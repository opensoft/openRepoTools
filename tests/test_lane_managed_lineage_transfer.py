# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for the bounded internal lineage-claim CAS."""

from __future__ import annotations

import copy
import json
import multiprocessing
import os
from pathlib import Path

import pytest

from lane_managed_state import (
    ManagedStateError,
    ManagedStateStore,
    resolve_workspace,
)
from test_lane_managed_state import (
    _recovery_arguments,
    _recovery_proof,
    _store,
    runtime_socket_path,
)


def _seed_source(managed_workspace, tmp_path: Path, *, lane: str = "build",
                 daemon_id: str = "daemon-transfer-source",
                 lineage_id: str = "lineage-transfer-source",
                 coordinator_session_uuid: str = "coordinator-transfer-source"):
    store = _store(managed_workspace, lane=lane)
    owner = store.enroll_managed(daemon_id=daemon_id)
    workspace = (tmp_path / (lane + "-transfer-workspace")).resolve()
    workspace.mkdir()
    claim = store.claim_lineage_workspace(
        lineage_id=lineage_id,
        owner_generation=owner["generation"],
        lineage_generation=1,
        workspace=str(workspace),
        common_dir=str(store.identity.common_dir.resolve()),
        repository=str(managed_workspace.project.resolve()),
        parent_read_only=True,
        coordinator_session_uuid=coordinator_session_uuid,
    )
    return store, owner, claim


def _transfer_arguments(claim, owner, *, lineage_id="lineage-transfer-target",
                        coordinator_session_uuid="coordinator-transfer-target",
                        lineage_generation=None):
    return {
        "target_lineage_id": lineage_id,
        "target_coordinator_session_uuid": coordinator_session_uuid,
        "target_lineage_generation": (
            claim["lineage_generation"] + 1
            if lineage_generation is None else lineage_generation
        ),
        "expected_daemon_id": owner["daemon_id"],
        "authoritative": True,
    }


def _claims_bytes(store):
    return (store.identity.global_root / "claims.json").read_bytes()


def _journal_events(store):
    path = store.identity.state_root / "claims.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_transfer_is_one_locked_atomic_index_replacement_and_preserves_unrelated_claim(
        managed_workspace, tmp_path: Path, monkeypatch):
    store, owner, source = _seed_source(managed_workspace, tmp_path)
    other_store, other_owner, other = _seed_source(
        managed_workspace, tmp_path, lane="transfer-other",
        daemon_id="daemon-transfer-other", lineage_id="lineage-transfer-other",
        coordinator_session_uuid="coordinator-transfer-other",
    )
    assert other_owner["generation"] == 1

    owner_bytes = (store.identity.state_root / "owner.json").read_bytes()
    generation_bytes = (store.identity.state_root / "generation.json").read_bytes()
    writes = []
    original_write = store._write_claims

    def observe_write(claims):
        writes.append(copy.deepcopy(claims))
        # The observer runs before the one atomic replacement, while the
        # exclusive lock is still held.  There is no release-then-claim gap.
        assert store.read_lineage_claims() == [source, other]
        return original_write(claims)

    monkeypatch.setattr(store, "_write_claims", observe_write)
    target = store.transfer_lineage_workspace_claim(
        source, **_transfer_arguments(source, owner),
    )

    assert len(writes) == 1
    assert len(writes[0]) == 2
    assert target["lineage_id"] == "lineage-transfer-target"
    assert target["coordinator_session_uuid"] == "coordinator-transfer-target"
    assert target["lineage_generation"] == source["lineage_generation"] + 1
    assert set(target) == set(source)
    assert {
        field for field in source if source[field] != target[field]
    } == {"lineage_id", "coordinator_session_uuid", "lineage_generation"}
    assert target["workspace"] == source["workspace"]
    assert target["repository"] == source["repository"]
    assert target["common_dir"] == source["common_dir"]
    assert target["parent_read_only"] == source["parent_read_only"]
    assert target["owner_generation"] == source["owner_generation"]

    final_claims = store.read_lineage_claims()
    assert target in final_claims
    assert source not in final_claims
    assert other in final_claims
    assert (store.identity.state_root / "owner.json").read_bytes() == owner_bytes
    assert (store.identity.state_root / "generation.json").read_bytes() == generation_bytes

    transfer_events = [
        event for event in _journal_events(store)
        if event.get("event", "").startswith("native-lineage-claim-transfer-")
    ]
    assert [event["event"] for event in transfer_events] == [
        "native-lineage-claim-transfer-intent",
        "native-lineage-claim-transfer-result",
    ]
    assert transfer_events[0]["source"]["lineage_id"] == source["lineage_id"]
    assert transfer_events[0]["target"]["lineage_id"] == target["lineage_id"]
    assert transfer_events[1]["status"] == "complete"
    assert other_store.read_lineage_claims() == final_claims


