# SPDX-License-Identifier: Apache-2.0
"""Private durable state foundation for the opt-in Claude CLI job boundary.

This module is deliberately not imported by the CLI, SDK runner, daemon socket
router, or installed launchers.  It provides state transitions only.  A
production caller still needs to supply trusted OS/job/history observations and
must wire every runtime-creation path through the source-generation check.

All reads and writes use :class:`ManagedStateStore`'s existing interprocess
lock and atomic file replacement.  The optional ledger is kept in its own
strictly versioned file; existing owner, controller, and SDK records are not
rewritten or migrated.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from lane_managed_state import ManagedStateError, ManagedStateStore


CAPABILITY = "claude-cli-supervised-jobs-v1"
SCHEMA_VERSION = 1
RECORD_KIND = "claude-cli-supervised-jobs-ledger"
_LEDGER_NAME = "claude-cli-supervised-jobs.json"
_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN_RE = re.compile(r"[^\x00-\x1f\x7f]{1,256}\Z")
_MAX_OPERATIONS = 32
_MAX_JOBS = 256
_MAX_WORKTREES = 128

_LEDGER_FIELDS = frozenset({
    "schema_version", "capability", "record_kind", "lane", "lane_key",
    "host", "process_domain", "common_dir", "daemon_id",
    "supervisor_incarnation", "owner_generation", "claim_generation",
    "current_claim", "retired_source_generations", "operations", "jobs",
    "reservations", "observation_watermark", "integrity_digest",
})
_CLAIM_FIELDS = frozenset({
    "claim_generation", "parent_uuid", "lineage_id", "lineage_generation",
    "profile_ref", "runtime_incarnation", "invocation_id", "domain_id",
    "manifest_digest", "worktree_ids", "state", "claimant_id",
})
_OP_FIELDS = frozenset({
    "operation_id", "request_id", "request_digest", "capability",
    "owner_generation", "source_claim_generation", "target_claim_generation",
    "parent_uuid", "lineage_id", "lineage_generation", "source_profile_ref",
    "target_profile_ref", "source_runtime_incarnation", "source_invocation_id",
    "source_domain_id", "source_manifest_digest", "target_manifest_digest",
    "supervisor_incarnation", "worktree_ids", "job_ids", "phase",
    "source_restart_denied", "source_exclusion", "history_manifest",
    "job_observations", "target_claim", "release_intent",
    "target_launch_intent", "uncertainty",
})
_JOB_FIELDS = frozenset({
    "job_id", "request_id", "request_digest", "parent_uuid",
    "owner_generation", "source_claim_generation", "lineage_id",
    "lineage_generation", "domain_id", "command_digest", "resource_ids",
    "launch_state", "launch_intent_id", "state", "effect_state",
    "observation_watermark", "process_identity", "output_ref", "result_digest",
})
_WORKTREE_FIELDS = frozenset({
    "resource_id", "claim_kind", "claim_digest", "path", "repository",
    "common_dir",
})
_SOURCE_EXCLUSION_FIELDS = frozenset({
    "witness_id", "witness_digest", "observation_watermark",
    "source_runtime_incarnation", "source_domain_id", "supervisor_incarnation",
    "parent_uuid", "membership_complete", "escape_coverage_complete",
    "active_source_processes", "restart_fence_effective", "job_domain_live",
})
_HISTORY_FIELDS = frozenset({
    "witness_id", "witness_digest", "parent_uuid", "manifest_digest",
    "worktree_manifest_digest", "observation_watermark", "complete",
})
_JOB_OBSERVATION_FIELDS = frozenset({
    "witness_id", "witness_digest", "job_id", "command_digest", "domain_id",
    "observation_watermark", "state", "effect_state", "process_identity",
    "output_ref", "result_digest",
})
_PROCESS_FIELDS = frozenset({"pid", "start_token", "domain_id"})
_TARGET_CLAIM_FIELDS = frozenset({
    "claimant_id", "claim_token", "parent_uuid", "claim_generation",
    "owner_generation", "profile_ref", "manifest_digest", "claim_digest",
})
_RELEASE_FIELDS = frozenset({
    "release_id", "release_digest", "claim_digest", "exclusion_digest",
    "history_manifest_digest", "worktree_manifest_digest",
    "job_observation_digest", "observation_watermark",
})
_TARGET_LAUNCH_FIELDS = frozenset({
    "launch_intent_id", "parent_uuid", "claim_generation", "owner_generation",
    "profile_ref", "manifest_digest", "release_id", "state",
    "runtime_incarnation", "invocation_id", "domain_id", "process_identity",
    "account_identity_digest",
})


def _fail(code: str, message: str) -> None:
    raise ManagedStateError(code, message)


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or _TOKEN_RE.fullmatch(value) is None:
        _fail("invalid", "%s is malformed" % label)
    return value


def _uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        _fail("invalid", "%s is malformed" % label)
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        _fail("invalid", "%s is malformed" % label)
    canonical = str(parsed)
    if canonical != value:
        _fail("invalid", "%s is not a canonical UUID" % label)
    return canonical


def _positive(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail("invalid", "%s must be a positive integer" % label)
    return value


def _nonnegative(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("invalid", "%s must be a non-negative integer" % label)
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        _fail("invalid", "%s must be a SHA-256 digest" % label)
    return value


def _json(value: Any) -> Any:
    try:
        return json.loads(json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ))
    except (TypeError, ValueError) as exc:
        _fail("invalid", "supervised-jobs value is not bounded JSON: %s" % exc)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _exact(value: Any, fields: frozenset, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("invalid", "%s fields are malformed" % label)
    return value


def _absolute_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        _fail("invalid", "%s is malformed" % label)
    path = Path(value)
    if not path.is_absolute() or os.path.normpath(value) != value:
        _fail("invalid", "%s must be canonical and absolute" % label)
    return value


def _process_identity(value: Any, label: str, domain: str) -> Dict[str, Any]:
    identity = _exact(value, _PROCESS_FIELDS, label)
    pid = identity.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        _fail("invalid", "%s pid is malformed" % label)
    start_token = _token(identity.get("start_token"), "%s start_token" % label)
    process_domain = _token(identity.get("domain_id"), "%s domain_id" % label)
    if process_domain != domain:
        _fail("ownership-conflict", "%s process domain changed" % label)
    return {"pid": pid, "start_token": start_token, "domain_id": process_domain}


def _worktree_identity(claim: Mapping[str, Any]) -> Dict[str, Any]:
    claim_kind = claim.get("record_kind")
    if claim_kind == "workspace-claim":
        path = claim.get("workspace")
    elif claim_kind == "child-worktree-claim":
        path = claim.get("worktree")
    else:
        _fail("unsupported", "supervised job resource is not a registered worktree claim")
    path = _absolute_path(path, "registered worktree path")
    common_dir = _absolute_path(claim.get("common_dir"), "registered common directory")
    repository = _absolute_path(claim.get("repository"), "registered repository")
    claim_digest = _hash(claim)
    return {
        "resource_id": claim_kind + ":" + claim_digest,
        "claim_kind": claim_kind,
        "claim_digest": claim_digest,
        "path": path,
        "repository": repository,
        "common_dir": common_dir,
    }


def _seal_ledger(value: Dict[str, Any]) -> Dict[str, Any]:
    value["integrity_digest"] = ""
    value["integrity_digest"] = _hash({
        key: item for key, item in value.items() if key != "integrity_digest"
    })
    return value


class ClaudeCliSupervisedJobsLedger:
    """Internal state transitions for ``claude-cli-supervised-jobs-v1``.

    ``witness_provider`` is constructor-injected supervisor/OS authority.  It
    must expose the stable ``persistent_job_domain_id`` and implement
    ``source_exclusion(binding)``, ``history_manifest(binding)``,
    ``job_status(binding, job_id)``, and ``target_status(binding)``.  None of
    those observations can be supplied through a model request or method
    argument.  This foundation has no launch side effects and is not wired to
    the public daemon surface.
    """

    def __init__(self, store: ManagedStateStore, witness_provider: Any = None):
        if not isinstance(store, ManagedStateStore):
            _fail("invalid", "supervised-jobs ledger requires ManagedStateStore")
        self.store = store
        self.witness_provider = witness_provider

    @contextlib.contextmanager
    def _locked(self) -> Iterator[Mapping[str, Any]]:
        self.store.validate_layout()
        state_root = self.store.identity.state_root
        global_root = self.store.identity.global_root
        if (not state_root.is_dir() or not global_root.is_dir() or
                not (state_root / "owner.json").exists()):
            _fail("ownership-conflict", "supervised jobs require an existing managed owner")
        with self.store._locked_existing():
            self.store.validate_layout()
            if not (state_root / "owner.json").exists():
                _fail("ownership-conflict", "managed owner disappeared before ledger lock")
            owner = self.store._read_owner_locked()
            if owner.get("mode") != "managed":
                _fail("ownership-conflict", "supervised jobs require managed lane ownership")
            recovery = self.store._load_recovery_intent()
            if recovery is not None and recovery.get("state") != "complete":
                _fail("uncertain-effect", "managed owner recovery is pending")
            yield owner

    def _path(self) -> Path:
        return self.store._json_path(_LEDGER_NAME)

    def _empty(self, owner: Mapping[str, Any], supervisor_incarnation: str) -> Dict[str, Any]:
        identity = self.store.identity
        return _seal_ledger({
            "schema_version": SCHEMA_VERSION,
            "capability": CAPABILITY,
            "record_kind": RECORD_KIND,
            "lane": identity.lane,
            "lane_key": identity.lane_key,
            "host": identity.host,
            "process_domain": owner["process_domain"],
            "common_dir": str(identity.common_dir),
            "daemon_id": owner["daemon_id"],
            "supervisor_incarnation": supervisor_incarnation,
            "owner_generation": owner["generation"],
            "claim_generation": 0,
            "current_claim": None,
            "retired_source_generations": [],
            "operations": {},
            "jobs": {},
            "reservations": {},
            "observation_watermark": 0,
            "integrity_digest": "",
        })

    def _load(self, owner: Mapping[str, Any], *, allow_absent: bool = False,
              supervisor_incarnation: Optional[str] = None) -> Optional[Dict[str, Any]]:
        path = self._path()
        raw = self.store._read_path(path)
        if raw is None:
            if allow_absent:
                if supervisor_incarnation is None:
                    return None
                return self._empty(owner, supervisor_incarnation)
            _fail("unknown", "supervised-jobs ledger is absent")
        if not isinstance(raw, Mapping) or set(raw) != _LEDGER_FIELDS:
            _fail("invalid", "supervised-jobs ledger fields are malformed")
        if (raw.get("schema_version") != SCHEMA_VERSION or
                raw.get("capability") != CAPABILITY or
                raw.get("record_kind") != RECORD_KIND):
            _fail("schema-mismatch", "supervised-jobs ledger schema is unsupported")
        for key in ("lane", "lane_key", "host", "process_domain", "common_dir",
                    "daemon_id", "supervisor_incarnation"):
            _token(raw.get(key), "supervised-jobs %s" % key)
        identity = self.store.identity
        if (raw["lane"] != identity.lane or raw["lane_key"] != identity.lane_key or
                raw["host"] != identity.host or raw["common_dir"] != str(identity.common_dir)):
            _fail("ownership-conflict", "supervised-jobs ledger belongs to another lane")
        if (raw["owner_generation"] != owner.get("generation") or
                raw["daemon_id"] != owner.get("daemon_id") or
                raw["process_domain"] != owner.get("process_domain")):
            _fail("stale-generation", "supervised-jobs supervisor owner changed")
        _positive(raw.get("owner_generation"), "supervised-jobs owner_generation")
        _nonnegative(raw.get("claim_generation"), "supervised-jobs claim_generation")
        _nonnegative(raw.get("observation_watermark"), "supervised-jobs observation_watermark")
        operations = raw.get("operations")
        jobs = raw.get("jobs")
        reservations = raw.get("reservations")
        retired = raw.get("retired_source_generations")
        if (not isinstance(operations, Mapping) or len(operations) > _MAX_OPERATIONS or
                not isinstance(jobs, Mapping) or len(jobs) > _MAX_JOBS or
                not isinstance(reservations, Mapping) or
                not isinstance(retired, list) or len(retired) > _MAX_OPERATIONS):
            _fail("invalid", "supervised-jobs ledger capacity or collection is malformed")
        if len(set(retired)) != len(retired):
            _fail("invalid", "supervised-jobs retired generation list is duplicated")
        for generation in retired:
            _positive(generation, "retired source generation")
        current = raw.get("current_claim")
        if current is not None:
            self._validate_claim(current)
        for operation_id, operation in operations.items():
            _token(operation_id, "supervised-jobs operation key")
            self._validate_operation(operation, operation_id)
        for job_id, job in jobs.items():
            _token(job_id, "supervised job key")
            self._validate_job(job, job_id)
        for resource_id, job_id in reservations.items():
            _token(resource_id, "supervised resource reservation key")
            _token(job_id, "supervised resource reservation job ID")
            if (job_id not in jobs or
                    resource_id not in jobs[job_id].get("resource_ids", [])):
                _fail("invalid", "supervised resource reservation names an unknown job")
        self._validate_cross_references(raw)
        integrity = _digest(raw.get("integrity_digest"), "supervised-jobs integrity_digest")
        expected = _hash({key: value for key, value in raw.items()
                          if key != "integrity_digest"})
        if integrity != expected:
            _fail("invalid", "supervised-jobs ledger integrity digest changed")
        return _json(raw)

    @staticmethod
    def _validate_claim(value: Any) -> Mapping[str, Any]:
        claim = _exact(value, _CLAIM_FIELDS, "supervised source claim")
        _positive(claim.get("claim_generation"), "claim_generation")
        _uuid(claim.get("parent_uuid"), "claim parent UUID")
        _token(claim.get("lineage_id"), "claim lineage_id")
        _positive(claim.get("lineage_generation"), "claim lineage_generation")
        for key in ("profile_ref", "runtime_incarnation", "invocation_id", "domain_id"):
            _token(claim.get(key), "claim %s" % key)
        _digest(claim.get("manifest_digest"), "claim manifest_digest")
        if claim.get("state") not in {"active", "source-denied", "target-pending", "target-active"}:
            _fail("invalid", "supervised claim state is malformed")
        if claim.get("claimant_id") is not None:
            _token(claim.get("claimant_id"), "claim claimant_id")
        worktree_ids = claim.get("worktree_ids")
        if (not isinstance(worktree_ids, list) or not worktree_ids or
                len(worktree_ids) > _MAX_WORKTREES or
                any(not isinstance(item, str) or not item for item in worktree_ids) or
                len(set(worktree_ids)) != len(worktree_ids)):
            _fail("invalid", "supervised claim worktree identities are malformed")
        for item in worktree_ids:
            _token(item, "claim worktree identity")
        return claim

    @staticmethod
    def _validate_operation(value: Any, operation_id: str) -> Mapping[str, Any]:
        op = _exact(value, _OP_FIELDS, "supervised operation")
        if op.get("operation_id") != operation_id or op.get("capability") != CAPABILITY:
            _fail("invalid", "supervised operation identity is malformed")
        _token(op.get("request_id"), "operation request_id")
        _digest(op.get("request_digest"), "operation request_digest")
        _positive(op.get("owner_generation"), "operation owner_generation")
        _positive(op.get("source_claim_generation"), "operation source generation")
        _positive(op.get("target_claim_generation"), "operation target generation")
        _uuid(op.get("parent_uuid"), "operation parent UUID")
        _token(op.get("lineage_id"), "operation lineage_id")
        _positive(op.get("lineage_generation"), "operation lineage_generation")
        for key in ("source_profile_ref", "target_profile_ref", "source_runtime_incarnation",
                    "source_invocation_id", "source_domain_id", "supervisor_incarnation"):
            _token(op.get(key), "operation %s" % key)
        for key in ("source_manifest_digest", "target_manifest_digest"):
            _digest(op.get(key), "operation %s" % key)
        if op.get("phase") not in {
                "source-stopping", "reconciling", "ready-to-resume",
                "release-authorized", "target-starting", "target-observed",
                "released", "indeterminate"}:
            _fail("invalid", "supervised operation phase is malformed")
        if op.get("source_restart_denied") is not True:
            _fail("invalid", "supervised operation lacks its durable restart deny")
        _positive(op.get("owner_generation"), "operation owner_generation")
        if op.get("target_claim_generation") != op.get("source_claim_generation") + 1:
            _fail("invalid", "target claim generation is not the next generation")
        for key in ("worktree_ids", "job_ids"):
            values = op.get(key)
            if (not isinstance(values, list) or
                    any(not isinstance(item, str) for item in values) or
                    len(set(values)) != len(values)):
                _fail("invalid", "supervised operation %s is malformed" % key)
            for item in values:
                _token(item, "operation %s identity" % key)
        if op.get("source_exclusion") is not None:
            _exact(op["source_exclusion"], _SOURCE_EXCLUSION_FIELDS, "source exclusion witness")
        if op.get("history_manifest") is not None:
            _exact(op["history_manifest"], _HISTORY_FIELDS, "history manifest")
        if not isinstance(op.get("job_observations"), Mapping):
            _fail("invalid", "supervised operation job observations are malformed")
        if op.get("target_claim") is not None:
            target = _exact(op["target_claim"], _TARGET_CLAIM_FIELDS, "target claim")
            for key in ("claimant_id", "claim_token", "profile_ref"):
                _token(target.get(key), "target claim %s" % key)
            _uuid(target.get("parent_uuid"), "target claim parent UUID")
            _positive(target.get("claim_generation"), "target claim generation")
            _positive(target.get("owner_generation"), "target claim owner generation")
            _digest(target.get("manifest_digest"), "target claim manifest digest")
            expected_claim_digest = _hash({
                key: value for key, value in target.items() if key != "claim_digest"
            })
            if _digest(target.get("claim_digest"), "target claim digest") != expected_claim_digest:
                _fail("invalid", "target claim digest changed")
        if op.get("release_intent") is not None:
            release = _exact(op["release_intent"], _RELEASE_FIELDS, "release intent")
            for key in ("release_id",):
                _token(release.get(key), "release %s" % key)
            for key in ("release_digest", "claim_digest", "exclusion_digest",
                        "history_manifest_digest", "worktree_manifest_digest",
                        "job_observation_digest"):
                _digest(release.get(key), "release %s" % key)
            _positive(release.get("observation_watermark"),
                      "release observation watermark")
        if op.get("target_launch_intent") is not None:
            launch = _exact(op["target_launch_intent"], _TARGET_LAUNCH_FIELDS,
                            "target launch intent")
            for key in ("launch_intent_id", "profile_ref", "release_id"):
                _token(launch.get(key), "target launch %s" % key)
            _uuid(launch.get("parent_uuid"), "target launch parent UUID")
            _positive(launch.get("claim_generation"), "target launch generation")
            _positive(launch.get("owner_generation"), "target launch owner generation")
            _digest(launch.get("manifest_digest"), "target launch manifest digest")
            if launch.get("state") not in {"intent-recorded", "observed-running"}:
                _fail("invalid", "target launch state is malformed")
            for key in ("runtime_incarnation", "invocation_id", "domain_id"):
                if launch.get(key) is not None:
                    _token(launch.get(key), "target launch %s" % key)
            if launch.get("process_identity") is not None:
                _exact(launch.get("process_identity"), _PROCESS_FIELDS,
                       "target process identity")
            if launch.get("account_identity_digest") is not None:
                _digest(launch.get("account_identity_digest"),
                        "target account identity digest")
            observed_fields = ("runtime_incarnation", "invocation_id", "domain_id",
                               "process_identity", "account_identity_digest")
            if launch.get("state") == "intent-recorded" and any(
                    launch.get(key) is not None for key in observed_fields):
                _fail("invalid", "unobserved target launch contains runtime identity")
            if launch.get("state") == "observed-running":
                for key in ("runtime_incarnation", "invocation_id", "domain_id"):
                    _token(launch.get(key), "observed target launch %s" % key)
                _process_identity(launch.get("process_identity"),
                                  "target process identity", launch["domain_id"])
                _digest(launch.get("account_identity_digest"),
                        "observed target account identity digest")
        if op.get("uncertainty") is not None:
            _token(op.get("uncertainty"), "operation uncertainty")
        return op

    @staticmethod
    def _validate_job(value: Any, job_id: str) -> Mapping[str, Any]:
        job = _exact(value, _JOB_FIELDS, "supervised job")
        if job.get("job_id") != job_id:
            _fail("invalid", "supervised job ID changed")
        for key in ("request_id", "domain_id", "lineage_id"):
            _token(job.get(key), "job %s" % key)
        _digest(job.get("request_digest"), "job request_digest")
        _digest(job.get("command_digest"), "job command_digest")
        _uuid(job.get("parent_uuid"), "job parent UUID")
        _positive(job.get("owner_generation"), "job owner_generation")
        _positive(job.get("source_claim_generation"), "job source generation")
        _positive(job.get("lineage_generation"), "job lineage_generation")
        _nonnegative(job.get("observation_watermark"), "job observation watermark")
        if job.get("launch_state") not in {"not-dispatched", "intent-recorded", "observed"}:
            _fail("invalid", "supervised job launch state is malformed")
        if job.get("state") not in {"admitted", "launch-intent", "running", "completed", "failed", "uncertain"}:
            _fail("invalid", "supervised job state is malformed")
        if job.get("effect_state") not in {"none", "known", "unknown"}:
            _fail("invalid", "supervised job effect state is malformed")
        resources = job.get("resource_ids")
        if (not isinstance(resources, list) or not resources or
                any(not isinstance(item, str) for item in resources) or
                len(set(resources)) != len(resources)):
            _fail("invalid", "supervised job resources are malformed")
        for item in resources:
            _token(item, "job resource identity")
        launch_id = job.get("launch_intent_id")
        if launch_id is not None:
            _token(launch_id, "job launch_intent_id")
        process = job.get("process_identity")
        if process is not None:
            _process_identity(process, "job process identity", job["domain_id"])
        for key in ("output_ref",):
            if job.get(key) is not None:
                _token(job.get(key), "job %s" % key)
        if job.get("result_digest") is not None:
            _digest(job.get("result_digest"), "job result_digest")
        launch_state = job.get("launch_state")
        state = job.get("state")
        if ((state == "admitted" and launch_state != "not-dispatched") or
                (state == "launch-intent" and launch_state != "intent-recorded") or
                (state in {"running", "completed", "failed"} and
                 launch_state != "observed")):
            _fail("invalid", "supervised job launch state disagrees with job state")
        return job

    @staticmethod
    def _validate_cross_references(ledger: Mapping[str, Any]) -> None:
        """Validate ownership and reservation relationships on every reload."""
        generation = ledger["claim_generation"]
        current = ledger["current_claim"]
        if any(item > generation for item in ledger["retired_source_generations"]):
            _fail("invalid", "retired source generation exceeds the current generation")
        if current is None:
            if generation != 0:
                _fail("invalid", "claim generation exists without a current claim")
        else:
            if current.get("claim_generation") != generation:
                _fail("invalid", "current claim generation does not match ledger")
            retired = generation in ledger["retired_source_generations"]
            if current.get("state") in {"active", "target-active"} and retired:
                _fail("invalid", "active claim generation is marked retired")
            if current.get("state") in {"source-denied", "target-pending"} and not retired:
                _fail("invalid", "denied claim generation is not marked retired")

        unresolved = 0
        for operation in ledger["operations"].values():
            if operation.get("phase") not in {"released", "target-observed"}:
                unresolved += 1
            if operation["source_claim_generation"] not in ledger["retired_source_generations"]:
                _fail("invalid", "operation source generation is not restart-denied")
            target_claim = operation.get("target_claim")
            if target_claim is not None and (
                    target_claim.get("parent_uuid") != operation.get("parent_uuid") or
                    target_claim.get("claim_generation") !=
                    operation.get("target_claim_generation") or
                    target_claim.get("owner_generation") != operation.get("owner_generation") or
                    target_claim.get("profile_ref") != operation.get("target_profile_ref") or
                    target_claim.get("manifest_digest") !=
                    operation.get("target_manifest_digest")):
                _fail("invalid", "target claim is outside its operation binding")
            for job_id in operation["job_ids"]:
                job = ledger["jobs"].get(job_id)
                if not isinstance(job, Mapping):
                    _fail("invalid", "operation refers to a missing persistent job")
                releasable = (job.get("state") in {"completed", "failed"} and
                              job.get("effect_state") in {"none", "known"})
                if (job.get("parent_uuid") != operation.get("parent_uuid") or
                        job.get("owner_generation") != operation.get("owner_generation") or
                        job.get("source_claim_generation") >
                        operation.get("source_claim_generation") or
                        (job.get("source_claim_generation") <
                         operation.get("source_claim_generation") and
                         job.get("source_claim_generation") not in
                         ledger["retired_source_generations"]) or
                        job.get("lineage_id") != operation.get("lineage_id") or
                        job.get("lineage_generation") !=
                        operation.get("lineage_generation") or
                        (set(job.get("resource_ids", [])) -
                         set(operation.get("worktree_ids", [])) and not releasable)):
                    _fail("invalid", "operation job binding does not match its roster")
            if operation.get("release_intent") is not None:
                if (operation.get("target_claim") is None or
                        operation.get("target_launch_intent") is None):
                    _fail("invalid", "release intent lacks its target claim or launch intent")
            launch = operation.get("target_launch_intent")
            if launch is not None and (
                    launch.get("parent_uuid") != operation.get("parent_uuid") or
                    launch.get("claim_generation") !=
                    operation.get("target_claim_generation") or
                    launch.get("owner_generation") != operation.get("owner_generation") or
                    launch.get("profile_ref") != operation.get("target_profile_ref") or
                    launch.get("manifest_digest") !=
                    operation.get("target_manifest_digest")):
                _fail("invalid", "target launch intent is outside its operation binding")
        if unresolved > 1:
            _fail("invalid", "more than one supervised transition is unresolved")

        reservations = ledger["reservations"]
        for job_id, job in ledger["jobs"].items():
            releasable = (job.get("state") in {"completed", "failed"} and
                          job.get("effect_state") in {"none", "known"})
            for resource_id in job["resource_ids"]:
                reservation = reservations.get(resource_id)
                if releasable:
                    continue
                elif reservation != job_id:
                    _fail("invalid", "possibly-writing job lost its resource reservation")

        for operation in ledger["operations"].values():
            observations = operation.get("job_observations", {})
            if set(observations) - set(operation["job_ids"]):
                _fail("invalid", "operation contains an observation for an unlisted job")
            for job_id, observation in observations.items():
                job = ledger["jobs"].get(job_id)
                value = _exact(observation, _JOB_OBSERVATION_FIELDS,
                               "persisted job observation")
                observed_watermark = _positive(
                    value.get("observation_watermark"),
                    "persisted job observation watermark",
                )
                if (not isinstance(job, Mapping) or value.get("job_id") != job_id or
                        value.get("command_digest") != job.get("command_digest") or
                        value.get("domain_id") != job.get("domain_id") or
                        observed_watermark > ledger["observation_watermark"]):
                    _fail("invalid", "persisted job observation identity changed")
                _token(value.get("witness_id"), "persisted job witness_id")
                _digest(value.get("witness_digest"), "persisted job witness_digest")
                if value.get("state") not in {
                        "admitted", "launch-intent", "running", "completed", "failed", "uncertain"}:
                    _fail("invalid", "persisted job observation status is malformed")
                if value.get("effect_state") not in {"none", "known", "unknown"}:
                    _fail("invalid", "persisted job observation effects are malformed")
                if value.get("process_identity") is not None:
                    _process_identity(value.get("process_identity"),
                                      "persisted job process identity", job["domain_id"])
                if value.get("output_ref") is not None:
                    _token(value.get("output_ref"), "persisted job output reference")
                if value.get("result_digest") is not None:
                    _digest(value.get("result_digest"), "persisted job result digest")

    def _write(self, ledger: Dict[str, Any]) -> None:
        _seal_ledger(ledger)
        checked = self._load_envelope(ledger)
        encoded = _canonical(checked) + b"\n"
        self.store._atomic_write(self._path(), encoded)

    def _load_envelope(self, value: Any) -> Dict[str, Any]:
        if not isinstance(value, Mapping) or set(value) != _LEDGER_FIELDS:
            _fail("invalid", "supervised-jobs ledger fields are malformed")
        # Validate by the same path used for disk reads without depending on a
        # second owner read.  The enclosing transaction has just re-read owner.
        copy = _json(value)
        if copy.get("integrity_digest") != _hash({
                key: item for key, item in copy.items() if key != "integrity_digest"}):
            _fail("invalid", "supervised-jobs ledger digest is malformed")
        for operation_id, operation in copy["operations"].items():
            self._validate_operation(operation, operation_id)
        for job_id, job in copy["jobs"].items():
            self._validate_job(job, job_id)
        self._validate_cross_references(copy)
        return copy

    def _owner_current(self, owner: Mapping[str, Any], ledger: Mapping[str, Any]) -> None:
        if (owner.get("mode") != "managed" or
                owner.get("daemon_id") != ledger.get("daemon_id") or
                owner.get("generation") != ledger.get("owner_generation") or
                owner.get("process_domain") != ledger.get("process_domain")):
            _fail("stale-generation", "supervised-jobs owner or generation changed")

    def _registered_worktrees(self, lineage_id: str, lineage_generation: int,
                              parent_uuid: str, owner_generation: int) -> List[Dict[str, Any]]:
        claims = self.store._load_claims()
        identity = self.store.identity
        matches = []
        for claim in claims:
            if (claim.get("state") != "active" or
                    claim.get("lineage_id") != lineage_id or
                    claim.get("lineage_generation") != lineage_generation or
                    claim.get("coordinator_session_uuid") != parent_uuid or
                    claim.get("owner_generation") != owner_generation or
                    claim.get("lane_key") != identity.lane_key or
                    claim.get("host") != identity.host or
                    claim.get("common_dir") != str(identity.common_dir)):
                continue
            matches.append(_worktree_identity(claim))
        matches.sort(key=lambda row: row["resource_id"])
        if not matches:
            _fail("unknown", "no registered worktree claims match the source lineage")
        if len(matches) > _MAX_WORKTREES:
            _fail("busy", "registered worktree claim capacity is exhausted")
        return matches

    def _assert_registered_worktree_ids(
            self, *, lineage_id: str, lineage_generation: int,
            parent_uuid: str, owner_generation: int,
            expected_worktree_ids: Sequence[str]) -> None:
        """Compare the live global claim index with a persisted identity set.

        Callers hold ``ManagedStateStore``'s shared interprocess lock, so a
        claim transfer/removal cannot race this check and its state commit.
        """
        try:
            current = self._registered_worktrees(
                lineage_id, lineage_generation, parent_uuid, owner_generation,
            )
        except ManagedStateError:
            _fail("stale-generation", "registered worktree claims changed or are unavailable")
        actual_ids = [item["resource_id"] for item in current]
        if actual_ids != sorted(expected_worktree_ids):
            _fail("stale-generation", "registered worktree claims changed")

    @staticmethod
    def _source_claim_digest(claim: Mapping[str, Any]) -> str:
        return _hash({key: value for key, value in claim.items() if key != "state"})

    def _provider(self, name: str, binding: Mapping[str, Any], *args: Any) -> Mapping[str, Any]:
        provider = self.witness_provider
        method = getattr(provider, name, None) if provider is not None else None
        if not callable(method):
            _fail("unsupported", "trusted supervised-jobs %s provider is unavailable" % name)
        try:
            result = method(_json(binding), *args)
        except ManagedStateError:
            raise
        except Exception:
            # Provider exceptions may contain paths, command text or account
            # details.  Keep the persisted/public boundary intentionally terse.
            _fail("uncertain-effect", "trusted supervised-jobs observation failed")
        if not isinstance(result, Mapping):
            _fail("uncertain-effect", "supervised-jobs %s observation is malformed" % name)
        return result

    def _persistent_job_domain_id(self) -> str:
        provider = self.witness_provider
        value = getattr(provider, "persistent_job_domain_id", None) if provider is not None else None
        try:
            if callable(value):
                value = value()
        except ManagedStateError:
            raise
        except Exception:
            _fail("unsupported", "trusted persistent job domain identity is unavailable")
        if value is None:
            _fail("unsupported", "trusted persistent job domain identity is unavailable")
        return _token(value, "trusted persistent job domain identity")

    @staticmethod
    def _source_binding(ledger: Mapping[str, Any], operation: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "capability": CAPABILITY,
            "lane": ledger["lane"],
            "lane_key": ledger["lane_key"],
            "host": ledger["host"],
            "process_domain": ledger["process_domain"],
            "common_dir": ledger["common_dir"],
            "daemon_id": ledger["daemon_id"],
            "supervisor_incarnation": operation["supervisor_incarnation"],
            "owner_generation": operation["owner_generation"],
            "source_claim_generation": operation["source_claim_generation"],
            "parent_uuid": operation["parent_uuid"],
            "lineage_id": operation["lineage_id"],
            "lineage_generation": operation["lineage_generation"],
            "source_runtime_incarnation": operation["source_runtime_incarnation"],
            "source_invocation_id": operation["source_invocation_id"],
            "source_domain_id": operation["source_domain_id"],
            "source_manifest_digest": operation["source_manifest_digest"],
            "target_profile_ref": operation["target_profile_ref"],
            "target_manifest_digest": operation["target_manifest_digest"],
            "worktree_ids": list(operation["worktree_ids"]),
        }

    def claim_source(
            self, *, supervisor_incarnation: str, parent_uuid: str,
            lineage_id: str, lineage_generation: int, profile_ref: str,
            runtime_incarnation: str, invocation_id: str, domain_id: str,
            manifest_digest: str,
    ) -> Dict[str, Any]:
        """Record the one source runtime currently admitted by this ledger."""
        supervisor_incarnation = _token(supervisor_incarnation, "supervisor incarnation")
        parent_uuid = _uuid(parent_uuid, "source parent UUID")
        lineage_id = _token(lineage_id, "source lineage_id")
        lineage_generation = _positive(lineage_generation, "source lineage_generation")
        profile_ref = _token(profile_ref, "source profile_ref")
        runtime_incarnation = _token(runtime_incarnation, "source runtime incarnation")
        invocation_id = _token(invocation_id, "source invocation_id")
        domain_id = _token(domain_id, "source domain_id")
        manifest_digest = _digest(manifest_digest, "source launch manifest digest")
        with self._locked() as owner:
            if owner.get("lineage_id") not in (None, lineage_id):
                _fail("ownership-conflict", "source lineage does not match managed owner")
            if owner.get("coordinator_session_uuid") not in (None, parent_uuid):
                _fail("ownership-conflict", "source parent does not match managed owner")
            generation = _positive(owner.get("generation"), "managed owner generation")
            worktrees = self._registered_worktrees(
                lineage_id, lineage_generation, parent_uuid, generation,
            )
            worktree_ids = [item["resource_id"] for item in worktrees]
            ledger = self._load(
                owner, allow_absent=True,
                supervisor_incarnation=supervisor_incarnation,
            )
            if ledger is None:
                _fail("invalid", "supervised-jobs ledger initialization failed")
            if ledger["supervisor_incarnation"] != supervisor_incarnation:
                _fail("ownership-conflict", "supervisor incarnation changed")
            claim = {
                "claim_generation": 1 if ledger["claim_generation"] == 0 else ledger["claim_generation"],
                "parent_uuid": parent_uuid,
                "lineage_id": lineage_id,
                "lineage_generation": lineage_generation,
                "profile_ref": profile_ref,
                "runtime_incarnation": runtime_incarnation,
                "invocation_id": invocation_id,
                "domain_id": domain_id,
                "manifest_digest": manifest_digest,
                "worktree_ids": worktree_ids,
                "state": "active",
                "claimant_id": None,
            }
            if ledger["current_claim"] is not None:
                prior = ledger["current_claim"]
                if ({key: prior[key] for key in _CLAIM_FIELDS - {"state", "claimant_id"}} ==
                        {key: claim[key] for key in _CLAIM_FIELDS - {"state", "claimant_id"}} and
                        prior.get("state") == "active"):
                    return _json(prior)
                # A positively observed target start is already the current
                # generation.  Its first ordinary runtime claim may adopt
                # that exact identity, while retaining the winning B claimant
                # as audit data.  It cannot replace any bound identity.
                if (prior.get("state") == "target-active" and
                        {key: prior[key] for key in _CLAIM_FIELDS - {"state", "claimant_id"}} ==
                        {key: claim[key] for key in _CLAIM_FIELDS - {"state", "claimant_id"}}):
                    adopted = dict(prior)
                    adopted["state"] = "active"
                    ledger["current_claim"] = adopted
                    self._write(ledger)
                    return _json(adopted)
                _fail("ownership-conflict", "a different source runtime already owns the lane")
            if claim["claim_generation"] in ledger["retired_source_generations"]:
                _fail("stale-generation", "source generation is durably retired")
            ledger["claim_generation"] = claim["claim_generation"]
            ledger["current_claim"] = claim
            self._write(ledger)
            return _json(claim)

    def authorize_source_creation(
            self, *, claim_generation: int, parent_uuid: str,
            manifest_digest: str, runtime_incarnation: str,
    ) -> Dict[str, Any]:
        """Check a source identity against the durable fence before dispatch.

        This read-only check is not atomic with an external spawn.  A production
        caller must serialize the actual launch through the same supervisor
        fence; this foundation is not wired to any runtime creation path.
        """
        claim_generation = _positive(claim_generation, "source claim generation")
        parent_uuid = _uuid(parent_uuid, "source parent UUID")
        manifest_digest = _digest(manifest_digest, "source manifest digest")
        runtime_incarnation = _token(runtime_incarnation, "source runtime incarnation")
        with self._locked() as owner:
            ledger = self._load(owner)
            self._owner_current(owner, ledger)
            if claim_generation in ledger["retired_source_generations"]:
                _fail("ownership-conflict", "source generation is durably restart-denied")
            current = ledger["current_claim"]
            if (not isinstance(current, Mapping) or
                    current.get("claim_generation") != claim_generation or
                    current.get("parent_uuid") != parent_uuid or
                    current.get("manifest_digest") != manifest_digest or
                    current.get("runtime_incarnation") != runtime_incarnation or
                    current.get("state") != "active"):
                _fail("stale-generation", "source creation does not match the current source claim")
            self._assert_registered_worktree_ids(
                lineage_id=current["lineage_id"],
                lineage_generation=current["lineage_generation"],
                parent_uuid=current["parent_uuid"],
                owner_generation=ledger["owner_generation"],
                expected_worktree_ids=current["worktree_ids"],
            )
            return {"allowed": True, "claim_generation": claim_generation,
                    "parent_uuid": parent_uuid, "manifest_digest": manifest_digest}

    def admit_job(
            self, *, job_id: str, request_id: str, request_digest: str,
            parent_uuid: str, claim_generation: int, command_digest: str,
            resource_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Persist a directly admitted job and reserve its worktrees pre-launch.

        ``resource_ids=None`` conservatively reserves every registered
        worktree.  Only opaque command/result references are stored; no raw
        command environment or output is accepted.
        """
        job_id = _token(job_id, "job_id")
        request_id = _token(request_id, "job request_id")
        request_digest = _digest(request_digest, "job request digest")
        parent_uuid = _uuid(parent_uuid, "job parent UUID")
        claim_generation = _positive(claim_generation, "job source generation")
        command_digest = _digest(command_digest, "job command digest")
        if resource_ids is not None:
            if isinstance(resource_ids, (str, bytes)) or not isinstance(resource_ids, Sequence):
                _fail("invalid", "job resources must be a sequence of registered worktree IDs")
            requested_resources = list(resource_ids)
            for item in requested_resources:
                _token(item, "job resource identity")
            if len(requested_resources) != len(set(requested_resources)):
                _fail("invalid", "job resource list contains duplicates")
        else:
            requested_resources = None
        job_domain_id = self._persistent_job_domain_id()
        with self._locked() as owner:
            ledger = self._load(owner)
            current = ledger.get("current_claim")
            if (not isinstance(current, Mapping) or current.get("state") != "active" or
                    current.get("claim_generation") != claim_generation or
                    current.get("parent_uuid") != parent_uuid):
                _fail("stale-generation", "job admission is outside the current source claim")
            if claim_generation in ledger["retired_source_generations"]:
                _fail("ownership-conflict", "retired source cannot admit another job")
            self._assert_registered_worktree_ids(
                lineage_id=current["lineage_id"],
                lineage_generation=current["lineage_generation"],
                parent_uuid=current["parent_uuid"],
                owner_generation=ledger["owner_generation"],
                expected_worktree_ids=current["worktree_ids"],
            )
            known = set(current["worktree_ids"])
            selected = sorted(known if requested_resources is None else set(requested_resources))
            if not selected or set(selected) - known:
                _fail("ownership-conflict", "job resources are not registered worktrees")
            digest_input = {
                "job_id": job_id, "request_id": request_id,
                "request_digest": request_digest, "parent_uuid": parent_uuid,
                "owner_generation": ledger["owner_generation"],
                "source_claim_generation": claim_generation,
                "lineage_id": current["lineage_id"],
                "lineage_generation": current["lineage_generation"],
                "domain_id": job_domain_id,
                "command_digest": command_digest, "resource_ids": selected,
            }
            prior = ledger["jobs"].get(job_id)
            if prior is not None:
                if _hash({key: prior[key] for key in digest_input}) != _hash(digest_input):
                    _fail("ownership-conflict", "job ID was reused with changed intent")
                return _json(prior)
            if len(ledger["jobs"]) >= _MAX_JOBS:
                _fail("busy", "supervised job ledger capacity is exhausted")
            for resource_id in selected:
                existing_job = ledger["reservations"].get(resource_id)
                if existing_job is not None:
                    existing = ledger["jobs"].get(existing_job)
                    if (not isinstance(existing, Mapping) or
                            existing.get("state") not in {"completed", "failed"} or
                            existing.get("effect_state") not in {"none", "known"}):
                        _fail("busy", "registered worktree already has a possibly-writing job")
            job = {
                **digest_input,
                "launch_state": "not-dispatched",
                "launch_intent_id": None,
                "state": "admitted",
                "effect_state": "none",
                "observation_watermark": ledger["observation_watermark"],
                "process_identity": None,
                "output_ref": None,
                "result_digest": None,
            }
            ledger["jobs"][job_id] = job
            for resource_id in selected:
                ledger["reservations"][resource_id] = job_id
            self._write(ledger)
            return _json(job)

    def begin_job_launch(self, *, job_id: str, request_digest: str) -> Dict[str, Any]:
        """Durably consume the job's one launch intent before an OS spawn."""
        job_id = _token(job_id, "job_id")
        request_digest = _digest(request_digest, "job request digest")
        with self._locked() as owner:
            ledger = self._load(owner)
            self._owner_current(owner, ledger)
            job = ledger["jobs"].get(job_id)
            if not isinstance(job, Mapping):
                _fail("unknown", "supervised job is not admitted")
            current = ledger.get("current_claim")
            if (not isinstance(current, Mapping) or current.get("state") != "active" or
                    current.get("claim_generation") != job.get("source_claim_generation") or
                    current.get("parent_uuid") != job.get("parent_uuid") or
                    job.get("source_claim_generation") in ledger["retired_source_generations"]):
                _fail("ownership-conflict", "source generation is fenced from new job dispatch")
            self._assert_registered_worktree_ids(
                lineage_id=current["lineage_id"],
                lineage_generation=current["lineage_generation"],
                parent_uuid=current["parent_uuid"],
                owner_generation=ledger["owner_generation"],
                expected_worktree_ids=current["worktree_ids"],
            )
            if job.get("request_digest") != request_digest:
                _fail("ownership-conflict", "job launch request changed")
            if job.get("launch_state") != "not-dispatched" or job.get("state") != "admitted":
                _fail("uncertain-effect", "job launch intent was already consumed; do not replay")
            job = dict(job)
            job["launch_state"] = "intent-recorded"
            job["launch_intent_id"] = "job-launch-" + secrets.token_hex(16)
            job["state"] = "launch-intent"
            # This is a durable dispatch transition, not an OS observation.
            # Keep it out of the monotonic evidence watermark sequence.
            job["observation_watermark"] = ledger["observation_watermark"]
            ledger["jobs"][job_id] = job
            self._write(ledger)
            return _json(job)

    def prepare_swap(
            self, *, operation_id: str, request_id: str, request_digest: str,
            target_profile_ref: str, target_manifest_digest: str,
            parent_uuid: str, claim_generation: int,
    ) -> Dict[str, Any]:
        """Atomically fence the source generation before any stop dispatch."""
        operation_id = _token(operation_id, "supervised operation_id")
        request_id = _token(request_id, "supervised request_id")
        request_digest = _digest(request_digest, "supervised request digest")
        target_profile_ref = _token(target_profile_ref, "target profile_ref")
        target_manifest_digest = _digest(target_manifest_digest, "target manifest digest")
        parent_uuid = _uuid(parent_uuid, "target parent UUID")
        claim_generation = _positive(claim_generation, "source claim generation")
        with self._locked() as owner:
            ledger = self._load(owner)
            current = ledger.get("current_claim")
            request_binding = {
                "operation_id": operation_id, "request_id": request_id,
                "request_digest": request_digest,
                "target_profile_ref": target_profile_ref,
                "target_manifest_digest": target_manifest_digest,
                "parent_uuid": parent_uuid, "claim_generation": claim_generation,
            }
            intent_digest = _hash(request_binding)
            prior = ledger["operations"].get(operation_id)
            if prior is not None:
                if prior.get("request_digest") != intent_digest:
                    _fail("ownership-conflict", "operation ID was reused with changed intent")
                return _json(prior)
            if (not isinstance(current, Mapping) or current.get("state") != "active" or
                    current.get("claim_generation") != claim_generation or
                    current.get("parent_uuid") != parent_uuid):
                _fail("stale-generation", "swap does not match the current source claim")
            if claim_generation in ledger["retired_source_generations"]:
                _fail("ownership-conflict", "source generation was already restart-denied")
            self._assert_registered_worktree_ids(
                lineage_id=current["lineage_id"],
                lineage_generation=current["lineage_generation"],
                parent_uuid=current["parent_uuid"],
                owner_generation=ledger["owner_generation"],
                expected_worktree_ids=current["worktree_ids"],
            )
            if any(op.get("phase") not in {"released", "target-observed"}
                   for op in ledger["operations"].values()):
                _fail("busy", "another supervised account transition is unresolved")
            if len(ledger["operations"]) >= _MAX_OPERATIONS:
                _fail("busy", "supervised operation ledger capacity is exhausted")
            if current.get("claim_generation") in ledger["retired_source_generations"]:
                _fail("stale-generation", "source generation is already fenced")
            job_ids = []
            registered_resources = set(current["worktree_ids"])
            for job_id, job in ledger["jobs"].items():
                if (job.get("owner_generation") != ledger["owner_generation"] or
                        job.get("parent_uuid") != parent_uuid or
                        job.get("lineage_id") != current["lineage_id"]):
                    continue
                if job.get("source_claim_generation") > claim_generation:
                    _fail("stale-generation", "future-generation job exists for this lineage")
                if job.get("lineage_generation") != current["lineage_generation"]:
                    # A live writer from another worktree generation cannot be
                    # silently omitted from this transition's evidence roster.
                    if (job.get("state") not in {"completed", "failed"} or
                            job.get("effect_state") not in {"none", "known"}):
                        _fail("ownership-conflict",
                              "live job belongs to a different worktree generation")
                    continue
                if (set(job.get("resource_ids", [])) - registered_resources and
                        (job.get("state") not in {"completed", "failed"} or
                         job.get("effect_state") not in {"none", "known"})):
                    _fail("ownership-conflict",
                          "live job resources are outside the current registered worktrees")
                if (job.get("source_claim_generation") < claim_generation and
                        job.get("source_claim_generation") not in
                        ledger["retired_source_generations"]):
                    _fail("ownership-conflict",
                          "prior-generation job admission is not durably retired")
                job_ids.append(job_id)
            job_ids.sort()
            op = {
                "operation_id": operation_id,
                "request_id": request_id,
                "request_digest": intent_digest,
                "capability": CAPABILITY,
                "owner_generation": ledger["owner_generation"],
                "source_claim_generation": claim_generation,
                "target_claim_generation": claim_generation + 1,
                "parent_uuid": parent_uuid,
                "lineage_id": current["lineage_id"],
                "lineage_generation": current["lineage_generation"],
                "source_profile_ref": current["profile_ref"],
                "target_profile_ref": target_profile_ref,
                "source_runtime_incarnation": current["runtime_incarnation"],
                "source_invocation_id": current["invocation_id"],
                "source_domain_id": current["domain_id"],
                "source_manifest_digest": current["manifest_digest"],
                "target_manifest_digest": target_manifest_digest,
                "supervisor_incarnation": ledger["supervisor_incarnation"],
                "worktree_ids": list(current["worktree_ids"]),
                "job_ids": job_ids,
                "phase": "source-stopping",
                "source_restart_denied": True,
                "source_exclusion": None,
                "history_manifest": None,
                "job_observations": {},
                "target_claim": None,
                "release_intent": None,
                "target_launch_intent": None,
                "uncertainty": None,
            }
            ledger["operations"][operation_id] = op
            ledger["retired_source_generations"].append(claim_generation)
            current = dict(current)
            current["state"] = "source-denied"
            ledger["current_claim"] = current
            self._write(ledger)
            return _json(op)

    def _operation(self, ledger: Mapping[str, Any], operation_id: str) -> Mapping[str, Any]:
        operation_id = _token(operation_id, "supervised operation_id")
        operation = ledger["operations"].get(operation_id)
        if not isinstance(operation, Mapping):
            _fail("unknown", "supervised operation is unknown")
        if operation.get("owner_generation") != ledger.get("owner_generation"):
            _fail("stale-generation", "supervised operation owner generation changed")
        return operation

    def observe_source_exclusion(self, operation_id: str, *,
                                 refresh_ready: bool = False) -> Dict[str, Any]:
        """Ask the trusted OS provider for complete source-domain exclusion."""
        operation_id = _token(operation_id, "supervised operation_id")
        with self._locked() as owner:
            ledger = self._load(owner)
            operation = self._operation(ledger, operation_id)
            if operation.get("phase") == "ready-to-resume" and not refresh_ready:
                return _json(operation)
            if (operation.get("phase") not in
                    {"source-stopping", "reconciling", "indeterminate", "ready-to-resume"} or
                    operation.get("target_launch_intent") is not None or
                    operation.get("release_intent") is not None):
                _fail("busy", "source exclusion is not valid in this operation phase")
            if operation.get("source_restart_denied") is not True:
                _fail("ownership-conflict", "source restart fence is not durable")
            self._assert_registered_worktree_ids(
                lineage_id=operation["lineage_id"],
                lineage_generation=operation["lineage_generation"],
                parent_uuid=operation["parent_uuid"],
                owner_generation=operation["owner_generation"],
                expected_worktree_ids=operation["worktree_ids"],
            )
            binding = self._source_binding(ledger, operation)
            snapshot_digest = _hash(ledger)
        try:
            raw = self._provider("source_exclusion", binding)
            witness = _exact(raw, _SOURCE_EXCLUSION_FIELDS, "source exclusion witness")
            _token(witness["witness_id"], "source exclusion witness_id")
            _digest(witness["witness_digest"], "source exclusion witness_digest")
            watermark = _positive(witness["observation_watermark"], "source exclusion watermark")
            for key, expected in (
                ("source_runtime_incarnation", binding["source_runtime_incarnation"]),
                ("source_domain_id", binding["source_domain_id"]),
                ("supervisor_incarnation", binding["supervisor_incarnation"]),
                ("parent_uuid", binding["parent_uuid"]),
            ):
                if witness.get(key) != expected:
                    _fail("ownership-conflict", "source exclusion witness identity changed")
            active = witness.get("active_source_processes")
            if (witness.get("membership_complete") is not True or
                    witness.get("escape_coverage_complete") is not True or
                    isinstance(active, bool) or not isinstance(active, int) or active != 0 or
                    witness.get("restart_fence_effective") is not True or
                    witness.get("job_domain_live") is not True):
                _fail("unsupported", "source exclusion witness is incomplete")
            clean = {key: witness[key] for key in _SOURCE_EXCLUSION_FIELDS}
        except Exception as exc:
            with self._locked() as owner:
                ledger = self._load(owner)
                current = self._operation(ledger, operation_id)
                if _hash(ledger) == snapshot_digest and current.get("phase") != "released":
                    changed = dict(current)
                    changed["phase"] = "indeterminate"
                    changed["uncertainty"] = getattr(exc, "code", "source-exclusion-unverified")
                    ledger["operations"][operation_id] = changed
                    self._write(ledger)
            if isinstance(exc, ManagedStateError):
                raise
            _fail("uncertain-effect", "source exclusion observation is uncertain: %s" % exc)
        with self._locked() as owner:
            ledger = self._load(owner)
            operation = self._operation(ledger, operation_id)
            if _hash(ledger) != snapshot_digest:
                _fail("stale-generation", "supervised state changed during source observation")
            self._assert_registered_worktree_ids(
                lineage_id=operation["lineage_id"],
                lineage_generation=operation["lineage_generation"],
                parent_uuid=operation["parent_uuid"],
                owner_generation=operation["owner_generation"],
                expected_worktree_ids=operation["worktree_ids"],
            )
            if watermark <= ledger["observation_watermark"]:
                _fail("stale-generation", "source exclusion observation watermark is stale")
            changed = dict(operation)
            changed["source_exclusion"] = clean
            changed["phase"] = "reconciling"
            ledger["observation_watermark"] = watermark
            ledger["operations"][operation_id] = changed
            self._write(ledger)
            return _json(changed)

    def _validate_history_witness(self, value: Any, operation: Mapping[str, Any],
                                  watermark_floor: int) -> Dict[str, Any]:
        witness = _exact(value, _HISTORY_FIELDS, "history manifest witness")
        _token(witness["witness_id"], "history witness_id")
        _digest(witness["witness_digest"], "history witness_digest")
        if witness.get("parent_uuid") != operation["parent_uuid"]:
            _fail("ownership-conflict", "history manifest names another parent")
        _digest(witness["manifest_digest"], "history manifest digest")
        _digest(witness["worktree_manifest_digest"], "worktree manifest digest")
        watermark = _positive(witness["observation_watermark"], "history observation watermark")
        if watermark <= watermark_floor:
            _fail("stale-generation", "history observation watermark did not advance")
        if witness.get("complete") is not True:
            _fail("unsupported", "history manifest is incomplete")
        return _json(witness)

    def _validate_job_witness(self, value: Any, job: Mapping[str, Any],
                              watermark_floor: int) -> Dict[str, Any]:
        witness = _exact(value, _JOB_OBSERVATION_FIELDS, "job observation")
        _token(witness["witness_id"], "job witness_id")
        _digest(witness["witness_digest"], "job witness_digest")
        if witness.get("job_id") != job["job_id"]:
            _fail("ownership-conflict", "job witness names another job")
        if witness.get("command_digest") != job["command_digest"]:
            _fail("ownership-conflict", "job witness command digest changed")
        if witness.get("domain_id") != job["domain_id"]:
            _fail("ownership-conflict", "job witness domain changed")
        watermark = _positive(witness["observation_watermark"], "job observation watermark")
        if watermark <= max(watermark_floor, job["observation_watermark"]):
            _fail("stale-generation", "job observation watermark did not advance")
        state = witness.get("state")
        effect_state = witness.get("effect_state")
        if state not in {"admitted", "launch-intent", "running", "completed", "failed", "uncertain"}:
            _fail("unsupported", "job status is unknown")
        if effect_state not in {"none", "known", "unknown"}:
            _fail("unsupported", "job effect status is unknown")
        process = witness.get("process_identity")
        if state == "running":
            _process_identity(process, "job process identity", job["domain_id"])
        elif process is not None:
            _process_identity(process, "job process identity", job["domain_id"])
        launch_state = job["launch_state"]
        if launch_state == "not-dispatched":
            if state != "admitted" or effect_state != "none":
                _fail("uncertain-effect", "job has effects without a durable launch intent")
        elif state in {"admitted", "launch-intent"}:
            # Once the launch intent is durable, an absent process/result does
            # not prove that spawn did not happen.  Retrying or declaring ready
            # here could duplicate an execution whose ACK was lost.
            _fail("uncertain-effect", "consumed job launch intent lacks authoritative outcome")

        previous_state = job["state"]
        if previous_state in {"completed", "failed"} and state != previous_state:
            _fail("ownership-conflict", "terminal job status regressed or changed")
        if previous_state == "running" and state not in {
                "running", "completed", "failed", "uncertain"}:
            _fail("ownership-conflict", "running job status regressed")
        if (previous_state == "launch-intent" and state not in
                {"running", "completed", "failed", "uncertain"}):
            _fail("uncertain-effect", "job launch outcome remains unresolved")
        prior_process = job.get("process_identity")
        if prior_process is not None and process is not None and prior_process != process:
            _fail("ownership-conflict", "job process identity changed")
        if previous_state == "completed" and (
                witness.get("result_digest") != job.get("result_digest") or
                witness.get("output_ref") != job.get("output_ref")):
            _fail("ownership-conflict", "completed job result changed")
        if job.get("effect_state") == "known" and effect_state != "known":
            _fail("ownership-conflict", "known job effects regressed")
        if state == "completed":
            _digest(witness.get("result_digest"), "job result digest")
            _token(witness.get("output_ref"), "job output reference")
            if effect_state != "known":
                _fail("uncertain-effect", "completed job has unresolved effects")
        elif witness.get("result_digest") is not None:
            _digest(witness.get("result_digest"), "job result digest")
        if witness.get("output_ref") is not None:
            _token(witness.get("output_ref"), "job output reference")
        return _json(witness)

    @staticmethod
    def _apply_job_observation(ledger: Dict[str, Any],
                               observation: Mapping[str, Any]) -> None:
        job_id = observation["job_id"]
        job = dict(ledger["jobs"][job_id])
        job.update({
            "state": observation["state"],
            "effect_state": observation["effect_state"],
            "observation_watermark": observation["observation_watermark"],
            "process_identity": (observation["process_identity"]
                                 if observation["process_identity"] is not None
                                 else job.get("process_identity")),
            "output_ref": (observation["output_ref"]
                           if observation["output_ref"] is not None
                           else job.get("output_ref")),
            "result_digest": (observation["result_digest"]
                              if observation["result_digest"] is not None
                              else job.get("result_digest")),
            "launch_state": ("observed" if observation["state"] in
                             {"running", "completed", "failed"} else
                             job.get("launch_state")),
        })
        ledger["jobs"][job_id] = job
        if (job.get("state") in {"completed", "failed"} and
                job.get("effect_state") in {"none", "known"}):
            for resource_id in job["resource_ids"]:
                if ledger["reservations"].get(resource_id) == job_id:
                    del ledger["reservations"][resource_id]

    def observe_active_job(self, *, job_id: str, parent_uuid: str,
                           claim_generation: int,
                           runtime_incarnation: str) -> Dict[str, Any]:
        """Settle one trusted job result while its exact parent source is active.

        The caller supplies only the authenticated source tuple and job ID.
        Completion and effects come from the independent job witness; a stale
        source or uncertain result cannot free a worktree reservation.
        """
        job_id = _token(job_id, "job ID")
        parent_uuid = _uuid(parent_uuid, "job parent UUID")
        claim_generation = _positive(claim_generation, "active job claim generation")
        runtime_incarnation = _token(runtime_incarnation, "active job runtime")

        def active(ledger: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
            current = ledger.get("current_claim")
            job = ledger["jobs"].get(job_id)
            if (not isinstance(current, Mapping) or current.get("state") != "active" or
                    current.get("parent_uuid") != parent_uuid or
                    current.get("claim_generation") != claim_generation or
                    current.get("runtime_incarnation") != runtime_incarnation or
                    claim_generation in ledger["retired_source_generations"]):
                _fail("stale-generation", "job observation is outside the active source")
            if (not isinstance(job, Mapping) or
                    job.get("parent_uuid") != parent_uuid or
                    job.get("owner_generation") != ledger["owner_generation"] or
                    job.get("lineage_id") != current["lineage_id"] or
                    job.get("lineage_generation") != current["lineage_generation"] or
                    job.get("source_claim_generation", 0) > claim_generation or
                    not set(job.get("resource_ids", [])).issubset(set(current["worktree_ids"]))):
                _fail("ownership-conflict", "job is outside the active source lineage")
            self._assert_registered_worktree_ids(
                lineage_id=current["lineage_id"],
                lineage_generation=current["lineage_generation"],
                parent_uuid=parent_uuid, owner_generation=ledger["owner_generation"],
                expected_worktree_ids=current["worktree_ids"],
            )
            return current, job

        with self._locked() as owner:
            ledger = self._load(owner)
            current, job = active(ledger)
            binding = {
                "capability": CAPABILITY,
                "owner_generation": ledger["owner_generation"],
                "parent_uuid": parent_uuid,
                "lineage_id": current["lineage_id"],
                "lineage_generation": current["lineage_generation"],
                "source_claim_generation": claim_generation,
                "source_runtime_incarnation": runtime_incarnation,
                "worktree_ids": list(current["worktree_ids"]),
            }
            floor = ledger["observation_watermark"]
            snapshot_digest = _hash(ledger)
            job_snapshot = _json(job)
        observation = self._validate_job_witness(
            self._provider("job_status", binding, job_id), job_snapshot, floor,
        )
        with self._locked() as owner:
            ledger = self._load(owner)
            active(ledger)
            if _hash(ledger) != snapshot_digest:
                _fail("stale-generation", "active job changed during observation")
            self._apply_job_observation(ledger, observation)
            ledger["observation_watermark"] = observation["observation_watermark"]
            self._write(ledger)
            if (observation["state"] == "uncertain" or
                    observation["effect_state"] == "unknown"):
                _fail("uncertain-effect", "active job effects remain unknown")
            return _json(ledger["jobs"][job_id])

    def reconcile(self, operation_id: str) -> Dict[str, Any]:
        """Settle jobs first, then witness the resulting worktree before ready."""
        operation_id = _token(operation_id, "supervised operation_id")
        with self._locked() as owner:
            ledger = self._load(owner)
            operation = self._operation(ledger, operation_id)
            if operation.get("phase") == "ready-to-resume":
                return _json(operation)
            if operation.get("phase") != "reconciling" or not isinstance(
                    operation.get("source_exclusion"), Mapping):
                _fail("busy", "source must be excluded before reconciliation")
            if operation.get("target_launch_intent") is not None:
                _fail("busy", "target startup intent cannot be reconciled as a job operation")
            self._assert_registered_worktree_ids(
                lineage_id=operation["lineage_id"],
                lineage_generation=operation["lineage_generation"],
                parent_uuid=operation["parent_uuid"],
                owner_generation=operation["owner_generation"],
                expected_worktree_ids=operation["worktree_ids"],
            )
            binding = self._source_binding(ledger, operation)
            jobs = {job_id: _json(ledger["jobs"][job_id]) for job_id in operation["job_ids"]}
            watermark_floor = ledger["observation_watermark"]
            snapshot_digest = _hash(ledger)
        try:
            observations: Dict[str, Dict[str, Any]] = {}
            for job_id in sorted(jobs):
                job = jobs[job_id]
                observation = self._validate_job_witness(
                    self._provider("job_status", binding, job_id),
                    job,
                    watermark_floor,
                )
                watermark_floor = observation["observation_watermark"]
                observations[job_id] = observation
            unknown = [job_id for job_id, value in observations.items()
                       if value["state"] == "uncertain" or value["effect_state"] == "unknown"]
        except Exception as exc:
            with self._locked() as owner:
                ledger = self._load(owner)
                operation = self._operation(ledger, operation_id)
                if _hash(ledger) == snapshot_digest:
                    changed = dict(operation)
                    changed["phase"] = "indeterminate"
                    changed["uncertainty"] = getattr(exc, "code", "job-reconciliation-unknown")
                    ledger["operations"][operation_id] = changed
                    self._write(ledger)
            if isinstance(exc, ManagedStateError):
                raise
            _fail("uncertain-effect", "job reconciliation is uncertain: %s" % exc)
        with self._locked() as owner:
            ledger = self._load(owner)
            operation = self._operation(ledger, operation_id)
            if _hash(ledger) != snapshot_digest:
                _fail("stale-generation", "supervised state changed during reconciliation")
            self._assert_registered_worktree_ids(
                lineage_id=operation["lineage_id"],
                lineage_generation=operation["lineage_generation"],
                parent_uuid=operation["parent_uuid"],
                owner_generation=operation["owner_generation"],
                expected_worktree_ids=operation["worktree_ids"],
            )
            for observation in observations.values():
                self._apply_job_observation(ledger, observation)
            changed = dict(operation)
            changed["job_observations"] = observations
            if unknown:
                changed["phase"] = "indeterminate"
                changed["uncertainty"] = "job-effects-unknown"
            else:
                # A terminal job may have cleared its worktree reservation.
                # Persist that settlement before observing history, so ready
                # never holds a digest of the old reservation set.
                changed["phase"] = "reconciling"
                changed["uncertainty"] = None
            ledger["observation_watermark"] = watermark_floor
            ledger["operations"][operation_id] = changed
            self._write(ledger)
            settled_digest = _hash(ledger)
            if unknown:
                _fail("uncertain-effect", "job effects are unknown; target release is blocked")
            binding = self._source_binding(ledger, changed)
        try:
            history = self._validate_history_witness(
                self._provider("history_manifest", binding), changed, watermark_floor,
            )
            prior_history = changed.get("history_manifest")
            if (isinstance(prior_history, Mapping) and
                    prior_history["manifest_digest"] != history["manifest_digest"]):
                _fail("ownership-conflict", "native parent or child history changed after first reconciliation")
        except Exception as exc:
            with self._locked() as owner:
                ledger = self._load(owner)
                operation = self._operation(ledger, operation_id)
                if _hash(ledger) == settled_digest:
                    failed = dict(operation)
                    failed["phase"] = "indeterminate"
                    failed["uncertainty"] = getattr(exc, "code", "history-reconciliation-unknown")
                    ledger["operations"][operation_id] = failed
                    self._write(ledger)
            if isinstance(exc, ManagedStateError):
                raise
            _fail("uncertain-effect", "history reconciliation is uncertain: %s" % exc)
        with self._locked() as owner:
            ledger = self._load(owner)
            operation = self._operation(ledger, operation_id)
            if _hash(ledger) != settled_digest:
                _fail("stale-generation", "supervised state changed during history observation")
            self._assert_registered_worktree_ids(
                lineage_id=operation["lineage_id"],
                lineage_generation=operation["lineage_generation"],
                parent_uuid=operation["parent_uuid"],
                owner_generation=operation["owner_generation"],
                expected_worktree_ids=operation["worktree_ids"],
            )
            ready = dict(operation)
            ready["history_manifest"] = history
            ready["phase"] = "ready-to-resume"
            ready["uncertainty"] = None
            ledger["observation_watermark"] = history["observation_watermark"]
            ledger["operations"][operation_id] = ready
            self._write(ledger)
            return _json(ready)

    def claim_target(
            self, *, operation_id: str, claimant_id: str, parent_uuid: str,
            owner_generation: int, claim_generation: int, profile_ref: str,
            manifest_digest: str,
    ) -> Dict[str, Any]:
        """CAS the unique B owner against exact parent, generations and manifest."""
        operation_id = _token(operation_id, "supervised operation_id")
        claimant_id = _token(claimant_id, "target claimant_id")
        parent_uuid = _uuid(parent_uuid, "target parent UUID")
        owner_generation = _positive(owner_generation, "target owner generation")
        claim_generation = _positive(claim_generation, "target claim generation")
        profile_ref = _token(profile_ref, "target profile_ref")
        manifest_digest = _digest(manifest_digest, "target manifest digest")
        with self._locked() as owner:
            ledger = self._load(owner)
            operation = self._operation(ledger, operation_id)
            if operation.get("phase") != "ready-to-resume":
                _fail("busy", "target claim requires ready-to-resume")
            if (owner_generation != operation["owner_generation"] or
                    claim_generation != operation["target_claim_generation"]):
                _fail("stale-generation", "target claim generation is not authorized")
            if (parent_uuid != operation["parent_uuid"] or
                    profile_ref != operation["target_profile_ref"] or
                    manifest_digest != operation["target_manifest_digest"]):
                _fail("ownership-conflict", "target parent, profile or manifest changed")
            self._assert_registered_worktree_ids(
                lineage_id=operation["lineage_id"],
                lineage_generation=operation["lineage_generation"],
                parent_uuid=operation["parent_uuid"],
                owner_generation=operation["owner_generation"],
                expected_worktree_ids=operation["worktree_ids"],
            )
            candidate = {
                "claimant_id": claimant_id,
                "claim_token": "target-claim-" + secrets.token_hex(16),
                "parent_uuid": parent_uuid,
                "claim_generation": claim_generation,
                "owner_generation": owner_generation,
                "profile_ref": profile_ref,
                "manifest_digest": manifest_digest,
                "claim_digest": "",
            }
            candidate["claim_digest"] = _hash({
                key: value for key, value in candidate.items() if key != "claim_digest"
            })
            previous = operation.get("target_claim")
            if previous is not None:
                if (previous.get("claimant_id") == claimant_id and
                        {key: previous[key] for key in _TARGET_CLAIM_FIELDS - {"claim_token", "claim_digest"}} ==
                        {key: candidate[key] for key in _TARGET_CLAIM_FIELDS - {"claim_token", "claim_digest"}}):
                    return _json(previous)
                _fail("ownership-conflict", "a different target runtime already claimed this operation")
            changed = dict(operation)
            changed["target_claim"] = candidate
            ledger["operations"][operation_id] = changed
            self._write(ledger)
            return _json(candidate)

    def _fresh_release_observations(
            self, ledger: Mapping[str, Any], operation: Mapping[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Dict[str, Any]], int]:
        binding = self._source_binding(ledger, operation)
        floor = ledger["observation_watermark"]
        raw_exclusion = _exact(
            self._provider("source_exclusion", binding),
            _SOURCE_EXCLUSION_FIELDS, "source exclusion witness",
        )
        exclusion = _json(raw_exclusion)
        _token(exclusion["witness_id"], "source exclusion witness_id")
        _digest(exclusion["witness_digest"], "source exclusion witness_digest")
        source_watermark = _positive(
            exclusion["observation_watermark"], "source exclusion watermark",
        )
        if source_watermark <= floor:
            _fail("stale-generation", "release source exclusion watermark is stale")
        floor = source_watermark
        expected = {
            "source_runtime_incarnation": operation["source_runtime_incarnation"],
            "source_domain_id": operation["source_domain_id"],
            "supervisor_incarnation": operation["supervisor_incarnation"],
            "parent_uuid": operation["parent_uuid"],
        }
        if any(exclusion.get(key) != value for key, value in expected.items()):
            _fail("ownership-conflict", "fresh source exclusion identity changed")
        active = exclusion.get("active_source_processes")
        if (exclusion.get("membership_complete") is not True or
                exclusion.get("escape_coverage_complete") is not True or
                isinstance(active, bool) or not isinstance(active, int) or active != 0 or
                exclusion.get("restart_fence_effective") is not True or
                exclusion.get("job_domain_live") is not True):
            _fail("unsupported", "fresh source exclusion witness is incomplete")
        history = self._validate_history_witness(
            self._provider("history_manifest", binding), operation, floor,
        )
        floor = history["observation_watermark"]
        prior_history = operation.get("history_manifest")
        if (not isinstance(prior_history, Mapping) or
                history["manifest_digest"] != prior_history["manifest_digest"] or
                history["worktree_manifest_digest"] != prior_history["worktree_manifest_digest"]):
            _fail("ownership-conflict", "history or worktree manifest changed before release")
        observations = {}
        for job_id in sorted(operation["job_ids"]):
            job = ledger["jobs"].get(job_id)
            if not isinstance(job, Mapping):
                _fail("invalid", "operation refers to an absent persistent job")
            observation = self._validate_job_witness(
                self._provider("job_status", binding, job_id), job, floor,
            )
            floor = observation["observation_watermark"]
            if observation["state"] == "uncertain" or observation["effect_state"] == "unknown":
                _fail("uncertain-effect", "job effect became unknown before release")
            previous = operation["job_observations"].get(job_id)
            if (not isinstance(previous, Mapping) or
                    previous.get("command_digest") != observation["command_digest"] or
                    previous.get("domain_id") != observation["domain_id"]):
                _fail("ownership-conflict", "job identity changed before release")
            observations[job_id] = observation
        return exclusion, history, observations, floor

    def authorize_release(
            self, *, operation_id: str, release_id: str,
            target_claim_token: str,
    ) -> Dict[str, Any]:
        """Persist explicit release and the sole target launch intent atomically.

        This method writes intent only.  It never starts a CLI process.  A
        duplicate identical release observes its first intent; a changed ID or
        claim cannot obtain another launch intent.
        """
        operation_id = _token(operation_id, "supervised operation_id")
        release_id = _token(release_id, "release_id")
        target_claim_token = _token(target_claim_token, "target claim token")
        with self._locked() as owner:
            ledger = self._load(owner)
            operation = self._operation(ledger, operation_id)
            existing = operation.get("release_intent")
            release_request_digest = _hash({
                "operation_id": operation_id,
                "release_id": release_id,
                "target_claim_token": target_claim_token,
            })
            if existing is not None:
                if existing.get("release_digest") != release_request_digest:
                    _fail("ownership-conflict", "release replay changed its authorization")
                return _json(operation["target_launch_intent"])
            if operation.get("phase") != "ready-to-resume":
                _fail("busy", "explicit release requires ready-to-resume")
            claim = operation.get("target_claim")
            if not isinstance(claim, Mapping) or claim.get("claim_token") != target_claim_token:
                _fail("ownership-conflict", "release does not hold the unique target claim")
            self._assert_registered_worktree_ids(
                lineage_id=operation["lineage_id"],
                lineage_generation=operation["lineage_generation"],
                parent_uuid=operation["parent_uuid"],
                owner_generation=operation["owner_generation"],
                expected_worktree_ids=operation["worktree_ids"],
            )
            snapshot_digest = _hash(ledger)
            operation_snapshot = _json(operation)
            ledger_snapshot = _json(ledger)
        try:
            exclusion, history, jobs, watermark = self._fresh_release_observations(
                ledger_snapshot, operation_snapshot,
            )
        except Exception as exc:
            with self._locked() as owner:
                current = self._load(owner)
                op = current["operations"].get(operation_id)
                if _hash(current) == snapshot_digest and isinstance(op, Mapping):
                    changed = dict(op)
                    changed["phase"] = "indeterminate"
                    changed["uncertainty"] = getattr(exc, "code", "release-observation-unknown")
                    current["operations"][operation_id] = changed
                    self._write(current)
            if isinstance(exc, ManagedStateError):
                raise
            _fail("uncertain-effect", "release observations are uncertain: %s" % exc)
        with self._locked() as owner:
            ledger = self._load(owner)
            operation = self._operation(ledger, operation_id)
            if _hash(ledger) != snapshot_digest:
                _fail("stale-generation", "supervised state changed during release validation")
            claim = operation.get("target_claim")
            if not isinstance(claim, Mapping) or claim.get("claim_token") != target_claim_token:
                _fail("ownership-conflict", "target claim changed during release validation")
            try:
                self._assert_registered_worktree_ids(
                    lineage_id=operation["lineage_id"],
                    lineage_generation=operation["lineage_generation"],
                    parent_uuid=operation["parent_uuid"],
                    owner_generation=operation["owner_generation"],
                    expected_worktree_ids=operation["worktree_ids"],
                )
            except ManagedStateError:
                changed = dict(operation)
                changed["phase"] = "indeterminate"
                changed["uncertainty"] = "registered-worktree-claims-changed"
                ledger["operations"][operation_id] = changed
                self._write(ledger)
                _fail("stale-generation",
                      "registered worktree claims changed during release observation")
            if watermark <= ledger["observation_watermark"]:
                _fail("stale-generation", "release evidence watermark did not advance")
            job_projection = {job_id: value for job_id, value in sorted(jobs.items())}
            release = {
                "release_id": release_id,
                "release_digest": release_request_digest,
                "claim_digest": claim["claim_digest"],
                "exclusion_digest": exclusion["witness_digest"],
                "history_manifest_digest": history["manifest_digest"],
                "worktree_manifest_digest": history["worktree_manifest_digest"],
                "job_observation_digest": _hash(job_projection),
                "observation_watermark": watermark,
            }
            launch = {
                "launch_intent_id": "target-launch-" + secrets.token_hex(16),
                "parent_uuid": operation["parent_uuid"],
                "claim_generation": operation["target_claim_generation"],
                "owner_generation": operation["owner_generation"],
                "profile_ref": operation["target_profile_ref"],
                "manifest_digest": operation["target_manifest_digest"],
                "release_id": release_id,
                "state": "intent-recorded",
                "runtime_incarnation": None,
                "invocation_id": None,
                "domain_id": None,
                "process_identity": None,
                "account_identity_digest": None,
            }
            for observation in jobs.values():
                self._apply_job_observation(ledger, observation)
            changed = dict(operation)
            changed["release_intent"] = release
            changed["target_launch_intent"] = launch
            changed["phase"] = "target-starting"
            changed["source_exclusion"] = exclusion
            changed["history_manifest"] = history
            changed["job_observations"] = jobs
            ledger["observation_watermark"] = watermark
            ledger["operations"][operation_id] = changed
            source = dict(ledger["current_claim"])
            source["state"] = "target-pending"
            ledger["current_claim"] = source
            self._write(ledger)
            return _json(launch)

    def observe_target_start(self, operation_id: str) -> Dict[str, Any]:
        """Reconcile an already-persisted launch intent; never launch again."""
        operation_id = _token(operation_id, "supervised operation_id")
        with self._locked() as owner:
            ledger = self._load(owner)
            operation = self._operation(ledger, operation_id)
            if operation.get("phase") in {"released", "target-observed"}:
                return _json(operation["target_launch_intent"])
            if (operation.get("phase") not in {"target-starting", "indeterminate"} or
                    not isinstance(operation.get("target_launch_intent"), Mapping)):
                _fail("busy", "target startup observation has no durable launch intent")
            self._assert_registered_worktree_ids(
                lineage_id=operation["lineage_id"],
                lineage_generation=operation["lineage_generation"],
                parent_uuid=operation["parent_uuid"],
                owner_generation=operation["owner_generation"],
                expected_worktree_ids=operation["worktree_ids"],
            )
            binding = {
                "capability": CAPABILITY,
                "operation_id": operation_id,
                "owner_generation": operation["owner_generation"],
                "target_claim_generation": operation["target_claim_generation"],
                "parent_uuid": operation["parent_uuid"],
                "profile_ref": operation["target_profile_ref"],
                "manifest_digest": operation["target_manifest_digest"],
                "launch_intent_id": operation["target_launch_intent"]["launch_intent_id"],
                "supervisor_incarnation": operation["supervisor_incarnation"],
            }
            snapshot_digest = _hash(ledger)
        try:
            status = self._provider("target_status", binding)
            expected_fields = {
                "witness_id", "witness_digest", "observation_watermark", "state",
                "parent_uuid", "profile_ref", "manifest_digest", "claim_generation",
                "runtime_incarnation", "invocation_id", "domain_id",
                "process_identity", "account_identity_digest",
            }
            status = _exact(status, frozenset(expected_fields), "target status witness")
            _token(status["witness_id"], "target witness_id")
            _digest(status["witness_digest"], "target witness_digest")
            watermark = _positive(status["observation_watermark"], "target status watermark")
            matches = (
                status.get("state") == "running" and
                status.get("parent_uuid") == binding["parent_uuid"] and
                status.get("profile_ref") == binding["profile_ref"] and
                status.get("manifest_digest") == binding["manifest_digest"] and
                status.get("claim_generation") == binding["target_claim_generation"]
            )
            if not matches:
                _fail("uncertain-effect", "target startup is not positively reconciled")
            domain_id = _token(status.get("domain_id"), "target process domain")
            runtime_incarnation = _token(status.get("runtime_incarnation"),
                                         "target runtime incarnation")
            invocation_id = _token(status.get("invocation_id"), "target invocation_id")
            process = _process_identity(status.get("process_identity"),
                                        "target process identity", domain_id)
            account_digest = _digest(status.get("account_identity_digest"),
                                      "target account identity digest")
        except Exception as exc:
            with self._locked() as owner:
                ledger = self._load(owner)
                operation = self._operation(ledger, operation_id)
                if _hash(ledger) == snapshot_digest:
                    changed = dict(operation)
                    changed["phase"] = "indeterminate"
                    changed["uncertainty"] = getattr(exc, "code", "target-start-unknown")
                    ledger["operations"][operation_id] = changed
                    self._write(ledger)
            if isinstance(exc, ManagedStateError):
                raise
            _fail("uncertain-effect", "target startup is uncertain: %s" % exc)
        with self._locked() as owner:
            ledger = self._load(owner)
            operation = self._operation(ledger, operation_id)
            if _hash(ledger) != snapshot_digest:
                _fail("stale-generation", "supervised state changed during target observation")
            try:
                self._assert_registered_worktree_ids(
                    lineage_id=operation["lineage_id"],
                    lineage_generation=operation["lineage_generation"],
                    parent_uuid=operation["parent_uuid"],
                    owner_generation=operation["owner_generation"],
                    expected_worktree_ids=operation["worktree_ids"],
                )
            except ManagedStateError:
                changed = dict(operation)
                changed["phase"] = "indeterminate"
                changed["uncertainty"] = "registered-worktree-claims-changed"
                ledger["operations"][operation_id] = changed
                self._write(ledger)
                _fail("stale-generation",
                      "registered worktree claims changed during target observation")
            if watermark <= ledger["observation_watermark"]:
                _fail("stale-generation", "target status watermark is stale")
            launch = dict(operation["target_launch_intent"])
            launch["state"] = "observed-running"
            launch["runtime_incarnation"] = runtime_incarnation
            launch["invocation_id"] = invocation_id
            launch["domain_id"] = domain_id
            launch["process_identity"] = process
            launch["account_identity_digest"] = account_digest
            changed = dict(operation)
            changed["target_launch_intent"] = launch
            # This private foundation records target-process observation only.
            # Native child continuation/result delivery is not represented
            # here, so this must not be mistaken for product lifecycle release.
            changed["phase"] = "target-observed"
            changed["uncertainty"] = None
            ledger["operations"][operation_id] = changed
            ledger["observation_watermark"] = watermark
            target = dict(ledger["current_claim"])
            target.update({
                "claim_generation": operation["target_claim_generation"],
                "parent_uuid": operation["parent_uuid"],
                "profile_ref": operation["target_profile_ref"],
                "runtime_incarnation": runtime_incarnation,
                "invocation_id": invocation_id,
                "domain_id": domain_id,
                "manifest_digest": operation["target_manifest_digest"],
                "state": "target-active",
                "claimant_id": operation["target_claim"]["claimant_id"],
            })
            ledger["claim_generation"] = operation["target_claim_generation"]
            ledger["current_claim"] = target
            self._write(ledger)
            return _json(launch)

    def status(self) -> Dict[str, Any]:
        """Return only validated, bounded ledger state; this method is read-only."""
        with self._locked() as owner:
            ledger = self._load(owner)
            return _json(ledger)
