# SPDX-License-Identifier: Apache-2.0
"""Fake-only contract tests for the managed lane controller.

The controller is intentionally exercised with an in-memory state boundary
and a runtime double.  No SDK, Claude account, auth material, subprocess, or
filesystem is involved.  The imported module is the implementation task's
T008 deliverable, so this file is expected to be red while that module is
absent.

The tests pin the public model used by T008: a ``Participant`` has a stable
participant/session identity, explicit logical parent/task/mailbox links, a
durable state, and (for writers) a ``WriterClaim``.  Mail is represented by a
``MailboxEntry`` and lifecycle transitions by an ``Operation``.  The
controller delegates writer exclusion to its state store and never owns a
second in-memory claim registry.
"""

from __future__ import annotations

import copy
import asyncio
import json
import threading
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import pytest

from lane_managed_controller import (
    ControllerError,
    MailboxEntry,
    ManagedController,
    Operation,
    Participant,
    WriterClaim,
)


COORDINATOR_SESSION = "11111111-1111-4111-8111-111111111111"
WORKER_A_SESSION = "22222222-2222-4222-8222-222222222222"
WORKER_B_SESSION = "33333333-3333-4333-8333-333333333333"
WORKER_C_SESSION = "44444444-4444-4444-8444-444444444444"
WORKER_D_SESSION = "55555555-5555-4555-8555-555555555555"
RESERVED_SESSION = "66666666-6666-4666-8666-666666666666"
ROLLOVER_COORDINATOR_SESSION = "77777777-7777-4777-8777-777777777777"
ROLLOVER_WORKER_A_SESSION = "88888888-8888-4888-8888-888888888888"
ROLLOVER_WORKER_B_SESSION = "99999999-9999-4999-8999-999999999999"
MANAGED_LANE = "build"
NATIVE_START_LINEAGE_ID = "native-start-lineage"
NATIVE_START_RUNNER = "native-start-runner"

SWAP_PROFILE = {
    "name": "target-profile",
    "email": "target@example.invalid",
    "family": "claude-transcripts-v1",
    "status": "active",
    "authentication": {"type": "subscription_oauth"},
    "config_dir": "/managed/profiles/target",
    "transcript_store": "claude-transcripts-v1",
    "workspace": "/managed/workspace",
    "permission_mode": "default",
    "model": "claude-sonnet-4-20250514",
    "fingerprint": {
        "model": "claude-sonnet-4-20250514",
        "permission_mode": "default",
        "workspace": "/managed/workspace",
    },
}

READ_ONLY_METADATA = {
    "read_only_enforced": True,
    "tool_allowlist": ["Read"],
    "tool_denylist": ["Write", "Edit", "Bash", "Agent", "Task", "Team"],
    "tools": [],
    "mcp_servers": [],
    "permissions": {
        "mode": "allowlist",
        "enforced": True,
        "allow": ["Read"],
        "deny": ["Write", "Edit", "Bash", "Agent", "Task", "Team"],
        "mcp": [],
    },
}


def _session_name(participant_id: str) -> str:
    return "managed-" + participant_id


