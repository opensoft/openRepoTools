# SPDX-License-Identifier: Apache-2.0
"""Offline refusal tests for the selected Bite 4 diagnostic acceptance path."""

from copy import deepcopy
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest


HARNESS = runpy.run_path(
    str(Path(__file__).parent / "probes" / "managed_two_domain.py")
)
MODE = HARNESS["HISTORY_QUERY_MODE"]


def complete_target_report():
    parent = "a" * 64
    nonce = "b" * 64
    challenge = "c" * 64
    return {
        "schema": "openrepotools-bite4-target-phase/v1",
        "history_query_mode": MODE,
        "support_claim": False,
        "same_parent_uuid": True,
        "target_parent_uuid_seen": True,
        "target_parent_uuid_digest": parent,
        "source_parent_uuid_digest": parent,
        "initialize_succeeded": True,
        "startup_gate": {
            "history_query_mode": MODE,
            "history_query_allowed": True,
            "history_query_skipped": False,
            "terminal_task_correlation_only": True,
            "support_claim": False,
            "reason_codes": [],
        },
        "history_query_sent": True,
        "history_query_read_complete": True,
        "target_process_exited": True,
        "gateway_server_fence_complete": True,
        "read_failed": False,
        "history_query_error_abort_or_tool_seen": False,
        "gateway_protocol_errors": [],
        "startup_result_count": 1,
        "startup_result_origins": ["task-notification"],
        "startup_result_origin_overflow": False,
        "startup_result_error_count": 0,
        "startup_result_parent_session_match_count": 1,
        "startup_result_parent_session_mismatch_count": 0,
        "startup_result_parent_session_id_digest": parent,
        "native_task_events": 1,
        "history_query_result_count": 1,
        "history_query_exact_parent_human_result_count": 1,
        "history_query_invalid_result_count": 0,
        "history_query_unexpected_frame_count": 0,
        "history_query_assistant_frame_count": 1,
        "history_query_assistant_message_id_digests": ["d" * 64],
        "history_query_assistant_message_id_missing_count": 0,
        "history_query_stdout_eof": True,
        "unparsed_frames": 0,
        "startup_partial_frames": 0,
        "startup_unexpected_frame_count": 0,
        "query_partial_frames": 0,
        "startup_request_observation": {
            "enabled": True,
            "closed": True,
            "overflow": False,
            "request_arrival_count": 0,
            "messages_route_arrival_count": 0,
            "other_route_arrival_count": 0,
            "parent_arrival_count": 0,
            "child_arrival_count": 0,
            "unclassified_arrival_count": 0,
            "in_flight_count": 0,
        },
        "request_arrival_witness": {
            "arrival_count": 1,
            "in_flight_count": 0,
            "overflow": False,
            "arrival_count_by_phase_route": {
                "target-diagnostic-query": {"/v1/messages": 1},
            },
        },
        "history_query_nonce_sha256": nonce,
        "history_query_challenge_sha256": challenge,
        "history_query_response_challenge_sha256": challenge,
        "history_query_gateway_witness": {
            "schema": "two-domain-history-query-gateway-witness/v1",
            "request_count": 1,
            "arrival_index": 1,
            "request_valid": True,
            "parent_request": True,
            "model_expected": True,
            "dummy_authorization": True,
            "nonce_present": True,
            "source_prompt_marker_present": True,
            "same_request_source_agent_history": True,
            "source_agent_tool_use_count": 1,
            "source_agent_tool_result_count": 1,
            "exact_source_agent_tool_use_count": 1,
            "all_tool_use_count": 1,
            "all_tool_result_count": 1,
            "history_order_valid": True,
            "response_write_succeeded": True,
            "window_closed": True,
            "response_write_count": 1,
            "response_write_failed": False,
            "request_facts_digest": "e" * 64,
            "response_message_id_digest": "d" * 64,
            "query_nonce_sha256": nonce,
            "response_challenge_sha256": challenge,
        },
    }


