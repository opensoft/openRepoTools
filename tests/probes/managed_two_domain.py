#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Opt-in Bite 4 source/target container orchestrator.

This is a bounded diagnostic only.  It never grants production capability and
does not alter the legacy managed_native_loopback entrypoint.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import posixpath
from pathlib import Path
import re
import selectors
import stat
import subprocess
import sys
import threading
import time
import uuid
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
import managed_native_loopback as probe  # noqa: E402


STATE_ROOT = "/opt/state"
LOOPBACK_ROOT = "/opt/loopback"
HISTORY_QUERY_MODE = probe.TWO_DOMAIN_HISTORY_QUERY_MODE
TMPFS_PROFILE = {
    "/tmp": "rw,nosuid,nodev,noexec,size=100663296",
    LOOPBACK_ROOT: "rw,nosuid,nodev,exec,size=268435456",
}
TARGET_PROFILE = {
    "network": "none",
    "readonly_rootfs": True,
    "cap_drop": ["ALL"],
    "no_new_privileges": True,
    "pids_limit": 96,
    "memory": 805306368,
    "nano_cpus": 1000000000,
    "restart": "no",
    "tmpfs": TMPFS_PROFILE,
}


MAX_PRIVATE_DOCKER_STDERR = 4096
MAX_MOUNT_WITNESS_REQUEST_BYTES = 2048
MAX_MOUNTINFO_BYTES = 64 * 1024
MAX_MOUNT_WITNESS_RESPONSE_BYTES = 128 * 1024
MAX_MOUNT_WITNESS_STDERR_BYTES = 4096
MOUNT_WITNESS_PROTOCOL = "mountinfo-two-stage-v1"
SOURCE_RUNTIME_REPORT_ENVELOPE_SCHEMA = "openrepotools-bite4-private-source-runtime-envelope/v1"
MOUNT_WITNESS_WRAPPER = r'''import base64,json,os,re,select,sys,time
MAX_REQUEST=2048
MAX_MOUNTINFO=65536
MAX_RESPONSE=131072
MAX_LIFETIME=900.0
REQUEST_TIMEOUT=180.0
def die():
    raise SystemExit(81)
def pairs(rows):
    result={}
    for key,value in rows:
        if key in result:
            die()
        result[key]=value
    return result
def read_bounded(fd,limit,deadline):
    chunks=bytearray()
    while len(chunks)<=limit:
        remaining=deadline-time.monotonic()
        if remaining<=0 or not select.select([fd],[],[],remaining)[0]:
            die()
        chunk=os.read(fd,min(4096,limit+1-len(chunks)))
        if not chunk:
            die()
        chunks.extend(chunk)
        if len(chunks)>limit:
            die()
        if b"\n" in chunks:
            if chunks.count(b"\n")!=1 or not chunks.endswith(b"\n"):
                die()
            return bytes(chunks)
    die()
def read_request(stage,seen,deadline):
    raw=read_bounded(0,MAX_REQUEST,deadline)
    try:
        value=json.loads(raw[:-1].decode("ascii"),object_pairs_hook=pairs)
    except Exception:
        die()
    if type(value) is not dict or set(value)!={"schema","nonce","stage"}:
        die()
    nonce=value.get("nonce")
    if (value.get("schema")!="openrepotools-mount-witness-request/v1"
            or value.get("stage")!=stage or not isinstance(nonce,str)
            or not re.fullmatch(r"[0-9a-f]{32}",nonce) or nonce in seen):
        die()
    seen.add(nonce)
    return nonce
def process_start_token():
    with open("/proc/self/stat","rb") as stream:
        raw=stream.read(8193)
    if len(raw)>8192 or b"\0" in raw or not raw.endswith(b"\n"):
        die()
    raw=raw[:-1]
    if b"\n" in raw:
        die()
    close=raw.rfind(b")")
    if close<0:
        die()
    fields=raw[close+1:].split()
    if len(fields)<20 or not fields[19].isdigit():
        die()
    return fields[19].decode("ascii")
def capture_mountinfo():
    namespace_before=os.readlink("/proc/self/ns/mnt")
    start_before=process_start_token()
    if not re.fullmatch(r"mnt:\[[0-9]+\]",namespace_before):
        die()
    with open("/proc/self/mountinfo","rb",buffering=0) as stream:
        mountinfo=stream.read(MAX_MOUNTINFO+1)
    namespace_after=os.readlink("/proc/self/ns/mnt")
    start_after=process_start_token()
    if (namespace_before!=namespace_after or start_before!=start_after
            or not mountinfo or len(mountinfo)>MAX_MOUNTINFO):
        die()
    return namespace_before,start_before,mountinfo
started=time.monotonic()
start_token=process_start_token()
if not re.fullmatch(r"[0-9]+",start_token):
    die()
seen=set()
for stage in ("before-upload","before-work"):
    deadline=min(started+MAX_LIFETIME,time.monotonic()+REQUEST_TIMEOUT)
    nonce=read_request(stage,seen,deadline)
    try:
        mount_namespace,observed_start_token,mountinfo=capture_mountinfo()
    except Exception:
        die()
    if observed_start_token!=start_token:
        die()
    response={"schema":"openrepotools-mount-witness-response/v1",
              "nonce":nonce,"stage":stage,"start_token":start_token,
              "mount_namespace":mount_namespace,
              "mountinfo_b64":base64.b64encode(mountinfo).decode("ascii")}
    frame=json.dumps(response,separators=(",",":"),ensure_ascii=True).encode("ascii")
    if len(frame)>MAX_RESPONSE or b"\n" in frame:
        die()
    sys.stdout.buffer.write(frame+b"\n")
    sys.stdout.buffer.flush()
while time.monotonic()<started+MAX_LIFETIME:
    remaining=started+MAX_LIFETIME-time.monotonic()
    if not select.select([0],[],[],remaining)[0]:
        break
    extra=os.read(0,1)
    if not extra:
        break
    die()
'''
MOUNT_WITNESS_WRAPPER_SHA256 = hashlib.sha256(
    MOUNT_WITNESS_WRAPPER.encode("utf-8")
).hexdigest()
TARGET_PROFILE["mount_witness_protocol"] = MOUNT_WITNESS_PROTOCOL
TARGET_PROFILE["mount_witness_wrapper_sha256"] = MOUNT_WITNESS_WRAPPER_SHA256


def _decode_mountinfo_path(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        code = int(match.group(1), 8)
        if code not in {0o11, 0o12, 0o40, 0o134}:
            raise RuntimeError("mountinfo contains an unsupported path escape")
        return chr(code)

    remaining = re.sub(r"\\([0-7]{3})", "", value)
    decoded = re.sub(r"\\([0-7]{3})", replace, value)
    if "\\" in remaining or "\x00" in decoded:
        raise RuntimeError("mountinfo path escape is malformed")
    return decoded


def _mount_option_tokens(value: str) -> list[str]:
    if not value:
        raise RuntimeError("mountinfo options are empty")
    tokens = value.split(",")
    if (any(not re.fullmatch(r"[A-Za-z0-9_.:=+-]+", token) for token in tokens)
            or len(set(tokens)) != len(tokens)):
        raise RuntimeError("mountinfo options are malformed or duplicated")
    return tokens


def _mount_size_bytes(value: str, destination: str) -> int:
    expected = {
        "/tmp": 100663296,
        LOOPBACK_ROOT: 268435456,
    }.get(destination)
    if expected is None:
        raise RuntimeError("mountinfo size destination is unknown")
    if re.fullmatch(r"[0-9]+", value):
        size = int(value)
    elif re.fullmatch(r"[0-9]+[kK]", value):
        size = int(value[:-1]) * 1024
    else:
        raise RuntimeError("mountinfo tmpfs size is malformed")
    if size != expected:
        raise KnownViolation("mountinfo-tmpfs-size-profile-mismatch")
    return size


def _parse_mountinfo_policy(raw: bytes) -> dict[str, object]:
    """Parse bounded Linux mountinfo and attest the two controlled tmpfs mounts."""

    if (not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_MOUNTINFO_BYTES
            or not raw.endswith(b"\n")
            or any((byte < 32 and byte != 10) or byte == 127 for byte in raw)):
        raise RuntimeError("mountinfo evidence is empty, malformed or oversized")
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeDecodeError as exc:
        raise RuntimeError("mountinfo evidence is not ASCII") from exc
    controlled: dict[str, dict[str, object]] = {}
    seen_mount_ids: set[int] = set()
    ignored_tmpfs_count = 0
    root_mount_count = 0
    lines = text[:-1].split("\n")
    if not lines or any(not line for line in lines):
        raise RuntimeError("mountinfo evidence contains an empty row")
    for line in lines:
        halves = line.split(" - ")
        if len(halves) != 2:
            raise RuntimeError("mountinfo row separator is malformed")
        left = halves[0].split()
        right = halves[1].split()
        if len(left) < 6 or len(right) != 3:
            raise RuntimeError("mountinfo row fields are incomplete")
        if (not left[0].isdecimal() or not left[1].isdecimal()
                or not re.fullmatch(r"[0-9]+:[0-9]+", left[2])):
            raise RuntimeError("mountinfo identity fields are malformed")
        mount_id = int(left[0])
        parent_id = int(left[1])
        if mount_id <= 0 or parent_id <= 0 or mount_id in seen_mount_ids:
            raise RuntimeError("mountinfo mount identity is invalid or duplicated")
        seen_mount_ids.add(mount_id)
        root = _decode_mountinfo_path(left[3])
        destination = _decode_mountinfo_path(left[4])
        if (not root.startswith("/") or root.startswith("//")
                or posixpath.normpath(root) != root
                or any(ord(character) < 32 or ord(character) == 127 for character in root)
                or not destination.startswith("/") or destination.startswith("//")
                or posixpath.normpath(destination) != destination
                or any(ord(character) < 32 or ord(character) == 127
                       for character in destination)):
            raise RuntimeError("mountinfo destination path is not normalized")
        if destination == "/":
            root_mount_count += 1
            if root_mount_count > 1:
                raise KnownViolation("mountinfo-root-overmount")
        if destination == "/opt":
            raise KnownViolation("mountinfo-controlled-ancestor-overmount")
        related = next((path for path in ("/tmp", LOOPBACK_ROOT)
                        if destination == path or destination.startswith(path + "/")), None)
        filesystem, mount_source, super_option_text = right
        if related is None:
            ignored_tmpfs_count += int(filesystem == "tmpfs")
            continue
        if destination != related:
            raise KnownViolation("mountinfo-nested-controlled-mount")
        if destination in controlled:
            raise KnownViolation("mountinfo-duplicate-controlled-mount")
        if filesystem != "tmpfs" or root != "/":
            raise KnownViolation("mountinfo-controlled-filesystem-mismatch")
        mount_options = _mount_option_tokens(left[5])
        super_options = _mount_option_tokens(super_option_text)
        mount_set = set(mount_options)
        super_set = set(super_options)
        if (not {"rw", "nosuid", "nodev"}.issubset(mount_set)
                or {"ro", "suid", "dev"}.intersection(mount_set)
                or "rw" not in super_set
                or {"ro", "suid", "dev"}.intersection(super_set)):
            raise KnownViolation("mountinfo-controlled-mount-flags-unsafe")
        if destination == "/tmp":
            if "noexec" not in mount_set or "exec" in mount_set | super_set:
                raise KnownViolation("mountinfo-tmpfs-exec-policy-mismatch")
        elif "noexec" in mount_set | super_set:
            raise KnownViolation("mountinfo-tmpfs-exec-policy-mismatch")
        size_tokens = [token[5:] for token in mount_options + super_options
                       if token.startswith("size=")]
        if len(size_tokens) != 1:
            raise KnownViolation("mountinfo-tmpfs-size-missing-or-duplicated")
        size_bytes = _mount_size_bytes(size_tokens[0], destination)
        controlled[destination] = {
            "mount_id": mount_id,
            "parent_id": parent_id,
            "device": left[2],
            "root": root,
            "destination": destination,
            "filesystem": filesystem,
            "mount_source": mount_source,
            "mount_options": sorted(mount_options),
            "optional_fields": sorted(left[6:]),
            "super_options": sorted(super_options),
            "size_bytes": size_bytes,
        }
    if root_mount_count != 1:
        raise RuntimeError("mountinfo root mount inventory is incomplete")
    if set(controlled) != {"/tmp", LOOPBACK_ROOT}:
        raise KnownViolation("mountinfo-controlled-tmpfs-inventory-mismatch")
    return {
        "mounts": [controlled[path] for path in sorted(controlled)],
        "ignored_tmpfs_count": ignored_tmpfs_count,
    }


class DockerCommandError(subprocess.CalledProcessError):
    """Docker failed; retain only a bounded stderr excerpt for the private ledger."""

    def __init__(
        self, returncode: int, command: tuple[str, ...], *,
        output: bytes, stderr: bytes,
    ) -> None:
        bounded_stderr = stderr[:MAX_PRIVATE_DOCKER_STDERR]
        super().__init__(returncode, command, output=output, stderr=bounded_stderr)
        self.private_stderr = bounded_stderr
        self.private_stderr_truncated = len(stderr) > MAX_PRIVATE_DOCKER_STDERR


def _docker(
    *args: str,
    timeout: int = 45,
    check: bool = True,
    input: bytes | None = None,
) -> subprocess.CompletedProcess:
    command = ("docker", *args)
    result = subprocess.run(
        command, check=False, capture_output=True, timeout=timeout,
        input=input,
    )
    if check and result.returncode:
        stderr = result.stderr if isinstance(result.stderr, bytes) else b""
        stdout = result.stdout if isinstance(result.stdout, bytes) else b""
        raise DockerCommandError(
            result.returncode, command, output=stdout, stderr=stderr,
        )
    return result


def _json_output(result: subprocess.CompletedProcess) -> object:
    return json.loads(result.stdout.decode("utf-8"))


def _digest(value: object) -> str:
    return hashlib.sha256(probe._canonical_json(value)).hexdigest()


def _inspect_container(container_id: str, *, timeout: int = 45) -> Mapping[str, object]:
    records = _json_output(_docker("inspect", container_id, timeout=timeout))
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], Mapping):
        raise RuntimeError("container inspection is incomplete")
    return records[0]


def _container_absent(container_id: str) -> bool:
    rows = _docker(
        "ps", "-aq", "--no-trunc", "--filter", "id=" + container_id,
    ).stdout.decode("ascii", "replace").splitlines()
    return not any(row.strip() for row in rows)


def _volume_create(
    name: str, run_id: str, role: str,
    observer: TwoDomainObserver | None = None,
) -> str:
    if observer is not None:
        observer.expect_object_creation(kind="volume", name=name, role=role)
    if not _volume_absent(name, timeout=8):
        raise KnownViolation("volume-name-reuse")
    result = _docker(
        "volume", "create",
        "--label", "openrepotools.bite4.run=" + run_id,
        "--label", "openrepotools.bite4.role=" + role,
        name,
    )
    actual = result.stdout.decode("ascii", "strict").strip()
    if actual != name:
        raise RuntimeError("engine-created volume identity mismatch")
    return actual


def _volume_absent(name: str, *, timeout: int = 8) -> bool:
    result = _docker("volume", "inspect", name, check=False, timeout=timeout)
    if result.returncode == 0:
        return False
    error_text = (result.stdout + result.stderr).decode("utf-8", "replace")
    if len(error_text) > 4096:
        raise RuntimeError("volume absence result exceeds its bound")
    if "no such volume" in error_text.lower():
        return True
    raise RuntimeError("volume absence could not be confirmed")


def _inspect_volume(name: str, *, timeout: int = 45) -> Mapping[str, object]:
    records = _json_output(_docker("volume", "inspect", name, timeout=timeout))
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], Mapping):
        raise RuntimeError("engine volume inspection is incomplete")
    return records[0]


def _validate_new_volume(
    name: str, run_id: str, role: str, *, timeout: int = 45,
) -> Mapping[str, object]:
    record = _inspect_volume(name, timeout=timeout)
    labels = record.get("Labels")
    options = record.get("Options")
    expected_labels = {
        "openrepotools.bite4.run": run_id,
        "openrepotools.bite4.role": role,
    }
    if (record.get("Name") != name or record.get("Driver") != "local"
            or record.get("Scope") != "local"
            or (options is not None and options != {})
            or not isinstance(labels, Mapping)
            or dict(labels) != expected_labels):
        raise RuntimeError("run fixture volume is not a plain engine-managed local volume")
    mountpoint = record.get("Mountpoint")
    if not isinstance(mountpoint, str) or not mountpoint:
        raise RuntimeError("run fixture volume mountpoint was not reported")
    return record


def _container_ids_for_run(run_id: str, *, timeout: int = 45) -> list[str]:
    result = _docker(
        "ps", "-aq", "--no-trunc",
        "--filter", "label=openrepotools.bite4.run=" + run_id,
        timeout=timeout,
    )
    rows = [row.strip() for row in result.stdout.decode("ascii", "replace").splitlines()
            if row.strip()]
    if len(rows) > 8 or any(not re.fullmatch(r"[0-9a-f]{12,64}", row) for row in rows):
        raise RuntimeError("run-scoped container inventory exceeds its bound or is malformed")
    if len(set(rows)) != len(rows):
        raise RuntimeError("run-scoped container inventory contains duplicate identities")
    return rows


def _volume_names_for_run(run_id: str, *, timeout: int = 45) -> list[str]:
    result = _docker(
        "volume", "ls", "--quiet",
        "--filter", "label=openrepotools.bite4.run=" + run_id,
        timeout=timeout,
    )
    rows = [row.strip() for row in result.stdout.decode("ascii", "replace").splitlines()
            if row.strip()]
    if len(rows) > 8 or any(
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", row) for row in rows
    ):
        raise RuntimeError("run-scoped volume inventory exceeds its bound or is malformed")
    if len(set(rows)) != len(rows):
        raise RuntimeError("run-scoped volume inventory contains duplicate names")
    return rows


