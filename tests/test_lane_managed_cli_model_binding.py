# SPDX-License-Identifier: Apache-2.0
"""Offline checks for explicit model binding; no provider request is made."""

import json
import runpy
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

import lane_managed_cli_control as control
from lane_managed_cli_control import LaneCliControlService
from lane_managed_cli_runtime import (MODEL_SCHEMA, SCHEMA, create_runtime_launch,
                                      validate_runtime_launch)
from lane_managed_state import ManagedStateError
from test_lane_managed_cli_vertical import LANE, PARENT, REPO, _fixture


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True) + "\n")
    path.chmod(0o600)


def _launch(tmp_path: Path, fixture: dict, model: str | None) -> dict:
    runtime_root = tmp_path / "runtimes"
    runtime_root.mkdir(mode=0o700)
    credential = tmp_path / "job-credential.json"
    credential.write_text("{}\n")
    credential.chmod(0o600)
    admissions = tmp_path / "admissions"
    admissions.mkdir(mode=0o700)
    return create_runtime_launch(
        root=str(runtime_root), runtime_id="22222222-2222-4222-8222-222222222222",
        parent_uuid=PARENT, profile_ref="team-a",
        profile_config_dir=str(fixture["profiles"] / "profiles" / "team-a"),
        session_name=LANE, cwd=str(fixture["nested"]),
        mcp_bridge_module=str(REPO / "lane_managed_local_jobs.py"),
        custodian_dir=str(admissions / "source-custodian"),
        job_socket=str(tmp_path / "jobs.sock"), job_credential_file=str(credential),
        launch_mode="fresh", claude_executable=str(fixture["fake"]), model=model,
    )


@pytest.mark.parametrize("selection,mutation,valid", [
    (None, None, True),
    ("sonnet", None, True),
    ("sonnet", "null-model", False),
    ("sonnet", "unsupported-model", False),
    ("sonnet", "argv", False),
])
def test_runtime_manifest_validation_preserves_v1_and_binds_explicit_model(
        tmp_path, selection, mutation, valid):
    fixture = _fixture(tmp_path)
    manifest = _launch(tmp_path, fixture, selection)
    if selection is None:
        assert manifest["schema"] == SCHEMA
        assert "model" not in manifest
        assert "--model" not in manifest["argv"]
    else:
        assert manifest["schema"] == MODEL_SCHEMA
        assert manifest["model"] == "sonnet"
        assert manifest["argv"][1:3] == ["--model", "sonnet"]

    if mutation == "null-model":
        manifest["model"] = None
    elif mutation == "unsupported-model":
        manifest["model"] = "opus"
    elif mutation == "argv":
        del manifest["argv"][1:3]
    if mutation:
        _write_json(Path(manifest["settings_path"]).parent / "manifest.json", manifest)

    if valid:
        assert validate_runtime_launch(manifest) == manifest
    else:
        with pytest.raises(ManagedStateError):
            validate_runtime_launch(manifest)


