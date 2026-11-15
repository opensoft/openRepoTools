# SPDX-License-Identifier: Apache-2.0
"""Offline cutover refusal contracts. No queue, settings or credential writes."""

from __future__ import annotations

import copy
import hashlib
import importlib
import io
import json
import os
import subprocess
import sys
import zipfile

import pytest

from conftest import REPO, NEEDS_UPSTREAM
from test_ci_delivery import batch, base_changes, delivery, git, request_for, threads, verify
from test_ci_pilot_queue import reader as yaml_reader, matches


@pytest.fixture
def cutover():
    sys.path.insert(0, str(REPO / ".github/ci"))
    try:
        yield importlib.import_module("delivery_route")
    finally:
        sys.path.remove(str(REPO / ".github/ci"))


def rules(*contexts):
    return [{"type": "required_status_checks", "parameters": {
        "required_status_checks": [{"context": name, "integration_id": app}
                                   for name, app in contexts]}}]


def classic_clear():
    return {"name": "main", "protected": True, "protection": {"enabled": False,
            "required_status_checks": {"enforcement_level": "off", "contexts": [], "checks": []}}}


@pytest.mark.parametrize("rows,expected", [
    (rules(("openrepotools-delivery", 15368)), True),
    ([], False), (rules(("openrepotools-delivery", None)), False),
    (rules(("openrepotools-delivery", 1)), False),
    (rules(("openrepotools-delivery", 15368), ("tests", None)), False),
    (rules(("openrepotools-delivery", 15368), ("package", 15368)), False),
    ({"error": "not a complete list"}, False),
])
def test_ci_cutover_effective_gate_is_app_bound_without_old_requirements(cutover, rows, expected):
    assert cutover.effective_gate(lambda _repo, path: classic_clear() if path == "branches/main" else rows) is expected


def test_ci_cutover_committed_configuration_is_enabled(cutover):
    assert cutover.enabled(REPO) is True


@pytest.mark.parametrize("rows", [[], rules(("openrepotools-delivery", None)),
    rules(("openrepotools-delivery", 15368), ("tests", None))])
def test_ci_cutover_enabled_default_retains_full_with_unmigrated_protection(cutover, rows):
    assert cutover.enabled(REPO) is True
    request = lambda _repo, path: classic_clear() if path == "branches/main" else rows
    assert cutover.route({}, {}, REPO, request) == {"mode": "full", "omit_full": False}


@pytest.mark.parametrize("config", [None, {}, {"schema_version": 1, "enabled": 1},
    {"schema_version": True, "enabled": True},
    {"schema_version": 1, "enabled": True, "scope": "everything"}])
def test_ci_cutover_configuration_uncertainty_is_full(cutover, tmp_path, config):
    path = tmp_path / ".github/ci/delivery-policy.json"
    path.parent.mkdir(parents=True)
    if config is not None:
        path.write_text(json.dumps(config))
    assert cutover.enabled(tmp_path) is False


def test_ci_cutover_disabled_requires_no_network(cutover, tmp_path):
    path = tmp_path / ".github/ci/delivery-policy.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema_version": 1, "enabled": False}))
    def forbidden(*_args):
        pytest.fail("disabled routing must not query GitHub")
    assert cutover.enabled(tmp_path) is False
    assert cutover.route({}, {}, tmp_path, forbidden) == {"mode": "full", "omit_full": False}


def enable_fixture(cutover, batch):
    path = batch["root"] / ".github/ci/delivery-policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"schema_version":1,"enabled":true}')
    batch["data"]["rules/branches/main?per_page=100&page=1"] = rules((cutover.GATE, 15368))
    batch["data"]["branches/main"] = classic_clear()
    for pr in batch["prs"].values():
        pr["body"] += "\nCI-Delivery: claude-current"
        batch["data"]["git/ref/heads/" + pr["head"]["ref"]] = {"object": {"sha": pr["head"]["sha"]}}


def run_row(cutover, number, head, branch, path, event="push"):
    return {"id": number, "event": event, "path": path, "head_sha": head, "head_branch": branch,
            "repository": {"full_name": cutover.REPOSITORY, "id": cutover.evidence.REPOSITORY_ID},
            "head_repository": {"full_name": cutover.REPOSITORY, "id": cutover.evidence.REPOSITORY_ID},
            "actor": {"login": "mergify[bot]"}, "triggering_actor": {"login": "mergify[bot]"},
            "run_attempt": 1, "status": "in_progress", "conclusion": None}


def source_fixture(cutover, batch):
    enable_fixture(cutover, batch)
    pr = batch["prs"][7]
    env = dict(batch["env"], GITHUB_EVENT_NAME="pull_request", GITHUB_RUN_ID="501",
               GITHUB_RUN_ATTEMPT="1", GITHUB_SHA=batch["prefixes"][0], GITHUB_REF="refs/pull/7/merge")
    event = {"action": "synchronize", "number": 7, "pull_request": copy.deepcopy(pr)}
    batch["data"]["actions/runs/501"] = run_row(cutover, 501, pr["head"]["sha"],
                                                  pr["head"]["ref"], cutover.DIRECT, "pull_request")
    return env, event


def route_fixture(cutover, batch, env, event):
    return cutover.route(env, event, batch["root"], request_for(batch),
                         threads=lambda number: threads(number, batch), base_changes=base_changes)


def test_ci_cutover_verified_source_selects_fast_but_not_merge_authority(cutover, batch):
    env, event = source_fixture(cutover, batch)
    result = route_fixture(cutover, batch, env, event)
    assert result["mode"] == "source"
    assert result["omit_full"] is True
    assert len(result["proof"]) == 64
    assert "queue_admission" not in result


@pytest.mark.parametrize("field", ["merged", "merge_commit_sha"])
def test_ci_cutover_source_snapshot_diagnostic_has_names_not_values(cutover, batch, capsys, field):
    env, event = source_fixture(cutover, batch)
    if field == "merge_commit_sha":
        batch["prs"][7][field] = env["GITHUB_SHA"]
    event["pull_request"][field] = "f" * 40 if field == "merge_commit_sha" else None
    batch["prs"][7]["body"] += "\nPrivate prose must never be logged."
    assert route_fixture(cutover, batch, env, event) == cutover.FULL
    rows = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert rows == [
        {"delivery_diagnostic": "snapshot-mismatch", "stage": "source", "fields": [field]},
        {"delivery_diagnostic": "event-merge-hint" if field == "merge_commit_sha" else "source-metadata",
         "stage": "source"},
    ]