def _identity_fingerprint(
        participant_id: str, fingerprint: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    result = copy.deepcopy(
        SWAP_PROFILE["fingerprint"] if fingerprint is None else fingerprint
    )
    result["session_name"] = _session_name(participant_id)
    result["bound_lane"] = MANAGED_LANE
    return result


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _runner_pid(participant_id: str) -> int:
    return {
        "coordinator": 1000,
        "worker-a": 1001,
        "worker-b": 1002,
        "worker-completed": 1003,
    }.get(participant_id, 1099)


def _runner_process(participant_id: str) -> Dict[str, Any]:
    return {
        "pid": _runner_pid(participant_id),
        "process_group_id": "pg-old-" + participant_id,
        "process_start_token": "start-old-" + participant_id,
        "process_group_owned": True,
    }


def _participant(
        participant_id: str,
        session_id: str,
        *,
        session_name: Optional[str] = None,
        bound_lane: str = MANAGED_LANE,
        role: str = "worker",
        parent_id: Optional[str] = "coordinator",
        task_id: Optional[str] = "task-1",
        mailbox_id: Optional[str] = "mailbox-1",
        state: str = "held",
        read_only: bool = False,
        writer_claim: Any = None,
        model: Optional[str] = None,
        permission_mode: Optional[str] = None,
        fingerprint: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
):
    session_name = _session_name(participant_id) if session_name is None else session_name
    participant_fingerprint = (
        None
        if fingerprint is None
        else _identity_fingerprint(participant_id, fingerprint)
    )
    return Participant(
        participant_id=participant_id,
        session_id=session_id,
        session_name=session_name,
        bound_lane=bound_lane,
        role=role,
        parent_id=parent_id,
        task_id=task_id,
        mailbox_id=mailbox_id,
        kind="independent",
        state=state,
        read_only=read_only,
        background=False,
        detached=False,
        writer_claim=writer_claim,
        model=model,
        permission_mode=permission_mode,
        fingerprint=participant_fingerprint,
        metadata=metadata,
    )


def _claim(participant_id: str, worktree: Any,
           *, lane: str = MANAGED_LANE, repository: Any = None):
    return WriterClaim(
        participant_id=participant_id,
        worktree=Path(worktree),
        lane=lane,
        repository=None if repository is None else Path(repository),
        state="active",
    )


def _mark(participant: Any, semantic: str, value: Any) -> Any:
    """Set a safety/participant-kind field on a model for a rejection test."""
    assert isinstance(participant, Participant)
    assert semantic in {"kind", "background", "detached"}
    return replace(participant, **{semantic: value})


class MemoryStore:
    """In-memory stand-in for ``ManagedStateStore`` used by the controller."""

    def __init__(self):
        self.identity = SimpleNamespace(lane=MANAGED_LANE)
        self.documents: Dict[str, Any] = {}
        self.journal: List[Tuple[str, Any]] = []
        self.claims: Dict[Tuple[str, str], Any] = {}
        self.claim_calls: List[Tuple[str, str, Any]] = []
        self.release_calls: List[Tuple[str, str]] = []
        self.write_calls: List[Tuple[str, Any]] = []
        self.claim_error: Optional[ControllerError] = None
        # Transcript identity is authoritative only through the exact injected
        # profile-owned callable.  Participant metadata below is deliberately
        # not accepted as proof by itself.
        self.transcript_evidence: Dict[str, Any] = {}
        self.transcript_bindings: Dict[Tuple[str, str, str], str] = {}
        self.transcript_verifier = self._verify_transcript
        self.verifier_calls: List[Tuple[str, str, str]] = []
        self._lock = threading.RLock()

    @contextmanager
    def locked(self, shared: bool = False):
        with self._lock:
            yield self

    def read_json(self, name: str):
        return copy.deepcopy(self.documents.get(name))

    def write_json(self, name: str, data: Any):
        self.write_calls.append((name, copy.deepcopy(data)))
        self.documents[name] = copy.deepcopy(data)
        return data

    def append_journal(self, name: str, event: Any):
        self.journal.append((name, copy.deepcopy(event)))
        return event

    def _verify_transcript(self, profile_name: str, session_id: str,
                           workspace: str):
        workspace = str(workspace)
        self.verifier_calls.append((profile_name, session_id, workspace))
        binding = (profile_name, session_id, workspace)
        participant_id = self.transcript_bindings.get(binding)
        if participant_id is None and profile_name == SWAP_PROFILE["name"]:
            # ctx creates a fresh fixed UUID only after its preflight has
            # proved the current released roster.  The injected resolver can
            # prove this new reservation as absent without inventing a native
            # holder or attaching a logical participant ID.
            project = workspace + "/project"
            return {
                "profile": {
                    "name": SWAP_PROFILE["name"],
                    "email": SWAP_PROFILE["email"],
                    "family": SWAP_PROFILE["family"],
                    "status": "active",
                    "authentication": {"type": "subscription_oauth"},
                    "config_dir": SWAP_PROFILE["config_dir"],
                },
                "session_id": session_id,
                "workspace": workspace,
                "transcript_store": SWAP_PROFILE["transcript_store"],
                "transcript_project": project,
                "transcript": {
                    "session_id": session_id,
                    "path": None,
                    "exists": False,
                    "written": False,
                    "regular": False,
                    "private": False,
                    "store": SWAP_PROFILE["transcript_store"],
                    "project": project,
                    "reserved": True,
                    "mode": "fresh",
                },
                "holders": [],
                "unknown_holders": [],
                "ambiguous": False,
            }
        evidence = self.transcript_evidence.get(participant_id)
        if evidence is None:
            raise ControllerError(
                "unknown", "canonical transcript verifier has no evidence"
            )
        result = copy.deepcopy(evidence)
        # The resolver is called for the selected profile.  During swap the
        # native holder may still be under source-profile; that holder remains
        # in the canonical result while top-level profile identity is the
        # requested target.  Initial start asks for source-profile instead.
        if profile_name == SWAP_PROFILE["name"]:
            result["profile"] = {
                "name": SWAP_PROFILE["name"],
                "email": SWAP_PROFILE["email"],
                "family": SWAP_PROFILE["family"],
                "status": "active",
                "authentication": {"type": "subscription_oauth"},
                "config_dir": SWAP_PROFILE["config_dir"],
            }
        else:
            result["profile"] = {
                "name": profile_name,
                "email": "source@example.invalid",
                "family": SWAP_PROFILE["family"],
                "status": "active",
                "authentication": {"type": "subscription_oauth"},
                "config_dir": "/managed/profiles/source",
            }
        return result

    def claim_writer(self, participant_id: str, worktree: Any,
                     repository: Any = None):
        path = str(worktree)
        self.claim_calls.append((participant_id, path, repository))
        if self.claim_error is not None:
            raise self.claim_error
        key = (participant_id, path)
        if key in self.claims:
            return self.claims[key]
        claim = _claim(participant_id, path, repository=repository)
        self.claims[key] = claim
        return claim

    def release_writer(self, participant_id: str, worktree: Any):
        path = str(worktree)
        self.release_calls.append((participant_id, path))
        key = (participant_id, path)
        if key not in self.claims:
            raise ControllerError("ownership-conflict", "writer claim is absent")
        claim = self.claims.pop(key)
        return claim


class ClaimIndexMemoryStore(MemoryStore):
    """Trusted shared claim-index adapter for partial unenroll recovery."""

    def __init__(self):
        super().__init__()
        self.identity.lane_key = MANAGED_LANE.casefold()
        self.identity.host = "test-host"
        self.owner = {"mode": "managed", "generation": 7}

    def read_owner(self) -> Dict[str, Any]:
        return copy.deepcopy(self.owner)

    def _canonical_repository(self, repository: Any, worktree: Any) -> str:
        if repository is None:
            return str(Path(worktree).resolve())
        return str(Path(repository).resolve())

    def _load_claims(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for (participant_id, worktree), claim in self.claims.items():
            canonical_worktree = str(Path(worktree).resolve())
            repository = self._canonical_repository(
                claim.repository, canonical_worktree
            )
            rows.append({
                "state": claim.state,
                "lane": claim.lane,
                "lane_key": str(claim.lane).casefold(),
                "host": self.identity.host,
                "workspace": str(Path(canonical_worktree).parent),
                "common_dir": str(Path(canonical_worktree).parent),
                "participant_id": participant_id,
                "worktree": canonical_worktree,
                "repository": repository,
                "generation": 7,
                "claimed_at": 1700000000.0,
            })
        return copy.deepcopy(rows)


class NativeStartStore(MemoryStore):
    """Durable owner/lineage authority for coordinator-only startup tests."""

    def __init__(self, *, generation: int = 7) -> None:
        super().__init__()
        self.identity.lane_key = MANAGED_LANE.casefold()
        self.identity.host = "test-host"
        self.owner = {
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "record_kind": "managed-owner",
            "mode": "managed",
            "lane": MANAGED_LANE,
            "lane_key": MANAGED_LANE.casefold(),
            "generation": generation,
            "daemon_id": "daemon-test",
        }
        self.lineage_claims: list[dict[str, Any]] = []
        self.lineage_claim_calls: list[tuple[str, dict[str, Any]]] = []

    def read_owner(self) -> dict[str, Any]:
        return copy.deepcopy(self.owner)

    def read_lineage_claims(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.lineage_claims)

    def claim_lineage(self, lineage_id: str, **values: Any) -> dict[str, Any]:
        self.lineage_claim_calls.append((lineage_id, copy.deepcopy(values)))
        claim = {
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "record_kind": "workspace-claim",
            "claim_kind": "workspace",
            "lineage_id": lineage_id,
            "owner_generation": values["owner_generation"],
            "lineage_generation": values["lineage_generation"],
            "lane": MANAGED_LANE,
            "lane_key": MANAGED_LANE.casefold(),
            "host": "test-host",
            "coordinator_session_uuid": values["coordinator_session_uuid"],
            "workspace": values.get("workspace", "/native/workspace"),
            "common_dir": values.get("common_dir", "/native/workspace"),
            "repository": values.get(
                "repository", values.get("workspace", "/native/workspace")
            ),
            "state": "active",
            "parent_read_only": values["parent_read_only"],
            "claimed_at": 1700000000.0,
        }
        self.lineage_claims.append(copy.deepcopy(claim))
        return copy.deepcopy(claim)


class FakeRuntime:
    """Runtime double that records sends and can fail at either send boundary."""

    def __init__(self, failure: Optional[str] = None):
        self.failure = failure
        self.calls: List[Any] = []

    async def send(self, recipient_id: str, message_id: str,
                   payload_ref: Any):
        if self.failure == "before-send":
            raise RuntimeError("crash before transport send")
        self.calls.append((recipient_id, message_id, payload_ref))
        if self.failure == "after-send":
            raise RuntimeError("crash after transport send")
        return {
            "message_id": message_id,
            "accepted": True,
            "ack_kind": "accepted-send",
            "runtime_id": "runtime-ack-1",
        }


class SwapRuntime:
    """In-memory runner boundary for T011's async orchestration contract."""

    @staticmethod
    def preflight_held_swap(spec, evidence_record):
        # Synthetic routing evidence for historical controller unit fixtures.
        # This never establishes native-runtime capability.
        return {
            "verdict": "verified", "reason_code": "synthetic-test-control",
            "reason": "injected unit-test runtime only",
            "identity_digest": "a" * 64,
            "evidence_reference": "fixture://synthetic-controller-runtime",
        }

    def __init__(self, statuses: Dict[str, List[Dict[str, Any]]],
                 *, open_results: Optional[Dict[str, Dict[str, Any]]] = None,
                 send_failure: Optional[str] = None):
        self.statuses = {
            participant_id: [copy.deepcopy(item) for item in values]
            for participant_id, values in statuses.items()
        }
        self.open_results = {
            participant_id: copy.deepcopy(item)
            for participant_id, item in (open_results or {}).items()
        }
        self.send_failure = send_failure
        self.calls: List[Tuple[Any, ...]] = []
        self.opened: List[Tuple[str, Dict[str, Any]]] = []
        self.interrupted: List[str] = []
        self.released: List[str] = []
        self.sent: List[Tuple[str, str, Any]] = []
        self.shutdowns: List[str] = []
        self.open_evidence: Dict[str, Dict[str, Any]] = {}
        self.shutdown_evidence: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _result(participant_id: str, session_id: str,
                runner_instance_id: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "participant_id": participant_id,
            "session_id": session_id,
            "runner_instance_id": runner_instance_id,
            "evidence": copy.deepcopy(evidence),
        }

    async def open(self, participant_id: str, spec: Dict[str, Any]):
        assert isinstance(participant_id, str)
        assert isinstance(spec, dict)
        self.calls.append(("open", participant_id, copy.deepcopy(spec)))
        self.opened.append((participant_id, copy.deepcopy(spec)))
        if participant_id in self.open_results:
            result = copy.deepcopy(self.open_results[participant_id])
        else:
            result = self._result(
                participant_id,
                spec["session_id"],
                "runner-new-" + participant_id,
                {
                    "participant_id": participant_id,
                    "session_id": spec["session_id"],
                    "runner_instance_id": "runner-new-" + participant_id,
                    "ready": True,
                    "released": False,
                    "active_turn": False,
                    "turn_terminal": True,
                    "drained": True,
                    "participant_quiescent": True,
                    "tools_quiescent": True,
                    "uncertain_effects": [],
                    "process": {
                        "pid": 2000,
                        "process_group_id": "pg-new-" + participant_id,
                        "process_start_token": "start-new-" + participant_id,
                        "process_group_owned": True,
                        "exited": False,
                        "group_excluded": False,
                    },
                    "initialization": {
                        "account_email": spec["account_email"],
                        "permission_mode": spec["permission_mode"],
                        "model": spec["model"],
                        "fingerprint": copy.deepcopy(spec["fingerprint"]),
                    },
                },
            )
        self.open_evidence[participant_id] = copy.deepcopy(result)
        # Newly opened ctx coordinators become addressable by subsequent
        # status/release calls in the same fake runtime.
        self.statuses[participant_id] = [copy.deepcopy(result)]
        return result

    async def interrupt(self, participant_id: str):
        assert isinstance(participant_id, str)
        self.calls.append(("interrupt", participant_id))
        self.interrupted.append(participant_id)
        current = self.statuses[participant_id][-1]
        return copy.deepcopy(current)

    async def release(self, participant_id: str):
        assert isinstance(participant_id, str)
        self.calls.append(("release", participant_id))
        self.released.append(participant_id)
        current = self.statuses[participant_id][-1]
        result = copy.deepcopy(current)
        result["evidence"]["released"] = True
        return result

    async def send(self, participant_id: str, message_id: str,
                   payload_ref: Any):
        assert isinstance(participant_id, str)
        assert isinstance(message_id, str)
        if self.send_failure == "before-send":
            raise RuntimeError("crash before runtime send")
        self.calls.append(("send", participant_id, message_id, payload_ref))
        self.sent.append((participant_id, message_id, payload_ref))
        if self.send_failure == "after-send-before-ack":
            raise RuntimeError("crash after send before acknowledgement")
        current = self.statuses[participant_id][-1]
        return {
            "participant_id": participant_id,
            "session_id": current["session_id"],
            "runner_instance_id": current["runner_instance_id"],
            "message_id": message_id,
            "accepted": True,
            "ack_kind": "accepted-send",
        }

    async def status(self, participant_id: str):
        assert isinstance(participant_id, str)
        self.calls.append(("status", participant_id))
        values = self.statuses[participant_id]
        value = values.pop(0) if len(values) > 1 else values[0]
        return copy.deepcopy(value)

    async def shutdown(self, participant_id: str):
        assert isinstance(participant_id, str)
        self.calls.append(("shutdown", participant_id))
        self.shutdowns.append(participant_id)
        current = copy.deepcopy(self.statuses[participant_id][-1])
        process = current["evidence"]["process"]
        process["exited"] = True
        process["group_excluded"] = True
        self.shutdown_evidence[participant_id] = copy.deepcopy(current)
        return current


class CompletionRuntime(SwapRuntime):
    """Runner double with canonical completion evidence and a status gate."""

    def __init__(self, statuses: Dict[str, List[Dict[str, Any]]],
                 *, shutdown_failure: Optional[str] = None):
        super().__init__(statuses)
        self.shutdown_failure = shutdown_failure
        self.completion_status_started: Optional[asyncio.Event] = None
        self.allow_completion_status: Optional[asyncio.Event] = None

    @staticmethod
    def _canonical(value: Dict[str, Any]) -> Dict[str, Any]:
        result = copy.deepcopy(value)
        evidence = result["evidence"]
        evidence.update({
            "participant_id": result["participant_id"],
            "session_id": result["session_id"],
            "runner_instance_id": result["runner_instance_id"],
            "quiescent": True,
            "tools": [],
        })
        return result

    async def open(self, participant_id: str, spec: Dict[str, Any]):
        result = await super().open(participant_id, spec)
        return self._canonical(result)

    async def interrupt(self, participant_id: str):
        result = await super().interrupt(participant_id)
        return self._canonical(result)

    async def release(self, participant_id: str):
        result = await super().release(participant_id)
        return self._canonical(result)

    async def status(self, participant_id: str):
        result = await super().status(participant_id)
        result = self._canonical(result)
        if (
            participant_id == "worker-a"
            and self.completion_status_started is not None
            and self.allow_completion_status is not None
        ):
            self.completion_status_started.set()
            await self.allow_completion_status.wait()
        return result

    async def shutdown(self, participant_id: str):
        if participant_id == self.shutdown_failure:
            self.calls.append(("shutdown", participant_id))
            self.shutdowns.append(participant_id)
            raise RuntimeError("injected uncertain completion shutdown")
        result = await super().shutdown(participant_id)
        return self._canonical(result)


class StartRuntime(SwapRuntime):
    """Runner double for managed startup launch-intent ordering tests."""

    def __init__(self, *, fail_on_open: Optional[str] = None,
                 cancel_on_open: Optional[str] = None,
                 uncertain_after_open: Optional[str] = None):
        super().__init__(_start_statuses())
        self.fail_on_open = fail_on_open
        self.cancel_on_open = cancel_on_open
        self.uncertain_after_open = uncertain_after_open
        self.controller: Optional[ManagedController] = None
        self.open_attempts: List[str] = []
        self.intent_snapshots: List[Tuple[str, Any]] = []
        self.prompts: List[Any] = []

    async def open(self, participant_id: str, spec: Dict[str, Any]):
        self.open_attempts.append(participant_id)
        if self.controller is not None:
            self.intent_snapshots.append(
                (participant_id,
                 copy.deepcopy(self.controller.store.documents.get("controller.json")))
            )
        if participant_id == self.cancel_on_open:
            raise asyncio.CancelledError
        if participant_id == self.fail_on_open:
            raise RuntimeError("injected startup failure")
        result = await super().open(participant_id, spec)
        if participant_id == self.uncertain_after_open:
            raise RuntimeError("injected uncertain post-open boundary")
        return result


def _controller(*, runtime: Any = None,
                store: Optional[MemoryStore] = None):
    selected_store = MemoryStore() if store is None else store
    controller = ManagedController(selected_store, runtime=runtime,
                                   clock=lambda: 1000.0,
                                   transcript_verifier=selected_store.transcript_verifier)
    return controller, selected_store


def _enrolled(*, runtime: Any = None,
              coordinator_metadata: Optional[Dict[str, Any]] = None,
              coordinator_read_only: bool = True,
              coordinator_claim: Any = None,
              store: Optional[MemoryStore] = None):
    controller, store = _controller(runtime=runtime, store=store)
    if coordinator_metadata is None:
        coordinator_metadata = copy.deepcopy(READ_ONLY_METADATA)
    coordinator = _participant(
        "coordinator", COORDINATOR_SESSION, role="coordinator",
        parent_id=None, task_id="task-root", mailbox_id="mailbox-coordinator",
        read_only=coordinator_read_only,
        writer_claim=coordinator_claim,
        model=SWAP_PROFILE["model"],
        permission_mode="dontAsk",
        fingerprint=SWAP_PROFILE["fingerprint"],
        metadata=coordinator_metadata,
    )
    controller.enroll(generation=7, coordinator=coordinator)
    return controller, store, coordinator


def _swap_status(participant_id: str, session_id: str, *,
                 turn_terminal: bool = True, drained: bool = True,
                 participant_quiescent: bool = True,
                 tools_quiescent: bool = True,
                 process_exited: bool = False,
                 group_excluded: bool = False,
                 active_turn: Optional[bool] = None,
                 uncertain_effects: Optional[List[str]] = None,
                 runner_instance_id: Optional[str] = None,
                 evidence_participant_id: Optional[str] = None,
                 evidence_session_id: Optional[str] = None) -> Dict[str, Any]:
    """Return one exact runner-evidence result envelope.

    Lane generation, operation IDs, external request IDs, transcript identity,
    and workspace equality are controller-owned state.  They intentionally do
    not appear in this adapter result.
    """
    process = _runner_process(participant_id)
    process.update({
        "exited": process_exited,
        "group_excluded": group_excluded,
    })
    active_turn_value = (not turn_terminal) if active_turn is None else active_turn
    return {
        "participant_id": evidence_participant_id or participant_id,
        "session_id": evidence_session_id or session_id,
        "runner_instance_id": runner_instance_id or "runner-old-" + participant_id,
        "evidence": {
            "participant_id": evidence_participant_id or participant_id,
            "session_id": evidence_session_id or session_id,
            "runner_instance_id": runner_instance_id or "runner-old-" + participant_id,
            "ready": True,
            "released": False,
            "active_turn": active_turn_value,
            "turn_terminal": turn_terminal,
            "drained": drained,
            "participant_quiescent": participant_quiescent,
            "tools_quiescent": tools_quiescent,
            "quiescent": all((
                not active_turn_value,
                turn_terminal,
                drained,
                participant_quiescent,
                tools_quiescent,
            )),
            "tools": [],
            "uncertain_effects": list(uncertain_effects or []),
            "process": process,
                    "initialization": {
                        "account_email": "source@example.invalid",
                        "permission_mode": "dontAsk",
                        "model": SWAP_PROFILE["model"],
                        "fingerprint": _identity_fingerprint(participant_id),
                    },
                },
            }


def _swap_open_result(participant_id: str, session_id: str, *,
                      runner_instance_id: Optional[str] = None,
                      ready: bool = True) -> Dict[str, Any]:
    """Build an exact target-loader result for open/recovery tests."""
    result = _swap_status(
        participant_id,
        session_id,
        runner_instance_id=runner_instance_id or "runner-new-" + participant_id,
        process_exited=False,
        group_excluded=False,
    )
    result["evidence"]["ready"] = ready
    target_fingerprint = _identity_fingerprint(
        participant_id, SWAP_PROFILE["fingerprint"]
    )
    target_fingerprint.update({
        "profile_name": SWAP_PROFILE["name"],
        "account_email": SWAP_PROFILE["email"],
        "config_dir": SWAP_PROFILE["config_dir"],
    })
    result["evidence"]["initialization"] = {
        "account_email": SWAP_PROFILE["email"],
        "permission_mode": SWAP_PROFILE["permission_mode"],
        "model": SWAP_PROFILE["model"],
        "fingerprint": target_fingerprint,
    }
    return result


def _completion_status(participant_id: str, session_id: str,
                       runner_instance_id: str, *,
                       terminal: bool = True,
                       drained: bool = True,
                       participant_quiescent: bool = True,
                       tools_quiescent: bool = True,
                       active_turn: bool = False,
                       uncertain_effects: Optional[List[str]] = None,
                       tools: Optional[List[Dict[str, Any]]] = None,
                       process_exited: bool = False,
                       group_excluded: bool = False) -> Dict[str, Any]:
    result = CompletionRuntime._canonical(_swap_status(
        participant_id,
        session_id,
        runner_instance_id=runner_instance_id,
        turn_terminal=terminal,
        drained=drained,
        participant_quiescent=participant_quiescent,
        tools_quiescent=tools_quiescent,
        active_turn=active_turn,
        uncertain_effects=uncertain_effects,
        process_exited=process_exited,
        group_excluded=group_excluded,
    ))
    result["evidence"]["quiescent"] = all((
        not active_turn,
        terminal,
        drained,
        participant_quiescent,
        tools_quiescent,
    ))
    result["evidence"]["tools"] = (
        [] if tools is None and tools_quiescent else
        ([{"tool_id": "tool-in-flight", "state": "running"}]
         if tools is None else tools)
    )
    return result


def _source_metadata(session_id: str, *,
                     participant_id: Optional[str] = None,
                     transcript_exists: bool = True,
                     transcript_written: bool = True,
                     transcript_reserved: bool = False,
                     transcript_session_id: Optional[str] = None,
                     transcript_store: str = SWAP_PROFILE["transcript_store"],
                     workspace: str = SWAP_PROFILE["workspace"]):
    identity_name = (
        _session_name(participant_id) if participant_id is not None else None
    )
    identity_fingerprint = (
        _identity_fingerprint(participant_id)
        if participant_id is not None
        else copy.deepcopy(SWAP_PROFILE["fingerprint"])
    )
    metadata = {
        **copy.deepcopy(READ_ONLY_METADATA),
        "profile_name": "source-profile",
        "profile_family": SWAP_PROFILE["family"],
        "profile_status": "active",
        "profile_authentication": {"type": "subscription_oauth"},
        "account_email": "source@example.invalid",
        "config_dir": "/managed/profiles/source",
        "session_name": identity_name,
        "bound_lane": MANAGED_LANE,
        "workspace": workspace,
        "transcript_store": transcript_store,
        "transcript": {
            "session_id": transcript_session_id or session_id,
            "exists": transcript_exists,
            "written": transcript_written,
            "reserved": transcript_reserved,
        },
        "runner_spec": {
            "mode": "resume",
            "session_id": session_id,
            "session_name": identity_name,
            "bound_lane": MANAGED_LANE,
            "profile_name": "source-profile",
            "profile_family": SWAP_PROFILE["family"],
            "account_email": "source@example.invalid",
            "config_dir": "/managed/profiles/source",
            "workspace": workspace,
            "transcript_store": transcript_store,
            "fingerprint": identity_fingerprint,
        },
    }
    if participant_id is not None:
        metadata["runner_process"] = _runner_process(participant_id)
    return metadata


def _bound_source_metadata(
        participant_id: str, session_id: str,
        supplied: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = copy.deepcopy(
        supplied
        if supplied is not None
        else _source_metadata(session_id, participant_id=participant_id)
    )
    if not metadata.get("session_name"):
        metadata["session_name"] = _session_name(participant_id)
    if not metadata.get("bound_lane"):
        metadata["bound_lane"] = MANAGED_LANE
    runner_spec = metadata.get("runner_spec")
    if isinstance(runner_spec, dict):
        if not runner_spec.get("session_name"):
            runner_spec["session_name"] = _session_name(participant_id)
        if not runner_spec.get("bound_lane"):
            runner_spec["bound_lane"] = MANAGED_LANE
        runner_fingerprint = runner_spec.get("fingerprint")
        if isinstance(runner_fingerprint, Mapping):
            runner_fingerprint = dict(runner_fingerprint)
            if not runner_fingerprint.get("session_name"):
                runner_fingerprint["session_name"] = _session_name(participant_id)
            if not runner_fingerprint.get("bound_lane"):
                runner_fingerprint["bound_lane"] = MANAGED_LANE
            runner_spec["fingerprint"] = runner_fingerprint
    metadata.setdefault("runner_process", _runner_process(participant_id))
    return metadata


def _swap_roster(
        runtime: SwapRuntime,
        *,
        participant_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        participant_sessions: Optional[Dict[str, str]] = None,
        coordinator_read_only: bool = True,
        coordinator_claim: Any = None,
        store: Optional[MemoryStore] = None,
):
    participant_metadata = participant_metadata or {}
    participant_sessions = participant_sessions or {}
    worker_a_session = participant_sessions.get("worker-a", WORKER_A_SESSION)
    worker_b_session = participant_sessions.get("worker-b", WORKER_B_SESSION)
    completed_session = participant_sessions.get("worker-completed", WORKER_C_SESSION)
    controller, store, coordinator = _enrolled(
        runtime=runtime,
        coordinator_metadata=_source_metadata(
            COORDINATOR_SESSION, participant_id="coordinator"
        ),
        coordinator_read_only=coordinator_read_only,
        coordinator_claim=coordinator_claim,
        store=store,
    )
    worker_a_metadata = _bound_source_metadata(
        "worker-a", worker_a_session, participant_metadata.get("worker-a")
    )
    controller.add_worker(_participant(
        "worker-a", worker_a_session, task_id="task-a", mailbox_id="mailbox-a",
        writer_claim=_claim("worker-a", "/trees/a"),
        model=SWAP_PROFILE["model"],
        permission_mode=SWAP_PROFILE["permission_mode"],
        fingerprint=SWAP_PROFILE["fingerprint"],
        metadata=worker_a_metadata,
    ))
    worker_b_metadata = _bound_source_metadata(
        "worker-b", worker_b_session, participant_metadata.get("worker-b")
    )
    controller.add_worker(_participant(
        "worker-b", worker_b_session, task_id="task-b", mailbox_id="mailbox-b",
        writer_claim=_claim("worker-b", "/trees/b"),
        model=SWAP_PROFILE["model"],
        permission_mode=SWAP_PROFILE["permission_mode"],
        fingerprint=SWAP_PROFILE["fingerprint"],
        metadata=worker_b_metadata,
    ))
    completed_metadata = _bound_source_metadata(
        "worker-completed", completed_session,
        participant_metadata.get("worker-completed"),
    )
    completed_status = _completion_status(
        "worker-completed",
        completed_session,
        "runner-old-worker-completed",
        process_exited=True,
        group_excluded=True,
    )
    completed_metadata.setdefault("completion_evidence", {
        "generation": 7,
        "runner_instance_id": completed_status["runner_instance_id"],
        "status": "completed",
        "shutdown": completed_status["evidence"],
    })
    controller.add_worker(_participant(
        "worker-completed", completed_session, task_id="task-completed",
        mailbox_id="mailbox-completed", state="completed", read_only=True,
        model=SWAP_PROFILE["model"],
        permission_mode=SWAP_PROFILE["permission_mode"],
        fingerprint=SWAP_PROFILE["fingerprint"],
        metadata=completed_metadata,
    ))
    for raw in _roster(controller.status()):
        participant_id = _value(raw, "participant_id")
        session_id = _value(raw, "session_id")
        metadata = copy.deepcopy(_value(raw, "metadata", {}))
        metadata.setdefault("runner_process", _runner_process(participant_id))
        workspace = metadata.get("workspace")
        transcript_store = metadata.get("transcript_store")
        transcript_project = metadata.get(
            "transcript_project",
            None if workspace is None else str(workspace) + "/project",
        )
        profile = {
            "name": SWAP_PROFILE["name"],
            "email": SWAP_PROFILE["email"],
            "family": SWAP_PROFILE["family"],
            "status": "active",
            "authentication": {"type": "subscription_oauth"},
            "config_dir": SWAP_PROFILE["config_dir"],
        }
        transcript = copy.deepcopy(metadata.get("transcript"))
        if isinstance(transcript, Mapping):
            transcript.setdefault(
                "path",
                None if transcript.get("exists") is not True else (
                    str(transcript_store) + "/" + session_id + ".jsonl"
                ),
            )
            transcript.setdefault("regular", transcript.get("exists") is True)
            transcript.setdefault("private", transcript.get("exists") is True)
            transcript.setdefault("store", transcript_store)
            transcript.setdefault("project", transcript_project)
            transcript.setdefault(
                "mode",
                metadata.get("runner_spec", {}).get("mode", "resume")
                if isinstance(metadata.get("runner_spec"), Mapping)
                else "resume",
            )
        else:
            transcript = {
                "session_id": session_id,
                "path": None,
                "exists": False,
                "written": False,
                "regular": False,
                "private": False,
                "store": transcript_store,
                "project": transcript_project,
                "reserved": False,
                "mode": "resume",
            }
        runner_process = metadata["runner_process"]
        mode = str(
            metadata.get("runner_spec", {}).get("mode", "resume")
            if isinstance(metadata.get("runner_spec"), Mapping)
            else "resume"
        ).casefold()
        # A fresh reserved UUID has no native projects holder yet.  Resume and
        # swap evidence use the real native holder shape: no managed logical
        # participant ID crosses this injected resolver boundary.
        holders: List[Dict[str, Any]] = []
        if not (
            mode == "fresh"
            and transcript.get("exists") is False
            and transcript.get("written") is False
            and transcript.get("reserved") is True
        ):
            child_pid = int(runner_process["pid"]) + 10000
            holder = {
                "profile_name": metadata.get("profile_name"),
                "session_id": session_id,
                "pid": child_pid,
                "process_start_token": "child-start-" + participant_id,
                "record": "/profiles/%s/sessions/%s.json" % (
                    metadata.get("profile_name"), session_id
                ),
                "live": True,
                "pid_domain": "linux:test-machine:test-pid-namespace",
                "process_group_id": runner_process["process_group_id"],
                "process_group_member": True,
                "profile": metadata.get("profile_name"),
                "config_dir": metadata.get("config_dir"),
                "projects_store": transcript_store,
                "workspace": workspace,
                "path": "/profiles/%s/sessions/%s.json" % (
                    metadata.get("profile_name"), session_id
                ),
                "transcript_path": transcript.get("path"),
            }
            holders.append(holder)
        unknown_holders = copy.deepcopy(metadata.get("unknown_holders", []))
        ambiguous = bool(metadata.get("ambiguous", False))
        store.transcript_evidence[participant_id] = {
            "profile": profile,
            "session_id": session_id,
            "workspace": workspace,
            "transcript_store": transcript_store,
            "transcript_project": transcript_project,
            "transcript": transcript,
            "holders": holders,
            "unknown_holders": unknown_holders,
            "ambiguous": ambiguous,
        }
        for profile_name in (str(metadata.get("profile_name")), SWAP_PROFILE["name"]):
            store.transcript_bindings[
                (profile_name, session_id, str(workspace))
            ] = participant_id
    return controller, store, coordinator


def _bind_source_transcript(store: MemoryStore, participant: Participant) -> None:
    """Install real-shaped source-holder evidence for an admission fixture."""
    metadata = participant.metadata
    session_id = participant.session_id
    workspace = metadata["workspace"]
    transcript_store = metadata["transcript_store"]
    transcript = copy.deepcopy(metadata["transcript"])
    transcript.setdefault("path", transcript_store + "/" + session_id + ".jsonl")
    transcript.setdefault("regular", True)
    transcript.setdefault("private", True)
    transcript.setdefault("store", transcript_store)
    transcript.setdefault("project", workspace + "/project")
    transcript.setdefault("mode", "resume")
    process = metadata["runner_process"]
    holder = {
        "profile_name": metadata["profile_name"],
        "session_id": session_id,
        "pid": int(process["pid"]) + 10000,
        "process_start_token": "child-start-admission-" + participant.participant_id,
        "record": "/profiles/%s/sessions/%s.json" % (
            metadata["profile_name"], session_id
        ),
        "live": True,
        "pid_domain": "linux:test-machine:test-pid-namespace",
        "process_group_id": process["process_group_id"],
        "process_group_member": True,
        "profile": metadata["profile_name"],
        "config_dir": metadata["config_dir"],
        "projects_store": transcript_store,
        "workspace": workspace,
        "path": "/profiles/%s/sessions/%s.json" % (
            metadata["profile_name"], session_id
        ),
        "transcript_path": transcript.get("path"),
    }
    evidence = {
        "profile": {
            "name": metadata["profile_name"],
            "email": metadata["account_email"],
            "family": metadata["profile_family"],
            "status": metadata["profile_status"],
            "authentication": copy.deepcopy(metadata["profile_authentication"]),
            "config_dir": metadata["config_dir"],
        },
        "session_id": session_id,
        "workspace": workspace,
        "transcript_store": transcript_store,
        "transcript_project": workspace + "/project",
        "transcript": transcript,
        "holders": [holder],
        "unknown_holders": [],
        "ambiguous": False,
    }
    store.transcript_evidence[participant.participant_id] = evidence
    for profile_name in (metadata["profile_name"], SWAP_PROFILE["name"]):
        store.transcript_bindings[(profile_name, session_id, str(workspace))] = (
            participant.participant_id
        )


def _runtime_writes_target_transcript_holders(
        store: MemoryStore, runtime: SwapRuntime,
        participant_ids: Optional[Iterable[str]] = None,
) -> None:
    """Record target holders observed after the runtime accepted an open."""
    opened_by_id: Dict[str, Dict[str, Any]] = {}
    for participant_id, spec in runtime.opened:
        opened_by_id[participant_id] = copy.deepcopy(spec)
    selected_ids = list(opened_by_id) if participant_ids is None else list(participant_ids)
    for participant_id in selected_ids:
        spec = opened_by_id[participant_id]
        evidence = copy.deepcopy(store.transcript_evidence[participant_id])
        opened = runtime.open_evidence[participant_id]
        process = copy.deepcopy(opened["evidence"]["process"])
        session_id = spec["session_id"]
        workspace = str(spec["workspace"])
        transcript_store = spec["transcript_store"]
        profile_name = spec["profile_name"]
        durable_spec = copy.deepcopy(spec)
        if str(durable_spec.get("mode", "resume")).casefold() == "fresh":
            # The first runtime open may intentionally use a fresh reserved
            # UUID.  Once the runtime has written its transcript, the trusted
            # evidence records that transcript as resume-compatible; this is a
            # runtime-owned observation, not controller metadata used as proof.
            durable_spec["mode"] = "resume"
            durable_spec["resume"] = True
            durable_spec.pop("fresh", None)
        transcript = copy.deepcopy(evidence["transcript"])
        transcript.update({
            "session_id": session_id,
            "path": str(transcript_store) + "/" + session_id + ".jsonl",
            "exists": True,
            "written": True,
            "reserved": False,
            "regular": True,
            "private": True,
            "store": transcript_store,
            "project": workspace + "/project",
            "mode": durable_spec.get("mode", "resume"),
        })
        holder = {
            "profile_name": profile_name,
            "session_id": session_id,
            "pid": int(process["pid"]) + 10000,
            "process_start_token": "child-start-runtime-" + participant_id,
            "record": "/profiles/%s/sessions/%s.json" % (
                profile_name, session_id
            ),
            "live": True,
            "pid_domain": "linux:test-machine:test-pid-namespace",
            "process_group_id": process["process_group_id"],
            "process_group_member": True,
            "profile": profile_name,
            "config_dir": spec["config_dir"],
            "projects_store": transcript_store,
            "workspace": workspace,
            "path": "/profiles/%s/sessions/%s.json" % (
                profile_name, session_id
            ),
            "transcript_path": transcript["path"],
        }
        evidence.update({
            "profile": {
                "name": profile_name,
                "email": spec["account_email"],
                "family": spec["profile_family"],
                "status": "active",
                "authentication": {"type": "subscription_oauth"},
                "config_dir": spec["config_dir"],
            },
            "session_id": session_id,
            "workspace": workspace,
            "transcript_store": transcript_store,
            "transcript_project": workspace + "/project",
            "transcript": transcript,
            "holders": [holder],
            "unknown_holders": [],
            "ambiguous": False,
        })
        store.transcript_evidence[participant_id] = evidence
        store.transcript_bindings[(profile_name, session_id, workspace)] = (
            participant_id
        )
        refreshed_status = copy.deepcopy(opened)
        refreshed_status["evidence"].update({
            "active_turn": False,
            "turn_terminal": True,
            "drained": True,
            "participant_quiescent": True,
            "tools_quiescent": True,
            "quiescent": True,
            "tools": [],
            "uncertain_effects": [],
        })
        runtime.statuses[participant_id] = [refreshed_status]


def _new_worker_for_admission(
        store: MemoryStore, participant_id: str = "worker-new",
        session_id: str = WORKER_D_SESSION,
        worktree: str = "/trees/new") -> Tuple[Participant, Dict[str, Any]]:
    participant = _participant(
        participant_id,
        session_id,
        task_id="task-new",
        mailbox_id="mailbox-new",
        writer_claim=_claim(participant_id, worktree),
        model=SWAP_PROFILE["model"],
        permission_mode=SWAP_PROFILE["permission_mode"],
        fingerprint=SWAP_PROFILE["fingerprint"],
        metadata=_source_metadata(session_id, participant_id=participant_id),
    )
    _bind_source_transcript(store, participant)
    spec = copy.deepcopy(_start_specs()["worker-b"])
    spec.update({
        "participant_id": participant_id,
        "session_id": session_id,
        "session_name": _session_name(participant_id),
        "bound_lane": MANAGED_LANE,
        "fingerprint": _identity_fingerprint(participant_id, spec["fingerprint"]),
    })
    return participant, spec


def _run_add_worker_held(controller: ManagedController, request_id: str,
                         participant: Participant,
                         runner_spec: Mapping[str, Any],
                         generation: Any = 7):
    return asyncio.run(controller.add_worker_held(
        request_id, generation, participant, runner_spec
    ))


def _durable_mailbox_state(store: MemoryStore, message_id: str, state: str) -> None:
    """Inject only a transport boundary state; no runtime effect is faked."""
    record = copy.deepcopy(store.documents["controller.json"])
    for entry in record["mailboxes"]:
        if entry["message_id"] == message_id:
            entry["state"] = state
            if state != "acknowledged":
                entry["runtime_ack"] = None
            break
    else:
        raise AssertionError("mailbox message is absent from durable snapshot")
    store.write_json("controller.json", record)


def _start_statuses() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "coordinator": [_swap_status("coordinator", COORDINATOR_SESSION)],
        "worker-a": [_swap_status("worker-a", WORKER_A_SESSION)],
        "worker-b": [_swap_status("worker-b", WORKER_B_SESSION)],
    }


def _start_participants() -> Tuple[Participant, List[Participant]]:
    coordinator = _participant(
        "coordinator", COORDINATOR_SESSION, role="coordinator",
        parent_id=None, task_id="task-root", mailbox_id="mailbox-coordinator",
        read_only=True,
        model=SWAP_PROFILE["model"],
        permission_mode="dontAsk",
        fingerprint=SWAP_PROFILE["fingerprint"],
        metadata=_source_metadata(
            COORDINATOR_SESSION, participant_id="coordinator"
        ),
    )
    worker_a = _participant(
        "worker-a", WORKER_A_SESSION, task_id="task-a", mailbox_id="mailbox-a",
        writer_claim=_claim("worker-a", "/trees/a"),
        model=SWAP_PROFILE["model"],
        permission_mode=SWAP_PROFILE["permission_mode"],
        fingerprint=SWAP_PROFILE["fingerprint"],
        metadata=_source_metadata(WORKER_A_SESSION, participant_id="worker-a"),
    )
    worker_b = _participant(
        "worker-b", WORKER_B_SESSION, task_id="task-b", mailbox_id="mailbox-b",
        writer_claim=_claim("worker-b", "/trees/b"),
        model=SWAP_PROFILE["model"],
        permission_mode=SWAP_PROFILE["permission_mode"],
        fingerprint=SWAP_PROFILE["fingerprint"],
        metadata=_source_metadata(WORKER_B_SESSION, participant_id="worker-b"),
    )
    return coordinator, [worker_a, worker_b]


def _start_specs() -> Dict[str, Dict[str, Any]]:
    source_fingerprint = copy.deepcopy(SWAP_PROFILE["fingerprint"])
    source_fingerprint.update({
        "profile_name": "source-profile",
        "account_email": "source@example.invalid",
        "config_dir": "/managed/profiles/source",
    })
    result: Dict[str, Dict[str, Any]] = {}
    sessions = {
        "coordinator": COORDINATOR_SESSION,
        "worker-a": WORKER_A_SESSION,
        "worker-b": WORKER_B_SESSION,
    }
    for participant_id, session_id in sessions.items():
        session_name = _session_name(participant_id)
        result[participant_id] = {
            "participant_id": participant_id,
            "session_id": session_id,
            "session_name": session_name,
            "bound_lane": MANAGED_LANE,
            "mode": "resume",
            "profile_name": "source-profile",
            "profile_family": SWAP_PROFILE["family"],
            "account_email": "source@example.invalid",
            "config_dir": "/managed/profiles/source",
            "workspace": SWAP_PROFILE["workspace"],
            "transcript_store": SWAP_PROFILE["transcript_store"],
            "permission_mode": (
                "dontAsk" if participant_id == "coordinator"
                else SWAP_PROFILE["permission_mode"]
            ),
            "model": SWAP_PROFILE["model"],
            "fingerprint": _identity_fingerprint(participant_id, source_fingerprint),
        }
    return result


def _rollover_start_roster(
        store: MemoryStore,
) -> Tuple[Participant, List[Participant], Dict[str, Dict[str, Any]]]:
    """Build a fresh fixed-UUID roster without recycling old history."""
    definitions = (
        (
            "coordinator-next",
            ROLLOVER_COORDINATOR_SESSION,
            "coordinator",
            None,
            "task-root-next",
            "mailbox-coordinator-next",
            None,
            "coordinator",
        ),
        (
            "worker-next-a",
            ROLLOVER_WORKER_A_SESSION,
            "worker",
            "coordinator-next",
            "task-next-a",
            "mailbox-next-a",
            "/trees/next-a",
            "worker-a",
        ),
        (
            "worker-next-b",
            ROLLOVER_WORKER_B_SESSION,
            "worker",
            "coordinator-next",
            "task-next-b",
            "mailbox-next-b",
            "/trees/next-b",
            "worker-b",
        ),
    )
    base_specs = _start_specs()
    participants: List[Participant] = []
    specs: Dict[str, Dict[str, Any]] = {}
    for (
        participant_id,
        session_id,
        role,
        parent_id,
        task_id,
        mailbox_id,
        worktree,
        base_id,
    ) in definitions:
        participant = _participant(
            participant_id,
            session_id,
            role=role,
            parent_id=parent_id,
            task_id=task_id,
            mailbox_id=mailbox_id,
            read_only=role == "coordinator",
            writer_claim=(
                None if worktree is None else _claim(participant_id, worktree)
            ),
            model=SWAP_PROFILE["model"],
            permission_mode=(
                "dontAsk" if role == "coordinator"
                else SWAP_PROFILE["permission_mode"]
            ),
            fingerprint=SWAP_PROFILE["fingerprint"],
            metadata=_source_metadata(session_id, participant_id=participant_id),
        )
        _bind_source_transcript(store, participant)
        participants.append(participant)
        spec = copy.deepcopy(base_specs[base_id])
        spec.update({
            "participant_id": participant_id,
            "session_id": session_id,
            "session_name": _session_name(participant_id),
            "bound_lane": MANAGED_LANE,
            "fingerprint": _identity_fingerprint(
                participant_id, spec["fingerprint"]
            ),
        })
        specs[participant_id] = spec
    return participants[0], participants[1:], specs


def _start_controller(*, runtime: StartRuntime):
    controller, store = _controller(runtime=runtime)
    runtime.controller = controller
    coordinator, workers = _start_participants()
    for participant in [coordinator] + workers:
        _bind_source_transcript(store, participant)
    return controller, store, coordinator, workers, _start_specs()


def _native_start_definitions() -> Dict[str, Dict[str, Any]]:
    """Trusted native definitions supplied by the internal startup seam."""
    return {
        "writer": {
            "model": "configured-model",
            "effort": "high",
            "tools": ["Read", "Write"],
            "prompt": "synthetic definition prompt is not authority",
        },
    }


def _native_start_participant(
        *, participant_id: str = "coordinator",
        session_id: str = COORDINATOR_SESSION,
        metadata: Optional[Dict[str, Any]] = None,
) -> Participant:
    participant = _participant(
        participant_id,
        session_id,
        role="coordinator",
        parent_id=None,
        task_id="task-root-" + participant_id,
        mailbox_id="mailbox-" + participant_id,
        read_only=True,
        model=SWAP_PROFILE["model"],
        permission_mode="dontAsk",
        fingerprint=SWAP_PROFILE["fingerprint"],
        metadata=metadata or _source_metadata(
            session_id, participant_id=participant_id,
        ),
    )
    return participant


def _native_start_spec(
        participant: Participant, *, lineage_id: str = NATIVE_START_LINEAGE_ID,
        lineage_generation: int = 1,
        runner_incarnation: str = NATIVE_START_RUNNER,
        definitions: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    spec = copy.deepcopy(_start_specs()["coordinator"])
    spec.update({
        "participant_id": participant.participant_id,
        "session_id": participant.session_id,
        "session_name": participant.session_name,
        "bound_lane": participant.bound_lane,
    })
    spec["fingerprint"]["session_name"] = participant.session_name
    spec["fingerprint"]["bound_lane"] = participant.bound_lane
    spec["fingerprint"]["native_config"] = {
        "lineage_id": lineage_id,
        "lineage_generation": lineage_generation,
        "runner_incarnation": runner_incarnation,
        "trusted_definitions": copy.deepcopy(
            _native_start_definitions() if definitions is None else definitions
        ),
    }
    return spec


def _native_start_controller(
        *, runtime: Optional[StartRuntime] = None,
        participant_id: str = "coordinator",
        session_id: str = COORDINATOR_SESSION,
        lineage_id: str = NATIVE_START_LINEAGE_ID,
        generation: int = 7,
):
    selected_runtime = StartRuntime() if runtime is None else runtime
    store = NativeStartStore(generation=generation)
    controller = ManagedController(
        store,
        runtime=selected_runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    selected_runtime.controller = controller
    coordinator = _native_start_participant(
        participant_id=participant_id, session_id=session_id,
    )
    _bind_source_transcript(store, coordinator)
    return (
        controller,
        store,
        coordinator,
        [],
        {participant_id: _native_start_spec(
            coordinator, lineage_id=lineage_id,
        )},
    )


def _run_native_start(
        controller: ManagedController, *, request_id: str,
        coordinator: Participant, runner_spec: Mapping[str, Any],
        generation: int = 7,
):
    return _run_start(
        controller,
        request_id=request_id,
        generation=generation,
        coordinator=coordinator,
        workers=[],
        runner_specs={coordinator.participant_id: copy.deepcopy(runner_spec)},
    )


async def _start(controller: ManagedController, request_id: str,
                 generation: Any, coordinator: Participant,
                 workers: List[Participant],
                 runner_specs: Dict[str, Dict[str, Any]]):
    return await controller.start(
        request_id=request_id,
        generation=generation,
        coordinator=coordinator,
        participants=workers,
        runner_specs=runner_specs,
    )


def _run_start(controller: ManagedController, request_id: str = "start-request",
               generation: Any = 7,
               coordinator: Optional[Participant] = None,
               workers: Optional[List[Participant]] = None,
               runner_specs: Optional[Dict[str, Dict[str, Any]]] = None):
    if coordinator is None or workers is None or runner_specs is None:
        default_coordinator, default_workers = _start_participants()
        coordinator = default_coordinator if coordinator is None else coordinator
        workers = default_workers if workers is None else workers
        runner_specs = _start_specs() if runner_specs is None else runner_specs
    return asyncio.run(_start(
        controller, request_id, generation, coordinator, workers, runner_specs
    ))


async def _swap(controller: ManagedController, request_id: str = "swap-request",
                generation: Any = 7, profile: Optional[Dict[str, Any]] = None):
    """Call the T011 controller operation with one explicit target profile."""
    return await controller.swap(request_id, generation,
                                 SWAP_PROFILE if profile is None else profile)


def _run_swap(controller: ManagedController, request_id: str = "swap-request",
              generation: Any = 7,
              profile: Optional[Dict[str, Any]] = None):
    return asyncio.run(_swap(controller, request_id, generation, profile))


def _run_release(controller: ManagedController, operation_id: str,
                 generation: Any = 7):
    return asyncio.run(controller.release(operation_id, generation))


def _run_recover(controller: ManagedController, operation_id: str,
                 generation: Any, evidence: Dict[str, Any]):
    """Reconcile with controller-internal stage evidence, never a public body."""
    return asyncio.run(controller.recover(operation_id, generation, evidence))


def _run_handoff(controller: ManagedController, request_id: str,
                 checkpoint: Any, generation: Any = 7):
    return controller.handoff(request_id, generation, checkpoint)


def _run_ctx(controller: ManagedController, request_id: str,
             checkpoint: Any, worker_policy: str,
             worker_mapping: Any = None, generation: Any = 7):
    return asyncio.run(controller.ctx(
        request_id,
        generation,
        checkpoint,
        worker_policy,
        worker_mapping,
    ))


def _prepare_released_swap(controller: ManagedController, store: MemoryStore,
                           runtime: SwapRuntime,
                           request_id: str = "swap-request") -> Operation:
    """Use the public swap/release APIs to establish a released roster."""
    operation = _run_swap(controller, request_id=request_id)
    record = _operation_record(store, request_id)
    runner_instances = record["metadata"]["runner_instances"]
    sessions = {
        "coordinator": COORDINATOR_SESSION,
        "worker-a": WORKER_A_SESSION,
        "worker-b": WORKER_B_SESSION,
    }
    for participant_id, session_id in sessions.items():
        status = _swap_open_result(
            participant_id,
            session_id,
            runner_instance_id=runner_instances[participant_id],
        )
        # The exact runner-evidence contract names the participant/tool
        # quiescence fields above.  These additional internal observations are
        # supplied only to exercise the retained-worker ctx gate.
        status["evidence"].update({"quiescent": True, "tools": []})
        runtime.statuses[participant_id] = [status]
    return _run_release(controller, _operation_id(operation), generation=7)


def _roster(status: Any) -> List[Any]:
    return list(status["participants"])


def _mailboxes(status: Any) -> List[Any]:
    return list(status["mailboxes"])


def _mailbox(status: Any, message_id: str) -> Any:
    for entry in _mailboxes(status):
        if _value(entry, "message_id") == message_id:
            return entry
    raise AssertionError("message is not present in controller status")


def _assert_error(exc: pytest.ExceptionInfo, code: str):
    assert isinstance(exc.value, ControllerError)
    assert exc.value.code == code


def _operation_id(operation: Any) -> str:
    return _value(operation, "operation_id")


def _durable_operation_phase(
        controller: ManagedController, operation: Operation, phase: str,
        *, release_count: Optional[int] = None) -> Operation:
    store = controller.store
    record = copy.deepcopy(store.documents["controller.json"])
    for raw in record["operations"]:
        if raw["operation_id"] == operation.operation_id:
            raw["phase"] = phase
            if release_count is not None:
                raw["release_count"] = release_count
            store.write_json("controller.json", record)
            return Operation.from_dict(raw)
    raise AssertionError("operation was not durably persisted")


def _release_state(controller: ManagedController, operation: Operation) -> Operation:
    """Inject the explicit release result owned by the later release task.

    T007 owns the dispatch gate, while T011/T012 own the public release
    orchestration.  Marking this exact durable model state lets these tests
    exercise post-release dispatch without inventing a second release API.
    """
    assert isinstance(operation, Operation)
    released = _durable_operation_phase(
        controller, operation, "released", release_count=1
    )
    released.metadata["released_generation"] = operation.generation
    record = copy.deepcopy(controller.store.documents["controller.json"])
    for raw in record["operations"]:
        if raw["operation_id"] == operation.operation_id:
            raw.setdefault("metadata", {})["released_generation"] = operation.generation
            controller.store.write_json("controller.json", record)
            return released
    raise AssertionError("operation was not durably persisted")


def _dispatch(controller: ManagedController, operation: Any) -> Any:
    return asyncio.run(controller.dispatch_next(_operation_id(operation)))


def test_managed_controller_requires_a_state_store():
    with pytest.raises(ControllerError) as raised:
        ManagedController(None)
    _assert_error(raised, "unsupported")


def test_malformed_durable_controller_record_fails_closed():
    store = MemoryStore()
    store.documents["controller.json"] = {
        "schema": 1,
        "generation": 7,
        "coordinator_id": "coordinator",
        "participants": [{"participant_id": "missing-session-and-mailbox"}],
        "mailboxes": [],
        "operations": [],
        "requests": {},
    }
    with pytest.raises(ControllerError) as raised:
        ManagedController(store)
    _assert_error(raised, "schema-mismatch")


def test_controller_transitions_are_atomic_persisted_and_reloadable():
    controller, store, _ = _enrolled()
    worker = _participant("worker-persisted", WORKER_A_SESSION,
                          task_id="task-persisted", mailbox_id="mailbox-persisted",
                          read_only=True,
                          permission_mode="dontAsk",
                          metadata=copy.deepcopy(READ_ONLY_METADATA))
    controller.add_worker(worker)
    operation = controller.begin_operation("operation-persisted", "swap", 7)
    entry = controller.submit("request-persisted", "worker-persisted", "payload",
                              sender_id="coordinator", task_id="task-persisted")
    controller.fence(_operation_id(operation))

    record = store.documents["controller.json"]
    assert isinstance(record, dict)
    assert set(record) >= {
        "schema_version", "architecture", "record_kind", "generation",
        "coordinator_id", "active_operation_id", "participants", "mailboxes",
        "operations", "requests",
    }
    assert len(store.write_calls) >= 5
    assert store.journal
    # Every durable snapshot is a complete controller record, not a partial
    # participant/mailbox write that a reload could observe.
    for _, snapshot in store.write_calls:
        assert set(snapshot) >= {
            "schema_version", "architecture", "record_kind", "generation",
            "coordinator_id", "active_operation_id", "participants", "mailboxes",
            "operations", "requests",
        }
    restored = ManagedController(store, clock=lambda: 1000.0)
    assert restored.status() == controller.status()
    assert _mailbox(restored.status(), _value(entry, "message_id"))


def test_read_only_coordinator_is_claimless_but_writable_coordinator_claims():
    controller, store = _controller()
    read_only = _participant(
        "coordinator", COORDINATOR_SESSION, role="coordinator",
        parent_id=None, task_id="task-root", mailbox_id="mailbox-coordinator",
        read_only=True, permission_mode="dontAsk",
        metadata=copy.deepcopy(READ_ONLY_METADATA),
    )
    controller.enroll(7, read_only)
    assert store.claim_calls == []

    writable_controller, writable_store = _controller()
    writable = _participant(
        "coordinator", COORDINATOR_SESSION, role="coordinator",
        parent_id=None, task_id="task-root", mailbox_id="mailbox-coordinator",
        read_only=False,
        writer_claim=_claim("coordinator", "/trees/coordinator"),
    )
    writable_controller.enroll(7, writable)
    assert [call[0] for call in writable_store.claim_calls] == ["coordinator"]
    assert writable_store.claim_calls[0][1] == "/trees/coordinator"


@pytest.mark.parametrize(
    ("metadata", "expected_code"),
    (
        ({"read_only_enforced": True,
          "tools": ["Read", "Write", "Edit", "Bash"]},
         "permission-mismatch"),
        ({"read_only_enforced": True}, "permission-mismatch"),
        ({**READ_ONLY_METADATA, "mcp_servers": ["unknown-mcp-capability"]},
         "unsupported"),
    ),
)
def test_dontask_or_unknown_tools_cannot_enroll_claimless_participant(
        metadata: Dict[str, Any], expected_code: str):
    controller, store = _controller()
    candidate = _participant(
        "coordinator", COORDINATOR_SESSION, role="coordinator",
        parent_id=None, task_id="task-root", mailbox_id="mailbox-coordinator",
        read_only=True, permission_mode="dontAsk",
        metadata=copy.deepcopy(metadata),
    )
    with pytest.raises(ControllerError) as raised:
        controller.enroll(7, candidate)
    _assert_error(raised, expected_code)
    assert controller.status()["participants"] == []
    assert store.claim_calls == []


def test_claimless_enrollment_requires_explicit_enforced_readonly_allowlist():
    controller, store = _controller()
    candidate = _participant(
        "coordinator", COORDINATOR_SESSION, role="coordinator",
        parent_id=None, task_id="task-root", mailbox_id="mailbox-coordinator",
        read_only=True, permission_mode="dontAsk",
        metadata=copy.deepcopy(READ_ONLY_METADATA),
    )
    enrolled = controller.enroll(7, candidate)
    assert _value(enrolled, "participant_id") == "coordinator"
    assert store.claim_calls == []


def test_coordinator_requires_an_explicit_root_task_and_mailbox_identity():
    controller, store = _controller()
    coordinator = _participant(
        "coordinator", COORDINATOR_SESSION, role="coordinator",
        parent_id=None, task_id=None, mailbox_id="mailbox-coordinator",
        read_only=True,
    )
    with pytest.raises(ControllerError) as raised:
        controller.enroll(7, coordinator)
    _assert_error(raised, "invalid")
    assert controller.status()["participants"] == []
    assert store.claim_calls == []


def test_enrollment_has_one_read_only_coordinator_and_explicit_workers():
    controller, store, coordinator = _enrolled()
    worker_a = _participant("worker-a", WORKER_A_SESSION, task_id="task-a",
                            mailbox_id="mailbox-a",
                            writer_claim=_claim("worker-a", "/trees/a"))
    worker_b = _participant("worker-b", WORKER_B_SESSION, task_id="task-b",
                            mailbox_id="mailbox-b",
                            writer_claim=_claim("worker-b", "/trees/b"))

    controller.add_worker(worker_a)
    controller.add_worker(worker_b)
    status = controller.status()
    roster = _roster(status)
    assert sum(_value(item, "role") == "coordinator" for item in roster) == 1
    assert sum(_value(item, "role") == "worker" for item in roster) == 2
    assert _value(coordinator, "read_only") is True
    assert { _value(item, "session_id")
             for item in roster } == {
                 COORDINATOR_SESSION, WORKER_A_SESSION, WORKER_B_SESSION,
             }
    assert len({_value(item, "session_id")
                for item in roster}) == 3
    enrolled_coordinator = next(
        item for item in roster if _value(item, "participant_id") == "coordinator"
    )
    assert _value(enrolled_coordinator, "task_id") == "task-root"
    assert _value(enrolled_coordinator, "mailbox_id") == "mailbox-coordinator"
    for worker in (worker_a, worker_b):
        matching = next(item for item in roster
                        if _value(item, "participant_id") ==
                        _value(worker, "participant_id"))
        assert _value(matching, "parent_id") == "coordinator"
        assert _value(matching, "task_id")
        assert _value(matching, "mailbox_id")
    assert [call[0] for call in store.claim_calls] == ["worker-a", "worker-b"]


def test_duplicate_coordinator_uuid_or_role_is_refused_before_mutation():
    controller, store, _ = _enrolled()
    duplicate = _participant("second-coordinator", COORDINATOR_SESSION,
                             role="coordinator", parent_id=None,
                             task_id="task-root-duplicate", mailbox_id="mailbox-second",
                             read_only=True, permission_mode="dontAsk",
                             metadata=copy.deepcopy(READ_ONLY_METADATA))
    before = copy.deepcopy(controller.status())
    with pytest.raises(ControllerError) as raised:
        controller.add_worker(duplicate)
    _assert_error(raised, "invalid")
    assert controller.status() == before
    assert store.claim_calls == []

    controller.add_worker(_participant(
        "worker-original", WORKER_A_SESSION, read_only=True,
        permission_mode="dontAsk", metadata=copy.deepcopy(READ_ONLY_METADATA)
    ))
    duplicate_worker = _participant("worker-duplicate", WORKER_A_SESSION,
                                    read_only=True, permission_mode="dontAsk",
                                    metadata=copy.deepcopy(READ_ONLY_METADATA))
    with pytest.raises(ControllerError) as raised:
        controller.add_worker(duplicate_worker)
    _assert_error(raised, "busy")
    assert store.claim_calls == []


@pytest.mark.parametrize(
    ("semantic", "value"),
    (("kind", "native-agent"), ("kind", "native-task"),
     ("kind", "native-team"), ("background", True), ("detached", True)),
)
def test_native_and_unmanaged_participants_are_rejected_before_admission(
        semantic: str, value: Any):
    controller, store, _ = _enrolled()
    candidate = _participant("bad-worker", WORKER_C_SESSION,
                             writer_claim=_claim("bad-worker", "/trees/bad"))
    candidate = _mark(candidate, semantic, value)
    with pytest.raises(ControllerError) as raised:
        controller.add_worker(candidate)
    _assert_error(raised, "unsupported")
    assert not any(_value(item, "participant_id") == "bad-worker"
                   for item in _roster(controller.status()))
    assert store.claim_calls == []


@pytest.mark.parametrize("field", ["parent_id", "task_id"])
def test_worker_admission_requires_explicit_parent_task_and_mailbox(field: str):
    controller, store, _ = _enrolled()
    values = {
        "parent_id": "coordinator",
        "task_id": "task-required",
        "mailbox_id": "mailbox-required",
    }
    values[field] = None
    candidate = _participant("missing-link", WORKER_C_SESSION, **values,
                             writer_claim=_claim("missing-link", "/trees/c"))
    with pytest.raises(ControllerError) as raised:
        controller.add_worker(candidate)
    _assert_error(raised, "invalid")
    assert store.claim_calls == []


def test_participant_constructor_requires_an_explicit_mailbox_identity():
    with pytest.raises(ControllerError) as raised:
        _participant("missing-mailbox", WORKER_C_SESSION, mailbox_id=None)
    _assert_error(raised, "invalid")


def test_worker_admission_cannot_bypass_state_global_writer_claim_refusal():
    controller, store, _ = _enrolled()
    store.claim_error = ControllerError(
        "ownership-conflict", "canonical worktree is held by another lane"
    )
    candidate = _participant(
        "worker-conflict", WORKER_C_SESSION, task_id="task-conflict",
        mailbox_id="mailbox-conflict",
        writer_claim=_claim("worker-conflict", "/trees/shared"),
    )
    before = copy.deepcopy(controller.status())
    with pytest.raises(ControllerError) as raised:
        controller.add_worker(candidate)
    _assert_error(raised, "ownership-conflict")
    assert controller.status() == before
    assert store.claim_calls == [("worker-conflict", "/trees/shared", None)]


def test_submit_request_id_is_content_deduplicated_and_conflict_refused():
    controller, store, _ = _enrolled()
    controller.add_worker(_participant("worker-a", WORKER_A_SESSION,
                                       task_id="task-a", mailbox_id="mailbox-a",
                                       state="active",
                                       read_only=True,
                                       permission_mode="dontAsk",
                                       metadata=copy.deepcopy(READ_ONLY_METADATA)))
    first = controller.submit("request-1", "worker-a", "payload-1",
                              sender_id="coordinator", task_id="task-a")
    same = controller.submit("request-1", "worker-a", "payload-1",
                             sender_id="coordinator", task_id="task-a")
    assert _value(first, "message_id") == _value(same, "message_id")
    messages = [entry for entry in _mailboxes(controller.status())
                if _value(entry, "message_id") == _value(first, "message_id")]
    assert len(messages) == 1
    with pytest.raises(ControllerError) as raised:
        controller.submit("request-1", "worker-a", "different-payload",
                          sender_id="coordinator", task_id="task-a")
    _assert_error(raised, "invalid")
    assert len([entry for entry in _mailboxes(controller.status())
                if _value(entry, "message_id") == _value(first, "message_id")]) == 1


def test_submit_rejects_stale_expected_generation_without_mailbox_or_store_mutation():
    controller, store, _ = _enrolled()
    controller.add_worker(_participant(
        "worker-a", WORKER_A_SESSION, task_id="task-a", mailbox_id="mailbox-a",
        read_only=True, permission_mode="dontAsk",
        metadata=copy.deepcopy(READ_ONLY_METADATA),
    ))
    before_documents = copy.deepcopy(store.documents)
    before_journal = copy.deepcopy(store.journal)
    before_writes = copy.deepcopy(store.write_calls)

    with pytest.raises(ControllerError) as raised:
        controller.submit(
            "stale-submit", "worker-a", "payload",
            sender_id="user", task_id="task-a", generation=6,
        )
    _assert_error(raised, "stale-generation")
    assert store.documents == before_documents
    assert store.journal == before_journal
    assert store.write_calls == before_writes
    assert _mailboxes(controller.status()) == []


def test_operation_request_id_is_content_deduplicated_and_generation_bound():
    controller, _, _ = _enrolled()
    first = controller.begin_operation("operation-1", "swap", 7)
    same = controller.begin_operation("operation-1", "swap", 7)
    assert _value(first, "operation_id") == _value(same, "operation_id")
    with pytest.raises(ControllerError) as raised:
        controller.begin_operation("operation-1", "ctx", 7)
    _assert_error(raised, "invalid")

    other, _, _ = _enrolled()
    with pytest.raises(ControllerError) as raised:
        other.begin_operation("stale-operation", "swap", 6)
    _assert_error(raised, "stale-generation")


def test_only_one_operation_can_serialize_a_generation():
    controller, _, _ = _enrolled()
    first = controller.begin_operation("operation-a", "swap", 7)
    with pytest.raises(ControllerError) as raised:
        controller.begin_operation("operation-b", "ctx", 7)
    _assert_error(raised, "busy")
    with pytest.raises(ControllerError) as raised:
        controller.fence("not-the-active-operation")
    _assert_error(raised, "unknown")
    assert _value(controller.status(), "operation_id",
                  _value(_value(controller.status(), "operation"),
                         "operation_id")) == _value(first, "operation_id")


def test_fence_seals_admission_and_mail_without_silent_drop():
    controller, store, _ = _enrolled()
    controller.add_worker(_participant("worker-a", WORKER_A_SESSION,
                                       task_id="task-a", mailbox_id="mailbox-a",
                                       read_only=True,
                                       permission_mode="dontAsk",
                                       metadata=copy.deepcopy(READ_ONLY_METADATA)))
    initial = controller.submit("request-before-fence", "worker-a", "payload",
                                sender_id="user", task_id="task-a")
    operation = controller.begin_operation("operation-fence", "swap", 7)
    controller.fence(_value(operation, "operation_id"))
    fenced = _mailbox(controller.status(), _value(initial, "message_id"))
    assert _value(fenced, "state") == "fenced"
    late_worker = _participant("worker-late", WORKER_C_SESSION,
                               writer_claim=_claim("worker-late", "/trees/late"))
    with pytest.raises(ControllerError) as raised:
        controller.add_worker(late_worker)
    _assert_error(raised, "busy")
    assert store.claim_calls == []
    late = controller.submit("request-after-fence", "worker-a", "late-payload",
                             sender_id="user", task_id="task-a")
    assert _value(late, "state") == "fenced"
    assert _value(_mailbox(controller.status(), _value(late, "message_id")),
                  "state") == "fenced"
    assert not getattr(controller, "runtime", None)


def _dispatch_fixture(*, failure: Optional[str] = None):
    runtime = FakeRuntime(failure=failure)
    controller, store, _ = _enrolled(runtime=runtime)
    controller.payload_resolver = lambda ref: ref
    controller.add_worker(_participant("worker-a", WORKER_A_SESSION,
                                       task_id="task-a", mailbox_id="mailbox-a",
                                       state="active",
                                       read_only=True,
                                       permission_mode="dontAsk",
                                       metadata=copy.deepcopy(READ_ONLY_METADATA)))
    entry = controller.submit("dispatch-request", "worker-a", "payload",
                              sender_id="coordinator", task_id="task-a")
    operation = controller.begin_operation("dispatch-operation", "swap", 7)
    return controller, store, runtime, entry, operation


def test_dispatch_is_blocked_before_matching_explicit_release():
    controller, _, _, _, operation = _dispatch_fixture()
    with pytest.raises(ControllerError) as raised:
        _dispatch(controller, operation)
    _assert_error(raised, "busy")

    controller, _, _, _, operation = _dispatch_fixture()
    controller.fence(_operation_id(operation))
    with pytest.raises(ControllerError) as raised:
        _dispatch(controller, operation)
    _assert_error(raised, "busy")

    controller, _, _, _, operation = _dispatch_fixture()
    operation = _durable_operation_phase(controller, operation, "ready-held")
    with pytest.raises(ControllerError) as raised:
        _dispatch(controller, operation)
    _assert_error(raised, "busy")


def test_dispatch_persists_intent_before_runtime_and_matching_ack_closes_entry():
    controller, _, runtime, entry, operation = _dispatch_fixture()
    operation = _release_state(controller, operation)
    message_id = _value(entry, "message_id")
    dispatched = _dispatch(controller, operation)
    assert _value(dispatched, "message_id") == message_id
    mailbox = _mailbox(controller.status(), message_id)
    assert _value(mailbox, "state") == "acknowledged"
    assert len(runtime.calls) == 1
    assert runtime.calls == [("worker-a", message_id, "payload")]
    ack = controller.acknowledge(message_id, {
        "message_id": message_id,
        "accepted": True,
        "ack_kind": "accepted-send",
        "runtime_id": "runtime-ack-1",
    })
    assert _value(ack, "message_id", message_id) == message_id
    assert _value(_mailbox(controller.status(), message_id), "state") == "acknowledged"
    # A duplicate acknowledgement is idempotent for the same message and does
    # not cause a second runtime send.
    controller.acknowledge(message_id, {
        "message_id": message_id,
        "accepted": True,
        "ack_kind": "accepted-send",
        "runtime_id": "runtime-ack-1",
    })
    assert len(runtime.calls) == 1


def test_ack_for_another_message_is_refused_without_advancing_mail():
    controller, _, _, entry, operation = _dispatch_fixture()
    operation = _release_state(controller, operation)
    message_id = _value(entry, "message_id")
    _dispatch(controller, operation)
    with pytest.raises(ControllerError) as raised:
        controller.acknowledge(message_id, {
            "message_id": "wrong-message",
            "accepted": True,
        })
    _assert_error(raised, "invalid")
    assert _value(_mailbox(controller.status(), message_id), "state") == "acknowledged"


def test_crash_before_send_requeues_only_with_affirmative_no_send_proof():
    controller, _, runtime, entry, operation = _dispatch_fixture(
        failure="before-send")
    operation = _release_state(controller, operation)
    message_id = _value(entry, "message_id")
    with pytest.raises(ControllerError) as raised:
        _dispatch(controller, operation)
    _assert_error(raised, "uncertain-effect")
    # A crash leaves a durable intent (or an explicitly uncertain entry), but
    # recovery may return it to queued only when the transport proves no send.
    controller.recover_dispatch(message_id,
                                transport_proof={"send_occurred": False,
                                                 "authoritative": True})
    assert _value(_mailbox(controller.status(), message_id), "state") == "queued"
    assert len(runtime.calls) == 0


def test_crash_after_send_without_ack_is_uncertain_and_never_resent():
    controller, _, runtime, entry, operation = _dispatch_fixture(
        failure="after-send")
    operation = _release_state(controller, operation)
    message_id = _value(entry, "message_id")
    with pytest.raises(ControllerError) as raised:
        _dispatch(controller, operation)
    _assert_error(raised, "uncertain-effect")
    controller.recover_dispatch(message_id)
    assert _value(_mailbox(controller.status(), message_id), "state") == "uncertain"
    calls = len(runtime.calls)
    with pytest.raises(ControllerError) as raised:
        _dispatch(controller, operation)
    _assert_error(raised, "uncertain-effect")
    assert len(runtime.calls) == calls
    # A proof that says the send happened cannot downgrade uncertainty back to
    # queued; only affirmative proof of *no* send has that authority.
    controller.recover_dispatch(message_id,
                                transport_proof={"sent": True,
                                                 "authoritative": True})
    assert _value(_mailbox(controller.status(), message_id), "state") == "uncertain"


def test_negative_or_non_authoritative_transport_proof_cannot_requeue_intent():
    controller, _, runtime, entry, operation = _dispatch_fixture(
        failure="before-send")
    operation = _release_state(controller, operation)
    message_id = _value(entry, "message_id")
    with pytest.raises(ControllerError) as raised:
        _dispatch(controller, operation)
    _assert_error(raised, "uncertain-effect")
    controller.recover_dispatch(message_id, {
        "sent": False,
        "authoritative": True,
    })
    assert _value(_mailbox(controller.status(), message_id), "state") == "uncertain"
    assert len(runtime.calls) == 0


def test_active_or_ambiguous_worker_cannot_complete_or_release_writer_claim():
    controller, store, _ = _enrolled()
    active = _participant("worker-active", WORKER_A_SESSION, state="active",
                          writer_claim=_claim("worker-active", "/trees/active"))
    controller.add_worker(active)
    with pytest.raises(ControllerError) as raised:
        controller.complete_worker("worker-active", {
            "participant_id": "worker-active",
            "generation": 7,
            "stopped": False,
            "tools_quiescent": False,
            "process_group": "owned-and-drained",
            "authoritative": True,
        })
    _assert_error(raised, "uncertain-effect")
    assert store.release_calls == []
    assert ("worker-active", "/trees/active") in store.claims

    with pytest.raises(ControllerError) as raised:
        controller.complete_worker("worker-active", {
            "participant_id": "worker-active",
            "generation": 7,
            "status": "stopped",
            "quiescent": True,
            "tools_quiescent": True,
            "participant_quiescent": True,
            "live_participant": True,
            "process_group": "owned-and-drained",
            "authoritative": True,
        })
    _assert_error(raised, "uncertain-effect")
    assert store.release_calls == []
    assert ("worker-active", "/trees/active") in store.claims


def test_authoritative_completion_releases_claim_once():
    controller, store, _ = _enrolled()
    worker = _participant("worker-done", WORKER_B_SESSION,
                          writer_claim=_claim("worker-done", "/trees/done"))
    controller.add_worker(worker)
    completed = controller.complete_worker("worker-done", {
        "participant_id": "worker-done",
        "generation": 7,
        "status": "stopped",
        "quiescent": True,
        "participant_quiescent": True,
        "tools_quiescent": True,
        "tool_evidence": {"participant_id": "worker-done", "generation": 7},
        "process_group": "owned-and-drained",
        "authoritative": True,
    })
    assert _value(completed, "state") == "completed"
    assert store.release_calls == [("worker-done", "/trees/done")]
    repeated = controller.complete_worker("worker-done", {
        "participant_id": "worker-done",
        "generation": 7,
        "status": "stopped",
        "quiescent": True,
        "participant_quiescent": True,
        "tools_quiescent": True,
        "tool_evidence": {"participant_id": "worker-done", "generation": 7},
        "process_group": "owned-and-drained",
        "authoritative": True,
    })
    assert _value(repeated, "state") == "completed"
    assert store.release_calls == [("worker-done", "/trees/done")]


def test_completion_fence_blocks_concurrent_dispatch_pump_without_a_new_send():
    runtime = CompletionRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    released = _prepare_released_swap(controller, store, runtime)
    operation_id = _operation_id(released)
    entry = controller.submit(
        "completion-race-mail", "worker-a", "payload://completion-race",
        sender_id="user", task_id="task-a",
    )
    message_id = _value(entry, "message_id")
    calls_before = copy.deepcopy(runtime.calls)
    runtime.completion_status_started = asyncio.Event()
    runtime.allow_completion_status = asyncio.Event()

    async def race():
        completion = asyncio.create_task(
            controller.complete_worker_runtime("worker-a", 7)
        )
        await asyncio.wait_for(runtime.completion_status_started.wait(), 1)
        assert controller.dispatch_candidates(operation_id) == []
        dispatched = await controller.dispatch_next(operation_id)
        assert dispatched is None
        assert runtime.sent == []
        assert _value(_mailbox(controller.status(), message_id), "state") == "queued"
        runtime.allow_completion_status.set()
        return await completion

    completed = asyncio.run(race())
    assert _value(completed, "participant_id") == "worker-a"
    assert _value(completed, "state") == "completed"
    assert runtime.sent == []
    assert store.release_calls.count(("worker-a", "/trees/a")) == 1
    assert runtime.calls[:len(calls_before)] == calls_before
    assert [call for call in runtime.calls[len(calls_before):]
            if call[0] == "send"] == []


def test_active_worker_completion_refuses_without_interrupt_or_claim_release():
    runtime = CompletionRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    released = _prepare_released_swap(controller, store, runtime)
    operation_id = _operation_id(released)
    operation_record = _operation_record(store, "swap-request")
    runner_instance_id = operation_record["metadata"]["runner_instances"]["worker-a"]
    runtime.statuses["worker-a"] = [_completion_status(
        "worker-a", WORKER_A_SESSION, runner_instance_id,
        terminal=False,
        drained=False,
        participant_quiescent=False,
        tools_quiescent=False,
        active_turn=True,
        uncertain_effects=["turn:worker-a"],
    )]
    calls_before = copy.deepcopy(runtime.calls)
    shutdowns_before = copy.deepcopy(runtime.shutdowns)
    interrupted_before = copy.deepcopy(runtime.interrupted)

    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.complete_worker_runtime("worker-a", 7))
    _assert_error(raised, "uncertain-effect")
    assert runtime.interrupted == interrupted_before
    assert runtime.shutdowns == shutdowns_before
    assert runtime.calls == calls_before + [("status", "worker-a")]
    assert ("worker-a", "/trees/a") in store.claims
    participant = _active_participant(controller.status(), "worker-a")
    assert participant["state"] == "active"
    intent = participant["metadata"]["completion_intent"]
    assert intent["state"] == "indeterminate"
    assert intent["generation"] == 7
    assert intent["runner_instance_id"] == runner_instance_id
    assert operation_id == _operation_id(controller.status()["operation"])


def test_uncertain_worker_completion_retry_stays_held_without_replaying_shutdown():
    runtime = CompletionRuntime(
        _successful_swap_statuses()
    )
    controller, store, _ = _swap_roster(runtime)
    released = _prepare_released_swap(controller, store, runtime)
    runtime.shutdown_failure = "worker-a"
    operation_id = _operation_id(released)
    shutdowns_before = runtime.shutdowns.count("worker-a")
    operation_record = _operation_record(store, "swap-request")
    runner_instance_id = operation_record["metadata"]["runner_instances"]["worker-a"]
    runtime.statuses["worker-a"] = [_completion_status(
        "worker-a", WORKER_A_SESSION, runner_instance_id
    )]

    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.complete_worker_runtime("worker-a", 7))
    _assert_error(raised, "uncertain-effect")
    calls_after_failure = copy.deepcopy(runtime.calls)
    assert ("worker-a", "/trees/a") in store.claims
    assert _active_participant(controller.status(), "worker-a")["metadata"][
        "completion_intent"
    ]["state"] == "indeterminate"

    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.complete_worker_runtime("worker-a", 7))
    _assert_error(raised, "uncertain-effect")
    assert runtime.calls == calls_after_failure
    assert runtime.shutdowns.count("worker-a") == shutdowns_before + 1
    assert ("worker-a", "/trees/a") in store.claims
    assert operation_id == _operation_id(controller.status()["operation"])


@pytest.mark.parametrize("mode", ["shutdown", "unenroll", "ctx"])
def test_recovery_mode_is_fenced_and_never_falls_back_to_swap_or_open(mode: str):
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    operation = controller.begin_operation(
        "mode-aware-%s" % mode, mode, 7,
        request_content={"mode": mode, "recovery": True},
    )
    controller.fence(_operation_id(operation))
    calls_before = copy.deepcopy(runtime.calls)
    participant_records = {
        _value(item, "participant_id"): {}
        for item in controller.status()["participants"]
    }

    with pytest.raises(ControllerError) as raised:
        _run_recover(
            controller,
            _operation_id(operation),
            7,
            {
                "operation_id": _operation_id(operation),
                "generation": 7,
                "participants": participant_records,
            },
        )
    assert getattr(raised.value, "code", None) in {"invalid", "uncertain-effect"}
    assert runtime.calls == calls_before
    assert runtime.opened == []


@pytest.mark.parametrize("mode", ["start", "swap"])
@pytest.mark.parametrize("case", ["missing", "inconclusive", "unsupported", "unbound"])
def test_capability_refusal_precedes_runtime_and_survives_reload(mode, case):
    runtime = StartRuntime() if mode == "start" else SwapRuntime(_successful_swap_statuses())
    if mode == "start":
        controller, store, coordinator, workers, specs = _start_controller(runtime=runtime)
        inputs = copy.deepcopy((coordinator, workers, specs))

        def invoke(target):
            coordinator, workers, specs = copy.deepcopy(inputs)
            return _run_start(target, "gate-refused", coordinator=coordinator,
                              workers=workers, runner_specs=specs)
    else:
        controller, store, _ = _swap_roster(runtime)

        def invoke(target):
            return _run_swap(target, request_id="gate-refused")

    claims_before = copy.deepcopy(store.claims)
    checked = []

    def preflight(spec, evidence):
        checked.append(copy.deepcopy(spec))
        assert evidence is None
        return {
            "verdict": "verified" if case == "unbound" else case,
            "reason_code": "runtime-identity-mismatch" if case == "unsupported" else "orphan-positive-control-unreachable",
            "reason": "synthetic negative-control result",
        }

    runtime.preflight_held_swap = None if case == "missing" else preflight
    expected_code = "unsupported" if case == "unsupported" else "live-unverified"
    with pytest.raises(ControllerError) as refused:
        invoke(controller)
    assert refused.value.code == expected_code
    assert runtime.calls == []
    assert runtime.opened == runtime.interrupted == runtime.shutdowns == runtime.released == runtime.sent == []
    assert store.claims == claims_before
    if mode == "swap":
        assert _operation_record(store, "gate-refused")["sealed_participants"] == []
    else:
        assert controller.status()["participants"] == []
    assert store.release_calls == []
    assert _operation_record(store, "gate-refused")["phase"] == "complete"
    assert _operation_record(store, "gate-refused")["metadata"]["outcome"] == "capability-refused"
    assert controller.status()["runtime_capability"]["verdict"] != "verified"

    calls_before = len(checked)
    runtime.preflight_held_swap = SwapRuntime.preflight_held_swap
    reloaded = ManagedController(store, runtime=runtime, clock=lambda: 1000.0,
                                 transcript_verifier=store.transcript_verifier)
    with pytest.raises(ControllerError) as retried:
        invoke(reloaded)
    assert retried.value.code == expected_code
    assert len(checked) == calls_before
    assert runtime.calls == []
    assert _operation_record(store, "gate-refused")["phase"] == "complete"
    if mode == "start":
        cleared = reloaded.unenroll(7)
        assert cleared["owner_clear_ready"] is True
        assert runtime.calls == []


@pytest.mark.parametrize("phase", ["paused", "starting"])
def test_reloaded_swap_without_capability_cannot_interrupt(phase):
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    _run_swap(controller)
    for operation in store.documents["controller.json"]["operations"]:
        if operation["request_id"] == "swap-request":
            operation["phase"] = phase
            operation["metadata"].pop("capability_gates", None)
    runtime.calls.clear()
    runtime.preflight_held_swap = None
    claims = copy.deepcopy(store.claims)
    reloaded = ManagedController(store, runtime=runtime,
                                 transcript_verifier=store.transcript_verifier)
    with pytest.raises(ControllerError) as refused:
        _run_swap(reloaded)
    assert refused.value.code == "live-unverified"
    assert runtime.calls == []
    assert store.claims == claims


def test_refused_swap_preserves_previous_released_control_operation():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    released = _prepare_released_swap(controller, store, runtime)
    for participant in controller._participants.values():
        if participant.state not in {"completed", "stopped"}:
            _bind_source_transcript(store, participant)
    previous_id = _value(released, "operation_id")
    runtime.calls.clear()
    runtime.preflight_held_swap = None
    with pytest.raises(ControllerError) as refused:
        _run_swap(controller, request_id="second-swap-refused")
    assert refused.value.code == "live-unverified", str(refused.value)
    status = controller.status()
    assert status["active_operation_id"] == previous_id
    assert status["phase"] == "released"
    assert status["runtime_capability"]["verdict"] == "inconclusive"
    assert runtime.calls == []


def test_partial_ctx_recovery_records_fresh_worker_evidence_without_reopening():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    released = _prepare_released_swap(controller, store, runtime)
    prior = _operation_record(store, "swap-request")
    worker_runner = prior["metadata"]["runner_instances"]["worker-a"]
    blocked = _swap_open_result(
        "worker-a", WORKER_A_SESSION, runner_instance_id=worker_runner
    )
    blocked["evidence"].update({
        "active_turn": True,
        "turn_terminal": False,
        "drained": False,
        "participant_quiescent": False,
        "tools_quiescent": False,
        "quiescent": False,
        "tools": [{"tool_id": "tool-in-flight", "state": "running"}],
        "uncertain_effects": ["turn:worker-a"],
    })
    runtime.statuses["worker-a"] = [blocked]
    with pytest.raises(ControllerError) as raised:
        _run_ctx(
            controller,
            "ctx-partial-recovery",
            "checkpoint://ctx/partial-recovery",
            "hold",
        )
    assert raised.value.code == "uncertain-effect"
    ctx_record = _operation_record(store, "ctx-partial-recovery")
    ctx_operation_id = ctx_record["operation_id"]
    assert ctx_record["mode"] == "ctx"
    assert ctx_record["phase"] == "indeterminate"
    request_record = store.documents["controller.json"]["requests"][
        "ctx-partial-recovery"
    ]
    assert request_record["kind"] == "operation"
    assert isinstance(request_record["digest"], str)
    opened_before_recovery = copy.deepcopy(runtime.opened)

    fresh_runtime = SwapRuntime(_successful_swap_statuses())
    reloaded = ManagedController(
        store,
        runtime=fresh_runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    fresh_status = _completion_status(
        "worker-a", WORKER_A_SESSION, worker_runner
    )
    recovered = _run_recover(
        reloaded,
        ctx_operation_id,
        7,
        {
            "operation_id": ctx_operation_id,
            "generation": 7,
            "participants": {"worker-a": {"status": fresh_status}},
        },
    )
    assert _value(recovered, "mode") == "ctx"
    assert _value(recovered, "phase") == "indeterminate"
    final_ctx = _operation_record(store, "ctx-partial-recovery")
    worker_evidence = final_ctx["metadata"]["worker_status_evidence"]["worker-a"]
    assert worker_evidence["participant_id"] == "worker-a"
    assert worker_evidence["session_id"] == WORKER_A_SESSION
    assert worker_evidence["runner_instance_id"] == worker_runner
    assert worker_evidence["turn_terminal"] is True
    assert "worker-a" not in final_ctx["metadata"]["status_evidence"]
    assert fresh_runtime.calls == []
    assert fresh_runtime.opened == []
    assert runtime.opened == opened_before_recovery

    # The recorded ctx request remains the current fenced operation.  A retry
    # must reconcile that operation explicitly rather than falling back to a
    # new swap/open sequence.
    with pytest.raises(ControllerError) as raised:
        _run_ctx(
            reloaded,
            "ctx-partial-recovery",
            "checkpoint://ctx/partial-recovery",
            "hold",
        )
    assert raised.value.code == "uncertain-effect"
    assert fresh_runtime.calls == []
    assert fresh_runtime.opened == []


def test_partial_shutdown_recovery_reconciles_fresh_exclusion_without_reopen():
    runtime = CompletionRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    _run_swap(controller, request_id="shutdown-partial-source")
    runtime.shutdown_failure = "worker-b"
    with pytest.raises(ControllerError) as raised:
        asyncio.run(controller.shutdown(7))
    _assert_error(raised, "uncertain-effect")
    operation_status = controller.status()["operation"]
    operation_id = operation_status["operation_id"]
    assert operation_status["mode"] == "shutdown"
    assert operation_status["phase"] == "indeterminate"
    before_opened = copy.deepcopy(runtime.opened)
    worker_runner = operation_status["metadata"]["runner_instances"]["worker-b"]

    fresh_runtime = CompletionRuntime(_successful_swap_statuses())
    reloaded = ManagedController(
        store,
        runtime=fresh_runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    fresh_status = _completion_status(
        "worker-b", WORKER_B_SESSION, worker_runner
    )
    fresh_shutdown = _completion_status(
        "worker-b", WORKER_B_SESSION, worker_runner,
        process_exited=True,
        group_excluded=True,
    )
    recovered = _run_recover(
        reloaded,
        operation_id,
        7,
        {
            "operation_id": operation_id,
            "generation": 7,
            "participants": {
                "worker-b": {
                    "interrupt": fresh_status,
                    "status": fresh_status,
                    "shutdown": fresh_shutdown,
                },
            },
        },
    )
    assert _value(recovered, "mode") == "shutdown"
    assert _value(recovered, "phase") == "complete"
    assert fresh_runtime.calls == []
    assert fresh_runtime.opened == []
    assert runtime.opened == before_opened
    # Fresh exclusion evidence completes the shutdown; a retry is an
    # idempotent completed result and never reopens the stopped runner.
    repeated = asyncio.run(reloaded.shutdown(7))
    assert _value(repeated, "phase") == "complete"
    assert fresh_runtime.calls == []
    assert fresh_runtime.opened == []


def test_partial_unenroll_claim_index_crash_stays_indeterminate_after_reload():
    runtime = CompletionRuntime(_successful_swap_statuses())
    store = ClaimIndexMemoryStore()
    controller, store, _ = _swap_roster(runtime, store=store)
    _run_swap(controller, request_id="unenroll-partial-source")
    asyncio.run(controller.shutdown(7))
    original_release = store.release_writer
    crashed = {"value": False}

    def crash_after_index_removal(participant_id: str, worktree: Any):
        result = original_release(participant_id, worktree)
        if participant_id == "worker-a" and not crashed["value"]:
            crashed["value"] = True
            raise RuntimeError("crash after durable claim-index removal")
        return result

    store.release_writer = crash_after_index_removal
    with pytest.raises(ControllerError) as raised:
        controller.unenroll(7)
    _assert_error(raised, "ownership-conflict")
    operation = controller.status()["operation"]
    assert operation["mode"] == "unenroll"
    assert operation["phase"] == "indeterminate"
    # The durable index is authoritative at this crash boundary even though
    # the participant snapshot has not recorded the public released flag.
    assert ("worker-a", "/trees/a") not in store.claims
    assert _active_participant(controller.status(), "worker-a")["writer_claim"][
        "state"
    ] == "active"
    claims_after_crash = store._load_claims()
    assert not any(
        row["participant_id"] == "worker-a" for row in claims_after_crash
    )
    worker_b_claim = next(
        row for row in claims_after_crash
        if row["participant_id"] == "worker-b"
    )
    assert worker_b_claim["lane_key"] == MANAGED_LANE.casefold()
    assert worker_b_claim["repository"] == store._canonical_repository(
        None, Path("/trees/b")
    )
    release_calls_after_crash = copy.deepcopy(store.release_calls)
    runtime_calls_after_crash = copy.deepcopy(runtime.calls)

    fresh_runtime = CompletionRuntime(_successful_swap_statuses())
    reloaded = ManagedController(
        store,
        runtime=fresh_runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    operation_id = operation["operation_id"]
    recovered = _run_recover(
        reloaded,
        operation_id,
        7,
        {
            "operation_id": operation_id,
            "generation": 7,
            "participants": {},
        },
    )
    assert _value(recovered, "mode") == "unenroll"
    assert _value(recovered, "phase") == "indeterminate"
    assert fresh_runtime.calls == []
    assert fresh_runtime.opened == []
    assert store.release_calls == release_calls_after_crash
    assert runtime.calls == runtime_calls_after_crash
    claims_after_recovery = store._load_claims()
    assert not any(
        row["participant_id"] == "worker-a" for row in claims_after_recovery
    )
    assert any(
        row["participant_id"] == "worker-b" for row in claims_after_recovery
    )
    with pytest.raises(ControllerError) as raised:
        reloaded.unenroll(7)
    assert raised.value.code in {"busy", "uncertain-effect"}
    assert fresh_runtime.calls == []
    assert fresh_runtime.opened == []
    assert store.release_calls == release_calls_after_crash
    assert runtime.calls == runtime_calls_after_crash


def _successful_swap_statuses():
    return {
        "coordinator": [_swap_status(
            "coordinator", COORDINATOR_SESSION,
        )],
        "worker-a": [_swap_status(
            "worker-a", WORKER_A_SESSION,
        )],
        "worker-b": [_swap_status(
            "worker-b", WORKER_B_SESSION,
        )],
        "worker-completed": [_swap_status(
            "worker-completed", WORKER_C_SESSION,
        )],
    }


def test_swap_restores_exact_unfinished_sessions_held_without_model_dispatch():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)

    operation = _run_swap(controller)

    assert _value(operation, "phase") == "ready-held"
    expected_sessions = {
        "coordinator": COORDINATOR_SESSION,
        "worker-a": WORKER_A_SESSION,
        "worker-b": WORKER_B_SESSION,
    }
    assert {participant_id for participant_id, _ in runtime.opened} == set(expected_sessions)
    assert "worker-completed" not in {participant_id for participant_id, _ in runtime.opened}
    for participant_id, spec in runtime.opened:
        assert spec["participant_id"] == participant_id
        assert spec["session_id"] == expected_sessions[participant_id]
        assert spec["session_name"] == _session_name(participant_id)
        assert spec["bound_lane"] == MANAGED_LANE
        assert spec["profile_name"] == SWAP_PROFILE["name"]
        assert spec["config_dir"] == SWAP_PROFILE["config_dir"]
        assert spec["account_email"] == SWAP_PROFILE["email"]
        assert spec["transcript_store"] == SWAP_PROFILE["transcript_store"]
        assert spec["workspace"] == SWAP_PROFILE["workspace"]
        assert spec["fingerprint"]["model"] == SWAP_PROFILE["fingerprint"]["model"]
        assert spec["fingerprint"]["permission_mode"] == SWAP_PROFILE["fingerprint"]["permission_mode"]
        assert spec["fingerprint"]["workspace"] == SWAP_PROFILE["fingerprint"]["workspace"]
        assert spec["fingerprint"]["profile_name"] == SWAP_PROFILE["name"]
        assert spec["fingerprint"]["account_email"] == SWAP_PROFILE["email"]
        assert spec["fingerprint"]["config_dir"] == SWAP_PROFILE["config_dir"]
        assert spec["fingerprint"]["session_name"] == _session_name(participant_id)
        assert spec["fingerprint"]["bound_lane"] == MANAGED_LANE
    assert runtime.sent == []
    assert runtime.released == []
    assert set(runtime.open_evidence) == set(expected_sessions)
    for result in runtime.open_evidence.values():
        assert set(result) == {
            "participant_id", "session_id", "runner_instance_id", "evidence",
        }
        assert set(result["evidence"]) == {
            "participant_id", "session_id", "runner_instance_id",
            "ready", "released", "active_turn", "turn_terminal", "drained",
            "participant_quiescent", "tools_quiescent", "uncertain_effects",
            "process", "initialization",
        }
        assert set(result["evidence"]["process"]) == {
            "pid", "process_group_id", "process_start_token",
            "process_group_owned", "exited", "group_excluded",
        }
        assert set(result["evidence"]["initialization"]) == {
            "account_email", "permission_mode", "model", "fingerprint",
        }
    for result in runtime.shutdown_evidence.values():
        process = result["evidence"]["process"]
        assert process["exited"] is True
        assert process["group_excluded"] is True
        assert "shutdown" not in result
    operation_record = next(
        raw for raw in store.documents["controller.json"]["operations"]
        if raw["operation_id"] == _operation_id(operation)
    )
    target_profile = operation_record["metadata"]["target_profile"]
    assert target_profile == {
        "name": SWAP_PROFILE["name"],
        "email": SWAP_PROFILE["email"],
        "family": SWAP_PROFILE["family"],
        "status": "active",
        "authentication": {"type": "subscription_oauth"},
        "config_dir": SWAP_PROFILE["config_dir"],
        "transcript_store": SWAP_PROFILE["transcript_store"],
    }
    target_specs = operation_record["metadata"]["target_specs"]
    readiness = operation_record["readiness"]
    for participant_id in expected_sessions:
        runner_spec = target_specs[participant_id]
        assert readiness[participant_id]["spec"] == runner_spec
        assert runner_spec["session_name"] == _session_name(participant_id)
        assert runner_spec["bound_lane"] == MANAGED_LANE
        assert runner_spec["profile_name"] == SWAP_PROFILE["name"]
        assert runner_spec["config_dir"] == SWAP_PROFILE["config_dir"]
        assert runner_spec["account_email"] == SWAP_PROFILE["email"]
        assert runner_spec["fingerprint"]["model"] == SWAP_PROFILE["fingerprint"]["model"]
        assert runner_spec["fingerprint"]["permission_mode"] == SWAP_PROFILE["fingerprint"]["permission_mode"]
        assert runner_spec["fingerprint"]["workspace"] == SWAP_PROFILE["fingerprint"]["workspace"]
        assert runner_spec["fingerprint"]["profile_name"] == SWAP_PROFILE["name"]
        assert runner_spec["fingerprint"]["account_email"] == SWAP_PROFILE["email"]
        assert runner_spec["fingerprint"]["config_dir"] == SWAP_PROFILE["config_dir"]
        assert runner_spec["fingerprint"]["session_name"] == _session_name(participant_id)
        assert runner_spec["fingerprint"]["bound_lane"] == MANAGED_LANE
        assert readiness[participant_id]["runner_instance_id"] == \
            runtime.open_evidence[participant_id]["runner_instance_id"]
    open_positions = [index for index, call in enumerate(runtime.calls)
                      if call[0] == "open"]
    shutdown_positions = [index for index, call in enumerate(runtime.calls)
                          if call[0] == "shutdown"]
    assert open_positions and shutdown_positions
    assert max(shutdown_positions) < min(open_positions)


def test_swap_same_request_content_returns_ready_state_without_repeating_runtime_calls():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, _, _ = _swap_roster(runtime)

    first = _run_swap(controller)
    calls = copy.deepcopy(runtime.calls)
    second = _run_swap(controller)

    assert _operation_id(second) == _operation_id(first)
    assert _value(second, "phase") == "ready-held"
    assert runtime.calls == calls
    assert runtime.interrupted == ["coordinator", "worker-a", "worker-b"]
    assert runtime.shutdowns == ["coordinator", "worker-a", "worker-b"]
    assert [participant_id for participant_id, _ in runtime.opened] == [
        "coordinator", "worker-a", "worker-b",
    ]
    assert runtime.released == []


def test_recover_open_adopts_target_runner_spec_and_persists_profile_evidence():
    interrupted_open = _swap_open_result("worker-a", WORKER_A_SESSION, ready=False)
    runtime = SwapRuntime(
        _successful_swap_statuses(),
        open_results={"worker-a": interrupted_open},
    )
    controller, store, _ = _swap_roster(runtime)

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller)
    _assert_error(raised, "loader-failed")
    operation_id = store.documents["controller.json"]["operations"][-1]["operation_id"]
    assert [participant_id for participant_id, _ in runtime.opened] == [
        "coordinator", "worker-a",
    ]

    adopted_open = _swap_open_result(
        "worker-a",
        WORKER_A_SESSION,
        runner_instance_id=interrupted_open["runner_instance_id"],
        ready=True,
    )
    recovered = _run_recover(
        controller,
        operation_id,
        generation=7,
        evidence={
            "operation_id": operation_id,
            "generation": 7,
            "open": {"worker-a": adopted_open},
        },
    )
    assert _operation_id(recovered) == operation_id
    assert _value(recovered, "phase") == "starting"

    completed = _run_swap(controller)
    assert _operation_id(completed) == operation_id
    assert _value(completed, "phase") == "ready-held"
    assert [participant_id for participant_id, _ in runtime.opened] == [
        "coordinator", "worker-a", "worker-b",
    ]

    operation_record = next(
        raw for raw in store.documents["controller.json"]["operations"]
        if raw["operation_id"] == operation_id
    )
    metadata = operation_record["metadata"]
    assert metadata["target_profile"]["name"] == SWAP_PROFILE["name"]
    assert metadata["target_profile"]["email"] == SWAP_PROFILE["email"]
    assert metadata["target_profile"]["config_dir"] == SWAP_PROFILE["config_dir"]
    runner_spec = metadata["target_specs"]["worker-a"]
    assert runner_spec["profile_name"] == SWAP_PROFILE["name"]
    assert runner_spec["account_email"] == SWAP_PROFILE["email"]
    assert runner_spec["config_dir"] == SWAP_PROFILE["config_dir"]
    assert runner_spec["fingerprint"]["model"] == SWAP_PROFILE["fingerprint"]["model"]
    assert runner_spec["fingerprint"]["permission_mode"] == SWAP_PROFILE["fingerprint"]["permission_mode"]
    assert runner_spec["fingerprint"]["workspace"] == SWAP_PROFILE["fingerprint"]["workspace"]
    assert runner_spec["fingerprint"]["profile_name"] == SWAP_PROFILE["name"]
    assert runner_spec["fingerprint"]["account_email"] == SWAP_PROFILE["email"]
    assert runner_spec["fingerprint"]["config_dir"] == SWAP_PROFILE["config_dir"]
    assert operation_record["readiness"]["worker-a"]["spec"] == runner_spec
    assert operation_record["readiness"]["worker-a"]["runner_instance_id"] == \
        adopted_open["runner_instance_id"]


def test_swap_uses_fresh_fixed_uuid_for_reserved_never_written_session():
    statuses = _successful_swap_statuses()
    statuses["worker-a"] = [_swap_status("worker-a", RESERVED_SESSION)]
    runtime = SwapRuntime(statuses)
    metadata = _source_metadata(
        RESERVED_SESSION,
        transcript_exists=False,
        transcript_written=False,
        transcript_reserved=True,
    )
    metadata["runner_spec"]["mode"] = "fresh"
    metadata["runner_spec"]["fresh"] = True
    metadata["runner_spec"].pop("resume", None)
    controller, store, _ = _swap_roster(
        runtime,
        participant_metadata={
            "worker-a": metadata,
        },
        participant_sessions={"worker-a": RESERVED_SESSION},
    )

    operation = _run_swap(controller)

    assert _value(operation, "phase") == "ready-held"
    fresh_evidence = store.transcript_evidence["worker-a"]
    assert set(fresh_evidence) == {
        "profile", "session_id", "workspace", "transcript_store",
        "transcript_project", "transcript", "holders", "unknown_holders",
        "ambiguous",
    }
    assert fresh_evidence["holders"] == []
    assert fresh_evidence["unknown_holders"] == []
    assert fresh_evidence["ambiguous"] is False
    worker_spec = next(
        spec for participant_id, spec in runtime.opened
        if participant_id == "worker-a"
    )
    assert worker_spec["session_id"] == RESERVED_SESSION
    assert runtime.open_evidence["worker-a"]["session_id"] == RESERVED_SESSION


def test_reserved_uuid_written_by_trusted_verifier_uses_resume_on_next_swap():
    statuses = _successful_swap_statuses()
    statuses["worker-a"] = [_swap_status("worker-a", RESERVED_SESSION)]
    runtime = SwapRuntime(statuses)
    metadata = _source_metadata(
        RESERVED_SESSION,
        transcript_exists=False,
        transcript_written=False,
        transcript_reserved=True,
    )
    metadata["runner_spec"]["mode"] = "fresh"
    metadata["runner_spec"]["fresh"] = True
    metadata["runner_spec"].pop("resume", None)
    controller, store, _ = _swap_roster(
        runtime,
        participant_metadata={"worker-a": metadata},
        participant_sessions={"worker-a": RESERVED_SESSION},
    )

    first = _run_swap(controller, request_id="reserved-fresh")
    assert _value(first, "phase") == "ready-held"
    # The runtime, rather than controller metadata, writes the first durable
    # target transcript and its native holder before a later resume.
    _runtime_writes_target_transcript_holders(
        store, runtime
    )
    first_record = _operation_record(store, "reserved-fresh")
    runner_instances = first_record["metadata"]["runner_instances"]

    # Complete only the prior operation's durable release gate so the next
    # request is a distinct operation; no runner command is hand-rolled here.
    _release_state(controller, Operation.from_dict(first_record))
    for participant_id, session_id in (
        ("coordinator", COORDINATOR_SESSION),
        ("worker-a", RESERVED_SESSION),
        ("worker-b", WORKER_B_SESSION),
    ):
        runtime.statuses[participant_id] = [_swap_open_result(
            participant_id, session_id,
            runner_instance_id=runner_instances[participant_id],
        )]
    prior_open_count = len(runtime.opened)

    second = _run_swap(controller, request_id="reserved-resume")
    assert _value(second, "phase") == "ready-held"
    resumed = [spec for participant_id, spec in runtime.opened[prior_open_count:]
               if participant_id == "worker-a"]
    assert len(resumed) == 1
    assert resumed[0]["session_id"] == RESERVED_SESSION
    assert resumed[0]["mode"] == "resume"
    assert resumed[0].get("fresh") is not True
    assert runtime.sent == []


def test_trusted_written_reserved_uuid_refuses_stale_fresh_spec_before_runtime():
    statuses = _successful_swap_statuses()
    statuses["worker-a"] = [_swap_status("worker-a", RESERVED_SESSION)]
    runtime = SwapRuntime(statuses)
    metadata = _source_metadata(
        RESERVED_SESSION,
        transcript_exists=False,
        transcript_written=False,
        transcript_reserved=True,
    )
    metadata["runner_spec"]["mode"] = "fresh"
    metadata["runner_spec"]["fresh"] = True
    metadata["runner_spec"].pop("resume", None)
    controller, store, _ = _swap_roster(
        runtime,
        participant_metadata={"worker-a": metadata},
        participant_sessions={"worker-a": RESERVED_SESSION},
    )
    store.transcript_evidence["worker-a"]["transcript"] = {
        "session_id": RESERVED_SESSION,
        "exists": True,
        "written": True,
        "reserved": False,
    }

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller, request_id="stale-fresh")
    _assert_error(raised, "profile-mismatch")
    assert runtime.calls == []
    assert store.verifier_calls
    assert store.documents["controller.json"]["operations"][-1]["phase"] == "failed"


def test_swap_refuses_known_written_session_with_missing_transcript_before_runtime():
    metadata = _source_metadata(
        WORKER_A_SESSION,
        transcript_exists=False,
        transcript_written=False,
        transcript_reserved=False,
    )
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(
        runtime, participant_metadata={"worker-a": metadata}
    )

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller)
    _assert_error(raised, "profile-mismatch")
    assert runtime.calls == []
    assert runtime.interrupted == []
    assert runtime.shutdowns == []
    assert runtime.opened == []
    assert store.documents["controller.json"]["operations"][-1]["phase"] == "failed"


