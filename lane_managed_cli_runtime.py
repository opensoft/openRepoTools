# SPDX-License-Identifier: Apache-2.0
"""Immutable, per-runtime Claude CLI launch material for a shared container.

The Docker-source candidate retains its earlier manifest schema.  This module
is a separate shared-session schema; it never writes a profile's settings or a
global Claude configuration file.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from lane_managed_claude_launch import REQUIRED_ENV, REVIEWED_CLI_VERSION
from lane_managed_state import ManagedStateError


SCHEMA = "claude-cli-shared-session-launch-v1"
MODEL_SCHEMA = "claude-cli-shared-session-launch-v2"
SUPPORTED_MODEL_SELECTIONS = ("sonnet",)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_BUILTINS = ("Read", "Glob", "Grep", "Edit", "Write", "NotebookEdit", "Agent", "SendMessage")
_SYSTEM_INSTRUCTIONS = (
    "This is a managed shared-container lane. Native Edit, Write and NotebookEdit "
    "are available. Run long-running and external commands only through the lane-jobs "
    "MCP tools; native Bash and PowerShell are unavailable. Keep each returned job ID "
    "and retrieve its status/output on "
    "this session or a later resume. Use local-worktree effect scope only for "
    "commands whose effects stay in the registered worktree; external effects "
    "require separate reconciliation. SendMessage may continue only a native child "
    "of this parent. Native background tasks and agent view are disabled. "
    "The user's literal /swap is handled by the owning terminal; do not interpret it as a task."
)
_SAFE_INHERITED = frozenset({
    "HOME", "PATH", "TERM", "LANG", "LC_ALL", "TZ", "USER", "LOGNAME",
    "SHELL", "TMPDIR", "COLORTERM", "NO_COLOR",
})


def _fail(message: str) -> None:
    raise ManagedStateError("unsupported", message)


def _bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8") + b"\n"


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_uuid(value: str, label: str) -> str:
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError("not canonical")
    except (TypeError, ValueError, AttributeError):
        _fail("%s must be a canonical UUID" % label)
    return value


def _real_directory(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink():
        _fail("%s must be an absolute real directory" % label)
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        _fail("%s is unavailable" % label)
    if resolved != path or not resolved.is_dir():
        _fail("%s must be a canonical real directory" % label)
    return resolved


def _private_directory(value: str, label: str) -> Path:
    path = _real_directory(value, label)
    if path.stat().st_mode & 0o077:
        _fail("%s must be owner-private" % label)
    return path


def _write_exclusive(path: Path, data: bytes) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _fsync_directory(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _executable(value: str) -> tuple[str, str]:
    candidate = shutil.which(value)
    if candidate is None:
        _fail("reviewed Claude executable is unavailable")
    path = Path(candidate).resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        _fail("reviewed Claude executable is not executable")
    try:
        result = subprocess.run([str(path), "--version"], check=True,
                                capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        _fail("Claude CLI version could not be verified")
    if result.stdout.strip() != REVIEWED_CLI_VERSION + " (Claude Code)":
        _fail("Claude CLI version is not the reviewed version")
    return str(path), _sha(path.read_bytes())


def create_runtime_launch(*, root: str, runtime_id: str, parent_uuid: str,
                          profile_ref: str, profile_config_dir: str, session_name: str,
                          cwd: str, mcp_bridge_module: str, custodian_dir: str,
                          job_socket: str, job_credential_file: str,
                          launch_mode: str = "resume",
                          claude_executable: str = "claude",
                          model: str | None = None,
                          inherited_environment: Mapping[str, str] | None = None,
                          settings: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Create one immutable launch bundle by exclusive writes under a private root.

    ``profile_config_dir`` must already exist.  The builder never creates or
    edits that profile and never copies its credential bytes.  The caller must
    validate profile/account policy before using this bundle.
    """
    root_path = _private_directory(root, "runtime root")
    runtime_id = _canonical_uuid(runtime_id, "runtime ID")
    parent_uuid = _canonical_uuid(parent_uuid, "parent UUID")
    if launch_mode not in {"fresh", "resume"}:
        _fail("Claude source launch mode is unsupported")
    if model is not None and (not isinstance(model, str) or model not in SUPPORTED_MODEL_SELECTIONS):
        _fail("Claude model selection is unsupported")
    if not isinstance(profile_ref, str) or not profile_ref or len(profile_ref) > 128:
        _fail("profile reference is malformed")
    if not isinstance(session_name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", session_name):
        _fail("managed lane session name is malformed")
    profile_dir = _real_directory(profile_config_dir, "profile config")
    cwd_path = _real_directory(cwd, "working directory")
    if not isinstance(mcp_bridge_module, str) or not Path(mcp_bridge_module).is_file():
        _fail("MCP bridge module is unavailable")
    bridge_path = str(Path(mcp_bridge_module).resolve(strict=True))
    observer = Path(__file__).with_name("lane-managed-cli").resolve(strict=True)
    if not observer.is_file() or not os.access(observer, os.X_OK):
        _fail("managed CLI hook observer is unavailable")
    custodian_path = Path(custodian_dir)
    if (not custodian_path.is_absolute() or custodian_path.is_symlink() or
            not custodian_path.parent.is_dir() or
            custodian_path.parent.stat().st_mode & 0o077):
        _fail("custodian hook path must be under an owner-private directory")
    if (not Path(job_socket).is_absolute() or not Path(job_credential_file).is_absolute() or
            not Path(job_credential_file).is_file()):
        _fail("job endpoint and credential paths must be absolute and present")
    if Path(job_credential_file).is_symlink() or Path(job_credential_file).stat().st_mode & 0o077:
        _fail("job credential file must be owner-private")
    cli_path, cli_digest = _executable(claude_executable)
    if settings is not None:
        # The policy-bearing settings are constructed here, not supplied by a
        # caller or copied from a mutable profile.
        _fail("caller-supplied Claude settings are unsupported")
    runtime_dir = root_path / runtime_id
    try:
        runtime_dir.mkdir(mode=0o700)
    except FileExistsError:
        _fail("runtime launch ID already exists; never overwrite it")
    try:
        settings_path = runtime_dir / "settings.json"
        mcp_path = runtime_dir / "mcp.json"
        hook = {"type": "command", "command": sys.executable,
                "args": [str(observer), "hook-observe", str(custodian_path)],
                "timeout": 10}
        settings_value = {
            "permissions": {
                "defaultMode": "dontAsk",
                "allow": [*_BUILTINS, "mcp__lane-jobs__*"],
                "deny": ["Bash", "PowerShell"],
            },
            "enableAllProjectMcpServers": False,
            "hooks": {event: [{"hooks": [hook]}]
                      for event in ("SessionStart", "UserPromptSubmit", "Stop", "StopFailure")},
        }
        mcp_value = {"mcpServers": {"lane-jobs": {
            "command": sys.executable,
            "args": [bridge_path, "mcp", job_socket, job_credential_file],
        }}}
        settings_bytes = _bytes(settings_value)
        mcp_bytes = _bytes(mcp_value)
        _write_exclusive(settings_path, settings_bytes)
        _write_exclusive(mcp_path, mcp_bytes)
        _fsync_directory(runtime_dir)
        inherited = dict(os.environ if inherited_environment is None else inherited_environment)
        environment = {key: value for key, value in inherited.items()
                       if key in _SAFE_INHERITED and isinstance(value, str)}
        environment.update({
            "CLAUDE_CONFIG_DIR": str(profile_dir),
            "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1",
            "CLAUDE_CODE_DISABLE_AGENT_VIEW": "1",
            "CLAUDE_CODE_HARBOR_KITE": "0",
            "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "0",
            "DISABLE_UPDATES": "1",
            "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
        })
        argv = [cli_path]
        if model is not None:
            argv.extend(("--model", model))
        argv.extend(("--session-id" if launch_mode == "fresh" else "--resume",
                parent_uuid, "--name", session_name, "--restricted",
                "--tools", ",".join(_BUILTINS),
                "--disallowedTools", "Bash", "PowerShell",
                "--settings", str(settings_path), "--strict-mcp-config",
                "--mcp-config", str(mcp_path),
                "--append-system-prompt", _SYSTEM_INSTRUCTIONS))
        manifest = {
            "schema": MODEL_SCHEMA if model is not None else SCHEMA,
            "runtime_id": runtime_id, "parent_uuid": parent_uuid,
            "session_name": session_name,
            "launch_mode": launch_mode,
            "profile_ref": profile_ref, "profile_config_dir": str(profile_dir),
            "cwd": str(cwd_path), "cli_executable": cli_path,
            "cli_executable_digest": cli_digest,
            "cli_version": REVIEWED_CLI_VERSION,
            "argv": argv,
            "environment": environment,
            "settings_path": str(settings_path), "settings_digest": _sha(settings_bytes),
            "mcp_path": str(mcp_path), "mcp_digest": _sha(mcp_bytes),
            "job_credential_path": job_credential_file,
            "job_credential_digest": _sha(Path(job_credential_file).read_bytes()),
            "mcp_bridge_digest": _sha(Path(bridge_path).read_bytes()),
            "hook_observer_path": str(observer),
            "hook_observer_digest": _sha(observer.read_bytes()),
            "custodian_dir": str(custodian_path),
            "background_policy": list(REQUIRED_ENV),
        }
        if model is not None:
            manifest["model"] = model
        _write_exclusive(runtime_dir / "manifest.json", _bytes(manifest))
        _fsync_directory(runtime_dir)
        return manifest
    except BaseException:
        # A partially created directory is evidence of uncertainty and is
        # deliberately retained for the caller to inspect, never reused.
        raise


def validate_runtime_launch(value: Mapping[str, Any]) -> Dict[str, Any]:
    """Recheck immutable file bytes and the pinned CLI before any spawn."""
    if not isinstance(value, Mapping) or value.get("schema") not in {SCHEMA, MODEL_SCHEMA}:
        _fail("shared-session launch manifest schema is unsupported")
    schema = value["schema"]
    required = {"schema", "runtime_id", "parent_uuid", "session_name",
                "launch_mode", "profile_ref",
                "profile_config_dir", "cwd", "cli_executable",
                "cli_executable_digest", "cli_version", "argv", "environment",
                "settings_path", "settings_digest", "mcp_path", "mcp_digest",
                "job_credential_path", "job_credential_digest", "mcp_bridge_digest",
                "hook_observer_path", "hook_observer_digest", "custodian_dir",
                "background_policy"}
    if schema == MODEL_SCHEMA:
        required.add("model")
    if set(value) != required:
        _fail("shared-session launch manifest fields changed")
    model = value.get("model") if schema == MODEL_SCHEMA else None
    if schema == MODEL_SCHEMA and (not isinstance(model, str) or
                                   model not in SUPPORTED_MODEL_SELECTIONS):
        _fail("Claude model selection changed")
    runtime_id = _canonical_uuid(value.get("runtime_id"), "runtime ID")
    parent_uuid = _canonical_uuid(value.get("parent_uuid"), "parent UUID")
    session_name = value.get("session_name")
    if not isinstance(session_name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", session_name):
        _fail("managed lane session name changed")
    settings_path = Path(value.get("settings_path", ""))
    mcp_path = Path(value.get("mcp_path", ""))
    manifest_path = settings_path.parent / "manifest.json"
    if (settings_path.parent.name != runtime_id or mcp_path.parent != settings_path.parent or
            settings_path.is_symlink() or mcp_path.is_symlink() or
            not settings_path.is_file() or not mcp_path.is_file() or
            not manifest_path.is_file()):
        _fail("runtime-specific launch files are missing or aliased")
    disk = json.loads(manifest_path.read_bytes())
    if disk != dict(value):
        _fail("runtime launch manifest changed")
    if (_sha(settings_path.read_bytes()) != value.get("settings_digest") or
            _sha(mcp_path.read_bytes()) != value.get("mcp_digest")):
        _fail("runtime-specific settings or MCP bytes changed")
    observer = Path(value.get("hook_observer_path", ""))
    custodian_path = Path(value.get("custodian_dir", ""))
    if (not observer.is_file() or observer.is_symlink() or
            _sha(observer.read_bytes()) != value.get("hook_observer_digest") or
            not custodian_path.is_absolute() or custodian_path.is_symlink() or
            not custodian_path.parent.is_dir() or
            custodian_path.parent.stat().st_mode & 0o077):
        _fail("managed CLI hook binding changed")
    hook = {"type": "command", "command": sys.executable,
            "args": [str(observer), "hook-observe", str(custodian_path)],
            "timeout": 10}
    expected_settings = {
        "permissions": {
            "defaultMode": "dontAsk",
            "allow": [*_BUILTINS, "mcp__lane-jobs__*"],
            "deny": ["Bash", "PowerShell"],
        },
        "enableAllProjectMcpServers": False,
        "hooks": {event: [{"hooks": [hook]}]
                  for event in ("SessionStart", "UserPromptSubmit", "Stop", "StopFailure")},
    }
    if settings_path.read_bytes() != _bytes(expected_settings):
        _fail("runtime-specific settings policy changed")
    try:
        mcp = json.loads(mcp_path.read_bytes())
        job_server = mcp["mcpServers"]["lane-jobs"]
        bridge = Path(job_server["args"][0])
        credential = Path(value["job_credential_path"])
        if (set(mcp) != {"mcpServers"} or set(mcp["mcpServers"]) != {"lane-jobs"} or
                set(job_server) != {"command", "args"} or
                job_server["command"] != sys.executable or
                job_server["args"][1] != "mcp" or
                job_server["args"][3] != str(credential) or
                len(job_server["args"]) != 4 or
                not bridge.is_file() or not credential.is_file() or
                bridge.is_symlink() or credential.is_symlink() or
                _sha(bridge.read_bytes()) != value["mcp_bridge_digest"] or
                _sha(credential.read_bytes()) != value["job_credential_digest"]):
            _fail("job MCP or scoped credential changed")
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        _fail("job MCP configuration is malformed")
    cli = Path(value.get("cli_executable", ""))
    if not cli.is_file() or _sha(cli.read_bytes()) != value.get("cli_executable_digest"):
        _fail("reviewed Claude executable changed")
    if value.get("cli_version") != REVIEWED_CLI_VERSION:
        _fail("Claude CLI version is not reviewed")
    mode = value.get("launch_mode")
    if mode not in {"fresh", "resume"}:
        _fail("Claude launch mode changed")
    expected_argv = [str(cli)]
    if model is not None:
        expected_argv.extend(("--model", model))
    expected_argv.extend(("--session-id" if mode == "fresh" else "--resume",
                     parent_uuid, "--name", session_name, "--restricted",
                     "--tools", ",".join(_BUILTINS),
                     "--disallowedTools", "Bash", "PowerShell",
                     "--settings", str(settings_path), "--strict-mcp-config",
                     "--mcp-config", str(mcp_path),
                     "--append-system-prompt", _SYSTEM_INSTRUCTIONS))
    if value.get("argv") != expected_argv or value.get("background_policy") != list(REQUIRED_ENV):
        _fail("Claude foreground launch policy changed")
    env = value.get("environment")
    if (not isinstance(env, dict) or
            set(env) - (_SAFE_INHERITED | {"CLAUDE_CONFIG_DIR",
                                              "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS",
                                              "CLAUDE_CODE_DISABLE_AGENT_VIEW",
                                              "CLAUDE_CODE_HARBOR_KITE",
                                              "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS",
                                              "DISABLE_UPDATES",
                                              "ENABLE_CLAUDEAI_MCP_SERVERS"}) or
            env.get("CLAUDE_CODE_DISABLE_BACKGROUND_TASKS") != "1" or
            env.get("CLAUDE_CODE_DISABLE_AGENT_VIEW") != "1" or
            env.get("CLAUDE_CODE_HARBOR_KITE") != "0" or
            env.get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") != "0" or
            env.get("DISABLE_UPDATES") != "1" or
            env.get("ENABLE_CLAUDEAI_MCP_SERVERS") != "false" or
            env.get("CLAUDE_CONFIG_DIR") != value.get("profile_config_dir")):
        _fail("effective per-runtime environment changed")
    _real_directory(value["profile_config_dir"], "profile config")
    _real_directory(value["cwd"], "working directory")
    return dict(value)


def runtime_launch_digest(value: Mapping[str, Any]) -> str:
    return _sha(_bytes(validate_runtime_launch(value)))
