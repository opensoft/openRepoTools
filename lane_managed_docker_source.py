# SPDX-License-Identifier: Apache-2.0
"""Internal, offline-testable Docker source containment candidate.

This module is not imported by any public route. All Engine mutations and
their durable intents share the managed lane lock with the T053 restart fence.
A mutation left in flight by a crash is never replayed automatically.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Protocol, Sequence, Tuple

from lane_managed_state import ManagedStateError
from lane_managed_supervised_jobs import CAPABILITY, ClaudeCliSupervisedJobsLedger
from lane_managed_claude_launch import REQUIRED_ENV, normalize_launch


PROVIDER = "docker-source-container-v1"
_JOURNAL = "docker-source-container.json"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_CONTAINER_ID = _HEX64
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[^\x00-\x1f\x7f]{1,256}\Z")
_TIMEOUT = 8.0
_MOUNT_TARGETS = {
    "worktree": "/workspace/current",
    "repo_metadata": "/run/l1/repository-metadata",
    "history": "/run/claude/history",
    "profile_config": "/run/claude/profile",
    "job_broker": "/run/l1/job-broker",
}
_READ_ONLY = {
    "worktree": False, "repo_metadata": False, "history": False,
    "profile_config": True, "job_broker": False,
}
_CONFIG_FIELDS = frozenset({
    "image_digest", "cli_executable_digest", "entrypoint", "user",
    "read_only_rootfs", "no_new_privileges", "seccomp_digest", "lsm_profile",
    "memory_limit_bytes", "pids_limit", "restart_policy", "auto_remove",
    "privileged", "pid_mode", "ipc_mode", "cgroup_mode",
    "network_id", "network_policy_digest", "published_ports", "cap_add", "cap_drop",
    "devices", "device_requests", "mounts", "healthcheck", "init",
    "environment", "extra_hosts", "claude_launch",
})
_MUTATION_FIELDS = frozenset({
    "kind", "intent_id", "request_digest", "state", "result_digest",
})
_JOURNAL_FIELDS = frozenset({
    "schema_version", "capability", "provider", "lane", "lane_key", "host",
    "common_dir", "owner_generation", "daemon_id", "supervisor_incarnation",
    "admissions", "integrity_digest",
})
_ADMISSION_FIELDS = frozenset({
    "admission_id", "source_claim_generation", "parent_uuid",
    "source_runtime_incarnation", "source_invocation_id", "source_domain_id",
    "source_manifest_digest", "engine_identity", "image_digest",
    "cli_executable_digest", "configuration_digest", "parent_identity",
    "container_id", "container_creation_identity", "container_config_digest",
    "container_host_identity", "operation_id", "phase", "mutations",
    "last_witness",
})


def _fail(code: str, message: str) -> None:
    raise ManagedStateError(code, message)


def _json_bytes(value: Any) -> bytes:
    try:
        result = json.dumps(value, ensure_ascii=True, sort_keys=True,
                            separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        _fail("invalid", "Docker provider record is not JSON data")
    if len(result) > 256 * 1024:
        _fail("invalid", "Docker provider record exceeds its size bound")
    return result


def _hash(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _copy(value: Any) -> Any:
    return json.loads(_json_bytes(value).decode("utf-8"))


def _exact(value: Any, fields: frozenset, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail("invalid", "%s has missing or unknown fields" % label)
    return dict(value)


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or _TOKEN.fullmatch(value) is None:
        _fail("invalid", "%s is malformed" % label)
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        _fail("invalid", "%s is malformed" % label)
    return value


def _positive(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail("invalid", "%s must be a positive integer" % label)
    return value


def normalize_config(value: Mapping[str, Any], *, state_root: Path) -> Dict[str, Any]:
    """Validate the bounded baseline before any Engine mutation."""
    config = _exact(value, _CONFIG_FIELDS, "Docker source configuration")
    for key in ("image_digest", "cli_executable_digest"):
        if not isinstance(config[key], str) or _DIGEST.fullmatch(config[key]) is None:
            _fail("unsupported", "%s must be an immutable sha256 digest" % key)
    if config["entrypoint"] != ["/usr/local/libexec/claude-wait-for-release"]:
        _fail("unsupported", "container must start the reviewed waiting entrypoint")
    if config["user"] not in {"1000:1000", "1001:1001", "65532:65532"}:
        _fail("unsupported", "container user must be a reviewed non-root identity")
    if (config["read_only_rootfs"] is not True or
            config["no_new_privileges"] is not True or
            config["restart_policy"] != "no" or config["auto_remove"] is not False or
            config["privileged"] is not False or config["pid_mode"] != "private" or
            config["ipc_mode"] != "private" or config["cgroup_mode"] != "private" or
            config["published_ports"] != [] or config["cap_add"] != [] or
            config["cap_drop"] != ["ALL"] or config["devices"] != [] or
            config["device_requests"] != [] or config["healthcheck"] is not None or
            config["init"] is not False or config["environment"] != list(REQUIRED_ENV) or
            config["extra_hosts"] != []):
        _fail("unsupported", "container requests an unsafe or unreviewed Docker feature")
    launch = normalize_launch(config["claude_launch"])
    if launch["environment"] != config["environment"]:
        _fail("unsupported", "container and Claude foreground policies disagree")
    _digest(config["seccomp_digest"], "seccomp profile digest")
    _token(config["lsm_profile"], "LSM profile")
    if config["lsm_profile"].lower() in {"unconfined", "none", "disabled"}:
        _fail("unsupported", "unconfined LSM profiles are not admitted")
    _token(config["network_id"], "source network identity")
    _digest(config["network_policy_digest"], "network policy digest")
    _positive(config["memory_limit_bytes"], "memory limit")
    _positive(config["pids_limit"], "PID limit")

    state_root = state_root.resolve(strict=True)
    mounts = config["mounts"]
    if not isinstance(mounts, list) or len(mounts) != len(_MOUNT_TARGETS):
        _fail("unsupported", "container mount roster is incomplete")
    seen = set()
    sources = []
    normalized = []
    for raw in mounts:
        mount = _exact(raw, frozenset({
            "role", "source_path", "source_identity", "target", "read_only",
            "propagation",
        }), "Docker source mount")
        role = _token(mount["role"], "mount role")
        if role not in _MOUNT_TARGETS or role in seen:
            _fail("unsupported", "mount role is unknown or duplicated")
        path_text = mount["source_path"]
        if (not isinstance(path_text, str) or not os.path.isabs(path_text) or
                os.path.normpath(path_text) != path_text):
            _fail("unsupported", "mount source path is not canonical")
        path = Path(path_text)
        try:
            if path.resolve(strict=True) != path:
                _fail("unsupported", "mount source path contains a symlink")
            info = path.stat()
        except OSError:
            _fail("unsupported", "mount source path is unavailable")
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISSOCK(info.st_mode)):
            _fail("unsupported", "mount source must be a directory or broker socket")
        source_identity = _digest(mount["source_identity"], "mount source identity")
        actual_identity = _hash({
            "path": str(path), "device": info.st_dev, "inode": info.st_ino,
            "mode": stat.S_IFMT(info.st_mode), "uid": info.st_uid,
        })
        if source_identity != actual_identity:
            _fail("ownership-conflict", "mount source identity changed")
        if mount["target"] != _MOUNT_TARGETS[role]:
            _fail("unsupported", "mount target is outside the fixed container layout")
        if mount["read_only"] is not _READ_ONLY[role] or mount["propagation"] != "rprivate":
            _fail("unsupported", "mount access or propagation is not admitted")
        for old in sources:
            try:
                common = os.path.commonpath((str(path), str(old)))
            except ValueError:
                common = ""
            if common in {str(path), str(old)}:
                _fail("unsupported", "mount sources overlap or alias")
        try:
            common = os.path.commonpath((str(path), str(state_root)))
        except ValueError:
            common = ""
        if common in {str(path), str(state_root)}:
            _fail("unsupported", "container mount exposes supervisor state")
        seen.add(role)
        sources.append(path)
        normalized.append({
            "role": role, "source_path": str(path),
            "source_identity": source_identity, "target": mount["target"],
            "read_only": mount["read_only"], "propagation": mount["propagation"],
        })
    if seen != set(_MOUNT_TARGETS):
        _fail("unsupported", "container mount roster is incomplete")
    result = dict(config)
    result["mounts"] = sorted(normalized, key=lambda item: item["role"])
    result["claude_launch"] = launch
    return result


class DockerEngineAdapter(Protocol):
    """Only these bounded, identity-bound calls may reach the Docker Engine."""
    def identity(self, *, deadline: float) -> Mapping[str, Any]: ...
    def create(self, admission_id: str, config: Mapping[str, Any], *,
               deadline: float) -> str: ...
    def inspect(self, container_id: str, *, deadline: float) -> Mapping[str, Any]: ...
    def start(self, container_id: str, *, deadline: float) -> None: ...
    def kill(self, container_id: str, signal_name: str, *, deadline: float) -> None: ...


class CgroupWitness(Protocol):
    def assert_engine_host(self, engine: Mapping[str, Any]) -> bool: ...
    def parent_snapshot(self) -> Mapping[str, Any]: ...
    def bind_container(self, host_pid: int) -> Mapping[str, Any]: ...
    def supervisor_outside(self, parent: Mapping[str, Any]) -> bool: ...
    def job_domain_witness(self, parent: Mapping[str, Any], job_domain_id: str,
                           jobs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]: ...


class RetainedCgroupV2Parent:
    """Retain and re-read one broker-provisioned cgroup directory handle."""
    def __init__(self, directory_fd: int, *, allocation_id: str,
                 host_boot_identity: str, mount_id: int,
                 require_empty: bool = True):
        if not os.sys.platform.startswith("linux"):
            _fail("unsupported", "cgroup v2 witness requires Linux")
        self.fd = os.dup(directory_fd)
        try:
            self.allocation_id = str(uuid.UUID(allocation_id))
            self.host_boot_identity = _token(host_boot_identity, "host boot identity")
            self.mount_id = _positive(mount_id, "cgroup mount identity")
            self.namespaces = self._host_namespaces()
            info = os.fstat(self.fd)
            if not stat.S_ISDIR(info.st_mode):
                _fail("unsupported", "retained cgroup handle is not a directory")
            self.device, self.inode = info.st_dev, info.st_ino
            self.cgroup_path = self._bound_path()
            if self.cgroup_path == "/":
                _fail("unsupported", "retained source parent cannot be the cgroup root")
            initial = self.snapshot()
            if (initial["cgroup_type"] != "domain" or
                    (require_empty and initial["populated"] != 0)):
                _fail("unsupported", "retained cgroup is not an admitted domain")
        except BaseException:
            os.close(self.fd)
            self.fd = -1
            raise

    @staticmethod
    def _host_namespaces() -> Dict[str, str]:
        result = {}
        try:
            for name in ("pid", "cgroup", "mnt"):
                result[name] = os.readlink("/proc/self/ns/" + name)
        except OSError:
            _fail("unsupported", "witness broker namespace identities are unavailable")
        # These are stable local identities, not an Engine-host attestation.
        # A sidecar with host PID/cgroup namespaces can be unable to read
        # /proc/1/ns under procfs ptrace policy. Provider admission requires
        # the separate trusted assert_engine_host check before mutation.
        return result

    def _fd_mount_id(self) -> int:
        try:
            contents = Path("/proc/self/fdinfo/%d" % self.fd).read_text(encoding="ascii")
        except (OSError, UnicodeError):
            _fail("unsupported", "retained cgroup mount identity is unavailable")
        for line in contents.splitlines():
            if line.startswith("mnt_id:"):
                try:
                    return int(line.split(":", 1)[1].strip())
                except ValueError:
                    break
        _fail("unsupported", "retained cgroup mount identity is malformed")

    @staticmethod
    def _mount_field(value: str) -> str:
        if re.search(r"\\(?![0-7]{3})", value):
            _fail("unknown", "cgroup mount path contains an invalid escape")
        decoded = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)
        if any(ord(character) < 32 or ord(character) == 127 for character in decoded):
            _fail("unknown", "cgroup mount path contains a control character")
        return decoded

    @classmethod
    def _path_from_mountinfo(cls, fd_path: str, mount_id: int,
                             mountinfo: str) -> str:
        """Map a retained FD to one host-visible unified cgroup path."""
        if (not isinstance(fd_path, str) or not fd_path.startswith("/") or
                os.path.normpath(fd_path) != fd_path or fd_path.endswith(" (deleted)")):
            _fail("unknown", "retained cgroup FD path is ambiguous")
        matches = []
        for line in mountinfo.splitlines():
            parts = line.split(" ")
            if not parts or parts[0] != str(mount_id):
                continue
            if len(parts) < 10 or parts.count("-") != 1:
                _fail("unknown", "retained cgroup mount record is malformed")
            separator = parts.index("-")
            if separator + 1 >= len(parts) or parts[separator + 1] != "cgroup2":
                _fail("unsupported", "retained FD is not on cgroup v2")
            root = cls._mount_field(parts[3])
            mountpoint = cls._mount_field(parts[4])
            if (root != "/" or not mountpoint.startswith("/") or
                    os.path.normpath(mountpoint) != mountpoint):
                _fail("unsupported", "cgroup mount has a shifted or malformed root")
            try:
                relative = os.path.relpath(fd_path, mountpoint)
            except ValueError:
                _fail("unknown", "retained FD is outside its cgroup mount")
            if relative == ".." or relative.startswith(".." + os.sep):
                _fail("unknown", "retained FD is outside its cgroup mount")
            matches.append("/" if relative == "." else "/" + relative)
        if len(matches) != 1:
            _fail("unknown", "retained cgroup mount identity is absent or ambiguous")
        return matches[0]

    def _bound_path(self) -> str:
        if self._fd_mount_id() != self.mount_id:
            _fail("ownership-conflict", "retained cgroup mount identity changed")
        try:
            fd_path = os.readlink("/proc/self/fd/%d" % self.fd)
            mountinfo = Path("/proc/self/mountinfo").read_text(encoding="ascii")
            resolved = Path(fd_path).resolve(strict=True)
            info = resolved.stat()
        except (OSError, UnicodeError, RuntimeError):
            _fail("unknown", "retained cgroup FD path custody is unavailable")
        if (str(resolved) != fd_path or info.st_dev != self.device or
                info.st_ino != self.inode):
            _fail("ownership-conflict", "retained cgroup FD path changed identity")
        return self._path_from_mountinfo(fd_path, self.mount_id, mountinfo)

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def snapshot(self) -> Dict[str, Any]:
        info = os.fstat(self.fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_dev != self.device or info.st_ino != self.inode:
            _fail("ownership-conflict", "retained cgroup parent identity changed")
        if (self._fd_mount_id() != self.mount_id or
                self._host_namespaces() != self.namespaces):
            _fail("ownership-conflict", "retained cgroup mount or namespace identity changed")
        if self._bound_path() != self.cgroup_path:
            _fail("ownership-conflict", "retained cgroup host path changed")
        try:
            boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(
                encoding="ascii").strip()
        except (OSError, UnicodeError):
            _fail("unknown", "host boot identity is unavailable")
        if boot_id != self.host_boot_identity:
            _fail("ownership-conflict", "host boot identity changed")
        kind = self._read_file("cgroup.type", 128).strip()
        events = {}
        for line in self._read_file("cgroup.events", 4096).splitlines():
            fields = line.split()
            if len(fields) != 2 or fields[0] in events or fields[1] not in {"0", "1"}:
                _fail("unknown", "retained cgroup events are malformed")
            events[fields[0]] = int(fields[1])
        if kind != "domain" or set(events) != {"populated", "frozen"}:
            _fail("unknown", "retained cgroup domain evidence is incomplete")
        identity = {
            "allocation_id": self.allocation_id,
            "host_boot_identity": self.host_boot_identity,
            "mount_id": self.mount_id,
            "device": self.device,
            "inode": self.inode,
            "cgroup_type": kind,
        }
        identity["identity_digest"] = _hash(identity)
        return {**identity, "populated": events["populated"], "frozen": events["frozen"]}

    def _read_file(self, name: str, maximum: int) -> str:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(name, flags, dir_fd=self.fd)
            try:
                data = os.read(fd, maximum + 1)
            finally:
                os.close(fd)
        except OSError:
            _fail("unknown", "retained cgroup evidence is unreadable")
        if len(data) > maximum:
            _fail("invalid", "retained cgroup evidence exceeds its bound")
        try:
            return data.decode("ascii")
        except UnicodeError:
            _fail("invalid", "retained cgroup evidence is malformed")

    def contains(self, cgroup_path: str) -> bool:
        if not isinstance(cgroup_path, str) or not cgroup_path.startswith("/"):
            _fail("unknown", "host cgroup path is malformed")
        parent_path = getattr(self, "cgroup_path", None)
        if not isinstance(parent_path, str) or not parent_path.startswith("/"):
            _fail("unsupported", "retained parent cgroup path is not bound")
        parent_path = parent_path.rstrip("/") or "/"
        if parent_path == "/":
            return True
        return cgroup_path == parent_path or cgroup_path.startswith(parent_path + "/")


class LinuxCgroupV2MembershipProbe:
    """Untrusted local probe; it cannot authorize source exclusion.

    PID 1 in the caller's procfs is not proof of the Docker Engine host. This
    probe is useful only to collect candidate membership observations. A
    reviewed host broker must bind its cgroup path to the retained handle,
    attest Engine-host namespace identity, and observe admitted job processes
    before production exclusion can be enabled.
    """
    def __init__(self, parent: RetainedCgroupV2Parent, *,
                 parent_cgroup_path: str, job_domain: RetainedCgroupV2Parent,
                 job_domain_id: str):
        if (not isinstance(parent, RetainedCgroupV2Parent) or
                not isinstance(job_domain, RetainedCgroupV2Parent)):
            _fail("unsupported", "Linux cgroup witness dependencies are unavailable")
        if (not parent_cgroup_path.startswith("/") or
                os.path.normpath(parent_cgroup_path) != parent_cgroup_path or
                parent_cgroup_path == "/"):
            _fail("unsupported", "host-visible cgroup parent path is not canonical")
        if parent.cgroup_path != parent_cgroup_path:
            _fail("ownership-conflict", "supplied cgroup path differs from retained FD")
        if (job_domain.cgroup_path == parent_cgroup_path or
                parent.contains(job_domain.cgroup_path) or
                job_domain.host_boot_identity != parent.host_boot_identity or
                job_domain.mount_id != parent.mount_id or
                job_domain.namespaces != parent.namespaces):
            _fail("unsupported", "persistent job domain is not separate on the same host")
        self.parent = parent
        self.job_domain = job_domain
        self.job_domain_id = _token(job_domain_id, "persistent job domain ID")

    def parent_snapshot(self) -> Mapping[str, Any]:
        return self.parent.snapshot()

    def assert_engine_host(self, engine: Mapping[str, Any]) -> bool:
        _fail("unsupported", "candidate probe has no trusted Engine-host identity attestation")

    @staticmethod
    def _process(pid: int) -> Tuple[str, str]:
        proc = Path("/proc") / str(_positive(pid, "host PID"))
        try:
            first = LinuxCgroupV2MembershipProbe._process_start_token(proc)
            rows = (proc / "cgroup").read_text(encoding="ascii").splitlines()
            second = LinuxCgroupV2MembershipProbe._process_start_token(proc)
        except (OSError, UnicodeError):
            _fail("unknown", "host process identity or cgroup membership is unavailable")
        if first != second:
            _fail("ownership-conflict", "host process changed during membership observation")
        paths = []
        for row in rows:
            parts = row.split(":", 2)
            if len(parts) == 3 and parts[0] == "0" and parts[1] == "":
                paths.append(parts[2])
        if len(paths) != 1 or not paths[0].startswith("/"):
            _fail("unknown", "host unified cgroup membership is ambiguous")
        return first, paths[0]

    @staticmethod
    def _process_start_token(proc: Path) -> str:
        try:
            text = (proc / "stat").read_text(encoding="ascii")
        except (OSError, UnicodeError):
            _fail("unknown", "host process start identity is unavailable")
        end = text.rfind(")")
        if end < 0:
            _fail("unknown", "host process start identity is malformed")
        fields = text[end + 2:].split()
        if len(fields) < 20:
            _fail("unknown", "host process start identity is truncated")
        return fields[19]

    def bind_container(self, host_pid: int) -> Mapping[str, Any]:
        first, path = self._process(host_pid)
        if not self.parent.contains(path):
            _fail("unsupported", "container init is outside its retained cgroup parent")
        second, path_after = self._process(host_pid)
        parent = self.parent.snapshot()
        if first != second or path != path_after:
            _fail("ownership-conflict", "container process changed during cgroup binding")
        return {
            "pid": host_pid,
            "start_token": first,
            "membership_digest": hashlib.sha256(path.encode("utf-8")).hexdigest(),
            "parent_identity_digest": parent["identity_digest"],
        }

    def supervisor_outside(self, parent: Mapping[str, Any]) -> bool:
        if _parent(self.parent.snapshot()) != _parent({
                **parent, "populated": 0, "frozen": 0}):
            _fail("ownership-conflict", "retained cgroup parent changed")
        _, path = self._process(os.getpid())
        return not self.parent.contains(path)

    def job_domain_witness(self, parent: Mapping[str, Any], job_domain_id: str,
                           jobs: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
        if (job_domain_id != self.job_domain_id or
                _parent(self.parent.snapshot()) != parent):
            _fail("ownership-conflict", "source or job domain binding changed")
        job = self.job_domain.snapshot()
        if (job["host_boot_identity"] != parent["host_boot_identity"] or
                job["mount_id"] != parent["mount_id"] or
                self.parent.contains(self.job_domain.cgroup_path)):
            _fail("ownership-conflict", "persistent job domain changed host or entered source")
        if not isinstance(jobs, Sequence) or isinstance(jobs, (str, bytes)):
            _fail("invalid", "admitted job roster is malformed")
        if (jobs and job["populated"] != 1) or (not jobs and job["populated"] != 0):
            _fail("unknown", "job-domain population disagrees with admitted jobs")
        seen = set()
        for item in jobs:
            record = _exact(item, frozenset({
                "job_id", "pid", "start_token", "domain_id", "job_domain_id",
            }), "admitted job process")
            if (record["job_id"] in seen or
                    record["domain_id"] != job_domain_id or
                    record["job_domain_id"] != job_domain_id):
                _fail("ownership-conflict", "admitted job identity is duplicated or changed")
            seen.add(record["job_id"])
            start, path = self._process(record["pid"])
            domain_path = self.job_domain.cgroup_path.rstrip("/")
            if (start != record["start_token"] or
                    not (path == domain_path or path.startswith(domain_path + "/"))):
                _fail("ownership-conflict", "admitted job process left its retained domain")
        # This roster only covers listed leaders.  A leader can exit while a
        # descendant remains, and an unrelated task can enter the job domain.
        # Neither case is complete job custody, even when every listed PID
        # matches.  A production runner must attest the entire subtree.
        return {
            "job_domain_id": job_domain_id,
            "domain_identity_digest": job["identity_digest"],
            "domain_live": True,
            "outside_parent": True,
            "membership_complete": False,
            "job_roster_digest": _hash(jobs),
            "live_processes_digest": _hash(jobs),
        }


def _parent(value: Any) -> Dict[str, Any]:
    fields = frozenset({
        "allocation_id", "host_boot_identity", "mount_id", "device", "inode",
        "cgroup_type", "identity_digest",
    })
    result = _exact(value, fields | {"populated", "frozen"}, "retained cgroup witness")
    if result["cgroup_type"] != "domain":
        _fail("unsupported", "retained cgroup parent is not a domain")
    _positive(result["mount_id"], "cgroup mount identity")
    _positive(result["device"], "cgroup device identity")
    _positive(result["inode"], "cgroup inode identity")
    _token(result["allocation_id"], "cgroup allocation ID")
    _token(result["host_boot_identity"], "cgroup host boot identity")
    for key in ("populated", "frozen"):
        if (isinstance(result[key], bool) or not isinstance(result[key], int) or
                result[key] not in {0, 1}):
            _fail("unknown", "retained cgroup %s state is malformed" % key)
    expected = _hash({key: result[key] for key in fields - {"identity_digest"}})
    if result["identity_digest"] != expected:
        _fail("invalid", "retained cgroup identity digest changed")
    return {key: result[key] for key in fields}


def _engine_identity(value: Any) -> Dict[str, Any]:
    fields = frozenset({
        "endpoint_identity", "engine_id", "engine_incarnation",
        "host_boot_identity", "os", "cgroup_driver", "cgroup_version",
        "rootless", "local_host", "live_restore",
    })
    result = _exact(value, fields, "Docker Engine identity")
    for key in ("endpoint_identity", "engine_id", "engine_incarnation", "host_boot_identity"):
        _token(result[key], "Engine %s" % key)
    if (result["os"] != "linux" or result["cgroup_driver"] not in {"systemd", "cgroupfs"} or
            result["cgroup_version"] != 2 or result["rootless"] is not False or
            result["local_host"] is not True or result["live_restore"] is not False):
        _fail("unsupported", "Docker Engine host/runtime tuple is unsupported")
    return result


def _inspect(value: Any) -> Dict[str, Any]:
    fields = frozenset({
        "container_id", "creation_identity", "configuration_digest", "state",
        "running", "restarting", "paused", "removing", "init_pid",
        "finished_identity", "exit_code", "exec_ids", "network_policy_digest",
        "parent_allocation_id",
    })
    result = _exact(value, fields, "Docker container inspection")
    if not isinstance(result["container_id"], str) or _CONTAINER_ID.fullmatch(result["container_id"]) is None:
        _fail("ownership-conflict", "Docker inspect did not return the bound full container ID")
    _token(result["creation_identity"], "Docker creation identity")
    _digest(result["configuration_digest"], "Docker resolved config digest")
    _digest(result["network_policy_digest"], "Docker resolved network policy digest")
    _token(result["parent_allocation_id"], "Docker cgroup parent allocation")
    if result["state"] not in {"created", "running", "exited", "dead"}:
        _fail("unsupported", "Docker container state is unsupported")
    for key in ("running", "restarting", "paused", "removing"):
        if not isinstance(result[key], bool):
            _fail("invalid", "Docker inspect state flag is malformed")
    pid = result["init_pid"]
    if isinstance(pid, bool) or not isinstance(pid, int) or pid < 0:
        _fail("invalid", "Docker init PID is malformed")
    if (result["state"] == "running") != (pid > 0) or (
            result["state"] == "running" and not result["running"]):
        _fail("ownership-conflict", "Docker state and init PID disagree")
    if result["finished_identity"] is not None:
        _token(result["finished_identity"], "Docker finished identity")
    if result["exit_code"] is not None and (
            isinstance(result["exit_code"], bool) or not isinstance(result["exit_code"], int)):
        _fail("invalid", "Docker exit code is malformed")
    if (not isinstance(result["exec_ids"], list) or len(result["exec_ids"]) > 256 or
            any(not isinstance(item, str) for item in result["exec_ids"]) or
            len(set(result["exec_ids"])) != len(result["exec_ids"])):
        _fail("invalid", "Docker exec roster is malformed")
    return result


class DockerSourceContainerProvider:
    """Internal candidate; positive exclusion is available to fake tests only.

    Production exclusion remains disabled until a separately reviewed host
    broker proves Engine-host identity, retained-FD/path custody, escape
    coverage, and every admitted job process membership.
    """
    def __init__(self, ledger: ClaudeCliSupervisedJobsLedger,
                 engine: DockerEngineAdapter, cgroup: CgroupWitness,
                 job_domain_id: str, other_witness_provider: Any = None,
                 *, test_only_fake_witness: bool = False):
        if not isinstance(ledger, ClaudeCliSupervisedJobsLedger):
            _fail("invalid", "Docker provider requires the managed jobs ledger")
        self.ledger, self.store = ledger, ledger.store
        self.engine, self.cgroup = engine, cgroup
        self.persistent_job_domain_id = _token(job_domain_id, "persistent job domain ID")
        self.other = other_witness_provider
        self.test_only_fake_witness = test_only_fake_witness
        if test_only_fake_witness and getattr(cgroup, "evidence_kind", None) != "offline-fake-test":
            _fail("invalid", "test-only exclusion requires the explicit fake cgroup witness")

    def history_manifest(self, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._delegate("history_manifest", binding)

    def job_status(self, binding: Mapping[str, Any], job_id: str) -> Mapping[str, Any]:
        return self._delegate("job_status", binding, job_id)

    def target_status(self, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._delegate("target_status", binding)

    def _delegate(self, name: str, *args: Any) -> Mapping[str, Any]:
        method = getattr(self.other, name, None)
        if not callable(method):
            _fail("unsupported", "trusted %s provider is unavailable" % name)
        return method(*args)

    def _call(self, name: str, *args: Any) -> Any:
        method = getattr(self.engine, name, None)
        if not callable(method):
            _fail("unsupported", "bounded Docker %s operation is unavailable" % name)
        try:
            value = method(*args, deadline=time.monotonic() + _TIMEOUT)
        except ManagedStateError:
            raise
        except Exception:
            _fail("uncertain-effect", "bounded Docker Engine operation failed")
        if value is not None and len(_json_bytes(value)) > 256 * 1024:
            _fail("invalid", "Docker Engine response exceeds its size bound")
        return value

    def _journal_path(self) -> Path:
        return self.store._json_path(_JOURNAL)

    def _load(self, owner: Mapping[str, Any], create: bool = False) -> Dict[str, Any]:
        path = self._journal_path()
        raw = self.store._read_path(path)
        supervisor_incarnation = self.ledger._load(owner)["supervisor_incarnation"]
        if raw is None:
            if not create:
                _fail("unknown", "Docker provider journal is absent")
            identity = self.store.identity
            return self._seal({
                "schema_version": 1, "capability": CAPABILITY, "provider": PROVIDER,
                "lane": identity.lane, "lane_key": identity.lane_key,
                "host": identity.host, "common_dir": str(identity.common_dir),
                "owner_generation": owner["generation"], "daemon_id": owner["daemon_id"],
                "supervisor_incarnation": supervisor_incarnation,
                "admissions": {}, "integrity_digest": "",
            })
        journal = _exact(raw, _JOURNAL_FIELDS, "Docker provider journal")
        identity = self.store.identity
        if (journal.get("schema_version") != 1 or journal.get("capability") != CAPABILITY or
                journal.get("provider") != PROVIDER or journal.get("lane") != identity.lane or
                journal.get("lane_key") != identity.lane_key or journal.get("host") != identity.host or
                journal.get("common_dir") != str(identity.common_dir) or
                journal.get("owner_generation") != owner.get("generation") or
                journal.get("daemon_id") != owner.get("daemon_id") or
                journal.get("supervisor_incarnation") != supervisor_incarnation):
            _fail("stale-generation", "Docker provider journal ownership changed")
        admissions = journal.get("admissions")
        if not isinstance(admissions, Mapping) or len(admissions) > 32:
            _fail("invalid", "Docker provider admission roster is malformed")
        for admission_id, admission in admissions.items():
            if str(uuid.UUID(admission_id)) != admission_id:
                _fail("invalid", "Docker admission ID is malformed")
            self._validate_admission(admission, admission_id)
        if journal.get("integrity_digest") != _hash({
                key: value for key, value in journal.items() if key != "integrity_digest"}):
            _fail("invalid", "Docker provider journal integrity digest changed")
        return journal

    @staticmethod
    def _seal(journal: Dict[str, Any]) -> Dict[str, Any]:
        journal["integrity_digest"] = ""
        journal["integrity_digest"] = _hash({
            key: value for key, value in journal.items() if key != "integrity_digest"
        })
        return journal

    def _write(self, journal: Dict[str, Any]) -> None:
        self._seal(journal)
        self.store._atomic_write(self._journal_path(), _json_bytes(journal) + b"\n")

    def _validate_admission(self, raw: Any, admission_id: str) -> Dict[str, Any]:
        value = _exact(raw, _ADMISSION_FIELDS, "Docker admission")
        if value.get("admission_id") != admission_id:
            _fail("invalid", "Docker admission ID changed")
        _positive(value.get("source_claim_generation"), "source generation")
        for key in ("parent_uuid", "source_runtime_incarnation",
                    "source_invocation_id", "source_domain_id"):
            _token(value.get(key), "Docker source %s" % key)
        _digest(value.get("source_manifest_digest"), "source manifest digest")
        _engine_identity(value.get("engine_identity"))
        for key, label in (("image_digest", "image digest"),
                           ("cli_executable_digest", "CLI executable digest")):
            if not isinstance(value.get(key), str) or _DIGEST.fullmatch(value[key]) is None:
                _fail("invalid", "%s is malformed" % label)
        _digest(value.get("configuration_digest"), "source configuration digest")
        stored_parent = _exact(value.get("parent_identity"), frozenset({
            "allocation_id", "host_boot_identity", "mount_id", "device", "inode",
            "cgroup_type", "identity_digest",
        }), "stored Docker cgroup parent identity")
        _parent({**stored_parent, "populated": 0, "frozen": 0})
        if value.get("phase") not in {
                "create-intent", "created", "start-intent", "started",
                "stop-intent", "stopped", "excluded", "indeterminate"}:
            _fail("invalid", "Docker admission phase is malformed")
        if value.get("container_id") is not None and (
                not isinstance(value["container_id"], str) or
                _CONTAINER_ID.fullmatch(value["container_id"]) is None):
            _fail("invalid", "Docker container ID is malformed")
        for key in ("container_creation_identity", "operation_id"):
            if value.get(key) is not None:
                _token(value[key], "Docker %s" % key)
        if value.get("container_config_digest") is not None:
            _digest(value["container_config_digest"], "Docker resolved config digest")
        if value.get("container_host_identity") is not None:
            _exact(value["container_host_identity"], frozenset({
                "pid", "start_token", "membership_digest", "parent_identity_digest",
            }), "Docker host process identity")
        mutations = value.get("mutations")
        if not isinstance(mutations, list) or len(mutations) > 3:
            _fail("invalid", "Docker mutation list is malformed")
        for mutation in mutations:
            item = _exact(mutation, _MUTATION_FIELDS, "Docker mutation intent")
            if item.get("kind") not in {"create", "start", "stop"}:
                _fail("invalid", "Docker mutation kind is malformed")
            _token(item.get("intent_id"), "Docker mutation intent ID")
            _digest(item.get("request_digest"), "Docker mutation digest")
            if item.get("state") not in {"dispatching", "completed", "uncertain"}:
                _fail("invalid", "Docker mutation state is malformed")
            if item.get("result_digest") is not None:
                _digest(item["result_digest"], "Docker mutation result digest")
        if value.get("last_witness") is not None:
            _exact(value["last_witness"], frozenset({
                "container_id", "creation_identity", "config_digest", "engine_incarnation",
                "parent_identity", "container_cgroup_identity", "populated",
                "supervisor_outside", "job_domain_id", "job_domain_outside",
                "job_domain_identity_digest", "job_roster_digest",
                "job_processes_digest", "mutation_digest", "witness_digest",
            }), "Docker exclusion witness")
        return value

    def _identity(self, expected: Mapping[str, Any] = None) -> Dict[str, Any]:
        current = _engine_identity(self._call("identity"))
        if expected is not None and current != dict(expected):
            _fail("ownership-conflict", "Docker Engine or host incarnation changed")
        return current

    def _persist_intent(self, journal: Dict[str, Any], admission: Dict[str, Any],
                        kind: str, request: Mapping[str, Any]) -> Dict[str, Any]:
        if any(item["state"] != "completed" for item in admission["mutations"]):
            _fail("uncertain-effect", "Docker mutation is unresolved; refusing replay")
        if len(admission["mutations"]) >= 3:
            _fail("busy", "Docker mutation journal is full")
        item = {
            "kind": kind, "intent_id": kind + "-" + secrets.token_hex(16),
            "request_digest": _hash(request), "state": "dispatching",
            "result_digest": None,
        }
        admission["mutations"].append(item)
        self._write(journal)
        return item

    def _complete(self, journal: Dict[str, Any], admission: Dict[str, Any],
                  intent: Dict[str, Any], result: Any) -> None:
        intent["state"] = "completed"
        intent["result_digest"] = _hash(result)
        self._write(journal)

    def _mark_uncertain(self, journal: Dict[str, Any], admission: Dict[str, Any],
                        intent: Dict[str, Any]) -> None:
        intent["state"] = "uncertain"
        admission["phase"] = "indeterminate"
        self._write(journal)

    def create_source(self, *, admission_id: str, claim_generation: int,
                      parent_uuid: str, runtime_incarnation: str,
                      invocation_id: str, source_domain_id: str,
                      manifest_digest: str, config: Mapping[str, Any]) -> Dict[str, Any]:
        admission_id = str(uuid.UUID(admission_id))
        config = normalize_config(config, state_root=self.store.identity.state_root)
        if config["claude_launch"]["parent_uuid"] != parent_uuid:
            _fail("ownership-conflict", "Claude CLI launch parent differs from source claim")
        generation = _positive(claim_generation, "source claim generation")
        engine = self._identity()
        self._assert_engine_host(engine)
        parent_observation = self.cgroup.parent_snapshot()
        parent = _parent(parent_observation)
        if (parent_observation["populated"] != 0 or parent_observation["frozen"] != 0 or
                parent["host_boot_identity"] != engine["host_boot_identity"]):
            _fail("unsupported", "retained host cgroup parent is not fresh and empty")
        request = {
            "admission_id": admission_id, "generation": generation,
            "parent_uuid": parent_uuid, "runtime_incarnation": runtime_incarnation,
            "invocation_id": invocation_id, "source_domain_id": source_domain_id,
            "manifest_digest": manifest_digest, "engine": engine,
            "config_digest": _hash(config), "parent": parent,
        }
        with self.ledger._locked() as owner:
            durable = self.ledger._load(owner)
            claim = durable.get("current_claim")
            if (not isinstance(claim, Mapping) or claim.get("state") != "active" or
                    claim.get("claim_generation") != generation or
                    claim.get("parent_uuid") != parent_uuid or
                    claim.get("runtime_incarnation") != runtime_incarnation or
                    claim.get("invocation_id") != invocation_id or
                    claim.get("domain_id") != source_domain_id or
                    claim.get("manifest_digest") != manifest_digest or
                    generation in durable.get("retired_source_generations", [])):
                _fail("stale-generation", "Docker launch does not match an active source claim")
            self._identity(engine)
            fresh_parent = self.cgroup.parent_snapshot()
            if (_parent(fresh_parent) != parent or fresh_parent["populated"] != 0 or
                    fresh_parent["frozen"] != 0):
                _fail("ownership-conflict", "retained cgroup parent changed before create")
            journal = self._load(owner, create=True)
            prior = journal["admissions"].get(admission_id)
            if prior is not None:
                if (prior["configuration_digest"] != request["config_digest"] or
                        prior["source_claim_generation"] != generation or
                        prior["parent_uuid"] != parent_uuid):
                    _fail("ownership-conflict", "Docker admission ID was reused with changed intent")
                return _copy(prior)
            admission = {
                "admission_id": admission_id,
                "source_claim_generation": generation, "parent_uuid": parent_uuid,
                "source_runtime_incarnation": runtime_incarnation,
                "source_invocation_id": invocation_id, "source_domain_id": source_domain_id,
                "source_manifest_digest": manifest_digest, "engine_identity": engine,
                "image_digest": config["image_digest"],
                "cli_executable_digest": config["cli_executable_digest"],
                "configuration_digest": request["config_digest"], "parent_identity": parent,
                "container_id": None, "container_creation_identity": None,
                "container_config_digest": None, "container_host_identity": None,
                "operation_id": None, "phase": "create-intent",
                "mutations": [], "last_witness": None,
            }
            journal["admissions"][admission_id] = admission
            intent = self._persist_intent(journal, admission, "create", request)
            try:
                container_id = self._call("create", admission_id, _copy(config))
                if not isinstance(container_id, str) or _CONTAINER_ID.fullmatch(container_id) is None:
                    _fail("uncertain-effect", "Docker create did not return a full container ID")
                seen = _inspect(self._call("inspect", container_id))
                if (seen["container_id"] != container_id or seen["state"] != "created" or
                        seen["running"] or seen["exec_ids"] or
                        seen["configuration_digest"] != request["config_digest"] or
                        seen["network_policy_digest"] != config["network_policy_digest"] or
                        seen["parent_allocation_id"] != parent["allocation_id"]):
                    _fail("ownership-conflict", "resolved Docker config does not match admission")
                admission["container_id"] = container_id
                admission["container_creation_identity"] = seen["creation_identity"]
                admission["container_config_digest"] = seen["configuration_digest"]
                admission["phase"] = "created"
                self._complete(journal, admission, intent, {
                    "container_id": container_id, "creation_identity": seen["creation_identity"],
                    "config_digest": seen["configuration_digest"],
                })
                return _copy(admission)
            except Exception:
                if intent["state"] == "dispatching":
                    self._mark_uncertain(journal, admission, intent)
                raise

    def _verify_inspect(self, admission: Mapping[str, Any], states: set) -> Dict[str, Any]:
        self._assert_engine_host(self._identity(admission["engine_identity"]))
        seen = _inspect(self._call("inspect", admission["container_id"]))
        if (seen["container_id"] != admission["container_id"] or
                seen["creation_identity"] != admission["container_creation_identity"] or
                seen["configuration_digest"] != admission["container_config_digest"] or
                seen["parent_allocation_id"] != admission["parent_identity"]["allocation_id"] or
                seen["state"] not in states or seen["restarting"] or seen["paused"] or
                seen["removing"] or seen["exec_ids"]):
            _fail("ownership-conflict", "fresh Docker inspection changed the bound container")
        return seen

    def _assert_engine_host(self, engine: Mapping[str, Any]) -> None:
        check = getattr(self.cgroup, "assert_engine_host", None)
        if not callable(check) or check(engine) is not True:
            _fail("unsupported", "trusted Engine-host identity attestation is unavailable")

    def start_source(self, admission_id: str, *, config: Mapping[str, Any]) -> Dict[str, Any]:
        admission_id = str(uuid.UUID(admission_id))
        config = normalize_config(config, state_root=self.store.identity.state_root)
        with self.ledger._locked() as owner:
            durable = self.ledger._load(owner)
            journal = self._load(owner)
            admission = journal["admissions"].get(admission_id)
            if not isinstance(admission, Mapping) or admission["phase"] != "created":
                _fail("uncertain-effect", "Docker source is not in a startable state")
            admission = dict(admission)
            journal["admissions"][admission_id] = admission
            claim = durable.get("current_claim")
            if (not isinstance(claim, Mapping) or claim.get("state") != "active" or
                    claim.get("claim_generation") != admission["source_claim_generation"] or
                    admission["source_claim_generation"] in durable.get("retired_source_generations", [])):
                _fail("ownership-conflict", "source generation was fenced before start")
            if _hash(config) != admission["configuration_digest"]:
                _fail("ownership-conflict", "Docker source configuration changed before start")
            fresh_parent = self.cgroup.parent_snapshot()
            if (_parent(fresh_parent) != admission["parent_identity"] or
                    fresh_parent["populated"] != 0 or fresh_parent["frozen"] != 0):
                _fail("ownership-conflict", "retained cgroup parent changed before start")
            self._verify_inspect(admission, {"created"})
            intent = self._persist_intent(journal, admission, "start", {
                "admission_id": admission_id, "container_id": admission["container_id"],
                "configuration_digest": admission["configuration_digest"],
                "parent_identity": admission["parent_identity"],
            })
            admission["phase"] = "start-intent"
            self._write(journal)
            try:
                self._call("start", admission["container_id"])
                seen = self._verify_inspect(admission, {"running"})
                host = _exact(self.cgroup.bind_container(seen["init_pid"]), frozenset({
                    "pid", "start_token", "membership_digest", "parent_identity_digest",
                }), "host container membership")
                if (host["pid"] != seen["init_pid"] or
                        host["parent_identity_digest"] != admission["parent_identity"]["identity_digest"]):
                    _fail("ownership-conflict", "container init is outside its retained parent")
                _token(host["start_token"], "container process start identity")
                _digest(host["membership_digest"], "container cgroup membership digest")
                again = self._verify_inspect(admission, {"running"})
                if again["init_pid"] != seen["init_pid"]:
                    _fail("ownership-conflict", "container init PID changed while binding membership")
                admission["container_host_identity"] = host
                admission["phase"] = "started"
                self._complete(journal, admission, intent, host)
                return _copy(admission)
            except Exception:
                if intent["state"] == "dispatching":
                    self._mark_uncertain(journal, admission, intent)
                raise

    def stop_source(self, operation_id: str) -> Dict[str, Any]:
        operation_id = _token(operation_id, "supervised operation ID")
        with self.ledger._locked() as owner:
            durable = self.ledger._load(owner)
            operation = self.ledger._operation(durable, operation_id)
            generation = operation["source_claim_generation"]
            if (operation["source_restart_denied"] is not True or
                    generation not in durable.get("retired_source_generations", [])):
                _fail("ownership-conflict", "durable source restart fence is absent")
            journal = self._load(owner)
            matches = [item for item in journal["admissions"].values()
                       if item["source_claim_generation"] == generation and
                       item["parent_uuid"] == operation["parent_uuid"] and
                       item["source_runtime_incarnation"] == operation["source_runtime_incarnation"]]
            if len(matches) != 1:
                _fail("unknown", "exact fenced Docker source admission is absent or ambiguous")
            admission = dict(matches[0])
            journal["admissions"][admission["admission_id"]] = admission
            if admission["phase"] == "stopped" and admission["operation_id"] == operation_id:
                return _copy(admission)
            if admission["phase"] not in {"created", "started"}:
                _fail("uncertain-effect", "Docker mutation is unresolved; refusing stop")
            fresh_parent = self.cgroup.parent_snapshot()
            if (_parent(fresh_parent) != admission["parent_identity"] or
                    fresh_parent["frozen"] != 0):
                _fail("ownership-conflict", "retained cgroup parent changed before stop")
            seen = self._verify_inspect(admission, {"created", "running", "exited", "dead"})
            intent = self._persist_intent(journal, admission, "stop", {
                "operation_id": operation_id, "source_generation": generation,
                "container_id": admission["container_id"],
                "engine_incarnation": admission["engine_identity"]["engine_incarnation"],
            })
            admission["operation_id"] = operation_id
            admission["phase"] = "stop-intent"
            self._write(journal)
            try:
                if seen["state"] == "running":
                    self._call("kill", admission["container_id"], "SIGKILL")
                # Engine kill acknowledgement precedes process exit on some
                # runtimes.  Poll observations only; never repeat the kill.
                stop_deadline = time.monotonic() + _TIMEOUT
                while True:
                    stopped = _inspect(self._call("inspect", admission["container_id"]))
                    if (stopped["container_id"] != admission["container_id"] or
                            stopped["creation_identity"] != admission["container_creation_identity"] or
                            stopped["configuration_digest"] != admission["container_config_digest"] or
                            stopped["restarting"] or stopped["paused"] or
                            stopped["removing"] or stopped["exec_ids"]):
                        _fail("ownership-conflict", "Docker source changed during stop")
                    parent = self.cgroup.parent_snapshot()
                    if (_parent(parent) != admission["parent_identity"] or
                            parent["frozen"] != 0):
                        _fail("ownership-conflict", "retained cgroup parent changed during stop")
                    terminal = (stopped["state"] in {"created", "exited", "dead"} and
                                not stopped["running"] and stopped["init_pid"] == 0 and
                                (stopped["state"] == "created" or
                                 (stopped["finished_identity"] is not None and
                                  stopped["exit_code"] is not None)))
                    if terminal and parent["populated"] == 0:
                        break
                    if time.monotonic() >= stop_deadline:
                        _fail("uncertain-effect", "Docker stop or source cgroup drain is unresolved")
                    time.sleep(0.05)
                admission["phase"] = "stopped"
                self._complete(journal, admission, intent, {
                    "operation_id": operation_id, "container_id": admission["container_id"],
                    "finished_identity": stopped["finished_identity"],
                    "parent_identity": admission["parent_identity"], "populated": 0,
                })
                return _copy(admission)
            except Exception:
                if intent["state"] == "dispatching":
                    self._mark_uncertain(journal, admission, intent)
                raise

    def source_exclusion(self, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        if (not self.test_only_fake_witness or
                getattr(self.cgroup, "evidence_kind", None) != "offline-fake-test"):
            _fail("unsupported", "production source exclusion needs the reviewed host broker")
        with self.ledger._locked() as owner:
            durable = self.ledger._load(owner)
            journal = self._load(owner)
            matches = [item for item in journal["admissions"].values()
                       if item["source_claim_generation"] == binding["source_claim_generation"] and
                       item["parent_uuid"] == binding["parent_uuid"] and
                       item["source_runtime_incarnation"] == binding["source_runtime_incarnation"] and
                       item["source_invocation_id"] == binding["source_invocation_id"]]
            if len(matches) != 1:
                _fail("unknown", "source container admission is absent or ambiguous")
            admission = matches[0]
            operation_id = admission["operation_id"]
            operation = self.ledger._operation(durable, operation_id) if operation_id else None
            if (admission["phase"] not in {"stopped", "excluded"} or operation is None or
                    operation["source_restart_denied"] is not True or
                    admission["source_claim_generation"] not in
                    durable.get("retired_source_generations", [])):
                _fail("ownership-conflict", "source container is not stopped behind its durable fence")
            self._assert_engine_host(self._identity(admission["engine_identity"]))
            seen = _inspect(self._call("inspect", admission["container_id"]))
            if (seen["container_id"] != admission["container_id"] or
                    seen["creation_identity"] != admission["container_creation_identity"] or
                    seen["configuration_digest"] != admission["container_config_digest"] or
                    seen["state"] not in {"exited", "dead"} or seen["running"] or
                    seen["restarting"] or seen["paused"] or seen["removing"] or
                    seen["init_pid"] != 0 or seen["finished_identity"] is None or
                    seen["exit_code"] is None or seen["exec_ids"]):
                _fail("unknown", "fresh exact-container inspection is not terminal")
            parent_observation = self.cgroup.parent_snapshot()
            parent = _parent(parent_observation)
            if (parent != admission["parent_identity"] or
                    parent_observation["populated"] != 0 or
                    parent_observation["frozen"] != 0):
                _fail("unknown", "retained cgroup parent is populated or its identity changed")
            supervisor_outside = self.cgroup.supervisor_outside(parent)
            expected_jobs = []
            for job_id in operation["job_ids"]:
                job = durable["jobs"].get(job_id)
                if not isinstance(job, Mapping):
                    _fail("invalid", "fenced operation lost a persistent job identity")
                if (job.get("state") in {"running", "launch-intent", "uncertain"} or
                        job.get("effect_state") == "unknown"):
                    process = job.get("process_identity")
                    if not isinstance(process, Mapping):
                        _fail("unknown", "live admitted job process identity is unavailable")
                    if (job.get("domain_id") != self.persistent_job_domain_id or
                            process.get("domain_id") != self.persistent_job_domain_id):
                        _fail("ownership-conflict", "admitted job process left its persistent domain")
                    expected_jobs.append({
                        "job_id": job_id,
                        "pid": process["pid"],
                        "start_token": process["start_token"],
                        "domain_id": process["domain_id"],
                        "job_domain_id": job["domain_id"],
                    })
            jobs_proof = _exact(self.cgroup.job_domain_witness(
                parent, self.persistent_job_domain_id, expected_jobs,
            ), frozenset({
                "job_domain_id", "domain_identity_digest", "domain_live",
                "outside_parent", "membership_complete", "job_roster_digest",
                "live_processes_digest",
            }), "persistent job domain witness")
            _digest(jobs_proof["domain_identity_digest"], "job domain identity digest")
            _digest(jobs_proof["job_roster_digest"], "job roster digest")
            _digest(jobs_proof["live_processes_digest"], "job process digest")
            if (jobs_proof["job_domain_id"] != self.persistent_job_domain_id or
                    jobs_proof["job_roster_digest"] != _hash(expected_jobs) or
                    jobs_proof["live_processes_digest"] != _hash(expected_jobs) or
                    jobs_proof["domain_live"] is not True or
                    jobs_proof["outside_parent"] is not True or
                    jobs_proof["membership_complete"] is not True):
                _fail("unsupported", "admitted job domain liveness or membership is unverified")
            jobs_outside = jobs_proof["outside_parent"]
            if supervisor_outside is not True or jobs_outside is not True:
                _fail("unsupported", "supervisor or admitted jobs are inside the source cgroup")
            if any(item["state"] != "completed" for item in admission["mutations"]):
                _fail("uncertain-effect", "Docker mutation journal has an unresolved intent")
            proof = {
                "container_id": admission["container_id"],
                "creation_identity": admission["container_creation_identity"],
                "config_digest": admission["container_config_digest"],
                "engine_incarnation": admission["engine_identity"]["engine_incarnation"],
                "parent_identity": parent,
                "container_cgroup_identity": admission["container_host_identity"],
                "populated": parent_observation["populated"],
                "supervisor_outside": supervisor_outside,
                "job_domain_id": self.persistent_job_domain_id,
                "job_domain_outside": jobs_outside,
                "job_domain_identity_digest": jobs_proof["domain_identity_digest"],
                "job_roster_digest": jobs_proof["job_roster_digest"],
                "job_processes_digest": jobs_proof["live_processes_digest"],
                "mutation_digest": _hash(admission["mutations"]),
            }
            witness_digest = _hash(proof)
            admission["last_witness"] = {**proof, "witness_digest": witness_digest}
            admission["phase"] = "excluded"
            self._write(journal)
            return {
                "witness_id": "offline-fake-docker-cgroup-exclusion-" + admission["admission_id"],
                "witness_digest": witness_digest,
                "observation_watermark": durable["observation_watermark"] + 1,
                "source_runtime_incarnation": binding["source_runtime_incarnation"],
                "source_domain_id": binding["source_domain_id"],
                "supervisor_incarnation": binding["supervisor_incarnation"],
                "parent_uuid": binding["parent_uuid"],
                "membership_complete": True,
                "escape_coverage_complete": True,
                "active_source_processes": 0,
                "restart_fence_effective": True,
                "job_domain_live": True,
            }
