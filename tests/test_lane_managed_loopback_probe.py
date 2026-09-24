# SPDX-License-Identifier: Apache-2.0
"""Offline contracts for the bounded native loopback probe.

These tests use the probe's pure state helpers and offline handler methods. They
do not start a gateway, Claude, Docker, a model service, or any network listener.
"""

import base64
import builtins
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import threading
from types import SimpleNamespace

import pytest


PROBE = runpy.run_path(
    str(Path(__file__).parent / "probes" / "managed_native_loopback.py")
)
TWO_DOMAIN = runpy.run_path(
    str(Path(__file__).parent / "probes" / "managed_two_domain.py")
)
TWO_DOMAIN_PROBE = TWO_DOMAIN["probe"]


def response_plan(state, **kwargs):
    """Call the shared gateway state machine used by the live handler."""
    return state.response(**kwargs)


def offline_post_handler(state, path, headers, body, *, on_read=None, on_write=None):
    writes = []

    class Body:
        def __init__(self):
            self.read_calls = 0

        def read(self, length):
            self.read_calls += 1
            if on_read is not None:
                on_read()
            return body

    handler_type = PROBE["LoopbackHandler"]
    handler = handler_type.__new__(handler_type)
    handler.server = SimpleNamespace(gateway=state)
    handler.path = path
    handler.headers = headers
    handler.rfile = Body()
    handler.write_json = lambda status, value: writes.append(
        ("json", status, value)
    )

    def write_sse(value, *, response_challenge=None):
        writes.append(("sse", value))
        if on_write is not None:
            on_write()

    handler.write_sse = write_sse
    return handler, handler.rfile, writes


def busy_parent_continuation_body(tool_name="Agent"):
    return json.dumps({
        "model": PROBE["EXPECTED_MODEL"],
        "messages": [
            {
                "role": "assistant",
                "content": [{
                    "type": "tool_use",
                    "id": PROBE["SOURCE_AGENT_TOOL_ID"],
                    "name": tool_name,
                    "input": {},
                }],
            },
            {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": PROBE["SOURCE_AGENT_TOOL_ID"],
                    "content": "native task accepted",
                }],
            },
        ],
    }).encode()


def isolated_container():
    return {
        "Privileged": False,
        "Mounts": [],
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "PidMode": "",
            "IpcMode": "private",
            "UTSMode": "private",
            "CapAdd": [],
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "Binds": [],
            "VolumesFrom": [],
        },
    }


def test_route_normalizes_auxiliary_query_without_merging_routes():
    state = PROBE["GatewayState"]()

    # A no-tools parent request can be an auxiliary/setup inference.  It must
    # not consume the later source prompt that advertises the native Agent.
    auxiliary_context = state.inspect_parent_body(
        {
            "messages": [{"role": "user", "content": "auxiliary no-tools"}],
        },
        child=False,
    )
    auxiliary_plan = response_plan(
        state,
        child=False,
        prompt_marker=auxiliary_context["marker_present"],
        advertised_tool=auxiliary_context["advertised_tool"],
    )
    source_context = state.inspect_parent_body(
        {
            "tools": [
                {
                    "name": "Agent",
                    "input_schema": {
                        "properties": {
                            "subagent_type": {"enum": [PROBE["SOURCE_AGENT_NAME"]]},
                        },
                    },
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": PROBE["SOURCE_PROMPT_MARKER"],
                }
            ],
        },
        child=False,
    )
    source_plan = response_plan(
        state,
        child=False,
        prompt_marker=source_context["marker_present"],
        advertised_tool=source_context["advertised_tool"],
    )
    state.record("/v1/messages/count_tokens", child=False)
    state.record("/api/hello", child=False)

    assert auxiliary_plan["kind"] == "text-end-turn"
    assert source_plan["kind"] == "agent-tool"
    snapshot = state.snapshot()
    assert snapshot["route_counts"] == {
        "source": {
            "/v1/messages": 2,
            "/v1/messages/count_tokens": 1,
            "/api/hello": 1,
        }
    }
    assert snapshot["parent_posts"] == 2
    assert snapshot["child_posts"] == 0
    assert snapshot["agent_responses"] == 1
    assert snapshot["bash_responses"] == 0


def test_scripted_source_parent_child_sequence_then_drain_is_bounded():
    state = PROBE["GatewayState"]()

    parent_context = state.inspect_parent_body(
        {
            "tools": [{"name": "Agent"}],
            "messages": [
                {"role": "user", "content": PROBE["SOURCE_PROMPT_MARKER"]}
            ],
        },
        child=False,
    )
    parent = response_plan(
        state,
        child=False,
        prompt_marker=parent_context["marker_present"],
        advertised_tool=parent_context["advertised_tool"],
    )
    child = response_plan(state, child=True)
    state.set_phase("source-drain")
    state.mark_stop_requested()
    drained_parent = response_plan(state, child=False)
    drained_child = response_plan(state, child=True)

    assert parent == {
        "kind": "agent-tool", "status": 200, "tool_name": "Agent",
        "response_challenge": None,
    }
    assert child == {
        "kind": "bash-tool", "status": 200, "tool_name": None,
        "response_challenge": None,
    }
    assert drained_parent == {
        "kind": "text-end-turn",
        "status": 200,
        "tool_name": None,
        "response_challenge": None,
    }
    assert drained_child == {
        "kind": "text-end-turn",
        "status": 200,
        "tool_name": None,
        "response_challenge": None,
    }
    snapshot = state.snapshot()
    assert snapshot["route_counts"]["source"]["/v1/messages"] == 2
    assert snapshot["route_counts"]["source-drain"]["/v1/messages"] == 2
    assert snapshot["parent_posts"] == 2
    assert snapshot["child_posts"] == 2
    assert snapshot["agent_responses"] == 1
    assert snapshot["bash_responses"] == 1
    assert snapshot["protocol_errors"] == []


def test_control_entry_epoch_starts_once_spans_hold_and_excludes_release():
    state = PROBE["GatewayState"]()
    state.record("/api/hello", method="GET", response_kind="hello")
    state.record(
        "/v1/messages/count_tokens",
        method="POST",
        response_kind="count-tokens",
    )

    state.begin_control_entry_epoch(parent_settled=True)
    start = state.control_entry_snapshot()
    state.observe_messages_arrival()
    state.record("/v1/messages", response_kind="protocol-error")
    state.set_phase("source-drain")
    state.observe_messages_arrival()
    state.record(
        "/v1/messages",
        child=True,
        response_kind="held-error",
    )
    state.record(
        "/v1/messages/count_tokens",
        method="POST",
        response_kind="count-tokens",
    )
    state.record("/api/hello", method="GET", response_kind="hello")
    state.begin_control_entry_epoch(parent_settled=False)
    state.set_phase("target-held")
    state.observe_messages_arrival()
    held = response_plan(state, child=False)
    state.observe_messages_arrival()

    open_epoch = state.control_entry_snapshot()
    assert held == {
        "kind": "held-error", "status": 409, "tool_name": None,
        "response_challenge": None,
    }
    assert open_epoch["status"] == "incomplete-until-release"
    assert open_epoch["observation_scope"] == (
        "scripted-loopback-messages-arrivals"
    )
    assert open_epoch["begin_calls"] == 2
    assert open_epoch["parent_settled_at_control_entry"] is True
    assert open_epoch["start_request_index"] == start["start_request_index"]
    assert open_epoch["end_request_index"] is None
    assert open_epoch["inference_attempts"] == 4
    assert open_epoch["phase_counts"] == {
        "source": 1,
        "source-drain": 1,
        "target-held": 2,
    }
    assert open_epoch["phases_observed"] == [
        "source",
        "source-drain",
        "target-held",
    ]
    incomplete = PROBE["assess_control_entry_observation"](
        open_epoch,
        active_fixture_observed=True,
        source_parent_process_exited=True,
        target_hold_complete=True,
        cleanup_complete=True,
    )
    assert incomplete["coverage_status"] == "incomplete-until-release"
    assert incomplete["zero_request_observation"] is False

    state.release_control_entry_epoch(next_phase="target-release")
    state.record("/v1/messages", response_kind="request-too-large")
    released = state.control_entry_snapshot()
    assert released["status"] == "released"
    assert released["end_request_index"] is not None
    assert released["end_request_index"] < state.snapshot()["request_count"]
    assert released["inference_attempts"] == 4
    assert released["phase_counts"] == open_epoch["phase_counts"]
    assert released["end_phase"] == "target-held"
    assert "target-release" not in released["phase_counts"]
    complete = PROBE["assess_control_entry_observation"](
        released,
        active_fixture_observed=True,
        source_parent_process_exited=True,
        target_hold_complete=True,
        cleanup_complete=True,
    )
    assert complete["inference_observation"] == "positive"
    assert complete["zero_request_observation"] is False
    assert complete["support_claim"] is False
    assert complete["production_continuous_observer_capability"] is False


@pytest.mark.parametrize(
    "overrides, expected_reason",
    [
        (
            {"active_fixture_observed": False},
            "control-entry-fixture-not-observed",
        ),
        (
            {"read_failed": True},
            "control-entry-read-failed",
        ),
        (
            {"cleanup_complete": False},
            "control-entry-cleanup-incomplete",
        ),
    ],
)
def test_control_entry_missing_or_incomplete_evidence_never_becomes_zero(
    overrides, expected_reason
):
    epoch = {
        "enabled": True,
        "closed_by_release": True,
        "inference_attempts": 0,
    }
    options = {
        "active_fixture_observed": True,
        "source_parent_process_exited": True,
        "target_hold_complete": True,
        "cleanup_complete": True,
        "read_failed": False,
    }
    options.update(overrides)

    result = PROBE["assess_control_entry_observation"](epoch, **options)

    assert result["coverage_status"] == "unknown"
    assert result["zero_request_observation"] == "unknown"
    assert result["verdict"] == "inconclusive"
    assert result["support_claim"] is False
    assert expected_reason in result["reason_codes"]


def test_control_entry_invalid_counter_remains_unknown_not_zero():
    result = PROBE["assess_control_entry_observation"](
        {
            "enabled": True,
            "closed_by_release": True,
            "inference_attempts": "unknown",
        },
        active_fixture_observed=True,
        source_parent_process_exited=True,
        target_hold_complete=True,
        cleanup_complete=True,
    )

    assert result["inference_attempts"] is None
    assert result["inference_observation"] == "unknown"
    assert result["coverage_status"] == "unknown"
    assert result["zero_request_observation"] == "unknown"
    assert result["verdict"] == "inconclusive"


def test_control_entry_epoch_counter_is_locked_and_counts_only_message_posts():
    state = PROBE["GatewayState"]()
    state.begin_control_entry_epoch(parent_settled=False)
    errors = []

    def record_attempt():
        try:
            state.observe_messages_arrival()
            state.record(
                "/v1/messages",
                method="POST",
                response_kind="rejected",
            )
        except Exception as exc:  # pragma: no cover - diagnostic guard
            errors.append(exc)

    threads = [threading.Thread(target=record_attempt) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    state.record(
        "/v1/messages/count_tokens",
        method="POST",
        response_kind="count-tokens",
    )
    state.record("/api/hello", method="GET", response_kind="hello")

    epoch = state.control_entry_snapshot()
    assert errors == []
    assert epoch["inference_attempts"] == 16
    assert epoch["phase_counts"] == {"source": 16}
    assert state.snapshot()["request_count"] == 18


def test_handler_counts_arrival_before_delayed_body_response_after_release():
    state = PROBE["GatewayState"]()
    state.begin_control_entry_epoch(parent_settled=False)
    read_observations = []

    def release_during_read():
        read_observations.append(state.control_entry_snapshot())
        state.release_control_entry_epoch(next_phase="target-release")

    body = json.dumps({
        "model": PROBE["EXPECTED_MODEL"],
        "messages": [],
    }).encode()
    handler, body_stream, writes = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        body,
        on_read=release_during_read,
    )

    PROBE["LoopbackHandler"].do_POST(handler)

    assert body_stream.read_calls == 1
    assert read_observations[0]["inference_attempts"] == 1
    assert read_observations[0]["closed_by_release"] is False
    epoch = state.control_entry_snapshot()
    assert epoch["message_arrival_count"] == 1
    assert epoch["inference_attempts"] == 1
    assert epoch["start_request_index"] == 1
    assert epoch["end_request_index"] == 1
    assert epoch["status"] == "released"
    assert len(state.snapshot()["requests"]) == 1
    assert state.snapshot()["requests"][0]["phase"] == "target-release"
    assert writes and writes[0][0] == "sse"


def test_handler_counts_oversized_once_and_excludes_auxiliary_count_tokens():
    for content_length in ("invalid", str(PROBE["MAX_HTTP_BODY"] + 1)):
        oversized = PROBE["GatewayState"]()
        oversized.begin_control_entry_epoch(parent_settled=False)
        handler, body_stream, writes = offline_post_handler(
            oversized,
            "/v1/messages",
            {"Content-Length": content_length},
            b"body-not-read",
        )

        PROBE["LoopbackHandler"].do_POST(handler)

        assert body_stream.read_calls == 0
        assert writes[0][0:2] == ("json", 413)
        oversized_epoch = oversized.control_entry_snapshot()
        assert oversized_epoch["message_arrival_count"] == 1
        assert oversized_epoch["inference_attempts"] == 1
        assert oversized.snapshot()["request_count"] == 1

    auxiliary = PROBE["GatewayState"]()
    auxiliary.begin_control_entry_epoch(parent_settled=False)
    auxiliary_body = json.dumps({
        "model": PROBE["EXPECTED_MODEL"],
        "messages": [],
    }).encode()
    handler, body_stream, writes = offline_post_handler(
        auxiliary,
        "/v1/messages/count_tokens",
        {
            "Content-Length": str(len(auxiliary_body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        auxiliary_body,
    )

    PROBE["LoopbackHandler"].do_POST(handler)

    assert body_stream.read_calls == 1
    assert writes[0][0:2] == ("json", 200)
    auxiliary_epoch = auxiliary.control_entry_snapshot()
    assert auxiliary_epoch["message_arrival_count"] == 0
    assert auxiliary_epoch["inference_attempts"] == 0


def test_busy_parent_barrier_requires_exact_result_and_holds_response_until_release():
    state = PROBE["GatewayState"](busy_parent_enabled=True)
    state.source_agent_response_sent = True
    state.source_agent_tool_name = "Agent"
    state.bash_responses = 1
    body = busy_parent_continuation_body()
    write_observations = []
    handler, body_stream, writes = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        body,
        on_write=lambda: write_observations.append(
            state.busy_parent_snapshot()["response_completed"]
        ),
    )

    worker = threading.Thread(
        target=PROBE["LoopbackHandler"].do_POST,
        args=(handler,),
    )
    worker.start()
    assert state.wait_for_busy_parent_barrier(timeout=1.0) is True
    pending = state.busy_parent_snapshot()
    assert pending["continuation_classified"] is True
    assert pending["barrier_pending"] is True
    assert pending["barrier_waiting"] is True
    assert pending["request_arrival_index"] == 1
    assert pending["blocked_request_arrival_index"] == 1
    assert writes == []

    assert state.begin_busy_parent_control_entry(
        task_id="task-1",
        process_identity_digest="process-digest",
        child_active_pre_entry=True,
        bash_active_pre_entry=True,
    ) is True
    state.set_phase("source-drain")
    entry = state.busy_parent_snapshot()
    assert entry["control_entry_observed"] is True
    assert entry["child_active_pre_entry"] is True
    assert entry["bash_active_pre_entry"] is True
    assert entry["liveness_observation"] == "immediate-pre-entry-not-atomic"
    epoch = state.control_entry_snapshot()
    assert epoch["start_request_index"] == 2
    assert epoch["inference_attempts"] == 0

    state.release_busy_parent_barrier()
    worker.join(timeout=1.0)
    assert worker.is_alive() is False
    assert body_stream.read_calls == 1
    assert writes and writes[0][0] == "sse"
    assert write_observations == [False]

    state.set_phase("target-held")
    state.observe_messages_arrival()
    state.release_control_entry_epoch(next_phase="target-release")
    final_busy = state.busy_parent_snapshot()
    final_epoch = state.control_entry_snapshot()
    assert final_busy["barrier_released_after_control"] is True
    assert final_busy["barrier_released_before_control"] is False
    assert final_busy["response_completed"] is True
    assert final_epoch["inference_attempts"] == 1
    assert final_epoch["start_request_index"] == 2
    assert final_epoch["end_request_index"] == 2
    assessment = PROBE["assess_busy_parent_observation"](final_busy)
    assert assessment["busy_parent_witness"] is True
    assert final_busy["response_disposition"] == "write-succeeded"
    assert final_busy["response_write_started"] is True
    assert final_busy["response_write_succeeded"] is True
    assert final_busy["response_write_failed"] is False
    assert final_busy["handler_returned"] is True
    assert assessment["response_cancellation_observed"] is False
    assert "busy-parent-response-cancellation-unobserved" in assessment[
        "reason_codes"
    ]
    assert assessment["support_claim"] is False


def test_busy_parent_barrier_rejects_ambiguous_or_early_release_without_fallback():
    state = PROBE["GatewayState"](busy_parent_enabled=True)
    state.source_agent_response_sent = True
    state.source_agent_tool_name = "Agent"
    state.bash_responses = 1
    body = json.dumps({
        "model": PROBE["EXPECTED_MODEL"],
        "messages": [{"role": "user", "content": "no tool result"}],
    }).encode()
    handler, _, writes = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        body,
    )

    PROBE["LoopbackHandler"].do_POST(handler)
    assert writes and writes[0][0] == "sse"
    assert state.busy_parent_snapshot()["barrier_entered"] is False

    state = PROBE["GatewayState"](busy_parent_enabled=True)
    state.source_agent_response_sent = True
    state.source_agent_tool_name = "Agent"
    state.bash_responses = 1
    handler, _, writes = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(busy_parent_continuation_body())),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        busy_parent_continuation_body(),
    )
    worker = threading.Thread(
        target=PROBE["LoopbackHandler"].do_POST,
        args=(handler,),
    )
    worker.start()
    assert state.wait_for_busy_parent_barrier(timeout=1.0) is True
    state.release_busy_parent_barrier()
    worker.join(timeout=1.0)
    assert worker.is_alive() is False
    busy = state.busy_parent_snapshot()
    assert busy["barrier_released_before_control"] is True
    assert busy["control_entry_observed"] is False
    assessment = PROBE["assess_busy_parent_observation"](busy)
    assert assessment["busy_parent_witness"] is False
    assert "busy-parent-barrier-released-before-control" in assessment[
        "reason_codes"
    ]
    assert assessment["verdict"] == "inconclusive"
    assert assessment["support_claim"] is False


def test_busy_parent_requires_the_contract_agent_tool_name():
    state = PROBE["GatewayState"](busy_parent_enabled=True)
    state.source_agent_response_sent = True
    state.source_agent_tool_name = "Agent"
    state.bash_responses = 1
    body = busy_parent_continuation_body(tool_name="Task")
    handler, _, writes = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        body,
    )

    PROBE["LoopbackHandler"].do_POST(handler)

    assert writes and writes[0][0] == "sse"
    assert state.busy_parent_snapshot()["barrier_entered"] is False


def test_busy_parent_failed_selected_write_cannot_complete_on_unrelated_write():
    state = PROBE["GatewayState"](busy_parent_enabled=True)
    state.source_agent_response_sent = True
    state.source_agent_tool_name = "Agent"
    state.bash_responses = 1
    selected_body = busy_parent_continuation_body()

    def fail_selected_write():
        raise OSError("selected response write failed")

    selected_handler, _, _ = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(selected_body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        selected_body,
        on_write=fail_selected_write,
    )
    errors = []

    def run_selected_handler():
        try:
            PROBE["LoopbackHandler"].do_POST(selected_handler)
        except OSError as exc:
            errors.append(exc)

    worker = threading.Thread(target=run_selected_handler)
    worker.start()
    assert state.wait_for_busy_parent_barrier(timeout=1.0) is True
    assert state.begin_busy_parent_control_entry(
        task_id="task-1",
        process_identity_digest="process-digest",
        child_active_pre_entry=True,
        bash_active_pre_entry=True,
    ) is True
    state.release_busy_parent_barrier()
    worker.join(timeout=1.0)

    assert worker.is_alive() is False
    assert errors and isinstance(errors[0], OSError)
    assert state.busy_parent_snapshot()["response_completed"] is False

    unrelated_body = json.dumps({
        "model": PROBE["EXPECTED_MODEL"],
        "messages": [{"role": "user", "content": "unrelated"}],
    }).encode()
    unrelated_handler, _, unrelated_writes = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(unrelated_body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        unrelated_body,
    )
    PROBE["LoopbackHandler"].do_POST(unrelated_handler)

    assert unrelated_writes and unrelated_writes[0][0] == "sse"
    busy = state.busy_parent_snapshot()
    assert busy["request_arrival_index"] == 1
    assert busy["response_completed"] is False
    assert busy["response_write_started"] is True
    assert busy["response_write_succeeded"] is False
    assert busy["response_write_failed"] is True
    assert busy["response_disposition"] == "write-failed"
    assert busy["handler_returned"] is True


def test_busy_parent_control_entry_requires_active_child_bash_and_process_evidence():
    state = PROBE["GatewayState"](busy_parent_enabled=True)
    state.source_agent_response_sent = True
    state.source_agent_tool_name = "Agent"
    state.bash_responses = 0
    body = busy_parent_continuation_body()
    handler, _, _ = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        body,
    )
    worker = threading.Thread(
        target=PROBE["LoopbackHandler"].do_POST,
        args=(handler,),
    )
    worker.start()
    assert state.wait_for_busy_parent_barrier(timeout=1.0) is True
    assert state.begin_busy_parent_control_entry(
        task_id="task-1",
        process_identity_digest="process-digest",
        child_active_pre_entry=True,
        bash_active_pre_entry=False,
    ) is False
    state.release_busy_parent_barrier()
    worker.join(timeout=1.0)
    assert worker.is_alive() is False


def test_busy_parent_control_entry_refuses_preexisting_epoch():
    state = PROBE["GatewayState"](busy_parent_enabled=True)
    state.source_agent_response_sent = True
    state.source_agent_tool_name = "Agent"
    state.bash_responses = 1
    state.begin_control_entry_epoch(parent_settled=True)
    body = busy_parent_continuation_body()
    handler, _, _ = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        body,
    )
    worker = threading.Thread(
        target=PROBE["LoopbackHandler"].do_POST,
        args=(handler,),
    )
    worker.start()
    assert state.wait_for_busy_parent_barrier(timeout=1.0) is True
    assert state.begin_busy_parent_control_entry(
        task_id="task-1",
        process_identity_digest="process-digest",
        child_active_pre_entry=True,
        bash_active_pre_entry=True,
    ) is False
    state.release_busy_parent_barrier()
    worker.join(timeout=1.0)

    assert worker.is_alive() is False
    assert state.busy_parent_snapshot()["control_entry_observed"] is False
    assert state.control_entry_snapshot()["parent_settled_at_control_entry"] is True
    assessment = PROBE["assess_busy_parent_observation"](
        state.busy_parent_snapshot()
    )
    assert "busy-parent-pending-request-not-before-epoch" in assessment[
        "reason_codes"
    ]


def test_busy_parent_control_entry_refuses_stale_terminal_child_witness():
    runtime = {
        "frames_seen": 0,
        "unparsed_frames": 0,
        "native_task_events": 0,
        "target_wake_evidence": 0,
        "task_started": False,
        "actual_task_id": None,
        "task_agent_id": None,
    }
    PROBE["observe_frame"]({
        "type": "system",
        "subtype": "task_started",
        "task_type": "local_agent",
        "task_id": "task-1",
    }, runtime)
    PROBE["observe_frame"]({
        "type": "system",
        "subtype": "task_notification",
        "task_id": "task-1",
        "status": "completed",
    }, runtime)
    assert runtime["task_terminal_observed"] is True

    state = PROBE["GatewayState"](busy_parent_enabled=True)
    state.source_agent_response_sent = True
    state.source_agent_tool_name = "Agent"
    state.bash_responses = 1
    body = busy_parent_continuation_body()
    handler, _, _ = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        body,
    )
    worker = threading.Thread(
        target=PROBE["LoopbackHandler"].do_POST,
        args=(handler,),
    )
    worker.start()
    assert state.wait_for_busy_parent_barrier(timeout=1.0) is True
    assert state.begin_busy_parent_control_entry(
        task_id="task-1",
        process_identity_digest="process-digest",
        child_active_pre_entry=not runtime["task_terminal_observed"],
        bash_active_pre_entry=not runtime["task_terminal_observed"],
    ) is False
    state.release_busy_parent_barrier()
    worker.join(timeout=1.0)

    assert worker.is_alive() is False
    assert state.busy_parent_snapshot()["control_entry_observed"] is False


def test_busy_parent_barrier_deadline_is_inconclusive_and_returns_bounded_error():
    state = PROBE["GatewayState"](
        busy_parent_enabled=True,
        busy_parent_barrier_timeout=0.01,
    )
    state.source_agent_response_sent = True
    state.source_agent_tool_name = "Agent"
    state.bash_responses = 1
    body = busy_parent_continuation_body()
    handler, _, writes = offline_post_handler(
        state,
        "/v1/messages",
        {
            "Content-Length": str(len(body)),
            "x-api-key": PROBE["DUMMY_API_KEY"],
        },
        body,
    )
    worker = threading.Thread(
        target=PROBE["LoopbackHandler"].do_POST,
        args=(handler,),
    )

    worker.start()
    assert state.wait_for_busy_parent_barrier(timeout=1.0) is True
    worker.join(timeout=1.0)

    assert worker.is_alive() is False
    assert writes and writes[0][0:2] == ("json", 504)
    busy = state.busy_parent_snapshot()
    assert busy["barrier_expired"] is True
    assert busy["response_completed"] is False
    assert busy["response_disposition"] == "barrier-expired"
    assert busy["response_cancellation_observed"] is False
    assessment = PROBE["assess_busy_parent_observation"](busy)
    assert assessment["busy_parent_witness"] is False
    assert "busy-parent-barrier-deadline-expired" in assessment["reason_codes"]
    assert assessment["verdict"] == "inconclusive"
    assert assessment["support_claim"] is False


def test_target_hold_same_uuid_and_quiet_gateway_do_not_prove_exact_parent_load():
    result = PROBE["assess_target_hold_observation"](
        {
            "hold_complete": True,
            "initialize_succeeded": True,
            "source_session_id": "source-session",
            "target_session_id": "source-session",
            "messages_posts": 0,
            "count_tokens_posts": 0,
            "api_hello_requests": 0,
            "endpoint_sensor_calibrated": True,
            "authoritative_loader_evidence": False,
        }
    )

    assert result["same_parent_uuid"] is True
    assert result["model_request_free_observation"] is True
    assert result["exact_parent_load"] == "unknown"
    assert result["support_claim"] is False
    assert "target-parent-load-not-proven" in result["reason_codes"]


def test_target_hold_missing_sensor_or_loader_evidence_stays_unknown():
    result = PROBE["assess_target_hold_observation"](
        {
            "hold_complete": True,
            "initialize_succeeded": True,
            "source_session_id": "source-session",
            "target_session_id": "source-session",
            "messages_posts": 0,
            "count_tokens_posts": 0,
            "api_hello_requests": 0,
        }
    )

    assert result["model_request_free_observation"] == "unknown"
    assert result["exact_parent_load"] == "unknown"
    assert "target-monitor-incomplete" in result["reason_codes"]
    assert "target-parent-load-not-proven" in result["reason_codes"]


def test_positive_orphan_assessment_does_not_promote_unverified_subtype_names():
    result = PROBE["assess_positive_orphan_observation"]({
        "control_mode": "crash-left-unfinished",
        "crash_requested": True,
        "records_observed_before_crash": True,
        "observed_owned_processes_excluded": True,
        "source_parent_process_exited": True,
        "target_launched": True,
        "target_hold_complete": True,
        "control_events": {
            "persisted_record_load": 1,
            "restored_orphans": 1,
            "child_parent_wake": 1,
            "notification_enqueue": 1,
        },
        "target_model_request_observed": True,
    })

    assert result["status"] == "unsupported"
    assert result["persisted_record_load"] == "unknown"
    assert result["restored_orphans"] == "unknown"
    assert result["child_parent_wake"] == "unknown"
    assert result["notification_enqueue"] == "unknown"
    assert result["model_query_attempt"] == "observed"
    assert "selected-runtime-orphan-event-schema-unavailable" in result[
        "reason_codes"
    ]
    assert result["support_claim"] is False


def test_positive_orphan_assessment_refuses_without_runtime_event_boundary():
    result = PROBE["assess_positive_orphan_observation"]({
        "control_mode": "crash-left-unfinished",
        "crash_requested": True,
        "records_observed_before_crash": True,
        "observed_owned_processes_excluded": True,
        "source_parent_process_exited": True,
        "target_launched": True,
        "target_hold_complete": True,
        "control_events": {},
        "target_model_request_observed": False,
    })

    assert result["status"] == "unsupported"
    assert result["support_claim"] is False
    assert "selected-runtime-orphan-event-schema-unavailable" in result[
        "reason_codes"
    ]


def test_terminal_clear_assessment_keeps_clear_and_target_facts_independent():
    result = PROBE["assess_terminal_clear_observation"]({
        "control_mode": "stopped",
        "actual_task_id": "task-1",
        "stop_receipt": True,
        "stopped_notification": True,
        "tool_terminal": True,
        "tracked_process_exited_before_cleanup": True,
        "source_parent_process_exited": True,
        "forced_cleanup": False,
        "control_events": {"durable_state_clear": 1},
        "target_launched": True,
        "target_hold_complete": True,
        "target_model_request_free": True,
        "target_wake_evidence": 0,
    })

    assert result["status"] == "unsupported"
    assert result["terminal_state_clear"] == "unknown"
    assert result["worker_state_clear"] == "unknown"
    assert result["orphan_state_clear"] == "unknown"
    assert result["target_connect"] == "unknown"
    assert result["target_no_wake"] == "unknown"
    assert result["model_query_attempt"] == "not-observed"
    assert "selected-runtime-state-clear-schema-unavailable" in result[
        "reason_codes"
    ]
    assert "target-connect-correlation-unavailable" in result["reason_codes"]
    assert result["support_claim"] is False


def test_terminal_clear_assessment_refuses_unknown_durable_state_clear():
    result = PROBE["assess_terminal_clear_observation"]({
        "control_mode": "stopped",
        "actual_task_id": "task-1",
        "stop_receipt": True,
        "stopped_notification": True,
        "tool_terminal": True,
        "tracked_process_exited_before_cleanup": True,
        "source_parent_process_exited": True,
        "forced_cleanup": False,
        "control_events": {},
        "source_control_messages": 1,
        "target_launched": True,
        "target_hold_complete": True,
        "target_model_request_free": True,
        "target_wake_evidence": 0,
    })

    assert result["status"] == "unsupported"
    assert result["terminal_state_clear"] == "unknown"
    assert result["target_no_wake"] == "unknown"
    assert result["control_request_free"] is False
    assert result["negative_gate"] == "source-control-request-observed"
    assert "selected-runtime-state-clear-schema-unavailable" in result[
        "reason_codes"
    ]


def test_target_release_is_separate_from_hold_and_retains_only_continuity_facts():
    state = PROBE["GatewayState"]()
    release_frame = PROBE["target_release_frame"]()

    state.set_phase("target-held")
    held = response_plan(state, child=False)
    state.set_phase("target-release")
    released = response_plan(state, child=False)

    release_body = {
        "messages": [
            {"role": "user", "content": PROBE["SOURCE_PROMPT_MARKER"]},
            {"role": "user", "content": PROBE["TARGET_RELEASE_MARKER"]},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu-gate0-agent",
                        "name": "Agent",
                        "input": {"private_prompt": "continuity-secret"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu-gate0-agent",
                        "content": "private-result-body",
                    }
                ],
            },
        ]
    }
    state.inspect_target_release_body(release_body)
    history = state.diagnostics()["target_release_history"]

    assert release_frame["type"] == "user"
    assert release_frame["message"]["content"] == PROBE["TARGET_RELEASE_MARKER"]
    assert release_frame["parent_tool_use_id"] is None
    assert held == {
        "kind": "held-error", "status": 409, "tool_name": None,
        "response_challenge": None,
    }
    assert released == {
        "kind": "text-end-turn", "status": 200, "tool_name": None,
        "response_challenge": None,
    }
    assert history["requests_seen"] == 1
    assert history["source_marker_present"] is True
    assert history["release_marker_present"] is True
    assert history["agent_tool_use_present"] is True
    assert history["agent_tool_result_present"] is True
    assert history["agent_tool_name"] == "Agent"
    assert len(history["history_facts_digest"]) == 64
    serialized = json.dumps(history, sort_keys=True)
    assert PROBE["SOURCE_PROMPT_MARKER"] not in serialized
    assert PROBE["TARGET_RELEASE_MARKER"] not in serialized
    assert "continuity-secret" not in serialized
    assert "private-result-body" not in serialized
    assert state.snapshot()["route_counts"] == {
        "target-held": {"/v1/messages": 1},
        "target-release": {"/v1/messages": 1},
    }


def test_unfinished_child_crash_phase_blocks_dispatch_and_keeps_process_kill_bounded(
    monkeypatch,
):
    state = PROBE["GatewayState"]()
    state.set_phase("source-crash")

    parent = response_plan(state, child=False)
    child = response_plan(state, child=True)

    assert parent == {
        "kind": "protocol-error", "status": 409, "tool_name": None,
        "response_challenge": None,
    }
    assert child == {
        "kind": "protocol-error", "status": 409, "tool_name": None,
        "response_challenge": None,
    }
    snapshot = state.snapshot()
    assert snapshot["route_counts"] == {"source-crash": {"/v1/messages": 2}}
    assert snapshot["parent_posts"] == 0
    assert snapshot["child_posts"] == 1
    assert "unexpected-messages-state" in snapshot["protocol_errors"]

    class FixtureProcess:
        pid = 48123

        def __init__(self):
            self.exited = False

        def poll(self):
            return None if not self.exited else -9

        def wait(self, timeout):
            self.exited = True
            return -9

    process = FixtureProcess()
    killed = []
    monkeypatch.setattr(
        PROBE["os"],
        "killpg",
        lambda pid, signal_number: killed.append((pid, signal_number)),
    )

    assert PROBE["crash_owned_process_group"](process) is True
    assert killed == [(48123, PROBE["signal"].SIGKILL)]


def test_gateway_diagnostics_bounds_first_parent_tools_and_records_agent_task_availability():
    state = PROBE["GatewayState"]()
    private_marker = "first-parent-private-schema-body"
    tools = [
        {
            "name": "Agent",
            "description": private_marker,
            "input_schema": {
                "properties": {
                    "subagent_type": {"enum": [PROBE["SOURCE_AGENT_NAME"]]},
                },
            },
        },
        {
            "name": "Task",
            "description": "task-private-schema-body",
            "input_schema": {
                "properties": {"subagent_type": {"enum": ["other-worker"]}},
            },
        },
        {"name": "Bash", "description": "bash-private-schema-body"},
    ]
    tools.extend(
        {"name": f"Z-Auxiliary-{index:03d}", "description": private_marker}
        for index in range(140)
    )

    state.inspect_parent_body({"tools": tools}, child=False)
    diagnostics = state.diagnostics()

    assert diagnostics["parent_messages_seen"] == 1
    assert diagnostics["first_parent_agent_schema_has_worker"] is True
    declared = diagnostics["first_parent_declared_tool_names"]
    assert len(declared) == 128
    assert {"Agent", "Task", "Bash"}.issubset(declared)
    assert private_marker not in json.dumps(diagnostics, sort_keys=True)


@pytest.mark.parametrize(
    "error_text, expected_classification",
    [
        ("unknown agent definition for gate0-worker", "unknown-agent-definition"),
        ("permission denied by the gateway", "permission-denied"),
        ("unknown tool requested", "unknown-tool"),
        ("invalid input schema: required field missing", "invalid-input"),
        ("gateway refused the operation", "other"),
    ],
)
def test_gateway_diagnostics_allowlists_matching_agent_error_categories(
    error_text, expected_classification
):
    state = PROBE["GatewayState"]()
    state.inspect_parent_body({"tools": [{"name": "Agent"}]}, child=False)
    state.inspect_parent_body(
        {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu-gate0-agent",
                            "is_error": True,
                            "content": error_text,
                        }
                    ],
                }
            ]
        },
        child=False,
    )

    diagnostics = state.diagnostics()
    assert diagnostics["second_parent_agent_result"] == {
        "matched": True,
        "is_error": True,
        "classification": expected_classification,
    }
    assert error_text not in json.dumps(diagnostics, sort_keys=True)


def test_gateway_diagnostics_matches_only_the_declared_agent_tool_result_id():
    first_parent = {"tools": [{"name": "Agent"}, {"name": "Task"}]}
    wrong_id = {
        "messages": [
            {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu-similar-but-wrong",
                        "is_error": True,
                        "content": "unknown agent private error",
                    }
                ]
            }
        ]
    }

    unmatched = PROBE["GatewayState"]()
    unmatched.inspect_parent_body(first_parent, child=False)
    unmatched.inspect_parent_body(wrong_id, child=False)
    assert unmatched.diagnostics()["second_parent_agent_result"] == {
        "matched": False,
        "is_error": None,
        "classification": "other",
    }

    matched = PROBE["GatewayState"]()
    matched.inspect_parent_body(first_parent, child=False)
    matched.inspect_parent_body(
        {
            "messages": [
                {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu-gate0-agent",
                            "is_error": False,
                            "content": "private successful result",
                        }
                    ]
                }
            ]
        },
        child=False,
    )
    assert matched.diagnostics()["second_parent_agent_result"] == {
        "matched": True,
        "is_error": False,
        "classification": "other",
    }


def test_child_tool_counter_does_not_promote_every_child_message_to_tool_use():
    state = PROBE["GatewayState"]()

    state.record("/v1/messages", child=True, response_kind="text-end-turn")
    state.record("/v1/messages", child=True, response_kind="bash-tool")

    snapshot = state.snapshot()
    assert snapshot["child_posts"] == 2
    assert snapshot["bash_responses"] == 1


def test_target_held_rejects_parent_and_child_messages_without_dispatch():
    state = PROBE["GatewayState"]()
    state.set_phase("target-held")

    parent = response_plan(state, child=False)
    child = response_plan(state, child=True)

    assert parent == {
        "kind": "held-error", "status": 409, "tool_name": None,
        "response_challenge": None,
    }
    assert child == {
        "kind": "held-error", "status": 409, "tool_name": None,
        "response_challenge": None,
    }
    snapshot = state.snapshot()
    assert snapshot["route_counts"] == {"target-held": {"/v1/messages": 2}}
    assert snapshot["parent_posts"] == 0
    assert snapshot["child_posts"] == 1
    assert snapshot["agent_responses"] == 0
    assert snapshot["bash_responses"] == 0
    assert snapshot["protocol_errors"] == []