@pytest.mark.parametrize("message,reason", [
    ("Reusable/foreign workflow must remain full", "incomplete-evidence"),
    ("Private exception / token / body must never be logged.", "incomplete-evidence"),
])
def test_ci_cutover_diagnostic_does_not_echo_exception_text(cutover, batch, monkeypatch, capsys,
                                                          message, reason):
    env, event = source_fixture(cutover, batch)
    def fail(*_args):
        raise ValueError(message)
    monkeypatch.setattr(cutover, "current_run", fail)
    assert route_fixture(cutover, batch, env, event) == cutover.FULL
    assert json.loads(capsys.readouterr().err) == {
        "delivery_diagnostic": reason, "stage": "workflow-identity"}


@pytest.mark.parametrize("message,reason", [
    ("Missing or ambiguous fast check", "fast-check-count"),
    ("Fast run/check changed during verification", "fast-reread"),
])
def test_ci_cutover_fast_refusal_diagnostic_keeps_full(cutover, batch, monkeypatch, capsys,
                                                     message, reason):
    env, event = source_fixture(cutover, batch)
    def fail(*_args, **_kwargs):
        raise cutover.verifier.Refused(message)
    monkeypatch.setattr(cutover.verifier, "fast_receipt", fail)
    assert route_fixture(cutover, batch, env, event) == cutover.FULL
    assert json.loads(capsys.readouterr().err) == {
        "delivery_diagnostic": reason, "stage": "source"}


def test_ci_cutover_success_has_no_refusal_diagnostic(cutover, batch, capsys):
    env, event = source_fixture(cutover, batch)
    assert route_fixture(cutover, batch, env, event)["mode"] == "source"
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("side", ["event", "live"])
@pytest.mark.parametrize("prose", ["prefix", "suffix", "replace"])
def test_ci_cutover_source_description_prose_preserves_decision(cutover, batch, side, prose):
    env, event = source_fixture(cutover, batch)
    expected = route_fixture(cutover, batch, env, event)
    assert expected["mode"] == "source" and expected["omit_full"] is True
    pr = event["pull_request"] if side == "event" else batch["prs"][7]
    if prose == "prefix":
        pr["body"] = "Explanatory prose.\n\n" + pr["body"]
    elif prose == "suffix":
        pr["body"] += "\n\n## Summary by Sourcery\n\nHelp summary."
    else:
        pr["body"] = "Revised prose.\nCI-Shadow: claude-current\nCI-Delivery: claude-current"
    assert route_fixture(cutover, batch, env, event) == expected


@pytest.mark.parametrize("side", ["event", "live"])
@pytest.mark.parametrize("change", ["missing-shadow", "duplicate-shadow", "wrong-shadow",
    "missing-delivery", "duplicate-delivery", "wrong-delivery", "dependency", "non-string"])
def test_ci_cutover_source_description_decision_drift_is_full(cutover, batch, side, change):
    env, event = source_fixture(cutover, batch)
    pr = event["pull_request"] if side == "event" else batch["prs"][7]
    marker = "CI-Shadow: claude-current" if change.endswith("shadow") else "CI-Delivery: claude-current"
    if change.startswith("missing"):
        pr["body"] = pr["body"].replace(marker, "")
    elif change.startswith("duplicate"):
        pr["body"] += "\n" + marker
    elif change.startswith("wrong"):
        pr["body"] = pr["body"].replace(marker, marker.replace("claude-current", "other"))
    elif change == "dependency":
        pr["body"] += "\nDepends-On: #123"
    else:
        pr["body"] = None
    assert route_fixture(cutover, batch, env, event) == cutover.FULL


@pytest.mark.parametrize("side", ["event", "live"])
@pytest.mark.parametrize("field", ["state", "draft", "merged", "author", "head-sha",
    "head-ref", "base-sha", "base-ref", "merge-sha"])
def test_ci_cutover_source_prose_does_not_relax_other_metadata(cutover, batch, side, field):
    env, event = source_fixture(cutover, batch)
    pr = event["pull_request"] if side == "event" else batch["prs"][7]
    pr["body"] += "\nUnrelated summary."
    if field == "state":
        pr["state"] = "closed"
    elif field in {"draft", "merged"}:
        pr[field] = True
    elif field == "author":
        pr["user"]["login"] = "other-author"
    elif field == "merge-sha":
        pr["merge_commit_sha"] = "f" * 40
    else:
        name, part = field.split("-")
        pr[name][part] = "f" * 40 if part == "sha" else "other-ref"
    assert route_fixture(cutover, batch, env, event) == cutover.FULL


def test_ci_cutover_source_description_live_reread_stays_strict(cutover, batch):
    env, event = source_fixture(cutover, batch)
    original = request_for(batch)
    reads = 0
    def request(repo, endpoint):
        nonlocal reads
        if endpoint == "pulls/7":
            reads += 1
            if reads == 2:
                batch["prs"][7]["body"] += "\nLive summary race."
        return original(repo, endpoint)
    assert cutover.route(env, event, batch["root"], request,
        threads=lambda number: threads(number, batch), base_changes=base_changes) == cutover.FULL
    assert reads >= 2


@pytest.mark.parametrize("failure", ["old-rules", "no-new-rule", "wrong-app", "reusable", "manual",
    "nightly", "release", "foreign-run", "rerun-mismatch", "run-head", "no-opt-in", "duplicate-intent",
    "draft", "base", "event-head", "test-merge", "fast-failed", "retarget", "api-error", "rules-race"])
