# SPDX-License-Identifier: Apache-2.0
"""Host-only Docker Engine adapter for the supervised Claude source candidate.

The adapter opens only a local Unix socket, binds the peer to a host-visible
``dockerd`` process, and checks fresh resolved inspect fields before returning
a configuration digest.  It deliberately has no exec, update, unpause,
restart or removal API.  The caller must retain its own durable mutation
intent and generation fence; an adapter restart never adopts a container.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import stat
import struct
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.parse import quote

from lane_managed_state import ManagedStateError
from lane_managed_docker_source import (
    LinuxCgroupV2MembershipProbe, RetainedCgroupV2Parent, _hash,
    normalize_config,
)


_API = "/v1.43"
_MAX_RESPONSE = 1024 * 1024


def _fail(code: str, message: str) -> None:
    raise ManagedStateError(code, message)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate Docker JSON key")
        result[key] = value
    return result


class _DeadlineReader:
    """Read one HTTP response with a wall-clock deadline, including trickle."""

    def __init__(self, conn: socket.socket, deadline: float):
        self.conn, self.deadline, self.buffer = conn, deadline, bytearray()

    def _receive(self) -> None:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("absolute Docker response deadline elapsed")
        self.conn.settimeout(remaining)
        chunk = self.conn.recv(65536)
        if not chunk:
            raise EOFError("Docker response ended early")
        self.buffer.extend(chunk)
        if len(self.buffer) > _MAX_RESPONSE + 65536:
            raise ValueError("Docker response exceeds its bound")

    def until(self, marker: bytes, maximum: int) -> bytes:
        while True:
            location = self.buffer.find(marker)
            if location >= 0:
                value = bytes(self.buffer[:location])
                del self.buffer[:location + len(marker)]
                return value
            if len(self.buffer) > maximum:
                raise ValueError("Docker response header exceeds its bound")
            self._receive()

    def exactly(self, count: int) -> bytes:
        if count < 0 or count > _MAX_RESPONSE:
            raise ValueError("Docker response body exceeds its bound")
        while len(self.buffer) < count:
            self._receive()
        value = bytes(self.buffer[:count])
        del self.buffer[:count]
        return value

    def response(self) -> tuple[int, bytes]:
        header = self.until(b"\r\n\r\n", 65536)
        lines = header.split(b"\r\n")
        if not lines or not lines[0].startswith(b"HTTP/1."):
            raise ValueError("Docker HTTP status is malformed")
        parts = lines[0].split(b" ", 2)
        if len(parts) < 2 or not parts[1].isdigit():
            raise ValueError("Docker HTTP status is malformed")
        headers: Dict[bytes, bytes] = {}
        for line in lines[1:]:
            name, separator, value = line.partition(b":")
            name = name.strip().lower()
            if not separator or not name or name in headers:
                raise ValueError("Docker HTTP headers are malformed or duplicated")
            headers[name] = value.strip().lower()
        status = int(parts[1])
        if status == 204:
            if headers.get(b"content-length") not in (None, b"0") or b"transfer-encoding" in headers:
                raise ValueError("Docker no-content reply has a body")
            return status, b""
        length, transfer = headers.get(b"content-length"), headers.get(b"transfer-encoding")
        if length is not None and transfer is not None:
            raise ValueError("Docker HTTP body framing is ambiguous")
        if length is not None:
            if not length.isdigit():
                raise ValueError("Docker HTTP length is malformed")
            body = self.exactly(int(length))
        elif transfer == b"chunked":
            chunks, size = [], 0
            while True:
                line = self.until(b"\r\n", 128)
                if not line or any(character not in b"0123456789abcdefABCDEF" for character in line):
                    raise ValueError("Docker chunk length is malformed")
                count = int(line, 16)
                size += count
                if size > _MAX_RESPONSE:
                    raise ValueError("Docker chunked body exceeds its bound")
                if count == 0:
                    if self.exactly(2) != b"\r\n":
                        raise ValueError("Docker chunk trailer is unsupported")
                    break
                chunks.append(self.exactly(count))
                if self.exactly(2) != b"\r\n":
                    raise ValueError("Docker chunk delimiter is malformed")
            body = b"".join(chunks)
        else:
            raise ValueError("Docker response has no bounded body framing")
        return status, body


class LocalDockerSocket:
    """Bounded Engine HTTP transport with a stable host daemon peer."""

    def __init__(self, socket_path: Path):
        path = Path(socket_path)
        if not path.is_absolute() or path.is_symlink():
            _fail("unsupported", "Docker endpoint must be a direct Unix socket path")
        try:
            info = path.stat()
        except OSError:
            _fail("unsupported", "Docker endpoint is unavailable")
        if not stat.S_ISSOCK(info.st_mode):
            _fail("unsupported", "Docker endpoint is not a Unix socket")
        self.path = path
        self.socket_identity = _hash({
            "device": info.st_dev, "inode": info.st_ino,
            "uid": info.st_uid, "mode": info.st_mode,
        })
        self.peer_identity: Optional[str] = None

    def _socket_unchanged(self) -> None:
        try:
            info = self.path.lstat()
        except OSError:
            _fail("ownership-conflict", "Docker endpoint disappeared")
        if not stat.S_ISSOCK(info.st_mode) or _hash({
                "device": info.st_dev, "inode": info.st_ino,
                "uid": info.st_uid, "mode": info.st_mode,
        }) != self.socket_identity:
            _fail("ownership-conflict", "Docker endpoint changed identity")

    def _peer(self, pid: int) -> str:
        proc = Path("/proc") / str(pid)
        try:
            executable = (proc / "exe").resolve(strict=True)
            pid_ns = os.readlink("/proc/self/ns/pid")
            daemon_ns = os.readlink(str(proc / "ns/pid"))
            host_ns = os.readlink("/proc/1/ns/pid")
            start = LinuxCgroupV2MembershipProbe._process_start_token(proc)
            boot = Path("/proc/sys/kernel/random/boot_id").read_text(
                encoding="ascii").strip()
        except (OSError, UnicodeError):
            _fail("unsupported", "Docker daemon host identity is unavailable")
        if (executable.name != "dockerd" or pid_ns != host_ns or
                daemon_ns != host_ns or not start.isdecimal()):
            _fail("unsupported", "Docker endpoint peer is not a visible host daemon")
        return _hash({"pid": pid, "start": start, "boot": boot,
                      "pid_namespace": host_ns})

    def request(self, method: str, endpoint: str, body: Any = None, *,
                deadline: float) -> Any:
        if (method not in {"GET", "POST"} or not endpoint.startswith("/") or
                ".." in endpoint or any(char in endpoint for char in "\x00\r\n")):
            _fail("invalid", "Docker API request is outside the bounded route")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _fail("uncertain-effect", "Docker request deadline elapsed before dispatch")
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        payload = (None if body is None else json.dumps(
            body, sort_keys=True, separators=(",", ":"),
            allow_nan=False).encode("utf-8"))
        if payload is not None and len(payload) > _MAX_RESPONSE:
            _fail("invalid", "Docker request body exceeds its bound")
        try:
            self._socket_unchanged()
            conn.settimeout(min(remaining, 8.0))
            conn.connect(str(self.path))
            if not hasattr(socket, "SO_PEERCRED"):
                _fail("unsupported", "Docker Unix peer credentials are unavailable")
            creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            peer_pid, _uid, _gid = struct.unpack("3i", creds)
            if peer_pid <= 1:
                _fail("unsupported", "Docker daemon peer PID is unavailable")
            peer = self._peer(peer_pid)
            self._socket_unchanged()
            if self.peer_identity is None:
                self.peer_identity = peer
            elif peer != self.peer_identity:
                _fail("ownership-conflict", "Docker daemon incarnation changed")
            if deadline - time.monotonic() <= 0:
                _fail("uncertain-effect", "Docker deadline elapsed before dispatch")
            request = ("%s %s%s HTTP/1.1\r\nHost: docker\r\nConnection: close\r\n"
                       "Content-Type: application/json\r\nContent-Length: %d\r\n\r\n" %
                       (method, _API, endpoint, len(payload or b""))).encode("ascii")
            conn.settimeout(max(deadline - time.monotonic(), 0.001))
            conn.sendall(request + (payload or b""))
            status, data = _DeadlineReader(conn, deadline).response()
            self._socket_unchanged()
            if self._peer(peer_pid) != peer:
                _fail("ownership-conflict", "Docker daemon changed during response")
            if status < 200 or status >= 300:
                # POST may have reached Engine before a reply.  Never retry it.
                _fail("uncertain-effect" if method == "POST" else "unknown",
                      "Docker Engine refused or did not complete the bounded request")
            return (json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
                    if data else None)
        except ManagedStateError:
            raise
        except (OSError, ValueError, UnicodeError, TimeoutError, EOFError):
            _fail("uncertain-effect" if method == "POST" else "unknown",
                  "Docker Engine request or response is unavailable")
        finally:
            conn.close()


class HostDockerEngineAdapter:
    """Real Engine calls; resolved config and external policy must both attest.

    ``image_attestor`` binds the immutable local image to the CLI executable.
    ``network_attestor`` checks the active egress policy and exact network
    attachment on each inspection.  Absent attestations refuse before create.
    Neither callback may infer evidence from labels or the requested digest.
    """

    def __init__(self, endpoint: LocalDockerSocket,
                 source_parent: RetainedCgroupV2Parent, *, state_root: Path,
                 seccomp_profile: Path,
                 image_attestor: Callable[[str, str], bool],
                 network_attestor: Callable[[str, str, Mapping[str, Any]], bool]):
        if not isinstance(source_parent, RetainedCgroupV2Parent):
            _fail("unsupported", "Docker adapter requires retained source custody")
        self.endpoint = endpoint
        self.parent = source_parent
        self.state_root = Path(state_root)
        self.seccomp_profile = Path(seccomp_profile)
        self.image_attestor = image_attestor
        self.network_attestor = network_attestor
        self._created: Dict[str, Dict[str, Any]] = {}

    def _security_profile(self, expected_digest: str) -> str:
        path = self.seccomp_profile
        if not path.is_absolute() or path.is_symlink():
            _fail("unsupported", "seccomp profile path is not trusted")
        try:
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
                _fail("unsupported", "seccomp profile is writable or not regular")
            content = path.read_bytes()
        except OSError:
            _fail("unsupported", "seccomp profile is unavailable")
        if len(content) > 256 * 1024 or hashlib.sha256(content).hexdigest() != expected_digest:
            _fail("ownership-conflict", "seccomp profile digest changed")
        try:
            profile = content.decode("utf-8")
            parsed = json.loads(profile, object_pairs_hook=_unique_object)
            if not isinstance(parsed, dict):
                raise ValueError("not an object")
        except (UnicodeError, ValueError):
            _fail("unsupported", "seccomp profile is not JSON")
        # Docker CLI compacts a seccomp file before sending SecurityOpt to the
        # Engine API.  Pin the source bytes, then compare the resolved compact
        # value rather than sending a pathname that only the CLI understands.
        return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)

    def identity(self, *, deadline: float) -> Mapping[str, Any]:
        version = self.endpoint.request("GET", "/version", deadline=deadline)
        if not isinstance(version, dict):
            _fail("unknown", "Docker API version response is malformed")
        try:
            maximum = tuple(int(part) for part in version["ApiVersion"].split("."))
            minimum = tuple(int(part) for part in version["MinAPIVersion"].split("."))
        except (KeyError, AttributeError, TypeError, ValueError):
            _fail("unknown", "Docker API version range is unavailable")
        if len(maximum) != 2 or len(minimum) != 2 or not minimum <= (1, 43) <= maximum:
            _fail("unsupported", "Docker Engine does not support the pinned API")
        info = self.endpoint.request("GET", "/info", deadline=deadline)
        if not isinstance(info, dict) or self.endpoint.peer_identity is None:
            _fail("unknown", "Docker Engine identity response is malformed")
        try:
            boot = Path("/proc/sys/kernel/random/boot_id").read_text(
                encoding="ascii").strip()
        except (OSError, UnicodeError):
            _fail("unsupported", "host boot identity is unavailable")
        security = info.get("SecurityOptions")
        if not isinstance(security, list):
            _fail("unknown", "Docker security options are unavailable")
        try:
            cgroup_version = int(info.get("CgroupVersion"))
        except (TypeError, ValueError):
            _fail("unknown", "Docker cgroup version is unavailable")
        return {
            "endpoint_identity": self.endpoint.socket_identity,
            "engine_id": info.get("ID"),
            "engine_incarnation": self.endpoint.peer_identity,
            "host_boot_identity": boot,
            "os": info.get("OSType"),
            "cgroup_driver": info.get("CgroupDriver"),
            "cgroup_version": cgroup_version,
            "rootless": any("rootless" in str(row).lower() for row in security),
            "local_host": True,
            "live_restore": info.get("LiveRestoreEnabled"),
        }

    def create(self, admission_id: str, config: Mapping[str, Any], *,
               deadline: float) -> str:
        normalized = normalize_config(config, state_root=self.state_root)
        parent = self.parent.snapshot()
        if parent["populated"] != 0 or parent["frozen"] != 0:
            _fail("ownership-conflict", "retained source parent is not empty")
        if not callable(self.image_attestor) or not callable(self.network_attestor):
            _fail("unsupported", "image or network policy attestation is unavailable")
        if self.image_attestor(normalized["image_digest"],
                               normalized["cli_executable_digest"]) is not True:
            _fail("unsupported", "image and CLI executable binding is unverified")
        profile = self._security_profile(normalized["seccomp_digest"])
        if self.network_attestor(normalized["network_id"],
                                 normalized["network_policy_digest"], {}) is not True:
            _fail("unsupported", "source network policy is unverified")
        mounts = [{
            "Type": "bind", "Source": row["source_path"],
            "Target": row["target"], "ReadOnly": row["read_only"],
            "BindOptions": {"Propagation": "rprivate"},
        } for row in normalized["mounts"]]
        host = {
            "CgroupParent": self.parent.cgroup_path,
            "CgroupnsMode": "private", "NetworkMode": normalized["network_id"],
            "IpcMode": "private", "PidMode": "", "Privileged": False,
            "ReadonlyRootfs": True, "AutoRemove": False,
            "RestartPolicy": {"Name": "no"}, "CapAdd": [], "CapDrop": ["ALL"],
            "Devices": [], "DeviceRequests": [], "Init": False,
            "Memory": normalized["memory_limit_bytes"],
            "PidsLimit": normalized["pids_limit"],
            "SecurityOpt": ["no-new-privileges:true",
                            "seccomp=" + profile,
                            "apparmor=" + normalized["lsm_profile"]],
            "Mounts": mounts,
        }
        body = {
            "Image": normalized["image_digest"],
            "Entrypoint": normalized["entrypoint"],
            "Cmd": [], "WorkingDir": "/", "User": normalized["user"],
            "Env": normalized["environment"],
            "HostConfig": host, "Healthcheck": {"Test": ["NONE"]},
            "Labels": {"openrepotools.admission": admission_id,
                       "openrepotools.config": _hash(normalized)},
        }
        result = self.endpoint.request("POST", "/containers/create", body,
                                       deadline=deadline)
        container_id = result.get("Id") if isinstance(result, dict) else None
        if (not isinstance(container_id, str) or len(container_id) != 64 or
                any(character not in "0123456789abcdef" for character in container_id)):
            _fail("uncertain-effect", "Docker create returned no full container ID")
        self._created[container_id] = normalized
        return container_id

    def _resolved(self, raw: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
        config = raw.get("Config")
        host = raw.get("HostConfig")
        if not isinstance(config, dict) or not isinstance(host, dict):
            _fail("unknown", "Docker resolved configuration is absent")
        profile = self._security_profile(expected["seccomp_digest"])
        if (config.get("Image") != expected["image_digest"] or
                config.get("Entrypoint") != expected["entrypoint"] or
                config.get("Cmd") not in (None, []) or
                config.get("WorkingDir") != "/" or
                config.get("Volumes") not in (None, {}) or
                config.get("User") != expected["user"] or
                config.get("Env") != expected["environment"] or
                raw.get("AppArmorProfile") != expected["lsm_profile"] or
                host.get("CgroupParent") != self.parent.cgroup_path or
                host.get("CgroupnsMode") != "private" or
                host.get("NetworkMode") != expected["network_id"] or
                host.get("IpcMode") != "private" or
                host.get("PidMode") not in {"", "private"} or
                host.get("Privileged") is not False or
                host.get("ReadonlyRootfs") is not True or
                host.get("AutoRemove") is not False or
                host.get("RestartPolicy", {}).get("Name") != "no" or
                host.get("CapAdd") not in (None, []) or
                host.get("CapDrop") != ["ALL"] or
                host.get("Devices") not in (None, []) or
                host.get("DeviceRequests") not in (None, []) or
                host.get("Init") not in (None, False) or
                host.get("Memory") != expected["memory_limit_bytes"] or
                host.get("PidsLimit") != expected["pids_limit"]):
            _fail("ownership-conflict", "Docker resolved source configuration changed")
        security = host.get("SecurityOpt")
        if not isinstance(security, list) or set(security) != {
                "no-new-privileges:true", "seccomp=" + profile,
                "apparmor=" + expected["lsm_profile"]}:
            _fail("ownership-conflict", "Docker resolved security options changed")
        healthcheck = config.get("Healthcheck")
        if healthcheck not in (None, {"Test": ["NONE"]}):
            _fail("ownership-conflict", "Docker resolved healthcheck changed")
        actual_mounts = raw.get("Mounts")
        if not isinstance(actual_mounts, list) or len(actual_mounts) != len(expected["mounts"]):
            _fail("ownership-conflict", "Docker resolved mount roster changed")
        desired = {row["target"]: row for row in expected["mounts"]}
        for mount in actual_mounts:
            if not isinstance(mount, dict) or mount.get("Destination") not in desired:
                _fail("ownership-conflict", "Docker resolved mount is unadmitted")
            row = desired.pop(mount["Destination"])
            if (mount.get("Type") != "bind" or
                    mount.get("Source") != row["source_path"] or
                    mount.get("RW") is not (not row["read_only"]) or
                    mount.get("Propagation") != "rprivate"):
                _fail("ownership-conflict", "Docker resolved mount changed")
        if desired or self.network_attestor(
                expected["network_id"], expected["network_policy_digest"], raw) is not True:
            _fail("ownership-conflict", "Docker network or mount policy changed")

    def inspect(self, container_id: str, *, deadline: float) -> Mapping[str, Any]:
        expected = self._created.get(container_id)
        if expected is None:
            _fail("uncertain-effect", "adapter lost exact created-container custody")
        raw = self.endpoint.request("GET", "/containers/%s/json" % quote(container_id),
                                    deadline=deadline)
        if not isinstance(raw, dict) or raw.get("Id") != container_id:
            _fail("ownership-conflict", "Docker inspect returned another container")
        self._resolved(raw, expected)
        state = raw.get("State")
        if not isinstance(state, dict):
            _fail("unknown", "Docker resolved state is absent")
        status = state.get("Status")
        if status not in {"created", "running", "exited", "dead"}:
            _fail("unsupported", "Docker source state is unsupported")
        finished = state.get("FinishedAt")
        if finished in (None, "", "0001-01-01T00:00:00Z"):
            finished = None
        exec_ids = raw.get("ExecIDs") or []
        if not isinstance(exec_ids, list):
            _fail("unknown", "Docker exec roster is malformed")
        return {
            "container_id": container_id,
            "creation_identity": raw.get("Created"),
            "configuration_digest": _hash(expected),
            "state": status, "running": state.get("Running"),
            "restarting": state.get("Restarting"),
            "paused": state.get("Paused"), "removing": state.get("RemovalInProgress", False),
            "init_pid": state.get("Pid"), "finished_identity": finished,
            "exit_code": state.get("ExitCode") if finished is not None else None,
            "exec_ids": exec_ids,
            "network_policy_digest": expected["network_policy_digest"],
            "parent_allocation_id": self.parent.allocation_id,
        }

    def start(self, container_id: str, *, deadline: float) -> None:
        if container_id not in self._created:
            _fail("uncertain-effect", "source container is outside adapter custody")
        self.endpoint.request("POST", "/containers/%s/start" % quote(container_id),
                              deadline=deadline)

    def kill(self, container_id: str, signal_name: str, *, deadline: float) -> None:
        if container_id not in self._created or signal_name != "SIGKILL":
            _fail("unsupported", "only bound source SIGKILL is admitted")
        self.endpoint.request("POST", "/containers/%s/kill?signal=SIGKILL" %
                              quote(container_id), deadline=deadline)
