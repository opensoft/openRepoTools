# SPDX-License-Identifier: Apache-2.0
"""Read-only native lineage workspace adoption assessment coverage."""

from __future__ import annotations

import copy
import contextlib
import json
from pathlib import Path

import pytest

from lane_managed_state import (
    ManagedStateError,
    native_record_marker,
)
from test_lane_managed_lineage_transfer import _seed_source
from test_lane_managed_state import (
    _durable_state_bytes,
    _recovery_arguments,
    _store,
    runtime_socket_path,
)


def _target(source, *, lineage_id="lineage-assessment-target",
            coordinator_session_uuid="coordinator-assessment-target",
            lineage_generation=None):
    target = dict(source)
    target.update({
        "lineage_id": lineage_id,
        "coordinator_session_uuid": coordinator_session_uuid,
        "lineage_generation": (
            source["lineage_generation"] + 1
            if lineage_generation is None else lineage_generation
        ),
    })
    return target


def _journal_events(store):
    path = store.identity.state_root / "claims.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _assess(store, source, target, owner):
    return store.assess_lineage_workspace_adoption(
        source,
        target,
        expected_daemon_id=owner["daemon_id"],
    )


def test_assessment_reports_source_and_target_held_without_authority(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-held",
        daemon_id="daemon-assessment-held",
        lineage_id="lineage-assessment-held-source",
        coordinator_session_uuid="coordinator-assessment-held-source",
    )
    target = _target(source)

    source_result = _assess(store, source, target, owner)
    assert source_result == {
        "status": "source-held",
        "blockers": [],
        "source_matches": 1,
        "target_matches": 0,
    }

    store._write_claims([target])
    target_result = _assess(store, source, target, owner)
    assert target_result == {
        "status": "target-held",
        "blockers": [],
        "source_matches": 0,
        "target_matches": 1,
    }


@pytest.mark.parametrize(
    ("rows", "required_blocker"),
    [
        ("both", "source-and-target-present"),
        ("none", "source-and-target-absent"),
    ],
)
def test_assessment_does_not_infer_from_both_or_neither_claim(
        managed_workspace, tmp_path: Path, rows, required_blocker):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-presence-" + rows,
        daemon_id="daemon-assessment-presence-" + rows,
        lineage_id="lineage-assessment-presence-" + rows,
        coordinator_session_uuid="coordinator-assessment-presence-" + rows,
    )
    target = _target(source, lineage_id="lineage-target-" + rows,
                     coordinator_session_uuid="coordinator-target-" + rows)
    store._write_claims([source, target] if rows == "both" else [])

    result = _assess(store, source, target, owner)
    assert result["status"] == "indeterminate"
    assert required_blocker in result["blockers"]


@pytest.mark.parametrize("changed_side", ["source", "target"])
def test_changed_expected_identity_row_is_indeterminate(
        managed_workspace, tmp_path: Path, changed_side):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-changed-" + changed_side,
        daemon_id="daemon-assessment-changed-" + changed_side,
        lineage_id="lineage-assessment-changed-" + changed_side,
        coordinator_session_uuid="coordinator-assessment-changed-" + changed_side,
    )
    target = _target(source, lineage_id="lineage-target-changed-" + changed_side,
                     coordinator_session_uuid="coordinator-target-changed-" + changed_side)
    changed = dict(source if changed_side == "source" else target)
    changed["parent_read_only"] = not changed["parent_read_only"]
    store._write_claims([changed])

    result = _assess(store, source, target, owner)
    assert result["status"] == "indeterminate"
    assert changed_side + "-changed" in result["blockers"]


@pytest.mark.parametrize("duplicate_side", ["source", "target"])
def test_duplicate_exact_claims_are_indeterminate(
        managed_workspace, tmp_path: Path, duplicate_side):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-duplicate-" + duplicate_side,
        daemon_id="daemon-assessment-duplicate-" + duplicate_side,
        lineage_id="lineage-assessment-duplicate-" + duplicate_side,
        coordinator_session_uuid="coordinator-assessment-duplicate-" + duplicate_side,
    )
    target = _target(source, lineage_id="lineage-target-duplicate-" + duplicate_side,
                     coordinator_session_uuid="coordinator-target-duplicate-" + duplicate_side)
    duplicate = source if duplicate_side == "source" else target
    store._write_claims([duplicate, copy.deepcopy(duplicate)])

    result = _assess(store, source, target, owner)
    assert result["status"] == "indeterminate"
    assert duplicate_side + "-duplicate" in result["blockers"]
    assert result["source_matches"] == (2 if duplicate_side == "source" else 0)
    assert result["target_matches"] == (2 if duplicate_side == "target" else 0)