@pytest.mark.parametrize(
    "observation, expected_reason",
    [
        (
            {
                "actual_task_id": "task-1",
                "stop_sent": True,
                "stop_receipt": True,
                "stopped_notification": False,
                "tool_terminal": True,
                "tracked_process_exited_before_cleanup": True,
                "source_parent_process_exited": True,
                "forced_cleanup": False,
            },
            "stop-receipt-without-terminal-event",
        ),
        (
            {
                "actual_task_id": "task-1",
                "stop_sent": True,
                "stop_receipt": True,
                "stopped_notification": True,
                "tool_terminal": True,
                "tracked_process_exited_before_cleanup": False,
                "source_parent_process_exited": True,
                "forced_cleanup": True,
            },
            "forced-cleanup-is-not-stop-evidence",
        ),
    ],
)
def test_stop_assessment_rejects_ack_or_forced_cleanup_without_full_boundary(
    observation, expected_reason
):
    result = PROBE["assess_stop_observation"](observation)

    assert result["stop_candidate"] is False
    assert expected_reason in result["reason_codes"]
    assert result["verdict"] == "inconclusive"
    assert result["support_claim"] is False


def test_stop_assessment_never_grants_support_even_when_all_facts_are_present():
    result = PROBE["assess_stop_observation"]({
        "actual_task_id": "task-1",
        "stop_sent": True,
        "stop_receipt": True,
        "stopped_notification": True,
        "tool_terminal": True,
        "tracked_process_exited_before_cleanup": True,
        "source_parent_process_exited": True,
        "forced_cleanup": False,
    })

    assert result["stop_candidate"] is True
    assert result["support_claim"] is False
    assert result["verdict"] == "inconclusive"


def test_task_notification_without_tool_terminal_is_not_quiescence():
    result = PROBE["assess_stop_observation"]({
        "actual_task_id": "task-1",
        "stop_sent": True,
        "stop_receipt": True,
        "stopped_notification": True,
        "tool_terminal": False,
        "tracked_process_exited_before_cleanup": True,
        "source_parent_process_exited": True,
        "forced_cleanup": False,
    })

    assert result["stop_candidate"] is False
    assert "tool-terminal-evidence-missing" in result["reason_codes"]
    assert result["support_claim"] is False


def test_observe_frame_keeps_task_stop_and_bash_tool_terminal_independent():
    runtime = {
        "init_request": "init",
        "stop_request": "stop",
        "initialize_succeeded": False,
        "session_id": None,
        "frames_seen": 0,
        "unparsed_frames": 0,
        "native_task_events": 0,
        "target_wake_evidence": 0,
        "task_started": False,
        "actual_task_id": None,
        "task_agent_id": None,
        "stop_receipt": False,
        "stopped_notification": False,
        "tool_terminal": False,
    }

    PROBE["observe_frame"]({
        "type": "system",
        "subtype": "task_started",
        "task_type": "local_agent",
        "task_id": "task-1",
        "agent_id": "agent-1",
    }, runtime)
    PROBE["observe_frame"]({
        "type": "system",
        "subtype": "task_notification",
        "task_id": "task-1",
        "status": "stopped",
    }, runtime)

    assert runtime["stopped_notification"] is True
    assert runtime["tool_terminal"] is False

    PROBE["observe_frame"]({
        "type": "system",
        "subtype": "tool_result",
        "tool_use_id": PROBE["SOURCE_TOOL_ID"],
    }, runtime)
    assert runtime["tool_terminal"] is True


def test_observe_frame_keeps_documented_interrupt_receipt_distinct_from_stop():
    runtime = {
        "init_request": "init",
        "stop_request": "source-stop",
        "interrupt_request": "source-interrupt",
        "initialize_succeeded": False,
        "session_id": None,
        "frames_seen": 0,
        "unparsed_frames": 0,
        "native_task_events": 0,
        "target_wake_evidence": 0,
        "task_started": False,
        "actual_task_id": None,
        "task_agent_id": None,
        "stop_receipt": False,
        "interrupt_receipt": False,
        "stopped_notification": False,
        "tool_terminal": False,
    }

    PROBE["observe_frame"]({
        "type": "control_response",
        "response": {"request_id": "source-interrupt", "subtype": "success"},
    }, runtime)

    assert runtime["interrupt_receipt"] is True
    assert runtime["stop_receipt"] is False

    assessment = PROBE["assess_stop_observation"]({
        "control_action": "interrupt",
        "actual_task_id": "task-1",
        "interrupt_sent": True,
        "interrupt_receipt": True,
        "stopped_notification": True,
        "tool_terminal": True,
        "tracked_process_exited_before_cleanup": True,
        "source_parent_process_exited": True,
        "forced_cleanup": False,
    })
    assert assessment["control_action"] == "interrupt"
    assert assessment["control_candidate"] is True
    assert assessment["support_claim"] is False


def test_owned_fixture_capture_excludes_unrelated_and_ambiguous_sleepers(
    monkeypatch,
):
    snapshot = {
        100: {
            "pid": 100,
            "ppid": 1,
            "starttime": "root",
            "state": "S",
            "scripted_sleeper": False,
        },
        101: {
            "pid": 101,
            "ppid": 100,
            "starttime": "owned",
            "state": "S",
            "scripted_sleeper": True,
        },
        102: {
            "pid": 102,
            "ppid": 101,
            "starttime": "owned-child",
            "state": "S",
            "scripted_sleeper": False,
        },
        201: {
            "pid": 201,
            "ppid": 999,
            "starttime": "unrelated",
            "state": "S",
            "scripted_sleeper": True,
        },
    }
    # ``runpy.run_path`` returns a namespace dict, but helper functions keep
    # the module globals mapping used during execution.  Patch that mapping so
    # the capture helper observes the bounded fixture snapshot.
    monkeypatch.setitem(
        PROBE["capture_owned_fixture_processes"].__globals__,
        "_proc_snapshot",
        lambda: snapshot,
    )

    captured = PROBE["capture_owned_fixture_processes"](100)

    assert [identity["pid"] for identity in captured] == [101, 102]
    assert 201 not in {identity["pid"] for identity in captured}

    snapshot[103] = {
        "pid": 103,
        "ppid": 100,
        "starttime": "second-owned",
        "state": "S",
        "scripted_sleeper": True,
    }
    assert PROBE["capture_owned_fixture_processes"](100) == []


def test_resume_replacement_uses_exact_inline_sdk_argument_and_preserves_other_argv():
    session_id = "11111111-1111-4111-8111-111111111111"
    template = [
        "--output-format",
        "stream-json",
        "--resume=__LANE_LOOPBACK_SESSION__",
        "--input-format",
        "stream-json",
    ]

    replaced = PROBE["replace_resume_sentinel"](template, session_id)

    assert replaced == [
        "--output-format",
        "stream-json",
        "--resume=" + session_id,
        "--input-format",
        "stream-json",
    ]
    assert template[2] == "--resume=__LANE_LOOPBACK_SESSION__"


@pytest.mark.parametrize(
    "arguments, session_id",
    [
        (["--output-format", "stream-json"], "11111111-1111-4111-8111-111111111111"),
        (
            ["--resume=__LANE_LOOPBACK_SESSION__", "__LANE_LOOPBACK_SESSION__"],
            "11111111-1111-4111-8111-111111111111",
        ),
        (["--resume=__LANE_LOOPBACK_SESSION__"], ""),
    ],
)
def test_resume_replacement_rejects_missing_duplicate_or_empty_session(
    arguments, session_id
):
    with pytest.raises(ValueError, match="sentinel|session id"):
        PROBE["replace_resume_sentinel"](arguments, session_id)


@pytest.mark.parametrize(
    "change",
    [
        lambda record: record["HostConfig"].update(NetworkMode="host"),
        lambda record: record.update(Privileged=True),
        lambda record: record["HostConfig"].update(ReadonlyRootfs=False),
        lambda record: record["HostConfig"].update(PidMode="host"),
        lambda record: record["HostConfig"].update(IpcMode="host"),
        lambda record: record["HostConfig"].update(UTSMode="host"),
        lambda record: record["HostConfig"].update(CapAdd=["SYS_ADMIN"]),
        lambda record: record["HostConfig"].update(CapDrop=[]),
        lambda record: record["HostConfig"].update(SecurityOpt=[]),
        lambda record: record.update(Mounts=[{"Type": "bind", "Source": "/host"}]),
        lambda record: record["HostConfig"].update(Binds=["/host:/work"]),
        lambda record: record["HostConfig"].update(VolumesFrom=["other"]),
    ],
)
def test_isolation_rejects_each_unsafe_boundary(change):
    record = isolated_container()
    change(record)

    with pytest.raises(RuntimeError, match="probe|requires|refuses"):
        PROBE["validate_isolation"](record)


def test_isolation_accepts_only_literal_disposable_shape():
    PROBE["validate_isolation"](isolated_container())


def test_safe_event_keeps_only_sanitized_identity_and_status_fields():
    event = {
        "type": "system",
        "subtype": "task_notification",
        "status": "stopped",
        "task_id": "task-secret",
        "agent_id": "agent-secret",
        "content": "private transcript body",
        "message": "private prompt",
        "response": {"request_id": "request-secret", "subtype": "success"},
    }

    sanitized = PROBE["safe_event"](event)

    assert sanitized == {
        "type": "system",
        "subtype": "task_notification",
        "status": "stopped",
        "task_id_seen": True,
        "task_id_digest": hashlib.sha256(b"task-secret").hexdigest(),
        "agent_id_seen": True,
        "agent_id_digest": hashlib.sha256(b"agent-secret").hexdigest(),
        "request_id": True,
    }
    serialized = repr(sanitized)
    assert "private" not in serialized
    assert "task-secret" not in serialized
    assert "agent-secret" not in serialized
    assert "request-secret" not in serialized


def test_safe_event_classifies_malformed_frame_without_retaining_content():
    assert PROBE["safe_event"]("private raw frame") == {"frame": "unparsed"}


def test_stop_then_resume_v1_requires_persisted_release_before_target_creation(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    parent_identity = {
        "session_id": "parent-session-1",
        "result_uuid_digest": "source-result-digest",
    }
    prepared = ledger.prepare(
        parent_identity=parent_identity,
        pre_stop_history={"watermark": 7, "record_digest": "history-digest"},
    )

    assert prepared["mode"] == "stop-then-resume-v1"
    assert prepared["phase"] == "preflight"
    assert prepared["target_created"] is False
    assert ledger.snapshot()["request_identity"]["mode"] == "stop-then-resume-v1"
    assert ledger.snapshot()["operation_metadata"]["mode"] == "stop-then-resume-v1"

    with pytest.raises(RuntimeError, match="release-authorized"):
        ledger.record_target_facts(
            parent_identity=parent_identity,
            retained_history=True,
            edit_hash=prepared["edit_hash"],
        )
    assert ledger.snapshot()["target_created"] is False

    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": [],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )
    release = ledger.request_release(explicit=True)

    assert release["authorized"] is True
    assert release["release_persisted"] is True
    assert ledger.release_path.exists()
    assert ledger.snapshot()["target_created"] is False
    assert ledger.record_launch_intent()["target_launch_intent_persisted"] is True

    ledger.record_target_facts(
        parent_identity={
            "session_id": "parent-session-1",
            "result_uuid_digest": "different-target-event",
        },
        retained_history=True,
        edit_hash=prepared["edit_hash"],
        result_identity_observed=True,
    )
    report = ledger.report()

    assert report["restoration_verdict"] == "positive"
    assert report["exact_parent_identity"] == "observed"
    assert report["pre_stop_history_retained"] == "observed"
    assert report["retained_history_scope"] == "parent-boundary-markers-only"
    assert report["child_history_retained"] == "unverified"
    assert report["edit_unchanged"] is True
    assert report["source_native_facts"] != report["harness_cleanup_facts"]
    assert report["source_termination_task_completed"] is False
    assert report["support_claim"] is False


def test_stop_then_resume_v1_explicit_release_refuses_unknown_effect_without_target(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    parent_identity = {"session_id": "parent-session-2"}
    ledger.prepare(
        parent_identity=parent_identity,
        pre_stop_history={"watermark": 11, "record_digest": "history-digest"},
    )
    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": ["untracked-writer"],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )

    refusal = ledger.request_release(explicit=True)
    report = ledger.report()

    assert refusal["release_requested"] is True
    assert refusal["authorized"] is False
    assert refusal["reason_code"] == "unknown-effects"
    assert refusal["release_persisted"] is False
    assert refusal["ready_to_resume"] is False
    assert refusal["target_creation_authorized"] is False
    assert report["target_created"] is False
    assert report["restoration_verdict"] == "inconclusive"
    assert report["reason_codes"] == ["unknown-effects"]
    assert report["support_claim"] is False


def test_stop_then_resume_v1_wrong_parent_identity_is_inconclusive(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    source_identity = {"session_id": "parent-session-3"}
    ledger.prepare(
        parent_identity=source_identity,
        pre_stop_history={"watermark": 13},
    )
    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": [],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )
    assert ledger.request_release(explicit=True)["authorized"] is True
    assert ledger.record_launch_intent()["target_launch_intent_persisted"] is True

    ledger.record_target_facts(
        parent_identity={"session_id": "different-parent"},
        retained_history=True,
        edit_hash=ledger.snapshot()["edit_hash"],
        result_identity_observed=True,
    )
    report = ledger.report()

    assert report["restoration_verdict"] == "inconclusive"
    assert report["exact_parent_identity"] == "unknown"
    assert report["pre_stop_history_retained"] == "observed"
    assert report["support_claim"] is False


def test_stop_then_resume_v1_missing_retained_history_is_inconclusive(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    parent_identity = {"session_id": "parent-session-4"}
    ledger.prepare(
        parent_identity=parent_identity,
        pre_stop_history={"watermark": 17},
    )
    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": [],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )
    assert ledger.request_release(explicit=True)["authorized"] is True
    assert ledger.record_launch_intent()["target_launch_intent_persisted"] is True

    ledger.record_target_facts(
        parent_identity=parent_identity,
        retained_history=False,
        edit_hash=ledger.snapshot()["edit_hash"],
        result_identity_observed=True,
    )
    report = ledger.report()

    assert report["restoration_verdict"] == "inconclusive"
    assert report["exact_parent_identity"] == "observed"
    assert report["pre_stop_history_retained"] == "unknown"
    assert report["support_claim"] is False


def test_stop_then_resume_v1_rechecks_boundary_and_late_unknown_effect(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    parent_identity = {"session_id": "parent-session-5"}
    ledger.prepare(
        parent_identity=parent_identity,
        pre_stop_history={"watermark": 19},
    )
    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": [],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )
    assert ledger.request_release(explicit=True)["authorized"] is True
    late_refusal = ledger.request_release(
        explicit=True,
        unknown_effect=True,
    )

    assert late_refusal["authorized"] is False
    assert late_refusal["reason_code"] == "unknown-effects"
    assert ledger.report()["restoration_verdict"] == "inconclusive"

    state = json.loads(ledger.state_path.read_text(encoding="utf-8"))
    state["source_parent_identity_digest"] = "tampered"
    ledger.state_path.write_text(json.dumps(state), encoding="utf-8")
    recovered = PROBE["StopThenResumeV1Ledger"](ledger.workspace)
    report = recovered.report()

    assert report["release_authorized"] is False
    assert report["target_creation_authorized"] is False
    assert report["restoration_verdict"] == "inconclusive"
    assert report["support_claim"] is False


def test_stop_then_resume_v1_recovery_rejects_tampered_history_binding(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    ledger.prepare(
        parent_identity={"session_id": "parent-session-6"},
        pre_stop_history={"watermark": 23},
    )
    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": [],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )
    assert ledger.request_release(explicit=True)["authorized"] is True

    state = json.loads(ledger.state_path.read_text(encoding="utf-8"))
    state["operation_metadata"]["pre_stop_history_digest"] = "tampered"
    ledger.state_path.write_text(json.dumps(state), encoding="utf-8")
    recovered = PROBE["StopThenResumeV1Ledger"](ledger.workspace)

    assert recovered.report()["release_authorized"] is False
    assert recovered.report()["release_persisted"] is False
    assert recovered.report()["restoration_verdict"] == "inconclusive"


def _v1_history_gate_observation(**overrides):
    observation = {
        "initialize_succeeded": True,
        "target_alive": True,
        "session_identity_observed": False,
        "session_identity_mismatch": False,
        "resume_spec_bound": True,
        "source_manifest_bound": True,
        "parent_messages_since_launch": 0,
        "child_messages_since_launch": 0,
        "native_task_events": 0,
        "startup_parent_result_observed": False,
        "generic_startup_activity_observed": False,
        "reader_error": False,
        "unparsed_frames": 0,
        "unclassified_lifecycle_events": 0,
        "quiet_window_observed": True,
    }
    observation.update(overrides)
    return observation


@pytest.mark.parametrize(
    ("name", "overrides", "reason"),
    [
        (
            "parent-post",
            {"parent_messages_since_launch": 1},
            "startup-parent-message-observed",
        ),
        (
            "child-post",
            {"child_messages_since_launch": 1},
            "startup-child-message-observed",
        ),
        (
            "task-event",
            {"native_task_events": 1},
            "startup-task-event-observed",
        ),
        (
            "activity-then-terminal",
            {"generic_startup_activity_observed": True},
            "startup-assistant-or-tool-activity-observed",
        ),
        (
            "reader-error",
            {"reader_error": True},
            "startup-reader-error",
        ),
    ],
)
def test_stop_then_resume_v1_history_gate_skips_on_startup_activity(
    name, overrides, reason
):
    del name
    result = PROBE["assess_v1_history_query_gate"](
        _v1_history_gate_observation(**overrides)
    )

    assert result["history_query_allowed"] is False
    assert result["history_query_skipped"] is True
    assert reason in result["reason_codes"]
    assert result["support_claim"] is False


def test_stop_then_resume_v1_history_gate_allows_one_quiet_query_without_echoed_uuid():
    result = PROBE["assess_v1_history_query_gate"](
        _v1_history_gate_observation()
    )

    assert result["history_query_allowed"] is True
    assert result["history_query_skipped"] is False
    assert result["quiet_window_observed"] is True
    assert result["support_claim"] is False


def test_stop_then_resume_v1_history_gate_rejects_observed_session_mismatch():
    result = PROBE["assess_v1_history_query_gate"](
        _v1_history_gate_observation(
            session_identity_observed=True,
            session_identity_mismatch=True,
        )
    )

    assert result["history_query_allowed"] is False
    assert "target-session-identity-mismatch" in result["reason_codes"]


def test_owned_identity_observation_error_is_unknown_not_absent():
    identity = {"pid": "not-a-pid", "starttime": "unknown"}

    assert PROBE["_identity_status"](identity) == "unknown"
    assert PROBE["fixture_processes_alive"]([identity]) is None


def test_stop_then_resume_v1_source_reader_and_protocol_facts_block_release(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    ledger.prepare(
        parent_identity={"session_id": "parent-session-reader"},
        pre_stop_history={"watermark": 29},
    )
    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": [],
            "read_failed": True,
            "unparsed_frames": 1,
            "protocol_errors": ["unexpected-messages-state"],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )

    refusal = ledger.request_release(explicit=True)
    report = ledger.report()

    assert refusal["authorized"] is False
    assert refusal["reason_code"] == "source-not-ready"
    assert report["source_native_facts"]["read_failed"] is True
    assert report["source_native_facts"]["unparsed_frames"] == 1
    assert report["source_native_facts"]["protocol_errors"] == [
        "unexpected-messages-state"
    ]
    assert report["target_created"] is False
    assert report["support_claim"] is False


def test_stop_then_resume_v1_unknown_effect_requires_valid_otherwise_arm(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    ledger.prepare(
        parent_identity={"session_id": "parent-session-negative"},
        pre_stop_history={"watermark": 31},
    )
    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": ["injected-unknown-effect"],
            "read_failed": True,
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )

    refusal = ledger.request_release(explicit=True)
    report = ledger.report()

    assert refusal["authorized"] is False
    assert refusal["reason_code"] == "unknown-effect-setup-inconclusive"
    assert report["unknown_effect_baseline_valid"] is False
    assert report["unknown_effect_refusal_demonstrated"] is False
    assert report["reason_codes"] == ["unknown-effect-setup-inconclusive"]
    assert report["target_created"] is False


def test_stop_then_resume_v1_durability_failure_blocks_release_authorization(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    ledger.prepare(
        parent_identity={"session_id": "parent-session-durable"},
        pre_stop_history={"watermark": 37},
    )
    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": [],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )

    def fail_sync(_path):
        raise RuntimeError("durable directory sync failed")

    ledger._sync_directory = fail_sync
    with pytest.raises(RuntimeError, match="durable directory sync failed"):
        ledger.request_release(explicit=True)

    assert ledger.snapshot()["release_authorized"] is False
    assert ledger.snapshot()["target_creation_authorized"] is False


def test_stop_then_resume_v1_launch_intent_enters_starting_before_target_facts(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    ledger.prepare(
        parent_identity={"session_id": "parent-session-order"},
        pre_stop_history={"watermark": 41},
    )
    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": [],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )
    assert ledger.request_release(explicit=True)["authorized"] is True
    assert ledger.record_launch_intent()["phase"] == "target-starting"
    assert ledger.snapshot()["target_created"] is False


def test_stop_then_resume_v1_startup_activity_is_sticky_but_init_setup_is_allowed():
    runtime = {
        "init_request": "target-init",
        "startup_observation_active": True,
        "startup_activity_observed": False,
        "startup_activity_kinds": [],
        "startup_unclassified_lifecycle_count": 0,
    }

    PROBE["_observe_v1_startup_frame"](
        {
            "type": "control_response",
            "response": {"request_id": "target-init", "subtype": "success"},
        },
        runtime,
    )
    assert runtime["startup_activity_observed"] is False

    PROBE["_observe_v1_startup_frame"](
        {"type": "assistant", "message": {"role": "assistant"}},
        runtime,
    )
    PROBE["_observe_v1_startup_frame"](
        {"type": "system", "subtype": "task_notification", "status": "completed"},
        runtime,
    )

    assert runtime["startup_activity_observed"] is True
    assert runtime["startup_activity_kinds"] == ["assistant"]


def test_stop_then_resume_v1_truncated_observation_blocks_source_and_query_gates(tmp_path):
    ledger = PROBE["StopThenResumeV1Ledger"](tmp_path / "workspace")
    ledger.prepare(
        parent_identity={"session_id": "parent-session-truncated"},
        pre_stop_history={"watermark": 43},
    )
    ledger.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": ["injected-unknown-effect"],
            "read_failed": True,
            "unparsed_frames": 0,
            "protocol_errors": [],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": True,
        },
    )
    refusal = ledger.request_release(explicit=True)
    query_gate = PROBE["assess_v1_history_query_gate"](
        _v1_history_gate_observation(reader_error=True)
    )

    assert ledger.snapshot()["ready_to_resume"] is False
    assert refusal["reason_code"] == "unknown-effect-setup-inconclusive"
    assert ledger.report()["unknown_effect_baseline_valid"] is False
    assert query_gate["history_query_allowed"] is False
    assert "startup-reader-error" in query_gate["reason_codes"]


def test_stop_then_resume_v1_native_task_evidence_is_sanitized_and_correlated():
    event = {
        "type": "system",
        "subtype": "task_notification",
        "task_type": "local_agent",
        "status": "completed",
        "session_id": "session-secret",
        "task_id": "task-secret",
        "uuid": "event-secret",
        "tool_use_id": "tool-secret",
        "agent_id": "agent-secret",
        "body": "private transcript body",
        "path": "/private/history/path",
    }

    evidence = PROBE["sanitize_native_task_lifecycle_event"](
        event,
        phase="target/startup",
        observation_sequence=12,
        source_identity={
            "session_id": "session-secret",
            "task_id": "task-secret",
            "agent_id": "agent-secret",
        },
        prior_event=dict(event),
    )

    assert evidence["phase"] == "target/startup"
    assert evidence["observation_sequence"] == 12
    assert evidence["event_type"] == "system"
    assert evidence["event_subtype"] == "task_notification"
    assert evidence["task_type"] == "local_agent"
    assert evidence["status"] == "completed"
    assert evidence["session_id_seen"] is True
    assert evidence["task_id_seen"] is True
    assert evidence["event_uuid_seen"] is True
    assert evidence["tool_use_id_seen"] is True
    assert evidence["agent_id_seen"] is True
    assert evidence["source_target_correlation"] == {
        "session_id": "match",
        "task_id": "match",
        "tool_use_id": "unknown",
        "agent_id": "match",
    }
    assert evidence["correlation_class"] == "replay-compatible"
    assert evidence["support_claim"] is False
    assert evidence["task_id_digest"] == hashlib.sha256(
        b"task-secret"
    ).hexdigest()
    assert evidence["agent_id_digest"] == hashlib.sha256(
        b"agent-secret"
    ).hexdigest()

    encoded = json.dumps(evidence, sort_keys=True)
    assert "session-secret" not in encoded
    assert "task-secret" not in encoded
    assert "event-secret" not in encoded
    assert "tool-secret" not in encoded
    assert "agent-secret" not in encoded
    assert "private transcript body" not in encoded
    assert "/private/history/path" not in encoded


def test_stop_then_resume_v1_native_task_evidence_marks_unresolved_join_without_proof():
    evidence = PROBE["sanitize_native_task_lifecycle_event"](
        {
            "type": "system",
            "subtype": "task_progress",
            "task_type": "local_agent",
            "status": "running",
            "task_id": "new-task",
        },
        phase="source/drain",
        observation_sequence=4,
        source_identity={"task_id": "old-task"},
    )

    assert evidence["source_target_correlation"]["task_id"] == "mismatch"
    assert evidence["correlation_class"] == "live-or-unresolved"
    assert evidence["incomplete"] is True
    assert evidence["agent_id_seen"] is False
    assert evidence["agent_id_digest"] is None
    assert evidence["event_uuid_seen"] is False
    assert evidence["event_uuid_digest"] is None
    assert evidence["support_claim"] is False


def test_stop_then_resume_v1_terminal_correlation_rejects_conflicting_tool_join():
    event = {
        "type": "system",
        "subtype": "task_notification",
        "task_type": "local_agent",
        "status": "completed",
        "session_id": "session-secret",
        "task_id": "task-secret",
        "uuid": "event-secret",
        "tool_use_id": "tool-new",
    }
    evidence = PROBE["sanitize_native_task_lifecycle_event"](
        event,
        phase="target/startup",
        observation_sequence=3,
        source_identity={
            "session_id": "session-secret",
            "task_id": "task-secret",
        },
        prior_event=dict(event, tool_use_id="tool-old"),
    )

    assert evidence["correlation_class"] == "live-or-unresolved"
    assert evidence["incomplete"] is True
    assert "identity-conflict" not in evidence["unknown_fields"]
    assert evidence["support_claim"] is False


def test_stop_then_resume_v1_malformed_terminal_cannot_be_replay_compatible():
    evidence = PROBE["sanitize_native_task_lifecycle_event"](
        {
            "type": "system",
            "subtype": "task_notification",
            "task_type": "local_agent",
            "status": "completed",
            "session_id": "session-secret",
            "task_id": {"not": "an-id"},
            "uuid": "event-secret",
        },
        phase="target/startup",
        observation_sequence=4,
        prior_event={
            "type": "system",
            "subtype": "task_notification",
            "task_type": "local_agent",
            "status": "completed",
            "session_id": "session-secret",
            "task_id": "task-secret",
            "uuid": "event-secret",
        },
    )

    assert evidence["correlation_class"] == "live-or-unresolved"
    assert evidence["incomplete"] is True
    assert "malformed-identity" in evidence["unknown_fields"]
    assert evidence["support_claim"] is False


def test_stop_then_resume_v1_conflicting_envelope_fields_are_unresolved():
    evidence = PROBE["sanitize_native_task_lifecycle_event"](
        {
            "type": "system",
            "subtype": "task_notification",
            "response": {"subtype": "task_progress"},
            "task_type": "local_agent",
            "status": "completed",
            "session_id": "session-secret",
            "task_id": "task-secret",
            "uuid": "event-secret",
        },
        phase="source/drain",
        observation_sequence=5,
        prior_event={
            "type": "system",
            "subtype": "task_notification",
            "task_type": "local_agent",
            "status": "completed",
            "session_id": "session-secret",
            "task_id": "task-secret",
            "uuid": "event-secret",
        },
    )

    assert evidence["incomplete"] is True
    assert "conflicting-event-subtype" in evidence["unknown_fields"]
    assert evidence["correlation_class"] == "live-or-unresolved"


def test_stop_then_resume_v1_history_integrity_reports_bounded_parent_child_prefixes():
    result = PROBE["compare_history_content_integrity"](
        {
            "parent": b"parent-history-before\n",
            "child": b"child-history-before\n",
        },
        {
            "parent": b"parent-history-before\nappend-after-startup\n",
            "child": b"child-history-before\n",
        },
        before_boundary="source-excluded/pre-release",
        after_boundary="post-startup-before-cleanup",
    )

    assert result["observation_status"] == "observed"
    assert result["before_boundary"] == "source-excluded/pre-release"
    assert result["after_boundary"] == "post-startup-before-cleanup"
    assert result["support_claim"] is False
    assert result["runtime_loaded_or_restored"] == "unverified"
    assert result["roles"]["parent"]["content_integrity"] == "changed"
    assert result["roles"]["parent"]["prefix_integrity"] == "preserved"
    assert result["roles"]["child"]["content_integrity"] == "preserved"
    assert result["roles"]["child"]["prefix_integrity"] == "preserved"

    encoded = json.dumps(result, sort_keys=True)
    assert "parent-history-before" not in encoded
    assert "child-history-before" not in encoded
    assert "append-after-startup" not in encoded
    assert "/private/history/path" not in encoded


@pytest.mark.parametrize(
    "before, after, reason",
    [
        (
            {"parent": b"parent-only"},
            {"parent": b"parent-only"},
            "missing-child",
        ),
        (
            {"parent": b"123456789", "child": b"child"},
            {"parent": b"123456789", "child": b"child"},
            "oversized",
        ),
    ],
)
def test_stop_then_resume_v1_history_integrity_fails_closed_for_unknown_records(
    before, after, reason
):
    kwargs = {"max_bytes": 8} if reason == "oversized" else {}
    result = PROBE["compare_history_content_integrity"](
        before,
        after,
        **kwargs,
    )

    assert result["observation_status"] == "unknown"
    assert result["support_claim"] is False
    assert result["runtime_loaded_or_restored"] == "unverified"
    assert reason in result["unknown_reasons"]


def test_stop_then_resume_v1_native_task_recorder_attaches_report_and_bounds_overflow():
    runtime = {
        "frames_seen": 0,
        "unparsed_frames": 0,
        "native_task_events": 0,
        "startup_observation_active": True,
        "startup_activity_observed": False,
        "startup_activity_kinds": [],
        "startup_unclassified_lifecycle_count": 0,
        "lifecycle_phase": "target/startup",
        "source_identity": {
            "session_id": "session-secret",
            "task_id": "task-secret",
            "agent_id": "agent-secret",
        },
        "native_task_evidence_limit": 1,
    }
    first = {
        "type": "system",
        "subtype": "task_notification",
        "task_type": "local_agent",
        "status": "completed",
        "session_id": "session-secret",
        "task_id": "task-secret",
        "uuid": "event-secret",
        "agent_id": "agent-secret",
    }

    PROBE["observe_frame"](first, runtime)
    PROBE["observe_frame"](dict(first, uuid="event-secret-2"), runtime)
    report = PROBE["native_task_lifecycle_report"](runtime)

    assert report["event_count"] == 1
    assert report["overflow"] is True
    assert report["observation_status"] == "unknown"
    assert "native-task-evidence-overflow" in report["unknown_reasons"]
    assert report["events"][0]["phase"] == "target/startup"
    assert report["events"][0]["observation_sequence"] == 1
    assert report["support_claim"] is False


def test_stop_then_resume_v1_native_task_recorder_marks_malformed_identity_incomplete():
    runtime = {
        "frames_seen": 0,
        "unparsed_frames": 0,
        "native_task_events": 0,
        "lifecycle_phase": "source/drain",
        "native_task_evidence": [],
        "native_task_evidence_limit": 4,
    }

    PROBE["observe_frame"](
        {
            "type": "system",
            "subtype": "task_progress",
            "task_type": "local_agent",
            "status": "running",
            "task_id": {"raw": "not-an-identity"},
            "uuid": ["malformed"],
        },
        runtime,
    )
    report = PROBE["native_task_lifecycle_report"](runtime)

    assert report["observation_status"] == "unknown"
    assert report["incomplete"] is True
    assert "malformed-identity" in report["unknown_reasons"]
    assert report["support_claim"] is False


def _native_lifecycle_runtime(*, phase, provenance, seed=None):
    return {
        "frames_seen": 0,
        "unparsed_frames": 0,
        "native_task_events": 0,
        "lifecycle_phase": phase,
        "native_task_evidence": [],
        "native_task_evidence_limit": 8,
        "native_task_evidence_overflow": False,
        "native_task_observation_sequence": 0,
        "native_task_last_observation": None,
        "native_task_source_terminal_seed": seed,
        "native_task_source_terminal_index": (
            seed.get("observation_sequence")
            if isinstance(seed, dict)
            else None
        ),
        "native_task_evidence_unknown_reasons": [],
        "native_task_recording_enabled": True,
        "lifecycle_provenance": provenance,
        "source_identity": {
            "session_id": "session-source",
            "task_id": "task-source",
            "agent_id": "agent-source",
        },
        "control_events": {},
        "session_id": None,
        "initialize_succeeded": False,
        "task_started": False,
        "actual_task_id": None,
        "task_agent_id": None,
        "task_terminal_observed": False,
        "stopped_notification": False,
        "tool_terminal": False,
        "source_parent_result_seen": False,
        "source_parent_result_origin": None,
        "successful_result_seen": False,
        "successful_result_session_id": None,
        "successful_result_uuid_digest": None,
    }


def test_two_domain_startup_lifecycle_snapshot_is_sanitized_and_pre_query():
    target = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed"
    )
    target["native_task_seed_provenance"] = "unavailable"
    first = {
        "type": "system",
        "subtype": "task_progress",
        "task_type": "local_agent",
        "status": "running",
        "session_id": "session-source",
        "task_id": "task-source",
        "agent_id": "agent-source",
        "uuid": "startup-event-private",
    }
    PROBE["observe_frame"](first, target)

    startup = PROBE["snapshot_native_task_lifecycle"](target)
    PROBE["observe_frame"](dict(first, uuid="history-query-event-private"), target)

    assert startup["seed_provenance"] == "unavailable"
    assert startup["event_count"] == 1
    assert startup["events"][0]["phase"] == "target/startup"
    assert startup["events"][0]["provenance"] == "target-observed"
    assert startup["events"][0]["event_subtype"] == "task_progress"
    assert startup["events"][0]["status"] == "running"
    assert startup["events"][0]["session_id_digest"] == hashlib.sha256(
        b"session-source"
    ).hexdigest()
    assert startup["events"][0]["task_id_seen"] is True
    assert startup["events"][0]["incomplete"] is False
    assert target["native_task_evidence"][-1]["event_uuid_digest"] != (
        startup["events"][0]["event_uuid_digest"]
    )
    assert "session-source" not in json.dumps(startup)
    assert "task-source" not in json.dumps(startup)
    assert "startup-event-private" not in json.dumps(startup)
    assert "history-query-event-private" not in json.dumps(startup)
    assert PROBE["native_task_lifecycle_report"](target)["event_count"] == 2

    gate = PROBE["assess_v1_history_query_gate"](
        _v1_history_gate_observation(native_task_events=startup["event_count"])
    )
    assert gate["history_query_allowed"] is False
    assert "startup-task-event-observed" in gate["reason_codes"]


def test_two_domain_startup_lifecycle_snapshot_keeps_missing_conflicting_identity_unknown():
    missing = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed"
    )
    missing["native_task_seed_provenance"] = "unavailable"
    PROBE["observe_frame"](
        {
            "type": "system", "subtype": "task_started",
            "task_type": "local_agent", "status": "started",
            "session_id": "session-source", "uuid": "missing-task-private",
        },
        missing,
    )
    missing_snapshot = PROBE["snapshot_native_task_lifecycle"](missing)
    missing_event = missing_snapshot["events"][0]
    assert missing_event["task_id_seen"] is False
    assert missing_event["task_id_digest"] is None
    assert missing_event["source_target_correlation"]["task_id"] == "unknown"
    assert missing_snapshot["seed_provenance"] == "unavailable"

    conflicting = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed"
    )
    conflicting["native_task_seed_provenance"] = "unavailable"
    PROBE["observe_frame"](
        {
            "type": "system", "subtype": "task_notification",
            "task_type": "local_agent", "status": "completed",
            "session_id": "session-source", "task_id": "different-task",
            "agent_id": "agent-source", "uuid": "conflict-private",
        },
        conflicting,
    )
    conflict_snapshot = PROBE["snapshot_native_task_lifecycle"](conflicting)
    assert conflict_snapshot["observation_status"] == "unknown"
    assert conflict_snapshot["incomplete"] is True
    assert "identity-conflict" in conflict_snapshot["unknown_reasons"]
    assert "different-task" not in json.dumps(conflict_snapshot)


def test_two_domain_startup_lifecycle_snapshot_preserves_overflow():
    target = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed"
    )
    target["native_task_seed_provenance"] = "unavailable"
    target["native_task_evidence_limit"] = 1
    event = {
        "type": "system", "subtype": "task_progress",
        "task_type": "local_agent", "status": "running",
        "session_id": "session-source", "task_id": "task-source",
        "agent_id": "agent-source", "uuid": "overflow-private",
    }
    PROBE["observe_frame"](event, target)
    PROBE["observe_frame"](dict(event, uuid="overflow-second-private"), target)

    snapshot = PROBE["snapshot_native_task_lifecycle"](target)

    assert snapshot["observation_status"] == "unknown"
    assert snapshot["overflow"] is True
    assert "native-task-evidence-overflow" in snapshot["unknown_reasons"]
    assert snapshot["event_count"] == 1
    assert "overflow-private" not in json.dumps(snapshot)
    assert "overflow-second-private" not in json.dumps(snapshot)


def test_stop_then_resume_v1_source_terminal_seed_survives_target_observations():
    source = _native_lifecycle_runtime(
        phase="source/setup", provenance="source-observed"
    )
    PROBE["observe_frame"](
        {
            "type": "system",
            "subtype": "task_started",
            "task_type": "local_agent",
            "status": "started",
            "session_id": "session-source",
            "task_id": "task-source",
            "agent_id": "agent-source",
            "uuid": "source-started",
        },
        source,
    )
    source["lifecycle_phase"] = "source/drain"
    PROBE["observe_frame"](
        {
            "type": "system",
            "subtype": "task_notification",
            "status": "completed",
            "session_id": "session-source",
            "task_id": "task-source",
            "agent_id": "agent-source",
            "uuid": "source-terminal",
        },
        source,
    )
    seed = PROBE["source_terminal_lifecycle_seed"](source)

    assert seed is not None
    assert seed["provenance"] == "source-terminal-seed"
    assert seed["incomplete"] is False

    target = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed", seed=seed
    )
    for event_uuid in ("target-first", "source-terminal"):
        PROBE["observe_frame"](
            {
                "type": "system",
                "subtype": "task_notification",
                "status": "completed",
                "session_id": "session-source",
                "task_id": "task-source",
                "agent_id": "agent-source",
                "uuid": event_uuid,
            },
            target,
        )

    classes = [
        event["correlation_class"]
        for event in target["native_task_evidence"]
    ]
    assert classes == ["terminal-correlation-only", "replay-compatible"]
    assert target["native_task_source_terminal_seed"] is seed
    assert target["native_task_last_observation"] is not seed


def test_stop_then_resume_v1_target_duplicates_without_source_seed_stay_unresolved():
    target = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed"
    )
    event = {
        "type": "system",
        "subtype": "task_notification",
        "status": "completed",
        "session_id": "session-source",
        "task_id": "task-source",
        "agent_id": "agent-source",
        "uuid": "duplicate-terminal",
    }
    PROBE["observe_frame"](event, target)
    PROBE["observe_frame"](dict(event), target)

    classes = [
        observed["correlation_class"]
        for observed in target["native_task_evidence"]
    ]
    assert classes == ["live-or-unresolved", "live-or-unresolved"]
    assert "replay-compatible" not in classes


