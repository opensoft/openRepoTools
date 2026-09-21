"""Pure validation for native coordinator child observations.

The runtime, controller, and durable store each own a different part of the
native-lineage boundary.  This module deliberately owns none of those parts:
it validates detached records, computes the contract digests, and resolves a
causal parent observation from records supplied by its caller.

There is no I/O in this module and, in particular, no import of the SDK,
controller, daemon, or state store.  A caller still has to validate transport
identity, owner/daemon authority, and the durable wrapper around an
observation before using these helpers.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from typing import Any


MAX_CANONICAL_BYTES = 1024 * 1024
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 65_536
MAX_ID_LENGTH = 256
MAX_INVENTORY = 256
MAX_RUNS = 256
MAX_OBSERVATIONS_PER_RUN = 16

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_NATIVE_ARCHITECTURE = "native-coordinator-lineage"
_OBSERVATION_KIND = "native-child-observation"
_OUTCOMES = frozenset({"completed", "stopped", "failed", "cancelled", "unknown"})

_SOURCE_FIELDS = frozenset(
    {
        "owner_generation",
        "lineage_id",
        "lineage_generation",
        "session_uuid",
        "runner_incarnation",
        "invocation_id",
    }
)
_TASK_START_FIELDS = frozenset({"event_uuid", "watermark", "task_type"})
_CHILD_FIELDS = frozenset(
    {
        "admission_id",
        "tool_use_id",
        "agent_id",
        "task_id",
        "parent_agent_id",
        "invocation_id",
        "lineage_incarnation",
        "trusted_definition_digest",
        "start_watermark",
        "task_start_event",
        "status",
        "terminal_watermark",
        "active_tool_ids",
        "uncertain_tool_ids",
        "unresolved_effect_ids",
    }
)
_OBSERVATION_FIELDS = frozenset(
    {
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
    }
)
_ADMISSION_FIELDS = frozenset(
    {
        "admission_id",
        "tool_use_id",
        "agent_type",
        "invocation_id",
        "parent",
        "custom_definition",
        "definition_digest",
        "trusted_definition_digest",
        "watermark",
        "owner_generation",
        "lineage_id",
        "runner_incarnation",
        "launch_completed",
    }
)
_PARENT_FIELDS = frozenset({"session_id", "invocation_id", "agent_id", "prompt_id"})
_PARENT_REQUIRED_FIELDS = frozenset({"session_id", "invocation_id"})
_BINDING_FIELDS = frozenset({"child_run_id", "observation_id", "observation_digest"})


class NativeChildContractError(ValueError):
    """Structured refusal raised by the pure native-child validators."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(self.message)

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _fail(code: str, message: str) -> None:
    raise NativeChildContractError(code, message)


