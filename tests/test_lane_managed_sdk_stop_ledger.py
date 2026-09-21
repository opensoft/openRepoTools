"""Native stop-ledger regressions over the admitted SDK child lifecycle."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from lane_managed_sdk import NativeLineageLedger, SdkAdapterError
from test_lane_managed_sdk import (
    SESSION_ID,
    _begin_native,
    _event_to_mapping,
    _native_admission_ack,
    _native_agent_pre,
    _native_claim,
    _native_definition,
    _native_hooks,
    _native_lineage_context,
    _native_start,
    _native_task_notification,
    _native_task_progress,
    _native_task_started,
    _native_task_updated,
)


def _new_ledger(tmp_path: Path):
    """Create a released ledger whose children must be admitted through hooks."""

    async def persist_admission(record):
        return _native_admission_ack(record)

    ledger = NativeLineageLedger(
        SESSION_ID,
        trusted_definitions={"writer": _native_definition()},
        parent_read_only=True,
        lineage_context=_native_lineage_context(),
        lineage_claim=_native_claim(tmp_path),
        persist_admission=persist_admission,
    )
    _begin_native(ledger, "parent-invocation-stop-ledger")
    hooks, _evidence, hook_error = _native_hooks(ledger)
    assert hook_error == {}
    return ledger, hooks


async def _admit_child(
    ledger,
    hooks,
    *,
    tool_use_id: str,
    agent_id: str,
    task_id: str,
):
    """Admit one child and bind it to the task ID observed from task_started."""
    context = {"signal": None}
    pre = _native_agent_pre(tool_use_id)
    assert await hooks["PreToolUse"][0].hooks[0](
        pre, tool_use_id, context
    ) == {}
    assert await hooks["SubagentStart"][0].hooks[0](
        _native_start(agent_id), None, context
    ) == {}
    assert ledger.observe(_event_to_mapping(_native_task_started(
        task_id,
        f"{task_id}-started",
        tool_use_id=tool_use_id,
    ))) is None


def _prepare_stop(ledger, *, task_id: str, stop_id: str):
    intent = ledger.prepare_native_stop(
        {"task_id": task_id, "stop_id": stop_id},
        participant_id="participant-stop-ledger",
        runner_instance_id="runner-1",
    )
    ledger.mark_native_stop_intent_persisted(
        stop_id,
        {"recorded": True, "stop_id": stop_id},
    )
    return intent


def test_native_stop_requires_observed_task_id_and_never_uses_agent_id(tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-observed-task",
            agent_id="agent-observed-task",
            task_id="task-observed-task",
        )

        with pytest.raises(SdkAdapterError) as raised:
            ledger.prepare_native_stop(
                {"task_id": "agent-observed-task", "stop_id": "stop-wrong-task"},
                participant_id="participant-stop-ledger",
                runner_instance_id="runner-1",
            )

        assert raised.value.code == "ownership-conflict"
        child = ledger.snapshot()["children"][0]
        assert child["agent_id"] == "agent-observed-task"
        assert child["task_id"] == "task-observed-task"

    asyncio.run(scenario())


def test_two_admitted_children_can_stop_after_the_first_stop_fence(tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-existing-a",
            agent_id="agent-existing-a",
            task_id="task-existing-a",
        )
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-existing-b",
            agent_id="agent-existing-b",
            task_id="task-existing-b",
        )

        first = _prepare_stop(
            ledger, task_id="task-existing-a", stop_id="stop-existing-a"
        )
        second = _prepare_stop(
            ledger, task_id="task-existing-b", stop_id="stop-existing-b"
        )

        assert first["stop"]["task_id"] == "task-existing-a"
        assert second["stop"]["task_id"] == "task-existing-b"
        assert ledger.revalidate_native_stop("stop-existing-a", first) is True
        assert ledger.revalidate_native_stop("stop-existing-b", second) is True

    asyncio.run(scenario())


def test_stop_fence_refuses_new_admission_and_parent_invocation(tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-fence-existing",
            agent_id="agent-fence-existing",
            task_id="task-fence-existing",
        )
        _prepare_stop(
            ledger,
            task_id="task-fence-existing",
            stop_id="stop-fence-existing",
        )

        invocation_error = ledger.begin_invocation("parent-invocation-new")
        assert isinstance(invocation_error, SdkAdapterError)
        assert invocation_error.code == "busy"
        assert ledger.current_invocation == "parent-invocation-stop-ledger"

        response = await hooks["PreToolUse"][0].hooks[0](
            _native_agent_pre("tool-fence-new"),
            "tool-fence-new",
            {"signal": None},
        )
        assert response["continue_"] is False
        assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert ledger.snapshot()["pending_admissions"] == []

    asyncio.run(scenario())


def test_task_progress_after_persisted_stop_intent_keeps_identity_revalidatable(
        tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-progress-after-intent",
            agent_id="agent-progress-after-intent",
            task_id="task-progress-after-intent",
        )
        intent = _prepare_stop(
            ledger,
            task_id="task-progress-after-intent",
            stop_id="stop-progress-after-intent",
        )

        assert ledger.observe(_event_to_mapping(_native_task_progress(
            "task-progress-after-intent",
            "task-progress-after-intent-event",
            tool_use_id="tool-progress-after-intent",
        ))) is None
        assert ledger.revalidate_native_stop(
            "stop-progress-after-intent", intent
        ) is True

    asyncio.run(scenario())


def test_ledger_error_after_stop_intent_blocks_revalidation(tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-error-after-intent",
            agent_id="agent-error-after-intent",
            task_id="task-error-after-intent",
        )
        intent = _prepare_stop(
            ledger,
            task_id="task-error-after-intent",
            stop_id="stop-error-after-intent",
        )
        children_before = ledger.snapshot()["children"]

        # A genuinely new start crosses the fence. Repeating the original
        # hook through the event stream is a valid cross-source duplicate.
        error = ledger.observe(_native_start("agent-new-after-stop"))
        assert isinstance(error, SdkAdapterError)
        assert error.code == "uncertain-effect"
        assert error.message == "native child start crossed an unresolved stop fence"
        assert ledger.snapshot()["children"] == children_before
        assert ledger.revalidate_native_stop(
            "stop-error-after-intent", intent
        ) is False

    asyncio.run(scenario())


def test_exact_task_notification_stopped_produces_terminal_stop_evidence(tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-exact-stopped",
            agent_id="agent-exact-stopped",
            task_id="task-exact-stopped",
        )
        intent = _prepare_stop(
            ledger, task_id="task-exact-stopped", stop_id="stop-exact-stopped"
        )
        event = _event_to_mapping(_native_task_notification(
            "task-exact-stopped",
            "task-exact-stopped-event",
            status="stopped",
            tool_use_id="tool-exact-stopped",
        ))

        assert ledger.observe(event) is None
        terminal = ledger.native_stop_terminal_evidence(event)
        assert terminal is not None
        assert terminal["evidence"]["kind"] == "terminal"
        assert terminal["evidence"]["event_kind"] == "task_notification"
        assert terminal["evidence"]["task_id"] == intent["stop"]["task_id"]

    asyncio.run(scenario())


def test_task_updated_stopped_cannot_produce_terminal_stop_evidence(tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-updated-stopped",
            agent_id="agent-updated-stopped",
            task_id="task-updated-stopped",
        )
        _prepare_stop(
            ledger,
            task_id="task-updated-stopped",
            stop_id="stop-updated-stopped",
        )
        event = _event_to_mapping(_native_task_updated(
            "task-updated-stopped",
            "task-updated-stopped-event",
            status="stopped",
        ))

        assert ledger.observe(event) is None
        assert ledger.native_stop_terminal_evidence(event) is None
        assert ledger.native_stop_pending_terminal_evidence(
            "stop-updated-stopped"
        ) is None

    asyncio.run(scenario())


def test_terminal_status_alias_cannot_produce_terminal_stop_evidence(tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-terminal-alias",
            agent_id="agent-terminal-alias",
            task_id="task-terminal-alias",
        )
        _prepare_stop(
            ledger,
            task_id="task-terminal-alias",
            stop_id="stop-terminal-alias",
        )
        event = _event_to_mapping(_native_task_notification(
            "task-terminal-alias",
            "task-terminal-alias-event",
            status="terminated",
            tool_use_id="tool-terminal-alias",
        ))

        assert ledger.observe(event) is None
        child = ledger.snapshot()["children"][0]
        assert child["task_terminal"] is True
        assert ledger.native_stop_terminal_evidence(event) is None
        assert ledger.native_stop_pending_terminal_evidence(
            "stop-terminal-alias"
        ) is None

    asyncio.run(scenario())


def test_terminal_evidence_before_intent_ack_is_retained_until_persisted(tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-terminal-before-ack",
            agent_id="agent-terminal-before-ack",
            task_id="task-terminal-before-ack",
        )
        intent = ledger.prepare_native_stop(
            {"task_id": "task-terminal-before-ack", "stop_id": "stop-terminal-before-ack"},
            participant_id="participant-stop-ledger",
            runner_instance_id="runner-1",
        )
        event = _event_to_mapping(_native_task_notification(
            "task-terminal-before-ack",
            "task-terminal-before-ack-event",
            status="stopped",
            tool_use_id="tool-terminal-before-ack",
        ))

        assert ledger.observe(event) is None
        terminal_before_ack = ledger.native_stop_terminal_evidence(event)
        assert terminal_before_ack is not None
        assert ledger.native_stop_pending_terminal_evidence(
            "stop-terminal-before-ack"
        ) is None

        ledger.mark_native_stop_intent_persisted(
            "stop-terminal-before-ack",
            {"recorded": True, "stop_id": intent["stop"]["stop_id"]},
        )
        assert ledger.native_stop_pending_terminal_evidence(
            "stop-terminal-before-ack"
        ) == terminal_before_ack

    asyncio.run(scenario())


def test_runtime_stop_ack_does_not_prove_quiescence(tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-runtime-ack",
            agent_id="agent-runtime-ack",
            task_id="task-runtime-ack",
        )
        _prepare_stop(
            ledger,
            task_id="task-runtime-ack",
            stop_id="stop-runtime-ack",
        )
        ledger.mark_native_stop_attempted("stop-runtime-ack")

        runtime_ack = ledger.native_stop_runtime_evidence("stop-runtime-ack")
        assert runtime_ack["evidence"]["kind"] == "runtime-ack"
        assert runtime_ack["evidence"]["ack_kind"] == "accepted-stop"
        assert runtime_ack["evidence"]["accepted"] is True
        assert ledger.quiescent is False
        assert ledger.snapshot()["children"][0]["task_terminal"] is False

    asyncio.run(scenario())


def test_native_stop_attempt_cannot_be_replayed_in_process_for_same_task(tmp_path):
    async def scenario():
        ledger, hooks = _new_ledger(tmp_path)
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-inprocess-replay",
            agent_id="agent-inprocess-replay",
            task_id="task-inprocess-replay",
        )
        _prepare_stop(
            ledger,
            task_id="task-inprocess-replay",
            stop_id="stop-inprocess-replay",
        )
        ledger.mark_native_stop_attempted("stop-inprocess-replay")

        for stop_id in ("stop-inprocess-replay", "stop-inprocess-new-id"):
            with pytest.raises(SdkAdapterError) as raised:
                ledger.prepare_native_stop(
                    {"task_id": "task-inprocess-replay", "stop_id": stop_id},
                    participant_id="participant-stop-ledger",
                    runner_instance_id="runner-1",
                )
            assert raised.value.code == "busy"

        with pytest.raises(SdkAdapterError) as raised:
            ledger.mark_native_stop_attempted("stop-inprocess-replay")
        assert raised.value.code == "busy"

    asyncio.run(scenario())
