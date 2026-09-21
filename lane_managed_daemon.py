#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Small persistent supervisor façade for the managed control transport.

The command named ``lane-managed`` owns framing, socket permissions, and the
single-loop server.  This module is the importable supervisor seam.  Keeping
the first slice deliberately narrow is useful: status can be observed through
the production transport while lifecycle mutations remain refused until their
durable controller paths are wired in.

No optional SDK or profile implementation is imported here.  A caller may
inject a controller object exposing the exact synchronous or asynchronous
``status()`` method used by the controller boundary.
"""

from __future__ import annotations

import asyncio
import argparse
import copy
import hashlib
import importlib.machinery
import importlib.util
import inspect
import json
import math
import os
import re
import stat
import subprocess
import shutil
import sys
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional, Sequence

from lane_managed_swap import (
    NativeSwapContractError,
    validate_release_authorization as _validate_native_swap_authorization,
    validate_release_binding as _validate_native_swap_release_binding,
)


MAX_FRAME_BYTES = 1024 * 1024
CONNECT_TIMEOUT = 5.0
OPERATION_TIMEOUT = 120.0
PROCESS_IDENTITY_TIMEOUT = 1.0
# Version 1 was the superseded independent child-runner/mailbox prototype.
# The daemon admits only the native coordinator-lineage wire boundary; old
# records are migration inputs, never compatibility aliases.
SCHEMA_VERSION = 2
SCHEMA_ARCHITECTURE = "native-coordinator-lineage"
NATIVE_SCHEMA_VERSION = SCHEMA_VERSION
NATIVE_ARCHITECTURE = SCHEMA_ARCHITECTURE
MAX_START_TOKEN_BYTES = 256
PROJECTION_TIMEOUT = 5.0
DISPATCH_PUMP_TIMEOUT = 5.0
DISPATCH_PUMP_MAX_ITERATIONS = 32
# A released lane with a busy recipient remains eligible for later delivery.
# The persistent pump sleeps between fresh runtime reads so this is an event
# wake with a bounded idle recheck, not a tight polling loop.  Client status is
# intentionally not part of this wake path.
DISPATCH_WAKE_INTERVAL = 0.25

# The public protocol is intentionally not treated as implemented merely by
# naming an operation.  Each route below is admitted only when its exact
# durable controller boundary is present; unknown aliases and body fields fail
# closed.
_STATUS_OPERATION = "status"
_START_OPERATION = "start"
_RELEASE_OPERATION = "release"
_SWAP_OPERATION = "swap"
_RECOVER_OPERATION = "recover"
NATIVE_ADMISSION_OPERATION = "native-admission-intent"
_NATIVE_ADMISSION_OPERATION = NATIVE_ADMISSION_OPERATION
# One exact injected controller seam.  A state-only writer is deliberately
# not an acceptable fallback: the controller must validate its live fence and
# commit the pending admission/claim/policy in the same durable transaction.
_NATIVE_ADMISSION_AUTHORITY_METHOD = "persist_native_admission"
# Native stop remains an internal adapter/controller seam.  It deliberately
# has no public request operation: the SDK connection supplies the complete
# frame and the controller owns identity, admission, claim, and fence checks.
_NATIVE_STOP_INTENT_AUTHORITY_METHOD = "persist_native_stop_intent"
_NATIVE_STOP_EVIDENCE_AUTHORITY_METHOD = "persist_native_stop_evidence"
_NATIVE_STOP_INTENT_TYPE = "native-stop-intent"
_NATIVE_STOP_EVIDENCE_TYPE = "native-stop-evidence"
# Coordinator-wide interrupt persistence is a separate internal transaction;
# it is not a collection of native task stops and has no public wire route.
_COORDINATOR_INTERRUPT_INTENT_AUTHORITY_METHOD = "persist_coordinator_interrupt_intent"
_COORDINATOR_INTERRUPT_EVIDENCE_AUTHORITY_METHOD = "persist_coordinator_interrupt_evidence"
_COORDINATOR_INTERRUPT_INTENT_TYPE = "coordinator-interrupt-intent"
_COORDINATOR_INTERRUPT_EVIDENCE_TYPE = "coordinator-interrupt-evidence"
# Native swap release authorization is a private runner callback.  It is not
# a public operation/body field and has one exact controller method; probing a
# legacy alias here would turn an unsupported native path into an authority
# grant.
_NATIVE_SWAP_RELEASE_AUTHORITY_METHOD = "authorize_native_swap_release"
_NATIVE_SWAP_RELEASE_TYPE = "native-swap-release-authorize"
# Native child observations are a private producer callback.  They retain
# the runner's exact joined observation, but never become a child route,
# launch, release, or quiescence authority at the daemon boundary.
_NATIVE_CHILD_OBSERVATION_AUTHORITY_METHOD = "persist_native_child_observation"
_NATIVE_CHILD_OBSERVATION_TYPE = "native-child-observation"
_NATIVE_CHILD_OBSERVATION_FRAME_KEYS = frozenset({
    "type", "participant_id", "session_id", "runner_instance_id",
    "observation",
})
_NATIVE_CHILD_OBSERVATION_KEYS = frozenset({
    "schema_version", "architecture", "record_kind", "observation_id",
    "source_identity", "context_binding_digest", "claim_digest",
    "observation_watermark", "terminal_outcome", "child",
})
_NATIVE_CHILD_SOURCE_IDENTITY_KEYS = frozenset({
    "owner_generation", "lineage_id", "lineage_generation", "session_uuid",
    "runner_incarnation", "invocation_id",
})
_NATIVE_CHILD_PROJECTION_KEYS = frozenset({
    "admission_id", "tool_use_id", "agent_id", "task_id", "parent_agent_id",
    "invocation_id", "lineage_incarnation", "trusted_definition_digest",
    "start_watermark", "task_start_event", "status", "terminal_watermark",
    "active_tool_ids", "uncertain_tool_ids", "unresolved_effect_ids",
})
_NATIVE_CHILD_TASK_START_KEYS = frozenset({
    "event_uuid", "watermark", "task_type",
})
_NATIVE_CHILD_OBSERVATION_ACK_KEYS = frozenset({
    "recorded", "observation_id", "observation_digest", "child_run_id",
    "observation_watermark",
})
_NATIVE_CHILD_TERMINAL_OUTCOMES = frozenset({
    "completed", "stopped", "failed", "cancelled", "unknown",
})
_NATIVE_CHILD_MAX_INVENTORY = 256
# Independent child runners had their own UUID/mailbox lifecycle.  Native
# Agent/Task children are admitted through the coordinator lineage, so these
# operation names remain explicit refusal paths until that integration is
# available rather than being forwarded to the legacy controller.
_OBSOLETE_OPERATIONS = frozenset({"add-worker", "complete-worker"})

_START_BODY_KEYS = frozenset({"coordinator", "participants", "runner_specs"})
_ADD_WORKER_BODY_KEYS = frozenset({"participant", "runner_spec"})
_COMPLETE_WORKER_BODY_KEYS = frozenset({"participant_id"})
_SWAP_BODY_KEYS = frozenset({"profile", "runner_specs"})
_CTX_BODY_KEYS = frozenset({"checkpoint", "worker_policy"})
_HANDOFF_BODY_KEYS = frozenset({"checkpoint"})
_SHUTDOWN_BODY_KEYS = frozenset()
_UNENROLL_BODY_KEYS = frozenset()
_RECOVER_BODY_KEYS = frozenset({"operation_id"})
_STATUS_BODY_KEYS = frozenset()
_SUBMIT_BODY_KEYS = frozenset({
    "recipient_id", "payload_ref", "sender_id", "task_id",
})
# This is the one runner-to-controller pre-allow record.  It mirrors the
# adapter's durable admission projection, but deliberately has no child
# session/runner/mailbox/process identity or caller-owned claim/policy field.
# The controller must derive those facts from its current native fence and
# trusted definition index before writing anything.
_NATIVE_ADMISSION_BODY_KEYS = frozenset({
    "admission_id", "tool_use_id", "agent_type", "invocation_id", "parent",
    "custom_definition", "definition_digest", "trusted_definition_digest",
    "watermark", "owner_generation", "lineage_id", "runner_incarnation",
    "launch_completed",
})
_NATIVE_ADMISSION_REQUIRED_KEYS = frozenset(_NATIVE_ADMISSION_BODY_KEYS)
_NATIVE_ADMISSION_PARENT_KEYS = frozenset({
    "session_id", "agent_id", "invocation_id", "prompt_id",
})
_NATIVE_ADMISSION_PARENT_REQUIRED_KEYS = frozenset({
    "session_id", "invocation_id",
})
_NATIVE_ADMISSION_ACK_FIELDS = (
    "admission_id", "owner_generation", "lineage_id", "runner_incarnation",
    "invocation_id", "tool_use_id", "trusted_definition_digest",
)
_NATIVE_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_NATIVE_ADMISSION_DEFINITION_FORBIDDEN_KEYS = frozenset({
    "session_id", "session_uuid", "runner_instance_id", "process_group_id",
    "mailbox_id", "pid", "agent_id", "task_id", "tool_use_id",
    "invocation_id", "owner_generation", "lineage_id", "runner_incarnation",
    "claim", "claim_ref", "policy", "fence", "accepted", "ack", "evidence",
    "runtime", "process", "runner", "mailbox",
})
_PARTICIPANT_KEYS = frozenset({
    "participant_id", "session_id", "session_uuid", "role", "parent_id",
    "task_id", "mailbox_id", "kind", "state", "writer_claim", "read_only",
    "background", "detached", "model", "permission_mode", "fingerprint",
    "metadata", "session_name", "bound_lane",
})
_PARTICIPANT_REQUIRED_KEYS = frozenset({
    "participant_id", "session_id", "role", "parent_id", "task_id",
    "mailbox_id", "kind", "state", "writer_claim", "read_only", "background",
    "detached", "model", "permission_mode", "fingerprint", "metadata",
})
_CLAIM_KEYS = frozenset({"participant_id", "worktree", "repository", "state", "lane", "metadata"})
_RUNNER_SPEC_KEYS = frozenset({
    "participant_id", "session_id", "mode", "resume", "fresh",
    "supported_models", "role", "parent_id", "task_id",
    "session_name", "bound_lane",
    "profile_name", "profile_family", "account_email", "config_dir",
    "workspace", "worktree", "cwd", "transcript_store", "transcript_path",
    "transcript_project", "model", "effort", "tools", "permission_mode",
    "permissions", "fingerprint", "launch_flags", "flags", "max_turns",
    "max_budget_usd",
})
_EVIDENCE_KEYS = frozenset({
    "evidence", "runtime", "process", "process_group", "process_group_id",
    "process_start_token", "runner_instance_id", "ack", "acknowledgement",
    "proof", "no_send", "no_send_proof", "transport_proof", "live_sdk",
    "live_capability", "accepted", "sent", "ready", "quiescent",
})
_NORMALIZED_EVIDENCE_KEYS = frozenset(
    key.casefold().replace("-", "_") for key in _EVIDENCE_KEYS
)

# The native dispatch-binding acknowledgement keeps the strict lineage
# context separate from the mutable, operation-scoped reservation.  The
# controller owns the committed wrapper; the daemon validates its exact
# response before returning it to the SDK adapter.
_RESERVATION_BINDING_REQUIRED_KEYS = frozenset({
    "schema_version", "architecture", "reservation_version",
    "reservation_id", "operation_id", "owner_generation", "daemon_id",
    "participant_id", "session_id", "runner_incarnation", "lineage_id",
    "lineage_generation", "prior_invocation_id", "next_invocation_id",
    "prior_mailbox_id", "next_mailbox_id", "prior_watermark",
    "definitions_digest", "permissions_digest",
    "claim_digest", "binding_digest",
})
_RESERVATION_BINDING_OPTIONAL_KEYS = frozenset({
    "state", "terminal_watermark", "next_watermark", "terminal_proof",
    "terminal_proof_digest",
})
_RESERVATION_BINDING_KEYS = frozenset(
    _RESERVATION_BINDING_REQUIRED_KEYS | _RESERVATION_BINDING_OPTIONAL_KEYS
)
_RESERVATION_BINDING_RESPONSE_KEYS = frozenset({
    "state", "terminal_watermark", "next_watermark", "terminal_proof",
    "terminal_proof_digest",
})
_RESERVATION_TERMINAL_PROOF_KEYS = frozenset({
    "parent_result", "roster", "roster_digest", "observation_watermark",
    "uncertainty", "overflow",
})
_RESERVATION_PARENT_RESULT_KEYS = frozenset({
    "session_id", "invocation_id", "message_id", "result_watermark",
    "reader_drained_watermark",
})
_RESERVATION_ROSTER_KEYS = frozenset({
    "parent_state", "children", "pending_admission_ids", "pending_task_ids",
    "parent_active_tool_ids", "parent_uncertain_tool_ids",
    "parent_unresolved_effect_ids", "descendant_ids",
})


class DaemonError(RuntimeError):
    """Stable refusal raised by the importable supervisor boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.message = str(message)
        super().__init__(self.message)


def _error(code: str, message: str) -> DaemonError:
    return DaemonError(code, message)