def _normalize_json(value: Any, *, depth: int = 0, state: list[int] | None = None,
                    ancestors: set[int] | None = None) -> Any:
    """Copy strict JSON while rejecting cycles, aliases with odd types, and bounds."""

    if state is None:
        state = [0]
    if ancestors is None:
        ancestors = set()
    state[0] += 1
    if depth > MAX_JSON_DEPTH or state[0] > MAX_JSON_NODES:
        _fail("invalid", "native child JSON exceeds structural bounds")

    kind = type(value)
    if value is None or kind is bool or kind is int or kind is str:
        return value
    if kind is float:
        if not math.isfinite(value):
            _fail("invalid", "native child JSON contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        marker = id(value)
        if marker in ancestors:
            _fail("invalid", "native child JSON contains a cycle")
        ancestors.add(marker)
        try:
            result: dict[str, Any] = {}
            for key, item in value.items():
                if type(key) is not str:
                    _fail("invalid", "native child JSON object keys must be strings")
                result[key] = _normalize_json(
                    item, depth=depth + 1, state=state, ancestors=ancestors
                )
            return result
        finally:
            ancestors.remove(marker)
    if kind is list:
        marker = id(value)
        if marker in ancestors:
            _fail("invalid", "native child JSON contains a cycle")
        ancestors.add(marker)
        try:
            return [
                _normalize_json(item, depth=depth + 1, state=state, ancestors=ancestors)
                for item in value
            ]
        finally:
            ancestors.remove(marker)
    _fail("invalid", "native child value is not strict JSON")


def _canonical_json(value: Any, *, limit: int = MAX_CANONICAL_BYTES) -> str:
    normalized = _normalize_json(value)
    try:
        encoded = json.dumps(
            normalized,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise NativeChildContractError("invalid", "native child value is not canonical JSON") from exc
    if limit is not None and len(encoded) > limit:
        _fail("invalid", "native child canonical record exceeds capacity")
    return encoded.decode("ascii")


def canonical_digest(value: Any) -> str:
    """Return the bounded canonical SHA-256 used by the native lineage contract."""

    return hashlib.sha256(_canonical_json(value).encode("ascii")).hexdigest()


def _exact_mapping(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("invalid", "%s must be an object" % label)
    if set(value) != set(fields):
        _fail("invalid", "%s has unknown or missing fields" % label)
    normalized = _normalize_json(dict(value))
    if not isinstance(normalized, dict):  # pragma: no cover - guarded above
        _fail("invalid", "%s must be an object" % label)
    return normalized


def _mapping_with_optional(
    value: Any, required: frozenset[str], optional: frozenset[str], label: str
) -> dict[str, Any]:
    """Copy a closed mapping whose optional fields retain their absence."""

    if not isinstance(value, Mapping):
        _fail("invalid", "%s must be an object" % label)
    keys = set(value)
    if not required.issubset(keys) or keys - required - optional:
        _fail("invalid", "%s has unknown or missing fields" % label)
    normalized = _normalize_json(dict(value))
    if not isinstance(normalized, dict):  # pragma: no cover
        _fail("invalid", "%s must be an object" % label)
    return normalized


def _id(value: Any, label: str) -> str:
    if type(value) is not str or not value or len(value) > MAX_ID_LENGTH:
        _fail("invalid", "%s must be a bounded non-empty string" % label)
    if "\x00" in value or value != value.strip():
        _fail("invalid", "%s has invalid whitespace or NUL" % label)
    return value


def _optional_id(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _id(value, label)


def _positive(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        _fail("invalid", "%s must be a positive integer" % label)
    return value


def _digest(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail("invalid", "%s must be a lowercase SHA-256 digest" % label)
    return value


def _reject_definition_identity(value: Any, label: str) -> None:
    """Reject fields that would smuggle runtime identity into a policy body."""

    if not isinstance(value, Mapping):
        return
    forbidden = {
        "session_id", "session_uuid", "runner_instance_id", "process_group_id",
        "mailbox_id", "pid", "agent_id", "task_id", "tool_use_id", "invocation_id",
        "owner_generation", "lineage_id", "runner_incarnation", "claim", "claim_ref",
        "fence", "accepted", "ack", "evidence", "runtime", "process", "runner",
        "mailbox",
    }
    for key, item in value.items():
        if type(key) is not str:
            _fail("invalid", "%s contains a non-string key" % label)
        if key.casefold() in forbidden:
            _fail("invalid", "%s contains runtime identity" % label)
        if isinstance(item, Mapping):
            _reject_definition_identity(item, label)
        elif type(item) is list:
            for nested in item:
                if isinstance(nested, Mapping):
                    _reject_definition_identity(nested, label)


def _validate_source(value: Any, label: str = "native child source_identity") -> dict[str, Any]:
    source = _exact_mapping(value, _SOURCE_FIELDS, label)
    source["owner_generation"] = _positive(source["owner_generation"], label + " owner_generation")
    source["lineage_generation"] = _positive(
        source["lineage_generation"], label + " lineage_generation"
    )
    for key in ("lineage_id", "session_uuid", "runner_incarnation", "invocation_id"):
        source[key] = _id(source[key], label + " " + key)
    return source


def _validate_task_start(value: Any, label: str) -> dict[str, Any]:
    task = _exact_mapping(value, _TASK_START_FIELDS, label)
    task["event_uuid"] = _optional_id(task["event_uuid"], label + " event_uuid")
    task["watermark"] = _positive(task["watermark"], label + " watermark")
    task["task_type"] = _id(task["task_type"], label + " task_type")
    return task


def _validate_id_list(value: Any, label: str) -> list[str]:
    if type(value) is not list or len(value) > MAX_INVENTORY:
        _fail("invalid", "%s must be a bounded list" % label)
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        item = _id(item, label + " item")
        if item in seen:
            _fail("uncertain-effect", "%s repeats an ID" % label)
        seen.add(item)
        result.append(item)
    return result


def _validate_child(value: Any, label: str = "native child observation child") -> dict[str, Any]:
    child = _exact_mapping(value, _CHILD_FIELDS, label)
    for key in ("admission_id", "tool_use_id", "agent_id", "task_id", "invocation_id"):
        child[key] = _id(child[key], label + " " + key)
    child["parent_agent_id"] = _optional_id(child["parent_agent_id"], label + " parent_agent_id")
    child["lineage_incarnation"] = _positive(
        child["lineage_incarnation"], label + " lineage_incarnation"
    )
    child["trusted_definition_digest"] = _digest(
        child["trusted_definition_digest"], label + " trusted_definition_digest"
    )
    child["start_watermark"] = _positive(child["start_watermark"], label + " start_watermark")
    child["task_start_event"] = _validate_task_start(
        child["task_start_event"], label + " task_start_event"
    )
    if type(child["status"]) is not str or child["status"] not in {"active", "completed", "stopped"}:
        _fail("invalid", "%s status is unsupported" % label)
    terminal = child["terminal_watermark"]
    if child["status"] == "active":
        if terminal is not None:
            _fail("invalid", "%s active child has terminal watermark" % label)
    else:
        terminal = _positive(terminal, label + " terminal_watermark")
        if terminal <= child["start_watermark"]:
            _fail("stale-generation", "%s terminal watermark is not after start" % label)
        if terminal < child["task_start_event"]["watermark"]:
            _fail("stale-generation", "%s terminal watermark predates task start" % label)
        child["terminal_watermark"] = terminal
    child["active_tool_ids"] = _validate_id_list(child["active_tool_ids"], label + " active_tool_ids")
    child["uncertain_tool_ids"] = _validate_id_list(
        child["uncertain_tool_ids"], label + " uncertain_tool_ids"
    )
    child["unresolved_effect_ids"] = _validate_id_list(
        child["unresolved_effect_ids"], label + " unresolved_effect_ids"
    )
    if set(child["active_tool_ids"]) & set(child["uncertain_tool_ids"]):
        _fail("uncertain-effect", "%s tool inventories overlap" % label)
    return child


def _validate_observation_shape(value: Any) -> dict[str, Any]:
    observation = _exact_mapping(value, _OBSERVATION_FIELDS, "native child observation")
    if type(observation["schema_version"]) is not int or observation["schema_version"] != 2:
        _fail("invalid", "native child observation schema_version is unsupported")
    if observation["architecture"] != _NATIVE_ARCHITECTURE:
        _fail("invalid", "native child observation architecture is unsupported")
    if observation["record_kind"] != _OBSERVATION_KIND:
        _fail("invalid", "native child observation record_kind is unsupported")
    observation["observation_id"] = _id(
        observation["observation_id"], "native child observation_id"
    )
    observation["source_identity"] = _validate_source(observation["source_identity"])
    observation["context_binding_digest"] = _digest(
        observation["context_binding_digest"], "native child context_binding_digest"
    )
    observation["claim_digest"] = _digest(
        observation["claim_digest"], "native child claim_digest"
    )
    observation["observation_watermark"] = _positive(
        observation["observation_watermark"], "native child observation watermark"
    )
    outcome = observation["terminal_outcome"]
    if outcome is not None:
        outcome = _id(outcome, "native child terminal outcome")
        if outcome not in _OUTCOMES:
            _fail("invalid", "native child terminal outcome is unsupported")
    observation["terminal_outcome"] = outcome
    observation["child"] = _validate_child(observation["child"])
    child = observation["child"]
    watermark = observation["observation_watermark"]
    if child["start_watermark"] >= watermark:
        _fail("stale-generation", "native child observation watermark is stale")
    if child["task_start_event"]["watermark"] > watermark:
        _fail("stale-generation", "native child task start exceeds observation")
    if child["status"] == "active":
        if outcome is not None:
            _fail("invalid", "active native child has a terminal outcome")
    else:
        if child["terminal_watermark"] > watermark:
            _fail("stale-generation", "native child terminal exceeds observation")
        if outcome is None:
            _fail("invalid", "terminal native child has no outcome")
        if child["status"] == "completed" and outcome != "completed":
            _fail("stale-generation", "completed native child has a different outcome")
        if child["status"] == "stopped" and outcome == "completed":
            _fail("stale-generation", "stopped native child cannot report completion")
    return observation


def _context_parts(context: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(context, Mapping):
        _fail("invalid", "native admission context must be an object")
    normalized = _normalize_json(dict(context))
    if not isinstance(normalized, dict):  # pragma: no cover
        _fail("invalid", "native admission context must be an object")
    lineage = normalized.get("lineage")
    if not isinstance(lineage, Mapping):
        _fail("invalid", "native admission context lineage is missing")
    lineage = dict(lineage)
    for key in ("owner_generation", "lineage_generation"):
        _positive(lineage.get(key), "native context lineage " + key)
    for key in ("lineage_id", "session_uuid"):
        _id(lineage.get(key), "native context lineage " + key)
    claim = lineage.get("workspace_claim")
    if not isinstance(claim, Mapping):
        _fail("invalid", "native admission context workspace claim is missing")
    _id(normalized.get("runner_incarnation"), "native context runner_incarnation")
    _id(normalized.get("invocation_id"), "native context invocation_id")
    if "invocation_watermark" in normalized:
        _positive(normalized["invocation_watermark"], "native context invocation_watermark")
    if "prompt_id" in normalized:
        _optional_id(normalized["prompt_id"], "native context prompt_id")
    if "fenced" in normalized and type(normalized["fenced"]) is not bool:
        _fail("invalid", "native context fenced is invalid")
    definitions = normalized.get("definitions")
    if definitions is not None:
        if not isinstance(definitions, Mapping) or len(definitions) > MAX_RUNS:
            _fail("invalid", "native context definitions are malformed")
        for name, fact in definitions.items():
            _id(name, "native context definition name")
            if not isinstance(fact, Mapping):
                _fail("invalid", "native context definition fact is malformed")
            _reject_definition_identity(fact, "native context definition fact")
            if "name" in fact and fact["name"] != name:
                _fail("ownership-conflict", "native context definition name changed")
            if "digest" in fact:
                _digest(fact["digest"], "native context definition digest")
            if "tools" in fact:
                if type(fact["tools"]) is not list or not fact["tools"]:
                    _fail("invalid", "native context definition tools are malformed")
                for tool in fact["tools"]:
                    _id(tool, "native context definition tool")
    return normalized, lineage, dict(claim)


def _context_digest(context: dict[str, Any]) -> str:
    context_for_digest = dict(context)
    context_for_digest.pop("fenced", None)
    return canonical_digest(context_for_digest)


def _validate_admission(value: Any, context: Any = None) -> dict[str, Any]:
    admission = _exact_mapping(value, _ADMISSION_FIELDS, "native admission")
    for key in (
        "admission_id", "tool_use_id", "agent_type", "invocation_id",
        "lineage_id", "runner_incarnation",
    ):
        admission[key] = _id(admission[key], "native admission " + key)
    admission["definition_digest"] = _digest(
        admission["definition_digest"], "native admission definition_digest"
    )
    admission["trusted_definition_digest"] = _digest(
        admission["trusted_definition_digest"], "native admission trusted_definition_digest"
    )
    if admission["definition_digest"] != admission["trusted_definition_digest"]:
        _fail("ownership-conflict", "native admission definition digests disagree")
    admission["watermark"] = _positive(admission["watermark"], "native admission watermark")
    admission["owner_generation"] = _positive(
        admission["owner_generation"], "native admission owner_generation"
    )
    if type(admission["launch_completed"]) is not bool or admission["launch_completed"] is not False:
        _fail("unsupported", "native admission must precede child launch")
    parent = _mapping_with_optional(
        admission["parent"], _PARENT_REQUIRED_FIELDS,
        _PARENT_FIELDS - _PARENT_REQUIRED_FIELDS, "native admission parent"
    )
    parent["session_id"] = _id(parent["session_id"], "native admission parent session_id")
    parent["invocation_id"] = _id(parent["invocation_id"], "native admission parent invocation_id")
    if "agent_id" in parent:
        parent["agent_id"] = _optional_id(parent["agent_id"], "native admission parent agent_id")
    if "prompt_id" in parent:
        parent["prompt_id"] = _optional_id(parent["prompt_id"], "native admission parent prompt_id")
    admission["parent"] = parent
    if not isinstance(admission["custom_definition"], Mapping):
        _fail("invalid", "native admission custom_definition must be an object")
    _reject_definition_identity(admission["custom_definition"], "native admission custom_definition")
    admission["custom_definition"] = _normalize_json(dict(admission["custom_definition"]))

    if context is None:
        return admission
    normalized_context, lineage, _claim = _context_parts(context)
    if admission["owner_generation"] != lineage["owner_generation"]:
        _fail("ownership-conflict", "native admission owner generation changed")
    if admission["lineage_id"] != lineage["lineage_id"]:
        _fail("ownership-conflict", "native admission lineage changed")
    if admission["runner_incarnation"] != normalized_context["runner_incarnation"]:
        _fail("stale-generation", "native admission runner changed")
    if admission["invocation_id"] != normalized_context["invocation_id"]:
        _fail("stale-generation", "native admission invocation changed")
    if parent["session_id"] != lineage["session_uuid"]:
        _fail("ownership-conflict", "native admission parent session changed")
    if parent["invocation_id"] != normalized_context["invocation_id"]:
        _fail("stale-generation", "native admission parent invocation changed")
    context_prompt = normalized_context.get("prompt_id")
    if parent.get("prompt_id") != context_prompt:
        _fail("ownership-conflict", "native admission parent prompt changed")
    if "invocation_watermark" in normalized_context and admission["watermark"] <= normalized_context["invocation_watermark"]:
        _fail("stale-generation", "native admission predates current invocation")
    definitions = normalized_context.get("definitions")
    if definitions is not None:
        fact = definitions.get(admission["agent_type"])
        if not isinstance(fact, Mapping):
            _fail("permission-mismatch", "native admission definition is not trusted")
        if admission["custom_definition"] != dict(fact):
            _fail("permission-mismatch", "native admission policy changed")
        expected = fact.get("digest")
        if expected is not None and admission["trusted_definition_digest"] != expected:
            _fail("permission-mismatch", "native admission trusted definition changed")
    return admission


def _join_observation(
    observation: dict[str, Any], context: dict[str, Any], lineage: dict[str, Any],
    claim: dict[str, Any], admission: dict[str, Any],
) -> dict[str, Any]:
    source = observation["source_identity"]
    expected_source = {
        "owner_generation": lineage["owner_generation"],
        "lineage_id": lineage["lineage_id"],
        "lineage_generation": lineage["lineage_generation"],
        "session_uuid": lineage["session_uuid"],
        "runner_incarnation": context["runner_incarnation"],
        "invocation_id": context["invocation_id"],
    }
    for key, expected in expected_source.items():
        if source[key] != expected:
            _fail("ownership-conflict", "native child observation source changed")
    if observation["context_binding_digest"] != _context_digest(context):
        _fail("ownership-conflict", "native child observation context changed")
    if observation["claim_digest"] != canonical_digest(claim):
        _fail("ownership-conflict", "native child observation claim changed")

    for key in ("owner_generation", "lineage_id", "runner_incarnation", "invocation_id"):
        if admission[key] != expected_source[key]:
            _fail("ownership-conflict", "native child observation admission changed")
    parent_agent = admission["parent"].get("agent_id")
    child = observation["child"]
    if child["admission_id"] != admission["admission_id"]:
        _fail("ownership-conflict", "native child observation admission identity changed")
    if child["tool_use_id"] != admission["tool_use_id"]:
        _fail("ownership-conflict", "native child observation tool identity changed")
    if child["invocation_id"] != admission["invocation_id"]:
        _fail("stale-generation", "native child observation invocation changed")
    if child["parent_agent_id"] != parent_agent:
        _fail("ownership-conflict", "native child observation parent identity changed")
    if child["trusted_definition_digest"] != admission["trusted_definition_digest"]:
        _fail("permission-mismatch", "native child observation definition changed")
    if admission["watermark"] >= child["start_watermark"]:
        _fail("stale-generation", "native child observation start predates admission")
    if admission["watermark"] >= child["task_start_event"]["watermark"]:
        _fail("stale-generation", "native child task start predates admission")
    if child["task_start_event"]["watermark"] > observation["observation_watermark"]:
        _fail("stale-generation", "native child task start exceeds observation")
    return observation


def validate_observation(value: Any, *, context: Any, admission: Any) -> dict[str, Any]:
    """Validate and detach one complete native-child observation.

    ``context`` and ``admission`` are the already-selected source context and
    durable pre-allow admission.  Their immutable identity and policy are
    joined here; owner/daemon/fence and transport authority remain caller
    responsibilities.
    """

    normalized_context, lineage, claim = _context_parts(context)
    normalized_admission = _validate_admission(admission, normalized_context)
    observation = _validate_observation_shape(value)
    return _join_observation(
        observation, normalized_context, lineage, claim, normalized_admission
    )


def observation_run_id(observation: Any) -> str:
    """Return the exact runner-evidence child-run digest."""

    normalized = _validate_observation_shape(observation)
    child = normalized["child"]
    return canonical_digest(
        {
            "source_identity": normalized["source_identity"],
            "admission_id": child["admission_id"],
            "tool_use_id": child["tool_use_id"],
            "agent_id": child["agent_id"],
            "task_id": child["task_id"],
            "lineage_incarnation": child["lineage_incarnation"],
            "start_watermark": child["start_watermark"],
        }
    )


def validate_observation_progress(previous: Any, candidate: Any) -> dict[str, Any]:
    """Validate one strictly later observation of the same immutable child run."""

    prior = _validate_observation_shape(previous)
    current = _validate_observation_shape(candidate)
    if observation_run_id(prior) != observation_run_id(current):
        _fail("stale-generation", "native child observation changed its child run")
    if current["observation_watermark"] <= prior["observation_watermark"]:
        _fail("stale-generation", "native child observation watermark did not advance")
    child_prior = prior["child"]
    child_current = current["child"]
    immutable = (
        "admission_id", "tool_use_id", "agent_id", "task_id", "parent_agent_id",
        "invocation_id", "lineage_incarnation", "trusted_definition_digest",
        "start_watermark", "task_start_event",
    )
    for key in immutable:
        if child_prior[key] != child_current[key]:
            _fail("ownership-conflict", "native child observation identity changed")
    if prior["source_identity"] != current["source_identity"]:
        _fail("ownership-conflict", "native child observation source changed")
    if prior["context_binding_digest"] != current["context_binding_digest"]:
        _fail("ownership-conflict", "native child observation context digest changed")
    if prior["claim_digest"] != current["claim_digest"]:
        _fail("ownership-conflict", "native child observation claim digest changed")

    prior_outcome = prior["terminal_outcome"]
    current_outcome = current["terminal_outcome"]
    if prior_outcome is not None:
        if current["child"]["status"] != child_prior["status"]:
            _fail("stale-generation", "native child terminal state changed")
        if current_outcome != prior_outcome:
            _fail("stale-generation", "native child terminal outcome conflicted")
        if current["child"]["terminal_watermark"] != child_prior["terminal_watermark"]:
            _fail("stale-generation", "native child terminal watermark changed")
    elif child_prior["status"] != "active":
        _fail("stale-generation", "native child terminal observation is incomplete")
    if child_prior["status"] != "active" and current["child"]["status"] == "active":
        _fail("stale-generation", "native child terminal state became active")

    # An uncertain tool/effect is sticky in a pure projection.  Only an
    # authoritative lifecycle/effect layer may clear it; a newer snapshot
    # cannot silently turn unresolved work into a completed child.
    for key in ("uncertain_tool_ids", "unresolved_effect_ids"):
        if not set(child_prior[key]).issubset(set(current["child"][key])):
            _fail("uncertain-effect", "native child unresolved inventory was cleared")
    return current


def _validate_binding(value: Any) -> dict[str, Any]:
    binding = _exact_mapping(value, _BINDING_FIELDS, "native parent observation binding")
    binding["child_run_id"] = _digest(binding["child_run_id"], "parent binding child_run_id")
    binding["observation_id"] = _id(binding["observation_id"], "parent binding observation_id")
    binding["observation_digest"] = _digest(
        binding["observation_digest"], "parent binding observation_digest"
    )
    return binding


def _collection_size(admissions: dict[str, Any], observations: dict[str, Any]) -> None:
    canonical_digest({"admissions": admissions, "observations": observations})


def _prepare_causal(
    context: Any, admission: Any, admissions: Any, observations: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    normalized_context, lineage, claim = _context_parts(context)
    current = _validate_admission(admission, normalized_context)
    if not isinstance(admissions, Mapping) or not isinstance(observations, Mapping):
        _fail("invalid", "native causal admissions and observations must be maps")
    if len(admissions) > MAX_RUNS:
        _fail("uncertain-effect", "native causal admission history is full")
    normalized_admissions: dict[str, dict[str, Any]] = {}
    seen_tool_ids: set[str] = set()
    seen_watermarks: set[int] = set()
    for key, raw in admissions.items():
        key = _id(key, "native causal admission key")
        item = _validate_admission(raw, normalized_context)
        if item["admission_id"] != key:
            _fail("invalid", "native causal admission key changed")
        if key in normalized_admissions:
            _fail("invalid", "native causal admission identity is duplicated")
        if item["tool_use_id"] in seen_tool_ids:
            _fail("invalid", "native causal tool identity is duplicated")
        if item["watermark"] in seen_watermarks:
            _fail("stale-generation", "native causal admission watermark is duplicated")
        seen_tool_ids.add(item["tool_use_id"])
        seen_watermarks.add(item["watermark"])
        normalized_admissions[key] = item
    if current["admission_id"] in normalized_admissions and normalized_admissions[current["admission_id"]] != current:
        _fail("ownership-conflict", "native causal current admission changed")

    if len(observations) > MAX_RUNS * MAX_OBSERVATIONS_PER_RUN:
        _fail("uncertain-effect", "native child observation history is full")
    normalized_observations: dict[str, dict[str, Any]] = {}
    for key, raw in observations.items():
        key = _id(key, "native causal observation key")
        item = _validate_observation_shape(raw)
        if item["observation_id"] != key:
            _fail("invalid", "native causal observation key changed")
        if key in normalized_observations:
            _fail("invalid", "native causal observation identity is duplicated")
        child_admission = normalized_admissions.get(item["child"]["admission_id"])
        if child_admission is None:
            _fail("ownership-conflict", "native child observation admission is missing")
        item = _join_observation(item, normalized_context, lineage, claim, child_admission)
        normalized_observations[key] = item

    _collection_size(normalized_admissions, normalized_observations)
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in normalized_observations.values():
        run_id = observation_run_id(item)
        groups.setdefault(run_id, []).append(item)
    if len(groups) > MAX_RUNS:
        _fail("uncertain-effect", "native child run history is full")
    for run_id, history in groups.items():
        if len(history) > MAX_OBSERVATIONS_PER_RUN:
            _fail("uncertain-effect", "native child observation history for one run is full")
        history.sort(key=lambda item: item["observation_watermark"])
        seen_watermarks: set[int] = set()
        for item in history:
            watermark = item["observation_watermark"]
            if watermark in seen_watermarks:
                _fail("uncertain-effect", "native child run repeats an observation watermark")
            seen_watermarks.add(watermark)
        for prior, item in zip(history, history[1:]):
            validate_observation_progress(prior, item)
    return current, normalized_admissions, normalized_observations


def _binding_for(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "child_run_id": observation_run_id(observation),
        "observation_id": observation["observation_id"],
        "observation_digest": canonical_digest(observation),
    }


def _historical_parent_observation(
    admission: dict[str, Any], *, admissions: dict[str, dict[str, Any]],
    observations: dict[str, dict[str, Any]], stack: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    parent_agent = admission["parent"].get("agent_id")
    if parent_agent is None:
        return None
    if admission["admission_id"] in stack:
        _fail("ownership-conflict", "native parent admission contains a cycle")
    candidates: dict[str, list[dict[str, Any]]] = {}
    for observation in observations.values():
        child = observation["child"]
        if child["agent_id"] != parent_agent:
            continue
        if observation["observation_watermark"] >= admission["watermark"]:
            continue
        run_id = observation_run_id(observation)
        candidates.setdefault(run_id, []).append(observation)
    if not candidates:
        _fail("ownership-conflict", "native parent observation is missing")
    if len(candidates) != 1:
        _fail("ownership-conflict", "native parent child run is ambiguous or reused")
    history = next(iter(candidates.values()))
    history.sort(key=lambda item: item["observation_watermark"])
    selected = history[-1]
    if selected["child"]["status"] != "active" or selected["terminal_outcome"] is not None:
        _fail("stale-generation", "native parent was not active at admission")
    parent_admission_id = selected["child"]["admission_id"]
    parent_admission = admissions.get(parent_admission_id)
    if parent_admission is None:
        _fail("ownership-conflict", "native parent admission is missing")
    if parent_admission_id == admission["admission_id"] or parent_admission_id in stack:
        _fail("ownership-conflict", "native parent admission contains a cycle")
    _historical_parent_observation(
        parent_admission,
        admissions=admissions,
        observations=observations,
        stack=stack + (admission["admission_id"],),
    )
    return selected


def derive_parent_binding(
    admission: Any, *, context: Any, admissions: Any, observations: Any,
) -> dict[str, Any] | None:
    """Derive the controller-owned causal parent binding for one admission."""

    current, normalized_admissions, normalized_observations = _prepare_causal(
        context, admission, admissions, observations
    )
    selected = _historical_parent_observation(
        current,
        admissions=normalized_admissions,
        observations=normalized_observations,
    )
    return None if selected is None else _binding_for(selected)


def validate_parent_binding(
    admission: Any, binding: Any, *, context: Any, admissions: Any, observations: Any,
) -> dict[str, Any] | None:
    """Recompute and compare a stored three-field causal parent binding."""

    expected = derive_parent_binding(
        admission,
        context=context,
        admissions=admissions,
        observations=observations,
    )
    if expected is None:
        if binding is not None:
            _fail("invalid", "top-level native admission has a parent binding")
        return None
    if binding is None:
        _fail("ownership-conflict", "nested native admission has no parent binding")
    normalized = _validate_binding(binding)
    if normalized != expected:
        _fail("ownership-conflict", "native parent observation binding changed")
    return normalized


def _validate_observation_context_only(
    observation: dict[str, Any], context: dict[str, Any],
    lineage: dict[str, Any], claim: dict[str, Any],
) -> dict[str, Any]:
    source = observation["source_identity"]
    expected = {
        "owner_generation": lineage["owner_generation"],
        "lineage_id": lineage["lineage_id"],
        "lineage_generation": lineage["lineage_generation"],
        "session_uuid": lineage["session_uuid"],
        "runner_incarnation": context["runner_incarnation"],
        "invocation_id": context["invocation_id"],
    }
    if any(source[key] != value for key, value in expected.items()):
        _fail("ownership-conflict", "native parent observation source changed")
    if observation["context_binding_digest"] != _context_digest(context):
        _fail("ownership-conflict", "native parent observation context changed")
    if observation["claim_digest"] != canonical_digest(claim):
        _fail("ownership-conflict", "native parent observation claim changed")
    if observation["child"]["invocation_id"] != context["invocation_id"]:
        _fail("stale-generation", "native parent observation invocation changed")
    return observation


def require_live_parent(
    admission: Any, binding: Any, *, context: Any, observations: Any,
) -> None:
    """Require the binding's parent run to remain the one current active run.

    This is intentionally stricter than historical derivation.  A later
    terminal observation may not rewrite an already-valid archived join, but
    it does make a new/live nested admission unsafe.
    """

    normalized_context, lineage, claim = _context_parts(context)
    current = _validate_admission(admission, normalized_context)
    parent_agent = current["parent"].get("agent_id")
    if parent_agent is None:
        if binding is not None:
            _fail("invalid", "top-level native admission has a live parent binding")
        return None
    if binding is None:
        _fail("ownership-conflict", "nested native admission has no live parent binding")
    normalized_binding = _validate_binding(binding)
    if not isinstance(observations, Mapping):
        _fail("invalid", "native parent observations must be a map")
    if len(observations) > MAX_RUNS * MAX_OBSERVATIONS_PER_RUN:
        _fail("uncertain-effect", "native parent observation history is full")
    normalized_observations: dict[str, dict[str, Any]] = {}
    for key, raw in observations.items():
        key = _id(key, "native parent observation key")
        item = _validate_observation_shape(raw)
        if key != item["observation_id"]:
            _fail("invalid", "native parent observation key changed")
        normalized_observations[key] = _validate_observation_context_only(
            item, normalized_context, lineage, claim
        )
    _collection_size({}, normalized_observations)
    # The caller must present the exact committed observation named by the
    # binding; recomputing the digest here catches substitution/reuse.
    selected = normalized_observations.get(normalized_binding["observation_id"])
    if selected is None:
        _fail("ownership-conflict", "native parent observation is missing")
    if observation_run_id(selected) != normalized_binding["child_run_id"]:
        _fail("ownership-conflict", "native parent child run binding changed")
    if canonical_digest(selected) != normalized_binding["observation_digest"]:
        _fail("ownership-conflict", "native parent observation digest changed")
    if selected["child"]["agent_id"] != parent_agent:
        _fail("ownership-conflict", "native parent agent identity changed")

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in normalized_observations.values():
        if item["child"]["agent_id"] != parent_agent:
            continue
        groups.setdefault(observation_run_id(item), []).append(item)
    if not groups:
        _fail("ownership-conflict", "native parent observation is missing")
    if len(groups) > MAX_RUNS:
        _fail("uncertain-effect", "native parent child run history is full")
    if len(groups) != 1:
        _fail("ownership-conflict", "native parent child run is ambiguous or reused")
    history = next(iter(groups.values()))
    if len(history) > MAX_OBSERVATIONS_PER_RUN:
        _fail("uncertain-effect", "native parent observation history for one run is full")
    history.sort(key=lambda item: item["observation_watermark"])
    for prior, item in zip(history, history[1:]):
        validate_observation_progress(prior, item)
    latest = history[-1]
    if latest["observation_watermark"] >= current["watermark"]:
        _fail("stale-generation", "native parent observation is not before admission")
    if latest["child"]["status"] != "active" or latest["terminal_outcome"] is not None:
        _fail("stale-generation", "native parent is no longer active")
    return None


__all__ = [
    "NativeChildContractError",
    "canonical_digest",
    "validate_observation",
    "observation_run_id",
    "validate_observation_progress",
    "derive_parent_binding",
    "validate_parent_binding",
    "require_live_parent",
]
