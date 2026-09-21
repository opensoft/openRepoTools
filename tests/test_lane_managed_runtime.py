# SPDX-License-Identifier: Apache-2.0
"""Runtime identity and Gate 0 refusal tests.

These tests use a disposable executable and an SDK-shaped transport seam.  No
credential, account, network, or official runtime connection is exercised.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from lane_managed_sdk import (
    CapabilityDecision,
    RunnerSpec,
    SdkAdapterError,
    assess_held_swap,
    drive_client,
    preflight_held_swap,
    resolve_runtime_identity,
)


SESSION_ID = "11111111-1111-4111-8111-111111111111"
MODEL = "claude-sonnet-4-20250514"


def _spec(tmp_path: Path, **overrides) -> RunnerSpec:
    values = {
        "session_id": SESSION_ID,
        "mode": "fresh",
        "model": MODEL,
        "supported_models": (MODEL,),
        "permission_mode": "default",
        "config_dir": tmp_path / "config",
        "cwd": tmp_path,
        "fingerprint": {"model": MODEL, "permission_mode": "default"},
        "environment": {"PATH": os.environ.get("PATH", "/usr/bin")},
    }
    values.update(overrides)
    return RunnerSpec(**values)


def _sdk(cli_path: Path, sdk_path: Path):
    class Options:
        def __init__(self, **values):
            self.__dict__.update(values)

    class Transport:
        instances = []

        def __init__(self, prompt, options):
            assert hasattr(prompt, "__aiter__"), "identity must use connect(None)'s empty stream"
            self.prompt = prompt
            self.options = options
            self._cli_path = None
            self._is_streaming = True
            self.find_calls = 0
            type(self).instances.append(self)

        def _find_cli(self):
            self.find_calls += 1
            return str(cli_path)

        def _build_command(self):
            return [
                str(cli_path),
                "--output-format",
                "stream-json",
                "--input-format",
                "stream-json",
            ]

    return SimpleNamespace(
        __name__="fake_claude_agent_sdk",
        __version__="0.2.153",
        __file__=str(sdk_path),
        ClaudeAgentOptions=Options,
        SubprocessCLITransport=Transport,
        ClaudeSDKClient=object,
    ), Transport


def _identity(tmp_path: Path):
    cli = tmp_path / "claude"
    cli.write_text("#!/bin/sh\nprintf '2.1.273\\n'\n", encoding="utf-8")
    cli.chmod(0o700)
    sdk_path = tmp_path / "fake_sdk.py"
    sdk_path.write_text("# test SDK seam\n", encoding="utf-8")
    sdk, transport = _sdk(cli, sdk_path)
    identity = resolve_runtime_identity(_spec(tmp_path), sdk_module=sdk)
    return identity, sdk, transport


def _verified_record(identity):
    return {
        "schema": "lane-managed-gate0/v1",
        "authority": "lane-managed-internal",
        "evidence_reference": "gate0/probe-1",
        "identity": identity.to_dict(),
        "identity_digest": identity.identity_digest,
        "probe_validity": {
            "identity_match": "observed",
            "instrumentation": "observed",
            "bounded_observation": "observed",
            "observation_complete": "observed",
            "isolation": "observed",
            "cleanup": "observed",
        },
        "startup": {"held_before_dispatch": "observed"},
        "positive_orphan": {
            "record_loaded": "observed",
            "notification_enqueued": "observed",
            "wake_observed": "observed",
            "model_dispatch_attempt": "observed",
        },
        "terminal_cleared": {
            "source_terminal_stop": "observed",
            "worker_state_cleared": "observed",
            "target_connect": "observed",
            "restored_orphans": 0,
            "wake": "not-observed",
            "enqueue": "not-observed",
            "model_dispatch": "not-observed",
            "pre_release_model_requests": 0,
        },
    }


def test_runtime_identity_uses_lazy_sdk_selection_and_reports_exact_binary(tmp_path):
    identity, _sdk_module, transport_type = _identity(tmp_path)

    assert identity.sdk_version == "0.2.153"
    assert identity.cli_version == "2.1.273"
    assert identity.cli_path == str((tmp_path / "claude").resolve())
    assert identity.cli_sha256 == hashlib.sha256((tmp_path / "claude").read_bytes()).hexdigest()
    assert identity.mode == "stream-json"
    assert identity.platform
    assert len(identity.config_digest) == 64
    assert len(identity.identity_digest) == 64
    assert transport_type.instances[-1]._cli_path is None
    assert transport_type.instances[-1].find_calls == 1


def test_missing_gate0_evidence_is_inconclusive_even_when_fingerprint_claims_verified(tmp_path):
    identity, sdk_module, _transport = _identity(tmp_path)
    spec = _spec(
        tmp_path,
        fingerprint={
            "model": MODEL,
            "permission_mode": "default",
            "capability": {"verdict": "verified", "identity_digest": identity.identity_digest},
        },
    )

    decision = preflight_held_swap(spec, None, sdk_module=sdk_module)

    assert isinstance(decision, CapabilityDecision)
    assert decision.verdict == "inconclusive"
    assert decision.reason_code == "gate0-evidence-missing"
    assert decision.identity_digest == identity.identity_digest


def test_unexercised_controls_keep_gate_inconclusive(tmp_path):
    identity, _sdk_module, _transport = _identity(tmp_path)
    record = {
        "schema": "lane-managed-gate0/v1",
        "authority": "lane-managed-internal",
        "evidence_reference": "gate0/baseline",
        "identity": identity.to_dict(),
        "identity_digest": identity.identity_digest,
        "probe_validity": {
            "identity_match": "observed",
            "instrumentation": "observed",
            "bounded_observation": "observed",
            "observation_complete": "observed",
            "isolation": "observed",
            "cleanup": "observed",
        },
        "startup": {"held_before_dispatch": "observed"},
        "positive_orphan": {
            "record_loaded": "not-exercised",
            "notification_enqueued": "not-exercised",
            "wake_observed": "not-exercised",
            "model_dispatch_attempt": "unknown",
        },
        "terminal_cleared": {"source_terminal_stop": "not-exercised"},
    }

    decision = assess_held_swap(identity, record)

    assert decision.verdict == "inconclusive"
    assert decision.reason_code == "orphan-positive-control-unreachable"


def test_probe_validity_is_required_before_a_verified_decision(tmp_path):
    identity, _sdk_module, _transport = _identity(tmp_path)
    record = _verified_record(identity)
    del record["probe_validity"]

    decision = assess_held_swap(identity, record)

    assert decision.verdict == "inconclusive"
    assert decision.reason_code == "probe-validity-missing"


def test_noncanonical_evidence_alias_cannot_verify_runtime(tmp_path):
    identity, _sdk_module, _transport = _identity(tmp_path)
    record = _verified_record(identity)
    record["terminal_cleared"]["restoredOrphans"] = record["terminal_cleared"].pop("restored_orphans")

    decision = assess_held_swap(identity, record)

    assert decision.verdict == "inconclusive"
    assert decision.reason_code == "evidence-fields-unknown"


@pytest.mark.parametrize("value", [False, True, 0.5, "0", -1, None])
def test_restored_orphan_count_requires_exact_nonnegative_int(tmp_path, value):
    identity, _sdk_module, _transport = _identity(tmp_path)
    record = _verified_record(identity)
    record["terminal_cleared"]["restored_orphans"] = value

    decision = assess_held_swap(identity, record)

    assert decision.verdict == "inconclusive"
    assert decision.reason_code == "target-orphan-state-unknown"


@pytest.mark.parametrize("value", [False, True, 0.5, "0", -1, None])
def test_model_request_count_requires_exact_nonnegative_int(tmp_path, value):
    identity, _sdk_module, _transport = _identity(tmp_path)
    record = _verified_record(identity)
    record["terminal_cleared"]["pre_release_model_requests"] = value

    decision = assess_held_swap(identity, record)

    assert decision.verdict == "inconclusive"
    assert decision.reason_code == "target-model-dispatch-unknown"


def test_mismatched_identity_is_inconclusive(tmp_path):
    identity, _sdk_module, _transport = _identity(tmp_path)
    record = _verified_record(identity)
    record["identity_digest"] = "0" * 64

    decision = assess_held_swap(identity, record)

    assert decision.verdict == "inconclusive"
    assert decision.reason_code == "runtime-identity-mismatch"


@pytest.mark.parametrize("conflict", ["nested-identity", "wake-alias"])
def test_capability_evidence_cannot_mask_conflicting_fields(tmp_path, conflict):
    identity, _sdk_module, _transport = _identity(tmp_path)
    record = _verified_record(identity)
    if conflict == "nested-identity":
        record["identity"]["cli_sha256"] = "0" * 64
    else:
        record["terminal_cleared"]["orphan_wake"] = "observed"
    decision = assess_held_swap(identity, record)
    assert decision.verdict == "inconclusive"


def test_official_startup_gate_refuses_before_constructing_client(tmp_path):
    identity, sdk_module, _transport = _identity(tmp_path)
    constructed = []

    class Client:
        def __init__(self, _options):
            constructed.append(True)

    sdk_module.ClaudeSDKClient = Client

    async def scenario():
        with pytest.raises(SdkAdapterError) as caught:
            await drive_client(
                _spec(tmp_path),
                sdk_module=sdk_module,
                require_live_capability=True,
            )
        assert caught.value.code == "live-unverified"
        assert "gate0-evidence-missing" in str(caught.value)

    import asyncio

    asyncio.run(scenario())
    assert constructed == []
    assert identity.identity_digest


@pytest.mark.parametrize("use_loader", [False, True])
def test_official_shaped_module_without_version_is_gated_by_default(tmp_path, use_loader):
    _identity_value, sdk_module, _transport = _identity(tmp_path)
    sdk_module.__name__ = "claude_agent_sdk"
    delattr(sdk_module, "__version__")
    constructed = []

    class Client:
        def __init__(self, _options):
            constructed.append(True)

    sdk_module.ClaudeSDKClient = Client

    async def scenario():
        kwargs = {"sdk_loader": lambda: sdk_module} if use_loader else {"sdk_module": sdk_module}
        with pytest.raises(SdkAdapterError) as caught:
            await drive_client(_spec(tmp_path), **kwargs)
        assert caught.value.code == "live-unverified"

    import asyncio

    asyncio.run(scenario())
    assert constructed == []
