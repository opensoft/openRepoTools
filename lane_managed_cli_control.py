# SPDX-License-Identifier: Apache-2.0
"""Model-free control of one opt-in shared-container Claude CLI lane.

The service owns the source custodian and a separate persistent job domain.
Every irreversible launch has a durable intent; an uncertain result is never
retried by guessing whether the child ran.  The service never signals a
container, another session, or a process supplied by a caller.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from lane_managed_cli_history import ClaudeCliHistoryWitness
from lane_managed_cli_runtime import (SUPPORTED_MODEL_SELECTIONS, create_runtime_launch,
                                     runtime_launch_digest, validate_runtime_launch)
from lane_managed_cli_source import (MonotonicWitnessSequence, SharedParentRegistry,
                                     SharedSessionSourceProvider, SourceCustodianLauncher,
                                     SourceCustodyError, auth_account_digest, _digest, _write_durable)
from lane_managed_job_runner import ManagedJobRunner
from lane_managed_local_jobs import (JobSupervisorService, LedgerCredentialVerifier,
                                     LocalJobExecutionDomain, job_socket_path)
from lane_managed_profiles import ProfileResolver, ProfileError, sanitize_environment
from lane_managed_state import ManagedStateError, ManagedStateStore, resolve_workspace
from lane_managed_supervised_jobs import ClaudeCliSupervisedJobsLedger


_MAX_FRAME = 65536


def _reject(code: str, detail: str) -> None:
    raise ManagedStateError(code, detail)


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _read_private(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        _reject("unsafe-state", "private control record is unavailable")
    raw = path.read_bytes()
    if len(raw) > _MAX_FRAME:
        _reject("invalid", "private control record exceeds its bound")
    value = json.loads(raw)
    if not isinstance(value, dict):
        _reject("invalid", "private control record is malformed")
    return value


def _private_dir(path: Path) -> None:
    if path.is_symlink():
        _reject("unsafe-state", "control directory is linked")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.resolve(strict=True) != path or path.stat().st_mode & 0o077:
        _reject("unsafe-state", "control directory is not owner-private")


def _runtime_socket(identity: str, *, create: bool = True) -> Path:
    root = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / ("openrepotools-cli-%d" % os.getuid())
    if create:
        _private_dir(root)
    elif root.is_symlink() or not root.is_dir() or root.stat().st_mode & 0o077:
        _reject("unknown", "control socket directory is unavailable")
    socket_path = root / (hashlib.sha256(identity.encode()).hexdigest()[:32] + "-control.sock")
    if len(os.fsencode(socket_path)) >= 100:
        _reject("invalid", "control socket path exceeds Unix bound")
    return socket_path


def _uuid(value: Any, label: str) -> str:
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError("noncanonical")
    except ValueError:
        _reject("invalid", "%s must be a canonical UUID" % label)
    return value


def _project_git_identity(cwd: Path) -> tuple[Path, Path]:
    """Resolve the real project before any durable enrollment or launch intent."""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(cwd), "rev-parse",
             "--path-format=absolute", "--show-toplevel", "--git-common-dir"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _reject("unknown", "project Git identity is unavailable")
    if result.returncode != 0:
        _reject("unsupported", "source working directory is not a project Git worktree")
    lines = result.stdout.splitlines()
    if len(lines) != 2 or any(not item or "\x00" in item for item in lines):
        _reject("unknown", "project Git identity is malformed")
    top, common = (Path(item) for item in lines)
    if (not top.is_absolute() or not common.is_absolute() or
            not top.is_dir() or not common.is_dir() or
            top.is_symlink() or common.is_symlink() or
            top.resolve(strict=True) != top or common.resolve(strict=True) != common or
            not cwd.is_relative_to(top)):
        _reject("ownership-conflict", "project Git identity is not canonical")
    return top, common


class _JobWitness:
    def __init__(self, domain: LocalJobExecutionDomain):
        self.domain = domain
        self.runner: ManagedJobRunner | None = None

    @property
    def persistent_job_domain_id(self) -> str:
        return self.domain.persistent_job_domain_id

    def assert_ready(self) -> None:
        self.domain.assert_ready()

    def job_status(self, binding: Mapping[str, Any], job_id: str) -> Mapping[str, Any]:
        if self.runner is None:
            _reject("unsupported", "persistent job runner is unavailable")
        return self.runner.job_status(binding, job_id)


class LaneCliControlService:
    """One process incarnation for one named lane; no automatic takeover."""

    def __init__(self, lane: str, *, env: Mapping[str, str] | None = None):
        self.env = dict(os.environ if env is None else env)
        self.store = ManagedStateStore(resolve_workspace(lane, env=self.env))
        self.store.ensure_layout()
        self.root = self.store.identity.state_root / "cli-supervisor"
        _private_dir(self.root)
        self.socket_path = _runtime_socket(str(self.root))
        self.credential_file = self.root / "control-credential.json"
        self.config_file = self.root / "session.json"
        self.admissions = self.root / "admissions"
        self.runtimes = self.root / "runtimes"
        self.jobs = self.root / "jobs"
        self.job_credentials = self.root / "job-credentials"
        for path in (self.admissions, self.runtimes, self.jobs, self.job_credentials):
            _private_dir(path)
        self.incarnation = str(uuid.uuid4())
        self.sequence = MonotonicWitnessSequence()
        self.profile_resolver = ProfileResolver(self.env)
        self.ledger = ClaudeCliSupervisedJobsLedger(self.store)
        self.domain = LocalJobExecutionDomain(self.jobs, "local-jobs-" + self.incarnation,
                                              next_watermark=self.sequence.next)
        self.job_witness = _JobWitness(self.domain)
        registry_root = self.store.identity.global_root / "shared-cli-parents"
        self.registry = SharedParentRegistry(str(registry_root))
        self.provider = SharedSessionSourceProvider(
            self.ledger, self.registry, str(self.admissions),
            history_provider=ClaudeCliHistoryWitness(self.ledger, self.profile_resolver,
                                                      next_watermark=self.sequence.next),
            job_provider=self.job_witness, next_watermark=self.sequence.next)
        self.ledger.witness_provider = self.provider
        self.runner = ManagedJobRunner(self.ledger, self.domain)
        self.job_witness.runner = self.runner
        self.verifier = LedgerCredentialVerifier(self.ledger, self.job_credentials)
        self.job_socket = job_socket_path(str(self.root))
        self.job_service = JobSupervisorService(self.job_socket, self.runner, self.verifier)
        self._job_thread: threading.Thread | None = None

    def _credential(self) -> str:
        value = _read_private(self.credential_file)
        if set(value) != {"token"} or not isinstance(value["token"], str):
            _reject("invalid", "control credential is malformed")
        return value["token"]

    def _config(self) -> dict[str, Any]:
        value = _read_private(self.config_file)
        if value.get("integrity_digest") != _digest({
                key: item for key, item in value.items() if key != "integrity_digest"}):
            _reject("unsafe-state", "session control intent changed")
        if ("model" in value and
                (not isinstance(value["model"], str) or
                 value["model"] not in SUPPORTED_MODEL_SELECTIONS)):
            _reject("unsafe-state", "session model selection changed")
        source_manifest_path = (self.runtimes / value["source_runtime_id"] /
                                "manifest.json")
        if source_manifest_path.is_file():
            source_manifest = _read_private(source_manifest_path)
            if source_manifest.get("model") != value.get("model"):
                _reject("unsafe-state", "session model differs from its source launch")
        return value

    def _save_config(self, value: dict[str, Any]) -> None:
        value["integrity_digest"] = _digest({
            key: item for key, item in value.items() if key != "integrity_digest"})
        _write_durable(self.config_file, value)

    def _write_custodian_binding(self, runtime_id: str, parent_uuid: str) -> None:
        path = self.admissions / (runtime_id + "-custodian") / "control.json"
        expected = {"socket": str(self.socket_path),
                    "credential_file": str(self.credential_file),
                    "parent_uuid": parent_uuid, "runtime_id": runtime_id}
        if path.exists():
            if _read_private(path) != expected:
                _reject("ownership-conflict", "source control binding changed")
            return
        # This file is deliberately scoped to the exact source custodian.
        _write_durable(path, expected)

    def _start(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"source_profile", "target_profile", "parent_uuid", "launch_mode",
                   "cwd", "claude_executable", "model"}
        if set(payload) - allowed or not {"source_profile", "target_profile", "parent_uuid", "cwd"}.issubset(payload):
            _reject("invalid", "start fields are malformed")
        if self.config_file.exists():
            _reject("busy", "lane already has a session or unresolved start intent")
        parent = _uuid(payload["parent_uuid"], "parent UUID")
        model = payload.get("model")
        if "model" in payload and (not isinstance(model, str) or
                                    model not in SUPPORTED_MODEL_SELECTIONS):
            _reject("invalid", "Claude model selection is unsupported")
        source = self.profile_resolver.resolve(payload["source_profile"])
        target = self.profile_resolver.require_same_family(source, payload["target_profile"])
        if source.name == target.name:
            _reject("invalid", "target profile must differ from current source")
        cwd = Path(payload["cwd"])
        if not cwd.is_absolute() or cwd.is_symlink() or not cwd.is_dir() or cwd.resolve(strict=True) != cwd:
            _reject("invalid", "source working directory is not canonical")
        project_worktree, project_common_dir = _project_git_identity(cwd)
        mode = payload.get("launch_mode", "fresh")
        if mode not in {"fresh", "resume"}:
            _reject("invalid", "source launch mode is unsupported")
        history_link = source.config_dir / "projects"
        if not history_link.is_dir():
            _reject("unsupported", "source history store is unavailable")
        history_store = history_link.resolve(strict=True)
        target_store = (target.config_dir / "projects").resolve(strict=True)
        if history_store != target_store or not history_store.is_dir():
            _reject("ownership-conflict", "profiles do not share the same canonical history store")
        if mode == "resume":
            evidence = self.profile_resolver.verify_transcript(source, parent, cwd)
            if not evidence["transcript"]["exists"]:
                _reject("unsupported", "exact source parent transcript is missing")
        runtime_id = str(uuid.uuid4())
        target_runtime_id = str(uuid.uuid4())
        lineage_id = "cli-lineage-" + parent
        intent = {"schema": 1, "phase": "enrollment-intent", "parent_uuid": parent,
                  "source_profile": source.name, "target_profile": target.name,
                  "history_store": str(history_store),
                  "source_runtime_id": runtime_id, "target_runtime_id": target_runtime_id,
                  "source_launch_mode": mode, "cwd": str(cwd),
                  "claude_executable": payload.get("claude_executable", "claude"),
                  "lineage_id": lineage_id, "lineage_generation": 1,
                  "supervisor_incarnation": self.incarnation, "source_invocation_id": str(uuid.uuid4())}
        if model is not None:
            intent["model"] = model
        self._save_config(intent)
        owner = self.store.enroll_managed(self.incarnation, lineage_id=lineage_id,
                                          coordinator_session_uuid=parent)
        self.store.claim_lineage_workspace(
            lineage_id=lineage_id, owner_generation=owner["generation"],
            lineage_generation=1, workspace=str(project_worktree),
            common_dir=str(self.store.identity.common_dir),
            repository=str(project_common_dir),
            coordinator_session_uuid=parent)
        self.domain.assert_ready()
        if self._job_thread is None:
            self._job_thread = threading.Thread(target=self.job_service.serve_forever, daemon=True)
            self._job_thread.start()
        deadline = time.monotonic() + 5
        while not self.job_socket.is_socket() and time.monotonic() < deadline:
            if not self._job_thread.is_alive():
                break
            time.sleep(0.02)
        if not self.job_socket.is_socket() or not self._job_thread.is_alive():
            _reject("uncertain-effect", "persistent job supervisor did not become ready")
        credential = self.job_credentials / (runtime_id + ".json")
        self.verifier.issue_credential(credential, parent_uuid=parent,
                                       claim_generation=1, runtime_incarnation=runtime_id)
        manifest = create_runtime_launch(
            root=str(self.runtimes), runtime_id=runtime_id, parent_uuid=parent,
            profile_ref=source.name, profile_config_dir=str(source.config_dir),
            cwd=str(cwd), mcp_bridge_module=str(Path(__file__).with_name("lane_managed_local_jobs.py")),
            job_socket=str(self.job_socket), job_credential_file=str(credential),
            custodian_dir=str(self.admissions / (runtime_id + "-custodian")),
            session_name=self.store.identity.lane,
            launch_mode=mode, claude_executable=intent["claude_executable"],
            model=model,
            inherited_environment=sanitize_environment(self.env, source))
        result = self.provider.admit_source(
            manifest=manifest, history_store=str(history_store),
            supervisor_incarnation=self.incarnation, lineage_id=lineage_id,
            lineage_generation=1, invocation_id=intent["source_invocation_id"])
        self._write_custodian_binding(runtime_id, parent)
        intent["phase"] = "source-running"
        intent["source_manifest_digest"] = runtime_launch_digest(manifest)
        intent["owner_generation"] = owner["generation"]
        self._save_config(intent)
        return {"lane": self.store.identity.lane, "parent_uuid": parent,
                "runtime_id": runtime_id, "custodian_dir": result["admission"]["custodian_dir"],
                "claim_generation": result["claim"]["claim_generation"]}

    def _target_manifest(self, config: Mapping[str, Any], claim_generation: int) -> dict[str, Any]:
        runtime_id = config["target_runtime_id"]
        path = self.runtimes / runtime_id / "manifest.json"
        profile = self.profile_resolver.resolve(config["target_profile"])
        source = self.profile_resolver.resolve(config["source_profile"])
        self.profile_resolver.require_same_family(source, profile)
        try:
            source_history = (source.config_dir / "projects").resolve(strict=True)
            target_history = (profile.config_dir / "projects").resolve(strict=True)
        except (OSError, RuntimeError):
            _reject("unknown", "bound profile history store is unavailable")
        if (str(source_history) != config["history_store"] or
                str(target_history) != config["history_store"]):
            _reject("ownership-conflict", "profile history store changed after enrollment")
        if path.exists():
            existing = validate_runtime_launch(_read_private(path))
            expected_credential = self.job_credentials / (runtime_id + ".json")
            if (existing["parent_uuid"] != config["parent_uuid"] or
                    existing["profile_ref"] != config["target_profile"] or
                    existing["runtime_id"] != runtime_id or
                    existing["cwd"] != config["cwd"] or
                    existing["launch_mode"] != "resume" or
                    existing.get("model") != config.get("model") or
                    existing["session_name"] != self.store.identity.lane or
                    existing["custodian_dir"] != str(self.admissions / (runtime_id + "-custodian")) or
                    existing["job_credential_path"] != str(expected_credential)):
                _reject("ownership-conflict", "existing target runtime has another binding")
            scoped = _read_private(expected_credential)
            if (scoped.get("parent_uuid") != config["parent_uuid"] or
                    scoped.get("claim_generation") != claim_generation or
                    scoped.get("runtime_incarnation") != runtime_id):
                _reject("ownership-conflict", "target job credential generation changed")
            return existing
        evidence = self.profile_resolver.verify_transcript(source, config["parent_uuid"], config["cwd"])
        if not evidence["transcript"]["exists"]:
            _reject("unsupported", "exact parent history is not available for target")
        target_evidence = self.profile_resolver.verify_transcript(
            profile, config["parent_uuid"], config["cwd"])
        if not target_evidence["transcript"]["exists"]:
            _reject("unsupported", "target profile cannot read exact parent history")
        credential = self.job_credentials / (runtime_id + ".json")
        self.verifier.issue_credential(credential, parent_uuid=config["parent_uuid"],
                                       claim_generation=claim_generation, runtime_incarnation=runtime_id)
        return create_runtime_launch(
            root=str(self.runtimes), runtime_id=runtime_id, parent_uuid=config["parent_uuid"],
            profile_ref=profile.name, profile_config_dir=str(profile.config_dir),
            cwd=config["cwd"], mcp_bridge_module=str(Path(__file__).with_name("lane_managed_local_jobs.py")),
            job_socket=str(self.job_socket), job_credential_file=str(credential),
            custodian_dir=str(self.admissions / (runtime_id + "-custodian")),
            session_name=self.store.identity.lane,
            launch_mode="resume", claude_executable=config["claude_executable"],
            model=config.get("model"),
            inherited_environment=sanitize_environment(self.env, profile))

    def _prepare(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if set(payload) != {"parent_uuid", "runtime_id"}:
            _reject("invalid", "prepare binding is malformed")
        config = self._config()
        if config["phase"] not in {"source-running", "source-fenced"}:
            _reject("busy", "source has no preparable session")
        if payload["parent_uuid"] != config["parent_uuid"] or payload["runtime_id"] != config["source_runtime_id"]:
            _reject("ownership-conflict", "prepare does not match the source")
        ledger = self.ledger.status()
        current = ledger["current_claim"]
        if current["runtime_incarnation"] != config["source_runtime_id"]:
            _reject("ownership-conflict", "source claim changed")
        generation = current["claim_generation"]
        manifest = self._target_manifest(config, generation + 1)
        target_profile = self.profile_resolver.resolve(config["target_profile"])
        operation_id = "swap-" + config["source_runtime_id"]
        intent = self.ledger.prepare_swap(
            operation_id=operation_id, request_id=operation_id,
            request_digest=_digest({"source": config["source_runtime_id"],
                                    "target": config["target_runtime_id"]}),
            target_profile_ref=target_profile.name,
            target_manifest_digest=runtime_launch_digest(manifest),
            parent_uuid=config["parent_uuid"], claim_generation=generation)
        # The durable ledger fence precedes this scoped custodian fence.
        SourceCustodianLauncher(str(self.admissions / (config["source_runtime_id"] + "-custodian"))).fence(
            operation_id=operation_id, parent_uuid=config["parent_uuid"],
            runtime_id=config["source_runtime_id"])
        if config["phase"] != "source-fenced":
            history_store = config["history_store"]
            registered = self.registry.status(
                history_store=history_store, parent_uuid=config["parent_uuid"])
            previous_phase = registered.get("phase") if isinstance(registered, dict) else None
            if previous_phase not in {"source-running", "target-running"}:
                _reject("ownership-conflict", "cross-lane parent phase changed")
            self.registry.transition(
                history_store=history_store,
                parent_uuid=config["parent_uuid"], lane=self.store.identity.lane,
                expected_phase=previous_phase, phase="source-fenced",
                runtime_id=config["source_runtime_id"], operation_id=operation_id)
            config = dict(config)
            config["phase"] = "source-fenced"
            self._save_config(config)
        return {"operation_id": operation_id, "phase": intent["phase"],
                "parent_uuid": config["parent_uuid"]}

    def _reconcile(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if set(payload) != {"operation_id"}:
            _reject("invalid", "reconcile binding is malformed")
        operation_id = payload["operation_id"]
        config = self._config()
        if operation_id != "swap-" + config["source_runtime_id"]:
            _reject("ownership-conflict", "operation is outside this session")
        operation = self.ledger.status()["operations"].get(operation_id)
        if operation is None:
            _reject("unknown", "operation is unavailable")
        if (operation["phase"] in {"source-stopping", "reconciling",
                                   "indeterminate", "ready-to-resume"} and
                operation["target_launch_intent"] is None and
                operation["release_intent"] is None):
            # Every explicit ready refreshes exact source custody.  This also
            # resumes a crash between job settlement and history observation,
            # and permits a completed job to clear its reservation before
            # re-witnessing the worktree.  Native history remains pinned.
            operation = self.ledger.observe_source_exclusion(
                operation_id, refresh_ready=operation["phase"] == "ready-to-resume")
        if operation["phase"] == "reconciling":
            operation = self.ledger.reconcile(operation_id)
        return {"operation_id": operation_id, "phase": operation["phase"],
                "uncertainty": operation["uncertainty"]}

    def _release(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if set(payload) != {"operation_id"}:
            _reject("invalid", "release binding is malformed")
        config = self._config()
        operation_id = payload["operation_id"]
        if operation_id != "swap-" + config["source_runtime_id"]:
            _reject("ownership-conflict", "release operation is outside this session")
        operation = self.ledger.status()["operations"].get(operation_id)
        if operation is None or operation["phase"] != "ready-to-resume":
            _reject("busy", "explicit release requires ready-to-resume")
        manifest = validate_runtime_launch(_read_private(
            self.runtimes / config["target_runtime_id"] / "manifest.json"))
        if runtime_launch_digest(manifest) != operation["target_manifest_digest"]:
            _reject("ownership-conflict", "target immutable launch changed")
        if manifest.get("model") != config.get("model"):
            _reject("ownership-conflict", "target model selection changed after enrollment")
        profile = self.profile_resolver.resolve(operation["target_profile_ref"])
        target_id = config["target_runtime_id"]
        source_history = config["history_store"]
        source_profile = self.profile_resolver.resolve(config["source_profile"])
        try:
            current_source_history = (source_profile.config_dir / "projects").resolve(strict=True)
            current_target_history = (profile.config_dir / "projects").resolve(strict=True)
        except (OSError, RuntimeError):
            _reject("unknown", "bound profile history store is unavailable")
        if (str(current_source_history) != source_history or
                str(current_target_history) != source_history):
            _reject("ownership-conflict", "profile history store changed before target release")
        account_digest = auth_account_digest(manifest, expected_email=profile.email)
        claimant_id = "target-" + target_id
        claim = self.ledger.claim_target(
            operation_id=operation_id, claimant_id=claimant_id,
            parent_uuid=config["parent_uuid"], owner_generation=operation["owner_generation"],
            claim_generation=operation["target_claim_generation"], profile_ref=profile.name,
            manifest_digest=operation["target_manifest_digest"])
        launch_intent = self.ledger.authorize_release(
            operation_id=operation_id, release_id="release-" + operation_id,
            target_claim_token=claim["claim_token"])
        admission = {"schema": 1, "runtime_id": target_id,
                     "parent_uuid": config["parent_uuid"], "profile_ref": profile.name,
                     "manifest_path": str(self.runtimes / target_id / "manifest.json"),
                     "manifest_digest": operation["target_manifest_digest"],
                     "claim_generation": operation["target_claim_generation"],
                     "source_domain_id": "source-subr-" + target_id,
                     "invocation_id": str(uuid.uuid4()),
                     "supervisor_incarnation": self.incarnation,
                     "custodian_dir": str(self.admissions / (target_id + "-custodian")),
                     "custodian": None, "source": None,
                     "launch_intent_id": launch_intent["launch_intent_id"],
                     "account_identity_digest": account_digest,
                     "history_store": source_history,
                     "phase": "target-spawn-intent"}
        target_intent = {"digest": _digest({"target": target_id,
                                           "launch_intent_id": launch_intent["launch_intent_id"]}),
                         "runtime_id": target_id,
                         "parent_uuid": config["parent_uuid"],
                         "cwd": manifest["cwd"],
                         "launch_intent_id": launch_intent["launch_intent_id"],
                         "generation": operation["target_claim_generation"],
                         "manifest_digest": operation["target_manifest_digest"]}
        # The same state lock used for source admission joins the final owner,
        # claim, manifest and registry check to B's actual exec-gate release.
        # A distinct owner cannot take over between the check and fork.
        with self.ledger._locked() as owner:
            state = self.ledger._load(owner)
            self.ledger._owner_current(owner, state)
            current = state.get("current_claim")
            fresh = state["operations"].get(operation_id)
            if (not isinstance(fresh, dict) or fresh.get("phase") != "target-starting" or
                    fresh.get("target_claim") != claim or
                    fresh.get("target_launch_intent") != launch_intent or
                    fresh.get("parent_uuid") != config["parent_uuid"] or
                    fresh.get("target_manifest_digest") != runtime_launch_digest(manifest) or
                    fresh.get("supervisor_incarnation") != self.incarnation or
                    not isinstance(current, dict) or current.get("state") != "target-pending" or
                    current.get("runtime_incarnation") != config["source_runtime_id"]):
                _reject("ownership-conflict", "target launch authority changed before exec")
            self.ledger._assert_registered_worktree_ids(
                lineage_id=fresh["lineage_id"],
                lineage_generation=fresh["lineage_generation"],
                parent_uuid=fresh["parent_uuid"],
                owner_generation=fresh["owner_generation"],
                expected_worktree_ids=fresh["worktree_ids"])
            registered = self.registry.status(
                history_store=source_history, parent_uuid=config["parent_uuid"])
            if ((source_profile.config_dir / "projects").resolve(strict=True) !=
                    Path(source_history) or
                    (profile.config_dir / "projects").resolve(strict=True) !=
                    Path(source_history)):
                _reject("ownership-conflict", "profile history store changed before target exec")
            if (not isinstance(registered, dict) or
                    registered.get("phase") != "source-fenced" or
                    registered.get("runtime_id") != config["source_runtime_id"] or
                    registered.get("operation_id") != operation_id):
                _reject("ownership-conflict", "cross-lane source fence changed before target exec")
            if self.provider._admission_path(target_id).exists():
                _reject("busy", "target admission intent already exists; startup may be uncertain")
            self.registry.transition(
                history_store=source_history, parent_uuid=config["parent_uuid"],
                lane=self.store.identity.lane,
                expected_phase="source-fenced", phase="target-intent",
                runtime_id=target_id, expected_runtime_id=config["source_runtime_id"],
                manifest_digest=operation["target_manifest_digest"],
                generation=operation["target_claim_generation"])
            self.provider._write_admission(admission)
            result = SourceCustodianLauncher(admission["custodian_dir"]).launch(
                argv=manifest["argv"], environment=manifest["environment"],
                cwd=manifest["cwd"], intent=target_intent)
            admission["phase"] = "target-running"
            admission["custodian"] = result["custodian"]
            admission["source"] = result["source"]
            self.provider._write_admission(admission)
            self.registry.transition(
                history_store=source_history, parent_uuid=config["parent_uuid"],
                lane=self.store.identity.lane,
                expected_phase="target-intent", phase="target-running",
                runtime_id=target_id, custodian_identity=result["custodian"],
                source_identity=result["source"])
        # The native CLI may wait at a fresh trust dialog before SessionStart.
        # Return this exact durable launch locator so an operator can attach;
        # later observation never re-enters this spawn path.
        return {"operation_id": operation_id, "phase": "target-starting",
                "runtime_id": target_id, "custodian_dir": admission["custodian_dir"],
                "launch_intent_id": launch_intent["launch_intent_id"]}

    def _observe_target(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if set(payload) != {"operation_id"}:
            _reject("invalid", "target observation binding is malformed")
        operation_id = payload["operation_id"]
        config = self._config()
        ledger = self.ledger.status()
        operation = ledger["operations"].get(operation_id)
        if not isinstance(operation, dict) or operation.get("phase") not in {
                "target-starting", "indeterminate", "target-observed"}:
            _reject("busy", "target observation has no current durable launch")
        launch_intent = operation.get("target_launch_intent")
        if (not isinstance(launch_intent, dict) or
                operation.get("supervisor_incarnation") != self.incarnation or
                operation.get("parent_uuid") != config.get("parent_uuid") or
                operation.get("owner_generation") != ledger.get("owner_generation") or
                not isinstance(operation.get("target_claim"), dict)):
            _reject("ownership-conflict", "target observation owner or claim changed")
        observed_before = operation["phase"] == "target-observed"
        target_id = (launch_intent.get("runtime_incarnation") if observed_before else
                     config.get("target_runtime_id"))
        if not isinstance(target_id, str):
            _reject("ownership-conflict", "target runtime identity is unavailable")
        current = ledger["current_claim"]
        if observed_before:
            if (config.get("phase") not in {"source-fenced", "source-running"} or
                    config.get("source_runtime_id") not in {
                        operation["source_runtime_incarnation"], target_id} or
                    current.get("state") not in {"target-active", "active"} or
                    current.get("runtime_incarnation") != target_id or
                    current.get("claim_generation") != operation["target_claim_generation"] or
                    current.get("claimant_id") != operation["target_claim"]["claimant_id"]):
                _reject("ownership-conflict", "observed target is no longer current")
        elif (config.get("phase") != "source-fenced" or
              config.get("source_runtime_id") != operation["source_runtime_incarnation"] or
              current.get("state") != "target-pending" or
              current.get("runtime_incarnation") != operation["source_runtime_incarnation"] or
              current.get("claim_generation") != operation["source_claim_generation"]):
            _reject("ownership-conflict", "pending target claim changed")
        if (launch_intent.get("launch_intent_id") is None or
                launch_intent.get("parent_uuid") != config["parent_uuid"] or
                launch_intent.get("manifest_digest") != operation["target_manifest_digest"] or
                launch_intent.get("claim_generation") != operation["target_claim_generation"]):
            _reject("ownership-conflict", "target launch intent changed")
        with self.ledger._locked() as owner:
            state = self.ledger._load(owner)
            self.ledger._owner_current(owner, state)
            self.ledger._assert_registered_worktree_ids(
                lineage_id=operation["lineage_id"],
                lineage_generation=operation["lineage_generation"],
                parent_uuid=operation["parent_uuid"],
                owner_generation=operation["owner_generation"],
                expected_worktree_ids=operation["worktree_ids"])
        admission = self.provider._read_admission(target_id)
        if (admission.get("phase") not in ({"target-running", "source-running"} if observed_before
                                          else {"target-running"}) or
                admission.get("runtime_id") != target_id or
                admission.get("parent_uuid") != config["parent_uuid"] or
                admission.get("profile_ref") != operation["target_profile_ref"] or
                admission.get("manifest_digest") != operation["target_manifest_digest"] or
                admission.get("claim_generation") != operation["target_claim_generation"] or
                admission.get("launch_intent_id") != launch_intent["launch_intent_id"] or
                admission.get("supervisor_incarnation") != self.incarnation or
                admission.get("history_store") != config["history_store"]):
            _reject("ownership-conflict", "target admission changed after release")
        manifest = self.provider._launch_manifest(admission)
        if manifest["launch_mode"] != "resume" or manifest["cwd"] != config["cwd"]:
            _reject("ownership-conflict", "target launch manifest changed")
        profile = self.profile_resolver.resolve(operation["target_profile_ref"])
        source_profile = self.profile_resolver.resolve(operation["source_profile_ref"])
        self.profile_resolver.require_same_family(source_profile, profile)
        try:
            histories = ((profile.config_dir / "projects").resolve(strict=True),
                         (source_profile.config_dir / "projects").resolve(strict=True))
        except (OSError, RuntimeError):
            _reject("unknown", "bound profile history store is unavailable")
        if any(str(path) != config["history_store"] for path in histories):
            _reject("ownership-conflict", "profile history store changed after release")
        if auth_account_digest(manifest, profile.email) != admission["account_identity_digest"]:
            _reject("ownership-conflict", "target account identity changed after release")
        registered = self.registry.status(history_store=config["history_store"],
                                          parent_uuid=config["parent_uuid"])
        if (not isinstance(registered, dict) or registered.get("lane") != self.store.identity.lane or
                registered.get("phase") != "target-running" or
                registered.get("runtime_id") != target_id or
                registered.get("manifest_digest") != operation["target_manifest_digest"] or
                registered.get("generation") != operation["target_claim_generation"] or
                registered.get("custodian_identity") != admission.get("custodian") or
                registered.get("source_identity") != admission.get("source") or
                registered.get("operation_id") != operation_id):
            _reject("ownership-conflict", "cross-lane target binding changed")
        launcher = SourceCustodianLauncher(admission["custodian_dir"])
        answer = launcher.challenge()
        intent = answer.get("launch_intent")
        if (answer.get("custodian") != admission["custodian"] or
                answer.get("source") != admission["source"] or
                answer.get("source_exit") is not None or answer.get("phase") != "running" or
                answer.get("subreaper") is not True or
                not isinstance(intent, dict) or
                intent.get("runtime_id") != target_id or
                intent.get("parent_uuid") != config["parent_uuid"] or
                intent.get("launch_intent_id") != launch_intent["launch_intent_id"] or
                intent.get("manifest_digest") != operation["target_manifest_digest"] or
                (not observed_before and answer.get("model_input_admitted") is not False)):
            _reject("ownership-conflict", "target custodian changed after release")
        from lane_managed_cli_source import _identity
        if _identity(admission["source"]["pid"]) != admission["source"]:
            _reject("ownership-conflict", "target source process identity changed")
        if answer.get("session_start") is None:
            if observed_before:
                _reject("uncertain-effect", "observed target lost SessionStart custody")
            return {"operation_id": operation_id, "phase": "target-starting",
                    "runtime_id": target_id, "custodian_dir": admission["custodian_dir"],
                    "launch_intent_id": launch_intent["launch_intent_id"]}
        if not observed_before:
            observed = self.ledger.observe_target_start(operation_id)
        else:
            observed = launch_intent
        self.ledger.claim_source(
            supervisor_incarnation=self.incarnation, parent_uuid=config["parent_uuid"],
            lineage_id=operation["lineage_id"],
            lineage_generation=operation["lineage_generation"],
            profile_ref=profile.name, runtime_incarnation=target_id,
            invocation_id=admission["invocation_id"],
            domain_id=admission["source_domain_id"],
            manifest_digest=operation["target_manifest_digest"])
        if admission["phase"] != "source-running":
            admission["phase"] = "source-running"
            self.provider._write_admission(admission)
        if config["source_runtime_id"] != target_id:
            config = dict(config)
            config["source_profile"] = profile.name
            config["target_profile"] = operation["source_profile_ref"]
            config["source_runtime_id"] = target_id
            config["target_runtime_id"] = str(uuid.uuid4())
            config["source_invocation_id"] = admission["invocation_id"]
            config["source_manifest_digest"] = operation["target_manifest_digest"]
            config["phase"] = "source-running"
            self._save_config(config)
        elif (config.get("source_profile") != profile.name or
              config.get("source_invocation_id") != admission["invocation_id"] or
              config.get("source_manifest_digest") != operation["target_manifest_digest"]):
            _reject("ownership-conflict", "adopted source config changed")
        self._write_custodian_binding(target_id, config["parent_uuid"])
        # The final input gate is joined to the same managed-owner lock as
        # source exec. A takeover between adoption writes and this point must
        # never leave stale B able to submit a model turn.
        with self.ledger._locked() as owner:
            state = self.ledger._load(owner)
            self.ledger._owner_current(owner, state)
            fresh = state["operations"].get(operation_id)
            current = state["current_claim"]
            if (not isinstance(fresh, dict) or fresh.get("phase") != "target-observed" or
                    fresh.get("target_launch_intent") != observed or
                    fresh.get("owner_generation") != state["owner_generation"] or
                    not isinstance(current, dict) or current.get("state") != "active" or
                    current.get("runtime_incarnation") != target_id or
                    current.get("claim_generation") != operation["target_claim_generation"] or
                    current.get("claimant_id") != operation["target_claim"]["claimant_id"] or
                    self._config() != config or
                    self.provider._read_admission(target_id) != admission):
                _reject("ownership-conflict", "target adoption changed before input activation")
            self.ledger._assert_registered_worktree_ids(
                lineage_id=fresh["lineage_id"],
                lineage_generation=fresh["lineage_generation"],
                parent_uuid=fresh["parent_uuid"],
                owner_generation=fresh["owner_generation"],
                expected_worktree_ids=fresh["worktree_ids"])
            binding_path = Path(admission["custodian_dir"]) / "control.json"
            if _read_private(binding_path) != {
                    "socket": str(self.socket_path),
                    "credential_file": str(self.credential_file),
                    "parent_uuid": config["parent_uuid"], "runtime_id": target_id}:
                _reject("ownership-conflict", "target input control binding changed")
            registered = self.registry.status(history_store=config["history_store"],
                                              parent_uuid=config["parent_uuid"])
            if (not isinstance(registered, dict) or
                    registered.get("phase") != "target-running" or
                    registered.get("runtime_id") != target_id or
                    registered.get("source_identity") != admission["source"] or
                    registered.get("custodian_identity") != admission["custodian"]):
                _reject("ownership-conflict", "target registry changed before input activation")
            launcher.activate_input(parent_uuid=config["parent_uuid"], runtime_id=target_id,
                                    launch_intent_id=launch_intent["launch_intent_id"],
                                    manifest_digest=operation["target_manifest_digest"])
        return {"operation_id": operation_id, "phase": "target-observed",
                "runtime_id": target_id, "custodian_dir": admission["custodian_dir"],
                "launch_intent_id": observed["launch_intent_id"]}

    def handle(self, method: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if method == "start":
            return self._start(payload)
        if method == "prepare":
            return self._prepare(payload)
        if method == "reconcile":
            return self._reconcile(payload)
        if method == "release":
            return self._release(payload)
        if method == "observe-target":
            return self._observe_target(payload)
        if method == "select-target" and set(payload) == {"target_profile"}:
            config = self._config()
            if config["phase"] != "source-running":
                _reject("busy", "target selection requires an active source")
            status = self.ledger.status()
            current = status["current_claim"]
            if (current.get("state") != "active" or
                    current.get("runtime_incarnation") != config["source_runtime_id"]):
                _reject("ownership-conflict", "target selection source changed")
            source_profile = self.profile_resolver.resolve(config["source_profile"])
            target_profile = self.profile_resolver.require_same_family(
                source_profile, payload["target_profile"])
            if target_profile.name == source_profile.name:
                _reject("invalid", "target profile must differ from current source")
            config["target_profile"] = target_profile.name
            config["target_runtime_id"] = str(uuid.uuid4())
            self._save_config(config)
            return {"source_profile": source_profile.name, "target_profile": target_profile.name,
                    "parent_uuid": config["parent_uuid"]}
        if method == "status" and not payload:
            ledger = self.ledger.status()
            return {"lane": ledger["lane"], "claim_generation": ledger["claim_generation"],
                    "current_claim": ledger["current_claim"],
                    "operations": {key: {"phase": op["phase"],
                                          "uncertainty": op["uncertainty"]}
                                   for key, op in ledger["operations"].items()}}
        if method == "ping" and not payload:
            return {"lane": self.store.identity.lane, "incarnation": self.incarnation}
        _reject("invalid", "control method is unsupported")

    @staticmethod
    def _send_response(conn: socket.socket, response: Mapping[str, Any]) -> bool:
        """A lost client ACK never stops the independent service or its jobs."""
        try:
            conn.sendall(_json(response) + b"\n")
            return True
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return False

    def serve_forever(self) -> None:
        self.domain.assert_ready()
        if self.socket_path.exists() or self.socket_path.is_symlink():
            _reject("busy", "control socket already exists; prior service may be live")
        if not self.credential_file.exists():
            _write_durable(self.credential_file, {"token": secrets.token_hex(32)})
        token = self._credential()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        server.listen(8)
        try:
            while True:
                conn, _ = server.accept()
                with conn:
                    try:
                        conn.settimeout(10)
                        data = bytearray()
                        while len(data) <= _MAX_FRAME and b"\n" not in data:
                            frame = conn.recv(4096)
                            if not frame:
                                break
                            data.extend(frame)
                        if len(data) > _MAX_FRAME or not data.endswith(b"\n"):
                            _reject("invalid", "control request is malformed")
                        request = json.loads(data)
                        if (not isinstance(request, dict) or set(request) != {"credential", "method", "payload"} or
                                not isinstance(request["credential"], str) or
                                not hmac.compare_digest(request["credential"], token) or
                                not isinstance(request["method"], str) or
                                not isinstance(request["payload"], dict)):
                            _reject("ownership-conflict", "control authority is invalid")
                        result = self.handle(request["method"], request["payload"])
                        response = {"ok": True, "result": result}
                    except (ManagedStateError, ProfileError) as exc:
                        response = {"ok": False, "error": {"code": exc.code, "message": str(exc)[:256]}}
                    except (SourceCustodyError, OSError, ValueError, TypeError, KeyError) as exc:
                        response = {"ok": False, "error": {"code": "uncertain-effect", "message": str(exc)[:256]}}
                    self._send_response(conn, response)
        finally:
            server.close()


def control_request(socket_path: str | Path, credential_file: str | Path,
                    method: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Issue one bounded external control request using supervisor authority."""
    credential = _read_private(Path(credential_file))
    if set(credential) != {"token"} or not isinstance(credential["token"], str):
        _reject("invalid", "control credential is malformed")
    request = _json({"credential": credential["token"], "method": method,
                     "payload": dict(payload)}) + b"\n"
    if len(request) > _MAX_FRAME:
        _reject("invalid", "control request exceeds its bound")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        # Release may include two independent history/effect scans, bounded
        # auth observations and exact CLI SessionStart.  A lost ACK is still
        # possible; the durable operation remains authoritative in that case.
        conn.settimeout(180 if method == "release" else 90 if method in {"start", "reconcile"} else 10)
        conn.connect(str(socket_path))
        conn.sendall(request)
        data = bytearray()
        while len(data) <= _MAX_FRAME and b"\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
    if len(data) > _MAX_FRAME or not data.endswith(b"\n"):
        _reject("unknown", "control response is unavailable")
    response = json.loads(data)
    if not isinstance(response, dict) or set(response) != {"ok", "result"} and set(response) != {"ok", "error"}:
        _reject("unknown", "control response is malformed")
    if response["ok"] is not True:
        error = response.get("error")
        if not isinstance(error, dict):
            _reject("unknown", "control request outcome is unavailable")
        _reject(str(error.get("code", "unknown")), str(error.get("message", "control refused")))
    if not isinstance(response["result"], dict):
        _reject("unknown", "control result is malformed")
    return response["result"]


