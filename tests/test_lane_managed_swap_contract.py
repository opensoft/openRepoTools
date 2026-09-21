# SPDX-License-Identifier: Apache-2.0
"""Pure NativeSwapEvidence/release-boundary contract tests.

These tests never construct a controller, state store, SDK adapter, runtime,
or process.  They exercise only the closed request/response records that the
controller and adapter will share.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Mapping

import pytest

from lane_managed_swap import (
    NATIVE_SWAP_STAGES,
    NativeSwapContractError,
    canonical_digest,
    require_satisfied_stage_records,
    validate_evidence_binding,
    validate_evidence_response,
    validate_release_authorization,
    validate_release_binding,
    validate_release_boundary,
    validate_stage_records,
)


RUNTIME_DIGEST = "1" * 64
SOURCE_IDENTITY = {
    "owner_generation": 7,
    "lineage_id": "lineage-1",
    "lineage_generation": 3,
    "session_uuid": "session-1",
    "runner_incarnation": "runner-source",
    "invocation_id": "invocation-1",
}


def _digest_without(value: Mapping[str, Any], field: str) -> str:
    return canonical_digest({key: item for key, item in value.items() if key != field})


def _release_binding(*, pre_release_digest: str = "8" * 64) -> Dict[str, Any]:
    value: Dict[str, Any] = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-swap-release-binding",
        "operation_id": "swap-operation",
        "owner_generation": 7,
        "expected_daemon_id": "daemon-1",
        "participant_id": "coordinator",
        "session_id": SOURCE_IDENTITY["session_uuid"],
        "runner_incarnation": "runner-target",
        "lineage_id": SOURCE_IDENTITY["lineage_id"],
        "lineage_generation": SOURCE_IDENTITY["lineage_generation"],
        "request_epoch_id": "epoch-1",
        "release_id": "release-1",
        "release_intent_digest": "7" * 64,
        "pre_release_evidence_digest": pre_release_digest,
        "binding_digest": "",
    }
    value["binding_digest"] = _digest_without(value, "binding_digest")
    return value


def _binding(stage: str = "entry", **changes: Any) -> Dict[str, Any]:
    value: Dict[str, Any] = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-swap-evidence-request",
        "stage": stage,
        "operation_id": "swap-operation",
        "owner_generation": 7,
        "expected_daemon_id": "daemon-1",
        "source_identity": copy.deepcopy(SOURCE_IDENTITY),
        "source_context_digest": "2" * 64,
        "source_claim_digest": "3" * 64,
        "target_spec_digest": "4" * 64,
        "request_epoch_id": "epoch-1",
        "interrupt_id": None,
        "interrupt_intent_digest": None,
        "source_archive_digest": None,
        "target_runner_incarnation": None,
        "release_id": None,
        "release_intent_digest": None,
        "release_boundary": None,
    }
    if stage in NATIVE_SWAP_STAGES[1:]:
        value.update({
            "interrupt_id": "interrupt-1",
            "interrupt_intent_digest": "5" * 64,
        })
    if stage in NATIVE_SWAP_STAGES[3:]:
        value["source_archive_digest"] = "6" * 64
    if stage in NATIVE_SWAP_STAGES[3:]:
        value["target_runner_incarnation"] = "runner-target"
    if stage in NATIVE_SWAP_STAGES[4:]:
        value.update({
            "release_id": "release-1",
            "release_intent_digest": "7" * 64,
        })
    if stage == "release-boundary":
        value["release_boundary"] = {
            "binding": _release_binding(),
            "gate_event_id": "gate-1",
            "gate_watermark": 50,
        }
    value.update(changes)
    return value


def _worker_clear(binding: Mapping[str, Any], stage: str) -> Dict[str, Any] | None:
    if stage == "entry":
        return None
    return {
        "source_identity_digest": canonical_digest(binding["source_identity"]),
        "interrupt_id": binding["interrupt_id"],
        "method": "pinned-native-clear",
        "evidence_reference": "clear/" + stage,
        "observation_watermark": 10 + NATIVE_SWAP_STAGES.index(stage),
        "cleared": True,
    }


def _response(binding: Mapping[str, Any], *, new_requests: Any = 0,
              observable: bool = True, continuous: bool = True,
              clear: Any = "default") -> Dict[str, Any]:
    stage = binding["stage"]
    if clear == "default":
        clear = _worker_clear(binding, stage)
    return {
        "binding": copy.deepcopy(dict(binding)),
        "runtime_identity_digest": RUNTIME_DIGEST,
        "evidence_reference": "evidence/" + stage,
        "request_observation": {
            "epoch_id": binding["request_epoch_id"],
            "entry_evidence_ref": "epoch/entry",
            "through_evidence_ref": "epoch/" + stage,
            "observable": observable,
            "continuous": continuous,
            "new_requests": new_requests,
        },
        "worker_state_clear": clear,
    }


def _record(observation: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "observation": copy.deepcopy(dict(observation)),
        "evidence_digest": canonical_digest(observation),
    }


def _successful_stage_records() -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    for stage in NATIVE_SWAP_STAGES[:5]:
        binding = _binding(stage)
        response = _response(binding)
        normalized = validate_evidence_response(
            binding, response, runtime_identity_digest=RUNTIME_DIGEST,
            prior_records=records,
        )
        records[stage] = _record(normalized)
    pre_digest = records["pre-release"]["evidence_digest"]
    binding = _binding(
        "release-boundary",
        release_boundary={
            "binding": _release_binding(pre_release_digest=pre_digest),
            "gate_event_id": "gate-1",
            "gate_watermark": 50,
        },
    )
    response = _response(binding)
    normalized = validate_evidence_response(
        binding, response, runtime_identity_digest=RUNTIME_DIGEST,
        prior_records=records,
    )
    records["release-boundary"] = _record(normalized)
    return records


def _assert_invalid(value: Any, *, code: str | None = None) -> None:
    with pytest.raises(NativeSwapContractError) as raised:
        value()
    if code is not None:
        assert raised.value.code == code


def test_canonical_digest_is_stable_and_bounded_json_only():
    left = {"z": [1, True, None], "a": {"b": "é"}}
    right = {"a": {"b": "é"}, "z": [1, True, None]}
    assert canonical_digest(left) == canonical_digest(right)
    assert canonical_digest(left) == hashlib.sha256(
        json.dumps(left, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True, allow_nan=False).encode("utf-8")
    ).hexdigest()
    _assert_invalid(lambda: canonical_digest({1: "non-string-key"}))
    _assert_invalid(lambda: canonical_digest(float("nan")))


@pytest.mark.parametrize("field", [
    "schema_version", "architecture", "record_kind", "stage", "operation_id",
    "owner_generation", "expected_daemon_id", "source_identity",
    "source_context_digest", "source_claim_digest", "target_spec_digest",
    "request_epoch_id", "interrupt_id", "interrupt_intent_digest",
    "source_archive_digest", "target_runner_incarnation", "release_id",
    "release_intent_digest", "release_boundary",
])
def test_evidence_binding_has_closed_exact_schema(field: str):
    value = _binding()
    value.pop(field)
    _assert_invalid(lambda: validate_evidence_binding(value), code="invalid")

    value = _binding()
    value["unknown"] = True
    _assert_invalid(lambda: validate_evidence_binding(value), code="invalid")


@pytest.mark.parametrize("field", ["schema_version", "owner_generation"])
def test_evidence_binding_rejects_bool_as_integer(field: str):
    value = _binding()
    value[field] = True
    _assert_invalid(lambda: validate_evidence_binding(value), code="invalid")


@pytest.mark.parametrize("stage,field", [
    ("entry", "interrupt_id"),
    ("graph-drained", "source_archive_digest"),
    ("source-excluded", "release_id"),
    ("target-held", "release_id"),
    ("pre-release", "release_boundary"),
    ("release-boundary", "release_boundary"),
])
def test_evidence_binding_enforces_stage_identity_nullability(stage: str, field: str):
    value = _binding(stage)
    if stage == "release-boundary" and field == "release_boundary":
        value[field] = None
    elif stage != "release-boundary":
        value[field] = "forged" if field != "release_boundary" else _release_binding()
    else:
        value[field] = None
    _assert_invalid(lambda: validate_evidence_binding(value))


def test_evidence_binding_allows_reserved_target_and_deferred_source_archive():
    for stage in NATIVE_SWAP_STAGES[:3]:
        value = _binding(stage, target_runner_incarnation="runner-target")
        if stage == "source-excluded":
            assert validate_evidence_binding(value) == value
            value["source_archive_digest"] = "6" * 64
        assert validate_evidence_binding(value) == value


def test_evidence_binding_normalizes_deep_copy_and_release_boundary_binding():
    value = _binding("release-boundary")
    normalized = validate_evidence_binding(value)
    assert normalized == value
    assert normalized is not value
    assert normalized["source_identity"] is not value["source_identity"]
    value["source_identity"]["lineage_id"] = "mutated-after-validation"
    assert normalized["source_identity"]["lineage_id"] == "lineage-1"


def test_evidence_response_preserves_well_formed_negative_observations():
    binding = _binding("entry")
    response = _response(binding, observable=False, continuous=False, new_requests=None)
    normalized = validate_evidence_response(
        binding, response, runtime_identity_digest=RUNTIME_DIGEST
    )
    assert normalized["request_observation"] == response["request_observation"]
    assert normalized["worker_state_clear"] is None

    response = _response(binding, observable=True, continuous=True, new_requests=2)
    normalized = validate_evidence_response(
        binding, response, runtime_identity_digest=RUNTIME_DIGEST
    )
    assert normalized["request_observation"]["new_requests"] == 2


@pytest.mark.parametrize("field", ["binding", "runtime_identity_digest",
                                    "evidence_reference", "request_observation",
                                    "worker_state_clear"])
def test_evidence_response_has_closed_exact_schema(field: str):
    binding = _binding()
    response = _response(binding)
    response.pop(field)
    _assert_invalid(lambda: validate_evidence_response(
        binding, response, runtime_identity_digest=RUNTIME_DIGEST
    ), code="invalid")
    response = _response(binding)
    response["unknown"] = True
    _assert_invalid(lambda: validate_evidence_response(
        binding, response, runtime_identity_digest=RUNTIME_DIGEST
    ), code="invalid")


@pytest.mark.parametrize("path", [
    ("binding", "operation_id"),
    ("request_observation", "epoch_id"),
])
def test_evidence_response_rejects_tampered_identity_or_epoch(path):
    binding = _binding()
    response = _response(binding)
    response[path[0]][path[1]] = "foreign"
    _assert_invalid(lambda: validate_evidence_response(
        binding, response, runtime_identity_digest=RUNTIME_DIGEST
    ), code="stale-generation")


def test_evidence_response_rejects_tampered_entry_reference_against_history():
    records = _successful_stage_records()
    binding = _binding("target-held")
    response = _response(binding)
    response["request_observation"]["entry_evidence_ref"] = "foreign-entry"
    prior = {stage: records[stage] for stage in NATIVE_SWAP_STAGES[:3]}
    _assert_invalid(lambda: validate_evidence_response(
        binding,
        response,
        runtime_identity_digest=RUNTIME_DIGEST,
        prior_records=prior,
    ), code="stale-generation")


@pytest.mark.parametrize("path", [
    ("request_observation", "observable"),
    ("request_observation", "continuous"),
    ("request_observation", "new_requests"),
])
def test_evidence_response_rejects_wrong_observation_types(path):
    binding = _binding()
    response = _response(binding)
    response[path[0]][path[1]] = True if path[1] == "new_requests" else 1
    _assert_invalid(lambda: validate_evidence_response(
        binding, response, runtime_identity_digest=RUNTIME_DIGEST
    ), code="invalid")


def test_evidence_response_requires_worker_clear_after_entry_and_binds_identity():
    binding = _binding("graph-drained")
    response = _response(binding, clear=None)
    _assert_invalid(lambda: validate_evidence_response(
        binding, response, runtime_identity_digest=RUNTIME_DIGEST
    ))
    response = _response(binding)
    response["worker_state_clear"]["interrupt_id"] = "foreign-interrupt"
    _assert_invalid(lambda: validate_evidence_response(
        binding, response, runtime_identity_digest=RUNTIME_DIGEST
    ), code="stale-generation")


def test_release_binding_digest_excludes_itself_and_boundary_is_exact():
    binding = _release_binding()
    assert validate_release_binding(binding) == binding
    tampered = copy.deepcopy(binding)
    tampered["binding_digest"] = "0" * 64
    _assert_invalid(lambda: validate_release_binding(tampered), code="stale-generation")

    receipt = {
        "binding": binding,
        "gate_event_id": "gate-1",
        "gate_watermark": 50,
    }
    assert validate_release_boundary(receipt) == receipt
    receipt["gate_watermark"] = True
    _assert_invalid(lambda: validate_release_boundary(receipt), code="invalid")
    receipt["gate_watermark"] = 50
    receipt["extra"] = "nope"
    _assert_invalid(lambda: validate_release_boundary(receipt), code="invalid")


def test_release_boundary_expected_binding_is_exact():
    expected = _release_binding()
    receipt = {
        "binding": copy.deepcopy(expected),
        "gate_event_id": "gate-1",
        "gate_watermark": 50,
    }
    assert validate_release_boundary(receipt, expected_binding=expected) == receipt
    altered = copy.deepcopy(receipt)
    altered["binding"]["release_id"] = "foreign-release"
    altered["binding"]["binding_digest"] = _digest_without(
        altered["binding"], "binding_digest"
    )
    _assert_invalid(lambda: validate_release_boundary(
        altered, expected_binding=expected
    ), code="stale-generation")


def test_release_authorization_accepts_positive_and_observational_duplicate():
    binding = _release_binding()
    for authorized in (True, False):
        value = {
            "validation_id": "validation-1",
            "authorized": authorized,
            "authorization_id": "authorization-1",
            "binding": copy.deepcopy(binding),
            "authorization_digest": "",
        }
        value["authorization_digest"] = _digest_without(
            value, "authorization_digest"
        )
        assert validate_release_authorization(
            value,
            expected_validation_id="validation-1",
            expected_binding=binding,
        ) == value


@pytest.mark.parametrize("field", [
    "validation_id", "authorized", "authorization_id", "binding",
    "authorization_digest",
])
def test_release_authorization_is_closed_and_bound(field: str):
    binding = _release_binding()
    value = {
        "validation_id": "validation-1",
        "authorized": True,
        "authorization_id": "authorization-1",
        "binding": copy.deepcopy(binding),
        "authorization_digest": "",
    }
    value["authorization_digest"] = _digest_without(
        value, "authorization_digest"
    )
    value.pop(field)
    _assert_invalid(lambda: validate_release_authorization(
        value,
        expected_validation_id="validation-1",
        expected_binding=binding,
    ), code="invalid")
    value = {
        "validation_id": "validation-1",
        "authorized": True,
        "authorization_id": "authorization-1",
        "binding": copy.deepcopy(binding),
        "authorization_digest": "0" * 64,
        "extra": "unsupported",
    }
    _assert_invalid(lambda: validate_release_authorization(
        value,
        expected_validation_id="validation-1",
        expected_binding=binding,
    ), code="invalid")


def test_release_authorization_rejects_tampered_identity_or_digest():
    binding = _release_binding()
    value = {
        "validation_id": "validation-1",
        "authorized": True,
        "authorization_id": "authorization-1",
        "binding": copy.deepcopy(binding),
        "authorization_digest": "",
    }
    value["authorization_digest"] = _digest_without(
        value, "authorization_digest"
    )
    foreign = copy.deepcopy(value)
    foreign["validation_id"] = "validation-foreign"
    foreign["authorization_digest"] = _digest_without(
        foreign, "authorization_digest"
    )
    _assert_invalid(lambda: validate_release_authorization(
        foreign,
        expected_validation_id="validation-1",
        expected_binding=binding,
    ), code="stale-generation")

    foreign = copy.deepcopy(value)
    foreign["binding"] = _release_binding()
    foreign["binding"]["release_id"] = "release-foreign"
    foreign["binding"]["binding_digest"] = _digest_without(
        foreign["binding"], "binding_digest"
    )
    foreign["authorization_digest"] = _digest_without(
        foreign, "authorization_digest"
    )
    _assert_invalid(lambda: validate_release_authorization(
        foreign,
        expected_validation_id="validation-1",
        expected_binding=binding,
    ), code="stale-generation")


def test_validate_successful_append_only_six_stage_sequence():
    records = _successful_stage_records()
    normalized = validate_stage_records(records, runtime_identity_digest=RUNTIME_DIGEST)
    assert tuple(normalized) == NATIVE_SWAP_STAGES
    assert all(set(item) == {"observation", "evidence_digest"}
               for item in normalized.values())
    require_satisfied_stage_records(
        normalized, runtime_identity_digest=RUNTIME_DIGEST,
    )


def test_first_response_must_begin_at_entry():
    binding = _binding("graph-drained")
    response = _response(binding)
    _assert_invalid(lambda: validate_evidence_response(
        binding, response, runtime_identity_digest=RUNTIME_DIGEST,
    ), code="stale-generation")


def test_satisfaction_gate_accepts_exact_prefix_through_stage():
    records = _successful_stage_records()
    prefix = {
        stage: records[stage] for stage in NATIVE_SWAP_STAGES[:4]
    }
    require_satisfied_stage_records(
        prefix,
        runtime_identity_digest=RUNTIME_DIGEST,
        through_stage="target-held",
    )
    _assert_invalid(lambda: require_satisfied_stage_records(
        prefix,
        runtime_identity_digest=RUNTIME_DIGEST,
        through_stage="pre-release",
    ), code="unsupported")


def test_satisfaction_gate_requires_independent_runtime_pin():
    records = _successful_stage_records()
    _assert_invalid(lambda: require_satisfied_stage_records(
        records,
        runtime_identity_digest="9" * 64,
    ), code="stale-generation")


@pytest.mark.parametrize("stages", [
    ("graph-drained",),
    ("entry", "source-excluded"),
    ("entry", "graph-drained", "target-held"),
])
def test_stage_records_require_contiguous_append_only_prefix(stages):
    records = _successful_stage_records()
    candidate = {stage: records[stage] for stage in stages}
    _assert_invalid(lambda: validate_stage_records(
        candidate, runtime_identity_digest=RUNTIME_DIGEST
    ))


def test_stage_records_rejects_digest_tampering_and_stage_mismatch():
    records = _successful_stage_records()
    tampered = copy.deepcopy(records)
    tampered["graph-drained"]["evidence_digest"] = "0" * 64
    _assert_invalid(lambda: validate_stage_records(
        tampered, runtime_identity_digest=RUNTIME_DIGEST
    ), code="stale-generation")

    tampered = copy.deepcopy(records)
    tampered["graph-drained"]["observation"]["binding"]["stage"] = "source-excluded"
    tampered["graph-drained"]["evidence_digest"] = canonical_digest(
        tampered["graph-drained"]["observation"]
    )
    _assert_invalid(lambda: validate_stage_records(
        tampered, runtime_identity_digest=RUNTIME_DIGEST
    ), code="stale-generation")


@pytest.mark.parametrize("field", ["operation_id", "request_epoch_id",
                                    "source_context_digest", "target_spec_digest"])
def test_stage_records_reject_immutable_binding_tamper(field: str):
    records = _successful_stage_records()
    tampered = copy.deepcopy(records)
    tampered["target-held"]["observation"]["binding"][field] = (
        "foreign" if field in {"operation_id", "request_epoch_id"} else "9" * 64
    )
    tampered["target-held"]["evidence_digest"] = canonical_digest(
        tampered["target-held"]["observation"]
    )
    _assert_invalid(lambda: validate_stage_records(
        tampered, runtime_identity_digest=RUNTIME_DIGEST
    ), code="stale-generation")


def test_stage_records_reject_bound_identity_rewrite_after_first_observation():
    records = _successful_stage_records()
    tampered = copy.deepcopy(records)
    tampered["pre-release"]["observation"]["binding"][
        "target_runner_incarnation"
    ] = "runner-foreign"
    tampered["pre-release"]["evidence_digest"] = canonical_digest(
        tampered["pre-release"]["observation"]
    )
    _assert_invalid(lambda: validate_stage_records(
        tampered, runtime_identity_digest=RUNTIME_DIGEST
    ), code="stale-generation")


def test_stage_records_keep_negative_observation_until_satisfaction_gate():
    records = _successful_stage_records()
    negative = copy.deepcopy(records)
    observation = negative["graph-drained"]["observation"]
    observation["request_observation"].update({
        "observable": False,
        "continuous": False,
        "new_requests": None,
    })
    negative["graph-drained"]["evidence_digest"] = canonical_digest(observation)
    normalized = validate_stage_records(
        negative, runtime_identity_digest=RUNTIME_DIGEST
    )
    assert normalized["graph-drained"]["observation"]["request_observation"][
        "new_requests"
    ] is None
    _assert_invalid(lambda: require_satisfied_stage_records(
        normalized, runtime_identity_digest=RUNTIME_DIGEST,
    ),
                    code="uncertain-effect")

    positive = copy.deepcopy(records)
    positive["graph-drained"]["observation"]["request_observation"][
        "new_requests"
    ] = 1
    positive["graph-drained"]["evidence_digest"] = canonical_digest(
        positive["graph-drained"]["observation"]
    )
    normalized = validate_stage_records(
        positive, runtime_identity_digest=RUNTIME_DIGEST
    )
    _assert_invalid(lambda: require_satisfied_stage_records(
        normalized, runtime_identity_digest=RUNTIME_DIGEST,
    ),
                    code="uncertain-effect")

    uncleared = copy.deepcopy(records)
    uncleared["target-held"]["observation"]["worker_state_clear"]["cleared"] = False
    uncleared["target-held"]["evidence_digest"] = canonical_digest(
        uncleared["target-held"]["observation"]
    )
    normalized = validate_stage_records(
        uncleared, runtime_identity_digest=RUNTIME_DIGEST
    )
    assert normalized["target-held"]["observation"]["worker_state_clear"][
        "cleared"
    ] is False
    _assert_invalid(lambda: require_satisfied_stage_records(
        normalized, runtime_identity_digest=RUNTIME_DIGEST,
    ),
                    code="uncertain-effect")


def test_stage_records_reject_source_watermark_regression():
    records = _successful_stage_records()
    tampered = copy.deepcopy(records)
    clear = tampered["target-held"]["observation"]["worker_state_clear"]
    clear["observation_watermark"] = 10
    tampered["target-held"]["evidence_digest"] = canonical_digest(
        tampered["target-held"]["observation"]
    )
    _assert_invalid(lambda: validate_stage_records(
        tampered, runtime_identity_digest=RUNTIME_DIGEST,
    ), code="stale-generation")


def test_stage_records_reject_runtime_identity_change_and_response_digest_size():
    records = _successful_stage_records()
    tampered = copy.deepcopy(records)
    tampered["source-excluded"]["observation"]["runtime_identity_digest"] = "9" * 64
    tampered["source-excluded"]["evidence_digest"] = canonical_digest(
        tampered["source-excluded"]["observation"]
    )
    _assert_invalid(lambda: validate_stage_records(
        tampered, runtime_identity_digest=RUNTIME_DIGEST
    ), code="stale-generation")

    huge = copy.deepcopy(records)
    huge["entry"]["observation"]["evidence_reference"] = "x" * (64 * 1024)
    huge["entry"]["evidence_digest"] = canonical_digest(
        huge["entry"]["observation"]
    )
    _assert_invalid(lambda: validate_stage_records(
        huge, runtime_identity_digest=RUNTIME_DIGEST
    ))


def test_stage_records_rejects_complete_ledger_over_one_mib():
    records = _successful_stage_records()
    for index, stage in enumerate(NATIVE_SWAP_STAGES):
        records[stage]["observation"]["evidence_reference"] = (
            "evidence/" + ("x" * (180_000 + index))
        )
        records[stage]["evidence_digest"] = canonical_digest(
            records[stage]["observation"]
        )
    _assert_invalid(lambda: validate_stage_records(
        records, runtime_identity_digest=RUNTIME_DIGEST
    ))