def test_stop_then_resume_v1_history_integrity_keeps_child_candidate_unattributed():
    result = PROBE["compare_history_content_integrity"](
        {
            "parent": {
                "content": b"parent-history-before\n",
                "attribution": "observed",
            },
            "child": {
                "content": b"child-history-before\n",
                "attribution": "candidate",
            },
        },
        {
            "parent": {
                "content": b"parent-history-before\n",
                "attribution": "observed",
            },
            "child": {
                "content": b"child-history-before\n",
                "attribution": "candidate",
            },
        },
    )

    assert result["observation_status"] == "observed"
    assert result["roles"]["child"]["attribution"] == "candidate"
    assert result["roles"]["child"]["association"] == "unattributed"
    assert result["roles"]["child"]["prefix_integrity"] == "preserved"
    assert result["roles"]["parent"]["before_digest"] == hashlib.sha256(
        b"parent-history-before\n"
    ).hexdigest()
    assert result["support_claim"] is False


def test_stop_then_resume_v1_history_capture_rejects_symlink_escape(tmp_path):
    root = tmp_path / "history"
    root.mkdir()
    (root / "parent.history").write_bytes(b"parent-history-before\n")
    outside = tmp_path / "outside.history"
    outside.write_bytes(b"outside-history\n")
    try:
        (root / "child.history").symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    captured = PROBE["capture_bounded_history_records"](
        root,
        parent_path="parent.history",
        child_path="child.history",
    )
    result = PROBE["compare_history_content_integrity"](captured, captured)

    assert result["observation_status"] == "unknown"
    assert "symlink" in result["unknown_reasons"]
    assert str(root) not in json.dumps(result, sort_keys=True)


def test_stop_then_resume_v1_history_capture_discovers_source_linked_records(tmp_path):
    root = tmp_path / "config"
    session_id = "session-auto"
    project_dir = root / "projects" / "sanitized-cwd"
    session_dir = project_dir / session_id / "subagents"
    session_dir.mkdir(parents=True)
    (project_dir / (session_id + ".jsonl")).write_bytes(
        json.dumps({"sessionId": session_id, "record": "parent"}).encode()
    )
    (session_dir / "agent-agent-auto.jsonl").write_bytes(
        json.dumps(
            {
                "sessionId": session_id,
                "status": "completed",
            }
        ).encode()
    )
    (session_dir / "agent-agent-auto.meta.json").write_bytes(
        json.dumps({"toolUseId": "tool-auto"}).encode()
    )

    captured = PROBE["capture_runtime_history_records"](
        root,
        source_identity={
            "session_id": session_id,
            "task_id": "task-auto",
            "agent_id": "agent-auto",
            "tool_use_id": "tool-auto",
        },
    )
    result = PROBE["compare_history_content_integrity"](captured, captured)

    assert captured["parent"]["status"] == "observed"
    assert captured["child"]["status"] == "observed"
    assert captured["child"]["attribution"] == "observed"
    assert result["observation_status"] == "observed"
    assert result["roles"]["child"]["association"] == "observed-link"
    assert result["support_claim"] is False


def test_stop_then_resume_v1_history_discovery_uses_top_level_schema_only(tmp_path):
    root = tmp_path / "config"
    session_id = "session-schema"
    project_dir = root / "projects" / "sanitized-cwd"
    session_dir = project_dir / session_id / "subagents"
    session_dir.mkdir(parents=True)
    (project_dir / (session_id + ".jsonl")).write_bytes(
        json.dumps({"message": {"sessionId": session_id}}).encode()
    )
    (session_dir / "agent-agent-schema.jsonl").write_bytes(b"child\n")
    (session_dir / "agent-agent-schema.meta.json").write_bytes(
        json.dumps({"tool_use_id": "not-the-sdk-field"}).encode()
    )

    captured = PROBE["capture_runtime_history_records"](
        root,
        source_identity={
            "session_id": session_id,
            "agent_id": "agent-schema",
        },
    )
    result = PROBE["compare_history_content_integrity"](captured, captured)

    assert captured["parent"]["status"] == "observed"
    assert captured["parent"]["attribution"] == "candidate"
    assert captured["child"]["status"] == "observed"
    assert captured["child"]["attribution"] == "candidate"
    assert result["roles"]["parent"]["association"] == "unattributed"
    assert result["roles"]["child"]["association"] == "unattributed"
    assert result["support_claim"] is False


def test_stop_then_resume_v1_sidecar_link_requires_known_native_join():
    assert not PROBE["_history_sidecar_link"](
        json.dumps({"toolUseId": "tool-auto"}).encode(),
        {"session_id": "session-auto", "agent_id": "agent-auto"},
    )


def test_stop_then_resume_v1_sidecar_link_accepts_exact_known_join():
    assert PROBE["_history_sidecar_link"](
        json.dumps(
            {
                "toolUseId": "tool-auto",
                "parentAgentId": "agent-parent",
            }
        ).encode(),
        {
            "session_id": "session-auto",
            "tool_use_id": "tool-auto",
            "parent_agent_id": "agent-parent",
        },
    )


def test_stop_then_resume_v1_sidecar_link_rejects_known_join_conflict():
    assert not PROBE["_history_sidecar_link"](
        json.dumps(
            {
                "toolUseId": "tool-auto",
                "parentAgentId": "agent-other",
            }
        ).encode(),
        {
            "session_id": "session-auto",
            "tool_use_id": "tool-auto",
            "parent_agent_id": "agent-parent",
        },
    )


def test_stop_then_resume_v1_history_discovery_bounds_directory_entries(
    tmp_path, monkeypatch
):
    root = tmp_path / "config"
    child_root = root / "projects" / "sanitized-cwd" / "session-overflow" / "subagents"
    child_root.mkdir(parents=True)
    monkeypatch.setitem(
        PROBE["capture_runtime_history_records"].__globals__,
        "MAX_HISTORY_SCAN_ENTRIES",
        1,
    )
    (child_root / "first").write_bytes(b"one")
    (child_root / "second").write_bytes(b"two")

    captured = PROBE["capture_runtime_history_records"](
        root,
        source_identity={"session_id": "session-overflow"},
    )

    assert captured["parent"]["status"] == "unknown"
    assert captured["child"]["status"] == "unknown"
    assert captured["parent"]["reason"] == "scan-overflow"
    assert captured["child"]["reason"] == "scan-overflow"


def test_stop_then_resume_v1_history_capture_refuses_fifo_without_blocking(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation is unavailable")
    root = tmp_path / "history"
    root.mkdir()
    fifo = root / "history.fifo"
    os.mkfifo(fifo)

    captured = PROBE["capture_bounded_history_records"](
        root,
        parent_path="history.fifo",
    )

    assert captured["parent"]["status"] == "unknown"
    assert captured["parent"]["reason"] == "not-regular"


def test_stop_then_resume_v1_history_capture_fails_closed_without_nofollow(
    tmp_path, monkeypatch
):
    root = tmp_path / "history"
    root.mkdir()
    (root / "parent.history").write_bytes(b"parent")
    monkeypatch.delattr(PROBE["os"], "O_NOFOLLOW", raising=False)

    captured = PROBE["capture_bounded_history_records"](
        root,
        parent_path="parent.history",
    )

    assert captured["parent"]["status"] == "unknown"
    assert captured["parent"]["reason"] == "no-follow-unavailable"


def test_stop_then_resume_v1_history_capture_bounds_bytes_and_reports_raw_digest(tmp_path):
    root = tmp_path / "history"
    root.mkdir()
    (root / "parent.history").write_bytes(b"123456789")
    (root / "child.history").write_bytes(b"child")

    oversized = PROBE["capture_bounded_history_records"](
        root,
        parent_path="parent.history",
        child_path="child.history",
        max_bytes=8,
    )
    oversized_result = PROBE["compare_history_content_integrity"](
        oversized, oversized, max_bytes=8
    )
    assert oversized_result["observation_status"] == "unknown"
    assert "oversized" in oversized_result["unknown_reasons"]

    (root / "parent.history").write_bytes(b"1234")
    bounded = PROBE["capture_bounded_history_records"](
        root,
        parent_path="parent.history",
        child_path="child.history",
        max_bytes=8,
    )
    bounded_result = PROBE["compare_history_content_integrity"](
        bounded, bounded, max_bytes=8
    )
    assert bounded_result["roles"]["parent"]["before_digest"] == hashlib.sha256(
        b"1234"
    ).hexdigest()


def test_stop_then_resume_v1_native_raw_identity_fields_are_not_authoritative():
    evidence = PROBE["sanitize_native_task_lifecycle_event"](
        {
            "type": "system",
            "subtype": "task_notification",
            "task_type": "local_agent",
            "status": "completed",
            "record_schema": "native-task-observation-v1",
            "session_id_seen": True,
            "session_id_digest": hashlib.sha256(b"forged-session").hexdigest(),
            "task_id_seen": True,
            "task_id_digest": hashlib.sha256(b"forged-task").hexdigest(),
            "uuid_seen": True,
            "uuid_digest": hashlib.sha256(b"forged-event").hexdigest(),
            "body": {
                "session_id": "nested-session",
                "task_id": "nested-task",
            },
        },
        phase="source/drain",
        observation_sequence=1,
    )

    assert evidence["session_id_seen"] is False
    assert evidence["task_id_seen"] is False
    assert evidence["event_uuid_seen"] is False
    assert evidence["correlation_class"] == "live-or-unresolved"


def _native_hook_runtime():
    return {
        "session_id": "session-current",
        "invocation_id": "invocation-current",
        "actual_task_id": "task-current",
        "task_tool_use_id": "tool-current",
        "native_agent_type": "native-worker",
        "native_hook_recording_enabled": True,
        "native_hook_evidence": [],
        "native_hook_evidence_limit": 4,
        "native_hook_unknown_reasons": [],
        "native_hook_evidence_overflow": False,
        "task_terminal_observed": False,
        "stopped_notification": False,
        "tool_terminal": False,
        "source_parent_result_seen": False,
        "successful_result_seen": False,
        "support_claim": False,
    }


def _native_hook_request(
    request_id, callback_id, input_value, *, tool_use_id="tool-current"
):
    return {
        "type": "control_request",
        "request_id": request_id,
        "request": {
            "subtype": "hook_callback",
            "callback_id": callback_id,
            "input": input_value,
            "tool_use_id": tool_use_id,
        },
    }


def _native_source_terminal_seed_envelope(
    *, parent="session-source", invocation="source-invocation-private",
    terminal_subtype="task_notification", terminal_status="completed",
    terminal_top_status=None,
    include_direct_agent=False, include_hook=True, early_hook=False,
    hook_agent="agent-source-private", hook_tool="tool-source-private",
    hook_session=None, expect_hook_success=True, second_hook_agent=None,
    second_hook_tool=None,
    join_after_early_hook=False, task_evidence_limit=None,
    hook_evidence_limit=4, start_task_type="local_agent",
    terminal_tool_use_id=None, terminal_agent_id=None,
    history_root=None, hook_event="SubagentStart", hook_transcript_path=None,
    hook_input_tool_id=None,
):
    runtime = _native_lifecycle_runtime(
        phase="source/drain", provenance="source-observed"
    )
    # Source records precede any target and must not claim source-target
    # correlation, even though the generic test runtime has a target fixture
    # identity preloaded.
    runtime["source_identity"] = None
    runtime.update({
        "session_id": parent,
        "actual_task_id": "task-source-private",
        "task_agent_id": (
            "agent-source-private" if include_direct_agent else None
        ),
        "task_tool_use_id": "tool-source-private",
        "native_agent_type": "gate0-worker",
        "native_hook_recording_enabled": True,
        "native_hook_evidence": [],
        "native_hook_evidence_limit": hook_evidence_limit,
        "native_hook_unknown_reasons": [],
        "native_hook_evidence_overflow": False,
        "native_hook_request_overflow": False,
        "native_hook_request_fingerprints": {},
    })
    if task_evidence_limit is not None:
        runtime["native_task_evidence_limit"] = task_evidence_limit
    selected_hook_session = hook_session or parent
    hook_input = {
        "hook_event_name": hook_event,
        "session_id": selected_hook_session,
        "transcript_path": "/private/coordinator.jsonl",
        "cwd": "/private/work",
        "agent_id": hook_agent,
        "agent_type": "gate0-worker",
    }
    if hook_event == "SubagentStop":
        hook_input["agent_transcript_path"] = hook_transcript_path or (
            "/private/config/projects/project-session/session-source/subagents/"
            "agent-%s.jsonl" % hook_agent
        )
        hook_input["stop_hook_active"] = False
    if early_hook and hook_tool is not None:
        hook_input["tool_use_id"] = hook_tool
    if hook_input_tool_id is not None:
        hook_input["tool_use_id"] = hook_input_tool_id
    if early_hook:
        runtime["actual_task_id"] = None
        runtime["task_tool_use_id"] = None
    if include_hook and early_hook:
        callback = _native_hook_request(
            "hook-source-early",
            PROBE["NATIVE_HOOK_CALLBACK_IDS"][hook_event],
            hook_input,
            tool_use_id=None,
        )
        expected = "success" if expect_hook_success else "error"
        assert PROBE["handle_native_hook_callback"](callback, runtime)[
            "response"
        ]["subtype"] == expected
    runtime["lifecycle_phase"] = "source/setup"
    started = {
        "type": "system",
        "subtype": "task_started",
        "task_type": start_task_type,
        "task_id": "task-source-private",
        "session_id": parent,
        "tool_use_id": "tool-source-private",
        "uuid": "event-source-private",
    }
    if include_direct_agent:
        # Exercise the SDK extension field only in the direct-agent proof test.
        started["agent_id"] = "agent-source-private"
    PROBE["observe_frame"](started, runtime)
    runtime["lifecycle_phase"] = "source/drain"
    if include_hook and (not early_hook or join_after_early_hook):
        callback = _native_hook_request(
            "hook-source-after-start",
            PROBE["NATIVE_HOOK_CALLBACK_IDS"][hook_event],
            hook_input,
            tool_use_id=hook_tool,
        )
        expected = "success" if expect_hook_success else "error"
        assert PROBE["handle_native_hook_callback"](callback, runtime)[
            "response"
        ]["subtype"] == expected
    if include_hook and second_hook_agent is not None:
        second_input = dict(hook_input, agent_id=second_hook_agent)
        callback = _native_hook_request(
            "hook-source-second-agent",
            "native-subagent-start",
            second_input,
            tool_use_id=(
                hook_tool if second_hook_tool is None else second_hook_tool
            ),
        )
        assert PROBE["handle_native_hook_callback"](callback, runtime)[
            "response"
        ]["subtype"] == "success"
    if terminal_subtype == "task_notification":
        terminal = {
            "type": "system",
            "subtype": terminal_subtype,
            "status": terminal_status,
            "session_id": parent,
            "task_id": "task-source-private",
            "uuid": "event-terminal-private",
        }
        if terminal_tool_use_id is not None:
            terminal["tool_use_id"] = terminal_tool_use_id
        if terminal_agent_id is not None:
            terminal["agent_id"] = terminal_agent_id
    else:
        terminal = {
            "type": "system",
            "subtype": terminal_subtype,
            "task_id": "task-source-private",
            "data": {
                "patch": {"status": terminal_status},
                "uuid": "event-terminal-private",
            },
        }
        if terminal_top_status is not None:
            terminal["status"] = terminal_top_status
        if terminal_tool_use_id is not None:
            terminal["tool_use_id"] = terminal_tool_use_id
        if terminal_agent_id is not None:
            terminal["agent_id"] = terminal_agent_id
    PROBE["observe_frame"](terminal, runtime)
    bridge_record = None
    bridge_diagnostic = {"status": None}
    if history_root is not None:
        bridge_record, bridge_diagnostic = PROBE[
            "native_hook_sdk_sidecar_bridge"
        ](history_root, runtime)
        runtime["native_hook_sdk_sidecar_diagnostic"] = bridge_diagnostic
    envelope = PROBE["native_task_source_terminal_seed_envelope"](
        runtime,
        parent_uuid=parent,
        source_invocation=invocation,
        sdk_sidecar_record=bridge_record,
        sdk_sidecar_reason=bridge_diagnostic.get("status"),
    )
    return runtime, envelope


def _write_sdk_sidecar_history(
    root,
    *,
    parent="session-source",
    agent="agent-source-private",
    tool="tool-source-private",
    child_records=None,
    parent_records=None,
    parent_agent_id=None,
    sidecar_bytes=None,
    child_subdirectory=None,
):
    project = root / "projects" / "project-session"
    session_dir = project / parent
    subagents = session_dir / "subagents"
    if child_subdirectory:
        subagents = subagents / child_subdirectory
    subagents.mkdir(parents=True)
    parent_records = parent_records or [{"sessionId": parent}]
    child_records = child_records or [
        {"sessionId": parent, "agentId": agent, "type": "assistant"}
    ]
    (project / (parent + ".jsonl")).write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n"
                for record in parent_records),
        encoding="utf-8",
    )
    child_path = subagents / ("agent-%s.jsonl" % agent)
    child_path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n"
                for record in child_records),
        encoding="utf-8",
    )
    sidecar_path = subagents / ("agent-%s.meta.json" % agent)
    sidecar_path.write_bytes(
        sidecar_bytes if sidecar_bytes is not None else json.dumps(
            {"toolUseId": tool, **(
                {"parentAgentId": parent_agent_id}
                if parent_agent_id is not None else {}
            )},
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return child_path, sidecar_path


def _rehash_native_source_seed(envelope):
    core = {key: value for key, value in envelope.items() if key != "seed_digest"}
    envelope["seed_digest"] = hashlib.sha256(
        PROBE["_canonical_json"](core)
    ).hexdigest()
    return envelope


def test_two_domain_native_source_terminal_seed_envelope_is_bounded_bound_and_digest_only():
    runtime, envelope = _native_source_terminal_seed_envelope()
    validated = PROBE["validate_native_task_source_terminal_seed_envelope"](
        envelope,
        expected_parent_uuid_digest=hashlib.sha256(b"session-source").hexdigest(),
        expected_source_invocation_digest=hashlib.sha256(
            b"source-invocation-private"
        ).hexdigest(),
    )
    assert envelope["status"] == "available"
    assert envelope["seed_digest"] == validated["seed_digest"]
    assert envelope["terminal_event"]["status"] == "completed"
    assert envelope["terminal_event"]["task_type"] is None
    assert envelope["terminal_event"]["agent_id_seen"] is False
    assert envelope["task_started_event"]["status"] is None
    assert envelope["agent_proof"]["provenance"] == "native_hook"
    assert envelope["source_identity_digests"]["task_id_digest"] == hashlib.sha256(
        b"task-source-private"
    ).hexdigest()
    assert envelope["source_identity_digests"]["tool_use_id_digest"] == hashlib.sha256(
        b"tool-source-private"
    ).hexdigest()
    encoded = json.dumps(envelope, sort_keys=True)
    for raw in (
        "session-source", "task-source-private", "agent-source-private",
        "event-source-private",
    ):
        assert raw not in encoded
    assert runtime["native_task_evidence_overflow"] is False


def test_two_domain_native_source_seed_uses_setup_start_and_sdk_shaped_notification_without_invented_agent():
    runtime, envelope = _native_source_terminal_seed_envelope()

    assert envelope["status"] == "available"
    assert envelope["task_started_event"]["phase"] == "source/setup"
    assert envelope["terminal_event"]["phase"] == "source/drain"
    assert envelope["terminal_event"]["task_type"] is None
    assert envelope["terminal_event"]["agent_id_seen"] is False
    assert envelope["agent_proof"]["provenance"] == "native_hook"
    observed_terminal = dict(runtime["native_task_evidence"][-1])
    observed_terminal["provenance"] = "source-terminal-seed"
    assert envelope["terminal_event"] == observed_terminal
    assert runtime["native_task_evidence"][0]["phase"] == "source/setup"


def test_two_domain_native_source_seed_accepts_early_unresolved_hook_only_after_exact_join():
    runtime, envelope = _native_source_terminal_seed_envelope(early_hook=True)
    summary = PROBE["native_hook_evidence_summary"](runtime)

    assert envelope["status"] == "available"
    assert runtime["native_hook_evidence"][0]["join_status"] == "unresolved"
    assert runtime["native_hook_evidence"][0]["task_id_seen"] is False
    assert runtime["native_hook_evidence"][0]["tool_use_id_seen"] is True
    assert summary["started_task_event_count"] == 1
    assert summary["session_matched_hook_count"] == 1
    assert summary["same_task_hook_count"] == 0
    assert summary["exact_task_tool_link_candidate_count"] == 1


def test_two_domain_native_source_seed_merges_early_and_later_exact_same_agent_hooks():
    runtime, envelope = _native_source_terminal_seed_envelope(
        early_hook=True, join_after_early_hook=True,
    )
    summary = PROBE["native_hook_evidence_summary"](runtime)

    assert envelope["status"] == "available"
    assert [record["join_status"] for record in runtime["native_hook_evidence"]] == [
        "unresolved", "joined",
    ]
    assert summary["exact_task_tool_link_candidate_count"] == 2
    assert summary["same_task_hook_count"] == 1


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"task_evidence_limit": 1}, "terminal-task-seed-incomplete"),
        ({"hook_evidence_limit": 0}, "terminal-task-hook-evidence-incomplete"),
        ({"start_task_type": "unknown_task_type"}, "terminal-task-seed-incomplete"),
    ],
)
def test_two_domain_native_source_seed_fails_closed_on_evidence_overflow_or_invalid_start(
    kwargs, reason,
):
    _, envelope = _native_source_terminal_seed_envelope(**kwargs)

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == reason


def test_two_domain_native_source_seed_requires_started_proof_before_terminal():
    runtime, initial = _native_source_terminal_seed_envelope()
    assert initial["status"] == "available"
    started, terminal = runtime["native_task_evidence"]
    started["observation_sequence"] = terminal["observation_sequence"]

    envelope = PROBE["native_task_source_terminal_seed_envelope"](
        runtime,
        parent_uuid="session-source",
        source_invocation="source-invocation-private",
    )

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-start-proof-unavailable"


@pytest.mark.parametrize(
    ("terminal_tool_use_id", "terminal_agent_id"),
    [
        ("tool-other-private", None),
        (None, "agent-other-private"),
    ],
)
def test_two_domain_native_source_seed_rejects_terminal_identity_conflict_with_start_or_hook(
    terminal_tool_use_id, terminal_agent_id,
):
    _, envelope = _native_source_terminal_seed_envelope(
        terminal_tool_use_id=terminal_tool_use_id,
        terminal_agent_id=terminal_agent_id,
    )

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-seed-identity-unlinked"


def test_two_domain_native_source_hook_summary_distinguishes_missing_and_mismatched_tool_ids():
    missing_runtime, missing_envelope = _native_source_terminal_seed_envelope(
        hook_tool=None,
    )
    missing = PROBE["native_hook_evidence_summary"](missing_runtime)
    assert missing_envelope["status"] == "unavailable"
    assert missing["started_task_tool_use_id_seen"] is True
    assert missing["hook_tool_use_id_missing_count"] == 1
    assert missing["same_task_tool_use_id_missing_count"] == 0
    assert missing["same_task_hook_count"] == 0
    assert missing["exact_task_tool_link_candidate_count"] == 0

    mismatch_runtime, mismatch_envelope = _native_source_terminal_seed_envelope(
        hook_tool="tool-other-private",
    )
    mismatch = PROBE["native_hook_evidence_summary"](mismatch_runtime)
    assert mismatch_envelope["status"] == "unavailable"
    assert mismatch["rejected_tool_use_id_mismatch_count"] == 1
    assert "hook-tool-use-id-mismatch" not in mismatch["unknown_reasons"]
    assert mismatch_runtime["native_hook_evidence"][0]["join_status"] == "unresolved"
    assert mismatch_runtime["native_hook_evidence"][0]["task_id_seen"] is False
    assert mismatch_runtime["native_hook_evidence"][0]["tool_use_id_digest"] == (
        PROBE["digest"]("tool-other-private")
    )
    assert mismatch["mismatch_diagnostics"][0]["callback_tool_use_id_digest"] == (
        PROBE["digest"]("tool-other-private")
    )
    assert mismatch["mismatch_diagnostics"][0]["task_tool_use_id_digest"] == (
        PROBE["digest"]("tool-source-private")
    )
    for summary in (missing, mismatch):
        serialized = json.dumps(summary, sort_keys=True)
        for raw in (
            "tool-source-private", "tool-other-private", "session-source",
            "/private/coordinator.jsonl", "/private/work",
        ):
            assert raw not in serialized


def test_two_domain_native_source_seed_uses_sdk_sidecar_bridge_for_unresolved_tool_mismatch(
    tmp_path,
):
    _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
    )
    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_tool="tool-other-private",
        history_root=tmp_path,
    )

    validated = PROBE["validate_native_task_source_terminal_seed_envelope"](
        envelope,
        expected_parent_uuid_digest=PROBE["digest"]("session-source"),
        expected_source_invocation_digest=PROBE["digest"](
            "source-invocation-private"
        ),
    )
    proof = validated["agent_proof"]
    assert envelope["status"] == "available"
    assert proof["provenance"] == "sdk_sidecar"
    assert proof["hook_record"]["join_status"] == "unresolved"
    assert proof["hook_record"]["task_id_seen"] is False
    assert proof["hook_record"]["tool_use_id_digest"] == PROBE["digest"](
        "tool-other-private"
    )
    assert proof["sidecar_record"]["task_tool_use_id_digest"] == PROBE["digest"](
        "tool-source-private"
    )
    assert runtime["native_hook_unknown_reasons"] == []
    serialized = json.dumps(envelope, sort_keys=True)
    for raw in (
        "tool-source-private", "tool-other-private", "agent-source-private",
        str(tmp_path), "session-source",
    ):
        assert raw not in serialized


def test_two_domain_native_source_sdk_sidecar_bridge_fails_closed_when_missing(tmp_path):
    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_tool="tool-other-private",
        history_root=tmp_path,
    )

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-sdk-sidecar-evidence-incomplete"
    assert runtime["native_hook_sdk_sidecar_diagnostic"]["status"] == "missing"


def test_two_domain_native_source_sdk_sidecar_bridge_rejects_duplicate_agent_sidecar(
    tmp_path,
):
    _, sidecar = _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
    )
    nested = sidecar.parent / "nested"
    nested.mkdir()
    (nested / sidecar.name).write_text(
        json.dumps({"toolUseId": "tool-other-private"}), encoding="utf-8",
    )

    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_tool="tool-other-private",
        history_root=tmp_path,
    )

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-sdk-sidecar-evidence-conflict"
    assert runtime["native_hook_sdk_sidecar_diagnostic"]["reason"] == (
        "duplicate-sidecars-for-hook-agent"
    )


@pytest.mark.parametrize(
    "sidecar_problem",
    ["same-agent-conflict", "multiple-agent-match"],
)
def test_two_domain_native_source_seed_does_not_ignore_sidecar_conflict_for_exact_hook(
    tmp_path, sidecar_problem,
):
    _, sidecar = _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
    )
    nested = sidecar.parent / "nested"
    nested.mkdir()
    if sidecar_problem == "same-agent-conflict":
        (nested / sidecar.name).write_text(
            json.dumps({"toolUseId": "tool-other-private"}), encoding="utf-8",
        )
        expected_status = "conflict"
        expected_reason = "terminal-task-sdk-sidecar-evidence-conflict"
    else:
        (nested / "agent-other-private.meta.json").write_text(
            json.dumps({"toolUseId": "tool-source-private"}), encoding="utf-8",
        )
        expected_status = "ambiguous"
        expected_reason = "terminal-task-sdk-sidecar-evidence-ambiguous"

    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_tool="tool-source-private",
        second_hook_agent="agent-source-private",
        second_hook_tool="tool-other-private",
        history_root=tmp_path,
    )

    assert runtime["native_hook_evidence"][0]["join_status"] == "joined"
    assert runtime["native_hook_evidence"][1]["join_status"] == "unresolved"
    assert runtime["native_hook_sdk_sidecar_diagnostic"]["status"] == expected_status
    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == expected_reason


@pytest.mark.parametrize(
    "sidecar_bytes",
    [
        b'{"toolUseId":"tool-source-private","toolUseId":"tool-other-private"}',
        b'{"toolUseId":"tool-source-private","parentAgentId":"parent-agent"}',
        b'{"toolUseId":"tool-source-private","parentAgentId":null}',
    ],
)
def test_two_domain_native_source_sdk_sidecar_bridge_rejects_ambiguous_metadata(
    tmp_path, sidecar_bytes,
):
    _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
        sidecar_bytes=sidecar_bytes,
    )

    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_tool="tool-other-private",
        history_root=tmp_path,
    )

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] in {
        "terminal-task-sdk-sidecar-evidence-incomplete",
        "terminal-task-sdk-sidecar-evidence-conflict",
    }
    assert runtime["native_hook_sdk_sidecar_diagnostic"]["status"] in {
        "incomplete", "conflict",
    }


@pytest.mark.parametrize(
    "child_records",
    [
        [
            {"sessionId": "session-other", "agentId": "agent-source-private"},
            {"sessionId": "session-source", "agentId": "agent-source-private"},
        ],
        [
            {"sessionId": "session-source", "agentId": "agent-other"},
            {"sessionId": "session-source", "agentId": "agent-source-private"},
        ],
    ],
)
def test_two_domain_native_source_sdk_sidecar_bridge_rejects_child_identity_conflicts(
    tmp_path, child_records,
):
    _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
        child_records=child_records,
    )

    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_tool="tool-other-private",
        history_root=tmp_path,
    )

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-sdk-sidecar-evidence-conflict"
    assert runtime["native_hook_sdk_sidecar_diagnostic"]["reason"] == (
        "child-session-agent-conflict"
    )


def test_two_domain_native_source_sdk_sidecar_bridge_requires_exact_subagent_stop_path(
    tmp_path,
):
    child_path, _ = _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
    )
    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_event="SubagentStop",
        hook_tool="tool-other-private",
        hook_transcript_path=str(child_path),
        history_root=tmp_path,
    )
    assert envelope["status"] == "available"
    assert envelope["agent_proof"]["provenance"] == "sdk_sidecar"
    assert envelope["agent_proof"]["sidecar_record"][
        "child_transcript_path_digest"
    ] == PROBE["digest"](str(child_path))
    assert runtime["native_hook_evidence"][0]["agent_transcript_path_digest"] == (
        PROBE["digest"](str(child_path))
    )

    wrong_runtime, wrong_envelope = _native_source_terminal_seed_envelope(
        hook_event="SubagentStop",
        hook_tool="tool-other-private",
        hook_transcript_path=str(child_path) + ".other",
        history_root=tmp_path,
    )
    assert wrong_envelope["status"] == "unavailable"
    assert wrong_envelope["reason_code"] == (
        "terminal-task-sdk-sidecar-evidence-conflict"
    )
    assert wrong_runtime["native_hook_sdk_sidecar_diagnostic"]["reason"] == (
        "subagent-stop-path-conflict"
    )


@pytest.mark.parametrize("unsafe_kind", ["symlink", "hardlink", "nonregular", "oversize"])
def test_two_domain_native_source_sdk_sidecar_bridge_rejects_unsafe_scan_entries(
    tmp_path, unsafe_kind,
):
    _, sidecar = _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
    )
    if unsafe_kind == "symlink":
        outside = tmp_path / "outside.meta.json"
        outside.write_text(json.dumps({"toolUseId": "tool-other-private"}))
        sidecar.unlink()
        sidecar.symlink_to(outside)
    elif unsafe_kind == "hardlink":
        os.link(sidecar, sidecar.parent / "agent-hardlink.meta.json")
    elif unsafe_kind == "nonregular":
        os.mkfifo(sidecar.parent / "not-a-file")
    else:
        (sidecar.parent / "agent-large.meta.json").write_bytes(
            b"{" + b"a" * PROBE["MAX_HISTORY_CONTENT_BYTES"] + b"}"
        )

    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_tool="tool-other-private",
        history_root=tmp_path,
    )

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] in {
        "terminal-task-sdk-sidecar-evidence-incomplete",
        "terminal-task-sdk-sidecar-evidence-conflict",
    }
    assert runtime["native_hook_sdk_sidecar_diagnostic"]["status"] in {
        "incomplete", "conflict",
    }


@pytest.mark.parametrize(
    "limit_name,limit_value,child_subdirectory",
    [
        ("MAX_HISTORY_SCAN_ENTRIES", 1, None),
        ("MAX_HISTORY_SCAN_FILES", 1, None),
        ("MAX_HISTORY_SCAN_DEPTH", 0, "nested"),
        ("MAX_HISTORY_SCAN_BYTES", 1, None),
    ],
)
def test_two_domain_native_source_sdk_sidecar_bridge_enforces_scan_bounds(
    tmp_path, monkeypatch, limit_name, limit_value, child_subdirectory,
):
    _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
        child_subdirectory=child_subdirectory,
    )
    monkeypatch.setitem(
        PROBE["native_hook_sdk_sidecar_bridge"].__globals__,
        limit_name,
        limit_value,
    )

    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_tool="tool-other-private",
        history_root=tmp_path,
    )

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-sdk-sidecar-evidence-incomplete"
    assert runtime["native_hook_sdk_sidecar_diagnostic"]["status"] == "incomplete"


@pytest.mark.parametrize(
    "tamper",
    [
        "session", "agent", "tool", "parent-agent-seen", "parent-session",
        "child-session-agent", "count-bool", "scan-complete", "extra",
        "stop-child-path",
    ],
)
def test_two_domain_native_source_sdk_sidecar_proof_rejects_rehashed_tampering(
    tmp_path, tamper,
):
    child_path, _ = _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
    )
    _, envelope = _native_source_terminal_seed_envelope(
        hook_event="SubagentStop",
        hook_tool="tool-other-private",
        hook_transcript_path=str(child_path),
        history_root=tmp_path,
    )
    assert envelope["status"] == "available"
    candidate = json.loads(json.dumps(envelope))
    sidecar = candidate["agent_proof"]["sidecar_record"]
    if tamper == "session":
        sidecar["session_id_digest"] = "0" * 64
    elif tamper == "agent":
        sidecar["agent_id_digest"] = "0" * 64
    elif tamper == "tool":
        sidecar["task_tool_use_id_digest"] = "0" * 64
    elif tamper == "parent-agent-seen":
        sidecar["parent_agent_id_seen"] = True
    elif tamper == "parent-session":
        sidecar["parent_history_session_proven"] = False
    elif tamper == "child-session-agent":
        sidecar["child_history_session_agent_proven"] = False
    elif tamper == "count-bool":
        sidecar["matching_sidecar_count"] = True
    elif tamper == "scan-complete":
        sidecar["scan_complete"] = False
    elif tamper == "extra":
        sidecar["unbound"] = "extra"
    else:
        sidecar["child_transcript_path_digest"] = "0" * 64
    _rehash_native_source_seed(candidate)

    with pytest.raises(ValueError):
        PROBE["validate_native_task_source_terminal_seed_envelope"](
            candidate,
            expected_parent_uuid_digest=PROBE["digest"]("session-source"),
            expected_source_invocation_digest=PROBE["digest"](
                "source-invocation-private"
            ),
        )


def test_two_domain_native_source_seed_refuses_exact_and_sidecar_proofs_for_different_agents(
    tmp_path,
):
    _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-sidecar-private",
        tool="tool-source-private",
    )
    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_agent="agent-exact-private",
        hook_tool="tool-source-private",
        second_hook_agent="agent-sidecar-private",
        second_hook_tool="tool-other-private",
        history_root=tmp_path,
    )

    assert len(runtime["native_hook_evidence"]) == 2
    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-sdk-sidecar-evidence-ambiguous"


def test_two_domain_native_source_seed_allows_one_sidecar_for_same_agent_mismatch_hooks(
    tmp_path,
):
    _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
    )
    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_agent="agent-source-private",
        hook_tool="tool-other-private",
        second_hook_agent="agent-source-private",
        second_hook_tool="tool-another-private",
        history_root=tmp_path,
    )

    assert envelope["status"] == "available"
    assert envelope["agent_proof"]["provenance"] == "sdk_sidecar"
    assert len(runtime["native_hook_evidence"]) == 2
    assert runtime["native_hook_evidence"][0]["tool_use_id_digest"] == PROBE[
        "digest"
    ]("tool-other-private")
    assert runtime["native_hook_evidence"][1]["tool_use_id_digest"] == PROBE[
        "digest"
    ]("tool-another-private")


def test_two_domain_native_source_sdk_sidecar_start_tool_digest_is_mandatory_after_rehash(
    tmp_path,
):
    _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
    )
    _, envelope = _native_source_terminal_seed_envelope(
        hook_tool="tool-other-private",
        history_root=tmp_path,
    )
    candidate = json.loads(json.dumps(envelope))
    started = candidate["task_started_event"]
    started["tool_use_id_seen"] = False
    started["tool_use_id_digest"] = None
    proof = candidate["agent_proof"]
    proof["tool_use_id_seen"] = False
    proof["tool_use_id_digest"] = None
    proof["sidecar_record"]["task_tool_use_id_digest"] = None
    identity = candidate["source_identity_digests"]
    identity["tool_use_id_seen"] = False
    identity["tool_use_id_digest"] = None
    _rehash_native_source_seed(candidate)

    with pytest.raises(ValueError, match="agent proof"):
        PROBE["validate_native_task_source_terminal_seed_envelope"](
            candidate,
            expected_parent_uuid_digest=PROBE["digest"]("session-source"),
            expected_source_invocation_digest=PROBE["digest"](
                "source-invocation-private"
            ),
        )


