# SPDX-License-Identifier: Apache-2.0
"""Public native ``ctx`` lifecycle integration tests.

The fixture in this module deliberately uses the real durable state store,
controller, daemon, and public Unix-socket request path from the native-swap
integration tests.  ``NativeCtxRuntime`` only observes claim/open ordering and
injects an open-boundary failure; it does not add a public child API or write
controller state on behalf of the production code.

These tests are intentionally not opt-in.  A native ctx implementation must
exercise the complete offline route when the ordinary test suite runs.
"""

from __future__ import annotations

import copy
import asyncio
import inspect
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import pytest

from test_lane_managed_native_swap_integration import (
    NativeSwapHarness,
    NativeSwapEvidenceProvider,
    NativeSwapRuntime,
    _start_and_release,
    _digest,
)
from test_lane_managed_coordinator_interrupt import _roster


CTX_CHECKPOINT_HOLD = "checkpoint://ctx/native-hold"
CTX_CHECKPOINT_RESTART = "checkpoint://ctx/native-restart"
# Adoption evidence resolves the selected profile's capability identity
# through ``NativeCtxHarness``.  It must not carry a static fixture pin: the
# marker case deliberately makes team-b the source of the later ctx request.
NATIVE_CTX_PUBLICATION_FIELDS = frozenset({
    "schema_version", "architecture", "record_kind", "operation_id",
    "owner_generation", "expected_daemon_id", "archive_id", "archive_digest",
    "adoption_id", "adoption_intent_digest",
    "adoption_controller_commit_digest", "target_participant_id",
    "target_session_uuid", "target_lineage_id", "target_lineage_generation",
    "target_runner_incarnation", "target_spec_digest",
    "target_open_evidence_digest", "target_claim_digest", "publication_digest",
})
NATIVE_CHILD_STATUS_FIELDS = frozenset({
    "child_run_id", "source_identity", "admission_id", "tool_use_id",
    "agent_id", "task_id", "lineage_incarnation",
    "trusted_definition_digest", "observation_id", "observation_watermark",
    "lifecycle_status", "terminal_outcome", "restoration",
})
NATIVE_ADOPTION_BINDING_FIELDS = frozenset({
    "adoption_id", "archive_id", "archive_digest", "operation_id",
    "owner_generation", "expected_daemon_id", "source_identity",
    "source_claim_digest", "target_claim_digest",
})


