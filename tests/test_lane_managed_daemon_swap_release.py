# SPDX-License-Identifier: Apache-2.0
"""Private native-swap release authorization daemon boundary tests.

These tests stop at the daemon/controller callback.  They do not expose a
public release request, grant a capability through a payload, or construct a
runner process.  The runner/SDK owns the authenticated frame and calls the
daemon with the exact identity tuple pinned by runner-evidence.md.
"""

from __future__ import annotations

import asyncio
import copy
from typing import Any, Mapping

import pytest

from lane_managed_daemon import DaemonError, ManagedDaemon
from lane_managed_swap import canonical_digest


DAEMON_ID = "daemon-test"
LANE = "build"
GENERATION = 7
PARTICIPANT_ID = "coordinator"
SESSION_ID = "session-1"
RUNNER_ID = "runner-1"
VALIDATION_ID = "validation-1"


def _binding(**changes: Any) -> dict[str, Any]:
    value = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-swap-release-binding",
        "operation_id": "operation-1",
        "owner_generation": GENERATION,
        "expected_daemon_id": DAEMON_ID,
        "participant_id": PARTICIPANT_ID,
        "session_id": SESSION_ID,
        "runner_incarnation": RUNNER_ID,
        "lineage_id": "lineage-1",
        "lineage_generation": 1,
        "request_epoch_id": "request-epoch-1",
        "release_id": "release-1",
        "release_intent_digest": "a" * 64,
        "pre_release_evidence_digest": "b" * 64,
    }
    value.update(changes)
    value["binding_digest"] = canonical_digest(value)
    return value


