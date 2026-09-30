# SPDX-License-Identifier: Apache-2.0
"""Engine-host cgroup custody for the opt-in supervised-job candidate.

This is a host-process primitive, not a controller-side PID probe.  Its
allocation record is append-once: a service restart must not reopen or
recreate the named parent and call that continuous custody.  A separately
reviewed authenticated IPC service is still required before public use.
"""

from __future__ import annotations

import json
import os
import stat
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from lane_managed_state import ManagedStateError
from lane_managed_docker_source import (
    LinuxCgroupV2MembershipProbe, RetainedCgroupV2Parent,
)
from lane_managed_host_docker import LocalDockerSocket


def _fail(code: str, message: str) -> None:
    raise ManagedStateError(code, message)


def _host_namespaces() -> None:
    """Require the host PID and cgroup namespace, including host procfs."""
    if not os.sys.platform.startswith("linux"):
        _fail("unsupported", "Engine-host custody requires Linux")
    try:
        for name in ("pid", "cgroup"):
            if os.readlink("/proc/self/ns/" + name) != os.readlink(
                    "/proc/1/ns/" + name):
                _fail("unsupported", "broker is not in the host %s namespace" % name)
        if LinuxCgroupV2MembershipProbe._process_start_token(Path("/proc/1")) == "":
            _fail("unsupported", "broker cannot read host procfs")
    except (OSError, UnicodeError):
        _fail("unsupported", "broker host namespace identity is unavailable")


def _direct_directory(path: Path) -> None:
    if not path.is_absolute() or str(path) != os.path.normpath(str(path)):
        _fail("unsupported", "cgroup custody path is not canonical")
    cursor = Path("/")
    for part in path.parts[1:]:
        cursor /= part
        try:
            info = cursor.lstat()
        except OSError:
            _fail("unsupported", "cgroup custody directory is unavailable")
        if not stat.S_ISDIR(info.st_mode):
            _fail("unsupported", "cgroup custody path contains a link or non-directory")


def _mount_id(fd: int) -> int:
    try:
        contents = Path("/proc/self/fdinfo/%d" % fd).read_text(encoding="ascii")
        for line in contents.splitlines():
            if line.startswith("mnt_id:"):
                return int(line.split(":", 1)[1].strip())
    except (OSError, UnicodeError, ValueError):
        pass
    _fail("unsupported", "cgroup mount identity is unavailable")


