# SPDX-License-Identifier: Apache-2.0
"""Pure native-swap evidence and release-boundary contracts.

This module deliberately has no controller, state-store, SDK, filesystem, or
runtime dependency.  It validates the closed records exchanged across those
boundaries and returns detached JSON-shaped values.  A valid observation is
not by itself a capability grant: callers must still apply their own runtime
and lifecycle authority, and must call :func:`require_satisfied_stage_records`
before treating the complete evidence sequence as sufficient.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Tuple


NATIVE_SWAP_STAGES = (
    "entry",
    "graph-drained",
    "source-excluded",
    "target-held",
    "pre-release",
    "release-boundary",
)

NATIVE_SWAP_STAGE_SET = frozenset(NATIVE_SWAP_STAGES)
MAX_NATIVE_SWAP_STAGE_RECORD_BYTES = 64 * 1024
MAX_NATIVE_SWAP_LEDGER_BYTES = 1024 * 1024
MAX_NATIVE_SWAP_ID_LENGTH = 256
MAX_NATIVE_SWAP_REFERENCE_LENGTH = 512
MAX_NATIVE_SWAP_DEPTH = 32
MAX_NATIVE_SWAP_NODES = 100_000
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

_SOURCE_IDENTITY_FIELDS = frozenset({
    "owner_generation",
    "lineage_id",
    "lineage_generation",
    "session_uuid",
    "runner_incarnation",
    "invocation_id",
})
_EVIDENCE_BINDING_FIELDS = frozenset({
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
_RELEASE_BINDING_FIELDS = frozenset({
    "schema_version",
    "architecture",
    "record_kind",
    "operation_id",
    "owner_generation",
    "expected_daemon_id",
    "participant_id",
    "session_id",
    "runner_incarnation",
    "lineage_id",
    "lineage_generation",
    "request_epoch_id",
    "release_id",
    "release_intent_digest",
    "pre_release_evidence_digest",
    "binding_digest",
})
_RELEASE_BOUNDARY_FIELDS = frozenset({
    "binding",
    "gate_event_id",
    "gate_watermark",
})
_EVIDENCE_RESPONSE_FIELDS = frozenset({
    "binding",
    "runtime_identity_digest",
    "evidence_reference",
    "request_observation",
    "worker_state_clear",
})
_REQUEST_OBSERVATION_FIELDS = frozenset({
    "epoch_id",
    "entry_evidence_ref",
    "through_evidence_ref",
    "observable",
    "continuous",
    "new_requests",
})
_WORKER_CLEAR_FIELDS = frozenset({
    "source_identity_digest",
    "interrupt_id",
    "method",
    "evidence_reference",
    "observation_watermark",
    "cleared",
})
_STAGE_RECORD_FIELDS = frozenset({"observation", "evidence_digest"})
_RELEASE_AUTHORIZATION_FIELDS = frozenset({
    "validation_id",
    "authorized",
    "authorization_id",
    "binding",
    "authorization_digest",
})
_IMMUTABLE_BINDING_FIELDS = (
    "operation_id",
    "owner_generation",
    "expected_daemon_id",
    "source_identity",
    "source_context_digest",
    "source_claim_digest",
    "target_spec_digest",
    "request_epoch_id",
)
_STAGE_BOUND_BINDING_FIELDS = (
    "interrupt_id",
    "interrupt_intent_digest",
    "source_archive_digest",
    "target_runner_incarnation",
    "release_id",
    "release_intent_digest",
    "release_boundary",
)


class NativeSwapContractError(ValueError):
    """Structured refusal raised by every pure native-swap validator."""

    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(self.message)

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message}


def _fail(code: str, message: str) -> None:
    raise NativeSwapContractError(code, message)


def _json_normalize(value: Any, *, depth: int = 0, nodes: Optional[List[int]] = None) -> Any:
    if nodes is None:
        nodes = [0]
    nodes[0] += 1
    if depth > MAX_NATIVE_SWAP_DEPTH or nodes[0] > MAX_NATIVE_SWAP_NODES:
        _fail("invalid", "native swap JSON exceeds structural bounds")
    kind = type(value)
    if value is None or kind is bool or kind is int or kind is str:
        return value
    if kind is float:
        if not math.isfinite(value):
            _fail("invalid", "native swap JSON contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                _fail("invalid", "native swap JSON object keys must be strings")
            result[key] = _json_normalize(item, depth=depth + 1, nodes=nodes)
        return result
    if type(value) is list:
        return [
            _json_normalize(item, depth=depth + 1, nodes=nodes)
            for item in value
        ]
    _fail("invalid", "native swap value is not JSON")


def _canonical_json(value: Any, *, limit: Optional[int] = MAX_NATIVE_SWAP_LEDGER_BYTES) -> str:
    normalized = _json_normalize(value)
    try:
        encoded = json.dumps(
            normalized,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise NativeSwapContractError("invalid", "native swap value is not canonical JSON") from exc
    if limit is not None and len(encoded) > limit:
        _fail("invalid", "native swap canonical record exceeds capacity")
    return encoded.decode("utf-8")


def canonical_digest(value: Any) -> str:
    """Return the bounded canonical SHA-256 digest used by the contracts."""
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _exact_mapping(value: Any, fields: frozenset[str], label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("invalid", "%s must be an object" % label)
    if set(value) != set(fields):
        _fail("invalid", "%s has unknown or missing fields" % label)
    return _json_normalize(value)


def _text(value: Any, label: str, *, limit: int = MAX_NATIVE_SWAP_ID_LENGTH) -> str:
    if type(value) is not str or not value or len(value) > limit or "\x00" in value:
        _fail("invalid", "%s must be a bounded non-empty string" % label)
    if value != value.strip():
        _fail("invalid", "%s must not have surrounding whitespace" % label)
    return value


def _positive_int(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        _fail("invalid", "%s must be a positive integer" % label)
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail("invalid", "%s must be a non-negative integer" % label)
    return value


def _digest(value: Any, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail("invalid", "%s must be a lowercase SHA-256 digest" % label)
    return value


def _optional_text(value: Any, label: str) -> Optional[str]:
    if value is None:
        return None
    return _text(value, label)


def _optional_digest(value: Any, label: str) -> Optional[str]:
    if value is None:
        return None
    return _digest(value, label)


def _record_size(value: Any, label: str, *, limit: int) -> None:
    _canonical_json(value, limit=limit)


def _validate_source_identity(value: Any) -> Dict[str, Any]:
    raw = _exact_mapping(value, _SOURCE_IDENTITY_FIELDS, "native swap source identity")
    raw["owner_generation"] = _positive_int(
        raw["owner_generation"], "source identity owner_generation"
    )
    raw["lineage_generation"] = _positive_int(
        raw["lineage_generation"], "source identity lineage_generation"
    )
    for key in (
        "lineage_id", "session_uuid", "runner_incarnation", "invocation_id",
    ):
        raw[key] = _text(raw[key], "source identity " + key)
    return raw


def validate_release_binding(value: Any) -> Dict[str, Any]:
    """Validate the exact synchronous native-swap release binding."""
    raw = _exact_mapping(value, _RELEASE_BINDING_FIELDS, "native swap release binding")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 2:
        _fail("invalid", "native swap release schema_version is unsupported")
    if raw["architecture"] != "native-coordinator-lineage":
        _fail("invalid", "native swap release architecture is unsupported")
    if raw["record_kind"] != "native-swap-release-binding":
        _fail("invalid", "native swap release record_kind is unsupported")
    for key in (
        "operation_id", "expected_daemon_id", "participant_id", "session_id",
        "runner_incarnation", "lineage_id", "request_epoch_id", "release_id",
    ):
        raw[key] = _text(raw[key], "native swap release " + key)
    for key in ("owner_generation", "lineage_generation"):
        raw[key] = _positive_int(raw[key], "native swap release " + key)
    for key in (
        "release_intent_digest", "pre_release_evidence_digest", "binding_digest",
    ):
        raw[key] = _digest(raw[key], "native swap release " + key)
    expected = canonical_digest({
        key: item for key, item in raw.items() if key != "binding_digest"
    })
    if raw["binding_digest"] != expected:
        _fail("stale-generation", "native swap release binding digest changed")
    _record_size(raw, "native swap release binding", limit=MAX_NATIVE_SWAP_STAGE_RECORD_BYTES)
    return copy.deepcopy(raw)


def validate_release_boundary(
        value: Any, *, expected_binding: Any = None
) -> Dict[str, Any]:
    """Validate an SDK synchronous held-to-released gate receipt."""
    raw = _exact_mapping(value, _RELEASE_BOUNDARY_FIELDS, "native swap release boundary")
    raw["binding"] = validate_release_binding(raw["binding"])
    raw["gate_event_id"] = _text(
        raw["gate_event_id"], "native swap release boundary gate_event_id"
    )
    raw["gate_watermark"] = _positive_int(
        raw["gate_watermark"], "native swap release boundary gate_watermark"
    )
    if expected_binding is not None:
        expected = validate_release_binding(expected_binding)
        if raw["binding"] != expected:
            _fail("stale-generation", "native swap release boundary binding changed")
    _record_size(raw, "native swap release boundary", limit=MAX_NATIVE_SWAP_STAGE_RECORD_BYTES)
    return copy.deepcopy(raw)


def _release_binding_matches_request(
        request: Mapping[str, Any], boundary: Mapping[str, Any]
) -> None:
    binding = boundary["binding"]
    source = request["source_identity"]
    pairs = (
        ("operation_id", "operation_id"),
        ("owner_generation", "owner_generation"),
        ("expected_daemon_id", "expected_daemon_id"),
        ("request_epoch_id", "request_epoch_id"),
        ("release_id", "release_id"),
        ("release_intent_digest", "release_intent_digest"),
    )
    for left, right in pairs:
        if binding[left] != request[right]:
            _fail("stale-generation", "native swap release boundary identity changed")
    if (
            binding["session_id"] != source["session_uuid"]
            or binding["lineage_id"] != source["lineage_id"]
            or binding["lineage_generation"] != source["lineage_generation"]
            or binding["runner_incarnation"] != request["target_runner_incarnation"]
    ):
        _fail("stale-generation", "native swap release boundary source identity changed")


def validate_evidence_binding(value: Any) -> Dict[str, Any]:
    """Validate one exact private native-swap evidence-provider request."""
    raw = _exact_mapping(value, _EVIDENCE_BINDING_FIELDS, "native swap evidence binding")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 2:
        _fail("invalid", "native swap evidence schema_version is unsupported")
    if raw["architecture"] != "native-coordinator-lineage":
        _fail("invalid", "native swap evidence architecture is unsupported")
    if raw["record_kind"] != "native-swap-evidence-request":
        _fail("invalid", "native swap evidence record_kind is unsupported")
    raw["stage"] = _text(raw["stage"], "native swap evidence stage")
    if raw["stage"] not in NATIVE_SWAP_STAGE_SET:
        _fail("invalid", "native swap evidence stage is unsupported")
    raw["operation_id"] = _text(raw["operation_id"], "native swap evidence operation_id")
    raw["owner_generation"] = _positive_int(
        raw["owner_generation"], "native swap evidence owner_generation"
    )
    raw["expected_daemon_id"] = _text(
        raw["expected_daemon_id"], "native swap evidence expected_daemon_id"
    )
    raw["source_identity"] = _validate_source_identity(raw["source_identity"])
    if raw["source_identity"]["owner_generation"] != raw["owner_generation"]:
        _fail("stale-generation", "native swap source owner generation changed")
    raw["source_context_digest"] = _digest(
        raw["source_context_digest"], "native swap source_context_digest"
    )
    raw["source_claim_digest"] = _digest(
        raw["source_claim_digest"], "native swap source_claim_digest"
    )
    raw["target_spec_digest"] = _digest(
        raw["target_spec_digest"], "native swap target_spec_digest"
    )
    raw["request_epoch_id"] = _text(
        raw["request_epoch_id"], "native swap request_epoch_id"
    )

    raw["interrupt_id"] = _optional_text(raw["interrupt_id"], "native swap interrupt_id")
    raw["interrupt_intent_digest"] = _optional_digest(
        raw["interrupt_intent_digest"], "native swap interrupt_intent_digest"
    )
    raw["source_archive_digest"] = _optional_digest(
        raw["source_archive_digest"], "native swap source_archive_digest"
    )
    raw["target_runner_incarnation"] = _optional_text(
        raw["target_runner_incarnation"], "native swap target_runner_incarnation"
    )
    raw["release_id"] = _optional_text(raw["release_id"], "native swap release_id")
    raw["release_intent_digest"] = _optional_digest(
        raw["release_intent_digest"], "native swap release_intent_digest"
    )

    required_by_stage = {
        "entry": set(),
        "graph-drained": {"interrupt_id", "interrupt_intent_digest"},
        # The source archive is persisted after source exclusion.  A target
        # runner may already be reserved here, but neither value is required
        # until the target-held boundary.
        "source-excluded": {"interrupt_id", "interrupt_intent_digest"},
        "target-held": {
            "interrupt_id", "interrupt_intent_digest", "source_archive_digest",
            "target_runner_incarnation",
        },
        "pre-release": {
            "interrupt_id", "interrupt_intent_digest", "source_archive_digest",
            "target_runner_incarnation", "release_id", "release_intent_digest",
        },
        "release-boundary": {
            "interrupt_id", "interrupt_intent_digest", "source_archive_digest",
            "target_runner_incarnation", "release_id", "release_intent_digest",
            "release_boundary",
        },
    }
    optional_fields = {
        "interrupt_id", "interrupt_intent_digest", "source_archive_digest",
        "target_runner_incarnation", "release_id", "release_intent_digest",
        "release_boundary",
    }
    if raw["stage"] == "release-boundary":
        if raw["release_boundary"] is None:
            _fail("invalid", "native release-boundary evidence requires a receipt")
        raw["release_boundary"] = validate_release_boundary(raw["release_boundary"])
        _release_binding_matches_request(raw, raw["release_boundary"])
    else:
        if raw["release_boundary"] is not None:
            _fail("invalid", "native release boundary is not valid at this stage")
    required = required_by_stage[raw["stage"]]
    early_target_runner = raw["stage"] in {
        "entry", "graph-drained", "source-excluded",
    }
    for field in optional_fields:
        present = raw[field] is not None
        if field in required and not present:
            _fail("invalid", "native swap %s is missing for %s" % (field, raw["stage"]))
        if field == "target_runner_incarnation" and early_target_runner:
            continue
        if field == "source_archive_digest" and raw["stage"] == "source-excluded":
            continue
        if field not in required and present:
            _fail("invalid", "native swap %s is premature for %s" % (field, raw["stage"]))
    if (raw["interrupt_id"] is None) != (raw["interrupt_intent_digest"] is None):
        _fail("invalid", "native swap interrupt identity is incomplete")
    if (raw["release_id"] is None) != (raw["release_intent_digest"] is None):
        _fail("invalid", "native swap release identity is incomplete")
    _record_size(raw, "native swap evidence binding", limit=MAX_NATIVE_SWAP_STAGE_RECORD_BYTES)
    return copy.deepcopy(raw)


def _prior_observations(prior_records: Any) -> List[Tuple[str, Dict[str, Any], str]]:
    if prior_records is None:
        return []
    if isinstance(prior_records, Mapping):
        items = list(prior_records.items())
    elif isinstance(prior_records, (list, tuple)):
        items = []
        for item in prior_records:
            if isinstance(item, Mapping) and "observation" in item:
                observation = item["observation"]
                stage = (
                    observation.get("binding", {}).get("stage")
                    if isinstance(observation, Mapping)
                    and isinstance(observation.get("binding"), Mapping)
                    else None
                )
                items.append((stage, item))
            else:
                stage = (
                    item.get("binding", {}).get("stage")
                    if isinstance(item, Mapping)
                    and isinstance(item.get("binding"), Mapping)
                    else None
                )
                items.append((stage, item))
    else:
        _fail("invalid", "native swap prior records must be a sequence or map")
    result: List[Tuple[str, Dict[str, Any], str]] = []
    for stage_key, item in items:
        if isinstance(item, Mapping) and set(item) == _STAGE_RECORD_FIELDS:
            observation = item.get("observation")
            evidence_digest = item.get("evidence_digest")
        else:
            observation = item
            evidence_digest = None
        if not isinstance(observation, Mapping):
            _fail("invalid", "native swap prior observation is malformed")
        binding = observation.get("binding")
        if not isinstance(binding, Mapping):
            _fail("invalid", "native swap prior observation binding is missing")
        stage = stage_key if isinstance(stage_key, str) else binding.get("stage")
        if not isinstance(stage, str) or stage not in NATIVE_SWAP_STAGE_SET:
            _fail("invalid", "native swap prior stage is unsupported")
        normalized = _validate_response_shape(observation)
        if normalized["binding"]["stage"] != stage:
            _fail("stale-generation", "native swap prior stage changed")
        if evidence_digest is None:
            evidence_digest = canonical_digest(normalized)
        else:
            evidence_digest = _digest(evidence_digest, "native swap prior evidence_digest")
            if evidence_digest != canonical_digest(normalized):
                _fail("stale-generation", "native swap prior evidence digest changed")
        result.append((stage, normalized, evidence_digest))
    result.sort(key=lambda item: NATIVE_SWAP_STAGES.index(item[0]))
    return result


def _validate_response_shape(value: Any) -> Dict[str, Any]:
    raw = _exact_mapping(value, _EVIDENCE_RESPONSE_FIELDS, "native swap evidence response")
    raw["binding"] = validate_evidence_binding(raw["binding"])
    raw["runtime_identity_digest"] = _digest(
        raw["runtime_identity_digest"], "native swap runtime_identity_digest"
    )
    raw["evidence_reference"] = _text(
        raw["evidence_reference"], "native swap evidence_reference",
        limit=MAX_NATIVE_SWAP_REFERENCE_LENGTH,
    )
    observation = _exact_mapping(
        raw["request_observation"], _REQUEST_OBSERVATION_FIELDS,
        "native swap request observation",
    )
    observation["epoch_id"] = _text(observation["epoch_id"], "native swap observation epoch_id")
    observation["entry_evidence_ref"] = _text(
        observation["entry_evidence_ref"], "native swap entry_evidence_ref",
        limit=MAX_NATIVE_SWAP_REFERENCE_LENGTH,
    )
    observation["through_evidence_ref"] = _text(
        observation["through_evidence_ref"], "native swap through_evidence_ref",
        limit=MAX_NATIVE_SWAP_REFERENCE_LENGTH,
    )
    if type(observation["observable"]) is not bool:
        _fail("invalid", "native swap observation observable must be boolean")
    if type(observation["continuous"]) is not bool:
        _fail("invalid", "native swap observation continuous must be boolean")
    if observation["new_requests"] is not None:
        observation["new_requests"] = _nonnegative_int(
            observation["new_requests"], "native swap observation new_requests"
        )
    if observation["epoch_id"] != raw["binding"]["request_epoch_id"]:
        _fail("stale-generation", "native swap observation epoch changed")
    raw["request_observation"] = observation

    clear = raw["worker_state_clear"]
    if raw["binding"]["stage"] == "entry":
        if clear is not None:
            _fail("invalid", "native swap entry cannot claim worker state clear")
    else:
        clear = _exact_mapping(clear, _WORKER_CLEAR_FIELDS, "native swap worker state clear")
        clear["source_identity_digest"] = _digest(
            clear["source_identity_digest"], "native swap source_identity_digest"
        )
        expected_source_digest = canonical_digest(raw["binding"]["source_identity"])
        if clear["source_identity_digest"] != expected_source_digest:
            _fail("stale-generation", "native swap worker source identity changed")
        clear["interrupt_id"] = _text(clear["interrupt_id"], "native swap clear interrupt_id")
        if clear["interrupt_id"] != raw["binding"]["interrupt_id"]:
            _fail("stale-generation", "native swap worker interrupt identity changed")
        clear["method"] = _text(clear["method"], "native swap worker clear method")
        clear["evidence_reference"] = _text(
            clear["evidence_reference"], "native swap worker clear evidence_reference",
            limit=MAX_NATIVE_SWAP_REFERENCE_LENGTH,
        )
        clear["observation_watermark"] = _positive_int(
            clear["observation_watermark"], "native swap worker clear observation_watermark"
        )
        if type(clear["cleared"]) is not bool:
            _fail("invalid", "native swap worker clear cleared must be boolean")
    raw["worker_state_clear"] = clear
    return copy.deepcopy(raw)


def _check_response_history(
        current: Mapping[str, Any], prior_records: Any,
        runtime_identity_digest: str,
) -> None:
    prior = _prior_observations(prior_records)
    current_binding = current["binding"]
    current_index = NATIVE_SWAP_STAGES.index(current_binding["stage"])
    if not prior and current_index != 0:
        _fail("stale-generation", "native swap history must begin at entry")
    if prior:
        indexes = [NATIVE_SWAP_STAGES.index(stage) for stage, _, _ in prior]
        if indexes != list(range(len(indexes))):
            _fail("invalid", "native swap prior stages are not ordered")
        if indexes[-1] + 1 != current_index:
            _fail("stale-generation", "native swap stage sequence changed")
        first_binding = prior[0][1]["binding"]
        for field in _IMMUTABLE_BINDING_FIELDS:
            if current_binding[field] != first_binding[field]:
                _fail("stale-generation", "native swap immutable binding changed")
        prior_bindings = [observation["binding"] for _, observation, _ in prior]
        for field in _STAGE_BOUND_BINDING_FIELDS:
            known = [item[field] for item in prior_bindings if item[field] is not None]
            if known:
                if any(item != known[0] for item in known[1:]):
                    _fail("stale-generation", "native swap stage binding was rewritten")
                if current_binding[field] != known[0]:
                    _fail("stale-generation", "native swap stage binding was rewritten")
        first_observation = prior[0][1]["request_observation"]
        current_observation = current["request_observation"]
        if (
                current_observation["entry_evidence_ref"]
                != first_observation["entry_evidence_ref"]
                or current_observation["epoch_id"] != first_observation["epoch_id"]
        ):
            _fail("stale-generation", "native swap request epoch observation changed")
        for _, observation, _ in prior:
            if observation["runtime_identity_digest"] != runtime_identity_digest:
                _fail("stale-generation", "native swap runtime identity changed")
        prior_watermark = None
        for _, observation, _ in prior:
            clear = observation["worker_state_clear"]
            if clear is None:
                continue
            watermark = clear["observation_watermark"]
            if prior_watermark is not None and watermark < prior_watermark:
                _fail("stale-generation", "native swap source watermark moved backward")
            prior_watermark = watermark
        current_clear = current["worker_state_clear"]
        if current_clear is not None and prior_watermark is not None:
            if current_clear["observation_watermark"] < prior_watermark:
                _fail("stale-generation", "native swap source watermark moved backward")
    if current["runtime_identity_digest"] != runtime_identity_digest:
        _fail("stale-generation", "native swap runtime identity changed")
    if current_binding["stage"] == "release-boundary" and prior:
        prior_map = {stage: (observation, digest) for stage, observation, digest in prior}
        prior_pre = prior_map.get("pre-release")
        if prior_pre is None:
            _fail("stale-generation", "native release boundary has no pre-release evidence")
        boundary = current_binding["release_boundary"]
        if boundary["binding"]["pre_release_evidence_digest"] != prior_pre[1]:
            _fail("stale-generation", "native release boundary pre-release evidence changed")


def validate_evidence_response(
        binding: Any,
        value: Any,
        *,
        runtime_identity_digest: Any,
        prior_records: Any = (),
) -> Dict[str, Any]:
    """Validate one provider response while retaining negative observations."""
    expected_binding = validate_evidence_binding(binding)
    normalized = _validate_response_shape(value)
    if normalized["binding"] != expected_binding:
        _fail("stale-generation", "native swap evidence response binding changed")
    expected_runtime = _digest(
        runtime_identity_digest, "expected native swap runtime_identity_digest"
    )
    _check_response_history(normalized, prior_records, expected_runtime)
    _record_size(
        normalized,
        "native swap evidence response",
        limit=MAX_NATIVE_SWAP_STAGE_RECORD_BYTES,
    )
    return copy.deepcopy(normalized)


def validate_stage_records(
        value: Any, *, runtime_identity_digest: Any
) -> Dict[str, Dict[str, Any]]:
    """Validate the contiguous append-only native-swap stage collection."""
    if not isinstance(value, Mapping):
        _fail("invalid", "native swap stage records must be an object")
    if len(value) > len(NATIVE_SWAP_STAGES):
        _fail("invalid", "native swap stage records exceed six stages")
    keys = list(value)
    if any(type(key) is not str or key not in NATIVE_SWAP_STAGE_SET for key in keys):
        _fail("invalid", "native swap stage record key is unsupported")
    expected_keys = list(NATIVE_SWAP_STAGES[:len(keys)])
    if set(keys) != set(expected_keys):
        _fail("stale-generation", "native swap stage sequence is not append-only")
    normalized: Dict[str, Dict[str, Any]] = {}
    for stage in expected_keys:
        record = _exact_mapping(value[stage], _STAGE_RECORD_FIELDS,
                                "native swap stage record")
        if (not isinstance(record.get("observation"), Mapping)
                or not isinstance(record["observation"].get("binding"), Mapping)):
            _fail("invalid", "native swap stage observation is malformed")
        observation = validate_evidence_response(
            record["observation"]["binding"], record["observation"],
            runtime_identity_digest=runtime_identity_digest,
            prior_records=normalized,
        )
        if observation["binding"]["stage"] != stage:
            _fail("stale-generation", "native swap stage key disagrees with observation")
        evidence_digest = _digest(record["evidence_digest"], "native swap evidence_digest")
        if evidence_digest != canonical_digest(observation):
            _fail("stale-generation", "native swap evidence digest changed")
        normalized[stage] = {
            "observation": observation,
            "evidence_digest": evidence_digest,
        }
        _record_size(normalized[stage], "native swap stage record",
                     limit=MAX_NATIVE_SWAP_STAGE_RECORD_BYTES)
    _record_size(normalized, "native swap stage ledger", limit=MAX_NATIVE_SWAP_LEDGER_BYTES)
    return copy.deepcopy(normalized)


def require_satisfied_stage_records(
        records: Any, *, runtime_identity_digest: Any,
        through_stage: str = "release-boundary",
) -> None:
    """Require a contiguous stage prefix to be positive and fully cleared.

    This is intentionally separate from response validation.  A negative or
    unknown provider observation is valid evidence and must be durably retained
    before this gate refuses the swap.
    """
    if not isinstance(records, Mapping):
        _fail("invalid", "native swap stage records must be an object")
    through_stage = _text(through_stage, "native swap satisfaction through_stage")
    if through_stage not in NATIVE_SWAP_STAGE_SET:
        _fail("invalid", "native swap satisfaction through_stage is unsupported")
    through_index = NATIVE_SWAP_STAGES.index(through_stage)
    expected_stages = NATIVE_SWAP_STAGES[:through_index + 1]
    if set(records) != set(expected_stages):
        _fail("unsupported", "native swap evidence sequence does not reach through_stage")
    expected_runtime = _digest(
        runtime_identity_digest, "expected native swap runtime_identity_digest"
    )
    ordered = validate_stage_records(
        records,
        runtime_identity_digest=expected_runtime,
    )
    for stage in expected_stages:
        observation = ordered[stage]["observation"]
        request_observation = observation["request_observation"]
        if (
                request_observation["observable"] is not True
                or request_observation["continuous"] is not True
                or request_observation["new_requests"] != 0
        ):
            _fail(
                "uncertain-effect",
                "native swap request observation is not a proven zero interval",
            )
        clear = observation["worker_state_clear"]
        if stage != "entry" and (not isinstance(clear, Mapping) or clear["cleared"] is not True):
            _fail("uncertain-effect", "native swap worker state clear is not proven")


def validate_release_authorization(
        value: Any, *, expected_validation_id: Any, expected_binding: Any
) -> Dict[str, Any]:
    """Validate the authenticated controller release-authority acknowledgement."""
    raw = _exact_mapping(
        value, _RELEASE_AUTHORIZATION_FIELDS,
        "native swap release authorization",
    )
    raw["validation_id"] = _text(
        raw["validation_id"], "native swap authorization validation_id"
    )
    expected_id = _text(
        expected_validation_id, "expected native swap authorization validation_id"
    )
    if raw["validation_id"] != expected_id:
        _fail("stale-generation", "native swap authorization validation ID changed")
    if type(raw["authorized"]) is not bool:
        _fail("invalid", "native swap authorization authorized must be boolean")
    raw["authorization_id"] = _text(
        raw["authorization_id"], "native swap authorization authorization_id"
    )
    expected_binding_normalized = validate_release_binding(expected_binding)
    raw["binding"] = validate_release_binding(raw["binding"])
    if raw["binding"] != expected_binding_normalized:
        _fail("stale-generation", "native swap authorization binding changed")
    raw["authorization_digest"] = _digest(
        raw["authorization_digest"], "native swap authorization authorization_digest"
    )
    expected_digest = canonical_digest({
        key: item for key, item in raw.items() if key != "authorization_digest"
    })
    if raw["authorization_digest"] != expected_digest:
        _fail("stale-generation", "native swap authorization digest changed")
    _record_size(raw, "native swap release authorization",
                 limit=MAX_NATIVE_SWAP_STAGE_RECORD_BYTES)
    return copy.deepcopy(raw)


__all__ = [
    "NATIVE_SWAP_STAGES",
    "NATIVE_SWAP_STAGE_SET",
    "MAX_NATIVE_SWAP_STAGE_RECORD_BYTES",
    "MAX_NATIVE_SWAP_LEDGER_BYTES",
    "NativeSwapContractError",
    "canonical_digest",
    "require_satisfied_stage_records",
    "validate_evidence_binding",
    "validate_evidence_response",
    "validate_release_authorization",
    "validate_release_binding",
    "validate_release_boundary",
    "validate_stage_records",
]