def test_two_domain_native_source_seed_factory_rejects_invalid_sidecar_proof(tmp_path):
    _write_sdk_sidecar_history(
        tmp_path,
        parent="session-source",
        agent="agent-source-private",
        tool="tool-source-private",
    )
    runtime, _ = _native_source_terminal_seed_envelope(
        hook_tool="tool-other-private",
        history_root=tmp_path,
    )
    valid_sidecar, _ = PROBE["native_hook_sdk_sidecar_bridge"](
        tmp_path, runtime,
    )
    invalid_sidecar = dict(valid_sidecar)
    invalid_sidecar["matching_sidecar_count"] = True
    envelope = PROBE["native_task_source_terminal_seed_envelope"](
        runtime,
        parent_uuid="session-source",
        source_invocation="source-invocation-private",
        sdk_sidecar_record=invalid_sidecar,
        sdk_sidecar_reason="observed",
    )

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-sdk-sidecar-evidence-incomplete"


def test_two_domain_native_source_seed_refuses_wrong_hook_session_and_multiple_agent_bindings():
    wrong_session_runtime, wrong_session = _native_source_terminal_seed_envelope(
        hook_session="session-other-private", expect_hook_success=False,
    )
    assert wrong_session["status"] == "unavailable"
    assert wrong_session["reason_code"] == "terminal-task-hook-evidence-incomplete"
    assert "hook-session-mismatch" in wrong_session_runtime[
        "native_hook_unknown_reasons"
    ]

    _, multiple_agents = _native_source_terminal_seed_envelope(
        second_hook_agent="agent-other-private",
    )
    assert multiple_agents["status"] == "unavailable"
    assert multiple_agents["reason_code"] == "terminal-task-hook-evidence-ambiguous"


def test_two_domain_native_source_seed_refuses_tool_or_direct_agent_reuse_across_started_tasks():
    for direct_agent in (False, True):
        runtime, _ = _native_source_terminal_seed_envelope(
            include_direct_agent=direct_agent,
        )
        second = PROBE["sanitize_native_task_lifecycle_event"](
            {
                "type": "system", "subtype": "task_started",
                "task_type": "local_agent", "task_id": "task-second-private",
                "session_id": "session-source",
                "tool_use_id": (
                    "tool-other-private"
                    if direct_agent else "tool-source-private"
                ),
                "agent_id": "agent-source-private",
                "uuid": "event-second-start-private",
            },
            phase="source/setup", observation_sequence=3,
            provenance="source-observed",
        )
        runtime["native_task_evidence"].append(second)
        refused = PROBE["native_task_source_terminal_seed_envelope"](
            runtime,
            parent_uuid="session-source",
            source_invocation="source-invocation-private",
        )
        assert refused["status"] == "unavailable"
        assert refused["reason_code"] == "terminal-task-hook-evidence-ambiguous"


def test_two_domain_native_source_seed_refuses_hook_agent_named_by_another_start():
    runtime, _ = _native_source_terminal_seed_envelope()
    second = PROBE["sanitize_native_task_lifecycle_event"](
        {
            "type": "system", "subtype": "task_started",
            "task_type": "local_agent", "task_id": "task-second-private",
            "session_id": "session-source", "tool_use_id": "tool-second-private",
            "agent_id": "agent-source-private",
            "uuid": "event-second-start-private",
        },
        phase="source/setup", observation_sequence=3,
        provenance="source-observed",
    )
    runtime["native_task_evidence"].append(second)

    envelope = PROBE["native_task_source_terminal_seed_envelope"](
        runtime,
        parent_uuid="session-source",
        source_invocation="source-invocation-private",
    )

    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-hook-evidence-ambiguous"


def test_two_domain_native_source_task_updated_patch_status_is_recorded_but_not_a_seed():
    runtime, envelope = _native_source_terminal_seed_envelope(
        terminal_subtype="task_updated", terminal_status="killed",
    )
    updated = runtime["native_task_evidence"][-1]

    assert updated["event_subtype"] == "task_updated"
    assert updated["status"] == "killed"
    assert updated["task_type"] is None
    assert updated["session_id_seen"] is False
    assert updated["incomplete"] is False
    assert runtime["task_terminal_observed"] is True
    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-notification-not-observed"


def test_two_domain_native_task_updated_conflicting_top_and_patch_status_is_incomplete():
    evidence = PROBE["sanitize_native_task_lifecycle_event"](
        {
            "type": "system", "subtype": "task_updated",
            "task_id": "task-private", "status": "completed",
            "data": {"patch": {"status": "killed"}},
        },
        phase="source/drain", observation_sequence=4,
    )

    assert evidence["status"] is None
    assert evidence["incomplete"] is True
    assert "conflicting-status" in evidence["unknown_fields"]


@pytest.mark.parametrize("binding", ["parent", "invocation", "tamper"])
def test_two_domain_native_source_terminal_seed_envelope_rejects_binding_or_content_change(binding):
    _, envelope = _native_source_terminal_seed_envelope()
    candidate = json.loads(json.dumps(envelope))
    parent_digest = hashlib.sha256(b"session-source").hexdigest()
    invocation_digest = hashlib.sha256(b"source-invocation-private").hexdigest()
    if binding == "parent":
        candidate["parent_uuid_digest"] = "0" * 64
    elif binding == "invocation":
        candidate["source_invocation_digest"] = "0" * 64
    else:
        candidate["terminal_event"]["task_id_digest"] = "0" * 64
    with pytest.raises(ValueError):
        PROBE["validate_native_task_source_terminal_seed_envelope"](
            candidate,
            expected_parent_uuid_digest=parent_digest,
            expected_source_invocation_digest=invocation_digest,
        )


@pytest.mark.parametrize(
    "tamper",
    ["started", "agent-proof", "hook-proof", "order", "source-correlation", "extra"],
)
def test_two_domain_native_source_seed_rejects_rehashed_evidence_tampering(tamper):
    _, envelope = _native_source_terminal_seed_envelope()
    candidate = json.loads(json.dumps(envelope))
    if tamper == "started":
        candidate["task_started_event"]["task_type"] = "task_notification"
    elif tamper == "agent-proof":
        candidate["agent_proof"]["agent_id_digest"] = "0" * 64
    elif tamper == "hook-proof":
        candidate["agent_proof"]["hook_record"]["session_id_digest"] = "0" * 64
    elif tamper == "order":
        candidate["task_started_event"]["observation_sequence"] = candidate[
            "terminal_event"
        ]["observation_sequence"]
    elif tamper == "source-correlation":
        candidate["task_started_event"]["source_target_correlation"][
            "session_id"
        ] = "match"
    else:
        candidate["injected_target_observation"] = {"status": "match"}
    _rehash_native_source_seed(candidate)

    with pytest.raises(ValueError):
        PROBE["validate_native_task_source_terminal_seed_envelope"](
            candidate,
            expected_parent_uuid_digest=hashlib.sha256(b"session-source").hexdigest(),
            expected_source_invocation_digest=hashlib.sha256(
                b"source-invocation-private"
            ).hexdigest(),
        )


def test_two_domain_native_source_seed_rejects_rehashed_started_vs_hook_agent_conflict():
    runtime, envelope = _native_source_terminal_seed_envelope(include_direct_agent=True)
    candidate = json.loads(json.dumps(envelope))
    hook_agent_digest = PROBE["digest"]("agent-hook-conflict-private")
    hook_record = dict(runtime["native_hook_evidence"][0])
    hook_record["agent_id_digest"] = hook_agent_digest
    candidate["agent_proof"] = {
        "record_schema": PROBE["NATIVE_TASK_AGENT_PROOF_SCHEMA"],
        "provenance": "native_hook",
        "session_id_digest": candidate["task_started_event"]["session_id_digest"],
        "task_id_digest": candidate["task_started_event"]["task_id_digest"],
        "tool_use_id_seen": candidate["task_started_event"]["tool_use_id_seen"],
        "tool_use_id_digest": candidate["task_started_event"]["tool_use_id_digest"],
        "agent_id_seen": True,
        "agent_id_digest": hook_agent_digest,
        "hook_record": hook_record,
        "sidecar_record": None,
    }
    candidate["source_identity_digests"]["agent_id_digest"] = hook_agent_digest
    _rehash_native_source_seed(candidate)

    with pytest.raises(ValueError, match="agent proof"):
        PROBE["validate_native_task_source_terminal_seed_envelope"](
            candidate,
            expected_parent_uuid_digest=hashlib.sha256(b"session-source").hexdigest(),
            expected_source_invocation_digest=hashlib.sha256(
                b"source-invocation-private"
            ).hexdigest(),
        )


def test_two_domain_native_source_terminal_seed_requires_live_task_and_agent_identity():
    _, envelope = _native_source_terminal_seed_envelope(include_hook=False)
    assert envelope["status"] == "unavailable"
    assert envelope["reason_code"] == "terminal-task-agent-proof-unavailable"


def test_two_domain_native_source_digest_identity_path_does_not_hash_digests_twice():
    _, envelope = _native_source_terminal_seed_envelope()
    seed = envelope["terminal_event"]
    runtime = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed", seed=seed,
    )
    runtime["native_task_source_identity_digests"] = envelope["source_identity_digests"]
    event = {
        "type": "system", "subtype": "task_notification",
        "task_type": "local_agent", "status": "completed",
        "session_id": "session-source", "task_id": "task-source-private",
        "agent_id": "agent-source-private", "uuid": "event-terminal-private",
    }
    PROBE["observe_frame"](event, runtime)
    evidence = runtime["native_task_evidence"][-1]
    assert evidence["source_target_correlation"] == {
        "session_id": "match", "task_id": "match",
        "tool_use_id": "unknown", "agent_id": "match",
    }
    assert evidence["correlation_class"] == "replay-compatible"
    assert evidence["task_id_digest"] == hashlib.sha256(
        b"task-source-private"
    ).hexdigest()


def test_two_domain_native_source_seed_matches_sdk_notification_without_optional_target_ids():
    _, envelope = _native_source_terminal_seed_envelope()
    target = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed",
        seed=envelope["terminal_event"],
    )
    target["native_task_source_identity_digests"] = envelope[
        "source_identity_digests"
    ]
    target["native_task_seed_provenance"] = "source-terminal-seed"
    PROBE["observe_frame"](
        {
            "type": "system", "subtype": "task_notification",
            "status": "completed", "session_id": "session-source",
            "task_id": "task-source-private", "uuid": "event-terminal-private",
        },
        target,
    )
    evidence = target["native_task_evidence"][-1]

    assert evidence["task_type"] is None
    assert evidence["agent_id_seen"] is False
    assert evidence["tool_use_id_seen"] is False
    assert evidence["source_target_correlation"] == {
        "session_id": "match", "task_id": "match",
        "tool_use_id": "unknown", "agent_id": "unknown",
    }
    assert evidence["incomplete"] is False
    assert evidence["correlation_class"] == "replay-compatible"


@pytest.mark.parametrize(
    ("field", "value", "correlation_key"),
    [
        ("tool_use_id", "tool-conflict-private", "tool_use_id"),
        ("agent_id", "agent-conflict-private", "agent_id"),
    ],
)
def test_two_domain_native_source_seed_rejects_conflicting_optional_target_identity(
    field, value, correlation_key,
):
    _, envelope = _native_source_terminal_seed_envelope()
    target = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed",
        seed=envelope["terminal_event"],
    )
    target["native_task_source_identity_digests"] = envelope[
        "source_identity_digests"
    ]
    event = {
        "type": "system", "subtype": "task_notification",
        "status": "completed", "session_id": "session-source",
        "task_id": "task-source-private", "uuid": "event-terminal-private",
        field: value,
    }
    PROBE["observe_frame"](event, target)
    evidence = target["native_task_evidence"][-1]

    assert evidence["source_target_correlation"][correlation_key] == "mismatch"
    assert evidence["incomplete"] is True
    assert evidence["correlation_class"] == "live-or-unresolved"
    assert value not in json.dumps(evidence)


def test_two_domain_native_target_requires_exact_terminal_subtype_and_status_for_correlation():
    _, envelope = _native_source_terminal_seed_envelope()
    target = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed",
        seed=envelope["terminal_event"],
    )
    PROBE["observe_frame"](
        {
            "type": "system", "subtype": "task_updated",
            "task_id": "task-source-private", "session_id": "session-source",
            "uuid": "event-terminal-private", "data": {"patch": {"status": "completed"}},
        },
        target,
    )
    assert target["native_task_evidence"][-1]["correlation_class"] == (
        "live-or-unresolved"
    )

    status_target = _native_lifecycle_runtime(
        phase="target/startup", provenance="target-observed",
        seed=envelope["terminal_event"],
    )
    PROBE["observe_frame"](
        {
            "type": "system", "subtype": "task_notification",
            "status": "failed", "session_id": "session-source",
            "task_id": "task-source-private", "uuid": "event-terminal-private",
        },
        status_target,
    )
    assert status_target["native_task_evidence"][-1]["correlation_class"] == (
        "live-or-unresolved"
    )


def test_two_domain_source_seed_validation_recomputes_source_phase_binding():
    parent = "session-source"
    invocation = "source-invocation-private"
    _, envelope = _native_source_terminal_seed_envelope(
        parent=parent, invocation=invocation,
    )
    source_projection = TWO_DOMAIN["_source_projection"]({
        "native_task_terminal_seed_status": "available",
        "native_task_terminal_seed_digest": envelope["seed_digest"],
        "native_task_terminal_seed_reason_code": None,
        "native_task_lifecycle_summary": {
            "record_schema": "native-task-observation-v2",
            "observation_status": "observed",
            "event_count": 2,
            "observation_sequence_max": 2,
            "overflow": False,
            "incomplete": False,
            "seed_provenance": "source-terminal-seed",
            "source_terminal_seed_index": 2,
            "unknown_reasons": [],
            "support_claim": False,
        },
        "native_hook_summary": {
            "record_schema": "native-hook-observation-v1",
            "observed_count": 1,
            "stored_count": 1,
            "request_count": 1,
            "request_limit": 128,
            "request_overflow": False,
            "overflow": False,
            "joined_count": 1,
            "unresolved_count": 0,
            "started_task_event_count": 1,
            "started_task_tool_use_id_seen": True,
            "session_matched_hook_count": 1,
            "hook_tool_use_id_seen_count": 1,
            "hook_tool_use_id_missing_count": 0,
            "same_task_hook_count": 1,
            "same_task_tool_use_id_missing_count": 0,
            "same_task_tool_use_id_mismatch_count": 0,
            "exact_task_tool_link_candidate_count": 1,
            "rejected_tool_use_id_conflict_count": 0,
            "rejected_tool_use_id_mismatch_count": 0,
            "unknown_reasons": [],
            "support_claim": False,
        },
    })
    report = {
        "source_invocation": invocation,
        "fixture_owner": "owner-private",
        "fixture_lineage": "lineage-private",
        "fixture_runner": "runner-private",
        "fixture_daemon": "daemon-private",
        "private_handoff": {
            "parent_uuid": parent,
            "parent_uuid_digest": hashlib.sha256(parent.encode()).hexdigest(),
            "native_task_terminal_seed": envelope,
        },
        "source": source_projection,
    }
    report["source_phase_report_digest"] = TWO_DOMAIN["_digest"]({
        "source_invocation": invocation,
        "fixture_owner": report["fixture_owner"],
        "fixture_lineage": report["fixture_lineage"],
        "fixture_runner": report["fixture_runner"],
        "fixture_daemon": report["fixture_daemon"],
        "parent_uuid_digest": report["private_handoff"]["parent_uuid_digest"],
        "source": report["source"],
        "native_task_terminal_seed_digest": envelope["seed_digest"],
    })
    validated = TWO_DOMAIN["_validated_source_native_task_seed"](
        report, parent_uuid=parent,
    )
    assert validated["seed_digest"] == envelope["seed_digest"]
    assert source_projection["native_hook_summary"][
        "exact_task_tool_link_candidate_count"
    ] == 1
    assert "/private/" not in json.dumps(source_projection)
    assert "tool-source-private" not in json.dumps(source_projection)
    report["source"]["native_hook_summary"][
        "hook_tool_use_id_missing_count"
    ] = 1
    with pytest.raises(RuntimeError, match="phase binding"):
        TWO_DOMAIN["_validated_source_native_task_seed"](
            report, parent_uuid=parent,
        )
    report["source_phase_report_digest"] = "0" * 64
    with pytest.raises(RuntimeError, match="phase binding"):
        TWO_DOMAIN["_validated_source_native_task_seed"](
            report, parent_uuid=parent,
        )


def test_two_domain_release_gate_refuses_unavailable_source_task_seed():
    unavailable = {
        "status": "unavailable",
        "reason_code": "terminal-task-seed-not-observed",
    }
    reasons = TWO_DOMAIN["_release_candidate_reasons"](
        {}, {}, {}, {}, unavailable,
    )
    assert "source-native-task-terminal-seed-unavailable" in reasons


def test_two_domain_target_spec_fingerprint_binds_source_task_seed():
    _, seed = _native_source_terminal_seed_envelope()
    selected = {"resume_arguments": ["--resume", "__LANE_LOOPBACK_SESSION__"]}
    kwargs = {
        "selected": selected,
        "parent_uuid": "session-source",
        "image_id": "sha256:" + "a" * 64,
        "state_volume": "target-volume-private",
        "source_phase_report_digest": "b" * 64,
        "source_invocation_digest": seed["source_invocation_digest"],
        "native_task_source_seed": seed,
    }
    profile, fingerprint = TWO_DOMAIN["_target_spec"](**kwargs)
    changed = json.loads(json.dumps(seed))
    changed["seed_digest"] = "0" * 64
    with pytest.raises(RuntimeError, match="validated native task seed"):
        TWO_DOMAIN["_target_spec"](**{**kwargs, "native_task_source_seed": changed})
    assert profile["native_task_source_seed_digest"] == seed["seed_digest"]
    assert profile["source_phase_report_digest"] == "b" * 64
    assert fingerprint == TWO_DOMAIN["_digest"]({
        "profile": profile,
        "image_id": kwargs["image_id"],
        "cli_sha256": None,
        "sdk_version": None,
        "arguments": ["--resume", "session-source"],
        "agent_config": None,
        "parent_uuid_digest": hashlib.sha256(b"session-source").hexdigest(),
        "native_task_source_seed_digest": seed["seed_digest"],
        "source_phase_report_digest": "b" * 64,
        "source_invocation_digest": seed["source_invocation_digest"],
        "history_query_mode": TWO_DOMAIN["HISTORY_QUERY_MODE"],
    })


def test_two_domain_target_spec_rejects_self_consistent_seed_change_before_cli(
    monkeypatch,
):
    parent = "session-source"
    _, seed = _native_source_terminal_seed_envelope(parent=parent)
    source_phase_digest = "b" * 64
    selected = {
        "resume_arguments": ["--resume", "__LANE_LOOPBACK_SESSION__"],
        "cli_sha256": "d" * 64,
        "sdk_version": "0.2.153",
        "agent_config": {"worker": {"description": "offline test"}},
    }
    profile, fingerprint = TWO_DOMAIN["_target_spec"](
        selected=selected,
        parent_uuid=parent,
        image_id="sha256:" + "a" * 64,
        state_volume="target-volume-private",
        source_phase_report_digest=source_phase_digest,
        source_invocation_digest=seed["source_invocation_digest"],
        native_task_source_seed=seed,
    )
    changed_seed = json.loads(json.dumps(seed))
    changed_seed["terminal_event"]["status"] = "failed"
    seed_core = {key: value for key, value in changed_seed.items() if key != "seed_digest"}
    changed_seed["seed_digest"] = hashlib.sha256(
        PROBE["_canonical_json"](seed_core)
    ).hexdigest()
    changed_profile = dict(profile)
    changed_profile["native_task_source_seed_digest"] = changed_seed["seed_digest"]
    expected = {
        "two_domain_phase": "target",
        "state_root": "/opt/state",
        "source_parent_uuid": parent,
        "source_invocation_digest": seed["source_invocation_digest"],
        "source_phase_report_digest": source_phase_digest,
        "native_task_source_terminal_seed": changed_seed,
        "native_task_source_terminal_seed_digest": changed_seed["seed_digest"],
        "history_query_mode": TWO_DOMAIN["HISTORY_QUERY_MODE"],
        "target_profile": changed_profile,
        "target_spec_fingerprint": fingerprint,
        "resume_arguments": selected["resume_arguments"],
        "image_id": "sha256:" + "a" * 64,
        "cli_sha256": selected["cli_sha256"],
        "sdk_version": selected["sdk_version"],
        "agent_config": selected["agent_config"],
    }
    cli_calls = []
    monkeypatch.setattr(
        PROBE["subprocess"], "run",
        lambda *args, **kwargs: cli_calls.append(("run", args, kwargs)),
    )
    monkeypatch.setattr(
        PROBE["subprocess"], "Popen",
        lambda *args, **kwargs: cli_calls.append(("Popen", args, kwargs)),
    )
    with pytest.raises(RuntimeError, match="target specification fingerprint mismatch"):
        PROBE["runtime_two_domain_target"](expected)
    assert cli_calls == []


def test_stop_then_resume_v1_native_hooks_are_opt_in_and_pinned():
    expected = {"agent_config": {"worker": {"description": "bounded"}}}

    legacy = PROBE["initialize_frame"](expected, "init-legacy")
    assert legacy["request"]["hooks"] is None

    enabled = PROBE["initialize_frame"](
        expected, "init-hooks", observe_native_hooks=True
    )
    hooks = enabled["request"]["hooks"]
    assert set(hooks) == {"SubagentStart", "SubagentStop"}
    assert hooks["SubagentStart"] == [
        {"matcher": None, "hookCallbackIds": ["native-subagent-start"]}
    ]
    assert hooks["SubagentStop"] == [
        {"matcher": None, "hookCallbackIds": ["native-subagent-stop"]}
    ]


def test_stop_then_resume_v1_native_hook_ack_is_empty_and_once():
    runtime = _native_hook_runtime()
    frame = _native_hook_request(
        "hook-once",
        "native-subagent-stop",
        {
            "hook_event_name": "SubagentStop",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-current",
            "agent_type": "native-worker",
            "agent_transcript_path": "/private/child.jsonl",
            "stop_hook_active": False,
            "body": {
                "type": "tool_result",
                "tool_use_id": "tool-current",
                "session_id": "spoof-session",
                "task_id": "spoof-task",
            },
        },
    )

    first = PROBE["handle_native_hook_callback"](frame, runtime)
    assert first == {
        "type": "control_response",
        "response": {
            "subtype": "success",
            "request_id": "hook-once",
            "response": {},
        },
    }
    assert PROBE["handle_native_hook_callback"](frame, runtime) is None
    assert len(runtime["native_hook_evidence"]) == 1
    assert runtime["task_terminal_observed"] is False
    assert runtime["stopped_notification"] is False
    assert runtime["tool_terminal"] is False
    assert runtime["source_parent_result_seen"] is False
    assert runtime["successful_result_seen"] is False
    assert runtime["session_id"] == "session-current"
    assert runtime["actual_task_id"] == "task-current"


@pytest.mark.parametrize(
    "callback_id,input_value,tool_use_id",
    [
        (
            "native-unknown",
            {"session_id": "session-current", "secret": "raw-body"},
            "tool-current",
        ),
        ("native-subagent-start", "raw-body", "tool-current"),
    ],
)
def test_stop_then_resume_v1_native_hook_unknown_or_malformed_fails_closed(
    callback_id, input_value, tool_use_id
):
    runtime = _native_hook_runtime()
    frame = _native_hook_request(
        "hook-reject",
        callback_id,
        input_value,
        tool_use_id=tool_use_id,
    )

    response = PROBE["handle_native_hook_callback"](frame, runtime)

    assert response["type"] == "control_response"
    assert response["response"]["subtype"] == "error"
    assert response["response"]["request_id"] == "hook-reject"
    assert "raw-body" not in json.dumps(response, sort_keys=True)
    assert "secret" not in json.dumps(response, sort_keys=True)
    assert runtime["native_hook_evidence"] == []


def test_stop_then_resume_v1_native_hook_reused_id_conflict_is_not_replayed():
    runtime = _native_hook_runtime()
    first = _native_hook_request(
        "hook-reused",
        "native-subagent-start",
        {
            "hook_event_name": "SubagentStart",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-current",
            "agent_type": "native-worker",
        },
    )
    assert PROBE["handle_native_hook_callback"](first, runtime)["response"][
        "subtype"
    ] == "success"

    conflict = _native_hook_request(
        "hook-reused",
        "native-subagent-start",
        {
            "hook_event_name": "SubagentStart",
            "session_id": "session-current",
            "agent_id": "agent-stale",
            "agent_type": "native-worker",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
        },
    )
    assert PROBE["handle_native_hook_callback"](conflict, runtime) is None
    assert len(runtime["native_hook_evidence"]) == 1
    assert "hook-request-id-conflict" in runtime["native_hook_unknown_reasons"]


def test_stop_then_resume_v1_native_hook_evidence_is_structural_and_separate():
    runtime = _native_hook_runtime()
    raw_path = "/private/raw-child-transcript.jsonl"
    frame = _native_hook_request(
        "hook-privacy",
        "native-subagent-stop",
        {
            "hook_event_name": "SubagentStop",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-current",
            "agent_type": "native-worker",
            "agent_transcript_path": raw_path,
            "stop_hook_active": False,
            "tool_input": {
                "session_id": "spoof-session",
                "agent_id": "spoof-agent",
                "agent_transcript_path": "/spoof/body.jsonl",
            },
        },
    )

    response = PROBE["handle_native_hook_callback"](frame, runtime)

    assert response["response"]["subtype"] == "success"
    evidence = runtime["native_hook_evidence"][0]
    assert evidence["hook_event_name"] == "SubagentStop"
    assert evidence["session_id_seen"] is True
    assert evidence["session_id_digest"] == PROBE["digest"]("session-current")
    assert evidence["agent_id_seen"] is True
    assert evidence["agent_id_digest"] == PROBE["digest"]("agent-current")
    assert evidence["agent_type"] == "native-worker"
    assert evidence["agent_transcript_path_seen"] is True
    assert evidence["agent_transcript_path_digest"] == PROBE["digest"](raw_path)
    encoded = json.dumps(evidence, sort_keys=True)
    assert raw_path not in encoded
    assert "spoof-session" not in encoded
    assert "spoof-agent" not in encoded
    assert runtime["task_terminal_observed"] is False
    assert runtime["stopped_notification"] is False


def test_stop_then_resume_v1_native_hook_input_cap_fails_closed_without_raw_error():
    runtime = _native_hook_runtime()
    oversized = "x" * 70000
    frame = _native_hook_request(
        "hook-overflow",
        "native-subagent-start",
        {
            "hook_event_name": "SubagentStart",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": oversized,
            "agent_type": "native-worker",
        },
    )

    response = PROBE["handle_native_hook_callback"](frame, runtime)

    assert response["response"]["subtype"] == "error"
    assert oversized not in json.dumps(response, sort_keys=True)
    assert runtime["native_hook_evidence"] == []


def test_stop_then_resume_v1_native_hook_event_must_match_registration():
    runtime = _native_hook_runtime()
    frame = _native_hook_request(
        "hook-event-mismatch",
        "native-subagent-start",
        {
            "hook_event_name": "SubagentStop",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-current",
            "agent_type": "native-worker",
            "agent_transcript_path": "/private/child.jsonl",
            "stop_hook_active": False,
            "body": {
                "type": "tool_result",
                "tool_use_id": "tool-current",
                "session_id": "spoof-session",
                "task_id": "spoof-task",
            },
        },
    )

    response = PROBE["handle_native_hook_callback"](frame, runtime)

    assert response["response"]["subtype"] == "error"
    assert runtime["native_hook_evidence"] == []


def test_stop_then_resume_v1_native_hook_wrong_session_is_rejected():
    runtime = _native_hook_runtime()
    frame = _native_hook_request(
        "hook-wrong-session",
        "native-subagent-start",
        {
            "hook_event_name": "SubagentStart",
            "session_id": "session-stale",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-current",
            "agent_type": "native-worker",
        },
    )

    response = PROBE["handle_native_hook_callback"](frame, runtime)

    assert response["response"]["subtype"] == "error"
    assert runtime["native_hook_evidence"] == []
    assert runtime["native_hook_unknown_reasons"] == [
        "hook-session-mismatch"
    ]


def test_stop_then_resume_v1_native_hook_input_tool_conflict_is_rejected():
    runtime = _native_hook_runtime()
    frame = _native_hook_request(
        "hook-tool-conflict",
        "native-subagent-start",
        {
            "hook_event_name": "SubagentStart",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-current",
            "agent_type": "native-worker",
            "tool_use_id": "tool-other",
        },
    )

    response = PROBE["handle_native_hook_callback"](frame, runtime)

    assert response["response"]["subtype"] == "error"
    assert runtime["native_hook_evidence"] == []
    assert "hook-tool-use-id-conflict" in runtime["native_hook_unknown_reasons"]
    diagnostic = PROBE["native_hook_evidence_summary"](runtime)[
        "mismatch_diagnostics"
    ][0]
    assert diagnostic["reason"] == "callback-input-tool-use-id-conflict"
    assert diagnostic["callback_tool_use_id_digest"] == PROBE["digest"](
        "tool-current"
    )
    assert diagnostic["input_tool_use_id_digest"] == PROBE["digest"](
        "tool-other"
    )
    assert diagnostic["task_tool_use_id_digest"] == PROBE["digest"](
        "tool-current"
    )
    assert diagnostic["task_id_digest"] == PROBE["digest"]("task-current")
    encoded = json.dumps(diagnostic, sort_keys=True)
    assert "tool-current" not in encoded
    assert "tool-other" not in encoded


def test_two_domain_native_hook_mismatch_diagnostic_distinguishes_input_from_callback_id():
    runtime, envelope = _native_source_terminal_seed_envelope(
        hook_tool=None,
        hook_input_tool_id="tool-input-only-private",
    )
    summary = PROBE["native_hook_evidence_summary"](runtime)
    diagnostic = summary["mismatch_diagnostics"][0]

    assert envelope["status"] == "unavailable"
    assert diagnostic["callback_tool_use_id_seen"] is False
    assert diagnostic["callback_tool_use_id_digest"] is None
    assert diagnostic["input_tool_use_id_seen"] is True
    assert diagnostic["input_tool_use_id_digest"] == PROBE["digest"](
        "tool-input-only-private"
    )
    assert diagnostic["task_tool_use_id_digest"] == PROBE["digest"](
        "tool-source-private"
    )
    assert diagnostic["task_id_digest"] == PROBE["digest"](
        "task-source-private"
    )
    assert runtime["native_hook_evidence"][0]["tool_use_id_digest"] == PROBE[
        "digest"
    ]("tool-input-only-private")


def test_stop_then_resume_v1_native_hook_null_tool_id_is_unresolved():
    runtime = _native_hook_runtime()
    frame = _native_hook_request(
        "hook-null-tool",
        "native-subagent-start",
        {
            "hook_event_name": "SubagentStart",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-current",
            "agent_type": "native-worker",
        },
        tool_use_id=None,
    )

    response = PROBE["handle_native_hook_callback"](frame, runtime)

    assert response["response"]["subtype"] == "success"
    evidence = runtime["native_hook_evidence"][0]
    assert evidence["join_status"] == "unresolved"
    assert evidence["agent_id_digest"] == PROBE["digest"]("agent-current")
    assert evidence["task_id_seen"] is False
    assert evidence["tool_use_id_seen"] is False


def test_stop_then_resume_v1_native_hook_task_not_observed_keeps_partial_fact():
    runtime = _native_hook_runtime()
    runtime["actual_task_id"] = None
    runtime["task_tool_use_id"] = None
    frame = _native_hook_request(
        "hook-pre-task",
        "native-subagent-start",
        {
            "hook_event_name": "SubagentStart",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-pre-task",
            "agent_type": "native-worker",
        },
        tool_use_id=None,
    )

    response = PROBE["handle_native_hook_callback"](frame, runtime)

    assert response["response"]["subtype"] == "success"
    evidence = runtime["native_hook_evidence"][0]
    assert evidence["join_status"] == "unresolved"
    assert evidence["task_id_seen"] is False
    assert evidence["tool_use_id_seen"] is False
    assert "task_id_digest" not in evidence
    assert "tool_use_id_digest" not in evidence


def test_stop_then_resume_v1_native_hook_same_agent_fresh_task_is_unresolved():
    runtime = _native_hook_runtime()
    first = _native_hook_request(
        "hook-agent-first",
        "native-subagent-start",
        {
            "hook_event_name": "SubagentStart",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-reused",
            "agent_type": "native-worker",
        },
    )
    assert PROBE["handle_native_hook_callback"](first, runtime)["response"][
        "subtype"
    ] == "success"

    runtime["actual_task_id"] = "task-next"
    runtime["task_tool_use_id"] = "tool-next"
    fresh = _native_hook_request(
        "hook-agent-fresh",
        "native-subagent-start",
        {
            "hook_event_name": "SubagentStart",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-reused",
            "agent_type": "native-worker",
        },
        tool_use_id="tool-next",
    )

    response = PROBE["handle_native_hook_callback"](fresh, runtime)

    assert response["response"]["subtype"] == "error"
    assert len(runtime["native_hook_evidence"]) == 1
    assert "reused-agent-id" in runtime["native_hook_unknown_reasons"]


def test_stop_then_resume_v1_native_hook_evidence_count_is_bounded_and_deduped():
    runtime = _native_hook_runtime()
    runtime["native_hook_evidence_limit"] = 2
    for index in range(5):
        frame = _native_hook_request(
            "hook-count-%d" % index,
            "native-subagent-start",
            {
                "hook_event_name": "SubagentStart",
                "session_id": "session-current",
                "transcript_path": "/private/coordinator.jsonl",
                "cwd": "/private/work",
                "agent_id": "agent-%d" % index,
                "agent_type": "native-worker",
            },
        )
        assert PROBE["handle_native_hook_callback"](frame, runtime)["response"][
            "subtype"
        ] == "success"

    for index in range(2):
        frame = _native_hook_request(
            "hook-bad-%d" % index,
            "native-subagent-start",
            {
                "hook_event_name": "SubagentStart",
                "session_id": "session-stale",
                "transcript_path": "/private/coordinator.jsonl",
                "cwd": "/private/work",
                "agent_id": "agent-bad-%d" % index,
                "agent_type": "native-worker",
            },
        )
        assert PROBE["handle_native_hook_callback"](frame, runtime)["response"][
            "subtype"
        ] == "error"

    report = PROBE["native_hook_evidence_report"](runtime)
    assert report["stored_count"] == 2
    assert report["observed_count"] == 5
    assert report["overflow"] is True
    assert report["support_claim"] is False
    assert len(report["unknown_reasons"]) == len(set(report["unknown_reasons"]))
    assert report["unknown_reasons"].count("hook-session-mismatch") == 1


def test_stop_then_resume_v1_read_frames_routes_hook_ack_once_and_keeps_guard():
    runtime = _native_hook_runtime()
    runtime.update(
        {
            "startup_observation_active": True,
            "startup_activity_observed": False,
            "startup_activity_kinds": [],
            "startup_unclassified_lifecycle_count": 0,
        }
    )
    frame = _native_hook_request(
        "hook-reader",
        "native-subagent-stop",
        {
            "hook_event_name": "SubagentStop",
            "session_id": "session-current",
            "transcript_path": "/private/coordinator.jsonl",
            "cwd": "/private/work",
            "agent_id": "agent-current",
            "agent_type": "native-worker",
            "agent_transcript_path": "/private/child.jsonl",
            "stop_hook_active": False,
            "body": {
                "type": "tool_result",
                "tool_use_id": "tool-current",
                "session_id": "spoof-session",
                "task_id": "spoof-task",
            },
        },
    )
    read_fd, write_fd = os.pipe()
    os.write(
        write_fd,
        (json.dumps(frame) + "\n" + json.dumps(frame) + "\n").encode(),
    )
    os.close(write_fd)
    stdout = os.fdopen(read_fd, "rb")

    class Writer:
        def __init__(self):
            self.chunks = []

        def write(self, value):
            self.chunks.append(value)
            return len(value)

        def flush(self):
            return None

    writer = Writer()
    process = SimpleNamespace(stdout=stdout, stdin=writer)
    selector = PROBE["selectors"].DefaultSelector()
    selector.register(stdout, PROBE["selectors"].EVENT_READ)
    try:
        PROBE["read_frames"](
            process,
            selector,
            {stdout: bytearray()},
            runtime,
            PROBE["time"].monotonic() + 1,
        )
    finally:
        selector.close()
        stdout.close()

    assert len(writer.chunks) == 1
    assert json.loads(writer.chunks[0]) == {
        "type": "control_response",
        "response": {
            "subtype": "success",
            "request_id": "hook-reader",
            "response": {},
        },
    }
    assert len(runtime["native_hook_evidence"]) == 1
    assert runtime["task_terminal_observed"] is False
    assert runtime["stopped_notification"] is False
    assert runtime["tool_terminal"] is False
    assert runtime["source_parent_result_seen"] is False
    assert runtime["successful_result_seen"] is False
    assert runtime["session_id"] == "session-current"
    assert runtime["actual_task_id"] == "task-current"
    assert runtime["startup_observation_active"] is True
    assert runtime["startup_activity_observed"] is True
    assert runtime["startup_unclassified_lifecycle_count"] == 2
    gate = PROBE["assess_v1_history_query_gate"](
        {
            "initialize_succeeded": True,
            "target_alive": True,
            "session_identity_observed": True,
            "session_identity_mismatch": False,
            "resume_spec_bound": True,
            "source_manifest_bound": True,
            "parent_messages_since_launch": 0,
            "child_messages_since_launch": 0,
            "native_task_events": 0,
            "startup_parent_result_observed": False,
            "generic_startup_activity_observed": runtime[
                "startup_activity_observed"
            ],
            "reader_error": False,
            "unparsed_frames": 0,
            "unclassified_lifecycle_events": runtime[
                "startup_unclassified_lifecycle_count"
            ],
            "quiet_window_observed": True,
        }
    )
    assert gate["history_query_allowed"] is False
    assert "startup-unclassified-lifecycle-observed" in gate["reason_codes"]


def two_domain_created_tmpfs_record():
    return {
        "Privileged": False,
        "HostConfig": {
            "NetworkMode": "none",
            "Privileged": False,
            "ReadonlyRootfs": True,
            "PidMode": "",
            "IpcMode": "private",
            "UTSMode": "private",
            "CapAdd": [],
            "CapDrop": ["ALL"],
            "Devices": [],
            "DeviceRequests": [],
            "SecurityOpt": ["no-new-privileges"],
            "Binds": [],
            "VolumesFrom": [],
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "PidsLimit": 96,
            "Memory": 768 * 1024 * 1024,
            "NanoCpus": 1_000_000_000,
            "Tmpfs": {
                "/tmp": "rw,nosuid,nodev,noexec,size=100663296",
                "/opt/loopback": "rw,nosuid,nodev,exec,size=268435456",
            },
        },
        "Config": {"Labels": {
            "openrepotools.bite4.run": "run-created",
            "openrepotools.bite4.role": "source",
        }},
        "State": {
            "Status": "created", "Running": False, "Pid": 0,
            "StartedAt": "0001-01-01T00:00:00Z",
            "FinishedAt": "0001-01-01T00:00:00Z",
        },
        "Mounts": [{
            "Type": "volume", "Name": "state-created",
            "Destination": "/opt/state", "RW": True,
        }],
    }