def test_source_target_model_propagation_and_reuse_binding(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    profiles = {
        name: SimpleNamespace(name=name, email=name + "@example.invalid",
                              config_dir=fixture["profiles"] / "profiles" / name)
        for name in ("team-a", "team-b")
    }

    class ProfileResolver:
        def resolve(self, name):
            return profiles[name]

        def require_same_family(self, _source, target):
            return profiles[target] if isinstance(target, str) else target

        def verify_transcript(self, *_args):
            return {"transcript": {"exists": True}}

    class FakeStore:
        identity = SimpleNamespace(lane=LANE, common_dir=fixture["wip"] / ".git")

        def enroll_managed(self, *_args, **_kwargs):
            return {"generation": 1}

        def claim_lineage_workspace(self, **_kwargs):
            return {"generation": 1}

    class FakeThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            pass

        def is_alive(self):
            return True

    service = LaneCliControlService.__new__(LaneCliControlService)
    service.config_file = tmp_path / "state" / "session.json"
    service.config_file.parent.mkdir(mode=0o700)
    service.env = fixture["env"]
    service.profile_resolver = ProfileResolver()
    service.store = FakeStore()
    service.domain = SimpleNamespace(assert_ready=lambda: None)
    service._job_thread = None
    service.job_service = SimpleNamespace(serve_forever=lambda: None)
    service.incarnation = "model-test-incarnation"
    service.runtimes = tmp_path / "state" / "runtimes"
    service.runtimes.mkdir(mode=0o700)
    service.admissions = tmp_path / "state" / "admissions"
    service.admissions.mkdir(mode=0o700)
    service.job_credentials = tmp_path / "state" / "job-credentials"
    service.job_credentials.mkdir(mode=0o700)
    service.job_socket = tmp_path / "state" / "jobs.sock"
    job_server = socket.socket(socket.AF_UNIX)
    job_server.bind(str(service.job_socket))

    class FakeVerifier:
        def issue_credential(self, path, *, parent_uuid, claim_generation,
                             runtime_incarnation):
            _write_json(path, {"parent_uuid": parent_uuid,
                               "claim_generation": claim_generation,
                               "runtime_incarnation": runtime_incarnation})

    service.verifier = FakeVerifier()
    source_observed = {}
    target_observed = {}

    def build_manifest(**kwargs):
        value = {"schema": MODEL_SCHEMA, "model": kwargs.get("model"),
                 "runtime_id": kwargs["runtime_id"],
                 "parent_uuid": kwargs["parent_uuid"],
                 "profile_ref": kwargs["profile_ref"], "cwd": kwargs["cwd"],
                 "launch_mode": kwargs["launch_mode"],
                 "session_name": kwargs["session_name"],
                 "custodian_dir": kwargs["custodian_dir"],
                 "job_credential_path": kwargs["job_credential_file"],
                 "argv": ["claude", "--model", kwargs.get("model")]}
        destination = service.runtimes / kwargs["runtime_id"] / "manifest.json"
        destination.parent.mkdir(mode=0o700)
        _write_json(destination, value)
        return value

    def source_builder(**kwargs):
        source_observed.update(kwargs)
        return build_manifest(**kwargs)

    def target_builder(**kwargs):
        target_observed.update(kwargs)
        return build_manifest(**kwargs)

    class Provider:
        def admit_source(self, *, manifest, **_kwargs):
            self.manifest = manifest
            return {"admission": {"custodian_dir": manifest["custodian_dir"]},
                    "claim": {"claim_generation": 1}}

    service.provider = Provider()
    service._write_custodian_binding = lambda *_args: None
    monkeypatch.setattr(control.threading, "Thread", FakeThread)
    monkeypatch.setattr(control, "sanitize_environment", lambda env, _profile: dict(env))
    monkeypatch.setattr(control, "create_runtime_launch", source_builder)
    monkeypatch.setattr(control, "runtime_launch_digest", lambda _manifest: "a" * 64)

    try:
        service._start({"source_profile": "team-a", "target_profile": "team-b",
                        "parent_uuid": PARENT, "cwd": str(fixture["nested"]),
                        "launch_mode": "fresh", "model": "sonnet"})
        config = service._config()
        assert source_observed["model"] == "sonnet"
        assert service.provider.manifest["model"] == "sonnet"
        assert config["model"] == "sonnet"

        monkeypatch.setattr(control, "create_runtime_launch", target_builder)
        target = service._target_manifest(config, 2)
        assert target_observed["model"] == "sonnet"
        assert target["model"] == "sonnet"

        target_path = service.runtimes / config["target_runtime_id"] / "manifest.json"
        _write_json(target_path, target)
        monkeypatch.setattr(control, "validate_runtime_launch", lambda value: value)
        assert service._target_manifest(config, 2) == target
        changed = dict(config)
        changed["model"] = None
        with pytest.raises(ManagedStateError, match="another binding"):
            service._target_manifest(changed, 2)
    finally:
        job_server.close()


@pytest.mark.parametrize("model", [None, "opus"])
def test_start_rejects_malformed_explicit_model_before_enrollment(tmp_path, model):
    service = LaneCliControlService.__new__(LaneCliControlService)
    service.config_file = tmp_path / "session.json"
    payload = {"source_profile": "team-a", "target_profile": "team-b",
               "parent_uuid": PARENT, "cwd": str(tmp_path), "model": model}
    with pytest.raises(ManagedStateError, match="Claude model selection is unsupported"):
        service._start(payload)
    assert not service.config_file.exists()


def test_public_start_parser_forwards_supported_model(tmp_path, monkeypatch, capsys):
    observed = []
    monkeypatch.setattr(control, "start_supervisor",
                        lambda lane: {"socket": "control.sock",
                                      "credential_file": "control-credential.json"})
    monkeypatch.setattr(control, "control_request",
                        lambda _socket, _credential, method, payload:
                        observed.append((method, payload)) or {"ok": True})
    main = runpy.run_path(str(REPO / "lane-managed-cli"),
                          run_name="managed_cli_model_binding_test")["main"]
    assert main(["start", LANE, "--source-profile", "team-a", "--target-profile",
                 "team-b", "--parent-uuid", PARENT, "--cwd", str(tmp_path),
                 "--model", "sonnet"]) == 0
    capsys.readouterr()
    assert observed == [("start", {"source_profile": "team-a",
                                    "target_profile": "team-b",
                                    "parent_uuid": PARENT, "launch_mode": "fresh",
                                    "cwd": str(tmp_path), "model": "sonnet"})]
    with pytest.raises(SystemExit):
        main(["start", LANE, "--source-profile", "team-a", "--target-profile",
              "team-b", "--parent-uuid", PARENT, "--cwd", str(tmp_path),
              "--model", "opus"])
