# SPDX-License-Identifier: Apache-2.0
"""Fake-only contract tests for the optional managed Claude SDK adapter.

The adapter is deliberately tested at its boundary.  These tests do not
install, authenticate, or contact the official SDK: an injected client is the
only runtime used by the driving tests.  The option and event assertions are
shaped after the published SDK protocol so that a later live probe can reuse
the same evidence without making fake evidence look like live capability.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import select
import subprocess
import sys
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from lane_managed_sdk import (
    InitializationTracker,
    NativeLineageLedger,
    RunnerSpec,
    SdkAdapterError,
    _BoundedJsonLines,
    _RunnerConnection,
    _ToolEvidence,
    _build_guard_hooks,
    _event_to_mapping,
    _process_start_token,
    _read_first_frame,
    build_sdk_options,
    drive_client,
    popen_runner,
    scrubbed_runner_environment,
)


SESSION_ID = "11111111-1111-4111-8111-111111111111"
FRESH_SESSION_ID = "22222222-2222-4222-8222-222222222222"
MODEL = "claude-sonnet-4-20250514"
MESSAGE_ID = "msg-restore-0001"
ACCOUNT_EMAIL = "target@example.invalid"
_NATIVE_ADMISSION_ACK_FIELDS = (
    "admission_id",
    "owner_generation",
    "lineage_id",
    "runner_incarnation",
    "invocation_id",
    "tool_use_id",
    "trusted_definition_digest",
)


def _option_value(options, key: str, default=None):
    """Read either a mapping or the official SDK options object."""
    if isinstance(options, Mapping):
        return options.get(key, default)
    return getattr(options, key, default)


def _unset(value) -> bool:
    """Whether an option is absent or at its SDK default."""
    return value is None or value is False


def _runner_spec(tmp_path: Path, **overrides) -> RunnerSpec:
    """Build a plain participant specification with all readiness evidence."""
    values = {
        "profile": "team-a",
        "participant": "coordinator",
        "session_id": SESSION_ID,
        "resume": True,
        "model": MODEL,
        "permission_mode": "default",
        "worktree": tmp_path,
        "env": {
            "PATH": os.environ.get("PATH", "/usr/bin"),
            "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-config"),
        },
        "fingerprint": {
            "model": MODEL,
            "permission_mode": "default",
            "worktree": str(tmp_path),
        },
        "account_email": ACCOUNT_EMAIL,
        "supported_models": (MODEL,),
    }
    values.update(overrides)
    return RunnerSpec(**values)


def _init_event(
    *,
    account=ACCOUNT_EMAIL,
    permission_mode="default",
    session_id=None,
    model=None,
    session_state="idle",
    models=(MODEL,),
):
    """Return the raw initialization event observed from the SDK CLI."""
    event = {
        "type": "system",
        "subtype": "init",
        "account": {"email": account} if isinstance(account, str) else account,
        "current_permission_mode": permission_mode,
        "session_state": session_state,
        "models": list(models),
    }
    if session_id is not None:
        event["session_id"] = session_id
    if model is not None:
        event["model"] = model
    return event


class FakeClient:
    """Small bidirectional client with the official client method names."""

    _STOP = object()

    def __init__(self, options, events=()):
        self.options = options
        self._events: asyncio.Queue = asyncio.Queue()
        self.calls: list[tuple] = []
        self.seen_events: list[object] = []
        self.connected = asyncio.Event()
        self.interrupted = asyncio.Event()
        self.disconnected = asyncio.Event()
        self.initial_events = list(events)

    async def connect(self, prompt=None):
        self.calls.append(("connect", prompt))
        assert prompt is None
        self.connected.set()
        for event in self.initial_events:
            await self._events.put(event)

    async def receive_messages(self) -> AsyncIterator[object]:
        self.calls.append(("receive_messages",))
        while True:
            event = await self._events.get()
            if event is self._STOP:
                return
            self.seen_events.append(event)
            yield event

    async def interrupt(self):
        self.calls.append(("interrupt",))
        self.interrupted.set()

    async def query(self, payload, session_id="default"):
        self.calls.append(("query", payload, session_id))
        await self._events.put(
            {
                "type": "result",
                "subtype": "success",
                "session_id": SESSION_ID,
                "message_id": MESSAGE_ID,
                "payload": payload,
            }
        )

    async def stream_input(self, stream):
        """Record stream input while retaining compatibility with SDK fakes."""
        messages = []
        async for message in stream:
            messages.append(message)
        self.calls.append(("stream_input", messages))
        for message in messages:
            await self._events.put(
                {
                    "type": "result",
                    "subtype": "success",
                    "session_id": SESSION_ID,
                    "message_id": MESSAGE_ID,
                    "payload": message,
                }
            )

    async def disconnect(self):
        self.calls.append(("disconnect",))
        await self._events.put(self._STOP)
        self.disconnected.set()


class FakeClientFactory:
    """Capture construction so tests can prove one client survives the run."""

    def __init__(self, events=()):
        self.events = tuple(events)
        self.clients: list[FakeClient] = []

    def __call__(self, options):
        client = FakeClient(options, self.events)
        self.clients.append(client)
        return client


class FakeHookMatcher:
    """The 0.2.153 ``HookMatcher`` constructor shape, without the SDK import."""

    def __init__(self, matcher=None, hooks=None, timeout=None):
        self.matcher = matcher
        self.hooks = list(hooks or ())
        self.timeout = timeout


def _native_definition(*, tools=("Read", "Edit")):
    """Return only the pinned SDK 0.2.153 ``AgentDefinition`` fields."""
    return {
        "description": "authorized native child",
        "prompt": "inspect and update the requested files",
        "tools": list(tools),
        "model": MODEL,
        "permissionMode": "default",
    }


def _native_claim(tmp_path: Path):
    """Return the optional writer claim used by native tests."""
    return {
        "claim_id": "lineage-claim-1",
        "session_id": SESSION_ID,
        "workspace": str(tmp_path),
    }


def _native_lineage_context():
    """Return the required coordinator identity separate from writer claims."""
    return {
        "owner_generation": 1,
        "lineage_id": "lineage-1",
        "runner_incarnation": "runner-1",
    }


def _native_admission_ack(record, *, accepted: bool = True, **overrides):
    """Return the exact durable admission acknowledgement envelope."""
    acknowledgement = {
        "accepted": accepted,
        **{field: record[field] for field in _NATIVE_ADMISSION_ACK_FIELDS},
    }
    acknowledgement.update(overrides)
    return acknowledgement


def _begin_native(ledger, invocation_id: str):
    """Open the current parent invocation and pass the held-release gate."""
    assert ledger.begin_invocation(invocation_id) is None
    assert ledger.mark_released() is None


def _native_hooks(ledger):
    """Build the real SDK callback seam around one coordinator ledger."""
    evidence = _ToolEvidence()
    hook_error = {}
    hooks = _build_guard_hooks(
        SimpleNamespace(HookMatcher=FakeHookMatcher),
        evidence,
        hook_error,
        lineage=ledger,
    )
    assert hooks is not None
    assert set(hooks) == {
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "SubagentStart",
        "SubagentStop",
    }
    return hooks, evidence, hook_error


def _native_agent_pre(
    tool_use_id: str,
    *,
    agent_type: str = "writer",
    containing_agent_id: str | None = None,
    include_untrusted_policy: bool = False,
    prompt_id: str | None = None,
):
    """Build the measured PreToolUse/Agent hook shape."""
    event = {
        "session_id": SESSION_ID,
        "transcript_path": "/tmp/coordinator-transcript.jsonl",
        "cwd": "/tmp",
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": {
            "description": "authorized native child",
            "prompt": "inspect and update the requested files",
            "subagent_type": agent_type,
        },
        "tool_use_id": tool_use_id,
    }
    if include_untrusted_policy:
        # These are model/tool-input claims, not controller-owned definition
        # authority.  They remain inside the SDK's arbitrary tool_input map;
        # the hook must ignore them when binding the trusted definition.
        event["tool_input"].update(
            {
                "tools": ["Bash"],
                "lineage_claim": {"claim_id": "model-supplied-fake"},
            }
        )
    if prompt_id is not None:
        event["prompt_id"] = prompt_id
    if containing_agent_id is not None:
        # ``agent_id`` is the official optional sub-agent context field on
        # tool hooks; do not invent a parent_agent_id field in the fixture.
        event["agent_id"] = containing_agent_id
        event["agent_type"] = "writer"
    return event


def _native_agent_post(pre_event, *, response="accepted"):
    """Build the measured PostToolUse/Agent hook shape."""
    return {
        **pre_event,
        "hook_event_name": "PostToolUse",
        "tool_response": {"status": response},
    }


def _native_start(agent_id: str, *, agent_type: str = "writer"):
    """Build the exact SubagentStartHookInput fields from SDK 0.2.153."""
    return {
        "session_id": SESSION_ID,
        # SubagentStart reports the containing coordinator transcript.  The
        # child transcript is supplied only by SubagentStop below.
        "transcript_path": "/tmp/coordinator-transcript.jsonl",
        "cwd": "/tmp",
        "permission_mode": "default",
        "hook_event_name": "SubagentStart",
        "agent_id": agent_id,
        "agent_type": agent_type,
    }


def _native_stop(
    agent_id: str,
    *,
    transcript: str,
    agent_type: str = "writer",
    prompt_id: str | None = None,
):
    """Build the exact SubagentStopHookInput fields from SDK 0.2.153."""
    event = {
        "session_id": SESSION_ID,
        "transcript_path": "/tmp/coordinator-transcript.jsonl",
        "cwd": "/tmp",
        "permission_mode": "default",
        "hook_event_name": "SubagentStop",
        "stop_hook_active": False,
        "agent_id": agent_id,
        "agent_transcript_path": transcript,
        "agent_type": agent_type,
    }
    if prompt_id is not None:
        event["prompt_id"] = prompt_id
    return event


def _native_task_started(
    task_id: str,
    event_uuid: str,
    *,
    tool_use_id: str | None,
    task_type: str = "local_agent",
):
    """Build the exact TaskStartedMessage wire fields."""
    event = {
        "type": "system",
        "subtype": "task_started",
        "task_id": task_id,
        "description": "authorized native child",
        "uuid": event_uuid,
        "session_id": SESSION_ID,
        "task_type": task_type,
    }
    if tool_use_id is not None:
        event["tool_use_id"] = tool_use_id
    return event


def _native_task_progress(task_id: str, event_uuid: str, *, tool_use_id: str):
    """Build the exact TaskProgressMessage wire fields."""
    return {
        "type": "system",
        "subtype": "task_progress",
        "task_id": task_id,
        "description": "authorized native child",
        "usage": {"total_tokens": 12, "tool_uses": 1, "duration_ms": 3},
        "uuid": event_uuid,
        "session_id": SESSION_ID,
        "tool_use_id": tool_use_id,
        "last_tool_name": "Read",
    }


def _native_task_notification(
    task_id: str,
    event_uuid: str,
    *,
    status: str,
    tool_use_id: str | None = None,
    prompt_id: str | None = None,
):
    """Build the exact TaskNotificationMessage wire fields."""
    event = {
        "type": "system",
        "subtype": "task_notification",
        "task_id": task_id,
        "status": status,
        "output_file": "/tmp/task-output.txt",
        "summary": "task notification",
        "uuid": event_uuid,
        "session_id": SESSION_ID,
    }
    if tool_use_id is not None:
        event["tool_use_id"] = tool_use_id
    if prompt_id is not None:
        event["prompt_id"] = prompt_id
    return event


def _native_task_updated(task_id: str, event_uuid: str, *, status: str):
    """Build TaskUpdatedMessage without manufacturing a tool-use ID."""
    return {
        "type": "system",
        "subtype": "task_updated",
        "task_id": task_id,
        "patch": {"status": status},
        "status": status,
        "session_id": SESSION_ID,
        "uuid": event_uuid,
    }


class CachedInfoClient:
    """Fake the official client lifecycle and cached init API exactly."""

    _STOP = object()

    def __init__(self, server_info, stream_event=None):
        self.server_info = server_info
        self.stream_event = stream_event
        self.options = None
        self.events: asyncio.Queue = asyncio.Queue()
        self.calls: list[tuple] = []
        self.call_tasks: dict[str, asyncio.Task] = {}
        self.connected = asyncio.Event()
        self.stream_started = asyncio.Event()
        self.stream_event_seen = asyncio.Event()
        self.disconnected = asyncio.Event()
        if stream_event is not None:
            self.events.put_nowait(stream_event)

    def bind(self, options):
        self.options = options
        return self

    def _record(self, name, *args):
        self.calls.append((name, *args))
        task = asyncio.current_task()
        if task is not None:
            self.call_tasks[name] = task

    async def connect(self, prompt=None):
        self._record("connect", prompt)
        assert prompt is None
        self.connected.set()

    async def get_server_info(self):
        self._record("get_server_info")
        return self.server_info

    async def receive_messages(self) -> AsyncIterator[object]:
        self._record("receive_messages")
        self.stream_started.set()
        while True:
            event = await self.events.get()
            if event is self._STOP:
                return
            self.stream_event_seen.set()
            yield event

    async def query(self, payload):
        self._record("query", payload)
        await self.events.put(
            {
                "type": "result",
                "subtype": "success",
                "session_id": SESSION_ID,
                "message_id": MESSAGE_ID,
                "payload": payload,
            }
        )

    async def interrupt(self):
        self._record("interrupt")

    async def disconnect(self):
        self._record("disconnect")
        await self.events.put(self._STOP)
        self.disconnected.set()


def _cached_sdk(client):
    """Expose only the official SDK symbols used by ``drive_client``."""
    options_type = type(
        "FakeClaudeAgentOptions",
        (),
        {"__init__": lambda self, **values: self.__dict__.update(values)},
    )
    return SimpleNamespace(
        ClaudeAgentOptions=options_type,
        ClaudeSDKClient=lambda options: client.bind(options),
        HookMatcher=FakeHookMatcher,
    )


async def _wait_until(predicate, timeout=1.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("condition was not observed before the deadline")
        await asyncio.sleep(0)


async def _cancel_and_await(task):
    """Collect a drive task even when an assertion aborts its scenario."""
    if task is None:
        return
    if not task.done():
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.fixture
def error_result_while_initialization_pending():
    """An exact-resume loader error that arrives before the init response."""
    return [
        {
            "type": "result",
            "subtype": "error_during_execution",
            "is_error": True,
            "errors": ["No conversation found with session ID"],
            "session_id": SESSION_ID,
        }
    ]


def test_resume_options_use_exact_uuid_without_fallback_fields(tmp_path):
    spec = _runner_spec(tmp_path, resume=True, session_id=SESSION_ID)

    options = build_sdk_options(spec)

    assert _option_value(options, "resume") == SESSION_ID
    assert _unset(_option_value(options, "session_id"))
    assert _unset(_option_value(options, "fork_session"))
    assert _unset(_option_value(options, "continue_conversation"))
    assert _unset(_option_value(options, "title"))
    assert _option_value(options, "model") == MODEL
    assert _option_value(options, "permission_mode") == "default"
    assert Path(_option_value(options, "cwd", _option_value(options, "worktree"))) == tmp_path


def test_fresh_fixed_uuid_uses_session_id_and_no_resume(tmp_path):
    spec = _runner_spec(
        tmp_path,
        resume=False,
        session_id=FRESH_SESSION_ID,
    )

    options = build_sdk_options(spec)

    assert _option_value(options, "session_id") == FRESH_SESSION_ID
    assert _unset(_option_value(options, "resume"))
    assert _unset(_option_value(options, "fork_session"))
    assert _unset(_option_value(options, "continue_conversation"))
    assert _unset(_option_value(options, "title"))


def test_fresh_fixed_ids_remain_distinct_per_participant(tmp_path):
    first = _runner_spec(
        tmp_path / "worker-a",
        participant="worker-a",
        resume=False,
        session_id=FRESH_SESSION_ID,
    )
    second_id = "33333333-3333-4333-8333-333333333333"
    second = _runner_spec(
        tmp_path / "worker-b",
        participant="worker-b",
        resume=False,
        session_id=second_id,
    )

    first_options = build_sdk_options(first)
    second_options = build_sdk_options(second)

    assert _option_value(first_options, "session_id") == FRESH_SESSION_ID
    assert _option_value(second_options, "session_id") == second_id
    assert _option_value(first_options, "session_id") != _option_value(
        second_options, "session_id"
    )


def test_initialization_tracker_accepts_probe_shape_without_optional_echo(tmp_path):
    """The real probe omitted session_id/model, so readiness cannot require them."""
    spec = _runner_spec(tmp_path)
    tracker = InitializationTracker(
        expected_account_email=ACCOUNT_EMAIL,
        expected_permission_mode="default",
        expected_model=MODEL,
        supported_models=(MODEL,),
        expected_fingerprint=spec.fingerprint,
        expected_worktree=tmp_path,
    )

    assert tracker.observe(_init_event()) is True
    assert tracker.ready is True
    assert tracker.evidence["account_email"] == ACCOUNT_EMAIL
    assert tracker.evidence["permission_mode"] == "default"
    assert tracker.evidence["session_state"] == "idle"
    assert MODEL in tracker.evidence["supported_models"]


def test_initialization_tracker_rejects_truthy_account_without_email(tmp_path):
    """A token/provider dict is not account identity and must fail closed."""
    tracker = InitializationTracker(
        expected_account_email=ACCOUNT_EMAIL,
        expected_permission_mode="default",
        expected_model=MODEL,
        supported_models=(MODEL,),
        expected_fingerprint={"model": MODEL},
        expected_worktree=tmp_path,
    )

    with pytest.raises(SdkAdapterError, match="account|email|identity"):
        tracker.observe(
            _init_event(
                account={"tokenSource": "oauth", "apiProvider": "anthropic"}
            )
        )


@pytest.mark.parametrize(
    "event, expected",
    [
        (_init_event(permission_mode="plan"), "permission"),
        (_init_event(account=ACCOUNT_EMAIL, session_state="active"), "idle"),
        (_init_event(models=("claude-opus-4-20250514",)), "model"),
    ],
)
def test_initialization_evidence_must_match_profile_and_launch_fingerprint(
    tmp_path, event, expected
):
    tracker = InitializationTracker(
        expected_account_email=ACCOUNT_EMAIL,
        expected_permission_mode="default",
        expected_model=MODEL,
        supported_models=(MODEL,),
        expected_fingerprint={"model": MODEL},
        expected_worktree=tmp_path,
    )

    with pytest.raises(SdkAdapterError, match=expected):
        tracker.observe(event)


def test_initialization_rejects_ambiguous_resume_holder_evidence(tmp_path):
    tracker = InitializationTracker(
        expected_account_email=ACCOUNT_EMAIL,
        expected_permission_mode="default",
        expected_model=MODEL,
        supported_models=(MODEL,),
        expected_fingerprint={"model": MODEL},
        expected_worktree=tmp_path,
    )

    event = _init_event()
    event["session_holders"] = ["runner-a", "runner-b"]
    with pytest.raises(SdkAdapterError, match="holder|ambiguous|ownership"):
        tracker.observe(event)


def test_error_result_before_initialization_is_loader_failure(
    tmp_path,
    error_result_while_initialization_pending,
):
    spec = _runner_spec(tmp_path)
    tracker = InitializationTracker(
        expected_account_email=ACCOUNT_EMAIL,
        expected_permission_mode="default",
        expected_model=MODEL,
        supported_models=(MODEL,),
        expected_fingerprint=spec.fingerprint,
        expected_worktree=tmp_path,
    )

    with pytest.raises(SdkAdapterError, match="loader|error_during_execution|conversation"):
        for event in error_result_while_initialization_pending:
            tracker.observe(event)

    assert tracker.ready is False


def test_drive_client_keeps_context_held_until_release_then_sends_one_correlated_payload(
    tmp_path,
):
    """Connect/read/interrupt/release/disconnect all use one async client."""

    async def scenario():
        spec = _runner_spec(tmp_path)
        factory = FakeClientFactory(events=(_init_event(),))
        release = asyncio.Event()
        interrupt = asyncio.Event()
        observed = []
        payload = {"role": "user", "content": "explicit restore message"}

        task = asyncio.create_task(
            drive_client(
                spec,
                client_factory=factory,
                release_event=release,
                interrupt_event=interrupt,
                payload=payload,
                message_id=MESSAGE_ID,
                on_event=observed.append,
            )
        )
        try:
            deadline = asyncio.get_running_loop().time() + 1
            while not factory.clients and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0)
            assert factory.clients, "drive_client did not construct an injected client"
            await asyncio.wait_for(factory.clients[0].connected.wait(), timeout=1)
            client = factory.clients[0]
            deadline = asyncio.get_running_loop().time() + 1
            while not observed and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0)
            assert client.calls[:2] == [("connect", None), ("receive_messages",)]
            assert not [call for call in client.calls if call[0] in ("query", "stream_input")]
            assert observed and observed[0]["subtype"] == "init"

            interrupt.set()
            await asyncio.wait_for(client.interrupted.wait(), timeout=1)
            assert not [call for call in client.calls if call[0] in ("query", "stream_input")]

            release.set()
            await asyncio.wait_for(task, timeout=1)

            input_calls = [
                call for call in client.calls if call[0] in ("query", "stream_input")
            ]
            assert len(input_calls) == 1
            if input_calls[0][0] == "query":
                assert input_calls[0][1] == payload
                assert input_calls[0][2] == MESSAGE_ID
            else:
                assert input_calls[0][1] == [{**payload, "message_id": MESSAGE_ID}]
            assert client.calls[-1] == ("disconnect",)
            assert client.disconnected.is_set()
            assert len(factory.clients) == 1
            assert any(
                event.get("message_id") == MESSAGE_ID
                and event.get("session_id") == SESSION_ID
                for event in observed
                if isinstance(event, Mapping)
            )
        finally:
            await _cancel_and_await(task)

    asyncio.run(scenario())


def test_drive_client_rejects_uncorrelated_runtime_events(tmp_path):
    async def scenario():
        spec = _runner_spec(tmp_path)
        factory = FakeClientFactory(
            events=(
                _init_event(),
                {
                    "type": "assistant",
                    "session_id": "wrong-session",
                    "message_id": MESSAGE_ID,
                },
            )
        )

        release = asyncio.Event()
        release.set()
        with pytest.raises(SdkAdapterError, match="correlat|session|identity"):
            await drive_client(
                spec,
                client_factory=factory,
                release_event=release,
            )

    asyncio.run(scenario())


def test_scrubbed_environment_is_clean_at_actual_child_boundary(tmp_path):
    config_dir = tmp_path / "selected-profile"
    config_dir.mkdir()
    source = dict(os.environ)
    source.update(
        {
            "PATH": os.environ.get("PATH", "/usr/bin"),
            "HOME": str(tmp_path / "home"),
            "KEEP_UNRELATED": "retained",
            "CLAUDE_PROFILE_NAME": "selected-profile",
            "LANE_SESSION_NAME": "worker-a",
            "ANTHROPIC_API_KEY": "must-not-cross",
            "AUTH_TOKEN": "must-not-cross",
            "ANTHROPIC_AUTH_TOKEN": "must-not-cross",
            "CLAUDE_CODE_OAUTH_TOKEN": "must-not-cross",
            "ANTHROPIC_BASE_URL": "https://provider.invalid",
            "ANTHROPIC_API_URL": "https://api.invalid",
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "CLAUDE_CODE_USE_VERTEX": "1",
            "AWS_BEDROCK_RUNTIME_ENDPOINT": "https://bedrock.invalid",
            "GOOGLE_CLOUD_PROJECT": "wrong-project",
            "VERTEXAI_PROJECT": "wrong-project",
            "CLAUDE_CONFIG_DIR": str(tmp_path / "inherited-profile"),
        }
    )

    sanitized = scrubbed_runner_environment(source, config_dir=config_dir)
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, os; print(json.dumps(dict(os.environ)))",
        ],
        env=sanitized,
        capture_output=True,
        text=True,
        check=True,
    )
    child_env = json.loads(probe.stdout)

    for forbidden in (
        "ANTHROPIC_API_KEY",
        "AUTH_TOKEN",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_URL",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "AWS_BEDROCK_RUNTIME_ENDPOINT",
        "GOOGLE_CLOUD_PROJECT",
        "VERTEXAI_PROJECT",
    ):
        assert forbidden not in child_env
    assert child_env["KEEP_UNRELATED"] == "retained"
    assert child_env["CLAUDE_PROFILE_NAME"] == "selected-profile"
    assert child_env["LANE_SESSION_NAME"] == "worker-a"
    assert child_env["CLAUDE_CONFIG_DIR"] == str(config_dir)


def test_process_start_token_uses_bounded_ps_when_proc_is_unavailable(monkeypatch):
    """The macOS-style path still records one bounded PID incarnation token."""
    import lane_managed_sdk as sdk

    original_read_text = sdk.Path.read_text

    def no_proc(path, *args, **kwargs):
        if str(path).startswith("/proc/"):
            raise FileNotFoundError(str(path))
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(sdk.Path, "read_text", no_proc)
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((list(argv), dict(kwargs)))
        return SimpleNamespace(
            returncode=0,
            stdout="Mon Sep 16 12:34:56 2026\n",
            stderr="",
        )

    monkeypatch.setattr(sdk.subprocess, "run", fake_run)
    token = _process_start_token(4242, SimpleNamespace())

    assert token == "Mon Sep 16 12:34:56 2026"
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv[0] == "ps"
    assert "-p" in argv and argv[argv.index("-p") + 1] == "4242"
    assert "-o" in argv and argv[argv.index("-o") + 1] in {"lstart", "lstart="}
    assert kwargs.get("timeout") is not None
    assert 0 < float(kwargs["timeout"]) <= 1


@pytest.mark.parametrize("failure", ["timeout", "malformed"])
def test_process_start_token_ps_failure_is_missing_identity_fail_closed(
    monkeypatch, failure
):
    """Timeouts and untrusted ps output never become a start token."""
    import lane_managed_sdk as sdk

    original_read_text = sdk.Path.read_text

    def no_proc(path, *args, **kwargs):
        if str(path).startswith("/proc/"):
            raise FileNotFoundError(str(path))
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(sdk.Path, "read_text", no_proc)

    def fake_run(argv, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
        return SimpleNamespace(
            returncode=0,
            stdout="malformed start token\nwith an extra line\n",
            stderr="",
        )

    monkeypatch.setattr(sdk.subprocess, "run", fake_run)
    assert _process_start_token(4242, SimpleNamespace()) is None


def test_missing_optional_sdk_is_an_explicit_refusal(tmp_path):
    async def scenario():
        spec = _runner_spec(tmp_path)

        def missing_sdk():
            raise ImportError("claude-agent-sdk is optional and unavailable")

        with pytest.raises(SdkAdapterError, match="optional|SDK|unavailable"):
            await drive_client(spec, sdk_loader=missing_sdk)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "event",
    [
        "{not-json}\n",
        json.dumps({"type": "system", "subtype": "init"}) + "\n",
    ],
)
def test_malformed_or_incomplete_json_event_fails_closed(tmp_path, event):
    tracker = InitializationTracker(
        expected_account_email=ACCOUNT_EMAIL,
        expected_permission_mode="default",
        expected_model=MODEL,
        supported_models=(MODEL,),
        expected_fingerprint={"model": MODEL},
        expected_worktree=tmp_path,
    )

    with pytest.raises(SdkAdapterError, match="malformed|invalid|account|init"):
        tracker.observe_json(event)


def test_oversized_json_event_is_bounded_and_refused(tmp_path):
    tracker = InitializationTracker(
        expected_account_email=ACCOUNT_EMAIL,
        expected_permission_mode="default",
        expected_model=MODEL,
        supported_models=(MODEL,),
        expected_fingerprint={"model": MODEL},
        expected_worktree=tmp_path,
        max_event_bytes=1024,
    )
    oversized = json.dumps({"type": "system", "subtype": "init", "padding": "x" * 2048})

    with pytest.raises(SdkAdapterError, match="size|large|bound"):
        tracker.observe_json(oversized)


def test_drive_client_uses_cached_init_then_keeps_one_continuous_client_context(
    tmp_path, monkeypatch
):
    """The official client's cached init and response stream share one context."""

    async def scenario():
        # This is the direct fake ``drive_client`` seam.  Process-group proof
        # belongs to the dedicated ``popen_runner`` test below; setting the
        # production runner marker here would conflate the two boundaries.
        monkeypatch.delenv("LANE_MANAGED_SDK_RUNNER", raising=False)
        spec = _runner_spec(
            tmp_path,
            model="sonnet",
            supported_models=("sonnet",),
            fingerprint={
                "model": "sonnet",
                "resolvedModel": MODEL,
                "permission_mode": "default",
                "worktree": str(tmp_path),
            },
            profile_name="selected-profile",
            session_name="worker-a",
        )
        server_info = {
            "type": "system",
            "subtype": "init",
            "account": {"email": ACCOUNT_EMAIL, "tokenSource": "subscription"},
            "current_permission_mode": "default",
            "session_state": "idle",
            "models": [
                {
                    "value": "sonnet",
                    "resolvedModel": MODEL,
                    "displayName": "Claude Sonnet",
                }
            ],
        }
        response = SimpleNamespace(
            content=[{"type": "text", "text": "continuous response"}],
            model="sonnet",
            session_id=SESSION_ID,
            message_id="assistant-0001",
        )
        client = CachedInfoClient(server_info, response)
        sdk = _cached_sdk(client)
        controls: asyncio.Queue = asyncio.Queue()
        emitted = []

        task = asyncio.create_task(
            drive_client(
                spec,
                controls=controls,
                emit=emitted.append,
                sdk_module=sdk,
            )
        )
        try:
            await asyncio.wait_for(client.connected.wait(), timeout=1)
            await asyncio.wait_for(client.stream_started.wait(), timeout=1)
            await asyncio.wait_for(client.stream_event_seen.wait(), timeout=1)

            assert [call[0] for call in client.calls[:3]] == [
                "connect",
                "get_server_info",
                "receive_messages",
            ]
            assert client.calls[0][1] is None
            assert any(
                isinstance(event, Mapping)
                and event.get("content") == response.content
                for event in emitted
            ), "the continuous response stream was never observed"
            assert not [call for call in client.calls if call[0] == "query"]

            await controls.put({"operation": "status"})
            await _wait_until(
                lambda: any(
                    isinstance(event, Mapping) and event.get("type") == "status"
                    for event in emitted
                )
            )
            assert not task.done(), "a held runner must remain alive while idle"

            await controls.put({"operation": "shutdown"})
            result = await asyncio.wait_for(task, timeout=1)

            assert result["ready"] is True
            assert result["released"] is False
            initialization = result["evidence"]["initialization"]
            assert initialization["account_email"] == ACCOUNT_EMAIL
            assert initialization["permission_mode"] == "default"
            assert initialization["model"] == "sonnet"
            assert initialization["fingerprint"]["resolvedModel"] == MODEL
            init_event = next(
                event
                for event in emitted
                if isinstance(event, Mapping) and event.get("subtype") == "init"
            )
            assert init_event["models"] == [
                {
                    "value": "sonnet",
                    "resolvedModel": MODEL,
                    "displayName": "Claude Sonnet",
                }
            ]
            assert client.call_tasks["connect"] is client.call_tasks["disconnect"]
            assert client.call_tasks["receive_messages"] is not client.call_tasks["connect"]
            assert client.disconnected.is_set()
        finally:
            await _cancel_and_await(task)

    asyncio.run(scenario())


