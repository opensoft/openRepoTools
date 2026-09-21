# SPDX-License-Identifier: Apache-2.0
"""Read-only resolution of workBenches Claude profiles.

This module intentionally has no launcher or credential-management dependency.
The workBenches manifest identifies a profile and its metadata-repository
path; the profile directory itself is discovered below ``CLAUDE_PROFILES_HOME``
and is never created, copied, or modified here.
"""

from __future__ import annotations

import errno
import json
import os
import stat
import subprocess
import sys
import uuid as _uuid
from dataclasses import dataclass
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple


__all__ = [
    "ProfileError",
    "ProfileReference",
    "ProfileResolver",
    "resolve_profile",
    "verify_transcript",
    "sanitize_environment",
    "sanitized_environment",
]


_TRANSCRIPT_IDENTITY_TIMEOUT = 1.0
_MAX_TRANSCRIPT_METADATA_BYTES = 1024 * 1024
_MAX_TRANSCRIPT_PROFILE_FILES = 4096
_MAX_PROFILE_HOLDER_FILES = 4096


# A managed launch must not inherit an account, provider, or endpoint selected
# by the parent process.  Keep this list explicit: removing every variable
# with a broad prefix would also discard unrelated user configuration.
_AUTH_AND_PROVIDER_ENV = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_API_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_URL",
        "ANTHROPIC_API_BASE",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_PROVIDER",
        "CLAUDE_PROVIDER",
        "CLAUDE_CODE_BASE_URL",
        "CLAUDE_API_BASE_URL",
        "AWS_PROFILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
        "AWS_ENDPOINT_URL",
        "AWS_BEARER_TOKEN_BEDROCK",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_REGION",
        "GOOGLE_CLOUD_QUOTA_PROJECT",
        "GOOGLE_API_KEY",
        "VERTEXAI_PROJECT",
        "VERTEXAI_LOCATION",
        "VERTEX_PROJECT",
        "VERTEX_REGION",
    }
)