class HostCgroupCustody:
    """Own two new disjoint cgroup-v2 domains and their retained FDs.

    ``record_path`` belongs to private broker state on durable storage.  Its
    exclusive creation happens before either cgroup mkdir.  It is never
    overwritten, including after a failed allocation.  Recovery needs a new
    reviewed continuous-FD design; this class intentionally cannot adopt.
    """

    def __init__(self, *, subtree: Path, record_path: Path,
                 endpoint: LocalDockerSocket):
        _host_namespaces()
        if not isinstance(endpoint, LocalDockerSocket):
            _fail("unsupported", "broker requires the verified local Engine endpoint")
        engine = endpoint.request("GET", "/info", deadline=time.monotonic() + 8.0)
        if (not isinstance(engine, dict) or engine.get("OSType") != "linux" or
                engine.get("CgroupDriver") != "cgroupfs" or
                str(engine.get("CgroupVersion")) != "2" or
                engine.get("LiveRestoreEnabled") is not False or
                not isinstance(engine.get("SecurityOptions"), list) or
                any("rootless" in str(value).lower()
                    for value in engine["SecurityOptions"])):
            _fail("unsupported", "Engine host is outside the cgroupfs candidate tuple")
        root = Path(subtree)
        record = Path(record_path)
        _direct_directory(root)
        _direct_directory(record.parent)
        try:
            root_info = root.stat()
            record_parent_info = record.parent.stat()
            boot = Path("/proc/sys/kernel/random/boot_id").read_text(
                encoding="ascii").strip()
        except (OSError, UnicodeError):
            _fail("unsupported", "host cgroup root or boot identity is unavailable")
        if not boot or root_info.st_mode & 0o022:
            _fail("unsupported", "cgroup allocation root is writable by other users")
        if (record_parent_info.st_uid != os.geteuid() or
                record_parent_info.st_mode & 0o077):
            _fail("unsupported", "broker allocation record directory is not private")
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        source_fd = job_fd = -1
        retained_source = retained_jobs = None
        try:
            mount_id = _mount_id(root_fd)
            fd_path = os.readlink("/proc/self/fd/%d" % root_fd)
            mountinfo = Path("/proc/self/mountinfo").read_text(encoding="ascii")
            root_cgroup_path = RetainedCgroupV2Parent._path_from_mountinfo(
                fd_path, mount_id, mountinfo)
            if root_cgroup_path == "/":
                _fail("unsupported", "broker cannot allocate at the cgroup root")
            if (root / "cgroup.type").read_text(encoding="ascii").strip() != "domain":
                _fail("unsupported", "broker cgroup root is not a domain")
            source_id, job_id = str(uuid.uuid4()), str(uuid.uuid4())
            source_name, job_name = "source-" + source_id, "jobs-" + job_id
            intent = {
                "schema_version": 1, "state": "allocation-intent",
                "host_boot_identity": boot, "mount_id": mount_id,
                "root_device": root_info.st_dev, "root_inode": root_info.st_ino,
                "source_allocation_id": source_id, "job_allocation_id": job_id,
                "source_name": source_name, "job_name": job_name,
            }
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            try:
                record_fd = os.open(record, flags, 0o600)
            except FileExistsError:
                _fail("uncertain-effect", "broker allocation record already exists")
            try:
                record_bytes = (json.dumps(intent, sort_keys=True) + "\n").encode("ascii")
                with os.fdopen(record_fd, "wb", closefd=False) as stream:
                    stream.write(record_bytes)
                    stream.flush()
                os.fsync(record_fd)
            finally:
                os.close(record_fd)
            directory_fd = os.open(record.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            os.mkdir(source_name, mode=0o700, dir_fd=root_fd)
            os.mkdir(job_name, mode=0o700, dir_fd=root_fd)
            source_fd = os.open(source_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=root_fd)
            job_fd = os.open(job_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                             dir_fd=root_fd)
            retained_source = RetainedCgroupV2Parent(
                source_fd, allocation_id=source_id, host_boot_identity=boot,
                mount_id=mount_id)
            retained_jobs = RetainedCgroupV2Parent(
                job_fd, allocation_id=job_id, host_boot_identity=boot,
                mount_id=mount_id)
            self.record_path = record
            self.endpoint_identity = endpoint.socket_identity
            self.daemon_incarnation = endpoint.peer_identity
            if (retained_source.contains(retained_jobs.cgroup_path) or
                    retained_jobs.contains(retained_source.cgroup_path)):
                _fail("ownership-conflict", "source and job domains overlap")
            self.source, self.jobs = retained_source, retained_jobs
        except BaseException:
            if retained_jobs is not None:
                retained_jobs.close()
            if retained_source is not None:
                retained_source.close()
            raise
        finally:
            if source_fd >= 0:
                os.close(source_fd)
            if job_fd >= 0:
                os.close(job_fd)
            os.close(root_fd)

    def close(self) -> None:
        self.source.close()
        self.jobs.close()


class HostCgroupWitness(LinuxCgroupV2MembershipProbe):
    """Host-only candidate witness; incomplete job roster cannot release."""

    def __init__(self, custody: HostCgroupCustody, endpoint: LocalDockerSocket):
        self.custody = custody
        self.endpoint = endpoint
        super().__init__(
            custody.source, parent_cgroup_path=custody.source.cgroup_path,
            job_domain=custody.jobs, job_domain_id=custody.jobs.allocation_id,
        )

    def assert_engine_host(self, engine: Mapping[str, Any]) -> bool:
        _host_namespaces()
        source = self.parent.snapshot()
        jobs = self.job_domain.snapshot()
        return bool(
            engine.get("os") == "linux" and
            engine.get("cgroup_driver") == "cgroupfs" and
            engine.get("cgroup_version") == 2 and
            engine.get("rootless") is False and
            engine.get("local_host") is True and
            engine.get("live_restore") is False and
            engine.get("engine_incarnation") == self.endpoint.peer_identity and
            engine.get("endpoint_identity") == self.endpoint.socket_identity and
            self.endpoint.socket_identity == self.custody.endpoint_identity and
            self.endpoint.peer_identity == self.custody.daemon_incarnation and
            engine.get("host_boot_identity") == source["host_boot_identity"] ==
            jobs["host_boot_identity"]
        )