def test_cached_server_info_requires_exact_account_email(tmp_path, monkeypatch):
    """A truthy provider/account object without the expected email is refusal."""

    async def scenario():
        monkeypatch.delenv("LANE_MANAGED_SDK_RUNNER", raising=False)
        info = {
            "type": "system",
            "subtype": "init",
            "account": {"tokenSource": "oauth", "apiProvider": "anthropic"},
            "current_permission_mode": "default",
            "session_state": "idle",
            "models": [MODEL],
        }
        client = CachedInfoClient(info)
        with pytest.raises(SdkAdapterError, match="account|email|identity"):
            await drive_client(
                _runner_spec(tmp_path),
                controls=asyncio.Queue(),
                sdk_module=_cached_sdk(client),
            )
        assert client.disconnected.is_set()

    asyncio.run(scenario())


def test_cached_server_info_account_mismatch_reaches_identity_check(
    tmp_path, monkeypatch
):
    """A returned account email different from the profile is an identity refusal."""

    async def scenario():
        monkeypatch.delenv("LANE_MANAGED_SDK_RUNNER", raising=False)
        info = _init_event(account="other@example.invalid")
        client = CachedInfoClient(info)
        with pytest.raises(SdkAdapterError) as caught:
            await drive_client(
                _runner_spec(tmp_path),
                controls=asyncio.Queue(),
                sdk_module=_cached_sdk(client),
            )
        assert caught.value.code == "account-mismatch"
        assert client.disconnected.is_set()

    asyncio.run(scenario())