def test_ci_cutover_source_uncertainty_keeps_full(cutover, batch, failure):
    env, event = source_fixture(cutover, batch)
    data = batch["data"]
    if failure == "old-rules":
        data["rules/branches/main?per_page=100&page=1"] += rules(("tests", None))
    elif failure == "no-new-rule":
        data["rules/branches/main?per_page=100&page=1"] = []
    elif failure == "wrong-app":
        data["rules/branches/main?per_page=100&page=1"] = rules((cutover.GATE, None))
    elif failure == "reusable":
        data["actions/runs/501"]["path"] = ".github/workflows/full-ci-parity.yml"
    elif failure in {"manual", "nightly", "release"}:
        env["GITHUB_EVENT_NAME"] = {"manual": "workflow_dispatch", "nightly": "schedule", "release": "push"}[failure]
        env["GITHUB_REF"] = "refs/heads/release/v1.3"
        data["actions/runs/501"]["event"] = env["GITHUB_EVENT_NAME"]
    elif failure == "foreign-run":
        data["actions/runs/501"]["repository"]["id"] = 2
    elif failure == "rerun-mismatch":
        data["actions/runs/501"]["run_attempt"] = 2
    elif failure == "run-head":
        data["actions/runs/501"]["head_sha"] = batch["heads"][1]
    elif failure == "no-opt-in":
        batch["prs"][7]["body"] = "CI-Shadow: claude-current"
    elif failure == "duplicate-intent":
        batch["prs"][7]["body"] += "\nCI-Delivery: claude-current"
    elif failure == "draft":
        batch["prs"][7]["draft"] = True
    elif failure == "base":
        batch["prs"][7]["base"]["ref"] = "other"
    elif failure == "event-head":
        event["pull_request"]["head"]["sha"] = batch["heads"][1]
    elif failure == "test-merge":
        env["GITHUB_SHA"] = batch["heads"][0]
    elif failure == "fast-failed":
        data["actions/runs/107"]["conclusion"] = "failure"
    request = request_for(batch)
    calls = []
    def reader(repo, endpoint):
        calls.append(endpoint)
        if failure == "api-error":
            raise OSError("offline")
        if failure == "rules-race" and endpoint.startswith("rules/") and calls.count(endpoint) == 2:
            return []
        return request(repo, endpoint)
    result = cutover.route(env, event, batch["root"], reader, threads=lambda number: threads(number, batch),
        base_changes=(lambda _number: {"pageInfo": {"hasNextPage": False}, "nodes":
                      [{"createdAt": "2026-11-12T00:00:00Z"}]}) if failure == "retarget" else base_changes)
    assert result == cutover.FULL


def test_ci_cutover_effective_rules_exhaust_pagination(cutover):
    first = [{"type": "other"}] * 100
    seen = []
    def reader(_repo, endpoint):
        seen.append(endpoint)
        return first if endpoint.endswith("page=1") else rules((cutover.GATE, 15368), ("package", None))
    assert cutover.effective_gate(reader) is False
    assert len(seen) == 2
    assert cutover.effective_gate(lambda _repo, _endpoint: first) is False


@pytest.fixture
def artifact(cutover, batch, delivery):
    enable_fixture(cutover, batch)
    proof = verify(delivery, batch)
    run = run_row(cutover, 601, batch["candidate"], "mergify/merge-queue/0123456789", cutover.evidence.CALLER)
    env = dict(batch["env"], GITHUB_RUN_ID="601", GITHUB_RUN_ATTEMPT="1")
    batch["data"]["actions/runs/601"] = run
    record = cutover.evidence.make_record(proof, "admission", env, request_for(batch))
    return {"run": run, "record": record, "env": env}


def zip_record(record, names=("proof.json",)):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name in names:
            archive.writestr(name, json.dumps(record))
    return output.getvalue()


def install_artifact(cutover, batch, artifact, phase="admission", names=("proof.json",)):
    artifact["record"]["phase"] = phase
    data = zip_record(artifact["record"], names)
    run = artifact["run"]
    row = {"id": 701, "name": f"candidate-{phase}-{run['head_sha']}-a1", "expired": False,
           "size_in_bytes": len(data), "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
           "workflow_run": {"id": run["id"], "repository_id": cutover.evidence.REPOSITORY_ID,
                            "head_repository_id": cutover.evidence.REPOSITORY_ID, "head_sha": run["head_sha"]}}
    batch["data"]["actions/runs/601/artifacts?per_page=100&page=1"] = {"total_count": 1, "artifacts": [row]}
    batch["data"]["actions/artifacts/701"] = row
    return data, row


def test_ci_cutover_archive_roundtrip(cutover, batch, artifact):
    data, _ = install_artifact(cutover, batch, artifact)
    assert cutover.evidence.artifact_record(artifact["run"], "admission", request_for(batch),
                                           lambda _id: data) == artifact["record"]


def test_ci_cutover_pruned_candidate_fetch_is_fixed_public_object_only(cutover, batch, artifact, monkeypatch):
    original, fetches = cutover.policy.git, []
    def read(root, *args):
        if args[0] == "cat-file" and not fetches:
            raise subprocess.CalledProcessError(1, args)
        if "fetch" in args:
            fetches.append(args)
            return b""
        return original(root, *args)
    monkeypatch.setattr(cutover.policy, "git", read)
    cutover.evidence.candidate_chain(artifact["record"], batch["root"])
    assert fetches == [("-c", "credential.helper=", "-c", "credential.interactive=false", "-c",
        "fetch.recurseSubmodules=false", "fetch", "--no-tags", "--no-write-fetch-head",
        "https://github.com/opensoft/openRepoTools-code.git", batch["candidate"])]


@pytest.mark.parametrize("intended", [True, False])
def test_ci_cutover_top_heavy_cli_requires_current_delivery_intent(delivery, tmp_path, monkeypatch, intended):
    event = tmp_path / "event.json"
    event.write_text("{}")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setattr(sys, "argv", ["delivery_verify.py", "candidate", "--require-delivery"])
    monkeypatch.setattr(delivery, "verify_candidate", lambda *_args: {"members": [{"delivery": intended}]})
    if intended:
        delivery.main()
    else:
        with pytest.raises(SystemExit) as refused:
            delivery.main()
        assert refused.value.code == 1


