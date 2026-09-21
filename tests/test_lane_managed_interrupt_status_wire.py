# SPDX-License-Identifier: Apache-2.0
"""Public observational coordinator-interrupt status coverage.

These tests use the real managed state store, controller, daemon owner, and
Unix-socket transport.  The adapter is only the credential-free internal hook
fixture; no SDK, account, model, or live runtime is started.
"""

from __future__ import annotations

import asyncio
import copy
import json
import socket
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import pytest

from lane_managed_controller import ManagedController
from lane_managed_daemon import (
    NATIVE_ARCHITECTURE,
    NATIVE_SCHEMA_VERSION,
    serve_daemon,
)
from test_lane_managed_coordinator_interrupt import _evidence, _roster_identity
from test_lane_managed_interrupt_integration import (
    admitted_interrupt,
    real_interrupt_authority,
)


STATUS_SUMMARY_KEYS = {
    "runtime_acknowledged",
    "graph_quiescent",
    "children",
    "blockers",
    "process_exclusion",
    "request_observation",
    "seal",
    "progress_watermark",
}


def _request(request_id: str, generation: int) -> dict[str, Any]:
    return {
        "schema": NATIVE_SCHEMA_VERSION,
        "schema_version": NATIVE_SCHEMA_VERSION,
        "architecture": NATIVE_ARCHITECTURE,
        "request_id": request_id,
        "lane": "build",
        "generation": generation,
        "operation": "status",
        "body": {},
    }


def _read_response(client: socket.socket) -> dict[str, Any]:
    chunks: list[bytes] = []
    while True:
        chunk = client.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    return json.loads(b"".join(chunks).split(b"\n", 1)[0].decode("utf-8"))


def _send(socket_path: Path, request: Mapping[str, Any]) -> dict[str, Any]:
    payload = json.dumps(dict(request), sort_keys=True, separators=(",", ":"))
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(3.0)
        client.connect(str(socket_path))
        client.sendall(payload.encode("utf-8") + b"\n")
        return _read_response(client)


def _wait_for_socket(socket_path: Path, thread: threading.Thread) -> None:
    deadline = time.monotonic() + 3.0
    while not socket_path.exists() and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert socket_path.exists(), "managed daemon did not bind its socket"


def _stop_server(
    socket_path: Path,
    stop_event: threading.Event,
    thread: threading.Thread,
) -> None:
    stop_event.set()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.2)
            client.connect(str(socket_path))
    except OSError:
        pass
    thread.join(timeout=3.0)
    assert not thread.is_alive(), "managed daemon transport did not stop"


@contextmanager
def _public_status_server(
    tmp_path: Path,
    daemon: Any,
    *,
    max_requests: int,
) -> Iterator[Path]:
    socket_path = tmp_path / "managed-status.sock"
    stop_event = threading.Event()
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            serve_daemon(
                socket_path,
                daemon,
                max_requests=max_requests,
                stop_event=stop_event,
            )
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    _wait_for_socket(socket_path, thread)
    try:
        yield socket_path
    finally:
        if thread.is_alive():
            _stop_server(socket_path, stop_event, thread)
        else:
            thread.join(timeout=3.0)
        assert not errors, errors


def _durable_snapshot(store: Any) -> dict[str, Any]:
    return {
        "controller": copy.deepcopy(store.read_json("controller.json")),
        "claims": copy.deepcopy(store.read_lineage_claims()),
        "owner": copy.deepcopy(store.read_owner()),
    }


def _summary(result: Mapping[str, Any], interrupt_id: str) -> dict[str, Any]:
    summaries = result["coordinator_interrupt_summaries"]
    assert set(summaries) == {interrupt_id}
    value = summaries[interrupt_id]
    assert STATUS_SUMMARY_KEYS.issubset(value)
    return value


