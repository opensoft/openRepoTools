# SPDX-License-Identifier: Apache-2.0
"""Disabled v1.3 observations: local Git histories and mocked read APIs only."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from conftest import NEEDS_UPSTREAM, REPO, UPSTREAM

SCRIPT = REPO / ".github/ci/v13_shadow.py"
WORKFLOW = ".github/workflows/v13-shadow.yml"
INTENT = "CI-Shadow: sql-register-v13\nCI-Task-Set: P03"
REPOSITORY = "opensoft/openRepoTools-code"


@pytest.fixture
def shadow(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("v13_shadow_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args],
                                   stderr=subprocess.STDOUT).decode().strip()


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def commit(root, message=INTENT):
    git(root, "add", ".")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def side(sha, ref):
    return {"sha": sha, "ref": ref, "repo": {"full_name": REPOSITORY}}


def pr(number, head, base, branch):
    return {"number": number, "state": "open", "draft": False, "merged": False,
            "body": INTENT, "user": {"login": "writer"}, "merge_commit_sha": None,
            "head": side(head, branch), "base": side(base, "main")}


@pytest.fixture
def fixture(tmp_path, shadow):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    for key, value in (("user.name", "CI Fixture"), ("user.email", "ci@example.invalid"),
                       ("core.autocrlf", "false"), ("core.filemode", "true")):
        git(root, "config", key, value)
    write(root, ".github/workflows/tests.yml", "# P01 required-engine workflow\n")
    write(root, shadow.BASELINE, json.dumps({
        "environment": {"OPENREPOTOOLS_REQUIRE_PG": "1"}, "expanded_jobs": 13}))
    for path in shadow.P01_FILES:
        write(root, path, "# foundation\n")
    for task in shadow.P01_TASKS:
        write(root, shadow.MARKERS + task, "")
    write(root, "tests/test_sql_register_import.py", "# initial test\n")
    foundation = commit(root, "P01 foundation")
    policy = json.loads((REPO / "tests/fixtures/ci/v13-initial-profiles.json").read_text())
    policy["prerequisite"]["head"] = foundation
    policy["prerequisite"]["blobs"] = {
        path: git(root, "rev-parse", "HEAD:" + path) for path in shadow.CONTROL_PATHS}
    write(root, shadow.CONFIG, json.dumps(policy))
    base = commit(root, "trusted disabled policy")
    write(root, "tests/test_sql_register_import.py", "# modified test\n")
    for task in policy["profiles"]["P03"]["tasks"]:
        write(root, shadow.MARKERS + task, "")
    head = commit(root)
    git(root, "checkout", "-q", "--detach", base)
    source, prerequisite = pr(7, head, base, "feature/small"), pr(88, foundation, base, "p01")
    prerequisite.update(state="closed", merged=True, merge_commit_sha=foundation)
    event = {"number": 7, "action": "synchronize", "pull_request": copy.deepcopy(source)}
    env = {"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_EVENT_NAME": "pull_request",
           "GITHUB_SHA": head, "GITHUB_REF": "refs/pull/7/merge"}
    return dict(root=root, main=base, head=head, pr=source, prerequisite=prerequisite,
                policy=policy, event=event, env=env)


def api(fixture):
    def request(repo, endpoint):
        assert repo == REPOSITORY
        if endpoint == "git/ref/heads/main":
            return {"object": {"sha": fixture["main"]}}
        if endpoint in {"pulls/7", "pulls/88"}:
            return copy.deepcopy(fixture["pr" if endpoint == "pulls/7" else "prerequisite"])
        if endpoint == "git/ref/heads/feature/small":
            return {"object": {"sha": fixture["head"]}}
        raise AssertionError("Unexpected read endpoint: " + endpoint)
    return request


def observe(shadow, fixture, request=None):
    result = shadow.classify(fixture["env"], fixture["event"], fixture["root"],
                             request or api(fixture))
    # Applies to every positive and negative API/Git test, not only one fixture.
    assert result["mode"] == "shadow"
    assert result["required_ci"] == "full"
    assert result["efficiency_enabled"] is False
    assert result["skip_ci"] is False
    assert result["queue_admission"] is False
    assert result["qualification"] == "not-qualified"
    assert result["proposed_cut"] in {None, "P03", "P05"}
    return result


def update_source(fixture, head):
    fixture["head"] = fixture["pr"]["head"]["sha"] = head
    fixture["event"]["pull_request"] = copy.deepcopy(fixture["pr"])
    git(fixture["root"], "checkout", "-q", "--detach", fixture["main"])


def test_v13_shadow_matching_modified_test_and_exact_markers_is_not_qualification(shadow, fixture):
    result = observe(shadow, fixture)
    assert result["proposed_cut"] == "P03"
    assert result["p01_status"] == "merged-contract-observed"
    assert result["reason"] == "cut-observed-not-qualified"


@pytest.mark.parametrize("cut", ["P03", "P05"])
def test_v13_shadow_new_named_test_files_are_observable(shadow, fixture, cut):
    root, profile = fixture["root"], fixture["policy"]["profiles"][cut]
    target = profile["files"][-1]
    write(root, target, "# added test\n")
    for task in profile["tasks"]:
        write(root, shadow.MARKERS + task, "")
    fixture["pr"]["body"] = INTENT.replace("P03", cut)
    update_source(fixture, commit(root))
    assert observe(shadow, fixture)["proposed_cut"] == cut


@pytest.mark.parametrize("operation", [
    "mixed", "control", "delete", "rename", "mode", "symlink", "extra-marker",
    "missing-marker", "nonempty-marker", "changed-foundation-marker", "marker-only", "empty"])
def test_v13_shadow_unsafe_or_incomplete_git_diff_stays_full(shadow, fixture, operation):
    root = fixture["root"]
    git(root, "checkout", "-q", "--detach", fixture["head"])
    target = root / "tests/test_sql_register_import.py"
    if operation == "mixed":
        write(root, "lane-start", "# unrelated\n")
    elif operation == "control":
        write(root, ".github/workflows/tests.yml", "# must not change\n")
    elif operation == "delete":
        target.unlink()
    elif operation == "rename":
        target.rename(root / "tests/test_sql_register_readers.py")
    elif operation == "mode":
        target.chmod(0o755)
    elif operation == "symlink":
        target.unlink()
        target.symlink_to("conftest.py")
    elif operation == "extra-marker":
        write(root, shadow.MARKERS + "T999", "")
    elif operation == "missing-marker":
        (root / (shadow.MARKERS + "T211")).unlink()
    elif operation == "nonempty-marker":
        write(root, shadow.MARKERS + "T211", "not empty\n")
    elif operation == "changed-foundation-marker":
        write(root, shadow.MARKERS + "T200", "changed\n")
    elif operation == "marker-only":
        target.write_text("# initial test\n")
    head = fixture["main"] if operation == "empty" else commit(root)
    update_source(fixture, head)
    assert observe(shadow, fixture)["proposed_cut"] is None


@pytest.mark.parametrize("mutation", [
    "draft", "fork", "number", "bool-number", "head", "base", "body", "dependent",
    "depends-on", "candidate", "reserved", "unsafe-ref", "closed", "missing-intent",
    "duplicate-intent", "duplicate-cut", "unknown-cut", "repository"])
def test_v13_shadow_unsupported_pr_snapshots_stay_full(shadow, fixture, mutation):
    source, event = fixture["pr"], fixture["event"]
    if mutation == "draft":
        source["draft"] = True
    elif mutation == "fork":
        source["head"]["repo"]["full_name"] = "fork/other"
    elif mutation == "number":
        source["number"] = 8
    elif mutation == "bool-number":
        event["number"] = True
    elif mutation in {"head", "base"}:
        source[mutation]["sha"] = "a" * 40
    elif mutation == "body":
        source["body"] += "\nchanged"
    elif mutation == "dependent":
        source["base"]["ref"] = "predecessor"
    elif mutation == "depends-on":
        source["body"] += "\n  Depends-On: #3"
    elif mutation in {"candidate", "reserved", "unsafe-ref"}:
        source["head"]["ref"] = {"candidate": "mergify/merge-queue/0123456789",
                                  "reserved": "verify/source", "unsafe-ref": "a/../b"}[mutation]
    elif mutation == "closed":
        source["state"] = "closed"
    elif mutation in {"missing-intent", "duplicate-intent", "duplicate-cut", "unknown-cut"}:
        source["body"] = {"missing-intent": "", "duplicate-intent": INTENT + "\n" + INTENT,
                          "duplicate-cut": INTENT + "\nCI-Task-Set: P03",
                          "unknown-cut": INTENT.replace("P03", "P99")}[mutation]
    else:
        fixture["env"]["GITHUB_REPOSITORY"] = "foreign/repository"
    if mutation not in {"number", "bool-number", "head", "base", "body"}:
        event["pull_request"] = copy.deepcopy(source)
    assert observe(shadow, fixture)["proposed_cut"] is None


@pytest.mark.parametrize("action", ["edited", "labeled", "unlabeled", "ready_for_review"])
def test_v13_shadow_third_party_edits_are_reproved_without_grants(shadow, fixture, action):
    fixture["event"].update(action=action, sender={"login": "third-party"})
    fixture["pr"]["body"] = fixture["event"]["pull_request"]["body"] = (
        INTENT.replace("\n", "\r\n") + " \r\n$(touch should-not-exist)\n::error::untrusted")
    result = observe(shadow, fixture)
    assert result["proposed_cut"] == "P03"
    assert "untrusted" not in json.dumps(result)
    assert not (fixture["root"] / "should-not-exist").exists()


@pytest.mark.parametrize("action", ["closed", "dequeued", "enqueued", "converted_to_draft"])
def test_v13_shadow_closed_or_queue_metadata_is_only_full_fallback(shadow, fixture, action):
    fixture["event"]["action"] = action
    assert observe(shadow, fixture)["proposed_cut"] is None


@pytest.mark.parametrize("mutation,status", [
    ("pending", "pending"), ("head", "anchor-drift"), ("base", "anchor-drift"),
    ("closed-unmerged", "not-merged"), ("draft", "not-merged"), ("merge", "unavailable")])
def test_v13_shadow_p01_pending_drift_is_not_pg_acceptance(shadow, fixture, mutation, status):
    prerequisite = fixture["prerequisite"]
    if mutation == "pending":
        prerequisite.update(state="open", merged=False, merge_commit_sha=None)
    elif mutation in {"head", "base"}:
        prerequisite[mutation]["sha" if mutation == "head" else "ref"] = (
            "a" * 40 if mutation == "head" else "dependent")
    elif mutation == "closed-unmerged":
        prerequisite["merged"] = False
    elif mutation == "draft":
        prerequisite["draft"] = True
    else:
        prerequisite["merge_commit_sha"] = "0" * 40
    result = observe(shadow, fixture)
    assert result["p01_status"] == status
    assert result["proposed_cut"] is None


@pytest.mark.parametrize("mutation", [
    "enabled", "nonboolean", "duplicate", "missing", "unknown-profile", "duplicate-task",
    "control-blob", "required-pg", "inventory", "missing-foundation", "nonempty-foundation"])
def test_v13_shadow_main_policy_and_p01_contract_drift_fall_back(shadow, fixture, mutation):
    root, policy = fixture["root"], copy.deepcopy(fixture["policy"])
    if mutation == "enabled":
        policy["efficiency_enabled"] = True
    elif mutation == "nonboolean":
        policy["efficiency_enabled"] = 0
    elif mutation == "unknown-profile":
        policy["profiles"]["P99"] = policy["profiles"].pop("P03")
    elif mutation == "duplicate-task":
        policy["profiles"]["P03"]["tasks"].append("T211")
    elif mutation == "control-blob":
        write(root, ".github/workflows/tests.yml", "# changed control\n")
    elif mutation in {"required-pg", "inventory"}:
        baseline = {"environment": {"OPENREPOTOOLS_REQUIRE_PG": "0"}, "expanded_jobs": 13}
        if mutation == "inventory":
            baseline.update(environment={"OPENREPOTOOLS_REQUIRE_PG": "1"}, expanded_jobs=12)
        write(root, shadow.BASELINE, json.dumps(baseline))
        git(root, "add", shadow.BASELINE)
        policy["prerequisite"]["blobs"][shadow.BASELINE] = git(root, "rev-parse", ":" + shadow.BASELINE)
    elif mutation == "missing-foundation":
        (root / shadow.P01_FILES[0]).unlink()
    elif mutation == "nonempty-foundation":
        write(root, shadow.MARKERS + "T200", "nonempty\n")
    text = json.dumps(policy)
    if mutation == "duplicate":
        text = text.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1')
    write(root, shadow.CONFIG, text)
    if mutation == "missing":
        (root / shadow.CONFIG).unlink()
    fixture["main"] = commit(root, "changed trusted policy")
    assert observe(shadow, fixture)["proposed_cut"] is None


@pytest.mark.parametrize("failure", ["api", "git", "main-before", "main-after", "pr-after", "p01-after"])
def test_v13_shadow_read_failures_and_moving_inputs_fall_back(shadow, fixture, monkeypatch, failure):
    original, counts = api(fixture), {}
    def request(repo, endpoint):
        counts[endpoint] = counts.get(endpoint, 0) + 1
        if failure == "api":
            raise subprocess.TimeoutExpired("gh", 15)
        result = original(repo, endpoint)
        if endpoint == "git/ref/heads/main" and (
                failure == "main-before" or failure == "main-after" and counts[endpoint] > 1):
            result["object"]["sha"] = "a" * 40
        if counts[endpoint] > 1 and (
                endpoint == "pulls/7" and failure == "pr-after"
                or endpoint == "pulls/88" and failure == "p01-after"):
            result["body"] += "\nchanged"
        return result
    if failure == "git":
        def unavailable(*args):
            raise subprocess.TimeoutExpired("git", 20)
        monkeypatch.setattr(shadow.common, "git", unavailable)
    assert observe(shadow, fixture, request)["proposed_cut"] is None


def push(fixture, ref="refs/heads/feature/small"):
    fixture["env"].update(GITHUB_EVENT_NAME="push", GITHUB_REF=ref, GITHUB_SHA=fixture["head"])
    fixture["event"] = {"ref": ref, "after": fixture["head"], "before": fixture["main"],
                        "repository": {"full_name": REPOSITORY}, "forced": False, "deleted": False}


def test_v13_shadow_source_push_is_observed_without_admission(shadow, fixture):
    push(fixture)
    assert observe(shadow, fixture)["proposed_cut"] == "P03"


@pytest.mark.parametrize("mutation", ["main", "mergify/merge-queue/0123456789", "verify/source",
                                   "release/v1.3", "forced", "deleted", "sha", "repository", "ref"])
def test_v13_shadow_push_fallbacks(shadow, fixture, mutation):
    push(fixture)
    if mutation in {"forced", "deleted"}:
        fixture["event"][mutation] = True
    elif mutation == "sha":
        fixture["env"]["GITHUB_SHA"] = "a" * 40
    elif mutation == "repository":
        fixture["event"]["repository"]["full_name"] = "foreign/repository"
    elif mutation == "ref":
        fixture["event"]["ref"] = "refs/heads/different"
    else:
        fixture["event"]["ref"] = fixture["env"]["GITHUB_REF"] = "refs/heads/" + mutation
    assert observe(shadow, fixture)["proposed_cut"] is None


@pytest.mark.parametrize("when", [1, 2])
def test_v13_shadow_push_rereads_branch(shadow, fixture, when):
    push(fixture)
    original, reads = api(fixture), 0
    def moving(repo, endpoint):
        nonlocal reads
        value = original(repo, endpoint)
        if endpoint.endswith("feature/small"):
            reads += 1
            if reads == when:
                value["object"]["sha"] = "a" * 40
        return value
    assert observe(shadow, fixture, moving)["proposed_cut"] is None


@pytest.mark.parametrize("payload", [None, [], {}, {"number": True}])
def test_v13_shadow_bad_events_fall_back(shadow, fixture, payload):
    fixture["event"] = payload
    assert observe(shadow, fixture)["proposed_cut"] is None


@pytest.mark.parametrize("event", ["pull_request_target", "workflow_dispatch", "merge_group", "schedule"])
def test_v13_shadow_unsupported_events_fall_back(shadow, fixture, event):
    fixture["env"]["GITHUB_EVENT_NAME"] = event
    assert observe(shadow, fixture)["proposed_cut"] is None


@pytest.fixture(params=["P03", "P05"])
def stack_fixture(tmp_path, shadow, request):
    """Real shape: source child of P01; main advances and normally merges P01."""
    root, cut = tmp_path / "stack", request.param
    root.mkdir()
    git(root, "init", "-q")
    for key, value in (("user.name", "CI Fixture"), ("user.email", "ci@example.invalid"),
                       ("core.autocrlf", "false"), ("core.filemode", "true")):
        git(root, "config", key, value)
    write(root, ".github/workflows/tests.yml", "# before P01\n")
    write(root, shadow.BASELINE, json.dumps({"environment": {}, "expanded_jobs": 13}))
    old_main = commit(root, "old main")
    write(root, ".github/workflows/tests.yml", "# P01 required-engine contract\n")
    write(root, shadow.BASELINE, json.dumps({
        "environment": {"OPENREPOTOOLS_REQUIRE_PG": "1"}, "expanded_jobs": 13}))
    for path in shadow.P01_FILES:
        write(root, path, "# foundation\n")
    for task in shadow.P01_TASKS:
        write(root, shadow.MARKERS + task, "")
    foundation = commit(root, "P01 source")
    policy = json.loads((REPO / "tests/fixtures/ci/v13-initial-profiles.json").read_text())
    profile = policy["profiles"][cut]
    policy["prerequisite"]["head"] = foundation
    policy["prerequisite"]["blobs"] = {
        path: git(root, "rev-parse", "HEAD:" + path) for path in shadow.CONTROL_PATHS}
    for path in profile["files"]:
        write(root, path, "# exact source test\n")
    for task in profile["tasks"]:
        write(root, shadow.MARKERS + task, "")
    head = commit(root, "actual owner cut without shadow trailers")
    profile["source"] = {"number": 7, "head": head, "branch": "feature/small"}
    git(root, "checkout", "-q", "--detach", old_main)
    write(root, shadow.CONFIG, json.dumps(policy))
    commit(root, "independent observer change on main")
    git(root, "merge", "--no-ff", "-qm", "normal P01 landing", foundation)
    merge = git(root, "rev-parse", "HEAD")
    write(root, ".github/ci/unrelated-observer", "keep this main change\n")
    main = commit(root, "later unrelated main change")
    source = pr(7, head, foundation, "feature/small")
    source["base"]["ref"] = "p01"
    source["body"] = INTENT.replace("P03", cut) + "\nDepends-On: #88"
    prerequisite = pr(88, foundation, main, "p01")
    prerequisite.update(state="closed", merged=True, merge_commit_sha=merge)
    return dict(root=root, main=main, head=head, pr=source, prerequisite=prerequisite,
                policy=policy, cut=cut,
                event={"number": 7, "action": "synchronize", "pull_request": copy.deepcopy(source)},
                env={"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_EVENT_NAME": "pull_request",
                     "GITHUB_SHA": head, "GITHUB_REF": "refs/pull/7/merge"})


@pytest.mark.parametrize("base", ["prerequisite", "main", "main-without-dependency"])
def test_v13_shadow_known_child_preserves_owner_topology(shadow, stack_fixture, base):
    fixture = stack_fixture
    if base != "prerequisite":
        fixture["pr"]["base"] = side(fixture["main"], "main")
    if base == "main-without-dependency":
        fixture["pr"]["body"] = INTENT.replace("P03", fixture["cut"])
    fixture["event"]["pull_request"] = copy.deepcopy(fixture["pr"])
    result = observe(shadow, fixture)
    assert result["proposed_cut"] == fixture["cut"]
    assert result["p01_status"] == "merged-contract-observed"
    assert git(fixture["root"], "show", "-s", "--format=%P", fixture["head"]) == (
        fixture["policy"]["prerequisite"]["head"])


def test_v13_shadow_fixture_normal_merge_keeps_main_files_and_exact_source(shadow, stack_fixture):
    fixture, root = stack_fixture, stack_fixture["root"]
    assert observe(shadow, fixture)["proposed_cut"] == fixture["cut"]
    git(root, "merge", "--no-ff", "-qm", "fixture only, not live qualification", fixture["head"])
    assert git(root, "show", "HEAD:.github/ci/unrelated-observer") == "keep this main change"
    assert git(root, "show", "-s", "--format=%P", "HEAD").split() == [fixture["main"], fixture["head"]]
    profile = fixture["policy"]["profiles"][fixture["cut"]]
    for path in profile["files"]:
        assert git(root, "rev-parse", "HEAD:" + path) == git(root, "rev-parse", fixture["head"] + ":" + path)
    for task in profile["tasks"]:
        assert git(root, "show", "HEAD:" + shadow.MARKERS + task) == ""


@pytest.mark.parametrize("mutation", [
    "pending", "dependency", "duplicate-dependency", "missing-dependency", "base-ref",
    "base-sha", "head", "branch", "number", "draft", "closed", "no-intent", "fork"])
def test_v13_shadow_known_child_uncertainty_stays_full(shadow, stack_fixture, mutation):
    fixture, source = stack_fixture, stack_fixture["pr"]
    if mutation == "pending":
        fixture["prerequisite"].update(state="open", merged=False, merge_commit_sha=None)
    elif mutation == "dependency":
        source["body"] = source["body"].replace("#88", "#89")
    elif mutation == "duplicate-dependency":
        source["body"] += "\nDepends-On: #88"
    elif mutation == "missing-dependency":
        source["body"] = INTENT.replace("P03", fixture["cut"])
    elif mutation == "base-ref":
        source["base"]["ref"] = "unknown-predecessor"
    elif mutation == "base-sha":
        source["base"]["sha"] = fixture["main"]
    elif mutation == "head":
        source["head"]["sha"] = "a" * 40
    elif mutation == "branch":
        source["head"]["ref"] = "different-source"
    elif mutation == "number":
        source["number"] = 8
    elif mutation == "draft":
        source["draft"] = True
    elif mutation == "closed":
        source["state"] = "closed"
    elif mutation == "no-intent":
        source["body"] = "Depends-On: #88"
    else:
        source["head"]["repo"]["full_name"] = "fork/elsewhere"
    fixture["event"]["pull_request"] = copy.deepcopy(source)
    assert observe(shadow, fixture)["proposed_cut"] is None


@pytest.mark.parametrize("collision", ["file", "marker"])
def test_v13_shadow_known_child_main_cut_path_drift_stays_full(shadow, stack_fixture, collision):
    fixture = stack_fixture
    profile = fixture["policy"]["profiles"][fixture["cut"]]
    path = profile["files"][0] if collision == "file" else shadow.MARKERS + profile["tasks"][0]
    write(fixture["root"], path, "" if collision == "marker" else "# different main content\n")
    fixture["main"] = commit(fixture["root"], "intervening cut content")
    assert observe(shadow, fixture)["proposed_cut"] is None


def test_v13_shadow_known_child_rejects_extra_parent_hop_even_with_updated_binding(shadow, stack_fixture):
    fixture = stack_fixture
    extra = git(fixture["root"], "commit-tree", fixture["head"] + "^{tree}",
                "-p", fixture["head"], "-m", "arbitrary extra hop")
    fixture["policy"]["profiles"][fixture["cut"]]["source"]["head"] = extra
    write(fixture["root"], shadow.CONFIG, json.dumps(fixture["policy"]))
    fixture["main"] = commit(fixture["root"], "updated anchor cannot excuse ancestry")
    fixture["pr"]["head"]["sha"] = extra
    fixture["event"]["pull_request"] = copy.deepcopy(fixture["pr"])
    assert observe(shadow, fixture)["proposed_cut"] is None


def test_v13_shadow_known_child_push_uses_live_pr_intent_without_rewriting_commit(shadow, stack_fixture):
    fixture = stack_fixture
    assert "CI-Shadow:" not in git(fixture["root"], "show", "-s", "--format=%B", fixture["head"])
    push(fixture)
    assert observe(shadow, fixture)["proposed_cut"] == fixture["cut"]


@pytest.mark.parametrize("mutation", ["closed", "draft", "no-intent", "wrong-cut", "body-after", "head-after", "api"])
def test_v13_shadow_known_push_needs_current_open_source_proof(shadow, stack_fixture, mutation):
    fixture = stack_fixture
    push(fixture)
    if mutation == "closed":
        fixture["pr"]["state"] = "closed"
    elif mutation == "draft":
        fixture["pr"]["draft"] = True
    elif mutation == "no-intent":
        fixture["pr"]["body"] = "Depends-On: #88"
    elif mutation == "wrong-cut":
        fixture["pr"]["body"] = fixture["pr"]["body"].replace(
            fixture["cut"], "P05" if fixture["cut"] == "P03" else "P03")
    original, reads = api(fixture), 0
    def request(repo, endpoint):
        nonlocal reads
        if endpoint == "pulls/7":
            reads += 1
            if mutation == "api":
                raise subprocess.TimeoutExpired("gh", 15)
        result = original(repo, endpoint)
        if endpoint == "pulls/7" and reads > 1:
            if mutation == "body-after":
                result["body"] += "\nchanged"
            elif mutation == "head-after":
                result["head"]["sha"] = "a" * 40
        return result
    assert observe(shadow, fixture, request)["proposed_cut"] is None


@pytest.mark.parametrize("mutation", ["bool-number", "prerequisite-number", "bad-head", "reserved-branch", "duplicate-source"])
def test_v13_shadow_invalid_source_bindings_fall_back(shadow, fixture, mutation):
    policy = fixture["policy"]
    source = policy["profiles"]["P03"]["source"]
    if mutation == "bool-number":
        source["number"] = True
    elif mutation == "prerequisite-number":
        source["number"] = 88
    elif mutation == "bad-head":
        source["head"] = "--output=bad"
    elif mutation == "reserved-branch":
        source["branch"] = "verify/forged"
    else:
        policy["profiles"]["P05"]["source"] = copy.deepcopy(source)
    write(fixture["root"], shadow.CONFIG, json.dumps(policy))
    fixture["main"] = commit(fixture["root"], "malformed binding")
    assert observe(shadow, fixture)["proposed_cut"] is None


@pytest.fixture
def yaml_reader():
    spec = importlib.util.spec_from_file_location("v13_shadow_yaml", UPSTREAM / "scripts/repo_shape.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_yaml


@NEEDS_UPSTREAM
def test_v13_shadow_workflow_trust_and_no_gating_contract(yaml_reader):
    workflow = yaml_reader(REPO / WORKFLOW)
    assert workflow["permissions"] == {}
    assert set(workflow["on"]) == {"pull_request", "push"}
    assert {"closed", "dequeued", "edited", "synchronize"} <= set(workflow["on"]["pull_request"]["types"])
    assert set(workflow["jobs"]) == {"observe", "contract"}
    observer, contract = (workflow["jobs"][name] for name in ("observe", "contract"))
    assert observer["permissions"] == {"contents": "read", "pull-requests": "read"}
    assert observer["steps"][0]["with"] == {"ref": "main", "fetch-depth": 0, "persist-credentials": False}
    assert "if" not in observer
    assert "opened" in contract["if"] and "synchronize" in contract["if"]
    assert contract["permissions"] == {"contents": "read"}
    assert contract["steps"][0]["with"] == {"submodules": True, "persist-credentials": False}
    assert contract["steps"][-1]["run"] == "bash tests/run.sh -k v13_shadow"
    assert all("GH_TOKEN" not in step.get("env", {}) for step in contract["steps"])
    for job in workflow["jobs"].values():
        assert not {"needs", "outputs", "environment"} & set(job)
        for step in job["steps"]:
            if "run" in step:
                assert "${{" not in step["run"]
            if "uses" in step:
                assert len(step["uses"].rsplit("@", 1)[1]) == 40
    assert "GITHUB_OUTPUT" not in SCRIPT.read_text()


@NEEDS_UPSTREAM
def test_v13_shadow_bootstrap_never_runs_pr_code(tmp_path, yaml_reader):
    script = yaml_reader(REPO / WORKFLOW)["jobs"]["observe"]["steps"][-1]["run"]
    tools = tmp_path / "bin"
    tools.mkdir()
    fake = tools / "python3"
    fake.write_text('#!/bin/sh\ntouch "$SHADOW_SENTINEL"\nexit 99\n')
    fake.chmod(0o755)
    sentinel, summary = tmp_path / "called", tmp_path / "summary"
    output = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            env=dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"],
                                     SHADOW_SENTINEL=str(sentinel), GITHUB_STEP_SUMMARY=str(summary)),
                            capture_output=True, text=True, timeout=10)
    assert output.returncode == 0, output.stderr
    result = json.loads(output.stdout)
    assert result["required_ci"] == "full" and result["efficiency_enabled"] is False
    assert result["skip_ci"] is False and result["queue_admission"] is False
    assert result["qualification"] == "not-qualified" and result["proposed_cut"] is None
    assert result["reason"] == "policy-unavailable"
    assert not sentinel.exists()


@NEEDS_UPSTREAM
def test_v13_shadow_controls_trigger_existing_full_reuse_without_selectors(yaml_reader):
    caller = yaml_reader(REPO / ".github/workflows/full-ci-parity.yml")
    assert set(caller["jobs"]) == {"parity", "full-ci", "qualification"}
    reuse = caller["jobs"]["full-ci"]
    assert reuse["uses"] == "./.github/workflows/tests.yml" and "with" not in reuse
    paths = caller["on"]["pull_request"]["paths"]
    assert {WORKFLOW, ".github/ci/v13_shadow.py", ".github/ci/shadow_scope.py", ".github/ci/v13-shadow-profiles.json",
            ".github/ci/v13-shadow.md", "tests/test_v13_shadow.py"} <= set(paths)


def test_v13_shadow_is_disabled_and_not_consumed_by_live_delivery():
    policy = json.loads((REPO / ".github/ci/v13-shadow-profiles.json").read_text())
    assert policy["efficiency_enabled"] is False
    for path in (".github/workflows/tests.yml", ".github/ci/delivery-policy.json",
                 ".github/ci/delivery_route.py", ".github/ci/delivery_verify.py",
                 ".github/ci/delivery_evidence.py"):
        text = (REPO / path).read_text()
        assert "v13_shadow" not in text and "sql-register-v13" not in text
    # The staged named queue declares delivery intent, never observation output.
    # Its separate false flag and heavy-held merge gate are covered by delivery
    # tests; banning its scope name here would forbid even disabled staging.
    queue_text = (REPO / ".mergify.yml").read_text()
    assert "v13_shadow" not in queue_text and "v13-shadow" not in queue_text
    assert "queue_admission" not in queue_text and "skip_ci" not in queue_text


def test_v13_shadow_cli_bad_payload_stays_safe_without_network(tmp_path):
    payload, summary = tmp_path / "event.json", tmp_path / "summary"
    payload.write_text("invalid JSON")
    output = subprocess.check_output([sys.executable, str(SCRIPT)], cwd=tmp_path, text=True,
                                     env=dict(os.environ, GITHUB_EVENT_PATH=str(payload),
                                              GITHUB_REPOSITORY="foreign/repository",
                                              GITHUB_STEP_SUMMARY=str(summary)))
    result = json.loads(output)
    assert result["required_ci"] == "full" and result["efficiency_enabled"] is False
    assert result["skip_ci"] is False and result["queue_admission"] is False
    assert "Full CI remains required" in summary.read_text()