class KnownViolation(RuntimeError):
    """A witnessed Bite 4 contract violation that cannot be retried away."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class MountWitnessTransportError(RuntimeError):
    """Sanitized witness failure with bounded private attach stderr retained."""

    def __init__(
        self, code: str, *, stderr: bytes = b"", truncated: bool = False,
        unreaped_process: subprocess.Popen | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.private_stderr = stderr[:MAX_MOUNT_WITNESS_STDERR_BYTES]
        self.private_stderr_truncated = truncated
        self.unreaped_process = unreaped_process


class MountWitnessAttach:
    """Bounded framed transport kept alive until its container is stopped."""

    EXCHANGE_SECONDS = 8.0

    def __init__(self, container_id: str) -> None:
        self.container_id = container_id
        try:
            self.process = subprocess.Popen(
                ("docker", "attach", "--sig-proxy=false", container_id),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=0,
            )
        except BaseException as exc:
            raise MountWitnessTransportError("mount-witness-attach-start-failed") from exc
        if (self.process.stdin is None or self.process.stdout is None
                or self.process.stderr is None):
            reaped = self._terminate_local()
            for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            raise MountWitnessTransportError(
                "mount-witness-attach-pipes-unavailable" if reaped
                else "mount-witness-attach-reap-incomplete",
                unreaped_process=None if reaped else self.process,
            )
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout
        self.stderr = self.process.stderr
        self.stderr_bytes = bytearray()
        self.stderr_truncated = False
        self.next_stage = "before-upload"
        self.stopped = False
        self.initialization_error: str | None = None
        try:
            for stream in (self.stdin, self.stdout, self.stderr):
                os.set_blocking(stream.fileno(), False)
        except BaseException as exc:
            if self._terminate_local():
                for stream in (self.stdin, self.stdout, self.stderr):
                    try:
                        stream.close()
                    except OSError:
                        pass
                raise MountWitnessTransportError(
                    "mount-witness-attach-pipe-setup-failed",
                ) from exc
            # Keep the client handle so the caller can register it before the
            # bounded container-stop/quarantine path reaps it.
            self.initialization_error = "mount-witness-attach-reap-incomplete"

    def require_initialized(self) -> None:
        if self.initialization_error is not None:
            raise self._error(self.initialization_error)

    def _capture_stderr(self, chunk: bytes) -> None:
        remaining = MAX_MOUNT_WITNESS_STDERR_BYTES - len(self.stderr_bytes)
        if len(chunk) > remaining:
            self.stderr_truncated = True
        if remaining > 0:
            self.stderr_bytes.extend(chunk[:remaining])

    def _error(self, code: str) -> MountWitnessTransportError:
        return MountWitnessTransportError(
            code, stderr=bytes(self.stderr_bytes), truncated=self.stderr_truncated,
        )

    def exchange(self, stage: str) -> dict[str, object]:
        if stage != self.next_stage or stage not in {"before-upload", "before-work"}:
            raise self._error("mount-witness-stage-order-invalid")
        nonce = uuid.uuid4().hex
        request = probe._canonical_json({
            "schema": "openrepotools-mount-witness-request/v1",
            "nonce": nonce,
            "stage": stage,
        }) + b"\n"
        if len(request) > MAX_MOUNT_WITNESS_REQUEST_BYTES:
            raise self._error("mount-witness-request-exceeds-bound")
        deadline = time.monotonic() + self.EXCHANGE_SECONDS
        sent = 0
        frame = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(self.stdout, selectors.EVENT_READ, "stdout")
            selector.register(self.stderr, selectors.EVENT_READ, "stderr")
            selector.register(self.stdin, selectors.EVENT_WRITE, "stdin")
            while True:
                if self.process.poll() is not None:
                    raise self._error("mount-witness-attach-exited-early")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise self._error("mount-witness-exchange-timeout")
                events = selector.select(remaining)
                if not events:
                    raise self._error("mount-witness-exchange-timeout")
                for key, _mask in events:
                    if key.data == "stdin":
                        try:
                            sent += os.write(
                                self.stdin.fileno(), request[sent:],
                            )
                        except (BrokenPipeError, OSError) as exc:
                            raise self._error("mount-witness-request-write-failed") from exc
                        if sent >= len(request):
                            selector.unregister(self.stdin)
                    else:
                        try:
                            chunk = os.read(key.fileobj.fileno(), 8192)
                        except BlockingIOError:
                            continue
                        if key.data == "stderr":
                            if chunk:
                                self._capture_stderr(chunk)
                                raise self._error("mount-witness-attach-stderr-observed")
                            raise self._error("mount-witness-attach-stderr-eof")
                        elif not chunk:
                            raise self._error("mount-witness-response-eof")
                        else:
                            frame.extend(chunk)
                            if len(frame) > MAX_MOUNT_WITNESS_RESPONSE_BYTES:
                                raise self._error("mount-witness-response-exceeds-bound")
                            if b"\n" in frame:
                                if frame.count(b"\n") != 1 or not frame.endswith(b"\n"):
                                    raise self._error("mount-witness-frame-boundary-invalid")
                                break
                if frame.endswith(b"\n"):
                    break
        if self.process.poll() is not None:
            raise self._error("mount-witness-attach-exited-after-response")
        try:
            value = _decode_mount_witness_frame(bytes(frame), nonce=nonce, stage=stage)
        except KnownViolation:
            raise
        except Exception as exc:
            code = str(exc) if isinstance(exc, RuntimeError) else "mount-witness-response-unparseable"
            raise self._error(code) from exc
        self.next_stage = "before-work" if stage == "before-upload" else "complete"
        return value

    def check_alive(self) -> None:
        if self.stopped or self.process.poll() is not None:
            raise self._error("mount-witness-wrapper-not-alive")
        for stream, label in ((self.stdout, "stdout"), (self.stderr, "stderr")):
            try:
                readable, _, _ = __import__("select").select([stream], [], [], 0)
                if not readable:
                    continue
                chunk = os.read(stream.fileno(), 8192)
            except BlockingIOError:
                continue
            except OSError as exc:
                raise self._error("mount-witness-pipe-read-failed") from exc
            if not chunk:
                raise self._error("mount-witness-pipe-eof")
            if label == "stderr":
                self._capture_stderr(chunk)
            raise self._error("mount-witness-unsolicited-output")

    def finish_after_stop(self) -> dict[str, object]:
        """Reap only after an external stop event and stopped inspect exist."""
        local_terminate_forced = False
        if not self.stopped:
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                local_terminate_forced = True
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired as exc:
                        raise self._error("mount-witness-attach-reap-incomplete") from exc
            self.stopped = True
        drain_deadline = time.monotonic() + 1.0
        open_streams = {self.stdout: "stdout", self.stderr: "stderr"}
        while open_streams and time.monotonic() < drain_deadline:
            remaining = max(0.0, drain_deadline - time.monotonic())
            readable, _, _ = __import__("select").select(
                list(open_streams), [], [], remaining,
            )
            if not readable:
                break
            for stream in readable:
                label = open_streams[stream]
                try:
                    chunk = os.read(stream.fileno(), 8192)
                except BlockingIOError:
                    continue
                except OSError as exc:
                    raise self._error("mount-witness-pipe-read-failed") from exc
                if not chunk:
                    del open_streams[stream]
                    continue
                if label == "stderr":
                    self._capture_stderr(chunk)
                raise self._error("mount-witness-output-after-container-stop")
        if open_streams:
            raise self._error("mount-witness-attach-output-drain-incomplete")
        for stream in (self.stdin, self.stdout, self.stderr):
            try:
                stream.close()
            except OSError:
                pass
        return {
            "exit_code": self.process.returncode,
            "stderr_sha256": hashlib.sha256(self.stderr_bytes).hexdigest(),
            "stderr_truncated": self.stderr_truncated,
            "local_terminate_forced": local_terminate_forced,
        }

    def _terminate_local(self) -> bool:
        try:
            running = self.process.poll() is None
        except BaseException:
            running = True
        if not running:
            return True
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        except BaseException:
            try:
                self.process.kill()
                self.process.wait(timeout=2)
            except BaseException:
                return False
        try:
            return self.process.poll() is not None
        except BaseException:
            return False


def _reap_local_attach_after_container_stop(process: subprocess.Popen) -> int | None:
    """Reap an attach client with missing pipes only after engine stop evidence."""
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.terminate()
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    if process.poll() is None:
        raise RuntimeError("mount-witness-attach-reap-incomplete")
    return process.returncode


def _strict_json_pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in rows:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _decode_mount_witness_frame(
    frame: bytes, *, nonce: str, stage: str,
) -> dict[str, object]:
    if (not isinstance(frame, bytes) or not 1 < len(frame)
            or len(frame) > MAX_MOUNT_WITNESS_RESPONSE_BYTES
            or not frame.endswith(b"\n") or frame.count(b"\n") != 1):
        raise RuntimeError("mount-witness-frame-boundary-invalid")
    try:
        value = json.loads(
            frame[:-1].decode("ascii"), object_pairs_hook=_strict_json_pairs,
        )
    except Exception as exc:
        raise RuntimeError("mount-witness-response-unparseable") from exc
    if (not isinstance(value, dict)
            or set(value) != {
                "schema", "nonce", "stage", "start_token",
                "mount_namespace", "mountinfo_b64",
            }
            or value.get("schema") != "openrepotools-mount-witness-response/v1"
            or value.get("nonce") != nonce or value.get("stage") != stage):
        raise RuntimeError("mount-witness-response-binding-mismatch")
    token = value.get("start_token")
    namespace = value.get("mount_namespace")
    encoded = value.get("mountinfo_b64")
    if (not isinstance(token, str) or not re.fullmatch(r"[0-9]+", token)
            or not isinstance(namespace, str)
            or not re.fullmatch(r"mnt:\[[0-9]+\]", namespace)
            or not isinstance(encoded, str)
            or len(encoded) > 4 * MAX_MOUNTINFO_BYTES // 3 + 8):
        raise RuntimeError("mount-witness-response-fields-invalid")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise RuntimeError("mount-witness-mountinfo-invalid") from exc
    if not 0 < len(raw) <= MAX_MOUNTINFO_BYTES:
        raise RuntimeError("mount-witness-mountinfo-exceeds-bound")
    value["_private_mountinfo"] = raw
    value["_mountinfo_sha256"] = hashlib.sha256(raw).hexdigest()
    value["_nonce_digest"] = _digest(nonce)
    try:
        parsed = _parse_mountinfo_policy(raw)
    except KnownViolation as exc:
        # Do not classify a mount policy finding as FAIL until the caller has
        # bracketed this exact response with stable inspect and engine events.
        value["_policy_finding_code"] = exc.code
    except Exception as exc:
        raise RuntimeError("mount-witness-mountinfo-invalid") from exc
    else:
        value["_normalized_mounts"] = parsed["mounts"]
    return value


class TwoDomainObserver:
    """Bounded external event sequence with a target creation precondition."""

    MAX_EVENTS = 256
    SAFE_FACTS = {
        "role", "operation", "digest", "source_report_digest",
        "target_code_reached", "exit_code", "oom_killed",
        "source_removal_digest", "manifest_digest", "exact_match",
        "explicit_release_selected", "reason_code", "target_spec_fingerprint",
        "container_id_digest", "remove_intent_digest", "identity_digest",
        "action", "object_type", "engine_time_ns",
    }

    def __init__(self, arm: str) -> None:
        if arm not in {"positive", "negative"}:
            raise ValueError("unknown observer arm")
        self.arm = arm
        self.events: list[dict[str, object]] = []
        self.source_removed = False
        self.copy_verified = False
        self.release_persisted = False
        self.launch_intent_persisted = False
        self.target_created = False
        self.unknown_effect_refusal = False
        self.last_monotonic_ns = 0
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.engine_process: subprocess.Popen[bytes] | None = None
        self.engine_reader: threading.Thread | None = None
        self.volume_process: subprocess.Popen[bytes] | None = None
        self.volume_reader: threading.Thread | None = None
        self.run_id: str | None = None
        self.engine_error: str | None = None
        self.engine_known_violation: str | None = None
        self.engine_ending = False
        self.engine_connected = False
        self.engine_containers: dict[str, dict[str, object]] = {}
        self.engine_volumes: dict[str, dict[str, object]] = {}
        self.volume_create_attesting: set[str] = set()
        self.volume_removal_intents: dict[str, str] = {}
        self.harness_container_roles: dict[str, str] = {}
        self.harness_volume_roles: dict[str, str] = {}
        self.expected_creates: dict[tuple[str, str], tuple[str, int]] = {}
        self.expected_container_volumes: dict[str, tuple[str, ...]] = {}
        self.engine_container_volumes: dict[str, tuple[str, ...]] = {}
        self.planned_volume_mount_counts: dict[str, int] = {}
        self.engine_container_writable_mounts: dict[str, int] = {}
        self.mount_witness_attestations: dict[str, dict[str, object]] = {}
        self._mount_witness_capture_facts: dict[str, dict[str, Mapping[str, object]]] = {}
        self.mount_witness_ledgers: dict[str, probe.TwoDomainIntentLedger] = {}
        self.pre_release_history_verified = False
        self.pre_release_inventory_ready = False
        self.pre_release_inventory_digest: str | None = None
        self.custody_result_persisted = False
        self.source_engine_destroyed = False
        self.target_create_pending = False
        self.target_expected = False
        self.target_start_seen = False
        self.negative_refusal_expected = False
        self.private_values: list[str] = []

    def start_engine_stream(self, run_id: str) -> None:
        if self.engine_process is not None or self.volume_process is not None:
            raise RuntimeError("two-domain engine observer already started")
        self.run_id = run_id
        since = str(int(time.time()))
        try:
            self.engine_process = subprocess.Popen(
                (
                    "docker", "events", "--since", since,
                    "--filter", "type=container",
                    "--filter", "label=openrepotools.bite4.run=" + run_id,
                    "--format", "{{json .}}",
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
            self.volume_process = subprocess.Popen(
                (
                    "docker", "events", "--since", since,
                    "--filter", "type=volume",
                    "--format", "{{json .}}",
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
        except BaseException:
            for process in (self.engine_process, self.volume_process):
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            raise
        self.engine_reader = threading.Thread(
            target=self._read_engine_events,
            args=(run_id, "container"), daemon=True,
        )
        self.volume_reader = threading.Thread(
            target=self._read_engine_events,
            args=(run_id, "volume"), daemon=True,
        )
        try:
            self.engine_reader.start()
            self.volume_reader.start()
        except BaseException:
            _stop_engine_observer(self)
            raise

    def _read_engine_events(self, run_id: str, stream_kind: str = "container") -> None:
        process = self.volume_process if stream_kind == "volume" else self.engine_process
        assert process is not None and process.stdout is not None
        try:
            while True:
                line = process.stdout.readline(65537)
                if not line:
                    with self.condition:
                        if not self.engine_ending:
                            self.engine_error = "engine-event-stream-ended"
                        self.condition.notify_all()
                    return
                if len(line) > 65536:
                    raise RuntimeError("engine-event-line-exceeds-bound")
                try:
                    event = json.loads(line.decode("utf-8"))
                    if stream_kind == "volume":
                        row = self._decode_volume_engine_event(event, run_id)
                        self._accept_volume_engine_row(row)
                    else:
                        row = self._decode_engine_event(event, run_id)
                        self._accept_engine_row(row)
                except KnownViolation:
                    raise
                except Exception as exc:
                    raise RuntimeError("engine-event-unparseable") from exc
        except Exception as exc:
            self._record_engine_failure(exc)

    def _record_engine_failure(self, exc: BaseException) -> None:
        with self.condition:
            if isinstance(exc, KnownViolation):
                self.engine_known_violation = exc.code
                self.engine_error = exc.code
            elif self.engine_error is None:
                self.engine_error = (
                    str(exc) if isinstance(exc, RuntimeError)
                    else "engine-event-observer-failed"
                )
            self.condition.notify_all()

    def _accept_engine_row(self, row: Mapping[str, object]) -> None:
        if row.get("type") == "volume":
            self._accept_volume_engine_row(row)
            return
        event_type = row["type"]
        action = row["action"]
        actor_id = row["id"]
        role = row["role"]
        event_time = row["time_ns"]
        if not all(isinstance(value, str) for value in (event_type, action, actor_id)):
            raise RuntimeError("engine-event-identity-unavailable")
        with self.condition:
            self.engine_connected = True
            self._validate_engine_event(row)
            if event_type == "container":
                state = self.engine_containers.setdefault(actor_id, {
                    "role": role, "create": 0, "start": 0,
                    "die": 0, "destroy": 0,
                })
                if state.get("role") != role:
                    raise KnownViolation("engine-container-role-changed")
                if action in state:
                    state[action] = int(state[action]) + 1
                if role == "target" and action == "start":
                    self.target_start_seen = True
                if role == "source" and action == "destroy":
                    self.source_engine_destroyed = True
            self._append_locked(
                "docker-engine-event", actor_id,
                {
                    "role": role if isinstance(role, str) else "unknown",
                    "action": action,
                    "object_type": event_type,
                    "engine_time_ns": event_time,
                },
            )
            self.condition.notify_all()

    @staticmethod
    def _decode_engine_event(event: object, run_id: str) -> dict[str, object]:
        """Parse the shape emitted by Docker `events --format '{{json .}}'`."""
        if not isinstance(event, Mapping):
            raise RuntimeError("engine-event-identity-unavailable")
        event_type = event.get("Type")
        action = event.get("Action") or event.get("Status")
        actor = event.get("Actor")
        actor = actor if isinstance(actor, Mapping) else {}
        actor_id = event.get("id") or actor.get("ID")
        attributes = actor.get("Attributes")
        attributes = attributes if isinstance(attributes, Mapping) else {}
        actor_name = attributes.get("name")
        labels: dict[str, object] = {}
        for key, value in attributes.items():
            text_key = str(key)
            if text_key.startswith("label."):
                labels[text_key[len("label."):]] = value
            elif text_key.startswith("openrepotools.bite4."):
                labels[text_key] = value
        if (event_type != "container"
                or labels.get("openrepotools.bite4.run") != run_id
                or not isinstance(actor_id, str)
                or not isinstance(event_type, str)
                or not isinstance(action, str)):
            raise RuntimeError("engine-event-identity-unavailable")
        event_time = event.get("timeNano")
        return {
            "type": event_type,
            "action": action,
            "id": actor_id,
            "role": labels.get("openrepotools.bite4.role"),
            "name": actor_name if isinstance(actor_name, str) else (
                actor_id if event_type == "volume" else None
            ),
            "time_ns": event_time if type(event_time) is int else None,
        }

    @staticmethod
    def _decode_volume_engine_event(
        event: object, run_id: str | None = None,
    ) -> dict[str, object]:
        """Parse a volume event without assuming labels are in Actor.Attributes."""
        if not isinstance(event, Mapping):
            raise RuntimeError("volume-event-identity-unavailable")
        event_type = event.get("Type")
        action = event.get("Action") or event.get("Status")
        actor = event.get("Actor")
        if not isinstance(actor, Mapping):
            raise RuntimeError("volume-event-identity-unavailable")
        attributes = actor.get("Attributes")
        attributes = attributes if isinstance(attributes, Mapping) else {}
        actor_id = actor.get("ID")
        top_level_id = event.get("id")
        actor_name = attributes.get("name")
        valid_identity = (
            isinstance(actor_id, str) and bool(actor_id)
            and actor_id == actor_id.strip() and len(actor_id) <= 256
            and all(ord(character) >= 33 and ord(character) != 127 for character in actor_id)
        )
        valid_top_level_identity = (
            "id" not in event or (
                isinstance(top_level_id, str) and bool(top_level_id)
                and top_level_id == top_level_id.strip()
                and len(top_level_id) <= 256
                and all(ord(character) >= 33 and ord(character) != 127
                        for character in top_level_id)
                and top_level_id == actor_id
            )
        )
        if (event_type != "volume" or not isinstance(action, str)
                or not valid_identity or not valid_top_level_identity
                or (actor_name is not None and not isinstance(actor_name, str))):
            raise RuntimeError("volume-event-identity-unavailable")
        run_labels: list[object] = []
        role_labels: list[object] = []
        if "openrepotools.bite4.run" in attributes:
            run_labels.append(attributes.get("openrepotools.bite4.run"))
        if "openrepotools.bite4.role" in attributes:
            role_labels.append(attributes.get("openrepotools.bite4.role"))
        for key, value in attributes.items():
            text_key = str(key)
            if text_key.startswith("label.openrepotools.bite4."):
                suffix = text_key[len("label."):]
                if suffix == "openrepotools.bite4.run":
                    run_labels.append(value)
                elif suffix == "openrepotools.bite4.role":
                    role_labels.append(value)
        run_conflict = bool(run_labels and any(value != run_labels[0] for value in run_labels[1:]))
        role_conflict = bool(role_labels and any(value != role_labels[0] for value in role_labels[1:]))
        return {
            "type": "volume",
            "action": action,
            "id": actor_id,
            "name": actor_name,
            "run_label": None if run_conflict else (run_labels[0] if run_labels else None),
            "role_label": None if role_conflict else (role_labels[0] if role_labels else None),
            "label_conflict": run_conflict or role_conflict,
            "run_label_matches_run": isinstance(run_id, str) and run_id in run_labels,
            "time_ns": event.get("timeNano") if type(event.get("timeNano")) is int else None,
        }

    def _accept_volume_engine_row(self, row: Mapping[str, object]) -> None:
        """Accept only preregistered volume identities and attest before use."""
        if row.get("type") != "volume":
            raise RuntimeError("volume-event-type-mismatch")
        identity = row.get("id")
        action = row.get("action")
        name = row.get("name")
        if not isinstance(identity, str) or not isinstance(action, str):
            raise RuntimeError("volume-event-identity-unavailable")

        with self.condition:
            pending = self.expected_creates.get(("volume", identity))
            state = self.engine_volumes.get(identity)
            matched = pending is not None or state is not None
            run_label = row.get("run_label")
            role_label = row.get("role_label")
            label_conflict = row.get("label_conflict") is True
            if isinstance(name, str) and name != identity:
                if matched or ("volume", name) in self.expected_creates or name in self.engine_volumes:
                    raise KnownViolation("volume-event-name-id-conflict")
                if row.get("run_label_matches_run") is True:
                    raise KnownViolation("unplanned-run-labelled-volume-event")
                return
            if label_conflict:
                if matched or row.get("run_label_matches_run") is True:
                    raise KnownViolation("volume-event-conflicting-label-attributes")
                return
            if run_label is not None and run_label != self.run_id:
                if matched:
                    raise KnownViolation("volume-event-run-label-conflict")
                return
            if not matched:
                if run_label == self.run_id:
                    raise KnownViolation("unplanned-run-labelled-volume-event")
                # The unfiltered stream includes unrelated engine volumes. Do
                # not retain their IDs, names, attributes, or event counts.
                return

            if action == "create":
                if pending is None or state is not None or identity in self.volume_create_attesting:
                    raise KnownViolation("volume-create-duplicate-or-name-reuse")
                role = pending[0]
                if role_label is not None and role_label != role:
                    raise KnownViolation("volume-event-role-label-conflict")
                self.volume_create_attesting.add(identity)
            else:
                if state is None:
                    raise KnownViolation("volume-lifecycle-before-attested-create")
                role = state.get("role")
                if not isinstance(role, str):
                    raise KnownViolation("volume-attested-role-missing")
                if role_label is not None and role_label != role:
                    raise KnownViolation("volume-event-role-label-conflict")
                if int(state.get("destroy", 0)):
                    raise KnownViolation("volume-event-after-destroy")
                if action == "destroy":
                    if not self.custody_result_persisted:
                        raise KnownViolation("volume-destroy-before-custody-result")
                    if identity not in self.volume_removal_intents:
                        raise KnownViolation("volume-destroy-without-removal-intent")
                    if int(state.get("mount", 0)) != int(state.get("unmount", 0)):
                        raise KnownViolation("volume-destroy-while-mounted")
                elif action == "unmount":
                    if int(state.get("unmount", 0)) >= int(state.get("mount", 0)):
                        raise KnownViolation("volume-unmount-without-mount")
                elif action == "mount":
                    if int(state.get("mount", 0)) >= self.planned_volume_mount_counts.get(
                        identity, 0,
                    ):
                        raise KnownViolation("unplanned-volume-mount")
                else:
                    raise KnownViolation("unexpected-attested-volume-event")

        if action == "create":
            try:
                assert isinstance(self.run_id, str)
                try:
                    inspected = _validate_new_volume(
                        identity, self.run_id, role, timeout=8,
                    )
                except RuntimeError as exc:
                    if str(exc) == "run fixture volume is not a plain engine-managed local volume":
                        raise KnownViolation("volume-event-attestation-mismatch") from exc
                    raise
                expected_labels = {
                    "openrepotools.bite4.run": self.run_id,
                    "openrepotools.bite4.role": role,
                }
                attestation_digest = _digest({
                    "schema": "openrepotools-bite4-volume-attestation/v1",
                    "name": identity,
                    "run_id": self.run_id,
                    "role": role,
                    "driver": inspected.get("Driver"),
                    "scope": inspected.get("Scope"),
                    "options": inspected.get("Options") or {},
                    "labels": expected_labels,
                })
            except BaseException:
                with self.condition:
                    self.volume_create_attesting.discard(identity)
                    self.condition.notify_all()
                raise
            with self.condition:
                current = self.expected_creates.get(("volume", identity))
                if current is None or current[0] != role or identity in self.engine_volumes:
                    self.volume_create_attesting.discard(identity)
                    raise KnownViolation("volume-create-intent-changed-during-attestation")
                self.expected_creates.pop(("volume", identity))
                self.volume_create_attesting.discard(identity)
                self.engine_volumes[identity] = {
                    "role": role, "create": 1, "mount": 0, "unmount": 0,
                    "destroy": 0, "attestation_digest": attestation_digest,
                    "absence_confirmed": False,
                }
                self.engine_connected = True
                self._append_locked("docker-engine-event", identity, {
                    "role": role, "action": action, "object_type": "volume",
                    "engine_time_ns": row.get("time_ns"),
                    "digest": attestation_digest,
                })
                self.condition.notify_all()
            return

        if action == "destroy":
            # The independent inspect runs after Docker's destroy event. The
            # removal intent is durable and was bound to this attested name.
            if not _volume_absent(identity, timeout=8):
                raise RuntimeError("volume-destroy-absence-not-confirmed")
            with self.condition:
                state = self.engine_volumes.get(identity)
                if state is None or int(state.get("destroy", 0)):
                    raise KnownViolation("volume-destroy-duplicate-or-state-changed")
                state["destroy"] = 1
                state["absence_confirmed"] = True
                self.engine_connected = True
                self._append_locked("docker-engine-event", identity, {
                    "role": role, "action": action, "object_type": "volume",
                    "engine_time_ns": row.get("time_ns"),
                    "digest": state.get("attestation_digest"),
                    "identity_digest": self.volume_removal_intents[identity],
                    "exact_match": True,
                })
                self.condition.notify_all()
            return

        with self.condition:
            state = self.engine_volumes.get(identity)
            if state is None:
                raise KnownViolation("volume-state-lost-during-event")
            state[action] = int(state.get(action, 0)) + 1
            self.engine_connected = True
            self._append_locked("docker-engine-event", identity, {
                "role": role, "action": action, "object_type": "volume",
                "engine_time_ns": row.get("time_ns"),
                "digest": state.get("attestation_digest"),
            })
            self.condition.notify_all()

    def expect_object_creation(
        self, *, kind: str, name: str, role: str, writable_mount_count: int = 0,
        volume_names: tuple[str, ...] = (),
    ) -> None:
        if (kind not in {"container", "volume"} or not name or not role
                or type(writable_mount_count) is not int or writable_mount_count < 0
                or not isinstance(volume_names, tuple)
                or any(not isinstance(volume, str) or not volume for volume in volume_names)
                or len(set(volume_names)) != len(volume_names)
                or (kind == "volume" and volume_names)):
            raise ValueError("invalid expected run-scoped object")
        key = (kind, name)
        with self.condition:
            if (key in self.expected_creates
                    or (kind == "volume" and (
                        name in self.engine_volumes
                        or name in self.harness_volume_roles
                        or name in self.volume_create_attesting
                    ))):
                if kind == "volume":
                    raise KnownViolation("volume-name-reuse")
                raise KnownViolation("duplicate-object-create-intent")
            if kind == "container":
                if any(
                    volume not in self.engine_volumes
                    or not isinstance(self.engine_volumes[volume].get("attestation_digest"), str)
                    or not re.fullmatch(
                        r"[0-9a-f]{64}",
                        str(self.engine_volumes[volume].get("attestation_digest")),
                    )
                    or int(self.engine_volumes[volume].get("destroy", 0)) != 0
                    for volume in volume_names
                ):
                    raise KnownViolation("container-volume-mount-not-attested")
                self.expected_container_volumes[name] = volume_names
                for volume in volume_names:
                    self.planned_volume_mount_counts[volume] = (
                        self.planned_volume_mount_counts.get(volume, 0) + 1
                    )
            self.expected_creates[key] = (role, writable_mount_count)

    def _validate_engine_event(self, row: Mapping[str, object]) -> None:
        kind = row.get("type")
        action = row.get("action")
        role = row.get("role")
        identity = row.get("id")
        assert isinstance(identity, str)
        if kind == "container":
            if role not in {"source", "target", "copy", "verify", "custodian"}:
                raise KnownViolation("engine-container-role-invalid")
            state = self.engine_containers.get(identity)
            if action == "create":
                expected_name = row.get("name")
                if state is not None and int(state.get("create", 0)):
                    raise KnownViolation("duplicate-container-create")
                if role == "source" and any(
                    item.get("role") == "source" and item.get("create")
                    for item in self.engine_containers.values()
                ):
                    raise KnownViolation("duplicate-source-container-created")
                if role == "target":
                    if (not self.can_create_target or not self.target_create_pending
                            or not self.source_engine_destroyed):
                        raise KnownViolation("target-engine-create-before-release")
                    if any(
                        item.get("role") == "target" and item.get("create")
                        for item in self.engine_containers.values()
                    ):
                        raise KnownViolation("duplicate-target-container-created")
                if not isinstance(expected_name, str):
                    raise RuntimeError("engine-container-name-unavailable")
                expected = self.expected_creates.pop(("container", expected_name), None)
                if expected is None or expected[0] != role:
                    raise KnownViolation("unplanned-run-labelled-container-create")
                volume_plan = self.expected_container_volumes.pop(expected_name, None)
                if volume_plan is None:
                    raise KnownViolation("container-volume-mount-plan-missing")
                self.engine_container_volumes[identity] = volume_plan
                self.engine_container_writable_mounts[identity] = expected[1]
            elif action == "start":
                if state is None or int(state.get("create", 0)) != 1:
                    raise KnownViolation("container-start-without-authorized-create")
                if state is not None and int(state.get("start", 0)):
                    raise KnownViolation("duplicate-container-start")
                if role == "source" and self.source_engine_destroyed:
                    raise KnownViolation("source-container-restarted-after-removal")
                if role == "target" and not self.target_created:
                    raise KnownViolation("target-container-start-before-create")
                if role == "target" and self.target_start_seen:
                    raise KnownViolation("duplicate-target-container-start")
            elif action in {"die", "destroy"}:
                if state is not None and int(state.get(action, 0)):
                    raise KnownViolation("duplicate-container-" + action)
            elif role == "source" and action in {"restart", "update"}:
                raise KnownViolation("source-container-recreation-observed")
    def _append_locked(
        self, event: str, identity: object | None,
        facts: Mapping[str, object] | None,
    ) -> None:
        # Called with self.condition held by the engine reader.
        if len(self.events) >= self.MAX_EVENTS:
            raise RuntimeError("two-domain observer event limit exceeded")
        now = time.monotonic_ns()
        if now < self.last_monotonic_ns:
            raise RuntimeError("two-domain observer monotonic sequence regressed")
        self.last_monotonic_ns = now
        safe_facts: dict[str, object] = {}
        for key, value in (facts or {}).items():
            if key not in self.SAFE_FACTS:
                continue
            if key.endswith("digest") or key.endswith("_digest") or key == "digest":
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
                    safe_facts[key] = value
                continue
            if type(value) in {bool, int} or value is None:
                safe_facts[key] = value
            elif isinstance(value, str) and len(value) <= 80 and not re.search(
                r"[0-9a-f]{8}-[0-9a-f-]{27,}|[0-9a-f]{32,}", value
            ):
                safe_facts[key] = value
        self.events.append({
            "sequence": len(self.events) + 1,
            "monotonic_ns": now,
            "event": event,
            "entity_digest": _digest(identity) if identity is not None else None,
            "facts": safe_facts,
            "observation_source": "external-docker-events" if event == "docker-engine-event"
            else "external-harness",
        })
        if isinstance(identity, str) and len(identity) >= 16:
            self.private_values.append(identity)

    def wait_engine_event(
        self, *, kind: str, action: str, identity: str | None = None,
        role: str | None = None, timeout: float = 10.0,
    ) -> None:
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                if self.engine_error:
                    if self.engine_known_violation:
                        raise KnownViolation(self.engine_known_violation)
                    raise RuntimeError("external Docker event observer is incomplete")
                collection = self.engine_containers if kind == "container" else self.engine_volumes
                for found_id, state in collection.items():
                    if identity is not None and found_id != identity:
                        continue
                    if role is not None and state.get("role") != role:
                        continue
                    if int(state.get(action, 0)) >= 1:
                        return
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("external Docker event was not observed")
                self.condition.wait(remaining)

    def container_start_observed(self, identity: str) -> bool:
        """Read start evidence for an exact container after its create event."""

        with self.condition:
            if self.engine_known_violation:
                raise KnownViolation(self.engine_known_violation)
            if self.engine_error:
                raise RuntimeError("external Docker event observer is incomplete")
            state = self.engine_containers.get(identity)
            if not isinstance(state, Mapping) or int(state.get("create", 0)) != 1:
                raise RuntimeError("external Docker container create event is missing")
            return int(state.get("start", 0)) > 0

    def mount_witness_engine_binding(
        self, identity: str, role: str,
    ) -> dict[str, object]:
        """Bind a mount response to one observed, unique container start."""
        self.ensure_engine_healthy()
        with self.condition:
            state = self.engine_containers.get(identity)
            if (not isinstance(state, Mapping) or state.get("role") != role
                    or any(int(state.get(key, 0)) != expected for key, expected in (
                        ("create", 1), ("start", 1), ("die", 0), ("destroy", 0),
                    ))):
                raise RuntimeError("mount witness lacks exact live create/start events")
            binding = {
                "run_id": self.run_id,
                "container_id": identity,
                "role": role,
                "create_count": int(state["create"]),
                "start_count": int(state["start"]),
                "die_count": int(state["die"]),
                "destroy_count": int(state["destroy"]),
            }
            binding["event_binding_digest"] = _digest(binding)
            return binding

    def record_mount_witness(
        self, identity: str, role: str, stage: str, digest_value: str,
    ) -> None:
        if (stage not in {"before-upload", "before-work"}
                or not re.fullmatch(r"[0-9a-f]{64}", digest_value)):
            raise RuntimeError("mount witness observer record is malformed")
        self.mount_witness_engine_binding(identity, role)
        with self.condition:
            row = self.mount_witness_attestations.setdefault(identity, {
                "role": role, "capture_digests": [],
            })
            expected_stage = "before-upload" if not row["capture_digests"] else "before-work"
            if (row.get("role") != role or stage != expected_stage
                    or len(row["capture_digests"]) >= 2):
                raise KnownViolation("duplicate-or-misordered-mount-witness")
            row["capture_digests"].append(digest_value)
            self._append_locked(
                "mount-witness-attested", identity,
                {"role": role, "operation": stage, "digest": digest_value},
            )
            self.condition.notify_all()

    def require_mount_witness_complete(self, identity: str) -> dict[str, object]:
        self.ensure_engine_healthy()
        with self.condition:
            row = self.mount_witness_attestations.get(identity)
            digests = row.get("capture_digests") if isinstance(row, Mapping) else None
            if (not isinstance(row, Mapping) or not isinstance(digests, list)
                    or len(digests) != 2
                    or any(not isinstance(value, str)
                           or not re.fullmatch(r"[0-9a-f]{64}", value)
                           for value in digests)
                    or len(set(digests)) != 2):
                raise RuntimeError("container has no complete two-stage mount witness")
            return {
                "role": row.get("role"),
                "capture_digests": list(digests),
                "witness_set_digest": _digest({
                    "container_id_digest": _digest(identity),
                    "role": row.get("role"),
                    "capture_digests": list(digests),
                }),
            }

    def ensure_engine_healthy(self) -> None:
        with self.condition:
            if self.engine_known_violation:
                raise KnownViolation(self.engine_known_violation)
            if (self.engine_process is None or self.volume_process is None
                    or self.engine_error):
                raise RuntimeError("external Docker event observer is incomplete")
            if not self.engine_ending and any(
                process.poll() is not None
                for process in (self.engine_process, self.volume_process)
            ):
                raise RuntimeError("external Docker event observer exited early")

    def _wait_for_planned_volume_lifecycle(self, *, timeout: float = 10.0) -> None:
        """Wait briefly for cross-stream mount events before inventory snapshot."""

        if (type(timeout) not in {int, float} or timeout <= 0
                or timeout > 30 or timeout != timeout):
            raise ValueError("volume lifecycle wait must be between 0 and 30 seconds")
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                # The container and unfiltered volume streams are independent;
                # both must still be live on every wake before the snapshot.
                self.ensure_engine_healthy()
                if not self.planned_volume_mount_counts:
                    raise RuntimeError("planned volume mount inventory is unavailable")
                complete = True
                for identity, expected in self.planned_volume_mount_counts.items():
                    if expected < 1:
                        raise RuntimeError("planned volume mount count is invalid")
                    row = self.engine_volumes.get(identity)
                    if row is None:
                        complete = False
                        continue
                    mounts = int(row.get("mount", 0))
                    unmounts = int(row.get("unmount", 0))
                    if mounts > expected or unmounts > expected:
                        raise KnownViolation("pre-release-unexpected-volume-mount-event")
                    if mounts != expected or unmounts != expected:
                        complete = False
                if complete:
                    self.ensure_engine_healthy()
                    return
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError("pre-release-volume-mount-events-are-incomplete")
                self.condition.wait(remaining)

    def authorize_target_create(self) -> None:
        self.require_target_launch()
        if self.target_create_pending:
            raise KnownViolation("duplicate-target-create-intent")
        self.target_create_pending = True
        self.target_expected = True

    def require_explicit_release(self, *, inventory_digest: str) -> None:
        self.ensure_engine_healthy()
        if not (
            self.arm == "positive" and self.source_removed and self.copy_verified
            and self.pre_release_history_verified and self.pre_release_inventory_ready
            and not self.target_created
        ):
            raise KnownViolation("release-before-pre-release-custody")
        if inventory_digest != self.pre_release_inventory_digest:
            raise KnownViolation("release-pre-release-inventory-binding-mismatch")
        with self.condition:
            if self.expected_creates:
                raise RuntimeError("release has unresolved engine object intents")
            if any(
                int(row.get("create", 0)) != 1 or int(row.get("destroy", 0)) != 0
                for row in self.engine_volumes.values()
            ):
                raise KnownViolation("pre-release-volume-exclusion-lost")

    def verify_pre_release_inventory(
        self, *, run_id: str, source_volume: str, target_volume: str,
        mount_wait_timeout: float = 10.0,
    ) -> dict[str, object]:
        """Reconcile observer and live-engine inventories before durable release."""

        self._wait_for_planned_volume_lifecycle(timeout=mount_wait_timeout)
        self.ensure_engine_healthy()
        with self.condition:
            if not (self.source_engine_destroyed and self.source_removed and self.copy_verified):
                raise KnownViolation("pre-release-source-exclusion-or-copy-missing")
            if self.expected_creates or self.expected_container_volumes:
                raise RuntimeError("expected run-scoped object creation is unresolved")
            if self.target_created or any(
                row.get("role") == "target" for row in self.engine_containers.values()
            ):
                raise KnownViolation("target-object-exists-before-release")
            if set(self.engine_containers) != set(self.harness_container_roles):
                raise RuntimeError("pre-release container event inventory is incomplete")
            if any(
                self.engine_containers[identity].get("role") != role
                for identity, role in self.harness_container_roles.items()
            ):
                raise KnownViolation("pre-release-container-role-mismatch")
            for row in self.engine_containers.values():
                counts = [int(row.get(key, 0)) for key in ("create", "start", "die", "destroy")]
                if any(count > 1 for count in counts):
                    raise KnownViolation("pre-release-duplicate-container-lifecycle")
                if any(count != 1 for count in counts):
                    raise RuntimeError("pre-release-container-lifecycle-evidence-incomplete")
            for identity, row in self.engine_containers.items():
                witness = self.require_mount_witness_complete(identity)
                if witness.get("role") != row.get("role"):
                    raise KnownViolation("pre-release-mount-witness-role-mismatch")
            if any(
                self.engine_container_writable_mounts.get(identity, 0) > 0
                and int(self.engine_containers[identity].get("destroy", 0)) != 1
                for identity in self.engine_containers
            ):
                raise KnownViolation("writable-helper-remains-before-release")
            for identity, row in self.engine_containers.items():
                role = row.get("role")
                expected_writable_mounts = 1 if role in {"source", "copy"} else 0
                if self.engine_container_writable_mounts.get(identity, 0) != expected_writable_mounts:
                    raise KnownViolation("pre-release-writable-mount-policy-mismatch")
                expected_volume_names = {
                    "source": {source_volume},
                    "copy": {source_volume, target_volume},
                    "verify": {source_volume, target_volume},
                    "custodian": {source_volume, target_volume},
                }.get(str(role))
                if (expected_volume_names is None
                        or set(self.engine_container_volumes.get(identity, ()))
                        != expected_volume_names):
                    raise KnownViolation("pre-release-container-volume-mount-mismatch")
            expected_volumes = {source_volume: "source-state", target_volume: "target-state"}
            if (set(self.engine_volumes) != set(expected_volumes)
                    or set(self.harness_volume_roles) != set(expected_volumes)):
                raise RuntimeError("pre-release volume event inventory is incomplete")
            if any(
                self.engine_volumes[identity].get("role") != role
                or int(self.engine_volumes[identity].get("create", 0)) != 1
                or int(self.engine_volumes[identity].get("destroy", 0)) != 0
                or self.harness_volume_roles.get(identity) != role
                for identity, role in expected_volumes.items()
            ):
                raise KnownViolation("pre-release-volume-inventory-mismatch")
            for identity, row in self.engine_volumes.items():
                attestation = row.get("attestation_digest")
                if not isinstance(attestation, str) or not re.fullmatch(
                    r"[0-9a-f]{64}", attestation,
                ):
                    raise RuntimeError("pre-release-volume-attestation-is-incomplete")
                expected_mounts = self.planned_volume_mount_counts.get(identity, 0)
                mounts = int(row.get("mount", 0))
                unmounts = int(row.get("unmount", 0))
                if mounts > expected_mounts or unmounts > expected_mounts:
                    raise KnownViolation("pre-release-unexpected-volume-mount-event")
                if expected_mounts < 1 or mounts != expected_mounts or unmounts != expected_mounts:
                    raise RuntimeError("pre-release-volume-mount-events-are-incomplete")
                if mounts != unmounts:
                    raise KnownViolation("pre-release-volume-remains-mounted")
        # Engine queries catch a run-labelled object even if the event reader
        # has not yet delivered its create event. Event expectations continue
        # to reject any later unexpected create immediately.
        container_ids = _container_ids_for_run(run_id)
        if container_ids:
            raise KnownViolation("pre-release-potential-writer-remains")
        volume_names = _volume_names_for_run(run_id)
        if set(volume_names) != {source_volume, target_volume}:
            raise KnownViolation("pre-release-run-volume-inventory-mismatch")
        with self.condition:
            self.pre_release_inventory_ready = True
            container_roles: dict[str, int] = {}
            for row in self.engine_containers.values():
                role = row.get("role")
                if isinstance(role, str):
                    container_roles[role] = container_roles.get(role, 0) + 1
            volume_roles: dict[str, int] = {}
            volume_lifecycle: dict[str, dict[str, object]] = {}
            container_mount_witnesses: list[dict[str, object]] = []
            for identity, row in self.engine_containers.items():
                witness = self.require_mount_witness_complete(identity)
                container_mount_witnesses.append({
                    "role": row.get("role"),
                    "container_identity_digest": _digest(identity),
                    "witness_set_digest": witness["witness_set_digest"],
                    "capture_count": 2,
                })
            container_mount_witnesses.sort(
                key=lambda item: (str(item.get("role")),
                                  str(item.get("container_identity_digest")))
            )
            for identity, row in self.engine_volumes.items():
                role = row.get("role")
                if isinstance(role, str):
                    volume_roles[role] = volume_roles.get(role, 0) + 1
                    volume_lifecycle[role] = {
                        "attestation_digest": row.get("attestation_digest"),
                        "expected_mount_count": self.planned_volume_mount_counts.get(identity, 0),
                        "mount_count": int(row.get("mount", 0)),
                        "unmount_count": int(row.get("unmount", 0)),
                    }
            summary: dict[str, object] = {
                "schema": "openrepotools-bite4-pre-release-inventory/v1",
                "source_destroyed_observed": self.source_engine_destroyed,
                "target_absent": not self.target_created,
                "container_count": len(self.engine_containers),
                "container_roles": dict(sorted(container_roles.items())),
                "container_identity_digests": sorted(
                    _digest(identity) for identity in self.engine_containers
                ),
                "container_mount_witnesses": container_mount_witnesses,
                "container_mount_witnesses_digest": _digest(container_mount_witnesses),
                "all_container_lifecycles_complete": True,
                "writable_mount_count": sum(
                    self.engine_container_writable_mounts.values()
                ),
                "all_writable_mounts_detached": True,
                "live_run_container_count": len(container_ids),
                "live_writable_helper_mount_count": 0,
                "volume_count": len(self.engine_volumes),
                "volume_roles": dict(sorted(volume_roles.items())),
                "volume_identity_digests": sorted(
                    _digest(identity) for identity in self.engine_volumes
                ),
                "volume_attestation_digests": sorted(
                    str(row["attestation_digest"])
                    for row in self.engine_volumes.values()
                ),
                "volume_lifecycle": dict(sorted(volume_lifecycle.items())),
                "pending_create_intent_count": len(self.expected_creates),
            }
            inventory_digest = _digest(summary)
            self.pre_release_inventory_digest = inventory_digest
            summary["inventory_digest"] = inventory_digest
            return summary

    def finish_engine_stream(self) -> None:
        processes = (self.engine_process, self.volume_process)
        if any(process is None for process in processes):
            raise RuntimeError("external Docker event observer was not started")
        with self.condition:
            self.engine_ending = True
        for process in processes:
            assert process is not None
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired as exc:
                process.kill()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    raise RuntimeError("external Docker event observer did not stop") from exc
        for reader in (self.engine_reader, self.volume_reader):
            if reader is not None:
                reader.join(timeout=5)
                if reader.is_alive():
                    raise RuntimeError("external Docker event reader did not stop")
        self.ensure_engine_healthy()

    def verify_lifecycle(self, *, volumes_removed: bool) -> None:
        with self.condition:
            if self.engine_process is None or self.volume_process is None:
                raise RuntimeError("both external Docker event streams are required")
            if self.engine_error:
                if self.engine_known_violation:
                    raise KnownViolation(self.engine_known_violation)
                raise RuntimeError("external Docker event observer reported a gap")
            if self.expected_creates or self.expected_container_volumes:
                raise RuntimeError("external engine object intents remain unresolved")
            if set(self.engine_container_volumes) != set(self.engine_containers):
                raise RuntimeError("external container volume plans are incomplete")
            source_creates = 0
            target_creates = 0
            for identity, row in self.engine_containers.items():
                if (int(row.get("create", 0)) != 1 or int(row.get("start", 0)) != 1
                        or int(row.get("die", 0)) != 1 or int(row.get("destroy", 0)) != 1):
                    raise RuntimeError("external Docker container lifecycle is incomplete")
                witness = self.require_mount_witness_complete(identity)
                if witness.get("role") != row.get("role"):
                    raise KnownViolation("container-mount-witness-role-mismatch")
                source_creates += int(row.get("role") == "source")
                target_creates += int(row.get("role") == "target")
            if source_creates != 1 or target_creates != (1 if self.target_expected else 0):
                raise RuntimeError("external Docker source/target role inventory is incomplete")
            if set(self.engine_containers) - set(self.harness_container_roles):
                raise KnownViolation("unexpected-run-labelled-container-observed")
            if set(self.harness_container_roles) - set(self.engine_containers):
                raise RuntimeError("external Docker container creation event is missing")
            if any(
                self.engine_containers[identity].get("role") != role
                for identity, role in self.harness_container_roles.items()
            ):
                raise KnownViolation("container-role-differs-from-harness-intent")
            role_names = {
                role: identity for identity, role in self.harness_volume_roles.items()
            }
            source_volume = role_names.get("source-state")
            target_volume = role_names.get("target-state")
            expected_container_volumes = {
                "source": {source_volume},
                "target": {target_volume},
                "copy": {source_volume, target_volume},
                "verify": {source_volume, target_volume},
                "custodian": {source_volume, target_volume},
            }
            for identity, row in self.engine_containers.items():
                role = row.get("role")
                expected_mounts = expected_container_volumes.get(str(role))
                if (expected_mounts is None
                        or set(self.engine_container_volumes[identity]) != expected_mounts):
                    raise KnownViolation("container-volume-mount-plan-mismatch")
            if not self.source_engine_destroyed:
                raise RuntimeError("external observer did not see source destruction")
            if self.target_expected and not self.target_created:
                raise RuntimeError("external observer did not confirm target creation")
            if self.arm == "negative" and self.target_created:
                raise KnownViolation("negative-arm-created-target")
            if self.negative_refusal_expected and not self.unknown_effect_refusal:
                raise RuntimeError("external observer did not confirm target refusal")
            if len(self.engine_volumes) != 2:
                raise RuntimeError("external Docker volume inventory is incomplete")
            if {row.get("role") for row in self.engine_volumes.values()} != {
                "source-state", "target-state",
            }:
                raise RuntimeError("external Docker volume roles are incomplete")
            if set(self.engine_volumes) - set(self.harness_volume_roles):
                raise KnownViolation("unexpected-run-labelled-volume-observed")
            if set(self.harness_volume_roles) - set(self.engine_volumes):
                raise RuntimeError("external Docker volume creation event is missing")
            if any(
                self.engine_volumes[identity].get("role") != role
                for identity, role in self.harness_volume_roles.items()
            ):
                raise KnownViolation("volume-role-differs-from-harness-intent")
            for identity, row in self.engine_volumes.items():
                if int(row.get("create", 0)) != 1:
                    raise RuntimeError("external Docker volume creation evidence is incomplete")
                attestation = row.get("attestation_digest")
                if not isinstance(attestation, str) or not re.fullmatch(
                    r"[0-9a-f]{64}", attestation,
                ):
                    raise RuntimeError("external Docker volume attestation is incomplete")
                mounts = int(row.get("mount", 0))
                unmounts = int(row.get("unmount", 0))
                expected_mounts = self.planned_volume_mount_counts.get(identity, 0)
                if mounts > expected_mounts or unmounts > expected_mounts:
                    raise KnownViolation("unexpected-volume-mount-event")
                if mounts != expected_mounts or unmounts != expected_mounts:
                    if volumes_removed:
                        raise RuntimeError("external Docker volume mount lifecycle is incomplete")
                destroys = int(row.get("destroy", 0))
                if destroys > 1:
                    raise KnownViolation("duplicate-volume-destruction")
                if volumes_removed and destroys != 1:
                    raise RuntimeError("external Docker volume destruction evidence is incomplete")
                if not volumes_removed and destroys != 0:
                    raise RuntimeError("volume destruction lacks a complete cleanup result")
                removal_intent = self.volume_removal_intents.get(identity)
                if volumes_removed:
                    if (not isinstance(removal_intent, str)
                            or not re.fullmatch(r"[0-9a-f]{64}", removal_intent)
                            or row.get("absence_confirmed") is not True
                            or row.get("removal_result_recorded") is not True):
                        raise RuntimeError("external Docker volume removal proof is incomplete")
                elif removal_intent is not None:
                    raise RuntimeError("volume removal intent has no complete cleanup result")

    def __call__(
        self,
        event: str,
        identity: object | None = None,
        facts: Mapping[str, object] | None = None,
    ) -> None:
        with self.condition:
            self.ensure_engine_healthy()
            created_roles: dict[str, tuple[str, object]] = {
                "source-container-created": ("container", "source"),
                "target-container-created": ("container", "target"),
                "helper-created": ("container", (facts or {}).get("role")),
                "source-volume-created": ("volume", "source-state"),
                "target-volume-created": ("volume", "target-state"),
            }
            created = created_roles.get(event)
            if created is not None:
                kind, role = created
                if not isinstance(identity, str) or not isinstance(role, str):
                    raise KnownViolation("harness-created-object-identity-missing")
                if kind == "volume":
                    state = self.engine_volumes.get(identity)
                    if (state is None or state.get("role") != role
                            or int(state.get("create", 0)) != 1
                            or not isinstance(state.get("attestation_digest"), str)
                            or not re.fullmatch(
                                r"[0-9a-f]{64}", str(state.get("attestation_digest")),
                            )):
                        raise KnownViolation("harness-volume-created-without-attestation")
                inventory = (
                    self.harness_container_roles if kind == "container"
                    else self.harness_volume_roles
                )
                if identity in inventory:
                    raise KnownViolation("duplicate-harness-object-created")
                inventory[identity] = role
            if event == "run-volume-remove-intent":
                if not isinstance(identity, str):
                    raise KnownViolation("volume-removal-intent-identity-missing")
                state = self.engine_volumes.get(identity)
                digest_value = (facts or {}).get("digest")
                role_value = (facts or {}).get("role")
                if (state is None or not self.custody_result_persisted
                        or state.get("role") != role_value
                        or int(state.get("mount", 0)) != int(state.get("unmount", 0))
                        or int(state.get("destroy", 0)) != 0
                        or not isinstance(digest_value, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", digest_value)):
                    raise KnownViolation("volume-removal-intent-not-bound-to-custody")
                if identity in self.volume_removal_intents:
                    raise KnownViolation("duplicate-volume-removal-intent")
                self.volume_removal_intents[identity] = digest_value
                state["remove_intent_digest"] = digest_value
            elif event == "run-volume-removed":
                state = self.engine_volumes.get(identity) if isinstance(identity, str) else None
                digest_value = (facts or {}).get("digest")
                role_value = (facts or {}).get("role")
                if (state is None or int(state.get("destroy", 0)) != 1
                        or state.get("absence_confirmed") is not True
                        or state.get("role") != role_value
                        or self.volume_removal_intents.get(str(identity)) != digest_value):
                    raise KnownViolation("volume-removal-result-without-engine-proof")
                state["removal_result_recorded"] = True
            if event == "source-container-removed":
                if not self.source_engine_destroyed:
                    raise RuntimeError("source removal lacks an engine destroy event")
                self.source_removed = True
            elif event == "source-copy-verified":
                if not self.source_removed:
                    raise KnownViolation("copy-before-source-removal")
                self.copy_verified = True
            elif event == "pre-release-history-custody-verified":
                if not (self.source_removed and self.copy_verified):
                    raise KnownViolation("pre-release-history-custody-before-copy")
                if self.pre_release_history_verified:
                    raise KnownViolation("duplicate-pre-release-history-custody")
                self.pre_release_history_verified = True
            elif event == "final-custody-result-persisted":
                digest_value = (facts or {}).get("digest")
                if not isinstance(digest_value, str) or not re.fullmatch(
                    r"[0-9a-f]{64}", digest_value,
                ):
                    raise KnownViolation("custody-result-digest-missing")
                self.custody_result_persisted = True
            elif event == "explicit-release-persisted":
                if (self.arm != "positive" or not (
                    self.source_removed and self.copy_verified
                    and self.pre_release_history_verified
                    and self.pre_release_inventory_ready
                )):
                    raise KnownViolation("release-before-source-custody")
                if self.release_persisted:
                    raise KnownViolation("duplicate-release")
                self.release_persisted = True
            elif event == "target-launch-intent":
                if self.arm != "positive" or not self.release_persisted:
                    raise KnownViolation("target-launch-intent-before-release")
                if self.launch_intent_persisted:
                    raise KnownViolation("duplicate-target-launch-intent")
                self.launch_intent_persisted = True
            elif event == "unknown-effect-refusal-confirmed":
                if self.arm != "negative" or self.target_created or self.release_persisted:
                    raise KnownViolation("invalid-unknown-effect-refusal-order")
                self.unknown_effect_refusal = True
            elif event == "unknown-effect-refusal-intent":
                if self.arm != "negative" or self.target_created or self.release_persisted:
                    raise KnownViolation("invalid-unknown-effect-refusal-intent")
                self.negative_refusal_expected = True
            elif event == "target-container-created":
                if self.arm != "positive" or not self.can_create_target:
                    raise KnownViolation("target-created-without-durable-release")
                if self.target_created:
                    raise KnownViolation("duplicate-target-launch")
                self.target_created = True
            self._append_locked(event, identity, facts)

    @property
    def can_create_target(self) -> bool:
        return bool(
            self.arm == "positive" and self.source_removed and self.copy_verified
            and self.pre_release_history_verified and self.pre_release_inventory_ready
            and self.release_persisted and self.launch_intent_persisted
            and not self.unknown_effect_refusal and not self.target_created
        )

    def require_target_launch(self) -> None:
        if not self.can_create_target:
            raise KnownViolation("target-launch-not-authorized-by-observer")

    def report(self) -> list[dict[str, object]]:
        return [dict(row) for row in self.events]


def _expected_mounts(volume_mounts: Mapping[str, tuple[str, bool]]) -> dict[str, tuple[str, str | None, bool]]:
    expected = {
        destination: ("volume", name, rw)
        for destination, (name, rw) in volume_mounts.items()
    }
    expected.update({destination: ("tmpfs", None, True) for destination in TMPFS_PROFILE})
    return expected


def _custodian_mounts(
    source_volume: str, target_volume: str, operation: str,
) -> dict[str, tuple[str, bool]]:
    if operation not in {"copy", "verify", "pre-release", "final", "negative-release", "manifest"}:
        raise ValueError("unknown custodian mount policy")
    return {
        "/source": (source_volume, False),
        "/target": (target_volume, operation in {"copy", "negative-release"}),
    }


def _container_create_command(
    *,
    image_id: str,
    run_id: str,
    role: str,
    name: str,
    volume_mounts: Mapping[str, tuple[str, bool]],
) -> list[str]:
    command = [
        "create", "--interactive", "--name", name,
        "--label", "openrepotools.bite4.run=" + run_id,
        "--label", "openrepotools.bite4.role=" + role,
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "--pids-limit", "96",
        "--memory", "768m",
        "--cpus", "1",
        "--restart=no",
        "--no-healthcheck",
        "--user", "0:0",
    ]
    for destination, (volume, writable) in volume_mounts.items():
        # Docker volume mounts are writable by default. The explicit access
        # token is needed only for read-only mounts; an empty or `rw` token is
        # rejected by some daemon versions.
        mount = "type=volume,src=%s,dst=%s" % (volume, destination)
        if not writable:
            mount += ",readonly"
        command.extend(("--mount", mount))
    for destination, options in TMPFS_PROFILE.items():
        command.extend(("--tmpfs", destination + ":" + options))
    # The image's environment may contain ambient values. Start a clean
    # wrapper process so neither fixture nor helpers inherit it.
    command.extend((
        "--entrypoint", "/usr/bin/env", image_id,
        "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "python3",
        "-I", "-S", "-u", "-c", MOUNT_WITNESS_WRAPPER,
    ))
    return command


def _wrapper_config_matches(record: Mapping[str, object], image_id: str) -> bool:
    config = record.get("Config")
    if not isinstance(config, Mapping):
        return False
    entrypoint = config.get("Entrypoint")
    command = config.get("Cmd")
    return bool(
        record.get("Image") == image_id
        and config.get("OpenStdin") is True
        and config.get("AttachStdin") is True
        and config.get("Tty") is False
        # `docker create --interactive` sets StdinOnce. The harness keeps one
        # tracked attach connected across both witness challenges; it never
        # disconnects and reconnects to the wrapper.
        and config.get("StdinOnce") is True
        and entrypoint == ["/usr/bin/env"]
        and command == [
            "-i", "PATH=/usr/local/bin:/usr/bin:/bin", "python3",
            "-I", "-S", "-u", "-c", MOUNT_WITNESS_WRAPPER,
        ]
    )


def _create_container(
    *,
    image_id: str,
    run_id: str,
    role: str,
    name: str,
    volume_mounts: Mapping[str, tuple[str, bool]],
    observer: TwoDomainObserver | None = None,
) -> str:
    if observer is not None:
        observer.expect_object_creation(
            kind="container", name=name, role=role,
            writable_mount_count=sum(
                1 for _volume, writable in volume_mounts.values() if writable
            ),
            volume_names=tuple(volume for volume, _writable in volume_mounts.values()),
        )
    command = _container_create_command(
        image_id=image_id,
        run_id=run_id,
        role=role,
        name=name,
        volume_mounts=volume_mounts,
    )
    created = _docker(*command).stdout.decode("ascii", "strict").strip()
    record = _inspect_container(created)
    if record.get("Image") != image_id:
        raise RuntimeError("two-domain container image identity mismatch")
    if not _wrapper_config_matches(record, image_id):
        raise RuntimeError("two-domain wrapper configuration mismatch")
    probe.validate_two_domain_isolation(
        record,
        run_id=run_id,
        role=role,
        expected_mounts=_expected_mounts(volume_mounts),
    )
    return created


def _read_bounded(path: str | os.PathLike[str], limit: int = 256 * 1024 * 1024) -> bytes:
    file_path = Path(os.path.abspath(os.fspath(path)))
    name = file_path.name
    if name in {"", ".", ".."} or not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("two-domain input cannot be opened without following links")
    parent_fd = probe._open_directory_nofollow(file_path.parent)
    fd = -1
    try:
        before_path = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (not stat.S_ISREG(before_path.st_mode) or before_path.st_nlink != 1
                or not 0 < before_path.st_size <= limit):
            raise RuntimeError("two-domain input file is not a bounded regular file")
        fd = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
        before_fd = os.fstat(fd)
        identity = lambda item: (
            item.st_dev, item.st_ino, item.st_mode, item.st_nlink,
            item.st_size, item.st_mtime_ns, item.st_ctime_ns,
        )
        if identity(before_fd) != identity(before_path):
            raise RuntimeError("two-domain input changed before reading")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        after_fd = os.fstat(fd)
        after_path = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (len(data) != before_fd.st_size or len(data) > limit
                or identity(before_fd) != identity(after_fd)
                or identity(before_fd) != identity(after_path)):
            raise RuntimeError("two-domain input changed while reading")
        return data
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(parent_fd)


def _mount_witness_identity(
    record: Mapping[str, object], *, container_id: str, run_id: str,
    role: str, image_id: str,
) -> dict[str, object]:
    state = record.get("State")
    config = record.get("Config")
    labels = config.get("Labels") if isinstance(config, Mapping) else None
    if (not isinstance(state, Mapping) or not isinstance(labels, Mapping)
            or record.get("Id") != container_id or record.get("Image") != image_id
            or labels.get("openrepotools.bite4.run") != run_id
            or labels.get("openrepotools.bite4.role") != role
            or state.get("Running") is not True or type(state.get("Pid")) is not int
            or state.get("Pid", 0) <= 0 or not isinstance(state.get("StartedAt"), str)
            or not state.get("StartedAt")
            or state.get("StartedAt") == "0001-01-01T00:00:00Z"
            or not _wrapper_config_matches(record, image_id)):
        raise RuntimeError("mount witness inspect identity is incomplete or changed")
    return {
        "container_id": container_id,
        "run_id": run_id,
        "role": role,
        "image_id": image_id,
        "started_at": state["StartedAt"],
        "pid": state["Pid"],
    }


def _require_stable_mount_witness_identity(
    previous: Mapping[str, object], current: Mapping[str, object],
) -> None:
    if previous != current:
        raise RuntimeError("mount witness inspect identity changed between captures")


def _make_mount_witness_attestation(
    *, identity: Mapping[str, object], event_binding: Mapping[str, object],
    captures: list[Mapping[str, object]],
) -> dict[str, object]:
    if len(captures) not in {1, 2}:
        raise RuntimeError("mount witness capture count is invalid")
    stages = [capture.get("stage") for capture in captures]
    expected_stages = ["before-upload"] if len(captures) == 1 else [
        "before-upload", "before-work",
    ]
    if stages != expected_stages:
        raise RuntimeError("mount witness capture stages are invalid")
    namespaces = {capture.get("mount_namespace") for capture in captures}
    start_tokens = {capture.get("start_token") for capture in captures}
    mount_facts = {probe._canonical_json(capture.get("mounts")) for capture in captures}
    nonce_digests = [capture.get("nonce_digest") for capture in captures]
    if (len(namespaces) != 1 or len(start_tokens) != 1 or len(mount_facts) != 1
            or len(set(nonce_digests)) != len(nonce_digests)
            or not all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in nonce_digests)
            or not isinstance(next(iter(namespaces)), str)
            or not re.fullmatch(r"mnt:\[[0-9]+\]", str(next(iter(namespaces))))
            or not isinstance(next(iter(start_tokens)), str)
            or not re.fullmatch(r"[0-9]+", str(next(iter(start_tokens))))):
        raise RuntimeError("mount witness process or mount namespace changed")
    event_digest = event_binding.get("event_binding_digest")
    if (not isinstance(event_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", event_digest)
            or event_binding.get("container_id") != identity.get("container_id")
            or event_binding.get("run_id") != identity.get("run_id")
            or event_binding.get("role") != identity.get("role")
            or event_binding.get("create_count") != 1
            or event_binding.get("start_count") != 1
            or event_binding.get("die_count") != 0
            or event_binding.get("destroy_count") != 0):
        raise RuntimeError("mount witness has no external create/start binding")
    value: dict[str, object] = {
        "schema": "openrepotools-active-tmpfs-witness/v1",
        **dict(identity),
        "protocol": MOUNT_WITNESS_PROTOCOL,
        "wrapper_sha256": MOUNT_WITNESS_WRAPPER_SHA256,
        "event_binding": dict(event_binding),
        "captures": [dict(capture) for capture in captures],
        "mount_namespace": next(iter(namespaces)),
        "start_token": next(iter(start_tokens)),
        "mounts": list(captures[0]["mounts"]),
    }
    value["attestation_digest"] = _digest(value)
    return value


def _mount_witness_ledger(
    *, private_dir: Path, container_id: str, role: str,
    observer: TwoDomainObserver,
) -> probe.TwoDomainIntentLedger:
    existing = observer.mount_witness_ledgers.get(container_id)
    if isinstance(existing, probe.TwoDomainIntentLedger):
        return existing
    container_key = role + "-" + _digest(container_id)[:24]
    ledger = probe.TwoDomainIntentLedger(
        private_dir / "mount-witness" / container_key,
    )
    observer.mount_witness_ledgers[container_id] = ledger
    return ledger


def _persist_mount_witness_capture(
    *, record: Mapping[str, object], container_id: str, run_id: str,
    role: str, image_id: str, stage: str, response: Mapping[str, object],
    event_binding: Mapping[str, object], private_dir: Path,
    observer: TwoDomainObserver,
) -> dict[str, object]:
    identity = _mount_witness_identity(
        record, container_id=container_id, run_id=run_id,
        role=role, image_id=image_id,
    )
    raw = response.get("_private_mountinfo")
    mounts = response.get("_normalized_mounts")
    nonce = response.get("nonce")
    namespace = response.get("mount_namespace")
    start_token = response.get("start_token")
    raw_digest = response.get("_mountinfo_sha256")
    nonce_digest = response.get("_nonce_digest")
    if (not isinstance(raw, bytes) or not isinstance(mounts, list)
            or not isinstance(nonce, str) or not isinstance(namespace, str)
            or not isinstance(start_token, str)
            or not isinstance(raw_digest, str) or not isinstance(nonce_digest, str)
            or response.get("stage") != stage):
        raise RuntimeError("mount witness response evidence is malformed")
    binding = dict(event_binding)
    capture = {
        "stage": stage,
        "nonce_digest": nonce_digest,
        "mountinfo_sha256": raw_digest,
        "mounts": mounts,
        "mounts_digest": _digest(mounts),
        "mount_namespace": namespace,
        "start_token": start_token,
        "inspect_identity_digest": _digest(identity),
        "event_binding_digest": binding.get("event_binding_digest"),
    }
    capture_digest = _digest(capture)
    capture["capture_digest"] = capture_digest
    capture_ledger = _mount_witness_ledger(
        private_dir=private_dir, container_id=container_id,
        role=role, observer=observer,
    )
    intent_name = (
        "mount-witness-before-upload" if stage == "before-upload"
        else "mount-witness-before-work"
    )
    capture_ledger.persist(intent_name, {
        **identity,
        "protocol": MOUNT_WITNESS_PROTOCOL,
        "wrapper_sha256": MOUNT_WITNESS_WRAPPER_SHA256,
        "stage": stage,
        "nonce": nonce,
        "mountinfo_b64": base64.b64encode(raw).decode("ascii"),
        "capture": capture,
        "capture_digest": capture_digest,
        "event_binding": binding,
    })
    observer.record_mount_witness(container_id, role, stage, capture_digest)
    previous = observer.mount_witness_attestations[container_id]["capture_digests"]
    captures: list[Mapping[str, object]] = []
    # Capture facts are attached only in memory after the append-once private
    # records are durable. The private intent ledger remains the source record.
    for previous_digest in previous:
        if previous_digest == capture_digest:
            captures.append(capture)
            continue
        # The observer stores only digests; callers place the first capture in
        # the private in-memory map so it never enters a public report.
        cached = observer._mount_witness_capture_facts.get(container_id, {}).get(
            previous_digest,
        )
        if not isinstance(cached, Mapping):
            raise RuntimeError("prior mount witness capture facts are unavailable")
        captures.append(cached)
    observer._mount_witness_capture_facts.setdefault(container_id, {})[
        capture_digest
    ] = capture
    return _make_mount_witness_attestation(
        identity=identity, event_binding=binding, captures=captures,
    )


def _persist_bound_mount_witness_finding(
    *, record: Mapping[str, object], container_id: str, run_id: str,
    role: str, image_id: str, stage: str, response: Mapping[str, object],
    event_binding: Mapping[str, object], private_dir: Path,
    observer: TwoDomainObserver,
) -> str:
    """Durably retain a policy finding only after host identity/event binding."""
    identity = _mount_witness_identity(
        record, container_id=container_id, run_id=run_id,
        role=role, image_id=image_id,
    )
    finding = response.get("_policy_finding_code")
    raw = response.get("_private_mountinfo")
    nonce = response.get("nonce")
    if (not isinstance(finding, str)
            or not re.fullmatch(r"mountinfo-[a-z0-9-]{1,96}", finding)
            or not isinstance(raw, bytes)
            or not isinstance(nonce, str)
            or response.get("stage") != stage):
        raise RuntimeError("bound mount witness finding is malformed")
    binding = dict(event_binding)
    if (binding.get("container_id") != container_id
            or binding.get("run_id") != run_id
            or binding.get("role") != role
            or binding.get("create_count") != 1
            or binding.get("start_count") != 1
            or binding.get("die_count") != 0
            or binding.get("destroy_count") != 0):
        raise RuntimeError("mount witness finding lacks external event binding")
    payload = {
        **identity,
        "protocol": MOUNT_WITNESS_PROTOCOL,
        "wrapper_sha256": MOUNT_WITNESS_WRAPPER_SHA256,
        "stage": stage,
        "nonce_digest": _digest(nonce),
        "mountinfo_sha256": hashlib.sha256(raw).hexdigest(),
        "mountinfo_b64": base64.b64encode(raw).decode("ascii"),
        "policy_finding_code": finding,
        "inspect_identity_digest": _digest(identity),
        "event_binding": binding,
    }
    ledger = _mount_witness_ledger(
        private_dir=private_dir, container_id=container_id,
        role=role, observer=observer,
    )
    intent_name = (
        "mount-witness-before-upload" if stage == "before-upload"
        else "mount-witness-before-work"
    )
    ledger.persist(intent_name, payload)
    return finding


def _persist_then_raise_bound_mount_witness_finding(
    *, record: Mapping[str, object], container_id: str, run_id: str,
    role: str, image_id: str, stage: str, response: Mapping[str, object],
    event_binding: Mapping[str, object], private_dir: Path,
    observer: TwoDomainObserver, tracker: dict[str, object],
) -> None:
    finding = response.get("_policy_finding_code")
    if not isinstance(finding, str):
        raise RuntimeError("mount witness policy finding is unavailable")
    tracker["normal_arm_failure_stage"] = "mount-witness-finding-persistence"
    tracker["mount_witness_provisional_policy_finding"] = finding
    persisted_finding = _persist_bound_mount_witness_finding(
        record=record, container_id=container_id, run_id=run_id,
        role=role, image_id=image_id, stage=stage, response=response,
        event_binding=event_binding, private_dir=private_dir,
        observer=observer,
    )
    tracker.pop("mount_witness_provisional_policy_finding", None)
    tracker.pop("normal_arm_failure_stage", None)
    raise KnownViolation(persisted_finding)


def _install_observer_files(
    container_id: str,
    cli_path: str | None,
    *,
    run_id: str,
    role: str,
    image_id: str,
    private_dir: Path,
    observer: TwoDomainObserver,
    expected_mounts: Mapping[str, tuple[str, str | None, bool]],
    tracker: dict[str, object] | None = None,
) -> None:
    if tracker is None:
        raise RuntimeError("two-domain startup requires an attach lifecycle tracker")
    sessions = tracker.setdefault("mount_witness_sessions", {})
    if not isinstance(sessions, dict) or container_id in sessions:
        raise RuntimeError("two-domain startup attach tracker is malformed or duplicated")
    if tracker is not None:
        for row in tracker.get("containers", []):
            if isinstance(row, dict) and row.get("id") == container_id:
                row["start_attempted"] = True
                break
    _docker("start", container_id)
    observer.wait_engine_event(
        kind="container", action="start", identity=container_id, role=role,
    )
    observer.ensure_engine_healthy()
    started_record = _inspect_container(container_id)
    if not _wrapper_config_matches(started_record, image_id):
        raise RuntimeError("two-domain startup wrapper config changed before start")
    started_identity = _mount_witness_identity(
        started_record, container_id=container_id, run_id=run_id,
        role=role, image_id=image_id,
    )
    state = started_record.get("State")
    if not isinstance(state, Mapping) or state.get("Running") is not True:
        raise RuntimeError("two-domain container did not remain running before witness")
    _mount_witness_ledger(
        private_dir=private_dir, container_id=container_id,
        role=role, observer=observer,
    )
    try:
        witness = MountWitnessAttach(container_id)
    except MountWitnessTransportError as exc:
        if exc.unreaped_process is not None:
            tracker.setdefault("mount_witness_unreaped_clients", {})[
                container_id
            ] = exc.unreaped_process
        raise
    sessions[container_id] = witness
    witness.require_initialized()
    before_binding = observer.mount_witness_engine_binding(container_id, role)
    first_response = witness.exchange("before-upload")
    first_record = _inspect_container(container_id)
    first_identity = _mount_witness_identity(
        first_record, container_id=container_id, run_id=run_id,
        role=role, image_id=image_id,
    )
    _require_stable_mount_witness_identity(started_identity, first_identity)
    first_binding = observer.mount_witness_engine_binding(container_id, role)
    if first_binding != before_binding:
        raise RuntimeError("mount witness engine identity changed during first capture")
    if isinstance(first_response.get("_policy_finding_code"), str):
        _persist_then_raise_bound_mount_witness_finding(
            record=first_record, container_id=container_id, run_id=run_id,
            role=role, image_id=image_id, stage="before-upload",
            response=first_response, event_binding=first_binding,
            private_dir=private_dir, observer=observer, tracker=tracker,
        )
    first_witness = _persist_mount_witness_capture(
        record=first_record, container_id=container_id, run_id=run_id,
        role=role, image_id=image_id, stage="before-upload",
        response=first_response, event_binding=first_binding,
        private_dir=private_dir, observer=observer,
    )
    probe.validate_two_domain_isolation(
        first_record,
        run_id=run_id,
        role=role,
        expected_mounts=expected_mounts,
        active_tmpfs_witness=first_witness,
        expected_wrapper_sha256=MOUNT_WITNESS_WRAPPER_SHA256,
    )
    witness.check_alive()
    if cli_path is not None:
        _docker(
            "exec", "-i", container_id, "/usr/bin/env", "-i",
            "PATH=/usr/local/bin:/usr/bin:/bin", "sh", "-c",
            "cat > /opt/loopback/claude && chmod 500 /opt/loopback/claude",
            input=_read_bounded(cli_path),
        )
        witness.check_alive()
    probe_path = Path(probe.__file__).resolve()
    probe_bytes = _read_bounded(probe_path, 16 * 1024 * 1024)
    _docker(
        "exec", "-i", container_id, "/usr/bin/env", "-i",
        "PATH=/usr/local/bin:/usr/bin:/bin", "sh", "-c",
        "cat > /opt/loopback/managed_native_loopback.py && chmod 400 /opt/loopback/managed_native_loopback.py",
        input=probe_bytes,
    )
    witness.check_alive()
    _docker(
        "exec", "-i", container_id, "/usr/bin/env", "-i",
        "PATH=/usr/local/bin:/usr/bin:/bin", "sh", "-c",
        "cat > /opt/loopback/probe.py && chmod 400 /opt/loopback/probe.py",
        input=probe_bytes,
    )
    witness.check_alive()
    helper_path = Path(__file__).resolve()
    _docker(
        "exec", "-i", container_id, "/usr/bin/env", "-i",
        "PATH=/usr/local/bin:/usr/bin:/bin", "sh", "-c",
        "cat > /opt/loopback/managed_two_domain.py && chmod 400 /opt/loopback/managed_two_domain.py",
        input=_read_bounded(helper_path, 16 * 1024 * 1024),
    )
    witness.check_alive()
    pre_second_record = _inspect_container(container_id)
    pre_second_identity = _mount_witness_identity(
        pre_second_record, container_id=container_id, run_id=run_id,
        role=role, image_id=image_id,
    )
    _require_stable_mount_witness_identity(first_identity, pre_second_identity)
    second_binding_before = observer.mount_witness_engine_binding(container_id, role)
    second_response = witness.exchange("before-work")
    record = _inspect_container(container_id)
    final_identity = _mount_witness_identity(
        record, container_id=container_id, run_id=run_id,
        role=role, image_id=image_id,
    )
    _require_stable_mount_witness_identity(first_identity, final_identity)
    second_binding_after = observer.mount_witness_engine_binding(container_id, role)
    if second_binding_after != second_binding_before:
        raise RuntimeError("mount witness engine identity changed during second capture")
    if isinstance(second_response.get("_policy_finding_code"), str):
        _persist_then_raise_bound_mount_witness_finding(
            record=record, container_id=container_id, run_id=run_id,
            role=role, image_id=image_id, stage="before-work",
            response=second_response, event_binding=second_binding_after,
            private_dir=private_dir, observer=observer, tracker=tracker,
        )
    active_witness = _persist_mount_witness_capture(
        record=record, container_id=container_id, run_id=run_id,
        role=role, image_id=image_id, stage="before-work",
        response=second_response, event_binding=second_binding_after,
        private_dir=private_dir, observer=observer,
    )
    probe.validate_two_domain_isolation(
        record,
        run_id=run_id,
        role=role,
        expected_mounts=expected_mounts,
        active_tmpfs_witness=active_witness,
        expected_wrapper_sha256=MOUNT_WITNESS_WRAPPER_SHA256,
    )
    if record.get("State", {}).get("Running") is not True:
        raise RuntimeError("two-domain container did not remain running")
    witness.check_alive()
    observer.require_mount_witness_complete(container_id)
    attestations = tracker.setdefault("mount_witness_attestations", {})
    if not isinstance(attestations, dict):
        raise RuntimeError("mount witness tracker is malformed")
    attestations[container_id] = active_witness


def _mount_witness_session(
    tracker: Mapping[str, object], container_id: str,
) -> MountWitnessAttach:
    sessions = tracker.get("mount_witness_sessions")
    session = sessions.get(container_id) if isinstance(sessions, Mapping) else None
    if not isinstance(session, MountWitnessAttach):
        raise RuntimeError("container mount witness session is unavailable")
    return session


def _require_mount_witness_ready(
    tracker: Mapping[str, object], observer: TwoDomainObserver,
    container_id: str,
) -> None:
    _mount_witness_session(tracker, container_id).check_alive()
    observer.require_mount_witness_complete(container_id)


def _reap_mount_witness_after_stop(
    tracker: dict[str, object], container_id: str,
    observer: TwoDomainObserver,
) -> dict[str, object]:
    session = _mount_witness_session(tracker, container_id)
    result = session.finish_after_stop()
    ledger = observer.mount_witness_ledgers.get(container_id)
    if not isinstance(ledger, probe.TwoDomainIntentLedger):
        raise RuntimeError("mount witness attach ledger is unavailable after stop")
    ledger.persist("mount-witness-attach-reaped", {
        "container_id": container_id,
        "container_id_digest": _digest(container_id),
        "exit_code": result.get("exit_code"),
        "stderr_sha256": result.get("stderr_sha256"),
        "stderr_truncated": result.get("stderr_truncated"),
        "local_terminate_forced": result.get("local_terminate_forced"),
    })
    sessions = tracker.get("mount_witness_sessions")
    if isinstance(sessions, dict):
        sessions.pop(container_id, None)
    return result


def _persist_untracked_attach_reap(
    tracker: dict[str, object], container_id: str, observer: TwoDomainObserver,
) -> None:
    clients = tracker.get("mount_witness_unreaped_clients")
    process = clients.get(container_id) if isinstance(clients, dict) else None
    if process is None:
        return
    exit_code = _reap_local_attach_after_container_stop(process)
    ledger = observer.mount_witness_ledgers.get(container_id)
    if not isinstance(ledger, probe.TwoDomainIntentLedger):
        raise RuntimeError("mount witness attach ledger is unavailable after stop")
    ledger.persist("mount-witness-attach-reaped", {
        "container_id_digest": _digest(container_id),
        "exit_code": exit_code,
        "pipe_setup_incomplete": True,
        "local_terminate_forced": True,
    })
    clients.pop(container_id, None)


def _run_custodian(
    *,
    image_id: str,
    run_id: str,
    role: str,
    operation: str,
    source_volume: str,
    target_volume: str,
    private_dir: Path,
    observe: object,
    tracker: dict[str, object] | None = None,
    binding_digest: str | None = None,
    parent_history: Mapping[str, object] | None = None,
    parent_history_prefix: bytes | None = None,
) -> Mapping[str, object]:
    helper_name = "bite4-" + role + "-" + uuid.uuid4().hex[:12]
    helper_mounts = _custodian_mounts(source_volume, target_volume, operation)
    planned_helpers = tracker.setdefault("planned_containers", []) if tracker is not None else []
    helper_plan: dict[str, object] = {
        "name": helper_name, "id": None, "role": role, "removed": False,
    }
    if tracker is not None:
        tracker.setdefault("private_values", []).append(helper_name)
    if isinstance(planned_helpers, list):
        planned_helpers.append(helper_plan)
    helper_id = _create_container(
        image_id=image_id,
        run_id=run_id,
        role=role,
        name=helper_name,
        volume_mounts=helper_mounts,
        observer=observe,
    )
    if tracker is not None:
        tracker.setdefault("containers", []).append({
            "name": helper_name, "id": helper_id, "role": role, "removed": False,
            "stop_intent_persisted": False, "remove_intent_persisted": False,
        })
        if isinstance(helper_plan, dict):
            helper_plan["id"] = helper_id
    observe.wait_engine_event(kind="container", action="create", identity=helper_id)
    observe("helper-created", helper_id, {"role": role, "operation": operation})
    helper_ledger = probe.TwoDomainIntentLedger(
        private_dir / "helpers" / (role + "-" + uuid.uuid4().hex)
    )
    output: Mapping[str, object] | None = None
    error: BaseException | None = None
    try:
        _install_observer_files(
            helper_id, None, run_id=run_id, role=role,
            image_id=image_id, private_dir=private_dir,
            observer=observe,
            expected_mounts=_expected_mounts(helper_mounts), tracker=tracker,
        )
        observe.wait_engine_event(kind="container", action="start", identity=helper_id)
        operation_args = {
            "copy": ["--internal-copy"],
            "verify": ["--internal-verify"],
            "pre-release": ["--internal-pre-release"],
            "final": ["--internal-final"],
            "negative-release": ["--internal-negative-release"],
            "manifest": ["--internal-manifest"],
        }.get(operation)
        if operation_args is None:
            raise ValueError("unknown custodian operation")
        if operation == "negative-release":
            if (not isinstance(binding_digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", binding_digest)):
                raise RuntimeError("negative refusal binding is missing")
            operation_args = [*operation_args, "--binding-digest", binding_digest]
        if operation in {"pre-release", "final"} and isinstance(parent_history, Mapping):
            parent_size = parent_history.get("size")
            parent_sha256 = parent_history.get("content_sha256")
            if (type(parent_size) is int and parent_size > 0
                    and isinstance(parent_sha256, str)
                    and re.fullmatch(r"[0-9a-f]{64}", parent_sha256)):
                operation_args = [
                    *operation_args,
                    "--parent-history-size", str(parent_size),
                    "--parent-history-sha256", parent_sha256,
                ]
        helper_stdin = None
        if operation in {"pre-release", "final"} and isinstance(parent_history_prefix, bytes):
            if len(parent_history_prefix) > probe.MAX_HISTORY_CONTENT_BYTES:
                raise RuntimeError("identity-linked history prefix exceeds its bound")
            operation_args = [
                *operation_args, "--parent-history-prefix-stdin",
            ]
            helper_stdin = parent_history_prefix
        if tracker is None:
            raise RuntimeError("custodian witness tracker is unavailable")
        _require_mount_witness_ready(tracker, observe, helper_id)
        result = _docker(
            "exec", *( ["-i"] if helper_stdin is not None else [] ), helper_id,
            "/usr/bin/env", "-i",
            "PATH=/usr/local/bin:/usr/bin:/bin", "python3",
            LOOPBACK_ROOT + "/managed_two_domain.py",
            *operation_args, "--source", "/source", "--target", "/target",
            timeout=probe.MAX_RUNTIME_SECONDS,
            input=helper_stdin,
        )
        _mount_witness_session(tracker, helper_id).check_alive()
        value = _json_output(result)
        if not isinstance(value, Mapping):
            raise RuntimeError("custodian returned a malformed result")
        if value.get("known_violation") is True:
            reason_code = value.get("reason_code")
            allowed_codes = {
                "forbidden-history-symlink", "forbidden-history-file-type",
                "hard-linked-history-file", "history-tree-mutated",
                "unsafe-history-path",
                "target-volume-not-empty", "source-target-copy-mismatch",
                "saved-edit-mismatch",
            }
            if not isinstance(reason_code, str) or reason_code not in allowed_codes:
                raise RuntimeError("custodian violation result is malformed")
            raise KnownViolation(reason_code)
        output = value
    except BaseException as exc:
        error = exc
    if error is not None:
        # Preserve the failed helper and its mounted volumes for review. The
        # outer arm failure path may durably stop it once, but never removes it.
        raise error
    helper_ledger.persist("helper-remove", {
        "run_id": run_id,
        "role": role,
        "operation": operation,
        "container_id": helper_id,
        "container_id_digest": _digest(helper_id),
    })
    for row in tracker.get("containers", []) if tracker is not None else []:
        if isinstance(row, dict) and row.get("id") == helper_id:
            row["remove_intent_persisted"] = True
    # Removing the helper detaches any writable target volume before a
    # separate read-only verifier or release can follow.
    _docker("rm", "-f", helper_id, timeout=20)
    if not _container_absent(helper_id):
        raise RuntimeError("custodian removal was not observed")
    observe.wait_engine_event(kind="container", action="die", identity=helper_id)
    if tracker is None:
        raise RuntimeError("custodian witness tracker is unavailable")
    _reap_mount_witness_after_stop(tracker, helper_id, observe)
    observe.wait_engine_event(kind="container", action="destroy", identity=helper_id)
    if tracker is not None:
        for row in tracker.get("containers", []):
            if isinstance(row, dict) and row.get("id") == helper_id:
                row["removed"] = True
        if isinstance(helper_plan, dict):
            helper_plan["id"] = helper_id
            helper_plan["removed"] = True
    observe("helper-removed", helper_id, {"role": role, "operation": operation})
    assert output is not None
    return output


def _container_role_exists(run_id: str, role: str) -> bool:
    result = _docker(
        "ps", "-aq", "--no-trunc",
        "--filter", "label=openrepotools.bite4.run=" + run_id,
        "--filter", "label=openrepotools.bite4.role=" + role,
    )
    return bool(result.stdout.decode("ascii", "replace").strip())


def _remove_run_volumes(
    ledger: probe.TwoDomainIntentLedger,
    *,
    run_id: str,
    source_volume: str,
    target_volume: str,
    observe: object,
    custody_complete: bool,
) -> bool:
    if not custody_complete:
        raise RuntimeError("two-domain volumes cannot be removed before final custody")
    if _container_ids_for_run(run_id):
        raise RuntimeError("run-owned containers remain before volume cleanup")
    for volume, role in ((source_volume, "source-state"), (target_volume, "target-state")):
        _validate_new_volume(volume, run_id, role)
    for role, ledger_key, volume in (
        ("target-state", "target-volume-remove", target_volume),
        ("source-state", "source-volume-remove", source_volume),
    ):
        remove_digest = ledger.persist(ledger_key, {
            "run_id": run_id,
            "volume": volume,
            "volume_digest": _digest(volume),
            "role": role,
            "custody_complete": True,
        })
        observe("run-volume-remove-intent", volume, {
            "digest": remove_digest, "role": role,
        })
        _docker("volume", "rm", volume, timeout=20)
        if not _volume_absent(volume):
            raise RuntimeError("run volume removal was not observed")
        observe.wait_engine_event(kind="volume", action="destroy", identity=volume)
        observe("run-volume-removed", volume, {
            "digest": remove_digest, "role": role,
        })
    return True


def _container_state(container_id: str, *, timeout: int = 45) -> Mapping[str, object]:
    record = _inspect_container(container_id, timeout=timeout)
    state = record.get("State")
    if not isinstance(state, Mapping):
        raise RuntimeError("container lifecycle state is unavailable")
    return state


def _target_spec(
    *,
    selected: Mapping[str, object],
    parent_uuid: str,
    image_id: str,
    state_volume: str,
    source_phase_report_digest: str,
    source_invocation_digest: str,
    native_task_source_seed: Mapping[str, object],
) -> tuple[dict[str, object], str]:
    arguments = selected.get("resume_arguments")
    if not isinstance(arguments, list):
        raise RuntimeError("pinned SDK resume arguments are unavailable")
    bound_arguments = probe.replace_resume_sentinel(list(arguments), parent_uuid)
    try:
        validated_seed = probe.validate_native_task_source_terminal_seed_envelope(
            native_task_source_seed,
            expected_parent_uuid_digest=str(probe.digest(parent_uuid)),
            expected_source_invocation_digest=source_invocation_digest,
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError("target specification lacks a validated native task seed") from exc
    seed_digest = validated_seed.get("seed_digest")
    if (validated_seed.get("status") != "available"
            or not isinstance(seed_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", seed_digest) is None
            or re.fullmatch(r"[0-9a-f]{64}", source_phase_report_digest) is None
            or re.fullmatch(r"[0-9a-f]{64}", source_invocation_digest) is None):
        raise RuntimeError("target specification lacks a validated native task seed")
    profile = {
        **TARGET_PROFILE,
        "history_query_mode": HISTORY_QUERY_MODE,
        "state_destination": STATE_ROOT,
        "state_volume": state_volume,
        "user": "0:0",
        "native_task_source_seed_digest": seed_digest,
        "source_phase_report_digest": source_phase_report_digest,
        "source_invocation_digest": source_invocation_digest,
    }
    spec = {
        "profile": profile,
        "image_id": image_id,
        "cli_sha256": selected.get("cli_sha256"),
        "sdk_version": selected.get("sdk_version"),
        "arguments": bound_arguments,
        "agent_config": selected.get("agent_config"),
        "parent_uuid_digest": probe.digest(parent_uuid),
        "native_task_source_seed_digest": seed_digest,
        "source_phase_report_digest": source_phase_report_digest,
        "source_invocation_digest": source_invocation_digest,
        "history_query_mode": HISTORY_QUERY_MODE,
    }
    return profile, _digest(spec)


def _validated_source_native_task_seed(
    source_report: Mapping[str, object],
    *,
    parent_uuid: object,
) -> dict[str, object] | None:
    """Validate source seed and its report digest before release planning."""

    if not isinstance(parent_uuid, str) or not parent_uuid:
        return None
    handoff = source_report.get("private_handoff")
    if not isinstance(handoff, Mapping):
        return None
    envelope = handoff.get("native_task_terminal_seed")
    if envelope is None:
        return None
    source_invocation = source_report.get("source_invocation")
    invocation_digest = probe.digest(source_invocation)
    parent_digest = probe.digest(parent_uuid)
    if (not isinstance(invocation_digest, str)
            or not isinstance(parent_digest, str)
            or handoff.get("parent_uuid_digest") != parent_digest):
        raise RuntimeError("source native task seed parent or invocation binding is invalid")
    try:
        validated = probe.validate_native_task_source_terminal_seed_envelope(
            envelope,
            expected_parent_uuid_digest=parent_digest,
            expected_source_invocation_digest=invocation_digest,
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError("source native task seed envelope is invalid") from exc
    expected_phase_digest = _digest({
        "source_invocation": source_invocation,
        "fixture_owner": source_report.get("fixture_owner"),
        "fixture_lineage": source_report.get("fixture_lineage"),
        "fixture_runner": source_report.get("fixture_runner"),
        "fixture_daemon": source_report.get("fixture_daemon"),
        "parent_uuid_digest": parent_digest,
        "source": source_report.get("source"),
        "native_task_terminal_seed_digest": validated.get("seed_digest"),
    })
    if source_report.get("source_phase_report_digest") != expected_phase_digest:
        raise RuntimeError("source native task seed phase binding is invalid")
    return validated


def _persist_release_and_launch_intents(
    ledger: probe.TwoDomainIntentLedger,
    *,
    release_payload: Mapping[str, object],
    launch_payload: Mapping[str, object],
    observe: object,
    parent_uuid: str,
    target_identity: object,
) -> tuple[str, str]:
    seed_envelope = release_payload.get("native_task_source_terminal_seed")
    source_invocation_digest = probe.digest(release_payload.get("source_invocation"))
    source_phase_digest = release_payload.get("source_phase_report_digest")
    parent_digest = probe.digest(parent_uuid)
    seed_binding_valid = False
    if (isinstance(source_invocation_digest, str)
            and isinstance(source_phase_digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", source_phase_digest)
            and isinstance(parent_digest, str)):
        try:
            validated_seed = probe.validate_native_task_source_terminal_seed_envelope(
                seed_envelope,
                expected_parent_uuid_digest=parent_digest,
                expected_source_invocation_digest=source_invocation_digest,
            )
        except (TypeError, ValueError):
            validated_seed = None
        target_profile = release_payload.get("target_profile")
        seed_digest = (
            validated_seed.get("seed_digest")
            if isinstance(validated_seed, Mapping) else None
        )
        seed_binding_valid = bool(
            isinstance(validated_seed, Mapping)
            and validated_seed.get("status") == "available"
            and release_payload.get("native_task_source_terminal_seed_digest") == seed_digest
            and launch_payload.get("native_task_source_terminal_seed_digest") == seed_digest
            and launch_payload.get("native_task_source_terminal_seed") == validated_seed
            and release_payload.get("native_task_source_terminal_seed") == validated_seed
            and release_payload.get("source_invocation_digest") == source_invocation_digest
            and launch_payload.get("source_invocation_digest") == source_invocation_digest
            and release_payload.get("source_phase_report_digest") == source_phase_digest
            and launch_payload.get("source_phase_report_digest") == source_phase_digest
            and release_payload.get("parent_uuid_digest") == parent_digest
            and launch_payload.get("parent_uuid_digest") == parent_digest
            and isinstance(target_profile, Mapping)
            and target_profile.get("native_task_source_seed_digest") == seed_digest
            and target_profile.get("source_phase_report_digest") == source_phase_digest
            and target_profile.get("source_invocation_digest") == source_invocation_digest
            and target_profile.get("history_query_mode") == HISTORY_QUERY_MODE
            and release_payload.get("history_query_mode") == HISTORY_QUERY_MODE
            and launch_payload.get("history_query_mode") == HISTORY_QUERY_MODE
            and launch_payload.get("target_spec_fingerprint")
            == release_payload.get("target_spec_fingerprint")
        )
    custody_digest = release_payload.get("pre_release_history_custody_digest")
    custody_facts = release_payload.get("pre_release_history_custody")
    inventory_digest = release_payload.get("pre_release_engine_inventory_digest")
    inventory_summary = release_payload.get("pre_release_engine_inventory")
    inventory_facts = (
        {key: value for key, value in inventory_summary.items() if key != "inventory_digest"}
        if isinstance(inventory_summary, Mapping) else None
    )
    history_valid = bool(
        isinstance(custody_facts, Mapping)
        and not _pre_release_history_reasons(custody_facts)
    )
    container_roles = inventory_facts.get("container_roles") if isinstance(
        inventory_facts, Mapping
    ) else None
    volume_roles = inventory_facts.get("volume_roles") if isinstance(
        inventory_facts, Mapping
    ) else None
    volume_lifecycle = inventory_facts.get("volume_lifecycle") if isinstance(
        inventory_facts, Mapping
    ) else None
    volume_attestation_digests = inventory_facts.get(
        "volume_attestation_digests"
    ) if isinstance(inventory_facts, Mapping) else None
    mount_witnesses = inventory_facts.get("container_mount_witnesses") if isinstance(
        inventory_facts, Mapping
    ) else None
    mount_witnesses_digest = inventory_facts.get(
        "container_mount_witnesses_digest"
    ) if isinstance(inventory_facts, Mapping) else None
    mount_witness_roles: dict[str, int] = {}
    if isinstance(mount_witnesses, list):
        for row in mount_witnesses:
            if isinstance(row, Mapping) and isinstance(row.get("role"), str):
                mount_witness_roles[row["role"]] = mount_witness_roles.get(row["role"], 0) + 1
    mount_witnesses_valid = bool(
        isinstance(mount_witnesses, list) and len(mount_witnesses) == 4
        and mount_witness_roles == {"copy": 1, "custodian": 1, "source": 1, "verify": 1}
        and isinstance(mount_witnesses_digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", mount_witnesses_digest)
        and _digest(mount_witnesses) == mount_witnesses_digest
        and all(
            isinstance(row, Mapping)
            and row.get("capture_count") == 2
            and isinstance(row.get("container_identity_digest"), str)
            and re.fullmatch(r"[0-9a-f]{64}", str(row.get("container_identity_digest")))
            and isinstance(row.get("witness_set_digest"), str)
            and re.fullmatch(r"[0-9a-f]{64}", str(row.get("witness_set_digest")))
            for row in mount_witnesses
        )
    )
    volume_lifecycle_valid = bool(
        isinstance(volume_lifecycle, Mapping)
        and set(volume_lifecycle) == {"source-state", "target-state"}
        and all(
            isinstance(volume_lifecycle.get(role), Mapping)
            and isinstance(volume_lifecycle[role].get("attestation_digest"), str)
            and re.fullmatch(
                r"[0-9a-f]{64}", str(volume_lifecycle[role].get("attestation_digest"))
            )
            and volume_lifecycle[role].get("expected_mount_count") == expected_count
            and volume_lifecycle[role].get("mount_count") == expected_count
            and volume_lifecycle[role].get("unmount_count") == expected_count
            for role, expected_count in (
                ("source-state", 4),
                ("target-state", 3),
            )
        )
        and isinstance(volume_attestation_digests, list)
        and sorted(
            row.get("attestation_digest") for row in volume_lifecycle.values()
            if isinstance(row, Mapping)
        ) == volume_attestation_digests
    )
    inventory_valid = bool(
        isinstance(inventory_facts, Mapping)
        and inventory_facts.get("source_destroyed_observed") is True
        and inventory_facts.get("target_absent") is True
        and inventory_facts.get("container_count") == 4
        and container_roles == {"copy": 1, "custodian": 1, "source": 1, "verify": 1}
        and mount_witnesses_valid
        and inventory_facts.get("writable_mount_count") == 2
        and inventory_facts.get("all_container_lifecycles_complete") is True
        and inventory_facts.get("all_writable_mounts_detached") is True
        and inventory_facts.get("live_run_container_count") == 0
        and inventory_facts.get("live_writable_helper_mount_count") == 0
        and inventory_facts.get("pending_create_intent_count") == 0
        and inventory_facts.get("volume_count") == 2
        and volume_roles == {"source-state": 1, "target-state": 1}
        and isinstance(inventory_facts.get("container_identity_digests"), list)
        and len(inventory_facts["container_identity_digests"]) == 4
        and all(re.fullmatch(r"[0-9a-f]{64}", str(value))
                for value in inventory_facts["container_identity_digests"])
        and isinstance(inventory_facts.get("volume_identity_digests"), list)
        and len(inventory_facts["volume_identity_digests"]) == 2
        and all(re.fullmatch(r"[0-9a-f]{64}", str(value))
                for value in inventory_facts["volume_identity_digests"])
        and isinstance(inventory_facts.get("volume_attestation_digests"), list)
        and len(inventory_facts["volume_attestation_digests"]) == 2
        and len(set(inventory_facts["volume_attestation_digests"])) == 2
        and all(re.fullmatch(r"[0-9a-f]{64}", str(value))
                for value in inventory_facts["volume_attestation_digests"])
        and volume_lifecycle_valid
    )
    if (not seed_binding_valid
            or not isinstance(custody_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", custody_digest)
            or not isinstance(custody_facts, Mapping)
            or _digest(custody_facts) != custody_digest
            or not history_valid
            or launch_payload.get("pre_release_history_custody_digest") != custody_digest
            or not isinstance(inventory_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", inventory_digest)
            or not isinstance(inventory_summary, Mapping)
            or inventory_summary.get("inventory_digest") != inventory_digest
            or not isinstance(inventory_facts, Mapping)
            or _digest(inventory_facts) != inventory_digest
            or not inventory_valid
            or launch_payload.get("pre_release_engine_inventory_digest") != inventory_digest
            or not isinstance(mount_witnesses_digest, str)
            or release_payload.get("pre_release_mount_witnesses_digest") != mount_witnesses_digest
            or launch_payload.get("pre_release_mount_witnesses_digest") != mount_witnesses_digest):
        raise RuntimeError(
            "release intent lacks bound pre-release history and engine inventory or native task seed"
        )
    require_release = getattr(observe, "require_explicit_release", None)
    if not callable(require_release):
        raise RuntimeError("release intent lacks an external pre-release gate")
    require_release(inventory_digest=inventory_digest)
    release_digest = ledger.persist("release", release_payload)
    observe("explicit-release-persisted", parent_uuid, {"digest": release_digest})
    launch_record = dict(launch_payload)
    launch_record["release_digest"] = release_digest
    launch_digest = ledger.persist("target-launch", launch_record)
    observe("target-launch-intent", target_identity, {"digest": launch_digest})
    return release_digest, launch_digest


def _create_authorized_target(
    observer: TwoDomainObserver,
    *,
    tracker: dict[str, object] | None = None,
    **kwargs: object,
) -> str:
    observer.authorize_target_create()
    target_id = _create_container(
        observer=observer, **kwargs,  # type: ignore[arg-type]
    )
    if tracker is not None:
        tracker.setdefault("containers", []).append({
            "name": kwargs.get("name"), "id": target_id, "role": "target",
            "removed": False, "stop_intent_persisted": False,
            "remove_intent_persisted": False,
        })
        tracker["target_container_id"] = target_id
        tracker.setdefault("private_values", []).append(target_id)
        for row in tracker.get("planned_containers", []):
            if isinstance(row, dict) and row.get("role") == "target":
                row["id"] = target_id
    observer.wait_engine_event(
        kind="container", action="create", identity=target_id,
    )
    observer("target-container-created", target_id, {
        "container_id_digest": _digest(target_id),
    })
    return target_id


def _seal_arm_result(
    ledger: probe.TwoDomainIntentLedger,
    result: Mapping[str, object],
    observer: TwoDomainObserver,
) -> str:
    """Fsync sanitized findings before deleting any verified state volume."""

    payload = dict(result)
    payload.pop("private_parent_uuid", None)
    payload["observer_events"] = observer.report()
    digest_value = ledger.persist("arm-result", payload)
    return digest_value


def _remember_normal_arm_disposition(
    result: Mapping[str, object], tracker: dict[str, object],
) -> None:
    """Keep a classified result available if later durability/observer work fails."""

    status = result.get("status")
    if status not in {"observed", "fail", "inconclusive"}:
        return
    tracker["normal_arm_status"] = status
    raw_reasons = result.get("reason_codes")
    tracker["normal_arm_reason_codes"] = sorted({
        value for value in raw_reasons
        if isinstance(value, str) and value
    }) if isinstance(raw_reasons, list) else []


def _finalize_normal_arm_result(
    result: dict[str, object],
    *,
    ledger: probe.TwoDomainIntentLedger,
    observer: TwoDomainObserver,
    tracker: dict[str, object],
    run_id: str,
    source_volume: str,
    target_volume: str,
    observe: object,
) -> None:
    """Persist an arm result, retaining all volumes unless it was observed."""

    _remember_normal_arm_disposition(result, tracker)
    status = result.get("status")
    if status in {"fail", "inconclusive"}:
        tracker["custody_complete"] = False
        result["cleanup_complete"] = False
        result["leftovers"] = _possible_leftovers(tracker)
        tracker["normal_arm_failure_stage"] = "arm-result-persistence"
        result["arm_result_digest"] = _seal_arm_result(ledger, result, observer)
        tracker["normal_arm_failure_stage"] = "arm-result-observer-record"
        observe("final-custody-result-persisted", facts={
            "digest": result["arm_result_digest"],
        })
        tracker.pop("normal_arm_failure_stage", None)
        return
    if status != "observed":
        raise RuntimeError("normal two-domain arm result status is invalid")

    tracker["custody_complete"] = True
    tracker["normal_arm_failure_stage"] = "arm-result-persistence"
    result["arm_result_digest"] = _seal_arm_result(ledger, result, observer)
    tracker["normal_arm_failure_stage"] = "arm-result-observer-record"
    observe("final-custody-result-persisted", facts={
        "digest": result["arm_result_digest"],
    })
    tracker["normal_arm_failure_stage"] = "volume-cleanup"
    _remove_run_volumes(
        ledger, run_id=run_id, source_volume=source_volume,
        target_volume=target_volume, observe=observe,
        custody_complete=True,
    )
    ledger.persist("cleanup-complete", {
        "run_id": run_id, "source_volume_removed": True,
        "target_volume_removed": True,
        "arm_result_digest": result["arm_result_digest"],
    })
    tracker["source_volume_removed"] = True
    tracker["target_volume_removed"] = True
    tracker["target_container_removed"] = True
    result["cleanup_complete"] = True
    tracker.pop("normal_arm_failure_stage", None)


def _final_custody_assessment(report: Mapping[str, object]) -> dict[str, object]:
    """Classify final byte custody without treating missing evidence as mismatch."""

    source = report.get("source")
    source = source if isinstance(source, Mapping) else {}
    target = report.get("target")
    target = target if isinstance(target, Mapping) else {}
    source_edit = source.get("saved_edit_sha256")
    target_edit = target.get("saved_edit_sha256")
    edit_evidence = bool(
        isinstance(source_edit, str) and re.fullmatch(r"[0-9a-f]{64}", source_edit)
        and isinstance(target_edit, str) and re.fullmatch(r"[0-9a-f]{64}", target_edit)
    )
    reasons: list[str] = []
    failures: list[str] = []
    saved_edit_retained = False
    if edit_evidence:
        if source_edit != target_edit:
            failures.append("saved-edit-not-retained")
        else:
            saved_edit_retained = True
    else:
        reasons.append("saved-edit-custody-incomplete")

    candidates = report.get("identity_linked_parent_history_candidate_count")
    binding_valid = report.get("identity_linked_parent_history_binding_valid") is True
    history_size = report.get("identity_linked_history_size")
    history_digest = report.get("identity_linked_history_sha256")
    history_identity_available = bool(
        type(candidates) is int and candidates == 1 and binding_valid
        and type(history_size) is int and history_size > 0
        and isinstance(history_digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", history_digest)
    )
    prefix_retained = report.get("identity_linked_parent_history_prefix_retained")
    if history_identity_available:
        if prefix_retained is False:
            failures.append("source-history-prefix-not-retained")
        elif prefix_retained is not True:
            reasons.append("identity-linked-history-custody-incomplete")
    else:
        reasons.append("identity-linked-history-evidence-incomplete")

    status = "fail" if failures else (
        "observed" if not reasons else "inconclusive"
    )
    return {
        "status": status,
        "reason_codes": sorted(set(failures or reasons)),
        "saved_edit_evidence_available": edit_evidence,
        "saved_edit_retained": saved_edit_retained,
        "identity_linked_history_evidence_available": history_identity_available,
        "identity_linked_history_prefix_retained": prefix_retained is True,
    }


def _negative_arm_disposition(
    *, refused: bool, no_target: bool, final_report: Mapping[str, object],
) -> dict[str, object]:
    custody = _final_custody_assessment(final_report)
    reasons: list[str] = []
    if not refused:
        reasons.append("unknown-effect-refusal-not-proven")
    if not no_target:
        reasons.append("target-created-despite-negative-release")
    if custody["status"] == "fail":
        reasons.extend(str(value) for value in custody["reason_codes"])
    elif custody["status"] != "observed":
        reasons.extend(str(value) for value in custody["reason_codes"])

    if not no_target or custody["status"] == "fail":
        status = "fail"
    elif refused and custody["status"] == "observed":
        status = "observed"
    else:
        status = "inconclusive"
    if status == "observed":
        reasons = []
    return {
        "status": status,
        "reason_codes": sorted(set(reasons)),
        "final_custody_assessment": custody,
    }


def _release_candidate_reasons(
    source_report: Mapping[str, object],
    source_manifest: Mapping[str, object],
    copy_report: Mapping[str, object],
    pre_release_history: Mapping[str, object],
    source_native_seed: Mapping[str, object] | None = None,
) -> list[str]:
    source = source_report.get("source")
    source = source if isinstance(source, Mapping) else {}
    store = source.get("store")
    store = store if isinstance(store, Mapping) else {}
    reasons: list[str] = []
    if (not isinstance(source_native_seed, Mapping)
            or source_native_seed.get("status") != "available"):
        reasons.append("source-native-task-terminal-seed-unavailable")
    if source_report.get("parent_uuid_seen") is not True:
        reasons.append("source-parent-uuid-missing")
    if source.get("source_parent_process_exited") is not True:
        reasons.append("source-parent-exit-unobserved")
    if source.get("active_fixture_observed") is not True:
        reasons.append("source-active-fixture-unobserved")
    if int(source.get("tracked_fixture_process_count", 0)) < 1:
        reasons.append("source-tracked-writer-unobserved")
    if source.get("tracked_processes_excluded") is not True:
        reasons.append("source-tracked-writer-exclusion-unobserved")
    if source.get("identity_linked_parent_history_observed") is not True:
        reasons.append("source-parent-history-not-identity-linked")
    history = source.get("history_evidence")
    history = history if isinstance(history, Mapping) else {}
    parent_history = history.get("parent")
    parent_history = parent_history if isinstance(parent_history, Mapping) else {}
    if (parent_history.get("status") != "observed"
            or parent_history.get("attribution") != "observed"
            or type(parent_history.get("size")) is not int
            or int(parent_history.get("size", 0)) < 1
            or not isinstance(parent_history.get("content_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", str(parent_history.get("content_sha256")))):
        reasons.append("source-parent-history-fingerprint-unavailable")
    if _parent_history_prefix(source_report) is None:
        reasons.append("source-parent-history-prefix-unavailable")
    if source.get("read_failed") is not False or int(source.get("unparsed_frames", -1)) != 0:
        reasons.append("source-observation-incomplete")
    if source.get("protocol_errors"):
        reasons.append("source-gateway-protocol-error")
    if source.get("v1_release_candidate_ready") is not True:
        reasons.append("source-v1-release-candidate-not-ready")
    if source.get("v1_unknown_effect_baseline_valid") is not True:
        reasons.append("source-unknown-effect-baseline-not-valid")
    if source.get("v1_unknown_effects"):
        reasons.append("source-unknown-effects-present")
    if (int(store.get("file_count", 0)) < 1
            or store.get("transcript_record_seen") is not True):
        reasons.append("source-sdk-history-not-observed")
    if int(source_manifest.get("history_jsonl_count", 0)) < 1:
        reasons.append("source-jsonl-history-candidate-missing")
    if source_manifest.get("saved_edit_sha256") != source_report.get("saved_edit_sha256"):
        reasons.append("source-saved-edit-hash-mismatch")
    if copy_report.get("exact_match") is not True:
        reasons.append("source-target-copy-not-exact")
    if (not isinstance(source_manifest.get("manifest_digest"), str)
            or not isinstance(copy_report.get("target"), Mapping)
            or copy_report["target"].get("manifest_digest") != source_manifest.get("manifest_digest")):
        reasons.append("source-target-manifest-binding-mismatch")
    reasons.extend(_pre_release_history_reasons(pre_release_history))
    return sorted(set(reasons))


def _source_projection(source: Mapping[str, object]) -> dict[str, object]:
    store = source.get("store")
    store = store if isinstance(store, Mapping) else {}
    history = source.get("history_evidence")
    history = history if isinstance(history, Mapping) else {}
    parent = history.get("parent")
    parent = parent if isinstance(parent, Mapping) else {}
    child = history.get("child")
    child = child if isinstance(child, Mapping) else {}
    lifecycle = source.get("native_task_lifecycle_summary")
    lifecycle = lifecycle if isinstance(lifecycle, Mapping) else {}
    hooks = source.get("native_hook_summary")
    hooks = hooks if isinstance(hooks, Mapping) else {}
    lifecycle_reasons = lifecycle.get("unknown_reasons")
    lifecycle_reasons = [
        value for value in lifecycle_reasons
        if isinstance(value, str)
    ][:64] if isinstance(lifecycle_reasons, list) else []
    hook_reasons = hooks.get("unknown_reasons")
    hook_reasons = [
        value for value in hook_reasons
        if isinstance(value, str)
    ][:probe.MAX_NATIVE_TASK_EVIDENCE] if isinstance(hook_reasons, list) else []

    def bounded_hook_count(
        name: str,
        maximum: int = probe.MAX_NATIVE_HOOK_EVIDENCE,
    ) -> int | None:
        value = hooks.get(name)
        if type(value) is int and 0 <= value <= maximum:
            return value
        return None

    started_tool_seen = hooks.get("started_task_tool_use_id_seen")
    if type(started_tool_seen) is not bool:
        started_tool_seen = None
    return {
        "source_parent_process_exited": source.get("source_parent_process_exited") is True,
        "active_fixture_observed": source.get("active_fixture_observed") is True,
        "tracked_fixture_process_count": source.get("tracked_fixture_process_count"),
        "tracked_processes_excluded": source.get("tracked_processes_excluded") is True,
        "identity_linked_parent_history_observed": (
            source.get("identity_linked_parent_history_observed") is True
        ),
        "history_evidence": source.get("history_evidence"),
        "history_parent_status": parent.get("status"),
        "history_parent_attribution": parent.get("attribution"),
        "history_child_status": child.get("status"),
        "history_child_attribution": child.get("attribution"),
        "history_file_count": store.get("file_count"),
        "history_transcript_record_seen": store.get("transcript_record_seen") is True,
        "v1_release_candidate_ready": source.get("v1_release_candidate_ready") is True,
        "v1_unknown_effect_baseline_valid": (
            source.get("v1_unknown_effect_baseline_valid") is True
        ),
        "read_failed": source.get("read_failed") is True,
        "unparsed_frames": source.get("unparsed_frames"),
        "protocol_error_count": len(source.get("protocol_errors", []))
        if isinstance(source.get("protocol_errors"), list) else None,
        "native_task_terminal_seed_status": source.get("native_task_terminal_seed_status"),
        "native_task_terminal_seed_digest": source.get("native_task_terminal_seed_digest"),
        "native_task_terminal_seed_reason_code": source.get(
            "native_task_terminal_seed_reason_code"
        ),
        "native_task_lifecycle_summary": {
            "record_schema": lifecycle.get("record_schema"),
            "observation_status": lifecycle.get("observation_status"),
            "event_count": lifecycle.get("event_count"),
            "observation_sequence_max": lifecycle.get(
                "observation_sequence_max"
            ),
            "overflow": lifecycle.get("overflow") is True,
            "incomplete": lifecycle.get("incomplete") is True,
            "seed_provenance": lifecycle.get("seed_provenance"),
            "source_terminal_seed_index": lifecycle.get(
                "source_terminal_seed_index"
            ),
            "unknown_reasons": lifecycle_reasons,
            "support_claim": False,
        },
        "native_hook_summary": {
            "record_schema": hooks.get("record_schema"),
            "observed_count": bounded_hook_count(
                "observed_count", probe.MAX_NATIVE_HOOK_REQUESTS
            ),
            "stored_count": bounded_hook_count("stored_count"),
            "request_count": bounded_hook_count(
                "request_count", probe.MAX_NATIVE_HOOK_REQUESTS
            ),
            "request_limit": (
                probe.MAX_NATIVE_HOOK_REQUESTS
                if hooks.get("request_limit") == probe.MAX_NATIVE_HOOK_REQUESTS
                else None
            ),
            "request_overflow": hooks.get("request_overflow") is True,
            "overflow": hooks.get("overflow") is True,
            "joined_count": bounded_hook_count("joined_count"),
            "unresolved_count": bounded_hook_count("unresolved_count"),
            "started_task_event_count": bounded_hook_count(
                "started_task_event_count", probe.MAX_NATIVE_TASK_EVIDENCE
            ),
            "started_task_tool_use_id_seen": started_tool_seen,
            "session_matched_hook_count": bounded_hook_count(
                "session_matched_hook_count"
            ),
            "hook_tool_use_id_seen_count": bounded_hook_count(
                "hook_tool_use_id_seen_count"
            ),
            "hook_tool_use_id_missing_count": bounded_hook_count(
                "hook_tool_use_id_missing_count"
            ),
            "same_task_hook_count": bounded_hook_count("same_task_hook_count"),
            "same_task_tool_use_id_missing_count": bounded_hook_count(
                "same_task_tool_use_id_missing_count"
            ),
            "same_task_tool_use_id_mismatch_count": bounded_hook_count(
                "same_task_tool_use_id_mismatch_count"
            ),
            "exact_task_tool_link_candidate_count": bounded_hook_count(
                "exact_task_tool_link_candidate_count"
            ),
            "rejected_tool_use_id_conflict_count": bounded_hook_count(
                "rejected_tool_use_id_conflict_count",
                probe.MAX_NATIVE_HOOK_REQUESTS,
            ),
            "rejected_tool_use_id_mismatch_count": bounded_hook_count(
                "rejected_tool_use_id_mismatch_count",
                probe.MAX_NATIVE_HOOK_REQUESTS,
            ),
            "unknown_reasons": hook_reasons,
            "support_claim": False,
        },
    }


def _parent_history_record(source: Mapping[str, object]) -> Mapping[str, object] | None:
    evidence = source.get("history_evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    parent = evidence.get("parent")
    return parent if isinstance(parent, Mapping) else None


def _parent_history_prefix(source_report: Mapping[str, object]) -> bytes | None:
    source = source_report.get("source")
    source = source if isinstance(source, Mapping) else {}
    evidence = _parent_history_record(source)
    handoff = source_report.get("private_handoff")
    handoff = handoff if isinstance(handoff, Mapping) else {}
    encoded = handoff.get("parent_history_prefix_b64")
    if (not isinstance(evidence, Mapping) or not isinstance(encoded, str)
            or len(encoded) > ((probe.MAX_HISTORY_CONTENT_BYTES + 2) // 3) * 4):
        return None
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return None
    if (not 0 < len(raw) <= probe.MAX_HISTORY_CONTENT_BYTES
            or len(raw) != evidence.get("size")
            or hashlib.sha256(raw).hexdigest() != evidence.get("content_sha256")):
        return None
    return raw


def _negative_release_diagnostic(
    workspace: Path,
    *,
    binding_digest: str,
) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{64}", binding_digest):
        raise RuntimeError("negative refusal binding digest is malformed")
    # This reads the prepared source ledger copied byte-for-byte into the
    # target fixture. It must already represent a valid source baseline before
    # this negative-only injected effect is added.
    ledger = probe.StopThenResumeV1Ledger(workspace)
    before = ledger.snapshot()
    if not before or before.get("unknown_effect_baseline_valid") is not True:
        raise RuntimeError("copied source ledger lacks a valid prepared baseline")
    refusal = ledger.request_release(explicit=True, unknown_effect=True)
    after = ledger.snapshot()
    return {
        "schema": "openrepotools-bite4-negative-refusal/v1",
        "binding_digest": binding_digest,
        "explicit_release_selected": True,
        "baseline_valid": before.get("unknown_effect_baseline_valid") is True,
        "unknown_effects": list(after.get("unknown_effects", [])),
        "release_requested": bool(refusal.get("release_requested")),
        "authorized": bool(refusal.get("authorized")),
        "release_persisted": bool(refusal.get("release_persisted")),
        "target_creation_authorized": bool(refusal.get("target_creation_authorized")),
        "reason_code": refusal.get("reason_code"),
        "unknown_effect_refusal_demonstrated": bool(
            after.get("unknown_effect_refusal_demonstrated")
        ),
    }


def _run_arm_impl(
    *,
    arm: str,
    run_id: str,
    token: str,
    image_id: str,
    cli_path: str,
    selected: Mapping[str, object],
    private_dir: Path,
    ledger: probe.TwoDomainIntentLedger,
    tracker: dict[str, object],
    observe: object,
) -> dict[str, object]:
    if arm not in {"positive", "negative"}:
        raise ValueError("unknown two-domain arm")
    source_volume = "opentools-b4-s-" + token
    target_volume = "opentools-b4-t-" + token
    source_name = "opentools-b4-source-" + token
    tracker.update({
        "run_id": run_id,
        "source_volume": source_volume,
        "target_volume": target_volume,
        "source_name": source_name,
        "target_name": "opentools-b4-target-" + token,
        "containers": [],
        "custody_complete": False,
    })
    tracker.setdefault("planned_containers", [])
    tracker["planned_containers"].extend([
        {"name": source_name, "id": None, "role": "source", "removed": False},
        {"name": tracker["target_name"], "id": None, "role": "target", "removed": False},
    ])
    source_invocation = "fixture-source-" + uuid.uuid4().hex
    fixture_ids = {
        "owner": "fixture-owner-" + uuid.uuid4().hex,
        "lineage": "fixture-lineage-" + uuid.uuid4().hex,
        "runner": "fixture-runner-" + uuid.uuid4().hex,
        "daemon": "fixture-daemon-" + uuid.uuid4().hex,
    }
    tracker.setdefault("private_values", []).extend(
        [source_invocation, *fixture_ids.values(), source_name,
         tracker["target_name"], source_volume, target_volume]
    )
    source_volume = _volume_create(
        source_volume, run_id, "source-state", observer=observe,
    )
    tracker["source_volume"] = source_volume
    tracker.setdefault("private_values", []).append(source_volume)
    source_volume_record = _validate_new_volume(source_volume, run_id, "source-state")
    observe("source-volume-validated", source_volume, {
        "digest": _digest({
            "driver": source_volume_record.get("Driver"),
            "scope": source_volume_record.get("Scope"),
            "options": source_volume_record.get("Options"),
        }),
    })
    observe.wait_engine_event(
        kind="volume", action="create", identity=source_volume,
    )
    observe("source-volume-created", source_volume, {"arm": arm})

    source_id = _create_container(
        image_id=image_id,
        run_id=run_id,
        role="source",
        name=source_name,
        volume_mounts={STATE_ROOT: (source_volume, True)},
        observer=observe,
    )
    tracker["containers"].append({
        "name": source_name, "id": source_id, "role": "source", "removed": False,
        "stop_intent_persisted": False, "remove_intent_persisted": False,
    })
    for row in tracker.get("planned_containers", []):
        if isinstance(row, dict) and row.get("role") == "source":
            row["id"] = source_id
    observe.wait_engine_event(
        kind="container", action="create", identity=source_id,
    )
    tracker["source_container_id"] = source_id
    tracker.setdefault("private_values", []).extend([source_id, source_name])
    observe("source-container-created", source_id, {"arm": arm})
    _install_observer_files(
        source_id, cli_path, run_id=run_id, role="source",
        image_id=image_id, private_dir=private_dir, observer=observe,
        expected_mounts=_expected_mounts({STATE_ROOT: (source_volume, True)}),
        tracker=tracker,
    )
    observe.wait_engine_event(
        kind="container", action="start", identity=source_id,
    )
    if _container_role_exists(run_id, "target"):
        raise RuntimeError("target container exists before source release")

    source_stop_digest = ledger.persist("source-stop", {
        "run_id": run_id,
        "arm": arm,
        "source_invocation": source_invocation,
        "source_container_id": source_id,
        "source_volume": source_volume,
        "fixture_ids": fixture_ids,
        "effect": "bounded-source-interrupt-and-exclusion",
    })
    observe("source-stop-intent", source_id, {"digest": source_stop_digest})
    expected = dict(selected)
    expected.pop("selected_cli", None)
    expected.update({
        "mode": probe.STOP_THEN_RESUME_V1,
        "control_mode": "interrupt",
        "release_target": False,
        "explicit_release": False,
        "unknown_effect": False,
        "observe_native_hooks": True,
        "control_entry_before_settle": False,
        "busy_parent_before_control": False,
        "two_domain_phase": "source",
        "state_root": STATE_ROOT,
        "source_invocation": source_invocation,
        "fixture_owner": fixture_ids["owner"],
        "fixture_lineage": fixture_ids["lineage"],
        "fixture_runner": fixture_ids["runner"],
        "fixture_daemon": fixture_ids["daemon"],
        "source_container_label": probe.digest(source_id),
    })
    _require_mount_witness_ready(tracker, observe, source_id)
    source_report = _runtime_exec(source_id, expected)
    _persist_and_validate_source_runtime_report(
        source_report,
        source_invocation=source_invocation,
        source_container_id=source_id,
        private_dir=private_dir,
        tracker=tracker,
    )
    _mount_witness_session(tracker, source_id).check_alive()
    observe("source-phase-returned", source_id, {
        "source_report_digest": _digest(source_report),
        "target_code_reached": source_report.get("target_code_reached"),
    })

    state = _container_state(source_id)
    source_container_stop_digest = ledger.persist("source-container-stop", {
        "run_id": run_id,
        "source_container_id": source_id,
        "source_container_id_digest": _digest(source_id),
        "observed_running_after_source_phase": state.get("Running"),
    })
    for row in tracker["containers"]:
        if isinstance(row, dict) and row.get("id") == source_id:
            row["stop_intent_persisted"] = True
    observe("source-container-stop-intent", source_id, {
        "digest": source_container_stop_digest,
    })
    _docker("stop", "--time", "10", source_id, timeout=20)
    observe.wait_engine_event(kind="container", action="die", identity=source_id)
    stopped_state = _container_state(source_id)
    if stopped_state.get("Running") is not False:
        raise RuntimeError("source container stop was not observed")
    _reap_mount_witness_after_stop(tracker, source_id, observe)
    observe("source-container-stopped", source_id, {
        "exit_code": stopped_state.get("ExitCode"),
        "oom_killed": stopped_state.get("OOMKilled"),
    })
    source_remove_digest = ledger.persist("source-remove", {
        "run_id": run_id,
        "source_container_id": source_id,
        "source_container_id_digest": _digest(source_id),
        "source_stop_intent_digest": source_stop_digest,
        "container_stop_intent_digest": source_container_stop_digest,
    })
    for row in tracker["containers"]:
        if isinstance(row, dict) and row.get("id") == source_id:
            row["remove_intent_persisted"] = True
    _docker("rm", source_id, timeout=20)
    if not _container_absent(source_id):
        raise RuntimeError("source container removal was not observed")
    observe.wait_engine_event(kind="container", action="destroy", identity=source_id)
    for row in tracker["containers"]:
        if isinstance(row, dict) and row.get("id") == source_id:
            row["removed"] = True
    for row in tracker.get("planned_containers", []):
        if isinstance(row, dict) and row.get("role") == "source":
            row["id"] = source_id
            row["removed"] = True
    source_removal_digest = _digest({
        "source_remove_intent_digest": source_remove_digest,
        "container_id_digest": _digest(source_id),
        "running_after_stop": stopped_state.get("Running"),
        "exit_code": stopped_state.get("ExitCode"),
        "absent_after_remove": True,
    })
    observe("source-container-removed", source_id, {
        "source_removal_digest": source_removal_digest,
    })
    # The target fixture volume does not exist until source removal and its
    # exclusion observation have both completed.
    target_volume = _volume_create(
        target_volume, run_id, "target-state", observer=observe,
    )
    tracker["target_volume"] = target_volume
    tracker.setdefault("private_values", []).append(target_volume)
    target_volume_record = _validate_new_volume(target_volume, run_id, "target-state")
    observe("target-volume-validated", target_volume, {
        "digest": _digest({
            "driver": target_volume_record.get("Driver"),
            "scope": target_volume_record.get("Scope"),
            "options": target_volume_record.get("Options"),
        }),
    })
    observe.wait_engine_event(
        kind="volume", action="create", identity=target_volume,
    )
    observe("target-volume-created", target_volume, {"arm": arm})
    copy_report = _run_custodian(
        image_id=image_id, run_id=run_id, role="copy", operation="copy",
        source_volume=source_volume, target_volume=target_volume,
        private_dir=private_dir, observe=observe, tracker=tracker,
    )
    source_manifest = copy_report.get("source")
    source_manifest = source_manifest if isinstance(source_manifest, Mapping) else {}
    verify_report = _run_custodian(
        image_id=image_id, run_id=run_id, role="verify", operation="verify",
        source_volume=source_volume, target_volume=target_volume,
        private_dir=private_dir, observe=observe, tracker=tracker,
    )
    if verify_report.get("exact_match") is not True:
        raise KnownViolation("source-target-copy-mismatch")
    observe("source-copy-verified", source_volume, {
        "manifest_digest": (copy_report.get("target") or {}).get("manifest_digest"),
        "exact_match": True,
    })
    source_observation = source_report.get("source")
    source_observation = source_observation if isinstance(source_observation, Mapping) else {}
    pre_release_history = _run_custodian(
        image_id=image_id, run_id=run_id, role="custodian",
        operation="pre-release", source_volume=source_volume,
        target_volume=target_volume, private_dir=private_dir, observe=observe,
        tracker=tracker,
        parent_history=_parent_history_record(source_observation),
        parent_history_prefix=_parent_history_prefix(source_report),
    )
    if pre_release_history.get("pre_release_history_custody_valid") is True:
        observe("pre-release-history-custody-verified", source_volume, {
            "digest": _digest(pre_release_history),
            "exact_match": True,
        })
    pre_release_inventory = observe.verify_pre_release_inventory(
        run_id=run_id, source_volume=source_volume, target_volume=target_volume,
    )
    private_handoff = source_report.get("private_handoff")
    private_handoff = private_handoff if isinstance(private_handoff, Mapping) else {}
    parent_uuid = private_handoff.get("parent_uuid")
    source_native_seed = _validated_source_native_task_seed(
        source_report, parent_uuid=parent_uuid,
    )
    gate_reasons = _release_candidate_reasons(
        source_report, source_manifest, copy_report, pre_release_history,
        source_native_seed,
    )
    if not isinstance(parent_uuid, str) or not parent_uuid:
        gate_reasons = sorted(set(gate_reasons + ["private-exact-parent-unavailable"]))
    else:
        tracker.setdefault("private_values", []).append(parent_uuid)
    if gate_reasons:
        final_report = _run_custodian(
            image_id=image_id, run_id=run_id, role="custodian", operation="final",
            source_volume=source_volume, target_volume=target_volume,
            private_dir=private_dir, observe=observe, tracker=tracker,
            parent_history=_parent_history_record(source_observation),
            parent_history_prefix=_parent_history_prefix(source_report),
        )
        known_reasons = {
            "source-gateway-protocol-error",
            "source-saved-edit-hash-mismatch",
            "source-target-copy-not-exact",
            "source-target-manifest-binding-mismatch",
            "source-unknown-effects-present",
            "pre-release-linked-history-copy-mismatch",
        }
        known = sorted(set(gate_reasons).intersection(known_reasons))
        arm_status = "fail" if known else "inconclusive"
        result = {
            "arm": arm,
            "status": arm_status,
            "reason_codes": known or gate_reasons,
            "target_container_created": False,
            "source_report_digest": source_report.get("source_phase_report_digest"),
            "source": _source_projection(source_observation),
            "copy_exact": copy_report.get("exact_match"),
            "source_manifest_digest": source_manifest.get("manifest_digest"),
            "pre_release_history_custody_digest": _digest(pre_release_history),
            "pre_release_history_custody": dict(pre_release_history),
            "final_custody": final_report,
            "support_claim": False,
            "release_candidate_ready": False,
        }
        _remember_normal_arm_disposition(result, tracker)
        for row in tracker.get("planned_containers", []):
            if isinstance(row, dict) and row.get("role") == "target":
                row["removed"] = True
        tracker["normal_arm_failure_stage"] = "arm-lifecycle-verification"
        observe.verify_lifecycle(volumes_removed=False)
        _finalize_normal_arm_result(
            result, ledger=ledger, observer=observe, tracker=tracker,
            run_id=run_id, source_volume=source_volume,
            target_volume=target_volume, observe=observe,
        )
        return result

    assert isinstance(parent_uuid, str) and parent_uuid
    target_profile, target_spec_fingerprint = _target_spec(
        selected=selected,
        parent_uuid=parent_uuid,
        image_id=image_id,
        state_volume=target_volume,
        source_phase_report_digest=str(source_report.get("source_phase_report_digest")),
        source_invocation_digest=str(probe.digest(source_report.get("source_invocation"))),
        native_task_source_seed=source_native_seed,
    )
    if arm == "negative":
        binding_digest = _digest({
            "run_id": run_id,
            "source_invocation": source_invocation,
            "fixture_ids": fixture_ids,
            "source_removal_digest": source_removal_digest,
            "source_manifest_digest": source_manifest.get("manifest_digest"),
            "pre_release_history_custody_digest": _digest(pre_release_history),
            "pre_release_engine_inventory_digest": pre_release_inventory.get("inventory_digest"),
            "pre_release_mount_witnesses_digest": pre_release_inventory.get(
                "container_mount_witnesses_digest"
            ),
            "target_spec_fingerprint": target_spec_fingerprint,
            "parent_uuid_digest": probe.digest(parent_uuid),
            "explicit_release_selected": True,
        })
        refusal_intent_digest = ledger.persist("negative-refusal", {
            "run_id": run_id,
            "arm": arm,
            "explicit_release_selected": True,
            "baseline_gates_valid": True,
            "injected_unknown_effect": "fixture-unknown-effect",
            "source_invocation": source_invocation,
            "fixture_ids": fixture_ids,
            "source_removal_digest": source_removal_digest,
            "source_manifest_digest": source_manifest.get("manifest_digest"),
            "target_spec_fingerprint": target_spec_fingerprint,
            "pre_release_history_custody_digest": _digest(pre_release_history),
            "pre_release_engine_inventory_digest": pre_release_inventory.get("inventory_digest"),
            "pre_release_mount_witnesses_digest": pre_release_inventory.get(
                "container_mount_witnesses_digest"
            ),
            "parent_uuid": parent_uuid,
            "binding_digest": binding_digest,
        })
        observe("unknown-effect-refusal-intent", parent_uuid, {
            "digest": refusal_intent_digest,
        })
        refusal = _run_custodian(
            image_id=image_id, run_id=run_id, role="custodian",
            operation="negative-release", source_volume=source_volume,
            target_volume=target_volume, private_dir=private_dir, observe=observe,
            tracker=tracker, binding_digest=binding_digest,
        )
        refused = (
            refusal.get("explicit_release_selected") is True
            and refusal.get("binding_digest") == binding_digest
            and refusal.get("baseline_valid") is True
            and refusal.get("authorized") is False
            and refusal.get("release_persisted") is False
            and refusal.get("target_creation_authorized") is False
            and refusal.get("reason_code") == "unknown-effects"
            and refusal.get("unknown_effect_refusal_demonstrated") is True
        )
        no_target = not _container_role_exists(run_id, "target")
        if no_target:
            for row in tracker.get("planned_containers", []):
                if isinstance(row, dict) and row.get("role") == "target":
                    row["removed"] = True
        if refused and no_target:
            observe("unknown-effect-refusal-confirmed", parent_uuid, {
                "digest": refusal_intent_digest,
                "reason_code": "unknown-effects",
            })
        final_report = _run_custodian(
            image_id=image_id, run_id=run_id, role="custodian", operation="final",
            source_volume=source_volume, target_volume=target_volume,
            private_dir=private_dir, observe=observe, tracker=tracker,
            parent_history=_parent_history_record(source_observation),
            parent_history_prefix=_parent_history_prefix(source_report),
        )
        disposition = _negative_arm_disposition(
            refused=refused, no_target=no_target, final_report=final_report,
        )
        result = {
            "arm": arm,
            "status": disposition["status"],
            "reason_codes": disposition["reason_codes"],
            "source_report_digest": source_report.get("source_phase_report_digest"),
            "source": _source_projection(source_observation),
            "source_manifest_digest": source_manifest.get("manifest_digest"),
            "pre_release_history_custody_digest": _digest(pre_release_history),
            "pre_release_engine_inventory_digest": pre_release_inventory.get("inventory_digest"),
            "pre_release_engine_inventory": pre_release_inventory,
            "target_spec_fingerprint": target_spec_fingerprint,
            "explicit_release_selected": refusal.get("explicit_release_selected"),
            "injected_unknown_effect": refusal.get("unknown_effects"),
            "release_refused": refused,
            "negative_refusal_binding_digest": binding_digest,
            "target_container_created": not no_target,
            "final_custody": final_report,
            "final_custody_assessment": disposition["final_custody_assessment"],
            "support_claim": False,
            "release_candidate_ready": disposition["status"] == "observed",
        }
        _remember_normal_arm_disposition(result, tracker)
        tracker["normal_arm_failure_stage"] = "arm-lifecycle-verification"
        observe.verify_lifecycle(volumes_removed=False)
        _finalize_normal_arm_result(
            result, ledger=ledger, observer=observe, tracker=tracker,
            run_id=run_id, source_volume=source_volume,
            target_volume=target_volume, observe=observe,
        )
        return result

    if _container_role_exists(run_id, "target"):
        raise KnownViolation("duplicate-target-before-release")
    release_payload = {
        "run_id": run_id,
        "arm": arm,
        "explicit_release_selected": True,
        "source_invocation": source_invocation,
        "source_invocation_digest": probe.digest(source_invocation),
        "source_phase_report_digest": source_report.get("source_phase_report_digest"),
        "native_task_source_terminal_seed": dict(source_native_seed),
        "native_task_source_terminal_seed_digest": source_native_seed.get("seed_digest"),
        "parent_uuid_digest": probe.digest(parent_uuid),
        "source_container_id_digest": _digest(source_id),
        "source_volume": source_volume,
        "target_volume": target_volume,
        "fixture_ids": fixture_ids,
        "source_removal_digest": source_removal_digest,
        "source_manifest_digest": source_manifest.get("manifest_digest"),
        "pre_release_history_custody_digest": _digest(pre_release_history),
        "pre_release_history_custody": dict(pre_release_history),
        "pre_release_engine_inventory_digest": pre_release_inventory.get("inventory_digest"),
        "pre_release_engine_inventory": pre_release_inventory,
        "pre_release_mount_witnesses_digest": pre_release_inventory.get(
            "container_mount_witnesses_digest"
        ),
        "target_copy_manifest_digest": copy_report.get("target", {}).get("manifest_digest"),
        "target_spec_fingerprint": target_spec_fingerprint,
        "history_query_mode": HISTORY_QUERY_MODE,
        "target_profile": target_profile,
        "parent_uuid": parent_uuid,
    }
    release_digest, target_launch_digest = _persist_release_and_launch_intents(
        ledger,
        release_payload=release_payload,
        launch_payload={
            "run_id": run_id,
            "source_invocation_digest": probe.digest(source_invocation),
            "source_phase_report_digest": source_report.get("source_phase_report_digest"),
            "native_task_source_terminal_seed": dict(source_native_seed),
            "native_task_source_terminal_seed_digest": source_native_seed.get("seed_digest"),
            "parent_uuid_digest": probe.digest(parent_uuid),
            "source_removal_digest": source_removal_digest,
            "pre_release_engine_inventory_digest": pre_release_inventory.get("inventory_digest"),
            "pre_release_mount_witnesses_digest": pre_release_inventory.get(
                "container_mount_witnesses_digest"
            ),
            "pre_release_history_custody_digest": _digest(pre_release_history),
            "target_spec_fingerprint": target_spec_fingerprint,
            "history_query_mode": HISTORY_QUERY_MODE,
            "parent_uuid": parent_uuid,
            "target_volume": target_volume,
        },
        observe=observe,
        parent_uuid=parent_uuid,
        target_identity=target_volume,
    )
    target_name = "opentools-b4-target-" + token
    tracker["target_name"] = target_name
    target_id = _create_authorized_target(
        observe,
        tracker=tracker,
        image_id=image_id,
        run_id=run_id,
        role="target",
        name=target_name,
        volume_mounts={STATE_ROOT: (target_volume, True)},
    )
    tracker.setdefault("private_values", []).append(target_name)
    _install_observer_files(
        target_id, cli_path, run_id=run_id, role="target",
        image_id=image_id, private_dir=private_dir, observer=observe,
        expected_mounts=_expected_mounts({STATE_ROOT: (target_volume, True)}),
        tracker=tracker,
    )
    observe.wait_engine_event(kind="container", action="start", identity=target_id)
    target_stop_digest = ledger.persist("target-stop", {
        "run_id": run_id,
        "target_container_id": target_id,
        "target_container_id_digest": _digest(target_id),
        "target_launch_intent_digest": target_launch_digest,
    })
    observe("target-runtime-stop-intent", target_id, {"digest": target_stop_digest})
    target_expected = dict(selected)
    target_expected.pop("selected_cli", None)
    target_expected.update({
        "two_domain_phase": "target",
        "state_root": STATE_ROOT,
        "source_parent_uuid": parent_uuid,
        "native_task_source_terminal_seed": dict(source_native_seed),
        "native_task_source_terminal_seed_digest": source_native_seed.get("seed_digest"),
        "source_phase_report_digest": source_report.get("source_phase_report_digest"),
        "source_invocation_digest": probe.digest(source_invocation),
        "target_profile": target_profile,
        "target_spec_fingerprint": target_spec_fingerprint,
        "history_query_mode": HISTORY_QUERY_MODE,
        "target_copy_manifest_digest": copy_report.get("target", {}).get("manifest_digest"),
        "source_manifest_digest": source_manifest.get("manifest_digest"),
        "pre_release_history_custody_digest": _digest(pre_release_history),
        "pre_release_engine_inventory_digest": pre_release_inventory.get("inventory_digest"),
        "image_id": image_id,
    })
    _require_mount_witness_ready(tracker, observe, target_id)
    target_report = _runtime_exec(target_id, target_expected)
    _mount_witness_session(tracker, target_id).check_alive()
    observe("target-phase-returned", target_id, {"target_report_digest": _digest(target_report)})
    target_container_stop_digest = ledger.persist("target-container-stop", {
        "run_id": run_id,
        "target_container_id": target_id,
        "target_container_id_digest": _digest(target_id),
    })
    for row in tracker["containers"]:
        if isinstance(row, dict) and row.get("id") == target_id:
            row["stop_intent_persisted"] = True
    _docker("stop", "--time", "10", target_id, timeout=20)
    observe.wait_engine_event(kind="container", action="die", identity=target_id)
    target_stopped = _container_state(target_id)
    if target_stopped.get("Running") is not False:
        raise RuntimeError("target container stop was not observed")
    _reap_mount_witness_after_stop(tracker, target_id, observe)
    observe("target-container-stopped", target_id, {
        "exit_code": target_stopped.get("ExitCode"),
    })
    target_remove_digest = ledger.persist("target-remove", {
        "run_id": run_id,
        "target_container_id": target_id,
        "target_container_id_digest": _digest(target_id),
        "target_container_stop_intent_digest": target_container_stop_digest,
    })
    for row in tracker["containers"]:
        if isinstance(row, dict) and row.get("id") == target_id:
            row["remove_intent_persisted"] = True
    _docker("rm", target_id, timeout=20)
    if not _container_absent(target_id):
        raise RuntimeError("target container removal was not observed")
    observe.wait_engine_event(
        kind="container", action="destroy", identity=target_id,
    )
    for row in tracker["containers"]:
        if isinstance(row, dict) and row.get("id") == target_id:
            row["removed"] = True
    for row in tracker.get("planned_containers", []):
        if isinstance(row, dict) and row.get("role") == "target":
            row["id"] = target_id
            row["removed"] = True
    observe("target-container-removed", target_id, {
        "remove_intent_digest": target_remove_digest,
    })
    final_report = _run_custodian(
        image_id=image_id, run_id=run_id, role="custodian", operation="final",
        source_volume=source_volume, target_volume=target_volume,
        private_dir=private_dir, observe=observe, tracker=tracker,
        parent_history=_parent_history_record(source_observation),
        parent_history_prefix=_parent_history_prefix(source_report),
    )
    target_uuid_seen = target_report.get("target_parent_uuid_seen") is True
    same_parent = target_report.get("same_parent_uuid") is True
    wrong_parent = target_uuid_seen and not same_parent
    source_prefixes = final_report.get("source_history_prefixes_retained") is True
    identity_history_candidates = final_report.get(
        "identity_linked_parent_history_candidate_count"
    )
    identity_history_bound = (
        final_report.get("identity_linked_parent_history_binding_valid") is True
    )
    custody_assessment = _final_custody_assessment(final_report)
    saved_edit_retained = custody_assessment["saved_edit_retained"] is True
    target_query_complete = _target_history_query_complete(target_report)
    violations = list(
        custody_assessment["reason_codes"]
        if custody_assessment["status"] == "fail" else []
    )
    if wrong_parent:
        violations.append("wrong-parent-uuid")
    if target_report.get("gateway_protocol_errors"):
        violations.append("unauthorized-target-request")
    custody_incomplete = (
        custody_assessment["status"] == "inconclusive"
        or identity_history_candidates != 1 or not identity_history_bound
        or not source_prefixes or not saved_edit_retained
    )
    status = "fail" if violations else (
        "observed" if same_parent and not custody_incomplete and target_query_complete
        else "inconclusive"
    )
    for row in tracker["containers"]:
        if isinstance(row, dict) and row.get("role") == "target":
            row["removed"] = True
    result = {
        "arm": arm,
        "status": status,
        "reason_codes": sorted(set(violations)) or list(
            (target_report.get("startup_gate") or {}).get("reason_codes", [])
            if isinstance(target_report.get("startup_gate"), Mapping) else []
        ) or list(custody_assessment["reason_codes"]) or [
            code for condition, code in (
                (not target_uuid_seen, "target-parent-uuid-unobserved"),
                (not identity_history_bound or identity_history_candidates != 1,
                 "identity-linked-history-evidence-incomplete"),
                (not source_prefixes, "source-history-custody-incomplete"),
                (not target_query_complete, "target-history-query-result-incomplete"),
            ) if condition
        ],
        "source_report_digest": source_report.get("source_phase_report_digest"),
        "source_manifest_digest": source_manifest.get("manifest_digest"),
        "target_copy_manifest_digest": copy_report.get("target", {}).get("manifest_digest"),
        "source_removal_digest": source_removal_digest,
        "pre_release_history_custody_digest": _digest(pre_release_history),
        "pre_release_history_custody": dict(pre_release_history),
        "pre_release_engine_inventory_digest": pre_release_inventory.get("inventory_digest"),
        "pre_release_engine_inventory": pre_release_inventory,
        "release_digest": release_digest,
        "target_launch_intent_digest": target_launch_digest,
        "target_spec_fingerprint": target_spec_fingerprint,
        "history_query_mode": HISTORY_QUERY_MODE,
        "target_report": target_report,
        "final_custody": final_report,
        "final_custody_assessment": custody_assessment,
        "source_container_created_digest": _digest(source_id),
        "target_container_created_digest": _digest(target_id),
        "target_container_stop_intent_digest": target_stop_digest,
        "target_container_removed": True,
        "fixture_identity_digests": {name: _digest(value) for name, value in fixture_ids.items()},
        "source": _source_projection(source_observation),
        "support_claim": False,
        "release_candidate_ready": True,
    }
    _remember_normal_arm_disposition(result, tracker)
    tracker["normal_arm_failure_stage"] = "arm-lifecycle-verification"
    observe.verify_lifecycle(volumes_removed=False)
    _finalize_normal_arm_result(
        result, ledger=ledger, observer=observe, tracker=tracker,
        run_id=run_id, source_volume=source_volume,
        target_volume=target_volume, observe=observe,
    )
    return result


def _stop_engine_observer(observer: TwoDomainObserver) -> None:
    with observer.condition:
        observer.engine_ending = True
    for process in (observer.engine_process, observer.volume_process):
        if process is None:
            continue
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    for reader in (observer.engine_reader, observer.volume_reader):
        if reader is not None:
            reader.join(timeout=5)


def _possible_leftovers(tracker: Mapping[str, object]) -> dict[str, object]:
    containers = tracker.get("containers")
    rows = []
    if isinstance(containers, list):
        for row in containers:
            if not isinstance(row, Mapping) or row.get("removed") is True:
                continue
            rows.append({
                "role": row.get("role"),
                "name_digest": _digest(row.get("name")),
                "id_digest": _digest(row.get("id")),
            })
    possible_names: list[dict[str, object]] = []
    planned = tracker.get("planned_containers")
    if isinstance(planned, list):
        for row in planned:
            if isinstance(row, Mapping) and row.get("removed") is not True:
                possible_names.append({
                    "role": row.get("role"),
                    "name_digest": _digest(row.get("name")),
                    "id_digest": _digest(row.get("id")),
                })
    possible_volumes = {
        key: _digest(tracker.get(key))
        for key, removed_key in (
            ("source_volume", "source_volume_removed"),
            ("target_volume", "target_volume_removed"),
        )
        if isinstance(tracker.get(key), str) and tracker.get(removed_key) is not True
    }
    quarantine_candidates = tracker.get("quarantine_candidates")
    unresolved_quarantine_ids = []
    if isinstance(quarantine_candidates, Mapping):
        unresolved_quarantine_ids = sorted(
            digest_value for digest_value, row in quarantine_candidates.items()
            if isinstance(digest_value, str)
            and isinstance(row, Mapping) and row.get("removed") is not True
        )
    return {
        "known_container_digests": rows,
        "possible_container_name_digests": possible_names,
        "possible_volume_digests": possible_volumes,
        "quarantine_unresolved_id_digests": unresolved_quarantine_ids,
        "manual_review_required": bool(
            rows or possible_names or possible_volumes or unresolved_quarantine_ids
        ),
    }


def _row_for_container(
    tracker: dict[str, object], container_id: str, *, name: str, role: str,
) -> dict[str, object]:
    containers = tracker.setdefault("containers", [])
    if not isinstance(containers, list):
        raise RuntimeError("container tracker is malformed")
    for row in containers:
        if isinstance(row, dict) and row.get("id") == container_id:
            return row
    for candidate in tracker.get("planned_containers", []):
        if not isinstance(candidate, dict):
            continue
        if (candidate.get("id") == container_id
                or (candidate.get("name") == name and candidate.get("role") == role)):
            candidate["id"] = container_id
            break
    if not isinstance(role, str):
        raise RuntimeError("run container has no planned role")
    row = {
        "name": name, "id": container_id, "role": role, "removed": False,
        "stop_intent_persisted": False, "remove_intent_persisted": False,
    }
    containers.append(row)
    return row


def _quarantine_run_owned_resources(
    *,
    run_id: str,
    tracker: dict[str, object],
    ledger: probe.TwoDomainIntentLedger | None,
    private_dir: Path,
    observer: TwoDomainObserver,
) -> dict[str, object]:
    """Stop exact run-labelled containers, with append-once intents.

    This is failure containment, not evidence custody. Containers and volumes
    remain in place for manual review after any failure. Previously recorded
    effects are never replayed.
    """

    stats = {
        "discovered": 0, "stopped": 0, "removed": 0, "preserved": 0,
        "never_started_preserved": 0,
    }
    reasons: list[str] = []
    if ledger is None:
        return {**stats, "reason_codes": ["quarantine-ledger-unavailable"]}
    try:
        container_ids = _container_ids_for_run(run_id, timeout=8)
    except BaseException:
        container_ids = []
        reasons.append("quarantine-inventory-unavailable")
    known_ids = [
        row.get("id") for row in tracker.get("containers", [])
        if isinstance(row, Mapping) and row.get("removed") is not True
        and isinstance(row.get("id"), str)
    ]
    container_ids = sorted(set(container_ids) | set(known_ids))
    if len(container_ids) > 4:
        candidates = tracker.setdefault("quarantine_candidates", {})
        if isinstance(candidates, dict):
            for container_id in container_ids[4:]:
                candidates[_digest(container_id)] = {"removed": False}
        container_ids = container_ids[:4]
        reasons.append("quarantine-container-count-exceeded")
    stats["discovered"] = len(container_ids)
    planned = tracker.get("planned_containers", [])
    expected_by_name: dict[str, str] = {}
    if isinstance(planned, list):
        for item in planned:
            if isinstance(item, Mapping):
                name, role = item.get("name"), item.get("role")
                if isinstance(name, str) and isinstance(role, str):
                    expected_by_name[name] = role

    for container_id in container_ids:
        candidates = tracker.setdefault("quarantine_candidates", {})
        if isinstance(candidates, dict):
            candidates[_digest(container_id)] = {"removed": False}
        try:
            record = _inspect_container(container_id, timeout=8)
            config = record.get("Config")
            labels = config.get("Labels") if isinstance(config, Mapping) else None
            raw_name = record.get("Name")
            name = raw_name[1:] if isinstance(raw_name, str) and raw_name.startswith("/") else raw_name
            role = labels.get("openrepotools.bite4.role") if isinstance(labels, Mapping) else None
            if (not isinstance(labels, Mapping)
                    or labels.get("openrepotools.bite4.run") != run_id
                    or not isinstance(name, str)
                    or expected_by_name.get(name) != role):
                reasons.append("quarantine-unrecognized-run-container")
                stats["preserved"] += 1
                continue
            row = _row_for_container(tracker, container_id, name=name, role=role)
            tracker.setdefault("private_values", []).append(container_id)
            if isinstance(name, str):
                tracker.setdefault("private_values", []).append(name)
            state = record.get("State")
            if not isinstance(state, Mapping) or type(state.get("Running")) is not bool:
                reasons.append("quarantine-container-state-unavailable")
                stats["preserved"] += 1
                continue
            if row.get("remove_intent_persisted") is True:
                reasons.append("quarantine-remove-intent-already-recorded")
                stats["preserved"] += 1
                continue

            if state.get("Running") is True:
                if row.get("stop_intent_persisted") is True:
                    reasons.append("quarantine-stop-intent-already-recorded")
                    stats["preserved"] += 1
                    continue
                per_container_ledger = probe.TwoDomainIntentLedger(
                    private_dir / "quarantine" / _digest(container_id)
                )
                per_container_ledger.persist("quarantine-stop", {
                    "run_id": run_id,
                    "container_id": container_id,
                    "container_id_digest": _digest(container_id),
                    "role": role,
                    "state_running_before": True,
                })
                row["stop_intent_persisted"] = True
                stop_error: BaseException | None = None
                try:
                    _docker("stop", "--time", "10", container_id, timeout=20)
                except BaseException as exc:
                    # A non-zero or timed-out command is uncertain. Inspect and
                    # observe, but never issue a second stop.
                    stop_error = exc
                try:
                    observer.wait_engine_event(
                        kind="container", action="die", identity=container_id,
                        timeout=3.0,
                    )
                    state = _container_state(container_id, timeout=8)
                except BaseException:
                    state = {}
                if state.get("Running") is not False:
                    reasons.append("quarantine-stop-effect-unconfirmed")
                    if stop_error is not None:
                        reasons.append("quarantine-stop-command-uncertain")
                    stats["preserved"] += 1
                    continue
                stats["stopped"] += 1
            elif probe.two_domain_created_never_started(record):
                try:
                    observer.wait_engine_event(
                        kind="container", action="create", identity=container_id,
                        timeout=3.0,
                    )
                    observer.ensure_engine_healthy()
                    start_observed = observer.container_start_observed(container_id)
                except BaseException:
                    reasons.append("quarantine-never-started-evidence-incomplete")
                    stats["preserved"] += 1
                    continue
                if row.get("start_attempted") is True or start_observed:
                    reasons.append("quarantine-start-history-uncertain")
                    stats["preserved"] += 1
                    continue
                stats["never_started_preserved"] += 1
                reasons.append("quarantine-created-never-started-preserved")
                stats["preserved"] += 1
                continue
            else:
                try:
                    observer.wait_engine_event(
                        kind="container", action="die", identity=container_id,
                        timeout=3.0,
                    )
                except BaseException:
                    reasons.append("quarantine-die-event-unconfirmed")
                    stats["preserved"] += 1
                    continue

            sessions = tracker.get("mount_witness_sessions")
            if isinstance(sessions, Mapping) and container_id in sessions:
                try:
                    _reap_mount_witness_after_stop(tracker, container_id, observer)
                except BaseException:
                    reasons.append("quarantine-mount-witness-attach-reap-incomplete")
                    stats["preserved"] += 1
                    continue
            try:
                _persist_untracked_attach_reap(tracker, container_id, observer)
            except BaseException:
                reasons.append("quarantine-mount-witness-attach-reap-incomplete")
                stats["preserved"] += 1
                continue

            reasons.append("quarantine-container-preserved-for-custody-review")
            stats["preserved"] += 1
        except BaseException:
            reasons.append("quarantine-step-incomplete")
            stats["preserved"] += 1

    summary: dict[str, object] = {
        **stats,
        "reason_codes": sorted(set(reasons)),
        "observer_event_digest": _digest(observer.report()),
        "volumes_removed": False,
    }
    try:
        ledger.persist("quarantine-summary", {
            "run_id": run_id,
            **summary,
        })
    except BaseException:
        summary["reason_codes"] = sorted(set(reasons + ["quarantine-summary-not-durable"]))
    return summary


def _public_image_id_scan_projection(
    value: object, resolved_image_id: str,
) -> dict[str, object]:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", resolved_image_id):
        raise KnownViolation("public-image-identity-invalid")
    if not isinstance(value, dict):
        raise KnownViolation("public-image-identity-invalid")
    identities = value.get("identities")
    if (not isinstance(identities, dict)
            or identities.get("image_id") != resolved_image_id):
        raise KnownViolation("public-image-identity-mismatch")
    projection = dict(value)
    projected_identities = dict(identities)
    projected_identities["image_id"] = None
    projection["identities"] = projected_identities
    return projection


def _assert_no_private_values(value: object, private_values: object) -> None:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    values = private_values if isinstance(private_values, list) else []
    for private in values:
        if isinstance(private, str) and len(private) >= 8 and private in serialized:
            raise KnownViolation("private-identifier-in-report")


def _run_arm(
    *,
    arm: str,
    run_id: str,
    image_id: str,
    cli_path: str,
    selected: Mapping[str, object],
    private_dir: Path,
) -> dict[str, object]:
    token = uuid.uuid4().hex[:16]
    observer = TwoDomainObserver(arm)
    ledger: probe.TwoDomainIntentLedger | None = None
    tracker: dict[str, object] = {
        "run_id": run_id,
        "source_name": "opentools-b4-source-" + token,
        "target_name": "opentools-b4-target-" + token,
        "source_volume": "opentools-b4-s-" + token,
        "target_volume": "opentools-b4-t-" + token,
        "containers": [],
        "private_values": [
            run_id, token, cli_path,
            "opentools-b4-source-" + token,
            "opentools-b4-target-" + token,
            "opentools-b4-s-" + token,
            "opentools-b4-t-" + token,
        ],
    }
    try:
        ledger = probe.TwoDomainIntentLedger(private_dir / "ledger")
        observer.start_engine_stream(run_id)
        result = _run_arm_impl(
            arm=arm,
            run_id=run_id,
            token=token,
            image_id=image_id,
            cli_path=cli_path,
            selected=selected,
            private_dir=private_dir,
            ledger=ledger,
            tracker=tracker,
            observe=observer,
        )
        status = result.get("status")
        if status in {"observed", "fail", "inconclusive"}:
            _remember_normal_arm_disposition(result, tracker)
        cleanup_complete = result.get("cleanup_complete") is True
        if status == "observed":
            if not cleanup_complete:
                raise RuntimeError("observed arm lacks completed custody cleanup")
        elif status in {"fail", "inconclusive"}:
            if cleanup_complete:
                raise KnownViolation("failed-arm-volumes-were-removed")
            cleanup_complete = False
        else:
            raise RuntimeError("two-domain arm returned an invalid normal status")
        tracker["normal_arm_failure_stage"] = "engine-stream-finalization"
        observer.finish_engine_stream()
        tracker["normal_arm_failure_stage"] = "observer-lifecycle-verification"
        observer.verify_lifecycle(volumes_removed=cleanup_complete)
        tracker["normal_arm_failure_stage"] = "observer-reporting"
        result["observer_events"] = observer.report()
        result["observer_complete"] = True
        result["cleanup_complete"] = cleanup_complete
        result["leftovers"] = (
            {
                "known_container_digests": [],
                "possible_container_name_digests": {},
                "possible_volume_digests": {},
                "quarantine_unresolved_id_digests": [],
                "manual_review_required": False,
            }
            if cleanup_complete else _possible_leftovers(tracker)
        )
        result["support_claim"] = False
        _assert_no_private_values(
            result,
            list(tracker.get("private_values", [])) + observer.private_values,
        )
        return result
    except BaseException as exc:
        normal_status = tracker.get("normal_arm_status")
        normal_reasons = tracker.get("normal_arm_reason_codes")
        normal_reasons = normal_reasons if isinstance(normal_reasons, list) else []
        exception_known = isinstance(exc, KnownViolation)
        known = exception_known or normal_status == "fail"
        if tracker.get("source_runtime_report_invalid") is True:
            reason_code = "source-runtime-report-invalid"
        else:
            reason_code = (
                exc.code if exception_known else "effect-or-observer-uncertain"
            )
        initial_leftovers = _possible_leftovers(tracker)
        if ledger is not None:
            try:
                private_failure = {
                    "run_id": run_id,
                    "arm": arm,
                    "reason_code": reason_code,
                    "error_type": type(exc).__name__,
                    "private_error": str(exc)[:1024],
                    "observer_event_digest": _digest(observer.report()),
                    "observer_error": observer.engine_error,
                    "prior_normal_status": normal_status,
                    "prior_normal_reason_codes": normal_reasons,
                    "leftovers": initial_leftovers,
                }
                if isinstance(exc, DockerCommandError):
                    private_failure.update({
                        "private_docker_exit_status": exc.returncode,
                        "private_docker_stderr_b64": base64.b64encode(
                            exc.private_stderr
                        ).decode("ascii"),
                        "private_docker_stderr_truncated": exc.private_stderr_truncated,
                    })
                if isinstance(exc, MountWitnessTransportError):
                    private_failure.update({
                        "private_mount_witness_error_code": exc.code,
                        "private_mount_witness_stderr_b64": base64.b64encode(
                            exc.private_stderr
                        ).decode("ascii"),
                        "private_mount_witness_stderr_truncated": exc.private_stderr_truncated,
                    })
                ledger.persist("arm-abort", private_failure)
            except BaseException:
                pass
        quarantine = _quarantine_run_owned_resources(
            run_id=run_id, tracker=tracker, ledger=ledger,
            private_dir=private_dir, observer=observer,
        )
        _stop_engine_observer(observer)
        leftovers = _possible_leftovers(tracker)
        reported_reasons = [reason_code]
        reported_reasons.extend(
            value for value in normal_reasons if isinstance(value, str)
        )
        failure_stage = tracker.get("normal_arm_failure_stage")
        if failure_stage in {
            "engine-stream-finalization", "observer-lifecycle-verification",
            "observer-reporting",
        }:
            reported_reasons.append("observer-incomplete")
        elif failure_stage == "arm-result-persistence":
            reported_reasons.append("arm-result-persistence-incomplete")
        elif failure_stage == "arm-result-observer-record":
            reported_reasons.append("arm-result-observer-record-incomplete")
        elif failure_stage == "arm-lifecycle-verification":
            reported_reasons.append("arm-lifecycle-verification-incomplete")
        elif failure_stage == "mount-witness-finding-persistence":
            reported_reasons.append("witness-durability-incomplete")
            provisional_finding = tracker.get("mount_witness_provisional_policy_finding")
            if (isinstance(provisional_finding, str)
                    and re.fullmatch(r"mountinfo-[a-z0-9-]{1,96}", provisional_finding)):
                reported_reasons.append("provisional-" + provisional_finding)
        reported_reasons.extend(
            reason for reason in quarantine.get("reason_codes", [])
            if isinstance(reason, str)
        )
        result = {
            "arm": arm,
            "status": "fail" if known else "inconclusive",
            "reason_codes": sorted(set(reported_reasons)),
            "observer_complete": False,
            "observer_event_digest": _digest(observer.report()),
            "quarantine": quarantine,
            "leftovers": leftovers,
            "support_claim": False,
            "release_candidate_ready": False,
            "cleanup_complete": False,
        }
        _assert_no_private_values(
            result,
            list(tracker.get("private_values", [])) + observer.private_values,
        )
        return result


def _create_private_directory(path: Path) -> Path:
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("private artifact directory requires no-follow support")
    absolute = Path(os.path.abspath(os.fspath(path)))
    name = absolute.name
    if name in {"", ".", ".."}:
        raise RuntimeError("private artifact directory path is invalid")
    parent_fd = probe._open_directory_nofollow(absolute.parent)
    child_fd = -1
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        os.fsync(parent_fd)
        child_fd = os.open(
            name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        info = os.fstat(child_fd)
        if (info.st_uid != os.geteuid() or info.st_mode & 0o077
                or not stat.S_ISDIR(info.st_mode)):
            raise RuntimeError("private artifact directory permissions are unsafe")
        os.fsync(child_fd)
    finally:
        if child_fd >= 0:
            os.close(child_fd)
        os.close(parent_fd)
    return absolute


def _write_private_report(path: Path, report: Mapping[str, object]) -> None:
    parent_fd = probe._open_directory_nofollow(path.parent)
    name = path.name
    if name in {"", ".", ".."}:
        os.close(parent_fd)
        raise RuntimeError("private report path is invalid")
    temp_name = ".report." + uuid.uuid4().hex + ".tmp"
    fd = -1
    try:
        dir_info = os.fstat(parent_fd)
        if (dir_info.st_uid != os.geteuid() or dir_info.st_mode & 0o077
                or not stat.S_ISDIR(dir_info.st_mode)):
            raise RuntimeError("private report directory permissions are unsafe")
        fd = os.open(
            temp_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        os.fchmod(fd, 0o600)
        data = probe._canonical_json(report)
        if len(data) > 1024 * 1024:
            raise RuntimeError("sanitized Bite 4 report exceeds its size bound")
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise RuntimeError("private report write made no progress")
            view = view[written:]
        os.fsync(fd)
        os.close(fd)
        fd = -1
        try:
            os.link(
                temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise RuntimeError("private report already exists; do not overwrite") from exc
        os.unlink(temp_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(parent_fd)


def _source_runtime_report_invalid_reasons(
    report: object,
    *,
    source_invocation: str,
    source_container_id: str,
) -> list[str]:
    if not isinstance(report, Mapping):
        return ["source-runtime-report-not-object"]
    reasons: list[str] = []
    if report.get("schema") != "openrepotools-bite4-source-phase/v1":
        reasons.append("source-runtime-report-schema-mismatch")
    if report.get("phase") != "source":
        reasons.append("source-runtime-report-phase-mismatch")
    if report.get("support_claim") is not False:
        reasons.append("source-runtime-report-support-claim-invalid")
    if report.get("target_code_reached") is not False:
        reasons.append("source-runtime-report-target-code-reached-or-unknown")
    if report.get("source_invocation") != source_invocation:
        reasons.append("source-runtime-report-invocation-mismatch")
    if report.get("source_container_label") != probe.digest(source_container_id):
        reasons.append("source-runtime-report-container-mismatch")
    return sorted(set(reasons))


def _persist_and_validate_source_runtime_report(
    report: object,
    *,
    source_invocation: str,
    source_container_id: str,
    private_dir: Path,
    tracker: dict[str, object],
) -> dict[str, object]:
    """Durably retain the exact source report before any source-stop effect."""
    envelope: dict[str, object] = {
        "schema": SOURCE_RUNTIME_REPORT_ENVELOPE_SCHEMA,
        "source_invocation_digest": _digest(source_invocation),
        "source_container_id_digest": _digest(source_container_id),
        "source_report_digest": _digest(report),
        "source_report": report,
    }
    _write_private_report(private_dir / "source-runtime-report.json", envelope)
    reasons = _source_runtime_report_invalid_reasons(
        report,
        source_invocation=source_invocation,
        source_container_id=source_container_id,
    )
    if reasons:
        if (
            isinstance(report, Mapping)
            and report.get("target_code_reached") is True
            and reasons == ["source-runtime-report-target-code-reached-or-unknown"]
        ):
            raise KnownViolation("source-phase-reached-target-code")
        tracker["source_runtime_report_invalid"] = True
        tracker["source_runtime_report_invalid_reasons"] = reasons
        raise RuntimeError(
            "source runtime report invalid: " + ",".join(reasons)
        )
    tracker["source_runtime_report_digest"] = envelope["source_report_digest"]
    return envelope


def _resolve_image_id(image_ref: str) -> str:
    if (not image_ref or image_ref.startswith("-")
            or re.search(r"[\s\x00-\x1f]", image_ref)):
        raise RuntimeError("local image reference is malformed")
    result = _docker("image", "inspect", "--format={{.Id}}", image_ref)
    image_id = result.stdout.decode("ascii", "strict").strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise RuntimeError("local image does not resolve to an immutable image ID")
    return image_id


def _host_file_sha256(path: str | os.PathLike[str]) -> str:
    return hashlib.sha256(_read_bounded(path)).hexdigest()


def _run_experiment(args: argparse.Namespace) -> dict[str, object]:
    if not args.explicit_release:
        raise RuntimeError("Bite 4 requires the explicit-release selection")
    if not args.sdk_python or not args.image or not args.private_artifacts:
        raise RuntimeError("Bite 4 requires SDK interpreter, local image and private artifacts")
    private_root = _create_private_directory(Path(args.private_artifacts))
    selected = probe._select_runtime(args.sdk_python)
    cli_path = selected.get("selected_cli")
    cli_digest = selected.get("cli_sha256")
    if (not isinstance(cli_path, str) or not isinstance(cli_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", cli_digest)
            or _host_file_sha256(cli_path) != cli_digest):
        raise RuntimeError("pinned SDK-selected CLI digest did not verify")
    image_id = _resolve_image_id(args.image)
    run_root = "bite4-" + uuid.uuid4().hex
    private_values = [cli_path, args.sdk_python, args.image, image_id, run_root]
    positive = _run_arm(
        arm="positive",
        run_id=run_root + "-positive",
        image_id=image_id,
        cli_path=cli_path,
        selected=selected,
        private_dir=private_root / "positive",
    )
    arms: list[dict[str, object]] = [positive]
    if (positive.get("release_candidate_ready") is True
            and positive.get("cleanup_complete") is True
            and positive.get("observer_complete") is True
            and positive.get("status") != "fail"):
        negative = _run_arm(
            arm="negative",
            run_id=run_root + "-negative",
            image_id=image_id,
            cli_path=cli_path,
            selected=selected,
            private_dir=private_root / "negative",
        )
        arms.append(negative)
    else:
        unmet = [
            code for condition, code in (
                (positive.get("release_candidate_ready") is not True,
                 "positive-release-candidate-not-established"),
                (positive.get("cleanup_complete") is not True,
                 "positive-cleanup-incomplete"),
                (positive.get("observer_complete") is not True,
                 "positive-observer-incomplete"),
                (positive.get("status") == "fail", "positive-arm-failed"),
            ) if condition
        ]
        arms.append({
            "arm": "negative",
            "status": "not-run",
            "reason_codes": unmet,
            "target_container_created": False,
            "support_claim": False,
        })
    failed = any(row.get("status") == "fail" for row in arms)
    complete = bool(
        len(arms) == 2
        and arms[0].get("arm") == "positive"
        and arms[1].get("arm") == "negative"
        and all(row.get("status") == "observed"
                and row.get("observer_complete") is True
                and row.get("cleanup_complete") is True
                for row in arms)
        and arms[1].get("release_refused") is True
        and arms[1].get("target_container_created") is False
    )
    report: dict[str, object] = {
        "schema": "openrepotools-bite4-two-domain-report/v1",
        "experiment": "bounded-two-domain-diagnostic",
        "diagnostic_status": "FAIL" if failed else "OBSERVED" if complete else "INCONCLUSIVE",
        "bite5_decision": "pending-review",
        "explicit_release_selected": True,
        "support_claim": False,
        "production_disposition": "unsupported",
        "identities": {
            "image_id": image_id,
            "sdk_version": selected.get("sdk_version"),
            "selected_cli_sha256": cli_digest,
            "probe_sha256": _host_file_sha256(probe.__file__),
            "harness_sha256": _host_file_sha256(__file__),
            "test_sha256": _host_file_sha256(
                Path(__file__).resolve().parents[1] / "test_lane_managed_loopback_probe.py"
            ),
        },
        "arms": arms,
    }
    _assert_no_private_values(
        _public_image_id_scan_projection(report, image_id), private_values,
    )
    return report


def _runtime_exec(container_id: str, expected: Mapping[str, object]) -> Mapping[str, object]:
    payload = json.dumps(expected, separators=(",", ":")).encode("utf-8")
    if len(payload) > 1024 * 1024:
        raise RuntimeError("two-domain runtime input exceeds its bound")
    result = _docker(
        "exec", "-i", container_id,
        "/usr/bin/env", "-i", "PATH=/usr/local/bin:/usr/bin:/bin",
        "python3", LOOPBACK_ROOT + "/probe.py",
        "--runtime", "--expected-stdin",
        timeout=probe.MAX_RUNTIME_SECONDS + 20,
        input=payload,
    )
    value = _json_output(result)
    if not isinstance(value, Mapping):
        raise RuntimeError("two-domain runtime phase returned a malformed report")
    return value


def _manifest_summary(root: str, *, require_fixture: bool = True) -> dict[str, object]:
    manifest = probe.manifest_two_domain_tree(root)
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise RuntimeError("two-domain tree manifest is malformed")
    directories = {
        row.get("path") for row in entries
        if isinstance(row, Mapping) and row.get("kind") == "directory"
    }
    files = {
        row.get("path"): row for row in entries
        if isinstance(row, Mapping) and row.get("kind") == "file"
    }
    required_dirs = {"config", "workspace", "home", "xdg"}
    if require_fixture and not required_dirs.issubset(directories):
        raise RuntimeError("two-domain state layout is incomplete")
    edit = files.get("workspace/saved-edit.txt")
    if (require_fixture and (not isinstance(edit, Mapping)
            or edit.get("sha256") != hashlib.sha256(probe.V1_SAVED_EDIT).hexdigest())):
        raise RuntimeError("two-domain deterministic saved edit mismatch")
    history_rows = [
        row for name, row in files.items()
        if isinstance(name, str) and name.startswith("config/")
    ]
    history_jsonl_count = sum(
        1 for name in files
        if isinstance(name, str) and name.startswith("config/") and name.endswith(".jsonl")
    )
    history_manifest = [
        {
            "path": name[len("config/"):],
            "size": row.get("size"),
            "sha256": row.get("sha256"),
        }
        for name, row in sorted(files.items())
        if isinstance(name, str) and name.startswith("config/")
        and isinstance(row, Mapping)
    ]
    return {
        "schema": manifest["schema"],
        "manifest_digest": _digest(manifest),
        "file_count": manifest["file_count"],
        "directory_count": manifest["directory_count"],
        "entry_count": manifest["entry_count"],
        "total_bytes": manifest["total_bytes"],
        "saved_edit_sha256": edit.get("sha256") if isinstance(edit, Mapping) else None,
        "history_file_count": len(history_rows),
        "history_jsonl_count": history_jsonl_count,
        "history_manifest_digest": _digest(history_manifest),
        "layout_valid": True,
    }


def _history_custody_facts(
    source_files: Mapping[str, bytes],
    target_files: Mapping[str, bytes],
    *,
    parent_prefix: bytes | None,
    parent_history_size: int | None,
    parent_history_sha256: str | None,
) -> dict[str, object]:
    prefix_bound = bool(
        isinstance(parent_prefix, bytes) and 0 < len(parent_prefix)
        and len(parent_prefix) == parent_history_size
        and isinstance(parent_history_sha256, str)
        and hashlib.sha256(parent_prefix).hexdigest() == parent_history_sha256
    )
    source_config = {
        path: content for path, content in source_files.items()
        if path.startswith("config/")
    }
    source_candidates = {
        path: content for path, content in source_config.items()
        if path.endswith(".jsonl") and prefix_bound
        and content.startswith(parent_prefix)
    } if prefix_bound else {}
    unique_candidate = len(source_candidates) == 1
    linked_path = next(iter(source_candidates)) if unique_candidate else None
    linked_source = source_candidates.get(linked_path) if linked_path else None
    linked_target = target_files.get(linked_path) if linked_path else None
    prefix_retained = bool(
        isinstance(linked_path, str)
        and isinstance(linked_source, bytes)
        and isinstance(linked_target, bytes)
        and linked_target.startswith(linked_source)
    )
    target_config_paths = {
        path for path in target_files if path.startswith("config/")
    }
    config_mutations = {
        path for path in set(source_config) | target_config_paths
        if source_config.get(path) != target_files.get(path)
    }
    unrelated_mutations = config_mutations - (
        {linked_path} if isinstance(linked_path, str) else set()
    )
    return {
        "identity_linked_parent_history_candidate_count": len(source_candidates),
        "identity_linked_parent_history_binding_valid": prefix_bound,
        "identity_linked_parent_history_size": parent_history_size,
        "identity_linked_parent_history_sha256": parent_history_sha256,
        "identity_linked_parent_history_prefix_bytes": len(parent_prefix or b""),
        "identity_linked_parent_history_prefix_retained": prefix_retained,
        "identity_linked_history_size": (
            len(linked_source) if isinstance(linked_source, bytes) else None
        ),
        "identity_linked_history_sha256": (
            hashlib.sha256(linked_source).hexdigest()
            if isinstance(linked_source, bytes) else None
        ),
        "target_identity_linked_history_size": (
            len(linked_target) if isinstance(linked_target, bytes) else None
        ),
        "target_identity_linked_history_sha256": (
            hashlib.sha256(linked_target).hexdigest()
            if isinstance(linked_target, bytes) else None
        ),
        "source_history_prefix_match_count": int(prefix_retained),
        "source_history_prefixes_retained": unique_candidate and prefix_retained,
        "other_config_mutation_count": len(unrelated_mutations),
    }


def _pre_release_history_reasons(facts: Mapping[str, object]) -> list[str]:
    """Require one identity-linked source transcript and its exact target prefix."""

    reasons: list[str] = []
    if facts.get("identity_linked_parent_history_binding_valid") is not True:
        reasons.append("pre-release-parent-history-binding-unavailable")
    candidates = facts.get("identity_linked_parent_history_candidate_count")
    if type(candidates) is not int or candidates != 1:
        reasons.append("pre-release-identity-linked-history-not-unique")
    source_size = facts.get("identity_linked_history_size")
    source_digest = facts.get("identity_linked_history_sha256")
    target_size = facts.get("target_identity_linked_history_size")
    target_digest = facts.get("target_identity_linked_history_sha256")
    if (type(source_size) is not int or source_size < 1
            or not isinstance(source_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", source_digest)):
        reasons.append("pre-release-source-history-fingerprint-unavailable")
    elif (facts.get("identity_linked_parent_history_prefix_retained") is not True
          or type(target_size) is not int or target_size != source_size
          or target_digest != source_digest):
        reasons.append("pre-release-linked-history-copy-mismatch")
    return sorted(set(reasons))


def _target_history_query_complete(report: Mapping[str, object]) -> bool:
    """Require the selected query's fresh result and one same-request witness."""

    if (report.get("schema") != "openrepotools-bite4-target-phase/v1"
            or report.get("history_query_mode") != HISTORY_QUERY_MODE
            or report.get("support_claim") is not False):
        return False
    gate = report.get("startup_gate")
    gateway = report.get("history_query_gateway_witness")
    startup = report.get("startup_request_observation")
    arrivals = report.get("request_arrival_witness")
    if not all(isinstance(value, Mapping) for value in (
        gate, gateway, startup, arrivals,
    )):
        return False

    def sha256_hex(value: object) -> bool:
        return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None

    def zero_count(value: object) -> bool:
        return type(value) is int and value == 0

    if not (
        report.get("same_parent_uuid") is True
        and report.get("target_parent_uuid_seen") is True
        and report.get("target_parent_uuid_digest")
        == report.get("source_parent_uuid_digest")
        and sha256_hex(report.get("target_parent_uuid_digest"))
        and report.get("initialize_succeeded") is True
        and gate.get("history_query_mode") == HISTORY_QUERY_MODE
        and gate.get("history_query_allowed") is True
        and gate.get("history_query_skipped") is False
        and gate.get("terminal_task_correlation_only") is True
        and gate.get("support_claim") is False
        and gate.get("reason_codes") == []
        and report.get("history_query_sent") is True
        and report.get("history_query_read_complete") is True
        and report.get("target_process_exited") is True
        and report.get("gateway_server_fence_complete") is True
        and report.get("read_failed") is False
        and report.get("history_query_error_abort_or_tool_seen") is False
        and report.get("gateway_protocol_errors") == []
        and report.get("startup_result_count") == 1
        and report.get("startup_result_origins") == ["task-notification"]
        and report.get("startup_result_origin_overflow") is False
        and zero_count(report.get("startup_result_error_count"))
        and report.get("startup_result_parent_session_match_count") == 1
        and zero_count(report.get("startup_result_parent_session_mismatch_count"))
        and report.get("startup_result_parent_session_id_digest")
        == report.get("source_parent_uuid_digest")
        and report.get("native_task_events") == 1
        and report.get("history_query_result_count") == 1
        and report.get("history_query_exact_parent_human_result_count") == 1
        and zero_count(report.get("history_query_invalid_result_count"))
        and zero_count(report.get("history_query_unexpected_frame_count"))
        and report.get("history_query_assistant_frame_count") == 1
        and report.get("history_query_stdout_eof") is True
        and all(zero_count(report.get(name)) for name in (
            "unparsed_frames", "startup_partial_frames", "query_partial_frames",
            "startup_unexpected_frame_count",
        ))
    ):
        return False

    if not (
        startup.get("enabled") is True
        and startup.get("closed") is True
        and startup.get("overflow") is False
        and all(zero_count(startup.get(name)) for name in (
            "request_arrival_count", "messages_route_arrival_count",
            "other_route_arrival_count", "parent_arrival_count",
            "child_arrival_count", "unclassified_arrival_count",
            "in_flight_count",
        ))
        and arrivals.get("arrival_count") == 1
        and zero_count(arrivals.get("in_flight_count"))
        and arrivals.get("overflow") is False
        and arrivals.get("arrival_count_by_phase_route") == {
            "target-diagnostic-query": {"/v1/messages": 1},
        }
    ):
        return False

    nonce = report.get("history_query_nonce_sha256")
    challenge = report.get("history_query_challenge_sha256")
    result_challenge = report.get("history_query_response_challenge_sha256")
    if not (
        sha256_hex(nonce) and sha256_hex(challenge)
        and nonce != challenge and result_challenge == challenge
        and gateway.get("schema") == "two-domain-history-query-gateway-witness/v1"
        and gateway.get("request_count") == 1
        and type(gateway.get("arrival_index")) is int
        and gateway.get("arrival_index") == 1
        and all(gateway.get(name) is True for name in (
            "request_valid", "parent_request", "model_expected",
            "dummy_authorization", "nonce_present",
            "source_prompt_marker_present", "same_request_source_agent_history",
            "history_order_valid", "response_write_succeeded", "window_closed",
        ))
        and gateway.get("response_write_count") == 1
        and gateway.get("response_write_failed") is False
        and all(gateway.get(name) == 1 for name in (
            "source_agent_tool_use_count", "source_agent_tool_result_count",
            "exact_source_agent_tool_use_count", "all_tool_use_count",
            "all_tool_result_count",
        ))
        and sha256_hex(gateway.get("request_facts_digest"))
        and sha256_hex(gateway.get("response_message_id_digest"))
        and gateway.get("query_nonce_sha256") == nonce
        and gateway.get("response_challenge_sha256") == challenge
    ):
        return False
    assistant_ids = report.get("history_query_assistant_message_id_digests")
    missing_ids = report.get("history_query_assistant_message_id_missing_count")
    if (not isinstance(assistant_ids, list)
            or type(missing_ids) is not int or missing_ids not in {0, 1}):
        return False
    if missing_ids == 0:
        if assistant_ids != [gateway.get("response_message_id_digest")]:
            return False
    elif assistant_ids:
        return False
    return True


