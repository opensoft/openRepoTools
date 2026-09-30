# SPDX-License-Identifier: Apache-2.0
"""Foundation for one-shot T053-admitted persistent jobs.

This module is private. The local Linux supervisor domain and MCP bridge live
in ``lane_managed_local_jobs``; callers must run them in the persistent
supervisor, independently of every source CLI. A trusted
``JobExecutionDomain`` must launch a new subprocess outside the source domain,
bound its output, read fresh PID/start/domain identity, and prove that the
whole job subtree has drained before returning a terminal result. Without that
authority the runner is unsupported. It never adopts a caller PID or retries
a consumed T053 launch intent.

Only digests, process identity, opaque output references, and bounded result
metadata are stored in the runner journal. Command arguments and environment
values are never persisted here or in the T053 ledger.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence

from lane_managed_state import ManagedStateError
from lane_managed_supervised_jobs import CAPABILITY, ClaudeCliSupervisedJobsLedger


RUNNER_SCHEMA_VERSION = 1
DEFAULT_OUTPUT_LIMIT = 256 * 1024
MAX_OUTPUT_LIMIT = 1024 * 1024
MAX_COMMAND_ITEMS = 128
MAX_COMMAND_TEXT = 64 * 1024
MAX_ENV_ITEMS = 16
MAX_ENV_TEXT = 16 * 1024
MAX_WAIT_SECONDS = 3600.0
SPAWN_TIMEOUT_SECONDS = 8.0

_TOKEN = re.compile(r"[^\x00-\x1f\x7f]{1,256}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_OUTPUT_REF = re.compile(r"job-output-[0-9a-f]{40}\Z")
_SAFE_ENV_KEYS = frozenset({"PATH", "LANG", "LC_ALL", "TZ"})
_PROCESS_FIELDS = frozenset({"pid", "start_token", "domain_id"})
_RECORD_FIELDS = frozenset({
    "schema_version", "job_id", "request_digest", "command_digest",
    "domain_id", "launch_intent_id", "process_identity", "output_ref",
    "state", "uncertainty", "exit_code", "output_digest", "output_size",
    "output_truncated", "result_digest", "integrity_digest",
})
_OBSERVATION_FIELDS = frozenset({
    "witness_id", "witness_digest", "job_id", "command_digest", "domain_id",
    "observation_watermark", "state", "effect_state", "process_identity",
    "output_ref", "result_digest",
})


def _fail(code: str, message: str) -> None:
    raise ManagedStateError(code, message)


def _canonical(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        _fail("invalid", "managed job value is not bounded JSON data")
    if len(encoded) > 1024 * 1024:
        _fail("invalid", "managed job value exceeds its size bound")
    return encoded


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
        _fail("invalid", "%s is malformed" % label)
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        _fail("invalid", "%s is malformed" % label)
    return value


def _process_identity(value: Any, *, expected_pid: Optional[int],
                      expected_domain: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _PROCESS_FIELDS:
        _fail("uncertain-effect", "job process identity is incomplete")
    pid = value.get("pid")
    if (isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0 or
            (expected_pid is not None and pid != expected_pid)):
        _fail("ownership-conflict", "job process identity does not match its launch")
    start_token = _token(value.get("start_token"), "job process start identity")
    domain_id = _token(value.get("domain_id"), "job process domain identity")
    if domain_id != expected_domain:
        _fail("ownership-conflict", "job process is outside its admitted domain")
    return {"pid": pid, "start_token": start_token, "domain_id": domain_id}


class JobExecutionDomain(Protocol):
    """Trusted OS authority. Implementations without these proofs refuse.

    ``launch_new`` starts a new child directly in the persistent job domain;
    it never accepts a PID for adoption. It binds stdout and stderr to
    ``output_fd`` and enforces the supplied limit in the child. Process
    identity is freshly read from the OS. ``wait_result`` only reports a
    leader exit; the runner separately requires ``job_subtree_empty`` before
    publishing any terminal result. A false or unavailable drain witness
    retains uncertainty and the T053 resource reservation.

    ``job_status_witness`` produces the exact T053 job observation, including
    fresh effect evidence and a watermark from the same authority used by the
    source/history witnesses. A process result alone never claims effects are
    known.
    """

    persistent_job_domain_id: str

    def assert_ready(self) -> None: ...

    def launch_new(self, *, job_id: str, launch_intent_id: str,
                   argv: Sequence[str], cwd: str, environment: Mapping[str, str],
                   output_fd: int, output_limit_bytes: int,
                   deadline: float) -> int: ...

    def read_process_identity(self, pid: int) -> Mapping[str, Any]: ...

    def process_is_running(self, process_identity: Mapping[str, Any]) -> bool: ...

    def wait_result(self, *, job_id: str,
                    process_identity: Mapping[str, Any], timeout: float
                    ) -> Optional[Mapping[str, Any]]: ...

    def job_subtree_empty(self, *, job_id: str,
                          process_identity: Mapping[str, Any]) -> bool: ...

    def job_status_witness(self, *, binding: Mapping[str, Any], job_id: str,
                           process_identity: Optional[Mapping[str, Any]],
                           output_ref: Optional[str], result_digest: Optional[str],
                           minimum_watermark: int) -> Mapping[str, Any]: ...


class ManagedJobRunner:
    """Admit once, launch once, and keep bounded result custody privately."""

    def __init__(self, ledger: ClaudeCliSupervisedJobsLedger,
                 domain: JobExecutionDomain, *,
                 output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT):
        if not isinstance(ledger, ClaudeCliSupervisedJobsLedger):
            _fail("invalid", "managed job runner requires the T053 ledger")
        if (isinstance(output_limit_bytes, bool) or
                not isinstance(output_limit_bytes, int) or
                not 0 < output_limit_bytes <= MAX_OUTPUT_LIMIT):
            _fail("invalid", "job output limit is outside the supported bound")
        self.ledger = ledger
        self.store = ledger.store
        self.domain = domain
        self.output_limit_bytes = output_limit_bytes

    def _domain_id(self) -> str:
        domain_id = _token(
            getattr(self.domain, "persistent_job_domain_id", None),
            "persistent job domain ID",
        )
        provider_id = getattr(self.ledger.witness_provider,
                              "persistent_job_domain_id", None)
        if callable(provider_id):
            provider_id = provider_id()
        if provider_id != domain_id:
            _fail("ownership-conflict", "runner and T053 job domain identities differ")
        return domain_id

    def _worktree_for(self, *, cwd: str, parent_uuid: str,
                      claim_generation: int) -> Dict[str, str]:
        path = Path(cwd)
        if not path.is_absolute():
            _fail("invalid", "job working directory must be absolute")
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError):
            _fail("unknown", "job working directory cannot be resolved")
        if not resolved.is_dir():
            _fail("invalid", "job working directory is not a directory")
        with self.ledger._locked() as owner:
            state = self.ledger._load(owner)
            current = state.get("current_claim")
            if (not isinstance(current, Mapping) or current.get("state") != "active" or
                    current.get("parent_uuid") != parent_uuid or
                    current.get("claim_generation") != claim_generation):
                _fail("stale-generation", "job working directory is outside the active source claim")
            rows = self.ledger._registered_worktrees(
                current["lineage_id"], current["lineage_generation"],
                parent_uuid, state["owner_generation"],
            )
        matches = []
        for row in rows:
            root = Path(row["path"]).resolve(strict=True)
            try:
                contained = os.path.commonpath((str(root), str(resolved))) == str(root)
            except ValueError:
                contained = False
            if contained:
                matches.append({"resource_id": row["resource_id"], "path": str(root)})
        if len(matches) != 1:
            _fail("ownership-conflict", "job working directory does not map to one registered worktree")
        return matches[0]

    @staticmethod
    def _normalize_argv(argv: Sequence[str]) -> Sequence[str]:
        if (isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence) or
                not argv or len(argv) > MAX_COMMAND_ITEMS):
            _fail("invalid", "job command must be a bounded argument vector")
        values = []
        total = 0
        for item in argv:
            if not isinstance(item, str) or "\x00" in item:
                _fail("invalid", "job command argument is malformed")
            total += len(item.encode("utf-8"))
            if total > MAX_COMMAND_TEXT:
                _fail("invalid", "job command exceeds its size bound")
            values.append(item)
        executable = Path(values[0])
        if not executable.is_absolute():
            _fail("invalid", "job executable must be an absolute path")
        try:
            executable = executable.resolve(strict=True)
            info = executable.stat()
        except (OSError, RuntimeError):
            _fail("unknown", "job executable cannot be resolved")
        if not stat.S_ISREG(info.st_mode) or not os.access(str(executable), os.X_OK):
            _fail("unsupported", "job executable is not a regular executable file")
        values[0] = str(executable)
        return tuple(values)

    @staticmethod
    def _normalize_environment(environment: Optional[Mapping[str, str]]) -> Dict[str, str]:
        if environment is None:
            return {}
        if not isinstance(environment, Mapping) or len(environment) > MAX_ENV_ITEMS:
            _fail("invalid", "job environment is malformed")
        normalized: Dict[str, str] = {}
        total = 0
        for key, value in environment.items():
            if key not in _SAFE_ENV_KEYS:
                _fail("unsupported", "job environment key is outside the safe allowlist")
            if not isinstance(value, str) or "\x00" in value:
                _fail("invalid", "job environment value is malformed")
            total += len(key.encode("utf-8")) + len(value.encode("utf-8"))
            if total > MAX_ENV_TEXT:
                _fail("invalid", "job environment exceeds its size bound")
            normalized[key] = value
        return normalized

    @staticmethod
    def _opaque_ref(job_id: str) -> str:
        return "job-output-" + hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:40]

    def _path(self, name: str) -> Path:
        return self.store._json_path(name)

    def _record_path(self, job_id: str) -> Path:
        key = hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:40]
        return self._path("managed-job-runner-" + key)

    def _output_path(self, output_ref: str) -> Path:
        if not isinstance(output_ref, str) or _OUTPUT_REF.fullmatch(output_ref) is None:
            _fail("invalid", "job output reference is malformed")
        return self._path(output_ref)

    @staticmethod
    def _seal_record(record: Dict[str, Any]) -> Dict[str, Any]:
        record["integrity_digest"] = ""
        record["integrity_digest"] = _hash({
            key: value for key, value in record.items() if key != "integrity_digest"
        })
        return record

    def _validate_record(self, job_id: str, raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, Mapping) or set(raw) != _RECORD_FIELDS:
            _fail("unknown", "managed job runner record is absent or malformed")
        record = dict(raw)
        if record.get("schema_version") != RUNNER_SCHEMA_VERSION or record.get("job_id") != job_id:
            _fail("invalid", "managed job runner record identity changed")
        _digest(record.get("request_digest"), "runner request digest")
        _digest(record.get("command_digest"), "runner command digest")
        _token(record.get("domain_id"), "runner domain ID")
        _token(record.get("launch_intent_id"), "runner launch intent ID")
        self._output_path(record.get("output_ref"))
        if record.get("state") not in {"launch-intent", "running", "uncertain", "completed", "failed"}:
            _fail("invalid", "runner state is malformed")
        if record.get("uncertainty") is not None:
            _token(record["uncertainty"], "runner uncertainty")
        identity = record.get("process_identity")
        if identity is not None:
            record["process_identity"] = _process_identity(
                identity, expected_pid=None, expected_domain=record["domain_id"],
            )
        exit_code = record.get("exit_code")
        if exit_code is not None and (isinstance(exit_code, bool) or not isinstance(exit_code, int)):
            _fail("invalid", "runner exit code is malformed")
        if record.get("output_digest") is not None:
            _digest(record["output_digest"], "runner output digest")
        size = record.get("output_size")
        if size is not None and (isinstance(size, bool) or not isinstance(size, int) or size < 0):
            _fail("invalid", "runner output size is malformed")
        if not isinstance(record.get("output_truncated"), bool):
            _fail("invalid", "runner output truncation flag is malformed")
        if record.get("result_digest") is not None:
            _digest(record["result_digest"], "runner result digest")
        result_values = (record.get("exit_code"), record.get("output_digest"),
                         record.get("output_size"), record.get("result_digest"))
        if any(value is not None for value in result_values) and any(
                value is None for value in result_values):
            _fail("invalid", "runner result record is incomplete")
        if (record["state"] in {"completed", "failed"} and
                (record.get("process_identity") is None or
                 any(value is None for value in result_values))):
            _fail("invalid", "terminal runner record lacks result custody")
        integrity = _digest(record.get("integrity_digest"), "runner integrity digest")
        if integrity != _hash({key: value for key, value in record.items()
                               if key != "integrity_digest"}):
            _fail("invalid", "managed job runner record integrity changed")
        return record

    def _load_record_unlocked(self, job_id: str) -> Dict[str, Any]:
        return self._validate_record(job_id, self.store._read_path(self._record_path(job_id)))

    def _load_record(self, job_id: str) -> Dict[str, Any]:
        with self.ledger._locked() as owner:
            self.ledger._load(owner)
            return self._load_record_unlocked(job_id)

    def _write_record_locked(self, record: Dict[str, Any], *,
                             expected_integrity: Optional[str] = None,
                             create_only: bool = False) -> Dict[str, Any]:
        path = self._record_path(record["job_id"])
        exists = path.exists() or path.is_symlink()
        if create_only and exists:
            _fail("ownership-conflict", "job runner record already exists")
        if expected_integrity is not None:
            current = self._load_record_unlocked(record["job_id"])
            if current["integrity_digest"] != expected_integrity:
                _fail("stale-generation", "job runner record changed during observation")
        self._seal_record(record)
        self.store._atomic_write(path, _canonical(record) + b"\n")
        return dict(record)

    def _write_record(self, record: Dict[str, Any], *,
                      expected_integrity: Optional[str] = None,
                      create_only: bool = False) -> Dict[str, Any]:
        with self.ledger._locked() as owner:
            self.ledger._load(owner)
            return self._write_record_locked(
                record, expected_integrity=expected_integrity,
                create_only=create_only,
            )

    def _mark_uncertain(self, record: Mapping[str, Any], reason: str) -> None:
        changed = dict(record)
        changed["state"] = "uncertain"
        changed["uncertainty"] = reason
        try:
            self._write_record(
                changed, expected_integrity=record["integrity_digest"],
            )
        except ManagedStateError:
            # Never replace a concurrent completion or newer observation.
            pass

    def _open_output(self, output_ref: str, *, create: bool,
                     writable: bool = False) -> int:
        path = self._output_path(output_ref)
        flags = (os.O_RDWR if writable or create else os.O_RDONLY)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        if create:
            flags |= os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(str(path), flags, 0o600)
            info = os.fstat(fd)
        except OSError:
            _fail("unsafe-state", "private job output custody is unavailable")
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            os.close(fd)
            _fail("unsafe-state", "job output file is not private and regular")
        return fd

    def _assert_dispatchable_locked(self, owner: Mapping[str, Any], *,
                                    job_id: str, request_digest: str,
                                    command_digest: str, parent_uuid: str,
                                    claim_generation: int,
                                    launch_intent_id: str) -> None:
        state = self.ledger._load(owner)
        self.ledger._owner_current(owner, state)
        job = state["jobs"].get(job_id)
        current = state.get("current_claim")
        if (not isinstance(job, Mapping) or
                job.get("request_digest") != request_digest or
                job.get("command_digest") != command_digest or
                job.get("launch_state") != "intent-recorded" or
                job.get("state") != "launch-intent" or
                job.get("launch_intent_id") != launch_intent_id):
            _fail("ownership-conflict", "durable job launch intent changed before dispatch")
        if (not isinstance(current, Mapping) or current.get("state") != "active" or
                current.get("parent_uuid") != parent_uuid or
                current.get("claim_generation") != claim_generation or
                claim_generation in state["retired_source_generations"]):
            _fail("ownership-conflict", "source generation was fenced before job dispatch")
        self.ledger._assert_registered_worktree_ids(
            lineage_id=current["lineage_id"],
            lineage_generation=current["lineage_generation"],
            parent_uuid=parent_uuid,
            owner_generation=state["owner_generation"],
            expected_worktree_ids=current["worktree_ids"],
        )

    def start_job(self, *, job_id: str, request_id: str, request_digest: str,
                  parent_uuid: str, claim_generation: int, argv: Sequence[str],
                  cwd: str, environment: Optional[Mapping[str, str]] = None,
                  resource_ids: Optional[Sequence[str]] = None,
                  effects_scope: str = "unknown") -> Dict[str, Any]:
        """Admit and consume one intent; serialize the OS spawn against fencing."""
        job_id = _token(job_id, "job ID")
        request_id = _token(request_id, "request ID")
        request_digest = _digest(request_digest, "request digest")
        parent_uuid = _token(parent_uuid, "parent UUID")
        if (isinstance(claim_generation, bool) or not isinstance(claim_generation, int) or
                claim_generation <= 0):
            _fail("invalid", "claim generation must be positive")
        self.domain.assert_ready()
        domain_id = self._domain_id()
        normalized_argv = self._normalize_argv(argv)
        normalized_env = self._normalize_environment(environment)
        worktree = self._worktree_for(
            cwd=cwd, parent_uuid=parent_uuid, claim_generation=claim_generation,
        )
        if effects_scope not in {"unknown", "local-worktree"}:
            _fail("invalid", "job effects scope is unsupported")
        resolved_cwd = str(Path(cwd).resolve(strict=True))
        requested_resources = None if resource_ids is None else list(resource_ids)
        if requested_resources is not None:
            if (any(not isinstance(item, str) for item in requested_resources) or
                    len(requested_resources) != len(set(requested_resources)) or
                    worktree["resource_id"] not in requested_resources):
                _fail("ownership-conflict", "job reservation must include its working directory")
        command_digest = _hash({
            "argv": list(normalized_argv), "cwd_resource_id": worktree["resource_id"],
            "cwd_relative": os.path.relpath(resolved_cwd, worktree["path"]),
            "environment": normalized_env, "effects_scope": effects_scope,
        })
        output_ref = self._opaque_ref(job_id)
        record_path = self._record_path(job_id)
        output_path = self._output_path(output_ref)
        if any(path.exists() or path.is_symlink() for path in (record_path, output_path)):
            _fail("ownership-conflict", "job ID already has runner custody files")
        binder = getattr(self.domain, "bind_worktree_root", None)
        if callable(binder):
            binder(job_id=job_id, worktree_root=worktree["path"],
                   effects_scope=effects_scope)
        admitted = self.ledger.admit_job(
            job_id=job_id, request_id=request_id, request_digest=request_digest,
            parent_uuid=parent_uuid, claim_generation=claim_generation,
            command_digest=command_digest, resource_ids=requested_resources,
        )
        if admitted.get("state") != "admitted" or admitted.get("launch_state") != "not-dispatched":
            _fail("uncertain-effect", "job ID already has a consumed launch intent; do not replay")
        launch = self.ledger.begin_job_launch(job_id=job_id, request_digest=request_digest)
        if (launch.get("state") != "launch-intent" or
                launch.get("launch_state") != "intent-recorded" or
                not isinstance(launch.get("launch_intent_id"), str)):
            _fail("uncertain-effect", "durable job launch intent is not dispatchable")
        record: Dict[str, Any] = {
            "schema_version": RUNNER_SCHEMA_VERSION,
            "job_id": job_id,
            "request_digest": request_digest,
            "command_digest": command_digest,
            "domain_id": domain_id,
            "launch_intent_id": launch["launch_intent_id"],
            "process_identity": None,
            "output_ref": output_ref,
            "state": "launch-intent",
            "uncertainty": None,
            "exit_code": None,
            "output_digest": None,
            "output_size": None,
            "output_truncated": False,
            "result_digest": None,
            "integrity_digest": "",
        }
        output_fd = -1
        record_created = False
        identity = None
        try:
            output_fd = self._open_output(output_ref, create=True)
            record = self._write_record(record, create_only=True)
            record_created = True
            # prepare_swap uses this same store lock. It either fences first,
            # in which case the check below refuses, or follows the spawn and
            # identity publication atomically as one admitted transition.
            with self.ledger._locked() as owner:
                self._assert_dispatchable_locked(
                    owner, job_id=job_id, request_digest=request_digest,
                    command_digest=command_digest, parent_uuid=parent_uuid,
                    claim_generation=claim_generation,
                    launch_intent_id=record["launch_intent_id"],
                )
                pid = self.domain.launch_new(
                    job_id=job_id, launch_intent_id=record["launch_intent_id"],
                    argv=normalized_argv, cwd=resolved_cwd,
                    environment=normalized_env, output_fd=output_fd,
                    output_limit_bytes=self.output_limit_bytes + 1,
                    deadline=time.monotonic() + SPAWN_TIMEOUT_SECONDS,
                )
                if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
                    _fail("uncertain-effect", "job domain did not return a launched process identity")
                identity = _process_identity(
                    self.domain.read_process_identity(pid), expected_pid=pid,
                    expected_domain=domain_id,
                )
                changed = dict(record)
                changed["process_identity"] = identity
                changed["state"] = "running"
                record = self._write_record_locked(
                    changed, expected_integrity=record["integrity_digest"],
                )
            return self._public(record)
        except Exception as exc:
            # The intent is consumed even if a backend lost its acknowledgement.
            if record_created:
                changed = dict(record)
                changed["state"] = "uncertain"
                changed["uncertainty"] = "launch-outcome-unknown"
                if identity is not None:
                    changed["process_identity"] = identity
                try:
                    record = self._write_record(
                        changed, expected_integrity=record["integrity_digest"],
                    )
                except ManagedStateError:
                    pass
            if isinstance(exc, ManagedStateError):
                raise
            _fail("uncertain-effect", "job launch outcome is uncertain; do not retry this job ID")
        finally:
            if output_fd >= 0:
                os.close(output_fd)

    @staticmethod
    def _public(record: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "job_id": record["job_id"], "state": record["state"],
            "domain_id": record["domain_id"],
            "process_identity": record["process_identity"],
            "output_ref": record["output_ref"],
            "result_digest": record["result_digest"],
            "uncertainty": record["uncertainty"],
        }

    def status(self, job_id: str) -> Dict[str, Any]:
        job_id = _token(job_id, "job ID")
        record = self._load_record(job_id)
        if record["state"] in {"completed", "failed"}:
            self.read_result(job_id)
            return self._public(record)
        identity = record.get("process_identity")
        if identity is None:
            _fail("uncertain-effect", "job process identity was not durably observed")
        try:
            running = self.domain.process_is_running(identity)
        except Exception:
            _fail("uncertain-effect", "job process status is unavailable")
        if running is not True:
            changed = dict(record)
            changed["state"] = "uncertain"
            changed["uncertainty"] = "process-ended-without-result"
            try:
                latest = self._write_record(
                    changed, expected_integrity=record["integrity_digest"],
                )
            except ManagedStateError:
                latest = self._load_record(job_id)
            if latest["state"] in {"completed", "failed"}:
                return self.read_result(job_id)
            _fail("uncertain-effect", "job ended without an authoritative result")
        return self._public(record)

    def read_output(self, job_id: str) -> bytes:
        record = self._load_record(_token(job_id, "job ID"))
        if record["state"] not in {"completed", "failed"}:
            _fail("uncertain-effect", "job output is not finalized")
        identity = record.get("process_identity")
        if identity is None:
            _fail("uncertain-effect", "finalized output has no process identity")
        try:
            subtree_empty = self.domain.job_subtree_empty(
                job_id=job_id, process_identity=identity,
            )
        except Exception:
            subtree_empty = False
        if subtree_empty is not True:
            self._mark_uncertain(record, "job-subtree-not-proven-empty")
            _fail("uncertain-effect", "job output cannot be read before subtree drain is proven")
        fd = self._open_output(record["output_ref"], create=False)
        try:
            info = os.fstat(fd)
            if info.st_size > self.output_limit_bytes + 1:
                _fail("uncertain-effect", "job output exceeded its enforced size bound")
            data = os.read(fd, self.output_limit_bytes + 1)
        except OSError:
            _fail("unsafe-state", "private job output could not be read")
        finally:
            os.close(fd)
        if len(data) > self.output_limit_bytes:
            _fail("uncertain-effect", "job output reached the capture boundary")
        if hashlib.sha256(data).hexdigest() != record["output_digest"]:
            _fail("ownership-conflict", "completed job output changed after capture")
        return data

    def _capture_output_locked(self, record: Dict[str, Any]) -> tuple[bytes, bool]:
        # The output is only finalized after the domain proves the subtree is
        # empty. Open writable so fsync is valid on platforms that reject it on
        # a read-only descriptor.
        fd = self._open_output(record["output_ref"], create=False, writable=True)
        try:
            os.fsync(fd)
            info = os.fstat(fd)
            if info.st_size > self.output_limit_bytes + 1:
                _fail("uncertain-effect", "job output exceeded its enforced size bound")
            os.lseek(fd, 0, os.SEEK_SET)
            data = os.read(fd, self.output_limit_bytes + 1)
            overflow = len(data) > self.output_limit_bytes
            if overflow:
                data = data[:self.output_limit_bytes]
                os.ftruncate(fd, self.output_limit_bytes)
                os.fsync(fd)
        except OSError:
            _fail("unsafe-state", "private job output could not be finalized")
        finally:
            os.close(fd)
        return data, overflow

    def wait_job(self, job_id: str, *, timeout: float = 0.0) -> Dict[str, Any]:
        """Publish a result only after the root and all descendants are gone."""
        job_id = _token(job_id, "job ID")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            _fail("invalid", "job wait timeout is outside the supported bound")
        try:
            wait_seconds = float(timeout)
        except (OverflowError, ValueError):
            _fail("invalid", "job wait timeout is outside the supported bound")
        if (not math.isfinite(wait_seconds) or wait_seconds < 0 or
                wait_seconds > MAX_WAIT_SECONDS):
            _fail("invalid", "job wait timeout is outside the supported bound")
        record = self._load_record(job_id)
        if record["state"] in {"completed", "failed"}:
            return self.read_result(job_id)
        identity = record.get("process_identity")
        if identity is None:
            _fail("uncertain-effect", "job launch has no observed process identity")
        try:
            result = self.domain.wait_result(
                job_id=job_id, process_identity=identity, timeout=wait_seconds,
            )
            if result is None:
                return self._public(record)
            if not isinstance(result, Mapping) or set(result) != {"exit_code", "output_truncated"}:
                _fail("uncertain-effect", "job result witness is malformed")
            exit_code = result.get("exit_code")
            if (isinstance(exit_code, bool) or not isinstance(exit_code, int) or
                    not -255 <= exit_code <= 255):
                _fail("uncertain-effect", "job exit result is malformed")
            if not isinstance(result.get("output_truncated"), bool):
                _fail("uncertain-effect", "job output truncation witness is malformed")
            if self.domain.job_subtree_empty(
                    job_id=job_id, process_identity=identity) is not True:
                changed = dict(record)
                changed["state"] = "uncertain"
                changed["uncertainty"] = "job-subtree-live"
                self._write_record(changed, expected_integrity=record["integrity_digest"])
                _fail("uncertain-effect", "job leader ended while descendants remain; reservation stays held")
            completed_by_concurrent_wait = False
            with self.ledger._locked() as owner:
                self.ledger._load(owner)
                latest = self._load_record_unlocked(job_id)
                if latest["integrity_digest"] != record["integrity_digest"]:
                    if latest["state"] in {"completed", "failed"}:
                        completed_by_concurrent_wait = True
                        record = latest
                    else:
                        _fail("stale-generation", "job runner record changed during wait")
                if not completed_by_concurrent_wait:
                    if self.domain.job_subtree_empty(
                            job_id=job_id, process_identity=identity) is not True:
                        latest["state"] = "uncertain"
                        latest["uncertainty"] = "job-subtree-not-proven-empty"
                        self._write_record_locked(latest)
                        _fail("uncertain-effect", "job descendants remain; result was not published")
                    output, overflow = self._capture_output_locked(latest)
                    if result["output_truncated"] is not overflow:
                        latest["state"] = "uncertain"
                        latest["uncertainty"] = "output-truncation-witness-mismatch"
                        self._write_record_locked(latest)
                        _fail("uncertain-effect", "job output truncation witness disagrees with captured bytes")
                    if overflow and len(output) != self.output_limit_bytes:
                        _fail("uncertain-effect", "output truncation attestation disagrees with captured bytes")
                    fields = {
                        "job_id": job_id,
                        "launch_intent_id": latest["launch_intent_id"],
                        "domain_id": latest["domain_id"],
                        "process_identity": identity,
                        "exit_code": exit_code,
                        "output_ref": latest["output_ref"],
                        "output_digest": hashlib.sha256(output).hexdigest(),
                        "output_size": len(output),
                        "output_truncated": overflow,
                    }
                    latest.update(fields)
                    latest["result_digest"] = _hash(fields)
                    latest["state"] = "completed" if exit_code == 0 else "failed"
                    latest["uncertainty"] = None
                    record = self._write_record_locked(
                        latest, expected_integrity=record["integrity_digest"],
                    )
            return self.read_result(job_id)
        except ManagedStateError as exc:
            if exc.code in {"uncertain-effect", "unsafe-state"}:
                self._mark_uncertain(record, "result-observation-unknown")
            raise
        except Exception:
            changed = dict(record)
            changed["state"] = "uncertain"
            changed["uncertainty"] = "result-observation-unknown"
            try:
                self._write_record(changed, expected_integrity=record["integrity_digest"])
            except ManagedStateError:
                pass
            _fail("uncertain-effect", "job result or descendant state is uncertain")

    def read_result(self, job_id: str) -> Dict[str, Any]:
        """Read an immutable result after a fresh subtree-empty check."""
        job_id = _token(job_id, "job ID")
        record = self._load_record(job_id)
        if record["state"] not in {"completed", "failed"}:
            _fail("uncertain-effect", "job has no safely publishable terminal result")
        identity = record.get("process_identity")
        if identity is None:
            _fail("uncertain-effect", "completed result has no process identity")
        try:
            subtree_empty = self.domain.job_subtree_empty(
                job_id=job_id, process_identity=identity,
            )
        except Exception:
            subtree_empty = False
        if subtree_empty is not True:
            self._mark_uncertain(record, "job-subtree-not-proven-empty")
            _fail("uncertain-effect", "job subtree drain is no longer proven")
        output = self.read_output(job_id)
        fields = {
            "job_id": record["job_id"],
            "launch_intent_id": record["launch_intent_id"],
            "domain_id": record["domain_id"],
            "process_identity": identity,
            "exit_code": record["exit_code"],
            "output_ref": record["output_ref"],
            "output_digest": hashlib.sha256(output).hexdigest(),
            "output_size": len(output),
            "output_truncated": record["output_truncated"],
        }
        if (fields["output_digest"] != record["output_digest"] or
                fields["output_size"] != record["output_size"] or
                _hash(fields) != record["result_digest"]):
            _fail("ownership-conflict", "job result custody changed")
        with self.ledger._locked() as owner:
            self.ledger._load(owner)
            latest = self._load_record_unlocked(job_id)
            if latest["integrity_digest"] != record["integrity_digest"]:
                _fail("stale-generation", "job result changed during read")
            try:
                subtree_empty = self.domain.job_subtree_empty(
                    job_id=job_id, process_identity=identity,
                )
            except Exception:
                subtree_empty = False
            if subtree_empty is not True:
                latest["state"] = "uncertain"
                latest["uncertainty"] = "job-subtree-not-proven-empty"
                self._write_record_locked(
                    latest, expected_integrity=record["integrity_digest"],
                )
                _fail("uncertain-effect", "job subtree drain is no longer proven")
        return {
            "job_id": job_id, "state": record["state"],
            "exit_code": record["exit_code"], "process_identity": identity,
            "output_ref": record["output_ref"],
            "output_digest": record["output_digest"],
            "output_size": record["output_size"],
            "output_truncated": record["output_truncated"],
            "result_digest": record["result_digest"],
        }

    def job_status(self, binding: Mapping[str, Any], job_id: str) -> Dict[str, Any]:
        """Bridge the runner journal into T053's trusted job observation API."""
        job_id = _token(job_id, "job ID")
        state = self.ledger.status()
        job = state["jobs"].get(job_id)
        if not isinstance(job, Mapping):
            _fail("unknown", "supervised job is not admitted")
        if (not isinstance(binding, Mapping) or binding.get("capability") != CAPABILITY or
                binding.get("owner_generation") != job["owner_generation"] or
                binding.get("parent_uuid") != job["parent_uuid"] or
                binding.get("lineage_id") != job["lineage_id"] or
                binding.get("lineage_generation") != job["lineage_generation"] or
                binding.get("source_claim_generation", 0) < job["source_claim_generation"] or
                not set(job["resource_ids"]).issubset(set(binding.get("worktree_ids", [])))):
            _fail("ownership-conflict", "job observation binding does not match its admission")
        record = None
        try:
            record = self._load_record(job_id)
        except ManagedStateError as exc:
            if exc.code != "unknown":
                raise
        if (record is not None and record.get("process_identity") is not None and
                record["state"] not in {"completed", "failed"}):
            # Seal a worker result already available before constructing the
            # witness arguments. A sealed result and a stale running record
            # must not be mistaken for a live job at reconciliation.
            self.wait_job(job_id, timeout=0)
            record = self._load_record(job_id)
        identity = None if record is None else record.get("process_identity")
        output_ref = None if record is None else record["output_ref"]
        result_digest = None if record is None else record.get("result_digest")
        observer = getattr(self.domain, "job_status_witness", None)
        if not callable(observer):
            _fail("unsupported", "trusted job-status witness is unavailable")
        try:
            witness = observer(
                binding=dict(binding), job_id=job_id,
                process_identity=identity, output_ref=output_ref,
                result_digest=result_digest,
                minimum_watermark=max(state["observation_watermark"], job["observation_watermark"]),
            )
        except ManagedStateError:
            raise
        except Exception:
            _fail("uncertain-effect", "trusted job-status observation failed")
        if not isinstance(witness, Mapping) or set(witness) != _OBSERVATION_FIELDS:
            _fail("uncertain-effect", "trusted job-status witness is malformed")
        if (witness.get("job_id") != job_id or
                witness.get("command_digest") != job["command_digest"] or
                witness.get("domain_id") != job["domain_id"]):
            _fail("ownership-conflict", "job-status witness identity changed")
        _token(witness.get("witness_id"), "job witness ID")
        _digest(witness.get("witness_digest"), "job witness digest")
        watermark = witness.get("observation_watermark")
        if (isinstance(watermark, bool) or not isinstance(watermark, int) or
                watermark <= max(state["observation_watermark"], job["observation_watermark"])):
            _fail("stale-generation", "job observation watermark did not advance")
        if witness.get("state") not in {
                "admitted", "launch-intent", "running", "completed", "failed", "uncertain"}:
            _fail("uncertain-effect", "job-status witness state is unknown")
        if witness.get("effect_state") not in {"none", "known", "unknown"}:
            _fail("uncertain-effect", "job-status witness effect state is unknown")
        observed_identity = witness.get("process_identity")
        if observed_identity is not None:
            observed_identity = _process_identity(
                observed_identity, expected_pid=None, expected_domain=job["domain_id"],
            )
        if identity is not None and observed_identity != identity:
            _fail("ownership-conflict", "job-status witness process identity changed")
        if witness.get("output_ref") != output_ref or witness.get("result_digest") != result_digest:
            _fail("ownership-conflict", "job-status witness result custody changed")
        if (record is not None and record["state"] in {"completed", "failed"} and
                witness.get("state") != record["state"]):
            _fail("ownership-conflict", "job-status witness terminal state changed")
        if witness.get("state") in {"completed", "failed"}:
            if (witness.get("effect_state") != "known" or record is None or
                    record["state"] != witness.get("state")):
                _fail("uncertain-effect", "terminal job effects are not authoritatively reconciled")
            self.read_result(job_id)
        return dict(witness)


class ManagedJobWitnessAdapter:
    """Compose runner job observations with existing source/history witnesses.

    This adapter is passed as the ``other_witness_provider`` to the private
    Docker source provider. It does not make that provider production-ready;
    its source/history witnesses still need the trusted Engine-host broker.
    """

    def __init__(self, runner: ManagedJobRunner, delegate: Any):
        self.runner = runner
        self.delegate = delegate

    @property
    def persistent_job_domain_id(self) -> str:
        # Do not call runner._domain_id() here: the runner compares its domain
        # identity with the ledger witness provider, which may be this adapter.
        value = getattr(self.runner.domain, "persistent_job_domain_id", None)
        if callable(value):
            value = value()
        return _token(value, "persistent job domain ID")

    def job_status(self, binding: Mapping[str, Any], job_id: str) -> Mapping[str, Any]:
        return self.runner.job_status(binding, job_id)

    def source_exclusion(self, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._call("source_exclusion", binding)

    def history_manifest(self, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._call("history_manifest", binding)

    def target_status(self, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._call("target_status", binding)

    def _call(self, name: str, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        method = getattr(self.delegate, name, None)
        if not callable(method):
            _fail("unsupported", "trusted %s witness is unavailable" % name)
        return method(binding)