def test_transfer_requires_authoritative_proof_and_valid_next_target(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(managed_workspace, tmp_path)
    claims_before = _claims_bytes(store)
    journal_before = _journal_events(store)

    with pytest.raises(ManagedStateError) as false_proof:
        store.transfer_lineage_workspace_claim(
            source, **dict(_transfer_arguments(source, owner), authoritative=False),
        )
    assert false_proof.value.code == "uncertain-effect"
    assert _claims_bytes(store) == claims_before
    assert _journal_events(store) == journal_before

    for invalid in (
            {"target_lineage_id": ""},
            {"target_coordinator_session_uuid": ""},
            {"target_lineage_generation": True},
    ):
        arguments = _transfer_arguments(source, owner)
        arguments.update(invalid)
        with pytest.raises(ManagedStateError) as raised:
            store.transfer_lineage_workspace_claim(source, **arguments)
        assert raised.value.code == "invalid"
        assert _claims_bytes(store) == claims_before
        assert _journal_events(store) == journal_before

    arguments = _transfer_arguments(
        source, owner, lineage_generation=source["lineage_generation"] + 2,
    )
    with pytest.raises(ManagedStateError) as wrong_generation:
        store.transfer_lineage_workspace_claim(source, **arguments)
    assert wrong_generation.value.code == "stale-generation"
    assert _claims_bytes(store) == claims_before
    assert _journal_events(store) == journal_before


@pytest.mark.parametrize(
    ("field", "value"),
    [("owner_generation", 1.0), ("owner_generation", True),
     ("lineage_generation", 1.0), ("lineage_generation", True)],
)
def test_typed_generation_spoof_is_not_an_exact_source_snapshot(
        managed_workspace, tmp_path: Path, field, value):
    store, owner, source = _seed_source(managed_workspace, tmp_path)
    spoof = dict(source)
    spoof[field] = value
    claims_before = _claims_bytes(store)
    journal_before = _journal_events(store)

    with pytest.raises(ManagedStateError) as raised:
        store.transfer_lineage_workspace_claim(
            spoof, **_transfer_arguments(source, owner),
        )

    assert raised.value.code == "invalid"
    assert _claims_bytes(store) == claims_before
    assert _journal_events(store) == journal_before


def test_changed_or_noncanonical_source_snapshot_refuses_without_mutation(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(managed_workspace, tmp_path)
    claims_before = _claims_bytes(store)
    journal_before = _journal_events(store)

    changed_policy = dict(source)
    changed_policy["parent_read_only"] = False
    with pytest.raises(ManagedStateError) as changed:
        store.transfer_lineage_workspace_claim(
            changed_policy, **_transfer_arguments(source, owner),
        )
    assert changed.value.code == "ownership-conflict"

    alias_root = tmp_path / "transfer-source-alias"
    alias_root.symlink_to(Path(source["workspace"]).parent, target_is_directory=True)
    noncanonical = dict(source)
    noncanonical["workspace"] = str(alias_root / Path(source["workspace"]).name)
    with pytest.raises(ManagedStateError) as alias:
        store.transfer_lineage_workspace_claim(
            noncanonical, **_transfer_arguments(source, owner),
        )
    assert alias.value.code == "invalid"
    assert _claims_bytes(store) == claims_before
    assert _journal_events(store) == journal_before


@pytest.mark.parametrize("null_source_uuid", [False, True])
def test_unbound_source_coordinator_uuid_cannot_authorize_lineage_transfer(
        managed_workspace, tmp_path: Path, null_source_uuid):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="transfer-unbound-source",
        daemon_id="daemon-transfer-unbound-source",
        lineage_id="lineage-transfer-unbound-source",
        coordinator_session_uuid=None,
    )
    if null_source_uuid:
        source = dict(source)
        source["coordinator_session_uuid"] = None
        store._write_claims([source])
    claims_before = _claims_bytes(store)
    journal_before = _journal_events(store)

    with pytest.raises(ManagedStateError) as raised:
        store.transfer_lineage_workspace_claim(
            source, **_transfer_arguments(source, owner),
        )

    assert raised.value.code == "ownership-conflict"
    assert _claims_bytes(store) == claims_before
    assert _journal_events(store) == journal_before


def test_source_isolated_child_claim_is_retained_and_blocks_workspace_transfer(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(managed_workspace, tmp_path)
    child_worktree = (tmp_path / "transfer-isolated-child").resolve()
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
        agent_id="agent-transfer-child",
        task_id="task-transfer-child",
    )
    claims_before = _claims_bytes(store)
    journal_before = _journal_events(store)

    with pytest.raises(ManagedStateError) as raised:
        store.transfer_lineage_workspace_claim(
            source, **_transfer_arguments(source, owner),
        )

    assert raised.value.code == "ownership-conflict"
    assert _claims_bytes(store) == claims_before
    assert _journal_events(store) == journal_before
    claims = store.read_lineage_claims()
    assert any(claim.get("record_kind") == "child-worktree-claim"
               for claim in claims)
    assert source in claims


def test_pending_owner_recovery_holds_transfer_before_claim_journal_or_index(
        managed_workspace, tmp_path: Path, runtime_socket_path, monkeypatch):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="transfer-pending-recovery",
        daemon_id="daemon-transfer-pending-recovery",
        lineage_id="lineage-transfer-pending-recovery",
        coordinator_session_uuid="coordinator-transfer-pending-recovery",
    )
    runtime = store.register_runtime(
        daemon_id=owner["daemon_id"], generation=owner["generation"],
        pid=47101, start_token="transfer-pending-old-start", pgid=47102,
        process_domain="local", socket_path=runtime_socket_path,
    )
    recovery_arguments = _recovery_arguments(
        owner, runtime, runtime_socket_path.with_name("transfer-pending-new.sock"),
        daemon_id="daemon-transfer-pending-new",
        pid=47103, start_token="transfer-pending-new-start", pgid=47104,
        request_id="transfer-pending-recovery-request",
        proof=_recovery_proof(runtime),
    )

    def crash_before_owner(_record):
        raise ManagedStateError("unsafe-state", "injected pending recovery boundary")

    monkeypatch.setattr(store, "_write_owner", crash_before_owner)
    with pytest.raises(ManagedStateError) as recovery_failure:
        store.recover_managed_owner(**recovery_arguments)
    assert recovery_failure.value.code == "unsafe-state"
    assert store._load_recovery_intent()["state"] == "pending"

    claims_before = _claims_bytes(store)
    journal_before = _journal_events(store)
    with pytest.raises(ManagedStateError) as transfer_failure:
        store.transfer_lineage_workspace_claim(
            source, **_transfer_arguments(source, owner),
        )
    assert transfer_failure.value.code == "uncertain-effect"
    assert _claims_bytes(store) == claims_before
    assert _journal_events(store) == journal_before


