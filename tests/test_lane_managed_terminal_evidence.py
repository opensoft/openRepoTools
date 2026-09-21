"""Current-incarnation precedence for native coordinator terminal evidence."""

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
    _native_definition,
    _native_hooks,
    _native_lineage_context,
    _native_start,
    _native_stop,
    _native_task_notification,
    _native_task_started,
)


def _new_ledger(tmp_path: Path, invocation_id: str):
    async def persist_admission(record):
        return _native_admission_ack(record)

    ledger = NativeLineageLedger(
        SESSION_ID,
        trusted_definitions={"writer": _native_definition(tools=("Read",))},
        parent_read_only=True,
        lineage_context=_native_lineage_context(),
        persist_admission=persist_admission,
    )
    _begin_native(ledger, invocation_id)
    hooks, tool_evidence, hook_error = _native_hooks(ledger)
    assert hook_error == {}
    return ledger, hooks, tool_evidence


async def _admit_child(
    ledger,
    hooks,
    *,
    tool_use_id: str,
    agent_id: str,
    task_id: str,
    prompt_id: str | None = None,
):
    context = {"signal": None}
    pre = _native_agent_pre(tool_use_id, prompt_id=prompt_id)
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
    assert await hooks["PostToolUse"][0].hooks[0](
        {**pre, "hook_event_name": "PostToolUse", "tool_response": {"status": "accepted"}},
        tool_use_id,
        context,
    ) == {}


def _prepare_interrupt(ledger, tool_evidence, interrupt_id: str):
    assert ledger.note_parent_state(
        active=True,
        drained=False,
        invocation_id=ledger.current_invocation,
    ) is None
    intent = ledger.prepare_coordinator_interrupt(
        {
            "operation_id": f"operation-{interrupt_id}",
            "interrupt_id": interrupt_id,
            "fence_epoch": 1,
            "capability_digest": "a" * 64,
            "request_epoch_id": f"request-{interrupt_id}",
        },
        participant_id="coordinator",
        runner_instance_id="runner-1",
        tool_evidence=tool_evidence,
        parent_state="active",
    )
    ledger.mark_coordinator_interrupt_intent_persisted(
        interrupt_id,
        {"recorded": True, "authorize_send": True, "interrupt_id": interrupt_id},
    )
    return intent


def _assert_reused_interrupt_prepare_refused(ledger, tool_evidence, interrupt_id: str):
    assert ledger.note_parent_state(
        active=True,
        drained=False,
        invocation_id=ledger.current_invocation,
    ) is None
    with pytest.raises(SdkAdapterError) as raised:
        ledger.prepare_coordinator_interrupt(
            {
                "operation_id": f"operation-{interrupt_id}",
                "interrupt_id": interrupt_id,
                "fence_epoch": 1,
                "capability_digest": "a" * 64,
                "request_epoch_id": f"request-{interrupt_id}",
            },
            participant_id="coordinator",
            runner_instance_id="runner-1",
            tool_evidence=tool_evidence,
            parent_state="active",
        )
    assert raised.value.code == "unsupported"
    assert str(raised.value) == "coordinator interrupt roster does not cover all admissions"


def _observe_and_record(ledger, event):
    assert ledger.observe(event) is None
    ledger.record_coordinator_observation(event)
    observed = ledger._coordinator_fact_events[-1]
    return ledger.coordinator_interrupt_event_evidence(observed)


def test_failed_task_notification_remains_failed_after_subagent_stop_hook(tmp_path):
    async def scenario():
        ledger, hooks, tool_evidence = _new_ledger(
            tmp_path, "invocation-failed-current"
        )
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-failed-current",
            agent_id="agent-failed-current",
            task_id="task-failed-current",
        )
        _prepare_interrupt(ledger, tool_evidence, "interrupt-failed-current")

        failed = _event_to_mapping(_native_task_notification(
            "task-failed-current",
            "task-failed-current-terminal",
            status="failed",
            tool_use_id="tool-failed-current",
        ))
        failure_frame = _observe_and_record(ledger, failed)
        assert failure_frame is not None
        failure = failure_frame["evidence"]
        assert failure["kind"] == "member-terminal"
        assert failure["data"]["status"] == "failed"
        assert failure["data"]["event_kind"] == "task_notification"
        assert failure["data"]["event_uuid"] == "task-failed-current-terminal"

        child = next(row for row in ledger.snapshot()["children"] if row["agent_id"] == "agent-failed-current")
        terminal_fact = next(
            fact for fact in child["task_events"]
            if fact["kind"] == "tasknotification"
        )
        assert failure["observed_watermark"] == terminal_fact["watermark"]

        stop = _native_stop(
            "agent-failed-current",
            transcript="/tmp/agent-failed-current.jsonl",
        )
        hook_frame = _observe_and_record(ledger, stop)
        assert hook_frame is not None
        assert hook_frame["evidence"] == failure
        assert hook_frame["evidence"]["data"]["status"] == "failed"
        assert hook_frame["evidence"]["data"]["event_kind"] == "task_notification"

        member_frames = [
            frame for frame in ledger.coordinator_interrupt_evidence_frames(
                "interrupt-failed-current", tool_evidence=tool_evidence
            )
            if frame["evidence"]["kind"] == "member-terminal"
        ]
        assert len(member_frames) == 1
        assert member_frames[0]["evidence"] == failure

    asyncio.run(scenario())