def test_swap_same_request_id_with_changed_target_refuses_content_digest_reuse():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, _, _ = _swap_roster(runtime)
    first = _run_swap(controller)
    calls = copy.deepcopy(runtime.calls)
    changed_profile = copy.deepcopy(SWAP_PROFILE)
    changed_profile["config_dir"] = "/managed/profiles/other-target"

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller, profile=changed_profile)
    _assert_error(raised, "invalid")
    assert runtime.calls == calls
    assert _operation_id(controller.status()["operation"]) == _operation_id(first)


def test_release_requires_matching_ready_generation_and_dispatches_once():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, _, _ = _swap_roster(runtime)
    controller.payload_resolver = lambda ref: ref
    entry = controller.submit(
        "release-message", "worker-a", "payload-after-release",
        sender_id="coordinator", task_id="task-a",
    )
    operation = _run_swap(controller)
    operation_id = _operation_id(operation)

    with pytest.raises(ControllerError) as raised:
        _run_release(controller, operation_id, generation=6)
    _assert_error(raised, "stale-generation")
    assert runtime.released == []
    assert runtime.sent == []

    released = _run_release(controller, operation_id, generation=7)
    assert _value(released, "phase") == "released"
    assert _value(released, "release_count") == 1
    assert set(runtime.released) == {"coordinator", "worker-a", "worker-b"}
    # Release only authorizes the queued effect; it does not dispatch inline.
    assert runtime.sent == []
    dispatched = _dispatch(controller, released)
    assert _value(dispatched, "state") == "acknowledged"
    assert runtime.sent == [("worker-a", _value(entry, "message_id"),
                             "payload-after-release")]

    with pytest.raises(ControllerError):
        _run_release(controller, operation_id, generation=7)
    assert runtime.released == ["coordinator", "worker-a", "worker-b"]
    assert runtime.sent == [("worker-a", _value(entry, "message_id"),
                             "payload-after-release")]