def test_sdk_hook_matchers_track_success_and_failure_lifecycle():
    """0.2.153 HookMatcher callbacks provide the authoritative tool ledger."""

    async def scenario():
        evidence = _ToolEvidence()
        hook_error = {}
        hooks = _build_guard_hooks(
            SimpleNamespace(HookMatcher=FakeHookMatcher), evidence, hook_error
        )
        assert hooks is not None
        assert set(hooks) == {
            "PreToolUse",
            "PostToolUse",
            "PostToolUseFailure",
            "SubagentStart",
            "SubagentStop",
        }
        assert all(isinstance(matchers[0], FakeHookMatcher) for matchers in hooks.values())

        pre = hooks["PreToolUse"][0].hooks[0]
        post = hooks["PostToolUse"][0].hooks[0]
        failure = hooks["PostToolUseFailure"][0].hooks[0]
        common = {
            "session_id": SESSION_ID,
            "transcript_path": "/tmp/managed-sdk-test.jsonl",
            "cwd": "/tmp",
        }

        first = {
            **common,
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "printf ok"},
            "tool_use_id": "tool-success",
        }
        assert await pre(first, "tool-success", {"signal": None}) == {}
        first_post = {
            **first,
            "hook_event_name": "PostToolUse",
            "tool_response": {"stdout": "ok"},
        }
        assert await post(first_post, "tool-success", {"signal": None}) == {}

        second = {
            **common,
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "false"},
            "tool_use_id": "tool-failure",
        }
        assert await pre(second, "tool-failure", {"signal": None}) == {}
        second_failure = {
            **second,
            "hook_event_name": "PostToolUseFailure",
            "error": "command failed",
            "is_interrupt": False,
        }
        assert await failure(second_failure, "tool-failure", {"signal": None}) == {}

        snapshot = evidence.snapshot()
        assert snapshot["active"] == []
        assert snapshot["uncertain"] == []
        assert [item["tool_use_id"] for item in snapshot["completed"]] == [
            "tool-success",
            "tool-failure",
        ]
        assert snapshot["completed"][1]["failure"] is True
        assert hook_error == {}

    asyncio.run(scenario())


