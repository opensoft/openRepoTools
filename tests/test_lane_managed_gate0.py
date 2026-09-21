# SPDX-License-Identifier: Apache-2.0
"""Bounded Gate 0 controls for the native managed-worker adapter.

The source excerpts and event traces in this module are extracted-logic
controls.  They deliberately cannot close Gate 0: only a separately approved
observation of the exact SDK-selected CLI/transport can do that.  In
particular, a fake ``connect(None)`` run proves the adapter's call boundary,
not live startup or orphan support.

Expected production surface (T004): the existing adapter boundary is
``RunnerSpec``/``drive_client`` plus ``NativeLineageLedger``.  The selected
runtime probe delegates its executable control arms to the isolated loopback
runner and still treats missing lifecycle events as unsupported.  The
selected-runtime record must
contain the exact SDK package/version/path, selected CLI path/version/full
SHA-256, mode, and no-auth/blocked-network observation.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import runpy
import shutil
from collections.abc import AsyncIterator, Mapping
from pathlib import Path

import pytest

from lane_managed_sdk import NativeLineageLedger, RunnerSpec, drive_client


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "managed-native"
GATE0_PROBE = runpy.run_path(
    str(Path(__file__).parent / "probes" / "managed_gate0.py")
)
PROBE_CASES = GATE0_PROBE["CASES"]
PROBE_CONTROL_CASES = GATE0_PROBE["CONTROL_CASES"]
SESSION_ID = "11111111-1111-4111-8111-111111111111"
MODEL = "claude-sonnet-4-20250514"
SELECTED_SDK_VERSION = "0.2.153"
SELECTED_CLI_VERSION = "2.1.273"
SELECTED_CLI_SHA256 = "6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1"


def _read_json(name: str) -> dict:
    with (FIXTURE_ROOT / name).open(encoding="utf-8") as stream:
        value = json.load(stream)
    assert isinstance(value, dict)
    return value


def _read_jsonl(name: str) -> list[dict]:
    events = []
    with (FIXTURE_ROOT / name).open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                assert isinstance(value, dict)
                events.append(value)
    return events


def _read_text(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


def _reference_manifest() -> dict:
    manifest = _read_json("runtime-manifest.json")
    selected = manifest["selected"]
    sdk = selected["sdk"]
    cli = selected["cli"]
    assert sdk == {
        "package": "claude-agent-sdk",
        "version": SELECTED_SDK_VERSION,
        "path": "site-packages/claude_agent_sdk",
    }
    assert cli["version"] == SELECTED_CLI_VERSION
    assert cli["path"] == "_bundled/claude"
    assert re.fullmatch(r"[0-9a-f]{64}", cli["sha256"])
    assert cli["sha256"] == SELECTED_CLI_SHA256
    assert selected["mode"] == "stream-json"
    assert selected["auth"] == "none"
    assert selected["network"] == "blocked"
    return manifest


def _observe_installed_identity_without_starting_it(manifest: Mapping[str, object]) -> dict[str, object]:
    """Return a read-only observation; never launch Claude or authenticate.

    A package spec and a ``which`` result cannot prove which CLI the SDK will
    select.  Consequently this helper is intentionally conservative and
    returns OPEN even when a local system installation happens to exist.
    """

    sdk_spec = importlib.util.find_spec("claude_agent_sdk")
    cli_path = shutil.which("claude")
    observed: dict[str, object] = {
        "sdk_path": None if sdk_spec is None else sdk_spec.origin,
        "sdk_version": None,
        "cli_path": cli_path,
        "cli_digest": None,
        "startup_observed": False,
        "status": "OPEN",
        "capability": "UNVERIFIED",
        "support_claim": False,
        "reason": "actual selected SDK/CLI startup was not exercised by the no-auth harness",
        "refusal": "selected bundled CLI startup/model-attempt observation is intentionally not run",
    }
    if cli_path:
        try:
            observed["cli_digest"] = hashlib.sha256(Path(cli_path).read_bytes()).hexdigest()
        except (OSError, ValueError):
            observed["cli_digest"] = None
    # Keep the reference available to callers while refusing to infer a match
    # from a system binary, an extracted source line, or a fake client.
    observed["selected_reference"] = {
        "sdk_version": manifest["selected"]["sdk"]["version"],
        "cli_version": manifest["selected"]["cli"]["version"],
        "cli_sha256": manifest["selected"]["cli"]["sha256"],
    }
    return observed


def test_selected_runtime_manifest_is_exact_but_gate_remains_open():
    manifest = _reference_manifest()

    observation = _observe_installed_identity_without_starting_it(manifest)

    assert observation["status"] == "OPEN"
    assert observation["capability"] == "UNVERIFIED"
    assert observation["support_claim"] is False
    assert observation["startup_observed"] is False
    assert observation["selected_reference"]["sdk_version"] == SELECTED_SDK_VERSION
    assert observation["selected_reference"]["cli_version"] == SELECTED_CLI_VERSION
    assert observation["selected_reference"]["cli_sha256"] == SELECTED_CLI_SHA256


@pytest.mark.parametrize(
    ("case", "control"),
    (("positive-orphan", "positive_orphan"),
     ("terminal-cleared", "terminal_cleared")),
)
def test_selected_runtime_control_cases_have_executable_loopback_dispatch(
    case: str, control: str,
):
    assert case in PROBE_CASES
    assert PROBE_CONTROL_CASES[case] == control


@pytest.mark.parametrize("case", ("positive_orphan", "terminal_cleared"))
def test_actual_selected_cli_gate0_cases_remain_unverified(case: str):
    """Keep actual positive/negative runtime cases distinct and non-gating."""

    manifest = _reference_manifest()
    actual = manifest["actual_observation"][case]
    observation = _observe_installed_identity_without_starting_it(manifest)

    assert observation["status"] == "OPEN"
    assert observation["capability"] == "UNVERIFIED"
    assert observation["startup_observed"] is False
    assert actual["status"] == "UNVERIFIED"
    assert actual["refusal"]
    assert observation["support_claim"] is False


def test_positive_orphan_extracted_control_keeps_enqueue_wake_and_model_distinct():
    source = _read_text("positive-orphan-source.js")
    events = _read_jsonl("positive-orphan-events.jsonl")

    # These are the exact source-level controls from the feasibility artifact;
    # no assertion here is allowed to become a live support claim.
    for marker in (
        "oq(",
        "running_background_tasks",
        "restoredOrphans",
        "enqueuePendingNotification",
    ):
        assert marker in source
    assert [event["event"] for event in events] == [
        "persisted-record-load",
        "restored-orphans",
        "child-parent-wake",
        "enqueuePendingNotification",
        "model-query-attempt",
    ]
    assert events[1]["source"] == "running_background_tasks"
    assert events[1]["target"] == "restoredOrphans"
    assert events[2]["event"] != events[3]["event"]
    assert events[3]["event"] != events[4]["event"]
    assert events[4]["event"] == "model-query-attempt"

    # A synthetic/extracted orphan trace is useful as a control but cannot
    # close Gate 0 without actual selected-runtime startup evidence.
    manifest = _read_json("runtime-manifest.json")
    assert manifest["actual_observation"]["status"] == "OPEN"
    assert manifest["control_evidence"]["kind"] == "extracted-fixture-only"
    assert manifest["control_evidence"]["selected_runtime_control_runner"] == {
        "path": "tests/probes/managed_gate0.py",
        "positive_orphan_case": "positive-orphan",
        "terminal_cleared_case": "terminal-cleared",
        "delegated_runner": "tests/probes/managed_native_loopback.py",
        "public_fixture_boundary": "not-exposed",
        "lifecycle_event_surface": "selected-cli-stream-json-schema-unavailable",
        "terminal_cleared_negative_gate": "stop_task-source-request",
        "support_claim": False,
    }
    assert manifest["control_evidence"]["positive_orphan"]["status"] == (
        "not-exercised"
    )
    assert manifest["control_evidence"]["positive_orphan"][
        "model_query_attempt"
    ] == "not-exercised"


def test_terminal_cleared_stopped_by_user_control_has_no_resume_or_wake():
    source = _read_text("terminal-cleared-source.js")
    events = _read_jsonl("terminal-cleared-events.jsonl")

    assert "stoppedByUser" in source
    assert "won't be resumed" in source
    assert [event["event"] for event in events] == [
        "terminal-stop",
        "durable-worker-state-clear",
        "target-connect",
        "terminal-cleared",
    ]
    terminal = events[-1]
    assert terminal == {
        "event": "terminal-cleared",
        "stoppedByUser": True,
        "child_resume": False,
        "restored_orphans": 0,
        "wake": False,
        "enqueue": False,
        "model_query": False,
    }
    assert events[1]["cleared"] is True
    assert events[2]["inference_fenced"] is True
    manifest = _read_json("runtime-manifest.json")
    assert manifest["actual_observation"]["support_claim"] is False
    assert manifest["control_evidence"]["terminal_cleared"] == {
        "status": "not-exercised",
        "terminal_state_clear": "not-exercised",
        "target_connect": "not-exercised",
        "restored_orphans": "not-exercised",
        "notification_enqueue": "not-exercised",
        "model_query_attempt": "not-exercised",
        "support_claim": False,
    }


def test_stop_routes_do_not_use_one_api_for_background_and_foreground_children():
    fixture = _read_json("stop-routes.json")
    registry = fixture["registry"]
    start = fixture["subagent_start"]
    routes = fixture["routes"]

    # The current local_agent registry entry uses the same exact ID as the
    # native SubagentStart agent_id; stop_task therefore targets that ID.
    assert registry["task_type"] == "local_agent"
    assert registry["id"] == start["agent_id"]
    foreground = next(route for route in routes if route["kind"] == "local_agent_foreground")
    assert foreground["supported"] is True
    assert foreground["operation"] == "stop_task"
    assert foreground["task_id"] == registry["id"]

    background = next(route for route in routes if route["kind"] == "runtime_tracked_background_task")
    assert background["supported"] is True
    assert background["operation"] == "stop_task"
    assert background["task_id"]

    # Other task kinds have no supported stop API in this harness; do not
    # silently substitute interrupt or a process-wide stop operation.
    unsupported = [route for route in routes if not route["supported"]]
    assert unsupported
    assert all(route["operation"] == "unsupported" for route in unsupported)
    assert {route["kind"] for route in unsupported} == {"local_bash", "remote_agent"}


def _native_definition() -> dict[str, object]:
    return {
        "description": "fixture worker",
        "prompt": "read-only fixture operation",
        "tools": ["Read"],
        "model": MODEL,
        "permissionMode": "default",
    }


def _ledger() -> NativeLineageLedger:
    async def persist_admission(record):
        acknowledgement = dict(record)
        acknowledgement["accepted"] = True
        return acknowledgement

    ledger = NativeLineageLedger(
        SESSION_ID,
        trusted_definitions={"worker": _native_definition()},
        # The fixture is a native event trace, so give the ledger the
        # controller-owned lineage identity needed to reach its parent and
        # transcript correlation assertions.  This is an internal test seam,
        # never evidence from the event body.
        lineage_claim={
            "owner_generation": 1,
            "lineage_id": "fixture-lineage",
            "runner_incarnation": "fixture-runner",
        },
        persist_admission=persist_admission,
    )
    assert ledger.begin_invocation("fixture-invocation", "fixture-message") is None
    assert ledger.mark_released() is None
    return ledger


@pytest.mark.parametrize(
    "fixture_name",
    ("invalid-parent.json", "invalid-definition.json", "invalid-transcript.json"),
)
def test_invalid_parent_definition_and_transcript_fixtures_refuse(fixture_name: str):
    fixture = _read_json(fixture_name)

    for event in fixture["events"]:
        if event.get("type") == "SubagentStart":
            assert event["transcript_path"] == "fixture://coordinator"
            assert {"task_id", "tool_use_id", "parent_agent_id", "agent_transcript_path"}.isdisjoint(event)
        elif event.get("type") == "SubagentStop":
            assert event["transcript_path"] == "fixture://coordinator"
            assert event["agent_transcript_path"].startswith("fixture://child-")
            assert {"task_id", "tool_use_id", "parent_agent_id"}.isdisjoint(event)
        elif event.get("subtype") == "task_started":
            assert event["task_type"] == "local_agent"
            assert event["prompt_id"].startswith("prompt-")

    async def scenario():
        ledger = _ledger()
        error = None
        for event in fixture["events"]:
            if event.get("type") == "PreToolUse":
                error = await ledger.admit_agent(event)
            else:
                error = ledger.observe(event)
            if error is not None:
                break
        return ledger, error

    ledger, error = asyncio.run(scenario())
    if "expected_code" in fixture:
        assert error is not None, fixture["case"]
        assert error.code == fixture["expected_code"]
        assert ledger.snapshot()["error"]["code"] == fixture["expected_code"]
    else:
        assert error is None, fixture["case"]
        snapshot = ledger.snapshot()
        assert snapshot["quiescent"] is fixture["expected_quiescent"]
        assert snapshot["ready_for_hold"] is fixture["expected_ready_for_hold"]
        children = [
            row for row in snapshot["children"]
            if row["status"] == fixture["expected_status"]
        ]
        assert len(children) == 1
        assert children[0]["transcript"]["child_path"] == fixture["expected_child_path"]
        assert [
            uncertainty["reason"] for uncertainty in snapshot["uncertainty"]
        ] == [fixture["expected_reason"]]


class _FakeSdkCli:
    """A wire-shaped fake: connect emits initialize and nothing user-facing."""

    _STOP = object()

    def __init__(self, options):
        self.options = options
        self.frames: list[dict[str, object]] = []
        self.calls: list[str] = []
        self.events: asyncio.Queue[object] = asyncio.Queue()

    async def connect(self, prompt=None):
        self.calls.append("connect")
        assert prompt is None
        self.frames.append({"type": "initialize"})

    async def get_server_info(self):
        self.calls.append("get_server_info")
        return {
            "type": "system",
            "subtype": "init",
            "account": {"email": "fixture@example.invalid"},
            "current_permission_mode": "default",
            "session_state": "idle",
            "models": [MODEL],
        }

    async def receive_messages(self) -> AsyncIterator[object]:
        self.calls.append("receive_messages")
        while True:
            event = await self.events.get()
            if event is self._STOP:
                return
            yield event

    async def query(self, payload, message_id=None):
        self.calls.append("query")
        self.frames.append({"type": "user", "payload": payload, "message_id": message_id})

    async def disconnect(self):
        self.calls.append("disconnect")
        await self.events.put(self._STOP)


def _fake_runner_spec(tmp_path: Path) -> RunnerSpec:
    return RunnerSpec(
        session_id=SESSION_ID,
        mode="resume",
        resume=True,
        account_email="fixture@example.invalid",
        permission_mode="default",
        model=MODEL,
        supported_models=(MODEL,),
        worktree=str(tmp_path),
        fingerprint={
            "model": MODEL,
            "permission_mode": "default",
            "worktree": str(tmp_path),
        },
        environment={"PATH": os.environ.get("PATH", "")},
    )


def test_connect_none_fake_cli_sends_initialize_only_and_no_user_frame(tmp_path: Path):
    created: list[_FakeSdkCli] = []

    def factory(options):
        client = _FakeSdkCli(options)
        created.append(client)
        return client

    result = asyncio.run(
        drive_client(
            _fake_runner_spec(tmp_path),
            controls=iter(({"operation": "shutdown", "request_id": "shutdown-1"},)),
            client_factory=factory,
        )
    )

    assert result["ok"] is True
    assert result["released"] is False
    assert len(created) == 1
    client = created[0]
    assert client.calls[:2] == ["connect", "get_server_info"]
    assert "receive_messages" in client.calls
    assert "query" not in client.calls
    assert client.frames == [{"type": "initialize"}]
    # Fake evidence is intentionally not a live Gate 0 claim.
    assert result.get("live_verified") is not True
    assert result["evidence"].get("live_verified") is not True