def test_swap_does_not_open_until_interrupt_terminal_drain_tools_and_process_exit():
    statuses = _successful_swap_statuses()
    statuses["worker-a"] = [_swap_status(
        "worker-a", WORKER_A_SESSION, turn_terminal=False, drained=False,
        participant_quiescent=False, tools_quiescent=False,
        process_exited=False, group_excluded=False,
    )]
    runtime = SwapRuntime(statuses)
    controller, store, _ = _swap_roster(runtime)

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller)
    assert raised.value.code in {"busy", "uncertain-effect", "loader-failed"}
    assert runtime.opened == []
    assert runtime.shutdowns == []
    assert any(call[0] == "interrupt" and call[1] == "worker-a"
               for call in runtime.calls)
    operation_records = store.documents["controller.json"]["operations"]
    assert operation_records
    first_operation_id = operation_records[-1]["operation_id"]
    assert operation_records[-1]["phase"] in {"paused", "indeterminate"}

    runtime.statuses["worker-a"] = [_swap_status(
        "worker-a", WORKER_A_SESSION, turn_terminal=True, drained=True,
        participant_quiescent=True, tools_quiescent=True,
        process_exited=False, group_excluded=False,
    )]
    reconciled = {
        "operation_id": first_operation_id,
        "generation": 7,
        "status": {
            "worker-a": runtime.statuses["worker-a"][0],
            "worker-b": runtime.statuses["worker-b"][0],
        },
    }
    recovered = _run_recover(
        controller, first_operation_id, generation=7, evidence=reconciled
    )
    assert _operation_id(recovered) == first_operation_id
    assert _value(recovered, "phase") in {"paused", "indeterminate"}
    assert runtime.interrupted.count("worker-a") == 1
    assert runtime.opened == []
    assert runtime.released == []

    # The second call resumes the durable request after explicit recovery; it
    # is not an independent swap/retry with a new operation identity.
    operation = _run_swap(controller)
    assert _operation_id(operation) == first_operation_id
    assert _value(operation, "phase") == "ready-held"
    assert runtime.opened
    assert runtime.interrupted.count("worker-a") == 1
    assert len(runtime.opened) == 3
    assert runtime.released == []
    open_positions = [index for index, call in enumerate(runtime.calls)
                      if call[0] == "open"]
    shutdown_positions = [index for index, call in enumerate(runtime.calls)
                          if call[0] == "shutdown"]
    assert max(shutdown_positions) < min(open_positions)

    calls = copy.deepcopy(runtime.calls)
    retry = _run_swap(controller)
    assert _operation_id(retry) == first_operation_id
    assert _value(retry, "phase") == "ready-held"
    assert runtime.calls == calls


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("runner_instance_id", "runner-other"),
        ("participant_id", "worker-other"),
        ("session_id", "99999999-9999-4999-8999-999999999999"),
    ),
)
def test_swap_rejects_runner_evidence_with_wrong_identity(field: str,
                                                          value: Any):
    bad_evidence = _swap_status("worker-a", WORKER_A_SESSION)
    bad_evidence[field] = value
    runtime = SwapRuntime(
        _successful_swap_statuses(),
        open_results={"worker-a": bad_evidence},
    )
    controller, store, _ = _swap_roster(runtime)

    with pytest.raises(ControllerError):
        _run_swap(controller)
    assert runtime.released == []
    assert runtime.sent == []
    assert store.documents["controller.json"]["operations"][-1]["phase"] != "ready-held"