def _known_custody_failure_code(error: str) -> str | None:
    if "refuses symlinks" in error:
        return "forbidden-history-symlink"
    if "refuses hard-linked files" in error:
        return "hard-linked-history-file"
    if ("refuses non-regular files" in error or "changed type or link count" in error
            or "directory changed type" in error):
        return "forbidden-history-file-type"
    if ("changed during scan" in error or "changed during read" in error
            or "changed before read" in error or "changed during scan" in error
            or "pathname changed during scan" in error
            or "pathname changed before copy" in error):
        return "history-tree-mutated"
    # Scan/read limits and ordinary I/O failures mean evidence is unavailable;
    # they do not prove a malformed or unauthorized tree.
    if "unsafe name" in error or "unsafe final component" in error:
        return "unsafe-history-path"
    if "target tree must be empty" in error:
        return "target-volume-not-empty"
    if ("source and target manifests differ" in error
            or "copied tree does not match source" in error
            or "source copy verification failed" in error):
        return "source-target-copy-mismatch"
    if "deterministic saved edit mismatch" in error:
        return "saved-edit-mismatch"
    return None


def _internal_custody_impl(args: argparse.Namespace) -> None:
    parent_history_prefix: bytes | None = None
    if args.parent_history_prefix_stdin:
        if (not (args.internal_pre_release or args.internal_final)
                or args.parent_history_size is None
                or args.parent_history_sha256 is None):
            raise RuntimeError("parent history prefix input is not bound to custody")
        parent_history_prefix = sys.stdin.buffer.read(
            probe.MAX_HISTORY_CONTENT_BYTES + 1
        )
        if (not 0 < len(parent_history_prefix) <= probe.MAX_HISTORY_CONTENT_BYTES
                or len(parent_history_prefix) != args.parent_history_size
                or hashlib.sha256(parent_history_prefix).hexdigest()
                != args.parent_history_sha256):
            raise RuntimeError("parent history prefix input failed its source binding")
    if args.internal_copy:
        source = _manifest_summary(args.source)
        if int(source.get("history_jsonl_count", 0)) < 1:
            raise RuntimeError("two-domain source has no SDK JSONL history candidate")
        copied = probe.copy_two_domain_tree(args.source, args.target)
        target = _manifest_summary(args.target)
        result = {
            **copied,
            "source": source,
            "target": target,
            "exact_match": bool(copied.get("exact_match"))
            and source.get("manifest_digest") == target.get("manifest_digest"),
        }
        if result["exact_match"] is not True:
            raise RuntimeError("two-domain source copy verification failed")
    elif args.internal_verify:
        source = _manifest_summary(args.source)
        target = _manifest_summary(args.target)
        exact = source["manifest_digest"] == target["manifest_digest"]
        result = {
            "schema": "openrepotools-bite4-verification/v1",
            "source": source,
            "target": target,
            "exact_match": exact,
        }
        if not exact:
            raise RuntimeError("two-domain source and target manifests differ")
    elif args.internal_pre_release:
        source_entries = probe._tree_file_bytes(args.source)
        target_entries = probe._tree_file_bytes(args.target)
        source_files = {
            path: content for kind, path, content in source_entries
            if kind == "file" and content is not None
        }
        target_files = {
            path: content for kind, path, content in target_entries
            if kind == "file" and content is not None
        }
        history_facts = _history_custody_facts(
            source_files,
            target_files,
            parent_prefix=parent_history_prefix,
            parent_history_size=args.parent_history_size,
            parent_history_sha256=args.parent_history_sha256,
        )
        reasons = _pre_release_history_reasons(history_facts)
        result = {
            "schema": "openrepotools-bite4-pre-release-history/v1",
            **history_facts,
            "history_custody_reasons": reasons,
            "pre_release_history_custody_valid": not reasons,
        }
    elif args.internal_final:
        source_entries = probe._tree_file_bytes(args.source)
        target_entries = probe._tree_file_bytes(args.target)
        source_files = {
            path: content for kind, path, content in source_entries
            if kind == "file" and content is not None
        }
        target_files = {
            path: content for kind, path, content in target_entries
            if kind == "file" and content is not None
        }
        history_facts = _history_custody_facts(
            source_files,
            target_files,
            parent_prefix=parent_history_prefix,
            parent_history_size=args.parent_history_size,
            parent_history_sha256=args.parent_history_sha256,
        )
        source = _manifest_summary(args.source)
        target = _manifest_summary(args.target, require_fixture=False)
        source_edit = source.get("saved_edit_sha256")
        target_edit = target.get("saved_edit_sha256")
        saved_edit_evidence = bool(
            isinstance(source_edit, str)
            and re.fullmatch(r"[0-9a-f]{64}", source_edit)
            and isinstance(target_edit, str)
            and re.fullmatch(r"[0-9a-f]{64}", target_edit)
        )
        result = {
            "schema": "openrepotools-bite4-final-custody/v1",
            "source": source,
            "target": target,
            **history_facts,
            "saved_edit_source_sha256": source_edit,
            "saved_edit_target_sha256": target_edit,
            "saved_edit_evidence_available": saved_edit_evidence,
            "saved_edit_retained": bool(
                saved_edit_evidence and source_edit == target_edit
            ),
        }
    elif args.internal_negative_release:
        result = _negative_release_diagnostic(
            Path(args.target) / "workspace",
            binding_digest=args.binding_digest,
        )
    elif args.internal_manifest:
        result = _manifest_summary(args.source)
    else:
        raise ValueError("internal custody operation was not selected")
    print(json.dumps(result, separators=(",", ":")))


