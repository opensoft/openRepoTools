# SPDX-License-Identifier: Apache-2.0
"""Offline disabled/fixture-enabled v1.3 delivery. No live or settings writes."""

from __future__ import annotations

import copy
import importlib
import json
import subprocess

import pytest

from conftest import REPO
from test_ci_delivery import (batch, base_changes, commit, delivery, git, request_for,
                              threads, verify)
from test_ci_cutover import (cutover, duplicate_fixture, enable_fixture, install_artifact,
                            qualified_fixture, run_row)


@pytest.fixture
def v13(delivery):
    return importlib.import_module("delivery_v13")


def write(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.fixture
def v13_batch(batch, cutover, v13, request):
    root = batch["root"]
    projection = v13.projection
    write(root, ".github/workflows/tests.yml", "# required-engine foundation\n")
    write(root, projection.BASELINE, json.dumps({
        "environment": {"OPENREPOTOOLS_REQUIRE_PG": "1"}, "expanded_jobs": 13}))
    for path in projection.P01_FILES:
        write(root, path, "# required-engine foundation\n")
    for task in projection.P01_TASKS:
        write(root, projection.MARKERS + task, "")
    foundation = commit(root, "P01")
    policy = json.loads((REPO / projection.CONFIG).read_text())
    policy["prerequisite"]["head"] = foundation
    policy["prerequisite"]["blobs"] = {
        path: git(root, "rev-parse", foundation + ":" + path) for path in projection.CONTROL_PATHS}
    heads = []
    for number, (name, profile) in zip((7, 8), policy["profiles"].items()):
        git(root, "checkout", "-q", "--detach", foundation)
        write(root, profile["files"][0], "# " + name + " test\n")
        for task in profile["tasks"]:
            write(root, projection.MARKERS + task, "")
        head = commit(root, name)
        heads.append(head)
        profile["source"] = {"number": number, "head": head, "branch": "feature/" + str(number)}
    git(root, "checkout", "-q", "--detach", foundation)
    write(root, projection.CONFIG, json.dumps(policy))
    write(root, v13.CONFIG, json.dumps({"schema_version": 1, "scope": v13.SCOPE,
                                       "enabled": getattr(request, "param", True)}))
    write(root, ".github/ci/delivery-policy.json", '{"schema_version":1,"enabled":true}')
    write(root, "unrelated-later-main", "preserve later main\n")
    base = commit(root, "later trusted main")
    prefixes, previous = [], base
    for head in heads:
        tree = git(root, "merge-tree", "--write-tree", previous, head)
        previous = git(root, "commit-tree", tree, "-p", previous, "-p", head, "-m", "candidate")
        prefixes.append(previous)
    replacements = dict(zip([batch["base"], *batch["heads"], *batch["prefixes"]],
                            [base, *heads, *prefixes]))
    for key in ("data", "env", "event"):
        text = json.dumps(batch[key])
        for before, after in replacements.items():
            text = text.replace(before, after)
        batch[key] = json.loads(text)
    batch.update(base=base, heads=heads, candidate=previous, prefixes=prefixes,
                 foundation=foundation, policy=policy)
    batch["prs"] = {number: batch["data"][f"pulls/{number}"] for number in (7, 8)}
    for number, name in zip((7, 8), ("P03", "P05")):
        batch["prs"][number]["body"] = (
            f"CI-Shadow: {v13.SCOPE}\nCI-Delivery: {v13.SCOPE}\nCI-Task-Set: {name}")
        batch["data"][f"commits/{heads[number - 7]}/pulls?per_page=100"] = [batch["prs"][number]]
    batch["data"]["pulls/88"] = {
        "number": 88, "state": "closed", "merged": True, "draft": False,
        "merge_commit_sha": foundation,
        "head": {"sha": foundation, "ref": "p01", "repo": {"full_name": cutover.REPOSITORY}},
        "base": {"sha": base, "ref": "main", "repo": {"full_name": cutover.REPOSITORY}}}
    enable_fixture(cutover, batch)
    # enable_fixture is legacy-only fixture scaffolding, not real source intent.
    for pr in batch["prs"].values():
        pr["body"] = pr["body"].removesuffix("\nCI-Delivery: claude-current")
    return batch


def route_source(cutover, batch, body=None):
    pr = batch["prs"][7]
    env = dict(batch["env"], GITHUB_EVENT_NAME="pull_request", GITHUB_RUN_ID="501",
               GITHUB_RUN_ATTEMPT="1", GITHUB_SHA=batch["prefixes"][0], GITHUB_REF="refs/pull/7/merge")
    event = {"action": "synchronize", "number": 7, "pull_request": copy.deepcopy(pr)}
    if body is not None:
        event["pull_request"]["body"] = body
    batch["data"]["actions/runs/501"] = run_row(cutover, 501, pr["head"]["sha"],
                                                  pr["head"]["ref"], cutover.DIRECT, "pull_request")
    return cutover.route(env, event, batch["root"], request_for(batch),
                         threads=lambda number: threads(number, batch), base_changes=base_changes)


@pytest.fixture
def v13_artifact(cutover, v13_batch, delivery):
    batch = v13_batch
    proof = verify(delivery, batch)
    run = run_row(cutover, 601, batch["candidate"], "mergify/merge-queue/0123456789", cutover.evidence.CALLER)
    env = dict(batch["env"], GITHUB_RUN_ID="601", GITHUB_RUN_ATTEMPT="1")
    batch["data"]["actions/runs/601"] = run
    record = cutover.evidence.make_record(proof, "admission", env, request_for(batch))
    return {"run": run, "record": record, "env": env}


def test_ci_v13_delivery_committed_policy_disabled_and_legacy_unchanged(v13, cutover):
    assert json.loads((REPO / v13.CONFIG).read_text()) == {
        "schema_version": 1, "scope": v13.SCOPE, "enabled": False}
    assert cutover.enabled(REPO) is True
    assert v13.projection.read_policy(REPO, "HEAD")["efficiency_enabled"] is False


def test_ci_v13_delivery_fixture_source_uses_test_merge_without_rewriting_owner_head(cutover, v13_batch):
    batch = v13_batch
    assert git(batch["root"], "merge-base", batch["base"], batch["heads"][0]) == batch["foundation"]
    result = route_source(cutover, batch)
    assert result["omit_full"] is True and result["mode"] == "source"
    assert "queue_admission" not in result


@pytest.mark.parametrize("v13_batch", [False], indirect=True)
def test_ci_v13_delivery_disabled_source_and_candidate_remain_full(cutover, delivery, v13_batch):
    assert route_source(cutover, v13_batch) == cutover.FULL
    with pytest.raises(ValueError, match="not enabled"):
        verify(delivery, v13_batch)


@pytest.mark.parametrize("syntax", ["def test_example():\n    assert True\n", "def invalid(\n"])
def test_ci_v13_delivery_fast_parses_sql_test_merge_without_database(delivery, v13_batch, syntax):
    batch, root = v13_batch, v13_batch["root"]
    write(root, "tests/test_sql_register_import.py", syntax)
    tree_head = commit(root, "SQL syntax fixture")
    tested = git(root, "commit-tree", git(root, "rev-parse", tree_head + "^{tree}"),
                 "-p", batch["base"], "-p", tree_head, "-m", "test merge")
    git(root, "checkout", "-q", "--detach", tested)
    env = dict(batch["env"], GITHUB_EVENT_NAME="pull_request", GITHUB_SHA=tested)
    event = {"action": "synchronize", "pull_request": {
        "base": {"sha": batch["base"]}, "head": {"sha": tree_head}}}
    if "invalid" in syntax:
        with pytest.raises(SyntaxError):
            delivery.verify_fast(env, event, root)
    else:
        assert delivery.verify_fast(env, event, root)["tested"] == tested


@pytest.mark.parametrize("body", ["", "CI-Shadow: sql-register-v13",
    "CI-Shadow: sql-register-v13\nCI-Delivery: sql-register-v13\nCI-Task-Set: P05"])
def test_ci_v13_delivery_event_intent_cannot_be_replaced_by_live_prose(cutover, v13_batch, body):
    assert route_source(cutover, v13_batch, body) == cutover.FULL


@pytest.mark.parametrize("failure", ["disabled", "missing", "wrong-schema", "duplicate-key", "extra-key",
    "p01-open", "p01-head", "p01-race", "dependency", "duplicate-intent", "task-set", "head", "number",
    "branch", "base", "draft", "closed", "merged", "fast-failed", "review-stale", "source-ref"])
def test_ci_v13_delivery_unsafe_source_refuses(cutover, delivery, v13_batch, v13, failure):
    batch, root = v13_batch, v13_batch["root"]
    pr, data = batch["prs"][7], batch["data"]
    if failure in {"disabled", "missing", "wrong-schema", "duplicate-key", "extra-key"}:
        values = {"disabled": '{"schema_version":1,"scope":"sql-register-v13","enabled":false}',
                  "wrong-schema": '{"schema_version":true,"scope":"sql-register-v13","enabled":true}',
                  "duplicate-key": '{"schema_version":1,"scope":"sql-register-v13","enabled":false,"enabled":true}',
                  "extra-key": '{"schema_version":1,"scope":"sql-register-v13","enabled":true,"anything":1}'}
        if failure == "missing":
            (root / v13.CONFIG).unlink()
        else:
            write(root, v13.CONFIG, values[failure])
        commit(root, "unqualified policy")
        with pytest.raises((ValueError, subprocess.SubprocessError)):
            v13.configuration(root, "HEAD")
        return
    if failure == "p01-open": data["pulls/88"].update(state="open", merged=False)
    elif failure == "p01-head": data["pulls/88"]["head"]["sha"] = "f" * 40
    elif failure == "dependency": pr["body"] += "\n Depends-On: #88"
    elif failure == "duplicate-intent": pr["body"] += "\nCI-Delivery: sql-register-v13"
    elif failure == "task-set": pr["body"] = pr["body"].replace("P03", "P05")
    elif failure == "head": pr["head"]["sha"] = batch["heads"][1]
    elif failure == "number":
        pr["number"] = 9
        data["pulls/9"] = pr
    elif failure == "branch": pr["head"]["ref"] = "feature/unknown"
    elif failure == "base": pr["base"]["ref"] = "p01"
    elif failure == "draft": pr["draft"] = True
    elif failure == "closed": pr["state"] = "closed"
    elif failure == "merged": pr["merged"] = True
    elif failure == "fast-failed": data["actions/jobs/907"]["conclusion"] = "failure"
    elif failure == "review-stale": data["issues/7/comments?per_page=100"][0]["body"] = "quota exhausted"
    elif failure == "source-ref": data["git/ref/heads/feature/7"]["object"]["sha"] = "f" * 40
    reader, reads = request_for(batch), []
    def request(repo, endpoint):
        value = reader(repo, endpoint)
        if failure == "p01-race" and endpoint == "pulls/88":
            reads.append(True)
            if len(reads) > 1:
                value["draft"] = True
        return value
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        verify(delivery, batch, request)
    if failure not in {"review-stale", "p01-race"}:
        assert route_source(cutover, batch) == cutover.FULL


def test_ci_v13_delivery_exact_homogeneous_batch_has_scope_bound_proof(delivery, v13_batch, v13):
    proof = verify(delivery, v13_batch)
    assert proof["scope"] == v13.SCOPE and proof["full_ci_required"] is True
    assert [row["head"] for row in proof["members"]] == v13_batch["heads"]
    assert proof["tree"] == git(v13_batch["root"], "rev-parse", v13_batch["candidate"] + "^{tree}")


def test_ci_v13_delivery_mixed_eligible_domains_refuse(delivery, v13_batch):
    batch, root = v13_batch, v13_batch["root"]
    write(root, "tests/test_claude_current.py", "# independent legacy task\n")
    head = commit(root, "legacy member")
    tree = git(root, "merge-tree", "--write-tree", batch["prefixes"][0], head)
    candidate = git(root, "commit-tree", tree, "-p", batch["prefixes"][0], "-p", head, "-m", "mixed")
    text = json.dumps(batch["data"]).replace(batch["heads"][1], head).replace(batch["candidate"], candidate)
    batch["data"] = json.loads(text)
    batch["prs"] = {number: batch["data"][f"pulls/{number}"] for number in (7, 8)}
    batch["prs"][8]["body"] = "CI-Shadow: claude-current\nCI-Delivery: claude-current"
    batch["data"][f"commits/{head}/pulls?per_page=100"] = [batch["prs"][8]]
    batch["env"]["GITHUB_SHA"] = batch["event"]["after"] = candidate
    git(root, "checkout", "-q", "--detach", batch["base"])
    with pytest.raises(ValueError, match="mixes delivery scopes"):
        verify(delivery, batch)


@pytest.mark.parametrize("path", [".github/workflows/tests.yml", ".github/ci/full-ci-baseline.json",
    "tests/pgcluster.py", "tests/conftest.py", "tests/sql_register_gate.py",
    "tests/sql_register_helpers.py", "tests/sql_register_landed/T200"])
def test_ci_v13_delivery_foundation_contract_changes_refuse(v13, v13_batch, path):
    write(v13_batch["root"], path, "unreviewed foundation change\n")
    changed = commit(v13_batch["root"], "contract drift")
    with pytest.raises(subprocess.SubprocessError):
        v13.configuration(v13_batch["root"], changed)


def test_ci_v13_delivery_candidate_duplicate_requires_scoped_admission(cutover, v13_batch, v13_artifact):
    env, event, data = duplicate_fixture(cutover, v13_batch, v13_artifact)
    result = cutover.route(env, event, v13_batch["root"], request_for(v13_batch), lambda _id: data,
                           lambda number: threads(number, v13_batch), base_changes)
    assert result["mode"] == "candidate" and result["omit_full"] is True


@pytest.mark.parametrize("count", [1, 2])
def test_ci_v13_delivery_historical_landing_matches_all_prefix_trees(cutover, v13_batch, v13_artifact, count):
    env, event, data, _jobs, _row = qualified_fixture(cutover, v13_batch, v13_artifact, count)
    result = cutover.route(env, event, v13_batch["root"], request_for(v13_batch), lambda _id: data)
    assert result["mode"] == "landing" and result["omit_full"] is True


@pytest.mark.parametrize("scope", ["unknown", "claude-current", None])
def test_ci_v13_delivery_receipt_scope_tampering_refuses(cutover, v13_batch, v13_artifact, scope):
    if scope is None:
        v13_artifact["record"]["proof"].pop("scope")
    else:
        v13_artifact["record"]["proof"]["scope"] = scope
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        record = cutover.evidence.record_valid(v13_artifact["record"], v13_artifact["run"], "admission")
        cutover.evidence.candidate_chain(record, v13_batch["root"])


@pytest.mark.parametrize("failure", ["failed", "skipped", "missing", "rerun", "workflow", "foundation", "policy"])
def test_ci_v13_delivery_incomplete_or_changed_heavy_remains_full(cutover, v13_batch, v13_artifact, v13, failure):
    batch = v13_batch
    env, event, data, jobs, _row = qualified_fixture(cutover, batch, v13_artifact)
    if failure in {"failed", "skipped"}: jobs[0]["conclusion"] = failure
    elif failure == "missing": jobs.pop()
    elif failure == "rerun": v13_artifact["run"]["run_attempt"] = 2
    elif failure == "workflow": v13_artifact["run"]["referenced_workflows"][0]["sha"] = batch["base"]
    elif failure in {"foundation", "policy"}:
        path = v13.projection.P01_FILES[0] if failure == "foundation" else v13.CONFIG
        write(batch["root"], path, "changed after qualification\n")
        changed = commit(batch["root"], "later drift")
        batch["data"]["git/ref/heads/main"]["object"]["sha"] = changed
    assert cutover.route(env, event, batch["root"], request_for(batch), lambda _id: data) == cutover.FULL