@pytest.mark.parametrize(
    ("process_field", "process_value"),
    (("exited", True), ("group_excluded", True)),
)
def test_swap_rejects_ready_evidence_for_dead_or_excluded_runner(
        process_field: str, process_value: bool):
    bad_ready = _swap_open_result("worker-a", WORKER_A_SESSION)
    bad_ready["evidence"]["process"][process_field] = process_value
    runtime = SwapRuntime(
        _successful_swap_statuses(),
        open_results={"worker-a": bad_ready},
    )
    controller, store, _ = _swap_roster(runtime)

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller)
    _assert_error(raised, "loader-failed")
    assert runtime.sent == []
    assert runtime.released == []
    assert store.documents["controller.json"]["operations"][-1]["phase"] != "ready-held"


def test_swap_rejects_wrong_target_before_interrupt():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    wrong_target = copy.deepcopy(SWAP_PROFILE)
    wrong_target["family"] = "different-transcript-family"
    wrong_target["email"] = "wrong-target@example.invalid"
    wrong_target["config_dir"] = "/managed/profiles/wrong-target"

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller, profile=wrong_target)
    _assert_error(raised, "profile-mismatch")
    assert runtime.interrupted == []
    assert runtime.shutdowns == []
    assert runtime.opened == []
    assert store.documents["controller.json"]["operations"][-1]["phase"] == "failed"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        ("transcript-store-mismatch", "profile-mismatch"),
        ("transcript-store-unknown", "profile-mismatch"),
        ("holder-unknown", "uncertain-effect"),
    ),
)
def test_swap_preflight_refuses_actual_transcript_or_holder_unknowns_before_runtime(
        mutation: str, expected_code: str):
    metadata = _source_metadata(WORKER_A_SESSION)
    if mutation == "transcript-store-mismatch":
        metadata["transcript_store"] = "/managed/other-transcripts"
        metadata["runner_spec"]["transcript_store"] = "/managed/other-transcripts"
    elif mutation == "transcript-store-unknown":
        metadata["transcript_store"] = None
    else:
        metadata["unknown_holders"] = ["unresolved-holder"]
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(
        runtime, participant_metadata={"worker-a": metadata}
    )

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller)
    _assert_error(raised, expected_code)
    assert runtime.calls == []
    assert runtime.interrupted == []
    assert runtime.shutdowns == []
    assert runtime.opened == []
    assert store.documents["controller.json"]["operations"][-1]["phase"] == "failed"


def test_swap_inline_transcript_flags_never_authorize_without_injected_verifier():
    metadata = _source_metadata(WORKER_A_SESSION)
    metadata.update({
        "trusted": True,
        "authoritative": True,
        "transcript_authoritative": True,
        "holder": {
            "session_id": WORKER_A_SESSION,
            "authoritative": True,
            "live": True,
        },
    })
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(
        runtime, participant_metadata={"worker-a": metadata}
    )
    # Inline participant metadata is an untrusted description.  Remove the
    # only authority capable of proving the canonical projects holder.
    store.transcript_evidence.pop("worker-a")

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller)
    _assert_error(raised, "unknown")
    assert store.verifier_calls
    assert runtime.calls == []
    assert runtime.interrupted == []
    assert runtime.opened == []
    assert store.documents["controller.json"]["operations"][-1]["phase"] == "failed"


def test_swap_uses_only_injected_verifier_evidence_over_inline_transcript_metadata():
    metadata = _source_metadata(WORKER_A_SESSION)
    metadata.update({
        "trusted": False,
        "authoritative": False,
        "holder": {"unknown": True},
    })
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(
        runtime, participant_metadata={"worker-a": metadata}
    )
    injected = store.transcript_evidence["worker-a"]
    assert set(injected) == {
        "profile", "session_id", "workspace", "transcript_store",
        "transcript_project", "transcript", "holders", "unknown_holders",
        "ambiguous",
    }
    assert injected["holders"]
    assert all("participant_id" not in holder for holder in injected["holders"])

    operation = _run_swap(controller)
    assert _value(operation, "phase") == "ready-held"
    assert runtime.interrupted == ["coordinator", "worker-a", "worker-b"]
    assert store.verifier_calls


