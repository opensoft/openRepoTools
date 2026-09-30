# SPDX-License-Identifier: Apache-2.0
"""Read-only native Claude history witness for the shared-session CLI lane.

The source custodian must first prove exit and exclusion.  This reader then
binds the saved parent and every discovered native child to the exact admitted
session.  It never edits a transcript or interprets a model response as task
completion.  An invalid or unstable tail is an incomplete history, not a
completed conversation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import select
import secrets
import stat
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from lane_managed_state import ManagedStateError


MAX_HISTORY_FILE_BYTES = 16 * 1024 * 1024
MAX_HISTORY_TOTAL_BYTES = 64 * 1024 * 1024
MAX_HISTORY_FILES = 128
MAX_HISTORY_ENTRIES = 512
MAX_HISTORY_DEPTH = 12
_AGENT_NAME = re.compile(r"agent-([^/\\\x00]{1,256})\.(jsonl|meta\.json)\Z")
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)


def _fail(code: str, message: str) -> None:
    raise ManagedStateError(code, message)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _signature(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _parse_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError, RecursionError) as exc:
        _fail("unsupported", "%s contains invalid JSON" % label)
    if not isinstance(value, dict):
        _fail("unsupported", "%s is not a JSON object" % label)
    return value


def _records(raw: bytes, session_id: str, *, agent_id: str | None = None) -> list[dict[str, Any]]:
    label = "native child history" if agent_id else "native parent history"
    if not raw or not raw.endswith(b"\n"):
        _fail("unsupported", "%s has an incomplete final record" % label)
    records: list[dict[str, Any]] = []
    identity_seen = False
    for line in raw.splitlines():
        if not line.strip():
            continue
        record = _parse_object(line, label)
        if "sessionId" in record:
            if record["sessionId"] != session_id:
                _fail("ownership-conflict", "%s belongs to another parent" % label)
            if agent_id is None:
                identity_seen = True
        if "agentId" in record:
            if agent_id is None or record["agentId"] != agent_id:
                _fail("ownership-conflict", "%s names another agent" % label)
        if agent_id is not None and record.get("sessionId") == session_id and record.get("agentId") == agent_id:
            identity_seen = True
        records.append(record)
    if not identity_seen:
        _fail("unsupported", "%s lacks exact top-level identity" % label)
    return records


def _agent_tool_ids(records: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for record in records:
        if record.get("type") != "assistant":
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if (isinstance(item, dict) and item.get("type") == "tool_use" and
                    item.get("name") in {"Agent", "Task"} and
                    isinstance(item.get("id"), str) and item["id"]):
                if item["id"] in result:
                    # The pinned saved corpus contains one occurrence per
                    # invocation.  Repeated streaming serialization has not
                    # been measured, so it is an ambiguous supported-shape
                    # boundary rather than evidence of a second execution.
                    _fail("unsupported", "repeated native Agent tool use is ambiguous")
                result.add(item["id"])
    return result


def _bounded_command(argv: list[str], *, limit: int, timeout: float) -> bytes:
    """Read only bounded git metadata; a stalled or verbose command refuses."""
    process = subprocess.Popen(argv, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL)
    chunks: list[bytes] = []
    total = 0
    deadline = time.monotonic() + timeout
    try:
        assert process.stdout is not None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _fail("unknown", "registered worktree inspection timed out")
            ready, _, _ = select.select([process.stdout], [], [], remaining)
            if not ready:
                _fail("unknown", "registered worktree inspection timed out")
            chunk = os.read(process.stdout.fileno(), min(65536, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                _fail("unsupported", "registered worktree inventory exceeds bound")
        if process.wait(timeout=max(0.001, deadline - time.monotonic())) != 0:
            _fail("unknown", "registered worktree inspection failed")
        return b"".join(chunks)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if process.stdout is not None:
            process.stdout.close()


class _HistoryTree:
    """Descriptor-relative no-follow reads with bounded, stable snapshots."""

    def __init__(self, root: Path):
        self.root = root
        self.files = 0
        self.entries = 0
        self.bytes = 0
        try:
            self.fd = os.open(str(root), _DIR_FLAGS)
        except OSError as exc:
            _fail("unknown", "canonical projects store is unreadable")

    def close(self) -> None:
        os.close(self.fd)

    def _directory(self, components: tuple[str, ...]) -> int:
        current = os.dup(self.fd)
        try:
            for component in components:
                if component in {"", ".", ".."} or "/" in component or "\\" in component:
                    _fail("invalid", "history path component is invalid")
                following = os.open(component, _DIR_FLAGS, dir_fd=current)
                os.close(current)
                current = following
            return current
        except BaseException:
            os.close(current)
            raise

    def names(self, components: tuple[str, ...]) -> list[str]:
        try:
            directory = self._directory(components)
            try:
                before = os.fstat(directory)
                names = sorted(os.listdir(directory))
                after = os.fstat(directory)
            finally:
                os.close(directory)
        except OSError:
            _fail("unknown", "native history directory is unreadable or linked")
        if _signature(before) != _signature(after):
            _fail("unknown", "native history directory changed during scan")
        self.entries += len(names)
        if self.entries > MAX_HISTORY_ENTRIES:
            _fail("unsupported", "native history scan exceeds entry bound")
        return names

    def kind(self, components: tuple[str, ...]) -> str:
        try:
            directory = self._directory(components[:-1])
            try:
                info = os.stat(components[-1], dir_fd=directory, follow_symlinks=False)
            finally:
                os.close(directory)
        except FileNotFoundError:
            raise
        except OSError:
            _fail("unknown", "native history entry is unreadable")
        if stat.S_ISLNK(info.st_mode):
            _fail("invalid", "native history contains a symlink")
        if stat.S_ISDIR(info.st_mode):
            return "directory"
        if stat.S_ISREG(info.st_mode):
            if info.st_nlink != 1:
                _fail("invalid", "native history contains a hardlink")
            return "file"
        _fail("invalid", "native history contains a special file")

    def read(self, components: tuple[str, ...]) -> bytes:
        self.files += 1
        if self.files > MAX_HISTORY_FILES:
            _fail("unsupported", "native history scan exceeds file bound")
        try:
            directory = self._directory(components[:-1])
            try:
                fd = os.open(components[-1], _FILE_FLAGS, dir_fd=directory)
                try:
                    before = os.fstat(fd)
                    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                        _fail("invalid", "native history file is linked or not regular")
                    if before.st_size > MAX_HISTORY_FILE_BYTES:
                        _fail("unsupported", "native history file exceeds size bound")
                    chunks: list[bytes] = []
                    remaining = MAX_HISTORY_FILE_BYTES + 1
                    while remaining:
                        chunk = os.read(fd, min(65536, remaining))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        remaining -= len(chunk)
                    raw = b"".join(chunks)
                    after = os.fstat(fd)
                    path_info = os.stat(components[-1], dir_fd=directory,
                                        follow_symlinks=False)
                finally:
                    os.close(fd)
            finally:
                os.close(directory)
        except OSError:
            _fail("unknown", "native history file is unreadable or changed")
        if (len(raw) != before.st_size or _signature(before) != _signature(after)
                or _signature(after) != _signature(path_info)):
            _fail("unknown", "native history file changed during read")
        self.bytes += len(raw)
        if self.bytes > MAX_HISTORY_TOTAL_BYTES:
            _fail("unsupported", "native history scan exceeds byte bound")
        return raw


class ClaudeCliHistoryWitness:
    """Supply T053's history witness from native bytes and registered claims.

    ``binding`` comes from the trusted source provider after source exclusion.
    It must add ``source_profile_ref`` and immutable admitted ``source_cwd`` to
    T053's source binding.  The ledger is queried again for worktree claims and
    reservations; caller supplied paths or a model-created completion flag have
    no authority.
    """

    def __init__(self, ledger: Any, profile_resolver: Any, *,
                 next_watermark: Callable[[int], int] | None = None):
        self.ledger = ledger
        self.profile_resolver = profile_resolver
        self.next_watermark = next_watermark

    def _worktrees(self, binding: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
        with self.ledger._locked() as owner:
            state = self.ledger._load(owner)
            operation = next((op for op in state["operations"].values()
                              if op["source_runtime_incarnation"] == binding["source_runtime_incarnation"]
                              and op["parent_uuid"] == binding["parent_uuid"]
                              and op["source_claim_generation"] == binding["source_claim_generation"]), None)
            if operation is None or operation.get("source_exclusion") is None:
                _fail("stale-generation", "history has no excluded source operation")
            if (operation["source_profile_ref"] != binding["source_profile_ref"] or
                    sorted(operation["worktree_ids"]) != sorted(binding["worktree_ids"]) or
                    operation["owner_generation"] != binding["owner_generation"] or
                    operation["lineage_id"] != binding["lineage_id"] or
                    operation["lineage_generation"] != binding["lineage_generation"]):
                _fail("ownership-conflict", "history binding differs from source operation")
            rows = self.ledger._registered_worktrees(
                binding["lineage_id"], binding["lineage_generation"],
                binding["parent_uuid"], binding["owner_generation"])
            if [row["resource_id"] for row in rows] != sorted(binding["worktree_ids"]):
                _fail("stale-generation", "registered worktree set changed")
            reservations = {resource: job for resource, job in state["reservations"].items()
                            if resource in binding["worktree_ids"]}
        observed_rows = []
        for row in rows:
            path = Path(row["path"])
            if path.is_symlink() or not path.is_dir() or path.resolve(strict=True) != path:
                _fail("unknown", "registered worktree path is unavailable or linked")
            try:
                top = _bounded_command(
                    ["git", "--no-optional-locks", "-C", str(path), "rev-parse",
                     "--show-toplevel"],
                    limit=4096, timeout=5)
                common = _bounded_command(
                    ["git", "--no-optional-locks", "-C", str(path), "rev-parse",
                     "--path-format=absolute", "--git-common-dir"],
                    limit=4096, timeout=5)
                inventory = _bounded_command(
                    ["git", "--no-optional-locks", "-C", str(path), "status",
                     "--porcelain=v1", "-z", "--untracked-files=all"],
                    limit=MAX_HISTORY_TOTAL_BYTES, timeout=10)
            except OSError:
                _fail("unknown", "registered worktree inventory is unavailable")
            try:
                observed_top = top.decode("utf-8").strip()
                observed_common = common.decode("utf-8").strip()
            except UnicodeError:
                _fail("unknown", "registered worktree Git identity is malformed")
            if observed_top != row["path"] or observed_common != row["repository"]:
                _fail("ownership-conflict", "registered project Git identity changed")
            observed_rows.append({**row, "dirty_inventory_sha256":
                                  hashlib.sha256(inventory).hexdigest()})
        if sum(os.path.commonpath((row["path"], binding["source_cwd"])) == row["path"]
               for row in rows) != 1:
            _fail("ownership-conflict", "source cwd is not one registered worktree")
        return observed_rows, reservations

    def history_manifest(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        parent = binding.get("parent_uuid")
        profile_ref = binding.get("source_profile_ref")
        cwd = binding.get("source_cwd")
        if not isinstance(parent, str) or not isinstance(profile_ref, str) or not isinstance(cwd, str):
            _fail("invalid", "history binding lacks exact parent, source profile or cwd")
        rows, reservations = self._worktrees(binding)
        profile = self.profile_resolver.resolve(profile_ref)
        evidence = self.profile_resolver.verify_transcript(profile, parent, cwd)
        transcript = evidence["transcript"]
        if not transcript["exists"] or transcript["path"] is None:
            _fail("unsupported", "exact parent native history is missing")
        store = Path(transcript["store"])
        project = Path(transcript["project"])
        if project.parent != store or Path(transcript["path"]) != project / (parent + ".jsonl"):
            _fail("ownership-conflict", "native history path is not canonical")
        tree = _HistoryTree(store)
        try:
            project_key = project.name
            parent_raw = tree.read((project_key, parent + ".jsonl"))
            parent_records = _records(parent_raw, parent)
            parent_tool_ids = _agent_tool_ids(parent_records)
            child_rows: list[dict[str, Any]] = []
            companion = (project_key, parent)
            try:
                companion_kind = tree.kind(companion)
            except FileNotFoundError:
                companion_kind = "missing"
            if companion_kind == "directory":
                pending = [(companion, 0)]
                while pending:
                    directory, depth = pending.pop()
                    for name in tree.names(directory):
                        entry = directory + (name,)
                        kind = tree.kind(entry)
                        if kind == "directory":
                            if depth >= MAX_HISTORY_DEPTH:
                                _fail("unsupported", "native child history exceeds depth bound")
                            pending.append((entry, depth + 1))
                            continue
                        match = _AGENT_NAME.fullmatch(name)
                        if match:
                            child_rows.append({"components": entry, "agent_id": match.group(1),
                                               "kind": match.group(2)})
                        elif name.endswith((".jsonl", ".meta.json")):
                            _fail("unsupported", "unrecognized native child history file")
            elif companion_kind != "missing":
                _fail("invalid", "native companion history is not a directory")
            paired: dict[tuple[str, ...], dict[str, tuple[str, ...]]] = {}
            for row in child_rows:
                key = row["components"][:-1] + (row["agent_id"],)
                pair = paired.setdefault(key, {})
                if row["kind"] in pair:
                    _fail("ownership-conflict", "duplicate native child file")
                pair[row["kind"]] = row["components"]
            parent_by_agent: dict[str, set[str]] = {"": parent_tool_ids}
            manifest_children = []
            for key in sorted(paired):
                pair = paired[key]
                if set(pair) != {"jsonl", "meta.json"}:
                    _fail("unsupported", "native child transcript or sidecar is missing")
                agent_id = key[-1]
                metadata_raw = tree.read(pair["meta.json"])
                metadata = _parse_object(metadata_raw, "native child metadata")
                tool_id = metadata.get("toolUseId")
                parent_agent = metadata.get("parentAgentId", "")
                if (not isinstance(tool_id, str) or not tool_id or len(tool_id) > 256 or
                        not isinstance(parent_agent, str) or len(parent_agent) > 256):
                    _fail("unsupported", "native child linkage is missing or malformed")
                child_raw = tree.read(pair["jsonl"])
                child_records = _records(child_raw, parent, agent_id=agent_id)
                if agent_id in parent_by_agent:
                    _fail("ownership-conflict", "native child agent ID is duplicated")
                parent_by_agent[agent_id] = _agent_tool_ids(child_records)
                manifest_children.append({
                    "agent_id": agent_id, "parent_agent_id": parent_agent,
                    "tool_use_id": tool_id,
                    "history_path": "/".join(pair["jsonl"]),
                    "history_sha256": hashlib.sha256(child_raw).hexdigest(),
                    "metadata_sha256": hashlib.sha256(metadata_raw).hexdigest(),
                    "records": len(child_records),
                })
            used_links: set[tuple[str, str]] = set()
            for child in manifest_children:
                parent_agent = child["parent_agent_id"]
                link = (parent_agent, child["tool_use_id"])
                if parent_agent not in parent_by_agent or child["tool_use_id"] not in parent_by_agent[parent_agent]:
                    _fail("ownership-conflict", "native child has no parent Agent tool use")
                if link in used_links:
                    _fail("ownership-conflict", "native children share one parent tool use")
                used_links.add(link)
            if sum(len(ids) for ids in parent_by_agent.values()) != len(used_links):
                _fail("unsupported", "parent has an unaccounted native child tool use")
            manifest = {
                "schema": 1, "parent_uuid": parent, "projects_store": str(store),
                "project": str(project), "source_cwd": str(Path(cwd).resolve(strict=True)),
                "parent": {"path": str(Path(transcript["path"])),
                           "sha256": hashlib.sha256(parent_raw).hexdigest(),
                           "records": len(parent_records)},
                "children": manifest_children,
            }
        finally:
            tree.close()
        # Dirty/untracked names are observed, but live admitted jobs can add
        # outputs after this read.  Those names belong in this observation's
        # digest, not the stable release comparison of claim/reservation
        # identity.  No workspace file is rewritten or inferred complete.
        inventory = [row["dirty_inventory_sha256"] for row in rows]
        worktree = {"schema": 1, "parent_uuid": parent,
                    "claims": [{key: value for key, value in row.items()
                                if key != "dirty_inventory_sha256"} for row in rows],
                    "reservations": reservations}
        with self.ledger._locked() as owner:
            state = self.ledger._load(owner)
            current_rows = self.ledger._registered_worktrees(
                binding["lineage_id"], binding["lineage_generation"],
                parent, binding["owner_generation"])
            if current_rows != [{key: value for key, value in row.items()
                                 if key != "dirty_inventory_sha256"} for row in rows]:
                _fail("stale-generation", "registered worktree claims changed during history read")
            if {resource: job for resource, job in state["reservations"].items()
                    if resource in binding["worktree_ids"]} != reservations:
                _fail("stale-generation", "worktree reservations changed during history read")
            floor = state["observation_watermark"]
        watermark = (self.next_watermark(floor) if self.next_watermark is not None
                     else max(time.monotonic_ns(), floor + 1))
        if type(watermark) is not int or watermark <= floor:
            _fail("stale-generation", "history observation watermark did not advance")
        result = {
            "witness_id": secrets.token_hex(16),
            "parent_uuid": parent,
            "manifest_digest": _digest(manifest),
            "worktree_manifest_digest": _digest(worktree),
            "observation_watermark": watermark,
            "complete": True,
        }
        result["witness_digest"] = _digest({"witness": result,
                                            "dirty_inventory_observation": inventory})
        return result
