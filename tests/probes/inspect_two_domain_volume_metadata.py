#!/usr/bin/env python3
"""Bounded, stat-only inventory for a separately mounted evidence volume.

The default mode runs inside an isolated container with /evidence mounted
read-only. It never reads file contents. Its complete report contains private
relative paths and must be captured into a mode-0600 private artifact. Use
--public-from on that private report to emit only the path-free summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import time
from typing import Any


SCHEMA = "openrepotools.bite4.volume-metadata.v1"
MAX_FILES = 128
MAX_ENTRIES = 512
MAX_DEPTH = 12
MAX_PATH_BYTES = 4096
MAX_WALL_SECONDS = 8.0
MAX_OUTPUT_BYTES = 64 * 1024
OVERSIZE_BYTES = 65_536
_ZERO_FLAGS = getattr(os, "O_CLOEXEC", 0)
_REFUSAL_CODES = {
    "metadata-walltime-limit", "metadata-path-limit", "metadata-path-shape",
    "metadata-depth-limit", "metadata-nofollow-unavailable",
    "metadata-root-open-failed", "metadata-root-not-directory",
    "metadata-directory-read-failed", "metadata-entry-limit",
    "metadata-entry-stat-failed", "metadata-symlink-entry",
    "metadata-directory-open-failed", "metadata-directory-changed",
    "metadata-nonregular-entry", "metadata-hardlink-entry",
    "metadata-file-limit", "metadata-file-stat-failed",
    "metadata-file-changed", "metadata-file-revalidation-failed",
    "metadata-file-mutated", "metadata-directory-revalidation-failed",
    "metadata-directory-mutated", "metadata-output-limit",
    "metadata-io-refused",
}


class MetadataRefusal(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_uid,
        value.st_gid,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _check_deadline(deadline: float) -> None:
    if time.monotonic() > deadline:
        raise MetadataRefusal("metadata-walltime-limit")


def _encoded_path(path: str) -> bytes:
    raw = os.fsencode(path)
    if len(raw) > MAX_PATH_BYTES:
        raise MetadataRefusal("metadata-path-limit")
    return raw


def _path_child(parent: str, name: str) -> str:
    if not isinstance(name, str) or name in {"", ".", ".."} or "/" in name:
        raise MetadataRefusal("metadata-path-shape")
    path = name if not parent else parent + "/" + name
    _encoded_path(path)
    if path.count("/") + 1 > MAX_DEPTH:
        raise MetadataRefusal("metadata-depth-limit")
    return path


def _hash_paths(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in sorted(entries, key=lambda item: os.fsencode(item["path"])):
        raw = os.fsencode(row["path"])
        digest.update(len(raw).to_bytes(4, "big"))
        digest.update(raw)
    return digest.hexdigest()


def _hash_metadata(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in sorted(entries, key=lambda item: os.fsencode(item["path"])):
        canonical = json.dumps(
            row, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
        digest.update(len(canonical).to_bytes(4, "big"))
        digest.update(canonical)
    return digest.hexdigest()


def _public_summary(
    entries: list[dict[str, Any]], total_bytes: int, max_file_size: int,
) -> dict[str, Any]:
    files = [row for row in entries if row["kind"] == "file"]
    oversized = [row for row in files if row["size"] > OVERSIZE_BYTES]
    category = "oversized-files-observed" if oversized else "no-file-above-65536"
    return {
        "schema": SCHEMA,
        "status": "complete",
        "category": category,
        "entry_count": len(entries),
        "file_count": len(files),
        "directory_count": len(entries) - len(files),
        "total_file_bytes": total_bytes,
        "max_file_bytes": max_file_size,
        "over_65536_file_count": len(oversized),
        "entry_path_sha256": _hash_paths(entries),
        "over_65536_path_sha256": _hash_paths(oversized),
        "metadata_sha256": _hash_metadata(entries),
    }


def scan_tree(
    root: str = "/evidence", *, wall_seconds: float = MAX_WALL_SECONDS,
    _deadline: float | None = None,
) -> dict[str, Any]:
    """Return bounded stat metadata, refusing unsafe or changing trees.

    File descriptors are opened with no-follow semantics and kept until all
    entries have been revalidated. O_PATH is required for regular files so
    metadata inspection does not require or perform a content read.
    """
    deadline = _deadline if _deadline is not None else time.monotonic() + wall_seconds
    if not hasattr(os, "O_PATH") or not hasattr(os, "O_NOFOLLOW"):
        raise MetadataRefusal("metadata-nofollow-unavailable")
    root_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW | _ZERO_FLAGS
    try:
        root_fd = os.open(root, root_flags)
    except OSError as exc:
        raise MetadataRefusal("metadata-root-open-failed") from exc

    open_fds: list[int] = [root_fd]
    directories: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    total_bytes = 0
    max_file_size = 0
    entry_count = 0
    file_count = 0
    root_before = os.fstat(root_fd)
    if not stat.S_ISDIR(root_before.st_mode):
        os.close(root_fd)
        raise MetadataRefusal("metadata-root-not-directory")
    directories.append({
        "fd": root_fd,
        "path": "",
        "parent_fd": None,
        "name": root,
        "signature": _signature(root_before),
        "root": True,
    })
    pending: list[tuple[int, str, int]] = [(root_fd, "", 0)]
    try:
        while pending:
            _check_deadline(deadline)
            directory_fd, parent_path, depth = pending.pop()
            try:
                iterator = os.scandir(directory_fd)
            except OSError as exc:
                raise MetadataRefusal("metadata-directory-read-failed") from exc
            with iterator:
                for item in iterator:
                    _check_deadline(deadline)
                    entry_count += 1
                    if entry_count > MAX_ENTRIES:
                        raise MetadataRefusal("metadata-entry-limit")
                    path = _path_child(parent_path, item.name)
                    try:
                        before = os.stat(item.name, dir_fd=directory_fd, follow_symlinks=False)
                    except OSError as exc:
                        raise MetadataRefusal("metadata-entry-stat-failed") from exc

                    if stat.S_ISLNK(before.st_mode):
                        raise MetadataRefusal("metadata-symlink-entry")
                    if stat.S_ISDIR(before.st_mode):
                        child_depth = depth + 1
                        if child_depth > MAX_DEPTH:
                            raise MetadataRefusal("metadata-depth-limit")
                        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW | _ZERO_FLAGS
                        try:
                            child_fd = os.open(item.name, flags, dir_fd=directory_fd)
                            open_fds.append(child_fd)
                            opened = os.fstat(child_fd)
                        except OSError as exc:
                            raise MetadataRefusal("metadata-directory-open-failed") from exc
                        if not stat.S_ISDIR(opened.st_mode) or _signature(before) != _signature(opened):
                            raise MetadataRefusal("metadata-directory-changed")
                        directories.append({
                            "fd": child_fd,
                            "path": path,
                            "parent_fd": directory_fd,
                            "name": item.name,
                            "signature": _signature(opened),
                            "root": False,
                        })
                        entries.append({"path": path, "kind": "directory", "size": opened.st_size})
                        pending.append((child_fd, path, child_depth))
                        continue

                    if not stat.S_ISREG(before.st_mode):
                        raise MetadataRefusal("metadata-nonregular-entry")
                    if before.st_nlink != 1:
                        raise MetadataRefusal("metadata-hardlink-entry")
                    file_count += 1
                    if file_count > MAX_FILES:
                        raise MetadataRefusal("metadata-file-limit")
                    try:
                        file_fd = os.open(item.name, os.O_PATH | os.O_NOFOLLOW | _ZERO_FLAGS, dir_fd=directory_fd)
                        open_fds.append(file_fd)
                        opened = os.fstat(file_fd)
                        named = os.stat(item.name, dir_fd=directory_fd, follow_symlinks=False)
                    except OSError as exc:
                        raise MetadataRefusal("metadata-file-stat-failed") from exc
                    if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                            or _signature(before) != _signature(opened)
                            or _signature(opened) != _signature(named)):
                        raise MetadataRefusal("metadata-file-changed")
                    row = {"path": path, "kind": "file", "size": opened.st_size}
                    entries.append(row)
                    files.append({
                        "fd": file_fd,
                        "parent_fd": directory_fd,
                        "name": item.name,
                        "signature": _signature(opened),
                        "row": row,
                    })
                    total_bytes += opened.st_size
                    max_file_size = max(max_file_size, opened.st_size)

        _check_deadline(deadline)
        for record in files:
            _check_deadline(deadline)
            try:
                current_fd = os.fstat(record["fd"])
                current_path = os.stat(
                    record["name"], dir_fd=record["parent_fd"], follow_symlinks=False,
                )
            except OSError as exc:
                raise MetadataRefusal("metadata-file-revalidation-failed") from exc
            _check_deadline(deadline)
            if (_signature(current_fd) != record["signature"]
                    or _signature(current_path) != record["signature"]):
                raise MetadataRefusal("metadata-file-mutated")
        for record in directories:
            _check_deadline(deadline)
            try:
                current_fd = os.fstat(record["fd"])
                if record["root"]:
                    current_path = os.stat(root, follow_symlinks=False)
                else:
                    current_path = os.stat(
                        record["name"], dir_fd=record["parent_fd"], follow_symlinks=False,
                    )
            except OSError as exc:
                raise MetadataRefusal("metadata-directory-revalidation-failed") from exc
            _check_deadline(deadline)
            if (_signature(current_fd) != record["signature"]
                    or _signature(current_path) != record["signature"]):
                raise MetadataRefusal("metadata-directory-mutated")

        _check_deadline(deadline)
        files.sort(key=lambda row: os.fsencode(row["row"]["path"]))
        entries.sort(key=lambda row: os.fsencode(row["path"]))
        public = _public_summary(entries, total_bytes, max_file_size)
        _check_deadline(deadline)
        private = {
            "entries": entries,
            "over_65536_files": [
                row for row in entries
                if row["kind"] == "file" and row["size"] > OVERSIZE_BYTES
            ],
            "total_file_bytes": total_bytes,
            "max_file_bytes": max_file_size,
            "metadata_sha256": public["metadata_sha256"],
        }
        _check_deadline(deadline)
        return {"schema": SCHEMA, "status": "complete", "private": private, "public": public}
    finally:
        for fd in reversed(open_fds):
            try:
                os.close(fd)
            except OSError:
                pass


def _refusal_report(code: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "inconclusive",
        "private": {"reason_code": code},
        "public": {
            "schema": SCHEMA,
            "status": "inconclusive",
            "category": "metadata-scan-refused",
            "reason_code": code,
        },
    }


def _emit_json(value: dict[str, Any], *, deadline: float | None = None) -> bool:
    timed_out = False
    if deadline is not None:
        try:
            _check_deadline(deadline)
        except MetadataRefusal:
            timed_out = True
            value = _refusal_report("metadata-walltime-limit")
    encoded = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii") + b"\n"
    if deadline is not None:
        try:
            _check_deadline(deadline)
        except MetadataRefusal:
            timed_out = True
            encoded = json.dumps(
                _refusal_report("metadata-walltime-limit"), ensure_ascii=True,
                sort_keys=True, separators=(",", ":"), allow_nan=False,
            ).encode("ascii") + b"\n"
    if len(encoded) > MAX_OUTPUT_BYTES:
        encoded = json.dumps(
            _refusal_report("metadata-output-limit"), ensure_ascii=True,
            sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("ascii") + b"\n"
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
        return False
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()
    return not timed_out


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate-json-key")
        result[key] = value
    return result


def _read_public_projection(path: str) -> dict[str, Any]:
    flags = os.O_RDONLY | os.O_NOFOLLOW | _ZERO_FLAGS
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise MetadataRefusal("metadata-report-open-failed") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_OUTPUT_BYTES:
            raise MetadataRefusal("metadata-report-shape")
        chunks: list[bytes] = []
        remaining = MAX_OUTPUT_BYTES + 1
        while remaining > 0:
            chunk = os.read(fd, min(8192, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        named = os.stat(path, follow_symlinks=False)
        if (_signature(before) != _signature(after)
                or _signature(after) != _signature(named)
                or len(raw) > MAX_OUTPUT_BYTES):
            raise MetadataRefusal("metadata-report-mutated")
    finally:
        os.close(fd)
    try:
        report = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise MetadataRefusal("metadata-report-invalid") from exc
    status_value = report.get("status") if isinstance(report, dict) else None
    if (not isinstance(report, dict) or set(report) != {"schema", "status", "private", "public"}
            or report.get("schema") != SCHEMA
            or not isinstance(status_value, str)
            or status_value not in {"complete", "inconclusive"}
            or not isinstance(report.get("private"), dict)
            or not isinstance(report.get("public"), dict)):
        raise MetadataRefusal("metadata-report-invalid")
    public = report["public"]
    private = report["private"]
    if public.get("schema") != SCHEMA or public.get("status") != report["status"]:
        raise MetadataRefusal("metadata-public-shape")
    if report["status"] == "inconclusive":
        code = private.get("reason_code")
        expected = _refusal_report(code) if isinstance(code, str) and code in _REFUSAL_CODES else None
        if (set(private) != {"reason_code"} or expected is None
                or public != expected["public"]):
            raise MetadataRefusal("metadata-public-shape")
        return public

    if (set(private) != {"entries", "over_65536_files", "total_file_bytes",
                         "max_file_bytes", "metadata_sha256"}
            or not isinstance(private.get("entries"), list)
            or len(private["entries"]) > MAX_ENTRIES):
        raise MetadataRefusal("metadata-private-shape")
    entries = private["entries"]
    seen: set[bytes] = set()
    files: list[dict[str, Any]] = []
    total = 0
    maximum = 0
    for row in entries:
        kind = row.get("kind") if isinstance(row, dict) else None
        if (not isinstance(row, dict) or set(row) != {"path", "kind", "size"}
                or not isinstance(row.get("path"), str)
                or not isinstance(kind, str)
                or kind not in {"file", "directory"}
                or isinstance(row.get("size"), bool)
                or not isinstance(row.get("size"), int) or row["size"] < 0):
            raise MetadataRefusal("metadata-private-shape")
        raw_path = _encoded_path(row["path"])
        parts = row["path"].split("/")
        if (not raw_path or row["path"].startswith("/")
                or len(parts) > MAX_DEPTH
                or any(part in {"", ".", ".."} for part in parts)
                or raw_path in seen):
            raise MetadataRefusal("metadata-private-shape")
        seen.add(raw_path)
        if row["kind"] == "file":
            files.append(row)
            total += row["size"]
            maximum = max(maximum, row["size"])
    if len(files) > MAX_FILES:
        raise MetadataRefusal("metadata-private-shape")
    oversized = [row for row in entries if row["kind"] == "file" and row["size"] > OVERSIZE_BYTES]
    if (private.get("over_65536_files") != oversized
            or private.get("total_file_bytes") != total
            or isinstance(private.get("total_file_bytes"), bool)
            or private.get("max_file_bytes") != maximum
            or isinstance(private.get("max_file_bytes"), bool)
            or private.get("metadata_sha256") != _hash_metadata(entries)):
        raise MetadataRefusal("metadata-private-inconsistent")
    expected_public = _public_summary(entries, total, maximum)
    if public != expected_public:
        raise MetadataRefusal("metadata-public-inconsistent")
    return public


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--public-from", metavar="PRIVATE_JSON")
    parser.add_argument("--root", default="/evidence")
    args = parser.parse_args(argv)

    if args.public_from:
        try:
            public = _read_public_projection(args.public_from)
        except MetadataRefusal as exc:
            _emit_json({
                "schema": SCHEMA,
                "status": "inconclusive",
                "category": "metadata-public-projection-refused",
                "reason_code": exc.code,
            })
            return 2
        _emit_json(public)
        return 0 if public["status"] == "complete" else 2

    deadline = time.monotonic() + MAX_WALL_SECONDS
    try:
        report = scan_tree(args.root, _deadline=deadline)
    except MetadataRefusal as exc:
        _emit_json(_refusal_report(exc.code))
        return 2
    except OSError:
        _emit_json(_refusal_report("metadata-io-refused"))
        return 2
    if not _emit_json(report, deadline=deadline):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
