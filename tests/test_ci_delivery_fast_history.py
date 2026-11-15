# SPDX-License-Identifier: Apache-2.0
"""Authentic same-head event history is not permission to borrow an old green."""

import copy

import pytest

from test_ci_delivery import FAST, batch, base_changes, delivery, request_for


def cohort(batch):
    head = batch["heads"][0]
    checks = batch["data"][f"commits/{head}/check-runs?check_name={FAST}&filter=latest&per_page=100"]
    path = f"actions/workflows/task-set-fast.yml/runs?head_sha={head}&event=pull_request&per_page=100&page=1"
    return checks, batch["data"][path], path


def add_historical_run(batch):
    checks, catalog, _path = cohort(batch)
    old = copy.deepcopy(catalog["workflow_runs"][0])
    # Deliberately a larger ID: workflow sequence, not ID or array order, is latest.
    old.update(id=700, run_number=1, check_suite_id=700,
               created_at="2026-11-10T00:00:01Z")
    check = copy.deepcopy(checks["check_runs"][0])
    check.update(id=1700, check_suite={"id": 700},
                 details_url="https://github.com/opensoft/openRepoTools-code/actions/runs/700/job/1700")
    checks["check_runs"].insert(0, check)
    checks["total_count"] += 1
    catalog["workflow_runs"].insert(0, old)
    catalog["total_count"] += 1
    batch["data"]["actions/runs/700"] = old
    batch["data"]["actions/jobs/1700"] = {
        **batch["data"]["actions/jobs/907"], "id": 1700, "run_id": 700}
    return old, check


def receipt(delivery, batch, request=None, **kwargs):
    return delivery.fast_receipt(batch["prs"][7], batch["heads"][0],
                                 request or request_for(batch), base_changes, **kwargs)


@pytest.mark.parametrize("older_state", ["success", "failure", "in_progress"])
def test_ci_delivery_fast_history_selects_newest_canonical_run(delivery, batch, older_state):
    old, check = add_historical_run(batch)
    if older_state == "in_progress":
        old.update(status="in_progress", conclusion=None)
        check.update(status="in_progress", conclusion=None)
    else:
        old["conclusion"] = check["conclusion"] = older_state
    result = receipt(delivery, batch)
    assert result[1]["id"] == 107 and result[2]["id"] == 907


@pytest.mark.parametrize("state", ["failure", "cancelled", "in_progress"])
def test_ci_delivery_fast_history_never_borrows_older_green(delivery, batch, state):
    add_historical_run(batch)
    run = batch["data"]["actions/runs/107"]
    run.update(status="in_progress" if state == "in_progress" else "completed",
               conclusion=None if state == "in_progress" else state)
    with pytest.raises(delivery.Refused):
        receipt(delivery, batch)


def test_ci_delivery_fast_history_missing_latest_job_cannot_borrow_old_green(delivery, batch):
    add_historical_run(batch)
    run = batch["data"]["actions/runs/107"]
    run.update(status="queued", conclusion=None)
    checks, _catalog, _path = cohort(batch)
    checks.update(total_count=1, check_runs=[checks["check_runs"][0]])
    with pytest.raises(delivery.Refused) as refused:
        receipt(delivery, batch, allow_pending=True)
    assert type(refused.value) is delivery.Refused


@pytest.mark.parametrize("failure", [
    "catalog-truncated", "catalog-boolean", "catalog-empty", "duplicate-id",
    "duplicate-sequence", "workflow", "head", "branch", "foreign", "sequence-type",
    "mixed-workflow-id", "unknown-check", "duplicate-check", "forged-app", "wrong-suite",
])
def test_ci_delivery_fast_history_uncertain_catalog_or_check_refuses(delivery, batch, failure):
    old, check = add_historical_run(batch)
    checks, catalog, _path = cohort(batch)
    if failure == "catalog-truncated": catalog["total_count"] += 1
    elif failure == "catalog-boolean": catalog["total_count"] = True
    elif failure == "catalog-empty": catalog.update(total_count=0, workflow_runs=[])
    elif failure == "duplicate-id": old["id"] = 107
    elif failure == "duplicate-sequence": old["run_number"] = 7
    elif failure == "workflow": old["path"] = ".github/workflows/other.yml"
    elif failure == "head": old["head_sha"] = "f" * 40
    elif failure == "branch": old["head_branch"] = "other"
    elif failure == "foreign": old["head_repository"]["full_name"] = "other/repo"
    elif failure == "sequence-type": old["run_number"] = True
    elif failure == "mixed-workflow-id": old["workflow_id"] += 1
    elif failure == "unknown-check": catalog.update(total_count=1, workflow_runs=[catalog["workflow_runs"][1]])
    elif failure == "duplicate-check": checks["check_runs"].append(copy.deepcopy(check)); checks["total_count"] += 1
    elif failure == "forged-app": check["app"]["slug"] = "other"
    elif failure == "wrong-suite": check["check_suite"]["id"] = 1
    with pytest.raises(delivery.Refused):
        receipt(delivery, batch)


def test_ci_delivery_fast_history_newer_event_during_reads_refuses(delivery, batch):
    old, _check = add_historical_run(batch)
    _checks, catalog, path = cohort(batch)
    reader, reads = request_for(batch), 0

    def request(repo, endpoint):
        nonlocal reads
        if endpoint == path:
            reads += 1
            if reads == 2:
                old["run_number"] = 8
        return reader(repo, endpoint)

    with pytest.raises(delivery.Refused):
        receipt(delivery, batch, request)
    assert reads == 2


@pytest.mark.parametrize("observation", [1, 2], ids=["initial", "final"])
@pytest.mark.parametrize("state", ["queued", "failure", "success", "same-attempt-failure"])
def test_ci_delivery_fast_history_catalogue_attempt_and_state_cannot_be_ignored(
        delivery, batch, observation, state):
    _checks, _catalog, path = cohort(batch)
    reader, reads = request_for(batch), 0

    def request(repo, endpoint):
        nonlocal reads
        result = reader(repo, endpoint)
        if endpoint == path:
            reads += 1
            if reads == observation:
                row = result["workflow_runs"][0]
                if state != "same-attempt-failure":
                    row["run_attempt"] += 1
                row.update(status="queued" if state == "queued" else "completed",
                           conclusion=None if state == "queued" else
                           "failure" if state == "same-attempt-failure" else state)
        return result

    with pytest.raises(delivery.Refused):
        receipt(delivery, batch, request, allow_pending=True)