class ProfileError(Exception):
    """A stable, operator-safe profile refusal.

    ``message`` is deliberately supplied by this module as a sanitized
    explanation.  We never include parsed JSON, environment values, or file
    contents in an error, so even callers that display ``str(error)`` cannot
    accidentally print credentials.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.message = str(message)
        super().__init__(self.message)


def _freeze(value: Any) -> Any:
    """Return a recursively immutable, JSON-shaped value."""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ProfileReference:
    """The non-secret identity and existing storage location of a profile."""

    name: str
    email: str
    family: str
    config_dir: Path
    authentication: Optional[Mapping[str, Any]]
    status: str
    metadata_path: Path
    aliases: Tuple[str, ...] = ()
    # ``profile_path`` is the manifest's metadata-repository path.  It is kept
    # as a compatibility/readability field and is never used as a credential
    # or copied into a profile directory.
    profile_path: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "config_dir", Path(self.config_dir))
        object.__setattr__(self, "metadata_path", Path(self.metadata_path))
        object.__setattr__(self, "aliases", tuple(self.aliases or ()))
        if self.authentication is not None:
            object.__setattr__(self, "authentication", _freeze(self.authentication))

    @property
    def profile_dir(self) -> Path:
        """Historical name used by the profile launcher and older callers."""

        return self.config_dir

    @property
    def authentication_type(self) -> Optional[str]:
        """Return the manifest authentication type, when one was supplied."""

        if self.authentication is None:
            return None
        value = self.authentication.get("type")
        return value if isinstance(value, str) else None


def _text(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ProfileError("invalid", "profile metadata has an invalid " + field)
    if not allow_empty and not value.strip():
        raise ProfileError("invalid", "profile metadata is missing " + field)
    if "\x00" in value:
        raise ProfileError("invalid", "profile metadata has an invalid " + field)
    return value


def _safe_profile_name(value: Any, field: str = "name") -> str:
    result = _text(value, field)
    # A profile name is eventually used as one directory component.  Reject
    # path syntax rather than relying on a later resolve() check.
    if result in {".", ".."} or "/" in result or "\\" in result:
        raise ProfileError("invalid", "profile " + field + " is an unsafe path component")
    return result


def _aliases(value: Any) -> Tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ProfileError("invalid", "profile metadata has invalid aliases")
    result = []
    for alias in value:
        alias = _text(alias, "alias")
        if alias in {".", ".."} or "\x00" in alias:
            raise ProfileError("invalid", "profile metadata has an invalid alias")
        result.append(alias)
    return tuple(result)


def _fold(value: str) -> str:
    return value.casefold()


def _safe_relative_path(value: Any, field: str = "profilePath") -> str:
    path = _text(value, field)
    # Manifest paths are POSIX-style repository-relative paths even when the
    # caller is on a host that accepts another path syntax.
    if path.startswith("/") or path.startswith("\\"):
        raise ProfileError("invalid", "profile path is absolute or outside its boundary")
    if "\x00" in path or "\\" in path:
        raise ProfileError("invalid", "profile path contains unsafe traversal syntax")
    parts = PurePath(path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ProfileError("invalid", "profile path contains unsafe traversal syntax")
    return "/".join(parts)


def _path_from_env(value: Optional[str], env: Mapping[str, str], *, default: Optional[Path] = None) -> Path:
    raw = value if value else (str(default) if default is not None else None)
    if raw is None or not isinstance(raw, str) or not raw:
        raise ProfileError("invalid", "profile storage home is not configured")
    # expanduser() consults the process environment, which is wrong for the
    # isolated env mapping used by tests and by managed child processes.
    if raw == "~" or raw.startswith("~/"):
        home = env.get("HOME")
        if not isinstance(home, str) or not home:
            raise ProfileError("invalid", "HOME is not configured for profile paths")
        raw = home + raw[1:]
    return Path(raw).expanduser()


def _under(base: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(base)
    except ValueError:
        return False
    return True


def _resolved_under(base: Path, candidate: Path) -> Path:
    """Resolve a candidate and reject traversal or an external symlink."""

    base_real = base.resolve(strict=False)
    candidate_real = candidate.resolve(strict=False)
    if not _under(base_real, candidate_real) or candidate_real == base_real:
        raise ProfileError("invalid", "profile config path is outside its boundary")

    # Check each physical component.  A symlink entirely within the trusted
    # profiles tree is usable; a link crossing the tree boundary is refused.
    try:
        relative = candidate.relative_to(base)
    except ValueError:
        raise ProfileError("invalid", "profile config path is outside its boundary")
    current = base
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            target = current.resolve(strict=False)
            if not _under(base_real, target):
                raise ProfileError("invalid", "profile config path crosses an unsafe symlink")
    return candidate_real


def _read_json(path: Path, *, kind: str) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError, TypeError):
        raise ProfileError("invalid", "profile " + kind + " is unreadable or malformed")


def _metadata(path: Path) -> dict[str, Any]:
    raw = _read_json(path, kind="metadata")
    if not isinstance(raw, dict):
        raise ProfileError("invalid", "profile metadata must be an object")
    name = _safe_profile_name(raw.get("name"))
    email = _text(raw.get("email"), "email")
    family = _text(raw.get("family"), "family")
    aliases = _aliases(raw.get("aliases", ()))
    return {"name": name, "email": email, "family": family, "aliases": aliases}


def _manifest_entries(path: Path) -> Optional[list[dict[str, Any]]]:
    if not path.exists():
        return None
    if not path.is_file():
        raise ProfileError("invalid", "profile manifest is not a regular file")
    raw = _read_json(path, kind="manifest")
    if not isinstance(raw, dict) or not isinstance(raw.get("profiles"), list):
        raise ProfileError("invalid", "profile manifest has no valid profiles list")

    entries: list[dict[str, Any]] = []
    for item in raw["profiles"]:
        if not isinstance(item, dict):
            raise ProfileError("invalid", "profile manifest contains an invalid profile")
        name = _safe_profile_name(item.get("name"))
        email = _text(item.get("email"), "email")
        family = _text(item.get("family"), "family")
        aliases = _aliases(item.get("aliases", ()))
        status = _text(item.get("status"), "status").casefold()
        profile_path = _safe_relative_path(item.get("profilePath"))
        authentication = item.get("authentication")
        if not isinstance(authentication, dict):
            raise ProfileError("invalid", "profile manifest has invalid authentication")
        auth_type = _text(authentication.get("type"), "authentication type")
        # Keep only non-secret identity metadata.  A workBenches manifest may
        # contain credential references, but this resolver must never retain
        # or expose them through its immutable reference.
        entries.append(
            {
                "name": name,
                "email": email,
                "family": family,
                "aliases": aliases,
                "status": status,
                "profilePath": profile_path,
                "authentication": MappingProxyType({"type": auth_type}),
            }
        )
    return entries


def _matches(value: str, entry: Mapping[str, Any], *, include_aliases: bool = True) -> bool:
    wanted = _fold(value)
    if wanted == _fold(entry["name"]):
        return True
    if include_aliases:
        return any(wanted == _fold(alias) for alias in entry.get("aliases", ()))
    return False


def _reject_metadata_symlink_components(
    profiles_root: Path, candidate: Path, label: str
) -> None:
    """Reject symlinks in a metadata path below the trusted profiles root."""

    try:
        if profiles_root.is_symlink():
            raise ProfileError("invalid", "profile storage root is a symlink")
        relative = candidate.relative_to(profiles_root)
    except ValueError:
        raise ProfileError("invalid", label + " is outside its boundary")
    current = profiles_root
    for component in relative.parts:
        current = current / component
        try:
            if current.is_symlink():
                raise ProfileError("invalid", label + " contains a symlink")
        except OSError:
            raise ProfileError("unknown", label + " could not be inspected")


def _metadata_files(root: Path) -> list[Path]:
    try:
        root_info = root.lstat()
    except FileNotFoundError:
        return []
    except OSError:
        raise ProfileError("invalid", "profile storage tree is unreadable")
    if stat.S_ISLNK(root_info.st_mode):
        raise ProfileError("invalid", "profile storage root is a symlink")
    if not stat.S_ISDIR(root_info.st_mode):
        return []
    result: list[Path] = []
    try:
        # os.walk does not follow directory symlinks by default.  Prune the
        # canonical runtime projects store explicitly: deployed profiles may
        # point that non-metadata subtree at a shared store outside ``profiles``.
        # It must not affect discovery of the profile metadata beside it.
        # Every other symlinked directory is a profile/config path and is
        # rejected, including links that happen to remain inside this tree.
        for current, dirs, files in os.walk(str(root), followlinks=False):
            for directory in list(dirs):
                linked = Path(current) / directory
                if not linked.is_symlink():
                    continue
                dirs.remove(directory)
                if directory == "projects":
                    continue
                raise ProfileError("invalid", "profile storage tree contains a symlinked config path")
            if ".profile.json" in files:
                result.append(Path(current) / ".profile.json")
    except OSError:
        raise ProfileError("invalid", "profile storage tree is unreadable")
    return sorted(result, key=lambda item: str(item))


def _candidate_metadata(
    metadata_path: Path,
    profiles_root: Path,
    *,
    expected: Optional[Mapping[str, Any]] = None,
) -> tuple[Path, dict[str, Any]]:
    config_dir = metadata_path.parent
    # Metadata discovery never follows symlinked profile roots.  Keep this
    # check here too because an explicit manifest path can bypass the walk.
    _reject_metadata_symlink_components(
        profiles_root, config_dir, "profile config directory"
    )
    _reject_metadata_symlink_components(profiles_root, metadata_path, "profile metadata")
    config_real = _resolved_under(profiles_root, config_dir)
    metadata_real = _resolved_under(profiles_root, metadata_path)
    if not config_real.is_dir() or not metadata_real.is_file():
        raise ProfileError("invalid", "profile config directory or metadata is missing")
    data = _metadata(metadata_real)
    if expected is not None:
        # Manifest identity is authoritative for the selected account.  Name
        # and storage family must agree; an email can be refreshed in a
        # manifest before a local metadata snapshot is updated.
        if _fold(data["name"]) != _fold(expected["name"]):
            raise ProfileError("invalid", "profile metadata does not match its manifest")
        if _fold(data["family"]) != _fold(expected["family"]):
            raise ProfileError("profile-mismatch", "profile metadata belongs to another family")
    return config_real, data


def _reject_symlink_components(path: Path, label: str) -> None:
    """Reject a path whose lexical components contain a symlink."""

    if not path.is_absolute():
        raise ProfileError("invalid", label + " must be an absolute path")
    current = Path(path.anchor)
    components = path.parts[1:] if path.anchor else path.parts
    for component in components:
        current = current / component
        try:
            if current.is_symlink():
                raise ProfileError("invalid", label + " contains a symlink")
        except OSError:
            raise ProfileError("unknown", label + " could not be inspected")


def _lstat(path: Path, label: str) -> os.stat_result:
    try:
        return path.lstat()
    except FileNotFoundError:
        raise ProfileError("unknown", label + " is missing")
    except OSError:
        raise ProfileError("unknown", label + " could not be inspected")


def _require_directory(path: Path, label: str, *, reject_symlink: bool = True) -> Path:
    info = _lstat(path, label)
    if stat.S_ISLNK(info.st_mode):
        if reject_symlink:
            raise ProfileError("invalid", label + " is a symlink")
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ProfileError("unknown", label + " could not be resolved")
        try:
            if not resolved.is_dir():
                raise ProfileError("invalid", label + " is not a directory")
        except OSError:
            raise ProfileError("unknown", label + " could not be inspected")
        return resolved
    if not stat.S_ISDIR(info.st_mode):
        raise ProfileError("invalid", label + " is not a directory")
    try:
        return path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ProfileError("unknown", label + " could not be resolved")


def _profile_storage_boundary(config_dir: Path) -> Path:
    """Return the private profile tree boundary for an existing config path."""

    for ancestor in (config_dir, *config_dir.parents):
        if ancestor.name == "profiles":
            try:
                return ancestor.parent.resolve(strict=False)
            except (OSError, RuntimeError):
                raise ProfileError("unknown", "profile storage boundary could not be resolved")
    try:
        return config_dir.parent.resolve(strict=False)
    except (OSError, RuntimeError):
        raise ProfileError("unknown", "profile storage boundary could not be resolved")


def _profile_config(profile: ProfileReference) -> tuple[Path, dict[str, Any]]:
    """Validate a resolved profile against its on-disk identity metadata."""

    if not isinstance(profile, ProfileReference):
        raise ProfileError("invalid", "transcript verification requires a resolved profile")
    if (
        not isinstance(profile.name, str)
        or not isinstance(profile.email, str)
        or not isinstance(profile.family, str)
        or not profile.name.strip()
        or not profile.email.strip()
        or not profile.family.strip()
        or any("\x00" in value for value in (profile.name, profile.email, profile.family))
    ):
        raise ProfileError("invalid", "profile identity is incomplete")
    _safe_profile_name(profile.name)
    if str(profile.status).casefold() != "active":
        raise ProfileError("unsupported", "profile is inactive or unavailable")
    auth_type = profile.authentication_type
    normalized_auth = str(auth_type).casefold().replace("-", "_").replace(" ", "_")
    if normalized_auth != "subscription_oauth":
        raise ProfileError("unsupported", "profile authentication type is unsupported")

    config_dir = Path(profile.config_dir)
    if not config_dir.is_absolute():
        raise ProfileError("invalid", "profile config directory must be absolute")
    _reject_symlink_components(config_dir, "profile config directory")
    config_real = _require_directory(config_dir, "profile config directory")
    metadata_path = config_real / ".profile.json"
    metadata_info = _lstat(metadata_path, "profile metadata")
    if stat.S_ISLNK(metadata_info.st_mode) or not stat.S_ISREG(metadata_info.st_mode):
        raise ProfileError("invalid", "profile metadata is not a regular file")
    metadata = _metadata(metadata_path)
    if _fold(metadata["name"]) != _fold(profile.name):
        raise ProfileError("profile-mismatch", "profile metadata belongs to another profile")
    if _fold(metadata["family"]) != _fold(profile.family):
        raise ProfileError("profile-mismatch", "profile metadata belongs to another family")
    return config_real, metadata


def _validate_session_id(session_id: Any) -> str:
    if not isinstance(session_id, str) or not session_id:
        raise ProfileError("invalid", "session ID is required")
    if "\x00" in session_id or "/" in session_id or "\\" in session_id:
        raise ProfileError("invalid", "session ID is not a UUID")
    try:
        parsed = _uuid.UUID(session_id)
    except (ValueError, AttributeError, TypeError):
        raise ProfileError("invalid", "session ID is not a UUID")
    canonical = str(parsed)
    if session_id != canonical:
        raise ProfileError("invalid", "session ID is not a canonical UUID")
    return session_id


def _canonical_workspace(workspace: Any) -> Path:
    if isinstance(workspace, (str, Path)):
        candidate = Path(workspace)
    else:
        raise ProfileError("invalid", "workspace must be an absolute directory")
    if not candidate.is_absolute():
        raise ProfileError("invalid", "workspace must be an absolute directory")
    _reject_symlink_components(candidate, "workspace")
    return _require_directory(candidate, "workspace")


def _workspace_project_key(workspace: Path) -> str:
    """Use Claude Code's deterministic projects-directory spelling."""

    value = str(workspace).replace("\\", "/")
    # The native launcher uses a conservative ASCII slug for an absolute cwd:
    # every character outside ``A-Z``, ``a-z`` and ``0-9`` becomes ``-``.
    # Keeping this local avoids importing the launcher or consulting mutable
    # profile state just to derive the exact transcript directory.
    key = "".join(
        character
        if (
            "A" <= character <= "Z"
            or "a" <= character <= "z"
            or "0" <= character <= "9"
        )
        else "-"
        for character in value
    )
    if not key or key in {".", ".."} or "\x00" in key:
        raise ProfileError("invalid", "workspace projects-directory identity is invalid")
    return key


