# SPDX-License-Identifier: Apache-2.0
"""Read-only facts for locating a viable Engine-host broker placement.

Usage: python3 -m lane_managed_host_preflight --socket /var/run/docker.sock
The report contains no account, container, path inventory or credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import struct
import subprocess
from pathlib import Path
from typing import Optional


def _namespace(name: str) -> Optional[str]:
    try:
        return os.readlink("/proc/%s/ns/%s" % (name.split(":", 1)[0],
                                                name.split(":", 1)[1]))
    except (OSError, UnicodeError):
        return None


def inspect(socket_path: Path) -> dict:
    result = {
        "schema_version": 1, "linux": os.sys.platform.startswith("linux"),
        "endpoint_socket": False, "peer_pid_visible": False,
        "host_pid_namespace_readable": False,
        "same_pid_namespace_as_pid1": False,
        "host_cgroup_namespace_readable": False,
        "same_cgroup_namespace_as_pid1": False,
        "cgroup_v2_mount_writable": False,
        "engine_info_available": False,
        "engine_cgroup_driver": None, "engine_cgroup_version": None,
        "engine_rootless": None, "engine_live_restore": None,
        "host_broker_candidate": False,
    }
    try:
        info = socket_path.lstat()
        result["endpoint_socket"] = stat.S_ISSOCK(info.st_mode)
    except OSError:
        return result
    if result["endpoint_socket"] and hasattr(socket, "SO_PEERCRED"):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.settimeout(3)
                conn.connect(str(socket_path))
                peer = struct.unpack("3i", conn.getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[0]
                result["peer_pid_visible"] = peer > 1 and Path(
                    "/proc/%d/stat" % peer).is_file()
        except OSError:
            pass
    for namespace in ("pid", "cgroup"):
        current = _namespace("self:" + namespace)
        first = _namespace("1:" + namespace)
        result["host_%s_namespace_readable" % namespace] = first is not None
        result["same_%s_namespace_as_pid1" % namespace] = bool(
            first and current == first)
    try:
        mountinfo = Path("/proc/self/mountinfo").read_text(encoding="ascii")
        result["cgroup_v2_mount_writable"] = any(
            " - cgroup2 " in row and "rw" in row.split(" - ", 1)[0].split()[5].split(",")
            for row in mountinfo.splitlines() if " - cgroup2 " in row
        )
    except (OSError, UnicodeError, IndexError):
        pass
    try:
        completed = subprocess.run(
            ["docker", "--host", "unix://" + str(socket_path), "info",
             "--format", "{{json .}}"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=8, check=True, text=True,
        )
        if len(completed.stdout) <= 1024 * 1024:
            engine = json.loads(completed.stdout)
            result["engine_info_available"] = isinstance(engine, dict)
            if isinstance(engine, dict):
                result["engine_cgroup_driver"] = engine.get("CgroupDriver")
                result["engine_cgroup_version"] = engine.get("CgroupVersion")
                security = engine.get("SecurityOptions")
                result["engine_rootless"] = (
                    any("rootless" in str(value).lower() for value in security)
                    if isinstance(security, list) else None)
                result["engine_live_restore"] = engine.get("LiveRestoreEnabled")
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    result["host_broker_candidate"] = bool(
        result["linux"] and result["endpoint_socket"] and
        result["peer_pid_visible"] and
        result["host_pid_namespace_readable"] and
        result["same_pid_namespace_as_pid1"] and
        result["host_cgroup_namespace_readable"] and
        result["same_cgroup_namespace_as_pid1"] and
        result["cgroup_v2_mount_writable"] and
        result["engine_info_available"] and
        result["engine_cgroup_driver"] == "cgroupfs" and
        str(result["engine_cgroup_version"]) == "2" and
        result["engine_rootless"] is False and
        result["engine_live_restore"] is False
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, default=Path("/var/run/docker.sock"))
    args = parser.parse_args()
    result = inspect(args.socket)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["host_broker_candidate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