def test_two_domain_validator_accepts_exact_created_tmpfs_configuration():
    expected = {
        "/opt/state": ("volume", "state-created", True),
        "/tmp": ("tmpfs", None, True),
        "/opt/loopback": ("tmpfs", None, True),
    }
    record = two_domain_created_tmpfs_record()

    assert PROBE["two_domain_created_never_started"](record) is True
    PROBE["validate_two_domain_isolation"](
        record, run_id="run-created", role="source", expected_mounts=expected,
    )


@pytest.mark.parametrize(
    ("field", "value", "remove"),
    [
        ("StartedAt", "", False),
        ("StartedAt", None, False),
        ("StartedAt", None, True),
        ("StartedAt", "2026-09-22T00:00:00Z", False),
        ("FinishedAt", "", False),
        ("FinishedAt", None, False),
        ("FinishedAt", None, True),
        ("FinishedAt", "2026-09-22T00:00:00Z", False),
    ],
)
def test_two_domain_never_started_requires_exact_docker_zero_times(field, value, remove):
    record = two_domain_created_tmpfs_record()
    if remove:
        record["State"].pop(field)
    else:
        record["State"][field] = value

    assert PROBE["two_domain_created_never_started"](record) is False


@pytest.mark.parametrize(
    "mutation",
    ["partial-tmpfs", "extra-tmpfs", "running-without-tmpfs",
     "ambiguous-start-history", "extra-configured-tmpfs"],
)
def test_two_domain_validator_rejects_unproven_or_conflicting_tmpfs(mutation):
    expected = {
        "/opt/state": ("volume", "state-created", True),
        "/tmp": ("tmpfs", None, True),
        "/opt/loopback": ("tmpfs", None, True),
    }
    record = two_domain_created_tmpfs_record()
    if mutation == "partial-tmpfs":
        record["Mounts"].append({
            "Type": "tmpfs", "Source": "tmpfs", "Destination": "/tmp", "RW": True,
        })
    elif mutation == "extra-tmpfs":
        record["Mounts"].append({
            "Type": "tmpfs", "Source": "tmpfs", "Destination": "/unexpected", "RW": True,
        })
    elif mutation == "running-without-tmpfs":
        record["State"].update({
            "Status": "running", "Running": True, "Pid": 17,
            "StartedAt": "2026-09-22T00:00:00Z",
        })
    elif mutation == "ambiguous-start-history":
        record["State"].update({
            "Status": "exited", "Running": False, "Pid": 0,
            "StartedAt": "2026-09-22T00:00:00Z",
        })
    elif mutation == "extra-configured-tmpfs":
        record["HostConfig"]["Tmpfs"]["/unexpected"] = (
            "rw,nosuid,nodev,noexec,size=1048576"
        )

    with pytest.raises(RuntimeError, match="two-domain tmpfs destination mismatch"):
        PROBE["validate_two_domain_isolation"](
            record, run_id="run-created", role="source", expected_mounts=expected,
        )


def test_two_domain_running_missing_tmpfs_requires_active_witness():
    started = two_domain_created_tmpfs_record()
    started["State"].update({
        "Status": "running", "Running": True, "Pid": 17,
        "StartedAt": "2026-09-22T00:00:00Z",
    })
    with pytest.raises(RuntimeError, match="two-domain tmpfs destination mismatch"):
        PROBE["validate_two_domain_isolation"](
            started, run_id="run-created", role="source",
            expected_mounts={
                "/opt/state": ("volume", "state-created", True),
                "/tmp": ("tmpfs", None, True),
                "/opt/loopback": ("tmpfs", None, True),
            },
        )


def test_two_domain_validator_requires_exact_no_network_volume_and_restart_no():
    record = {
        "Privileged": False,
        "HostConfig": {
            "NetworkMode": "none",
            "Privileged": False,
            "ReadonlyRootfs": True,
            "PidMode": "",
            "IpcMode": "private",
            "UTSMode": "private",
            "CapAdd": [],
            "CapDrop": ["ALL"],
            "Devices": [],
            "DeviceRequests": [],
            "SecurityOpt": ["no-new-privileges"],
            "Binds": [],
            "VolumesFrom": [],
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "PidsLimit": 96,
            "Memory": 805306368,
            "NanoCpus": 1000000000,
        },
        "Config": {"Labels": {
            "openrepotools.bite4.run": "run-1",
            "openrepotools.bite4.role": "source",
        }},
        "Mounts": [{
            "Type": "volume",
            "Name": "state-run-1",
            "Destination": "/opt/state",
            "RW": True,
        }],
    }
    PROBE["validate_two_domain_isolation"](
        record,
        run_id="run-1",
        role="source",
        expected_mounts={"/opt/state": ("volume", "state-run-1", True)},
    )

    wrong_restart = json.loads(json.dumps(record))
    wrong_restart["HostConfig"]["RestartPolicy"]["Name"] = "always"
    with pytest.raises(RuntimeError, match="restart=no"):
        PROBE["validate_two_domain_isolation"](
            wrong_restart,
            run_id="run-1",
            role="source",
            expected_mounts={"/opt/state": ("volume", "state-run-1", True)},
        )

    wrong_mount = json.loads(json.dumps(record))
    wrong_mount["Mounts"][0]["Type"] = "bind"
    with pytest.raises(RuntimeError, match="non-volume"):
        PROBE["validate_two_domain_isolation"](
            wrong_mount,
            run_id="run-1",
            role="source",
            expected_mounts={"/opt/state": ("volume", "state-run-1", True)},
        )


def test_two_domain_validator_rejects_inherited_healthchecks():
    record = {
        "Privileged": False,
        "HostConfig": {
            "NetworkMode": "none", "ReadonlyRootfs": True,
            "PidMode": "private", "IpcMode": "private", "UTSMode": "private",
            "CapAdd": [], "CapDrop": ["ALL"], "Devices": [], "DeviceRequests": [],
            "SecurityOpt": ["no-new-privileges:true"], "Binds": [], "VolumesFrom": [],
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "PidsLimit": 96, "Memory": 768 * 1024 * 1024, "NanoCpus": 1_000_000_000,
        },
        "Config": {
            "Labels": {
                "openrepotools.bite4.run": "run-health",
                "openrepotools.bite4.role": "source",
            },
            "Healthcheck": {"Test": ["CMD-SHELL", "unexpected process"]},
        },
        "Mounts": [{
            "Type": "volume", "Name": "state-health", "Destination": "/opt/state", "RW": True,
        }],
    }
    with pytest.raises(RuntimeError, match="inherited healthchecks"):
        PROBE["validate_two_domain_isolation"](
            record,
            run_id="run-health", role="source",
            expected_mounts={"/opt/state": ("volume", "state-health", True)},
        )

    disabled = json.loads(json.dumps(record))
    disabled["Config"]["Healthcheck"] = {"Test": ["NONE"]}
    PROBE["validate_two_domain_isolation"](
        disabled,
        run_id="run-health", role="source",
        expected_mounts={"/opt/state": ("volume", "state-health", True)},
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("Driver", "nfs"),
        ("Options", {"type": "nfs"}),
        ("Labels", {"openrepotools.bite4.run": "other-run",
                     "openrepotools.bite4.role": "source-state"}),
        ("Labels", {"openrepotools.bite4.run": "run-volume",
                     "openrepotools.bite4.role": "target-state"}),
        ("Labels", {"openrepotools.bite4.run": "run-volume",
                     "openrepotools.bite4.role": "source-state",
                     "unexpected": "label"}),
    ],
)
def test_two_domain_volume_validation_rejects_driver_options_and_labels(
    field, value, monkeypatch,
):
    record = {
        "Name": "state-volume", "Driver": "local", "Scope": "local",
        "Options": {}, "Mountpoint": "/private/engine/volume",
        "Labels": {
            "openrepotools.bite4.run": "run-volume",
            "openrepotools.bite4.role": "source-state",
        },
    }
    record[field] = value
    globals_map = TWO_DOMAIN["_validate_new_volume"].__globals__
    monkeypatch.setitem(globals_map, "_inspect_volume", lambda name, **_kwargs: record)
    with pytest.raises(RuntimeError, match="plain engine-managed local volume"):
        TWO_DOMAIN["_validate_new_volume"]("state-volume", "run-volume", "source-state")


def test_two_domain_history_custody_binds_parent_prefix_and_tolerates_appends():
    parent_prefix = b'{"parent":"seen"}\n'
    appended_source = parent_prefix + b'{"shutdown":"append"}\n'
    facts = TWO_DOMAIN["_history_custody_facts"](
        {
            "config/session.jsonl": appended_source,
            "config/settings.json": b"source-settings",
        },
        {
            "config/session.jsonl": appended_source + b'{"target":"append"}\n',
            "config/settings.json": b"target-cache-rewrite",
        },
        parent_prefix=parent_prefix,
        parent_history_size=len(parent_prefix),
        parent_history_sha256=hashlib.sha256(parent_prefix).hexdigest(),
    )
    assert facts["identity_linked_parent_history_binding_valid"] is True
    assert facts["identity_linked_parent_history_candidate_count"] == 1
    assert facts["identity_linked_parent_history_prefix_retained"] is True
    assert facts["source_history_prefixes_retained"] is True
    assert facts["other_config_mutation_count"] == 1

    before_release = TWO_DOMAIN["_history_custody_facts"](
        {"config/session.jsonl": appended_source},
        {"config/session.jsonl": appended_source},
        parent_prefix=parent_prefix,
        parent_history_size=len(parent_prefix),
        parent_history_sha256=hashlib.sha256(parent_prefix).hexdigest(),
    )
    assert TWO_DOMAIN["_pre_release_history_reasons"](before_release) == []
    assert before_release["identity_linked_history_sha256"] == hashlib.sha256(
        appended_source
    ).hexdigest()
    assert before_release["target_identity_linked_history_sha256"] == before_release[
        "identity_linked_history_sha256"
    ]

    source_missing_append = TWO_DOMAIN["_history_custody_facts"](
        {"config/session.jsonl": appended_source},
        {"config/session.jsonl": parent_prefix + b'{"target":"append"}\n'},
        parent_prefix=parent_prefix,
        parent_history_size=len(parent_prefix),
        parent_history_sha256=hashlib.sha256(parent_prefix).hexdigest(),
    )
    assert source_missing_append["identity_linked_parent_history_candidate_count"] == 1
    assert source_missing_append["identity_linked_parent_history_prefix_retained"] is False
    assert source_missing_append["source_history_prefixes_retained"] is False
    assert "pre-release-linked-history-copy-mismatch" in TWO_DOMAIN[
        "_pre_release_history_reasons"
    ](source_missing_append)

    ambiguous = TWO_DOMAIN["_history_custody_facts"](
        {
            "config/session.jsonl": appended_source,
            "config/other.jsonl": parent_prefix + b"second candidate\n",
        },
        {},
        parent_prefix=parent_prefix,
        parent_history_size=len(parent_prefix),
        parent_history_sha256=hashlib.sha256(parent_prefix).hexdigest(),
    )
    assert ambiguous["identity_linked_parent_history_candidate_count"] == 2
    assert ambiguous["source_history_prefixes_retained"] is False
    assert "pre-release-identity-linked-history-not-unique" in TWO_DOMAIN[
        "_pre_release_history_reasons"
    ](ambiguous)


def test_two_domain_custodian_classifies_known_tree_violations_only():
    classify = TWO_DOMAIN["_known_custody_failure_code"]
    assert classify("two-domain tree refuses symlinks") == "forbidden-history-symlink"
    assert classify("two-domain copied tree does not match source") == "source-target-copy-mismatch"
    assert classify("parent history evidence unavailable") is None
    assert classify("file size limit exceeded") is None
    assert classify("history file could not be read") is None


def test_two_domain_engine_observer_rejects_unplanned_run_labelled_container_create():
    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    observer.expect_object_creation(kind="container", name="planned-helper", role="copy")
    event_row = {
        "type": "container", "action": "create", "id": "c" * 64,
        "role": "copy", "name": "unexpected-helper", "time_ns": 1,
    }
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="unplanned-run-labelled-.*-create"):
        observer._accept_engine_row(event_row)


def _docker_volume_event(action, identity, *, attributes=None, time_ns=1):
    return {
        "Type": "volume",
        "Action": action,
        "timeNano": time_ns,
        "Actor": {
            "ID": identity,
            "Attributes": dict(attributes or {}),
        },
    }


def test_two_domain_volume_event_parser_accepts_literal_and_prefixed_labels():
    parser = TWO_DOMAIN["TwoDomainObserver"]._decode_volume_engine_event
    literal = parser(_docker_volume_event("create", "state-volume", attributes={
        "name": "state-volume",
        "openrepotools.bite4.run": "run-unique",
        "openrepotools.bite4.role": "source-state",
    }), "run-unique")
    assert literal["id"] == "state-volume"
    assert literal["name"] == "state-volume"
    assert literal["run_label"] == "run-unique"
    assert literal["role_label"] == "source-state"
    assert literal["run_label_matches_run"] is True
    assert literal["label_conflict"] is False

    prefixed = parser(_docker_volume_event("create", "state-volume", attributes={
        "label.openrepotools.bite4.run": "run-unique",
        "label.openrepotools.bite4.role": "source-state",
    }), "run-unique")
    assert prefixed["run_label"] == "run-unique"
    assert prefixed["role_label"] == "source-state"
    assert prefixed["label_conflict"] is False


def test_two_domain_volume_event_requires_consistent_engine_actor_identity():
    parser = TWO_DOMAIN["TwoDomainObserver"]._decode_volume_engine_event

    missing_actor_id = _docker_volume_event(
        "create", "state-volume", attributes={"name": "state-volume"},
    )
    del missing_actor_id["Actor"]["ID"]
    with pytest.raises(RuntimeError, match="volume-event-identity-unavailable"):
        parser(missing_actor_id)

    empty_actor_id = _docker_volume_event("create", "", attributes={
        "name": "state-volume",
    })
    with pytest.raises(RuntimeError, match="volume-event-identity-unavailable"):
        parser(empty_actor_id)

    conflicting_top_level_id = _docker_volume_event("create", "state-volume")
    conflicting_top_level_id["id"] = "different-volume"
    with pytest.raises(RuntimeError, match="volume-event-identity-unavailable"):
        parser(conflicting_top_level_id)

    matching_top_level_id = _docker_volume_event("create", "state-volume")
    matching_top_level_id["id"] = "state-volume"
    assert parser(matching_top_level_id)["id"] == "state-volume"


def test_two_domain_volume_event_without_label_attributes_is_inspected_and_attested(
    monkeypatch,
):
    observer_type = TWO_DOMAIN["TwoDomainObserver"]
    observer = observer_type("positive")
    observer.run_id = "run-unique"
    observer.expect_object_creation(
        kind="volume", name="planned-volume", role="source-state",
    )
    inspected = []

    def valid_volume(name, run_id, role, *, timeout):
        inspected.append((name, run_id, role, timeout))
        return {
            "Name": name, "Driver": "local", "Scope": "local",
            "Options": {},
            "Labels": {
                "openrepotools.bite4.run": run_id,
                "openrepotools.bite4.role": role,
            },
        }

    monkeypatch.setitem(
        observer_type._accept_volume_engine_row.__globals__,
        "_validate_new_volume", valid_volume,
    )
    row = observer_type._decode_volume_engine_event(
        _docker_volume_event("create", "planned-volume", attributes={"driver": "local"})
    )
    assert row["run_label"] is None
    assert row["role_label"] is None
    assert row["name"] is None

    observer._accept_volume_engine_row(row)

    assert inspected == [("planned-volume", "run-unique", "source-state", 8)]
    state = observer.engine_volumes["planned-volume"]
    assert state["create"] == 1
    assert state["role"] == "source-state"
    assert state["attestation_digest"] == TWO_DOMAIN["_digest"]({
        "schema": "openrepotools-bite4-volume-attestation/v1",
        "name": "planned-volume",
        "run_id": "run-unique",
        "role": "source-state",
        "driver": "local",
        "scope": "local",
        "options": {},
        "labels": {
            "openrepotools.bite4.run": "run-unique",
            "openrepotools.bite4.role": "source-state",
        },
    })
    assert ("volume", "planned-volume") not in observer.expected_creates
    report = json.dumps(observer.report(), sort_keys=True)
    assert "planned-volume" not in report
    assert "run-unique" not in report
    assert state["attestation_digest"] in report

    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="volume-create-duplicate-or-name-reuse"):
        observer._accept_volume_engine_row(row)
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="volume-name-reuse"):
        observer.expect_object_creation(
            kind="volume", name="planned-volume", role="source-state",
        )
    observer.expect_object_creation(
        kind="container", name="planned-source", role="source",
        volume_names=("planned-volume",),
    )

    observer._accept_volume_engine_row(TWO_DOMAIN["TwoDomainObserver"]._decode_volume_engine_event(
        _docker_volume_event("mount", "planned-volume", attributes={"driver": "local"})
    ))
    observer._accept_volume_engine_row(TWO_DOMAIN["TwoDomainObserver"]._decode_volume_engine_event(
        _docker_volume_event("unmount", "planned-volume", attributes={"driver": "local"})
    ))
    assert observer.engine_volumes["planned-volume"]["mount"] == 1
    assert observer.engine_volumes["planned-volume"]["unmount"] == 1
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="unplanned-volume-mount"):
        observer._accept_volume_engine_row(TWO_DOMAIN["TwoDomainObserver"]._decode_volume_engine_event(
            _docker_volume_event("mount", "planned-volume", attributes={"driver": "local"})
        ))


def test_two_domain_volume_observer_ignores_unrelated_unlabelled_events_without_retaining_them():
    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    observer.run_id = "run-unique"
    observer.expect_object_creation(
        kind="volume", name="planned-volume", role="source-state",
    )
    unrelated = TWO_DOMAIN["TwoDomainObserver"]._decode_volume_engine_event(
        _docker_volume_event("create", "unrelated-volume", attributes={"driver": "local"})
    )
    observer._accept_volume_engine_row(unrelated)
    assert observer.engine_volumes == {}
    assert observer.events == []
    assert observer.private_values == []
    assert observer.expected_creates == {
        ("volume", "planned-volume"): ("source-state", 0),
    }

    unrelated_conflicting_labels = TWO_DOMAIN["TwoDomainObserver"]._decode_volume_engine_event(
        _docker_volume_event("create", "another-volume", attributes={
            "openrepotools.bite4.run": "other-run-a",
            "label.openrepotools.bite4.run": "other-run-b",
        }),
        "run-unique",
    )
    assert unrelated_conflicting_labels["label_conflict"] is True
    observer._accept_volume_engine_row(unrelated_conflicting_labels)
    assert observer.engine_volumes == {}
    assert observer.events == []

    unexpected_run_labelled = dict(unrelated)
    unexpected_run_labelled["run_label"] = "run-unique"
    unexpected_run_labelled["role_label"] = "source-state"
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="unplanned-run-labelled-volume-event"):
        observer._accept_volume_engine_row(unexpected_run_labelled)


def test_two_domain_volume_attestation_mismatch_is_a_known_violation(monkeypatch):
    observer_type = TWO_DOMAIN["TwoDomainObserver"]
    observer = observer_type("positive")
    observer.run_id = "run-unique"
    observer.expect_object_creation(
        kind="volume", name="planned-volume", role="source-state",
    )

    def invalid_volume(*_args, **_kwargs):
        raise RuntimeError("run fixture volume is not a plain engine-managed local volume")

    monkeypatch.setitem(
        observer_type._accept_volume_engine_row.__globals__,
        "_validate_new_volume", invalid_volume,
    )
    row = observer_type._decode_volume_engine_event(
        _docker_volume_event("create", "planned-volume", attributes={"driver": "local"})
    )
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="volume-event-attestation-mismatch"):
        observer._accept_volume_engine_row(row)
    assert observer.engine_volumes == {}
    assert observer.volume_create_attesting == set()
    assert ("volume", "planned-volume") in observer.expected_creates


@pytest.mark.parametrize(
    ("run_label", "role_label", "expected_code"),
    [
        ("another-run", "source-state", "volume-event-run-label-conflict"),
        ("run-unique", "target-state", "volume-event-role-label-conflict"),
    ],
)
def test_two_domain_volume_event_rejects_conflicting_optional_labels(
    run_label, role_label, expected_code,
):
    observer_type = TWO_DOMAIN["TwoDomainObserver"]
    observer = observer_type("positive")
    observer.run_id = "run-unique"
    observer.expect_object_creation(
        kind="volume", name="planned-volume", role="source-state",
    )
    row = {
        "type": "volume", "action": "create", "id": "planned-volume",
        "name": "planned-volume", "run_label": run_label,
        "role_label": role_label, "time_ns": 1,
    }
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match=expected_code):
        observer._accept_volume_engine_row(row)


def test_two_domain_volume_observer_requires_removal_intent_and_confirms_absence(
    monkeypatch,
):
    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    observer.run_id = "run-unique"
    observer.custody_result_persisted = True
    observer.ensure_engine_healthy = lambda: None
    volume_name = "planned-volume"
    attestation_digest = "a" * 64
    observer.engine_volumes[volume_name] = {
        "role": "source-state", "create": 1, "mount": 1, "unmount": 1,
        "destroy": 0, "attestation_digest": attestation_digest,
        "absence_confirmed": False,
    }
    monkeypatch.setitem(
        TWO_DOMAIN["TwoDomainObserver"]._accept_volume_engine_row.__globals__,
        "_volume_absent", lambda name, *, timeout: name == volume_name and timeout == 8,
    )
    destroy = TWO_DOMAIN["TwoDomainObserver"]._decode_volume_engine_event(
        _docker_volume_event("destroy", volume_name, attributes={"driver": "local"})
    )
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="volume-destroy-without-removal-intent"):
        observer._accept_volume_engine_row(destroy)

    removal_digest = "b" * 64
    observer("run-volume-remove-intent", volume_name, {
        "digest": removal_digest, "role": "source-state",
    })
    observer._accept_volume_engine_row(destroy)
    observer("run-volume-removed", volume_name, {
        "digest": removal_digest, "role": "source-state",
    })
    assert observer.engine_volumes[volume_name]["destroy"] == 1
    assert observer.engine_volumes[volume_name]["absence_confirmed"] is True
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="volume-event-after-destroy"):
        observer._accept_volume_engine_row(destroy)


def test_two_domain_engine_observer_starts_and_checks_both_event_streams(monkeypatch):
    commands = []

    class FakeProcess:
        def __init__(self):
            self.alive = True

        def poll(self):
            return None if self.alive else 1

    processes = []

    def fake_popen(command, **_kwargs):
        commands.append(tuple(command))
        process = FakeProcess()
        processes.append(process)
        return process

    class FakeThread:
        def __init__(self, *, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon
            self.started = False

        def start(self):
            self.started = True

    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    monkeypatch.setattr(TWO_DOMAIN["subprocess"], "Popen", fake_popen)
    monkeypatch.setattr(TWO_DOMAIN["threading"], "Thread", FakeThread)
    observer.start_engine_stream("run-unique")
    assert len(commands) == 2
    container_command, volume_command = commands
    assert ("--filter", "type=container") == tuple(container_command[
        container_command.index("--filter"):container_command.index("--filter") + 2
    ])
    assert any(value.startswith("label=openrepotools.bite4.run=") for value in container_command)
    assert ("--filter", "type=volume") == tuple(volume_command[
        volume_command.index("--filter"):volume_command.index("--filter") + 2
    ])
    assert not any("label=openrepotools.bite4.run=" in value for value in volume_command)
    assert observer.engine_reader.started is True
    assert observer.volume_reader.started is True
    observer.ensure_engine_healthy()
    processes[1].alive = False
    with pytest.raises(RuntimeError, match="exited early"):
        observer.ensure_engine_healthy()


def test_two_domain_engine_observer_stops_first_stream_if_second_cannot_start(monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, *, timeout):
            assert timeout == 5

    process = FakeProcess()
    calls = []

    def failing_popen(command, **_kwargs):
        calls.append(tuple(command))
        if len(calls) == 1:
            return process
        raise OSError("volume stream unavailable")

    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    monkeypatch.setattr(TWO_DOMAIN["subprocess"], "Popen", failing_popen)
    with pytest.raises(OSError, match="volume stream unavailable"):
        observer.start_engine_stream("run-unique")
    assert len(calls) == 2
    assert process.terminated is True


def _two_domain_seed_pre_release_inventory(observer):
    observer.source_engine_destroyed = True
    observer.source_removed = True
    observer.copy_verified = True
    rows = {
        "source-id": ("source", 1),
        "copy-id": ("copy", 1),
        "verify-id": ("verify", 0),
        "custodian-id": ("custodian", 0),
    }
    for identity, (role, writable_mount_count) in rows.items():
        observer.engine_containers[identity] = {
            "role": role, "create": 1, "start": 1, "die": 1, "destroy": 1,
        }
        observer.harness_container_roles[identity] = role
        observer.engine_container_writable_mounts[identity] = writable_mount_count
        observer.mount_witness_attestations[identity] = {
            "role": role,
            "capture_digests": [
                hashlib.sha256((identity + "-before-upload").encode()).hexdigest(),
                hashlib.sha256((identity + "-before-work").encode()).hexdigest(),
            ],
        }
    observer.engine_container_volumes.update({
        "source-id": ("source-volume",),
        "copy-id": ("source-volume", "target-volume"),
        "verify-id": ("source-volume", "target-volume"),
        "custodian-id": ("source-volume", "target-volume"),
    })
    observer.planned_volume_mount_counts.update({
        "source-volume": 4, "target-volume": 3,
    })
    observer.engine_volumes.update({
        "source-volume": {
            "role": "source-state", "create": 1, "mount": 4, "unmount": 4,
            "destroy": 0, "attestation_digest": "a" * 64,
            "absence_confirmed": False,
        },
        "target-volume": {
            "role": "target-state", "create": 1, "mount": 3, "unmount": 3,
            "destroy": 0, "attestation_digest": "b" * 64,
            "absence_confirmed": False,
        },
    })
    observer.harness_volume_roles.update({
        "source-volume": "source-state", "target-volume": "target-state",
    })


def test_two_domain_pre_release_inventory_requires_no_live_writers_or_rw_helpers(
    monkeypatch,
):
    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    _two_domain_seed_pre_release_inventory(observer)
    observer_type = TWO_DOMAIN["TwoDomainObserver"]
    monkeypatch.setattr(observer_type, "ensure_engine_healthy", lambda self: None)
    globals_map = observer_type.verify_pre_release_inventory.__globals__
    monkeypatch.setitem(globals_map, "_container_ids_for_run", lambda _run: [])
    monkeypatch.setitem(
        globals_map, "_volume_names_for_run",
        lambda _run: ["source-volume", "target-volume"],
    )
    observer.pre_release_history_verified = True
    summary = observer.verify_pre_release_inventory(
        run_id="run-1", source_volume="source-volume", target_volume="target-volume",
    )
    assert observer.pre_release_inventory_ready is True
    assert summary["inventory_digest"] == observer.pre_release_inventory_digest
    assert summary["inventory_digest"] == TWO_DOMAIN["_digest"]({
        key: value for key, value in summary.items() if key != "inventory_digest"
    })
    assert summary["volume_attestation_digests"] == ["a" * 64, "b" * 64]
    assert summary["volume_lifecycle"] == {
        "source-state": {
            "attestation_digest": "a" * 64,
            "expected_mount_count": 4,
            "mount_count": 4,
            "unmount_count": 4,
        },
        "target-state": {
            "attestation_digest": "b" * 64,
            "expected_mount_count": 3,
            "mount_count": 3,
            "unmount_count": 3,
        },
    }
    serialized = json.dumps(summary, sort_keys=True)
    assert "source-id" not in serialized
    assert "copy-id" not in serialized
    mounts = TWO_DOMAIN["_custodian_mounts"]
    assert mounts("source-volume", "target-volume", "pre-release") == {
        "/source": ("source-volume", False),
        "/target": ("target-volume", False),
    }
    assert mounts("source-volume", "target-volume", "verify")["/target"][1] is False
    assert mounts("source-volume", "target-volume", "copy")["/target"][1] is True

    live_observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    _two_domain_seed_pre_release_inventory(live_observer)
    monkeypatch.setitem(
        globals_map, "_container_ids_for_run", lambda _run: ["unexpected-live-id"],
    )
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="potential-writer-remains"):
        live_observer.verify_pre_release_inventory(
            run_id="run-1", source_volume="source-volume", target_volume="target-volume",
        )


def test_two_domain_pre_release_waits_for_delayed_volume_unmount_before_snapshot(
    monkeypatch,
):
    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    _two_domain_seed_pre_release_inventory(observer)
    observer.engine_volumes["source-volume"]["unmount"] = 3
    health_checks = []
    observer.ensure_engine_healthy = lambda: health_checks.append("healthy")
    globals_map = TWO_DOMAIN["TwoDomainObserver"].verify_pre_release_inventory.__globals__
    monkeypatch.setitem(globals_map, "_container_ids_for_run", lambda _run: [])
    monkeypatch.setitem(
        globals_map, "_volume_names_for_run",
        lambda _run: ["source-volume", "target-volume"],
    )

    delayed_unmount = TWO_DOMAIN["TwoDomainObserver"]._decode_volume_engine_event(
        _docker_volume_event("unmount", "source-volume", attributes={"driver": "local"})
    )
    waits = []

    def deliver_after_container_stream_woke(_remaining):
        waits.append(True)
        observer._accept_volume_engine_row(delayed_unmount)

    observer.condition.wait = deliver_after_container_stream_woke
    observer.pre_release_history_verified = True
    summary = observer.verify_pre_release_inventory(
        run_id="run-1", source_volume="source-volume", target_volume="target-volume",
        mount_wait_timeout=1.0,
    )
    assert waits == [True]
    assert len(health_checks) >= 3
    assert summary["volume_lifecycle"]["source-state"]["unmount_count"] == 4


@pytest.mark.parametrize("failed_stream", ["engine_process", "volume_process"])
def test_two_domain_pre_release_mount_wait_checks_both_streams(
    failed_stream,
):
    class FakeProcess:
        def __init__(self):
            self.alive = True

        def poll(self):
            return None if self.alive else 1

    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    _two_domain_seed_pre_release_inventory(observer)
    observer.engine_volumes["source-volume"]["unmount"] = 3
    engine_process = FakeProcess()
    volume_process = FakeProcess()
    observer.engine_process = engine_process
    observer.volume_process = volume_process

    def stop_one_stream(_remaining):
        getattr(observer, failed_stream).alive = False

    observer.condition.wait = stop_one_stream
    with pytest.raises(RuntimeError, match="external Docker event observer exited early"):
        observer._wait_for_planned_volume_lifecycle(timeout=1.0)


def test_two_domain_pre_release_mount_wait_is_bounded():
    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    _two_domain_seed_pre_release_inventory(observer)
    observer.engine_volumes["source-volume"]["unmount"] = 3
    observer.ensure_engine_healthy = lambda: None

    with pytest.raises(RuntimeError, match="pre-release-volume-mount-events-are-incomplete"):
        observer._wait_for_planned_volume_lifecycle(timeout=0.01)


def _two_domain_startup_gate_case(
    *,
    source_status="stopped",
    event_overrides=None,
    omit_task_type=False,
    extra_startup_frames=(),
    startup_results=None,
    startup_arrival=None,
    startup_activity=False,
    reader_error=False,
    unparsed_frames=0,
    partial_frames=0,
):
    parent = "session-source"
    invocation = "source-invocation-private"
    _, seed_envelope = _native_source_terminal_seed_envelope(
        parent=parent,
        invocation=invocation,
        terminal_status=source_status,
    )
    parent_digest = PROBE["digest"](parent)
    invocation_digest = PROBE["digest"](invocation)
    validated = PROBE["validate_native_task_source_terminal_seed_envelope"](
        seed_envelope,
        expected_parent_uuid_digest=parent_digest,
        expected_source_invocation_digest=invocation_digest,
    )
    target = _native_lifecycle_runtime(
        phase="target/startup",
        provenance="target-observed",
        seed=validated["terminal_event"],
    )
    target.update({
        "source_identity": None,
        "native_task_source_identity_digests": validated[
            "source_identity_digests"
        ],
        "native_task_source_terminal_seed": validated["terminal_event"],
        "native_task_seed_provenance": "source-terminal-seed",
        "startup_observation_active": True,
        "startup_parent_session_id": parent,
        "startup_activity_observed": bool(startup_activity),
        "startup_activity_kinds": [],
        "startup_other_lifecycle_events": 0,
        "startup_unexpected_frame_count": 0,
        "startup_unclassified_lifecycle_count": 0,
        "startup_result_count": 0,
        "startup_result_origins": [],
        "startup_result_origin_overflow": False,
        "startup_result_error_count": 0,
        "startup_result_parent_session_match_count": 0,
        "startup_result_parent_session_mismatch_count": 0,
        "startup_result_parent_session_id_digest": None,
        "startup_partial_frames": partial_frames,
        "query_partial_frames": 0,
        "read_failed": False,
        "unparsed_frames": unparsed_frames,
    })
    task_event = {
        "type": "system",
        "subtype": "task_notification",
        "status": "stopped",
        "session_id": parent,
        "task_id": "task-source-private",
        "uuid": "event-target-private",
    }
    if not omit_task_type:
        # The pinned target notification can carry null here; the source
        # started event, not this optional field, proves local_agent.
        task_event["task_type"] = None
    if isinstance(event_overrides, dict):
        task_event.update(event_overrides)
    PROBE["observe_frame"](task_event, target)
    frames = list(extra_startup_frames)
    if startup_results is None:
        startup_results = [{
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "origin": {"kind": "task-notification"},
            "session_id": parent,
            "result": "startup result",
        }]
    frames.extend(startup_results)
    for frame in frames:
        PROBE["observe_frame"](frame, target)
    target["startup_observation_active"] = False

    gateway = PROBE["GatewayState"]()
    gateway.set_phase("target-held")
    gateway.begin_startup_observation()
    if startup_arrival is not None:
        arrival_kind = startup_arrival
        if arrival_kind == "parent":
            arrival_index = gateway.observe_messages_arrival(
                agent_header_present=False,
            )
            gateway.complete_messages_arrival(arrival_index)
        elif arrival_kind == "child":
            arrival_index = gateway.observe_messages_arrival(
                agent_header_present=True,
            )
            gateway.complete_messages_arrival(arrival_index)
        elif arrival_kind == "in-flight":
            gateway.observe_messages_arrival(agent_header_present=False)
        elif arrival_kind == "other-route":
            gateway.observe_other_request_arrival("/v1/messages/count_tokens")
        elif arrival_kind == "overflow":
            for _ in range(PROBE["MAX_REQUESTS"] + 2):
                gateway.observe_messages_arrival(agent_header_present=False)
        else:
            raise AssertionError("unknown test startup arrival selector")
    startup_arrivals = gateway.close_startup_observation()
    lifecycle = PROBE["snapshot_native_task_lifecycle"](target)
    observation = {
        "initialize_succeeded": True,
        "target_alive": True,
        "same_parent_session": True,
        "resume_spec_bound": True,
        "source_manifest_bound": True,
        "native_task_source_terminal_seed": seed_envelope,
        "parent_uuid_digest": parent_digest,
        "source_invocation_digest": invocation_digest,
        "startup_native_task_lifecycle": lifecycle,
        "startup_request_observation": startup_arrivals,
        "startup_activity_observed": target["startup_activity_observed"],
        "startup_other_lifecycle_events": target["startup_other_lifecycle_events"],
        "startup_unexpected_frame_count": target["startup_unexpected_frame_count"],
        "reader_error": bool(reader_error),
        "unparsed_frames": target["unparsed_frames"],
        "partial_frames": target["startup_partial_frames"],
        "unclassified_lifecycle_events": target[
            "startup_unclassified_lifecycle_count"
        ],
        "startup_result_count": target["startup_result_count"],
        "startup_result_origins": target["startup_result_origins"],
        "startup_result_origin_overflow": target[
            "startup_result_origin_overflow"
        ],
        "startup_result_error_count": target["startup_result_error_count"],
        "startup_result_parent_session_match_count": target[
            "startup_result_parent_session_match_count"
        ],
        "startup_result_parent_session_mismatch_count": target[
            "startup_result_parent_session_mismatch_count"
        ],
        "startup_result_parent_session_id_digest": target[
            "startup_result_parent_session_id_digest"
        ],
    }
    return observation, target


def test_two_domain_diagnostic_startup_admits_exact_stopped_terminal_correlation():
    observation, _target = _two_domain_startup_gate_case()
    decision = PROBE["assess_two_domain_terminal_task_query_gate"](observation)

    assert decision["history_query_mode"] == PROBE[
        "TWO_DOMAIN_HISTORY_QUERY_MODE"
    ]
    assert decision["history_query_allowed"] is True
    assert decision["terminal_task_correlation_only"] is True
    assert decision["support_claim"] is False
    assert decision["reason_codes"] == []
    event = observation["startup_native_task_lifecycle"]["events"][0]
    assert event["task_type"] is None
    assert observation["startup_native_task_lifecycle"]["event_origins"] == [{
        "observation_sequence": 1,
        "origin_kind": "task-notification",
    }]


def test_two_domain_diagnostic_accepts_sdk_omission_of_target_task_type():
    observation, _target = _two_domain_startup_gate_case(omit_task_type=True)
    decision = PROBE["assess_two_domain_terminal_task_query_gate"](observation)

    assert decision["history_query_allowed"] is True
    assert observation["startup_native_task_lifecycle"]["events"][0][
        "task_type"
    ] is None


def test_two_domain_diagnostic_keeps_replay_compatible_event_class_unpromoted():
    observation, _target = _two_domain_startup_gate_case(
        event_overrides={"uuid": "event-terminal-private"},
    )
    decision = PROBE["assess_two_domain_terminal_task_query_gate"](observation)

    assert observation["startup_native_task_lifecycle"]["events"][0][
        "correlation_class"
    ] == "replay-compatible"
    assert decision["history_query_allowed"] is True
    assert decision["terminal_task_correlation_only"] is True
    assert decision["support_claim"] is False