def _projects_store_for_config(config_dir: Path, family: str, *, required: bool) -> Optional[Path]:
    projects = config_dir / "projects"
    try:
        info = projects.lstat()
    except FileNotFoundError:
        if required:
            raise ProfileError("unknown", "canonical projects store is missing")
        return None
    except OSError:
        raise ProfileError("unknown", "canonical projects store could not be inspected")

    if stat.S_ISLNK(info.st_mode):
        try:
            resolved = projects.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ProfileError("unknown", "canonical projects store could not be resolved")
        boundary = _profile_storage_boundary(config_dir)
        if not _under(boundary, resolved) or resolved == boundary:
            raise ProfileError("invalid", "canonical projects store crosses its profile boundary")
        try:
            if not resolved.is_dir():
                raise ProfileError("invalid", "canonical projects store is not a directory")
        except OSError:
            raise ProfileError("unknown", "canonical projects store could not be inspected")
        return resolved
    if not stat.S_ISDIR(info.st_mode):
        raise ProfileError("invalid", "canonical projects store is not a directory")
    try:
        resolved = projects.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ProfileError("unknown", "canonical projects store could not be resolved")
    # ``family`` is intentionally consumed here so a future layout cannot
    # silently use a store from a different family when it is materialized
    # directly below a profile.
    if not isinstance(family, str) or not family:
        raise ProfileError("invalid", "profile family is missing")
    return resolved