def test_swap_accepts_native_source_holder_by_owned_group_before_shutdown():
    """The source holder is native evidence, not a managed participant tag."""
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    source = next(
        item for item in _roster(controller.status())
        if _value(item, "participant_id") == "worker-a"
    )
    runner_process = _value(source, "metadata")["runner_process"]
    evidence = store.transcript_evidence["worker-a"]
    holder = evidence["holders"][0]

    assert set(evidence) == {
        "profile", "session_id", "workspace", "transcript_store",
        "transcript_project", "transcript", "holders", "unknown_holders",
        "ambiguous",
    }
    assert evidence["profile"]["name"] == SWAP_PROFILE["name"]
    assert "participant_id" not in holder
    assert set(holder) == {
        "profile_name", "session_id", "pid", "process_start_token",
        "record", "live", "pid_domain", "process_group_id",
        "process_group_member", "profile", "config_dir",
        "projects_store", "workspace", "path", "transcript_path",
    }
    assert holder["profile_name"] == "source-profile"
    assert holder["session_id"] == WORKER_A_SESSION
    assert holder["workspace"] == SWAP_PROFILE["workspace"]
    assert holder["pid_domain"] == "linux:test-machine:test-pid-namespace"
    assert holder["process_group_id"] == runner_process["process_group_id"]
    assert holder["process_group_member"] is True
    # Claude's native child has its own PID/start identity.  Membership in the
    # exact owned process group is the binding; PID equality is not proof.
    assert holder["pid"] != runner_process["pid"]
    assert holder["process_start_token"]
    assert holder["process_start_token"] != runner_process["process_start_token"]

    operation = _run_swap(controller)

    assert _value(operation, "phase") == "ready-held"
    assert all(
        item["profile_name"] != SWAP_PROFILE["name"]
        for item in evidence["holders"]
    )
    assert runtime.shutdowns == ["coordinator", "worker-a", "worker-b"]
    assert runtime.opened


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        ("additional", "ownership-conflict"),
        ("foreign-domain", "ownership-conflict"),
        ("unknown", "unknown"),
    ),
)
def test_swap_refuses_extra_foreign_or_unknown_native_holder_before_effects(
        mutation: str, expected_code: str):
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    evidence = store.transcript_evidence["worker-a"]
    holder = evidence["holders"][0]
    assert "participant_id" not in holder
    if mutation == "additional":
        extra = copy.deepcopy(holder)
        extra["pid"] += 1
        extra["process_start_token"] = "child-start-extra"
        extra["record"] = "/profiles/source-profile/sessions/extra.json"
        evidence["holders"].append(extra)
    elif mutation == "foreign-domain":
        evidence["holders"] = [
            {
                **holder,
                "profile_name": "foreign-profile",
                "profile": "foreign-profile",
                "config_dir": "/foreign/profile",
                "projects_store": "/foreign/projects",
            }
        ]
    else:
        evidence["unknown_holders"] = ["unobservable-foreign-process-domain"]

    with pytest.raises(ControllerError) as raised:
        _run_swap(controller)
    _assert_error(raised, expected_code)
    assert runtime.calls == []
    assert runtime.interrupted == []
    assert runtime.shutdowns == []
    assert runtime.opened == []
    assert _operation_record(store, "swap-request")["phase"] == "failed"


def _operation_record(store: MemoryStore, request_id: str) -> Dict[str, Any]:
    for operation in store.documents["controller.json"]["operations"]:
        if operation["request_id"] == request_id:
            return operation
    raise AssertionError("operation request is not durably recorded")


def test_handoff_is_checkpoint_only_after_release_and_content_deduplicated():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    released = _prepare_released_swap(controller, store, runtime)
    operation_id = _operation_id(released)
    before_status = copy.deepcopy(controller.status())
    before_calls = copy.deepcopy(runtime.calls)
    before_claims = copy.deepcopy(store.claims)
    checkpoint = "checkpoint://handoff/opaque-1"

    def _status_without_checkpoints(status):
        current = copy.deepcopy(status)
        current.pop("checkpoints")
        expected = copy.deepcopy(before_status)
        expected.pop("checkpoints")
        assert current == expected
        return status["checkpoints"]

    first = _run_handoff(controller, "handoff-request", checkpoint)

    assert set(first) == {
        "request_id", "generation", "checkpoint", "checkpoint_digest",
        "operation_id", "operation_phase", "created_at",
    }
    assert first["request_id"] == "handoff-request"
    assert first["generation"] == 7
    assert first["checkpoint"] == checkpoint
    assert first["operation_id"] == operation_id
    assert first["operation_phase"] == "released"
    checkpoints = _status_without_checkpoints(controller.status())
    assert len(checkpoints) == len(before_status["checkpoints"]) + 1
    assert runtime.calls == before_calls
    assert store.claims == before_claims
    operation_record = _operation_record(store, "swap-request")
    assert operation_record["phase"] == "released"
    assert operation_record["release_count"] == 1

    same = _run_handoff(controller, "handoff-request", checkpoint)
    assert same == first
    assert _status_without_checkpoints(controller.status()) == checkpoints
    assert runtime.calls == before_calls
    assert store.claims == before_claims

    with pytest.raises(ControllerError) as raised:
        _run_handoff(
            controller,
            "handoff-request",
            "checkpoint://handoff/changed-content",
        )
    _assert_error(raised, "invalid")
    assert _status_without_checkpoints(controller.status()) == checkpoints
    assert runtime.calls == before_calls
    assert store.claims == before_claims


def test_handoff_refuses_while_prior_operation_has_unresolved_effects():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    before_claims = copy.deepcopy(store.claims)
    controller.begin_operation("unresolved-operation", "swap", 7)
    durable = copy.deepcopy(store.documents["controller.json"])
    for record in durable["operations"]:
        if record["request_id"] == "unresolved-operation":
            record["phase"] = "indeterminate"
            record["uncertainty"] = ["open:worker-a"]
            break
    store.write_json("controller.json", durable)

    with pytest.raises(ControllerError) as raised:
        _run_handoff(controller, "blocked-handoff", "checkpoint://blocked")
    _assert_error(raised, "uncertain-effect")
    assert runtime.calls == []
    assert store.claims == before_claims
    assert _operation_record(store, "unresolved-operation")["phase"] == "indeterminate"


def _active_participant(status: Mapping[str, Any], participant_id: str) -> Dict[str, Any]:
    for item in status["participants"]:
        if item["participant_id"] == participant_id:
            return item
    raise AssertionError("active participant is absent from controller status")


def _archived_participant(status: Mapping[str, Any], participant_id: str) -> Dict[str, Any]:
    for item in status["archived_participants"]:
        if item["participant_id"] == participant_id:
            return item
    raise AssertionError("archived participant is absent from controller status")


def _checkpoint_entry(status: Mapping[str, Any], request_id: str) -> Dict[str, Any]:
    for item in status["mailboxes"]:
        if item["request_id"] == request_id:
            return item
    raise AssertionError("ctx checkpoint mailbox entry is absent")


def test_ctx_hold_archives_old_coordinator_and_preserves_released_workers():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    released = _prepare_released_swap(controller, store, runtime)
    old_status = copy.deepcopy(controller.status())
    old_release_calls = copy.deepcopy(runtime.released)
    old_claims = copy.deepcopy(store.claims)
    old_workers = {
        participant_id: _active_participant(old_status, participant_id)
        for participant_id in ("worker-a", "worker-b")
    }

    result = _run_ctx(
        controller,
        "ctx-hold",
        "checkpoint://ctx/hold-1",
        "hold",
    )

    assert _value(result, "phase") == "ready-held"
    status = controller.status()
    roster = status["participants"]
    assert sum(item["role"] == "coordinator" for item in roster) == 1
    new_coordinator = next(item for item in roster if item["role"] == "coordinator")
    assert new_coordinator["participant_id"].startswith("ctx-coordinator-")
    assert new_coordinator["participant_id"] != "coordinator"
    assert _archived_participant(status, "coordinator")["state"] == "stopped"
    assert status["coordinator_id"] == new_coordinator["participant_id"]
    assert new_coordinator["session_id"] not in {
        item["session_id"] for item in old_status["participants"]
    }
    assert str(uuid.UUID(new_coordinator["session_id"])) == new_coordinator["session_id"]

    # Hold preserves each worker's exact logical linkage, native session, and
    # mailbox identity.  The released claim index is not reconstructed by ctx.
    for participant_id, before in old_workers.items():
        after = _active_participant(status, participant_id)
        for field in ("session_id", "parent_id", "task_id", "mailbox_id"):
            assert after[field] == before[field]
    assert store.claims == old_claims
    assert runtime.released == old_release_calls
    assert runtime.sent == []

    checkpoint = _checkpoint_entry(status, "ctx-hold")
    assert checkpoint["recipient_id"] == new_coordinator["participant_id"]
    assert checkpoint["payload_ref"] == "checkpoint://ctx/hold-1"
    assert checkpoint["state"] == "fenced"
    assert checkpoint["generation"] == 7
    assert checkpoint["operation_id"] == _operation_id(result)

    old_operation = _operation_record(store, "swap-request")
    assert old_operation["phase"] == "complete"
    assert old_operation["metadata"]["superseded_by"] == _operation_id(result)
    ctx_record = _operation_record(store, "ctx-hold")
    assert ctx_record["phase"] == "ready-held"
    assert ctx_record["metadata"]["ctx_intent"]["state"] == "complete"
    assert ctx_record["metadata"]["checkpoint"] == "checkpoint://ctx/hold-1"

    # A checkpoint is not dispatched merely because ctx reached ready-held.
    calls_before_release = copy.deepcopy(runtime.calls)
    released_ctx = _run_release(controller, _operation_id(result), generation=7)
    assert _value(released_ctx, "phase") == "released"
    assert runtime.released == old_release_calls + [new_coordinator["participant_id"]]
    assert runtime.sent == []
    assert runtime.calls.count(("release", "worker-a")) == 1
    assert runtime.calls.count(("release", "worker-b")) == 1
    assert runtime.calls[:len(calls_before_release)] == calls_before_release
    candidates = controller.dispatch_candidates(_operation_id(result))
    assert any(
        item["message_id"] == checkpoint["message_id"]
        and item["recipient_id"] == new_coordinator["participant_id"]
        for item in candidates
    )
    assert _checkpoint_entry(controller.status(), "ctx-hold")["state"] == "fenced"


def test_ctx_request_reload_deduplicates_without_lifecycle_effects():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    _prepare_released_swap(controller, store, runtime)

    first = _run_ctx(
        controller,
        "ctx-reload-dedup",
        "checkpoint://ctx/reload-dedup",
        "hold",
    )
    first_operation_id = _operation_id(first)
    request_record = store.documents["controller.json"]["requests"][
        "ctx-reload-dedup"
    ]
    assert request_record["kind"] == "operation"
    assert len(request_record["digest"]) == 64
    assert request_record["result"]["operation_id"] == first_operation_id
    calls_after_first = copy.deepcopy(runtime.calls)

    reloaded_runtime = SwapRuntime(_successful_swap_statuses())
    reloaded = ManagedController(
        store,
        runtime=reloaded_runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    same = _run_ctx(
        reloaded,
        "ctx-reload-dedup",
        "checkpoint://ctx/reload-dedup",
        "hold",
    )

    assert _operation_id(same) == first_operation_id
    assert _value(same, "phase") == "ready-held"
    assert runtime.calls == calls_after_first
    assert reloaded_runtime.calls == []
    assert store.documents["controller.json"]["requests"][
        "ctx-reload-dedup"
    ] == request_record


def test_ctx_rebind_is_refused_before_parent_task_or_runtime_effects():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    _prepare_released_swap(controller, store, runtime)
    before_status = copy.deepcopy(controller.status())
    before_calls = copy.deepcopy(runtime.calls)
    before_opened = copy.deepcopy(runtime.opened)
    before_interrupted = copy.deepcopy(runtime.interrupted)
    before_released = copy.deepcopy(runtime.released)
    before_shutdowns = copy.deepcopy(runtime.shutdowns)
    before_sent = copy.deepcopy(runtime.sent)
    before_claims = copy.deepcopy(store.claims)
    before_operations = copy.deepcopy(store.documents["controller.json"]["operations"])
    mapping = {
        "worker-a": {"coordinator": "coordinator-new", "task": "ctx-task-a"},
        "worker-b": {"coordinator": "coordinator-new", "task": "ctx-task-b"},
    }

    with pytest.raises(ControllerError) as raised:
        _run_ctx(
            controller,
            "ctx-rebind",
            "checkpoint://ctx/rebind-1",
            "rebind",
            mapping,
        )

    _assert_error(raised, "invalid")
    assert controller.status() == before_status
    assert runtime.calls == before_calls
    assert runtime.opened == before_opened
    assert runtime.interrupted == before_interrupted
    assert runtime.released == before_released
    assert runtime.shutdowns == before_shutdowns
    assert runtime.sent == before_sent
    assert store.claims == before_claims
    assert store.documents["controller.json"]["operations"] == before_operations
    assert "ctx-rebind" not in store.documents["controller.json"]["requests"]


def test_ctx_rebind_is_refused_before_mapping_completeness_or_runtime_effects():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    _prepare_released_swap(controller, store, runtime)
    before_status = copy.deepcopy(controller.status())
    before_calls = copy.deepcopy(runtime.calls)
    before_opened = copy.deepcopy(runtime.opened)
    before_interrupted = copy.deepcopy(runtime.interrupted)
    before_released = copy.deepcopy(runtime.released)
    before_shutdowns = copy.deepcopy(runtime.shutdowns)
    before_sent = copy.deepcopy(runtime.sent)
    before_claims = copy.deepcopy(store.claims)
    before_operations = copy.deepcopy(store.documents["controller.json"]["operations"])

    with pytest.raises(ControllerError) as raised:
        _run_ctx(
            controller,
            "ctx-incomplete-map",
            "checkpoint://ctx/incomplete",
            "rebind",
            {"worker-a": {"coordinator": "coordinator-new", "task": "ctx-a"}},
        )
    _assert_error(raised, "invalid")
    assert controller.status() == before_status
    assert runtime.calls == before_calls
    assert runtime.opened == before_opened
    assert runtime.interrupted == before_interrupted
    assert runtime.released == before_released
    assert runtime.shutdowns == before_shutdowns
    assert runtime.sent == before_sent
    assert store.claims == before_claims
    assert store.documents["controller.json"]["operations"] == before_operations
    assert "ctx-incomplete-map" not in store.documents["controller.json"]["requests"]


def test_ctx_writable_coordinator_requires_atomic_claim_transfer_primitive():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(
        runtime,
        coordinator_read_only=False,
        coordinator_claim=_claim("coordinator", "/trees/coordinator"),
    )
    _prepare_released_swap(controller, store, runtime)
    before_calls = copy.deepcopy(runtime.calls)
    before_opened = copy.deepcopy(runtime.opened)
    before_claims = copy.deepcopy(store.claims)
    assert not hasattr(store, "transfer_writer_claim")

    with pytest.raises(ControllerError) as raised:
        _run_ctx(
            controller,
            "ctx-writable-atomic-transfer",
            "checkpoint://ctx/writable-transfer",
            "hold",
        )
    _assert_error(raised, "unsupported")
    assert runtime.calls == before_calls
    assert runtime.opened == before_opened
    assert store.claims == before_claims
    assert controller.status()["participants"]
    assert "ctx-writable-atomic-transfer" not in store.documents[
        "controller.json"
    ]["requests"]


def test_ctx_refuses_ambiguous_worker_status_without_interrupting_old_coordinator():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    _prepare_released_swap(controller, store, runtime)
    operation = _operation_record(store, "swap-request")
    runner = operation["metadata"]["runner_instances"]["worker-a"]
    uncertain = _swap_open_result(
        "worker-a", WORKER_A_SESSION, runner_instance_id=runner
    )
    uncertain["evidence"].update({
        "active_turn": True,
        "turn_terminal": False,
        "drained": False,
        "participant_quiescent": False,
        "tools_quiescent": False,
        "quiescent": False,
        "tools": ["tool-call-in-flight"],
        "uncertain_effects": ["turn:worker-a"],
    })
    runtime.statuses["worker-a"] = [uncertain]
    before_claims = copy.deepcopy(store.claims)
    before_opened = copy.deepcopy(runtime.opened)
    before_interrupted = copy.deepcopy(runtime.interrupted)
    before_shutdowns = copy.deepcopy(runtime.shutdowns)

    with pytest.raises(ControllerError) as raised:
        _run_ctx(
            controller,
            "ctx-uncertain-worker",
            "checkpoint://ctx/uncertain",
            "hold",
        )
    _assert_error(raised, "uncertain-effect")
    assert runtime.interrupted == before_interrupted
    assert runtime.shutdowns == before_shutdowns
    assert runtime.opened == before_opened
    assert store.claims == before_claims
    assert controller.status()["operation"]["phase"] == "indeterminate"


def test_released_unsent_mail_survives_add_worker_and_swap_then_dispatches_once():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)

    # Create one message before the first fence and one after its release so
    # both queued and fenced unsent backlog must cross later lifecycle gates.
    acknowledged = controller.submit(
        "mail-acknowledged", "worker-a", "payload://already-acknowledged",
        sender_id="coordinator", task_id="task-a",
    )
    first = _run_swap(controller, request_id="mail-initial-swap")
    _runtime_writes_target_transcript_holders(
        store, runtime
    )
    fenced = controller.submit(
        "mail-fenced", "worker-b", "payload://fenced-backlog",
        sender_id="coordinator", task_id="task-b",
    )
    assert _value(fenced, "state") == "fenced"
    first_released = _run_release(controller, _operation_id(first), generation=7)
    assert _value(first_released, "phase") == "released"
    queued = controller.submit(
        "mail-queued", "worker-b", "payload://queued-backlog",
        sender_id="coordinator", task_id="task-b",
    )
    assert _value(queued, "state") == "queued"

    # Make one effect terminal and two others non-replayable.  These entries
    # are deliberately not eligible for migration by either lifecycle gate.
    controller.payload_resolver = lambda ref: "body:" + ref
    acknowledged_id = _value(acknowledged, "message_id")
    _dispatch(controller, first_released)
    assert _value(_mailbox(controller.status(), acknowledged_id), "state") == "acknowledged"
    dispatch_intent = controller.submit(
        "mail-dispatch-intent", "worker-a", "payload://dispatch-intent",
        sender_id="coordinator", task_id="task-a",
    )
    uncertain = controller.submit(
        "mail-uncertain", "worker-a", "payload://uncertain",
        sender_id="coordinator", task_id="task-a",
    )
    _durable_mailbox_state(store, _value(dispatch_intent, "message_id"), "dispatch-intent")
    _durable_mailbox_state(store, _value(uncertain, "message_id"), "uncertain")

    added_participant, added_spec = _new_worker_for_admission(store)
    added = _run_add_worker_held(
        controller, "add-worker-backlog", added_participant, added_spec
    )
    assert _value(added, "phase") == "ready-held"
    _runtime_writes_target_transcript_holders(
        store, runtime
    )
    for message in (fenced, queued):
        current = _mailbox(controller.status(), _value(message, "message_id"))
        assert _value(current, "operation_id") == _operation_id(added)
        assert _value(current, "state") in {"queued", "fenced"}
    assert _value(_mailbox(controller.status(), _value(dispatch_intent, "message_id")),
                  "state") == "dispatch-intent"
    assert _value(_mailbox(controller.status(), _value(uncertain, "message_id")),
                  "state") == "uncertain"

    added_released = _run_release(controller, _operation_id(added), generation=7)
    assert _value(added_released, "phase") == "released"
    swapped = _run_swap(controller, request_id="swap-after-add-worker")
    swapped_released = _run_release(controller, _operation_id(swapped), generation=7)
    assert _value(swapped_released, "phase") == "released"
    for message in (fenced, queued):
        current = _mailbox(controller.status(), _value(message, "message_id"))
        assert _value(current, "operation_id") == _operation_id(swapped)
        assert _value(current, "state") == "fenced"

    # Explicit release authorizes both unsent entries.  Each is sent once;
    # acknowledged/dispatch-intent/uncertain entries retain their old
    # correlation and cannot be silently replayed into the new gate.
    first_sent = _dispatch(controller, swapped_released)
    second_sent = _dispatch(controller, swapped_released)
    assert _value(first_sent, "state") == "acknowledged"
    assert _value(second_sent, "state") == "acknowledged"
    assert runtime.sent == [
        ("worker-a", acknowledged_id, "body:payload://already-acknowledged"),
        ("worker-b", _value(fenced, "message_id"), "body:payload://fenced-backlog"),
        ("worker-b", _value(queued, "message_id"), "body:payload://queued-backlog"),
    ]
    status = controller.status()
    assert _value(_mailbox(status, _value(dispatch_intent, "message_id")), "state") == "dispatch-intent"
    assert _value(_mailbox(status, _value(dispatch_intent, "message_id")), "operation_id") != _operation_id(swapped)
    assert _value(_mailbox(status, _value(uncertain, "message_id")), "state") == "uncertain"
    assert _value(_mailbox(status, _value(uncertain, "message_id")), "operation_id") != _operation_id(swapped)
    assert len([item for item in runtime.sent if item[1] == acknowledged_id]) == 1


