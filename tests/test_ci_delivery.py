# SPDX-License-Identifier: Apache-2.0
"""Offline candidate proof fixtures; no live queue, credential or GitHub write."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from conftest import NEEDS_UPSTREAM, REPO, UPSTREAM

SCRIPT = REPO / ".github/ci/delivery_verify.py"
REPOSITORY = "opensoft/openRepoTools-code"
FAST = "openrepotools-pr-fast"
QUEUE = "mergify/merge-queue/0123456789"


@pytest.fixture(scope="module")
def delivery():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("delivery_under_test", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(SCRIPT.parent))


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   stderr=subprocess.STDOUT).decode().strip()


def commit(root, message="fixture"):
    git(root, "add", ".")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def batch(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", "CI Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    git(root, "config", "core.filemode", "true")
    (root / "tests").mkdir()
    (root / "claude-current").write_text("#!/bin/sh\nexit 0\n")
    (root / "claude-current").chmod(0o755)
    (root / "tests/test_claude_current.py").write_text("# base\n")
    base = commit(root)
    (root / "claude-current").write_text("#!/bin/sh\n# member one\nexit 0\n")
    first = commit(root)
    git(root, "checkout", "-q", "--detach", base)
    (root / "tests/test_claude_current.py").write_text("# member two\n")
    second = commit(root)
    previous, prefixes = base, []
    for head in (first, second):
        try:
            tree = git(root, "merge-tree", "--write-tree", previous, head)
        except subprocess.CalledProcessError as error:
            if "unknown option" in error.output.decode(errors="replace"):
                pytest.skip("CI candidate proof fixtures require Git merge-tree --write-tree (2.38+)")
            raise
        previous = git(root, "commit-tree", tree, "-p", previous, "-p", head, "-m", "candidate")
        prefixes.append(previous)
    git(root, "checkout", "-q", "--detach", base)
    def side(head, branch):
        return {"sha": head, "ref": branch, "repo": {"full_name": REPOSITORY}}
    prs = {}
    data = {"git/ref/heads/main": {"object": {"sha": base}},
            "git/ref/heads/" + QUEUE: {"object": {"sha": previous}}}
    for number, head in ((7, first), (8, second)):
        pr = {"number": number, "state": "open", "draft": False, "merged": False,
              "body": "CI-Shadow: claude-current", "user": {"login": "writer"},
              "head": side(head, "feature/" + str(number)), "base": side(base, "main")}
        prs[number] = pr
        run_id, job_id = 100 + number, 900 + number
        check = {"id": job_id, "name": FAST, "head_sha": head,
                 "status": "completed", "conclusion": "success", "app": {"slug": "github-actions"},
                 "check_suite": {"id": run_id},
                 "details_url": f"https://github.com/{REPOSITORY}/actions/runs/{run_id}/job/{job_id}"}
        data[f"commits/{head}/pulls?per_page=100"] = [pr]
        data[f"pulls/{number}"] = pr
        data[f"commits/{head}/check-runs?check_name={FAST}&filter=latest&per_page=100"] = {
            "total_count": 1, "check_runs": [check]}
        data[f"actions/runs/{run_id}"] = {
            "id": run_id, "event": "pull_request", "path": ".github/workflows/task-set-fast.yml",
            "run_number": number, "workflow_id": 301,
            "head_sha": head, "head_branch": pr["head"]["ref"],
            "head_repository": {"full_name": REPOSITORY}, "check_suite_id": run_id,
            "status": "completed", "conclusion": "success", "run_attempt": 1,
            "created_at": "2026-11-11T00:00:01Z", "pull_requests": [{
                "number": number, "url": f"https://api.github.com/repos/{REPOSITORY}/pulls/{number}",
                "head": {"sha": head, "ref": pr["head"]["ref"],
                         "repo": {"url": f"https://api.github.com/repos/{REPOSITORY}"}},
                "base": {"sha": base, "ref": "main",
                         "repo": {"url": f"https://api.github.com/repos/{REPOSITORY}"}}}]}
        data[f"actions/workflows/task-set-fast.yml/runs?head_sha={head}&event=pull_request&per_page=100&page=1"] = {
            "total_count": 1, "workflow_runs": [data[f"actions/runs/{run_id}"]]}
        data[f"actions/jobs/{job_id}"] = {
            "id": job_id, "run_id": run_id, "run_attempt": 1, "head_sha": head,
            "name": FAST, "status": "completed", "conclusion": "success"}
        review = {"code_review": {"commit_sha": head, "status": "completed",
                                 "has_any_findings": False, "has_unresolved_findings": False}}
        data[f"issues/{number}/comments?per_page=100"] = [{
            "id": 1000 + number,
            "user": {"login": "chatgpt-codex-connector[bot]", "type": "Bot"},
            "updated_at": "2026-11-11T00:00:00Z",
            "body": "<!-- codex-pull-request-review-summary -->\n"
                    "<!-- codex-review-state:v1 " + json.dumps(review) + " -->"}]
    return {"root": root, "base": base, "heads": [first, second],
            "candidate": previous, "prefixes": prefixes, "prs": prs, "data": data,
            "env": {"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_EVENT_NAME": "push",
                    "GITHUB_ACTOR": "mergify[bot]", "GITHUB_REF": "refs/heads/" + QUEUE,
                    "GITHUB_SHA": previous},
            "event": {"repository": {"full_name": REPOSITORY}, "ref": "refs/heads/" + QUEUE,
                      "after": previous, "deleted": False, "forced": False,
                      "sender": {"login": "mergify[bot]"}}}


def request_for(batch):
    def request(repo, endpoint):
        assert repo == REPOSITORY
        return copy.deepcopy(batch["data"][endpoint])
    return request


def threads(number, batch=None):
    result = {"pageInfo": {"hasNextPage": False}, "nodes": []}
    if batch is not None:
        result["comments"] = {"pageInfo": {"hasNextPage": False}, "nodes": [
            {"databaseId": row["id"], "lastEditedAt": None, "body": row["body"]}
            for row in batch["data"][f"issues/{number}/comments?per_page=100"]]}
    return result


def base_changes(_number):
    return {"pageInfo": {"hasNextPage": False}, "nodes": []}


def verify(delivery, batch, request=None, read_threads=threads, read_base_changes=base_changes):
    if read_threads is threads:
        read_threads = lambda number: threads(number, batch)
    return delivery.verify_candidate(batch["env"], batch["event"], batch["root"],
                                     request or request_for(batch), read_threads, read_base_changes)


def test_ci_delivery_exact_independent_batch_has_immutable_prefix_proof(delivery, batch):
    proof = verify(delivery, batch)
    assert proof["verified"] is True
    assert proof["full_ci_required"] is True
    assert proof["base"] == batch["base"]
    assert proof["candidate"] == batch["candidate"]
    assert [row["number"] for row in proof["members"]] == [7, 8]
    assert [row["head"] for row in proof["members"]] == batch["heads"]
    assert [row["prefix"] for row in proof["members"]] == batch["prefixes"]
    assert proof["tree"] == git(batch["root"], "rev-parse", batch["candidate"] + "^{tree}")
    assert "queue_admission" not in proof
    assert "skip_ci" not in proof


@pytest.mark.parametrize("failure", [
    "actor", "sender", "event-kind", "context-sha", "event-sha", "event-repo", "forced", "deleted",
    "draft", "closed", "fork", "dependency", "intent", "ambiguous", "fast-missing",
    "fast-forged-app", "fast-old-head", "fast-wrong-workflow", "fast-job-skipped",
    "review-old-head", "review-running", "review-quota", "review-findings", "review-unmanaged",
    "truncated-comments", "fast-attempt", "boolean-count", "truncated-checks"])
def test_ci_delivery_missing_forged_or_unsupported_evidence_refuses(delivery, batch, failure):
    data, first = batch["data"], batch["heads"][0]
    checks = data[f"commits/{first}/check-runs?check_name={FAST}&filter=latest&per_page=100"]
    comment = data["issues/7/comments?per_page=100"][0]
    if failure == "actor":
        batch["env"]["GITHUB_ACTOR"] = "writer"
    elif failure == "sender":
        batch["event"]["sender"]["login"] = "writer"
    elif failure == "event-kind":
        batch["env"]["GITHUB_EVENT_NAME"] = "workflow_dispatch"
    elif failure == "context-sha":
        batch["env"]["GITHUB_SHA"] = "a" * 40
    elif failure == "event-sha":
        batch["event"]["after"] = "a" * 40
    elif failure == "event-repo":
        batch["event"]["repository"]["full_name"] = "fork/project"
    elif failure in ("forced", "deleted"):
        batch["event"][failure] = True
    elif failure == "draft":
        batch["prs"][7]["draft"] = True
    elif failure == "closed":
        batch["prs"][7]["state"] = "closed"
    elif failure == "fork":
        batch["prs"][7]["head"]["repo"]["full_name"] = "fork/project"
    elif failure == "dependency":
        batch["prs"][7]["body"] += "\nDepends-On: #1"
    elif failure == "intent":
        batch["prs"][7]["body"] = ""
    elif failure == "ambiguous":
        data[f"commits/{first}/pulls?per_page=100"].append(copy.deepcopy(batch["prs"][7]))
    elif failure == "fast-missing":
        checks.update(total_count=0, check_runs=[])
    elif failure == "fast-forged-app":
        checks["check_runs"][0]["app"]["slug"] = "another-app"
    elif failure == "fast-old-head":
        checks["check_runs"][0]["head_sha"] = "a" * 40
    elif failure == "fast-wrong-workflow":
        data["actions/runs/107"]["path"] = ".github/workflows/another.yml"
    elif failure == "fast-job-skipped":
        data["actions/jobs/907"]["conclusion"] = "skipped"
    elif failure == "fast-attempt":
        data["actions/jobs/907"]["run_attempt"] = 2
    elif failure == "truncated-comments":
        data["issues/7/comments?per_page=100"] = [copy.deepcopy(comment) for _ in range(100)]
    elif failure == "truncated-checks":
        checks["total_count"] = 2
    elif failure == "boolean-count":
        checks["total_count"] = True
    elif failure == "review-quota":
        comment["body"] = "Codex review usage limit reached"
    elif failure == "review-unmanaged":
        comment["body"] = comment["body"].replace(
            "<!-- codex-pull-request-review-summary -->", "")
    else:
        old = json.loads(comment["body"].split("v1 ", 1)[1].split(" -->", 1)[0])
        if failure == "review-old-head":
            old["code_review"]["commit_sha"] = "a" * 40
        elif failure == "review-findings":
            old["code_review"]["has_any_findings"] = True
        else:
            old["code_review"]["status"] = "running"
        comment["body"] = ("<!-- codex-pull-request-review-summary -->\n"
                           "<!-- codex-review-state:v1 " + json.dumps(old) + " -->")
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        verify(delivery, batch)


@pytest.mark.parametrize("failure", ["main-before", "main-after", "queue-after", "source-after", "api"])
def test_ci_delivery_read_failures_and_live_drift_refuse(delivery, batch, failure):
    original, counts = request_for(batch), {}
    def request(repo, endpoint):
        counts[endpoint] = counts.get(endpoint, 0) + 1
        if failure == "api":
            raise subprocess.TimeoutExpired("gh", 15)
        data = original(repo, endpoint)
        if endpoint == "git/ref/heads/main" and (
                failure == "main-before" or failure == "main-after" and counts[endpoint] > 1):
            data["object"]["sha"] = "a" * 40
        if endpoint == "git/ref/heads/" + QUEUE and failure == "queue-after" and counts[endpoint] > 1:
            data["object"]["sha"] = "a" * 40
        if endpoint == "pulls/7" and failure == "source-after" and counts[endpoint] > 1:
            data["head"]["sha"] = "a" * 40
        return data
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        verify(delivery, batch, request)


@pytest.mark.parametrize("response", [
    {"pageInfo": {"hasNextPage": True}, "nodes": []},
    {"pageInfo": {"hasNextPage": False}, "nodes": [{"isResolved": False}]},
])
def test_ci_delivery_unresolved_or_incomplete_threads_refuse(delivery, batch, response):
    with pytest.raises(ValueError):
        verify(delivery, batch, read_threads=lambda number: dict(threads(number, batch), **response))


def test_ci_delivery_wrong_candidate_tree_with_same_parents_refuses(delivery, batch):
    wrong = git(batch["root"], "commit-tree", batch["heads"][1] + "^{tree}",
                "-p", batch["prefixes"][0], "-p", batch["heads"][1], "-m", "wrong tree")
    batch["candidate"] = batch["env"]["GITHUB_SHA"] = batch["event"]["after"] = wrong
    batch["data"]["git/ref/heads/" + QUEUE]["object"]["sha"] = wrong
    with pytest.raises(ValueError):
        verify(delivery, batch)


def test_ci_delivery_fast_validation_proves_checkout_and_both_merge_parents(delivery, batch):
    prefix = batch["prefixes"][0]
    git(batch["root"], "checkout", "-q", "--detach", prefix)
    env = dict(batch["env"], GITHUB_EVENT_NAME="pull_request", GITHUB_SHA=prefix)
    event = {"action": "synchronize", "pull_request": batch["prs"][7]}
    assert delivery.verify_fast(env, event, batch["root"])["tested"] == prefix
    event["pull_request"] = batch["prs"][8]
    with pytest.raises(ValueError):
        delivery.verify_fast(env, event, batch["root"])


def test_ci_delivery_singleton_is_valid_but_not_two_member_qualification(delivery, batch):
    first = batch["prefixes"][0]
    batch["candidate"] = batch["env"]["GITHUB_SHA"] = batch["event"]["after"] = first
    batch["data"]["git/ref/heads/" + QUEUE]["object"]["sha"] = first
    proof = verify(delivery, batch)
    assert len(proof["members"]) == 1
    assert proof["members"][0]["number"] == 7


def test_ci_delivery_third_member_is_outside_initial_bound(delivery, batch):
    third = git(batch["root"], "commit-tree", batch["candidate"] + "^{tree}",
                "-p", batch["candidate"], "-p", batch["heads"][0], "-m", "third")
    batch["candidate"] = batch["env"]["GITHUB_SHA"] = batch["event"]["after"] = third
    batch["data"]["git/ref/heads/" + QUEUE]["object"]["sha"] = third
    with pytest.raises(ValueError):
        verify(delivery, batch)


def test_ci_delivery_reverification_catches_changes_after_initial_success(delivery, batch):
    assert verify(delivery, batch)["verified"] is True
    batch["prs"][7]["state"] = "closed"
    with pytest.raises(ValueError):
        verify(delivery, batch)


@pytest.mark.parametrize("shared_history", [False, True])
def test_ci_delivery_hidden_dependent_or_shared_non_main_history_refuses(
        delivery, batch, shared_history):
    root, (first, second) = batch["root"], batch["heads"]
    left = (git(root, "commit-tree", first + "^{tree}", "-p", first, "-m", "left")
            if shared_history else first)
    right = git(root, "commit-tree", batch["candidate"] + "^{tree}",
                "-p", first, "-m", "dependent right")
    batch["data"] = json.loads(json.dumps(batch["data"]).replace(first, left).replace(second, right))
    previous = batch["base"]
    for head in (left, right):
        tree = git(root, "merge-tree", "--write-tree", previous, head)
        previous = git(root, "commit-tree", tree, "-p", previous, "-p", head, "-m", "candidate")
    batch["env"]["GITHUB_SHA"] = batch["event"]["after"] = previous
    batch["data"]["git/ref/heads/" + QUEUE]["object"]["sha"] = previous
    with pytest.raises(ValueError, match="non-main history"):
        verify(delivery, batch)


@pytest.mark.parametrize("failure", ["wrong-base", "wrong-pr", "ambiguous", "foreign-repo"])
def test_ci_delivery_fast_source_association_refuses(delivery, batch, failure):
    run = batch["data"]["actions/runs/107"]
    source = run["pull_requests"][0]
    if failure == "wrong-base":
        source["base"]["ref"] = "alternate-base"
    elif failure == "wrong-pr":
        source["number"] = 99
    elif failure == "foreign-repo":
        source["base"]["repo"]["url"] = "https://api.github.com/repos/fork/other"
    else:
        run["pull_requests"].append(copy.deepcopy(source))
    with pytest.raises(ValueError):
        verify(delivery, batch)


@pytest.mark.parametrize("created,expected", [
    ("2026-11-11T00:00:00Z", False), ("2026-11-11T00:00:01Z", False),
    ("2026-11-11T00:00:02Z", True),
])
def test_ci_delivery_mutable_association_requires_run_created_after_retarget(
        delivery, batch, created, expected):
    # An OLD run's mutable association can already report the current main base.
    batch["data"]["actions/runs/107"]["created_at"] = created
    history = {"pageInfo": {"hasNextPage": False},
               "nodes": [{"createdAt": "2026-11-11T00:00:01Z"}]}
    reader = lambda number: copy.deepcopy(history if number == 7 else base_changes(number))
    if expected:
        assert verify(delivery, batch, read_base_changes=reader)["verified"] is True
    else:
        with pytest.raises(ValueError, match="predates a base change"):
            verify(delivery, batch, read_base_changes=reader)


@pytest.mark.parametrize("history", [
    {"pageInfo": {"hasNextPage": True}, "nodes": []},
    {"pageInfo": {"hasNextPage": False}, "nodes": [{"createdAt": "invalid"}]},
])
def test_ci_delivery_incomplete_or_malformed_base_history_refuses(delivery, batch, history):
    with pytest.raises(ValueError):
        verify(delivery, batch, read_base_changes=lambda _number: history)


def test_ci_delivery_fast_attempt_changes_after_run_read_refuses(delivery, batch):
    original = request_for(batch)
    def request(repo, endpoint):
        answer = original(repo, endpoint)
        if endpoint == "actions/jobs/907":
            batch["data"]["actions/runs/107"].update(
                run_attempt=2, status="in_progress", conclusion=None)
        return answer
    with pytest.raises(ValueError, match="changed during verification"):
        verify(delivery, batch, request)


@pytest.mark.parametrize("failure", ["thread", "review", "run", "history"])
def test_ci_delivery_member_evidence_changes_during_second_member_refuses(delivery, batch, failure):
    original, state = request_for(batch), {"changed": False}
    def request(repo, endpoint):
        answer = original(repo, endpoint)
        if endpoint == "pulls/8":
            state["changed"] = True
            if failure == "review":
                batch["data"]["issues/7/comments?per_page=100"][0]["body"] = "quota reached"
            if failure == "run":
                batch["data"]["actions/runs/107"].update(
                    run_attempt=2, status="in_progress", conclusion=None)
        return answer
    def read_threads(number):
        return dict(threads(number, batch), nodes=
                    [{"isResolved": False}] if failure == "thread" and number == 7
                    and state["changed"] else [])
    def read_history(number):
        return {"pageInfo": {"hasNextPage": False}, "nodes":
                [{"createdAt": "2026-11-12T00:00:00Z"}] if failure == "history"
                and number == 7 and state["changed"] else []}
    with pytest.raises(ValueError):
        verify(delivery, batch, request, read_threads, read_history)


@pytest.mark.parametrize("mode", ["fast", "candidate"])
def test_ci_delivery_cli_candidate_root_is_trusted_script_checkout_not_caller_cwd(
        delivery, tmp_path, monkeypatch, capsys, mode):
    event = tmp_path / "event.json"
    event.write_text("{}")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setattr(sys, "argv", ["delivery_verify.py", mode])
    monkeypatch.chdir(tmp_path)
    seen = []
    def verify_stub(_env, _event, root):
        seen.append(root)
        return {"full_ci_required": True}
    monkeypatch.setattr(delivery, "verify_" + mode, verify_stub)
    delivery.main()
    assert seen == [tmp_path if mode == "fast" else SCRIPT.resolve().parents[2]]
    assert json.loads(capsys.readouterr().out)["full_ci_required"] is True


@NEEDS_UPSTREAM
def test_ci_delivery_workflows_are_additive_and_candidate_has_no_live_trigger():
    spec = importlib.util.spec_from_file_location("delivery_yaml", UPSTREAM / "scripts/repo_shape.py")
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader
    spec.loader.exec_module(reader)
    fast = reader.load_yaml(REPO / ".github/workflows/task-set-fast.yml")
    heavy = reader.load_yaml(REPO / ".github/workflows/task-set-candidate.yml")
    assert fast["on"] == {"pull_request": {"types": ["opened", "synchronize", "reopened"]}}
    assert fast["permissions"] == {"contents": "read"}
    assert set(heavy["on"]) == {"workflow_call"}
    assert heavy["on"]["workflow_call"] is None
    assert heavy["permissions"] == {"contents": "read"}
    for job in ("verify", "qualification"):
        assert heavy["jobs"][job]["permissions"] == {
            "contents": "read", "pull-requests": "read", "checks": "read", "actions": "read"}
    assert set(heavy["jobs"]) == {"verify", "full-ci", "qualification"}
    assert heavy["jobs"]["full-ci"] == {
        "needs": "verify", "uses": "./.github/workflows/tests.yml",
        "permissions": {"contents": "read", "pull-requests": "read", "checks": "read", "actions": "read"}}
    gate = heavy["jobs"]["qualification"]
    assert gate["if"] == "${{ always() }}"
    assert gate["needs"] == ["verify", "full-ci"]
    assert gate["name"] == "Candidate full-suite qualification"
    assert heavy["jobs"]["verify"]["steps"][0]["with"]["ref"] == "main"
    assert gate["steps"][1]["with"]["ref"] == "main"
    assert gate["steps"][-2]["run"] == 'python3 policy/.github/ci/delivery_verify.py candidate --proof-kind qualified'
    assert gate["steps"][-1]["with"]["if-no-files-found"] == "error"
    assert all("GH_TOKEN" not in step.get("env", {}) for step in fast["jobs"]["fast"]["steps"])


@NEEDS_UPSTREAM
@pytest.mark.parametrize("verify_result,full_result,ok", [
    ("success", "success", True), ("failure", "success", False),
    ("success", "failure", False), ("success", "skipped", False),
    ("cancelled", "success", False), ("success", "", False),
])
def test_ci_delivery_heavy_aggregate_rejects_failed_skipped_or_cancelled_calls(
        verify_result, full_result, ok):
    spec = importlib.util.spec_from_file_location("delivery_gate_yaml", UPSTREAM / "scripts/repo_shape.py")
    reader = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = reader
    spec.loader.exec_module(reader)
    heavy = reader.load_yaml(REPO / ".github/workflows/task-set-candidate.yml")
    script = heavy["jobs"]["qualification"]["steps"][0]["run"]
    result = subprocess.run(["bash", "-euo", "pipefail", "-c", script], capture_output=True,
                            env=dict(os.environ, VERIFIED=verify_result, FULL_CI=full_result),
                            timeout=10)
    assert (result.returncode == 0) is ok