def _family_profile_configs(
    profile: ProfileReference,
    selected_config: Path,
    *,
    resolver: Optional[ProfileResolver] = None,
) -> list[tuple[Path, dict[str, Any]]]:
    """Find the concrete profile stores that can share this transcript family."""

    if resolver is not None:
        profiles_root = resolver._profiles_root().resolve(strict=False)
        if not _under(profiles_root, selected_config):
            raise ProfileError("profile-mismatch", "profile config is outside the resolver profile store")
    else:
        root = selected_config
        while root.name != "profiles" and root != root.parent:
            root = root.parent
        profiles_root = root if root.name == "profiles" else selected_config.parent
    try:
        if not profiles_root.is_dir():
            raise ProfileError("unknown", "same-family profile store is unavailable")
    except OSError:
        raise ProfileError("unknown", "same-family profile store is unavailable")
    try:
        metadata_files = _metadata_files(profiles_root)
    except ProfileError:
        raise
    if len(metadata_files) > _MAX_TRANSCRIPT_PROFILE_FILES:
        raise ProfileError("unknown", "same-family profile store is too large")

    result: list[tuple[Path, dict[str, Any]]] = [(selected_config, {
        "name": profile.name,
        "email": profile.email,
        "family": profile.family,
        "aliases": tuple(profile.aliases),
    })]
    seen = {selected_config}
    for metadata_path in metadata_files:
        try:
            metadata_info = _lstat(metadata_path, "same-family profile metadata")
            if stat.S_ISLNK(metadata_info.st_mode) or not stat.S_ISREG(metadata_info.st_mode):
                raise ProfileError("invalid", "same-family profile metadata is not a regular file")
            metadata = _metadata(metadata_path)
        except ProfileError as exc:
            # A malformed sibling cannot be classified as a different family;
            # refusing is the only safe answer for holder enumeration.
            raise ProfileError("unknown", "same-family profile metadata is unreadable") from exc
        if _fold(metadata["family"]) != _fold(profile.family):
            continue
        try:
            config = metadata_path.parent.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ProfileError("unknown", "same-family profile config is unreadable") from exc
        if config in seen:
            continue
        seen.add(config)
        result.append((config, metadata))
    return result


def _process_start_identity(pid: int) -> Optional[str]:
    """Read a stable PID incarnation token using procfs or portable ``ps``."""

    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        raw = Path("/proc/%d/stat" % pid).read_text(encoding="utf-8")
        suffix = raw.rsplit(")", 1)[-1].split()
        if len(suffix) > 19 and suffix[19].isdigit():
            return suffix[19]
    except (OSError, UnicodeError, ValueError):
        pass
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            check=False,
            timeout=_TRANSCRIPT_IDENTITY_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if getattr(result, "returncode", 1) != 0:
        return None
    output = getattr(result, "stdout", None)
    if not isinstance(output, str):
        return None
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    token = lines[0]
    if token in {"?", "-"} or len(token) > 256 or "\x00" in token:
        return None
    return token


def _pid_is_alive(pid: int) -> Optional[bool]:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        # The caller has already proved the native holder's exact local
        # pidDomain before reaching this lookup.  ESRCH is therefore stale /
        # absent evidence for this holder, rather than a foreign-namespace
        # ambiguity.  Foreign and unrecognized domains never reach this path.
        return False
    except PermissionError:
        return True
    except OSError as exc:
        if getattr(exc, "errno", None) == errno.ESRCH:
            return False
        # EPERM and every other observation failure remain conservative: a
        # matching PID cannot be treated as dead without a reliable answer.
        return None
    return True


def _local_pid_domain() -> Optional[str]:
    """Derive the exact local process domain used by native holder records.

    Linux and WSL expose both inputs needed for a stable domain: the machine
    identity and the PID namespace inode.  Other platforms have no equivalent
    format in the native record contract, so returning ``None`` is deliberate
    fail-closed behavior rather than guessing from a hostname or PID.
    """

    if not sys.platform.startswith("linux"):
        return None
    try:
        machine_id = Path("/etc/machine-id").read_text(encoding="ascii").strip()
        namespace = os.readlink("/proc/self/ns/pid").strip()
    except (OSError, UnicodeError, ValueError):
        return None
    if (
        not machine_id
        or len(machine_id) > 256
        or "\x00" in machine_id
        or any(character not in "0123456789abcdefABCDEF" for character in machine_id)
        or not namespace.startswith("pid:[")
        or not namespace.endswith("]")
        or not namespace[5:-1]
        or not namespace[5:-1].isdigit()
    ):
        return None
    return "linux:" + machine_id + ":" + namespace


def _process_group_id(pid: int) -> Optional[int]:
    """Read a holder's current process-group ID when the host exposes it."""

    getpgid = getattr(os, "getpgid", None)
    if not callable(getpgid):
        return None
    try:
        value = getpgid(pid)
    except (OSError, ValueError):
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _bounded_json_file(path: Path, label: str) -> Any:
    info = _lstat(path, label)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ProfileError("invalid", label + " is not a regular file")
    if info.st_size > _MAX_TRANSCRIPT_METADATA_BYTES:
        raise ProfileError("invalid", label + " is too large")
    try:
        raw = path.read_bytes()
        if len(raw) > _MAX_TRANSCRIPT_METADATA_BYTES:
            raise ProfileError("invalid", label + " is too large")
        return json.loads(raw.decode("utf-8"))
    except ProfileError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError):
        raise ProfileError("unknown", label + " is unreadable or malformed")


