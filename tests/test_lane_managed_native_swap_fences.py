# SPDX-License-Identifier: Apache-2.0
"""Public native-swap owner fences at every awaited lifecycle boundary.

The harness in ``test_lane_managed_native_swap_integration`` is deliberately
reused here instead of replacing the controller with a test double.  The
takeover fault uses the real state store recovery transaction, which changes
the durable daemon incarnation while retaining the generation and lineage
claims.  Each runtime/provider seam then crosses one real boundary before the
controller's post-await authority check observes that replacement.
"""

from __future__ import annotations

import copy
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import pytest

from test_lane_managed_native_swap_integration import (
    NativeSwapEvidenceProvider,
    NativeSwapRuntime,
    _harness,
    _start_and_release,
)


_FENCE_BOUNDARIES = ("evidence", "interrupt", "status", "shutdown", "open")
_REFUSAL_CODES = frozenset({
    "ownership-conflict",
    "stale-generation",
    "uncertain-effect",
})


class _DurableTakeover:
    """Replace the active durable owner through the real recovery API once."""

    def __init__(self, boundary: str) -> None:
        self.boundary = boundary
        self.fixture: Any = None
        self.fired = False
        self.failure: Optional[Exception] = None
        self.claims_before: Optional[list[dict[str, Any]]] = None
        self.owner_before: Optional[dict[str, Any]] = None
        self.owner_after: Optional[dict[str, Any]] = None

    def arm(self, fixture: Any) -> None:
        self.fixture = fixture

    def replace_owner(self) -> None:
        try:
            self._replace_owner()
        except Exception as exc:
            # Preserve the fault before the public boundary sanitizes it.
            self.failure = exc
            raise

    def _replace_owner(self) -> None:
        if self.fired:
            return
        if self.fixture is None:
            raise AssertionError("durable takeover was not armed")
        fixture = self.fixture
        state = fixture.state
        owner = state.read_owner()
        runtime = state.read_runtime()
        claims = state.read_lineage_claims()
        if owner.get("daemon_id") != fixture.daemon.daemon_id:
            raise AssertionError("fixture owner was not the enrolled daemon")
        if not isinstance(runtime, Mapping):
            raise AssertionError("fixture runtime identity is unavailable")
        process_domain = runtime.get("process_domain")
        if not isinstance(process_domain, str) or not process_domain:
            raise AssertionError("fixture runtime process domain is unavailable")

        # This is the same complete exclusion shape used by the state-store
        # recovery contract.  The fixture fault models an external supervisor
        # takeover; it does not edit owner.json or claim records and does not
        # grant the replacement any controller/runtime authority.
        exclusion = {
            "pid": runtime["pid"],
            "start_token": runtime["start_token"],
            "pgid": runtime["pgid"],
            "process_group_owned": True,
            "exited": True,
            "group_excluded": True,
            "process_domain": process_domain,
        }
        replacement_socket = fixture.socket_path.with_name(
            "native-swap-replacement.sock"
        )
        state.recover_managed_owner(
            old_daemon_id=owner["daemon_id"],
            old_generation=owner["generation"],
            old_pid=runtime["pid"],
            old_start_token=runtime["start_token"],
            old_pgid=runtime["pgid"],
            new_daemon_id="daemon-native-swap-replacement",
            new_pid=int(runtime["pid"]) + 100000,
            new_start_token="native-swap-replacement-" + uuid.uuid4().hex,
            new_pgid=int(runtime["pgid"]) + 100000,
            process_domain=process_domain,
            old_process_domain=process_domain,
            new_process_domain=process_domain,
            socket_path=replacement_socket,
            exclusion_proof=exclusion,
            request_id="native-swap-takeover-" + self.boundary,
        )
        replacement = state.read_owner()
        if replacement.get("daemon_id") != "daemon-native-swap-replacement":
            raise AssertionError("state recovery did not publish replacement owner")
        if replacement.get("generation") != owner.get("generation"):
            raise AssertionError("owner replacement changed generation unexpectedly")
        if state.read_lineage_claims() != claims:
            raise AssertionError("owner replacement changed lineage claims")
        self.owner_before = copy.deepcopy(owner)
        self.owner_after = copy.deepcopy(replacement)
        self.claims_before = copy.deepcopy(claims)
        self.fired = True


class _TakeoverRuntime(NativeSwapRuntime):
    """Inject one durable owner replacement after a real runtime await."""

    def __init__(self, boundary: str) -> None:
        super().__init__()
        self.boundary = boundary
        self.takeover: Optional[Callable[[], None]] = None

    def _takeover_after(self, boundary: str) -> None:
        if self.boundary == boundary and self.takeover is not None:
            self.takeover()

    async def coordinator_interrupt(
            self, participant_id: str, selection: Mapping[str, Any]
    ) -> dict[str, Any]:
        result = await super().coordinator_interrupt(participant_id, selection)
        self._takeover_after("interrupt")
        return result

    async def status(self, participant_id: str) -> dict[str, Any]:
        result = await super().status(participant_id)
        # The first status is the pre-interrupt liveness check.  Only the
        # second, post-interrupt status crosses the requested boundary.
        if self._interrupt_seen:
            self._takeover_after("status")
        return result

    async def shutdown(self, participant_id: str) -> dict[str, Any]:
        result = await super().shutdown(participant_id)
        self._takeover_after("shutdown")
        return result

    async def open(
            self, participant_id: str, spec: Mapping[str, Any]
    ) -> dict[str, Any]:
        result = await super().open(participant_id, spec)
        # The initial source open is A setup.  The target open is the second
        # adapter crossing and is the only one eligible for this fault.
        if len(self.open_calls) > 1:
            self._takeover_after("open")
        return result