def test_completed_task_notification_stays_completed_without_stop_provenance(tmp_path):
    async def scenario():
        ledger, hooks, tool_evidence = _new_ledger(
            tmp_path, "invocation-completed-current"
        )
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-completed-current",
            agent_id="agent-completed-current",
            task_id="task-completed-current",
        )
        _prepare_interrupt(ledger, tool_evidence, "interrupt-completed-current")

        completed = _event_to_mapping(_native_task_notification(
            "task-completed-current",
            "task-completed-current-terminal",
            status="completed",
            tool_use_id="tool-completed-current",
        ))
        completion_frame = _observe_and_record(ledger, completed)
        assert completion_frame is not None
        completion = completion_frame["evidence"]
        assert completion["data"]["status"] == "completed"
        assert completion["data"]["event_kind"] == "task_notification"
        assert completion["data"]["event_uuid"] == "task-completed-current-terminal"

        stop = _native_stop(
            "agent-completed-current",
            transcript="/tmp/agent-completed-current.jsonl",
        )
        hook_frame = _observe_and_record(ledger, stop)
        assert hook_frame is not None
        assert hook_frame["evidence"] == completion
        assert hook_frame["evidence"]["data"]["status"] == "completed"
        assert hook_frame["evidence"]["data"]["event_kind"] == "task_notification"
        assert hook_frame["evidence"]["data"]["event_uuid"] == "task-completed-current-terminal"

        child = next(row for row in ledger.snapshot()["children"] if row["agent_id"] == "agent-completed-current")
        assert child["status"] == "completed"
        assert "source" not in child["stop_provenance"]
        assert child["task_events"][0]["kind"] == "taskstarted"
        assert child["task_events"][-1]["status"] == "completed"

    asyncio.run(scenario())


def test_subagent_stop_alone_reports_stopped_and_not_successful(tmp_path):
    async def scenario():
        ledger, hooks, tool_evidence = _new_ledger(
            tmp_path, "invocation-hook-only-current"
        )
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-hook-only-current",
            agent_id="agent-hook-only-current",
            task_id="task-hook-only-current",
        )
        _prepare_interrupt(ledger, tool_evidence, "interrupt-hook-only-current")

        stop = _native_stop(
            "agent-hook-only-current",
            transcript="/tmp/agent-hook-only-current.jsonl",
        )
        frame = _observe_and_record(ledger, stop)
        assert frame is not None
        data = frame["evidence"]["data"]
        assert data["status"] == "stopped"
        assert data["event_kind"] == "SubagentStop"
        assert data["event_uuid"] is None

    asyncio.run(scenario())


def test_first_incarnation_stop_hook_rejects_contradictory_correlations(tmp_path):
    async def scenario():
        ledger, hooks, _tool_evidence = _new_ledger(
            tmp_path, "invocation-correlation-current"
        )
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-correlation-current",
            agent_id="agent-correlation-current",
            task_id="task-correlation-current",
            prompt_id="prompt-correlation-current",
        )
        record = ledger.children["agent-correlation-current"]
        stop = _native_stop(
            "agent-correlation-current",
            transcript="/tmp/agent-correlation-current.jsonl",
        )
        assert ledger._coordinator_subagent_stop_matches_current_record(record, stop)
        for field, value in (
            ("tool_use_id", "tool-correlation-stale"),
            ("prompt_id", "prompt-correlation-stale"),
            ("invocation_id", "invocation-correlation-stale"),
        ):
            contradictory = {**stop, field: value}
            assert not ledger._coordinator_subagent_stop_matches_current_record(
                record, contradictory
            )

    asyncio.run(scenario())


def test_non_authoritative_task_notification_cannot_promote_terminal_fact(tmp_path):
    async def scenario():
        ledger, hooks, tool_evidence = _new_ledger(
            tmp_path, "invocation-non-authoritative-current"
        )
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-non-authoritative-current",
            agent_id="agent-non-authoritative-current",
            task_id="task-non-authoritative-current",
        )
        _prepare_interrupt(ledger, tool_evidence, "interrupt-non-authoritative-current")

        rejected = _event_to_mapping(_native_task_notification(
            "task-non-authoritative-current",
            "task-non-authoritative-terminal",
            status="failed",
            tool_use_id="tool-non-authoritative-current",
        ))
        rejected["authoritative"] = False
        assert ledger.observe(rejected) is not None
        child = ledger.children["agent-non-authoritative-current"]
        assert child["task_events"][-1]["authoritative"] is False
        assert child["task_events"][-1]["validated"] is False
        assert ledger._coordinator_current_terminal_task_fact(child) is None
        assert ledger.coordinator_interrupt_event_evidence(rejected) is None

    asyncio.run(scenario())


