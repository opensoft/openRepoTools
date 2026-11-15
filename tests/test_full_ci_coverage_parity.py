# SPDX-License-Identifier: Apache-2.0
"""Full CI reuse is the existing workflow, not a second suite or a skip mode.

The baseline hashes sorted, compact JSON of each complete parsed job (including
step order, matrices, conditions and permissions). Comments do not affect it.
Update this inventory only in an explicitly reviewed coverage-contract change;
new test files are still discovered by ci_shards.py without an inventory edit.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from conftest import NEEDS_UPSTREAM, REPO, UPSTREAM

pytestmark = NEEDS_UPSTREAM
WORKFLOW = ".github/workflows/tests.yml"
CALLER = ".github/workflows/full-ci-parity.yml"
BASELINE = ".github/ci/full-ci-baseline.json"
GATES = {"guard-launch-mode", "tests", "tests-no-submodule", "package"}
SHARDS = {"tests-shard": ["pytest-1", "pytest-2", "pytest-3", "pytest-4", "shell"],
          "tests-no-submodule-shard": ["pytest-1", "pytest-2", "pytest-3", "shell"]}
ROOT_GUARD = "${{ !cancelled() && !(needs.delivery-route.result == 'success' && needs.delivery-route.outputs.omit_full == 'true') }}"
AGGREGATE_GUARD = "${{ always() && !(needs.delivery-route.result == 'success' && needs.delivery-route.outputs.omit_full == 'true') }}"
CONTROLS = {"delivery-route", "delivery-gate"}
CONTROL_DIGESTS = {
    "delivery-gate": "a92ee06898813042cfc5cc413139ff330041a4b2baace8b7512fc5ad03053fa7",
    "delivery-route": "513e7e08d5b60164bf837712478698f5434e8efd10ce7cf31d26c0f1c47fa044",
}
READ_PERMISSIONS = {"contents": "read", "pull-requests": "read", "checks": "read", "actions": "read"}


@pytest.fixture(scope="module")
def reader():
    spec = importlib.util.spec_from_file_location(
        "coverage_parity_yaml", UPSTREAM / "scripts/repo_shape.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_yaml


@pytest.fixture
def workflow(reader):
    return reader(REPO / WORKFLOW)


@pytest.fixture
def baseline():
    return json.loads((REPO / BASELINE).read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def parity_errors(workflow, baseline):
    """Compare complete job definitions, not selected commands or job counts."""
    errors = []
    if set(workflow) != {"name", "on", "env", "jobs"}:
        errors.append("workflow settings changed")
    if workflow.get("env") != baseline["environment"]:
        errors.append("environment changed")
    events = dict(workflow.get("on", {}))
    if "workflow_call" not in events or events.pop("workflow_call") is not None:
        errors.append("reuse is not parameterless")
    if events != baseline["ordinary_events"]:
        errors.append("ordinary events changed")
    jobs = copy.deepcopy(workflow.get("jobs", {}))
    if set(jobs) != set(baseline["job_sha256"]) | CONTROLS:
        errors.append("job inventory changed")
    for name, expected in CONTROL_DIGESTS.items():
        if digest(jobs.get(name)) != expected:
            errors.append(name + " control changed")
    for name, expected in baseline["job_sha256"].items():
        job = jobs.get(name, {})
        shard = {"tests": "tests-shard", "tests-no-submodule": "tests-no-submodule-shard"}.get(name)
        # Strip ONLY this exact reviewed routing projection. Every other field
        # (including commands/env/matrices/step conditions) keeps its old hash.
        if shard and job.get("needs") == [shard, "delivery-route"] and job.get("if") == AGGREGATE_GUARD:
            job["needs"], job["if"] = shard, "${{ always() }}"
        elif not shard and job.get("needs") == ["delivery-route"] and job.get("if") == ROOT_GUARD:
            del job["needs"]
            del job["if"]
        if digest(jobs.get(name)) != expected:
            errors.append(name + " definition changed")
    return errors


def test_full_ci_coverage_parity_matches_reviewed_full_baseline(workflow, baseline):
    assert baseline["workflow"] == WORKFLOW
    assert set(baseline["job_sha256"]) == GATES | set(SHARDS)
    assert parity_errors(workflow, baseline) == []
    jobs = workflow["jobs"]
    for name, shards in SHARDS.items():
        assert jobs[name]["strategy"]["matrix"] == {"shard": shards}
    count = len(GATES) + sum(len(shards) for shards in SHARDS.values())
    assert count == baseline["expanded_jobs"] == 13


@pytest.mark.parametrize("name", sorted(GATES | set(SHARDS)))
def test_full_ci_coverage_parity_rejects_each_missing_or_conditional_job(
        workflow, baseline, name):
    missing = copy.deepcopy(workflow)
    del missing["jobs"][name]
    assert "job inventory changed" in parity_errors(missing, baseline)
    workflow["jobs"][name]["if"] = "${{ false }}"
    assert name + " definition changed" in parity_errors(workflow, baseline)


@pytest.mark.parametrize("name", sorted(SHARDS))
def test_full_ci_coverage_parity_rejects_a_missing_shard(workflow, baseline, name):
    workflow["jobs"][name]["strategy"]["matrix"]["shard"].pop()
    assert name + " definition changed" in parity_errors(workflow, baseline)


@pytest.mark.parametrize("name", sorted(GATES | set(SHARDS)))
@pytest.mark.parametrize("mutation", ["needs", "guard", "masking"])
def test_full_ci_coverage_parity_only_normalizes_exact_control_wiring(workflow, baseline, name, mutation):
    job = workflow["jobs"][name]
    if mutation == "needs":
        job["needs"].append("unrelated")
    elif mutation == "guard":
        job["if"] += " || true"
    else:
        job["continue-on-error"] = True
    assert name + " definition changed" in parity_errors(workflow, baseline)


@pytest.mark.parametrize("name", sorted(CONTROLS))
@pytest.mark.parametrize("mutation", ["if", "permissions", "steps", "needs", "continue-on-error"])
def test_full_ci_coverage_parity_control_projection_cannot_hide_mutations(workflow, baseline, name, mutation):
    workflow["jobs"][name][mutation] = True
    assert name + " control changed" in parity_errors(workflow, baseline)


@pytest.mark.parametrize("name", sorted(GATES | set(SHARDS)))
def test_full_ci_coverage_parity_rejects_changed_steps_or_failure_masking(
        workflow, baseline, name):
    changed = copy.deepcopy(workflow)
    changed["jobs"][name]["steps"].pop()
    assert name + " definition changed" in parity_errors(changed, baseline)
    workflow["jobs"][name]["continue-on-error"] = True
    assert name + " definition changed" in parity_errors(workflow, baseline)


@pytest.mark.parametrize("name", sorted(SHARDS))
def test_full_ci_coverage_parity_rejects_checkout_mode_changes(workflow, baseline, name):
    checkout = workflow["jobs"][name]["steps"][0]["with"]
    checkout["submodules"] = not checkout["submodules"]
    assert name + " definition changed" in parity_errors(workflow, baseline)


@pytest.mark.parametrize("key,value", [
    ("inputs", {"fast": {"type": "boolean", "default": True}}),
    ("secrets", {"token": {"required": False}}),
    ("outputs", {"passed": {"value": "true"}}),
])
def test_full_ci_coverage_parity_rejects_reuse_inputs_secrets_or_outputs(
        workflow, baseline, key, value):
    workflow["on"]["workflow_call"] = {key: value}
    assert "reuse is not parameterless" in parity_errors(workflow, baseline)


@pytest.mark.parametrize("event", ["pull_request", "push", "schedule", "workflow_dispatch"])
def test_full_ci_coverage_parity_rejects_changed_ordinary_events(workflow, baseline, event):
    del workflow["on"][event]
    assert "ordinary events changed" in parity_errors(workflow, baseline)


def test_full_ci_coverage_parity_rejects_altered_context_and_global_settings(workflow, baseline):
    workflow["env"]["OPENREPOTOOLS_COMPOSED"] = "1"
    assert "environment changed" in parity_errors(workflow, baseline)
    workflow["permissions"] = {"contents": "write"}
    assert "workflow settings changed" in parity_errors(workflow, baseline)


def test_full_ci_coverage_parity_caller_is_pr_only_same_commit_and_not_admission(reader):
    caller = reader(REPO / CALLER)
    assert set(caller["on"]) == {"pull_request"}
    trigger = caller["on"]["pull_request"]
    assert trigger["types"] == ["opened", "synchronize", "reopened"]
    assert set(trigger) == {"types", "paths"}
    assert set(trigger["paths"]) == {
        WORKFLOW, CALLER, BASELINE, ".github/ci/ci_shards.py", ".github/ci/weights.json",
        "tests/test_tests_workflow.py", "tests/test_ci_shards.py",
        "tests/test_full_ci_coverage_parity.py", ".github/ci/delivery-policy.json",
        ".github/ci/delivery_route.py", ".github/ci/delivery_evidence.py", ".github/ci/delivery_verify.py",
        ".github/ci/delivery_v13.py", ".github/ci/delivery-v13-policy.json",
        ".github/ci/delivery-v13.md", "tests/test_ci_v13_delivery.py",
        ".github/workflows/task-set-candidate.yml", ".github/workflows/task-set-candidate-shadow.yml",
        ".mergify.yml", "tests/test_ci_cutover.py", "tests/test_ci_cutover_repair.py",
        ".github/ci/v13_shadow.py", ".github/ci/shadow_scope.py", ".github/ci/v13-shadow-profiles.json",
        ".github/ci/v13-shadow.md", ".github/workflows/v13-shadow.yml", "tests/test_v13_shadow.py"}
    assert caller["permissions"] == {"contents": "read"}
    assert set(caller["jobs"]) == {"parity", "full-ci", "qualification"}
    assert caller["jobs"]["full-ci"] == {
        "needs": "parity", "uses": "./" + WORKFLOW, "permissions": READ_PERMISSIONS}
    parity = caller["jobs"]["parity"]
    assert "if" not in parity and "continue-on-error" not in parity
    assert any(step.get("run") == "bash tests/run.sh -k full_ci_coverage_parity"
               for step in parity["steps"])
    gate = caller["jobs"]["qualification"]
    assert gate["needs"] == ["parity", "full-ci"]
    assert gate["if"] == "${{ always() }}"
    assert "continue-on-error" not in gate
    assert gate["steps"][0]["env"] == {
        "PARITY_RESULT": "${{ needs.parity.result }}",
        "FULL_CI_RESULT": "${{ needs.full-ci.result }}"}


@pytest.mark.parametrize("parity,full,success", [
    ("success", "success", True), ("failure", "success", False),
    ("skipped", "success", False), ("cancelled", "success", False),
    ("success", "failure", False), ("success", "skipped", False),
    ("success", "cancelled", False), ("success", "", False),
    ("", "success", False), ("success", "success\necho forged", False),
])
def test_full_ci_coverage_parity_qualification_fails_closed(reader, parity, full, success):
    caller = reader(REPO / CALLER)
    step = caller["jobs"]["qualification"]["steps"][0]
    result = subprocess.run(["bash", "-euo", "pipefail", "-c", step["run"]],
                            env=dict(os.environ, PARITY_RESULT=parity, FULL_CI_RESULT=full),
                            capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) is success, result.stdout + result.stderr
