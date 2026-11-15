# SPDX-License-Identifier: Apache-2.0
"""Offline disabled/fixture-enabled v1.3 delivery. No live or settings writes."""

from __future__ import annotations

import copy
import importlib
import json
import subprocess

import pytest

from conftest import NEEDS_UPSTREAM, REPO
from test_ci_pilot_queue import reader as yaml_reader, matches
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
    policy = json.loads((REPO / "tests/fixtures/ci/v13-initial-profiles.json").read_text())
    mode = getattr(request, "param", True)
    if mode == "reviewed-pair":
        policy["profiles"] = {"P05": policy["profiles"]["P05"], "P06": {
            "tasks": ["T212", "T256", "T225", "T242"],
            "files": ["tests/test_sql_register_build_flip.py", "tests/test_sql_register_marker.py"]}}
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
        lineage = [head]
        count = 2 if mode == "reviewed-pair" else mode if type(mode) is int else 1
        for index in range(count - 1):
            write(root, profile["files"][0], f"# {name} reviewed fix {index}\n")
            head = commit(root, f"{name} reviewed fix {index}")
            lineage.append(head)
        heads.append(head)
        profile["source"] = {"number": number, "head": head, "branch": "feature/" + str(number)}
        if len(lineage) > 1:
            profile["source"]["commits"] = lineage
    git(root, "checkout", "-q", "--detach", foundation)
    write(root, projection.CONFIG, json.dumps(policy))
    write(root, v13.CONFIG, json.dumps({"schema_version": 1, "scope": v13.SCOPE,
                                       "enabled": mode if type(mode) is bool else True}))
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
    for number, name in zip((7, 8), policy["profiles"]):
        batch["prs"][number]["body"] = (
            f"CI-Shadow: {v13.SCOPE}\nCI-Delivery: {v13.SCOPE}\nCI-Task-Set: {name}")
        batch["data"][f"commits/{heads[number - 7]}/pulls?per_page=100"] = [batch["prs"][number]]
    batch["data"]["pulls/88"] = {
        "number": 88, "state": "closed", "merged": True, "draft": False,
        "user": {"login": "writer"},
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


def test_ci_v13_delivery_committed_policy_enabled_with_observer_and_legacy_unchanged(v13, cutover):
    assert json.loads((REPO / v13.CONFIG).read_text()) == {
        "schema_version": 1, "scope": v13.SCOPE, "enabled": True}
    assert cutover.enabled(REPO) is True
    assert v13.projection.read_policy(REPO, "HEAD")["efficiency_enabled"] is False


def test_ci_v13_delivery_committed_reviewed_pair_has_exact_qualified_provenance(v13):
    policy = v13.projection.read_policy(REPO, "HEAD")
    assert policy["spec_revision"] == "a3366afcc059b4686c990f4715c36dac9b1db05b"
    assert policy["prerequisite"]["head"] == "7f1141be15ac9c0d20c25c802ba9533c2fec811c"
    assert policy["foundation"] == {"head": "f0070e009bc6f183904549b69c710ef3982ca6e6", "blobs": {
        "tests/conftest.py": "5c4e3d182094bd149e9a68f826ae427dc9739b5d",
        "tests/pgcluster.py": "97871b78a222b1b3d7cc05ef1bc4bbbeeaa4419d",
        "tests/sql_register_gate.py": "0d0a30d3df586222b4b84a4e91cfb97260781d87",
        "tests/sql_register_helpers.py": "cc357350d3438fd59b232c9610273a71f4969bfb"}}
    assert policy["profiles"] == {
        "P05": {"source": {"number": 92,
            "head": "2a02cd9eba113329870ed7eba6efd470375b8739",
            "branch": "007-p05-readers-table-and-default-arms",
            "commits": ["3b71c7c532f0da0b6ebbe5aee1c7cc0213a0cd56",
                        "2a02cd9eba113329870ed7eba6efd470375b8739"]},
            "tasks": ["T217", "T235", "T259"],
            "files": ["tests/test_sql_register_readers.py"]},
        "P06": {"source": {"number": 94,
            "head": "bcc8858bf587fbe86b00264b41caca1b39ccfc72",
            "branch": "007-p06-refusing-flipped-wip-init-marker",
            "commits": ["b65d836b4ea939a43f89cf4e582055bb9e80f890",
                        "bcc8858bf587fbe86b00264b41caca1b39ccfc72"]},
            "tasks": ["T212", "T256", "T225", "T242"],
            "files": ["tests/test_sql_register_build_flip.py", "tests/test_sql_register_marker.py"]}}


@NEEDS_UPSTREAM
def test_ci_v13_delivery_manual_queue_is_heavy_held_and_preserves_existing_queues(yaml_reader):
    import hashlib
    config = yaml_reader(REPO / ".mergify.yml")
    assert set(config) == {"merge_queue", "commands_restrictions", "queue_rules"}
    assert config["commands_restrictions"]["queue"]["conditions"] == ["sender-permission>=write"]
    assert hashlib.sha256(json.dumps(config["queue_rules"][:4], sort_keys=True,
        separators=(",", ":")).encode()).hexdigest() == "7b9279424e5552fdee67d1a943adbc95af30c8c7a28889fd5d4f9be6e38097f3"
    queue = config["queue_rules"][4]
    assert queue["name"] == "openrepotools-sql-register-v13"
    assert queue["branch_protection_injection_mode"] == "queue"
    assert queue["batch_size"] == 2 and queue["batch_max_wait_time"] == "60 seconds"
    assert queue["batch_max_failure_resolution_attempts"] == queue["max_checks_retries"] == 0
    assert queue["checks_timeout"] == "90 minutes" and queue["merge_method"] == "merge"
    assert not queue.get("allow_queue_branch_edit", False)
    assert queue["merge_conditions"] == ["check-success=@github-actions/openrepotools-batch-heavy"]


@pytest.fixture
def v13_queue_source():
    return {"draft": False, "closed": False, "from-fork": False,
            "head": "007-p05-readers-table-and-default-arms", "base": "main",
            "body": "CI-Shadow: sql-register-v13\nCI-Delivery: sql-register-v13\nCI-Task-Set: P05",
            "files": ["tests/test_sql_register_readers.py", "tests/sql_register_landed/T217",
                      "tests/sql_register_landed/T235", "tests/sql_register_landed/T259"],
            "check-success": ["@github-actions/openrepotools-pr-fast", "@github-actions/openrepotools-delivery"]}


@NEEDS_UPSTREAM
@pytest.mark.parametrize("cut, eligible", [("P05", True), ("P06", True), ("P03", False)])
def test_ci_v13_delivery_reviewed_manual_queue_accepts_only_current_pair(
        yaml_reader, v13_queue_source, cut, eligible):
    context = v13_queue_source
    context["body"] = ("CI-Shadow: sql-register-v13\nCI-Delivery: sql-register-v13\n"
                       "CI-Task-Set: " + cut)
    if cut == "P06":
        context["head"] = "007-p06-refusing-flipped-wip-init-marker"
        context["files"] = ["tests/test_sql_register_build_flip.py", "tests/test_sql_register_marker.py",
                            *["tests/sql_register_landed/" + task for task in ("T212", "T256", "T225", "T242")]]
    elif cut == "P03":
        context["head"] = "007-p03-import-cutover-operator-tools"
        context["files"] = ["tests/test_sql_register_import.py", "tests/sql_register_landed/T211"]
    queue = yaml_reader(REPO / ".mergify.yml")["queue_rules"][4]
    assert all(matches(condition, context) for condition in queue["queue_conditions"]) is eligible


@NEEDS_UPSTREAM
@pytest.mark.parametrize("failure", [None, "foundation", "control", "product", "missing-fast", "other-app",
    "missing-delivery", "no-heavy", "wrong-heavy-app", "fork", "draft", "closed", "dependency", "base",
    "reserved-branch", "unknown-task", "wrong-scope", "too-many-files", "empty"])
def test_ci_v13_delivery_manual_queue_refusal_vectors(yaml_reader, v13_queue_source, failure):
    context = v13_queue_source
    queue = yaml_reader(REPO / ".mergify.yml")["queue_rules"][4]
    if failure in {"foundation", "control", "product"}:
        context["files"].append({"foundation": "tests/pgcluster.py", "control": ".mergify.yml",
                                 "product": "lanes-index"}[failure])
    elif failure in {"missing-fast", "missing-delivery"}:
        context["check-success"].remove("@github-actions/openrepotools-" + (
            "pr-fast" if failure == "missing-fast" else "delivery"))
    elif failure == "other-app": context["check-success"] = ["@other/pr-fast", "@other/delivery"]
    elif failure in {"fork", "draft", "closed"}:
        context["from-fork" if failure == "fork" else failure] = True
    elif failure == "dependency": context["body"] += "\n depends-on: #88"
    elif failure == "base": context["base"] = "p01"
    elif failure == "reserved-branch": context["head"] = "verify/preview"
    elif failure == "unknown-task": context["body"] = context["body"].replace("P05", "P02")
    elif failure == "wrong-scope": context["body"] = context["body"].replace("sql-register-v13", "claude-current")
    elif failure == "too-many-files": context["files"] *= 4
    elif failure == "empty": context["files"] = []
    eligible = all(matches(condition, context) for condition in queue["queue_conditions"])
    assert eligible is (failure in {None, "no-heavy", "wrong-heavy-app"})
    if failure in {"no-heavy", "wrong-heavy-app"}:
        if failure == "wrong-heavy-app": context["check-success"].append("@other/openrepotools-batch-heavy")
        assert not all(matches(condition, context) for condition in queue["merge_conditions"])
    elif failure is None:
        context["check-success"].append("@github-actions/openrepotools-batch-heavy")
        assert all(matches(condition, context) for condition in queue["merge_conditions"])


def test_ci_v13_delivery_fixture_source_uses_test_merge_without_rewriting_owner_head(cutover, v13_batch):
    batch = v13_batch
    assert git(batch["root"], "merge-base", batch["base"], batch["heads"][0]) == batch["foundation"]
    result = route_source(cutover, batch)
    assert result["omit_full"] is True and result["mode"] == "source"
    assert "queue_admission" not in result


@pytest.mark.parametrize("v13_batch", [2, 3], indirect=True)
def test_ci_v13_delivery_reviewed_linear_fixes_keep_all_proof_gates(cutover, delivery, v13_batch, v13):
    assert route_source(cutover, v13_batch)["omit_full"] is True
    proof = verify(delivery, v13_batch)
    assert [row["head"] for row in proof["members"]] == v13_batch["heads"]
    assert v13.projection.known_child(v13_batch["root"], v13_batch["base"], v13_batch["policy"],
        "P03", v13_batch["prs"][7], v13_batch["data"]["pulls/88"]) is True


@pytest.mark.parametrize("v13_batch", [3], indirect=True)
@pytest.mark.parametrize("failure", ["empty", "not-list", "duplicate", "reordered", "wrong-last",
    "overlong", "abbreviated", "merge", "intermediate-control", "unpinned-fix"])
def test_ci_v13_delivery_unreviewed_or_unsafe_lineage_refuses(v13, v13_batch, failure):
    batch, root = v13_batch, v13_batch["root"]
    policy = copy.deepcopy(batch["policy"])
    source = policy["profiles"]["P03"]["source"]
    chain = source["commits"]
    if failure == "empty": source["commits"] = []
    elif failure == "not-list": source["commits"] = source["head"]
    elif failure == "duplicate": source["commits"] = [chain[0], chain[0], chain[-1]]
    elif failure == "reordered": source["commits"] = [chain[1], chain[0], chain[-1]]
    elif failure == "wrong-last": source["commits"] = chain[:-1]
    elif failure == "overlong": source["commits"] = ["a" * 40, *chain]
    elif failure == "abbreviated": source["commits"][0] = chain[0][:7]
    elif failure == "unpinned-fix": source.pop("commits")
    else:
        git(root, "checkout", "-q", "--detach", chain[0])
        if failure == "merge":
            head = git(root, "commit-tree", git(root, "rev-parse", chain[-1] + "^{tree}"),
                       "-p", chain[0], "-p", batch["foundation"], "-m", "merge fix")
            source["commits"] = [chain[0], head]
        else:
            write(root, ".github/workflows/extra.yml", "# temporary control\n")
            middle = commit(root, "temporary out-of-scope change")
            git(root, "rm", ".github/workflows/extra.yml")
            write(root, "tests/test_sql_register_import.py", "# corrected source\n")
            head = commit(root, "restore final narrow diff")
            source["commits"] = [chain[0], middle, head]
            assert v13.projection.scoped_diff(root, batch["foundation"], head, policy["profiles"]["P03"])
        source["head"] = head
    git(root, "checkout", "-q", "--detach", batch["base"])
    write(root, v13.projection.CONFIG, json.dumps(policy))
    base = commit(root, "trusted lineage fixture")
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        v13.cut(root, base, source["head"])


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
