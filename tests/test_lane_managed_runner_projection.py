# SPDX-License-Identifier: Apache-2.0
"""Contract tests for the canonical SDK runner projection boundary.

These tests stay at the controller's pure projection seam.  They do not open a
runner or write controller state; the returned mapping is the only candidate
for durable runner data.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Mapping

import pytest

from lane_managed_controller import (
    ControllerError,
    _SAFE_RUNNER_KEYS,
    _contains_secret_key,
    _safe_runner_projection,
)
from lane_managed_sdk import RunnerSpec


NON_DURABLE_DEFAULT_FIELDS = frozenset(
    {
        "environment",
        "settings",
        "extra_args",
        "strict_mcp_config",
        "startup_deadline",
        "operation_deadline",
        "frame_limit",
        "allowed_tools",
        "read_only_tools",
        "read_only",
        "disallowed_tools",
        "add_dirs",
        "setting_sources",
        "max_buffer_size",
        "role",
        "parent_id",
        "task_id",
    }
)

MODEL = "claude-sonnet-4-20250514"


def _runner_spec(**overrides: Any) -> RunnerSpec:
    values = {
        "session_id": "native-session",
        "account_email": "operator@example.invalid",
        "permission_mode": "default",
        "model": MODEL,
        "fingerprint": {
            "workspace": "/managed/workspace",
            "profile": "target",
        },
        "config_dir": "/managed/config",
        "cwd": "/managed/workspace",
        "session_name": "managed-coordinator",
        "bound_lane": "build",
        "participant_id": "coordinator",
    }
    values.update(overrides)
    return RunnerSpec(**values)


def _mapping_base() -> dict[str, Any]:
    """Return a valid raw mapping without typed-only transport fields."""
    return {
        "participant_id": "coordinator",
        "session_id": "native-session",
        "session_name": "managed-coordinator",
        "bound_lane": "build",
        "mode": "resume",
        "account_email": "operator@example.invalid",
        "permission_mode": "default",
        "model": MODEL,
        "fingerprint": {
            "workspace": "/managed/workspace",
            "profile": "target",
        },
    }


def _expected_typed_projection(spec: RunnerSpec) -> dict[str, Any]:
    raw = spec.to_dict()
    return {
        key: copy.deepcopy(value)
        for key, value in raw.items()
        if key in _SAFE_RUNNER_KEYS
        and (key != "supported_models" or bool(value))
    }


def _assert_refusal(raised: pytest.ExceptionInfo[ControllerError], code: str) -> None:
    assert raised.value.code == code


def test_exact_canonical_runner_defaults_project_only_durable_fields():
    spec = _runner_spec()
    raw = spec.to_dict()

    assert NON_DURABLE_DEFAULT_FIELDS.issubset(raw)
    projected = _safe_runner_projection(spec, "canonical runner")

    assert projected == _expected_typed_projection(spec)
    assert NON_DURABLE_DEFAULT_FIELDS.isdisjoint(projected)
    assert _contains_secret_key(projected) is None
    assert json.loads(json.dumps(projected, sort_keys=True)) == projected


def test_exact_runner_constructor_canonicalizes_default_types_before_projection():
    spec = _runner_spec(
        startup_deadline=5,
        operation_deadline=120,
        strict_mcp_config=True,
    )

    # The SDK intentionally normalizes the numeric deadlines.  Assertions use
    # the post-init representation, rather than rejecting the input integer.
    assert spec.startup_deadline == 5.0
    assert type(spec.startup_deadline) is float
    assert spec.operation_deadline == 120.0
    assert type(spec.operation_deadline) is float
    assert spec.strict_mcp_config is True
    assert type(spec.strict_mcp_config) is bool
    assert _safe_runner_projection(spec, "canonicalized runner") == (
        _expected_typed_projection(spec)
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("environment", {"MANAGED_TEST": "value"}),
        ("settings", "managed-settings.json"),
        ("extra_args", {"--managed-test": "value"}),
        ("strict_mcp_config", False),
        ("startup_deadline", 6.0),
        ("operation_deadline", 121.0),
        ("frame_limit", 65536),
        ("allowed_tools", ("Read",)),
        ("read_only_tools", ("Read",)),
        ("read_only", True),
        ("disallowed_tools", ("Write",)),
        ("add_dirs", ("/managed/extra",)),
        ("setting_sources", ("user",)),
        ("max_buffer_size", 1024),
        ("role", "worker"),
        ("parent_id", "parent"),
        ("task_id", "task"),
    ],
)
def test_exact_runner_nondefault_transport_field_refuses_instead_of_dropping(
        field_name: str, value: Any,
):
    spec = _runner_spec(**{field_name: value})
    before = copy.deepcopy(spec.to_dict())

    with pytest.raises(ControllerError) as raised:
        _safe_runner_projection(spec, "non-default runner")

    _assert_refusal(raised, "unsupported")
    assert spec.to_dict() == before


def test_strict_mcp_integer_one_does_not_compare_equal_to_default_boolean():
    spec = _runner_spec(strict_mcp_config=1)

    # Python considers 1 == True, but these are distinct serialized SDK
    # values.  The adapter's canonical comparison must preserve that type.
    assert type(spec.strict_mcp_config) is int
    assert spec.strict_mcp_config == 1
    assert spec.strict_mcp_config == True  # noqa: E712 - intentional contrast

    with pytest.raises(ControllerError) as raised:
        _safe_runner_projection(spec, "bool-confused runner")

    _assert_refusal(raised, "unsupported")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("environment", {}),
        ("environment", None),
        ("env", {}),
        ("env", None),
        ("settings", {}),
        ("settings", None),
        ("extra_args", {}),
        ("strict_mcp_config", True),
        ("startup_deadline", 5.0),
    ],
)
def test_raw_mapping_cannot_use_typed_default_exemption(
        key: str, value: Any,
):
    mapping = _mapping_base()
    mapping[key] = value
    before = copy.deepcopy(mapping)

    with pytest.raises(ControllerError) as raised:
        _safe_runner_projection(mapping, "raw runner mapping")

    _assert_refusal(raised, "unsupported")
    assert mapping == before


def test_valid_supported_models_are_retained_for_exact_typed_runner():
    spec = _runner_spec(supported_models=("model-a", "model-b"))
    serialized = spec.to_dict()

    assert type(spec.supported_models) is tuple
    assert serialized["supported_models"] == ["model-a", "model-b"]
    projected = _safe_runner_projection(spec, "typed models runner")
    assert projected["supported_models"] == ["model-a", "model-b"]


def test_typed_supported_models_uses_post_init_canonical_serialization():
    # A string is an SDK-supported shorthand and is canonicalized to a
    # one-element tuple before the adapter validates the serialized value.
    spec = _runner_spec(supported_models="model-a")

    assert spec.supported_models == ("model-a",)
    assert spec.to_dict()["supported_models"] == ["model-a"]
    assert _safe_runner_projection(spec, "canonical model shorthand")[
        "supported_models"
    ] == ["model-a"]


def test_valid_supported_models_are_retained_for_raw_mapping():
    mapping = _mapping_base()
    mapping["supported_models"] = ["model-a", "model-b"]

    projected = _safe_runner_projection(mapping, "mapped models runner")

    assert projected["supported_models"] == ["model-a", "model-b"]
    assert "supported_models" in projected


@pytest.mark.parametrize(
    "supported_models",
    [
        "model-a",
        [""],
        ["model-a", ""],
        ["model-a", 1],
        [None],
        {"model": "model-a"},
        [True],
    ],
)
def test_malformed_supported_models_in_raw_mapping_refuse(
        supported_models: Any,
):
    mapping = _mapping_base()
    mapping["supported_models"] = supported_models

    with pytest.raises(ControllerError) as raised:
        _safe_runner_projection(mapping, "malformed mapped models")

    _assert_refusal(raised, "invalid")


def test_malformed_supported_models_in_canonical_serialization_refuse():
    spec = _runner_spec(supported_models=("model-a",))

    # Keep the exact SDK type but exercise the adapter against a malformed
    # value that remains malformed in the SDK's own wire serialization.  This
    # is distinct from constructor inputs that the SDK intentionally normalizes.
    object.__setattr__(spec, "supported_models", ("model-a", 7))
    assert spec.to_dict()["supported_models"] == ["model-a", 7]

    with pytest.raises(ControllerError) as raised:
        _safe_runner_projection(spec, "malformed typed models")

    _assert_refusal(raised, "invalid")


def test_nested_secret_in_typed_fingerprint_never_reaches_projection():
    spec = _runner_spec(
        fingerprint={
            "workspace": "/managed/workspace",
            "nested": {"credential_fingerprint": {"access_token": "secret"}},
        }
    )

    with pytest.raises(ControllerError) as raised:
        _safe_runner_projection(spec, "nested-secret runner")

    _assert_refusal(raised, "unsupported")


def test_nested_secret_in_raw_fingerprint_never_reaches_projection():
    mapping = _mapping_base()
    mapping["fingerprint"] = {
        "native": {"credentials": {"api_key": "secret"}},
    }
    before = copy.deepcopy(mapping)

    with pytest.raises(ControllerError) as raised:
        _safe_runner_projection(mapping, "nested-secret mapping")

    _assert_refusal(raised, "unsupported")
    assert mapping == before


@dataclass(frozen=True)
class _RunnerSpecSubclass(RunnerSpec):
    pass


@dataclass(frozen=True)
class _RunnerSpecLookalike:
    session_id: str = "native-session"

    def to_dict(self) -> dict[str, Any]:
        return {"session_id": self.session_id}


@pytest.mark.parametrize(
    "value",
    [_RunnerSpecSubclass(), _RunnerSpecLookalike()],
)
def test_runner_spec_subclasses_and_lookalike_dataclasses_get_no_exemption(
        value: Any,
):
    with pytest.raises(ControllerError) as raised:
        _safe_runner_projection(value, "non-canonical runner")

    _assert_refusal(raised, "invalid")


def test_projection_rejection_preserves_all_raw_input_without_durable_effects():
    mapping = _mapping_base()
    mapping["environment"] = {}
    mapping["fingerprint"]["nested"] = {"token": "must-not-persist"}
    before = copy.deepcopy(mapping)

    with pytest.raises(ControllerError) as raised:
        _safe_runner_projection(mapping, "rejected runner")

    _assert_refusal(raised, "unsupported")
    assert mapping == before
    assert "must-not-persist" in json.dumps(mapping, sort_keys=True)