@pytest.mark.parametrize("collision_side", ["source", "target"])
def test_cross_lane_identity_reuse_blocks_even_on_disjoint_path(
        managed_workspace, tmp_path: Path, collision_side):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-identity-" + collision_side,
        daemon_id="daemon-assessment-identity-" + collision_side,
        lineage_id="lineage-assessment-identity-" + collision_side,
        coordinator_session_uuid="coordinator-assessment-identity-" + collision_side,
    )
    target = _target(source, lineage_id="lineage-target-identity-" + collision_side,
                     coordinator_session_uuid="coordinator-target-identity-" + collision_side)
    other_workspace = (tmp_path / ("other-" + collision_side)).resolve()
    other_workspace.mkdir()
    other = dict(source)
    other.update({
        "lineage_id": (
            source["lineage_id"] if collision_side == "source"
            else target["lineage_id"]
        ),
        "coordinator_session_uuid": (
            "coordinator-other-identity-" + collision_side
        ),
        "lane": "assessment-other-lane-" + collision_side,
        "lane_key": "assessment-other-lane-" + collision_side,
        "workspace": str(other_workspace),
        "lineage_generation": source["lineage_generation"] + 9,
    })
    store._write_claims([source, other])

    result = _assess(store, source, target, owner)
    assert result["status"] == "indeterminate"
    assert (collision_side + "-identity-collision") in result["blockers"]


def test_source_coordinator_identity_reuse_alone_blocks_target_held(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-source-session-reuse",
        daemon_id="daemon-assessment-source-session-reuse",
        lineage_id="lineage-assessment-source-session-reuse",
        coordinator_session_uuid="coordinator-assessment-source-session-reuse",
    )
    target = _target(source,
                     lineage_id="lineage-target-source-session-reuse",
                     coordinator_session_uuid="coordinator-target-source-session-reuse")
    other_workspace = (tmp_path / "other-source-session-reuse").resolve()
    other_workspace.mkdir()
    other = dict(target)
    other.update({
        "lineage_id": "lineage-other-source-session-reuse",
        "coordinator_session_uuid": source["coordinator_session_uuid"],
        "workspace": str(other_workspace),
        "lane": "assessment-other-source-session",
        "lane_key": "assessment-other-source-session",
        "lineage_generation": 23,
    })
    store._write_claims([target, other])

    result = _assess(store, source, target, owner)
    assert result["status"] == "indeterminate"
    assert "source-identity-collision" in result["blockers"]


def test_path_overlap_and_retained_source_child_are_indeterminate(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-path-child",
        daemon_id="daemon-assessment-path-child",
        lineage_id="lineage-assessment-path-child",
        coordinator_session_uuid="coordinator-assessment-path-child",
    )
    target = _target(source, lineage_id="lineage-target-path-child",
                     coordinator_session_uuid="coordinator-target-path-child")
    other = dict(target)
    other.update({
        "lineage_id": "lineage-other-path-child",
        "coordinator_session_uuid": "coordinator-other-path-child",
        "lane": "assessment-other-path",
        "lane_key": "assessment-other-path",
    })
    child_worktree = (tmp_path / "assessment-isolated-child").resolve()
    child_worktree.mkdir()
    store.claim_child_worktree(
        lineage_id=source["lineage_id"],
        coordinator_session_uuid=source["coordinator_session_uuid"],
        owner_generation=owner["generation"],
        lineage_generation=source["lineage_generation"],
        workspace=source["workspace"],
        common_dir=source["common_dir"],
        repository=source["repository"],
        worktree=str(child_worktree),
        agent_id="agent-assessment-child",
        task_id="task-assessment-child",
    )
    store._write_claims([source, other] + [
        claim for claim in store.read_lineage_claims()
        if claim.get("record_kind") == "child-worktree-claim"
    ])

    result = _assess(store, source, target, owner)
    assert result["status"] == "indeterminate"
    assert "path-overlap" in result["blockers"]
    assert "source-child-claim-retained" in result["blockers"]


def test_pinned_owner_and_stale_daemon_never_produce_held_result(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-owner-boundary",
        daemon_id="daemon-assessment-owner-boundary",
        lineage_id="lineage-assessment-owner-boundary",
        coordinator_session_uuid="coordinator-assessment-owner-boundary",
    )
    target = _target(source, lineage_id="lineage-target-owner-boundary",
                     coordinator_session_uuid="coordinator-target-owner-boundary")
    store._write_owner({
        **owner,
        "lineage_id": source["lineage_id"],
        "coordinator_session_uuid": source["coordinator_session_uuid"],
    })
    pinned = _assess(store, source, target, owner)
    assert pinned["status"] == "indeterminate"
    assert "owner-pinned-identity" in pinned["blockers"]

    store._write_owner({**owner, "daemon_id": "daemon-assessment-replaced"})
    with pytest.raises(ManagedStateError) as stale:
        _assess(store, source, target, owner)
    assert stale.value.code == "ownership-conflict"