async def _authorize_interrupt(
    daemon: Any,
    adapter: Any,
    lineage: Any,
    *,
    descendant_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    base = await admitted_interrupt(daemon, adapter, lineage)
    frame = copy.deepcopy(base)
    roster = frame["interrupt"]["roster"]
    # Keep the fixture's sealed child/tool facts, while making the projection
    # scenario explicit.  The controller validates this as a real sealed
    # roster and recomputes the identity digest before durable authorization.
    roster["children"][0]["unresolved_effect_ids"] = []
    roster["descendant_ids"] = list(descendant_ids)
    frame["interrupt"]["roster_identity_digest"] = _roster_identity(roster)
    assert await adapter.interrupt_intent(frame) == {
        "recorded": True,
        "authorize_send": True,
        "interrupt_id": frame["interrupt"]["interrupt_id"],
    }
    return frame


def _status_result(response: Mapping[str, Any]) -> Mapping[str, Any]:
    assert response["ok"] is True
    result = response["result"]
    assert isinstance(result, Mapping)
    return result


def test_public_status_projects_real_interrupt_evidence_across_reload_without_effects(
    tmp_path, managed_workspace
):
    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )

    async def authorize() -> dict[str, Any]:
        return await _authorize_interrupt(daemon, adapter, lineage)

    frame = asyncio.run(authorize())
    interrupt_id = frame["interrupt"]["interrupt_id"]
    # If status ever reaches the runtime seam, fail rather than allowing a
    # summary request to look like an interrupt call.
    adapter.coordinator_interrupt = lambda *_args, **_kwargs: pytest.fail(
        "observational status must not call the runtime"
    )

    with _public_status_server(tmp_path, daemon, max_requests=3) as socket_path:
        before_initial = _durable_snapshot(store)
        initial = _status_result(
            _send(socket_path, _request("status-initial", lineage.owner_generation))
        )
        assert _durable_snapshot(store) == before_initial
        initial_summary = _summary(initial, interrupt_id)
        assert initial_summary["runtime_acknowledged"] is False
        assert initial_summary["graph_quiescent"] is False
        assert initial_summary["children"][0]["status"] is None
        assert initial_summary["process_exclusion"]["status"] == "unknown"
        assert initial_summary["request_observation"]["new_requests"] is None
        assert initial_summary["progress_watermark"] == 8
        assert initial_summary["seal"]["progress_watermark"] == 8
        assert "request-observation-missing" in initial_summary["blockers"]

        asyncio.run(
            adapter.interrupt_evidence(_evidence(frame, "runtime-ack"))
        )
        asyncio.run(
            adapter.interrupt_evidence(_evidence(frame, "member-terminal"))
        )
        before_partial = _durable_snapshot(store)
        partial = _status_result(
            _send(socket_path, _request("status-partial", lineage.owner_generation))
        )
        assert _durable_snapshot(store) == before_partial
        partial_summary = _summary(partial, interrupt_id)
        assert partial_summary["runtime_acknowledged"] is True
        assert partial_summary["children"][0]["status"] == "stopped"
        assert partial_summary["graph_quiescent"] is False
        assert partial_summary["request_observation"]["new_requests"] is None
        assert partial_summary["progress_watermark"] == 9

        for kind in (
            "tool-terminal",
            "admission-closed",
            "parent-drained",
            "request-observation",
            "process-excluded",
        ):
            asyncio.run(
                adapter.interrupt_evidence(_evidence(frame, kind))
            )

        # A fresh controller must derive the same projection from the durable
        # evidence rather than retaining the pre-reload in-memory aggregate.
        daemon.controller = ManagedController(
            store,
            runtime=adapter,
            _native_stop_daemon_id="daemon-test",
            _coordinator_interrupt_daemon_id="daemon-test",
        )
        before_final = _durable_snapshot(store)
        final = _status_result(
            _send(socket_path, _request("status-final", lineage.owner_generation))
        )
        assert _durable_snapshot(store) == before_final
        final_summary = _summary(final, interrupt_id)

    raw_record = before_final["controller"]["coordinator_interrupts"][interrupt_id]
    assert final["coordinator_interrupts"] == before_final["controller"][
        "coordinator_interrupts"
    ]
    assert raw_record["may_have_been_sent"] is True
    assert raw_record["authorization_count"] == 1
    assert final_summary != initial_summary
    assert final_summary["runtime_acknowledged"] is True
    # Every graph boundary is accounted for in this scenario, but that is not
    # a runtime capability or a successful account/lifecycle transition.
    assert final_summary["graph_quiescent"] is True
    assert final_summary["children"][0]["status"] == "stopped"
    assert final_summary["process_exclusion"]["status"] == "excluded"
    request_observation = final_summary["request_observation"]
    assert request_observation["observable"] is True
    assert request_observation["new_requests"] == 0
    assert request_observation["coverage_proven"] is False
    assert request_observation["pre_entry_observation_proven"] is False
    assert "request-observation-pre-entry-unproven" in final_summary["blockers"]
    assert final["live_sdk"] == "UNVERIFIED"
    assert final["live_capability"] == "UNVERIFIED"
    assert final["capability_status"] == "experimental"
    assert "safe_to_restore" not in final_summary
    assert "success" not in final_summary
    assert "capability" not in final_summary

    before_direct = _durable_snapshot(store)
    assert daemon.controller.coordinator_interrupt_status(interrupt_id) == final_summary
    assert _durable_snapshot(store) == before_direct