def test_ci_cutover_proof_writer_uses_only_exclusive_fixed_temp_file(delivery, tmp_path):
    record = {"fixture": "validated record"}
    delivery.write_record(record, {"RUNNER_TEMP": str(tmp_path)})
    destination = tmp_path / "proof.json"
    assert json.loads(destination.read_text()) == record
    with pytest.raises(FileExistsError):
        delivery.write_record({"fixture": "replacement"}, {"RUNNER_TEMP": str(tmp_path)})
    assert json.loads(destination.read_text()) == record


@pytest.mark.parametrize("failure", ["relative-directory", "missing-directory", "symlink-directory", "symlink-file", "oversized"])
def test_ci_cutover_proof_writer_refuses_redirection_and_overwrite(delivery, tmp_path, failure):
    destination, record = tmp_path, {"fixture": "record"}
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("preserve")
    if failure == "relative-directory": destination = "../outside"
    elif failure == "missing-directory": destination = tmp_path / "absent"
    elif failure == "symlink-directory":
        destination = tmp_path / "alias"
        destination.symlink_to(tmp_path, target_is_directory=True)
    elif failure == "symlink-file": (tmp_path / "proof.json").symlink_to(sentinel)
    elif failure == "oversized": record = {"fixture": "x" * 40000}
    with pytest.raises((ValueError, FileExistsError)):
        delivery.write_record(record, {"RUNNER_TEMP": str(destination)})
    assert sentinel.read_text() == "preserve"


def test_ci_cutover_cli_no_longer_accepts_an_output_path(delivery, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["delivery_verify.py", "candidate", "--proof-kind", "admission",
                                      "--proof-output", "/outside/credentials"])
    with pytest.raises(SystemExit) as refused:
        delivery.main()
    assert refused.value.code == 2


@pytest.mark.parametrize("failure", ["wrong-name", "expired", "oversized", "digest", "foreign-repo",
    "head", "run", "traversal", "extra-member", "bad-json", "schema", "attempt", "duplicate",
    "artifact-race", "run-race", "zip-bomb", "duplicate-json-key", "bad-zip"])
def test_ci_cutover_archive_rejects_forgery_and_races(cutover, batch, artifact, failure):
    if failure == "schema":
        artifact["record"]["proof"]["extra"] = True
    if failure == "attempt":
        artifact["record"]["run_attempt"] = 2
    data, row = install_artifact(cutover, batch, artifact,
        names=("../proof.json",) if failure == "traversal" else
              ("proof.json", "other.json") if failure == "extra-member" else ("proof.json",))
    if failure == "wrong-name": row["name"] = "other"
    if failure == "expired": row["expired"] = True
    if failure == "oversized": row["size_in_bytes"] = 999999
    if failure == "digest": row["digest"] = "sha256:" + "0" * 64
    if failure == "foreign-repo": row["workflow_run"]["repository_id"] = 2
    if failure == "head": row["workflow_run"]["head_sha"] = batch["heads"][0]
    if failure == "run": row["workflow_run"]["id"] = 2
    if failure in {"bad-json", "zip-bomb", "duplicate-json-key", "bad-zip"}:
        if failure == "bad-zip":
            data = b"not a zip"
        else:
            output = io.BytesIO()
            value = {"bad-json": "{", "zip-bomb": " " * 40000,
                     "duplicate-json-key": '{"phase":"admission","phase":"qualified"}'}[failure]
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("proof.json", value)
            data = output.getvalue()
        row["digest"] = "sha256:" + hashlib.sha256(data).hexdigest()
    if failure == "duplicate":
        batch["data"]["actions/runs/601/artifacts?per_page=100&page=1"] = {
            "total_count": 2, "artifacts": [row, row]}
    reader = request_for(batch)
    def request(repo, endpoint):
        result = reader(repo, endpoint)
        if failure == "artifact-race" and endpoint == "actions/artifacts/701":
            result["digest"] = "changed"
        if failure == "run-race" and endpoint == "actions/runs/601":
            result["run_attempt"] = 2
        return result
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        cutover.evidence.artifact_record(artifact["run"], "admission", request, lambda _id: data)


def candidate_discovery(cutover, batch, artifact):
    batch["data"][f"actions/workflows/task-set-candidate-shadow.yml/runs?head_sha={batch['candidate']}&per_page=100&page=1"] = {
        "total_count": 1, "workflow_runs": [artifact["run"]]}


def duplicate_fixture(cutover, batch, artifact):
    data, _ = install_artifact(cutover, batch, artifact)
    candidate_discovery(cutover, batch, artifact)
    pr = copy.deepcopy(batch["prs"][7])
    pr.update(number=9, draft=True, user={"login": "mergify[bot]"})
    pr["head"].update(sha=batch["candidate"], ref=artifact["run"]["head_branch"])
    batch["data"]["pulls/9"] = pr
    merge = git(batch["root"], "commit-tree", artifact["record"]["proof"]["tree"],
                "-p", batch["base"], "-p", batch["candidate"], "-m", "candidate test merge")
    env = dict(artifact["env"], GITHUB_EVENT_NAME="pull_request", GITHUB_RUN_ID="501",
               GITHUB_SHA=merge, GITHUB_REF="refs/pull/9/merge")
    event = {"action": "synchronize", "number": 9, "pull_request": copy.deepcopy(pr)}
    batch["data"]["actions/runs/501"] = run_row(cutover, 501, pr["head"]["sha"],
                                                  pr["head"]["ref"], cutover.DIRECT, "pull_request")
    return env, event, data


@pytest.fixture(params=["source", "candidate"])
def merge_hint_case(request, cutover, batch):
    if request.param == "source":
        env, event = source_fixture(cutover, batch)
        data = None
    else:
        env, event, data = duplicate_fixture(cutover, batch, request.getfixturevalue("artifact"))
    return env, event, data, batch["data"][f"pulls/{event['number']}"]


def hint_route(cutover, batch, case, request=None):
    env, event, data, _live = case
    return cutover.route(env, event, batch["root"], request or request_for(batch),
                         lambda _id: data, lambda number: threads(number, batch), base_changes)


