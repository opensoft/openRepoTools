# SPDX-License-Identifier: Apache-2.0
"""Optional Claude SDK adapter for managed lane participants.

The managed supervisor deliberately has no dependency on the Claude Agent SDK.
This module is the narrow boundary between that standard-library supervisor and
the optional official Python SDK.  Importing this module is safe on a machine
which does not have the SDK installed.  The production entry point is the
dedicated ``--runner`` process: it reads and validates its first bounded frame,
scrubs the *process* environment, and only then imports ``claude_agent_sdk``.

The adapter is intentionally conservative.  Initialisation is promptless and
held, exact resume and fresh-session options are mutually exclusive, and a
normal user query is possible only after an explicit ``release`` control.  A
fake SDK object can be supplied to :func:`drive_client` for deterministic tests;
it is not evidence that live SDK support is verified.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import dataclasses
import hashlib
import importlib
import inspect
import json
import math
import os
import platform as _platform
import re
import select
import signal
import subprocess
import sys
import time
import traceback
import uuid as _uuid
from collections import deque
from collections.abc import AsyncIterable, AsyncIterator, Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from lane_managed_swap import (
    NativeSwapContractError,
    canonical_digest as _native_swap_digest,
    validate_release_authorization as _validate_native_swap_authorization,
    validate_release_binding as _validate_native_swap_binding,
    validate_release_boundary as _validate_native_swap_boundary,
)


MAX_FRAME_BYTES = 1024 * 1024
DEFAULT_STARTUP_DEADLINE = 5.0
DEFAULT_OPERATION_DEADLINE = 120.0
# ``/proc/<pid>/stat`` is not available on macOS.  The ``ps`` fallback is a
# read-only helper, but it still needs a finite bound: a process identity
# lookup must never hold an adapter operation open indefinitely.
PROCESS_IDENTITY_TIMEOUT = 1.0
MAX_DIAGNOSTIC_EVENTS = 256
# Keep the public readiness counter bounded as well as its diagnostic tail.
# Once this cap is reached the counter is a lower-fidelity "at least" count;
# retaining an exact lifetime count would recreate the unbounded state that
# the bounded runner is intended to avoid.
MAX_INITIALIZATION_EVENTS_SEEN = 4096
MAX_COMPLETED_TOOL_EVIDENCE = 512
MAX_UNCERTAIN_TOOL_EVIDENCE = 256
MAX_NATIVE_CHILD_RECORDS = 256
MAX_NATIVE_CHILD_HISTORY = 256
MAX_NATIVE_LIFECYCLE_EVENTS = 1024
MAX_NATIVE_PROGRESS_EVENTS = 32
MAX_NATIVE_UNCERTAINTIES = 256
MAX_NATIVE_DEFINITION_BYTES = MAX_FRAME_BYTES
MAX_NATIVE_DEFINITION_DEPTH = 32
MAX_NATIVE_DEFINITION_NODES = 65536
# Native child observations are an ordered persistence stream, not a second
# lifecycle ledger.  Keep the stream bounded without evicting an old identity:
# an eviction would permit an old acknowledgement to be replayed as a new
# child fact after the runner has crossed a source boundary.
# The evidence contract bounds observations per joined child run and bounds
# the number of child runs retained by one runner.  Keep the former name as a
# small queue/concurrency bound used by the existing private IPC helpers.
MAX_NATIVE_CHILD_OBSERVATIONS = 16
MAX_NATIVE_CHILD_OBSERVATIONS_PER_RUN = 16
MAX_NATIVE_CHILD_RUNS = 256

# A private sentinel used only between the runner's bounded stdin reader and
# its control adapter.  A sentinel is preferable to leaving a queue waiter
# behind on EOF: the latter makes ``asyncio.run`` wait for an executor-backed
# stream on platforms where add_reader is unavailable.
_CONTROL_EOF = object()

# This token is intentionally private and never reachable from the runner wire
# protocol.  Unit tests that need to exercise the runner/IPC choreography with
# a fake SDK must inject it through the direct Python call; the production
# subprocess always imports and gates the official package normally.
_INTERNAL_TEST_HARNESS_TOKEN = object()


def _internal_test_harness(sdk_module: Any) -> tuple[Any, Any]:
    """Build the explicit in-process fake SDK seam used by adapter tests."""

    if sdk_module is None:
        raise SdkAdapterError("invalid", "internal runner test harness requires an SDK module")
    return _INTERNAL_TEST_HARNESS_TOKEN, sdk_module

# The SDK's transport intentionally re-merges os.environ when it starts the
# Claude subprocess.  Keep this list in this module (rather than relying only
# on ClaudeAgentOptions.env) so a runner can establish a complete clean process
# environment before the optional package is imported.
_PROVIDER_ENV_NAMES = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_API_URL",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_BEDROCK_BASE_URL",
        "ANTHROPIC_VERTEX_BASE_URL",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_PROVIDER",
        "CLAUDE_PROVIDER",
        "CLAUDE_API_KEY",
        "CLAUDE_AUTH_TOKEN",
        "AUTH_TOKEN",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
        "AWS_BEDROCK_REGION",
        "BEDROCK_REGION",
        "BEDROCK_MODEL_ID",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_REGION",
        "CLOUD_ML_REGION",
        "VERTEXAI_PROJECT",
        "VERTEXAI_LOCATION",
    }
)

_PROVIDER_ENV_PREFIXES = (
    "ANTHROPIC_AUTH_",
    "ANTHROPIC_VERTEX_",
    "CLAUDE_CODE_USE_",
    "CLAUDE_CODE_PROVIDER",
    "VERTEXAI_",
    "BEDROCK_",
    "AWS_BEDROCK_",
)

_UNSUPPORTED_TOOL_NAMES = frozenset(
    {
        "team",
        "teams",
    }
)

_NATIVE_CHILD_TOOL_NAMES = frozenset({"agent", "task"})
_NATIVE_CROSS_SOURCE_DUPLICATE = object()

# The controller's native-swap target launch carries this restrictive marker
# in the trusted startup fingerprint.  It is deliberately not a capability
# grant: a forged/overly broad marker can only force the bound-release path,
# while the private controller authorization still owns the release authority.
# Keep the accepted locations narrow so a public release payload can never set
# this mode after startup.
_NATIVE_SWAP_TARGET_MARKER = "native_swap_target"


def _native_swap_target_requires_bound_release(value: Any) -> bool:
    """Return whether a launch was selected as a native-swap target.

    ``value`` is the already-extracted ``RunnerSpec.fingerprint`` mapping.
    The marker is read once from that launch-time object; this helper never
    unwraps a nested ``fingerprint`` key or examines a release command/payload.
    Controller-generated swap specs use only
    ``spec.fingerprint.native_config.native_swap_target``.
    """

    if not isinstance(value, Mapping):
        return False
    native_config = value.get("native_config")
    return (
        isinstance(native_config, Mapping)
        and native_config.get(_NATIVE_SWAP_TARGET_MARKER) is True
    )


def _native_swap_target_marker_error(value: Any) -> Optional[str]:
    """Validate the launch-only native-swap marker spelling.

    The marker is intentionally closed: only the nested literal boolean is
    meaningful.  A malformed/false/string marker is a startup refusal rather
    than an ordinary native launch, and the tempting top-level fingerprint
    alias is rejected instead of being silently ignored.
    """

    if isinstance(value, Mapping):
        # Inspect the enclosing wire object before selecting its fingerprint;
        # otherwise a stale top-level alias would disappear when
        # ``RunnerSpec.from_mapping`` filters unknown fields.
        if _NATIVE_SWAP_TARGET_MARKER in value and "fingerprint" in value:
            return (
                "native swap target marker must be nested in fingerprint.native_config"
            )
        fingerprint = value.get("fingerprint", value)
    else:
        fingerprint = getattr(value, "fingerprint", None)
    if not isinstance(fingerprint, Mapping):
        return None
    if _NATIVE_SWAP_TARGET_MARKER in fingerprint:
        return (
            "native swap target marker must be nested in fingerprint.native_config"
        )
    if "native_config" not in fingerprint:
        return None
    native_config = fingerprint.get("native_config")
    if not isinstance(native_config, Mapping):
        return "native_config launch fingerprint must be an object"
    if _NATIVE_SWAP_TARGET_MARKER in native_config and (
        native_config.get(_NATIVE_SWAP_TARGET_MARKER) is not True
    ):
        return "native swap target marker must be the literal boolean true"
    return None

_DETACHED_INPUT_KEYS = frozenset(
    {
        "run_in_background",
        "runInBackground",
        "background",
        "detached",
        "detach",
        "setsid",
        "nohup",
        "disown",
    }
)

_SUPPORTED_PERMISSION_MODES = frozenset(
    {"default", "acceptEdits", "plan", "bypassPermissions", "dontAsk", "auto"}
)
_READ_ONLY_DENY_TOOLS = frozenset(
    {
        "bash",
        "write",
        "edit",
        "notebookedit",
        "multiedit",
        "apply_patch",
        "execute",
        "shell",
        "computer",
        "webbrowser",
    }
)
_READ_ONLY_BUILTIN_TOOLS = frozenset(
    {"read", "glob", "grep", "ls", "webfetch", "websearch", "todoread", "search", "list"}
)


class SdkAdapterError(Exception):
    """A stable, operator-visible refusal from the optional SDK boundary."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(self.message)

    def __repr__(self) -> str:  # pragma: no cover - convenience when debugging
        return f"SdkAdapterError({self.code!r}, {self.message!r})"

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _native_swap_error(error: NativeSwapContractError) -> SdkAdapterError:
    """Translate the pure swap contract's stable refusal into SDK errors."""

    return SdkAdapterError(error.code, error.message)


def _native_swap_binding(value: Any) -> dict[str, Any]:
    try:
        return _validate_native_swap_binding(value)
    except NativeSwapContractError as exc:
        raise _native_swap_error(exc) from exc


def _native_swap_boundary(
    value: Any, *, expected_binding: Any = None
) -> dict[str, Any]:
    try:
        return _validate_native_swap_boundary(
            value, expected_binding=expected_binding
        )
    except NativeSwapContractError as exc:
        raise _native_swap_error(exc) from exc


def _native_swap_authorization(
    value: Any, *, validation_id: Any, binding: Any
) -> dict[str, Any]:
    try:
        return _validate_native_swap_authorization(
            value,
            expected_validation_id=validation_id,
            expected_binding=binding,
        )
    except NativeSwapContractError as exc:
        raise _native_swap_error(exc) from exc


def _native_swap_refusal_ack(
    validation_id: str, binding: Mapping[str, Any], authorization_id: str
) -> dict[str, Any]:
    """Build a closed negative authorization observation without granting."""

    acknowledgement: dict[str, Any] = {
        "validation_id": validation_id,
        "authorized": False,
        "authorization_id": authorization_id,
        "binding": copy.deepcopy(dict(binding)),
    }
    acknowledgement["authorization_digest"] = _native_swap_digest(acknowledgement)
    return acknowledgement


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        return (value,)
    try:
        return tuple(value)
    except TypeError:
        return (value,)


def _model_identifiers(value: Any) -> tuple[str, ...]:
    """Extract model identifiers from SDK strings or model metadata objects.

    Claude 2.1's init payload uses entries such as ``{"value": ...,
    "resolvedModel": ..., "displayName": ...}``, while older fakes and
    runtimes use a list of strings.  ``displayName`` is intentionally not
    treated as an exact identifier unless no stronger value exists.
    """

    if value is None:
        return ()
    if isinstance(value, Mapping):
        values: list[str] = []
        for key in (
            "value",
            "resolvedModel",
            "resolved_model",
            "model",
            "id",
            "name",
            "displayName",
            "display_name",
        ):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                values.append(candidate.strip())
        # A mapping may itself be the model map (name -> details).
        if not values:
            for key, candidate in value.items():
                if isinstance(key, str) and key.strip():
                    values.append(key.strip())
                values.extend(_model_identifiers(candidate))
        return tuple(dict.fromkeys(values))
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (bytes, bytearray)):
        try:
            decoded = value.decode().strip()
        except UnicodeDecodeError:
            return ()
        return (decoded,) if decoded else ()
    if isinstance(value, (list, tuple, set, frozenset)):
        result: list[str] = []
        for item in value:
            result.extend(_model_identifiers(item))
        return tuple(dict.fromkeys(result))
    # Dataclass/SDK model metadata objects are intentionally handled without
    # importing SDK types in this module.
    result = []
    for name in (
        "value",
        "resolvedModel",
        "resolved_model",
        "model",
        "id",
        "name",
        "displayName",
        "display_name",
    ):
        candidate = getattr(value, name, None)
        if isinstance(candidate, str) and candidate.strip():
            result.append(candidate.strip())
    return tuple(dict.fromkeys(result))


def _model_match_identifiers(value: Any) -> tuple[str, ...]:
    """Return only exact model keys suitable for membership checks.

    Human-facing ``displayName``/``description`` values are useful evidence but
    must never make an unsupported model look supported.  ``value`` and
    ``resolvedModel`` are the identifiers emitted by the Claude CLI.
    """

    if isinstance(value, Mapping):
        result: list[str] = []
        for key in (
            "value",
            "resolvedModel",
            "resolved_model",
            "model",
            "id",
            "name",
        ):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                result.append(candidate.strip())
        return tuple(dict.fromkeys(result))
    if isinstance(value, (list, tuple, set, frozenset)):
        result: list[str] = []
        for item in value:
            result.extend(_model_match_identifiers(item))
        return tuple(dict.fromkeys(result))
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    return _model_identifiers(value)


def _model_records(value: Any) -> list[dict[str, Any]]:
    """Flatten model catalogue entries while retaining value/resolved pairs."""

    if value is None:
        return []
    if isinstance(value, Mapping):
        # A single entry has an identifier key; a map of model names to entry
        # dictionaries is also accepted.
        if any(key in value for key in ("value", "resolvedModel", "resolved_model", "model", "id", "name")):
            return [dict(value)]
        records: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                record = dict(item)
                record.setdefault("value", key)
                records.append(record)
            elif isinstance(key, str):
                records.append({"value": key})
        return records
    if isinstance(value, (list, tuple, set, frozenset)):
        records = []
        for item in value:
            records.extend(_model_records(item))
        return records
    if isinstance(value, str):
        return [{"value": value}]
    # The official SDK/CLI boundary has emitted model metadata as objects in
    # some releases.  Preserve the requested ``value`` and its
    # ``resolvedModel`` on one record; flattening an object to two independent
    # strings would lose the very relationship the readiness check proves.
    record: dict[str, Any] = {}
    for key in (
        "value",
        "resolvedModel",
        "resolved_model",
        "model",
        "id",
        "name",
        "displayName",
        "display_name",
        "description",
        "supportsEffort",
        "supportedEffortLevels",
    ):
        try:
            candidate = getattr(value, key)
        except (AttributeError, TypeError):
            continue
        if candidate is not None:
            record[key] = candidate
    if record:
        return [record]
    identifiers = _model_match_identifiers(value)
    return [{"value": item} for item in identifiers]


def _mapping_copy(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def _first_nonempty(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _runtime_json_value(value: Any, *, depth: int = 0) -> Any:
    """Return a bounded JSON value for runtime identity hashing.

    Runtime identity is derived from the effective launch definition, not from
    arbitrary object representations.  Refusing an unsupported value keeps a
    digest stable across processes and prevents a caller from hiding mutable
    state behind ``repr``.
    """

    if depth > 32:
        raise SdkAdapterError("invalid", "runtime configuration is too deeply nested")
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SdkAdapterError("invalid", "runtime configuration contains a non-finite number")
        return value
    if isinstance(value, (Path, os.PathLike)):
        return str(value)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value, key=lambda item: str(item)):
            if not isinstance(key, str):
                raise SdkAdapterError("invalid", "runtime configuration keys must be strings")
            result[key] = _runtime_json_value(value[key], depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_runtime_json_value(item, depth=depth + 1) for item in value]
    if isinstance(value, (set, frozenset)):
        values = [_runtime_json_value(item, depth=depth + 1) for item in value]
        return sorted(values, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    raise SdkAdapterError(
        "invalid",
        f"runtime configuration contains unsupported value {type(value).__name__}",
    )


def _runtime_digest(value: Any) -> str:
    encoded = json.dumps(
        _runtime_json_value(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RunnerSpec:
    """Immutable launch/readiness description for one participant.

    ``session_id`` is the exact native UUID for resume and the fixed reserved
    UUID for a fresh session.  A few explicit aliases are retained because the
    state/controller layers use both ``expected_email`` and
    ``account_email`` terminology.  They are normalised in ``__post_init__``;
    the generated SDK options never contain the aliases.

    All fields are optional at construction time so a wire payload can be
    decoded before a precise refusal is returned.  ``build_sdk_options`` and
    ``InitializationTracker.finalize`` are the validation boundaries.
    """

    session_id: Optional[str] = None
    mode: str = "resume"
    account_email: Optional[str] = None
    permission_mode: Optional[str] = None
    model: Optional[str] = None
    supported_models: tuple[str, ...] = field(default_factory=tuple)
    fingerprint: Mapping[str, Any] = field(default_factory=dict)
    config_dir: Optional[str] = None
    cwd: Optional[str] = None
    environment: Mapping[str, str] = field(default_factory=dict)

    # Launch settings retained from profile resolution.  These are values, not
    # credentials; credentials are deliberately never read or copied here.
    tools: Any = None
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)
    read_only_tools: tuple[str, ...] = field(default_factory=tuple)
    read_only: bool = False
    disallowed_tools: tuple[str, ...] = field(default_factory=tuple)
    effort: Optional[str] = None
    settings: Optional[str] = None
    add_dirs: tuple[str, ...] = field(default_factory=tuple)
    strict_mcp_config: Optional[bool] = True
    setting_sources: Optional[tuple[str, ...]] = None
    max_buffer_size: Optional[int] = None
    extra_args: Mapping[str, str | None] = field(default_factory=dict)

    # Bounded runner controls.
    startup_deadline: float = DEFAULT_STARTUP_DEADLINE
    operation_deadline: float = DEFAULT_OPERATION_DEADLINE
    frame_limit: int = MAX_FRAME_BYTES

    # Profile/session display context is non-secret and useful in evidence.
    profile_name: Optional[str] = None
    session_name: Optional[str] = None
    bound_lane: Optional[str] = None
    participant_id: Optional[str] = None
    profile: Optional[str] = None
    participant: Optional[str] = None
    worktree: Optional[str] = None
    role: Optional[str] = None
    parent_id: Optional[str] = None
    task_id: Optional[str] = None

    # Compatibility aliases accepted by tests/controllers and normalised below.
    expected_email: Optional[str] = None
    expected_account: Optional[str] = None
    expected_account_email: Optional[str] = None
    expected_permission_mode: Optional[str] = None
    expected_model: Optional[str] = None
    launch_fingerprint: Mapping[str, Any] = field(default_factory=dict)
    env: Mapping[str, str] = field(default_factory=dict)
    profile_config_dir: Optional[str] = None
    native_session_id: Optional[str] = None
    session_uuid: Optional[str] = None
    resume_id: Optional[str] = None
    fixed_session_id: Optional[str] = None
    fresh_session_id: Optional[str] = None
    resume: Optional[bool] = None
    fresh: Optional[bool] = None

    def __post_init__(self) -> None:
        mode = str(self.mode or "resume").strip().lower().replace("_", "-")
        if mode in {"start", "new", "fresh-session", "fresh_session"}:
            mode = "fresh"
        elif mode in {"load", "restore", "exact-resume", "exact_resume"}:
            mode = "resume"
        if mode == "resume" and self.resume is False:
            mode = "fresh"
        if mode == "resume" and self.fresh is True and self.resume is not True:
            mode = "fresh"
        object.__setattr__(self, "mode", mode)

        sid = _first_nonempty(
            self.session_id,
            self.native_session_id,
            self.session_uuid,
            self.resume_id if mode == "resume" else None,
            self.fixed_session_id if mode == "fresh" else None,
            self.fresh_session_id if mode == "fresh" else None,
        )
        object.__setattr__(self, "session_id", None if sid is None else str(sid))

        email = _first_nonempty(
            self.account_email,
            self.expected_email,
            self.expected_account_email,
            self.expected_account,
        )
        object.__setattr__(self, "account_email", None if email is None else str(email))

        permission = _first_nonempty(
            self.permission_mode,
            self.expected_permission_mode,
        )
        object.__setattr__(
            self,
            "permission_mode",
            None if permission is None else str(permission),
        )

        expected_model = _first_nonempty(self.model, self.expected_model)
        object.__setattr__(
            self, "model", None if expected_model is None else str(expected_model)
        )

        models = self.supported_models
        if not models:
            fp = _mapping_copy(self.fingerprint)
            models = _first_nonempty(
                fp.get("supported_models"),
                fp.get("models"),
                fp.get("available_models"),
            ) or ()
        object.__setattr__(
            self,
            "supported_models",
            _model_identifiers(models),
        )

        fp = _mapping_copy(self.fingerprint)
        if not fp:
            fp = _mapping_copy(self.launch_fingerprint)
        # The spec's resolved target identity is authoritative at the adapter
        # boundary.  Controller payloads may carry a launch fingerprint copied
        # from an earlier profile; overwrite only identity fields while
        # retaining execution/capability settings from that fingerprint.
        for key, value in (
            ("account_email", self.account_email),
            ("permission_mode", self.permission_mode),
            ("model", self.model),
        ):
            if value is not None:
                fp[key] = value
        object.__setattr__(self, "fingerprint", fp)
        object.__setattr__(self, "launch_fingerprint", dict(fp))

        env = _mapping_copy(self.environment)
        if not env:
            env = _mapping_copy(self.env)
        object.__setattr__(self, "environment", {str(k): str(v) for k, v in env.items()})
        object.__setattr__(self, "env", dict(self.environment))
        object.__setattr__(self, "extra_args", {
            str(key): None if value is None else str(value)
            for key, value in _mapping_copy(self.extra_args).items()
        })

        if self.config_dir is None and self.profile_config_dir is not None:
            object.__setattr__(self, "config_dir", str(self.profile_config_dir))
        elif self.config_dir is not None:
            object.__setattr__(self, "config_dir", str(self.config_dir))
        if self.cwd is not None:
            object.__setattr__(self, "cwd", str(self.cwd))
        elif self.worktree is not None:
            object.__setattr__(self, "cwd", str(self.worktree))

        if self.profile_name is None and self.profile is not None:
            object.__setattr__(self, "profile_name", str(self.profile))
        if self.session_name is not None:
            object.__setattr__(self, "session_name", str(self.session_name))
        if self.bound_lane is not None:
            object.__setattr__(self, "bound_lane", str(self.bound_lane))
        if self.participant_id is None and self.participant is not None:
            object.__setattr__(self, "participant_id", str(self.participant))
        if self.worktree is not None:
            object.__setattr__(self, "worktree", str(self.worktree))

        object.__setattr__(self, "allowed_tools", tuple(str(v) for v in _as_tuple(self.allowed_tools)))
        object.__setattr__(self, "read_only_tools", tuple(str(v) for v in _as_tuple(self.read_only_tools)))
        object.__setattr__(self, "read_only", bool(self.read_only))
        object.__setattr__(self, "disallowed_tools", tuple(str(v) for v in _as_tuple(self.disallowed_tools)))
        object.__setattr__(self, "add_dirs", tuple(str(v) for v in _as_tuple(self.add_dirs)))
        if self.setting_sources is not None:
            object.__setattr__(
                self,
                "setting_sources",
                tuple(str(v) for v in _as_tuple(self.setting_sources)),
            )

        # Explicit boolean aliases win over the textual mode only when mode was
        # left at its default.  This keeps wire payloads using ``fresh: true``
        # unsurprising while preserving an explicit ``mode``.
        for name in ("startup_deadline", "operation_deadline"):
            try:
                value = float(getattr(self, name))
            except (TypeError, ValueError):
                value = DEFAULT_STARTUP_DEADLINE if name == "startup_deadline" else DEFAULT_OPERATION_DEADLINE
            if value <= 0:
                value = DEFAULT_STARTUP_DEADLINE if name == "startup_deadline" else DEFAULT_OPERATION_DEADLINE
            object.__setattr__(self, name, value)
        try:
            frame_limit = int(self.frame_limit)
        except (TypeError, ValueError):
            frame_limit = MAX_FRAME_BYTES
        object.__setattr__(self, "frame_limit", max(1024, min(frame_limit, MAX_FRAME_BYTES)))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RunnerSpec":
        """Decode a bounded wire mapping without retaining unknown keys."""

        raw = dict(payload)
        nested = raw.get("spec")
        if isinstance(nested, Mapping):
            raw = dict(nested)

        # Profile objects often arrive nested under ``profile``.  Only copy
        # non-secret identity/config fields from that object.
        profile = raw.get("profile")
        if isinstance(profile, Mapping):
            raw.setdefault("account_email", _first_nonempty(profile.get("email"), profile.get("account_email")))
            raw.setdefault("config_dir", _first_nonempty(profile.get("config_dir"), profile.get("profilePath")))
            raw.setdefault("profile_name", profile.get("name"))

        aliases = {
            "session_uuid": "session_id",
            "native_session_id": "session_id",
            "resume_id": "session_id",
            "fixed_session_id": "session_id",
            "fresh_session_id": "session_id",
            "expected_email": "account_email",
            "expected_account_email": "account_email",
            "expected_account": "account_email",
            "expected_permission_mode": "permission_mode",
            "expected_model": "model",
            "launch_fingerprint": "fingerprint",
            "env": "environment",
            "profile_config_dir": "config_dir",
        }
        normal = dict(raw)
        for source, target in aliases.items():
            if target not in normal and source in raw:
                normal[target] = raw[source]
        allowed = {f.name for f in dataclasses.fields(cls)}
        return cls(**{key: value for key, value in normal.items() if key in allowed})

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RunnerSpec":
        return cls.from_mapping(payload)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe, non-secret description for the runner wire."""

        result: dict[str, Any] = {
            "session_id": self.session_id,
            "mode": self.mode,
            "account_email": self.account_email,
            "permission_mode": self.permission_mode,
            "model": self.model,
            "supported_models": list(self.supported_models),
            "fingerprint": dict(self.fingerprint),
            "config_dir": self.config_dir,
            "cwd": self.cwd,
            "environment": dict(self.environment),
            "tools": self.tools,
            "allowed_tools": list(self.allowed_tools),
            "read_only_tools": list(self.read_only_tools),
            "read_only": self.read_only,
            "disallowed_tools": list(self.disallowed_tools),
            "effort": self.effort,
            "settings": self.settings,
            "add_dirs": list(self.add_dirs),
            "strict_mcp_config": self.strict_mcp_config,
            "setting_sources": None if self.setting_sources is None else list(self.setting_sources),
            "max_buffer_size": self.max_buffer_size,
            "extra_args": dict(self.extra_args),
            "startup_deadline": self.startup_deadline,
            "operation_deadline": self.operation_deadline,
            "frame_limit": self.frame_limit,
            "profile_name": self.profile_name,
            "session_name": self.session_name,
            "bound_lane": self.bound_lane,
            "participant_id": self.participant_id,
            "role": self.role,
            "parent_id": self.parent_id,
            "task_id": self.task_id,
        }
        return result


def _spec_get(spec: Any, *names: str, default: Any = None) -> Any:
    if isinstance(spec, Mapping):
        for name in names:
            if name in spec and spec[name] is not None:
                return spec[name]
    else:
        for name in names:
            value = getattr(spec, name, None)
            if value is not None:
                return value
    return default


def _normalise_spec(spec: RunnerSpec | Mapping[str, Any]) -> RunnerSpec:
    if isinstance(spec, RunnerSpec):
        return spec
    if isinstance(spec, Mapping):
        marker_error = _native_swap_target_marker_error(spec)
        if marker_error is not None:
            raise SdkAdapterError("invalid", marker_error)
        return RunnerSpec.from_mapping(spec)
    # Do not silently use arbitrary object attributes as a wire source unless
    # it has the normal RunnerSpec identity fields; this catches controller bugs
    # at the adapter boundary with a useful stable code.
    if hasattr(spec, "session_id") or hasattr(spec, "session_uuid"):
        values: dict[str, Any] = {}
        for field_info in dataclasses.fields(RunnerSpec):
            if hasattr(spec, field_info.name):
                values[field_info.name] = getattr(spec, field_info.name)
        return RunnerSpec(**values)
    raise SdkAdapterError("invalid", "runner specification must be a RunnerSpec or object")


def _valid_session_uuid(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        _uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _assert_spec_launchable(spec: RunnerSpec) -> None:
    if spec.mode not in {"resume", "fresh"}:
        raise SdkAdapterError("invalid", f"unsupported runner mode {spec.mode!r}")
    if not _valid_session_uuid(spec.session_id):
        raise SdkAdapterError(
            "loader-failed",
            "an exact native UUID is required for both resume and fresh sessions",
        )
    if spec.mode == "resume" and spec.fresh is True:
        raise SdkAdapterError("invalid", "resume and fresh session modes are mutually exclusive")
    if spec.mode == "fresh" and spec.resume is True:
        raise SdkAdapterError("invalid", "resume and fresh session modes are mutually exclusive")
    # A supported model list is the stored capability boundary.  The actual
    # init message may omit model, so validate the stored model before launch.
    if spec.supported_models and spec.model and spec.model not in spec.supported_models:
        raise SdkAdapterError(
            "unsupported",
            f"stored model {spec.model!r} is not in the supported model set",
        )
    if spec.config_dir is not None and not str(spec.config_dir).strip():
        raise SdkAdapterError("invalid", "profile config directory cannot be empty")
    if spec.permission_mode is not None and spec.permission_mode not in _SUPPORTED_PERMISSION_MODES:
        raise SdkAdapterError("permission-mismatch", f"unsupported permission mode {spec.permission_mode!r}")


@dataclass(frozen=True)
class RuntimeIdentity:
    """The exact SDK-selected runtime used by a managed coordinator.

    Resolving this identity is a read-only operation.  It selects the CLI
    through the official SDK transport and runs only the SDK's version probe;
    it does not construct a client or connect to the CLI.
    """

    sdk_package: str
    sdk_version: str
    sdk_path: str
    cli_path: str
    cli_version: str
    cli_sha256: str
    mode: str
    platform: str
    platform_machine: str
    config_digest: str
    identity_digest: str = field(init=False)

    def __post_init__(self) -> None:
        values = {
            "sdk_package": self.sdk_package,
            "sdk_version": self.sdk_version,
            "sdk_path": self.sdk_path,
            "cli_path": self.cli_path,
            "cli_version": self.cli_version,
            "cli_sha256": self.cli_sha256,
            "mode": self.mode,
            "platform": self.platform,
            "platform_machine": self.platform_machine,
            "config_digest": self.config_digest,
        }
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ValueError("runtime identity fields must be non-empty strings")
        if not re.fullmatch(r"[0-9a-f]{64}", self.cli_sha256):
            raise ValueError("runtime identity requires a complete lowercase CLI SHA-256 digest")
        if not re.fullmatch(r"[0-9a-f]{64}", self.config_digest):
            raise ValueError("runtime identity requires a complete lowercase config digest")
        object.__setattr__(self, "identity_digest", _runtime_digest(values))

    def to_dict(self) -> dict[str, str]:
        return {
            "schema": "lane-managed-runtime/v1",
            "sdk_package": self.sdk_package,
            "sdk_version": self.sdk_version,
            "sdk_path": self.sdk_path,
            "cli_path": self.cli_path,
            "cli_version": self.cli_version,
            "cli_sha256": self.cli_sha256,
            "mode": self.mode,
            "platform": self.platform,
            "platform_machine": self.platform_machine,
            "config_digest": self.config_digest,
            "identity_digest": self.identity_digest,
        }


@dataclass(frozen=True)
class CapabilityDecision:
    """Fail-closed Gate 0 result for one exact runtime identity."""

    verdict: str
    reason_code: str
    reason: str
    identity: Optional[RuntimeIdentity] = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    evidence_reference: Optional[str] = None

    def __post_init__(self) -> None:
        if self.verdict not in {"verified", "unsupported", "inconclusive"}:
            raise ValueError(f"invalid capability verdict {self.verdict!r}")
        if not isinstance(self.reason_code, str) or not self.reason_code.strip():
            raise ValueError("capability decision requires a reason code")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("capability decision requires a reason")
        if self.identity is not None and not isinstance(self.identity, RuntimeIdentity):
            raise ValueError("capability decision identity has the wrong type")
        if not isinstance(self.evidence, Mapping):
            raise ValueError("capability decision evidence must be a mapping")

    @property
    def identity_digest(self) -> Optional[str]:
        return None if self.identity is None else self.identity.identity_digest

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "identity": None if self.identity is None else self.identity.to_dict(),
            "identity_digest": self.identity_digest,
            "evidence_reference": self.evidence_reference,
            "evidence": copy.deepcopy(dict(self.evidence)),
        }


def _runtime_config_payload(spec: RunnerSpec) -> dict[str, Any]:
    """Build the non-secret launch configuration covered by Gate 0."""

    options = build_sdk_options(spec)
    # ``resume``/``session_id`` identify the conversation, not the selected
    # runtime.  ``env`` may contain caller-provided values, so it is excluded;
    # the selected profile directory is already represented explicitly.
    options = {
        key: value
        for key, value in options.items()
        if key not in {"resume", "session_id", "env", "hooks", "include_hook_events"}
    }
    return {
        "mode": spec.mode,
        "config_dir": spec.config_dir,
        "profile_name": spec.profile_name,
        "session_name": spec.session_name,
        "bound_lane": spec.bound_lane,
        "options": options,
    }


def _sdk_transport_class(sdk_module: Any) -> Any:
    """Load the SDK transport class that owns CLI selection."""

    direct = getattr(sdk_module, "SubprocessCLITransport", None)
    if direct is not None:
        return direct
    package = getattr(sdk_module, "__name__", None)
    if not isinstance(package, str) or not package.strip():
        return None
    try:
        transport_module = importlib.import_module(
            f"{package}._internal.transport.subprocess_cli"
        )
    except (ImportError, ModuleNotFoundError, AttributeError):
        return None
    return getattr(transport_module, "SubprocessCLITransport", None)


def _is_official_sdk_module(sdk_module: Any) -> bool:
    """Recognize the official package boundary without trusting its shape."""

    # A missing version or a changed/missing SDK attribute must produce a live
    # refusal, not turn an official import into an injectable fake seam.
    return getattr(sdk_module, "__name__", None) == "claude_agent_sdk"


def _resolve_sdk_module(sdk_module: Any = None) -> Any:
    if sdk_module is not None:
        return sdk_module
    try:
        return importlib.import_module("claude_agent_sdk")
    except (ImportError, ModuleNotFoundError) as exc:
        raise SdkAdapterError(
            "inconclusive",
            "the official Claude Agent SDK is unavailable for runtime identity resolution",
        ) from exc


def _sdk_package_version(sdk_module: Any) -> Optional[str]:
    version = getattr(sdk_module, "__version__", None)
    if isinstance(version, str) and version.strip():
        return version.strip()
    package = getattr(sdk_module, "__package__", None) or getattr(sdk_module, "__name__", None)
    if not isinstance(package, str) or not package.strip():
        return None
    try:
        from importlib import metadata as importlib_metadata

        value = importlib_metadata.version(package)
    except Exception:  # noqa: BLE001 - metadata is optional for test seams
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _read_cli_version(cli_path: str) -> str:
    """Use the same promptless ``-v`` probe as the official SDK transport."""

    try:
        completed = subprocess.run(
            [cli_path, "-v"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SdkAdapterError(
            "inconclusive",
            f"selected Claude CLI version probe failed: {exc}",
        ) from exc
    output = "\n".join(
        value for value in (completed.stdout, completed.stderr) if isinstance(value, str)
    )
    match = re.search(r"(?<![0-9])([0-9]+\.[0-9]+\.[0-9]+)(?![0-9])", output)
    if completed.returncode != 0 or match is None:
        raise SdkAdapterError(
            "inconclusive",
            "selected Claude CLI did not provide a usable version from the official probe",
        )
    return match.group(1)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
    except OSError as exc:
        raise SdkAdapterError(
            "inconclusive",
            f"selected Claude CLI cannot be hashed: {exc}",
        ) from exc
    return digest.hexdigest()


def _stream_json_mode(transport: Any) -> str:
    command_builder = getattr(transport, "_build_command", None)
    if not callable(command_builder):
        raise SdkAdapterError(
            "inconclusive",
            "SDK transport does not expose its selected command mode",
        )
    try:
        command = list(command_builder())
    except Exception as exc:  # noqa: BLE001 - SDK shape is an explicit gate
        raise SdkAdapterError(
            "inconclusive",
            f"SDK transport command mode could not be resolved: {exc}",
        ) from exc
    if not all(isinstance(item, str) for item in command):
        raise SdkAdapterError("inconclusive", "SDK transport command contains a non-string argument")
    pairs = {command[index]: command[index + 1] for index in range(len(command) - 1)}
    if pairs.get("--output-format") != "stream-json" or pairs.get("--input-format") != "stream-json":
        raise SdkAdapterError(
            "unsupported",
            "the selected SDK transport is not the supported stream-json mode",
        )
    if getattr(transport, "_is_streaming", True) is not True:
        raise SdkAdapterError("unsupported", "the selected SDK transport is not streaming")
    return "stream-json"


async def _empty_prompt_stream() -> AsyncIterator[dict[str, Any]]:
    """Match ``ClaudeSDKClient.connect(None)``'s empty async stream."""

    return
    yield {}  # pragma: no cover - keeps this function an async generator


def resolve_runtime_identity(
    spec: RunnerSpec | Mapping[str, Any],
    *,
    sdk_module: Any = None,
) -> RuntimeIdentity:
    """Resolve the exact runtime without constructing or connecting a client.

    The official SDK's own ``SubprocessCLITransport._find_cli`` is used so a
    bundled CLI wins over a system executable exactly as it does at connect
    time.  The only subprocess started here is the CLI's documented ``-v``
    version probe; no credentials, account endpoint, prompt, or model request
    is involved.
    """

    runner_spec = _normalise_spec(spec)
    marker_error = _native_swap_target_marker_error(runner_spec)
    if marker_error is not None:
        raise SdkAdapterError("invalid", marker_error)
    _assert_spec_launchable(runner_spec)
    module = _resolve_sdk_module(sdk_module)
    sdk_version = _sdk_package_version(module)
    if sdk_version is None:
        raise SdkAdapterError("inconclusive", "SDK package version is unavailable")
    sdk_path_value = getattr(module, "__file__", None)
    if not isinstance(sdk_path_value, (str, os.PathLike)) or not str(sdk_path_value).strip():
        raise SdkAdapterError("inconclusive", "SDK package path is unavailable")
    transport_class = _sdk_transport_class(module)
    if transport_class is None:
        raise SdkAdapterError(
            "inconclusive",
            "SDK CLI selection transport is unavailable",
        )
    options_type = getattr(module, "ClaudeAgentOptions", None)
    if options_type is None:
        raise SdkAdapterError("inconclusive", "SDK options type is unavailable")
    try:
        # The official client turns ``connect(None)`` into an empty async
        # iterable before constructing its transport.  Using a string here
        # could select a different prompt/print path and make the reported
        # mode diverge from the production connection.
        options = _normalise_sdk_options(module, build_sdk_options(runner_spec))
        transport = transport_class(prompt=_empty_prompt_stream(), options=options)
    except SdkAdapterError:
        raise
    except Exception as exc:  # noqa: BLE001 - constructor shape is a gate
        raise SdkAdapterError(
            "inconclusive",
            f"SDK transport could not be constructed for identity selection: {exc}",
        ) from exc

    cli_path_value = getattr(transport, "_cli_path", None)
    if not isinstance(cli_path_value, (str, os.PathLike)) or not str(cli_path_value).strip():
        finder = getattr(transport, "_find_cli", None)
        if not callable(finder):
            raise SdkAdapterError("inconclusive", "SDK transport has no CLI selection method")
        try:
            cli_path_value = finder()
        except Exception as exc:  # noqa: BLE001 - selection refusal is evidence
            raise SdkAdapterError(
                "inconclusive",
                f"SDK CLI selection failed: {exc}",
            ) from exc
    if not isinstance(cli_path_value, (str, os.PathLike)) or not str(cli_path_value).strip():
        raise SdkAdapterError("inconclusive", "SDK CLI selection returned no executable path")

    cli_path = Path(cli_path_value).expanduser()
    try:
        cli_path = cli_path.resolve(strict=True)
    except OSError as exc:
        raise SdkAdapterError("inconclusive", f"selected Claude CLI path is unavailable: {exc}") from exc
    if not cli_path.is_file():
        raise SdkAdapterError("inconclusive", "selected Claude CLI path is not a regular file")
    cli_version = _read_cli_version(str(cli_path))
    cli_sha256 = _sha256_file(cli_path)
    mode = _stream_json_mode(transport)
    config_digest = _runtime_digest(
        {
            "sdk_version": sdk_version,
            "mode": mode,
            "platform": sys.platform,
            "platform_machine": _platform.machine(),
            "config": _runtime_config_payload(runner_spec),
        }
    )
    try:
        return RuntimeIdentity(
            sdk_package="claude-agent-sdk",
            sdk_version=sdk_version,
            sdk_path=str(Path(sdk_path_value).expanduser().resolve()),
            cli_path=str(cli_path),
            cli_version=cli_version,
            cli_sha256=cli_sha256,
            mode=mode,
            platform=sys.platform,
            platform_machine=_platform.machine() or "unknown",
            config_digest=config_digest,
        )
    except ValueError as exc:
        raise SdkAdapterError("inconclusive", f"selected runtime identity is invalid: {exc}") from exc


def _evidence_value(record: Mapping[str, Any], name: str) -> Any:
    """Read one field from the canonical internal Gate 0 record."""

    return record.get(name)


def _observation_status(value: Any) -> str:
    if isinstance(value, bool):
        return "observed" if value else "not-observed"
    if value is None:
        return "unknown"
    text = str(value).strip().casefold().replace("_", "-").replace(" ", "-")
    if text in {"observed", "present", "seen", "true", "yes", "passed", "complete"}:
        return "observed"
    if text in {"not-observed", "absent", "not-seen", "false", "no", "clear", "zero"}:
        return "not-observed"
    if text in {"not-exercised", "not-run", "unverified", "unavailable"}:
        return "not-exercised"
    if text in {"unknown", "missing", "inconclusive"}:
        return "unknown"
    if text in {"unsupported", "incompatible", "failed"}:
        return "incompatible"
    return "unknown"


def _exact_nonnegative_int(value: Any) -> Optional[int]:
    """Accept only an actual, non-negative integer observation."""

    if type(value) is not int or value < 0:
        return None
    return value


def _decision(
    verdict: str,
    reason_code: str,
    reason: str,
    identity: Optional[RuntimeIdentity],
    evidence: Mapping[str, Any],
) -> CapabilityDecision:
    reference = evidence.get("evidence_reference")
    return CapabilityDecision(
        verdict=verdict,
        reason_code=reason_code,
        reason=reason,
        identity=identity,
        evidence=copy.deepcopy(dict(evidence)),
        evidence_reference=reference,
    )


def assess_held_swap(
    identity: RuntimeIdentity,
    evidence_record: Any,
) -> CapabilityDecision:
    """Assess controller-owned Gate 0 evidence for ``identity``.

    Evidence is deliberately supplied separately from ``RunnerSpec``.  A
    public fingerprint, a requested ``verified`` flag, or a probe path in the
    launch specification is never read as capability authority.  The record
    must be an internal Gate 0 record with the exact identity digest and both
    the positive orphan and terminal-cleared controls exercised.
    """

    if not isinstance(identity, RuntimeIdentity):
        return _decision(
            "inconclusive",
            "runtime-identity-missing",
            "held-swap capability cannot be assessed without a resolved runtime identity",
            None,
            {},
        )
    if not isinstance(evidence_record, Mapping):
        return _decision(
            "inconclusive",
            "gate0-evidence-missing",
            "no controller-owned Gate 0 capability evidence is available",
            identity,
            {},
        )
    evidence = copy.deepcopy(dict(evidence_record))
    if evidence.get("authority") != "lane-managed-internal":
        return _decision(
            "inconclusive",
            "untrusted-evidence",
            "capability evidence is not marked as controller-owned internal evidence",
            identity,
            evidence,
        )
    reference = evidence.get("evidence_reference")
    if not isinstance(reference, str) or not reference.strip():
        return _decision(
            "inconclusive",
            "evidence-reference-missing",
            "controller-owned capability evidence has no bounded evidence reference",
            identity,
            evidence,
        )
    recorded_digest = evidence.get("identity_digest")
    if not isinstance(recorded_digest, str) or not recorded_digest.strip():
        return _decision(
            "inconclusive",
            "evidence-identity-missing",
            "capability evidence does not identify the exact selected runtime",
            identity,
            evidence,
        )
    if recorded_digest != identity.identity_digest:
        return _decision(
            "inconclusive",
            "runtime-identity-mismatch",
            "capability evidence was collected for a different SDK, CLI, mode, platform, or configuration",
            identity,
            evidence,
        )

    if evidence.get("identity") != identity.to_dict():
        return _decision("inconclusive", "evidence-identity-conflict",
                         "the recorded identity description is missing or contradictory",
                         identity, evidence)
    canonical_sections = {
        "probe_validity": {"identity_match", "instrumentation", "bounded_observation",
                           "observation_complete", "isolation", "cleanup"},
        "startup": {"held_before_dispatch"},
        "positive_orphan": {"record_loaded", "notification_enqueued", "wake_observed",
                            "model_dispatch_attempt"},
        "terminal_cleared": {"source_terminal_stop", "worker_state_cleared", "target_connect",
                             "restored_orphans", "wake", "enqueue", "model_dispatch",
                             "pre_release_model_requests"},
    }
    for section, allowed_fields in canonical_sections.items():
        value = evidence.get(section)
        if isinstance(value, Mapping) and set(value) - allowed_fields:
            return _decision("inconclusive", "evidence-fields-unknown",
                             "Gate 0 observations contain noncanonical fields",
                             identity, evidence)

    if evidence.get("schema") != "lane-managed-gate0/v1":
        return _decision(
            "inconclusive",
            "evidence-schema-missing",
            "capability evidence does not use the strict Gate 0 record schema",
            identity,
            evidence,
        )
    probe_validity = evidence.get("probe_validity")
    if not isinstance(probe_validity, Mapping):
        return _decision(
            "inconclusive",
            "probe-validity-missing",
            "Gate 0 evidence does not prove identity, instrumentation, bounded completion, isolation, and cleanup",
            identity,
            evidence,
        )
    for field_name in (
        "identity_match",
        "instrumentation",
        "bounded_observation",
        "observation_complete",
        "isolation",
        "cleanup",
    ):
        status = _observation_status(probe_validity.get(field_name))
        if status == "observed":
            continue
        return _decision(
            "inconclusive",
            f"probe-{field_name.replace('_', '-')}",
            f"Gate 0 probe validity field {field_name!r} was not observed",
            identity,
            evidence,
        )

    positive = evidence.get("positive_orphan")
    target = evidence.get("terminal_cleared")
    startup = evidence.get("startup")
    if not isinstance(positive, Mapping):
        return _decision(
            "inconclusive",
            "orphan-positive-control-unreachable",
            "the strict Gate 0 record has no positive orphan control section",
            identity,
            evidence,
        )
    if not isinstance(startup, Mapping):
        return _decision(
            "inconclusive",
            "hold-boundary-unproven",
            "the strict Gate 0 record has no promptless hold section",
            identity,
            evidence,
        )
    if not isinstance(target, Mapping):
        return _decision(
            "inconclusive",
            "terminal-startup-not-exercised",
            "the strict Gate 0 record has no terminal-cleared target section",
            identity,
            evidence,
        )

    for field_name, reason_code, reason in (
        ("record_loaded",
         "orphan-positive-control-unreachable",
         "the positive orphan record-load control was not exercised"),
        ("notification_enqueued",
         "orphan-positive-control-unreachable",
         "the positive orphan notification enqueue was not observed"),
        ("wake_observed",
         "orphan-positive-control-unreachable",
         "the positive orphan wake was not observed"),
        ("model_dispatch_attempt",
         "model-dispatch-unknown",
         "the positive control did not separately observe a model-dispatch attempt"),
    ):
        status = _observation_status(_evidence_value(positive, field_name))
        if status == "incompatible":
            return _decision("unsupported", reason_code, reason, identity, evidence)
        if status != "observed":
            return _decision("inconclusive", reason_code, reason, identity, evidence)

    for field_name, reason_code, reason in (
        ("held_before_dispatch",
         "hold-boundary-unproven",
         "promptless coordinator startup was not proven held before inference"),
    ):
        status = _observation_status(_evidence_value(startup, field_name))
        if status == "incompatible":
            return _decision("unsupported", reason_code, reason, identity, evidence)
        if status != "observed":
            return _decision("inconclusive", reason_code, reason, identity, evidence)

    for field_name, reason_code, reason in (
        ("source_terminal_stop",
         "terminal-stop-not-exercised",
         "source native child/tool terminal stop was not observed"),
        ("worker_state_cleared",
         "terminal-state-clear-not-exercised",
         "supported durable worker-state clearing was not observed"),
        ("target_connect",
         "terminal-startup-not-exercised",
         "target held startup was not observed"),
    ):
        status = _observation_status(_evidence_value(target, field_name))
        if status == "incompatible":
            return _decision("unsupported", reason_code, reason, identity, evidence)
        if status != "observed":
            return _decision("inconclusive", reason_code, reason, identity, evidence)

    restored = _evidence_value(target, "restored_orphans")
    restored_count = _exact_nonnegative_int(restored)
    if restored_count is None:
        return _decision(
            "inconclusive",
            "target-orphan-state-unknown",
            "target startup did not report a non-negative integer restored-orphan count",
            identity,
            evidence,
        )
    if restored_count != 0:
        return _decision(
            "unsupported",
            "target-orphan-restored",
            "target startup restored a native orphan before release",
            identity,
            evidence,
        )

    for field_name, reason_code, reason in (
        ("wake",
         "target-orphan-wake",
         "target startup emitted an orphan wake before release"),
        ("enqueue",
         "target-orphan-wake",
         "target startup enqueued an orphan notification before release"),
        ("model_dispatch",
         "target-model-dispatch",
         "target startup dispatched a model request before release"),
    ):
        status = _observation_status(_evidence_value(target, field_name))
        if status == "observed":
            return _decision("unsupported", reason_code, reason, identity, evidence)
        if status in {"unknown", "not-exercised", "incompatible"}:
            return _decision("inconclusive", reason_code, f"{reason}; absence was not proven", identity, evidence)

    model_requests = _evidence_value(target, "pre_release_model_requests")
    model_request_count = _exact_nonnegative_int(model_requests)
    if model_request_count is None:
        return _decision(
            "inconclusive",
            "target-model-dispatch-unknown",
            "target startup did not report a non-negative integer pre-release model-request count",
            identity,
            evidence,
        )
    if model_request_count != 0:
        return _decision(
            "unsupported",
            "target-model-dispatch",
            "target startup dispatched a model request before release",
            identity,
            evidence,
        )
    return _decision(
        "verified",
        "gate0-verified",
        "the exact runtime passed held startup, positive orphan, and terminal-cleared controls",
        identity,
        evidence,
    )


def preflight_held_swap(
    spec: RunnerSpec | Mapping[str, Any],
    evidence_record: Any,
    *,
    sdk_module: Any = None,
) -> CapabilityDecision:
    """Resolve and assess Gate 0 before a controller interrupts its source."""

    try:
        identity = resolve_runtime_identity(spec, sdk_module=sdk_module)
    except SdkAdapterError as exc:
        verdict = "unsupported" if exc.code == "unsupported" else "inconclusive"
        return _decision(verdict, exc.code, exc.message, None, {})
    return assess_held_swap(identity, evidence_record)


def _read_only_allowlist(spec: RunnerSpec) -> tuple[str, ...]:
    """Return the explicit read-only tool boundary, or refuse its absence."""

    values = spec.read_only_tools or spec.allowed_tools
    if not values and isinstance(spec.tools, (list, tuple, set, frozenset)):
        values = tuple(str(item) for item in spec.tools)
    if not spec.read_only:
        return tuple(values)
    if not values:
        raise SdkAdapterError(
            "unsupported",
            "claimless read-only participants require an explicit builtin tool allowlist",
        )
    result: list[str] = []
    for value in values:
        name = str(value).strip()
        if not name:
            raise SdkAdapterError("invalid", "read-only tool allowlist contains an empty name")
        folded = name.casefold()
        if folded.startswith("mcp__") or folded in _READ_ONLY_DENY_TOOLS:
            raise SdkAdapterError("unsupported", f"tool {name!r} is not permitted for read-only participants")
        if folded not in _READ_ONLY_BUILTIN_TOOLS:
            raise SdkAdapterError("unsupported", f"unknown read-only builtin tool {name!r}")
        result.append(name)
    return tuple(dict.fromkeys(result))


def _is_forbidden_provider_key(key: str) -> bool:
    upper = str(key).upper()
    if upper in _PROVIDER_ENV_NAMES:
        return True
    return any(upper.startswith(prefix) for prefix in _PROVIDER_ENV_PREFIXES)


def scrubbed_runner_environment(
    base_env: Mapping[str, Any] | None,
    spec: RunnerSpec | Mapping[str, Any] | None = None,
    *,
    config_dir: str | os.PathLike[str] | None = None,
    profile_name: str | None = None,
    session_name: str | None = None,
) -> dict[str, str]:
    """Build a complete clean environment for a dedicated SDK runner.

    ``base_env`` is copied, never mutated.  Explicit spec values are merged,
    then provider/auth overrides are removed again so a malformed profile input
    cannot reintroduce them.  ``CLAUDE_CONFIG_DIR``, the optional profile and
    session display names, and the canonical bound-lane guard locator are the
    only managed context values set here.  This function intentionally never
    reads a credential file or invokes a profile launcher.
    """

    if spec is None:
        runner_spec = RunnerSpec(
            config_dir=None if config_dir is None else str(config_dir),
            profile_name=profile_name,
            session_name=session_name,
            session_id="00000000-0000-4000-8000-000000000000",
        )
    else:
        runner_spec = _normalise_spec(spec)
        if config_dir is not None or profile_name is not None or session_name is not None:
            runner_spec = dataclasses.replace(
                runner_spec,
                config_dir=runner_spec.config_dir if config_dir is None else str(config_dir),
                profile_name=runner_spec.profile_name if profile_name is None else str(profile_name),
                session_name=runner_spec.session_name if session_name is None else str(session_name),
            )
    result: dict[str, str] = {}
    for key, value in dict(base_env or {}).items():
        if value is None:
            continue
        name = str(key)
        if _is_forbidden_provider_key(name):
            continue
        result[name] = str(value)

    # Merge only the explicit environment supplied by the caller/profile.  A
    # second scrub is intentional: profile metadata is untrusted input too.
    for key, value in runner_spec.environment.items():
        name = str(key)
        if _is_forbidden_provider_key(name):
            continue
        if value is not None:
            result[name] = str(value)

    if runner_spec.config_dir:
        result["CLAUDE_CONFIG_DIR"] = str(runner_spec.config_dir)
    if runner_spec.profile_name:
        result["CLAUDE_PROFILE_NAME"] = str(runner_spec.profile_name)
    if runner_spec.session_name:
        # The prompt guard checks managed session-name hints before the Claude
        # fallback.  A stale inherited hint must not outrank the canonical
        # durable participant name, so remove those aliases when the exact
        # name is available and set only the supported SDK-facing field.
        result.pop("LANE_MANAGED_SESSION_NAME", None)
        result.pop("LANE_SESSION_NAME", None)
        result["CLAUDE_SESSION_NAME"] = str(runner_spec.session_name)
    if runner_spec.bound_lane:
        # ``LANE_MANAGED_BOUND_LANE`` is the canonical guard locator.  Do not
        # preserve an inherited legacy lane hint that could disagree with the
        # durable participant binding; the guard still proves ownership from
        # its roster and process evidence.
        result.pop("LANE_MANAGED_LANE", None)
        result.pop("LANES_LANE", None)
        result["LANE_MANAGED_BOUND_LANE"] = str(runner_spec.bound_lane)

    # CLAUDE_CONFIG_DIR is deliberately preserved/selected; it is not a
    # credential and the SDK needs it to locate the already-authorized profile.
    return result


def build_sdk_options(spec: RunnerSpec | Mapping[str, Any]) -> dict[str, Any]:
    """Return SDK option values without importing the optional SDK.

    The mapping is consumed by ``ClaudeAgentOptions`` inside the runner.  Exact
    resume has only ``resume``; fresh has only ``session_id``.  In particular,
    no ``continue_conversation``, ``fork_session``, title, picker, or
    ``session_store`` option is emitted.
    """

    runner_spec = _normalise_spec(spec)
    _assert_spec_launchable(runner_spec)
    options: dict[str, Any] = {}
    definitions = runner_spec.fingerprint.get("trusted_definitions")
    if definitions is not None:
        native_definition_facts(definitions)
        agents = {}
        supported = {
            "description", "prompt", "tools", "disallowedTools", "model", "skills",
            "memory", "mcpServers", "initialPrompt", "maxTurns", "background",
            "effort", "permissionMode",
        }
        for name, raw_definition in definitions.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(raw_definition, Mapping):
                raise SdkAdapterError("invalid", "native agent definitions require a name and mapping")
            definition = copy.deepcopy(dict(raw_definition))
            for alias, canonical in (("permission_mode", "permissionMode"), ("allowed_tools", "tools")):
                if alias in definition:
                    value = definition.pop(alias)
                    if canonical in definition and definition[canonical] != value:
                        raise SdkAdapterError("invalid", "conflicting native agent policy aliases")
                    definition[canonical] = value
            if set(definition) - supported:
                raise SdkAdapterError("unsupported", "native agent definition contains unsupported policy fields")
            if any(not isinstance(definition.get(key), str) or not definition[key].strip()
                   for key in ("description", "prompt")):
                raise SdkAdapterError("unsupported", "native agent requires its complete description and prompt")
            tools = definition.get("tools")
            if not isinstance(tools, list) or not tools or any(not isinstance(tool, str) or not tool.strip() for tool in tools):
                raise SdkAdapterError("unsupported", "native agent requires an explicit effective tool list")
            permission = definition.get("permissionMode")
            if permission is not None and permission not in _SUPPORTED_PERMISSION_MODES:
                raise SdkAdapterError("unsupported", "native agent permission mode is unsupported")
            if runner_spec.read_only and not {tool.casefold() for tool in tools}.issubset(_READ_ONLY_BUILTIN_TOOLS):
                raise SdkAdapterError("unsupported", "distinct writable child policy under a read-only coordinator is not supported by this adapter")
            agents[name] = definition
        if agents:
            options["agents"] = agents
    if runner_spec.mode == "resume":
        options["resume"] = runner_spec.session_id
    else:
        options["session_id"] = runner_spec.session_id

    # Values below are copied only if explicitly present.  Omitting model from
    # the options is valid when the stored fingerprint and supported model set
    # establish it; inventing a model would invalidate readiness evidence.
    for name in (
        "tools",
        "permission_mode",
        "model",
        "effort",
        "settings",
        "max_buffer_size",
    ):
        value = getattr(runner_spec, name)
        if value is not None:
            options[name] = value
    readonly_allowlist = _read_only_allowlist(runner_spec)
    if runner_spec.read_only:
        options["tools"] = list(readonly_allowlist)
        options["allowed_tools"] = list(readonly_allowlist)
        options["strict_mcp_config"] = True
    if runner_spec.allowed_tools:
        options["allowed_tools"] = list(runner_spec.allowed_tools)
    if runner_spec.disallowed_tools:
        options["disallowed_tools"] = list(runner_spec.disallowed_tools)
    if runner_spec.add_dirs:
        options["add_dirs"] = list(runner_spec.add_dirs)
    if runner_spec.cwd:
        options["cwd"] = runner_spec.cwd
    if runner_spec.strict_mcp_config is not None:
        options["strict_mcp_config"] = bool(runner_spec.strict_mcp_config)
    if runner_spec.setting_sources is not None:
        options["setting_sources"] = list(runner_spec.setting_sources)
    extra_args = dict(runner_spec.extra_args)
    forbidden_extra = {
        "resume",
        "session-id",
        "session_id",
        "continue",
        "continue-conversation",
        "fork",
        "fork-session",
        "title",
    }
    if any(str(key).lstrip("-").casefold() in forbidden_extra for key in extra_args):
        raise SdkAdapterError(
            "invalid",
            "resume/fork/continue/title options are not permitted by the exact-session adapter",
        )
    if runner_spec.session_name:
        if "session-name" in extra_args:
            raise SdkAdapterError(
                "invalid",
                "session-name is not a supported SDK extra argument; use session_name",
            )
        existing_name = extra_args.get("name")
        if existing_name is not None and str(existing_name) != str(runner_spec.session_name):
            raise SdkAdapterError("invalid", "session name conflicts with the participant specification")
        extra_args["name"] = str(runner_spec.session_name)
    if extra_args:
        options["extra_args"] = extra_args

    # Hook lifecycle messages are the portable evidence path.  The dedicated
    # runner's process environment is scrubbed separately before SDK import;
    # this env mapping also makes fake SDK tests observable and protects SDK
    # implementations that use only options.env.
    options["include_hook_events"] = True
    options["env"] = scrubbed_runner_environment(runner_spec.environment, runner_spec)
    return options


def _event_to_mapping(event: Any) -> dict[str, Any]:
    """Convert SDK dataclasses, raw mappings, and test doubles to a mapping."""

    if isinstance(event, Mapping):
        return dict(event)
    if dataclasses.is_dataclass(event):
        try:
            result = dataclasses.asdict(event)
            if not result.get("type"):
                class_name = type(event).__name__.casefold()
                if "result" in class_name:
                    result["type"] = "result"
                elif "assistant" in class_name:
                    result["type"] = "assistant"
                elif "user" in class_name:
                    result["type"] = "user"
                elif "system" in class_name:
                    result["type"] = "system"
                elif "stream" in class_name:
                    result["type"] = "stream"
            return result
        except (TypeError, ValueError):
            pass
    result: dict[str, Any] = {}
    for name in (
        "type",
        "subtype",
        "data",
        "event",
        "hook_event",
        "hook_event_name",
        "session_id",
        "uuid",
        "origin",
        "terminal_reason",
        "message_id",
        "model",
        "is_error",
        "errors",
        "result",
        "account",
        "current_permission_mode",
        "session_state",
        "content",
        "tool_name",
        "tool_use_id",
        "tool_input",
        "tool_response",
        "error",
        "agent_id",
        "agent_type",
        "task_id",
        "task_type",
        "parent_agent_id",
        "parent_task_id",
        "parent_tool_use_id",
        "transcript_path",
        "agent_transcript_path",
        "cwd",
        "permission_mode",
        "stop_hook_active",
        "stop_reason",
        "status",
        "patch",
        "invocation_id",
        "prompt_id",
        "event_cursor",
        "sequence",
    ):
        if hasattr(event, name):
            result[name] = getattr(event, name)
    if not result:
        result["value"] = repr(event)
    return result


def _merged_event_data(event: Mapping[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    merged = dict(data) if isinstance(data, Mapping) else {}
    # Raw JSON events generally put these values at top level.  Keep data's
    # values authoritative when both spellings are present.
    for key, value in event.items():
        if key not in {"data", "message", "content"} and key not in merged:
            merged[key] = value
    message = event.get("message")
    if isinstance(message, Mapping):
        for key, value in message.items():
            merged.setdefault(key, value)
    return merged


def _get_ci(mapping: Mapping[str, Any], *names: str) -> Any:
    lowered = {str(key).lower(): value for key, value in mapping.items()}
    for name in names:
        if name in mapping:
            return mapping[name]
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return None


class InitializationTracker:
    """Validate promptless SDK loader evidence before marking a runner ready.

    The tracker accepts both raw wire events and official SDK message objects.
    It records an ``error_during_execution`` result even when it arrives before
    the init response (the observed behavior for a missing exact resume UUID).
    ``session_id`` and ``model`` in init are optional: exact identity comes from
    the prevalidated UUID/options and model from the stored launch fingerprint
    plus supported-model membership.
    """

    def __init__(
        self,
        spec: RunnerSpec | Mapping[str, Any] | None = None,
        *,
        expected_account: Optional[str] = None,
        expected_email: Optional[str] = None,
        expected_account_email: Optional[str] = None,
        expected_permission_mode: Optional[str] = None,
        expected_model: Optional[str] = None,
        supported_models: Iterable[str] = (),
        fingerprint: Mapping[str, Any] | None = None,
        expected_fingerprint: Mapping[str, Any] | None = None,
        expected_worktree: str | os.PathLike[str] | None = None,
        session_id: Optional[str] = None,
        expected_session_id: Optional[str] = None,
        expected_session_uuid: Optional[str] = None,
        max_event_bytes: int = MAX_FRAME_BYTES,
    ) -> None:
        runner_spec: RunnerSpec | None
        if spec is None:
            runner_spec = None
        else:
            runner_spec = _normalise_spec(spec)
        fp = _mapping_copy(fingerprint)
        fp = {**_mapping_copy(expected_fingerprint), **fp}
        if runner_spec is not None:
            fp = {**dict(runner_spec.fingerprint), **fp}
        self.expected_email = _first_nonempty(
            expected_email,
            expected_account_email,
            expected_account,
            runner_spec.account_email if runner_spec else None,
            fp.get("account_email"),
            fp.get("expected_email"),
            fp.get("email"),
        )
        self.expected_permission_mode = _first_nonempty(
            expected_permission_mode,
            runner_spec.permission_mode if runner_spec else None,
            fp.get("permission_mode"),
            fp.get("current_permission_mode"),
        )
        self.expected_model = _first_nonempty(
            expected_model,
            runner_spec.model if runner_spec else None,
            fp.get("model"),
        )
        declared_models = _model_identifiers(supported_models)
        if not declared_models and runner_spec is not None:
            declared_models = tuple(runner_spec.supported_models)
        if not declared_models:
            declared_models = _model_identifiers(
                fp.get("supported_models")
                or fp.get("models")
                or fp.get("available_models")
            )
        self.supported_models = declared_models
        self.expected_session_id = _first_nonempty(
            session_id,
            expected_session_id,
            expected_session_uuid,
            runner_spec.session_id if runner_spec else None,
        )
        self.fingerprint = fp
        self.expected_worktree = None if expected_worktree is None else str(expected_worktree)
        if self.expected_worktree is None:
            self.expected_worktree = _first_nonempty(
                fp.get("worktree"),
                fp.get("workspace"),
            )
        self.max_event_bytes = max(1024, min(int(max_event_bytes), MAX_FRAME_BYTES))
        self.initialized = False
        self.ready = False
        self.failed = False
        self.error: Optional[SdkAdapterError] = None
        # Readiness only needs a bounded diagnostic tail; retaining every
        # runtime message here made a long-lived runner grow without bound.
        self.events: deque[dict[str, Any]] = deque(maxlen=MAX_DIAGNOSTIC_EVENTS)
        self.events_seen = 0
        self.evidence: dict[str, Any] = {
            "initialized": False,
            "ready": False,
            "session_id_validated": bool(self.expected_session_id),
        }

    @property
    def initialization_seen(self) -> bool:
        return self.initialized

    @property
    def loader_error(self) -> Optional[SdkAdapterError]:
        return self.error

    @property
    def failure(self) -> Optional[SdkAdapterError]:
        return self.error

    def _fail(self, code: str, message: str) -> None:
        if self.error is None:
            self.error = SdkAdapterError(code, message)
        self.failed = True
        self.ready = False
        self.evidence["ready"] = False
        raise self.error

    @staticmethod
    def _is_error_result(event: Mapping[str, Any], data: Mapping[str, Any]) -> bool:
        typ = str(_get_ci(event, "type") or "").lower()
        subtype = str(_get_ci(event, "subtype") or _get_ci(data, "subtype") or "").lower()
        is_error = _get_ci(event, "is_error")
        if is_error is True:
            return True
        if subtype.startswith("error") or "error_during_execution" in subtype:
            return True
        if typ in {"error", "exception"}:
            return True
        errors = _get_ci(event, "errors") or _get_ci(data, "errors")
        return bool(errors) and typ in {"result", "system", "error", "exception"}

    @staticmethod
    def _error_message(event: Mapping[str, Any], data: Mapping[str, Any]) -> str:
        for key in ("error", "message", "result"):
            value = _get_ci(event, key)
            if value is None:
                value = _get_ci(data, key)
            if value:
                if isinstance(value, (list, tuple)):
                    return "; ".join(str(item) for item in value)
                return str(value)
        errors = _get_ci(event, "errors") or _get_ci(data, "errors")
        if errors:
            return "; ".join(str(item) for item in _as_tuple(errors))
        return "Claude loader returned an error result"

    @staticmethod
    def _account_email(account: Any) -> Optional[str]:
        if isinstance(account, Mapping):
            value = _first_nonempty(
                account.get("email"),
                account.get("account_email"),
                account.get("accountEmail"),
            )
            return None if value is None else str(value)
        # A plain string is accepted as a test/runtime shorthand, but a truthy
        # arbitrary object is never treated as account identity.
        if isinstance(account, str) and account.strip():
            return account
        return None

    def observe(self, event: Any) -> bool:
        """Consume one event and return whether readiness is now proven."""

        mapping = _event_to_mapping(event)
        self.events_seen = min(
            self.events_seen + 1,
            MAX_INITIALIZATION_EVENTS_SEEN,
        )
        self.events.append(mapping)
        data = _merged_event_data(mapping)

        if self._is_error_result(mapping, data) and not self.initialized:
            self._fail("loader-failed", self._error_message(mapping, data))
            return False
        if self._is_error_result(mapping, data) and self.initialized:
            self._fail("loader-failed", self._error_message(mapping, data))
            return False

        typ = str(_get_ci(mapping, "type") or "").lower()
        subtype = str(
            _get_ci(mapping, "subtype") or _get_ci(data, "subtype") or ""
        ).lower()
        is_init = subtype in {"init", "initialize", "initialized"}
        if typ in {"init", "initialize"}:
            is_init = True
        if not is_init:
            return self.ready

        if self.initialized:
            # ``get_server_info`` returns the control-plane init result during
            # connect, while some CLI versions also emit a session-start init
            # event on the continuous stream.  The latter may omit account or
            # permission fields; validate only identity/model when present.
            returned_session = _get_ci(data, "session_id", "sessionId")
            if returned_session is not None and self.expected_session_id and str(returned_session) != str(self.expected_session_id):
                self._fail("loader-failed", "initialization returned a different session UUID")
            returned_model = _get_ci(data, "model", "selected_model", "selectedModel")
            if returned_model is not None and self.expected_model:
                ids = _model_match_identifiers(returned_model)
                if ids and str(self.expected_model) not in ids:
                    self._fail("unsupported", "stream initialization model differs from stored launch fingerprint")
            return self.ready
        self.initialized = True
        self.evidence["initialized"] = True
        self.evidence["init_subtype"] = subtype or "init"

        account = _get_ci(data, "account")
        email = self._account_email(account)
        self.evidence["account_email"] = email
        if not self.expected_email:
            self._fail("account-mismatch", "initialization has no expected account email")
            return False
        if not email or email.casefold() != str(self.expected_email).casefold():
            self._fail(
                "account-mismatch",
                f"initialized account does not match expected {self.expected_email!r}",
            )
            return False

        permission = _get_ci(
            data,
            "current_permission_mode",
            "currentPermissionMode",
        )
        self.evidence["current_permission_mode"] = permission
        self.evidence["permission_mode"] = permission
        if not self.expected_permission_mode:
            self._fail("permission-mismatch", "initialization has no expected permission mode")
            return False
        if permission != self.expected_permission_mode:
            self._fail(
                "permission-mismatch",
                f"permission mode {permission!r} does not match expected {self.expected_permission_mode!r}",
            )
            return False

        session_state = _get_ci(data, "session_state", "sessionState")
        self.evidence["session_state"] = session_state
        if str(session_state).lower() != "idle":
            self._fail(
                "loader-failed",
                f"session is not held idle after initialization ({session_state!r})",
            )
            return False

        actual_worktree = _get_ci(
            data,
            "worktree",
            "workspace",
            "cwd",
            "working_directory",
            "workingDirectory",
        )
        self.evidence["worktree"] = actual_worktree
        if actual_worktree is not None and self.expected_worktree is not None:
            try:
                expected_path = Path(self.expected_worktree).resolve()
                actual_path = Path(str(actual_worktree)).resolve()
                same_worktree = expected_path == actual_path
            except (OSError, RuntimeError, ValueError):
                same_worktree = str(actual_worktree) == str(self.expected_worktree)
            if not same_worktree:
                self._fail("loader-failed", "initialized workspace differs from stored launch fingerprint")
                return False

        # An SDK init response may omit session_id.  If it does provide one,
        # compare it to the prevalidated exact UUID; never use it to discover a
        # replacement identity.
        returned_session = _get_ci(data, "session_id", "sessionId")
        self.evidence["returned_session_id"] = returned_session
        if returned_session is not None and self.expected_session_id:
            if str(returned_session) != str(self.expected_session_id):
                self._fail("loader-failed", "initialization returned a different session UUID")
                return False

        returned_model_raw = _get_ci(data, "model", "selected_model", "selectedModel")
        returned_model_ids = _model_match_identifiers(returned_model_raw)
        returned_model = returned_model_ids[0] if returned_model_ids else returned_model_raw
        self.evidence["returned_model"] = returned_model
        actual_models_raw = _get_ci(
            data,
            "models",
            "available_models",
            "availableModels",
            "supported_models",
            "supportedModels",
        )
        actual_model_ids = _model_match_identifiers(actual_models_raw)
        actual_model_records = _model_records(actual_models_raw)
        self.evidence["available_models"] = list(actual_model_ids)
        self.evidence["supported_models"] = list(
            actual_model_ids or self.supported_models
        )
        self.evidence["model_catalogue"] = [
            {
                key: record[key]
                for key in (
                    "value",
                    "resolvedModel",
                    "resolved_model",
                    "displayName",
                    "display_name",
                    "description",
                    "supportsEffort",
                    "supportedEffortLevels",
                )
                if key in record
            }
            for record in actual_model_records
        ]
        holders = _get_ci(data, "session_holders", "sessionHolders", "holders")
        if isinstance(holders, (list, tuple, set, frozenset)) and len(holders) != 1:
            self._fail(
                "ownership-conflict",
                "initialization reports ambiguous native session holders",
            )
            return False
        expected_model = self.expected_model
        if expected_model is None and returned_model is not None:
            expected_model = str(returned_model)
        fingerprint_resolved = _first_nonempty(
            _get_ci(self.fingerprint, "resolved_model", "resolvedModel"),
        )
        target_model_ids = {str(value) for value in (expected_model, fingerprint_resolved) if value}
        target_model_ids.update(str(value) for value in returned_model_ids)
        # The actual CLI model catalogue is independent evidence.  A caller's
        # supported-model list alone cannot prove that this runtime selected a
        # model it actually knows how to load.
        if actual_models_raw is not None:
            if not actual_model_ids:
                self._fail("unsupported", "initialization returned no usable model identifiers")
                return False
            if not target_model_ids.intersection(actual_model_ids):
                self._fail(
                    "unsupported",
                    "stored model fingerprint is not present in the initialized model catalogue",
                )
                return False
            if fingerprint_resolved and expected_model:
                matching_catalogue = [
                    record
                    for record in actual_model_records
                    if expected_model
                    in _model_match_identifiers(record)
                ]
                # ``matching_catalogue`` is deliberately a concrete list of
                # model records.  Do not reduce it to a truth value and later
                # iterate that boolean: the official init catalogue contains
                # metadata objects/dicts, while older fakes may contain plain
                # strings.  A stored requested→resolved pair is accepted only
                # when the same actual record proves that mapping.
                if not matching_catalogue:
                    self._fail(
                        "unsupported",
                        "stored model value is not present in the initialized model catalogue",
                    )
                    return False
                resolved_match = any(
                    isinstance(resolved_value, str)
                    and resolved_value.strip() == str(fingerprint_resolved)
                    for record in matching_catalogue
                    for resolved_value in (
                        _get_ci(record, "resolvedModel", "resolved_model"),
                    )
                )
                if not resolved_match:
                    self._fail(
                        "unsupported",
                        "initialized model value does not resolve to stored model fingerprint",
                    )
                    return False
        if self.supported_models:
            if expected_model is None:
                self._fail(
                    "unsupported",
                    "initialization omitted model and no stored model fingerprint is available",
                )
                return False
            if not target_model_ids.intersection(self.supported_models):
                self._fail(
                    "unsupported",
                    f"model {expected_model!r} is outside the supported model set",
                )
                return False
            if returned_model is not None and not set(returned_model_ids or (str(returned_model),)).intersection(self.supported_models):
                self._fail(
                    "unsupported",
                    f"initialized model {returned_model!r} is outside the supported model set",
                )
                return False
            if returned_model is not None and self.expected_model and not set(returned_model_ids or (str(returned_model),)).intersection({str(self.expected_model)}):
                self._fail("unsupported", "initialized model differs from stored launch fingerprint")
                return False
        elif expected_model is not None and returned_model is not None and str(returned_model) != str(expected_model):
            self._fail("unsupported", "initialized model differs from stored launch fingerprint")
            return False

        # Compare known fingerprint values where init actually provides a
        # corresponding field.  Missing init fields are allowed by the measured
        # SDK behavior; the stored fingerprint remains the authority for those
        # settings.
        for expected_key, init_keys, code in (
            ("account_email", ("account_email", "email"), "account-mismatch"),
            ("permission_mode", ("current_permission_mode", "currentPermissionMode"), "permission-mismatch"),
            ("model", ("model", "selected_model", "selectedModel"), "unsupported"),
            ("workspace", ("workspace", "cwd", "working_directory", "workingDirectory"), "loader-failed"),
        ):
            expected = _get_ci(self.fingerprint, expected_key)
            if expected is None:
                continue
            actual = _get_ci(data, *init_keys)
            if actual is None:
                continue
            if expected_key == "account_email":
                actual = self._account_email(actual) or actual
                if str(actual).casefold() != str(expected).casefold():
                    self._fail(code, f"fingerprint {expected_key} does not match initialization")
                    return False
            elif str(actual) != str(expected):
                self._fail(code, f"fingerprint {expected_key} does not match initialization")
                return False

        self.ready = True
        self.evidence["ready"] = True
        self.evidence["exact_identity"] = bool(self.expected_session_id)
        self.evidence["model"] = expected_model
        return True

    def finalize(self) -> dict[str, Any]:
        """Return evidence or raise the first fail-closed refusal."""

        if self.error is not None:
            raise self.error
        if not self.initialized:
            raise SdkAdapterError("loader-failed", "Claude initialization response was not received")
        if not self.ready:
            raise SdkAdapterError("loader-failed", "Claude initialization did not reach ready-held state")
        return self.snapshot()

    def validate(self) -> dict[str, Any]:
        return self.finalize()

    def require_ready(self) -> dict[str, Any]:
        return self.finalize()

    # Small verb aliases keep the tracker convenient for controller/fake
    # adapters without creating separate readiness paths.
    def feed(self, event: Any) -> bool:
        return self.observe(event)

    def ingest(self, event: Any) -> bool:
        return self.observe(event)

    def handle(self, event: Any) -> bool:
        return self.observe(event)

    def observe_json(self, raw: str | bytes | bytearray) -> bool:
        """Consume one bounded JSON event from a runner/test wire."""

        if isinstance(raw, str):
            encoded = raw.encode("utf-8", "replace")
        elif isinstance(raw, (bytes, bytearray)):
            encoded = bytes(raw)
        else:
            raise SdkAdapterError("invalid", "SDK event must be a JSON string or bytes")
        if len(encoded) > self.max_event_bytes:
            raise SdkAdapterError("invalid", "SDK event exceeds configured size bound")
        try:
            value = json.loads(encoded.decode("utf-8"))
        except (UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SdkAdapterError("invalid", "SDK event is malformed JSON") from exc
        if not isinstance(value, Mapping):
            raise SdkAdapterError("invalid", "SDK event must be a JSON object")
        return self.observe(value)

    def snapshot(self) -> dict[str, Any]:
        return {
            **dict(self.evidence),
            "error": None if self.error is None else self.error.as_dict(),
            "events_seen": self.events_seen,
            "diagnostic_tail": list(self.events),
        }


_NATIVE_TERMINAL_STATUSES = frozenset(
    {"completed", "stopped", "exact-resumed", "restarted", "restart-pending", "resume-pending"}
)
_NATIVE_ACTIVE_STATUSES = frozenset({"discovered", "admitted", "starting", "active", "stopping", "restarting"})
_NATIVE_ADMISSION_DEADLINE = 0.5
_NATIVE_POLICY_BODY_KEYS = frozenset(
    {
        "prompt",
        "message",
        "description",
        "instructions",
        "content",
        "command",
        "script",
        "input",
        "initialprompt",
        "systemprompt",
        "userprompt",
        "systemmessage",
        "credentials",
        "secret",
        "apikey",
        "accesstoken",
        "authtoken",
        "authorization",
        "password",
    }
)


def _native_event_data(event: Mapping[str, Any]) -> dict[str, Any]:
    return _merged_event_data(event)


def _native_event_kind(event: Mapping[str, Any]) -> str:
    """Normalize only the pinned native hook/task event names."""

    data = _native_event_data(event)
    raw = _first_nonempty(
        _get_ci(event, "hook_event_name", "hook_event", "event_type"),
        _get_ci(data, "hook_event_name", "hook_event", "event_type"),
        _get_ci(event, "subtype"),
        _get_ci(data, "subtype"),
        _get_ci(event, "type", "event"),
        _get_ci(data, "type", "event"),
    )
    if raw is None:
        return ""
    normalized = re.sub(r"[_\s-]+", "", str(raw).casefold())
    return {
        "pretooluse": "pretooluse",
        "posttooluse": "posttooluse",
        "posttoolusefailure": "posttoolusefailure",
        "subagentstart": "subagentstart",
        "subagentstop": "subagentstop",
        "taskstarted": "taskstarted",
        "taskprogress": "taskprogress",
        "tasknotification": "tasknotification",
        "taskupdated": "taskupdated",
        "progress": "taskprogress",
        "notification": "tasknotification",
        "taskstart": "taskstarted",
    }.get(normalized, "")


def _native_tool_input(event: Mapping[str, Any]) -> dict[str, Any]:
    value = _get_ci(_native_event_data(event), "tool_input", "toolInput", "input")
    return dict(value) if isinstance(value, Mapping) else {}


def _native_value(event: Mapping[str, Any], *names: str) -> Any:
    data = _native_event_data(event)
    return _first_nonempty(_get_ci(event, *names), _get_ci(data, *names))


def _native_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        folded = value.strip().casefold()
        if folded in {"true", "1", "yes", "on"}:
            return True
        if folded in {"false", "0", "no", "off"}:
            return False
    return None


def _native_policy_value(value: Any, depth: int = 0) -> Any:
    """Bound and redact an immutable policy without retaining prompt bodies."""

    if depth > 6:
        return "<depth-limit>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:512]
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        items = sorted(((str(key), item) for key, item in value.items()), key=lambda pair: pair[0].casefold())
        for key, item in items:
            if re.sub(r"[_\s-]+", "", key.casefold()) in _NATIVE_POLICY_BODY_KEYS:
                continue
            result[key] = _native_policy_value(item, depth + 1)
            if len(result) >= 64:
                break
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_native_policy_value(item, depth + 1) for item in list(value)[:64]]
    return repr(value)[:256]


def _native_canonical_json(value: Any) -> str:
    return json.dumps(
        _native_policy_value(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def _native_digest(value: Any) -> str:
    return hashlib.sha256(_native_canonical_json(value).encode("utf-8")).hexdigest()


def _native_full_digest(value: Any) -> str:
    """Hash complete strict JSON, refusing lossy conversion or excessive size."""

    nodes = 0
    ancestors: set[int] = set()

    def validate(item: Any, depth: int = 0) -> None:
        nonlocal nodes
        nodes += 1
        if depth > MAX_NATIVE_DEFINITION_DEPTH or nodes > MAX_NATIVE_DEFINITION_NODES:
            raise SdkAdapterError("invalid", "native definition exceeds structural bounds")
        kind = type(item)
        if item is None or kind in (bool, int):
            return
        if kind is float:
            if not math.isfinite(item):
                raise SdkAdapterError("invalid", "native definition contains a nonfinite number")
            return
        if kind is str:
            if len(item) > MAX_NATIVE_DEFINITION_BYTES:
                raise SdkAdapterError("invalid", "native definition exceeds JSON size bound")
            return
        if kind not in (dict, list):
            raise SdkAdapterError("invalid", "native definition contains a non-JSON value")
        if id(item) in ancestors:
            raise SdkAdapterError("invalid", "native definition contains a cycle")
        if len(item) > MAX_NATIVE_DEFINITION_NODES:
            raise SdkAdapterError("invalid", "native definition exceeds structural bounds")
        ancestors.add(id(item))
        try:
            if kind is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise SdkAdapterError("invalid", "native definition keys must be JSON strings")
                    validate(key, depth + 1)
                    validate(child, depth + 1)
            else:
                for child in item:
                    validate(child, depth + 1)
        finally:
            ancestors.remove(id(item))

    validate(value)
    digest = hashlib.sha256()
    size = 0
    encoder = json.JSONEncoder(ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    try:
        for chunk in encoder.iterencode(value):
            encoded = chunk.encode("ascii")
            size += len(encoded)
            if size > MAX_NATIVE_DEFINITION_BYTES:
                raise SdkAdapterError("invalid", "native definition exceeds JSON size bound")
            digest.update(encoded)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SdkAdapterError("invalid", "native definition is not strict JSON") from exc
    return digest.hexdigest()


def native_definition_facts(definitions: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the shared, body-free trusted-definition projection.

    Input is a name-to-definition mapping (empty is allowed), at most 256
    definitions and 1 MiB of canonical JSON across the mapping. Nested values
    must be JSON dict/list/scalars, finite, acyclic, depth <= 32 and <= 65536
    nodes. Names are nonempty strings of at most 256 characters. Invalid
    input raises SdkAdapterError(code="invalid"); no repr/default coercion.

    Each result has name, digest, tools, model, effort, permissionMode,
    permissions, writable_paths. The SHA-256 hashes the COMPLETE individual
    definition as sorted, compact, ASCII-escaped JSON, before redaction.
    Tools must be a nonempty list of at most 128 strings, each 1..128 characters;
    model/effort/permission strings retain 512 characters. Nested policy
    uses the SDK's recursive body/secret redaction, depth 6, 64 entries per
    container and 512 characters per string. Returned facts are detached
    from input. They are evidence, not SDK launch definitions or authority.
    """

    return _native_definition_facts(definitions, strict_tools=True)


def _native_definition_facts(
    definitions: Mapping[str, Any], *, strict_tools: bool,
) -> dict[str, dict[str, Any]]:
    """One projection; standalone ledger evidence may omit a tool policy."""
    if not isinstance(definitions, Mapping) or len(definitions) > MAX_NATIVE_CHILD_RECORDS:
        raise SdkAdapterError("invalid", "trusted native definitions must be a bounded mapping")
    definitions = dict(definitions)
    _native_full_digest(definitions)  # Validate the complete aggregate before projecting.
    result: dict[str, dict[str, Any]] = {}
    for name, source in definitions.items():
        if not name.strip() or len(name) > 256 or type(source) is not dict:
            raise SdkAdapterError("invalid", "native agent definitions require bounded names and JSON objects")
        tools = _get_ci(source, "tools", "allowed_tools", "allowedTools")
        valid_tools = (
            type(tools) is list and len(tools) <= 128
            and all(type(tool) is str and 1 <= len(tool) <= 128 for tool in tools)
        )
        if (tools is not None and not valid_tools) or (strict_tools and not tools):
            raise SdkAdapterError("invalid", "native definition requires explicit bounded tools")
        # Tool identities are never shortened, filtered, or stringified.
        safe_tools = list(tools) if tools is not None else []
        model = _first_nonempty(_get_ci(source, "model"), _get_ci(source, "model_id", "modelId"))
        effort = _get_ci(source, "effort")
        permission = _first_nonempty(_get_ci(source, "permissionMode"), _get_ci(source, "permission_mode"))
        if (model is not None and type(model) is not str
                or permission is not None and type(permission) is not str
                or effort is not None and type(effort) not in (str, int)):
            raise SdkAdapterError("invalid", "native definition metadata has an invalid type")
        result[name] = {
            "name": name,
            "digest": _native_full_digest(source),
            "tools": safe_tools,
            "model": _native_policy_value(model),
            "effort": _native_policy_value(effort),
            "permissionMode": _native_policy_value(permission),
            "permissions": _native_policy_value(_get_ci(source, "permissions", "permission_policy", "permissionPolicy")),
            "writable_paths": _native_policy_value(_get_ci(source, "writable_paths", "writablePaths", "write_paths", "writePaths")),
        }
    return result


def _native_policy_lookup(policy: Mapping[str, Any], *names: str) -> Any:
    value = _get_ci(policy, *names)
    if value is not None:
        return value
    nested = _get_ci(policy, "policy")
    return _get_ci(nested, *names) if isinstance(nested, Mapping) else None


def _native_policy_projection(event: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Extract explicit child policy fields; prompts and descriptions are not policy."""

    tool_input = _native_tool_input(event)
    if not tool_input:
        return {}, False
    policy: dict[str, Any] = {}
    explicit = False
    supplied_policy = _get_ci(tool_input, "policy", "permission_policy")
    if isinstance(supplied_policy, Mapping) and supplied_policy:
        policy["policy"] = _native_policy_value(supplied_policy)
        explicit = True
    definition = _get_ci(
        tool_input,
        "custom_definition",
        "customDefinition",
        "agent_definition",
        "agentDefinition",
    )
    if definition is not None:
        policy["custom_definition"] = {
            "digest": _native_digest(definition),
            "reference": _native_policy_value(definition),
        }
        explicit = True
    for key in (
        "agent_type",
        "agentType",
        "subagent_type",
        "subagentType",
        "model",
        "effort",
        "tools",
        "allowed_tools",
        "allowedTools",
        "permission_mode",
        "permissionMode",
        "permissions",
        "read_only",
        "readOnly",
        "workspace",
        "worktree",
        "cwd",
        "run_in_background",
        "runInBackground",
        "lineage_claim",
        "claim_ref",
    ):
        value = _get_ci(tool_input, key)
        if value is not None:
            canonical_key = re.sub(r"([A-Z])", lambda match: "_" + match.group(1).lower(), key).lstrip("_")
            policy[canonical_key] = _native_policy_value(value)
            if key not in {"agent_type", "agentType", "subagent_type", "subagentType", "model", "effort"}:
                explicit = True
    return policy, explicit


class NativeLineageLedger:
    """Bounded native Agent/Task lifecycle and admission ledger.

    This is a coordinator-local projection.  Child records intentionally do
    not contain a child session UUID, process group, or independent SDK
    connection: native children share the containing coordinator boundary.
    """

    def __init__(
        self,
        coordinator_session_id: str,
        *,
        trusted_definitions: Mapping[str, Any] | None,
        parent_read_only: bool = False,
        lineage_context: Mapping[str, Any] | None = None,
        lineage_claim: Any = None,
        persist_admission: Callable[[Mapping[str, Any]], Any] | None = None,
        coordinator_enabled: bool = False,
    ) -> None:
        self.coordinator_session_id = None if coordinator_session_id is None else str(coordinator_session_id)
        self.parent_read_only = bool(parent_read_only)
        self.lineage_context = (
            _native_policy_value(lineage_context)
            if isinstance(lineage_context, Mapping)
            else None
        )
        self.lineage_claim = _native_policy_value(lineage_claim) if lineage_claim is not None else None
        # Keep an exact, detached claim only for the immutable reservation
        # digest.  The redacted projection above remains the public evidence
        # source and never carries claim bodies into a wire response.
        self._lineage_claim_exact = copy.deepcopy(lineage_claim) if lineage_claim is not None else None
        self.persist_admission = persist_admission
        # A coordinator-enabled runner has a stricter invocation/fence
        # lifecycle than the legacy ledger-only seam.  Keep that mode opt-in
        # so native task-stop/admission compatibility tests retain their
        # existing rollover behavior.
        self.coordinator_enabled = bool(coordinator_enabled)
        # Definitions are controller-owned configuration.  Keep a private
        # deep copy for the full-content digest so a caller mutation cannot
        # broaden an already admitted child.  Only bounded metadata is ever
        # emitted in a snapshot.
        definitions = {} if trusted_definitions is None else trusted_definitions
        self._definition_facts = _native_definition_facts(definitions, strict_tools=False)
        self.trusted_definitions = copy.deepcopy(dict(definitions))
        self.watermark = 0
        self.runtime_cursor: Optional[int] = None
        self.current_invocation: Optional[str] = None
        self.current_message_id: Optional[str] = None
        self.current_invocation_watermark = 0
        self.released = False
        self.startup_violation = False
        self.error: Optional[SdkAdapterError] = None
        self.overflow = False
        self.children: dict[str, dict[str, Any]] = {}
        self.child_history: list[dict[str, Any]] = []
        self.admissions: list[dict[str, Any]] = []
        self.pending_admissions: dict[str, dict[str, Any]] = {}
        self.pending_tasks: dict[str, dict[str, Any]] = {}
        self.lifecycle: deque[dict[str, Any]] = deque(maxlen=MAX_NATIVE_LIFECYCLE_EVENTS)
        self.uncertainties: list[dict[str, Any]] = []
        self._seen_events: dict[tuple[Any, ...], str] = {}
        self._retired_child_paths: dict[str, set[str]] = {}
        self._native_stop_states: dict[str, dict[str, Any]] = {}
        self._native_stop_targets: dict[tuple[Any, ...], str] = {}
        self._native_stop_fenced = False
        self._coordinator_interrupt_fenced = False
        self._coordinator_interrupt_states: dict[str, dict[str, Any]] = {}
        self._coordinator_interrupt_targets: dict[tuple[Any, ...], str] = {}
        self._coordinator_fact_events: deque[dict[str, Any]] = deque(
            maxlen=MAX_NATIVE_LIFECYCLE_EVENTS
        )
        self._coordinator_fact_overflow = False
        self._parent_active = False
        self._parent_drained = True
        self._parent_state_observed = False
        self._parent_result: Optional[dict[str, Any]] = None
        self._invocation_reservation: Optional[dict[str, Any]] = None
        self._reservation_sealed = False
        # Never evict consumed IDs: eviction would let a delayed controller
        # acknowledgement replay an old reservation after enough rollovers.
        self._consumed_reservation_ids: set[str] = set()

    @staticmethod
    def _definition_fact(name: str, definition: Any) -> dict[str, Any]:
        """Compatibility wrapper; the public projection is the sole source."""
        return _native_definition_facts({name: definition}, strict_tools=False)[name]

    def _definition_for(self, name: Any) -> Optional[dict[str, Any]]:
        if name is None:
            return None
        return self._definition_facts.get(str(name))

    def _lineage_identity(self) -> dict[str, Any]:
        """Return the current durable lineage identity source.

        A read-only coordinator still has an owner/lineage/process identity;
        it cannot borrow that identity from an optional writable claim.  A
        writer may use its explicit claim when no separate context was given.
        The returned values are reloaded after every asynchronous admission
        acknowledgement so a context replacement is a fence change.
        """

        source = self.lineage_context
        if source is None and not self.parent_read_only:
            source = self.lineage_claim
        if not isinstance(source, Mapping):
            return {}
        return {
            "owner_generation": source.get("owner_generation"),
            "lineage_id": source.get("lineage_id"),
            "runner_incarnation": source.get("runner_incarnation"),
        }

    def _validated_lineage_identity(self) -> tuple[Optional[dict[str, Any]], Optional[SdkAdapterError]]:
        identity = self._lineage_identity()
        owner_generation = identity.get("owner_generation")
        lineage_id = identity.get("lineage_id")
        runner_incarnation = identity.get("runner_incarnation")
        if (
            type(owner_generation) is not int
            or owner_generation <= 0
            or not isinstance(lineage_id, str)
            or not lineage_id.strip()
            or not isinstance(runner_incarnation, str)
            or not runner_incarnation.strip()
        ):
            return None, self._fail(
                "unsupported",
                "native child admission lacks a complete durable lineage identity",
            )
        return identity, None

    def _lineage_generation(self) -> int:
        """Return the trusted lineage generation carried by startup context."""

        source = self.lineage_context
        if source is None and not self.parent_read_only:
            source = self.lineage_claim
        value = _get_ci(source, "lineage_generation", "lineageGeneration") if isinstance(source, Mapping) else None
        if type(value) is int and value > 0:
            return value
        # Older startup fingerprints carry the generation only in the durable
        # claim object.  A single initial lineage is the only safe fallback;
        # callers that need a later generation must include it explicitly.
        return 1

    def _child_is_read_only(self, definition: Mapping[str, Any]) -> bool:
        tools = definition.get("tools")
        if not isinstance(tools, list) or not tools:
            return False
        return {str(value).casefold() for value in tools}.issubset(_READ_ONLY_BUILTIN_TOOLS)

    @property
    def quiescent(self) -> bool:
        return bool(
            self.error is None
            and not self.overflow
            and not self.pending_admissions
            and not self.pending_tasks
            and not self.uncertainties
            and all(
                record.get("status") in _NATIVE_TERMINAL_STATUSES
                and not record.get("tool_events", {}).get("active")
                and not record.get("tool_events", {}).get("uncertain")
                and bool(record.get("task_terminal", record.get("task_id") is None))
                for record in self.children.values()
            )
        )

    @property
    def ready_for_hold(self) -> bool:
        return bool(
            self.error is None
            and not self.startup_violation
            and not self.pending_admissions
            and not self.pending_tasks
            and not self.uncertainties
            and not self.overflow
            and all(
                record.get("status") in _NATIVE_TERMINAL_STATUSES
                and not record.get("tool_events", {}).get("active")
                and not record.get("tool_events", {}).get("uncertain")
                and bool(record.get("task_terminal", record.get("task_id") is None))
                for record in self.children.values()
            )
        )

    def _redact_event(self, kind: str, event: Mapping[str, Any], watermark: int) -> dict[str, Any]:
        item: dict[str, Any] = {"kind": kind, "watermark": watermark}
        for output, names in (
            ("agent_id", ("agent_id", "agentId")),
            ("task_id", ("task_id", "taskId")),
            ("tool_use_id", ("tool_use_id", "toolUseId")),
            ("event_uuid", ("uuid", "event_uuid", "eventUuid")),
            ("status", ("status",)),
            ("type", ("agent_type", "agentType", "task_type", "taskType")),
        ):
            value = _native_value(event, *names)
            if value is not None:
                item[output] = str(value)[:256]
        return item

    def _record_uncertainty(self, reason: str, event: Mapping[str, Any], *, code: str = "uncertain-effect") -> SdkAdapterError:
        item = {"reason": reason, **self._redact_event(_native_event_kind(event), event, self.watermark)}
        if len(self.uncertainties) >= MAX_NATIVE_UNCERTAINTIES:
            self.overflow = True
        else:
            self.uncertainties.append(item)
        if self.error is None:
            self.error = SdkAdapterError(code, reason)
        return self.error

    def _fail(self, code: str, message: str, event: Mapping[str, Any] | None = None) -> SdkAdapterError:
        if event is not None:
            self._record_uncertainty(message, event, code=code)
        elif self.error is None:
            self.error = SdkAdapterError(code, message)
        return self.error or SdkAdapterError(code, message)

    def _mark_event(self, kind: str, event: Mapping[str, Any]) -> Any:
        source = str(event.get("_adapter_event_source", "direct"))
        event_uuid = _native_value(event, "uuid", "event_uuid", "eventUuid")
        event_invocation = self._event_invocation(event)
        effective_invocation = event_invocation or self.current_invocation
        invocation_epoch = (
            self.current_invocation_watermark
            if effective_invocation is not None and effective_invocation == self.current_invocation
            else None
        )
        key = (
            kind,
            str(event_uuid) if event_uuid is not None else None,
            _native_value(event, "agent_id", "agentId"),
            _native_value(event, "task_id", "taskId"),
            _native_value(event, "tool_use_id", "toolUseId"),
            effective_invocation,
            invocation_epoch,
            _native_value(event, "prompt_id", "promptId"),
            _native_value(event, "agent_transcript_path", "agentTranscriptPath"),
            _native_value(event, "status"),
        )
        previous_source = self._seen_events.get(key)
        if previous_source is not None:
            if previous_source != source:
                return _NATIVE_CROSS_SOURCE_DUPLICATE
            return self._fail("uncertain-effect", f"duplicate native {kind} event", event)
        if len(self._seen_events) >= MAX_NATIVE_LIFECYCLE_EVENTS:
            self.overflow = True
            return self._fail("uncertain-effect", "native lifecycle event ledger is full", event)
        self._seen_events[key] = source
        self.watermark += 1
        cursor = _native_value(event, "sequence", "event_cursor", "cursor", "watermark")
        if isinstance(cursor, int) and not isinstance(cursor, bool):
            if self.runtime_cursor is not None and cursor < self.runtime_cursor:
                return self._fail("stale-generation", "native event cursor moved backwards", event)
            self.runtime_cursor = cursor
            self.watermark = max(self.watermark, cursor)
        self.lifecycle.append(self._redact_event(kind, event, self.watermark))
        return None

    def _check_session(self, event: Mapping[str, Any], *, required: bool) -> Optional[SdkAdapterError]:
        session_id = _native_value(event, "session_id", "sessionId")
        if required and session_id is None:
            return self._fail("ownership-conflict", "native lifecycle event omitted its containing session", event)
        if (
            session_id is not None
            and self.coordinator_session_id is not None
            and str(session_id) != self.coordinator_session_id
        ):
            return self._fail("ownership-conflict", "native lifecycle event belongs to another session", event)
        return None

    def begin_invocation(
        self,
        invocation_id: Any,
        message_id: Any = None,
        *,
        reservation_binding: Mapping[str, Any] | None = None,
    ) -> Optional[SdkAdapterError]:
        if invocation_id is None or not str(invocation_id).strip():
            return self._fail("invalid", "native parent invocation ID is required")
        if self._native_stop_fenced:
            return SdkAdapterError("busy", "native stop fence blocks a new parent invocation")
        if self._coordinator_interrupt_fenced:
            return SdkAdapterError(
                "busy", "coordinator interrupt fence blocks a new parent invocation"
            )
        if reservation_binding is not None and not self.coordinator_enabled:
            return SdkAdapterError(
                "unsupported", "native reservation requires coordinator lineage mode"
            )
        invocation = str(invocation_id).strip()
        if reservation_binding is not None and (
            self.current_invocation is None or invocation == self.current_invocation
        ):
            return SdkAdapterError(
                "stale-generation", "native reservation cannot authorize the current invocation"
            )
        if (
            self.coordinator_enabled
            and self.current_invocation is not None
            and invocation != self.current_invocation
        ):
            if reservation_binding is None:
                return SdkAdapterError(
                    "busy",
                    "native coordinator invocation is already bound; reconcile before rollover",
                )
            if self._invocation_reservation is None:
                return SdkAdapterError(
                    "stale-generation", "native invocation reservation is not outstanding"
                )
            cached_reservation = self._invocation_reservation
            cached_request = {
                key: cached_reservation[key] for key in _NATIVE_INVOCATION_BINDING_FIELDS
            }
            try:
                candidate_reservation = _native_invocation_response(
                    reservation_binding, cached_request
                )
            except SdkAdapterError as exc:
                return exc
            if any(
                candidate_reservation.get(key) != cached_reservation.get(key)
                for key in _NATIVE_INVOCATION_RESPONSE_FIELDS
            ):
                return SdkAdapterError(
                    "stale-generation", "native rollover binding does not match the sealed reservation"
                )
            if (
                candidate_reservation["next_invocation_id"] != invocation
                or candidate_reservation["next_mailbox_id"]
                != (None if message_id is None else str(message_id))
            ):
                return SdkAdapterError(
                    "stale-generation", "native rollover binding does not target the new invocation"
                )
            if candidate_reservation["next_watermark"] <= self.watermark:
                return SdkAdapterError(
                    "stale-generation", "native rollover next watermark is not newer"
                )
            consume_error = self.consume_invocation_reservation(reservation_binding)
            if consume_error is not None:
                return consume_error
        self.current_invocation = invocation
        self.current_message_id = None if message_id is None else str(message_id)
        self.current_invocation_watermark = self.watermark + 1
        self.watermark += 1
        # Parent activity belongs to this exact mailbox invocation.  A state
        # observed for the previous message cannot be reused for a new seal.
        self._parent_state_observed = False
        # Beginning an invocation does not open the held coordinator.  Only
        # the explicit mark_released transition permits model/native work.
        self._parent_active = False
        self._parent_drained = True
        self._parent_result = None
        return None

    def _event_invocation(self, event: Mapping[str, Any]) -> Optional[str]:
        value = _native_value(
            event,
            "invocation_id",
            "invocationId",
            "parent_invocation_id",
            "parentInvocationId",
        )
        return None if value is None else str(value)

    def _context_error(self, record: Mapping[str, Any], event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        invocation = self._event_invocation(event)
        expected = record.get("parent_links", {}).get("invocation_id")
        if invocation is not None and (expected is None or invocation != expected):
            return self._fail("stale-generation", "native child event has another parent invocation", event)
        if invocation is None and self.current_invocation is not None and expected != self.current_invocation:
            return self._fail("stale-generation", "native child event omitted its current parent invocation", event)
        started = int(record.get("lineage_incarnation", {}).get("start_watermark", 0))
        if self.watermark <= started:
            return self._fail("stale-generation", "native child terminal event predates its start", event)
        correlated = invocation is not None and expected is not None and invocation == expected
        current_incarnation = int(record.get("lineage_incarnation", {}).get("number", 1))
        event_task_id = _native_value(event, "task_id", "taskId")
        expected_task_id = record.get("task_id")
        if event_task_id is not None:
            if expected_task_id is None or str(event_task_id) != str(expected_task_id):
                return self._fail("ownership-conflict", "native child event changed its current task identity", event)
            # local_agent reuses task_id == agent_id across incarnations.  A
            # bare task ID therefore cannot authenticate an update for a
            # reused child; require a launch/prompt/parent fence as well.
            if current_incarnation == 1:
                correlated = True
        event_tool_id = _native_value(event, "tool_use_id", "toolUseId")
        expected_tool_id = record.get("tool_use_id")
        if event_tool_id is not None:
            if expected_tool_id is None or str(event_tool_id) != str(expected_tool_id):
                return self._fail("ownership-conflict", "native child event changed its launch tool identity", event)
            correlated = True
        event_prompt_id = _native_value(event, "prompt_id", "promptId")
        expected_prompt_id = record.get("parent_links", {}).get("prompt_id")
        if event_prompt_id is not None:
            if expected_prompt_id is not None and str(event_prompt_id) != str(expected_prompt_id):
                return self._fail("stale-generation", "native child event changed its prompt correlation", event)
            if expected_prompt_id is not None and str(expected_prompt_id).strip():
                correlated = True
        for name in ("parent_agent_id", "parentAgentId", "parent_task_id", "parentTaskId", "parent_tool_use_id", "parentToolUseId"):
            actual = _native_value(event, name)
            if actual is None:
                continue
            expected_value = record.get("parent_links", {}).get(
                {
                    "parentAgentId": "parent_agent_id",
                    "parentTaskId": "parent_task_id",
                    "parentToolUseId": "parent_tool_use_id",
                }.get(name, name)
            )
            if expected_value is not None and str(actual) != str(expected_value):
                return self._fail("ownership-conflict", "native child parent linkage changed", event)
            if current_incarnation == 1 and expected_value is not None and str(expected_value).strip():
                correlated = True
        # SubagentStop supplies the current child transcript path.  It is a
        # runtime correlation fact for an initial incarnation.  A stable path
        # is not enough to identify a reused child run.
        if (
            current_incarnation == 1
            and _native_value(event, "agent_transcript_path", "agentTranscriptPath") is not None
        ):
            correlated = True
        if not correlated:
            return self._fail(
                "stale-generation",
                "native child event lacks a current launch, prompt, task, parent, or transcript correlation",
                event,
            )
        return None

    async def admit_agent(self, event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        """Record and validate a PreToolUse Agent/Task admission before execution."""

        if self._reservation_sealed:
            return SdkAdapterError(
                "busy", "native invocation reservation seals new child admissions"
            )
        if self._native_stop_fenced:
            # Keep the stop path available while the affected lineage is
            # fenced.  This refusal deliberately does not poison the ledger;
            # a stop acknowledgement or terminal fact may still arrive.
            return SdkAdapterError("busy", "native stop fence blocks new child admission")
        if self._coordinator_interrupt_fenced:
            return SdkAdapterError(
                "busy", "coordinator interrupt fence blocks new child admission"
            )
        kind = _native_event_kind(event)
        if kind != "pretooluse":
            return self._fail("invalid", "native admission requires PreToolUse", event)
        name = _native_value(event, "tool_name", "toolName", "name")
        tool_name = "" if name is None else str(name).casefold()
        if tool_name not in _NATIVE_CHILD_TOOL_NAMES:
            return None
        tool_id = _native_value(event, "tool_use_id", "toolUseId", "id")
        if tool_id is None or not str(tool_id).strip():
            return self._fail("uncertain-effect", "native Agent/Task admission has no tool-use ID", event)
        event = dict(event)
        event.setdefault("_adapter_event_source", "hook")
        seen_error = self._mark_event(kind, event)
        if seen_error is _NATIVE_CROSS_SOURCE_DUPLICATE:
            return None
        if seen_error is not None:
            return seen_error
        if self.released is False:
            self.startup_violation = True
            return self._fail("startup-orphan", "native child admission occurred before coordinator release", event)
        invocation = self._event_invocation(event) or self.current_invocation
        if invocation is None:
            return self._fail("unsupported", "native child admission is not bound to a parent invocation", event)
        if self.current_invocation is None or invocation != self.current_invocation:
            return self._fail("stale-generation", "native child admission has another parent invocation", event)
        # The durable callback is an asynchronous fence boundary.  Capture
        # the exact parent generation before yielding and recheck it after
        # the supervisor acknowledges the admission; a late ack must never
        # authorize a child in a newer invocation.
        identity, identity_error = self._validated_lineage_identity()
        if identity_error is not None:
            return identity_error
        assert identity is not None
        admission_fence = (
            self.released,
            self.current_invocation,
            self.current_invocation_watermark,
            identity["owner_generation"],
            identity["lineage_id"],
            identity["runner_incarnation"],
        )
        # The tool input is a request for a definition key, not policy
        # authority.  Model-supplied tools, permissions, prompts, and model
        # claims are deliberately ignored here.
        tool_input = _native_tool_input(event)
        requested_type = _get_ci(tool_input, "subagent_type", "subagentType", "agent_type", "agentType")
        definition = self._definition_for(requested_type)
        if definition is None:
            return self._fail("unsupported", "native Agent/Task admission references an unknown child definition", event)
        trusted_tools = definition.get("tools")
        if not isinstance(trusted_tools, list) or not trusted_tools:
            return self._fail("unsupported", "trusted native child definition has no effective tool policy", event)
        if self.parent_read_only and not self._child_is_read_only(definition):
            claim = self.lineage_claim
            if claim is None:
                return self._fail("unsupported", "writable child lacks the coordinator lineage claim", event)
        parent_agent = _native_value(event, "agent_id", "agentId")
        if parent_agent is not None:
            parent_record = self.children.get(str(parent_agent))
            if parent_record is None:
                return self._fail(
                    "ownership-conflict",
                    "native child admission has an unknown containing agent",
                    event,
                )
            if parent_record.get("status") not in _NATIVE_ACTIVE_STATUSES:
                return self._fail(
                    "stale-generation",
                    "native child admission parent is not a current active child",
                    event,
                )
        tool_key = str(tool_id)
        if tool_key in self.pending_admissions:
            return self._fail("uncertain-effect", "native Agent/Task admission was duplicated", event)
        if len(self.pending_admissions) >= MAX_NATIVE_CHILD_RECORDS:
            self.overflow = True
            return self._fail("uncertain-effect", "native child admission ledger is full", event)
        admission_id = str(_uuid.uuid4())
        pending = {
            "admission_id": admission_id,
            "tool_use_id": tool_key,
            "tool_name": str(name),
            "agent_type": str(requested_type),
            "parent_agent_id": None if parent_agent is None else str(parent_agent),
            "parent_task_id": None,
            "parent_tool_use_id": None,
            "invocation_id": invocation,
            "prompt_id": _native_value(event, "prompt_id", "promptId"),
            "admission_watermark": self.watermark,
            "custom_definition": copy.deepcopy(definition),
            "policy": {
                "tools": list(trusted_tools),
                "model": definition.get("model"),
                "effort": definition.get("effort"),
                "permissionMode": definition.get("permissionMode"),
                "writable_paths": definition.get("writable_paths"),
                "claim_ref": self.lineage_claim,
            },
            "policy_digest": definition.get("digest"),
            "launch_completed": False,
            "background_requested": bool(_native_bool(_get_ci(tool_input, "run_in_background", "runInBackground"))),
        }
        self.pending_admissions[tool_key] = pending
        admission = {
            "admission_id": admission_id,
            "tool_use_id": tool_key,
            "agent_type": str(requested_type),
            "invocation_id": invocation,
            "parent": {
                "session_id": self.coordinator_session_id,
                "agent_id": None if parent_agent is None else str(parent_agent),
                "invocation_id": invocation,
                "prompt_id": _native_value(event, "prompt_id", "promptId"),
            },
            "custom_definition": copy.deepcopy(definition),
            "definition_digest": definition.get("digest"),
            "trusted_definition_digest": definition.get("digest"),
            "watermark": self.watermark,
            "owner_generation": identity["owner_generation"],
            "lineage_id": identity["lineage_id"],
            "runner_incarnation": identity["runner_incarnation"],
            "launch_completed": False,
        }
        if self.persist_admission is None:
            self.pending_admissions.pop(tool_key, None)
            return self._fail("unsupported", "native child admission has no durable pre-allow recorder", event)
        try:
            async def await_admission_ack() -> Any:
                return await _maybe_await(self.persist_admission(dict(admission)))

            acknowledgement = await _await_bounded(
                await_admission_ack(),
                _NATIVE_ADMISSION_DEADLINE,
            )
        except asyncio.TimeoutError:
            self.pending_admissions.pop(tool_key, None)
            return self._fail("loader-failed", "durable native child admission exceeded its deadline", event)
        except asyncio.CancelledError:
            self.pending_admissions.pop(tool_key, None)
            raise
        except Exception as exc:  # noqa: BLE001
            self.pending_admissions.pop(tool_key, None)
            return self._fail("loader-failed", f"durable native child admission failed: {exc}", event)
        acknowledged = (
            isinstance(acknowledgement, Mapping)
            and acknowledgement.get("accepted") is True
            and all(
                key in acknowledgement
                and type(acknowledgement.get(key)) is type(admission.get(key))
                and acknowledgement.get(key) == admission.get(key)
                for key in (
                    "admission_id",
                    "owner_generation",
                    "lineage_id",
                    "runner_incarnation",
                    "invocation_id",
                    "tool_use_id",
                    "trusted_definition_digest",
                )
            )
        )
        if not acknowledged:
            self.pending_admissions.pop(tool_key, None)
            return self._fail("unsupported", "durable native child admission acknowledgement was invalid", event)
        if len(self.admissions) >= MAX_NATIVE_CHILD_HISTORY:
            self.overflow = True
            self.pending_admissions.pop(tool_key, None)
            return self._fail("uncertain-effect", "native admission history is full", event)
        # Record the acknowledged admission before checking the fence again.
        # If a concurrent fence crossed while the supervisor was persisting,
        # this durable mirror keeps the pre-fence admission in the sealed
        # ledger instead of silently losing the child join.
        self.admissions.append(dict(admission))
        current_identity, current_identity_error = self._validated_lineage_identity()
        if current_identity_error is not None:
            self.pending_admissions.pop(tool_key, None)
            return current_identity_error
        assert current_identity is not None
        current_fence = (
            self.released,
            self.current_invocation,
            self.current_invocation_watermark,
            current_identity["owner_generation"],
            current_identity["lineage_id"],
            current_identity["runner_incarnation"],
        )
        if current_fence != admission_fence:
            self.pending_admissions.pop(tool_key, None)
            return self._fail("stale-generation", "native child admission crossed a release or invocation boundary", event)
        return None

    def _pending_for_start(self, event: Mapping[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[SdkAdapterError]]:
        tool_id = _native_value(event, "tool_use_id", "toolUseId", "parent_tool_use_id", "parentToolUseId")
        if tool_id is not None:
            admission = self.pending_admissions.get(str(tool_id))
            if admission is not None:
                return admission, None
        parent_agent_id = _native_value(event, "parent_agent_id", "parentAgentId")
        if parent_agent_id is not None:
            matching = [
                admission
                for admission in self.pending_admissions.values()
                if admission.get("parent_agent_id") is not None
                and str(admission["parent_agent_id"]) == str(parent_agent_id)
            ]
            if len(matching) == 1:
                return matching[0], None
            if len(matching) > 1:
                return None, None
        invocation = self._event_invocation(event) or self.current_invocation
        matching = [
            admission
            for admission in self.pending_admissions.values()
            if admission.get("invocation_id") == invocation
        ]
        if len(matching) == 1:
            return matching[0], None
        if len(matching) > 1:
            return None, None
        return None, None

    def _hold_event(
        self,
        reason: str,
        event: Mapping[str, Any],
        record: dict[str, Any] | None = None,
    ) -> None:
        item = {"reason": reason, **self._redact_event(_native_event_kind(event), event, self.watermark)}
        if len(self.uncertainties) >= MAX_NATIVE_UNCERTAINTIES:
            self.overflow = True
        else:
            self.uncertainties.append(item)
        if record is not None:
            record["status"] = "unresolved"
            record["uncertain"] = True
            events = record.setdefault("tool_events", {}).setdefault("uncertain", [])
            if len(events) < MAX_NATIVE_PROGRESS_EVENTS:
                events.append(item)

    def _unresolved_child(self, event: Mapping[str, Any], reason: str) -> Optional[dict[str, Any]]:
        agent_id = _native_value(event, "agent_id", "agentId")
        if agent_id is None or not str(agent_id).strip():
            self._hold_event(reason, event)
            return None
        key = str(agent_id)
        existing = self.children.get(key)
        if existing is not None:
            self._hold_event(reason, event, existing)
            return existing
        if len(self.children) >= MAX_NATIVE_CHILD_RECORDS:
            self.overflow = True
            self._hold_event("native child ledger is full", event)
            return None
        record: dict[str, Any] = {
            "agent_id": key,
            "task_id": None,
            "type": _native_value(event, "agent_type", "agentType"),
            "tool_use_id": None,
            "parent": {
                "session_id": self.coordinator_session_id,
                "agent_id": _native_value(event, "parent_agent_id", "parentAgentId"),
                "task_id": _native_value(event, "parent_task_id", "parentTaskId"),
                "tool_use_id": _native_value(event, "parent_tool_use_id", "parentToolUseId"),
                "invocation_id": self._event_invocation(event) or self.current_invocation,
                "invocation_watermark": self.watermark,
            },
            "transcript": {
                "coordinator_path": _native_value(event, "transcript_path", "transcriptPath"),
                "child_path": _native_value(event, "agent_transcript_path", "agentTranscriptPath"),
                "cwd": _native_value(event, "cwd", "working_directory", "workingDirectory"),
                "available": _native_value(event, "transcript_path", "transcriptPath") is not None,
            },
            "status": "unresolved",
            "stop_provenance": None,
            "model": None,
            "effort": None,
            "custom_definition": None,
            "restart_correlation": None,
            "admission_context": None,
            "tools": [],
            "permissions": None,
            "tool_events": {"active": [], "completed": [], "uncertain": []},
            "_tool_observation_known": False,
            "_effect_observation_known": False,
            "execution_mode": "foreground",
            "claim_ref": None,
            "lineage_incarnation": {"number": 1, "start_watermark": self.watermark},
            "task_events": [],
        }
        self.children[key] = record
        self._hold_event(reason, event, record)
        return record

    def _append_child_history(self, record: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        if len(self.child_history) >= MAX_NATIVE_CHILD_HISTORY:
            self.overflow = True
            return self._fail("uncertain-effect", "native child history is full")
        self.child_history.append(dict(record))
        return None

    def _attach_pending_tasks(self, record: dict[str, Any]) -> Optional[SdkAdapterError]:
        candidates = [
            (task_id, task)
            for task_id, task in self.pending_tasks.items()
            if (
                task.get("tool_use_id") is not None
                and str(task.get("tool_use_id")) == str(record.get("tool_use_id"))
            )
            or (
                task.get("agent_id") is not None
                and str(task.get("agent_id")) == str(record.get("agent_id"))
            )
        ]
        if len(candidates) > 1:
            return self._fail("ownership-conflict", "multiple native task records match one child")
        if not candidates:
            invocation = record.get("parent_links", {}).get("invocation_id")
            by_invocation = [
                (task_id, task)
                for task_id, task in self.pending_tasks.items()
                if task.get("invocation_id") == invocation
            ]
            if len(by_invocation) == 1:
                candidates = by_invocation
            elif len(by_invocation) > 1:
                return self._fail("ownership-conflict", "native task join is ambiguous", {})
            else:
                return None
        task_id, task = candidates[0]
        record["task_id"] = task_id
        record["task_type"] = task.get("task_type") or "unknown"
        record["task_terminal"] = False
        record["task_events"].append(task["event"])
        self.pending_tasks.pop(task_id, None)
        return None

    def _observe_subagent_start(self, event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        if (error := self._check_session(event, required=True)) is not None:
            return error
        mark = self._mark_event("subagentstart", event)
        if mark is _NATIVE_CROSS_SOURCE_DUPLICATE:
            return None
        if mark is not None:
            error = mark
            return error
        agent_id = _native_value(event, "agent_id", "agentId")
        if agent_id is None or not str(agent_id).strip():
            return self._fail("ownership-conflict", "SubagentStart omitted agent_id", event)
        agent_key = str(agent_id)
        if self._native_stop_fenced:
            return self._fail(
                "uncertain-effect",
                "native child start crossed an unresolved stop fence",
                event,
            )
        admission, error = self._pending_for_start(event)
        if error is not None:
            return error
        if admission is None:
            return self._fail(
                "ownership-conflict",
                "native child start has no unique pending admission",
                event,
            )
        invocation = self._event_invocation(event) or str(admission["invocation_id"])
        if invocation != admission.get("invocation_id"):
            return self._fail(
                "stale-generation",
                "SubagentStart has another parent invocation",
                event,
            )
        existing = self.children.get(agent_key)
        if existing is not None:
            if existing.get("native_stop_pending") is not None:
                return self._fail(
                    "uncertain-effect",
                    "native child restart is blocked while its stop is unresolved",
                    event,
                )
            if existing.get("status") in _NATIVE_ACTIVE_STATUSES:
                self._hold_event("native agent_id was started twice in one incarnation", event, existing)
                return None
            if int(existing.get("parent_links", {}).get("invocation_watermark", 0)) >= self.watermark:
                self._hold_event("native agent_id reuse lacks a new invocation watermark", event, existing)
                return None
            if (error := self._append_child_history(existing)) is not None:
                return error
        if len(self.children) >= MAX_NATIVE_CHILD_RECORDS and existing is None:
            self.overflow = True
            return self._fail("uncertain-effect", "native child ledger is full", event)
        agent_type = _native_value(event, "agent_type", "agentType")
        if agent_type is None or str(agent_type) != str(admission.get("agent_type")):
            self._unresolved_child(event, "SubagentStart agent_type does not match its trusted admission")
            return None
        expected_permission = _get_ci(admission.get("custom_definition", {}), "permissionMode", "permission_mode")
        actual_permission = _native_value(event, "permission_mode", "permissionMode")
        if expected_permission is not None and actual_permission is not None and str(expected_permission) != str(actual_permission):
            self._unresolved_child(event, "SubagentStart permission mode contradicts its trusted definition")
            return None
        parent_agent = _native_value(event, "parent_agent_id", "parentAgentId") or admission.get("parent_agent_id")
        parent_task = _native_value(event, "parent_task_id", "parentTaskId") or admission.get("parent_task_id")
        parent_tool = _native_value(event, "parent_tool_use_id", "parentToolUseId") or admission.get("parent_tool_use_id")
        if parent_agent is not None and str(parent_agent) not in self.children:
            self._unresolved_child(event, "nested native child parent_agent_id is unknown")
            return None
        transcript_path = _native_value(event, "transcript_path", "transcriptPath")
        cwd = _native_value(event, "cwd", "working_directory", "workingDirectory")
        policy = dict(admission.get("policy", {}))
        parent_links = {
            "session_id": self.coordinator_session_id,
            "parent_agent_id": None if parent_agent is None else str(parent_agent),
            "parent_task_id": None if parent_task is None else str(parent_task),
            "parent_tool_use_id": None if parent_tool is None else str(parent_tool),
            "invocation_id": invocation,
            "invocation_watermark": self.watermark,
            "prompt_id": admission.get("prompt_id"),
        }
        record: dict[str, Any] = {
            "agent_id": agent_key,
            "task_id": None,
            "type": None if agent_type is None else str(agent_type),
            "tool_use_id": admission.get("tool_use_id"),
            "parent_links": parent_links,
            "parent": {
                "session_id": self.coordinator_session_id,
                "agent_id": None if parent_agent is None else str(parent_agent),
                "task_id": None if parent_task is None else str(parent_task),
                "tool_use_id": None if parent_tool is None else str(parent_tool),
                "invocation_id": invocation,
                "invocation_watermark": self.watermark,
                "prompt_id": admission.get("prompt_id"),
            },
            "transcript": {
                "coordinator_path": None if transcript_path is None else str(transcript_path)[:1024],
                "child_path": None,
                "cwd": None if cwd is None else str(cwd)[:1024],
                "available": transcript_path is not None,
            },
            "status": "active",
            "stop_provenance": None,
            "model": _first_nonempty(_native_policy_lookup(policy, "model"), _native_value(event, "model")),
            "effort": _first_nonempty(_native_policy_lookup(policy, "effort"), _native_value(event, "effort")),
            "custom_definition": dict(admission.get("custom_definition", {})),
            "restart_correlation": None,
            "admission_context": {
                "admission_id": admission.get("admission_id"),
                "tool_use_id": admission.get("tool_use_id"),
                "invocation_id": invocation,
                "watermark": admission.get("admission_watermark"),
                "policy_digest": admission.get("policy_digest"),
            },
            "tools": list(admission.get("custom_definition", {}).get("tools", ())),
            "permissions": admission.get("custom_definition", {}).get("permissions"),
            "_tool_observation_known": False,
            "_effect_observation_known": False,
            "task_terminal": True,
            "tool_events": {"active": [], "completed": [], "uncertain": []},
            "execution_mode": "background" if admission.get("background_requested") else "foreground",
            "claim_ref": _native_policy_lookup(policy, "lineage_claim", "claim_ref"),
            "lineage_incarnation": {
                "number": (int(existing.get("lineage_incarnation", {}).get("number", 0)) + 1) if existing else 1,
                "start_watermark": self.watermark,
            },
            "task_events": [],
        }
        self.children[agent_key] = record
        self.pending_admissions.pop(str(admission["tool_use_id"]), None)
        return self._attach_pending_tasks(record)

    def _observe_subagent_stop(self, event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        if (error := self._check_session(event, required=True)) is not None:
            return error
        agent_id = _native_value(event, "agent_id", "agentId")
        actual_path = _native_value(event, "agent_transcript_path", "agentTranscriptPath")
        # The SDK can repeat an identical stop hook after the task terminal
        # event.  Once the current incarnation has the same child transcript,
        # this is an idempotent observation.  Check it before the duplicate
        # event ledger turns a safe replay into a new uncertainty.
        if agent_id is not None and actual_path is not None:
            existing = self.children.get(str(agent_id))
            if (
                existing is not None
                and existing.get("task_terminal") is True
                and str(existing.get("transcript", {}).get("child_path")) == str(actual_path)
                and existing.get("status") in _NATIVE_TERMINAL_STATUSES
            ):
                return None
        mark = self._mark_event("subagentstop", event)
        if mark is _NATIVE_CROSS_SOURCE_DUPLICATE:
            return None
        if mark is not None:
            error = mark
            return error
        if agent_id is None or str(agent_id) not in self.children:
            self._hold_event("SubagentStop has no admitted native child", event)
            return None
        record = self.children[str(agent_id)]
        status = record.get("status")
        if status not in _NATIVE_ACTIVE_STATUSES and status not in {"stopped", "restart-pending", "resume-pending"}:
            if status != "completed":
                self._hold_event("SubagentStop targeted a non-active child incarnation", event, record)
                return None
        if int(record.get("lineage_incarnation", {}).get("number", 1)) > 1:
            current_invocation = self._event_invocation(event)
            expected_invocation = record.get("parent_links", {}).get("invocation_id")
            current_tool = _native_value(event, "tool_use_id", "toolUseId")
            expected_tool = record.get("tool_use_id")
            current_prompt = _native_value(event, "prompt_id", "promptId")
            expected_prompt = record.get("parent_links", {}).get("prompt_id")
            correlated = (
                current_invocation is not None
                and expected_invocation is not None
                and current_invocation == expected_invocation
            ) or (
                current_tool is not None
                and expected_tool is not None
                and str(current_tool) == str(expected_tool)
            ) or (
                current_prompt is not None
                and expected_prompt is not None
                and str(current_prompt) == str(expected_prompt)
            )
            if not correlated:
                self._hold_event(
                    "late SubagentStop lacks current launch, prompt, or invocation correlation",
                    event,
                    record,
                )
                return None
        if (error := self._context_error(record, event)) is not None:
            self._hold_event("SubagentStop lacks current child-run correlation", event, record)
            return None
        if actual_path is not None:
            actual_path = str(actual_path)
            retired = self._retired_child_paths.setdefault(str(agent_id), set())
            known_path = record.get("transcript", {}).get("child_path")
            if known_path is not None and str(known_path) != actual_path:
                self._hold_event("SubagentStop child transcript does not match the current incarnation", event, record)
                return None
            record.setdefault("transcript", {})["child_path"] = actual_path
            retired.add(actual_path)
        if record.get("uncertain"):
            self._hold_event("native child already has unresolved lifecycle evidence", event, record)
            return None
        task_terminal = bool(record.get("task_terminal", record.get("task_id") is None))
        if record.get("status") in _NATIVE_ACTIVE_STATUSES or record.get("status") == "stopped":
            # A stop hook is terminal child evidence, but does not prove a
            # successful completion or exact continuation.  Leave the
            # controller a restart/resume decision instead of treating the
            # launch tool's end as child completion.
            record["status"] = "restart-pending"
        record["task_terminal"] = task_terminal
        prior_provenance = record.get("stop_provenance")
        hook_provenance = {"watermark": self.watermark}
        for key, value in (
            ("event_uuid", _native_value(event, "uuid", "event_uuid", "eventUuid")),
            ("stop_hook_active", _native_bool(_native_value(event, "stop_hook_active", "stopHookActive"))),
            ("kind", _native_value(event, "stop_reason", "stopReason", "reason", "origin", "cause")),
        ):
            if value is not None:
                hook_provenance[key] = value
        if (
            isinstance(prior_provenance, Mapping)
            and prior_provenance.get("source") == "task_notification"
        ):
            # Keep the authoritative notification's UUID, watermark and kind
            # together.  The later hook is useful evidence, but it is a
            # separate fact and cannot rewrite that terminal notification.
            provenance = dict(prior_provenance)
            provenance["hook"] = hook_provenance
            record["stop_provenance"] = provenance
        else:
            provenance = dict(prior_provenance) if isinstance(prior_provenance, Mapping) else {}
            provenance.update(hook_provenance)
            record["stop_provenance"] = provenance
        record["stop_watermark"] = self.watermark
        tool_id = record.get("tool_use_id")
        if tool_id is not None:
            self.pending_admissions.pop(str(tool_id), None)
        return None

    def _task_record_for_event(self, event: Mapping[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[SdkAdapterError]]:
        task_id = _native_value(event, "task_id", "taskId")
        if task_id is None or not str(task_id).strip():
            return None, self._fail("ownership-conflict", "native task event omitted task_id", event)
        task_key = str(task_id)
        for record in self.children.values():
            if str(record.get("task_id")) == task_key:
                return record, None
        agent_id = _native_value(event, "agent_id", "agentId")
        if agent_id is not None and str(agent_id) in self.children:
            return self.children[str(agent_id)], None
        tool_id = _native_value(event, "tool_use_id", "toolUseId")
        matching = [
            record
            for record in self.children.values()
            if tool_id is not None and str(record.get("tool_use_id")) == str(tool_id)
        ]
        if len(matching) == 1:
            return matching[0], None
        if len(matching) > 1:
            return None, self._fail("ownership-conflict", "native task event matched multiple children", event)
        return None, None

    def _observe_task_event(self, kind: str, event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        required_session = kind in {"taskstarted", "taskprogress", "tasknotification"}
        if (error := self._check_session(event, required=required_session)) is not None:
            return error
        mark = self._mark_event(kind, event)
        if mark is _NATIVE_CROSS_SOURCE_DUPLICATE:
            return None
        if mark is not None:
            error = mark
            return error
        supplied_task_type = _native_value(event, "task_type", "taskType")
        if supplied_task_type is not None and str(supplied_task_type) != "local_agent":
            return self._fail(
                "unsupported",
                "native task event has an unsupported task type",
                event,
            )
        task_id = _native_value(event, "task_id", "taskId")
        if task_id is None or not str(task_id).strip():
            return self._fail("ownership-conflict", "native task event omitted task_id", event)
        task_key = str(task_id)
        record, error = self._task_record_for_event(event)
        if error is not None:
            return error
        known_task_type = None
        if record is not None:
            known_task_type = record.get("task_type")
            if known_task_type in (None, "unknown"):
                for prior in reversed(record.get("task_events", ())):
                    candidate = prior.get("task_type")
                    if candidate not in (None, "unknown"):
                        known_task_type = candidate
                        break
        if known_task_type is None:
            pending = self.pending_tasks.get(task_key)
            if pending is not None:
                known_task_type = pending.get("task_type")
        task_type = (
            str(supplied_task_type)
            if supplied_task_type is not None
            else str(known_task_type)
            if known_task_type not in (None, "")
            else "unknown"
        )
        event_agent_id = _native_value(event, "agent_id", "agentId")
        if (
            record is not None
            and event_agent_id is not None
            and str(record.get("agent_id")) != str(event_agent_id)
        ):
            return self._fail("ownership-conflict", "native task event changed its child agent", event)
        task_event_authoritative = _native_bool(
            _native_value(event, "authoritative", "is_authoritative")
        )
        event_fact = {
            "kind": kind,
            "task_id": task_key,
            "task_type": task_type,
            "event_uuid": _native_value(event, "uuid", "event_uuid", "eventUuid"),
            "tool_use_id": _native_value(event, "tool_use_id", "toolUseId"),
            "status": _native_value(event, "status"),
            "watermark": self.watermark,
        }
        if kind in {"taskupdated", "tasknotification"}:
            # Keep an explicit rejection marker with the fact because the
            # event is appended before terminal-status validation below.
            event_fact["authoritative"] = task_event_authoritative is not False
            event_fact["validated"] = False
        if record is None:
            if kind != "taskstarted":
                if task_key not in self.pending_tasks:
                    self._hold_event("native task event has no admitted child", event)
                    return None
                self.pending_tasks[task_key]["event"] = event_fact
                return None
            if task_key in self.pending_tasks:
                return self._fail("uncertain-effect", "native task_started duplicated a pending task", event)
            if len(self.pending_tasks) >= MAX_NATIVE_CHILD_RECORDS:
                self.overflow = True
                return self._fail("uncertain-effect", "native task ledger is full", event)
            self.pending_tasks[task_key] = {
                "task_id": task_key,
                "agent_id": _native_value(event, "agent_id", "agentId"),
                "tool_use_id": _native_value(event, "tool_use_id", "toolUseId"),
                "invocation_id": self._event_invocation(event) or self.current_invocation,
                "task_type": task_type,
                "event": event_fact,
            }
            return None
        if kind == "taskstarted":
            if any(
                str(item.get("task_id")) == task_key and item.get("kind") == "taskstarted"
                for item in record.get("task_events", ())
            ):
                return self._fail("uncertain-effect", "native task_started duplicated a current child task", event)
            existing_task = record.get("task_id")
            if existing_task is not None and str(existing_task) != task_key:
                return self._fail("ownership-conflict", "child was bound to a different native task", event)
            record["task_id"] = task_key
            record["task_type"] = task_type
            record["task_terminal"] = False
            record["task_events"].append(event_fact)
            if len(record["task_events"]) > MAX_NATIVE_PROGRESS_EVENTS:
                del record["task_events"][: len(record["task_events"]) - MAX_NATIVE_PROGRESS_EVENTS]
            return None
        if (error := self._context_error(record, event)) is not None:
            self._hold_event("native task event lacks current child-run correlation", event, record)
            return None
        record["task_events"].append(event_fact)
        if len(record["task_events"]) > MAX_NATIVE_PROGRESS_EVENTS:
            del record["task_events"][: len(record["task_events"]) - MAX_NATIVE_PROGRESS_EVENTS]
        if kind in {"taskupdated", "tasknotification"}:
            status_value = _native_value(event, "status")
            patch = _native_value(event, "patch")
            if isinstance(patch, Mapping):
                status_value = _first_nonempty(status_value, _get_ci(patch, "status"))
            status = "" if status_value is None else str(status_value).casefold()
            if task_event_authoritative is False:
                return self._fail("unsupported", "native task terminal notification is not authoritative", event)
            if status in {"completed", "complete", "success", "done"}:
                record["status"] = "completed"
                record["task_terminal"] = True
                self.pending_tasks.pop(task_key, None)
            elif status in {"failed", "failure", "error", "stopped", "cancelled", "canceled", "terminated", "killed"}:
                # A task stop/failure is terminal evidence for the task, but
                # it is not successful child completion.  Keep it eligible
                # for the controller's restart/resume decision.
                record["status"] = "restart-pending"
                record["task_terminal"] = True
                self.pending_tasks.pop(task_key, None)
            elif status in {"stopping", "cancelling", "canceled_pending"}:
                record["status"] = "stopping"
            elif status in {"active", "running", "pending", "started", "in_progress"}:
                record["status"] = "active"
            else:
                return self._fail("uncertain-effect", "native task update has an unknown status", event)
            event_fact["validated"] = True
            if kind == "tasknotification" and status == "stopped":
                # Preserve the authoritative task notification as one
                # provenance fact.  A later SubagentStop may omit its reason;
                # it must not replace this fact with that hook's UUID or
                # watermark.
                notification_provenance = {
                    "source": "task_notification",
                    "event_uuid": event_fact.get("event_uuid"),
                    "watermark": event_fact.get("watermark"),
                    "kind": status,
                }
                prior_provenance = record.get("stop_provenance")
                if isinstance(prior_provenance, Mapping):
                    prior_hook = prior_provenance.get("hook")
                    if not isinstance(prior_hook, Mapping):
                        prior_hook = {
                            key: prior_provenance[key]
                            for key in ("event_uuid", "watermark", "stop_hook_active", "kind")
                            if key in prior_provenance
                        }
                    if prior_hook:
                        notification_provenance["hook"] = dict(prior_hook)
                record["stop_provenance"] = notification_provenance
        return None

    def _observe_agent_tool_end(self, kind: str, event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        name = _native_value(event, "tool_name", "toolName", "name")
        if name is None or str(name).casefold() not in _NATIVE_CHILD_TOOL_NAMES:
            return None
        tool_id = _native_value(event, "tool_use_id", "toolUseId", "id")
        event = dict(event)
        event.setdefault("_adapter_event_source", "hook")
        mark = self._mark_event(kind, event)
        if mark is _NATIVE_CROSS_SOURCE_DUPLICATE:
            return None
        if mark is not None:
            return mark
        if tool_id is None:
            return self._fail("uncertain-effect", "native Agent/Task tool completed without admission", event)
        admission = self.pending_admissions.get(str(tool_id))
        if admission is None:
            historical = [
                value
                for value in self.admissions
                if str(value.get("tool_use_id")) == str(tool_id)
            ]
            if len(historical) != 1:
                return self._fail("uncertain-effect", "native Agent/Task tool completed without admission", event)
            admission = historical[0]
        if admission.get("launch_completed"):
            return self._fail("uncertain-effect", "native Agent/Task tool completed twice", event)
        admission["launch_completed"] = True
        pending = self.pending_admissions.get(str(tool_id))
        if pending is not None:
            pending["launch_completed"] = True
        if kind == "posttoolusefailure":
            return self._record_uncertainty("native Agent/Task launch failed with child state unresolved", event)
        # The launch tool terminal event deliberately does not close its child.
        return None

    def _observe_child_tool(self, kind: str, event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        """Track a child tool only when the SDK supplies its agent_id context."""

        event = dict(event)
        event.setdefault("_adapter_event_source", "hook")
        if self._coordinator_interrupt_fenced and kind == "pretooluse":
            return SdkAdapterError(
                "busy", "coordinator interrupt fence blocks a new child tool"
            )
        mark = self._mark_event(kind, event)
        if mark is _NATIVE_CROSS_SOURCE_DUPLICATE:
            return None
        if mark is not None:
            return mark
        agent_id = _native_value(event, "agent_id", "agentId")
        if agent_id is None:
            return None
        record = self.children.get(str(agent_id))
        if record is None:
            return self._fail("ownership-conflict", "child tool hook has an unknown agent_id", event)
        if kind == "pretooluse" and record.get("status") not in _NATIVE_ACTIVE_STATUSES:
            return self._fail("uncertain-effect", "child tool hook targeted a non-active child", event)
        tool_id = _native_value(event, "tool_use_id", "toolUseId", "id")
        tool_name = _native_value(event, "tool_name", "toolName", "name")
        if tool_id is None or tool_name is None:
            return self._fail("uncertain-effect", "child tool hook omitted its ID or name", event)
        tool_key = str(tool_id)
        tools = {str(value).casefold() for value in record.get("tools", ())}
        if kind == "pretooluse":
            record["_tool_observation_known"] = True
            if str(tool_name).casefold() not in tools:
                return self._fail("unsupported", "child tool is outside its trusted definition", event)
            tool_input = _native_tool_input(event)
            detached = any(
                str(key) in _DETACHED_INPUT_KEYS
                and (_native_bool(value) is True)
                for key, value in tool_input.items()
            )
            command = _first_nonempty(tool_input.get("command"), tool_input.get("cmd"), tool_input.get("script"))
            if isinstance(command, str) and re.search(r"(?:^|[;&|\s])(setsid|nohup|disown)(?:\s|$)", command):
                detached = True
            if detached:
                return self._fail("unsupported", "child requested an unmanaged detached process", event)
            active = record.setdefault("tool_events", {}).setdefault("active", [])
            if any(str(item.get("tool_use_id")) == tool_key for item in active):
                return self._fail("uncertain-effect", "child tool-use ID was admitted twice", event)
            if len(active) >= MAX_NATIVE_PROGRESS_EVENTS:
                self.overflow = True
                return self._fail("uncertain-effect", "child tool ledger is full", event)
            active.append({"tool_use_id": tool_key, "tool_name": str(tool_name)})
            return None
        active = record.setdefault("tool_events", {}).setdefault("active", [])
        item = next((value for value in active if str(value.get("tool_use_id")) == tool_key), None)
        if item is None:
            return self._fail("uncertain-effect", "child tool completion has no tracked start", event)
        active.remove(item)
        record["_tool_observation_known"] = True
        completed = record.setdefault("tool_events", {}).setdefault("completed", [])
        completed.append({**item, "watermark": self.watermark, "failure": kind == "posttoolusefailure"})
        if len(completed) > MAX_NATIVE_PROGRESS_EVENTS:
            del completed[: len(completed) - MAX_NATIVE_PROGRESS_EVENTS]
        if kind == "posttoolusefailure":
            self._hold_event("child tool failure leaves its effect uncertain", event, record)
            return self._fail("uncertain-effect", "child tool failure leaves its effect uncertain", event)
        return None

    def _remember_coordinator_event(
        self, event: Mapping[str, Any], *, observed_watermark: Optional[int] = None
    ) -> None:
        """Retain bounded hook/stream facts that may race intent persistence."""

        if not self.coordinator_enabled or not isinstance(event, Mapping):
            return
        kind = _native_event_kind(event)
        event_type = str(_get_ci(event, "type") or "").casefold()
        if kind not in {
            "posttooluse", "posttoolusefailure", "subagentstop",
            "tasknotification",
        } and event_type not in {
            "result", "message-stop", "turn-end", "turn-ended", "turn-complete",
            "done", "drained", "idle", "quiesced",
        }:
            return
        if len(self._coordinator_fact_events) >= MAX_NATIVE_LIFECYCLE_EVENTS:
            self._coordinator_fact_overflow = True
            return
        captured = copy.deepcopy(dict(event))
        cursor = _native_value(event, "sequence", "event_cursor", "cursor", "watermark")
        if observed_watermark is None:
            observed_watermark = self.watermark
        if type(cursor) is int and not isinstance(cursor, bool):
            observed_watermark = max(observed_watermark, cursor)
        captured["_coordinator_observed_watermark"] = observed_watermark
        self._coordinator_fact_events.append(captured)

    def record_coordinator_observation(self, event: Mapping[str, Any]) -> None:
        """Record an event only after the native ledger accepted it."""

        self._remember_coordinator_event(event, observed_watermark=self.watermark)

    def note_parent_state(
        self,
        *,
        active: bool,
        drained: bool,
        invocation_id: Any = None,
        result_watermark: Any = None,
        reader_drained_watermark: Any = None,
    ) -> Optional[SdkAdapterError]:
        """Record coordinator-owned parent state for a later roster seal."""

        if self.coordinator_enabled:
            if self.current_invocation is None or invocation_id is None:
                return SdkAdapterError(
                    "unsupported", "coordinator parent state is not bound to an invocation"
                )
            if str(invocation_id) != self.current_invocation:
                return self._fail(
                    "stale-generation", "parent state belongs to another invocation"
                )
        elif invocation_id is not None and self.current_invocation is not None:
            if str(invocation_id) != self.current_invocation:
                return self._fail(
                    "stale-generation", "parent state belongs to another invocation"
                )
        if self._reservation_sealed:
            return SdkAdapterError(
                "stale-generation", "parent state arrived after native invocation reservation"
            )
        explicit_result = (
            not active
            and drained
            and self.current_invocation is not None
            and result_watermark is not None
            and reader_drained_watermark is not None
        )
        # Validate the reader-correlated watermarks before changing the
        # observational flags.  A malformed result must not leave a partial
        # terminal state that a later reservation could reuse.
        if explicit_result:
            if type(result_watermark) is not int or type(reader_drained_watermark) is not int:
                return self._fail("invalid", "native parent result watermarks are invalid")
            if result_watermark <= self.current_invocation_watermark:
                return self._fail("stale-generation", "native parent result watermark predates its invocation")
            if reader_drained_watermark < result_watermark:
                return self._fail("stale-generation", "native reader drain watermark moved backwards")
            if self.runtime_cursor is not None and reader_drained_watermark < self.runtime_cursor:
                return self._fail("stale-generation", "native reader drain cursor moved backwards")
        self._parent_active = bool(active)
        self._parent_drained = bool(drained)
        self._parent_state_observed = True
        # Idle/drained flags are observational state only.  They do not prove
        # that the correlated parent result and independent reader drain were
        # observed.  Only explicit watermarks supplied by the accepted reader
        # correlation may populate the terminal-result proof.
        if explicit_result:
            self.runtime_cursor = max(
                self.runtime_cursor or 0,
                reader_drained_watermark,
            )
            self.watermark = max(self.watermark, reader_drained_watermark)
            self._parent_result = {
                "session_id": self.coordinator_session_id,
                "invocation_id": self.current_invocation,
                "message_id": self.current_message_id,
                "result_watermark": result_watermark,
                "reader_drained_watermark": reader_drained_watermark,
            }
        return None

    def note_parent_result(
        self,
        *,
        invocation_id: Any,
        message_id: Any,
        result_watermark: Any,
        reader_drained_watermark: Any,
    ) -> Optional[SdkAdapterError]:
        """Record a reader-correlated terminal result, never caller flags."""

        if self.current_invocation is None or self.current_message_id is None:
            return SdkAdapterError("unsupported", "native parent result has no current invocation")
        if str(invocation_id) != self.current_invocation or str(message_id) != self.current_message_id:
            return self._fail("stale-generation", "native parent result has a stale invocation or mailbox")
        return self.note_parent_state(
            active=False,
            drained=True,
            invocation_id=invocation_id,
            result_watermark=result_watermark,
            reader_drained_watermark=reader_drained_watermark,
        )

    @staticmethod
    def _coordinator_ids(values: Any, label: str) -> list[str]:
        if not isinstance(values, (list, tuple)) or len(values) > MAX_NATIVE_PROGRESS_EVENTS:
            raise SdkAdapterError("unsupported", f"coordinator interrupt {label} inventory is unavailable")
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise SdkAdapterError("uncertain-effect", f"coordinator interrupt {label} contains an invalid ID")
            value = value.strip()
            if value in seen:
                raise SdkAdapterError("uncertain-effect", f"coordinator interrupt {label} contains a duplicate ID")
            seen.add(value)
            result.append(value)
        return result

    @staticmethod
    def _coordinator_tool_ids(items: Any, label: str) -> list[str]:
        if not isinstance(items, (list, tuple)):
            raise SdkAdapterError("unsupported", f"coordinator interrupt {label} inventory is unavailable")
        values: list[str] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise SdkAdapterError("uncertain-effect", f"coordinator interrupt {label} fact is malformed")
            value = item.get("tool_use_id")
            if not isinstance(value, str) or not value.strip():
                raise SdkAdapterError("uncertain-effect", f"coordinator interrupt {label} lacks a tool ID")
            values.append(value.strip())
        return NativeLineageLedger._coordinator_ids(values, label)

    def _coordinator_child_roster(
        self, record: Mapping[str, Any], *, seal_watermark: int
    ) -> dict[str, Any]:
        context = record.get("admission_context")
        admission_id = context.get("admission_id") if isinstance(context, Mapping) else None
        admission = next(
            (
                value for value in self.admissions
                if isinstance(value, Mapping) and value.get("admission_id") == admission_id
            ),
            None,
        )
        if not isinstance(admission, Mapping):
            raise SdkAdapterError("ownership-conflict", "coordinator interrupt child lacks its durable admission")
        task_id = record.get("task_id")
        tool_use_id = record.get("tool_use_id")
        agent_id = record.get("agent_id")
        invocation_id = record.get("parent_links", {}).get("invocation_id")
        parent_agent_id = record.get("parent_links", {}).get("parent_agent_id")
        incarnation = record.get("lineage_incarnation")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (admission_id, task_id, tool_use_id, agent_id, invocation_id)
        ):
            raise SdkAdapterError("unsupported", "coordinator interrupt child lacks a complete identity")
        if not isinstance(incarnation, Mapping) or type(incarnation.get("number")) is not int or incarnation["number"] <= 0:
            raise SdkAdapterError("unsupported", "coordinator interrupt child lacks an incarnation")
        start_watermark = incarnation.get("start_watermark")
        admission_watermark = admission.get("watermark")
        if (
            type(start_watermark) is not int
            or start_watermark <= 0
            or type(admission_watermark) is not int
            or admission_watermark <= 0
            or start_watermark <= admission_watermark
            or start_watermark > seal_watermark
        ):
            raise SdkAdapterError("stale-generation", "coordinator interrupt child watermark is not current")
        task_events = [
            value for value in record.get("task_events", ())
            if isinstance(value, Mapping) and value.get("kind") == "taskstarted"
        ]
        if len(task_events) != 1:
            raise SdkAdapterError("unsupported", "coordinator interrupt child lacks one task start fact")
        task_start = task_events[0]
        task_start_watermark = task_start.get("watermark")
        if (
            type(task_start_watermark) is not int
            or task_start_watermark <= admission_watermark
            or task_start_watermark > seal_watermark
        ):
            raise SdkAdapterError("stale-generation", "coordinator interrupt task start watermark is not current")
        task_type = task_start.get("task_type") or record.get("task_type") or "unknown"
        if not isinstance(task_type, str) or not task_type.strip() or len(task_type) > 256:
            raise SdkAdapterError("unsupported", "coordinator interrupt task type is unavailable")
        raw_status = record.get("status")
        if raw_status in {"restart-pending", "resume-pending"}:
            terminal_facts = [
                value for value in record.get("task_events", ())
                if isinstance(value, Mapping)
                and value.get("kind") == "tasknotification"
                and str(value.get("status") or "").casefold()
                in {"failed", "failure", "error"}
            ]
            if terminal_facts:
                raise SdkAdapterError(
                    "unsupported",
                    "coordinator interrupt cannot normalize a failed child into stopped",
                )
        status = raw_status
        if status == "completed":
            status = "completed"
        elif status in {"stopped", "restart-pending", "resume-pending"}:
            status = "stopped"
        elif status in _NATIVE_ACTIVE_STATUSES:
            status = "active"
        else:
            raise SdkAdapterError("unsupported", "coordinator interrupt child status is unresolved")
        terminal_watermark: Optional[int] = None
        if status != "active":
            terminal_facts = [
                value for value in record.get("task_events", ())
                if isinstance(value, Mapping)
                and value.get("kind") == "tasknotification"
                and str(value.get("status") or "").casefold()
                in {"completed", "complete", "success", "done", "stopped", "failed", "failure", "error", "cancelled", "canceled", "terminated", "killed"}
            ]
            if terminal_facts:
                terminal_watermark = terminal_facts[-1].get("watermark")
            if terminal_watermark is None:
                terminal_watermark = record.get("stop_watermark")
            if type(terminal_watermark) is not int or terminal_watermark < start_watermark or terminal_watermark > seal_watermark:
                raise SdkAdapterError("unsupported", "coordinator interrupt child terminal watermark is unavailable")
        active_tool_ids = self._coordinator_tool_ids(
            record.get("tool_events", {}).get("active", ())
            if isinstance(record.get("tool_events"), Mapping) else (),
            "child active tools",
        )
        uncertain_tool_ids = self._coordinator_tool_ids(
            record.get("tool_events", {}).get("uncertain", ())
            if isinstance(record.get("tool_events"), Mapping) else (),
            "child uncertain tools",
        )
        if set(active_tool_ids) & set(uncertain_tool_ids):
            raise SdkAdapterError("uncertain-effect", "coordinator interrupt child tool inventory overlaps")
        effect_events = record.get("effect_events")
        if isinstance(effect_events, Mapping):
            unresolved_effect_ids = self._coordinator_ids(
                list(effect_events.get("unresolved", ())), "child unresolved effects"
            )
        else:
            unresolved_effect_ids = []
        digest = admission.get("trusted_definition_digest")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SdkAdapterError("unsupported", "coordinator interrupt child definition digest is unavailable")
        # The official hook surface cannot prove arbitrary writable effects or
        # descendant ownership.  Keep this producer bounded to trusted
        # read-only child definitions unless a real effect ledger is present.
        trusted_tools = record.get("tools")
        if (
            not isinstance(trusted_tools, list)
            or not trusted_tools
            or not {str(value).casefold() for value in trusted_tools}.issubset(_READ_ONLY_BUILTIN_TOOLS)
        ) and not isinstance(effect_events, Mapping):
            raise SdkAdapterError(
                "unsupported",
                "coordinator interrupt cannot seal an unobserved child effect inventory",
            )
        return {
            "admission_id": str(admission_id),
            "tool_use_id": str(tool_use_id),
            "agent_id": str(agent_id),
            "task_id": str(task_id),
            "parent_agent_id": None if parent_agent_id is None else str(parent_agent_id),
            "invocation_id": str(invocation_id),
            "lineage_incarnation": incarnation["number"],
            "trusted_definition_digest": digest,
            "start_watermark": start_watermark,
            "task_start_event": {
                "event_uuid": task_start.get("event_uuid"),
                "watermark": task_start_watermark,
                "task_type": task_type,
            },
            "status": status,
            "terminal_watermark": terminal_watermark,
            "active_tool_ids": active_tool_ids,
            "uncertain_tool_ids": uncertain_tool_ids,
            "unresolved_effect_ids": unresolved_effect_ids,
        }

    def _coordinator_parent_tool_inventory(
        self, tool_evidence: Any, *, known_child_ids: set[str] | None = None
    ) -> tuple[list[str], list[str]]:
        if tool_evidence is None:
            raise SdkAdapterError(
                "unsupported", "coordinator interrupt parent tool inventory is unavailable"
            )
        if bool(getattr(tool_evidence, "evidence_overflow", False)):
            raise SdkAdapterError(
                "uncertain-effect", "coordinator interrupt parent tool ledger overflowed"
            )
        owners = getattr(tool_evidence, "_owners", {})
        unknown = getattr(tool_evidence, "_unknown_owners", set())
        active = getattr(tool_evidence, "active", {})
        parent_active: list[str] = []
        for tool_id in active:
            owner = owners.get(tool_id)
            if tool_id in unknown:
                raise SdkAdapterError("unsupported", "coordinator interrupt tool owner is unknown")
            if owner is None:
                parent_active.append(str(tool_id))
            elif known_child_ids is not None and str(owner) not in known_child_ids:
                raise SdkAdapterError("ownership-conflict", "coordinator interrupt tool owner is not an admitted child")
        uncertain: list[str] = []
        for item in getattr(tool_evidence, "uncertain", ()):
            if not isinstance(item, Mapping):
                continue
            tool_id = item.get("tool_use_id")
            if tool_id is None:
                # An external/effect uncertainty without an identity cannot be
                # sealed into the complete roster.
                raise SdkAdapterError("unsupported", "coordinator interrupt has an unowned uncertain effect")
            tool_id = str(tool_id)
            owner = owners.get(tool_id)
            if tool_id in unknown:
                raise SdkAdapterError("unsupported", "coordinator interrupt uncertain tool owner is unknown")
            if owner is None:
                uncertain.append(tool_id)
            elif known_child_ids is not None and str(owner) not in known_child_ids:
                raise SdkAdapterError("ownership-conflict", "coordinator interrupt uncertain tool owner is not an admitted child")
        return self._coordinator_ids(parent_active, "parent active tools"), self._coordinator_ids(uncertain, "parent uncertain tools")

    def _coordinator_roster(
        self,
        *,
        seal_watermark: int,
        tool_evidence: Any = None,
        parent_state: Optional[str] = None,
    ) -> dict[str, Any]:
        if self._coordinator_fact_overflow or self.overflow:
            raise SdkAdapterError("uncertain-effect", "coordinator interrupt fact ledger overflowed")
        if self.pending_admissions or self.pending_tasks:
            raise SdkAdapterError("unsupported", "coordinator interrupt has pending admissions or tasks")
        if self.current_invocation is None:
            raise SdkAdapterError("unsupported", "coordinator interrupt has no bound parent invocation")
        if not self._parent_state_observed:
            raise SdkAdapterError(
                "unsupported", "coordinator interrupt parent state has not been observed"
            )
        # The official hook/event surface does not provide a complete proof of
        # arbitrary writable parent effects.  A read-only parent (or a parent
        # with a future, actually populated effect ledger) is required before
        # an empty unresolved-effect inventory can be sealed.
        if not self.parent_read_only:
            raise SdkAdapterError(
                "unsupported",
                "coordinator interrupt cannot seal an unobserved writable parent effect inventory",
            )
        children = [
            self._coordinator_child_roster(record, seal_watermark=seal_watermark)
            for record in self.children.values()
        ]
        admission_ids = {str(value.get("admission_id")) for value in self.admissions if isinstance(value, Mapping)}
        child_admission_ids = {child["admission_id"] for child in children}
        if admission_ids != child_admission_ids:
            raise SdkAdapterError("unsupported", "coordinator interrupt roster does not cover all admissions")
        parent_active, parent_uncertain = self._coordinator_parent_tool_inventory(
            tool_evidence, known_child_ids={child["agent_id"] for child in children}
        )
        child_tools = {
            tool_id
            for child in children
            for tool_id in child["active_tool_ids"] + child["uncertain_tool_ids"]
        }
        if set(parent_active) & child_tools or set(parent_uncertain) & child_tools:
            raise SdkAdapterError("ownership-conflict", "coordinator interrupt tool ownership is ambiguous")
        observed_parent_state = "active" if self._parent_active else "idle"
        if parent_state is not None and parent_state != observed_parent_state:
            raise SdkAdapterError(
                "stale-generation", "coordinator parent state changed during roster sealing"
            )
        roster = {
            "parent_state": observed_parent_state,
            "children": sorted(children, key=lambda item: item["admission_id"]),
            "pending_admission_ids": [],
            "pending_task_ids": [],
            "parent_active_tool_ids": parent_active,
            "parent_uncertain_tool_ids": parent_uncertain,
            "parent_unresolved_effect_ids": [],
            "descendant_ids": [],
        }
        return roster

    @staticmethod
    def _coordinator_roster_projection(roster: Mapping[str, Any]) -> dict[str, Any]:
        children = []
        for child in roster["children"]:
            children.append({
                "admission_id": child["admission_id"],
                "tool_use_id": child["tool_use_id"],
                "agent_id": child["agent_id"],
                "task_id": child["task_id"],
                "parent_agent_id": child["parent_agent_id"],
                "invocation_id": child["invocation_id"],
                "lineage_incarnation": child["lineage_incarnation"],
                "trusted_definition_digest": child["trusted_definition_digest"],
                "active_tool_ids": sorted(child["active_tool_ids"]),
                "uncertain_tool_ids": sorted(child["uncertain_tool_ids"]),
                "unresolved_effect_ids": sorted(child["unresolved_effect_ids"]),
            })
        children.sort(key=lambda item: item["admission_id"])
        return {
            "children": children,
            "pending_admission_ids": sorted(roster["pending_admission_ids"]),
            "pending_task_ids": sorted(roster["pending_task_ids"]),
            "parent_active_tool_ids": sorted(roster["parent_active_tool_ids"]),
            "parent_uncertain_tool_ids": sorted(roster["parent_uncertain_tool_ids"]),
            "parent_unresolved_effect_ids": sorted(roster["parent_unresolved_effect_ids"]),
            "descendant_ids": sorted(roster["descendant_ids"]),
        }

    @staticmethod
    def _coordinator_evidence_id(interrupt_id: str, kind: str, identity: Any = None) -> str:
        suffix = kind if identity is None else f"{kind}:{identity}"
        value = f"{interrupt_id}:{suffix}"
        if len(value) <= 256 and "\x00" not in value:
            return value
        return "coordinator-" + hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()

    def prepare_native_coordinator(self) -> Optional[SdkAdapterError]:
        """Validate trusted startup identity before the runner is opened."""

        if not self.coordinator_enabled:
            return None
        identity, error = self._validated_lineage_identity()
        if error is not None:
            return error
        if identity is None or self.coordinator_session_id is None:
            return self._fail("unsupported", "native coordinator startup identity is unavailable")
        try:
            native_definition_facts(self.trusted_definitions)
        except SdkAdapterError as exc:
            return exc
        return None

    def _invocation_context_digests(self) -> tuple[str, str, str]:
        definitions_digest = _native_full_digest(self._definition_facts)
        permissions = {
            name: {
                key: facts.get(key)
                for key in ("tools", "permissionMode", "permissions", "writable_paths")
            }
            for name, facts in sorted(self._definition_facts.items())
        }
        permissions_digest = _native_full_digest(permissions)
        claim_digest = _native_full_digest(self._lineage_claim_exact)
        return definitions_digest, permissions_digest, claim_digest

    def _native_child_context_digest(self) -> str:
        """Digest the exact startup/admission context available to this ledger.

        Native runner fingerprints normally carry the controller's complete
        admission-context.  Older/focused SDK seams carry only its immutable
        identity projection; retaining that projection is still preferable to
        inventing a controller operation or dropping fields.  ``fenced`` is
        the one mutable controller field intentionally excluded by contract.
        """

        source: Any = self.lineage_context
        if not isinstance(source, Mapping):
            source = self.lineage_claim
        if not isinstance(source, Mapping):
            raise SdkAdapterError(
                "unsupported", "native child observation lacks its validated admission context"
            )
        context = copy.deepcopy(dict(source))
        context.pop("fenced", None)
        return _native_full_digest(context)

    def _native_child_observation_projection(
        self, record: Mapping[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Build one joined child projection and its normalized outcome."""

        context = record.get("admission_context")
        admission_id = context.get("admission_id") if isinstance(context, Mapping) else None
        admission = next(
            (
                value for value in self.admissions
                if isinstance(value, Mapping) and value.get("admission_id") == admission_id
            ),
            None,
        )
        if not isinstance(admission, Mapping):
            raise SdkAdapterError(
                "ownership-conflict", "native child observation lacks its durable admission"
            )
        task_id = record.get("task_id")
        tool_use_id = record.get("tool_use_id")
        agent_id = record.get("agent_id")
        invocation_id = record.get("parent_links", {}).get("invocation_id")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (admission_id, task_id, tool_use_id, agent_id, invocation_id)
        ):
            raise SdkAdapterError(
                "unsupported", "native child observation lacks a complete joined identity"
            )
        incarnation = record.get("lineage_incarnation")
        if (
            not isinstance(incarnation, Mapping)
            or type(incarnation.get("number")) is not int
            or incarnation["number"] <= 0
            or type(incarnation.get("start_watermark")) is not int
            or incarnation["start_watermark"] <= 0
        ):
            raise SdkAdapterError(
                "unsupported", "native child observation lacks its incarnation"
            )
        admission_watermark = admission.get("watermark")
        if (
            type(admission_watermark) is not int
            or admission_watermark <= 0
            or incarnation["start_watermark"] <= admission_watermark
        ):
            raise SdkAdapterError(
                "stale-generation", "native child observation admission/start watermark is stale"
            )
        task_events = [
            value for value in record.get("task_events", ())
            if isinstance(value, Mapping) and value.get("kind") == "taskstarted"
        ]
        if len(task_events) != 1:
            raise SdkAdapterError(
                "unsupported", "native child observation lacks one task start fact"
            )
        task_start = task_events[0]
        task_start_watermark = task_start.get("watermark")
        if (
            type(task_start_watermark) is not int
            or task_start_watermark <= admission_watermark
        ):
            raise SdkAdapterError(
                "stale-generation", "native child observation task start watermark is stale"
            )
        task_type = task_start.get("task_type") or record.get("task_type") or "unknown"
        task_type = _wire_id(task_type, "native child task type")
        raw_status = record.get("status")
        if raw_status == "completed":
            child_status = "completed"
        elif raw_status in _NATIVE_ACTIVE_STATUSES:
            child_status = "active"
        elif raw_status in {
            "stopped", "restart-pending", "resume-pending", "stopping"
        }:
            child_status = "stopped"
        else:
            raise SdkAdapterError(
                "unsupported", "native child observation status is unresolved"
            )
        terminal_watermark: Optional[int] = None
        terminal_outcome: Optional[str] = None
        terminal_statuses = {
            "completed", "complete", "success", "done", "stopped", "failed",
            "failure", "error", "cancelled", "canceled", "terminated", "killed",
        }
        terminal_facts = [
            value for value in record.get("task_events", ())
            if (
                isinstance(value, Mapping)
                and value.get("kind") in {"tasknotification", "taskupdated"}
                and str(value.get("status") or "").casefold() in terminal_statuses
            )
        ]
        if child_status != "active":
            if terminal_facts:
                terminal_fact = terminal_facts[-1]
                terminal_watermark = terminal_fact.get("watermark")
                status = str(terminal_fact.get("status") or "").casefold()
                terminal_outcome = {
                    "completed": "completed", "complete": "completed",
                    "success": "completed", "done": "completed",
                    "stopped": "stopped", "terminated": "stopped", "killed": "stopped",
                    "failed": "failed", "failure": "failed", "error": "failed",
                    "cancelled": "cancelled", "canceled": "cancelled",
                }.get(status, "unknown")
            else:
                terminal_watermark = record.get("stop_watermark")
                terminal_outcome = "stopped" if record.get("stop_provenance") else "unknown"
            if (
                type(terminal_watermark) is not int
                or terminal_watermark < incarnation["start_watermark"]
                or terminal_watermark > self.watermark
            ):
                raise SdkAdapterError(
                    "unsupported", "native child observation terminal watermark is unavailable"
                )
            if child_status == "completed" and terminal_outcome != "completed":
                raise SdkAdapterError(
                    "unsupported", "native child completion lacks a completed terminal outcome"
                )
        active_tool_ids = self._coordinator_tool_ids(
            record.get("tool_events", {}).get("active", ())
            if isinstance(record.get("tool_events"), Mapping) else (),
            "child active tools",
        )
        uncertain_tool_ids = self._coordinator_tool_ids(
            record.get("tool_events", {}).get("uncertain", ())
            if isinstance(record.get("tool_events"), Mapping) else (),
            "child uncertain tools",
        )
        effect_events = record.get("effect_events")
        unresolved_effect_ids = self._coordinator_ids(
            list(effect_events.get("unresolved", ())), "child unresolved effects"
        ) if isinstance(effect_events, Mapping) else []
        trusted_definition_digest = admission.get("trusted_definition_digest")
        _native_digest_field(
            trusted_definition_digest, "native child trusted_definition_digest"
        )
        # A read-only configured child has a complete bounded effect policy;
        # a writable child needs a real effect ledger before observation can be
        # represented.  Never infer completion from the launch tool's return.
        trusted_tools = record.get("tools")
        if (
            not isinstance(trusted_tools, list)
            or not trusted_tools
            or not {
                str(value).casefold() for value in trusted_tools
            }.issubset(_READ_ONLY_BUILTIN_TOOLS)
        ) and not isinstance(effect_events, Mapping):
            raise SdkAdapterError(
                "unsupported", "native child observation lacks its effect inventory"
            )
        projection = {
            "admission_id": str(admission_id),
            "tool_use_id": str(tool_use_id),
            "agent_id": str(agent_id),
            "task_id": str(task_id),
            "parent_agent_id": (
                None
                if record.get("parent_links", {}).get("parent_agent_id") is None
                else str(record["parent_links"]["parent_agent_id"])
            ),
            "invocation_id": str(invocation_id),
            "lineage_incarnation": incarnation["number"],
            "trusted_definition_digest": trusted_definition_digest,
            "start_watermark": incarnation["start_watermark"],
            "task_start_event": {
                "event_uuid": task_start.get("event_uuid"),
                "watermark": task_start_watermark,
                "task_type": task_type,
            },
            "status": child_status,
            "terminal_watermark": terminal_watermark,
            "active_tool_ids": active_tool_ids,
            "uncertain_tool_ids": uncertain_tool_ids,
            "unresolved_effect_ids": unresolved_effect_ids,
        }
        return _native_child_projection(projection), terminal_outcome

    def native_child_observation_for_event(
        self, event: Mapping[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Produce a terminal joined-child observation from ledger facts only."""

        if not self.coordinator_enabled:
            raise SdkAdapterError(
                "unsupported", "native child observation requires coordinator lineage mode"
            )
        kind = _native_event_kind(event)
        if kind not in {"tasknotification", "taskupdated", "subagentstop"}:
            return None
        if kind == "subagentstop":
            agent_id = _native_value(event, "agent_id", "agentId")
            record = self.children.get(str(agent_id)) if agent_id is not None else None
        else:
            record, error = self._task_record_for_event(event)
            if error is not None:
                raise error
        if not isinstance(record, Mapping):
            # The ordinary lifecycle observer retains an uncertainty for an
            # unknown event.  No synthetic row is emitted for that fact.
            return None
        if record.get("task_terminal") is not True:
            return None
        child, outcome = self._native_child_observation_projection(record)
        identity, error = self._validated_lineage_identity()
        if error is not None:
            raise error
        assert identity is not None
        invocation_id = record.get("parent_links", {}).get("invocation_id")
        if invocation_id != self.current_invocation:
            raise SdkAdapterError(
                "stale-generation", "native child observation belongs to another invocation"
            )
        source_identity = {
            "owner_generation": identity["owner_generation"],
            "lineage_id": identity["lineage_id"],
            "lineage_generation": self._lineage_generation(),
            "session_uuid": self.coordinator_session_id,
            "runner_incarnation": identity["runner_incarnation"],
            "invocation_id": str(invocation_id),
        }
        observation = {
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "record_kind": "native-child-observation",
            "observation_id": "native-child-" + _uuid.uuid4().hex,
            "source_identity": source_identity,
            "context_binding_digest": self._native_child_context_digest(),
            "claim_digest": _native_full_digest(self._lineage_claim_exact),
            "observation_watermark": self.watermark,
            "terminal_outcome": outcome,
            "child": child,
        }
        return _native_child_observation(observation)

    @property
    def invocation_reservation(self) -> Optional[dict[str, Any]]:
        """Return only the bounded observational reservation projection."""

        return None if self._invocation_reservation is None else copy.deepcopy(self._invocation_reservation)

    def prepare_invocation_reservation(
        self,
        request: Mapping[str, Any],
        *,
        participant_id: Any = None,
        tool_evidence: Any = None,
    ) -> dict[str, Any]:
        """Issue one terminal-proof-backed same-runner reservation.

        This method is deliberately fed only runner-owned ledger/tool facts;
        the request supplies identity bindings but never supplies terminal or
        quiescence authority.  An exact retry observes the existing sealed
        reservation, while every competing request refuses before mutation.
        """

        binding = _native_invocation_binding(request)
        if participant_id is not None and binding["participant_id"] != _wire_id(participant_id, "participant_id"):
            raise SdkAdapterError("ownership-conflict", "native reservation participant is not the coordinator")
        if self._invocation_reservation is not None:
            existing = self._invocation_reservation
            existing_binding = {
                key: existing[key] for key in _NATIVE_INVOCATION_BINDING_FIELDS
            }
            if existing_binding == binding:
                return copy.deepcopy(existing)
            raise SdkAdapterError(
                "busy", "a different native invocation reservation is already sealed"
            )
        if not self.coordinator_enabled:
            raise SdkAdapterError(
                "unsupported", "native invocation reservation requires coordinator lineage mode"
            )
        if binding["session_id"] != self.coordinator_session_id:
            raise SdkAdapterError("stale-generation", "native reservation session changed")
        identity, identity_error = self._validated_lineage_identity()
        if identity_error is not None:
            raise identity_error
        assert identity is not None
        if any(
            binding[key] != identity.get(key)
            for key in ("owner_generation", "lineage_id", "runner_incarnation")
        ):
            raise SdkAdapterError("stale-generation", "native reservation lineage identity changed")
        if binding["lineage_generation"] != self._lineage_generation():
            raise SdkAdapterError("stale-generation", "native reservation lineage generation changed")
        definitions_digest, permissions_digest, claim_digest = self._invocation_context_digests()
        if binding["definitions_digest"] != definitions_digest:
            raise SdkAdapterError("stale-generation", "native reservation definitions changed")
        if binding["permissions_digest"] != permissions_digest:
            raise SdkAdapterError("stale-generation", "native reservation permissions changed")
        if binding["claim_digest"] != claim_digest:
            raise SdkAdapterError("stale-generation", "native reservation claim changed")
        if self.current_invocation is None or self.current_message_id is None:
            raise SdkAdapterError("unsupported", "native reservation has no current invocation")
        if binding["prior_invocation_id"] != self.current_invocation:
            raise SdkAdapterError("stale-generation", "native reservation prior invocation is stale")
        if binding["prior_mailbox_id"] != self.current_message_id:
            raise SdkAdapterError("stale-generation", "native reservation prior mailbox is stale")
        if binding["prior_invocation_id"] != binding["prior_mailbox_id"]:
            raise SdkAdapterError("invalid", "native invocation and mailbox IDs must match")
        if binding["next_invocation_id"] != binding["next_mailbox_id"]:
            raise SdkAdapterError("invalid", "native invocation and mailbox IDs must match")
        if binding["prior_watermark"] != self.current_invocation_watermark:
            raise SdkAdapterError("stale-generation", "native reservation prior watermark is stale")
        if not self.released:
            raise SdkAdapterError("busy", "native reservation requires explicit release")
        if self.error is not None:
            raise self.error
        if self.overflow or self._coordinator_fact_overflow:
            raise SdkAdapterError("uncertain-effect", "native reservation evidence overflowed")
        if not self._parent_state_observed or self._parent_active or not self._parent_drained:
            raise SdkAdapterError("busy", "native parent invocation is not terminal and drained")
        if not self.quiescent:
            raise SdkAdapterError("uncertain-effect", "native child/effect ledger is not quiescent")
        if tool_evidence is None:
            raise SdkAdapterError("unsupported", "native reservation lacks independent tool evidence")
        parent_result = self._parent_result
        if not isinstance(parent_result, Mapping):
            raise SdkAdapterError("unsupported", "native reservation lacks a correlated parent result")
        if (
            parent_result.get("session_id") != self.coordinator_session_id
            or parent_result.get("invocation_id") != self.current_invocation
            or parent_result.get("message_id") != self.current_message_id
        ):
            raise SdkAdapterError("stale-generation", "native parent result correlation changed")
        terminal_watermark = self.watermark
        next_watermark = terminal_watermark + 1
        roster = self._coordinator_roster(
            seal_watermark=terminal_watermark,
            tool_evidence=tool_evidence,
            parent_state="idle",
        )
        proof = {
            "parent_result": copy.deepcopy(dict(parent_result)),
            "roster": roster,
            "roster_digest": _native_full_digest(roster),
            "observation_watermark": terminal_watermark,
            "uncertainty": [],
            "overflow": False,
        }
        response = {
            **binding,
            "state": "reserved",
            "terminal_watermark": terminal_watermark,
            "next_watermark": next_watermark,
            "terminal_proof": proof,
            "terminal_proof_digest": _native_full_digest(proof),
        }
        # Validate the assembled response before sealing.  A seal is never
        # left behind for a malformed or partially observed proof.
        response = _native_invocation_response(response, binding)
        self._invocation_reservation = response
        self._reservation_sealed = True
        return copy.deepcopy(response)

    def consume_invocation_reservation(
        self, reservation_binding: Mapping[str, Any]
    ) -> Optional[SdkAdapterError]:
        """Consume only the exact controller-committed reservation binding."""

        if self._invocation_reservation is None:
            return SdkAdapterError("stale-generation", "native invocation reservation is not outstanding")
        cached = self._invocation_reservation
        request = {key: cached[key] for key in _NATIVE_INVOCATION_BINDING_FIELDS}
        try:
            supplied = _native_invocation_response(reservation_binding, request)
        except SdkAdapterError as exc:
            return exc
        if any(supplied.get(key) != cached.get(key) for key in _NATIVE_INVOCATION_RESPONSE_FIELDS):
            return SdkAdapterError("stale-generation", "native reservation binding does not match the sealed reservation")
        reservation_id = str(cached["reservation_id"])
        if reservation_id in self._consumed_reservation_ids:
            return SdkAdapterError("busy", "native invocation reservation was already consumed")
        if len(self._consumed_reservation_ids) >= MAX_NATIVE_LIFECYCLE_EVENTS:
            return SdkAdapterError("busy", "native invocation reservation history is full")
        self._consumed_reservation_ids.add(reservation_id)
        self._invocation_reservation = None
        self._reservation_sealed = False
        return None

    def prepare_native_invocation(self, invocation_id: Any, message_id: Any = None) -> Optional[SdkAdapterError]:
        """Bind the actual durable mailbox ID before a native query."""

        return self.begin_invocation(invocation_id, message_id)

    def prepare_coordinator_interrupt(
        self,
        selection: Mapping[str, Any],
        *,
        participant_id: str,
        runner_instance_id: str,
        tool_evidence: Any = None,
        parent_state: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fence and seal a complete roster-derived coordinator intent."""

        self.coordinator_enabled = True
        expected = {
            "operation_id", "interrupt_id", "fence_epoch",
            "capability_digest", "request_epoch_id",
        }
        if not isinstance(selection, Mapping) or set(selection) != expected:
            raise SdkAdapterError(
                "invalid", "coordinator interrupt selection is malformed"
            )
        participant_id = _wire_id(participant_id, "participant_id")
        runner_instance_id = _wire_id(runner_instance_id, "runner_instance_id")
        interrupt_id = _wire_id(selection.get("interrupt_id"), "interrupt_id")
        operation_id = _wire_id(selection.get("operation_id"), "operation_id")
        request_epoch_id = _wire_id(selection.get("request_epoch_id"), "request_epoch_id")
        fence_epoch = selection.get("fence_epoch")
        if type(fence_epoch) is not int or fence_epoch <= 0:
            raise SdkAdapterError("invalid", "coordinator interrupt fence_epoch is invalid")
        capability_digest = selection.get("capability_digest")
        if not isinstance(capability_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", capability_digest):
            raise SdkAdapterError("invalid", "coordinator interrupt capability_digest is invalid")
        if interrupt_id in self._coordinator_interrupt_states:
            raise SdkAdapterError("busy", "coordinator interrupt ID already has a local transaction")
        identity, identity_error = self._validated_lineage_identity()
        if identity_error is not None:
            raise identity_error
        assert identity is not None
        if identity.get("runner_incarnation") != runner_instance_id:
            raise SdkAdapterError("stale-generation", "coordinator interrupt runner incarnation changed")
        if self.current_invocation is None:
            raise SdkAdapterError("unsupported", "coordinator interrupt has no current invocation")
        # Set the local admission/control fence before taking the first local
        # receipt watermark.  Any later refusal retains the fence.
        self._coordinator_interrupt_fenced = True
        self.watermark += 1
        request_entry_watermark = self.watermark
        roster_seal_watermark = self.watermark
        roster = self._coordinator_roster(
            seal_watermark=roster_seal_watermark,
            tool_evidence=tool_evidence,
            parent_state=parent_state,
        )
        projection = self._coordinator_roster_projection(roster)
        roster_identity_digest = _native_digest(projection)
        intent = {
            "type": "coordinator-interrupt-intent",
            "participant_id": participant_id,
            "session_id": self.coordinator_session_id,
            "runner_instance_id": runner_instance_id,
            "interrupt": {
                "interrupt_id": interrupt_id,
                "operation_id": operation_id,
                "owner_generation": identity["owner_generation"],
                "lineage_id": identity["lineage_id"],
                "lineage_generation": self._lineage_generation(),
                "invocation_id": self.current_invocation,
                "fence_epoch": fence_epoch,
                "roster_identity_digest": roster_identity_digest,
                "roster_seal_watermark": roster_seal_watermark,
                "capability_digest": capability_digest,
                "request_epoch_id": request_epoch_id,
                "request_entry_watermark": request_entry_watermark,
                "roster": roster,
            },
        }
        target = (
            identity["owner_generation"], identity["lineage_id"],
            self._lineage_generation(), runner_instance_id,
            self.current_invocation, fence_epoch, roster_identity_digest,
        )
        if target in self._coordinator_interrupt_targets:
            raise SdkAdapterError("busy", "coordinator interrupt source already has a local transaction")
        self._coordinator_interrupt_targets[target] = interrupt_id
        self._coordinator_interrupt_states[interrupt_id] = {
            "intent": copy.deepcopy(intent),
            "intent_digest": _native_digest(intent),
            "roster_projection": copy.deepcopy(projection),
            "roster": copy.deepcopy(roster),
            "target": target,
            "tool_evidence": tool_evidence,
            "phase": "intent-prepared",
            "intent_persisted": False,
            "authorized": False,
            "attempted": False,
            "runtime_evidence": None,
            "evidence_ids": set(),
        }
        return copy.deepcopy(intent)

    def mark_coordinator_interrupt_intent_persisted(
        self, interrupt_id: str, acknowledgement: Mapping[str, Any]
    ) -> None:
        interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        state = self._coordinator_interrupt_states.get(interrupt_id)
        if state is None:
            raise SdkAdapterError("unknown", "coordinator interrupt transaction is unknown")
        if (
            not isinstance(acknowledgement, Mapping)
            or acknowledgement.get("recorded") is not True
            or acknowledgement.get("interrupt_id") != interrupt_id
        ):
            raise SdkAdapterError("invalid", "coordinator interrupt intent acknowledgement was not recorded")
        state["intent_persisted"] = True
        state["authorized"] = acknowledgement.get("authorize_send") is True
        state["phase"] = "intent-authorized" if state["authorized"] else "intent-persisted"

    def coordinator_interrupt_intent_digest(self, interrupt_id: str) -> str:
        interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        state = self._coordinator_interrupt_states.get(interrupt_id)
        if state is None:
            raise SdkAdapterError("unknown", "coordinator interrupt transaction is unknown")
        return str(state["intent_digest"])

    def revalidate_coordinator_interrupt(self, interrupt_id: str, intent: Mapping[str, Any]) -> bool:
        interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        state = self._coordinator_interrupt_states.get(interrupt_id)
        if (
            self.error is not None
            or state is None
            or state.get("intent") != dict(intent)
            or not state.get("intent_persisted")
            or not state.get("authorized")
            or state.get("attempted")
            or not self._coordinator_interrupt_fenced
        ):
            return False
        body = intent.get("interrupt") if isinstance(intent, Mapping) else None
        if not isinstance(body, Mapping) or body.get("interrupt_id") != interrupt_id:
            return False
        identity, error = self._validated_lineage_identity()
        if error is not None or identity is None:
            return False
        if (
            identity.get("owner_generation") != body.get("owner_generation")
            or identity.get("lineage_id") != body.get("lineage_id")
            or identity.get("runner_incarnation") != intent.get("runner_instance_id")
            or self.current_invocation != body.get("invocation_id")
        ):
            return False
        sealed = state.get("roster")
        if not isinstance(sealed, Mapping):
            return False
        # The sealed inventory is historical.  Terminal completion may remove
        # active entries while the waiters are in flight, but a new member,
        # incarnation, tool, effect, or pending admission is a refusal.
        try:
            current = self._coordinator_roster(
                seal_watermark=max(self.watermark, int(body.get("roster_seal_watermark", 0))),
                tool_evidence=state.get("tool_evidence"),
            )
        except (SdkAdapterError, TypeError, ValueError):
            return False
        if current.get("parent_state") != sealed.get("parent_state"):
            return False
        sealed_children = {item["admission_id"]: item for item in sealed.get("children", ()) if isinstance(item, Mapping)}
        current_children = {item["admission_id"]: item for item in current.get("children", ()) if isinstance(item, Mapping)}
        if set(sealed_children) != set(current_children):
            return False
        for admission_id, old in sealed_children.items():
            now = current_children[admission_id]
            for key in (
                "tool_use_id", "agent_id", "task_id", "parent_agent_id",
                "invocation_id", "lineage_incarnation", "trusted_definition_digest",
            ):
                if now.get(key) != old.get(key):
                    return False
            if old.get("status") == "completed" and now.get("status") != "completed":
                return False
            if old.get("status") == "stopped" and now.get("status") == "active":
                return False
            for key in ("active_tool_ids", "uncertain_tool_ids", "unresolved_effect_ids"):
                if not set(now.get(key, ())).issubset(set(old.get(key, ()) )):
                    return False
        for key in (
            "parent_active_tool_ids", "parent_uncertain_tool_ids",
            "parent_unresolved_effect_ids", "descendant_ids",
        ):
            if not set(current.get(key, ())).issubset(set(sealed.get(key, ()) )):
                return False
        if current.get("pending_admission_ids") or current.get("pending_task_ids"):
            return False
        return True

    def mark_coordinator_interrupt_attempted(self, interrupt_id: str) -> None:
        interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        state = self._coordinator_interrupt_states.get(interrupt_id)
        if state is None or not state.get("authorized"):
            raise SdkAdapterError("stale-generation", "coordinator interrupt was not durably authorized")
        if state.get("attempted"):
            raise SdkAdapterError("busy", "coordinator interrupt SDK call has already been attempted")
        state["attempted"] = True
        state["phase"] = "sdk-attempted"

    def coordinator_interrupt_runtime_evidence(self, interrupt_id: str) -> dict[str, Any]:
        interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        state = self._coordinator_interrupt_states.get(interrupt_id)
        if state is None or not state.get("attempted"):
            raise SdkAdapterError("stale-generation", "coordinator interrupt SDK call was not attempted")
        if state.get("runtime_evidence") is not None:
            return copy.deepcopy(state["runtime_evidence"])
        intent = state["intent"]
        self.watermark += 1
        evidence = {
            "evidence_id": self._coordinator_evidence_id(interrupt_id, "runtime-ack"),
            "interrupt_id": interrupt_id,
            "kind": "runtime-ack",
            "observed_watermark": self.watermark,
            "data": {"accepted": True, "ack_kind": "accepted-interrupt"},
        }
        frame = {
            "type": "coordinator-interrupt-evidence",
            "participant_id": intent["participant_id"],
            "session_id": intent["session_id"],
            "runner_instance_id": intent["runner_instance_id"],
            "evidence": evidence,
        }
        state["runtime_evidence"] = copy.deepcopy(frame)
        state["evidence_ids"].add(evidence["evidence_id"])
        return frame

    def _coordinator_state(self, interrupt_id: Any) -> Optional[dict[str, Any]]:
        try:
            key = _wire_id(interrupt_id, "interrupt_id")
        except SdkAdapterError:
            return None
        state = self._coordinator_interrupt_states.get(key)
        return state if isinstance(state, dict) and state.get("intent_persisted") else None

    def _coordinator_frame(
        self,
        state: Mapping[str, Any],
        *,
        evidence_id: str,
        kind: str,
        observed_watermark: int,
        data: Mapping[str, Any],
    ) -> dict[str, Any]:
        intent = state["intent"]
        return {
            "type": "coordinator-interrupt-evidence",
            "participant_id": intent["participant_id"],
            "session_id": intent["session_id"],
            "runner_instance_id": intent["runner_instance_id"],
            "evidence": {
                "evidence_id": evidence_id,
                "interrupt_id": intent["interrupt"]["interrupt_id"],
                "kind": kind,
                "observed_watermark": observed_watermark,
                "data": copy.deepcopy(dict(data)),
            },
        }

    def _coordinator_terminal_frame_for_record(
        self, state: Mapping[str, Any], child: Mapping[str, Any]
    ) -> Optional[dict[str, Any]]:
        status = child.get("status")
        if status not in {"completed", "stopped"}:
            return None
        event_kind = "SubagentStop"
        event_uuid = None
        record = self.children.get(str(child.get("agent_id")))
        if isinstance(record, Mapping):
            provenance = record.get("stop_provenance")
            if isinstance(provenance, Mapping) and provenance.get("source") == "task_notification":
                event_kind = "task_notification"
                event_uuid = provenance.get("event_uuid")
            else:
                for fact in reversed(record.get("task_events", ())):
                    if isinstance(fact, Mapping) and fact.get("kind") == "tasknotification":
                        event_kind = "task_notification"
                        event_uuid = fact.get("event_uuid")
                        break
        terminal_watermark = child.get("terminal_watermark")
        if type(terminal_watermark) is not int:
            return None
        interrupt_id = state["intent"]["interrupt"]["interrupt_id"]
        evidence_id = self._coordinator_evidence_id(
            interrupt_id,
            "member-terminal",
            f"{child['agent_id']}:{child['task_id']}:{child['lineage_incarnation']}:{event_uuid or 'none'}",
        )
        return self._coordinator_frame(
            state,
            evidence_id=evidence_id,
            kind="member-terminal",
            observed_watermark=terminal_watermark,
            data={
                "agent_id": child["agent_id"],
                "task_id": child["task_id"],
                "tool_use_id": child["tool_use_id"],
                "lineage_incarnation": child["lineage_incarnation"],
                "event_kind": event_kind,
                "event_uuid": event_uuid,
                "status": status,
            },
        )

    @staticmethod
    def _coordinator_terminal_task_status(value: Any) -> Optional[str]:
        status = "" if value is None else str(value).casefold()
        if status in {"completed", "complete", "success", "done"}:
            return "completed"
        if status in {"failed", "failure", "error"}:
            return "failed"
        if status in {"stopped", "cancelled", "canceled", "terminated", "killed"}:
            return "stopped"
        return None

    def _coordinator_current_terminal_task_fact(
        self, record: Mapping[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Return the first authoritative terminal notification of this incarnation.

        ``SubagentStop`` is a hook fact about the child lifecycle.  It must not
        replace a current task notification's terminal status, event UUID, or
        watermark.  Task events are kept on the current child record, so the
        task/incarnation identity checks below also prevent a prior reused
        ``agent_id`` from supplying terminal evidence for this incarnation.
        """

        task_id = record.get("task_id")
        incarnation = record.get("lineage_incarnation")
        start_watermark = incarnation.get("start_watermark") if isinstance(incarnation, Mapping) else None
        if (
            not isinstance(task_id, str)
            or not task_id.strip()
            or type(start_watermark) is not int
            or record.get("task_terminal") is not True
        ):
            return None
        for fact in record.get("task_events", ()):
            if not isinstance(fact, Mapping) or fact.get("kind") != "tasknotification":
                continue
            if fact.get("authoritative") is False:
                continue
            if fact.get("validated") is not True:
                continue
            if str(fact.get("task_id")) != task_id:
                continue
            watermark = fact.get("watermark")
            if type(watermark) is not int or watermark <= start_watermark:
                continue
            status = self._coordinator_terminal_task_status(fact.get("status"))
            if status is None:
                continue
            event_uuid = fact.get("event_uuid")
            return {
                "status": status,
                "event_uuid": None if event_uuid is None else str(event_uuid),
                "watermark": watermark,
            }
        return None

    def _coordinator_subagent_stop_matches_current_record(
        self, record: Mapping[str, Any], event: Mapping[str, Any]
    ) -> bool:
        """Check the correlation that a SubagentStop hook can actually prove."""

        incarnation = record.get("lineage_incarnation")
        number = incarnation.get("number") if isinstance(incarnation, Mapping) else None
        if type(number) is not int:
            return False
        expected_agent = record.get("agent_id")
        event_agent = _native_value(event, "agent_id", "agentId")
        if event_agent is not None and (
            expected_agent is None or str(event_agent) != str(expected_agent)
        ):
            return False
        actual_path = _native_value(event, "agent_transcript_path", "agentTranscriptPath")
        transcript = record.get("transcript")
        known_path = transcript.get("child_path") if isinstance(transcript, Mapping) else None
        if actual_path is not None and known_path is not None and str(actual_path) != str(known_path):
            return False
        parent_links = record.get("parent_links")
        expected_task = record.get("task_id")
        event_task = _native_value(event, "task_id", "taskId")
        if event_task is not None and (
            expected_task is None or str(event_task) != str(expected_task)
        ):
            return False
        expected_invocation = (
            parent_links.get("invocation_id")
            if isinstance(parent_links, Mapping)
            else None
        )
        event_invocation = self._event_invocation(event)
        if event_invocation is not None and (
            expected_invocation is None or event_invocation != str(expected_invocation)
        ):
            return False
        current_tool = _native_value(event, "tool_use_id", "toolUseId")
        expected_tool = record.get("tool_use_id")
        if current_tool is not None and (
            expected_tool is None or str(current_tool) != str(expected_tool)
        ):
            return False
        current_prompt = _native_value(event, "prompt_id", "promptId")
        expected_prompt = (
            parent_links.get("prompt_id")
            if isinstance(parent_links, Mapping)
            else None
        )
        if (
            current_prompt is not None
            and expected_prompt is not None
            and str(current_prompt) != str(expected_prompt)
        ):
            return False
        for event_names, link_name in (
            (("parent_agent_id", "parentAgentId"), "parent_agent_id"),
            (("parent_task_id", "parentTaskId"), "parent_task_id"),
            (("parent_tool_use_id", "parentToolUseId"), "parent_tool_use_id"),
        ):
            supplied_link = _native_value(event, *event_names)
            expected_link = (
                parent_links.get(link_name)
                if isinstance(parent_links, Mapping)
                else None
            )
            if (
                supplied_link is not None
                and expected_link is not None
                and str(supplied_link) != str(expected_link)
            ):
                return False
        matching_tool = (
            current_tool is not None
            and expected_tool is not None
            and str(current_tool) == str(expected_tool)
        )
        matching_prompt = (
            current_prompt is not None
            and expected_prompt is not None
            and str(current_prompt) == str(expected_prompt)
        )
        if number == 1:
            return actual_path is not None or matching_tool or matching_prompt
        return bool(
            (event_invocation is not None and expected_invocation is not None
             and event_invocation == str(expected_invocation))
            or matching_tool
            or matching_prompt
        )

    def _coordinator_tool_terminal_frame(
        self, state: Mapping[str, Any], event: Mapping[str, Any], *, owner: Any = None
    ) -> Optional[dict[str, Any]]:
        kind = _native_event_kind(event)
        if kind not in {"posttooluse", "posttoolusefailure"}:
            return None
        tool_id = _native_value(event, "tool_use_id", "toolUseId", "id")
        if tool_id is None:
            return None
        tool_id = str(tool_id)
        agent_id = _native_value(event, "agent_id", "agentId")
        if owner is None and agent_id is not None:
            owner = str(agent_id)
        record = self.children.get(str(owner)) if owner is not None else None
        incarnation = None
        if isinstance(record, Mapping):
            incarnation_value = record.get("lineage_incarnation", {}).get("number")
            incarnation = incarnation_value if type(incarnation_value) is int else None
        roster = state.get("roster", {})
        parent_ids = set(roster.get("parent_active_tool_ids", ())) | set(
            roster.get("parent_uncertain_tool_ids", ())
        )
        child_matches = [
            child for child in roster.get("children", ())
            if isinstance(child, Mapping)
            and tool_id in set(child.get("active_tool_ids", ())) | set(child.get("uncertain_tool_ids", ()))
        ]
        if owner is None:
            if tool_id not in parent_ids:
                return None
        else:
            if len(child_matches) != 1 or child_matches[0].get("agent_id") != str(owner):
                return None
            if incarnation is None or child_matches[0].get("lineage_incarnation") != incarnation:
                return None
        status = "failed" if kind == "posttoolusefailure" else "completed"
        data = {
            "tool_use_id": tool_id,
            "agent_id": None if owner is None else str(owner),
            "lineage_incarnation": incarnation,
            "status": status,
        }
        interrupt_id = state["intent"]["interrupt"]["interrupt_id"]
        evidence_id = self._coordinator_evidence_id(
            interrupt_id, "tool-terminal", f"{tool_id}:{owner or 'parent'}"
        )
        observed_watermark = event.get("_coordinator_observed_watermark")
        if type(observed_watermark) is not int or observed_watermark <= 0:
            return None
        if observed_watermark <= int(state["intent"]["interrupt"]["roster_seal_watermark"]):
            return None
        return self._coordinator_frame(
            state,
            evidence_id=evidence_id,
            kind="tool-terminal",
            observed_watermark=observed_watermark,
            data=data,
        )

    def coordinator_interrupt_event_evidence(
        self, event: Mapping[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Derive one actual terminal fact after a live event or hook."""

        if not isinstance(event, Mapping):
            return None
        if self.error is not None:
            return None
        kind = _native_event_kind(event)
        state = None
        for candidate in self._coordinator_interrupt_states.values():
            if candidate.get("intent_persisted"):
                state = candidate
                break
        if state is None:
            return None
        interrupt_id = state["intent"]["interrupt"]["interrupt_id"]
        event_type = str(_get_ci(event, "type") or "").casefold()
        observed_watermark = event.get("_coordinator_observed_watermark")
        if type(observed_watermark) is not int or observed_watermark <= 0:
            return None
        seal_watermark = int(state["intent"]["interrupt"]["roster_seal_watermark"])
        if event_type in {
            "result", "message-stop", "turn-end", "turn-ended", "turn-complete",
            "done", "drained", "idle", "quiesced",
        }:
            if event.get("_coordinator_parent_observation") is not True:
                return None
            if any(
                _native_value(event, key) is not None
                for key in (
                    "agent_id", "agentId", "task_id", "taskId",
                    "parent_tool_use_id", "parentToolUseId",
                )
            ):
                return None
            correlated = True
            if not correlated or self.current_invocation is None:
                return None
            if observed_watermark <= seal_watermark:
                return None
            state_name = "idle" if event_type == "idle" else "drained"
            return self._coordinator_frame(
                state,
                evidence_id=self._coordinator_evidence_id(
                    interrupt_id, "parent-drained", self.current_invocation
                ),
                kind="parent-drained",
                observed_watermark=observed_watermark,
                data={"invocation_id": self.current_invocation, "state": state_name},
            )
        if kind in {"posttooluse", "posttoolusefailure"}:
            if observed_watermark <= seal_watermark:
                return None
            agent_id = _native_value(event, "agent_id", "agentId")
            return self._coordinator_tool_terminal_frame(
                state, event, owner=None if agent_id is None else str(agent_id)
            )
        if kind not in {"subagentstop", "tasknotification"}:
            return None
        record = None
        event_uuid = None
        if kind == "subagentstop":
            agent_id = _native_value(event, "agent_id", "agentId")
            record = self.children.get(str(agent_id)) if agent_id is not None else None
            if not isinstance(record, Mapping):
                return None
            if not self._coordinator_subagent_stop_matches_current_record(record, event):
                return None
            terminal_fact = self._coordinator_current_terminal_task_fact(record)
            current_status = record.get("status")
            if terminal_fact is not None:
                status = terminal_fact["status"]
                event_kind = "task_notification"
                observed_watermark = terminal_fact["watermark"]
                event_uuid = terminal_fact["event_uuid"]
            elif current_status == "completed":
                # A hook alone cannot turn a child into successful completion.
                return None
            elif current_status in {"stopped", "restart-pending", "resume-pending"}:
                status = "stopped"
                event_kind = "SubagentStop"
            else:
                return None
        else:
            task_id = _native_value(event, "task_id", "taskId")
            record, _error = self._task_record_for_event(event)
            if not isinstance(record, Mapping) or task_id is None or str(record.get("task_id")) != str(task_id):
                return None
            event_agent_id = _native_value(event, "agent_id", "agentId")
            if event_agent_id is not None and str(record.get("agent_id")) != str(event_agent_id):
                return None
            terminal_fact = self._coordinator_current_terminal_task_fact(record)
            if terminal_fact is None:
                return None
            status = terminal_fact["status"]
            event_uuid = terminal_fact["event_uuid"]
            observed_watermark = terminal_fact["watermark"]
            event_kind = "task_notification"
        if not isinstance(record, Mapping):
            return None
        agent_id = record.get("agent_id")
        task_id = record.get("task_id")
        tool_use_id = record.get("tool_use_id")
        incarnation = record.get("lineage_incarnation", {}).get("number")
        if any(not isinstance(value, str) or not value for value in (agent_id, task_id, tool_use_id)) or type(incarnation) is not int:
            return None
        sealed_children = state.get("roster", {}).get("children", ())
        if not any(
            isinstance(child, Mapping)
            and child.get("agent_id") == str(agent_id)
            and child.get("task_id") == str(task_id)
            and child.get("lineage_incarnation") == incarnation
            for child in sealed_children
        ):
            return None
        evidence_id = self._coordinator_evidence_id(
            interrupt_id, "member-terminal", f"{agent_id}:{task_id}:{incarnation}:{event_uuid or 'none'}"
        )
        return self._coordinator_frame(
            state,
            evidence_id=evidence_id,
            kind="member-terminal",
            observed_watermark=observed_watermark,
            data={
                "agent_id": str(agent_id),
                "task_id": str(task_id),
                "tool_use_id": str(tool_use_id),
                "lineage_incarnation": incarnation,
                "event_kind": event_kind,
                "event_uuid": None if event_uuid is None else str(event_uuid),
                "status": status,
            },
        )

    def coordinator_interrupt_evidence_frames(
        self, interrupt_id: str, *, tool_evidence: Any = None
    ) -> list[dict[str, Any]]:
        """Return independent facts already observed at/after intent seal."""

        interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        state = self._coordinator_state(interrupt_id)
        if state is None:
            return []
        frames: list[dict[str, Any]] = []
        seen = state["evidence_ids"]
        intent = state["intent"]["interrupt"]
        def add(frame: Optional[dict[str, Any]]) -> None:
            if not isinstance(frame, Mapping):
                return
            evidence = frame.get("evidence")
            evidence_id = evidence.get("evidence_id") if isinstance(evidence, Mapping) else None
            if not isinstance(evidence_id, str) or evidence_id in seen:
                return
            seen.add(evidence_id)
            frames.append(copy.deepcopy(dict(frame)))

        self.watermark = max(self.watermark, int(intent["roster_seal_watermark"]))
        add(self._coordinator_frame(
            state,
            evidence_id=self._coordinator_evidence_id(interrupt_id, "request-observation"),
            kind="request-observation",
            observed_watermark=self.watermark,
            data={
                "epoch_id": intent["request_epoch_id"],
                "entry_watermark": intent["request_entry_watermark"],
                "through_watermark": self.watermark,
                "new_requests": None,
                "observable": False,
            },
        ))
        for child in intent["roster"]["children"]:
            add(self._coordinator_frame(
                state,
                evidence_id=self._coordinator_evidence_id(
                    interrupt_id, "admission-closed", child["admission_id"]
                ),
                kind="admission-closed",
                observed_watermark=self.watermark,
                data={"admission_id": child["admission_id"], "closed": True},
            ))
            add(self._coordinator_terminal_frame_for_record(state, child))
        for event in list(self._coordinator_fact_events):
            add(self.coordinator_interrupt_event_evidence(event))
        return frames

    @staticmethod
    def _native_stop_ids(value: Any, label: str) -> list[str]:
        if not isinstance(value, list) or len(value) > MAX_NATIVE_PROGRESS_EVENTS:
            raise SdkAdapterError("unsupported", f"native stop {label} observation is unavailable")
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str) or not item.strip() or len(item) > 256:
                raise SdkAdapterError("uncertain-effect", f"native stop {label} contains an unbounded ID")
            item = item.strip()
            if item in seen:
                raise SdkAdapterError("uncertain-effect", f"native stop {label} contains a duplicate ID")
            seen.add(item)
            result.append(item)
        return result

    def _native_stop_observed_arrays(
        self,
        record: Mapping[str, Any],
        *,
        event: Mapping[str, Any] | None = None,
    ) -> dict[str, list[str]]:
        """Return only arrays backed by an observed ledger fact.

        An empty array is valid after the corresponding hook/effect stream has
        actually been observed.  Before that point the field is omitted so a
        missing observation cannot become a fabricated quiescence claim.
        """

        supplied = None
        if isinstance(event, Mapping):
            candidate = _native_value(event, "observation")
            if isinstance(candidate, Mapping):
                supplied = candidate
        result: dict[str, list[str]] = {}
        if record.get("_tool_observation_known") is True:
            active = [
                str(item.get("tool_use_id"))
                for item in record.get("tool_events", {}).get("active", ())
                if isinstance(item, Mapping) and item.get("tool_use_id") is not None
            ]
            uncertain = [
                str(item.get("tool_use_id"))
                for item in record.get("tool_events", {}).get("uncertain", ())
                if isinstance(item, Mapping) and item.get("tool_use_id") is not None
            ]
            if len(uncertain) != len(record.get("tool_events", {}).get("uncertain", ())):
                raise SdkAdapterError(
                    "uncertain-effect",
                    "native stop tool uncertainty lacks an actual tool ID",
                )
            result["active_tool_ids"] = self._native_stop_ids(active, "active_tool_ids")
            result["uncertain_tool_ids"] = self._native_stop_ids(uncertain, "uncertain_tool_ids")
        if record.get("_effect_observation_known") is True:
            effects = record.get("effect_events", {})
            unresolved = effects.get("unresolved", ()) if isinstance(effects, Mapping) else ()
            result["unresolved_effect_ids"] = self._native_stop_ids(
                [str(value) for value in unresolved],
                "unresolved_effect_ids",
            )
        # A terminal SDK notification may carry an independently observed
        # array.  Prefer it for that field, but never fill an omitted field.
        if supplied is not None:
            for key in ("active_tool_ids", "uncertain_tool_ids", "unresolved_effect_ids"):
                if key in supplied:
                    result[key] = self._native_stop_ids(supplied[key], key)
        return result

    def _native_stop_admission(self, record: Mapping[str, Any]) -> dict[str, Any]:
        admission_context = record.get("admission_context")
        admission_id = (
            admission_context.get("admission_id")
            if isinstance(admission_context, Mapping)
            else None
        )
        if not isinstance(admission_id, str) or not admission_id.strip():
            raise SdkAdapterError("unsupported", "native stop child has no durable admission ID")
        matches = [
            admission
            for admission in self.admissions
            if admission.get("admission_id") == admission_id
        ]
        if len(matches) != 1:
            raise SdkAdapterError("ownership-conflict", "native stop has no unique durable admission")
        return matches[0]

    @staticmethod
    def _native_stop_target_key(stop: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            stop["owner_generation"],
            stop["lineage_id"],
            stop["runner_instance_id"],
            stop["invocation_id"],
            stop["agent_id"],
            stop["task_id"],
            stop["tool_use_id"],
            stop["lineage_incarnation"],
        )

    @staticmethod
    def _native_stop_evidence_id(stop_id: str, kind: str, event_uuid: Any = None) -> str:
        suffix = kind if event_uuid is None else f"{kind}:{event_uuid}"
        candidate = f"{stop_id}:{suffix}"
        if len(candidate) <= 256 and "\x00" not in candidate:
            return candidate
        digest = hashlib.sha256(candidate.encode("utf-8", "replace")).hexdigest()
        return f"native-{kind}-{digest}"

    def _native_stop_record_for_task(self, task_id: str) -> dict[str, Any]:
        matches = [
            record
            for record in self.children.values()
            if record.get("task_id") is not None and str(record.get("task_id")) == task_id
        ]
        if len(matches) != 1:
            raise SdkAdapterError("ownership-conflict", "native stop task ID is not uniquely current")
        return matches[0]

    def prepare_native_stop(
        self,
        selection: Mapping[str, Any],
        *,
        participant_id: str,
        runner_instance_id: str,
    ) -> dict[str, Any]:
        """Fence and derive one stop intent from the current task ledger."""

        if not isinstance(selection, Mapping) or set(selection) != {"task_id", "stop_id"}:
            raise SdkAdapterError("invalid", "native stop selects only task_id and stop_id")
        task_id = _wire_id(selection.get("task_id"), "task_id")
        stop_id = _wire_id(selection.get("stop_id"), "stop_id")
        participant_id = _wire_id(participant_id, "participant_id")
        runner_instance_id = _wire_id(runner_instance_id, "runner_instance_id")
        if stop_id in self._native_stop_states:
            raise SdkAdapterError("busy", "native stop ID already has an in-process transaction")
        record = self._native_stop_record_for_task(task_id)
        if record.get("native_stop_pending") is not None:
            raise SdkAdapterError("busy", "native task already has an unresolved stop")
        if record.get("status") not in _NATIVE_ACTIVE_STATUSES or record.get("task_terminal") is not False:
            raise SdkAdapterError("stale-generation", "native stop target is no longer active")
        if self.current_invocation is None:
            raise SdkAdapterError("unsupported", "native stop target has no current invocation")
        admission = self._native_stop_admission(record)
        identity, identity_error = self._validated_lineage_identity()
        if identity_error is not None:
            raise identity_error
        assert identity is not None
        if str(identity["runner_incarnation"]) != runner_instance_id:
            raise SdkAdapterError("stale-generation", "native stop runner incarnation changed")
        invocation_id = record.get("parent_links", {}).get("invocation_id")
        if invocation_id != self.current_invocation:
            raise SdkAdapterError("stale-generation", "native stop target is outside the current invocation")
        actual_task_id = record.get("task_id")
        tool_use_id = record.get("tool_use_id")
        agent_id = record.get("agent_id")
        if any(not isinstance(value, str) or not value.strip() for value in (actual_task_id, tool_use_id, agent_id)):
            raise SdkAdapterError("unsupported", "native stop target lacks observed task, agent, or launch IDs")
        incarnation = record.get("lineage_incarnation")
        if not isinstance(incarnation, Mapping) or type(incarnation.get("number")) is not int or incarnation["number"] <= 0:
            raise SdkAdapterError("unsupported", "native stop target lacks a bounded child incarnation")
        start_watermark = incarnation.get("start_watermark")
        admission_watermark = admission.get("watermark")
        observed_watermark = self.watermark
        if (
            type(start_watermark) is not int
            or start_watermark <= 0
            or type(admission_watermark) is not int
            or admission_watermark <= 0
            or type(observed_watermark) is not int
            or observed_watermark <= 0
            or start_watermark <= admission_watermark
            or observed_watermark < start_watermark
        ):
            raise SdkAdapterError("stale-generation", "native stop watermarks are not current")
        task_events = [
            event
            for event in record.get("task_events", ())
            if isinstance(event, Mapping) and event.get("kind") == "taskstarted"
        ]
        if len(task_events) != 1:
            raise SdkAdapterError("unsupported", "native stop target lacks one observed task start event")
        task_start = task_events[0]
        task_watermark = task_start.get("watermark")
        if type(task_watermark) is not int or task_watermark <= admission_watermark or task_watermark > observed_watermark:
            raise SdkAdapterError("stale-generation", "native stop task start watermark is not current")
        task_type = task_start.get("task_type") or record.get("task_type") or "unknown"
        if not isinstance(task_type, str) or not task_type.strip() or len(task_type) > 256:
            raise SdkAdapterError("unsupported", "native stop task type is unavailable")
        trusted_digest = admission.get("trusted_definition_digest")
        if not isinstance(trusted_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", trusted_digest):
            raise SdkAdapterError("unsupported", "native stop definition digest is unavailable")
        observation = {
            "status": "active",
            "task_terminal": False,
            "start_watermark": start_watermark,
            "task_start_event": {
                "event_uuid": task_start.get("event_uuid"),
                "watermark": task_watermark,
                "task_type": task_type,
            },
        }
        observation.update(self._native_stop_observed_arrays(record))
        stop = {
            "stop_id": stop_id,
            "owner_generation": identity["owner_generation"],
            "lineage_id": identity["lineage_id"],
            "invocation_id": invocation_id,
            "admission_id": admission["admission_id"],
            "tool_use_id": str(tool_use_id),
            "agent_id": str(agent_id),
            "task_id": str(actual_task_id),
            "lineage_incarnation": incarnation["number"],
            "trusted_definition_digest": trusted_digest,
            "observed_watermark": observed_watermark,
            "observation": observation,
        }
        target_key = self._native_stop_target_key({**stop, "runner_instance_id": runner_instance_id})
        if target_key in self._native_stop_targets:
            raise SdkAdapterError("busy", "native task incarnation already has an in-process stop")
        intent = {
            "type": "native-stop-intent",
            "participant_id": participant_id,
            "session_id": self.coordinator_session_id,
            "runner_instance_id": runner_instance_id,
            "stop": stop,
        }
        record["native_stop_pending"] = stop_id
        # Keep the durable stop transaction separate from the last observed
        # SDK task status.  A later nonterminal task update may report the
        # same identity as active while this stop remains fenced.
        self._native_stop_fenced = True
        self._native_stop_states[stop_id] = {
            "intent": copy.deepcopy(intent),
            "record": record,
            "target_key": target_key,
            "phase": "intent-prepared",
            "intent_persisted": False,
            "attempted": False,
            "runtime_evidence": None,
            "terminal_evidence": None,
        }
        self._native_stop_targets[target_key] = stop_id
        return copy.deepcopy(intent)

    def mark_native_stop_intent_persisted(self, stop_id: str, acknowledgement: Mapping[str, Any]) -> None:
        stop_id = _wire_id(stop_id, "stop_id")
        state = self._native_stop_states.get(stop_id)
        if state is None:
            raise SdkAdapterError("unknown", "native stop transaction is unknown")
        if not isinstance(acknowledgement, Mapping) or acknowledgement.get("recorded") is not True:
            raise SdkAdapterError("invalid", "native stop intent acknowledgement was not recorded")
        if acknowledgement.get("stop_id") != stop_id:
            raise SdkAdapterError("stale-generation", "native stop intent acknowledgement changed stop ID")
        state["intent_persisted"] = True
        state["phase"] = "intent-persisted"

    def revalidate_native_stop(self, stop_id: str, intent: Mapping[str, Any]) -> bool:
        stop_id = _wire_id(stop_id, "stop_id")
        state = self._native_stop_states.get(stop_id)
        if self.error is not None or state is None or state.get("intent") != dict(intent) or not state.get("intent_persisted"):
            return False
        record = state.get("record")
        stop = intent.get("stop") if isinstance(intent, Mapping) else None
        if not isinstance(record, Mapping) or not isinstance(stop, Mapping):
            return False
        current = self.children.get(str(record.get("agent_id")))
        if current is not record or current.get("native_stop_pending") != stop_id:
            return False
        if current.get("task_terminal") is not False or current.get("status") not in _NATIVE_ACTIVE_STATUSES:
            return False
        if current.get("task_id") != stop.get("task_id") or current.get("tool_use_id") != stop.get("tool_use_id"):
            return False
        if self.current_invocation != stop.get("invocation_id"):
            return False
        identity, error = self._validated_lineage_identity()
        if error is not None or identity is None:
            return False
        return (
            identity.get("owner_generation") == stop.get("owner_generation")
            and identity.get("lineage_id") == stop.get("lineage_id")
            and identity.get("runner_incarnation") == intent.get("runner_instance_id")
            and state.get("target_key") == self._native_stop_target_key({**dict(stop), "runner_instance_id": intent.get("runner_instance_id")})
        )

    def mark_native_stop_attempted(self, stop_id: str) -> None:
        stop_id = _wire_id(stop_id, "stop_id")
        state = self._native_stop_states.get(stop_id)
        if state is None or not state.get("intent_persisted"):
            raise SdkAdapterError("stale-generation", "native stop was not durably authorized")
        if state.get("attempted"):
            raise SdkAdapterError("busy", "native stop SDK call has already been attempted")
        state["attempted"] = True
        state["phase"] = "sdk-attempted"

    def native_stop_pending_terminal_evidence(self, stop_id: str) -> Optional[dict[str, Any]]:
        stop_id = _wire_id(stop_id, "stop_id")
        state = self._native_stop_states.get(stop_id)
        if state is None or not state.get("intent_persisted"):
            return None
        frame = state.get("terminal_evidence")
        return None if frame is None else copy.deepcopy(frame)

    def native_stop_runtime_evidence(self, stop_id: str) -> dict[str, Any]:
        stop_id = _wire_id(stop_id, "stop_id")
        state = self._native_stop_states.get(stop_id)
        if state is None or not state.get("attempted"):
            raise SdkAdapterError("stale-generation", "native stop SDK call was not attempted")
        if state.get("runtime_evidence") is not None:
            return copy.deepcopy(state["runtime_evidence"])
        intent = state["intent"]
        stop = intent["stop"]
        evidence = {
            "evidence_id": self._native_stop_evidence_id(stop_id, "runtime-ack"),
            "stop_id": stop_id,
            "kind": "runtime-ack",
            "agent_id": stop["agent_id"],
            "task_id": stop["task_id"],
            "lineage_incarnation": stop["lineage_incarnation"],
            "observed_watermark": stop["observed_watermark"],
            "accepted": True,
            "ack_kind": "accepted-stop",
        }
        frame = {
            "type": "native-stop-evidence",
            "participant_id": intent["participant_id"],
            "session_id": intent["session_id"],
            "runner_instance_id": intent["runner_instance_id"],
            "evidence": evidence,
        }
        state["runtime_evidence"] = copy.deepcopy(frame)
        return frame

    def native_stop_terminal_evidence(self, event: Mapping[str, Any]) -> Optional[dict[str, Any]]:
        # Only the authoritative task notification can close the runtime
        # portion of a native stop.  A task update, SDK ACK, or aliased
        # terminal status is not a task notification fact.
        if _native_event_kind(event) != "tasknotification":
            return None
        status = _native_value(event, "status")
        if status is None or str(status).casefold() != "stopped":
            return None
        task_id = _native_value(event, "task_id", "taskId")
        if task_id is None:
            return None
        try:
            record = self._native_stop_record_for_task(str(task_id))
        except SdkAdapterError:
            return None
        stop_id = record.get("native_stop_pending")
        state = self._native_stop_states.get(stop_id) if isinstance(stop_id, str) else None
        if state is None:
            return None
        if state.get("terminal_evidence") is not None:
            return None
        event_uuid = _native_value(event, "uuid", "event_uuid", "eventUuid")
        event_tool_use_id = _native_value(event, "tool_use_id", "toolUseId")
        matched_facts = [
            fact
            for fact in record.get("task_events", ())
            if (
                isinstance(fact, Mapping)
                and fact.get("kind") == "tasknotification"
                and str(fact.get("task_id")) == str(task_id)
                and str(fact.get("status")).casefold() == "stopped"
                and (
                    (event_uuid is None and fact.get("event_uuid") is None)
                    or (event_uuid is not None and fact.get("event_uuid") == event_uuid)
                )
                and (
                    event_tool_use_id is None
                    or str(fact.get("tool_use_id")) == str(event_tool_use_id)
                )
            )
        ]
        if len(matched_facts) != 1:
            return None
        terminal_fact = matched_facts[0]
        terminal_watermark = terminal_fact.get("watermark")
        if (
            record.get("task_terminal") is not True
            or type(terminal_watermark) is not int
            or terminal_watermark <= state["intent"]["stop"]["observed_watermark"]
        ):
            return None
        agent_id = _native_value(event, "agent_id", "agentId")
        if agent_id is not None and str(agent_id) != str(record.get("agent_id")):
            return None
        tool_use_id = _native_value(event, "tool_use_id", "toolUseId")
        if tool_use_id is not None and str(tool_use_id) != str(record.get("tool_use_id")):
            return None
        intent = state["intent"]
        stop = intent["stop"]
        observation = {"task_terminal": True}
        observation.update(self._native_stop_observed_arrays(record, event=event))
        evidence = {
            "evidence_id": self._native_stop_evidence_id(stop_id, "terminal", event_uuid),
            "stop_id": stop_id,
            "kind": "terminal",
            "agent_id": stop["agent_id"],
            "task_id": stop["task_id"],
            "lineage_incarnation": stop["lineage_incarnation"],
            "observed_watermark": terminal_watermark,
            "event_kind": "task_notification",
            "event_uuid": event_uuid,
            "status": "stopped",
            "tool_use_id": record["tool_use_id"],
            "observation": observation,
        }
        frame = {
            "type": "native-stop-evidence",
            "participant_id": intent["participant_id"],
            "session_id": intent["session_id"],
            "runner_instance_id": intent["runner_instance_id"],
            "evidence": evidence,
        }
        state["terminal_evidence"] = copy.deepcopy(frame)
        return frame

    def observe(self, event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        if self.error is not None:
            return self.error
        if not isinstance(event, Mapping):
            return self._fail("invalid", "native lifecycle event must be an object")
        if self._reservation_sealed:
            event_invocation = self._event_invocation(event)
            if event_invocation is None or event_invocation == self.current_invocation:
                return SdkAdapterError(
                    "stale-generation",
                    "native lifecycle event arrived after invocation reservation",
                )
            return SdkAdapterError(
                "stale-generation", "native lifecycle event belongs to the retired invocation"
            )
        kind = _native_event_kind(event)
        if kind == "pretooluse":
            name = _native_value(event, "tool_name", "toolName", "name")
            if name is not None and str(name).casefold() in _NATIVE_CHILD_TOOL_NAMES:
                tool_id = _native_value(event, "tool_use_id", "toolUseId", "id")
                if tool_id is not None and str(tool_id) in self.pending_admissions:
                    # The native hook has already completed the durable
                    # admission; the stream copy is an explicit cross-source
                    # duplicate and must not be processed a second time.
                    return None
                return self._fail(
                    "unsupported",
                    "native Agent/Task PreToolUse must be admitted through the async hook boundary",
                    event,
                )
            return self._observe_child_tool("pretooluse", event)
        if kind in {"posttooluse", "posttoolusefailure"}:
            name = _native_value(event, "tool_name", "toolName", "name")
            if name is not None and str(name).casefold() in _NATIVE_CHILD_TOOL_NAMES:
                return self._observe_agent_tool_end(kind, event)
            return self._observe_child_tool(kind, event)
        if kind == "subagentstart":
            return self._observe_subagent_start(event)
        if kind == "subagentstop":
            return self._observe_subagent_stop(event)
        if kind in {"taskstarted", "taskprogress", "tasknotification", "taskupdated"}:
            return self._observe_task_event(kind, event)
        return None

    def mark_released(self) -> Optional[SdkAdapterError]:
        if self.error is not None:
            return self.error
        if not self.ready_for_hold:
            return self._fail("uncertain-effect", "native child ledger is not ready for release")
        self.released = True
        return None

    def can_release(self) -> Optional[SdkAdapterError]:
        if self.error is not None:
            return self.error
        if not self.quiescent:
            return self._fail("uncertain-effect", "release blocked by active or unresolved native child state")
        return None

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "coordinator_session_id": self.coordinator_session_id,
            "lineage_context": dict(self._lineage_identity()),
            "event_cursor": self.runtime_cursor if self.runtime_cursor is not None else self.watermark,
            "current_invocation": self.current_invocation,
            "native_invocation_reservation": self.invocation_reservation,
            "coordinator_interrupt_fenced": self._coordinator_interrupt_fenced,
            "parent_state": {
                "observed": self._parent_state_observed,
                "active": self._parent_active,
                "drained": self._parent_drained,
            },
            "coordinator_interrupts": [
                {
                    "interrupt_id": interrupt_id,
                    "phase": state.get("phase"),
                    "intent_persisted": bool(state.get("intent_persisted")),
                    "authorized": bool(state.get("authorized")),
                    "attempted": bool(state.get("attempted")),
                }
                for interrupt_id, state in self._coordinator_interrupt_states.items()
            ],
            "released": self.released,
            "startup_violation": self.startup_violation,
            "ready_for_hold": self.ready_for_hold,
            "quiescent": self.quiescent,
            "admissions": list(self.admissions),
            "children": [dict(record) for record in self.children.values()],
            "child_history": list(self.child_history),
            "pending_admissions": [
                {
                    "admission_id": value.get("admission_id"),
                    "tool_use_id": value.get("tool_use_id"),
                    "tool_name": value.get("tool_name"),
                    "agent_type": value.get("agent_type"),
                    "parent": {
                        "session_id": self.coordinator_session_id,
                        "agent_id": value.get("parent_agent_id"),
                        "invocation_id": value.get("invocation_id"),
                        "prompt_id": value.get("prompt_id"),
                    },
                    "invocation_id": value.get("invocation_id"),
                    "watermark": value.get("admission_watermark"),
                    "custom_definition": value.get("custom_definition"),
                    "policy": value.get("policy"),
                    "policy_digest": value.get("policy_digest"),
                    "launch_completed": value.get("launch_completed"),
                }
                for value in self.pending_admissions.values()
            ],
            "pending_tasks": list(self.pending_tasks.values()),
            "lifecycle": list(self.lifecycle),
            "uncertainty": list(self.uncertainties),
            "overflow": self.overflow,
            "error": None if self.error is None else self.error.as_dict(),
        }


class _ToolEvidence:
    """Bounded evidence ledger for supported tool hook events."""

    def __init__(self) -> None:
        self.active: dict[str, dict[str, Any]] = {}
        self.completed: list[dict[str, Any]] = []
        self.uncertain: list[dict[str, Any]] = []
        self.rejections: list[dict[str, Any]] = []
        self.completed_count = 0
        self.uncertain_count = 0
        self.rejection_count = 0
        self.evidence_overflow = False
        # Ownership is kept out of the public snapshot for compatibility with
        # existing evidence consumers.  The coordinator roster uses it to
        # distinguish parent tools from child tools; an unknown owner is never
        # silently classified as parent work.
        self._owners: dict[str, Optional[str]] = {}
        self._unknown_owners: set[str] = set()
        self._completed_owners: dict[str, Optional[str]] = {}

    @property
    def quiescent(self) -> bool:
        return not self.active and not self.uncertain and not self.evidence_overflow

    def _reject(self, reason: str, detail: Mapping[str, Any]) -> None:
        item = {"reason": reason, **dict(detail)}
        self.rejection_count += 1
        self.uncertain_count += 1
        if len(self.rejections) < MAX_UNCERTAIN_TOOL_EVIDENCE:
            self.rejections.append(item)
        if len(self.uncertain) < MAX_UNCERTAIN_TOOL_EVIDENCE:
            self.uncertain.append(item)
        else:
            # Do not evict an older uncertainty to make room for a new one.
            # The overflow flag is itself a durable refusal condition.
            self.evidence_overflow = True

    @staticmethod
    def _tool_input(event: Mapping[str, Any]) -> dict[str, Any]:
        data = _merged_event_data(event)
        value = _get_ci(data, "tool_input", "toolInput", "input")
        return dict(value) if isinstance(value, Mapping) else {}

    @staticmethod
    def _tool_name(event: Mapping[str, Any]) -> Optional[str]:
        data = _merged_event_data(event)
        value = _get_ci(data, "tool_name", "toolName", "name")
        if value is None:
            content = _get_ci(event, "content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, Mapping) and str(block.get("type", "")).lower() in {"tool_use", "tooluse"}:
                        value = block.get("name")
                        if value is not None:
                            break
        return None if value is None else str(value)

    @staticmethod
    def _tool_id(event: Mapping[str, Any]) -> Optional[str]:
        data = _merged_event_data(event)
        value = _get_ci(data, "tool_use_id", "toolUseId", "id")
        if value is None:
            content = _get_ci(event, "content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, Mapping) and str(block.get("type", "")).lower() in {"tool_use", "tooluse"}:
                        value = block.get("id")
                        if value is not None:
                            break
        return None if value is None else str(value)

    def observe(self, event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        data = _merged_event_data(event)
        typ = str(_get_ci(event, "type") or "").lower()
        if typ in {"descendant", "process", "effect", "external-effect", "external_effect"}:
            owned = _get_ci(data, "owned", "owned_by_runner", "ownedByRunner")
            detached = _get_ci(data, "detached", "unknown", "unresolved")
            if owned is False or detached is True or str(detached).lower() in {"true", "1", "yes"}:
                self._reject(
                    "unknown-process-or-effect",
                    {"type": typ, "detail": dict(data)},
                )
                return SdkAdapterError(
                    "uncertain-effect",
                    "runner observed an unknown descendant or external effect",
                )
        phase = str(
            _get_ci(event, "hook_event", "hook_event_name", "hookEventName")
            or _get_ci(data, "hook_event", "hook_event_name", "hookEventName")
            or ""
        )
        subtype = str(_get_ci(event, "subtype") or _get_ci(data, "subtype") or "")
        if not phase and subtype.lower() in {"pretooluse", "posttooluse", "posttoolusefailure"}:
            phase = subtype
        if not phase and typ in {"pretooluse", "posttooluse", "posttoolusefailure"}:
            phase = typ
        phase_fold = phase.casefold()
        name = self._tool_name(event)
        tool_id = self._tool_id(event)
        tool_input = self._tool_input(event)

        # Assistant tool-use blocks are useful fake-runtime evidence even when
        # hook events are not enabled.  They prove intent, not completion.
        if not phase and name and tool_id:
            phase_fold = "pretooluse"

        if phase_fold == "pretooluse":
            lname = (name or "").casefold()
            if lname in _UNSUPPORTED_TOOL_NAMES:
                self._reject("native-team", {"tool_name": name, "tool_use_id": tool_id})
                return SdkAdapterError("unsupported", f"native team tool {name!r} is unsupported")
            detached = False
            # Native Agent/Task background execution is admitted only by the
            # lifecycle ledger.  A background flag by itself remains unsafe;
            # shell/detached requests keep the old refusal path.
            if lname not in _NATIVE_CHILD_TOOL_NAMES:
                for key, value in tool_input.items():
                    if str(key) in _DETACHED_INPUT_KEYS and (value is True or str(value).lower() in {"1", "true", "yes", "on"}):
                        detached = True
                        break
                command = _first_nonempty(tool_input.get("command"), tool_input.get("cmd"), tool_input.get("script"))
                if isinstance(command, str) and re.search(r"(?:^|[;&|\s])(setsid|nohup|disown)(?:\s|$)", command):
                    detached = True
            if detached:
                self._reject("detached-process", {"tool_name": name, "tool_use_id": tool_id})
                return SdkAdapterError("unsupported", f"detached/background tool request {name!r} is unsupported")
            if not tool_id:
                self._reject("missing-tool-id", {"tool_name": name})
                return SdkAdapterError("uncertain-effect", f"tool {name!r} has no durable tool-use ID")
            owner = _get_ci(event, "agent_id", "agentId")
            owner = None if owner is None else str(owner)
            if owner is not None and not owner.strip():
                owner = None
            self._owners[tool_id] = owner
            if owner is not None and owner == "<unknown>":
                self._unknown_owners.add(tool_id)
            if tool_id not in self.active and len(self.active) >= MAX_UNCERTAIN_TOOL_EVIDENCE:
                self.evidence_overflow = True
                self._reject("active-tool-evidence-overflow", {"tool_name": name, "tool_use_id": tool_id})
                return SdkAdapterError("uncertain-effect", "active tool evidence exceeds the bounded ledger")
            self.active[tool_id] = {"tool_name": name, "tool_use_id": tool_id, "started": True}
            return None

        if phase_fold in {"posttooluse", "posttoolusefailure"}:
            if not tool_id:
                self._reject("missing-tool-id", {"tool_name": name, "phase": phase})
                return SdkAdapterError("uncertain-effect", "tool completion has no durable tool-use ID")
            item = self.active.pop(tool_id, None)
            if item is None:
                self._reject("completion-without-start", {"tool_name": name, "tool_use_id": tool_id, "phase": phase})
                return SdkAdapterError("uncertain-effect", f"tool {tool_id!r} completed without a tracked start")
            item.update({"ended": True, "failure": phase_fold == "posttoolusefailure"})
            owner = self._owners.get(tool_id)
            self._completed_owners[tool_id] = owner
            self.completed_count += 1
            if len(self.completed) >= MAX_COMPLETED_TOOL_EVIDENCE:
                # Completed lifecycle facts are historical summaries.  They
                # may be evicted oldest-first once their bounded diagnostic
                # window is full; active and uncertain effects are kept in
                # their separate non-evicting ledgers above.
                del self.completed[: len(self.completed) - MAX_COMPLETED_TOOL_EVIDENCE + 1]
            self.completed.append(item)
            if phase_fold == "posttoolusefailure":
                interrupted = _get_ci(data, "is_interrupt", "isInterrupt", "interrupted")
                error_text = str(_get_ci(data, "error", "message") or "").casefold()
                if interrupted is True or any(token in error_text for token in ("interrupt", "abort", "cancel")):
                    self._reject(
                        "interrupted-tool-effect",
                        {"tool_name": name, "tool_use_id": tool_id},
                    )
        return None

    def snapshot(self) -> dict[str, Any]:
        return {
            "active": list(self.active.values()),
            "completed": list(self.completed),
            "uncertain": list(self.uncertain),
            "rejections": list(self.rejections),
            "quiescent": self.quiescent,
            "completed_count": self.completed_count,
            "uncertain_count": self.uncertain_count,
            "rejection_count": self.rejection_count,
            "evidence_overflow": self.evidence_overflow,
        }


def _hook_input_event(value: Any, tool_use_id: Any, phase: str) -> dict[str, Any]:
    """Adapt an official hook callback input to the evidence event shape."""

    if isinstance(value, Mapping):
        event = dict(value)
    elif dataclasses.is_dataclass(value):
        try:
            event = dataclasses.asdict(value)
        except (TypeError, ValueError):
            event = _event_to_mapping(value)
    else:
        event = _event_to_mapping(value)
    event.setdefault("hook_event_name", phase)
    if tool_use_id is not None:
        event.setdefault("tool_use_id", tool_use_id)
    return event


def _build_guard_hooks(
    sdk_module: Any,
    tool_evidence: _ToolEvidence,
    hook_error: dict[str, SdkAdapterError],
    spec: RunnerSpec | None = None,
    lineage: NativeLineageLedger | None = None,
    activity: MutableMapping[str, int] | None = None,
) -> Optional[dict[str, list[Any]]]:
    """Build SDK-native pre/post hooks for tool admission/evidence.

    The callbacks deny unsupported graph/background/detached requests *before*
    the tool executes.  Post hooks are observational and turn a missing or
    mismatched terminal event into uncertainty; they never assert descendant
    containment merely from a process-group identifier.
    """

    matcher_type = getattr(sdk_module, "HookMatcher", None)
    if matcher_type is None:
        return None

    async def pre_tool_use(value: Any, tool_use_id: Any = None, _context: Any = None) -> dict[str, Any]:
        probe = _hook_input_event(value, tool_use_id, "PreToolUse")
        tool_name = (_ToolEvidence._tool_name(probe) or "").casefold()
        if lineage is not None and lineage._coordinator_interrupt_fenced:
            error = SdkAdapterError(
                "busy", "coordinator interrupt fence blocks every new tool start"
            )
            return {
                "continue_": False,
                "decision": "block",
                "reason": error.message,
                "stopReason": error.message,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": error.message,
                },
            }
        if tool_name in _NATIVE_CHILD_TOOL_NAMES:
            if lineage is None:
                error = SdkAdapterError(
                    "unsupported",
                    "native Agent/Task admission requires the coordinator lineage ledger",
                )
                hook_error["error"] = error
                tool_evidence._reject("native-lineage-missing", {"tool_name": tool_name})
                return {
                    "continue_": False,
                    "decision": "block",
                    "reason": error.message,
                    "stopReason": error.message,
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": error.message,
                    },
                }
            error = await lineage.admit_agent(probe)
            if error is not None:
                if not (
                    error.code == "busy"
                    and lineage._coordinator_interrupt_fenced
                ):
                    hook_error["error"] = error
                return {
                    "continue_": False,
                    "decision": "block",
                    "reason": error.message,
                    "stopReason": error.message,
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": error.message,
                    },
                }
        agent_id = _native_value(probe, "agent_id", "agentId")
        child_record = None
        if agent_id is not None and lineage is not None:
            child_record = lineage.children.get(str(agent_id))
            if child_record is None:
                error = SdkAdapterError(
                    "ownership-conflict", "child tool hook has an unknown agent_id"
                )
                hook_error["error"] = error
                return {
                    "continue_": False,
                    "decision": "block",
                    "reason": error.message,
                    "stopReason": error.message,
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": error.message,
                    },
                }
        # A child is checked against its admitted trusted definition by
        # ``_observe_child_tool``.  The parent's read-only allowlist applies
        # only when no actual child owner is present.
        if spec is not None and spec.read_only and tool_name not in _NATIVE_CHILD_TOOL_NAMES and child_record is None:
            if (
                tool_name.startswith("mcp__")
                or tool_name in _READ_ONLY_DENY_TOOLS
                or tool_name not in _READ_ONLY_BUILTIN_TOOLS
            ):
                error = SdkAdapterError(
                    "unsupported",
                    f"tool {tool_name or '<unknown>'!r} is outside the read-only builtin allowlist",
                )
                hook_error["error"] = error
                tool_evidence._reject("read-only-tool-boundary", {"tool_name": tool_name})
                return {
                    "continue_": False,
                    "decision": "block",
                    "reason": error.message,
                    "stopReason": error.message,
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": error.message,
                    },
                }
        error = tool_evidence.observe(probe)
        if error is None and lineage is not None and tool_name not in _NATIVE_CHILD_TOOL_NAMES:
            error = lineage._observe_child_tool("pretooluse", probe)
        if error is None:
            return {}
        hook_error["error"] = error
        return {
            "continue_": False,
            "decision": "block",
            "reason": error.message,
            "stopReason": error.message,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": error.message,
            },
        }

    async def post_tool_use(value: Any, tool_use_id: Any = None, _context: Any = None) -> dict[str, Any]:
        probe = _hook_input_event(value, tool_use_id, "PostToolUse")
        tool_error = tool_evidence.observe(probe)
        lineage_error = None
        if lineage is not None:
            lineage_error = lineage.observe(probe)
            # Retain the original hook payload and watermark even when the
            # lineage ledger reports an uncertainty; the terminal fact itself
            # must remain available to the independent evidence path.
            lineage.record_coordinator_observation(probe)
        error = tool_error or lineage_error
        if error is not None:
            hook_error["error"] = error
        return {}

    async def post_tool_failure(value: Any, tool_use_id: Any = None, _context: Any = None) -> dict[str, Any]:
        probe = _hook_input_event(value, tool_use_id, "PostToolUseFailure")
        tool_error = tool_evidence.observe(probe)
        lineage_error = None
        if lineage is not None:
            lineage_error = lineage.observe(probe)
            # Failure hooks are authoritative observations even when they
            # leave an effect unknown.  Preserve their immutable provenance
            # before the reader is forced into its fail-closed path.
            lineage.record_coordinator_observation(probe)
        error = tool_error or lineage_error
        if error is not None:
            hook_error["error"] = error
        return {}

    async def subagent_start(value: Any, tool_use_id: Any = None, _context: Any = None) -> dict[str, Any]:
        probe = _hook_input_event(value, tool_use_id, "SubagentStart")
        if lineage is None:
            error = SdkAdapterError("unsupported", "native SubagentStart requires the coordinator lineage ledger")
        else:
            probe["_adapter_event_source"] = "hook"
            error = lineage.observe(probe)
            if error is None:
                lineage.record_coordinator_observation(probe)
        if error is not None:
            hook_error["error"] = error
        return {}

    async def subagent_stop(value: Any, tool_use_id: Any = None, _context: Any = None) -> dict[str, Any]:
        probe = _hook_input_event(value, tool_use_id, "SubagentStop")
        if lineage is None:
            error = SdkAdapterError("unsupported", "native SubagentStop requires the coordinator lineage ledger")
        else:
            probe["_adapter_event_source"] = "hook"
            error = lineage.observe(probe)
            if error is None:
                lineage.record_coordinator_observation(probe)
        if error is not None:
            hook_error["error"] = error
        return {}

    def tracked(callback: Callable[..., Any]) -> Callable[..., Any]:
        """Count hook callbacks while they can still mutate the ledger.

        A prepare-invocation request is synchronous with respect to this
        event loop, but a native hook may be suspended awaiting durable
        admission/effect evidence.  The local reader checkpoint must refuse
        while such a callback is still able to cross the A admission fence.
        Keep this accounting private to the runner; it is not runtime or
        caller-provided authority.
        """

        if activity is None:
            return callback

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            activity["hooks_inflight"] = activity.get("hooks_inflight", 0) + 1
            try:
                return await callback(*args, **kwargs)
            finally:
                activity["hooks_inflight"] = max(
                    0, activity.get("hooks_inflight", 1) - 1
                )

        return wrapper

    try:
        return {
            "PreToolUse": [matcher_type(matcher=None, hooks=[tracked(pre_tool_use)])],
            "PostToolUse": [matcher_type(matcher=None, hooks=[tracked(post_tool_use)])],
            "PostToolUseFailure": [matcher_type(matcher=None, hooks=[tracked(post_tool_failure)])],
            "SubagentStart": [matcher_type(matcher=None, hooks=[tracked(subagent_start)])],
            "SubagentStop": [matcher_type(matcher=None, hooks=[tracked(subagent_stop)])],
        }
    except Exception:
        # A runtime with a nominal HookMatcher but incompatible callback shape
        # cannot safely admit tools.
        return None


def _process_evidence() -> dict[str, Any]:
    """Capture ownership of this runner without claiming arbitrary descendants."""

    pid = os.getpid()
    evidence: dict[str, Any] = {
        "pid": pid,
        "process_group_id": None,
        "process_start_token": _process_start_token(pid),
        "process_group_owned": False,
        "exited": False,
        "group_excluded": False,
        "owned_process": True,
        "arbitrary_descendants": False,
    }
    if hasattr(os, "getpgid"):
        try:
            pgid = os.getpgid(pid)
            evidence["process_group_id"] = pgid
            evidence["session_id"] = os.getsid(pid) if hasattr(os, "getsid") else None
            evidence["process_group_owned"] = pgid == pid and (
                evidence["session_id"] is None or evidence["session_id"] == pid
            )
        except OSError:
            evidence["process_group_owned"] = False
    else:  # pragma: no cover - Windows fallback
        evidence["process_group_owned"] = False
    evidence["group_excluded"] = not _process_group_alive(evidence.get("process_group_id"))
    return evidence


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _await_bounded(awaitable: Any, timeout: float) -> Any:
    """Await in the current task with a deadline (without ``wait_for``).

    ``asyncio.wait_for`` wraps a coroutine in a second task.  That is unsafe for
    the SDK's client because its reader/transport lifetime is tied to the task
    and async context which performed ``connect``.  Python 3.11's timeout scope
    cancels the current task instead; supported older runtimes simply retain
    the SDK's own cancellation semantics when no timeout scope exists.
    """

    timeout_scope = getattr(asyncio, "timeout", None)
    if timeout_scope is not None:
        async with timeout_scope(timeout):
            return await awaitable
    # Python 3.9/3.10 fallback: cancel this task from the event loop rather
    # than wrapping the awaitable in a second task (the latter breaks SDK
    # client/task affinity just as ``wait_for`` does).
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    timed_out = [False]

    def cancel_current() -> None:
        timed_out[0] = True
        if task is not None:
            task.cancel()

    handle = loop.call_later(timeout, cancel_current)
    try:
        return await awaitable
    except asyncio.CancelledError as exc:
        if timed_out[0]:
            raise asyncio.TimeoutError from exc
        raise
    finally:
        handle.cancel()


async def _call_emit(emit: Callable[..., Any], payload: Any) -> None:
    if emit is None:
        return
    try:
        result = emit(payload)
    except TypeError:
        # A small compatibility seam for supervisors that use
        # ``emit(kind, payload)``.  The first call is the canonical API.
        result = emit("event", payload)
    await _maybe_await(result)


async def _connect_promptless(client: Any) -> None:
    connect = getattr(client, "connect", None)
    if connect is None:
        raise SdkAdapterError("unsupported", "Claude SDK client has no connect method")
    try:
        await _maybe_await(connect(prompt=None))
    except TypeError as exc:
        # Fake clients may expose only a positional prompt.  Passing None is
        # still explicit and never becomes an implicit query.
        try:
            await _maybe_await(connect(None))
        except TypeError:
            raise SdkAdapterError("unsupported", "Claude SDK client cannot connect promptlessly") from exc


async def _disconnect(client: Any) -> None:
    disconnect = getattr(client, "disconnect", None)
    if disconnect is not None:
        await _maybe_await(disconnect())


async def _interrupt(client: Any) -> None:
    interrupt = getattr(client, "interrupt", None)
    if interrupt is None:
        raise SdkAdapterError("unsupported", "Claude SDK client cannot interrupt")
    await _maybe_await(interrupt())


async def _receive_messages(client: Any) -> AsyncIterator[Any]:
    receiver = getattr(client, "receive_messages", None)
    if receiver is None:
        receiver = getattr(client, "receive", None)
    if receiver is None:
        raise SdkAdapterError("unsupported", "Claude SDK client has no continuous event reader")
    stream = receiver()
    if inspect.isawaitable(stream):
        stream = await stream
    if hasattr(stream, "__aiter__"):
        async for event in stream:
            yield event
        return
    if isinstance(stream, Iterable):
        for event in stream:
            yield event
        return
    raise SdkAdapterError("unsupported", "Claude SDK event reader is not iterable")


async def _initialization_event(client: Any) -> Optional[dict[str, Any]]:
    """Read the cached control ``init`` result exposed by official clients."""

    getter = getattr(client, "get_server_info", None)
    if getter is None:
        return None
    try:
        info = await _maybe_await(getter())
    except Exception as exc:  # noqa: BLE001
        raise SdkAdapterError("loader-failed", f"could not read Claude initialization info: {exc}") from exc
    if info is None:
        return None
    mapping = _event_to_mapping(info)
    # Official ClaudeSDKClient returns the init data mapping itself, not a
    # SystemMessage.  Preserve both forms for fake runtimes.
    if str(_get_ci(mapping, "subtype") or "").lower() in {"init", "initialize", "initialized"}:
        return mapping
    return {"type": "system", "subtype": "init", "data": mapping}


async def _control_value(controls: Any) -> Any:
    if controls is None:
        raise StopAsyncIteration
    getter = getattr(controls, "get", None)
    if getter is not None:
        return await _maybe_await(getter())
    anext = getattr(controls, "__anext__", None)
    if anext is not None:
        return await _maybe_await(anext())
    if not hasattr(controls, "__iter__"):
        raise SdkAdapterError("invalid", "controls must be an async iterator, queue, or iterable")
    # Materialise only one item at a time.  This path is for finite unit-test
    # iterables; production uses a queue/socket so the event loop is not blocked.
    iterator = getattr(_control_value, "_iterator", None)
    if iterator is None or getattr(_control_value, "_source", None) is not controls:
        iterator = iter(controls)
        setattr(_control_value, "_iterator", iterator)
        setattr(_control_value, "_source", controls)
    try:
        return next(iterator)
    except StopIteration as exc:
        # PEP 479 turns StopIteration escaping an async function into a
        # RuntimeError; translate it explicitly for the control loop.
        raise StopAsyncIteration from exc


def _control_operation(command: Any) -> str:
    if isinstance(command, str):
        return command.strip().lower()
    if isinstance(command, Mapping):
        value = _first_nonempty(command.get("operation"), command.get("command"), command.get("type"), command.get("action"))
        return "" if value is None else str(value).strip().lower().replace("_", "-")
    return ""


async def _legacy_event_controls(
    release_event: Any,
    interrupt_event: Any,
    payload: Any,
    message_id: Any,
) -> AsyncIterator[dict[str, Any]]:
    """Adapt the original in-process fake seam to the bounded control model."""

    released = False
    while not released:
        waiters: dict[str, asyncio.Task[Any]] = {}
        if release_event is not None and hasattr(release_event, "wait"):
            waiters["release"] = asyncio.create_task(release_event.wait())
        if interrupt_event is not None and hasattr(interrupt_event, "wait"):
            waiters["interrupt"] = asyncio.create_task(interrupt_event.wait())
        if not waiters:
            return
        try:
            done, _pending = await asyncio.wait(
                list(waiters.values()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            # Prefer interrupt if both flags were already set: it is the safe
            # quiescence action and can run concurrently with the reader.
            if "interrupt" in waiters and waiters["interrupt"] in done:
                if hasattr(interrupt_event, "clear"):
                    interrupt_event.clear()
                yield {"operation": "interrupt"}
                continue
            if "release" in waiters and waiters["release"] in done:
                if hasattr(release_event, "clear"):
                    release_event.clear()
                released = True
                yield {"operation": "release"}
                if payload is not None:
                    # Dispatching this command happens only after the release
                    # transition, making the boundary visible to the
                    # supervisor.
                    yield {
                        "operation": "query",
                        "payload": payload,
                        "message_id": message_id,
                    }
        finally:
            # Cancellation can arrive while the generator is suspended at a
            # yielded control.  Always reap both event waiters so a finished
            # drive_client cannot leave orphan tasks behind.
            for task in waiters.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*waiters.values(), return_exceptions=True)


def _normalise_sdk_options(sdk_module: Any, values: Mapping[str, Any]) -> Any:
    values = dict(values)
    if values.get("agents"):
        definition_type = getattr(sdk_module, "AgentDefinition", None)
        if definition_type is None:
            raise SdkAdapterError("unsupported", "Claude SDK exposes no native AgentDefinition")
        try:
            values["agents"] = {
                name: definition_type(**copy.deepcopy(definition))
                for name, definition in values["agents"].items()
            }
        except TypeError as exc:
            raise SdkAdapterError("unsupported", "Claude SDK cannot preserve the configured native agent policy") from exc
    options_type = getattr(sdk_module, "ClaudeAgentOptions", None)
    if options_type is None:
        # A deliberately tiny fake may accept mappings directly.
        return dict(values)
    try:
        return options_type(**dict(values))
    except TypeError as exc:
        # Never silently drop a resume/session, permission, model, tool, or
        # environment constraint.  Older optional SDK versions may not know a
        # newer observational setting, but that is an explicit capability
        # refusal rather than a weaker launch.
        message = str(exc)
        raise SdkAdapterError("unsupported", f"Claude SDK options are incompatible: {message}") from exc


async def drive_client(
    spec: RunnerSpec | Mapping[str, Any],
    controls: Any = None,
    emit: Callable[..., Any] = None,
    sdk_module: Any = None,
    *,
    client_factory: Callable[..., Any] | None = None,
    release_event: Any = None,
    interrupt_event: Any = None,
    payload: Any = None,
    message_id: Any = None,
    on_event: Callable[..., Any] = None,
    sdk_loader: Callable[..., Any] = None,
    persist_admission: Callable[[Mapping[str, Any]], Any] | None = None,
    capability_evidence: Any = None,
    require_live_capability: bool = False,
    native_stop_ipc: Any = None,
    native_stop_identity: Mapping[str, Any] | None = None,
    coordinator_interrupt_ipc: Any = None,
    coordinator_interrupt_identity: Mapping[str, Any] | None = None,
    native_child_observation_ipc: Any = None,
    native_swap_release_ipc: Any = None,
    native_swap_release_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one promptless held SDK client and its concurrent control reader.

    The function uses one client lifecycle and one continuous event reader.
    ``sdk_module`` is an explicit test seam.  Production passes the module from
    :func:`_runner_main` after sanitising ``os.environ`; a direct call without a
    fake therefore returns an explicit optional-capability refusal rather than
    importing the official dependency in the supervisor process.
    """

    runner_spec = _normalise_spec(spec)
    marker_error = _native_swap_target_marker_error(runner_spec)
    if marker_error is not None:
        raise SdkAdapterError("invalid", marker_error)
    _assert_spec_launchable(runner_spec)
    fake_factory = client_factory is not None
    if emit is None:
        emit = on_event
    if emit is None:
        async def emit(_payload: Any) -> None:
            return None
    if controls is None and (release_event is not None or interrupt_event is not None):
        controls = _legacy_event_controls(
            release_event,
            interrupt_event,
            payload,
            message_id,
        )
    if controls is None:
        controls = ()

    if sdk_module is None and sdk_loader is not None:
        try:
            sdk_module = sdk_loader()
            sdk_module = await _maybe_await(sdk_module)
        except (ImportError, ModuleNotFoundError) as exc:
            raise SdkAdapterError(
                "unsupported",
                "optional claude-agent-sdk is not installed; live capability is unverified",
            ) from exc
        except SdkAdapterError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SdkAdapterError("unsupported", f"optional Claude SDK loader failed: {exc}") from exc
    if sdk_module is None and not fake_factory:
        if os.environ.get("LANE_MANAGED_SDK_RUNNER") != "1":
            raise SdkAdapterError(
                "unsupported",
                "official Claude SDK is available only in the sanitized dedicated runner",
            )
        try:
            sdk_module = importlib.import_module("claude_agent_sdk")
        except (ImportError, ModuleNotFoundError) as exc:
            raise SdkAdapterError(
                "unsupported",
                "optional claude-agent-sdk is not installed; live capability is unverified",
            ) from exc

    # Official SDK-shaped modules are live runtimes even when the caller omits
    # the flag or the module has no ``__version__`` attribute.  Only an explicit
    # fake client factory can bypass this automatic classification; a false
    # caller flag cannot turn off the production gate.
    live_module = not fake_factory and _is_official_sdk_module(sdk_module)
    # This check is deliberately before hooks, options-to-SDK conversion, and
    # client construction.  A production runner may not connect first and
    # discover that Gate 0 was never proven.  Nonofficial injected module seams
    # remain usable for deterministic tests, but their results are never
    # accepted as live capability evidence.
    if require_live_capability or live_module:
        try:
            identity = resolve_runtime_identity(runner_spec, sdk_module=sdk_module)
        except SdkAdapterError as exc:
            raise SdkAdapterError(
                "unsupported" if exc.code == "unsupported" else "live-unverified",
                f"live runtime identity is unavailable: {exc.message}",
            ) from exc
        decision = assess_held_swap(identity, capability_evidence)
        if decision.verdict != "verified":
            refusal_code = "unsupported" if decision.verdict == "unsupported" else "live-unverified"
            raise SdkAdapterError(
                refusal_code,
                f"live runtime startup refused: {decision.reason_code}: {decision.reason}",
            )

    tool_evidence = _ToolEvidence()
    fingerprint = _mapping_copy(runner_spec.fingerprint)
    native_swap_target_requires_bound_release = (
        _native_swap_target_requires_bound_release(fingerprint)
    )
    lineage_context = _get_ci(fingerprint, "lineage_context")
    lineage_claim = _get_ci(fingerprint, "lineage_claim", "claim_ref")
    native_runtime_enabled = isinstance(lineage_context, Mapping) or isinstance(lineage_claim, Mapping)
    lineage = NativeLineageLedger(
        runner_spec.session_id,
        trusted_definitions=_get_ci(fingerprint, "trusted_definitions"),
        parent_read_only=runner_spec.read_only,
        lineage_context=lineage_context,
        lineage_claim=lineage_claim,
        persist_admission=persist_admission,
        coordinator_enabled=(
            native_runtime_enabled
            and (coordinator_interrupt_ipc is not None or coordinator_interrupt_identity is not None)
        ),
    )
    coordinator_enabled = lineage.coordinator_enabled
    startup_error = lineage.prepare_native_coordinator()
    if startup_error is not None:
        raise startup_error
    hook_error: dict[str, SdkAdapterError] = {}
    # Hook callbacks can await the durable admission/evidence bridge.  Keep a
    # runner-local count so a synchronous terminal checkpoint cannot race a
    # callback that still has authority to mutate invocation A.
    hook_activity: dict[str, int] = {"hooks_inflight": 0}
    guard_hooks = None
    hooks_authoritative = False
    if not fake_factory:
        guard_hooks = _build_guard_hooks(
            sdk_module,
            tool_evidence,
            hook_error,
            runner_spec,
            lineage,
            hook_activity,
        )
        if guard_hooks is None:
            raise SdkAdapterError(
                "unsupported",
                "Claude SDK does not expose compatible PreToolUse/PostToolUse hooks",
            )
        hooks_authoritative = True
    options_values = build_sdk_options(runner_spec)
    if guard_hooks is not None:
        options_values["hooks"] = guard_hooks
    if fake_factory:
        options = options_values
        try:
            client = client_factory(options)
        except TypeError:
            client = client_factory(options=options)
    else:
        options = _normalise_sdk_options(sdk_module, options_values)
        client_type = getattr(sdk_module, "ClaudeSDKClient", None)
        if client_type is None:
            raise SdkAdapterError("unsupported", "optional SDK exposes no ClaudeSDKClient")
        try:
            client = client_type(options)
        except TypeError:
            try:
                client = client_type(options=options)
            except Exception as exc:  # noqa: BLE001
                raise SdkAdapterError("unsupported", f"unable to construct Claude SDK client: {exc}") from exc

    tracker = InitializationTracker(runner_spec)
    process_evidence = _process_evidence()
    released = False
    native_swap_release_attempted = False
    native_swap_release_boundary: Optional[dict[str, Any]] = None
    interrupted = False
    stop_requested = False
    active_turn = False
    turn_terminal = True
    drained = True
    participant_quiescent = True
    reader_error: Optional[SdkAdapterError] = None
    control_error: Optional[SdkAdapterError] = None
    task_failure: Optional[SdkAdapterError] = None
    reader_done = asyncio.Event()
    control_done = asyncio.Event()
    emit_lock = asyncio.Lock()
    ready_emitted = False
    dispatched_request_ids: set[str] = set()
    dispatched_message_ids: set[str] = set()
    # A result message may carry a mailbox correlation in fake/legacy SDK
    # shapes.  Official ResultMessage 0.2.153 has no ``message_id`` field, so
    # absence is allowed; when a runtime supplies one while a send is pending,
    # a different value is an explicit identity failure.
    expected_result_message_ids: set[str] = set()
    # A ResultMessage proves the parent result only.  A later, distinct reader
    # checkpoint is produced locally by the persistent reader when the
    # controller asks to prepare a reservation.  Runtime idle/status aliases
    # never close this candidate.
    pending_parent_result: Optional[dict[str, Any]] = None
    reader_frame_inflight = False
    last_fully_processed_cursor: Optional[int] = None
    stop_evidence_tasks: set[asyncio.Task[Any]] = set()
    scheduled_stop_evidence_ids: set[str] = set()
    stop_evidence_error: Optional[SdkAdapterError] = None
    coordinator_evidence_tasks: set[asyncio.Task[Any]] = set()
    scheduled_coordinator_evidence_ids: set[str] = set()
    coordinator_evidence_error: Optional[SdkAdapterError] = None
    native_child_observation_inflight = False
    native_child_observation_attempted: set[str] = set()
    native_child_observation_frames: dict[str, dict[str, Any]] = {}
    native_child_observation_run_counts: dict[str, int] = {}

    def native_child_observation_identity() -> dict[str, str]:
        source = next(
            (
                value
                for value in (
                    coordinator_interrupt_identity,
                    native_stop_identity,
                    native_swap_release_identity,
                )
                if isinstance(value, Mapping)
            ),
            None,
        )
        participant = (
            runner_spec.participant_id
            if runner_spec.participant_id is not None
            else source.get("participant_id") if isinstance(source, Mapping) else None
        )
        runner_instance = (
            source.get("runner_instance_id") if isinstance(source, Mapping) else None
        )
        if participant is None or runner_instance is None:
            context = _get_ci(runner_spec.fingerprint, "lineage_context")
            runner_instance = (
                runner_instance
                or context.get("runner_incarnation")
                if isinstance(context, Mapping)
                else runner_instance
            )
        return {
            "participant_id": _wire_id(participant, "participant_id"),
            "session_id": _wire_id(runner_spec.session_id, "session_id"),
            "runner_instance_id": _wire_id(runner_instance, "runner_instance_id"),
        }

    async def persist_native_child_observation(
        observation: Mapping[str, Any]
    ) -> None:
        """Persist one joined child observation before the reader advances."""

        nonlocal native_child_observation_inflight
        if native_child_observation_ipc is None or not callable(
            getattr(native_child_observation_ipc, "request_native_child_observation", None)
        ):
            raise SdkAdapterError(
                "unsupported", "native child observation channel is not bound"
            )
        observation = _native_child_observation(observation)
        identity = native_child_observation_identity()
        frame = {
            "type": "native-child-observation",
            **identity,
            "observation": copy.deepcopy(observation),
        }
        if set(frame) != set(_NATIVE_CHILD_OBSERVATION_FRAME_FIELDS):
            raise SdkAdapterError(
                "invalid", "native child observation transport frame is malformed"
            )
        child_run_key = _native_child_observation_run_id(observation)
        if child_run_key in native_child_observation_attempted:
            return
        if child_run_key not in native_child_observation_run_counts:
            if len(native_child_observation_run_counts) >= MAX_NATIVE_CHILD_RUNS:
                raise SdkAdapterError(
                    "busy", "native child observation child-run history is full"
                )
            native_child_observation_run_counts[child_run_key] = 0
        if (
            native_child_observation_run_counts[child_run_key]
            >= MAX_NATIVE_CHILD_OBSERVATIONS_PER_RUN
        ):
            raise SdkAdapterError(
                "busy", "native child observation history is full for this child run"
            )
        native_child_observation_attempted.add(child_run_key)
        native_child_observation_run_counts[child_run_key] += 1
        native_child_observation_frames[child_run_key] = copy.deepcopy(frame)
        native_child_observation_inflight = True
        try:
            acknowledgement = await native_child_observation_ipc.request_native_child_observation(
                frame
            )
            if isinstance(acknowledgement, Mapping) and acknowledgement.get("recorded") is False:
                code = str(acknowledgement.get("code") or "loader-failed")
                raise SdkAdapterError(
                    "uncertain-effect" if code in {"uncertain-effect", "canceled", "cancelled"} else code,
                    "native child observation was not durably recorded",
                )
            if not _native_child_observation_ack_matches(acknowledgement, observation):
                raise SdkAdapterError(
                    "invalid", "native child observation acknowledgement was invalid"
                )
        except asyncio.CancelledError:
            lineage._fail(
                "uncertain-effect",
                "native child observation acknowledgement was cancelled",
                observation,
            )
            raise
        except SdkAdapterError as exc:
            lineage._fail(
                "uncertain-effect" if exc.code in {"loader-failed", "invalid"} else exc.code,
                f"native child observation persistence failed: {exc.message}",
                observation,
            )
            raise
        except Exception as exc:  # noqa: BLE001
            lineage._fail(
                "uncertain-effect",
                f"native child observation persistence failed: {exc}",
                observation,
            )
            raise SdkAdapterError(
                "uncertain-effect", "native child observation persistence failed"
            ) from exc
        finally:
            native_child_observation_inflight = False

    async def emit_serial(payload: Any) -> None:
        async with emit_lock:
            await _call_emit(emit, payload)

    async def emit_control(
        kind: str,
        command: Any = None,
        **values: Any,
    ) -> None:
        """Emit a control acknowledgement with its exact wire correlation."""

        payload: dict[str, Any] = {"type": kind, "session_id": runner_spec.session_id}
        if isinstance(command, Mapping):
            for key in (
                "request_id",
                "participant_id",
                "session_id",
                "runner_instance_id",
                "message_id",
            ):
                value = command.get(key)
                if value is not None:
                    payload[key] = value
        payload.update(values)
        await emit_serial(payload)

    async def persist_stop_evidence(frame: Mapping[str, Any]) -> None:
        nonlocal stop_evidence_error
        if native_stop_ipc is None:
            stop_evidence_error = SdkAdapterError(
                "unsupported",
                "native stop evidence channel is not bound",
            )
            return
        try:
            evidence = frame.get("evidence") if isinstance(frame, Mapping) else None
            evidence_id = evidence.get("evidence_id") if isinstance(evidence, Mapping) else None
            stop_id = evidence.get("stop_id") if isinstance(evidence, Mapping) else None
            acknowledgement = await native_stop_ipc.request_native_stop_evidence(frame)
            if not _native_stop_evidence_ack_matches(acknowledgement, evidence_id, stop_id):
                raise SdkAdapterError(
                    "invalid",
                    "native stop evidence was not durably recorded",
                )
        except asyncio.CancelledError:
            raise
        except SdkAdapterError as exc:
            stop_evidence_error = exc
            await emit_serial({"type": "adapter-error", **exc.as_dict()})

    def schedule_stop_evidence(frame: Mapping[str, Any]) -> None:
        evidence = frame.get("evidence") if isinstance(frame, Mapping) else None
        evidence_id = evidence.get("evidence_id") if isinstance(evidence, Mapping) else None
        if not isinstance(evidence_id, str) or evidence_id in scheduled_stop_evidence_ids:
            return
        scheduled_stop_evidence_ids.add(evidence_id)
        task = asyncio.create_task(
            persist_stop_evidence(copy.deepcopy(dict(frame))),
            name=f"lane-managed-native-stop-evidence-{evidence_id}",
        )
        stop_evidence_tasks.add(task)
        task.add_done_callback(stop_evidence_tasks.discard)

    async def persist_coordinator_evidence(frame: Mapping[str, Any]) -> None:
        nonlocal coordinator_evidence_error
        if coordinator_interrupt_ipc is None:
            coordinator_evidence_error = SdkAdapterError(
                "unsupported", "coordinator interrupt evidence channel is not bound"
            )
            return
        try:
            evidence = frame.get("evidence") if isinstance(frame, Mapping) else None
            evidence_id = evidence.get("evidence_id") if isinstance(evidence, Mapping) else None
            interrupt_id = evidence.get("interrupt_id") if isinstance(evidence, Mapping) else None
            acknowledgement = await coordinator_interrupt_ipc.request_coordinator_interrupt_evidence(frame)
            if not _coordinator_interrupt_evidence_ack_matches(
                acknowledgement, evidence_id, interrupt_id
            ):
                raise SdkAdapterError("invalid", "coordinator interrupt evidence was not durably recorded")
        except asyncio.CancelledError:
            raise
        except SdkAdapterError as exc:
            coordinator_evidence_error = exc
            await emit_serial({"type": "adapter-error", **exc.as_dict()})

    def schedule_coordinator_evidence(frame: Mapping[str, Any]) -> None:
        evidence = frame.get("evidence") if isinstance(frame, Mapping) else None
        evidence_id = evidence.get("evidence_id") if isinstance(evidence, Mapping) else None
        if not isinstance(evidence_id, str) or evidence_id in scheduled_coordinator_evidence_ids:
            return
        scheduled_coordinator_evidence_ids.add(evidence_id)
        task = asyncio.create_task(
            persist_coordinator_evidence(copy.deepcopy(dict(frame))),
            name=f"lane-managed-coordinator-interrupt-evidence-{evidence_id}",
        )
        coordinator_evidence_tasks.add(task)
        task.add_done_callback(coordinator_evidence_tasks.discard)

    def schedule_current_coordinator_evidence() -> None:
        if not coordinator_enabled:
            return
        for interrupt_id in list(lineage._coordinator_interrupt_states):
            for frame in lineage.coordinator_interrupt_evidence_frames(
                interrupt_id, tool_evidence=tool_evidence
            ):
                schedule_coordinator_evidence(frame)

    def mark_parent_result_observation(
        event: Mapping[str, Any], event_type: str, lineage_event: dict[str, Any]
    ) -> bool:
        """Correlate one official terminal ResultMessage with the query.

        ResultMessage does not carry the adapter mailbox or invocation IDs.
        The runner therefore uses the exact session, acceptable human origin,
        and one outstanding managed query as an internal correlation.  The
        reserved marker is local evidence metadata; it is never sent as SDK
        payload or used as a caller supplied identity.  Idle/drained/status
        notifications are deliberately not result or drain authority.  The
        persistent reader creates the independent local checkpoint only when
        the controller requests ``prepare-invocation``.
        """

        if not coordinator_enabled or event_type != "result":
            return False
        subtype = str(_get_ci(event, "subtype") or "").strip().casefold()
        if subtype not in {"success", "error", "error_during_execution"}:
            return False
        if subtype == "success":
            error_flag = _get_ci(event, "is_error", "isError")
            if error_flag is not None and _native_bool(error_flag) is not False:
                return False
        event_agent_id = _native_value(event, "agent_id", "agentId")
        event_task_id = _native_value(event, "task_id", "taskId")
        event_parent_tool = _native_value(
            event, "parent_tool_use_id", "parentToolUseId"
        )
        if event_agent_id is not None or event_task_id is not None or event_parent_tool is not None:
            return False
        event_session = _get_ci(event, "session_id", "sessionId")
        if (
            event_session is None
            or runner_spec.session_id is None
            or str(event_session) != str(runner_spec.session_id)
        ):
            return False
        origin = _get_ci(event, "origin")
        if origin is not None:
            if (
                not isinstance(origin, Mapping)
                or str(_get_ci(origin, "kind") or "").casefold() != "human"
            ):
                return False
        explicit_message = _get_ci(event, "message_id", "messageId")
        explicit_invocation = _native_value(event, "invocation_id", "invocationId")
        if explicit_message is not None:
            if (
                lineage.current_message_id is None
                or str(explicit_message) != lineage.current_message_id
            ):
                raise SdkAdapterError(
                    "stale-generation", "SDK result has the wrong correlated message ID"
                )
        if explicit_invocation is not None:
            if (
                lineage.current_invocation is None
                or str(explicit_invocation) != lineage.current_invocation
            ):
                raise SdkAdapterError(
                    "stale-generation", "SDK result has the wrong correlated invocation ID"
                )
        if (
            lineage.current_message_id is None
            or len(expected_result_message_ids) != 1
            or lineage.current_message_id not in expected_result_message_ids
        ):
            # An ambiguous, already consumed, or absent mailbox remains an
            # uncorrelated runtime fact rather than proving parent drain.
            return False
        if explicit_message is not None and str(explicit_message) != lineage.current_message_id:
            return False
        expected_result_message_ids.discard(lineage.current_message_id)
        lineage_event["_coordinator_parent_observation"] = True
        lineage_event["_coordinator_parent_message_id"] = lineage.current_message_id
        lineage_event["_coordinator_parent_result_subtype"] = subtype
        return True

    def post_result_child_frame_is_correlated(
        event: Mapping[str, Any], event_type: str, native_kind: str
    ) -> bool:
        """Check a post-result child frame against the accepted A join.

        Native children may finish after the coordinator's ResultMessage.  A
        frame from a child that was admitted and joined to the current A
        invocation is therefore ordinary remaining work, not an uncorrelated
        follow-up.  The local checkpoint still waits for that work to become
        terminal.  Unknown identities, contradictory task/tool joins, and
        lifecycle frames that cannot be tied to a current child remain poison
        so they cannot be mistaken for reader-drain evidence.

        This is intentionally evaluated after ``lineage.observe``.  The
        ledger's existing admission/task/incarnation validator is the source
        of truth for the exact join; this helper only classifies the accepted
        result for the pending reader checkpoint and never grants authority.
        """

        if not coordinator_enabled or pending_parent_result is None:
            return True
        child_kinds = {
            "pretooluse", "posttooluse", "posttoolusefailure", "subagentstart",
            "subagentstop", "taskstarted", "taskprogress", "tasknotification",
            "taskupdated",
        }
        has_child_identity = any(
            _native_value(event, name) is not None
            for name in (
                "agent_id", "agentId", "task_id", "taskId", "tool_use_id",
                "toolUseId", "parent_tool_use_id", "parentToolUseId",
            )
        )
        # A second result cannot be the one outstanding correlated result and
        # is not a drain checkpoint.  Ordinary assistant/status frames without
        # child identity are allowed to flow to the persistent reader; the
        # local checkpoint independently proves their processing boundary.
        if event_type == "result":
            return False
        if not has_child_identity and native_kind not in child_kinds:
            return True
        current_invocation = pending_parent_result.get("invocation_id")
        records: list[dict[str, Any]] = []
        agent_id = _native_value(event, "agent_id", "agentId")
        if agent_id is not None:
            record = lineage.children.get(str(agent_id))
            if record is not None:
                records.append(record)
        task_id = _native_value(event, "task_id", "taskId")
        if task_id is not None:
            records.extend(
                record
                for record in lineage.children.values()
                if str(record.get("task_id")) == str(task_id)
                and record not in records
            )
        tool_id = _native_value(event, "tool_use_id", "toolUseId")
        if tool_id is not None:
            records.extend(
                record
                for record in lineage.children.values()
                if str(record.get("tool_use_id")) == str(tool_id)
                and record not in records
            )
        pending_task = None
        if task_id is not None:
            pending_task = lineage.pending_tasks.get(str(task_id))
        pending_admission = None
        if tool_id is not None:
            pending_admission = lineage.pending_admissions.get(str(tool_id))
        if not records and pending_task is None and pending_admission is None:
            return False
        if len(records) > 1:
            return False
        if records:
            record = records[0]
            parent_links = record.get("parent_links")
            if not isinstance(parent_links, Mapping):
                return False
            if parent_links.get("invocation_id") != current_invocation:
                return False
            # ``lineage.observe`` marks a contradictory current-child event as
            # unresolved/uncertain.  It is not a valid joined completion even
            # when one of its IDs happens to match an older record.
            if record.get("status") == "unresolved" or record.get("uncertain"):
                return False
            event_agent = _native_value(event, "agent_id", "agentId")
            if event_agent is not None and str(event_agent) != str(record.get("agent_id")):
                return False
            expected_task = record.get("task_id")
            if task_id is not None and (
                expected_task is None or str(task_id) != str(expected_task)
            ):
                return False
            # A child tool's tool_use_id is the child effect ID, not the
            # launch admission ID.  For native Agent/Task lifecycle frames it
            # is the launch ID and must agree with the joined record.
            tool_name = str(_native_value(event, "tool_name", "toolName", "name") or "").casefold()
            if tool_id is not None and (
                native_kind in {"subagentstart", "subagentstop"}
                or tool_name in _NATIVE_CHILD_TOOL_NAMES
                or task_id is not None
            ) and str(tool_id) != str(record.get("tool_use_id")):
                return False
        for pending in (pending_task, pending_admission):
            if pending is not None and pending.get("invocation_id") != current_invocation:
                return False
        return True

    def _checkpoint_terminal_invocation(
        request: Any,
        checkpoint_tool_evidence: Any,
    ) -> dict[str, Any]:
        """Produce the runner-local independent drain checkpoint.

        The SDK has no portable CLI ``idle``/``drained`` notification that
        proves its receive queue is empty.  The persistent reader is the
        supported authority here: it has fully processed the correlated
        ResultMessage and every frame before this synchronous call.  A local
        cursor is then allocated and bound to that result while the existing
        ledger reservation gate seals new A work.  No await occurs between the
        final checks, the checkpoint, and reservation issuance.
        """

        nonlocal pending_parent_result, last_fully_processed_cursor

        if not isinstance(request, Mapping):
            raise SdkAdapterError(
                "invalid", "native invocation checkpoint request must be an object"
            )
        # Validate the request before inspecting or mutating the current
        # reservation.  This also makes exact retries byte-equivalent at the
        # canonical binding boundary.
        binding = _native_invocation_binding(request)
        participant_id = (
            coordinator_interrupt_identity.get("participant_id")
            if isinstance(coordinator_interrupt_identity, Mapping)
            else runner_spec.participant_id
        )
        # An exact retry observes the already sealed immutable response.  It
        # must not depend on the reader still being live after the first
        # successful checkpoint.
        if lineage.invocation_reservation is not None:
            return lineage.prepare_invocation_reservation(
                binding,
                participant_id=participant_id,
                tool_evidence=checkpoint_tool_evidence,
            )
        if not coordinator_enabled:
            raise SdkAdapterError(
                "unsupported",
                "native invocation checkpoint requires coordinator lineage mode",
            )
        if reader_done.is_set():
            raise SdkAdapterError(
                "unsupported", "native invocation reader ended before its drain checkpoint"
            )
        if reader_error is not None:
            raise reader_error
        if reader_frame_inflight:
            raise SdkAdapterError(
                "busy", "native invocation reader is still processing a runtime frame"
            )
        if hook_activity.get("hooks_inflight", 0):
            raise SdkAdapterError(
                "busy", "native invocation hook/admission callback is still in flight"
            )
        if native_child_observation_inflight:
            raise SdkAdapterError(
                "busy", "native child observation acknowledgement is still in flight"
            )
        if lineage.pending_admissions or lineage.pending_tasks:
            raise SdkAdapterError(
                "busy", "native invocation has an admission or task callback in flight"
            )
        if any(not task.done() for task in stop_evidence_tasks):
            raise SdkAdapterError(
                "busy", "native invocation stop evidence is still being recorded"
            )
        if any(not task.done() for task in coordinator_evidence_tasks):
            raise SdkAdapterError(
                "busy", "native invocation coordinator evidence is still being recorded"
            )
        if stop_evidence_error is not None:
            raise stop_evidence_error
        if coordinator_evidence_error is not None:
            raise coordinator_evidence_error
        if lineage.error is not None:
            raise lineage.error
        if lineage.overflow or lineage._coordinator_fact_overflow:
            raise SdkAdapterError(
                "uncertain-effect", "native invocation reader evidence overflowed"
            )
        if (
            checkpoint_tool_evidence is None
            or bool(getattr(checkpoint_tool_evidence, "evidence_overflow", False))
        ):
            raise SdkAdapterError(
                "uncertain-effect", "native invocation tool evidence overflowed or is absent"
            )
        pending = pending_parent_result
        if not isinstance(pending, Mapping):
            raise SdkAdapterError(
                "unsupported", "native invocation lacks a correlated terminal ResultMessage"
            )
        current_invocation = lineage.current_invocation
        current_message_id = lineage.current_message_id
        if (
            pending.get("session_id") != lineage.coordinator_session_id
            or pending.get("session_id") != runner_spec.session_id
            or pending.get("invocation_id") != current_invocation
            or pending.get("message_id") != current_message_id
            or binding["session_id"] != lineage.coordinator_session_id
            or binding["prior_invocation_id"] != current_invocation
            or binding["prior_mailbox_id"] != current_message_id
        ):
            raise SdkAdapterError(
                "stale-generation", "native invocation result correlation changed"
            )
        if pending.get("uncorrelated_followup"):
            raise SdkAdapterError(
                "stale-generation",
                "native invocation received an uncorrelated child/status frame after its result",
            )
        result_watermark = pending.get("result_watermark")
        if type(result_watermark) is not int or result_watermark <= lineage.current_invocation_watermark:
            raise SdkAdapterError(
                "stale-generation", "native invocation result watermark is stale"
            )
        processed_through = last_fully_processed_cursor
        if type(processed_through) is not int or processed_through < result_watermark:
            raise SdkAdapterError(
                "busy", "native invocation result frame has not finished reader processing"
            )
        if not lineage.quiescent:
            raise SdkAdapterError(
                "busy", "native invocation child/effect inventory is not terminal"
            )
        # All checks above are synchronous and no await is allowed below.  The
        # event loop therefore cannot admit new A work between this point and
        # the existing reservation seal in ``prepare_invocation_reservation``.
        ledger_cursor = lineage.runtime_cursor if lineage.runtime_cursor is not None else lineage.watermark
        checkpoint_watermark = max(result_watermark, processed_through, lineage.watermark, ledger_cursor) + 1
        previous_parent_result = copy.deepcopy(lineage._parent_result)
        previous_parent_state = (
            lineage._parent_state_observed,
            lineage._parent_active,
            lineage._parent_drained,
            lineage.watermark,
            lineage.runtime_cursor,
        )
        parent_error = lineage.note_parent_result(
            invocation_id=current_invocation,
            message_id=current_message_id,
            result_watermark=result_watermark,
            reader_drained_watermark=checkpoint_watermark,
        )
        if parent_error is not None:
            raise parent_error
        try:
            reservation = lineage.prepare_invocation_reservation(
                binding,
                participant_id=participant_id,
                tool_evidence=checkpoint_tool_evidence,
            )
        except SdkAdapterError:
            # This path is synchronous and deterministic.  If proof assembly
            # fails before the seal, restore the pre-checkpoint observation so
            # a later retry cannot mistake a failed attempt for a drain.  An
            # already sealed/unknown result is never rolled back.
            if not lineage._reservation_sealed and lineage.invocation_reservation is None:
                (
                    lineage._parent_state_observed,
                    lineage._parent_active,
                    lineage._parent_drained,
                    lineage.watermark,
                    lineage.runtime_cursor,
                ) = previous_parent_state
                lineage._parent_result = previous_parent_result
            raise
        # The reservation's observation watermark is allocated from the same
        # persistent-reader cursor domain used by STATUS.  Commit that cursor
        # only after the synchronous seal and proof issuance have succeeded;
        # doing it earlier would make a failed reservation look fully
        # processed, while advancing it from STATUS would weaken the
        # independent-reader proof.
        last_fully_processed_cursor = checkpoint_watermark
        # The cached response is now the durable retry authority; the local
        # pending candidate is consumed so later runtime facts cannot be
        # attributed to the next invocation.
        pending_parent_result = None
        return reservation

    async def emit_ready_held() -> None:
        nonlocal ready_emitted
        if not tracker.ready or ready_emitted:
            return
        if not lineage.ready_for_hold:
            error = lineage.error or SdkAdapterError(
                "startup-orphan",
                "native child state was observed before coordinator readiness could be held",
            )
            raise error
        ready_emitted = True
        await emit_serial(
            {
                "type": "ready-held",
                "session_id": runner_spec.session_id,
                "evidence": {
                    **tracker.snapshot(),
                    "lineage": lineage.snapshot(),
                },
                "lineage": lineage.snapshot(),
            }
        )

    async def reader() -> None:
        nonlocal reader_error, active_turn, turn_terminal, drained, participant_quiescent
        nonlocal pending_parent_result
        nonlocal reader_frame_inflight, last_fully_processed_cursor
        try:
            async for raw_event in _receive_messages(client):
                event = _event_to_mapping(raw_event)
                # This flag spans every await below, including serial event
                # emission and evidence scheduling.  Prepare must never use a
                # cursor while the current frame can still mutate A state.
                reader_frame_inflight = True
                frame_cursor = _native_value(
                    event, "sequence", "event_cursor", "cursor", "watermark"
                )
                event_type = _event_type(event)
                event_session = _get_ci(event, "session_id", "sessionId")
                if event_session is not None and runner_spec.session_id is not None and str(event_session) != str(runner_spec.session_id):
                    raise SdkAdapterError(
                        "loader-failed",
                        "runtime event session identity does not match the exact participant UUID",
                    )
                lineage_event = dict(event)
                lineage_event.setdefault("_adapter_event_source", "stream")
                parent_result_observed = mark_parent_result_observation(
                    event, event_type, lineage_event
                )
                native_kind = _native_event_kind(lineage_event)
                if coordinator_enabled and pending_parent_result is not None and not parent_result_observed:
                    # A child/status frame is not a reader-drain authority.
                    # Keep explicit old invocation/mailbox identities from
                    # being silently ignored.  Exact current-A child joins
                    # are classified only after the ledger observes the
                    # frame; active joined children remain busy until their
                    # own terminal evidence is processed.
                    explicit_invocation = _native_value(
                        event, "invocation_id", "invocationId"
                    )
                    explicit_message = _get_ci(event, "message_id", "messageId")
                    if (
                        explicit_invocation is not None
                        and str(explicit_invocation) != pending_parent_result["invocation_id"]
                    ) or (
                        explicit_message is not None
                        and str(explicit_message) != pending_parent_result["message_id"]
                    ):
                        raise SdkAdapterError(
                            "stale-generation",
                            "post-result reader frame belongs to another invocation or mailbox",
                        )
                # Official hook callbacks are the pre-execution authority for
                # Agent/Task.  The SDK may also mirror that same PreToolUse
                # record on the stream; observing it a second time would
                # either re-admit or reject an already-authorized launch.
                lineage_error = None
                if not (hooks_authoritative and native_kind == "pretooluse"):
                    lineage_error = lineage.observe(lineage_event)
                if lineage_error is not None:
                    reader_error = lineage_error
                    await emit_serial({"type": "adapter-error", **lineage_error.as_dict()})
                    break
                # Publish only after the real SubagentStart -> TaskStarted ->
                # terminal lifecycle join has been accepted by the ledger.
                # The callback is awaited while ``reader_frame_inflight`` is
                # true, so checkpoint, release, and status/no-send paths all
                # remain closed until this exact ACK commits (or uncertainty
                # is retained on failure).
                if native_child_observation_ipc is not None and coordinator_enabled:
                    observation = lineage.native_child_observation_for_event(lineage_event)
                    if observation is not None:
                        await persist_native_child_observation(observation)
                if (
                    coordinator_enabled
                    and pending_parent_result is not None
                    and not parent_result_observed
                    and not post_result_child_frame_is_correlated(
                        event, event_type, native_kind
                    )
                ):
                    pending_parent_result["uncorrelated_followup"] = True
                lineage.record_coordinator_observation(lineage_event)
                coordinator_frame = lineage.coordinator_interrupt_event_evidence(lineage_event)
                if coordinator_frame is not None:
                    schedule_coordinator_evidence(coordinator_frame)
                terminal_frame = lineage.native_stop_terminal_evidence(lineage_event)
                if terminal_frame is not None:
                    terminal_stop_id = terminal_frame["evidence"]["stop_id"]
                    if lineage.native_stop_pending_terminal_evidence(terminal_stop_id) is not None:
                        schedule_stop_evidence(terminal_frame)
                await emit_serial(event)
                if event_type in {"assistant", "message-start", "message-started", "turn-start", "turn-started"}:
                    active_turn = True
                    turn_terminal = False
                    drained = False
                    participant_quiescent = False
                elif event_type in {"result", "message-stop", "turn-end", "turn-ended", "turn-complete", "done", "drained", "idle"}:
                    active_turn = False
                    turn_terminal = True
                    drained = True
                    participant_quiescent = True
                if coordinator_enabled:
                    if parent_result_observed:
                        result_cursor = _native_value(
                            lineage_event, "sequence", "event_cursor", "cursor", "watermark"
                        )
                        if result_cursor is None:
                            result_cursor = lineage.watermark + 1
                        elif type(result_cursor) is not int:
                            parent_error = SdkAdapterError(
                                "invalid", "SDK result cursor is not an integer"
                            )
                            reader_error = parent_error
                            await emit_serial({"type": "adapter-error", **parent_error.as_dict()})
                            break
                        elif result_cursor <= lineage.current_invocation_watermark:
                            parent_error = SdkAdapterError(
                                "stale-generation", "SDK result cursor predates its invocation"
                            )
                            reader_error = parent_error
                            await emit_serial({"type": "adapter-error", **parent_error.as_dict()})
                            break
                        frame_cursor = result_cursor
                        pending_parent_result = {
                            "session_id": lineage.coordinator_session_id,
                            "invocation_id": lineage.current_invocation,
                            "message_id": lineage.current_message_id,
                            "result_watermark": result_cursor,
                        }
                        # The result is terminal evidence, but the reader has
                        # not yet supplied an independent drain checkpoint.
                        parent_error = lineage.note_parent_state(
                            active=False,
                            drained=False,
                            invocation_id=lineage.current_invocation,
                        )
                        if parent_error is not None:
                            reader_error = parent_error
                            await emit_serial({"type": "adapter-error", **parent_error.as_dict()})
                            break
                tracker.observe(event)
                tool_error = hook_error.get("error")
                event_subtype = str(_get_ci(event, "subtype") or "").casefold()
                # HookEventMessage lifecycle notifications describe the hook
                # callback itself.  The callback already recorded the actual
                # tool start/end; counting these notifications a second time
                # would turn every PostToolUse into a false completion-without-
                # start uncertainty.
                if (
                    tool_error is None
                    and not hooks_authoritative
                    and event_subtype not in {"hook_started", "hook_response"}
                ):
                    tool_error = tool_evidence.observe(event)
                if tool_error is not None:
                    reader_error = tool_error
                    await emit_serial({"type": "adapter-error", **tool_error.as_dict()})
                    break
                if tracker.error is not None:
                    reader_error = tracker.error
                    await emit_serial({"type": "adapter-error", **tracker.error.as_dict()})
                    break
                if tracker.ready and not ready_emitted:
                    await emit_ready_held()
                # Only after lineage/tracker/tool processing, coordinator
                # evidence scheduling, and serial emission have all completed
                # may this frame become part of the local reader checkpoint.
                if type(frame_cursor) is not int or isinstance(frame_cursor, bool):
                    frame_cursor = lineage.watermark
                else:
                    frame_cursor = max(frame_cursor, lineage.watermark)
                if last_fully_processed_cursor is None:
                    last_fully_processed_cursor = frame_cursor
                else:
                    last_fully_processed_cursor = max(
                        last_fully_processed_cursor, frame_cursor
                    )
                reader_frame_inflight = False
        except asyncio.CancelledError:
            raise
        except SdkAdapterError as exc:
            reader_error = exc
            await emit_serial({"type": "adapter-error", **exc.as_dict()})
        except Exception as exc:  # noqa: BLE001
            reader_error = SdkAdapterError("loader-failed", f"SDK event reader failed: {exc}")
            await emit_serial({"type": "adapter-error", **reader_error.as_dict()})
        finally:
            reader_frame_inflight = False
            reader_done.set()

    def native_release_identity_error(binding: Mapping[str, Any]) -> Optional[SdkAdapterError]:
        """Fence a release binding against the runner's current held identity."""

        if not isinstance(native_swap_release_identity, Mapping):
            return SdkAdapterError(
                "unsupported",
                "native swap release authorization identity is not bound",
            )
        try:
            for key in _RUNNER_IDENTITY_FIELDS:
                actual = _wire_id(native_swap_release_identity.get(key), key)
                expected = {
                    "participant_id": (
                        runner_spec.participant_id
                        if runner_spec.participant_id is not None
                        else native_swap_release_identity.get("participant_id")
                    ),
                    "session_id": runner_spec.session_id,
                    "runner_instance_id": native_swap_release_identity.get(
                        "runner_instance_id"
                    ),
                }[key]
                if actual != str(expected):
                    return SdkAdapterError(
                        "stale-generation",
                        f"native swap release identity changed its {key}",
                    )
        except SdkAdapterError:
            return SdkAdapterError(
                "unsupported",
                "native swap release authorization identity is incomplete",
            )
        identity = lineage._lineage_identity()
        expected_owner = identity.get("owner_generation")
        expected_lineage = identity.get("lineage_id")
        expected_runner = identity.get("runner_incarnation")
        expected_generation = lineage._lineage_generation()
        try:
            expected_participant = _wire_id(
                native_swap_release_identity.get("participant_id"),
                "participant_id",
            )
            expected_session = _wire_id(
                native_swap_release_identity.get("session_id"), "session_id"
            )
            expected_runner_instance = _wire_id(
                native_swap_release_identity.get("runner_instance_id"),
                "runner_instance_id",
            )
        except SdkAdapterError:
            return SdkAdapterError(
                "unsupported",
                "native swap release authorization identity is incomplete",
            )
        if (
            type(expected_owner) is not int
            or expected_owner <= 0
            or not isinstance(expected_lineage, str)
            or not expected_lineage
            or not isinstance(expected_runner, str)
            or not expected_runner
            or binding["participant_id"] != expected_participant
            or binding["session_id"] != expected_session
            or binding["runner_incarnation"] != expected_runner_instance
            or binding["owner_generation"] != expected_owner
            or binding["lineage_id"] != expected_lineage
            or binding["runner_incarnation"] != expected_runner
            or binding["lineage_generation"] != expected_generation
        ):
            return SdkAdapterError(
                "stale-generation",
                "native swap release binding changed its lineage identity",
            )
        return None

    def native_release_quiescence_error(
        *, message: str
    ) -> Optional[SdkAdapterError]:
        """Return a local readiness refusal for the synchronous native gate.

        Native-swap release has no parent ResultMessage requirement: a target
        runner starts held and promptless.  It does, however, need the same
        causal accounting used by the terminal reader checkpoint.  In
        particular, an EOF, an in-flight reader frame/hook, or queued native
        stop/coordinator evidence is not made safe by a quiet status flag.
        """

        if reader_done.is_set():
            return SdkAdapterError(
                "unsupported", "native swap release reader ended before its gate"
            )
        if reader_error is not None:
            return reader_error
        if reader_frame_inflight:
            return SdkAdapterError(
                "busy", "native swap release reader is still processing a runtime frame"
            )
        if hook_activity.get("hooks_inflight", 0):
            return SdkAdapterError(
                "busy", "native swap release hook/admission callback is still in flight"
            )
        if native_child_observation_inflight:
            return SdkAdapterError(
                "busy", "native child observation acknowledgement is still in flight"
            )
        if lineage.pending_admissions or lineage.pending_tasks:
            return SdkAdapterError(
                "busy", "native swap release has a native admission or task callback in flight"
            )
        if any(not task.done() for task in stop_evidence_tasks):
            return SdkAdapterError(
                "busy", "native swap release stop evidence is still being recorded"
            )
        if any(not task.done() for task in coordinator_evidence_tasks):
            return SdkAdapterError(
                "busy", "native swap release coordinator evidence is still being recorded"
            )
        if stop_evidence_error is not None:
            return stop_evidence_error
        if coordinator_evidence_error is not None:
            return coordinator_evidence_error
        if control_error is not None:
            return control_error
        if task_failure is not None:
            return task_failure
        if hook_error.get("error") is not None:
            return hook_error["error"]
        if lineage.error is not None:
            return lineage.error
        if lineage.overflow or lineage._coordinator_fact_overflow:
            return SdkAdapterError(
                "uncertain-effect", "native swap release lineage evidence overflowed"
            )
        if bool(getattr(tool_evidence, "evidence_overflow", False)):
            return SdkAdapterError(
                "uncertain-effect", "native swap release tool evidence overflowed"
            )
        if stop_requested:
            return SdkAdapterError(
                "uncertain-effect", "native swap release runner is stopping"
            )
        if (
            released
            or lineage.released
            or not tracker.ready
            or not tool_evidence.quiescent
            or not lineage.quiescent
            or active_turn
            or not turn_terminal
            or not drained
            or not participant_quiescent
        ):
            return SdkAdapterError("uncertain-effect", message)
        return None

    async def perform_native_swap_release(
        command: Any, value: Any
    ) -> None:
        """Authorize and synchronously cross one bound native release gate."""

        nonlocal released, native_swap_release_attempted, native_swap_release_boundary
        # The presence of a bound payload selects the one-shot native path.
        # Poison the ordinary fallback before parsing/identity validation so a
        # malformed or stale native command cannot be repaired by an unbound
        # release on the same runner.
        if native_swap_release_attempted:
            refusal = SdkAdapterError(
                "busy",
                "native swap release authorization was already attempted; retry is forbidden",
            )
            await emit_control("adapter-error", command, **refusal.as_dict())
            return
        native_swap_release_attempted = True
        try:
            binding = _native_swap_binding(value)
        except SdkAdapterError as exc:
            await emit_control("adapter-error", command, **exc.as_dict())
            return
        identity_error = native_release_identity_error(binding)
        if identity_error is not None:
            await emit_control("adapter-error", command, **identity_error.as_dict())
            return
        if native_swap_release_ipc is None or not callable(
            getattr(native_swap_release_ipc, "request_native_swap_release", None)
        ):
            refusal = SdkAdapterError(
                "unsupported",
                "native swap release authorization channel is not bound",
            )
            await emit_control("adapter-error", command, **refusal.as_dict())
            return
        refusal = native_release_quiescence_error(
            message="native swap release requires an actually quiescent held runner"
        )
        if refusal is not None:
            await emit_control("adapter-error", command, **refusal.as_dict())
            return

        # The ID is allocated once immediately before the first private IPC
        # attempt.  A timeout/lost ACK therefore cannot cause an automatic
        # retry with a new authority transaction.
        validation_id = "native-swap-" + _uuid.uuid4().hex
        frame = {
            "type": "native-swap-release-authorize",
            **{
                key: native_swap_release_identity.get(key)
                for key in _RUNNER_IDENTITY_FIELDS
            },
            "validation_id": validation_id,
            "binding": copy.deepcopy(binding),
        }
        try:
            acknowledgement = await _await_bounded(
                native_swap_release_ipc.request_native_swap_release(frame),
                runner_spec.operation_deadline,
            )
        except asyncio.TimeoutError:
            refusal = SdkAdapterError(
                "loader-failed",
                "native swap release authorization acknowledgement timed out",
            )
            await emit_control("adapter-error", command, **refusal.as_dict())
            return
        except SdkAdapterError as exc:
            await emit_control("adapter-error", command, **exc.as_dict())
            return
        except Exception as exc:  # noqa: BLE001
            refusal = SdkAdapterError(
                "loader-failed",
                f"native swap release authorization failed: {exc}",
            )
            await emit_control("adapter-error", command, **refusal.as_dict())
            return
        try:
            acknowledgement = _native_swap_authorization(
                acknowledgement,
                validation_id=validation_id,
                binding=binding,
            )
        except SdkAdapterError as exc:
            await emit_control("adapter-error", command, **exc.as_dict())
            return
        if acknowledgement["authorized"] is not True:
            refusal = SdkAdapterError(
                "unsupported",
                "controller did not authorize native swap release",
            )
            await emit_control("adapter-error", command, **refusal.as_dict())
            return

        # No await is permitted between this revalidation and the gate.  The
        # private ACK is controller authority, while these checks prove that
        # this exact runner is still held and quiescent locally.
        identity_error = native_release_identity_error(binding)
        if identity_error is not None:
            await emit_control("adapter-error", command, **identity_error.as_dict())
            return
        refusal = native_release_quiescence_error(
            message="native swap release runner changed before its synchronous gate"
        )
        if refusal is not None:
            await emit_control("adapter-error", command, **refusal.as_dict())
            return
        lineage_error = lineage.can_release()
        if lineage_error is not None:
            await emit_control("adapter-error", command, **lineage_error.as_dict())
            return
        lineage_error = lineage.mark_released()
        if lineage_error is not None:
            await emit_control("adapter-error", command, **lineage_error.as_dict())
            return
        current_watermark = max(
            lineage.watermark,
            lineage.runtime_cursor if lineage.runtime_cursor is not None else 0,
        )
        gate_watermark = current_watermark + 1
        lineage.watermark = gate_watermark
        lineage.runtime_cursor = gate_watermark
        native_swap_release_boundary = _native_swap_boundary(
            {
                "binding": binding,
                "gate_event_id": str(_uuid.uuid4()),
                "gate_watermark": gate_watermark,
            },
            expected_binding=binding,
        )
        released = True
        await emit_control(
            "released",
            command,
            release_receipt=True,
            native_swap_release_boundary=copy.deepcopy(native_swap_release_boundary),
            lineage=lineage.snapshot(),
        )

    async def control_loop() -> None:
        nonlocal released, interrupted, stop_requested, active_turn, turn_terminal, drained, participant_quiescent, control_error
        try:
            while not stop_requested:
                try:
                    command = await _control_value(controls)
                except (StopAsyncIteration, StopIteration):
                    return
                operation = _control_operation(command)
                if operation == "protocol-error":
                    code = command.get("code", "invalid") if isinstance(command, Mapping) else "invalid"
                    message = command.get("message", "invalid control frame") if isinstance(command, Mapping) else "invalid control frame"
                    control_error = SdkAdapterError(str(code), str(message))
                    await emit_control("adapter-error", command, code=str(code), message=str(message))
                    stop_requested = True
                    return
                if operation in {"", "unknown"}:
                    await emit_control("adapter-error", command, code="invalid", message="control operation is required")
                    continue
                if operation in {"interrupt", "cancel"}:
                    if native_runtime_enabled:
                        refusal = SdkAdapterError(
                            "unsupported",
                            "native coordinator interrupt must use durable coordinator authorization",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    try:
                        await _await_bounded(_interrupt(client), runner_spec.operation_deadline)
                    except asyncio.TimeoutError as exc:
                        refusal = SdkAdapterError("loader-failed", "interrupt operation deadline exceeded")
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        hook_error.setdefault("error", refusal)
                        continue
                    interrupted = True
                    await emit_control(
                        "interrupt-ack",
                        command,
                        interrupt_receipt=True,
                        active_turn=active_turn,
                        turn_terminal=turn_terminal,
                        drained=drained,
                        participant_quiescent=participant_quiescent,
                        tools_quiescent=tool_evidence.quiescent,
                        quiescent=(participant_quiescent and tool_evidence.quiescent and lineage.quiescent and drained),
                        lineage=lineage.snapshot(),
                    )
                    continue
                if operation in {"coordinator-interrupt", "coordinator-interrupt-send"}:
                    if (
                        coordinator_interrupt_ipc is None
                        or not isinstance(coordinator_interrupt_identity, Mapping)
                    ):
                        refusal = SdkAdapterError(
                            "unsupported",
                            "coordinator interrupt channel is not bound",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    selection = command.get("payload_ref") if isinstance(command, Mapping) else None
                    try:
                        intent = lineage.prepare_coordinator_interrupt(
                            selection,
                            participant_id=coordinator_interrupt_identity.get("participant_id"),
                            runner_instance_id=coordinator_interrupt_identity.get("runner_instance_id"),
                            tool_evidence=tool_evidence,
                            # The ledger records only a current-invocation
                            # correlated parent observation.  The global turn
                            # flag is deliberately not an authority here.
                            parent_state=None,
                        )
                        interrupt_id = intent["interrupt"]["interrupt_id"]
                        intent_ack = await coordinator_interrupt_ipc.request_coordinator_interrupt_intent(intent)
                        lineage.mark_coordinator_interrupt_intent_persisted(interrupt_id, intent_ack)
                    except asyncio.TimeoutError:
                        refusal = SdkAdapterError(
                            "loader-failed",
                            "coordinator interrupt intent acknowledgement timed out",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    except SdkAdapterError as exc:
                        await emit_control("adapter-error", command, **exc.as_dict())
                        continue
                    schedule_current_coordinator_evidence()
                    if intent_ack.get("authorize_send") is not True:
                        await emit_control(
                            "coordinator-interrupt-ack",
                            command,
                            accepted=False,
                            authorize_send=False,
                            ack_kind="not-authorized",
                            interrupt_id=interrupt_id,
                        )
                        continue
                    validation_id = "validation-" + _uuid.uuid4().hex
                    validation_frame = {
                        "type": "coordinator-interrupt-validate",
                        **{
                            key: coordinator_interrupt_identity.get(key)
                            for key in _RUNNER_IDENTITY_FIELDS
                        },
                        "validation_id": validation_id,
                        "interrupt_id": interrupt_id,
                        "intent_digest": lineage.coordinator_interrupt_intent_digest(interrupt_id),
                    }
                    try:
                        validation = await coordinator_interrupt_ipc.request_coordinator_interrupt_validation(
                            validation_frame
                        )
                    except asyncio.TimeoutError:
                        refusal = SdkAdapterError(
                            "loader-failed",
                            "coordinator interrupt validation acknowledgement timed out",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    except SdkAdapterError as exc:
                        await emit_control("adapter-error", command, **exc.as_dict())
                        continue
                    if validation.get("validated") is not True:
                        refusal = SdkAdapterError(
                            str(validation.get("code") or "stale-generation"),
                            "coordinator interrupt send validation was refused",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    if not lineage.revalidate_coordinator_interrupt(interrupt_id, intent):
                        refusal = lineage.error or SdkAdapterError(
                            "stale-generation",
                            "coordinator interrupt target changed after durable validation",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    interrupt_callable = getattr(client, "interrupt", None)
                    if not callable(interrupt_callable):
                        refusal = SdkAdapterError(
                            "unsupported", "Claude SDK client cannot interrupt"
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    blocking_error = (
                        lineage.error
                        or hook_error.get("error")
                        or reader_error
                        or coordinator_evidence_error
                    )
                    if blocking_error is not None:
                        await emit_control("adapter-error", command, **blocking_error.as_dict())
                        continue
                    try:
                        # The marker precedes the await.  A timeout or lost
                        # receipt therefore retains uncertainty and cannot
                        # cause an automatic second SDK call.
                        lineage.mark_coordinator_interrupt_attempted(interrupt_id)
                        await _await_bounded(
                            _maybe_await(interrupt_callable()),
                            runner_spec.operation_deadline,
                        )
                        interrupted = True
                    except asyncio.TimeoutError:
                        refusal = SdkAdapterError(
                            "loader-failed",
                            "coordinator interrupt SDK operation deadline exceeded; replay is forbidden",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    except Exception:
                        refusal = SdkAdapterError(
                            "loader-failed",
                            "coordinator interrupt SDK operation failed; replay is forbidden",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    try:
                        runtime_frame = lineage.coordinator_interrupt_runtime_evidence(interrupt_id)
                        runtime_ack = await coordinator_interrupt_ipc.request_coordinator_interrupt_evidence(
                            runtime_frame
                        )
                        runtime_evidence = runtime_frame["evidence"]
                        if not _coordinator_interrupt_evidence_ack_matches(
                            runtime_ack,
                            runtime_evidence["evidence_id"],
                            runtime_evidence["interrupt_id"],
                        ):
                            raise SdkAdapterError(
                                "invalid",
                                "coordinator interrupt runtime evidence was not durably recorded",
                            )
                    except SdkAdapterError as exc:
                        await emit_control("adapter-error", command, **exc.as_dict())
                        continue
                    schedule_current_coordinator_evidence()
                    await emit_control(
                        "coordinator-interrupt-ack",
                        command,
                        accepted=True,
                        authorize_send=True,
                        ack_kind="accepted-interrupt",
                        interrupt_id=interrupt_id,
                    )
                    continue
                if operation in {"native-stop", "stop-task"}:
                    if native_stop_ipc is None or not isinstance(native_stop_identity, Mapping):
                        refusal = SdkAdapterError(
                            "unsupported",
                            "native stop channel is not bound",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    selection = command.get("payload_ref") if isinstance(command, Mapping) else None
                    try:
                        intent = lineage.prepare_native_stop(
                            selection,
                            participant_id=native_stop_identity.get("participant_id"),
                            runner_instance_id=native_stop_identity.get("runner_instance_id"),
                        )
                        stop_id = intent["stop"]["stop_id"]
                        intent_ack = await native_stop_ipc.request_native_stop_intent(intent)
                        lineage.mark_native_stop_intent_persisted(stop_id, intent_ack)
                    except asyncio.TimeoutError:
                        refusal = SdkAdapterError(
                            "loader-failed",
                            "native stop intent acknowledgement timed out",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    except SdkAdapterError as exc:
                        await emit_control("adapter-error", command, **exc.as_dict())
                        continue
                    pending_terminal = lineage.native_stop_pending_terminal_evidence(stop_id)
                    if pending_terminal is not None:
                        schedule_stop_evidence(pending_terminal)
                    if intent_ack.get("authorize_send") is not True:
                        await emit_control(
                            "native-stop-ack",
                            command,
                            accepted=False,
                            authorize_send=False,
                            ack_kind="not-authorized",
                            stop_id=stop_id,
                            task_id=intent["stop"]["task_id"],
                            terminal_evidence=pending_terminal is not None,
                        )
                        continue
                    if not lineage.revalidate_native_stop(stop_id, intent):
                        refusal = SdkAdapterError(
                            "stale-generation",
                            "native stop target changed after durable authorization",
                        )
                        if lineage.error is not None:
                            refusal = lineage.error
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    # The intent ACK only proves durable recording.  A hook
                    # or the continuous event reader may have observed a
                    # conflicting lifecycle fact while that ACK was in
                    # flight.  Refuse before marking the SDK call attempted.
                    blocking_error = lineage.error or hook_error.get("error") or reader_error
                    if blocking_error is not None:
                        await emit_control("adapter-error", command, **blocking_error.as_dict())
                        continue
                    stop_task = getattr(client, "stop_task", None)
                    if not callable(stop_task):
                        refusal = SdkAdapterError(
                            "unsupported",
                            "Claude SDK client cannot stop a native task",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    try:
                        # Mark before awaiting the SDK.  A timeout, lost reply,
                        # or process crash therefore cannot replay a task-ID
                        # control against a possibly reused task incarnation.
                        lineage.mark_native_stop_attempted(stop_id)
                        await _await_bounded(
                            _maybe_await(stop_task(intent["stop"]["task_id"])),
                            runner_spec.operation_deadline,
                        )
                    except asyncio.TimeoutError:
                        refusal = SdkAdapterError(
                            "loader-failed",
                            "native stop SDK operation deadline exceeded",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    except Exception:
                        refusal = SdkAdapterError(
                            "loader-failed",
                            "native stop SDK operation failed; replay is forbidden",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    try:
                        runtime_frame = lineage.native_stop_runtime_evidence(stop_id)
                        runtime_evidence = runtime_frame["evidence"]
                        runtime_ack = await native_stop_ipc.request_native_stop_evidence(runtime_frame)
                        if not _native_stop_evidence_ack_matches(
                            runtime_ack,
                            runtime_evidence["evidence_id"],
                            runtime_evidence["stop_id"],
                        ):
                            raise SdkAdapterError(
                                "invalid",
                                "native stop runtime evidence was not durably recorded",
                            )
                    except SdkAdapterError as exc:
                        # The SDK call already happened.  Surface the evidence
                        # failure without attempting the operation again.
                        await emit_control("adapter-error", command, **exc.as_dict())
                        continue
                    pending_terminal = lineage.native_stop_pending_terminal_evidence(stop_id)
                    if pending_terminal is not None:
                        schedule_stop_evidence(pending_terminal)
                    await emit_control(
                        "native-stop-ack",
                        command,
                        accepted=True,
                        authorize_send=True,
                        ack_kind="accepted-stop",
                        stop_id=stop_id,
                        task_id=intent["stop"]["task_id"],
                        terminal_evidence=pending_terminal is not None,
                    )
                    continue
                if operation in {"release", "release-held"}:
                    native_binding = (
                        command.get("payload_ref")
                        if isinstance(command, Mapping)
                        else None
                    )
                    if native_binding is None and (
                        native_swap_target_requires_bound_release
                        or native_swap_release_attempted
                    ):
                        refusal = SdkAdapterError(
                            "unsupported"
                            if native_swap_target_requires_bound_release
                            else "uncertain-effect",
                            "native swap target release requires its launch-bound authorization"
                            if native_swap_target_requires_bound_release
                            else "native swap release was already attempted; an unbound retry is forbidden",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    if native_binding is not None:
                        await perform_native_swap_release(command, native_binding)
                        continue
                    if not tracker.ready:
                        refusal = SdkAdapterError("loader-failed", "release requires ready-held initialization")
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    if not tool_evidence.quiescent:
                        refusal = SdkAdapterError("uncertain-effect", "release blocked by active or uncertain tool evidence")
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    if released:
                        refusal = SdkAdapterError("busy", "release has already occurred for this runner")
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    lineage_error = lineage.can_release()
                    if lineage_error is not None:
                        await emit_control("adapter-error", command, **lineage_error.as_dict())
                        continue
                    lineage_error = lineage.mark_released()
                    if lineage_error is not None:
                        await emit_control("adapter-error", command, **lineage_error.as_dict())
                        continue
                    # This transition intentionally does not send a prompt.
                    released = True
                    await emit_control("released", command, release_receipt=True, lineage=lineage.snapshot())
                    continue
                if operation in {"shutdown", "disconnect", "close", "stop"}:
                    await emit_control(
                        "shutdown-ack",
                        command,
                        shutdown_receipt=True,
                        active_turn=active_turn,
                        turn_terminal=turn_terminal,
                        drained=drained,
                        participant_quiescent=participant_quiescent,
                        tools_quiescent=tool_evidence.quiescent,
                        quiescent=(participant_quiescent and tool_evidence.quiescent and lineage.quiescent and drained),
                        lineage=lineage.snapshot(),
                        evidence={"tools": tool_evidence.snapshot()},
                    )
                    stop_requested = True
                    return
                if operation in {"ping", "status"}:
                    reader_evidence = {
                        # These are runner-owned observations from the
                        # persistent reader.  In particular, ``reader_cursor``
                        # is never advanced by this status operation.
                        "reader_done": reader_done.is_set(),
                        "reader_frame_inflight": reader_frame_inflight,
                        "reader_cursor": last_fully_processed_cursor,
                        "hooks_inflight": hook_activity.get("hooks_inflight", 0),
                        "stop_evidence_inflight": sum(
                            1 for task in stop_evidence_tasks if not task.done()
                        ),
                        "coordinator_evidence_inflight": sum(
                            1 for task in coordinator_evidence_tasks if not task.done()
                        ),
                        "native_child_observation_inflight": int(
                            native_child_observation_inflight
                        ),
                        "native_child_observation_error": bool(
                            lineage.error is not None
                            and any(
                                "child observation" in str(item.get("reason", ""))
                                for item in lineage.uncertainties
                            )
                        ),
                        "reader_error": reader_error is not None,
                        "control_error": control_error is not None,
                        "task_failure": task_failure is not None,
                    }
                    await emit_control(
                        "status",
                        command,
                        ready=tracker.ready,
                        released=released,
                        interrupted=interrupted,
                        active_turn=active_turn,
                        turn_terminal=turn_terminal,
                        drained=drained,
                        participant_quiescent=participant_quiescent,
                        tools_quiescent=tool_evidence.quiescent,
                        quiescent=(participant_quiescent and tool_evidence.quiescent and lineage.quiescent and drained),
                        tools=tool_evidence.snapshot(),
                        lineage=lineage.snapshot(),
                        reader_evidence=reader_evidence,
                    )
                    continue
                if operation == "prepare-invocation":
                    if not coordinator_enabled:
                        refusal = SdkAdapterError(
                            "unsupported",
                            "native invocation reservation requires coordinator lineage mode",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    try:
                        reservation = _checkpoint_terminal_invocation(
                            command.get("payload_ref"),
                            checkpoint_tool_evidence=tool_evidence,
                        )
                    except SdkAdapterError as exc:
                        await emit_control("adapter-error", command, **exc.as_dict())
                        continue
                    await emit_control("prepare-invocation-ack", command, **reservation)
                    continue
                if operation in {"query", "send", "message", "user"}:
                    if not released:
                        refusal = SdkAdapterError("busy", "model/user query is held until explicit release")
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    request_id: Optional[str] = None
                    message_id_value: Optional[str] = None
                    if isinstance(command, Mapping):
                        raw_request_id = command.get("request_id")
                        raw_message_id = _first_nonempty(
                            command.get("message_id"),
                            command.get("id"),
                        )
                        if raw_request_id is not None:
                            if not isinstance(raw_request_id, str) or not raw_request_id.strip():
                                refusal = SdkAdapterError("invalid", "query request_id must be a non-empty string")
                                await emit_control("adapter-error", command, **refusal.as_dict())
                                continue
                            request_id = raw_request_id.strip()
                        if not isinstance(raw_message_id, str) or not raw_message_id.strip():
                            refusal = SdkAdapterError(
                                "invalid",
                                "released query requires a non-empty correlated message_id",
                            )
                            await emit_control("adapter-error", command, **refusal.as_dict())
                            continue
                        message_id_value = raw_message_id.strip()
                    else:
                        # The in-process legacy seam has no wire request ID;
                        # generate one internally while keeping the durable
                        # mailbox message ID distinct for SDK correlation.
                        message_id_value = None
                    if message_id_value is None:
                        refusal = SdkAdapterError(
                            "invalid",
                            "released query requires a non-empty correlated message_id",
                        )
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    if request_id is None:
                        request_id = str(_uuid.uuid4())
                    if request_id in dispatched_request_ids:
                        refusal = SdkAdapterError(
                            "busy",
                            f"request_id {request_id!r} was already dispatched",
                        )
                        await emit_control(
                            "adapter-error",
                            command,
                            **refusal.as_dict(),
                            request_id=request_id,
                            message_id=message_id_value,
                        )
                        continue
                    if message_id_value in dispatched_message_ids:
                        refusal = SdkAdapterError(
                            "busy",
                            f"message_id {message_id_value!r} was already dispatched",
                        )
                        await emit_control(
                            "adapter-error",
                            command,
                            **refusal.as_dict(),
                            request_id=request_id,
                            message_id=message_id_value,
                        )
                        continue
                    prompt: Any = command
                    if isinstance(command, Mapping):
                        prompt = _first_nonempty(
                            command.get("payload_ref"),
                            command.get("prompt"),
                            command.get("message"),
                            command.get("payload"),
                        )
                    if prompt is None or prompt == "":
                        refusal = SdkAdapterError("invalid", "released query requires an explicit message")
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    query = getattr(client, "query", None)
                    if query is None:
                        refusal = SdkAdapterError("unsupported", "Claude SDK client cannot send a released query")
                        await emit_control("adapter-error", command, **refusal.as_dict())
                        continue
                    # Reserve before the SDK call.  If the process dies or the
                    # call times out, a retry remains uncertain and cannot send
                    # either correlated payload or wire request a second time.
                    dispatched_request_ids.add(request_id)
                    dispatched_message_ids.add(message_id_value)
                    expected_result_message_ids.add(message_id_value)
                    # The mailbox ID is durable and known before send; the
                    # random transport request ID is not controller authority.
                    reservation_binding = command.get("reservation_binding")
                    lineage_error = lineage.begin_invocation(
                        message_id_value,
                        message_id_value,
                        reservation_binding=(
                            reservation_binding
                            if isinstance(reservation_binding, Mapping)
                            else None
                        ),
                    )
                    if lineage_error is not None:
                        expected_result_message_ids.discard(message_id_value)
                        await emit_control("adapter-error", command, **lineage_error.as_dict(), request_id=request_id, message_id=message_id_value)
                        continue
                    if coordinator_enabled:
                        parent_error = lineage.note_parent_state(
                            active=True,
                            drained=False,
                            invocation_id=message_id_value,
                        )
                        if parent_error is not None:
                            expected_result_message_ids.discard(message_id_value)
                            await emit_control(
                                "adapter-error",
                                command,
                                **parent_error.as_dict(),
                                request_id=request_id,
                                message_id=message_id_value,
                            )
                            continue
                    active_turn = True
                    turn_terminal = False
                    drained = False
                    participant_quiescent = False
                    try:
                        if fake_factory:
                            query_call = query(prompt, message_id_value)
                        else:
                            query_call = query(prompt)
                        await _await_bounded(_maybe_await(query_call), runner_spec.operation_deadline)
                    except asyncio.TimeoutError:
                        refusal = SdkAdapterError("loader-failed", "released query operation deadline exceeded")
                        await emit_control("adapter-error", command, **refusal.as_dict(), request_id=request_id)
                        continue
                    # A fake/SDK transport may enqueue a correlated result
                    # synchronously before returning from ``query``.  Give the
                    # continuous reader one scheduling turn to validate an
                    # explicit message ID before acknowledging accepted-send;
                    # this does not wait for model completion.
                    await asyncio.sleep(0)
                    if reader_error is not None:
                        raise reader_error
                    await emit_control(
                        "query-dispatched",
                        command,
                        request_id=request_id,
                        message_id=str(message_id_value),
                        accepted=True,
                        ack_kind="accepted-send",
                    )
                    continue
                await emit_control(
                    "adapter-error",
                    command,
                    code="invalid",
                    message=f"unsupported control operation {operation!r}",
                )
        except asyncio.CancelledError:
            raise
        except SdkAdapterError as exc:
            control_error = exc
            await emit_control("adapter-error", None, **exc.as_dict())
        except Exception as exc:  # noqa: BLE001
            control_error = SdkAdapterError("loader-failed", f"SDK control task failed: {exc}")
            await emit_control("adapter-error", None, **control_error.as_dict())
        finally:
            control_done.set()

    try:
        try:
            await _await_bounded(
                _connect_promptless(client),
                runner_spec.startup_deadline,
            )
        except asyncio.TimeoutError as exc:
            raise SdkAdapterError("loader-failed", "Claude SDK startup deadline exceeded") from exc
        except SdkAdapterError:
            raise
        except Exception as exc:  # noqa: BLE001
            # The official SDK raises when an error result arrives before init;
            # retain the same stable loader-failed class as the tracker path.
            raise SdkAdapterError("loader-failed", f"Claude SDK promptless connect failed: {exc}") from exc

        cached_init = await _initialization_event(client)
        if cached_init is not None:
            await emit_serial(cached_init)
            tracker.observe(cached_init)
            if tracker.error is not None:
                raise tracker.error
            if tracker.ready and not ready_emitted:
                await emit_ready_held()
        reader_task = asyncio.create_task(reader(), name="lane-managed-sdk-reader")
        control_task = asyncio.create_task(control_loop(), name="lane-managed-sdk-controls")
        try:
            while True:
                if reader_done.is_set() or stop_requested:
                    break
                if reader_error is not None:
                    break
                if control_done.is_set():
                    # A finite control iterable has ended.  The continuous
                    # reader cannot keep a supervisor operation alive forever
                    # in that case, so disconnect after its current event.
                    # Give a just-dispatched fake/runtime result one event-loop
                    # turn (and a small bounded drain window) to be observed
                    # before cancelling the reader.
                    await asyncio.sleep(0.05)
                    break
                # The operation deadline bounds each control action, not the
                # lifetime of a held participant.  A supervisor may keep a
                # ready runner held for hours while no model work is released.
                await asyncio.sleep(0.05)
        finally:
            for task in (control_task, reader_task):
                if not task.done():
                    task.cancel()
            task_results = await asyncio.gather(
                control_task,
                reader_task,
                return_exceptions=True,
            )
            for result in task_results:
                if isinstance(result, asyncio.CancelledError):
                    continue
                if isinstance(result, SdkAdapterError):
                    task_failure = result
                    break
                if isinstance(result, BaseException):
                    task_failure = SdkAdapterError(
                        "loader-failed",
                        f"SDK background task failed: {result}",
                    )
                    break

        if stop_evidence_tasks:
            await _await_bounded(
                asyncio.gather(*list(stop_evidence_tasks), return_exceptions=True),
                runner_spec.operation_deadline,
            )
        if stop_evidence_error is not None:
            raise stop_evidence_error

        schedule_current_coordinator_evidence()
        if coordinator_evidence_tasks:
            await _await_bounded(
                asyncio.gather(*list(coordinator_evidence_tasks), return_exceptions=True),
                runner_spec.operation_deadline,
            )
        if coordinator_evidence_error is not None:
            raise coordinator_evidence_error

        if reader_error is not None:
            raise reader_error
        if control_error is not None:
            raise control_error
        if task_failure is not None:
            raise task_failure
        if not tracker.ready:
            # If a finite fake reader ended before init, preserve a specific
            # loader refusal rather than claiming a held participant.
            tracker.finalize()
        if not tool_evidence.quiescent or not lineage.quiescent:
            await emit_serial(
                {
                    "type": "held-uncertain",
                    "tools": tool_evidence.snapshot(),
                    "lineage": lineage.snapshot(),
                }
            )
        tracker_evidence = tracker.snapshot()
        tool_snapshot = tool_evidence.snapshot()
        process_snapshot = dict(process_evidence)
        process_snapshot.setdefault("exited", False)
        process_snapshot.setdefault("group_excluded", False)
        lineage_snapshot = lineage.snapshot()
        participant_quiescent = bool(participant_quiescent and lineage_snapshot["quiescent"])
        evidence = {
            "ready": tracker.ready,
            "released": released,
            "active_turn": active_turn,
            "turn_terminal": turn_terminal,
            "drained": drained,
            "participant_quiescent": participant_quiescent,
            "tools_quiescent": bool(tool_snapshot["quiescent"] and lineage_snapshot["quiescent"]),
            "quiescent": bool(
                participant_quiescent
                and turn_terminal
                and drained
                and tool_snapshot["quiescent"]
                and lineage_snapshot["quiescent"]
            ),
            "process": process_snapshot,
            "initialization": {
                "account_email": tracker_evidence.get("account_email"),
                "permission_mode": tracker_evidence.get("permission_mode"),
                "model": tracker_evidence.get("model") or runner_spec.model,
                "fingerprint": dict(runner_spec.fingerprint),
            },
            "tools": tool_snapshot,
            "uncertain_effects": list(tool_snapshot.get("uncertain", ())),
            "lineage": lineage_snapshot,
            "native_swap_release_boundary": (
                None
                if native_swap_release_boundary is None
                else copy.deepcopy(native_swap_release_boundary)
            ),
        }
        return {
            "ok": True,
            "ready": tracker.ready,
            "released": released,
            "interrupted": interrupted,
            "session_id": runner_spec.session_id,
            "lineage": lineage_snapshot,
            "evidence": evidence,
        }
    finally:
        primary_exception = sys.exc_info()[1]
        try:
            await _await_bounded(
                _disconnect(client),
                runner_spec.operation_deadline,
            )
        except asyncio.TimeoutError as exc:
            if primary_exception is None:
                raise SdkAdapterError("loader-failed", "Claude SDK disconnect deadline exceeded") from exc
        except Exception as exc:  # noqa: BLE001
            # Never hide the primary adapter refusal.  If there was no primary
            # error, a disconnect failure is still an explicit refusal.
            if primary_exception is None:
                raise SdkAdapterError("unknown", f"Claude SDK disconnect failed: {exc}") from exc


class _BoundedJsonLines:
    """Async stdin/stdout bridge enforcing the one-megabyte frame contract."""

    def __init__(self, reader: Any, writer: Any, limit: int = MAX_FRAME_BYTES):
        self.reader = reader
        self.writer = writer
        self.limit = max(1024, min(int(limit), MAX_FRAME_BYTES))
        self.write_lock = asyncio.Lock()
        self._buffer = bytearray()

    async def _read_frame_bytes(self) -> bytes:
        """Read one line without leaving a blocking executor at shutdown."""

        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                frame = bytes(self._buffer[: newline + 1])
                del self._buffer[: newline + 1]
                return frame
            if len(self._buffer) > self.limit:
                raise SdkAdapterError("invalid", "control frame exceeds 1 MiB limit")

            fileno = None
            try:
                fileno = self.reader.fileno()
            except (AttributeError, OSError, ValueError):
                fileno = None
            if fileno is None:
                # In-memory fake streams are finite and do not need a thread;
                # production stdin always exposes a POSIX fd.  Keep this
                # fallback for Windows/fake callers while preserving the
                # cancellable fd path where it matters.
                raw = self.reader.readline(self.limit + 1)
                if isinstance(raw, str):
                    return raw.encode("utf-8", "replace")
                return raw

            loop = asyncio.get_running_loop()
            waiter: asyncio.Future[bytes] = loop.create_future()

            def on_readable() -> None:
                try:
                    chunk = os.read(fileno, min(65536, self.limit + 1 - len(self._buffer)))
                    if not chunk:
                        if not waiter.done():
                            if self._buffer:
                                waiter.set_exception(
                                    SdkAdapterError(
                                        "invalid",
                                        "control frame ended before its newline",
                                    )
                                )
                            else:
                                waiter.set_result(b"")
                        return
                    self._buffer.extend(chunk)
                    if len(self._buffer) > self.limit:
                        if not waiter.done():
                            waiter.set_exception(
                                SdkAdapterError("invalid", "control frame exceeds 1 MiB limit")
                            )
                        return
                    if b"\n" in self._buffer and not waiter.done():
                        newline = self._buffer.find(b"\n")
                        frame = bytes(self._buffer[: newline + 1])
                        del self._buffer[: newline + 1]
                        waiter.set_result(frame)
                except BaseException as exc:  # noqa: BLE001
                    if not waiter.done():
                        waiter.set_exception(exc)

            try:
                loop.add_reader(fileno, on_readable)
            except (NotImplementedError, OSError):
                # Some event loops (notably Windows' Proactor) cannot watch
                # stdin.  There is no safe way to cancel a TextIO readline
                # there; use a short-lived executor only as a compatibility
                # fallback and let the process owner close stdin on shutdown.
                raw = await asyncio.to_thread(self.reader.readline, self.limit + 1)
                if isinstance(raw, str):
                    return raw.encode("utf-8", "replace")
                return raw
            try:
                return await waiter
            finally:
                try:
                    loop.remove_reader(fileno)
                except (NotImplementedError, OSError):
                    pass

    async def read(self) -> dict[str, Any]:
        raw = await self._read_frame_bytes()
        if raw in (b"", ""):
            raise StopAsyncIteration
        if isinstance(raw, str):
            encoded_len = len(raw.encode("utf-8", "replace"))
            text = raw
        else:
            encoded_len = len(raw)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SdkAdapterError("invalid", "control frame is not UTF-8") from exc
        if encoded_len > self.limit:
            raise SdkAdapterError("invalid", "control frame exceeds 1 MiB limit")
        try:
            value = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SdkAdapterError("invalid", "control frame is not valid JSON") from exc
        if not isinstance(value, Mapping):
            raise SdkAdapterError("invalid", "control frame must be a JSON object")
        return dict(value)

    async def write(self, value: Mapping[str, Any]) -> None:
        try:
            text = json.dumps(dict(value), ensure_ascii=False, separators=(",", ":")) + "\n"
        except (TypeError, ValueError) as exc:
            raise SdkAdapterError("invalid", "adapter event is not JSON serializable") from exc
        if len(text.encode("utf-8")) > self.limit:
            raise SdkAdapterError("invalid", "adapter event exceeds 1 MiB limit")
        async with self.write_lock:
            data = text.encode("utf-8")
            fileno = None
            try:
                fileno = self.writer.fileno()
            except (AttributeError, OSError, ValueError):
                fileno = None
            if fileno is not None and os.name == "posix":
                await self._write_fd(fileno, data)
                return

            # In-memory fakes and event loops without POSIX descriptor support
            # have no cancellable write primitive.  Their writes are bounded
            # to one frame and are expected not to block; production pipes use
            # the nonblocking descriptor path above.
            def write_frame() -> None:
                try:
                    self.writer.write(text)
                except TypeError:
                    self.writer.write(data)
                flush = getattr(self.writer, "flush", None)
                if callable(flush):
                    flush()

            await asyncio.to_thread(write_frame)

    async def _write_fd(self, fileno: int, data: bytes) -> None:
        """Write a bounded frame through a cancellable nonblocking pipe."""

        try:
            was_blocking = os.get_blocking(fileno)
            os.set_blocking(fileno, False)
        except (AttributeError, OSError, ValueError):
            # A descriptor may be supplied by a test double with no blocking
            # controls; fall back to its file object's bounded write path.
            raise SdkAdapterError("unsupported", "runner pipe cannot be made nonblocking")

        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[None] = loop.create_future()
        offset = 0

        def on_writable() -> None:
            nonlocal offset
            if waiter.done():
                return
            try:
                written = os.write(fileno, data[offset:])
                if written <= 0:
                    raise BrokenPipeError("runner control pipe closed")
                offset += written
                if offset >= len(data):
                    waiter.set_result(None)
            except BlockingIOError:
                return
            except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                waiter.set_exception(SdkAdapterError("loader-failed", f"runner control pipe write failed: {exc}"))

        try:
            try:
                loop.add_writer(fileno, on_writable)
            except (NotImplementedError, OSError) as exc:
                raise SdkAdapterError("unsupported", "runner pipe has no cancellable writer") from exc
            on_writable()
            await waiter
        finally:
            try:
                loop.remove_writer(fileno)
            except (NotImplementedError, OSError):
                pass
            try:
                os.set_blocking(fileno, was_blocking)
            except (AttributeError, OSError, ValueError):
                pass


_ADMISSION_ACK_FIELDS = (
    "admission_id", "owner_generation", "lineage_id", "runner_incarnation",
    "invocation_id", "tool_use_id", "trusted_definition_digest",
)
_RUNNER_IDENTITY_FIELDS = ("participant_id", "session_id", "runner_instance_id")


def _admission_ack_matches(ack: Any, admission: Mapping[str, Any]) -> bool:
    return (
        isinstance(ack, Mapping)
        and type(ack.get("accepted")) is bool
        and all(key in ack and key in admission
                and type(ack[key]) is type(admission[key])
                and ack[key] == admission[key] for key in _ADMISSION_ACK_FIELDS)
    )


def _native_stop_intent_ack_matches(ack: Any, stop_id: str) -> bool:
    if not isinstance(ack, Mapping):
        return False
    if set(ack) - {"recorded", "authorize_send", "stop_id", "code"}:
        return False
    return (
        type(ack.get("recorded")) is bool
        and type(ack.get("authorize_send")) is bool
        and ack.get("stop_id") == stop_id
        and ("code" not in ack or isinstance(ack.get("code"), str))
    )


def _native_stop_evidence_ack_matches(ack: Any, evidence_id: str, stop_id: str) -> bool:
    if not isinstance(ack, Mapping):
        return False
    if set(ack) - {"recorded", "evidence_id", "stop_id", "code"}:
        return False
    return (
        ack.get("recorded") is True
        and ack.get("evidence_id") == evidence_id
        and ack.get("stop_id") == stop_id
        and ("code" not in ack or isinstance(ack.get("code"), str))
    )


def _coordinator_interrupt_intent_ack_matches(
    ack: Any, interrupt_id: str
) -> bool:
    """Validate the narrow acknowledgement for one interrupt intent.

    Coordinator-wide interrupts use their own wire namespace and durable
    source transaction.  In particular, a native-stop acknowledgement must
    never satisfy this matcher (or vice versa).
    """

    if not isinstance(ack, Mapping):
        return False
    if set(ack) - {"recorded", "authorize_send", "interrupt_id", "code"}:
        return False
    return (
        type(ack.get("recorded")) is bool
        and type(ack.get("authorize_send")) is bool
        and ack.get("interrupt_id") == interrupt_id
        and not (ack.get("authorize_send") is True and ack.get("recorded") is False)
        and ("code" not in ack or isinstance(ack.get("code"), str))
    )


def _coordinator_interrupt_evidence_ack_matches(
    ack: Any, evidence_id: str, interrupt_id: str
) -> bool:
    """Validate one independent coordinator-interrupt evidence acknowledgement."""

    if not isinstance(ack, Mapping):
        return False
    if set(ack) - {"recorded", "evidence_id", "interrupt_id", "code"}:
        return False
    return (
        type(ack.get("recorded")) is bool
        and ack.get("evidence_id") == evidence_id
        and ack.get("interrupt_id") == interrupt_id
        and ("code" not in ack or isinstance(ack.get("code"), str))
    )


def _coordinator_interrupt_validation_ack_matches(
    ack: Any, validation_id: str, interrupt_id: str, intent_digest: str
) -> bool:
    """Validate the validate-only reply for one interrupt waiter.

    Validation is deliberately a third wire namespace.  It returns eligibility
    only; it cannot carry or recreate ``authorize_send`` and it is correlated
    to both the fresh validation ID and the immutable full intent digest.
    """

    if not isinstance(ack, Mapping):
        return False
    if set(ack) - {"validated", "validation_id", "interrupt_id", "intent_digest", "code"}:
        return False
    return (
        type(ack.get("validated")) is bool
        and ack.get("validation_id") == validation_id
        and ack.get("interrupt_id") == interrupt_id
        and ack.get("intent_digest") == intent_digest
        and ("code" not in ack or isinstance(ack.get("code"), str))
    )


class _NativeAdmissionIPC:
    """Runner-side waiters; only the independent stdin reader resolves them.

    The SDK query/control task and its event reader may both be inside a hook
    awaiting this channel. Acknowledgements must never enter their control
    queue or require either task to advance.
    """

    def __init__(self, bridge: _BoundedJsonLines, identity: Mapping[str, Any]):
        self.bridge = bridge
        self.identity = {key: identity[key] for key in _RUNNER_IDENTITY_FIELDS}
        self.pending: dict[str, tuple[dict[str, Any], asyncio.Future[Any]]] = {}
        self.coordinator_interrupt_pending: dict[
            str, tuple[dict[str, Any], asyncio.Future[Any]]
        ] = {}
        self.coordinator_interrupt_validation_pending: dict[
            str, tuple[dict[str, Any], asyncio.Future[Any]]
        ] = {}
        self.native_swap_release_pending: dict[
            str, tuple[dict[str, Any], asyncio.Future[Any]]
        ] = {}
        self.native_child_observation_pending: dict[
            str, tuple[dict[str, Any], asyncio.Future[Any]]
        ] = {}
        self.native_child_observation_ids: set[str] = set()
        self.native_child_observation_run_counts: dict[str, int] = {}
        # A positive whole-roster authorization is a one-shot fact for this
        # authenticated runner connection.  Keep consumed IDs bounded but do
        # not evict them: eviction would let a delayed/replayed true ACK grant
        # a second send.  A reconnect gets a fresh set and must still obtain a
        # durable false acknowledgement from the controller.
        self._coordinator_interrupt_authorized_ids: set[str] = set()
        self.error: Optional[SdkAdapterError] = None

    def close(self, error: Optional[SdkAdapterError] = None) -> None:
        self.error = error or SdkAdapterError("loader-failed", "native admission channel closed")
        for pending in (
            self.pending,
            self.coordinator_interrupt_pending,
            self.coordinator_interrupt_validation_pending,
            self.native_swap_release_pending,
            self.native_child_observation_pending,
        ):
            for _, future in pending.values():
                if not future.done():
                    future.set_exception(self.error)

    async def _request(
        self,
        key: str,
        frame: Mapping[str, Any],
        *,
        timeout_message: str,
        pending: Optional[dict[str, tuple[dict[str, Any], asyncio.Future[Any]]]] = None,
    ) -> Mapping[str, Any]:
        if pending is None:
            pending = self.pending
        if self.error is not None:
            raise self.error
        if key in pending or len(pending) >= MAX_NATIVE_CHILD_RECORDS:
            raise SdkAdapterError("busy", "native transaction waiter is duplicate or full")
        future = asyncio.get_running_loop().create_future()
        pending[key] = (copy.deepcopy(dict(frame)), future)

        async def send_and_wait() -> Any:
            await self.bridge.write(dict(frame))
            result = await future
            if self.error is not None:
                raise self.error
            return result

        try:
            return await _await_bounded(send_and_wait(), _NATIVE_ADMISSION_DEADLINE)
        except asyncio.TimeoutError as exc:
            raise SdkAdapterError("loader-failed", timeout_message) from exc
        finally:
            pending.pop(key, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                # Also consume a concurrent EOF failure when writing failed.
                future.exception()

    async def request(self, admission: Mapping[str, Any]) -> Mapping[str, Any]:
        admission = copy.deepcopy(dict(admission))
        admission_id = _wire_id(admission.get("admission_id"), "admission_id")
        return await self._request(
            f"native-admission:{admission_id}",
            {
                "type": "native-admission-intent",
                **self.identity,
                "admission_id": admission_id,
                "admission": admission,
            },
            timeout_message="native admission acknowledgement timed out",
        )

    async def request_native_stop_intent(self, frame: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(frame, Mapping) or frame.get("type") != "native-stop-intent":
            raise SdkAdapterError("invalid", "native stop intent frame is malformed")
        stop = frame.get("stop")
        if not isinstance(stop, Mapping):
            raise SdkAdapterError("invalid", "native stop intent has no stop body")
        stop_id = _wire_id(stop.get("stop_id"), "stop_id")
        for key in _RUNNER_IDENTITY_FIELDS:
            if frame.get(key) != self.identity[key]:
                raise SdkAdapterError("stale-generation", "native stop intent identity changed")
        return await self._request(
            f"native-stop-intent:{stop_id}",
            {"type": "native-stop-intent", **self.identity, "stop": copy.deepcopy(dict(stop))},
            timeout_message="native stop intent acknowledgement timed out",
        )

    async def request_native_stop_evidence(self, frame: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(frame, Mapping) or frame.get("type") != "native-stop-evidence":
            raise SdkAdapterError("invalid", "native stop evidence frame is malformed")
        evidence = frame.get("evidence")
        if not isinstance(evidence, Mapping):
            raise SdkAdapterError("invalid", "native stop evidence has no evidence body")
        evidence_id = _wire_id(evidence.get("evidence_id"), "evidence_id")
        stop_id = _wire_id(evidence.get("stop_id"), "stop_id")
        for key in _RUNNER_IDENTITY_FIELDS:
            if frame.get(key) != self.identity[key]:
                raise SdkAdapterError("stale-generation", "native stop evidence identity changed")
        return await self._request(
            f"native-stop-evidence:{evidence_id}",
            {"type": "native-stop-evidence", **self.identity, "evidence": copy.deepcopy(dict(evidence))},
            timeout_message="native stop evidence acknowledgement timed out",
        )

    async def request_coordinator_interrupt_intent(
        self, frame: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Persist one coordinator-wide interrupt intent through the bridge.

        This is intentionally a separate transaction namespace from native
        task stops.  The adapter only authenticates the current runner
        connection and bounded outer frame; the controller owns the complete
        interrupt body and source-incarnation exclusion.
        """

        expected = {
            "type", "participant_id", "session_id", "runner_instance_id",
            "interrupt",
        }
        if not isinstance(frame, Mapping) or set(frame) != expected:
            raise SdkAdapterError(
                "invalid", "coordinator interrupt intent frame is malformed"
            )
        if frame.get("type") != "coordinator-interrupt-intent":
            raise SdkAdapterError(
                "invalid", "coordinator interrupt intent frame is malformed"
            )
        interrupt = frame.get("interrupt")
        if not isinstance(interrupt, Mapping):
            raise SdkAdapterError(
                "invalid", "coordinator interrupt intent has no interrupt body"
            )
        interrupt_id = _wire_id(interrupt.get("interrupt_id"), "interrupt_id")
        for key in _RUNNER_IDENTITY_FIELDS:
            if frame.get(key) != self.identity[key]:
                raise SdkAdapterError(
                    "stale-generation",
                    "coordinator interrupt intent identity changed",
                )
        if (
            interrupt_id not in self._coordinator_interrupt_authorized_ids
            and len(self._coordinator_interrupt_authorized_ids)
            >= MAX_NATIVE_LIFECYCLE_EVENTS
        ):
            raise SdkAdapterError(
                "busy", "coordinator interrupt authorization history is full"
            )
        return await self._request(
            f"coordinator-interrupt-intent:{interrupt_id}",
            {
                "type": "coordinator-interrupt-intent",
                **self.identity,
                "interrupt": copy.deepcopy(dict(interrupt)),
            },
            timeout_message=(
                "coordinator interrupt intent acknowledgement timed out"
            ),
            pending=self.coordinator_interrupt_pending,
        )

    async def request_coordinator_interrupt_evidence(
        self, frame: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Persist one independent coordinator-wide drain fact."""

        expected = {
            "type", "participant_id", "session_id", "runner_instance_id",
            "evidence",
        }
        if not isinstance(frame, Mapping) or set(frame) != expected:
            raise SdkAdapterError(
                "invalid", "coordinator interrupt evidence frame is malformed"
            )
        if frame.get("type") != "coordinator-interrupt-evidence":
            raise SdkAdapterError(
                "invalid", "coordinator interrupt evidence frame is malformed"
            )
        evidence = frame.get("evidence")
        if not isinstance(evidence, Mapping):
            raise SdkAdapterError(
                "invalid", "coordinator interrupt evidence has no evidence body"
            )
        evidence_id = _wire_id(evidence.get("evidence_id"), "evidence_id")
        interrupt_id = _wire_id(evidence.get("interrupt_id"), "interrupt_id")
        for key in _RUNNER_IDENTITY_FIELDS:
            if frame.get(key) != self.identity[key]:
                raise SdkAdapterError(
                    "stale-generation",
                    "coordinator interrupt evidence identity changed",
                )
        return await self._request(
            f"coordinator-interrupt-evidence:{evidence_id}",
            {
                "type": "coordinator-interrupt-evidence",
                **self.identity,
                "evidence": copy.deepcopy(dict(evidence)),
            },
            timeout_message=(
                "coordinator interrupt evidence acknowledgement timed out"
            ),
            pending=self.coordinator_interrupt_pending,
        )

    async def request_coordinator_interrupt_validation(
        self, frame: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Ask the durable controller to revalidate one already-recorded intent."""

        expected = {
            "type", "participant_id", "session_id", "runner_instance_id",
            "validation_id", "interrupt_id", "intent_digest",
        }
        if not isinstance(frame, Mapping) or set(frame) != expected:
            raise SdkAdapterError(
                "invalid", "coordinator interrupt validation frame is malformed"
            )
        if frame.get("type") != "coordinator-interrupt-validate":
            raise SdkAdapterError(
                "invalid", "coordinator interrupt validation frame is malformed"
            )
        validation_id = _wire_id(frame.get("validation_id"), "validation_id")
        interrupt_id = _wire_id(frame.get("interrupt_id"), "interrupt_id")
        intent_digest = frame.get("intent_digest")
        if (
            not isinstance(intent_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", intent_digest)
        ):
            raise SdkAdapterError("invalid", "coordinator interrupt intent digest is malformed")
        for key in _RUNNER_IDENTITY_FIELDS:
            if frame.get(key) != self.identity[key]:
                raise SdkAdapterError(
                    "stale-generation",
                    "coordinator interrupt validation identity changed",
                )
        return await self._request(
            f"coordinator-interrupt-validate:{validation_id}",
            {
                "type": "coordinator-interrupt-validate",
                **self.identity,
                "validation_id": validation_id,
                "interrupt_id": interrupt_id,
                "intent_digest": intent_digest,
            },
            timeout_message="coordinator interrupt validation acknowledgement timed out",
            pending=self.coordinator_interrupt_validation_pending,
        )

    async def request_native_swap_release(
        self, frame: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Request the one private controller authorization for native release."""

        expected = {
            "type", "participant_id", "session_id", "runner_instance_id",
            "validation_id", "binding",
        }
        if not isinstance(frame, Mapping) or set(frame) != expected:
            raise SdkAdapterError(
                "invalid", "native swap release authorization frame is malformed"
            )
        if frame.get("type") != "native-swap-release-authorize":
            raise SdkAdapterError(
                "invalid", "native swap release authorization frame is malformed"
            )
        validation_id = _wire_id(frame.get("validation_id"), "validation_id")
        binding = _native_swap_binding(frame.get("binding"))
        for key in _RUNNER_IDENTITY_FIELDS:
            if frame.get(key) != self.identity[key]:
                raise SdkAdapterError(
                    "stale-generation",
                    "native swap release authorization identity changed",
                )
        return await self._request(
            f"native-swap-release:{validation_id}",
            {
                "type": "native-swap-release-authorize",
                **self.identity,
                "validation_id": validation_id,
                "binding": binding,
            },
            timeout_message="native swap release authorization acknowledgement timed out",
            pending=self.native_swap_release_pending,
        )

    async def request_native_child_observation(
        self, frame: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Persist one exact joined-child observation through the IPC reader."""

        if (
            not isinstance(frame, Mapping)
            or set(frame) != set(_NATIVE_CHILD_OBSERVATION_FRAME_FIELDS)
            or frame.get("type") != "native-child-observation"
        ):
            raise SdkAdapterError("invalid", "native child observation frame is malformed")
        for key in _RUNNER_IDENTITY_FIELDS:
            if frame.get(key) != self.identity[key]:
                raise SdkAdapterError(
                    "stale-generation", "native child observation identity changed"
                )
        observation = _native_child_observation(frame.get("observation"))
        observation_id = observation["observation_id"]
        run_id = _native_child_observation_run_id(observation)
        if (
            observation_id not in self.native_child_observation_ids
            and run_id not in self.native_child_observation_run_counts
            and len(self.native_child_observation_run_counts) >= MAX_NATIVE_CHILD_RUNS
        ):
            raise SdkAdapterError(
                "busy", "native child observation child-run history is full"
            )
        if (
            observation_id not in self.native_child_observation_ids
            and self.native_child_observation_run_counts.get(run_id, 0)
            >= MAX_NATIVE_CHILD_OBSERVATIONS_PER_RUN
        ):
            raise SdkAdapterError(
                "busy", "native child observation history is full for this child run"
            )
        self.native_child_observation_ids.add(observation_id)
        if observation_id not in self.native_child_observation_pending:
            self.native_child_observation_run_counts[run_id] = (
                self.native_child_observation_run_counts.get(run_id, 0) + 1
            )
        return await self._request(
            f"native-child-observation:{observation_id}",
            {
                "type": "native-child-observation",
                **self.identity,
                "observation": observation,
            },
            timeout_message="native child observation acknowledgement timed out",
            pending=self.native_child_observation_pending,
        )

    def receive(self, frame: Mapping[str, Any]) -> None:
        operation = frame.get("operation")
        shape_valid = True
        coordinator_positive = False
        if operation == "native-admission-ack":
            correlation = frame.get("admission_id")
            key = f"native-admission:{correlation}"
            body, future = self.pending.get(key, ({}, None))
            valid = isinstance(correlation, str) and isinstance(future, asyncio.Future) and _admission_ack_matches(
                frame.get("ack"), body.get("admission", {})
            )
        elif operation == "native-stop-intent-ack":
            ack = frame.get("ack")
            correlation = frame.get("stop_id")
            key = f"native-stop-intent:{correlation}"
            body, future = self.pending.get(key, ({}, None))
            valid = isinstance(correlation, str) and isinstance(future, asyncio.Future) and _native_stop_intent_ack_matches(
                ack, correlation
            )
        elif operation == "native-stop-evidence-ack":
            ack = frame.get("ack")
            correlation = frame.get("evidence_id")
            key = f"native-stop-evidence:{correlation}"
            body, future = self.pending.get(key, ({}, None))
            evidence = body.get("evidence", {})
            valid = isinstance(correlation, str) and isinstance(future, asyncio.Future) and _native_stop_evidence_ack_matches(
                ack, correlation, evidence.get("stop_id")
            )
        elif operation == "native-child-observation-ack":
            shape_valid = set(frame) == {
                "operation", "participant_id", "session_id",
                "runner_instance_id", "observation_id", "ack",
            }
            ack = frame.get("ack")
            correlation = frame.get("observation_id")
            key = f"native-child-observation:{correlation}"
            body, future = self.native_child_observation_pending.get(key, ({}, None))
            observation = body.get("observation")
            refusal = (
                isinstance(ack, Mapping)
                and set(ack) == set(_NATIVE_CHILD_OBSERVATION_REFUSAL_FIELDS)
                and ack.get("recorded") is False
                and ack.get("observation_id") == correlation
                and isinstance(ack.get("code"), str)
                and bool(ack.get("code").strip())
            )
            valid = (
                isinstance(correlation, str)
                and isinstance(future, asyncio.Future)
                and isinstance(observation, Mapping)
                and (
                    _native_child_observation_ack_matches(ack, observation)
                    or refusal
                )
            )
        elif operation == "coordinator-interrupt-intent-ack":
            shape_valid = set(frame) == {
                "operation", "participant_id", "session_id",
                "runner_instance_id", "interrupt_id", "ack",
            }
            ack = frame.get("ack")
            correlation = frame.get("interrupt_id")
            key = f"coordinator-interrupt-intent:{correlation}"
            body, future = self.coordinator_interrupt_pending.get(key, ({}, None))
            valid = (
                isinstance(correlation, str)
                and isinstance(future, asyncio.Future)
                and body.get("interrupt", {}).get("interrupt_id") == correlation
                and _coordinator_interrupt_intent_ack_matches(ack, correlation)
            )
            coordinator_positive = valid and ack.get("authorize_send") is True
        elif operation == "coordinator-interrupt-evidence-ack":
            shape_valid = set(frame) == {
                "operation", "participant_id", "session_id",
                "runner_instance_id", "evidence_id", "interrupt_id", "ack",
            }
            ack = frame.get("ack")
            correlation = frame.get("evidence_id")
            key = f"coordinator-interrupt-evidence:{correlation}"
            body, future = self.coordinator_interrupt_pending.get(key, ({}, None))
            evidence = body.get("evidence", {})
            valid = (
                isinstance(correlation, str)
                and isinstance(future, asyncio.Future)
                and frame.get("interrupt_id") == evidence.get("interrupt_id")
                and _coordinator_interrupt_evidence_ack_matches(
                    ack, correlation, evidence.get("interrupt_id")
                )
            )
        elif operation == "coordinator-interrupt-validate-ack":
            shape_valid = set(frame) == {
                "operation", "participant_id", "session_id",
                "runner_instance_id", "validation_id", "interrupt_id", "ack",
            }
            ack = frame.get("ack")
            correlation = frame.get("validation_id")
            key = f"coordinator-interrupt-validate:{correlation}"
            body, future = self.coordinator_interrupt_validation_pending.get(
                key, ({}, None)
            )
            valid = (
                isinstance(correlation, str)
                and isinstance(future, asyncio.Future)
                and frame.get("interrupt_id") == body.get("interrupt_id")
                and _coordinator_interrupt_validation_ack_matches(
                    ack,
                    correlation,
                    body.get("interrupt_id"),
                    body.get("intent_digest"),
                )
            )
        elif operation == "native-swap-release-authorize-ack":
            shape_valid = set(frame) == {
                "operation", "participant_id", "session_id",
                "runner_instance_id", "validation_id", "ack",
            }
            ack = frame.get("ack")
            correlation = frame.get("validation_id")
            key = f"native-swap-release:{correlation}"
            body, future = self.native_swap_release_pending.get(key, ({}, None))
            binding = body.get("binding")
            try:
                valid = (
                    isinstance(correlation, str)
                    and isinstance(future, asyncio.Future)
                    and body.get("validation_id") == correlation
                    and isinstance(binding, Mapping)
                    and _native_swap_authorization(
                        ack,
                        validation_id=correlation,
                        binding=binding,
                    )
                    is not None
                )
            except SdkAdapterError:
                valid = False
        else:
            raise SdkAdapterError("invalid", "unknown native transaction acknowledgement")
        identity_valid = not any(
            type(frame.get(key)) is not type(self.identity[key])
            or frame.get(key) != self.identity[key] for key in _RUNNER_IDENTITY_FIELDS
        )
        if (
            operation == "coordinator-interrupt-intent-ack"
            and shape_valid
            and identity_valid
            and valid
            and coordinator_positive
        ):
            if correlation in self._coordinator_interrupt_authorized_ids:
                # A delayed/replayed positive receipt must never satisfy a
                # later retry.  Leave that waiter pending for the durable
                # controller's explicit false acknowledgement.
                return
            if (
                len(self._coordinator_interrupt_authorized_ids)
                >= MAX_NATIVE_LIFECYCLE_EVENTS
            ):
                raise SdkAdapterError(
                    "busy", "coordinator interrupt authorization history is full"
                )
            # Mark before resolving the future so cancellation or a lost
            # caller acknowledgement cannot create a second local grant.
            self._coordinator_interrupt_authorized_ids.add(correlation)
        if not shape_valid or not isinstance(future, asyncio.Future) or future.done() or not identity_valid or not valid:
            raise SdkAdapterError("stale-generation", "native transaction acknowledgement is malformed or uncorrelated")
        future.set_result(dict(frame["ack"]))


async def _queue_controls(
    bridge: _BoundedJsonLines, queue: asyncio.Queue[Any],
    admissions: Optional[_NativeAdmissionIPC] = None,
) -> None:
    failure = None
    try:
        while True:
            value = await bridge.read()
            if isinstance(value, Mapping) and value.get("operation") in {
                "native-admission-ack",
                "native-stop-intent-ack",
                "native-stop-evidence-ack",
                "coordinator-interrupt-intent-ack",
                "coordinator-interrupt-evidence-ack",
                "coordinator-interrupt-validate-ack",
                "native-child-observation-ack",
                "native-swap-release-authorize-ack",
            }:
                if admissions is None:
                    raise SdkAdapterError("invalid", "unexpected native admission acknowledgement")
                admissions.receive(value)
                continue
            # Never block this demultiplexer on a control consumer that can
            # itself be awaiting an admission acknowledgement.
            queue.put_nowait(value)
    except StopAsyncIteration:
        # A closed private control channel is not a clean finite controls
        # iterable.  Pending native child/stop/observation callbacks may be
        # waiting on this bridge, so surface a bounded failure and let the
        # runner cancel them instead of silently returning a successful
        # runner result while a persistence callback remains suspended.
        failure = SdkAdapterError(
            "loader-failed", "runner control channel closed before completion"
        )
    except asyncio.QueueFull:
        failure = SdkAdapterError("invalid", "runner control queue overflowed")
    except SdkAdapterError as exc:
        failure = exc
    except asyncio.CancelledError:
        raise
    except Exception:
        failure = SdkAdapterError("loader-failed", "runner control reader failed")
    finally:
        if admissions is not None:
            admissions.close(failure)
        # Reserve terminal capacity without awaiting a blocked hook. Overflow
        # refuses the channel; queued controls are not authorization to run.
        if queue.maxsize and queue.qsize() + 2 > queue.maxsize:
            while not queue.empty():
                queue.get_nowait()
            failure = failure or SdkAdapterError("invalid", "runner control queue overflowed")
        if failure is not None:
            queue.put_nowait({"operation": "protocol-error", **failure.as_dict()})
        if not queue.full():
            queue.put_nowait(_CONTROL_EOF)


def _write_runner_frame_sync(value: Mapping[str, Any]) -> None:
    """Write an early runner refusal before the async bridge exists."""

    text = json.dumps(dict(value), ensure_ascii=False, separators=(",", ":")) + "\n"
    stream = getattr(sys.stdout, "buffer", sys.stdout)
    try:
        stream.write(text.encode("utf-8"))
    except TypeError:
        stream.write(text)
    stream.flush()


async def _runner_async(
    first: Mapping[str, Any],
    *,
    _test_harness: tuple[Any, Any] | None = None,
) -> int:
    test_harness_active = _test_harness is not None
    test_sdk_module = None
    if _test_harness is not None:
        if (
            not isinstance(_test_harness, tuple)
            or len(_test_harness) != 2
            or _test_harness[0] is not _INTERNAL_TEST_HARNESS_TOKEN
            or _test_harness[1] is None
        ):
            raise SdkAdapterError("invalid", "runner fake SDK must use the internal test harness")
        test_sdk_module = _test_harness[1]
    payload = dict(first)
    raw_spec = payload.get("spec")
    if not isinstance(raw_spec, Mapping):
        raw_spec = payload
    wire_context: dict[str, Any] = {}
    try:
        operation = _wire_id(
            _first_nonempty(payload.get("operation"), payload.get("type")),
            "start operation",
        )
        if operation != "start":
            raise SdkAdapterError("invalid", "runner first frame must be a start operation")
        wire_context = {
            "request_id": _wire_id(payload.get("request_id"), "start request_id"),
            "participant_id": _wire_id(payload.get("participant_id"), "participant_id"),
            "session_id": _wire_id(payload.get("session_id"), "session_id"),
            "runner_instance_id": _wire_id(payload.get("runner_instance_id"), "runner_instance_id"),
        }
        marker_error = _native_swap_target_marker_error(raw_spec)
        if marker_error is not None:
            raise SdkAdapterError("invalid", marker_error)
        runner_spec = RunnerSpec.from_mapping(raw_spec)
        marker_error = _native_swap_target_marker_error(runner_spec)
        if marker_error is not None:
            raise SdkAdapterError("invalid", marker_error)
        if runner_spec.participant_id is not None and str(runner_spec.participant_id) != wire_context["participant_id"]:
            raise SdkAdapterError("ownership-conflict", "start specification belongs to another participant")
        if runner_spec.participant_id is None:
            runner_spec = dataclasses.replace(runner_spec, participant_id=wire_context["participant_id"])
        if str(runner_spec.session_id) != wire_context["session_id"]:
            raise SdkAdapterError("stale-generation", "start specification has a different session UUID")
        context = runner_spec.fingerprint.get("lineage_context")
        if isinstance(context, Mapping) and context.get("runner_incarnation") != wire_context["runner_instance_id"]:
            raise SdkAdapterError("stale-generation", "native lineage context has a different runner incarnation")
        _assert_spec_launchable(runner_spec)
    except SdkAdapterError as exc:
        # There is no bridge until after spec validation; report directly.
        _write_runner_frame_sync({"type": "adapter-error", **wire_context, **exc.as_dict()})
        return 2

    # This assignment is deliberately before the official SDK import.  The
    # SDK transport merges os.environ independently of options.env.
    clean_env = scrubbed_runner_environment(os.environ, runner_spec)
    os.environ.clear()
    os.environ.update(clean_env)
    os.environ["LANE_MANAGED_SDK_RUNNER"] = "1"

    # The process-group proof belongs to the dedicated entrypoint, before the
    # optional SDK is imported or allowed to start its transport.  Direct
    # ``drive_client`` calls remain an injectable fake/runtime seam and report
    # their observed ownership without imposing this process-launch check.
    process_evidence = _process_evidence()
    if (
        not process_evidence.get("process_group_owned", False)
        or not process_evidence.get("process_start_token")
    ):
        error = SdkAdapterError(
            "uncertain-effect",
            "dedicated SDK runner lacks a verifiable process group or start identity",
        )
        _write_runner_frame_sync({"type": "adapter-error", **wire_context, **error.as_dict()})
        return 2

    if test_sdk_module is not None:
        sdk_module = test_sdk_module
    else:
        try:
            sdk_module = importlib.import_module("claude_agent_sdk")
        except (ImportError, ModuleNotFoundError) as exc:
            error = SdkAdapterError(
                "unsupported",
                "optional claude-agent-sdk is not installed; live capability is unverified",
            )
            _write_runner_frame_sync({"type": "adapter-error", **wire_context, **error.as_dict()})
            return 2

    bridge = _BoundedJsonLines(
        getattr(sys.stdin, "buffer", sys.stdin),
        getattr(sys.stdout, "buffer", sys.stdout),
        runner_spec.frame_limit,
    )
    queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=256)
    admissions = _NativeAdmissionIPC(bridge, wire_context)
    controls_task = asyncio.create_task(_queue_controls(bridge, queue, admissions), name="lane-managed-stdin")
    seen_wire_requests: set[str] = set()
    shutdown_requested = False

    async def validated_controls() -> AsyncIterator[Mapping[str, Any]]:
        """Validate every post-start command before drive_client sees it."""

        nonlocal shutdown_requested
        while True:
            command = await queue.get()
            if command is _CONTROL_EOF:
                return
            if not isinstance(command, Mapping):
                yield {
                    "operation": "protocol-error",
                    **wire_context,
                    "code": "invalid",
                    "message": "runner control frame must be an object",
                }
                return
            raw_command = dict(command)
            if str(raw_command.get("operation", "")).strip().lower().replace("_", "-") == "protocol-error":
                yield {**wire_context, **raw_command}
                return
            try:
                operation = _control_operation(raw_command)
                if operation not in {
                    "interrupt", "release", "status", "ping", "query", "send",
                    "message", "user", "shutdown", "native-stop", "stop-task",
                    "coordinator-interrupt", "coordinator-interrupt-send",
                    "prepare-invocation",
                }:
                    raise SdkAdapterError("invalid", "unsupported runner control operation")
                request_id = _wire_id(raw_command.get("request_id"), "request_id")
                if request_id in seen_wire_requests:
                    raise SdkAdapterError("busy", "runner request_id was already used")
                seen_wire_requests.add(request_id)
                for key in ("participant_id", "session_id", "runner_instance_id"):
                    expected = wire_context[key]
                    actual = _wire_id(raw_command.get(key), key)
                    if actual != expected:
                        raise SdkAdapterError("stale-generation", f"runner control has the wrong {key}")
                if operation == "shutdown":
                    shutdown_requested = True
                if operation in {"query", "send", "message", "user"}:
                    _wire_id(
                        _first_nonempty(raw_command.get("message_id"), raw_command.get("id")),
                        "message_id",
                    )
                    if raw_command.get("reservation_binding") is not None:
                        reservation = raw_command.get("reservation_binding")
                        if not isinstance(reservation, Mapping):
                            raise SdkAdapterError("invalid", "native reservation binding must be an object")
                        # The complete proof/response is checked again at the
                        # ledger consume point; this early check keeps malformed
                        # caller frames out of the SDK control loop.
                        request_binding = {
                            key: reservation.get(key)
                            for key in _NATIVE_INVOCATION_BINDING_FIELDS
                        }
                        _native_invocation_response(reservation, request_binding)
                if operation == "prepare-invocation":
                    raw_command["payload_ref"] = _native_invocation_binding(
                        raw_command.get("payload_ref")
                    )
                if operation in {"release", "release-held"} and raw_command.get("payload_ref") is not None:
                    # A payload on release selects the bound native-swap
                    # transaction.  The closed binding is validated before it
                    # can reach the runner gate; an omitted payload keeps the
                    # legacy non-native release shape.
                    raw_command["payload_ref"] = _native_swap_binding(
                        raw_command.get("payload_ref")
                    )
                if operation in {"native-stop", "stop-task"}:
                    selection = raw_command.get("payload_ref")
                    if not isinstance(selection, Mapping) or set(selection) != {"task_id", "stop_id"}:
                        raise SdkAdapterError(
                            "invalid",
                            "native stop payload must select task_id and stop_id",
                        )
                    _wire_id(selection.get("task_id"), "task_id")
                    _wire_id(selection.get("stop_id"), "stop_id")
                if operation in {"coordinator-interrupt", "coordinator-interrupt-send"}:
                    selection = raw_command.get("payload_ref")
                    if not isinstance(selection, Mapping) or set(selection) != {
                        "operation_id", "interrupt_id", "fence_epoch",
                        "capability_digest", "request_epoch_id",
                    }:
                        raise SdkAdapterError(
                            "invalid",
                            "coordinator interrupt payload must select operation, interrupt, fence, capability, and request epoch",
                        )
                    _wire_id(selection.get("operation_id"), "operation_id")
                    _wire_id(selection.get("interrupt_id"), "interrupt_id")
                    _wire_id(selection.get("request_epoch_id"), "request_epoch_id")
                    if type(selection.get("fence_epoch")) is not int or selection.get("fence_epoch") <= 0:
                        raise SdkAdapterError("invalid", "coordinator interrupt fence_epoch is invalid")
                    if (
                        not isinstance(selection.get("capability_digest"), str)
                        or not re.fullmatch(r"[0-9a-f]{64}", selection.get("capability_digest"))
                    ):
                        raise SdkAdapterError("invalid", "coordinator interrupt capability_digest is invalid")
                raw_command["request_id"] = request_id
                yield raw_command
            except SdkAdapterError as exc:
                yield {"operation": "protocol-error", **wire_context, **exc.as_dict()}
                return

    async def emit(value: Any) -> None:
        if isinstance(value, Mapping):
            event = dict(value)
        else:
            event = {"type": "event", "value": value}
        for key in ("participant_id", "session_id", "runner_instance_id"):
            expected = wire_context[key]
            event.setdefault(key, expected)
        if event.get("type") == "ready-held":
            event.setdefault("request_id", wire_context["request_id"])
            raw_evidence = event.get("evidence")
            if isinstance(raw_evidence, Mapping):
                evidence = dict(raw_evidence)
                if not isinstance(evidence.get("initialization"), Mapping):
                    evidence["initialization"] = {
                        "account_email": evidence.get("account_email"),
                        "permission_mode": evidence.get("permission_mode"),
                        "model": evidence.get("model"),
                        "fingerprint": dict(runner_spec.fingerprint),
                    }
                event["evidence"] = evidence
        await bridge.write(event)

    try:
        result = await drive_client(
            runner_spec, validated_controls(), emit, sdk_module=sdk_module,
            persist_admission=admissions.request,
            native_stop_ipc=admissions,
            native_stop_identity=wire_context,
            coordinator_interrupt_ipc=admissions,
            coordinator_interrupt_identity=wire_context,
            native_child_observation_ipc=admissions,
            native_swap_release_ipc=admissions,
            native_swap_release_identity=wire_context,
            # The runner's first JSON frame is caller-controlled input at this
            # boundary.  It cannot grant Gate 0 authority.  An internal
            # controller/provider must supply evidence to ``drive_client`` in
            # process after preflight; absent that, every imported runtime is
            # refused before client construction.
            capability_evidence=None,
            require_live_capability=not test_harness_active,
        )
        if shutdown_requested:
            # ``runner-result`` is the last frame emitted by this process.  No
            # later runner operation can mutate the SDK or its process group;
            # expose the terminal shutdown state in this final frame.  The
            # supervisor connection independently waits for process/group
            # exclusion before applying the same evidence to its registry.
            result = dict(result)
            evidence = dict(result.get("evidence", {}))
            process = dict(evidence.get("process", {}))
            process["exited"] = True
            process["group_excluded"] = True
            evidence["process"] = process
            result["evidence"] = evidence
        await emit({"type": "runner-result", **result})
        return 0
    except SdkAdapterError as exc:
        await emit({"type": "adapter-error", **exc.as_dict()})
        return 2
    except Exception as exc:  # noqa: BLE001
        await emit({"type": "adapter-error", "code": "unknown", "message": str(exc)})
        return 2
    finally:
        if not controls_task.done():
            controls_task.cancel()
        await asyncio.gather(controls_task, return_exceptions=True)


def _read_first_frame(
    stream: Any,
    limit: int = MAX_FRAME_BYTES,
    timeout: float = DEFAULT_STARTUP_DEADLINE,
) -> dict[str, Any]:
    bounded = max(1024, min(int(limit), MAX_FRAME_BYTES))
    try:
        fileno = stream.fileno()
    except (AttributeError, OSError, ValueError):
        fileno = None
    if fileno is not None:
        # Read one byte at a time so a parent that pipelined controls cannot
        # have bytes after the first newline swallowed by TextIO buffering.
        # ``select`` is applied to every byte, so a partial/malicious first
        # frame cannot block past the startup deadline.
        deadline = time.monotonic() + timeout
        buffer = bytearray()
        while b"\n" not in buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SdkAdapterError("loader-failed", "runner start frame deadline exceeded")
            try:
                readable, _writable, _exceptional = select.select([fileno], [], [], remaining)
            except (OSError, ValueError):
                readable = [fileno]
            if not readable:
                raise SdkAdapterError("loader-failed", "runner start frame deadline exceeded")
            chunk = os.read(fileno, 1)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > bounded:
                raise SdkAdapterError("invalid", "start frame exceeds 1 MiB limit")
        raw = bytes(buffer)
    else:
        raw = stream.readline(bounded + 1)
    if raw in (b"", ""):
        raise SdkAdapterError("invalid", "runner did not receive a start frame")
    if isinstance(raw, bytes):
        if len(raw) > bounded:
            raise SdkAdapterError("invalid", "start frame exceeds 1 MiB limit")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SdkAdapterError("invalid", "start frame is not UTF-8") from exc
    else:
        if len(raw.encode("utf-8", "replace")) > bounded:
            raise SdkAdapterError("invalid", "start frame exceeds 1 MiB limit")
        text = raw
    try:
        value = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SdkAdapterError("invalid", "start frame is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise SdkAdapterError("invalid", "start frame must be a JSON object")
    return dict(value)


def _runner_main() -> int:
    # Popen uses start_new_session=True; this fallback also makes direct
    # ``python lane_managed_sdk.py --runner`` invocations process-group owned.
    if os.name == "posix" and hasattr(os, "setsid"):
        try:
            os.setsid()
        except OSError:
            pass
    try:
        first = _read_first_frame(getattr(sys.stdin, "buffer", sys.stdin))
    except SdkAdapterError as exc:
        sys.stdout.write(json.dumps({"type": "adapter-error", **exc.as_dict()}) + "\n")
        sys.stdout.flush()
        return 2
    try:
        return int(asyncio.run(_runner_async(first)))
    except KeyboardInterrupt:
        return 130
    except SdkAdapterError as exc:
        sys.stdout.write(json.dumps({"type": "adapter-error", **exc.as_dict()}) + "\n")
        sys.stdout.flush()
        return 2


def popen_runner(
    spec: RunnerSpec | Mapping[str, Any],
    *,
    base_env: Mapping[str, Any] | None = None,
    python_executable: str | None = None,
    module_path: str | os.PathLike[str] | None = None,
    **kwargs: Any,
) -> subprocess.Popen[Any]:
    """Spawn a dedicated, new-session runner with a complete scrubbed env.

    The helper is intentionally small and does not write state or credentials.
    The caller sends the first ``spec`` JSON frame through ``stdin`` after this
    returns.  ``start_new_session`` is the only containment claim made here;
    arbitrary detached descendants remain unsupported and fail closed when
    observed as tool/effect evidence.
    """

    runner_spec = _normalise_spec(spec)
    _assert_spec_launchable(runner_spec)
    executable = python_executable or sys.executable
    source = Path(module_path) if module_path is not None else Path(__file__).resolve()
    environment = scrubbed_runner_environment(
        os.environ if base_env is None else base_env,
        runner_spec,
    )
    # Marking the process before import is safe; the child still sanitises its
    # complete environment once more after reading the wire spec.
    command = [executable, str(source), "--runner"]
    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": environment,
        "start_new_session": os.name == "posix",
        "text": True,
        "bufsize": 1,
    }
    popen_kwargs.update(kwargs)
    # Never let callers accidentally replace the security-critical env or
    # session ownership settings through kwargs.
    popen_kwargs["env"] = environment
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True
    return subprocess.Popen(command, **popen_kwargs)


def _wire_id(value: Any, label: str) -> str:
    """Validate an identifier used on the runner control wire."""

    if isinstance(value, bool) or not isinstance(value, str):
        raise SdkAdapterError("invalid", f"{label} must be a string")
    value = value.strip()
    if not value or len(value) > 256 or "\x00" in value:
        raise SdkAdapterError("invalid", f"{label} is empty or too long")
    return value


# ``prepare-invocation`` is an implementation-owned control protocol.  Keep
# its immutable binding separate from transport request IDs/deadlines so a
# retry cannot accidentally change the identity being authorized.
_NATIVE_INVOCATION_BINDING_FIELDS = (
    "schema_version",
    "architecture",
    "reservation_version",
    "reservation_id",
    "operation_id",
    "owner_generation",
    "daemon_id",
    "participant_id",
    "session_id",
    "runner_incarnation",
    "lineage_id",
    "lineage_generation",
    "prior_invocation_id",
    "next_invocation_id",
    "prior_mailbox_id",
    "next_mailbox_id",
    "prior_watermark",
    "definitions_digest",
    "permissions_digest",
    "claim_digest",
    "binding_digest",
)
_NATIVE_INVOCATION_RESPONSE_FIELDS = (
    *_NATIVE_INVOCATION_BINDING_FIELDS,
    "state",
    "terminal_watermark",
    "next_watermark",
    "terminal_proof",
    "terminal_proof_digest",
)
_NATIVE_TERMINAL_PROOF_FIELDS = (
    "parent_result",
    "roster",
    "roster_digest",
    "observation_watermark",
    "uncertainty",
    "overflow",
)
_NATIVE_PARENT_RESULT_FIELDS = (
    "session_id",
    "invocation_id",
    "message_id",
    "result_watermark",
    "reader_drained_watermark",
)
_NATIVE_RESERVATION_NO_SEND_FIELDS = (
    "schema_version",
    "architecture",
    "record_kind",
    "observation_id",
    "reservation_binding",
    "reservation_digest",
    "observation_watermark",
    "state",
    "transport_attempted",
    "receipt_digest",
)
_NATIVE_RESERVATION_NO_SEND_MAX_BYTES = 64 * 1024
_NATIVE_ROSTER_FIELDS = (
    "parent_state",
    "children",
    "pending_admission_ids",
    "pending_task_ids",
    "parent_active_tool_ids",
    "parent_uncertain_tool_ids",
    "parent_unresolved_effect_ids",
    "descendant_ids",
)
_NATIVE_TERMINAL_CHILD_STATUSES = frozenset({
    "completed", "stopped",
})
_NATIVE_TERMINAL_CHILD_FIELDS = (
    "admission_id", "tool_use_id", "agent_id", "task_id", "parent_agent_id",
    "invocation_id", "lineage_incarnation", "trusted_definition_digest",
    "start_watermark", "task_start_event", "status", "terminal_watermark",
    "active_tool_ids", "uncertain_tool_ids", "unresolved_effect_ids",
)
_NATIVE_CHILD_SOURCE_FIELDS = (
    "owner_generation",
    "lineage_id",
    "lineage_generation",
    "session_uuid",
    "runner_incarnation",
    "invocation_id",
)
_NATIVE_CHILD_OBSERVATION_FIELDS = (
    "schema_version",
    "architecture",
    "record_kind",
    "observation_id",
    "source_identity",
    "context_binding_digest",
    "claim_digest",
    "observation_watermark",
    "terminal_outcome",
    "child",
)
_NATIVE_CHILD_OBSERVATION_FRAME_FIELDS = (
    "type",
    "participant_id",
    "session_id",
    "runner_instance_id",
    "observation",
)
_NATIVE_CHILD_OBSERVATION_ACK_FIELDS = (
    "recorded",
    "observation_id",
    "observation_digest",
    "child_run_id",
    "observation_watermark",
)
_NATIVE_CHILD_OBSERVATION_REFUSAL_FIELDS = (
    "recorded",
    "observation_id",
    "code",
)
_NATIVE_CHILD_TERMINAL_OUTCOMES = frozenset(
    {"completed", "stopped", "failed", "cancelled", "unknown"}
)


def _native_digest_field(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SdkAdapterError("invalid", f"{label} must be a lowercase SHA-256 digest")
    return value


def _native_child_projection(value: Any) -> dict[str, Any]:
    """Validate the exact fifteen-field joined native-child projection."""

    if not isinstance(value, Mapping) or set(value) != set(_NATIVE_TERMINAL_CHILD_FIELDS):
        raise SdkAdapterError(
            "invalid", "native child observation projection has unknown or missing fields"
        )
    child = copy.deepcopy(dict(value))
    for key in ("admission_id", "tool_use_id", "agent_id", "task_id", "invocation_id"):
        child[key] = _wire_id(child.get(key), f"native child {key}")
    parent_agent_id = child.get("parent_agent_id")
    if parent_agent_id is not None:
        child["parent_agent_id"] = _wire_id(parent_agent_id, "native child parent_agent_id")
    if type(child.get("lineage_incarnation")) is not int or child["lineage_incarnation"] <= 0:
        raise SdkAdapterError("invalid", "native child lineage_incarnation is invalid")
    _native_digest_field(
        child.get("trusted_definition_digest"), "native child trusted_definition_digest"
    )
    if type(child.get("start_watermark")) is not int or child["start_watermark"] <= 0:
        raise SdkAdapterError("invalid", "native child start_watermark is invalid")
    task_start = child.get("task_start_event")
    if not isinstance(task_start, Mapping) or set(task_start) != {
        "event_uuid", "watermark", "task_type"
    }:
        raise SdkAdapterError("invalid", "native child task_start_event is incomplete")
    task_start = dict(task_start)
    if task_start.get("event_uuid") is not None:
        task_start["event_uuid"] = _wire_id(
            task_start.get("event_uuid"), "native child task event UUID"
        )
    task_start["task_type"] = _wire_id(
        task_start.get("task_type"), "native child task type"
    )
    if (
        type(task_start.get("watermark")) is not int
        or task_start["watermark"] <= child["start_watermark"]
    ):
        raise SdkAdapterError("stale-generation", "native child task start watermark is stale")
    child["task_start_event"] = task_start
    if child.get("status") not in {"active", "completed", "stopped"}:
        raise SdkAdapterError("invalid", "native child status is unsupported")
    terminal_watermark = child.get("terminal_watermark")
    if child["status"] == "active":
        if terminal_watermark is not None:
            raise SdkAdapterError("invalid", "active native child has terminal watermark")
    else:
        if (
            type(terminal_watermark) is not int
            or terminal_watermark < child["start_watermark"]
        ):
            raise SdkAdapterError("stale-generation", "native child terminal watermark is invalid")
    for key in ("active_tool_ids", "uncertain_tool_ids", "unresolved_effect_ids"):
        values = child.get(key)
        if not isinstance(values, list) or len(values) > MAX_NATIVE_PROGRESS_EVENTS:
            raise SdkAdapterError("invalid", f"native child {key} inventory is invalid")
        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            item = _wire_id(item, f"native child {key} ID")
            if item in seen:
                raise SdkAdapterError("uncertain-effect", f"native child {key} inventory repeats an ID")
            seen.add(item)
            normalized.append(item)
        child[key] = normalized
    if set(child["active_tool_ids"]) & set(child["uncertain_tool_ids"]):
        raise SdkAdapterError("uncertain-effect", "native child tool inventories overlap")
    return child


def _native_child_observation(value: Any) -> dict[str, Any]:
    """Validate and detach one SDK-produced native-child observation."""

    if not isinstance(value, Mapping) or set(value) != set(_NATIVE_CHILD_OBSERVATION_FIELDS):
        raise SdkAdapterError(
            "invalid", "native child observation has unknown or missing fields"
        )
    observation = copy.deepcopy(dict(value))
    if observation["schema_version"] != 2 or type(observation["schema_version"]) is not int:
        raise SdkAdapterError("invalid", "native child observation schema_version is unsupported")
    if observation["architecture"] != "native-coordinator-lineage":
        raise SdkAdapterError("invalid", "native child observation architecture is unsupported")
    if observation["record_kind"] != "native-child-observation":
        raise SdkAdapterError("invalid", "native child observation record_kind is unsupported")
    observation["observation_id"] = _wire_id(
        observation.get("observation_id"), "native child observation_id"
    )
    source = observation.get("source_identity")
    if not isinstance(source, Mapping) or set(source) != set(_NATIVE_CHILD_SOURCE_FIELDS):
        raise SdkAdapterError("invalid", "native child observation source identity is incomplete")
    source = dict(source)
    if type(source.get("owner_generation")) is not int or source["owner_generation"] <= 0:
        raise SdkAdapterError("invalid", "native child source owner_generation is invalid")
    if type(source.get("lineage_generation")) is not int or source["lineage_generation"] <= 0:
        raise SdkAdapterError("invalid", "native child source lineage_generation is invalid")
    for key in ("lineage_id", "session_uuid", "runner_incarnation", "invocation_id"):
        source[key] = _wire_id(source.get(key), f"native child source {key}")
    observation["source_identity"] = source
    for key in ("context_binding_digest", "claim_digest"):
        observation[key] = _native_digest_field(observation.get(key), key)
    watermark = observation.get("observation_watermark")
    if type(watermark) is not int or watermark <= 0:
        raise SdkAdapterError("invalid", "native child observation watermark is invalid")
    observation["observation_watermark"] = watermark
    child = _native_child_projection(observation.get("child"))
    if child["invocation_id"] != source["invocation_id"]:
        raise SdkAdapterError("stale-generation", "native child projection invocation is not its source")
    if child["start_watermark"] >= watermark:
        raise SdkAdapterError("stale-generation", "native child observation watermark is stale")
    if child["status"] != "active" and child["terminal_watermark"] > watermark:
        raise SdkAdapterError("stale-generation", "native child terminal watermark exceeds observation")
    outcome = observation.get("terminal_outcome")
    if child["status"] == "active":
        if outcome is not None:
            raise SdkAdapterError("invalid", "active native child has a terminal outcome")
    elif outcome not in _NATIVE_CHILD_TERMINAL_OUTCOMES:
        raise SdkAdapterError("invalid", "native child terminal outcome is unsupported")
    elif child["status"] == "completed" and outcome != "completed":
        raise SdkAdapterError("stale-generation", "completed native child has a different outcome")
    elif child["status"] == "stopped" and outcome == "completed":
        raise SdkAdapterError("stale-generation", "stopped native child cannot report completion")
    observation["child"] = child
    try:
        encoded = json.dumps(
            observation,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise SdkAdapterError("invalid", "native child observation is not strict JSON") from exc
    if len(encoded) > MAX_FRAME_BYTES:
        raise SdkAdapterError("invalid", "native child observation exceeds its frame bound")
    return observation


def _native_child_observation_ack_matches(
    value: Any, observation: Mapping[str, Any]
) -> bool:
    """Validate the exact positive ACK for one observation frame."""

    if not isinstance(value, Mapping) or set(value) != set(_NATIVE_CHILD_OBSERVATION_ACK_FIELDS):
        return False
    try:
        expected = _native_child_observation(observation)
        if value.get("recorded") is not True or type(value.get("recorded")) is not bool:
            return False
        if value.get("observation_id") != expected["observation_id"]:
            return False
        if value.get("observation_digest") != _native_full_digest(expected):
            return False
        child = expected["child"]
        child_run_id = {
            "source_identity": expected["source_identity"],
            **{
                key: child[key]
                for key in (
                    "admission_id", "tool_use_id", "agent_id", "task_id",
                    "lineage_incarnation", "start_watermark",
                )
            },
        }
        if value.get("child_run_id") != _native_full_digest(child_run_id):
            return False
        return value.get("observation_watermark") == expected["observation_watermark"]
    except SdkAdapterError:
        return False


def _native_child_observation_run_id(observation: Mapping[str, Any]) -> str:
    """Return the bounded child-run key used by all observation queues."""

    observation = _native_child_observation(observation)
    child = observation["child"]
    return _native_full_digest(
        {
            "source_identity": observation["source_identity"],
            **{
                key: child[key]
                for key in (
                    "admission_id",
                    "tool_use_id",
                    "agent_id",
                    "task_id",
                    "lineage_incarnation",
                    "start_watermark",
                )
            },
        }
    )


def _native_child_observation_refusal(
    observation_id: Any, code: str
) -> dict[str, Any]:
    """Build a private transport refusal without widening the persisted ACK."""

    try:
        observation_id = _wire_id(observation_id, "native child observation_id")
    except SdkAdapterError:
        observation_id = "invalid-observation-id"
    return {
        "recorded": False,
        "observation_id": observation_id,
        "code": str(code)[:128],
    }


def _native_invocation_binding(value: Any, *, verify_digest: bool = True) -> dict[str, Any]:
    """Validate and detach one exact immutable invocation binding."""

    if not isinstance(value, Mapping) or set(value) != set(_NATIVE_INVOCATION_BINDING_FIELDS):
        raise SdkAdapterError(
            "invalid",
            "native invocation binding must contain exactly the versioned fields",
        )
    binding = dict(value)
    if binding["schema_version"] != 2 or type(binding["schema_version"]) is not int:
        raise SdkAdapterError("invalid", "native invocation schema_version is unsupported")
    if binding["architecture"] != "native-coordinator-lineage":
        raise SdkAdapterError("invalid", "native invocation architecture is unsupported")
    if type(binding["reservation_version"]) is not int or binding["reservation_version"] != 1:
        raise SdkAdapterError("invalid", "native invocation reservation_version is unsupported")
    for key in (
        "reservation_id", "operation_id", "daemon_id", "participant_id", "session_id",
        "runner_incarnation", "lineage_id", "prior_invocation_id", "next_invocation_id",
        "prior_mailbox_id", "next_mailbox_id",
    ):
        binding[key] = _wire_id(binding.get(key), key)
    for key in ("owner_generation", "lineage_generation"):
        if type(binding[key]) is not int or binding[key] <= 0:
            raise SdkAdapterError("invalid", f"native invocation {key} is invalid")
    if type(binding["prior_watermark"]) is not int or binding["prior_watermark"] < 0:
        raise SdkAdapterError("invalid", "native invocation prior_watermark is invalid")
    for key in (
        "definitions_digest", "permissions_digest", "claim_digest", "binding_digest",
    ):
        binding[key] = _native_digest_field(binding[key], key)
    if binding["prior_invocation_id"] == binding["prior_mailbox_id"]:
        pass
    else:
        raise SdkAdapterError("invalid", "native prior invocation and mailbox IDs must match")
    if binding["next_invocation_id"] == binding["next_mailbox_id"]:
        pass
    else:
        raise SdkAdapterError("invalid", "native next invocation and mailbox IDs must match")
    if binding["prior_invocation_id"] == binding["next_invocation_id"]:
        raise SdkAdapterError("invalid", "native invocation rollover requires distinct invocations")
    if binding["prior_mailbox_id"] == binding["next_mailbox_id"]:
        raise SdkAdapterError("invalid", "native invocation rollover requires distinct mailboxes")
    if verify_digest:
        digest_input = {key: binding[key] for key in _NATIVE_INVOCATION_BINDING_FIELDS if key != "binding_digest"}
        expected = _native_full_digest(digest_input)
        if binding["binding_digest"] != expected:
            raise SdkAdapterError("stale-generation", "native invocation binding digest does not match its fields")
    return copy.deepcopy(binding)


def _native_terminal_roster(
    value: Any,
    binding: Mapping[str, Any],
    terminal_watermark: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(_NATIVE_ROSTER_FIELDS):
        raise SdkAdapterError("invalid", "native terminal proof roster is incomplete")
    roster = copy.deepcopy(dict(value))
    if roster.get("parent_state") != "idle":
        raise SdkAdapterError("busy", "native terminal proof parent is not idle")
    children = roster.get("children")
    if not isinstance(children, list) or len(children) > MAX_NATIVE_CHILD_RECORDS:
        raise SdkAdapterError("invalid", "native terminal proof child roster is unbounded")
    seen_admissions: set[str] = set()
    for child in children:
        if not isinstance(child, Mapping):
            raise SdkAdapterError("invalid", "native terminal proof child record is malformed")
        if set(child) != set(_NATIVE_TERMINAL_CHILD_FIELDS):
            raise SdkAdapterError("invalid", "native terminal proof child record is not the closed native schema")
        child = dict(child)
        for key in ("admission_id", "tool_use_id", "agent_id", "task_id", "invocation_id"):
            child[key] = _wire_id(child.get(key), f"terminal child {key}")
        if child["admission_id"] in seen_admissions:
            raise SdkAdapterError("uncertain-effect", "native terminal proof repeats a child admission")
        seen_admissions.add(child["admission_id"])
        if child["invocation_id"] != binding["prior_invocation_id"]:
            raise SdkAdapterError("stale-generation", "native terminal child belongs to another invocation")
        parent_agent_id = child.get("parent_agent_id")
        if parent_agent_id is not None:
            _wire_id(parent_agent_id, "terminal child parent_agent_id")
        if type(child.get("lineage_incarnation")) is not int or child["lineage_incarnation"] <= 0:
            raise SdkAdapterError("invalid", "native terminal child incarnation is invalid")
        _native_digest_field(child.get("trusted_definition_digest"), "terminal child definition digest")
        if type(child.get("start_watermark")) is not int or child["start_watermark"] <= binding["prior_watermark"]:
            raise SdkAdapterError("stale-generation", "native terminal child start watermark is stale")
        child_terminal = child.get("terminal_watermark")
        if type(child_terminal) is not int or child_terminal < child["start_watermark"] or child_terminal > terminal_watermark:
            raise SdkAdapterError("stale-generation", "native terminal child terminal watermark is invalid")
        task_start = child.get("task_start_event")
        if not isinstance(task_start, Mapping) or set(task_start) != {"event_uuid", "watermark", "task_type"}:
            raise SdkAdapterError("invalid", "native terminal child task start evidence is incomplete")
        task_start_watermark = task_start.get("watermark")
        if type(task_start_watermark) is not int or task_start_watermark <= child["start_watermark"] or task_start_watermark > terminal_watermark:
            raise SdkAdapterError("stale-generation", "native terminal child task start watermark is invalid")
        if task_start.get("event_uuid") is not None:
            _wire_id(task_start.get("event_uuid"), "terminal child task event UUID")
        _wire_id(task_start.get("task_type"), "terminal child task type")
        status = child.get("status")
        if status not in _NATIVE_TERMINAL_CHILD_STATUSES:
            raise SdkAdapterError("busy", "native terminal proof contains an active child")
        for key in ("active_tool_ids", "uncertain_tool_ids", "unresolved_effect_ids"):
            values = child.get(key)
            if not isinstance(values, list) or len(values) > MAX_NATIVE_PROGRESS_EVENTS:
                raise SdkAdapterError("invalid", f"native terminal child {key} inventory is invalid")
            if values:
                raise SdkAdapterError("uncertain-effect", f"native terminal child {key} inventory is not empty")
    for key in (
        "pending_admission_ids", "pending_task_ids", "parent_active_tool_ids",
        "parent_uncertain_tool_ids", "parent_unresolved_effect_ids", "descendant_ids",
    ):
        values = roster.get(key)
        if not isinstance(values, list) or len(values) > MAX_NATIVE_PROGRESS_EVENTS:
            raise SdkAdapterError("invalid", f"native terminal proof {key} inventory is invalid")
        if values:
            raise SdkAdapterError("uncertain-effect", f"native terminal proof {key} inventory is not empty")
    return roster


def _native_terminal_proof(
    value: Any,
    binding: Mapping[str, Any],
    *,
    terminal_watermark: Any,
    next_watermark: Any,
    proof_digest: Any,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(_NATIVE_TERMINAL_PROOF_FIELDS):
        raise SdkAdapterError("invalid", "native terminal proof has unknown or missing fields")
    proof = copy.deepcopy(dict(value))
    parent = proof.get("parent_result")
    if not isinstance(parent, Mapping) or set(parent) != set(_NATIVE_PARENT_RESULT_FIELDS):
        raise SdkAdapterError("invalid", "native terminal parent result is incomplete")
    parent = dict(parent)
    if parent["session_id"] != binding["session_id"]:
        raise SdkAdapterError("stale-generation", "native terminal result has the wrong session")
    if parent["invocation_id"] != binding["prior_invocation_id"]:
        raise SdkAdapterError("stale-generation", "native terminal result has the wrong invocation")
    if parent["message_id"] != binding["prior_mailbox_id"]:
        raise SdkAdapterError("stale-generation", "native terminal result has the wrong mailbox")
    for key in ("session_id", "invocation_id", "message_id"):
        parent[key] = _wire_id(parent[key], f"terminal parent {key}")
    for key in ("result_watermark", "reader_drained_watermark"):
        if type(parent[key]) is not int or parent[key] < 0:
            raise SdkAdapterError("invalid", f"native terminal parent {key} is invalid")
    if parent["result_watermark"] <= binding["prior_watermark"]:
        raise SdkAdapterError("stale-generation", "native terminal result did not advance the prior watermark")
    if parent["result_watermark"] > parent["reader_drained_watermark"]:
        raise SdkAdapterError("stale-generation", "native terminal reader watermark moved backwards")
    proof["parent_result"] = parent
    roster = _native_terminal_roster(proof.get("roster"), binding, terminal_watermark)
    proof["roster"] = roster
    proof["roster_digest"] = _native_digest_field(proof.get("roster_digest"), "roster_digest")
    if proof["roster_digest"] != _native_full_digest(roster):
        raise SdkAdapterError("stale-generation", "native terminal roster digest changed")
    observation = proof.get("observation_watermark")
    if type(observation) is not int or observation < 0:
        raise SdkAdapterError("invalid", "native terminal observation watermark is invalid")
    uncertainty = proof.get("uncertainty")
    if not isinstance(uncertainty, list) or uncertainty:
        raise SdkAdapterError("uncertain-effect", "native terminal proof contains uncertainty")
    if type(proof.get("overflow")) is not bool or proof["overflow"]:
        raise SdkAdapterError("uncertain-effect", "native terminal proof overflow is not clear")
    if type(terminal_watermark) is not int or type(next_watermark) is not int:
        raise SdkAdapterError("invalid", "native reservation watermarks are invalid")
    if observation != terminal_watermark:
        raise SdkAdapterError("stale-generation", "native terminal proof watermark disagrees with response")
    if parent["reader_drained_watermark"] > terminal_watermark:
        raise SdkAdapterError("stale-generation", "native terminal proof drain exceeds terminal watermark")
    if terminal_watermark >= next_watermark:
        raise SdkAdapterError("stale-generation", "native reservation next watermark is not newer")
    digest = _native_digest_field(proof_digest, "terminal_proof_digest")
    if digest != _native_full_digest(proof):
        raise SdkAdapterError("stale-generation", "native terminal proof digest changed")
    return proof


def _native_invocation_response(value: Any, request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SdkAdapterError("invalid", "native prepare acknowledgement must be an object")
    response = dict(value)
    transport_fields = {"type", "request_id", "participant_id", "session_id", "runner_instance_id"}
    if set(response) - (set(_NATIVE_INVOCATION_RESPONSE_FIELDS) | transport_fields):
        raise SdkAdapterError("invalid", "native prepare acknowledgement contains unknown fields")
    if not set(_NATIVE_INVOCATION_RESPONSE_FIELDS).issubset(response):
        raise SdkAdapterError("invalid", "native prepare acknowledgement is incomplete")
    expected = _native_invocation_binding(request)
    actual = _native_invocation_binding(
        {key: response[key] for key in _NATIVE_INVOCATION_BINDING_FIELDS}
    )
    if actual != expected:
        raise SdkAdapterError("stale-generation", "native prepare acknowledgement changed its binding")
    if response.get("state") != "reserved":
        raise SdkAdapterError("busy", "native invocation reservation was not reserved")
    for key in ("terminal_watermark", "next_watermark"):
        if type(response.get(key)) is not int or response[key] < 0:
            raise SdkAdapterError("invalid", f"native prepare acknowledgement {key} is invalid")
    proof = _native_terminal_proof(
        response.get("terminal_proof"),
        expected,
        terminal_watermark=response["terminal_watermark"],
        next_watermark=response["next_watermark"],
        proof_digest=response.get("terminal_proof_digest"),
    )
    response["terminal_proof"] = proof
    response["terminal_proof_digest"] = _native_full_digest(proof)
    # Transport correlation is deliberately not part of the cached immutable
    # reservation.  Callers validate it at the frame boundary before this
    # canonical response is retained or consumed.
    return {
        key: copy.deepcopy(response[key]) for key in _NATIVE_INVOCATION_RESPONSE_FIELDS
    }


def _native_invocation_request_from_response(value: Any) -> dict[str, Any]:
    """Project a complete reservation response back to its binding shape.

    Response validators deliberately accept only the immutable binding as the
    ``request`` argument.  Status/recovery paths hold the complete cached
    response, so they must strip proof/transport fields before re-validating it
    rather than passing that response as a binding and accidentally refusing a
    genuine no-send observation.
    """

    if not isinstance(value, Mapping):
        return {}
    return {
        key: value.get(key)
        for key in _NATIVE_INVOCATION_BINDING_FIELDS
    }


def _native_reservation_no_send_receipt(
    value: Any,
    *,
    reservation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the private status evidence for one unconsumed reservation.

    This is deliberately a producer/validator for the existing authenticated
    status path, not a public recovery proof.  The reservation is the complete
    versioned response (including its terminal proof), and all digests cover
    the exact canonical objects carried on the wire.
    """

    if not isinstance(value, Mapping) or set(value) != set(_NATIVE_RESERVATION_NO_SEND_FIELDS):
        raise SdkAdapterError(
            "invalid",
            "native reservation no-send receipt has unknown or missing fields",
        )
    receipt = copy.deepcopy(dict(value))
    if receipt["schema_version"] != 2 or type(receipt["schema_version"]) is not int:
        raise SdkAdapterError("invalid", "native reservation no-send schema_version is unsupported")
    if receipt["architecture"] != "native-coordinator-lineage":
        raise SdkAdapterError("invalid", "native reservation no-send architecture is unsupported")
    if receipt["record_kind"] != "native-reservation-no-send":
        raise SdkAdapterError("invalid", "native reservation no-send record_kind is unsupported")
    receipt["observation_id"] = _wire_id(
        receipt.get("observation_id"), "native reservation observation_id"
    )
    if receipt["state"] != "reserved-unconsumed":
        raise SdkAdapterError("invalid", "native reservation no-send state is unsupported")
    if receipt["transport_attempted"] is not False or type(receipt["transport_attempted"]) is not bool:
        raise SdkAdapterError("uncertain-effect", "native reservation transport history is not no-send")
    raw_reservation = receipt.get("reservation_binding")
    if (
        not isinstance(raw_reservation, Mapping)
        or set(raw_reservation) != set(_NATIVE_INVOCATION_RESPONSE_FIELDS)
    ):
        raise SdkAdapterError(
            "invalid",
            "native reservation no-send binding must be the complete strict response",
        )
    reservation_value = _native_invocation_response(
        raw_reservation,
        _native_invocation_request_from_response(raw_reservation),
    )
    if reservation is not None:
        expected = _native_invocation_response(
            reservation,
            _native_invocation_request_from_response(reservation),
        )
        if reservation_value != expected:
            raise SdkAdapterError(
                "stale-generation",
                "native reservation no-send receipt changed its cached reservation",
            )
    receipt["reservation_binding"] = reservation_value
    reservation_digest = _native_digest_field(
        receipt.get("reservation_digest"), "reservation_digest"
    )
    if reservation_digest != _native_full_digest(reservation_value):
        raise SdkAdapterError(
            "stale-generation",
            "native reservation no-send reservation digest changed",
        )
    observation_watermark = receipt.get("observation_watermark")
    if (
        type(observation_watermark) is not int
        or observation_watermark <= 0
        or observation_watermark < reservation_value["terminal_watermark"]
    ):
        raise SdkAdapterError(
            "stale-generation",
            "native reservation no-send observation watermark is invalid",
        )
    receipt_digest = _native_digest_field(
        receipt.get("receipt_digest"), "receipt_digest"
    )
    digest_input = {
        key: receipt[key]
        for key in _NATIVE_RESERVATION_NO_SEND_FIELDS
        if key != "receipt_digest"
    }
    if receipt_digest != _native_full_digest(digest_input):
        raise SdkAdapterError(
            "stale-generation",
            "native reservation no-send receipt digest changed",
        )
    try:
        encoded_receipt = json.dumps(
            receipt,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise SdkAdapterError(
            "invalid", "native reservation no-send receipt is not strict JSON"
        ) from exc
    if len(encoded_receipt) > _NATIVE_RESERVATION_NO_SEND_MAX_BYTES:
        raise SdkAdapterError(
            "invalid", "native reservation no-send receipt exceeds its size bound"
        )
    return {
        key: copy.deepcopy(receipt[key]) for key in _NATIVE_RESERVATION_NO_SEND_FIELDS
    }


def _stream_binary(stream: Any) -> Any:
    """Use one unbuffered byte stream for each subprocess pipe when possible."""

    return getattr(stream, "buffer", stream)


def _event_type(event: Mapping[str, Any]) -> str:
    return str(_first_nonempty(event.get("type"), event.get("event"), "")).strip().lower().replace("_", "-")


def _event_data(event: Mapping[str, Any]) -> Mapping[str, Any]:
    data = event.get("data")
    if isinstance(data, Mapping):
        return data
    return event


def _event_value(event: Mapping[str, Any], *names: str) -> Any:
    data = _event_data(event)
    value = _get_ci(event, *names)
    if value is not None:
        return value
    return _get_ci(data, *names)


def _event_error(event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
    """Decode only an explicit runner refusal, never a model result message."""

    kind = _event_type(event)
    if kind not in {"adapter-error", "protocol-error", "runner-error"}:
        return None
    code = _first_nonempty(event.get("code"), "unknown")
    message = _first_nonempty(event.get("message"), event.get("error"), "runner refused the operation")
    return SdkAdapterError(str(code), str(message))


def _runtime_event_error(event: Mapping[str, Any]) -> Optional[SdkAdapterError]:
    """Surface an SDK error result even when no control waiter is active."""

    kind = _event_type(event)
    subtype = str(_first_nonempty(event.get("subtype"), _event_data(event).get("subtype"), "")).lower()
    if kind in {"error", "exception"} or subtype.startswith("error") or "error_during_execution" in subtype:
        return SdkAdapterError("loader-failed", InitializationTracker._error_message(event, _event_data(event)))
    return None


def _redact_runner_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Keep bounded lifecycle/error evidence without retaining model content."""

    kept: dict[str, Any] = {}
    for key in (
        "type",
        "event",
        "subtype",
        "code",
        "message",
        "participant_id",
        "session_id",
        "runner_instance_id",
        "request_id",
        "message_id",
        "tool_name",
        "tool_use_id",
        "hook_event",
        "hook_event_name",
        "active_turn",
        "turn_active",
        "turn_terminal",
        "drained",
        "participant_quiescent",
        "tools_quiescent",
        "quiescent",
        "accepted",
        "ack_kind",
        "uncertain",
    ):
        if key in event:
            value = event[key]
            if isinstance(value, str) and len(value) > 512:
                value = value[:512] + "…"
            kept[key] = value
    return kept


def _public_runner_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Remove adapter-internal request correlation before returning to control."""

    return {key: value for key, value in dict(event).items() if key != "request_id"}


def _process_pid_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _process_group_alive(pgid: Any) -> bool:
    if os.name != "posix" or not isinstance(pgid, int) or pgid <= 0:
        return False
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError) as exc:
        return isinstance(exc, PermissionError)
    except OSError:
        return False
    return True


def _process_start_token(pid: Any, process: Any = None) -> Optional[str]:
    """Return a bounded PID-incarnation token without claiming ancestry.

    Linux exposes a monotonic start tick in ``/proc/<pid>/stat``.  macOS does
    not expose that interface, so use ``ps``'s stable ``lstart`` value as the
    portable fallback.  A missing, timed-out, or malformed answer is unknown,
    never a claim that the PID is still the same process.
    """

    if not isinstance(pid, int) or pid <= 0:
        return None
    explicit = getattr(process, "process_start_token", None)
    if explicit is not None:
        token = str(explicit).strip()
        if token and len(token) <= 256 and "\x00" not in token:
            return token
        return None
    if os.name == "posix":
        try:
            stat_path = f"/proc/{pid}/stat"
            raw = Path(stat_path).read_text(encoding="utf-8")
            # The command name may contain spaces/parentheses.  The fields
            # after the final ')' start at proc-stat field 3; starttime is
            # field 22, hence offset 19 in that suffix.
            suffix = raw.rsplit(")", 1)[-1].split()
            if len(suffix) > 19 and re.fullmatch(r"[0-9]+", suffix[19]):
                return suffix[19]
        except (OSError, UnicodeError, ValueError):
            pass

    # ``ps -p ... -o lstart=`` is supported by the BSD/macOS and procps
    # implementations.  Keep the invocation shell-free and validate the
    # single-line result just as the state-layer helper does.  This fallback
    # is intentionally attempted after /proc so Linux keeps its stronger
    # monotonic token and does not change representation across refreshes.
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
    if token in {"?", "-"} or len(token) > 256 or "\x00" in token:
        return None
    return token


@dataclass(frozen=True)
class _RunnerReaderFailure:
    error: SdkAdapterError


class _RunnerConnection:
    """Private one-process connection with one continuous event demux reader.

    The supervisor never calls ``readline`` itself.  This object owns exactly
    one reader task and routes every bounded frame through a queue, retaining
    unsolicited runtime/tool/error evidence while a control waiter looks for
    its own correlated acknowledgement.
    """

    def __init__(
        self,
        participant_id: str,
        spec: RunnerSpec,
        process: Any,
        runner_instance_id: str,
        *,
        strict_process_group: bool = True,
        native_admission: Callable[[Mapping[str, Any]], Any] | None = None,
        native_stop_intent: Callable[[Mapping[str, Any]], Any] | None = None,
        native_stop_evidence: Callable[[Mapping[str, Any]], Any] | None = None,
        coordinator_interrupt_intent: Callable[[Mapping[str, Any]], Any] | None = None,
        coordinator_interrupt_evidence: Callable[[Mapping[str, Any]], Any] | None = None,
        coordinator_interrupt_validate: Callable[[Mapping[str, Any]], Any] | None = None,
        native_child_observation: Callable[[Mapping[str, Any]], Any] | None = None,
        native_swap_release: Callable[..., Any] | None = None,
    ) -> None:
        self.participant_id = _wire_id(participant_id, "participant_id")
        self.spec = spec
        marker_error = _native_swap_target_marker_error(spec)
        if marker_error is not None:
            raise SdkAdapterError("invalid", marker_error)
        self.process = process
        self.runner_instance_id = _wire_id(runner_instance_id, "runner_instance_id")
        self.strict_process_group = bool(strict_process_group)
        self.native_admission = native_admission
        self.native_stop_intent = native_stop_intent
        self.native_stop_evidence = native_stop_evidence
        self.coordinator_interrupt_intent = coordinator_interrupt_intent
        self.coordinator_interrupt_evidence = coordinator_interrupt_evidence
        self.coordinator_interrupt_validate = coordinator_interrupt_validate
        self.native_child_observation = native_child_observation
        self.native_swap_release = native_swap_release
        self._admission_tasks: set[asyncio.Task[Any]] = set()
        self._admission_ids: set[str] = set()
        self._stop_tasks: set[asyncio.Task[Any]] = set()
        self._stop_intent_ids: set[str] = set()
        self._stop_evidence_ids: set[str] = set()
        self._stop_intent_frames: dict[str, dict[str, Any]] = {}
        self._stop_evidence_frames: dict[str, dict[str, Any]] = {}
        self._stop_intent_inflight: set[str] = set()
        self._stop_evidence_inflight: set[str] = set()
        self._stop_intent_tasks: dict[str, asyncio.Task[Any]] = {}
        self._stop_evidence_tasks: dict[str, asyncio.Task[Any]] = {}
        # Coordinator-wide interrupt transactions have an independent
        # namespace and lifecycle map.  A task-stop ID or acknowledgement can
        # never satisfy a whole-roster interrupt waiter.
        self._coordinator_interrupt_tasks: set[asyncio.Task[Any]] = set()
        self._coordinator_interrupt_intent_ids: set[str] = set()
        self._coordinator_interrupt_evidence_ids: set[str] = set()
        self._coordinator_interrupt_intent_frames: dict[str, dict[str, Any]] = {}
        self._coordinator_interrupt_evidence_frames: dict[str, dict[str, Any]] = {}
        self._coordinator_interrupt_intent_inflight: set[str] = set()
        self._coordinator_interrupt_evidence_inflight: set[str] = set()
        self._coordinator_interrupt_intent_tasks: dict[str, asyncio.Task[Any]] = {}
        self._coordinator_interrupt_evidence_tasks: dict[str, asyncio.Task[Any]] = {}
        self._coordinator_interrupt_validate_ids: set[str] = set()
        self._coordinator_interrupt_validate_frames: dict[str, dict[str, Any]] = {}
        self._coordinator_interrupt_validate_inflight: set[str] = set()
        self._coordinator_interrupt_validate_tasks: dict[str, asyncio.Task[Any]] = {}
        self._native_swap_release_ids: set[str] = set()
        self._native_swap_release_frames: dict[str, dict[str, Any]] = {}
        self._native_swap_release_results: dict[str, dict[str, Any]] = {}
        self._native_swap_release_granted = False
        self._native_swap_release_inflight: set[str] = set()
        self._native_swap_release_tasks: dict[str, asyncio.Task[Any]] = {}
        # A callback task can be cancelled after the authority has seen the
        # request but before its result is delivered.  Retain the attempted
        # validation ID/frame as a tombstone; a replay of that ID must observe
        # uncertainty and never invoke the authority a second time.
        self._native_swap_release_tombstones: set[str] = set()
        self._native_child_observation_ids: set[str] = set()
        self._native_child_observation_frames: dict[str, dict[str, Any]] = {}
        self._native_child_observation_results: dict[str, dict[str, Any]] = {}
        self._native_child_observation_tombstones: set[str] = set()
        self._native_child_observation_inflight: set[str] = set()
        self._native_child_observation_tasks: dict[str, asyncio.Task[Any]] = {}
        self._native_child_observation_run_counts: dict[str, int] = {}
        self.frame_limit = spec.frame_limit
        self.startup_deadline = spec.startup_deadline
        self.operation_deadline = spec.operation_deadline
        self.bridge = _BoundedJsonLines(
            _stream_binary(getattr(process, "stdout", None)),
            _stream_binary(getattr(process, "stdin", None)),
            self.frame_limit,
        )
        self.events: asyncio.Queue[Any] = asyncio.Queue(maxsize=256)
        self.history: deque[dict[str, Any]] = deque(maxlen=512)
        self.reader_task: Optional[asyncio.Task[Any]] = None
        self._reader_error: Optional[SdkAdapterError] = None
        self._reader_done = False
        self._runtime_reader_done: Optional[bool] = None
        self._reader_frame_inflight = False
        self._last_fully_processed_cursor: Optional[int] = None
        self._reader_hooks_inflight = 0
        self._reader_stop_evidence_inflight = 0
        self._reader_coordinator_evidence_inflight = 0
        self._reader_native_child_observation_inflight = 0
        self._reader_native_child_observation_error = False
        # ``None`` means that the raw runner has not supplied the strict child
        # observation counters yet.  A native no-send status proof must not
        # turn that unknown into a zero; ordinary legacy/fake connections that
        # have no child-observation binder retain their existing compatibility.
        self._reader_native_child_observation_seen = False
        self.stderr_task: Optional[asyncio.Task[Any]] = None
        self.stderr_tail = bytearray()
        self.closed = False
        self.started = False
        self.ready = False
        self.released = False
        self.interrupt_receipts = 0
        self.shutdown_ack: Optional[dict[str, Any]] = None
        self.sent_message_ids: set[str] = set()
        self._reservation: Optional[dict[str, Any]] = None
        self._native_swap_release_boundary: Optional[dict[str, Any]] = None
        self._native_swap_release_attempted = False
        self._native_swap_target_requires_bound_release = (
            _native_swap_target_requires_bound_release(self.spec.fingerprint)
        )
        self._next_send_reservation_binding: Optional[dict[str, Any]] = None
        self._native_send_started = False
        # A reservation's transport-attempt marker is written before the
        # controller binder callback or any B query/control await.  Entries
        # are intentionally never evicted so a delayed status/recovery path
        # cannot mistake an old ambiguous attempt for a proven no-send.
        self._reservation_transport_attempts: dict[str, bool] = {}
        self.request_ids: set[str] = set()
        self._request_inflight: dict[str, str] = {}
        self._control_lock = asyncio.Lock()
        self._turn_active = False
        self._turn_terminal = True
        self._turn_drained = True
        self._participant_quiescent: Optional[bool] = True
        self._tools = _ToolEvidence()
        self._uncertain: list[dict[str, Any]] = []
        self._uncertain_overflow = False
        self._initialization: dict[str, Any] = {
            "account_email": None,
            "permission_mode": None,
            "model": None,
            "fingerprint": None,
        }
        self._group_evidence = self._capture_process_group()

    def _capture_process_group(self) -> dict[str, Any]:
        pid = getattr(self.process, "pid", None)
        pgid = getattr(self.process, "process_group_id", None)
        process_token = _process_start_token(pid, self.process)
        evidence: dict[str, Any] = {
            "pid": pid,
            "process_group_id": pgid,
            "process_start_token": process_token,
            "process_group_owned": False,
            "exited": False,
            "group_excluded": False,
        }
        explicit = getattr(self.process, "process_group_owned", None)
        if isinstance(explicit, bool):
            evidence["process_group_owned"] = explicit
        if isinstance(pid, int) and pid > 0 and os.name == "posix":
            try:
                pgid = os.getpgid(pid)
                sid = os.getsid(pid) if hasattr(os, "getsid") else None
                evidence["process_group_id"] = pgid
                evidence["process_group_owned"] = pgid == pid and (sid is None or sid == pid)
                evidence["process_start_token"] = _process_start_token(pid, self.process)
            except OSError:
                evidence["process_group_owned"] = False
        evidence["exited"] = not self.process_alive
        evidence["group_excluded"] = not _process_group_alive(evidence.get("process_group_id"))
        if self.strict_process_group and not evidence["process_group_owned"]:
            raise SdkAdapterError(
                "uncertain-effect",
                "dedicated SDK runner does not own a distinct process group",
            )
        if (
            self.strict_process_group
            and isinstance(pid, int)
            and pid > 0
            and not evidence.get("process_start_token")
        ):
            raise SdkAdapterError(
                "uncertain-effect",
                "dedicated SDK runner process start identity is unavailable",
            )
        return evidence

    @property
    def process_group_id(self) -> Optional[int]:
        value = self._group_evidence.get("process_group_id")
        return value if isinstance(value, int) else None

    @property
    def process_group_owned(self) -> bool:
        return bool(self._group_evidence.get("process_group_owned"))

    @property
    def process_alive(self) -> bool:
        poll = getattr(self.process, "poll", None)
        if callable(poll):
            try:
                return poll() is None
            except Exception:  # noqa: BLE001
                return True
        return True

    @property
    def participant_quiescent(self) -> bool:
        return self._participant_quiescent is True

    @property
    def tools_quiescent(self) -> bool:
        return self._tools.quiescent

    @property
    def reservation(self) -> Optional[dict[str, Any]]:
        """Current bounded reservation, never the caller's payload/body."""

        return None if self._reservation is None else copy.deepcopy(self._reservation)

    @property
    def native_send_started(self) -> bool:
        return self._native_send_started

    @property
    def quiescent(self) -> bool:
        return bool(
            self._turn_terminal
            and self._turn_drained
            and self.participant_quiescent
            and self.tools_quiescent
            and not self._native_child_observation_tasks
            and not self._native_child_observation_inflight
            and not self._uncertain
            and not self._uncertain_overflow
        )

    def _native_child_observation_connection_error(
        self,
    ) -> Optional[SdkAdapterError]:
        """Return a local child-observation barrier for every gate.

        The raw runner's reader reports a failed persistence callback as an
        adapter error, while a status frame reports the strict counters.  Keep
        both forms blocking and never infer a successful zero from an absent
        status field.
        """

        if self._reader_native_child_observation_error:
            return SdkAdapterError(
                "uncertain-effect",
                "native child observation persistence reported an error",
            )
        if self._reader_native_child_observation_inflight:
            return SdkAdapterError(
                "busy",
                "native child observation persistence is still in flight",
            )
        for task in self._native_child_observation_tasks.values():
            if not task.done():
                return SdkAdapterError(
                    "busy",
                    "native child observation callback is still in flight",
                )
        if self._reader_error is not None and "child observation" in self._reader_error.message:
            return self._reader_error
        for item in self._uncertain:
            text = " ".join(str(item.get(key, "")) for key in ("operation", "message", "reason"))
            if "child observation" in text:
                return SdkAdapterError(
                    str(item.get("code") or "uncertain-effect"),
                    "native child observation evidence is uncertain",
                )
        return None

    def _cancel_native_child_observation_tasks(self, message: str) -> None:
        """Cancel child persistence callbacks after an uncorrelated fatal frame."""

        for task in list(self._native_child_observation_tasks.values()):
            if task.done():
                continue
            self._record_uncertain({
                "operation": "native-child-observation",
                "code": "uncertain-effect",
                "message": message,
            })
            task.cancel()

    def evidence(self) -> dict[str, Any]:
        process = dict(self._group_evidence)
        process["exited"] = not self.process_alive
        process["group_excluded"] = not _process_group_alive(process.get("process_group_id"))
        return {
            "participant_id": self.participant_id,
            "session_id": self.spec.session_id,
            "runner_instance_id": self.runner_instance_id,
            "ready": self.ready,
            "released": self.released,
            "active_turn": self._turn_active,
            "turn_terminal": self._turn_terminal,
            "drained": self._turn_drained,
            "participant_quiescent": self.participant_quiescent,
            "tools_quiescent": self.tools_quiescent,
            "quiescent": self.quiescent,
            "process": process,
            "initialization": dict(self._initialization),
            "tools": self._tools.snapshot(),
            "uncertain_effects": list(self._uncertain),
            "uncertain_effects_overflow": self._uncertain_overflow,
            "native_child_observation_inflight": len(
                self._native_child_observation_inflight
            ),
            "native_child_observation_pending": len(
                [task for task in self._native_child_observation_tasks.values() if not task.done()]
            ),
            "native_child_observation_error": self._reader_native_child_observation_error,
            "native_child_observation_status_seen": self._reader_native_child_observation_seen,
            "events_seen": len(self.history),
            "native_invocation_reservation": self.reservation,
            "native_swap_release_boundary": (
                None
                if self._native_swap_release_boundary is None
                else copy.deepcopy(self._native_swap_release_boundary)
            ),
            # Keep the short observational alias for older status consumers;
            # both values are the same detached, bounded canonical response.
            "reservation": self.reservation,
        }

    def start_reader(self) -> None:
        if self.reader_task is None:
            self.reader_task = asyncio.create_task(
                self._read_events(),
                name=f"lane-managed-runner-reader-{self.participant_id}",
            )
        if self.stderr_task is None and getattr(self.process, "stderr", None) is not None:
            self.stderr_task = asyncio.create_task(
                self._drain_stderr(),
                name=f"lane-managed-runner-stderr-{self.participant_id}",
            )

    async def _drain_stderr(self) -> None:
        """Continuously drain diagnostics so SDK/CLI stderr cannot deadlock."""

        stream = _stream_binary(getattr(self.process, "stderr", None))
        if stream is None:
            return
        try:
            fileno = stream.fileno()
        except (AttributeError, OSError, ValueError):
            fileno = None
        if fileno is None:
            # This branch is test/fallback only.  It is bounded per read and
            # cancellation is handled by the owning process close path.
            while True:
                chunk = await asyncio.to_thread(stream.read, 4096)
                if not chunk:
                    return
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8", "replace")
                self.stderr_tail.extend(chunk[-4096:])
                del self.stderr_tail[:-16384]
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[None] = loop.create_future()

        def on_readable() -> None:
            try:
                chunk = os.read(fileno, 65536)
                if not chunk:
                    if not waiter.done():
                        waiter.set_result(None)
                    return
                self.stderr_tail.extend(chunk)
                del self.stderr_tail[:-16384]
            except BlockingIOError:
                return
            except BaseException as exc:  # noqa: BLE001
                if not waiter.done():
                    waiter.set_exception(exc)

        try:
            try:
                loop.add_reader(fileno, on_readable)
            except (NotImplementedError, OSError):
                # A Windows/fake stream may lack an event-loop reader.  The
                # process is still bounded by the shutdown owner.
                while True:
                    chunk = await asyncio.to_thread(stream.read, 4096)
                    if not chunk:
                        return
                    if isinstance(chunk, str):
                        chunk = chunk.encode("utf-8", "replace")
                    self.stderr_tail.extend(chunk[-4096:])
                    del self.stderr_tail[:-16384]
            await waiter
        except asyncio.CancelledError:
            raise
        except Exception:
            # Diagnostics never replace a more authoritative runtime refusal.
            return
        finally:
            if fileno is not None:
                try:
                    loop.remove_reader(fileno)
                except (NotImplementedError, OSError):
                    pass

    async def _read_events(self) -> None:
        try:
            while True:
                event = await self.bridge.read()
                if not isinstance(event, Mapping):
                    raise SdkAdapterError("invalid", "runner emitted a non-object event")
                event = dict(event)
                if _event_type(event) == "native-admission-intent":
                    self._validate_event_identity(event)
                    self._start_native_admission(event)
                    continue
                if _event_type(event) == "native-stop-intent":
                    self._validate_event_identity(event)
                    self._start_native_stop_intent(event)
                    continue
                if _event_type(event) == "native-stop-evidence":
                    self._validate_event_identity(event)
                    self._start_native_stop_evidence(event)
                    continue
                if _event_type(event) == "coordinator-interrupt-intent":
                    self._validate_event_identity(event)
                    self._start_coordinator_interrupt_intent(event)
                    continue
                if _event_type(event) == "coordinator-interrupt-evidence":
                    self._validate_event_identity(event)
                    self._start_coordinator_interrupt_evidence(event)
                    continue
                if _event_type(event) == "coordinator-interrupt-validate":
                    self._validate_event_identity(event)
                    self._start_coordinator_interrupt_validate(event)
                    continue
                if _event_type(event) == "native-child-observation":
                    self._validate_event_identity(event)
                    self._start_native_child_observation(event)
                    continue
                if _event_type(event) == "native-swap-release-authorize":
                    self._validate_event_identity(event)
                    self._start_native_swap_release(event)
                    continue
                self._observe_event(event)
                # Control replies and errors must be delivered to the current
                # waiter.  Ordinary model/token events are already represented
                # by bounded lifecycle/tool evidence and are not allowed to
                # back-pressure stdout until the SDK deadlocks.
                kind = _event_type(event)
                explicit_error = _event_error(event)
                error = explicit_error
                if error is None:
                    error = _runtime_event_error(event)
                if error is not None and _event_error(event) is None:
                    await self.events.put(_RunnerReaderFailure(error))
                    return
                if (
                    explicit_error is not None
                    and event.get("request_id") is None
                ):
                    # An uncorrelated adapter/protocol error terminates the
                    # runner boundary.  Do not leave a controller callback
                    # awaiting an ACK after the other side has closed.
                    self._cancel_native_child_observation_tasks(
                        "native child observation callback was cancelled after runner channel failure"
                    )
                if error is not None or kind in {
                    "ready-held",
                    "interrupt-ack",
                    "released",
                    "status",
                    "query-dispatched",
                    "shutdown-ack",
                    "native-stop-ack",
                    "coordinator-interrupt-ack",
                    "prepare-invocation-ack",
                    "runner-result",
                }:
                    try:
                        self.events.put_nowait(event)
                    except asyncio.QueueFull:
                        raise SdkAdapterError("invalid", "runner acknowledgement queue overflowed")
        except StopAsyncIteration:
            self._reader_error = SdkAdapterError(
                "loader-failed", "runner closed its event stream"
            )
            await self.events.put(_RunnerReaderFailure(self._reader_error))
        except asyncio.CancelledError:
            raise
        except SdkAdapterError as exc:
            self._reader_error = exc
            await self.events.put(_RunnerReaderFailure(exc))
        except Exception as exc:  # noqa: BLE001
            self._reader_error = SdkAdapterError(
                "loader-failed", f"runner event reader failed: {exc}"
            )
            await self.events.put(_RunnerReaderFailure(self._reader_error))
        finally:
            self._reader_done = True
            # Persistence may already have committed when transport disappears.
            # Cancelling these tasks does not undo it or permit replay.
            tasks = list(self._admission_tasks)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            tasks = list(self._stop_tasks)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            tasks = list(self._coordinator_interrupt_tasks)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            tasks = list(self._native_child_observation_tasks.values())
            self._cancel_native_child_observation_tasks(
                "native child observation callback was cancelled at reader close"
            )
            await asyncio.gather(*tasks, return_exceptions=True)

    def _start_native_admission(self, event: Mapping[str, Any]) -> None:
        admission = event.get("admission")
        admission_id = _wire_id(event.get("admission_id"), "admission_id")
        if not isinstance(admission, Mapping) or admission.get("admission_id") != admission_id:
            raise SdkAdapterError("invalid", "native admission intent is malformed")
        if admission_id in self._admission_ids or len(self._admission_ids) >= MAX_NATIVE_LIFECYCLE_EVENTS:
            raise SdkAdapterError("busy", "native admission intent is duplicate or history is full")
        if len(self._admission_tasks) >= MAX_NATIVE_CHILD_RECORDS:
            raise SdkAdapterError("busy", "too many pending native admissions")
        self._admission_ids.add(admission_id)
        task = asyncio.create_task(
            self._answer_native_admission(copy.deepcopy(dict(admission))),
            name=f"lane-managed-native-admission-{admission_id}",
        )
        self._admission_tasks.add(task)
        task.add_done_callback(self._admission_tasks.discard)

    async def _answer_native_admission(self, admission: Mapping[str, Any]) -> None:
        # A refusal may echo correlation; success must originate in the bound
        # controller callback and is never synthesized from request content.
        ack = {key: admission.get(key) for key in _ADMISSION_ACK_FIELDS}
        ack["accepted"] = False
        try:
            context = self.spec.fingerprint.get("lineage_context")
            if not isinstance(context, Mapping) and not self.spec.read_only:
                context = self.spec.fingerprint.get("lineage_claim")
            if not isinstance(context, Mapping) or any(
                key not in context or type(admission.get(key)) is not type(context[key])
                or admission.get(key) != context[key]
                for key in ("owner_generation", "lineage_id", "runner_incarnation")
            ):
                raise SdkAdapterError("stale-generation", "native admission differs from configured lineage context")
            parent = admission.get("parent")
            if not isinstance(parent, Mapping) or parent.get("session_id") != self.spec.session_id:
                raise SdkAdapterError("stale-generation", "native admission has another parent session")
            definitions = self.spec.fingerprint.get("trusted_definitions")
            name = admission.get("agent_type")
            if (not isinstance(definitions, Mapping) or not isinstance(name, str)
                    or name not in definitions
                    or admission.get("trusted_definition_digest") != _native_full_digest(definitions[name])):
                raise SdkAdapterError("unsupported", "native admission differs from configured definition")
            if self.native_admission is None:
                raise SdkAdapterError("unsupported", "native admission callback is not bound")

            async def persist() -> Any:
                return await _maybe_await(self.native_admission(copy.deepcopy(dict(admission))))

            result = await _await_bounded(persist(), _NATIVE_ADMISSION_DEADLINE)
            if not _admission_ack_matches(result, admission):
                raise SdkAdapterError("invalid", "native admission callback returned an invalid acknowledgement")
            # Emit only the correlation tuple and boolean, not arbitrary
            # controller diagnostics or any secret-bearing exception text.
            ack["accepted"] = result["accepted"]
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            ack["code"] = "loader-failed"
        except SdkAdapterError as exc:
            ack["code"] = exc.code
        except Exception:
            ack["code"] = "loader-failed"
        try:
            # Do not acquire _control_lock: send() can hold it while query()
            # waits for this hook. The bridge serializes frame writes only.
            await _await_bounded(self.bridge.write({
                "operation": "native-admission-ack",
                "participant_id": self.participant_id,
                "session_id": self.spec.session_id,
                "runner_instance_id": self.runner_instance_id,
                "admission_id": admission["admission_id"], "ack": ack,
            }), self.operation_deadline)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({"operation": "native-admission-ack", "admission_id": admission["admission_id"]})

    def _start_native_child_observation(self, event: Mapping[str, Any]) -> None:
        expected = set(_NATIVE_CHILD_OBSERVATION_FRAME_FIELDS)
        if set(event) != expected or event.get("type") != "native-child-observation":
            raise SdkAdapterError("invalid", "native child observation frame is malformed")
        observation = _native_child_observation(event.get("observation"))
        observation_id = observation["observation_id"]
        run_id = _native_child_observation_run_id(observation)
        frame = copy.deepcopy(dict(event))
        frame["observation"] = observation
        if len(self._native_child_observation_tasks) >= MAX_NATIVE_CHILD_OBSERVATIONS:
            raise SdkAdapterError(
                "busy", "too many pending native child observation transactions"
            )
        previous = self._native_child_observation_frames.get(observation_id)
        if previous is not None and previous != frame:
            task = asyncio.create_task(
                self._answer_native_child_observation_refusal(
                    observation_id, "stale-generation"
                ),
                name="lane-managed-native-child-observation-conflict-" + observation_id,
            )
            self._native_child_observation_tasks[observation_id] = task
            task.add_done_callback(
                lambda done: self._native_child_observation_tasks.pop(
                    observation_id, None
                )
            )
            return
        previous_result = self._native_child_observation_results.get(observation_id)
        if previous_result is not None:
            task = asyncio.create_task(
                self._answer_native_child_observation_duplicate(
                    observation_id, previous_result
                ),
                name="lane-managed-native-child-observation-duplicate-" + observation_id,
            )
            self._native_child_observation_tasks[observation_id] = task
            task.add_done_callback(
                lambda done: self._native_child_observation_tasks.pop(
                    observation_id, None
                )
            )
            return
        if previous is not None:
            existing = self._native_child_observation_tasks.get(observation_id)
            if existing is not None and existing.done():
                self._native_child_observation_tasks.pop(observation_id, None)
                self._native_child_observation_inflight.discard(observation_id)
                existing = None
            if existing is None and observation_id not in self._native_child_observation_tombstones:
                # A task that ended before caching an ACK crossed the private
                # authority boundary and is therefore permanently uncertain.
                self._native_child_observation_tombstones.add(observation_id)
                refusal = _native_child_observation_refusal(
                    observation_id, "uncertain-effect"
                )
                self._native_child_observation_results[observation_id] = refusal
                task = asyncio.create_task(
                    self._answer_native_child_observation_duplicate(
                        observation_id, refusal
                    ),
                    name="lane-managed-native-child-observation-tombstone-" + observation_id,
                )
                self._native_child_observation_tasks[observation_id] = task
                task.add_done_callback(
                    lambda done: self._native_child_observation_tasks.pop(
                        observation_id, None
                    )
                )
                return
            if existing is None and observation_id in self._native_child_observation_tombstones:
                # Cancellation/EOF can happen after the callback crossed its
                # private authority boundary but before an ACK was cached.
                # The tombstone is terminal for this observation ID; replaying
                # the same frame would create a second persistence attempt.
                task = asyncio.create_task(
                    self._answer_native_child_observation_refusal(
                        observation_id, "uncertain-effect"
                    ),
                    name="lane-managed-native-child-observation-tombstone-replay-"
                    + observation_id,
                )
                self._native_child_observation_tasks[observation_id] = task
                task.add_done_callback(
                    lambda done: self._native_child_observation_tasks.pop(
                        observation_id, None
                    )
                )
                return
            if existing is not None or observation_id in self._native_child_observation_inflight:
                task = asyncio.create_task(
                    self._answer_native_child_observation_refusal(
                        observation_id, "busy"
                    ),
                    name="lane-managed-native-child-observation-inflight-" + observation_id,
                )
                self._native_child_observation_tasks[observation_id] = task
                task.add_done_callback(
                    lambda done: self._native_child_observation_tasks.pop(
                        observation_id, None
                    )
                )
                return
        if previous is None:
            if (
                run_id not in self._native_child_observation_run_counts
                and len(self._native_child_observation_run_counts)
                >= MAX_NATIVE_CHILD_RUNS
            ):
                raise SdkAdapterError(
                    "busy", "native child observation child-run history is full"
                )
            if (
                self._native_child_observation_run_counts.get(run_id, 0)
                >= MAX_NATIVE_CHILD_OBSERVATIONS_PER_RUN
            ):
                raise SdkAdapterError(
                    "busy", "native child observation history is full for this child run"
                )
            self._native_child_observation_ids.add(observation_id)
            self._native_child_observation_frames[observation_id] = frame
            self._native_child_observation_run_counts[run_id] = (
                self._native_child_observation_run_counts.get(run_id, 0) + 1
            )
        self._native_child_observation_inflight.add(observation_id)
        task = asyncio.create_task(
            self._answer_native_child_observation(frame),
            name="lane-managed-native-child-observation-" + observation_id,
        )
        self._native_child_observation_tasks[observation_id] = task

        def finish(done: asyncio.Task[Any]) -> None:
            self._native_child_observation_inflight.discard(observation_id)
            if self._native_child_observation_tasks.get(observation_id) is done:
                self._native_child_observation_tasks.pop(observation_id, None)

        task.add_done_callback(finish)

    async def _answer_native_child_observation_refusal(
        self, observation_id: Any, code: str
    ) -> None:
        acknowledgement = _native_child_observation_refusal(observation_id, code)
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "native-child-observation-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "observation_id": acknowledgement["observation_id"],
                    "ack": acknowledgement,
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "native-child-observation-ack",
                "observation_id": acknowledgement["observation_id"],
            })

    async def _answer_native_child_observation_duplicate(
        self, observation_id: Any, acknowledgement: Mapping[str, Any]
    ) -> None:
        try:
            observation_id = _wire_id(observation_id, "native child observation_id")
        except SdkAdapterError:
            observation_id = "invalid-observation-id"
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "native-child-observation-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "observation_id": observation_id,
                    "ack": copy.deepcopy(dict(acknowledgement)),
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "native-child-observation-ack",
                "observation_id": observation_id,
            })

    async def _answer_native_child_observation(
        self, frame: Mapping[str, Any]
    ) -> None:
        observation = frame.get("observation")
        observation_id = observation.get("observation_id") if isinstance(observation, Mapping) else None
        acknowledgement: Mapping[str, Any]
        try:
            self._validate_event_identity(frame)
            observation = _native_child_observation(observation)
            observation_id = observation["observation_id"]
            if not self.started or not self.ready:
                raise SdkAdapterError(
                    "unsupported", "native child observation requires an owned started runner"
                )
            if self.native_child_observation is None:
                raise SdkAdapterError(
                    "unsupported", "native child observation callback is not bound"
                )
            result = await _await_bounded(
                _maybe_await(
                    self.native_child_observation(copy.deepcopy(dict(frame)))
                ),
                self.operation_deadline,
            )
            if not _native_child_observation_ack_matches(result, observation):
                raise SdkAdapterError(
                    "invalid", "native child observation callback returned an invalid acknowledgement"
                )
            if self.closed or not self.started or not self.process_alive:
                raise SdkAdapterError(
                    "stale-generation",
                    "native child observation runner changed while awaiting authority",
                )
            self._validate_event_identity(frame)
            acknowledgement = dict(result)
        except asyncio.CancelledError:
            self._native_child_observation_tombstones.add(str(observation_id))
            self._record_uncertain({
                "operation": "native-child-observation",
                "observation_id": observation_id,
                "code": "uncertain-effect",
                "message": "native child observation callback was cancelled",
            })
            raise
        except asyncio.TimeoutError:
            acknowledgement = _native_child_observation_refusal(
                observation_id, "loader-failed"
            )
        except SdkAdapterError as exc:
            acknowledgement = _native_child_observation_refusal(
                observation_id, exc.code
            )
        except Exception:
            acknowledgement = _native_child_observation_refusal(
                observation_id, "loader-failed"
            )
        if acknowledgement.get("recorded") is not True:
            self._native_child_observation_tombstones.add(str(observation_id))
            self._record_uncertain({
                "operation": "native-child-observation",
                "observation_id": observation_id,
                "code": acknowledgement.get("code", "loader-failed"),
            })
        self._native_child_observation_results[str(observation_id)] = copy.deepcopy(
            dict(acknowledgement)
        )
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "native-child-observation-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "observation_id": observation_id,
                    "ack": dict(acknowledgement),
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            self._native_child_observation_tombstones.add(str(observation_id))
            self._record_uncertain({
                "operation": "native-child-observation-ack",
                "observation_id": observation_id,
                "code": "uncertain-effect",
            })
            raise
        except Exception:
            self._record_uncertain({
                "operation": "native-child-observation-ack",
                "observation_id": observation_id,
            })

    def _start_native_stop_intent(self, event: Mapping[str, Any]) -> None:
        stop = event.get("stop")
        if not isinstance(stop, Mapping):
            raise SdkAdapterError("invalid", "native stop intent is malformed")
        stop_id = _wire_id(stop.get("stop_id"), "stop_id")
        frame = copy.deepcopy(dict(event))
        if len(self._stop_tasks) >= MAX_NATIVE_CHILD_RECORDS:
            raise SdkAdapterError("busy", "too many pending native stop transactions")
        previous = self._stop_intent_frames.get(stop_id)
        if previous is not None and previous != frame:
            task = asyncio.create_task(
                self._answer_native_stop_intent_refusal(stop_id, "stale-generation"),
                name=f"lane-managed-native-stop-intent-refusal-{stop_id}",
            )
            self._stop_tasks.add(task)
            task.add_done_callback(self._stop_tasks.discard)
            return
        if previous is None and len(self._stop_intent_ids) >= MAX_NATIVE_LIFECYCLE_EVENTS:
            raise SdkAdapterError("busy", "native stop intent is duplicate or history is full")
        if previous is None:
            self._stop_intent_ids.add(stop_id)
            self._stop_intent_frames[stop_id] = frame
        inflight = self._stop_intent_tasks.get(stop_id)
        if inflight is not None and inflight.done():
            self._stop_intent_tasks.pop(stop_id, None)
            self._stop_intent_inflight.discard(stop_id)
            inflight = None
        if inflight is not None or stop_id in self._stop_intent_inflight:
            # A retry while the first durable callback is still running gets
            # a bounded refusal.  A later retry is sent through the durable
            # callback again, so a positive authorization is never cached in
            # this transport.
            task = asyncio.create_task(
                self._answer_native_stop_intent_refusal(stop_id, "busy"),
                name=f"lane-managed-native-stop-intent-inflight-{stop_id}",
            )
            self._stop_tasks.add(task)
            task.add_done_callback(self._stop_tasks.discard)
            return
        self._stop_intent_inflight.add(stop_id)
        task = asyncio.create_task(
            self._answer_native_stop_intent(frame),
            name=f"lane-managed-native-stop-intent-{stop_id}",
        )
        self._stop_tasks.add(task)
        self._stop_intent_tasks[stop_id] = task
        def finish(done: asyncio.Task[Any]) -> None:
            self._stop_tasks.discard(done)
            self._stop_intent_inflight.discard(stop_id)
            if self._stop_intent_tasks.get(stop_id) is done:
                self._stop_intent_tasks.pop(stop_id, None)
        task.add_done_callback(finish)

    def _start_native_stop_evidence(self, event: Mapping[str, Any]) -> None:
        evidence = event.get("evidence")
        if not isinstance(evidence, Mapping):
            raise SdkAdapterError("invalid", "native stop evidence is malformed")
        evidence_id = _wire_id(evidence.get("evidence_id"), "evidence_id")
        frame = copy.deepcopy(dict(event))
        if len(self._stop_tasks) >= MAX_NATIVE_CHILD_RECORDS:
            raise SdkAdapterError("busy", "too many pending native stop transactions")
        previous = self._stop_evidence_frames.get(evidence_id)
        if previous is not None and previous != frame:
            task = asyncio.create_task(
                self._answer_native_stop_evidence_refusal(evidence_id, evidence.get("stop_id"), "stale-generation"),
                name=f"lane-managed-native-stop-evidence-refusal-{evidence_id}",
            )
            self._stop_tasks.add(task)
            task.add_done_callback(self._stop_tasks.discard)
            return
        if previous is None and len(self._stop_evidence_ids) >= MAX_NATIVE_LIFECYCLE_EVENTS:
            raise SdkAdapterError("busy", "native stop evidence is duplicate or history is full")
        if previous is None:
            self._stop_evidence_ids.add(evidence_id)
            self._stop_evidence_frames[evidence_id] = frame
        inflight = self._stop_evidence_tasks.get(evidence_id)
        if inflight is not None and inflight.done():
            self._stop_evidence_tasks.pop(evidence_id, None)
            self._stop_evidence_inflight.discard(evidence_id)
            inflight = None
        if inflight is not None or evidence_id in self._stop_evidence_inflight:
            task = asyncio.create_task(
                self._answer_native_stop_evidence_refusal(evidence_id, evidence.get("stop_id"), "busy"),
                name=f"lane-managed-native-stop-evidence-inflight-{evidence_id}",
            )
            self._stop_tasks.add(task)
            task.add_done_callback(self._stop_tasks.discard)
            return
        self._stop_evidence_inflight.add(evidence_id)
        task = asyncio.create_task(
            self._answer_native_stop_evidence(frame),
            name=f"lane-managed-native-stop-evidence-{evidence_id}",
        )
        self._stop_tasks.add(task)
        self._stop_evidence_tasks[evidence_id] = task
        def finish(done: asyncio.Task[Any]) -> None:
            self._stop_tasks.discard(done)
            self._stop_evidence_inflight.discard(evidence_id)
            if self._stop_evidence_tasks.get(evidence_id) is done:
                self._stop_evidence_tasks.pop(evidence_id, None)
        task.add_done_callback(finish)

    def _start_coordinator_interrupt_intent(self, event: Mapping[str, Any]) -> None:
        expected = {
            "type", "participant_id", "session_id", "runner_instance_id",
            "interrupt",
        }
        if set(event) != expected:
            raise SdkAdapterError(
                "invalid", "coordinator interrupt intent is malformed"
            )
        interrupt = event.get("interrupt")
        if not isinstance(interrupt, Mapping):
            raise SdkAdapterError(
                "invalid", "coordinator interrupt intent is malformed"
            )
        interrupt_id = _wire_id(interrupt.get("interrupt_id"), "interrupt_id")
        frame = copy.deepcopy(dict(event))
        if len(self._coordinator_interrupt_tasks) >= MAX_NATIVE_CHILD_RECORDS:
            raise SdkAdapterError(
                "busy", "too many pending coordinator interrupt transactions"
            )
        previous = self._coordinator_interrupt_intent_frames.get(interrupt_id)
        if previous is not None and previous != frame:
            task = asyncio.create_task(
                self._answer_coordinator_interrupt_intent_refusal(
                    interrupt_id, "stale-generation"
                ),
                name=(
                    "lane-managed-coordinator-interrupt-intent-refusal-"
                    + interrupt_id
                ),
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        if (
            previous is None
            and len(self._coordinator_interrupt_intent_ids)
            >= MAX_NATIVE_LIFECYCLE_EVENTS
        ):
            raise SdkAdapterError(
                "busy", "coordinator interrupt intent is duplicate or history is full"
            )
        if previous is None:
            self._coordinator_interrupt_intent_ids.add(interrupt_id)
            self._coordinator_interrupt_intent_frames[interrupt_id] = frame
        inflight = self._coordinator_interrupt_intent_tasks.get(interrupt_id)
        if inflight is not None and inflight.done():
            self._coordinator_interrupt_intent_tasks.pop(interrupt_id, None)
            self._coordinator_interrupt_intent_inflight.discard(interrupt_id)
            inflight = None
        if inflight is not None or interrupt_id in self._coordinator_interrupt_intent_inflight:
            # A retry while the durable callback is running receives a bounded
            # refusal.  A later retry calls the controller again; the adapter
            # never caches or replays a positive authorization.
            task = asyncio.create_task(
                self._answer_coordinator_interrupt_intent_refusal(
                    interrupt_id, "busy"
                ),
                name=(
                    "lane-managed-coordinator-interrupt-intent-inflight-"
                    + interrupt_id
                ),
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        self._coordinator_interrupt_intent_inflight.add(interrupt_id)
        task = asyncio.create_task(
            self._answer_coordinator_interrupt_intent(frame),
            name="lane-managed-coordinator-interrupt-intent-" + interrupt_id,
        )
        self._coordinator_interrupt_tasks.add(task)
        self._coordinator_interrupt_intent_tasks[interrupt_id] = task

        def finish(done: asyncio.Task[Any]) -> None:
            self._coordinator_interrupt_tasks.discard(done)
            self._coordinator_interrupt_intent_inflight.discard(interrupt_id)
            if self._coordinator_interrupt_intent_tasks.get(interrupt_id) is done:
                self._coordinator_interrupt_intent_tasks.pop(interrupt_id, None)

        task.add_done_callback(finish)

    def _start_coordinator_interrupt_evidence(self, event: Mapping[str, Any]) -> None:
        expected = {
            "type", "participant_id", "session_id", "runner_instance_id",
            "evidence",
        }
        if set(event) != expected:
            raise SdkAdapterError(
                "invalid", "coordinator interrupt evidence is malformed"
            )
        evidence = event.get("evidence")
        if not isinstance(evidence, Mapping):
            raise SdkAdapterError(
                "invalid", "coordinator interrupt evidence is malformed"
            )
        evidence_id = _wire_id(evidence.get("evidence_id"), "evidence_id")
        interrupt_id = _wire_id(evidence.get("interrupt_id"), "interrupt_id")
        frame = copy.deepcopy(dict(event))
        if len(self._coordinator_interrupt_tasks) >= MAX_NATIVE_CHILD_RECORDS:
            raise SdkAdapterError(
                "busy", "too many pending coordinator interrupt transactions"
            )
        previous = self._coordinator_interrupt_evidence_frames.get(evidence_id)
        if previous is not None and previous != frame:
            task = asyncio.create_task(
                self._answer_coordinator_interrupt_evidence_refusal(
                    evidence_id, interrupt_id, "stale-generation"
                ),
                name=(
                    "lane-managed-coordinator-interrupt-evidence-refusal-"
                    + evidence_id
                ),
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        if (
            previous is None
            and len(self._coordinator_interrupt_evidence_ids)
            >= MAX_NATIVE_LIFECYCLE_EVENTS
        ):
            raise SdkAdapterError(
                "busy", "coordinator interrupt evidence is duplicate or history is full"
            )
        if previous is None:
            self._coordinator_interrupt_evidence_ids.add(evidence_id)
            self._coordinator_interrupt_evidence_frames[evidence_id] = frame
        inflight = self._coordinator_interrupt_evidence_tasks.get(evidence_id)
        if inflight is not None and inflight.done():
            self._coordinator_interrupt_evidence_tasks.pop(evidence_id, None)
            self._coordinator_interrupt_evidence_inflight.discard(evidence_id)
            inflight = None
        if inflight is not None or evidence_id in self._coordinator_interrupt_evidence_inflight:
            task = asyncio.create_task(
                self._answer_coordinator_interrupt_evidence_refusal(
                    evidence_id, interrupt_id, "busy"
                ),
                name=(
                    "lane-managed-coordinator-interrupt-evidence-inflight-"
                    + evidence_id
                ),
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        self._coordinator_interrupt_evidence_inflight.add(evidence_id)
        task = asyncio.create_task(
            self._answer_coordinator_interrupt_evidence(frame),
            name="lane-managed-coordinator-interrupt-evidence-" + evidence_id,
        )
        self._coordinator_interrupt_tasks.add(task)
        self._coordinator_interrupt_evidence_tasks[evidence_id] = task

        def finish(done: asyncio.Task[Any]) -> None:
            self._coordinator_interrupt_tasks.discard(done)
            self._coordinator_interrupt_evidence_inflight.discard(evidence_id)
            if self._coordinator_interrupt_evidence_tasks.get(evidence_id) is done:
                self._coordinator_interrupt_evidence_tasks.pop(evidence_id, None)

        task.add_done_callback(finish)

    def _start_native_swap_release(self, event: Mapping[str, Any]) -> None:
        expected = {
            "type", "participant_id", "session_id", "runner_instance_id",
            "validation_id", "binding",
        }
        if set(event) != expected or event.get("type") != "native-swap-release-authorize":
            raise SdkAdapterError(
                "invalid", "native swap release authorization is malformed"
            )
        if len(self._coordinator_interrupt_tasks) >= MAX_NATIVE_CHILD_RECORDS:
            raise SdkAdapterError(
                "busy", "too many pending native swap release authorizations"
            )
        validation_id = _wire_id(event.get("validation_id"), "validation_id")
        binding = _native_swap_binding(event.get("binding"))
        frame = copy.deepcopy(dict(event))
        frame["binding"] = binding
        previous = self._native_swap_release_frames.get(validation_id)
        if previous is not None and previous != frame:
            task = asyncio.create_task(
                self._answer_native_swap_release_refusal(
                    validation_id, binding, "stale-generation"
                ),
                name="lane-managed-native-swap-release-refusal-" + validation_id,
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        previous_ack = self._native_swap_release_results.get(validation_id)
        if previous_ack is not None:
            task = asyncio.create_task(
                self._answer_native_swap_release_duplicate(
                    validation_id, binding, previous_ack.get("authorization_id")
                ),
                name="lane-managed-native-swap-release-duplicate-" + validation_id,
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        # One runner owns at most one release authorization transaction.  A
        # new validation ID is never a local retry/reissue (the controller's
        # durable authority is the only recovery owner), so refuse it before
        # adding another frame/task/history entry.
        if previous is None and self._native_swap_release_ids:
            task = asyncio.create_task(
                self._answer_native_swap_release_refusal(
                    validation_id, binding, "uncertain-effect"
                ),
                name="lane-managed-native-swap-release-new-id-refusal-" + validation_id,
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        # ``_answer_native_swap_release`` may have been cancelled after the
        # callback crossed its private IPC boundary but before a result was
        # recorded.  The original frame/ID is deliberately retained above;
        # once its task is gone, convert it to a sticky uncertain observation
        # instead of recalling the controller callback.  This is the local
        # at-most-once fence for cancellation/lost-ACK windows.
        inflight = self._native_swap_release_tasks.get(validation_id)
        if (
            previous is not None
            and previous_ack is None
            and (
                (inflight is not None and inflight.done())
                or (
                    inflight is None
                    and validation_id not in self._native_swap_release_inflight
                )
            )
        ):
            self._native_swap_release_tombstones.add(validation_id)
            tombstone = _native_swap_refusal_ack(
                validation_id, binding, "refused-uncertain-effect"
            )
            self._native_swap_release_results[validation_id] = copy.deepcopy(tombstone)
            task = asyncio.create_task(
                self._answer_native_swap_release_duplicate(
                    validation_id, binding, tombstone.get("authorization_id")
                ),
                name="lane-managed-native-swap-release-tombstone-" + validation_id,
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        if previous is None:
            if len(self._native_swap_release_ids) >= MAX_NATIVE_LIFECYCLE_EVENTS:
                raise SdkAdapterError(
                    "busy", "native swap release authorization history is full"
                )
            self._native_swap_release_ids.add(validation_id)
            self._native_swap_release_frames[validation_id] = frame
        if inflight is not None and inflight.done():
            self._native_swap_release_tasks.pop(validation_id, None)
            self._native_swap_release_inflight.discard(validation_id)
            inflight = None
        if inflight is not None or validation_id in self._native_swap_release_inflight:
            task = asyncio.create_task(
                self._answer_native_swap_release_refusal(
                    validation_id, binding, "busy"
                ),
                name="lane-managed-native-swap-release-inflight-" + validation_id,
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        self._native_swap_release_inflight.add(validation_id)
        task = asyncio.create_task(
            self._answer_native_swap_release(frame),
            name="lane-managed-native-swap-release-" + validation_id,
        )
        self._coordinator_interrupt_tasks.add(task)
        self._native_swap_release_tasks[validation_id] = task

        def finish(done: asyncio.Task[Any]) -> None:
            self._coordinator_interrupt_tasks.discard(done)
            self._native_swap_release_inflight.discard(validation_id)
            if self._native_swap_release_tasks.get(validation_id) is done:
                self._native_swap_release_tasks.pop(validation_id, None)

        task.add_done_callback(finish)

    async def _answer_native_swap_release_refusal(
        self,
        validation_id: str,
        binding: Mapping[str, Any],
        code: str,
    ) -> None:
        try:
            acknowledgement = _native_swap_refusal_ack(
                validation_id, binding, "refused-" + code
            )
            await _await_bounded(
                self.bridge.write({
                    "operation": "native-swap-release-authorize-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "validation_id": validation_id,
                    "ack": acknowledgement,
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "native-swap-release-authorize-ack",
                "validation_id": validation_id,
            })

    async def _answer_native_swap_release_duplicate(
        self,
        validation_id: str,
        binding: Mapping[str, Any],
        authorization_id: Any,
    ) -> None:
        """Return a false duplicate observation without invoking the binder."""

        if not isinstance(authorization_id, str) or not authorization_id:
            authorization_id = "refused-duplicate"
        try:
            acknowledgement = _native_swap_refusal_ack(
                validation_id, binding, authorization_id
            )
            await _await_bounded(
                self.bridge.write({
                    "operation": "native-swap-release-authorize-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "validation_id": validation_id,
                    "ack": acknowledgement,
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "native-swap-release-authorize-ack",
                "validation_id": validation_id,
            })

    async def _answer_native_swap_release(self, frame: Mapping[str, Any]) -> None:
        validation_id = frame.get("validation_id")
        binding = frame.get("binding")
        acknowledgement: dict[str, Any]
        try:
            validation_id = _wire_id(validation_id, "validation_id")
            binding = _native_swap_binding(binding)
        except SdkAdapterError:
            # The reader already validates this shape; retain a bounded refusal
            # if a future transport changes that ordering.
            return
        try:
            connection_error = self._native_swap_release_connection_error(binding)
            if connection_error is not None:
                raise connection_error
            if self.native_swap_release is None:
                raise SdkAdapterError(
                    "unsupported",
                    "native swap release authorization callback is not bound",
                )
            result = await _await_bounded(
                _maybe_await(
                    self.native_swap_release(
                        self.participant_id,
                        self.spec.session_id,
                        self.runner_instance_id,
                        validation_id,
                        copy.deepcopy(binding),
                    )
                ),
                self.operation_deadline,
            )
            acknowledgement = _native_swap_authorization(
                result,
                validation_id=validation_id,
                binding=binding,
            )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            acknowledgement = _native_swap_refusal_ack(
                validation_id, binding, "timeout"
            )
        except SdkAdapterError:
            acknowledgement = _native_swap_refusal_ack(
                validation_id, binding, "refused"
            )
        except Exception:
            acknowledgement = _native_swap_refusal_ack(
                validation_id, binding, "failed"
            )
        # The callback is an awaited private controller operation.  A runner
        # can therefore be closed, released, replaced, or become uncertain
        # while it is in flight.  Never publish a positive ACK from that old
        # connection; this recheck is intentionally immediately before the
        # result is cached and written to the authenticated bridge.
        if acknowledgement["authorized"] is True:
            connection_error = self._native_swap_release_connection_error(binding)
            if connection_error is not None:
                acknowledgement = _native_swap_refusal_ack(
                    validation_id,
                    binding,
                    "refused-" + connection_error.code,
                )
        if acknowledgement["authorized"] is True:
            self._native_swap_release_granted = True
        self._native_swap_release_results[validation_id] = copy.deepcopy(
            acknowledgement
        )
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "native-swap-release-authorize-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "validation_id": validation_id,
                    "ack": acknowledgement,
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "native-swap-release-authorize-ack",
                "validation_id": validation_id,
            })

    def _start_coordinator_interrupt_validate(self, event: Mapping[str, Any]) -> None:
        expected = {
            "type", "participant_id", "session_id", "runner_instance_id",
            "validation_id", "interrupt_id", "intent_digest",
        }
        if set(event) != expected or event.get("type") != "coordinator-interrupt-validate":
            raise SdkAdapterError("invalid", "coordinator interrupt validation is malformed")
        validation_id = _wire_id(event.get("validation_id"), "validation_id")
        interrupt_id = _wire_id(event.get("interrupt_id"), "interrupt_id")
        intent_digest = event.get("intent_digest")
        if not isinstance(intent_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", intent_digest):
            raise SdkAdapterError("invalid", "coordinator interrupt validation digest is malformed")
        frame = copy.deepcopy(dict(event))
        if len(self._coordinator_interrupt_tasks) >= MAX_NATIVE_CHILD_RECORDS:
            raise SdkAdapterError("busy", "too many pending coordinator interrupt transactions")
        previous = self._coordinator_interrupt_validate_frames.get(validation_id)
        if previous is not None and previous != frame:
            task = asyncio.create_task(
                self._answer_coordinator_interrupt_validate_refusal(
                    validation_id, interrupt_id, intent_digest, "stale-generation"
                ),
                name="lane-managed-coordinator-interrupt-validate-refusal-" + validation_id,
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        if previous is None and len(self._coordinator_interrupt_validate_ids) >= MAX_NATIVE_LIFECYCLE_EVENTS:
            raise SdkAdapterError("busy", "coordinator interrupt validation history is full")
        if previous is None:
            self._coordinator_interrupt_validate_ids.add(validation_id)
            self._coordinator_interrupt_validate_frames[validation_id] = frame
        inflight = self._coordinator_interrupt_validate_tasks.get(validation_id)
        if inflight is not None and inflight.done():
            self._coordinator_interrupt_validate_tasks.pop(validation_id, None)
            self._coordinator_interrupt_validate_inflight.discard(validation_id)
            inflight = None
        if inflight is not None or validation_id in self._coordinator_interrupt_validate_inflight:
            task = asyncio.create_task(
                self._answer_coordinator_interrupt_validate_refusal(
                    validation_id, interrupt_id, intent_digest, "busy"
                ),
                name="lane-managed-coordinator-interrupt-validate-inflight-" + validation_id,
            )
            self._coordinator_interrupt_tasks.add(task)
            task.add_done_callback(self._coordinator_interrupt_tasks.discard)
            return
        self._coordinator_interrupt_validate_inflight.add(validation_id)
        task = asyncio.create_task(
            self._answer_coordinator_interrupt_validate(frame),
            name="lane-managed-coordinator-interrupt-validate-" + validation_id,
        )
        self._coordinator_interrupt_tasks.add(task)
        self._coordinator_interrupt_validate_tasks[validation_id] = task

        def finish(done: asyncio.Task[Any]) -> None:
            self._coordinator_interrupt_tasks.discard(done)
            self._coordinator_interrupt_validate_inflight.discard(validation_id)
            if self._coordinator_interrupt_validate_tasks.get(validation_id) is done:
                self._coordinator_interrupt_validate_tasks.pop(validation_id, None)

        task.add_done_callback(finish)

    async def _answer_coordinator_interrupt_validate_refusal(
        self, validation_id: Any, interrupt_id: Any, intent_digest: Any, code: str
    ) -> None:
        try:
            validation_id = _wire_id(validation_id, "validation_id")
        except SdkAdapterError:
            validation_id = "invalid-validation-id"
        try:
            interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        except SdkAdapterError:
            interrupt_id = "invalid-interrupt-id"
        digest = intent_digest if isinstance(intent_digest, str) else "0" * 64
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "coordinator-interrupt-validate-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "validation_id": validation_id,
                    "interrupt_id": interrupt_id,
                    "ack": {
                        "validated": False,
                        "validation_id": validation_id,
                        "interrupt_id": interrupt_id,
                        "intent_digest": digest,
                        "code": code,
                    },
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "coordinator-interrupt-validate-ack",
                "validation_id": validation_id,
            })

    async def _answer_coordinator_interrupt_validate(self, frame: Mapping[str, Any]) -> None:
        validation_id = frame.get("validation_id")
        interrupt_id = frame.get("interrupt_id")
        intent_digest = frame.get("intent_digest")
        ack: dict[str, Any] = {
            "validated": False,
            "validation_id": validation_id,
            "interrupt_id": interrupt_id,
            "intent_digest": intent_digest,
        }
        try:
            self._validate_event_identity(frame)
            if not self.started or not self.ready:
                raise SdkAdapterError("unsupported", "coordinator interrupt validation requires an owned started runner")
            if self.coordinator_interrupt_validate is None:
                raise SdkAdapterError("unsupported", "coordinator interrupt validation callback is not bound")
            result = await _await_bounded(
                _maybe_await(self.coordinator_interrupt_validate(copy.deepcopy(dict(frame)))),
                self.operation_deadline,
            )
            # The authority callback may yield while the runner is being
            # retired.  A positive validation is useful only for the same
            # still-owned connection that made the request.
            if (
                self.closed
                or not self.started
                or not self.ready
                or not self.process_alive
            ):
                raise SdkAdapterError(
                    "stale-generation",
                    "coordinator interrupt validation connection changed while awaiting authority",
                )
            self._validate_event_identity(frame)
            if not _coordinator_interrupt_validation_ack_matches(
                result, validation_id, interrupt_id, intent_digest
            ):
                raise SdkAdapterError("invalid", "coordinator interrupt validation callback returned an invalid acknowledgement")
            ack = dict(result)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            ack["code"] = "loader-failed"
        except SdkAdapterError as exc:
            ack["code"] = exc.code
        except Exception as exc:
            exception_code = getattr(exc, "code", None)
            ack["code"] = (
                exception_code
                if isinstance(exception_code, str) and exception_code.strip()
                else "loader-failed"
            )
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "coordinator-interrupt-validate-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "validation_id": validation_id,
                    "interrupt_id": interrupt_id,
                    "ack": ack,
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "coordinator-interrupt-validate-ack",
                "validation_id": validation_id,
            })

    async def _answer_coordinator_interrupt_intent_refusal(
        self, interrupt_id: Any, code: str
    ) -> None:
        try:
            interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        except SdkAdapterError:
            interrupt_id = "invalid-interrupt-id"
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "coordinator-interrupt-intent-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "interrupt_id": interrupt_id,
                    "ack": {
                        "recorded": False,
                        "authorize_send": False,
                        "interrupt_id": interrupt_id,
                        "code": code,
                    },
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "coordinator-interrupt-intent-ack",
                "interrupt_id": interrupt_id,
            })

    async def _answer_coordinator_interrupt_evidence_refusal(
        self, evidence_id: Any, interrupt_id: Any, code: str
    ) -> None:
        try:
            evidence_id = _wire_id(evidence_id, "evidence_id")
        except SdkAdapterError:
            evidence_id = "invalid-evidence-id"
        try:
            interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        except SdkAdapterError:
            interrupt_id = "invalid-interrupt-id"
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "coordinator-interrupt-evidence-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "evidence_id": evidence_id,
                    "interrupt_id": interrupt_id,
                    "ack": {
                        "recorded": False,
                        "evidence_id": evidence_id,
                        "interrupt_id": interrupt_id,
                        "code": code,
                    },
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "coordinator-interrupt-evidence-ack",
                "evidence_id": evidence_id,
            })

    async def _answer_coordinator_interrupt_intent(
        self, frame: Mapping[str, Any]
    ) -> None:
        interrupt = frame.get("interrupt")
        interrupt_id = interrupt.get("interrupt_id") if isinstance(interrupt, Mapping) else None
        try:
            interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        except SdkAdapterError:
            interrupt_id = "invalid-interrupt-id"
        ack: dict[str, Any] = {
            "recorded": False,
            "authorize_send": False,
            "interrupt_id": interrupt_id,
        }
        try:
            self._validate_event_identity(frame)
            if not self.started or not self.ready:
                raise SdkAdapterError(
                    "unsupported",
                    "coordinator interrupt requires an owned started runner",
                )
            if (
                not isinstance(interrupt, Mapping)
                or interrupt.get("interrupt_id") != interrupt_id
            ):
                raise SdkAdapterError(
                    "invalid", "coordinator interrupt intent is malformed"
                )
            if self.coordinator_interrupt_intent is None:
                raise SdkAdapterError(
                    "unsupported",
                    "coordinator interrupt intent callback is not bound",
                )
            result = await _await_bounded(
                _maybe_await(
                    self.coordinator_interrupt_intent(copy.deepcopy(dict(frame)))
                ),
                self.operation_deadline,
            )
            if not _coordinator_interrupt_intent_ack_matches(result, interrupt_id):
                raise SdkAdapterError(
                    "invalid",
                    "coordinator interrupt intent callback returned an invalid acknowledgement",
                )
            if result["authorize_send"] and not result["recorded"]:
                raise SdkAdapterError(
                    "invalid",
                    "coordinator interrupt callback authorized an unrecorded intent",
                )
            ack = dict(result)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            ack["code"] = "loader-failed"
        except SdkAdapterError as exc:
            ack["code"] = exc.code
        except Exception:
            ack["code"] = "loader-failed"
        try:
            # This callback intentionally bypasses _control_lock.  The
            # coordinator's event/persistence reader must remain live while a
            # normal control operation waits for its own response.
            await _await_bounded(
                self.bridge.write({
                    "operation": "coordinator-interrupt-intent-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "interrupt_id": interrupt_id,
                    "ack": ack,
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "coordinator-interrupt-intent-ack",
                "interrupt_id": interrupt_id,
            })

    async def _answer_coordinator_interrupt_evidence(
        self, frame: Mapping[str, Any]
    ) -> None:
        evidence = frame.get("evidence")
        evidence_id = evidence.get("evidence_id") if isinstance(evidence, Mapping) else None
        interrupt_id = evidence.get("interrupt_id") if isinstance(evidence, Mapping) else None
        try:
            evidence_id = _wire_id(evidence_id, "evidence_id")
        except SdkAdapterError:
            evidence_id = "invalid-evidence-id"
        try:
            interrupt_id = _wire_id(interrupt_id, "interrupt_id")
        except SdkAdapterError:
            interrupt_id = "invalid-interrupt-id"
        ack: dict[str, Any] = {
            "recorded": False,
            "evidence_id": evidence_id,
            "interrupt_id": interrupt_id,
        }
        try:
            self._validate_event_identity(frame)
            if not self.started or not self.ready:
                raise SdkAdapterError(
                    "unsupported",
                    "coordinator interrupt evidence requires an owned started runner",
                )
            if (
                not isinstance(evidence, Mapping)
                or evidence.get("evidence_id") != evidence_id
                or evidence.get("interrupt_id") != interrupt_id
            ):
                raise SdkAdapterError(
                    "invalid", "coordinator interrupt evidence is malformed"
                )
            if self.coordinator_interrupt_evidence is None:
                raise SdkAdapterError(
                    "unsupported",
                    "coordinator interrupt evidence callback is not bound",
                )
            result = await _await_bounded(
                _maybe_await(
                    self.coordinator_interrupt_evidence(copy.deepcopy(dict(frame)))
                ),
                self.operation_deadline,
            )
            if not _coordinator_interrupt_evidence_ack_matches(
                result, evidence_id, interrupt_id
            ):
                raise SdkAdapterError(
                    "invalid",
                    "coordinator interrupt evidence callback returned an invalid acknowledgement",
                )
            ack = dict(result)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            ack["code"] = "loader-failed"
        except SdkAdapterError as exc:
            ack["code"] = exc.code
        except Exception:
            ack["code"] = "loader-failed"
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "coordinator-interrupt-evidence-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "evidence_id": evidence_id,
                    "interrupt_id": interrupt_id,
                    "ack": ack,
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({
                "operation": "coordinator-interrupt-evidence-ack",
                "evidence_id": evidence_id,
            })

    async def _answer_native_stop_intent_refusal(self, stop_id: Any, code: str) -> None:
        try:
            stop_id = _wire_id(stop_id, "stop_id")
        except SdkAdapterError:
            stop_id = "invalid-stop-id"
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "native-stop-intent-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "stop_id": stop_id,
                    "ack": {
                        "recorded": False,
                        "authorize_send": False,
                        "stop_id": stop_id,
                        "code": code,
                    },
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({"operation": "native-stop-intent-ack", "stop_id": stop_id})

    async def _answer_native_stop_evidence_refusal(
        self,
        evidence_id: Any,
        stop_id: Any,
        code: str,
    ) -> None:
        try:
            evidence_id = _wire_id(evidence_id, "evidence_id")
        except SdkAdapterError:
            evidence_id = "invalid-evidence-id"
        try:
            stop_id = _wire_id(stop_id, "stop_id")
        except SdkAdapterError:
            stop_id = "invalid-stop-id"
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "native-stop-evidence-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "evidence_id": evidence_id,
                    "stop_id": stop_id,
                    "ack": {
                        "recorded": False,
                        "evidence_id": evidence_id,
                        "stop_id": stop_id,
                        "code": code,
                    },
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({"operation": "native-stop-evidence-ack", "evidence_id": evidence_id})

    async def _answer_native_stop_intent(self, frame: Mapping[str, Any]) -> None:
        stop = frame.get("stop")
        stop_id = stop.get("stop_id") if isinstance(stop, Mapping) else None
        try:
            stop_id = _wire_id(stop_id, "stop_id")
        except SdkAdapterError:
            stop_id = "invalid-stop-id"
        ack: dict[str, Any] = {
            "recorded": False,
            "authorize_send": False,
            "stop_id": stop_id,
        }
        try:
            self._validate_event_identity(frame)
            if not self.started or not self.ready:
                raise SdkAdapterError("unsupported", "native stop requires an owned started runner")
            if not isinstance(stop, Mapping) or stop.get("stop_id") != stop_id:
                raise SdkAdapterError("invalid", "native stop intent is malformed")
            if self.native_stop_intent is None:
                raise SdkAdapterError("unsupported", "native stop intent callback is not bound")
            result = await _await_bounded(
                _maybe_await(self.native_stop_intent(copy.deepcopy(dict(frame)))),
                self.operation_deadline,
            )
            if not _native_stop_intent_ack_matches(result, stop_id):
                raise SdkAdapterError("invalid", "native stop intent callback returned an invalid acknowledgement")
            if result["authorize_send"] and not result["recorded"]:
                raise SdkAdapterError("invalid", "native stop callback authorized an unrecorded intent")
            ack = dict(result)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            ack["code"] = "loader-failed"
        except SdkAdapterError as exc:
            ack["code"] = exc.code
        except Exception:
            ack["code"] = "loader-failed"
        try:
            # This path intentionally bypasses _control_lock.  A native Agent
            # hook can be awaiting the controller while the normal control
            # waiter owns that lock.
            await _await_bounded(
                self.bridge.write({
                    "operation": "native-stop-intent-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "stop_id": stop_id,
                    "ack": ack,
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({"operation": "native-stop-intent-ack", "stop_id": stop_id})

    async def _answer_native_stop_evidence(self, frame: Mapping[str, Any]) -> None:
        evidence = frame.get("evidence")
        evidence_id = evidence.get("evidence_id") if isinstance(evidence, Mapping) else None
        stop_id = evidence.get("stop_id") if isinstance(evidence, Mapping) else None
        try:
            evidence_id = _wire_id(evidence_id, "evidence_id")
        except SdkAdapterError:
            evidence_id = "invalid-evidence-id"
        try:
            stop_id = _wire_id(stop_id, "stop_id")
        except SdkAdapterError:
            stop_id = "invalid-stop-id"
        ack: dict[str, Any] = {
            "recorded": False,
            "evidence_id": evidence_id,
            "stop_id": stop_id,
        }
        try:
            self._validate_event_identity(frame)
            if not self.started or not self.ready:
                raise SdkAdapterError("unsupported", "native stop evidence requires an owned started runner")
            if (
                not isinstance(evidence, Mapping)
                or evidence.get("evidence_id") != evidence_id
                or evidence.get("stop_id") != stop_id
            ):
                raise SdkAdapterError("invalid", "native stop evidence is malformed")
            if self.native_stop_evidence is None:
                raise SdkAdapterError("unsupported", "native stop evidence callback is not bound")
            result = await _await_bounded(
                _maybe_await(self.native_stop_evidence(copy.deepcopy(dict(frame)))),
                self.operation_deadline,
            )
            if not _native_stop_evidence_ack_matches(result, evidence_id, stop_id):
                raise SdkAdapterError("invalid", "native stop evidence callback returned an invalid acknowledgement")
            ack = dict(result)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            ack["code"] = "loader-failed"
        except SdkAdapterError as exc:
            ack["code"] = exc.code
        except Exception:
            ack["code"] = "loader-failed"
        try:
            await _await_bounded(
                self.bridge.write({
                    "operation": "native-stop-evidence-ack",
                    "participant_id": self.participant_id,
                    "session_id": self.spec.session_id,
                    "runner_instance_id": self.runner_instance_id,
                    "evidence_id": evidence_id,
                    "stop_id": stop_id,
                    "ack": ack,
                }),
                self.operation_deadline,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_uncertain({"operation": "native-stop-evidence-ack", "evidence_id": evidence_id})

    def _validate_event_identity(self, event: Mapping[str, Any]) -> None:
        participant = event.get("participant_id")
        session = event.get("session_id")
        generation = event.get("runner_instance_id")
        if participant is None or session is None or generation is None:
            raise SdkAdapterError(
                "invalid",
                "runner event is missing participant, session, or generation identity",
            )
        if str(participant) != self.participant_id:
            raise SdkAdapterError("ownership-conflict", "runner event belongs to another participant")
        if str(session) != str(self.spec.session_id):
            raise SdkAdapterError("stale-generation", "runner event has the wrong session UUID")
        if str(generation) != self.runner_instance_id:
            raise SdkAdapterError("stale-generation", "runner event has the wrong runner instance")

    def _observe_event(self, event: Mapping[str, Any]) -> None:
        self._validate_event_identity(event)
        mapping = dict(event)
        self.history.append(_redact_runner_event(mapping))
        kind = _event_type(mapping)
        if kind == "ready-held":
            self.ready = True
            self._participant_quiescent = True
            evidence = mapping.get("evidence")
            if isinstance(evidence, Mapping):
                initialization = evidence.get("initialization")
                if isinstance(initialization, Mapping):
                    self._ingest_initialization(initialization)
                else:
                    self._ingest_initialization(evidence)
                self._ingest_status(evidence)
        elif kind == "released":
            self.released = True
            boundary = mapping.get("native_swap_release_boundary")
            if boundary is not None:
                try:
                    self._native_swap_release_boundary = _native_swap_boundary(
                        boundary
                    )
                except SdkAdapterError:
                    self._record_uncertain({
                        "code": "stale-generation",
                        "message": "native swap release boundary receipt is malformed",
                    })
        elif kind == "interrupt-ack":
            self.interrupt_receipts += 1
        elif kind == "query-dispatched":
            self._turn_active = True
            self._turn_terminal = False
            self._turn_drained = False
            self._participant_quiescent = False
        elif kind == "shutdown-ack":
            self.shutdown_ack = mapping
            evidence = mapping.get("evidence")
            self._ingest_status(evidence if isinstance(evidence, Mapping) else mapping)
        elif kind == "status":
            self._ingest_status(mapping)
            # These fields are emitted by the persistent runner reader, not
            # supplied by a status caller.  Keep them separate from the
            # connection demux task's own EOF/error state: a live control
            # channel can observe a runtime reader that has already failed.
            reader_evidence = mapping.get("reader_evidence")
            if not isinstance(reader_evidence, Mapping):
                reader_evidence = mapping
            runtime_reader_done = reader_evidence.get("reader_done")
            if type(runtime_reader_done) is bool:
                self._runtime_reader_done = runtime_reader_done
            frame_inflight = reader_evidence.get("reader_frame_inflight")
            if type(frame_inflight) is bool:
                self._reader_frame_inflight = frame_inflight
            cursor = _first_nonempty(
                reader_evidence.get("reader_cursor"),
                reader_evidence.get("last_fully_processed_cursor"),
                reader_evidence.get("processed_through_watermark"),
            )
            if cursor is not None:
                if type(cursor) is not int or cursor <= 0:
                    self._record_uncertain({
                        "code": "invalid",
                        "message": "runner status supplied an invalid reader cursor",
                    })
                else:
                    self._last_fully_processed_cursor = cursor
            for attr, key in (
                ("_reader_hooks_inflight", "hooks_inflight"),
                ("_reader_stop_evidence_inflight", "stop_evidence_inflight"),
                ("_reader_coordinator_evidence_inflight", "coordinator_evidence_inflight"),
                (
                    "_reader_native_child_observation_inflight",
                    "native_child_observation_inflight",
                ),
            ):
                value = reader_evidence.get(key)
                if type(value) is int and value >= 0:
                    setattr(self, attr, value)
                    if key == "native_child_observation_inflight":
                        self._reader_native_child_observation_seen = True
                elif value is not None:
                    self._record_uncertain({
                        "code": "invalid",
                        "message": f"runner status supplied an invalid {key}",
                    })
                    if key == "native_child_observation_inflight":
                        self._reader_native_child_observation_seen = True
            child_observation_error = reader_evidence.get(
                "native_child_observation_error"
            )
            if type(child_observation_error) is bool:
                self._reader_native_child_observation_error = child_observation_error
                self._reader_native_child_observation_seen = True
            elif child_observation_error is not None:
                self._record_uncertain({
                    "code": "invalid",
                    "message": "runner status supplied an invalid native child observation error",
                })
                self._reader_native_child_observation_seen = True

        # Hook events, rather than AssistantMessage content, are authoritative
        # for tool starts/ends.  A missing or mismatched terminal hook leaves a
        # durable uncertainty that cannot be hidden by a later result message.
        phase = _event_value(mapping, "hook_event", "hook_event_name", "hookEventName")
        if phase or kind in {"descendant", "process", "effect", "external-effect", "external_effect"}:
            error = self._tools.observe(mapping)
            if error is not None:
                self._record_uncertain({"code": error.code, "message": error.message})

        data = _event_data(mapping)
        explicit_uncertain = _event_value(mapping, "uncertain", "uncertain_effect", "unknown_effect")
        if explicit_uncertain is True or str(explicit_uncertain).lower() in {"true", "1", "yes"}:
            self._record_uncertain({"type": kind, "detail": dict(data)})

        if kind in {
            "turn-start",
            "turn-started",
            "message-start",
            "assistant",
            "query-started",
        }:
            self._turn_active = True
            self._turn_terminal = False
            self._turn_drained = False
            self._participant_quiescent = False
        elif kind in {
            "turn-end",
            "turn-ended",
            "turn-complete",
            "message-stop",
            "response-complete",
            "result",
            "done",
            "idle",
            "drained",
            "quiesced",
        }:
            self._turn_active = False
            self._turn_terminal = True
            self._turn_drained = True
            self._participant_quiescent = True

        self._ingest_status(data)

    def _ingest_status(self, value: Mapping[str, Any]) -> None:
        ready = _get_ci(value, "ready")
        if ready is not None:
            self.ready = bool(ready)
        released = _get_ci(value, "released")
        if released is not None:
            self.released = bool(released)
        active = _get_ci(value, "active_turn", "activeTurn", "turn_active", "turnActive")
        if active is not None:
            self._turn_active = bool(active)
        terminal = _get_ci(value, "turn_terminal", "turnTerminal", "terminal")
        if terminal is not None:
            self._turn_terminal = bool(terminal)
        drained = _get_ci(value, "drained", "is_drained", "turn_drained", "turnDrained")
        if drained is not None:
            self._turn_drained = bool(drained)
        participant = _get_ci(value, "participant_quiescent", "participantQuiescent", "live_participant")
        if participant is not None:
            self._participant_quiescent = not bool(participant) if "live_participant" in value else bool(participant)
        tools = _get_ci(value, "tools_quiescent", "toolsQuiescent", "no_live_tools")
        if tools is False:
            self._participant_quiescent = False if self._participant_quiescent is True else self._participant_quiescent
        process = _get_ci(value, "process")
        if isinstance(process, Mapping) and process.get("process_group_owned") is False:
            self._record_uncertain({"code": "uncertain-effect", "message": "runner process group ownership is unproven"})
        if _get_ci(value, "quiescent") is False:
            self._participant_quiescent = False

    def _record_uncertain(self, item: Mapping[str, Any]) -> None:
        if len(self._uncertain) >= MAX_UNCERTAIN_TOOL_EVIDENCE:
            self._uncertain_overflow = True
            return
        self._uncertain.append(dict(item))

    def _ingest_initialization(self, value: Mapping[str, Any]) -> None:
        for key in ("account_email", "permission_mode", "model"):
            candidate = _get_ci(value, key)
            if candidate is not None:
                self._initialization[key] = candidate
        fingerprint = _get_ci(value, "fingerprint", "launch_fingerprint")
        if isinstance(fingerprint, Mapping):
            self._initialization["fingerprint"] = dict(fingerprint)

    async def _send(self, frame: Mapping[str, Any]) -> None:
        if self.closed:
            raise SdkAdapterError("busy", "runner connection is closed")
        if not self.process_alive:
            raise SdkAdapterError("loader-failed", "runner process is not alive")
        await self.bridge.write(frame)

    async def _wait_for_reply(
        self,
        request_id: str,
        expected_type: str,
        message_id: Optional[str] = None,
    ) -> dict[str, Any]:
        while True:
            item = await self.events.get()
            if isinstance(item, _RunnerReaderFailure):
                raise item.error
            if not isinstance(item, Mapping):
                raise SdkAdapterError("invalid", "runner emitted a non-object event")
            event = dict(item)
            kind = _event_type(event)
            event_request = event.get("request_id")
            event_message = event.get("message_id")
            error = _event_error(event)
            if error is not None:
                if event_request is not None and str(event_request) != request_id:
                    raise SdkAdapterError("stale-generation", "runner refusal has a different request ID")
                raise error
            if kind == expected_type:
                if event_request is None or str(event_request) != request_id:
                    raise SdkAdapterError("stale-generation", f"{expected_type} acknowledgement has the wrong request ID")
                if message_id is not None and (event_message is None or str(event_message) != message_id):
                    raise SdkAdapterError("stale-generation", "runner acknowledgement has the wrong message ID")
                return event
            # A control acknowledgement for another request must never be
            # allowed to satisfy this waiter, even if its operation/type is
            # otherwise the one being awaited.
            if kind in {
                "ready-held", "interrupt-ack", "released", "status", "query-dispatched",
                "shutdown-ack", "native-stop-ack", "coordinator-interrupt-ack",
                "prepare-invocation-ack",
            } and event_request is not None and str(event_request) != request_id:
                raise SdkAdapterError("stale-generation", "late runner acknowledgement cannot satisfy this request")

    async def request(
        self,
        operation: str,
        *,
        message_id: Optional[str] = None,
        payload_ref: Any = None,
        expected_type: str,
        deadline: Optional[float] = None,
        extra_fields: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        operation = _wire_id(operation, "operation")
        if message_id is not None:
            message_id = _wire_id(message_id, "message_id")
        request_id = str(_uuid.uuid4())
        if request_id in self.request_ids:
            raise SdkAdapterError("unknown", "runner request ID collision")
        self.request_ids.add(request_id)
        frame: dict[str, Any] = {
            "schema": 1,
            "operation": operation,
            "request_id": request_id,
            "participant_id": self.participant_id,
            "session_id": self.spec.session_id,
            "runner_instance_id": self.runner_instance_id,
        }
        # ``prepare-invocation`` has an explicit frozen frame type.  Preserve
        # the established operation-only shape for all other control calls.
        if operation == "prepare-invocation":
            frame["type"] = operation
        if message_id is not None:
            frame["message_id"] = message_id
        if payload_ref is not None:
            frame["payload_ref"] = payload_ref
        if extra_fields is not None:
            if not isinstance(extra_fields, Mapping):
                raise SdkAdapterError("invalid", "runner transport extension must be an object")
            for key, value in extra_fields.items():
                if key in frame or key in {"operation", "payload_ref"}:
                    raise SdkAdapterError("invalid", "runner transport extension collides with control fields")
                frame[str(key)] = copy.deepcopy(value)
        async def send_and_wait() -> dict[str, Any]:
            async with self._control_lock:
                self._request_inflight[request_id] = operation
                try:
                    await self._send(frame)
                    return await self._wait_for_reply(request_id, expected_type, message_id)
                finally:
                    self._request_inflight.pop(request_id, None)

        try:
            # The timeout wraps lock acquisition, nonblocking pipe write, and
            # acknowledgement wait as one current-task operation budget.
            return await _await_bounded(
                send_and_wait(),
                self.operation_deadline if deadline is None else deadline,
            )
        except asyncio.TimeoutError as exc:
            self._record_uncertain({"operation": operation, "request_id": request_id, "message_id": message_id})
            raise SdkAdapterError("loader-failed", f"{operation} operation deadline exceeded") from exc

    async def start(self, deadline: Optional[float] = None) -> dict[str, Any]:
        request_id = str(_uuid.uuid4())
        self.request_ids.add(request_id)
        frame = {
            "schema": 1,
            "operation": "start",
            "request_id": request_id,
            "participant_id": self.participant_id,
            "session_id": self.spec.session_id,
            "runner_instance_id": self.runner_instance_id,
            "spec": self.spec.to_dict(),
        }
        async def send_and_wait() -> dict[str, Any]:
            async with self._control_lock:
                await self._send(frame)
                return await self._wait_for_reply(request_id, "ready-held")

        try:
            event = await _await_bounded(
                send_and_wait(),
                self.startup_deadline if deadline is None else max(0.001, deadline),
            )
        except asyncio.TimeoutError as exc:
            raise SdkAdapterError("loader-failed", "runner startup deadline exceeded") from exc
        self.started = True
        self.ready = True
        if any(
            self._initialization.get(key) in (None, "")
            for key in ("account_email", "permission_mode", "model")
        ) or not isinstance(self._initialization.get("fingerprint"), Mapping):
            raise SdkAdapterError(
                "loader-failed",
                "ready-held runner omitted required account, permission, or model evidence",
            )
        if not self.quiescent:
            raise SdkAdapterError("uncertain-effect", "runner reached ready-held without quiescence evidence")
        return _public_runner_event(event)

    async def interrupt(self) -> dict[str, Any]:
        event = await self.request("interrupt", expected_type="interrupt-ack")
        # This is explicitly receipt evidence.  ``quiescent`` is the current
        # observed state, not an assertion that interrupt itself drained it.
        return {**_public_runner_event(event), "evidence": self.evidence(), "interrupt_receipt": True}

    async def coordinator_interrupt(self, selection: Mapping[str, Any]) -> dict[str, Any]:
        """Request one runner-owned, durably authorized coordinator interrupt."""

        expected = {
            "operation_id", "interrupt_id", "fence_epoch",
            "capability_digest", "request_epoch_id",
        }
        if not isinstance(selection, Mapping) or set(selection) != expected:
            raise SdkAdapterError("invalid", "coordinator interrupt selection is malformed")
        operation_id = _wire_id(selection.get("operation_id"), "operation_id")
        interrupt_id = _wire_id(selection.get("interrupt_id"), "interrupt_id")
        request_epoch_id = _wire_id(selection.get("request_epoch_id"), "request_epoch_id")
        fence_epoch = selection.get("fence_epoch")
        if type(fence_epoch) is not int or fence_epoch <= 0:
            raise SdkAdapterError("invalid", "coordinator interrupt fence_epoch is invalid")
        capability_digest = selection.get("capability_digest")
        if (
            not isinstance(capability_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", capability_digest)
        ):
            raise SdkAdapterError("invalid", "coordinator interrupt capability_digest is invalid")
        payload_ref = {
            "operation_id": operation_id,
            "interrupt_id": interrupt_id,
            "fence_epoch": fence_epoch,
            "capability_digest": capability_digest,
            "request_epoch_id": request_epoch_id,
        }
        event = await self.request(
            "coordinator-interrupt",
            payload_ref=payload_ref,
            expected_type="coordinator-interrupt-ack",
        )
        if event.get("interrupt_id") != interrupt_id:
            raise SdkAdapterError(
                "stale-generation",
                "coordinator interrupt acknowledgement changed its target",
            )
        return {
            **_public_runner_event(event),
            "interrupt_id": interrupt_id,
            "evidence": self.evidence(),
        }

    def _validate_native_swap_binding_for_connection(
            self, value: Any
    ) -> dict[str, Any]:
        binding = _native_swap_binding(value)
        if binding["participant_id"] != self.participant_id:
            raise SdkAdapterError(
                "ownership-conflict",
                "native swap release binding belongs to another participant",
            )
        if binding["session_id"] != self.spec.session_id:
            raise SdkAdapterError(
                "stale-generation",
                "native swap release binding has another session",
            )
        if binding["runner_incarnation"] != self.runner_instance_id:
            raise SdkAdapterError(
                "stale-generation",
                "native swap release binding has another runner incarnation",
            )
        fingerprint = self.spec.fingerprint
        context = fingerprint.get("lineage_context")
        if not isinstance(context, Mapping):
            context = fingerprint.get("lineage_claim")
        if not isinstance(context, Mapping):
            raise SdkAdapterError(
                "unsupported",
                "native swap release requires a bound lineage context",
            )
        expected_generation = context.get("owner_generation")
        expected_lineage = context.get("lineage_id")
        expected_runner = context.get("runner_incarnation")
        expected_lineage_generation = context.get("lineage_generation", 1)
        if (
            binding["owner_generation"] != expected_generation
            or binding["lineage_id"] != expected_lineage
            or binding["runner_incarnation"] != expected_runner
            or binding["lineage_generation"] != expected_lineage_generation
        ):
            raise SdkAdapterError(
                "stale-generation",
                "native swap release binding changed its lineage identity",
            )
        return binding

    def _native_swap_release_connection_error(
            self, binding: Mapping[str, Any]
    ) -> Optional[SdkAdapterError]:
        """Recheck the owned, held connection at a release-auth boundary.

        The private controller callback is awaited.  Every fact below is
        therefore checked both before that await and again immediately after
        it, so an old/closed/released runner cannot turn a late positive ACK
        into a gate.  This helper is observational only and never mutates the
        connection or grants the release.
        """

        try:
            self._validate_native_swap_binding_for_connection(binding)
        except SdkAdapterError as exc:
            return exc
        if not self.started or not self.ready or self.released:
            return SdkAdapterError(
                "stale-generation",
                "native swap release authorization requires the current held runner",
            )
        if self.closed or not self.process_alive:
            return SdkAdapterError(
                "stale-generation",
                "native swap release authorization runner is no longer owned",
            )
        if self.strict_process_group and not self.process_group_owned:
            return SdkAdapterError(
                "uncertain-effect",
                "native swap release authorization lost runner process ownership",
            )
        for key in ("account_email", "permission_mode", "model"):
            expected = getattr(self.spec, key, None)
            actual = self._initialization.get(key)
            if expected is not None and actual is not None and actual != expected:
                return SdkAdapterError(
                    "stale-generation",
                    "native swap release authorization startup identity changed",
                )
        observed_fingerprint = self._initialization.get("fingerprint")
        if (
            isinstance(observed_fingerprint, Mapping)
            and observed_fingerprint != self.spec.fingerprint
        ):
            return SdkAdapterError(
                "stale-generation",
                "native swap release authorization launch fingerprint changed",
            )
        if self._native_swap_release_granted:
            return SdkAdapterError(
                "uncertain-effect",
                "another native swap release authorization already granted the gate",
            )
        if self._reader_native_child_observation_error:
            return SdkAdapterError(
                "uncertain-effect",
                "native child observation persistence reported an error",
            )
        if self._reader_native_child_observation_inflight:
            return SdkAdapterError(
                "busy",
                "native child observation persistence is still in flight",
            )
        if not self.quiescent:
            return SdkAdapterError(
                "uncertain-effect",
                "native swap release authorization requires an actually quiescent held runner",
            )
        current_task = asyncio.current_task()
        pending_tasks = (
            set(self._admission_tasks)
            | set(self._stop_tasks)
            | set(self._coordinator_interrupt_tasks)
            | {
                task
                for task in self._native_child_observation_tasks.values()
                if not task.done()
            }
        )
        if any(task is not current_task and not task.done() for task in pending_tasks):
            return SdkAdapterError(
                "busy",
                "native swap release authorization has another runner control task in flight",
            )
        return None

    async def release(
        self, *, native_swap_binding: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        if not self.ready:
            raise SdkAdapterError("loader-failed", "release requires ready-held runner")
        if native_swap_binding is None and (
            self._native_swap_target_requires_bound_release
            or self._native_swap_release_attempted
        ):
            raise SdkAdapterError(
                "unsupported" if self._native_swap_target_requires_bound_release else "uncertain-effect",
                "native swap release requires its original bound authorization"
                if self._native_swap_target_requires_bound_release
                else "native swap release was already attempted; an unbound retry is forbidden",
            )
        if native_swap_binding is not None and self._native_swap_release_attempted:
            raise SdkAdapterError(
                "uncertain-effect",
                "native swap release was already attempted; retry is forbidden",
            )
        child_error = self._native_child_observation_connection_error()
        if child_error is not None:
            raise child_error
        if not self.quiescent:
            raise SdkAdapterError("uncertain-effect", "release requires participant and tool quiescence")
        binding = None
        if native_swap_binding is not None:
            # Treat every bound native command as an attempted one before
            # validating its content.  A stale/malformed binding must not be
            # repaired by falling back to the ordinary unbound release path.
            self._native_swap_release_attempted = True
            binding = self._validate_native_swap_binding_for_connection(
                native_swap_binding
            )
        event = await self.request(
            "release",
            payload_ref=binding,
            expected_type="released",
        )
        if binding is not None:
            receipt = event.get("native_swap_release_boundary")
            try:
                receipt = _native_swap_boundary(
                    receipt, expected_binding=binding
                )
            except SdkAdapterError as exc:
                # The runner may already have crossed its synchronous gate;
                # never retry or fall back to a legacy release call.
                self._record_uncertain({
                    "code": exc.code,
                    "message": exc.message,
                    "operation": "native-swap-release-boundary",
                })
                raise SdkAdapterError(
                    "uncertain-effect",
                    "native swap release boundary receipt is missing or changed",
                ) from exc
            self._native_swap_release_boundary = copy.deepcopy(receipt)
            self.released = True
            return {
                **_public_runner_event(event),
                "native_swap_release_boundary": copy.deepcopy(receipt),
                "evidence": self.evidence(),
            }
        self.released = True
        return {**_public_runner_event(event), "evidence": self.evidence()}

    async def prepare_invocation(
        self,
        request_binding: Mapping[str, Any],
        *,
        deadline: Optional[float] = None,
    ) -> dict[str, Any]:
        """Obtain one exact terminal-proof-backed runner reservation."""

        binding = _native_invocation_binding(request_binding)
        if self.closed or not self.process_alive:
            raise SdkAdapterError("stale-generation", "native reservation runner is no longer owned")
        if not self.ready or not self.released:
            raise SdkAdapterError("busy", "native reservation requires a released ready runner")
        if self._reservation is not None:
            existing_binding = {
                key: self._reservation[key] for key in _NATIVE_INVOCATION_BINDING_FIELDS
            }
            if existing_binding == binding:
                return self.reservation or copy.deepcopy(self._reservation)
            raise SdkAdapterError("busy", "a different native reservation is already outstanding")
        reservation_id = binding["reservation_id"]
        if (
            reservation_id not in self._reservation_transport_attempts
            and len(self._reservation_transport_attempts) >= MAX_NATIVE_LIFECYCLE_EVENTS
        ):
            raise SdkAdapterError(
                "busy", "native reservation transport history is full"
            )
        event = await self.request(
            "prepare-invocation",
            payload_ref=binding,
            expected_type="prepare-invocation-ack",
            deadline=deadline,
        )
        if event.get("type") not in {None, "prepare-invocation-ack"}:
            raise SdkAdapterError("invalid", "native reservation acknowledgement has the wrong type")
        for key, expected in (
            ("participant_id", self.participant_id),
            ("session_id", self.spec.session_id),
            ("runner_instance_id", self.runner_instance_id),
        ):
            if event.get(key) is not None and str(event.get(key)) != str(expected):
                raise SdkAdapterError("stale-generation", "native reservation acknowledgement changed runner identity")
        response = _native_invocation_response(event, binding)
        self._reservation_transport_attempts.setdefault(reservation_id, False)
        self._reservation = response
        return copy.deepcopy(response)

    def consume_invocation_reservation(
        self, reservation_binding: Mapping[str, Any]
    ) -> Optional[SdkAdapterError]:
        """Consume the exact cached response after controller binding ACK."""

        if self._reservation is None:
            return SdkAdapterError("stale-generation", "native reservation is not outstanding")
        cached = self._reservation
        request = {key: cached[key] for key in _NATIVE_INVOCATION_BINDING_FIELDS}
        try:
            supplied = _native_invocation_response(reservation_binding, request)
        except SdkAdapterError as exc:
            return exc
        if any(supplied.get(key) != cached.get(key) for key in _NATIVE_INVOCATION_RESPONSE_FIELDS):
            return SdkAdapterError("stale-generation", "native reservation binding does not match the cached response")
        self._next_send_reservation_binding = copy.deepcopy(supplied)
        self._reservation = None
        return None

    def _mark_reservation_transport_attempted(
        self, reservation: Mapping[str, Any]
    ) -> None:
        """Tombstone a B transport attempt before its first await/write."""

        reservation_id = _wire_id(
            reservation.get("reservation_id"), "reservation_id"
        )
        if reservation_id not in self._reservation_transport_attempts:
            if len(self._reservation_transport_attempts) >= MAX_NATIVE_LIFECYCLE_EVENTS:
                raise SdkAdapterError(
                    "busy", "native reservation transport history is full"
                )
            self._reservation_transport_attempts[reservation_id] = False
        self._reservation_transport_attempts[reservation_id] = True

    def _native_reservation_no_send_status_receipt(
        self, event: Mapping[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Build no-send evidence only from one fresh trusted status frame."""

        reservation = self._reservation
        if reservation is None or self._next_send_reservation_binding is not None:
            return None
        try:
            reservation = _native_invocation_response(
                reservation,
                _native_invocation_request_from_response(reservation),
            )
            reservation_id = _wire_id(
                reservation.get("reservation_id"), "reservation_id"
            )
        except SdkAdapterError:
            return None
        if self._reservation_transport_attempts.get(reservation_id) is not False:
            return None
        # A native runner that has the private child-observation channel must
        # report its strict reader counters before STATUS can certify that no
        # child ACK is pending.  Missing counters are unknown, never an
        # implicit zero.  Legacy/fake connections with no bound channel keep
        # the pre-existing status contract.
        if self.native_child_observation is not None and not self._reader_native_child_observation_seen:
            return None
        if (
            self._reader_native_child_observation_inflight != 0
            or self._reader_native_child_observation_error
        ):
            return None
        if (
            self.closed
            or not self.started
            or not self.ready
            or not self.released
            or not self.process_alive
            or self._reader_done
            or self._reader_error is not None
            or self._runtime_reader_done is not False
            or self._reader_frame_inflight
            or self._reader_hooks_inflight != 0
            or self._reader_stop_evidence_inflight != 0
            or self._reader_coordinator_evidence_inflight != 0
            or self._uncertain
            or self._uncertain_overflow
            or not self.participant_quiescent
            or not self.tools_quiescent
            or self._turn_active
            or not self._turn_terminal
            or not self._turn_drained
        ):
            return None
        current_task = asyncio.current_task()
        if any(
            task is not current_task and not task.done()
            for task in (
                set(self._admission_tasks)
                | set(self._stop_tasks)
                | set(self._coordinator_interrupt_tasks)
            )
        ):
            return None
        if self._request_inflight or self._control_lock.locked() or not self.events.empty():
            return None

        # Startup facts and status identity are independent of the caller's
        # recovery body.  A status frame from another owner/runner is rejected
        # by the reader, and an unobserved startup identity is insufficient for
        # a no-send claim.
        for key in ("account_email", "permission_mode", "model"):
            expected = getattr(self.spec, key, None)
            if expected is not None and self._initialization.get(key) != expected:
                return None
        observed_fingerprint = self._initialization.get("fingerprint")
        if not isinstance(observed_fingerprint, Mapping) or observed_fingerprint != self.spec.fingerprint:
            return None
        try:
            observation_id = _wire_id(
                event.get("request_id"), "native reservation observation_id"
            )
        except SdkAdapterError:
            return None
        reader_evidence = event.get("reader_evidence")
        if not isinstance(reader_evidence, Mapping):
            reader_evidence = event
        if self.native_child_observation is not None:
            # The two child-channel fields must come from this exact STATUS
            # response.  A previously observed zero cannot certify a later
            # response that omitted (or malformed) one of the fields.
            if (
                "native_child_observation_inflight" not in reader_evidence
                or "native_child_observation_error" not in reader_evidence
                or type(reader_evidence.get("native_child_observation_inflight")) is not int
                or isinstance(reader_evidence.get("native_child_observation_inflight"), bool)
                or reader_evidence.get("native_child_observation_inflight") < 0
                or type(reader_evidence.get("native_child_observation_error")) is not bool
                or reader_evidence.get("native_child_observation_inflight") != 0
                or reader_evidence.get("native_child_observation_error") is not False
            ):
                return None
        required_reader_fields = {
            "reader_done",
            "reader_frame_inflight",
            "hooks_inflight",
            "stop_evidence_inflight",
            "coordinator_evidence_inflight",
            "reader_error",
            "control_error",
            "task_failure",
        }
        if not required_reader_fields.issubset(reader_evidence):
            return None
        if (
            reader_evidence.get("reader_done") is not False
            or reader_evidence.get("reader_frame_inflight") is not False
            or reader_evidence.get("reader_error") is not False
            or reader_evidence.get("control_error") is not False
            or reader_evidence.get("task_failure") is not False
        ):
            return None
        for key in (
            "hooks_inflight",
            "stop_evidence_inflight",
            "coordinator_evidence_inflight",
        ):
            if type(reader_evidence.get(key)) is not int or reader_evidence[key] != 0:
                return None
        if any(
            event.get(key) is not expected
            for key, expected in (
                ("active_turn", False),
                ("turn_terminal", True),
                ("drained", True),
                ("participant_quiescent", True),
                ("tools_quiescent", True),
                ("quiescent", True),
            )
        ):
            return None
        cursor_keys = (
            "reader_cursor",
            "last_fully_processed_cursor",
            "processed_through_watermark",
        )
        if not any(key in reader_evidence for key in cursor_keys):
            return None
        observation_watermark = next(
            reader_evidence[key] for key in cursor_keys if key in reader_evidence
        )
        if (
            type(observation_watermark) is not int
            or observation_watermark <= 0
            or observation_watermark < reservation["terminal_watermark"]
        ):
            return None
        lineage = event.get("lineage")
        if not isinstance(lineage, Mapping):
            return None
        lineage_context = lineage.get("lineage_context")
        if not isinstance(lineage_context, Mapping):
            return None
        for key in ("owner_generation", "lineage_id", "runner_incarnation"):
            if lineage_context.get(key) != reservation.get(key):
                return None
        if lineage.get("current_invocation") != reservation["prior_invocation_id"]:
            return None
        status_reservation = lineage.get("native_invocation_reservation")
        if not isinstance(status_reservation, Mapping):
            return None
        try:
            status_reservation = _native_invocation_response(
                status_reservation,
                _native_invocation_request_from_response(reservation),
            )
        except SdkAdapterError:
            return None
        if status_reservation != reservation:
            return None
        if lineage.get("quiescent") is not True:
            return None
        parent_state = lineage.get("parent_state")
        if not isinstance(parent_state, Mapping):
            return None
        if parent_state.get("active") is not False or parent_state.get("drained") is not True:
            return None
        for key in ("pending_admissions", "pending_tasks"):
            pending = lineage.get(key)
            if not isinstance(pending, list) or pending:
                return None
        receipt = {
            "schema_version": 2,
            "architecture": "native-coordinator-lineage",
            "record_kind": "native-reservation-no-send",
            "observation_id": observation_id,
            "reservation_binding": copy.deepcopy(reservation),
            "reservation_digest": _native_full_digest(reservation),
            "observation_watermark": observation_watermark,
            "state": "reserved-unconsumed",
            "transport_attempted": False,
        }
        receipt["receipt_digest"] = _native_full_digest(receipt)
        try:
            return _native_reservation_no_send_receipt(
                receipt, reservation=reservation
            )
        except SdkAdapterError:
            return None

    async def send(self, message_id: str, payload_ref: Any) -> dict[str, Any]:
        message_id = _wire_id(message_id, "message_id")
        if message_id in self.sent_message_ids:
            raise SdkAdapterError("busy", f"message_id {message_id!r} was already dispatched")
        if not self.released:
            raise SdkAdapterError("busy", "send requires explicit release")
        pending_reservation = self._next_send_reservation_binding
        if pending_reservation is not None and (
            pending_reservation.get("next_invocation_id") != message_id
            or pending_reservation.get("next_mailbox_id") != message_id
        ):
            # Do this before reserving the mailbox ID so a caller cannot burn
            # a committed B proof by attempting to send C through the same
            # connection.
            raise SdkAdapterError(
                "stale-generation", "native reservation targets another mailbox"
            )
        # Reserve before writing.  If the pipe dies after the write, automatic
        # retry of the same mailbox ID would be an at-most-once violation.
        self.sent_message_ids.add(message_id)
        reservation_binding = pending_reservation
        # The reservation is consumed before writing the query.  If the
        # write/ack crosses a crash, the at-most-once mailbox marker above
        # prevents an automatic replay.
        self._next_send_reservation_binding = None
        try:
            event = await self.request(
                "query",
                message_id=message_id,
                payload_ref=payload_ref,
                expected_type="query-dispatched",
                extra_fields=(
                    {"reservation_binding": reservation_binding}
                    if reservation_binding is not None else None
                ),
            )
        except SdkAdapterError:
            self._record_uncertain({"operation": "query", "message_id": message_id})
            raise
        return {
            **_public_runner_event(event),
            "accepted": True,
            "ack_kind": "accepted-send",
            "message_id": message_id,
            "evidence": self.evidence(),
        }

    async def status(self) -> dict[str, Any]:
        event = await self.request("status", expected_type="status")
        no_send = self._native_reservation_no_send_status_receipt(event)
        evidence = self.evidence()
        evidence["native_reservation_no_send"] = no_send
        return {**_public_runner_event(event), "evidence": evidence}

    async def stop_task(self, task_id: str, *, stop_id: str) -> dict[str, Any]:
        task_id = _wire_id(task_id, "task_id")
        stop_id = _wire_id(stop_id, "stop_id")
        event = await self.request(
            "native-stop",
            payload_ref={"task_id": task_id, "stop_id": stop_id},
            expected_type="native-stop-ack",
        )
        if event.get("stop_id") != stop_id or event.get("task_id") != task_id:
            raise SdkAdapterError("stale-generation", "native stop acknowledgement changed its target")
        return {**_public_runner_event(event), "evidence": self.evidence()}

    async def wait_process_exit(self, deadline: float) -> None:
        async def poll_until_exit() -> None:
            while self.process_alive:
                await asyncio.sleep(0.01)

        try:
            await _await_bounded(poll_until_exit(), deadline)
        except asyncio.TimeoutError as exc:
            raise SdkAdapterError("loader-failed", "runner shutdown deadline exceeded") from exc

    async def shutdown(self) -> dict[str, Any]:
        operation_started = time.monotonic()
        event = await self.request(
            "shutdown",
            expected_type="shutdown-ack",
            deadline=self.operation_deadline,
        )
        remaining = self.operation_deadline - (time.monotonic() - operation_started)
        await self.wait_process_exit(max(0.001, remaining))
        if not self.quiescent:
            raise SdkAdapterError(
                "uncertain-effect",
                "runner shutdown did not prove active turn, tool, and participant quiescence",
            )
        pgid = self.process_group_id
        if pgid is not None and _process_group_alive(pgid):
            raise SdkAdapterError("uncertain-effect", "old runner process group remains alive")
        return {**_public_runner_event(event), "evidence": self.evidence()}

    async def close(self, *, force: bool = False) -> None:
        if self.closed:
            return
        self.closed = True
        if force and self.process_alive:
            pgid = self.process_group_id
            try:
                if pgid is not None and self.process_group_owned and os.name == "posix":
                    os.killpg(pgid, signal.SIGTERM)
                else:
                    terminate = getattr(self.process, "terminate", None)
                    if callable(terminate):
                        terminate()
            except OSError:
                pass
            try:
                await self.wait_process_exit(min(2.0, self.operation_deadline))
            except (SdkAdapterError, asyncio.CancelledError):
                # A process that ignored TERM is still never forgotten.  Kill
                # only the verified runner group; otherwise use the direct
                # process handle and retain uncertainty in the adapter.
                try:
                    if pgid is not None and self.process_group_owned and os.name == "posix":
                        os.killpg(pgid, signal.SIGKILL)
                    else:
                        kill = getattr(self.process, "kill", None)
                        if callable(kill):
                            kill()
                except OSError:
                    pass
                try:
                    await self.wait_process_exit(1.0)
                except (SdkAdapterError, asyncio.CancelledError):
                    pass
        for stream_name in ("stdin", "stdout", "stderr"):
            stream = getattr(self.process, stream_name, None)
            if stream is None:
                continue
            try:
                stream.close()
            except (OSError, ValueError):
                pass
        if self.reader_task is not None and not self.reader_task.done():
            self.reader_task.cancel()
            await asyncio.gather(self.reader_task, return_exceptions=True)
        if self.stderr_task is not None and not self.stderr_task.done():
            self.stderr_task.cancel()
            await asyncio.gather(self.stderr_task, return_exceptions=True)
        child_tasks = list(self._native_child_observation_tasks.values())
        for task in child_tasks:
            if not task.done():
                self._record_uncertain({
                    "operation": "native-child-observation",
                    "code": "uncertain-effect",
                    "message": "native child observation callback was cancelled at connection close",
                })
                task.cancel()
        if child_tasks:
            await asyncio.gather(*child_tasks, return_exceptions=True)


class SdkRunnerAdapter:
    """Supervisor-side registry for one dedicated runner per participant."""

    def __init__(
        self,
        runner_factory: Optional[Callable[[RunnerSpec], Any]] = None,
        *,
        strict_process_group: bool = True,
    ) -> None:
        self._runner_factory = popen_runner if runner_factory is None else runner_factory
        self._strict_process_group = bool(strict_process_group)
        self._connections: dict[str, _RunnerConnection] = {}
        self._opening: set[str] = set()
        # Failed/cancelled launches remain here until both the process and its
        # owned group are absent.  This is the in-memory projection of the
        # controller's durable pre-spawn launch intent; it prevents a retry
        # from racing an un-reaped old runner.
        self._failed_launches: dict[str, dict[str, Any]] = {}
        self._launch_intents: dict[str, dict[str, Any]] = {}
        self._runner_incarnations: set[str] = set()
        self._retired_groups: dict[tuple[int, int], dict[str, Any]] = {}
        self._registry_lock = asyncio.Lock()
        self._native_admission: Callable[[Mapping[str, Any]], Any] | None = None
        self._native_stop_intent: Callable[[Mapping[str, Any]], Any] | None = None
        self._native_stop_evidence: Callable[[Mapping[str, Any]], Any] | None = None
        self._coordinator_interrupt_intent: Callable[[Mapping[str, Any]], Any] | None = None
        self._coordinator_interrupt_evidence: Callable[[Mapping[str, Any]], Any] | None = None
        self._coordinator_interrupt_validate: Callable[[Mapping[str, Any]], Any] | None = None
        self._native_invocation: Callable[[Any, Any, Any, Any], Any] | None = None
        self._native_child_observation: Callable[[Mapping[str, Any]], Any] | None = None
        self._native_swap_release: Callable[..., Any] | None = None

    def bind_native_admission(self, callback: Callable[[Mapping[str, Any]], Any]) -> None:
        """Bind the controller recorder after construction and before open.

        The callback accepts one admission mapping and may be asynchronous.
        It must validate already registered durable context and return the
        strict acknowledgement tuple; binding itself grants no authority.
        """
        if not callable(callback):
            raise SdkAdapterError("invalid", "native admission callback must be callable")
        if self._opening or self._connections:
            raise SdkAdapterError("busy", "bind native admission before opening coordinator runners")
        self._native_admission = callback

    def bind_native_stop(
        self,
        intent_callback: Callable[[Mapping[str, Any]], Any],
        evidence_callback: Callable[[Mapping[str, Any]], Any],
    ) -> None:
        """Bind the controller's internal native-stop persistence callbacks."""

        if not callable(intent_callback) or not callable(evidence_callback):
            raise SdkAdapterError("invalid", "native stop callbacks must be callable")
        if self._opening or self._connections:
            raise SdkAdapterError("busy", "bind native stop before opening coordinator runners")
        self._native_stop_intent = intent_callback
        self._native_stop_evidence = evidence_callback

    def bind_native_child_observation(
        self, callback: Callable[[Mapping[str, Any]], Any]
    ) -> None:
        """Bind the private joined-child observation recorder before open.

        This callback is an authenticated persistence seam only.  It receives
        an SDK-produced observation frame and may return the exact bounded
        recorder ACK; it does not launch, resume, route, or grant a child.
        """

        if not callable(callback):
            raise SdkAdapterError(
                "invalid", "native child observation callback must be callable"
            )
        if self._opening or self._connections:
            raise SdkAdapterError(
                "busy",
                "bind native child observation before opening coordinator runners",
            )
        self._native_child_observation = callback

    def bind_coordinator_interrupt(
        self,
        intent_callback: Callable[[Mapping[str, Any]], Any],
        evidence_callback: Callable[[Mapping[str, Any]], Any],
        validation_callback: Callable[[Mapping[str, Any]], Any] | None = None,
    ) -> None:
        """Bind internal whole-roster interrupt persistence callbacks.

        This bridge only carries authenticated, bounded intent/evidence
        frames.  It does not dispatch an SDK interrupt and it never grants a
        public command or capability.
        """

        if not callable(intent_callback) or not callable(evidence_callback):
            raise SdkAdapterError(
                "invalid", "coordinator interrupt callbacks must be callable"
            )
        if self._opening or self._connections:
            raise SdkAdapterError(
                "busy",
                "bind coordinator interrupt before opening coordinator runners",
            )
        self._coordinator_interrupt_intent = intent_callback
        self._coordinator_interrupt_evidence = evidence_callback
        if validation_callback is not None:
            if not callable(validation_callback):
                raise SdkAdapterError(
                    "invalid", "coordinator interrupt validation callback must be callable"
                )
            self._coordinator_interrupt_validate = validation_callback

    def bind_coordinator_interrupt_validation(
        self, callback: Callable[[Mapping[str, Any]], Any]
    ) -> None:
        """Bind the controller's validate-only send authority callback."""

        if not callable(callback):
            raise SdkAdapterError(
                "invalid", "coordinator interrupt validation callback must be callable"
            )
        if self._opening or self._connections:
            raise SdkAdapterError(
                "busy",
                "bind coordinator interrupt validation before opening coordinator runners",
            )
        self._coordinator_interrupt_validate = callback

    def bind_native_invocation(
        self, callback: Callable[[Any, Any, Any, Any], Any]
    ) -> None:
        """Bind the durable actual-mailbox invocation preparation callback."""

        if not callable(callback):
            raise SdkAdapterError(
                "invalid", "native invocation callback must be callable"
            )
        if self._opening or self._connections:
            raise SdkAdapterError(
                "busy", "bind native invocation before opening coordinator runners"
            )
        self._native_invocation = callback

    def bind_native_swap_release(self, callback: Callable[..., Any]) -> None:
        """Bind the private controller authorization callback for native swap.

        The callback is never exposed through the public runner command.  It
        is invoked only by an authenticated owned runner connection with the
        exact participant/session/runner/validation/binding tuple.
        """

        if not callable(callback):
            raise SdkAdapterError(
                "invalid", "native swap release callback must be callable"
            )
        if self._opening or self._connections:
            raise SdkAdapterError(
                "busy", "bind native swap release before opening coordinator runners"
            )
        self._native_swap_release = callback

    def preflight_held_swap(
        self,
        spec: RunnerSpec | Mapping[str, Any],
        evidence_record: Any,
    ) -> CapabilityDecision:
        """Resolve and assess Gate 0 before the controller interrupts source."""

        return preflight_held_swap(spec, evidence_record)

    @staticmethod
    def _participant(value: Any) -> str:
        return _wire_id(value, "participant_id")

    def _prepare_spec(self, participant_id: str, spec: RunnerSpec | Mapping[str, Any]) -> RunnerSpec:
        runner_spec = _normalise_spec(spec)
        runner_spec = dataclasses.replace(runner_spec, fingerprint=copy.deepcopy(dict(runner_spec.fingerprint)))
        marker_error = _native_swap_target_marker_error(runner_spec)
        if marker_error is not None:
            raise SdkAdapterError("invalid", marker_error)
        if runner_spec.participant_id is not None and str(runner_spec.participant_id) != participant_id:
            raise SdkAdapterError("ownership-conflict", "runner specification belongs to another participant")
        if runner_spec.participant_id is None:
            runner_spec = dataclasses.replace(runner_spec, participant_id=participant_id)
        if not runner_spec.account_email:
            raise SdkAdapterError(
                "account-mismatch",
                "target profile must supply an expected account email",
            )
        _assert_spec_launchable(runner_spec)
        # Validate complete custom policies before creating a runner process.
        build_sdk_options(runner_spec)
        return runner_spec

    async def _ensure_no_old_group(self) -> None:
        stale: list[tuple[int, int]] = []
        for key, evidence in self._retired_groups.items():
            pid, pgid = key
            if _process_pid_alive(pid) or _process_group_alive(pgid):
                raise SdkAdapterError(
                    "uncertain-effect",
                    "an older participant runner process group is still alive",
                )
            stale.append(key)
        for key in stale:
            self._retired_groups.pop(key, None)

    @staticmethod
    async def _terminate_unbound(process: Any) -> bool:
        """Boundedly reap a process whose connection could not be built."""

        pid = getattr(process, "pid", None)
        pgid = None
        owned = False
        if isinstance(pid, int) and pid > 0 and os.name == "posix":
            try:
                pgid = os.getpgid(pid)
                sid = os.getsid(pid) if hasattr(os, "getsid") else None
                owned = pgid == pid and (sid is None or sid == pid)
            except OSError:
                pass
        try:
            if owned and isinstance(pgid, int):
                os.killpg(pgid, signal.SIGTERM)
            else:
                terminate = getattr(process, "terminate", None)
                if callable(terminate):
                    terminate()
        except OSError:
            pass
        deadline = time.monotonic() + 2.0
        poll = getattr(process, "poll", None)
        while callable(poll) and time.monotonic() < deadline:
            try:
                if poll() is not None:
                    return True
            except Exception:  # noqa: BLE001
                break
            await asyncio.sleep(0.01)
        try:
            if owned and isinstance(pgid, int) and _process_group_alive(pgid):
                os.killpg(pgid, signal.SIGKILL)
            else:
                kill = getattr(process, "kill", None)
                if callable(kill):
                    kill()
        except OSError:
            pass
        if callable(poll):
            try:
                return poll() is not None
            except Exception:  # noqa: BLE001
                return False
        return True

    async def open(self, participant_id: str, spec: RunnerSpec | Mapping[str, Any]) -> dict[str, Any]:
        participant_id = self._participant(participant_id)
        runner_spec = self._prepare_spec(participant_id, spec)
        context = runner_spec.fingerprint.get("lineage_context")
        claim = runner_spec.fingerprint.get("lineage_claim")
        native_launch = isinstance(context, Mapping) or isinstance(claim, Mapping)
        if not isinstance(context, Mapping) and not runner_spec.read_only:
            context = claim
        # A native-enabled launch uses the controller's pre-recorded process
        # incarnation. It is configuration, never a value from an intent.
        generation = (
            _wire_id(context.get("runner_incarnation"), "runner_incarnation")
            if isinstance(context, Mapping) else str(_uuid.uuid4())
        )
        async with self._registry_lock:
            if participant_id in self._connections or participant_id in self._opening:
                raise SdkAdapterError("busy", f"participant {participant_id!r} already has a runner")
            if generation in self._runner_incarnations:
                raise SdkAdapterError("stale-generation", "a replacement runner requires a new incarnation")
            failed = self._failed_launches.get(participant_id)
            if failed is not None:
                pid_alive = _process_pid_alive(failed.get("pid"))
                group_alive = _process_group_alive(failed.get("pgid"))
                if pid_alive or group_alive or (failed.get("pid") is None and failed.get("pgid") is None and failed.get("alive")):
                    raise SdkAdapterError(
                        "uncertain-effect",
                        f"participant {participant_id!r} has an unreconciled runner launch",
                    )
                self._failed_launches.pop(participant_id, None)
            self._runner_incarnations.add(generation)
            self._opening.add(participant_id)
            self._launch_intents[participant_id] = {
                "participant_id": participant_id,
                "session_id": runner_spec.session_id,
                "mode": runner_spec.mode,
                "state": "spawning",
                "started_at": time.time(),
            }
        process = None
        connection: Optional[_RunnerConnection] = None
        launch_started = time.monotonic()
        try:
            await self._ensure_no_old_group()
            process = self._runner_factory(runner_spec)
            if inspect.isawaitable(process):
                process = await process
            launch_remaining = runner_spec.startup_deadline - (time.monotonic() - launch_started)
            if launch_remaining <= 0:
                raise SdkAdapterError("loader-failed", "runner startup deadline exceeded")
            self._launch_intents[participant_id].update(
                {
                    "state": "started",
                    "runner_instance_id": generation,
                    "pid": getattr(process, "pid", None),
                }
            )
            connection = _RunnerConnection(
                participant_id,
                runner_spec,
                process,
                generation,
                strict_process_group=self._strict_process_group,
                native_admission=self._native_admission,
                native_stop_intent=self._native_stop_intent,
                native_stop_evidence=self._native_stop_evidence,
                coordinator_interrupt_intent=self._coordinator_interrupt_intent,
                coordinator_interrupt_evidence=self._coordinator_interrupt_evidence,
                coordinator_interrupt_validate=self._coordinator_interrupt_validate,
                native_child_observation=self._native_child_observation,
                native_swap_release=self._native_swap_release,
            )
            connection.start_reader()
            ready = await connection.start(deadline=launch_remaining)
            async with self._registry_lock:
                self._connections[participant_id] = connection
                self._opening.discard(participant_id)
            return {
                **ready,
                "ok": True,
                "participant_id": participant_id,
                "session_id": runner_spec.session_id,
                    "runner_instance_id": generation,
                "evidence": connection.evidence(),
            }
        except BaseException:
            if connection is not None:
                try:
                    await asyncio.shield(connection.close(force=True))
                except BaseException:
                    pass
                if connection.process_alive or _process_group_alive(connection.process_group_id):
                    self._failed_launches[participant_id] = {
                        "pid": connection._group_evidence.get("pid"),
                        "pgid": connection.process_group_id,
                        "alive": True,
                        "runner_instance_id": generation,
                    }
            elif process is not None:
                try:
                    reaped = await asyncio.shield(self._terminate_unbound(process))
                except BaseException:
                    reaped = False
                if not reaped:
                    pid = getattr(process, "pid", None)
                    pgid = None
                    if isinstance(pid, int) and os.name == "posix":
                        try:
                            pgid = os.getpgid(pid)
                        except OSError:
                            pass
                    self._failed_launches[participant_id] = {
                        "pid": pid,
                        "pgid": pgid,
                        "alive": True,
                        "runner_instance_id": generation,
                    }
            async with self._registry_lock:
                self._opening.discard(participant_id)
                intent = self._launch_intents.get(participant_id)
                if intent is not None:
                    intent["state"] = "failed"
            raise

    async def _connection(self, participant_id: str) -> _RunnerConnection:
        participant_id = self._participant(participant_id)
        async with self._registry_lock:
            connection = self._connections.get(participant_id)
        if connection is None:
            raise SdkAdapterError("unknown", f"participant {participant_id!r} has no runner")
        return connection

    async def interrupt(self, participant_id: str) -> dict[str, Any]:
        connection = await self._connection(participant_id)
        return await connection.interrupt()

    async def coordinator_interrupt(
        self, participant_id: str, selection: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Drive the runner-owned durable coordinator interrupt transaction."""

        connection = await self._connection(participant_id)
        return await connection.coordinator_interrupt(selection)

    async def release(
        self,
        participant_id: str,
        *,
        native_swap_binding: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        connection = await self._connection(participant_id)
        return await connection.release(native_swap_binding=native_swap_binding)

    async def prepare_invocation(
        self,
        participant_id: str,
        request: Mapping[str, Any],
        *,
        deadline: Optional[float] = None,
    ) -> dict[str, Any]:
        """Reserve a terminal same-runner invocation transition."""

        connection = await self._connection(participant_id)
        binding = _native_invocation_binding(request)
        if binding["participant_id"] != connection.participant_id:
            raise SdkAdapterError("ownership-conflict", "native reservation participant differs from connection")
        if binding["session_id"] != connection.spec.session_id:
            raise SdkAdapterError("stale-generation", "native reservation session differs from connection")
        if binding["runner_incarnation"] != connection.runner_instance_id:
            raise SdkAdapterError("stale-generation", "native reservation runner differs from connection")
        return await connection.prepare_invocation(binding, deadline=deadline)

    async def send(self, participant_id: str, message_id: str, payload_ref: Any) -> dict[str, Any]:
        connection = await self._connection(participant_id)
        message_id = _wire_id(message_id, "message_id")
        if message_id in connection.sent_message_ids:
            raise SdkAdapterError("busy", f"message_id {message_id!r} was already dispatched")
        if not connection.released:
            raise SdkAdapterError("busy", "send requires explicit release")
        fingerprint = connection.spec.fingerprint
        context = fingerprint.get("lineage_context")
        claim = fingerprint.get("lineage_claim")
        native_launch = isinstance(context, Mapping) or isinstance(claim, Mapping)
        if native_launch:
            # Mark before even checking the private binder capability.  A
            # caller that attempted this committed B can never later turn a
            # missing capability into a fresh no-send claim on the same
            # reservation.
            cached_reservation = connection.reservation
            if cached_reservation is not None:
                connection._mark_reservation_transport_attempted(cached_reservation)
            callback = self._native_invocation
            if callback is None:
                raise SdkAdapterError(
                    "unsupported",
                    "native query requires the durable invocation binder",
                )
            if connection.closed or not connection.process_alive:
                raise SdkAdapterError(
                    "stale-generation", "native query connection is no longer owned"
                )
            # The controller binding callback is itself a B-side control
            # await.  The marker above therefore precedes it; a timeout,
            # refusal, cancellation, or lost result leaves no-send status
            # evidence unavailable forever for this ID.
            try:
                acknowledgement = await _await_bounded(
                    _maybe_await(
                        callback(
                            connection.participant_id,
                            connection.spec.session_id,
                            connection.runner_instance_id,
                            message_id,
                        )
                    ),
                    connection.operation_deadline,
                )
            except asyncio.TimeoutError as exc:
                raise SdkAdapterError(
                    "loader-failed", "native invocation binding deadline exceeded"
                ) from exc
            if (
                connection.closed
                or not connection.process_alive
                or not isinstance(acknowledgement, Mapping)
                or acknowledgement.get("bound") is not True
                or acknowledgement.get("participant_id") != connection.participant_id
                or acknowledgement.get("session_id") != connection.spec.session_id
                or acknowledgement.get("runner_instance_id") != connection.runner_instance_id
                or acknowledgement.get("message_id") != message_id
            ):
                raise SdkAdapterError(
                    "stale-generation",
                    "native invocation binding changed before query dispatch",
                )
            reservation = cached_reservation
            reservation_binding = acknowledgement.get("reservation_binding")
            if reservation is not None:
                if not isinstance(reservation_binding, Mapping):
                    raise SdkAdapterError(
                        "stale-generation",
                        "controller did not prove the committed native reservation",
                    )
                if (
                    reservation_binding.get("next_mailbox_id") != message_id
                    or reservation_binding.get("next_invocation_id") != message_id
                ):
                    raise SdkAdapterError(
                        "stale-generation",
                        "native reservation binding targets another mailbox",
                    )
                consume_error = connection.consume_invocation_reservation(reservation_binding)
                if consume_error is not None:
                    raise consume_error
            else:
                if reservation_binding is not None:
                    raise SdkAdapterError(
                        "stale-generation",
                        "controller supplied a native reservation with no cached preparation",
                    )
                # The first A send is already represented by the durable
                # mailbox set.  ``_native_send_started`` is intentionally the
                # replacement/B crossing marker, not a substitute for that
                # set: a pending child observation during A must not make the
                # connection look as if an unauthorized B was issued, while a
                # later unreserved replacement still refuses before writing.
                if connection.native_send_started or connection.sent_message_ids:
                    raise SdkAdapterError(
                        "busy",
                        "native replacement invocation requires an exact terminal reservation",
                    )
            if reservation is not None:
                # Mark before the transport write: an ambiguous B crossing
                # cannot be retried as either a replacement or a generic send.
                connection._native_send_started = True
        return await connection.send(message_id, payload_ref)

    async def status(self, participant_id: str) -> dict[str, Any]:
        connection = await self._connection(participant_id)
        return await connection.status()

    async def stop_task(self, participant_id: str, task_id: str, *, stop_id: str) -> dict[str, Any]:
        connection = await self._connection(participant_id)
        return await connection.stop_task(task_id, stop_id=stop_id)

    async def shutdown(self, participant_id: str) -> dict[str, Any]:
        participant_id = self._participant(participant_id)
        connection = await self._connection(participant_id)
        try:
            result = await connection.shutdown()
        except SdkAdapterError:
            # Keep the registry entry on every uncertain/partial shutdown.  A
            # later open must not create a second writer over an old group.
            raise
        async with self._registry_lock:
            self._connections.pop(participant_id, None)
        pid = connection._group_evidence.get("pid")
        pgid = connection.process_group_id
        if isinstance(pid, int) and isinstance(pgid, int):
            self._retired_groups[(pid, pgid)] = connection.evidence()
        await connection.close()
        return {**result, "participant_id": participant_id}


# Names used by early supervisor experiments; aliases keep the process boundary
# explicit without introducing another implementation.
spawn_runner = popen_runner
start_runner = popen_runner


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="managed optional Claude SDK runner")
    parser.add_argument("--runner", action="store_true", help="run the bounded JSON-lines participant process")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    if not args.runner:
        print("lane_managed_sdk: use --runner for the dedicated SDK process", file=sys.stderr)
        return 2
    return _runner_main()


if __name__ == "__main__":  # pragma: no cover - exercised by process tests
    raise SystemExit(main())
