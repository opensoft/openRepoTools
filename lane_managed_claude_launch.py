# SPDX-License-Identifier: Apache-2.0
"""Private, fail-closed launch policy for the managed Claude CLI source.

The returned arguments are data for a future trusted launcher. This module
does not start Claude or enable the managed account-swap capability.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any, Dict, Mapping

from lane_managed_state import ManagedStateError


REQUIRED_ENV = (
    "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1",
    "CLAUDE_CODE_DISABLE_AGENT_VIEW=1",
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
# The initial capability exposes ordinary file tools and foreground children.
# Shell execution is available only through the separately admitted L1 broker.
_BUILTINS = ("Read", "Edit", "Write", "NotebookEdit", "Glob", "Grep", "Agent", "SendMessage")
_MCP_PATH = "/run/claude/profile/managed-mcp.json"
_SETTINGS_PATH = "/run/claude/profile/managed-settings.json"
REVIEWED_CLI_VERSION = "2.1.283"


def _invalid(message: str) -> None:
    raise ManagedStateError("unsupported", message)


def build_launch(*, parent_uuid: str, mcp_config_digest: str,
                 settings_digest: str) -> Dict[str, Any]:
    """Return one exact-parent foreground CLI launch with a bounded tool set."""
    try:
        if str(uuid.UUID(parent_uuid)) != parent_uuid:
            raise ValueError("noncanonical UUID")
    except (TypeError, AttributeError, ValueError):
        _invalid("Claude launch requires an exact canonical parent UUID")
    for value, name in ((mcp_config_digest, "MCP configuration"),
                        (settings_digest, "settings")):
        if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
            _invalid("Claude %s digest is missing or malformed" % name)
    launch = {
        "parent_uuid": parent_uuid,
        "argv": [
            "claude", "--resume", parent_uuid,
            "--restricted",
            "--tools", ",".join(_BUILTINS),
            "--disallowedTools", "Bash", "PowerShell",
            "--settings", _SETTINGS_PATH,
            "--strict-mcp-config", "--mcp-config", _MCP_PATH,
        ],
        "environment": list(REQUIRED_ENV),
        "mcp_config_path": _MCP_PATH,
        "settings_path": _SETTINGS_PATH,
        "mcp_config_digest": mcp_config_digest,
        "settings_digest": settings_digest,
        "background_policy": "foreground-only-v1",
        "cli_version": REVIEWED_CLI_VERSION,
    }
    return launch


def normalize_launch(value: Mapping[str, Any]) -> Dict[str, Any]:
    """Refuse modified tool, background, parent or MCP launch properties."""
    if not isinstance(value, Mapping) or set(value) != {
            "parent_uuid", "argv", "environment", "mcp_config_path",
            "mcp_config_digest", "settings_path", "settings_digest", "background_policy",
            "cli_version"}:
        _invalid("Claude launch manifest has missing or unknown fields")
    expected = build_launch(
        parent_uuid=value["parent_uuid"],
        mcp_config_digest=value["mcp_config_digest"],
        settings_digest=value["settings_digest"],
    )
    if dict(value) != expected:
        _invalid("Claude launch differs from the admitted foreground tool policy")
    return expected


def launch_digest(value: Mapping[str, Any]) -> str:
    normalized = normalize_launch(value)
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