def regenerated_hint(batch, case, label):
    """A different immutable commit ID for identical tested parents and tree."""
    tested = case[0]["GITHUB_SHA"]
    parents = git(batch["root"], "show", "-s", "--format=%P", tested).split()
    tree = git(batch["root"], "rev-parse", tested + "^{tree}")
    hint = git(batch["root"], "commit-tree", tree, "-p", parents[0],
               "-p", parents[1], "-m", "regenerated test merge " + label)
    assert hint != tested
    batch["data"]["git/commits/" + hint] = {
        "sha": hint, "tree": {"sha": tree},
        "parents": [{"sha": parent} for parent in parents],
    }
    return hint


@pytest.mark.parametrize("side", ["event", "live", "both", "same"])
def test_ci_cutover_regenerated_hint_same_parents_and_tree_preserves_proof(
        cutover, batch, merge_hint_case, side):
    env, event, _data, live = merge_hint_case
    expected = hint_route(cutover, batch, merge_hint_case)
    env_hint = regenerated_hint(batch, merge_hint_case, "event")
    live_hint = regenerated_hint(batch, merge_hint_case, "live")
    event["action"] = "reopened"
    event["pull_request"]["merge_commit_sha"] = env_hint if side != "live" else env["GITHUB_SHA"]
    live["merge_commit_sha"] = live_hint if side != "event" else env["GITHUB_SHA"]
    if side == "same":
        live["merge_commit_sha"] = env_hint
    reader, lookups = request_for(batch), []

    def request(repo, endpoint):
        if endpoint.startswith("git/commits/"):
            lookups.append(endpoint)
        return reader(repo, endpoint)

    assert hint_route(cutover, batch, merge_hint_case, request) == expected
    assert len(lookups) == (2 if side == "both" else 1)


@pytest.mark.parametrize("failure", [
    "returned-sha", "tree", "reversed-parents", "base", "head", "one-parent",
    "missing-tree", "malformed-parents",
])
def test_ci_cutover_regenerated_hint_unproven_identity_retains_full(
        cutover, batch, merge_hint_case, failure):
    env, event, _data, live = merge_hint_case
    hint = regenerated_hint(batch, merge_hint_case, "unproven")
    row = batch["data"]["git/commits/" + hint]
    if failure == "returned-sha": row["sha"] = "f" * 40
    elif failure == "tree": row["tree"]["sha"] = "f" * 40
    elif failure == "reversed-parents": row["parents"].reverse()
    elif failure in {"base", "head"}: row["parents"][1 if failure == "head" else 0]["sha"] = "f" * 40
    elif failure == "one-parent": row["parents"].pop()
    elif failure == "missing-tree": row.pop("tree")
    elif failure == "malformed-parents": row["parents"] = {}
    event["pull_request"]["merge_commit_sha"] = hint
    live["merge_commit_sha"] = env["GITHUB_SHA"]
    assert hint_route(cutover, batch, merge_hint_case) == cutover.FULL


def test_ci_cutover_regenerated_hint_does_not_mask_base_drift(cutover, batch, merge_hint_case):
    _env, event, _data, _live = merge_hint_case
    event["pull_request"]["merge_commit_sha"] = regenerated_hint(batch, merge_hint_case, "base-drift")
    event["pull_request"]["base"]["sha"] = "f" * 40
    assert hint_route(cutover, batch, merge_hint_case) == cutover.FULL


def test_ci_cutover_regenerated_hint_live_reread_remains_exact(cutover, batch, merge_hint_case):
    _env, event, _data, live = merge_hint_case
    event["pull_request"]["merge_commit_sha"] = regenerated_hint(batch, merge_hint_case, "before")
    replacement = regenerated_hint(batch, merge_hint_case, "after")
    reader, reads = request_for(batch), 0

    def request(repo, endpoint):
        nonlocal reads
        if endpoint == f"pulls/{event['number']}":
            reads += 1
            if reads == 2:
                live["merge_commit_sha"] = replacement
        return reader(repo, endpoint)

    observed = hint_route(cutover, batch, merge_hint_case, request)
    expected = {**cutover.FULL, "retryable": True} if event["number"] == 9 else cutover.FULL
    assert observed == expected and "proof" not in observed
    assert reads == 2


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
@pytest.mark.parametrize("event_hint,live_hint", [
    ("missing", "current"), ("null", "current"), ("current", "missing"),
    ("current", "null"), ("current", "current"), ("null", "null"),
])
def test_ci_cutover_generated_merge_hint_transition_preserves_proof(cutover, batch, merge_hint_case,
                                                                  action, event_hint, live_hint):
    env, event, _data, live = merge_hint_case
    expected = hint_route(cutover, batch, merge_hint_case)
    assert expected["omit_full"] is True
    event["action"] = action
    for pr, hint in ((event["pull_request"], event_hint), (live, live_hint)):
        if hint == "missing":
            pr.pop("merge_commit_sha", None)
        else:
            pr["merge_commit_sha"] = None if hint == "null" else env["GITHUB_SHA"]
    if expected["mode"] == "source":
        live["body"] += "\nUnrelated summary."
    assert hint_route(cutover, batch, merge_hint_case) == expected


@pytest.mark.parametrize("side", ["event", "live", "both"])
@pytest.mark.parametrize("hint", ["f" * 40, "malformed", True, 1, {}, []],
                         ids=["foreign-sha", "malformed", "boolean", "number", "object", "list"])
def test_ci_cutover_generated_merge_hint_unknown_retains_full(cutover, batch, merge_hint_case,
                                                            side, hint):
    env, event, _data, live = merge_hint_case
    assert hint_route(cutover, batch, merge_hint_case)["omit_full"] is True
    event["pull_request"]["merge_commit_sha"] = live["merge_commit_sha"] = env["GITHUB_SHA"]
    if side in {"event", "both"}:
        event["pull_request"]["merge_commit_sha"] = hint
    if side in {"live", "both"}:
        live["merge_commit_sha"] = hint
    assert hint_route(cutover, batch, merge_hint_case) == cutover.FULL