@pytest.mark.parametrize(
    "case,reason",
    [
        ({"source_status": "completed"}, "source-terminal-seed-is-not-exact-stopped-task"),
        ({"event_overrides": {"status": "completed"}}, "startup-task-notification-is-not-exact-stopped-correlation"),
        ({"event_overrides": {"task_type": "remote_agent"}}, "startup-task-notification-is-not-exact-stopped-correlation"),
        ({"event_overrides": {"origin": {"kind": "system"}}}, "startup-task-notification-origin-unknown-or-conflicting"),
        ({"event_overrides": {"session_id": "other-session"}}, "startup-task-session-identity-not-source-matched"),
        ({"event_overrides": {"task_id": "other-task"}}, "startup-task-task-identity-not-source-matched"),
        ({"startup_results": []}, "startup-task-notification-result-not-observed-exactly-once"),
        ({"startup_results": [{"type": "result", "subtype": "success", "is_error": False, "origin": {"kind": "human"}, "session_id": "session-source", "result": "ok"}]}, "startup-task-notification-result-not-observed-exactly-once"),
        ({"startup_results": [{"type": "result", "subtype": "success", "is_error": False, "origin": {"kind": "task-notification"}, "session_id": "other-session", "result": "ok"}]}, "startup-result-parent-session-not-correlated"),
        ({"startup_results": [{"type": "result", "subtype": "success", "is_error": False, "origin": {"kind": "task-notification"}, "session_id": "session-source", "terminal_reason": "aborted_streaming", "result": "ok"}]}, "startup-error-result-observed"),
        ({"startup_results": [{"type": "result", "subtype": "success", "is_error": False, "origin": {"kind": "task-notification"}, "session_id": "session-source", "deferred_tool_use": {"id": "hidden"}, "result": "ok"}]}, "startup-error-result-observed"),
        ({"extra_startup_frames": [{"type": "system", "subtype": "task_progress", "task_type": "local_agent", "status": "running", "session_id": "session-source", "task_id": "task-source-private"}]}, "startup-native-task-event-count-not-one"),
        ({"extra_startup_frames": [{"type": "assistant", "message": {"role": "assistant", "content": "extra"}}]}, "startup-assistant-or-tool-activity-observed"),
        ({"extra_startup_frames": ["not a parsed frame"]}, "startup-unparsed-frame-count-invalid-or-nonzero"),
        ({"startup_arrival": "parent"}, "startup-request-arrival-count-not-zero"),
        ({"startup_arrival": "child"}, "startup-request-arrival-count-not-zero"),
        ({"startup_arrival": "in-flight"}, "startup-in-flight-count-not-zero"),
        ({"startup_arrival": "other-route"}, "startup-request-arrival-count-not-zero"),
        ({"startup_arrival": "overflow"}, "startup-request-arrival-overflow-or-unknown"),
        ({"reader_error": True}, "startup-reader-error-or-unknown"),
        ({"partial_frames": 1}, "startup-partial-frame-count-invalid-or-nonzero"),
    ],
)
def test_two_domain_diagnostic_startup_refuses_adversarial_evidence(case, reason):
    observation, _target = _two_domain_startup_gate_case(**case)
    decision = PROBE["assess_two_domain_terminal_task_query_gate"](observation)

    assert decision["history_query_allowed"] is False
    assert reason in decision["reason_codes"]


def _two_domain_diagnostic_history_request(nonce):
    return {
        "model": PROBE["EXPECTED_MODEL"],
        "messages": [
            {"role": "user", "content": PROBE["SOURCE_PROMPT_MARKER"]},
            {
                "role": "assistant",
                "content": [{
                    "type": "tool_use",
                    "id": PROBE["SOURCE_AGENT_TOOL_ID"],
                    "name": "Agent",
                    "input": {"subagent_type": PROBE["SOURCE_AGENT_NAME"]},
                }],
            },
            {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": PROBE["SOURCE_AGENT_TOOL_ID"],
                    "content": "accepted",
                }],
            },
            {"role": "user", "content": "Query token: " + nonce},
        ],
    }


def test_two_domain_diagnostic_gateway_requires_one_same_request_witness_and_write():
    state = PROBE["GatewayState"]()
    state.set_phase("target-held")
    state.begin_startup_observation()
    startup = state.close_startup_observation()
    assert startup["request_arrival_count"] == 0
    assert startup["closed"] is True

    nonce = "private-query-nonce-0123456789abcdef"
    challenge = "separate-response-challenge-fedcba9876543210"
    assert nonce != challenge
    state.configure_history_query(nonce, challenge)
    state.set_phase("target-diagnostic-query")
    arrival = state.observe_messages_arrival(agent_header_present=False)
    request = _two_domain_diagnostic_history_request(nonce)
    facts = state.inspect_diagnostic_history_query(
        request,
        arrival_index=arrival,
        child=False,
        agent_header_present=False,
        model_ok=True,
        authorization_ok=True,
    )
    assert facts["valid"] is True
    assert facts["history_order_valid"] is True
    assert facts["source_agent_tool_use_count"] == 1
    assert facts["source_agent_tool_result_count"] == 1
    plan = state.response(
        child=False,
        model_ok=True,
        authorization_ok=True,
        agent_header_present=False,
        arrival_index=arrival,
        diagnostic_query_body_valid=facts["valid"],
    )
    assert plan["kind"] == "diagnostic-query-challenge"
    assert plan["response_challenge"] == challenge
    state.mark_history_query_response_write(
        arrival_index=arrival,
        response_message_id="gateway-message-private",
        succeeded=True,
    )
    state.complete_messages_arrival(arrival)
    witness = state.close_history_query_window()
    arrivals = state.request_arrival_report()

    assert witness["request_count"] == 1
    assert witness["request_valid"] is True
    assert witness["response_write_count"] == 1
    assert witness["response_write_succeeded"] is True
    assert witness["response_write_failed"] is False
    assert witness["response_challenge_sha256"] == PROBE["digest"](challenge)
    assert witness["query_nonce_sha256"] == PROBE["digest"](nonce)
    assert witness["response_message_id_digest"] == PROBE["digest"](
        "gateway-message-private"
    )
    assert arrivals == {
        "arrival_count": 1,
        "arrival_count_by_phase_route": {
            "target-diagnostic-query": {"/v1/messages": 1},
        },
        "in_flight_count": 0,
        "overflow": False,
    }


@pytest.mark.parametrize(
    "mutation,fields",
    [
        ("split", {"request_count": 2}),
        ("same-message-order", {"history_order_valid": False}),
        ("wrong-role", {"parent_request": False}),
        ("child", {"parent_request": False}),
        ("model", {"model_expected": False}),
        ("authorization", {"dummy_authorization": False}),
        ("nonce-first", {"history_order_valid": False}),
        ("nested-use", {"same_request_source_agent_history": False}),
        ("extra-tool", {"all_tool_use_count": 2}),
        ("trailing-message", {"history_order_valid": False}),
    ],
)
def test_two_domain_diagnostic_gateway_rejects_split_or_malformed_facts(
    mutation, fields,
):
    state = PROBE["GatewayState"]()
    state.configure_history_query(
        "private-query-nonce-0123456789abcdef",
        "separate-response-challenge-fedcba9876543210",
    )
    state.set_phase("target-diagnostic-query")
    nonce = state.history_query_nonce
    request = _two_domain_diagnostic_history_request(nonce)
    if mutation == "split":
        source_history = copy.deepcopy(request)
        source_history["messages"] = source_history["messages"][:3]
        nonce_only = copy.deepcopy(request)
        nonce_only["messages"] = [request["messages"][-1]]
        first = state.inspect_diagnostic_history_query(
            source_history,
            arrival_index=1,
            child=False,
            agent_header_present=False,
            model_ok=True,
            authorization_ok=True,
        )
        second = state.inspect_diagnostic_history_query(
            nonce_only,
            arrival_index=2,
            child=False,
            agent_header_present=False,
            model_ok=True,
            authorization_ok=True,
        )
        witness = second
        assert first["valid"] is False
    else:
        if mutation == "same-message-order":
            request["messages"][1]["content"].append({
                "type": "tool_result",
                "tool_use_id": PROBE["SOURCE_AGENT_TOOL_ID"],
                "content": "same-role is not the native result",
            })
            request["messages"][2]["content"] = "tool result moved"
        elif mutation == "nonce-first":
            request["messages"][0], request["messages"][-1] = (
                request["messages"][-1], request["messages"][0],
            )
        elif mutation == "nested-use":
            request["messages"][1]["content"][0]["input"] = {
                "hidden": {"type": "tool_use", "id": "fake"},
            }
        elif mutation == "extra-tool":
            request["messages"][1]["content"].append({
                "type": "tool_use", "id": "extra", "name": "Bash", "input": {},
            })
        elif mutation == "trailing-message":
            request["messages"].append({
                "role": "user", "content": "message after the nonce",
            })
        witness = state.inspect_diagnostic_history_query(
            request,
            arrival_index=1,
            child=mutation == "child",
            agent_header_present=mutation in {"child", "wrong-role"},
            model_ok=mutation != "model",
            authorization_ok=mutation != "authorization",
        )

    assert witness["valid"] is False
    for name, value in fields.items():
        if name == "request_count":
            assert state.history_query_request_count == value
        else:
            assert witness[name] == value


def test_two_domain_diagnostic_gateway_keeps_unexpected_startup_request_visible():
    state = PROBE["GatewayState"]()
    state.set_phase("target-held")
    state.begin_startup_observation()
    arrival = state.observe_messages_arrival(agent_header_present=False)
    plan = state.response(
        child=False,
        model_ok=True,
        authorization_ok=True,
        agent_header_present=False,
        arrival_index=arrival,
        diagnostic_query_body_valid=True,
    )
    state.complete_messages_arrival(arrival)
    startup = state.close_startup_observation()

    assert plan["kind"] == "held-error"
    assert startup["closed"] is True
    assert startup["request_arrival_count"] == 1
    assert startup["parent_arrival_count"] == 1
    assert startup["in_flight_count"] == 0


def test_two_domain_diagnostic_json_parser_refuses_duplicate_keys():
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        PROBE["_json_object_without_duplicate_keys"]([
            ("model", "first"), ("model", "shadow"),
        ])


def _two_domain_query_observer_runtime(*, active=True):
    runtime = _native_lifecycle_runtime(
        phase="target/query",
        provenance="target-observed",
    )
    runtime.update({
        "successful_result_count": 0,
        "successful_parent_result_count": 0,
        "unclassified_control_subtype_count": 0,
        "startup_observation_active": False,
        "history_query_observation_active": active,
        "history_query_parent_session_id": "parent-session-private",
        "history_query_challenge": "response-challenge-private",
        "history_query_frame_count": 0,
        "history_query_result_count": 0,
        "history_query_exact_parent_human_result_count": 0,
        "history_query_invalid_result_count": 0,
        "history_query_unexpected_frame_count": 0,
        "history_query_assistant_frame_count": 0,
        "history_query_assistant_message_id_digests": [],
        "history_query_assistant_message_id_missing_count": 0,
        "history_query_error_abort_or_tool_seen": False,
    })
    return runtime


def test_two_domain_diagnostic_query_requires_fresh_exact_parent_human_challenge():
    nonce = "fresh-query-token-0123456789abcdef"
    query = PROBE["target_diagnostic_history_query_frame"](nonce)
    assert query["origin"] == {"kind": "human"}
    assert nonce in query["message"]["content"]

    runtime = _two_domain_query_observer_runtime(active=False)
    pre_query_result = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "origin": {"kind": "human"},
        "session_id": "parent-session-private",
        "result": "response-challenge-private",
    }
    PROBE["observe_frame"](pre_query_result, runtime)
    assert runtime["history_query_result_count"] == 0

    runtime["history_query_observation_active"] = True
    PROBE["observe_frame"]({
        "type": "assistant",
        "message": {"role": "assistant", "id": "gateway-response-message"},
    }, runtime)
    PROBE["observe_frame"](pre_query_result, runtime)

    assert runtime["history_query_result_count"] == 1
    assert runtime["history_query_exact_parent_human_result_count"] == 1
    assert runtime["history_query_invalid_result_count"] == 0
    assert runtime["history_query_response_challenge_sha256"] == PROBE["digest"](
        "response-challenge-private"
    )
    assert runtime["history_query_assistant_message_id_digests"] == [
        PROBE["digest"]("gateway-response-message")
    ]
    evidence = {
        key: value for key, value in runtime.items()
        if key != "history_query_challenge"
    }
    encoded = json.dumps(evidence, sort_keys=True)
    assert "gateway-response-message" not in encoded
    assert "response-challenge-private" not in encoded


@pytest.mark.parametrize(
    "mutation",
    [
        {"session_id": "other-parent"},
        {"origin": {"kind": "system"}},
        {"origin": None},
        {"result": "wrong-challenge"},
        {"subtype": "error"},
        {"is_error": True},
        {"terminal_reason": "aborted_streaming"},
        {"deferred_tool_use": {"type": "tool_use"}},
        {"stop_reason": "tool_use"},
        {"error": "aborted"},
    ],
)
def test_two_domain_diagnostic_query_result_refuses_wrong_parent_origin_or_abort(
    mutation,
):
    runtime = _two_domain_query_observer_runtime()
    PROBE["observe_frame"]({
        "type": "assistant",
        "message": {"role": "assistant", "id": "gateway-response-message"},
    }, runtime)
    result = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "origin": {"kind": "human"},
        "session_id": "parent-session-private",
        "result": "response-challenge-private",
    }
    result.update(mutation)
    PROBE["observe_frame"](result, runtime)

    assert runtime["history_query_exact_parent_human_result_count"] == 0
    assert runtime["history_query_invalid_result_count"] == 1
    assert runtime["history_query_error_abort_or_tool_seen"] is (
        "error" in mutation
        or "is_error" in mutation
        or mutation.get("subtype") == "error"
        or "terminal_reason" in mutation
        or "deferred_tool_use" in mutation
        or "stop_reason" in mutation
    )


def test_two_domain_diagnostic_query_rejects_extra_or_malformed_assistant_frames():
    runtime = _two_domain_query_observer_runtime()
    PROBE["observe_frame"]({
        "type": "assistant",
        "message": {"role": "assistant", "id": "first"},
    }, runtime)
    PROBE["observe_frame"]({
        "type": "assistant",
        "message": {"role": "user", "id": "second"},
    }, runtime)
    PROBE["observe_frame"]({
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "origin": {"kind": "human"},
        "session_id": "parent-session-private",
        "result": "response-challenge-private",
    }, runtime)
    PROBE["observe_frame"]({"type": "system", "subtype": "unrequested"}, runtime)

    assert runtime["history_query_assistant_frame_count"] == 2
    assert runtime["history_query_unexpected_frame_count"] == 2
    assert runtime["history_query_exact_parent_human_result_count"] == 0


def test_two_domain_history_query_minimal_legacy_report_does_not_pass():
    complete = {
        "history_query_sent": True,
        "history_query_read_complete": True,
        "successful_result_seen": True,
        "read_failed": False,
        "unparsed_frames": 0,
    }
    assert TWO_DOMAIN["_target_history_query_complete"](complete) is False


def test_two_domain_tree_manifest_and_copy_are_byte_exact(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "config").mkdir()
    (source / "workspace").mkdir()
    (source / "workspace" / "empty-directory").mkdir()
    (source / "config" / "session.jsonl").write_bytes(b"session\n")
    (source / "workspace" / "saved-edit.txt").write_bytes(b"saved edit\n")

    target = tmp_path / "target"
    target.mkdir()
    result = PROBE["copy_two_domain_tree"](source, target)
    source_manifest = PROBE["manifest_two_domain_tree"](source)
    target_manifest = PROBE["manifest_two_domain_tree"](target)

    assert result["exact_match"] is True
    assert source_manifest == target_manifest
    assert source_manifest["file_count"] == 2
    assert source_manifest["directory_count"] == 3
    assert (target / "workspace" / "saved-edit.txt").read_bytes() == b"saved edit\n"
    assert (target / "workspace" / "empty-directory").is_dir()


def test_two_domain_large_config_json_is_copied_and_custodied_byte_exact(tmp_path):
    source = tmp_path / "source-large-config"
    for name in ("config", "workspace", "home", "xdg"):
        (source / name).mkdir(parents=True, exist_ok=True)
    config_prefix = b'{"padding":"'
    config_suffix = b'"}'
    large_config = (
        config_prefix
        + b"x" * (306_896 - len(config_prefix) - len(config_suffix))
        + config_suffix
    )
    assert len(large_config) == 306_896
    assert json.loads(large_config)["padding"].startswith("x")
    (source / "config" / "settings.json").write_bytes(large_config)
    parent_prefix = b'{"session_id":"parent-fixture"}\n'
    source_history = parent_prefix + b'{"event":"source-stop"}\n'
    (source / "config" / "parent.jsonl").write_bytes(source_history)
    (source / "workspace" / "saved-edit.txt").write_bytes(
        PROBE["V1_SAVED_EDIT"]
    )

    target = tmp_path / "target-large-config"
    target.mkdir()
    copied = PROBE["copy_two_domain_tree"](source, target)
    source_manifest = PROBE["manifest_two_domain_tree"](source)
    target_manifest = PROBE["manifest_two_domain_tree"](target)
    source_summary = TWO_DOMAIN["_manifest_summary"](str(source))
    target_summary = TWO_DOMAIN["_manifest_summary"](str(target))

    assert copied["exact_match"] is True
    assert source_manifest == target_manifest
    assert source_summary["manifest_digest"] == target_summary["manifest_digest"]
    large_row = next(
        row for row in source_manifest["entries"]
        if row.get("path") == "config/settings.json"
    )
    assert large_row["size"] == 306_896
    assert (target / "config" / "settings.json").read_bytes() == large_config

    source_files = {
        path: content for kind, path, content in PROBE["_tree_file_bytes"](source)
        if kind == "file" and content is not None
    }
    target_files = {
        path: content for kind, path, content in PROBE["_tree_file_bytes"](target)
        if kind == "file" and content is not None
    }
    custody = TWO_DOMAIN["_history_custody_facts"](
        source_files,
        target_files,
        parent_prefix=parent_prefix,
        parent_history_size=len(parent_prefix),
        parent_history_sha256=hashlib.sha256(parent_prefix).hexdigest(),
    )
    assert custody["identity_linked_parent_history_candidate_count"] == 1
    assert custody["identity_linked_parent_history_prefix_retained"] is True
    assert TWO_DOMAIN["_pre_release_history_reasons"](custody) == []

    final_config = (
        b'{"padding":"'
        + b"y" * (306_896 - len(config_prefix) - len(config_suffix))
        + config_suffix
    )
    (target / "config" / "settings.json").write_bytes(final_config)
    final_files = {
        path: content for kind, path, content in PROBE["_tree_file_bytes"](target)
        if kind == "file" and content is not None
    }
    final_custody = TWO_DOMAIN["_history_custody_facts"](
        source_files,
        final_files,
        parent_prefix=parent_prefix,
        parent_history_size=len(parent_prefix),
        parent_history_sha256=hashlib.sha256(parent_prefix).hexdigest(),
    )
    assert final_custody["identity_linked_parent_history_prefix_retained"] is True
    assert final_custody["other_config_mutation_count"] == 1
    assert TWO_DOMAIN["_manifest_summary"](str(target))["total_bytes"] > 64 * 1024


def test_two_domain_fixture_tree_file_and_total_caps_are_separate_from_history_caps(tmp_path):
    file_cap = PROBE["MAX_TWO_DOMAIN_TREE_FILE_BYTES"]
    tree_cap = PROBE["MAX_TWO_DOMAIN_TREE_BYTES"]
    assert file_cap == 512 * 1024
    assert tree_cap == 2 * 1024 * 1024
    assert PROBE["MAX_HISTORY_CONTENT_BYTES"] == 64 * 1024
    assert PROBE["MAX_HISTORY_SCAN_BYTES"] == 512 * 1024

    file_boundary = tmp_path / "file-boundary"
    file_boundary.mkdir()
    (file_boundary / "at-limit.bin").write_bytes(b"x" * file_cap)
    exact_file = PROBE["manifest_two_domain_tree"](file_boundary)
    assert exact_file["total_bytes"] == file_cap
    assert exact_file["entries"][0]["size"] == file_cap

    file_over = tmp_path / "file-over"
    file_over.mkdir()
    (file_over / "over-limit.bin").write_bytes(b"x" * (file_cap + 1))
    with pytest.raises(RuntimeError, match="file size limit exceeded") as file_error:
        PROBE["manifest_two_domain_tree"](file_over)
    assert TWO_DOMAIN["_known_custody_failure_code"](str(file_error.value)) is None

    total_boundary = tmp_path / "total-boundary"
    total_boundary.mkdir()
    for index in range(4):
        (total_boundary / f"part-{index}.bin").write_bytes(b"x" * file_cap)
    exact_total = PROBE["manifest_two_domain_tree"](total_boundary)
    assert exact_total["total_bytes"] == tree_cap

    total_over = tmp_path / "total-over"
    total_over.mkdir()
    for index in range(4):
        (total_over / f"part-{index}.bin").write_bytes(b"x" * file_cap)
    (total_over / "one-byte-over.bin").write_bytes(b"x")
    with pytest.raises(RuntimeError, match="tree byte limit exceeded") as total_error:
        PROBE["manifest_two_domain_tree"](total_over)
    assert TWO_DOMAIN["_known_custody_failure_code"](str(total_error.value)) is None


def test_two_domain_fixture_tree_limit_does_not_widen_history_prefix_capture(tmp_path):
    assert PROBE["MAX_HISTORY_CONTENT_BYTES"] == 64 * 1024
    (tmp_path / "oversized-parent.jsonl").write_bytes(
        b"x" * (PROBE["MAX_HISTORY_CONTENT_BYTES"] + 1)
    )
    history = PROBE["capture_bounded_history_records"](
        tmp_path, parent_path="oversized-parent.jsonl"
    )
    assert history["parent"]["status"] == "unknown"
    assert history["parent"]["reason"] == "oversized"


def test_two_domain_tree_refuses_symlinks_hardlinks_and_special_files(tmp_path):
    symlink_root = tmp_path / "symlink-tree"
    symlink_root.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    (symlink_root / "escape").symlink_to(target)
    with pytest.raises(RuntimeError, match="symlinks"):
        PROBE["manifest_two_domain_tree"](symlink_root)

    hardlink_root = tmp_path / "hardlink-tree"
    hardlink_root.mkdir()
    original = hardlink_root / "one"
    original.write_text("linked", encoding="utf-8")
    os.link(original, hardlink_root / "two")
    with pytest.raises(RuntimeError, match="hard-linked"):
        PROBE["manifest_two_domain_tree"](hardlink_root)

    fifo_root = tmp_path / "fifo-tree"
    fifo_root.mkdir()
    os.mkfifo(fifo_root / "fifo")
    with pytest.raises(RuntimeError, match="non-regular"):
        PROBE["manifest_two_domain_tree"](fifo_root)


def test_two_domain_intent_ledger_is_private_append_once(tmp_path):
    ledger = PROBE["TwoDomainIntentLedger"](tmp_path / "intents")
    digest = ledger.persist("release", {
        "run_id": "run-1",
        "source_manifest_digest": "a" * 64,
        "parent_uuid_digest": "b" * 64,
    })
    record_path = tmp_path / "intents" / "release.json"
    record = json.loads(record_path.read_text(encoding="ascii"))
    assert record["sha256"] == digest
    assert record_path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(RuntimeError, match="do not replay"):
        ledger.persist("release", {"run_id": "run-1"})


def test_two_domain_engine_event_parser_accepts_docker_actor_labels():
    parser = TWO_DOMAIN["TwoDomainObserver"]._decode_engine_event
    event = {
        "Type": "container",
        "Action": "create",
        "timeNano": 123456789,
        "Actor": {
            "ID": "c" * 64,
            "Attributes": {
                "openrepotools.bite4.run": "run-1",
                "openrepotools.bite4.role": "source",
                "name": "source-fixture",
            },
        },
    }
    assert parser(event, "run-1") == {
        "type": "container",
        "action": "create",
        "id": "c" * 64,
        "role": "source",
        "name": "source-fixture",
        "time_ns": 123456789,
    }

    prefixed = json.loads(json.dumps(event))
    prefixed["Actor"]["Attributes"] = {
        "label.openrepotools.bite4.run": "run-1",
        "label.openrepotools.bite4.role": "source",
    }
    assert parser(prefixed, "run-1")["role"] == "source"
    with pytest.raises(RuntimeError, match="identity-unavailable"):
        parser(event, "different-run")


def test_two_domain_target_create_requires_durable_release_and_launch_intents(
    tmp_path, monkeypatch,
):
    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    monkeypatch.setattr(observer, "ensure_engine_healthy", lambda: None)
    observer.source_engine_destroyed = True
    observer("source-container-removed", "source-container-private-id")
    observer("source-copy-verified", "manifest-private-id")
    observer.pre_release_history_verified = True
    parent_prefix = b'{"parent":"observed"}\n'
    linked_history = parent_prefix + b'{"shutdown":"complete"}\n'
    history_custody_facts = TWO_DOMAIN["_history_custody_facts"](
        {"config/session.jsonl": linked_history},
        {"config/session.jsonl": linked_history},
        parent_prefix=parent_prefix,
        parent_history_size=len(parent_prefix),
        parent_history_sha256=hashlib.sha256(parent_prefix).hexdigest(),
    )
    history_custody_digest = TWO_DOMAIN["_digest"](history_custody_facts)
    inventory_facts = {
        "schema": "openrepotools-bite4-pre-release-inventory/v1",
        "source_destroyed_observed": True,
        "target_absent": True,
        "container_count": 4,
        "container_roles": {"copy": 1, "custodian": 1, "source": 1, "verify": 1},
        "container_identity_digests": ["c" * 64, "d" * 64, "e" * 64, "f" * 64],
        "all_container_lifecycles_complete": True,
        "writable_mount_count": 2,
        "all_writable_mounts_detached": True,
        "live_run_container_count": 0,
        "live_writable_helper_mount_count": 0,
        "volume_count": 2,
        "volume_roles": {"source-state": 1, "target-state": 1},
        "volume_identity_digests": ["1" * 64, "2" * 64],
        "volume_attestation_digests": ["a" * 64, "b" * 64],
        "volume_lifecycle": {
            "source-state": {
                "attestation_digest": "a" * 64,
                "expected_mount_count": 4,
                "mount_count": 4,
                "unmount_count": 4,
            },
            "target-state": {
                "attestation_digest": "b" * 64,
                "expected_mount_count": 3,
                "mount_count": 3,
                "unmount_count": 3,
            },
        },
        "container_mount_witnesses": [
            {
                "role": role,
                "capture_count": 2,
                "container_identity_digest": hashlib.sha256(
                    f"container-{role}".encode()
                ).hexdigest(),
                "witness_set_digest": hashlib.sha256(
                    f"witness-set-{role}".encode()
                ).hexdigest(),
            }
            for role in ("copy", "custodian", "source", "verify")
        ],
        "pending_create_intent_count": 0,
    }
    inventory_facts["container_mount_witnesses_digest"] = TWO_DOMAIN["_digest"](
        inventory_facts["container_mount_witnesses"]
    )
    inventory_digest = TWO_DOMAIN["_digest"](inventory_facts)
    inventory_summary = {**inventory_facts, "inventory_digest": inventory_digest}
    observer.pre_release_inventory_digest = inventory_digest
    observer.pre_release_inventory_ready = True
    secret_parent_uuid = "123e4567-e89b-12d3-a456-426614174000"
    source_invocation = "source-invocation-private"
    _, terminal_seed = _native_source_terminal_seed_envelope(
        parent=secret_parent_uuid, invocation=source_invocation,
    )
    source_phase_report_digest = "c" * 64
    target_profile = {
        "history_query_mode": TWO_DOMAIN["HISTORY_QUERY_MODE"],
        "native_task_source_seed_digest": terminal_seed["seed_digest"],
        "source_phase_report_digest": source_phase_report_digest,
        "source_invocation_digest": hashlib.sha256(source_invocation.encode()).hexdigest(),
    }
    target_spec_fingerprint = "e" * 64
    ledger = TWO_DOMAIN_PROBE.TwoDomainIntentLedger(tmp_path / "private-ledger")
    release_digest, launch_digest = TWO_DOMAIN["_persist_release_and_launch_intents"](
        ledger,
        release_payload={
            "run_id": "run-unique-positive",
            "explicit_release_selected": True,
            "source_invocation": source_invocation,
            "source_invocation_digest": hashlib.sha256(source_invocation.encode()).hexdigest(),
            "source_phase_report_digest": source_phase_report_digest,
            "native_task_source_terminal_seed": terminal_seed,
            "native_task_source_terminal_seed_digest": terminal_seed["seed_digest"],
            "parent_uuid_digest": hashlib.sha256(secret_parent_uuid.encode()).hexdigest(),
            "target_profile": target_profile,
            "target_spec_fingerprint": target_spec_fingerprint,
            "history_query_mode": TWO_DOMAIN["HISTORY_QUERY_MODE"],
            "private_parent_uuid": secret_parent_uuid,
            "pre_release_history_custody_digest": history_custody_digest,
            "pre_release_history_custody": history_custody_facts,
            "pre_release_engine_inventory_digest": inventory_digest,
            "pre_release_engine_inventory": inventory_summary,
            "pre_release_mount_witnesses_digest": inventory_facts[
                "container_mount_witnesses_digest"
            ],
        },
        launch_payload={
            "run_id": "run-unique-positive",
            "parent_uuid_digest": hashlib.sha256(secret_parent_uuid.encode()).hexdigest(),
            "source_invocation_digest": hashlib.sha256(source_invocation.encode()).hexdigest(),
            "source_phase_report_digest": source_phase_report_digest,
            "native_task_source_terminal_seed": terminal_seed,
            "native_task_source_terminal_seed_digest": terminal_seed["seed_digest"],
            "target_spec_fingerprint": target_spec_fingerprint,
            "history_query_mode": TWO_DOMAIN["HISTORY_QUERY_MODE"],
            "pre_release_history_custody_digest": history_custody_digest,
            "pre_release_engine_inventory_digest": inventory_digest,
            "pre_release_mount_witnesses_digest": inventory_facts[
                "container_mount_witnesses_digest"
            ],
        },
        observe=observer,
        parent_uuid=secret_parent_uuid,
        target_identity="target-state-volume-private",
    )
    assert release_digest and launch_digest
    intents_dir = tmp_path / "private-ledger"
    assert (intents_dir / "release.json").is_file()
    assert (intents_dir / "target-launch.json").is_file()
    release_record = json.loads((intents_dir / "release.json").read_text(encoding="ascii"))
    launch_record = json.loads((intents_dir / "target-launch.json").read_text(encoding="ascii"))
    assert release_record["payload"]["pre_release_engine_inventory_digest"] == inventory_digest
    assert launch_record["payload"]["pre_release_engine_inventory_digest"] == inventory_digest
    assert release_record["payload"]["pre_release_engine_inventory"][
        "volume_attestation_digests"
    ] == ["a" * 64, "b" * 64]
    assert release_record["payload"]["pre_release_history_custody_digest"] == history_custody_digest
    assert release_record["payload"]["native_task_source_terminal_seed_digest"] == terminal_seed["seed_digest"]
    assert launch_record["payload"]["native_task_source_terminal_seed_digest"] == terminal_seed["seed_digest"]

    create_attempts = []
    module_globals = TWO_DOMAIN["_create_authorized_target"].__globals__

    def fake_create(**kwargs):
        assert (intents_dir / "release.json").is_file()
        assert (intents_dir / "target-launch.json").is_file()
        create_attempts.append(kwargs["role"])
        observer.expect_object_creation(
            kind="container", name=kwargs["name"], role=kwargs["role"],
            writable_mount_count=1,
        )
        target_id = "f" * 64
        observer._accept_engine_row({
            "type": "container", "action": "create", "id": target_id,
            "role": "target", "name": kwargs["name"], "time_ns": 10,
        })
        return target_id

    monkeypatch.setitem(module_globals, "_create_container", fake_create)
    monkeypatch.setattr(observer, "wait_engine_event", lambda **kwargs: None)
    target_id = TWO_DOMAIN["_create_authorized_target"](
        observer,
        role="target",
        image_id="sha256:" + "a" * 64,
        run_id="run-unique-positive",
        name="private-target-name",
        volume_mounts={},
    )
    assert target_id == "f" * 64
    assert create_attempts == ["target"]
    observer._accept_engine_row({
        "type": "container", "action": "start", "id": target_id,
        "role": "target", "time_ns": 11,
    })
    assert observer.engine_containers[target_id]["start"] == 1
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="duplicate-container-start"):
        observer._accept_engine_row({
            "type": "container", "action": "start", "id": target_id,
            "role": "target", "time_ns": 12,
        })
    public_events = json.dumps(observer.report(), sort_keys=True)
    assert secret_parent_uuid not in public_events
    TWO_DOMAIN["_assert_no_private_values"](
        observer.report(), [secret_parent_uuid, "source-container-private-id",
                            "manifest-private-id", "target-state-volume-private",
                            "f" * 64],
    )
    names = [row["event"] for row in observer.report()]
    assert names.index("explicit-release-persisted") < names.index("target-launch-intent")
    assert names.index("target-launch-intent") < names.index("target-container-created")


def test_two_domain_public_image_id_exception_is_validated_and_field_scoped():
    resolved = "sha256:" + "c" * 64
    report = {"identities": {"image_id": resolved}, "arms": []}
    projection = TWO_DOMAIN["_public_image_id_scan_projection"](report, resolved)
    assert report["identities"]["image_id"] == resolved
    assert projection["identities"]["image_id"] is None
    TWO_DOMAIN["_assert_no_private_values"](projection, [resolved, "/private/sdk"])

    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="public-image-identity-invalid"):
        TWO_DOMAIN["_public_image_id_scan_projection"](report, "py-bench:brett")
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="public-image-identity-mismatch"):
        TWO_DOMAIN["_public_image_id_scan_projection"](
            {"identities": {"image_id": "sha256:" + "d" * 64}}, resolved,
        )
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="public-image-identity-mismatch"):
        TWO_DOMAIN["_public_image_id_scan_projection"](
            {"identities": {"image_id": "py-bench:brett"}}, resolved,
        )
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="private-identifier-in-report"):
        TWO_DOMAIN["_assert_no_private_values"](
            {**projection, "unexpected": resolved}, [resolved],
        )
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="private-identifier-in-report"):
        TWO_DOMAIN["_assert_no_private_values"](
            {"value": "/private/sdk/interpreter"}, ["/private/sdk/interpreter"],
        )
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="private-identifier-in-report"):
        TWO_DOMAIN["_assert_no_private_values"](
            {**projection, "extra": "py-bench:brett"}, ["py-bench:brett"],
        )


@pytest.mark.parametrize(
    "image_ref,leak_resolved_image_id",
    [
        ("py-bench:brett", False),
        ("sha256:" + "c" * 64, False),
        ("py-bench:brett", True),
    ],
)
def test_two_domain_run_experiment_keeps_inconclusive_arm_for_valid_public_image_id(
    tmp_path, monkeypatch, image_ref, leak_resolved_image_id,
):
    module_globals = TWO_DOMAIN["_run_experiment"].__globals__
    resolved_image_id = "sha256:" + "c" * 64
    selected = {
        "selected_cli": "/private/sdk/cli",
        "cli_sha256": "d" * 64,
        "sdk_version": "0.2.153",
    }
    monkeypatch.setitem(module_globals, "_create_private_directory", lambda path: Path(path))
    monkeypatch.setitem(module_globals, "_resolve_image_id", lambda _ref: resolved_image_id)
    monkeypatch.setitem(module_globals, "_host_file_sha256", lambda _path: "d" * 64)
    def fake_run_arm(**kwargs):
        result = {
            "arm": kwargs["arm"],
            "status": "inconclusive",
            "reason_codes": ["startup-task-event-observed"],
            "release_candidate_ready": True,
            "cleanup_complete": False,
            "observer_complete": False,
            "support_claim": False,
        }
        if leak_resolved_image_id:
            result["unexpected_image_id"] = resolved_image_id
        return result

    monkeypatch.setitem(module_globals, "_run_arm", fake_run_arm)
    monkeypatch.setattr(TWO_DOMAIN_PROBE, "_select_runtime", lambda _path: selected)

    args = SimpleNamespace(
        explicit_release=True,
        sdk_python="/private/sdk/python",
        image=image_ref,
        private_artifacts=os.fspath(tmp_path / "artifacts"),
    )
    if leak_resolved_image_id:
        with pytest.raises(
            TWO_DOMAIN["KnownViolation"], match="private-identifier-in-report",
        ):
            TWO_DOMAIN["_run_experiment"](args)
        return

    report = TWO_DOMAIN["_run_experiment"](args)

    assert report["diagnostic_status"] == "INCONCLUSIVE"
    assert report["identities"]["image_id"] == resolved_image_id
    assert report["arms"][0]["status"] == "inconclusive"
    assert report["arms"][0]["reason_codes"] == ["startup-task-event-observed"]
    assert report["arms"][1]["status"] == "not-run"


def test_two_domain_engine_thread_preserves_known_violation_code():
    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="target-engine-create-before-release") as caught:
        observer._accept_engine_row({
            "type": "container", "action": "create", "id": "d" * 64,
            "role": "target", "time_ns": 123,
        })
    observer._record_engine_failure(caught.value)
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="target-engine-create-before-release"):
        observer.ensure_engine_healthy()


def test_two_domain_release_refuses_unbound_pre_release_inventory_digest(tmp_path):
    ledger = TWO_DOMAIN_PROBE.TwoDomainIntentLedger(tmp_path / "unbound-ledger")
    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    with pytest.raises(RuntimeError, match="bound pre-release history and engine inventory"):
        TWO_DOMAIN["_persist_release_and_launch_intents"](
            ledger,
            release_payload={
                "pre_release_history_custody_digest": "a" * 64,
                "pre_release_history_custody": {"valid": True},
                "pre_release_engine_inventory_digest": "b" * 64,
                "pre_release_engine_inventory": {
                    "inventory_digest": "c" * 64,
                    "container_count": 0,
                },
            },
            launch_payload={
                "pre_release_history_custody_digest": "a" * 64,
                "pre_release_engine_inventory_digest": "b" * 64,
            },
            observe=observer,
            parent_uuid="private-parent-uuid",
            target_identity="private-target-id",
        )
    assert not (tmp_path / "unbound-ledger" / "release.json").exists()


def test_two_domain_witnessed_engine_violation_becomes_fail(tmp_path, monkeypatch):
    module_globals = TWO_DOMAIN["_run_arm"].__globals__
    monkeypatch.setitem(module_globals, "_run_arm_impl", lambda **kwargs: _raise_engine_violation(kwargs))
    monkeypatch.setitem(
        module_globals, "_quarantine_run_owned_resources",
        lambda **kwargs: {"reason_codes": [], "volumes_removed": False},
    )
    monkeypatch.setattr(TWO_DOMAIN["TwoDomainObserver"], "start_engine_stream", lambda self, run: None)
    result = TWO_DOMAIN["_run_arm"](
        arm="positive", run_id="run-known-failure",
        image_id="sha256:" + "1" * 64, cli_path="/private/cli",
        selected={}, private_dir=tmp_path / "failure-private",
    )
    assert result["status"] == "fail"
    assert result["reason_codes"] == ["target-engine-create-before-release"]


def _raise_engine_violation(kwargs):
    observer = kwargs["observe"]
    try:
        observer._accept_engine_row({
            "type": "container", "action": "create", "id": "9" * 64,
            "role": "target", "time_ns": 100,
        })
    except TWO_DOMAIN["KnownViolation"] as exc:
        observer._record_engine_failure(exc)
    observer.ensure_engine_healthy()