def test_add_worker_open_recovery_adopts_exact_runner_without_replay():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    _run_release(controller, _operation_id(_run_swap(controller)), generation=7)
    participant, spec = _new_worker_for_admission(store, participant_id="worker-recover",
                                                   session_id=WORKER_D_SESSION,
                                                   worktree="/trees/recover")
    # The fake raises after returning an accepted open, so the durable intent
    # remains in-progress while the runner identity is observable only through
    # the explicit recovery evidence supplied below.
    failing_runtime = SwapRuntime(_successful_swap_statuses())
    # Keep the controller's existing roster/store, but use a runtime that
    # exposes the accepted admission runner and then crashes at the boundary.
    controller.runtime = failing_runtime
    original_open = failing_runtime.open

    async def crash_after_open(participant_id: str, runner_spec: Dict[str, Any]):
        result = await original_open(participant_id, runner_spec)
        if participant_id == "worker-recover":
            # Capture the accepted open envelope explicitly.  This admission
            # fake has no pre-seeded target result: the first open creates the
            # durable runner/process identity that recovery must later adopt.
            result = CompletionRuntime._canonical(result)
            result["runner_instance_id"] = "runner-admission-recovered"
            result["evidence"]["runner_instance_id"] = (
                "runner-admission-recovered"
            )
            failing_runtime.open_evidence[participant_id] = copy.deepcopy(result)
            failing_runtime.statuses[participant_id] = [copy.deepcopy(result)]
            raise RuntimeError("crash after admission open before registration")
        return result

    failing_runtime.open = crash_after_open
    request_id = "add-worker-recover"
    with pytest.raises(ControllerError) as raised:
        _run_add_worker_held(controller, request_id, participant, spec)
    assert raised.value.code == "uncertain-effect"
    record = _operation_record(store, request_id)
    operation_id = record["operation_id"]
    intent = record["metadata"]["launch_intents"]["worker-recover"]
    assert intent["state"] == "in-progress"
    assert [item[0] for item in failing_runtime.opened] == ["worker-recover"]
    accepted = copy.deepcopy(failing_runtime.open_evidence["worker-recover"])
    fresh_status = copy.deepcopy(accepted)
    fresh_status["evidence"].update({
        "quiescent": True,
        "tools": [],
    })
    calls_before_recovery = copy.deepcopy(failing_runtime.calls)

    reloaded = ManagedController(
        store,
        runtime=failing_runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    recovered = _run_recover(
        reloaded,
        operation_id,
        7,
        {
            "operation_id": operation_id,
            "generation": 7,
            "participants": {
                "worker-recover": {
                    "open": accepted,
                    "status": fresh_status,
                },
            },
        },
    )
    assert _value(recovered, "phase") == "ready-held"
    assert failing_runtime.calls == calls_before_recovery
    assert [item[0] for item in failing_runtime.opened] == ["worker-recover"]
    final = _operation_record(store, request_id)
    assert final["metadata"]["launch_intents"]["worker-recover"]["state"] == "ready"
    assert final["metadata"]["runner_instances"]["worker-recover"] == "runner-admission-recovered"
    assert "shutdown" not in final["metadata"]

    # A duplicate admission request returns the durable held operation and
    # cannot call open a second time or create another claim.
    same = _run_add_worker_held(reloaded, request_id, participant, spec)
    assert _operation_id(same) == operation_id
    assert _value(same, "phase") == "ready-held"
    assert [item[0] for item in failing_runtime.opened] == ["worker-recover"]
    assert list(store.claims).count(("worker-recover", "/trees/recover")) == 1


def test_add_worker_held_retry_is_stable_across_release_reload_and_content_change():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    initial = _run_swap(controller, request_id="add-retry-initial-swap")
    _run_release(controller, _operation_id(initial), generation=7)
    participant, spec = _new_worker_for_admission(
        store, participant_id="worker-retry", session_id=WORKER_D_SESSION,
        worktree="/trees/retry",
    )
    request_id = "add-worker-retry"

    first = _run_add_worker_held(controller, request_id, participant, spec)
    assert _value(first, "phase") == "ready-held"
    calls_after_first = copy.deepcopy(runtime.calls)
    claims_after_first = copy.deepcopy(store.claims)
    same_held = _run_add_worker_held(
        controller, request_id, participant, copy.deepcopy(spec)
    )
    assert _operation_id(same_held) == _operation_id(first)
    assert _value(same_held, "phase") == "ready-held"
    assert runtime.calls == calls_after_first
    assert store.claims == claims_after_first

    released = _run_release(controller, _operation_id(first), generation=7)
    assert _value(released, "phase") == "released"
    calls_after_release = copy.deepcopy(runtime.calls)
    claims_after_release = copy.deepcopy(store.claims)
    # A native transcript can gain durable content between retries.  That
    # evolving observation is written by the runtime, not controller metadata;
    # it is not caller request identity and must not change the stable digest.
    _runtime_writes_target_transcript_holders(
        store, runtime, ["worker-retry"]
    )

    reloaded = ManagedController(
        store,
        runtime=runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    same_released = _run_add_worker_held(
        reloaded, request_id, participant, copy.deepcopy(spec)
    )
    assert _operation_id(same_released) == _operation_id(first)
    assert _value(same_released, "phase") == "released"
    assert runtime.calls == calls_after_release
    assert store.claims == claims_after_release
    assert store.claim_calls.count(("worker-retry", "/trees/retry", None)) == 1

    changed_participant = replace(participant, task_id="different-task")
    with pytest.raises(ControllerError) as raised:
        _run_add_worker_held(reloaded, request_id, changed_participant, spec)
    _assert_error(raised, "invalid")
    changed_spec = copy.deepcopy(spec)
    changed_spec["config_dir"] = "/managed/profiles/changed"
    with pytest.raises(ControllerError) as raised:
        _run_add_worker_held(reloaded, request_id, participant, changed_spec)
    _assert_error(raised, "invalid")
    changed_session_name = "managed-worker-retry-renamed"
    changed_metadata = copy.deepcopy(participant.metadata)
    changed_metadata["session_name"] = changed_session_name
    for metadata_key in ("runner_spec", "spec"):
        metadata_spec = copy.deepcopy(changed_metadata[metadata_key])
        metadata_spec["session_name"] = changed_session_name
        metadata_fingerprint = copy.deepcopy(metadata_spec["fingerprint"])
        metadata_fingerprint["session_name"] = changed_session_name
        metadata_spec["fingerprint"] = metadata_fingerprint
        changed_metadata[metadata_key] = metadata_spec
    changed_fingerprint = copy.deepcopy(participant.fingerprint)
    changed_fingerprint["session_name"] = changed_session_name
    changed_participant = replace(
        participant,
        session_name=changed_session_name,
        fingerprint=changed_fingerprint,
        metadata=changed_metadata,
    )
    changed_spec = copy.deepcopy(spec)
    changed_spec["session_name"] = changed_session_name
    changed_spec_fingerprint = copy.deepcopy(changed_spec["fingerprint"])
    changed_spec_fingerprint["session_name"] = changed_session_name
    changed_spec["fingerprint"] = changed_spec_fingerprint
    with pytest.raises(ControllerError) as raised:
        _run_add_worker_held(
            reloaded, request_id, changed_participant, changed_spec
        )
    _assert_error(raised, "invalid")
    changed_bound_lane = replace(participant, bound_lane="other-lane")
    with pytest.raises(ControllerError) as raised:
        _run_add_worker_held(
            reloaded, request_id, changed_bound_lane, copy.deepcopy(spec)
        )
    _assert_error(raised, "ownership-conflict")
    assert runtime.calls == calls_after_release
    assert store.claims == claims_after_release


def test_lifecycle_carries_only_unsent_mail_and_preserves_transport_effects():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    controller.payload_resolver = lambda ref: "body:" + ref

    acknowledged = controller.submit(
        "mail-transition-ack", "worker-a", "payload://transition-ack",
        sender_id="coordinator", task_id="task-a",
    )
    first = _run_swap(controller, request_id="transition-first-swap")
    _runtime_writes_target_transcript_holders(
        store, runtime
    )
    fenced = controller.submit(
        "mail-transition-fenced", "worker-b", "payload://transition-fenced",
        sender_id="coordinator", task_id="task-b",
    )
    assert _value(fenced, "state") == "fenced"
    first_released = _run_release(controller, _operation_id(first), generation=7)
    queued = controller.submit(
        "mail-transition-queued", "worker-b", "payload://transition-queued",
        sender_id="coordinator", task_id="task-b",
    )
    assert _value(queued, "state") == "queued"

    acknowledged_id = _value(acknowledged, "message_id")
    _dispatch(controller, first_released)
    assert _value(_mailbox(controller.status(), acknowledged_id), "state") == "acknowledged"
    dispatch_intent = controller.submit(
        "mail-transition-intent", "worker-a", "payload://transition-intent",
        sender_id="coordinator", task_id="task-a",
    )
    uncertain = controller.submit(
        "mail-transition-uncertain", "worker-a", "payload://transition-uncertain",
        sender_id="coordinator", task_id="task-a",
    )
    _durable_mailbox_state(store, _value(dispatch_intent, "message_id"), "dispatch-intent")
    _durable_mailbox_state(store, _value(uncertain, "message_id"), "uncertain")

    second = _run_swap(controller, request_id="transition-second-swap")
    second_released = _run_release(controller, _operation_id(second), generation=7)
    assert _value(second_released, "phase") == "released"
    # Only the legitimate unsent backlog changes operation ownership.  The
    # runtime effects retain their original state/correlation across swap.
    for message in (fenced, queued):
        current = _mailbox(controller.status(), _value(message, "message_id"))
        assert _value(current, "operation_id") == _operation_id(second)
        assert _value(current, "state") == "fenced"
    for message, state in ((acknowledged, "acknowledged"),
                           (dispatch_intent, "dispatch-intent"),
                           (uncertain, "uncertain")):
        current = _mailbox(controller.status(), _value(message, "message_id"))
        assert _value(current, "state") == state
        assert _value(current, "operation_id") != _operation_id(second)

    _dispatch(controller, second_released)
    _dispatch(controller, second_released)
    assert runtime.sent == [
        ("worker-a", acknowledged_id, "body:payload://transition-ack"),
        ("worker-b", _value(fenced, "message_id"), "body:payload://transition-fenced"),
        ("worker-b", _value(queued, "message_id"), "body:payload://transition-queued"),
    ]
    status = controller.status()
    assert _value(_mailbox(status, _value(dispatch_intent, "message_id")), "state") == "dispatch-intent"
    assert _value(_mailbox(status, _value(uncertain, "message_id")), "state") == "uncertain"
    assert len([item for item in runtime.sent if item[1] == acknowledged_id]) == 1


def test_ctx_held_mail_is_not_requeued_or_dispatched_by_new_release_gate():
    runtime = SwapRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    controller.payload_resolver = lambda ref: ref
    _prepare_released_swap(controller, store, runtime)
    ctx_operation = _run_ctx(
        controller,
        "ctx-held-mail-gate",
        "checkpoint://ctx/held-mail-gate",
        "hold",
    )
    held = controller.submit(
        "ctx-held-mail-gate-entry", "worker-a", "payload://held-worker",
        sender_id="user", task_id="task-a",
    )
    assert _value(held, "state") == "fenced"
    assert _value(held, "operation_id") == _operation_id(ctx_operation)

    released = _run_release(controller, _operation_id(ctx_operation), generation=7)
    assert _value(released, "phase") == "released"
    current = _mailbox(controller.status(), _value(held, "message_id"))
    assert _value(current, "state") == "fenced"
    assert _value(current, "operation_id") == _operation_id(ctx_operation)
    candidates = controller.dispatch_candidates(_operation_id(ctx_operation))
    new_coordinator = controller.status()["coordinator_id"]
    assert any(item["recipient_id"] == new_coordinator for item in candidates)
    assert all(item["recipient_id"] != "worker-a" for item in candidates)
    checkpoint = _checkpoint_entry(controller.status(), "ctx-held-mail-gate")
    dispatched = asyncio.run(
        controller.dispatch_next(_operation_id(ctx_operation))
    )
    assert _value(dispatched, "message_id") == checkpoint["message_id"]
    assert _value(_mailbox(controller.status(), checkpoint["message_id"]),
                  "state") == "acknowledged"
    assert runtime.sent == [(
        new_coordinator,
        checkpoint["message_id"],
        "checkpoint://ctx/held-mail-gate",
    )]
    assert _value(_mailbox(controller.status(), _value(held, "message_id")),
                  "state") == "fenced"
    assert not any(
        call[0] == "send" and call[1] == "worker-a"
        for call in runtime.calls
    )


def test_start_prevalidates_fixed_roster_and_records_ready_held_without_dispatch():
    runtime = StartRuntime()
    controller, store, coordinator, workers, specs = _native_start_controller(
        runtime=runtime
    )
    request_id = "start-fixed-roster"

    result = _run_native_start(
        controller,
        request_id=request_id,
        coordinator=coordinator,
        runner_spec=specs[coordinator.participant_id],
    )

    expected_ids = ["coordinator"]
    assert _value(result, "phase") == "ready-held"
    assert runtime.open_attempts == expected_ids
    assert [participant_id for participant_id, _ in runtime.opened] == expected_ids
    opened_spec = runtime.opened[0][1]
    assert opened_spec["participant_id"] == coordinator.participant_id
    assert opened_spec["session_id"] == coordinator.session_id
    assert opened_spec["session_name"] == coordinator.session_name
    assert opened_spec["bound_lane"] == coordinator.bound_lane
    assert opened_spec["fingerprint"]["lineage_context"]["lineage_id"] == (
        NATIVE_START_LINEAGE_ID
    )
    assert opened_spec["fingerprint"]["lineage_context"]["runner_incarnation"] == (
        NATIVE_START_RUNNER
    )
    assert opened_spec["fingerprint"]["trusted_definitions"]["writer"]["tools"] == [
        "Read", "Write",
    ]
    assert runtime.sent == []
    assert runtime.prompts == []
    assert {call[0] for call in runtime.calls} == {"open"}

    roster = _roster(controller.status())
    assert len(roster) == 1
    assert sum(_value(item, "role") == "coordinator" for item in roster) == 1
    assert {(_value(item, "participant_id"), _value(item, "session_id"))
            for item in roster} == {
                ("coordinator", COORDINATOR_SESSION),
            }
    assert store.claim_calls == []
    assert len(store.lineage_claims) == 1

    record = _operation_record(store, request_id)
    assert record["phase"] == "ready-held"
    assert record["sealed_participants"] == expected_ids
    launch_intents = record["metadata"]["launch_intents"]
    assert set(launch_intents) == set(expected_ids)
    assert all(launch_intents[item]["state"] == "ready"
               for item in expected_ids)
    assert set(record["readiness"]) == set(expected_ids)
    for participant_id in expected_ids:
        assert specs[participant_id]["session_name"] == _session_name(participant_id)
        assert specs[participant_id]["bound_lane"] == MANAGED_LANE
        assert specs[participant_id]["fingerprint"]["session_name"] == _session_name(participant_id)
        assert specs[participant_id]["fingerprint"]["bound_lane"] == MANAGED_LANE
        readiness = record["readiness"][participant_id]
        assert readiness["session_id"] == specs[participant_id]["session_id"]
        readiness_spec = readiness["spec"]
        assert readiness_spec["participant_id"] == participant_id
        assert readiness_spec["session_id"] == specs[participant_id]["session_id"]
        assert readiness_spec["session_name"] == specs[participant_id]["session_name"]
        assert readiness_spec["bound_lane"] == MANAGED_LANE
        assert readiness_spec["fingerprint"]["lineage_context"]["lineage_id"] == (
            NATIVE_START_LINEAGE_ID
        )
        launch_definitions = readiness_spec["fingerprint"]["trusted_definitions"]
        assert launch_definitions["writer"]["model"] == "configured-model"
        assert launch_definitions["writer"]["effort"] == "high"
        assert launch_definitions["writer"]["tools"] == ["Read", "Write"]
        assert launch_definitions["writer"]["prompt"]
        assert "digest" not in launch_definitions["writer"]
        assert readiness["evidence"] == runtime.open_evidence[participant_id]
        assert set(readiness["evidence"]) == {
            "participant_id", "session_id", "runner_instance_id", "evidence",
        }
        assert set(readiness["evidence"]["evidence"]) == {
            "participant_id", "session_id", "runner_instance_id",
            "ready", "released", "active_turn", "turn_terminal", "drained",
            "participant_quiescent", "tools_quiescent", "uncertain_effects",
            "process", "initialization",
        }

    # Native startup persists the validated lineage and body-free trusted
    # definition facts before the coordinator open.  It does not fabricate a
    # native invocation context before a real durable mailbox is selected.
    startup = record["metadata"]["native_startup"]
    assert startup["lineage_id"] == NATIVE_START_LINEAGE_ID
    assert startup["runner_incarnation"] == NATIVE_START_RUNNER
    assert startup["lineage"]["lineage_id"] == NATIVE_START_LINEAGE_ID
    assert startup["lineage"]["owner_generation"] == 7
    assert startup["definitions"]["writer"]["digest"]
    assert startup["definitions"]["writer"]["tools"] == ["Read", "Write"]
    assert startup["invocation_bound"] is False

    # A launch intent is durable before its corresponding runtime call.  The
    # fake captures the record at each open boundary, not after the operation.
    assert [participant_id for participant_id, _ in runtime.intent_snapshots] == expected_ids
    for participant_id, snapshot in runtime.intent_snapshots:
        assert snapshot is not None
        snap = _operation_record_from_snapshot(snapshot, request_id)
        intent = snap["metadata"]["launch_intents"][participant_id]
        assert intent["state"] == "in-progress"
        assert intent["participant_id"] == participant_id
        assert intent["session_id"] == specs[participant_id]["session_id"]
        assert intent["generation"] == 7
        assert intent["spec"]["participant_id"] == participant_id
        assert intent["spec"]["session_id"] == specs[participant_id]["session_id"]
        prepared = snap["metadata"]["target_specs"][participant_id]
        assert prepared["fingerprint"]["lineage_context"] == (
            opened_spec["fingerprint"]["lineage_context"]
        )
        startup = snap["metadata"]["native_startup"]
        opened_context = opened_spec["fingerprint"]["lineage_context"]
        assert {
            "owner_generation": startup["lineage"]["owner_generation"],
            "lineage_id": startup["lineage_id"],
            "lineage_generation": startup["lineage_generation"],
            "runner_incarnation": startup["runner_incarnation"],
        } == opened_context

    assert controller._native_context is None

    reloaded = ManagedController(
        store,
        runtime=runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    assert _operation_id(reloaded.status()["operation"]) == _operation_id(result)
    assert reloaded.status()["operation"]["phase"] == "ready-held"
    assert reloaded.status() == controller.status()


def _operation_record_from_snapshot(snapshot: Mapping[str, Any],
                                    request_id: str) -> Dict[str, Any]:
    for operation in snapshot.get("operations", []):
        if operation.get("request_id") == request_id:
            return operation
    raise AssertionError("startup operation is absent at launch boundary")


def test_start_validates_every_spec_before_first_open():
    runtime = StartRuntime()
    controller, store, coordinator, workers, specs = _native_start_controller(
        runtime=runtime
    )
    malformed = copy.deepcopy(specs)
    malformed[coordinator.participant_id]["unsupported_setting"] = True

    with pytest.raises(ControllerError) as raised:
        _run_start(
            controller, request_id="start-preflight-all", generation=7,
            coordinator=coordinator, workers=workers, runner_specs=malformed,
        )
    _assert_error(raised, "unsupported")
    assert runtime.open_attempts == []
    assert runtime.opened == []
    assert runtime.sent == []
    assert runtime.prompts == []
    assert not any(call[0] == "open" for call in runtime.calls)
    # Validation happens before the native workspace claim is published as
    # well, so malformed coordinator definitions cannot leave a partial lane.
    assert store.claim_calls == []
    assert store.lineage_claims == []
    assert controller.status()["participants"] == []


@pytest.mark.parametrize("failure_kind", ["failure", "cancel"])
def test_start_failure_or_cancel_is_indeterminate_and_never_auto_replayed(
        failure_kind: str):
    runtime = StartRuntime(
        fail_on_open="coordinator" if failure_kind == "failure" else None,
        cancel_on_open="coordinator" if failure_kind == "cancel" else None,
    )
    controller, store, coordinator, workers, specs = _native_start_controller(
        runtime=runtime
    )
    request_id = "start-uncertain-" + failure_kind

    if failure_kind == "cancel":
        with pytest.raises(asyncio.CancelledError):
            _run_native_start(
                controller,
                request_id=request_id,
                coordinator=coordinator,
                runner_spec=specs[coordinator.participant_id],
            )
    else:
        with pytest.raises(ControllerError) as raised:
            _run_native_start(
                controller,
                request_id=request_id,
                coordinator=coordinator,
                runner_spec=specs[coordinator.participant_id],
            )
        assert raised.value.code in {"loader-failed", "uncertain-effect"}

    attempts = copy.deepcopy(runtime.open_attempts)
    calls = copy.deepcopy(runtime.calls)
    record = _operation_record(store, request_id)
    assert record["phase"] == "indeterminate"
    assert record["uncertainty"]
    assert runtime.sent == []
    assert runtime.prompts == []

    with pytest.raises(ControllerError) as raised:
        _run_native_start(
            controller,
            request_id=request_id,
            coordinator=coordinator,
            runner_spec=specs[coordinator.participant_id],
        )
    _assert_error(raised, "uncertain-effect")
    assert runtime.open_attempts == attempts
    assert runtime.calls == calls


def test_start_request_dedup_has_no_second_open_and_changed_specs_refuse():
    runtime = StartRuntime()
    controller, _, coordinator, workers, specs = _native_start_controller(
        runtime=runtime
    )
    request_id = "start-dedup"
    first = _run_native_start(
        controller,
        request_id=request_id,
        coordinator=coordinator,
        runner_spec=specs[coordinator.participant_id],
    )
    calls = copy.deepcopy(runtime.calls)
    same = _run_native_start(
        controller,
        request_id=request_id,
        coordinator=coordinator,
        runner_spec=copy.deepcopy(specs[coordinator.participant_id]),
    )
    assert _operation_id(same) == _operation_id(first)
    assert _value(same, "phase") == "ready-held"
    assert runtime.calls == calls

    # Keep the coordinator, lineage, session, and ownership unchanged.  Only
    # the semantic runner payload changes, so this exercises request-content
    # refusal rather than an identity or authority bypass.
    changed = copy.deepcopy(specs[coordinator.participant_id])
    changed["model"] = "different-native-model"
    with pytest.raises(ControllerError) as raised:
        _run_native_start(
            controller,
            request_id=request_id,
            coordinator=coordinator,
            runner_spec=changed,
        )
    _assert_error(raised, "invalid")
    assert runtime.calls == calls


def test_start_reload_reconciles_uncertain_native_coordinator_without_reopen():
    first_runtime = StartRuntime(uncertain_after_open="coordinator")
    controller, store, coordinator, workers, specs = _native_start_controller(
        runtime=first_runtime
    )
    request_id = "start-reconcile-uncertain"

    with pytest.raises(ControllerError) as raised:
        _run_native_start(
            controller,
            request_id=request_id,
            coordinator=coordinator,
            runner_spec=specs[coordinator.participant_id],
        )
    assert raised.value.code == "uncertain-effect"
    first_record = _operation_record(store, request_id)
    assert first_record["phase"] == "indeterminate"
    first_intents = first_record["metadata"]["launch_intents"]
    assert first_intents["coordinator"]["state"] == "in-progress"
    assert first_runtime.open_attempts == ["coordinator"]
    assert [participant_id for participant_id, _ in first_runtime.opened] == [
        "coordinator",
    ]
    accepted_uncertain_open = copy.deepcopy(
        first_runtime.open_evidence[coordinator.participant_id]
    )

    second_runtime = StartRuntime()
    reloaded = ManagedController(
        store,
        runtime=second_runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    second_runtime.controller = reloaded

    recovered = _run_recover(
        reloaded,
        first_record["operation_id"],
        7,
        {
            "operation_id": first_record["operation_id"],
            "generation": 7,
            "participants": {
                "coordinator": {"open": accepted_uncertain_open},
            },
        },
    )
    assert _value(recovered, "phase") == "ready-held"
    assert second_runtime.open_attempts == []
    assert second_runtime.calls == []

    resumed = _run_native_start(
        reloaded,
        request_id=request_id,
        coordinator=coordinator,
        runner_spec=specs[coordinator.participant_id],
    )
    assert _value(resumed, "phase") == "ready-held"
    assert second_runtime.open_attempts == []
    assert second_runtime.sent == []
    assert second_runtime.prompts == []
    final_record = _operation_record(store, request_id)
    assert final_record["phase"] == "ready-held"
    assert final_record["metadata"]["launch_intents"]["coordinator"]["state"] == "ready"


def test_start_recovery_reconciles_accepted_native_open_without_reopen():
    first_runtime = StartRuntime(uncertain_after_open="coordinator")
    controller, store, coordinator, workers, specs = _native_start_controller(
        runtime=first_runtime
    )
    request_id = "start-mode-aware-recovery"

    with pytest.raises(ControllerError) as raised:
        _run_native_start(
            controller,
            request_id=request_id,
            coordinator=coordinator,
            runner_spec=specs[coordinator.participant_id],
        )
    assert raised.value.code == "uncertain-effect"
    record = _operation_record(store, request_id)
    operation_id = record["operation_id"]
    intents = record["metadata"]["launch_intents"]
    assert first_runtime.open_attempts == ["coordinator"]
    assert [participant_id for participant_id, _ in first_runtime.opened] == [
        "coordinator",
    ]
    assert intents["coordinator"]["state"] == "in-progress"
    accepted_uncertain_open = copy.deepcopy(
        first_runtime.open_evidence[coordinator.participant_id]
    )

    second_runtime = StartRuntime()
    reloaded = ManagedController(
        store,
        runtime=second_runtime,
        clock=lambda: 1000.0,
        transcript_verifier=store.transcript_verifier,
    )
    second_runtime.controller = reloaded

    # Explicitly reconcile the already-crossed coordinator open boundary.  This
    # records the accepted runner identity and never calls runtime.open.
    recovered = _run_recover(
        reloaded,
        operation_id,
        7,
        {
            "operation_id": operation_id,
            "generation": 7,
            "participants": {
                "coordinator": {"open": accepted_uncertain_open},
            },
        },
    )
    assert _value(recovered, "phase") == "ready-held"
    assert second_runtime.open_attempts == []
    assert second_runtime.calls == []

    resumed = _run_native_start(
        reloaded,
        request_id=request_id,
        coordinator=coordinator,
        runner_spec=specs[coordinator.participant_id],
    )
    assert _value(resumed, "phase") == "ready-held"
    # The accepted coordinator boundary is durable ready state; a retry never
    # reopens the coordinator and there are no independent child opens.
    assert second_runtime.open_attempts == []
    assert not any(call[0] == "open" for call in second_runtime.calls)
    assert second_runtime.sent == []
    final = _operation_record(store, request_id)
    assert final["phase"] == "ready-held"
    assert final["metadata"]["launch_intents"]["coordinator"]["state"] == "ready"


def test_start_rejects_credential_bearing_spec_before_any_durable_state():
    runtime = StartRuntime()
    controller, store, coordinator, workers, specs = _native_start_controller(
        runtime=runtime
    )
    unsafe_specs = copy.deepcopy(specs)
    unsafe_specs[coordinator.participant_id]["environment"] = {
        "ANTHROPIC_API_KEY": "must-never-cross-controller-boundary",
    }

    with pytest.raises(ControllerError) as raised:
        _run_start(
            controller, request_id="start-credential-refused", generation=7,
            coordinator=coordinator, workers=workers, runner_specs=unsafe_specs,
        )
    _assert_error(raised, "unsupported")
    assert runtime.open_attempts == []
    assert runtime.calls == []
    assert store.documents == {}
    assert store.journal == []
    assert "ANTHROPIC_API_KEY" not in repr(store.documents)


def test_unenroll_state_reenroll_rolls_controller_to_higher_generation_for_start():
    runtime = CompletionRuntime(_successful_swap_statuses())
    controller, store, _ = _swap_roster(runtime)
    _run_swap(controller, request_id="rollover-source-swap")
    asyncio.run(controller.shutdown(7))
    unenrolled = controller.unenroll(7)
    assert unenrolled["phase"] == "complete"
    old_sessions = {
        COORDINATOR_SESSION,
        WORKER_A_SESSION,
        WORKER_B_SESSION,
        WORKER_C_SESSION,
    }
    assert old_sessions.issubset(set(controller.status()["session_history"]))
    assert controller.status()["participants"] == []

    # The state owner has committed unenrollment and re-enrolled generation 8.
    # Controller rollover must consume this authoritative owner record rather
    # than trusting a caller's larger integer by itself.  The new roster is a
    # native coordinator only; no old child session is rebound as a runner.
    store.owner = {
        "mode": "managed", "lane": MANAGED_LANE, "generation": 8,
        "daemon_id": "daemon-test",
    }
    store.lineage_claims = []
    store.lineage_claim_calls = []
    store.read_owner = lambda: copy.deepcopy(store.owner)
    store.read_lineage_claims = lambda: copy.deepcopy(store.lineage_claims)
    store.claim_lineage = NativeStartStore.claim_lineage.__get__(store)
    next_coordinator = _native_start_participant(
        participant_id="coordinator-next",
        session_id=ROLLOVER_COORDINATOR_SESSION,
    )
    _bind_source_transcript(store, next_coordinator)
    next_spec = _native_start_spec(
        next_coordinator, lineage_id="rollover-native-lineage",
    )
    next_runtime = StartRuntime()
    controller.runtime = next_runtime
    next_runtime.controller = controller

    started = _run_native_start(
        controller,
        request_id="rollover-start",
        generation=8,
        coordinator=next_coordinator,
        runner_spec=next_spec,
    )
    assert _value(started, "phase") == "ready-held"
    assert _value(started, "generation") == 8
    assert [participant_id for participant_id, _ in next_runtime.opened] == [
        "coordinator-next",
    ]
    history = set(controller.status()["session_history"])
    assert old_sessions.issubset(history)
    assert ROLLOVER_COORDINATOR_SESSION in history
    assert {
        item["session_id"] for item in controller.status()["archived_participants"]
    } == old_sessions

    before_old_request = copy.deepcopy(controller.status())
    before_old_calls = copy.deepcopy(next_runtime.calls)
    with pytest.raises(ControllerError) as raised:
        controller.submit(
            "old-generation-request", "coordinator-next", "payload://old-generation",
            generation=7,
        )
    _assert_error(raised, "stale-generation")
    assert controller.status() == before_old_request
    assert next_runtime.calls == before_old_calls


def test_start_retry_same_request_refuses_changed_native_semantic_payload():
    runtime = StartRuntime()
    controller, store, coordinator, workers, specs = _native_start_controller(
        runtime=runtime
    )
    first = _run_native_start(
        controller,
        request_id="start-semantic-retry",
        coordinator=coordinator,
        runner_spec=specs[coordinator.participant_id],
    )
    before_status = copy.deepcopy(controller.status())
    before_calls = copy.deepcopy(runtime.calls)
    before_claims = copy.deepcopy(store.claims)

    changed_cases = []
    changed_model = copy.deepcopy(specs[coordinator.participant_id])
    changed_model["model"] = "different-native-model"
    changed_cases.append(("model", changed_model))
    changed_definition = copy.deepcopy(specs[coordinator.participant_id])
    changed_definition["fingerprint"]["native_config"]["trusted_definitions"][
        "writer"
    ]["effort"] = "low"
    changed_cases.append(("trusted-definition-effort", changed_definition))

    for field, changed_spec in changed_cases:
        with pytest.raises(ControllerError) as raised:
            _run_native_start(
                controller,
                request_id="start-semantic-retry",
                coordinator=coordinator,
                runner_spec=changed_spec,
            )
        _assert_error(raised, "invalid")
        assert controller.status() == before_status, field
        assert runtime.calls == before_calls, field
        assert store.claims == before_claims, field

    same = _run_native_start(
        controller,
        request_id="start-semantic-retry",
        coordinator=coordinator,
        runner_spec=copy.deepcopy(specs[coordinator.participant_id]),
    )
    assert _operation_id(same) == _operation_id(first)
    assert _value(same, "phase") == "ready-held"
    assert runtime.calls == before_calls


# ---------------------------------------------------------------------------
# Native-lineage schema boundary (T005)
# ---------------------------------------------------------------------------

_NATIVE_SCHEMA_VERSION = 2
_NATIVE_ARCHITECTURE = "native-coordinator-lineage"


def _legacy_controller_snapshot() -> Dict[str, Any]:
    """Return the complete schema-1 controller snapshot from the prototype."""
    return {
        "schema": 1,
        "generation": 1,
        "coordinator_id": "coordinator-old",
        "active_operation_id": None,
        "participants": [
            {
                "participant_id": "coordinator-old",
                "session_id": "coordinator-session-old",
                "session_uuid": "coordinator-session-old",
                "session_name": "managed-coordinator-old",
                "bound_lane": MANAGED_LANE,
                "role": "coordinator",
                "parent_id": None,
                "task_id": "root-task-old",
                "mailbox_id": "mailbox-coordinator-old",
                "kind": "independent",
                "state": "held",
                "writer_claim": None,
                "read_only": False,
                "background": False,
                "detached": False,
                "model": None,
                "permission_mode": None,
                "fingerprint": None,
                "metadata": {},
            },
            {
                "participant_id": "worker-old",
                "session_id": "worker-session-old",
                "session_uuid": "worker-session-old",
                "session_name": "managed-worker-old",
                "bound_lane": MANAGED_LANE,
                "role": "worker",
                "parent_id": "coordinator-old",
                "task_id": "task-old",
                "mailbox_id": "mailbox-worker-old",
                "kind": "independent",
                "state": "held",
                "writer_claim": None,
                "read_only": False,
                "background": False,
                "detached": False,
                "model": None,
                "permission_mode": None,
                "fingerprint": None,
                "metadata": {},
            },
        ],
        "archived_participants": [],
        "session_history": ["coordinator-session-old", "worker-session-old"],
        "mailboxes": [
            {
                "message_id": "message-old",
                "request_id": "request-old",
                "sender_id": "coordinator-old",
                "recipient_id": "worker-old",
                "task_id": "task-old",
                "payload_ref": "payload-ref-old",
                "state": "queued",
                "generation": 1,
                "operation_id": None,
                "dispatch_attempt": 0,
                "runtime_ack": None,
                "metadata": {},
            }
        ],
        "operations": [],
        "requests": {},
        "checkpoints": [],
    }


def _legacy_independent_worker_controller_blob() -> Dict[str, Any]:
    """Return an arbitrary worker blob kept as supplemental schema evidence."""
    return {
        "schema_version": 1,
        "architecture": "independent-worker",
        "mode": "independent-workers",
        "participants": [{
            "participant_id": "worker-old",
            "session_id": "session-old",
            "session_uuid": "session-old",
            "uuid": "session-old",
            "mailbox_id": "mailbox-old",
            "mailbox": "mailbox-old",
            "runner_id": "runner-old",
            "process_group_id": "pg-old",
            "open": {"state": "active"},
            "release": {"state": "pending"},
        }],
        "mailboxes": [{
            "message_id": "message-old",
            "recipient_id": "worker-old",
            "mailbox_id": "mailbox-old",
        }],
    }


def _schema_refusal(error: ControllerError) -> None:
    assert error.code in {"schema-mismatch", "migration-required"}, (
        error.code, error.message
    )


def _state_store_for_controller(managed_workspace):
    """Resolve the real private state store without changing global HOME."""
    from lane_managed_state import ManagedStateStore, resolve_workspace

    helper = (
        managed_workspace.workspace_repo.parent
        / "controller-schema-workspace-helper"
        / "lanes-edit.sh"
    )
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if len(sys.argv) < 2 or sys.argv[1] != 'workspace-root':\n"
        "    sys.exit(64)\n"
        "sys.stdout.write(%r)\n"
        % (str(managed_workspace.workspace_repo.resolve()) + "\n"),
        encoding="utf-8",
    )
    helper.chmod(0o700)
    identity = resolve_workspace(
        managed_workspace.lane, env=managed_workspace.env, helper=helper,
    )
    return ManagedStateStore(identity)


def test_controller_schema_v1_snapshot_is_read_only_and_refused_before_load(
        managed_workspace):
    """A legacy snapshot cannot be reinterpreted as a native lineage."""
    store = _state_store_for_controller(managed_workspace)
    store.ensure_layout()
    path = store.identity.state_root / "controller.json"
    raw = json.dumps(
        _legacy_controller_snapshot(), ensure_ascii=True, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    path.write_bytes(raw)
    path.chmod(0o600)
    before = path.read_bytes()

    with pytest.raises(ControllerError) as raised:
        ManagedController(store)

    _schema_refusal(raised.value)
    assert path.read_bytes() == before


def test_controller_schema_v1_snapshot_blocks_status_writer_and_recovery(
        managed_workspace):
    """Every controller transaction reloads the schema before mutating it."""
    store = MemoryStore()
    controller = ManagedController(store)
    actions = (
        lambda: controller.status(),
        lambda: controller.begin_operation(
            request_id="legacy-operation", mode="swap", generation=1,
        ),
        lambda: asyncio.run(
            controller.recover(
                "legacy-operation", 1,
                {"participants": {"worker-old": {"status": {"state": "unknown"}}}},
            )
        ),
    )

    for legacy in (_legacy_controller_snapshot(),
                   _legacy_independent_worker_controller_blob()):
        store.documents["controller.json"] = copy.deepcopy(legacy)
        before = copy.deepcopy(store.documents["controller.json"])
        for action in actions:
            with pytest.raises(ControllerError) as raised:
                action()
            _schema_refusal(raised.value)
            assert store.documents["controller.json"] == before


def _native_record_types():
    """Import schema-v2 records only when their implementation exists."""
    from lane_managed_controller import ChildTaskRecord, LineageRecord

    return LineageRecord, ChildTaskRecord


def _native_lineage_payload(workspace: Path) -> Dict[str, Any]:
    payload = {
        "schema_version": _NATIVE_SCHEMA_VERSION,
        "architecture": _NATIVE_ARCHITECTURE,
        "lineage_id": "lineage-build-7",
        "lane": MANAGED_LANE,
        "owner_generation": 7,
        "lineage_generation": 3,
        "session_uuid": COORDINATOR_SESSION,
        "transcript": {"ref": "transcript://coordinator-build-7"},
        "workspace": str(workspace.resolve()),
        "common_dir": str(workspace.resolve()),
        "state": "held",
    }
    payload["workspace_claim"] = _native_workspace_claim_payload(payload)
    return payload


def _native_workspace_claim_payload(lineage: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the one workspace claim inherited by every native child."""
    return {
        "schema_version": _NATIVE_SCHEMA_VERSION,
        "architecture": _NATIVE_ARCHITECTURE,
        "record_kind": "workspace-claim",
        "claim_kind": "workspace",
        "lineage_id": lineage["lineage_id"],
        "owner_generation": lineage["owner_generation"],
        "lineage_generation": lineage["lineage_generation"],
        "lane": lineage["lane"],
        "lane_key": lineage.get("lane_key", lineage["lane"].casefold()),
        "host": lineage.get("host", "test-host"),
        "coordinator_session_uuid": lineage["session_uuid"],
        "workspace": lineage["workspace"],
        "common_dir": lineage["common_dir"],
        "repository": lineage.get("repository", lineage["workspace"]),
        "state": "held",
        "parent_read_only": lineage.get("read_only", False),
        "claimed_at": lineage.get("claimed_at", 1700000000.0),
    }


def _native_child_payload(lineage: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": _NATIVE_SCHEMA_VERSION,
        "architecture": _NATIVE_ARCHITECTURE,
        "lineage_id": lineage["lineage_id"],
        "agent_id": "agent-native-actual-1",
        "task_id": "task-native-actual-1",
        "type": "Agent",
        "tool_use_id": "tool-use-native-actual-1",
        "parent_links": {
            "session_uuid": lineage["session_uuid"],
            "parent_tool_use_id": "tool-use-coordinator-agent-1",
            "event_watermark": 17,
        },
        "transcript": {"ref": "transcript://agent-native-actual-1"},
        "status": "admitted",
        "model": "claude-sonnet-4-20250514",
        "effort": "medium",
        "custom_definition": {
            "name": "authorized-writer",
            "tools": ["Read", "Edit"],
            "permission_mode": "default",
        },
        "execution_mode": "foreground",
        "claim_ref": _native_workspace_claim_payload(lineage),
    }


def test_native_records_preserve_actual_ids_and_do_not_create_child_aliases(
        tmp_path: Path):
    """Only the coordinator has a session UUID; children retain native IDs."""
    LineageRecord, ChildTaskRecord = _native_record_types()
    lineage_payload = _native_lineage_payload(tmp_path)
    lineage = LineageRecord.from_dict(lineage_payload)
    child_payload = _native_child_payload(lineage_payload)
    child = ChildTaskRecord.from_dict(child_payload)

    assert lineage.lineage_id == lineage_payload["lineage_id"]
    assert lineage.session_uuid == COORDINATOR_SESSION
    assert child.agent_id == "agent-native-actual-1"
    assert child.task_id == "task-native-actual-1"
    assert child.tool_use_id == "tool-use-native-actual-1"

    lineage_wire = lineage.to_dict()
    child_wire = child.to_dict()
    assert lineage_wire["schema_version"] == _NATIVE_SCHEMA_VERSION
    assert lineage_wire["architecture"] == _NATIVE_ARCHITECTURE
    assert child_wire["agent_id"] == child_payload["agent_id"]
    assert child_wire["task_id"] == child_payload["task_id"]
    assert child_wire["parent_links"]["session_uuid"] == COORDINATOR_SESSION
    assert {
        "session_id", "session_uuid", "uuid", "mailbox", "mailbox_id",
        "process_group_id", "pgid", "runner_id",
    }.isdisjoint(child_wire)


def test_native_child_record_refuses_schema1_uuid_and_mailbox_aliases(
        tmp_path: Path):
    """Old participant aliases never become fabricated native child IDs."""
    _LineageRecord, ChildTaskRecord = _native_record_types()
    lineage_payload = _native_lineage_payload(tmp_path)
    legacy_child = _native_child_payload(lineage_payload)
    legacy_child.update({
        "schema_version": 1,
        "architecture": "independent-worker",
        "participant_id": "worker-old",
        "session_id": "session-old",
        "uuid": "session-old",
        "mailbox_id": "mailbox-old",
        "mailbox": "mailbox-old",
    })
    legacy_child.pop("agent_id")
    legacy_child.pop("task_id")

    with pytest.raises(ControllerError) as raised:
        ChildTaskRecord.from_dict(legacy_child)

    _schema_refusal(raised.value)


def test_readonly_coordinator_writable_child_and_nested_child_inherit_one_lineage_claim(
        tmp_path: Path):
    """Native writers inherit the lineage claim instead of becoming owners."""
    LineageRecord, ChildTaskRecord = _native_record_types()
    lineage_payload = _native_lineage_payload(tmp_path)
    lineage_payload["read_only"] = True
    # The workspace claim is the durable parent capability boundary.  A
    # read-only coordinator must publish the matching immutable claim field;
    # a stale writable-parent claim is a scope conflict, not an inheritance
    # hint.
    with pytest.raises(ControllerError) as raised:
        LineageRecord.from_dict(lineage_payload)
    assert raised.value.code == "ownership-conflict"
    lineage_payload["workspace_claim"]["parent_read_only"] = True
    lineage = LineageRecord.from_dict(lineage_payload)
    claim = lineage.to_dict()["workspace_claim"]

    child_payload = _native_child_payload(lineage_payload)
    child = ChildTaskRecord.from_dict(child_payload)
    child_wire = child.to_dict()
    assert claim["claim_kind"] == "workspace"
    assert claim["lineage_id"] == lineage.lineage_id
    assert child_wire["claim_ref"] == claim
    assert child_wire["claim_ref"]["lineage_id"] == lineage.lineage_id
    assert "agent_id" not in child_wire["claim_ref"]
    assert {"session_id", "session_uuid", "uuid", "mailbox", "mailbox_id",
            "process_group_id", "pgid", "runner_id"}.isdisjoint(child_wire)

    nested_payload = _native_child_payload(lineage_payload)
    nested_payload.update({
        "agent_id": "agent-native-nested-actual-2",
        "task_id": "task-native-nested-actual-2",
        "tool_use_id": "tool-use-native-nested-actual-2",
        "parent_links": {
            "session_uuid": lineage_payload["session_uuid"],
            "parent_agent_id": child_payload["agent_id"],
            "parent_task_id": child_payload["task_id"],
            "parent_tool_use_id": child_payload["tool_use_id"],
            "event_watermark": 18,
        },
    })
    nested = ChildTaskRecord.from_dict(nested_payload)
    nested_wire = nested.to_dict()
    assert nested_wire["agent_id"] == "agent-native-nested-actual-2"
    assert nested_wire["task_id"] == "task-native-nested-actual-2"
    assert nested_wire["parent_links"]["parent_agent_id"] == child_payload["agent_id"]
    assert nested_wire["claim_ref"] == claim
    assert nested_wire["claim_ref"]["lineage_id"] == lineage.lineage_id
    assert {"session_id", "session_uuid", "uuid", "mailbox", "mailbox_id",
            "process_group_id", "pgid", "runner_id"}.isdisjoint(nested_wire)


def test_isolated_native_child_claim_is_additional_and_keyed_by_actual_agent_task(
        tmp_path: Path):
    """An isolated worktree adds one exact child claim under the same lineage."""
    LineageRecord, ChildTaskRecord = _native_record_types()
    lineage_payload = _native_lineage_payload(tmp_path)
    lineage = LineageRecord.from_dict(lineage_payload)
    child_payload = _native_child_payload(lineage_payload)
    isolated_worktree = (tmp_path / "native-isolated-child").resolve()
    isolated_worktree.mkdir()
    dirty_file = isolated_worktree / "untracked.txt"
    dirty_file.write_text("keep native child work\n", encoding="utf-8")
    child_payload["claim_ref"] = _native_workspace_claim_payload(lineage_payload)
    child_payload["claim_ref"].update({
        "record_kind": "child-worktree-claim",
        "claim_kind": "child-worktree",
        "agent_id": child_payload["agent_id"],
        "task_id": child_payload["task_id"],
        "worktree": str(isolated_worktree),
    })
    child_payload["claim_ref"].pop("parent_read_only", None)

    child = ChildTaskRecord.from_dict(child_payload)
    child_wire = child.to_dict()
    isolated_claim = child_wire["claim_ref"]
    assert isolated_claim["claim_kind"] == "child-worktree"
    assert isolated_claim["lineage_id"] == lineage.lineage_id
    assert isolated_claim["agent_id"] == child_payload["agent_id"]
    assert isolated_claim["task_id"] == child_payload["task_id"]
    assert isolated_claim["worktree"] == str(isolated_worktree)
    assert {"session_id", "session_uuid", "uuid", "mailbox", "mailbox_id",
            "process_group_id", "pgid", "runner_id"}.isdisjoint(isolated_claim)
    assert dirty_file.read_text(encoding="utf-8") == "keep native child work\n"


@pytest.mark.parametrize(
    "change",
    [
        "unknown-lineage",
        "unknown-agent",
        "changed-lineage-generation",
        "changed-workspace",
    ],
)
def test_native_child_unknown_or_changed_immutable_claim_is_refused(
        tmp_path: Path, change: str):
    """A child cannot broaden or retarget its immutable lineage claim."""
    _LineageRecord, ChildTaskRecord = _native_record_types()
    lineage_payload = _native_lineage_payload(tmp_path)
    child_payload = _native_child_payload(lineage_payload)
    changed = copy.deepcopy(child_payload)
    claim = changed["claim_ref"]
    if change == "unknown-lineage":
        changed["lineage_id"] = "lineage-untracked"
    elif change == "unknown-agent":
        changed["claim_ref"]["agent_id"] = "agent-untracked"
    elif change == "changed-lineage-generation":
        claim["lineage_generation"] = lineage_payload["lineage_generation"] + 1
    else:
        claim["workspace"] = str((tmp_path / "different-workspace").resolve())

    with pytest.raises(ControllerError) as raised:
        ChildTaskRecord.from_dict(
            changed, expected_claim=child_payload["claim_ref"]
        )

    expected_code = {
        "unknown-lineage": "ownership-conflict",
        "unknown-agent": "invalid",
        "changed-lineage-generation": "ownership-conflict",
        "changed-workspace": "ownership-conflict",
    }[change]
    assert raised.value.code == expected_code


def test_native_records_bind_the_actual_state_claim_scope_without_stripping(
        managed_workspace, tmp_path: Path):
    """Controller records retain the complete claim returned by state."""
    LineageRecord, ChildTaskRecord = _native_record_types()
    state_store = _state_store_for_controller(managed_workspace)
    lineage_id = "lineage-state-scope"
    owner = state_store.enroll_managed(
        daemon_id="daemon-state-scope",
        lineage_id=lineage_id,
        coordinator_session_uuid=COORDINATOR_SESSION,
        coordinator_read_only=True,
    )
    lineage_generation = 1
    workspace_claim = state_store.claim_lineage_workspace(
        lineage_id=lineage_id,
        owner_generation=owner["generation"],
        lineage_generation=lineage_generation,
        workspace=str(state_store.identity.workspace_root.resolve()),
        common_dir=str(state_store.identity.common_dir.resolve()),
        repository=str(managed_workspace.project.resolve()),
        parent_read_only=True,
        coordinator_session_uuid=COORDINATOR_SESSION,
    )

    lineage_payload = {
        **_native_lineage_payload(Path(workspace_claim["workspace"])),
        "record_kind": "lineage",
        "lineage_id": lineage_id,
        "lane": workspace_claim["lane"],
        "owner_generation": owner["generation"],
        "lineage_generation": lineage_generation,
        "session_uuid": COORDINATOR_SESSION,
        "workspace": workspace_claim["workspace"],
        "common_dir": workspace_claim["common_dir"],
        "read_only": True,
        "workspace_claim": workspace_claim,
    }
    lineage = LineageRecord.from_dict(lineage_payload)

    child_root = (tmp_path / "state-scope-child").resolve()
    child_root.mkdir()
    child_claim = state_store.claim_child_worktree(
        lineage_id,
        worktree=str(child_root),
        repository=workspace_claim["repository"],
        coordinator_session_uuid=COORDINATOR_SESSION,
        owner_generation=owner["generation"],
        lineage_generation=lineage_generation,
        workspace=workspace_claim["workspace"],
        common_dir=workspace_claim["common_dir"],
        agent_id="agent-state-scope",
        task_id="task-state-scope",
    )
    child_payload = _native_child_payload(lineage_payload)
    child_payload.update({
        "record_kind": "child-task",
        "agent_id": child_claim["agent_id"],
        "task_id": child_claim["task_id"],
        "claim_ref": child_claim,
    })
    child = ChildTaskRecord.from_dict(child_payload)

    scope_fields = (
        "schema_version", "architecture", "lane", "lane_key", "host",
        "coordinator_session_uuid", "owner_generation", "lineage_generation",
        "lineage_id",
    )
    for claim in (workspace_claim, child_claim):
        for field_name in scope_fields:
            assert field_name in claim
            assert claim[field_name] == {
                "schema_version": 2,
                "architecture": _NATIVE_ARCHITECTURE,
                "lane": state_store.identity.lane,
                "lane_key": state_store.identity.lane_key,
                "host": state_store.identity.host,
                "coordinator_session_uuid": COORDINATOR_SESSION,
                "owner_generation": owner["generation"],
                "lineage_generation": lineage_generation,
                "lineage_id": lineage_id,
            }[field_name]

    lineage_wire = lineage.to_dict()
    child_wire = child.to_dict()
    assert lineage_wire["workspace_claim"] == workspace_claim
    assert child_wire["claim_ref"] == child_claim
    assert lineage_wire["lane"] == workspace_claim["lane"]
    assert lineage_wire["owner_generation"] == workspace_claim["owner_generation"]
    assert lineage_wire["lineage_generation"] == workspace_claim["lineage_generation"]
    assert child_wire["lineage_id"] == child_claim["lineage_id"] == lineage_id
    assert child_wire["agent_id"] == child_claim["agent_id"]
    assert child_wire["task_id"] == child_claim["task_id"]
    assert child_claim["workspace"] == workspace_claim["workspace"]
    assert child_wire["claim_ref"]["workspace"] == lineage.workspace

    # A hand-built claim that drops the owner/lane/schema binding is not a
    # valid substitute for the state-store result, for either record kind.
    stripped_workspace = {
        key: value for key, value in workspace_claim.items()
        if key not in {
            "schema_version", "architecture", "lane", "lane_key", "host",
            "coordinator_session_uuid", "owner_generation",
            "lineage_generation",
        }
    }
    invalid_lineage = copy.deepcopy(lineage_payload)
    invalid_lineage["workspace_claim"] = stripped_workspace
    with pytest.raises(ControllerError) as lineage_error:
        LineageRecord.from_dict(invalid_lineage)
    assert lineage_error.value.code in {
        "invalid", "ownership-conflict", "schema-mismatch",
    }

    mismatched_lineage = copy.deepcopy(lineage_payload)
    mismatched_lineage["workspace_claim"] = copy.deepcopy(workspace_claim)
    mismatched_lineage["workspace_claim"][
        "coordinator_session_uuid"
    ] = "99999999-9999-4999-8999-999999999999"
    with pytest.raises(ControllerError) as lineage_parent_error:
        LineageRecord.from_dict(mismatched_lineage)
    assert lineage_parent_error.value.code in {
        "invalid", "ownership-conflict", "schema-mismatch",
    }

    stripped_child = {
        key: value for key, value in child_claim.items()
        if key not in {
            "schema_version", "architecture", "lane", "lane_key", "host",
            "coordinator_session_uuid", "owner_generation",
            "lineage_generation",
        }
    }
    invalid_child = copy.deepcopy(child_payload)
    invalid_child["claim_ref"] = stripped_child
    with pytest.raises(ControllerError) as child_error:
        ChildTaskRecord.from_dict(invalid_child)
    assert child_error.value.code in {
        "invalid", "ownership-conflict", "schema-mismatch",
    }

    mismatched_child = copy.deepcopy(child_payload)
    mismatched_child["claim_ref"] = copy.deepcopy(child_claim)
    mismatched_child["claim_ref"][
        "coordinator_session_uuid"
    ] = "99999999-9999-4999-8999-999999999999"
    with pytest.raises(ControllerError) as child_parent_error:
        ChildTaskRecord.from_dict(mismatched_child)
    assert child_parent_error.value.code in {
        "invalid", "ownership-conflict", "schema-mismatch",
    }