@pytest.mark.parametrize("commit", ["base", "source-head"])
def test_ci_cutover_generated_merge_hint_cannot_replace_tested_parents(cutover, batch,
                                                                     merge_hint_case, commit, capsys):
    env, event, _data, live = merge_hint_case
    env["GITHUB_SHA"] = batch["base"] if commit == "base" else batch["heads"][0]
    event["pull_request"]["merge_commit_sha"] = None
    live["merge_commit_sha"] = env["GITHUB_SHA"]
    assert hint_route(cutover, batch, merge_hint_case) == cutover.FULL
    rows = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert rows == [{"delivery_diagnostic": "source-test-merge" if event["number"] == 7
                    else "incomplete-evidence", "stage": "source" if event["number"] == 7 else "candidate"}]


def test_ci_cutover_generated_merge_hint_live_reread_stays_strict(cutover, batch, merge_hint_case):
    env, event, _data, live = merge_hint_case
    event["pull_request"]["merge_commit_sha"] = None
    live["merge_commit_sha"] = env["GITHUB_SHA"]
    stable = hint_route(cutover, batch, merge_hint_case)
    reader, reads = request_for(batch), 0
    def request(repo, endpoint):
        nonlocal reads
        if endpoint == f"pulls/{event['number']}":
            reads += 1
            if reads == 2:
                live["merge_commit_sha"] = None
        return reader(repo, endpoint)
    observed = hint_route(cutover, batch, merge_hint_case, request)
    expected = {**cutover.FULL, 'retryable': True} if stable['mode'] == 'candidate' else cutover.FULL
    assert observed == expected and 'proof' not in observed
    assert reads == 2
    if stable['mode'] == 'candidate':
        assert hint_route(cutover, batch, merge_hint_case) == stable


def test_ci_cutover_generated_merge_hint_keeps_candidate_body_exact(cutover, batch, artifact):
    env, event, data = duplicate_fixture(cutover, batch, artifact)
    live = batch["data"]["pulls/9"]
    event["pull_request"]["merge_commit_sha"] = None
    live["merge_commit_sha"] = env["GITHUB_SHA"]
    reader, reads = request_for(batch), []
    def request(repo, endpoint):
        if endpoint == "pulls/9":
            reads.append(True)
            if len(reads) == 2:
                live["body"] += "\nChanged candidate body during verification."
        return reader(repo, endpoint)
    observed = hint_route(cutover, batch, (env, event, data, live), request)
    assert observed == {**cutover.FULL, 'retryable': True}
    assert 'proof' not in observed
    assert len(reads) == 2


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_ci_cutover_generated_merge_hint_still_requires_admission(cutover, batch, artifact, failure):
    env, event, data = duplicate_fixture(cutover, batch, artifact)
    live = batch["data"]["pulls/9"]
    event["pull_request"]["merge_commit_sha"] = None
    live["merge_commit_sha"] = env["GITHUB_SHA"]
    if failure == "missing":
        batch["data"]["actions/runs/601/artifacts?per_page=100&page=1"] = {"total_count": 0, "artifacts": []}
    else:
        artifact["record"]["proof"]["members"][0]["tree"] = "0" * 40
        data, _ = install_artifact(cutover, batch, artifact)
    expected = {**cutover.FULL, "retryable": True} if failure == "missing" else cutover.FULL
    assert hint_route(cutover, batch, (env, event, data, live)) == expected


def test_ci_cutover_candidate_duplicate_requires_real_admission(cutover, batch, artifact):
    env, event, data = duplicate_fixture(cutover, batch, artifact)
    result = cutover.route(env, event, batch["root"], request_for(batch), lambda _id: data,
                           lambda number: threads(number, batch), base_changes)
    assert result["mode"] == "candidate"
    assert result["omit_full"] is True


@pytest.mark.parametrize("failure", ["no-admission", "no-intent", "source-closed", "candidate-author",
    "not-draft", "run-rerun", "run-failed", "run-cancelled", "workflow", "actor", "triggering-actor",
    "no-review", "wrong-base", "duplicate-run", "source-moved", "candidate-tree", "source-mode"])
def test_ci_cutover_candidate_uncertainty_retains_full(cutover, batch, artifact, failure):
    env, event, data = duplicate_fixture(cutover, batch, artifact)
    if failure == "no-admission":
        batch["data"]["actions/runs/601/artifacts?per_page=100&page=1"] = {"total_count": 0, "artifacts": []}
    elif failure == "no-intent":
        batch["prs"][7]["body"] = "CI-Shadow: claude-current"
    elif failure == "source-closed":
        batch["prs"][7]["state"] = "closed"
    elif failure == "candidate-author":
        batch["data"]["pulls/9"]["user"]["login"] = "writer"
    elif failure == "not-draft":
        batch["data"]["pulls/9"]["draft"] = False
    elif failure == "run-rerun":
        artifact["run"]["run_attempt"] = 2
    elif failure in {"run-failed", "run-cancelled"}:
        artifact["run"].update(status="completed", conclusion="failure" if failure == "run-failed" else "cancelled")
    elif failure == "workflow": artifact["run"]["path"] = ".github/workflows/tests.yml"
    elif failure == "actor": artifact["run"]["actor"]["login"] = "writer"
    elif failure == "triggering-actor": artifact["run"]["triggering_actor"]["login"] = "writer"
    elif failure == "no-review": batch["data"]["issues/7/comments?per_page=100"] = []
    elif failure == "wrong-base": batch["data"]["git/ref/heads/main"]["object"]["sha"] = batch["heads"][0]
    elif failure == "duplicate-run":
        endpoint = f"actions/workflows/task-set-candidate-shadow.yml/runs?head_sha={batch['candidate']}&per_page=100&page=1"
        batch["data"][endpoint] = {"total_count": 2, "workflow_runs": [artifact["run"], artifact["run"]]}
    elif failure == "source-moved": batch["prs"][7]["head"]["sha"] = batch["heads"][1]
    elif failure == "candidate-tree":
        artifact["record"]["proof"]["members"][0]["tree"] = "0" * 40
        data, _ = install_artifact(cutover, batch, artifact)
    elif failure == "source-mode":
        artifact["record"]["proof"]["members"][0]["delivery"] = False
        data, _ = install_artifact(cutover, batch, artifact)
    result = cutover.route(env, event, batch["root"], request_for(batch), lambda _id: data,
                           lambda number: threads(number, batch), base_changes)
    assert result == ({**cutover.FULL, "retryable": True} if failure == "no-admission" else cutover.FULL)