def _private_transcript_file(path: Path) -> None:
    info = _lstat(path, "transcript")
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ProfileError("invalid", "transcript is not a regular file")
    if os.name != "nt" and info.st_mode & 0o077:
        raise ProfileError("invalid", "transcript file is not private")
    if os.name != "nt" and not (info.st_mode & 0o400):
        raise ProfileError("invalid", "transcript file is not readable")
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise ProfileError("ownership-conflict", "transcript file is owned by another user")


def _session_holders(
    config_dir: Path,
    profile_name: str,
    session_id: str,
    workspace: Path,
) -> tuple[list[dict[str, Any]], int]:
    """Read authoritative Claude session holder records for one config tree."""

    sessions = config_dir / "sessions"
    try:
        info = sessions.lstat()
    except FileNotFoundError:
        return [], 0
    except OSError:
        raise ProfileError("unknown", "profile session holder directory is unreadable")
    if stat.S_ISLNK(info.st_mode):
        raise ProfileError("invalid", "profile session holder directory is a symlink")
    if not stat.S_ISDIR(info.st_mode):
        raise ProfileError("invalid", "profile session holder path is not a directory")
    try:
        entries = sorted(sessions.iterdir(), key=lambda item: str(item))
    except OSError:
        raise ProfileError("unknown", "profile session holder directory is unreadable")
    if len(entries) > _MAX_PROFILE_HOLDER_FILES:
        raise ProfileError("unknown", "profile session holder directory is too large")

    holders: list[dict[str, Any]] = []
    matching_records = 0
    for path in entries:
        try:
            path_info = path.lstat()
        except OSError:
            raise ProfileError("unknown", "profile session holder entry is unreadable")
        if stat.S_ISLNK(path_info.st_mode):
            raise ProfileError("invalid", "profile session holder entry is a symlink")
        if not stat.S_ISREG(path_info.st_mode) or path.suffix != ".json":
            continue
        raw = _bounded_json_file(path, "profile session holder record")
        if not isinstance(raw, Mapping):
            raise ProfileError("unknown", "profile session holder record is malformed")
        recorded_session = raw.get("sessionId", raw.get("session_id"))
        if recorded_session is None:
            continue
        if not isinstance(recorded_session, str):
            raise ProfileError("unknown", "profile session holder record has an invalid session ID")
        try:
            canonical_recorded_session = _validate_session_id(recorded_session)
        except ProfileError as exc:
            raise ProfileError("unknown", "profile session holder record has an invalid session ID") from exc
        if canonical_recorded_session != session_id:
            continue
        matching_records += 1
        status = raw.get("status")
        if status is not None:
            if not isinstance(status, str) or "\x00" in status:
                raise ProfileError("unknown", "matching session holder has an invalid status")
            if status.casefold() in {"ended", "exited", "dead", "stopped"}:
                # The record is historical evidence, not a live holder.  It
                # still prevents an absent UUID from being treated as a fresh
                # session below.
                continue
        native_domain = raw.get("pidDomain")
        if (
            not isinstance(native_domain, str)
            or not native_domain
            or "\x00" in native_domain
            or len(native_domain) > 512
        ):
            raise ProfileError("unknown", "matching session holder has no process domain")
        local_domain = _local_pid_domain()
        if local_domain is None:
            raise ProfileError("unknown", "local process domain is unavailable")
        if native_domain != local_domain:
            raise ProfileError("unknown", "matching session holder belongs to another process domain")
        recorded_workspace = raw.get("cwd", raw.get("workspace"))
        if not isinstance(recorded_workspace, str) or not recorded_workspace:
            raise ProfileError("unknown", "matching session holder has no workspace identity")
        try:
            holder_workspace = Path(recorded_workspace)
        except (TypeError, ValueError):
            raise ProfileError("unknown", "matching session holder has an invalid workspace")
        if not holder_workspace.is_absolute():
            raise ProfileError("unknown", "matching session holder has an invalid workspace")
        _reject_symlink_components(holder_workspace, "holder workspace")
        try:
            holder_workspace = holder_workspace.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ProfileError("unknown", "matching session holder workspace is unavailable")
        if holder_workspace != workspace:
            raise ProfileError("ownership-conflict", "matching session holder belongs to another workspace")
        pid = raw.get("pid")
        token = raw.get("procStart", raw.get("process_start_token"))
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ProfileError("unknown", "matching session holder has no valid PID")
        if not isinstance(token, str) or not token or len(token) > 256 or "\x00" in token:
            raise ProfileError("unknown", "matching session holder has no valid start identity")
        pid_alive = _pid_is_alive(pid)
        if pid_alive is None:
            raise ProfileError("unknown", "matching session holder process is not observable")
        if not pid_alive:
            continue
        actual_token = _process_start_identity(pid)
        if actual_token is None:
            raise ProfileError("unknown", "matching session holder process identity is unavailable")
        # A recycled PID is stale evidence, not a live holder.  It still
        # counts as a historical record, so it cannot authorize a fresh UUID.
        if actual_token != token:
            continue
        recorded_process_group_id: Optional[int] = None
        for field in ("process_group_id", "processGroupId", "pgid"):
            if field not in raw or raw[field] is None:
                continue
            value = raw[field]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ProfileError("unknown", "matching session holder has an invalid process group")
            recorded_process_group_id = value
            break
        process_group_id = _process_group_id(pid)
        if (
            recorded_process_group_id is not None
            and process_group_id is not None
            and recorded_process_group_id != process_group_id
        ):
            raise ProfileError("unknown", "matching session holder process group changed")
        if process_group_id is None:
            process_group_id = recorded_process_group_id
        holder = {
            "profile_name": profile_name,
            "session_id": session_id,
            "pid": pid,
            "process_start_token": token,
            "pid_domain": local_domain,
            "record": str(path),
            "live": True,
        }
        if process_group_id is not None:
            holder["process_group_id"] = process_group_id
        # Every live native holder record is an independent piece of
        # ownership evidence.  Even byte-for-byte duplicate files must not be
        # collapsed by PID: doing so could turn a duplicated/ambiguous
        # durable identity into permission to resume.  Historical/stopped
        # records never reach this branch and remain harmless evidence that
        # prevents a fresh UUID reservation.
        if any(item["pid"] == pid for item in holders):
            raise ProfileError("ownership-conflict", "transcript has duplicate live holders")
        holders.append(holder)
    return holders, matching_records


