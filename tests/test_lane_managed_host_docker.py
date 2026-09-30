# SPDX-License-Identifier: Apache-2.0
"""Bounded host transport tests; no real Docker mutation or account use."""

from __future__ import annotations

import hashlib
import copy
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from lane_managed_state import ManagedStateError
from lane_managed_host_docker import HostDockerEngineAdapter, LocalDockerSocket
from lane_managed_docker_source import normalize_config
from test_lane_managed_docker_source import _config
from test_lane_managed_supervised_jobs import _seed


host_unix_peer = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not hasattr(socket, "SO_PEERCRED"),
    reason="host Docker transport requires Linux Unix peer credentials",
)


def _serve(path: Path, handler):
    ready = threading.Event()
    observations = []

    def worker():
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            listener.listen(1)
            ready.set()
            with listener.accept()[0] as connection:
                connection.settimeout(0.25)
                handler(connection, observations)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    assert ready.wait(2)
    return thread, observations


@host_unix_peer
def test_local_docker_rejects_peer_before_post_dispatch(tmp_path: Path):
    path = tmp_path / "engine.sock"

    def handler(connection, observations):
        try:
            observations.append(connection.recv(128))
        except socket.timeout:
            observations.append(b"")

    thread, observations = _serve(path, handler)
    endpoint = LocalDockerSocket(path)

    def reject(_pid):
        raise ManagedStateError("unsupported", "untrusted peer")

    endpoint._peer = reject
    with pytest.raises(ManagedStateError) as rejected:
        endpoint.request("POST", "/containers/create", {}, deadline=time.monotonic() + 1)
    thread.join(1)
    assert rejected.value.code == "unsupported"
    assert observations == [b""]


@host_unix_peer
def test_local_docker_trickled_headers_obey_absolute_deadline(tmp_path: Path):
    path = tmp_path / "engine.sock"

    def handler(connection, observations):
        observations.append(connection.recv(1024))
        for byte in b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}":
            try:
                connection.sendall(bytes([byte]))
            except OSError:
                break
            time.sleep(0.015)

    thread, observations = _serve(path, handler)
    endpoint = LocalDockerSocket(path)
    endpoint._peer = lambda _pid: "reviewed-host-daemon"
    started = time.monotonic()
    with pytest.raises(ManagedStateError) as rejected:
        endpoint.request("GET", "/info", deadline=started + 0.1)
    assert rejected.value.code == "unknown"
    assert time.monotonic() - started < 0.4
    assert observations and observations[0].startswith(b"GET ")
    thread.join(1)


@host_unix_peer
@pytest.mark.parametrize("response,expected", [
    (b"HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n", None),
    (b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}", {}),
    (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
     b"2\r\n{}\r\n0\r\n\r\n", {}),
])
def test_local_docker_accepts_bounded_engine_response_shapes(
        tmp_path: Path, response: bytes, expected):
    path = tmp_path / "engine.sock"

    def handler(connection, observations):
        observations.append(connection.recv(1024))
        connection.sendall(response)

    thread, observations = _serve(path, handler)
    endpoint = LocalDockerSocket(path)
    endpoint._peer = lambda _pid: "reviewed-host-daemon"
    result = endpoint.request("GET", "/info", deadline=time.monotonic() + 1)
    thread.join(1)
    assert result == expected
    assert observations and observations[0].startswith(b"GET ")


@pytest.mark.skipif(os.name != "posix", reason="seccomp profile mode requires POSIX permissions")
def test_seccomp_profile_is_digest_checked_and_sent_as_compact_json(tmp_path: Path):
    profile = tmp_path / "seccomp.json"
    content = b'{\n  "defaultAction": "SCMP_ACT_ERRNO"\n}\n'
    profile.write_bytes(content)
    profile.chmod(0o600)
    adapter = object.__new__(HostDockerEngineAdapter)
    adapter.seccomp_profile = profile
    digest = hashlib.sha256(content).hexdigest()
    assert adapter._security_profile(digest) == '{"defaultAction":"SCMP_ACT_ERRNO"}'
    profile.write_text('{"defaultAction":"SCMP_ACT_ALLOW"}')
    with pytest.raises(ManagedStateError) as rejected:
        adapter._security_profile(digest)
    assert rejected.value.code == "ownership-conflict"


@pytest.mark.skipif(os.name != "posix", reason="seccomp profile mode requires POSIX permissions")
def test_resolved_mount_and_entrypoint_are_verified_before_config_digest(
        managed_workspace, tmp_path: Path):
    store = _seed(managed_workspace, tmp_path)
    profile = tmp_path / "seccomp.json"
    profile.write_text('{"defaultAction":"SCMP_ACT_ERRNO"}')
    profile.chmod(0o600)
    requested = _config(tmp_path, store)
    requested["seccomp_digest"] = hashlib.sha256(profile.read_bytes()).hexdigest()
    config = normalize_config(requested, state_root=store.identity.state_root)
    adapter = object.__new__(HostDockerEngineAdapter)
    adapter.seccomp_profile = profile
    adapter.parent = type("Parent", (), {"cgroup_path": "/l1/source"})()
    adapter.network_attestor = lambda _network, _policy, _raw: True
    raw = {
        "Config": {
            "Image": config["image_digest"], "Entrypoint": config["entrypoint"],
            "Cmd": [], "WorkingDir": "/", "Volumes": None,
            "User": config["user"], "Env": config["environment"],
            "Healthcheck": {"Test": ["NONE"]},
        },
        "AppArmorProfile": config["lsm_profile"],
        "HostConfig": {
            "CgroupParent": "/l1/source", "CgroupnsMode": "private",
            "NetworkMode": config["network_id"], "IpcMode": "private",
            "PidMode": "", "Privileged": False, "ReadonlyRootfs": True,
            "AutoRemove": False, "RestartPolicy": {"Name": "no"},
            "CapAdd": [], "CapDrop": ["ALL"], "Devices": [],
            "DeviceRequests": [], "Init": False,
            "Memory": config["memory_limit_bytes"], "PidsLimit": config["pids_limit"],
            "SecurityOpt": ["no-new-privileges:true",
                            "seccomp=" + adapter._security_profile(config["seccomp_digest"]),
                            "apparmor=" + config["lsm_profile"]],
        },
        "Mounts": [{
            "Type": "bind", "Destination": row["target"],
            "Source": row["source_path"], "RW": not row["read_only"],
            "Propagation": "rprivate",
        } for row in config["mounts"]],
    }
    adapter._resolved(raw, config)
    for mutation in (
            lambda value: value["Mounts"][0].pop("RW"),
            lambda value: value["Config"].__setitem__("Cmd", ["unexpected"]),
            lambda value: value["HostConfig"].__setitem__("CgroupParent", "/other")):
        changed = copy.deepcopy(raw)
        mutation(changed)
        with pytest.raises(ManagedStateError) as rejected:
            adapter._resolved(changed, config)
        assert rejected.value.code == "ownership-conflict"
