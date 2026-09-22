#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded synthetic-gateway probe for a real native Agent child.

This experiment is separate from the no-auth Gate 0 baseline. It uses a
loopback Messages endpoint and a literal dummy API key, never a real profile,
account, network, model service, transcript body, or request body. It can
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
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
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
BUSY_PARENT_BARRIER_TIMEOUT = 15.0
SOURCE_AGENT_NAME = "gate0-worker"
SOURCE_AGENT_TOOL_ID = "toolu-gate0-agent"
SOURCE_TOOL_ID = "toolu-gate0-bash"
SOURCE_PROMPT_MARKER = "Run the bounded native background worker."
TARGET_RELEASE_MARKER = "Continue the bounded native worker after release."
STOP_THEN_RESUME_V1 = "stop-then-resume-v1"
V1_SAVED_EDIT = b"stop-then-resume-v1 deterministic saved edit\n"

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
            "target-release",
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

    def observe_messages_arrival(self) -> int:
        """Observe one loopback POST arrival before body validation or reading."""
        with self.lock:
            self.message_arrival_count += 1
            arrival_index = self.message_arrival_count
            if (
                self.control_entry_epoch_id is not None
                and not self.control_entry_epoch_closed
            ):
                self.control_entry_epoch_inference_attempts += 1
                self.control_entry_epoch_phase_counts[self.phase] = (
                    self.control_entry_epoch_phase_counts.get(self.phase, 0) + 1
                )
            return arrival_index

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
                "method": method,
                "phase": self.phase,
                "route": normalized,
                "agent_header_present": bool(child),
                "model_expected": bool(model_ok),
                "dummy_authorization": bool(authorization_ok),
                "response_kind": response_kind,
            })
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
        prompt_marker: bool = False,
        advertised_tool: str | None = None,
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
    """Reduce native output to statuses/digests, never content or prompts."""
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


def run(*command: str, timeout: int = 45, **kwargs: Any) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, capture_output=True, timeout=timeout, **kwargs)


def sse_payload(
    kind: str,
    response_id: str,
    tool_name: str | None = None,
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

    def write_sse(self, value: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(value)))
        self.end_headers()
        self.wfile.write(value)

    def do_GET(self) -> None:
        endpoint = route(self.path)
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
        arrival_index: int | None = None
        if endpoint == "/v1/messages":
            arrival_index = self.gateway.observe_messages_arrival()
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = MAX_HTTP_BODY + 1
        if length < 0 or length > MAX_HTTP_BODY:
            if endpoint == "/v1/messages":
                self.gateway.record(
                    endpoint,
                    method="POST",
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
            request = json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, ValueError):
            request = {}
        model_ok = isinstance(request, dict) and request.get("model") == EXPECTED_MODEL
        api_key = self.headers.get("x-api-key")
        authorization = self.headers.get("authorization")
        authorization_ok = (
            api_key == DUMMY_API_KEY
            or authorization == "Bearer " + DUMMY_API_KEY
        )
        agent_header = self.headers.get("x-claude-code-agent-id")
        child = bool(agent_header)
        if endpoint == "/v1/messages/count_tokens":
            self.gateway.record(
                endpoint,
                method="POST",
                child=child,
                agent_header=agent_header,
                model_ok=model_ok,
                authorization_ok=authorization_ok,
                response_kind="count-tokens",
            )
            self.write_json(200, {"input_tokens": 1})
            return
        if endpoint != "/v1/messages":
            self.gateway.record(
                endpoint,
                method="POST",
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
        if self.gateway.phase == "target-release":
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
            try:
                self.write_sse(sse_payload(kind, "msg-loopback-%d"
                                           % self.gateway.request_count,
                                           tool_name=(
                                               str(plan["tool_name"])
                                               if plan.get("tool_name") else None
                                           )))
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


def _contains_assistant_or_tool_activity(value: object, depth: int = 0) -> bool:
    if depth > 8:
        return False
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
    subtype = frame.get("subtype") or response.get("subtype")
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


def observe_frame(frame: object, runtime: dict[str, object]) -> None:
    """Consume one native frame, retaining only lifecycle facts/digests."""

    if not isinstance(frame, Mapping):
        runtime["unparsed_frames"] = int(runtime["unparsed_frames"]) + 1
        return
    runtime["frames_seen"] = int(runtime["frames_seen"]) + 1
    _observe_v1_startup_frame(frame, runtime)
    response = frame.get("response")
    response = response if isinstance(response, Mapping) else {}
    subtype = frame.get("subtype") or response.get("subtype")
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
    if subtype in {
        "task_started", "task_progress", "task_updated", "task_notification"
    }:
        runtime["native_task_events"] = int(runtime["native_task_events"]) + 1
    task_id = frame.get("task_id")
    if subtype == "task_started" and task_id and frame.get("task_type") == "local_agent":
        if str(task_id) != runtime.get("actual_task_id"):
            runtime["task_terminal_observed"] = False
        runtime["task_started"] = True
        runtime["actual_task_id"] = str(task_id)
        agent_id = find_value(frame, ("agent_id",))
        runtime["task_agent_id"] = str(agent_id) if agent_id else None
    if (runtime.get("actual_task_id") and task_id == runtime.get("actual_task_id")
            and subtype == "task_notification" and frame.get("status") == "stopped"):
        # A stopped task is not automatically a stopped Bash tool.
        runtime["stopped_notification"] = True
    if (
        runtime.get("actual_task_id")
        and task_id == runtime.get("actual_task_id")
        and subtype == "task_notification"
        and frame.get("status") in {
            "stopped", "completed", "failed", "cancelled", "error",
        }
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


def initialize_frame(expected: Mapping[str, object], request_id: str) -> dict[str, object]:
    """Match the pinned Python SDK initialize shape for configured agents."""

    return {
        "type": "control_request",
        "request_id": request_id,
        "request": {
            "subtype": "initialize",
            "hooks": None,
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

    root = Path(
        tempfile.mkdtemp(prefix="managed-loopback-v1-")
        if v1_mode else "/tmp/managed-loopback"
    )
    for name in ("home", "config", "xdg", "work"):
        (root / name).mkdir(parents=True, exist_ok=True)
    v1_ledger = StopThenResumeV1Ledger(root / "work") if v1_mode else None
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
        "target_wake_evidence": 0,
        "task_started": False,
        "actual_task_id": None,
        "task_agent_id": None,
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
    tracked_fixture_processes: list[dict[str, object]] = []
    source_alive_before_harness_cleanup = False
    try:
        source = subprocess.Popen(
            [binary] + list(expected["arguments"]), env=env, cwd=root / "work",
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,
        )
        source_selector = selectors.DefaultSelector()
        source_selector.register(source.stdout, selectors.EVENT_READ)
        source_selector.register(source.stderr, selectors.EVENT_READ)
        source_buffers = {source.stdout: bytearray(), source.stderr: bytearray()}
        send_frame(source, initialize_frame(expected, "source-init"))
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

    session_id = source_runtime.get("session_id")
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
            send_frame(target, initialize_frame(expected, "target-init"))
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
            }
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


def runtime_main(expected_json: str) -> None:
    """Container entrypoint; print one sanitized JSON observation only."""

    try:
        observed = runtime_observe(json.loads(expected_json))
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
