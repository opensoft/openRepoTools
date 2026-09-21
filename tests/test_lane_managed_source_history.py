# SPDX-License-Identifier: Apache-2.0
"""Test-first preservation and refusal cases for native source archives.

This module exercises only the durable controller boundary.  Archive reads and
writes must not consult a runtime, transfer a claim, mutate an admission, or
turn a source snapshot into an adoption authorization.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping

import pytest

from lane_managed_controller import ControllerError, ManagedController
from test_lane_managed_controller import MemoryStore
from test_lane_managed_coordinator_interrupt import (
    _digest,
    _evidence as _interrupt_evidence,
    _fenced_authority,
    _intent as _interrupt_intent,
    _roster,
)
from test_lane_managed_native_stop import (
    _intent as _stop_intent,
    _native_stop_authority,
)


ARCHIVE_FIELDS = {
    "schema_version",
    "architecture",
    "record_kind",
    "archive_id",
    "operation_id",
    "source_identity",
    "snapshot_digest",
    "snapshot",
}
SOURCE_IDENTITY_FIELDS = {
    "owner_generation",
    "lineage_id",
    "lineage_generation",
    "session_uuid",
    "runner_incarnation",
    "invocation_id",
}
MAX_JSON_BYTES = 1024 * 1024


class _NoRuntimeCalls:
    def __getattr__(self, name):
        raise AssertionError("source archive accessed runtime attribute %s" % name)


def _record(store):
    return copy.deepcopy(store.documents["controller.json"])


def _without_archives(record):
    result = copy.deepcopy(record)
    result.pop("native_source_archives", None)
    return result


def _archive_entry(store, archive_id):
    return store.documents["controller.json"]["native_source_archives"][archive_id]


def _write_state(store):
    return copy.deepcopy(store.write_calls), copy.deepcopy(store.journal)


def _assert_no_write_or_journal(store, writes, journal):
    assert store.write_calls == writes
    assert store.journal == journal


def _archive(controller, store, archive_id, operation_id, generation=7):
    before = _record(store)
    result = controller.archive_native_source(
        archive_id, operation_id, generation
    )
    entry = _archive_entry(store, archive_id)
    assert result == entry
    assert set(entry) == ARCHIVE_FIELDS
    assert entry["archive_id"] == archive_id
    assert entry["operation_id"] == operation_id
    assert entry["snapshot"] == _without_archives(before)
    assert entry["snapshot_digest"] == _digest(entry["snapshot"])
    return result


def _assert_source_identity(entry, lineage, runner_instance_id, invocation_id):
    identity = entry["source_identity"]
    assert set(identity) == SOURCE_IDENTITY_FIELDS
    assert identity == {
        "owner_generation": lineage["owner_generation"],
        "lineage_id": lineage["lineage_id"],
        "lineage_generation": lineage["lineage_generation"],
        "session_uuid": lineage["session_uuid"],
        "runner_incarnation": runner_instance_id,
        "invocation_id": invocation_id,
    }


def _status_archive_summary(controller, archive_id):
    summaries = controller.status()["native_source_archives"]
    assert isinstance(summaries, Mapping)
    assert set(summaries) == {archive_id}
    summary = summaries[archive_id]
    assert "snapshot" not in summary
    return summary


def _two_admission_fenced_authority(tmp_path):
    """Create two real admissions before one real native fence."""
    _old_controller, store, lineage, first_admission, _context = (
        _native_stop_authority(tmp_path)
    )
    controller = ManagedController(
        store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )
    second_admission = copy.deepcopy(first_admission)
    second_admission.update(
        {
            "admission_id": "admission-2",
            "tool_use_id": "tool-2",
            "watermark": 3,
        }
    )
    controller.persist_native_admission(
        "request-2", lineage["owner_generation"], second_admission
    )
    operation = controller.begin_operation(
        "native-source-archive-operation",
        "swap",
        lineage["owner_generation"],
        request_content={"target": "synthetic-test-profile"},
    )
    controller.fence(operation.operation_id)
    return controller, store, lineage, first_admission, second_admission, operation


def _interrupt_with_terminal_facts(tmp_path):
    controller, store, lineage, first, second, operation = (
        _two_admission_fenced_authority(tmp_path)
    )
    first_child = _roster(
        first, child_status="completed", terminal_watermark=7
    )["children"][0]
    second_child = _roster(second)["children"][0]
    second_child.update(
        {
            "agent_id": "agent-2",
            "task_id": "task-2",
            "start_watermark": 4,
            "task_start_event": {
                "event_uuid": "task-start-2",
                "watermark": 5,
                "task_type": "local_agent",
            },
            "active_tool_ids": ["child-tool-2"],
            "unresolved_effect_ids": ["effect-2"],
        }
    )
    roster = {
        "parent_state": "active",
        "children": [first_child, second_child],
        "pending_admission_ids": [],
        "pending_task_ids": [],
        "parent_active_tool_ids": [],
        "parent_uncertain_tool_ids": [],
        "parent_unresolved_effect_ids": [],
        "descendant_ids": [],
    }
    frame = _interrupt_intent(
        lineage,
        first,
        operation.operation_id,
        roster=roster,
        interrupt_id="interrupt-source-history",
    )
    controller.persist_coordinator_interrupt_intent(frame)
    controller.persist_coordinator_interrupt_evidence(
        _interrupt_evidence(frame, "runtime-ack")
    )

    completed_data = copy.deepcopy(
        _interrupt_evidence(frame, "member-terminal")["evidence"]["data"]
    )
    completed_data.update(
        {
            "agent_id": first_child["agent_id"],
            "task_id": first_child["task_id"],
            "tool_use_id": first_child["tool_use_id"],
            "lineage_incarnation": first_child["lineage_incarnation"],
            "status": "completed",
        }
    )
    controller.persist_coordinator_interrupt_evidence(
        _interrupt_evidence(
            frame,
            "member-terminal",
            evidence_id="evidence-member-completed",
            observed_watermark=7,
            data=completed_data,
        )
    )

    failed_data = copy.deepcopy(completed_data)
    failed_data.update(
        {
            "agent_id": second_child["agent_id"],
            "task_id": second_child["task_id"],
            "tool_use_id": second_child["tool_use_id"],
            "event_uuid": "task-failed-2",
            "status": "failed",
        }
    )
    controller.persist_coordinator_interrupt_evidence(
        _interrupt_evidence(
            frame,
            "member-terminal",
            evidence_id="evidence-member-failed",
            observed_watermark=9,
            data=failed_data,
        )
    )
    return controller, store, lineage, operation, frame


def _native_stop_archive_fixture(tmp_path):
    _old_controller, store, lineage, admission, _context = (
        _native_stop_authority(tmp_path)
    )
    controller = ManagedController(
        store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )
    stop_frame = _stop_intent(lineage, admission)
    controller.persist_native_stop_intent(stop_frame)
    operation = controller.begin_operation(
        "native-source-archive-after-stop",
        "swap",
        lineage["owner_generation"],
        request_content={"target": "synthetic-test-profile"},
    )
    controller.fence(operation.operation_id)
    return controller, store, lineage, operation, stop_frame


def _interrupt_archive_fixture(tmp_path):
    controller, store, lineage, admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    frame = _interrupt_intent(lineage, admission, operation_id)
    controller.persist_coordinator_interrupt_intent(frame)
    return controller, store, lineage, operation_id, frame


def _padded_fenced_authority(tmp_path, padding_length=160_000):
    _old_controller, store, lineage, _admission, _context = (
        _native_stop_authority(tmp_path)
    )
    controller = ManagedController(
        store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )
    operation = controller.begin_operation(
        "native-source-archive-size-operation",
        "swap",
        lineage["owner_generation"],
        request_content={
            "target": "synthetic-test-profile",
            "padding": "x" * padding_length,
        },
    )
    controller.fence(operation.operation_id)
    return controller, store, lineage, operation


def test_archive_preserves_canonical_source_and_natural_terminal_facts(tmp_path):
    controller, store, lineage, operation, frame = _interrupt_with_terminal_facts(
        tmp_path
    )
    before = _record(store)

    entry = _archive(
        controller,
        store,
        "archive-terminal-facts",
        operation.operation_id,
        lineage["owner_generation"],
    )

    expected = _without_archives(before)
    assert entry["snapshot"] == expected
    isolated_store = MemoryStore()
    isolated_store.documents["controller.json"] = copy.deepcopy(expected)
    isolated = ManagedController(isolated_store)
    canonical = isolated._record()
    canonical.pop("native_source_archives", None)
    assert entry["snapshot"] == canonical

    interrupt = entry["snapshot"]["coordinator_interrupts"][
        "interrupt-source-history"
    ]
    children = interrupt["frame"]["interrupt"]["roster"]["children"]
    assert {child["status"] for child in children} == {"active", "completed"}
    evidence = interrupt["evidence"]
    assert (
        evidence["evidence-member-completed"]["frame"]["evidence"]["data"][
            "status"
        ]
        == "completed"
    )
    assert (
        evidence["evidence-member-failed"]["frame"]["evidence"]["data"][
            "status"
        ]
        == "failed"
    )
    assert frame["interrupt"]["operation_id"] == operation.operation_id


def test_archive_constructor_getter_and_status_use_aligned_entry_shapes(tmp_path):
    controller, store, lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )

    entry = _archive(controller, store, "archive-1", operation_id)
    _assert_source_identity(
        entry,
        lineage,
        runner_instance_id="runner-current",
        invocation_id="invocation-1",
    )

    assert controller.native_source_archive("archive-1") == entry
    summary = _status_archive_summary(controller, "archive-1")
    assert summary == {
        key: value for key, value in entry.items() if key != "snapshot"
    }
    assert summary["archive_id"] == "archive-1"
    assert summary["snapshot_digest"] == entry["snapshot_digest"]


def test_exact_archive_retry_is_byte_stable_without_write_or_journal(tmp_path):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    first = _archive(controller, store, "archive-1", operation_id)
    before_record = _record(store)
    writes, journal = _write_state(store)

    retry = controller.archive_native_source("archive-1", operation_id, 7)

    assert retry == first
    assert _record(store) == before_record
    _assert_no_write_or_journal(store, writes, journal)


@pytest.mark.parametrize("missing_fields", [
    ("native_invocation_history",),
    ("native_invocation_rollovers",),
    ("native_child_observations",),
    ("native_invocation_history", "native_invocation_rollovers",
     "native_child_observations"),
])
def test_optional_archive_defaults_never_rewrite_hashed_history(
    tmp_path, missing_fields,
):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    entry = _archive(controller, store, "archive-optional", operation_id)
    for field in ("native_invocation_history", "native_invocation_rollovers",
                  "native_child_observations"):
        assert not entry["snapshot"].get(field)
        entry["snapshot"][field] = {}
    for field in missing_fields:
        entry["snapshot"].pop(field)
    entry["snapshot_digest"] = _digest(entry["snapshot"])
    expected = copy.deepcopy(entry)
    expected_bytes = json.dumps(expected, sort_keys=True, separators=(",", ":"))

    for _ in range(2):
        entry = ManagedController._validate_native_source_archive_entry(entry)
        assert entry == expected
        assert entry["snapshot_digest"] == _digest(entry["snapshot"])
        assert json.dumps(entry, sort_keys=True, separators=(",", ":")) == expected_bytes

    store.documents["controller.json"]["native_source_archives"][
        "archive-optional"
    ] = copy.deepcopy(entry)
    reloaded = ManagedController(store)
    writes, journal = _write_state(store)
    assert reloaded.native_source_archive("archive-optional") == expected
    _assert_no_write_or_journal(store, writes, journal)
    # A later controller write must not persist the validator's expanded view.
    reloaded._persist()
    assert _archive_entry(store, "archive-optional") == expected
    assert ManagedController(store).native_source_archive("archive-optional") == expected


def test_changed_source_content_under_same_archive_id_refuses_without_archive_write(
    tmp_path,
):
    controller, store, _lineage, operation_id, _frame = (
        _interrupt_archive_fixture(tmp_path)
    )
    frame = store.documents["controller.json"]["coordinator_interrupts"][
        "interrupt-1"
    ]["frame"]
    first = _archive(controller, store, "archive-1", operation_id)

    # The public evidence validator changes the source after archival.  The
    # retry must not replace the immutable entry with this new source.
    controller.persist_coordinator_interrupt_evidence(
        _interrupt_evidence(frame, "runtime-ack")
    )
    changed_record = _record(store)
    writes, journal = _write_state(store)

    with pytest.raises(ControllerError) as raised:
        controller.archive_native_source("archive-1", operation_id, 7)

    assert raised.value.code == "invalid"
    assert _record(store) == changed_record
    assert _archive_entry(store, "archive-1") == first
    _assert_no_write_or_journal(store, writes, journal)


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        pytest.param("owner", "ownership-conflict", id="owner-replaced"),
        pytest.param(
            "coordinator-daemon", "ownership-conflict",
            id="coordinator-interrupt-daemon-replaced",
        ),
        pytest.param("generation", "stale-generation", id="generation-stale"),
    ],
)
def test_archive_revalidates_owner_daemon_and_generation_before_persisting(
    tmp_path, case, expected_code,
):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path / case)
    )
    candidate = controller
    generation = 7
    if case == "owner":
        store.read_owner = lambda: {
            "mode": "managed",
            "lane": "build",
            "generation": 7,
            "daemon_id": "replacement-daemon",
        }
    elif case == "coordinator-daemon":
        candidate = ManagedController(
            store,
            _native_stop_daemon_id="daemon-test",
            _coordinator_interrupt_daemon_id="wrong-daemon",
        )
    else:
        generation = 8

    before = _record(store)
    writes, journal = _write_state(store)
    with pytest.raises(ControllerError) as raised:
        candidate.archive_native_source("archive-" + case, operation_id, generation)

    assert raised.value.code == expected_code
    assert _record(store) == before
    _assert_no_write_or_journal(store, writes, journal)


def test_archive_requires_a_matching_fenced_operation(tmp_path):
    _old_controller, store, lineage, _admission, _context = (
        _native_stop_authority(tmp_path)
    )
    controller = ManagedController(
        store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )
    operation = controller.begin_operation(
        "native-source-archive-unfenced",
        "swap",
        lineage["owner_generation"],
        request_content={"target": "synthetic-test-profile"},
    )
    before = _record(store)
    writes, journal = _write_state(store)

    with pytest.raises(ControllerError) as raised:
        controller.archive_native_source(
            "archive-unfenced", operation.operation_id, lineage["owner_generation"]
        )

    assert raised.value.code in {"busy", "unsupported", "stale-generation"}
    assert _record(store) == before
    _assert_no_write_or_journal(store, writes, journal)


def test_history_reloads_without_current_owner_claim_or_daemon_authority(tmp_path):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    entry = _archive(controller, store, "archive-1", operation_id)
    writes, journal = _write_state(store)

    store.read_owner = lambda: None
    store.read_lineage_claims = lambda: []
    reloaded = ManagedController(store)

    assert reloaded.native_source_archive("archive-1") == entry
    assert reloaded.status()["native_source_archives"]["archive-1"] == {
        key: value for key, value in entry.items() if key != "snapshot"
    }
    _assert_no_write_or_journal(store, writes, journal)


def test_archive_and_getter_results_are_defensive_copies(tmp_path):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    entry = _archive(controller, store, "archive-1", operation_id)
    durable_before = _record(store)
    writes, journal = _write_state(store)

    returned = controller.native_source_archive("archive-1")
    returned["snapshot"]["generation"] = "forged"
    returned["source_identity"]["lineage_id"] = "forged"

    status = controller.status()
    status["native_source_archives"]["archive-1"][
        "source_identity"
    ]["lineage_id"] = "forged-status"

    assert controller.native_source_archive("archive-1") == entry
    assert controller.status()["native_source_archives"]["archive-1"] == {
        key: value for key, value in entry.items() if key != "snapshot"
    }
    assert _record(store) == durable_before
    _assert_no_write_or_journal(store, writes, journal)


def test_unknown_archive_getter_is_read_only_and_refuses(tmp_path):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    _archive(controller, store, "archive-1", operation_id)
    before = _record(store)
    writes, journal = _write_state(store)

    with pytest.raises(ControllerError) as raised:
        controller.native_source_archive("archive-unknown")

    assert raised.value.code == "unknown"
    assert _record(store) == before
    _assert_no_write_or_journal(store, writes, journal)


def test_corrupt_archive_digest_refuses_reload_without_rewriting_history(tmp_path):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    _archive(controller, store, "archive-1", operation_id)
    raw = _record(store)
    raw["native_source_archives"]["archive-1"]["snapshot_digest"] = "0" * 64
    store.documents["controller.json"] = raw
    before = _record(store)
    writes, journal = _write_state(store)

    with pytest.raises(ControllerError):
        ManagedController(
            store,
            _native_stop_daemon_id="daemon-test",
            _coordinator_interrupt_daemon_id="daemon-test",
        )

    assert _record(store) == before
    _assert_no_write_or_journal(store, writes, journal)


@pytest.mark.parametrize("tamper", ["unknown-field", "type-coercion"])
def test_recomputed_digest_does_not_admit_noncanonical_snapshot(tmp_path, tamper):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    _archive(controller, store, "archive-1", operation_id)
    raw = _record(store)
    snapshot = raw["native_source_archives"]["archive-1"]["snapshot"]
    if tamper == "unknown-field":
        snapshot["unknown_snapshot_field"] = {"even": {}}
    else:
        snapshot["generation"] = str(snapshot["generation"])
    raw["native_source_archives"]["archive-1"]["snapshot_digest"] = _digest(
        snapshot
    )
    store.documents["controller.json"] = raw
    before = _record(store)
    writes, journal = _write_state(store)

    with pytest.raises(ControllerError):
        ManagedController(
            store,
            _native_stop_daemon_id="daemon-test",
            _coordinator_interrupt_daemon_id="daemon-test",
        )

    assert _record(store) == before
    _assert_no_write_or_journal(store, writes, journal)


@pytest.mark.parametrize("kind", ["native-stop", "coordinator-interrupt"])
def test_malformed_nested_stop_or_interrupt_snapshot_refuses_reload(
    tmp_path, kind
):
    if kind == "native-stop":
        controller, store, _lineage, operation, _stop_frame = (
            _native_stop_archive_fixture(tmp_path)
        )
        _archive(controller, store, "archive-1", operation.operation_id)
        raw = _record(store)
        nested_stop = raw["native_source_archives"]["archive-1"]["snapshot"][
            "native_stops"
        ]["stop-1"]
        del nested_stop["frame"]["stop"]["observation"]
    else:
        controller, store, _lineage, operation_id, _frame = (
            _interrupt_archive_fixture(tmp_path)
        )
        _archive(controller, store, "archive-1", operation_id)
        raw = _record(store)
        nested_interrupt = raw["native_source_archives"]["archive-1"][
            "snapshot"
        ]["coordinator_interrupts"]["interrupt-1"]
        del nested_interrupt["frame"]["interrupt"]["roster"]

    snapshot = raw["native_source_archives"]["archive-1"]["snapshot"]
    raw["native_source_archives"]["archive-1"]["snapshot_digest"] = _digest(
        snapshot
    )
    store.documents["controller.json"] = raw
    before = _record(store)
    writes, journal = _write_state(store)

    with pytest.raises(ControllerError):
        ManagedController(
            store,
            _native_stop_daemon_id="daemon-test",
            _coordinator_interrupt_daemon_id="daemon-test",
        )

    assert _record(store) == before
    _assert_no_write_or_journal(store, writes, journal)


def test_nested_archive_collection_even_empty_refuses_before_recursion(tmp_path):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    _archive(controller, store, "archive-1", operation_id)
    raw = _record(store)
    snapshot = raw["native_source_archives"]["archive-1"]["snapshot"]
    snapshot["native_source_archives"] = {}
    raw["native_source_archives"]["archive-1"]["snapshot_digest"] = _digest(
        snapshot
    )
    store.documents["controller.json"] = raw
    before = _record(store)
    writes, journal = _write_state(store)

    with pytest.raises(ControllerError):
        ManagedController(
            store,
            _native_stop_daemon_id="daemon-test",
            _coordinator_interrupt_daemon_id="daemon-test",
        )

    assert _record(store) == before
    _assert_no_write_or_journal(store, writes, journal)


def test_archive_count_limit_refuses_before_write_and_never_evicts_history(tmp_path):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    for index in range(16):
        _archive(
            controller,
            store,
            "archive-%02d" % index,
            operation_id,
        )
    before = _record(store)
    writes, journal = _write_state(store)

    with pytest.raises(ControllerError) as raised:
        controller.archive_native_source("archive-16", operation_id, 7)

    assert raised.value.code in {"busy", "invalid"}
    assert set(before["native_source_archives"]) == {
        "archive-%02d" % index for index in range(16)
    }
    assert _record(store) == before
    _assert_no_write_or_journal(store, writes, journal)


def test_full_archive_candidate_over_one_mib_refuses_before_write(tmp_path):
    controller, store, _lineage, operation = _padded_fenced_authority(tmp_path)
    failed_index = None
    for index in range(16):
        archive_id = "archive-size-%02d" % index
        before = _record(store)
        writes, journal = _write_state(store)
        try:
            _archive(controller, store, archive_id, operation.operation_id)
        except ControllerError:
            failed_index = index
            candidate = _record(store)
            source = _without_archives(candidate)
            existing = candidate.get("native_source_archives", {})
            assert existing
            prototype = copy.deepcopy(next(iter(existing.values())))
            prototype["archive_id"] = archive_id
            prototype["operation_id"] = operation.operation_id
            prototype["snapshot"] = source
            prototype["snapshot_digest"] = _digest(source)
            candidate.setdefault("native_source_archives", {})[archive_id] = prototype
            encoded = json.dumps(
                candidate,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
            assert len(encoded) > MAX_JSON_BYTES
            assert _record(store) == before
            _assert_no_write_or_journal(store, writes, journal)
            break
    assert failed_index is not None
    assert failed_index < 16


def test_archive_is_observational_for_runtime_claims_admissions_and_operation(
    tmp_path,
):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    controller.runtime = _NoRuntimeCalls()
    claims_before = copy.deepcopy(store.read_lineage_claims())
    owner_before = copy.deepcopy(store.read_owner())
    admissions_before = copy.deepcopy(
        store.documents["controller.json"]["native_admissions"]
    )
    operation_before = copy.deepcopy(next(
        operation
        for operation in store.documents["controller.json"]["operations"]
        if operation["operation_id"] == operation_id
    ))
    operation_phase = operation_before["phase"]

    _archive(controller, store, "archive-1", operation_id)

    assert store.read_lineage_claims() == claims_before
    assert store.read_owner() == owner_before
    assert store.documents["controller.json"]["native_admissions"] == admissions_before
    operation_after = next(
        operation
        for operation in store.documents["controller.json"]["operations"]
        if operation["operation_id"] == operation_id
    )
    assert operation_after == operation_before
    assert operation_after["phase"] == operation_phase


def test_journal_failure_after_snapshot_write_keeps_archive_and_active_ledgers(
    tmp_path,
):
    controller, store, _lineage, _admission, _context, operation_id = (
        _fenced_authority(tmp_path)
    )
    controller.runtime = _NoRuntimeCalls()
    claims_before = copy.deepcopy(store.read_lineage_claims())
    owner_before = copy.deepcopy(store.read_owner())
    before = _record(store)
    writes, journal = _write_state(store)

    original_append_journal = store.append_journal

    def fail_after_snapshot_write(name, event):
        raise RuntimeError("injected journal failure")

    store.append_journal = fail_after_snapshot_write
    with pytest.raises(RuntimeError):
        controller.archive_native_source("archive-after-journal-failure", operation_id, 7)
    store.append_journal = original_append_journal

    after = _record(store)
    assert "archive-after-journal-failure" in after["native_source_archives"]
    assert len(store.write_calls) == len(writes) + 1
    assert store.journal == journal
    for ledger in (
        "native_context",
        "native_admissions",
        "native_stops",
        "coordinator_interrupts",
        "operations",
    ):
        assert after[ledger] == before[ledger]
    assert store.read_lineage_claims() == claims_before
    assert store.read_owner() == owner_before

    reloaded = ManagedController(
        store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )
    before_retry = _record(store)
    retry_writes, retry_journal = _write_state(store)
    retry = reloaded.archive_native_source(
        "archive-after-journal-failure", operation_id, 7
    )

    assert retry == _archive_entry(store, "archive-after-journal-failure")
    assert _record(store) == before_retry
    _assert_no_write_or_journal(store, retry_writes, retry_journal)
    assert store.read_lineage_claims() == claims_before
    assert store.read_owner() == owner_before


def test_archived_context_reloads_from_a_separately_valid_current_fixture(tmp_path):
    source_controller, source_store, _source_lineage, _source_admission, _context, source_operation_id = (
        _fenced_authority(tmp_path / "source")
    )
    source_entry = _archive(
        source_controller, source_store, "archive-independent", source_operation_id
    )

    current_controller, current_store, _current_lineage, _current_admission, _context, current_operation_id = (
        _fenced_authority(tmp_path / "current")
    )
    current_raw = _record(current_store)
    current_raw["native_source_archives"] = {
        "archive-independent": copy.deepcopy(source_entry)
    }
    current_store.documents["controller.json"] = current_raw
    assert current_raw["native_context"] != source_entry["snapshot"]["native_context"]
    assert current_operation_id != source_operation_id

    reloaded = ManagedController(
        current_store,
        _native_stop_daemon_id="daemon-test",
        _coordinator_interrupt_daemon_id="daemon-test",
    )

    assert reloaded.native_source_archive("archive-independent") == source_entry
    assert reloaded.status()["native_source_archives"]["archive-independent"] == {
        key: value for key, value in source_entry.items() if key != "snapshot"
    }
    assert current_controller.status()["operation"]["operation_id"] == current_operation_id