def _internal_custody(args: argparse.Namespace) -> None:
    try:
        _internal_custody_impl(args)
    except RuntimeError as exc:
        reason_code = _known_custody_failure_code(str(exc))
        if reason_code is None:
            raise
        print(json.dumps({
            "schema": "openrepotools-bite4-custody-result/v1",
            "known_violation": True,
            "reason_code": reason_code,
        }, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-python")
    parser.add_argument("--image")
    parser.add_argument("--private-artifacts", type=Path)
    parser.add_argument("--explicit-release", action="store_true")
    parser.add_argument("--internal-copy", action="store_true")
    parser.add_argument("--internal-verify", action="store_true")
    parser.add_argument("--internal-pre-release", action="store_true")
    parser.add_argument("--internal-final", action="store_true")
    parser.add_argument("--internal-negative-release", action="store_true")
    parser.add_argument("--internal-manifest", action="store_true")
    parser.add_argument("--binding-digest")
    parser.add_argument("--parent-history-size", type=int)
    parser.add_argument("--parent-history-sha256")
    parser.add_argument("--parent-history-prefix-stdin", action="store_true")
    parser.add_argument("--source", default="/source")
    parser.add_argument("--target", default="/target")
    args = parser.parse_args()
    if (args.internal_copy or args.internal_verify or args.internal_pre_release
            or args.internal_final
            or args.internal_negative_release or args.internal_manifest):
        _internal_custody(args)
        return
    private_root: Path | None = None
    try:
        report = _run_experiment(args)
        private_root = Path(args.private_artifacts)
    except BaseException as exc:
        if args.private_artifacts:
            candidate = Path(os.path.abspath(os.fspath(args.private_artifacts)))
            if candidate.is_dir() and not candidate.is_symlink():
                private_root = candidate
        reason_code = exc.code if isinstance(exc, KnownViolation) else "preflight-or-arm-incomplete"
        report = {
            "schema": "openrepotools-bite4-two-domain-report/v1",
            "experiment": "bounded-two-domain-diagnostic",
            "diagnostic_status": "FAIL" if isinstance(exc, KnownViolation) else "INCONCLUSIVE",
            "bite5_decision": "pending-review",
            "reason_codes": [reason_code],
            "support_claim": False,
            "production_disposition": "unsupported",
        }
    if private_root is not None:
        try:
            _write_private_report(private_root / "report.json", report)
        except BaseException:
            report = {
                "schema": "openrepotools-bite4-two-domain-report/v1",
                "experiment": "bounded-two-domain-diagnostic",
                "diagnostic_status": "INCONCLUSIVE",
                "bite5_decision": "pending-review",
                "reason_codes": ["private-report-write-incomplete"],
                "support_claim": False,
                "production_disposition": "unsupported",
            }
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    if report.get("diagnostic_status") == "FAIL":
        raise SystemExit(1)
    if report.get("diagnostic_status") != "OBSERVED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