@pytest.mark.parametrize("owner_boundary", ["mode", "generation"])
def test_owner_mode_or_generation_refuses_before_claim_read(
        managed_workspace, tmp_path: Path, owner_boundary, monkeypatch):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-owner-" + owner_boundary,
        daemon_id="daemon-assessment-owner-" + owner_boundary,
        lineage_id="lineage-assessment-owner-" + owner_boundary,
        coordinator_session_uuid="coordinator-assessment-owner-" + owner_boundary,
    )
    target = _target(
        source,
        lineage_id="lineage-target-owner-" + owner_boundary,
        coordinator_session_uuid="coordinator-target-owner-" + owner_boundary,
    )
    if owner_boundary == "mode":
        store._write_owner({
            "mode": "legacy-lease",
            "pid": 47301,
            "start_token": "assessment-legacy-start",
            "pgid": 47302,
            "lane": owner["lane"],
            "lane_key": owner["lane_key"],
            "host": owner["host"],
            "created_at": owner["created_at"],
        })
        expected_code = "ownership-conflict"
    else:
        replacement_generation = owner["generation"] + 1
        store._write_generation(replacement_generation)
        store._write_owner({**owner, "generation": replacement_generation})
        expected_code = "stale-generation"

    def claims_must_not_be_read():
        raise AssertionError("claim index must not be read after owner refusal")

    monkeypatch.setattr(store, "_load_claims", claims_must_not_be_read)
    with pytest.raises(ManagedStateError) as raised:
        _assess(store, source, target, owner)
    assert raised.value.code == expected_code


def test_pending_recovery_refuses_without_mutating_assessment_inputs(
        managed_workspace, tmp_path: Path, runtime_socket_path, monkeypatch):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-pending-recovery",
        daemon_id="daemon-assessment-pending-recovery",
        lineage_id="lineage-assessment-pending-recovery",
        coordinator_session_uuid="coordinator-assessment-pending-recovery",
    )
    target = _target(source, lineage_id="lineage-target-pending-recovery",
                     coordinator_session_uuid="coordinator-target-pending-recovery")
    runtime = store.register_runtime(
        daemon_id=owner["daemon_id"], generation=owner["generation"],
        pid=47201, start_token="assessment-old-start", pgid=47202,
        process_domain="local", socket_path=runtime_socket_path,
    )
    arguments = _recovery_arguments(
        owner, runtime, runtime_socket_path.with_name("assessment-new.sock"),
        daemon_id="daemon-assessment-new",
        request_id="assessment-pending-recovery-request",
    )
    original_write_owner = store._write_owner

    def fail_after_intent(_record):
        raise ManagedStateError("unsafe-state", "injected owner write failure")

    monkeypatch.setattr(store, "_write_owner", fail_after_intent)
    with pytest.raises(ManagedStateError):
        store.recover_managed_owner(**arguments)
    assert store._load_recovery_intent()["state"] == "pending"
    monkeypatch.setattr(store, "_write_owner", original_write_owner)

    before = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as raised:
        _assess(store, source, target, owner)
    assert raised.value.code == "uncertain-effect"
    assert _durable_state_bytes(store) == before


def test_cold_or_owner_missing_store_refuses_without_provisioning(
        managed_workspace, tmp_path: Path):
    store = _store(managed_workspace, lane="assessment-cold-store")
    workspace = (tmp_path / "assessment-cold-workspace").resolve()
    workspace.mkdir()
    common_dir = str(store.identity.common_dir.resolve())
    source = {
        **native_record_marker("workspace-claim"),
        "state": "active",
        "claim_kind": "workspace",
        "lineage_id": "lineage-assessment-cold-source",
        "coordinator_session_uuid": "coordinator-assessment-cold-source",
        "owner_generation": 1,
        "lineage_generation": 1,
        "lane": "assessment-cold-store",
        "lane_key": "assessment-cold-store",
        "host": store.identity.host,
        "workspace": str(workspace),
        "common_dir": common_dir,
        "repository": str((tmp_path / "assessment-repository").resolve()),
        "parent_read_only": True,
        "claimed_at": 1.0,
    }
    target = _target(
        source,
        lineage_id="lineage-assessment-cold-target",
        coordinator_session_uuid="coordinator-assessment-cold-target",
    )
    before = _durable_state_bytes(store)

    with pytest.raises(ManagedStateError) as raised:
        _assess(store, source, target, {"daemon_id": "daemon-cold"})
    assert raised.value.code == "ownership-conflict"
    assert not store.identity.global_root.exists()
    assert not store.identity.state_root.exists()
    assert _durable_state_bytes(store) == before