def test_native_agent_admission_binds_immutable_child_policy_before_allow(tmp_path):
    """A native Agent is durably admitted before execution and keeps policy."""

    async def scenario():
        definition = _native_definition()
        parent_claim = _native_claim(tmp_path)
        lineage_context = _native_lineage_context()
        persisted = []
        admission_started = asyncio.Event()
        admission_ack = asyncio.Event()
        context = {"signal": None}

        async def persist_admission(record):
            persisted.append(dict(record))
            admission_started.set()
            await admission_ack.wait()
            return _native_admission_ack(record)

        ledger = NativeLineageLedger(
            SESSION_ID,
            trusted_definitions={"writer": definition},
            parent_read_only=True,
            lineage_context=lineage_context,
            lineage_claim=parent_claim,
            persist_admission=persist_admission,
        )

        held = NativeLineageLedger(
            SESSION_ID,
            trusted_definitions={"writer": _native_definition()},
            parent_read_only=True,
            lineage_context=lineage_context,
            lineage_claim=parent_claim,
            persist_admission=persist_admission,
        )
        assert held.begin_invocation("held-before-release") is None
        assert held.released is False
        assert held.ready_for_hold is True
        assert held.mark_released() is None
        assert held.released is True

        invalid_persistence_calls = []

        async def never_called(record):
            invalid_persistence_calls.append(record)
            raise AssertionError("invalid lineage identity reached persistence")

        invalid_contexts = []
        for field, values in (
            ("owner_generation", (0, -1, 1.0, True)),
            ("lineage_id", (None, "")),
            ("runner_incarnation", (None, "")),
        ):
            for value in values:
                invalid_contexts.append(
                    {
                        **lineage_context,
                        field: value,
                    }
                )
        invalid_contexts.extend(
            [
                {key: value for key, value in lineage_context.items() if key != "lineage_id"},
                {key: value for key, value in lineage_context.items() if key != "runner_incarnation"},
            ]
        )
        for index, invalid_context in enumerate(invalid_contexts):
            invalid = NativeLineageLedger(
                SESSION_ID,
                trusted_definitions={"writer": _native_definition()},
                parent_read_only=True,
                lineage_context=invalid_context,
                lineage_claim=parent_claim,
                persist_admission=never_called,
            )
            _begin_native(invalid, f"invalid-lineage-{index}")
            invalid_hooks, _evidence, _hook_error = _native_hooks(invalid)
            denied = await invalid_hooks["PreToolUse"][0].hooks[0](
                _native_agent_pre(f"invalid-lineage-tool-{index}"),
                f"invalid-lineage-tool-{index}",
                context,
            )
            assert denied["continue_"] is False
            assert invalid.snapshot()["pending_admissions"] == []
        assert invalid_persistence_calls == []

        _begin_native(ledger, "parent-invocation-1")
        hooks, _evidence, hook_error = _native_hooks(ledger)
        pre = _native_agent_pre("agent-tool-1", include_untrusted_policy=True)

        # The allow decision follows a durable callback/ack, not a memory-only
        # pending dict.  The model's launch prompt is not policy authority.
        allow_task = asyncio.create_task(hooks["PreToolUse"][0].hooks[0](
            pre, "agent-tool-1", context
        ))
        await asyncio.wait_for(admission_started.wait(), timeout=1)
        assert not allow_task.done()
        assert ledger.snapshot()["pending_admissions"][0]["tool_use_id"] == "agent-tool-1"
        admission_ack.set()
        response = await allow_task
        assert response == {}
        assert persisted
        assert {
            "admission_id",
            "owner_generation",
            "lineage_id",
            "runner_incarnation",
            "invocation_id",
            "tool_use_id",
            "trusted_definition_digest",
        } <= persisted[0].keys()
        assert persisted[0]["tool_use_id"] == "agent-tool-1"
        assert persisted[0]["invocation_id"] == "parent-invocation-1"
        assert persisted[0]["owner_generation"] == lineage_context["owner_generation"]
        assert persisted[0]["lineage_id"] == lineage_context["lineage_id"]
        assert persisted[0]["runner_incarnation"] == lineage_context["runner_incarnation"]
        admission_digest = persisted[0]["trusted_definition_digest"]
        assert admission_digest
        assert persisted[0]["admission_id"]
        assert persisted[0]["watermark"]
        assert hook_error == {}
        admission = ledger.snapshot()["pending_admissions"][0]
        assert admission["tool_use_id"] == "agent-tool-1"
        assert admission["custom_definition"]["digest"] == admission_digest

        async def persist_refused(record):
            return _native_admission_ack(record, accepted=False)

        refused_ledger = NativeLineageLedger(
            SESSION_ID,
            trusted_definitions={"writer": _native_definition()},
            parent_read_only=True,
            lineage_context=lineage_context,
            lineage_claim=parent_claim,
            persist_admission=persist_refused,
        )
        _begin_native(refused_ledger, "parent-invocation-refused")
        refused_hooks, _evidence, _hook_error = _native_hooks(refused_ledger)
        refused = await refused_hooks["PreToolUse"][0].hooks[0](
            _native_agent_pre("agent-tool-refused"), "agent-tool-refused", context
        )
        assert refused["continue_"] is False
        assert refused["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert refused_ledger.snapshot()["pending_admissions"] == []

        async def persist_wrong_ack(record):
            return _native_admission_ack(
                record,
                admission_id="wrong-admission-id",
            )

        def wrong_ack_field(field):
            async def persist_wrong_field(record):
                return _native_admission_ack(
                    record,
                    **{field: f"wrong-{field}"},
                )

            return persist_wrong_field

        async def persist_disconnected(_record):
            raise ConnectionError("admission control reader disconnected")

        async def persist_timeout(_record):
            await asyncio.sleep(5)

        async def persist_bool(_record):
            return True

        async def persist_missing(record):
            acknowledgement = _native_admission_ack(record)
            del acknowledgement["trusted_definition_digest"]
            return acknowledgement

        async def persist_missing_accepted(record):
            acknowledgement = _native_admission_ack(record)
            del acknowledgement["accepted"]
            return acknowledgement

        async def persist_missing_invocation(record):
            acknowledgement = _native_admission_ack(record)
            del acknowledgement["invocation_id"]
            return acknowledgement

        async def persist_none_invocation(record):
            return _native_admission_ack(record, invocation_id=None)

        async def persist_missing_lineage_id(record):
            acknowledgement = _native_admission_ack(record)
            del acknowledgement["lineage_id"]
            return acknowledgement

        async def persist_none_lineage_id(record):
            return _native_admission_ack(record, lineage_id=None)

        async def persist_missing_runner_incarnation(record):
            acknowledgement = _native_admission_ack(record)
            del acknowledgement["runner_incarnation"]
            return acknowledgement

        async def persist_none_runner_incarnation(record):
            return _native_admission_ack(record, runner_incarnation=None)

        failed_callbacks = [
            (persist_wrong_ack, "wrong-admission-id"),
            *[
                (wrong_ack_field(field), f"wrong-{field}")
                for field in _NATIVE_ADMISSION_ACK_FIELDS
                if field != "admission_id"
            ],
            (persist_disconnected, "disconnected"),
            (persist_timeout, "timeout"),
            (persist_bool, "bare-bool"),
            (persist_missing, "missing-trusted-definition-digest"),
            (persist_missing_accepted, "missing-accepted"),
            (persist_missing_invocation, "missing-invocation"),
            (persist_none_invocation, "none-invocation"),
            (persist_missing_lineage_id, "missing-lineage-id"),
            (persist_none_lineage_id, "none-lineage-id"),
            (persist_missing_runner_incarnation, "missing-runner-incarnation"),
            (persist_none_runner_incarnation, "none-runner-incarnation"),
        ]
        for callback, suffix in failed_callbacks:
            failed_ledger = NativeLineageLedger(
                SESSION_ID,
                trusted_definitions={"writer": _native_definition()},
                parent_read_only=True,
                lineage_context=lineage_context,
                lineage_claim=parent_claim,
                persist_admission=callback,
            )
            _begin_native(failed_ledger, f"parent-invocation-{suffix}")
            failed_hooks, _evidence, _hook_error = _native_hooks(failed_ledger)
            failed_call = failed_hooks["PreToolUse"][0].hooks[0](
                _native_agent_pre(f"agent-tool-{suffix}"),
                f"agent-tool-{suffix}",
                context,
            )
            failed = await asyncio.wait_for(failed_call, timeout=1)
            assert failed["continue_"] is False
            assert failed["hookSpecificOutput"]["permissionDecision"] == "deny"
            assert failed_ledger.snapshot()["pending_admissions"] == []

        fenced_holder = []

        async def persist_fenced(record):
            fenced_holder[0].lineage_context = {
                **lineage_context,
                "lineage_id": "lineage-replaced-during-ack",
            }
            return _native_admission_ack(record)

        fenced_ledger = NativeLineageLedger(
            SESSION_ID,
            trusted_definitions={"writer": _native_definition()},
            parent_read_only=True,
            lineage_context=lineage_context,
            lineage_claim=parent_claim,
            persist_admission=persist_fenced,
        )
        fenced_holder.append(fenced_ledger)
        _begin_native(fenced_ledger, "parent-invocation-before-fence")
        fenced_hooks, _evidence, _hook_error = _native_hooks(fenced_ledger)
        fenced = await fenced_hooks["PreToolUse"][0].hooks[0](
            _native_agent_pre("agent-tool-fenced"), "agent-tool-fenced", context
        )
        assert fenced["continue_"] is False
        assert fenced["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert fenced_ledger.snapshot()["pending_admissions"] == []

        # A caller-side mutation after construction cannot broaden the trusted
        # child definition captured by the ledger.
        definition["tools"].append("Bash")
        start = _native_start("agent-1")
        stop = _native_stop("agent-1", transcript="/tmp/agent-1.jsonl")
        assert start["transcript_path"] == "/tmp/coordinator-transcript.jsonl"
        assert {"task_id", "tool_use_id", "parent_agent_id"}.isdisjoint(start)
        assert {"task_id", "tool_use_id", "parent_agent_id"}.isdisjoint(stop)
        assert await hooks["SubagentStart"][0].hooks[0](start, None, context) == {}

        child = next(
            row for row in ledger.snapshot()["children"] if row["agent_id"] == "agent-1"
        )
        assert child["type"] == "writer"
        assert child["tool_use_id"] == "agent-tool-1"
        assert child["parent_links"]["session_id"] == SESSION_ID
        assert child["tools"] == ["Read", "Edit"]
        assert child["claim_ref"] == parent_claim
        assert child["transcript"]["coordinator_path"] == "/tmp/coordinator-transcript.jsonl"
        assert child["transcript"]["child_path"] is None
        assert child.get("task_id") is None
        assert "session_id" not in child
        assert "runner_instance_id" not in child
        assert "process_group_id" not in child
        assert ledger.quiescent is False

        # Agent launch completion is not native child completion.
        assert await hooks["PostToolUse"][0].hooks[0](
            _native_agent_post(pre), "agent-tool-1", context
        ) == {}
        child = next(
            row for row in ledger.snapshot()["children"] if row["agent_id"] == "agent-1"
        )
        assert child["status"] not in {"completed", "failed", "stopped", "killed"}
        assert ledger.quiescent is False

        started = _native_task_started(
            "agent-1", "task-event-agent-1", tool_use_id="agent-tool-1"
        )
        assert started["task_type"] == "local_agent"
        assert ledger.observe(_event_to_mapping(started)) is None
        assert ledger.observe(_event_to_mapping(
            _native_task_updated("agent-1", "task-updated-agent-1", status="completed")
        )) is None
        assert await hooks["SubagentStop"][0].hooks[0](stop, None, context) == {}
        child = next(
            row for row in ledger.snapshot()["children"] if row["agent_id"] == "agent-1"
        )
        assert child["transcript"]["child_path"] == "/tmp/agent-1.jsonl"
        assert child["status"] == "completed"

    asyncio.run(scenario())


def test_native_task_and_nested_child_lifecycle_gate_quiescence(tmp_path):
    """Task/tool/child state stays held until every current item is terminal."""

    async def scenario():
        persisted = []
        lineage_context = _native_lineage_context()

        async def persist_admission(record):
            persisted.append(dict(record))
            return _native_admission_ack(record)

        ledger = NativeLineageLedger(
            SESSION_ID,
            trusted_definitions={"writer": _native_definition()},
            parent_read_only=True,
            lineage_context=lineage_context,
            lineage_claim=_native_claim(tmp_path),
            persist_admission=persist_admission,
        )
        _begin_native(ledger, "parent-invocation-2")
        hooks, _evidence, hook_error = _native_hooks(ledger)
        context = {"signal": None}
        parent_pre = _native_agent_pre("agent-tool-parent")
        nested_pre = _native_agent_pre(
            "agent-tool-child", containing_agent_id="agent-parent"
        )
        assert "agent_id" not in parent_pre
        assert nested_pre["agent_id"] == "agent-parent"
        assert "parent_agent_id" not in nested_pre
        assert await hooks["PreToolUse"][0].hooks[0](
            parent_pre, "agent-tool-parent", context
        ) == {}
        assert await hooks["SubagentStart"][0].hooks[0](
            _native_start("agent-parent"), None, context
        ) == {}
        assert await hooks["PreToolUse"][0].hooks[0](
            nested_pre, "agent-tool-child", context
        ) == {}
        assert await hooks["SubagentStart"][0].hooks[0](
            _native_start("agent-child"), None, context
        ) == {}

        # Tool hooks from inside a child use the SDK's optional agent_id
        # context; no synthetic parent field is accepted.
        write_pre = {
            "session_id": SESSION_ID,
            "transcript_path": "/tmp/coordinator-transcript.jsonl",
            "cwd": "/tmp",
            "hook_event_name": "PreToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/tmp/requested.txt",
                "old_string": "before",
                "new_string": "after",
            },
            "tool_use_id": "write-tool-1",
            "agent_id": "agent-child",
            "agent_type": "writer",
        }
        assert await hooks["PreToolUse"][0].hooks[0](
            write_pre, "write-tool-1", context
        ) == {}
        assert ledger.ready_for_hold is False
        assert ledger.quiescent is False

        # Closing either Agent launch does not close either child or the Edit.
        assert await hooks["PostToolUse"][0].hooks[0](
            _native_agent_post(parent_pre), "agent-tool-parent", context
        ) == {}
        assert await hooks["PostToolUse"][0].hooks[0](
            _native_agent_post(nested_pre), "agent-tool-child", context
        ) == {}
        assert hook_error == {}
        assert ledger.quiescent is False

        assert ledger.observe(_event_to_mapping(_native_task_started(
            "agent-parent", "task-event-parent", tool_use_id="agent-tool-parent"
        ))) is None
        assert ledger.observe(_event_to_mapping(_native_task_progress(
            "agent-parent", "task-progress-parent", tool_use_id="agent-tool-parent"
        ))) is None
        assert ledger.observe(_event_to_mapping(_native_task_notification(
            "agent-parent",
            "task-notification-parent",
            status="completed",
            tool_use_id="agent-tool-parent",
        ))) is None
        parent = next(
            row for row in ledger.snapshot()["children"] if row["agent_id"] == "agent-parent"
        )
        # A strictly correlated terminal notification closes the task, while
        # the child lifecycle still remains independently observable.
        assert parent["status"] == "completed"
        assert parent["task_terminal"] is True
        assert ledger.observe(_event_to_mapping(_native_task_updated(
            "agent-parent", "task-updated-parent", status="completed"
        ))) is None

        assert ledger.observe(_event_to_mapping(_native_task_started(
            "agent-child", "task-event-child", tool_use_id="agent-tool-child"
        ))) is None
        assert ledger.observe(_event_to_mapping(_native_task_progress(
            "agent-child", "task-progress-child", tool_use_id="agent-tool-child"
        ))) is None
        assert await hooks["SubagentStop"][0].hooks[0](
            _native_stop("agent-child", transcript="/tmp/agent-child.jsonl"),
            None,
            context,
        ) == {}
        child = next(
            row for row in ledger.snapshot()["children"] if row["agent_id"] == "agent-child"
        )
        assert child["status"] == "restart-pending"
        assert child["task_terminal"] is False
        assert ledger.ready_for_hold is False
        assert ledger.quiescent is False
        assert ledger.observe(_event_to_mapping(_native_task_notification(
            "agent-child",
            "task-notification-child",
            status="stopped",
            tool_use_id="agent-tool-child",
        ))) is None
        child = next(
            row for row in ledger.snapshot()["children"] if row["agent_id"] == "agent-child"
        )
        assert child["status"] == "restart-pending"
        assert child["task_terminal"] is True
        assert ledger.quiescent is False
        assert ledger.observe(_event_to_mapping(_native_task_updated(
            "agent-child", "task-updated-child", status="killed"
        ))) is None
        assert ledger.quiescent is False

        write_post = {
            **write_pre,
            "hook_event_name": "PostToolUse",
            "tool_response": {"file_path": "/tmp/requested.txt"},
        }
        assert await hooks["PostToolUse"][0].hooks[0](
            write_post, "write-tool-1", context
        ) == {}
        assert ledger.quiescent is True
        assert await hooks["SubagentStop"][0].hooks[0](
            _native_stop("agent-child", transcript="/tmp/agent-child.jsonl"),
            None,
            context,
        ) == {}
        assert ledger.quiescent is True
        assert await hooks["SubagentStop"][0].hooks[0](
            _native_stop("agent-parent", transcript="/tmp/agent-parent.jsonl"),
            None,
            context,
        ) == {}
        assert ledger.quiescent is True

        children = {
            row["agent_id"]: row for row in ledger.snapshot()["children"]
        }
        assert children["agent-parent"]["task_id"] == "agent-parent"
        assert children["agent-child"]["task_id"] == "agent-child"
        assert children["agent-child"]["parent_links"]["parent_agent_id"] == "agent-parent"
        assert children["agent-child"]["tool_use_id"] == "agent-tool-child"
        assert children["agent-parent"]["status"] == "completed"
        assert children["agent-child"]["status"] in {"resume-pending", "restart-pending"}
        assert children["agent-child"]["stop_provenance"]["kind"] == "stopped"
        assert "tool_use_id" not in _native_task_updated(
            "agent-child", "task-updated-check", status="completed"
        )
        for child in children.values():
            assert "session_id" not in child
            assert "runner_instance_id" not in child
            assert "process_group_id" not in child

        async def terminal_task_case(status, *, via_update):
            case = NativeLineageLedger(
                SESSION_ID,
                trusted_definitions={"writer": _native_definition()},
                parent_read_only=True,
                lineage_context=lineage_context,
                lineage_claim=_native_claim(tmp_path),
                persist_admission=persist_admission,
            )
            _begin_native(case, f"terminal-{status}-{'update' if via_update else 'notification'}")
            case_hooks, _case_evidence, _case_hook_error = _native_hooks(case)
            tool_id = f"terminal-tool-{status}-{'update' if via_update else 'notification'}"
            agent_id = f"terminal-agent-{status}-{'update' if via_update else 'notification'}"
            assert await case_hooks["PreToolUse"][0].hooks[0](
                _native_agent_pre(tool_id), tool_id, context
            ) == {}
            assert await case_hooks["SubagentStart"][0].hooks[0](
                _native_start(agent_id), None, context
            ) == {}
            assert case.observe(_event_to_mapping(_native_task_started(
                agent_id, f"{agent_id}-start", tool_use_id=tool_id
            ))) is None
            if via_update:
                terminal_event = _native_task_updated(
                    agent_id, f"{agent_id}-terminal", status=status
                )
            else:
                terminal_event = _native_task_notification(
                    agent_id,
                    f"{agent_id}-terminal",
                    status=status,
                    tool_use_id=tool_id,
                )
            assert case.observe(_event_to_mapping(terminal_event)) is None
            terminal_child = next(
                row for row in case.snapshot()["children"] if row["agent_id"] == agent_id
            )
            expected_status = "completed" if status == "completed" else "restart-pending"
            assert terminal_child["status"] == expected_status
            assert terminal_child["task_terminal"] is True
            assert case.ready_for_hold is True
            assert case.quiescent is True

        for status in ("completed", "failed", "stopped"):
            await terminal_task_case(status, via_update=False)
        for status in ("completed", "failed", "killed"):
            await terminal_task_case(status, via_update=True)

    asyncio.run(scenario())


def test_native_reused_agent_id_ignores_late_uncorrelated_stop_and_notification(tmp_path):
    """A reused ID with no prompt/task join stays unresolved, not completed."""

    async def scenario():
        lineage_context = _native_lineage_context()

        async def persist_admission(record):
            return _native_admission_ack(record)

        ledger = NativeLineageLedger(
            SESSION_ID,
            trusted_definitions={"writer": _native_definition()},
            lineage_context=lineage_context,
            lineage_claim=_native_claim(tmp_path),
            persist_admission=persist_admission,
        )
        _begin_native(ledger, "parent-invocation-3-old")
        hooks, _evidence, _hook_error = _native_hooks(ledger)
        context = {"signal": None}
        old_pre = _native_agent_pre("agent-tool-old")
        assert await hooks["PreToolUse"][0].hooks[0](
            old_pre, "agent-tool-old", context
        ) == {}
        assert await hooks["SubagentStart"][0].hooks[0](
            _native_start("agent-reused"), None, context
        ) == {}
        assert ledger.observe(_event_to_mapping(_native_task_started(
            "agent-reused", "task-old-start", tool_use_id="agent-tool-old"
        ))) is None
        assert ledger.observe(_event_to_mapping(_native_task_updated(
            "agent-reused", "task-old-update", status="completed"
        ))) is None
        assert await hooks["PostToolUse"][0].hooks[0](
            _native_agent_post(old_pre), "agent-tool-old", context
        ) == {}
        assert await hooks["SubagentStop"][0].hooks[0](
            _native_stop("agent-reused", transcript="/tmp/agent-reused.jsonl"),
            None,
            context,
        ) == {}

        # A new parent invocation and task reuse the same native agent ID and
        # child transcript.  The optional prompt_id is absent in this fixture.
        assert ledger.begin_invocation("parent-invocation-3-current") is None
        current_pre = _native_agent_pre("agent-tool-current")
        assert await hooks["PreToolUse"][0].hooks[0](
            current_pre, "agent-tool-current", context
        ) == {}
        assert await hooks["SubagentStart"][0].hooks[0](
            _native_start("agent-reused"), None, context
        ) == {}
        assert ledger.observe(_event_to_mapping(_native_task_started(
            "agent-reused", "task-current-start", tool_use_id="agent-tool-current"
        ))) is None
        assert ledger.quiescent is False

        # This late stop and notification have the old task/incarnation but
        # arrive later.  Arrival watermark alone cannot terminate the current.
        stale_stop = _native_stop(
            "agent-reused", transcript="/tmp/agent-reused.jsonl"
        )
        assert await hooks["SubagentStop"][0].hooks[0](
            stale_stop, None, context
        ) == {}
        assert ledger.observe(_event_to_mapping(_native_task_notification(
            "agent-reused", "task-old-late-notification", status="completed"
        ))) is None
        current = next(
            row
            for row in ledger.snapshot()["children"]
            if row["agent_id"] == "agent-reused"
        )
        assert current["tool_use_id"] == "agent-tool-current"
        assert current["task_id"] == "agent-reused"
        assert current["status"] == "unresolved"
        assert ledger.snapshot()["uncertainty"]
        assert ledger.quiescent is False

        async def prepare_reused_case(current_prompt=None):
            case = NativeLineageLedger(
                SESSION_ID,
                trusted_definitions={"writer": _native_definition()},
                lineage_context=_native_lineage_context(),
                lineage_claim=_native_claim(tmp_path),
                persist_admission=persist_admission,
            )
            _begin_native(case, "case-old-invocation")
            case_hooks, _case_evidence, _case_hook_error = _native_hooks(case)
            old_case_pre = _native_agent_pre("case-tool-old")
            assert await case_hooks["PreToolUse"][0].hooks[0](
                old_case_pre, "case-tool-old", context
            ) == {}
            assert await case_hooks["SubagentStart"][0].hooks[0](
                _native_start("case-reused"), None, context
            ) == {}
            assert case.observe(_event_to_mapping(_native_task_started(
                "case-reused", "case-old-start", tool_use_id="case-tool-old"
            ))) is None
            assert case.observe(_event_to_mapping(_native_task_updated(
                "case-reused", "case-old-update", status="completed"
            ))) is None
            assert await case_hooks["PostToolUse"][0].hooks[0](
                _native_agent_post(old_case_pre), "case-tool-old", context
            ) == {}
            assert await case_hooks["SubagentStop"][0].hooks[0](
                _native_stop("case-reused", transcript="/tmp/case-reused.jsonl"),
                None,
                context,
            ) == {}
            assert case.begin_invocation("case-current-invocation") is None
            current_case_pre = _native_agent_pre(
                "case-tool-current", prompt_id=current_prompt
            )
            assert await case_hooks["PreToolUse"][0].hooks[0](
                current_case_pre, "case-tool-current", context
            ) == {}
            assert await case_hooks["SubagentStart"][0].hooks[0](
                _native_start("case-reused"), None, context
            ) == {}
            assert case.observe(_event_to_mapping(_native_task_started(
                "case-reused", "case-current-start", tool_use_id="case-tool-current"
            ))) is None
            return case, case_hooks

        matched_case, matched_hooks = await prepare_reused_case("prompt-current")
        assert await matched_hooks["SubagentStop"][0].hooks[0](
            _native_stop(
                "case-reused",
                transcript="/tmp/case-reused.jsonl",
                prompt_id="prompt-current",
            ),
            None,
            context,
        ) == {}
        assert matched_case.observe(_event_to_mapping(_native_task_notification(
            "case-reused",
            "case-current-completed",
            status="completed",
            tool_use_id="case-tool-current",
            prompt_id="prompt-current",
        ))) is None
        matched_child = next(
            row
            for row in matched_case.snapshot()["children"]
            if row["agent_id"] == "case-reused"
        )
        assert matched_child["status"] == "completed"
        assert matched_child["task_terminal"] is True
        assert matched_child["transcript"]["child_path"] == "/tmp/case-reused.jsonl"
        assert matched_case.snapshot()["uncertainty"] == []
        assert matched_case.ready_for_hold is True

        missing_prompt_case, missing_prompt_hooks = await prepare_reused_case(None)
        assert await missing_prompt_hooks["SubagentStop"][0].hooks[0](
            _native_stop(
                "case-reused",
                transcript="/tmp/case-reused.jsonl",
                prompt_id="unexpected-prompt",
            ),
            None,
            context,
        ) == {}
        missing_prompt_child = next(
            row
            for row in missing_prompt_case.snapshot()["children"]
            if row["agent_id"] == "case-reused"
        )
        assert missing_prompt_child["status"] == "unresolved"
        assert missing_prompt_case.snapshot()["uncertainty"]
        assert missing_prompt_case.ready_for_hold is False

        mismatched_case, mismatched_hooks = await prepare_reused_case("prompt-current")
        assert await mismatched_hooks["SubagentStop"][0].hooks[0](
            _native_stop(
                "case-reused",
                transcript="/tmp/case-reused.jsonl",
                prompt_id="prompt-stale",
            ),
            None,
            context,
        ) == {}
        mismatched_child = next(
            row
            for row in mismatched_case.snapshot()["children"]
            if row["agent_id"] == "case-reused"
        )
        assert mismatched_child["status"] == "unresolved"
        assert mismatched_case.snapshot()["uncertainty"]
        assert mismatched_case.ready_for_hold is False

    asyncio.run(scenario())


def test_native_missing_or_ambiguous_child_join_refuses_and_stays_unknown(tmp_path):
    """Unknown child identity never inherits a writable native policy."""

    async def scenario():
        lineage_context = _native_lineage_context()

        async def persist_admission(record):
            return _native_admission_ack(record)

        context = {"signal": None}
        unknown = NativeLineageLedger(
            SESSION_ID,
            trusted_definitions={"writer": _native_definition()},
            parent_read_only=True,
            lineage_context=lineage_context,
            lineage_claim=_native_claim(tmp_path),
            persist_admission=persist_admission,
        )
        _begin_native(unknown, "parent-invocation-4")
        hooks, _evidence, _hook_error = _native_hooks(unknown)
        denied = await hooks["PreToolUse"][0].hooks[0](
            _native_agent_pre("agent-tool-unknown", agent_type="not-authorized"),
            "agent-tool-unknown",
            context,
        )
        assert denied["continue_"] is False
        assert denied["decision"] == "block"
        assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert unknown.snapshot()["children"] == []

        orphan = NativeLineageLedger(
            SESSION_ID,
            trusted_definitions={"writer": _native_definition()},
            lineage_context=lineage_context,
            lineage_claim=_native_claim(tmp_path),
            persist_admission=persist_admission,
        )
        _begin_native(orphan, "parent-invocation-5")
        orphan_hooks, _evidence, orphan_hook_error = _native_hooks(orphan)
        assert await orphan_hooks["SubagentStart"][0].hooks[0](
            _native_start("agent-orphan"), None, context
        ) == {}
        assert orphan_hook_error["error"].code in {"ownership-conflict", "uncertain-effect"}
        assert orphan.snapshot()["children"] == []
        assert orphan.snapshot()["uncertainty"]
        assert orphan.quiescent is False

        ambiguous = NativeLineageLedger(
            SESSION_ID,
            trusted_definitions={"writer": _native_definition()},
            lineage_context=lineage_context,
            lineage_claim=_native_claim(tmp_path),
            persist_admission=persist_admission,
        )
        _begin_native(ambiguous, "parent-invocation-6")
        ambiguous_hooks, _evidence, ambiguous_hook_error = _native_hooks(ambiguous)
        for tool_use_id in ("agent-tool-a", "agent-tool-b"):
            assert await ambiguous_hooks["PreToolUse"][0].hooks[0](
                _native_agent_pre(tool_use_id), tool_use_id, context
            ) == {}
        assert await ambiguous_hooks["SubagentStart"][0].hooks[0](
            _native_start("agent-ambiguous"), None, context
        ) == {}
        assert ambiguous_hook_error["error"].code in {"ownership-conflict", "uncertain-effect"}
        assert ambiguous.snapshot()["children"] == []
        assert ambiguous.snapshot()["uncertainty"]
        assert ambiguous.quiescent is False

    asyncio.run(scenario())


def test_native_trusted_definition_digest_does_not_collide_after_redaction(tmp_path):
    """Full trusted definitions hash distinctly while snapshots stay sanitized."""

    def long_definition(marker: str):
        long_body = ("body-prefix-" + ("x" * 700) + marker)
        return {
            "description": "same bounded description",
            "prompt": long_body,
            "tools": ["Read"] * 65,
            "model": MODEL,
            "permissionMode": "default",
        }

    def make_ledger(definition, persisted):
        async def persist_admission(record):
            persisted.append(dict(record))
            return _native_admission_ack(record)

        ledger = NativeLineageLedger(
            SESSION_ID,
            trusted_definitions={"writer": definition},
            lineage_context=_native_lineage_context(),
            lineage_claim=_native_claim(tmp_path),
            persist_admission=persist_admission,
        )
        _begin_native(ledger, "digest-invocation")
        return ledger

    persisted_a = []
    persisted_b = []
    oversized = long_definition("INVALID_TOOL_BODY")
    oversized["tools"].append("Read-" + "x" * 300)
    with pytest.raises(SdkAdapterError, match="bounded tools"):
        make_ledger(oversized, [])
    ledger_a = make_ledger(long_definition("BODY_A_SHOULD_NOT_PERSIST"), persisted_a)
    ledger_b = make_ledger(long_definition("BODY_B_SHOULD_NOT_PERSIST"), persisted_b)

    async def scenario():
        hooks_a, _evidence, _hook_error = _native_hooks(ledger_a)
        hooks_b, _evidence, _hook_error = _native_hooks(ledger_b)
        context = {"signal": None}
        assert await hooks_a["PreToolUse"][0].hooks[0](
            _native_agent_pre("digest-tool-a"), "digest-tool-a", context
        ) == {}
        assert await hooks_b["PreToolUse"][0].hooks[0](
            _native_agent_pre("digest-tool-b"), "digest-tool-b", context
        ) == {}

    asyncio.run(scenario())
    snapshot_a = ledger_a.snapshot()
    snapshot_b = ledger_b.snapshot()
    definition_a = snapshot_a["pending_admissions"][0]["custom_definition"]
    definition_b = snapshot_b["pending_admissions"][0]["custom_definition"]
    digest_a = definition_a["digest"]
    digest_b = definition_b["digest"]
    assert digest_a != digest_b
    assert persisted_a and persisted_b
    assert persisted_a[0]["trusted_definition_digest"] == digest_a
    assert persisted_b[0]["trusted_definition_digest"] == digest_b
    assert "prompt" not in definition_a
    assert "prompt" not in definition_b
    assert "description" not in definition_a
    assert "description" not in definition_b
    serialized = json.dumps((snapshot_a, snapshot_b, persisted_a, persisted_b))
    assert "BODY_A_SHOULD_NOT_PERSIST" not in serialized
    assert "BODY_B_SHOULD_NOT_PERSIST" not in serialized
    assert len(serialized) < 100_000


def test_official_result_message_dataclass_normalizes_terminal_lifecycle(tmp_path):
    """ResultMessage has no wire ``type`` after ``dataclasses.asdict``."""

    @dataclass
    class ResultMessage:
        # These fields mirror the official 0.2.153 ResultMessage shape.  In
        # particular, ``type`` is deliberately not a dataclass field.
        subtype: str
        duration_ms: int
        duration_api_ms: int
        is_error: bool
        num_turns: int
        session_id: str
        stop_reason: str | None = None
        total_cost_usd: float | None = None
        usage: dict | None = None
        result: str | None = None
        structured_output: object = None
        model_usage: dict | None = None
        permission_denials: list[object] | None = None
        deferred_tool_use: object = None
        errors: list[str] | None = None
        api_error_status: int | None = None
        uuid: str | None = None
        terminal_reason: str | None = None
        origin: dict | None = None

    class IdleProcess:
        pid = None
        stdout = None
        stdin = None
        stderr = None

        @staticmethod
        def poll():
            return None

    connection = _RunnerConnection(
        "coordinator",
        _runner_spec(tmp_path),
        IdleProcess(),
        "runner-instance-1",
        strict_process_group=False,
    )
    identity = {
        "participant_id": "coordinator",
        "session_id": SESSION_ID,
        "runner_instance_id": "runner-instance-1",
    }
    result = ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id=SESSION_ID,
        stop_reason="end_turn",
    )

    assert "type" not in dataclasses.asdict(result)
    mapped = _event_to_mapping(result)
    assert mapped["type"] == "result"
    assert mapped["subtype"] == "success"

    connection._observe_event({**identity, "type": "query-dispatched"})
    connection._observe_event({**identity, **mapped})
    evidence = connection.evidence()
    assert evidence["active_turn"] is False
    assert evidence["turn_terminal"] is True
    assert evidence["drained"] is True
    assert evidence["participant_quiescent"] is True
    assert evidence["tools_quiescent"] is True
    assert evidence["quiescent"] is True