def start_supervisor(lane: str, *, env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Start one persistent service; an existing or stale socket is never replaced."""
    identity = resolve_workspace(lane, env=env)
    ManagedStateStore(identity).ensure_layout()
    root = identity.state_root / "cli-supervisor"
    _private_dir(root)
    socket_path = _runtime_socket(str(root))
    credential_file = root / "control-credential.json"
    if socket_path.exists() or socket_path.is_symlink():
        _reject("busy", "control socket already exists; use the existing supervisor")
    if credential_file.exists() or credential_file.is_symlink():
        _reject("busy", "control credential already exists; prior service outcome is uncertain")
    command = [sys.executable, str(Path(__file__).resolve()), "serve", identity.lane]
    with open(os.devnull, "rb") as input_file, open(os.devnull, "wb") as output_file:
        child = subprocess.Popen(command, stdin=input_file, stdout=output_file,
                                 stderr=output_file, start_new_session=True,
                                 env=dict(os.environ if env is None else env))
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if socket_path.exists() and credential_file.exists():
            try:
                control_request(socket_path, credential_file, "ping", {})
            except (ManagedStateError, OSError):
                pass
            else:
                return {"socket": str(socket_path), "credential_file": str(credential_file),
                        "lane": identity.lane}
        if child.poll() is not None:
            break
        time.sleep(0.03)
    _reject("unknown", "control service startup is uncertain; do not retry blindly")


def control_endpoint(lane: str, *, env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Locate an already running lane service without provisioning or replacing it."""
    identity = resolve_workspace(lane, env=env)
    root = identity.state_root / "cli-supervisor"
    if root.is_symlink() or not root.is_dir() or root.stat().st_mode & 0o077:
        _reject("unknown", "lane has no private CLI supervisor")
    credential_file = root / "control-credential.json"
    _read_private(credential_file)
    socket_path = _runtime_socket(str(root), create=False)
    if socket_path.is_symlink() or not socket_path.is_socket() or socket_path.stat().st_mode & 0o077:
        _reject("unknown", "lane control socket is unavailable")
    return {"socket": str(socket_path), "credential_file": str(credential_file),
            "lane": identity.lane}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] != "serve":
        print("usage: lane_managed_cli_control.py serve <lane>", file=sys.stderr)
        return 2
    try:
        LaneCliControlService(args[1]).serve_forever()
    except (ManagedStateError, ProfileError, SourceCustodyError) as exc:
        print("shared CLI supervisor: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