class NativeCtxAdoptionEvidenceProvider:
    """Private held-adoption evidence seam, independent of swap evidence."""

    def __init__(self, *, identity_resolver: Any = None) -> None:
        self.identity_resolver = identity_resolver
        self.calls: list[dict[str, Any]] = []

    def __call__(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        assert isinstance(binding, Mapping)
        assert set(binding) == NATIVE_ADOPTION_BINDING_FIELDS
        resolver = self.identity_resolver
        if not callable(resolver):
            raise AssertionError("ctx adoption identity resolver is unavailable")
        runtime_identity_digest = resolver()
        assert isinstance(runtime_identity_digest, str)
        assert len(runtime_identity_digest) == 64
        assert all(
            character in "0123456789abcdef"
            for character in runtime_identity_digest
        )
        self.calls.append(copy.deepcopy(dict(binding)))
        return {
            **copy.deepcopy(dict(binding)),
            "runtime_identity_digest": runtime_identity_digest,
            "evidence_reference": "fixture://native-ctx/adoption-evidence-1",
            "source_writers_excluded": True,
            "source_effects_resolved": True,
            "native_worker_state_cleared": True,
            "control_epoch_request_free": True,
            "target_startup_hold_supported": True,
        }


class NativeCtxHarness(NativeSwapHarness):
    """Native-swap harness with the private adoption provider installed."""

    def __init__(
            self, tmp_path: Path, *, provider: Any, runtime: NativeCtxRuntime,
            adoption_provider: NativeCtxAdoptionEvidenceProvider,
    ) -> None:
        super().__init__(tmp_path, provider=provider, runtime=runtime)
        self.adoption_provider = adoption_provider
        # Reuse the exact capability evidence authority installed into the
        # managed controller.  The resolver cross-checks its selected profile
        # against the latest durable preflight gate, so a swapped team-b
        # source cannot accidentally receive team-a adoption evidence.
        self.adoption_provider.identity_resolver = self._selected_profile_pin
        # Rebuild the controller before the daemon starts so ctx receives the
        # constructor-only adoption evidence seam.  The inherited harness
        # constructor has not acquired ownership or started a server yet.
        self.controller = type(self.controller)(
            self.state,
            runtime=runtime,
            payload_resolver=lambda payload_ref: str(payload_ref),
            transcript_verifier=self._transcript_verifier,
            _capability_evidence_provider=self._capability,
            _native_swap_evidence_provider=provider,
            _native_adoption_evidence_provider=adoption_provider,
            _native_stop_daemon_id="daemon-native-swap",
            _coordinator_interrupt_daemon_id="daemon-native-swap",
            clock=lambda: 1000.0,
        )
        runtime.controller = self.controller
        self.daemon.controller = self.controller

    def _selected_profile_pin(self) -> str:
        """Resolve the current coordinator's preflight-bound capability pin."""
        record = self.state.read_json("controller.json")
        coordinator_id = record.get("coordinator_id")
        assert isinstance(coordinator_id, str) and coordinator_id
        coordinator = _participant(record, coordinator_id)
        metadata = coordinator.get("metadata")
        assert isinstance(metadata, Mapping)
        spec = metadata.get("runner_spec")
        assert isinstance(spec, Mapping)

        # This is the same injected capability provider used by the
        # controller's Gate 0 preflight.  It derives the identity from the
        # durable selected profile/spec instead of accepting a provider-owned
        # identity or guessing from the ctx request.
        selected = self._capability(spec, coordinator_id)
        assert selected.get("verdict") == "verified"
        assert selected.get("profile_name") == spec.get("profile_name")
        assert selected.get("participant_id") == coordinator_id
        assert selected.get("spec_digest") == _digest(spec)
        selected_pin = selected.get("identity_digest")
        assert isinstance(selected_pin, str)
        assert len(selected_pin) == 64
        assert all(character in "0123456789abcdef" for character in selected_pin)

        # Native swap persists the preflight decision on its operation.  Use
        # that durable binding when present and fail closed if it disagrees
        # with the currently selected profile.  Initial startup also has a
        # verified gate; the fallback keeps this fixture useful for a future
        # source path that supplies only the selected profile while retaining
        # the same controller capability authority.
        operations = record.get("operations", [])
        assert isinstance(operations, list)
        for operation in reversed(operations):
            if not isinstance(operation, Mapping):
                continue
            operation_metadata = operation.get("metadata")
            if not isinstance(operation_metadata, Mapping):
                continue
            gates = operation_metadata.get("capability_gates")
            if not isinstance(gates, Mapping) or coordinator_id not in gates:
                continue
            gate = gates.get(coordinator_id)
            assert isinstance(gate, Mapping)
            assert gate.get("verdict") == "verified"
            gate_pin = gate.get("identity_digest")
            assert gate_pin == selected_pin
            return gate_pin
        return selected_pin


class NativeCtxRuntime(NativeSwapRuntime):
    """Native fixture that records the claim set at a fresh ctx open.

    The source runtime's first open is ordinary native startup.  A later open
    without the dedicated ``native_swap_target`` marker is the fresh ctx
    coordinator.  The marker-aware distinction also lets the marker test use
    a real swap target as the source without treating that swap open as ctx.
    """

    def __init__(self, *, crash_target_open: str | None = None) -> None:
        super().__init__()
        if crash_target_open not in {None, "before-open", "after-open"}:
            raise AssertionError("unknown ctx open crash boundary")
        self.crash_target_open = crash_target_open
        self.ctx_open_observations: list[dict[str, Any]] = []
        self._native_child_observation_callback: Any = None
        self.native_child_observation: dict[str, Any] | None = None
        self.native_child_observation_ack: dict[str, Any] | None = None

    def bind_native_child_observation(self, callback: Any) -> None:
        self._native_child_observation_callback = callback

    async def emit_joined_child_observation(self) -> dict[str, Any]:
        """Send one observation produced from the real admission/runner seam."""
        if self.native_child_observation is not None:
            assert self.native_child_observation_ack is not None
            return copy.deepcopy(self.native_child_observation_ack)
        if self.controller is None or self._admission is None:
            raise AssertionError("real native admission is unavailable")
        if not callable(self._native_child_observation_callback):
            raise AssertionError("native child observation callback is unavailable")
        context = self.controller.status().get("native_context")
        assert isinstance(context, Mapping)
        lineage = context.get("lineage")
        assert isinstance(lineage, Mapping)
        claims = self.controller.store.read_lineage_claims()
        source_claims = [
            claim for claim in claims
            if isinstance(claim, Mapping)
            and claim.get("lineage_id") == lineage.get("lineage_id")
            and claim.get("state") == "active"
        ]
        assert len(source_claims) == 1
        context_binding = copy.deepcopy(dict(context))
        context_binding.pop("fenced", None)
        child = copy.deepcopy(_roster(self._admission)["children"][0])
        observation = {
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "record_kind": "native-child-observation",
            "observation_id": "observation-native-ctx-1",
            "source_identity": {
                "owner_generation": lineage["owner_generation"],
                "lineage_id": lineage["lineage_id"],
                "lineage_generation": lineage["lineage_generation"],
                "session_uuid": lineage["session_uuid"],
                "runner_incarnation": context["runner_incarnation"],
                "invocation_id": context["invocation_id"],
            },
            "context_binding_digest": _digest(context_binding),
            "claim_digest": _digest(source_claims[0]),
            "observation_watermark": max(
                int(self._admission["watermark"]) + 2, 8
            ),
            "terminal_outcome": None,
            "child": child,
        }
        frame = {
            "type": "native-child-observation",
            "participant_id": "coordinator",
            "session_id": lineage["session_uuid"],
            "runner_instance_id": context["runner_incarnation"],
            "observation": observation,
        }
        acknowledgement = self._native_child_observation_callback(frame)
        if inspect.isawaitable(acknowledgement):
            acknowledgement = await acknowledgement
        assert isinstance(acknowledgement, Mapping)
        self.native_child_observation = copy.deepcopy(observation)
        self.native_child_observation_ack = copy.deepcopy(dict(acknowledgement))
        return copy.deepcopy(dict(acknowledgement))

    @staticmethod
    def _native_config(spec: Mapping[str, Any]) -> Mapping[str, Any]:
        fingerprint = spec.get("fingerprint")
        if not isinstance(fingerprint, Mapping):
            return {}
        native_config = fingerprint.get("native_config")
        return native_config if isinstance(native_config, Mapping) else {}

    def _is_ctx_open(self, spec: Mapping[str, Any]) -> bool:
        # ``open_calls`` is populated by the base runtime.  The first open is
        # startup; later marked opens are native swap; later unmarked opens
        # are the fresh ctx target.
        return bool(self.open_calls) and not bool(
            self._native_config(spec).get("native_swap_target")
        )

    async def open(
            self, participant_id: str, spec: Mapping[str, Any]
    ) -> dict[str, Any]:
        is_ctx_open = self._is_ctx_open(spec)
        if is_ctx_open:
            claims = (
                self.controller.store.read_lineage_claims()
                if self.controller is not None
                else []
            )
            self.ctx_open_observations.append({
                "participant_id": participant_id,
                "spec": copy.deepcopy(dict(spec)),
                "claims": copy.deepcopy(claims),
            })
            if self.crash_target_open == "before-open":
                raise RuntimeError("injected ctx target-open crash before effect")

        opened = await super().open(participant_id, spec)
        if is_ctx_open and self.crash_target_open == "after-open":
            raise RuntimeError("injected ctx target-open crash after effect")
        return opened


@contextmanager
def _ctx_harness(
        tmp_path: Path, *, provider: NativeSwapEvidenceProvider,
        runtime: NativeCtxRuntime,
) -> Iterator[NativeCtxHarness]:
    adoption_provider = NativeCtxAdoptionEvidenceProvider()
    fixture = NativeCtxHarness(
        tmp_path,
        provider=provider,
        runtime=runtime,
        adoption_provider=adoption_provider,
    )
    fixture.start()
    try:
        yield fixture
    finally:
        fixture.close()
    assert fixture.thread is None or not fixture.thread.is_alive()
    assert fixture.errors == []


def _participant(record: Mapping[str, Any], participant_id: str) -> Mapping[str, Any]:
    for collection_name in ("participants", "archived_participants"):
        collection = record.get(collection_name, [])
        if not isinstance(collection, list):
            continue
        for value in collection:
            if isinstance(value, Mapping) and value.get("participant_id") == participant_id:
                return value
    raise AssertionError("participant %r is absent" % participant_id)


def _operation(record: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
    operations = record.get("operations", [])
    assert isinstance(operations, list)
    for value in operations:
        if isinstance(value, Mapping) and value.get("operation_id") == operation_id:
            return value
    raise AssertionError("operation %r is absent" % operation_id)


def _target_spec(record: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
    operation = _operation(record, operation_id)
    metadata = operation.get("metadata")
    assert isinstance(metadata, Mapping)
    target_specs = metadata.get("target_specs")
    ctx_intent = metadata.get("ctx_intent")
    assert isinstance(target_specs, Mapping)
    assert isinstance(ctx_intent, Mapping)
    target_id = ctx_intent.get("new_coordinator_id")
    assert isinstance(target_id, str)
    target = target_specs.get(target_id)
    assert isinstance(target, Mapping)
    return target


def _lineage_from_spec(spec: Mapping[str, Any]) -> Mapping[str, Any]:
    fingerprint = spec.get("fingerprint")
    assert isinstance(fingerprint, Mapping)
    lineage_context = fingerprint.get("lineage_context")
    assert isinstance(lineage_context, Mapping)
    assert isinstance(lineage_context.get("lineage_id"), str)
    assert type(lineage_context.get("lineage_generation")) is int
    return lineage_context


def _ctx_request(fixture: Any, request_id: str, policy: str, checkpoint: str):
    response = fixture.request(
        request_id,
        "ctx",
        {"checkpoint": checkpoint, "worker_policy": policy},
    )
    assert response["ok"] is True, json.dumps(response, sort_keys=True)
    assert response["result"]["phase"] == "ready-held"
    return response


def _reload_ctx_fixture_controller(fixture: NativeCtxHarness) -> NativeCtxRuntime:
    """Reload the ctx controller/runtime while preserving process identities."""
    previous = fixture.runtime
    runtime = NativeCtxRuntime(crash_target_open=None)
    for name in (
        "open_calls", "coordinator_interrupt_calls", "shutdown_calls",
        "release_calls", "send_calls", "gate_receipts",
        "native_swap_authorization_acks", "_opened", "_shutdown_runners",
        "_released_runners", "_release_validation_ids", "_admission",
        "_interrupt_frames", "opened", "ctx_open_observations",
        "native_child_observation", "native_child_observation_ack",
    ):
        setattr(runtime, name, copy.deepcopy(getattr(previous, name)))
    runtime._open_count = previous._open_count
    runtime._interrupt_seen = previous._interrupt_seen
    runtime._preflight_injected = previous._preflight_injected
    runtime._preflight_crashed = previous._preflight_crashed
    runtime.request_observation_cursor = previous.request_observation_cursor
    runtime._busy_until_interrupt = previous._busy_until_interrupt
    runtime._typed_observation_watermark = previous._typed_observation_watermark
    runtime._process_excluded_recorded = previous._process_excluded_recorded
    runtime.source_process_identity_digest = previous.source_process_identity_digest
    runtime.evidence_provider = fixture.provider
    if fixture.provider is not None:
        fixture.provider.runtime = runtime
    reloaded = type(fixture.controller)(
        fixture.state,
        runtime=runtime,
        payload_resolver=lambda payload_ref: str(payload_ref),
        transcript_verifier=fixture._transcript_verifier,
        _capability_evidence_provider=fixture._capability,
        _native_swap_evidence_provider=fixture.provider,
        _native_adoption_evidence_provider=fixture.adoption_provider,
        _native_stop_daemon_id="daemon-native-swap",
        _coordinator_interrupt_daemon_id="daemon-native-swap",
        clock=lambda: 1000.0,
    )
    fixture.runtime = runtime
    fixture.controller = reloaded
    fixture.daemon.controller = reloaded
    fixture.daemon.adapter = runtime
    runtime.controller = reloaded
    fixture.daemon._construct_dependencies()
    return runtime


def _assert_ctx_identity_and_claim_order(
        before: Mapping[str, Any], after: Mapping[str, Any],
        operation_id: str, runtime: NativeCtxRuntime,
        state: Any,
) -> None:
    source_context = before.get("native_context")
    assert isinstance(source_context, Mapping)
    source_lineage = source_context.get("lineage")
    assert isinstance(source_lineage, Mapping)
    source_coordinator = _participant(before, str(before["coordinator_id"]))
    target_coordinator = _participant(after, str(after["coordinator_id"]))
    assert target_coordinator["session_id"] != source_coordinator["session_id"]
    assert target_coordinator["metadata"]["profile_name"] == (
        source_coordinator["metadata"]["profile_name"]
    )
    assert target_coordinator["metadata"]["account_email"] == (
        source_coordinator["metadata"]["account_email"]
    )

    target_spec = _target_spec(after, operation_id)
    target_lineage = _lineage_from_spec(target_spec)
    assert target_lineage["lineage_id"] != source_lineage["lineage_id"]
    assert target_lineage["lineage_generation"] == (
        source_lineage["lineage_generation"] + 1
    )
    assert target_lineage["owner_generation"] == (
        source_lineage["owner_generation"]
    )
    native_config = target_spec["fingerprint"]["native_config"]
    assert isinstance(native_config, Mapping)
    assert "native_swap_target" not in native_config

    assert runtime.ctx_open_observations
    observation = runtime.ctx_open_observations[-1]
    claims = observation["claims"]
    active = [claim for claim in claims if claim.get("state") == "active"]
    target_claims = [
        claim for claim in active
        if claim.get("lineage_id") == target_lineage["lineage_id"]
    ]
    source_claims = [
        claim for claim in active
        if claim.get("lineage_id") == source_lineage["lineage_id"]
    ]
    assert len(target_claims) == 1
    assert not source_claims
    target_claim = target_claims[0]
    assert target_claim["lineage_generation"] == target_lineage["lineage_generation"]
    assert target_claim["owner_generation"] == source_lineage["owner_generation"]
    assert target_claim["coordinator_session_uuid"] == target_coordinator["session_id"]

    operation = _operation(after, operation_id)
    metadata = operation.get("metadata")
    assert isinstance(metadata, Mapping)
    publication = metadata.get("native_ctx_publication")
    assert isinstance(publication, Mapping)
    assert set(publication) == NATIVE_CTX_PUBLICATION_FIELDS
    assert publication["schema_version"] == 2
    assert publication["architecture"] == "native-coordinator-lineage"
    assert publication["record_kind"] == "native-ctx-publication"
    assert publication["operation_id"] == operation_id
    assert publication["owner_generation"] == source_lineage["owner_generation"]
    assert publication["expected_daemon_id"] == "daemon-native-swap"
    assert publication["target_participant_id"] == target_coordinator["participant_id"]
    assert publication["target_session_uuid"] == target_coordinator["session_id"]
    assert publication["target_lineage_id"] == target_lineage["lineage_id"]
    assert publication["target_lineage_generation"] == target_lineage["lineage_generation"]
    assert publication["target_runner_incarnation"] == target_lineage["runner_incarnation"]
    assert publication["target_spec_digest"] == _digest(target_spec)

    open_evidence = metadata.get("open_evidence")
    assert isinstance(open_evidence, Mapping)
    target_open = open_evidence.get(target_coordinator["participant_id"])
    assert isinstance(target_open, Mapping)
    assert publication["target_open_evidence_digest"] == _digest(target_open)

    claims = state.read_lineage_claims()
    target_claims = [
        claim for claim in claims
        if isinstance(claim, Mapping)
        and claim.get("lineage_id") == target_lineage["lineage_id"]
        and claim.get("coordinator_session_uuid") == target_coordinator["session_id"]
    ]
    assert len(target_claims) == 1
    assert publication["target_claim_digest"] == _digest(target_claims[0])

    adoption = metadata.get("native_adoption")
    assert isinstance(adoption, Mapping)
    assert publication["adoption_id"] == adoption["adoption_id"]
    assert publication["adoption_intent_digest"] == adoption["intent_digest"]
    assert publication["archive_id"] == adoption["archive_id"]
    assert publication["archive_digest"] == adoption["archive_digest"]
    assert publication["target_claim_digest"] == adoption["target_claim_digest"]
    adoption_record = state.read_lineage_adoption(publication["adoption_id"])
    assert isinstance(adoption_record, Mapping)
    assert (
        publication["adoption_controller_commit_digest"]
        == adoption_record["controller_commit_digest"]
    )

    archives = after.get("native_source_archives")
    assert isinstance(archives, Mapping)
    archive = archives.get(publication["archive_id"])
    assert isinstance(archive, Mapping)
    snapshot = archive.get("snapshot")
    assert isinstance(snapshot, Mapping)
    assert publication["archive_digest"] == archive["snapshot_digest"]
    assert publication["archive_digest"] == _digest(snapshot)
    old_context = snapshot.get("native_context")
    assert isinstance(old_context, Mapping)
    assert old_context["fenced"] is True

    observation = runtime.native_child_observation
    assert isinstance(observation, Mapping)
    source_observation_id = observation["observation_id"]
    archived_observations = snapshot.get("native_child_observations")
    assert isinstance(archived_observations, Mapping)
    retained = archived_observations.get(source_observation_id)
    assert isinstance(retained, Mapping)
    assert retained["observation"] == observation
    assert retained["observation_digest"] == _digest(observation)
    retained_source = retained["observation"]["source_identity"]
    assert retained_source == observation["source_identity"]
    retained_child = retained["observation"]["child"]
    assert retained_child["parent_agent_id"] == observation["child"]["parent_agent_id"]
    assert retained_child["invocation_id"] == observation["child"]["invocation_id"]

    publication_without_digest = {
        key: value for key, value in publication.items()
        if key != "publication_digest"
    }
    assert publication["publication_digest"] == _digest(publication_without_digest)


def test_native_ctx_hold_cas_precedes_open_and_retains_joined_child_record(
        tmp_path: Path,
) -> None:
    provider = NativeSwapEvidenceProvider()
    runtime = NativeCtxRuntime()
    with _ctx_harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        asyncio.run(runtime.emit_joined_child_observation())
        before = fixture.state.read_json("controller.json")
        sends_before = len(runtime.send_calls)

        held = _ctx_request(
            fixture, "native-ctx-hold", "hold", CTX_CHECKPOINT_HOLD
        )
        operation_id = held["result"]["operation_id"]
        after = fixture.state.read_json("controller.json")
        assert after["native_context"] is None

        _assert_ctx_identity_and_claim_order(
            before, after, operation_id, runtime, fixture.state
        )
        assert len(runtime.send_calls) == sends_before


def test_native_ctx_restart_gates_checkpoint_and_accepted_send_is_not_restart(
        tmp_path: Path,
) -> None:
    provider = NativeSwapEvidenceProvider()
    runtime = NativeCtxRuntime()
    with _ctx_harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        asyncio.run(runtime.emit_joined_child_observation())
        sends_before = len(runtime.send_calls)
        held = _ctx_request(
            fixture, "native-ctx-restart", "restart", CTX_CHECKPOINT_RESTART
        )
        operation_id = held["result"]["operation_id"]
        held_record = fixture.state.read_json("controller.json")
        checkpoint_entries = [
            item for item in held_record.get("mailboxes", [])
            if isinstance(item, Mapping)
            and item.get("operation_id") == operation_id
            and item.get("payload_ref") == CTX_CHECKPOINT_RESTART
        ]
        assert len(checkpoint_entries) == 1
        assert checkpoint_entries[0]["state"] in {"fenced", "queued"}
        assert len(runtime.send_calls) == sends_before

        released = fixture.request(
            "native-ctx-restart-release",
            "release",
            {"operation_id": operation_id},
        )
        assert released["ok"] is True, json.dumps(released, sort_keys=True)
        assert released["result"]["phase"] == "released"
        assert len(runtime.send_calls) > sends_before
        target_id = fixture.state.read_json("controller.json")["coordinator_id"]
        assert all(
            call["participant_id"] == target_id
            for call in runtime.send_calls[sends_before:]
        )

        final_record = fixture.state.read_json("controller.json")
        status_response = fixture.request("native-ctx-restart-status", "status")
        assert status_response["ok"] is True, json.dumps(
            status_response, sort_keys=True
        )
        status = status_response["result"]
        native_children = status.get("native_children")
        assert isinstance(native_children, list) and native_children
        assert native_children == sorted(
            native_children, key=lambda value: value["child_run_id"]
        )
        for child in native_children:
            assert set(child) == NATIVE_CHILD_STATUS_FIELDS
            assert child["source_identity"]["lineage_id"]
            assert child["observation_id"]
            restoration = child["restoration"]
            assert isinstance(restoration, Mapping)
            assert set(restoration) == {
                "operation_id", "policy", "disposition", "restart_attempt_id",
                "instruction_mailbox_id", "new_child_run_id", "evidence_refs",
            }
            assert restoration["operation_id"] == operation_id
            assert restoration["policy"] == "restart"
            assert restoration["disposition"] in {
                "restart-pending", "unresolved"
            }
            assert restoration["disposition"] != "restarted"
        assert _operation(final_record, operation_id)["phase"] == "released"


def test_native_ctx_fresh_spec_strips_inherited_native_swap_target(
        tmp_path: Path,
) -> None:
    provider = NativeSwapEvidenceProvider()
    runtime = NativeCtxRuntime()
    with _ctx_harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        swapped = fixture.request(
            "native-ctx-marker-source", "swap", {"profile": "team-b"}
        )
        assert swapped["ok"] is True, json.dumps(swapped, sort_keys=True)
        swap_operation_id = swapped["result"]["operation_id"]
        released = fixture.request(
            "native-ctx-marker-source-release",
            "release",
            {"operation_id": swap_operation_id},
        )
        assert released["ok"] is True, json.dumps(released, sort_keys=True)
        assert released["result"]["phase"] == "released"

        # A swap release is not a source-context binding.  Submit and allow
        # the released target to pump one real mailbox before requesting ctx.
        submitted = fixture.request(
            "native-ctx-marker-bound-submit",
            "submit",
            {
                "recipient_id": "coordinator",
                "payload_ref": "opaque://native-ctx-marker-bound",
                "sender_id": "user",
                "task_id": "task-native-ctx-marker-bound",
            },
        )
        assert submitted["ok"] is True, json.dumps(submitted, sort_keys=True)
        assert runtime.send_calls[-1]["participant_id"] == "coordinator"

        source = fixture.state.read_json("controller.json")
        source_coordinator = _participant(source, str(source["coordinator_id"]))
        source_spec = source_coordinator["metadata"]["runner_spec"]
        assert source_spec["fingerprint"]["native_config"]["native_swap_target"] is True
        held = _ctx_request(
            fixture, "native-ctx-strip-marker", "hold", CTX_CHECKPOINT_HOLD
        )
        target = fixture.state.read_json("controller.json")
        target_spec = _target_spec(target, held["result"]["operation_id"])
        target_config = target_spec["fingerprint"]["native_config"]
        assert "native_swap_target" not in target_config


@pytest.mark.parametrize("crash_boundary", ["before-open", "after-open"])
def test_native_ctx_claim_or_open_crash_never_reopens_target(
        tmp_path: Path, crash_boundary: str,
) -> None:
    provider = NativeSwapEvidenceProvider()
    runtime = NativeCtxRuntime(crash_target_open=crash_boundary)
    with _ctx_harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        first = fixture.request(
            "native-ctx-crash", "ctx",
            {"checkpoint": CTX_CHECKPOINT_HOLD, "worker_policy": "hold"},
        )
        assert first["ok"] is False
        record = fixture.state.read_json("controller.json")
        operation_id = record["active_operation_id"]
        assert isinstance(operation_id, str)
        assert len(runtime.ctx_open_observations) == 1
        claims_at_open = copy.deepcopy(
            runtime.ctx_open_observations[0]["claims"]
        )
        target_open_count = len(
            [
                call for call in runtime.open_calls
                if call["participant_id"] == runtime.ctx_open_observations[0]["participant_id"]
            ]
        )

        _reload_ctx_fixture_controller(fixture)
        recovered = fixture.request(
            "native-ctx-crash-recover", "recover", {"operation_id": operation_id}
        )
        if crash_boundary == "before-open":
            assert recovered["ok"] is False
            assert recovered["code"] in {
                "uncertain-effect", "unknown", "loader-failed",
            }
        else:
            assert recovered["ok"] is True, json.dumps(
                recovered, sort_keys=True
            )
            assert recovered["result"]["phase"] == "ready-held"
        retried = fixture.request(
            "native-ctx-crash", "ctx",
            {"checkpoint": CTX_CHECKPOINT_HOLD, "worker_policy": "hold"},
        )
        if crash_boundary == "before-open":
            assert retried["ok"] is False
            assert retried["code"] in {
                "uncertain-effect", "unknown", "loader-failed",
            }
        else:
            assert retried["ok"] is True, json.dumps(retried, sort_keys=True)
            assert retried["result"]["operation_id"] == operation_id
            assert retried["result"]["phase"] == "ready-held"
        assert len(fixture.runtime.ctx_open_observations) == 1
        assert len(
            [
                call for call in fixture.runtime.open_calls
                if call["participant_id"] == fixture.runtime.ctx_open_observations[0]["participant_id"]
            ]
        ) == target_open_count
        assert fixture.state.read_lineage_claims() == claims_at_open
