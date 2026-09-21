# SPDX-License-Identifier: Apache-2.0
"""Private, local durable state for explicitly managed lanes.

This module deliberately has no knowledge of the human-facing lane register.
The installed ``lanes-edit.sh`` helper is the only authority for resolving a
workspace; the state kept here is execution state under that workspace's Git
common directory.  The implementation uses only the Python standard library
so that the optional managed supervisor can be imported without any runtime or
SDK dependency.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Mapping, Optional, Sequence, Tuple


# State is intentionally bounded.  Control frames have the same one MiB
# boundary, and keeping local records below that boundary prevents a malformed
# file from becoming an unbounded memory allocation during recovery.
MAX_JSON_BYTES = 1024 * 1024
MAX_COMPONENT_LENGTH = 128
HELPER_TIMEOUT_SECONDS = 5.0

# The native-lineage boundary is shared by every managed durable record.  Keep
# this definition in the state layer so the daemon, controller, and installed
# front doors cannot slowly grow subtly different meanings for ``schema``.
# ``schema``/version 1 is the superseded independent-worker prototype and is
# deliberately not an alias for this record shape.
NATIVE_SCHEMA_VERSION = 2
NATIVE_ARCHITECTURE = "native-coordinator-lineage"
NATIVE_RECORD_MARKER = {
    "schema_version": NATIVE_SCHEMA_VERSION,
    "architecture": NATIVE_ARCHITECTURE,
}
LEGACY_SCHEMA_VERSION = 1
# New callers should use the explicit native names.  SCHEMA_VERSION remains a
# useful public spelling for the current durable contract.
SCHEMA_VERSION = NATIVE_SCHEMA_VERSION

_LANE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,%d}\Z" %
                      (MAX_COMPONENT_LENGTH - 1))
_COMPONENT_RE = _LANE_RE
_STATE_DIR_NAME = "openrepotools-managed"
_LOCK_NAME = "state.lock"
_OWNER_NAME = "owner.json"
_CLAIMS_NAME = "claims.json"
_RUNTIME_NAME = "runtime.json"
_GENERATION_NAME = "generation.json"
_RECOVERY_NAME = "recovery.json"
_ADOPTIONS_NAME = "native-adoptions.json"
_PROCESS_DOMAIN_RE = re.compile(
    r"linux:[0-9A-Fa-f]+:pid:\[[0-9]+\]\Z"
)

_NATIVE_ADOPTION_PHASES = frozenset({
    "prepared", "claim-cas-pending", "claim-transferred",
    "controller-committed", "indeterminate",
})
_NATIVE_ADOPTION_ENTRY_FIELDS = frozenset({
    "schema_version", "architecture", "record_kind",
    "adoption_id", "archive_id", "archive_digest", "operation_id",
    "owner_generation", "expected_daemon_id", "source_identity",
    "source_claim", "target_claim", "source_claim_digest",
    "target_claim_digest", "evidence_digest", "runtime_identity_digest",
    "evidence_reference", "intent_digest", "phase",
    "controller_commit_digest",
})
_NATIVE_ADOPTION_IMMUTABLE_FIELDS = frozenset(
    _NATIVE_ADOPTION_ENTRY_FIELDS - {
        "intent_digest", "phase", "controller_commit_digest",
        "schema_version", "architecture", "record_kind",
    }
)
_NATIVE_ADOPTION_CONTROLLER_FIELDS = frozenset({
    "adoption_id", "intent_digest", "archive_id", "archive_digest",
    "target_claim_digest", "phase",
})
_NATIVE_SOURCE_IDENTITY_FIELDS = frozenset({
    "owner_generation", "lineage_id", "lineage_generation", "session_uuid",
    "runner_incarnation", "invocation_id",
})
_NATIVE_ADOPTION_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")


class ManagedStateError(RuntimeError):
    """Stable, operator-visible refusal from the managed state boundary."""

    def __init__(self, code: str, message: str, returncode: Optional[int] = None):
        self.code = str(code)
        self.returncode = returncode
        # A few callers use the subprocess spelling when relaying helper
        # failures.  Keep it as a harmless alias while ``returncode`` remains
        # the public name used by the state tests.
        self.rc = returncode
        self.message = str(message)
        super().__init__(self.message)


def native_record_marker(record_kind: Optional[str] = None) -> Dict[str, Any]:
    """Return a fresh canonical marker for one native durable record.

    Returning a fresh mapping is intentional: callers may add their own
    fields without mutating the process-wide constant or another record.
    ``record_kind`` is a discriminator, not a compatibility/version alias.
    """

    marker = dict(NATIVE_RECORD_MARKER)
    if record_kind is not None:
        if (not isinstance(record_kind, str) or not record_kind or
                "\x00" in record_kind or len(record_kind) > MAX_COMPONENT_LENGTH or
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", record_kind)):
            raise _error("invalid", "native record kind is invalid")
        marker["record_kind"] = record_kind
    return marker


def validate_native_lineage_record(
        record: Any, *, record_kind: Optional[str] = None,
        required: Optional[Sequence[str]] = None,
        label: str = "native managed record") -> Dict[str, Any]:
    """Validate the one schema-v2 native-lineage envelope without writing.

    The returned mapping is a shallow copy and the input is never normalized,
    repaired, or deleted.  In particular, a schema-1 record and a record that
    uses the old ``schema``/alias fields are a migration refusal, not an empty
    record and not native evidence.
    """

    if not isinstance(record, Mapping):
        raise _error("schema-mismatch", "%s is not a native-lineage object" % label)
    value = dict(record)
    version = value.get("schema_version")
    architecture = value.get("architecture")
    if "schema" in value or version != NATIVE_SCHEMA_VERSION:
        if value.get("schema") == LEGACY_SCHEMA_VERSION or version == LEGACY_SCHEMA_VERSION:
            raise _error(
                "schema-mismatch",
                "%s uses superseded schema 1; migration-required" % label,
            )
        raise _error("schema-mismatch", "%s has an unsupported schema" % label)
    if architecture != NATIVE_ARCHITECTURE:
        raise _error(
            "schema-mismatch",
            "%s is not marked %s" % (label, NATIVE_ARCHITECTURE),
        )
    if isinstance(version, bool) or not isinstance(version, int):
        raise _error("schema-mismatch", "%s has an invalid schema version" % label)
    if record_kind is not None and value.get("record_kind") != record_kind:
        raise _error(
            "schema-mismatch",
            "%s has an unsupported record kind" % label,
        )
    if required is not None:
        missing = [name for name in required if name not in value]
        if missing:
            raise _error(
                "invalid",
                "%s is missing required fields: %s" % (label, ", ".join(missing)),
            )
    return value


# Short explicit spelling used by callers that validate arbitrary managed
# records.  It is a function alias, not a wire-field alias: the durable wire
# still has exactly ``schema_version`` and ``architecture``.
validate_native_record = validate_native_lineage_record


def _native_record_with_marker(record: Mapping[str, Any], record_kind: str,
                               label: str) -> Dict[str, Any]:
    """Attach the canonical marker without repairing a caller's record.

    Lifecycle writers construct records in memory and then pass them through
    this helper.  A conflicting marker or a prototype ``schema``/``version``
    field is a refusal; it is never silently replaced or removed.
    """

    if not isinstance(record, Mapping):
        raise _error("invalid", "%s is not an object" % label)
    value = dict(record)
    if "schema" in value or "version" in value:
        raise _error("schema-mismatch", "%s uses a superseded schema field" % label)
    marker = native_record_marker(record_kind)
    for key, expected in marker.items():
        if key in value and value[key] != expected:
            raise _error("schema-mismatch", "%s has an incompatible native marker" % label)
    value.update(marker)
    return validate_native_lineage_record(
        value, record_kind=record_kind, label=label,
    )


def _native_json_value(value: Any) -> Any:
    """Convert bounded native claim evidence into deterministic JSON data."""

    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _native_json_value(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_native_json_value(item) for item in value]
    return value


def _native_digest(value: Any) -> str:
    try:
        encoded = json.dumps(
            _native_json_value(value), ensure_ascii=True, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise _error("unsupported", "native capability evidence is not JSON-shaped: %s" % exc)
    return hashlib.sha256(encoded).hexdigest()


def canonical_lane(lane: str) -> str:
    """Validate and return a lane's display spelling.

    Lane names are one path component.  The display spelling is preserved so
    a caller can report the register's canonical form, while state paths use
    ``casefold`` (``WorkspaceIdentity.lane_key``) so case variants cannot
    create two ownership authorities.
    """

    if not isinstance(lane, str):
        raise ManagedStateError("invalid", "lane name must be a string")
    if not lane or len(lane) > MAX_COMPONENT_LENGTH or not _LANE_RE.fullmatch(lane):
        raise ManagedStateError(
            "invalid",
            "lane name must be one path-safe component beginning with a letter "
            "or digit",
        )
    return lane


def _canonical_component(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_COMPONENT_LENGTH:
        raise ManagedStateError("invalid", "%s must be one path-safe component" % label)
    if not _COMPONENT_RE.fullmatch(value):
        raise ManagedStateError("invalid", "%s must be one path-safe component" % label)
    return value


def _opaque_token(value: Any, label: str, *, maximum: int = 256) -> str:
    """Validate an opaque caller/token identifier without changing it."""

    if (not isinstance(value, str) or not value or len(value) > maximum or
            "\x00" in value):
        raise _error("invalid", "%s is invalid" % label)
    return value


def _local_process_domain() -> Optional[str]:
    """Return the native Linux PID domain when it can be observed exactly."""

    if not sys.platform.startswith("linux"):
        return None
    try:
        machine_id = Path("/etc/machine-id").read_text(encoding="ascii").strip()
        namespace = os.readlink("/proc/self/ns/pid").strip()
    except (OSError, UnicodeError, ValueError):
        return None
    if (not machine_id or
            any(character not in "0123456789abcdefABCDEF" for character in machine_id) or
            not _PROCESS_DOMAIN_RE.fullmatch(
                "linux:%s:%s" % (machine_id, namespace))):
        return None
    return "linux:%s:%s" % (machine_id, namespace)


def _canonical_process_domain(value: Any, label: str = "process domain") -> str:
    """Validate a local/native or exactly observed supported domain token."""

    token = _opaque_token(value, label, maximum=512)
    if token in {"local", "native"}:
        return token
    if not _PROCESS_DOMAIN_RE.fullmatch(token):
        raise _error("live-unverified", "%s is unknown" % label)
    local = _local_process_domain()
    if local is None or token != local:
        raise _error("live-unverified", "%s is foreign or unobservable" % label)
    return token


def _current_uid() -> Optional[int]:
    getuid = getattr(os, "getuid", None)
    if getuid is None:
        return None
    return int(getuid())


def _mode_is_private(mode: int) -> bool:
    # Owner-only is the security property.  The implementation creates 0700
    # directories and 0600 files, but accepting owner read-only files lets a
    # caller make a durable record immutable without making the whole layout
    # unusable.
    return (mode & 0o077) == 0


def _error(code: str, message: str, returncode: Optional[int] = None) -> ManagedStateError:
    return ManagedStateError(code, message, returncode)


def _assert_private(path: Path, *, directory: Optional[bool] = None) -> None:
    """Check one existing state component without following symlinks."""

    try:
        info = path.lstat()
    except FileNotFoundError:
        raise _error("unsafe-state", "managed state component is missing: %s" % path)
    except OSError as exc:
        raise _error("unsafe-state", "cannot inspect managed state component %s: %s" %
                     (path, exc))
    if stat.S_ISLNK(info.st_mode):
        raise _error("unsafe-state", "managed state component is a symlink: %s" % path)
    is_dir = stat.S_ISDIR(info.st_mode)
    if directory is not None and is_dir != directory:
        expected = "directory" if directory else "file"
        raise _error("unsafe-state", "%s is not a %s" % (path, expected))
    if directory is False and not stat.S_ISREG(info.st_mode):
        raise _error("unsafe-state", "managed state record is not a regular file: %s" % path)
    uid = _current_uid()
    if uid is not None and info.st_uid != uid:
        raise _error("unsafe-state", "managed state component is not owned by the current user: %s" % path)
    if not _mode_is_private(stat.S_IMODE(info.st_mode)):
        raise _error("unsafe-state", "managed state component is not private: %s" % path)


def _assert_private_socket(path: Path) -> None:
    """Check an existing discovery socket without following symlinks."""

    try:
        info = path.lstat()
    except FileNotFoundError:
        raise _error("unsafe-state", "managed runtime socket is missing: %s" % path)
    except OSError as exc:
        raise _error("unsafe-state", "cannot inspect managed runtime socket %s: %s" %
                     (path, exc))
    if stat.S_ISLNK(info.st_mode):
        raise _error("unsafe-state", "managed runtime socket is a symlink: %s" % path)
    if not stat.S_ISSOCK(info.st_mode):
        raise _error("unsafe-state", "managed runtime socket is not a Unix socket: %s" % path)
    uid = _current_uid()
    if uid is not None and info.st_uid != uid:
        raise _error("unsafe-state", "managed runtime socket is not owned by the current user: %s" % path)
    if not _mode_is_private(stat.S_IMODE(info.st_mode)):
        raise _error("unsafe-state", "managed runtime socket is not private: %s" % path)


def _canonical_private_socket(value: Any) -> Path:
    """Validate an absolute canonical socket path and its private parent."""

    if isinstance(value, Path):
        path = value
    elif isinstance(value, str):
        path = Path(value)
    else:
        raise _error("invalid", "socket path is invalid")
    raw = str(path)
    if (not path.is_absolute() or "\x00" in raw or
            len(os.fsencode(raw)) >= 104):
        raise _error("invalid", "socket path must be an absolute bounded path")
    try:
        canonical = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise _error("invalid", "socket path cannot be resolved: %s" % exc)
    if str(canonical) != raw:
        raise _error("invalid", "socket path is not canonical")
    anchor = Path(canonical.anchor)
    _check_existing_chain(anchor, canonical.parent,
                          final_directory=True, check_private=False)
    _assert_private(canonical.parent, directory=True)
    if canonical.exists() or canonical.is_symlink():
        _assert_private_socket(canonical)
    return canonical


def _path_parts_from(base: Path, target: Path) -> Iterator[Path]:
    """Yield ``target``'s components below ``base`` in parent-first order."""

    base = Path(base)
    target = Path(target)
    try:
        relative = target.relative_to(base)
    except ValueError:
        raise _error("invalid", "managed state path escapes its Git common directory")
    current = base
    for component in relative.parts:
        current = current / component
        yield current


def _check_existing_chain(base: Path, target: Path, *, final_directory: Optional[bool] = None,
                          check_private: bool = True) -> None:
    """Reject symlinks and unsafe existing components below ``base``.

    Missing final components are fine during identity resolution and layout
    creation.  Any non-directory component before a missing component is a
    refusal rather than a path fallback.
    """

    base = Path(base)
    try:
        base_info = base.lstat()
    except OSError as exc:
        raise _error("unsafe-state", "cannot inspect Git common directory %s: %s" %
                     (base, exc))
    if stat.S_ISLNK(base_info.st_mode):
        raise _error("unsafe-state", "Git common directory is a symlink: %s" % base)
    if not stat.S_ISDIR(base_info.st_mode):
        raise _error("unsafe-state", "Git common directory is not a directory: %s" % base)

    for component in _path_parts_from(base, target):
        try:
            info = component.lstat()
        except FileNotFoundError:
            break
        except OSError as exc:
            raise _error("unsafe-state", "cannot inspect managed state path %s: %s" %
                         (component, exc))
        if stat.S_ISLNK(info.st_mode):
            raise _error("unsafe-state", "managed state path contains a symlink: %s" % component)
        is_final = component == target
        if not is_final and not stat.S_ISDIR(info.st_mode):
            raise _error("unsafe-state", "managed state path component is not a directory: %s" % component)
        if check_private and component != base:
            _assert_private(component, directory=(True if not is_final else final_directory))


def _safe_resolve(path: Path, *, label: str) -> Path:
    try:
        return path.resolve(strict=True)
    except OSError as exc:
        raise _error("unknown", "cannot resolve %s %s: %s" % (label, path, exc), 1)


def _coerce_runner_result(result: Any) -> Tuple[str, int, str]:
    """Normalize subprocess and deliberately tiny test-runner seams."""

    if hasattr(result, "returncode"):
        rc = int(getattr(result, "returncode"))
        stdout = getattr(result, "stdout", "")
        stderr = getattr(result, "stderr", "")
        return ("" if stdout is None else str(stdout), rc,
                "" if stderr is None else str(stderr))
    if isinstance(result, (tuple, list)):
        if len(result) == 0:
            return "", 0, ""
        if len(result) == 1:
            return str(result[0]), 0, ""
        first, second = result[0], result[1]
        # The state test seam returns (stdout, returncode, stderr), while a
        # number of subprocess-like helpers return (returncode, stdout, stderr).
        if isinstance(first, int):
            rc = int(first)
            stdout = "" if second is None else str(second)
            stderr = "" if len(result) < 3 or result[2] is None else str(result[2])
            return stdout, rc, stderr
        stdout = "" if first is None else str(first)
        rc = int(second)
        stderr = "" if len(result) < 3 or result[2] is None else str(result[2])
        return stdout, rc, stderr
    if isinstance(result, int):
        return "", int(result), ""
    if result is None:
        return "", 0, ""
    return str(result), 0, ""


def _invoke_runner(runner: Callable[..., Any], command: Sequence[str],
                   env: Mapping[str, str]) -> Tuple[str, int, str]:
    """Call a subprocess-compatible runner, including small test seams."""

    try:
        result = runner(command, env=dict(env), capture_output=True,
                        text=True, check=False, timeout=HELPER_TIMEOUT_SECONDS)
    except TypeError:
        try:
            result = runner(command, env=dict(env))
        except TypeError:
            result = runner(command)
    return _coerce_runner_result(result)


def _helper_command(helper: Any, env: Mapping[str, str]) -> Sequence[str]:
    if helper is None:
        selected = env.get("LANES_EDIT") or shutil.which("lanes-edit.sh")
        if not selected:
            adjacent = Path(__file__).with_name("lanes-edit.sh")
            selected = str(adjacent) if adjacent.exists() else "lanes-edit.sh"
        return (str(selected), "workspace-root")
    if callable(helper):
        # A callable helper is handled by resolve_workspace as a runner seam;
        # this return is never executed, but keeps the command shape available
        # to the seam for assertions.
        return ("lanes-edit.sh", "workspace-root")
    if isinstance(helper, (list, tuple)):
        command = [str(part) for part in helper]
        return tuple(command + ["workspace-root"])
    return (str(helper), "workspace-root")