@pytest.mark.parametrize("role", ["coordinator", "worker"])
@pytest.mark.parametrize("tools", [("Write", "Edit", "Bash"), None])
def test_claimless_dontask_spec_requires_explicit_read_only_tools(tmp_path, role, tools):
    """dontAsk alone is not evidence that a claimless runner is safe."""
    spec = _runner_spec(
        tmp_path,
        role=role,
        parent_id="coordinator" if role == "worker" else None,
        task_id="task-read-only" if role == "worker" else None,
        read_only=True,
        permission_mode="dontAsk",
        tools=tools,
        allowed_tools=(),
        strict_mcp_config=True,
    )

    with pytest.raises(SdkAdapterError, match="read.?only|tool|constraint|permission"):
        build_sdk_options(spec)


def test_explicit_read_only_tools_and_strict_mcp_deny_write_execute_and_unknown(
    tmp_path, monkeypatch
):
    """Only an explicit built-in read-only set is admitted by PreToolUse."""

    async def scenario():
        monkeypatch.delenv("LANE_MANAGED_SDK_RUNNER", raising=False)
        safe_tools = ("Read", "Glob", "Grep")
        spec = _runner_spec(
            tmp_path,
            role="coordinator",
            read_only=True,
            permission_mode="dontAsk",
            tools=safe_tools,
            allowed_tools=(),
            strict_mcp_config=True,
            fingerprint={
                "model": MODEL,
                "permission_mode": "dontAsk",
                "worktree": str(tmp_path),
            },
        )
        info = _init_event(permission_mode="dontAsk")
        client = CachedInfoClient(info)
        controls: asyncio.Queue = asyncio.Queue()
        emitted = []
        task = asyncio.create_task(
            drive_client(
                spec,
                controls=controls,
                emit=emitted.append,
                sdk_module=_cached_sdk(client),
            )
        )
        try:
            await asyncio.wait_for(client.connected.wait(), timeout=1)
            await _wait_until(
                lambda: any(
                    isinstance(event, Mapping) and event.get("type") == "ready-held"
                    for event in emitted
                )
            )

            options = client.options
            assert list(_option_value(options, "tools")) == list(safe_tools)
            assert list(_option_value(options, "allowed_tools")) == list(safe_tools)
            assert _option_value(options, "strict_mcp_config") is True
            pre = options.hooks["PreToolUse"][0].hooks[0]
            post = options.hooks["PostToolUse"][0].hooks[0]
            safe_id = "tool-read-only-read"
            assert await pre(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Read",
                    "tool_input": {"file_path": "/tmp/read-only-input"},
                    "tool_use_id": safe_id,
                },
                safe_id,
                {"signal": None},
            ) == {}
            assert await post(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Read",
                    "tool_input": {"file_path": "/tmp/read-only-input"},
                    "tool_use_id": safe_id,
                },
                safe_id,
                {"signal": None},
            ) == {}
            attempted = {
                "Write": {"file_path": "/tmp/should-not-write"},
                "Edit": {
                    "file_path": "/tmp/should-not-edit",
                    "old_string": "a",
                    "new_string": "b",
                },
                "Bash": {"command": "printf should-not-execute"},
                "mcp__unknown__write": {"value": "should-not-call"},
            }
            for tool_name, tool_input in attempted.items():
                response = await pre(
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "tool_use_id": "tool-read-only-" + tool_name,
                    },
                    "tool-read-only-" + tool_name,
                    {"signal": None},
                )
                assert response["continue_"] is False
                assert response["decision"] == "block"
                assert response["hookSpecificOutput"]["permissionDecision"] == "deny"

            await controls.put({"operation": "shutdown"})
            result = await asyncio.wait_for(task, timeout=1)
            assert result["ready"] is True
            assert result["released"] is False
        finally:
            await _cancel_and_await(task)

    asyncio.run(scenario())