@pytest.mark.parametrize("state", ["failure", "skipped", "cancelled", "", "success\necho forged"])
@pytest.mark.parametrize("key", ["GUARD_RESULT", "TESTS_RESULT", "NO_SUBMODULE_RESULT", "PACKAGE_RESULT"])
def test_ci_cutover_full_gate_requires_every_actual_full_result(cutover, state, key):
    env = dict.fromkeys(("GUARD_RESULT", "TESTS_RESULT", "NO_SUBMODULE_RESULT", "PACKAGE_RESULT"), "success")
    cutover.gate(env, {}, REPO)
    env[key] = state
    with pytest.raises(ValueError):
        cutover.gate(env, {}, REPO)


def test_ci_cutover_omission_gate_refuses_disabled_or_changed_policy(cutover, monkeypatch):
    env = {"OMIT_FULL": "true", "ROUTE_MODE": "source", "ROUTE_PROOF": "a" * 64}
    with pytest.raises(ValueError):
        cutover.gate(env, {}, REPO)
    monkeypatch.setattr(cutover, "route", lambda *_args: {"mode": "source", "omit_full": True, "proof": "a" * 64})
    cutover.gate(env, {}, REPO)
    env["ROUTE_PROOF"] = "b" * 64
    with pytest.raises(ValueError):
        cutover.gate(env, {}, REPO)


@NEEDS_UPSTREAM
@pytest.mark.parametrize("omit,results,ok", [
    ("", ["success"] * 4, True), ("false", ["success"] * 4, True),
    ("true", ["success"] * 4, False), ("false", ["success", "skipped", "success", "success"], False),
    ("false", ["failure", "success", "success", "success"], False),
])
def test_ci_cutover_actual_bootstrap_shell_is_full_only(yaml_reader, tmp_path, omit, results, ok):
    workflow = yaml_reader(REPO / ".github/workflows/tests.yml")
    step = workflow["jobs"]["delivery-gate"]["steps"][1]
    result = subprocess.run(["bash", "-euo", "pipefail", "-c", step["run"]], cwd=tmp_path,
        env=dict(os.environ, OMIT_FULL=omit, **dict(zip(
            ("GUARD_RESULT", "TESTS_RESULT", "NO_SUBMODULE_RESULT", "PACKAGE_RESULT"), results))),
        capture_output=True, timeout=10)
    assert (result.returncode == 0) is ok


@NEEDS_UPSTREAM
def test_ci_cutover_controls_are_read_only_trusted_and_unfiltered(yaml_reader):
    workflow = yaml_reader(REPO / ".github/workflows/tests.yml")
    for key in ("delivery-route", "delivery-gate"):
        job = workflow["jobs"][key]
        assert job["permissions"] == {"contents": "read", "pull-requests": "read", "checks": "read", "actions": "read"}
        assert job["timeout-minutes"] == 15
        assert job["steps"][0]["with"] == {"ref": "main", "fetch-depth": 0, "persist-credentials": False}
        assert all("${{" not in step.get("run", "") for step in job["steps"])
        assert "continue-on-error" not in job
    gate = workflow["jobs"]["delivery-gate"]
    assert gate["name"] == "openrepotools-delivery"
    assert gate["if"] == "${{ always() }}"
    assert set(gate["needs"]) == {"delivery-route", "guard-launch-mode", "tests", "tests-no-submodule", "package"}


@NEEDS_UPSTREAM
@pytest.mark.parametrize("probe,qualify,candidate,ok", [
    ("success", "true", "success", True), ("failure", "true", "success", False),
    ("success", "false", "success", False), ("success", "true", "failure", False),
    ("success", "true", "skipped", False), ("success", "true", "cancelled", False),
])
def test_ci_cutover_top_level_heavy_shell_fails_closed(yaml_reader, tmp_path, probe, qualify, candidate, ok):
    workflow = yaml_reader(REPO / ".github/workflows/task-set-candidate-shadow.yml")
    job = workflow["jobs"]["heavy"]
    assert job["name"] == "openrepotools-batch-heavy"
    assert job["if"] == "${{ always() }}"
    result = subprocess.run(["bash", "-euo", "pipefail", "-c", job["steps"][0]["run"]], cwd=tmp_path,
        env=dict(os.environ, PROBE=probe, QUALIFY=qualify, CANDIDATE=candidate), capture_output=True, timeout=10)
    assert (result.returncode == 0) is ok
    assert job["steps"][-1]["run"] == "python3 .github/ci/delivery_verify.py candidate --require-delivery"


@NEEDS_UPSTREAM
def test_ci_cutover_manual_queue_holds_heavy_and_preserves_older_queues(yaml_reader):
    config = yaml_reader(REPO / ".mergify.yml")
    queue = config["queue_rules"][3]
    assert queue["name"] == "openrepotools-claude-current"
    assert queue["branch_protection_injection_mode"] == "queue"
    assert queue["batch_size"] == 2
    assert queue["batch_max_failure_resolution_attempts"] == 0
    assert queue["max_checks_retries"] == 0
    assert queue["checks_timeout"] == "90 minutes"
    assert queue["merge_conditions"] == ["check-success=@github-actions/openrepotools-batch-heavy"]
    context = {"draft": False, "closed": False, "from-fork": False, "head": "feature/scoped", "base": "main",
               "body": "CI-Shadow: claude-current\nCI-Delivery: claude-current",
               "files": ["claude-current"], "check-success": ["@github-actions/openrepotools-pr-fast", "@github-actions/openrepotools-delivery"]}
    assert all(matches(condition, context) for condition in queue["queue_conditions"])
    for key, value in [("files", ["claude-current", ".github/workflows/tests.yml"]), ("draft", True),
                       ("base", "feature/other"), ("body", "CI-Shadow: claude-current"), ("check-success", [])]:
        changed = dict(context, **{key: value})
        assert not all(matches(condition, changed) for condition in queue["queue_conditions"])
    # A frozen original-queue digest, not a history lookup: ordinary CI has a
    # depth-one checkout and must not depend on the old commit being present.
    assert hashlib.sha256(json.dumps(config["queue_rules"][:3], sort_keys=True,
        separators=(",", ":")).encode()).hexdigest() == "8fb841ba9bb2b01488cb2ea8f08fbb9b60f9b6537ba7c77efa84bcad75571c2c"