class _TakeoverEvidenceProvider(NativeSwapEvidenceProvider):
    """Inject takeover after the synchronous entry evidence return."""

    def __init__(self) -> None:
        super().__init__()
        self.takeover: Optional[Callable[[], None]] = None

    def __call__(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        response = super().__call__(binding)
        if binding.get("stage") == "entry" and self.takeover is not None:
            # This provider boundary is synchronous by contract; the fault is
            # intentionally not described as an awaited provider takeover.
            self.takeover()
        return response


def _lifecycle_counts(runtime: NativeSwapRuntime) -> dict[str, int]:
    return {
        "interrupt": len(runtime.coordinator_interrupt_calls),
        "shutdown": len(runtime.shutdown_calls),
        "open": len(runtime.open_calls),
        "release": len(runtime.release_calls),
        "send": len(runtime.send_calls),
    }


def _assert_fenced_refusal(response: Mapping[str, Any]) -> None:
    assert response.get("ok") is False
    assert response.get("code") in _REFUSAL_CODES


@pytest.mark.parametrize("boundary", _FENCE_BOUNDARIES)
def test_native_swap_owner_replacement_fences_each_awaited_boundary(
        tmp_path: Path, boundary: str,
) -> None:
    """A takeover after one boundary cannot authorize the next lifecycle step."""

    takeover = _DurableTakeover(boundary)
    runtime = _TakeoverRuntime(boundary)
    provider: NativeSwapEvidenceProvider
    if boundary == "evidence":
        provider = _TakeoverEvidenceProvider()
    else:
        provider = NativeSwapEvidenceProvider()

    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        # Recovery needs the real daemon endpoint, which this harness does
        # not publish as part of its start/serve setup.
        registered = fixture.daemon.register_runtime(fixture.socket_path)
        owner = fixture.state.read_owner()
        published = fixture.state.read_runtime()
        assert isinstance(published, Mapping)
        assert published == registered
        assert owner["mode"] == "managed"
        assert owner["daemon_id"] == fixture.daemon.daemon_id
        for key in ("daemon_id", "generation", "process_domain", "lane_key", "host"):
            assert published[key] == owner[key]
        assert tuple(published[key] for key in (
            "daemon_id", "generation", "pid", "start_token", "pgid", "process_domain",
        )) == fixture.daemon.discovery_identity
        assert published["socket_path"] == str(fixture.socket_path.resolve())
        takeover.arm(fixture)
        runtime.takeover = takeover.replace_owner
        if isinstance(provider, _TakeoverEvidenceProvider):
            provider.takeover = takeover.replace_owner
        _start_and_release(fixture)

        counts_before = _lifecycle_counts(runtime)
        claims_before = fixture.state.read_lineage_claims()

        first = fixture.request(
            "native-swap-owner-fence-" + boundary,
            "swap",
            {"profile": "team-b"},
        )
        _assert_fenced_refusal(first)
        assert takeover.fired is True, (
            f"takeover at {boundary!r} did not fire; "
            f"helper exception={takeover.failure!r}; response={first!r}"
        )
        assert takeover.owner_before is not None
        assert takeover.owner_after is not None
        assert takeover.owner_after["generation"] == takeover.owner_before["generation"]
        assert takeover.owner_after["daemon_id"] != takeover.owner_before["daemon_id"]

        counts_after_first = _lifecycle_counts(runtime)
        expected_deltas = {
            "evidence": {"interrupt": 0, "shutdown": 0, "open": 0, "release": 0, "send": 0},
            "interrupt": {"interrupt": 1, "shutdown": 0, "open": 0, "release": 0, "send": 0},
            "status": {"interrupt": 1, "shutdown": 0, "open": 0, "release": 0, "send": 0},
            "shutdown": {"interrupt": 1, "shutdown": 1, "open": 0, "release": 0, "send": 0},
            "open": {"interrupt": 1, "shutdown": 1, "open": 1, "release": 0, "send": 0},
        }
        expected = expected_deltas[boundary]
        assert {
            key: counts_after_first[key] - counts_before[key]
            for key in counts_before
        } == expected
        assert fixture.state.read_lineage_claims() == claims_before
        assert takeover.claims_before == claims_before
        durable_after_first = fixture.state.read_json("controller.json")
        provider_requests_after_first = len(provider.requests)

        # Exact request retry is a durable refusal, not a new provider call or
        # lifecycle attempt.  The replacement owner remains authoritative for
        # the state store even though the old daemon socket is still serving.
        retry = fixture.request(
            "native-swap-owner-fence-" + boundary,
            "swap",
            {"profile": "team-b"},
        )
        _assert_fenced_refusal(retry)
        assert _lifecycle_counts(runtime) == counts_after_first
        assert len(provider.requests) == provider_requests_after_first
        assert fixture.state.read_lineage_claims() == claims_before
        assert fixture.state.read_json("controller.json") == durable_after_first