def _ack(
        validation_id: str = VALIDATION_ID,
        *,
        authorized: bool = True,
        authorization_id: str = "authorization-1",
        binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    value = {
        "validation_id": validation_id,
        "authorized": authorized,
        "authorization_id": authorization_id,
        "binding": copy.deepcopy(dict(binding or _binding())),
    }
    value["authorization_digest"] = canonical_digest(value)
    return value


class OwnerState:
    def __init__(self) -> None:
        self.owner = {
            "mode": "managed",
            "lane": LANE,
            "generation": GENERATION,
            "daemon_id": DAEMON_ID,
        }

    def read_owner(self, *, deadline: float | None = None) -> dict[str, Any]:
        del deadline
        return copy.deepcopy(self.owner)


class AuthorizationController:
    """Synchronous controller seam with durable first-grant semantics."""

    def __init__(self, *, binding: Mapping[str, Any] | None = None) -> None:
        self.binding = copy.deepcopy(dict(binding or _binding()))
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.authorization_id = "authorization-1"
        self.granted = False
        self.first_validation_id: str | None = None

    def authorize_native_swap_release(
        self, validation_id: str, binding: Mapping[str, Any]
    ) -> dict[str, Any]:
        self.calls.append((validation_id, copy.deepcopy(dict(binding))))
        if dict(binding) != self.binding:
            raise RuntimeError("controller binding mismatch")
        if not self.granted:
            self.first_validation_id = validation_id
            self.granted = True
            return _ack(
                validation_id,
                authorized=True,
                authorization_id=self.authorization_id,
                binding=binding,
            )
        if validation_id != self.first_validation_id:
            raise RuntimeError("changed validation ID cannot reauthorize")
        return _ack(
            validation_id,
            authorized=False,
            authorization_id=self.authorization_id,
            binding=binding,
        )


def _daemon(
        state: OwnerState | None = None,
        controller: Any = None,
        *,
        daemon_id: str = DAEMON_ID,
        adapter: Any = None,
) -> tuple[ManagedDaemon, OwnerState]:
    state = OwnerState() if state is None else state
    daemon = ManagedDaemon(
        state=state,
        controller=controller,
        adapter=adapter,
        daemon_id=daemon_id,
        opt_in=True,
        lane=LANE,
    )
    daemon.owner_record = state.read_owner()
    daemon.started = True
    return daemon, state


def test_construct_dependencies_binds_only_the_private_native_release_callback():
    class Adapter:
        def __init__(self) -> None:
            self.callback: Any = None

        def bind_native_swap_release(self, callback: Any) -> None:
            self.callback = callback

    adapter = Adapter()
    daemon, _state = _daemon(
        controller=AuthorizationController(),
        adapter=adapter,
    )
    daemon.profiles = object()
    daemon._construct_dependencies()
    assert adapter.callback is not None
    assert adapter.callback.__self__ is daemon
    assert adapter.callback.__name__ == "_authorize_native_swap_release_callback"


def _invoke_with_validation_id(
        daemon: ManagedDaemon, validation_id: str,
        binding: Mapping[str, Any] | None = None,
):
    return asyncio.run(
        daemon._authorize_native_swap_release_callback(
            PARTICIPANT_ID,
            SESSION_ID,
            RUNNER_ID,
            validation_id,
            copy.deepcopy(dict(binding or _binding())),
        )
    )


def _invoke(daemon: ManagedDaemon, binding: Mapping[str, Any] | None = None):
    return _invoke_with_validation_id(daemon, VALIDATION_ID, binding)


def test_private_callback_returns_exact_first_grant_and_exact_repeat_observation():
    controller = AuthorizationController()
    daemon, _state = _daemon(controller=controller)

    first = _invoke(daemon)
    assert set(first) == {
        "validation_id", "authorized", "authorization_id", "binding",
        "authorization_digest",
    }
    assert first == _ack(binding=_binding())
    assert controller.calls == [(VALIDATION_ID, _binding())]

    repeated = _invoke(daemon)
    assert repeated == _ack(
        authorized=False,
        authorization_id="authorization-1",
        binding=_binding(),
    )
    assert len(controller.calls) == 2
    assert controller.calls[0] == controller.calls[1]


@pytest.mark.parametrize(
    "field,value",
    [
        ("participant_id", "another-participant"),
        ("session_id", "another-session"),
        ("runner_instance_id", "another-runner"),
    ],
)
def test_private_callback_rejects_tampered_authenticated_identity_before_controller(
        field: str, value: str,
):
    controller = AuthorizationController()
    daemon, _state = _daemon(controller=controller)
    args = {
        "participant_id": PARTICIPANT_ID,
        "session_id": SESSION_ID,
        "runner_instance_id": RUNNER_ID,
        "validation_id": VALIDATION_ID,
        "binding": _binding(),
    }
    args[field] = value

    async def scenario():
        with pytest.raises(DaemonError) as raised:
            await daemon._authorize_native_swap_release_callback(**args)
        assert raised.value.code in {"ownership-conflict", "stale-generation"}

    asyncio.run(scenario())
    assert controller.calls == []


def test_private_callback_forwards_runner_validation_id_and_refuses_changed_id():
    controller = AuthorizationController()
    daemon, _state = _daemon(controller=controller)
    runner_validation_id = "runner-chosen-validation"

    first = asyncio.run(
        daemon._authorize_native_swap_release_callback(
            PARTICIPANT_ID,
            SESSION_ID,
            RUNNER_ID,
            runner_validation_id,
            _binding(),
        )
    )
    assert first["authorized"] is True
    assert first["validation_id"] == runner_validation_id

    repeated = asyncio.run(
        daemon._authorize_native_swap_release_callback(
            PARTICIPANT_ID,
            SESSION_ID,
            RUNNER_ID,
            runner_validation_id,
            _binding(),
        )
    )
    assert repeated["authorized"] is False
    assert repeated["authorization_id"] == first["authorization_id"]

    with pytest.raises(DaemonError) as raised:
        _invoke_with_validation_id(
            daemon, "changed-validation", _binding()
        )
    assert raised.value.code == "uncertain-effect"
    assert controller.granted is True
    assert controller.first_validation_id == runner_validation_id
    assert len(controller.calls) == 3


@pytest.mark.parametrize(
    "changes,expected_code",
    [
        ({"owner_generation": GENERATION + 1}, "stale-generation"),
        ({"expected_daemon_id": "replacement-daemon"}, "ownership-conflict"),
        ({"binding_digest": "d" * 64}, "stale-generation"),
        ({"extra": "refused"}, "invalid"),
    ],
)
def test_private_callback_rejects_tampered_or_stale_binding_before_controller(
        changes: Mapping[str, Any], expected_code: str,
):
    controller = AuthorizationController()
    daemon, _state = _daemon(controller=controller)
    binding = _binding(**dict(changes))
    if "binding_digest" in changes:
        binding["binding_digest"] = changes["binding_digest"]

    # ``extra`` is intentionally not part of the digest input; the strict
    # contract must reject it rather than canonicalizing it away.
    async def scenario():
        with pytest.raises(DaemonError) as raised:
            await daemon._authorize_native_swap_release_callback(
                PARTICIPANT_ID,
                SESSION_ID,
                RUNNER_ID,
                VALIDATION_ID,
                binding,
            )
        assert raised.value.code == expected_code

    asyncio.run(scenario())
    assert controller.calls == []


def test_private_callback_requires_exact_controller_method_without_legacy_fallback():
    class LegacyOnly:
        def native_swap_release_authorization(self, *args: Any) -> Any:
            raise AssertionError("legacy controller method must not be probed")

    daemon, _state = _daemon(controller=LegacyOnly())

    with pytest.raises(DaemonError) as raised:
        _invoke(daemon)
    assert raised.value.code == "unsupported"


def test_private_callback_refuses_missing_controller():
    daemon, _state = _daemon(controller=None)

    with pytest.raises(DaemonError) as raised:
        _invoke(daemon)
    assert raised.value.code == "unsupported"


def test_private_callback_requires_complete_binding_shape():
    controller = AuthorizationController()
    daemon, _state = _daemon(controller=controller)
    binding = _binding()
    binding.pop("release_id")

    with pytest.raises(DaemonError) as raised:
        _invoke(daemon, binding)
    assert raised.value.code == "invalid"
    assert controller.calls == []


def test_private_callback_rechecks_owner_after_controller_await():
    state = OwnerState()
    started = asyncio.Event()
    continue_call = asyncio.Event()

    class AwaitingController(AuthorizationController):
        async def authorize_native_swap_release(
                self, validation_id: str, binding: Mapping[str, Any]
        ) -> dict[str, Any]:
            self.calls.append((validation_id, copy.deepcopy(dict(binding))))
            started.set()
            await continue_call.wait()
            return _ack(binding=binding)

    controller = AwaitingController()
    daemon, _state = _daemon(state, controller)

    async def scenario():
        task = asyncio.create_task(
            daemon._authorize_native_swap_release_callback(
                PARTICIPANT_ID,
                SESSION_ID,
                RUNNER_ID,
                VALIDATION_ID,
                _binding(),
            )
        )
        await asyncio.wait_for(started.wait(), 1)
        state.owner["daemon_id"] = "replacement-daemon"
        continue_call.set()
        with pytest.raises(DaemonError) as raised:
            await task
        assert raised.value.code == "ownership-conflict"

    asyncio.run(scenario())
    assert len(controller.calls) == 1


def test_private_callback_rechecks_generation_after_controller_await():
    state = OwnerState()
    started = asyncio.Event()
    continue_call = asyncio.Event()

    class AwaitingController(AuthorizationController):
        async def authorize_native_swap_release(
                self, validation_id: str, binding: Mapping[str, Any]
        ) -> dict[str, Any]:
            self.calls.append((validation_id, copy.deepcopy(dict(binding))))
            started.set()
            await continue_call.wait()
            return _ack(binding=binding)

    controller = AwaitingController()
    daemon, _state = _daemon(state, controller)

    async def scenario():
        task = asyncio.create_task(
            daemon._authorize_native_swap_release_callback(
                PARTICIPANT_ID,
                SESSION_ID,
                RUNNER_ID,
                VALIDATION_ID,
                _binding(),
            )
        )
        await asyncio.wait_for(started.wait(), 1)
        state.owner["generation"] = GENERATION + 1
        continue_call.set()
        with pytest.raises(DaemonError) as raised:
            await task
        assert raised.value.code == "stale-generation"

    asyncio.run(scenario())
    assert len(controller.calls) == 1


def test_private_callback_refuses_owner_generation_change_before_controller():
    state = OwnerState()
    state.owner["generation"] = GENERATION + 1
    controller = AuthorizationController()
    daemon, _state = _daemon(state, controller)

    with pytest.raises(DaemonError) as raised:
        _invoke(daemon)
    assert raised.value.code == "stale-generation"
    assert controller.calls == []


def test_private_callback_rejects_controller_ack_shape_or_digest():
    class MalformedController(AuthorizationController):
        def authorize_native_swap_release(
                self, validation_id: str, binding: Mapping[str, Any]
        ) -> dict[str, Any]:
            del validation_id
            result = _ack(binding=binding)
            result.pop("authorization_digest")
            result["unexpected"] = True
            return result

    daemon, _state = _daemon(controller=MalformedController())
    with pytest.raises(DaemonError) as raised:
        _invoke(daemon)
    assert raised.value.code == "invalid"


def test_private_callback_does_not_accept_public_release_capability_arguments():
    controller = AuthorizationController()
    daemon, _state = _daemon(controller=controller)

    async def scenario():
        with pytest.raises(TypeError):
            await daemon._authorize_native_swap_release_callback(
                PARTICIPANT_ID,
                SESSION_ID,
                RUNNER_ID,
                VALIDATION_ID,
                _binding(),
                capability=True,
            )

    asyncio.run(scenario())
    assert controller.calls == []
