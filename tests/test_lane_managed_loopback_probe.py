# SPDX-License-Identifier: Apache-2.0
"""Offline contracts for the bounded native loopback probe.

These tests use the probe's pure state helpers and offline handler methods. They
do not start a gateway, Claude, Docker, a model service, or any network listener.
"""

import hashlib
import json
from pathlib import Path
import runpy
import threading
from types import SimpleNamespace

import pytest


PROBE = runpy.run_path(
    str(Path(__file__).parent / "probes" / "managed_native_loopback.py")
)


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

    def write_sse(value):
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

    assert parent == {"kind": "agent-tool", "status": 200, "tool_name": "Agent"}
    assert child == {"kind": "bash-tool", "status": 200, "tool_name": None}
    assert drained_parent == {
        "kind": "text-end-turn",
        "status": 200,
        "tool_name": None,
    }
    assert drained_child == {
        "kind": "text-end-turn",
        "status": 200,
        "tool_name": None,
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
    assert held == {"kind": "held-error", "status": 409, "tool_name": None}
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
    assert held == {"kind": "held-error", "status": 409, "tool_name": None}
    assert released == {"kind": "text-end-turn", "status": 200, "tool_name": None}
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

    assert parent == {"kind": "protocol-error", "status": 409, "tool_name": None}
    assert child == {"kind": "protocol-error", "status": 409, "tool_name": None}
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

    assert parent == {"kind": "held-error", "status": 409, "tool_name": None}
    assert child == {"kind": "held-error", "status": 409, "tool_name": None}
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