def qualified_fixture(cutover, batch, artifact, count=2):
    run = artifact["run"]
    run.update(status="completed", conclusion="success", referenced_workflows=[{
        "path": f"{cutover.REPOSITORY}/{path}@{batch['candidate']}", "sha": batch["candidate"],
        "ref": "refs/heads/" + run["head_branch"]} for path in sorted(cutover.evidence.CALLEES)])
    jobs = [{"id": 9000 + index, "run_id": 601, "run_attempt": 1, "head_sha": batch["candidate"],
             "name": name, "status": "completed", "conclusion": "success", "completed_at": "2026-11-12T00:00:10Z"}
            for index, name in enumerate(sorted(cutover.evidence.CANDIDATE_JOBS))]
    batch["data"]["actions/runs/601/attempts/1/jobs?per_page=100&page=1"] = {"total_count": len(jobs), "jobs": jobs}
    candidate_discovery(cutover, batch, artifact)
    batch["data"]["actions/workflows/task-set-candidate-shadow.yml/runs?per_page=20&page=1"] = {"workflow_runs": [run]}
    data, row = install_artifact(cutover, batch, artifact, "qualified")
    actual, previous = [], batch["base"]
    for member in artifact["record"]["proof"]["members"][:count]:
        landed = git(batch["root"], "commit-tree", member["tree"], "-p", previous,
                     "-p", member["head"], "-m", "landed source")
        batch["prs"][member["number"]].update(state="closed", merged=True,
            merge_commit_sha=landed, merged_at="2026-11-12T00:00:11Z")
        actual.append((previous, landed))
        previous = landed
    git(batch["root"], "checkout", "-q", "--detach", previous)
    batch["data"]["git/ref/heads/main"]["object"]["sha"] = previous
    env = dict(artifact["env"], GITHUB_RUN_ID="501", GITHUB_SHA=previous, GITHUB_REF="refs/heads/main")
    event = dict(batch["event"], ref="refs/heads/main", before=actual[-1][0], after=previous)
    batch["data"]["actions/runs/501"] = run_row(cutover, 501, previous, "main", cutover.DIRECT)
    return env, event, data, jobs, row


@pytest.mark.parametrize("count", [1, 2])
def test_ci_cutover_exact_closed_landing_prefix_uses_completed_proof(cutover, batch, artifact, count):
    env, event, data, _jobs, _row = qualified_fixture(cutover, batch, artifact, count)
    result = cutover.route(env, event, batch["root"], request_for(batch), lambda _id: data,
                           lambda number: threads(number, batch), base_changes)
    assert result["mode"] == "landing"
    assert result["omit_full"] is True


@pytest.mark.parametrize("failure", ["job-failed", "job-skipped", "job-cancelled", "job-missing",
    "job-duplicate", "job-name", "job-head", "job-attempt", "job-run", "run-rerun", "wrong-reuse",
    "wrong-callee", "wrong-actor", "wrong-main-actor", "forced", "before", "merge-time", "merge-record",
    "not-merged", "source-head", "policy-change", "unknown-run", "artifact-expired", "main-moved"])
def test_ci_cutover_lookalike_landing_and_incomplete_heavy_remain_full(cutover, batch, artifact, failure):
    env, event, data, jobs, row = qualified_fixture(cutover, batch, artifact)
    if failure.startswith("job-"):
        kind = failure[4:]
        if kind in {"failed", "skipped", "cancelled"}: jobs[0]["conclusion"] = kind
        elif kind == "missing": jobs.pop()
        elif kind == "duplicate": jobs[1] = copy.deepcopy(jobs[0])
        elif kind == "name": jobs[0]["name"] = "lookalike"
        elif kind == "head": jobs[0]["head_sha"] = batch["heads"][0]
        elif kind == "attempt": jobs[0]["run_attempt"] = 2
        elif kind == "run": jobs[0]["run_id"] = 2
    elif failure == "run-rerun": artifact["run"]["run_attempt"] = 2
    elif failure == "wrong-reuse": artifact["run"]["referenced_workflows"][0]["sha"] = batch["base"]
    elif failure == "wrong-callee": artifact["run"]["referenced_workflows"][0]["path"] = "foreign"
    elif failure == "wrong-actor": artifact["run"]["actor"]["login"] = "writer"
    elif failure == "wrong-main-actor": env["GITHUB_ACTOR"] = "writer"
    elif failure == "forced": event["forced"] = True
    elif failure == "before": event["before"] = batch["base"]
    elif failure == "merge-time": batch["prs"][7]["merged_at"] = "2026-11-12T00:00:09Z"
    elif failure == "merge-record": batch["prs"][7]["merge_commit_sha"] = batch["prefixes"][0]
    elif failure == "not-merged": batch["prs"][7]["merged"] = False
    elif failure == "source-head": batch["prs"][7]["head"]["sha"] = batch["heads"][1]
    elif failure == "artifact-expired": row["expired"] = True
    elif failure == "unknown-run": batch["data"]["actions/workflows/task-set-candidate-shadow.yml/runs?per_page=20&page=1"] = {"workflow_runs": []}
    elif failure == "main-moved": batch["data"]["git/ref/heads/main"]["object"]["sha"] = batch["base"]
    elif failure == "policy-change":
        (batch["root"] / "unrelated").write_text("changed policy")
        git(batch["root"], "add", "unrelated")
        git(batch["root"], "commit", "-qm", "unrelated new main")
        batch["data"]["git/ref/heads/main"]["object"]["sha"] = git(batch["root"], "rev-parse", "HEAD")
    assert cutover.route(env, event, batch["root"], request_for(batch), lambda _id: data,
                          lambda number: threads(number, batch), base_changes) == cutover.FULL