def test_assessment_does_not_recreate_owner_deleted_before_lock(
        managed_workspace, tmp_path: Path, monkeypatch):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-lock-race",
        daemon_id="daemon-assessment-lock-race",
        lineage_id="lineage-assessment-lock-race",
        coordinator_session_uuid="coordinator-assessment-lock-race",
    )
    target = _target(
        source,
        lineage_id="lineage-target-lock-race",
        coordinator_session_uuid="coordinator-target-lock-race",
    )
    owner_path = store.identity.state_root / "owner.json"
    claims_path = store.identity.global_root / "claims.json"
    claims_before = claims_path.read_bytes()
    journal_before = _journal_events(store)
    original_lock = store._locked_existing

    @contextlib.contextmanager
    def delete_before_lock(*args, **kwargs):
        owner_path.unlink()
        with original_lock(*args, **kwargs):
            yield

    monkeypatch.setattr(store, "_locked_existing", delete_before_lock)
    with pytest.raises(ManagedStateError) as raised:
        _assess(store, source, target, owner)

    assert raised.value.code == "ownership-conflict"
    assert not owner_path.exists()
    assert claims_path.read_bytes() == claims_before
    assert _journal_events(store) == journal_before


def test_assessment_does_not_create_missing_lock_inode(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-missing-lock",
        daemon_id="daemon-assessment-missing-lock",
        lineage_id="lineage-assessment-missing-lock",
        coordinator_session_uuid="coordinator-assessment-missing-lock",
    )
    target = _target(
        source,
        lineage_id="lineage-target-missing-lock",
        coordinator_session_uuid="coordinator-target-missing-lock",
    )
    lock_path = store.identity.global_root / "state.lock"
    owner_path = store.identity.state_root / "owner.json"
    lock_path.unlink()
    before = _durable_state_bytes(store)

    with pytest.raises(ManagedStateError) as raised:
        _assess(store, source, target, owner)

    assert raised.value.code == "unsafe-state"
    assert not lock_path.exists()
    assert owner_path.exists()
    assert _durable_state_bytes(store) == before


def test_malformed_claim_index_refuses_without_writing_or_journaling(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-corrupt-index",
        daemon_id="daemon-assessment-corrupt-index",
        lineage_id="lineage-assessment-corrupt-index",
        coordinator_session_uuid="coordinator-assessment-corrupt-index",
    )
    target = _target(source, lineage_id="lineage-target-corrupt-index",
                     coordinator_session_uuid="coordinator-target-corrupt-index")
    store._write_claims([{"record_kind": "workspace-claim"}])
    before = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError) as raised:
        _assess(store, source, target, owner)
    assert raised.value.code in {"invalid", "schema-mismatch", "unsupported"}
    assert _durable_state_bytes(store) == before


@pytest.mark.parametrize(
    "mutator",
    [
        lambda source, target: (dict(source, owner_generation=True), target),
        lambda source, target: (source, dict(target, claimed_at=1)),
        lambda source, target: (source, dict(target, parent_read_only=False)),
    ],
)
def test_invalid_strict_pair_refuses_without_state_change(
        managed_workspace, tmp_path: Path, mutator):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-invalid-pair-" + str(abs(hash(mutator))),
        daemon_id="daemon-assessment-invalid-pair",
        lineage_id="lineage-assessment-invalid-pair",
        coordinator_session_uuid="coordinator-assessment-invalid-pair",
    )
    target = _target(source, lineage_id="lineage-target-invalid-pair",
                     coordinator_session_uuid="coordinator-target-invalid-pair")
    bad_source, bad_target = mutator(source, target)
    before = _durable_state_bytes(store)
    with pytest.raises(ManagedStateError):
        _assess(store, bad_source, bad_target, owner)
    assert _durable_state_bytes(store) == before


def test_repeated_assessment_is_byte_identical_including_claim_journal(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="assessment-repeat",
        daemon_id="daemon-assessment-repeat",
        lineage_id="lineage-assessment-repeat",
        coordinator_session_uuid="coordinator-assessment-repeat",
    )
    target = _target(source, lineage_id="lineage-target-repeat",
                     coordinator_session_uuid="coordinator-target-repeat")
    before = _durable_state_bytes(store)
    journal_before = _journal_events(store)
    first = _assess(store, source, target, owner)
    middle = _durable_state_bytes(store)
    second = _assess(store, source, target, owner)
    after = _durable_state_bytes(store)

    assert first == second
    assert first["status"] == "source-held"
    assert before == middle == after
    assert _journal_events(store) == journal_before
