# SPDX-License-Identifier: Apache-2.0
"""Model-free, offline native-history integrity checks.

Structural calibration only: the two saved pinned-CLI sidecars in the local
Sept 25 evidence corpus contain ``toolUseId`` and no ``parentAgentId``;
their parent JSONLs each contain one matching Agent tool use.  The saved
parent/child JSONLs have consistent top-level session/agent identities and
newline-terminated records.  Message bodies are neither fixtures nor proof.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
from pathlib import Path

import pytest

import lane_managed_cli_history as history
from lane_managed_state import ManagedStateError


PARENT = "00000000-0000-4000-8000-000000000001"
OTHER = "00000000-0000-4000-8000-000000000002"


def _line(value: dict) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode() + b"\n"


class _Resolver:
    def __init__(self, store: Path, project: Path):
        self.store = store
        self.project = project

    def resolve(self, name):
        assert name == "team-a"
        return name

    def verify_transcript(self, profile, parent, cwd):
        assert profile == "team-a"
        assert parent == PARENT
        return {"transcript": {"exists": True, "store": str(self.store),
                               "project": str(self.project),
                               "path": str(self.project / (parent + ".jsonl"))}}


class _Ledger:
    def __init__(self, claim):
        self.claim = claim
        self.state = {"operations": {"op": {
            "source_runtime_incarnation": "runtime-1", "parent_uuid": PARENT,
            "source_claim_generation": 1, "source_exclusion": {"complete": True},
            "source_profile_ref": "team-a", "worktree_ids": [claim["resource_id"]],
            "owner_generation": 1, "lineage_id": "lineage", "lineage_generation": 1,
        }}, "reservations": {claim["resource_id"]: "job-1"},
            "observation_watermark": 42}

    @contextlib.contextmanager
    def _locked(self):
        yield object()

    def _load(self, _owner):
        return self.state

    def _registered_worktrees(self, *_args):
        return [dict(self.claim)]


@pytest.fixture
def case(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    common = subprocess.run(["git", "-C", str(workspace), "rev-parse",
                             "--path-format=absolute", "--git-common-dir"],
                            check=True, capture_output=True, text=True).stdout.strip()
    store = tmp_path / "projects"
    project = store / "-canonical-workspace"
    project.mkdir(parents=True)
    parent = project / (PARENT + ".jsonl")
    parent.write_bytes(_line({"type": "user", "sessionId": PARENT,
                              "message": {"content": "saved context"}}))
    claim = {"resource_id": "workspace-claim:one", "claim_kind": "workspace-claim",
             "claim_digest": "1" * 64, "path": str(workspace),
             "repository": common, "common_dir": str(tmp_path / "wip-state" / ".git")}
    ledger = _Ledger(claim)
    binding = {"source_runtime_incarnation": "runtime-1", "parent_uuid": PARENT,
               "source_claim_generation": 1, "lineage_id": "lineage", "lineage_generation": 1,
               "owner_generation": 1, "worktree_ids": [claim["resource_id"]],
               "source_profile_ref": "team-a", "source_cwd": str(workspace)}
    witness = history.ClaudeCliHistoryWitness(ledger, _Resolver(store, project))
    return witness, binding, parent, project, ledger, workspace


def _child(project: Path, *, session: str = PARENT, tool: str = "toolu_agent"):
    agent = "abc123"
    root = project / PARENT / "subagents"
    root.mkdir(parents=True, exist_ok=True)
    (root / ("agent-" + agent + ".meta.json")).write_bytes(
        _line({"toolUseId": tool}))
    (root / ("agent-" + agent + ".jsonl")).write_bytes(
        _line({"type": "assistant", "sessionId": session, "agentId": agent,
               "message": {"content": "saved child response"}}))


def _parent_with_agent(parent: Path):
    with parent.open("ab") as output:
        output.write(_line({"type": "assistant", "sessionId": PARENT,
                            "message": {"content": [{"type": "tool_use",
                                                    "name": "Agent", "id": "toolu_agent"}]}}))


def test_exact_parent_and_native_child_are_bound_without_completion_claim(case, monkeypatch):
    witness, binding, parent, project, ledger, workspace = case
    monkeypatch.setattr(history.secrets, "token_hex", lambda _count: "fixed-witness-id")
    _parent_with_agent(parent)
    _child(project)
    original_inventory = witness._worktrees(binding)[0][0]["dirty_inventory_sha256"]
    first = witness.history_manifest(binding)
    assert first["complete"] is True
    assert first["parent_uuid"] == PARENT
    assert first["observation_watermark"] > ledger.state["observation_watermark"]
    assert first["manifest_digest"] == witness.history_manifest(binding)["manifest_digest"]
    (workspace / "saved-edit.txt").write_text("unsaved work remains visible")
    changed_inventory = witness._worktrees(binding)[0][0]["dirty_inventory_sha256"]
    changed = witness.history_manifest(binding)
    assert changed_inventory != original_inventory
    assert changed["worktree_manifest_digest"] == first["worktree_manifest_digest"]
    assert changed["witness_digest"] != first["witness_digest"]
    assert (workspace / "saved-edit.txt").read_text() == "unsaved work remains visible"


@pytest.mark.parametrize("change", [
    "wrong-parent", "partial-tail", "duplicate-key", "orphan-agent",
    "wrong-child", "wrong-link", "linked-child", "repeated-agent",
])
def test_incomplete_or_conflicting_history_refuses(case, change):
    witness, binding, parent, project, _ledger, _workspace = case
    if change == "wrong-parent":
        parent.write_bytes(_line({"type": "user", "sessionId": OTHER}))
    elif change == "partial-tail":
        parent.write_bytes(parent.read_bytes() + b'{"type":"assistant"')
    elif change == "duplicate-key":
        parent.write_bytes(b'{"sessionId":"' + PARENT.encode() + b'","sessionId":"' +
                           PARENT.encode() + b'"}\n')
    elif change == "repeated-agent":
        _parent_with_agent(parent)
        _parent_with_agent(parent)
        _child(project)
    elif change == "orphan-agent":
        _parent_with_agent(parent)
    else:
        _parent_with_agent(parent)
        _child(project, session=OTHER if change == "wrong-child" else PARENT,
               tool="other" if change == "wrong-link" else "toolu_agent")
        if change == "linked-child":
            child = project / PARENT / "subagents" / "agent-abc123.jsonl"
            child.unlink()
            child.symlink_to(parent)
    with pytest.raises(ManagedStateError):
        witness.history_manifest(binding)


def test_sibling_parent_history_is_not_substituted(case):
    witness, binding, parent, project, _ledger, _workspace = case
    parent.unlink()
    (project / (OTHER + ".jsonl")).write_bytes(_line({"sessionId": OTHER}))
    with pytest.raises(ManagedStateError):
        witness.history_manifest(binding)


def test_registered_project_common_directory_must_match_claim_repository(case):
    witness, binding, _parent, _project, ledger, workspace = case
    ledger.claim["repository"] = str(workspace / "other-git-common")
    with pytest.raises(ManagedStateError, match="project Git identity changed"):
        witness._worktrees(binding)


def test_shared_watermark_allocator_uses_ledger_floor(case):
    witness, binding, _parent, _project, ledger, _workspace = case
    floor = 10**30
    ledger.state["observation_watermark"] = floor
    calls = []

    def next_watermark(value):
        calls.append(value)
        return max(value, floor) + len(calls)

    shared = history.ClaudeCliHistoryWitness(
        ledger, witness.profile_resolver, next_watermark=next_watermark)
    assert shared.history_manifest(binding)["observation_watermark"] == floor + 1
    assert shared.history_manifest(binding)["observation_watermark"] == floor + 2
    assert calls == [floor, floor]


def test_changed_file_during_read_refuses(case, monkeypatch):
    witness, binding, parent, _project, _ledger, _workspace = case
    original = history.os.read
    changed = False

    def racing_read(fd, count):
        nonlocal changed
        data = original(fd, count)
        if (data and not changed and
                (os.fstat(fd).st_dev, os.fstat(fd).st_ino) ==
                (parent.stat().st_dev, parent.stat().st_ino)):
            changed = True
            with parent.open("ab") as output:
                output.write(_line({"sessionId": PARENT}))
        return data

    monkeypatch.setattr(history.os, "read", racing_read)
    with pytest.raises(ManagedStateError):
        witness.history_manifest(binding)
