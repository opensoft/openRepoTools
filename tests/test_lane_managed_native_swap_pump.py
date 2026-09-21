# SPDX-License-Identifier: Apache-2.0
"""Public native-swap release to the ordinary coordinator pump.

The setup in this module is deliberately the real native-swap fixture: the
controller, durable store, daemon, Unix socket, and target-held/released
transitions are production objects.  The runtime is the existing SDK-shaped
offline adapter with only two observations added for this tranche:

* a busy status envelope can keep the first post-release mailbox queued; and
* the first ordinary rollover send can hold the next pump tick long enough to
  observe that the following mailbox was not coalesced into the same send.

No durable operation, reservation, history, or positive native result is
constructed by the tests.  Every positive record is produced by the public
start/submit/swap/release path and the existing native ``prepare-invocation``
adapter boundary.
"""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any, Mapping

from test_lane_managed_native_swap_integration import (
    NativeSwapEvidenceProvider,
    NativeSwapRuntime,
    _harness,
    _reload_fixture_controller,
    _start_and_release,
)


def _wait_until(predicate: Any, *, timeout: float = 2.0) -> None:
    """Wait only for the real daemon worker to publish its next durable row."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


class PumpNativeSwapRuntime(NativeSwapRuntime):
    """Existing native runtime fixture with deterministic pump observations."""

    def __init__(self, *, hold_after_first_rollover: bool = True) -> None:
        super().__init__()
        self.pump_hold = False
        self.status_runner_override: str | None = None
        self.hold_after_first_rollover = hold_after_first_rollover

    async def status(self, participant_id: str) -> dict[str, Any]:
        value = await super().status(participant_id)
        if participant_id != "coordinator":
            return value
        if self.status_runner_override is not None:
            value["runner_instance_id"] = self.status_runner_override
            evidence = value.get("evidence")
            assert isinstance(evidence, dict)
            evidence["runner_instance_id"] = self.status_runner_override
        if self.pump_hold:
            evidence = value.get("evidence")
            assert isinstance(evidence, dict)
            evidence.update({
                "active_turn": True,
                "turn_terminal": False,
                "drained": False,
                "participant_quiescent": False,
                "tools_quiescent": False,
                "quiescent": False,
            })
        return value

    async def send(
            self, participant_id: str, message_id: str, payload_ref: Any,
    ) -> dict[str, Any]:
        result = await super().send(participant_id, message_id, payload_ref)
        # The first send is the real A startup invocation.  Holding after the
        # first later send (B) makes the daemon obtain a fresh busy observation
        # before it can consider C; it does not synthesize a reservation or
        # alter the durable operation.
        if self.hold_after_first_rollover and len(self.send_calls) == 2:
            self.pump_hold = True
        return result


def _ready_held_swap(fixture: Any) -> str:
    """Start A through the public socket, then reach a real target-held swap."""

    _start_and_release(fixture)
    swapped = fixture.request(
        "native-pump-swap", "swap", {"profile": "team-b"}
    )
    assert swapped["ok"] is True, json.dumps(swapped, sort_keys=True)
    assert swapped["result"]["phase"] == "ready-held"
    assert len(fixture.runtime.send_calls) == 1
    return str(swapped["result"]["operation_id"])


def _submit_held(fixture: Any, request_id: str, payload_ref: str) -> dict[str, Any]:
    result = fixture.request(request_id, "submit", {
        "recipient_id": "coordinator",
        "payload_ref": payload_ref,
        "sender_id": "user",
        "task_id": "task-root-coordinator",
    })
    assert result["ok"] is True, json.dumps(result, sort_keys=True)
    mailbox = result["result"]
    assert isinstance(mailbox, Mapping)
    assert mailbox["recipient_id"] == "coordinator"
    assert mailbox["state"] in {"fenced", "queued"}
    return dict(mailbox)


def _mailbox(record: Mapping[str, Any], message_id: str) -> Mapping[str, Any]:
    rows = record.get("mailboxes")
    assert isinstance(rows, list)
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("message_id") == message_id
    ]
    assert len(matches) == 1
    return matches[0]


def _operation(record: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
    operations = record.get("operations")
    assert isinstance(operations, list)
    matches = [
        row for row in operations
        if isinstance(row, Mapping) and row.get("operation_id") == operation_id
    ]
    assert len(matches) == 1
    return matches[0]


def _rollover_for(record: Mapping[str, Any], message_id: str) -> Mapping[str, Any]:
    rollovers = record.get("native_invocation_rollovers")
    assert isinstance(rollovers, Mapping)
    matches = [
        row for row in rollovers.values()
        if isinstance(row, Mapping) and row.get("next_mailbox_id") == message_id
    ]
    assert len(matches) == 1
    return matches[0]


def _assert_delivered_rollover(
        record: Mapping[str, Any], message_id: str,
) -> None:
    rollover = _rollover_for(record, message_id)
    assert rollover["state"] == "delivered"
    reservation = rollover.get("reservation_binding")
    assert isinstance(reservation, Mapping)
    dispatch_intent = rollover.get("dispatch_intent")
    assert isinstance(dispatch_intent, Mapping)
    assert dispatch_intent["message_id"] == message_id
    history_id = rollover.get("history_id")
    assert isinstance(history_id, str) and history_id
    histories = record.get("native_invocation_history")
    assert isinstance(histories, Mapping)
    history = histories.get(history_id)
    assert isinstance(history, Mapping)
    assert history["operation_id"] == rollover["operation_id"]
    assert history["invocation_id"] == rollover["prior_invocation_id"]


def test_native_swap_release_pumps_held_b_and_c_once_across_reload(
        tmp_path: Path,
) -> None:
    """A held swap queues B/C; release gates once and the normal pump drains them."""

    provider = NativeSwapEvidenceProvider()
    runtime = PumpNativeSwapRuntime()
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        operation_id = _ready_held_swap(fixture)
        b = _submit_held(fixture, "native-pump-b", "opaque://native-pump-b")
        c = _submit_held(fixture, "native-pump-c", "opaque://native-pump-c")
        b_id = str(b["message_id"])
        c_id = str(c["message_id"])
        held_record = fixture.state.read_json("controller.json")
        assert _operation(held_record, operation_id)["phase"] == "ready-held"
        assert _mailbox(held_record, b_id)["state"] in {"fenced", "queued"}
        assert _mailbox(held_record, c_id)["state"] in {"fenced", "queued"}
        assert [call["message_id"] for call in runtime.send_calls] == [
            runtime.send_calls[0]["message_id"]
        ]

        # The release route itself has a bounded pump tick.  A positively
        # observed busy invocation must leave both held mailboxes untouched.
        runtime.pump_hold = True
        released = fixture.request(
            "native-pump-release", "release", {"operation_id": operation_id}
        )
        assert released["ok"] is True, json.dumps(released, sort_keys=True)
        assert released["result"]["phase"] == "released"
        release_pump = released["result"].get("dispatch")
        assert isinstance(release_pump, Mapping)
        assert release_pump["dispatched"] == []
        assert release_pump["skipped"]
        assert release_pump["skipped"][0]["code"] == "busy"
        assert release_pump["skipped"][0]["reason"] == "status-not-idle"
        assert len(runtime.gate_receipts) == 1
        assert [ack["authorized"] for ack in runtime.native_swap_authorization_acks] == [
            True
        ]
        assert [call["message_id"] for call in runtime.send_calls] == [
            runtime.send_calls[0]["message_id"]
        ]
        assert _mailbox(fixture.state.read_json("controller.json"), b_id)["state"] in {
            "fenced", "queued",
        }

        # Recovery is observational only.  Whether the current source accepts
        # this already-released no-op recovery or refuses it for lack of a
        # recoverable rollover, it must not inline-send held B/C.
        recovered = fixture.request(
            "native-pump-recover", "recover", {"operation_id": operation_id}
        )
        assert recovered["schema"] == 2
        assert len(runtime.send_calls) == 1
        after_recovery = fixture.state.read_json("controller.json")
        assert _mailbox(after_recovery, b_id)["state"] in {"fenced", "queued"}
        assert _mailbox(after_recovery, c_id)["state"] in {"fenced", "queued"}

        # Release the first pump observation.  The persistent daemon worker
        # obtains a fresh idle status and sends exactly B; the send hook then
        # holds the next worker tick so C remains queued for inspection.
        runtime.pump_hold = False
        _wait_until(
            lambda: any(call["message_id"] == b_id for call in runtime.send_calls)
        )
        assert [call["message_id"] for call in runtime.send_calls].count(b_id) == 1
        after_b = fixture.state.read_json("controller.json")
        assert _mailbox(after_b, b_id)["state"] == "acknowledged"
        assert _mailbox(after_b, c_id)["state"] in {"fenced", "queued"}
        _assert_delivered_rollover(after_b, b_id)
        assert len(runtime.gate_receipts) == 1
        assert len(runtime.prepare_requests) == 1

        # A fresh idle observation lets the ordinary daemon pump consume the
        # exact next reservation.  It is not a recovery callback or a second
        # release, and no replacement reservation is allowed.
        runtime.pump_hold = False
        _wait_until(
            lambda: any(call["message_id"] == c_id for call in runtime.send_calls)
        )
        send_ids = [call["message_id"] for call in runtime.send_calls]
        assert send_ids.count(b_id) == 1
        assert send_ids.count(c_id) == 1
        assert len(runtime.gate_receipts) == 1
        assert len(runtime.prepare_requests) == 2
        assert len({
            request["reservation_id"] for request in runtime.prepare_requests
        }) == 2

        completed = fixture.state.read_json("controller.json")
        assert _operation(completed, operation_id)["phase"] == "released"
        assert _operation(completed, operation_id)["release_count"] == 1
        assert _mailbox(completed, c_id)["state"] == "acknowledged"
        _assert_delivered_rollover(completed, b_id)
        _assert_delivered_rollover(completed, c_id)
        context = completed.get("native_context")
        assert isinstance(context, Mapping)
        assert context["invocation_id"] == c_id
        histories = completed.get("native_invocation_history")
        assert isinstance(histories, Mapping)
        assert len(histories) == 2
        claims_before_reload = copy.deepcopy(fixture.state.read_lineage_claims())
        snapshot_before_reload = copy.deepcopy(completed)
        send_count_before_reload = len(runtime.send_calls)

        # A fresh controller reads the same history/reservation joins.  An
        # idempotent public submit only wakes the normal pump and cannot replay
        # either acknowledged mailbox or the native release gate.
        reloaded_runtime = _reload_fixture_controller(fixture)
        status = fixture.request("native-pump-reload-status", "status")
        assert status["ok"] is True, json.dumps(status, sort_keys=True)
        status_result = status["result"]
        assert status_result["native_context"] == snapshot_before_reload[
            "native_context"
        ]
        assert status_result["native_invocation_history"] == snapshot_before_reload[
            "native_invocation_history"
        ]
        assert status_result["native_invocation_rollovers"] == snapshot_before_reload[
            "native_invocation_rollovers"
        ]
        duplicate = fixture.request("native-pump-c", "submit", {
            "recipient_id": "coordinator",
            "payload_ref": "opaque://native-pump-c",
            "sender_id": "user",
            "task_id": "task-root-coordinator",
        })
        assert duplicate["ok"] is True, json.dumps(duplicate, sort_keys=True)
        assert duplicate["result"]["message_id"] == c_id
        assert len(reloaded_runtime.send_calls) == send_count_before_reload
        assert fixture.state.read_json("controller.json") == snapshot_before_reload
        assert fixture.state.read_lineage_claims() == claims_before_reload
        runtime.pump_hold = False
        _wait_until(lambda: fixture.daemon._dispatch_pump_task is None)


def test_native_swap_pump_stale_runner_keeps_held_mail_queued_without_gate_replay(
        tmp_path: Path,
) -> None:
    """A stale runtime runner status fences pump admission, not the release gate."""

    provider = NativeSwapEvidenceProvider()
    runtime = PumpNativeSwapRuntime(hold_after_first_rollover=False)
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        operation_id = _ready_held_swap(fixture)
        b = _submit_held(fixture, "native-pump-stale-b", "opaque://native-pump-stale-b")
        b_id = str(b["message_id"])
        runtime.status_runner_override = "stale-native-target-runner"
        released = fixture.request(
            "native-pump-stale-release", "release", {"operation_id": operation_id}
        )
        assert released["ok"] is True, json.dumps(released, sort_keys=True)
        assert released["result"]["phase"] == "released"
        dispatch = released["result"].get("dispatch")
        assert isinstance(dispatch, Mapping)
        assert dispatch["dispatched"] == []
        assert dispatch["skipped"]
        assert dispatch["skipped"][0]["code"] == "busy"
        assert dispatch["skipped"][0]["reason"] == "status-runner-mismatch"
        assert len(runtime.gate_receipts) == 1
        assert len(runtime.native_swap_authorization_acks) == 1
        assert len(runtime.send_calls) == 1
        stale_record = fixture.state.read_json("controller.json")
        assert _mailbox(stale_record, b_id)["state"] in {"fenced", "queued"}

        # The stale runner observation is removed only by a new status read;
        # the retry is the normal released public submit/pump wake and not a
        # recovery proof or a second release authorization.
        runtime.status_runner_override = None
        duplicate = fixture.request("native-pump-stale-b", "submit", {
            "recipient_id": "coordinator",
            "payload_ref": "opaque://native-pump-stale-b",
            "sender_id": "user",
            "task_id": "task-root-coordinator",
        })
        assert duplicate["ok"] is True, json.dumps(duplicate, sort_keys=True)
        assert duplicate["result"]["message_id"] == b_id
        _wait_until(
            lambda: any(call["message_id"] == b_id for call in runtime.send_calls)
        )
        assert [call["message_id"] for call in runtime.send_calls].count(b_id) == 1
        assert len(runtime.gate_receipts) == 1
        assert len(runtime.native_swap_authorization_acks) == 1
        _wait_until(lambda: fixture.daemon._dispatch_pump_task is None)