def _project_transcript(
    store: Path,
    workspace_key: str,
    session_id: str,
) -> Optional[dict[str, Any]]:
    project = store / workspace_key
    try:
        project_info = project.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise ProfileError("unknown", "workspace transcript directory is unreadable")
    if stat.S_ISLNK(project_info.st_mode):
        raise ProfileError("invalid", "workspace transcript directory is a symlink")
    if not stat.S_ISDIR(project_info.st_mode):
        raise ProfileError("invalid", "workspace transcript directory is not a directory")
    transcript = project / (session_id + ".jsonl")
    try:
        transcript.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise ProfileError("unknown", "transcript file is unreadable")
    _private_transcript_file(transcript)
    sibling = project / session_id
    try:
        sibling_info = sibling.lstat()
    except FileNotFoundError:
        sibling_info = None
    except OSError:
        raise ProfileError("unknown", "transcript companion directory is unreadable")
    if sibling_info is not None:
        if stat.S_ISLNK(sibling_info.st_mode):
            raise ProfileError("invalid", "transcript companion directory is a symlink")
        if not stat.S_ISDIR(sibling_info.st_mode):
            raise ProfileError("invalid", "transcript companion path is not a directory")
    return {
        "session_id": session_id,
        "path": str(transcript),
        "exists": True,
        "written": True,
        "regular": True,
        "private": True,
        "store": str(store),
        "project": str(project),
    }


def _verify_transcript(
    profile: ProfileReference,
    session_id: Any,
    workspace: Any,
    *,
    resolver: Optional[ProfileResolver] = None,
) -> dict[str, Any]:
    selected_config, selected_metadata = _profile_config(profile)
    session_id = _validate_session_id(session_id)
    workspace_real = _canonical_workspace(workspace)
    workspace_key = _workspace_project_key(workspace_real)
    configs = _family_profile_configs(profile, selected_config, resolver=resolver)

    stores: list[tuple[Path, Path, dict[str, Any]]] = []
    # Keep the per-config relationship independently of ``stores``.  Several
    # profiles in one family may intentionally point at one shared projects
    # directory; deduplicating transcript candidates must not erase the
    # mapping needed to interpret a holder found in a sibling config.
    store_by_config: dict[str, Path] = {}
    holders: list[dict[str, Any]] = []
    matching_records = 0
    for config, metadata in configs:
        store = _projects_store_for_config(
            config,
            profile.family,
            required=config == selected_config,
        )
        sibling_holders, sibling_records = _session_holders(
            config,
            metadata["name"],
            session_id,
            workspace_real,
        )
        holders.extend(
            {
                **holder,
                "config_dir": str(config),
            }
            for holder in sibling_holders
        )
        matching_records += sibling_records
        if store is not None:
            store_by_config[str(config)] = store
            if not any(item[0] == store for item in stores):
                stores.append((store, config, metadata))

    selected_store = store_by_config.get(str(selected_config))
    if selected_store is None:
        raise ProfileError("unknown", "canonical projects store is unavailable")

    if len(holders) > 1:
        raise ProfileError("ownership-conflict", "transcript has ambiguous live holders")
    transcript_candidates: list[dict[str, Any]] = []
    for store, _config, _metadata_data in stores:
        transcript = _project_transcript(store, workspace_key, session_id)
        if transcript is not None:
            transcript_candidates.append(transcript)
    if len(transcript_candidates) > 1:
        raise ProfileError("invalid", "transcript identity is ambiguous across profile stores")
    if transcript_candidates and transcript_candidates[0]["store"] != str(selected_store):
        raise ProfileError("ownership-conflict", "transcript belongs to another profile store")

    project_path = selected_store / workspace_key
    transcript = transcript_candidates[0] if transcript_candidates else {
        "session_id": session_id,
        "path": None,
        "exists": False,
        "written": False,
        "regular": False,
        "private": False,
        "store": str(selected_store),
        "project": str(project_path),
    }
    if not transcript_candidates:
        if matching_records:
            raise ProfileError(
                "unknown",
                "reserved UUID is not proven never-written",
            )
        mode = "fresh"
        reserved = True
    else:
        mode = "resume"
        reserved = False
    transcript["reserved"] = reserved
    transcript["mode"] = mode

    # Holder records are native process facts.  They intentionally contain no
    # managed participant identity: the controller maps the exact UUID back to
    # its sealed roster and decides whether this source holder is the one it
    # expected during a profile switch.
    holder_facts: list[dict[str, Any]] = []
    for holder in holders:
        fact = dict(holder)
        config = Path(str(fact.pop("config_dir", selected_config)))
        store = store_by_config.get(str(config))
        if store is None:
            raise ProfileError("unknown", "holder projects store is unavailable")
        fact.update(
            {
                "profile": fact.get("profile_name"),
                "config_dir": str(config),
                "projects_store": str(store),
                "workspace": str(workspace_real),
                "session_id": session_id,
                "path": fact.get("record"),
                "transcript_path": transcript.get("path"),
            }
        )
        # A native Claude record must never smuggle a managed participant ID
        # across this boundary, even if a future client adds such a field.
        fact.pop("participant_id", None)
        holder_facts.append(fact)

    profile_evidence = {
        "name": profile.name,
        "email": profile.email,
        "family": profile.family,
        "status": "active",
        "authentication": {"type": "subscription_oauth"},
        "config_dir": str(selected_config),
    }
    result: dict[str, Any] = {
        "profile": profile_evidence,
        "session_id": session_id,
        "workspace": str(workspace_real),
        "transcript_store": str(selected_store),
        "transcript_project": str(project_path),
        "transcript": transcript,
        "holders": holder_facts,
        "unknown_holders": [],
        "ambiguous": False,
    }
    # Keep the selected metadata identity in the local computation so a
    # resolver cannot accidentally return a store from another family.  It is
    # deliberately not copied into the public evidence beyond canonical fields.
    if _fold(selected_metadata["family"]) != _fold(profile.family):
        raise ProfileError("profile-mismatch", "profile metadata belongs to another family")
    return result


