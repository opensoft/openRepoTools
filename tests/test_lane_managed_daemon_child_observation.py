# SPDX-License-Identifier: Apache-2.0
"""Private daemon boundary for joined native-child observations.

These tests stop at the daemon/controller callback.  The controller consumer
is represented by a bounded authority double; they do not claim that a
selected SDK/runtime can produce a native child observation.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from lane_managed_daemon import DaemonError, ManagedDaemon


LANE = "build"
DAEMON_ID = "daemon-child-observation"
GENERATION = 7
PARTICIPANT_ID = "coordinator"
SESSION_ID = "session-child-observation"
RUNNER_ID = "runner-child-observation"
LINEAGE_ID = "lineage-child-observation"
INVOCATION_ID = "invocation-child-observation"
OBSERVATION_ID = "observation-child-1"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _observation(*, observation_id: str = OBSERVATION_ID) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-child-observation",
        "observation_id": observation_id,
        "source_identity": {
            "owner_generation": GENERATION,
            "lineage_id": LINEAGE_ID,
            "lineage_generation": 3,
            "session_uuid": SESSION_ID,
            "runner_incarnation": RUNNER_ID,
            "invocation_id": INVOCATION_ID,
        },
        "context_binding_digest": "a" * 64,
        "claim_digest": "b" * 64,
        "observation_watermark": 20,
        "terminal_outcome": "completed",
        "child": {
            "admission_id": "admission-child-1",
            "tool_use_id": "tool-child-1",
            "agent_id": "agent-child-1",
            "task_id": "task-child-1",
            "parent_agent_id": None,
            "invocation_id": INVOCATION_ID,
            "lineage_incarnation": 1,
            "trusted_definition_digest": "c" * 64,
            "start_watermark": 10,
            "task_start_event": {
                "event_uuid": "task-start-child-1",
                "watermark": 12,
                "task_type": "local_agent",
            },
            "status": "completed",
            "terminal_watermark": 15,
            "active_tool_ids": [],
            "uncertain_tool_ids": [],
            "unresolved_effect_ids": [],
        },
    }


def _frame(*, observation: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "native-child-observation",
        "participant_id": PARTICIPANT_ID,
        "session_id": SESSION_ID,
        "runner_instance_id": RUNNER_ID,
        "observation": copy.deepcopy(
            dict(observation or _observation())
        ),
    }


def _ack(observation: Mapping[str, Any]) -> dict[str, Any]:
    child = observation["child"]
    child_run_input = {
        "source_identity": observation["source_identity"],
        **{
            key: child[key]
            for key in (
                "admission_id", "tool_use_id", "agent_id", "task_id",
                "lineage_incarnation", "start_watermark",
            )
        },
    }
    return {
        "recorded": True,
        "observation_id": observation["observation_id"],
        "observation_digest": _digest(observation),
        "child_run_id": _digest(child_run_input),
        "observation_watermark": observation["observation_watermark"],
    }


class MemoryState:
    def __init__(self) -> None:
        self.owner = {
            "mode": "managed",
            "lane": LANE,
            "daemon_id": DAEMON_ID,
            "generation": GENERATION,
        }

    def enroll_managed(self, daemon_id: str, **_kwargs: Any) -> dict[str, Any]:
        assert daemon_id == DAEMON_ID
        return copy.deepcopy(self.owner)

    def read_owner(self, *, deadline: float | None = None) -> dict[str, Any]:
        del deadline
        return copy.deepcopy(self.owner)


class ObservationAdapter:
    def __init__(self) -> None:
        self.observation_callback: Any = None
        self.bind_count = 0

    def bind_native_child_observation(self, callback: Any) -> None:
        self.observation_callback = callback
        self.bind_count += 1


class ObservationController:
    def __init__(self, state: MemoryState) -> None:
        self.state = state
        self.calls: list[tuple[Any, ...]] = []
        self.kwargs: list[dict[str, Any]] = []
        self.ack_override: Any = None
        self.on_call: Any = None
        # The state-store owner intentionally has no coordinator aliases.
        # This independent live projection is the authoritative transport
        # identity fence used by the daemon before and after persistence.
        self.status_value: dict[str, Any] = {
            "generation": GENERATION,
            "coordinator_id": PARTICIPANT_ID,
            "participants": [{
                "participant_id": PARTICIPANT_ID,
                "session_id": SESSION_ID,
                "role": "coordinator",
            }],
            "native_context": {
                "lineage": {
                    "owner_generation": GENERATION,
                    "lineage_id": LINEAGE_ID,
                    "lineage_generation": 3,
                    "session_uuid": SESSION_ID,
                },
                "runner_incarnation": RUNNER_ID,
                "invocation_id": INVOCATION_ID,
            },
        }
        self.status_calls = 0

    def status(self) -> dict[str, Any]:
        self.status_calls += 1
        return copy.deepcopy(self.status_value)

    async def persist_native_child_observation(
            self, observation_id: str, generation: int,
            observation: Mapping[str, Any], *, expected_daemon_id: str,
    ) -> dict[str, Any]:
        self.calls.append((observation_id, generation, copy.deepcopy(dict(observation))))
        self.kwargs.append({"expected_daemon_id": expected_daemon_id})
        if self.on_call is not None:
            result = self.on_call()
            if asyncio.iscoroutine(result):
                await result
        if self.ack_override is not None:
            return copy.deepcopy(self.ack_override)
        return _ack(observation)


def _daemon(
        state: MemoryState | None = None,
        controller: ObservationController | None = None,
        adapter: ObservationAdapter | None = None,
) -> tuple[ManagedDaemon, MemoryState, ObservationController, ObservationAdapter]:
    state = state or MemoryState()
    controller = controller or ObservationController(state)
    adapter = adapter or ObservationAdapter()
    profiles = SimpleNamespace(
        resolve=lambda name: name,
        verify_transcript=lambda *args: {},
    )
    daemon = ManagedDaemon(
        state=state,
        adapter=adapter,
        profiles=profiles,
        controller=controller,
        lane=LANE,
        daemon_id=DAEMON_ID,
        opt_in=True,
    )
    return daemon, state, controller, adapter


def test_construct_dependencies_binds_only_private_observation_callback() -> None:
    daemon, _state, _controller, adapter = _daemon()

    async def scenario() -> None:
        await daemon.start()
        await daemon.start()
        assert adapter.bind_count == 1
        assert adapter.observation_callback.__self__ is daemon
        assert (
            adapter.observation_callback.__name__
            == "_persist_native_child_observation_callback"
        )

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "start_watermark, task_watermark",
    [(10, 12), (12, 10)],
)
def test_callback_forwards_exact_observation_and_ack_correlation(
        start_watermark: int, task_watermark: int,
) -> None:
    daemon, _state, controller, adapter = _daemon()
    daemon.owner_record = copy.deepcopy(_state.owner)
    daemon._owner_enrolled = True
    daemon.started = True
    daemon._construct_dependencies()
    frame = _frame()
    frame["observation"]["child"]["start_watermark"] = start_watermark
    frame["observation"]["child"]["task_start_event"]["watermark"] = task_watermark

    async def scenario() -> None:
        acknowledgement = await adapter.observation_callback(frame)
        assert acknowledgement == _ack(frame["observation"])

    asyncio.run(scenario())
    assert controller.status_calls == 2
    assert controller.calls == [
        (OBSERVATION_ID, GENERATION, frame["observation"])
    ]
    assert controller.kwargs == [{"expected_daemon_id": DAEMON_ID}]


@pytest.mark.parametrize(
    "field",
    ["participant_id", "session_id", "runner_instance_id"],
)
def test_callback_rejects_transport_identity_before_controller(
        field: str,
) -> None:
    daemon, _state, controller, adapter = _daemon()
    daemon.owner_record = copy.deepcopy(_state.owner)
    daemon._owner_enrolled = True
    daemon.started = True
    daemon._construct_dependencies()
    frame = _frame()
    frame[field] = "foreign-" + field

    async def scenario() -> None:
        with pytest.raises(DaemonError) as caught:
            await adapter.observation_callback(frame)
        assert caught.value.code in {"ownership-conflict", "stale-generation"}

    asyncio.run(scenario())
    assert controller.calls == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda frame: frame.update({"unexpected": True}),
        lambda frame: frame["observation"].update({"raw_runtime": {}}),
        lambda frame: frame["observation"]["child"].pop("task_id"),
        lambda frame: frame["observation"]["source_identity"].update(
            {"owner_generation": GENERATION + 1}
        ),
        lambda frame: frame["observation"].update(
            {"observation_watermark": 11}
        ),
        lambda frame: frame["observation"]["child"]["task_start_event"].update(
            {"watermark": 21}
        ),
        lambda frame: frame["observation"]["child"].update(
            {"terminal_watermark": 11}
        ),
    ],
)
def test_callback_rejects_closed_frame_malformed_observation_without_authority(
        mutate: Any,
) -> None:
    daemon, _state, controller, adapter = _daemon()
    daemon.owner_record = copy.deepcopy(_state.owner)
    daemon._owner_enrolled = True
    daemon.started = True
    daemon._construct_dependencies()
    frame = _frame()
    mutate(frame)

    async def scenario() -> None:
        with pytest.raises(DaemonError) as caught:
            await adapter.observation_callback(frame)
        assert caught.value.code in {
            "invalid", "stale-generation", "ownership-conflict",
        }

    asyncio.run(scenario())
    assert controller.calls == []


@pytest.mark.parametrize(
    "mutate, expected_code",
    [
        (lambda state, controller: state.owner.update(
            {"daemon_id": "replacement-daemon"}
        ),
         "ownership-conflict"),
        (lambda state, controller: state.owner.update(
            {"generation": GENERATION + 1}
        ),
         "stale-generation"),
        (lambda state, controller: controller.status_value.update(
            {"coordinator_id": "foreign-coordinator"}
        ),
         "ownership-conflict"),
        (lambda state, controller: controller.status_value["participants"][0].update(
            {"session_id": "new-session"}
        ),
         "stale-generation"),
        (lambda state, controller: controller.status_value["native_context"].update(
            {"runner_incarnation": "new-runner"}
        ),
         "stale-generation"),
    ],
)
def test_callback_rejects_stale_owner_before_controller(
        mutate: Any, expected_code: str,
) -> None:
    daemon, state, controller, adapter = _daemon()
    daemon.owner_record = copy.deepcopy(state.owner)
    daemon._owner_enrolled = True
    daemon.started = True
    daemon._construct_dependencies()
    mutate(state, controller)

    async def scenario() -> None:
        with pytest.raises(DaemonError) as caught:
            await adapter.observation_callback(_frame())
        assert caught.value.code == expected_code

    asyncio.run(scenario())
    assert controller.calls == []


@pytest.mark.parametrize("ack_mutation", [
    lambda ack: ack.update({"extra": True}),
    lambda ack: ack.pop("child_run_id"),
    lambda ack: ack.update({"observation_digest": "f" * 64}),
    lambda ack: ack.update({"observation_watermark": 21}),
])
def test_callback_rejects_noncorrelated_controller_ack(
        ack_mutation: Any,
) -> None:
    daemon, state, controller, adapter = _daemon()
    daemon.owner_record = copy.deepcopy(state.owner)
    daemon._owner_enrolled = True
    daemon.started = True
    daemon._construct_dependencies()
    observation = _observation()
    bad_ack = _ack(observation)
    ack_mutation(bad_ack)
    controller.ack_override = bad_ack

    async def scenario() -> None:
        with pytest.raises(DaemonError) as caught:
            await adapter.observation_callback(_frame(observation=observation))
        assert caught.value.code in {
            "invalid", "stale-generation", "uncertain-effect",
        }

    asyncio.run(scenario())
    assert len(controller.calls) == 1


def test_callback_rechecks_owner_after_controller_await() -> None:
    daemon, state, controller, adapter = _daemon()
    daemon.owner_record = copy.deepcopy(state.owner)
    daemon._owner_enrolled = True
    daemon.started = True
    daemon._construct_dependencies()

    async def replace_owner() -> None:
        state.owner["daemon_id"] = "replacement-daemon"

    controller.on_call = replace_owner

    async def scenario() -> None:
        with pytest.raises(DaemonError) as caught:
            await adapter.observation_callback(_frame())
        assert caught.value.code == "ownership-conflict"

    asyncio.run(scenario())
    assert len(controller.calls) == 1


def test_callback_rechecks_authoritative_controller_identity_after_await() -> None:
    daemon, state, controller, adapter = _daemon()
    daemon.owner_record = copy.deepcopy(state.owner)
    daemon._owner_enrolled = True
    daemon.started = True
    daemon._construct_dependencies()

    def replace_controller_identity() -> None:
        controller.status_value["coordinator_id"] = "replacement-coordinator"

    controller.on_call = replace_controller_identity

    async def scenario() -> None:
        with pytest.raises(DaemonError) as caught:
            await adapter.observation_callback(_frame())
        assert caught.value.code == "ownership-conflict"

    asyncio.run(scenario())
    assert len(controller.calls) == 1
    assert controller.status_calls == 2


def test_callback_requires_exact_controller_consumer_without_legacy_fallback() -> None:
    daemon, state, _controller, adapter = _daemon()
    daemon.controller = SimpleNamespace(
        send=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("child observation must not route through send")
        ),
        release=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("child observation must not release")
        ),
    )
    daemon.owner_record = copy.deepcopy(state.owner)
    daemon._owner_enrolled = True
    daemon.started = True
    daemon._construct_dependencies()

    async def scenario() -> None:
        with pytest.raises(DaemonError) as caught:
            await adapter.observation_callback(_frame())
        assert caught.value.code == "unsupported"

    asyncio.run(scenario())