def test_target_identity_collision_and_other_lane_overlap_refuse_atomically(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(managed_workspace, tmp_path)
    target_store, target_owner, target_claim = _seed_source(
        managed_workspace, tmp_path, lane="transfer-target-existing",
        daemon_id="daemon-transfer-target-existing",
        lineage_id="lineage-transfer-target-existing",
        coordinator_session_uuid="coordinator-transfer-target-existing",
    )
    assert target_store.identity.global_root == store.identity.global_root
    claims_before_collision = _claims_bytes(store)
    journal_before_collision = _journal_events(store)

    for target_lineage_id, target_session_uuid in (
            (target_claim["lineage_id"], "coordinator-transfer-fresh-session"),
            ("lineage-transfer-fresh-lineage", target_claim["coordinator_session_uuid"]),
    ):
        collision_arguments = _transfer_arguments(
            source, owner,
            lineage_id=target_lineage_id,
            coordinator_session_uuid=target_session_uuid,
            lineage_generation=source["lineage_generation"] + 1,
        )
        with pytest.raises(ManagedStateError) as collision:
            store.transfer_lineage_workspace_claim(source, **collision_arguments)
        assert collision.value.code == "ownership-conflict"
        assert _claims_bytes(store) == claims_before_collision
        assert _journal_events(store) == journal_before_collision
    assert target_owner["generation"] == owner["generation"]

    # Seed a valid global row for another lane at an ancestor path.  The
    # admission API would reject it after source admission; this fixture
    # models a durable row already present when the CAS revalidates overlap.
    other = dict(source)
    other["lineage_id"] = "lineage-transfer-overlap-other"
    other["coordinator_session_uuid"] = "coordinator-transfer-overlap-other"
    other["lane"] = "transfer-overlap-other"
    other["lane_key"] = "transfer-overlap-other"
    other["workspace"] = str(Path(source["workspace"]).parent)
    store._write_claims([source, target_claim, other])
    claims_before_overlap = _claims_bytes(store)
    journal_before_overlap = _journal_events(store)
    with pytest.raises(ManagedStateError) as overlap:
        store.transfer_lineage_workspace_claim(
            source, **_transfer_arguments(source, owner),
        )
    assert overlap.value.code == "ownership-conflict"
    assert _claims_bytes(store) == claims_before_overlap
    assert _journal_events(store) == journal_before_overlap
    assert other in store.read_lineage_claims()


def test_owner_pinned_identity_and_replaced_same_generation_daemon_refuse(
        managed_workspace, tmp_path: Path):
    pinned_store, pinned_owner, pinned_source = _seed_source(
        managed_workspace, tmp_path, lane="transfer-pinned",
        daemon_id="daemon-transfer-pinned",
        lineage_id="lineage-transfer-pinned",
        coordinator_session_uuid="coordinator-transfer-pinned",
    )
    # The fixture above intentionally enrolls an unpinned owner.  A separate
    # lane models an owner record that the single-index primitive cannot adopt.
    pinned_store._write_owner({
        **pinned_owner,
        "lineage_id": pinned_source["lineage_id"],
        "coordinator_session_uuid": pinned_source["coordinator_session_uuid"],
    })
    pinned_claims = _claims_bytes(pinned_store)
    pinned_journal = _journal_events(pinned_store)
    with pytest.raises(ManagedStateError) as pinned:
        pinned_store.transfer_lineage_workspace_claim(
            pinned_source, **_transfer_arguments(pinned_source, pinned_owner),
        )
    assert pinned.value.code == "ownership-conflict"
    assert _claims_bytes(pinned_store) == pinned_claims
    assert _journal_events(pinned_store) == pinned_journal

    store, owner, source = _seed_source(
        managed_workspace, tmp_path, lane="transfer-replaced-daemon",
        daemon_id="daemon-transfer-old",
        lineage_id="lineage-transfer-replaced-daemon",
        coordinator_session_uuid="coordinator-transfer-replaced-daemon",
    )
    replaced_owner = dict(owner)
    replaced_owner["daemon_id"] = "daemon-transfer-new"
    store._write_owner(replaced_owner)
    owner_bytes = (store.identity.state_root / "owner.json").read_bytes()
    claims_before = _claims_bytes(store)
    journal_before = _journal_events(store)
    with pytest.raises(ManagedStateError) as replaced:
        store.transfer_lineage_workspace_claim(
            source, **_transfer_arguments(source, owner),
        )
    assert replaced.value.code == "ownership-conflict"
    assert (store.identity.state_root / "owner.json").read_bytes() == owner_bytes
    assert _claims_bytes(store) == claims_before
    assert _journal_events(store) == journal_before


@pytest.mark.parametrize(
    "failure_stage", [
        "intent", "after-intent", "index", "after-index", "result", "after-result",
    ])
def test_transfer_crash_boundaries_keep_one_exclusive_claim_and_old_retry_refuses(
        managed_workspace, tmp_path: Path, monkeypatch, failure_stage):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path,
        lane="transfer-crash-" + failure_stage,
        daemon_id="daemon-transfer-crash-" + failure_stage,
        lineage_id="lineage-transfer-crash-" + failure_stage,
        coordinator_session_uuid="coordinator-transfer-crash-" + failure_stage,
    )
    arguments = _transfer_arguments(source, owner)
    original_append = store.append_journal
    original_write = store._write_claims
    write_calls = []

    def append_with_failure(name, event):
        if (failure_stage == "intent" and
                event.get("event") == "native-lineage-claim-transfer-intent"):
            raise ManagedStateError("unsafe-state", "injected transfer journal failure")
        if (failure_stage == "after-intent" and
                event.get("event") == "native-lineage-claim-transfer-intent"):
            original_append(name, event)
            raise ManagedStateError("unsafe-state", "injected post-intent failure")
        if (failure_stage == "result" and
                event.get("event") == "native-lineage-claim-transfer-result"):
            raise ManagedStateError("unsafe-state", "injected transfer journal failure")
        if (failure_stage == "after-result" and
                event.get("event") == "native-lineage-claim-transfer-result"):
            original_append(name, event)
            raise ManagedStateError("unsafe-state", "injected post-journal failure")
        return original_append(name, event)

    def write_with_failure(claims):
        write_calls.append(copy.deepcopy(claims))
        if failure_stage == "index":
            raise ManagedStateError("unsafe-state", "injected transfer index failure")
        result = original_write(claims)
        if failure_stage == "after-index":
            raise ManagedStateError("unsafe-state", "injected post-index failure")
        return result

    if failure_stage in {"intent", "after-intent", "result", "after-result"}:
        monkeypatch.setattr(store, "append_journal", append_with_failure)
    monkeypatch.setattr(store, "_write_claims", write_with_failure)

    with pytest.raises(ManagedStateError) as raised:
        store.transfer_lineage_workspace_claim(source, **arguments)
    assert raised.value.code == "unsafe-state"

    if failure_stage in {"intent", "after-intent", "index"}:
        claims = store.read_lineage_claims()
        assert claims == [source]
        assert source in claims
    else:
        claims = store.read_lineage_claims()
        assert source not in claims
        assert len(claims) == 1
        assert claims[0]["lineage_id"] == arguments["target_lineage_id"]

    events = [
        event for event in _journal_events(store)
        if event.get("event", "").startswith("native-lineage-claim-transfer-")
    ]
    if failure_stage == "intent":
        assert events == []
    elif failure_stage in {"after-intent", "index", "after-index", "result"}:
        assert [event["event"] for event in events] == [
            "native-lineage-claim-transfer-intent"
        ]
    else:
        assert [event["event"] for event in events] == [
            "native-lineage-claim-transfer-intent",
            "native-lineage-claim-transfer-result",
        ]

    assert len(write_calls) == (
        0 if failure_stage in {"intent", "after-intent"} else 1
    )
    if failure_stage in {"after-index", "result", "after-result"}:
        monkeypatch.setattr(store, "_write_claims", original_write)
        monkeypatch.setattr(store, "append_journal", original_append)
        with pytest.raises(ManagedStateError) as retry:
            store.transfer_lineage_workspace_claim(source, **arguments)
        assert retry.value.code == "ownership-conflict"
        assert len(store.read_lineage_claims()) == 1
        assert store.read_lineage_claims()[0]["lineage_id"] == arguments["target_lineage_id"]
        assert len(write_calls) == 1


