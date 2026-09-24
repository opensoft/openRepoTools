#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded synthetic-gateway probe for a real native Agent child.

This experiment is separate from the no-auth Gate 0 baseline. It uses a
loopback Messages endpoint and a literal dummy API key, never a real profile,
account, network, or model service. Reports contain no transcript or request
bodies. It can
report observed native stop facts, but it always reports support_claim as
false and never grants production capability.

The same GatewayState and response policy are used by the live container
observer and by the offline unit tests. The probe copies this file into the
disposable container instead of maintaining a second embedded implementation.
The ``positive-orphan`` and ``terminal-cleared`` modes are executable
selected-runtime candidates; they remain unsupported unless the runtime emits
the exact allowlisted orphan/clear lifecycle events.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass, field
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Mapping
from urllib.parse import unquote, urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import uuid


PINNED_SDK_VERSION = "0.2.153"
PINNED_CLI_VERSION = "2.1.273"
EXPECTED_MODEL = "claude-sonnet-4-20250514"
DUMMY_API_KEY = "sk-ant-loopback-dummy"
RESUME_SENTINEL = "__LANE_LOOPBACK_SESSION__"
MAX_HTTP_BODY = 1024 * 1024
MAX_REQUESTS = 32
MAX_RUNTIME_OUTPUT = 4 * 1024 * 1024
MAX_RUNTIME_SECONDS = 70
MAX_NATIVE_TASK_EVIDENCE = 64
MAX_NATIVE_TASK_TOKEN = 256
MAX_NATIVE_HOOK_EVIDENCE = 16
MAX_NATIVE_HOOK_REQUESTS = 128
MAX_NATIVE_HOOK_INPUT_BYTES = 16 * 1024
MAX_NATIVE_HOOK_REASONS = 16
MAX_NATIVE_HOOK_PATH = 4096
MAX_HISTORY_CONTENT_BYTES = 64 * 1024
MAX_HISTORY_SCAN_FILES = 128
MAX_HISTORY_SCAN_ENTRIES = 512
MAX_HISTORY_SCAN_DEPTH = 12
MAX_HISTORY_SCAN_BYTES = 8 * MAX_HISTORY_CONTENT_BYTES
# Fixture-tree custody includes SDK config JSON and other files that can be
# much larger than bounded history-prefix evidence transported between
# phases. Keep fixture-tree limits separate so complete files do not widen the
# history-observation or prefix protocol.
MAX_TWO_DOMAIN_TREE_FILE_BYTES = 512 * 1024
MAX_TWO_DOMAIN_TREE_BYTES = 2 * 1024 * 1024
BUSY_PARENT_BARRIER_TIMEOUT = 15.0
SOURCE_AGENT_NAME = "gate0-worker"
SOURCE_AGENT_TOOL_ID = "toolu-gate0-agent"
SOURCE_TOOL_ID = "toolu-gate0-bash"
SOURCE_PROMPT_MARKER = "Run the bounded native background worker."
TARGET_RELEASE_MARKER = "Continue the bounded native worker after release."
TWO_DOMAIN_HISTORY_QUERY_MODE = "two-domain-terminal-task-diagnostic-v1"
STRICT_HISTORY_QUERY_MODE = "strict-v1"
STOP_THEN_RESUME_V1 = "stop-then-resume-v1"
RUNTIME_ERROR_SITE_FUNCTIONS = frozenset({
    "runtime_main", "runtime_observe", "runtime_two_domain_target",
})
V1_SAVED_EDIT = b"stop-then-resume-v1 deterministic saved edit\n"

NATIVE_TASK_PHASES = {
    "source/setup",
    "source/drain",
    "target/startup",
}
NATIVE_TASK_EVENT_TYPES = {
    "system",
    "event",
    "control_response",
}
NATIVE_TASK_SUBTYPES = {
    "task_started",
    "task_progress",
    "task_updated",
    "task_notification",
}
NATIVE_TASK_TYPES = {"local_agent"}
NATIVE_TASK_STATUSES = {
    "started",
    "running",
    "progress",
    "stopped",
    "completed",
    "failed",
    "cancelled",
    "error",
    "killed",
}
NATIVE_TASK_TERMINAL_STATUSES = {
    "stopped",
    "completed",
    "failed",
    "cancelled",
    "error",
    "killed",
}
NATIVE_TASK_RECORD_SCHEMA = "native-task-observation-v2"
NATIVE_TASK_SOURCE_SEED_SCHEMA = "native-task-source-seed-envelope-v3"
NATIVE_TASK_AGENT_PROOF_SCHEMA = "native-task-agent-proof-v2"
NATIVE_TASK_SOURCE_IDENTITY_DIGESTS_SCHEMA = "native-task-source-identity-digests-v2"
NATIVE_TASK_SDK_SIDECAR_PROOF_SCHEMA = "native-task-sdk-sidecar-proof-v1"
NATIVE_HOOK_MISMATCH_DIAGNOSTIC_SCHEMA = "native-hook-tool-use-id-mismatch-v1"
NATIVE_HOOK_CALLBACK_IDS = {
    "SubagentStart": "native-subagent-start",
    "SubagentStop": "native-subagent-stop",
}
NATIVE_TASK_PROVENANCES = {
    "offline-observation",
    "source-observed",
    "target-observed",
    "source-terminal-seed",
}
NATIVE_TASK_SEED_UNAVAILABLE_REASONS = {
    "terminal-task-seed-not-observed",
    "terminal-task-seed-incomplete",
    "terminal-task-seed-identity-unlinked",
    "terminal-task-start-proof-unavailable",
    "terminal-task-agent-proof-unavailable",
    "terminal-task-hook-evidence-incomplete",
    "terminal-task-hook-evidence-ambiguous",
    "terminal-task-sdk-sidecar-evidence-incomplete",
    "terminal-task-sdk-sidecar-evidence-ambiguous",
    "terminal-task-sdk-sidecar-evidence-conflict",
    "terminal-task-notification-not-observed",
}
HISTORY_ATTRIBUTIONS = {"observed", "candidate", "unattributed"}
HISTORY_UNKNOWN_REASONS = {
    "missing",
    "missing-parent",
    "missing-child",
    "unattributed-child-history",
    "malformed",
    "invalid-limit",
    "oversized",
    "symlink",
    "outside-root",
    "not-regular",
    "read-failed",
    "unstable",
    "scan-overflow",
    "ambiguous",
    "identity-unavailable",
    "uncorrelated",
    "no-follow-unavailable",
    "nonblock-unavailable",
}

def digest(value: object) -> str | None:
    """Digest identifiers without retaining their values in evidence."""
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parent_identity_digest(identity: Mapping[str, object] | None) -> str | None:
    """Bind equality to the observed session UUID, not a result event UUID."""
    if not isinstance(identity, Mapping):
        return None
    session_id = identity.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    return _canonical_digest({"session_id": session_id})


class StopThenResumeV1Ledger:
    """Small durable ledger for the opt-in stop-then-resume experiment.

    This ledger deliberately keeps native source observations separate from
    harness cleanup observations.  A process-group kill can be recorded as
    cleanup evidence, but it cannot satisfy native completion or release
    authorization by itself.
    """

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.state_path = self.workspace / ".stop-then-resume-v1.json"
        self.release_path = self.workspace / ".stop-then-resume-v1.release.json"
        self.edit_path = self.workspace / "saved-edit.txt"
        self._state: dict[str, object] = {}
        if self.state_path.exists():
            self._state = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._reconcile_release_boundary()

    @staticmethod
    def _sync_directory(path: Path) -> None:
        try:
            directory_fd = os.open(path, os.O_RDONLY)
        except OSError as exc:
            raise RuntimeError("durable directory sync unavailable") from exc
        try:
            os.fsync(directory_fd)
        except OSError as exc:
            raise RuntimeError("durable directory sync failed") from exc
        finally:
            os.close(directory_fd)

    def _persist(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self.workspace),
            prefix=".stop-then-resume-v1.",
            suffix=".tmp",
            delete=False,
        )
        temporary_name = temporary.name
        try:
            os.chmod(temporary_name, 0o600)
            json.dump(self._state, temporary, sort_keys=True, separators=(",", ":"))
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary.close()
            os.replace(temporary_name, self.state_path)
            self._sync_directory(self.workspace)
        except BaseException:
            temporary.close()
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def _reconcile_release_boundary(self) -> None:
        if not self._state or not self.release_path.exists():
            return
        boundary = json.loads(self.release_path.read_text(encoding="utf-8"))
        expected = self._release_boundary()
        if (
            boundary != expected
            or not self._state.get("ready_to_resume")
            or bool(self._state.get("unknown_effects"))
            or not self._state.get("source_parent_identity_digest")
            or not self._state.get("pre_stop_history_digest")
        ):
            self._state["phase"] = "indeterminate"
            self._state["ready_to_resume"] = False
            self._state["release_persisted"] = False
            self._state["release_authorized"] = False
            self._state["target_creation_authorized"] = False
            self._state["reason_codes"] = ["release-boundary-mismatch"]
            return
        self._state["release_persisted"] = True
        self._state["release_authorized"] = True
        self._state["target_creation_authorized"] = not bool(
            self._state.get("target_launch_intent_persisted")
        )
        if not self._state.get("target_created"):
            self._state["phase"] = "release-authorized"

    def _release_boundary(self) -> dict[str, object]:
        return {
            "mode": STOP_THEN_RESUME_V1,
            "edit_hash": self._state.get("edit_hash"),
            "request_identity_digest": _canonical_digest(
                self._state.get("request_identity", {})
            ),
            "operation_metadata_digest": _canonical_digest(
                self._state.get("operation_metadata", {})
            ),
            "source_parent_identity_digest": self._state.get(
                "source_parent_identity_digest"
            ),
            "pre_stop_history_digest": self._state.get("pre_stop_history_digest"),
            "source_facts_digest": _canonical_digest(
                self._state.get("source_native_facts", {})
            ),
            "harness_facts_digest": _canonical_digest(
                self._state.get("harness_cleanup_facts", {})
            ),
            "unknown_effects": list(self._state.get("unknown_effects", [])),
        }

    def _release_boundary_matches(self) -> bool:
        if not self.release_path.exists():
            return False
        try:
            return (
                json.loads(self.release_path.read_text(encoding="utf-8"))
                == self._release_boundary()
            )
        except (OSError, ValueError):
            return False

    def _copy_state(self) -> dict[str, object]:
        return json.loads(json.dumps(self._state, sort_keys=True))

    def prepare(
        self,
        *,
        parent_identity: Mapping[str, object] | None = None,
        pre_stop_history: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        if self._state:
            return self.snapshot()
        self.workspace.mkdir(parents=True, exist_ok=True)
        if self.edit_path.exists():
            if self.edit_path.read_bytes() != V1_SAVED_EDIT:
                raise RuntimeError("saved edit is not the deterministic v1 edit")
        else:
            self.edit_path.write_bytes(V1_SAVED_EDIT)
        edit_hash = hashlib.sha256(self.edit_path.read_bytes()).hexdigest()
        parent_digest = _parent_identity_digest(parent_identity)
        history_digest = _canonical_digest(pre_stop_history) if pre_stop_history else None
        self._state = {
            "mode": STOP_THEN_RESUME_V1,
            "phase": "preflight",
            "request_identity": {
                "mode": STOP_THEN_RESUME_V1,
                "parent_identity_digest": parent_digest,
            },
            "operation_metadata": {
                "mode": STOP_THEN_RESUME_V1,
                "edit_hash": edit_hash,
                "pre_stop_history_digest": history_digest,
                "resume_arguments_digest": None,
                "source_manifest_digest": None,
            },
            "edit_hash": edit_hash,
            "pre_stop_history_digest": history_digest,
            "source_parent_identity_digest": parent_digest,
            "target_parent_identity_digest": None,
            "source_result_event_uuid_digest": None,
            "target_result_event_uuid_digest": None,
            "target_result_identity_observed": False,
            "source_native_facts": {},
            "harness_cleanup_facts": {},
            "unknown_effects": [],
            "unknown_effect_baseline_valid": False,
            "unknown_effect_refusal_demonstrated": False,
            "ready_to_resume": False,
            "release_requested": False,
            "release_persisted": False,
            "release_authorized": False,
            "target_creation_authorized": False,
            "target_created": False,
            "target_launch_intent_persisted": False,
            "retained_history_observed": False,
            "retained_history_scope": "parent-boundary-markers-only",
            "edit_unchanged": True,
            "source_termination_task_completed": False,
            "reason_codes": [],
        }
        self._persist()
        return self.snapshot()

    def record_pre_stop_facts(
        self,
        *,
        parent_identity: Mapping[str, object],
        pre_stop_history: Mapping[str, object],
        result_uuid_digest: str | None = None,
    ) -> dict[str, object]:
        if not self._state:
            raise RuntimeError("v1 ledger is not prepared")
        parent_digest = _parent_identity_digest(parent_identity)
        history_digest = _canonical_digest(pre_stop_history)
        self._state["source_parent_identity_digest"] = parent_digest
        self._state["pre_stop_history_digest"] = history_digest
        self._state["source_result_event_uuid_digest"] = result_uuid_digest
        request_identity = self._state["request_identity"]
        assert isinstance(request_identity, dict)
        request_identity["parent_identity_digest"] = parent_digest
        operation_metadata = self._state["operation_metadata"]
        assert isinstance(operation_metadata, dict)
        operation_metadata["pre_stop_history_digest"] = history_digest
        self._persist()
        return self.snapshot()

    def record_source_facts(
        self,
        *,
        native: Mapping[str, object],
        harness: Mapping[str, object],
    ) -> dict[str, object]:
        if not self._state:
            raise RuntimeError("v1 ledger is not prepared")
        unknown_effects = native.get("unknown_effects", [])
        if not isinstance(unknown_effects, list):
            unknown_effects = ["malformed-unknown-effects"]
        unknown_effects = [str(effect) for effect in unknown_effects]
        unparsed_frames = native.get("unparsed_frames", 0)
        if type(unparsed_frames) is not int or unparsed_frames < 0:
            unparsed_frames = -1
        protocol_errors = native.get("protocol_errors", [])
        if not isinstance(protocol_errors, list):
            protocol_errors = ["malformed-protocol-errors"]
        protocol_errors = [str(error) for error in protocol_errors]
        read_failed = native.get("read_failed") is True
        self._state["source_native_facts"] = {
            "interrupt_sent": bool(native.get("interrupt_sent")),
            "interrupt_receipt": bool(native.get("interrupt_receipt")),
            "child_terminal": bool(native.get("child_terminal")),
            "tool_terminal": bool(native.get("tool_terminal")),
            "unknown_effects": unknown_effects,
            "read_failed": read_failed,
            "unparsed_frames": unparsed_frames,
            "protocol_errors": protocol_errors,
        }
        self._state["harness_cleanup_facts"] = {
            "parent_process_exited": bool(harness.get("parent_process_exited")),
            "tracked_processes_excluded": bool(harness.get("tracked_processes_excluded")),
            "pg_kill_observed": bool(harness.get("pg_kill_observed")),
        }
        self._state["unknown_effects"] = unknown_effects
        native_complete = all(
            bool(self._state["source_native_facts"].get(name))
            for name in ("interrupt_sent", "interrupt_receipt", "child_terminal", "tool_terminal")
        )
        harness_excluded = all(
            bool(self._state["harness_cleanup_facts"].get(name))
            for name in ("parent_process_exited", "tracked_processes_excluded")
        )
        base_reasons: list[str] = []
        if not native_complete:
            base_reasons.append("source-native-terminal-proof-incomplete")
        if not harness_excluded:
            base_reasons.append("source-harness-exclusion-incomplete")
        if not self._state.get("source_parent_identity_digest"):
            base_reasons.append("source-parent-identity-not-observed")
        if not self._state.get("pre_stop_history_digest"):
            base_reasons.append("source-pre-stop-history-not-observed")
        if read_failed:
            base_reasons.append("source-read-failed")
        if unparsed_frames != 0:
            base_reasons.append("source-unparsed-frame-observed")
        if protocol_errors:
            base_reasons.append("source-protocol-error-observed")
        baseline_valid = not base_reasons
        self._state["unknown_effect_baseline_valid"] = baseline_valid
        ready = bool(
            native_complete
            and harness_excluded
            and self._state.get("source_parent_identity_digest")
            and self._state.get("pre_stop_history_digest")
            and not unknown_effects
            and baseline_valid
        )
        self._state["ready_to_resume"] = ready
        self._state["phase"] = "ready-to-resume" if ready else "indeterminate"
        if not baseline_valid:
            self._state["release_persisted"] = False
            self._state["release_authorized"] = False
            self._state["target_creation_authorized"] = False
        if unknown_effects and baseline_valid:
            self._state["release_persisted"] = False
            self._state["release_authorized"] = False
            self._state["target_creation_authorized"] = False
            self._state["reason_codes"] = ["unknown-effects"]
        elif base_reasons:
            self._state["reason_codes"] = sorted(set(base_reasons))
            if unknown_effects:
                self._state["reason_codes"].append(
                    "unknown-effect-setup-inconclusive"
                )
        self._persist()
        return self.snapshot()

    def bind_resume_spec(
        self,
        *,
        resume_arguments: list[object],
        source_manifest: Mapping[str, object],
    ) -> dict[str, object]:
        if not self._state:
            raise RuntimeError("v1 ledger is not prepared")
        arguments_digest = _canonical_digest(resume_arguments)
        manifest_digest = _canonical_digest(source_manifest)
        metadata = self._state["operation_metadata"]
        assert isinstance(metadata, dict)
        existing_arguments = metadata.get("resume_arguments_digest")
        existing_manifest = metadata.get("source_manifest_digest")
        if (
            existing_arguments not in {None, arguments_digest}
            or existing_manifest not in {None, manifest_digest}
        ):
            self._state["phase"] = "indeterminate"
            self._state["reason_codes"] = ["resume-spec-mismatch"]
            self._persist()
            raise RuntimeError("resume specification changed")
        metadata["resume_arguments_digest"] = arguments_digest
        metadata["source_manifest_digest"] = manifest_digest
        self._persist()
        return self.snapshot()

    def resume_spec_matches(
        self,
        *,
        resume_arguments: list[object],
        source_manifest: Mapping[str, object],
    ) -> bool:
        metadata = self._state.get("operation_metadata", {})
        if not isinstance(metadata, Mapping):
            return False
        return bool(
            metadata.get("resume_arguments_digest")
            == _canonical_digest(resume_arguments)
            and metadata.get("source_manifest_digest")
            == _canonical_digest(source_manifest)
        )

    def request_release(
        self,
        *,
        explicit: bool,
        unknown_effect: bool = False,
    ) -> dict[str, object]:
        if not self._state:
            raise RuntimeError("v1 ledger is not prepared")
        self._state["release_requested"] = bool(explicit)
        if not explicit:
            self._persist()
            return {
                "release_requested": False,
                "authorized": False,
                "release_persisted": False,
                "ready_to_resume": bool(self._state.get("ready_to_resume")),
                "target_creation_authorized": False,
                "reason_code": "explicit-release-required",
            }
        if unknown_effect and not self._state.get("unknown_effects"):
            self._state["unknown_effects"] = ["unknown-effect-arm"]
        if self._state.get("unknown_effects"):
            self._state["ready_to_resume"] = False
            self._state["phase"] = "indeterminate"
            self._state["release_persisted"] = False
            self._state["release_authorized"] = False
            self._state["target_creation_authorized"] = False
            if self._state.get("unknown_effect_baseline_valid"):
                self._state["reason_codes"] = ["unknown-effects"]
                self._state["unknown_effect_refusal_demonstrated"] = True
                reason_code = "unknown-effects"
            else:
                self._state["reason_codes"] = [
                    "unknown-effect-setup-inconclusive"
                ]
                reason_code = "unknown-effect-setup-inconclusive"
            self._persist()
            return {
                "release_requested": True,
                "authorized": False,
                "release_persisted": False,
                "ready_to_resume": False,
                "target_creation_authorized": False,
                "reason_code": reason_code,
            }
        if (
            self._state.get("target_launch_intent_persisted")
            and not self._state.get("target_created")
        ):
            self._state["phase"] = "indeterminate"
            self._state["target_creation_authorized"] = False
            self._state["reason_codes"] = ["target-launch-indeterminate"]
            self._persist()
            return {
                "release_requested": True,
                "authorized": False,
                "release_persisted": bool(self._state.get("release_persisted")),
                "ready_to_resume": False,
                "target_creation_authorized": False,
                "reason_code": "target-launch-indeterminate",
            }
        if self._state.get("release_authorized") and self.release_path.exists():
            if self.release_path.read_text(encoding="utf-8") != json.dumps(
                self._release_boundary(), sort_keys=True, separators=(",", ":")
            ):
                self._state["phase"] = "indeterminate"
                self._state["ready_to_resume"] = False
                self._state["release_persisted"] = False
                self._state["release_authorized"] = False
                self._state["target_creation_authorized"] = False
                self._state["reason_codes"] = ["release-boundary-mismatch"]
                self._persist()
                return {
                    "release_requested": True,
                    "authorized": False,
                    "release_persisted": False,
                    "ready_to_resume": False,
                    "target_creation_authorized": False,
                    "reason_code": "release-boundary-mismatch",
                }
            self._persist()
            return {
                "release_requested": True,
                "authorized": True,
                "release_persisted": True,
                "ready_to_resume": bool(self._state.get("ready_to_resume")),
                "target_creation_authorized": bool(
                    self._state.get("target_creation_authorized")
                ),
            }
        if not self._state.get("ready_to_resume"):
            self._state["phase"] = "indeterminate"
            self._state["reason_codes"] = ["source-not-ready"]
            self._persist()
            return {
                "release_requested": True,
                "authorized": False,
                "release_persisted": False,
                "ready_to_resume": False,
                "target_creation_authorized": False,
                "reason_code": "source-not-ready",
            }
        boundary = self._release_boundary()
        if self.release_path.exists():
            existing = json.loads(self.release_path.read_text(encoding="utf-8"))
            if existing != boundary:
                self._state["phase"] = "indeterminate"
                self._state["reason_codes"] = ["release-boundary-mismatch"]
                self._persist()
                return {
                    "release_requested": True,
                    "authorized": False,
                    "release_persisted": False,
                    "ready_to_resume": False,
                    "target_creation_authorized": False,
                    "reason_code": "release-boundary-mismatch",
                }
            self._sync_directory(self.workspace)
        else:
            with self.release_path.open("x", encoding="utf-8") as boundary_file:
                os.chmod(self.release_path, 0o600)
                json.dump(boundary, boundary_file, sort_keys=True, separators=(",", ":"))
                boundary_file.flush()
                os.fsync(boundary_file.fileno())
            self._sync_directory(self.workspace)
        self._state["release_persisted"] = True
        self._state["release_authorized"] = True
        self._state["target_creation_authorized"] = True
        self._state["phase"] = "release-authorized"
        self._state["reason_codes"] = []
        self._persist()
        return {
            "release_requested": True,
            "authorized": True,
            "release_persisted": True,
            "ready_to_resume": True,
            "target_creation_authorized": True,
        }

    def record_launch_intent(self) -> dict[str, object]:
        if not (
            self._state.get("release_authorized")
            and self._state.get("release_persisted")
            and self._state.get("target_creation_authorized")
            and self.release_path.exists()
        ):
            raise RuntimeError("target launch intent is not release-authorized")
        if not self._release_boundary_matches():
            self._state["phase"] = "indeterminate"
            self._state["ready_to_resume"] = False
            self._state["release_persisted"] = False
            self._state["release_authorized"] = False
            self._state["target_creation_authorized"] = False
            self._state["reason_codes"] = ["release-boundary-mismatch"]
            self._persist()
            raise RuntimeError("release boundary is not current")
        if self._state.get("target_launch_intent_persisted"):
            return self.snapshot()
        self._state["target_launch_intent_persisted"] = True
        self._state["target_creation_authorized"] = False
        self._state["phase"] = "target-starting"
        self._persist()
        return self.snapshot()

    def record_target_facts(
        self,
        *,
        parent_identity: Mapping[str, object],
        retained_history: bool,
        edit_hash: str | None,
        result_uuid_digest: str | None = None,
        result_identity_observed: bool = False,
        retained_history_scope: str = "parent-boundary-markers-only",
        target_created: bool = True,
    ) -> dict[str, object]:
        if target_created and not (
            self._state.get("release_authorized")
            and self._state.get("release_persisted")
            and self.release_path.exists()
            and self._state.get("target_launch_intent_persisted")
            and self._release_boundary_matches()
        ):
            raise RuntimeError("target creation is not release-authorized")
        self._state["target_created"] = bool(target_created)
        self._state["target_parent_identity_digest"] = _parent_identity_digest(
            parent_identity
        )
        self._state["target_result_event_uuid_digest"] = result_uuid_digest
        self._state["target_result_identity_observed"] = bool(
            result_identity_observed
        )
        self._state["retained_history_observed"] = bool(retained_history)
        self._state["retained_history_scope"] = retained_history_scope
        self._state["edit_unchanged"] = bool(edit_hash == self._state.get("edit_hash"))
        if target_created:
            self._state["phase"] = "released"
        self._persist()
        return self.snapshot()

    def snapshot(self) -> dict[str, object]:
        return self._copy_state()

    def report(self) -> dict[str, object]:
        current_edit_hash = None
        if self.edit_path.exists():
            current_edit_hash = hashlib.sha256(self.edit_path.read_bytes()).hexdigest()
        edit_unchanged = current_edit_hash == self._state.get("edit_hash")
        exact_parent_identity = bool(
            self._state.get("source_parent_identity_digest")
            and self._state.get("target_parent_identity_digest")
            and self._state.get("source_parent_identity_digest")
            == self._state.get("target_parent_identity_digest")
        )
        history_retained = bool(
            self._state.get("pre_stop_history_digest")
            and self._state.get("retained_history_observed")
        )
        boundary_matches = False
        if self.release_path.exists():
            try:
                boundary_matches = (
                    json.loads(self.release_path.read_text(encoding="utf-8"))
                    == self._release_boundary()
                )
            except (OSError, ValueError):
                boundary_matches = False
        release_valid = bool(
            self._state.get("release_authorized")
            and self._state.get("release_persisted")
            and self._state.get("target_launch_intent_persisted")
            and boundary_matches
            and not self._state.get("unknown_effects")
        )
        unknown_effects = list(self._state.get("unknown_effects", []))
        reason_codes = list(self._state.get("reason_codes", []))
        if unknown_effects:
            reason_codes = [
                "unknown-effects"
                if self._state.get("unknown_effect_refusal_demonstrated")
                else "unknown-effect-setup-inconclusive"
            ]
        elif not reason_codes and not (
            release_valid
            and self._state.get("target_created")
            and exact_parent_identity
            and self._state.get("target_result_identity_observed")
            and history_retained
            and edit_unchanged
        ):
            reason_codes = ["exact-restoration-not-observed"]
        return {
            "mode": STOP_THEN_RESUME_V1,
            "request_identity": self._state.get("request_identity", {}),
            "operation_metadata": self._state.get("operation_metadata", {}),
            "resume_spec_bound": bool(
                isinstance(self._state.get("operation_metadata"), Mapping)
                and self._state["operation_metadata"].get(
                    "resume_arguments_digest"
                )
                and self._state["operation_metadata"].get(
                    "source_manifest_digest"
                )
            ),
            "phase": self._state.get("phase", "indeterminate"),
            "ready_to_resume": bool(self._state.get("ready_to_resume")),
            "release_requested": bool(self._state.get("release_requested")),
            "release_persisted": bool(self._state.get("release_persisted")),
            "release_authorized": bool(self._state.get("release_authorized")),
            "target_creation_authorized": bool(self._state.get("target_creation_authorized")),
            "target_launch_intent_persisted": bool(
                self._state.get("target_launch_intent_persisted")
            ),
            "target_created": bool(self._state.get("target_created")),
            "restoration_verdict": (
                "positive"
                if release_valid
                and self._state.get("target_created")
                and exact_parent_identity
                and self._state.get("target_result_identity_observed")
                and history_retained
                and edit_unchanged
                else "inconclusive"
            ),
            "exact_parent_identity": "observed" if exact_parent_identity else "unknown",
            "target_result_identity": (
                "observed"
                if self._state.get("target_result_identity_observed")
                else "unknown"
            ),
            "pre_stop_history_retained": "observed" if history_retained else "unknown",
            "retained_history_scope": self._state.get(
                "retained_history_scope", "parent-boundary-markers-only"
            ),
            "child_history_retained": "unverified",
            "source_result_event_uuid_digest": self._state.get(
                "source_result_event_uuid_digest"
            ),
            "target_result_event_uuid_digest": self._state.get(
                "target_result_event_uuid_digest"
            ),
            "edit_hash": self._state.get("edit_hash"),
            "edit_unchanged": edit_unchanged,
            "unknown_effects": unknown_effects,
            "unknown_effect_baseline_valid": bool(
                self._state.get("unknown_effect_baseline_valid")
            ),
            "unknown_effect_refusal_demonstrated": bool(
                self._state.get("unknown_effect_refusal_demonstrated")
            ),
            "source_native_facts": self._state.get("source_native_facts", {}),
            "harness_cleanup_facts": self._state.get("harness_cleanup_facts", {}),
            "source_proof_scope": "tracked-fixture-only",
            "source_termination_task_completed": False,
            "reason_codes": reason_codes,
            "support_claim": False,
        }


def route(path: str) -> str:
    return urlsplit(path).path


def _json_object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


@dataclass
class GatewayState:
    """Thread-safe counters and one strict scripted response state machine."""

    phase: str = "source"
    stop_requested: bool = False
    parent_posts: int = 0
    child_posts: int = 0
    agent_responses: int = 0
    bash_responses: int = 0
    request_count: int = 0
    parent_messages_seen: int = 0
    first_parent_declared_tool_names: list[str] = field(default_factory=list)
    first_parent_agent_schema_has_worker: bool = False
    second_parent_agent_result: dict[str, object] = field(default_factory=dict)
    parent_request_records: list[dict[str, object]] = field(default_factory=list)
    agent_schema_has_worker_observed: bool = False
    source_agent_response_sent: bool = False
    source_agent_tool_name: str | None = None
    target_release_history: dict[str, object] = field(default_factory=dict)
    protocol_errors: list[str] = field(default_factory=list)
    route_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    requests: list[dict[str, object]] = field(default_factory=list)
    child_agent_header_digests: set[str] = field(default_factory=set)
    child_agent_decoded_digests: set[str] = field(default_factory=set)
    control_entry_epoch_id: str | None = None
    control_entry_epoch_closed: bool = False
    control_entry_epoch_start_request_index: int | None = None
    control_entry_epoch_end_request_index: int | None = None
    control_entry_epoch_start_phase: str | None = None
    control_entry_epoch_end_phase: str | None = None
    control_entry_epoch_inference_attempts: int = 0
    control_entry_epoch_phase_counts: dict[str, int] = field(default_factory=dict)
    control_entry_epoch_phases: list[str] = field(default_factory=list)
    control_entry_epoch_parent_settled_at_entry: bool | None = None
    control_entry_epoch_begin_calls: int = 0
    message_arrival_count: int = 0
    request_arrival_count: int = 0
    request_arrivals: list[dict[str, object]] = field(default_factory=list)
    message_arrivals_overflow: bool = False
    startup_observation_active: bool = False
    startup_observation_start_arrival_index: int | None = None
    startup_observation_end_arrival_index: int | None = None
    startup_observation_closed: bool = False
    history_query_nonce: str | None = field(default=None, repr=False)
    history_query_challenge: str | None = field(default=None, repr=False)
    history_query_request_count: int = 0
    history_query_request_witness: dict[str, object] = field(default_factory=dict)
    history_query_response_write_count: int = 0
    history_query_response_write_succeeded: bool = False
    history_query_response_write_failed: bool = False
    history_query_response_message_id_digest: str | None = None
    history_query_window_closed: bool = False
    busy_parent_enabled: bool = False
    busy_parent_barrier_timeout: float = BUSY_PARENT_BARRIER_TIMEOUT
    busy_parent_barrier_event: threading.Event = field(
        default_factory=threading.Event,
        repr=False,
    )
    busy_parent_release_event: threading.Event = field(
        default_factory=threading.Event,
        repr=False,
    )
    busy_parent_continuation_classified: bool = False
    busy_parent_barrier_pending: bool = False
    busy_parent_barrier_waiting: bool = False
    busy_parent_barrier_release_requested: bool = False
    busy_parent_barrier_released_before_control: bool = False
    busy_parent_barrier_released_after_control: bool = False
    busy_parent_barrier_pending_at_control_entry: bool = False
    busy_parent_barrier_waiting_at_control_entry: bool = False
    busy_parent_barrier_expired: bool = False
    busy_parent_barrier_response_completed: bool = False
    busy_parent_response_write_started: bool = False
    busy_parent_response_write_succeeded: bool = False
    busy_parent_response_write_failed: bool = False
    busy_parent_handler_returned: bool = False
    busy_parent_request_arrival_index: int | None = None
    busy_parent_control_entry_observed: bool = False
    busy_parent_child_active_pre_entry: bool = False
    busy_parent_bash_active_pre_entry: bool = False
    busy_parent_task_id_digest: str | None = None
    busy_parent_process_identity_digest: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @staticmethod
    def _validate_phase(phase: str) -> None:
        if phase not in {
            "source", "source-drain", "source-crash", "target-held",
            "target-release", "target-diagnostic-query",
            "target-query-closed",
        }:
            raise ValueError("unknown probe phase")

    def set_phase(self, phase: str) -> None:
        self._validate_phase(phase)
        with self.lock:
            self.phase = phase
            if (
                self.control_entry_epoch_id is not None
                and not self.control_entry_epoch_closed
                and (not self.control_entry_epoch_phases
                     or self.control_entry_epoch_phases[-1] != phase)
            ):
                self.control_entry_epoch_phases.append(phase)

    def _begin_control_entry_epoch_locked(self, *, parent_settled: bool) -> bool:
        self.control_entry_epoch_begin_calls += 1
        if self.control_entry_epoch_id is not None:
            return False
        self.control_entry_epoch_id = "control-entry-" + uuid.uuid4().hex
        self.control_entry_epoch_closed = False
        self.control_entry_epoch_start_request_index = self.message_arrival_count + 1
        self.control_entry_epoch_end_request_index = None
        self.control_entry_epoch_start_phase = self.phase
        self.control_entry_epoch_end_phase = None
        self.control_entry_epoch_inference_attempts = 0
        self.control_entry_epoch_phase_counts = {}
        self.control_entry_epoch_phases = [self.phase]
        self.control_entry_epoch_parent_settled_at_entry = bool(parent_settled)
        return True

    def begin_control_entry_epoch(self, *, parent_settled: bool) -> None:
        """Start the sticky account-control observation boundary once.

        A repeated begin is deliberately idempotent: phase changes and an
        accidental second begin cannot erase earlier request evidence.
        """
        with self.lock:
            self._begin_control_entry_epoch_locked(parent_settled=parent_settled)

    def begin_busy_parent_control_entry(
        self,
        *,
        task_id: str,
        process_identity_digest: str,
        child_active_pre_entry: bool,
        bash_active_pre_entry: bool,
    ) -> bool:
        """Admit busy control only with positive pre-entry fixture evidence."""
        with self.lock:
            if (
                not self.busy_parent_enabled
                or not self.busy_parent_continuation_classified
                or not self.busy_parent_barrier_pending
                or not self.busy_parent_barrier_waiting
                or self.busy_parent_barrier_release_requested
                or self.busy_parent_control_entry_observed
                or self.control_entry_epoch_id is not None
            ):
                return False
            if (
                not isinstance(task_id, str)
                or not task_id
                or not child_active_pre_entry
                or not bash_active_pre_entry
                or not isinstance(process_identity_digest, str)
                or not process_identity_digest
            ):
                return False
            self.busy_parent_control_entry_observed = True
            self.busy_parent_child_active_pre_entry = bool(child_active_pre_entry)
            self.busy_parent_bash_active_pre_entry = bool(bash_active_pre_entry)
            self.busy_parent_barrier_pending_at_control_entry = (
                self.busy_parent_barrier_pending
            )
            self.busy_parent_barrier_waiting_at_control_entry = (
                self.busy_parent_barrier_waiting
            )
            self.busy_parent_task_id_digest = digest(task_id)
            self.busy_parent_process_identity_digest = process_identity_digest
            self._begin_control_entry_epoch_locked(parent_settled=False)
            return True

    def release_control_entry_epoch(self, *, next_phase: str | None = None) -> None:
        """Close the epoch and target-release transition under one lock."""
        if next_phase is not None:
            self._validate_phase(next_phase)
        with self.lock:
            if self.control_entry_epoch_id is not None and not self.control_entry_epoch_closed:
                self.control_entry_epoch_closed = True
                self.control_entry_epoch_end_request_index = self.message_arrival_count
                self.control_entry_epoch_end_phase = self.phase
            if next_phase is not None:
                self.phase = next_phase

    def begin_startup_observation(self) -> dict[str, object]:
        """Start request-arrival accounting before the target process exists."""
        with self.lock:
            if self.startup_observation_active or self.startup_observation_closed:
                raise RuntimeError("target startup observation was already selected")
            self.startup_observation_start_arrival_index = (
                self.request_arrival_count + 1
            )
            self.startup_observation_active = True
            return self._startup_observation_snapshot_locked()

    def close_startup_observation(self) -> dict[str, object]:
        with self.lock:
            if self.startup_observation_start_arrival_index is None:
                return self._startup_observation_snapshot_locked()
            if self.startup_observation_active:
                self.startup_observation_end_arrival_index = self.request_arrival_count
                self.startup_observation_active = False
                self.startup_observation_closed = True
            return self._startup_observation_snapshot_locked()

    def _startup_observation_snapshot_locked(self) -> dict[str, object]:
        start = self.startup_observation_start_arrival_index
        end = (
            self.startup_observation_end_arrival_index
            if self.startup_observation_closed
            else self.request_arrival_count
        )
        rows = [
            row for row in self.request_arrivals
            if isinstance(start, int) and isinstance(end, int)
            and start <= row.get("request_arrival_index", 0) <= end
        ]
        return {
            "enabled": isinstance(start, int),
            "closed": self.startup_observation_closed,
            "start_arrival_index": start,
            "end_arrival_index": end,
            "request_arrival_count": len(rows),
            "messages_route_arrival_count": sum(
                row.get("route") == "/v1/messages" for row in rows
            ),
            "other_route_arrival_count": sum(
                row.get("route") != "/v1/messages" for row in rows
            ),
            "parent_arrival_count": sum(
                row.get("agent_header_present") is False for row in rows
            ),
            "child_arrival_count": sum(
                row.get("agent_header_present") is True for row in rows
            ),
            "unclassified_arrival_count": sum(
                row.get("agent_header_present") is None for row in rows
            ),
            "in_flight_count": sum(row.get("completed") is not True for row in rows),
            "overflow": self.message_arrivals_overflow,
        }

    def _request_arrival_report_locked(self) -> dict[str, object]:
        by_phase_route: dict[str, dict[str, int]] = {}
        in_flight = 0
        for row in self.request_arrivals:
            phase = row.get("phase")
            route_value = row.get("route")
            if not isinstance(phase, str) or not isinstance(route_value, str):
                continue
            routes = by_phase_route.setdefault(phase, {})
            routes[route_value] = routes.get(route_value, 0) + 1
            if row.get("completed") is not True:
                in_flight += 1
        return {
            "arrival_count": self.request_arrival_count,
            "arrival_count_by_phase_route": {
                phase: dict(sorted(routes.items()))
                for phase, routes in sorted(by_phase_route.items())
            },
            "in_flight_count": in_flight,
            "overflow": self.message_arrivals_overflow,
        }

    def request_arrival_report(self) -> dict[str, object]:
        with self.lock:
            return self._request_arrival_report_locked()

    def observe_messages_arrival(
        self,
        *,
        agent_header_present: bool | None = None,
    ) -> int:
        """Observe one loopback POST arrival before body validation or reading."""
        with self.lock:
            self.message_arrival_count += 1
            arrival_index = self.message_arrival_count
            self.request_arrival_count += 1
            request_arrival_index = self.request_arrival_count
            if len(self.request_arrivals) < MAX_REQUESTS + 1:
                self.request_arrivals.append({
                    "request_arrival_index": request_arrival_index,
                    "arrival_index": arrival_index,
                    "route": "/v1/messages",
                    "phase": self.phase,
                    "agent_header_present": agent_header_present,
                    "completed": False,
                })
            else:
                self.message_arrivals_overflow = True
            if (
                self.control_entry_epoch_id is not None
                and not self.control_entry_epoch_closed
            ):
                self.control_entry_epoch_inference_attempts += 1
                self.control_entry_epoch_phase_counts[self.phase] = (
                    self.control_entry_epoch_phase_counts.get(self.phase, 0) + 1
                )
            return arrival_index

    def observe_other_request_arrival(self, path: str) -> int:
        """Observe non-message HTTP requests in the same startup epoch."""
        with self.lock:
            self.request_arrival_count += 1
            request_arrival_index = self.request_arrival_count
            if len(self.request_arrivals) < MAX_REQUESTS + 1:
                self.request_arrivals.append({
                    "request_arrival_index": request_arrival_index,
                    "arrival_index": None,
                    "route": route(path),
                    "phase": self.phase,
                    "agent_header_present": None,
                    "completed": False,
                })
            else:
                self.message_arrivals_overflow = True
            return request_arrival_index

    def complete_messages_arrival(self, arrival_index: int | None) -> None:
        if type(arrival_index) is not int:
            return
        with self.lock:
            for row in self.request_arrivals:
                if row.get("arrival_index") == arrival_index:
                    row["completed"] = True
                    return

    def request_arrival_index_for_message(
        self,
        arrival_index: int | None,
    ) -> int | None:
        if type(arrival_index) is not int:
            return None
        with self.lock:
            for row in self.request_arrivals:
                if row.get("arrival_index") == arrival_index:
                    value = row.get("request_arrival_index")
                    return value if type(value) is int else None
        return None

    def complete_request_arrival(self, request_arrival_index: int | None) -> None:
        if type(request_arrival_index) is not int:
            return
        with self.lock:
            for row in self.request_arrivals:
                if row.get("request_arrival_index") == request_arrival_index:
                    row["completed"] = True
                    return

    def configure_history_query(self, nonce: str, challenge: str) -> None:
        if (not isinstance(nonce, str) or len(nonce) < 32
                or not isinstance(challenge, str) or len(challenge) < 32
                or nonce == challenge):
            raise ValueError("diagnostic history query tokens are invalid")
        with self.lock:
            self.history_query_nonce = nonce
            self.history_query_challenge = challenge
            self.history_query_request_count = 0
            self.history_query_request_witness = {}
            self.history_query_response_write_count = 0
            self.history_query_response_write_succeeded = False
            self.history_query_response_write_failed = False
            self.history_query_response_message_id_digest = None
            self.history_query_window_closed = False

    @staticmethod
    def _diagnostic_query_tool_facts(
        request: object,
        *,
        nonce: str | None,
    ) -> dict[str, object]:
        """Count only direct, role-correct blocks in the message history."""
        messages = request.get("messages") if isinstance(request, Mapping) else None
        if not isinstance(messages, list):
            return {
                "source_agent_tool_use_count": 0,
                "source_agent_tool_result_count": 0,
                "exact_source_agent_tool_use_count": 0,
                "all_tool_use_count": 0,
                "all_tool_result_count": 0,
                "history_order_valid": False,
                "walk_overflow": False,
                "nested_tool_activity": False,
                "malformed_history": True,
            }

        def has_nested_tool_activity(value: object, depth: int = 0) -> bool:
            if depth > 20:
                return True
            if isinstance(value, Mapping):
                if value.get("type") in {"tool_use", "tool_result"}:
                    return True
                return any(
                    has_nested_tool_activity(child, depth + 1)
                    for child in value.values()
                )
            if isinstance(value, (list, tuple)):
                return any(
                    has_nested_tool_activity(child, depth + 1)
                    for child in value
                )
            return False

        source_tool_use_count = 0
        source_agent_use_count = 0
        matching_tool_result_count = 0
        all_tool_use_count = 0
        all_tool_result_count = 0
        source_marker_indices: list[int] = []
        nonce_indices: list[int] = []
        tool_use_indices: list[int] = []
        tool_result_indices: list[int] = []
        visited = 0
        overflow = False
        nested_tool_activity = False
        malformed_history = False
        for message_index, message in enumerate(messages):
            if not isinstance(message, Mapping):
                malformed_history = True
                continue
            role = message.get("role")
            content = message.get("content")
            if isinstance(content, str):
                content_items: list[object] = [content]
            elif isinstance(content, list):
                content_items = content
            else:
                malformed_history = True
                continue
            for block in content_items:
                visited += 1
                if visited > 20000:
                    overflow = True
                    break
                if isinstance(block, str):
                    text_value = block
                    block_type = None
                elif isinstance(block, Mapping):
                    block_type = block.get("type")
                    text_value = block.get("text") if block_type == "text" else None
                    if block_type == "tool_use":
                        all_tool_use_count += 1
                        if role == "assistant" and block.get("id") == SOURCE_AGENT_TOOL_ID:
                            source_tool_use_count += 1
                            tool_use_indices.append(message_index)
                            if block.get("name") == "Agent":
                                source_agent_use_count += 1
                        else:
                            malformed_history = True
                        if has_nested_tool_activity(block.get("input")):
                            nested_tool_activity = True
                    elif block_type == "tool_result":
                        all_tool_result_count += 1
                        if (role == "user"
                                and block.get("tool_use_id") == SOURCE_AGENT_TOOL_ID):
                            matching_tool_result_count += 1
                            tool_result_indices.append(message_index)
                        else:
                            malformed_history = True
                        if has_nested_tool_activity(block.get("content")):
                            nested_tool_activity = True
                    elif block_type == "text":
                        if not isinstance(text_value, str):
                            malformed_history = True
                        extra_fields = {
                            key: value for key, value in block.items()
                            if key not in {"type", "text"}
                        }
                        if has_nested_tool_activity(extra_fields):
                            nested_tool_activity = True
                    elif block_type is not None:
                        # Other native payloads are not evidence of the source
                        # Agent exchange and must not hide nested tool blocks.
                        nested_tool_activity = nested_tool_activity or has_nested_tool_activity(block)
                    else:
                        malformed_history = True
                        nested_tool_activity = nested_tool_activity or has_nested_tool_activity(block)
                else:
                    malformed_history = True
                    continue
                if isinstance(text_value, str) and role == "user":
                    marker_count = text_value.count(SOURCE_PROMPT_MARKER)
                    source_marker_indices.extend([message_index] * marker_count)
                    if isinstance(nonce, str):
                        nonce_count = text_value.count(nonce)
                        nonce_indices.extend([message_index] * nonce_count)
            if overflow:
                break
        history_order_valid = bool(
            len(source_marker_indices) == 1
            and len(tool_use_indices) == 1
            and len(tool_result_indices) == 1
            and len(nonce_indices) == 1
            and source_marker_indices[0] < tool_use_indices[0]
            and tool_use_indices[0] < tool_result_indices[0]
            and tool_result_indices[0] < nonce_indices[0]
            and nonce_indices[0] == len(messages) - 1
        )
        return {
            "source_agent_tool_use_count": source_tool_use_count,
            "source_agent_tool_result_count": matching_tool_result_count,
            "exact_source_agent_tool_use_count": source_agent_use_count,
            "all_tool_use_count": all_tool_use_count,
            "all_tool_result_count": all_tool_result_count,
            "history_order_valid": history_order_valid,
            "walk_overflow": overflow,
            "nested_tool_activity": nested_tool_activity,
            "malformed_history": malformed_history,
        }

    def inspect_diagnostic_history_query(
        self,
        request: object,
        *,
        arrival_index: int | None,
        child: bool,
        agent_header_present: bool,
        model_ok: bool,
        authorization_ok: bool,
    ) -> dict[str, object]:
        """Retain only a digest and allowlisted facts about one query request."""
        with self.lock:
            self.history_query_request_count += 1
            nonce = self.history_query_nonce
            source_marker = self._has_source_marker(request)
            nonce_present = bool(
                isinstance(nonce, str)
                and self._has_user_marker(request, nonce)
            )
            tool_facts = self._diagnostic_query_tool_facts(
                request, nonce=nonce,
            )
            same_request_source_history = bool(
                tool_facts["source_agent_tool_use_count"] == 1
                and tool_facts["exact_source_agent_tool_use_count"] == 1
                and tool_facts["source_agent_tool_result_count"] == 1
                and tool_facts["all_tool_use_count"] == 1
                and tool_facts["all_tool_result_count"] == 1
                and tool_facts["walk_overflow"] is False
                and tool_facts["nested_tool_activity"] is False
                and tool_facts["malformed_history"] is False
            )
            facts = {
                "arrival_index": arrival_index if type(arrival_index) is int else None,
                "parent_request": child is False and agent_header_present is False,
                "model_expected": model_ok is True,
                "dummy_authorization": authorization_ok is True,
                "nonce_present": nonce_present,
                "source_prompt_marker_present": source_marker,
                "same_request_source_agent_history": same_request_source_history,
                "history_order_valid": tool_facts["history_order_valid"],
                "source_agent_tool_use_count": tool_facts[
                    "source_agent_tool_use_count"
                ],
                "source_agent_tool_result_count": tool_facts[
                    "source_agent_tool_result_count"
                ],
                "exact_source_agent_tool_use_count": tool_facts[
                    "exact_source_agent_tool_use_count"
                ],
                "all_tool_use_count": tool_facts["all_tool_use_count"],
                "all_tool_result_count": tool_facts["all_tool_result_count"],
                "walk_overflow": tool_facts["walk_overflow"],
                "nested_tool_activity": tool_facts["nested_tool_activity"],
                "malformed_history": tool_facts["malformed_history"],
            }
            facts_digest = digest(json.dumps(facts, sort_keys=True))
            valid = bool(
                self.phase == "target-diagnostic-query"
                and self.history_query_window_closed is False
                and self.history_query_request_count == 1
                and facts["parent_request"] is True
                and facts["model_expected"] is True
                and facts["dummy_authorization"] is True
                and nonce_present and source_marker and same_request_source_history
                and tool_facts["history_order_valid"] is True
            )
            witness = {
                **facts,
                "valid": valid,
                "facts_digest": facts_digest,
                "nonce_sha256": digest(nonce),
                "challenge_sha256": digest(self.history_query_challenge),
            }
            self.history_query_request_witness = witness
            return dict(witness)

    def mark_history_query_response_write(
        self,
        *,
        arrival_index: int | None,
        response_message_id: str | None,
        succeeded: bool,
    ) -> None:
        with self.lock:
            witness_arrival = self.history_query_request_witness.get("arrival_index")
            if (self.phase != "target-diagnostic-query"
                    or arrival_index != witness_arrival
                    or self.history_query_request_count != 1):
                return
            self.history_query_response_write_count += 1
            self.history_query_response_message_id_digest = digest(
                response_message_id
            )
            if succeeded:
                self.history_query_response_write_succeeded = True
            else:
                self.history_query_response_write_failed = True

    def close_history_query_window(self) -> dict[str, object]:
        with self.lock:
            self.history_query_window_closed = True
            if self.phase == "target-diagnostic-query":
                self.phase = "target-query-closed"
            return self._history_query_witness_locked()

    def _history_query_witness_locked(self) -> dict[str, object]:
        witness = self.history_query_request_witness
        return {
            "schema": "two-domain-history-query-gateway-witness/v1",
            "request_count": self.history_query_request_count,
            "arrival_index": witness.get("arrival_index"),
            "request_valid": witness.get("valid") is True,
            "parent_request": witness.get("parent_request") is True,
            "model_expected": witness.get("model_expected") is True,
            "dummy_authorization": witness.get("dummy_authorization") is True,
            "nonce_present": witness.get("nonce_present") is True,
            "source_prompt_marker_present": (
                witness.get("source_prompt_marker_present") is True
            ),
            "same_request_source_agent_history": (
                witness.get("same_request_source_agent_history") is True
            ),
            "source_agent_tool_use_count": witness.get(
                "source_agent_tool_use_count"
            ),
            "source_agent_tool_result_count": witness.get(
                "source_agent_tool_result_count"
            ),
            "exact_source_agent_tool_use_count": witness.get(
                "exact_source_agent_tool_use_count"
            ),
            "all_tool_use_count": witness.get("all_tool_use_count"),
            "all_tool_result_count": witness.get("all_tool_result_count"),
            "nested_tool_activity": witness.get("nested_tool_activity") is True,
            "malformed_history": witness.get("malformed_history") is True,
            "history_order_valid": witness.get("history_order_valid") is True,
            "request_facts_digest": witness.get("facts_digest"),
            "query_nonce_sha256": witness.get("nonce_sha256"),
            "response_challenge_sha256": witness.get("challenge_sha256"),
            "response_write_count": self.history_query_response_write_count,
            "response_write_succeeded": (
                self.history_query_response_write_succeeded
            ),
            "response_write_failed": self.history_query_response_write_failed,
            "response_message_id_digest": (
                self.history_query_response_message_id_digest
            ),
            "window_closed": self.history_query_window_closed,
        }

    def wait_for_busy_parent_barrier(self, *, timeout: float) -> bool:
        """Wait for the handler to publish a positive pending-response witness."""
        return self.busy_parent_barrier_event.wait(timeout)

    def hold_busy_parent_response(
        self,
        request: object,
        *,
        child: bool,
        response_kind: str,
        arrival_index: int | None,
    ) -> str:
        """Withhold one exact parent continuation response at a bounded barrier."""
        with self.lock:
            if (
                not self.busy_parent_enabled
                or child
                or response_kind != "text-end-turn"
                or self.phase != "source"
                or not self.source_agent_response_sent
                or self.source_agent_tool_name != "Agent"
                or self.busy_parent_barrier_event.is_set()
                or self._find_exact_agent_continuation_result(request) is None
            ):
                return "not-selected"
            self.busy_parent_continuation_classified = True
            self.busy_parent_request_arrival_index = arrival_index
            self.busy_parent_barrier_pending = True
            self.busy_parent_barrier_waiting = True
            self.busy_parent_barrier_event.set()
        released = self.busy_parent_release_event.wait(
            max(0.0, float(self.busy_parent_barrier_timeout))
        )
        with self.lock:
            self.busy_parent_barrier_waiting = False
            self.busy_parent_barrier_pending = False
            if not released:
                self.busy_parent_barrier_expired = True
                return "expired"
            if self.busy_parent_control_entry_observed:
                self.busy_parent_barrier_released_after_control = True
            else:
                self.busy_parent_barrier_released_before_control = True
            return "released"

    def mark_busy_parent_response_completed(
        self,
        *,
        arrival_index: int | None,
        barrier_status: str,
    ) -> None:
        """Record completion only after the handler's HTTP write returns."""
        with self.lock:
            if (
                barrier_status == "released"
                and arrival_index == self.busy_parent_request_arrival_index
                and self.busy_parent_barrier_released_after_control
            ):
                self.busy_parent_response_write_succeeded = True
                self.busy_parent_barrier_response_completed = True

    def mark_busy_parent_response_write_started(
        self,
        *,
        arrival_index: int | None,
        barrier_status: str,
    ) -> None:
        """Record that the selected response write was actually attempted."""
        with self.lock:
            if (
                barrier_status == "released"
                and arrival_index == self.busy_parent_request_arrival_index
                and self.busy_parent_barrier_released_after_control
            ):
                self.busy_parent_response_write_started = True

    def mark_busy_parent_response_write_failed(
        self,
        *,
        arrival_index: int | None,
        barrier_status: str,
    ) -> None:
        """Record a failed selected response write without inferring cancel."""
        with self.lock:
            if (
                barrier_status == "released"
                and arrival_index == self.busy_parent_request_arrival_index
                and self.busy_parent_barrier_released_after_control
            ):
                self.busy_parent_response_write_failed = True

    def mark_busy_parent_handler_returned(
        self,
        *,
        arrival_index: int | None,
        barrier_status: str,
    ) -> None:
        """Record selected-handler return independently from response success."""
        with self.lock:
            if (
                arrival_index == self.busy_parent_request_arrival_index
                and barrier_status in {"released", "expired"}
            ):
                self.busy_parent_handler_returned = True

    def _busy_parent_response_disposition_locked(self) -> str:
        if self.busy_parent_barrier_expired:
            return "barrier-expired"
        if self.busy_parent_barrier_released_before_control:
            return "released-before-control"
        if not self.busy_parent_barrier_released_after_control:
            return "not-released"
        if self.busy_parent_response_write_succeeded:
            return "write-succeeded"
        if self.busy_parent_response_write_failed:
            return "write-failed"
        if self.busy_parent_response_write_started:
            return "write-outcome-unknown"
        if self.busy_parent_handler_returned:
            return "write-not-attempted"
        return "outcome-unknown"

    def release_busy_parent_barrier(self) -> None:
        """Release the handler exactly once, including failure cleanup."""
        with self.lock:
            self.busy_parent_barrier_release_requested = True
        self.busy_parent_release_event.set()

    def busy_parent_snapshot(self) -> dict[str, object]:
        with self.lock:
            if not self.busy_parent_enabled:
                status = "not-started"
            elif self.busy_parent_barrier_expired:
                status = "expired"
            elif self.busy_parent_barrier_pending:
                status = "pending"
            elif self.busy_parent_barrier_event.is_set():
                status = "released"
            else:
                status = "not-observed"
            return {
                "enabled": self.busy_parent_enabled,
                "status": status,
                "continuation_classified": self.busy_parent_continuation_classified,
                "barrier_entered": self.busy_parent_barrier_event.is_set(),
                "barrier_pending": self.busy_parent_barrier_pending,
                "barrier_waiting": self.busy_parent_barrier_waiting,
                "barrier_release_requested": self.busy_parent_barrier_release_requested,
                "barrier_released_before_control": (
                    self.busy_parent_barrier_released_before_control
                ),
                "barrier_released_after_control": (
                    self.busy_parent_barrier_released_after_control
                ),
                "barrier_pending_at_control_entry": (
                    self.busy_parent_barrier_pending_at_control_entry
                ),
                "barrier_waiting_at_control_entry": (
                    self.busy_parent_barrier_waiting_at_control_entry
                ),
                "barrier_expired": self.busy_parent_barrier_expired,
                "response_completed": self.busy_parent_barrier_response_completed,
                "response_write_started": self.busy_parent_response_write_started,
                "response_write_succeeded": self.busy_parent_response_write_succeeded,
                "response_write_failed": self.busy_parent_response_write_failed,
                "handler_returned": self.busy_parent_handler_returned,
                "response_disposition": self._busy_parent_response_disposition_locked(),
                # The gateway does not observe the runtime client's cancellation
                # boundary.  Keep this explicit instead of inferring it from an
                # interrupt receipt, parent exit, or a failed HTTP write.
                "response_cancellation_observed": False,
                "request_arrival_index": self.busy_parent_request_arrival_index,
                "blocked_request_arrival_index": self.busy_parent_request_arrival_index,
                "control_entry_observed": self.busy_parent_control_entry_observed,
                "child_active_pre_entry": (
                    self.busy_parent_child_active_pre_entry
                ),
                "bash_active_pre_entry": (
                    self.busy_parent_bash_active_pre_entry
                ),
                "liveness_observation": "immediate-pre-entry-not-atomic",
                "control_entry_epoch_start_request_index": (
                    self.control_entry_epoch_start_request_index
                ),
                "task_id_digest": self.busy_parent_task_id_digest,
                "process_identity_digest": self.busy_parent_process_identity_digest,
            }

    def control_entry_snapshot(self) -> dict[str, object]:
        with self.lock:
            if self.control_entry_epoch_id is None:
                status = "not-started"
            elif self.control_entry_epoch_closed:
                status = "released"
            else:
                status = "incomplete-until-release"
            return {
                "observation_scope": "scripted-loopback-messages-arrivals",
                "enabled": self.control_entry_epoch_id is not None,
                "status": status,
                "epoch_id_digest": digest(self.control_entry_epoch_id),
                "closed_by_release": self.control_entry_epoch_closed,
                "start_request_index": self.control_entry_epoch_start_request_index,
                "end_request_index": self.control_entry_epoch_end_request_index,
                "start_phase": self.control_entry_epoch_start_phase,
                "end_phase": self.control_entry_epoch_end_phase,
                "inference_attempts": self.control_entry_epoch_inference_attempts,
                "phase_counts": dict(self.control_entry_epoch_phase_counts),
                "phases_observed": list(self.control_entry_epoch_phases),
                "parent_settled_at_control_entry": (
                    self.control_entry_epoch_parent_settled_at_entry
                ),
                "begin_calls": self.control_entry_epoch_begin_calls,
                "message_arrival_count": self.message_arrival_count,
            }

    def mark_stop_requested(self) -> None:
        with self.lock:
            self.stop_requested = True

    @staticmethod
    def _contains_literal(value: object, target: str, depth: int = 0) -> bool:
        if depth > 10:
            return False
        if isinstance(value, str):
            return value == target
        if isinstance(value, Mapping):
            return any(
                GatewayState._contains_literal(child, target, depth + 1)
                for child in value.values()
            )
        if isinstance(value, (list, tuple)):
            return any(
                GatewayState._contains_literal(child, target, depth + 1)
                for child in value
            )
        return False

    @staticmethod
    def _find_agent_result(value: object, depth: int = 0) -> Mapping[str, object] | None:
        if depth > 10:
            return None
        if isinstance(value, Mapping):
            if (value.get("type") == "tool_result"
                    and value.get("tool_use_id") == SOURCE_AGENT_TOOL_ID):
                return value
            for child in value.values():
                found = GatewayState._find_agent_result(child, depth + 1)
                if found is not None:
                    return found
        elif isinstance(value, (list, tuple)):
            for child in value:
                found = GatewayState._find_agent_result(child, depth + 1)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _classify_agent_result(result: Mapping[str, object]) -> str:
        if result.get("is_error") is not True:
            return "other"
        # Classification examines the private result locally and retains only
        # this allowlisted category; no error text is written to evidence.
        text = json.dumps(result, separators=(",", ":")).lower()
        if ("unknown agent" in text or "agent definition" in text
                or "subagent_type" in text):
            return "unknown-agent-definition"
        if ("permission" in text or "not allowed" in text
                or "denied" in text):
            return "permission-denied"
        if ("unknown tool" in text or "tool not found" in text
                or "invalid tool" in text):
            return "unknown-tool"
        if ("invalid" in text or "schema" in text or "required" in text
                or "input" in text):
            return "invalid-input"
        return "other"

    @classmethod
    def _summarize_agent_result(cls, request: object) -> dict[str, object]:
        result = cls._find_agent_result(request)
        if result is None:
            return {"matched": False, "is_error": None, "classification": "other"}
        is_error = result.get("is_error")
        return {
            "matched": True,
            "is_error": is_error if isinstance(is_error, bool) else None,
            "classification": cls._classify_agent_result(result),
        }

    @staticmethod
    def _has_user_marker(request: object, marker: str) -> bool:
        if not isinstance(request, Mapping):
            return False
        messages = request.get("messages")
        if not isinstance(messages, list):
            return False
        for message in messages:
            if not isinstance(message, Mapping) or message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, str) and marker in content:
                return True
            if isinstance(content, Mapping):
                text = content.get("text")
                if isinstance(text, str) and marker in text:
                    return True
            if isinstance(content, (list, tuple)):
                for block in content:
                    if GatewayState._has_user_marker(
                        {"messages": [{"role": "user", "content": block}]},
                        marker,
                    ):
                        return True
        return False

    @staticmethod
    def _has_source_marker(request: object) -> bool:
        return GatewayState._has_user_marker(request, SOURCE_PROMPT_MARKER)

    @staticmethod
    def _find_tool_use(
        value: object,
        tool_id: str,
        depth: int = 0,
    ) -> Mapping[str, object] | None:
        if depth > 10:
            return None
        if isinstance(value, Mapping):
            if value.get("type") == "tool_use" and value.get("id") == tool_id:
                return value
            for child in value.values():
                found = GatewayState._find_tool_use(child, tool_id, depth + 1)
                if found is not None:
                    return found
        elif isinstance(value, (list, tuple)):
            for child in value:
                found = GatewayState._find_tool_use(child, tool_id, depth + 1)
                if found is not None:
                    return found
        return None

    @classmethod
    def _find_exact_agent_continuation_result(
        cls,
        value: object,
    ) -> Mapping[str, object] | None:
        """Match only the contracted Agent tool use and its result."""
        tool_use = cls._find_tool_use(value, SOURCE_AGENT_TOOL_ID)
        if tool_use is None or tool_use.get("name") != "Agent":
            return None
        return cls._find_agent_result(value)

    def inspect_target_release_body(self, request: object) -> None:
        """Verify only safe continuity facts in the first release request.

        The request body is inspected transiently.  Only booleans, the
        allowlisted native tool name, and a digest of those facts survive.
        """
        with self.lock:
            if self.phase != "target-release":
                return
            source_marker = self._has_source_marker(request)
            release_marker = self._has_user_marker(request, TARGET_RELEASE_MARKER)
            tool_use = self._find_tool_use(request, SOURCE_AGENT_TOOL_ID)
            tool_name = (
                tool_use.get("name") if tool_use is not None else None
            )
            tool_use_present = (
                tool_name in {"Agent", "Task"}
                and (
                    self.source_agent_tool_name is None
                    or tool_name == self.source_agent_tool_name
                )
            )
            result = self._find_agent_result(request)
            result_present = result is not None
            facts = {
                "source_marker_present": source_marker,
                "release_marker_present": release_marker,
                "agent_tool_use_present": tool_use_present,
                "agent_tool_result_present": result_present,
                "agent_tool_name": tool_name if tool_use_present else None,
            }
            facts_digest = digest(json.dumps(facts, sort_keys=True))
            current = self.target_release_history
            if not current:
                current.update({
                    "requests_seen": 0,
                    "source_marker_present": False,
                    "release_marker_present": False,
                    "agent_tool_use_present": False,
                    "agent_tool_result_present": False,
                    "agent_tool_name": None,
                    "history_facts_digest": None,
                })
            current["requests_seen"] = int(current["requests_seen"]) + 1
            for key in (
                "source_marker_present", "release_marker_present",
                "agent_tool_use_present", "agent_tool_result_present",
            ):
                current[key] = bool(current[key]) or bool(facts[key])
            if current.get("agent_tool_name") is None and tool_use_present:
                current["agent_tool_name"] = tool_name
            current["history_facts_digest"] = facts_digest

    def inspect_parent_body(self, request: object, *, child: bool) -> dict[str, object]:
        """Record bounded schema/result diagnostics from source parent turns."""

        result_context = {"marker_present": False, "advertised_tool": None}
        with self.lock:
            if child or self.phase not in {"source", "source-drain"}:
                return result_context
            self.parent_messages_seen += 1
            mapping = request if isinstance(request, Mapping) else {}
            tools = mapping.get("tools")
            names: list[str] = []
            agent_schema_has_worker = False
            if isinstance(tools, list):
                for tool in tools:
                    if isinstance(tool, Mapping) and isinstance(tool.get("name"), str):
                        names.append(tool["name"])
                        if tool["name"] in {"Agent", "Task"}:
                            if self._contains_literal(tool, SOURCE_AGENT_NAME):
                                agent_schema_has_worker = True
            names = sorted(set(names))[:128]
            marker_present = self._has_source_marker(request)
            advertised_tool = (
                "Agent" if "Agent" in names
                else "Task" if "Task" in names
                else None
            )
            result_context = {
                "marker_present": marker_present,
                "advertised_tool": advertised_tool,
            }
            self.agent_schema_has_worker_observed = (
                self.agent_schema_has_worker_observed or agent_schema_has_worker
            )
            if len(self.parent_request_records) < 4:
                request_record = {
                    "marker_present": marker_present,
                    "tools_shape": (
                        "list" if isinstance(tools, list)
                        else "missing" if tools is None
                        else type(tools).__name__
                    ),
                    "tools_count": len(tools) if isinstance(tools, list) else 0,
                    "top_level_keys": sorted(
                        str(key) for key in mapping.keys()
                    )[:64],
                    "declared_tool_names": names,
                    "advertised_native_tool": advertised_tool,
                    "agent_schema_has_worker": agent_schema_has_worker,
                    "agent_tool_result": self._summarize_agent_result(request),
                }
                self.parent_request_records.append(request_record)
            if self.parent_messages_seen == 1:
                self.first_parent_declared_tool_names = names
                self.first_parent_agent_schema_has_worker = agent_schema_has_worker
            elif self.parent_messages_seen == 2:
                self.second_parent_agent_result = self._summarize_agent_result(request)
        return result_context

    def diagnostics(self) -> dict[str, object]:
        with self.lock:
            diagnostics = {
                "parent_messages_seen": self.parent_messages_seen,
                "first_parent_declared_tool_names": list(
                    self.first_parent_declared_tool_names
                ),
                "first_parent_agent_schema_has_worker": (
                    self.first_parent_agent_schema_has_worker
                ),
                "agent_schema_has_worker_observed": (
                    self.agent_schema_has_worker_observed
                ),
                "parent_request_records": list(self.parent_request_records),
                "second_parent_agent_result": dict(self.second_parent_agent_result),
                "source_agent_response_sent": self.source_agent_response_sent,
                "source_agent_tool_name": self.source_agent_tool_name,
                "target_release_history": dict(self.target_release_history),
            }
        diagnostics["busy_parent"] = self.busy_parent_snapshot()
        return diagnostics

    def record(
        self,
        path: str,
        *,
        method: str = "POST",
        child: bool = False,
        agent_header: str | None = None,
        agent_header_present: bool | None = None,
        arrival_index: int | None = None,
        model_ok: bool = True,
        authorization_ok: bool = True,
        response_kind: str = "unknown",
    ) -> None:
        """Count a redacted request independently for every phase and route."""
        normalized = route(path)
        method = str(method).upper()
        with self.lock:
            if self.request_count == MAX_REQUESTS:
                self.protocol_errors.append("request-ceiling-exceeded")
            self.request_count += 1
            request_index = self.request_count
            phase_counts = self.route_counts.setdefault(self.phase, {})
            phase_counts[normalized] = phase_counts.get(normalized, 0) + 1
            self.requests.append({
                "request_index": request_index,
                "arrival_index": (
                    arrival_index if type(arrival_index) is int else None
                ),
                "method": method,
                "phase": self.phase,
                "route": normalized,
                "agent_header_present": (
                    bool(child) if agent_header_present is None
                    else bool(agent_header_present)
                ),
                "model_expected": bool(model_ok),
                "dummy_authorization": bool(authorization_ok),
                "response_kind": response_kind,
            })
            if (self.phase in {
                    "target-diagnostic-query", "target-query-closed",
                }
                    and (normalized != "/v1/messages"
                         or child
                         or agent_header_present is True)):
                self.protocol_errors.append(
                    "diagnostic-query-unexpected-request"
                )
            if agent_header:
                self.child_agent_header_digests.add(digest(agent_header) or "")
                self.child_agent_decoded_digests.add(
                    digest(unquote(agent_header)) or ""
                )
            if normalized == "/v1/messages":
                if child:
                    self.child_posts += 1
                    if response_kind == "bash-tool":
                        self.bash_responses += 1
                elif self.phase in {"source", "source-drain"}:
                    self.parent_posts += 1
            if response_kind == "agent-tool":
                self.agent_responses += 1
            if not model_ok:
                self.protocol_errors.append("unexpected-model")
            if not authorization_ok:
                self.protocol_errors.append("non-dummy-authorization")

    def response(
        self,
        *,
        child: bool,
        model_ok: bool = True,
        authorization_ok: bool = True,
        agent_header: str | None = None,
        agent_header_present: bool | None = None,
        arrival_index: int | None = None,
        prompt_marker: bool = False,
        advertised_tool: str | None = None,
        diagnostic_query_body_valid: bool = False,
    ) -> dict[str, object]:
        """Choose the only allowed scripted response for the current phase."""
        if self.request_count >= MAX_REQUESTS:
            kind, status = "protocol-error", 429
            self.protocol_errors.append("request-ceiling-exceeded")
        elif not model_ok:
            kind, status = "protocol-error", 400
        elif not authorization_ok:
            kind, status = "credential-error", 401
        elif self.phase == "target-held":
            kind, status = "held-error", 409
        elif self.phase == "target-diagnostic-query":
            if (not child and agent_header_present is not True
                    and diagnostic_query_body_valid is True
                    and self.history_query_request_count == 1
                    and self.history_query_window_closed is False):
                kind, status = "diagnostic-query-challenge", 200
            else:
                kind, status = "protocol-error", 409
        elif self.phase == "target-query-closed":
            kind, status = "protocol-error", 409
        elif self.phase == "source" and child and self.child_posts == 0:
            kind, status = "bash-tool", 200
        elif (self.phase == "source" and not child and prompt_marker
              and advertised_tool in {"Agent", "Task"}
              and not self.source_agent_response_sent):
            kind, status = "agent-tool", 200
            self.source_agent_response_sent = True
            self.source_agent_tool_name = advertised_tool
        elif self.phase == "source" and not child:
            kind, status = "text-end-turn", 200
        elif self.phase in {"source-drain", "target-release"} or self.stop_requested:
            kind, status = "text-end-turn", 200
        else:
            kind, status = "protocol-error", 409
        self.record(
            "/v1/messages",
            child=child,
            agent_header=agent_header,
            agent_header_present=agent_header_present,
            arrival_index=arrival_index,
            model_ok=model_ok,
            authorization_ok=authorization_ok,
            response_kind=kind,
        )
        if kind == "protocol-error":
            self.protocol_errors.append("unexpected-messages-state")
        return {
            "kind": kind,
            "status": status,
            "tool_name": self.source_agent_tool_name if kind == "agent-tool" else None,
            "response_challenge": (
                self.history_query_challenge
                if kind == "diagnostic-query-challenge" else None
            ),
        }

    def snapshot(self) -> dict[str, object]:
        with self.lock:
            snapshot = {
                "phase": self.phase,
                "route_counts": {
                    phase: dict(counts)
                    for phase, counts in self.route_counts.items()
                },
                "request_count": self.request_count,
                "message_arrival_count": self.message_arrival_count,
                "requests": list(self.requests),
                "protocol_errors": list(self.protocol_errors),
                "parent_posts": self.parent_posts,
                "child_posts": self.child_posts,
                "agent_responses": self.agent_responses,
                "source_parent_posts": self.parent_posts,
                "source_child_posts": self.child_posts,
                "child_tool_posts": self.bash_responses,
                "bash_responses": self.bash_responses,
                "child_agent_header_count": len(self.child_agent_header_digests),
            }
            snapshot["startup_observation"] = (
                self._startup_observation_snapshot_locked()
            )
            snapshot["history_query_gateway_witness"] = (
                self._history_query_witness_locked()
            )
            snapshot["request_arrivals"] = self._request_arrival_report_locked()
        snapshot["control_entry_epoch"] = self.control_entry_snapshot()
        snapshot["busy_parent"] = self.busy_parent_snapshot()
        return snapshot

    def response_plan(self, *, child: bool, **kwargs: object) -> dict[str, object]:
        """Use the historical synthetic source fixture for offline tests.

        The live handler always supplies the request-derived marker/tool
        facts.  This convenience entrypoint keeps pure state-machine tests
        concise without weakening live auxiliary-request routing.
        """
        kwargs.setdefault("prompt_marker", not child)
        kwargs.setdefault("advertised_tool", "Agent" if not child else None)
        return self.response(child=child, **kwargs)


def scripted_response(
    state: GatewayState,
    *,
    child: bool,
    model_ok: bool = True,
    authorization_ok: bool = True,
) -> dict[str, object]:
    """Offline/test entrypoint for the exact live gateway policy."""

    plan = state.response(
        child=child,
        model_ok=model_ok,
        authorization_ok=authorization_ok,
        prompt_marker=not child,
        advertised_tool="Agent" if not child else None,
    )
    return {"kind": plan["kind"], "status": plan["status"]}


def assess_stop_observation(observation: Mapping[str, object]) -> dict[str, object]:
    """Keep control receipts, terminal events, and cleanup facts independent."""
    action = str(observation.get("control_action") or (
        "interrupt" if observation.get("interrupt_sent") else "stop_task"
    ))
    sent_name = "interrupt_sent" if action == "interrupt" else "stop_sent"
    receipt_name = (
        "interrupt_receipt" if action == "interrupt" else "stop_receipt"
    )
    required = (
        "actual_task_id",
        sent_name,
        receipt_name,
        "stopped_notification",
        "tool_terminal",
        "tracked_process_exited_before_cleanup",
        "source_parent_process_exited",
    )
    missing = [name for name in required if not observation.get(name)]
    reasons: list[str] = []
    if not observation.get("actual_task_id"):
        reasons.append("native-task-id-not-observed")
    if observation.get(receipt_name) and not observation.get(
        "stopped_notification"
    ):
        reasons.append(
            "interrupt-receipt-without-terminal-event"
            if action == "interrupt"
            else "stop-receipt-without-terminal-event"
        )
    if observation.get("forced_cleanup") and not observation.get(
        "tracked_process_exited_before_cleanup"
    ):
        reasons.append("forced-cleanup-is-not-stop-evidence")
    if not observation.get("tool_terminal"):
        reasons.append("tool-terminal-evidence-missing")
    if not observation.get("tracked_process_exited_before_cleanup"):
        reasons.append("tracked-process-exit-not-observed")
    if not observation.get("source_parent_process_exited"):
        reasons.append("source-parent-process-exclusion-not-observed")
    return {
        "stop_candidate": not missing,
        "control_candidate": not missing,
        "control_action": action,
        "support_claim": False,
        "verdict": "inconclusive",
        "missing_facts": missing,
        "reason_codes": sorted(set(reasons)),
    }


def assess_control_entry_observation(
    epoch: Mapping[str, object],
    *,
    active_fixture_observed: bool,
    source_parent_process_exited: bool,
    target_hold_complete: bool,
    cleanup_complete: bool,
    read_failed: bool = False,
) -> dict[str, object]:
    """Classify the sticky observation without granting a zero-request gate."""

    if epoch.get("enabled") is not True:
        return {
            "observation_scope": "scripted-loopback-messages-arrivals",
            "inference_observation": "not-started",
            "coverage_status": "unknown",
            "zero_request_observation": "unknown",
            "verdict": "inconclusive",
            "support_claim": False,
            "production_continuous_observer_capability": False,
            "reason_codes": ["control-entry-epoch-not-started"],
        }
    raw_attempts = epoch.get("inference_attempts")
    attempts = raw_attempts if type(raw_attempts) is int and raw_attempts >= 0 else None
    logical_attempts = attempts if attempts is not None else 0
    reasons: list[str] = []
    if attempts is None:
        reasons.append("control-entry-counter-invalid")
    if logical_attempts:
        reasons.append("control-entry-inference-attempt-observed")
    if not active_fixture_observed:
        reasons.append("control-entry-fixture-not-observed")
    if read_failed:
        reasons.append("control-entry-read-failed")
    if not cleanup_complete:
        reasons.append("control-entry-cleanup-incomplete")
    if not source_parent_process_exited:
        reasons.append("control-entry-source-exclusion-incomplete")
    if not target_hold_complete:
        reasons.append("control-entry-target-held-not-observed")

    if any(
        reason in reasons
        for reason in (
            "control-entry-counter-invalid",
            "control-entry-fixture-not-observed",
            "control-entry-read-failed",
            "control-entry-cleanup-incomplete",
            "control-entry-source-exclusion-incomplete",
            "control-entry-target-held-not-observed",
        )
    ):
        coverage_status = "unknown"
        zero_request_observation: bool | str = (
            False if logical_attempts else "unknown"
        )
    elif epoch.get("closed_by_release") is not True:
        coverage_status = "incomplete-until-release"
        zero_request_observation = (
            False if logical_attempts else "unknown"
        )
        reasons.append("control-entry-incomplete-until-release")
    else:
        coverage_status = "complete"
        zero_request_observation = logical_attempts == 0

    return {
        "observation_scope": "scripted-loopback-messages-arrivals",
        "inference_observation": (
            "positive" if logical_attempts
            else "unknown" if attempts is None
            else "quiet"
        ),
        "inference_attempts": attempts,
        "coverage_status": coverage_status,
        "zero_request_observation": zero_request_observation,
        "verdict": "inconclusive",
        "support_claim": False,
        "production_continuous_observer_capability": False,
        "reason_codes": sorted(set(reasons)),
    }


def assess_busy_parent_observation(
    observation: Mapping[str, object],
) -> dict[str, object]:
    """Classify a pending-HTTP witness without inferring cancellation.

    The gateway can prove that an exact parent continuation was withheld.  It
    cannot, by itself, observe the runtime client's cancellation boundary, so a
    receipt, parent exit, failed write, or quiet target is never upgraded to a
    cancelled-request claim.
    """
    reasons: list[str] = []
    if observation.get("enabled") is not True:
        reasons.append("busy-parent-arm-not-enabled")
    if observation.get("continuation_classified") is not True:
        reasons.append("busy-parent-continuation-not-identified")
    if observation.get("control_entry_observed") is not True:
        reasons.append("busy-parent-control-entry-not-observed")
    arrival_index = observation.get("request_arrival_index")
    if type(arrival_index) is not int or arrival_index < 1:
        reasons.append("busy-parent-pending-request-index-not-observed")
    if observation.get("barrier_pending_at_control_entry") is not True:
        reasons.append("busy-parent-barrier-not-pending-at-control-entry")
    if observation.get("barrier_waiting_at_control_entry") is not True:
        reasons.append("busy-parent-barrier-wait-not-observed-at-control-entry")
    if observation.get("child_active_pre_entry") is not True:
        reasons.append("busy-parent-native-child-not-active-at-control-entry")
    if observation.get("bash_active_pre_entry") is not True:
        reasons.append("busy-parent-bash-not-active-at-control-entry")
    if observation.get("liveness_observation") != "immediate-pre-entry-not-atomic":
        reasons.append("busy-parent-liveness-observation-imprecise")
    epoch_start = observation.get("control_entry_epoch_start_request_index")
    if type(epoch_start) is not int or epoch_start < 1:
        reasons.append("busy-parent-control-entry-index-not-observed")
    elif type(arrival_index) is int and arrival_index >= epoch_start:
        reasons.append("busy-parent-pending-request-not-before-epoch")
    if not isinstance(observation.get("task_id_digest"), str):
        reasons.append("busy-parent-task-identity-not-observed")
    if not isinstance(observation.get("process_identity_digest"), str):
        reasons.append("busy-parent-process-identity-not-observed")
    if observation.get("barrier_expired") is True:
        reasons.append("busy-parent-barrier-deadline-expired")
    if observation.get("barrier_released_before_control") is True:
        reasons.append("busy-parent-barrier-released-before-control")
    if observation.get("barrier_released_after_control") is not True:
        reasons.append("busy-parent-barrier-cleanup-release-not-observed")
    response_disposition = observation.get("response_disposition")
    if response_disposition not in {
        "write-succeeded",
        "write-failed",
        "write-outcome-unknown",
        "write-not-attempted",
        "barrier-expired",
        "released-before-control",
        "not-released",
        "outcome-unknown",
    }:
        reasons.append("busy-parent-response-disposition-not-observed")
    structural_reasons = list(reasons)
    if observation.get("response_cancellation_observed") is not True:
        reasons.append("busy-parent-response-cancellation-unobserved")
    witness = not structural_reasons
    return {
        "observation_scope": "scripted-loopback-parent-http-barrier",
        "busy_parent_witness": witness,
        "pending_request_witness": witness,
        "response_disposition": response_disposition,
        "response_cancellation_observed": (
            observation.get("response_cancellation_observed") is True
        ),
        "control_candidate": False,
        "inference_observation": "positive" if witness else "unknown",
        "coverage_status": "observed" if witness else "inconclusive",
        "verdict": "inconclusive",
        "support_claim": False,
        "reason_codes": sorted(set(reasons)),
    }


def assess_target_hold_observation(
    observation: Mapping[str, object],
) -> dict[str, object]:
    """Keep quiet target traffic distinct from authoritative parent loading.

    A matching session UUID is an identity observation only.  Exact held
    parent restoration requires an authoritative loader fact from the selected
    runtime in addition to a calibrated, request-free hold window.  The
    current loopback stream does not emit that fact, so its ordinary result is
    intentionally ``unknown``.
    """
    reasons: list[str] = []
    hold_complete = observation.get("hold_complete") is True
    initialize_succeeded = observation.get("initialize_succeeded") is True
    source_session = observation.get("source_session_id")
    target_session = observation.get("target_session_id")
    same_parent_uuid = bool(
        isinstance(source_session, str)
        and source_session
        and isinstance(target_session, str)
        and target_session
        and source_session == target_session
    )
    if not hold_complete or not initialize_succeeded:
        reasons.append("target-parent-hold-not-complete")
    if not same_parent_uuid:
        reasons.append("target-session-not-observed")
    sensor_calibrated = observation.get("endpoint_sensor_calibrated") is True
    if not sensor_calibrated:
        reasons.append("target-monitor-incomplete")

    def _count(name: str) -> int | None:
        value = observation.get(name)
        return value if type(value) is int and value >= 0 else None

    messages_posts = _count("messages_posts")
    count_tokens_posts = _count("count_tokens_posts")
    api_hello_requests = _count("api_hello_requests")
    if messages_posts is None or count_tokens_posts is None or api_hello_requests is None:
        reasons.append("target-route-count-invalid")
    quiet = (
        messages_posts == 0
        and count_tokens_posts == 0
        and api_hello_requests == 0
    )
    if messages_posts is not None and messages_posts:
        reasons.append("target-model-request-observed")

    model_request_free_observation: bool | str
    if sensor_calibrated and not any(
        reason in reasons
        for reason in (
            "target-route-count-invalid",
            "target-model-request-observed",
        )
    ):
        model_request_free_observation = quiet
    else:
        model_request_free_observation = "unknown"

    authoritative_loader_evidence = (
        observation.get("authoritative_loader_evidence") is True
    )
    exact_parent_load = "unknown"
    if not authoritative_loader_evidence:
        reasons.append("target-parent-load-not-proven")
    elif not (
        hold_complete
        and initialize_succeeded
        and same_parent_uuid
        and sensor_calibrated
        and quiet
    ):
        reasons.append("target-parent-load-evidence-incomplete")
    else:
        exact_parent_load = "observed"

    return {
        "observation_scope": "scripted-loopback-target-held",
        "same_parent_uuid": same_parent_uuid,
        "model_request_free_observation": model_request_free_observation,
        "exact_parent_load": exact_parent_load,
        "support_claim": False,
        "verdict": "inconclusive",
        "reason_codes": sorted(set(reasons)),
    }


def assess_v1_history_query_gate(
    observation: Mapping[str, object],
) -> dict[str, object]:
    """Authorize one v1 history query only after a clean startup window."""
    reasons: list[str] = []
    if observation.get("initialize_succeeded") is not True:
        reasons.append("target-init-not-observed")
    if observation.get("target_alive") is not True:
        reasons.append("target-not-alive-at-history-gate")
    if observation.get("session_identity_mismatch") is True:
        reasons.append("target-session-identity-mismatch")
    elif (
        observation.get("session_identity_observed") is not True
        and observation.get("session_identity_observed") is not False
    ):
        reasons.append("target-session-identity-observation-invalid")
    if observation.get("resume_spec_bound") is not True:
        reasons.append("exact-resume-spec-not-bound")
    if observation.get("source_manifest_bound") is not True:
        reasons.append("source-manifest-not-bound")

    for name, reason in (
        ("parent_messages_since_launch", "startup-parent-message-observed"),
        ("child_messages_since_launch", "startup-child-message-observed"),
    ):
        count = observation.get(name)
        if type(count) is not int or count < 0:
            reasons.append("%s-invalid" % name.replace("_since_launch", ""))
        elif count:
            reasons.append(reason)

    native_task_events = observation.get("native_task_events")
    if type(native_task_events) is not int or native_task_events < 0:
        reasons.append("startup-task-event-count-invalid")
    elif native_task_events:
        reasons.append("startup-task-event-observed")

    if observation.get("startup_parent_result_observed") is True:
        reasons.append("startup-parent-result-observed")
    elif observation.get("startup_parent_result_observed") is not False:
        reasons.append("startup-parent-result-observation-invalid")
    if observation.get("generic_startup_activity_observed") is True:
        reasons.append("startup-assistant-or-tool-activity-observed")
    elif observation.get("generic_startup_activity_observed") is not False:
        reasons.append("startup-activity-observation-invalid")
    if observation.get("reader_error") is True:
        reasons.append("startup-reader-error")
    elif observation.get("reader_error") is not False:
        reasons.append("startup-reader-observation-invalid")

    unparsed_frames = observation.get("unparsed_frames")
    if type(unparsed_frames) is not int or unparsed_frames < 0:
        reasons.append("startup-unparsed-frame-count-invalid")
    elif unparsed_frames:
        reasons.append("startup-unparsed-frame-observed")
    unclassified = observation.get("unclassified_lifecycle_events")
    if type(unclassified) is not int or unclassified < 0:
        reasons.append("startup-unclassified-lifecycle-count-invalid")
    elif unclassified:
        reasons.append("startup-unclassified-lifecycle-observed")
    if observation.get("quiet_window_observed") is not True:
        reasons.append("startup-quiet-window-not-observed")

    allowed = not reasons
    return {
        "observation_scope": "v1-target-startup-after-release",
        "history_query_allowed": allowed,
        "history_query_skipped": not allowed,
        "quiet_window_observed": observation.get("quiet_window_observed") is True,
        "verdict": "inconclusive",
        "support_claim": False,
        "reason_codes": sorted(set(reasons)),
    }


def native_frame_origin_kind(frame: object) -> str:
    """Return a known native origin class, requiring an explicit object."""
    if not isinstance(frame, Mapping):
        return "unknown"
    origin = frame.get("origin")
    if not isinstance(origin, Mapping):
        return "unknown"
    kind = origin.get("kind")
    if isinstance(kind, str) and kind in {
        "human", "system", "assistant", "tool", "task-notification",
    }:
        return str(kind)
    return "unknown"


def native_task_event_origin_kind(frame: object) -> str:
    """Keep task-event origin separate from its sanitized lifecycle record."""
    if (isinstance(frame, Mapping)
            and frame.get("type") == "system"
            and frame.get("subtype") == "task_notification"):
        # The pinned emitter represents this lifecycle source in the frame
        # type/subtype, without an `origin` object. Do not invent the generic
        # `system` origin for that event.
        return "task-notification" if "origin" not in frame else "unknown"
    return native_frame_origin_kind(frame)


def _contains_query_error_or_deferred_tool(value: object, depth: int = 0) -> bool:
    if depth > 20:
        return True
    if isinstance(value, Mapping):
        if "error" in value:
            return True
        if value.get("is_error") is True:
            return True
        if "deferred_tool_use" in value:
            deferred = value.get("deferred_tool_use")
            if deferred is not False and deferred is not None:
                return True
        terminal_reason = value.get("terminal_reason")
        if (terminal_reason is not None
                and (not isinstance(terminal_reason, str)
                     or terminal_reason == "aborted"
                     or terminal_reason.startswith("aborted_"))):
            return True
        stop_reason = value.get("stop_reason")
        if (stop_reason is not None
                and (not isinstance(stop_reason, str)
                     or stop_reason in {"tool_use", "error", "abort", "aborted"}
                     or stop_reason.startswith("aborted_"))):
            return True
        if value.get("role") == "tool":
            return True
        frame_type = value.get("type")
        if frame_type is not None and (
            not isinstance(frame_type, str) or frame_type in {
                "error", "abort", "aborted", "tool", "tool_use",
                "tool_result", "tool_use_result", "tool_error",
                "deferred_tool_use",
            } or frame_type.startswith("aborted_")
        ):
            return True
        subtype = value.get("subtype")
        if subtype is not None and (
            not isinstance(subtype, str) or subtype in {
                "error", "abort", "aborted", "tool_use", "tool_result",
                "tool_use_result", "tool_error", "deferred_tool_use",
            } or subtype.startswith("aborted_")
        ):
            return True
        return any(
            _contains_query_error_or_deferred_tool(child, depth + 1)
            for child in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(
            _contains_query_error_or_deferred_tool(child, depth + 1)
            for child in value
        )
    return False


def _validated_terminal_seed_for_query_gate(
    envelope: object,
    *,
    parent_uuid_digest: object,
    source_invocation_digest: object,
) -> dict[str, object] | None:
    try:
        validated = validate_native_task_source_terminal_seed_envelope(
            envelope,
            expected_parent_uuid_digest=parent_uuid_digest,
            expected_source_invocation_digest=source_invocation_digest,
        )
    except (TypeError, ValueError):
        return None
    if validated.get("status") != "available":
        return None
    return validated


def assess_two_domain_terminal_task_query_gate(
    observation: Mapping[str, object],
) -> dict[str, object]:
    """Authorize one neutral query from an exact startup terminal-task event."""
    reasons: list[str] = []
    if observation.get("initialize_succeeded") is not True:
        reasons.append("target-init-not-observed")
    if observation.get("target_alive") is not True:
        reasons.append("target-not-alive-at-terminal-task-gate")
    if observation.get("same_parent_session") is not True:
        reasons.append("target-session-identity-mismatch")
    if observation.get("resume_spec_bound") is not True:
        reasons.append("exact-resume-spec-not-bound")
    if observation.get("source_manifest_bound") is not True:
        reasons.append("source-manifest-not-bound")

    seed = _validated_terminal_seed_for_query_gate(
        observation.get("native_task_source_terminal_seed"),
        parent_uuid_digest=observation.get("parent_uuid_digest"),
        source_invocation_digest=observation.get("source_invocation_digest"),
    )
    if seed is None:
        reasons.append("validated-source-terminal-seed-unavailable")
    else:
        source_terminal = seed.get("terminal_event")
        source_started = seed.get("task_started_event")
        if (not isinstance(source_terminal, Mapping)
                or source_terminal.get("event_subtype") != "task_notification"
                or source_terminal.get("status") != "stopped"
                or source_terminal.get("session_id_seen") is not True
                or source_terminal.get("session_id_digest")
                != observation.get("parent_uuid_digest")
                or source_terminal.get("task_id_seen") is not True
                or not isinstance(source_started, Mapping)
                or source_started.get("event_type") != "system"
                or source_started.get("event_subtype") != "task_started"
                or source_started.get("task_type") != "local_agent"
                or source_started.get("session_id_digest")
                != observation.get("parent_uuid_digest")
                or source_started.get("task_id_seen") is not True
                or source_started.get("task_id_digest")
                != source_terminal.get("task_id_digest")):
            reasons.append("source-terminal-seed-is-not-exact-stopped-task")

    lifecycle = observation.get("startup_native_task_lifecycle")
    if not isinstance(lifecycle, Mapping):
        lifecycle = {}
        reasons.append("startup-native-task-lifecycle-missing")
    if lifecycle.get("observation_status") != "observed":
        reasons.append("startup-native-task-lifecycle-not-complete")
    if lifecycle.get("event_count") != 1:
        reasons.append("startup-native-task-event-count-not-one")
    if lifecycle.get("overflow") is not False:
        reasons.append("startup-native-task-evidence-overflow-or-unknown")
    if lifecycle.get("incomplete") is not False:
        reasons.append("startup-native-task-evidence-incomplete")
    events = lifecycle.get("events")
    if not isinstance(events, list) or len(events) != 1 or not isinstance(events[0], Mapping):
        event: Mapping[str, object] = {}
        reasons.append("startup-native-task-event-ambiguous")
    else:
        event = events[0]
    if (event.get("event_type") != "system"
            or event.get("event_subtype") != "task_notification"
            or event.get("task_type") not in {None, "local_agent"}
            or event.get("status") != "stopped"
            or event.get("phase") != "target/startup"
            or event.get("provenance") != "target-observed"
            or event.get("correlation_class") not in {
                "terminal-correlation-only", "replay-compatible",
            }
            or event.get("incomplete") is not False):
        reasons.append("startup-task-notification-is-not-exact-stopped-correlation")

    origins = lifecycle.get("event_origins")
    if (not isinstance(origins, list) or len(origins) != 1
            or not isinstance(origins[0], Mapping)
            or origins[0].get("observation_sequence") != 1
            or origins[0].get("origin_kind") != "task-notification"):
        reasons.append("startup-task-notification-origin-unknown-or-conflicting")

    correlations = event.get("source_target_correlation")
    if not isinstance(correlations, Mapping):
        correlations = {}
    for field in ("session_id", "task_id"):
        if event.get(field + "_seen") is not True:
            reasons.append("startup-task-%s-identity-missing" % field.replace("_id", ""))
        if correlations.get(field) != "match":
            reasons.append("startup-task-%s-identity-not-source-matched" % field.replace("_id", ""))
    source_identity = seed.get("source_identity_digests") if seed is not None else None
    if isinstance(source_identity, Mapping):
        for field in ("agent_id", "tool_use_id"):
            if correlations.get(field) == "mismatch":
                reasons.append("startup-task-%s-identity-conflict" % field)
            source_seen = source_identity.get(field + "_seen") is True
            target_seen = event.get(field + "_seen") is True
            if source_seen and target_seen and correlations.get(field) != "match":
                reasons.append("startup-task-%s-identity-not-source-matched" % field)
            if correlations.get(field) not in {"match", "unknown"}:
                reasons.append("startup-task-%s-identity-classification-invalid" % field)
    else:
        reasons.append("source-task-identity-digests-missing")

    arrivals = observation.get("startup_request_observation")
    if not isinstance(arrivals, Mapping):
        arrivals = {}
        reasons.append("startup-request-arrival-observation-missing")
    if arrivals.get("enabled") is not True or arrivals.get("closed") is not True:
        reasons.append("startup-request-arrival-window-not-closed")
    for name in (
        "request_arrival_count", "messages_route_arrival_count",
        "other_route_arrival_count", "parent_arrival_count",
        "child_arrival_count", "unclassified_arrival_count",
        "in_flight_count",
    ):
        if type(arrivals.get(name)) is not int or arrivals.get(name) != 0:
            reasons.append("startup-%s-not-zero" % name.replace("_", "-"))
    if arrivals.get("overflow") is not False:
        reasons.append("startup-request-arrival-overflow-or-unknown")

    if observation.get("startup_activity_observed") is not False:
        reasons.append("startup-assistant-or-tool-activity-observed")
    if observation.get("startup_other_lifecycle_events") != 0:
        reasons.append("startup-other-lifecycle-event-observed-or-unknown")
    if observation.get("startup_unexpected_frame_count") != 0:
        reasons.append("startup-unexpected-frame-observed-or-unknown")
    if observation.get("reader_error") is not False:
        reasons.append("startup-reader-error-or-unknown")
    for name, reason in (
        ("unparsed_frames", "startup-unparsed-frame-count-invalid-or-nonzero"),
        ("partial_frames", "startup-partial-frame-count-invalid-or-nonzero"),
        ("unclassified_lifecycle_events", "startup-unclassified-lifecycle-event"),
    ):
        value = observation.get(name)
        if type(value) is not int or value != 0:
            reasons.append(reason)

    result_count = observation.get("startup_result_count")
    result_origins = observation.get("startup_result_origins")
    if (type(result_count) is not int or result_count != 1
            or not isinstance(result_origins, list)
            or len(result_origins) != result_count
            or result_origins != ["task-notification"]):
        reasons.append("startup-task-notification-result-not-observed-exactly-once")
    if observation.get("startup_result_origin_overflow") is not False:
        reasons.append("startup-result-origin-observation-overflow-or-unknown")
    if observation.get("startup_result_error_count") != 0:
        reasons.append("startup-error-result-observed")
    if observation.get("startup_result_parent_session_match_count") != 1:
        reasons.append("startup-result-parent-session-not-correlated")
    if observation.get("startup_result_parent_session_mismatch_count") != 0:
        reasons.append("startup-result-parent-session-mismatch")
    if (observation.get("startup_result_parent_session_id_digest")
            != observation.get("parent_uuid_digest")):
        reasons.append("startup-result-parent-session-digest-mismatch")

    allowed = not reasons
    return {
        "observation_scope": "two-domain-terminal-task-startup",
        "history_query_mode": TWO_DOMAIN_HISTORY_QUERY_MODE,
        "history_query_allowed": allowed,
        "history_query_skipped": not allowed,
        "terminal_task_correlation_only": allowed,
        "verdict": "inconclusive",
        "support_claim": False,
        "reason_codes": sorted(set(reasons)),
    }


def _control_event_observed(
    observation: Mapping[str, object],
    name: str,
) -> bool:
    # No verified selected-CLI event schema exists for these internal
    # operations.  In particular, accepting ``{"worker_state_clear": 1}``
    # from a fixture or unit caller would turn fabricated evidence into a
    # runtime fact.  Keep the producer closed until a correlated public
    # emitter is pinned and implemented.
    del observation, name
    return False


def assess_positive_orphan_observation(
    observation: Mapping[str, object],
) -> dict[str, object]:
    """Assess an actual unfinished-worker startup, without trace promotion.

    The source crash and a pre-crash record count only establish that an
    unfinished input existed.  Positive orphan support requires the selected
    runtime itself to expose each load/wake/enqueue event and a corresponding
    target model request.  The pinned CLI's public event schema for those
    internal operations is currently unavailable, so source-symbol names and
    bare stream subtypes never satisfy these fields.
    """
    reasons: list[str] = []
    if observation.get("control_mode") not in {
        "crash-left-unfinished", "positive-orphan",
    }:
        reasons.append("positive-orphan-control-mode-not-selected")
    for name, reason in (
        ("crash_requested", "positive-orphan-crash-not-observed"),
        ("records_observed_before_crash", "positive-orphan-record-load-not-seeded"),
        ("observed_owned_processes_excluded", "positive-orphan-writer-exclusion-not-observed"),
        ("source_parent_process_exited", "positive-orphan-source-exit-not-observed"),
        ("target_launched", "positive-orphan-target-not-launched"),
        ("target_hold_complete", "positive-orphan-target-hold-not-complete"),
    ):
        if observation.get(name) is not True:
            reasons.append(reason)

    event_names = (
        "persisted_record_load",
        "restored_orphans",
        "child_parent_wake",
        "notification_enqueue",
    )
    event_status = {
        name: "observed" if _control_event_observed(observation, name)
        else "unknown"
        for name in event_names
    }
    if any(value == "unknown" for value in event_status.values()):
        reasons.append("selected-runtime-orphan-event-schema-unavailable")
    model_query_attempt = observation.get("target_model_request_observed") is True
    if not model_query_attempt:
        reasons.append("positive-orphan-model-query-not-observed")

    complete = not reasons
    return {
        "observation_scope": "selected-runtime-unfinished-worker-startup",
        "status": "observed" if complete else "unsupported",
        **event_status,
        "model_query_attempt": "observed" if model_query_attempt else "unknown",
        "support_claim": False,
        "verdict": "inconclusive",
        "observation_boundary": (
            "loopback-request-only; selected-cli-lifecycle-schema-unavailable"
        ),
        "reason_codes": sorted(set(reasons)),
    }


def assess_terminal_clear_observation(
    observation: Mapping[str, object],
) -> dict[str, object]:
    """Assess stop/clear/no-wake facts as independent selected-runtime facts."""
    reasons: list[str] = []
    if observation.get("control_mode") not in {"stopped", "terminal-cleared"}:
        reasons.append("terminal-clear-control-mode-not-selected")
    for name, reason in (
        ("actual_task_id", "terminal-clear-task-id-not-observed"),
        ("stop_receipt", "terminal-clear-stop-receipt-not-observed"),
        ("stopped_notification", "terminal-clear-terminal-event-not-observed"),
        ("tool_terminal", "terminal-clear-tool-terminal-not-observed"),
        ("tracked_process_exited_before_cleanup", "terminal-clear-process-exit-not-observed"),
        ("source_parent_process_exited", "terminal-clear-source-exit-not-observed"),
    ):
        if not observation.get(name):
            reasons.append(reason)
    if observation.get("forced_cleanup") is True:
        reasons.append("terminal-clear-forced-cleanup")
    source_control_messages = observation.get("source_control_messages")
    if type(source_control_messages) is not int:
        reasons.append("terminal-clear-source-control-count-unknown")
    elif source_control_messages > 0:
        reasons.append("terminal-clear-source-control-request-observed")

    worker_state_clear = _control_event_observed(
        observation, "worker_state_clear"
    )
    orphan_state_clear = _control_event_observed(
        observation, "orphan_state_clear"
    )
    terminal_state_clear = worker_state_clear and orphan_state_clear
    if not worker_state_clear or not orphan_state_clear:
        reasons.append("selected-runtime-state-clear-schema-unavailable")

    target_launched = observation.get("target_launched") is True
    target_hold_complete = observation.get("target_hold_complete") is True
    target_connect = (
        target_launched
        and target_hold_complete
        and observation.get("target_connect_observed") is True
        and observation.get("target_initialize_succeeded") is True
        and observation.get("target_session_identity_correlated") is True
        and observation.get("target_loader_correlated") is True
    )
    if not target_connect:
        reasons.append("target-connect-correlation-unavailable")

    target_wake_absent = (
        observation.get("target_no_wake_observed") is True
        and observation.get("target_wake_sensor_calibrated") is True
        and observation.get("endpoint_sensor_calibrated") is True
        and observation.get("target_initialize_succeeded") is True
        and observation.get("target_session_identity_correlated") is True
    )
    target_model_request_free = observation.get("target_model_request_free") is True
    if not target_wake_absent:
        reasons.append("target-no-wake-observation-surface-unavailable")
    if not target_model_request_free:
        reasons.append("terminal-clear-target-model-request-unknown-or-observed")

    complete = not reasons
    return {
        "observation_scope": "selected-runtime-terminal-clear-and-target-hold",
        "status": "observed" if complete else "unsupported",
        "terminal_state_clear": "observed" if terminal_state_clear else "unknown",
        "target_connect": "observed" if target_connect else "unknown",
        "target_no_wake": "observed" if target_wake_absent else "unknown",
        "model_query_attempt": (
            "not-observed" if target_model_request_free is True else "unknown"
        ),
        "control_request_free": (
            False if type(source_control_messages) is int
            and source_control_messages > 0 else "unknown"
        ),
        "negative_gate": (
            "source-control-request-observed"
            if type(source_control_messages) is int and source_control_messages > 0
            else "source-control-request-not-observed"
        ),
        "worker_state_clear": (
            "observed" if worker_state_clear else "unknown"
        ),
        "orphan_state_clear": (
            "observed" if orphan_state_clear else "unknown"
        ),
        "support_claim": False,
        "verdict": "inconclusive",
        "observation_boundary": (
            "loopback-request-only; selected-cli-lifecycle-schema-unavailable"
        ),
        "reason_codes": sorted(set(reasons)),
    }


def replace_resume_sentinel(arguments: list[str], session_id: str) -> list[str]:
    """Substitute only the value emitted by the SDK options builder."""
    if not session_id:
        raise ValueError("empty session id")
    matches = [
        index for index, value in enumerate(arguments)
        if value == RESUME_SENTINEL or value == "--resume=" + RESUME_SENTINEL
    ]
    if len(matches) != 1:
        raise ValueError("SDK resume template must contain one sentinel")
    if sum(value == "--resume" or value.startswith("--resume=")
           for value in arguments) != 1:
        raise ValueError("SDK resume template contains an unexpected resume flag")
    return [
        session_id if value == RESUME_SENTINEL
        else "--resume=" + session_id
        if value == "--resume=" + RESUME_SENTINEL
        else value
        for value in arguments
    ]


def safe_event(event: object) -> dict[str, object]:
    """Reduce native output to statuses/digests, never report content/prompts."""
    if not isinstance(event, Mapping):
        return {"frame": "unparsed"}
    response = event.get("response")
    response = response if isinstance(response, Mapping) else {}
    subtype = event.get("subtype") or response.get("subtype")
    task_id = event.get("task_id")
    agent_id = event.get("agent_id")
    return {
        "type": event.get("type") if isinstance(event.get("type"), str) else "unknown",
        "subtype": subtype if isinstance(subtype, str) else None,
        "status": event.get("status") if isinstance(event.get("status"), str) else None,
        "task_id_seen": bool(task_id),
        "task_id_digest": digest(task_id),
        "agent_id_seen": bool(agent_id),
        "agent_id_digest": digest(agent_id),
        "request_id": bool(response.get("request_id")),
    }


def _native_raw_field(event: object, key: str) -> tuple[object | None, str | None]:
    if not isinstance(event, Mapping):
        return None, None
    values: list[object] = []
    containers: list[Mapping[str, object]] = [event]
    response = event.get("response")
    if isinstance(response, Mapping):
        containers.append(response)
    data = event.get("data")
    if isinstance(data, Mapping):
        containers.append(data)
    response_data = response.get("data") if isinstance(response, Mapping) else None
    if isinstance(response_data, Mapping):
        containers.append(response_data)
    for container in containers:
        value = container.get(key)
        if value is not None:
            values.append(value)
        # TaskUpdatedMessage carries its terminal state at patch.status.  Some
        # emitters also include a top-level status, so both locations must
        # agree when present.
        patch = container.get("patch")
        if key == "status" and isinstance(patch, Mapping):
            value = patch.get("status")
            if value is not None:
                values.append(value)
    if not values:
        return None, None
    if any(value != values[0] for value in values[1:]):
        return values[0], "conflicting-field"
    return values[0], None


def _native_event_value(event: object, key: str) -> object | None:
    value, _ = _native_raw_field(event, key)
    return value


def _native_allowlisted_token(
    event: object,
    *,
    field: str,
    keys: tuple[str, ...],
    allowed: set[str],
    unknown_fields: list[str],
) -> str | None:
    value = None
    for key in keys:
        value, error = _native_raw_field(event, key)
        if error:
            unknown_fields.append("conflicting-" + field)
            return None
        if value is not None:
            break
    if value is None:
        subtype = _native_event_value(event, "subtype")
        optional_by_subtype = {
            "task-type": {"task_progress", "task_updated", "task_notification"},
            "status": {"task_started", "task_progress"},
        }
        if subtype not in optional_by_subtype.get(field, set()):
            unknown_fields.append("missing-" + field)
        return None
    if not isinstance(value, str) or not value or len(value) > MAX_NATIVE_TASK_TOKEN:
        unknown_fields.append("malformed-" + field)
        return None
    if value not in allowed:
        unknown_fields.append("unrecognized-" + field)
        return None
    return value


def _native_identity_digest(
    event: object,
    field: str,
    *,
    trusted_sanitized: bool = False,
) -> tuple[str | None, bool, str | None]:
    """Return only an identity digest, presence, and a sanitized error code."""

    if (
        trusted_sanitized and isinstance(event, Mapping)
        and event.get("record_schema") == NATIVE_TASK_RECORD_SCHEMA
        and field + "_seen" in event
    ):
        seen = event.get(field + "_seen") is True
        value = event.get(field + "_digest")
        if not seen:
            return None, False, None
        if (
            isinstance(value, str)
            and len(value) == 64
            and re.fullmatch(r"[0-9a-f]{64}", value)
        ):
            return value, True, None
        return None, True, "malformed-identity"
    raw_field = "uuid" if field == "event_uuid" else field
    value, error = _native_raw_field(event, raw_field)
    if error:
        return None, False, "conflicting-identity"
    if value is None:
        return None, False, None
    if not isinstance(value, str) or not value or len(value) > MAX_NATIVE_TASK_TOKEN:
        return None, False, "malformed-identity"
    return digest(value), True, None


def _native_source_identity_digest(
    source_identity: Mapping[str, object] | None,
    field: str,
) -> tuple[str | None, bool, str | None]:
    if not isinstance(source_identity, Mapping):
        return None, False, None
    value = source_identity.get(field)
    if value is None:
        return None, False, None
    if not isinstance(value, str) or not value or len(value) > MAX_NATIVE_TASK_TOKEN:
        return None, False, "malformed-identity"
    return digest(value), True, None


def _native_source_identity_digest_value(
    source_identity_digests: Mapping[str, object] | None,
    field: str,
) -> tuple[str | None, bool, str | None]:
    """Read a validated digest-only source identity without hashing it again."""

    if not isinstance(source_identity_digests, Mapping):
        return None, False, None
    if source_identity_digests.get("schema") != NATIVE_TASK_SOURCE_IDENTITY_DIGESTS_SCHEMA:
        return None, False, "malformed-source-identity-digests"
    seen = source_identity_digests.get(field + "_seen")
    value = source_identity_digests.get(field + "_digest")
    if type(seen) is not bool:
        return None, False, "malformed-source-identity-digests"
    if not seen:
        if value is not None:
            return None, False, "malformed-source-identity-digests"
        return None, False, None
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        return None, True, "malformed-source-identity-digests"
    return value, True, None


def _native_event_token(event: object, field: str) -> str | None:
    if not isinstance(event, Mapping):
        return None
    if isinstance(event.get(field), str):
        return event[field]
    aliases = {
        "event_type": ("type",),
        "event_subtype": ("subtype",),
        "task_type": ("task_type",),
        "status": ("status",),
    }
    for key in aliases.get(field, ()):
        value, error = _native_raw_field(event, key)
        if error:
            return None
        if isinstance(value, str):
            return value
    return None


def _native_join_compatible(current: Mapping[str, object], prior: Mapping[str, object]) -> bool:
    for field in ("session_id", "task_id"):
        current_digest, current_seen, _ = _native_identity_digest(
            current, field, trusted_sanitized=True
        )
        prior_digest, prior_seen, _ = _native_identity_digest(
            prior, field, trusted_sanitized=True
        )
        if not current_seen or not prior_seen or current_digest != prior_digest:
            return False
    for field in ("agent_id", "tool_use_id"):
        current_digest, current_seen, _ = _native_identity_digest(
            current, field, trusted_sanitized=True
        )
        prior_digest, prior_seen, _ = _native_identity_digest(
            prior, field, trusted_sanitized=True
        )
        # The pinned SDK omits agent_id from task notifications and may omit
        # tool_use_id from terminal updates.  These are useful when observed,
        # but their absence is not evidence of a conflicting task.
        if current_seen and prior_seen and current_digest != prior_digest:
            return False
    current_type = _native_event_token(current, "task_type")
    prior_type = _native_event_token(prior, "task_type")
    return not (current_type and prior_type and current_type != prior_type)


def _native_correlation_class(
    current: Mapping[str, object],
    prior: Mapping[str, object] | None,
) -> str:
    current_subtype = _native_event_token(current, "event_subtype")
    status = _native_event_token(current, "status")
    if (
        status not in NATIVE_TASK_TERMINAL_STATUSES
        or current_subtype not in {"task_notification", "task_updated"}
        or not isinstance(prior, Mapping)
        or current.get("incomplete") is True
    ):
        return "live-or-unresolved"
    # A notification and an update patch are distinct SDK observations. Do
    # not translate one terminal representation into the other while
    # correlating target evidence.
    if _native_event_token(prior, "event_subtype") != current_subtype:
        return "live-or-unresolved"
    for event in (current, prior):
        for field in ("session_id", "task_id"):
            _, seen, error = _native_identity_digest(
                event, field, trusted_sanitized=True
            )
            if error or (not seen and not (
                field == "session_id"
                and event.get("source_target_correlation", {}).get(field)
                == "match"
            )):
                return "live-or-unresolved"
        _, _, error = _native_identity_digest(
            event, "event_uuid", trusted_sanitized=True
        )
        if error:
            return "live-or-unresolved"
    if not _native_join_compatible(current, prior):
        return "live-or-unresolved"
    if _native_event_token(prior, "status") != status:
        return "live-or-unresolved"
    current_uuid, current_seen, _ = _native_identity_digest(
        current, "event_uuid", trusted_sanitized=True
    )
    prior_uuid, prior_seen, _ = _native_identity_digest(
        prior, "event_uuid", trusted_sanitized=True
    )
    if current_seen and prior_seen and current_uuid == prior_uuid:
        return "replay-compatible"
    return "terminal-correlation-only"


def sanitize_native_task_lifecycle_event(
    event: object,
    *,
    phase: str,
    observation_sequence: int,
    source_identity: Mapping[str, object] | None = None,
    source_identity_digests: Mapping[str, object] | None = None,
    prior_event: Mapping[str, object] | None = None,
    provenance: str = "offline-observation",
) -> dict[str, object]:
    """Return one bounded native-task observation without raw event values."""

    unknown_fields: list[str] = []
    if phase not in NATIVE_TASK_PHASES:
        unknown_fields.append("invalid-phase")
        safe_phase = "unknown"
    else:
        safe_phase = phase
    if type(observation_sequence) is not int or observation_sequence < 1:
        unknown_fields.append("invalid-observation-sequence")
        safe_sequence: int | None = None
    else:
        safe_sequence = observation_sequence
    if provenance not in NATIVE_TASK_PROVENANCES:
        unknown_fields.append("invalid-provenance")
        safe_provenance = "offline-observation"
    else:
        safe_provenance = provenance

    event_type = _native_allowlisted_token(
        event,
        field="event-type",
        keys=("type",),
        allowed=NATIVE_TASK_EVENT_TYPES,
        unknown_fields=unknown_fields,
    )
    event_subtype = _native_allowlisted_token(
        event,
        field="event-subtype",
        keys=("subtype",),
        allowed=NATIVE_TASK_SUBTYPES,
        unknown_fields=unknown_fields,
    )
    task_type = _native_allowlisted_token(
        event,
        field="task-type",
        keys=("task_type",),
        allowed=NATIVE_TASK_TYPES,
        unknown_fields=unknown_fields,
    )
    status = _native_allowlisted_token(
        event,
        field="status",
        keys=("status",),
        allowed=NATIVE_TASK_STATUSES,
        unknown_fields=unknown_fields,
    )

    identities: dict[str, tuple[str | None, bool]] = {}
    for field in (
        "session_id",
        "task_id",
        "event_uuid",
        "tool_use_id",
        "agent_id",
    ):
        value_digest, seen, error = _native_identity_digest(event, field)
        if error:
            unknown_fields.append(error)
        identities[field] = (value_digest, seen)

    source_target_correlation: dict[str, str] = {}
    source_identity_available = (
        isinstance(source_identity, Mapping)
        or isinstance(source_identity_digests, Mapping)
    )
    if isinstance(source_identity_digests, Mapping):
        expected_digest_keys = {
            "schema",
            *(field + suffix for field in (
                "session_id", "task_id", "tool_use_id", "agent_id",
            )
              for suffix in ("_seen", "_digest")),
        }
        if (set(source_identity_digests) != expected_digest_keys
                or source_identity_digests.get("schema")
                != NATIVE_TASK_SOURCE_IDENTITY_DIGESTS_SCHEMA):
            unknown_fields.append("malformed-source-identity-digests")
    for field in ("session_id", "task_id", "tool_use_id", "agent_id"):
        current_digest, current_seen = identities[field]
        if isinstance(source_identity_digests, Mapping):
            source_digest, source_seen, error = _native_source_identity_digest_value(
                source_identity_digests, field
            )
        else:
            source_digest, source_seen, error = _native_source_identity_digest(
                source_identity, field
            )
        if error:
            unknown_fields.append(error)
        if current_seen and source_seen:
            if current_digest == source_digest:
                source_target_correlation[field] = "match"
            else:
                source_target_correlation[field] = "mismatch"
                unknown_fields.append("identity-conflict")
        else:
            source_target_correlation[field] = "unknown"
            optional_observation_absent = (
                field in {"agent_id", "tool_use_id"}
                and (
                    not identities[field][1]
                    or not source_seen
                )
            ) or (
                field == "session_id"
                and event_subtype == "task_updated"
                and not identities[field][1]
            )
            if (source_identity_available and (source_seen or current_seen)
                    and not optional_observation_absent):
                unknown_fields.append("identity-unresolved")

    evidence: dict[str, object] = {
        "record_schema": NATIVE_TASK_RECORD_SCHEMA,
        "provenance": safe_provenance,
        "phase": safe_phase,
        "observation_sequence": safe_sequence,
        "event_type": event_type,
        "event_subtype": event_subtype,
        "task_type": task_type,
        "status": status,
        "source_target_correlation": source_target_correlation,
        "correlation_class": "live-or-unresolved",
        "unknown_fields": sorted(set(unknown_fields)),
        "incomplete": bool(unknown_fields),
        "support_claim": False,
    }
    for field, (value_digest, seen) in identities.items():
        evidence[field + "_seen"] = seen
        evidence[field + "_digest"] = value_digest
    evidence["correlation_class"] = _native_correlation_class(evidence, prior_event)
    if (
        status in NATIVE_TASK_TERMINAL_STATUSES
        and prior_event is not None
        and safe_phase == "target/startup"
        and evidence["correlation_class"] == "live-or-unresolved"
    ):
        unknown_fields.append("terminal-correlation-unresolved")
        evidence["unknown_fields"] = sorted(set(unknown_fields))
        evidence["incomplete"] = True
    return evidence


def record_native_task_lifecycle_event(
    frame: object,
    runtime: dict[str, object],
) -> dict[str, object] | None:
    """Record a bounded sanitized native-task event in an existing runtime."""

    subtype = _native_event_value(frame, "subtype")
    if subtype not in NATIVE_TASK_SUBTYPES:
        return None
    if runtime.get("native_task_recording_enabled", True) is not True:
        return None
    sequence = int(runtime.get("native_task_observation_sequence", 0)) + 1
    runtime["native_task_observation_sequence"] = sequence
    events = runtime.setdefault("native_task_evidence", [])
    if not isinstance(events, list):
        events = []
        runtime["native_task_evidence"] = events
        runtime["native_task_evidence_overflow"] = True
        _append_native_task_reason(runtime, "malformed-recorder")
    limit = runtime.get("native_task_evidence_limit", MAX_NATIVE_TASK_EVIDENCE)
    if type(limit) is not int or limit < 1 or limit > MAX_NATIVE_TASK_EVIDENCE:
        runtime["native_task_evidence_overflow"] = True
        _append_native_task_reason(runtime, "invalid-evidence-limit")
        return None
    if len(events) >= limit:
        runtime["native_task_evidence_overflow"] = True
        _append_native_task_reason(runtime, "native-task-evidence-overflow")
        return None
    if (
        runtime.get("lifecycle_phase") == "target/startup"
        and "native_task_source_terminal_seed" in runtime
    ):
        source_seed = runtime.get("native_task_source_terminal_seed")
        prior_event = (
            source_seed
            if (
                isinstance(source_seed, Mapping)
                and source_seed.get("provenance") == "source-terminal-seed"
            )
            else None
        )
    else:
        prior_event = (
            runtime.get("native_task_last_observation")
            if isinstance(runtime.get("native_task_last_observation"), Mapping)
            else None
        )
    evidence = sanitize_native_task_lifecycle_event(
        frame,
        phase=str(runtime.get("lifecycle_phase", "unknown")),
        observation_sequence=sequence,
        source_identity=(
            runtime.get("source_identity")
            if isinstance(runtime.get("source_identity"), Mapping)
            else None
        ),
        source_identity_digests=(
            runtime.get("native_task_source_identity_digests")
            if isinstance(runtime.get("native_task_source_identity_digests"), Mapping)
            else None
        ),
        prior_event=prior_event,
        provenance=str(runtime.get("lifecycle_provenance", "offline-observation")),
    )
    events.append(evidence)
    event_origins = runtime.setdefault("native_task_event_origins", [])
    if not isinstance(event_origins, list):
        event_origins = []
        runtime["native_task_event_origins"] = event_origins
        runtime["native_task_evidence_overflow"] = True
        _append_native_task_reason(runtime, "malformed-event-origin-recorder")
    if len(event_origins) < MAX_NATIVE_TASK_EVIDENCE:
        event_origins.append({
            "observation_sequence": sequence,
            "origin_kind": native_task_event_origin_kind(frame),
        })
    else:
        runtime["native_task_evidence_overflow"] = True
        _append_native_task_reason(runtime, "native-task-origin-overflow")
    runtime["native_task_last_observation"] = evidence
    if evidence.get("incomplete"):
        for reason in (
            evidence.get("unknown_fields", [])
            if isinstance(evidence.get("unknown_fields"), list)
            else ["incomplete-native-task-event"]
        ):
            _append_native_task_reason(runtime, str(reason))
    return evidence


def _append_native_task_reason(runtime: dict[str, object], reason: str) -> None:
    reasons = runtime.setdefault("native_task_evidence_unknown_reasons", [])
    if not isinstance(reasons, list):
        reasons = []
        runtime["native_task_evidence_unknown_reasons"] = reasons
    if reason not in reasons and len(reasons) < MAX_NATIVE_TASK_EVIDENCE:
        reasons.append(reason)


def source_terminal_lifecycle_seed(
    runtime: Mapping[str, object],
) -> dict[str, object] | None:
    events = runtime.get("native_task_evidence", [])
    if not isinstance(events, list):
        return None
    for event in reversed(events):
        if not isinstance(event, Mapping):
            continue
        if (
            event.get("record_schema") != NATIVE_TASK_RECORD_SCHEMA
            or event.get("phase") != "source/drain"
            or event.get("provenance") != "source-observed"
            or event.get("event_subtype") != "task_notification"
            or event.get("status") not in NATIVE_TASK_TERMINAL_STATUSES
            or event.get("incomplete") is True
            or event.get("session_id_seen") is not True
            or event.get("task_id_seen") is not True
        ):
            continue
        seed = dict(event)
        seed["provenance"] = "source-terminal-seed"
        return seed
    return None


def _native_task_source_identity_digest_record(
    started_event: Mapping[str, object],
    agent_id_digest: str,
) -> dict[str, object] | None:
    fields = ("session_id", "task_id", "tool_use_id")
    record: dict[str, object] = {
        "schema": NATIVE_TASK_SOURCE_IDENTITY_DIGESTS_SCHEMA,
    }
    for field in fields:
        seen = started_event.get(field + "_seen")
        value = started_event.get(field + "_digest")
        if field == "tool_use_id" and seen is False:
            if value is not None:
                return None
            record[field + "_seen"] = False
            record[field + "_digest"] = None
            continue
        if (seen is not True or not isinstance(value, str)
                or re.fullmatch(r"[0-9a-f]{64}", value) is None):
            return None
        record[field + "_seen"] = seen
        record[field + "_digest"] = value
    if re.fullmatch(r"[0-9a-f]{64}", agent_id_digest) is None:
        return None
    record["agent_id_seen"] = True
    record["agent_id_digest"] = agent_id_digest
    return record


_NATIVE_TASK_SEED_EVENT_FIELDS = {
    "record_schema", "provenance", "phase", "observation_sequence",
    "event_type", "event_subtype", "task_type", "status",
    "source_target_correlation", "correlation_class", "unknown_fields",
    "incomplete", "support_claim",
    *(field + suffix for field in (
        "session_id", "task_id", "event_uuid", "tool_use_id", "agent_id",
    ) for suffix in ("_seen", "_digest")),
}


def _native_task_sanitized_event_valid(
    event: object,
    *,
    subtype: str,
) -> bool:
    if not isinstance(event, Mapping) or set(event) != _NATIVE_TASK_SEED_EVENT_FIELDS:
        return False
    correlation = event.get("source_target_correlation")
    if (not isinstance(correlation, Mapping)
            or set(correlation) != {
                "session_id", "task_id", "tool_use_id", "agent_id",
            }
            or any(value != "unknown" for value in correlation.values())):
        return False
    allowed_phases = (
        {"source/setup", "source/drain"}
        if subtype == "task_started"
        else {"source/drain"}
    )
    if (
        event.get("record_schema") != NATIVE_TASK_RECORD_SCHEMA
        or event.get("provenance") != (
            "source-terminal-seed"
            if subtype == "task_notification" else "source-observed"
        )
        or event.get("phase") not in allowed_phases
        or type(event.get("observation_sequence")) is not int
        or not 1 <= int(event.get("observation_sequence", 0)) <= MAX_NATIVE_TASK_EVIDENCE
        or event.get("event_type") not in NATIVE_TASK_EVENT_TYPES
        or event.get("event_subtype") != subtype
        or event.get("correlation_class") != "live-or-unresolved"
        or event.get("unknown_fields") != []
        or event.get("incomplete") is not False
        or event.get("support_claim") is not False
    ):
        return False
    if subtype == "task_started":
        if (event.get("task_type") != "local_agent"
                or event.get("status") not in {None, "started", "running"}):
            return False
    elif (event.get("task_type") not in {None, *NATIVE_TASK_TYPES}
            or event.get("status") not in NATIVE_TASK_TERMINAL_STATUSES):
        return False
    for field in ("session_id", "task_id", "event_uuid", "tool_use_id", "agent_id"):
        seen = event.get(field + "_seen")
        value = event.get(field + "_digest")
        if type(seen) is not bool:
            return False
        if seen:
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                return False
        elif value is not None:
            return False
    if (event.get("task_id_seen") is not True
            or (subtype != "task_updated"
                and event.get("session_id_seen") is not True)):
        return False
    return True


def _native_task_source_seed_event_valid(event: object) -> bool:
    if not isinstance(event, Mapping):
        return False
    subtype = event.get("event_subtype")
    return subtype == "task_notification" and (
        _native_task_sanitized_event_valid(event, subtype="task_notification")
    )


def _native_task_started_seed_event_valid(event: object) -> bool:
    return _native_task_sanitized_event_valid(event, subtype="task_started")


def _valid_native_hook_seed_record(
    record: object,
    *,
    expected_agent_type: str,
) -> bool:
    if not isinstance(record, Mapping):
        return False
    event_name = record.get("hook_event_name")
    expected = {
        "record_schema", "hook_event_name", "observation_sequence",
        "provenance", "join_status", "session_id_seen", "session_id_digest",
        "task_id_seen", "agent_id_seen", "agent_id_digest", "agent_type",
        "transcript_path_seen", "transcript_path_digest", "cwd_seen",
        "cwd_digest", "tool_use_id_seen",
    }
    if record.get("task_id_seen") is True:
        expected.add("task_id_digest")
    if record.get("tool_use_id_seen") is True:
        expected.add("tool_use_id_digest")
    if event_name == "SubagentStop":
        expected.update({
            "agent_transcript_path_seen", "agent_transcript_path_digest",
            "stop_hook_active",
        })
    if (
        set(record) != expected
        or record.get("record_schema") != "native-hook-observation-v1"
        or event_name not in NATIVE_HOOK_CALLBACK_IDS
        or type(record.get("observation_sequence")) is not int
        or not 1 <= int(record.get("observation_sequence", 0)) <= MAX_NATIVE_HOOK_EVIDENCE
        or record.get("provenance") != "hook-observed"
        or record.get("join_status") not in {"joined", "unresolved"}
        or record.get("agent_type") != expected_agent_type
        or record.get("session_id_seen") is not True
        or record.get("agent_id_seen") is not True
        or record.get("transcript_path_seen") is not True
        or record.get("cwd_seen") is not True
        or type(record.get("task_id_seen")) is not bool
        or type(record.get("tool_use_id_seen")) is not bool
        or (record.get("join_status") == "joined"
            and (record.get("task_id_seen") is not True
                 or record.get("tool_use_id_seen") is not True))
        or (event_name == "SubagentStop"
            and (record.get("agent_transcript_path_seen") is not True
                 or type(record.get("stop_hook_active")) is not bool))
    ):
        return False
    digest_fields = [
        "session_id_digest", "agent_id_digest", "transcript_path_digest",
        "cwd_digest",
    ]
    if record.get("task_id_seen") is True:
        digest_fields.append("task_id_digest")
    elif "task_id_digest" in record:
        return False
    if record.get("tool_use_id_seen") is True:
        digest_fields.append("tool_use_id_digest")
    elif "tool_use_id_digest" in record:
        return False
    if event_name == "SubagentStop":
        digest_fields.append("agent_transcript_path_digest")
    for field in digest_fields:
        if (not isinstance(record.get(field), str)
                or re.fullmatch(r"[0-9a-f]{64}", str(record.get(field))) is None):
            return False
    for field in ("session_id_seen", "agent_id_seen", "transcript_path_seen", "cwd_seen"):
        if record.get(field) is not True:
            return False
    return True


def _native_task_agent_proof_valid(
    proof: object,
    started_event: Mapping[str, object],
    *,
    expected_agent_type: str,
) -> bool:
    fields = {
        "record_schema", "provenance", "session_id_digest", "task_id_digest",
        "tool_use_id_seen", "tool_use_id_digest", "agent_id_seen",
        "agent_id_digest", "hook_record", "sidecar_record",
    }
    if not isinstance(proof, Mapping) or set(proof) != fields:
        return False
    if (
        proof.get("record_schema") != NATIVE_TASK_AGENT_PROOF_SCHEMA
        or proof.get("provenance") not in {"task_started", "native_hook", "sdk_sidecar"}
        or proof.get("session_id_digest") != started_event.get("session_id_digest")
        or proof.get("task_id_digest") != started_event.get("task_id_digest")
        or proof.get("tool_use_id_seen") is not started_event.get("tool_use_id_seen")
        or proof.get("tool_use_id_digest") != started_event.get("tool_use_id_digest")
        or proof.get("agent_id_seen") is not True
        or not isinstance(proof.get("agent_id_digest"), str)
        or re.fullmatch(r"[0-9a-f]{64}", str(proof.get("agent_id_digest"))) is None
    ):
        return False
    started_agent_seen = started_event.get("agent_id_seen") is True
    if started_agent_seen:
        if (proof.get("provenance") != "task_started"
                or proof.get("agent_id_digest")
                != started_event.get("agent_id_digest")):
            return False
    elif proof.get("provenance") not in {"native_hook", "sdk_sidecar"}:
        return False
    if proof.get("provenance") == "task_started":
        return (
            proof.get("hook_record") is None
            and proof.get("sidecar_record") is None
            and started_event.get("agent_id_seen") is True
            and proof.get("agent_id_digest") == started_event.get("agent_id_digest")
        )
    hook_record = proof.get("hook_record")
    sidecar_record = proof.get("sidecar_record")
    if proof.get("provenance") == "sdk_sidecar":
        return bool(
            started_event.get("agent_id_seen") is False
            and started_event.get("tool_use_id_seen") is True
            and isinstance(started_event.get("tool_use_id_digest"), str)
            and re.fullmatch(
                r"[0-9a-f]{64}", str(started_event.get("tool_use_id_digest"))
            ) is not None
            and _valid_native_hook_seed_record(
                hook_record, expected_agent_type=expected_agent_type,
            )
            and isinstance(hook_record, Mapping)
            and hook_record.get("session_id_digest")
            == started_event.get("session_id_digest")
            and hook_record.get("join_status") == "unresolved"
            and hook_record.get("task_id_seen") is False
            and hook_record.get("tool_use_id_seen") is True
            and hook_record.get("tool_use_id_digest")
            != started_event.get("tool_use_id_digest")
            and hook_record.get("agent_id_digest") == proof.get("agent_id_digest")
            and _valid_native_task_sdk_sidecar_proof(
                sidecar_record,
                started_event,
                hook_record,
                expected_agent_type=expected_agent_type,
            )
        )
    return bool(
        sidecar_record is None
        and _valid_native_hook_seed_record(
            hook_record, expected_agent_type=expected_agent_type,
        )
        and hook_record.get("session_id_digest")
        == started_event.get("session_id_digest")
        and hook_record.get("tool_use_id_seen") is True
        and hook_record.get("tool_use_id_digest")
        == started_event.get("tool_use_id_digest")
        and (hook_record.get("task_id_seen") is not True
             or hook_record.get("task_id_digest") == started_event.get("task_id_digest"))
        and hook_record.get("agent_id_digest") == proof.get("agent_id_digest")
    )


def _valid_native_task_sdk_sidecar_proof(
    sidecar: object,
    started_event: Mapping[str, object],
    hook_record: Mapping[str, object],
    *,
    expected_agent_type: str,
) -> bool:
    fields = {
        "record_schema", "session_id_digest", "agent_id_digest", "agent_type",
        "task_tool_use_id_digest", "parent_agent_id_seen",
        "parent_history_session_proven", "child_history_session_agent_proven",
        "matching_sidecar_count", "scan_complete", "parent_history_path_digest",
        "child_transcript_path_digest", "parent_history_sha256",
        "child_transcript_sha256", "sidecar_sha256",
    }
    if not isinstance(sidecar, Mapping) or set(sidecar) != fields:
        return False
    if (
        sidecar.get("record_schema") != NATIVE_TASK_SDK_SIDECAR_PROOF_SCHEMA
        or sidecar.get("session_id_digest") != started_event.get("session_id_digest")
        or sidecar.get("agent_id_digest") != hook_record.get("agent_id_digest")
        or sidecar.get("agent_type") != expected_agent_type
        or sidecar.get("task_tool_use_id_digest")
        != started_event.get("tool_use_id_digest")
        or sidecar.get("parent_agent_id_seen") is not False
        or sidecar.get("parent_history_session_proven") is not True
        or sidecar.get("child_history_session_agent_proven") is not True
        or type(sidecar.get("matching_sidecar_count")) is not int
        or sidecar.get("matching_sidecar_count") != 1
        or sidecar.get("scan_complete") is not True
    ):
        return False
    for field in (
        "parent_history_path_digest", "child_transcript_path_digest",
        "parent_history_sha256", "child_transcript_sha256", "sidecar_sha256",
        "task_tool_use_id_digest",
    ):
        if (not isinstance(sidecar.get(field), str)
                or re.fullmatch(r"[0-9a-f]{64}", str(sidecar.get(field))) is None):
            return False
    if (hook_record.get("hook_event_name") == "SubagentStop"
            and hook_record.get("agent_transcript_path_digest")
            != sidecar.get("child_transcript_path_digest")):
        return False
    return True


def _native_hook_mismatch_diagnostics_match_records(
    runtime: Mapping[str, object],
    started_event: Mapping[str, object],
    *,
    expected_agent_type: str,
) -> bool:
    if runtime.get("native_hook_mismatch_diagnostic_overflow") is True:
        return False
    mismatches = _native_hook_mismatch_records(runtime, started_event)
    diagnostics = runtime.get("native_hook_mismatch_diagnostics", [])
    if not isinstance(diagnostics, list):
        return False
    selected = [
        diagnostic for diagnostic in diagnostics
        if isinstance(diagnostic, Mapping)
        and diagnostic.get("reason") == "callback-task-tool-use-id-mismatch"
    ]
    if len(mismatches) != len(selected):
        return False
    by_sequence = {
        diagnostic.get("observation_sequence"): diagnostic
        for diagnostic in selected
        if _valid_native_hook_mismatch_diagnostic(
            diagnostic, expected_agent_type=expected_agent_type,
        )
    }
    if len(by_sequence) != len(selected):
        return False
    start_tool = started_event.get("tool_use_id_digest")
    for record in mismatches:
        diagnostic = by_sequence.get(record.get("observation_sequence"))
        if not isinstance(diagnostic, Mapping):
            return False
        callback_digest = diagnostic.get("callback_tool_use_id_digest")
        input_digest = diagnostic.get("input_tool_use_id_digest")
        effective_digest = (
            callback_digest
            if diagnostic.get("callback_tool_use_id_seen") is True
            else input_digest
        )
        if (
            diagnostic.get("hook_event_name") != record.get("hook_event_name")
            or diagnostic.get("hook_session_id_digest")
            != record.get("session_id_digest")
            or diagnostic.get("hook_agent_id_digest")
            != record.get("agent_id_digest")
            or diagnostic.get("task_tool_use_id_digest") != start_tool
            or effective_digest != record.get("tool_use_id_digest")
            or diagnostic.get("task_id_digest") != started_event.get("task_id_digest")
        ):
            return False
    return True


def _native_hook_seed_agent_proof(
    runtime: Mapping[str, object],
    started_event: Mapping[str, object],
    *,
    sdk_sidecar_record: Mapping[str, object] | None = None,
    sdk_sidecar_reason: str | None = None,
) -> tuple[dict[str, object] | None, str | None]:
    hooks = runtime.get("native_hook_evidence", [])
    if not isinstance(hooks, list):
        return None, "terminal-task-hook-evidence-incomplete"
    if (runtime.get("native_hook_evidence_overflow") is True
            or runtime.get("native_hook_request_overflow") is True
            or runtime.get("native_hook_mismatch_diagnostic_overflow") is True):
        return None, "terminal-task-hook-evidence-incomplete"
    expected_agent_type = runtime.get("native_agent_type", SOURCE_AGENT_NAME)
    if not isinstance(expected_agent_type, str) or not expected_agent_type:
        return None, "terminal-task-hook-evidence-incomplete"
    reasons = runtime.get("native_hook_unknown_reasons", [])
    if (not isinstance(reasons, list)
            or any(not isinstance(reason, str) for reason in reasons)):
        return None, "terminal-task-hook-evidence-incomplete"
    mismatch_records = _native_hook_mismatch_records(runtime, started_event)
    has_legacy_mismatch_reason = "hook-tool-use-id-mismatch" in reasons
    other_reasons = [
        reason for reason in reasons if reason != "hook-tool-use-id-mismatch"
    ]
    if other_reasons or (
        has_legacy_mismatch_reason
        and not _native_hook_mismatch_diagnostics_match_records(
            runtime, started_event, expected_agent_type=expected_agent_type,
        )
    ):
        return None, "terminal-task-hook-evidence-incomplete"
    if (mismatch_records and not _native_hook_mismatch_diagnostics_match_records(
        runtime, started_event, expected_agent_type=expected_agent_type,
    )):
        return None, "terminal-task-hook-evidence-incomplete"
    if mismatch_records and sdk_sidecar_reason == "ambiguous":
        return None, "terminal-task-sdk-sidecar-evidence-ambiguous"
    if mismatch_records and sdk_sidecar_reason == "conflict":
        return None, "terminal-task-sdk-sidecar-evidence-conflict"
    start_session = started_event.get("session_id_digest")
    start_task = started_event.get("task_id_digest")
    start_tool_seen = started_event.get("tool_use_id_seen") is True
    start_tool = started_event.get("tool_use_id_digest")
    exact: list[Mapping[str, object]] = []
    agent_bindings: dict[str, tuple[object, object, object]] = {}
    task_binding_conflict = False
    for record in hooks:
        if not isinstance(record, Mapping) or not _valid_native_hook_seed_record(
            record, expected_agent_type=expected_agent_type,
        ):
            return None, "terminal-task-hook-evidence-incomplete"
        mismatched_unresolved = bool(
            record.get("join_status") == "unresolved"
            and record.get("task_id_seen") is False
            and record.get("tool_use_id_seen") is True
            and record.get("tool_use_id_digest") != start_tool
        )
        binding = (
            record.get("session_id_digest"),
            record.get("task_id_digest") if record.get("task_id_seen") is True else None,
            record.get("tool_use_id_digest")
            if record.get("tool_use_id_seen") is True and not mismatched_unresolved
            else None,
        )
        agent_digest = str(record.get("agent_id_digest"))
        previous = agent_bindings.get(agent_digest)
        if previous is not None:
            merged: list[object] = []
            for prior_value, current_value in zip(previous, binding):
                if (prior_value is not None and current_value is not None
                        and prior_value != current_value):
                    return None, "terminal-task-hook-evidence-ambiguous"
                merged.append(prior_value if prior_value is not None else current_value)
            agent_bindings[agent_digest] = tuple(merged)
        else:
            agent_bindings[agent_digest] = binding
        same_task = (
            record.get("session_id_digest") == start_session
            and record.get("task_id_seen") is True
            and record.get("task_id_digest") == start_task
        )
        if same_task and (
            record.get("tool_use_id_seen") is not True
            or not start_tool_seen
            or record.get("tool_use_id_digest") != start_tool
        ):
            task_binding_conflict = True
        is_exact = bool(
            start_tool_seen
            and record.get("session_id_digest") == start_session
            and record.get("tool_use_id_seen") is True
            and record.get("tool_use_id_digest") == start_tool
            and (record.get("task_id_seen") is not True
                 or record.get("task_id_digest") == start_task)
        )
        if is_exact:
            exact.append(record)
    if task_binding_conflict:
        return None, "terminal-task-hook-evidence-ambiguous"
    agent_ids = {record.get("agent_id_digest") for record in exact}
    if len(agent_ids) > 1:
        return None, "terminal-task-hook-evidence-ambiguous"
    if exact and sdk_sidecar_record is not None and mismatch_records:
        sidecar_agent = sdk_sidecar_record.get("agent_id_digest")
        sidecar_hook = next(
            (
                record for record in mismatch_records
                if record.get("agent_id_digest") == sidecar_agent
                and _valid_native_task_sdk_sidecar_proof(
                    sdk_sidecar_record,
                    started_event,
                    record,
                    expected_agent_type=expected_agent_type,
                )
            ),
            None,
        )
        if sidecar_hook is not None and sidecar_agent not in agent_ids:
            return None, "terminal-task-sdk-sidecar-evidence-ambiguous"
    if not exact:
        if sdk_sidecar_record is not None and len(mismatch_records) > 0:
            agent_ids = {record.get("agent_id_digest") for record in mismatch_records}
            if len(agent_ids) != 1:
                return None, "terminal-task-sdk-sidecar-evidence-ambiguous"
            selected_mismatch = min(
                mismatch_records,
                key=lambda record: int(record.get("observation_sequence", 0)),
            )
            return {
                "record_schema": NATIVE_TASK_AGENT_PROOF_SCHEMA,
                "provenance": "sdk_sidecar",
                "session_id_digest": start_session,
                "task_id_digest": start_task,
                "tool_use_id_seen": start_tool_seen,
                "tool_use_id_digest": start_tool,
                "agent_id_seen": True,
                "agent_id_digest": selected_mismatch.get("agent_id_digest"),
                "hook_record": dict(selected_mismatch),
                "sidecar_record": dict(sdk_sidecar_record),
            }, None
        if sdk_sidecar_reason == "ambiguous":
            return None, "terminal-task-sdk-sidecar-evidence-ambiguous"
        if sdk_sidecar_reason == "conflict":
            return None, "terminal-task-sdk-sidecar-evidence-conflict"
        if sdk_sidecar_reason in {"incomplete", "missing", "unavailable"}:
            return None, "terminal-task-sdk-sidecar-evidence-incomplete"
        return None, "terminal-task-agent-proof-unavailable"
    selected = min(exact, key=lambda record: int(record.get("observation_sequence", 0)))
    return {
        "record_schema": NATIVE_TASK_AGENT_PROOF_SCHEMA,
        "provenance": "native_hook",
        "session_id_digest": start_session,
        "task_id_digest": start_task,
        "tool_use_id_seen": start_tool_seen,
        "tool_use_id_digest": start_tool,
        "agent_id_seen": True,
        "agent_id_digest": selected.get("agent_id_digest"),
        "hook_record": dict(selected),
        "sidecar_record": None,
    }, None


def native_task_source_terminal_seed_envelope(
    runtime: Mapping[str, object],
    *,
    parent_uuid: object,
    source_invocation: object,
    sdk_sidecar_record: Mapping[str, object] | None = None,
    sdk_sidecar_reason: str | None = None,
) -> dict[str, object]:
    """Create a bounded, digest-only handoff for one observed terminal task."""

    parent_digest = digest(parent_uuid)
    invocation_digest = digest(source_invocation)
    lifecycle = native_task_lifecycle_report(runtime)
    candidate = source_terminal_lifecycle_seed(runtime)
    reason: str | None = None
    identity_digests: dict[str, object] | None = None
    started_event: dict[str, object] | None = None
    agent_proof: dict[str, object] | None = None
    if lifecycle.get("incomplete") is True or lifecycle.get("overflow") is True:
        reason = "terminal-task-seed-incomplete"
        candidate = None
    elif candidate is None:
        events = runtime.get("native_task_evidence", [])
        updated_terminal_seen = bool(
            isinstance(events, list)
            and any(
                isinstance(event, Mapping)
                and event.get("event_subtype") == "task_updated"
                and event.get("status") in NATIVE_TASK_TERMINAL_STATUSES
                and event.get("phase") == "source/drain"
                for event in events
            )
        )
        reason = (
            "terminal-task-notification-not-observed"
            if updated_terminal_seen
            else "terminal-task-seed-not-observed"
        )
    elif not _native_task_source_seed_event_valid(candidate):
        reason = "terminal-task-seed-incomplete"
        candidate = None
    else:
        events = runtime.get("native_task_evidence", [])
        matching_starts = [
            event for event in events
            if isinstance(event, Mapping)
            and event.get("event_subtype") == "task_started"
            and event.get("session_id_digest") == (
                candidate.get("session_id_digest")
                if candidate.get("session_id_seen") is True
                else digest(runtime.get("session_id"))
            )
            and event.get("task_id_digest") == candidate.get("task_id_digest")
        ] if isinstance(events, list) else []
        if len(matching_starts) != 1:
            reason = "terminal-task-start-proof-unavailable"
            candidate = None
        elif not _native_task_started_seed_event_valid(matching_starts[0]):
            reason = "terminal-task-seed-incomplete"
            candidate = None
        elif (matching_starts[0].get("observation_sequence")
                >= candidate.get("observation_sequence")):
            reason = "terminal-task-start-proof-unavailable"
            candidate = None
        else:
            started_event = dict(matching_starts[0])
        if candidate is not None and started_event is not None:
            valid_starts = [
                event for event in events
                if isinstance(event, Mapping)
                and _native_task_started_seed_event_valid(event)
                and event.get("session_id_digest")
                == started_event.get("session_id_digest")
            ] if isinstance(events, list) else []
            if started_event.get("tool_use_id_seen") is True:
                tool_tasks = {
                    event.get("task_id_digest")
                    for event in valid_starts
                    if event.get("tool_use_id_seen") is True
                    and event.get("tool_use_id_digest")
                    == started_event.get("tool_use_id_digest")
                }
                if len(tool_tasks) > 1:
                    reason = "terminal-task-hook-evidence-ambiguous"
                    candidate = None
                    started_event = None
        actual_task = runtime.get("actual_task_id")
        actual_session = runtime.get("session_id")
        if (candidate is not None and started_event is not None and (
            not isinstance(parent_uuid, str) or not parent_uuid
            or not isinstance(source_invocation, str) or not source_invocation
            or digest(actual_session) != parent_digest
            or (candidate.get("session_id_seen") is True
                and candidate.get("session_id_digest") != parent_digest)
            or started_event.get("session_id_digest") != parent_digest
            or not isinstance(actual_task, str) or not actual_task
            or digest(actual_task) != candidate.get("task_id_digest")
        )):
            reason = "terminal-task-seed-identity-unlinked"
            candidate = None
            started_event = None
        if candidate is not None and started_event is not None:
            terminal_agent_seen = candidate.get("agent_id_seen") is True
            started_agent_seen = started_event.get("agent_id_seen") is True
            if started_agent_seen:
                reused_agent_tasks = {
                    event.get("task_id_digest")
                    for event in events
                    if isinstance(event, Mapping)
                    and _native_task_started_seed_event_valid(event)
                    and event.get("session_id_digest")
                    == started_event.get("session_id_digest")
                    and event.get("agent_id_seen") is True
                    and event.get("agent_id_digest")
                    == started_event.get("agent_id_digest")
                } if isinstance(events, list) else set()
                if len(reused_agent_tasks) > 1:
                    reason = "terminal-task-hook-evidence-ambiguous"
                    candidate = None
                    started_event = None
            if (candidate is not None and started_event is not None
                    and terminal_agent_seen and started_agent_seen
                    and candidate.get("agent_id_digest")
                    != started_event.get("agent_id_digest")):
                reason = "terminal-task-seed-identity-unlinked"
                candidate = None
                started_event = None
            if candidate is not None:
                direct_agent_digest = (
                    started_event.get("agent_id_digest")
                    if started_agent_seen else None
                )
                proof, proof_error = _native_hook_seed_agent_proof(
                    runtime,
                    started_event,
                    sdk_sidecar_record=sdk_sidecar_record,
                    sdk_sidecar_reason=sdk_sidecar_reason,
                )
                if started_agent_seen:
                    if proof_error in {
                        "terminal-task-hook-evidence-incomplete",
                        "terminal-task-hook-evidence-ambiguous",
                    }:
                        reason = proof_error
                        candidate = None
                        started_event = None
                    else:
                        hook_digest = (
                            proof.get("agent_id_digest")
                            if isinstance(proof, Mapping) else None
                        )
                        if hook_digest is not None and hook_digest != direct_agent_digest:
                            reason = "terminal-task-hook-evidence-ambiguous"
                            candidate = None
                            started_event = None
                        else:
                            agent_proof = {
                                "record_schema": NATIVE_TASK_AGENT_PROOF_SCHEMA,
                                "provenance": "task_started",
                                "session_id_digest": started_event.get("session_id_digest"),
                                "task_id_digest": started_event.get("task_id_digest"),
                                "tool_use_id_seen": started_event.get("tool_use_id_seen"),
                                "tool_use_id_digest": started_event.get("tool_use_id_digest"),
                                "agent_id_seen": True,
                                "agent_id_digest": direct_agent_digest,
                                "hook_record": None,
                                "sidecar_record": None,
                            }
                elif proof is None:
                    reason = proof_error or "terminal-task-agent-proof-unavailable"
                    candidate = None
                    started_event = None
                else:
                    agent_proof = proof
                if (candidate is not None and started_event is not None
                        and agent_proof is not None
                        and not _native_task_agent_proof_valid(
                            agent_proof,
                            started_event,
                            expected_agent_type=(
                                runtime.get("native_agent_type", SOURCE_AGENT_NAME)
                                if isinstance(
                                    runtime.get("native_agent_type", SOURCE_AGENT_NAME),
                                    str,
                                ) else SOURCE_AGENT_NAME
                            ),
                        )):
                    reason = (
                        "terminal-task-sdk-sidecar-evidence-incomplete"
                        if agent_proof.get("provenance") == "sdk_sidecar"
                        else "terminal-task-hook-evidence-incomplete"
                    )
                    candidate = None
                    started_event = None
                    agent_proof = None
                if candidate is not None and started_event is not None and agent_proof is not None:
                    proof_agent_digest = agent_proof.get("agent_id_digest")
                    reused_agent_tasks = {
                        started_event.get("task_id_digest"),
                    } | {
                        event.get("task_id_digest")
                        for event in events
                        if isinstance(event, Mapping)
                        and _native_task_started_seed_event_valid(event)
                        and event.get("session_id_digest")
                        == started_event.get("session_id_digest")
                        and event.get("agent_id_seen") is True
                        and event.get("agent_id_digest") == proof_agent_digest
                    } if isinstance(events, list) else set()
                    if len(reused_agent_tasks) > 1:
                        reason = (
                            "terminal-task-hook-evidence-ambiguous"
                            if agent_proof.get("provenance") == "native_hook"
                            else "terminal-task-seed-identity-unlinked"
                        )
                        candidate = None
                        started_event = None
                        agent_proof = None
                if candidate is not None and started_event is not None and agent_proof is not None:
                    current_tool = runtime.get("task_tool_use_id")
                    actual_agent = runtime.get("task_agent_id")
                    terminal_tool_seen = candidate.get("tool_use_id_seen") is True
                    started_tool_seen = started_event.get("tool_use_id_seen") is True
                    terminal_agent_digest = candidate.get("agent_id_digest")
                    if (terminal_tool_seen and (
                            not started_tool_seen
                            or candidate.get("tool_use_id_digest")
                            != started_event.get("tool_use_id_digest"))):
                        reason = "terminal-task-seed-identity-unlinked"
                        candidate = None
                        started_event = None
                        agent_proof = None
                    elif (terminal_agent_seen
                            and terminal_agent_digest
                            != agent_proof.get("agent_id_digest")):
                        reason = "terminal-task-seed-identity-unlinked"
                        candidate = None
                        started_event = None
                        agent_proof = None
                    elif (current_tool is not None
                            and digest(current_tool)
                            != started_event.get("tool_use_id_digest")):
                        reason = "terminal-task-seed-identity-unlinked"
                        candidate = None
                        started_event = None
                        agent_proof = None
                    elif (actual_agent is not None
                            and digest(actual_agent)
                            != agent_proof.get("agent_id_digest")):
                        reason = "terminal-task-seed-identity-unlinked"
                        candidate = None
                        started_event = None
                        agent_proof = None
                    else:
                        identity_digests = _native_task_source_identity_digest_record(
                            started_event, str(agent_proof.get("agent_id_digest")),
                        )
                        if identity_digests is None:
                            reason = "terminal-task-seed-incomplete"
                            candidate = None
                            started_event = None
                            agent_proof = None
    if candidate is None:
        identity_digests = None
        started_event = None
        agent_proof = None
    else:
        reason = None
    core: dict[str, object] = {
        "schema": NATIVE_TASK_SOURCE_SEED_SCHEMA,
        "status": "available" if candidate is not None else "unavailable",
        "source_invocation_digest": invocation_digest,
        "parent_uuid_digest": parent_digest,
        "terminal_event": dict(candidate) if candidate is not None else None,
        "task_started_event": dict(started_event) if started_event is not None else None,
        "agent_proof": dict(agent_proof) if agent_proof is not None else None,
        "source_identity_digests": identity_digests,
        "reason_code": None if candidate is not None else reason,
    }
    return {
        **core,
        "seed_digest": hashlib.sha256(_canonical_json(core)).hexdigest(),
    }


def validate_native_task_source_terminal_seed_envelope(
    envelope: object,
    *,
    expected_parent_uuid_digest: object,
    expected_source_invocation_digest: object,
) -> dict[str, object]:
    """Validate and detach a seed envelope before durable release/target use."""

    fields = {
        "schema", "status", "source_invocation_digest", "parent_uuid_digest",
        "terminal_event", "task_started_event", "agent_proof",
        "source_identity_digests", "reason_code", "seed_digest",
    }
    if not isinstance(envelope, Mapping) or set(envelope) != fields:
        raise ValueError("source terminal seed envelope schema mismatch")
    if envelope.get("schema") != NATIVE_TASK_SOURCE_SEED_SCHEMA:
        raise ValueError("source terminal seed schema is unsupported")
    for value in (
        expected_parent_uuid_digest, expected_source_invocation_digest,
        envelope.get("parent_uuid_digest"), envelope.get("source_invocation_digest"),
        envelope.get("seed_digest"),
    ):
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("source terminal seed digest is malformed")
    if (envelope.get("parent_uuid_digest") != expected_parent_uuid_digest
            or envelope.get("source_invocation_digest")
            != expected_source_invocation_digest):
        raise ValueError("source terminal seed binding mismatch")
    core = {key: envelope[key] for key in fields if key != "seed_digest"}
    if hashlib.sha256(_canonical_json(core)).hexdigest() != envelope.get("seed_digest"):
        raise ValueError("source terminal seed digest mismatch")
    status = envelope.get("status")
    if status == "unavailable":
        if (envelope.get("terminal_event") is not None
                or envelope.get("task_started_event") is not None
                or envelope.get("agent_proof") is not None
                or envelope.get("source_identity_digests") is not None
                or envelope.get("reason_code") not in NATIVE_TASK_SEED_UNAVAILABLE_REASONS):
            raise ValueError("source terminal seed unavailable record is malformed")
    elif status == "available":
        event = envelope.get("terminal_event")
        started_event = envelope.get("task_started_event")
        agent_proof = envelope.get("agent_proof")
        identity = envelope.get("source_identity_digests")
        if (envelope.get("reason_code") is not None
                or not _native_task_source_seed_event_valid(event)
                or not _native_task_started_seed_event_valid(started_event)
                or not isinstance(started_event, Mapping)
                or not isinstance(agent_proof, Mapping)
                or not isinstance(identity, Mapping)):
            raise ValueError("source terminal seed evidence is incomplete")
        expected_identity = _native_task_source_identity_digest_record(
            started_event, str(agent_proof.get("agent_id_digest")),
        )
        if (event.get("task_id_digest") != started_event.get("task_id_digest")
                or started_event.get("observation_sequence")
                >= event.get("observation_sequence")
                or (event.get("session_id_seen") is True
                    and event.get("session_id_digest")
                    != started_event.get("session_id_digest"))
                or (event.get("tool_use_id_seen") is True
                    and (started_event.get("tool_use_id_seen") is not True
                         or event.get("tool_use_id_digest")
                         != started_event.get("tool_use_id_digest")))
                or (event.get("agent_id_seen") is True
                    and event.get("agent_id_digest")
                    != agent_proof.get("agent_id_digest"))):
            raise ValueError("source terminal seed task binding mismatch")
        if (not _native_task_agent_proof_valid(
                agent_proof, started_event,
                expected_agent_type=SOURCE_AGENT_NAME,
        )):
            raise ValueError("source terminal seed agent proof is incomplete")
        if (expected_identity is None or dict(identity) != expected_identity
                or started_event.get("session_id_digest") != expected_parent_uuid_digest
                or (event.get("session_id_seen") is True
                    and event.get("session_id_digest") != expected_parent_uuid_digest)):
            raise ValueError("source terminal seed identity binding mismatch")
    else:
        raise ValueError("source terminal seed status is invalid")
    detached = json.loads(_canonical_json(dict(envelope)))
    if not isinstance(detached, dict):
        raise ValueError("source terminal seed detachment failed")
    return detached


def native_task_lifecycle_report(runtime: Mapping[str, object]) -> dict[str, object]:
    """Build the report attachment for bounded native-task observations."""

    events = runtime.get("native_task_evidence", [])
    events = [event for event in events if isinstance(event, Mapping)] \
        if isinstance(events, list) else []
    unknown_reasons: list[str] = []
    configured_reasons = runtime.get("native_task_evidence_unknown_reasons", [])
    if isinstance(configured_reasons, list):
        unknown_reasons.extend(str(reason) for reason in configured_reasons)
    for event in events:
        fields = event.get("unknown_fields")
        if isinstance(fields, list):
            unknown_reasons.extend(str(field) for field in fields)
    incomplete = bool(runtime.get("native_task_evidence_overflow")) or any(
        event.get("incomplete") is True for event in events
    )
    if runtime.get("native_task_evidence_overflow"):
        unknown_reasons.append("native-task-evidence-overflow")
    if not events and not incomplete:
        observation_status = "not-observed"
    else:
        observation_status = "unknown" if incomplete else "observed"
    return {
        "observation_status": observation_status,
        "event_count": len(events),
        "observation_sequence_max": max(
            (
                event.get("observation_sequence")
                for event in events
                if type(event.get("observation_sequence")) is int
            ),
            default=0,
        ),
        "overflow": bool(runtime.get("native_task_evidence_overflow")),
        "incomplete": incomplete,
        "seed_provenance": runtime.get("native_task_seed_provenance", "none"),
        "source_terminal_seed_index": runtime.get(
            "native_task_source_terminal_index"
        ),
        "unknown_reasons": sorted(set(unknown_reasons))[:MAX_NATIVE_TASK_EVIDENCE],
        "events": [dict(event) for event in events],
        "event_origins": [
            dict(row) for row in runtime.get("native_task_event_origins", [])
            if isinstance(row, Mapping)
        ][:MAX_NATIVE_TASK_EVIDENCE]
        if isinstance(runtime.get("native_task_event_origins"), list) else [],
        "support_claim": False,
    }


def snapshot_native_task_lifecycle(runtime: Mapping[str, object]) -> dict[str, object]:
    """Freeze one bounded lifecycle report as JSON-safe detached data."""

    snapshot = json.loads(_canonical_json(native_task_lifecycle_report(runtime)))
    if not isinstance(snapshot, dict):
        raise RuntimeError("native task lifecycle snapshot is malformed")
    return snapshot


def _history_boundary(value: object, fallback: str) -> tuple[str, bool]:
    if not isinstance(value, str) or not value or len(value) > 96:
        return fallback, False
    if re.fullmatch(r"[a-z0-9][a-z0-9/_-]*", value) is None:
        return fallback, False
    return value, True


def _history_input_record(
    value: object,
    *,
    role: str,
    max_bytes: int,
) -> tuple[bytes | None, str, str | None]:
    default_attribution = "observed" if role == "parent" else "candidate"
    if value is None:
        return None, default_attribution, "missing-" + role
    attribution = default_attribution
    if isinstance(value, Mapping):
        supplied_attribution = value.get("attribution")
        if supplied_attribution is not None:
            if supplied_attribution not in HISTORY_ATTRIBUTIONS:
                return None, "unattributed", "malformed"
            attribution = str(supplied_attribution)
        if value.get("status") == "unknown":
            reason = value.get("reason")
            if reason in HISTORY_UNKNOWN_REASONS:
                return None, attribution, str(reason)
            return None, attribution, "malformed"
        value = value.get("content")
    if not isinstance(value, (bytes, bytearray)):
        return None, attribution, "malformed"
    content = bytes(value)
    if len(content) > max_bytes:
        return None, attribution, "oversized"
    return content, attribution, None


def compare_history_content_integrity(
    before: Mapping[str, object],
    after: Mapping[str, object],
    *,
    before_boundary: str = "source-excluded/pre-release",
    after_boundary: str = "post-startup-before-cleanup",
    max_bytes: int = MAX_HISTORY_CONTENT_BYTES,
) -> dict[str, object]:
    """Compare bounded parent/child bytes without returning paths or bodies."""

    safe_before_boundary, before_boundary_valid = _history_boundary(
        before_boundary, "unknown"
    )
    safe_after_boundary, after_boundary_valid = _history_boundary(
        after_boundary, "unknown"
    )
    unknown_reasons: list[str] = []
    if not before_boundary_valid or not after_boundary_valid:
        unknown_reasons.append("malformed")
    if type(max_bytes) is not int or max_bytes < 1 or max_bytes > MAX_HISTORY_CONTENT_BYTES:
        max_bytes = MAX_HISTORY_CONTENT_BYTES
        unknown_reasons.append("invalid-limit")
    if not isinstance(before, Mapping):
        before = {}
        unknown_reasons.append("malformed")
    if not isinstance(after, Mapping):
        after = {}
        unknown_reasons.append("malformed")

    roles: dict[str, object] = {}
    for role in ("parent", "child"):
        before_content, before_attribution, before_error = _history_input_record(
            before.get(role), role=role, max_bytes=max_bytes
        )
        after_content, after_attribution, after_error = _history_input_record(
            after.get(role), role=role, max_bytes=max_bytes
        )
        if before_error:
            unknown_reasons.append(before_error)
        if after_error:
            unknown_reasons.append(after_error)
        attribution = before_attribution
        if before_attribution != after_attribution:
            unknown_reasons.append("attribution-changed")
            attribution = "unattributed"
        association = (
            "observed-link" if attribution == "observed" else "unattributed"
        )
        content_integrity = "unknown"
        prefix_integrity = "unknown"
        checked_prefix_bytes = 0
        if before_content is not None and after_content is not None:
            content_integrity = (
                "preserved" if before_content == after_content else "changed"
            )
            # Every accepted file is bounded by max_bytes, so the complete
            # observed before image is the checked prefix.  This does not
            # imply that bytes beyond that bounded image were retained.
            checked_prefix_bytes = len(before_content)
            prefix_integrity = (
                "preserved"
                if len(after_content) >= checked_prefix_bytes
                and after_content[:checked_prefix_bytes] == before_content
                else "changed"
            )
        roles[role] = {
            "attribution": attribution,
            "association": association,
            "before_status": "observed" if before_content is not None else "unknown",
            "after_status": "observed" if after_content is not None else "unknown",
            "before_size": len(before_content) if before_content is not None else None,
            "after_size": len(after_content) if after_content is not None else None,
            "before_digest": (
                hashlib.sha256(before_content).hexdigest()
                if before_content is not None else None
            ),
            "after_digest": (
                hashlib.sha256(after_content).hexdigest()
                if after_content is not None else None
            ),
            "content_integrity": content_integrity,
            "prefix_integrity": prefix_integrity,
            "checked_prefix_bytes": checked_prefix_bytes,
            "prefix_scope": "complete-bounded-before-observation",
        }
    return {
        "observation_status": "unknown" if unknown_reasons else "observed",
        "before_boundary": safe_before_boundary,
        "after_boundary": safe_after_boundary,
        "roles": roles,
        "unknown_reasons": sorted(set(unknown_reasons)),
        "history_scope": "bounded-regular-file-bytes",
        "runtime_loaded_or_restored": "unverified",
        "support_claim": False,
    }


def _history_unknown_record(reason: str, attribution: str) -> dict[str, object]:
    return {
        "status": "unknown",
        "reason": reason if reason in HISTORY_UNKNOWN_REASONS else "malformed",
        "attribution": attribution,
    }


def _history_file_signature(file_stat: os.stat_result) -> tuple[int, ...]:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_mode,
        file_stat.st_size,
        file_stat.st_mtime_ns,
        file_stat.st_ctime_ns,
    )


def _capture_history_file(
    root: Path,
    relative_path: object,
    *,
    attribution: str,
    max_bytes: int,
    require_single_link: bool = False,
) -> dict[str, object]:
    """Read one stable bounded regular file through a no-follow descriptor."""

    if type(max_bytes) is not int or max_bytes < 1 or max_bytes > MAX_HISTORY_CONTENT_BYTES:
        return _history_unknown_record("invalid-limit", attribution)
    if not isinstance(relative_path, (str, Path)):
        return _history_unknown_record("missing", attribution)
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        return _history_unknown_record("outside-root", attribution)

    root_fd: int | None = None
    current_fd: int | None = None
    try:
        root_resolved = root.resolve(strict=True)
        candidate = root.joinpath(relative)
        cursor = root
        for part in relative.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                return _history_unknown_record("symlink", attribution)
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(root_resolved)
        except ValueError:
            return _history_unknown_record("outside-root", attribution)

        nofollow = getattr(os, "O_NOFOLLOW", 0)
        nonblock = getattr(os, "O_NONBLOCK", 0)
        if not nofollow:
            return _history_unknown_record("no-follow-unavailable", attribution)
        if not nonblock:
            return _history_unknown_record("nonblock-unavailable", attribution)
        directory = getattr(os, "O_DIRECTORY", 0)
        root_fd = os.open(
            str(root), os.O_RDONLY | directory | nofollow | nonblock
        )
        current_fd = root_fd
        parts = relative.parts
        for index, part in enumerate(parts):
            flags = os.O_RDONLY | nofollow | nonblock
            if index < len(parts) - 1:
                flags |= directory
            next_fd = os.open(part, flags, dir_fd=current_fd)
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd

        before_stat = os.fstat(current_fd)
        if not stat.S_ISREG(before_stat.st_mode):
            return _history_unknown_record("not-regular", attribution)
        if require_single_link and before_stat.st_nlink != 1:
            return _history_unknown_record("hardlink", attribution)
        if before_stat.st_size > max_bytes:
            return _history_unknown_record("oversized", attribution)

        content_parts: list[bytes] = []
        total = 0
        read_limit = max_bytes + 1
        while total < read_limit:
            chunk = os.read(current_fd, min(65536, read_limit - total))
            if not chunk:
                break
            content_parts.append(chunk)
            total += len(chunk)
        content = b"".join(content_parts)
        after_stat = os.fstat(current_fd)
        if (
            len(content) > max_bytes
            or len(content) != before_stat.st_size
            or (require_single_link and after_stat.st_nlink != 1)
            or _history_file_signature(before_stat)
            != _history_file_signature(after_stat)
        ):
            return _history_unknown_record(
                "oversized" if len(content) > max_bytes
                else "hardlink" if require_single_link and after_stat.st_nlink != 1
                else "unstable",
                attribution,
            )
    except FileNotFoundError:
        return _history_unknown_record("missing", attribution)
    except OSError as exc:
        return _history_unknown_record(
            "symlink" if exc.errno == errno.ELOOP else "read-failed",
            attribution,
        )
    finally:
        if current_fd is not None and current_fd != root_fd:
            try:
                os.close(current_fd)
            except OSError:
                pass
        if root_fd is not None:
            try:
                os.close(root_fd)
            except OSError:
                pass
    return {
        "status": "observed",
        "content": content,
        "attribution": attribution,
    }


def _history_path_component(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 256:
        return None
    if "\x00" in value or "/" in value or "\\" in value:
        return None
    if value in {".", ".."}:
        return None
    return value


def _history_parent_session_observed(content: bytes, session_id: str) -> bool:
    """Check only top-level JSONL ``sessionId`` metadata, never message bodies."""

    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return False
    matched = False
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except (TypeError, ValueError):
            return False
        if not isinstance(entry, Mapping):
            return False
        if entry.get("sessionId") == session_id:
            matched = True
    return matched


def _strict_json_object(content: bytes) -> dict[str, object] | None:
    """Decode one JSON object while rejecting duplicate keys at every depth."""

    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(
            content.decode("utf-8"), object_pairs_hook=unique_pairs,
        )
    except (UnicodeDecodeError, TypeError, ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _sdk_parent_history_session_proven(
    content: bytes,
    session_id: str,
) -> bool:
    """Require valid top-level SDK parent entries with no conflicting session."""

    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return False
    matched = False
    for line in lines:
        if not line.strip():
            continue
        entry = _strict_json_object(line.encode("utf-8"))
        if entry is None:
            return False
        if "sessionId" in entry:
            if entry.get("sessionId") != session_id:
                return False
            matched = True
    return matched


def _sdk_child_history_identity_proven(
    content: bytes,
    session_id: str,
    agent_id: str,
) -> bool:
    """Use only top-level sessionId/agentId fields, never message bodies."""

    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return False
    matched = False
    for line in lines:
        if not line.strip():
            continue
        entry = _strict_json_object(line.encode("utf-8"))
        if entry is None:
            return False
        if "sessionId" in entry and entry.get("sessionId") != session_id:
            return False
        if "agentId" in entry and entry.get("agentId") != agent_id:
            return False
        if entry.get("sessionId") == session_id and entry.get("agentId") == agent_id:
            matched = True
    return matched


def _sdk_sidecar_metadata(content: bytes) -> dict[str, object] | None:
    metadata = _strict_json_object(content)
    if metadata is None:
        return None
    tool_use_id = metadata.get("toolUseId")
    if tool_use_id is not None and (
        not isinstance(tool_use_id, str)
        or not tool_use_id
        or len(tool_use_id) > MAX_NATIVE_TASK_TOKEN
    ):
        return None
    parent_agent_id = metadata.get("parentAgentId")
    if parent_agent_id is not None and (
        not isinstance(parent_agent_id, str)
        or not parent_agent_id
        or len(parent_agent_id) > MAX_NATIVE_TASK_TOKEN
    ):
        return None
    return metadata


def _native_hook_mismatch_records(
    runtime: Mapping[str, object],
    started_event: Mapping[str, object],
) -> list[Mapping[str, object]]:
    records = runtime.get("native_hook_evidence", [])
    if not isinstance(records, list):
        return []
    expected_agent_type = runtime.get("native_agent_type", SOURCE_AGENT_NAME)
    if not isinstance(expected_agent_type, str) or not expected_agent_type:
        return []
    start_tool = started_event.get("tool_use_id_digest")
    start_session = started_event.get("session_id_digest")
    if (started_event.get("tool_use_id_seen") is not True
            or not isinstance(start_tool, str)
            or not isinstance(start_session, str)):
        return []
    return [
        record for record in records
        if isinstance(record, Mapping)
        and _valid_native_hook_seed_record(
            record, expected_agent_type=expected_agent_type,
        )
        and record.get("join_status") == "unresolved"
        and record.get("task_id_seen") is False
        and record.get("tool_use_id_seen") is True
        and record.get("tool_use_id_digest") != start_tool
        and record.get("session_id_digest") == start_session
    ]


def native_hook_sdk_sidecar_bridge(
    root: Path,
    runtime: Mapping[str, object],
) -> tuple[dict[str, object] | None, dict[str, object]]:
    """Build a detached, fail-closed link from a hook agent to its SDK parent tool.

    The scan reads only bounded parent/child JSONL identity fields and SDK
    metadata sidecars. It never parses transcript message or tool bodies.
    """

    events = runtime.get("native_task_evidence", [])
    session_id = runtime.get("session_id")
    task_id = runtime.get("actual_task_id")
    if not isinstance(events, list) or not isinstance(session_id, str) or not session_id:
        return None, {"status": "unavailable", "reason": "source-identity-unavailable"}
    if not isinstance(task_id, str) or not task_id:
        return None, {"status": "unavailable", "reason": "source-identity-unavailable"}
    starts = [
        event for event in events
        if isinstance(event, Mapping)
        and event.get("event_subtype") == "task_started"
        and event.get("session_id_digest") == digest(session_id)
        and event.get("task_id_digest") == digest(task_id)
        and _native_task_started_seed_event_valid(event)
    ]
    if len(starts) != 1:
        return None, {"status": "unavailable", "reason": "task-start-identity-unavailable"}
    started = starts[0]
    if started.get("agent_id_seen") is True:
        return None, {"status": "not-needed", "reason": "task-start-agent-observed"}
    mismatch_records = _native_hook_mismatch_records(runtime, started)
    if not mismatch_records:
        return None, {"status": "not-needed", "reason": None}
    agent_digests = {record.get("agent_id_digest") for record in mismatch_records}
    if len(agent_digests) != 1:
        return None, {
            "status": "ambiguous",
            "reason": "multiple-hook-agents",
            "hook_record_count": len(mismatch_records),
        }
    selected = min(
        mismatch_records,
        key=lambda record: int(record.get("observation_sequence", 0)),
    )
    start_tool_digest = started.get("tool_use_id_digest")
    hook_agent_digest = selected.get("agent_id_digest")
    expected_agent_type = runtime.get("native_agent_type", SOURCE_AGENT_NAME)
    if (not isinstance(start_tool_digest, str)
            or not isinstance(hook_agent_digest, str)
            or not isinstance(expected_agent_type, str)
            or not expected_agent_type):
        return None, {"status": "unavailable", "reason": "source-identity-unavailable"}

    session_text = _history_path_component(session_id)
    if session_text is None:
        return None, {"status": "unavailable", "reason": "unsafe-session-component"}
    root = Path(root)
    scan_entries = 0
    scan_files = 0
    scan_bytes = 0
    parent_matches: list[tuple[str, Path, bytes]] = []
    projects_root = root / "projects"
    try:
        projects_stat = os.lstat(projects_root)
    except FileNotFoundError:
        return None, {"status": "missing", "reason": "parent-history-missing"}
    except OSError:
        return None, {"status": "incomplete", "reason": "history-scan-failed"}
    if stat.S_ISLNK(projects_stat.st_mode) or not stat.S_ISDIR(projects_stat.st_mode):
        return None, {"status": "incomplete", "reason": "history-scan-failed"}
    try:
        with os.scandir(projects_root) as entries:
            project_names = []
            for entry in entries:
                scan_entries += 1
                if scan_entries > MAX_HISTORY_SCAN_ENTRIES:
                    raise OverflowError
                project_names.append(entry.name)
    except (OSError, OverflowError):
        return None, {"status": "incomplete", "reason": "history-scan-overflow"}
    for project_name in sorted(project_names):
        project_relative = Path("projects") / project_name
        project_path = root / project_relative
        try:
            project_stat = os.lstat(project_path)
        except OSError:
            return None, {"status": "incomplete", "reason": "history-scan-failed"}
        if stat.S_ISLNK(project_stat.st_mode):
            return None, {"status": "incomplete", "reason": "history-symlink"}
        if not stat.S_ISDIR(project_stat.st_mode):
            continue
        parent_relative = project_relative / (session_text + ".jsonl")
        parent = _capture_history_file(
            root,
            parent_relative,
            attribution="candidate",
            max_bytes=MAX_HISTORY_CONTENT_BYTES,
            require_single_link=True,
        )
        if parent.get("status") == "unknown":
            if parent.get("reason") == "missing":
                continue
            return None, {"status": "incomplete", "reason": "parent-history-unreadable"}
        parent_content = parent.get("content")
        if not isinstance(parent_content, bytes):
            return None, {"status": "incomplete", "reason": "parent-history-unreadable"}
        scan_files += 1
        scan_bytes += len(parent_content)
        if (scan_files > MAX_HISTORY_SCAN_FILES
                or scan_bytes > MAX_HISTORY_SCAN_BYTES):
            return None, {"status": "incomplete", "reason": "history-scan-overflow"}
        if _sdk_parent_history_session_proven(parent_content, session_id):
            parent_matches.append((project_name, parent_relative, parent_content))
        else:
            return None, {"status": "conflict", "reason": "parent-session-conflict"}
    if not parent_matches:
        return None, {"status": "missing", "reason": "parent-history-missing"}
    if len(parent_matches) != 1:
        return None, {
            "status": "ambiguous",
            "reason": "multiple-parent-histories",
            "parent_candidate_count": len(parent_matches),
        }

    project_name, parent_relative, parent_content = parent_matches[0]
    session_root = Path("projects") / project_name / session_text
    subagents_root = root / session_root / "subagents"
    try:
        subagents_stat = os.lstat(subagents_root)
    except FileNotFoundError:
        return None, {
            "status": "missing",
            "reason": "agent-sidecar-missing",
            "parent_history_sha256": hashlib.sha256(parent_content).hexdigest(),
        }
    except OSError:
        return None, {"status": "incomplete", "reason": "sidecar-scan-failed"}
    if stat.S_ISLNK(subagents_stat.st_mode) or not stat.S_ISDIR(subagents_stat.st_mode):
        return None, {"status": "incomplete", "reason": "sidecar-scan-failed"}

    sidecars: list[tuple[str, Path, bytes, dict[str, object]]] = []
    stack: list[tuple[Path, int]] = [(session_root / "subagents", 0)]
    while stack:
        relative_dir, depth = stack.pop()
        directory = root / relative_dir
        try:
            with os.scandir(directory) as entries:
                names = []
                for entry in entries:
                    scan_entries += 1
                    if scan_entries > MAX_HISTORY_SCAN_ENTRIES:
                        raise OverflowError
                    names.append(entry.name)
        except (OSError, OverflowError):
            return None, {"status": "incomplete", "reason": "sidecar-scan-overflow"}
        for name in sorted(names):
            relative = relative_dir / name
            path = root / relative
            try:
                entry_stat = os.lstat(path)
            except OSError:
                return None, {"status": "incomplete", "reason": "sidecar-scan-failed"}
            if stat.S_ISLNK(entry_stat.st_mode):
                return None, {"status": "incomplete", "reason": "sidecar-symlink"}
            if stat.S_ISDIR(entry_stat.st_mode):
                if depth >= MAX_HISTORY_SCAN_DEPTH:
                    return None, {"status": "incomplete", "reason": "sidecar-scan-overflow"}
                stack.append((relative, depth + 1))
                continue
            if not stat.S_ISREG(entry_stat.st_mode):
                return None, {"status": "incomplete", "reason": "sidecar-not-regular"}
            if entry_stat.st_nlink != 1:
                return None, {"status": "incomplete", "reason": "sidecar-hardlink"}
            if not name.endswith(".meta.json"):
                continue
            scan_files += 1
            if scan_files > MAX_HISTORY_SCAN_FILES:
                return None, {"status": "incomplete", "reason": "sidecar-scan-overflow"}
            sidecar = _capture_history_file(
                root,
                relative,
                attribution="candidate",
                max_bytes=MAX_HISTORY_CONTENT_BYTES,
                require_single_link=True,
            )
            content = sidecar.get("content")
            if sidecar.get("status") != "observed" or not isinstance(content, bytes):
                return None, {"status": "incomplete", "reason": "sidecar-unreadable"}
            scan_bytes += len(content)
            if scan_bytes > MAX_HISTORY_SCAN_BYTES:
                return None, {"status": "incomplete", "reason": "sidecar-scan-overflow"}
            metadata = _sdk_sidecar_metadata(content)
            if metadata is None:
                return None, {"status": "incomplete", "reason": "sidecar-metadata-invalid"}
            filename = relative.name
            prefix = "agent-"
            suffix = ".meta.json"
            if not filename.startswith(prefix) or not filename.endswith(suffix):
                return None, {"status": "incomplete", "reason": "sidecar-name-invalid"}
            agent_id = filename[len(prefix):-len(suffix)]
            if _history_path_component(agent_id) is None:
                return None, {"status": "incomplete", "reason": "sidecar-agent-id-invalid"}
            sidecars.append((agent_id, relative, content, metadata))

    diag_base = {
        "scan_entry_count": scan_entries,
        "scan_file_count": scan_files,
        "scan_byte_count": scan_bytes,
        "parent_history_sha256": hashlib.sha256(parent_content).hexdigest(),
    }
    hook_agent_sidecars = [
        candidate for candidate in sidecars
        if digest(candidate[0]) == hook_agent_digest
    ]
    matching_tool_sidecars = [
        candidate for candidate in sidecars
        if isinstance(candidate[3].get("toolUseId"), str)
        and digest(candidate[3].get("toolUseId")) == start_tool_digest
    ]
    if len(hook_agent_sidecars) > 1:
        return None, {
            **diag_base,
            "status": "conflict",
            "reason": "duplicate-sidecars-for-hook-agent",
            "matching_sidecar_count": len(hook_agent_sidecars),
        }
    if len(matching_tool_sidecars) != 1:
        return None, {
            **diag_base,
            "status": "ambiguous" if matching_tool_sidecars else "missing",
            "reason": (
                "multiple-agent-sidecars" if matching_tool_sidecars
                else "agent-sidecar-missing"
            ),
            "matching_sidecar_count": len(matching_tool_sidecars),
        }
    if len(hook_agent_sidecars) != 1:
        return None, {
            **diag_base,
            "status": "conflict",
            "reason": "hook-agent-sidecar-missing",
            "matching_sidecar_count": 1,
        }
    agent_id, sidecar_relative, sidecar_content, metadata = matching_tool_sidecars[0]
    if digest(agent_id) != hook_agent_digest:
        return None, {
            **diag_base,
            "status": "conflict",
            "reason": "sidecar-agent-hook-conflict",
            "matching_sidecar_count": 1,
        }
    if (hook_agent_sidecars[0][1] != sidecar_relative
            or hook_agent_sidecars[0][3].get("toolUseId") is None
            or digest(hook_agent_sidecars[0][3].get("toolUseId"))
            != start_tool_digest):
        return None, {
            **diag_base,
            "status": "conflict",
            "reason": "hook-agent-parent-tool-conflict",
            "matching_sidecar_count": 1,
        }
    if "parentAgentId" in metadata:
        return None, {
            **diag_base,
            "status": "conflict",
            "reason": "nested-parent-agent",
            "matching_sidecar_count": 1,
        }
    child_relative = sidecar_relative.with_name(
        sidecar_relative.name[: -len(".meta.json")] + ".jsonl"
    )
    child = _capture_history_file(
        root,
        child_relative,
        attribution="candidate",
        max_bytes=MAX_HISTORY_CONTENT_BYTES,
        require_single_link=True,
    )
    child_content = child.get("content")
    if child.get("status") != "observed" or not isinstance(child_content, bytes):
        return None, {
            **diag_base,
            "status": "incomplete",
            "reason": "child-transcript-unreadable",
            "matching_sidecar_count": 1,
        }
    scan_bytes += len(child_content)
    if scan_bytes > MAX_HISTORY_SCAN_BYTES:
        return None, {**diag_base, "status": "incomplete", "reason": "sidecar-scan-overflow"}
    if not _sdk_child_history_identity_proven(child_content, session_id, agent_id):
        return None, {
            **diag_base,
            "status": "conflict",
            "reason": "child-session-agent-conflict",
            "matching_sidecar_count": 1,
        }
    child_path_digest = digest(str(root / child_relative))
    stop_records = [
        record for record in mismatch_records
        if record.get("hook_event_name") == "SubagentStop"
    ]
    if any(
        record.get("agent_transcript_path_digest") != child_path_digest
        for record in stop_records
    ):
        return None, {
            **diag_base,
            "status": "conflict",
            "reason": "subagent-stop-path-conflict",
            "matching_sidecar_count": 1,
        }

    proof = {
        "record_schema": NATIVE_TASK_SDK_SIDECAR_PROOF_SCHEMA,
        "session_id_digest": digest(session_id),
        "agent_id_digest": hook_agent_digest,
        "agent_type": expected_agent_type,
        "task_tool_use_id_digest": start_tool_digest,
        "parent_agent_id_seen": False,
        "parent_history_session_proven": True,
        "child_history_session_agent_proven": True,
        "matching_sidecar_count": 1,
        "scan_complete": True,
        "parent_history_path_digest": digest(str(root / parent_relative)),
        "child_transcript_path_digest": child_path_digest,
        "parent_history_sha256": hashlib.sha256(parent_content).hexdigest(),
        "child_transcript_sha256": hashlib.sha256(child_content).hexdigest(),
        "sidecar_sha256": hashlib.sha256(sidecar_content).hexdigest(),
    }
    return proof, {
        **diag_base,
        "status": "observed",
        "reason": None,
        "matching_sidecar_count": 1,
        "child_transcript_sha256": proof["child_transcript_sha256"],
        "sidecar_sha256": proof["sidecar_sha256"],
    }


def _history_sidecar_link(
    content: bytes,
    source_identity: Mapping[str, object],
) -> bool:
    """Read only the SDK sidecar's top-level camel-case linkage fields."""

    try:
        metadata = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, TypeError, ValueError):
        return False
    if not isinstance(metadata, Mapping):
        return False
    tool_use_id = metadata.get("toolUseId")
    parent_agent_id = metadata.get("parentAgentId")
    if not isinstance(tool_use_id, str) and not isinstance(parent_agent_id, str):
        return False
    expected_tool_use_id = source_identity.get("tool_use_id")
    expected_parent_agent_id = source_identity.get("parent_agent_id")
    tool_use_id_expected = isinstance(expected_tool_use_id, str)
    parent_agent_id_expected = isinstance(expected_parent_agent_id, str)
    if not tool_use_id_expected and not parent_agent_id_expected:
        return False
    if tool_use_id_expected and (
        not isinstance(tool_use_id, str) or tool_use_id != expected_tool_use_id
    ):
        return False
    if parent_agent_id_expected and (
        not isinstance(parent_agent_id, str)
        or parent_agent_id != expected_parent_agent_id
    ):
        return False
    return True


def _discover_history_paths(
    root: Path,
    source_identity: Mapping[str, object] | None,
    *,
    max_bytes: int,
) -> dict[str, object]:
    candidates: dict[str, list[tuple[Path, str]]] = {
        "parent": [],
        "child": [],
    }
    if not isinstance(source_identity, Mapping):
        return {"candidates": candidates, "reason": "identity-unavailable"}
    identity = {
        field: source_identity.get(field)
        for field in (
            "session_id",
            "task_id",
            "agent_id",
            "tool_use_id",
            "parent_agent_id",
        )
    }
    session_text = _history_path_component(identity.get("session_id"))
    if session_text is None:
        return {"candidates": candidates, "reason": "identity-unavailable"}
    root = Path(root)
    scanned_files = 0
    scanned_entries = 0
    scanned_bytes = 0
    projects_root = root / "projects"
    try:
        projects_stat = os.lstat(projects_root)
    except FileNotFoundError:
        return {"candidates": candidates, "reason": None}
    except OSError:
        return {"candidates": candidates, "reason": "scan-overflow"}
    if stat.S_ISLNK(projects_stat.st_mode) or not stat.S_ISDIR(projects_stat.st_mode):
        return {"candidates": candidates, "reason": "scan-overflow"}

    project_names: list[str] = []
    try:
        with os.scandir(projects_root) as project_entries:
            for entry in project_entries:
                scanned_entries += 1
                if scanned_entries > MAX_HISTORY_SCAN_ENTRIES:
                    return {"candidates": candidates, "reason": "scan-overflow"}
                project_names.append(entry.name)
    except OSError:
        return {"candidates": candidates, "reason": "scan-overflow"}

    for project_name in sorted(project_names):
        project_path = projects_root / project_name
        try:
            project_stat = os.lstat(project_path)
        except OSError:
            return {"candidates": candidates, "reason": "scan-overflow"}
        if stat.S_ISLNK(project_stat.st_mode) or not stat.S_ISDIR(project_stat.st_mode):
            continue
        project_relative = Path("projects") / project_name
        parent_path = project_relative / (session_text + ".jsonl")
        parent_probe = _capture_history_file(
            root,
            parent_path,
            attribution="candidate",
            max_bytes=max_bytes,
        )
        if parent_probe.get("status") == "observed":
            parent_content = parent_probe.get("content")
            parent_attribution = (
                "observed"
                if isinstance(parent_content, bytes)
                and _history_parent_session_observed(parent_content, session_text)
                else "candidate"
            )
            candidates["parent"].append((parent_path, parent_attribution))
        elif parent_probe.get("reason") != "missing":
            candidates["parent"].append((parent_path, "candidate"))

        child_root = project_path / session_text / "subagents"
        stack: list[tuple[Path, int]] = [(child_root, 0)]
        while stack:
            directory, depth = stack.pop()
            try:
                directory_stat = os.lstat(directory)
            except FileNotFoundError:
                continue
            except OSError:
                return {"candidates": candidates, "reason": "scan-overflow"}
            if stat.S_ISLNK(directory_stat.st_mode):
                return {"candidates": candidates, "reason": "scan-overflow"}
            if not stat.S_ISDIR(directory_stat.st_mode):
                continue
            names: list[str] = []
            try:
                with os.scandir(directory) as directory_entries:
                    for entry in directory_entries:
                        scanned_entries += 1
                        if scanned_entries > MAX_HISTORY_SCAN_ENTRIES:
                            return {"candidates": candidates, "reason": "scan-overflow"}
                        names.append(entry.name)
            except OSError:
                return {"candidates": candidates, "reason": "scan-overflow"}
            for name in sorted(names):
                entry_path = directory / name
                try:
                    entry_stat = os.lstat(entry_path)
                except OSError:
                    return {"candidates": candidates, "reason": "scan-overflow"}
                if stat.S_ISLNK(entry_stat.st_mode):
                    continue
                if stat.S_ISDIR(entry_stat.st_mode):
                    if depth < MAX_HISTORY_SCAN_DEPTH:
                        stack.append((entry_path, depth + 1))
                    continue
                if not stat.S_ISREG(entry_stat.st_mode):
                    continue
                if not name.startswith("agent-") or not name.endswith(".jsonl"):
                    continue
                scanned_files += 1
                if scanned_files > MAX_HISTORY_SCAN_FILES:
                    return {"candidates": candidates, "reason": "scan-overflow"}
                agent_id = name[len("agent-") : -len(".jsonl")]
                if not agent_id:
                    continue
                relative = entry_path.relative_to(root)
                sidecar_relative = relative.with_name(
                    relative.name[: -len(".jsonl")] + ".meta.json"
                )
                sidecar = _capture_history_file(
                    root,
                    sidecar_relative,
                    attribution="candidate",
                    max_bytes=max_bytes,
                )
                sidecar_content = sidecar.get("content")
                scanned_bytes += (
                    len(sidecar_content) if isinstance(sidecar_content, bytes) else 0
                )
                if scanned_bytes > MAX_HISTORY_SCAN_BYTES:
                    return {"candidates": candidates, "reason": "scan-overflow"}
                native_join = agent_id == identity.get("agent_id")
                sidecar_link = (
                    isinstance(sidecar_content, bytes)
                    and _history_sidecar_link(sidecar_content, identity)
                )
                candidates["child"].append(
                    (
                        relative,
                        "observed" if native_join and sidecar_link else "candidate",
                    )
                )
    return {
        "candidates": candidates,
        "reason": None,
    }


def _select_history_candidate(
    candidates: list[tuple[Path, str]],
    *,
    exclude: Path | None = None,
) -> tuple[Path | None, str, str | None]:
    filtered = [(path, attribution) for path, attribution in candidates if path != exclude]
    observed = [(path, attribution) for path, attribution in filtered if attribution == "observed"]
    if len(observed) == 1:
        path, _ = observed[0]
        return path, "observed", None
    if len(observed) > 1:
        return None, "unattributed", "ambiguous"
    if len(filtered) == 1:
        path, attribution = filtered[0]
        return path, attribution, None
    if len(filtered) > 1:
        return None, "unattributed", "ambiguous"
    return None, "unattributed", "missing"


def _revalidate_observed_history_link(
    record: Mapping[str, object],
    root: Path,
    relative_path: Path | None,
    source_identity: Mapping[str, object] | None,
    *,
    child: bool,
    max_bytes: int,
) -> dict[str, object]:
    if (
        record.get("status") != "observed"
        or record.get("attribution") != "observed"
        or not isinstance(source_identity, Mapping)
        or relative_path is None
    ):
        return dict(record)
    if child:
        sidecar_relative = relative_path.with_name(
            relative_path.name[: -len(".jsonl")] + ".meta.json"
        )
        sidecar = _capture_history_file(
            root,
            sidecar_relative,
            attribution="candidate",
            max_bytes=max_bytes,
        )
        content = sidecar.get("content")
        linked = isinstance(content, bytes) and _history_sidecar_link(
            content, source_identity
        )
    else:
        content = record.get("content")
        linked = isinstance(content, bytes) and _history_parent_session_observed(
            content, str(source_identity.get("session_id"))
        )
    if not linked:
        return _history_unknown_record("uncorrelated", "unattributed")
    return dict(record)


def capture_runtime_history_records(
    root: Path,
    *,
    source_identity: Mapping[str, object] | None,
    max_bytes: int = MAX_HISTORY_CONTENT_BYTES,
) -> dict[str, object]:
    """Discover source-linked candidates; never accept caller attribution claims."""

    discovery = _discover_history_paths(
        Path(root), source_identity, max_bytes=max_bytes
    )
    candidates = discovery.get("candidates", {})
    candidates = candidates if isinstance(candidates, Mapping) else {}
    parent_path, parent_attribution, parent_reason = _select_history_candidate(
        candidates.get("parent", [])
        if isinstance(candidates.get("parent"), list)
        else []
    )
    child_path, child_attribution, child_reason = _select_history_candidate(
        candidates.get("child", [])
        if isinstance(candidates.get("child"), list)
        else [],
        exclude=parent_path,
    )
    scan_reason = discovery.get("reason")
    if scan_reason in {"identity-unavailable", "scan-overflow"}:
        parent_record = _history_unknown_record(str(scan_reason), "unattributed")
        child_record = _history_unknown_record(str(scan_reason), "unattributed")
    else:
        parent_record = (
            _capture_history_file(
                Path(root),
                parent_path,
                attribution=parent_attribution,
                max_bytes=max_bytes,
            )
            if parent_path is not None
            else _history_unknown_record(
                "missing-parent" if parent_reason == "missing" else str(parent_reason),
                parent_attribution,
            )
        )
        child_record = (
            _capture_history_file(
                Path(root),
                child_path,
                attribution=child_attribution,
                max_bytes=max_bytes,
            )
            if child_path is not None
            else _history_unknown_record(
                "unattributed-child-history"
                if child_reason == "missing" else str(child_reason),
                child_attribution,
            )
        )
        parent_record = _revalidate_observed_history_link(
            parent_record,
            Path(root),
            parent_path,
            source_identity,
            child=False,
            max_bytes=max_bytes,
        )
        child_record = _revalidate_observed_history_link(
            child_record,
            Path(root),
            child_path,
            source_identity,
            child=True,
            max_bytes=max_bytes,
        )
    return {"parent": parent_record, "child": child_record}


def capture_bounded_history_records(
    root: Path,
    *,
    parent_path: object = None,
    child_path: object = None,
    max_bytes: int = MAX_HISTORY_CONTENT_BYTES,
) -> dict[str, object]:
    """Read explicitly selected paths only for offline safety regressions."""

    parent_record = _capture_history_file(
        Path(root),
        parent_path,
        attribution="observed",
        max_bytes=max_bytes,
    )
    child_record = (
        _capture_history_file(
            Path(root),
            child_path,
            attribution="candidate",
            max_bytes=max_bytes,
        )
        if child_path is not None
        else _history_unknown_record("unattributed-child-history", "candidate")
    )
    return {"parent": parent_record, "child": child_record}


def validate_isolation(record: Mapping[str, object]) -> None:
    """Require network-none, read-only, unprivileged, no-host-mount isolation."""
    config = record.get("HostConfig")
    if not isinstance(config, Mapping):
        raise RuntimeError("container isolation record is malformed")
    if config.get("NetworkMode") != "none":
        raise RuntimeError("probe requires network=none")
    if (record.get("Privileged") or config.get("Privileged")
            or not config.get("ReadonlyRootfs")):
        raise RuntimeError("probe requires unprivileged read-only root")
    if config.get("PidMode"):
        raise RuntimeError("probe refuses a joined PID namespace")
    if config.get("IpcMode") == "host" or config.get("UTSMode") == "host":
        raise RuntimeError("probe refuses a joined host namespace")
    if (config.get("CapAdd") or config.get("Devices")
            or config.get("DeviceRequests")
            or "ALL" not in (config.get("CapDrop") or [])):
        raise RuntimeError("probe requires all capabilities dropped")
    security = [str(value) for value in (config.get("SecurityOpt") or [])]
    if not any(value == "no-new-privileges"
               or value.startswith("no-new-privileges:") for value in security):
        raise RuntimeError("probe requires no-new-privileges")
    for mount in record.get("Mounts") or ():
        if not isinstance(mount, Mapping):
            raise RuntimeError("probe mount record is malformed")
        if mount.get("Type") not in {"tmpfs", None}:
            raise RuntimeError("probe refuses host or persistent mounts")
        if mount.get("Type") == "tmpfs" and mount.get("Source") not in {None, "", "tmpfs"}:
            raise RuntimeError("probe refuses a tmpfs host source")
    if config.get("Binds") or config.get("VolumesFrom"):
        raise RuntimeError("probe refuses host mounts")


_TWO_DOMAIN_ROLES = frozenset({"source", "target", "custodian", "copy", "verify"})
_TWO_DOMAIN_INTENTS = frozenset({
    "source-stop", "source-container-stop", "source-remove", "release",
    "target-launch", "target-stop", "target-container-stop", "target-remove",
    "helper-remove", "source-volume-remove", "target-volume-remove",
    "negative-refusal", "arm-result", "arm-abort", "cleanup-complete",
    "quarantine-stop", "quarantine-summary",
    "mount-witness-before-upload", "mount-witness-before-work",
    "mount-witness-attach-reaped",
})
_TWO_DOMAIN_MAX_PIDS = 96
_TWO_DOMAIN_MAX_MEMORY = 768 * 1024 * 1024
_TWO_DOMAIN_MAX_NANO_CPUS = 1_000_000_000


def two_domain_created_never_started(record: Mapping[str, object]) -> bool:
    """Recognize an inspect record that proves a container never started."""

    state = record.get("State")
    if not isinstance(state, Mapping):
        return False
    status = state.get("Status")
    started_at = state.get("StartedAt")
    finished_at = state.get("FinishedAt")
    return bool(
        (status == "created" or status == "Created")
        and state.get("Running") is False
        and type(state.get("Pid")) is int
        and state.get("Pid") == 0
        and type(started_at) is str
        and started_at == "0001-01-01T00:00:00Z"
        and type(finished_at) is str
        and finished_at == "0001-01-01T00:00:00Z"
    )


def _validate_active_tmpfs_witness(
    record: Mapping[str, object], *, run_id: str, role: str,
    witness: Mapping[str, object], expected_wrapper_sha256: str | None,
) -> None:
    """Validate externally bound, two-stage mountinfo facts for this process."""
    def fail() -> None:
        raise RuntimeError("two-domain active tmpfs witness is invalid")

    state = record.get("State")
    config = record.get("Config")
    labels = config.get("Labels") if isinstance(config, Mapping) else None
    if (witness.get("schema") != "openrepotools-active-tmpfs-witness/v1"
            or witness.get("protocol") != "mountinfo-two-stage-v1"
            or not isinstance(state, Mapping) or not isinstance(labels, Mapping)
            or state.get("Running") is not True
            or type(state.get("Pid")) is not int or state.get("Pid", 0) <= 0
            or not isinstance(state.get("StartedAt"), str)
            or witness.get("container_id") != record.get("Id")
            or witness.get("run_id") != run_id
            or witness.get("role") != role
            or witness.get("image_id") != record.get("Image")
            or witness.get("started_at") != state.get("StartedAt")
            or witness.get("pid") != state.get("Pid")
            or labels.get("openrepotools.bite4.run") != run_id
            or labels.get("openrepotools.bite4.role") != role):
        fail()
    wrapper_sha = witness.get("wrapper_sha256")
    if (not isinstance(wrapper_sha, str)
            or not re.fullmatch(r"[0-9a-f]{64}", wrapper_sha)
            or not isinstance(expected_wrapper_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_wrapper_sha256)
            or wrapper_sha != expected_wrapper_sha256):
        fail()
    command = config.get("Cmd") if isinstance(config, Mapping) else None
    if (config.get("OpenStdin") is not True
            or config.get("AttachStdin") is not True
            or config.get("Tty") is not False
            or config.get("StdinOnce") is not True
            or config.get("Entrypoint") != ["/usr/bin/env"]
            or not isinstance(command, list) or len(command) != 8
            or command[:7] != [
                "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "python3",
                "-I", "-S", "-u", "-c",
            ]
            or not isinstance(command[7], str)
            or hashlib.sha256(command[7].encode("utf-8")).hexdigest() != wrapper_sha):
        fail()
    event_binding = witness.get("event_binding")
    if not isinstance(event_binding, Mapping):
        fail()
    event_digest = event_binding.get("event_binding_digest")
    event_payload = {
        key: value for key, value in event_binding.items()
        if key != "event_binding_digest"
    }
    if (not isinstance(event_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", event_digest)
            or _canonical_digest(event_payload) != event_digest
            or event_binding.get("container_id") != record.get("Id")
            or event_binding.get("run_id") != run_id
            or event_binding.get("role") != role
            or event_binding.get("create_count") != 1
            or event_binding.get("start_count") != 1
            or event_binding.get("die_count") != 0
            or event_binding.get("destroy_count") != 0):
        fail()
    captures = witness.get("captures")
    if not isinstance(captures, list) or len(captures) not in {1, 2}:
        fail()
    expected_stages = ["before-upload"] if len(captures) == 1 else [
        "before-upload", "before-work",
    ]
    nonces: list[str] = []
    namespaces: list[str] = []
    start_tokens: list[str] = []
    normalized_mounts: list[object] = []
    for index, capture in enumerate(captures):
        if not isinstance(capture, Mapping):
            fail()
        capture_digest = capture.get("capture_digest")
        capture_payload = {
            key: value for key, value in capture.items()
            if key != "capture_digest"
        }
        nonce_digest = capture.get("nonce_digest")
        mountinfo_digest = capture.get("mountinfo_sha256")
        inspect_identity_digest = capture.get("inspect_identity_digest")
        capture_event_digest = capture.get("event_binding_digest")
        namespace = capture.get("mount_namespace")
        start_token = capture.get("start_token")
        mounts = capture.get("mounts")
        mounts_digest = capture.get("mounts_digest")
        if (capture.get("stage") != expected_stages[index]
                or not isinstance(capture_digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", capture_digest)
                or _canonical_digest(capture_payload) != capture_digest
                or not isinstance(nonce_digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", nonce_digest)
                or not isinstance(mountinfo_digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", mountinfo_digest)
                or inspect_identity_digest != _canonical_digest({
                    "container_id": witness.get("container_id"),
                    "run_id": witness.get("run_id"),
                    "role": witness.get("role"),
                    "image_id": witness.get("image_id"),
                    "started_at": witness.get("started_at"),
                    "pid": witness.get("pid"),
                })
                or capture_event_digest != event_digest
                or not isinstance(namespace, str)
                or not re.fullmatch(r"mnt:\[[0-9]+\]", namespace)
                or not isinstance(start_token, str)
                or not re.fullmatch(r"[0-9]+", start_token)
                or not isinstance(mounts, list)
                or not isinstance(mounts_digest, str)
                or _canonical_digest(mounts) != mounts_digest):
            fail()
        nonces.append(nonce_digest)
        namespaces.append(namespace)
        start_tokens.append(start_token)
        normalized_mounts.append(mounts)
    if (len(set(nonces)) != len(nonces)
            or len(set(namespaces)) != 1 or len(set(start_tokens)) != 1
            or len({_canonical_digest(value) for value in normalized_mounts}) != 1):
        fail()
    mounts = witness.get("mounts")
    if not isinstance(mounts, list) or _canonical_digest(mounts) != _canonical_digest(normalized_mounts[0]):
        fail()
    if len(mounts) != 2:
        fail()
    by_destination: dict[str, Mapping[str, object]] = {}
    for mount in mounts:
        if not isinstance(mount, Mapping):
            fail()
        destination = mount.get("destination")
        if destination not in {"/tmp", "/opt/loopback"} or destination in by_destination:
            fail()
        by_destination[str(destination)] = mount
    if set(by_destination) != {"/tmp", "/opt/loopback"}:
        fail()
    expected_sizes = {"/tmp": 100663296, "/opt/loopback": 268435456}
    for destination, mount in by_destination.items():
        mount_options = mount.get("mount_options")
        super_options = mount.get("super_options")
        if (mount.get("root") != "/" or mount.get("filesystem") != "tmpfs"
                or mount.get("size_bytes") != expected_sizes[destination]
                or not isinstance(mount.get("mount_id"), int)
                or not isinstance(mount.get("parent_id"), int)
                or not isinstance(mount.get("device"), str)
                or not re.fullmatch(r"[0-9]+:[0-9]+", str(mount.get("device")))
                or not isinstance(mount_options, list)
                or not isinstance(super_options, list)):
            fail()
        mounted = set(mount_options)
        superblock = set(super_options)
        if (not {"rw", "nosuid", "nodev"}.issubset(mounted)
                or "rw" not in superblock
                or {"ro", "suid", "dev"}.intersection(mounted | superblock)):
            fail()
        if destination == "/tmp":
            if "noexec" not in mounted or "exec" in mounted | superblock:
                fail()
        elif "noexec" in mounted | superblock:
            fail()
    attestation_digest = witness.get("attestation_digest")
    payload = {key: value for key, value in witness.items() if key != "attestation_digest"}
    if (not isinstance(attestation_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", attestation_digest)
            or _canonical_digest(payload) != attestation_digest):
        fail()


def validate_two_domain_isolation(
    record: Mapping[str, object],
    *,
    run_id: str,
    role: str,
    expected_mounts: Mapping[str, tuple[str, str | None, bool]],
    active_tmpfs_witness: Mapping[str, object] | None = None,
    expected_wrapper_sha256: str | None = None,
) -> None:
    """Validate the new two-domain envelope without relaxing validate_isolation."""

    if role not in _TWO_DOMAIN_ROLES:
        raise RuntimeError("unknown two-domain container role")
    config = record.get("HostConfig")
    image_config = record.get("Config")
    if not isinstance(config, Mapping) or not isinstance(image_config, Mapping):
        raise RuntimeError("two-domain container record is malformed")
    labels = image_config.get("Labels")
    if not isinstance(labels, Mapping):
        raise RuntimeError("two-domain labels are unavailable")
    if labels.get("openrepotools.bite4.run") != run_id:
        raise RuntimeError("two-domain run label mismatch")
    if labels.get("openrepotools.bite4.role") != role:
        raise RuntimeError("two-domain role label mismatch")
    healthcheck = image_config.get("Healthcheck")
    if healthcheck is not None and not (
        isinstance(healthcheck, Mapping) and healthcheck.get("Test") == ["NONE"]
    ):
        raise RuntimeError("two-domain container refuses inherited healthchecks")
    if config.get("NetworkMode") != "none":
        raise RuntimeError("two-domain container requires network=none")
    if (record.get("Privileged") or config.get("Privileged")
            or not config.get("ReadonlyRootfs")):
        raise RuntimeError("two-domain container requires an unprivileged read-only root")
    pid_mode = config.get("PidMode") or ""
    ipc_mode = config.get("IpcMode") or ""
    uts_mode = config.get("UTSMode") or ""
    if (pid_mode not in {"", "private"}
            or ipc_mode not in {"", "private"}
            or uts_mode not in {"", "private"}):
        raise RuntimeError("two-domain container refuses host namespaces")
    if (config.get("CapAdd") or config.get("Devices")
            or config.get("DeviceRequests")
            or "ALL" not in (config.get("CapDrop") or [])):
        raise RuntimeError("two-domain container requires all capabilities dropped")
    security = [str(value).strip().lower() for value in (config.get("SecurityOpt") or [])]
    nnp_values = [
        value for value in security
        if value == "no-new-privileges"
        or value.startswith("no-new-privileges:")
        or value.startswith("no-new-privileges=")
    ]
    if (not nnp_values
            or any(value not in {"no-new-privileges", "no-new-privileges:true",
                                 "no-new-privileges=1"} for value in nnp_values)):
        raise RuntimeError("two-domain container requires no-new-privileges")
    restart = config.get("RestartPolicy")
    if (not isinstance(restart, Mapping) or restart.get("Name") != "no"
            or restart.get("MaximumRetryCount") not in {0, None}):
        raise RuntimeError("two-domain container requires restart=no")
    pids_limit = config.get("PidsLimit")
    memory_limit = config.get("Memory")
    nano_cpus = config.get("NanoCpus")
    if (type(pids_limit) is not int or not 1 <= pids_limit <= _TWO_DOMAIN_MAX_PIDS
            or type(memory_limit) is not int
            or not 1 <= memory_limit <= _TWO_DOMAIN_MAX_MEMORY
            or type(nano_cpus) is not int
            or not 1 <= nano_cpus <= _TWO_DOMAIN_MAX_NANO_CPUS):
        raise RuntimeError("two-domain container resource limits are missing or exceed caps")
    if config.get("Binds") or config.get("VolumesFrom"):
        raise RuntimeError("two-domain container refuses host binds")
    if not isinstance(expected_mounts, Mapping):
        raise RuntimeError("two-domain expected mount inventory is malformed")
    normalized_expected: dict[str, tuple[str, str | None, bool]] = {}
    for destination, expected in expected_mounts.items():
        if (not isinstance(destination, str) or not isinstance(expected, tuple)
                or len(expected) != 3):
            raise RuntimeError("two-domain expected mount inventory is malformed")
        kind, name, rw = expected
        if (kind not in {"volume", "tmpfs"} or type(rw) is not bool
                or (kind == "volume" and (not isinstance(name, str) or not name))
                or (kind == "tmpfs" and name is not None)):
            raise RuntimeError("two-domain expected mount inventory is malformed")
        normalized_expected[destination] = (kind, name, rw)

    mounts = record.get("Mounts")
    if not isinstance(mounts, list):
        raise RuntimeError("two-domain mount inventory mismatch")
    observed_volumes: dict[str, tuple[str, str | None, bool]] = {}
    observed_tmpfs: dict[str, bool] = {}
    for mount in mounts:
        if not isinstance(mount, Mapping):
            raise RuntimeError("two-domain mount record is malformed")
        kind = mount.get("Type")
        if kind not in {"volume", "tmpfs"}:
            raise RuntimeError("two-domain container refuses non-volume mounts")
        destination = mount.get("Destination")
        rw = mount.get("RW")
        if not isinstance(destination, str) or type(rw) is not bool:
            raise RuntimeError("two-domain mount record is malformed")
        if kind == "volume":
            name = mount.get("Name")
            if not isinstance(name, str) or not name or destination in observed_volumes:
                raise RuntimeError("two-domain volume name is missing or duplicated")
            observed_volumes[destination] = ("volume", name, rw)
        else:
            if mount.get("Source") not in {None, "", "tmpfs"}:
                raise RuntimeError("two-domain tmpfs source is invalid")
            if destination in observed_tmpfs:
                raise RuntimeError("two-domain tmpfs destination is duplicated")
            observed_tmpfs[destination] = rw

    expected_volumes = {
        destination: item for destination, item in normalized_expected.items()
        if item[0] == "volume"
    }
    if observed_volumes != expected_volumes:
        raise RuntimeError("two-domain volume identity or access mismatch")
    expected_tmpfs = {
        destination: item for destination, item in normalized_expected.items()
        if item[0] == "tmpfs"
    }
    # Docker inspect can expose configured tmpfs destinations in
    # HostConfig.Tmpfs before start while omitting them from Mounts. Accept
    # that one exact representation only for a corroborated never-started
    # Created container. Partial or extra active tmpfs mounts remain invalid.
    configured_tmpfs_only = bool(
        expected_tmpfs
        and not observed_tmpfs
        and two_domain_created_never_started(record)
    )
    has_running_witness = bool(
        expected_tmpfs and not observed_tmpfs
        and isinstance(active_tmpfs_witness, Mapping)
        and not two_domain_created_never_started(record)
    )
    if active_tmpfs_witness is not None:
        _validate_active_tmpfs_witness(
            record, run_id=run_id, role=role,
            witness=active_tmpfs_witness,
            expected_wrapper_sha256=expected_wrapper_sha256,
        )
    if (set(observed_tmpfs) != set(expected_tmpfs)
            and not configured_tmpfs_only and not has_running_witness):
        raise RuntimeError("two-domain tmpfs destination mismatch")
    if any(expected_tmpfs[destination][2] != rw
           for destination, rw in observed_tmpfs.items()):
        raise RuntimeError("two-domain tmpfs access mismatch")
    tmpfs_config = config.get("Tmpfs")
    if tmpfs_config is None:
        tmpfs_config = {}
    if not isinstance(tmpfs_config, Mapping) or set(tmpfs_config) != set(expected_tmpfs):
        raise RuntimeError("two-domain tmpfs destination mismatch")
    for destination, (_, _, writable) in expected_tmpfs.items():
        options = tmpfs_config[destination]
        if not isinstance(options, str):
            raise RuntimeError("two-domain tmpfs options are unavailable")
        tokens = options.split(",")
        token_set = set(tokens)
        sizes = [token.split("=", 1)[1] for token in tokens
                 if token.startswith("size=") and "=" in token]
        allowed = {"rw", "nosuid", "nodev", "noexec", "exec"}
        executable_tmpfs = destination == "/opt/loopback"
        required_exec_flag = "exec" if executable_tmpfs else "noexec"
        forbidden_exec_flag = "noexec" if executable_tmpfs else "exec"
        if (len(token_set) != len(tokens)
                or not {"nosuid", "nodev", required_exec_flag}.issubset(token_set)
                or (writable and "rw" not in token_set)
                or {"ro", "suid", "dev", forbidden_exec_flag}.intersection(token_set)
                or len(sizes) != 1 or not sizes[0].isdecimal()
                or not 0 < int(sizes[0]) <= 256 * 1024 * 1024
                or token_set - allowed - {"size=" + sizes[0]}):
            raise RuntimeError("two-domain tmpfs options exceed the safe profile")


def _open_directory_nofollow(path: str | os.PathLike[str]) -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if (nofollow is None or directory is None
            or os.open not in os.supports_dir_fd
            or os.stat not in os.supports_dir_fd
            or os.scandir not in os.supports_fd):
        raise RuntimeError("no-follow directory access is unavailable")
    text_path = os.fsdecode(os.fspath(path))
    if "\x00" in text_path:
        raise RuntimeError("no-follow directory path contains NUL")
    absolute = os.path.abspath(text_path)
    current_fd = os.open(os.sep, os.O_RDONLY | directory | nofollow)
    try:
        for component in absolute.split(os.sep):
            if not component:
                continue
            next_fd = os.open(
                component,
                os.O_RDONLY | directory | nofollow,
                dir_fd=current_fd,
            )
            try:
                if not stat.S_ISDIR(os.fstat(next_fd).st_mode):
                    raise RuntimeError("no-follow path component is not a directory")
            except BaseException:
                os.close(next_fd)
                raise
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _tree_stat_signature(info: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
    return (
        info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
        info.st_size, info.st_mtime_ns, info.st_ctime_ns,
    )


def _revalidate_tree_root(
    root: str | os.PathLike[str], root_fd: int, expected: os.stat_result
) -> None:
    if _tree_stat_signature(os.fstat(root_fd)) != _tree_stat_signature(expected):
        raise RuntimeError("two-domain tree root changed during scan")
    check_fd = _open_directory_nofollow(root)
    try:
        if _tree_stat_signature(os.fstat(check_fd)) != _tree_stat_signature(expected):
            raise RuntimeError("two-domain tree root pathname changed during scan")
    finally:
        os.close(check_fd)


def _tree_file_bytes(
    root: str | os.PathLike[str],
    *,
    max_files: int = MAX_HISTORY_SCAN_FILES,
    max_entries: int = MAX_HISTORY_SCAN_ENTRIES,
    max_depth: int = MAX_HISTORY_SCAN_DEPTH,
    max_file_bytes: int = MAX_TWO_DOMAIN_TREE_FILE_BYTES,
    max_total_bytes: int = MAX_TWO_DOMAIN_TREE_BYTES,
) -> list[tuple[str, str, bytes | None]]:
    """Read a bounded fixture tree without following links or unstable paths.

    These fixture-copy budgets are intentionally separate from the smaller
    history-prefix capture and history-discovery budgets above.
    """

    if min(max_files, max_entries, max_depth, max_file_bytes, max_total_bytes) <= 0:
        raise ValueError("two-domain tree limits must be positive")
    root_fd = _open_directory_nofollow(root)
    root_initial = os.fstat(root_fd)
    if not stat.S_ISDIR(root_initial.st_mode):
        os.close(root_fd)
        raise RuntimeError("two-domain tree root is not a directory")
    entries: list[tuple[str, str, bytes | None]] = []
    entries_seen = 0
    files_seen = 0
    bytes_seen = 0
    nofollow = os.O_NOFOLLOW
    directory = os.O_DIRECTORY
    nonblock = getattr(os, "O_NONBLOCK", 0)

    def list_names_bounded(directory_fd: int) -> list[str]:
        names: list[str] = []
        with os.scandir(directory_fd) as iterator:
            for item in iterator:
                names.append(item.name)
                if len(names) > max_entries:
                    raise RuntimeError("two-domain tree entry limit exceeded")
        names.sort()
        return names

    def check_child_path(
        parent_fd: int, name: str, before: os.stat_result, message: str
    ) -> None:
        after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if _tree_stat_signature(after) != _tree_stat_signature(before):
            raise RuntimeError(message)

    def visit(directory_fd: int, prefix: str, depth: int) -> None:
        nonlocal entries_seen, files_seen, bytes_seen
        if depth > max_depth:
            raise RuntimeError("two-domain tree depth exceeded")
        directory_initial = os.fstat(directory_fd)
        if not stat.S_ISDIR(directory_initial.st_mode):
            raise RuntimeError("two-domain tree directory changed type")
        names = list_names_bounded(directory_fd)
        for name in names:
            if name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
                raise RuntimeError("two-domain tree contains an unsafe name")
            entries_seen += 1
            if entries_seen > max_entries:
                raise RuntimeError("two-domain tree entry limit exceeded")
            relative = name if not prefix else prefix + "/" + name
            if len(relative.encode("utf-8", "surrogatepass")) > 4096:
                raise RuntimeError("two-domain tree path limit exceeded")
            before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISLNK(before.st_mode):
                raise RuntimeError("two-domain tree refuses symlinks")
            if stat.S_ISDIR(before.st_mode):
                entries.append(("directory", relative, None))
                child_fd = os.open(
                    name,
                    os.O_RDONLY | directory | nofollow,
                    dir_fd=directory_fd,
                )
                try:
                    opened = os.fstat(child_fd)
                    if _tree_stat_signature(opened) != _tree_stat_signature(before):
                        raise RuntimeError("two-domain directory changed during scan")
                    visit(child_fd, relative, depth + 1)
                    if _tree_stat_signature(os.fstat(child_fd)) != _tree_stat_signature(before):
                        raise RuntimeError("two-domain directory changed during scan")
                    check_child_path(
                        directory_fd, name, before,
                        "two-domain directory pathname changed during scan",
                    )
                finally:
                    os.close(child_fd)
                continue
            if not stat.S_ISREG(before.st_mode):
                raise RuntimeError("two-domain tree refuses non-regular files")
            if before.st_nlink != 1:
                raise RuntimeError("two-domain tree refuses hard-linked files")
            if before.st_size < 0 or before.st_size > max_file_bytes:
                raise RuntimeError("two-domain file size limit exceeded")
            files_seen += 1
            if files_seen > max_files:
                raise RuntimeError("two-domain file count exceeded")
            fd = os.open(
                name,
                os.O_RDONLY | nofollow | nonblock,
                dir_fd=directory_fd,
            )
            try:
                opened = os.fstat(fd)
                if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                    raise RuntimeError("two-domain file changed type or link count")
                if _tree_stat_signature(opened) != _tree_stat_signature(before):
                    raise RuntimeError("two-domain file changed before read")
                chunks: list[bytes] = []
                file_bytes = 0
                while True:
                    chunk = os.read(fd, min(65536, max_file_bytes + 1 - file_bytes))
                    if not chunk:
                        break
                    file_bytes += len(chunk)
                    bytes_seen += len(chunk)
                    if file_bytes > max_file_bytes or bytes_seen > max_total_bytes:
                        raise RuntimeError("two-domain tree byte limit exceeded")
                    chunks.append(chunk)
                after = os.fstat(fd)
                if (_tree_stat_signature(after) != _tree_stat_signature(opened)
                        or file_bytes != opened.st_size):
                    raise RuntimeError("two-domain file changed during read")
                check_child_path(
                    directory_fd, name, opened,
                    "two-domain file pathname changed during read",
                )
                entries.append(("file", relative, b"".join(chunks)))
            finally:
                os.close(fd)

        if _tree_stat_signature(os.fstat(directory_fd)) != _tree_stat_signature(directory_initial):
            raise RuntimeError("two-domain directory changed during scan")

    try:
        visit(root_fd, "", 0)
        _revalidate_tree_root(root, root_fd, root_initial)
    finally:
        os.close(root_fd)
    return entries


def manifest_two_domain_tree(
    root: str | os.PathLike[str],
    **limits: int,
) -> dict[str, object]:
    """Return an internal, bounded inventory; callers sanitize paths for reports."""

    entries = _tree_file_bytes(root, **limits)
    rows: list[dict[str, object]] = []
    for kind, name, content in entries:
        if kind == "directory":
            rows.append({"kind": kind, "path": name})
        else:
            assert content is not None
            rows.append({
                "kind": kind,
                "path": name,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })
    files = [row for row in rows if row["kind"] == "file"]
    directories = [row for row in rows if row["kind"] == "directory"]
    return {
        "schema": "openrepotools-two-domain-tree/v1",
        "file_count": len(files),
        "directory_count": len(directories),
        "entry_count": len(rows),
        "total_bytes": sum(int(row["size"]) for row in files),
        "entries": rows,
    }


def copy_two_domain_tree(
    source: str | os.PathLike[str],
    target: str | os.PathLike[str],
    **limits: int,
) -> dict[str, object]:
    """Copy a bounded tree into an empty destination and verify exact entries."""

    source_entries = _tree_file_bytes(source, **limits)
    target_path = Path(target)
    target_parent_fd = _open_directory_nofollow(target_path.parent)
    target_name = target_path.name
    if not target_name or target_name in {".", ".."} or "/" in target_name:
        os.close(target_parent_fd)
        raise RuntimeError("two-domain target path has an unsafe final component")
    try:
        try:
            os.mkdir(target_name, mode=0o700, dir_fd=target_parent_fd)
            os.fsync(target_parent_fd)
        except FileExistsError:
            pass
        target_fd = os.open(
            target_name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=target_parent_fd,
        )
    finally:
        os.close(target_parent_fd)
    target_initial = os.fstat(target_fd)
    if not stat.S_ISDIR(target_initial.st_mode):
        os.close(target_fd)
        raise RuntimeError("two-domain target is not a directory")
    with os.scandir(target_fd) as iterator:
        try:
            next(iterator)
        except StopIteration:
            pass
        else:
            os.close(target_fd)
            raise RuntimeError("two-domain target tree must be empty before copy")
    path_check_fd = _open_directory_nofollow(target_path)
    try:
        if _tree_stat_signature(os.fstat(path_check_fd)) != _tree_stat_signature(target_initial):
            os.close(target_fd)
            raise RuntimeError("two-domain target pathname changed before copy")
    finally:
        os.close(path_check_fd)
    root_fd = target_fd
    target_fd = -1
    nofollow = os.O_NOFOLLOW
    directory = os.O_DIRECTORY
    try:
        def open_relative_directory(parts: list[str]) -> int:
            directory_fd = os.dup(root_fd)
            for component in parts:
                try:
                    child_fd = os.open(
                        component,
                        os.O_RDONLY | directory | nofollow,
                        dir_fd=directory_fd,
                    )
                except BaseException:
                    os.close(directory_fd)
                    raise
                os.close(directory_fd)
                directory_fd = child_fd
            return directory_fd

        directory_entries = sorted(
            (path for kind, path, _ in source_entries if kind == "directory"),
            key=lambda path: (path.count("/"), path),
        )
        for relative in directory_entries:
            parts = relative.split("/")
            parent_fd = open_relative_directory(parts[:-1])
            try:
                os.mkdir(parts[-1], mode=0o700, dir_fd=parent_fd)
            finally:
                os.close(parent_fd)
        for kind, relative, content in source_entries:
            if kind != "file":
                continue
            assert content is not None
            parts = relative.split("/")
            parent_fd = open_relative_directory(parts[:-1])
            try:
                fd = os.open(
                    parts[-1],
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
                    0o600,
                    dir_fd=parent_fd,
                )
                try:
                    view = memoryview(content)
                    while view:
                        written = os.write(fd, view)
                        if written <= 0:
                            raise RuntimeError("two-domain copy made no progress")
                        view = view[written:]
                    os.fsync(fd)
                finally:
                    os.close(fd)
            finally:
                os.close(parent_fd)
        # Persist every new child-directory entry, deepest first, followed by
        # the root mountpoint that owns the top-level entries.
        for relative in sorted(
            directory_entries, key=lambda path: (-path.count("/"), path),
        ):
            directory_fd = open_relative_directory(relative.split("/"))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        os.fsync(root_fd)
        _revalidate_tree_root(target_path, root_fd, os.fstat(root_fd))
    finally:
        if target_fd >= 0:
            os.close(target_fd)
        os.close(root_fd)
    source_manifest = manifest_two_domain_tree(source, **limits)
    target_manifest = manifest_two_domain_tree(target, **limits)
    original_manifest = {
        "schema": "openrepotools-two-domain-tree/v1",
        "file_count": sum(kind == "file" for kind, _, _ in source_entries),
        "directory_count": sum(kind == "directory" for kind, _, _ in source_entries),
        "entry_count": len(source_entries),
        "total_bytes": sum(len(content) for kind, _, content in source_entries
                            if kind == "file" and content is not None),
        "entries": [
            ({"kind": kind, "path": path} if kind == "directory" else {
                "kind": kind,
                "path": path,
                "size": len(content or b""),
                "sha256": hashlib.sha256(content or b"").hexdigest(),
            })
            for kind, path, content in source_entries
        ],
    }
    if source_manifest != original_manifest or source_manifest != target_manifest:
        raise RuntimeError("two-domain copied tree does not match source")
    return {
        "schema": "openrepotools-two-domain-copy/v1",
        "source_digest": hashlib.sha256(_canonical_json(source_manifest)).hexdigest(),
        "target_digest": hashlib.sha256(_canonical_json(target_manifest)).hexdigest(),
        "file_count": source_manifest["file_count"],
        "total_bytes": source_manifest["total_bytes"],
        "exact_match": True,
    }


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


class TwoDomainIntentLedger:
    """Private append-once phase records, fsynced before external effects."""

    def __init__(self, directory: str | os.PathLike[str]) -> None:
        if os.open not in os.supports_dir_fd or os.mkdir not in os.supports_dir_fd:
            raise RuntimeError("two-domain durable directory access is unavailable")
        self.directory = Path(os.path.abspath(os.fsdecode(os.fspath(directory))))
        root_fd = os.open(os.sep, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        current_fd = root_fd
        components = [part for part in self.directory.parts if part not in {os.sep, ""}]
        try:
            for index, component in enumerate(components):
                created = False
                try:
                    next_fd = os.open(
                        component,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=current_fd,
                    )
                except FileNotFoundError:
                    os.mkdir(component, mode=0o700, dir_fd=current_fd)
                    created = True
                    # Persist a newly-created child name in its parent before
                    # exposing a ledger that may authorize an external effect.
                    os.fsync(current_fd)
                    next_fd = os.open(
                        component,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=current_fd,
                    )
                if created:
                    child = os.fstat(next_fd)
                    if child.st_uid != os.geteuid():
                        os.close(next_fd)
                        raise RuntimeError("two-domain intent directory owner mismatch")
                    os.fsync(next_fd)
                if current_fd != root_fd:
                    os.close(current_fd)
                current_fd = next_fd
                if index == len(components) - 1:
                    info = os.fstat(current_fd)
                    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                            or info.st_mode & 0o077 or info.st_mode & 0o300 != 0o300):
                        raise RuntimeError("two-domain intent directory is not private")
            if not components:
                raise RuntimeError("two-domain intent directory cannot be filesystem root")
        finally:
            if current_fd != root_fd:
                os.close(current_fd)
            os.close(root_fd)
        final_fd = _open_directory_nofollow(self.directory)
        try:
            info = os.fstat(final_fd)
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_mode & 0o077 or info.st_mode & 0o300 != 0o300):
                raise RuntimeError("two-domain intent directory is not private")
        finally:
            os.close(final_fd)

    def persist(self, name: str, payload: Mapping[str, object]) -> str:
        if name not in _TWO_DOMAIN_INTENTS:
            raise ValueError("unknown two-domain intent name")
        record: dict[str, object] = {
            "schema": "openrepotools-two-domain-intent/v1",
            "name": name,
            "payload": dict(payload),
        }
        record["sha256"] = hashlib.sha256(_canonical_json(record)).hexdigest()
        if os.link not in os.supports_dir_fd or os.unlink not in os.supports_dir_fd:
            raise RuntimeError("two-domain atomic intent installation is unavailable")
        final_name = name + ".json"
        temp_name = "." + name + "." + uuid.uuid4().hex + ".tmp"
        directory_fd = _open_directory_nofollow(self.directory)
        fd = -1
        installed = False
        try:
            fd = os.open(
                temp_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
            os.fchmod(fd, 0o600)
            data = _canonical_json(record)
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise RuntimeError("two-domain intent write made no progress")
                view = view[written:]
            os.fsync(fd)
            os.close(fd)
            fd = -1
            try:
                os.link(
                    temp_name, final_name,
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                raise RuntimeError("two-domain intent already exists; do not replay") from exc
            installed = True
            os.unlink(temp_name, dir_fd=directory_fd)
            os.fsync(directory_fd)
        except BaseException:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(temp_name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            raise
        try:
            current = os.stat(final_name, dir_fd=directory_fd, follow_symlinks=False)
            if (not stat.S_ISREG(current.st_mode) or current.st_nlink != 1
                    or current.st_mode & 0o077):
                raise RuntimeError("two-domain installed intent is not a private regular file")
        finally:
            os.close(directory_fd)
        if not installed:
            raise RuntimeError("two-domain intent installation did not complete")
        return str(record["sha256"])


def run(*command: str, timeout: int = 45, **kwargs: Any) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, capture_output=True, timeout=timeout, **kwargs)


def sse_payload(
    kind: str,
    response_id: str,
    tool_name: str | None = None,
    response_challenge: str | None = None,
) -> bytes:
    """Build only the minimal streaming response needed by the real CLI."""

    if kind == "agent-tool":
        name, tool_id, tool_input = tool_name or "Agent", SOURCE_AGENT_TOOL_ID, {
            "description": "Gate zero bounded worker",
            "prompt": "Run the bounded local tool and remain unfinished until stopped.",
            "subagent_type": SOURCE_AGENT_NAME,
            "run_in_background": True,
        }
        stop_reason = "tool_use"
        delta = {
            "type": "input_json_delta",
            "partial_json": json.dumps(tool_input, separators=(",", ":")),
        }
        start = {"type": "tool_use", "id": tool_id, "name": name, "input": {}}
    elif kind == "bash-tool":
        name, tool_id, tool_input = "Bash", SOURCE_TOOL_ID, {
            "command": "sleep 30",
            "timeout": 35000,
        }
        stop_reason = "tool_use"
        delta = {
            "type": "input_json_delta",
            "partial_json": json.dumps(tool_input, separators=(",", ":")),
        }
        start = {"type": "tool_use", "id": tool_id, "name": name, "input": {}}
    elif kind == "diagnostic-query-challenge":
        if not isinstance(response_challenge, str) or not response_challenge:
            raise ValueError("diagnostic query response challenge is unavailable")
        stop_reason = "end_turn"
        delta = {"type": "text_delta", "text": response_challenge}
        start = {"type": "text", "text": ""}
    else:
        stop_reason = "end_turn"
        delta = {"type": "text_delta", "text": "bounded source drain"}
        start = {"type": "text", "text": ""}
    message = {
        "id": response_id,
        "type": "message",
        "role": "assistant",
        "model": EXPECTED_MODEL,
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    rows = [
        ("message_start", {"type": "message_start", "message": message}),
        ("content_block_start", {
            "type": "content_block_start",
            "index": 0,
            "content_block": start,
        }),
        ("content_block_delta", {
            "type": "content_block_delta",
            "index": 0,
            "delta": delta,
        }),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": 1},
        }),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(
        "event: %s\ndata: %s\n\n" % (
            event, json.dumps(body, separators=(",", ":")))
        for event, body in rows
    ).encode("utf-8")


class LoopbackHandler(BaseHTTPRequestHandler):
    """Local API gateway; its instance reads the real observer's state."""

    server_version = "loopback-probe/1"
    sys_version = ""

    def log_message(self, *args: object) -> None:
        return

    @property
    def gateway(self) -> GatewayState:
        return self.server.gateway  # type: ignore[attr-defined]

    def write_json(self, status: int, value: Mapping[str, object]) -> None:
        data = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        self._complete_request_arrival()

    def write_sse(self, value: bytes, *, response_challenge: str | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(value)))
        self.end_headers()
        try:
            written = self.wfile.write(value)
            if written != len(value):
                raise OSError("short loopback response write")
        except OSError:
            if response_challenge is not None:
                self.gateway.mark_history_query_response_write(
                    arrival_index=getattr(self, "_active_message_arrival_index", None),
                    response_message_id=getattr(self, "_active_response_message_id", None),
                    succeeded=False,
                )
            raise
        else:
            if response_challenge is not None:
                self.gateway.mark_history_query_response_write(
                    arrival_index=getattr(self, "_active_message_arrival_index", None),
                    response_message_id=getattr(self, "_active_response_message_id", None),
                    succeeded=True,
                )
        self._complete_request_arrival()

    def _complete_request_arrival(self) -> None:
        request_arrival_index = getattr(self, "_active_request_arrival_index", None)
        if type(request_arrival_index) is int:
            self.gateway.complete_request_arrival(request_arrival_index)

    def do_GET(self) -> None:
        endpoint = route(self.path)
        self._active_request_arrival_index = (
            self.gateway.observe_other_request_arrival(endpoint)
        )
        if self.gateway.phase in {
            "target-held", "target-diagnostic-query", "target-query-closed",
        }:
            self.gateway.record(endpoint, method="GET", response_kind="held-error")
            self.gateway.protocol_errors.append("unexpected-held-route")
            self.write_json(409, {
                "type": "error",
                "error": {"type": "invalid_request_error"},
            })
            return
        if endpoint == "/api/hello":
            self.gateway.record(endpoint, method="GET", response_kind="hello")
            self.write_json(200, {"ok": True})
            return
        self.gateway.record(endpoint, method="GET", response_kind="unknown-route")
        self.gateway.protocol_errors.append("unexpected-route")
        self.write_json(404, {
            "type": "error",
            "error": {"type": "not_found"},
        })

    def do_POST(self) -> None:
        endpoint = route(self.path)
        agent_header = self.headers.get("x-claude-code-agent-id")
        agent_header_present = agent_header is not None
        self._active_request_arrival_index = None
        arrival_index: int | None = None
        self._active_response_message_id = None
        if endpoint == "/v1/messages":
            arrival_index = self.gateway.observe_messages_arrival(
                agent_header_present=agent_header_present,
            )
            self._active_message_arrival_index = arrival_index
            self._active_request_arrival_index = (
                self.gateway.request_arrival_index_for_message(arrival_index)
            )
        else:
            self._active_request_arrival_index = (
                self.gateway.observe_other_request_arrival(endpoint)
            )
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = MAX_HTTP_BODY + 1
        if length < 0 or length > MAX_HTTP_BODY:
            if endpoint == "/v1/messages":
                self.gateway.record(
                    endpoint,
                    method="POST",
                    arrival_index=arrival_index,
                    response_kind="request-too-large",
                )
            self.gateway.protocol_errors.append("request-too-large")
            self.write_json(413, {
                "type": "error",
                "error": {"type": "invalid_request_error"},
            })
            return
        body = self.rfile.read(length)
        # Parse only the expected model. Body bytes are never retained.
        try:
            request = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_json_object_without_duplicate_keys,
            ) if body else {}
        except (UnicodeDecodeError, ValueError):
            request = {}
        model_ok = isinstance(request, dict) and request.get("model") == EXPECTED_MODEL
        api_key = self.headers.get("x-api-key")
        authorization = self.headers.get("authorization")
        auth_values = [value for value in (api_key, authorization) if value is not None]
        authorization_ok = bool(
            auth_values
            and all(value in {DUMMY_API_KEY, "Bearer " + DUMMY_API_KEY}
                    for value in auth_values)
            and (api_key == DUMMY_API_KEY
                 or authorization == "Bearer " + DUMMY_API_KEY)
        )
        child = bool(agent_header)
        if endpoint == "/v1/messages/count_tokens":
            self.gateway.record(
                endpoint,
                method="POST",
                child=child,
                agent_header=agent_header,
                agent_header_present=agent_header_present,
                model_ok=model_ok,
                authorization_ok=authorization_ok,
                response_kind="count-tokens",
            )
            if self.gateway.phase in {
                "target-held", "target-diagnostic-query", "target-query-closed",
            }:
                self.gateway.protocol_errors.append("unexpected-held-route")
                self.write_json(409, {
                    "type": "error",
                    "error": {"type": "invalid_request_error"},
                })
                return
            self.write_json(200, {"input_tokens": 1})
            return
        if endpoint != "/v1/messages":
            self.gateway.record(
                endpoint,
                method="POST",
                arrival_index=arrival_index,
                model_ok=model_ok,
                authorization_ok=authorization_ok,
                response_kind="unknown-route",
            )
            self.gateway.protocol_errors.append("unexpected-route")
            self.write_json(404, {
                "type": "error",
                "error": {"type": "not_found"},
            })
            return
        diagnostic_query_body_valid = False
        if self.gateway.phase == "target-diagnostic-query":
            query_witness = self.gateway.inspect_diagnostic_history_query(
                request,
                arrival_index=arrival_index,
                child=child,
                agent_header_present=agent_header_present,
                model_ok=model_ok,
                authorization_ok=authorization_ok,
            )
            diagnostic_query_body_valid = query_witness.get("valid") is True
            context = {
                "marker_present": query_witness.get(
                    "source_prompt_marker_present"
                ) is True,
                "advertised_tool": "Agent" if query_witness.get(
                    "same_request_source_agent_history"
                ) is True else None,
            }
        elif self.gateway.phase in {"target-release", "target-query-closed"}:
            if not child:
                self.gateway.inspect_target_release_body(request)
            context = {"marker_present": False, "advertised_tool": None}
        else:
            context = self.gateway.inspect_parent_body(request, child=child)
        plan = self.gateway.response(
            child=child,
            agent_header=agent_header,
            model_ok=model_ok,
            authorization_ok=authorization_ok,
            prompt_marker=bool(context["marker_present"]),
            advertised_tool=(
                str(context["advertised_tool"])
                if context["advertised_tool"] else None
            ),
            arrival_index=arrival_index,
            agent_header_present=agent_header_present,
            diagnostic_query_body_valid=diagnostic_query_body_valid,
        )
        kind = str(plan["kind"])
        status = int(plan["status"])
        if kind == "protocol-error":
            self.write_json(status, {
                "type": "error",
                "error": {"type": "invalid_request_error"},
            })
        elif kind == "held-error":
            self.write_json(status, {
                "type": "error",
                "error": {"type": "invalid_request_error"},
            })
        elif kind == "credential-error":
            self.write_json(status, {
                "type": "error",
                "error": {"type": "authentication_error"},
            })
        else:
            barrier_status = self.gateway.hold_busy_parent_response(
                request,
                child=child,
                response_kind=kind,
                arrival_index=arrival_index,
            )
            if barrier_status == "expired":
                self.write_json(504, {
                    "type": "error",
                    "error": {"type": "busy_parent_barrier_timeout"},
                })
                self.gateway.mark_busy_parent_handler_returned(
                    arrival_index=arrival_index,
                    barrier_status=barrier_status,
                )
                return
            self.gateway.mark_busy_parent_response_write_started(
                arrival_index=arrival_index,
                barrier_status=barrier_status,
            )
            response_message_id = "msg-loopback-%d" % self.gateway.request_count
            self._active_response_message_id = response_message_id
            try:
                self.write_sse(
                    sse_payload(
                        kind,
                        response_message_id,
                        tool_name=(
                            str(plan["tool_name"])
                            if plan.get("tool_name") else None
                        ),
                        response_challenge=(
                            str(plan["response_challenge"])
                            if isinstance(plan.get("response_challenge"), str)
                            else None
                        ),
                    ),
                    response_challenge=(
                        str(plan["response_challenge"])
                        if isinstance(plan.get("response_challenge"), str)
                        else None
                    ),
                )
            except OSError:
                self.gateway.mark_busy_parent_response_write_failed(
                    arrival_index=arrival_index,
                    barrier_status=barrier_status,
                )
                raise
            else:
                self.gateway.mark_busy_parent_response_completed(
                    arrival_index=arrival_index,
                    barrier_status=barrier_status,
                )
            finally:
                self.gateway.mark_busy_parent_handler_returned(
                    arrival_index=arrival_index,
                    barrier_status=barrier_status,
                )


def find_value(value: object, keys: tuple[str, ...], depth: int = 0) -> object | None:
    if depth > 6 or not isinstance(value, Mapping):
        return None
    for key in keys:
        found = value.get(key)
        if found:
            return found
    for child in value.values():
        found = find_value(child, keys, depth + 1)
        if found:
            return found
    return None


def frame_has_tool_result(value: object, tool_id: str, depth: int = 0) -> bool:
    """Accept a native tool result only when its actual tool ID is present."""

    if depth > 8:
        return False
    if isinstance(value, (list, tuple)):
        return any(frame_has_tool_result(child, tool_id, depth + 1)
                   for child in value)
    if not isinstance(value, Mapping):
        return False
    if value.get("tool_use_id") == tool_id and (
        value.get("type") in {"tool_result", "tool_use_result", "tool_error"}
        or value.get("subtype") in {"tool_result", "tool_use_result", "tool_error"}
    ):
        return True
    return any(frame_has_tool_result(child, tool_id, depth + 1)
               for child in value.values())


def observe_control_event(subtype: object, runtime: dict[str, object]) -> None:
    """Retain only that an unclassified subtype was seen.

    The selected CLI's public stream-json emitter for orphan/clear lifecycle
    events is not established.  A bare subtype is therefore diagnostic only;
    it cannot be joined to a task/session/control phase or promoted into one
    of the Gate 0 facts.
    """

    if not isinstance(subtype, str) or not subtype:
        return
    runtime["unclassified_control_subtype_count"] = int(
        runtime.get("unclassified_control_subtype_count", 0)
    ) + 1


def _append_native_hook_reason(runtime: dict[str, object], reason: str) -> None:
    reasons = runtime.setdefault("native_hook_unknown_reasons", [])
    if not isinstance(reasons, list):
        reasons = []
        runtime["native_hook_unknown_reasons"] = reasons
    if reason in reasons:
        return
    if len(reasons) >= MAX_NATIVE_HOOK_REASONS:
        runtime["native_hook_reason_overflow"] = True
        if "native-hook-reason-overflow" not in reasons:
            reasons[-1] = "native-hook-reason-overflow"
        return
    reasons.append(reason)


def _count_native_hook_id_rejection(runtime: dict[str, object], kind: str) -> None:
    key = "native_hook_tool_use_id_%s_count" % kind
    current = runtime.get(key, 0)
    if type(current) is not int or current < 0:
        current = 0
    runtime[key] = min(MAX_NATIVE_HOOK_REQUESTS, current + 1)


def _append_native_hook_mismatch_diagnostic(
    runtime: dict[str, object],
    *,
    event_name: str,
    reason: str,
    callback_tool_use_id: str | None,
    input_tool_use_id: str | None,
    hook_session_id: str | None,
    hook_agent_id: str | None,
    agent_type: str | None,
) -> bool:
    diagnostics = runtime.setdefault("native_hook_mismatch_diagnostics", [])
    if not isinstance(diagnostics, list):
        diagnostics = []
        runtime["native_hook_mismatch_diagnostics"] = diagnostics
        runtime["native_hook_mismatch_diagnostic_overflow"] = True
    if len(diagnostics) >= MAX_NATIVE_HOOK_EVIDENCE:
        runtime["native_hook_mismatch_diagnostic_overflow"] = True
        _append_native_hook_reason(runtime, "native-hook-mismatch-diagnostic-overflow")
        return False
    sequence = int(runtime.get("native_hook_observation_sequence", 0)) + 1
    session_id = _native_hook_text(runtime.get("session_id"))
    task_id = _native_hook_text(runtime.get("actual_task_id"))
    task_tool_use_id = _native_hook_text(runtime.get("task_tool_use_id"))
    configured_agent_type = _native_hook_text(runtime.get("native_agent_type"))
    safe_agent_type = (
        agent_type if isinstance(agent_type, str)
        and agent_type == configured_agent_type else None
    )
    diagnostics.append({
        "record_schema": NATIVE_HOOK_MISMATCH_DIAGNOSTIC_SCHEMA,
        "observation_sequence": sequence,
        "hook_event_name": event_name,
        "reason": reason,
        "task_session_id_seen": session_id is not None,
        "task_session_id_digest": digest(session_id),
        "hook_session_id_seen": hook_session_id is not None,
        "hook_session_id_digest": digest(hook_session_id),
        "task_id_seen": task_id is not None,
        "task_id_digest": digest(task_id),
        "callback_tool_use_id_seen": callback_tool_use_id is not None,
        "callback_tool_use_id_digest": digest(callback_tool_use_id),
        "input_tool_use_id_seen": input_tool_use_id is not None,
        "input_tool_use_id_digest": digest(input_tool_use_id),
        "task_tool_use_id_seen": task_tool_use_id is not None,
        "task_tool_use_id_digest": digest(task_tool_use_id),
        "hook_agent_id_seen": hook_agent_id is not None,
        "hook_agent_id_digest": digest(hook_agent_id),
        "agent_type": safe_agent_type,
    })
    return True


def _native_hook_error_response(request_id: str) -> dict[str, object]:
    """Return only the pinned SDK error envelope, without input details."""
    return {
        "type": "control_response",
        "response": {
            "subtype": "error",
            "request_id": request_id,
            "error": "native hook callback rejected",
        },
    }


def _native_hook_success_response(request_id: str) -> dict[str, object]:
    return {
        "type": "control_response",
        "response": {
            "subtype": "success",
            "request_id": request_id,
            "response": {},
        },
    }


def _native_hook_text(
    value: object,
    *,
    path: bool = False,
) -> str | None:
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    limit = MAX_NATIVE_HOOK_PATH if path else MAX_NATIVE_TASK_TOKEN
    if len(value) > limit:
        return None
    return value


def _native_hook_input_size(value: object) -> int | None:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    except (RecursionError, TypeError, ValueError, UnicodeError):
        return None
    return len(encoded)


def _native_hook_frame_fingerprint(frame: object) -> tuple[str | None, bool]:
    size = _native_hook_input_size(frame)
    if size is None:
        return None, False
    if size > MAX_NATIVE_HOOK_INPUT_BYTES:
        return None, True
    try:
        return _canonical_digest(frame), False
    except (RecursionError, TypeError, ValueError, UnicodeError):
        return None, False


def _native_hook_record(
    runtime: dict[str, object],
    event_name: str,
    hook_input: Mapping[str, object],
    session_id: str,
    tool_use_id: str | None,
    task_id: str | None,
    agent_id: str,
    agent_type: str,
    join_status: str,
) -> None:
    transcript_path = str(hook_input["transcript_path"])
    cwd = str(hook_input["cwd"])
    sequence = int(runtime.get("native_hook_observation_sequence", 0)) + 1
    runtime["native_hook_observation_sequence"] = sequence
    runtime["native_hook_observed_count"] = int(
        runtime.get("native_hook_observed_count", 0)
    ) + 1
    evidence: dict[str, object] = {
        "record_schema": "native-hook-observation-v1",
        "hook_event_name": event_name,
        "observation_sequence": sequence,
        "provenance": "hook-observed",
        "join_status": join_status,
        "session_id_seen": True,
        "session_id_digest": digest(session_id),
        "task_id_seen": task_id is not None,
        "tool_use_id_seen": tool_use_id is not None,
        "agent_id_seen": True,
        "agent_id_digest": digest(agent_id),
        "agent_type": agent_type,
        "transcript_path_seen": True,
        "transcript_path_digest": digest(transcript_path),
        "cwd_seen": True,
        "cwd_digest": digest(cwd),
    }
    if task_id is not None:
        evidence["task_id_digest"] = digest(task_id)
    if tool_use_id is not None:
        evidence["tool_use_id_digest"] = digest(tool_use_id)
    if event_name == "SubagentStop":
        child_path = str(hook_input["agent_transcript_path"])
        evidence["agent_transcript_path_seen"] = True
        evidence["agent_transcript_path_digest"] = digest(child_path)
        evidence["stop_hook_active"] = bool(hook_input["stop_hook_active"])
    limit = runtime.get("native_hook_evidence_limit", MAX_NATIVE_HOOK_EVIDENCE)
    try:
        limit = max(0, min(int(limit), MAX_NATIVE_HOOK_EVIDENCE))
    except (TypeError, ValueError):
        limit = MAX_NATIVE_HOOK_EVIDENCE
    records = runtime.setdefault("native_hook_evidence", [])
    if not isinstance(records, list):
        records = []
        runtime["native_hook_evidence"] = records
    if len(records) < limit:
        records.append(evidence)
    else:
        runtime["native_hook_evidence_overflow"] = True
        _append_native_hook_reason(runtime, "native-hook-evidence-overflow")


def handle_native_hook_callback(
    frame: object,
    runtime: dict[str, object],
) -> dict[str, object] | None:
    """Validate one pinned hook callback and return at most one wire reply.

    This records only bounded, structural hook facts. It never reads a
    transcript path and never changes task-terminal or effect evidence.
    """
    if not isinstance(frame, Mapping):
        _append_native_hook_reason(runtime, "malformed-hook-frame")
        return None
    request_id = _native_hook_text(frame.get("request_id"))
    if request_id is None:
        _append_native_hook_reason(runtime, "missing-hook-request-id")
        return None
    fingerprint, oversized = _native_hook_frame_fingerprint(frame)
    marker = "oversized" if oversized else fingerprint or "malformed"
    fingerprints = runtime.setdefault("native_hook_request_fingerprints", {})
    if not isinstance(fingerprints, dict):
        fingerprints = {}
        runtime["native_hook_request_fingerprints"] = fingerprints
    if request_id in fingerprints:
        if fingerprints[request_id] != marker:
            _append_native_hook_reason(runtime, "hook-request-id-conflict")
        return None
    if len(fingerprints) >= MAX_NATIVE_HOOK_REQUESTS:
        runtime["native_hook_request_overflow"] = True
        _append_native_hook_reason(runtime, "native-hook-request-overflow")
        return None
    fingerprints[request_id] = marker
    if fingerprint is None and not oversized:
        _append_native_hook_reason(runtime, "malformed-hook-frame")
        return _native_hook_error_response(request_id)
    if oversized:
        _append_native_hook_reason(runtime, "oversized-hook-input")
        return _native_hook_error_response(request_id)
    request = frame.get("request")
    if not isinstance(request, Mapping):
        _append_native_hook_reason(runtime, "malformed-hook-request")
        return _native_hook_error_response(request_id)
    if request.get("subtype") != "hook_callback":
        _append_native_hook_reason(runtime, "unexpected-hook-subtype")
        return _native_hook_error_response(request_id)
    callback_id = _native_hook_text(request.get("callback_id"))
    callback_events = {
        callback_id: event_name
        for event_name, callback_id in NATIVE_HOOK_CALLBACK_IDS.items()
    }
    event_name = callback_events.get(callback_id)
    if event_name is None:
        _append_native_hook_reason(runtime, "unknown-hook-callback")
        return _native_hook_error_response(request_id)
    hook_input = request.get("input")
    if not isinstance(hook_input, Mapping):
        _append_native_hook_reason(runtime, "malformed-hook-input")
        return _native_hook_error_response(request_id)
    hook_input_size = _native_hook_input_size(hook_input)
    if hook_input_size is None or hook_input_size > MAX_NATIVE_HOOK_INPUT_BYTES:
        _append_native_hook_reason(runtime, "oversized-hook-input")
        return _native_hook_error_response(request_id)
    if hook_input.get("hook_event_name") != event_name:
        _append_native_hook_reason(runtime, "hook-event-mismatch")
        return _native_hook_error_response(request_id)
    raw_tool_use_id = request.get("tool_use_id")
    tool_use_id = (
        None
        if raw_tool_use_id is None
        else _native_hook_text(raw_tool_use_id)
    )
    if raw_tool_use_id is not None and tool_use_id is None:
        _append_native_hook_reason(runtime, "malformed-hook-tool-use-id")
        return _native_hook_error_response(request_id)
    callback_tool_use_id = tool_use_id
    input_tool_use_id = hook_input.get("tool_use_id")
    if input_tool_use_id is not None:
        input_tool_use_id = _native_hook_text(input_tool_use_id)
        if (
            input_tool_use_id is None
            or (
                tool_use_id is not None
                and input_tool_use_id != tool_use_id
            )
        ):
            if (input_tool_use_id is not None and tool_use_id is not None
                    and input_tool_use_id != tool_use_id):
                _count_native_hook_id_rejection(runtime, "conflict")
                _append_native_hook_mismatch_diagnostic(
                    runtime,
                    event_name=event_name,
                    reason="callback-input-tool-use-id-conflict",
                    callback_tool_use_id=callback_tool_use_id,
                    input_tool_use_id=input_tool_use_id,
                    hook_session_id=_native_hook_text(
                        hook_input.get("session_id")
                    ),
                    hook_agent_id=_native_hook_text(hook_input.get("agent_id")),
                    agent_type=_native_hook_text(hook_input.get("agent_type")),
                )
            _append_native_hook_reason(runtime, "hook-tool-use-id-conflict")
            return _native_hook_error_response(request_id)
        if tool_use_id is None:
            # Some callback frames carry tool_use_id only in their input. Keep
            # that exact value so a later task_started frame can join an early
            # hook callback by session and tool identity.
            tool_use_id = input_tool_use_id
    session_id = _native_hook_text(hook_input.get("session_id"))
    current_session_id = _native_hook_text(runtime.get("session_id"))
    if session_id is None:
        _append_native_hook_reason(runtime, "missing-hook-session-id")
        return _native_hook_error_response(request_id)
    if current_session_id is not None and session_id != current_session_id:
        _append_native_hook_reason(runtime, "hook-session-mismatch")
        return _native_hook_error_response(request_id)
    agent_id = _native_hook_text(hook_input.get("agent_id"))
    if agent_id is None:
        _append_native_hook_reason(runtime, "missing-hook-agent-id")
        return _native_hook_error_response(request_id)
    agent_type = _native_hook_text(hook_input.get("agent_type"))
    if agent_type is None:
        _append_native_hook_reason(runtime, "missing-hook-agent-type")
        return _native_hook_error_response(request_id)
    configured_agent_type = _native_hook_text(runtime.get("native_agent_type"))
    if configured_agent_type is not None and agent_type != configured_agent_type:
        _append_native_hook_reason(runtime, "hook-agent-type-mismatch")
        return _native_hook_error_response(request_id)
    transcript_path = _native_hook_text(
        hook_input.get("transcript_path"), path=True
    )
    cwd = _native_hook_text(hook_input.get("cwd"), path=True)
    if transcript_path is None or cwd is None:
        _append_native_hook_reason(runtime, "missing-hook-context-path")
        return _native_hook_error_response(request_id)
    task_id = _native_hook_text(runtime.get("actual_task_id"))
    current_tool_use_id = _native_hook_text(runtime.get("task_tool_use_id"))
    tool_use_id_mismatch = False
    if (
        tool_use_id is not None
        and current_tool_use_id is not None
        and tool_use_id != current_tool_use_id
    ):
        # Keep the structurally valid callback as unresolved evidence. The SDK
        # sidecar bridge may later bind its agent identity to the task-started
        # Agent tool; the callback tool digest itself remains unchanged.
        tool_use_id_mismatch = True
    join_status = "joined"
    if (
        current_session_id is None
        or task_id is None
        or current_tool_use_id is None
        or tool_use_id is None
        or tool_use_id_mismatch
    ):
        join_status = "unresolved"
    if event_name == "SubagentStop":
        child_path = _native_hook_text(
            hook_input.get("agent_transcript_path"), path=True
        )
        if child_path is None or not isinstance(
            hook_input.get("stop_hook_active"), bool
        ):
            _append_native_hook_reason(runtime, "malformed-subagent-stop")
            return _native_hook_error_response(request_id)
    if tool_use_id_mismatch:
        if not _append_native_hook_mismatch_diagnostic(
            runtime,
            event_name=event_name,
            reason="callback-task-tool-use-id-mismatch",
            callback_tool_use_id=callback_tool_use_id,
            input_tool_use_id=input_tool_use_id,
            hook_session_id=session_id,
            hook_agent_id=agent_id,
            agent_type=agent_type,
        ):
            return _native_hook_error_response(request_id)
        _count_native_hook_id_rejection(runtime, "mismatch")
    if join_status == "joined":
        agent_bindings = runtime.setdefault("native_hook_agent_bindings", {})
        if not isinstance(agent_bindings, dict):
            agent_bindings = {}
            runtime["native_hook_agent_bindings"] = agent_bindings
        agent_key = digest(agent_id)
        binding = (
            digest(session_id),
            digest(task_id),
            digest(tool_use_id),
        )
        prior_binding = agent_bindings.get(agent_key)
        if prior_binding is not None and prior_binding != binding:
            _append_native_hook_reason(runtime, "reused-agent-id")
            return _native_hook_error_response(request_id)
        agent_bindings[agent_key] = binding
    _native_hook_record(
        runtime,
        event_name,
        hook_input,
        session_id,
        tool_use_id if tool_use_id is not None else None,
        task_id if join_status == "joined" else None,
        agent_id,
        agent_type,
        join_status,
    )
    return _native_hook_success_response(request_id)


def native_hook_evidence_report(runtime: Mapping[str, object]) -> dict[str, object]:
    records = runtime.get("native_hook_evidence")
    records = records if isinstance(records, list) else []
    reasons = runtime.get("native_hook_unknown_reasons")
    reasons = reasons if isinstance(reasons, list) else []
    deduped_reasons: list[str] = []
    for reason in reasons:
        if isinstance(reason, str) and reason not in deduped_reasons:
            deduped_reasons.append(reason)
    fingerprints = runtime.get("native_hook_request_fingerprints")
    request_count = len(fingerprints) if isinstance(fingerprints, dict) else 0
    diagnostics = runtime.get("native_hook_mismatch_diagnostics", [])
    diagnostics = diagnostics if isinstance(diagnostics, list) else []
    expected_agent_type = runtime.get("native_agent_type", SOURCE_AGENT_NAME)
    if not isinstance(expected_agent_type, str) or not expected_agent_type:
        expected_agent_type = SOURCE_AGENT_NAME
    return {
        "record_schema": "native-hook-observation-v1",
        "observed_count": int(runtime.get("native_hook_observed_count", 0)),
        "stored_count": len(records),
        "request_count": request_count,
        "request_limit": MAX_NATIVE_HOOK_REQUESTS,
        "request_overflow": bool(runtime.get("native_hook_request_overflow")),
        "overflow": bool(runtime.get("native_hook_evidence_overflow")),
        "unknown_reasons": deduped_reasons[:MAX_NATIVE_HOOK_REASONS],
        "records": [
            dict(record) for record in records if isinstance(record, Mapping)
        ],
        "mismatch_diagnostic_overflow": bool(
            runtime.get("native_hook_mismatch_diagnostic_overflow")
        ),
        "mismatch_diagnostics": [
            dict(record) for record in diagnostics
            if _valid_native_hook_mismatch_diagnostic(
                record, expected_agent_type=expected_agent_type,
            )
        ][:MAX_NATIVE_HOOK_EVIDENCE],
        "support_claim": False,
    }


def _valid_native_hook_mismatch_diagnostic(
    record: object,
    *,
    expected_agent_type: str,
) -> bool:
    fields = {
        "record_schema", "observation_sequence", "hook_event_name", "reason",
        "task_session_id_seen", "task_session_id_digest",
        "hook_session_id_seen", "hook_session_id_digest", "task_id_seen",
        "task_id_digest", "callback_tool_use_id_seen",
        "callback_tool_use_id_digest", "input_tool_use_id_seen",
        "input_tool_use_id_digest", "task_tool_use_id_seen",
        "task_tool_use_id_digest", "hook_agent_id_seen",
        "hook_agent_id_digest", "agent_type",
    }
    if not isinstance(record, Mapping) or set(record) != fields:
        return False
    if (
        record.get("record_schema") != NATIVE_HOOK_MISMATCH_DIAGNOSTIC_SCHEMA
        or type(record.get("observation_sequence")) is not int
        or not 1 <= int(record.get("observation_sequence", 0))
        <= MAX_NATIVE_HOOK_EVIDENCE
        or record.get("hook_event_name") not in NATIVE_HOOK_CALLBACK_IDS
        or record.get("reason") not in {
            "callback-task-tool-use-id-mismatch",
            "callback-input-tool-use-id-conflict",
        }
    ):
        return False
    boolean_digest_pairs = (
        ("task_session_id_seen", "task_session_id_digest"),
        ("hook_session_id_seen", "hook_session_id_digest"),
        ("task_id_seen", "task_id_digest"),
        ("callback_tool_use_id_seen", "callback_tool_use_id_digest"),
        ("input_tool_use_id_seen", "input_tool_use_id_digest"),
        ("task_tool_use_id_seen", "task_tool_use_id_digest"),
        ("hook_agent_id_seen", "hook_agent_id_digest"),
    )
    for seen_field, digest_field in boolean_digest_pairs:
        seen = record.get(seen_field)
        value = record.get(digest_field)
        if type(seen) is not bool:
            return False
        if seen:
            if (not isinstance(value, str)
                    or re.fullmatch(r"[0-9a-f]{64}", value) is None):
                return False
        elif value is not None:
            return False
    if record.get("reason") == "callback-input-tool-use-id-conflict":
        return bool(
            record.get("agent_type") in {None, expected_agent_type}
            and
            record.get("callback_tool_use_id_seen") is True
            and record.get("input_tool_use_id_seen") is True
            and record.get("callback_tool_use_id_digest")
            != record.get("input_tool_use_id_digest")
        )
    effective_digest = (
        record.get("callback_tool_use_id_digest")
        if record.get("callback_tool_use_id_seen") is True
        else record.get("input_tool_use_id_digest")
    )
    return bool(
        record.get("task_session_id_seen") is True
        and record.get("hook_session_id_seen") is True
        and record.get("task_session_id_digest")
        == record.get("hook_session_id_digest")
        and record.get("task_id_seen") is True
        and (record.get("callback_tool_use_id_seen") is True
             or record.get("input_tool_use_id_seen") is True)
        and record.get("agent_type") == expected_agent_type
        and (record.get("callback_tool_use_id_seen") is not True
             or record.get("input_tool_use_id_seen") is not True
             or record.get("callback_tool_use_id_digest")
             == record.get("input_tool_use_id_digest"))
    ) and bool(
        record.get("task_tool_use_id_seen") is True
        and record.get("hook_agent_id_seen") is True
        and record.get("agent_type") == expected_agent_type
        and effective_digest != record.get("task_tool_use_id_digest")
    )


def native_hook_evidence_summary(runtime: Mapping[str, object]) -> dict[str, object]:
    """Return a compact source-phase hook diagnostic without raw hook input."""

    report = native_hook_evidence_report(runtime)
    records = report.get("records")
    records = records if isinstance(records, list) else []
    expected_agent_type = runtime.get("native_agent_type", SOURCE_AGENT_NAME)
    if not isinstance(expected_agent_type, str) or not expected_agent_type:
        expected_agent_type = SOURCE_AGENT_NAME
    safe_records = [
        record for record in records
        if isinstance(record, Mapping)
        and _valid_native_hook_seed_record(
            record, expected_agent_type=expected_agent_type,
        )
    ][:MAX_NATIVE_HOOK_EVIDENCE]
    joined = sum(
        1 for record in records
        if isinstance(record, Mapping) and record.get("join_status") == "joined"
    )
    unresolved = sum(
        1 for record in records
        if isinstance(record, Mapping) and record.get("join_status") == "unresolved"
    )
    task_events = runtime.get("native_task_evidence")
    task_events = task_events if isinstance(task_events, list) else []
    actual_session = runtime.get("session_id")
    actual_task = runtime.get("actual_task_id")
    start_candidates: list[Mapping[str, object]] = []
    if (isinstance(actual_session, str) and actual_session
            and isinstance(actual_task, str) and actual_task):
        session_digest = digest(actual_session)
        task_digest = digest(actual_task)
        start_candidates = [
            event for event in task_events
            if isinstance(event, Mapping)
            and event.get("event_subtype") == "task_started"
            and event.get("session_id_digest") == session_digest
            and event.get("task_id_digest") == task_digest
            and _native_task_started_seed_event_valid(event)
        ][:MAX_NATIVE_TASK_EVIDENCE]
    start = start_candidates[0] if len(start_candidates) == 1 else None
    started_tool_seen: bool | None = None
    session_matched: int | None = None
    same_task: list[Mapping[str, object]] = []
    exact_link_count: int | None = None
    same_task_tool_missing: int | None = None
    same_task_tool_mismatch: int | None = None
    if isinstance(start, Mapping):
        started_tool_seen = start.get("tool_use_id_seen") is True
        start_session_digest = start.get("session_id_digest")
        start_task_digest = start.get("task_id_digest")
        start_tool_digest = start.get("tool_use_id_digest")
        session_records = [
            record for record in safe_records
            if record.get("session_id_digest") == start_session_digest
        ]
        session_matched = len(session_records)
        same_task = [
            record for record in session_records
            if record.get("task_id_seen") is True
            and record.get("task_id_digest") == start_task_digest
        ]
        same_task_tool_missing = sum(
            1 for record in same_task if record.get("tool_use_id_seen") is not True
        )
        same_task_tool_mismatch = (
            sum(
                1 for record in same_task
                if record.get("tool_use_id_seen") is True
                and record.get("tool_use_id_digest") != start_tool_digest
            )
            if started_tool_seen else None
        )
        exact_link_count = sum(
            1 for record in session_records
            if started_tool_seen
            and record.get("tool_use_id_seen") is True
            and record.get("tool_use_id_digest") == start_tool_digest
            and (
                record.get("task_id_seen") is not True
                or record.get("task_id_digest") == start_task_digest
            )
        )
    return {
        "record_schema": report.get("record_schema"),
        "observed_count": report.get("observed_count"),
        "stored_count": report.get("stored_count"),
        "request_count": report.get("request_count"),
        "request_limit": report.get("request_limit"),
        "request_overflow": report.get("request_overflow"),
        "overflow": report.get("overflow"),
        "joined_count": joined,
        "unresolved_count": unresolved,
        "started_task_event_count": len(start_candidates),
        "started_task_tool_use_id_seen": started_tool_seen,
        "session_matched_hook_count": session_matched,
        "hook_tool_use_id_seen_count": sum(
            1 for record in safe_records
            if record.get("tool_use_id_seen") is True
        ),
        "hook_tool_use_id_missing_count": sum(
            1 for record in safe_records
            if record.get("tool_use_id_seen") is not True
        ),
        "same_task_hook_count": len(same_task) if isinstance(start, Mapping) else None,
        "same_task_tool_use_id_missing_count": same_task_tool_missing,
        "same_task_tool_use_id_mismatch_count": same_task_tool_mismatch,
        "exact_task_tool_link_candidate_count": exact_link_count,
        "rejected_tool_use_id_conflict_count": min(
            MAX_NATIVE_HOOK_REQUESTS,
            max(0, runtime.get("native_hook_tool_use_id_conflict_count", 0))
            if type(runtime.get("native_hook_tool_use_id_conflict_count", 0)) is int
            else 0,
        ),
        "rejected_tool_use_id_mismatch_count": min(
            MAX_NATIVE_HOOK_REQUESTS,
            max(0, runtime.get("native_hook_tool_use_id_mismatch_count", 0))
            if type(runtime.get("native_hook_tool_use_id_mismatch_count", 0)) is int
            else 0,
        ),
        "unknown_reasons": list(report.get("unknown_reasons", [])),
        "mismatch_diagnostic_overflow": report.get(
            "mismatch_diagnostic_overflow"
        ),
        "mismatch_diagnostics": list(report.get("mismatch_diagnostics", [])),
        "sdk_sidecar_bridge": _native_hook_sdk_sidecar_diagnostic_summary(runtime),
        "support_claim": False,
    }


def _native_hook_sdk_sidecar_diagnostic_summary(
    runtime: Mapping[str, object],
) -> dict[str, object]:
    raw = runtime.get("native_hook_sdk_sidecar_diagnostic")
    if not isinstance(raw, Mapping):
        return {"status": "not-attempted", "reason": None}
    result: dict[str, object] = {}
    for field in (
        "status", "reason", "hook_record_count", "parent_candidate_count",
        "matching_sidecar_count", "scan_entry_count", "scan_file_count",
        "scan_byte_count", "parent_history_sha256", "child_transcript_sha256",
        "sidecar_sha256",
    ):
        value = raw.get(field)
        if field.endswith("_sha256"):
            if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
                result[field] = value
        elif field == "status":
            if value in {"not-needed", "observed", "missing", "ambiguous", "conflict", "incomplete", "unavailable"}:
                result[field] = value
        elif field == "reason":
            if value is None or isinstance(value, str) and re.fullmatch(
                r"[a-z0-9-]{1,64}", value
            ):
                result[field] = value
        elif type(value) is int and 0 <= value <= MAX_HISTORY_SCAN_ENTRIES * MAX_HISTORY_CONTENT_BYTES:
            result[field] = value
    if "status" not in result:
        return {"status": "unavailable", "reason": "diagnostic-invalid"}
    if "reason" not in result:
        result["reason"] = None
    return result


def native_task_lifecycle_summary(runtime: Mapping[str, object]) -> dict[str, object]:
    """Return a compact source-phase lifecycle diagnostic."""

    report = native_task_lifecycle_report(runtime)
    return {
        "record_schema": NATIVE_TASK_RECORD_SCHEMA,
        "observation_status": report.get("observation_status"),
        "event_count": report.get("event_count"),
        "observation_sequence_max": report.get("observation_sequence_max"),
        "overflow": report.get("overflow"),
        "incomplete": report.get("incomplete"),
        "seed_provenance": report.get("seed_provenance"),
        "source_terminal_seed_index": report.get("source_terminal_seed_index"),
        "unknown_reasons": list(report.get("unknown_reasons", [])),
        "support_claim": False,
    }


def _contains_assistant_or_tool_activity(value: object, depth: int = 0) -> bool:
    if depth > 8:
        # The startup exception requires proving that no assistant/tool frame
        # occurred. Deeply nested unknown payloads are therefore activity-risk
        # evidence, not a reason to stop looking and assume a clean frame.
        return True
    if isinstance(value, Mapping):
        if value.get("role") in {"assistant", "tool"}:
            return True
        if value.get("type") in {
            "assistant", "tool", "tool_use", "tool_result", "tool_error",
        }:
            return True
        return any(
            _contains_assistant_or_tool_activity(child, depth + 1)
            for child in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(
            _contains_assistant_or_tool_activity(child, depth + 1)
            for child in value
        )
    return False


def _observe_v1_startup_frame(frame: Mapping[str, object], runtime: dict[str, object]) -> None:
    if "startup_activity_observed" not in runtime:
        return
    if runtime.get("startup_observation_active") is not True:
        return
    response = frame.get("response")
    response = response if isinstance(response, Mapping) else {}
    request = frame.get("request")
    request = request if isinstance(request, Mapping) else {}
    subtype = (
        frame.get("subtype")
        or response.get("subtype")
        or request.get("subtype")
    )
    request_id = response.get("request_id")
    known_init = (
        frame.get("type") == "control_response"
        and request_id == runtime.get("init_request")
    ) or (
        frame.get("type") == "system"
        and subtype in {"init", "system_init", "init_success"}
    )
    if known_init:
        return
    if _contains_assistant_or_tool_activity(frame):
        runtime["startup_activity_observed"] = True
        kinds = runtime.setdefault("startup_activity_kinds", [])
        if isinstance(kinds, list):
            kind = frame.get("type") or subtype or "unknown"
            if str(kind) not in kinds:
                kinds.append(str(kind))
    if frame.get("type") in {
        "system", "control_response", "control_request", "event",
    }:
        known_subtypes = {
            "success", "error", "init", "system_init", "init_success",
            "message_start", "message_delta", "message_stop",
            "task_started", "task_progress", "task_updated",
            "task_notification",
        }
        if isinstance(subtype, str) and subtype not in known_subtypes:
                runtime["startup_unclassified_lifecycle_count"] = int(
                    runtime.get("startup_unclassified_lifecycle_count", 0)
                ) + 1


def _is_expected_two_domain_startup_lifecycle_frame(
    frame: Mapping[str, object],
    runtime: Mapping[str, object],
) -> bool:
    response = frame.get("response")
    response = response if isinstance(response, Mapping) else {}
    subtype = frame.get("subtype") or response.get("subtype")
    if (frame.get("type") == "control_response"
            and response.get("request_id") == runtime.get("init_request")
            and subtype == "success"):
        return True
    if (frame.get("type") == "system"
            and subtype in {"init", "system_init", "init_success"}):
        return True
    return bool(
        frame.get("type") == "system"
        and subtype == "task_notification"
    )


def observe_frame(frame: object, runtime: dict[str, object]) -> None:
    """Consume one native frame, retaining only lifecycle facts/digests."""

    if not isinstance(frame, Mapping):
        runtime["unparsed_frames"] = int(runtime["unparsed_frames"]) + 1
        return
    runtime["frames_seen"] = int(runtime["frames_seen"]) + 1
    _observe_v1_startup_frame(frame, runtime)
    if (runtime.get("startup_observation_active") is True
            and frame.get("type") == "result"):
        runtime["startup_result_count"] = int(
            runtime.get("startup_result_count", 0)
        ) + 1
        result_origins = runtime.setdefault("startup_result_origins", [])
        if (isinstance(result_origins, list)
                and len(result_origins) < MAX_NATIVE_TASK_EVIDENCE):
            result_origins.append(native_frame_origin_kind(frame))
        else:
            runtime["startup_result_origin_overflow"] = True
        if (frame.get("subtype") != "success"
                or frame.get("is_error") is not False
                or "error" in frame
                or _contains_query_error_or_deferred_tool(frame)):
            runtime["startup_result_error_count"] = int(
                runtime.get("startup_result_error_count", 0)
            ) + 1
        expected_session = runtime.get("startup_parent_session_id")
        observed_session = frame.get("session_id")
        if (isinstance(expected_session, str)
                and isinstance(observed_session, str)
                and observed_session == expected_session):
            runtime["startup_result_parent_session_match_count"] = int(
                runtime.get("startup_result_parent_session_match_count", 0)
            ) + 1
            runtime["startup_result_parent_session_id_digest"] = digest(
                observed_session
            )
        else:
            runtime["startup_result_parent_session_mismatch_count"] = int(
                runtime.get("startup_result_parent_session_mismatch_count", 0)
            ) + 1
    observe_two_domain_history_query_frame(frame, runtime)
    response = frame.get("response")
    response = response if isinstance(response, Mapping) else {}
    subtype = _native_event_value(frame, "subtype")
    if (runtime.get("startup_observation_active") is True
            and frame.get("type") in {
                "system", "event", "control_response", "control_request",
            }
            and not _is_expected_two_domain_startup_lifecycle_frame(frame, runtime)):
        runtime["startup_other_lifecycle_events"] = int(
            runtime.get("startup_other_lifecycle_events", 0)
        ) + 1
    if runtime.get("startup_observation_active") is True:
        expected_startup_frame = (
            frame.get("type") == "result"
            or _is_expected_two_domain_startup_lifecycle_frame(frame, runtime)
        )
        if not expected_startup_frame:
            runtime["startup_unexpected_frame_count"] = int(
                runtime.get("startup_unexpected_frame_count", 0)
            ) + 1
    observe_control_event(subtype, runtime)
    request_id = response.get("request_id")
    if frame.get("type") == "control_response" and request_id == runtime.get(
        "init_request"
    ) and subtype == "success":
        runtime["initialize_succeeded"] = True
    if frame.get("type") == "control_response" and request_id == runtime.get(
        "stop_request"
    ) and subtype == "success":
        runtime["stop_receipt"] = True
    if frame.get("type") == "control_response" and request_id == runtime.get(
        "interrupt_request"
    ) and subtype == "success":
        runtime["interrupt_receipt"] = True
    if runtime.get("session_id") is None:
        session_id = find_value(frame, ("session_id",))
        if session_id:
            runtime["session_id"] = str(session_id)
    if (
        isinstance(frame, Mapping)
        and frame.get("type") == "result"
        and frame.get("subtype") in {None, "success"}
        and frame.get("is_error") is not True
    ):
        runtime["successful_result_seen"] = True
        runtime["successful_result_count"] = int(
            runtime.get("successful_result_count", 0)
        ) + 1
        result_session_id = frame.get("session_id") or find_value(
            frame, ("session_id",)
        )
        if result_session_id:
            runtime["successful_result_session_id"] = str(result_session_id)
        result_uuid = frame.get("uuid")
        if result_uuid:
            runtime["successful_result_uuid_digest"] = digest(result_uuid)
    if is_successful_parent_result(frame):
        runtime["source_parent_result_seen"] = True
        runtime["source_parent_result_origin"] = result_origin_kind(frame)
        runtime["successful_parent_result_count"] = int(
            runtime.get("successful_parent_result_count", 0)
        ) + 1
    if subtype in {
        "task_started", "task_progress", "task_updated", "task_notification"
    }:
        runtime["native_task_events"] = int(runtime["native_task_events"]) + 1
        record_native_task_lifecycle_event(frame, runtime)
    task_id = _native_event_value(frame, "task_id")
    task_type = _native_event_value(frame, "task_type")
    task_status = _native_event_value(frame, "status")
    valid_task_id = (
        isinstance(task_id, str) and bool(task_id)
        and len(task_id) <= MAX_NATIVE_TASK_TOKEN
    )
    if subtype == "task_started" and valid_task_id and task_type == "local_agent":
        if str(task_id) != runtime.get("actual_task_id"):
            runtime["task_terminal_observed"] = False
        runtime["task_started"] = True
        runtime["actual_task_id"] = str(task_id)
        agent_id = find_value(frame, ("agent_id",))
        runtime["task_agent_id"] = (
            str(agent_id)
            if isinstance(agent_id, str) and agent_id
            and len(agent_id) <= MAX_NATIVE_TASK_TOKEN
            else None
        )
        tool_use_id = _native_event_value(frame, "tool_use_id")
        runtime["task_tool_use_id"] = (
            str(tool_use_id)
            if isinstance(tool_use_id, str) and tool_use_id
            and len(tool_use_id) <= MAX_NATIVE_TASK_TOKEN
            else None
        )
    if (runtime.get("actual_task_id") and task_id == runtime.get("actual_task_id")
            and subtype == "task_notification" and task_status == "stopped"):
        # A stopped task is not automatically a stopped Bash tool.
        runtime["stopped_notification"] = True
    if (
        runtime.get("actual_task_id")
        and task_id == runtime.get("actual_task_id")
        and subtype in {"task_notification", "task_updated"}
        and task_status in NATIVE_TASK_TERMINAL_STATUSES
    ):
        runtime["task_terminal_observed"] = True
    if frame_has_tool_result(frame, SOURCE_TOOL_ID):
        runtime["tool_terminal"] = True


def read_frames(
    process: subprocess.Popen[bytes],
    selector: selectors.BaseSelector,
    buffers: dict[Any, bytearray],
    runtime: dict[str, object],
    deadline: float,
) -> None:
    while time.monotonic() < deadline:
        events = selector.select(.1)
        if not events:
            continue
        for key, _ in events:
            try:
                chunk = os.read(key.fileobj.fileno(), 65536)
            except OSError:
                runtime["read_failed"] = True
                runtime.setdefault("reason_codes", []).append("runtime-read-failed")
                return
            if chunk:
                buffers[key.fileobj].extend(chunk)
                if sum(len(value) for value in buffers.values()) > MAX_RUNTIME_OUTPUT:
                    runtime["read_failed"] = True
                    runtime["reason_codes"].append("runtime-output-limit")
                    return
            else:
                if key.fileobj is process.stdout:
                    runtime["stdout_eof"] = True
                    if runtime.get("history_query_observation_active") is True:
                        runtime["history_query_stdout_eof"] = True
                selector.unregister(key.fileobj)
        output = buffers[process.stdout]
        while b"\n" in output:
            end = output.index(b"\n")
            line = bytes(output[:end])
            del output[:end + 1]
            try:
                frame = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                runtime["unparsed_frames"] = int(runtime["unparsed_frames"]) + 1
                continue
            if isinstance(frame, Mapping):
                request = frame.get("request")
                if (
                    runtime.get("native_hook_recording_enabled") is True
                    and frame.get("type") == "control_request"
                    and isinstance(request, Mapping)
                    and request.get("subtype") == "hook_callback"
                ):
                    response = handle_native_hook_callback(frame, runtime)
                    if response is not None:
                        try:
                            send_frame(process, response)
                        except (OSError, TypeError, ValueError):
                            runtime["read_failed"] = True
                            reasons = runtime.setdefault("reason_codes", [])
                            if "native-hook-response-write-failed" not in reasons:
                                reasons.append("native-hook-response-write-failed")
                            return
                    runtime["frames_seen"] = int(runtime.get("frames_seen", 0)) + 1
                    _observe_v1_startup_frame(frame, runtime)
                    continue
            observe_frame(frame, runtime)


def _proc_identity(pid: int) -> dict[str, object] | None:
    """Read PID, parent, and Linux starttime without retaining cmdline text."""
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text(
            encoding="utf-8", errors="replace"
        )
        close = stat.rfind(")")
        if close < 0:
            return None
        fields = stat[close + 2:].split()
        if len(fields) <= 19:
            return None
        ppid = int(fields[1])
        starttime = fields[19]
        argv = [
            part for part in (
                Path("/proc") / str(pid) / "cmdline"
            ).read_bytes().split(b"\0")
            if part
        ]
    except (OSError, ValueError):
        return None
    return {
        "pid": pid,
        "ppid": ppid,
        "starttime": starttime,
        "state": fields[0],
        "scripted_sleeper": (
            len(argv) == 2
            and argv[0].rsplit(b"/", 1)[-1] == b"sleep"
            and argv[1] == b"30"
        ),
    }


def _proc_snapshot() -> dict[int, dict[str, object]] | None:
    proc = Path("/proc")
    if not proc.exists():
        return None
    snapshot: dict[int, dict[str, object]] = {}
    try:
        entries = list(proc.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        identity = _proc_identity(int(entry.name))
        if identity is not None:
            snapshot[int(entry.name)] = identity
    return snapshot


def _descendants(
    root_pid: int,
    snapshot: Mapping[int, Mapping[str, object]],
) -> list[dict[str, object]]:
    children: dict[int, list[dict[str, object]]] = {}
    for identity in snapshot.values():
        parent = identity.get("ppid")
        if isinstance(parent, int):
            children.setdefault(parent, []).append(dict(identity))
    pending = [root_pid]
    result: list[dict[str, object]] = []
    while pending:
        parent = pending.pop()
        for identity in children.get(parent, []):
            result.append(identity)
            child_pid = identity.get("pid")
            if isinstance(child_pid, int):
                pending.append(child_pid)
    return result


def capture_owned_fixture_processes(root_pid: int) -> list[dict[str, object]]:
    """Capture the real scripted sleeper and its current descendants.

    The result is a private PID/starttime snapshot. Callers must revalidate
    every identity before signalling it; no namespace-wide process scan is
    ever used for cleanup.
    """
    snapshot = _proc_snapshot()
    if not snapshot:
        return []
    descendants = _descendants(root_pid, snapshot)
    sleepers = [
        identity for identity in descendants
        if identity.get("scripted_sleeper") is True
    ]
    if len(sleepers) != 1:
        return []
    sleeper_pid = sleepers[0].get("pid")
    if not isinstance(sleeper_pid, int):
        return []
    sleeper_descendants = _descendants(sleeper_pid, snapshot)
    return [sleepers[0]] + sleeper_descendants


def _identity_alive(identity: Mapping[str, object]) -> bool:
    return _identity_status(identity) == "alive"


def _identity_status(identity: Mapping[str, object]) -> str:
    """Classify an owned PID without turning observation failure into absence."""
    pid = identity.get("pid")
    starttime = identity.get("starttime")
    if not isinstance(pid, int) or not isinstance(starttime, str):
        return "unknown"
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text(
            encoding="utf-8", errors="replace"
        )
        close = stat.rfind(")")
        if close < 0:
            return "unknown"
        fields = stat[close + 2:].split()
        if len(fields) <= 19:
            return "unknown"
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unknown"
    if fields[19] != starttime:
        return "replaced"
    if fields[0] in {"Z", "X", "x"}:
        return "terminal"
    return "alive"


def fixture_processes_alive(identities: list[Mapping[str, object]]) -> bool | None:
    if not identities:
        return None
    statuses = [_identity_status(identity) for identity in identities]
    if "unknown" in statuses:
        return None
    return "alive" in statuses


def terminate_owned_fixture_processes(
    identities: list[Mapping[str, object]],
    timeout: float = 5,
) -> bool:
    """Signal only identity-revalidated sleeper descendants and await exit."""
    if not identities:
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        statuses = [_identity_status(identity) for identity in identities]
        if "unknown" in statuses:
            return False
        live = [
            identity
            for identity, status in zip(identities, statuses)
            if status == "alive"
        ]
        if not live:
            return all(status in {"absent", "replaced", "terminal"} for status in statuses)
        for identity in live:
            pid = identity.get("pid")
            if not isinstance(pid, int):
                continue
            # The starttime check immediately before signalling prevents a
            # recycled PID from receiving a signal.
            current = _proc_identity(pid)
            if current and current.get("starttime") == identity.get("starttime"):
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
        time.sleep(.1)
    statuses = [_identity_status(identity) for identity in identities]
    return (
        "unknown" not in statuses
        and all(status in {"absent", "replaced", "terminal"} for status in statuses)
    )


def process_has_sleep(
    root_pid: int | None = None,
    identities: list[Mapping[str, object]] | None = None,
) -> bool | None:
    """Observe the scripted sleeper, preferring an owned identity snapshot."""
    if identities is not None:
        return fixture_processes_alive(identities)
    if root_pid is not None:
        return bool(capture_owned_fixture_processes(root_pid))
    snapshot = _proc_snapshot()
    if snapshot is None:
        return None
    return any(identity.get("scripted_sleeper") is True
               for identity in snapshot.values())


def send_frame(process: subprocess.Popen[bytes], frame: Mapping[str, object]) -> None:
    process.stdin.write(
        (json.dumps(frame, separators=(",", ":")) + "\n").encode("utf-8")
    )
    process.stdin.flush()


def terminate(process: subprocess.Popen[bytes] | None) -> bool:
    if process is None or process.poll() is not None:
        return True
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            return False
    return process.poll() is not None


def crash_owned_process_group(process: subprocess.Popen[bytes] | None) -> bool:
    """Kill only the source process group, preserving its native records."""
    if process is None or process.poll() is not None:
        return True
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return False
    return process.poll() is not None


def observe_store(root: Path) -> dict[str, object]:
    """Observe runtime-written records by metadata only; never read contents."""

    files: list[tuple[str, int]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        files.append((path.relative_to(root).as_posix(), size))
    names = "|".join(name for name, _ in files)
    return {
        "file_count": len(files),
        "bytes": sum(size for _, size in files),
        "path_digest": digest(names),
        "transcript_record_seen": any(name.endswith(".jsonl") for name, _ in files),
        "task_record_seen": any("task" in name or "agent" in name for name, _ in files),
    }


def _native_hook_initialize_config() -> dict[str, list[dict[str, object]]]:
    return {
        event_name: [
            {
                "matcher": None,
                "hookCallbackIds": [callback_id],
            }
        ]
        for event_name, callback_id in NATIVE_HOOK_CALLBACK_IDS.items()
    }


def initialize_frame(
    expected: Mapping[str, object],
    request_id: str,
    *,
    observe_native_hooks: bool = False,
) -> dict[str, object]:
    """Match the pinned Python SDK initialize shape for configured agents."""

    return {
        "type": "control_request",
        "request_id": request_id,
        "request": {
            "subtype": "initialize",
            "hooks": (
                _native_hook_initialize_config()
                if observe_native_hooks else None
            ),
            "agents": expected["agent_config"],
        },
    }


def user_frame() -> dict[str, object]:
    # This is the same input envelope emitted by SDK query() for a string
    # prompt. The loopback server, rather than this prompt, scripts the tool.
    return {
        "type": "user",
        "session_id": "default",
        "message": {
            "role": "user",
            "content": "Run the bounded native background worker.",
        },
        "parent_tool_use_id": None,
    }


def target_release_frame() -> dict[str, object]:
    """Ask the resumed process for one bounded, target-only model turn."""
    return {
        "type": "user",
        "session_id": "default",
        "message": {
            "role": "user",
            "content": TARGET_RELEASE_MARKER,
        },
        "parent_tool_use_id": None,
    }


def target_diagnostic_history_query_frame(nonce: str) -> dict[str, object]:
    """Send one neutral human-origin query with a private fresh nonce."""
    if not isinstance(nonce, str) or len(nonce) < 32:
        raise ValueError("diagnostic history query nonce is invalid")
    return {
        "type": "user",
        "session_id": "default",
        "message": {
            "role": "user",
            "content": (
                "Read the existing parent conversation and reply with only the "
                "private diagnostic token on the final line. Token: " + nonce
            ),
        },
        "parent_tool_use_id": None,
        "origin": {"kind": "human"},
    }


def observe_two_domain_history_query_frame(
    frame: object,
    runtime: dict[str, object],
) -> None:
    """Count only fresh, exact-parent, human-origin challenge results."""
    if runtime.get("history_query_observation_active") is not True:
        return
    runtime["history_query_frame_count"] = int(
        runtime.get("history_query_frame_count", 0)
    ) + 1
    if _contains_query_error_or_deferred_tool(frame):
        runtime["history_query_error_abort_or_tool_seen"] = True
    if not isinstance(frame, Mapping):
        runtime["history_query_unexpected_frame_count"] = int(
            runtime.get("history_query_unexpected_frame_count", 0)
        ) + 1
        return
    if frame.get("type") == "assistant":
        if int(runtime.get("history_query_result_count", 0)) > 0:
            runtime["history_query_unexpected_frame_count"] = int(
                runtime.get("history_query_unexpected_frame_count", 0)
            ) + 1
        runtime["history_query_assistant_frame_count"] = int(
            runtime.get("history_query_assistant_frame_count", 0)
        ) + 1
        message = frame.get("message")
        if not isinstance(message, Mapping) or message.get("role") != "assistant":
            runtime["history_query_unexpected_frame_count"] = int(
                runtime.get("history_query_unexpected_frame_count", 0)
            ) + 1
        else:
            message_id = message.get("id")
            if isinstance(message_id, str) and message_id:
                ids = runtime.setdefault("history_query_assistant_message_id_digests", [])
                if isinstance(ids, list) and len(ids) < MAX_NATIVE_TASK_EVIDENCE:
                    ids.append(digest(message_id))
                else:
                    runtime["history_query_unexpected_frame_count"] = int(
                        runtime.get("history_query_unexpected_frame_count", 0)
                    ) + 1
            elif "id" not in message:
                runtime["history_query_assistant_message_id_missing_count"] = int(
                    runtime.get("history_query_assistant_message_id_missing_count", 0)
                ) + 1
            else:
                runtime["history_query_unexpected_frame_count"] = int(
                    runtime.get("history_query_unexpected_frame_count", 0)
                ) + 1
        return
    if frame.get("type") != "result":
        runtime["history_query_unexpected_frame_count"] = int(
            runtime.get("history_query_unexpected_frame_count", 0)
        ) + 1
        return
    runtime["history_query_result_count"] = int(
        runtime.get("history_query_result_count", 0)
    ) + 1
    expected_session = runtime.get("history_query_parent_session_id")
    challenge = runtime.get("history_query_challenge")
    exact_success = bool(
        frame.get("subtype") == "success"
        and frame.get("is_error") is False
        and native_frame_origin_kind(frame) == "human"
        and isinstance(expected_session, str)
        and frame.get("session_id") == expected_session
        and isinstance(challenge, str)
        and frame.get("result") == challenge
        and int(runtime.get("history_query_assistant_frame_count", 0)) == 1
        and "error" not in frame
        and not _contains_query_error_or_deferred_tool(frame)
    )
    if exact_success:
        runtime["history_query_exact_parent_human_result_count"] = int(
            runtime.get("history_query_exact_parent_human_result_count", 0)
        ) + 1
        runtime["history_query_response_challenge_sha256"] = digest(challenge)
    else:
        runtime["history_query_invalid_result_count"] = int(
            runtime.get("history_query_invalid_result_count", 0)
        ) + 1


def result_origin_kind(frame: Mapping[str, object]) -> str:
    """Return only the allowlisted origin class of a native result frame."""
    origin = frame.get("origin")
    if isinstance(origin, Mapping):
        kind = origin.get("kind")
    else:
        kind = origin
    if kind is None:
        return "none"
    if kind == "human":
        return "human"
    return "other"


def is_successful_parent_result(frame: object) -> bool:
    """Recognize the SDK's own successful source-turn ResultMessage."""
    if not isinstance(frame, Mapping):
        return False
    if frame.get("type") != "result":
        return False
    if frame.get("subtype") not in {None, "success"}:
        return False
    if frame.get("is_error") is True:
        return False
    return result_origin_kind(frame) in {"none", "human"}


def runtime_observe(expected: Mapping[str, object]) -> dict[str, object]:
    """Run source stop and target-held initialize inside the sandbox."""

    two_domain_phase = expected.get("two_domain_phase")
    if two_domain_phase not in {None, "source"}:
        raise ValueError("target phase uses the isolated target observer")
    mode = expected.get("mode")
    if mode not in {None, STOP_THEN_RESUME_V1}:
        raise ValueError("unknown probe mode")
    v1_mode = mode == STOP_THEN_RESUME_V1
    control_mode = str(expected.get("control_mode", "stopped"))
    if v1_mode and control_mode == "stopped":
        control_mode = "interrupt"
    if control_mode not in {
        "stopped", "interrupt", "crash-left-unfinished",
        "positive-orphan", "terminal-cleared",
    }:
        raise ValueError("unknown source control mode")
    unfinished_mode = control_mode in {
        "crash-left-unfinished", "positive-orphan",
    }
    control_action = {
        "stopped": "stop_task",
        "terminal-cleared": "stop_task",
        "interrupt": "interrupt",
        "crash-left-unfinished": "crash-owned-process-group",
        "positive-orphan": "crash-owned-process-group",
    }[control_mode]
    release_target = bool(expected.get("release_target", False))
    explicit_release = bool(expected.get("explicit_release", False))
    unknown_effect = bool(expected.get("unknown_effect", False))
    if v1_mode and release_target:
        raise ValueError("stop-then-resume-v1 requires explicit release")
    if unknown_effect and (not v1_mode or not explicit_release):
        raise ValueError(
            "unknown-effect negative arm requires stop-then-resume-v1 and explicit release"
        )
    if v1_mode and control_mode != "interrupt":
        raise ValueError("stop-then-resume-v1 requires interrupt control")
    control_entry_before_settle = bool(
        expected.get("control_entry_before_settle", False)
    )
    busy_parent_before_control = bool(
        expected.get("busy_parent_before_control", False)
    )
    if control_entry_before_settle and control_mode != "interrupt":
        raise ValueError(
            "control-entry-before-settle is only valid for interrupt control"
        )
    if busy_parent_before_control and control_mode != "interrupt":
        raise ValueError(
            "busy-parent-before-control is only valid for interrupt control"
        )
    if busy_parent_before_control and control_entry_before_settle:
        raise ValueError(
            "busy-parent-before-control cannot combine with settled-parent arm"
        )

    if two_domain_phase == "source":
        state_root = expected.get("state_root")
        if not isinstance(state_root, str) or state_root != "/opt/state":
            raise ValueError("two-domain source phase requires its fixed state root")
        root = Path(state_root)
    else:
        root = Path(
            tempfile.mkdtemp(prefix="managed-loopback-v1-")
            if v1_mode else "/tmp/managed-loopback"
        )
    work_dir = root / ("workspace" if two_domain_phase == "source" else "work")
    for directory_path in (root / "home", root / "config", root / "xdg", work_dir):
        directory_path.mkdir(parents=True, exist_ok=True)
    def history_snapshot(source_runtime: Mapping[str, object]) -> dict[str, object]:
        source_identity = {
            "session_id": source_runtime.get("session_id"),
            "task_id": source_runtime.get("actual_task_id"),
            "agent_id": source_runtime.get("task_agent_id"),
            "tool_use_id": source_runtime.get("task_tool_use_id"),
            "parent_agent_id": source_runtime.get("parent_agent_id"),
        }
        return capture_runtime_history_records(
            root / "config",
            source_identity=source_identity,
        )

    v1_ledger = StopThenResumeV1Ledger(work_dir) if v1_mode else None
    if v1_ledger is not None:
        v1_ledger.prepare()
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(root / "home"),
        "CLAUDE_CONFIG_DIR": str(root / "config"),
        "XDG_CONFIG_HOME": str(root / "xdg"),
        "ANTHROPIC_API_KEY": DUMMY_API_KEY,
    }
    binary = "/opt/loopback/claude"
    with open(binary, "rb") as stream:
        actual_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual_digest != expected["cli_sha256"]:
        raise RuntimeError("copied selected executable digest mismatch")
    version = subprocess.run(
        [binary, "--version"], env=env, capture_output=True, text=True,
        timeout=15, check=True,
    ).stdout.strip()
    if PINNED_CLI_VERSION not in version:
        raise RuntimeError("selected CLI version is outside the pinned probe")

    gateway = GatewayState(busy_parent_enabled=busy_parent_before_control)
    server = ThreadingHTTPServer(("127.0.0.1", 0), LoopbackHandler)
    server.gateway = gateway  # type: ignore[attr-defined]
    env["ANTHROPIC_BASE_URL"] = (
        "http://127.0.0.1:%d" % server.server_address[1]
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    source: subprocess.Popen[bytes] | None = None
    target: subprocess.Popen[bytes] | None = None
    source_selector = target_selector = None
    source_runtime: dict[str, object] = {
        "init_request": "source-init",
        "stop_request": None,
        "interrupt_request": None,
        "initialize_succeeded": False,
        "session_id": None,
        "frames_seen": 0,
        "unparsed_frames": 0,
        "native_task_events": 0,
        "lifecycle_phase": "source/setup",
        "native_task_evidence": [],
        "native_task_evidence_limit": MAX_NATIVE_TASK_EVIDENCE,
        "native_task_evidence_overflow": False,
        "native_task_observation_sequence": 0,
        "native_task_last_observation": None,
        "native_task_evidence_unknown_reasons": [],
        "native_task_recording_enabled": True,
        "native_hook_recording_enabled": (
            expected.get("observe_native_hooks", False) is True
        ),
        "native_agent_type": str(
            SOURCE_AGENT_NAME
        ),
        "native_hook_evidence": [],
        "native_hook_unknown_reasons": [],
        "native_hook_evidence_overflow": False,
        "lifecycle_provenance": "source-observed",
        "source_identity": None,
        "target_wake_evidence": 0,
        "task_started": False,
        "actual_task_id": None,
        "task_agent_id": None,
        "task_tool_use_id": None,
        "task_terminal_observed": False,
        "source_parent_result_seen": False,
        "source_parent_result_origin": None,
        "parent_settled_at_control_entry": None,
        "control_entry_epoch_started_before_settle": False,
        "busy_parent_control_entry_observed": False,
        "busy_parent_barrier_cleanup_requested": False,
        "successful_result_seen": False,
        "successful_result_session_id": None,
        "successful_result_uuid_digest": None,
        "source_parent_settled_before_control": False,
        "stop_receipt": False,
        "interrupt_receipt": False,
        "stop_sent": False,
        "interrupt_sent": False,
        "stopped_notification": False,
        "tool_terminal": False,
        "tracked_process_seen_before_stop": False,
        "tracked_process_exited_before_cleanup": False,
        "crash_requested": False,
        "crash_parent_process_exited": False,
        "tracked_process_exited_after_crash": False,
        "observed_owned_processes_excluded": False,
        "tracked_sleeper_seen": False,
        "tracked_sleeper_identity_digest": None,
        "tracked_fixture_process_count": 0,
        "control_events": {},
        "read_failed": False,
        "reason_codes": [],
    }
    target_runtime: dict[str, object] = {
        "init_request": "target-init",
        "stop_request": None,
        "initialize_succeeded": False,
        "session_id": None,
        "frames_seen": 0,
        "unparsed_frames": 0,
        "native_task_events": 0,
        "lifecycle_phase": "target/startup",
        "native_task_evidence": [],
        "native_task_evidence_limit": MAX_NATIVE_TASK_EVIDENCE,
        "native_task_evidence_overflow": False,
        "native_task_observation_sequence": 0,
        "native_task_last_observation": None,
        "native_task_evidence_unknown_reasons": [],
        "native_task_recording_enabled": True,
        "native_hook_recording_enabled": (
            expected.get("observe_native_hooks", False) is True
        ),
        "native_agent_type": str(
            SOURCE_AGENT_NAME
        ),
        "native_hook_evidence": [],
        "native_hook_unknown_reasons": [],
        "native_hook_evidence_overflow": False,
        "lifecycle_provenance": "target-observed",
        "source_identity": None,
        "native_task_seed_provenance": "none",
        "target_wake_evidence": 0,
        "startup_observation_active": True,
        "startup_activity_observed": False,
        "startup_activity_kinds": [],
        "startup_unclassified_lifecycle_count": 0,
        "startup_quiet_window_observed": False,
        "startup_parent_result_observed": False,
        "startup_parent_messages_since_launch": 0,
        "startup_child_messages_since_launch": 0,
        "gateway_request_index_at_launch": None,
        "history_query_gate": None,
        "history_query_skipped": False,
        "history_query_skip_reasons": [],
        "history_query_count": 0,
        "source_parent_result_seen": False,
        "source_parent_result_origin": None,
        "successful_result_seen": False,
        "successful_result_session_id": None,
        "successful_result_uuid_digest": None,
        "release_requested": False,
        "release_read_complete": False,
        "control_events": {},
        "read_failed": False,
        "reason_codes": [],
    }
    source_store = {
        "file_count": 0,
        "bytes": 0,
        "path_digest": None,
        "transcript_record_seen": False,
        "task_record_seen": False,
    }
    source_store_before_crash = {
        "file_count": 0,
        "bytes": 0,
        "path_digest": None,
        "transcript_record_seen": False,
        "task_record_seen": False,
    }
    target_hold_snapshot: dict[str, object] = {
        "frames_seen": 0,
        "session_id": None,
        "initialize_succeeded": False,
        "native_task_events": 0,
        "target_wake_evidence": 0,
        "successful_result_seen": False,
        "successful_result_session_id": None,
    }
    history_active_snapshot: dict[str, object] = {}
    history_pre_release_snapshot: dict[str, object] = {}
    history_post_startup_snapshot: dict[str, object] = {}
    tracked_fixture_processes: list[dict[str, object]] = []
    source_alive_before_harness_cleanup = False
    try:
        source = subprocess.Popen(
            [binary] + list(expected["arguments"]), env=env, cwd=work_dir,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        source_selector = selectors.DefaultSelector()
        source_selector.register(source.stdout, selectors.EVENT_READ)
        source_selector.register(source.stderr, selectors.EVENT_READ)
        source_buffers = {source.stdout: bytearray(), source.stderr: bytearray()}
        send_frame(
            source,
            initialize_frame(
                expected,
                "source-init",
                observe_native_hooks=(
                    expected.get("observe_native_hooks", False) is True
                ),
            ),
        )
        read_frames(
            source, source_selector, source_buffers, source_runtime,
            time.monotonic() + 8,
        )
        if source_runtime["initialize_succeeded"]:
            send_frame(source, user_frame())
            active_deadline = time.monotonic() + 15
            process_seen: bool | None = None
            while time.monotonic() < active_deadline:
                read_frames(
                    source, source_selector, source_buffers, source_runtime,
                    time.monotonic() + .2,
                )
                if not tracked_fixture_processes:
                    tracked_fixture_processes = capture_owned_fixture_processes(
                        source.pid
                    )
                    if tracked_fixture_processes:
                        source_runtime["tracked_sleeper_seen"] = True
                        source_runtime["tracked_sleeper_identity_digest"] = digest(
                            "|".join(
                                "%s:%s" % (
                                    identity.get("pid"),
                                    identity.get("starttime"),
                                )
                                for identity in tracked_fixture_processes
                            )
                        )
                        source_runtime["tracked_fixture_process_count"] = len(
                            tracked_fixture_processes
                        )
                process_seen = fixture_processes_alive(tracked_fixture_processes)
                if process_seen is True:
                    source_runtime["tracked_process_seen_before_stop"] = True
                if (
                    source_runtime["task_started"]
                    and source_runtime["actual_task_id"]
                    and gateway.bash_responses
                    and not source_runtime.get("task_terminal_observed")
                    and process_seen is True
                ):
                    break
            active_fixture = bool(
                source_runtime["task_started"]
                and source_runtime["actual_task_id"]
                and gateway.bash_responses
                and not source_runtime.get("task_terminal_observed")
                and process_seen is True
            )
            source_runtime["active_fixture_observed"] = active_fixture
            if v1_ledger is not None and active_fixture:
                history_active_snapshot = history_snapshot(source_runtime)
                v1_ledger.record_pre_stop_facts(
                    parent_identity={
                        "session_id": source_runtime.get("session_id"),
                    },
                    pre_stop_history={
                        "store": observe_store(root / "config"),
                        "source_frames_seen": source_runtime.get("frames_seen"),
                        "gateway_request_count": gateway.request_count,
                    },
                    result_uuid_digest=source_runtime.get(
                        "successful_result_uuid_digest"
                    ),
                )
            if active_fixture:
                control_entry_admitted = not busy_parent_before_control
                if busy_parent_before_control:
                    busy_deadline = time.monotonic() + 15
                    while time.monotonic() < busy_deadline:
                        read_frames(
                            source, source_selector, source_buffers, source_runtime,
                            time.monotonic() + .2,
                        )
                        if not tracked_fixture_processes:
                            tracked_fixture_processes = capture_owned_fixture_processes(
                                source.pid
                            )
                        process_seen = fixture_processes_alive(
                            tracked_fixture_processes
                        )
                        if process_seen is True:
                            source_runtime["tracked_process_seen_before_stop"] = True
                        busy = gateway.busy_parent_snapshot()
                        process_digest = source_runtime.get(
                            "tracked_sleeper_identity_digest"
                        )
                        if (
                            busy.get("barrier_pending") is True
                            and source_runtime["task_started"]
                            and source_runtime["actual_task_id"]
                            and not source_runtime.get("task_terminal_observed")
                            and gateway.bash_responses >= 1
                            and process_seen is True
                            and isinstance(process_digest, str)
                        ):
                            control_entry_admitted = gateway.begin_busy_parent_control_entry(
                                task_id=str(source_runtime["actual_task_id"]),
                                process_identity_digest=process_digest,
                                child_active_pre_entry=True,
                                bash_active_pre_entry=True,
                            )
                            if control_entry_admitted:
                                source_runtime[
                                    "busy_parent_control_entry_observed"
                                ] = True
                                source_runtime["parent_settled_at_control_entry"] = False
                                source_runtime[
                                    "control_entry_epoch_started_before_settle"
                                ] = True
                                break
                    if not control_entry_admitted:
                        source_runtime["reason_codes"].append(
                            "busy-parent-witness-inconclusive"
                        )
                elif control_entry_before_settle:
                    source_runtime["parent_settled_at_control_entry"] = bool(
                        source_runtime.get("source_parent_result_seen")
                    )
                    source_runtime[
                        "control_entry_epoch_started_before_settle"
                    ] = True
                    gateway.begin_control_entry_epoch(
                        parent_settled=bool(
                            source_runtime.get("source_parent_result_seen")
                        )
                    )
                    control_entry_admitted = True
                else:
                    # Let the source parent finish its own human turn while the
                    # child remains active. This separates an already-scheduled
                    # continuation from a request caused by the selected control.
                    settled_deadline = time.monotonic() + 5
                    while time.monotonic() < settled_deadline:
                        read_frames(
                            source, source_selector, source_buffers, source_runtime,
                            time.monotonic() + .2,
                        )
                        process_seen = fixture_processes_alive(tracked_fixture_processes)
                        if process_seen is not True:
                            source_runtime["reason_codes"].append(
                                "child-ended-before-parent-settled"
                            )
                            break
                        if source_runtime.get("source_parent_result_seen"):
                            source_runtime["source_parent_settled_before_control"] = True
                            break
                    if not source_runtime.get("source_parent_settled_before_control"):
                        source_runtime["reason_codes"].append(
                            "parent-settlement-before-control-unresolved"
                        )
                    control_entry_admitted = True
                if control_entry_admitted and unfinished_mode:
                    source_store_before_crash = observe_store(root / "config")
                    source_runtime["records_observed_before_crash"] = bool(
                        source_store_before_crash.get("file_count", 0)
                    )
                    source_runtime["lifecycle_phase"] = "source/drain"
                    gateway.set_phase("source-crash")
                    source_runtime["crash_requested"] = True
                    source_runtime["crash_parent_process_exited"] = (
                        crash_owned_process_group(source)
                    )
                    source_runtime["tracked_process_exited_after_crash"] = (
                        terminate_owned_fixture_processes(
                            tracked_fixture_processes
                        )
                    )
                    source_runtime["observed_owned_processes_excluded"] = bool(
                        source_runtime.get("crash_parent_process_exited")
                        and source_runtime.get("tracked_process_exited_after_crash")
                    )
                elif control_entry_admitted:
                    # Drain/hold policy begins before the selected control.
                    # A parent inference triggered by it is separately counted.
                    source_runtime["lifecycle_phase"] = "source/drain"
                    gateway.set_phase("source-drain")
                    gateway.mark_stop_requested()
                    if control_mode == "interrupt":
                        source_runtime["interrupt_request"] = "source-interrupt"
                        send_frame(source, {
                            "type": "control_request",
                            "request_id": "source-interrupt",
                            "request": {"subtype": "interrupt"},
                        })
                        source_runtime["interrupt_sent"] = True
                    else:
                        source_runtime["stop_request"] = "source-stop"
                        send_frame(source, {
                            "type": "control_request",
                            "request_id": "source-stop",
                            "request": {
                                "subtype": "stop_task",
                                "task_id": source_runtime["actual_task_id"],
                            },
                        })
                        source_runtime["stop_sent"] = True
                    stop_deadline = time.monotonic() + 10
                    while time.monotonic() < stop_deadline:
                        read_frames(
                            source, source_selector, source_buffers, source_runtime,
                            time.monotonic() + .2,
                        )
                        process_seen = fixture_processes_alive(
                            tracked_fixture_processes
                        )
                        if (
                            source_runtime.get("tracked_process_seen_before_stop")
                            and process_seen is False
                        ):
                            source_runtime[
                                "tracked_process_exited_before_cleanup"
                            ] = True
                        control_receipt = bool(
                            source_runtime["stop_receipt"]
                            or source_runtime["interrupt_receipt"]
                        )
                        if (
                            control_receipt
                            and source_runtime["stopped_notification"]
                            and source_runtime.get(
                                "tracked_process_exited_before_cleanup"
                            )
                            and source_runtime["tool_terminal"]
                        ):
                            break
                    if busy_parent_before_control:
                        gateway.release_busy_parent_barrier()
                        source_runtime["busy_parent_barrier_cleanup_requested"] = True
        if gateway.phase == "source":
            source_runtime["lifecycle_phase"] = "source/drain"
            gateway.set_phase("source-drain")
    finally:
        if busy_parent_before_control:
            gateway.release_busy_parent_barrier()
            source_runtime["busy_parent_barrier_cleanup_requested"] = True
        if source_runtime.get("crash_requested"):
            source_runtime["source_parent_process_exited"] = bool(
                source_runtime.get("crash_parent_process_exited")
            )
        else:
            source_alive_before_harness_cleanup = bool(
                source is not None and source.poll() is None
            )
            source_runtime["source_parent_process_exited"] = terminate(source)
        if source_selector is not None:
            source_selector.close()
        source_store = observe_store(root / "config")
        if v1_ledger is not None:
            tracked_excluded = False
            if tracked_fixture_processes:
                tracked_excluded = terminate_owned_fixture_processes(
                    tracked_fixture_processes
                )
            source_runtime["tracked_processes_excluded"] = tracked_excluded
            source_gateway_snapshot = gateway.snapshot()
            v1_ledger.record_source_facts(
                native={
                    "interrupt_sent": bool(source_runtime.get("interrupt_sent")),
                    "interrupt_receipt": bool(
                        source_runtime.get("interrupt_receipt")
                    ),
                    "child_terminal": bool(
                        source_runtime.get("task_terminal_observed")
                    ),
                    "tool_terminal": bool(source_runtime.get("tool_terminal")),
                    "unknown_effects": (
                        ["unknown-effect-arm"] if unknown_effect else []
                    ),
                    "read_failed": bool(source_runtime.get("read_failed")),
                    "unparsed_frames": source_runtime.get("unparsed_frames", 0),
                    "protocol_errors": source_gateway_snapshot.get(
                        "protocol_errors", []
                    ),
                },
                harness={
                    "parent_process_exited": bool(
                        source_runtime.get("source_parent_process_exited")
                    ),
                    "tracked_processes_excluded": tracked_excluded,
                    "pg_kill_observed": source_alive_before_harness_cleanup,
                },
            )
            history_pre_release_snapshot = history_snapshot(source_runtime)

    if two_domain_phase == "source":
        # This early return is the source-domain boundary.  In particular it
        # occurs before any target argument binding, target release, or target
        # Popen in the legacy combined probe below.
        gateway_snapshot = gateway.snapshot()
        v1_snapshot = v1_ledger.snapshot() if v1_ledger is not None else {}
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        raw_session_id = source_runtime.get("session_id")
        source_invocation = expected.get("source_invocation")
        sdk_sidecar_record, sdk_sidecar_diagnostic = native_hook_sdk_sidecar_bridge(
            root / "config",
            source_runtime,
        )
        source_runtime["native_hook_sdk_sidecar_diagnostic"] = (
            sdk_sidecar_diagnostic
        )
        terminal_seed_envelope = native_task_source_terminal_seed_envelope(
            source_runtime,
            parent_uuid=raw_session_id,
            source_invocation=source_invocation,
            sdk_sidecar_record=sdk_sidecar_record,
            sdk_sidecar_reason=(
                str(sdk_sidecar_diagnostic.get("status"))
                if isinstance(sdk_sidecar_diagnostic, Mapping) else None
            ),
        )
        history_evidence: dict[str, object] = {}
        for role in ("parent", "child"):
            record = history_pre_release_snapshot.get(role)
            record = record if isinstance(record, Mapping) else {}
            content = record.get("content")
            history_evidence[role] = {
                "status": record.get("status", "unknown"),
                "attribution": record.get("attribution", "unattributed"),
                "size": len(content) if isinstance(content, bytes) else None,
                "content_sha256": (
                    hashlib.sha256(content).hexdigest()
                    if isinstance(content, bytes) else None
                ),
            }
        source_history_linked = bool(
            history_evidence.get("parent", {}).get("status") == "observed"
            and history_evidence.get("parent", {}).get("attribution") == "observed"
        )
        source_observation = {
            "source_parent_process_exited": bool(
                source_runtime.get("source_parent_process_exited")
            ),
            "active_fixture_observed": bool(
                source_runtime.get("active_fixture_observed")
            ),
            "tracked_fixture_process_count": int(
                source_runtime.get("tracked_fixture_process_count", 0)
            ),
            "tracked_processes_excluded": bool(
                source_runtime.get("tracked_processes_excluded")
            ),
            "tracked_process_exited_before_cleanup": bool(
                source_runtime.get("tracked_process_exited_before_cleanup")
            ),
            "initialize_succeeded": bool(source_runtime.get("initialize_succeeded")),
            "task_started": bool(source_runtime.get("task_started")),
            "task_terminal_observed": bool(source_runtime.get("task_terminal_observed")),
            "interrupt_sent": bool(source_runtime.get("interrupt_sent")),
            "interrupt_receipt": bool(source_runtime.get("interrupt_receipt")),
            "stopped_notification": bool(source_runtime.get("stopped_notification")),
            "tool_terminal": bool(source_runtime.get("tool_terminal")),
            "read_failed": bool(source_runtime.get("read_failed")),
            "unparsed_frames": int(source_runtime.get("unparsed_frames", 0)),
            "reason_codes": sorted(set(source_runtime.get("reason_codes", []))),
            "store": dict(source_store),
            "gateway_request_count": gateway_snapshot.get("request_count", 0),
            "protocol_errors": sorted(set(gateway_snapshot.get("protocol_errors", []))),
            "source_history_snapshot_digest": hashlib.sha256(
                _canonical_json(history_evidence)
            ).hexdigest() if history_pre_release_snapshot else None,
            "identity_linked_parent_history_observed": source_history_linked,
            "history_evidence": history_evidence,
            "v1_release_candidate_ready": bool(v1_snapshot.get("ready_to_resume")),
            "v1_unknown_effect_baseline_valid": bool(
                v1_snapshot.get("unknown_effect_baseline_valid")
            ),
            "v1_unknown_effects": list(v1_snapshot.get("unknown_effects", [])),
            "v1_reason_codes": list(v1_snapshot.get("reason_codes", [])),
            "native_task_terminal_seed_status": terminal_seed_envelope.get("status"),
            "native_task_terminal_seed_digest": terminal_seed_envelope.get("seed_digest"),
            "native_task_terminal_seed_reason_code": terminal_seed_envelope.get(
                "reason_code"
            ),
            "native_task_lifecycle_summary": native_task_lifecycle_summary(
                source_runtime
            ),
            "native_hook_summary": native_hook_evidence_summary(source_runtime),
        }
        source_report_digest_payload = {
            "source_invocation": source_invocation,
            "fixture_owner": expected.get("fixture_owner"),
            "fixture_lineage": expected.get("fixture_lineage"),
            "fixture_runner": expected.get("fixture_runner"),
            "fixture_daemon": expected.get("fixture_daemon"),
            "parent_uuid_digest": digest(raw_session_id),
            "source": source_observation,
            "native_task_terminal_seed_digest": terminal_seed_envelope.get("seed_digest"),
        }
        return {
            "schema": "openrepotools-bite4-source-phase/v1",
            "phase": "source",
            "support_claim": False,
            "target_code_reached": False,
            "source_invocation": source_invocation,
            "fixture_owner": expected.get("fixture_owner"),
            "fixture_lineage": expected.get("fixture_lineage"),
            "fixture_runner": expected.get("fixture_runner"),
            "fixture_daemon": expected.get("fixture_daemon"),
            "source_container_label": expected.get("source_container_label"),
            "private_handoff": {
                "parent_uuid": raw_session_id,
                "parent_uuid_digest": digest(raw_session_id),
                "parent_history_prefix_b64": (
                    base64.b64encode(
                        history_pre_release_snapshot["parent"]["content"]
                    ).decode("ascii")
                    if isinstance(history_pre_release_snapshot, Mapping)
                    and isinstance(history_pre_release_snapshot.get("parent"), Mapping)
                    and isinstance(
                        history_pre_release_snapshot["parent"].get("content"), bytes
                    )
                    and len(history_pre_release_snapshot["parent"]["content"])
                    <= MAX_HISTORY_CONTENT_BYTES
                    else None
                ),
                "native_task_terminal_seed": terminal_seed_envelope,
            },
            "source": source_observation,
            "parent_uuid_seen": isinstance(raw_session_id, str) and bool(raw_session_id),
            "saved_edit_sha256": v1_snapshot.get("edit_hash"),
            "source_phase_report_digest": hashlib.sha256(
                _canonical_json(source_report_digest_payload)
            ).hexdigest(),
        }

    session_id = source_runtime.get("session_id")
    target_runtime["source_identity"] = {
        "session_id": session_id,
        "task_id": source_runtime.get("actual_task_id"),
        "agent_id": source_runtime.get("task_agent_id"),
    }
    if v1_mode:
        source_terminal_seed = source_terminal_lifecycle_seed(source_runtime)
        target_runtime["native_task_source_terminal_seed"] = source_terminal_seed
        target_runtime["native_task_source_terminal_index"] = (
            source_terminal_seed.get("observation_sequence")
            if isinstance(source_terminal_seed, Mapping)
            else None
        )
        target_runtime["native_task_last_observation"] = None
        target_runtime["native_task_seed_provenance"] = (
            "source-terminal-seed"
            if source_terminal_seed is not None else "unavailable"
        )
    target_arguments: list[object] = []
    v1_source_manifest: dict[str, object] = {}
    if v1_ledger is not None and isinstance(session_id, str) and session_id:
        target_arguments = replace_resume_sentinel(
            list(expected["resume_arguments"]), session_id
        )
        v1_snapshot = v1_ledger.snapshot()
        v1_source_manifest = {
            "edit_hash": v1_snapshot.get("edit_hash"),
            "source_parent_identity_digest": v1_snapshot.get(
                "source_parent_identity_digest"
            ),
            "source_native_facts": v1_snapshot.get("source_native_facts", {}),
            "harness_cleanup_facts": v1_snapshot.get(
                "harness_cleanup_facts", {}
            ),
        }
        v1_ledger.bind_resume_spec(
            resume_arguments=target_arguments,
            source_manifest=v1_source_manifest,
        )
    target_launched = False
    target_hold_complete = False
    busy_parent_admitted = (
        not busy_parent_before_control
        or bool(source_runtime.get("busy_parent_control_entry_observed"))
    )
    source_resume_admitted = bool(
        session_id
        and source_runtime.get("source_parent_process_exited")
        and busy_parent_admitted
        and (
            not unfinished_mode
            or (
                source_runtime.get("observed_owned_processes_excluded")
                and source_runtime.get("records_observed_before_crash")
            )
        )
    )
    v1_release: dict[str, object] | None = None
    v1_release_authorized = False
    if v1_ledger is not None:
        v1_release = v1_ledger.request_release(
            explicit=explicit_release,
            unknown_effect=unknown_effect,
        )
        v1_release_authorized = bool(v1_release.get("authorized"))
        source_resume_admitted = bool(
            source_resume_admitted and v1_release_authorized
        )
    if (
        session_id
        and source_runtime.get("source_parent_process_exited")
        and busy_parent_admitted
        and (
            not unfinished_mode
            or (
                source_runtime.get("observed_owned_processes_excluded")
                and source_runtime.get("records_observed_before_crash")
            )
        )
        and (not v1_mode or v1_release_authorized)
    ):
        if v1_mode:
            # The opt-in target is created only after the durable release
            # boundary. Its startup belongs to target-release, not a
            # pre-release target-held window.
            gateway.release_control_entry_epoch(next_phase="target-release")
        else:
            gateway.set_phase("target-held")
        target_start_request_index = gateway.snapshot()["request_count"]
        target_runtime["gateway_request_index_at_launch"] = target_start_request_index
        if not target_arguments:
            target_arguments = replace_resume_sentinel(
                list(expected["resume_arguments"]), str(session_id)
            )
        if v1_ledger is not None:
            v1_ledger.record_launch_intent()
        target = subprocess.Popen(
            [binary] + target_arguments, env=env, cwd=root / "work",
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        target_launched = True
        target_selector = selectors.DefaultSelector()
        target_selector.register(target.stdout, selectors.EVENT_READ)
        target_selector.register(target.stderr, selectors.EVENT_READ)
        target_buffers = {target.stdout: bytearray(), target.stderr: bytearray()}
        try:
            send_frame(
                target,
                initialize_frame(
                    expected,
                    "target-init",
                    observe_native_hooks=(
                        expected.get("observe_native_hooks", False) is True
                    ),
                ),
            )
            read_frames(
                target, target_selector, target_buffers, target_runtime,
                time.monotonic() + 8,
            )
            target_hold_complete = True
            target_hold_snapshot = {
                "frames_seen": target_runtime["frames_seen"],
                "session_id": target_runtime.get("session_id"),
                "initialize_succeeded": target_runtime["initialize_succeeded"],
                "native_task_events": target_runtime["native_task_events"],
                "target_wake_evidence": target_runtime["target_wake_evidence"],
                "control_events": dict(
                    target_runtime.get("control_events", {})
                ),
                "successful_result_seen": target_runtime.get(
                    "successful_result_seen", False
                ),
                "successful_result_session_id": target_runtime.get(
                    "successful_result_session_id"
                ),
                "native_task_lifecycle": native_task_lifecycle_report(
                    target_runtime
                ),
            }
            if v1_mode:
                history_post_startup_snapshot = history_snapshot(source_runtime)
            target_runtime["native_task_recording_enabled"] = False
            if v1_mode:
                launch_snapshot = gateway.snapshot()
                startup_requests = [
                    request
                    for request in launch_snapshot["requests"]
                    if (
                        request.get("request_index", 0) > target_start_request_index
                        and request.get("route") == "/v1/messages"
                    )
                ]
                target_runtime["startup_parent_messages_since_launch"] = sum(
                    1
                    for request in startup_requests
                    if not request.get("agent_header_present")
                )
                target_runtime["startup_child_messages_since_launch"] = sum(
                    1
                    for request in startup_requests
                    if request.get("agent_header_present")
                )
                target_runtime["startup_parent_result_observed"] = bool(
                    target_runtime.get("source_parent_result_seen")
                )
                target_session = target_runtime.get("session_id")
                session_observed = isinstance(target_session, str) and bool(
                    target_session
                )
                target_runtime["startup_quiet_window_observed"] = bool(
                    target.poll() is None
                    and not target_runtime.get("read_failed")
                )
                target_runtime["startup_observation_active"] = False
                startup_gate = assess_v1_history_query_gate({
                    "initialize_succeeded": target_runtime[
                        "initialize_succeeded"
                    ],
                    "target_alive": target.poll() is None,
                    "session_identity_observed": session_observed,
                    "session_identity_mismatch": bool(
                        session_observed
                        and target_session != session_id
                    ),
                    "resume_spec_bound": bool(
                        v1_ledger is not None
                        and v1_ledger.resume_spec_matches(
                            resume_arguments=target_arguments,
                            source_manifest=v1_source_manifest,
                        )
                    ),
                    "source_manifest_bound": bool(
                        v1_ledger is not None
                        and v1_ledger.resume_spec_matches(
                            resume_arguments=target_arguments,
                            source_manifest=v1_source_manifest,
                        )
                    ),
                    "parent_messages_since_launch": target_runtime[
                        "startup_parent_messages_since_launch"
                    ],
                    "child_messages_since_launch": target_runtime[
                        "startup_child_messages_since_launch"
                    ],
                    "native_task_events": target_runtime[
                        "native_task_events"
                    ],
                    "startup_parent_result_observed": target_runtime[
                        "startup_parent_result_observed"
                    ],
                    "generic_startup_activity_observed": target_runtime[
                        "startup_activity_observed"
                    ],
                    "reader_error": bool(target_runtime.get("read_failed")),
                    "unparsed_frames": target_runtime["unparsed_frames"],
                    "unclassified_lifecycle_events": target_runtime[
                        "startup_unclassified_lifecycle_count"
                    ],
                    "quiet_window_observed": target_runtime[
                        "startup_quiet_window_observed"
                    ],
                })
                target_runtime["history_query_gate"] = startup_gate
                if startup_gate["history_query_allowed"]:
                    target_runtime["release_requested"] = True
                    target_runtime["history_query_count"] = 1
                    target_runtime["startup_observation_active"] = False
                    target_runtime["successful_result_seen"] = False
                    target_runtime["successful_result_session_id"] = None
                    target_runtime["successful_result_uuid_digest"] = None
                    send_frame(target, target_release_frame())
                    read_frames(
                        target, target_selector, target_buffers, target_runtime,
                        time.monotonic() + 8,
                    )
                    target_runtime["release_read_complete"] = True
                else:
                    target_runtime["history_query_skipped"] = True
                    target_runtime["history_query_skip_reasons"] = list(
                        startup_gate["reason_codes"]
                    )
            elif release_target and target.poll() is None and target_runtime[
                "initialize_succeeded"
            ]:
                # Legacy strict mode retains its held window and query gate.
                gateway.release_control_entry_epoch(next_phase="target-release")
                target_runtime["release_requested"] = True
                target_runtime["successful_result_seen"] = False
                target_runtime["successful_result_session_id"] = None
                target_runtime["successful_result_uuid_digest"] = None
                send_frame(target, target_release_frame())
                read_frames(
                    target, target_selector, target_buffers, target_runtime,
                    time.monotonic() + 8,
                )
                target_runtime["release_read_complete"] = True
        finally:
            target_runtime["target_process_exited"] = terminate(target)
            target_selector.close()
    elif unfinished_mode and session_id:
        if not source_runtime.get("observed_owned_processes_excluded"):
            source_runtime["reason_codes"].append(
                "owned-writer-exclusion-not-observed"
            )
        if not source_runtime.get("records_observed_before_crash"):
            source_runtime["reason_codes"].append(
                "runtime-records-not-observed-before-crash"
            )
    server.shutdown()
    server.server_close()
    server_thread.join(timeout=2)

    snapshot = gateway.snapshot()
    diagnostics = gateway.diagnostics()
    busy_parent = snapshot["busy_parent"]
    busy_parent_assessment = assess_busy_parent_observation(busy_parent)
    stop_observation = {
        "control_mode": control_mode,
        "control_action": control_action,
        "control_scope": (
            "turn-wide-interrupt-candidate"
            if control_mode == "interrupt"
            else "child-task-stop"
            if control_mode in {"stopped", "terminal-cleared"}
            else "owned-source-process-group-crash"
        ),
        "actual_task_id": source_runtime.get("actual_task_id"),
        "stop_sent": bool(source_runtime.get("stop_sent")),
        "stop_receipt": bool(source_runtime.get("stop_receipt")),
        "interrupt_sent": bool(source_runtime.get("interrupt_sent")),
        "interrupt_receipt": bool(source_runtime.get("interrupt_receipt")),
        "stopped_notification": bool(source_runtime.get("stopped_notification")),
        "tool_terminal": bool(source_runtime.get("tool_terminal")),
        "tracked_process_exited_before_cleanup": bool(
            source_runtime.get("tracked_process_exited_before_cleanup")
        ),
        "source_parent_process_exited": bool(
            source_runtime.get("source_parent_process_exited")
        ),
        "forced_cleanup": not bool(
            source_runtime.get("tracked_process_exited_before_cleanup")
        ),
    }
    stop_assessment = assess_stop_observation(stop_observation)
    control_entry_epoch = gateway.control_entry_snapshot()
    control_entry_assessment = assess_control_entry_observation(
        control_entry_epoch,
        active_fixture_observed=bool(source_runtime.get("active_fixture_observed")),
        source_parent_process_exited=bool(
            source_runtime.get("source_parent_process_exited")
        ),
        target_hold_complete=target_hold_complete,
        cleanup_complete=bool(stop_assessment["control_candidate"]),
        read_failed=bool(
            source_runtime.get("read_failed") or target_runtime.get("read_failed")
        ),
    )
    source_phase = snapshot["route_counts"].get("source", {})
    source_drain_phase = snapshot["route_counts"].get("source-drain", {})
    target_phase = snapshot["route_counts"].get("target-held", {})
    target_release_phase = snapshot["route_counts"].get("target-release", {})
    task_agent_digest = digest(source_runtime.get("task_agent_id"))
    header_correlation = bool(
        task_agent_digest
        and task_agent_digest in gateway.child_agent_decoded_digests
    )
    endpoint_sensor_calibrated = bool(
        source_phase.get("/v1/messages", 0)
        or source_drain_phase.get("/v1/messages", 0)
    )
    source_control_messages = source_drain_phase.get("/v1/messages", 0)
    source_control_model_request_observed = bool(
        source_runtime.get("source_parent_settled_before_control")
        and source_control_messages
    )
    target_monitor_valid = (
        target_launched
        and target_hold_complete
        and target_runtime["initialize_succeeded"] is True
        and endpoint_sensor_calibrated
    )
    target_posts = target_phase.get("/v1/messages", 0)
    target_release_posts = target_release_phase.get("/v1/messages", 0)
    target_release_parent_posts = sum(
        1
        for request in snapshot["requests"]
        if request.get("phase") == "target-release"
        and request.get("route") == "/v1/messages"
        and not request.get("agent_header_present")
    )
    target_release_plain_end_turn = any(
        request.get("phase") == "target-release"
        and request.get("route") == "/v1/messages"
        and not request.get("agent_header_present")
        and request.get("response_kind") == "text-end-turn"
        for request in snapshot["requests"]
    )
    target_hold_assessment = assess_target_hold_observation({
        "hold_complete": target_hold_complete,
        "initialize_succeeded": target_runtime["initialize_succeeded"],
        "source_session_id": session_id,
        "target_session_id": target_hold_snapshot.get("session_id"),
        "messages_posts": target_posts,
        "count_tokens_posts": target_phase.get(
            "/v1/messages/count_tokens", 0
        ),
        "api_hello_requests": target_phase.get("/api/hello", 0),
        "endpoint_sensor_calibrated": endpoint_sensor_calibrated,
        # The stream-json path has no authoritative exact-loader fact; a
        # matching UUID and quiet traffic remain identity/transport facts.
        "authoritative_loader_evidence": False,
    })
    target_model_request_free = (
        target_hold_assessment["model_request_free_observation"] is True
    )
    target_control_events = target_hold_snapshot.get("control_events", {})
    positive_orphan_assessment = assess_positive_orphan_observation({
        "control_mode": control_mode,
        "crash_requested": source_runtime.get("crash_requested"),
        "records_observed_before_crash": source_runtime.get(
            "records_observed_before_crash"
        ),
        "observed_owned_processes_excluded": source_runtime.get(
            "observed_owned_processes_excluded"
        ),
        "source_parent_process_exited": source_runtime.get(
            "source_parent_process_exited"
        ),
        "target_launched": target_launched,
        "target_hold_complete": target_hold_complete,
        "control_events": target_control_events,
        "target_model_request_observed": bool(target_posts),
    })
    terminal_clear_assessment = assess_terminal_clear_observation({
        "control_mode": control_mode,
        "actual_task_id": source_runtime.get("actual_task_id"),
        "stop_receipt": source_runtime.get("stop_receipt"),
        "stopped_notification": source_runtime.get("stopped_notification"),
        "tool_terminal": source_runtime.get("tool_terminal"),
        "tracked_process_exited_before_cleanup": source_runtime.get(
            "tracked_process_exited_before_cleanup"
        ),
        "source_parent_process_exited": source_runtime.get(
            "source_parent_process_exited"
        ),
        "forced_cleanup": not bool(
            source_runtime.get("tracked_process_exited_before_cleanup")
        ),
        "control_events": source_runtime.get("control_events", {}),
        "source_control_messages": source_control_messages,
        "target_launched": target_launched,
        "target_hold_complete": target_hold_complete,
        "target_connect_observed": False,
        "target_initialize_succeeded": target_runtime[
            "initialize_succeeded"
        ],
        "target_session_identity_correlated": bool(
            session_id
            and target_hold_snapshot.get("session_id") == session_id
        ),
        "target_loader_correlated": False,
        "endpoint_sensor_calibrated": endpoint_sensor_calibrated,
        "target_wake_sensor_calibrated": False,
        "target_no_wake_observed": False,
        "target_model_request_free": target_model_request_free,
        "target_wake_evidence": target_hold_snapshot.get(
            "target_wake_evidence", 0
        ),
    })
    source_result_session_id = source_runtime.get(
        "successful_result_session_id"
    )
    target_result_session_id = target_runtime.get(
        "successful_result_session_id"
    )
    target_result_same_source_uuid = bool(
        source_result_session_id
        and target_result_session_id
        and source_result_session_id == target_result_session_id
    )
    release_history = diagnostics.get("target_release_history", {})
    release_history = (
        release_history if isinstance(release_history, Mapping) else {}
    )
    release_history_complete = bool(
        release_history.get("source_marker_present")
        and release_history.get("release_marker_present")
        and release_history.get("agent_tool_use_present")
        and release_history.get("agent_tool_result_present")
    )
    release_continuity_observed = bool(
        release_target
        and target_release_parent_posts >= 1
        and target_release_plain_end_turn
        and release_history_complete
        and target_runtime.get("successful_result_seen")
        and target_result_same_source_uuid
    )
    history_integrity: object = "not-selected"
    if v1_mode:
        history_integrity = {
            "active_to_pre_release": compare_history_content_integrity(
                history_active_snapshot,
                history_pre_release_snapshot,
                before_boundary="active-source",
                after_boundary="source-excluded/pre-release",
            ),
            "pre_release_to_post_startup": compare_history_content_integrity(
                history_pre_release_snapshot,
                history_post_startup_snapshot,
                before_boundary="source-excluded/pre-release",
                after_boundary="post-startup-before-cleanup",
            ),
            "support_claim": False,
        }
    if v1_ledger is not None and target_launched:
        v1_ledger.record_target_facts(
            parent_identity={
                "session_id": target_runtime.get("successful_result_session_id"),
            },
            retained_history=release_history_complete,
            edit_hash=str(v1_ledger.snapshot().get("edit_hash")),
            result_uuid_digest=target_runtime.get(
                "successful_result_uuid_digest"
            ),
            result_identity_observed=bool(
                target_runtime.get("successful_result_seen")
                and target_runtime.get("successful_result_session_id") == session_id
            ),
            retained_history_scope="parent-boundary-markers-only",
        )
    unfinished_child_control = {
        "mode": control_mode,
        "control_action": control_action,
        "active_fixture_observed": bool(
            source_runtime.get("active_fixture_observed")
        ),
        "records_observed_before_crash": (
            bool(source_runtime.get("records_observed_before_crash"))
            if unfinished_mode
            else "not-selected"
        ),
        "records_before_crash_metadata": (
            dict(source_store_before_crash)
            if unfinished_mode
            else "not-selected"
        ),
        "crash_requested": bool(source_runtime.get("crash_requested")),
        "stop_task_sent": bool(source_runtime.get("stop_sent")),
        "source_parent_process_exited": bool(
            source_runtime.get("source_parent_process_exited")
        ),
        "tracked_process_exited_after_crash": (
            bool(source_runtime.get("tracked_process_exited_after_crash"))
            if unfinished_mode
            else "not-selected"
        ),
        "observed_owned_processes_excluded": (
            bool(source_runtime.get("observed_owned_processes_excluded"))
            if unfinished_mode
            else "not-selected"
        ),
        "tracked_sleeper_seen": bool(
            source_runtime.get("tracked_sleeper_seen")
        ),
        "tracked_fixture_process_count": source_runtime.get(
            "tracked_fixture_process_count", 0
        ),
        "writer_exclusion_scope": "source-process-group-and-scripted-sleeper",
        "unfinished_input_left": bool(
            unfinished_mode
            and source_runtime.get("crash_requested")
        ),
        "exact_parent_load": "unknown",
        "internal_wake_evidence": "unknown",
    }
    report = {
        "schema": "lane-managed-loopback/v1",
        "experiment": "synthetic-gateway",
        "gateway_mode": "synthetic-loopback-dummy-api-key",
        "network": "none",
        "host_mounts": [],
        "auth": {
            "kind": "dummy-api-key",
            "real_credentials": False,
            "production_account": False,
        },
        "models": "scripted",
        "support_claim": False,
        "worker_state_clear": (
            terminal_clear_assessment["worker_state_clear"]
            if control_mode in {"stopped", "terminal-cleared"}
            else "not-selected"
        ),
        "orphan_state_clear": (
            terminal_clear_assessment["orphan_state_clear"]
            if control_mode in {"stopped", "terminal-cleared"}
            else "unknown"
        ),
        "verdict": "inconclusive",
        "history_integrity": history_integrity,
        "runtime": {
            "sdk_version": expected["sdk_version"],
            "selected_cli_path": expected["selected_cli"],
            "selected_cli_sha256": expected["cli_sha256"],
            "cli_version": version,
            "arguments": expected["arguments"],
            "resume_arguments_from_sdk": True,
            "mode": "stream-json",
            "control_mode": control_mode,
            "control_action": control_action,
            "control_scope": (
                "turn-wide-interrupt-candidate"
                if control_mode == "interrupt"
                else "child-task-stop"
                if control_mode in {"stopped", "terminal-cleared"}
                else "owned-source-process-group-crash"
            ),
            "release_target": release_target,
            "probe_mode": mode,
            "explicit_release": explicit_release,
            "unknown_effect": unknown_effect,
            "release_boundary_persisted": bool(
                v1_release and v1_release.get("release_persisted")
            ) if v1_mode else "not-selected",
            "control_entry_before_settle": control_entry_before_settle,
            "busy_parent_before_control": busy_parent_before_control,
            "gateway_mode": "synthetic-loopback-dummy-api-key",
            "base_url": "loopback-only",
            "container": "network-none-readonly-no-host-mount",
        },
        "source_fixture": {
            "parent_agent_response": gateway.agent_responses >= 1,
            "agent_tool_name": gateway.source_agent_tool_name,
            "child_agent_header_seen": snapshot["child_agent_header_count"] >= 1,
            "child_bash_response": gateway.bash_responses >= 1,
            "active_bash_process_seen": bool(
                source_runtime.get("tracked_process_seen_before_stop")
            ),
            "tracked_sleeper_seen": bool(
                source_runtime.get("tracked_sleeper_seen")
            ),
            "tracked_sleeper_identity_digest": source_runtime.get(
                "tracked_sleeper_identity_digest"
            ),
            "parent_result_seen": bool(
                source_runtime.get("source_parent_result_seen")
            ),
            "parent_result_origin": source_runtime.get(
                "source_parent_result_origin"
            ),
            "parent_settled_before_control": bool(
                source_runtime.get("source_parent_settled_before_control")
            ),
            "parent_settled_at_control_entry": source_runtime.get(
                "parent_settled_at_control_entry"
            ),
            "control_entry_epoch_started_before_settle": bool(
                source_runtime.get("control_entry_epoch_started_before_settle")
            ),
            "busy_parent_enabled": busy_parent_before_control,
            "busy_parent_control_entry_observed": bool(
                source_runtime.get("busy_parent_control_entry_observed")
            ),
            "busy_parent_barrier": busy_parent,
            "busy_parent_assessment": busy_parent_assessment,
            "request_ceiling": MAX_REQUESTS,
        },
        "source": {
            "session_id_seen": bool(session_id),
            "session_id_digest": digest(session_id),
            "initialize_succeeded": bool(source_runtime["initialize_succeeded"]),
            "task_started": bool(source_runtime.get("task_started")),
            "task_id_seen": bool(source_runtime.get("actual_task_id")),
            "task_id_digest": digest(source_runtime.get("actual_task_id")),
            "task_terminal_observed": bool(
                source_runtime.get("task_terminal_observed")
            ),
            "task_agent_id_seen": bool(source_runtime.get("task_agent_id")),
            "task_agent_id_digest": digest(source_runtime.get("task_agent_id")),
            "agent_header_task_correlation": header_correlation,
            "successful_result_seen": bool(
                source_runtime.get("successful_result_seen")
            ),
            "successful_result_session_id_seen": bool(
                source_runtime.get("successful_result_session_id")
            ),
            "successful_result_session_id_digest": digest(
                source_runtime.get("successful_result_session_id")
            ),
            "native_task_events": source_runtime["native_task_events"],
            "frames_seen": source_runtime["frames_seen"],
            "read_failed": bool(source_runtime.get("read_failed")),
            "store": source_store,
            "control_events": dict(source_runtime.get("control_events", {})),
            "native_task_lifecycle": native_task_lifecycle_report(source_runtime),
        },
        "stop": {
            **stop_observation,
            "task_id_digest": digest(source_runtime.get("actual_task_id")),
            "assessment": stop_assessment,
        },
        "target": {
            "resume_requested": bool(session_id),
            "resume_admitted": source_resume_admitted,
            "initialize_only": "not-applicable" if v1_mode else True,
            "startup_phase": (
                "startup-after-release" if v1_mode else "target-held"
            ),
            "held_window": "not-applicable" if v1_mode else "observed",
            "launched": target_launched,
            "hold_complete": (
                "not-applicable" if v1_mode else target_hold_complete
            ),
            "initialize_succeeded": bool(target_hold_snapshot["initialize_succeeded"]),
            "session_id_seen": bool(target_hold_snapshot.get("session_id")),
            "session_id_digest": digest(target_hold_snapshot.get("session_id")),
            "same_parent_uuid": bool(
                session_id
                and target_hold_snapshot.get("session_id") == session_id
            ),
            "successful_result_seen": bool(
                target_hold_snapshot.get("successful_result_seen")
            ),
            "successful_result_session_id_seen": bool(
                target_hold_snapshot.get("successful_result_session_id")
            ),
            "successful_result_same_source_uuid": (
                False if release_target else target_result_same_source_uuid
            ),
            "exact_parent_load": target_hold_assessment["exact_parent_load"],
            "restored_task_events": "unknown",
            "wake_evidence": "unknown",
            "wire_restore_export_verified": False,
            "observed_frame_count": target_hold_snapshot["frames_seen"],
            "observed_task_event_count": target_hold_snapshot[
                "native_task_events"
            ],
            "observed_wake_subtype_frame_count": target_hold_snapshot[
                "target_wake_evidence"
            ],
            "target_wake_evidence_usable": False,
            "startup_activity_observed": target_runtime.get(
                "startup_activity_observed", "not-selected"
            ) if v1_mode else "not-selected",
            "startup_activity_kinds": target_runtime.get(
                "startup_activity_kinds", []
            ) if v1_mode else "not-selected",
            "history_query_skipped": bool(
                target_runtime.get("history_query_skipped")
            ) if v1_mode else "not-selected",
            "history_query_skip_reasons": list(
                target_runtime.get("history_query_skip_reasons", [])
            ) if v1_mode else "not-selected",
            "history_query_count": target_runtime.get(
                "history_query_count", 0
            ) if v1_mode else "not-selected",
            "history_query_gate": target_runtime.get(
                "history_query_gate"
            ) if v1_mode else "not-selected",
            "native_task_lifecycle": native_task_lifecycle_report(target_runtime),
            "read_failed": bool(target_runtime.get("read_failed")),
            "messages_posts": target_posts,
            "count_tokens_posts": target_phase.get(
                "/v1/messages/count_tokens", 0
            ),
            "api_hello_requests": target_phase.get("/api/hello", 0),
            "model_request_free_observation": target_hold_assessment[
                "model_request_free_observation"
            ],
            "control_events": (
                dict(target_control_events)
                if isinstance(target_control_events, Mapping) else {}
            ),
            "hold_assessment": target_hold_assessment,
            "process_exited": bool(target_runtime.get("target_process_exited")),
        },
        "target_release": {
            "requested": explicit_release if v1_mode else release_target,
            "history_query_requested": bool(
                target_runtime.get("release_requested")
            ) if v1_mode else release_target,
            "history_query_skipped": bool(
                target_runtime.get("history_query_skipped")
            ) if v1_mode else "not-selected",
            "history_query_skip_reasons": list(
                target_runtime.get("history_query_skip_reasons", [])
            ) if v1_mode else "not-selected",
            "history_query_count": target_runtime.get(
                "history_query_count", 0
            ) if v1_mode else "not-selected",
            "startup_phase": (
                "startup-after-release" if v1_mode else "target-held"
            ),
            "phase_messages_posts": target_release_posts,
            "parent_messages_posts": target_release_parent_posts,
            "plain_end_turn_observed": target_release_plain_end_turn,
            "history_verification": dict(release_history),
            "target_successful_result_seen": bool(
                target_runtime.get("successful_result_seen")
            ),
            "source_successful_result_session_id_digest": digest(
                source_result_session_id
            ),
            "target_successful_result_session_id_digest": digest(
                target_result_session_id
            ),
            "target_result_same_source_uuid": target_result_same_source_uuid,
            "eventual_continuity_observed": release_continuity_observed,
            "continuity_scope": (
                "parent-boundary-markers-only"
                if v1_mode else "eventual-history-only"
            ),
            "support_claim": False,
        },
        "endpoint": {
            "source_messages_posts": source_phase.get("/v1/messages", 0),
            "source_drain_messages_posts": source_drain_phase.get(
                "/v1/messages", 0
            ),
            "source_drain_parent_settled_before_control": bool(
                source_runtime.get("source_parent_settled_before_control")
            ),
            "source_drain_causality": (
                "settled-parent-before-control"
                if source_runtime.get("source_parent_settled_before_control")
                else "unresolved"
            ),
            "source_control_messages_posts": source_control_messages,
            "source_control_model_request_observed": (
                source_control_model_request_observed
            ),
            "source_count_tokens_posts": source_phase.get(
                "/v1/messages/count_tokens", 0
            ),
            "endpoint_sensor_calibrated": endpoint_sensor_calibrated,
            "target_route_counts": target_phase,
            "target_release_route_counts": target_release_phase,
            "request_metadata": snapshot["requests"],
            "protocol_errors": sorted(set(snapshot["protocol_errors"])),
        },
        "gateway_diagnostics": diagnostics,
        "busy_parent": {
            "observation": busy_parent,
            "assessment": busy_parent_assessment,
            "support_claim": False,
        },
        "control_entry_epoch": {
            **control_entry_epoch,
            **control_entry_assessment,
            "enabled_by_flag": control_entry_before_settle,
            "busy_parent_enabled_by_flag": busy_parent_before_control,
            "busy_parent": busy_parent,
            "busy_parent_assessment": busy_parent_assessment,
            "worker_state_clear": (
                terminal_clear_assessment["worker_state_clear"]
                if control_mode in {"stopped", "terminal-cleared"}
                else "not-selected"
            ),
            "orphan_state_clear": (
                terminal_clear_assessment["orphan_state_clear"]
                if control_mode in {"stopped", "terminal-cleared"}
                else "unknown"
            ),
            "support_claim": False,
        },
        "unfinished_child_control": unfinished_child_control,
        "positive_orphan": positive_orphan_assessment,
        "terminal_cleared": terminal_clear_assessment,
        "reason_codes": sorted(set(
            stop_assessment["reason_codes"]
            + (["target-session-not-observed"] if not session_id else [])
            + (["target-parent-load-not-proven"] if session_id else [])
            + (["target-monitor-incomplete"] if not target_monitor_valid else [])
            + (["target-model-request-observed"] if target_posts else [])
            + list(target_hold_assessment["reason_codes"])
            + list(positive_orphan_assessment["reason_codes"])
            + list(terminal_clear_assessment["reason_codes"])
            + (["source-control-model-request-observed"]
               if source_control_model_request_observed else [])
            + (
                list(control_entry_assessment["reason_codes"])
                if control_entry_before_settle
                else []
            )
            + (
                list(busy_parent_assessment["reason_codes"])
                if busy_parent_before_control
                else []
            )
            + (["target-release-continuity-not-observed"]
               if release_target and not release_continuity_observed else [])
            + (
                [str(v1_release.get("reason_code"))]
                if v1_release and v1_release.get("reason_code")
                else []
            )
            + (
                list(target_runtime.get("history_query_skip_reasons", []))
                if v1_mode
                else []
            )
            + (["owned-writer-exclusion-not-observed"]
               if unfinished_mode
               and not source_runtime.get("observed_owned_processes_excluded")
               else [])
            + (["runtime-records-not-observed-before-crash"]
               if unfinished_mode
               and not source_runtime.get("records_observed_before_crash")
               else [])
            + list(source_runtime.get("reason_codes", []))
            + snapshot["protocol_errors"]
        )),
    }
    if source_runtime.get("native_hook_recording_enabled") is True:
        report["source"]["native_hook_evidence"] = native_hook_evidence_report(
            source_runtime
        )
        report["target"]["native_hook_evidence"] = native_hook_evidence_report(
            target_runtime
        )
    if v1_ledger is not None:
        report["stop_then_resume_v1"] = v1_ledger.report()
    return report


SELECT_RUNTIME = r"""
import hashlib
import importlib.metadata
import json
from dataclasses import asdict
from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions
from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

EXPECTED_MODEL = "claude-sonnet-4-20250514"
AGENT_NAME = "gate0-worker"
AGENT = AgentDefinition(
    description="Gate zero bounded worker",
    prompt="Run the bounded local tool and remain unfinished until stopped.",
    tools=["Bash"],
    model=EXPECTED_MODEL,
    permissionMode="default",
)
OPTIONS = {
    "tools": ["Agent", "Bash"],
    "allowed_tools": ["Agent", "Bash"],
    "model": EXPECTED_MODEL,
    "permission_mode": "default",
    "agents": {AGENT_NAME: AGENT},
}

async def empty():
    if False:
        yield {}

def build(options, selected):
    transport = SubprocessCLITransport(prompt=empty(), options=options)
    transport._cli_path = selected
    return transport._build_command()[1:]

first = SubprocessCLITransport(prompt=empty(), options=ClaudeAgentOptions(**OPTIONS))
selected = first._find_cli()
fresh = build(ClaudeAgentOptions(**OPTIONS), selected)
resume_options = dict(OPTIONS)
resume_options["resume"] = "__LANE_LOOPBACK_SESSION__"
resume = build(ClaudeAgentOptions(**resume_options), selected)
with open(selected, "rb") as stream:
    sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
agent_config = {
    AGENT_NAME: {key: value for key, value in asdict(AGENT).items()
                 if value is not None}
}
print(json.dumps({
    "sdk_version": importlib.metadata.version("claude-agent-sdk"),
    "selected_cli": selected,
    "cli_sha256": sha256,
    "arguments": fresh,
    "resume_arguments": resume,
    "agent_config": agent_config,
}))
"""


def _select_runtime(sdk_python: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="managed-loopback-select-") as tmp:
        selected = json.loads(run(
            sdk_python,
            "-I",
            "-c",
            SELECT_RUNTIME,
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": tmp,
                "CLAUDE_CONFIG_DIR": tmp,
            },
        ).stdout)
    if selected.get("sdk_version") != PINNED_SDK_VERSION:
        raise RuntimeError("SDK version is outside the pinned probe")
    if (not isinstance(selected.get("selected_cli"), str)
            or not isinstance(selected.get("cli_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", selected["cli_sha256"])):
        raise RuntimeError("SDK did not report an exact selected CLI digest")
    args = selected.get("arguments")
    resume_args = selected.get("resume_arguments")
    if not isinstance(args, list) or not isinstance(resume_args, list):
        raise RuntimeError("SDK launch arguments are malformed")
    required = {
        "--output-format",
        "stream-json",
        "--input-format",
        "stream-json",
        "--model",
        EXPECTED_MODEL,
        "--permission-mode",
        "default",
    }
    if not required.issubset(set(args)):
        raise RuntimeError("SDK launch mode/model/policy changed")
    if not any(value == "--allowedTools,Agent,Bash"
               or (value == "--allowedTools" and index + 1 < len(args)
                   and "Agent" in str(args[index + 1])
                   and "Bash" in str(args[index + 1]))
               for index, value in enumerate(args)):
        raise RuntimeError("SDK did not select the scripted allowed tools")
    if RESUME_SENTINEL not in resume_args and (
        "--resume=" + RESUME_SENTINEL not in resume_args
    ):
        raise RuntimeError("SDK resume arguments lack the exact sentinel")
    if not isinstance(selected.get("agent_config"), dict):
        raise RuntimeError("SDK agent definition was not serialized")
    return selected


def probe(
    sdk_python: str,
    image: str,
    *,
    control_mode: str = "stopped",
    release_target: bool = False,
    control_entry_before_settle: bool = False,
    busy_parent_before_control: bool = False,
    mode: str | None = None,
    explicit_release: bool = False,
    unknown_effect: bool = False,
    observe_native_hooks: bool = False,
) -> dict[str, object]:
    """Run one disposable synthetic-gateway experiment."""

    if control_mode not in {
        "stopped", "interrupt", "crash-left-unfinished",
        "positive-orphan", "terminal-cleared",
    }:
        raise ValueError("unknown source control mode")
    if mode not in {None, STOP_THEN_RESUME_V1}:
        raise ValueError("unknown probe mode")
    if mode is None and (explicit_release or unknown_effect):
        raise ValueError(
            "explicit release flags require stop-then-resume-v1"
        )
    if mode == STOP_THEN_RESUME_V1:
        if release_target:
            raise ValueError(
                "stop-then-resume-v1 uses explicit release, not release-target"
            )
        if unknown_effect and not explicit_release:
            raise ValueError(
                "unknown-effect negative arm requires explicit release"
            )
        if control_mode == "stopped":
            control_mode = "interrupt"
        if control_mode != "interrupt":
            raise ValueError("stop-then-resume-v1 requires interrupt control")
    if control_entry_before_settle and control_mode != "interrupt":
        raise ValueError(
            "control-entry-before-settle is only valid for interrupt control"
        )
    if busy_parent_before_control and control_mode != "interrupt":
        raise ValueError(
            "busy-parent-before-control is only valid for interrupt control"
        )
    if busy_parent_before_control and control_entry_before_settle:
        raise ValueError(
            "busy-parent-before-control cannot combine with settled-parent arm"
        )
    selected = _select_runtime(sdk_python)
    selected = dict(selected)
    selected["control_mode"] = control_mode
    selected["release_target"] = bool(release_target)
    selected["mode"] = mode
    selected["explicit_release"] = bool(explicit_release)
    selected["unknown_effect"] = bool(unknown_effect)
    selected["observe_native_hooks"] = bool(observe_native_hooks)
    selected["control_entry_before_settle"] = bool(control_entry_before_settle)
    selected["busy_parent_before_control"] = bool(busy_parent_before_control)
    image_id = json.loads(run("docker", "image", "inspect", image).stdout)[0]["Id"]
    name = "managed-loopback-" + uuid.uuid4().hex[:12]
    container = run(
        "docker",
        "create",
        "--name",
        name,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "96",
        "--memory",
        "768m",
        "--cpus",
        "1",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=96m",
        "--tmpfs",
        "/opt/loopback:rw,exec,nosuid,nodev,size=256m",
        "--entrypoint",
        "/bin/sleep",
        image_id,
        "180",
    ).stdout.decode().strip()
    removed = False
    try:
        record = json.loads(run("docker", "inspect", container).stdout)[0]
        validate_isolation(record)
        run("docker", "start", container)
        with open(str(selected["selected_cli"]), "rb") as executable:
            run(
                "docker",
                "exec",
                "-i",
                container,
                "sh",
                "-c",
                "cat > /opt/loopback/claude && chmod 500 /opt/loopback/claude",
                stdin=executable,
            )
        source_path = Path(__file__).resolve()
        with source_path.open("rb") as source:
            run(
                "docker",
                "exec",
                "-i",
                container,
                "sh",
                "-c",
                "cat > /opt/loopback/probe.py && chmod 500 /opt/loopback/probe.py",
                stdin=source,
            )
        record = json.loads(run("docker", "inspect", container).stdout)[0]
        validate_isolation(record)
        output = run(
            "docker",
            "exec",
            "-i",
            container,
            "/usr/bin/env",
            "-i",
            "PATH=/usr/local/bin:/usr/bin:/bin",
            "python3",
            "/opt/loopback/probe.py",
            "--runtime",
            "--expected-json",
            json.dumps(selected),
            timeout=MAX_RUNTIME_SECONDS,
        ).stdout
        observed = json.loads(output)
        observed.update({
            "selected_runtime": {
                "sdk_version": selected["sdk_version"],
                "selected_cli": selected["selected_cli"],
                "cli_sha256": selected["cli_sha256"],
                "arguments": selected["arguments"],
                "resume_arguments_from_sdk": True,
                "agent_configured": True,
                "control_mode": control_mode,
                "release_target": bool(release_target),
                "mode": mode,
                "explicit_release": bool(explicit_release),
                "unknown_effect": bool(unknown_effect),
                "observe_native_hooks": bool(observe_native_hooks),
                "control_entry_before_settle": bool(
                    control_entry_before_settle
                ),
                "busy_parent_before_control": bool(
                    busy_parent_before_control
                ),
            },
            "image_id": image_id,
            "network": "none",
            "host_mounts": [],
            "auth": {"kind": "dummy-api-key", "real_credentials": False},
        })
    finally:
        run("docker", "rm", "-f", container, timeout=20)
        removed = True
    observed["sandbox_removed"] = removed
    observed["support_claim"] = False
    return observed


def runtime_two_domain_target(expected: Mapping[str, object]) -> dict[str, object]:
    """Run only the released target in its own persistent state volume."""

    if expected.get("two_domain_phase") != "target":
        raise ValueError("two-domain target phase was not selected")
    if expected.get("state_root") != "/opt/state":
        raise ValueError("two-domain target phase requires its fixed state root")
    parent_uuid = expected.get("source_parent_uuid")
    if not isinstance(parent_uuid, str) or not parent_uuid:
        raise RuntimeError("released exact parent UUID is unavailable")
    parent_uuid_digest = digest(parent_uuid)
    source_invocation_digest = expected.get("source_invocation_digest")
    source_phase_report_digest = expected.get("source_phase_report_digest")
    if (not isinstance(parent_uuid_digest, str)
            or not isinstance(source_invocation_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", source_invocation_digest) is None
            or not isinstance(source_phase_report_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", source_phase_report_digest) is None):
        raise RuntimeError("released native task seed bindings are unavailable")
    try:
        native_task_seed = validate_native_task_source_terminal_seed_envelope(
            expected.get("native_task_source_terminal_seed"),
            expected_parent_uuid_digest=parent_uuid_digest,
            expected_source_invocation_digest=source_invocation_digest,
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError("released native task seed binding is invalid") from exc
    if (native_task_seed.get("status") != "available"
            or native_task_seed.get("seed_digest")
            != expected.get("native_task_source_terminal_seed_digest")):
        raise RuntimeError("released native task seed is unavailable")
    target_profile = expected.get("target_profile")
    history_query_mode = expected.get(
        "history_query_mode", STRICT_HISTORY_QUERY_MODE,
    )
    if history_query_mode not in {
        STRICT_HISTORY_QUERY_MODE,
        TWO_DOMAIN_HISTORY_QUERY_MODE,
    }:
        raise RuntimeError("released history query mode is unsupported")
    if (not isinstance(target_profile, Mapping)
            or target_profile.get("history_query_mode") != history_query_mode
            or target_profile.get("mount_witness_protocol") != "mountinfo-two-stage-v1"
            or not isinstance(target_profile.get("mount_witness_wrapper_sha256"), str)
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(target_profile.get("mount_witness_wrapper_sha256"))
            )
            or target_profile.get("native_task_source_seed_digest")
            != native_task_seed.get("seed_digest")
            or target_profile.get("source_phase_report_digest")
            != source_phase_report_digest
            or target_profile.get("source_invocation_digest")
            != source_invocation_digest):
        raise RuntimeError("released target profile lacks native task seed binding")
    source_identity_digests = native_task_seed.get("source_identity_digests")
    terminal_event = native_task_seed.get("terminal_event")
    if (not isinstance(source_identity_digests, Mapping)
            or not isinstance(terminal_event, Mapping)):
        raise RuntimeError("released native task seed evidence is incomplete")
    resume_arguments = expected.get("resume_arguments")
    if not isinstance(resume_arguments, list):
        raise RuntimeError("released target argument vector is malformed")
    bound_arguments = replace_resume_sentinel(list(resume_arguments), parent_uuid)
    target_spec = {
        "profile": target_profile,
        "image_id": expected.get("image_id"),
        "cli_sha256": expected.get("cli_sha256"),
        "sdk_version": expected.get("sdk_version"),
        "arguments": bound_arguments,
        "agent_config": expected.get("agent_config"),
        "parent_uuid_digest": parent_uuid_digest,
        "native_task_source_seed_digest": native_task_seed.get("seed_digest"),
        "source_phase_report_digest": source_phase_report_digest,
        "source_invocation_digest": source_invocation_digest,
        "history_query_mode": history_query_mode,
    }
    target_spec_digest = hashlib.sha256(_canonical_json(target_spec)).hexdigest()
    if target_spec_digest != expected.get("target_spec_fingerprint"):
        raise RuntimeError("released target specification fingerprint mismatch")
    root = Path("/opt/state")
    config_dir = root / "config"
    workspace_dir = root / "workspace"
    home_dir = root / "home"
    xdg_dir = root / "xdg"
    for directory in (config_dir, workspace_dir, home_dir, xdg_dir):
        info = directory.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise RuntimeError("two-domain target state layout is unsafe")
    manifest = manifest_two_domain_tree(root)
    manifest_digest = hashlib.sha256(_canonical_json(manifest)).hexdigest()
    if manifest_digest != expected.get("target_copy_manifest_digest"):
        raise RuntimeError("released target copy manifest changed before startup")
    files = {
        row.get("path"): row for row in manifest.get("entries", [])
        if isinstance(row, Mapping) and row.get("kind") == "file"
    }
    saved_edit = files.get("workspace/saved-edit.txt")
    if (not isinstance(saved_edit, Mapping)
            or saved_edit.get("sha256") != hashlib.sha256(V1_SAVED_EDIT).hexdigest()):
        raise RuntimeError("two-domain target saved edit is not exact")

    binary = "/opt/loopback/claude"
    with open(binary, "rb") as stream:
        actual_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual_digest != expected.get("cli_sha256"):
        raise RuntimeError("released selected executable digest mismatch")
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home_dir),
        "CLAUDE_CONFIG_DIR": str(config_dir),
        "XDG_CONFIG_HOME": str(xdg_dir),
        "ANTHROPIC_API_KEY": DUMMY_API_KEY,
    }
    version = subprocess.run(
        [binary, "--version"], env=env, capture_output=True, text=True,
        timeout=15, check=True,
    ).stdout.strip()
    if PINNED_CLI_VERSION not in version:
        raise RuntimeError("selected target CLI version is outside the pinned probe")

    gateway = GatewayState()
    # Keep the target held until startup has been observed and a selected
    # history gate authorizes one bounded diagnostic request.
    gateway.set_phase("target-held")
    server = ThreadingHTTPServer(("127.0.0.1", 0), LoopbackHandler)
    server.gateway = gateway  # type: ignore[attr-defined]
    env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:%d" % server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    gateway.begin_startup_observation()
    gateway_server_stopped = False
    gateway_server_fence_complete = False
    target_runtime: dict[str, object] = {
        "init_request": "target-init",
        "stop_request": None,
        "interrupt_request": None,
        "initialize_succeeded": False,
        "session_id": None,
        "frames_seen": 0,
        "unparsed_frames": 0,
        "native_task_events": 0,
        "lifecycle_phase": "target/startup",
        "native_task_evidence": [],
        "native_task_event_origins": [],
        "native_task_evidence_limit": MAX_NATIVE_TASK_EVIDENCE,
        "native_task_evidence_overflow": False,
        "native_task_observation_sequence": 0,
        "native_task_last_observation": None,
        "native_task_evidence_unknown_reasons": [],
        "native_task_recording_enabled": True,
        "lifecycle_provenance": "target-observed",
        "native_hook_recording_enabled": False,
        "native_agent_type": str(SOURCE_AGENT_NAME),
        "native_hook_evidence": [],
        "native_hook_unknown_reasons": [],
        "native_hook_evidence_overflow": False,
        "source_identity": {"session_id": parent_uuid},
        "native_task_source_identity_digests": dict(source_identity_digests),
        "native_task_seed_provenance": "source-terminal-seed",
        "native_task_source_terminal_seed": dict(terminal_event),
        "native_task_source_terminal_index": terminal_event.get("observation_sequence"),
        "target_wake_evidence": 0,
        "startup_observation_active": True,
        "startup_parent_session_id": parent_uuid,
        "startup_activity_observed": False,
        "startup_activity_kinds": [],
        "startup_unclassified_lifecycle_count": 0,
        "startup_other_lifecycle_events": 0,
        "startup_unexpected_frame_count": 0,
        "startup_parent_result_observed": False,
        "successful_result_seen": False,
        "successful_result_session_id": None,
        "successful_result_uuid_digest": None,
        "successful_parent_result_count": 0,
        "startup_result_count": 0,
        "startup_result_origins": [],
        "startup_result_origin_overflow": False,
        "startup_result_error_count": 0,
        "startup_result_parent_session_match_count": 0,
        "startup_result_parent_session_mismatch_count": 0,
        "startup_result_parent_session_id_digest": None,
        "startup_partial_frames": 0,
        "query_partial_frames": 0,
        "history_query_observation_active": False,
        "history_query_parent_session_id": None,
        "history_query_challenge": None,
        "history_query_frame_count": 0,
        "history_query_result_count": 0,
        "history_query_exact_parent_human_result_count": 0,
        "history_query_invalid_result_count": 0,
        "history_query_unexpected_frame_count": 0,
        "history_query_assistant_frame_count": 0,
        "history_query_assistant_message_id_digests": [],
        "history_query_assistant_message_id_missing_count": 0,
        "history_query_error_abort_or_tool_seen": False,
        "stdout_eof": False,
        "history_query_stdout_eof": False,
        "read_failed": False,
        "reason_codes": [],
        "control_events": {},
    }
    target: subprocess.Popen[bytes] | None = None
    selector: selectors.BaseSelector | None = None
    startup_gate: dict[str, object] | None = None
    query_sent = False
    query_read_complete = False
    history_query_gateway_witness: dict[str, object] = {}
    request_arrival_witness: dict[str, object] = {}
    parent_posts = 0
    child_posts = 0
    observed_session: object = None
    same_parent = False
    startup_native_task_lifecycle: dict[str, object] = {}
    query_nonce_digest: str | None = None
    challenge_digest: str | None = None
    try:
        target = subprocess.Popen(
            [binary] + bound_arguments,
            env=env,
            cwd=workspace_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        selector = selectors.DefaultSelector()
        selector.register(target.stdout, selectors.EVENT_READ)
        selector.register(target.stderr, selectors.EVENT_READ)
        buffers = {target.stdout: bytearray(), target.stderr: bytearray()}
        send_frame(
            target,
            initialize_frame(expected, "target-init", observe_native_hooks=False),
        )
        read_frames(
            target, selector, buffers, target_runtime, time.monotonic() + 8,
        )
        target_runtime["startup_partial_frames"] = int(
            bool(buffers.get(target.stdout))
        )
        startup_native_task_lifecycle = snapshot_native_task_lifecycle(
            target_runtime
        )
        startup_request_observation = gateway.close_startup_observation()
        parent_posts = int(startup_request_observation.get("parent_arrival_count", 0))
        child_posts = int(startup_request_observation.get("child_arrival_count", 0))
        observed_session = target_runtime.get("session_id")
        same_parent = isinstance(observed_session, str) and observed_session == parent_uuid
        target_runtime["startup_observation_active"] = False
        target_runtime["startup_quiet_window_observed"] = bool(
            target.poll() is None and not target_runtime.get("read_failed")
        )
        target_runtime["startup_parent_messages_since_launch"] = parent_posts
        target_runtime["startup_child_messages_since_launch"] = child_posts
        target_runtime["startup_parent_result_observed"] = bool(
            target_runtime.get("source_parent_result_seen")
        )
        gate_observation = {
            "initialize_succeeded": target_runtime.get("initialize_succeeded"),
            "target_alive": target.poll() is None,
            "session_identity_observed": isinstance(observed_session, str) and bool(observed_session),
            "session_identity_mismatch": not same_parent,
            "resume_spec_bound": target_spec_digest == expected.get("target_spec_fingerprint"),
            "source_manifest_bound": manifest_digest == expected.get("source_manifest_digest"),
            "parent_messages_since_launch": parent_posts,
            "child_messages_since_launch": child_posts,
            "native_task_events": target_runtime.get("native_task_events"),
            "startup_parent_result_observed": target_runtime.get("startup_parent_result_observed"),
            "generic_startup_activity_observed": target_runtime.get("startup_activity_observed"),
            "reader_error": bool(target_runtime.get("read_failed")),
            "unparsed_frames": target_runtime.get("unparsed_frames"),
            "unclassified_lifecycle_events": target_runtime.get("startup_unclassified_lifecycle_count"),
            "quiet_window_observed": target_runtime.get("startup_quiet_window_observed"),
        }
        if history_query_mode == TWO_DOMAIN_HISTORY_QUERY_MODE:
            startup_gate = assess_two_domain_terminal_task_query_gate({
                "initialize_succeeded": target_runtime.get("initialize_succeeded"),
                "target_alive": target.poll() is None,
                "same_parent_session": same_parent,
                "resume_spec_bound": target_spec_digest == expected.get("target_spec_fingerprint"),
                "source_manifest_bound": manifest_digest == expected.get("source_manifest_digest"),
                "native_task_source_terminal_seed": expected.get(
                    "native_task_source_terminal_seed"
                ),
                "parent_uuid_digest": parent_uuid_digest,
                "source_invocation_digest": source_invocation_digest,
                "startup_native_task_lifecycle": startup_native_task_lifecycle,
                "startup_request_observation": startup_request_observation,
                "startup_activity_observed": target_runtime.get("startup_activity_observed"),
                "reader_error": bool(target_runtime.get("read_failed")),
                "unparsed_frames": target_runtime.get("unparsed_frames"),
                "partial_frames": target_runtime.get("startup_partial_frames"),
                "unclassified_lifecycle_events": target_runtime.get("startup_unclassified_lifecycle_count"),
                "startup_other_lifecycle_events": target_runtime.get(
                    "startup_other_lifecycle_events"
                ),
                "startup_unexpected_frame_count": target_runtime.get(
                    "startup_unexpected_frame_count"
                ),
                "startup_result_count": target_runtime.get("startup_result_count"),
                "startup_result_origins": target_runtime.get("startup_result_origins"),
                "startup_result_origin_overflow": target_runtime.get(
                    "startup_result_origin_overflow"
                ),
                "startup_result_error_count": target_runtime.get("startup_result_error_count"),
                "startup_result_parent_session_match_count": target_runtime.get(
                    "startup_result_parent_session_match_count"
                ),
                "startup_result_parent_session_mismatch_count": target_runtime.get(
                    "startup_result_parent_session_mismatch_count"
                ),
                "startup_result_parent_session_id_digest": target_runtime.get(
                    "startup_result_parent_session_id_digest"
                ),
            })
        else:
            startup_gate = assess_v1_history_query_gate(gate_observation)
        if startup_gate.get("history_query_allowed") is True:
            if history_query_mode == TWO_DOMAIN_HISTORY_QUERY_MODE:
                query_nonce = secrets.token_urlsafe(32)
                challenge = secrets.token_urlsafe(32)
                while challenge == query_nonce:
                    challenge = secrets.token_urlsafe(32)
                gateway.configure_history_query(query_nonce, challenge)
                target_runtime["history_query_observation_active"] = True
                target_runtime["history_query_parent_session_id"] = parent_uuid
                target_runtime["history_query_challenge"] = challenge
                target_runtime["history_query_stdout_eof"] = False
                query_nonce_digest = digest(query_nonce)
                challenge_digest = digest(challenge)
                gateway.set_phase("target-diagnostic-query")
                try:
                    send_frame(
                        target,
                        target_diagnostic_history_query_frame(query_nonce),
                    )
                    query_sent = True
                except (OSError, TypeError, ValueError):
                    target_runtime["read_failed"] = True
                if query_sent:
                    read_frames(
                        target, selector, buffers, target_runtime,
                        time.monotonic() + 8,
                    )
                gateway.close_history_query_window()
            else:
                gateway.set_phase("target-release")
                release_parent_results = int(
                    target_runtime.get("successful_parent_result_count", 0)
                )
                try:
                    send_frame(target, target_release_frame())
                    query_sent = True
                except (OSError, TypeError, ValueError):
                    target_runtime["read_failed"] = True
                if query_sent:
                    read_frames(
                        target, selector, buffers, target_runtime,
                        time.monotonic() + 8,
                    )
                    query_read_complete = bool(
                        int(target_runtime.get("successful_parent_result_count", 0))
                        == release_parent_results + 1
                        and target_runtime.get("successful_result_session_id")
                        == parent_uuid
                    )
        if history_query_mode == TWO_DOMAIN_HISTORY_QUERY_MODE:
            target_runtime["query_partial_frames"] = int(
                bool(buffers.get(target.stdout))
            )
        if history_query_mode == STRICT_HISTORY_QUERY_MODE:
            gateway.set_phase("target-query-closed")
        target_process_exited = terminate(target)
        if history_query_mode == TWO_DOMAIN_HISTORY_QUERY_MODE and selector is not None:
            # Drain complete lines left in the pipe after process-group stop so
            # a late lifecycle event or partial frame invalidates completion.
            read_frames(
                target, selector, buffers, target_runtime, time.monotonic() + 0.35,
            )
            target_runtime["query_partial_frames"] = int(
                bool(buffers.get(target.stdout))
            )
            target_runtime["history_query_observation_active"] = False
            history_query_gateway_witness = gateway.close_history_query_window()
        # Stop accepting requests before taking the final witness. Any request
        # accepted before this fence remains counted and must have completed.
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
        gateway_server_fence_complete = not server_thread.is_alive()
        gateway_server_stopped = gateway_server_fence_complete
        arrivals_drain_deadline = time.monotonic() + 1.0
        while time.monotonic() < arrivals_drain_deadline:
            arrivals_now = gateway.request_arrival_report()
            if arrivals_now.get("in_flight_count") == 0:
                break
            time.sleep(0.01)
        result_snapshot = gateway.snapshot()
        request_arrival_witness = result_snapshot.get("request_arrivals", {})
        if not isinstance(request_arrival_witness, dict):
            request_arrival_witness = {}
        if history_query_mode == TWO_DOMAIN_HISTORY_QUERY_MODE:
            startup_gate = dict(startup_gate or {})
            query_read_complete = bool(
                query_sent
                and target_runtime.get("history_query_result_count") == 1
                and target_runtime.get("history_query_exact_parent_human_result_count") == 1
                and target_runtime.get("history_query_response_challenge_sha256")
                == challenge_digest
                and target_runtime.get("history_query_invalid_result_count") == 0
                and target_runtime.get("history_query_unexpected_frame_count") == 0
                and target_runtime.get("history_query_assistant_frame_count") == 1
                and target_runtime.get("history_query_error_abort_or_tool_seen") is False
                and target_runtime.get("history_query_stdout_eof") is True
                and target_runtime.get("query_partial_frames") == 0
                and target_runtime.get("unparsed_frames") == 0
                and target_runtime.get("read_failed") is False
                and target_runtime.get("native_task_events") == 1
                and target_process_exited is True
                and gateway_server_fence_complete is True
                and history_query_gateway_witness.get("request_count") == 1
                and history_query_gateway_witness.get("request_valid") is True
                and history_query_gateway_witness.get("response_write_count") == 1
                and history_query_gateway_witness.get("response_write_succeeded") is True
                and history_query_gateway_witness.get("response_write_failed") is False
                and history_query_gateway_witness.get("model_expected") is True
                and history_query_gateway_witness.get("dummy_authorization") is True
                and history_query_gateway_witness.get("parent_request") is True
                and history_query_gateway_witness.get("source_prompt_marker_present") is True
                and history_query_gateway_witness.get("same_request_source_agent_history") is True
                and history_query_gateway_witness.get("history_order_valid") is True
                and history_query_gateway_witness.get("source_agent_tool_use_count") == 1
                and history_query_gateway_witness.get("source_agent_tool_result_count") == 1
                and history_query_gateway_witness.get("exact_source_agent_tool_use_count") == 1
                and history_query_gateway_witness.get("all_tool_use_count") == 1
                and history_query_gateway_witness.get("all_tool_result_count") == 1
                and history_query_gateway_witness.get("query_nonce_sha256")
                == query_nonce_digest
                and history_query_gateway_witness.get("response_challenge_sha256")
                == challenge_digest
                and query_nonce_digest != challenge_digest
                and isinstance(
                    history_query_gateway_witness.get("response_message_id_digest"),
                    str,
                )
                and re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(history_query_gateway_witness.get("response_message_id_digest")),
                ) is not None
                and request_arrival_witness.get("arrival_count") == 1
                and request_arrival_witness.get("in_flight_count") == 0
                and request_arrival_witness.get("overflow") is False
                and request_arrival_witness.get("arrival_count_by_phase_route") == {
                    "target-diagnostic-query": {"/v1/messages": 1}
                }
                and (
                    target_runtime.get("history_query_assistant_message_id_digests")
                    == [history_query_gateway_witness.get("response_message_id_digest")]
                    or (
                        target_runtime.get("history_query_assistant_message_id_digests") == []
                        and target_runtime.get(
                            "history_query_assistant_message_id_missing_count"
                        ) == 1
                    )
                )
            )
        target = None
        return {
            "schema": "openrepotools-bite4-target-phase/v1",
            "phase": "target",
            "support_claim": False,
            "target_spec_fingerprint": target_spec_digest,
            "history_query_mode": history_query_mode,
            "source_manifest_digest": manifest_digest,
            "source_parent_uuid_digest": digest(parent_uuid),
            "target_parent_uuid_seen": isinstance(observed_session, str) and bool(observed_session),
            "target_parent_uuid_digest": digest(observed_session),
            "same_parent_uuid": same_parent,
            "initialize_succeeded": bool(target_runtime.get("initialize_succeeded")),
            "startup_gate": startup_gate,
            "history_query_sent": query_sent,
            "history_query_read_complete": query_read_complete,
            "history_query_nonce_sha256": query_nonce_digest,
            "history_query_challenge_sha256": challenge_digest,
            "history_query_gateway_witness": history_query_gateway_witness,
            "request_arrival_witness": request_arrival_witness,
            "gateway_server_fence_complete": gateway_server_fence_complete,
            "startup_request_observation": startup_request_observation,
            "startup_result_count": target_runtime.get("startup_result_count"),
            "startup_result_origins": list(target_runtime.get("startup_result_origins", [])),
            "startup_result_origin_overflow": target_runtime.get(
                "startup_result_origin_overflow"
            ),
            "startup_result_error_count": target_runtime.get(
                "startup_result_error_count"
            ),
            "startup_result_parent_session_match_count": target_runtime.get(
                "startup_result_parent_session_match_count"
            ),
            "startup_result_parent_session_mismatch_count": target_runtime.get(
                "startup_result_parent_session_mismatch_count"
            ),
            "startup_result_parent_session_id_digest": target_runtime.get(
                "startup_result_parent_session_id_digest"
            ),
            "startup_partial_frames": target_runtime.get("startup_partial_frames"),
            "query_partial_frames": target_runtime.get("query_partial_frames"),
            "history_query_result_count": target_runtime.get("history_query_result_count"),
            "history_query_exact_parent_human_result_count": target_runtime.get(
                "history_query_exact_parent_human_result_count"
            ),
            "history_query_response_challenge_sha256": target_runtime.get(
                "history_query_response_challenge_sha256"
            ),
            "history_query_assistant_frame_count": target_runtime.get(
                "history_query_assistant_frame_count"
            ),
            "history_query_assistant_message_id_digests": list(
                target_runtime.get("history_query_assistant_message_id_digests", [])
            ),
            "history_query_assistant_message_id_missing_count": target_runtime.get(
                "history_query_assistant_message_id_missing_count"
            ),
            "history_query_unexpected_frame_count": target_runtime.get(
                "history_query_unexpected_frame_count"
            ),
            "history_query_invalid_result_count": target_runtime.get(
                "history_query_invalid_result_count"
            ),
            "history_query_error_abort_or_tool_seen": target_runtime.get(
                "history_query_error_abort_or_tool_seen"
            ),
            "history_query_stdout_eof": target_runtime.get(
                "history_query_stdout_eof"
            ),
            "startup_activity_observed": bool(target_runtime.get("startup_activity_observed")),
            "startup_activity_kinds": list(target_runtime.get("startup_activity_kinds", [])),
            "startup_unexpected_frame_count": target_runtime.get(
                "startup_unexpected_frame_count"
            ),
            "startup_parent_messages": parent_posts,
            "startup_child_messages": child_posts,
            "frames_seen": target_runtime.get("frames_seen", 0),
            "native_task_events": target_runtime.get("native_task_events", 0),
            "startup_native_task_lifecycle": startup_native_task_lifecycle,
            "unparsed_frames": target_runtime.get("unparsed_frames", 0),
            "read_failed": bool(target_runtime.get("read_failed")),
            "successful_result_seen": bool(target_runtime.get("successful_result_seen")),
            "successful_result_parent_uuid_digest": digest(
                target_runtime.get("successful_result_session_id")
            ),
            "gateway_route_counts": result_snapshot.get("route_counts", {}),
            "gateway_protocol_errors": sorted(set(result_snapshot.get("protocol_errors", []))),
            "target_process_exited": target_process_exited,
        }
    finally:
        if target is not None:
            target_runtime["target_process_exited"] = terminate(target)
        if selector is not None:
            selector.close()
        if not gateway_server_stopped:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)
            gateway_server_fence_complete = not server_thread.is_alive()
            gateway_server_stopped = gateway_server_fence_complete


def _bounded_runtime_error_site(exc: BaseException) -> dict[str, object]:
    """Project only an allowlisted probe function and its source line."""
    candidates: list[tuple[str, int]] = []
    traceback_node = exc.__traceback__
    own_file = os.path.abspath(__file__)
    while traceback_node is not None:
        code = traceback_node.tb_frame.f_code
        if (os.path.abspath(code.co_filename) == own_file
                and code.co_name in RUNTIME_ERROR_SITE_FUNCTIONS
                and type(traceback_node.tb_lineno) is int
                and traceback_node.tb_lineno > 0):
            candidates.append((code.co_name, traceback_node.tb_lineno))
        traceback_node = traceback_node.tb_next
    # runtime_main is the catch boundary, so its traceback line should always
    # be present. Keep a fixed, non-sensitive fallback if an interpreter
    # supplies a truncated traceback.
    function, line = candidates[-1] if candidates else ("runtime_main", 0)
    return {
        "component": "managed_native_loopback",
        "function": function,
        "line": line,
    }


def runtime_main(expected_json: str) -> None:
    """Container entrypoint; print one sanitized JSON observation only."""

    try:
        expected = json.loads(expected_json)
        if isinstance(expected, Mapping) and expected.get("two_domain_phase") == "target":
            observed = runtime_two_domain_target(expected)
        else:
            observed = runtime_observe(expected)
    except Exception as exc:
        observed = {
            "schema": "lane-managed-loopback/v1",
            "gateway_mode": "synthetic-loopback-dummy-api-key",
            "verdict": "inconclusive",
            "support_claim": False,
            "worker_state_clear": "unknown",
            "orphan_state_clear": "unknown",
            "positive_orphan": {
                "status": "unsupported",
                "support_claim": False,
                "reason_codes": ["probe-runtime-failed"],
            },
            "terminal_cleared": {
                "status": "unsupported",
                "support_claim": False,
                "reason_codes": ["probe-runtime-failed"],
            },
            "auth": {"kind": "dummy-api-key", "real_credentials": False},
            "cleanup_verified": False,
            "error_type": type(exc).__name__,
            "error_site": _bounded_runtime_error_site(exc),
            "reason_codes": ["probe-runtime-failed"],
        }
    print(json.dumps(observed, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sdk-python",
        required=True,
        help="existing bench Python that owns the pinned SDK",
    )
    parser.add_argument(
        "--image",
        required=True,
        help="existing local bench image; no image is pulled",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new private report; never a capability grant",
    )
    parser.add_argument(
        "--control-mode",
        choices=(
            "stopped", "interrupt", "crash-left-unfinished",
            "positive-orphan", "terminal-cleared",
        ),
        default="stopped",
        help=(
            "source control arm; interrupt is turn-wide candidate and crash "
            "leaves unfinished input separate"
        ),
    )
    parser.add_argument(
        "--release-target",
        action="store_true",
        help="after the held initialize window, issue one bounded target query",
    )
    parser.add_argument(
        "--mode",
        choices=(STOP_THEN_RESUME_V1,),
        default=None,
        help="opt in to the persisted stop-then-resume-v1 experiment",
    )
    parser.add_argument(
        "--explicit-release",
        action="store_true",
        help="persist the v1 release boundary before creating the target",
    )
    parser.add_argument(
        "--unknown-effect",
        action="store_true",
        help="v1 negative arm: inject an unresolved effect and refuse release",
    )
    parser.add_argument(
        "--observe-native-hooks",
        action="store_true",
        help=(
            "opt in to bounded SubagentStart/Stop observations; this does "
            "not claim native identity or effect safety"
        ),
    )
    parser.add_argument(
        "--control-entry-before-settle",
        action="store_true",
        help=(
            "for interrupt only, start the sticky loopback request epoch "
            "before the existing parent-settlement wait"
        ),
    )
    parser.add_argument(
        "--busy-parent-before-control",
        action="store_true",
        help=(
            "for interrupt only, positively identify and hold the source "
            "Agent continuation before control entry"
        ),
    )
    args = parser.parse_args()
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as report:
        try:
            observed = probe(
                args.sdk_python,
                args.image,
                control_mode=args.control_mode,
                release_target=args.release_target,
                control_entry_before_settle=args.control_entry_before_settle,
                busy_parent_before_control=args.busy_parent_before_control,
                mode=args.mode,
                explicit_release=args.explicit_release,
                unknown_effect=args.unknown_effect,
                observe_native_hooks=args.observe_native_hooks,
            )
        except Exception as exc:
            report.write(json.dumps({
                "schema": "lane-managed-loopback/v1",
                "gateway_mode": "synthetic-loopback-dummy-api-key",
                "verdict": "inconclusive",
                "support_claim": False,
                "worker_state_clear": "unknown",
                "orphan_state_clear": "unknown",
                "positive_orphan": {
                    "status": "unsupported",
                    "support_claim": False,
                    "reason_codes": ["probe-failed"],
                },
                "terminal_cleared": {
                    "status": "unsupported",
                    "support_claim": False,
                    "reason_codes": ["probe-failed"],
                },
                "cleanup_verified": False,
                "auth": {"kind": "dummy-api-key", "real_credentials": False},
                "error_type": type(exc).__name__,
                "reason_codes": ["probe-failed"],
            }) + "\n")
            raise
        json.dump(observed, report, indent=2)
        report.write("\n")
    print(
        "INCONCLUSIVE: synthetic gateway observation only; "
        "native swap support remains unverified"
    )


if __name__ == "__main__":
    if "--runtime" in os.sys.argv:
        try:
            if "--expected-stdin" in os.sys.argv:
                expected_json = sys.stdin.buffer.read(1024 * 1024 + 1)
                if len(expected_json) > 1024 * 1024:
                    raise ValueError("runtime input exceeds the bounded envelope")
                runtime_main(expected_json.decode("utf-8"))
            else:
                index = os.sys.argv.index("--expected-json")
                runtime_main(os.sys.argv[index + 1])
        except Exception as exc:
            print(json.dumps({
                "schema": "lane-managed-loopback/v1",
                "gateway_mode": "synthetic-loopback-dummy-api-key",
                "verdict": "inconclusive",
                "support_claim": False,
                "worker_state_clear": "unknown",
                "orphan_state_clear": "unknown",
                "cleanup_verified": False,
                "error_type": type(exc).__name__,
                "reason_codes": ["probe-runtime-arguments-invalid"],
            }))
    else:
        main()