def test_idle_unsolicited_output_over_queue_bound_does_not_block_interrupt(tmp_path):
    """A noisy idle stream cannot prevent a correlated interrupt receipt."""

    class IdleBurstBridge:
        def __init__(self):
            self.writes = []
            self.noise_count = 0
            self.ack_sent = False
            self.hold = asyncio.Event()

        async def write(self, frame):
            self.writes.append(dict(frame))

        async def read(self):
            while not self.writes:
                await asyncio.sleep(0)
            request_id = self.writes[-1]["request_id"]
            identity = {
                "participant_id": "coordinator",
                "session_id": SESSION_ID,
                "runner_instance_id": "runner-instance-1",
            }
            if self.noise_count <= 256:
                self.noise_count += 1
                return {
                    **identity,
                    "type": "idle-diagnostic",
                    "detail": {"sequence": self.noise_count},
                }
            if not self.ack_sent:
                self.ack_sent = True
                return {
                    **identity,
                    "type": "interrupt-ack",
                    "request_id": request_id,
                    "interrupt_receipt": True,
                    "turn_terminal": True,
                    "drained": True,
                    "participant_quiescent": True,
                    "tools_quiescent": True,
                    "quiescent": True,
                }
            await self.hold.wait()

    class IdleProcess:
        pid = None
        stdout = None
        stdin = None
        stderr = None

        @staticmethod
        def poll():
            return None

    async def scenario():
        bridge = IdleBurstBridge()
        connection = _RunnerConnection(
            "coordinator",
            _runner_spec(tmp_path, operation_deadline=0.1),
            IdleProcess(),
            "runner-instance-1",
            strict_process_group=False,
        )
        connection.bridge = bridge
        connection.start_reader()
        try:
            receipt = await asyncio.wait_for(connection.interrupt(), timeout=0.5)
            assert receipt["interrupt_receipt"] is True
            assert bridge.noise_count > connection.events.maxsize
            assert connection.events.qsize() <= connection.events.maxsize
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_runner_connection_continuously_drains_stderr(tmp_path):
    """A long stderr stream is consumed independently of stdout events."""

    class EmptyStream:
        def fileno(self):
            raise OSError("fake stdout has no descriptor")

        @staticmethod
        def readline(_size=-1):
            return b""

        @staticmethod
        def close():
            return None

    class IdleProcess:
        pid = None

        def __init__(self, stderr):
            self.stdout = EmptyStream()
            self.stdin = None
            self.stderr = stderr

        @staticmethod
        def poll():
            return None

    async def scenario():
        read_fd, write_fd = os.pipe()
        os.set_blocking(write_fd, False)
        stderr = os.fdopen(read_fd, "rb", buffering=0)
        connection = _RunnerConnection(
            "coordinator",
            _runner_spec(tmp_path),
            IdleProcess(stderr),
            "runner-instance-1",
            strict_process_group=False,
        )
        connection.start_reader()
        try:
            await _wait_until(lambda: connection.stderr_task is not None)
            payload = b"diagnostic line\n" * 16384
            offset = 0
            deadline = asyncio.get_running_loop().time() + 1
            while offset < len(payload):
                try:
                    offset += os.write(write_fd, payload[offset:])
                except BlockingIOError:
                    if asyncio.get_running_loop().time() >= deadline:
                        raise AssertionError("stderr pipe was not drained continuously")
                    await asyncio.sleep(0)
            os.close(write_fd)
            write_fd = -1
            await asyncio.wait_for(connection.stderr_task, timeout=1)
            os.set_blocking(read_fd, False)
            assert os.read(read_fd, 1) == b""
        finally:
            await connection.close()
            if write_fd != -1:
                os.close(write_fd)

    asyncio.run(scenario())