@pytest.mark.parametrize(
    "path,value",
    [
        (("history_query_mode",), "strict-v1"),
        (("history_query_result_count",), 0),
        (("history_query_stdout_eof",), False),
        (("gateway_server_fence_complete",), False),
        (("history_query_exact_parent_human_result_count",), 0),
        (("history_query_assistant_frame_count",), 2),
        (("history_query_assistant_message_id_digests",), ["f" * 64]),
        (("history_query_unexpected_frame_count",), 1),
        (("history_query_response_challenge_sha256",), "f" * 64),
        (("history_query_gateway_witness", "same_request_source_agent_history"), False),
        (("history_query_gateway_witness", "history_order_valid"), False),
        (("history_query_gateway_witness", "all_tool_use_count"), 2),
        (("history_query_gateway_witness", "dummy_authorization"), False),
        (("history_query_gateway_witness", "response_write_succeeded"), False),
        (("history_query_gateway_witness", "response_write_failed"), True),
        (("request_arrival_witness", "arrival_count"), 2),
        (("request_arrival_witness", "in_flight_count"), 1),
        (("startup_request_observation", "request_arrival_count"), 1),
        (("startup_result_origins",), ["human"]),
        (("startup_result_parent_session_match_count",), 0),
        (("startup_result_error_count",), 1),
        (("native_task_events",), 2),
        (("query_partial_frames",), 1),
        (("startup_unexpected_frame_count",), 1),
    ],
)
def test_two_domain_t049_target_requires_fresh_correlated_query(path, value):
    complete = complete_target_report()
    assert HARNESS["_target_history_query_complete"](complete) is True
    changed = deepcopy(complete)
    cursor = changed
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    assert HARNESS["_target_history_query_complete"](changed) is False


def test_two_domain_t049_assistant_id_absence_is_explicitly_bounded():
    complete = complete_target_report()
    complete["history_query_assistant_message_id_digests"] = []
    complete["history_query_assistant_message_id_missing_count"] = 1
    assert HARNESS["_target_history_query_complete"](complete) is True


def test_two_domain_t049_overall_observed_requires_both_arms(tmp_path, monkeypatch):
    module = HARNESS["_run_experiment"].__globals__
    selected = {
        "selected_cli": "/private/sdk/cli",
        "cli_sha256": "d" * 64,
        "sdk_version": "0.2.153",
    }
    monkeypatch.setitem(module, "_create_private_directory", lambda path: Path(path))
    monkeypatch.setitem(module, "_resolve_image_id", lambda _ref: "sha256:" + "c" * 64)
    monkeypatch.setitem(module, "_host_file_sha256", lambda _path: "d" * 64)
    monkeypatch.setattr(HARNESS["probe"], "_select_runtime", lambda _path: selected)
    arms_run = []

    def observed_arm(**kwargs):
        arms_run.append(kwargs["arm"])
        return {
            "arm": kwargs["arm"],
            "status": "observed",
            "release_candidate_ready": True,
            "cleanup_complete": True,
            "observer_complete": True,
            "release_refused": kwargs["arm"] == "negative",
            "target_container_created": kwargs["arm"] == "positive",
            "support_claim": False,
        }

    monkeypatch.setitem(module, "_run_arm", observed_arm)
    args = SimpleNamespace(
        explicit_release=True,
        sdk_python="/private/sdk/python",
        image="local-bench-image",
        private_artifacts=str(tmp_path / "artifacts"),
    )
    report = HARNESS["_run_experiment"](args)
    assert arms_run == ["positive", "negative"]
    assert report["diagnostic_status"] == "OBSERVED"

    def incomplete_positive(**kwargs):
        result = observed_arm(**kwargs)
        result["cleanup_complete"] = False
        return result

    monkeypatch.setitem(module, "_run_arm", incomplete_positive)
    arms_run.clear()
    report = HARNESS["_run_experiment"](args)
    assert arms_run == ["positive"]
    assert report["diagnostic_status"] == "INCONCLUSIVE"
    assert report["arms"][1]["reason_codes"] == ["positive-cleanup-incomplete"]
