# SPDX-License-Identifier: Apache-2.0
"""Fake-only native coordinator startup and admission integration.

The fixtures use the production controller, daemon callback, and native
lineage ledger with bounded in-memory state.  They do not open an SDK client,
send a model request, or contact an account.  A startup preparation result is
configuration evidence only; the actual invocation mailbox ID is registered
at the first native invocation boundary.
"""

from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace

import pytest

from lane_managed_controller import ControllerError
from lane_managed_sdk import (
    NativeLineageLedger,
    _ToolEvidence,
    _build_guard_hooks,
    _event_to_mapping,
)
from test_lane_managed_daemon_admission_integration import (
    context_intent,
    native_fixture,
    trusted_definitions,
)
from test_lane_managed_sdk import (
    FakeHookMatcher,
    _native_agent_pre,
    _native_start,
    _native_task_started,
    _native_task_updated,
)


MAILBOX_MESSAGE = "mailbox-message-1"
SESSION = "11111111-1111-4111-8111-111111111111"


def _hooks(ledger: NativeLineageLedger):
    evidence = _ToolEvidence()
    errors: dict[str, object] = {}
    hooks = _build_guard_hooks(
        SimpleNamespace(HookMatcher=FakeHookMatcher),
        evidence,
        errors,
        lineage=ledger,
    )
    assert hooks is not None
    return hooks


def test_prepare_native_coordinator_preserves_trusted_identity_before_open(
    tmp_path,
):
    """Startup preparation is durable configuration, before invocation work."""

    daemon, store, _adapter, lineage = native_fixture(tmp_path)

    async def scenario():
        await daemon.start()
        prepare = getattr(daemon.controller, "prepare_native_coordinator")
        prepared = prepare(
            lineage.owner_generation,
            lineage,
            "runner-1",
            trusted_definitions(),
        )

        assert prepared["lineage"]["lineage_id"] == lineage.lineage_id
        assert prepared["lineage"]["session_uuid"] == SESSION
        assert prepared["runner_incarnation"] == "runner-1"
        assert prepared["definitions"]["writer"]["digest"]
        # Configuration preparation cannot itself create a mailbox invocation
        # or claim that a native child has joined.
        assert prepared.get("invocation_id") is None
        assert prepared.get("native_admissions", []) in ([], {})
        assert store.documents["controller.json"].get("native_context") is None

    asyncio.run(scenario())


def test_actual_mailbox_invocation_binds_context_before_hook_admission(
    tmp_path,
):
    """Only the registered mailbox ID can authorize a native Agent admission."""

    daemon, store, adapter, lineage = native_fixture(tmp_path)

    async def scenario():
        await daemon.start()
        controller = daemon.controller
        prepare = getattr(controller, "prepare_native_coordinator")
        prepared = prepare(
            lineage.owner_generation,
            lineage,
            "runner-1",
            trusted_definitions(),
        )

        # This is the same public controller registration used by the adapter
        # callback.  The invocation is the durable mailbox identity, rather
        # than a random transport request ID supplied by a test or client.
        context = controller.register_native_context(
            lineage.owner_generation,
            lineage,
            "runner-1",
            MAILBOX_MESSAGE,
            trusted_definitions(),
            invocation_watermark=1,
        )
        assert context["invocation_id"] == MAILBOX_MESSAGE
        assert context["definitions"] == prepared["definitions"]

        ledger = NativeLineageLedger(
            SESSION,
            trusted_definitions=trusted_definitions(),
            parent_read_only=True,
            lineage_context={
                "owner_generation": lineage.owner_generation,
                "lineage_id": lineage.lineage_id,
                "runner_incarnation": "runner-1",
            },
            lineage_claim=store.claims[0],
            persist_admission=adapter.callback,
        )
        assert ledger.begin_invocation(MAILBOX_MESSAGE) is None
        assert ledger.mark_released() is None
        hooks = _hooks(ledger)
        pre = _native_agent_pre("agent-tool-1")
        assert await hooks["PreToolUse"][0].hooks[0](
            pre, "agent-tool-1", {"signal": None}
        ) == {}

        # The real stream lifecycle joins the persisted admission to the
        # actual child and task.  The child owns no fabricated session/runner.
        assert ledger.observe(_event_to_mapping(_native_task_started(
            "agent-1", "task-event-1", tool_use_id="agent-tool-1"
        ))) is None
        assert await hooks["SubagentStart"][0].hooks[0](
            _native_start("agent-1"), None, {"signal": None}
        ) == {}
        assert ledger.observe(_event_to_mapping(_native_task_updated(
            "agent-1", "task-updated-1", status="completed"
        ))) is None

        snapshot = ledger.snapshot()
        assert snapshot["current_invocation"] == MAILBOX_MESSAGE
        assert snapshot["pending_admissions"] == []
        assert len(snapshot["children"]) == 1
        child = snapshot["children"][0]
        assert child["agent_id"] == "agent-1"
        assert child["task_id"] == "agent-1"
        assert "session_id" not in child
        assert "runner_instance_id" not in child
        assert len(store.documents["controller.json"]["native_admissions"]) == 1

        # A second ledger using only a random transport ID cannot pass the
        # controller's registered invocation check, even with the same hooks.
        random_ledger = NativeLineageLedger(
            SESSION,
            trusted_definitions=trusted_definitions(),
            parent_read_only=True,
            lineage_context={
                "owner_generation": lineage.owner_generation,
                "lineage_id": lineage.lineage_id,
                "runner_incarnation": "runner-1",
            },
            lineage_claim=store.claims[0],
            persist_admission=adapter.callback,
        )
        assert random_ledger.begin_invocation("random-transport-request") is None
        assert random_ledger.mark_released() is None
        random_hooks = _hooks(random_ledger)
        denied = await random_hooks["PreToolUse"][0].hooks[0](
            _native_agent_pre("agent-tool-random"),
            "agent-tool-random",
            {"signal": None},
        )
        assert denied["continue_"] is False
        assert denied["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert len(store.documents["controller.json"]["native_admissions"]) == 1

    asyncio.run(scenario())


def test_context_registration_retries_are_idempotent_but_changed_invocation_refuses(
    tmp_path,
):
    """The registration boundary cannot be replaced by a later invocation."""

    daemon, store, _adapter, lineage = native_fixture(tmp_path)

    async def scenario():
        await daemon.start()
        controller = daemon.controller
        kwargs = {
            "generation": lineage.owner_generation,
            "lineage": lineage,
            "runner_incarnation": "runner-1",
            "trusted_definitions": trusted_definitions(),
            "invocation_watermark": 1,
        }
        first = controller.register_native_context(
            invocation_id=MAILBOX_MESSAGE, **kwargs
        )
        writes = copy.deepcopy(store.documents["controller.json"])
        assert controller.register_native_context(
            invocation_id=MAILBOX_MESSAGE, **kwargs
        ) == first
        assert store.documents["controller.json"] == writes
        with pytest.raises(ControllerError) as caught:
            controller.register_native_context(
                invocation_id="different-mailbox-message", **kwargs
            )
        assert getattr(caught.value, "code", None) in {"busy", "stale-generation"}
        assert store.documents["controller.json"] == writes

    asyncio.run(scenario())