def test_send_deadline_covers_control_lock_acquisition(tmp_path):
    """An operation deadline starts before waiting for the control lock."""

    class Bridge:
        def __init__(self):
            self.writes = []

        async def write(self, frame):
            self.writes.append(dict(frame))

    class IdleProcess:
        pid = None
        stdout = None
        stdin = None
        stderr = None

        @staticmethod
        def poll():
            return None

    async def scenario():
        bridge = Bridge()
        connection = _RunnerConnection(
            "coordinator",
            _runner_spec(tmp_path, operation_deadline=0.02),
            IdleProcess(),
            "runner-instance-1",
            strict_process_group=False,
        )
        connection.bridge = bridge
        connection.released = True
        await connection._control_lock.acquire()
        try:
            request = asyncio.create_task(
                connection.send("message-lock-timeout", {"content": "held"})
            )
            with pytest.raises(SdkAdapterError, match="deadline"):
                await asyncio.wait_for(request, timeout=0.3)
        finally:
            connection._control_lock.release()
        assert bridge.writes == []

    asyncio.run(scenario())


def test_send_deadline_covers_blocked_pipe_write_without_lingering_writer(tmp_path):
    """A blocked outbound frame is cancelled within the operation deadline."""

    class BlockingBridge:
        def __init__(self):
            self.started = asyncio.Event()
            self.cancelled = asyncio.Event()
            self.allow = asyncio.Event()
            self.active_writes = 0

        async def write(self, _frame):
            self.active_writes += 1
            self.started.set()
            try:
                await self.allow.wait()
            except asyncio.CancelledError:
                self.cancelled.set()
                raise
            finally:
                self.active_writes -= 1

    class IdleProcess:
        pid = None
        stdout = None
        stdin = None
        stderr = None

        @staticmethod
        def poll():
            return None

    async def scenario():
        bridge = BlockingBridge()
        connection = _RunnerConnection(
            "coordinator",
            _runner_spec(tmp_path, operation_deadline=0.02),
            IdleProcess(),
            "runner-instance-1",
            strict_process_group=False,
        )
        connection.bridge = bridge
        task = asyncio.create_task(connection.status())
        await asyncio.wait_for(bridge.started.wait(), timeout=0.3)
        with pytest.raises(SdkAdapterError, match="deadline"):
            await asyncio.wait_for(task, timeout=0.3)
        assert bridge.cancelled.is_set()
        assert bridge.active_writes == 0

    asyncio.run(scenario())


def test_mature_completed_tool_history_stays_bounded_and_quiescent():
    """Long-held sessions cannot grow a status frame past the 1 MiB wire cap."""
    evidence = _ToolEvidence()
    pre = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "true"},
    }
    post = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "true"},
    }
    for index in range(20000):
        tool_id = "tool-%05d" % index
        evidence.observe({**pre, "tool_use_id": tool_id})
        evidence.observe({**post, "tool_use_id": tool_id})

    snapshot = evidence.snapshot()
    assert snapshot["quiescent"] is True
    assert len(json.dumps(snapshot).encode("utf-8")) < 1024 * 1024
    # Keep this a count assertion as well as a byte assertion: a future compact
    # representation must not merely hide an unbounded completed list in JSON.
    assert len(snapshot["completed"]) <= 4096


