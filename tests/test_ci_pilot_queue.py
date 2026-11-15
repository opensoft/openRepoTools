# SPDX-License-Identifier: Apache-2.0
"""Offline pilot config regressions, not a Mergify service or stack-graph simulator.

Evaluate only the documented condition grammar used by this file. Schema
validation is separate; live access/queue/candidate acceptance is not claimed.
"""

from __future__ import annotations

import importlib.util
import re
import sys

import pytest

from conftest import REPO, UPSTREAM, NEEDS_UPSTREAM

GATES = {"guard-launch-mode", "tests", "tests-no-submodule", "package"}
CHECKS = {"@github-actions/" + name for name in GATES}
REFERENCES = [".github/ci/task-set-delivery.md", ".github/ci/batching-pilot.md"]
pytestmark = NEEDS_UPSTREAM


@pytest.fixture(scope="module")
def reader():
    spec = importlib.util.spec_from_file_location(
        "manual_queue_yaml", UPSTREAM / "scripts/repo_shape.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_yaml


@pytest.fixture(scope="module")
def config(reader):
    return reader(REPO / ".mergify.yml")


@pytest.fixture
def ready():
    return {"draft": False, "closed": False, "from-fork": False,
            "label": ["batch-pilot-reviewed"], "head": "ci/batch-pilot/first",
            "base": "main", "body": "", "files": REFERENCES[:1],
            "check-success": sorted(CHECKS), "sender-permission": "write"}


def matches(condition, context):
    """Bounded test evaluator; unknown syntax/attributes cannot silently pass."""
    if isinstance(condition, dict):
        assert len(condition) == 1
        operator, children = next(iter(condition.items()))
        assert operator in {"and", "or"}
        return (all if operator == "and" else any)(matches(c, context) for c in children)
    parsed = re.fullmatch(r"(-?)(#?)([a-z-]+)(?:(~=|>=|<=|=)(.*))?", condition)
    assert parsed is not None, condition
    negative, counted, attribute, operator, wanted = parsed.groups()
    if attribute not in context:
        return False
    value = context[attribute]
    if counted:
        value, wanted = len(value), int(wanted)
    elif attribute == "number":
        wanted = int(wanted)
    if operator is None:
        assert isinstance(value, bool)
        result = value
    elif operator == "~=":
        values = value if isinstance(value, list) else [value]
        result = any(re.search(wanted, item) is not None for item in values)
    elif operator == "=":
        result = wanted in value if isinstance(value, list) else value == wanted
    elif attribute == "sender-permission":
        permissions = {"none": 0, "read": 1, "triage": 2, "write": 3,
                       "maintain": 4, "admin": 5}
        result = permissions[value] >= permissions[wanted]
    else:
        assert counted and operator in {">=", "<="}
        result = value >= wanted if operator == ">=" else value <= wanted
    return not result if negative else result


def admitted(config, context, index=0):
    return all(matches(c, context) for c in config["queue_rules"][index]["queue_conditions"])


def test_manual_mergify_queue_is_bounded_and_has_no_automatic_admission(config):
    assert set(config) == {"merge_queue", "commands_restrictions", "queue_rules"}
    assert config["merge_queue"] == {
        "mode": "serial", "max_parallel_checks": 1, "queue_controls_comment": False,
        "reset_on_external_merge": "always", "skip_intermediate_results": False}
    assert [q["name"] for q in config["queue_rules"]] == [
        "openrepotools-docs-pilot", "openrepotools-real-code-35-36", "openrepotools-code",
        "openrepotools-claude-current", "openrepotools-sql-register-v13"]
    queue = config["queue_rules"][0]
    assert queue["name"] == "openrepotools-docs-pilot"
    assert queue["batch_size"] == 2
    assert queue["batch_max_wait_time"] == "60 seconds"
    assert queue["max_checks_retries"] == 0
    assert queue["batch_max_failure_resolution_attempts"] == 0
    assert queue["checks_timeout"] == "90 minutes"
    assert queue["merge_method"] == "merge"
    # The service defaults to refusing external queue edits; never opt in.
    assert queue.get("allow_queue_branch_edit", False) is False
    assert set(config["commands_restrictions"]) == {"queue"}
    assert config["commands_restrictions"]["queue"]["conditions"] == ["sender-permission>=write"]


def test_manual_mergify_queue_requires_full_checks_on_pr_and_candidate(config):
    queue = config["queue_rules"][0]
    expected = {"check-success=" + check for check in CHECKS}
    assert expected <= {c for c in queue["queue_conditions"] if isinstance(c, str)}
    assert set(queue["merge_conditions"]) == expected
    # No advisory result, targeted verify or neutral/skipped condition is a gate.
    assert all(c.startswith("check-success=@github-actions/") for c in queue["merge_conditions"])


def test_manual_mergify_queue_uses_existing_full_ci_on_every_pr_base(reader):
    workflow = reader(REPO / ".github/workflows/tests.yml")
    assert set(workflow["on"]["pull_request"]) == {"types"}
    assert set(workflow["on"]["pull_request"]["types"]) == {"opened", "synchronize", "reopened"}
    assert workflow["on"]["push"]["branches"] == ["main", "release/v*"]
    assert "schedule" in workflow["on"] and "workflow_dispatch" in workflow["on"]
    assert GATES <= set(workflow["jobs"])
    for name in GATES:
        # Existing aggregators run even on shard failure; no draft/path skip.
        from test_full_ci_coverage_parity import ROOT_GUARD, AGGREGATE_GUARD
        assert workflow["jobs"][name].get("if") in (ROOT_GUARD, AGGREGATE_GUARD)
    import json
    # Scoped enablement preserves this full entry; the old docs queue is out of scope.
    assert json.loads((REPO / ".github/ci/delivery-policy.json").read_text())["enabled"] is True


@pytest.mark.parametrize("files", [REFERENCES[:1], REFERENCES[1:], REFERENCES])
def test_manual_mergify_queue_accepts_only_intended_reference_vectors(config, ready, files):
    ready["files"] = files
    assert admitted(config, ready)


@pytest.mark.parametrize("path", ["lane-start", "claude-current", "AGENTS.md",
    "tests/test_ci_pilot.py", ".mergify.yml", ".github/workflows/tests.yml",
    ".github/workflows/release.yml", ".github/ci/task-set-delivery.md.evil",
    ".github/ci/task-set-delivery.md\n", ".github/ci/unrelated.md"])
def test_manual_mergify_queue_rejects_mixed_or_unknown_paths(config, ready, path):
    ready["files"] = REFERENCES[:1] + [path]
    assert not admitted(config, ready)


@pytest.mark.parametrize("attribute,value", [("draft", True), ("closed", True),
    ("from-fork", True), ("label", []), ("label", ["stack-ci-reviewed"]),
    ("head", "fix/existing-lane"), ("head", "ci/batch-pilot/"),
    ("base", "release/v1.2"), ("base", "fix/existing-lane"), ("files", []),
    ("files", REFERENCES + [REFERENCES[0]])])
def test_manual_mergify_queue_refuses_ordinary_or_incomplete_prs(config, ready, attribute, value):
    ready[attribute] = value
    assert not admitted(config, ready)


def test_manual_mergify_queue_upper_base_needs_explicit_predecessor_marker(config, ready):
    ready["head"], ready["base"] = "ci/batch-pilot/second", "ci/batch-pilot/first"
    assert not admitted(config, ready)
    ready["body"] = "Task set two\n\nDepends-On: #42\n"
    assert admitted(config, ready)
    ready["body"] = "Mentions Depends-On: #42 in prose only"
    assert not admitted(config, ready)


@pytest.mark.parametrize("gate", sorted(CHECKS))
@pytest.mark.parametrize("outcome", ["missing", "pending", "skipped", "neutral", "failure", "cancelled"])
def test_manual_mergify_queue_each_gate_must_succeed(config, ready, gate, outcome):
    ready["check-success"].remove(gate)
    ready["check-" + outcome] = [gate]
    assert not admitted(config, ready)
    assert not all(matches(c, ready) for c in config["queue_rules"][0]["merge_conditions"])


def test_manual_mergify_queue_unqualified_or_other_app_checks_are_not_enough(config, ready):
    ready["check-success"] = sorted(GATES) + ["@another-app/" + name for name in GATES]
    assert not admitted(config, ready)


@pytest.mark.parametrize("permission", ["none", "read", "triage", "write", "maintain", "admin"])
def test_manual_mergify_queue_command_requires_repository_writer(config, ready, permission):
    ready["sender-permission"] = permission
    conditions = config["commands_restrictions"]["queue"]["conditions"]
    assert all(matches(c, ready) for c in conditions) == (permission in {"write", "maintain", "admin"})


@pytest.mark.parametrize("attribute", ["head", "base", "label", "files", "check-success"])
def test_manual_mergify_queue_missing_context_cannot_grant_scope(config, ready, attribute):
    del ready[attribute]
    assert not admitted(config, ready)


def test_manual_mergify_queue_references_exist_and_shared_agents_find_them():
    for reference in REFERENCES:
        assert (REPO / reference).is_file()
    assert "batching-pilot.md" in (REPO / REFERENCES[0]).read_text()
    assert ".github/ci/task-set-delivery.md" in (REPO / "AGENTS.md").read_text()
    assert "Read AGENTS.md." in (REPO / "CLAUDE.md").read_text()


@pytest.fixture(params=[35, 36])
def real_ready(request):
    number = str(request.param)
    return {"number": request.param, "draft": False, "closed": False, "from-fork": False,
            "base": "main", "head": {"35": "fix/exit-refusals-keep-their-words",
            "36": "fix/a14-three-nudge-race"}[number],
            "files": {"35": ["lane-handoff", "tests/test_a23_lane_handoff.py"],
            "36": ["tests/test_lane_helpers.sh"]}[number],
            "check-success": sorted(CHECKS)}


def test_real_code_queue_is_manual_bounded_and_retains_full_ci(config, real_ready):
    queue = config["queue_rules"][1]
    assert admitted(config, real_ready, 1)
    assert not admitted(config, real_ready)  # Docs scope is not widened.
    assert queue["batch_size"] == 2
    assert queue["batch_max_wait_time"] == "60 seconds"
    assert queue["max_checks_retries"] == 0
    assert queue["batch_max_failure_resolution_attempts"] == 0
    assert queue["checks_timeout"] == "90 minutes"
    assert queue["merge_method"] == "merge"
    assert queue.get("allow_queue_branch_edit", False) is False
    expected = {"check-success=" + check for check in CHECKS}
    assert expected <= {c for c in queue["queue_conditions"] if isinstance(c, str)}
    assert set(queue["merge_conditions"]) == expected


@pytest.mark.parametrize("attribute,value", [("number", 32), ("number", 37),
    ("head", "fix/other-lane"), ("base", "release/v1.2"), ("base", "fix/predecessor"),
    ("draft", True), ("closed", True), ("from-fork", True), ("files", [])])
def test_real_code_queue_rejects_unapproved_identity_or_state(config, real_ready, attribute, value):
    real_ready[attribute] = value
    assert not admitted(config, real_ready, 1)


@pytest.mark.parametrize("path", [".mergify.yml", ".github/workflows/tests.yml",
    ".github/workflows/release.yml", "lane-start", "lane-handoff\n",
    "tests/test_lane_helpers.sh.evil", "tests/test_a23_lane_handoff.py\n"])
def test_real_code_queue_rejects_mixed_paths(config, real_ready, path):
    real_ready["files"].append(path)
    assert not admitted(config, real_ready, 1)


def test_real_code_queue_cannot_swap_the_two_pr_numbers(config, real_ready):
    real_ready["number"] = 36 if real_ready["number"] == 35 else 35
    assert not admitted(config, real_ready, 1)


@pytest.mark.parametrize("gate", sorted(CHECKS))
@pytest.mark.parametrize("outcome", ["missing", "pending", "skipped", "neutral", "failure", "cancelled"])
def test_real_code_queue_every_gate_must_succeed(config, real_ready, gate, outcome):
    real_ready["check-success"].remove(gate)
    real_ready["check-" + outcome] = [gate]
    assert not admitted(config, real_ready, 1)
    assert not all(matches(c, real_ready) for c in config["queue_rules"][1]["merge_conditions"])


@pytest.mark.parametrize("attribute", ["number", "head", "base", "files", "check-success"])
def test_real_code_queue_missing_context_cannot_grant_scope(config, real_ready, attribute):
    del real_ready[attribute]
    assert not admitted(config, real_ready, 1)


@pytest.fixture
def code_ready():
    return {"draft": False, "closed": False, "from-fork": False,
            "base": "main", "head": "fix/small-task-set",
            "files": ["lane-handoff", "tests/test_a23_lane_handoff.py"],
            "check-success": sorted(CHECKS)}


def test_general_code_queue_is_manual_full_ci_and_bounded(config, code_ready):
    queue = config["queue_rules"][2]
    assert queue["name"] == "openrepotools-code"
    assert admitted(config, code_ready, 2)
    for key, value in {"batch_size": 2, "batch_max_wait_time": "60 seconds",
                       "batch_max_failure_resolution_attempts": 0,
                       "max_checks_retries": 0, "checks_timeout": "90 minutes",
                       "merge_method": "merge"}.items():
        assert queue[key] == value
    assert queue.get("allow_queue_branch_edit", False) is False
    expected = {"check-success=" + check for check in CHECKS}
    assert expected <= {c for c in queue["queue_conditions"] if isinstance(c, str)}
    assert set(queue["merge_conditions"]) == expected
    assert not any("label" in c for c in queue["queue_conditions"] if isinstance(c, str))
    assert "pull_request_rules" not in config  # No auto-enqueue rule.
    assert not admitted(config, code_ready, 0)  # Earlier scopes stay narrow.
    assert not admitted(config, code_ready, 1)


@pytest.mark.parametrize("path", ["claude-current", "claude-restart-check", "lane",
    "lane-end", "lane-handoff", "lane-rename", "lane-start", "lane-worktrees",
    "lanes", "lanes-edit.sh", "lanes-index", "link-estates", "openRepoTools",
    "park", "resume", "status", "repos.tsv", "README.md", "tests/test_new.py",
    "src/openrepotools/cli.py", "commands/handoff.md", "skills/handoff/SKILL.md",
    "features/009-manual-two-pr-queue/openspec/amendment.md"])
def test_general_code_queue_accepts_known_normal_paths(config, code_ready, path):
    code_ready["files"] = [path]
    assert admitted(config, code_ready, 2)


@pytest.mark.parametrize("path", [".mergify.yml", ".github/workflows/tests.yml",
    ".github/workflows/release.yml", ".github/ci/pilot_scope.py",
    ".github/release-build-requirements.txt", "contracts/openreposhape-pin.yaml",
    "upstream/openRepoShape", ".gitmodules", "pyproject.toml", "AGENTS.md",
    "CLAUDE.md", "src/openrepotools/_release.py", "new-command", "docs/new.md",
    "tests/", "tests/test_new.py\n", "lane-handoff.evil", "lane-handoff\n"])
@pytest.mark.parametrize("mixed", [False, True])
def test_general_code_queue_rejects_unknown_control_release_and_mixed_paths(
        config, code_ready, path, mixed):
    code_ready["files"] = (["lane-handoff"] if mixed else []) + [path]
    assert not admitted(config, code_ready, 2)


@pytest.mark.parametrize("attribute,value", [("draft", True), ("closed", True),
    ("from-fork", True), ("base", "release/v1.2"), ("base", "fix/predecessor"),
    ("head", "release/v1.2"), ("head", "verify/lane/task"),
    ("head", "mergify/merge-queue/123"), ("head", "ci/batch-pilot/first"),
    ("files", [])])
def test_general_code_queue_refuses_unsupported_state_or_topology(
        config, code_ready, attribute, value):
    code_ready[attribute] = value
    assert not admitted(config, code_ready, 2)


@pytest.mark.parametrize("gate", sorted(CHECKS))
@pytest.mark.parametrize("outcome", ["missing", "pending", "skipped", "neutral", "failure", "cancelled"])
def test_general_code_queue_every_full_gate_must_succeed(config, code_ready, gate, outcome):
    code_ready["check-success"].remove(gate)
    code_ready["check-" + outcome] = [gate]
    assert not admitted(config, code_ready, 2)
    assert not all(matches(c, code_ready) for c in config["queue_rules"][2]["merge_conditions"])


def test_general_code_queue_other_app_or_unqualified_success_is_insufficient(config, code_ready):
    code_ready["check-success"] = sorted(GATES) + ["@another-app/" + name for name in GATES]
    assert not admitted(config, code_ready, 2)


@pytest.mark.parametrize("attribute", ["draft", "closed", "from-fork", "head", "base", "files", "check-success"])
def test_general_code_queue_missing_context_refuses(config, code_ready, attribute):
    del code_ready[attribute]
    assert not admitted(config, code_ready, 2)


def test_general_code_queue_operator_procedure_is_shared():
    text = (REPO / ".github/ci/batching-pilot.md").read_text()
    assert "@mergifyio queue openrepotools-code" in text
    assert "operator attestation" in text
    assert "exact-head Codex review" in text
    assert "main-only" in text
    assert "batching-pilot.md" in (REPO / ".github/ci/task-set-delivery.md").read_text()
