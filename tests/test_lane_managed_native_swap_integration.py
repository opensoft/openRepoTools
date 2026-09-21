# SPDX-License-Identifier: Apache-2.0
"""Public native-swap acceptance fixtures.

These tests deliberately use the real temporary managed state store, the real
controller, the real daemon, and its public Unix-socket client.  The runner
and the two evidence authorities are constructor-injected offline fixtures;
they do not claim that an installed Claude runtime is capable of native swap.

The private native-swap evidence provider is intentionally strict.  It echoes
the exact schema-v2 request binding, keeps one request epoch and one ordered
stage stream, and returns a negative final observation when the release gate
receipt cannot be covered by a continuous same-epoch proof.  There is no
legacy provider, context-only binder, public capability flag, or public proof
field in this fixture.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
import subprocess
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

import pytest

from lane_managed_controller import ManagedController
from lane_managed_daemon import ManagedDaemon, serve_daemon
from lane_managed_state import ManagedStateStore, resolve_workspace
from lane_managed_swap import (
    validate_release_authorization,
    validate_release_binding,
    validate_release_boundary,
)
from test_lane_managed_coordinator_interrupt import (
    _evidence,
    _intent,
    _roster,
)
from test_lane_managed_controller_rollover import RolloverRuntime
from test_lane_managed_daemon import (
    VerifyingProfiles,
    _load_cli_api,
    _native_start_body,
    _start_request,
    _stop_server_thread,
    _wait_for_socket,
)


LANE = "build"
EVIDENCE_STAGES = (
    "entry",
    "graph-drained",
    "source-excluded",
    "target-held",
    "pre-release",
    "release-boundary",
)
SOURCE_CAPABILITY_PIN = "a" * 64
TARGET_CAPABILITY_PIN = "b" * 64
MIN_TYPED_TERMINAL_WATERMARK = 12
_NATIVE_EVIDENCE_REQUEST_KEYS = frozenset({
    "schema_version",
    "architecture",
    "record_kind",
    "stage",
    "operation_id",
    "owner_generation",
    "expected_daemon_id",
    "source_identity",
    "source_context_digest",
    "source_claim_digest",
    "target_spec_digest",
    "request_epoch_id",
    "interrupt_id",
    "interrupt_intent_digest",
    "source_archive_digest",
    "target_runner_incarnation",
    "release_id",
    "release_intent_digest",
    "release_boundary",
})
_NATIVE_SOURCE_IDENTITY_KEYS = frozenset({
    "owner_generation",
    "lineage_id",
    "lineage_generation",
    "session_uuid",
    "runner_incarnation",
    "invocation_id",
})
_NATIVE_EVIDENCE_RESPONSE_KEYS = frozenset({
    "binding",
    "runtime_identity_digest",
    "evidence_reference",
    "request_observation",
    "worker_state_clear",
})
_NATIVE_REQUEST_OBSERVATION_KEYS = frozenset({
    "epoch_id",
    "entry_evidence_ref",
    "through_evidence_ref",
    "observable",
    "continuous",
    "new_requests",
})
_NATIVE_WORKER_CLEAR_KEYS = frozenset({
    "source_identity_digest",
    "interrupt_id",
    "method",
    "evidence_reference",
    "observation_watermark",
    "cleared",
})
_ALLOWED_WORKER_DISPOSITIONS = frozenset({
    "completed",
    "resume-pending",
    "restart-pending",
    "exact-resumed",
    "restarted",
    "unresolved",
})


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class NativeSwapEvidenceProvider:
    """Offline, read-only implementation of the frozen provider seam.

    ``continuous=False`` at the final stage is a deliberate negative fact: a
    runtime gate receipt exists, but this provider cannot prove the complete
    request epoch through that gate.  The controller must retain that record
    before refusing release.
    """

    def __init__(
            self, *, incomplete_release_boundary: bool = False,
            runtime_identity_digest: str = TARGET_CAPABILITY_PIN,
    ) -> None:
        self.incomplete_release_boundary = incomplete_release_boundary
        self.runtime_identity_digest = runtime_identity_digest
        self.requests: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []
        self.by_stage: dict[str, dict[str, Any]] = {}
        self._epoch_id: str | None = None
        self._entry_evidence_ref: str | None = None
        self._source_identity: Any = None
        self._operation_id: str | None = None
        self._owner_generation: int | None = None
        self._source_cursor_watermark: int | None = None
        self.runtime: Any = None
        self.entry_request_count: int | None = None
        self.entry_capture: dict[str, Any] | None = None

    def record_source_cursor(self, watermark: int) -> None:
        """Publish the cursor captured after typed source terminal facts."""
        assert type(watermark) is int and watermark >= MIN_TYPED_TERMINAL_WATERMARK
        if self._source_cursor_watermark is not None:
            assert watermark >= self._source_cursor_watermark
        self._source_cursor_watermark = watermark

    def __call__(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        assert isinstance(binding, Mapping)
        assert set(binding) == _NATIVE_EVIDENCE_REQUEST_KEYS
        request = copy.deepcopy(dict(binding))
        stage = request["stage"]
        assert stage in EVIDENCE_STAGES
        expected_index = len(self.requests)
        assert stage == EVIDENCE_STAGES[expected_index]
        assert stage not in self.by_stage
        assert request["schema_version"] == 2
        assert request["architecture"] == "native-coordinator-lineage"
        assert request["record_kind"] == "native-swap-evidence-request"
        assert isinstance(request["operation_id"], str) and request["operation_id"]
        assert type(request["owner_generation"]) is int
        assert request["owner_generation"] > 0
        assert isinstance(request["expected_daemon_id"], str)
        assert request["expected_daemon_id"]
        assert isinstance(request["source_identity"], Mapping)
        assert set(request["source_identity"]) == _NATIVE_SOURCE_IDENTITY_KEYS
        assert request["source_identity"]["owner_generation"] == request[
            "owner_generation"
        ]
        for identity_key in (
            "lineage_id",
            "session_uuid",
            "runner_incarnation",
            "invocation_id",
        ):
            assert isinstance(request["source_identity"][identity_key], str)
            assert request["source_identity"][identity_key]
        assert type(request["source_identity"]["lineage_generation"]) is int
        assert request["source_identity"]["lineage_generation"] > 0
        for digest_key in (
            "source_context_digest",
            "source_claim_digest",
            "target_spec_digest",
        ):
            assert isinstance(request[digest_key], str)
            assert len(request[digest_key]) == 64
            int(request[digest_key], 16)
        assert isinstance(request["request_epoch_id"], str)
        assert request["request_epoch_id"]

        if self._epoch_id is None:
            self._epoch_id = request["request_epoch_id"]
            self._entry_evidence_ref = (
                "fixture://native-swap/epoch/" + self._epoch_id
            )
            self._source_identity = copy.deepcopy(request["source_identity"])
            self._operation_id = request["operation_id"]
            self._owner_generation = request["owner_generation"]
        else:
            assert request["request_epoch_id"] == self._epoch_id
            assert request["source_identity"] == self._source_identity
            assert request["operation_id"] == self._operation_id
            assert request["owner_generation"] == self._owner_generation

        if stage == "entry":
            assert self.runtime is not None
            self.entry_request_count = self.runtime.request_observation_cursor
            self.entry_capture = {
                "request_epoch_id": request["request_epoch_id"],
                "entry_evidence_ref": self._entry_evidence_ref,
                "request_count": self.entry_request_count,
            }
            assert request["interrupt_id"] is None
            assert request["interrupt_intent_digest"] is None
            assert request["source_archive_digest"] is None
            assert request["release_id"] is None
            assert request["release_intent_digest"] is None
            assert request["release_boundary"] is None
        else:
            assert isinstance(request["interrupt_id"], str)
            assert request["interrupt_id"]

        if stage == "release-boundary":
            boundary = request["release_boundary"]
            assert isinstance(boundary, Mapping)
            assert set(boundary) == {
                "binding", "gate_event_id", "gate_watermark",
            }
            assert isinstance(boundary["binding"], Mapping)
            assert isinstance(boundary["gate_event_id"], str)
            assert boundary["gate_event_id"]
            assert type(boundary["gate_watermark"]) is int
            assert boundary["gate_watermark"] > 0

        self.requests.append(request)
        continuous = not (
            self.incomplete_release_boundary and stage == "release-boundary"
        )
        new_requests = (
            0
            if stage == "entry"
            else self.runtime.request_observation_cursor - self.entry_request_count
        )
        observation = {
            "epoch_id": request["request_epoch_id"],
            "entry_evidence_ref": self._entry_evidence_ref,
            "through_evidence_ref": (
                "fixture://native-swap/stage/" + stage
            ),
            "observable": True,
            # A request observed after entry is still covered by the same
            # epoch.  The count is an independent negative fact; it must not
            # be collapsed into a false continuity flag.
            "continuous": continuous,
            "new_requests": new_requests,
        }
        assert set(observation) == _NATIVE_REQUEST_OBSERVATION_KEYS
        if stage == "entry":
            worker_state_clear = None
        else:
            assert self._source_cursor_watermark is not None
            assert self._source_cursor_watermark >= MIN_TYPED_TERMINAL_WATERMARK
            worker_state_clear = {
                "source_identity_digest": _digest(request["source_identity"]),
                "interrupt_id": request["interrupt_id"],
                "method": "fixture-native-state-clear-observation",
                "evidence_reference": (
                    "fixture://native-swap/clear/" + stage
                ),
                "observation_watermark": self._source_cursor_watermark,
                "cleared": True,
            }
            assert set(worker_state_clear) == _NATIVE_WORKER_CLEAR_KEYS
        response = {
            "binding": copy.deepcopy(request),
            "runtime_identity_digest": self.runtime_identity_digest,
            "evidence_reference": "fixture://native-swap/response/" + stage,
            "request_observation": observation,
            "worker_state_clear": worker_state_clear,
        }
        assert set(response) == _NATIVE_EVIDENCE_RESPONSE_KEYS
        self.responses.append(copy.deepcopy(response))
        self.by_stage[stage] = copy.deepcopy(response)
        return copy.deepcopy(response)


class NativeSwapProfiles(VerifyingProfiles):
    """Profile authority for source and target transcript-family fixtures."""

    _PROFILES = {
        "team-a": {
            "name": "team-a",
            "email": "a@example.invalid",
            "family": "family-a",
            "status": "active",
            "authentication": {"type": "subscription_oauth"},
            "config_dir": "/managed/profiles/team-a",
            "transcript_store": "/managed/transcripts",
        },
        "team-b": {
            "name": "team-b",
            "email": "b@example.invalid",
            "family": "family-a",
            "status": "active",
            "authentication": {"type": "subscription_oauth"},
            "config_dir": "/managed/profiles/team-b",
            "transcript_store": "/managed/transcripts",
        },
    }

    def resolve(self, name: str) -> dict[str, Any]:
        if name not in self._PROFILES:
            raise AssertionError("unexpected profile lookup: %s" % name)
        return copy.deepcopy(self._PROFILES[name])


class NativeSwapRuntime(RolloverRuntime):
    """Trusted offline runner fixture with explicit lifecycle observations."""

    def __init__(
            self,
            *,
            unknown_effects: bool = False,
            crash_boundary: str | None = None,
            inject_request_during_preflight: bool = False,
            preflight_crash_once: bool = False,
            block_interrupt: bool = False,
    ) -> None:
        super().__init__()
        assert crash_boundary in {None, "interrupt", "shutdown", "open"}
        self.unknown_effects = unknown_effects
        self.crash_boundary = crash_boundary
        self.inject_request_during_preflight = inject_request_during_preflight
        self.preflight_crash_once = preflight_crash_once
        self.block_interrupt = block_interrupt
        self._preflight_injected = False
        self._preflight_crashed = False
        self.request_observation_cursor = 0
        self._busy_until_interrupt = False
        self.open_calls: list[dict[str, Any]] = []
        self.coordinator_interrupt_calls: list[dict[str, Any]] = []
        self.shutdown_calls: list[str] = []
        self.release_calls: list[dict[str, Any]] = []
        self.send_calls: list[dict[str, Any]] = []
        self.gate_receipts: list[dict[str, Any]] = []
        self._opened: dict[str, dict[str, Any]] = {}
        self._open_count = 0
        self._interrupt_seen = False
        self._typed_observation_watermark: int | None = None
        self._process_excluded_recorded = False
        self._shutdown_runners: set[tuple[str, str]] = set()
        self._released_runners: set[tuple[str, str]] = set()
        self._admission_callback: Any = None
        self._interrupt_intent_callback: Any = None
        self._interrupt_evidence_callback: Any = None
        self._native_swap_release_callback: Any = None
        self._release_validation_ids: dict[tuple[str, str], str] = {}
        self.native_swap_authorization_acks: list[dict[str, Any]] = []
        self._admission: dict[str, Any] | None = None
        self._interrupt_frames: list[dict[str, Any]] = []
        self.controller: Any = None
        self.evidence_provider: Any = None
        self.source_process_identity_digest: str | None = None

    def bind_native_admission(self, callback: Any) -> None:
        self._admission_callback = callback

    def bind_coordinator_interrupt(
            self, intent_callback: Any, evidence_callback: Any
    ) -> None:
        self._interrupt_intent_callback = intent_callback
        self._interrupt_evidence_callback = evidence_callback

    def bind_native_swap_release(self, callback: Any) -> None:
        self._native_swap_release_callback = callback

    def preflight_held_swap(
            self,
            spec: Mapping[str, Any], evidence_record: Any,
    ) -> dict[str, Any]:
        # This is the existing static exact-mode gate.  The independent
        # provider below does not replace it or grant a live capability.
        assert isinstance(spec, Mapping)
        assert isinstance(evidence_record, Mapping)
        profile_name = spec.get("profile_name")
        if profile_name == "team-a":
            expected_pin = SOURCE_CAPABILITY_PIN
        elif profile_name == "team-b":
            expected_pin = TARGET_CAPABILITY_PIN
        else:
            raise AssertionError("unrecognized capability profile")
        assert evidence_record.get("profile_name") == profile_name
        assert evidence_record.get("participant_id") == spec.get("participant_id")
        assert evidence_record.get("spec_digest") == _digest(spec)
        assert evidence_record.get("identity_digest") == expected_pin
        if profile_name == "team-b" and self.inject_request_during_preflight:
            if not self._preflight_injected:
                self.request_observation_cursor += 1
                self._preflight_injected = True
        if profile_name == "team-b" and self.preflight_crash_once:
            if not self._preflight_crashed:
                self._preflight_crashed = True
                raise RuntimeError("injected target preflight crash")
        return {
            "verdict": "verified",
            "reason_code": "synthetic-test-control",
            "reason": "injected offline runner fixture only",
            "identity_digest": expected_pin,
            "evidence_reference": (
                "fixture://native-swap/static-capability/" + profile_name
            ),
        }

    @staticmethod
    def _process(participant_id: str, count: int, *, excluded: bool) -> dict[str, Any]:
        return {
            "pid": 4100 + count,
            "process_group_id": "pg-native-swap-%s-%d" % (participant_id, count),
            "process_start_token": "start-native-swap-%s-%d" % (
                participant_id, count,
            ),
            "process_group_owned": True,
            "exited": excluded,
            "group_excluded": excluded,
            "pid_domain": "linux:test-machine:test-pid-namespace",
        }

    def _envelope(
            self, participant_id: str, spec: Mapping[str, Any],
            runner_instance_id: str, *, excluded: bool = False,
    ) -> dict[str, Any]:
        process = self._process(
            participant_id, self._open_count, excluded=excluded
        )
        uncertain = ["fixture-unknown-effect"] if self.unknown_effects else []
        busy = self._busy_until_interrupt and participant_id == "coordinator"
        evidence = {
            "participant_id": participant_id,
            "session_id": spec["session_id"],
            "runner_instance_id": runner_instance_id,
            "ready": True,
            "released": (
                participant_id, runner_instance_id
            ) in self._released_runners,
            "active_turn": busy,
            "turn_terminal": not busy,
            "drained": not busy and not bool(uncertain),
            "participant_quiescent": not busy and not bool(uncertain),
            "tools_quiescent": not busy and not bool(uncertain),
            "quiescent": not busy and not bool(uncertain),
            "tools": [],
            "uncertain_effects": uncertain,
            "uncertain_effects_overflow": False,
            "process": process,
            "initialization": {
                "account_email": spec["account_email"],
                "permission_mode": spec["permission_mode"],
                "model": spec["model"],
                "fingerprint": copy.deepcopy(spec["fingerprint"]),
            },
        }
        return {
            "participant_id": participant_id,
            "session_id": spec["session_id"],
            "runner_instance_id": runner_instance_id,
            "evidence": evidence,
        }

    async def _persist_real_admission(self) -> None:
        """Emit one real native admission through the bound daemon seam.

        The first accepted coordinator mailbox is the only source of native
        context authority.  This child admission is derived from that
        committed context and persisted by the production controller; it is
        not a hand-edited record or a replacement for the adapter callback.
        """

        if self._admission is not None:
            return
        if not callable(self._admission_callback):
            raise RuntimeError("native admission callback is unavailable")
        if self.controller is None:
            raise RuntimeError("native admission controller is unavailable")
        context = self.controller.status().get("native_context")
        if not isinstance(context, Mapping):
            raise RuntimeError("native context was not committed before admission")
        lineage = context.get("lineage")
        definitions = context.get("definitions")
        if not isinstance(lineage, Mapping) or not isinstance(definitions, Mapping):
            raise RuntimeError("native context definition authority is incomplete")
        agent_type, definition = next(iter(definitions.items()))
        if not isinstance(agent_type, str) or not isinstance(definition, Mapping):
            raise RuntimeError("native context definition authority is malformed")
        digest = definition.get("digest")
        if not isinstance(digest, str):
            raise RuntimeError("native context definition digest is missing")
        admission = {
            "admission_id": "admission-native-swap-1",
            "tool_use_id": "tool-native-swap-1",
            "agent_type": agent_type,
            "invocation_id": context["invocation_id"],
            "parent": {
                "session_id": lineage["session_uuid"],
                "invocation_id": context["invocation_id"],
            },
            "custom_definition": copy.deepcopy(dict(definition)),
            "definition_digest": digest,
            "trusted_definition_digest": digest,
            "watermark": int(context["invocation_watermark"]) + 1,
            "owner_generation": lineage["owner_generation"],
            "lineage_id": lineage["lineage_id"],
            "runner_incarnation": context["runner_incarnation"],
            "launch_completed": False,
        }
        acknowledgement = self._admission_callback(copy.deepcopy(admission))
        if inspect.isawaitable(acknowledgement):
            acknowledgement = await acknowledgement
        if not isinstance(acknowledgement, Mapping) or acknowledgement.get("accepted") is not True:
            raise RuntimeError("native admission was not durably accepted")
        self._admission = copy.deepcopy(admission)

    async def _persist_typed_interrupt(self, selection: Mapping[str, Any]) -> None:
        """Persist an exact intent plus independent typed evidence facts."""

        if not callable(self._interrupt_intent_callback) or not callable(
                self._interrupt_evidence_callback
        ):
            raise RuntimeError("typed coordinator interrupt callbacks are unavailable")
        if self.controller is None or self._admission is None:
            raise RuntimeError("native A admission is unavailable for interrupt")
        context = self.controller.status().get("native_context")
        if not isinstance(context, Mapping):
            raise RuntimeError("native context was not committed before interrupt")
        lineage = context.get("lineage")
        if not isinstance(lineage, Mapping):
            raise RuntimeError("native context lineage is unavailable")
        admission = copy.deepcopy(self._admission)
        seal = max(8, int(admission["watermark"]) + 4)
        # Reuse the canonical fixture roster shape and replace only the
        # identities that come from this real A admission below.
        roster = _roster(admission)
        # Reuse the canonical frame builder from the coordinator-interrupt
        # contract tests.  Only identities obtained from the committed A
        # context and controller selection replace its fixture defaults.
        frame = _intent(
            lineage,
            admission,
            selection["operation_id"],
            roster=roster,
            interrupt_id=selection["interrupt_id"],
            fence_epoch=selection["fence_epoch"],
            runner_instance_id=context["runner_incarnation"],
            roster_seal_watermark=seal,
            request_entry_watermark=5,
        )
        frame["interrupt"].update({
            "invocation_id": context["invocation_id"],
            "capability_digest": selection["capability_digest"],
            "request_epoch_id": selection["request_epoch_id"],
        })
        if selection["capability_digest"] != SOURCE_CAPABILITY_PIN:
            raise RuntimeError("interrupt did not use the source capability pin")
        intent_ack = self._interrupt_intent_callback(copy.deepcopy(frame))
        if inspect.isawaitable(intent_ack):
            intent_ack = await intent_ack
        if (
            not isinstance(intent_ack, Mapping)
            or intent_ack.get("recorded") is not True
            or intent_ack.get("authorize_send") is not True
        ):
            raise RuntimeError("typed interrupt intent was not durably authorized")

        child = roster["children"][0]
        observed = seal + 4
        entry_request_count = (
            self.evidence_provider.entry_request_count
            if self.evidence_provider is not None
            else 0
        )
        if entry_request_count is None:
            raise RuntimeError("native swap entry request cursor is unavailable")
        new_requests = self.request_observation_cursor - entry_request_count
        if new_requests < 0:
            raise RuntimeError("native swap source request cursor moved backwards")
        facts = {
            "runtime-ack": {
                "accepted": True,
                "ack_kind": "accepted-interrupt",
            },
            "member-terminal": {
                "agent_id": child["agent_id"],
                "task_id": child["task_id"],
                "lineage_incarnation": child["lineage_incarnation"],
                "tool_use_id": child["tool_use_id"],
                "event_kind": "task_notification",
                "event_uuid": "task-stop-native-swap",
                "status": "stopped",
            },
            "tool-terminal": {
                "tool_use_id": child["active_tool_ids"][0],
                "agent_id": child["agent_id"],
                "lineage_incarnation": child["lineage_incarnation"],
                "status": "cancelled",
            },
            "effect-outcome": {
                "effect_id": child["unresolved_effect_ids"][0],
                "status": "unknown" if self.unknown_effects else "resolved",
            },
            "admission-closed": {
                "admission_id": admission["admission_id"],
                "closed": True,
            },
            "parent-drained": {
                "invocation_id": context["invocation_id"],
                "state": "drained",
            },
            "request-observation": {
                "epoch_id": selection["request_epoch_id"],
                "entry_watermark": 5,
                "through_watermark": observed,
                "new_requests": new_requests,
                "observable": True,
            },
        }
        for kind, data in facts.items():
            evidence = _evidence(
                frame,
                kind,
                observed_watermark=observed,
                data=data,
            )
            evidence_ack = self._interrupt_evidence_callback(evidence)
            if inspect.isawaitable(evidence_ack):
                evidence_ack = await evidence_ack
            if not isinstance(evidence_ack, Mapping) or evidence_ack.get("recorded") is not True:
                raise RuntimeError("typed interrupt evidence was not durably recorded")
        self._typed_observation_watermark = observed
        if self.evidence_provider is not None:
            self.evidence_provider.record_source_cursor(observed)
        self._interrupt_frames.append(copy.deepcopy(frame))
        self._interrupt_seen = True

    async def _persist_typed_process_excluded(
            self, participant_id: str, current: Mapping[str, Any],
    ) -> None:
        """Record source exclusion only after the fixture proves shutdown."""

        if self._process_excluded_recorded:
            return
        if participant_id != "coordinator" or not self._interrupt_frames:
            raise RuntimeError("source exclusion has no bound interrupt frame")
        evidence = current.get("evidence")
        process = evidence.get("process") if isinstance(evidence, Mapping) else None
        if not isinstance(process, Mapping):
            raise RuntimeError("source exclusion process identity is unavailable")
        if process.get("exited") is not True or process.get("group_excluded") is not True:
            raise RuntimeError("source process exclusion was not observed")
        process_identity = {
            key: process[key]
            for key in (
                "pid", "process_group_id", "process_start_token",
                "process_group_owned", "pid_domain",
            )
            if key in process
        }
        if set(process_identity) != {
                "pid", "process_group_id", "process_start_token",
                "process_group_owned", "pid_domain",
        }:
            raise RuntimeError("source process identity is incomplete")
        process_identity_digest = _digest(process_identity)
        previous = self._typed_observation_watermark or 0
        observed = max(MIN_TYPED_TERMINAL_WATERMARK, previous) + 1
        evidence_frame = _evidence(
            self._interrupt_frames[-1],
            "process-excluded",
            observed_watermark=observed,
            data={
                "process_identity_digest": process_identity_digest,
                "status": "excluded",
            },
        )
        acknowledgement = self._interrupt_evidence_callback(evidence_frame)
        if inspect.isawaitable(acknowledgement):
            acknowledgement = await acknowledgement
        if not isinstance(acknowledgement, Mapping) or acknowledgement.get("recorded") is not True:
            raise RuntimeError("typed process exclusion evidence was not durably recorded")
        self._typed_observation_watermark = observed
        self._process_excluded_recorded = True
        self.source_process_identity_digest = process_identity_digest
        if self.evidence_provider is not None:
            self.evidence_provider.record_source_cursor(observed)

    async def open(
            self, participant_id: str, spec: Mapping[str, Any]
    ) -> dict[str, Any]:
        self._open_count += 1
        fingerprint = spec.get("fingerprint")
        native_config = (
            fingerprint.get("native_config")
            if isinstance(fingerprint, Mapping)
            else None
        )
        lineage_context = (
            fingerprint.get("lineage_context")
            if isinstance(fingerprint, Mapping)
            else None
        )
        reserved_runner = None
        for candidate in (lineage_context, native_config):
            if isinstance(candidate, Mapping) and isinstance(
                    candidate.get("runner_incarnation"), str
            ):
                reserved_runner = candidate["runner_incarnation"]
                break
        if not reserved_runner:
            raise RuntimeError("native runner specification has no reserved incarnation")
        runner_instance_id = reserved_runner
        call = {
            "participant_id": participant_id,
            "spec": copy.deepcopy(dict(spec)),
            "runner_instance_id": runner_instance_id,
        }
        self.open_calls.append(call)
        result = self._envelope(participant_id, spec, runner_instance_id)
        self._opened[participant_id] = copy.deepcopy(result)
        self.opened.append((participant_id, copy.deepcopy(dict(spec))))
        if self.crash_boundary == "open" and len(self.open_calls) > 1:
            raise RuntimeError("injected target-open crash after effect")
        return copy.deepcopy(result)

    async def coordinator_interrupt(
            self, participant_id: str, selection: Mapping[str, Any]
    ) -> dict[str, Any]:
        captured = {
            "participant_id": participant_id,
            "selection": copy.deepcopy(dict(selection)),
        }
        self.coordinator_interrupt_calls.append(captured)
        if self.crash_boundary == "interrupt":
            raise RuntimeError("injected coordinator interrupt crash")
        if self.block_interrupt:
            # Deliberately leave the adapter call pending.  The public
            # operation deadline must cancel this exact in-flight call and
            # the durable selection must prevent a retry from replaying it.
            await asyncio.Event().wait()
        await self._persist_typed_interrupt(selection)
        self._busy_until_interrupt = False
        return {
            "accepted": True,
            "interrupt_id": selection["interrupt_id"],
            "operation_id": selection["operation_id"],
            "request_epoch_id": selection["request_epoch_id"],
            "fence_epoch": selection["fence_epoch"],
            "receipt": {
                "kind": "fixture-coordinator-interrupt-receipt",
                "interrupt_id": selection["interrupt_id"],
                "observation_watermark": 11,
            },
        }

    async def status(self, participant_id: str) -> dict[str, Any]:
        current = copy.deepcopy(self._opened[participant_id])
        evidence = current["evidence"]
        if self.unknown_effects:
            evidence.update({
                "drained": False,
                "participant_quiescent": False,
                "tools_quiescent": False,
                "quiescent": False,
                "uncertain_effects": ["fixture-unknown-effect"],
            })
        if self._busy_until_interrupt and participant_id == "coordinator":
            evidence.update({
                "active_turn": True,
                "turn_terminal": False,
                "drained": False,
                "participant_quiescent": False,
                "tools_quiescent": False,
                "quiescent": False,
            })
        runner_instance_id = current["runner_instance_id"]
        if (participant_id, runner_instance_id) in self._shutdown_runners:
            evidence["process"]["exited"] = True
            evidence["process"]["group_excluded"] = True
            await self._persist_typed_process_excluded(participant_id, current)
        if self._interrupt_seen and not self.unknown_effects:
            evidence.update({
                "drained": True,
                "participant_quiescent": True,
                "tools_quiescent": True,
                "quiescent": True,
            })
        return current

    async def shutdown(self, participant_id: str) -> dict[str, Any]:
        self.shutdown_calls.append(participant_id)
        current = copy.deepcopy(self._opened[participant_id])
        self._shutdown_runners.add((participant_id, current["runner_instance_id"]))
        current["evidence"]["process"]["exited"] = True
        current["evidence"]["process"]["group_excluded"] = True
        self._opened[participant_id] = copy.deepcopy(current)
        await self._persist_typed_process_excluded(participant_id, current)
        if self.crash_boundary == "shutdown":
            raise RuntimeError("injected shutdown crash after effect")
        return current

    async def release(
            self, participant_id: str, *, native_swap_binding: Any = None
    ) -> dict[str, Any]:
        call = {
            "participant_id": participant_id,
            "native_swap_binding": copy.deepcopy(native_swap_binding),
        }
        current = copy.deepcopy(self._opened[participant_id])
        if native_swap_binding is not None:
            binding = validate_release_binding(native_swap_binding)
            if not callable(self._native_swap_release_callback):
                raise RuntimeError("native swap release authorization callback is unavailable")
            release_key = (participant_id, current["runner_instance_id"])
            validation_id = self._release_validation_ids.setdefault(
                release_key,
                "native-swap-" + uuid.uuid4().hex,
            )
            acknowledgement = self._native_swap_release_callback(
                participant_id,
                current["session_id"],
                current["runner_instance_id"],
                validation_id,
                copy.deepcopy(binding),
            )
            if inspect.isawaitable(acknowledgement):
                acknowledgement = await acknowledgement
            acknowledgement = validate_release_authorization(
                acknowledgement,
                expected_validation_id=validation_id,
                expected_binding=binding,
            )
            self.native_swap_authorization_acks.append(copy.deepcopy(acknowledgement))
            if acknowledgement["authorized"] is not True:
                raise RuntimeError("native swap release authorization was not granted")
        self.release_calls.append(call)
        current["evidence"]["released"] = True
        self._released_runners.add((participant_id, current["runner_instance_id"]))
        if native_swap_binding is not None:
            receipt = {
                "binding": copy.deepcopy(binding),
                "gate_event_id": "fixture-native-swap-gate-1",
                "gate_watermark": 20,
            }
            receipt = validate_release_boundary(
                receipt,
                expected_binding=binding,
            )
            current["native_swap_release_boundary"] = copy.deepcopy(receipt)
            current["evidence"]["native_swap_release_boundary"] = copy.deepcopy(
                receipt
            )
            self.gate_receipts.append(copy.deepcopy(receipt))
        self._opened[participant_id] = copy.deepcopy(current)
        return current

    async def send(
            self, participant_id: str, message_id: str, payload_ref: Any
    ) -> dict[str, Any]:
        self.send_calls.append({
            "participant_id": participant_id,
            "message_id": message_id,
            "payload_ref": payload_ref,
        })
        if not self.send_calls[:-1]:
            await self._persist_real_admission()
        return {
            "participant_id": participant_id,
            "message_id": message_id,
            "accepted": True,
            "ack_kind": "accepted-send",
        }


class NativeSwapHarness:
    def __init__(
            self, tmp_path: Path, *, provider: Any, runtime: NativeSwapRuntime,
            operation_timeout: float = 10.0,
    ):
        workspace = tmp_path / "workspace"
        workspace.mkdir(mode=0o700)
        subprocess.run(
            ["git", "init", "-q"],
            cwd=str(workspace),
            check=True,
            capture_output=True,
            text=True,
        )
        agents_root = tmp_path / "agents"
        agents_root.mkdir(mode=0o700)
        home = tmp_path / "home"
        home.mkdir(mode=0o700)
        self.env = {
            "HOME": str(home),
            "AGENT_PROTOCOL_ROOT": str(agents_root),
            "LANES_WORKSTATION": "native-swap-test",
        }
        identity = resolve_workspace(
            LANE,
            env=self.env,
            helper=lambda *_args, **_kwargs: (str(workspace) + "\n", 0, ""),
        )
        self.state = ManagedStateStore(identity)
        self.state.ensure_layout()
        self.runtime = runtime
        self.provider = provider
        self.operation_timeout = operation_timeout
        profiles = NativeSwapProfiles()
        self.profiles = profiles
        self.controller = ManagedController(
            self.state,
            runtime=runtime,
            payload_resolver=lambda payload_ref: str(payload_ref),
            transcript_verifier=self._transcript_verifier,
            _capability_evidence_provider=self._capability,
            _native_swap_evidence_provider=provider,
            _native_stop_daemon_id="daemon-native-swap",
            _coordinator_interrupt_daemon_id="daemon-native-swap",
            clock=lambda: 1000.0,
        )
        # The fake runtime is a constructor-injected trusted adapter.  It
        # observes the real controller only to derive its typed runner frames;
        # it never writes controller state directly.
        runtime.controller = self.controller
        runtime.evidence_provider = provider
        if provider is not None:
            provider.runtime = runtime
        self.daemon = ManagedDaemon(
            state=self.state,
            profiles=profiles,
            controller=self.controller,
            adapter=runtime,
            daemon_id="daemon-native-swap",
            opt_in=True,
            lane=LANE,
            env=self.env,
        )
        self.socket_path = tmp_path / "managed-native-swap.sock"
        self.stop_event = threading.Event()
        self.errors: list[BaseException] = []
        self.thread: threading.Thread | None = None
        self.api: dict[str, Any] | None = None
        self.generation: int | None = None

    @staticmethod
    def _capability(spec: Mapping[str, Any], participant_id: str) -> dict[str, Any]:
        profile_name = spec.get("profile_name")
        if profile_name == "team-a":
            identity_digest = SOURCE_CAPABILITY_PIN
        elif profile_name == "team-b":
            identity_digest = TARGET_CAPABILITY_PIN
        else:
            raise AssertionError("unexpected capability profile: %r" % profile_name)
        return {
            "verdict": "verified",
            "reason_code": "synthetic-test-control",
            "reason": "injected offline runner fixture only",
            "identity_digest": identity_digest,
            "evidence_reference": (
                "fixture://native-swap/static-capability/" + str(profile_name)
            ),
            "profile_name": profile_name,
            "participant_id": participant_id,
            "spec_digest": _digest(spec),
        }

    def _transcript_verifier(
            self, profile_name: str, session_id: str, workspace: str
    ) -> dict[str, Any]:
        profile = self.profiles.resolve(profile_name)
        source = self.runtime._opened.get("coordinator")
        process = (
            copy.deepcopy(source["evidence"]["process"])
            if source is not None
            else {
                "pid": 4000,
                "process_group_id": "pg-native-swap-coordinator-0",
                "process_start_token": "start-native-swap-coordinator-0",
            }
        )
        holder = {
            "profile_name": "team-a",
            "session_id": session_id,
            "workspace": str(workspace),
            "projects_store": "/managed/transcripts",
            "config_dir": "/managed/profiles/team-a",
            "pid_domain": "linux:test-machine:test-pid-namespace",
            "process_group_member": True,
            "live": True,
            "process": process,
        }
        return {
            "profile": copy.deepcopy(profile),
            "session_id": session_id,
            "workspace": str(workspace),
            "transcript_store": "/managed/transcripts",
            "transcript_project": str(Path(workspace) / "transcripts"),
            # Initial native startup has not opened the runner yet, so the
            # profile authority proves an empty holder set.  Swap preflight
            # runs after that source runner exists and receives its exact
            # process-bound holder below.
            "holders": [] if source is None else [holder],
            "unknown_holders": [],
            "ambiguous": False,
            "transcript": {
                "session_id": session_id,
                "exists": True,
                "written": True,
                "reserved": False,
                "regular": True,
                "private": True,
            },
        }

    def start(self) -> None:
        asyncio.run(self.daemon.start())
        self.generation = int(self.daemon.owner_record["generation"])
        self.api = _load_cli_api()

        def serve() -> None:
            try:
                serve_daemon(
                    str(self.socket_path),
                    self.daemon,
                    operation_timeout=self.operation_timeout,
                    stop_event=self.stop_event,
                )
            except BaseException as error:
                self.errors.append(error)

        self.thread = threading.Thread(
            target=serve, name="managed-public-native-swap", daemon=True
        )
        self.thread.start()
        _wait_for_socket(self.socket_path, self.thread)

    def request(
            self, request_id: str, operation: str,
            body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        assert self.api is not None
        assert self.generation is not None
        if operation == "start":
            start_body = _native_start_body()
            workspace = self.state.identity.workspace
            start_body["coordinator"]["metadata"].update({
                "workspace": str(workspace),
                "transcript_project": str(Path(workspace) / "transcripts"),
            })
            spec = start_body["runner_specs"]["coordinator"]
            spec.update({
                "cwd": str(workspace),
                "transcript_project": str(Path(workspace) / "transcripts"),
            })
            spec["fingerprint"].update({"workspace": str(workspace)})
            spec["fingerprint"]["native_config"].update({
                "workspace": str(workspace),
                "repository": str(workspace),
            })
            wire = _start_request(request_id, start_body)
        else:
            wire = {
                "schema": 2,
                "schema_version": 2,
                "architecture": "native-coordinator-lineage",
                "request_id": request_id,
                "lane": LANE,
                "generation": self.generation,
                "operation": operation,
                "body": dict(body or {}),
            }
        wire["generation"] = self.generation
        return self.api["request_socket"](
            str(self.socket_path), wire,
            connect_timeout=0.5,
            operation_timeout=self.operation_timeout,
        )

    def close(self) -> None:
        if self.thread is not None:
            _stop_server_thread(self.socket_path, self.stop_event, self.thread)


@contextmanager
def _harness(
        tmp_path: Path, *, provider: Any,
        runtime: NativeSwapRuntime | None = None,
        operation_timeout: float = 10.0,
) -> Iterator[NativeSwapHarness]:
    fixture = NativeSwapHarness(
        tmp_path,
        provider=provider,
        runtime=runtime or NativeSwapRuntime(),
        operation_timeout=operation_timeout,
    )
    fixture.start()
    try:
        yield fixture
    finally:
        fixture.close()
    assert fixture.thread is None or not fixture.thread.is_alive()
    assert fixture.errors == []


def _reload_fixture_controller(fixture: NativeSwapHarness) -> NativeSwapRuntime:
    """Reload controller and adapter ownership from the same durable state."""
    previous = fixture.runtime
    runtime = NativeSwapRuntime(
        unknown_effects=previous.unknown_effects,
        crash_boundary=previous.crash_boundary,
        inject_request_during_preflight=previous.inject_request_during_preflight,
        preflight_crash_once=previous.preflight_crash_once,
    )
    for name in (
        "open_calls", "coordinator_interrupt_calls", "shutdown_calls",
        "release_calls", "send_calls", "gate_receipts",
        "native_swap_authorization_acks", "_opened", "_shutdown_runners",
        "_released_runners", "_release_validation_ids", "_admission",
        "_interrupt_frames", "opened",
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
    reloaded = ManagedController(
        fixture.state,
        runtime=runtime,
        payload_resolver=lambda payload_ref: str(payload_ref),
        transcript_verifier=fixture._transcript_verifier,
        _capability_evidence_provider=fixture._capability,
        _native_swap_evidence_provider=fixture.provider,
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


def _start_and_release(fixture: NativeSwapHarness) -> str:
    started = fixture.request("native-start", "start")
    assert started["ok"] is True, json.dumps(started, sort_keys=True)
    operation_id = started["result"]["operation_id"]
    first = fixture.request("native-first-submit", "submit", {
        "recipient_id": "coordinator",
        "payload_ref": "opaque://native-first",
        "sender_id": "user",
        "task_id": "task-root-coordinator",
    })
    assert first["ok"] is True
    assert first["result"]["state"] in {"fenced", "queued"}
    released = fixture.request(
        "native-release", "release", {"operation_id": operation_id}
    )
    assert released["ok"] is True, json.dumps(released, sort_keys=True)
    assert released["result"]["phase"] == "released"
    assert fixture.runtime.send_calls
    durable = fixture.state.read_json("controller.json")
    context = durable.get("native_context")
    assert isinstance(context, Mapping)
    # A is a genuine coordinator dispatch: its mailbox ID is the bound native
    # context invocation, and the typed child admission was persisted through
    # the daemon callback during that send.  A startup descriptor alone is not
    # accepted as a native-swap source.
    assert context["invocation_id"] == fixture.runtime.send_calls[0]["message_id"]
    assert context["fenced"] is False
    startup = durable["operations"][0]["metadata"]["native_startup"]
    assert startup["invocation_bound"] is True
    assert startup["invocation_id"] == context["invocation_id"]
    admissions = durable.get("native_admissions")
    assert isinstance(admissions, Mapping) and len(admissions) == 1
    return operation_id


def _operation_metadata(response: Mapping[str, Any]) -> Mapping[str, Any]:
    operation = response.get("result")
    assert isinstance(operation, Mapping)
    metadata = operation.get("metadata")
    assert isinstance(metadata, Mapping)
    return metadata


def _assert_durable_evidence(
        operation: Mapping[str, Any], provider: NativeSwapEvidenceProvider,
        expected_stages: tuple[str, ...],
) -> None:
    metadata = operation.get("metadata")
    assert isinstance(metadata, Mapping)
    native_swap = metadata.get("native_swap")
    assert isinstance(native_swap, Mapping)
    records = native_swap.get("native_swap_evidence")
    assert isinstance(records, Mapping)
    expected_set = set(expected_stages)
    assert set(records) == expected_set
    assert set(provider.by_stage) == expected_set
    # The durable JSON writer canonicalizes object keys, so mapping iteration
    # order is not the evidence chronology.  The provider's append-only list
    # and each binding's explicit stage carry the semantic order instead.
    assert [
        response["binding"]["stage"] for response in provider.responses
    ] == list(expected_stages)
    request_epochs = set()
    observation_watermarks = []
    for stage in expected_stages:
        record = records[stage]
        assert isinstance(record, Mapping)
        assert set(record) == {"observation", "evidence_digest"}
        assert record["observation"] == provider.by_stage[stage]
        assert record["evidence_digest"] == _digest(record["observation"])
        observation = record["observation"]
        assert observation["binding"]["stage"] == stage
        request_epoch = observation["binding"]["request_epoch_id"]
        request_epochs.add(request_epoch)
        request_observation = observation["request_observation"]
        assert request_observation["epoch_id"] == request_epoch
        clear = observation["worker_state_clear"]
        if stage == "entry":
            assert clear is None
        else:
            assert isinstance(clear, Mapping)
            watermark = clear["observation_watermark"]
            assert type(watermark) is int and watermark > 0
            observation_watermarks.append(watermark)
    assert len(request_epochs) == 1
    assert observation_watermarks == sorted(observation_watermarks)


def _assert_worker_disposition_bounds(operation: Mapping[str, Any]) -> None:
    """Validate any durable native-worker rows without accepting new labels."""
    metadata = operation.get("metadata")
    assert isinstance(metadata, Mapping)
    # The child admission is real, but the fixture does not launch a second
    # runtime process.  Any controller disposition projection must still use
    # the bounded data-model vocabulary; an empty projection is valid when the
    # controller records only the parent boundary.
    native_swap = metadata.get("native_swap")
    assert isinstance(native_swap, Mapping)
    dispositions = native_swap.get("worker_dispositions", {})
    assert isinstance(dispositions, Mapping)
    for value in dispositions.values():
        if isinstance(value, Mapping):
            status = value.get("status")
        else:
            status = value
        assert status in _ALLOWED_WORKER_DISPOSITIONS


def test_public_socket_exact_parent_swap_reaches_ready_held_without_model_work(
        tmp_path: Path,
) -> None:
    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime()
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        source_operation = _start_and_release(fixture)
        before = fixture.state.read_json("controller.json")
        before_claims = fixture.state.read_lineage_claims()
        source_context_before = copy.deepcopy(before["native_context"])
        source_operation_before = next(
            item for item in before["operations"]
            if item["operation_id"] == source_operation
        )
        source_startup_before = copy.deepcopy(
            source_operation_before["metadata"]["native_startup"]
        )
        source_lineage_id = source_context_before["lineage"]["lineage_id"]
        source_claim_before = next(
            claim for claim in before_claims
            if claim["lineage_id"] == source_lineage_id
        )
        source_identity_before = {
            "owner_generation": source_context_before["lineage"]["owner_generation"],
            "lineage_id": source_lineage_id,
            "lineage_generation": source_context_before["lineage"][
                "lineage_generation"
            ],
            "session_uuid": source_context_before["lineage"]["session_uuid"],
            "runner_incarnation": source_context_before["runner_incarnation"],
            "invocation_id": source_context_before["invocation_id"],
        }
        source = next(
            item for item in before["participants"]
            if item["participant_id"] == "coordinator"
        )
        source_session = source["session_id"]
        source_native_config = copy.deepcopy(
            source["fingerprint"]["native_config"]
        )
        source_runner = source["metadata"]["runner_instance_id"]
        release_count_before = len(runtime.release_calls)
        send_count_before = len(runtime.send_calls)

        swapped = fixture.request(
            "native-swap-positive", "swap", {"profile": "team-b"}
        )
        assert swapped["ok"] is True, json.dumps(swapped, sort_keys=True)
        assert swapped["result"]["phase"] == "ready-held"
        _assert_durable_evidence(
            swapped["result"], provider, EVIDENCE_STAGES[:4]
        )
        _assert_worker_disposition_bounds(swapped["result"])

        after = fixture.state.read_json("controller.json")
        target = next(
            item for item in after["participants"]
            if item["participant_id"] == "coordinator"
        )
        assert target["session_id"] == source_session
        assert target["metadata"]["runner_instance_id"] != source_runner
        assert target["metadata"]["profile_name"] == "team-b"
        assert target["metadata"]["account_email"] == "b@example.invalid"
        assert after["generation"] == before["generation"]
        target_native_config = target["fingerprint"]["native_config"]
        assert target_native_config["lineage_id"] == source_native_config["lineage_id"]
        assert target_native_config["lineage_generation"] == source_native_config[
            "lineage_generation"
        ]
        assert fixture.state.read_lineage_claims() == before_claims
        assert len(runtime.open_calls) == 2
        assert len(runtime.coordinator_interrupt_calls) == 1
        assert len(runtime.shutdown_calls) == 1
        assert len(runtime.release_calls) == release_count_before
        assert len(runtime.send_calls) == send_count_before
        assert fixture.state.read_json("controller.json").get("checkpoints", {}) == []

        # The exact source archive/lineage facts remain durable; only the
        # target account and runner incarnation are adopted for the held copy.
        assert source_operation != swapped["result"]["operation_id"]
        native_swap = swapped["result"]["metadata"]["native_swap"]
        archives = after.get("native_source_archives")
        assert isinstance(archives, Mapping) and len(archives) == 1
        archive_id = native_swap["source_archive_id"]
        archive = archives[archive_id]
        assert archive["operation_id"] == swapped["result"]["operation_id"]
        assert archive["snapshot_digest"] == native_swap["source_archive_digest"]
        assert archive["source_identity"] == source_identity_before
        assert native_swap["source_identity"] == source_identity_before
        assert native_swap["source_claim_digest"] == _digest(source_claim_before)
        archive_snapshot = archive["snapshot"]
        archive_context = archive_snapshot["native_context"]
        assert archive_context["invocation_id"] == source_context_before["invocation_id"]
        assert archive_context["runner_incarnation"] == source_context_before[
            "runner_incarnation"
        ]
        assert archive_context["lineage"] == source_context_before["lineage"]
        archive_source_operation = next(
            item for item in archive_snapshot["operations"]
            if item["operation_id"] == source_operation
        )
        assert archive_source_operation["metadata"]["native_startup"] == (
            source_startup_before
        )
        archive_source = next(
            item for item in archive_snapshot["participants"]
            if item["participant_id"] == "coordinator"
        )
        assert archive_source["session_id"] == source_session
        assert archive_source["metadata"]["runner_instance_id"] == source_runner
        assert archive_source["fingerprint"]["native_config"]["lineage_id"] == (
            source_native_config["lineage_id"]
        )
        assert archive_source["fingerprint"]["native_config"][
            "lineage_generation"
        ] == source_native_config["lineage_generation"]
        interrupt_id = native_swap["interrupt_id"]
        archive_interrupts = archive_snapshot.get("coordinator_interrupts")
        assert isinstance(archive_interrupts, Mapping)
        interrupt_record = archive_interrupts.get(interrupt_id)
        assert isinstance(interrupt_record, Mapping)
        assert interrupt_record["interrupt_id"] == interrupt_id
        assert interrupt_record["digest"] == _digest(interrupt_record["frame"])
        interrupt_frame = interrupt_record["frame"]
        assert isinstance(interrupt_frame, Mapping)
        assert interrupt_frame["interrupt"]["interrupt_id"] == interrupt_id
        archive_swap_operation = next(
            item for item in archive_snapshot["operations"]
            if item["operation_id"] == swapped["result"]["operation_id"]
        )
        archive_selection = archive_swap_operation["metadata"].get(
            "coordinator_interrupt_selection"
        )
        assert isinstance(archive_selection, Mapping)
        assert archive_selection["operation_id"] == swapped["result"]["operation_id"]
        assert archive_selection["interrupt_id"] == interrupt_id
        assert native_swap["interrupt_intent_digest"] == _digest(archive_selection)
        assert interrupt_frame["interrupt"]["operation_id"] == archive_selection[
            "operation_id"
        ]
        assert interrupt_frame["interrupt"]["fence_epoch"] == archive_selection[
            "fence_epoch"
        ]
        assert interrupt_frame["interrupt"]["request_epoch_id"] == archive_selection[
            "request_epoch_id"
        ]
        process_fact = next(
            fact for fact in interrupt_record["evidence"].values()
            if fact["frame"]["evidence"]["kind"] == "process-excluded"
        )
        assert process_fact["frame"]["evidence"]["data"][
            "process_identity_digest"
        ] == runtime.source_process_identity_digest
        assert "native_source_archives" not in archive["snapshot"]


def test_native_swap_absent_provider_refuses_before_source_interrupt(
        tmp_path: Path,
) -> None:
    runtime = NativeSwapRuntime()
    with _harness(tmp_path, provider=None, runtime=runtime) as fixture:
        _start_and_release(fixture)
        sends_before = len(runtime.send_calls)
        refused = fixture.request(
            "native-swap-no-provider", "swap", {"profile": "team-b"}
        )
        assert refused["ok"] is False
        assert refused["code"] in {"unsupported", "live-unverified"}
        assert len(runtime.coordinator_interrupt_calls) == 0
        assert len(runtime.shutdown_calls) == 0
        assert len(runtime.open_calls) == 1
        assert runtime.release_calls
        assert len(runtime.send_calls) == sends_before


def test_native_swap_unknown_effect_refuses_and_never_opens_target(
        tmp_path: Path,
) -> None:
    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime()
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        runtime.unknown_effects = True
        sends_before = len(runtime.send_calls)
        before = fixture.state.read_json("controller.json")
        before_claims = fixture.state.read_lineage_claims()

        refused = fixture.request(
            "native-swap-unknown-effect", "swap", {"profile": "team-b"}
        )
        assert refused["ok"] is False
        assert refused["code"] == "uncertain-effect"
        # The typed interrupt intent/evidence crosses its own durable
        # boundary before the post-interrupt quiescence observation reports
        # the unknown effect.  Recovery must retain that one effect and stop
        # before any source shutdown, target open, or dispatch.
        assert len(runtime.coordinator_interrupt_calls) == 1
        assert len(runtime.shutdown_calls) == 0
        assert len(runtime.open_calls) == 1
        assert len(runtime.send_calls) == sends_before
        assert fixture.state.read_lineage_claims() == before_claims
        after = fixture.state.read_json("controller.json")
        source_before = next(
            item for item in before["participants"]
            if item["participant_id"] == "coordinator"
        )
        source_after = next(
            item for item in after["participants"]
            if item["participant_id"] == "coordinator"
        )
        # The trusted transcript preflight may durably promote the source's
        # reserved/fresh descriptor to written/resume.  That is the only
        # source-participant mutation permitted before the unknown-effect
        # refusal; identity, profile, runner, claim and every other metadata
        # field remain immutable.
        assert {
            key: value for key, value in source_after.items()
            if key != "metadata"
        } == {
            key: value for key, value in source_before.items()
            if key != "metadata"
        }
        before_metadata = source_before["metadata"]
        after_metadata = source_after["metadata"]
        allowed_preflight = {"transcript", "runner_spec", "spec"}
        assert set(before_metadata).issubset(set(after_metadata))
        assert set(after_metadata) - set(before_metadata) <= allowed_preflight
        for key in set(before_metadata) - allowed_preflight:
            assert after_metadata[key] == before_metadata[key]
        assert after_metadata["transcript"]["session_id"] == source_before[
            "session_id"
        ]
        assert after_metadata["transcript"]["exists"] is True
        assert after_metadata["transcript"]["written"] is True
        assert after_metadata["transcript"]["reserved"] is False
        for key in ("runner_spec", "spec"):
            if key in before_metadata:
                expected_spec = copy.deepcopy(before_metadata[key])
                expected_spec["mode"] = "resume"
                expected_spec["resume"] = True
                expected_spec.pop("fresh", None)
                assert after_metadata[key] == expected_spec
            else:
                # ``_apply_transcript_preflight`` may materialize the legacy
                # ``spec`` alias from the durable runner specification.
                assert key in after_metadata
                assert after_metadata[key] == after_metadata["runner_spec"]
        assert list(provider.by_stage) == ["entry"]


def test_native_swap_entry_capture_precedes_preflight_request_and_keeps_one_epoch(
        tmp_path: Path,
) -> None:
    """A request racing target preflight belongs to the captured entry epoch."""
    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime(inject_request_during_preflight=True)
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        refused = fixture.request(
            "native-swap-entry-race", "swap", {"profile": "team-b"}
        )
        assert refused["ok"] is False
        assert refused["code"] in {"uncertain-effect", "live-unverified"}
        assert runtime.request_observation_cursor == 1
        assert provider.entry_capture == {
            "request_epoch_id": provider.requests[0]["request_epoch_id"],
            "entry_evidence_ref": provider.responses[0]["request_observation"][
                "entry_evidence_ref"
            ],
            "request_count": 0,
        }
        assert provider.requests[0]["stage"] == "entry"
        assert len(provider.requests) == 2
        assert len(runtime.coordinator_interrupt_calls) <= 1
        assert provider.requests[1]["stage"] == "graph-drained"
        assert provider.requests[1]["request_epoch_id"] == provider.requests[0][
            "request_epoch_id"
        ]
        assert provider.responses[1]["request_observation"]["new_requests"] == 1
        assert provider.responses[1]["request_observation"]["continuous"] is True
        assert len(runtime.shutdown_calls) == 0
        assert len(runtime.open_calls) == 1
        durable = fixture.state.read_json("controller.json")
        operation = next(
            item for item in durable["operations"]
            if item["operation_id"] == durable["active_operation_id"]
        )
        native_swap = operation["metadata"]["native_swap"]
        capture = native_swap["entry_capture"]
        assert capture["binding"]["stage"] == "entry"
        assert capture["binding"]["request_epoch_id"] == provider.requests[0][
            "request_epoch_id"
        ]
        assert capture["state"] in {"captured-unvalidated", "accepted"}
        durable_evidence = native_swap["native_swap_evidence"]
        assert durable_evidence["graph-drained"]["observation"][
            "request_observation"
        ]["new_requests"] == 1


def test_native_swap_lost_entry_capture_after_reload_refuses_without_recapture(
        tmp_path: Path,
) -> None:
    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime(preflight_crash_once=True)
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        first = fixture.request(
            "native-swap-entry-capture-loss", "swap", {"profile": "team-b"}
        )
        assert first["ok"] is False
        assert first["code"] in {"uncertain-effect", "live-unverified"}
        assert len(provider.requests) == 1
        durable = fixture.state.read_json("controller.json")
        operation = next(
            item for item in durable["operations"]
            if item["operation_id"] == durable["active_operation_id"]
        )
        capture_before_reload = copy.deepcopy(
            operation["metadata"]["native_swap"]["entry_capture"]
        )
        assert capture_before_reload is not None
        counts_before = (
            len(runtime.coordinator_interrupt_calls),
            len(runtime.shutdown_calls),
            len(runtime.open_calls),
            len(runtime.release_calls),
            len(runtime.send_calls),
        )
        claims_before = fixture.state.read_lineage_claims()

        # Drop the old controller object without changing durable capture
        # bytes.  A replacement must reuse the captured entry epoch and must
        # not call the provider again merely because the process restarted.
        fixture.controller = None
        fixture.daemon.controller = None
        reloaded_runtime = _reload_fixture_controller(fixture)
        after_reload = fixture.state.read_json("controller.json")
        reloaded_operation = next(
            item for item in after_reload["operations"]
            if item["operation_id"] == after_reload["active_operation_id"]
        )
        assert reloaded_operation["phase"] == "indeterminate"
        assert reloaded_operation["metadata"]["native_swap"]["entry_capture"] == (
            capture_before_reload
        )
        assert reloaded_operation["metadata"]["native_swap"]["entry_capture"][
            "state"
        ] in {"captured-unvalidated", "pending"}
        retry = fixture.request(
            "native-swap-entry-capture-loss", "swap", {"profile": "team-b"}
        )
        assert retry["ok"] is False
        assert retry["code"] in {"uncertain-effect", "live-unverified", "invalid"}
        assert len(provider.requests) == 1
        assert (
            len(reloaded_runtime.coordinator_interrupt_calls),
            len(reloaded_runtime.shutdown_calls),
            len(reloaded_runtime.open_calls),
            len(reloaded_runtime.release_calls),
            len(reloaded_runtime.send_calls),
        ) == counts_before
        assert fixture.state.read_json("controller.json")["operations"] == (
            after_reload["operations"]
        )
        assert fixture.state.read_lineage_claims() == claims_before


def test_native_swap_independent_target_pin_mismatch_refuses_before_interrupt(
        tmp_path: Path,
) -> None:
    provider = NativeSwapEvidenceProvider(runtime_identity_digest="c" * 64)
    runtime = NativeSwapRuntime()
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        refused = fixture.request(
            "native-swap-target-pin-mismatch", "swap", {"profile": "team-b"}
        )
        assert refused["ok"] is False
        assert refused["code"] in {"stale-generation", "live-unverified", "uncertain-effect"}
        assert provider.requests[0]["stage"] == "entry"
        assert len(provider.requests) == 1
        assert len(runtime.coordinator_interrupt_calls) == 0
        assert len(runtime.shutdown_calls) == 0
        assert len(runtime.open_calls) == 1


def test_native_swap_busy_typed_source_interrupts_once_then_drains(
        tmp_path: Path,
) -> None:
    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime()
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        runtime._busy_until_interrupt = True
        swapped = fixture.request(
            "native-swap-busy-source", "swap", {"profile": "team-b"}
        )
        assert swapped["ok"] is True, json.dumps(swapped, sort_keys=True)
        assert swapped["result"]["phase"] == "ready-held"
        assert len(runtime.coordinator_interrupt_calls) == 1
        assert runtime._busy_until_interrupt is False
        drained = asyncio.run(runtime.status("coordinator"))
        assert drained["evidence"]["drained"] is True
        assert drained["evidence"]["participant_quiescent"] is True
        assert len(runtime.shutdown_calls) == 1
        assert len(runtime.open_calls) == 2
        assert list(provider.by_stage) == list(EVIDENCE_STAGES[:4])


def test_native_swap_blocked_runtime_times_out_without_replaying_interrupt(
        tmp_path: Path,
) -> None:
    """The short public deadline cancels one blocked effect and never retries it."""
    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime(block_interrupt=True)
    with _harness(
            tmp_path, provider=provider, runtime=runtime, operation_timeout=2.0
    ) as fixture:
        _start_and_release(fixture)
        baseline = (
            len(runtime.shutdown_calls),
            len(runtime.open_calls),
            len(runtime.release_calls),
            len(runtime.send_calls),
        )
        first = None
        try:
            first = fixture.request(
                "native-swap-blocked-runtime", "swap", {"profile": "team-b"}
            )
        except BaseException as error:
            assert getattr(error, "code", None) == "timeout"
        if first is not None:
            assert first["ok"] is False
            assert first["code"] == "timeout"
        assert len(runtime.coordinator_interrupt_calls) == 1
        assert (
            len(runtime.shutdown_calls),
            len(runtime.open_calls),
            len(runtime.release_calls),
            len(runtime.send_calls),
        ) == baseline

        # Once the fake is made cancellable, the same public request ID must
        # still refuse from the durable uncertain boundary rather than issue a
        # second interrupt or continue the lifecycle effects.
        runtime.block_interrupt = False
        retry = fixture.request(
            "native-swap-blocked-runtime", "swap", {"profile": "team-b"}
        )
        assert retry["ok"] is False
        assert retry["code"] in {"uncertain-effect", "busy", "live-unverified"}
        assert len(runtime.coordinator_interrupt_calls) == 1
        assert (
            len(runtime.shutdown_calls),
            len(runtime.open_calls),
            len(runtime.release_calls),
            len(runtime.send_calls),
        ) == baseline


@pytest.mark.parametrize("crash_boundary", ["interrupt", "shutdown", "open"])
def test_native_swap_crash_boundaries_never_repeat_lifecycle_effects(
        tmp_path: Path, crash_boundary: str,
) -> None:
    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime(crash_boundary=crash_boundary)
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        sends_before = len(runtime.send_calls)
        first = fixture.request(
            "native-swap-crash", "swap", {"profile": "team-b"}
        )
        assert first["ok"] is False
        assert first["code"] == "uncertain-effect"
        counts = (
            len(runtime.coordinator_interrupt_calls),
            len(runtime.shutdown_calls),
            len(runtime.open_calls),
        )
        operation_id = fixture.state.read_json("controller.json")[
            "active_operation_id"
        ]
        claims_before = fixture.state.read_lineage_claims()

        # A fresh controller and adapter must reconcile the durable window;
        # the retry is intentionally routed only after the public recover
        # boundary.  The copied runtime state represents the same reserved
        # process identities, not a new target process.
        reloaded_runtime = _reload_fixture_controller(fixture)
        recovered = fixture.request(
            "native-swap-crash-recover-" + crash_boundary,
            "recover",
            {"operation_id": operation_id},
        )
        if crash_boundary == "interrupt":
            # The interrupt callback crossed an uncertain boundary before its
            # typed intent was recorded.  Recovery must preserve uncertainty
            # and refuse the retry rather than infer a no-op interrupt.
            assert recovered["ok"] is False
            assert recovered["code"] in {"uncertain-effect", "live-unverified"}
            retry = fixture.request(
                "native-swap-crash", "swap", {"profile": "team-b"}
            )
            assert retry["ok"] is False
            assert retry["code"] in {"uncertain-effect", "busy"}
            expected_counts = counts
        else:
            assert recovered["ok"] is True, json.dumps(recovered, sort_keys=True)
            retry = fixture.request(
                "native-swap-crash", "swap", {"profile": "team-b"}
            )
            assert retry["ok"] is True, json.dumps(retry, sort_keys=True)
            assert retry["result"]["phase"] == "ready-held"
            expected_counts = (1, 1, 2)
        assert (
            len(reloaded_runtime.coordinator_interrupt_calls),
            len(reloaded_runtime.shutdown_calls),
            len(reloaded_runtime.open_calls),
        ) == expected_counts
        if crash_boundary == "interrupt":
            assert expected_counts == (1, 0, 1)
        elif crash_boundary == "shutdown":
            assert expected_counts == (1, 1, 2)
        else:
            assert expected_counts == (1, 1, 2)
        assert len(reloaded_runtime.send_calls) == sends_before
        assert fixture.state.read_lineage_claims() == claims_before


def test_native_swap_release_receipt_without_same_epoch_boundary_keeps_claims_and_no_pump(
        tmp_path: Path,
) -> None:
    provider = NativeSwapEvidenceProvider(incomplete_release_boundary=True)
    runtime = NativeSwapRuntime()
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        swapped = fixture.request(
            "native-swap-release-gap", "swap", {"profile": "team-b"}
        )
        assert swapped["ok"] is True, json.dumps(swapped, sort_keys=True)
        assert swapped["result"]["phase"] == "ready-held"
        _assert_durable_evidence(
            swapped["result"], provider, EVIDENCE_STAGES[:4]
        )
        claims_before_release = fixture.state.read_lineage_claims()
        sends_before = len(runtime.send_calls)

        operation_id = swapped["result"]["operation_id"]
        refused = fixture.request(
            "native-swap-release-gap-request", "release",
            {"operation_id": operation_id},
        )
        assert refused["ok"] is False
        assert refused["code"] in {"uncertain-effect", "live-unverified"}
        assert len(runtime.release_calls) == 2  # source release plus target gate
        assert len(runtime.gate_receipts) == 1
        assert len(runtime.send_calls) == sends_before
        assert fixture.state.read_lineage_claims() == claims_before_release
        final_record = fixture.state.read_json("controller.json")
        final_operation = next(
            item for item in final_record["operations"]
            if item["operation_id"] == operation_id
        )
        _assert_durable_evidence(
            final_operation,
            provider,
            EVIDENCE_STAGES,
        )
        assert final_operation["phase"] != "released"
        _assert_worker_disposition_bounds(final_operation)
        final_evidence = final_operation["metadata"]["native_swap"][
            "native_swap_evidence"]["release-boundary"]["observation"]
        assert final_evidence["request_observation"]["continuous"] is False
        assert final_evidence["request_observation"]["new_requests"] == 0
        assert final_evidence["binding"] == provider.by_stage[
            "release-boundary"
        ]["binding"]


def test_native_swap_same_id_omitted_specs_deduplicates_before_and_after_reload(
        tmp_path: Path,
) -> None:
    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime()
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        first = fixture.request(
            "native-swap-omitted-specs", "swap", {"profile": "team-b"}
        )
        assert first["ok"] is True, json.dumps(first, sort_keys=True)
        assert first["result"]["phase"] == "ready-held"
        operation_id = first["result"]["operation_id"]
        durable_before = fixture.state.read_json("controller.json")
        claims_before = fixture.state.read_lineage_claims()
        provider_count = len(provider.requests)
        lifecycle_counts = (
            len(runtime.coordinator_interrupt_calls),
            len(runtime.shutdown_calls),
            len(runtime.open_calls),
            len(runtime.release_calls),
            len(runtime.send_calls),
        )

        retry = fixture.request(
            "native-swap-omitted-specs", "swap", {"profile": "team-b"}
        )
        assert retry["ok"] is True, json.dumps(retry, sort_keys=True)
        assert retry["result"]["operation_id"] == operation_id
        assert retry["result"]["phase"] == "ready-held"
        assert fixture.state.read_json("controller.json") == durable_before
        assert fixture.state.read_lineage_claims() == claims_before
        assert len(provider.requests) == provider_count
        assert (
            len(runtime.coordinator_interrupt_calls),
            len(runtime.shutdown_calls),
            len(runtime.open_calls),
            len(runtime.release_calls),
            len(runtime.send_calls),
        ) == lifecycle_counts

        reloaded_runtime = _reload_fixture_controller(fixture)
        durable_before_reload_retry = fixture.state.read_json("controller.json")
        retry_after_reload = fixture.request(
            "native-swap-omitted-specs", "swap", {"profile": "team-b"}
        )
        assert retry_after_reload["ok"] is True, json.dumps(
            retry_after_reload, sort_keys=True
        )
        assert retry_after_reload["result"]["operation_id"] == operation_id
        assert retry_after_reload["result"]["phase"] == "ready-held"
        assert fixture.state.read_json("controller.json") == durable_before_reload_retry
        assert fixture.state.read_lineage_claims() == claims_before
        assert len(provider.requests) == provider_count
        assert (
            len(reloaded_runtime.coordinator_interrupt_calls),
            len(reloaded_runtime.shutdown_calls),
            len(reloaded_runtime.open_calls),
            len(reloaded_runtime.release_calls),
            len(reloaded_runtime.send_calls),
        ) == lifecycle_counts


def test_native_swap_all_six_stages_release_and_reload_never_releases_again(
        tmp_path: Path,
) -> None:
    """The full gate is durable across a controller reload.

    This is intentionally a real public-socket/controller/state scenario.  A
    second exact release request is an observation of the durable authorization
    and must not call the target runtime release or append a second gate
    receipt.  The test remains red until the controller/SDK native release
    seam is integrated; it does not grant that seam through a fixture field.
    """

    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime()
    with _harness(tmp_path, provider=provider, runtime=runtime) as fixture:
        _start_and_release(fixture)
        swapped = fixture.request(
            "native-swap-release-positive", "swap", {"profile": "team-b"}
        )
        assert swapped["ok"] is True, json.dumps(swapped, sort_keys=True)
        assert swapped["result"]["phase"] == "ready-held"
        _assert_durable_evidence(
            swapped["result"], provider, EVIDENCE_STAGES[:4]
        )
        operation_id = swapped["result"]["operation_id"]
        release_count_before = len(runtime.release_calls)
        claims_before = fixture.state.read_lineage_claims()

        released = fixture.request(
            "native-swap-release-positive-release", "release",
            {"operation_id": operation_id},
        )
        assert released["ok"] is True, json.dumps(released, sort_keys=True)
        assert released["result"]["phase"] == "released"
        _assert_durable_evidence(
            released["result"], provider, EVIDENCE_STAGES
        )
        assert len(runtime.release_calls) == release_count_before + 1
        assert runtime.release_calls[-1]["native_swap_binding"] is not None
        assert len(runtime.gate_receipts) == 1
        first_authorization = runtime.native_swap_authorization_acks[-1]
        assert first_authorization["authorized"] is True
        binding = runtime.release_calls[-1]["native_swap_binding"]
        repeated_authorization = asyncio.run(
            runtime._native_swap_release_callback(
                binding["participant_id"],
                binding["session_id"],
                binding["runner_incarnation"],
                first_authorization["validation_id"],
                copy.deepcopy(binding),
            )
        )
        assert repeated_authorization["authorized"] is False
        assert repeated_authorization["authorization_id"] == first_authorization[
            "authorization_id"
        ]
        assert len(runtime.release_calls) == release_count_before + 1
        assert len(runtime.gate_receipts) == 1
        durable = fixture.state.read_json("controller.json")
        native_swap = next(
            item for item in durable["operations"]
            if item["operation_id"] == operation_id
        )["metadata"]["native_swap"]
        # The runtime's released acknowledgement carries the canonical
        # boundary receipt under its evidence object.  The controller stores
        # that validated receipt in the native-swap metadata projection while
        # retaining a safe transport receipt without the gate-only field.
        runtime_evidence = runtime._opened["coordinator"]["evidence"]
        assert runtime_evidence["native_swap_release_boundary"] == (
            runtime.gate_receipts[-1]
        )
        assert native_swap["release_boundary"] == runtime.gate_receipts[-1]
        assert fixture.state.read_lineage_claims() == claims_before

        # Reload the real controller from the same durable store and route the
        # exact request through the still-running public daemon/socket.
        reloaded_runtime = _reload_fixture_controller(fixture)
        before_retry = fixture.state.read_json("controller.json")
        repeat = fixture.request(
            "native-swap-release-positive-release", "release",
            {"operation_id": operation_id},
        )
        assert repeat["ok"] is True, json.dumps(repeat, sort_keys=True)
        assert repeat["result"]["operation_id"] == operation_id
        assert repeat["result"]["phase"] == "released"
        assert len(reloaded_runtime.release_calls) == release_count_before + 1
        assert len(reloaded_runtime.gate_receipts) == 1
        assert fixture.state.read_json("controller.json") == before_retry
        assert fixture.state.read_lineage_claims() == claims_before