def test_mature_tool_history_preserves_every_unresolved_effect():
    """Trimming completed history may never discard active or uncertain work."""
    evidence = _ToolEvidence()
    active_id = "tool-active-unresolved"
    evidence.observe(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "long-running"},
            "tool_use_id": active_id,
        }
    )
    uncertain_id = "tool-uncertain"
    refusal = evidence.observe(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "missing-start"},
            "tool_use_id": uncertain_id,
        }
    )
    assert isinstance(refusal, SdkAdapterError)

    for index in range(20000):
        tool_id = "tool-complete-%05d" % index
        evidence.observe(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "true"},
                "tool_use_id": tool_id,
            }
        )
        evidence.observe(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "true"},
                "tool_use_id": tool_id,
            }
        )

    snapshot = evidence.snapshot()
    assert snapshot["quiescent"] is False
    assert [item["tool_use_id"] for item in snapshot["active"]] == [active_id]
    assert any(item.get("tool_use_id") == uncertain_id for item in snapshot["uncertain"])
    assert len(json.dumps(snapshot).encode("utf-8")) < 1024 * 1024


def test_mature_initialization_event_history_is_bounded(tmp_path):
    """A continuous SDK stream retains bounded evidence, not every raw event."""
    tracker = InitializationTracker(_runner_spec(tmp_path))
    tracker.observe(_init_event())
    for index in range(20000):
        tracker.observe(
            {
                "type": "assistant",
                "session_id": SESSION_ID,
                "message_id": "assistant-%05d" % index,
                "content": [{"type": "text", "text": "held"}],
            }
        )

    assert len(tracker.events) <= 4096
    assert tracker.snapshot()["events_seen"] <= 4096


@pytest.mark.parametrize(
    "tool_name, tool_input",
    [
        ("Agent", {}),
        ("Task", {}),
        ("team", {}),
        ("Bash", {"run_in_background": True}),
        ("Bash", {"detached": True}),
        ("Bash", {"command": "setsid sleep 10"}),
    ],
)
def test_sdk_pre_tool_hook_rejects_native_or_detached_tools_before_execution(
    tool_name, tool_input
):
    """Managed mode never executes native graph/background/detached tools."""

    async def scenario():
        evidence = _ToolEvidence()
        hook_error = {}
        hooks = _build_guard_hooks(
            SimpleNamespace(HookMatcher=FakeHookMatcher), evidence, hook_error
        )
        assert hooks is not None
        pre = hooks["PreToolUse"][0].hooks[0]
        executed = []
        value = {
            "session_id": SESSION_ID,
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_use_id": "tool-rejected",
        }

        response = await pre(value, "tool-rejected", {"signal": None})
        if response.get("hookSpecificOutput", {}).get("permissionDecision") == "allow":
            executed.append(tool_name)

        assert response["continue_"] is False
        assert response["decision"] == "block"
        assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert executed == []
        assert evidence.active == {}
        assert evidence.completed == []
        assert evidence.uncertain
        assert hook_error["error"].code in {"unsupported", "uncertain-effect"}

    asyncio.run(scenario())


def test_held_runner_outlives_operation_deadline_without_dispatching_query(tmp_path):
    """The operation deadline applies to controls, not a ready held lifetime."""

    async def scenario():
        spec = _runner_spec(tmp_path, operation_deadline=0.03)
        factory = FakeClientFactory(events=(_init_event(),))
        controls: asyncio.Queue = asyncio.Queue()
        emitted = []
        task = asyncio.create_task(
            drive_client(
                spec,
                controls=controls,
                client_factory=factory,
                emit=emitted.append,
            )
        )
        try:
            await _wait_until(lambda: bool(factory.clients))
            await asyncio.wait_for(factory.clients[0].connected.wait(), timeout=1)
            await _wait_until(lambda: bool(emitted))

            await asyncio.sleep(spec.operation_deadline * 4)
            assert not task.done()
            assert not [call for call in factory.clients[0].calls if call[0] == "query"]

            await controls.put({"operation": "status"})
            await _wait_until(
                lambda: any(
                    isinstance(event, Mapping) and event.get("type") == "status"
                    for event in emitted
                )
            )
            assert not task.done()

            await controls.put({"operation": "shutdown"})
            result = await asyncio.wait_for(task, timeout=1)
            assert result["ready"] is True
            assert result["released"] is False
        finally:
            await _cancel_and_await(task)

    asyncio.run(scenario())


def test_released_query_ack_must_match_the_single_correlated_message_id(tmp_path):
    """A wire acknowledgement with another message ID cannot satisfy send."""

    class WrongAckBridge:
        def __init__(self):
            self.frame = None
            self.sent = asyncio.Event()

        async def write(self, frame):
            self.frame = dict(frame)
            self.sent.set()

        async def read(self):
            await self.sent.wait()
            return {
                "type": "query-dispatched",
                "participant_id": "coordinator",
                "session_id": SESSION_ID,
                "runner_instance_id": "runner-instance-1",
                "request_id": self.frame["request_id"],
                "message_id": "wrong-message-id",
                "accepted": True,
                "ack_kind": "accepted-send",
            }

    class IdleProcess:
        pid = None
        stdout = None
        stdin = None
        stderr = None

        @staticmethod
        def poll():
            return None

    async def scenario():
        connection = _RunnerConnection(
            "coordinator",
            _runner_spec(tmp_path),
            IdleProcess(),
            "runner-instance-1",
            strict_process_group=False,
        )
        connection.bridge = WrongAckBridge()
        connection.ready = True
        connection.released = True
        connection.start_reader()
        try:
            with pytest.raises(SdkAdapterError, match="ack|correlat|message|identity"):
                await asyncio.wait_for(
                    connection.send(
                        MESSAGE_ID,
                        {"role": "user", "content": "one dispatch"},
                    ),
                    timeout=1,
                )
        finally:
            await connection.close()

    asyncio.run(scenario())


def test_start_frame_reader_leaves_pipelined_controls_for_the_control_reader():
    """A buffered startup wrapper must not consume controls after its frame."""
    read_fd, write_fd = os.pipe()
    reader = os.fdopen(read_fd, "rb")
    try:
        os.write(
            write_fd,
            b'{"spec":{"session_id":"'
            + SESSION_ID.encode("ascii")
            + b'"}}\n{"operation":"status"}\n{"operation":"shutdown"}\n',
        )
        os.close(write_fd)
        write_fd = -1

        first = _read_first_frame(reader, timeout=1)
        assert first["spec"]["session_id"] == SESSION_ID
        # Read through the raw descriptor, as the separately-created control
        # bridge does.  TextIO.readline() would have prefetched these bytes.
        remaining = os.read(read_fd, 4096)
        assert remaining == b'{"operation":"status"}\n{"operation":"shutdown"}\n'
    finally:
        reader.close()
        if write_fd != -1:
            os.close(write_fd)


def test_partial_nonempty_control_frame_at_eof_is_not_clean_shutdown():
    async def scenario():
        read_fd, write_fd = os.pipe()
        reader = os.fdopen(read_fd, "rb", buffering=0)
        try:
            os.write(write_fd, b'{"operation":"status"')
            os.close(write_fd)
            write_fd = -1
            bridge = _BoundedJsonLines(reader, SimpleNamespace(write=lambda _: None, flush=lambda: None))
            with pytest.raises(SdkAdapterError, match="malformed|truncated|frame|JSON"):
                await asyncio.wait_for(bridge.read(), timeout=1)
        finally:
            reader.close()
            if write_fd != -1:
                os.close(write_fd)

    asyncio.run(scenario())


@pytest.mark.skipif(os.name == "nt", reason="requires POSIX process-group and pipe semantics")
def test_dedicated_runner_scrubs_before_sdk_import_and_refuses_unverified_sdk(tmp_path):
    """A subprocess fake proves scrub ordering while production refuses it."""
    import_probe = tmp_path / "sdk-import-environment.json"
    client_probe = tmp_path / "sdk-client-construction"
    fake_sdk = tmp_path / "claude_agent_sdk.py"
    fake_sdk.write_text(
        """
import asyncio
import json
import os
from pathlib import Path

SESSION_ID = "11111111-1111-4111-8111-111111111111"
MODEL = "claude-sonnet-4-20250514"
ACCOUNT_EMAIL = "target@example.invalid"

# This executes at import time.  The adapter must scrub the process environment
# before this module is imported, not merely put a clean mapping in options.env.
Path(os.environ["SDK_IMPORT_PROBE"]).write_text(
    json.dumps(dict(os.environ)), encoding="utf-8"
)


class ClaudeAgentOptions:
    def __init__(self, **values):
        self.__dict__.update(values)


class HookMatcher:
    def __init__(self, matcher=None, hooks=None, timeout=None):
        self.matcher = matcher
        self.hooks = list(hooks or ())
        self.timeout = timeout


class ClaudeSDKClient:
    def __init__(self, options):
        Path(os.environ["SDK_CLIENT_PROBE"]).write_text("constructed", encoding="utf-8")
        self.options = options
        self.events = asyncio.Queue()
        self.events.put_nowait({
            "type": "assistant",
            "session_id": SESSION_ID,
            "content": [{"type": "text", "text": "continuous fake response"}],
            "model": MODEL,
        })

    async def connect(self, prompt=None):
        assert prompt is None

    async def get_server_info(self):
        return {
            "type": "system",
            "subtype": "init",
            "account": {"email": ACCOUNT_EMAIL},
            "current_permission_mode": "default",
            "session_state": "idle",
            "models": [{
                "value": MODEL,
                "resolvedModel": MODEL,
                "displayName": "Claude Sonnet",
            }],
        }

    async def receive_messages(self):
        while True:
            event = await self.events.get()
            if event is None:
                return
            yield event

    async def interrupt(self):
        return None

    async def disconnect(self):
        await self.events.put(None)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    spec = _runner_spec(
        tmp_path,
        config_dir=str(tmp_path / "selected-profile"),
        profile_name="selected-profile",
        session_name="worker-a",
    )
    base_env = {
        "PATH": os.environ.get("PATH", "/usr/bin"),
        "PYTHONPATH": str(tmp_path),
        "SDK_IMPORT_PROBE": str(import_probe),
        "SDK_CLIENT_PROBE": str(client_probe),
        "ANTHROPIC_API_KEY": "must-not-cross",
        "CLAUDE_PROFILE_NAME": "inherited-profile",
        "CLAUDE_SESSION_NAME": "inherited-session",
    }
    process = popen_runner(
        spec,
        base_env=base_env,
        module_path=Path(__file__).resolve().parents[1] / "lane_managed_sdk.py",
    )

    def read_event(timeout=2):
        assert process.stdout is not None
        ready, _writable, _exceptional = select.select([process.stdout], [], [], timeout)
        assert ready, "dedicated runner produced no event before the deadline"
        line = process.stdout.readline()
        assert line, "dedicated runner closed stdout before emitting an event"
        return json.loads(line)

    try:
        assert process.stdin is not None
        process.stdin.write(
            json.dumps(
                {
                    "operation": "start",
                    "request_id": "start-0001",
                    "participant_id": "coordinator",
                    "session_id": SESSION_ID,
                    "runner_instance_id": "runner-instance-1",
                    "spec": spec.to_dict(),
                }
            )
            + "\n"
        )
        process.stdin.flush()

        refusal = read_event()
        assert refusal["type"] == "adapter-error"
        assert refusal["code"] == "live-unverified"
        assert not client_probe.exists(), "production refusal happened after fake client construction"
        assert import_probe.is_file(), "SDK import probe was not reached"
        child_env = json.loads(import_probe.read_text(encoding="utf-8"))
        assert "ANTHROPIC_API_KEY" not in child_env
        assert child_env["CLAUDE_CONFIG_DIR"] == str(tmp_path / "selected-profile")
        assert child_env["CLAUDE_PROFILE_NAME"] == "selected-profile"
        assert child_env["CLAUDE_SESSION_NAME"] == "worker-a"
        process.stdin.close()
        process.stdin = None
        assert process.wait(timeout=2) == 2
    finally:
        if process.stdin is not None:
            process.stdin.close()
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        if process.poll() is None:
            process.kill()
            process.wait()