def _bounded_id(value: Any, label: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise _error("invalid", "%s is invalid" % label)
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise _error("invalid", "%s is invalid" % label)
    if size > maximum:
        raise _error("invalid", "%s is too long" % label)
    return value


def _process_start_token(pid: int) -> Optional[str]:
    """Return the current process incarnation token, or ``None``.

    Linux exposes a monotonic start tick in ``/proc/<pid>/stat``.  macOS and
    other POSIX systems commonly expose a stable ``lstart`` value through
    ``ps``.  Both reads are bounded and shell-free; an unavailable or
    malformed answer remains unknown rather than becoming weak identity
    evidence.
    """

    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return None
    if os.name == "posix":
        try:
            raw = Path("/proc/%d/stat" % pid).read_text(encoding="utf-8")
            # The command name is parenthesized and may contain spaces.  The
            # fields after the final close parenthesis begin at field 3;
            # process start time is field 22, offset 19 in that suffix.
            suffix = raw.rsplit(")", 1)[-1].split()
            if len(suffix) > 19 and re.fullmatch(r"[0-9]+", suffix[19]):
                return suffix[19]
        except (OSError, UnicodeError, ValueError):
            pass
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            check=False,
            timeout=PROCESS_IDENTITY_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if getattr(result, "returncode", 1) != 0:
        return None
    output = getattr(result, "stdout", None)
    if not isinstance(output, str):
        return None
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    token = lines[0]
    if token in {"?", "-"} or len(token) > MAX_START_TOKEN_BYTES or "\x00" in token:
        return None
    return token


def _current_process_identity() -> tuple[int, str, int]:
    """Capture this supervisor's PID, incarnation token, and process group."""

    pid = os.getpid()
    token = _process_start_token(pid)
    if token is None:
        raise _error("unknown", "current supervisor process identity is unavailable")
    getpgid = getattr(os, "getpgid", None)
    if not callable(getpgid):
        raise _error("unknown", "current supervisor process group is unavailable")
    try:
        pgid = getpgid(pid)
    except (OSError, ValueError):
        raise _error("unknown", "current supervisor process group is unavailable")
    if isinstance(pgid, bool) or not isinstance(pgid, int) or pgid <= 0:
        raise _error("unknown", "current supervisor process group is unavailable")
    return pid, token, pgid


def _current_process_domain() -> str:
    """Return the exact native PID domain used by managed-state discovery."""

    # Linux can distinguish a PID reused in a foreign namespace only when the
    # machine and PID-namespace identities are carried with the durable
    # endpoint.  Keep the derivation local to this supervisor; an inherited
    # environment hint is not process evidence.  Non-Linux supported hosts
    # use the state layer's explicit native domain convention.
    if sys.platform.startswith("linux"):
        try:
            machine_id = Path("/etc/machine-id").read_text(encoding="ascii").strip()
            namespace = os.readlink("/proc/self/ns/pid").strip()
        except (OSError, UnicodeError, ValueError):
            raise _error("unknown", "current supervisor process domain is unavailable")
        if (
            not machine_id
            or any(character not in "0123456789abcdefABCDEF" for character in machine_id)
            or not namespace.startswith("pid:[")
            or not namespace.endswith("]")
        ):
            raise _error("unknown", "current supervisor process domain is unavailable")
        return "linux:%s:%s" % (machine_id, namespace)
    return "native"


def _bounded_wire(value: Any, label: str) -> None:
    """Require JSON-shaped input that fits one bounded control frame."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise _error("invalid", "%s is not valid JSON" % label)
    if len(encoded) > MAX_FRAME_BYTES:
        raise _error("invalid", "%s exceeds the one MiB bound" % label)


async def _await_bounded(value: Any, deadline: float, label: str) -> Any:
    """Await one runtime/controller call without crossing its absolute bound."""

    if not inspect.isawaitable(value):
        return value
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        close = getattr(value, "close", None)
        if callable(close):
            close()
        raise _error("timeout", "%s deadline exceeded" % label)
    try:
        return await asyncio.wait_for(value, timeout=remaining)
    except asyncio.TimeoutError:
        raise _error("timeout", "%s deadline exceeded" % label)


def _strict_object(value: Any, allowed: frozenset[str],
                   required: frozenset[str], label: str) -> dict[str, Any]:
    """Copy one canonical object after rejecting aliases and unknown keys."""

    if not isinstance(value, Mapping):
        raise _error("invalid", "%s must be an object" % label)
    keys = list(value.keys())
    if any(not isinstance(key, str) for key in keys):
        raise _error("invalid", "%s contains a non-string key" % label)
    keyset = set(keys)
    extra = keyset.difference(allowed)
    if extra:
        raise _error("invalid", "%s contains an unsupported field" % label)
    missing = required.difference(keyset)
    if missing:
        raise _error("invalid", "%s is missing a required field" % label)
    return dict(value)


def _reject_evidence_keys(value: Any, label: str) -> None:
    """Reject public nested runtime/evidence claims before controller entry."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise _error("invalid", "%s contains a non-string key" % label)
            normalized_key = key.casefold().replace("-", "_")
            if normalized_key in _NORMALIZED_EVIDENCE_KEYS:
                raise _error("unsupported", "%s contains a runtime/evidence field" % label)
            _reject_evidence_keys(item, "%s.%s" % (label, key))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _reject_evidence_keys(item, label)


def _optional_bounded_text(value: Any, label: str) -> Optional[str]:
    if value is None:
        return None
    return _bounded_id(value, label)


def resolve_payload_reference(payload_ref: Any) -> str:
    """Resolve one owner-private file reference to ephemeral UTF-8 text.

    The durable controller stores only the opaque reference.  This production
    resolver is deliberately narrower than a general URI/file loader: only
    ``file:/absolute/path`` is accepted, and the final object is opened
    without following a symlink, rechecked through its descriptor, and read
    into a bounded transient value.  No resolved text is returned to durable
    state by this module.
    """

    if not isinstance(payload_ref, str):
        raise _error("invalid", "payload_ref must be an opaque string reference")
    _bounded_id(payload_ref, "payload_ref", MAX_FRAME_BYTES)
    if not payload_ref.startswith("file:/") or payload_ref.startswith("file://"):
        raise _error("unsupported", "payload reference scheme is unsupported")
    raw_path = payload_ref[len("file:"):]
    if not raw_path or "\x00" in raw_path:
        raise _error("invalid", "payload file path is invalid")
    path = Path(raw_path)
    if not path.is_absolute():
        raise _error("invalid", "payload file path must be absolute")
    try:
        initial = os.lstat(str(path))
    except (FileNotFoundError, NotADirectoryError):
        raise _error("invalid", "payload file does not exist")
    except OSError:
        raise _error("unknown", "payload file identity is unavailable")
    if stat.S_ISLNK(initial.st_mode):
        raise _error("invalid", "payload path must not be a symlink")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise _error("unsupported", "secure payload file opening is unavailable")
    nonblock = getattr(os, "O_NONBLOCK", None)
    if nonblock is None:
        raise _error("unsupported", "bounded payload file opening is unavailable")
    geteuid = getattr(os, "geteuid", None)
    if not callable(geteuid):
        raise _error("unknown", "payload file ownership cannot be verified")
    try:
        owner_uid = geteuid()
    except OSError:
        raise _error("unknown", "payload file ownership cannot be verified")
    _check_payload_file_stat(initial, owner_uid)
    flags = os.O_RDONLY | int(nofollow) | int(nonblock)
    cloexec = getattr(os, "O_CLOEXEC", 0)
    if isinstance(cloexec, int):
        flags |= cloexec
    fd: Optional[int] = None
    try:
        try:
            fd = os.open(str(path), flags)
        except (OSError, ValueError):
            raise _error("unknown", "payload file could not be opened securely")
        try:
            first = os.fstat(fd)
        except OSError:
            raise _error("unknown", "payload file identity could not be checked")
        if (first.st_dev, first.st_ino) != (initial.st_dev, initial.st_ino):
            raise _error("unknown", "payload path changed during secure open")
        _check_payload_file_stat(first, owner_uid)
        content = bytearray()
        while len(content) <= MAX_FRAME_BYTES:
            try:
                chunk = os.read(fd, MAX_FRAME_BYTES + 1 - len(content))
            except OSError:
                raise _error("unknown", "payload file could not be read")
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > MAX_FRAME_BYTES:
                raise _error("invalid", "payload file exceeds the one MiB bound")
        try:
            final = os.fstat(fd)
        except OSError:
            raise _error("unknown", "payload file identity could not be checked")
        if (final.st_dev, final.st_ino) != (initial.st_dev, initial.st_ino):
            raise _error("unknown", "payload path changed during secure read")
        _check_payload_file_stat(final, owner_uid)
        try:
            return bytes(content).decode("utf-8")
        except UnicodeDecodeError:
            raise _error("invalid", "payload file is not valid UTF-8")
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _check_payload_file_stat(file_stat: os.stat_result, owner_uid: int) -> None:
    """Fail closed unless a descriptor names the required private file."""

    if not stat.S_ISREG(file_stat.st_mode):
        raise _error("invalid", "payload path is not a regular file")
    if file_stat.st_uid != owner_uid:
        raise _error("unsupported", "payload file is not owner-owned")
    if stat.S_IMODE(file_stat.st_mode) & 0o077:
        raise _error("unsupported", "payload file is not private")
    if file_stat.st_size > MAX_FRAME_BYTES:
        raise _error("invalid", "payload file exceeds the one MiB bound")


def _participant_from_wire(
        value: Any, label: str, *, bound_lane: Optional[str] = None) -> Any:
    """Build the exact controller ``Participant`` from one public record."""

    from lane_managed_controller import Participant, WriterClaim

    _bounded_wire(value, label)
    raw = _strict_object(value, _PARTICIPANT_KEYS, _PARTICIPANT_REQUIRED_KEYS, label)
    participant_id = _bounded_id(raw["participant_id"], "%s participant_id" % label)
    session_id = _bounded_id(raw["session_id"], "%s session_id" % label)
    if "session_uuid" in raw:
        session_uuid = _bounded_id(raw["session_uuid"], "%s session_uuid" % label)
        if session_uuid != session_id:
            raise _error("invalid", "%s session UUID aliases disagree" % label)
    role = raw["role"]
    if role not in {"coordinator", "worker"}:
        raise _error("invalid", "%s role is not canonical" % label)
    kind = raw["kind"]
    if kind != "independent":
        raise _error("unsupported", "%s kind is not an independent session" % label)
    state = raw["state"]
    if state not in {"reserved", "held", "active", "completed", "stopped"}:
        raise _error("invalid", "%s state is invalid" % label)
    parent_id = _optional_bounded_text(raw["parent_id"], "%s parent_id" % label)
    task_id = _bounded_id(raw["task_id"], "%s task_id" % label)
    mailbox_id = _bounded_id(raw["mailbox_id"], "%s mailbox_id" % label)
    for name in ("read_only", "background", "detached"):
        if not isinstance(raw[name], bool):
            raise _error("invalid", "%s %s must be boolean" % (label, name))
    if raw["metadata"] is None or not isinstance(raw["metadata"], Mapping):
        raise _error("invalid", "%s metadata must be an object" % label)
    _bounded_wire(raw["metadata"], "%s metadata" % label)
    _reject_evidence_keys(raw["metadata"], "%s metadata" % label)
    for name in ("model", "permission_mode"):
        if raw[name] is not None and not isinstance(raw[name], str):
            raise _error("invalid", "%s %s must be text or null" % (label, name))

    session_name = _bounded_id(
        raw.get("session_name", participant_id), "%s session_name" % label
    )
    if bound_lane is None:
        supplied_lane = raw.get("bound_lane")
        if supplied_lane is None:
            raise _error("invalid", "%s bound_lane is unavailable" % label)
        bound_lane = supplied_lane
    bound_lane = _bounded_id(bound_lane, "%s bound_lane" % label, 128)
    if bound_lane in {".", ".."} or "/" in bound_lane or "\\" in bound_lane:
        raise _error("invalid", "%s bound_lane is invalid" % label)
    supplied_bound_lane = raw.get("bound_lane")
    if supplied_bound_lane is not None:
        supplied_bound_lane = _bounded_id(
            supplied_bound_lane, "%s bound_lane" % label, 128
        )
        if supplied_bound_lane.casefold() != bound_lane.casefold():
            raise _error("ownership-conflict", "%s bound_lane is not canonical" % label)
    metadata = dict(raw["metadata"])
    if "session_name" in metadata:
        metadata_name = _bounded_id(metadata["session_name"], "%s metadata session_name" % label)
        if metadata_name != session_name:
            raise _error("invalid", "%s session_name copies disagree" % label)
    if "bound_lane" in metadata:
        metadata_lane = _bounded_id(metadata["bound_lane"], "%s metadata bound_lane" % label, 128)
        if metadata_lane.casefold() != bound_lane.casefold():
            raise _error("ownership-conflict", "%s bound_lane copies disagree" % label)
    metadata["session_name"] = session_name
    metadata["bound_lane"] = bound_lane

    claim = raw["writer_claim"]
    claim_object = None
    if claim is not None:
        _bounded_wire(claim, "%s writer_claim" % label)
        _reject_evidence_keys(claim, "%s writer_claim" % label)
        claim_raw = _strict_object(
            claim,
            _CLAIM_KEYS,
            frozenset({"participant_id", "worktree", "repository", "state"}),
            "%s writer_claim" % label,
        )
        claim_participant_id = _bounded_id(
            claim_raw["participant_id"], "%s writer_claim participant_id" % label
        )
        if claim_participant_id != participant_id:
            raise _error("invalid", "%s writer claim identity disagrees" % label)
        if claim_raw.get("metadata") is not None:
            if not isinstance(claim_raw["metadata"], Mapping):
                raise _error("invalid", "%s writer claim metadata is invalid" % label)
            _bounded_wire(claim_raw["metadata"], "%s writer claim metadata" % label)
        if claim_raw.get("lane") is not None and not isinstance(claim_raw["lane"], str):
            raise _error("invalid", "%s writer claim lane is invalid" % label)
        claim_object = WriterClaim(
            participant_id=claim_participant_id,
            worktree=claim_raw["worktree"],
            repository=claim_raw["repository"],
            state=claim_raw["state"],
            lane=claim_raw.get("lane"),
            metadata=dict(claim_raw.get("metadata") or {}),
        )

    try:
        return Participant(
            participant_id=participant_id,
            session_id=session_id,
            role=role,
            parent_id=parent_id,
            task_id=task_id,
            mailbox_id=mailbox_id,
            kind=kind,
            state=state,
            writer_claim=claim_object,
            read_only=raw["read_only"],
            background=raw["background"],
            detached=raw["detached"],
            model=raw["model"],
            permission_mode=raw["permission_mode"],
            fingerprint=raw["fingerprint"],
            session_name=session_name,
            bound_lane=bound_lane,
            metadata=metadata,
        )
    except DaemonError:
        raise
    except Exception:
        raise _error("invalid", "%s participant fields are malformed" % label)


def _runner_spec_from_wire(
        value: Any, participant_id: str, *, bound_lane: Optional[str] = None) -> Any:
    """Build the exact canonical runner reconstruction specification."""

    # ``RunnerSpec`` is part of the adapter boundary and is imported only when
    # an opted-in start request actually crosses this admission point.
    from lane_managed_sdk import RunnerSpec

    label = "start runner specification for %s" % participant_id
    _bounded_wire(value, label)
    _reject_evidence_keys(value, label)
    raw = _strict_object(
        value,
        _RUNNER_SPEC_KEYS,
        frozenset({"participant_id", "session_id", "mode"}),
        label,
    )
    session_id = _bounded_id(raw["session_id"], "%s session_id" % label)
    mode = raw["mode"]
    if mode not in {"resume", "fresh"}:
        raise _error("invalid", "%s mode is not canonical" % label)
    if "participant_id" in raw:
        supplied_participant_id = _bounded_id(
            raw["participant_id"], "%s participant_id" % label
        )
        if supplied_participant_id != participant_id:
            raise _error("invalid", "%s participant identity disagrees" % label)
    # The native name is the stable guard identity.  A missing name is
    # derived once from the durable participant ID; it is inserted into the
    # canonical spec before the controller sees it, so retries do not invent a
    # different name.  ``bound_lane`` is always derived from the canonical
    # request lane, never from inherited environment state.
    session_name = raw.get("session_name", participant_id)
    session_name = _bounded_id(session_name, "%s session_name" % label)
    if bound_lane is None:
        supplied_lane = raw.get("bound_lane")
        if supplied_lane is None:
            raise _error("invalid", "%s bound_lane is unavailable" % label)
        bound_lane = supplied_lane
    bound_lane = _bounded_id(bound_lane, "%s bound_lane" % label, 128)
    if bound_lane in {".", ".."} or "/" in bound_lane or "\\" in bound_lane:
        raise _error("invalid", "%s bound_lane is invalid" % label)
    supplied_bound_lane = raw.get("bound_lane")
    if supplied_bound_lane is not None:
        supplied_bound_lane = _bounded_id(
            supplied_bound_lane, "%s bound_lane" % label, 128
        )
        if supplied_bound_lane.casefold() != bound_lane.casefold():
            raise _error("ownership-conflict", "%s bound_lane is not canonical" % label)
    if "resume" in raw and not isinstance(raw["resume"], bool):
        raise _error("invalid", "%s resume must be boolean" % label)
    if "fresh" in raw and not isinstance(raw["fresh"], bool):
        raise _error("invalid", "%s fresh must be boolean" % label)
    for name in (
        "profile_name", "profile_family", "account_email", "config_dir",
        "workspace", "worktree", "cwd", "transcript_store", "transcript_path",
        "transcript_project", "model", "effort", "permission_mode",
    ):
        if name in raw and raw[name] is not None and not isinstance(raw[name], str):
            raise _error("invalid", "%s %s must be text or null" % (label, name))
    if "fingerprint" in raw and not isinstance(raw["fingerprint"], Mapping):
        raise _error("invalid", "%s fingerprint must be an object" % label)
    if "permissions" in raw and not isinstance(raw["permissions"], Mapping):
        raise _error("invalid", "%s permissions must be an object" % label)
    if "supported_models" in raw:
        supported_models = raw["supported_models"]
        if not isinstance(supported_models, (list, tuple)):
            raise _error("invalid", "%s supported_models must be an array" % label)
        if any(not isinstance(item, str) or not item for item in supported_models):
            raise _error("invalid", "%s supported_models contains an invalid model" % label)
    if "tools" in raw and raw["tools"] is not None:
        _bounded_wire(raw["tools"], "%s tools" % label)
    if "launch_flags" in raw and raw["launch_flags"] is not None:
        _bounded_wire(raw["launch_flags"], "%s launch_flags" % label)
    if "flags" in raw and raw["flags"] is not None:
        _bounded_wire(raw["flags"], "%s flags" % label)
    canonical_raw = dict(raw)
    canonical_raw["session_name"] = session_name
    canonical_raw["bound_lane"] = bound_lane
    try:
        spec = RunnerSpec.from_mapping(canonical_raw)
    except Exception:
        raise _error("invalid", "%s runner fields are malformed" % label)
    if type(spec) is not RunnerSpec:
        raise _error("invalid", "%s did not produce a canonical runner spec" % label)
    if (
        spec.session_id != session_id
        or spec.participant_id != participant_id
        or spec.session_name != session_name
    ):
        raise _error("invalid", "%s runner identity is malformed" % label)
    if getattr(spec, "bound_lane", None) != bound_lane:
        # Do not silently drop the guard's lane binding when an older adapter
        # class is loaded.  The production SDK boundary must carry this exact
        # field into native runner construction.
        raise _error("unsupported", "%s runner spec cannot carry bound_lane" % label)
    if spec.mode != mode:
        raise _error("invalid", "%s runner mode is inconsistent" % label)
    return spec


def _swap_runner_specs_from_wire(
        value: Any, *, bound_lane: Optional[str] = None) -> Optional[dict[str, dict[str, Any]]]:
    """Validate optional swap specs without accepting evidence or aliases."""

    if value is None:
        return None
    _bounded_wire(value, "swap runner_specs")
    if not isinstance(value, Mapping):
        raise _error("invalid", "swap runner_specs must be an object")
    result: dict[str, dict[str, Any]] = {}
    for raw_participant_id, raw_spec in value.items():
        participant_id = _bounded_id(raw_participant_id, "swap participant_id")
        label = "swap runner specification for %s" % participant_id
        _bounded_wire(raw_spec, label)
        _reject_evidence_keys(raw_spec, label)
        spec = _strict_object(
            raw_spec,
            _RUNNER_SPEC_KEYS,
            frozenset({"session_id", "mode"}),
            label,
        )
        session_name = spec.get("session_name", participant_id)
        session_name = _bounded_id(session_name, "%s session_name" % label)
        if bound_lane is None:
            canonical_lane = spec.get("bound_lane")
        else:
            canonical_lane = bound_lane
        canonical_lane = _bounded_id(canonical_lane, "%s bound_lane" % label, 128)
        if canonical_lane in {".", ".."} or "/" in canonical_lane or "\\" in canonical_lane:
            raise _error("invalid", "%s bound_lane is invalid" % label)
        if "bound_lane" in spec:
            supplied_lane = _bounded_id(spec["bound_lane"], "%s bound_lane" % label, 128)
            if supplied_lane.casefold() != canonical_lane.casefold():
                raise _error("ownership-conflict", "%s bound_lane is not canonical" % label)
        _bounded_id(spec["session_id"], "%s session_id" % label)
        if spec["mode"] not in {"resume", "fresh"}:
            raise _error("invalid", "%s mode is not canonical" % label)
        if "participant_id" in spec:
            supplied = _bounded_id(spec["participant_id"], "%s participant_id" % label)
            if supplied != participant_id:
                raise _error("invalid", "%s participant identity disagrees" % label)
        for name in ("resume", "fresh"):
            if name in spec and not isinstance(spec[name], bool):
                raise _error("invalid", "%s %s must be boolean" % (label, name))
        for name in (
            "profile_name", "profile_family", "account_email", "config_dir",
            "workspace", "worktree", "cwd", "transcript_store", "transcript_path",
            "transcript_project", "model", "effort", "permission_mode", "role",
            "parent_id", "task_id",
        ):
            if name in spec and spec[name] is not None and not isinstance(spec[name], str):
                raise _error("invalid", "%s %s must be text or null" % (label, name))
        if "supported_models" in spec:
            models = spec["supported_models"]
            if not isinstance(models, (list, tuple)) or any(
                not isinstance(item, str) or not item for item in models
            ):
                raise _error("invalid", "%s supported_models is invalid" % label)
        for name in ("fingerprint", "permissions"):
            if name in spec and spec[name] is not None:
                if not isinstance(spec[name], Mapping):
                    raise _error("invalid", "%s %s must be an object" % (label, name))
                _bounded_wire(spec[name], "%s %s" % (label, name))
        for name in ("tools", "launch_flags", "flags"):
            if name in spec and spec[name] is not None:
                _bounded_wire(spec[name], "%s %s" % (label, name))
        canonical_spec = dict(spec)
        canonical_spec["session_name"] = session_name
        canonical_spec["bound_lane"] = canonical_lane
        result[participant_id] = canonical_spec
    session_names = [spec["session_name"] for spec in result.values()]
    if len(set(session_names)) != len(session_names):
        raise _error("invalid", "swap runner specifications contain duplicate session names")
    return result


def _start_inputs(
        value: Any, *, bound_lane: Optional[str] = None) -> tuple[Any, list[Any], dict[str, Any]]:
    """Validate and construct the complete canonical start argument tuple."""

    _bounded_wire(value, "start body")
    body = _strict_object(value, _START_BODY_KEYS, _START_BODY_KEYS, "start body")
    coordinator = _participant_from_wire(
        body["coordinator"], "start coordinator", bound_lane=bound_lane
    )
    raw_participants = body["participants"]
    if not isinstance(raw_participants, list):
        raise _error("invalid", "start participants must be an array")
    participants = [
        _participant_from_wire(
            item, "start participant %d" % index, bound_lane=bound_lane
        )
        for index, item in enumerate(raw_participants)
    ]
    if coordinator.role != "coordinator" or coordinator.parent_id is not None:
        raise _error("invalid", "start coordinator identity is malformed")
    if any(item.role != "worker" for item in participants):
        raise _error("invalid", "start participants must be workers")
    all_participants = [coordinator] + participants
    participant_ids = [item.participant_id for item in all_participants]
    session_ids = [item.session_id for item in all_participants]
    mailbox_ids = [item.mailbox_id for item in all_participants]
    if len(set(participant_ids)) != len(participant_ids):
        raise _error("invalid", "start roster contains duplicate participant IDs")
    if len(set(session_ids)) != len(session_ids):
        raise _error("invalid", "start roster contains duplicate session UUIDs")
    if len(set(mailbox_ids)) != len(mailbox_ids):
        raise _error("invalid", "start roster contains duplicate mailbox identities")
    if any(item.parent_id != coordinator.participant_id for item in participants):
        raise _error("invalid", "start worker parent_id must name the coordinator")

    raw_specs = body["runner_specs"]
    if not isinstance(raw_specs, Mapping):
        raise _error("invalid", "start runner_specs must be an object")
    spec_keys = list(raw_specs.keys())
    if any(not isinstance(key, str) for key in spec_keys):
        raise _error("invalid", "start runner_specs contains a non-string identity")
    if set(spec_keys) != set(participant_ids):
        raise _error("invalid", "start runner_specs must exactly cover the roster")
    runner_specs = {
        participant_id: _runner_spec_from_wire(
            raw_specs[participant_id], participant_id, bound_lane=bound_lane
        )
        for participant_id in participant_ids
    }
    session_names = [spec.session_name for spec in runner_specs.values()]
    if any(not isinstance(name, str) or not name for name in session_names):
        raise _error("invalid", "start runner session names are unavailable")
    if len(set(session_names)) != len(session_names):
        raise _error("invalid", "start roster contains duplicate session names")
    for participant_id, spec in runner_specs.items():
        participant = next(
            item.session_id for item in all_participants
            if item.participant_id == participant_id
        )
        enrolled = next(
            item for item in all_participants if item.participant_id == participant_id
        )
        if (
            spec.session_id != participant
            or spec.session_name != enrolled.session_name
            or getattr(spec, "bound_lane", None) != enrolled.bound_lane
        ):
            raise _error("invalid", "start runner UUID does not match the participant")
    return coordinator, participants, runner_specs


def _checkpoint_from_wire(value: Any) -> Any:
    """Validate one bounded opaque checkpoint reference.

    Checkpoints cross the daemon as references only.  A structured value may
    carry its digest, but never transcript/payload content or runtime proof.
    """

    _bounded_wire(value, "checkpoint")
    if isinstance(value, str):
        return _bounded_id(value, "checkpoint", MAX_FRAME_BYTES)
    if not isinstance(value, Mapping):
        raise _error("invalid", "checkpoint must be an opaque reference")
    if set(value).difference({"ref", "digest"}):
        raise _error("unsupported", "checkpoint contains body or unsupported fields")
    if "ref" not in value and "digest" not in value:
        raise _error("invalid", "checkpoint reference is empty")
    result: dict[str, Any] = {}
    if "ref" in value:
        result["ref"] = _bounded_id(
            value["ref"], "checkpoint ref", MAX_FRAME_BYTES
        )
    if "digest" in value:
        digest = value["digest"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise _error("invalid", "checkpoint digest is malformed")
        result["digest"] = digest
    return result


def _native_digest(value: Any, label: str) -> str:
    """Validate one complete trusted-definition digest without recomputing it."""

    if not isinstance(value, str) or _NATIVE_DIGEST_RE.fullmatch(value) is None:
        raise _error("invalid", "%s is not a complete definition digest" % label)
    return value


def _positive_int(value: Any, label: str) -> int:
    """Validate a strict positive integer in a reservation binding."""

    if type(value) is not int or value <= 0:
        raise _error("invalid", "%s must be a positive integer" % label)
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise _error("invalid", "%s must be a non-negative integer" % label)
    return value


def _reservation_digest(value: Any, label: str) -> str:
    """Return the canonical digest used by the native reservation contract."""

    try:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise _error("invalid", "%s is not canonically digestible" % label)
    return hashlib.sha256(encoded).hexdigest()


def _reservation_binding_from_controller(
        value: Any, *, daemon_id: str, participant_id: str,
        session_id: str, runner_instance_id: str, message_id: str,
        owner_generation: int, context: Mapping[str, Any],
        label: str = "native reservation binding") -> dict[str, Any]:
    """Project one controller reservation into the SDK acknowledgement.

    The trusted runner produces the terminal proof and reservation; the
    controller validates and durably commits it.  This seam performs the
    final closed-shape, digest, and current-lineage checks before exposing
    that exact response to the SDK.  The mutable reservation remains outside
    the strict lineage context.
    """

    if not isinstance(value, Mapping):
        raise _error("invalid", "%s must be an object" % label)
    keys = set(value)
    if any(not isinstance(key, str) for key in keys):
        raise _error("invalid", "%s contains a non-string key" % label)
    unknown = keys.difference(_RESERVATION_BINDING_KEYS)
    if unknown:
        raise _error("invalid", "%s contains an unsupported field" % label)
    missing = _RESERVATION_BINDING_KEYS.difference(keys)
    if missing:
        raise _error("invalid", "%s is missing a complete response field" % label)
    result = dict(value)
    for key in (
            "reservation_id", "operation_id", "daemon_id",
            "participant_id", "session_id", "runner_incarnation",
            "lineage_id", "prior_invocation_id", "next_invocation_id",
            "prior_mailbox_id", "next_mailbox_id"):
        result[key] = _bounded_id(result[key], "%s.%s" % (label, key))
    if (type(result["schema_version"]) is not int or
            result["schema_version"] != SCHEMA_VERSION):
        raise _error("schema-mismatch", "%s schema version is unsupported" % label)
    if result["architecture"] != SCHEMA_ARCHITECTURE:
        raise _error("schema-mismatch", "%s architecture is unsupported" % label)
    if (type(result["reservation_version"]) is not int or
            result["reservation_version"] != 1):
        raise _error("schema-mismatch", "%s reservation version is unsupported" % label)
    result["prior_watermark"] = _nonnegative_int(
        result["prior_watermark"], "%s.prior_watermark" % label
    )
    result["owner_generation"] = _positive_int(
        result["owner_generation"], "%s.owner_generation" % label
    )
    result["lineage_generation"] = _positive_int(
        result["lineage_generation"], "%s.lineage_generation" % label
    )
    for key in (
            "definitions_digest", "permissions_digest", "claim_digest",
            "binding_digest", "terminal_proof_digest"):
        result[key] = _native_digest(result[key], "%s.%s" % (label, key))
    if result["state"] != "reserved":
        raise _error("busy", "%s is not reserved" % label)
    result["terminal_watermark"] = _nonnegative_int(
        result["terminal_watermark"], "%s.terminal_watermark" % label
    )
    result["next_watermark"] = _nonnegative_int(
        result["next_watermark"], "%s.next_watermark" % label
    )
    if result["terminal_watermark"] <= result["prior_watermark"]:
        raise _error("stale-generation", "%s terminal watermark is stale" % label)
    if result["next_watermark"] <= result["terminal_watermark"]:
        raise _error("stale-generation", "%s next watermark is stale" % label)

    proof = result["terminal_proof"]
    if not isinstance(proof, Mapping) or set(proof) != _RESERVATION_TERMINAL_PROOF_KEYS:
        raise _error("invalid", "%s terminal proof fields are malformed" % label)
    parent = proof["parent_result"]
    if not isinstance(parent, Mapping) or set(parent) != _RESERVATION_PARENT_RESULT_KEYS:
        raise _error("invalid", "%s terminal parent result is malformed" % label)
    parent_identity = {
        "session_id": result["session_id"],
        "invocation_id": result["prior_invocation_id"],
        "message_id": result["prior_mailbox_id"],
    }
    for key, expected in parent_identity.items():
        parent_value = _bounded_id(parent[key], "%s.parent_result.%s" % (label, key))
        if parent_value != expected:
            raise _error("stale-generation", "%s terminal parent identity changed" % label)
    result_watermark = _nonnegative_int(
        parent["result_watermark"], "%s.parent_result.result_watermark" % label
    )
    drained_watermark = _nonnegative_int(
        parent["reader_drained_watermark"],
        "%s.parent_result.reader_drained_watermark" % label,
    )
    if result_watermark <= result["prior_watermark"] or result_watermark > drained_watermark:
        raise _error("stale-generation", "%s terminal parent watermark is invalid" % label)
    roster = proof["roster"]
    if not isinstance(roster, Mapping) or set(roster) != _RESERVATION_ROSTER_KEYS:
        raise _error("invalid", "%s terminal roster is malformed" % label)
    if roster["parent_state"] != "idle":
        raise _error("busy", "%s terminal roster is not idle" % label)
    if not isinstance(roster["children"], list):
        raise _error("invalid", "%s terminal child roster is malformed" % label)
    for key in (
            "pending_admission_ids", "pending_task_ids", "parent_active_tool_ids",
            "parent_uncertain_tool_ids", "parent_unresolved_effect_ids",
            "descendant_ids"):
        if not isinstance(roster[key], list) or roster[key]:
            raise _error("uncertain-effect", "%s terminal roster is not drained" % label)
    if not isinstance(proof["uncertainty"], list) or proof["uncertainty"]:
        raise _error("uncertain-effect", "%s terminal proof has uncertainty" % label)
    if type(proof["overflow"]) is not bool or proof["overflow"]:
        raise _error("uncertain-effect", "%s terminal proof overflowed" % label)
    observation = _nonnegative_int(
        proof["observation_watermark"], "%s.observation_watermark" % label
    )
    if observation != result["terminal_watermark"] or drained_watermark > observation:
        raise _error("stale-generation", "%s terminal observation changed" % label)
    if result["terminal_proof_digest"] != _reservation_digest(
            proof, label + ".terminal_proof"):
        raise _error("stale-generation", "%s terminal proof digest changed" % label)
    if proof["roster_digest"] != _reservation_digest(roster, label + ".roster"):
        raise _error("stale-generation", "%s terminal roster digest changed" % label)
    binding_input = {
        key: result[key]
        for key in _RESERVATION_BINDING_REQUIRED_KEYS
        if key != "binding_digest"
    }
    if result["binding_digest"] != _reservation_digest(
            binding_input, label + ".binding"):
        raise _error("stale-generation", "%s binding digest changed" % label)

    if result["daemon_id"] != daemon_id:
        raise _error("ownership-conflict", "%s daemon identity changed" % label)
    if result["participant_id"] != participant_id:
        raise _error("ownership-conflict", "%s participant identity changed" % label)
    if result["session_id"] != session_id:
        raise _error("stale-generation", "%s session identity changed" % label)
    if result["runner_incarnation"] != runner_instance_id:
        raise _error("stale-generation", "%s runner identity changed" % label)
    if (result["next_invocation_id"] != message_id or
            result["next_mailbox_id"] != message_id):
        raise _error("stale-generation", "%s next mailbox changed" % label)
    if result["prior_invocation_id"] == result["next_invocation_id"]:
        raise _error("invalid", "%s rollover invocations are not distinct" % label)
    if result["prior_mailbox_id"] == result["next_mailbox_id"]:
        raise _error("invalid", "%s rollover mailboxes are not distinct" % label)
    if result["owner_generation"] != owner_generation:
        raise _error("stale-generation", "%s owner generation changed" % label)
    lineage = context.get("lineage") if isinstance(context, Mapping) else None
    if not isinstance(lineage, Mapping):
        raise _error("ownership-conflict", "%s context lineage is unavailable" % label)
    for key in ("owner_generation", "lineage_id", "lineage_generation"):
        if result[key] != lineage.get(key):
            raise _error("stale-generation", "%s lineage identity changed" % label)
    _bounded_wire(result, label)
    return result


def _reject_native_definition_identity(value: Any, label: str) -> None:
    """Reject child/runner authority hidden inside a caller definition.

    The definition is an intent payload.  Its digest is checked by the
    controller against its trusted definition fence; this loader never treats
    an embedded identity, claim, policy, or runtime observation as authority.
    """

    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise _error("invalid", "%s contains a non-string key" % label)
            normalized = key.casefold().replace("-", "_")
            if normalized in _NATIVE_ADMISSION_DEFINITION_FORBIDDEN_KEYS:
                raise _error(
                    "unsupported",
                    "%s contains a child identity or runtime authority field" % label,
                )
            _reject_native_definition_identity(item, "%s.%s" % (label, key))
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _reject_native_definition_identity(item, label)


def _native_admission_from_wire(value: Any) -> dict[str, Any]:
    """Load one canonical native admission intent without adding aliases.

    This boundary accepts only the pre-allow data emitted by the native SDK
    adapter.  In particular, ``agent_id``, ``task_id``, child ``session_id``,
    runner incarnation aliases, process groups, mailboxes, claims, policy,
    and acknowledgement/evidence fields are not request fields.  The
    controller is the sole authority that can validate the current fence and
    trusted definition, then persist the pending admission atomically.
    """

    _bounded_wire(value, "native admission body")
    raw = _strict_object(
        value,
        _NATIVE_ADMISSION_BODY_KEYS,
        _NATIVE_ADMISSION_REQUIRED_KEYS,
        "native admission body",
    )
    _reject_evidence_keys(raw, "native admission body")

    result: dict[str, Any] = {}
    for name in (
        "admission_id", "tool_use_id", "agent_type", "invocation_id",
        "lineage_id", "runner_incarnation",
    ):
        result[name] = _bounded_id(
            raw[name], "native admission %s" % name
        )
    result["definition_digest"] = _native_digest(
        raw["definition_digest"], "native admission definition_digest"
    )
    result["trusted_definition_digest"] = _native_digest(
        raw["trusted_definition_digest"],
        "native admission trusted_definition_digest",
    )
    if result["definition_digest"] != result["trusted_definition_digest"]:
        raise _error(
            "ownership-conflict",
            "native admission definition digests disagree",
        )

    owner_generation = raw["owner_generation"]
    if type(owner_generation) is not int or owner_generation <= 0:
        raise _error(
            "invalid", "native admission owner_generation must be a positive integer"
        )
    result["owner_generation"] = owner_generation
    watermark = raw["watermark"]
    if type(watermark) is not int or watermark <= 0:
        raise _error(
            "invalid", "native admission watermark must be a positive integer"
        )
    result["watermark"] = watermark
    if type(raw["launch_completed"]) is not bool or raw["launch_completed"] is not False:
        raise _error(
            "unsupported",
            "native admission must be pending before SubagentStart",
        )
    result["launch_completed"] = False

    parent = raw["parent"]
    _bounded_wire(parent, "native admission parent")
    parent = _strict_object(
        parent,
        _NATIVE_ADMISSION_PARENT_KEYS,
        _NATIVE_ADMISSION_PARENT_REQUIRED_KEYS,
        "native admission parent",
    )
    parent_result: dict[str, Any] = {
        "session_id": _bounded_id(
            parent["session_id"], "native admission parent session_id"
        ),
        "invocation_id": _bounded_id(
            parent["invocation_id"], "native admission parent invocation_id"
        ),
    }
    if parent_result["invocation_id"] != result["invocation_id"]:
        raise _error(
            "stale-generation",
            "native admission parent invocation does not match its intent",
        )
    for name in ("agent_id", "prompt_id"):
        if name not in parent:
            continue
        item = parent[name]
        parent_result[name] = (
            None if item is None else _bounded_id(
                item, "native admission parent %s" % name
            )
        )
    result["parent"] = parent_result

    definition = raw["custom_definition"]
    if not isinstance(definition, Mapping):
        raise _error(
            "invalid", "native admission custom_definition must be an object"
        )
    _bounded_wire(definition, "native admission custom_definition")
    _reject_evidence_keys(definition, "native admission custom_definition")
    _reject_native_definition_identity(
        definition, "native admission custom_definition"
    )
    # The JSON-bound check above makes this deep copy deterministic and keeps
    # caller-owned nested objects from changing while the controller performs
    # its bounded atomic persistence call.
    result["custom_definition"] = copy.deepcopy(dict(definition))
    return result


def _native_admission_ack(
    admission: Mapping[str, Any], acknowledgement: Any
) -> dict[str, Any]:
    """Return only the exact correlated pre-allow acknowledgement."""

    if not isinstance(acknowledgement, Mapping):
        raise _error(
            "invalid", "managed native admission authority returned no acknowledgement"
        )
    if acknowledgement.get("accepted") is not True:
        # A controller may return a stable refusal code with ``accepted`` false.
        # No caller-provided code is read; this is an injected authority result.
        code = acknowledgement.get("code")
        if not isinstance(code, str) or not code:
            code = "unsupported"
        raise _error(code, "managed native admission was refused")
    result: dict[str, Any] = {"accepted": True}
    for name in _NATIVE_ADMISSION_ACK_FIELDS:
        if name not in acknowledgement:
            raise _error(
                "uncertain-effect",
                "managed native admission acknowledgement is incomplete",
            )
        expected = admission.get(name)
        actual = acknowledgement.get(name)
        if type(actual) is not type(expected) or actual != expected:
            raise _error(
                "stale-generation",
                "managed native admission acknowledgement is stale",
            )
        result[name] = actual
    _bounded_wire(result, "native admission acknowledgement")
    return result


def _native_child_observation_projection(
        value: Any, label: str = "native child observation"
) -> dict[str, Any]:
    """Validate the exact joined fifteen-field native child projection.

    The daemon repeats the producer's closed-shape checks so malformed or
    raw-runtime frames never reach the controller authority.  Identity joins,
    trusted definition ownership, and durable watermark admission remain the
    controller's responsibility; this helper only rejects aliases, malformed
    values, and impossible local relationships.
    """

    _bounded_wire(value, label)
    child = _strict_object(
        value,
        _NATIVE_CHILD_PROJECTION_KEYS,
        _NATIVE_CHILD_PROJECTION_KEYS,
        label,
    )
    for key in ("admission_id", "tool_use_id", "agent_id", "task_id", "invocation_id"):
        child[key] = _bounded_id(child[key], "%s %s" % (label, key))
    if child["parent_agent_id"] is not None:
        child["parent_agent_id"] = _bounded_id(
            child["parent_agent_id"], "%s parent_agent_id" % label
        )
    child["lineage_incarnation"] = _positive_int(
        child["lineage_incarnation"], "%s lineage_incarnation" % label
    )
    child["trusted_definition_digest"] = _native_digest(
        child["trusted_definition_digest"],
        "%s trusted_definition_digest" % label,
    )
    child["start_watermark"] = _positive_int(
        child["start_watermark"], "%s start_watermark" % label
    )

    task_start = _strict_object(
        child["task_start_event"],
        _NATIVE_CHILD_TASK_START_KEYS,
        _NATIVE_CHILD_TASK_START_KEYS,
        "%s task_start_event" % label,
    )
    if task_start["event_uuid"] is not None:
        task_start["event_uuid"] = _bounded_id(
            task_start["event_uuid"], "%s task event UUID" % label
        )
    task_start["watermark"] = _positive_int(
        task_start["watermark"], "%s task event watermark" % label
    )
    task_start["task_type"] = _bounded_id(
        task_start["task_type"], "%s task type" % label
    )
    child["task_start_event"] = task_start

    status = child["status"]
    if status not in {"active", "completed", "stopped"}:
        raise _error("invalid", "%s status is unsupported" % label)
    terminal_watermark = child["terminal_watermark"]
    if status == "active":
        if terminal_watermark is not None:
            raise _error("invalid", "%s active child has terminal watermark" % label)
    else:
        child["terminal_watermark"] = _positive_int(
            terminal_watermark, "%s terminal watermark" % label
        )
        if child["terminal_watermark"] < child["start_watermark"]:
            raise _error(
                "stale-generation",
                "%s terminal watermark predates child start" % label,
            )

    for key in ("active_tool_ids", "uncertain_tool_ids", "unresolved_effect_ids"):
        values = child[key]
        if not isinstance(values, list) or len(values) > _NATIVE_CHILD_MAX_INVENTORY:
            raise _error("invalid", "%s %s inventory is invalid" % (label, key))
        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            item = _bounded_id(item, "%s %s ID" % (label, key))
            if item in seen:
                raise _error(
                    "uncertain-effect",
                    "%s %s inventory repeats an ID" % (label, key),
                )
            seen.add(item)
            normalized.append(item)
        child[key] = normalized
    if set(child["active_tool_ids"]) & set(child["uncertain_tool_ids"]):
        raise _error("uncertain-effect", "%s tool inventories overlap" % label)
    return child


def _native_child_observation_from_frame(value: Any) -> dict[str, Any]:
    """Validate and detach one exact private native-child frame."""

    _bounded_wire(value, "native child observation frame")
    frame = _strict_object(
        value,
        _NATIVE_CHILD_OBSERVATION_FRAME_KEYS,
        _NATIVE_CHILD_OBSERVATION_FRAME_KEYS,
        "native child observation frame",
    )
    if frame["type"] != _NATIVE_CHILD_OBSERVATION_TYPE:
        raise _error("invalid", "native child observation frame type is unsupported")
    frame["participant_id"] = _bounded_id(
        frame["participant_id"], "native child observation participant_id"
    )
    frame["session_id"] = _bounded_id(
        frame["session_id"], "native child observation session_id"
    )
    frame["runner_instance_id"] = _bounded_id(
        frame["runner_instance_id"],
        "native child observation runner_instance_id",
    )

    observation = _strict_object(
        frame["observation"],
        _NATIVE_CHILD_OBSERVATION_KEYS,
        _NATIVE_CHILD_OBSERVATION_KEYS,
        "native child observation",
    )
    if type(observation["schema_version"]) is not int or observation["schema_version"] != 2:
        raise _error("invalid", "native child observation schema_version is unsupported")
    if observation["architecture"] != NATIVE_ARCHITECTURE:
        raise _error("invalid", "native child observation architecture is unsupported")
    if observation["record_kind"] != _NATIVE_CHILD_OBSERVATION_TYPE:
        raise _error("invalid", "native child observation record_kind is unsupported")
    observation["observation_id"] = _bounded_id(
        observation["observation_id"], "native child observation_id"
    )

    source = _strict_object(
        observation["source_identity"],
        _NATIVE_CHILD_SOURCE_IDENTITY_KEYS,
        _NATIVE_CHILD_SOURCE_IDENTITY_KEYS,
        "native child observation source_identity",
    )
    source["owner_generation"] = _positive_int(
        source["owner_generation"], "native child source owner_generation"
    )
    source["lineage_generation"] = _positive_int(
        source["lineage_generation"], "native child source lineage_generation"
    )
    for key in ("lineage_id", "session_uuid", "runner_incarnation", "invocation_id"):
        source[key] = _bounded_id(
            source[key], "native child source %s" % key
        )
    if source["session_uuid"] != frame["session_id"]:
        raise _error(
            "ownership-conflict",
            "native child observation source session changed",
        )
    if source["runner_incarnation"] != frame["runner_instance_id"]:
        raise _error(
            "stale-generation",
            "native child observation source runner changed",
        )
    observation["source_identity"] = source
    observation["context_binding_digest"] = _native_digest(
        observation["context_binding_digest"],
        "native child observation context_binding_digest",
    )
    observation["claim_digest"] = _native_digest(
        observation["claim_digest"],
        "native child observation claim_digest",
    )
    observation["observation_watermark"] = _positive_int(
        observation["observation_watermark"],
        "native child observation watermark",
    )
    outcome = observation["terminal_outcome"]
    if outcome is not None:
        outcome = _bounded_id(outcome, "native child terminal outcome")
        if outcome not in _NATIVE_CHILD_TERMINAL_OUTCOMES:
            raise _error("invalid", "native child terminal outcome is unsupported")
    observation["terminal_outcome"] = outcome
    child = _native_child_observation_projection(observation["child"])
    if child["invocation_id"] != source["invocation_id"]:
        raise _error(
            "stale-generation",
            "native child projection invocation is not its source",
        )
    if child["start_watermark"] >= observation["observation_watermark"]:
        raise _error(
            "stale-generation",
            "native child observation watermark is stale",
        )
    task_start_watermark = child["task_start_event"]["watermark"]
    if task_start_watermark > observation["observation_watermark"]:
        raise _error(
            "stale-generation",
            "native child task start watermark exceeds observation",
        )
    if (
        child["status"] != "active"
        and child["terminal_watermark"] > observation["observation_watermark"]
    ):
        raise _error(
            "stale-generation",
            "native child terminal watermark exceeds observation",
        )
    if (
        child["status"] != "active"
        and child["terminal_watermark"] < task_start_watermark
    ):
        raise _error(
            "stale-generation",
            "native child terminal watermark predates task start",
        )
    if child["status"] == "active":
        if outcome is not None:
            raise _error("invalid", "active native child has a terminal outcome")
    elif outcome is None:
        raise _error("invalid", "terminal native child has no outcome")
    elif child["status"] == "completed" and outcome != "completed":
        raise _error(
            "stale-generation",
            "completed native child has a different outcome",
        )
    elif child["status"] == "stopped" and outcome == "completed":
        raise _error(
            "stale-generation",
            "stopped native child cannot report completion",
        )
    observation["child"] = child
    frame["observation"] = observation
    _bounded_wire(frame, "native child observation frame")
    return frame


def _native_child_observation_child_run_id(observation: Mapping[str, Any]) -> str:
    child = observation["child"]
    return _reservation_digest(
        {
            "source_identity": observation["source_identity"],
            **{
                key: child[key]
                for key in (
                    "admission_id", "tool_use_id", "agent_id", "task_id",
                    "lineage_incarnation", "start_watermark",
                )
            },
        },
        "native child observation child_run_id",
    )


def _native_child_observation_ack(
        acknowledgement: Any, observation: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate the exact controller ACK and its canonical digests."""

    _bounded_wire(acknowledgement, "native child observation acknowledgement")
    ack = _strict_object(
        acknowledgement,
        _NATIVE_CHILD_OBSERVATION_ACK_KEYS,
        _NATIVE_CHILD_OBSERVATION_ACK_KEYS,
        "native child observation acknowledgement",
    )
    if type(ack["recorded"]) is not bool or ack["recorded"] is not True:
        raise _error(
            "uncertain-effect",
            "native child observation acknowledgement was not recorded",
        )
    if ack["observation_id"] != observation["observation_id"]:
        raise _error(
            "stale-generation",
            "native child observation acknowledgement ID changed",
        )
    expected_digest = _reservation_digest(
        observation, "native child observation digest"
    )
    if ack["observation_digest"] != expected_digest:
        raise _error(
            "uncertain-effect",
            "native child observation acknowledgement digest changed",
        )
    if ack["child_run_id"] != _native_child_observation_child_run_id(observation):
        raise _error(
            "uncertain-effect",
            "native child observation child identity digest changed",
        )
    ack["observation_digest"] = _native_digest(
        ack["observation_digest"],
        "native child observation acknowledgement digest",
    )
    ack["child_run_id"] = _native_digest(
        ack["child_run_id"],
        "native child observation acknowledgement child_run_id",
    )
    ack["observation_watermark"] = _positive_int(
        ack["observation_watermark"],
        "native child observation acknowledgement watermark",
    )
    if ack["observation_watermark"] != observation["observation_watermark"]:
        raise _error(
            "stale-generation",
            "native child observation acknowledgement watermark changed",
        )
    return ack


def _validate_request(request: Any) -> dict[str, Any]:
    """Validate the complete wire identity before entering the router."""

    if not isinstance(request, Mapping):
        raise _error("invalid", "request must be an object")
    value = dict(request)
    required = {
        "schema", "schema_version", "architecture", "request_id", "lane",
        "generation", "operation", "body",
    }
    if not required.issubset(value):
        raise _error("invalid", "request is missing required fields")
    # Keep the envelope closed.  A schema-1 request represented independent
    # child owners, so accepting it (or unknown fields that might encode one)
    # would silently reinterpret another ownership model as native state.
    if set(value).difference(required):
        raise _error("schema-mismatch", "request shape is unsupported")
    if (
        type(value.get("schema")) is not int
        or value.get("schema") != SCHEMA_VERSION
        or type(value.get("schema_version")) is not int
        or value.get("schema_version") != NATIVE_SCHEMA_VERSION
        or value.get("architecture") != NATIVE_ARCHITECTURE
    ):
        raise _error("schema-mismatch", "request schema is unsupported")
    _bounded_id(value.get("request_id"), "request ID")
    lane = _bounded_id(value.get("lane"), "lane", 128)
    if lane in {".", ".."} or "/" in lane or "\\" in lane:
        raise _error("invalid", "lane is invalid")
    generation = value.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, (str, int, float)):
        raise _error("invalid", "generation is invalid")
    if isinstance(generation, str) and not generation:
        raise _error("invalid", "generation is invalid")
    if isinstance(generation, float) and not math.isfinite(generation):
        raise _error("invalid", "generation is invalid")
    _bounded_id(value.get("operation"), "operation")
    if not isinstance(value.get("body"), Mapping):
        raise _error("invalid", "request body must be an object")
    _bounded_wire(value, "request")
    value["lane"] = lane
    return value


def _json_value(value: Any) -> Any:
    """Convert controller result objects without retaining arbitrary values."""

    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        return _json_value(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _unverified_status(value: Any) -> dict[str, Any]:
    """Publish status while preventing fake evidence from becoming live proof."""

    result = _json_value(value)
    if isinstance(result, Mapping):
        result = dict(result)
    else:
        result = {"value": result}
    result["live_sdk"] = "UNVERIFIED"
    result["live_capability"] = "UNVERIFIED"
    result["capability_status"] = "experimental"
    result["experimental"] = True
    return result


def _runtime_idle_status(
    value: Any,
    participant_id: str,
    *,
    expected_session_id: Optional[str] = None,
    expected_runner_instance_id: Optional[str] = None,
) -> tuple[bool, str]:
    """Validate fresh adapter status before admitting a mailbox intent.

    The envelope and nested evidence are not an identity authority by
    themselves.  The pump supplies the session/runner incarnation read from
    the durable dispatch candidate and this check requires both identities to
    match that durable record before the controller can write an intent.
    """

    if not isinstance(value, Mapping):
        return False, "status-malformed"
    evidence = value.get("evidence")
    if not isinstance(evidence, Mapping):
        return False, "status-evidence-missing"
    if value.get("participant_id") != participant_id:
        return False, "status-participant-mismatch"
    if evidence.get("participant_id") != participant_id:
        return False, "status-participant-mismatch"
    session_id = value.get("session_id")
    evidence_session_id = evidence.get("session_id")
    runner_instance_id = value.get("runner_instance_id")
    evidence_runner_instance_id = evidence.get("runner_instance_id")
    if (
        not isinstance(session_id, str)
        or not session_id
        or evidence_session_id != session_id
        or not isinstance(runner_instance_id, str)
        or not runner_instance_id
        or evidence_runner_instance_id != runner_instance_id
    ):
        return False, "status-identity-missing"
    if expected_session_id is None or expected_runner_instance_id is None:
        return False, "status-durable-identity-missing"
    if session_id != expected_session_id:
        return False, "status-session-mismatch"
    if runner_instance_id != expected_runner_instance_id:
        return False, "status-runner-mismatch"
    required_flags = {
        "ready": True,
        "released": True,
        "active_turn": False,
        "turn_terminal": True,
        "drained": True,
        "participant_quiescent": True,
        "tools_quiescent": True,
        "quiescent": True,
    }
    if any(
        not isinstance(evidence.get(name), bool) or evidence.get(name) is not expected
        for name, expected in required_flags.items()
    ):
        return False, "status-not-idle"
    if evidence.get("tools") is not None and not isinstance(evidence.get("tools"), list):
        return False, "status-tools-malformed"
    if evidence.get("tools") is None:
        return False, "status-tools-missing"
    if evidence.get("uncertain_effects") != []:
        return False, "status-uncertain"
    if evidence.get("uncertain_effects_overflow") is not False:
        return False, "status-uncertain"
    process = evidence.get("process")
    if not isinstance(process, Mapping):
        return False, "status-process-missing"
    required_process = {
        "pid", "process_group_id", "process_start_token",
        "process_group_owned", "exited", "group_excluded",
    }
    if any(name not in process for name in required_process):
        return False, "status-process-incomplete"
    if (
        isinstance(process.get("pid"), bool)
        or not isinstance(process.get("pid"), int)
        or process.get("pid") <= 0
        or not isinstance(process.get("process_group_id"), (str, int))
        or not isinstance(process.get("process_start_token"), str)
        or not process.get("process_start_token")
        or process.get("process_group_owned") is not True
        or process.get("exited") is not False
        or process.get("group_excluded") is not False
    ):
        return False, "status-process-not-owned"
    return True, ""


def _runtime_process_domain_matches(value: Mapping[str, Any], expected: str) -> bool:
    """Reject an explicitly reported foreign/unknown runner PID domain."""

    containers: list[Mapping[str, Any]] = [value]
    evidence = value.get("evidence")
    if isinstance(evidence, Mapping):
        containers.append(evidence)
        process = evidence.get("process")
        if isinstance(process, Mapping):
            containers.append(process)
    for container in containers:
        if "process_domain" not in container:
            continue
        process_domain = container.get("process_domain")
        if not isinstance(process_domain, str) or process_domain != expected:
            return False
    return True


def _response(request: Mapping[str, Any], *, result: Any = None,
              error: Optional[BaseException] = None) -> dict[str, Any]:
    response: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "schema_version": NATIVE_SCHEMA_VERSION,
        "architecture": NATIVE_ARCHITECTURE,
        "request_id": request.get("request_id"),
        "generation": request.get("generation"),
    }
    if error is not None:
        response.update({
            "ok": False,
            "code": str(getattr(error, "code", "unknown")),
            "error": "managed request was refused",
        })
        return response
    response.update({"ok": True, "result": result})
    if request.get("operation") == _STATUS_OPERATION:
        response["result"] = _unverified_status(result)
        response["live_sdk"] = "UNVERIFIED"
        response["live_capability"] = "UNVERIFIED"
        response["capability_status"] = "experimental"
        response["experimental"] = True
    return response


class ManagedDaemon:
    """Importable one-loop supervisor façade with opt-in construction.

    ``state``, ``profiles``, ``controller``, and ``adapter`` are explicit
    seams.  Supplying them is useful for local fakes and does not import the
    optional SDK.  When ``opt_in`` is true, :meth:`start` may construct missing
    production dependencies lazily; merely importing or constructing this
    class never starts a runner or claims a lane.
    """

    def __init__(self, handler: Any = None, *, state: Any = None,
                 profiles: Any = None, controller: Any = None,
                 adapter: Any = None, daemon_id: Optional[str] = None,
                 opt_in: bool = False, lane: Optional[str] = None,
                 env: Optional[Mapping[str, str]] = None,
                 helper: Any = None, runner: Any = None,
                 payload_resolver: Any = None,
                 projection: Any = None) -> None:
        # ``handler`` remains a dependency-injection seam for an already-built
        # controller.  It is not a second operation route.  The object must
        # still expose the controller's exact ``status()`` method.
        if controller is not None and handler is not None and controller is not handler:
            raise _error("invalid", "controller and handler dependencies disagree")
        self.controller = controller if controller is not None else handler
        self.state = state
        self.profiles = profiles
        self.adapter = adapter
        if not isinstance(opt_in, bool):
            raise _error("invalid", "opt_in must be boolean")
        self.opt_in = opt_in
        if daemon_id is None:
            daemon_id = "daemon-" + uuid.uuid4().hex
        self.daemon_id = _bounded_id(daemon_id, "daemon ID", 128)
        self.env = dict(os.environ if env is None else env)
        self.helper = helper
        self.runner = runner
        self.projection = projection
        if payload_resolver is not None and not callable(payload_resolver):
            raise _error("invalid", "payload resolver must be callable")
        self.payload_resolver = payload_resolver
        self.started = False
        self.owner_record: Any = None
        self._owner_enrolled = False
        self._start_on_loop = False
        self.transcript_verifier: Any = None
        self.discovery_record: Any = None
        self.discovery_identity: Optional[tuple[str, int, int, str, int, str]] = None
        self.shutdown_succeeded = False
        self._dispatch_lock: Optional[asyncio.Lock] = None
        self._dispatch_lock_loop: Any = None
        self._dispatch_wake_event: Optional[asyncio.Event] = None
        self._dispatch_pump_task: Optional[asyncio.Task[Any]] = None
        self._dispatch_pump_loop: Any = None
        self._dispatch_operation_id: Optional[str] = None
        if lane is not None:
            self.lane = _bounded_id(lane, "lane", 128)
            if self.lane in {".", ".."} or "/" in self.lane or "\\" in self.lane:
                raise _error("invalid", "lane is invalid")
        else:
            self.lane = None

    def _ensure_state(self) -> Any:
        """Resolve the durable state authority without starting a runner."""

        if self.state is not None:
            return self.state
        if self.lane is None:
            raise _error("invalid", "lane is required to construct managed state")
        try:
            from lane_managed_state import ManagedStateStore, resolve_workspace

            identity = resolve_workspace(
                self.lane,
                env=self.env,
                helper=self.helper,
                runner=self.runner,
            )
            self.state = ManagedStateStore(identity)
        except DaemonError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "unknown")
            raise _error(str(code), "managed state construction failed")
        return self.state

    def _enroll_owner(self) -> Any:
        """Acquire the durable owner before constructing runtime adapters."""

        if self._owner_enrolled:
            return self.owner_record
        state = self._ensure_state()
        enroll = getattr(state, "enroll_managed", None)
        if not callable(enroll):
            raise _error("unsupported", "managed state ownership enrollment is unavailable")
        try:
            # This synchronous state transition takes the shared lock only for
            # its own read/write.  It happens before any adapter construction
            # or future SDK/runtime await.
            process_domain = _current_process_domain()
            self.owner_record = enroll(
                self.daemon_id, process_domain=process_domain
            )
        except Exception as exc:
            code = getattr(exc, "code", "ownership-conflict")
            raise _error(str(code), "managed ownership enrollment was refused")
        if not isinstance(self.owner_record, Mapping):
            raise _error("invalid", "managed ownership enrollment returned no record")
        self._owner_enrolled = True
        return self.owner_record

    def _construct_dependencies(self) -> None:
        """Construct profile, adapter, and controller seams after enrollment."""

        # Production construction is intentionally lazy and occurs only after
        # explicit opt-in and durable ownership.  The SDK module itself is an
        # adapter boundary; its optional official dependency is imported only
        # by a runner process.
        if self.profiles is None:
            try:
                from lane_managed_profiles import ProfileResolver

                self.profiles = ProfileResolver(env=self.env)
            except Exception as exc:
                code = getattr(exc, "code", "unsupported")
                raise _error(str(code), "managed profile resolver is unavailable")

        if self.adapter is None:
            try:
                from lane_managed_sdk import SdkRunnerAdapter

                self.adapter = SdkRunnerAdapter()
            except Exception as exc:
                code = getattr(exc, "code", "unsupported")
                raise _error(str(code), "managed runner adapter is unavailable")

        profiles = self.profiles
        resolve_profile = getattr(profiles, "resolve", None)
        verify_transcript = getattr(profiles, "verify_transcript", None)
        if callable(resolve_profile) and callable(verify_transcript):
            # Bind the exact production dependency boundary.  The controller
            # receives a three-argument callable; only this closure resolves
            # the profile reference before asking the profile authority for
            # canonical transcript/holder facts.
            self.transcript_verifier = lambda profile_name, session_id, workspace: (
                profiles.verify_transcript(
                    profiles.resolve(profile_name), session_id, workspace
                )
            )

        if self.controller is None:
            if not callable(self.transcript_verifier):
                # A controller without the profile-owned transcript verifier
                # would turn client/body evidence into an authority.  Refuse
                # until both sides of the exact construction API are present.
                raise _error("unsupported", "managed transcript verifier is unavailable")
            if self.payload_resolver is None:
                self.payload_resolver = resolve_payload_reference
            try:
                from lane_managed_controller import ManagedController

                self.controller = ManagedController(
                    self.state,
                    runtime=self.adapter,
                    payload_resolver=self.payload_resolver,
                    transcript_verifier=self.transcript_verifier,
                    _native_stop_daemon_id=self.daemon_id,
                    _coordinator_interrupt_daemon_id=self.daemon_id,
                )
            except Exception as exc:
                code = getattr(exc, "code", "unsupported")
                raise _error(str(code), "managed controller transcript verifier is unavailable")

        # The controller needs the adapter during construction, while native
        # hook admission needs the finished controller.  Bind only now; never
        # construct a second controller or populate trusted context from an
        # incoming admission.  Adapters without this capability still refuse
        # native launch through their existing missing-authority boundary.
        bind_admission = getattr(self.adapter, "bind_native_admission", None)
        if callable(bind_admission):
            bind_admission(self._admit_native_callback)

        bind_stop = getattr(self.adapter, "bind_native_stop", None)
        if callable(bind_stop):
            bind_stop(
                self._persist_native_stop_intent_callback,
                self._persist_native_stop_evidence_callback,
            )

        bind_coordinator_interrupt = getattr(
            self.adapter, "bind_coordinator_interrupt", None
        )
        if callable(bind_coordinator_interrupt):
            bind_coordinator_interrupt(
                self._persist_coordinator_interrupt_intent_callback,
                self._persist_coordinator_interrupt_evidence_callback,
            )

        # Native startup binds the exact durable mailbox ID immediately
        # before the first coordinator query.  Current SDK adapters may use
        # the controller's dispatch boundary directly; adapters that expose
        # the explicit callback receive the same authenticated seam here.
        bind_native_invocation = getattr(self.adapter, "bind_native_invocation", None)
        if callable(bind_native_invocation):
            bind_native_invocation(self._prepare_native_invocation_callback)

        # Native swap release authorization is a private authenticated runner
        # seam.  Adapters without this exact capability continue to refuse
        # native release in their own missing-callback boundary; there is no
        # legacy release or public capability fallback here.
        bind_native_swap_release = getattr(
            self.adapter, "bind_native_swap_release", None
        )
        if callable(bind_native_swap_release):
            bind_native_swap_release(
                self._authorize_native_swap_release_callback
            )

        # Native child observations are a private producer seam.  Bind only
        # the exact callback when an adapter exposes it; the callback stores
        # no child route or lifecycle capability and adapters without the seam
        # retain their existing unsupported boundary.
        bind_native_child_observation = getattr(
            self.adapter, "bind_native_child_observation", None
        )
        if callable(bind_native_child_observation):
            bind_native_child_observation(
                self._persist_native_child_observation_callback
            )

        bind_coordinator_validation = getattr(
            self.adapter, "bind_coordinator_interrupt_validation", None
        )
        if callable(bind_coordinator_validation):
            bind_coordinator_validation(self._validate_coordinator_interrupt_callback)

    async def start(self) -> "ManagedDaemon":
        """Explicitly construct dependencies and acquire durable ownership."""

        if not self.opt_in:
            raise _error("unsupported", "managed daemon startup requires explicit opt-in")
        if self.started:
            return self

        self._ensure_state()
        self._enroll_owner()

        self._construct_dependencies()
        self.started = True
        return self

    @staticmethod
    def _owner_generation(owner: Any) -> int:
        if not isinstance(owner, Mapping):
            raise _error("invalid", "managed owner record is unavailable")
        generation = owner.get("generation")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise _error("invalid", "managed owner generation is malformed")
        return generation

    def _bound_lane_for_request(self, request_lane: str) -> str:
        """Return the canonical durable lane used by guard identity fields."""

        candidates: list[Any] = []
        if self.lane is not None:
            candidates.append(self.lane)
        if isinstance(self.owner_record, Mapping):
            candidates.append(self.owner_record.get("lane"))
        state = self._ensure_state()
        identity = getattr(state, "identity", None)
        if identity is not None:
            candidates.append(getattr(identity, "lane", None))
        durable_lane = next(
            (value for value in candidates if isinstance(value, str) and value),
            None,
        )
        if durable_lane is None:
            raise _error("unknown", "canonical durable lane identity is unavailable")
        durable_lane = _bounded_id(durable_lane, "bound_lane", 128)
        if (
            durable_lane in {".", ".."}
            or "/" in durable_lane
            or "\\" in durable_lane
        ):
            raise _error("invalid", "canonical durable lane identity is malformed")
        if durable_lane.casefold() != request_lane.casefold():
            raise _error("stale-generation", "request lane is not the durable bound lane")
        return durable_lane

    def _projection_context(self) -> dict[str, Any]:
        """Build the exact non-secret managed-owner projection arguments."""

        if self.lane is None:
            raise _error("invalid", "managed projection requires a canonical lane")
        owner = self.owner_record
        if not isinstance(owner, Mapping):
            raise _error("unknown", "managed projection has no enrolled owner")
        generation = self._owner_generation(owner)
        return {
            "lane": self.lane,
            "mode": "managed",
            "daemon_id": self.daemon_id,
            "generation": generation,
            "bound_lane": self.lane,
        }

    def _projection_executable(self) -> Path:
        """Resolve the supported lanes-edit helper without a shell."""

        selected = self.env.get("LANES_EDIT")
        if selected:
            if os.path.sep not in selected:
                resolved = shutil.which(selected)
            else:
                resolved = selected
        else:
            resolved = shutil.which("lanes-edit.sh")
            if not resolved:
                adjacent = Path(__file__).with_name("lanes-edit.sh")
                resolved = str(adjacent) if adjacent.exists() else None
        if not resolved:
            raise _error("unsupported", "managed-owner projection helper is unavailable")
        path = Path(resolved)
        try:
            info = path.lstat()
        except OSError:
            raise _error("unknown", "managed-owner projection helper cannot be inspected")
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise _error("unsupported", "managed-owner projection helper is not a regular file")
        if not os.access(str(path), os.X_OK):
            raise _error("unsupported", "managed-owner projection helper is not executable")
        return path

    def preflight_projection(self) -> None:
        """Check projection capability before durable local owner enrollment."""

        context = {
            "lane": self.lane,
            "mode": "managed",
            "daemon_id": self.daemon_id,
            "bound_lane": self.lane,
        }
        if self.projection is not None:
            method = getattr(self.projection, "preflight", None)
            if not callable(method):
                raise _error("unsupported", "managed-owner projection preflight is unavailable")
            try:
                result = method(dict(context))
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                code = str(getattr(exc, "code", "unknown"))
                raise _error(code, "managed-owner projection preflight was refused")
            if result is False:
                raise _error("unsupported", "managed-owner projection preflight was refused")
            return
        path = self._projection_executable()
        try:
            source = path.read_bytes()
        except OSError:
            raise _error("unknown", "managed-owner projection helper cannot be read")
        if len(source) > MAX_FRAME_BYTES:
            raise _error("unsupported", "managed-owner projection helper is unbounded")
        text_source = source.decode("utf-8", "replace")
        if "managed-owner)" not in text_source or "managed-clear)" not in text_source:
            raise _error("unsupported", "managed-owner projection capability is unavailable")

    def project_owner(self) -> Any:
        """Write the managed-owner projection after local enrollment."""

        context = self._projection_context()
        if self.projection is not None:
            method = getattr(self.projection, "managed_owner", None)
            if not callable(method):
                raise _error("unsupported", "managed-owner projection writer is unavailable")
            try:
                result = method(dict(context))
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                code = str(getattr(exc, "code", "unknown"))
                raise _error(code, "managed-owner projection was refused")
            if result is False:
                raise _error("unknown", "managed-owner projection was not confirmed")
            return result
        path = self._projection_executable()
        args = [
            str(path), "managed-owner", context["lane"],
            "--mode", "managed", "--daemon-id", context["daemon_id"],
            "--generation", str(context["generation"]),
            "--bound-lane", context["bound_lane"],
        ]
        try:
            result = subprocess.run(
                args,
                env=dict(self.env),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=PROJECTION_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise _error("unknown", "managed-owner projection timed out")
        except (OSError, ValueError):
            raise _error("unknown", "managed-owner projection could not be run")
        if result.returncode != 0:
            raise _error("unknown", "managed-owner projection was refused")
        return {"projected": True, **context}

    def clear_owner_projection(self) -> Any:
        """Clear the managed-owner projection after authoritative quiescence."""

        context = self._projection_context()
        clear_context = dict(context)
        clear_context["authoritative_unenroll"] = True
        if self.projection is not None:
            method = getattr(self.projection, "managed_clear", None)
            if not callable(method):
                raise _error(
                    "unsupported",
                    "managed-owner projection clear writer is unavailable",
                )
            try:
                result = method(dict(clear_context))
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                code = str(getattr(exc, "code", "unknown"))
                raise _error(code, "managed-owner projection clear was refused")
            if result is False:
                raise _error(
                    "unknown",
                    "managed-owner projection clear was not confirmed",
                )
            return result

        path = self._projection_executable()
        args = [
            str(path), "managed-clear", context["lane"],
            "--mode", "managed", "--daemon-id", context["daemon_id"],
            "--generation", str(context["generation"]),
            "--bound-lane", context["bound_lane"],
            "--authoritative-unenroll",
        ]
        try:
            result = subprocess.run(
                args,
                env=dict(self.env),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=PROJECTION_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise _error("unknown", "managed-owner projection clear timed out")
        except (OSError, ValueError):
            raise _error("unknown", "managed-owner projection clear could not be run")
        if result.returncode != 0:
            raise _error("unknown", "managed-owner projection clear was refused")
        return {"cleared": True, **clear_context}

    def register_runtime(self, socket_path: str | os.PathLike[str]) -> Any:
        """Publish this daemon's endpoint using the exact durable identity."""

        if not self.opt_in:
            raise _error("unsupported", "managed daemon startup requires explicit opt-in")
        state = self._ensure_state()
        owner = self._enroll_owner()
        generation = self._owner_generation(owner)
        pid, start_token, pgid = _current_process_identity()
        process_domain = _current_process_domain()
        register = getattr(state, "register_runtime", None)
        if not callable(register):
            raise _error("unsupported", "managed runtime discovery registration is unavailable")
        try:
            record = register(
                daemon_id=self.daemon_id,
                generation=generation,
                pid=pid,
                start_token=start_token,
                pgid=pgid,
                process_domain=process_domain,
                socket_path=socket_path,
            )
        except Exception as exc:
            code = getattr(exc, "code", "unknown")
            raise _error(str(code), "managed runtime discovery registration was refused")
        if not isinstance(record, Mapping):
            raise _error("invalid", "managed runtime discovery returned no record")
        self.discovery_record = dict(record)
        self.discovery_identity = (
            self.daemon_id, generation, pid, start_token, pgid, process_domain
        )
        return self.discovery_record

    def clear_runtime(self) -> Any:
        """Clear only the exact endpoint published by this daemon."""

        if self.discovery_identity is None:
            return None
        state = self._ensure_state()
        clear = getattr(state, "clear_runtime", None)
        if not callable(clear):
            raise _error("unsupported", "managed runtime discovery cleanup is unavailable")
        daemon_id, generation, pid, start_token, pgid, process_domain = (
            self.discovery_identity
        )
        try:
            result = clear(
                daemon_id=daemon_id,
                generation=generation,
                pid=pid,
                start_token=start_token,
                pgid=pgid,
                process_domain=process_domain,
            )
        except Exception as exc:
            code = getattr(exc, "code", "unknown")
            raise _error(str(code), "managed runtime discovery cleanup was refused")
        self.discovery_record = None
        self.discovery_identity = None
        return result

    def _dispatch_lock_for_loop(self) -> asyncio.Lock:
        """Return a lock owned by the daemon's persistent asyncio loop."""

        loop = asyncio.get_running_loop()
        if self._dispatch_lock is None or self._dispatch_lock_loop is not loop:
            self._dispatch_lock = asyncio.Lock()
            self._dispatch_lock_loop = loop
        return self._dispatch_lock

    def _runtime_adapter(self) -> Any:
        """Return the injected adapter; controller runtime is only a seam fallback."""

        if self.adapter is not None:
            return self.adapter
        return getattr(self.controller, "runtime", None)

    async def _durable_dispatch_identity(
        self,
        operation_id: str,
        candidate: Mapping[str, Any],
        deadline: float,
    ) -> tuple[str, str, str]:
        """Read the candidate's canonical session/runner identity.

        ``dispatch_candidates`` intentionally returns only mailbox and
        recipient IDs.  Before asking the runtime whether that recipient is
        idle, obtain the identity from the controller's durable projection so
        a forged envelope that agrees with its own nested evidence cannot
        authorize a send.  This read is an internal admission check; the
        public observational ``status`` route never wakes the pump.
        """

        participant_id = _bounded_id(
            candidate.get("recipient_id"), "dispatch recipient_id"
        )
        supplied_session = candidate.get("session_id")
        supplied_runner = candidate.get("runner_instance_id")
        if supplied_session is not None or supplied_runner is not None:
            # A future controller may include the identity in its exact
            # candidate projection.  Accept that projection only when both
            # fields are present and well-formed; the runtime envelope is
            # still checked against them below.  A single caller-supplied
            # field is never enough to establish an identity.
            if (
                not isinstance(supplied_session, str)
                or not supplied_session
                or not isinstance(supplied_runner, str)
                or not supplied_runner
            ):
                raise _error("unknown", "dispatch candidate identity is incomplete")
            return participant_id, supplied_session, supplied_runner
        status_method = getattr(self.controller, "status", None)
        if not callable(status_method):
            raise _error(
                "unsupported", "managed dispatch identity authority is unavailable"
            )
        durable = status_method()
        durable = await _await_bounded(
            durable, deadline, "dispatch durable identity read"
        )
        if not isinstance(durable, Mapping):
            raise _error("unknown", "dispatch durable identity is malformed")
        operation = durable.get("operation")
        if not isinstance(operation, Mapping):
            operation = durable.get("active_operation")
        if not isinstance(operation, Mapping):
            raise _error("stale-generation", "dispatch operation is no longer durable")
        if operation.get("operation_id") != operation_id:
            raise _error("stale-generation", "dispatch operation identity changed")
        if operation.get("phase") != "released":
            raise _error("busy", "dispatch operation is not released")
        metadata = operation.get("metadata")
        if not isinstance(metadata, Mapping):
            raise _error("unknown", "dispatch durable metadata is malformed")
        runner_instances = metadata.get("runner_instances")
        if not isinstance(runner_instances, Mapping):
            raise _error("unknown", "dispatch runner identity ledger is unavailable")
        runner_instance_id = runner_instances.get(participant_id)
        if not isinstance(runner_instance_id, str) or not runner_instance_id:
            raise _error("unknown", "dispatch runner identity is unavailable")
        participants = durable.get("participants")
        if not isinstance(participants, list):
            participants = durable.get("roster")
        if not isinstance(participants, list):
            raise _error("unknown", "dispatch participant roster is unavailable")
        participant: Optional[Mapping[str, Any]] = None
        for item in participants:
            if not isinstance(item, Mapping):
                raise _error("unknown", "dispatch participant roster is malformed")
            if item.get("participant_id") == participant_id:
                participant = item
                break
        if participant is None:
            raise _error("unknown", "dispatch recipient is no longer enrolled")
        session_id = participant.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise _error("unknown", "dispatch participant session identity is unavailable")
        if supplied_session is not None and supplied_session != session_id:
            raise _error("stale-generation", "dispatch candidate session identity changed")
        if supplied_runner is not None and supplied_runner != runner_instance_id:
            raise _error("stale-generation", "dispatch candidate runner identity changed")
        return participant_id, session_id, runner_instance_id

    def _wake_dispatch_pump(self, operation_id: Any) -> None:
        """Wake or create the persistent same-loop dispatch pump.

        The transport invokes the handler on one owning asyncio loop.  This
        seam only schedules work on that loop; it never creates a second loop
        or runs runtime/controller code synchronously from a client thread.
        """

        operation_id = _bounded_id(operation_id, "operation_id")
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # A direct one-shot caller has no persistent supervisor loop.  Its
            # explicit release/submit path still performs the bounded inline
            # tick, while production transport calls always have a loop.
            return
        if self._dispatch_pump_loop is not loop:
            self._dispatch_pump_loop = loop
            self._dispatch_wake_event = asyncio.Event()
            self._dispatch_pump_task = None
        if self._dispatch_wake_event is None:
            self._dispatch_wake_event = asyncio.Event()
        self._dispatch_operation_id = operation_id
        self._dispatch_wake_event.set()
        task = self._dispatch_pump_task
        if task is None or task.done():
            self._dispatch_pump_task = asyncio.create_task(
                self._dispatch_pump_worker()
            )

    async def _dispatch_pump_worker(self) -> None:
        """Keep released eligible mail moving while clients are idle.

        A wake from release/submit starts the worker immediately.  When a
        recipient is busy, the worker performs bounded fresh status reads
        separated by ``DISPATCH_WAKE_INTERVAL`` until the recipient becomes
        idle.  Once candidates are exhausted it exits and waits for a future
        durable submit/release wake, avoiding an unbounded idle poll.
        """

        task = asyncio.current_task()
        first_pass = True
        try:
            while True:
                event = self._dispatch_wake_event
                if event is None:
                    return
                if not first_pass:
                    # Clear before waiting.  A wake that arrives while the
                    # previous tick is awaiting runtime I/O remains set and
                    # is observed by this wait rather than being erased.
                    event.clear()
                    try:
                        await asyncio.wait_for(
                            event.wait(), timeout=DISPATCH_WAKE_INTERVAL
                        )
                    except asyncio.TimeoutError:
                        pass
                first_pass = False
                operation_id = self._dispatch_operation_id
                if operation_id is None:
                    return
                try:
                    result = await self.dispatch_pump_tick(
                        operation_id,
                        deadline=time.monotonic() + DISPATCH_PUMP_TIMEOUT,
                    )
                except asyncio.CancelledError:
                    raise
                except BaseException:
                    # A controller refusal, stale generation, or uncertain
                    # effect is already durable (or fail-closed).  Do not
                    # turn a background observation into an automatic retry.
                    return
                dispatched = result.get("dispatched")
                skipped = result.get("skipped")
                if isinstance(dispatched, list) and dispatched:
                    # A tick grants at most one message per recipient.  Give
                    # the runtime a bounded idle interval before the next
                    # tick so a second message for that recipient is admitted
                    # only after fresh readiness evidence.
                    continue
                if isinstance(skipped, list) and any(
                    isinstance(item, Mapping) and item.get("code") == "busy"
                    for item in skipped
                ):
                    # A busy recipient remains a live candidate.  The next
                    # timed wake detects the runtime's busy-to-idle transition
                    # without requiring another client request.
                    continue
                return
        finally:
            if self._dispatch_pump_task is task:
                self._dispatch_pump_task = None

    def _reconcile_dispatch_intent(self, message_id: str) -> Any:
        """Mark a timed-out/cancelled dispatch uncertain before any next mutation."""

        recover = getattr(self.controller, "recover_dispatch", None)
        if not callable(recover):
            raise _error(
                "unsupported",
                "managed dispatch reconciliation is unavailable",
            )
        try:
            # No public/body proof is accepted here.  Absence of an
            # authoritative no-send receipt must leave the durable intent
            # uncertain, never queued for an automatic retry.
            return recover(message_id)
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise _error(
                "uncertain-effect",
                "dispatch reconciliation was not durable",
            ) from exc

    async def dispatch_pump_tick(
        self,
        operation_id: str,
        *,
        max_iterations: int = DISPATCH_PUMP_MAX_ITERATIONS,
        deadline: Optional[float] = None,
    ) -> dict[str, Any]:
        """Dispatch eligible released mail once per idle recipient.

        The controller's candidate read and recipient-scoped dispatch call are
        the only durable admission APIs.  A fresh adapter status is collected
        before every intent; busy/held/uncertain recipients are skipped so an
        independent idle recipient can proceed.  The short daemon lock
        serializes pump ticks, while the controller's own transaction lock is
        never held across a runtime await.
        """

        operation_id = _bounded_id(operation_id, "operation_id")
        if (
            isinstance(max_iterations, bool)
            or not isinstance(max_iterations, int)
            or max_iterations <= 0
            or max_iterations > DISPATCH_PUMP_MAX_ITERATIONS
        ):
            raise _error("invalid", "dispatch pump iteration bound is invalid")
        if deadline is None:
            absolute_deadline = time.monotonic() + DISPATCH_PUMP_TIMEOUT
        else:
            if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
                raise _error("invalid", "dispatch pump deadline is invalid")
            if not math.isfinite(float(deadline)):
                raise _error("invalid", "dispatch pump deadline is invalid")
            absolute_deadline = float(deadline)
        result: dict[str, Any] = {
            "operation_id": operation_id,
            "iterations": 0,
            "dispatched": [],
            "skipped": [],
            "bounded": False,
        }
        status_method = getattr(self._runtime_adapter(), "status", None)
        candidates_method = getattr(self.controller, "dispatch_candidates", None)
        dispatch_method = getattr(self.controller, "dispatch_next", None)
        if not callable(candidates_method) or not callable(dispatch_method):
            raise _error("unsupported", "managed dispatch pump controller API is unavailable")
        if not callable(status_method):
            result["bounded"] = True
            result["skipped"].append({"code": "unsupported", "reason": "runtime-status-unavailable"})
            return result

        lock = self._dispatch_lock_for_loop()
        async with lock:
            dispatched_recipients: set[str] = set()
            blocked_recipients: set[str] = set()
            while result["iterations"] < max_iterations:
                if time.monotonic() >= absolute_deadline:
                    result["bounded"] = True
                    break
                candidates = candidates_method(operation_id)
                candidates = await _await_bounded(
                    candidates, absolute_deadline, "dispatch candidate read"
                )
                if not isinstance(candidates, list):
                    raise _error("invalid", "managed dispatch candidates are malformed")
                if not candidates:
                    break
                made_dispatch = False
                for candidate in candidates:
                    if result["iterations"] >= max_iterations:
                        result["bounded"] = True
                        break
                    if time.monotonic() >= absolute_deadline:
                        result["bounded"] = True
                        break
                    if not isinstance(candidate, Mapping):
                        raise _error("invalid", "managed dispatch candidate is malformed")
                    message_id = _bounded_id(candidate.get("message_id"), "message_id")
                    recipient_id = _bounded_id(candidate.get("recipient_id"), "recipient_id")
                    if recipient_id in blocked_recipients:
                        continue
                    if recipient_id in dispatched_recipients:
                        # One message per recipient per tick prevents an
                        # accepted send from becoming an implicit readiness
                        # proof for the next queued message.
                        continue
                    result["iterations"] += 1
                    try:
                        (
                            durable_recipient_id,
                            expected_session_id,
                            expected_runner_instance_id,
                        ) = await self._durable_dispatch_identity(
                            operation_id,
                            candidate,
                            absolute_deadline,
                        )
                        runtime_status = status_method(recipient_id)
                        runtime_status = await _await_bounded(
                            runtime_status,
                            absolute_deadline,
                            "runtime status",
                        )
                    except BaseException as exc:
                        if isinstance(exc, asyncio.CancelledError):
                            raise
                        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                            raise
                        blocked_recipients.add(recipient_id)
                        result["skipped"].append({
                            "recipient_id": recipient_id,
                            "message_id": message_id,
                            "code": str(getattr(exc, "code", "unknown")),
                            "reason": "dispatch-identity-or-status-unavailable",
                        })
                        continue
                    idle, reason = _runtime_idle_status(
                        runtime_status,
                        durable_recipient_id,
                        expected_session_id=expected_session_id,
                        expected_runner_instance_id=expected_runner_instance_id,
                    )
                    if not idle:
                        blocked_recipients.add(recipient_id)
                        result["skipped"].append({
                            "recipient_id": recipient_id,
                            "message_id": message_id,
                            "code": "busy",
                            "reason": reason,
                        })
                        continue
                    try:
                        dispatch_result = dispatch_method(
                            operation_id,
                            recipient_id=recipient_id,
                        )
                        dispatch_result = await _await_bounded(
                            dispatch_result,
                            absolute_deadline,
                            "managed dispatch",
                        )
                    except asyncio.CancelledError:
                        self._reconcile_dispatch_intent(message_id)
                        raise
                    except BaseException as exc:
                        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                            raise
                        code = str(getattr(exc, "code", "uncertain-effect"))
                        if code in {"timeout", "uncertain-effect"}:
                            self._reconcile_dispatch_intent(message_id)
                        blocked_recipients.add(recipient_id)
                        result["skipped"].append({
                            "recipient_id": recipient_id,
                            "message_id": message_id,
                            "code": code,
                            "reason": "dispatch-not-acknowledged",
                        })
                        continue
                    if dispatch_result is None:
                        blocked_recipients.add(recipient_id)
                        result["skipped"].append({
                            "recipient_id": recipient_id,
                            "message_id": message_id,
                            "code": "busy",
                            "reason": "dispatch-not-admitted",
                        })
                        continue
                    from lane_managed_controller import MailboxEntry

                    if isinstance(dispatch_result, MailboxEntry):
                        metadata = dispatch_result.to_dict()
                    elif isinstance(dispatch_result, Mapping):
                        metadata = _json_value(dispatch_result)
                    else:
                        raise _error("invalid", "managed dispatch result is malformed")
                    _bounded_wire(metadata, "dispatch metadata")
                    result["dispatched"].append(metadata)
                    dispatched_recipients.add(recipient_id)
                    made_dispatch = True
                if not made_dispatch:
                    break
            if result["iterations"] >= max_iterations:
                result["bounded"] = True
            _bounded_wire(result, "dispatch pump result")
            return result

    async def _collect_recovery_evidence(
            self,
            operation_id: str,
            generation: Any,
            deadline: Optional[float],
    ) -> dict[str, Any]:
        """Collect fresh, stage-labelled evidence for controller recovery.

        A generic ``{"status": runtime_status}`` wrapper is unsafe here:
        recovery must know whether a fact describes an old runner's
        quiescence/exclusion or the target runner's open/release lifecycle.
        The durable operation mode, per-participant launch intent, and
        canonical old/new runner ledgers choose the stage; the adapter result
        only supplies fresh facts for that already-recorded identity.  Public
        request evidence never enters this function.
        """

        absolute_deadline = (
            time.monotonic() + DISPATCH_PUMP_TIMEOUT
            if deadline is None
            else float(deadline)
        )
        # Establish the supervisor's own native PID domain before asking any
        # adapter to observe a recovery handle.  A foreign/unknown domain is
        # never converted into a PID-absence or process-death conclusion.
        recovery_process_domain = _current_process_domain()
        status_method = getattr(self.controller, "status", None)
        runtime_status = getattr(self._runtime_adapter(), "status", None)
        if not callable(status_method):
            raise _error("unsupported", "managed controller status is unavailable")
        if not callable(runtime_status):
            raise _error("unsupported", "managed runtime status is unavailable")
        durable = status_method()
        durable = await _await_bounded(durable, absolute_deadline, "managed recovery status")
        if not isinstance(durable, Mapping):
            raise _error("invalid", "managed recovery status is malformed")
        operation = self._recovery_operation_projection(durable)
        if not isinstance(operation, Mapping):
            raise _error("unknown", "managed recovery operation is unavailable")
        if operation.get("operation_id") != operation_id:
            raise _error("stale-generation", "recovery does not match the current operation")
        if operation.get("generation") != generation:
            raise _error("stale-generation", "recovery does not match the current generation")
        sealed = operation.get("sealed_participants")
        if not isinstance(sealed, list) or not sealed:
            raise _error("invalid", "managed recovery roster is unavailable")
        roster = durable.get("participants")
        roster_by_id: dict[str, Mapping[str, Any]] = {}
        archived_roster = durable.get("archived_participants")
        for roster_name, roster_value in (
            ("participants", roster),
            ("archived participants", archived_roster),
        ):
            if roster_value is None:
                continue
            if not isinstance(roster_value, list):
                raise _error("invalid", "managed recovery %s are malformed" % roster_name)
            for raw_participant in roster_value:
                if not isinstance(raw_participant, Mapping):
                    raise _error("invalid", "managed recovery roster is malformed")
                raw_id = raw_participant.get("participant_id")
                if not isinstance(raw_id, str) or not raw_id:
                    raise _error("invalid", "managed recovery roster identity is malformed")
                previous = roster_by_id.get(raw_id)
                if previous is not None and _json_value(previous) != _json_value(raw_participant):
                    raise _error("invalid", "managed recovery roster repeats an identity")
                roster_by_id[raw_id] = raw_participant
        metadata = operation.get("metadata")
        if not isinstance(metadata, Mapping):
            raise _error("invalid", "managed recovery operation metadata is malformed")
        mode = operation.get("mode")
        if not isinstance(mode, str) or not mode:
            raise _error("invalid", "managed recovery operation mode is malformed")
        ctx_intent = metadata.get("ctx_intent")
        ctx_old_id: Optional[str] = None
        ctx_target_id: Optional[str] = None
        if mode == "ctx":
            if not isinstance(ctx_intent, Mapping):
                raise _error("invalid", "managed ctx recovery intent is malformed")
            ctx_old_id = _bounded_id(
                ctx_intent.get("old_coordinator_id"),
                "managed ctx old coordinator_id",
            )
            ctx_target_id = _bounded_id(
                ctx_intent.get("new_coordinator_id"),
                "managed ctx new coordinator_id",
            )
            if ctx_old_id == ctx_target_id:
                raise _error("invalid", "managed ctx recovery identities are not distinct")
            if ctx_old_id not in roster_by_id:
                raise _error("unknown", "managed ctx archived coordinator identity is unavailable")
        launch_intents = metadata.get("launch_intents", {})
        shutdown_intents = metadata.get("shutdown_intents", {})
        unenroll_intents = metadata.get("unenroll_intents", {})
        runner_instances = metadata.get("runner_instances", {})
        old_runner_instances = metadata.get("old_runner_instances", {})
        stage_maps = {
            "interrupt": metadata.get("interrupt_receipts", {}),
            "status": metadata.get("status_evidence", {}),
            "worker_status": metadata.get("worker_status_evidence", {}),
            "shutdown": metadata.get("shutdown_receipts", {}),
            "open": metadata.get("open_evidence", {}),
            "release": metadata.get("release_receipts", {}),
        }
        for name, value in {
            "launch intents": launch_intents,
            "shutdown intents": shutdown_intents,
            "unenroll intents": unenroll_intents,
            "runner identities": runner_instances,
            "old runner identities": old_runner_instances,
            **{
                "%s evidence" % name: value
                for name, value in stage_maps.items()
            },
        }.items():
            if not isinstance(value, Mapping):
                raise _error("invalid", "managed recovery %s are malformed" % name)

        release_intent = metadata.get("release_intent")
        if release_intent is not None and not isinstance(release_intent, Mapping):
            raise _error("invalid", "managed recovery release intent is malformed")

        # Native swap owns its source/target runner identities in its private
        # durable record.  It intentionally does not populate the legacy
        # ``old_runner_instances`` map used by generic swap recovery: copying
        # one into that map would make a source or target status observation
        # look like evidence for the wrong lifecycle boundary.  Keep this
        # projection local to recovery and let the native controller consume
        # the resulting stage-labelled status/open record.
        native_swap: Optional[Mapping[str, Any]] = None
        native_swap_records: Mapping[str, Any] = {}
        native_source_runner: Optional[str] = None
        native_target_runner: Optional[str] = None
        if mode == "swap" and metadata.get("native_swap") is not None:
            candidate = metadata.get("native_swap")
            if not isinstance(candidate, Mapping):
                raise _error("invalid", "managed native swap recovery metadata is malformed")
            native_swap = candidate
            candidate_records = candidate.get("native_swap_evidence")
            if not isinstance(candidate_records, Mapping):
                raise _error(
                    "invalid", "managed native swap recovery evidence ledger is malformed"
                )
            native_swap_records = candidate_records
            source_identity = candidate.get("source_identity")
            if not isinstance(source_identity, Mapping):
                raise _error(
                    "invalid", "managed native swap recovery source identity is malformed"
                )
            native_source_runner = source_identity.get("runner_incarnation")
            if not isinstance(native_source_runner, str) or not native_source_runner:
                raise _error(
                    "unknown", "managed native swap recovery source runner identity is unavailable"
                )
            target_runner = candidate.get("target_runner_incarnation")
            if not isinstance(target_runner, str) or not target_runner:
                raise _error(
                    "unknown", "managed native swap recovery target runner identity is unavailable"
                )
            native_target_runner = target_runner

        def _runner_identity(
            values: Mapping[str, Any], participant_id: str, label: str
        ) -> Optional[str]:
            value = values.get(participant_id)
            if value is None:
                return None
            if not isinstance(value, str) or not value:
                raise _error("invalid", "%s runner identity is malformed" % label)
            return value

        def _stage_value(
            name: str, participant_id: str
        ) -> Optional[Mapping[str, Any]]:
            value = stage_maps[name].get(participant_id)
            if value is None:
                return None
            if not isinstance(value, Mapping):
                raise _error(
                    "invalid", "managed recovery %s evidence is malformed" % name
                )
            return value

        def _intent_state(participant_id: str) -> tuple[Optional[str], Optional[str]]:
            value = launch_intents.get(participant_id)
            if value is None:
                return None, None
            if not isinstance(value, Mapping):
                raise _error("invalid", "managed recovery launch intent is malformed")
            state = value.get("state")
            if state is not None and (not isinstance(state, str) or not state):
                raise _error("invalid", "managed recovery launch intent state is malformed")
            runner = value.get("runner_instance_id")
            if runner is not None and (not isinstance(runner, str) or not runner):
                raise _error("invalid", "managed recovery launch intent runner is malformed")
            return state, runner

        def _process_is_excluded(value: Mapping[str, Any]) -> bool:
            nested = value.get("evidence")
            if not isinstance(nested, Mapping):
                return False
            process = nested.get("process")
            return (
                isinstance(process, Mapping)
                and process.get("exited") is True
                and process.get("group_excluded") is True
            )

        def _observed_identity(
            value: Mapping[str, Any],
            participant_id: str,
            participant_record: Mapping[str, Any],
            expected_runner: Optional[str],
        ) -> str:
            observed_participant = value.get("participant_id")
            observed_session = value.get("session_id")
            observed_runner = value.get("runner_instance_id")
            nested = value.get("evidence")
            if not isinstance(nested, Mapping):
                raise _error("unknown", "managed recovery runtime evidence is missing")
            if observed_participant != participant_id or nested.get("participant_id") != participant_id:
                raise _error("stale-generation", "managed recovery runtime participant identity changed")
            expected_session = participant_record.get("session_id")
            if (
                not isinstance(expected_session, str)
                or not expected_session
                or observed_session != expected_session
                or nested.get("session_id") != expected_session
            ):
                raise _error("stale-generation", "managed recovery runtime session identity changed")
            if (
                not isinstance(observed_runner, str)
                or not observed_runner
                or nested.get("runner_instance_id") != observed_runner
            ):
                raise _error("unknown", "managed recovery runner identity is unavailable")
            if expected_runner is not None and observed_runner != expected_runner:
                raise _error("stale-generation", "managed recovery runner identity changed")
            return observed_runner

        subject_ids = list(sealed)
        # Ctx seals the fresh coordinator and retained workers, while the
        # retired coordinator is deliberately archived outside that roster.
        # Its old incarnation still needs independent status/exclusion proof;
        # include that exact durable identity without broadening the public
        # evidence surface.
        if mode == "ctx" and ctx_old_id is not None:
            if ctx_old_id not in subject_ids:
                subject_ids.append(ctx_old_id)

        records: dict[str, dict[str, Any]] = {}
        for raw_participant_id in subject_ids:
            participant_id = _bounded_id(raw_participant_id, "recovery participant_id")
            participant_record = roster_by_id.get(participant_id)
            if isinstance(participant_record, Mapping) and participant_record.get("state") in {
                "completed", "stopped",
            }:
                # Completed identities remain sealed historical state; they
                # have no live adapter handle to query and must not be
                # reopened merely to manufacture recovery evidence.
                if mode not in {"ctx", "shutdown", "unenroll"}:
                    continue
            intent_state, intent_runner = _intent_state(participant_id)
            new_runner = _runner_identity(
                runner_instances, participant_id, "managed recovery new"
            )
            if new_runner is None:
                new_runner = intent_runner
            old_runner = _runner_identity(
                old_runner_instances, participant_id, "managed recovery old"
            )
            if native_swap is not None:
                # The native source runner is authoritative until the durable
                # source-excluded stage.  The target runner is authoritative
                # only after the target-open intent crosses; its observed
                # instance ID is deliberately not used before that await.
                old_runner = native_source_runner
                target_open_intent = native_swap.get("target_open_intent")
                if target_open_intent is not None and not isinstance(
                    target_open_intent, Mapping
                ):
                    raise _error(
                        "invalid", "managed native swap target-open intent is malformed"
                    )
                if isinstance(target_open_intent, Mapping):
                    reserved_target = target_open_intent.get(
                        "target_runner_incarnation"
                    )
                    if reserved_target != native_target_runner:
                        raise _error(
                            "stale-generation",
                            "managed native swap target runner reservation changed",
                        )
                # ``runner_instances`` may contain the source runner until
                # target activation.  It must never override the exact target
                # reservation above; the collector only queries it when the
                # target-open intent is in progress.
                if isinstance(target_open_intent, Mapping) and target_open_intent.get(
                    "state"
                ) == "in-progress":
                    new_runner = native_target_runner
            open_evidence = _stage_value("open", participant_id)
            release_evidence = _stage_value("release", participant_id)
            shutdown_evidence = _stage_value("shutdown", participant_id)
            release_state = (
                release_intent.get("state")
                if isinstance(release_intent, Mapping)
                else None
            )
            if release_state == "in-progress" and mode not in {
                "start", "add-worker", "swap", "ctx",
            }:
                raise _error(
                    "invalid", "managed recovery has an invalid release intent"
                )

            # A completed/stopped participant is durable historical state, not
            # a reason to reopen an adapter handle merely to make an evidence
            # envelope complete.
            if participant_record is None:
                raise _error("unknown", "managed recovery participant identity is unavailable")

            stage: Optional[str] = None
            expected_runner: Optional[str] = None
            shutdown_state: Optional[str] = None
            if native_swap is not None:
                # Native swap has its own stage ledger and runtime intents.
                # Do not consult the generic shutdown/open receipt maps here:
                # the source shutdown receipt is joined to
                # ``native_swap.shutdown_intent`` and a target-open receipt is
                # joined to ``native_swap.target_open_intent``.  Selecting a
                # subject from the legacy maps can query B while expecting A
                # after a target-open crash (or the reverse).
                if "graph-drained" not in native_swap_records:
                    records[participant_id] = {}
                    continue
                if "source-excluded" not in native_swap_records:
                    shutdown_intent = native_swap.get("shutdown_intent")
                    if shutdown_intent is not None and not isinstance(
                        shutdown_intent, Mapping
                    ):
                        raise _error(
                            "invalid", "managed native swap shutdown intent is malformed"
                        )
                    if shutdown_intent is None:
                        # No shutdown intent means no shutdown call crossed
                        # its durable boundary.  The native controller keeps
                        # the operation paused and never asks us to reopen A.
                        records[participant_id] = {}
                        continue
                    shutdown_state = shutdown_intent.get("state")
                    if shutdown_state not in {"in-progress", "complete"}:
                        raise _error(
                            "invalid", "managed native swap shutdown intent state is malformed"
                        )
                    if shutdown_state == "complete":
                        # The complete intent contains the source shutdown
                        # receipt itself.  Recovery only needs to archive the
                        # already-excluded source; no fresh status handle is
                        # needed at this boundary.
                        records[participant_id] = {}
                        continue
                    stage = "status"
                    expected_runner = native_source_runner
                elif "target-held" not in native_swap_records:
                    target_open_intent = native_swap.get("target_open_intent")
                    if target_open_intent is not None and not isinstance(
                        target_open_intent, Mapping
                    ):
                        raise _error(
                            "invalid", "managed native swap target-open intent is malformed"
                        )
                    if target_open_intent is None:
                        records[participant_id] = {}
                        continue
                    if target_open_intent.get("state") != "in-progress":
                        # A ready/complete target intent has already crossed
                        # the open await and is not a fresh status subject;
                        # the controller will retain its conservative
                        # unresolved boundary until target-held is durable.
                        records[participant_id] = {}
                        continue
                    reserved_target = target_open_intent.get(
                        "target_runner_incarnation"
                    )
                    if reserved_target != native_target_runner:
                        raise _error(
                            "stale-generation",
                            "managed native swap target runner reservation changed",
                        )
                    stage = "open"
                    expected_runner = native_target_runner
                else:
                    records[participant_id] = {}
                    continue
            elif release_state == "in-progress" and release_evidence is None:
                # Release acknowledgement belongs to the current/new runner,
                # never to the old source runner from a swap.
                if not isinstance(new_runner, str) or not new_runner:
                    raise _error("unknown", "managed recovery release runner identity is unavailable")
                stage = "release"
                expected_runner = new_runner
            elif mode in {"start", "add-worker"}:
                if open_evidence is not None:
                    continue
                if intent_state == "pending" and new_runner is None:
                    # A pending launch never crossed the adapter boundary.
                    # Preserve the explicit empty record so the mode-aware
                    # controller can retain it without replaying open.
                    records[participant_id] = {}
                    continue
                if intent_state not in {"in-progress", "registered", "ready"}:
                    raise _error("unknown", "managed recovery launch intent is unavailable")
                if intent_state in {"registered", "ready"} and new_runner is None:
                    raise _error("unknown", "managed recovery registered runner identity is unavailable")
                stage = "open"
                # An in-progress intent may have opened a runner immediately
                # before the daemon crashed, before its runner ID reached the
                # durable map.  Fresh status supplies that ID; the controller
                # still validates it against the durable participant/spec.
                expected_runner = new_runner
            elif mode == "swap":
                if shutdown_evidence is None:
                    if old_runner is None:
                        raise _error("unknown", "managed recovery old runner identity is unavailable")
                    # Until shutdown is durably recorded this fact describes
                    # the old source runner.  If its fresh process proof says
                    # exited/group-excluded, label it shutdown below; an idle
                    # live process remains only quiescence status.
                    stage = "status"
                    expected_runner = old_runner
                elif open_evidence is None:
                    if intent_state not in {"pending", "in-progress", "registered", "ready"}:
                        raise _error("unknown", "managed recovery target launch intent is unavailable")
                    if intent_state == "pending" and new_runner is None:
                        # The target never crossed the adapter boundary.
                        # Preserve the pending reservation explicitly; asking
                        # status for a nonexistent handle would manufacture a
                        # recovery fact and could invite an automatic reopen.
                        records[participant_id] = {}
                        continue
                    if intent_state in {"registered", "ready"} and new_runner is None:
                        raise _error("unknown", "managed recovery target runner identity is unavailable")
                    stage = "open"
                    expected_runner = new_runner
                else:
                    # Durable target-open evidence is sufficient unless a
                    # release intent is still in progress (handled first).
                    continue
            elif mode == "shutdown":
                shutdown_intent = shutdown_intents.get(participant_id)
                if not isinstance(shutdown_intent, Mapping):
                    raise _error("invalid", "managed shutdown recovery intent is malformed")
                expected_runner = _runner_identity(
                    runner_instances, participant_id, "managed shutdown"
                )
                if expected_runner is None:
                    raise _error(
                        "unknown", "managed shutdown runner identity is unavailable"
                    )
                shutdown_state = shutdown_intent.get("state")
                if shutdown_state is not None and (
                    not isinstance(shutdown_state, str) or not shutdown_state
                ):
                    raise _error("invalid", "managed shutdown recovery state is malformed")
                # A participant with both durable status and exclusion proof
                # needs no fresh handle.  Otherwise read status only; if a
                # shutdown call had crossed its durable intent boundary, a
                # fresh excluded process may be recorded as shutdown proof
                # after the already-durable status proof.
                if shutdown_evidence is not None and _stage_value(
                    "status", participant_id
                ) is not None:
                    continue
                stage = "status"
            elif mode == "unenroll":
                # Unenrollment has no runtime lifecycle to reconstruct.  The
                # controller consumes only its durable claim/owner state;
                # emit an empty per-participant record so no caller-supplied
                # claim or quiescence assertion can become evidence.
                records[participant_id] = {}
                continue
            elif mode == "ctx":
                # Retained workers need fresh old-runner quiescence; only the
                # newly reserved coordinator may produce target-open facts.
                worker_status = metadata.get("worker_status_evidence", {})
                if not isinstance(worker_status, Mapping):
                    raise _error("invalid", "managed ctx worker status ledger is malformed")
                if participant_id == ctx_old_id:
                    if shutdown_evidence is not None and _stage_value(
                        "status", participant_id
                    ) is not None and _stage_value(
                        "interrupt", participant_id
                    ) is not None:
                        continue
                    if old_runner is None:
                        raise _error(
                            "unknown", "managed ctx old runner identity is unavailable"
                        )
                    stage = "status"
                    expected_runner = old_runner
                elif participant_id == ctx_target_id:
                    if open_evidence is not None:
                        continue
                    if intent_state not in {
                        "pending", "in-progress", "registered", "ready",
                    }:
                        raise _error(
                            "unknown", "managed ctx target launch intent is unavailable"
                        )
                    if intent_state == "pending" and new_runner is None:
                        records[participant_id] = {}
                        continue
                    if intent_state in {"registered", "ready"} and new_runner is None:
                        raise _error(
                            "unknown", "managed ctx target runner identity is unavailable"
                        )
                    stage = "open"
                    expected_runner = new_runner
                elif participant_id in worker_status:
                    continue
                elif old_runner is not None:
                    stage = "status"
                    expected_runner = old_runner
                else:
                    raise _error("unsupported", "managed ctx recovery stage is unavailable")
            else:
                raise _error("unsupported", "managed recovery mode is not supported")

            if stage is None:
                raise _error("unknown", "managed recovery stage is unavailable")
            fresh = runtime_status(participant_id)
            fresh = await _await_bounded(
                fresh, absolute_deadline, "managed runtime recovery status"
            )
            _bounded_wire(fresh, "managed runtime recovery status")
            if not isinstance(fresh, Mapping):
                raise _error("unknown", "managed runtime recovery status is malformed")
            if not _runtime_process_domain_matches(fresh, recovery_process_domain):
                raise _error(
                    "unknown", "managed runtime recovery process domain is foreign"
                )
            _observed_identity(
                fresh, participant_id, participant_record, expected_runner
            )
            durable_status = _stage_value("status", participant_id)
            if mode == "ctx" and participant_id not in {
                ctx_old_id, ctx_target_id,
            }:
                durable_status = _stage_value("worker_status", participant_id)
            if (
                stage == "status"
                and durable_status is not None
                and _process_is_excluded(fresh)
                and (
                    mode in {"swap", "ctx"}
                    or (
                        mode == "shutdown"
                        and shutdown_state in {"shutdown-in-progress", "complete"}
                    )
                )
            ):
                stage = "shutdown"
            # Store the adapter's complete canonical result under the exact
            # lifecycle stage selected from durable state; do not flatten it
            # into a generic status wrapper or accept caller-provided proof.
            records[participant_id] = {stage: dict(fresh)}
        if not records:
            raise _error("unknown", "managed recovery has no live participant evidence")
        evidence = {
            "operation_id": operation_id,
            "generation": generation,
            "participants": records,
        }
        _bounded_wire(evidence, "managed recovery evidence")
        return evidence

    @staticmethod
    def _recovery_operation_projection(
            durable: Mapping[str, Any],
    ) -> Optional[Mapping[str, Any]]:
        """Resolve the one current operation from either status projection.

        ``ManagedController.status()`` exposes ``operation`` and
        ``active_operation`` for the live controller seam.  A freshly loaded
        durable projection may instead expose the same current record through
        ``active_operation_id`` plus the persisted ``operations`` list.  That
        projection is still exact only when the active pointer selects one
        and only one well-formed operation; never select an arbitrary
        historical row or fall back to a legacy recovery path.
        """

        operation = durable.get("operation")
        if isinstance(operation, Mapping):
            return operation
        operation = durable.get("active_operation")
        if isinstance(operation, Mapping):
            return operation

        active_operation_id = durable.get("active_operation_id")
        operations = durable.get("operations")
        if active_operation_id is None and operations is None:
            return None
        if not isinstance(active_operation_id, str) or not active_operation_id:
            raise _error(
                "invalid",
                "managed recovery active operation projection is malformed",
            )
        if not isinstance(operations, list):
            raise _error(
                "invalid",
                "managed recovery operations projection is malformed",
            )
        matches: list[Mapping[str, Any]] = []
        for value in operations:
            if not isinstance(value, Mapping):
                raise _error(
                    "invalid",
                    "managed recovery operations projection is malformed",
                )
            if value.get("operation_id") == active_operation_id:
                matches.append(value)
        if len(matches) != 1:
            raise _error(
                "unknown",
                "managed recovery active operation is unavailable",
            )
        return matches[0]

    @staticmethod
    def _native_rollover_recovery_states() -> frozenset[str]:
        """Return mutable rollover states that still need reconciliation."""

        return frozenset({
            "preparation-pending", "runtime-reserved", "bound", "send-pending",
            "reconciled", "uncertain",
        })

    def _native_rollover_recovery_candidate(
            self, durable: Any, operation_id: str, generation: int,
    ) -> bool:
        """Validate the daemon-owned native rollover recovery entry fence.

        This is deliberately a bounded identity/fence check only.  The
        controller remains the owner of the status observation,
        ``native_reservation_no_send`` receipt validation, durable receipt
        persistence, and queue transition.  Returning ``False`` means the
        active operation is not this private native rollover mode and lets
        the existing generic recovery route handle it.
        """

        if not isinstance(durable, Mapping):
            raise _error("invalid", "managed recovery status is malformed")
        operation = self._recovery_operation_projection(durable)
        if not isinstance(operation, Mapping):
            return False

        mode = operation.get("mode")
        native_context = durable.get("native_context")
        metadata = operation.get("metadata")
        native_startup = (
            metadata.get("native_startup")
            if isinstance(metadata, Mapping) else None
        )
        rows_value = durable.get("native_invocation_rollovers")
        has_native_rows = isinstance(rows_value, Mapping) and bool(rows_value)
        supported_native_mode = mode in {"start", "swap"}
        if not supported_native_mode:
            if has_native_rows:
                raise _error(
                    "unsupported",
                    "native rollover recovery mode is not supported",
                )
            return False
        # A native-startup descriptor is also retained by native swap after
        # target activation.  It is not, by itself, a rollover authority:
        # native-swap recovery must continue through the generic evidence
        # collector and the controller's mode-aware consumer when its durable
        # rollover ledger is empty.  Only a non-empty ledger can select this
        # private no-send route.
        if not has_native_rows:
            if rows_value is not None and not isinstance(rows_value, Mapping):
                raise _error(
                    "unsupported",
                    "native rollover recovery records are unavailable",
                )
            return False
        native_operation = (
            isinstance(native_context, Mapping)
            or isinstance(native_startup, Mapping)
        )
        if not native_operation:
            if has_native_rows:
                raise _error(
                    "unsupported",
                    "native rollover recovery startup authority is unavailable",
                )
            return False
        if operation.get("operation_id") != operation_id:
            raise _error(
                "stale-generation",
                "native rollover recovery operation identity changed",
            )
        if operation.get("generation") != generation:
            raise _error(
                "stale-generation",
                "native rollover recovery operation generation changed",
            )
        if durable.get("generation") is not None and durable.get("generation") != generation:
            raise _error(
                "stale-generation",
                "native rollover recovery owner generation changed",
            )
        if operation.get("phase") != "released":
            raise _error(
                "busy",
                "native rollover recovery requires a released operation",
            )
        if not isinstance(metadata, Mapping):
            raise _error("invalid", "native rollover recovery metadata is malformed")

        if not isinstance(rows_value, Mapping):
            raise _error(
                "unsupported",
                "native rollover recovery records are unavailable",
            )
        states = self._native_rollover_recovery_states()
        unresolved: list[Mapping[str, Any]] = []
        for key, value in rows_value.items():
            if not isinstance(key, str) or not isinstance(value, Mapping):
                raise _error(
                    "invalid", "native rollover recovery records are malformed"
                )
            if value.get("state") in states:
                unresolved.append(value)
        if len(unresolved) != 1:
            raise _error(
                "uncertain-effect",
                "native rollover recovery requires exactly one unresolved record",
            )
        rollover = unresolved[0]
        if rollover.get("record_kind") != "native-invocation-rollover":
            raise _error("invalid", "native rollover recovery record kind is invalid")
        if rollover.get("rollover_schema") != 1:
            raise _error("schema-mismatch", "native rollover recovery schema is unsupported")
        if rollover.get("operation_id") != operation_id:
            raise _error(
                "stale-generation",
                "native rollover recovery record names another operation",
            )
        if rollover.get("owner_generation") != generation:
            raise _error(
                "stale-generation",
                "native rollover recovery record generation changed",
            )
        if rollover.get("daemon_id") != self.daemon_id:
            raise _error(
                "ownership-conflict",
                "native rollover recovery daemon identity changed",
            )
        daemon_incarnation = rollover.get("daemon_incarnation")
        if daemon_incarnation is not None and daemon_incarnation != self.daemon_id:
            raise _error(
                "ownership-conflict",
                "native rollover recovery daemon incarnation changed",
            )

        coordinator = rollover.get("coordinator")
        if not isinstance(coordinator, Mapping):
            raise _error("invalid", "native rollover recovery coordinator is malformed")
        participant_id = coordinator.get("participant_id")
        session_id = coordinator.get("session_uuid")
        if not isinstance(participant_id, str) or not participant_id:
            raise _error("invalid", "native rollover recovery participant is malformed")
        if not isinstance(session_id, str) or not session_id:
            raise _error("invalid", "native rollover recovery session is malformed")
        runner_instance_id = rollover.get("runner_incarnation")
        lineage_id = rollover.get("lineage_id")
        lineage_generation = rollover.get("lineage_generation")
        if not isinstance(runner_instance_id, str) or not runner_instance_id:
            raise _error("invalid", "native rollover recovery runner is malformed")
        if not isinstance(lineage_id, str) or not lineage_id:
            raise _error("invalid", "native rollover recovery lineage is malformed")
        if isinstance(lineage_generation, bool) or not isinstance(lineage_generation, int) or lineage_generation < 1:
            raise _error("invalid", "native rollover recovery lineage generation is malformed")
        for key in (
                "prior_invocation_id", "next_invocation_id",
                "prior_mailbox_id", "next_mailbox_id",
        ):
            if not isinstance(rollover.get(key), str) or not rollover.get(key):
                raise _error("invalid", "native rollover recovery identity is malformed")
        if rollover["prior_invocation_id"] != rollover["prior_mailbox_id"]:
            raise _error(
                "ownership-conflict",
                "native rollover recovery A invocation/mailbox binding changed",
            )
        if rollover["next_invocation_id"] != rollover["next_mailbox_id"]:
            raise _error(
                "ownership-conflict",
                "native rollover recovery B invocation/mailbox binding changed",
            )

        if not isinstance(native_context, Mapping):
            raise _error(
                "unsupported",
                "native rollover recovery source context is unavailable",
            )
        context_lineage = native_context.get("lineage")
        if not isinstance(context_lineage, Mapping):
            raise _error("invalid", "native rollover recovery source lineage is malformed")
        if (
            native_context.get("invocation_id") != rollover["prior_invocation_id"]
            or native_context.get("runner_incarnation") != runner_instance_id
            or context_lineage.get("lineage_id") != lineage_id
            or context_lineage.get("lineage_generation") != lineage_generation
            or context_lineage.get("session_uuid") != session_id
            or context_lineage.get("owner_generation") != generation
        ):
            raise _error(
                "stale-generation",
                "native rollover recovery source context changed",
            )
        runner_instances = metadata.get("runner_instances")
        if not isinstance(runner_instances, Mapping) or runner_instances.get(participant_id) != runner_instance_id:
            raise _error(
                "ownership-conflict",
                "native rollover recovery runner authority changed",
            )
        if isinstance(native_startup, Mapping):
            startup_daemon = native_startup.get("daemon_id")
            if startup_daemon is not None and startup_daemon != self.daemon_id:
                raise _error(
                    "ownership-conflict",
                    "native rollover recovery startup daemon changed",
                )

        participants = durable.get("participants")
        if not isinstance(participants, list):
            raise _error("invalid", "native rollover recovery participant roster is malformed")
        matching_participants = [
            item for item in participants
            if isinstance(item, Mapping) and item.get("participant_id") == participant_id
        ]
        if len(matching_participants) != 1:
            raise _error(
                "ownership-conflict",
                "native rollover recovery coordinator identity is unavailable",
            )
        participant = matching_participants[0]
        if participant.get("session_id") != session_id:
            raise _error(
                "stale-generation",
                "native rollover recovery coordinator session changed",
            )

        mailboxes = durable.get("mailboxes")
        if not isinstance(mailboxes, list):
            raise _error("invalid", "native rollover recovery mailbox ledger is malformed")
        prior_mailboxes = [
            item for item in mailboxes
            if isinstance(item, Mapping)
            and item.get("message_id") == rollover["prior_mailbox_id"]
        ]
        next_mailboxes = [
            item for item in mailboxes
            if isinstance(item, Mapping)
            and item.get("message_id") == rollover["next_mailbox_id"]
        ]
        if len(prior_mailboxes) != 1 or len(next_mailboxes) != 1:
            raise _error(
                "uncertain-effect",
                "native rollover recovery mailbox identity is unavailable",
            )
        prior_mailbox = prior_mailboxes[0]
        next_mailbox = next_mailboxes[0]
        if (
            prior_mailbox.get("operation_id") != operation_id
            or prior_mailbox.get("generation") != generation
            or prior_mailbox.get("recipient_id") != participant_id
            or prior_mailbox.get("state") != "acknowledged"
        ):
            raise _error(
                "uncertain-effect",
                "native rollover recovery has a live or unresolved A dispatch",
            )
        if (
            next_mailbox.get("operation_id") != operation_id
            or next_mailbox.get("generation") != generation
            or next_mailbox.get("recipient_id") != participant_id
            or next_mailbox.get("state") not in {"queued", "dispatch-intent", "uncertain"}
        ):
            raise _error(
                "uncertain-effect",
                "native rollover recovery B mailbox is not recoverable",
            )
        return True

    async def _recover_native_rollover_if_needed(
            self, operation_id: str, generation: int, deadline: float,
    ) -> Any:
        """Route one exact native rollover to the controller's private branch.

        The daemon serializes this decision with its existing dispatch lock,
        but does not run a pump tick after recovery.  The controller owns the
        one fresh runtime status observation and the authenticated no-send
        receipt; recovery only returns that exact durable operation to the
        normal released pump when the controller has proved it safe.
        """

        status_method = getattr(self.controller, "status", None)
        if not callable(status_method):
            return None
        durable = status_method()
        durable = await _await_bounded(
            durable, deadline, "managed native rollover recovery status"
        )
        if not self._native_rollover_recovery_candidate(
                durable, operation_id, generation
        ):
            return None

        lock = self._dispatch_lock_for_loop()
        if lock.locked():
            raise _error(
                "busy",
                "native rollover recovery cannot overlap a live dispatch",
            )
        async with lock:
            # Re-read the durable operation after acquiring the same lock the
            # pump uses.  A queued pump cannot race the identity fence or make
            # an original A dispatch live between this check and recovery.
            durable = status_method()
            durable = await _await_bounded(
                durable, deadline, "managed native rollover recovery status"
            )
            if not self._native_rollover_recovery_candidate(
                    durable, operation_id, generation
            ):
                raise _error(
                    "stale-generation",
                    "native rollover recovery authority changed before dispatch",
                )
            await self._assert_native_stop_owner(deadline)
            recover_method = getattr(self.controller, "recover", None)
            if not callable(recover_method):
                raise _error(
                    "unsupported", "managed controller recover is unavailable"
                )
            # This exact two-argument call is the private native branch.  Do
            # not pass public/body evidence and do not fall through to the
            # generic evidence collector or a legacy recover_dispatch path.
            result = recover_method(operation_id, generation)
            return await _await_bounded(
                result, deadline, "managed native rollover recovery"
            )

    def _success_response(self, request: Mapping[str, Any], result: Any) -> dict[str, Any]:
        response = _response(request, result=result)
        if request.get("operation") == "shutdown" and response.get("ok") is True:
            self.shutdown_succeeded = True
        return response

    async def _admit_native_callback(
            self, admission: Mapping[str, Any]) -> dict[str, Any]:
        """Bridge the SDK hook to the same strict authority as the wire route.

        Registration of trusted native context belongs before released query
        execution, after durable dispatch intent and runtime invocation
        correlation.  Neither admission fields nor accepted-send evidence can
        supply that missing pre-query authority here.
        """

        if not self.opt_in or not self.started:
            raise _error("unsupported", "managed daemon startup is not active")
        intent = _native_admission_from_wire(admission)
        # Policy/definition contents deliberately do not select the request
        # identity.  A changed payload for the same admission must reach the
        # controller's durable content-conflict check, not become a new act.
        correlation = {
            name: intent[name]
            for name in (
                "admission_id", "owner_generation", "lineage_id",
                "runner_incarnation", "invocation_id", "tool_use_id",
                "parent", "watermark",
            )
        }
        request_id = "native-admission-" + hashlib.sha256(
            json.dumps(correlation, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        return await self._persist_native_admission(
            {"request_id": request_id,
             "generation": intent["owner_generation"], "body": intent},
            time.monotonic() + OPERATION_TIMEOUT,
        )

    async def _persist_native_stop_intent_callback(
            self, frame: Mapping[str, Any]
    ) -> Any:
        """Forward one SDK native-stop intent through the trusted controller.

        Stop frames are an internal runner boundary.  The daemon requires its
        opted-in managed owner, generation, daemon identity, and callback
        frame type to match, then preserves the complete runner-derived frame
        for the controller's current-owner, admission, claim, and fence
        validation.  There is intentionally no state-only or public-wire
        fallback.
        """

        return await self._persist_native_stop_callback(
            frame,
            _NATIVE_STOP_INTENT_AUTHORITY_METHOD,
            "native stop intent",
            _NATIVE_STOP_INTENT_TYPE,
        )

    async def _persist_native_stop_evidence_callback(
            self, frame: Mapping[str, Any]
    ) -> Any:
        """Forward one SDK native-stop evidence frame to the controller."""

        return await self._persist_native_stop_callback(
            frame,
            _NATIVE_STOP_EVIDENCE_AUTHORITY_METHOD,
            "native stop evidence",
            _NATIVE_STOP_EVIDENCE_TYPE,
        )

    async def _persist_coordinator_interrupt_intent_callback(
            self, frame: Mapping[str, Any]
    ) -> Any:
        """Forward one internal whole-roster interrupt intent to the controller."""

        return await self._persist_coordinator_interrupt_callback(
            frame,
            _COORDINATOR_INTERRUPT_INTENT_AUTHORITY_METHOD,
            "coordinator interrupt intent",
            _COORDINATOR_INTERRUPT_INTENT_TYPE,
        )

    async def _persist_coordinator_interrupt_evidence_callback(
            self, frame: Mapping[str, Any]
    ) -> Any:
        """Forward one independent coordinator interrupt fact to the controller."""

        return await self._persist_coordinator_interrupt_callback(
            frame,
            _COORDINATOR_INTERRUPT_EVIDENCE_AUTHORITY_METHOD,
            "coordinator interrupt evidence",
            _COORDINATOR_INTERRUPT_EVIDENCE_TYPE,
        )

    async def _prepare_native_invocation_callback(
            self, participant_id: Any, session_id: Any,
            runner_instance_id: Any, message_id: Any,
    ) -> Any:
        """Bind one actual durable coordinator mailbox before SDK query."""

        if not self.opt_in or not self.started:
            raise _error("unsupported", "managed daemon startup is not active")
        participant_id = _bounded_id(participant_id, "native invocation participant_id")
        session_id = _bounded_id(session_id, "native invocation session_id")
        runner_instance_id = _bounded_id(
            runner_instance_id, "native invocation runner_instance_id"
        )
        message_id = _bounded_id(message_id, "native invocation message_id")
        deadline = time.monotonic() + OPERATION_TIMEOUT
        await self._assert_native_stop_owner(deadline)
        generation = self._owner_generation(self.owner_record)
        # The rollover controller keeps the original four-argument callback
        # contract but exposes the committed B context and its exact durable
        # reservation through this result wrapper.  There is intentionally no
        # legacy context-only fallback: accepting it would let a first-mail
        # binder masquerade as a committed rollover and would leave the SDK
        # without an explicit null reservation.
        binder = getattr(
            self.controller, "native_invocation_dispatch_binding", None
        )
        if not callable(binder):
            raise _error(
                "unsupported",
                "managed native invocation dispatch binding is unavailable",
            )
        try:
            result = binder(
                generation, participant_id, runner_instance_id, message_id,
                session_id=session_id,
            )
            result = await _await_bounded(
                result, deadline, "managed native invocation binding"
            )
        except asyncio.CancelledError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise _error(code, "managed native invocation binding was refused")
            raise _error("uncertain-effect", "managed native invocation binding is unknown")

        # The await is deliberately outside the daemon/controller lock.  A
        # replacement may take ownership while runtime preparation is in
        # flight, so the authority fence must be read again before this
        # callback returns a context that an adapter could send.
        await self._assert_native_stop_owner(deadline)
        if result is None:
            raise _error("unsupported", "native coordinator startup is not prepared")

        _bounded_wire(result, "managed native invocation binding acknowledgement")
        if not isinstance(result, Mapping) or set(result) != {
                "context", "reservation_binding"}:
            raise _error(
                "invalid",
                "managed native invocation binding wrapper is incomplete",
            )
        context_value = result.get("context")
        reservation_value = result.get("reservation_binding")
        if not isinstance(context_value, Mapping):
            raise _error(
                "invalid", "managed native invocation binding context is malformed"
            )
        context = dict(context_value)
        lineage = context.get("lineage")
        if (not isinstance(lineage, Mapping) or
                lineage.get("session_uuid") != session_id or
                context.get("runner_incarnation") != runner_instance_id or
                context.get("invocation_id") != message_id):
            raise _error("ownership-conflict", "native invocation binding identity changed")
        reservation = None
        if reservation_value is not None:
            reservation = _reservation_binding_from_controller(
                reservation_value,
                daemon_id=self.daemon_id,
                participant_id=participant_id,
                session_id=session_id,
                runner_instance_id=runner_instance_id,
                message_id=message_id,
                owner_generation=generation,
                context=context,
            )
        _bounded_wire(context, "managed native invocation binding context")
        return {
            "bound": True,
            "participant_id": participant_id,
            "session_id": session_id,
            "runner_instance_id": runner_instance_id,
            "message_id": message_id,
            "context": context,
            "reservation_binding": reservation,
        }

    async def _authorize_native_swap_release_callback(
            self, participant_id: Any, session_id: Any,
            runner_instance_id: Any, validation_id: Any,
            binding: Any,
    ) -> dict[str, Any]:
        """Authorize one private native-swap release boundary.

        The SDK runner reaches this method only through its authenticated
        internal IPC reader.  Keep the callback closed over the exact
        participant/session/runner/validation/binding tuple and revalidate the
        managed owner after the controller call.  The controller owns the
        durable first-grant/exact-repeat decision; this daemon owns the
        authenticated owner and daemon fences and exposes only the frozen ACK
        shape.
        """

        if not self.opt_in or not self.started:
            raise _error("unsupported", "managed daemon startup is not active")

        participant_id = _bounded_id(
            participant_id, "native swap release participant_id"
        )
        session_id = _bounded_id(
            session_id, "native swap release session_id"
        )
        runner_instance_id = _bounded_id(
            runner_instance_id, "native swap release runner_instance_id"
        )
        validation_id = _bounded_id(
            validation_id, "native swap release validation_id"
        )
        try:
            binding = _validate_native_swap_release_binding(binding)
        except NativeSwapContractError as exc:
            raise _error(exc.code, exc.message)

        if binding["participant_id"] != participant_id:
            raise _error(
                "ownership-conflict",
                "native swap release participant identity changed",
            )
        if binding["session_id"] != session_id:
            raise _error(
                "stale-generation",
                "native swap release session identity changed",
            )
        if binding["runner_incarnation"] != runner_instance_id:
            raise _error(
                "stale-generation",
                "native swap release runner identity changed",
            )

        deadline = time.monotonic() + OPERATION_TIMEOUT
        # This read authenticates the callback's daemon/owner before any
        # controller authority can persist a grant.  It does not hold a
        # controller/state lock across the potentially asynchronous call.
        await self._assert_native_stop_owner(deadline)
        generation = self._owner_generation(self.owner_record)
        if binding["owner_generation"] != generation:
            raise _error(
                "stale-generation",
                "native swap release owner generation changed",
            )
        if binding["expected_daemon_id"] != self.daemon_id:
            raise _error(
                "ownership-conflict",
                "native swap release daemon identity changed",
            )

        authority = getattr(
            self.controller, _NATIVE_SWAP_RELEASE_AUTHORITY_METHOD, None
        )
        if not callable(authority):
            raise _error(
                "unsupported",
                "managed native swap release authorization is unavailable",
            )
        try:
            acknowledgement = authority(
                validation_id, copy.deepcopy(binding)
            )
            acknowledgement = await _await_bounded(
                acknowledgement,
                deadline,
                "native swap release authorization",
            )
        except asyncio.CancelledError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise _error(
                    code,
                    "native swap release authorization was refused",
                )
            raise _error(
                "uncertain-effect",
                "native swap release authorization outcome is unknown",
            )

        # A controller response can arrive after owner takeover.  Never
        # return an ACK that an old daemon/runner could use to cross the gate.
        await self._assert_native_stop_owner(deadline)
        try:
            acknowledgement = _validate_native_swap_authorization(
                acknowledgement,
                expected_validation_id=validation_id,
                expected_binding=binding,
            )
        except NativeSwapContractError as exc:
            raise _error(exc.code, exc.message)
        _bounded_wire(
            acknowledgement,
            "managed native swap release authorization acknowledgement",
        )
        return acknowledgement

    async def _validate_coordinator_interrupt_callback(
            self, frame: Mapping[str, Any]
    ) -> Any:
        """Forward the validate-only coordinator interrupt send check."""

        if not self.opt_in or not self.started:
            raise _error("unsupported", "managed daemon startup is not active")
        if not isinstance(frame, Mapping):
            raise _error("invalid", "coordinator interrupt validation frame must be an object")
        expected = {
            "type", "participant_id", "session_id", "runner_instance_id",
            "validation_id", "interrupt_id", "intent_digest",
        }
        if set(frame) != expected or frame.get("type") != "coordinator-interrupt-validate":
            raise _error("invalid", "coordinator interrupt validation frame shape is unsupported")
        _bounded_wire(frame, "coordinator interrupt validation frame")
        deadline = time.monotonic() + OPERATION_TIMEOUT
        await self._assert_coordinator_interrupt_owner(deadline)
        authority = getattr(self.controller, "validate_coordinator_interrupt_send", None)
        if not callable(authority):
            raise _error("unsupported", "managed coordinator interrupt validation is unavailable")
        try:
            acknowledgement = authority(frame)
            acknowledgement = await _await_bounded(
                acknowledgement, deadline, "coordinator interrupt validation"
            )
        except asyncio.CancelledError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise _error(code, "coordinator interrupt validation was refused")
            raise _error("uncertain-effect", "coordinator interrupt validation is unknown")
        _bounded_wire(acknowledgement, "coordinator interrupt validation acknowledgement")
        return acknowledgement

    async def _interrupt_native_coordinator(
            self, operation_id: Any, generation: Any, *,
            interrupt_id: Any, capability_digest: Any,
            request_epoch_id: Any = None, deadline: Optional[float] = None,
    ) -> Any:
        """Run the private controller-to-adapter coordinator interrupt seam.

        No public request reaches this method.  The adapter/runner constructs
        the actual native roster and owns intent authorization, validation,
        local recheck, SDK invocation, and runtime evidence.
        """

        if not self.opt_in or not self.started:
            raise _error("unsupported", "managed daemon startup is not active")
        if deadline is None:
            deadline = time.monotonic() + OPERATION_TIMEOUT
        elif (isinstance(deadline, bool) or
              not isinstance(deadline, (int, float)) or
              not math.isfinite(float(deadline))):
            raise _error("invalid", "managed coordinator interrupt deadline is invalid")
        deadline = float(deadline)
        await self._assert_coordinator_interrupt_owner(deadline)
        method = getattr(self.controller, "interrupt_native_coordinator", None)
        if not callable(method):
            raise _error("unsupported", "managed coordinator interrupt controller is unavailable")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _error("timeout", "managed coordinator interrupt deadline exceeded")
        result = method(
            operation_id,
            generation,
            interrupt_id=interrupt_id,
            capability_digest=capability_digest,
            request_epoch_id=request_epoch_id,
            deadline=remaining,
        )
        result = await _await_bounded(
            result, deadline, "managed coordinator interrupt"
        )
        _bounded_wire(result, "managed coordinator interrupt result")
        return result

    async def _assert_coordinator_interrupt_owner(self, deadline: float) -> None:
        """Revalidate the currently enrolled owner before interrupt persistence."""

        # Coordinator interrupt records use the same authenticated managed
        # owner/claim boundary as native stop records.  Keep a named wrapper
        # so tests and future takeover checks can fence this transaction
        # independently without conflating its durable namespace.
        await self._assert_native_stop_owner(deadline)

    async def _persist_coordinator_interrupt_callback(
            self, frame: Mapping[str, Any], authority_name: str, label: str,
            expected_type: str,
    ) -> Any:
        """Run one bounded internal interrupt callback through the controller."""

        if not self.opt_in or not self.started:
            raise _error("unsupported", "managed daemon startup is not active")
        if not isinstance(frame, Mapping):
            raise _error("invalid", "%s frame must be an object" % label)
        expected_fields = {
            "type", "participant_id", "session_id", "runner_instance_id",
            "interrupt" if expected_type == _COORDINATOR_INTERRUPT_INTENT_TYPE else "evidence",
        }
        if set(frame) != expected_fields:
            raise _error("invalid", "%s frame shape is unsupported" % label)
        if frame.get("type") != expected_type:
            raise _error("invalid", "%s frame type is unsupported" % label)
        _bounded_wire(frame, label)
        deadline = time.monotonic() + OPERATION_TIMEOUT
        await self._assert_coordinator_interrupt_owner(deadline)
        authority = getattr(self.controller, authority_name, None)
        if not callable(authority):
            raise _error(
                "unsupported", "managed %s authority is unavailable" % label
            )
        try:
            acknowledgement = authority(frame)
            acknowledgement = await _await_bounded(
                acknowledgement,
                deadline,
                label,
            )
        except asyncio.CancelledError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise _error(code, "%s was refused" % label)
            raise _error("uncertain-effect", "%s outcome is unknown" % label)
        _bounded_wire(acknowledgement, "%s acknowledgement" % label)
        return acknowledgement

    async def _assert_native_stop_owner(self, deadline: float) -> None:
        """Revalidate this daemon's managed owner before a stop authority call."""

        owner = self.owner_record
        if not isinstance(owner, Mapping):
            raise _error(
                "ownership-conflict",
                "managed native stop owner is unavailable",
            )
        if owner.get("mode") != "managed":
            raise _error(
                "ownership-conflict",
                "managed native stop owner is not active",
            )
        generation = self._owner_generation(owner)
        if owner.get("daemon_id") != self.daemon_id:
            raise _error(
                "ownership-conflict",
                "managed native stop belongs to another daemon",
            )
        if self.lane is not None and owner.get("lane") != self.lane:
            raise _error(
                "ownership-conflict",
                "managed native stop owner lane changed",
            )

        # A supervisor replacement can keep the same owner generation while
        # changing daemon_id.  Use the store's fresh owner snapshot when the
        # state seam exposes it; the enrolled record alone cannot prove that
        # this callback still belongs to the current owner.
        read_owner = getattr(self.state, "read_owner", None)
        if not callable(read_owner):
            raise _error(
                "unsupported",
                "managed native stop owner reader is unavailable",
            )
        try:
            fresh_owner = read_owner(deadline=deadline)
            fresh_owner = await _await_bounded(
                fresh_owner, deadline, "managed native stop owner read"
            )
        except asyncio.CancelledError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise _error(code, "managed native stop owner read was refused")
            raise _error(
                "ownership-conflict",
                "managed native stop owner could not be revalidated",
            )
        if not isinstance(fresh_owner, Mapping):
            raise _error(
                "ownership-conflict",
                "managed native stop owner could not be revalidated",
            )
        if fresh_owner.get("mode") != "managed":
            raise _error(
                "ownership-conflict",
                "managed native stop owner is no longer active",
            )
        fresh_generation = self._owner_generation(fresh_owner)
        if fresh_generation != generation:
            raise _error(
                "stale-generation",
                "managed native stop owner generation changed",
            )
        if (fresh_owner.get("daemon_id") != self.daemon_id or
                fresh_owner.get("daemon_id") != owner.get("daemon_id")):
            raise _error(
                "ownership-conflict",
                "managed native stop owner daemon changed",
            )
        if self.lane is not None and fresh_owner.get("lane") != self.lane:
            raise _error(
                "ownership-conflict",
                "managed native stop owner lane changed",
            )

    async def _persist_native_stop_callback(
            self, frame: Mapping[str, Any], authority_name: str, label: str,
            expected_type: str,
    ) -> Any:
        """Run one bounded internal stop callback without changing its frame."""

        if not self.opt_in or not self.started:
            raise _error("unsupported", "managed daemon startup is not active")
        if not isinstance(frame, Mapping):
            raise _error("invalid", "%s frame must be an object" % label)
        if frame.get("type") != expected_type:
            raise _error("invalid", "%s frame type is unsupported" % label)
        _bounded_wire(frame, label)
        deadline = time.monotonic() + OPERATION_TIMEOUT
        await self._assert_native_stop_owner(deadline)
        authority = getattr(self.controller, authority_name, None)
        if not callable(authority):
            raise _error(
                "unsupported", "managed %s authority is unavailable" % label
            )
        try:
            acknowledgement = authority(frame)
            acknowledgement = await _await_bounded(
                acknowledgement,
                deadline,
                label,
            )
        except asyncio.CancelledError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise _error(code, "%s was refused" % label)
            raise _error("uncertain-effect", "%s outcome is unknown" % label)
        _bounded_wire(acknowledgement, "%s acknowledgement" % label)
        return acknowledgement

    async def _assert_native_child_observation_owner(
            self, frame: Mapping[str, Any], deadline: float,
    ) -> int:
        """Fence a child observation to the fresh managed owner identity."""

        await self._assert_native_stop_owner(deadline)
        read_owner = getattr(self.state, "read_owner", None)
        if not callable(read_owner):
            raise _error(
                "unsupported",
                "managed native child observation owner reader is unavailable",
            )
        try:
            owner = read_owner(deadline=deadline)
            owner = await _await_bounded(
                owner, deadline, "managed native child observation owner read"
            )
        except asyncio.CancelledError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise _error(
                    code,
                    "managed native child observation owner read was refused",
                )
            raise _error(
                "ownership-conflict",
                "managed native child observation owner could not be revalidated",
            )
        if not isinstance(owner, Mapping):
            raise _error(
                "ownership-conflict",
                "managed native child observation owner is unavailable",
            )
        if owner.get("mode") != "managed":
            raise _error(
                "ownership-conflict",
                "managed native child observation owner is not active",
            )
        generation = self._owner_generation(owner)
        if owner.get("daemon_id") != self.daemon_id:
            raise _error(
                "ownership-conflict",
                "managed native child observation daemon identity changed",
            )
        if self.lane is not None and owner.get("lane") != self.lane:
            raise _error(
                "ownership-conflict",
                "managed native child observation lane changed",
            )

        observation = frame["observation"]
        source = observation["source_identity"]
        if source["owner_generation"] != generation:
            raise _error(
                "stale-generation",
                "managed native child observation generation changed",
            )

        # The enrolled state-store owner intentionally need not repeat the
        # coordinator's participant/session/runner aliases.  The private
        # frame's transport identity therefore has to join the controller's
        # fresh authoritative projection, and that projection is re-read on
        # both sides of the controller persistence await.  In particular,
        # the observation sent to the controller does not contain the outer
        # participant identity, so passing ``expected_daemon_id`` alone would
        # not bind a tampered transport participant.
        status_reader = getattr(self.controller, "status", None)
        if not callable(status_reader):
            raise _error(
                "unsupported",
                "managed native child observation controller status is unavailable",
            )
        try:
            status = status_reader()
            status = await _await_bounded(
                status, deadline, "managed native child observation controller status"
            )
        except asyncio.CancelledError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise _error(
                    code,
                    "managed native child observation controller status was refused",
                )
            raise _error(
                "ownership-conflict",
                "managed native child observation controller status is unavailable",
            )
        _bounded_wire(status, "managed native child observation controller status")
        if not isinstance(status, Mapping):
            raise _error(
                "invalid",
                "managed native child observation controller status is malformed",
            )
        status_generation = status.get("generation")
        if type(status_generation) is not int or status_generation < 1:
            raise _error(
                "invalid",
                "managed native child observation controller generation is malformed",
            )
        if status_generation != generation:
            raise _error(
                "stale-generation",
                "managed native child observation controller generation changed",
            )
        coordinator_id = status.get("coordinator_id")
        if not isinstance(coordinator_id, str) or not coordinator_id:
            raise _error(
                "ownership-conflict",
                "managed native child observation coordinator identity is unavailable",
            )
        if coordinator_id != frame["participant_id"]:
            raise _error(
                "ownership-conflict",
                "managed native child observation participant changed",
            )
        participants = status.get("participants")
        if not isinstance(participants, list):
            raise _error(
                "invalid",
                "managed native child observation coordinator roster is malformed",
            )
        matching_participants = [
            participant
            for participant in participants
            if isinstance(participant, Mapping)
            and participant.get("participant_id") == frame["participant_id"]
        ]
        if len(matching_participants) != 1:
            raise _error(
                "ownership-conflict",
                "managed native child observation coordinator is not uniquely live",
            )
        coordinator = matching_participants[0]
        if coordinator.get("role") != "coordinator":
            raise _error(
                "ownership-conflict",
                "managed native child observation participant is not coordinator",
            )
        if coordinator.get("session_id") != frame["session_id"]:
            raise _error(
                "stale-generation",
                "managed native child observation coordinator session changed",
            )

        native_context = status.get("native_context")
        if not isinstance(native_context, Mapping):
            raise _error(
                "unsupported",
                "managed native child observation native context is unavailable",
            )
        if native_context.get("runner_incarnation") != frame["runner_instance_id"]:
            raise _error(
                "stale-generation",
                "managed native child observation runner changed",
            )
        if native_context.get("invocation_id") != source["invocation_id"]:
            raise _error(
                "stale-generation",
                "managed native child observation invocation changed",
            )
        context_lineage = native_context.get("lineage")
        if not isinstance(context_lineage, Mapping):
            raise _error(
                "unsupported",
                "managed native child observation lineage is unavailable",
            )
        expected_lineage = {
            "owner_generation": generation,
            "lineage_id": source["lineage_id"],
            "lineage_generation": source["lineage_generation"],
            "session_uuid": frame["session_id"],
        }
        for key, expected in expected_lineage.items():
            if context_lineage.get(key) != expected:
                raise _error(
                    "stale-generation",
                    "managed native child observation %s changed" % key,
                )

        # Some enrolled-owner records carry the coordinator identity.  When
        # present, those fields are an additional exact fence.  They are not
        # the transport binding authority: the fresh controller projection
        # above remains mandatory even when every alias is absent.
        identity_fields = (
            (
                "participant_id",
                ("participant_id", "coordinator_id", "coordinator_participant_id"),
                frame["participant_id"],
                "ownership-conflict",
            ),
            (
                "session_id",
                ("session_id", "session_uuid", "coordinator_session_uuid"),
                frame["session_id"],
                "stale-generation",
            ),
            (
                "runner_instance_id",
                ("runner_instance_id", "runner_incarnation"),
                frame["runner_instance_id"],
                "stale-generation",
            ),
            (
                "lineage_id",
                ("lineage_id",),
                source["lineage_id"],
                "stale-generation",
            ),
        )
        for label, names, actual, code in identity_fields:
            expected = next(
                (owner[name] for name in names if owner.get(name) is not None),
                None,
            )
            if expected is None:
                continue
            expected = _bounded_id(expected, "managed native child owner %s" % label)
            if actual != expected:
                raise _error(
                    code,
                    "managed native child observation %s changed" % label,
                )
        return generation

    async def _persist_native_child_observation_callback(
            self, frame: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Persist one authenticated native child observation.

        This callback is deliberately observation-only.  It forwards the
        exact validated observation to the controller's transaction and
        returns only the frozen correlated ACK; it cannot create a child,
        route a mailbox, release a participant, or certify quiescence.
        """

        if not self.opt_in or not self.started:
            raise _error("unsupported", "managed daemon startup is not active")
        frame = _native_child_observation_from_frame(frame)
        deadline = time.monotonic() + OPERATION_TIMEOUT
        generation = await self._assert_native_child_observation_owner(
            frame, deadline
        )
        authority = getattr(
            self.controller, _NATIVE_CHILD_OBSERVATION_AUTHORITY_METHOD, None
        )
        if not callable(authority):
            raise _error(
                "unsupported",
                "managed native child observation authority is unavailable",
            )
        observation = frame["observation"]
        try:
            acknowledgement = authority(
                observation["observation_id"],
                generation,
                copy.deepcopy(observation),
                expected_daemon_id=self.daemon_id,
            )
            acknowledgement = await _await_bounded(
                acknowledgement,
                deadline,
                "managed native child observation",
            )
        except asyncio.CancelledError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise _error(code, "managed native child observation was refused")
            raise _error(
                "uncertain-effect",
                "managed native child observation outcome is unknown",
            )

        # The owner may be replaced while the controller awaits.  Re-check
        # all current identity fields before exposing an ACK to the runner.
        await self._assert_native_child_observation_owner(frame, deadline)
        return _native_child_observation_ack(acknowledgement, observation)

    async def _persist_native_admission(
            self, request: Mapping[str, Any], deadline: float) -> dict[str, Any]:
        """Durably pre-allow one native Agent/Task intent through the controller.

        The injected ``persist_native_admission(request_id, generation,
        admission)`` method is the atomic authority for the live owner,
        lineage, runner incarnation, parent invocation/tool-use, trusted
        definition digest, pending claim/policy, and concurrent seal.  This
        daemon method performs only bounded, non-mutating wire checks before
        calling it.  In particular it never falls back to a state-store write
        or to a per-child runner/mailbox operation.
        """

        admission = _native_admission_from_wire(request["body"])
        request_generation = request.get("generation")
        if type(request_generation) is not int or request_generation <= 0:
            raise _error(
                "invalid", "native admission request generation must be positive"
            )
        if request_generation != admission["owner_generation"]:
            raise _error(
                "stale-generation",
                "native admission request and intent generations disagree",
            )

        # The owner generation is available synchronously at enrollment and can
        # be checked before the await.  Lineage and runner-incarnation facts
        # are intentionally checked by the controller in the same transaction;
        # a separate status read here would create a TOCTOU window.
        owner = self.owner_record
        current_generation = self._owner_generation(owner)
        if type(current_generation) is not int or current_generation <= 0:
            raise _error("invalid", "managed owner generation is malformed")
        if current_generation != request_generation:
            raise _error(
                "stale-generation", "native admission owner generation is stale"
            )
        if isinstance(owner, Mapping):
            if owner.get("daemon_id") != self.daemon_id:
                raise _error(
                    "ownership-conflict", "native admission belongs to another daemon"
                )
            for name in ("lineage_id", "runner_incarnation"):
                expected = owner.get(name)
                if expected is None:
                    continue
                expected = _bounded_id(
                    expected, "managed owner %s" % name
                )
                if admission[name] != expected:
                    raise _error(
                        "ownership-conflict",
                        "native admission %s does not match managed owner" % name,
                    )
            coordinator_session = owner.get("coordinator_session_uuid")
            if coordinator_session is not None:
                coordinator_session = _bounded_id(
                    coordinator_session,
                    "managed owner coordinator_session_uuid",
                )
                if admission["parent"]["session_id"] != coordinator_session:
                    raise _error(
                        "ownership-conflict",
                        "native admission parent does not match managed coordinator",
                    )

        authority = getattr(
            self.controller, _NATIVE_ADMISSION_AUTHORITY_METHOD, None
        )
        if not callable(authority):
            # There is no safe state-only fallback for a missing authority.
            raise _error(
                "unsupported",
                "managed native admission authority is unavailable",
            )
        try:
            # No daemon/state lock is held while this injected method runs or
            # awaits.  Its implementation owns the atomic durable write and
            # must include a pending admission, lineage claim/policy, and any
            # racing fence seal before returning an acknowledgement.
            acknowledgement = authority(
                request["request_id"], request_generation, admission
            )
            acknowledgement = await _await_bounded(
                acknowledgement, deadline, "managed native admission"
            )
        except asyncio.CancelledError:
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            code = getattr(exc, "code", None)
            if isinstance(code, str) and code:
                raise _error(code, "managed native admission was refused")
            # A transport/disconnect or unexpected controller failure after
            # invocation leaves the durable outcome unknown.  Never issue a
            # second attempt from this route.
            raise _error(
                "uncertain-effect",
                "managed native admission outcome is unknown",
            )
        return _native_admission_ack(admission, acknowledgement)

    async def handle_request(self, request: Mapping[str, Any],
                             deadline: Optional[float] = None) -> dict[str, Any]:
        """Route exactly one canonical request on the persistent owner loop."""

        try:
            validated = _validate_request(request)
            if deadline is None:
                deadline = time.monotonic() + OPERATION_TIMEOUT
            elif (
                isinstance(deadline, bool)
                or not isinstance(deadline, (int, float))
                or not math.isfinite(float(deadline))
            ):
                raise _error("invalid", "managed operation deadline is invalid")
            deadline = float(deadline)
            if self.lane is not None and validated["lane"].casefold() != self.lane.casefold():
                raise _error("stale-generation", "request targets another managed lane")
            operation = validated["operation"]
            if operation not in {
                _STATUS_OPERATION, _START_OPERATION, "add-worker", "submit",
                "complete-worker", _RELEASE_OPERATION, _SWAP_OPERATION, "ctx",
                "handoff", _RECOVER_OPERATION, "shutdown", "unenroll",
                _NATIVE_ADMISSION_OPERATION,
            }:
                raise _error("unsupported", "managed operation is not implemented")
            if operation in _OBSOLETE_OPERATIONS:
                raise _error(
                    "migration-required",
                    "independent child-runner operation requires migration",
                )
            if self._start_on_loop and not self.started:
                # The supervisor boot path has already enrolled and published
                # its own process identity.  Construct loop-bound adapter
                # state only after the transport's one persistent loop exists.
                await self.start()
            if operation == _NATIVE_ADMISSION_OPERATION:
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                result = await self._persist_native_admission(
                    validated, deadline
                )
                return self._success_response(validated, result)
            if operation == _START_OPERATION:
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                if not callable(self.transcript_verifier):
                    # Public request fields, including any transcript or
                    # runtime-looking evidence, can never substitute for the
                    # profile-owned verifier injected at construction.
                    raise _error("unsupported", "managed transcript verifier is unavailable")
                bound_lane = self._bound_lane_for_request(validated["lane"])
                coordinator, participants, runner_specs = _start_inputs(
                    validated["body"], bound_lane=bound_lane
                )
                try:
                    start_method = self.controller.start
                except AttributeError:
                    raise _error("unsupported", "managed controller start is unavailable")
                if not callable(start_method):
                    raise _error("unsupported", "managed controller start is unavailable")
                # This is the exact controller boundary.  In particular, do
                # not pass public evidence or probe alternate keyword/alias
                # forms: the controller owns durable preflight and launch
                # intent ordering.
                result = start_method(
                    validated["request_id"],
                    validated["generation"],
                    coordinator,
                    participants,
                    runner_specs,
                )
                result = await _await_bounded(result, deadline, "managed start")
                from lane_managed_controller import Operation

                if not isinstance(result, Operation):
                    raise _error("invalid", "managed controller start returned no operation")
                operation_result = result.to_dict()
                _bounded_wire(operation_result, "start operation result")
                return self._success_response(validated, operation_result)
            if operation == "add-worker":
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                body = _strict_object(
                    validated["body"],
                    _ADD_WORKER_BODY_KEYS,
                    _ADD_WORKER_BODY_KEYS,
                    "add-worker body",
                )
                bound_lane = self._bound_lane_for_request(validated["lane"])
                participant = _participant_from_wire(
                    body["participant"],
                    "add-worker participant",
                    bound_lane=bound_lane,
                )
                runner_spec = _runner_spec_from_wire(
                    body["runner_spec"],
                    participant.participant_id,
                    bound_lane=bound_lane,
                )
                add_worker = getattr(self.controller, "add_worker_held", None)
                if not callable(add_worker):
                    raise _error("unsupported", "managed controller add-worker is unavailable")
                result = add_worker(
                    validated["request_id"],
                    validated["generation"],
                    participant,
                    runner_spec,
                )
                result = await _await_bounded(result, deadline, "managed add-worker")
                from lane_managed_controller import Operation

                if not isinstance(result, Operation):
                    raise _error("invalid", "managed controller add-worker returned no operation")
                operation_result = result.to_dict()
                _bounded_wire(operation_result, "add-worker operation result")
                return self._success_response(validated, operation_result)
            if operation == "complete-worker":
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                body = _strict_object(
                    validated["body"],
                    _COMPLETE_WORKER_BODY_KEYS,
                    _COMPLETE_WORKER_BODY_KEYS,
                    "complete-worker body",
                )
                participant_id = _bounded_id(
                    body["participant_id"], "participant_id"
                )
                # The public body contains no completion/evidence field.  The
                # exact runtime method owns fresh status, shutdown, process,
                # and tool-quiescence proof before releasing the claim.
                complete_worker = getattr(
                    self.controller, "complete_worker_runtime", None
                )
                if not callable(complete_worker):
                    raise _error(
                        "unsupported",
                        "managed controller completion lifecycle is unavailable",
                    )
                result = complete_worker(
                    participant_id,
                    validated["generation"],
                )
                result = await _await_bounded(
                    result, deadline, "managed complete-worker"
                )
                from lane_managed_controller import Participant

                if not isinstance(result, Participant):
                    raise _error(
                        "invalid", "managed controller completion returned no participant"
                    )
                participant_result = result.to_dict()
                _bounded_wire(participant_result, "complete-worker result")
                # Completion may release a participant-specific fence or let
                # independent recipients progress.  Wake only an already
                # known released operation; no status request is synthesized
                # merely to discover a pump target.
                if self._dispatch_operation_id is not None:
                    self._wake_dispatch_pump(self._dispatch_operation_id)
                return self._success_response(validated, participant_result)
            if operation == _SWAP_OPERATION:
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                body = _strict_object(
                    validated["body"],
                    _SWAP_BODY_KEYS,
                    frozenset({"profile"}),
                    "swap body",
                )
                profile_name = _bounded_id(body["profile"], "target profile")
                resolve_profile = getattr(self.profiles, "resolve", None)
                if not callable(resolve_profile):
                    raise _error("unsupported", "managed profile resolver is unavailable")
                profile = resolve_profile(profile_name)
                profile = await _await_bounded(
                    profile, deadline, "target profile resolution"
                )
                bound_lane = self._bound_lane_for_request(validated["lane"])
                runner_specs = _swap_runner_specs_from_wire(
                    body.get("runner_specs"), bound_lane=bound_lane
                )
                swap_method = getattr(self.controller, "swap", None)
                if not callable(swap_method):
                    raise _error("unsupported", "managed controller swap is unavailable")
                result = swap_method(
                    validated["request_id"],
                    validated["generation"],
                    profile,
                    runner_specs,
                )
                result = await _await_bounded(
                    result, deadline, "managed swap"
                )
                from lane_managed_controller import Operation

                if not isinstance(result, Operation):
                    raise _error("invalid", "managed controller swap returned no operation")
                operation_result = result.to_dict()
                _bounded_wire(operation_result, "swap operation result")
                return self._success_response(validated, operation_result)
            if operation == "ctx":
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                body = _strict_object(
                    validated["body"],
                    _CTX_BODY_KEYS,
                    frozenset({"checkpoint", "worker_policy"}),
                    "ctx body",
                )
                checkpoint = _checkpoint_from_wire(body["checkpoint"])
                worker_policy = body["worker_policy"]
                if (
                    not isinstance(worker_policy, str)
                    or worker_policy not in {"hold", "restart"}
                ):
                    raise _error(
                        "invalid",
                        "ctx worker_policy must be exactly hold or restart",
                    )
                ctx_method = getattr(self.controller, "ctx", None)
                if not callable(ctx_method):
                    raise _error("unsupported", "managed controller ctx is unavailable")
                result = ctx_method(
                    validated["request_id"],
                    validated["generation"],
                    checkpoint,
                    worker_policy,
                    None,
                )
                result = await _await_bounded(result, deadline, "managed ctx")
                from lane_managed_controller import Operation

                if not isinstance(result, Operation):
                    raise _error("invalid", "managed controller ctx returned no operation")
                operation_result = result.to_dict()
                _bounded_wire(operation_result, "ctx operation result")
                return self._success_response(validated, operation_result)
            if operation == "handoff":
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                body = _strict_object(
                    validated["body"],
                    _HANDOFF_BODY_KEYS,
                    _HANDOFF_BODY_KEYS,
                    "handoff body",
                )
                checkpoint = _checkpoint_from_wire(body["checkpoint"])
                handoff = getattr(self.controller, "handoff", None)
                if not callable(handoff):
                    raise _error("unsupported", "managed controller handoff is unavailable")
                result = handoff(
                    validated["request_id"],
                    validated["generation"],
                    checkpoint,
                )
                result = await _await_bounded(result, deadline, "managed handoff")
                result_value = _json_value(result)
                if not isinstance(result_value, Mapping):
                    raise _error("invalid", "managed controller handoff returned no record")
                _bounded_wire(result_value, "handoff result")
                return self._success_response(validated, result_value)
            if operation == _RECOVER_OPERATION:
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                body = _strict_object(
                    validated["body"],
                    _RECOVER_BODY_KEYS,
                    _RECOVER_BODY_KEYS,
                    "recover body",
                )
                operation_id = _bounded_id(body["operation_id"], "operation_id")
                result = await self._recover_native_rollover_if_needed(
                    operation_id,
                    validated["generation"],
                    deadline,
                )
                if result is None:
                    evidence = await self._collect_recovery_evidence(
                        operation_id,
                        validated["generation"],
                        deadline,
                    )
                    recover_method = getattr(self.controller, "recover", None)
                    if not callable(recover_method):
                        raise _error(
                            "unsupported", "managed controller recover is unavailable"
                        )
                    result = recover_method(
                        operation_id,
                        validated["generation"],
                        evidence,
                    )
                    result = await _await_bounded(
                        result, deadline, "managed recovery"
                    )
                from lane_managed_controller import Operation

                if not isinstance(result, Operation):
                    raise _error("invalid", "managed controller recover returned no operation")
                operation_result = result.to_dict()
                _bounded_wire(operation_result, "recover operation result")
                return self._success_response(validated, operation_result)
            if operation == _RELEASE_OPERATION:
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                body = _strict_object(
                    validated["body"],
                    frozenset({"operation_id"}),
                    frozenset({"operation_id"}),
                    "release body",
                )
                operation_id = _bounded_id(body["operation_id"], "operation_id")
                try:
                    release_method = self.controller.release
                    candidates_method = self.controller.dispatch_candidates
                    dispatch_method = self.controller.dispatch_next
                except AttributeError:
                    raise _error("unsupported", "managed controller release is unavailable")
                if not all(callable(method) for method in (
                    release_method, candidates_method, dispatch_method,
                )):
                    raise _error("unsupported", "managed controller release is unavailable")
                # Release authorizes normal work; the bounded pump then admits
                # at most one message per freshly idle recipient in this tick.
                # A controller uncertainty refusal is left durable and is
                # never retried or replayed by this router.
                release_result = release_method(operation_id, validated["generation"])
                release_result = await _await_bounded(
                    release_result, deadline, "managed release"
                )
                from lane_managed_controller import Operation

                if not isinstance(release_result, Operation):
                    raise _error("invalid", "managed controller release returned no operation")
                dispatch_metadata = await self.dispatch_pump_tick(
                    operation_id,
                    deadline=deadline,
                )
                operation_result = dict(release_result.to_dict())
                operation_result["dispatch"] = dispatch_metadata
                _bounded_wire(operation_result, "release operation result")
                # Keep the same-loop worker alive for later submissions and
                # for recipients that become idle after this response.  The
                # inline tick above preserves the release response's first
                # delivery latency; this wake owns all subsequent progress.
                self._wake_dispatch_pump(operation_id)
                return self._success_response(validated, operation_result)
            if operation == "submit":
                if not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                body = _strict_object(
                    validated["body"],
                    _SUBMIT_BODY_KEYS,
                    frozenset({"recipient_id", "payload_ref"}),
                    "submit body",
                )
                recipient_id = body.get("recipient_id")
                payload_ref = body.get("payload_ref")
                if recipient_id is None or payload_ref is None:
                    raise _error("invalid", "submit requires recipient_id and payload_ref")
                recipient_id = _bounded_id(recipient_id, "recipient_id")
                sender_id = body.get("sender_id", "user")
                sender_id = _bounded_id(sender_id, "sender_id")
                task_id = body.get("task_id")
                if task_id is not None:
                    task_id = _bounded_id(task_id, "task_id")
                submit = getattr(self.controller, "submit", None)
                if not callable(submit):
                    raise _error("unsupported", "managed controller submit is unavailable")
                # The controller owns payload bounds/digests and durable
                # request deduplication.  No client evidence is interpreted
                # as runtime acknowledgement by this transport boundary.
                result = submit(
                    validated["request_id"],
                    recipient_id,
                    payload_ref,
                    sender_id,
                    task_id,
                    generation=validated["generation"],
                )
                result = await _await_bounded(
                    result, deadline, "managed submit"
                )
                from lane_managed_controller import MailboxEntry

                if isinstance(result, MailboxEntry):
                    result_value = result.to_dict()
                else:
                    result_value = _json_value(result)
                _bounded_wire(result_value, "submit result")
                # A submission after release wakes the same-loop pump.  The
                # pump is optional for old/injected controllers; absence of
                # its exact APIs does not turn a durable submit into a
                # request failure.  Any accepted or uncertain dispatch is
                # nevertheless left to the controller's durable boundary.
                submitted_operation_id = None
                if isinstance(result_value, Mapping):
                    candidate_operation_id = result_value.get("operation_id")
                    if isinstance(candidate_operation_id, str):
                        submitted_operation_id = candidate_operation_id
                # ``ManagedController.submit`` deliberately leaves mail sent
                # after a released operation attached to the next durable
                # dispatch lookup (its public mailbox result has no active
                # operation ID).  The release boundary already recorded the
                # exact operation on this daemon, so retain that authority as
                # the wake target instead of letting a legitimate B/C submit
                # strand behind an exited pump.
                if submitted_operation_id is None:
                    known_operation_id = self._dispatch_operation_id
                    if isinstance(known_operation_id, str) and known_operation_id:
                        submitted_operation_id = known_operation_id
                if submitted_operation_id is not None:
                    if callable(getattr(self.controller, "dispatch_candidates", None)) and callable(
                        getattr(self.controller, "dispatch_next", None)
                    ):
                        try:
                            pump = await self.dispatch_pump_tick(
                                submitted_operation_id,
                                deadline=deadline,
                            )
                        except asyncio.CancelledError:
                            raise
                        except BaseException as pump_exc:
                            if isinstance(pump_exc, (KeyboardInterrupt, SystemExit)):
                                raise
                            pump = {
                                "operation_id": submitted_operation_id,
                                "iterations": 0,
                                "dispatched": [],
                                "skipped": [{
                                    "code": str(getattr(pump_exc, "code", "unknown")),
                                    "reason": "dispatch-pump-unavailable",
                                }],
                                "bounded": True,
                            }
                        if isinstance(result_value, dict):
                            result_value["dispatch_pump"] = pump
                            _bounded_wire(result_value, "submit result")
                        self._wake_dispatch_pump(submitted_operation_id)
                return self._success_response(validated, result_value)
            if operation == "shutdown":
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                _strict_object(
                    validated["body"],
                    _SHUTDOWN_BODY_KEYS,
                    _SHUTDOWN_BODY_KEYS,
                    "shutdown body",
                )
                shutdown = getattr(self.controller, "shutdown", None)
                if not callable(shutdown):
                    raise _error("unsupported", "managed controller shutdown is unavailable")
                result = shutdown(validated["generation"])
                result = await _await_bounded(result, deadline, "managed shutdown")
                result_value = _json_value(result)
                if not isinstance(result_value, Mapping):
                    raise _error("invalid", "managed controller shutdown returned no record")
                _bounded_wire(result_value, "shutdown result")
                return self._success_response(validated, result_value)
            if operation == "unenroll":
                if not self.opt_in or not self.started:
                    raise _error("unsupported", "managed daemon startup is not active")
                _strict_object(
                    validated["body"],
                    _UNENROLL_BODY_KEYS,
                    _UNENROLL_BODY_KEYS,
                    "unenroll body",
                )
                state = self._ensure_state()
                clear_owner = getattr(state, "unenroll_managed", None)
                if not callable(clear_owner):
                    raise _error(
                        "unsupported",
                        "managed owner clear authority is unavailable",
                    )
                unenroll = getattr(self.controller, "unenroll", None)
                if not callable(unenroll):
                    raise _error("unsupported", "managed controller unenroll is unavailable")
                # Controller unenrollment first proves quiescence and releases
                # every lane claim.  Clear the human-facing projection before
                # touching local discovery/ownership so a projection refusal
                # leaves the runtime and owner discoverable for a retry.
                result = unenroll(validated["generation"])
                result = await _await_bounded(result, deadline, "managed unenroll")
                result_value = _json_value(result)
                if not isinstance(result_value, Mapping):
                    raise _error("invalid", "managed controller unenroll returned no record")
                if (
                    result_value.get("phase") != "complete"
                    or result_value.get("unenrolled") is not True
                    or result_value.get("claims_released") is not True
                    or result_value.get("owner_clear_ready") is not True
                ):
                    raise _error(
                        "live-unverified",
                        "managed unenrollment lacks authoritative quiescence",
                    )
                projection_cleared = False
                owner_cleared = False
                try:
                    self.clear_owner_projection()
                    projection_cleared = True
                    self.clear_runtime()
                    owner = self.owner_record
                    generation = self._owner_generation(owner)
                    clear_owner(
                        self.daemon_id,
                        generation,
                        quiescent=True,
                        claims_released=True,
                    )
                    owner_cleared = True
                    self.owner_record = None
                    self._owner_enrolled = False
                    self.started = False
                    result_value = dict(result_value)
                    result_value["owner_cleared"] = True
                    _bounded_wire(result_value, "unenroll result")
                    return self._success_response(validated, result_value)
                except BaseException as exc:
                    if isinstance(exc, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                        raise
                    if projection_cleared and not owner_cleared and self.owner_record is not None:
                        try:
                            # A local cleanup refusal leaves the durable owner
                            # in place.  Restore its projection so the next
                            # attempt starts from one coherent visible owner.
                            self.project_owner()
                        except BaseException as restore_exc:
                            if isinstance(
                                    restore_exc,
                                    (KeyboardInterrupt, SystemExit, asyncio.CancelledError),
                            ):
                                raise
                            raise _error(
                                "uncertain-effect",
                                "managed-owner projection restoration was refused",
                            ) from restore_exc
                    raise
            status_method = getattr(self.controller, "status", None)
            if not callable(status_method):
                raise _error("unsupported", "managed controller status is unavailable")
            _strict_object(
                validated["body"],
                _STATUS_BODY_KEYS,
                _STATUS_BODY_KEYS,
                "status body",
            )
            result = status_method()
            result = await _await_bounded(
                result, deadline, "managed status"
            )
            status_value = _json_value(result)
            _bounded_wire(status_value, "status result")
            # Status is observational.  It never starts or advances the
            # dispatch worker; release/submit and the worker's own bounded
            # runtime-idle wake are the only dispatch triggers.
            return self._success_response(validated, status_value)
        except BaseException as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            # Do not expose controller/profile/runtime text on the wire.
            request_value = request if isinstance(request, Mapping) else {}
            return _response(request_value, error=exc)

    # The existing transport's embedding seam uses ``handle``.  It delegates
    # to the one canonical router and does not add a second operation surface.
    async def handle(self, request: Mapping[str, Any],
                     deadline: Optional[float] = None) -> dict[str, Any]:
        return await self.handle_request(request, deadline=deadline)


def _load_transport() -> Any:
    """Load the executable transport without importing a hyphenated module."""

    path = Path(__file__).with_name("lane-managed")
    if not path.is_file():
        raise _error("unsupported", "managed transport is unavailable")
    name = "_openrepotools_lane_managed_transport"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    if spec is None:
        raise _error("unsupported", "managed transport could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def serve_daemon(socket_path: str | os.PathLike[str], handler: Any = None, *,
                 connect_timeout: float = CONNECT_TIMEOUT,
                 operation_timeout: float = OPERATION_TIMEOUT,
                 max_bytes: int = MAX_FRAME_BYTES,
                 max_requests: Optional[int] = None,
                 stop_event: Any = None,
                 on_ready: Any = None) -> list[dict[str, Any]]:
    """Run the existing secure persistent transport on one asyncio loop."""

    if handler is None:
        raise _error("unsupported", "managed daemon handler is required")
    if isinstance(handler, ManagedDaemon):
        target = handler.handle_request
    elif callable(handler):
        target = handler
    else:
        target_method = getattr(handler, "handle_request", None)
        if not callable(target_method):
            raise _error("unsupported", "managed daemon handler is unavailable")
        target = target_method
    if on_ready is not None and not callable(on_ready):
        raise _error("invalid", "managed transport readiness callback is unavailable")
    transport = _load_transport()
    server = getattr(transport, "serve_daemon", None)
    if not callable(server):
        raise _error("unsupported", "managed persistent transport is unavailable")
    # ``on_ready`` is an exact transport hook, invoked only after bind,
    # chmod(0600), listen, and endpoint verification.  Do not emulate this by
    # registering discovery before the transport call or by catching a
    # TypeError and retrying without the hook: either behavior reintroduces a
    # discovery-before-readiness race.
    kwargs = {
        "connect_timeout": connect_timeout,
        "operation_timeout": operation_timeout,
        "max_bytes": max_bytes,
        "max_requests": max_requests,
        "stop_event": stop_event,
    }
    if on_ready is not None:
        kwargs["on_ready"] = on_ready
    return server(socket_path, target, **kwargs)


def run_supervisor(
    lane: str,
    socket_path: str | os.PathLike[str],
    daemon_id: str,
    opt_in: bool,
    *,
    env: Optional[Mapping[str, str]] = None,
    helper: Any = None,
    runner: Any = None,
    state: Any = None,
    profiles: Any = None,
    controller: Any = None,
    adapter: Any = None,
    projection: Any = None,
    connect_timeout: float = CONNECT_TIMEOUT,
    operation_timeout: float = OPERATION_TIMEOUT,
    max_bytes: int = MAX_FRAME_BYTES,
    max_requests: Optional[int] = None,
    stop_event: Any = None,
) -> list[dict[str, Any]]:
    """Boot one explicit managed owner in the foreground.

    Owner enrollment and endpoint discovery are synchronous durable writes
    before the transport starts and before profile/adapter/controller
    construction.  The latter is deferred to the transport's persistent
    asyncio loop by ``ManagedDaemon.handle_request`` so runner-owned async
    objects cannot be created on a short-lived bootstrap loop.
    """

    if opt_in is not True:
        raise _error("unsupported", "managed supervisor startup requires explicit opt-in")
    daemon = ManagedDaemon(
        state=state,
        profiles=profiles,
        controller=controller,
        adapter=adapter,
        daemon_id=daemon_id,
        opt_in=True,
        lane=lane,
        env=env,
        helper=helper,
        runner=runner,
        projection=projection,
    )
    daemon._ensure_state()
    # Verify the registry writer capability before taking local durable
    # ownership.  A missing/incompatible projection helper therefore cannot
    # leave a locally enrolled owner that the human-facing guard cannot see.
    daemon.preflight_projection()
    daemon._enroll_owner()
    # The helper owns its own registry lock and commit boundary.  This call is
    # deliberately outside the ManagedStateStore lock held by enroll_managed.
    daemon.project_owner()
    daemon._start_on_loop = True

    # The runtime record is the crash-recovery discovery authority.  Publish
    # it only from the transport's readiness callback, after the owner-only
    # socket has been bound, chmod(0600), listened, and verified.  The
    # callback is synchronous and contains no SDK activity.
    runtime_published = False

    def publish_runtime() -> None:
        nonlocal runtime_published
        daemon.register_runtime(socket_path)
        runtime_published = True

    try:
        responses = serve_daemon(
            socket_path,
            daemon.handle_request,
            connect_timeout=connect_timeout,
            operation_timeout=operation_timeout,
            max_bytes=max_bytes,
            max_requests=max_requests,
            stop_event=stop_event,
            on_ready=publish_runtime,
        )
        if not runtime_published:
            raise _error("unknown", "managed transport did not report listen readiness")
        # The transport returns only for an orderly shutdown or an explicit
        # bounded embedding stop.  Any exception above retains the durable
        # discovery record for recovery.
        daemon.clear_runtime()
        return responses
    except BaseException:
        # Never clear an endpoint after a crash, cancellation, transport
        # refusal, or uncertain shutdown.  Recovery must inspect its exact
        # PID/start-token evidence instead of assuming the owner is absent.
        raise


def _supervisor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lane_managed_daemon.py",
        description="foreground managed-lane supervisor (experimental)",
    )
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--lane", required=True, help="canonical managed lane name")
    parser.add_argument("--socket", dest="socket_path", required=True,
                        help="owner-only Unix socket path")
    parser.add_argument("--daemon-id", required=True,
                        help="durable managed daemon identity")
    parser.add_argument("--opt-in", action="store_true",
                        help="explicitly enable managed supervisor startup")
    parser.add_argument("--connect-timeout", type=float, default=CONNECT_TIMEOUT)
    parser.add_argument("--operation-timeout", type=float, default=OPERATION_TIMEOUT)
    parser.add_argument("--max-bytes", type=int, default=MAX_FRAME_BYTES)
    parser.add_argument("--max-requests", type=int, default=None,
                        help=argparse.SUPPRESS)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the hidden foreground ``--serve`` supervisor entry point."""

    parser = _supervisor_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.serve:
        parser.error("--serve is required")
    try:
        run_supervisor(
            args.lane,
            args.socket_path,
            args.daemon_id,
            args.opt_in,
            connect_timeout=args.connect_timeout,
            operation_timeout=args.operation_timeout,
            max_bytes=args.max_bytes,
            max_requests=args.max_requests,
        )
    except DaemonError as exc:
        print("lane_managed_daemon: %s: managed supervisor failed" % exc.code,
              file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except BaseException:
        print("lane_managed_daemon: unknown: managed supervisor failed",
              file=sys.stderr)
        return 1
    return 0


__all__ = [
    "CONNECT_TIMEOUT",
    "DaemonError",
    "MAX_FRAME_BYTES",
    "ManagedDaemon",
    "NATIVE_ADMISSION_OPERATION",
    "OPERATION_TIMEOUT",
    "PROCESS_IDENTITY_TIMEOUT",
    "NATIVE_ARCHITECTURE",
    "NATIVE_SCHEMA_VERSION",
    "resolve_payload_reference",
    "run_supervisor",
    "SCHEMA_VERSION",
    "serve_daemon",
]


if __name__ == "__main__":
    raise SystemExit(main())