def test_stale_task_notification_cannot_close_reused_current_incarnation(tmp_path):
    async def scenario():
        ledger, hooks, tool_evidence = _new_ledger(
            tmp_path, "invocation-reused-old"
        )
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-reused-old",
            agent_id="agent-reused-current",
            task_id="task-reused-old",
        )
        old_terminal = _event_to_mapping(_native_task_notification(
            "task-reused-old",
            "task-reused-old-terminal",
            status="completed",
            tool_use_id="tool-reused-old",
        ))
        assert ledger.observe(old_terminal) is None
        assert await hooks["SubagentStop"][0].hooks[0](
            _native_stop(
                "agent-reused-current",
                transcript="/tmp/agent-reused-old.jsonl",
            ),
            None,
            {"signal": None},
        ) == {}

        assert ledger.begin_invocation("invocation-reused-current") is None
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-reused-current",
            agent_id="agent-reused-current",
            task_id="task-reused-current",
        )
        # The current SDK roster intentionally refuses this mixed historical /
        # current admission set until archival lineage coverage is implemented.
        _assert_reused_interrupt_prepare_refused(
            ledger, tool_evidence, "interrupt-reused-current"
        )

        stale = _event_to_mapping(_native_task_notification(
            "task-reused-old",
            "task-reused-old-late",
            status="completed",
            tool_use_id="tool-reused-old",
        ))
        stale["agent_id"] = "agent-reused-current"
        before_task_events = [
            dict(fact) for fact in ledger.children["agent-reused-current"]["task_events"]
        ]
        assert ledger.observe(stale) is None

        current = next(
            row for row in ledger.snapshot()["children"]
            if row["agent_id"] == "agent-reused-current"
        )
        assert current["task_id"] == "task-reused-current"
        assert current["status"] == "unresolved"
        assert current["uncertain"] is True
        assert current["task_terminal"] is False
        assert current["task_events"] == before_task_events
        assert ledger.snapshot()["error"]["code"] == "ownership-conflict"
        assert ledger.snapshot()["uncertainty"][-1]["reason"] == (
            "native task event lacks current child-run correlation"
        )
        assert ledger._coordinator_current_terminal_task_fact(ledger.children[
            "agent-reused-current"
        ]) is None

    asyncio.run(scenario())


def test_stale_reused_subagent_stop_hook_cannot_emit_terminal_evidence(tmp_path):
    async def scenario():
        ledger, hooks, tool_evidence = _new_ledger(
            tmp_path, "invocation-hook-reused-old"
        )
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-hook-reused-old",
            agent_id="agent-hook-reused",
            task_id="task-hook-reused-old",
        )
        assert ledger.observe(_event_to_mapping(_native_task_notification(
            "task-hook-reused-old",
            "task-hook-reused-old-terminal",
            status="completed",
            tool_use_id="tool-hook-reused-old",
        ))) is None
        assert await hooks["SubagentStop"][0].hooks[0](
            _native_stop("agent-hook-reused", transcript="/tmp/hook-reused.jsonl"),
            None,
            {"signal": None},
        ) == {}

        assert ledger.begin_invocation("invocation-hook-reused-current") is None
        await _admit_child(
            ledger,
            hooks,
            tool_use_id="tool-hook-reused-current",
            agent_id="agent-hook-reused",
            task_id="task-hook-reused-current",
        )
        # Do not claim an integrated reused-ID interrupt roster while the
        # durable historical admission is outside the current roster.
        _assert_reused_interrupt_prepare_refused(
            ledger, tool_evidence, "interrupt-hook-reused-current"
        )

        stale_hook = _native_stop(
            "agent-hook-reused",
            transcript="/tmp/hook-reused.jsonl",
        )
        assert await hooks["SubagentStop"][0].hooks[0](
            stale_hook, None, {"signal": None}
        ) == {}

        current = next(
            row for row in ledger.snapshot()["children"]
            if row["agent_id"] == "agent-hook-reused"
        )
        assert current["task_id"] == "task-hook-reused-current"
        assert current["status"] == "unresolved"
        assert current["task_terminal"] is False
        assert not ledger._coordinator_subagent_stop_matches_current_record(
            ledger.children["agent-hook-reused"], stale_hook
        )
        assert ledger.snapshot()["uncertainty"][-1]["reason"] == (
            "late SubagentStop lacks current launch, prompt, or invocation correlation"
        )

    asyncio.run(scenario())