def test_public_status_keeps_opaque_descendant_as_blocker_even_when_id_matches_child(
    tmp_path, managed_workspace
):
    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )
    frame = asyncio.run(
        _authorize_interrupt(
            daemon,
            adapter,
            lineage,
            descendant_ids=("agent-1",),
        )
    )
    for kind in (
        "runtime-ack",
        "member-terminal",
        "tool-terminal",
        "admission-closed",
        "parent-drained",
        "request-observation",
        "process-excluded",
    ):
        asyncio.run(adapter.interrupt_evidence(_evidence(frame, kind)))

    with _public_status_server(tmp_path, daemon, max_requests=1) as socket_path:
        before = _durable_snapshot(store)
        response = _send(
            socket_path,
            _request("status-descendant", lineage.owner_generation),
        )
        result = _status_result(response)
        assert _durable_snapshot(store) == before

    summary = _summary(result, frame["interrupt"]["interrupt_id"])
    assert summary["graph_quiescent"] is False
    assert summary["descendants"] == [
        {
            "descendant_id": "agent-1",
            "mapped_admission_id": None,
            "resolved": False,
            "blockers": ["descendant-unproven:agent-1"],
        }
    ]
    assert "descendant-unproven:agent-1" in summary["blockers"]
    assert result["live_sdk"] == "UNVERIFIED"
    assert result["live_capability"] == "UNVERIFIED"


@pytest.mark.parametrize(
    "case,expected_code",
    [
        ("owner-generation", "stale-generation"),
        ("stale-request-observation", "stale-generation"),
        ("corrupt-ledger", "invalid"),
    ],
)
def test_public_status_refuses_stale_owner_stale_evidence_and_corrupt_ledger_without_mutation(
    tmp_path, managed_workspace, case, expected_code
):
    daemon, store, adapter, lineage = real_interrupt_authority(
        tmp_path, managed_workspace
    )
    frame = asyncio.run(_authorize_interrupt(daemon, adapter, lineage))
    if case == "stale-request-observation":
        asyncio.run(
            adapter.interrupt_evidence(_evidence(frame, "request-observation"))
        )

    raw = store.read_json("controller.json")
    record = raw["coordinator_interrupts"][frame["interrupt"]["interrupt_id"]]
    if case == "owner-generation":
        record["frame"]["interrupt"]["owner_generation"] = (
            lineage.owner_generation + 1
        )
    elif case == "stale-request-observation":
        record["evidence"]["evidence-request-observation"]["frame"]["evidence"][
            "data"
        ]["through_watermark"] = 6
    else:
        del record["evidence"]
    store.write_json("controller.json", raw)
    before = _durable_snapshot(store)

    with _public_status_server(tmp_path, daemon, max_requests=1) as socket_path:
        response = _send(
            socket_path,
            _request("status-refusal-" + case, lineage.owner_generation),
        )

    assert response["ok"] is False
    assert response["code"] == expected_code
    assert _durable_snapshot(store) == before