def _transfer_worker(workspace: str, lane: str, expected_claim, arguments,
                     barrier, results):
    helper = Path(workspace).parent / "workspace-helper" / "lanes-edit.sh"
    try:
        identity = resolve_workspace(
            lane, env={"LANES_WORKSTATION": "eagle"}, helper=helper,
        )
        store = ManagedStateStore(identity)
        barrier.wait(timeout=5)
        result = store.transfer_lineage_workspace_claim(
            expected_claim, **arguments,
        )
        results.put(("ok", result["lineage_id"]))
    except ManagedStateError as exc:
        results.put(("error", exc.code))
    except BaseException as exc:  # pragma: no cover - child diagnostics
        results.put(("crash", type(exc).__name__, str(exc)))


@pytest.mark.skipif(os.name == "nt", reason="requires POSIX process locks")
def test_concurrent_transfer_has_one_cas_winner_and_no_retry_success(
        managed_workspace, tmp_path: Path):
    store, owner, source = _seed_source(
        managed_workspace, tmp_path, lane="transfer-race",
        daemon_id="daemon-transfer-race",
        lineage_id="lineage-transfer-race",
        coordinator_session_uuid="coordinator-transfer-race",
    )
    arguments = _transfer_arguments(source, owner)
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(
            target=_transfer_worker,
            args=(str(managed_workspace.workspace_repo), "transfer-race",
                  source, arguments, barrier, results),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    outcomes = []
    try:
        outcomes = [results.get(timeout=5), results.get(timeout=5)]
        for process in processes:
            process.join(timeout=5)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)

    assert all(outcome[0] in {"ok", "error"} for outcome in outcomes), outcomes
    assert sum(outcome[0] == "ok" for outcome in outcomes) == 1, outcomes
    assert sum(outcome[0] == "error" for outcome in outcomes) == 1, outcomes
    assert next(outcome for outcome in outcomes if outcome[0] == "error")[1] == \
        "ownership-conflict"
    final = store.read_lineage_claims()
    assert len(final) == 1
    assert final[0]["lineage_id"] == arguments["target_lineage_id"]