def test_two_domain_negative_arm_refuses_target_before_docker_create(monkeypatch):
    observer = TWO_DOMAIN["TwoDomainObserver"]("negative")
    monkeypatch.setattr(observer, "ensure_engine_healthy", lambda: None)
    attempts = []
    module_globals = TWO_DOMAIN["_create_authorized_target"].__globals__
    monkeypatch.setitem(module_globals, "_create_container", lambda **kwargs: attempts.append(kwargs))
    with pytest.raises(TWO_DOMAIN["KnownViolation"], match="target-launch-not-authorized"):
        TWO_DOMAIN["_create_authorized_target"](
            observer,
            role="target",
            image_id="sha256:" + "b" * 64,
            run_id="run-negative",
            name="private-target-name",
            volume_mounts={},
        )
    assert attempts == []


def test_two_domain_negative_refusal_requires_prepared_valid_baseline(tmp_path):
    workspace = tmp_path / "source-copy" / "workspace"
    baseline = TWO_DOMAIN_PROBE.StopThenResumeV1Ledger(workspace)
    baseline.prepare(
        parent_identity={"session_id": "source-session-private"},
        pre_stop_history={"candidate": "bounded"},
    )
    baseline.record_source_facts(
        native={
            "interrupt_sent": True,
            "interrupt_receipt": True,
            "child_terminal": True,
            "tool_terminal": True,
            "unknown_effects": [],
            "read_failed": False,
            "unparsed_frames": 0,
            "protocol_errors": [],
        },
        harness={
            "parent_process_exited": True,
            "tracked_processes_excluded": True,
            "pg_kill_observed": False,
        },
    )
    assert baseline.snapshot()["unknown_effect_baseline_valid"] is True

    refusal = TWO_DOMAIN["_negative_release_diagnostic"](
        workspace, binding_digest="d" * 64,
    )
    assert refusal["baseline_valid"] is True
    assert refusal["explicit_release_selected"] is True
    assert refusal["reason_code"] == "unknown-effects"
    assert refusal["authorized"] is False
    assert refusal["release_persisted"] is False
    assert refusal["target_creation_authorized"] is False
    assert refusal["unknown_effect_refusal_demonstrated"] is True


def test_two_domain_arm_failure_persists_abort_before_quarantine_and_sanitizes(
    tmp_path, monkeypatch,
):
    observer_type = TWO_DOMAIN["TwoDomainObserver"]
    monkeypatch.setattr(observer_type, "start_engine_stream", lambda self, run_id: None)
    private_id = "container-private-id-1234567890"
    private_name = "fixture-private-container-name"

    def incomplete_arm(**kwargs):
        tracker = kwargs["tracker"]
        tracker["planned_containers"] = [{
            "name": private_name, "id": private_id, "role": "source", "removed": False,
        }]
        tracker["containers"].append({
            "name": private_name, "id": private_id, "role": "source", "removed": False,
        })
        raise RuntimeError("simulated uncertain source effect")

    module_globals = TWO_DOMAIN["_run_arm"].__globals__
    monkeypatch.setitem(module_globals, "_run_arm_impl", incomplete_arm)
    docker_calls = []
    monkeypatch.setitem(module_globals, "_docker", lambda *args, **kwargs: docker_calls.append(args))

    def fake_quarantine(**kwargs):
        abort_path = tmp_path / "positive-private" / "ledger" / "arm-abort.json"
        assert abort_path.is_file()
        return {
            "discovered": 1, "stopped": 0, "removed": 0, "preserved": 1,
            "reason_codes": ["quarantine-stop-effect-unconfirmed"],
            "observer_event_digest": "a" * 64, "volumes_removed": False,
        }

    monkeypatch.setitem(module_globals, "_quarantine_run_owned_resources", fake_quarantine)
    result = TWO_DOMAIN["_run_arm"](
        arm="positive",
        run_id="run-failure-private-id",
        image_id="sha256:" + "c" * 64,
        cli_path="/private/sdk/cli",
        selected={"sdk_version": "pinned"},
        private_dir=tmp_path / "positive-private",
    )
    assert result["status"] == "inconclusive"
    assert result["cleanup_complete"] is False
    assert result["leftovers"]["manual_review_required"] is True
    assert result["quarantine"]["preserved"] == 1
    assert "quarantine-stop-effect-unconfirmed" in result["reason_codes"]
    assert docker_calls == []
    assert private_id not in json.dumps(result)
    assert private_name not in json.dumps(result)
    abort = json.loads(
        (tmp_path / "positive-private" / "ledger" / "arm-abort.json").read_text()
    )
    assert abort["payload"]["reason_code"] == "effect-or-observer-uncertain"


@pytest.mark.parametrize("status", ["fail", "inconclusive"])
def test_two_domain_normal_unaccepted_arm_result_preserves_volumes(
    tmp_path, monkeypatch, status,
):
    module_globals = TWO_DOMAIN["_finalize_normal_arm_result"].__globals__
    removal_calls = []
    monkeypatch.setitem(
        module_globals, "_remove_run_volumes",
        lambda *args, **kwargs: removal_calls.append((args, kwargs)),
    )

    class Observer:
        def __init__(self):
            self.events = []

        def report(self):
            return list(self.events)

        def __call__(self, event, identity=None, facts=None):
            self.events.append({"event": event, "facts": dict(facts or {})})

    observer = Observer()
    ledger_path = tmp_path / status / "ledger"
    ledger = TWO_DOMAIN_PROBE.TwoDomainIntentLedger(ledger_path)
    tracker = {
        "run_id": "private-run-id",
        "source_volume": "private-source-volume",
        "target_volume": "private-target-volume",
        "containers": [],
        "planned_containers": [],
        "custody_complete": False,
    }
    result = {"status": status, "reason_codes": ["candidate-not-established"]}

    TWO_DOMAIN["_finalize_normal_arm_result"](
        result, ledger=ledger, observer=observer, tracker=tracker,
        run_id=tracker["run_id"], source_volume=tracker["source_volume"],
        target_volume=tracker["target_volume"], observe=observer,
    )

    assert removal_calls == []
    assert tracker["custody_complete"] is False
    assert result["cleanup_complete"] is False
    assert result["leftovers"]["manual_review_required"] is True
    assert set(result["leftovers"]["possible_volume_digests"]) == {
        "source_volume", "target_volume",
    }
    serialized = json.dumps(result)
    assert tracker["source_volume"] not in serialized
    assert tracker["target_volume"] not in serialized
    assert (ledger_path / "arm-result.json").is_file()
    assert not (ledger_path / "cleanup-complete.json").exists()
    assert not (ledger_path / "source-volume-remove.json").exists()
    assert not (ledger_path / "target-volume-remove.json").exists()


def test_two_domain_observed_arm_result_keeps_successful_cleanup_boundary(
    tmp_path, monkeypatch,
):
    module_globals = TWO_DOMAIN["_finalize_normal_arm_result"].__globals__
    removal_calls = []
    monkeypatch.setitem(
        module_globals, "_remove_run_volumes",
        lambda ledger, **kwargs: removal_calls.append((ledger, kwargs)) or True,
    )

    class Observer:
        def report(self):
            return []

        def __call__(self, event, identity=None, facts=None):
            return None

    observer = Observer()
    ledger_path = tmp_path / "observed" / "ledger"
    ledger = TWO_DOMAIN_PROBE.TwoDomainIntentLedger(ledger_path)
    tracker = {"containers": [], "custody_complete": False}
    result = {"status": "observed", "reason_codes": []}

    TWO_DOMAIN["_finalize_normal_arm_result"](
        result, ledger=ledger, observer=observer, tracker=tracker,
        run_id="private-run-id", source_volume="private-source-volume",
        target_volume="private-target-volume", observe=observer,
    )

    assert len(removal_calls) == 1
    assert removal_calls[0][1]["custody_complete"] is True
    assert tracker["custody_complete"] is True
    assert tracker["source_volume_removed"] is True
    assert tracker["target_volume_removed"] is True
    assert result["cleanup_complete"] is True
    assert (ledger_path / "cleanup-complete.json").is_file()


def test_two_domain_negative_refusal_with_bad_final_custody_never_cleans_volumes(
    tmp_path, monkeypatch,
):
    final_custody = {
        "source": {"saved_edit_sha256": "a" * 64},
        "target": {"saved_edit_sha256": "b" * 64},
        "identity_linked_parent_history_candidate_count": 1,
        "identity_linked_parent_history_binding_valid": True,
        "identity_linked_history_size": 64,
        "identity_linked_history_sha256": "c" * 64,
        "identity_linked_parent_history_prefix_retained": False,
    }
    disposition = TWO_DOMAIN["_negative_arm_disposition"](
        refused=True, no_target=True, final_report=final_custody,
    )
    assert disposition["status"] == "fail"
    assert set(disposition["reason_codes"]) == {
        "saved-edit-not-retained", "source-history-prefix-not-retained",
    }

    module_globals = TWO_DOMAIN["_finalize_normal_arm_result"].__globals__
    removal_calls = []
    monkeypatch.setitem(
        module_globals, "_remove_run_volumes",
        lambda *args, **kwargs: removal_calls.append((args, kwargs)),
    )

    class Observer:
        def report(self):
            return []

        def __call__(self, event, identity=None, facts=None):
            return None

    ledger_path = tmp_path / "negative-bad-custody" / "ledger"
    ledger = TWO_DOMAIN_PROBE.TwoDomainIntentLedger(ledger_path)
    tracker = {
        "source_volume": "private-source-volume",
        "target_volume": "private-target-volume",
        "containers": [], "planned_containers": [],
    }
    result = {
        "arm": "negative", "status": disposition["status"],
        "reason_codes": disposition["reason_codes"],
        "release_refused": True, "target_container_created": False,
        "final_custody": final_custody,
    }
    observer = Observer()
    TWO_DOMAIN["_finalize_normal_arm_result"](
        result, ledger=ledger, observer=observer, tracker=tracker,
        run_id="private-run", source_volume=tracker["source_volume"],
        target_volume=tracker["target_volume"], observe=observer,
    )
    assert removal_calls == []
    assert result["cleanup_complete"] is False
    assert result["leftovers"]["manual_review_required"] is True
    assert not (ledger_path / "cleanup-complete.json").exists()


def test_two_domain_negative_refusal_with_missing_final_custody_is_inconclusive():
    disposition = TWO_DOMAIN["_negative_arm_disposition"](
        refused=True, no_target=True, final_report={},
    )
    assert disposition["status"] == "inconclusive"
    assert set(disposition["reason_codes"]) == {
        "saved-edit-custody-incomplete",
        "identity-linked-history-evidence-incomplete",
    }
    assert disposition["final_custody_assessment"]["saved_edit_evidence_available"] is False
    assert disposition["final_custody_assessment"][
        "identity_linked_history_evidence_available"
    ] is False


@pytest.mark.parametrize("status", ["fail", "inconclusive"])
def test_two_domain_run_arm_preserves_normal_unaccepted_result_inventory(
    tmp_path, monkeypatch, status,
):
    observer_type = TWO_DOMAIN["TwoDomainObserver"]
    lifecycle_checks = []
    monkeypatch.setattr(observer_type, "start_engine_stream", lambda self, run_id: None)
    monkeypatch.setattr(observer_type, "finish_engine_stream", lambda self: None)
    monkeypatch.setattr(
        observer_type, "verify_lifecycle",
        lambda self, *, volumes_removed: lifecycle_checks.append(volumes_removed),
    )
    monkeypatch.setattr(observer_type, "report", lambda self: [])
    module_globals = TWO_DOMAIN["_run_arm"].__globals__

    def normal_unaccepted_arm(**kwargs):
        return {
            "arm": kwargs["arm"],
            "status": status,
            "reason_codes": ["candidate-not-established"],
            "release_candidate_ready": False,
            "cleanup_complete": False,
            "support_claim": False,
        }

    monkeypatch.setitem(module_globals, "_run_arm_impl", normal_unaccepted_arm)
    result = TWO_DOMAIN["_run_arm"](
        arm="positive", run_id="private-run-id",
        image_id="sha256:" + "a" * 64, cli_path="/private/cli",
        selected={}, private_dir=tmp_path / status,
    )

    assert result["status"] == status
    assert result["cleanup_complete"] is False
    assert result["observer_complete"] is True
    assert result["leftovers"]["manual_review_required"] is True
    assert set(result["leftovers"]["possible_volume_digests"]) == {
        "source_volume", "target_volume",
    }
    assert lifecycle_checks == [False]
    assert "private-run-id" not in json.dumps(result)


def test_two_domain_run_arm_preserves_established_fail_when_stream_finish_fails(
    tmp_path, monkeypatch,
):
    observer_type = TWO_DOMAIN["TwoDomainObserver"]
    monkeypatch.setattr(observer_type, "start_engine_stream", lambda self, run_id: None)
    monkeypatch.setattr(observer_type, "__call__", lambda self, *args, **kwargs: None)

    def fail_finish(self):
        raise RuntimeError("simulated event-stream finalization uncertainty")

    monkeypatch.setattr(observer_type, "finish_engine_stream", fail_finish)
    module_globals = TWO_DOMAIN["_run_arm"].__globals__

    def established_fail(**kwargs):
        tracker = kwargs["tracker"]
        tracker["containers"].append({
            "name": tracker["source_name"], "id": "private-source-id",
            "role": "source", "removed": False,
        })
        result = {
            "arm": kwargs["arm"], "status": "fail",
            "reason_codes": ["known-source-history-mismatch"],
            "release_candidate_ready": False, "cleanup_complete": False,
            "support_claim": False,
        }
        TWO_DOMAIN["_finalize_normal_arm_result"](
            result, ledger=kwargs["ledger"], observer=kwargs["observe"],
            tracker=tracker, run_id=kwargs["run_id"],
            source_volume=tracker["source_volume"],
            target_volume=tracker["target_volume"], observe=kwargs["observe"],
        )
        return result

    monkeypatch.setitem(module_globals, "_run_arm_impl", established_fail)

    def preserved_quarantine(**kwargs):
        ledger = kwargs["ledger"]
        assert (ledger.directory / "arm-result.json").is_file()
        assert (ledger.directory / "arm-abort.json").is_file()
        return {
            "preserved": 1, "removed": 0,
            "reason_codes": ["quarantine-preserved-for-review"],
        }

    monkeypatch.setitem(
        module_globals, "_quarantine_run_owned_resources", preserved_quarantine,
    )
    result = TWO_DOMAIN["_run_arm"](
        arm="positive", run_id="private-established-fail-run",
        image_id="sha256:" + "d" * 64, cli_path="/private/cli",
        selected={}, private_dir=tmp_path / "established-fail",
    )

    assert result["status"] == "fail"
    assert "known-source-history-mismatch" in result["reason_codes"]
    assert "observer-incomplete" in result["reason_codes"]
    assert "effect-or-observer-uncertain" in result["reason_codes"]
    assert result["observer_complete"] is False
    assert result["cleanup_complete"] is False
    assert result["leftovers"]["manual_review_required"] is True
    assert result["quarantine"]["preserved"] == 1
    assert "private-established-fail-run" not in json.dumps(result)


def test_two_domain_run_arm_preserves_fail_when_arm_result_persistence_fails(
    tmp_path, monkeypatch,
):
    observer_type = TWO_DOMAIN["TwoDomainObserver"]
    monkeypatch.setattr(observer_type, "start_engine_stream", lambda self, run_id: None)
    module_globals = TWO_DOMAIN["_run_arm"].__globals__

    def fail_during_seal(**kwargs):
        tracker = kwargs["tracker"]
        tracker["containers"].append({
            "name": tracker["source_name"], "id": "private-source-id",
            "role": "source", "removed": False,
        })
        result = {
            "arm": kwargs["arm"], "status": "fail",
            "reason_codes": ["known-final-custody-mismatch"],
            "cleanup_complete": False, "support_claim": False,
        }
        TWO_DOMAIN["_finalize_normal_arm_result"](
            result, ledger=kwargs["ledger"], observer=kwargs["observe"],
            tracker=tracker, run_id=kwargs["run_id"],
            source_volume=tracker["source_volume"],
            target_volume=tracker["target_volume"], observe=kwargs["observe"],
        )
        return result

    monkeypatch.setitem(module_globals, "_run_arm_impl", fail_during_seal)
    original_persist = TWO_DOMAIN_PROBE.TwoDomainIntentLedger.persist

    def fail_arm_result_persist(self, name, payload):
        if name == "arm-result":
            raise RuntimeError("simulated private arm-result fsync failure")
        return original_persist(self, name, payload)

    monkeypatch.setattr(
        TWO_DOMAIN_PROBE.TwoDomainIntentLedger, "persist", fail_arm_result_persist,
    )

    def preserved_quarantine(**kwargs):
        assert (kwargs["ledger"].directory / "arm-abort.json").is_file()
        return {"preserved": 1, "removed": 0, "reason_codes": []}

    monkeypatch.setitem(
        module_globals, "_quarantine_run_owned_resources", preserved_quarantine,
    )
    result = TWO_DOMAIN["_run_arm"](
        arm="positive", run_id="private-seal-failure-run",
        image_id="sha256:" + "e" * 64, cli_path="/private/cli",
        selected={}, private_dir=tmp_path / "seal-failure",
    )

    assert result["status"] == "fail"
    assert "known-final-custody-mismatch" in result["reason_codes"]
    assert "arm-result-persistence-incomplete" in result["reason_codes"]
    assert "effect-or-observer-uncertain" in result["reason_codes"]
    assert result["observer_complete"] is False
    assert result["cleanup_complete"] is False
    assert result["leftovers"]["manual_review_required"] is True
    assert not (tmp_path / "seal-failure" / "ledger" / "arm-result.json").exists()


def test_two_domain_run_arm_keeps_successful_cleanup_disposition(
    tmp_path, monkeypatch,
):
    observer_type = TWO_DOMAIN["TwoDomainObserver"]
    lifecycle_checks = []
    monkeypatch.setattr(observer_type, "start_engine_stream", lambda self, run_id: None)
    monkeypatch.setattr(observer_type, "finish_engine_stream", lambda self: None)
    monkeypatch.setattr(
        observer_type, "verify_lifecycle",
        lambda self, *, volumes_removed: lifecycle_checks.append(volumes_removed),
    )
    monkeypatch.setattr(observer_type, "report", lambda self: [])
    module_globals = TWO_DOMAIN["_run_arm"].__globals__

    def observed_arm(**kwargs):
        tracker = kwargs["tracker"]
        tracker["source_volume_removed"] = True
        tracker["target_volume_removed"] = True
        return {
            "arm": kwargs["arm"], "status": "observed",
            "reason_codes": [], "release_candidate_ready": True,
            "cleanup_complete": True, "support_claim": False,
        }

    monkeypatch.setitem(module_globals, "_run_arm_impl", observed_arm)
    result = TWO_DOMAIN["_run_arm"](
        arm="positive", run_id="private-run-id",
        image_id="sha256:" + "a" * 64, cli_path="/private/cli",
        selected={}, private_dir=tmp_path / "observed",
    )

    assert result["status"] == "observed"
    assert result["cleanup_complete"] is True
    assert result["observer_complete"] is True
    assert result["leftovers"]["manual_review_required"] is False
    assert lifecycle_checks == [True]


def test_two_domain_quarantine_stops_and_preserves_state_for_manual_review(
    tmp_path, monkeypatch,
):
    module_globals = TWO_DOMAIN["_quarantine_run_owned_resources"].__globals__
    container_id = "e" * 64
    run_id = "run-quarantine"
    state = {"Running": True}
    calls = []
    event_actions = []

    def inspect(_container_id, **_kwargs):
        return {
            "Name": "/source-fixture",
            "Config": {"Labels": {
                "openrepotools.bite4.run": run_id,
                "openrepotools.bite4.role": "source",
            }},
            "State": dict(state),
        }

    def docker(*args, **kwargs):
        calls.append(args)
        if args[0] == "stop":
            state["Running"] = False
        return SimpleNamespace(stdout=b"")

    class Observer:
        def wait_engine_event(self, *, action, **kwargs):
            event_actions.append(action)

        def ensure_engine_healthy(self):
            return None

        def report(self):
            return []

    monkeypatch.setitem(
        module_globals, "_container_ids_for_run",
        lambda _run, **_kwargs: [container_id],
    )
    monkeypatch.setitem(module_globals, "_inspect_container", inspect)
    monkeypatch.setitem(
        module_globals, "_container_state", lambda _id, **_kwargs: dict(state),
    )
    monkeypatch.setitem(module_globals, "_docker", docker)
    tracker = {
        "planned_containers": [{
            "name": "source-fixture", "id": container_id, "role": "source", "removed": False,
        }],
        "containers": [{
            "name": "source-fixture", "id": container_id, "role": "source", "removed": False,
            "stop_intent_persisted": False, "remove_intent_persisted": False,
        }],
        "private_values": [],
    }
    ledger = TWO_DOMAIN_PROBE.TwoDomainIntentLedger(tmp_path / "arm-ledger")
    result = TWO_DOMAIN["_quarantine_run_owned_resources"](
        run_id=run_id, tracker=tracker, ledger=ledger,
        private_dir=tmp_path / "private", observer=Observer(),
    )
    assert calls == [("stop", "--time", "10", container_id)]
    assert event_actions == ["die"]
    assert result["stopped"] == 1
    assert result["removed"] == 0
    assert "quarantine-container-preserved-for-custody-review" in result["reason_codes"]
    assert tracker["containers"][0]["removed"] is False
    quarantine_files = list((tmp_path / "private" / "quarantine").glob("*/*.json"))
    assert {path.name for path in quarantine_files} == {"quarantine-stop.json"}
    leftovers = TWO_DOMAIN["_possible_leftovers"](tracker)
    assert leftovers["manual_review_required"] is True
    assert leftovers["quarantine_unresolved_id_digests"] == [TWO_DOMAIN["_digest"](container_id)]
    assert (tmp_path / "arm-ledger" / "quarantine-summary.json").is_file()


def test_two_domain_quarantine_never_replays_recorded_stop_intent(tmp_path, monkeypatch):
    module_globals = TWO_DOMAIN["_quarantine_run_owned_resources"].__globals__
    container_id = "f" * 64
    run_id = "run-no-replay"
    calls = []
    monkeypatch.setitem(
        module_globals, "_container_ids_for_run",
        lambda _run, **_kwargs: [container_id],
    )
    monkeypatch.setitem(module_globals, "_inspect_container", lambda _id, **_kwargs: {
        "Name": "/source-fixture",
        "Config": {"Labels": {
            "openrepotools.bite4.run": run_id,
            "openrepotools.bite4.role": "source",
        }},
        "State": {"Running": True},
    })
    monkeypatch.setitem(module_globals, "_docker", lambda *args, **kwargs: calls.append(args))

    class Observer:
        def wait_engine_event(self, **kwargs):
            pytest.fail("quarantine must not wait or remove after an uncertain stop intent")

        def ensure_engine_healthy(self):
            return None

        def report(self):
            return []

    tracker = {
        "planned_containers": [{
            "name": "source-fixture", "id": container_id, "role": "source", "removed": False,
        }],
        "containers": [{
            "name": "source-fixture", "id": container_id, "role": "source", "removed": False,
            "stop_intent_persisted": True, "remove_intent_persisted": False,
        }],
        "private_values": [],
    }
    ledger = TWO_DOMAIN_PROBE.TwoDomainIntentLedger(tmp_path / "arm-ledger")
    result = TWO_DOMAIN["_quarantine_run_owned_resources"](
        run_id=run_id, tracker=tracker, ledger=ledger,
        private_dir=tmp_path / "private", observer=Observer(),
    )
    assert calls == []
    assert result["preserved"] == 1
    assert "quarantine-stop-intent-already-recorded" in result["reason_codes"]


def test_two_domain_quarantine_preserves_confirmed_never_started_created_container(
    tmp_path, monkeypatch,
):
    module_globals = TWO_DOMAIN["_quarantine_run_owned_resources"].__globals__
    container_id = "created-container-private-id-0123456789"
    run_id = "run-never-started"
    event_actions = []
    record = two_domain_created_tmpfs_record()
    record["Name"] = "/source-fixture"
    record["Config"]["Labels"] = {
        "openrepotools.bite4.run": run_id,
        "openrepotools.bite4.role": "source",
    }

    class Observer:
        def wait_engine_event(self, *, action, **kwargs):
            event_actions.append(action)

        def ensure_engine_healthy(self):
            return None

        def container_start_observed(self, identity):
            assert identity == container_id
            return False

        def report(self):
            return []

    def forbidden_docker(*args, **kwargs):
        pytest.fail("a corroborated never-started container must not be stopped")

    monkeypatch.setitem(
        module_globals, "_container_ids_for_run", lambda _run, **_kwargs: [container_id],
    )
    monkeypatch.setitem(module_globals, "_inspect_container", lambda *_a, **_k: record)
    monkeypatch.setitem(module_globals, "_docker", forbidden_docker)
    tracker = {
        "planned_containers": [{
            "name": "source-fixture", "id": container_id,
            "role": "source", "removed": False,
        }],
        "containers": [{
            "name": "source-fixture", "id": container_id,
            "role": "source", "removed": False,
            "start_attempted": False,
            "stop_intent_persisted": False,
            "remove_intent_persisted": False,
        }],
        "private_values": [],
    }
    result = TWO_DOMAIN["_quarantine_run_owned_resources"](
        run_id=run_id,
        tracker=tracker,
        ledger=TWO_DOMAIN_PROBE.TwoDomainIntentLedger(tmp_path / "arm-ledger"),
        private_dir=tmp_path / "private",
        observer=Observer(),
    )

    assert event_actions == ["create"]
    assert result["never_started_preserved"] == 1
    assert result["preserved"] == 1
    assert result["removed"] == result["stopped"] == 0
    assert "quarantine-created-never-started-preserved" in result["reason_codes"]
    assert "quarantine-die-event-unconfirmed" not in result["reason_codes"]


@pytest.mark.parametrize("observed_start, start_attempted", [(False, True), (True, False)])
def test_two_domain_quarantine_treats_ambiguous_created_start_as_uncertain(
    tmp_path, monkeypatch, observed_start, start_attempted,
):
    module_globals = TWO_DOMAIN["_quarantine_run_owned_resources"].__globals__
    container_id = "created-ambiguous-private-id-0123456789"
    run_id = "run-ambiguous-start"
    event_actions = []
    record = two_domain_created_tmpfs_record()
    record["Name"] = "/source-fixture"
    record["Config"]["Labels"] = {
        "openrepotools.bite4.run": run_id,
        "openrepotools.bite4.role": "source",
    }

    class Observer:
        def wait_engine_event(self, *, action, **kwargs):
            event_actions.append(action)

        def ensure_engine_healthy(self):
            return None

        def container_start_observed(self, identity):
            assert identity == container_id
            return observed_start

        def report(self):
            return []

    monkeypatch.setitem(
        module_globals, "_container_ids_for_run", lambda _run, **_kwargs: [container_id],
    )
    monkeypatch.setitem(module_globals, "_inspect_container", lambda *_a, **_k: record)
    monkeypatch.setitem(
        module_globals, "_docker",
        lambda *args, **kwargs: pytest.fail("ambiguous start must not be replayed or stopped"),
    )
    tracker = {
        "planned_containers": [{
            "name": "source-fixture", "id": container_id,
            "role": "source", "removed": False,
        }],
        "containers": [{
            "name": "source-fixture", "id": container_id,
            "role": "source", "removed": False,
            "start_attempted": start_attempted,
            "stop_intent_persisted": False,
            "remove_intent_persisted": False,
        }],
        "private_values": [],
    }
    result = TWO_DOMAIN["_quarantine_run_owned_resources"](
        run_id=run_id,
        tracker=tracker,
        ledger=TWO_DOMAIN_PROBE.TwoDomainIntentLedger(tmp_path / "arm-ledger"),
        private_dir=tmp_path / "private",
        observer=Observer(),
    )

    assert event_actions == ["create"]
    assert result["never_started_preserved"] == 0
    assert result["preserved"] == 1
    assert "quarantine-start-history-uncertain" in result["reason_codes"]
    assert "quarantine-die-event-unconfirmed" not in result["reason_codes"]



def test_two_domain_container_builder_omits_writable_mount_token_and_marks_readonly():
    command = TWO_DOMAIN["_container_create_command"](
        image_id="sha256:" + "a" * 64,
        run_id="run-private",
        role="copy",
        name="private-container",
        volume_mounts={
            "/source": ("source-volume", True),
            "/target": ("target-volume", False),
        },
    )
    mounts = [command[index + 1] for index, value in enumerate(command[:-1])
              if value == "--mount"]
    assert mounts == [
        "type=volume,src=source-volume,dst=/source",
        "type=volume,src=target-volume,dst=/target,readonly",
    ]
    assert all(not value.endswith(",") for value in mounts)
    assert [value.split(",")[-1] for value in mounts] == ["dst=/source", "readonly"]


def test_two_domain_docker_create_stderr_is_bounded_and_private_abort_only(
    tmp_path, monkeypatch,
):
    raw_stderr = b"private-daemon-detail-" * 400
    calls = []

    def fake_run(command, **kwargs):
        calls.append((tuple(command), kwargs))
        return TWO_DOMAIN["subprocess"].CompletedProcess(
            command, 125, stdout=b"", stderr=raw_stderr,
        )

    monkeypatch.setattr(TWO_DOMAIN["subprocess"], "run", fake_run)
    with pytest.raises(TWO_DOMAIN["DockerCommandError"]) as caught:
        TWO_DOMAIN["_docker"]("create", "--name", "private-container")
    assert caught.value.private_stderr == raw_stderr[:TWO_DOMAIN["MAX_PRIVATE_DOCKER_STDERR"]]
    assert caught.value.private_stderr_truncated is True
    assert calls[0][1]["check"] is False

    module_globals = TWO_DOMAIN["_run_arm"].__globals__
    monkeypatch.setattr(
        TWO_DOMAIN["TwoDomainObserver"], "start_engine_stream",
        lambda self, run_id: None,
    )
    monkeypatch.setitem(module_globals, "_run_arm_impl", lambda **kwargs: TWO_DOMAIN["_docker"](
        "create", "--name", "private-container",
    ))
    monkeypatch.setitem(
        module_globals, "_quarantine_run_owned_resources",
        lambda **kwargs: {"reason_codes": [], "volumes_removed": False},
    )

    result = TWO_DOMAIN["_run_arm"](
        arm="positive",
        run_id="run-private",
        image_id="sha256:" + "b" * 64,
        cli_path="/private/sdk/cli",
        selected={},
        private_dir=tmp_path / "private-artifacts",
    )
    abort_path = tmp_path / "private-artifacts" / "ledger" / "arm-abort.json"
    abort = json.loads(abort_path.read_text())
    payload = abort["payload"]
    assert payload["private_docker_exit_status"] == 125
    assert payload["private_docker_stderr_b64"] == base64.b64encode(
        raw_stderr[:TWO_DOMAIN["MAX_PRIVATE_DOCKER_STDERR"]]
    ).decode("ascii")
    assert payload["private_docker_stderr_truncated"] is True
    assert abort_path.stat().st_mode & 0o777 == 0o600
    assert result["status"] == "inconclusive"
    assert "private-daemon-detail" not in json.dumps(result)


def _mountinfo_witness_sample():
    return (
        b"1 1 0:1 / / rw,relatime - overlay overlay rw\n"
        b"35 1 0:35 / /tmp rw,nosuid,nodev,noexec,relatime shared:2 - tmpfs tmpfs rw,size=98304k,inode64\n"
        b"36 1 0:36 / /opt/loopback rw,nosuid,nodev,relatime master:1 - tmpfs tmpfs rw,size=262144k,inode64\n"
        b"37 1 0:37 / /dev/shm rw,nosuid,nodev - tmpfs shm rw,size=65536k\n"
    )


@pytest.mark.parametrize("size_suffix", ["k", "K", "bytes"])
def test_two_domain_mountinfo_parser_normalizes_exact_tmpfs_profile(size_suffix):
    raw = _mountinfo_witness_sample()
    if size_suffix == "K":
        raw = raw.replace(b"98304k", b"98304K").replace(b"262144k", b"262144K")
    elif size_suffix == "bytes":
        raw = raw.replace(b"98304k", b"100663296").replace(b"262144k", b"268435456")
    result = TWO_DOMAIN["_parse_mountinfo_policy"](raw)
    assert [row["destination"] for row in result["mounts"]] == [
        "/opt/loopback", "/tmp",
    ]
    by_destination = {row["destination"]: row for row in result["mounts"]}
    assert by_destination["/tmp"]["size_bytes"] == 100663296
    assert by_destination["/opt/loopback"]["size_bytes"] == 268435456
    assert by_destination["/tmp"]["optional_fields"] == ["shared:2"]
    assert result["ignored_tmpfs_count"] == 1


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        _mountinfo_witness_sample()[:-1],
        _mountinfo_witness_sample() + b"\n",
        b"x" * (TWO_DOMAIN["MAX_MOUNTINFO_BYTES"] + 1),
        _mountinfo_witness_sample().replace(b"\n", b"\v", 1),
        _mountinfo_witness_sample().replace(b"/opt/loopback", b"/opt/loopback/../other"),
        _mountinfo_witness_sample().replace(b"98304k", b"50%"),
        _mountinfo_witness_sample().replace(b"size=98304k", b"size=98304k,size=100663296"),
        _mountinfo_witness_sample().replace(b"/opt/loopback rw", b"/opt rw"),
    ],
)
def test_two_domain_mountinfo_parser_rejects_truncation_and_unsafe_topology(raw):
    with pytest.raises(RuntimeError):
        TWO_DOMAIN["_parse_mountinfo_policy"](raw)


def test_two_domain_wrapper_proc_stat_starttime_accepts_kernel_terminator(monkeypatch):
    import ast
    import io

    wrapper_tree = ast.parse(TWO_DOMAIN["MOUNT_WITNESS_WRAPPER"])
    function = next(
        node for node in wrapper_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "process_start_token"
    )
    namespace = {"die": lambda: (_ for _ in ()).throw(SystemExit(81))}
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, "<mount-witness-wrapper-test>", "exec"), namespace)
    stat_row = b"123 (comm with ) paren) S " + b" ".join(
        [b"0"] * 18 + [b"987654321"]
    ) + b"\n"
    monkeypatch.setattr(
        "builtins.open", lambda *_a, **_k: io.BytesIO(stat_row),
    )
    assert namespace["process_start_token"]() == "987654321"


def _active_mount_witness_fixture(*, capture_count=2):
    raw = _mountinfo_witness_sample()
    parsed_mounts = TWO_DOMAIN["_parse_mountinfo_policy"](raw)["mounts"]
    identity = {
        "container_id": "f" * 64,
        "run_id": "run-witness",
        "role": "source",
        "image_id": "sha256:" + "a" * 64,
        "started_at": "2026-09-23T01:02:03.123456789Z",
        "pid": 77,
    }
    event_binding = {
        "run_id": identity["run_id"],
        "container_id": identity["container_id"],
        "role": identity["role"],
        "create_count": 1,
        "start_count": 1,
        "die_count": 0,
        "destroy_count": 0,
    }
    event_binding["event_binding_digest"] = TWO_DOMAIN["_digest"](event_binding)
    captures = []
    for index, stage in enumerate(("before-upload", "before-work")[:capture_count]):
        capture = {
            "stage": stage,
            "nonce_digest": hashlib.sha256(f"nonce-{index}".encode()).hexdigest(),
            "mountinfo_sha256": hashlib.sha256(raw).hexdigest(),
            "mounts": parsed_mounts,
            "mounts_digest": TWO_DOMAIN["_digest"](parsed_mounts),
            "mount_namespace": "mnt:[4026535000]",
            "start_token": "987654321",
            "inspect_identity_digest": TWO_DOMAIN["_digest"](identity),
            "event_binding_digest": event_binding["event_binding_digest"],
        }
        capture["capture_digest"] = TWO_DOMAIN["_digest"](capture)
        captures.append(capture)
    witness = TWO_DOMAIN["_make_mount_witness_attestation"](
        identity=identity, event_binding=event_binding, captures=captures,
    )
    record = two_domain_created_tmpfs_record()
    record["Config"]["Labels"] = {
        "openrepotools.bite4.run": identity["run_id"],
        "openrepotools.bite4.role": identity["role"],
    }
    record["Id"] = identity["container_id"]
    record["Image"] = identity["image_id"]
    record["Config"].update({
        "OpenStdin": True,
        "AttachStdin": True,
        "Tty": False,
        "StdinOnce": True,
        "Entrypoint": ["/usr/bin/env"],
        "Cmd": [
            "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "python3",
            "-I", "-S", "-u", "-c", TWO_DOMAIN["MOUNT_WITNESS_WRAPPER"],
        ],
    })
    record["State"].update({
        "Status": "running", "Running": True, "Pid": identity["pid"],
        "StartedAt": identity["started_at"],
    })
    return record, witness


@pytest.mark.parametrize("capture_count", [1, 2])
def test_two_domain_native_validator_accepts_bound_active_tmpfs_witness(capture_count):
    record, witness = _active_mount_witness_fixture(capture_count=capture_count)
    PROBE["validate_two_domain_isolation"](
        record, run_id="run-witness", role="source",
        expected_mounts={
            "/opt/state": ("volume", "state-created", True),
            "/tmp": ("tmpfs", None, True),
            "/opt/loopback": ("tmpfs", None, True),
        },
        active_tmpfs_witness=witness,
        expected_wrapper_sha256=TWO_DOMAIN["MOUNT_WITNESS_WRAPPER_SHA256"],
    )


def _interactive_witness_config_record():
    image_id = "sha256:" + "a" * 64
    return {
        "Image": image_id,
        "Config": {
            "OpenStdin": True,
            "AttachStdin": True,
            "Tty": False,
            "StdinOnce": True,
            "Entrypoint": ["/usr/bin/env"],
            "Cmd": [
                "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "python3",
                "-I", "-S", "-u", "-c", TWO_DOMAIN["MOUNT_WITNESS_WRAPPER"],
            ],
        },
    }


def test_two_domain_wrapper_config_accepts_exact_interactive_stdio_profile():
    record = _interactive_witness_config_record()
    assert TWO_DOMAIN["_wrapper_config_matches"](
        record, record["Image"],
    ) is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("StdinOnce", False), ("StdinOnce", None), ("StdinOnce", "missing"),
        ("AttachStdin", False), ("AttachStdin", None), ("AttachStdin", "missing"),
    ],
)
def test_two_domain_wrapper_config_rejects_inexact_interactive_stdio_profile(
    field, value,
):
    record = _interactive_witness_config_record()
    if value == "missing":
        record["Config"].pop(field)
    else:
        record["Config"][field] = value
    assert TWO_DOMAIN["_wrapper_config_matches"](
        record, record["Image"],
    ) is False