class ProfileResolver:
    """Resolve an explicitly named profile without making any changes."""

    def __init__(self, env: Optional[Mapping[str, str]] = None) -> None:
        self._env = dict(os.environ if env is None else env)

    @property
    def env(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self._env))

    def _profiles_root(self) -> Path:
        configured = self._env.get("CLAUDE_PROFILES_HOME")
        if not configured:
            home = self._env.get("HOME")
            if not isinstance(home, str) or not home:
                raise ProfileError("invalid", "HOME is not configured for profile storage")
            configured = str(Path(home) / ".claude-profiles")
        home = _path_from_env(configured, self._env)
        return home / "profiles"

    def _manifest_path(self) -> Path:
        override = self._env.get("CLAUDE_PROFILES_MANIFEST")
        if override:
            return _path_from_env(override, self._env)
        xdg = self._env.get("XDG_CONFIG_HOME")
        if not xdg:
            home = self._env.get("HOME")
            if not isinstance(home, str) or not home:
                raise ProfileError("invalid", "HOME is not configured for profile manifest")
            xdg = str(Path(home) / ".config")
        return _path_from_env(xdg, self._env) / "workbenches" / "claude-profiles.json"

    def _find_manifest_entry(self, requested: str, entries: Sequence[Mapping[str, Any]]) -> Optional[dict[str, Any]]:
        matches = [entry for entry in entries if _matches(requested, entry)]
        if len(matches) > 1:
            raise ProfileError("invalid", "profile name or alias is ambiguous")
        return dict(matches[0]) if matches else None

    @staticmethod
    def _ensure_supported(entry: Mapping[str, Any]) -> None:
        status = str(entry.get("status", "")).casefold()
        if status != "active":
            raise ProfileError("unsupported", "profile is inactive or unavailable")
        auth = entry.get("authentication")
        auth_type = auth.get("type") if isinstance(auth, Mapping) else None
        normalized = str(auth_type).casefold().replace("-", "_").replace(" ", "_")
        if normalized in {"setup_token", "setuptoken"}:
            raise ProfileError("unsupported", "setup-token authentication is unsupported")
        if normalized != "subscription_oauth":
            raise ProfileError("unsupported", "profile authentication type is unsupported")

    def _manifest_candidate(
        self, entry: Mapping[str, Any], profiles_root: Path
    ) -> tuple[Path, Path, dict[str, Any]]:
        """Return ``(config_dir, metadata_path, metadata)`` for a manifest entry."""

        # Manifest paths are intentionally interpreted below profiles/ only.
        relative = PurePath(str(entry["profilePath"]))
        exact_dir = profiles_root.joinpath(*relative.parts)

        # An existing path is an explicit operator declaration.  If it is
        # present but not configured, refuse rather than silently selecting a
        # different directory that happens to contain similar metadata.
        if exact_dir.exists() or exact_dir.is_symlink():
            exact_real = _resolved_under(profiles_root, exact_dir)
            if not exact_real.is_dir():
                raise ProfileError("invalid", "profile config directory is not configured")
            exact_metadata = exact_dir / ".profile.json"
            if not exact_metadata.exists() and not exact_metadata.is_symlink():
                raise ProfileError("invalid", "profile config directory is missing metadata")
            config_real, metadata = _candidate_metadata(
                exact_metadata, profiles_root, expected=entry
            )
            return config_real, config_real / ".profile.json", metadata

        # A stale metadata-repository path is recoverable when exactly one
        # existing local config carries the selected canonical identity.
        candidates: list[tuple[Path, Path, dict[str, Any]]] = []
        for metadata_path in _metadata_files(profiles_root):
            try:
                config_real, metadata = _candidate_metadata(
                    metadata_path, profiles_root, expected=entry
                )
            except ProfileError as error:
                # A malformed candidate is not a usable fallback.  For an
                # unrelated profile, continue scanning; for a candidate with
                # matching identity, fail closed with its specific refusal.
                try:
                    probe = _metadata(metadata_path.resolve(strict=True))
                except ProfileError:
                    continue
                if _matches(str(entry["name"]), probe):
                    raise error
                continue
            if _matches(str(entry["name"]), metadata):
                candidates.append((config_real, metadata_path.resolve(strict=True), metadata))

        if len(candidates) > 1:
            raise ProfileError("invalid", "duplicate profile metadata is ambiguous")
        if not candidates:
            raise ProfileError("unknown", "profile config directory or metadata is not configured")
        return candidates[0]

    def _metadata_fallback(
        self,
        requested: str,
        profiles_root: Path,
        manifest: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> ProfileReference:
        candidates: list[tuple[Path, Path, dict[str, Any]]] = []
        for metadata_path in _metadata_files(profiles_root):
            config_real, metadata = _candidate_metadata(metadata_path, profiles_root)
            if _matches(requested, metadata):
                if manifest is not None:
                    represented = [
                        item
                        for item in manifest
                        if _matches(metadata["name"], item)
                    ]
                    if len(represented) > 1:
                        raise ProfileError("invalid", "profile name or alias is ambiguous")
                    if represented:
                        # A local metadata file cannot bypass an inactive or
                        # unsupported manifest entry simply because the
                        # requested alias was absent from that manifest.
                        self._ensure_supported(represented[0])
                candidates.append((config_real, metadata_path.resolve(strict=True), metadata))
        if len(candidates) > 1:
            raise ProfileError("invalid", "duplicate profile metadata is ambiguous")
        if not candidates:
            raise ProfileError("unknown", "profile was not found")
        config_real, metadata_real, metadata = candidates[0]
        relative = config_real.relative_to(profiles_root.resolve(strict=False))
        return ProfileReference(
            name=metadata["name"],
            email=metadata["email"],
            family=metadata["family"],
            config_dir=config_real,
            # Metadata-only fallback cannot prove account authentication or
            # manifest eligibility.  Preserve that uncertainty for the
            # adapter/controller instead of presenting it as an active OAuth
            # profile.
            authentication=MappingProxyType({"type": "unknown"}),
            status="unknown",
            metadata_path=metadata_real,
            aliases=metadata["aliases"],
            profile_path="/".join(relative.parts),
        )

    def resolve(self, name: str) -> ProfileReference:
        if not isinstance(name, str) or not name:
            raise ProfileError("invalid", "profile name is required")

        profiles_root = self._profiles_root()
        manifest = _manifest_entries(self._manifest_path())
        if manifest is not None:
            entry = self._find_manifest_entry(name, manifest)
            if entry is not None:
                # Eligibility is checked before touching the selected config
                # path, so an inactive/setup-token profile cannot influence a
                # running operation or cause any side effect.
                self._ensure_supported(entry)
                config_dir, metadata_path, _metadata_data = self._manifest_candidate(
                    entry, profiles_root
                )
                return ProfileReference(
                    name=entry["name"],
                    email=entry["email"],
                    family=entry["family"],
                    config_dir=config_dir,
                    authentication=entry["authentication"],
                    status=entry["status"],
                    metadata_path=metadata_path,
                    aliases=entry["aliases"],
                    profile_path=entry["profilePath"],
                )

        return self._metadata_fallback(name, profiles_root, manifest=manifest)

    def verify_transcript(
        self,
        profile: ProfileReference,
        session_id: str,
        workspace: str | Path,
    ) -> dict[str, Any]:
        """Return trusted local transcript evidence for a resolved profile.

        The resolver is deliberately consulted again here.  A caller cannot
        turn a hand-built :class:`ProfileReference` (or fields copied from a
        controller request) into profile authority: the current manifest must
        still resolve the same active subscription-OAuth profile and the
        existing config metadata must agree with it.  The remainder of the
        proof is read-only and is performed by ``_verify_transcript``.
        """

        if not isinstance(profile, ProfileReference):
            raise ProfileError("invalid", "transcript verification requires a resolved profile")
        resolved = self.resolve(profile.name)
        supplied_config, _supplied_metadata = _profile_config(profile)
        resolved_config, _resolved_metadata = _profile_config(resolved)
        if supplied_config != resolved_config:
            raise ProfileError("profile-mismatch", "profile config does not match the resolver")
        if (
            _fold(profile.name) != _fold(resolved.name)
            or _fold(profile.email) != _fold(resolved.email)
            or _fold(profile.family) != _fold(resolved.family)
            or str(profile.status).casefold() != str(resolved.status).casefold()
            or str(profile.authentication_type).casefold()
            != str(resolved.authentication_type).casefold()
        ):
            raise ProfileError("profile-mismatch", "profile identity does not match the resolver")
        return _verify_transcript(resolved, session_id, workspace, resolver=self)

    def require_same_family(
        self, source: ProfileReference | str, target: ProfileReference | str
    ) -> ProfileReference:
        if isinstance(source, str):
            source = self.resolve(source)
        if isinstance(target, str):
            target = self.resolve(target)
        if not isinstance(source, ProfileReference) or not isinstance(target, ProfileReference):
            raise ProfileError("invalid", "profile family comparison requires profile references")
        if _fold(source.family) != _fold(target.family):
            raise ProfileError("profile-mismatch", "profiles belong to incompatible storage families")
        return target


def sanitize_environment(
    base_env: Mapping[str, str], profile: ProfileReference
) -> dict[str, str]:
    """Copy ``base_env`` with inherited provider context removed."""

    if not isinstance(base_env, Mapping):
        raise ProfileError("invalid", "environment must be a mapping")
    if not isinstance(profile, ProfileReference):
        raise ProfileError("invalid", "environment requires a profile reference")

    result = dict(base_env)
    for key in tuple(result):
        if not isinstance(key, str):
            continue
        upper = key.upper()
        remove = upper in _AUTH_AND_PROVIDER_ENV
        if not remove:
            # Cover documented provider endpoint/selector spellings while
            # retaining unrelated environment variables.
            remove = (
                (upper.startswith("ANTHROPIC_") and upper.endswith(("_BASE_URL", "_API_URL")))
                or upper.startswith("ANTHROPIC_BEDROCK_")
                or upper.startswith("ANTHROPIC_VERTEX_")
                or upper.startswith("AWS_BEDROCK_")
                or upper.startswith("AWS_ENDPOINT_URL_")
                or upper.startswith("CLAUDE_CODE_BEDROCK_")
                or upper.startswith("CLAUDE_CODE_VERTEX_")
                or upper.startswith("GOOGLE_GENAI_")
                or upper.endswith("_API_BASE_URL")
                or upper in {"API_BASE_URL", "BASE_URL"}
            )
        if remove:
            result.pop(key, None)
    result["CLAUDE_CONFIG_DIR"] = str(profile.config_dir)
    # A launcher-level profile selector is also inherited state.  Set it to
    # the canonical identity rather than allowing an old alias/account name
    # to survive in a child environment.
    result["CLAUDE_PROFILE_NAME"] = profile.name
    return result


def resolve_profile(
    name: str,
    *,
    env: Optional[Mapping[str, str]] = None,
    expected_email: Optional[str] = None,
    expected_family: Optional[str] = None,
) -> ProfileReference:
    """Compatibility function for callers predating :class:`ProfileResolver`."""

    profile = ProfileResolver(env=env).resolve(name)
    if expected_email is not None and profile.email.casefold() != expected_email.casefold():
        raise ProfileError("account-mismatch", "profile account identity does not match")
    if expected_family is not None and profile.family.casefold() != expected_family.casefold():
        raise ProfileError("profile-mismatch", "profile belongs to an incompatible family")
    return profile


def verify_transcript(
    profile: ProfileReference,
    session_id: str,
    workspace: str | Path,
) -> dict[str, Any]:
    """Verify one exact native UUID using only the supplied profile identity.

    Production callers should normally use ``ProfileResolver.verify_transcript``
    so the selected profile is re-resolved against its configured manifest.
    This function is the exact dependency-free boundary for callers that have
    already completed that resolution; it still validates the immutable
    profile object, on-disk metadata, storage family, holder records, and
    transcript path and never trusts caller-supplied authority flags.
    """

    return _verify_transcript(profile, session_id, workspace)


def sanitized_environment(
    profile: ProfileReference, *, environ: Optional[Mapping[str, str]] = None
) -> dict[str, str]:
    """Backward-compatible argument order for the old helper spelling."""

    return sanitize_environment(os.environ if environ is None else environ, profile)