def _git_common_dir(workspace: Path) -> Path:
    command = ["git", "-C", str(workspace), "rev-parse",
               "--path-format=absolute", "--git-common-dir"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False,
                                timeout=HELPER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise _error("unknown", "workspace Git common-directory read timed out", 1)
    except OSError as exc:
        raise _error("unknown", "cannot inspect workspace Git common directory: %s" % exc, 1)
    if result.returncode != 0:
        # Older Git versions do not know --path-format.  The fallback is still
        # read-only and is resolved against the verified workspace root.
        fallback = ["git", "-C", str(workspace), "rev-parse", "--git-common-dir"]
        try:
            result = subprocess.run(fallback, capture_output=True, text=True, check=False,
                                    timeout=HELPER_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            raise _error("unknown", "workspace Git common-directory read timed out", 1)
        except OSError as exc:
            raise _error("unknown", "cannot inspect workspace Git common directory: %s" % exc, 1)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Git common directory read failed").strip()
        raise _error("unknown", detail, int(result.returncode))
    raw = (result.stdout or "").strip()
    if not raw or "\n" in raw or "\x00" in raw:
        raise _error("unknown", "Git common directory read was malformed", 1)
    common = Path(raw)
    if not common.is_absolute():
        common = workspace / common
    return _safe_resolve(common, label="Git common directory")


def _host_name(env: Mapping[str, str]) -> str:
    supplied = env.get("LANES_WORKSTATION") or env.get("HOSTNAME")
    if not supplied:
        try:
            supplied = socket.gethostname().split(".", 1)[0]
        except OSError:
            supplied = "unknown"
    # Host identity is a path key as well; case-fold it just as lane keys are
    # folded so a workstation cannot accidentally create two global indexes.
    return _canonical_component(str(supplied).strip().casefold(), "host")


def _identity_paths_are_safe(identity: "WorkspaceIdentity") -> None:
    _check_existing_chain(identity.common_dir, identity.global_root,
                          final_directory=True)
    _check_existing_chain(identity.common_dir, identity.state_root,
                          final_directory=True)


@dataclass(frozen=True)
class WorkspaceIdentity:
    """Resolved workspace and the private state roots derived from it."""

    workspace_root: Path
    common_dir: Path
    lane: str
    host: str
    state_root: Optional[Path] = None
    global_root: Optional[Path] = None
    lane_key: Optional[str] = None

    def __post_init__(self) -> None:
        lane = canonical_lane(self.lane)
        lane_key = lane.casefold()
        if self.lane_key is not None and self.lane_key != lane_key:
            raise _error("invalid", "lane_key does not match the canonical lane")
        host = _canonical_component(str(self.host).casefold(), "host")
        workspace = Path(self.workspace_root)
        common = Path(self.common_dir)
        if not workspace.is_absolute():
            workspace = workspace.absolute()
        if not common.is_absolute():
            common = common.absolute()
        expected_global = common / _STATE_DIR_NAME / host
        expected_state = expected_global / lane_key
        supplied_global = expected_global if self.global_root is None else Path(self.global_root)
        supplied_state = expected_state if self.state_root is None else Path(self.state_root)
        if not supplied_global.is_absolute():
            supplied_global = supplied_global.absolute()
        if not supplied_state.is_absolute():
            supplied_state = supplied_state.absolute()
        if supplied_global != expected_global or supplied_state != expected_state:
            raise _error("invalid", "managed state roots do not match workspace identity")
        object.__setattr__(self, "workspace_root", workspace)
        object.__setattr__(self, "common_dir", common)
        object.__setattr__(self, "lane", lane)
        object.__setattr__(self, "host", host)
        object.__setattr__(self, "lane_key", lane_key)
        object.__setattr__(self, "global_root", supplied_global)
        object.__setattr__(self, "state_root", supplied_state)

    @property
    def workspace(self) -> Path:
        """Compatibility alias for callers that call the root ``workspace``."""

        return self.workspace_root

    @property
    def git_common_dir(self) -> Path:
        return self.common_dir


def resolve_workspace(lane: str, *, env: Optional[Mapping[str, str]] = None,
                      helper: Any = None, runner: Optional[Callable[..., Any]] = None
                      ) -> WorkspaceIdentity:
    """Resolve a lane through the supported helper and derive secure roots.

    Exit status ``8`` is the helper's confirmed-absent answer and is preserved
    as ``ManagedStateError.returncode == 8``.  Exit 1, unknown statuses, and a
    malformed successful response are read failures; none is treated as an
    absent workspace or guessed from this module's own location.
    """

    display_lane = canonical_lane(lane)
    merged_env: Dict[str, str] = dict(os.environ)
    if env is not None:
        merged_env.update({str(key): str(value) for key, value in env.items()})
    host = _host_name(merged_env)

    command = _helper_command(helper, merged_env)
    try:
        if callable(helper) and runner is None:
            stdout, returncode, stderr = _invoke_runner(helper, command, merged_env)
        elif runner is not None:
            stdout, returncode, stderr = _invoke_runner(runner, command, merged_env)
        else:
            try:
                result = subprocess.run(command, env=merged_env,
                                        capture_output=True, text=True, check=False,
                                        timeout=HELPER_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                raise _error("unknown", "workspace helper timed out", 1)
            except OSError as exc:
                raise _error("unknown", "workspace helper could not be run: %s" % exc, 1)
            stdout, returncode, stderr = _coerce_runner_result(result)
    except ManagedStateError:
        raise
    except Exception as exc:
        raise _error("unknown", "workspace helper failed: %s" % exc, 1)

    if returncode != 0:
        code = "absent" if returncode == 8 else "unknown"
        detail = (stderr or stdout or "workspace helper failed").strip()
        raise _error(code, detail, int(returncode))
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise _error("unknown", "workspace helper returned no unique workspace root", 0)
    raw_workspace = lines[0]
    if "\x00" in raw_workspace:
        raise _error("unknown", "workspace helper returned a malformed path", 0)
    workspace = Path(raw_workspace).expanduser()
    if not workspace.is_absolute():
        raise _error("unknown", "workspace helper returned a relative path", 0)
    # The helper is the authority for the root, but a symlinked root would make
    # subsequent path identity ambiguous.  Reject it before resolving.
    try:
        _check_existing_chain(workspace.anchor and Path(workspace.anchor) or Path("/"),
                              workspace, final_directory=True, check_private=False)
    except ManagedStateError:
        raise
    if not workspace.exists() or not workspace.is_dir():
        raise _error("unknown", "workspace root does not exist or is not a directory", 1)
    workspace = _safe_resolve(workspace, label="workspace root")
    common = _git_common_dir(workspace)
    identity = WorkspaceIdentity(workspace_root=workspace, common_dir=common,
                                 lane=display_lane, host=host)
    _identity_paths_are_safe(identity)
    return identity


# ``flock`` supplies cross-process exclusion.  The in-process table is also
# needed: nested calls in one thread (for example an owner method calling
# ``append_journal``) must not deadlock, while a *different* thread must not be
# mistaken for that owner.  A per-path gate serializes such threads before
# they enter the kernel lock.  The PID is retained so a child created by fork
# cannot inherit the parent's Python ownership table and bypass exclusion.
_LOCK_GUARD = threading.RLock()
_LOCK_HELD: Dict[str, Tuple[int, int, int, bool, int]] = {}
_LOCK_GATES: Dict[str, threading.Lock] = {}
_LOCK_PID = os.getpid()


def _reset_forked_locks() -> None:
    """Drop duplicated lock descriptors after ``fork`` in a child process."""

    global _LOCK_PID
    # Do not acquire ``_LOCK_GUARD`` here.  At-fork callbacks run with only the
    # forking thread alive, so that mutex may itself have been held by a thread
    # that vanished in the child; taking it would wedge every future state
    # operation.  Closing the duplicated descriptors is safe: the parent's
    # descriptors (and therefore its lock ownership) remain open.
    for fd, _pid, _thread, _exclusive, _depth in list(_LOCK_HELD.values()):
        try:
            os.close(fd)
        except OSError:
            pass
    _LOCK_HELD.clear()
    _LOCK_GATES.clear()
    _LOCK_PID = os.getpid()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_forked_locks)


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= int(getattr(os, "O_DIRECTORY"))
    try:
        fd = os.open(str(directory), flags)
    except OSError as exc:
        raise _error("unsafe-state", "cannot open state directory for fsync: %s" % exc)
    try:
        os.fsync(fd)
    except OSError as exc:
        raise _error("unsafe-state", "cannot fsync state directory: %s" % exc)
    finally:
        os.close(fd)


class ManagedStateStore:
    """Secure state files, ownership interlock, and global writer claims."""

    def __init__(self, identity: WorkspaceIdentity):
        if not isinstance(identity, WorkspaceIdentity):
            raise _error("invalid", "state store requires a WorkspaceIdentity")
        self.identity = identity

    def _known_state_files(self) -> Iterator[Path]:
        if not self.identity.state_root.exists():
            return
        try:
            entries = list(self.identity.state_root.iterdir())
        except OSError as exc:
            raise _error("unsafe-state", "cannot inspect state root: %s" % exc)
        for entry in entries:
            yield entry

    def validate_layout(self) -> "ManagedStateStore":
        """Validate existing state components and known files, without writes."""

        _identity_paths_are_safe(self.identity)
        global_root = self.identity.global_root
        state_root = self.identity.state_root
        if global_root.exists():
            _assert_private(global_root, directory=True)
            try:
                global_entries = list(global_root.iterdir())
            except OSError as exc:
                raise _error("unsafe-state", "cannot inspect global state root: %s" % exc)
            for entry in global_entries:
                if entry.is_symlink():
                    raise _error("unsafe-state", "managed state component is a symlink: %s" % entry)
                if entry.is_dir():
                    _assert_private(entry, directory=True)
                else:
                    _assert_private(entry, directory=False)
        if state_root.exists():
            _assert_private(state_root, directory=True)
            for entry in self._known_state_files():
                if entry.is_symlink():
                    raise _error("unsafe-state", "managed state component is a symlink: %s" % entry)
                _assert_private(entry, directory=entry.is_dir())
        return self

    def _mkdir_private(self, path: Path) -> None:
        try:
            info = path.lstat()
        except FileNotFoundError:
            try:
                path.mkdir(mode=0o700)
            except FileExistsError:
                # A concurrent creator is fine; it is checked immediately
                # below and a symlink can never be accepted.
                pass
            except OSError as exc:
                raise _error("unsafe-state", "cannot create managed state directory %s: %s" %
                             (path, exc))
        except OSError as exc:
            raise _error("unsafe-state", "cannot inspect managed state directory %s: %s" %
                         (path, exc))
        _assert_private(path, directory=True)

    def ensure_layout(self) -> "ManagedStateStore":
        """Create the private state roots and an empty owner record."""

        common = self.identity.common_dir
        if not common.exists() or not common.is_dir():
            raise _error("unsafe-state", "Git common directory is unavailable: %s" % common)
        _check_existing_chain(common, self.identity.global_root,
                              final_directory=True)
        managed_root = common / _STATE_DIR_NAME
        self._mkdir_private(managed_root)
        self._mkdir_private(self.identity.global_root)
        self._mkdir_private(self.identity.state_root)
        owner = self.identity.state_root / _OWNER_NAME
        if not owner.exists():
            self._atomic_write(owner, b"{}\n", create_only=True)
        self.validate_layout()
        return self

    def _normalise_name(self, name: str, suffix: str) -> str:
        if not isinstance(name, str) or not name or "\x00" in name:
            raise _error("invalid", "state record name must be one file name")
        if name in (".", "..") or Path(name).name != name or "/" in name or "\\" in name:
            raise _error("invalid", "state record name must not contain path separators")
        if not name.endswith(suffix):
            name += suffix
        if len(name) > MAX_COMPONENT_LENGTH or not _COMPONENT_RE.fullmatch(name.rsplit(".", 1)[0]):
            raise _error("invalid", "state record name is not path-safe")
        return name

    def _json_path(self, name: str, *, global_file: bool = False) -> Path:
        filename = self._normalise_name(name, ".json")
        root = self.identity.global_root if global_file else self.identity.state_root
        path = root / filename
        _check_existing_chain(self.identity.common_dir, root, final_directory=True)
        if path.exists() or path.is_symlink():
            _assert_private(path, directory=False)
        return path

    def _journal_path(self, name: str) -> Path:
        filename = self._normalise_name(name, ".jsonl")
        path = self.identity.state_root / filename
        _check_existing_chain(self.identity.common_dir, self.identity.state_root,
                              final_directory=True)
        if path.exists() or path.is_symlink():
            _assert_private(path, directory=False)
        return path

    def _atomic_write(self, path: Path, payload: bytes, *, create_only: bool = False) -> None:
        if len(payload) > MAX_JSON_BYTES:
            raise _error("invalid", "managed state record exceeds one MiB")
        parent = path.parent
        if not parent.exists() or not parent.is_dir():
            raise _error("unsafe-state", "managed state parent is unavailable: %s" % parent)
        _assert_private(parent, directory=True)
        if path.exists() or path.is_symlink():
            _assert_private(path, directory=False)
        fd = -1
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix=".managed-", dir=str(parent))
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as stream:
                fd = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            temp_path = Path(temporary)
            _assert_private(temp_path, directory=False)
            if create_only:
                # A check followed by replace is not a create-only operation:
                # another process can enroll a lane between those calls and a
                # delayed initializer would overwrite its durable owner.  A
                # hard link publishes the already-fsynced temporary inode with
                # true no-replace semantics; the existing destination wins a
                # race and is never touched.
                try:
                    os.link(str(temp_path), str(path))
                except FileExistsError:
                    if path.exists() or path.is_symlink():
                        _assert_private(path, directory=False)
                    else:
                        raise _error("unsafe-state", "managed state record creation raced and disappeared")
                else:
                    temporary = None
                    os.unlink(str(temp_path))
            else:
                os.replace(str(temp_path), str(path))
                temporary = None
            _fsync_directory(parent)
        except OSError as exc:
            raise _error("unsafe-state", "atomic managed state write failed: %s" % exc)
        finally:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if temporary:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    @contextlib.contextmanager
    def _lock_context(self, shared: bool = False, timeout: Optional[float] = None,
                      deadline: Optional[float] = None, *,
                      provision: bool) -> Iterator["ManagedStateStore"]:
        """Acquire the host/workspace-global advisory lock.

        Nested calls in one process are treated as already holding the lock;
        this avoids deadlock when a higher-level owner operation calls one of
        the JSON helpers.  A shared nested read under an exclusive outer lock
        is safe.  Callers should not attempt an exclusive upgrade from a
        shared outer context.
        """

        if timeout is not None:
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
                raise _error("invalid", "lock timeout must be positive")
            if deadline is not None:
                raise _error("invalid", "specify lock timeout or deadline, not both")
            deadline = time.monotonic() + float(timeout)
        elif deadline is not None:
            if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
                raise _error("invalid", "lock deadline must be a monotonic timestamp")
            if deadline <= time.monotonic():
                raise _error("busy", "managed state lock acquisition timed out")

        if provision:
            self.ensure_layout()
        lock_path = self.identity.global_root / _LOCK_NAME
        key = str(lock_path)
        pid = os.getpid()
        thread_id = threading.get_ident()

        # ``register_at_fork`` handles normal POSIX forks.  This check also
        # covers runtimes that expose a fork-like process transition without
        # the hook (and makes the invariant explicit at the call site).
        global _LOCK_PID
        if _LOCK_PID != pid:
            _reset_forked_locks()

        nested = False
        gate: Optional[threading.Lock] = None
        with _LOCK_GUARD:
            existing = _LOCK_HELD.get(key)
            if existing is not None:
                fd_existing, pid_existing, thread_existing, exclusive_existing, depth = existing
                if pid_existing == pid and thread_existing == thread_id:
                    # A shared lock cannot be upgraded safely while an outer
                    # context is active.  Refuse instead of silently writing
                    # through a reader's lock.
                    if not shared and not exclusive_existing:
                        raise _error("busy", "cannot upgrade a shared managed-state lock")
                    _LOCK_HELD[key] = (fd_existing, pid_existing, thread_existing,
                                       exclusive_existing, depth + 1)
                    nested = True
            if not nested:
                gate = _LOCK_GATES.setdefault(key, threading.Lock())

        if nested:
            try:
                yield self
            finally:
                with _LOCK_GUARD:
                    current = _LOCK_HELD.get(key)
                    if current is None:
                        # This can only happen if a caller forked while inside
                        # a context and then reused the inherited object.
                        pass
                    else:
                        fd_existing, pid_existing, thread_existing, exclusive_existing, depth = current
                        if depth > 1:
                            _LOCK_HELD[key] = (fd_existing, pid_existing, thread_existing,
                                               exclusive_existing, depth - 1)
                        else:
                            # The outer context owns the descriptor and unlocks it.
                            _LOCK_HELD[key] = current
            return

        # Only one thread at a time attempts a given path.  The gate is not
        # held while this thread yields, so the owner can always exit and wake
        # a waiter; unlike the old process-wide guard, a blocked waiter cannot
        # deadlock the releasing thread.
        assert gate is not None
        if deadline is None:
            gate.acquire()
        else:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not gate.acquire(timeout=remaining):
                raise _error("busy", "managed state lock acquisition timed out")
        fd = -1
        try:
            flags = os.O_RDWR
            if provision:
                flags |= os.O_CREAT
            if hasattr(os, "O_NOFOLLOW"):
                flags |= int(getattr(os, "O_NOFOLLOW"))
            try:
                if provision:
                    fd = os.open(str(lock_path), flags, 0o600)
                    os.fchmod(fd, 0o600)
                else:
                    # An assessment may only use an already-existing lock
                    # inode.  Do not create or chmod it while racing a
                    # disappearing state store; validate the opened inode
                    # itself before taking the advisory lock.
                    fd = os.open(str(lock_path), flags)
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode):
                        raise _error(
                            "unsafe-state",
                            "managed state lock is not a regular file: %s" % lock_path,
                        )
                    uid = _current_uid()
                    if uid is not None and info.st_uid != uid:
                        raise _error(
                            "unsafe-state",
                            "managed state lock is not owned by the current user: %s" % lock_path,
                        )
                    if not _mode_is_private(stat.S_IMODE(info.st_mode)):
                        raise _error(
                            "unsafe-state",
                            "managed state lock is not private: %s" % lock_path,
                        )
                operation = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
                if deadline is None:
                    fcntl.flock(fd, operation)
                else:
                    while True:
                        try:
                            fcntl.flock(fd, operation | fcntl.LOCK_NB)
                            break
                        except OSError as lock_error:
                            if lock_error.errno not in (errno.EACCES, errno.EAGAIN):
                                raise
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                raise _error("busy", "managed state lock acquisition timed out")
                            time.sleep(min(0.01, remaining))
            except OSError as exc:
                raise _error("unsafe-state", "cannot lock managed state: %s" % exc)
            with _LOCK_GUARD:
                _LOCK_HELD[key] = (fd, pid, thread_id, not shared, 1)
            yield self
        finally:
            with _LOCK_GUARD:
                current = _LOCK_HELD.get(key)
                if current is not None and current[0] == fd and current[1] == pid and current[2] == thread_id:
                    del _LOCK_HELD[key]
            if fd >= 0:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)
            gate.release()

    @contextlib.contextmanager
    def locked(self, shared: bool = False, timeout: Optional[float] = None,
               deadline: Optional[float] = None) -> Iterator["ManagedStateStore"]:
        """Hold the advisory lock, provisioning the normal state layout first."""

        with self._lock_context(
                shared=shared, timeout=timeout, deadline=deadline,
                provision=True):
            yield self

    @contextlib.contextmanager
    def _locked_existing(self, shared: bool = False,
                         timeout: Optional[float] = None,
                         deadline: Optional[float] = None) -> Iterator["ManagedStateStore"]:
        """Hold the advisory lock without provisioning any state component."""

        with self._lock_context(
                shared=shared, timeout=timeout, deadline=deadline,
                provision=False):
            yield self

    def _read_path(self, path: Path) -> Any:
        if path.is_symlink():
            _assert_private(path, directory=False)
        if not path.exists():
            return None
        _assert_private(path, directory=False)
        try:
            size = path.stat().st_size
            if size > MAX_JSON_BYTES:
                raise _error("invalid", "managed state record exceeds one MiB")
            raw = path.read_bytes()
            if len(raw) > MAX_JSON_BYTES:
                raise _error("invalid", "managed state record exceeds one MiB")
            return json.loads(raw.decode("utf-8"))
        except ManagedStateError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise _error("invalid", "managed state JSON is unreadable: %s" % exc)

    def read_json(self, name: str) -> Any:
        self.ensure_layout()
        with self.locked(shared=True):
            filename = self._normalise_name(name, ".json")
            if filename == _OWNER_NAME:
                return self._load_owner()
            if filename == _RUNTIME_NAME:
                return self._load_runtime()
            if filename == _GENERATION_NAME:
                generation = self._load_generation()
                return (None if generation is None else
                        self._read_path(self._json_path(_GENERATION_NAME)))
            if filename == _RECOVERY_NAME:
                return self._load_recovery_intent()
            if filename == _CLAIMS_NAME:
                # Claims live below the workspace-global root rather than the
                # lane-local state root.  The loader validates the complete
                # index before the raw envelope is returned to a caller.
                self._load_claims()
                return self._read_path(
                    self._json_path(_CLAIMS_NAME, global_file=True)
                )
            if filename == _ADOPTIONS_NAME:
                # Adoption intents have their own strict record marker and
                # identity/digest validation.  Keep the generic read API
                # behind that same boundary so a malformed present ledger is
                # never exposed as arbitrary JSON.
                path = self._json_path(_ADOPTIONS_NAME)
                raw = self._read_path(path)
                if raw is not None:
                    self._validate_native_adoption_ledger_payload(raw)
                return raw
            path = self._json_path(name)
            raw = self._read_path(path)
            if filename == "controller.json" and raw is not None:
                validate_native_lineage_record(
                    raw, record_kind="controller",
                    label="managed controller record",
                )
            return raw

    def _validate_reserved_write(self, filename: str, data: Any) -> Any:
        """Validate a reserved record before an atomic replacement.

        Existing bytes are loaded first by :meth:`write_json`; therefore a
        superseded record fails before this method can publish anything.  New
        native records must carry the exact marker, while the two explicitly
        legacy owner leases remain legacy interlocks rather than native
        controller state.
        """

        if filename == _OWNER_NAME:
            if data == {}:
                return data
            if not isinstance(data, Mapping):
                raise _error("invalid", "managed owner record is not an object")
            if data.get("mode") in {"legacy-lease", "pending-launch"}:
                return data
            required = {
                "schema_version", "architecture", "record_kind", "mode",
                "daemon_id", "generation", "lane", "lane_key", "host",
                "process_domain", "created_at",
            }
            return validate_native_lineage_record(
                data, record_kind="managed-owner", required=required,
                label="managed owner record",
            )
        if filename == _CLAIMS_NAME:
            value = validate_native_lineage_record(
                data, record_kind="lineage-claims",
                required={"schema_version", "architecture", "record_kind",
                          "claims"},
                label="global lineage claim index",
            )
            if not isinstance(value["claims"], list):
                raise _error("invalid", "global lineage claim index is invalid")
            for claim in value["claims"]:
                if not isinstance(claim, Mapping):
                    raise _error("invalid", "global lineage claim is not an object")
                claim_kind = claim.get("record_kind")
                if claim_kind not in {"workspace-claim", "child-worktree-claim"}:
                    raise _error("unsupported", "global lineage claim kind is unknown")
                validate_native_lineage_record(
                    claim, record_kind=claim_kind,
                    label="global lineage claim",
                )
            return value
        if filename == "controller.json":
            return validate_native_lineage_record(
                data, record_kind="controller",
                label="managed controller record",
            )
        if filename == _ADOPTIONS_NAME:
            return self._validate_native_adoption_ledger_payload(data)
        return data

    def write_json(self, name: str, data: Any) -> Any:
        self.ensure_layout()
        filename = self._normalise_name(name, ".json")
        if filename in (_RUNTIME_NAME, _GENERATION_NAME, _RECOVERY_NAME):
            raise _error("ownership-conflict",
                         "%s is managed only by its lifecycle operation" % filename)
        try:
            encoded = json.dumps(data, ensure_ascii=True, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise _error("invalid", "managed state data is not JSON: %s" % exc)
        if len(encoded) > MAX_JSON_BYTES:
            raise _error("invalid", "managed state record exceeds one MiB")
        with self.locked():
            # Read the current reserved record under the same exclusive lock
            # before publishing.  This is the read-only migration boundary:
            # schema-1/unknown bytes remain untouched and are never adopted.
            if filename == _OWNER_NAME:
                self._load_owner()
            elif filename == _RUNTIME_NAME:
                self._load_runtime()
            elif filename == _GENERATION_NAME:
                self._load_generation()
            elif filename == _RECOVERY_NAME:
                self._load_recovery_intent()
            elif filename == _CLAIMS_NAME:
                self._load_claims()
            elif filename == _ADOPTIONS_NAME:
                # Preserve the old bytes on every failed replacement.  A
                # schema-v1 or malformed ledger is an explicit refusal, not
                # something a generic writer may overwrite.
                self._load_native_adoption_ledger()
            self._validate_reserved_write(filename, data)
            path = self._json_path(
                name, global_file=(filename == _CLAIMS_NAME)
            )
            self._atomic_write(path, encoded + b"\n")
        return data

    def append_journal(self, name: str, event: Any) -> Any:
        self.ensure_layout()
        try:
            encoded = json.dumps(event, ensure_ascii=True, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        except (TypeError, ValueError) as exc:
            raise _error("invalid", "journal event is not JSON: %s" % exc)
        if len(encoded) > MAX_JSON_BYTES:
            raise _error("invalid", "journal event exceeds one MiB")
        with self.locked():
            path = self._journal_path(name)
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            if hasattr(os, "O_NOFOLLOW"):
                flags |= int(getattr(os, "O_NOFOLLOW"))
            try:
                fd = os.open(str(path), flags, 0o600)
                os.fchmod(fd, 0o600)
                _assert_private(path, directory=False)
                offset = 0
                while offset < len(encoded):
                    offset += os.write(fd, encoded[offset:])
                os.fsync(fd)
            except OSError as exc:
                raise _error("unsafe-state", "journal append failed: %s" % exc)
            finally:
                try:
                    os.close(fd)
                except (OSError, UnboundLocalError):
                    pass
            _fsync_directory(path.parent)
        return event

    def _load_owner(self) -> Dict[str, Any]:
        owner = self._read_path(self.identity.state_root / _OWNER_NAME)
        if owner is None:
            return {}
        if not isinstance(owner, dict):
            raise _error("invalid", "managed owner record is not an object")
        # Only the exact empty object produced by ``ensure_layout`` denotes an
        # unowned lane.  Treating an arbitrary partial record as empty would
        # allow a crash/corruption to erase an owner during the next enroll.
        if not owner:
            return {}
        mode = owner.get("mode")
        if mode == "managed":
            # Managed ownership is native-lineage state.  A pre-marker
            # managed owner is the superseded prototype and is a read-only
            # migration refusal; never treat it as an unowned lane or rewrite
            # it in place.  Legacy ``legacy-lease`` records below remain an
            # exclusion boundary for the installed legacy front door.
            if "schema_version" not in owner or "architecture" not in owner:
                raise _error(
                    "schema-mismatch",
                    "managed owner uses superseded schema; migration-required",
                )
            validate_native_lineage_record(
                owner, record_kind="managed-owner",
                label="managed owner record",
            )
            required = {
                "schema_version", "architecture", "record_kind",
                "mode", "daemon_id", "generation", "lane", "lane_key",
                "host", "process_domain", "created_at",
            }
            optional = {
                "lineage_id", "coordinator_session_uuid",
                "coordinator_read_only",
            }
            if not required.issubset(owner) or set(owner) - required - optional:
                raise _error("invalid", "managed owner record is malformed")
            try:
                daemon_id = _canonical_component(owner["daemon_id"],
                                                 "owner daemon_id")
                lane = canonical_lane(owner["lane"])
                lane_key = owner["lane_key"]
                host = _canonical_component(owner["host"], "owner host")
                process_domain = _canonical_process_domain(
                    owner["process_domain"], "owner process domain")
            except (KeyError, TypeError):
                raise _error("invalid", "managed owner record is malformed")
            generation = owner["generation"]
            created_at = owner["created_at"]
            lineage_id = owner.get("lineage_id")
            coordinator_session_uuid = owner.get("coordinator_session_uuid")
            coordinator_read_only = owner.get("coordinator_read_only")
            if lineage_id is not None:
                lineage_id = _opaque_token(lineage_id, "owner lineage_id")
            if coordinator_session_uuid is not None:
                coordinator_session_uuid = _opaque_token(
                    coordinator_session_uuid, "owner coordinator_session_uuid",
                )
            if (daemon_id != owner["daemon_id"] or
                    isinstance(generation, bool) or
                    not isinstance(generation, int) or generation < 1 or
                    not isinstance(lane_key, str) or
                    lane_key != lane.casefold() or
                    lane_key != self.identity.lane_key or
                    host != self.identity.host or
                    process_domain != owner["process_domain"] or
                    (lineage_id is not None and
                     lineage_id != owner["lineage_id"]) or
                    (coordinator_session_uuid is not None and
                     coordinator_session_uuid != owner["coordinator_session_uuid"]) or
                    (coordinator_read_only is not None and
                     not isinstance(coordinator_read_only, bool)) or
                    isinstance(created_at, bool) or
                    not isinstance(created_at, (int, float))):
                raise _error("invalid", "managed owner record is malformed")
            try:
                created_at_finite = math.isfinite(float(created_at))
            except (OverflowError, TypeError, ValueError):
                created_at_finite = False
            if not created_at_finite:
                raise _error("invalid", "managed owner record is malformed")
            return dict(owner)
        if mode == "legacy-lease":
            required = {
                "mode", "pid", "start_token", "pgid", "lane", "lane_key",
                "host", "created_at",
            }
            if set(owner) != required:
                raise _error("invalid", "legacy owner record is malformed")
            try:
                lane = canonical_lane(owner["lane"])
                lane_key = owner["lane_key"]
                host = _canonical_component(owner["host"], "owner host")
                token = _opaque_token(owner["start_token"],
                                      "legacy start token")
            except (KeyError, TypeError):
                raise _error("invalid", "legacy owner record is malformed")
            pid = owner["pid"]
            pgid = owner["pgid"]
            created_at = owner["created_at"]
            if (isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0 or
                    isinstance(pgid, bool) or not isinstance(pgid, int) or pgid <= 0 or
                    not isinstance(lane_key, str) or lane_key != lane.casefold() or
                    lane_key != self.identity.lane_key or
                    host != self.identity.host or
                    isinstance(created_at, bool) or
                    not isinstance(created_at, (int, float))):
                raise _error("invalid", "legacy owner record is malformed")
            try:
                created_at_finite = math.isfinite(float(created_at))
            except (OverflowError, TypeError, ValueError):
                created_at_finite = False
            if not created_at_finite:
                raise _error("invalid", "legacy owner record is malformed")
            return dict(owner)
        if mode == "pending-launch":
            required = {
                "mode", "pid", "start_token", "request_id", "lease_id",
                "lane", "lane_key", "host", "created_at",
            }
            if set(owner) != required:
                raise _error("invalid", "pending-launch owner record is malformed")
            try:
                lane = canonical_lane(owner["lane"])
                lane_key = owner["lane_key"]
                host = _canonical_component(owner["host"], "owner host")
                request_id = _opaque_token(owner["request_id"], "request_id")
                lease_id = _opaque_token(owner["lease_id"], "lease_id")
            except (KeyError, TypeError):
                raise _error("invalid", "pending-launch owner record is malformed")
            pid = owner["pid"]
            start_token = owner["start_token"]
            created_at = owner["created_at"]
            if (isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0 or
                    not isinstance(start_token, str) or not start_token or
                    len(start_token) > 256 or "\x00" in start_token or
                    not isinstance(lane_key, str) or lane_key != lane.casefold() or
                    lane_key != self.identity.lane_key or
                    host != self.identity.host or
                    isinstance(created_at, bool) or
                    not isinstance(created_at, (int, float))):
                raise _error("invalid", "pending-launch owner record is malformed")
            try:
                created_at_finite = math.isfinite(float(created_at))
            except (OverflowError, TypeError, ValueError):
                created_at_finite = False
            if not created_at_finite:
                raise _error("invalid", "pending-launch owner record is malformed")
            # Keep the local variables above as explicit schema checks; the
            # record itself remains the durable wire representation.
            del request_id, lease_id
            return dict(owner)
        # Any non-legacy owner shape is an opaque record from another schema.
        # Validate its marker only to classify the refusal; this path never
        # repairs, adopts, or clears the bytes on disk.
        if any(key in owner for key in ("schema", "schema_version", "architecture",
                                        "record_kind", "version")):
            validate_native_lineage_record(
                owner, label="managed owner record",
            )
        raise _error(
            "invalid",
            "managed owner record has an unknown mode",
        )

    def _write_owner(self, record: Dict[str, Any]) -> None:
        if not isinstance(record, Mapping):
            raise _error("invalid", "managed owner record is not an object")
        if record and record.get("mode") == "managed":
            record = _native_record_with_marker(
                record, "managed-owner", "managed owner record",
            )
        self._atomic_write(self.identity.state_root / _OWNER_NAME,
                           json.dumps(record, ensure_ascii=True, sort_keys=True,
                                      separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n")

    def _load_generation(self) -> Optional[int]:
        """Load the strict monotonic lane-generation tombstone, if present."""

        raw = self._read_path(self._json_path(_GENERATION_NAME))
        if raw is None:
            return None
        validate_native_lineage_record(
            raw, record_kind="generation", label="managed generation ledger",
        )
        if set(raw) != {"schema_version", "architecture", "record_kind", "generation"}:
            raise _error("invalid", "managed generation ledger is malformed")
        generation = raw.get("generation")
        if (isinstance(generation, bool) or not isinstance(generation, int) or
                generation < 1):
            raise _error("invalid", "managed generation ledger is malformed")
        return generation

    def _write_generation(self, generation: int) -> None:
        if (isinstance(generation, bool) or not isinstance(generation, int) or
                generation < 1):
            raise _error("invalid", "managed generation must be a positive integer")
        self._atomic_write(
            self.identity.state_root / _GENERATION_NAME,
            json.dumps({**native_record_marker("generation"),
                        "generation": generation},
                       ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n",
        )

    def _write_runtime(self, record: Dict[str, Any]) -> None:
        record = _native_record_with_marker(
            record, "runtime", "managed runtime discovery record",
        )
        self._atomic_write(
            self.identity.state_root / _RUNTIME_NAME,
            json.dumps(record, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n",
        )

    def _write_recovery_intent(self, record: Dict[str, Any]) -> None:
        record = _native_record_with_marker(
            record, "recovery-intent", "managed recovery intent",
        )
        self._atomic_write(
            self.identity.state_root / _RECOVERY_NAME,
            json.dumps(record, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n",
        )

    def _remove_recovery_intent(self) -> None:
        path = self._json_path(_RECOVERY_NAME)
        if not path.exists() and not path.is_symlink():
            return
        _assert_private(path, directory=False)
        try:
            path.unlink()
        except OSError as exc:
            raise _error("unsafe-state", "managed recovery intent clear failed: %s" % exc)
        _fsync_directory(path.parent)

    def _load_recovery_intent(self) -> Optional[Dict[str, Any]]:
        """Load the strict two-file recovery transaction intent."""

        raw = self._read_path(self._json_path(_RECOVERY_NAME))
        if raw is None:
            return None
        validate_native_lineage_record(
            raw, record_kind="recovery-intent", label="managed recovery intent",
        )
        required = {
            "schema_version", "architecture", "record_kind", "state",
            "request_id", "lane", "lane_key", "host",
            "old_daemon_id", "old_generation", "old_pid", "old_start_token",
            "old_pgid", "old_process_domain", "old_socket_path",
            "new_daemon_id", "new_generation", "new_pid", "new_start_token",
            "new_pgid", "new_process_domain", "new_socket_path",
            "new_timestamp",
        }
        if not isinstance(raw, dict) or set(raw) != required:
            raise _error("invalid", "managed recovery intent is malformed")
        try:
            state = raw["state"]
            request_id = _opaque_token(raw["request_id"],
                                       "recovery request_id")
            lane = canonical_lane(raw["lane"])
            lane_key = raw["lane_key"]
            host = _canonical_component(raw["host"], "recovery host")
            old_daemon_id = _canonical_component(
                raw["old_daemon_id"], "old recovery daemon_id")
            new_daemon_id = _canonical_component(
                raw["new_daemon_id"], "new recovery daemon_id")
            old_start_token = _opaque_token(
                raw["old_start_token"], "old recovery start token")
            new_start_token = _opaque_token(
                raw["new_start_token"], "new recovery start token")
            old_process_domain = _canonical_process_domain(
                raw["old_process_domain"], "old recovery process domain")
            new_process_domain = _canonical_process_domain(
                raw["new_process_domain"], "new recovery process domain")
            old_socket_path = _canonical_private_socket(raw["old_socket_path"])
            new_socket_path = _canonical_private_socket(raw["new_socket_path"])
        except (KeyError, TypeError):
            raise _error("invalid", "managed recovery intent is malformed")
        old_generation = raw["old_generation"]
        new_generation = raw["new_generation"]
        old_pid = raw["old_pid"]
        new_pid = raw["new_pid"]
        old_pgid = raw["old_pgid"]
        new_pgid = raw["new_pgid"]
        new_timestamp = raw["new_timestamp"]
        if (state not in {"pending", "complete"} or
                lane_key != lane.casefold() or
                lane_key != self.identity.lane_key or
                host != self.identity.host or
                old_daemon_id == new_daemon_id or
                isinstance(old_generation, bool) or
                not isinstance(old_generation, int) or old_generation < 1 or
                isinstance(new_generation, bool) or
                not isinstance(new_generation, int) or
                new_generation != old_generation or
                isinstance(old_pid, bool) or not isinstance(old_pid, int) or
                old_pid <= 0 or isinstance(new_pid, bool) or
                not isinstance(new_pid, int) or new_pid <= 0 or
                isinstance(old_pgid, bool) or not isinstance(old_pgid, int) or
                old_pgid <= 0 or isinstance(new_pgid, bool) or
                not isinstance(new_pgid, int) or new_pgid <= 0 or
                old_process_domain != raw["old_process_domain"] or
                new_process_domain != raw["new_process_domain"] or
                str(old_socket_path) != raw["old_socket_path"] or
                str(new_socket_path) != raw["new_socket_path"] or
                isinstance(new_timestamp, bool) or
                not isinstance(new_timestamp, (int, float))):
            raise _error("invalid", "managed recovery intent is malformed")
        try:
            timestamp_finite = math.isfinite(float(new_timestamp))
        except (OverflowError, TypeError, ValueError):
            timestamp_finite = False
        if not timestamp_finite:
            raise _error("invalid", "managed recovery intent is malformed")
        if (old_daemon_id != raw["old_daemon_id"] or
                new_daemon_id != raw["new_daemon_id"] or
                old_start_token != raw["old_start_token"] or
                new_start_token != raw["new_start_token"] or
                lane != raw["lane"] or host != raw["host"]):
            raise _error("invalid", "managed recovery intent is malformed")
        return dict(raw)

    def _owner_matches_recovery_intent(self, owner: Dict[str, Any],
                                       intent: Dict[str, Any],
                                       prefix: str) -> bool:
        return (owner.get("mode") == "managed" and
                owner.get("daemon_id") == intent[prefix + "_daemon_id"] and
                owner.get("generation") == intent[prefix + "_generation"] and
                owner.get("process_domain") == intent[prefix + "_process_domain"] and
                owner.get("lane_key") == self.identity.lane_key and
                owner.get("host") == self.identity.host)

    def _runtime_matches_recovery_intent(
            self, runtime: Optional[Dict[str, Any]], intent: Dict[str, Any],
            prefix: str) -> bool:
        if runtime is None:
            return False
        return (runtime.get("daemon_id") == intent[prefix + "_daemon_id"] and
                runtime.get("generation") == intent[prefix + "_generation"] and
                runtime.get("pid") == intent[prefix + "_pid"] and
                runtime.get("start_token") == intent[prefix + "_start_token"] and
                runtime.get("pgid") == intent[prefix + "_pgid"] and
                runtime.get("process_domain") == intent[prefix + "_process_domain"] and
                runtime.get("socket_path") == intent[prefix + "_socket_path"] and
                runtime.get("lane_key") == self.identity.lane_key and
                runtime.get("host") == self.identity.host)

    @staticmethod
    def _recovery_identity_matches(
            intent: Dict[str, Any], prefix: str, daemon_id: str,
            generation: int, pid: int, start_token: str, pgid: int,
            process_domain: str) -> bool:
        """Compare one caller identity with one durable intent side."""

        return (
            daemon_id == intent[prefix + "_daemon_id"] and
            generation == intent[prefix + "_generation"] and
            pid == intent[prefix + "_pid"] and
            start_token == intent[prefix + "_start_token"] and
            pgid == intent[prefix + "_pgid"] and
            process_domain == intent[prefix + "_process_domain"]
        )

    def _validate_recovery_snapshot(
            self, owner: Dict[str, Any], runtime: Optional[Dict[str, Any]],
            intent: Dict[str, Any]) -> None:
        """Refuse reads that observe only one side of a recovery boundary."""

        owner_old = self._owner_matches_recovery_intent(owner, intent, "old")
        owner_new = self._owner_matches_recovery_intent(owner, intent, "new")
        runtime_old = self._runtime_matches_recovery_intent(runtime, intent, "old")
        runtime_new = self._runtime_matches_recovery_intent(runtime, intent, "new")
        if intent["state"] == "pending":
            # The intent may be durable before any replacement, or after both
            # replacement writes but before its completion marker.  Only those
            # two complete pairs are safe to expose to a reader.
            if (owner_old and runtime_old) or (owner_new and runtime_new):
                return
            raise _error("uncertain-effect",
                         "managed recovery is between owner/runtime writes")
        # A completed intent is allowed to outlive an explicitly cleared
        # endpoint, but ownership must remain the new incarnation.  A
        # different runtime is evidence of an unsafe replacement, never a
        # reason to treat the lane as unowned.
        if not owner_new:
            raise _error("uncertain-effect",
                         "completed recovery intent has no new managed owner")
        if runtime is not None and not runtime_new:
            raise _error("uncertain-effect",
                         "completed recovery intent has a mismatched runtime")

    def _load_runtime(self) -> Optional[Dict[str, Any]]:
        """Load and strictly validate the separate daemon discovery record."""

        path = self._json_path(_RUNTIME_NAME)
        raw = self._read_path(path)
        if raw is None:
            return None
        validate_native_lineage_record(
            raw, record_kind="runtime", label="managed runtime discovery record",
        )
        required = {
            "schema_version", "architecture", "record_kind", "daemon_id",
            "generation", "lane", "lane_key",
            "host", "pid", "start_token", "pgid", "process_domain",
            "socket_path", "timestamp",
        }
        if not isinstance(raw, dict) or set(raw) != required:
            raise _error("invalid", "managed runtime discovery record is malformed")
        try:
            daemon_id = _canonical_component(raw["daemon_id"], "runtime daemon_id")
            generation = raw["generation"]
            lane = canonical_lane(raw["lane"])
            lane_key = raw["lane_key"]
            host = _canonical_component(raw["host"], "runtime host")
            pid = raw["pid"]
            start_token = _opaque_token(raw["start_token"],
                                        "runtime start token")
            pgid = raw["pgid"]
            process_domain = _canonical_process_domain(
                raw["process_domain"], "runtime process domain")
            socket_path = _canonical_private_socket(raw["socket_path"])
            timestamp = raw["timestamp"]
        except (KeyError, TypeError):
            raise _error("invalid", "managed runtime discovery record is malformed")
        if (isinstance(generation, bool) or not isinstance(generation, int) or
                generation < 1 or
                not isinstance(lane_key, str) or lane_key != lane.casefold() or
                lane_key != self.identity.lane_key or host != self.identity.host or
                isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0 or
                isinstance(pgid, bool) or not isinstance(pgid, int) or pgid <= 0 or
                process_domain != raw["process_domain"] or
                str(socket_path) != raw["socket_path"] or
                isinstance(timestamp, bool) or
                not isinstance(timestamp, (int, float))):
            raise _error("invalid", "managed runtime discovery record is malformed")
        try:
            timestamp_finite = math.isfinite(float(timestamp))
        except (OverflowError, TypeError, ValueError):
            timestamp_finite = False
        if not timestamp_finite:
            raise _error("invalid", "managed runtime discovery record is malformed")
        if (daemon_id != raw["daemon_id"] or start_token != raw["start_token"] or
                lane != raw["lane"] or host != raw["host"]):
            raise _error("invalid", "managed runtime discovery record is malformed")
        return dict(raw)

    def register_runtime(self, daemon_id: str, generation: int, pid: int,
                         start_token: str, pgid: int,
                         process_domain: Optional[str] = None,
                         socket_path: Any = None) -> Dict[str, Any]:
        """Publish one daemon endpoint for the current managed owner."""

        daemon_id = _canonical_component(daemon_id, "daemon_id")
        if (isinstance(generation, bool) or not isinstance(generation, int) or
                generation < 1):
            raise _error("invalid", "runtime generation must be a positive integer")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise _error("invalid", "runtime PID must be a positive integer")
        start_token = _opaque_token(start_token, "runtime start token")
        if isinstance(pgid, bool) or not isinstance(pgid, int) or pgid <= 0:
            raise _error("invalid", "runtime process group ID must be a positive integer")
        # Accept the original positional shape where the sixth argument was
        # the socket path; new callers should pass the process domain
        # explicitly (preferably by keyword).
        if socket_path is None and isinstance(process_domain, (str, Path)):
            candidate = str(process_domain)
            if candidate.startswith(os.sep):
                socket_path = process_domain
                process_domain = None
        if process_domain is None:
            process_domain = "local"
        process_domain = _canonical_process_domain(
            process_domain, "runtime process domain")
        canonical_socket = _canonical_private_socket(socket_path)
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            if (owner.get("mode") != "managed" or
                    owner.get("daemon_id") != daemon_id or
                    owner.get("generation") != generation or
                    owner.get("process_domain") != process_domain or
                    owner.get("lane_key") != self.identity.lane_key or
                    owner.get("host") != self.identity.host):
                raise _error("ownership-conflict",
                             "runtime registration is not for the current managed owner")
            # A stale/corrupt prior endpoint must never be replaced silently.
            existing = self._load_runtime()
            intent = self._load_recovery_intent()
            if intent is not None:
                # Runtime replacement is a recovery transaction, never a
                # registration side effect.  An exact already-published new
                # endpoint may be retried, but a missing/partial endpoint is
                # reconciled only by ``recover_managed_owner``.
                if (existing is None or intent["state"] != "complete" or
                        not self._owner_matches_recovery_intent(owner, intent, "new") or
                        not self._runtime_matches_recovery_intent(existing, intent, "new")):
                    raise _error("uncertain-effect",
                                 "runtime registration is blocked by recovery intent")
            record: Dict[str, Any] = {
                **native_record_marker("runtime"),
                "daemon_id": daemon_id,
                "generation": generation,
                "lane": self.identity.lane,
                "lane_key": self.identity.lane_key,
                "host": self.identity.host,
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
                "process_domain": process_domain,
                "socket_path": str(canonical_socket),
                "timestamp": time.time(),
            }
            if existing is not None:
                identity_fields = (
                    "schema_version", "architecture", "record_kind",
                    "daemon_id", "generation", "lane_key", "host",
                    "pid", "start_token", "pgid", "process_domain",
                    "socket_path",
                )
                if all(existing[field] == record[field] for field in identity_fields):
                    return existing
                raise _error(
                    "ownership-conflict",
                    "a different daemon runtime is already published; clear or recover it",
                )
            self._write_runtime(record)
            self.append_journal("ownership", {
                "event": "runtime-register",
                **record,
            })
            return dict(record)

    def read_runtime(self, *, timeout: Optional[float] = None,
                     deadline: Optional[float] = None
                     ) -> Optional[Dict[str, Any]]:
        """Read the strict daemon endpoint record, if one is published."""

        self.ensure_layout()
        with self.locked(shared=True, timeout=timeout, deadline=deadline):
            runtime = self._load_runtime()
            owner = self._load_owner()
            intent = self._load_recovery_intent()
            if intent is not None:
                self._validate_recovery_snapshot(owner, runtime, intent)
            if runtime is None:
                return None
            if owner.get("mode") != "managed":
                raise _error("ownership-conflict",
                             "runtime discovery has no current managed owner")
            try:
                owner_lane = canonical_lane(owner["lane"])
                owner_host = _canonical_component(owner["host"], "owner host")
            except (KeyError, TypeError):
                raise _error("invalid", "managed owner record is malformed")
            if (owner.get("daemon_id") != runtime["daemon_id"] or
                    owner.get("generation") != runtime["generation"] or
                    owner.get("process_domain") != runtime["process_domain"] or
                    owner_lane.casefold() != runtime["lane_key"] or
                    owner.get("lane_key") != runtime["lane_key"] or
                    owner_host != runtime["host"] or
                    runtime["lane_key"] != self.identity.lane_key or
                    runtime["host"] != self.identity.host):
                raise _error("ownership-conflict",
                             "runtime discovery is stale for the current managed owner")
            return runtime

    def clear_runtime(self, daemon_id: str, generation: int, pid: int,
                      start_token: str, pgid: int,
                      process_domain: Optional[str] = None
                      ) -> Dict[str, Any]:
        """Remove an endpoint only when every runtime identity matches."""

        daemon_id = _canonical_component(daemon_id, "daemon_id")
        if (isinstance(generation, bool) or not isinstance(generation, int) or
                generation < 1):
            raise _error("invalid", "runtime generation must be a positive integer")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise _error("invalid", "runtime PID must be a positive integer")
        start_token = _opaque_token(start_token, "runtime start token")
        if isinstance(pgid, bool) or not isinstance(pgid, int) or pgid <= 0:
            raise _error("invalid", "runtime process group ID must be a positive integer")
        if process_domain is None:
            process_domain = "local"
        process_domain = _canonical_process_domain(
            process_domain, "runtime process domain")
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            if (owner.get("mode") != "managed" or
                    owner.get("daemon_id") != daemon_id or
                    owner.get("generation") != generation or
                    owner.get("process_domain") != process_domain):
                raise _error("ownership-conflict",
                             "runtime clear is not for the current managed owner")
            intent = self._load_recovery_intent()
            if intent is not None and intent["state"] != "complete":
                raise _error("uncertain-effect",
                             "runtime clear is blocked by pending recovery")
            runtime = self._load_runtime()
            if runtime is None:
                raise _error("ownership-conflict", "managed runtime discovery is absent")
            if (runtime["daemon_id"] != daemon_id or
                    runtime["generation"] != generation or
                    runtime["pid"] != pid or
                    runtime["start_token"] != start_token or
                    runtime["pgid"] != pgid or
                    runtime["process_domain"] != process_domain):
                raise _error("ownership-conflict",
                             "runtime identity does not match the published endpoint")
            path = self._json_path(_RUNTIME_NAME)
            _assert_private(path, directory=False)
            try:
                path.unlink()
            except OSError as exc:
                raise _error("unsafe-state", "managed runtime clear failed: %s" % exc)
            _fsync_directory(path.parent)
            self.append_journal("ownership", {
                "event": "runtime-clear",
                **runtime,
            })
            return {}

    @staticmethod
    def _validate_exclusion_proof(proof: Mapping[str, Any], pid: int,
                                  start_token: str, pgid: int,
                                  process_domain: str) -> None:
        """Require complete trusted evidence that one old process group is gone."""

        required = {
            "pid", "start_token", "pgid", "process_group_owned", "exited",
            "group_excluded", "process_domain",
        }
        if not isinstance(proof, Mapping) or set(proof) != required:
            raise _error("live-unverified",
                         "managed recovery lacks complete old-group exclusion evidence")
        proof_pid = proof.get("pid")
        proof_pgid = proof.get("pgid")
        proof_start = proof.get("start_token")
        proof_domain = proof.get("process_domain")
        if (isinstance(proof_pid, bool) or not isinstance(proof_pid, int) or
                proof_pid != pid or isinstance(proof_pgid, bool) or
                not isinstance(proof_pgid, int) or proof_pgid != pgid or
                not isinstance(proof_start, str) or proof_start != start_token or
                proof_domain != process_domain or
                proof["process_group_owned"] is not True or
                proof["exited"] is not True or
                proof["group_excluded"] is not True):
            raise _error("live-unverified",
                         "managed recovery old-group exclusion evidence is not authoritative")

    def recover_managed_owner(
            self, old_daemon_id: str, old_generation: int, old_pid: int,
            old_start_token: str, old_pgid: int, new_daemon_id: str,
            new_pid: int, new_start_token: str, new_pgid: int,
            process_domain: Optional[str] = None, socket_path: Any = None,
            exclusion_proof: Optional[Mapping[str, Any]] = None,
            request_id: Optional[str] = None, *,
            old_process_domain: Optional[str] = None,
            new_process_domain: Optional[str] = None,
            claimant_exclusion_proof: Optional[Mapping[str, Any]] = None
            ) -> Dict[str, Any]:
        """Reconcile one durable supervisor-incarnation recovery transaction.

        A strict pending intent is fsynced before either owner or runtime file
        changes.  A later same-request bootstrap can therefore finish after a
        crash at either replacement boundary without clearing ownership.
        """

        old_daemon_id = _canonical_component(old_daemon_id, "old daemon_id")
        new_daemon_id = _canonical_component(new_daemon_id, "new daemon_id")
        if old_daemon_id == new_daemon_id:
            raise _error("ownership-conflict",
                         "managed recovery requires a new daemon incarnation")
        if (isinstance(old_generation, bool) or
                not isinstance(old_generation, int) or old_generation < 1):
            raise _error("invalid", "old managed generation must be positive")
        if isinstance(old_pid, bool) or not isinstance(old_pid, int) or old_pid <= 0:
            raise _error("invalid", "old managed PID must be positive")
        old_start_token = _opaque_token(old_start_token, "old managed start token")
        if isinstance(old_pgid, bool) or not isinstance(old_pgid, int) or old_pgid <= 0:
            raise _error("invalid", "old managed process group ID must be positive")
        if process_domain is not None:
            common_process_domain = _canonical_process_domain(
                process_domain, "managed process domain")
            if old_process_domain is not None:
                checked_old_domain = _canonical_process_domain(
                    old_process_domain, "old managed process domain")
                if checked_old_domain != common_process_domain:
                    raise _error("ownership-conflict",
                                 "old managed process domain does not match recovery request")
                old_process_domain = checked_old_domain
            else:
                old_process_domain = common_process_domain
            if new_process_domain is not None:
                checked_new_domain = _canonical_process_domain(
                    new_process_domain, "new managed process domain")
                if checked_new_domain != common_process_domain:
                    raise _error("ownership-conflict",
                                 "new managed process domain does not match recovery request")
                new_process_domain = checked_new_domain
            else:
                new_process_domain = common_process_domain
        else:
            old_process_domain = _canonical_process_domain(
                old_process_domain if old_process_domain is not None else "local",
                "old managed process domain")
            new_process_domain = _canonical_process_domain(
                new_process_domain if new_process_domain is not None
                else old_process_domain,
                "new managed process domain")
        if isinstance(new_pid, bool) or not isinstance(new_pid, int) or new_pid <= 0:
            raise _error("invalid", "new managed PID must be positive")
        new_start_token = _opaque_token(new_start_token, "new managed start token")
        if isinstance(new_pgid, bool) or not isinstance(new_pgid, int) or new_pgid <= 0:
            raise _error("invalid", "new managed process group ID must be positive")
        # Recovery is normally same-domain, but retain the exact domain value
        # for the new incarnation instead of inferring it from host/PID.
        new_process_domain = _canonical_process_domain(
            new_process_domain, "new managed process domain")
        request_id = _opaque_token(request_id, "recovery request_id")
        self._validate_exclusion_proof(
            exclusion_proof, old_pid, old_start_token, old_pgid,
            old_process_domain)
        canonical_socket = _canonical_private_socket(socket_path)
        self.ensure_layout()

        with self.locked():
            intent = self._load_recovery_intent()
            owner = self._load_owner()
            ledger = self._load_generation()
            if ledger is not None and ledger != old_generation:
                raise _error("invalid", "managed generation ledger disagrees with owner")
            runtime = self._load_runtime()

            if intent is not None:
                expected = {
                    "request_id": request_id,
                    "lane_key": self.identity.lane_key,
                    "host": self.identity.host,
                    "old_daemon_id": old_daemon_id,
                    "old_generation": old_generation,
                    "old_pid": old_pid,
                    "old_start_token": old_start_token,
                    "old_pgid": old_pgid,
                    "old_process_domain": old_process_domain,
                    "new_daemon_id": new_daemon_id,
                    "new_generation": old_generation,
                    "new_pid": new_pid,
                    "new_start_token": new_start_token,
                    "new_pgid": new_pgid,
                    "new_process_domain": new_process_domain,
                    "new_socket_path": str(canonical_socket),
                }
                request_matches = all(intent[key] == value
                                      for key, value in expected.items())
                if not request_matches and intent["state"] == "complete":
                    # A completed transaction is only a historical marker.
                    # Retire it after a fresh exact CAS against the currently
                    # published owner/runtime, leaving both durable records
                    # continuously managed while the next intent is created.
                    current_owner = self._owner_matches_recovery_intent(
                        owner, intent, "new")
                    current_runtime = self._runtime_matches_recovery_intent(
                        runtime, intent, "new")
                    current_identity = self._recovery_identity_matches(
                        intent, "new", old_daemon_id, old_generation, old_pid,
                        old_start_token, old_pgid, old_process_domain)
                    if (request_id == intent["request_id"] or
                            not current_owner or not current_runtime or
                            not current_identity):
                        raise _error(
                            "ownership-conflict",
                            "managed recovery request does not match its completed intent",
                        )
                    self._load_claims()
                    self.append_journal("ownership", {
                        "event": "managed-recover-intent-retire",
                        "retired_request_id": intent["request_id"],
                        "retired_daemon_id": intent["new_daemon_id"],
                        "retired_generation": intent["new_generation"],
                        "daemon_id": old_daemon_id,
                        "generation": old_generation,
                        "request_id": request_id,
                    })
                    self._remove_recovery_intent()
                    intent = None
                elif not request_matches and intent["state"] == "pending":
                    # A pending claimant may be replaced only after the
                    # original request's old supervisor *and* its recorded
                    # claimant have independently been excluded.  A host name
                    # or matching numeric PID is never sufficient evidence.
                    original_old = self._recovery_identity_matches(
                        intent, "old", old_daemon_id, old_generation, old_pid,
                        old_start_token, old_pgid, old_process_domain)
                    if request_id == intent["request_id"] or not original_old:
                        raise _error(
                            "ownership-conflict",
                            "managed recovery request does not match its pending intent",
                        )
                    self._validate_exclusion_proof(
                        claimant_exclusion_proof,
                        intent["new_pid"], intent["new_start_token"],
                        intent["new_pgid"], intent["new_process_domain"],
                    )
                    owner_old = self._owner_matches_recovery_intent(
                        owner, intent, "old")
                    owner_claimant = self._owner_matches_recovery_intent(
                        owner, intent, "new")
                    runtime_old = self._runtime_matches_recovery_intent(
                        runtime, intent, "old")
                    runtime_claimant = self._runtime_matches_recovery_intent(
                        runtime, intent, "new")
                    if owner_old and runtime_old:
                        base_prefix = "old"
                    elif owner_claimant and runtime_claimant:
                        base_prefix = "new"
                    else:
                        raise _error(
                            "uncertain-effect",
                            "pending recovery has a mixed owner/runtime boundary",
                        )
                    base_identity = (
                        intent[base_prefix + "_daemon_id"],
                        intent[base_prefix + "_generation"],
                        intent[base_prefix + "_pid"],
                        intent[base_prefix + "_start_token"],
                        intent[base_prefix + "_pgid"],
                        intent[base_prefix + "_process_domain"],
                    )
                    if new_daemon_id == base_identity[0]:
                        raise _error(
                            "ownership-conflict",
                            "managed recovery requires a new daemon incarnation",
                        )
                    self._load_claims()
                    self.append_journal("ownership", {
                        "event": "managed-recover-claimant-retire",
                        "retired_request_id": intent["request_id"],
                        "retired_daemon_id": intent["new_daemon_id"],
                        "retired_pid": intent["new_pid"],
                        "retired_pgid": intent["new_pgid"],
                        "retired_process_domain": intent["new_process_domain"],
                        "request_id": request_id,
                    })
                    self._remove_recovery_intent()
                    (old_daemon_id, old_generation, old_pid,
                     old_start_token, old_pgid,
                     old_process_domain) = base_identity
                    intent = None
                elif not request_matches:
                    raise _error("invalid", "managed recovery intent has unknown state")

            if intent is not None and intent["state"] == "complete":
                if (not self._owner_matches_recovery_intent(owner, intent, "new") or
                        not self._runtime_matches_recovery_intent(runtime, intent, "new")):
                    raise _error("uncertain-effect",
                                 "completed recovery intent does not match durable state")
                self._load_claims()
                return dict(owner)

            if intent is None:
                if not self._owner_matches_recovery_intent(
                        owner, {
                            "old_daemon_id": old_daemon_id,
                            "old_generation": old_generation,
                            "old_process_domain": old_process_domain,
                        }, "old"):
                    raise _error("ownership-conflict",
                                 "managed recovery owner CAS does not match current state")
                if runtime is None:
                    raise _error("live-unverified",
                                 "managed recovery has no old runtime identity to exclude")
                if (runtime["daemon_id"] != old_daemon_id or
                        runtime["generation"] != old_generation or
                        runtime["pid"] != old_pid or
                        runtime["start_token"] != old_start_token or
                        runtime["pgid"] != old_pgid or
                        runtime["process_domain"] != old_process_domain):
                    raise _error("ownership-conflict",
                                 "managed recovery runtime CAS does not match current state")
                self._load_claims()
                intent = {
                    **native_record_marker("recovery-intent"),
                    "state": "pending",
                    "request_id": request_id,
                    "lane": self.identity.lane,
                    "lane_key": self.identity.lane_key,
                    "host": self.identity.host,
                    "old_daemon_id": old_daemon_id,
                    "old_generation": old_generation,
                    "old_pid": old_pid,
                    "old_start_token": old_start_token,
                    "old_pgid": old_pgid,
                    "old_process_domain": old_process_domain,
                    "old_socket_path": runtime["socket_path"],
                    "new_daemon_id": new_daemon_id,
                    "new_generation": old_generation,
                    "new_pid": new_pid,
                    "new_start_token": new_start_token,
                    "new_pgid": new_pgid,
                    "new_process_domain": new_process_domain,
                    "new_socket_path": str(canonical_socket),
                    "new_timestamp": time.time(),
                }
                # This is the durable transaction boundary.  It must precede
                # generation, owner, runtime, and journal transition writes.
                self._write_recovery_intent(intent)
                self.append_journal("ownership", {
                    "event": "managed-recover-intent",
                    "request_id": request_id,
                    "old_daemon_id": old_daemon_id,
                    "old_generation": old_generation,
                    "old_pid": old_pid,
                    "old_start_token": old_start_token,
                    "old_pgid": old_pgid,
                    "old_process_domain": old_process_domain,
                    "new_daemon_id": new_daemon_id,
                    "new_pid": new_pid,
                    "new_start_token": new_start_token,
                    "new_pgid": new_pgid,
                    "new_process_domain": new_process_domain,
                    "new_socket_path": str(canonical_socket),
                })
            else:
                # A pending intent is the authority for the exact replacement
                # values after a crash; all claims remain untouched.
                self._load_claims()

            owner_old = self._owner_matches_recovery_intent(owner, intent, "old")
            owner_new = self._owner_matches_recovery_intent(owner, intent, "new")
            runtime_old = self._runtime_matches_recovery_intent(runtime, intent, "old")
            runtime_new = self._runtime_matches_recovery_intent(runtime, intent, "new")
            if not (owner_old or owner_new) or not (runtime_old or runtime_new):
                raise _error("uncertain-effect",
                             "managed recovery found an unrecognized owner/runtime boundary")

            new_owner = dict(owner)
            new_owner["daemon_id"] = intent["new_daemon_id"]
            new_owner["process_domain"] = intent["new_process_domain"]
            new_runtime: Dict[str, Any] = {
                **native_record_marker("runtime"),
                "daemon_id": intent["new_daemon_id"],
                "generation": intent["new_generation"],
                "lane": intent["lane"],
                "lane_key": intent["lane_key"],
                "host": intent["host"],
                "pid": intent["new_pid"],
                "start_token": intent["new_start_token"],
                "pgid": intent["new_pgid"],
                "process_domain": intent["new_process_domain"],
                "socket_path": intent["new_socket_path"],
                "timestamp": intent["new_timestamp"],
            }
            if ledger is None:
                self._write_generation(old_generation)
            # Complete whichever side of the two-file boundary is still old.
            if owner_old:
                self._write_owner(new_owner)
            if runtime_old:
                self._write_runtime(new_runtime)
            completed = dict(intent)
            completed["state"] = "complete"
            self._write_recovery_intent(completed)
            self.append_journal("ownership", {
                "event": "managed-recover",
                "request_id": intent["request_id"],
                "old_daemon_id": intent["old_daemon_id"],
                "new_daemon_id": intent["new_daemon_id"],
                "generation": intent["old_generation"],
                "new_pid": intent["new_pid"],
                "new_pgid": intent["new_pgid"],
                "new_process_domain": intent["new_process_domain"],
            })
            return dict(new_owner)

    def unenroll_managed(self, daemon_id: str, generation: int, *,
                         quiescent: bool, claims_released: bool = True
                         ) -> Dict[str, Any]:
        """Remove an exact managed owner after authoritative quiescence.

        Active claims and a published runtime are prerequisites owned by their
        respective lifecycle operations.  This method never guesses process
        liveness or clears another generation's state.
        """

        daemon_id = _canonical_component(daemon_id, "daemon_id")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise _error("invalid", "managed generation must be positive")
        if quiescent is not True or claims_released is not True:
            raise _error("live-unverified",
                         "managed unenrollment requires authoritative quiescence")
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            if (owner.get("mode") != "managed" or
                    owner.get("daemon_id") != daemon_id or
                    owner.get("generation") != generation or
                    owner.get("lane_key") != self.identity.lane_key or
                    owner.get("host") != self.identity.host):
                raise _error("ownership-conflict",
                             "managed unenrollment owner CAS does not match current state")
            ledger = self._load_generation()
            if ledger is not None and ledger != generation:
                raise _error("invalid", "managed generation ledger disagrees with owner")
            intent = self._load_recovery_intent()
            if intent is not None:
                if intent["state"] != "complete":
                    raise _error("uncertain-effect",
                                 "managed recovery is not complete")
                self._validate_recovery_snapshot(owner, self._load_runtime(), intent)
            claims = self._load_claims()
            if any(claim["lane_key"] == self.identity.lane_key for claim in claims):
                raise _error("ownership-conflict",
                             "managed unenrollment requires all lane writer claims released")
            runtime = self._load_runtime()
            if runtime is not None:
                raise _error("ownership-conflict",
                             "managed runtime must be cleared before unenrollment")
            # Once all quiescence prerequisites are true, retire a completed
            # recovery marker immediately before clearing the owner.  A crash
            # before the owner write leaves managed ownership intact; a retry
            # can finish using the monotonic generation ledger.
            if intent is not None:
                self._remove_recovery_intent()
            # Persist the tombstone before removing ownership.  If the owner
            # write fails, the higher durable generation still prevents reuse.
            if ledger is None:
                self._write_generation(generation)
            self._write_owner({})
            self.append_journal("ownership", {
                "event": "managed-unenroll",
                "daemon_id": daemon_id,
                "generation": generation,
                "lane": owner["lane"],
                "lane_key": owner["lane_key"],
                "host": owner["host"],
                "process_domain": owner["process_domain"],
                "tombstone_generation": generation,
            })
            return {}

    def begin_pending_launch(self, pid: int, start_token: str,
                             request_id: str) -> Dict[str, Any]:
        """Reserve a legacy launch before its external launcher starts.

        The reservation is durable and never expires because its creator
        exits.  Repeating the exact request and PID/start-token holder returns
        the original lease, including its opaque ``lease_id``.
        """

        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise _error("invalid", "pending-launch PID must be a positive integer")
        start_token = _opaque_token(start_token, "pending-launch start token")
        request_id = _opaque_token(request_id, "pending-launch request_id")
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            if self._load_recovery_intent() is not None:
                raise _error("uncertain-effect",
                             "pending managed recovery blocks pending-launch ownership")
            mode = owner.get("mode")
            if mode == "pending-launch":
                if (owner.get("pid") == pid and
                        owner.get("start_token") == start_token and
                        owner.get("request_id") == request_id):
                    return dict(owner)
                raise _error("busy", "lane %s already has a pending launch" %
                             self.identity.lane)
            if mode == "managed":
                raise _error("busy", "lane %s has durable managed ownership" %
                             self.identity.lane)
            if mode == "legacy-lease":
                raise _error("busy", "lane %s already has a legacy lease" %
                             self.identity.lane)
            record: Dict[str, Any] = {
                "mode": "pending-launch",
                "pid": pid,
                "start_token": start_token,
                "request_id": request_id,
                "lease_id": secrets.token_urlsafe(32),
                "lane": self.identity.lane,
                "lane_key": self.identity.lane_key,
                "host": self.identity.host,
                "created_at": time.time(),
            }
            self._write_owner(record)
            self.append_journal("ownership", {
                "event": "pending-launch-begin",
                **record,
            })
            return dict(record)

    def bind_pending_launch(self, lease_id: str, pid: int,
                            start_token: str, pgid: int) -> Dict[str, Any]:
        """Bind an exact pending lease to a verified launcher identity.

        The PID/start-token pair supplied here belongs to the external
        launcher and is intentionally allowed to differ from the creator
        recorded by :meth:`begin_pending_launch`.
        """

        lease_id = _opaque_token(lease_id, "pending-launch lease_id")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise _error("invalid", "pending-launch PID must be a positive integer")
        start_token = _opaque_token(start_token, "pending-launch start token")
        if isinstance(pgid, bool) or not isinstance(pgid, int) or pgid <= 0:
            raise _error("invalid", "pending-launch process group ID must be a positive integer")
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            if (owner.get("mode") != "pending-launch" or
                    owner.get("lease_id") != lease_id):
                raise _error("ownership-conflict",
                             "pending launch lease does not match lane %s" %
                             self.identity.lane)
            creator_pid = owner["pid"]
            creator_start_token = owner["start_token"]
            record: Dict[str, Any] = {
                "mode": "legacy-lease",
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
                "lane": self.identity.lane,
                "lane_key": self.identity.lane_key,
                "host": self.identity.host,
                "created_at": time.time(),
            }
            self._write_owner(record)
            self.append_journal("ownership", {
                "event": "pending-launch-bind",
                "lease_id": lease_id,
                "request_id": owner["request_id"],
                "creator_pid": creator_pid,
                "creator_start_token": creator_start_token,
                **record,
            })
            return dict(record)

    def abort_pending_launch(self, lease_id: str) -> Dict[str, Any]:
        """Clear one exact pending launch reservation."""

        lease_id = _opaque_token(lease_id, "pending-launch lease_id")
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            if (owner.get("mode") != "pending-launch" or
                    owner.get("lease_id") != lease_id):
                raise _error("ownership-conflict",
                             "pending launch lease does not match lane %s" %
                             self.identity.lane)
            self._write_owner({})
            self.append_journal("ownership", {
                "event": "pending-launch-abort",
                "lease_id": lease_id,
                "request_id": owner["request_id"],
                "pid": owner["pid"],
                "start_token": owner["start_token"],
                "lane": owner["lane"],
                "lane_key": owner["lane_key"],
                "host": owner["host"],
            })
            return {}

    def begin_legacy(self, pid: int, start_token: str,
                     pgid: int) -> Dict[str, Any]:
        """Acquire the legacy PID/start-token/process-group lease atomically."""

        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise _error("invalid", "legacy PID must be a positive integer")
        if not isinstance(start_token, str) or not start_token or len(start_token) > 256 or "\x00" in start_token:
            raise _error("invalid", "legacy start token is invalid")
        if isinstance(pgid, bool) or not isinstance(pgid, int) or pgid <= 0:
            raise _error("invalid", "legacy process group ID must be a positive integer")
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            if self._load_recovery_intent() is not None:
                raise _error("uncertain-effect",
                             "managed recovery blocks legacy ownership")
            mode = owner.get("mode")
            if mode == "managed":
                raise _error("busy", "lane %s has durable managed ownership" % self.identity.lane)
            if mode == "legacy-lease":
                if (owner.get("pid") == pid and
                        owner.get("start_token") == start_token and
                        owner.get("pgid") == pgid):
                    return owner
                raise _error("busy", "lane %s already has a legacy lease" % self.identity.lane)
            if mode == "pending-launch":
                raise _error("busy", "lane %s has a pending launch" % self.identity.lane)
            record: Dict[str, Any] = {
                "mode": "legacy-lease",
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
                "lane": self.identity.lane,
                "lane_key": self.identity.lane_key,
                "host": self.identity.host,
                "created_at": time.time(),
            }
            self._write_owner(record)
            self.append_journal("ownership", {"event": "legacy-begin", **record})
            return dict(record)

    def release_legacy(self, pid: int, start_token: str,
                       pgid: int) -> Dict[str, Any]:
        """Release one exact ordinary legacy lease under the state lock.

        This operation authenticates the complete PID/start-token/process-group
        tuple.  It never treats a pending launch as an ordinary lease and does
        not make any process-liveness assertion.
        """

        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise _error("invalid", "legacy PID must be a positive integer")
        start_token = _opaque_token(start_token, "legacy start token")
        if isinstance(pgid, bool) or not isinstance(pgid, int) or pgid <= 0:
            raise _error("invalid", "legacy process group ID must be a positive integer")
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            if owner.get("mode") != "legacy-lease":
                raise _error("ownership-conflict",
                             "lane %s does not have an ordinary legacy lease" %
                             self.identity.lane)
            if (owner.get("pid") != pid or
                    owner.get("start_token") != start_token or
                    owner.get("pgid") != pgid):
                raise _error("ownership-conflict",
                             "legacy lease identity does not match lane %s" %
                             self.identity.lane)
            self._write_owner({})
            self.append_journal("ownership", {
                "event": "legacy-release",
                **owner,
            })
            return {}

    def _read_owner_locked(self) -> Dict[str, Any]:
        """Read and validate the owner without provisioning state.

        The caller must already hold a managed-state lock.  Keeping this
        locked read separate preserves ``read_owner``'s existing provisioning
        behavior while allowing read-only assessments to fail closed if the
        state disappears between their precheck and lock acquisition.
        """

        owner = self._load_owner()
        generation = self._load_generation()
        if (owner.get("mode") == "managed" and generation is not None and
                generation != owner["generation"]):
            raise _error("invalid", "managed generation ledger disagrees with owner")
        intent = self._load_recovery_intent()
        if intent is not None:
            self._validate_recovery_snapshot(owner, self._load_runtime(), intent)
        return dict(owner)

    def read_owner(self, *, timeout: Optional[float] = None,
                   deadline: Optional[float] = None) -> Dict[str, Any]:
        """Return a strict owner snapshot while holding the shared lock."""

        self.ensure_layout()
        with self.locked(shared=True, timeout=timeout, deadline=deadline):
            return self._read_owner_locked()

    def _claim_generation(self, owner: Dict[str, Any]) -> int:
        """Return the current generation for a claim, including after unenroll."""

        if owner.get("mode") == "managed":
            generation = owner["generation"]
            ledger = self._load_generation()
            if ledger is not None and ledger != generation:
                raise _error("invalid", "managed generation ledger disagrees with owner")
            return generation
        ledger = self._load_generation()
        return 1 if ledger is None else ledger

    def enroll_managed(
            self, daemon_id: str, process_domain: Optional[str] = None, *,
            lineage_id: Optional[str] = None,
            coordinator_session_uuid: Optional[str] = None,
            coordinator_read_only: bool = False,
    ) -> Dict[str, Any]:
        """Acquire durable managed ownership under the shared lock."""

        daemon_id = _canonical_component(daemon_id, "daemon_id")
        if lineage_id is not None:
            lineage_id = _opaque_token(lineage_id, "lineage_id")
        if coordinator_session_uuid is not None:
            coordinator_session_uuid = _opaque_token(
                coordinator_session_uuid, "coordinator_session_uuid",
            )
        if not isinstance(coordinator_read_only, bool):
            raise _error("invalid", "coordinator_read_only must be boolean")
        requested_domain = (None if process_domain is None else
                            _canonical_process_domain(
                                process_domain, "managed process domain"))
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            mode = owner.get("mode")
            if requested_domain is None:
                # Preserve the old one-argument API for a first enrollment,
                # while retries of an existing owner remain exact.
                requested_domain = (owner.get("process_domain")
                                    if mode == "managed" else "local")
                requested_domain = _canonical_process_domain(
                    requested_domain, "managed process domain")
            intent = self._load_recovery_intent()
            if intent is not None:
                if (intent["state"] == "complete" and
                        self._owner_matches_recovery_intent(owner, intent, "new") and
                        owner.get("daemon_id") == daemon_id and
                        owner.get("process_domain") == requested_domain):
                    ledger = self._load_generation()
                    if ledger is not None and ledger != owner["generation"]:
                        raise _error("invalid",
                                     "managed generation ledger disagrees with owner")
                    if ledger is None:
                        self._write_generation(owner["generation"])
                    return dict(owner)
                raise _error("uncertain-effect",
                             "managed recovery intent blocks enrollment")
            if mode == "managed":
                if owner.get("daemon_id") != daemon_id:
                    raise _error("busy", "lane %s already has managed ownership" % self.identity.lane)
                if owner.get("process_domain") != requested_domain:
                    raise _error("ownership-conflict",
                                 "managed process domain does not match current owner")
                if (lineage_id is not None and
                        owner.get("lineage_id") not in (None, lineage_id)):
                    raise _error("ownership-conflict",
                                 "managed owner lineage does not match current owner")
                if (coordinator_session_uuid is not None and
                        owner.get("coordinator_session_uuid") not in
                        (None, coordinator_session_uuid)):
                    raise _error(
                        "ownership-conflict",
                        "managed owner coordinator identity does not match current owner",
                    )
                ledger = self._load_generation()
                if ledger is not None and ledger != owner["generation"]:
                    raise _error("invalid", "managed generation ledger disagrees with owner")
                if ledger is None:
                    self._write_generation(owner["generation"])
                return owner
            if mode == "legacy-lease":
                raise _error("busy", "lane %s has a legacy lease" % self.identity.lane)
            if mode == "pending-launch":
                raise _error("busy", "lane %s has a pending launch" % self.identity.lane)
            generation = self._load_generation()
            if generation is None:
                generation = 0
            record: Dict[str, Any] = {
                **native_record_marker("managed-owner"),
                "mode": "managed",
                "daemon_id": daemon_id,
                "generation": generation + 1,
                "lane": self.identity.lane,
                "lane_key": self.identity.lane_key,
                "host": self.identity.host,
                "process_domain": requested_domain,
                "created_at": time.time(),
            }
            if lineage_id is not None:
                record["lineage_id"] = lineage_id
            if coordinator_session_uuid is not None:
                record["coordinator_session_uuid"] = coordinator_session_uuid
            if coordinator_read_only:
                record["coordinator_read_only"] = True
            self._write_generation(record["generation"])
            self._write_owner(record)
            self.append_journal("ownership", {"event": "managed-enroll", **record})
            return dict(record)

    def _load_claims(self) -> list[Dict[str, Any]]:
        path = self.identity.global_root / _CLAIMS_NAME
        raw = self._read_path(path)
        if raw is None:
            return []
        validate_native_lineage_record(
            raw, record_kind="lineage-claims", label="global lineage claim index",
        )
        if (set(raw) != {"schema_version", "architecture", "record_kind",
                         "claims"}):
            raise _error("invalid", "global lineage claim index is invalid")
        claims = raw.get("claims", [])
        if not isinstance(claims, list):
            raise _error("invalid", "global lineage claim index is invalid")
        result: list[Dict[str, Any]] = []
        for claim in claims:
            if not isinstance(claim, dict):
                raise _error("invalid", "global lineage claim is not an object")
            claim_kind = claim.get("record_kind")
            if claim_kind not in {"workspace-claim", "child-worktree-claim"}:
                raise _error("unsupported", "global lineage claim kind is unknown")
            validate_native_lineage_record(
                claim, record_kind=claim_kind, label="global lineage claim",
            )
            base_required = {
                "schema_version", "architecture", "record_kind", "state",
                "claim_kind", "lineage_id", "owner_generation",
                "lineage_generation", "lane", "lane_key", "host", "workspace",
                "common_dir", "repository", "claimed_at",
            }
            optional = {"coordinator_session_uuid"}
            if claim_kind == "workspace-claim":
                required = base_required | {"parent_read_only"}
            else:
                required = base_required | {
                    "worktree", "agent_id", "task_id",
                }
                optional |= {"definition_digest", "capability_digest"}
            if not required.issubset(claim) or set(claim) - required - optional:
                raise _error("invalid", "global lineage claim is malformed")
            expected_claim_kind = (
                "workspace" if claim_kind == "workspace-claim" else "child-worktree"
            )
            if claim.get("claim_kind") != expected_claim_kind:
                raise _error("invalid", "global lineage claim kind is malformed")
            if claim.get("state") != "active":
                raise _error("invalid", "global lineage claim has an unknown state")
            try:
                lane = canonical_lane(claim["lane"])
                lane_key = claim["lane_key"]
                host = _canonical_component(claim["host"], "claim host")
                lineage_id = _opaque_token(claim["lineage_id"], "claim lineage_id")
                coordinator_session_uuid = claim.get("coordinator_session_uuid")
                if coordinator_session_uuid is not None:
                    coordinator_session_uuid = _opaque_token(
                        coordinator_session_uuid,
                        "claim coordinator_session_uuid",
                    )
                workspace = self._canonical_record_path(
                    claim["workspace"], "claim workspace")
                repository = self._canonical_record_path(
                    claim["repository"], "claim repository")
                common_dir = self._canonical_record_path(
                    claim["common_dir"], "claim common_dir")
                worktree = (None if claim_kind == "workspace-claim" else
                            self._canonical_record_path(
                                claim["worktree"], "claim worktree"))
            except (KeyError, TypeError):
                raise _error("invalid", "global lineage claim is malformed")
            claimed_at = claim.get("claimed_at")
            if (isinstance(claimed_at, bool) or
                    not isinstance(claimed_at, (int, float))):
                raise _error("invalid", "global lineage claim is malformed")
            try:
                claimed_at_finite = math.isfinite(float(claimed_at))
            except (OverflowError, TypeError, ValueError):
                claimed_at_finite = False
            owner_generation = claim.get("owner_generation")
            lineage_generation = claim.get("lineage_generation")
            if (not isinstance(lane_key, str) or lane_key != lane.casefold() or
                    host != self.identity.host or
                    common_dir != self.identity.common_dir or
                    lineage_id != claim["lineage_id"] or
                    (coordinator_session_uuid is not None and
                     coordinator_session_uuid != claim["coordinator_session_uuid"]) or
                    str(workspace) != claim["workspace"] or
                    str(repository) != claim["repository"] or
                    str(common_dir) != claim["common_dir"] or
                    isinstance(owner_generation, bool) or
                    not isinstance(owner_generation, int) or owner_generation <= 0 or
                    isinstance(lineage_generation, bool) or
                    not isinstance(lineage_generation, int) or lineage_generation <= 0 or
                    not claimed_at_finite):
                raise _error("invalid", "global lineage claim is malformed")
            if claim_kind == "workspace-claim":
                if not isinstance(claim.get("parent_read_only"), bool):
                    raise _error("invalid", "global workspace claim is malformed")
            else:
                agent_id = _opaque_token(claim["agent_id"],
                                         "claim agent_id")
                task_id = _opaque_token(claim["task_id"],
                                        "claim task_id")
                definition_digest = claim.get("definition_digest")
                capability_digest = claim.get("capability_digest")
                if (agent_id != claim["agent_id"] or
                        task_id != claim["task_id"] or
                        worktree is None or str(worktree) != claim["worktree"] or
                        (definition_digest is not None and
                         not re.fullmatch(r"[0-9a-f]{64}", str(definition_digest))) or
                        (capability_digest is not None and
                         not re.fullmatch(r"[0-9a-f]{64}", str(capability_digest)))):
                    raise _error("invalid", "global child worktree claim is malformed")
            result.append(dict(claim))
        return result

    def _write_claims(self, claims: list[Dict[str, Any]]) -> None:
        marked_claims = [
            _native_record_with_marker(
                claim, claim.get("record_kind", ""), "global lineage claim",
            )
            for claim in claims
        ]
        payload = {
            **native_record_marker("lineage-claims"),
            "claims": marked_claims,
        }
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True,
                              separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        self._atomic_write(self.identity.global_root / _CLAIMS_NAME, encoded)

    @staticmethod
    def _canonical_worktree(value: Any) -> Path:
        if isinstance(value, Path):
            path = value
        elif isinstance(value, str):
            path = Path(value)
        else:
            raise _error("invalid", "worktree must be a path")
        if not path.is_absolute():
            raise _error("invalid", "worktree must be an absolute path")
        try:
            return path.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise _error("invalid", "worktree path cannot be resolved: %s" % exc)

    @staticmethod
    def _canonical_record_path(value: Any, label: str) -> Path:
        """Load a persisted path only when it is absolute and canonical.

        Claims are an authority, not a best-effort cache.  In particular, a
        relative or symlink/``..`` spelling must not be silently normalized
        while another claim operation is rewriting the index.
        """

        if not isinstance(value, str) or not value:
            raise _error("invalid", "%s must be an absolute canonical path" % label)
        path = Path(value)
        if not path.is_absolute():
            raise _error("invalid", "%s must be an absolute canonical path" % label)
        try:
            canonical = path.resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise _error("invalid", "%s cannot be resolved: %s" % (label, exc))
        if str(canonical) != value:
            raise _error("invalid", "%s is not a canonical path" % label)
        return canonical

    @staticmethod
    def _canonical_repository(value: Any, worktree: Path) -> str:
        if value is None:
            candidate = worktree
            command = ["git", "-C", str(worktree), "rev-parse",
                       "--path-format=absolute", "--git-common-dir"]
            try:
                result = subprocess.run(command, capture_output=True, text=True, check=False,
                                        timeout=HELPER_TIMEOUT_SECONDS)
                if result.returncode == 0 and result.stdout.strip():
                    candidate = Path(result.stdout.strip())
                    if not candidate.is_absolute():
                        candidate = worktree / candidate
            except (OSError, subprocess.TimeoutExpired):
                candidate = worktree
        else:
            if not isinstance(value, (str, Path)):
                raise _error("invalid", "repository must be a path")
            candidate = Path(value)
            if not candidate.is_absolute():
                raise _error("invalid", "repository must be an absolute path")
        return str(candidate.resolve(strict=False))

    @staticmethod
    def _paths_overlap(first: Path, second: Path) -> bool:
        try:
            first.relative_to(second)
            return True
        except ValueError:
            pass
        try:
            second.relative_to(first)
            return True
        except ValueError:
            return False

    @staticmethod
    def _native_child_facts(
            child: Any, lineage_id: str,
            coordinator_session_uuid: str) -> Dict[str, Any]:
        """Validate one actual native child capability for claim admission.

        This boundary accepts only the native ``agent_id``/``task_id`` and
        parent-link fields.  A child session, mailbox, process group, runner,
        or participant alias is not an alternate spelling of a native child;
        if one is supplied the capability is unknown and the claim is held.
        """

        if hasattr(child, "to_dict") and callable(getattr(child, "to_dict")):
            child = child.to_dict()
        if not isinstance(child, Mapping):
            raise _error("unsupported", "native child identity is unavailable")
        forbidden = {
            "participant_id", "session_id", "session_uuid", "uuid", "mailbox",
            "mailbox_id", "process_group_id", "pgid", "runner_id",
            "runner_instance_id", "child_id", "agentId", "taskId", "sessionId",
            "mailboxId", "processGroupId",
        }
        if forbidden.intersection(child):
            raise _error(
                "schema-mismatch",
                "native child claim contains a superseded child identity alias",
            )
        try:
            agent_id = _opaque_token(child["agent_id"], "native child agent_id")
            task_id = _opaque_token(child["task_id"], "native child task_id")
            child_lineage = _opaque_token(
                child["lineage_id"], "native child lineage_id",
            )
        except (KeyError, TypeError):
            raise _error("unsupported", "native child identity is incomplete")
        if child_lineage != lineage_id:
            raise _error("ownership-conflict", "native child belongs to another lineage")

        parent_links = child.get("parent_links")
        if not isinstance(parent_links, Mapping):
            raise _error("unsupported", "native child parent linkage is unavailable")
        if any(key in parent_links for key in
               ("session_id", "uuid", "parent_session_id", "sessionId")):
            raise _error(
                "schema-mismatch",
                "native child parent linkage contains a superseded identity alias",
            )
        parent_session = parent_links.get("session_uuid")
        if not isinstance(parent_session, str) or not parent_session:
            raise _error("unsupported", "native child coordinator linkage is unavailable")
        if parent_session != coordinator_session_uuid:
            raise _error("ownership-conflict", "native child has another coordinator parent")
        for link_name in ("parent_agent_id", "parent_task_id", "parent_tool_use_id"):
            if link_name in parent_links and parent_links[link_name] is not None:
                _opaque_token(parent_links[link_name],
                              "native child %s" % link_name)

        definition = child.get("custom_definition")
        if not isinstance(definition, Mapping) or not definition:
            raise _error("unsupported", "native child definition capability is unknown")
        if forbidden.intersection(definition):
            raise _error(
                "schema-mismatch",
                "native child definition contains a superseded identity alias",
            )
        tools = definition.get("tools")
        if not isinstance(tools, (list, tuple, set, frozenset)) or not tools:
            raise _error("unsupported", "native child definition has no effective tools")
        normalized_tools = []
        for tool in tools:
            if not isinstance(tool, str) or not tool.strip():
                raise _error("unsupported", "native child definition has unknown tools")
            normalized_tools.append(tool.strip())
        permission_mode = definition.get("permission_mode")
        if permission_mode is not None and not isinstance(permission_mode, str):
            raise _error("unsupported", "native child permission capability is unknown")
        definition_digest = _native_digest(definition)
        supplied_definition_digest = child.get("definition_digest")
        if supplied_definition_digest is not None and (
                supplied_definition_digest != definition_digest):
            raise _error("ownership-conflict", "native child definition changed")

        capability = child.get("capability")
        if capability is None:
            # A pinned custom definition is the minimum trusted capability
            # evidence for the first native claim slice.  Model tool-input
            # claims are not consulted here.
            capability = {
                "authorized": True,
                "tools": list(normalized_tools),
                "permission_mode": permission_mode,
                "definition_digest": definition_digest,
            }
        elif not isinstance(capability, Mapping):
            raise _error("unsupported", "native child capability is unknown")
        else:
            capability = dict(capability)
            if capability.get("authorized") is not True:
                raise _error("unsupported", "native child capability is not authorized")
            capability_lineage = capability.get("lineage_id")
            if capability_lineage is not None and capability_lineage != lineage_id:
                raise _error("ownership-conflict", "native child capability belongs to another lineage")
            capability_definition_digest = capability.get("definition_digest")
            if (capability_definition_digest is not None and
                    capability_definition_digest != definition_digest):
                raise _error("ownership-conflict", "native child capability definition changed")
            capability_tools = capability.get("tools", normalized_tools)
            if not isinstance(capability_tools,
                              (list, tuple, set, frozenset)) or not capability_tools:
                raise _error("unsupported", "native child capability has no effective tools")
            normalized_tools = []
            for tool in capability_tools:
                if not isinstance(tool, str) or not tool.strip():
                    raise _error("unsupported", "native child capability has unknown tools")
                normalized_tools.append(tool.strip())
            capability["tools"] = list(normalized_tools)
            capability["definition_digest"] = definition_digest
        capability_digest = _native_digest(capability)
        supplied_capability_digest = child.get("capability_digest")
        if (supplied_capability_digest is not None and
                supplied_capability_digest != capability_digest):
            raise _error("ownership-conflict", "native child capability changed")

        read_only = child.get("read_only", False)
        writable_value = child.get("writable")
        if not isinstance(read_only, bool):
            raise _error("unsupported", "native child read-only capability is unknown")
        if writable_value is not None and not isinstance(writable_value, bool):
            raise _error("unsupported", "native child writable capability is unknown")
        write_tools = {
            "edit", "write", "bash", "multiedit", "apply_patch", "notebookedit",
        }
        inferred_writable = any(
            tool.casefold() in write_tools for tool in normalized_tools
        )
        writable = inferred_writable if writable_value is None else writable_value
        if read_only and writable:
            raise _error("ownership-conflict", "native child read-only and writable capabilities disagree")
        if writable and capability.get("authorized") is not True:
            raise _error("unsupported", "native child writable capability is not authorized")
        return {
            "agent_id": agent_id,
            "task_id": task_id,
            "definition_digest": definition_digest,
            "capability_digest": capability_digest,
            "writable": bool(writable),
        }

    @staticmethod
    def _native_claim_path(claim: Mapping[str, Any]) -> Path:
        field = "workspace" if claim.get("record_kind") == "workspace-claim" else "worktree"
        value = claim.get(field)
        if not isinstance(value, str):
            raise _error("unknown", "native claim has no canonical path")
        return Path(value)

    def _native_claim_context(
            self, lineage_id: Any, coordinator_session_uuid: Any,
            owner_generation: Any, lineage_generation: Any,
            parent_read_only: Any) -> Tuple[str, Optional[str], Optional[int], int,
                                             Optional[bool]]:
        lineage_id = _opaque_token(lineage_id, "lineage_id")
        if coordinator_session_uuid is not None:
            coordinator_session_uuid = _opaque_token(
                coordinator_session_uuid, "coordinator_session_uuid",
            )
        if owner_generation is not None and (
                isinstance(owner_generation, bool) or
                not isinstance(owner_generation, int) or owner_generation <= 0):
            raise _error("invalid", "claim owner_generation must be positive")
        if lineage_generation is None:
            lineage_generation = 1
        if (isinstance(lineage_generation, bool) or
                not isinstance(lineage_generation, int) or lineage_generation <= 0):
            raise _error("invalid", "claim lineage_generation must be positive")
        if parent_read_only is not None and not isinstance(parent_read_only, bool):
            raise _error("invalid", "claim parent_read_only must be boolean")
        return (lineage_id, coordinator_session_uuid, owner_generation,
                lineage_generation, parent_read_only)

    def _claim_native_records(
            self, *, lineage_id: str, coordinator_session_uuid: Optional[str],
            owner_generation: Optional[int], lineage_generation: int,
            parent_read_only: Optional[bool], workspace: Path, repository: str,
            common_dir: Optional[Path] = None,
            child_facts: Optional[Mapping[str, Any]] = None,
            child_worktree: Optional[Path] = None,
            child_repository: Optional[str] = None,
            require_existing_workspace: bool = False) -> Dict[str, Any]:
        """Atomically add/reuse a lineage workspace and optional child claim."""

        if common_dir is None:
            common_dir = self.identity.common_dir
        if parent_read_only is None and not require_existing_workspace:
            raise _error("invalid", "native workspace claim read-only policy is required")
        workspace_record: Dict[str, Any] = {
            **native_record_marker("workspace-claim"),
            "claim_kind": "workspace",
            "state": "active",
            "lineage_id": lineage_id,
            "owner_generation": owner_generation,
            "lineage_generation": lineage_generation,
            "lane": self.identity.lane,
            "lane_key": self.identity.lane_key,
            "host": self.identity.host,
            "workspace": str(workspace),
            "common_dir": str(common_dir),
            "repository": repository,
            "parent_read_only": parent_read_only,
            "claimed_at": time.time(),
        }
        if coordinator_session_uuid is not None:
            workspace_record["coordinator_session_uuid"] = coordinator_session_uuid
        child_record: Optional[Dict[str, Any]] = None
        if child_facts is not None:
            if child_worktree is None:
                raise _error("invalid", "native child claim worktree is required")
            if child_worktree == workspace:
                raise _error("unsupported", "native child worktree is not isolated")
            child_record = {
                **native_record_marker("child-worktree-claim"),
                "claim_kind": "child-worktree",
                "state": "active",
                "lineage_id": lineage_id,
                "owner_generation": owner_generation,
                "lineage_generation": lineage_generation,
                "lane": self.identity.lane,
                "lane_key": self.identity.lane_key,
                "host": self.identity.host,
                "workspace": str(workspace),
                "common_dir": str(common_dir),
                "repository": child_repository or repository,
                "worktree": str(child_worktree),
                "claimed_at": time.time(),
            }
            if coordinator_session_uuid is not None:
                child_record["coordinator_session_uuid"] = coordinator_session_uuid
            for digest_name in ("definition_digest", "capability_digest"):
                digest = child_facts.get(digest_name)
                if digest is not None:
                    child_record[digest_name] = digest
            child_record["agent_id"] = child_facts["agent_id"]
            child_record["task_id"] = child_facts["task_id"]

        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            if owner.get("mode") != "managed":
                raise _error(
                    "ownership-conflict",
                    "native lineage claims require durable managed ownership",
                )
            current_owner_generation = owner.get("generation")
            if owner_generation is None:
                owner_generation = current_owner_generation
                workspace_record["owner_generation"] = owner_generation
                if child_record is not None:
                    child_record["owner_generation"] = owner_generation
            if owner_generation != current_owner_generation:
                raise _error("stale-generation", "native lineage claim owner generation is stale")
            if (owner.get("lineage_id") is not None and
                    owner.get("lineage_id") != lineage_id):
                raise _error("ownership-conflict", "native lineage does not match managed owner")
            if (owner.get("coordinator_session_uuid") is not None and
                    owner.get("coordinator_session_uuid") != coordinator_session_uuid):
                raise _error(
                    "ownership-conflict",
                    "native coordinator identity does not match managed owner",
                )
            claims = self._load_claims()
            if require_existing_workspace:
                workspace_identity = [
                    existing for existing in claims
                    if existing.get("record_kind") == "workspace-claim" and
                    existing.get("claim_kind") == "workspace" and
                    existing.get("lineage_id") == lineage_id and
                    existing.get("coordinator_session_uuid") ==
                    coordinator_session_uuid and
                    existing.get("lane_key") == self.identity.lane_key and
                    existing.get("host") == self.identity.host and
                    existing.get("owner_generation") == owner_generation and
                    existing.get("lineage_generation") == lineage_generation and
                    existing.get("common_dir") == str(common_dir) and
                    existing.get("workspace") == str(workspace) and
                    existing.get("repository") == repository
                ]
                if len(workspace_identity) != 1:
                    raise _error(
                        "unknown",
                        "native child claim has no exact lineage workspace claim",
                    )
                inherited_read_only = workspace_identity[0]["parent_read_only"]
                if parent_read_only is None:
                    parent_read_only = inherited_read_only
                    workspace_record["parent_read_only"] = inherited_read_only
                elif parent_read_only != inherited_read_only:
                    raise _error(
                        "ownership-conflict",
                        "native child claim read-only policy differs from workspace claim",
                    )
            additions = [workspace_record]
            if child_record is not None:
                additions.append(child_record)
                # A native child identity is immutable for one lineage
                # generation.  Do this check before path overlap handling so
                # a changed task/worktree cannot evade the claim merely by
                # selecting a new, otherwise-disjoint directory.
                for existing in claims:
                    if (existing.get("record_kind") != "child-worktree-claim" or
                            existing.get("lineage_id") != lineage_id or
                            existing.get("coordinator_session_uuid") !=
                            coordinator_session_uuid or
                            existing.get("lane_key") != self.identity.lane_key or
                            existing.get("host") != self.identity.host or
                            existing.get("common_dir") != str(self.identity.common_dir) or
                            existing.get("owner_generation") != owner_generation or
                            existing.get("lineage_generation") != lineage_generation):
                        continue
                    same_agent = existing.get("agent_id") == child_record.get("agent_id")
                    same_task = existing.get("task_id") == child_record.get("task_id")
                    if ((same_agent and (not same_task or
                                         existing.get("worktree") !=
                                         child_record.get("worktree"))) or
                            (same_task and (not same_agent or
                                            existing.get("worktree") !=
                                            child_record.get("worktree")))):
                        raise _error(
                            "ownership-conflict",
                            "native child identity or worktree changed",
                        )
                    if (same_agent and same_task and
                            (existing.get("definition_digest") !=
                             child_record.get("definition_digest") or
                             existing.get("capability_digest") !=
                             child_record.get("capability_digest"))):
                        raise _error(
                            "ownership-conflict",
                            "native child definition or capability changed",
                        )
            found: Dict[str, Dict[str, Any]] = {}
            for candidate in additions:
                candidate_path = self._native_claim_path(candidate)
                for existing in claims:
                    existing_path = self._native_claim_path(existing)
                    if not self._paths_overlap(candidate_path, existing_path):
                        continue
                    same_lineage = (
                        existing.get("lineage_id") == lineage_id and
                        existing.get("coordinator_session_uuid") ==
                        coordinator_session_uuid and
                        existing.get("lane_key") == self.identity.lane_key and
                        existing.get("host") == self.identity.host and
                        existing.get("common_dir") == str(self.identity.common_dir) and
                        existing.get("owner_generation") == owner_generation and
                        existing.get("lineage_generation") == lineage_generation
                    )
                    same_workspace = (
                        candidate["record_kind"] == "workspace-claim" and
                        existing.get("record_kind") == "workspace-claim" and
                        same_lineage and
                        existing.get("workspace") == candidate.get("workspace") and
                        existing.get("repository") == candidate.get("repository") and
                        existing.get("parent_read_only") == candidate.get("parent_read_only")
                    )
                    same_child = (
                        candidate["record_kind"] == "child-worktree-claim" and
                        existing.get("record_kind") == "child-worktree-claim" and
                        same_lineage and
                        existing.get("worktree") == candidate.get("worktree") and
                        existing.get("repository") == candidate.get("repository") and
                        existing.get("agent_id") == candidate.get("agent_id") and
                        existing.get("task_id") == candidate.get("task_id") and
                        existing.get("definition_digest") == candidate.get("definition_digest") and
                        existing.get("capability_digest") == candidate.get("capability_digest")
                    )
                    # A workspace and its own isolated child may overlap: the
                    # child is still covered by the same lineage.  Distinct
                    # child worktrees never overlap, even under one lineage.
                    inherited_overlap = same_lineage and {
                        candidate["record_kind"], existing.get("record_kind")
                    } == {"workspace-claim", "child-worktree-claim"}
                    if same_workspace or same_child:
                        found[candidate["record_kind"]] = existing
                        continue
                    if inherited_overlap:
                        continue
                    holder = "%s/%s" % (
                        existing.get("lane", "unknown"),
                        existing.get("lineage_id", "unknown"),
                    )
                    raise _error(
                        "ownership-conflict",
                        "native claim overlaps active lineage claim %s" % holder,
                    )
                # Check overlap between two new records.  The workspace row
                # may cover its own child, but two child subclaims may not.
                for prior in additions:
                    if prior is candidate:
                        break
                    prior_path = self._native_claim_path(prior)
                    if not self._paths_overlap(candidate_path, prior_path):
                        continue
                    if {candidate["record_kind"], prior["record_kind"]} == {
                            "workspace-claim", "child-worktree-claim"}:
                        continue
                    raise _error(
                        "ownership-conflict",
                        "native lineage claims overlap each other",
                    )
            new_claims = list(claims)
            for candidate in additions:
                existing = found.get(candidate["record_kind"])
                if existing is None:
                    new_claims.append(candidate)
            if len(new_claims) != len(claims):
                self._write_claims(new_claims)
                for candidate in additions:
                    if candidate["record_kind"] not in found:
                        self.append_journal("claims", {
                            "event": "native-lineage-claim",
                            **candidate,
                        })
            if child_record is not None:
                return dict(found.get("child-worktree-claim", child_record))
            return dict(found.get("workspace-claim", workspace_record))

    def claim_lineage(
            self, lineage_id: Any, workspace: Any = None,
            repository: Any = None, *,
            coordinator_session_uuid: Any = None,
            owner_generation: Any = None,
            lineage_generation: Any = None,
            parent_read_only: bool = False,
            children: Any = None) -> Dict[str, Any]:
        """Claim the canonical workspace for one coordinator execution lineage.

        ``children`` is optional evidence used when a read-only coordinator
        contains a writable native child.  It is validated even when the
        workspace claim is already present, so changed or unknown capability
        cannot silently inherit the old claim.
        """

        (lineage_id, coordinator_session_uuid, owner_generation,
         lineage_generation, parent_read_only) = self._native_claim_context(
             lineage_id, coordinator_session_uuid, owner_generation,
             lineage_generation, parent_read_only,
         )
        if workspace is None:
            workspace = self.identity.workspace_root
        workspace = self._canonical_worktree(workspace)
        repository_id = self._canonical_repository(repository, workspace)
        if children is None:
            child_values: list[Any] = []
        elif isinstance(children, Mapping) or hasattr(children, "to_dict"):
            child_values = [children]
        elif isinstance(children, (str, bytes)):
            raise _error("unsupported", "native child capability list is invalid")
        else:
            try:
                child_values = list(children)
            except TypeError:
                raise _error("unsupported", "native child capability list is invalid")
        facts = [
            self._native_child_facts(
                value, lineage_id, coordinator_session_uuid,
            )
            for value in child_values
        ]
        # The caller asked for a lineage workspace claim; writable children
        # inherit this one claim and do not receive a child row unless an
        # isolated worktree is explicitly selected below.
        return self._claim_native_records(
            lineage_id=lineage_id,
            coordinator_session_uuid=coordinator_session_uuid,
            owner_generation=owner_generation,
            lineage_generation=lineage_generation,
            parent_read_only=parent_read_only,
            workspace=workspace,
            repository=repository_id,
        )

    def claim_lineage_workspace(
            self, *, lineage_id: Any, owner_generation: Any,
            lineage_generation: Any, workspace: Any, common_dir: Any,
            repository: Any, parent_read_only: bool = False,
            coordinator_session_uuid: Any = None) -> Dict[str, Any]:
        """Atomically claim one canonical workspace for a native lineage.

        This is the narrow wire-facing entry point used by the native
        coordinator.  A coordinator session identity is optional evidence;
        it is never fabricated by the store.  The durable owner generation
        and common directory remain mandatory, so an untracked lineage or a
        second lane cannot acquire a claim by guessing an alias.
        """

        (lineage_id, coordinator_session_uuid, owner_generation,
         lineage_generation, parent_read_only) = self._native_claim_context(
             lineage_id, coordinator_session_uuid, owner_generation,
             lineage_generation, parent_read_only,
         )
        if owner_generation is None:
            raise _error("invalid", "claim owner_generation is required")
        workspace = self._canonical_worktree(workspace)
        common_path = self._canonical_record_path(common_dir, "claim common_dir")
        if common_path != self.identity.common_dir:
            raise _error(
                "ownership-conflict",
                "native lineage claim common directory does not match workspace identity",
            )
        repository_id = self._canonical_repository(repository, workspace)
        return self._claim_native_records(
            lineage_id=lineage_id,
            coordinator_session_uuid=coordinator_session_uuid,
            owner_generation=owner_generation,
            lineage_generation=lineage_generation,
            parent_read_only=parent_read_only,
            workspace=workspace,
            common_dir=common_path,
            repository=repository_id,
        )

    def claim_child_worktree(
            self, lineage_id: Any, child: Any = None, worktree: Any = None,
            repository: Any = None, *,
            coordinator_session_uuid: Any = None,
            owner_generation: Any = None,
            lineage_generation: Any = None,
            parent_read_only: Optional[bool] = None,
            workspace: Any = None, common_dir: Any = None,
            agent_id: Any = None, task_id: Any = None,
            definition_digest: Any = None,
            capability_digest: Any = None) -> Dict[str, Any]:
        """Add one exact isolated native-child worktree claim atomically."""

        (lineage_id, coordinator_session_uuid, owner_generation,
         lineage_generation, parent_read_only) = self._native_claim_context(
             lineage_id, coordinator_session_uuid, owner_generation,
             lineage_generation, parent_read_only,
         )
        if workspace is None:
            workspace = self.identity.workspace_root
        workspace = self._canonical_worktree(workspace)
        child_worktree = self._canonical_worktree(worktree)
        if common_dir is None:
            common_path = self.identity.common_dir
        else:
            common_path = self._canonical_record_path(common_dir, "claim common_dir")
        if common_path != self.identity.common_dir:
            raise _error(
                "ownership-conflict",
                "native child claim common directory does not match workspace identity",
            )
        repository_id = self._canonical_repository(repository, workspace)
        child_repository = self._canonical_repository(repository, child_worktree)
        if child is None:
            # Direct native callers provide the actual runtime IDs.  No
            # session/mailbox/process identity is generated as a substitute.
            facts = {
                "agent_id": _opaque_token(agent_id, "native child agent_id"),
                "task_id": _opaque_token(task_id, "native child task_id"),
                "writable": True,
            }
            forbidden = {
                "session_id", "session_uuid", "uuid", "mailbox", "mailbox_id",
                "process_group_id", "pgid", "runner_id",
            }
            if any(name in facts for name in forbidden):
                raise _error(
                    "schema-mismatch",
                    "native child claim contains a superseded child identity alias",
                )
            for digest_name, digest in (("definition_digest", definition_digest),
                                        ("capability_digest", capability_digest)):
                if digest is not None:
                    if (not isinstance(digest, str) or
                            not re.fullmatch(r"[0-9a-f]{64}", digest)):
                        raise _error("invalid", "native child %s is invalid" % digest_name)
                    facts[digest_name] = digest
        else:
            facts = self._native_child_facts(
                child, lineage_id, coordinator_session_uuid,
            )
            if not facts.get("writable"):
                raise _error(
                    "unsupported",
                    "native child worktree claim requires an authorized writable child",
                )
        return self._claim_native_records(
            lineage_id=lineage_id,
            coordinator_session_uuid=coordinator_session_uuid,
            owner_generation=owner_generation,
            lineage_generation=lineage_generation,
            parent_read_only=parent_read_only,
            workspace=workspace,
            common_dir=common_path,
            repository=repository_id,
            child_facts=facts,
            child_worktree=child_worktree,
            child_repository=child_repository,
            require_existing_workspace=True,
        )

    def read_lineage_claims(self) -> list[Dict[str, Any]]:
        """Read the validated native global claim index without mutation."""

        self.ensure_layout()
        with self.locked(shared=True):
            return [dict(claim) for claim in self._load_claims()]

    @staticmethod
    def _strict_claim_snapshot_bytes(value: Mapping[str, Any]) -> bytes:
        """Encode one caller snapshot without Python's loose equality rules.

        Claim snapshots come from JSON, but the internal transfer boundary is
        also callable by Python code.  Canonical JSON keeps ``True`` distinct
        from ``1`` and ``1.0`` distinct from ``1`` before a snapshot can be
        accepted as a compare-and-swap witness.
        """

        if any(not isinstance(key, str) for key in value):
            raise _error("invalid", "native lineage claim snapshot has a non-string key")
        try:
            encoded = json.dumps(
                dict(value), ensure_ascii=True, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as exc:
            raise _error("invalid", "native lineage claim snapshot is not JSON: %s" % exc)
        if len(encoded) > MAX_JSON_BYTES:
            raise _error("invalid", "native lineage claim snapshot exceeds one MiB")
        return encoded

    def _validate_workspace_claim_snapshot(
            self, expected_claim: Mapping[str, Any]) -> Tuple[Dict[str, Any], bytes]:
        """Validate and canonically encode a complete workspace claim witness."""

        if not isinstance(expected_claim, Mapping):
            raise _error("invalid", "expected native workspace claim is not an object")
        try:
            if any(not isinstance(key, str) for key in expected_claim):
                raise _error(
                    "invalid",
                    "expected native workspace claim has a non-string key",
                )
            value = dict(expected_claim)
        except (TypeError, ValueError) as exc:
            raise _error("invalid", "expected native workspace claim is malformed: %s" % exc)

        validate_native_lineage_record(
            value, record_kind="workspace-claim",
            label="expected native workspace claim",
        )
        required = {
            "schema_version", "architecture", "record_kind", "state",
            "claim_kind", "lineage_id", "owner_generation",
            "lineage_generation", "lane", "lane_key", "host", "workspace",
            "common_dir", "repository", "parent_read_only", "claimed_at",
        }
        optional = {"coordinator_session_uuid"}
        if (not required.issubset(value) or
                set(value) - required - optional or
                value.get("claim_kind") != "workspace" or
                value.get("state") != "active"):
            raise _error("invalid", "expected native workspace claim is malformed")

        try:
            lane = canonical_lane(value["lane"])
            lane_key = value["lane_key"]
            host = _canonical_component(value["host"], "claim host")
            lineage_id = _opaque_token(value["lineage_id"], "claim lineage_id")
            coordinator_session_uuid = value.get("coordinator_session_uuid")
            if coordinator_session_uuid is not None:
                coordinator_session_uuid = _opaque_token(
                    coordinator_session_uuid,
                    "claim coordinator_session_uuid",
                )
            workspace = self._canonical_record_path(
                value["workspace"], "claim workspace")
            repository = self._canonical_record_path(
                value["repository"], "claim repository")
            common_dir = self._canonical_record_path(
                value["common_dir"], "claim common_dir")
        except (KeyError, TypeError):
            raise _error("invalid", "expected native workspace claim is malformed")

        claimed_at = value.get("claimed_at")
        try:
            claimed_at_finite = math.isfinite(float(claimed_at))
        except (OverflowError, TypeError, ValueError):
            claimed_at_finite = False
        owner_generation = value.get("owner_generation")
        lineage_generation = value.get("lineage_generation")
        if (not isinstance(lane_key, str) or lane_key != lane.casefold() or
                host != self.identity.host or
                lineage_id != value["lineage_id"] or
                (coordinator_session_uuid is not None and
                 coordinator_session_uuid != value["coordinator_session_uuid"]) or
                str(workspace) != value["workspace"] or
                str(repository) != value["repository"] or
                str(common_dir) != value["common_dir"] or
                not isinstance(value.get("parent_read_only"), bool) or
                isinstance(owner_generation, bool) or
                not isinstance(owner_generation, int) or owner_generation <= 0 or
                isinstance(lineage_generation, bool) or
                not isinstance(lineage_generation, int) or lineage_generation <= 0 or
                isinstance(claimed_at, bool) or
                not isinstance(claimed_at, (int, float)) or
                not claimed_at_finite):
            raise _error("invalid", "expected native workspace claim is malformed")

        return value, self._strict_claim_snapshot_bytes(value)

    @staticmethod
    def _claim_transfer_facts(claim: Mapping[str, Any]) -> Dict[str, Any]:
        """Select a bounded source/target projection for the claims journal."""

        fields = (
            "record_kind", "claim_kind", "state", "lineage_id",
            "coordinator_session_uuid", "owner_generation", "lineage_generation",
            "lane", "lane_key", "host", "workspace", "common_dir",
            "repository", "parent_read_only",
        )
        return {field: claim[field] for field in fields if field in claim}

    def transfer_lineage_workspace_claim(
            self, expected_claim: Mapping[str, Any], *,
            target_lineage_id: Any,
            target_coordinator_session_uuid: Any,
            target_lineage_generation: Any,
            expected_daemon_id: Any,
            authoritative: bool = False) -> Dict[str, Any]:
        """CAS one workspace claim to a new lineage incarnation.

        This is an internal state-store prerequisite, not a public lifecycle
        operation and not native ``ctx`` integration.  A trusted controller
        must prove old-writer exclusion and resolved effects before passing
        ``authoritative=True``.  The store does not observe or manufacture
        that proof, update owner/controller records, reconcile native history,
        or provide automatic retry/recovery after an acknowledgement loss.
        """

        if authoritative is not True:
            raise _error(
                "uncertain-effect",
                "native lineage workspace transfer requires authoritative stop/effect proof",
            )
        target_lineage_id = _opaque_token(target_lineage_id, "target lineage_id")
        target_coordinator_session_uuid = _opaque_token(
            target_coordinator_session_uuid,
            "target coordinator_session_uuid",
        )
        if (isinstance(target_lineage_generation, bool) or
                not isinstance(target_lineage_generation, int) or
                target_lineage_generation <= 0):
            raise _error("invalid", "target lineage_generation must be positive")
        expected_daemon_id = _canonical_component(
            expected_daemon_id, "expected daemon_id",
        )
        _expected, expected_bytes = self._validate_workspace_claim_snapshot(
            expected_claim,
        )

        self.ensure_layout()
        with self.locked():
            # ``read_owner`` validates the generation ledger and the complete
            # owner/runtime recovery boundary while this method still holds
            # the outer EXCLUSIVE lock.  A pending recovery cannot safely
            # transfer a claim on behalf of either daemon incarnation.
            owner = self.read_owner()
            if owner.get("mode") != "managed":
                raise _error(
                    "ownership-conflict",
                    "native lineage workspace transfer requires managed ownership",
                )
            recovery_intent = self._load_recovery_intent()
            if (recovery_intent is not None and
                    recovery_intent.get("state") != "complete"):
                raise _error(
                    "uncertain-effect",
                    "managed recovery is pending; native workspace transfer is held",
                )
            current_owner_generation = owner["generation"]
            if owner.get("daemon_id") != expected_daemon_id:
                raise _error(
                    "ownership-conflict",
                    "managed owner daemon incarnation does not match transfer witness",
                )

            claims = self._load_claims()
            source_matches = [
                index for index, claim in enumerate(claims)
                if self._strict_claim_snapshot_bytes(claim) == expected_bytes
            ]
            if len(source_matches) != 1:
                raise _error(
                    "ownership-conflict",
                    "native lineage workspace claim is missing, duplicated, or changed",
                )
            source_index = source_matches[0]
            source = claims[source_index]

            if (source.get("record_kind") != "workspace-claim" or
                    source.get("claim_kind") != "workspace" or
                    source.get("lane_key") != self.identity.lane_key or
                    source.get("host") != self.identity.host or
                    source.get("common_dir") != str(self.identity.common_dir) or
                    source.get("owner_generation") != current_owner_generation):
                raise _error(
                    "ownership-conflict",
                    "native lineage workspace claim is not current owner state",
                )
            source_coordinator_session_uuid = source.get(
                "coordinator_session_uuid",
            )
            if (not isinstance(source_coordinator_session_uuid, str) or
                    not source_coordinator_session_uuid):
                raise _error(
                    "ownership-conflict",
                    "native workspace transfer requires a bound source coordinator identity",
                )

            # There must be one active workspace row for this current source
            # lineage identity.  A changed-path/policy duplicate is as unsafe
            # as an exact duplicate and is deliberately not selected.
            source_workspace_rows = [
                claim for claim in claims
                if claim.get("record_kind") == "workspace-claim" and
                claim.get("lineage_id") == source.get("lineage_id") and
                claim.get("owner_generation") == source.get("owner_generation") and
                claim.get("lane_key") == source.get("lane_key") and
                claim.get("host") == source.get("host") and
                claim.get("common_dir") == source.get("common_dir")
            ]
            if len(source_workspace_rows) != 1:
                raise _error(
                    "ownership-conflict",
                    "native lineage workspace claim has a duplicate incarnation",
                )

            if any(
                    claim.get("record_kind") == "child-worktree-claim" and
                    claim.get("lineage_id") == source.get("lineage_id") and
                    claim.get("owner_generation") == source.get("owner_generation") and
                    claim.get("lane_key") == source.get("lane_key") and
                    claim.get("host") == source.get("host") and
                    claim.get("common_dir") == source.get("common_dir")
                    for claim in claims):
                raise _error(
                    "ownership-conflict",
                    "native isolated child claims must be retained before workspace transfer",
                )

            if target_lineage_id == source.get("lineage_id"):
                raise _error(
                    "ownership-conflict",
                    "native workspace transfer target lineage is not new",
                )
            if target_coordinator_session_uuid == source.get("coordinator_session_uuid"):
                raise _error(
                    "ownership-conflict",
                    "native workspace transfer target coordinator is not new",
                )
            if target_lineage_generation != source["lineage_generation"] + 1:
                raise _error(
                    "stale-generation",
                    "native workspace transfer target lineage generation is not next",
                )

            # Owner/controller records are not part of this single-index CAS.
            # A pinned identity would therefore become false after transfer.
            for field, target in (
                    ("lineage_id", target_lineage_id),
                    ("coordinator_session_uuid", target_coordinator_session_uuid)):
                pinned = owner.get(field)
                if pinned is not None and (
                        pinned != source.get(field) or pinned != target):
                    raise _error(
                        "ownership-conflict",
                        "managed owner pins an identity this transfer cannot update",
                    )

            for index, claim in enumerate(claims):
                if index == source_index:
                    continue
                if (claim.get("lineage_id") == target_lineage_id or
                        claim.get("coordinator_session_uuid") ==
                        target_coordinator_session_uuid):
                    raise _error(
                        "ownership-conflict",
                        "native workspace transfer target identity is already present",
                    )
                if self._paths_overlap(
                        self._native_claim_path(source),
                        self._native_claim_path(claim)):
                    raise _error(
                        "ownership-conflict",
                        "native workspace transfer overlaps an active claim",
                    )

            target = dict(source)
            target["lineage_id"] = target_lineage_id
            target["coordinator_session_uuid"] = target_coordinator_session_uuid
            target["lineage_generation"] = target_lineage_generation
            source_facts = self._claim_transfer_facts(source)
            target_facts = self._claim_transfer_facts(target)

            self.append_journal("claims", {
                "event": "native-lineage-claim-transfer-intent",
                "authoritative": True,
                "expected_daemon_id": expected_daemon_id,
                "source": source_facts,
                "target": target_facts,
            })
            # This is the sole ownership-authority write.  It remains inside
            # the EXCLUSIVE lock, so the source is never released into a gap.
            replacement = list(claims)
            replacement[source_index] = target
            self._write_claims(replacement)
            self.append_journal("claims", {
                "event": "native-lineage-claim-transfer-result",
                "status": "complete",
                "expected_daemon_id": expected_daemon_id,
                "source": source_facts,
                "target": target_facts,
            })
            return dict(target)

    def assess_lineage_workspace_adoption(
            self, expected_source_claim: Mapping[str, Any],
            expected_target_claim: Mapping[str, Any], *,
            expected_daemon_id: Any) -> Dict[str, Any]:
        """Assess one possible lineage-claim adoption without mutation.

        This is deliberately only an observation.  It does not authorize a
        transfer, infer quiescence, or provision a cold state store.  The
        claim index remains the authority; a journal entry, missing row, or
        matching identity alone cannot turn an indeterminate observation into
        a positive result.
        """

        expected_daemon_id = _canonical_component(
            expected_daemon_id, "expected daemon_id",
        )
        source, source_bytes = self._validate_workspace_claim_snapshot(
            expected_source_claim,
        )
        target, target_bytes = self._validate_workspace_claim_snapshot(
            expected_target_claim,
        )
        identity_fields = {
            "lineage_id", "coordinator_session_uuid", "lineage_generation",
        }
        source_session = source.get("coordinator_session_uuid")
        target_session = target.get("coordinator_session_uuid")
        if (not isinstance(source_session, str) or not source_session or
                not isinstance(target_session, str) or not target_session):
            raise _error(
                "ownership-conflict",
                "lineage adoption requires bound source and target coordinators",
            )
        if source.get("lineage_id") == target.get("lineage_id"):
            raise _error(
                "ownership-conflict",
                "lineage adoption target lineage is not new",
            )
        if source_session == target_session:
            raise _error(
                "ownership-conflict",
                "lineage adoption target coordinator is not new",
            )
        if target.get("lineage_generation") != source.get("lineage_generation", 0) + 1:
            raise _error(
                "stale-generation",
                "lineage adoption target generation is not next",
            )
        if set(source) != set(target):
            raise _error(
                "invalid",
                "lineage adoption source and target claim fields differ",
            )
        source_immutable = {
            key: value for key, value in source.items()
            if key not in identity_fields
        }
        target_immutable = {
            key: value for key, value in target.items()
            if key not in identity_fields
        }
        if (self._strict_claim_snapshot_bytes(source_immutable) !=
                self._strict_claim_snapshot_bytes(target_immutable)):
            raise _error(
                "invalid",
                "lineage adoption target changes immutable claim fields",
            )
        if (source.get("lane_key") != self.identity.lane_key or
                source.get("host") != self.identity.host or
                source.get("common_dir") != str(self.identity.common_dir)):
            raise _error(
                "ownership-conflict",
                "lineage adoption claim is outside this managed state scope",
            )

        # ``locked`` creates the private layout as part of its normal entry
        # path.  Validate and load the existing owner first so an assessment
        # on a cold or owner-missing store cannot create an empty owner.
        self.validate_layout()
        owner_path = self.identity.state_root / _OWNER_NAME
        if not owner_path.exists():
            raise _error(
                "ownership-conflict",
                "lineage adoption requires an existing managed owner record",
            )
        owner_before = self._load_owner()
        if owner_before.get("mode") != "managed":
            raise _error(
                "ownership-conflict",
                "lineage adoption requires managed ownership",
            )

        with self._locked_existing(shared=True):
            # Revalidate the layout and owner after taking the shared lock.
            # The non-provisioning lock is intentional: no assessment may
            # recreate state that disappeared after the pre-lock snapshot.
            self.validate_layout()
            if not owner_path.exists():
                raise _error(
                    "ownership-conflict",
                    "managed owner record disappeared before adoption assessment",
                )
            owner = self._read_owner_locked()
            if owner.get("mode") != "managed":
                raise _error(
                    "ownership-conflict",
                    "lineage adoption requires managed ownership",
                )
            if owner.get("daemon_id") != expected_daemon_id:
                raise _error(
                    "ownership-conflict",
                    "managed owner daemon incarnation does not match assessment witness",
                )
            if owner.get("generation") != source.get("owner_generation"):
                raise _error(
                    "stale-generation",
                    "managed owner generation does not match assessment claims",
                )
            recovery_intent = self._load_recovery_intent()
            if (recovery_intent is not None and
                    recovery_intent.get("state") != "complete"):
                raise _error(
                    "uncertain-effect",
                    "managed recovery is pending; lineage adoption assessment is held",
                )

            claims = self._load_claims()
            source_matches = [
                claim for claim in claims
                if self._strict_claim_snapshot_bytes(claim) == source_bytes
            ]
            target_matches = [
                claim for claim in claims
                if self._strict_claim_snapshot_bytes(claim) == target_bytes
            ]
            blockers: set[str] = set()

            # The single-index observation cannot update owner-pinned lineage
            # identities atomically.  Even a pin matching the source is not a
            # positive adoption result; it is an incompatible cross-record
            # boundary, consistent with the CAS prerequisite.
            if (owner.get("lineage_id") is not None or
                    owner.get("coordinator_session_uuid") is not None):
                blockers.add("owner-pinned-identity")

            def _workspace_identity_matches(
                    claim: Mapping[str, Any], expected: Mapping[str, Any]) -> bool:
                return (
                    claim.get("record_kind") == "workspace-claim" and
                    (claim.get("lineage_id") == expected.get("lineage_id") or
                     claim.get("coordinator_session_uuid") ==
                     expected.get("coordinator_session_uuid"))
                )

            source_identity_rows = [
                claim for claim in claims
                if _workspace_identity_matches(claim, source)
            ]
            target_identity_rows = [
                claim for claim in claims
                if _workspace_identity_matches(claim, target)
            ]
            if len(source_matches) > 1:
                blockers.add("source-duplicate")
            if len(target_matches) > 1:
                blockers.add("target-duplicate")
            if source_identity_rows and not all(
                    self._strict_claim_snapshot_bytes(claim) == source_bytes
                    for claim in source_identity_rows):
                blockers.add("source-changed")
            if target_identity_rows and not all(
                    self._strict_claim_snapshot_bytes(claim) == target_bytes
                    for claim in target_identity_rows):
                blockers.add("target-changed")

            source_children = [
                claim for claim in claims
                if (claim.get("record_kind") == "child-worktree-claim" and
                    claim.get("lineage_id") == source.get("lineage_id"))
            ]
            if source_children:
                blockers.add("source-child-claim-retained")

            # A target identity is unsafe if any additional active row reuses
            # either target identity field, even on a disjoint path.  The
            # exact target row itself is the sole allowed occurrence.
            for claim in claims:
                exact_target = (
                    self._strict_claim_snapshot_bytes(claim) == target_bytes
                )
                exact_source = (
                    self._strict_claim_snapshot_bytes(claim) == source_bytes
                )
                if (claim.get("lineage_id") == target.get("lineage_id") or
                        claim.get("coordinator_session_uuid") == target_session):
                    if not exact_target:
                        blockers.add("target-identity-collision")
                if (claim.get("lineage_id") == source.get("lineage_id") or
                        claim.get("coordinator_session_uuid") == source_session):
                    if not exact_source:
                        blockers.add("source-identity-collision")

            if source_matches and target_matches:
                blockers.add("source-and-target-present")
            elif not source_matches and not target_matches:
                blockers.add("source-and-target-absent")

            expected_path = self._native_claim_path(source)
            for claim in claims:
                if (self._strict_claim_snapshot_bytes(claim) == source_bytes or
                        self._strict_claim_snapshot_bytes(claim) == target_bytes):
                    continue
                if (claim.get("record_kind") == "child-worktree-claim" and
                        claim.get("lineage_id") == source.get("lineage_id")):
                    continue
                if self._paths_overlap(expected_path, self._native_claim_path(claim)):
                    blockers.add("path-overlap")

            if blockers:
                status = "indeterminate"
            elif len(source_matches) == 1 and not target_matches:
                status = "source-held"
            elif len(target_matches) == 1 and not source_matches:
                status = "target-held"
            else:
                status = "indeterminate"
                blockers.add("claim-state-unresolved")

            return {
                "status": status,
                "blockers": sorted(blockers),
                "source_matches": len(source_matches),
                "target_matches": len(target_matches),
            }

    # ---- bounded native adoption transaction -------------------------

    @staticmethod
    def _native_adoption_digest_value(value: Any, label: str) -> str:
        if (not isinstance(value, str) or
                not _NATIVE_ADOPTION_DIGEST_RE.fullmatch(value)):
            raise _error("invalid", "%s must be a lowercase SHA-256 digest" % label)
        return value

    @staticmethod
    def _native_adoption_intent_digest(intent: Mapping[str, Any]) -> str:
        """Digest immutable intent content, excluding mutable terminal fields."""

        if not isinstance(intent, Mapping):
            raise _error("invalid", "native adoption intent is not an object")
        immutable = {
            key: value for key, value in intent.items()
            if key not in {"intent_digest", "phase", "controller_commit_digest"}
        }
        return _native_digest(immutable)

    @staticmethod
    def _native_adoption_source_identity(value: Any) -> Dict[str, Any]:
        if not isinstance(value, Mapping) or set(value) != _NATIVE_SOURCE_IDENTITY_FIELDS:
            raise _error("invalid", "native adoption source identity is malformed")
        result = dict(value)
        owner_generation = result["owner_generation"]
        lineage_generation = result["lineage_generation"]
        if (isinstance(owner_generation, bool) or
                not isinstance(owner_generation, int) or owner_generation <= 0 or
                isinstance(lineage_generation, bool) or
                not isinstance(lineage_generation, int) or lineage_generation <= 0):
            raise _error("invalid", "native adoption source identity generation is malformed")
        for field in (
                "lineage_id", "session_uuid", "runner_incarnation", "invocation_id"):
            _opaque_token(result[field], "native adoption source " + field)
        return result

    def _native_adoption_claim_pair(
            self, source_value: Any, target_value: Any,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        source, _source_bytes = self._validate_workspace_claim_snapshot(source_value)
        target, _target_bytes = self._validate_workspace_claim_snapshot(target_value)
        if (source.get("lane_key") != self.identity.lane_key or
                target.get("lane_key") != self.identity.lane_key or
                source.get("host") != self.identity.host or
                target.get("host") != self.identity.host or
                source.get("common_dir") != str(self.identity.common_dir) or
                target.get("common_dir") != str(self.identity.common_dir)):
            raise _error("ownership-conflict", "native adoption claim is outside this state scope")
        source_session = source.get("coordinator_session_uuid")
        target_session = target.get("coordinator_session_uuid")
        if (not isinstance(source_session, str) or not source_session or
                not isinstance(target_session, str) or not target_session):
            raise _error(
                "ownership-conflict",
                "native adoption requires bound source and target coordinators",
            )
        if source.get("owner_generation") != target.get("owner_generation"):
            raise _error("stale-generation", "native adoption claim owner generations differ")
        if source.get("lineage_id") == target.get("lineage_id"):
            raise _error("ownership-conflict", "native adoption target lineage is not new")
        if source_session == target_session:
            raise _error("ownership-conflict", "native adoption target coordinator is not new")
        if target.get("lineage_generation") != source.get("lineage_generation", 0) + 1:
            raise _error("stale-generation", "native adoption target generation is not next")
        if set(source) != set(target):
            raise _error("invalid", "native adoption claim fields differ")
        identity_fields = {
            "lineage_id", "coordinator_session_uuid", "lineage_generation",
        }
        source_immutable = {
            key: value for key, value in source.items()
            if key not in identity_fields
        }
        target_immutable = {
            key: value for key, value in target.items()
            if key not in identity_fields
        }
        if (self._strict_claim_snapshot_bytes(source_immutable) !=
                self._strict_claim_snapshot_bytes(target_immutable)):
            raise _error("invalid", "native adoption target changes immutable claim fields")
        return source, target

    def _validate_native_adoption_entry(
            self, value: Any, *, expected_adoption_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not isinstance(value, Mapping):
            raise _error("invalid", "native adoption intent is not an object")
        entry = dict(value)
        validate_native_lineage_record(
            entry, record_kind="native-adoption-intent",
            label="native adoption intent",
        )
        if set(entry) != _NATIVE_ADOPTION_ENTRY_FIELDS:
            raise _error("invalid", "native adoption intent fields are malformed")
        adoption_id = _opaque_token(entry["adoption_id"], "native adoption ID")
        if expected_adoption_id is not None and adoption_id != expected_adoption_id:
            raise _error("invalid", "native adoption ledger key does not match adoption ID")
        archive_id = _opaque_token(entry["archive_id"], "native adoption archive ID")
        operation_id = _opaque_token(entry["operation_id"], "native adoption operation ID")
        expected_daemon_id = _canonical_component(
            entry["expected_daemon_id"], "native adoption expected daemon_id",
        )
        owner_generation = entry["owner_generation"]
        if (isinstance(owner_generation, bool) or
                not isinstance(owner_generation, int) or owner_generation <= 0):
            raise _error("invalid", "native adoption owner generation is malformed")
        source_identity = self._native_adoption_source_identity(entry["source_identity"])
        source, target = self._native_adoption_claim_pair(
            entry["source_claim"], entry["target_claim"],
        )
        if (source["owner_generation"] != owner_generation or
                target["owner_generation"] != owner_generation or
                source["lineage_id"] != source_identity["lineage_id"] or
                source["lineage_generation"] != source_identity["lineage_generation"] or
                source.get("coordinator_session_uuid") != source_identity["session_uuid"] or
                source_identity["owner_generation"] != owner_generation):
            raise _error("stale-generation", "native adoption source identity is not bound to source claim")
        for field, label in (
                ("archive_digest", "native adoption archive digest"),
                ("source_claim_digest", "native adoption source claim digest"),
                ("target_claim_digest", "native adoption target claim digest"),
                ("evidence_digest", "native adoption evidence digest"),
                ("runtime_identity_digest", "native adoption runtime identity digest")):
            self._native_adoption_digest_value(entry[field], label)
        if self._native_adoption_digest_value(
                entry["source_claim_digest"], "native adoption source claim digest") != _native_digest(source):
            raise _error("invalid", "native adoption source claim digest changed")
        if self._native_adoption_digest_value(
                entry["target_claim_digest"], "native adoption target claim digest") != _native_digest(target):
            raise _error("invalid", "native adoption target claim digest changed")
        _opaque_token(entry["evidence_reference"], "native adoption evidence reference")
        phase = entry["phase"]
        if phase not in _NATIVE_ADOPTION_PHASES:
            raise _error("invalid", "native adoption phase is unknown")
        controller_digest = entry["controller_commit_digest"]
        if controller_digest is not None:
            self._native_adoption_digest_value(
                controller_digest, "native adoption controller commit digest",
            )
        if phase == "controller-committed" and controller_digest is None:
            raise _error("invalid", "completed native adoption lacks controller digest")
        if phase != "controller-committed" and controller_digest is not None:
            raise _error("invalid", "native adoption controller digest is premature")
        intent_digest = self._native_adoption_digest_value(
            entry["intent_digest"], "native adoption intent digest",
        )
        if intent_digest != self._native_adoption_intent_digest(entry):
            raise _error("invalid", "native adoption intent digest changed")
        # Keep local variables as explicit strict checks; return a recursively
        # copied JSON-shaped record so callers cannot mutate durable state.
        del adoption_id, archive_id, operation_id, expected_daemon_id, source_identity
        return _native_json_value(entry)

    def _native_adoption_candidate(self, value: Any) -> Dict[str, Any]:
        if not isinstance(value, Mapping):
            raise _error("invalid", "native adoption intent is not an object")
        allowed = set(_NATIVE_ADOPTION_IMMUTABLE_FIELDS) | {
            "schema_version", "architecture", "record_kind", "intent_digest",
            "phase", "controller_commit_digest",
        }
        if set(value) - allowed:
            raise _error("invalid", "native adoption intent contains unknown fields")
        marker = native_record_marker("native-adoption-intent")
        for key, expected in marker.items():
            if key in value and value[key] != expected:
                raise _error("schema-mismatch", "native adoption intent marker is incompatible")
        missing = set(_NATIVE_ADOPTION_IMMUTABLE_FIELDS) - set(value)
        if missing:
            raise _error(
                "invalid",
                "native adoption intent is missing: %s" % ", ".join(sorted(missing)),
            )
        candidate = {
            **marker,
            **{key: _native_json_value(value[key])
               for key in _NATIVE_ADOPTION_IMMUTABLE_FIELDS},
            "phase": value.get("phase", "prepared"),
            "controller_commit_digest": value.get("controller_commit_digest"),
        }
        if candidate["phase"] != "prepared":
            raise _error("invalid", "new native adoption intent must be prepared")
        if candidate["controller_commit_digest"] is not None:
            raise _error("invalid", "new native adoption intent has a controller digest")
        candidate["intent_digest"] = self._native_adoption_intent_digest(candidate)
        supplied_digest = value.get("intent_digest")
        if supplied_digest is not None:
            self._native_adoption_digest_value(
                supplied_digest, "native adoption intent digest",
            )
            if supplied_digest != candidate["intent_digest"]:
                raise _error("invalid", "native adoption intent digest does not match content")
        return self._validate_native_adoption_entry(candidate)

    def _native_adoption_path(self) -> Path:
        return self._json_path(_ADOPTIONS_NAME)

    def _validate_native_adoption_ledger_payload(
            self, value: Any,
    ) -> Dict[str, Dict[str, Any]]:
        """Validate a complete native-adoption ledger without publishing it."""

        validate_native_lineage_record(
            value, record_kind="native-adoption-ledger",
            label="native adoption ledger",
        )
        if set(value) != {
                "schema_version", "architecture", "record_kind", "intents"}:
            raise _error("invalid", "native adoption ledger fields are malformed")
        intents = value["intents"]
        if not isinstance(intents, Mapping) or len(intents) > 16:
            raise _error("invalid", "native adoption ledger capacity is malformed")
        result: Dict[str, Dict[str, Any]] = {}
        for adoption_id, entry in intents.items():
            if not isinstance(adoption_id, str) or not adoption_id:
                raise _error("invalid", "native adoption ledger key is malformed")
            result[adoption_id] = self._validate_native_adoption_entry(
                entry, expected_adoption_id=adoption_id,
            )
        return result

    def _load_native_adoption_ledger(self) -> Dict[str, Dict[str, Any]]:
        raw = self._read_path(self._native_adoption_path())
        if raw is None:
            return {}
        return self._validate_native_adoption_ledger_payload(raw)

    def _write_native_adoption_ledger(
            self, intents: Mapping[str, Mapping[str, Any]],
    ) -> None:
        if not isinstance(intents, Mapping) or len(intents) > 16:
            raise _error("busy", "native adoption ledger capacity is exhausted")
        checked: Dict[str, Dict[str, Any]] = {}
        for adoption_id, value in intents.items():
            if not isinstance(adoption_id, str) or not adoption_id:
                raise _error("invalid", "native adoption ledger key is malformed")
            checked[adoption_id] = self._validate_native_adoption_entry(
                value, expected_adoption_id=adoption_id,
            )
        payload = {
            **native_record_marker("native-adoption-ledger"),
            "intents": checked,
        }
        encoded = json.dumps(
            payload, ensure_ascii=True, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8") + b"\n"
        self._atomic_write(self._native_adoption_path(), encoded)

    @contextlib.contextmanager
    def _native_adoption_locked(self) -> Iterator["ManagedStateStore"]:
        """Use the existing global lock without provisioning a cold store."""

        self.validate_layout()
        if (not self.identity.global_root.is_dir() or
                not self.identity.state_root.is_dir() or
                not (self.identity.state_root / _OWNER_NAME).exists()):
            raise _error(
                "ownership-conflict",
                "native adoption requires an existing managed state layout",
            )
        with self._locked_existing():
            self.validate_layout()
            if not (self.identity.state_root / _OWNER_NAME).exists():
                raise _error(
                    "ownership-conflict",
                    "managed owner disappeared before native adoption lock",
                )
            yield self

    def _native_adoption_owner(
            self, entry: Mapping[str, Any], expected_daemon_id: str,
    ) -> Dict[str, Any]:
        if entry.get("expected_daemon_id") != expected_daemon_id:
            raise _error("ownership-conflict", "native adoption daemon binding changed")
        owner = self._read_owner_locked()
        if owner.get("mode") != "managed":
            raise _error("ownership-conflict", "native adoption requires managed ownership")
        if owner.get("daemon_id") != expected_daemon_id:
            raise _error(
                "ownership-conflict",
                "managed owner daemon incarnation does not match native adoption",
            )
        if owner.get("generation") != entry.get("owner_generation"):
            raise _error(
                "stale-generation",
                "managed owner generation does not match native adoption",
            )
        recovery_intent = self._load_recovery_intent()
        if (recovery_intent is not None and
                recovery_intent.get("state") != "complete"):
            raise _error(
                "uncertain-effect",
                "managed recovery is pending; native adoption is held",
            )
        return owner

    def _native_adoption_controller_record(self) -> Dict[str, Any]:
        raw = self._read_path(self._json_path("controller.json"))
        if raw is None:
            raise _error("unknown", "native adoption controller record is absent")
        validate_native_lineage_record(
            raw, record_kind="controller", label="managed controller record",
        )
        if not isinstance(raw, dict):
            raise _error("invalid", "native adoption controller record is malformed")
        return raw

    def _native_adoption_controller_binding(
            self, entry: Mapping[str, Any], *, controller_phase: Any,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        raw = self._native_adoption_controller_record()
        if raw.get("generation") != entry["owner_generation"]:
            raise _error("stale-generation", "native adoption controller generation changed")
        if raw.get("active_operation_id") != entry["operation_id"]:
            raise _error("stale-generation", "native adoption active operation changed")
        operations = raw.get("operations")
        if not isinstance(operations, list):
            raise _error("invalid", "native adoption controller operations are malformed")
        matches = [
            operation for operation in operations
            if isinstance(operation, Mapping) and
            operation.get("operation_id") == entry["operation_id"]
        ]
        if len(matches) != 1:
            raise _error("stale-generation", "native adoption operation linkage is not unique")
        operation = dict(matches[0])
        if (operation.get("generation") != entry["owner_generation"] or
                operation.get("phase") not in {"paused", "indeterminate"}):
            raise _error(
                "stale-generation",
                "native adoption operation is not paused or indeterminate",
            )
        metadata = operation.get("metadata")
        if not isinstance(metadata, Mapping) or "native_adoption" not in metadata:
            raise _error("invalid", "native adoption controller reference is absent")
        reference = metadata["native_adoption"]
        if (not isinstance(reference, Mapping) or
                set(reference) != _NATIVE_ADOPTION_CONTROLLER_FIELDS):
            raise _error("invalid", "native adoption controller reference is malformed")
        reference = dict(reference)
        if reference["adoption_id"] != entry["adoption_id"]:
            raise _error("ownership-conflict", "native adoption controller ID changed")
        if reference["intent_digest"] != entry["intent_digest"]:
            raise _error("invalid", "native adoption controller intent digest changed")
        if reference["archive_id"] != entry["archive_id"]:
            raise _error("invalid", "native adoption controller archive ID changed")
        if reference["archive_digest"] != entry["archive_digest"]:
            raise _error("invalid", "native adoption controller archive digest changed")
        if reference["target_claim_digest"] != entry["target_claim_digest"]:
            raise _error("invalid", "native adoption controller target digest changed")
        allowed_controller_phases = (
            {controller_phase} if isinstance(controller_phase, str)
            else set(controller_phase)
        )
        if reference["phase"] not in allowed_controller_phases:
            raise _error("uncertain-effect", "native adoption controller phase is not current")
        self._native_adoption_digest_value(
            reference["intent_digest"], "native adoption controller intent digest",
        )
        self._native_adoption_digest_value(
            reference["archive_digest"], "native adoption controller archive digest",
        )
        self._native_adoption_digest_value(
            reference["target_claim_digest"], "native adoption controller target digest",
        )
        archives = raw.get("native_source_archives")
        if not isinstance(archives, Mapping):
            raise _error("unknown", "native adoption source archive collection is absent")
        archive = archives.get(entry["archive_id"])
        if not isinstance(archive, Mapping):
            raise _error("unknown", "native adoption source archive is absent")
        archive = dict(archive)
        validate_native_lineage_record(
            archive, record_kind="native-source-archive",
            label="native adoption source archive",
        )
        if set(archive) != {
                "schema_version", "architecture", "record_kind", "archive_id",
                "operation_id", "source_identity", "snapshot_digest", "snapshot"}:
            raise _error("invalid", "native adoption source archive is malformed")
        if (archive["archive_id"] != entry["archive_id"] or
                archive["operation_id"] != entry["operation_id"]):
            raise _error("stale-generation", "native adoption source archive linkage changed")
        snapshot = archive["snapshot"]
        if (not isinstance(snapshot, Mapping) or
                "native_source_archives" in snapshot):
            raise _error("invalid", "native adoption source archive snapshot is malformed")
        archive_digest = self._native_adoption_digest_value(
            archive["snapshot_digest"], "native adoption source archive digest",
        )
        if archive_digest != _native_digest(snapshot) or archive_digest != entry["archive_digest"]:
            raise _error("invalid", "native adoption source archive digest changed")
        archive_identity = self._native_adoption_source_identity(archive["source_identity"])
        if archive_identity != entry["source_identity"]:
            raise _error("ownership-conflict", "native adoption source identity changed")
        source_claim = entry["source_claim"]
        if (
                source_claim.get("owner_generation") != archive_identity["owner_generation"] or
                source_claim.get("lineage_id") != archive_identity["lineage_id"] or
                source_claim.get("lineage_generation") != archive_identity["lineage_generation"] or
                source_claim.get("coordinator_session_uuid") != archive_identity["session_uuid"] or
                source_claim.get("common_dir") != str(self.identity.common_dir) or
                source_claim.get("host") != self.identity.host or
                source_claim.get("lane_key") != self.identity.lane_key):
            raise _error(
                "ownership-conflict",
                "native adoption source claim is not bound to archived source identity",
            )
        snapshot_context = snapshot.get("native_context")
        snapshot_lineage = (
            snapshot_context.get("lineage")
            if isinstance(snapshot_context, Mapping) else None
        )
        archived_claim = (
            snapshot_lineage.get("workspace_claim")
            if isinstance(snapshot_lineage, Mapping) else None
        )
        if not isinstance(archived_claim, Mapping):
            raise _error(
                "invalid",
                "native adoption archived workspace claim is absent",
            )
        for field in ("workspace", "common_dir", "repository"):
            if archived_claim.get(field) != source_claim.get(field):
                raise _error(
                    "ownership-conflict",
                    "native adoption source claim is outside the archived workspace",
                )
        return raw, operation, archive

    def _native_adoption_observe_target_held(
            self, entry: Mapping[str, Any], expected_daemon_id: str,
    ) -> Dict[str, Any]:
        """Revalidate every durable fact before returning a prior success."""

        if entry["phase"] == "controller-committed":
            controller_phase: Any = "controller-committed"
        elif entry["phase"] == "claim-transferred":
            # The controller acknowledgement may have landed immediately
            # before a state finalization retry.  That window is observable,
            # but it is not permission to claim final state here.
            controller_phase = ("prepared", "controller-committed")
        else:
            controller_phase = "prepared"
        controller_record, _operation, _archive = (
            self._native_adoption_controller_binding(
                entry, controller_phase=controller_phase,
            )
        )
        if entry["phase"] == "controller-committed":
            commit_digest = entry["controller_commit_digest"]
            if _native_digest(controller_record) != commit_digest:
                raise _error(
                    "invalid",
                    "native adoption controller acknowledgement changed",
                )
        assessment = self.assess_lineage_workspace_adoption(
            entry["source_claim"], entry["target_claim"],
            expected_daemon_id=expected_daemon_id,
        )
        if assessment["status"] != "target-held":
            raise _error(
                "uncertain-effect",
                "native adoption durable target is no longer held exactly",
            )
        return _native_json_value(entry)

    def prepare_lineage_adoption(self, intent: Mapping[str, Any]) -> Dict[str, Any]:
        """Durably prepare one state-side adoption descriptor, without CAS."""

        candidate = self._native_adoption_candidate(intent)
        expected_daemon_id = _canonical_component(
            candidate["expected_daemon_id"], "native adoption expected daemon_id",
        )
        with self._native_adoption_locked():
            ledger = self._load_native_adoption_ledger()
            existing = ledger.get(candidate["adoption_id"])
            if existing is not None:
                if (self._native_adoption_intent_digest(existing) !=
                        self._native_adoption_intent_digest(candidate)):
                    raise _error("invalid", "native adoption ID was reused with different content")
                self._native_adoption_owner(existing, expected_daemon_id)
                if existing["phase"] == "controller-committed":
                    return self._native_adoption_observe_target_held(
                        existing, expected_daemon_id,
                    )
                self._native_adoption_controller_binding(
                    existing,
                    controller_phase=(
                        ("prepared", "controller-committed")
                        if existing["phase"] == "claim-transferred" else "prepared"
                    ),
                )
                if existing["phase"] == "claim-transferred":
                    return self._native_adoption_observe_target_held(
                        existing, expected_daemon_id,
                    )
                return _native_json_value(existing)
            self._native_adoption_owner(candidate, expected_daemon_id)
            self._native_adoption_controller_binding(
                candidate, controller_phase="prepared",
            )
            assessment = self.assess_lineage_workspace_adoption(
                candidate["source_claim"], candidate["target_claim"],
                expected_daemon_id=expected_daemon_id,
            )
            if assessment["status"] != "source-held":
                raise _error(
                    "uncertain-effect",
                    "native adoption source claim is not held exactly",
                )
            for other in ledger.values():
                same_operation = other["operation_id"] == candidate["operation_id"]
                same_source = (
                    other["source_identity"] == candidate["source_identity"] and
                    other["source_claim_digest"] == candidate["source_claim_digest"]
                )
                if same_operation or same_source:
                    raise _error(
                        "ownership-conflict",
                        "native adoption conflicts with an existing operation or source",
                    )
            if len(ledger) >= 16:
                raise _error("busy", "native adoption ledger capacity is exhausted")
            ledger[candidate["adoption_id"]] = candidate
            self._write_native_adoption_ledger(ledger)
            return _native_json_value(candidate)

    def apply_lineage_adoption(
            self, adoption_id: Any, *, expected_daemon_id: Any,
            authoritative: bool = False,
    ) -> Dict[str, Any]:
        """Apply one prepared intent through the existing exact claim CAS."""

        adoption_id = _opaque_token(adoption_id, "native adoption ID")
        expected_daemon_id = _canonical_component(
            expected_daemon_id, "native adoption expected daemon_id",
        )
        if authoritative is not True:
            raise _error(
                "uncertain-effect",
                "native adoption requires an authoritative internal caller witness",
            )
        with self._native_adoption_locked():
            ledger = self._load_native_adoption_ledger()
            entry = ledger.get(adoption_id)
            if entry is None:
                raise _error("unknown", "native adoption ID is unknown")
            self._native_adoption_owner(entry, expected_daemon_id)
            if entry["expected_daemon_id"] != expected_daemon_id:
                raise _error("ownership-conflict", "native adoption daemon binding changed")
            if entry["phase"] in {"claim-transferred", "controller-committed"}:
                return self._native_adoption_observe_target_held(
                    entry, expected_daemon_id,
                )
            if entry["phase"] != "prepared":
                raise _error(
                    "uncertain-effect",
                    "native adoption is not a fresh prepared CAS authorization",
                )
            self._native_adoption_controller_binding(
                entry,
                controller_phase=(
                    ("prepared", "controller-committed")
                    if entry["phase"] == "claim-transferred" else "prepared"
                ),
            )
            assessment = self.assess_lineage_workspace_adoption(
                entry["source_claim"], entry["target_claim"],
                expected_daemon_id=expected_daemon_id,
            )
            if assessment["status"] != "source-held":
                raise _error(
                    "uncertain-effect",
                    "native adoption source claim is not held exactly before CAS",
                )
            pending = dict(entry)
            pending["phase"] = "claim-cas-pending"
            ledger[adoption_id] = pending
            # This replacement is durable before the existing one-row claim
            # CAS.  If the following call is ambiguous, recovery can never
            # mistake a source-held view for permission to retry the CAS.
            self._write_native_adoption_ledger(ledger)
            self.transfer_lineage_workspace_claim(
                entry["source_claim"],
                target_lineage_id=entry["target_claim"]["lineage_id"],
                target_coordinator_session_uuid=(
                    entry["target_claim"]["coordinator_session_uuid"]
                ),
                target_lineage_generation=entry["target_claim"]["lineage_generation"],
                expected_daemon_id=expected_daemon_id,
                authoritative=True,
            )
            assessment = self.assess_lineage_workspace_adoption(
                entry["source_claim"], entry["target_claim"],
                expected_daemon_id=expected_daemon_id,
            )
            if assessment["status"] != "target-held":
                indeterminate = dict(pending)
                indeterminate["phase"] = "indeterminate"
                self._write_native_adoption_ledger({
                    **ledger, adoption_id: indeterminate,
                })
                raise _error(
                    "uncertain-effect",
                    "native adoption claim CAS did not produce an exact target claim",
                )
            transferred = dict(pending)
            transferred["phase"] = "claim-transferred"
            ledger[adoption_id] = transferred
            self._write_native_adoption_ledger(ledger)
            return _native_json_value(transferred)

    def reconcile_lineage_adoption(
            self, adoption_id: Any, *, expected_daemon_id: Any,
    ) -> Dict[str, Any]:
        """Reconcile bookkeeping only; this method never issues claim CAS."""

        adoption_id = _opaque_token(adoption_id, "native adoption ID")
        expected_daemon_id = _canonical_component(
            expected_daemon_id, "native adoption expected daemon_id",
        )
        with self._native_adoption_locked():
            ledger = self._load_native_adoption_ledger()
            entry = ledger.get(adoption_id)
            if entry is None:
                raise _error("unknown", "native adoption ID is unknown")
            self._native_adoption_owner(entry, expected_daemon_id)
            if entry["expected_daemon_id"] != expected_daemon_id:
                raise _error("ownership-conflict", "native adoption daemon binding changed")
            if entry["phase"] == "controller-committed":
                return self._native_adoption_observe_target_held(
                    entry, expected_daemon_id,
                )
            self._native_adoption_controller_binding(
                entry,
                controller_phase=(
                    ("prepared", "controller-committed")
                    if entry["phase"] == "claim-transferred" else "prepared"
                ),
            )
            assessment = self.assess_lineage_workspace_adoption(
                entry["source_claim"], entry["target_claim"],
                expected_daemon_id=expected_daemon_id,
            )
            status = assessment["status"]
            phase = entry["phase"]
            if phase == "prepared" and status == "source-held":
                return _native_json_value(entry)
            if phase == "claim-transferred" and status == "target-held":
                return _native_json_value(entry)
            if phase == "claim-cas-pending" and status == "target-held":
                updated = dict(entry)
                updated["phase"] = "claim-transferred"
            elif phase in {"prepared", "claim-cas-pending", "claim-transferred"}:
                # Source-held after pending is deliberately indeterminate; a
                # prepared intent with an unexpected target is not transfer
                # proof.  No branch below can call the CAS primitive.
                updated = dict(entry)
                updated["phase"] = "indeterminate"
            else:
                return _native_json_value(entry)
            ledger[adoption_id] = updated
            self._write_native_adoption_ledger(ledger)
            return _native_json_value(updated)

    def finalize_lineage_adoption(
            self, adoption_id: Any, *, expected_daemon_id: Any,
            controller_digest: Any,
    ) -> Dict[str, Any]:
        """Record a separately committed controller acknowledgement."""

        adoption_id = _opaque_token(adoption_id, "native adoption ID")
        expected_daemon_id = _canonical_component(
            expected_daemon_id, "native adoption expected daemon_id",
        )
        controller_digest = self._native_adoption_digest_value(
            controller_digest, "native adoption controller commit digest",
        )
        with self._native_adoption_locked():
            ledger = self._load_native_adoption_ledger()
            entry = ledger.get(adoption_id)
            if entry is None:
                raise _error("unknown", "native adoption ID is unknown")
            self._native_adoption_owner(entry, expected_daemon_id)
            if entry["expected_daemon_id"] != expected_daemon_id:
                raise _error("ownership-conflict", "native adoption daemon binding changed")
            controller_record, _operation, _archive = (
                self._native_adoption_controller_binding(
                    entry, controller_phase="controller-committed",
                )
            )
            actual_digest = _native_digest(controller_record)
            if actual_digest != controller_digest:
                raise _error("invalid", "native adoption controller digest does not match record")
            assessment = self.assess_lineage_workspace_adoption(
                entry["source_claim"], entry["target_claim"],
                expected_daemon_id=expected_daemon_id,
            )
            if assessment["status"] != "target-held":
                raise _error(
                    "uncertain-effect",
                    "native adoption target claim is not held exactly at finalization",
                )
            if entry["phase"] == "controller-committed":
                if entry["controller_commit_digest"] != controller_digest:
                    raise _error("invalid", "native adoption controller digest changed")
                return _native_json_value(entry)
            if entry["phase"] != "claim-transferred":
                raise _error(
                    "uncertain-effect",
                    "native adoption is not claim-transferred at finalization",
                )
            completed = dict(entry)
            completed["phase"] = "controller-committed"
            completed["controller_commit_digest"] = controller_digest
            ledger[adoption_id] = completed
            self._write_native_adoption_ledger(ledger)
            return _native_json_value(completed)

    def read_lineage_adoption(self, adoption_id: Any) -> Optional[Dict[str, Any]]:
        """Read one adoption intent without provisioning or mutation."""

        adoption_id = _opaque_token(adoption_id, "native adoption ID")
        with self._native_adoption_locked():
            entry = self._load_native_adoption_ledger().get(adoption_id)
            return None if entry is None else _native_json_value(entry)

    def release_lineage_claim(
            self, lineage_id: Any, *,
            coordinator_session_uuid: Any = None,
            owner_generation: Any = None,
            lineage_generation: Any = None,
            authoritative: bool = False) -> Dict[str, Any]:
        """Release a workspace claim only after explicit native proof."""

        if authoritative is not True:
            raise _error(
                "uncertain-effect",
                "native lineage claim release requires authoritative stop/effect proof",
            )
        (lineage_id, coordinator_session_uuid, owner_generation,
         lineage_generation, _parent_read_only) = self._native_claim_context(
             lineage_id, coordinator_session_uuid, owner_generation,
             lineage_generation, False,
         )
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            current_generation = owner.get("generation")
            if owner.get("mode") != "managed":
                raise _error("ownership-conflict", "native lineage owner is unavailable")
            if owner_generation is not None and owner_generation != current_generation:
                raise _error("stale-generation", "native lineage claim owner generation is stale")
            claims = self._load_claims()
            matches = [
                claim for claim in claims
                if claim.get("record_kind") == "workspace-claim" and
                claim.get("lineage_id") == lineage_id and
                claim.get("coordinator_session_uuid") == coordinator_session_uuid and
                claim.get("lane_key") == self.identity.lane_key and
                claim.get("host") == self.identity.host and
                claim.get("common_dir") == str(self.identity.common_dir) and
                claim.get("owner_generation") == current_generation and
                claim.get("lineage_generation") == lineage_generation
            ]
            if len(matches) != 1:
                raise _error("ownership-conflict", "native lineage workspace claim is not exact")
            if any(
                    claim.get("lineage_id") == lineage_id and
                    claim.get("record_kind") == "child-worktree-claim"
                    for claim in claims):
                raise _error("ownership-conflict", "native child worktree claims remain active")
            match = matches[0]
            self._write_claims([
                claim for claim in claims if claim is not match
            ])
            released = dict(match)
            released["state"] = "released"
            released["released_at"] = time.time()
            self.append_journal("claims", {"event": "native-lineage-release", **released})
            return released

    def release_child_worktree_claim(
            self, lineage_id: Any, agent_id: Any, task_id: Any, *,
            coordinator_session_uuid: Any = None,
            owner_generation: Any = None,
            lineage_generation: Any = None,
            authoritative: bool = False) -> Dict[str, Any]:
        """Release one exact isolated child claim after native completion."""

        if authoritative is not True:
            raise _error(
                "uncertain-effect",
                "native child claim release requires authoritative stop/effect proof",
            )
        (lineage_id, coordinator_session_uuid, owner_generation,
         lineage_generation, _parent_read_only) = self._native_claim_context(
             lineage_id, coordinator_session_uuid, owner_generation,
             lineage_generation, False,
         )
        agent_id = _opaque_token(agent_id, "agent_id")
        task_id = _opaque_token(task_id, "task_id")
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            current_generation = owner.get("generation")
            if owner.get("mode") != "managed":
                raise _error("ownership-conflict", "native lineage owner is unavailable")
            if owner_generation is not None and owner_generation != current_generation:
                raise _error("stale-generation", "native child claim owner generation is stale")
            claims = self._load_claims()
            matches = [
                claim for claim in claims
                if claim.get("record_kind") == "child-worktree-claim" and
                claim.get("lineage_id") == lineage_id and
                claim.get("coordinator_session_uuid") == coordinator_session_uuid and
                claim.get("lane_key") == self.identity.lane_key and
                claim.get("host") == self.identity.host and
                claim.get("common_dir") == str(self.identity.common_dir) and
                claim.get("owner_generation") == current_generation and
                claim.get("lineage_generation") == lineage_generation and
                claim.get("agent_id") == agent_id and
                claim.get("task_id") == task_id
            ]
            if len(matches) != 1:
                raise _error("ownership-conflict", "native child worktree claim is not exact")
            match = matches[0]
            self._write_claims([
                claim for claim in claims if claim is not match
            ])
            released = dict(match)
            released["state"] = "released"
            released["released_at"] = time.time()
            self.append_journal("claims", {"event": "native-child-release", **released})
            return released

        # Short explicit names used by the controller boundary.  They do not
        # change the durable wire shape or accept prototype identity aliases.
    release_lineage = release_lineage_claim
    release_child_worktree = release_child_worktree_claim

    def _reject_independent_claim_api(self, message: str) -> None:
        """Validate durable state before refusing the obsolete claim API.

        The old participant claim methods remain as visible refusal points
        while the controller moves to lineage claims.  They still cross the
        durable-state boundary, so an existing schema-1 or malformed record
        must be reported before the compatibility refusal.  Otherwise a
        caller could mistake an unreadable old index for a clean unsupported
        operation and proceed without reconciling the recorded ownership.
        """

        self.ensure_layout()
        with self.locked():
            self._load_owner()
            self._load_generation()
            self._load_recovery_intent()
            self._load_claims()
        raise _error("unsupported", message)

    def claim_writer(self, participant_id: str, worktree: Any,
                     repository: Any = None) -> Dict[str, Any]:
        """Reject the superseded independent-participant claim API.

        Native ownership is claimed by a coordinator lineage.  Keeping this
        entry point as a refusal prevents callers from turning a child
        participant name into a second top-level owner while the lifecycle
        controller migrates to :meth:`claim_lineage`.
        """

        self._reject_independent_claim_api(
            "independent participant writer claims are superseded; use claim_lineage",
        )

        # The historical implementation is intentionally unreachable.  It is
        # left below during the bounded controller migration only to keep the
        # surrounding release/transfer code structurally localized.
        participant_id = _canonical_component(participant_id, "participant_id")
        canonical_worktree = self._canonical_worktree(worktree)
        repository_id = self._canonical_repository(repository, canonical_worktree)
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            # Claims always carry a positive generation.  After unenrollment,
            # the tombstone keeps compatibility claims from recycling 1.
            owner_generation = self._claim_generation(owner)
            claims = self._load_claims()
            for existing in claims:
                existing_path_raw = existing.get("worktree")
                if not isinstance(existing_path_raw, str):
                    raise _error("unknown", "global writer claim has no canonical worktree")
                existing_path = self._canonical_worktree(existing_path_raw)
                if self._paths_overlap(canonical_worktree, existing_path):
                    same_claim = (
                        existing.get("lane_key") == self.identity.lane_key and
                        existing.get("participant_id") == participant_id and
                        existing_path == canonical_worktree and
                        existing.get("generation") == owner_generation
                    )
                    if same_claim:
                        return existing
                    holder = "%s/%s" % (existing.get("lane", "unknown"),
                                         existing.get("participant_id", "unknown"))
                    raise _error("ownership-conflict",
                                 "worktree overlaps active writer claim %s" % holder)
            record: Dict[str, Any] = {
                "state": "active",
                "lane": self.identity.lane,
                "lane_key": self.identity.lane_key,
                "host": self.identity.host,
                "workspace": str(self.identity.workspace_root),
                "common_dir": str(self.identity.common_dir),
                "participant_id": participant_id,
                "worktree": str(canonical_worktree),
                "repository": repository_id,
                "generation": owner_generation,
                "claimed_at": time.time(),
            }
            self._write_claims(claims + [record])
            self.append_journal("claims", {"event": "claim", **record})
            return dict(record)

    def release_writer(self, participant_id: str, worktree: Any) -> Dict[str, Any]:
        """Release an exact participant/path claim after authoritative stop."""

        self._reject_independent_claim_api(
            "independent participant writer claims are superseded; use release_lineage_claim",
        )

        participant_id = _canonical_component(participant_id, "participant_id")
        canonical_worktree = self._canonical_worktree(worktree)
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            owner_generation = self._claim_generation(owner)
            claims = self._load_claims()
            match: Optional[Dict[str, Any]] = None
            remaining: list[Dict[str, Any]] = []
            for existing in claims:
                existing_path_raw = existing.get("worktree")
                if not isinstance(existing_path_raw, str):
                    raise _error("unknown", "global writer claim has no canonical worktree")
                existing_path = self._canonical_worktree(existing_path_raw)
                if (match is None and existing.get("lane_key") == self.identity.lane_key and
                        existing.get("participant_id") == participant_id and
                        existing_path == canonical_worktree):
                    if existing.get("generation") != owner_generation:
                        raise _error("ownership-conflict",
                                     "writer claim belongs to a different owner generation")
                    match = existing
                    continue
                remaining.append(existing)
            if match is None:
                raise _error("ownership-conflict",
                             "worktree is not held by this participant in lane %s" %
                             self.identity.lane)
            self._write_claims(remaining)
            released = dict(match)
            released["state"] = "released"
            released["released_at"] = time.time()
            self.append_journal("claims", {"event": "release", **released})
            return released

    def transfer_writer_claim(self, old_participant_id: str, worktree: Any,
                              repository: Any, lane: str, generation: int,
                              new_participant_id: str) -> Dict[str, Any]:
        """Transfer one exact claim without exposing an unclaimed interval."""

        self._reject_independent_claim_api(
            "independent participant writer claims are superseded; use claim_lineage",
        )

        old_participant_id = _canonical_component(
            old_participant_id, "old participant_id")
        new_participant_id = _canonical_component(
            new_participant_id, "new participant_id")
        canonical_worktree = self._canonical_worktree(worktree)
        canonical_repository = self._canonical_record_path(
            repository, "claim repository")
        old_lane = canonical_lane(lane)
        if old_lane.casefold() != self.identity.lane_key:
            raise _error("ownership-conflict",
                         "claim lane does not match this managed state")
        if (isinstance(generation, bool) or not isinstance(generation, int) or
                generation <= 0):
            raise _error("invalid", "claim generation must be a positive integer")
        self.ensure_layout()
        with self.locked():
            owner = self._load_owner()
            current_generation = self._claim_generation(owner)
            if generation != current_generation:
                raise _error("ownership-conflict",
                             "claim transfer belongs to a different owner generation")
            claims = self._load_claims()
            worktree_text = str(canonical_worktree)
            repository_text = str(canonical_repository)
            old_match: Optional[Dict[str, Any]] = None
            new_match: Optional[Dict[str, Any]] = None
            for claim in claims:
                same_identity = (
                    claim["lane_key"] == self.identity.lane_key and
                    claim["worktree"] == worktree_text and
                    claim["repository"] == repository_text and
                    claim["generation"] == generation
                )
                if not same_identity:
                    continue
                if claim["lane"] != old_lane:
                    raise _error("ownership-conflict",
                                 "claim lane CAS does not match the recorded lane")
                if claim["participant_id"] == old_participant_id:
                    old_match = claim
                if claim["participant_id"] == new_participant_id:
                    new_match = claim
            if old_match is None:
                if new_match is not None:
                    return dict(new_match)
                raise _error("ownership-conflict",
                             "writer claim CAS does not match the active index")
            if new_participant_id == old_participant_id:
                return dict(old_match)
            if new_match is not None:
                raise _error("ownership-conflict",
                             "new participant already owns the writer claim")
            replacement = dict(old_match)
            replacement["participant_id"] = new_participant_id
            replaced = False
            updated: list[Dict[str, Any]] = []
            for claim in claims:
                if claim is old_match and not replaced:
                    updated.append(replacement)
                    replaced = True
                else:
                    updated.append(claim)
            if not replaced:
                raise _error("ownership-conflict",
                             "writer claim changed during transfer")
            # _write_claims uses one fsynced atomic replace while the shared
            # lock is held: observers see either complete old or new claim.
            self._write_claims(updated)
            self.append_journal("claims", {
                "event": "transfer",
                "old_participant_id": old_participant_id,
                "new_participant_id": new_participant_id,
                "lane": old_lane,
                "lane_key": self.identity.lane_key,
                "generation": generation,
                "worktree": worktree_text,
                "repository": repository_text,
            })
            return dict(replacement)


__all__ = [
    "LEGACY_SCHEMA_VERSION",
    "ManagedStateError",
    "ManagedStateStore",
    "NATIVE_ARCHITECTURE",
    "NATIVE_RECORD_MARKER",
    "NATIVE_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "WorkspaceIdentity",
    "canonical_lane",
    "native_record_marker",
    "resolve_workspace",
    "validate_native_lineage_record",
    "validate_native_record",
]