@pytest.mark.parametrize(
    ("mutate_image", "mutate_stdio", "expected_error"),
    [
        (True, False, "two-domain container image identity mismatch"),
        (False, True, "two-domain wrapper configuration mismatch"),
    ],
)
def test_two_domain_container_creation_reports_image_and_wrapper_failures_separately(
    mutate_image, mutate_stdio, expected_error, monkeypatch,
):
    module_globals = TWO_DOMAIN["_create_container"].__globals__
    image_id = "sha256:" + "a" * 64
    record = _interactive_witness_config_record()
    if mutate_image:
        record["Image"] = "sha256:" + "b" * 64
    if mutate_stdio:
        record["Config"]["StdinOnce"] = False
    monkeypatch.setitem(
        module_globals, "_docker",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=b"created-id"),
    )
    monkeypatch.setitem(module_globals, "_inspect_container", lambda *_a, **_k: record)
    with pytest.raises(RuntimeError, match=expected_error):
        TWO_DOMAIN["_create_container"](
            image_id=image_id, run_id="run-stdio", role="source",
            name="source-container", volume_mounts={},
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("StdinOnce", False), ("StdinOnce", None), ("StdinOnce", "missing"),
        ("AttachStdin", False), ("AttachStdin", None), ("AttachStdin", "missing"),
    ],
)
def test_two_domain_native_validator_rejects_inexact_interactive_stdio_profile(
    field, value,
):
    record, witness = _active_mount_witness_fixture()
    if value == "missing":
        record["Config"].pop(field)
    else:
        record["Config"][field] = value
    with pytest.raises(RuntimeError, match="active tmpfs witness"):
        PROBE["validate_two_domain_isolation"](
            record, run_id="run-witness", role="source",
            expected_mounts={
                "/opt/state": ("volume", "state-created", True),
                "/tmp": ("tmpfs", None, True),
                "/opt/loopback": ("tmpfs", None, True),
            },
            active_tmpfs_witness=witness,
            expected_wrapper_sha256=TWO_DOMAIN["MOUNT_WITNESS_WRAPPER_SHA256"],
        )


def test_two_domain_native_validator_rejects_changed_identity_or_capture_digest():
    record, witness = _active_mount_witness_fixture()
    changed_identity = json.loads(json.dumps(record))
    changed_identity["State"]["Pid"] += 1
    with pytest.raises(RuntimeError, match="active tmpfs witness"):
        PROBE["validate_two_domain_isolation"](
            changed_identity, run_id="run-witness", role="source",
            expected_mounts={
                "/opt/state": ("volume", "state-created", True),
                "/tmp": ("tmpfs", None, True),
                "/opt/loopback": ("tmpfs", None, True),
            }, active_tmpfs_witness=witness,
            expected_wrapper_sha256=TWO_DOMAIN["MOUNT_WITNESS_WRAPPER_SHA256"],
        )
    changed_capture = json.loads(json.dumps(witness))
    changed_capture["captures"][1]["mount_namespace"] = "mnt:[99]"
    with pytest.raises(RuntimeError, match="active tmpfs witness"):
        PROBE["validate_two_domain_isolation"](
            record, run_id="run-witness", role="source",
            expected_mounts={
                "/opt/state": ("volume", "state-created", True),
                "/tmp": ("tmpfs", None, True),
                "/opt/loopback": ("tmpfs", None, True),
            }, active_tmpfs_witness=changed_capture,
            expected_wrapper_sha256=TWO_DOMAIN["MOUNT_WITNESS_WRAPPER_SHA256"],
        )


@pytest.mark.parametrize("changed_key", ["pid", "started_at"])
def test_two_domain_cross_stage_inspect_identity_must_remain_stable(changed_key):
    record, _witness = _active_mount_witness_fixture()
    identity = TWO_DOMAIN["_mount_witness_identity"](
        record, container_id=record["Id"], run_id="run-witness",
        role="source", image_id=record["Image"],
    )
    changed = dict(identity)
    changed[changed_key] = (
        identity[changed_key] + 1 if changed_key == "pid"
        else "2026-09-23T01:02:04.123456789Z"
    )
    with pytest.raises(RuntimeError, match="inspect identity changed"):
        TWO_DOMAIN["_require_stable_mount_witness_identity"](identity, changed)


@pytest.mark.parametrize(
    ("role", "disconnect_stage"),
    [
        ("source", None), ("target", None), ("copy", None),
        ("verify", None), ("custodian", None),
        ("source", "before-upload"), ("source", "before-work"),
    ],
)
def test_two_domain_every_role_keeps_two_stage_attach_until_stop(
    role, disconnect_stage, tmp_path, monkeypatch,
):
    module_globals = TWO_DOMAIN["_install_observer_files"].__globals__
    raw = _mountinfo_witness_sample()
    parsed_mounts = TWO_DOMAIN["_parse_mountinfo_policy"](raw)["mounts"]
    events = []
    run_id = "run-" + role
    container_id = (role[0] * 64)
    image_id = "sha256:" + "a" * 64
    record = two_domain_created_tmpfs_record()
    record.update({"Id": container_id, "Image": image_id})
    record["Config"].update({
        "Labels": {
            "openrepotools.bite4.run": run_id,
            "openrepotools.bite4.role": role,
        },
        "OpenStdin": True, "AttachStdin": True, "Tty": False, "StdinOnce": True,
        "Entrypoint": ["/usr/bin/env"],
        "Cmd": [
            "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "python3",
            "-I", "-S", "-u", "-c", TWO_DOMAIN["MOUNT_WITNESS_WRAPPER"],
        ],
        "Healthcheck": {"Test": ["NONE"]},
    })
    record["State"].update({
        "Status": "running", "Running": True, "Pid": 77,
        "StartedAt": "2026-09-23T01:02:03.123456789Z",
    })
    record["Mounts"] = [{
        "Type": "volume", "Name": "state-volume",
        "Destination": "/opt/state", "RW": True,
    }]

    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    observer.run_id = run_id
    observer.engine_containers[container_id] = {
        "role": role, "create": 1, "start": 1, "die": 0, "destroy": 0,
    }
    observer.ensure_engine_healthy = lambda: None
    observer.wait_engine_event = lambda **_kwargs: None

    attach_clients = []

    class FakeAttach:
        def __init__(self, identity):
            assert identity == container_id
            self.stages = []
            self.reaped = False
            self.initialized = True
            attach_clients.append(self)

        def require_initialized(self):
            assert self.initialized is True

        def exchange(self, stage):
            assert container_id in observer.mount_witness_ledgers
            events.append(("challenge", stage))
            self.stages.append(stage)
            if stage == disconnect_stage:
                raise TWO_DOMAIN["MountWitnessTransportError"](
                    "mount-witness-response-eof",
                )
            index = len(self.stages) - 1
            return {
                "schema": "openrepotools-mount-witness-response/v1",
                "nonce": f"{index + 1:032x}",
                "stage": stage,
                "start_token": "987654321",
                "mount_namespace": "mnt:[4026535000]",
                "mountinfo_b64": base64.b64encode(raw).decode(),
                "_private_mountinfo": raw,
                "_normalized_mounts": parsed_mounts,
                "_mountinfo_sha256": hashlib.sha256(raw).hexdigest(),
                "_nonce_digest": hashlib.sha256(f"{index + 1:032x}".encode()).hexdigest(),
            }

        def check_alive(self):
            events.append(("alive", self.stages[-1] if self.stages else "start"))

        def finish_after_stop(self):
            self.reaped = True
            return {
                "exit_code": 0,
                "stderr_sha256": hashlib.sha256(b"").hexdigest(),
                "stderr_truncated": False,
                "local_terminate_forced": False,
            }

    def fake_docker(*args, **kwargs):
        events.append(("docker", args[0]))
        return SimpleNamespace(stdout=b"")

    monkeypatch.setitem(module_globals, "MountWitnessAttach", FakeAttach)
    monkeypatch.setitem(module_globals, "_docker", fake_docker)
    monkeypatch.setitem(module_globals, "_inspect_container", lambda *_a, **_k: record)
    monkeypatch.setattr(
        TWO_DOMAIN_PROBE, "validate_two_domain_isolation", lambda *a, **k: None,
    )
    tracker = {"containers": [{"id": container_id, "role": role}]}
    expected = {
        "/opt/state": ("volume", "state-volume", True),
        "/tmp": ("tmpfs", None, True),
        "/opt/loopback": ("tmpfs", None, True),
    }
    if disconnect_stage is not None:
        with pytest.raises(TWO_DOMAIN["MountWitnessTransportError"]):
            TWO_DOMAIN["_install_observer_files"](
                container_id, None, run_id=run_id, role=role, image_id=image_id,
                private_dir=tmp_path / role, observer=observer,
                expected_mounts=expected, tracker=tracker,
            )
        assert len(attach_clients) == 1
        assert attach_clients[0].stages == (
            ["before-upload"] if disconnect_stage == "before-upload"
            else ["before-upload", "before-work"]
        )
        assert len([item for item in events if item[0] == "challenge"]) == len(
            attach_clients[0].stages
        )
        if disconnect_stage == "before-upload":
            assert not any(item == ("docker", "exec") for item in events)
        else:
            # Uploads complete after the first witness, but the second
            # challenge loss prevents subsequent SDK/helper work and is never
            # retried through a replacement attach.
            assert any(item == ("docker", "exec") for item in events)
        return

    TWO_DOMAIN["_install_observer_files"](
        container_id, None, run_id=run_id, role=role, image_id=image_id,
        private_dir=tmp_path / role, observer=observer,
        expected_mounts=expected, tracker=tracker,
    )
    assert len(attach_clients) == 1
    challenge_indexes = [i for i, item in enumerate(events) if item[0] == "challenge"]
    upload_indexes = [i for i, item in enumerate(events) if item == ("docker", "exec")]
    assert [events[index][1] for index in challenge_indexes] == [
        "before-upload", "before-work",
    ]
    assert challenge_indexes[0] < upload_indexes[0] < upload_indexes[-1] < challenge_indexes[1]
    assert observer.require_mount_witness_complete(container_id)["capture_digests"]
    assert tracker["mount_witness_attestations"][container_id]["role"] == role
    session = TWO_DOMAIN["_mount_witness_session"](tracker, container_id)
    assert session.reaped is False
    TWO_DOMAIN["_reap_mount_witness_after_stop"](tracker, container_id, observer)
    assert session.reaped is True
    assert container_id not in tracker["mount_witness_sessions"]


@pytest.mark.parametrize("pipe_state", ["eof", "unsolicited", "stderr"])
def test_two_domain_attach_check_alive_rejects_eof_and_unsolicited_output(pipe_state):
    import os

    read_fd, write_fd = os.pipe()
    err_read_fd, err_write_fd = os.pipe()
    stdout = os.fdopen(read_fd, "rb", buffering=0)
    stderr = os.fdopen(err_read_fd, "rb", buffering=0)
    if pipe_state == "eof":
        os.close(write_fd)
    elif pipe_state == "unsolicited":
        os.write(write_fd, b"unexpected")
    else:
        os.write(err_write_fd, b"private stderr")
    fake_process = SimpleNamespace(poll=lambda: None)
    attach = object.__new__(TWO_DOMAIN["MountWitnessAttach"])
    attach.process = fake_process
    attach.stdout = stdout
    attach.stderr = stderr
    attach.stderr_bytes = bytearray()
    attach.stderr_truncated = False
    attach.stopped = False
    with pytest.raises(TWO_DOMAIN["MountWitnessTransportError"]) as caught:
        attach.check_alive()
    if pipe_state == "stderr":
        assert caught.value.code == "mount-witness-unsolicited-output"
        assert caught.value.private_stderr == b"private stderr"
    stdout.close()
    stderr.close()
    if pipe_state != "eof":
        os.close(write_fd)
    os.close(err_write_fd)


def test_two_domain_mount_witness_stderr_capture_is_bounded():
    attach = object.__new__(TWO_DOMAIN["MountWitnessAttach"])
    attach.stderr_bytes = bytearray()
    attach.stderr_truncated = False
    private_stderr = b"x" * (TWO_DOMAIN["MAX_MOUNT_WITNESS_STDERR_BYTES"] + 17)
    attach._capture_stderr(private_stderr)
    assert len(attach.stderr_bytes) == TWO_DOMAIN["MAX_MOUNT_WITNESS_STDERR_BYTES"]
    assert attach.stderr_truncated is True


@pytest.mark.parametrize(
    "binding_available,persist_failure",
    [(False, False), (True, False), (True, True)],
)
def test_two_domain_policy_finding_becomes_fail_only_after_external_binding(
    binding_available, persist_failure, tmp_path, monkeypatch,
):
    module_globals = TWO_DOMAIN["_install_observer_files"].__globals__
    container_id = "d" * 64
    run_id = "run-policy-finding"
    role = "source"
    image_id = "sha256:" + "c" * 64
    record, _valid_witness = _active_mount_witness_fixture()
    record["Id"] = container_id
    record["Image"] = image_id
    record["Config"]["Labels"] = {
        "openrepotools.bite4.run": run_id,
        "openrepotools.bite4.role": role,
    }
    record["State"].update({"Running": True, "Pid": 81, "Status": "running"})
    record["State"]["StartedAt"] = "2026-09-23T02:03:04.123456789Z"
    record["Mounts"] = [{
        "Type": "volume", "Name": "state-volume",
        "Destination": "/opt/state", "RW": True,
    }]
    unsafe_raw = _mountinfo_witness_sample().replace(b"98304k", b"98305k")
    nonce = "e" * 32
    response = TWO_DOMAIN["_decode_mount_witness_frame"](
        TWO_DOMAIN["probe"]._canonical_json({
            "schema": "openrepotools-mount-witness-response/v1",
            "nonce": nonce,
            "stage": "before-upload",
            "start_token": "987654321",
            "mount_namespace": "mnt:[4026535000]",
            "mountinfo_b64": base64.b64encode(unsafe_raw).decode("ascii"),
        }) + b"\n",
        nonce=nonce,
        stage="before-upload",
    )
    assert response["_policy_finding_code"] == "mountinfo-tmpfs-size-profile-mismatch"
    assert "_normalized_mounts" not in response

    class FakeAttach:
        def __init__(self, _identity):
            self.initialized = True

        def require_initialized(self):
            assert self.initialized is True

        def exchange(self, stage):
            assert stage == "before-upload"
            return response

    observer = TWO_DOMAIN["TwoDomainObserver"]("positive")
    observer.run_id = run_id
    observer.engine_containers[container_id] = {
        "role": role, "create": 1, "start": 1, "die": 0, "destroy": 0,
    }
    observer.wait_engine_event = lambda **_kwargs: None
    observer.ensure_engine_healthy = lambda: None
    binding = {
        "run_id": run_id,
        "container_id": container_id,
        "role": role,
        "create_count": 1,
        "start_count": 1,
        "die_count": 0,
        "destroy_count": 0,
    }
    binding["event_binding_digest"] = TWO_DOMAIN["_digest"](binding)
    calls = 0

    def engine_binding(_identity, _role):
        nonlocal calls
        calls += 1
        if calls == 2 and not binding_available:
            raise RuntimeError("event witness absent")
        return binding

    observer.mount_witness_engine_binding = engine_binding
    monkeypatch.setitem(module_globals, "MountWitnessAttach", FakeAttach)
    docker_calls = []

    def fake_docker(*args, **_kwargs):
        docker_calls.append(args)
        return SimpleNamespace(stdout=b"")

    monkeypatch.setitem(module_globals, "_docker", fake_docker)
    monkeypatch.setitem(module_globals, "_inspect_container", lambda *_a, **_k: record)
    if persist_failure:
        def fail_finding_persist(**_kwargs):
            raise OSError("synthetic ledger fsync failure")

        monkeypatch.setitem(
            module_globals, "_persist_bound_mount_witness_finding",
            fail_finding_persist,
        )
    tracker = {"containers": [{"id": container_id, "role": role}]}
    expected = {
        "/opt/state": ("volume", "state-volume", True),
        "/tmp": ("tmpfs", None, True),
        "/opt/loopback": ("tmpfs", None, True),
    }
    if binding_available and not persist_failure:
        with pytest.raises(TWO_DOMAIN["KnownViolation"]) as caught:
            TWO_DOMAIN["_install_observer_files"](
                container_id, None, run_id=run_id, role=role,
                image_id=image_id, private_dir=tmp_path / "private",
                observer=observer, expected_mounts=expected, tracker=tracker,
            )
        assert caught.value.code == "mountinfo-tmpfs-size-profile-mismatch"
        intent_path = (
            tmp_path / "private" / "mount-witness"
            / (role + "-" + TWO_DOMAIN["_digest"](container_id)[:24])
            / "mount-witness-before-upload.json"
        )
        payload = json.loads(intent_path.read_text())["payload"]
        assert payload["policy_finding_code"] == caught.value.code
        assert payload["event_binding"] == binding
        assert base64.b64decode(payload["mountinfo_b64"]) == unsafe_raw
    elif not binding_available:
        with pytest.raises(RuntimeError, match="event witness absent"):
            TWO_DOMAIN["_install_observer_files"](
                container_id, None, run_id=run_id, role=role,
                image_id=image_id, private_dir=tmp_path / "private",
                observer=observer, expected_mounts=expected, tracker=tracker,
            )
        assert not list((tmp_path / "private").rglob("mount-witness-before-upload.json"))
    else:
        with pytest.raises(OSError, match="synthetic ledger fsync failure"):
            TWO_DOMAIN["_install_observer_files"](
                container_id, None, run_id=run_id, role=role,
                image_id=image_id, private_dir=tmp_path / "private",
                observer=observer, expected_mounts=expected, tracker=tracker,
            )
        assert tracker["normal_arm_failure_stage"] == "mount-witness-finding-persistence"
        assert tracker["mount_witness_provisional_policy_finding"] == (
            "mountinfo-tmpfs-size-profile-mismatch"
        )
        assert not list((tmp_path / "private").rglob("mount-witness-before-upload.json"))
    assert not any(call and call[0] == "exec" for call in docker_calls)


@pytest.mark.parametrize("mutation", ["nonce", "stage", "duplicate-key", "oversized"])
def test_two_domain_mount_witness_decoder_rejects_stale_duplicate_and_oversized_frames(mutation):
    raw = _mountinfo_witness_sample()
    nonce = "a" * 32
    value = {
        "schema": "openrepotools-mount-witness-response/v1",
        "nonce": nonce,
        "stage": "before-upload",
        "start_token": "987654321",
        "mount_namespace": "mnt:[4026535000]",
        "mountinfo_b64": base64.b64encode(raw).decode("ascii"),
    }
    if mutation == "nonce":
        value["nonce"] = "b" * 32
    elif mutation == "stage":
        value["stage"] = "before-work"
    if mutation == "duplicate-key":
        frame = (
            b'{"schema":"openrepotools-mount-witness-response/v1",'
            b'"nonce":"' + nonce.encode() + b'","nonce":"' + nonce.encode()
            + b'","stage":"before-upload","start_token":"987654321",'
            b'"mount_namespace":"mnt:[4026535000]","mountinfo_b64":"'
            + base64.b64encode(raw) + b'"}\n'
        )
    elif mutation == "oversized":
        frame = b"x" * (TWO_DOMAIN["MAX_MOUNT_WITNESS_RESPONSE_BYTES"] + 1) + b"\n"
    else:
        frame = TWO_DOMAIN["probe"]._canonical_json(value) + b"\n"
    with pytest.raises(RuntimeError):
        TWO_DOMAIN["_decode_mount_witness_frame"](
            frame, nonce=nonce, stage="before-upload",
        )


@pytest.mark.parametrize("raw", [b"", b"x" * (TWO_DOMAIN["MAX_MOUNTINFO_BYTES"] + 1)])
def test_two_domain_corrupt_or_oversized_witness_is_inconclusive_not_policy_fail(raw):
    nonce = "a" * 32
    frame = TWO_DOMAIN["probe"]._canonical_json({
        "schema": "openrepotools-mount-witness-response/v1",
        "nonce": nonce,
        "stage": "before-upload",
        "start_token": "987654321",
        "mount_namespace": "mnt:[4026535000]",
        "mountinfo_b64": base64.b64encode(raw).decode("ascii"),
    }) + b"\n"
    with pytest.raises(RuntimeError) as caught:
        TWO_DOMAIN["_decode_mount_witness_frame"](
            frame, nonce=nonce, stage="before-upload",
        )
    assert not isinstance(caught.value, TWO_DOMAIN["KnownViolation"])


def test_two_domain_mount_witness_transport_error_stderr_is_private_abort_only(
    tmp_path, monkeypatch,
):
    module_globals = TWO_DOMAIN["_run_arm"].__globals__
    monkeypatch.setattr(
        TWO_DOMAIN["TwoDomainObserver"], "start_engine_stream",
        lambda self, run_id: None,
    )
    monkeypatch.setitem(
        module_globals,
        "_run_arm_impl",
        lambda **_kwargs: (_ for _ in ()).throw(
            TWO_DOMAIN["MountWitnessTransportError"](
                "mount-witness-attach-stderr-observed",
                stderr=b"private witness diagnostic",
                truncated=False,
            )
        ),
    )
    monkeypatch.setitem(
        module_globals, "_quarantine_run_owned_resources",
        lambda **_kwargs: {"reason_codes": [], "volumes_removed": False},
    )
    result = TWO_DOMAIN["_run_arm"](
        arm="positive", run_id="run-private-witness",
        image_id="sha256:" + "c" * 64, cli_path="/private/sdk/cli",
        selected={}, private_dir=tmp_path / "private-artifacts",
    )
    abort_path = tmp_path / "private-artifacts" / "ledger" / "arm-abort.json"
    payload = json.loads(abort_path.read_text())["payload"]
    assert payload["private_mount_witness_error_code"] == "mount-witness-attach-stderr-observed"
    assert base64.b64decode(payload["private_mount_witness_stderr_b64"]) == b"private witness diagnostic"
    assert "private witness diagnostic" not in json.dumps(result)


def test_two_domain_undurable_provisional_policy_finding_is_inconclusive(
    tmp_path, monkeypatch,
):
    module_globals = TWO_DOMAIN["_run_arm"].__globals__
    monkeypatch.setattr(
        TWO_DOMAIN["TwoDomainObserver"], "start_engine_stream",
        lambda self, run_id: None,
    )

    def fail_before_witness_durability(**kwargs):
        tracker = kwargs["tracker"]
        tracker["normal_arm_failure_stage"] = "mount-witness-finding-persistence"
        tracker["mount_witness_provisional_policy_finding"] = (
            "mountinfo-tmpfs-size-profile-mismatch"
        )
        raise OSError("synthetic witness ledger fsync failure")

    monkeypatch.setitem(module_globals, "_run_arm_impl", fail_before_witness_durability)
    monkeypatch.setitem(
        module_globals, "_quarantine_run_owned_resources",
        lambda **_kwargs: {"reason_codes": [], "volumes_removed": False},
    )
    result = TWO_DOMAIN["_run_arm"](
        arm="positive", run_id="run-undurable-finding",
        image_id="sha256:" + "c" * 64, cli_path="/private/sdk/cli",
        selected={}, private_dir=tmp_path / "private-artifacts",
    )
    assert result["status"] == "inconclusive"
    assert "witness-durability-incomplete" in result["reason_codes"]
    assert "provisional-mountinfo-tmpfs-size-profile-mismatch" in result["reason_codes"]
    assert result["cleanup_complete"] is False
    assert result["support_claim"] is False


def test_two_domain_attach_initialization_failure_terminates_and_closes_pipes(monkeypatch):
    module_globals = TWO_DOMAIN["MountWitnessAttach"].__init__.__globals__

    class FakeStream:
        def __init__(self):
            self.closed = False

        def fileno(self):
            return 17

        def close(self):
            self.closed = True

    class FakeProcess:
        def __init__(self):
            self.stdin = FakeStream()
            self.stdout = FakeStream()
            self.stderr = FakeStream()
            self.returncode = None
            self.terminated = False

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = -15

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            self.returncode = -9

    process = FakeProcess()
    monkeypatch.setattr(
        TWO_DOMAIN["subprocess"], "Popen", lambda *_a, **_k: process,
    )
    monkeypatch.setattr(
        TWO_DOMAIN["os"], "set_blocking",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("synthetic fcntl error")),
    )
    with pytest.raises(TWO_DOMAIN["MountWitnessTransportError"]) as caught:
        TWO_DOMAIN["MountWitnessAttach"]("f" * 64)
    assert caught.value.code == "mount-witness-attach-pipe-setup-failed"
    assert process.terminated is True
    assert all(stream.closed for stream in (process.stdin, process.stdout, process.stderr))


def test_two_domain_attach_setup_reap_uncertainty_keeps_a_tracked_client(monkeypatch):
    class FakeStream:
        def __init__(self):
            self.closed = False

        def fileno(self):
            return 23

        def close(self):
            self.closed = True

    class FakeProcess:
        def __init__(self):
            self.stdin = FakeStream()
            self.stdout = FakeStream()
            self.stderr = FakeStream()
            self.terminated = False
            self.killed = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            raise TWO_DOMAIN["subprocess"].TimeoutExpired("docker attach", timeout)

    process = FakeProcess()
    monkeypatch.setattr(
        TWO_DOMAIN["subprocess"], "Popen", lambda *_a, **_k: process,
    )
    monkeypatch.setattr(
        TWO_DOMAIN["os"], "set_blocking",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("synthetic fcntl error")),
    )
    attach = TWO_DOMAIN["MountWitnessAttach"]("e" * 64)
    with pytest.raises(TWO_DOMAIN["MountWitnessTransportError"]) as caught:
        attach.require_initialized()
    assert caught.value.code == "mount-witness-attach-reap-incomplete"
    assert process.terminated is True
    assert process.killed is True
    assert all(not stream.closed for stream in (process.stdin, process.stdout, process.stderr))


def test_two_domain_attach_stop_drain_rejects_late_output():
    import os

    out_read, out_write = os.pipe()
    err_read, err_write = os.pipe()
    stdin_read, stdin_write = os.pipe()
    stdout = os.fdopen(out_read, "rb", buffering=0)
    stderr = os.fdopen(err_read, "rb", buffering=0)
    stdin = os.fdopen(stdin_write, "wb", buffering=0)
    os.write(out_write, b"late frame\n")

    class FakeProcess:
        returncode = 0

        def __init__(self):
            self.waited = False

        def poll(self):
            return 0

        def wait(self, timeout=None):
            self.waited = True
            return 0

    attach = object.__new__(TWO_DOMAIN["MountWitnessAttach"])
    attach.process = FakeProcess()
    attach.stdin, attach.stdout, attach.stderr = stdin, stdout, stderr
    attach.stderr_bytes = bytearray()
    attach.stderr_truncated = False
    attach.stopped = False
    try:
        with pytest.raises(TWO_DOMAIN["MountWitnessTransportError"], match="output-after-container-stop"):
            attach.finish_after_stop()
    finally:
        for stream in (stdin, stdout, stderr):
            stream.close()
        for fd in (out_write, err_write, stdin_read):
            os.close(fd)


@pytest.mark.parametrize("source_phase", [False, True], ids=["legacy", "source"])
def test_runtime_observe_reaches_popen_for_legacy_and_source_initializers(
    monkeypatch, source_phase,
):
    class PopenReached(Exception):
        pass

    payload = b"selected probe cli bytes"
    cli_digest = hashlib.sha256(payload).hexdigest()

    class FakeServer:
        server_address = ("127.0.0.1", 32123)

        def __init__(self, *_args, **_kwargs):
            self.gateway = None

        def serve_forever(self):
            return None

        def shutdown(self):
            return None

        def server_close(self):
            return None

    class FakeThread:
        def __init__(self, *, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

        def join(self, timeout=None):
            return None

    class FakeV1Ledger:
        def __init__(self, _workspace):
            pass

        def prepare(self):
            return None

        def record_source_facts(self, **_facts):
            return None

        def snapshot(self):
            return {}

    real_open = builtins.open

    def fake_open(path, mode="r", *args, **kwargs):
        if os.fspath(path) == "/opt/loopback/claude" and mode == "rb":
            return io.BytesIO(payload)
        return real_open(path, mode, *args, **kwargs)

    def fake_popen(*_args, **_kwargs):
        raise PopenReached

    runtime_globals = PROBE["runtime_observe"].__globals__
    monkeypatch.setattr(PROBE["Path"], "mkdir", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(PROBE["subprocess"], "Popen", fake_popen)
    monkeypatch.setattr(
        PROBE["subprocess"], "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=PROBE["PINNED_CLI_VERSION"]),
    )
    monkeypatch.setattr(PROBE["threading"], "Thread", FakeThread)
    monkeypatch.setitem(runtime_globals, "ThreadingHTTPServer", FakeServer)
    monkeypatch.setitem(runtime_globals, "observe_store", lambda *_args, **_kwargs: {})
    monkeypatch.setitem(
        runtime_globals, "capture_runtime_history_records",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setitem(runtime_globals, "StopThenResumeV1Ledger", FakeV1Ledger)

    expected = {"cli_sha256": cli_digest, "arguments": []}
    if source_phase:
        expected.update({
            "mode": PROBE["STOP_THEN_RESUME_V1"],
            "control_mode": "interrupt",
            "two_domain_phase": "source",
            "state_root": "/opt/state",
            "source_invocation": "source-invocation-fixture",
        })

    with pytest.raises(PopenReached):
        PROBE["runtime_observe"](expected)


def test_runtime_main_projects_generic_error_to_bounded_error_site(
    monkeypatch, capsys,
):
    private_message = "private traceback message /secret/source/report"

    def fail_runtime(_expected):
        raise NameError(private_message)

    runtime_globals = PROBE["runtime_main"].__globals__
    monkeypatch.setitem(runtime_globals, "runtime_observe", fail_runtime)
    PROBE["runtime_main"]("{}")
    published = capsys.readouterr().out
    report = json.loads(published)

    assert report["error_type"] == "NameError"
    assert report["error_site"]["component"] == "managed_native_loopback"
    assert report["error_site"]["function"] == "runtime_main"
    assert type(report["error_site"]["line"]) is int
    assert report["error_site"]["line"] > 0
    assert private_message not in published
    assert "/secret/source/report" not in published


def _run_arm_with_source_runtime_report(
    tmp_path, monkeypatch, source_report, *, fail_private_writer=False,
    private_dir_name="positive-private-source-report",
):
    module_globals = TWO_DOMAIN["_run_arm"].__globals__
    events = []
    quarantine_calls = []

    class Observer:
        def __init__(self, arm):
            self.arm = arm
            self.private_values = []
            self.engine_error = None

        def start_engine_stream(self, _run_id):
            return None

        def __call__(self, event, identity=None, payload=None):
            events.append(("observer", event, identity, payload))

        def wait_engine_event(self, **_kwargs):
            return None

        def report(self):
            return []

        def finish_engine_stream(self):
            return None

        def verify_lifecycle(self, **_kwargs):
            return None

    monkeypatch.setitem(module_globals, "TwoDomainObserver", Observer)
    monkeypatch.setitem(
        module_globals, "_volume_create",
        lambda name, _run_id, role, **_kwargs: (
            events.append(("volume-create", role)) or name
        ),
    )
    monkeypatch.setitem(
        module_globals, "_validate_new_volume",
        lambda *_args, **_kwargs: {
            "Driver": "local", "Scope": "local", "Options": None,
        },
    )
    monkeypatch.setitem(
        module_globals, "_create_container",
        lambda **_kwargs: "source-container-private-id-123456789",
    )
    monkeypatch.setitem(
        module_globals, "_install_observer_files", lambda *_a, **_k: None,
    )
    monkeypatch.setitem(
        module_globals, "_container_role_exists", lambda *_a, **_k: False,
    )
    monkeypatch.setitem(
        module_globals, "_require_mount_witness_ready", lambda *_a, **_k: None,
    )
    def runtime_exec(_container_id, expected):
        events.append(("runtime-returned",))
        if callable(source_report):
            return source_report(expected)
        return source_report

    monkeypatch.setitem(module_globals, "_runtime_exec", runtime_exec)
    actual_writer = TWO_DOMAIN["_write_private_report"]

    def private_writer(path, report):
        events.append(("private-report-write", path.name))
        if fail_private_writer:
            raise OSError("private persistence failure /secret/message")
        return actual_writer(path, report)

    monkeypatch.setitem(module_globals, "_write_private_report", private_writer)
    monkeypatch.setitem(module_globals, "_stop_engine_observer", lambda _observer: None)

    def quarantine(**_kwargs):
        quarantine_calls.append(True)
        return {"reason_codes": [], "volumes_removed": False}

    monkeypatch.setitem(module_globals, "_quarantine_run_owned_resources", quarantine)
    result = TWO_DOMAIN["_run_arm"](
        arm="positive",
        run_id="run-private-source-report-fixture",
        image_id="sha256:" + "c" * 64,
        cli_path="/private/sdk/cli-fixture",
        selected={"sdk_version": "pinned-fixture"},
        private_dir=tmp_path / private_dir_name,
    )
    return result, events, quarantine_calls, tmp_path / private_dir_name


def test_source_runtime_fallback_is_private_and_stops_before_later_effects(
    tmp_path, monkeypatch,
):
    private_marker = "private-fallback-error-marker-123456"
    fallback = {
        "schema": "lane-managed-loopback/v1",
        "verdict": "inconclusive",
        "support_claim": False,
        "error_type": "NameError",
        "error_site": {
            "component": "managed_native_loopback",
            "function": "runtime_observe",
            "line": 8693,
        },
        "private_message": private_marker,
    }

    result, events, quarantine_calls, private_dir = _run_arm_with_source_runtime_report(
        tmp_path, monkeypatch, fallback,
    )

    assert result["status"] == "inconclusive"
    assert result["reason_codes"] == ["source-runtime-report-invalid"]
    assert quarantine_calls == [True]
    public_report = json.dumps(result, sort_keys=True)
    assert private_marker not in public_report
    assert "/private/sdk/cli-fixture" not in public_report
    assert "private_message" not in public_report

    event_names = [event[1] for event in events if event[0] == "observer"]
    assert "source-container-stop-intent" not in event_names
    assert "source-container-removed" not in event_names
    assert "target-volume-created" not in event_names
    assert [event[1] for event in events if event[0] == "volume-create"] == [
        "source-state",
    ]
    runtime_return_index = next(
        i for i, event in enumerate(events) if event[0] == "runtime-returned"
    )
    private_write_index = next(
        i for i, event in enumerate(events) if event[0] == "private-report-write"
    )
    assert private_write_index == runtime_return_index + 1

    private_path = private_dir / "source-runtime-report.json"
    assert private_path.is_file()
    assert private_path.stat().st_mode & 0o777 == 0o600
    envelope = json.loads(private_path.read_text(encoding="utf-8"))
    assert envelope["schema"] == TWO_DOMAIN["SOURCE_RUNTIME_REPORT_ENVELOPE_SCHEMA"]
    assert envelope["source_report"] == fallback
    assert envelope["source_report_digest"] == TWO_DOMAIN["_digest"](fallback)
    source_stop = json.loads(
        (private_dir / "ledger" / "source-stop.json").read_text(encoding="utf-8")
    )["payload"]
    assert envelope["source_invocation_digest"] == TWO_DOMAIN["_digest"](
        source_stop["source_invocation"]
    )
    assert envelope["source_container_id_digest"] == TWO_DOMAIN["_digest"](
        source_stop["source_container_id"]
    )


def test_valid_source_report_uses_probe_digest_and_is_persisted_as_accepted(
    tmp_path,
):
    source_invocation = "fixture-source-invocation-123456"
    source_container_id = "fixture-source-container-123456"
    report = {
        "schema": "openrepotools-bite4-source-phase/v1",
        "phase": "source",
        "support_claim": False,
        "target_code_reached": False,
        "source_invocation": source_invocation,
        "source_container_label": TWO_DOMAIN_PROBE.digest(source_container_id),
    }
    private_dir = TWO_DOMAIN["_create_private_directory"](
        tmp_path / "valid-source-report-private",
    )
    tracker = {}

    envelope = TWO_DOMAIN["_persist_and_validate_source_runtime_report"](
        report,
        source_invocation=source_invocation,
        source_container_id=source_container_id,
        private_dir=private_dir,
        tracker=tracker,
    )

    assert report["source_container_label"] == TWO_DOMAIN_PROBE.digest(
        source_container_id
    )
    assert tracker.get("source_runtime_report_invalid") is not True
    assert tracker["source_runtime_report_digest"] == TWO_DOMAIN["_digest"](report)
    assert envelope["source_report"] == report
    path = private_dir / "source-runtime-report.json"
    assert path.is_file()
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text(encoding="utf-8")) == envelope


def test_bound_source_report_target_reach_is_fail_and_missing_reach_is_inconclusive(
    tmp_path, monkeypatch,
):
    def source_report(expected, *, include_reach):
        report = {
            "schema": "openrepotools-bite4-source-phase/v1",
            "phase": "source",
            "support_claim": False,
            "source_invocation": expected["source_invocation"],
            "source_container_label": expected["source_container_label"],
        }
        if include_reach:
            report["target_code_reached"] = True
        return report

    explicit_reach, _events, quarantine_calls, private_dir = (
        _run_arm_with_source_runtime_report(
            tmp_path, monkeypatch,
            lambda expected: source_report(expected, include_reach=True),
            private_dir_name="explicit-reach-private",
        )
    )
    assert explicit_reach["status"] == "fail"
    assert explicit_reach["reason_codes"] == ["source-phase-reached-target-code"]
    assert quarantine_calls == [True]
    explicit_envelope = json.loads(
        (private_dir / "source-runtime-report.json").read_text(encoding="utf-8")
    )
    assert explicit_envelope["source_report"]["target_code_reached"] is True
    assert explicit_envelope["source_report"]["source_container_label"] == (
        TWO_DOMAIN_PROBE.digest("source-container-private-id-123456789")
    )

    missing_reach, _events, quarantine_calls, private_dir = (
        _run_arm_with_source_runtime_report(
            tmp_path, monkeypatch,
            lambda expected: source_report(expected, include_reach=False),
            private_dir_name="missing-reach-private",
        )
    )
    assert missing_reach["status"] == "inconclusive"
    assert missing_reach["reason_codes"] == ["source-runtime-report-invalid"]
    assert quarantine_calls == [True]
    missing_envelope = json.loads(
        (private_dir / "source-runtime-report.json").read_text(encoding="utf-8")
    )
    assert "target_code_reached" not in missing_envelope["source_report"]


def test_source_runtime_report_persistence_failure_fails_closed_before_progression(
    tmp_path, monkeypatch,
):
    fallback = {
        "schema": "lane-managed-loopback/v1",
        "error_type": "NameError",
        "private_message": "private-writer-error-fixture-123456",
    }
    result, events, quarantine_calls, private_dir = _run_arm_with_source_runtime_report(
        tmp_path, monkeypatch, fallback, fail_private_writer=True,
    )

    assert result["status"] == "inconclusive"
    assert "source-runtime-report-invalid" not in result["reason_codes"]
    assert quarantine_calls == [True]
    public_report = json.dumps(result, sort_keys=True)
    assert "private persistence failure" not in public_report
    assert "private-writer-error-fixture-123456" not in public_report
    assert not (private_dir / "source-runtime-report.json").exists()
    assert [event[1] for event in events if event[0] == "volume-create"] == [
        "source-state",
    ]
    event_names = [event[1] for event in events if event[0] == "observer"]
    assert "source-container-stop-intent" not in event_names
    assert "source-container-removed" not in event_names
    assert "target-volume-created" not in event_names
