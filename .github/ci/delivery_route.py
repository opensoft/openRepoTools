# SPDX-License-Identifier: Apache-2.0
"""Trusted-main, default-full CI routing. Reads only; never grants merge authority."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
import zipfile

import delivery_evidence as evidence
import delivery_verify as verifier
import shadow_scope as policy
import delivery_v13 as v13

REPOSITORY = policy.REPOSITORY
FULL = {"mode": "full", "omit_full": False}
LEGACY = {"guard-launch-mode", "tests", "tests-no-submodule", "package"}
GATE = "openrepotools-delivery"
DIRECT = ".github/workflows/tests.yml"
PARENTS = "--format=%P"
PENDING_ATTEMPTS = 30
ERRORS = policy.ERRORS + (zipfile.BadZipFile, RuntimeError)
require = verifier.require

# Only fixed vocabulary reaches logs: never exception text or API/body values.
REFUSALS = {
    "Source is not opted-in/current": "source-metadata",
    "Source is outside fixed scope": "source-scope",
    "Source event ref differs": "source-event-ref",
    "Source test-merge identity differs": "source-test-merge",
    "Source moved during verification": "source-reread",
    "Event merge hint is neither absent nor current": "event-merge-hint",
    "Candidate description is not string or null": "candidate-description-type",
    "Not a current scoped draft candidate": "candidate-metadata",
    "Candidate evidence moved": "candidate-reread",
    "Missing or ambiguous fast check": "fast-check-count",
    "Fast check is not successful exact-head Actions evidence": "fast-check-identity",
    "Fast evidence is not successful or authenticated pending work": "fast-state",
    "Unrecognized fast workflow identity": "fast-details-url",
    "Fast job identity differs": "fast-job-id",
    "Fast run belongs to another workflow/head or is incomplete": "fast-run-identity",
    "Fast run has no unique source PR": "fast-source-count",
    "Fast run source association differs": "fast-source-identity",
    "Incomplete base-change history": "fast-base-history",
    "Fast run predates a base change": "fast-retarget",
    "Fast job does not match the current successful run": "fast-job-identity",
    "Fast run/check changed during verification": "fast-reread",
}


def diagnostic(stage, reason, **details):
    print(json.dumps({"delivery_diagnostic": reason, "stage": stage, **details},
                     sort_keys=True), file=sys.stderr)


def enabled(root):
    try:
        value = evidence.read_json((root / ".github/ci/delivery-policy.json").read_bytes())
        return (set(value) == {"schema_version", "enabled"}
                and type(value["schema_version"]) is int and value["schema_version"] == 1
                and value["enabled"] is True)
    except policy.ERRORS:
        return False


def effective_gate(request=policy.github):
    try:
        rows = evidence.pages(request, "rules/branches/main", None)
        contexts = []
        for rule in rows:
            require(isinstance(rule, dict) and isinstance(rule["type"], str), "Malformed rule")
            if rule["type"] == "required_status_checks":
                values = rule["parameters"]["required_status_checks"]
                require(isinstance(values, list), "Malformed status rule")
                for value in values:
                    require(isinstance(value["context"], str) and "integration_id" in value,
                            "Incomplete app-bound rule")
                    contexts.append((value["context"], value["integration_id"]))
        if (not any(name == GATE and type(app) is int and app == 15368 for name, app in contexts)
                or any(name in LEGACY for name, _app in contexts)):
            return False
        # Rulesets and classic protection layer together. Public branch metadata
        # exposes the latter using existing Contents:read, without admin access.
        branch = request(REPOSITORY, "branches/main")
        protection = branch["protection"]
        checks = protection["required_status_checks"]
        require(branch["name"] == "main" and branch["protected"] is True
                and type(protection["enabled"]) is bool
                and checks["enforcement_level"] in {"off", "non_admins", "everyone"}
                and isinstance(checks["contexts"], list) and isinstance(checks["checks"], list),
                "Incomplete classic protection evidence")
        classic = list(checks["contexts"])
        classic.extend(row["context"] for row in checks["checks"])
        require(all(isinstance(name, str) and name for name in classic)
                and (protection["enabled"] or not classic)
                and (protection["enabled"] or checks["enforcement_level"] == "off")
                and (checks["enforcement_level"] != "off" or not classic),
                "Malformed classic status requirements")
        return not any(name in LEGACY for name in classic)
    except policy.ERRORS:
        return False


def current_run(env, request):
    require(env["GITHUB_REPOSITORY"] == REPOSITORY, "Foreign repository")
    run_id = evidence.positive(int(env["GITHUB_RUN_ID"]))
    run = request(REPOSITORY, f"actions/runs/{run_id}")
    require(run["id"] == run_id and run["repository"]["id"] == evidence.REPOSITORY_ID
            and run["repository"]["full_name"] == REPOSITORY
            and run["head_repository"]["full_name"] == REPOSITORY
            and run["head_repository"]["id"] == evidence.REPOSITORY_ID
            and run["run_attempt"] == int(env["GITHUB_RUN_ATTEMPT"])
            and run["event"] == env["GITHUB_EVENT_NAME"] and run["path"] == DIRECT,
            "Reusable/foreign workflow must remain full")
    return run


def current_merge_hints(env, pr, expected, root, request):
    """Accept regenerated metadata only with immutable parent/tree equivalence."""
    tested = policy.sha(env["GITHUB_SHA"])
    hints = (pr.get("merge_commit_sha"), expected.get("merge_commit_sha"))
    if all(hint is None or hint == tested for hint in hints):
        return True
    try:
        distinct = {policy.sha(hint) for hint in hints if hint is not None}
        evidence.ensure_commit(root, tested)
        parents = policy.git(root, "show", "-s", PARENTS, tested).decode().split()
        tree = policy.git(root, "rev-parse", tested + "^{tree}").decode().strip()
        if len(parents) != 2:
            return False
        for hint in distinct - {tested}:
            commit = request(REPOSITORY, "git/commits/" + hint)
            if (commit["sha"] != hint or commit["tree"]["sha"] != tree
                    or not isinstance(commit["parents"], list)
                    or [parent["sha"] for parent in commit["parents"]] != parents):
                return False
        return True
    except policy.ERRORS:
        return False


def source(env, event, root, main, request, base_changes):
    require(event["action"] in {"opened", "synchronize", "reopened"}, "Unsupported PR event")
    number = evidence.positive(event["number"])
    pr = request(REPOSITORY, f"pulls/{number}")
    expected = event["pull_request"]
    hints_current = current_merge_hints(env, pr, expected, root, request)
    comparison = dict(pr, body=expected.get("body"))
    if hints_current:
        comparison["merge_commit_sha"] = expected.get("merge_commit_sha")
    live_snapshot = policy.snapshot(comparison)
    event_snapshot = policy.snapshot(expected)
    if live_snapshot != event_snapshot:
        names = ("number", "state", "draft", "merged", "body", "merge_commit_sha",
                 "head", "base", "author")
        diagnostic("source", "snapshot-mismatch", fields=[name for name, live, old
                   in zip(names, live_snapshot, event_snapshot) if live != old])
    # Generated hints are not tested-commit authority. Keep ordered Git-parent
    # verification below and strict subsequent rereads of the original live PR.
    require(hints_current, "Event merge hint is neither absent nor current")
    # Prose may change before routing. Validate both decisions independently;
    # retain all other snapshot fields and strict subsequent live rereads.
    require(verifier.delivery_intended(expected.get("body"))
            and not re.search(r"(?m)^Depends-On:", expected["body"])
            and live_snapshot == event_snapshot
            and pr["state"] == "open" and pr["draft"] is False
            and pr["number"] == number and verifier.delivery_intended(pr["body"])
            and not re.search(r"(?m)^Depends-On:", pr["body"]), "Source is not opted-in/current")
    head, branch = policy.side(pr, "head")
    base, base_ref = policy.side(pr, "base")
    require(base == main and base_ref == "main" and policy.source_branch(branch),
            "Source is outside fixed scope")
    if v13.intended(pr.get("body")):
        v13.source(root, main, pr, request)
        v13.source(root, main, dict(pr, body=expected.get("body")), request)
    else:
        require(policy.regular_scope(root, main, head), "Source is outside fixed scope")
        policy.git(root, "merge-base", "--is-ancestor", main, head)
    require(env["GITHUB_REF"] == f"refs/pull/{number}/merge", "Source event ref differs")
    tested = evidence.ensure_commit(root, env["GITHUB_SHA"])
    require(policy.git(root, "show", "-s", PARENTS, tested).decode().split() == [main, head],
            "Source test-merge identity differs")
    fast = verifier.fast_receipt(pr, head, request, base_changes, allow_pending=True)
    require(pr == request(REPOSITORY, f"pulls/{number}")
            and request(REPOSITORY, "git/ref/heads/" + branch)["object"]["sha"] == head,
            "Source moved during verification")
    return {"base": main, "head": head, "tested": tested, "fast": evidence.digest(fast)}


def duplicate(env, event, root, main, request, fetch, threads, base_changes):
    require(event["action"] in {"opened", "synchronize", "reopened"}, "Unsupported candidate event")
    number = evidence.positive(event["number"])
    pr = request(REPOSITORY, f"pulls/{number}")
    head, branch = policy.side(pr, "head")
    expected = event["pull_request"]
    require(current_merge_hints(env, pr, expected, root, request),
            "Event merge hint is neither absent nor current")
    require(all(body is None or isinstance(body, str)
                for body in (pr.get("body"), expected.get("body"))),
            "Candidate description is not string or null")
    # Candidate prose grants no authority. Align only this initial comparison;
    # keep the original live PR for independent evidence and strict rereads.
    comparison = dict(pr, body=expected.get("body"),
                      merge_commit_sha=expected.get("merge_commit_sha"))
    live_snapshot = policy.snapshot(comparison)
    event_snapshot = policy.snapshot(expected)
    if live_snapshot != event_snapshot:
        names = ("number", "state", "draft", "merged", "body", "merge_commit_sha",
                 "head", "base", "author")
        diagnostic("candidate", "snapshot-mismatch", fields=[name for name, live, old
                   in zip(names, live_snapshot, event_snapshot) if live != old])
    require(live_snapshot == event_snapshot
            and pr["number"] == number and pr["state"] == "open" and pr["draft"] is True
            and pr["user"]["login"] == "mergify[bot]"
            and policy.side(pr, "base") == (main, "main")
            and policy.QUEUE.fullmatch(branch) is not None, "Not a current scoped draft candidate")
    require(env["GITHUB_REF"] == f"refs/pull/{number}/merge", "Candidate event ref differs")
    tested = evidence.ensure_commit(root, env["GITHUB_SHA"])
    require(policy.git(root, "show", "-s", PARENTS, tested).decode().split()
            == [main, head], "Candidate test-merge identity differs")
    run = evidence.candidate_runs(head, request)
    evidence.run_identity(run, head, branch)
    record = evidence.artifact_record(run, "admission", request, fetch, allow_pending=True)
    proof = evidence.candidate_chain(record, root)
    require(proof["base"] == main, "Admission belongs to another main")
    # Independently re-read live sources; do not manufacture a push payload to
    # trick the admission verifier into accepting a pull_request event.
    for member in proof["members"]:
        source_pr, _receipt = verifier.source_pr(member["head"], main, root, request, threads, base_changes)
        require(source_pr["number"] == member["number"]
                and verifier.delivery_intended(source_pr["body"]), "Admission source differs")
    current_pr = request(REPOSITORY, f"pulls/{number}")
    require(evidence.positive(current_pr["number"]) == number
            and current_pr["state"] == "open" and current_pr["draft"] is True
            and type(current_pr.get("merged")) is type(pr.get("merged"))
            and current_pr.get("merged") == pr.get("merged")
            and policy.side(current_pr, "head") == (head, branch)
            and policy.side(current_pr, "base") == (main, "main")
            and current_pr["user"]["login"] == "mergify[bot]", "Candidate evidence moved")
    require(current_pr.get("body") is None or isinstance(current_pr.get("body"), str),
            "Candidate description is not string or null")
    require(current_pr.get("merge_commit_sha") == pr.get("merge_commit_sha")
            or current_merge_hints(env, pr, current_pr, root, request),
            "Event merge hint is neither absent nor current")
    require(request(REPOSITORY, "git/ref/heads/" + branch)["object"]["sha"] == head,
            "Candidate evidence moved")
    current_run = evidence.run_identity(request(REPOSITORY, f"actions/runs/{run['id']}"), head, branch)
    require(current_run["id"] == run["id"]
            and (current_run["status"] == "completed" or current_run["conclusion"] is None),
            "Candidate evidence moved")
    moved = [name for name, old, current in
             (("pull_request", pr, current_pr), ("caller", run, current_run)) if old != current]
    if moved:
        # No raced view supplies proof. Reauthenticate the complete decision on
        # a fresh bounded observation; accepted views retain raw equality.
        diagnostic("candidate", "candidate-reread-pending", fields=moved)
        raise verifier.PendingEvidence("Authenticated candidate evidence moved")
    return {"candidate": head, "record": evidence.digest(record)}


def landed(env, event, root, request, fetch):
    after = policy.sha(env["GITHUB_SHA"])
    pair = policy.git(root, "show", "-s", PARENTS, after).decode().split()
    require(len(pair) == 2, "Main event is not a merge")
    response = request(REPOSITORY,
                       "actions/workflows/task-set-candidate-shadow.yml/runs?per_page=20&page=1")
    rows = response["workflow_runs"]
    require(isinstance(rows, list) and len(rows) <= 20, "Malformed recent candidate history")
    proofs = []
    for row in rows:
        if row["status"] != "completed" or row["conclusion"] != "success":
            continue
        try:
            run = evidence.run_identity(request(REPOSITORY, f"actions/runs/{evidence.positive(row['id'])}"),
                                        completed=True)
            # A per-head all-state lookup also refuses multiple historical runs
            # or a later rerun outside this recent discovery window.
            require(evidence.candidate_runs(run["head_sha"], request) == run,
                    "Candidate history is ambiguous")
            record = evidence.artifact_record(run, "qualified", request, fetch)
            if pair[1] not in [member["head"] for member in record["proof"]["members"]]:
                continue
            proofs.append(evidence.landing(record, run, env, event, root, request))
        except ERRORS:
            # An unrelated/expired candidate is not evidence for this landing.
            continue
    require(len(proofs) == 1, "No unique completed landing proof")
    return proofs[0]


def route(env, event, root, request=policy.github, fetch=evidence.download,
          threads=verifier.read_threads, base_changes=verifier.read_base_changes):
    if not enabled(root):
        return dict(FULL)
    stage = "effective-protection"
    try:
        require(effective_gate(request), "Effective protection is not migrated")
        stage = "workflow-identity"
        run = current_run(env, request)
        stage = "trusted-main"
        main = policy.sha(policy.git(root, "rev-parse", "HEAD").decode().strip())
        require(request(REPOSITORY, "git/ref/heads/main")["object"]["sha"] == main,
                "Trusted main changed")
        kind = env["GITHUB_EVENT_NAME"]
        if kind == "pull_request":
            stage = "event-identity"
            head, branch = policy.side(event["pull_request"], "head")
            require(run["head_sha"] == head and run["head_branch"] == branch, "Run source differs")
            if policy.QUEUE.fullmatch(branch):
                stage = "candidate"
                proof = duplicate(env, event, root, main, request, fetch, threads, base_changes)
                mode = "candidate"
            else:
                stage = "source"
                proof = source(env, event, root, main, request, base_changes)
                mode = "source"
        elif kind == "push" and env["GITHUB_REF"] == "refs/heads/main":
            stage = "landing"
            require(run["head_sha"] == policy.sha(env["GITHUB_SHA"])
                    and run["head_branch"] == "main", "Run landing differs")
            proof = landed(env, event, root, request, fetch)
            mode = "landing"
        else:
            return dict(FULL)
        stage = "final-reread"
        require(effective_gate(request)
                and request(REPOSITORY, "git/ref/heads/main")["object"]["sha"] == main
                and run == request(REPOSITORY, f"actions/runs/{run['id']}"), "Routing evidence changed")
        return {"mode": mode, "omit_full": True, "proof": evidence.digest(proof)}
    except verifier.PendingEvidence:
        return {**FULL, "retryable": True}
    except ERRORS as exc:
        diagnostic(stage, REFUSALS.get(str(exc), "incomplete-evidence"))
        return dict(FULL)


def bounded_observation(observe):
    """Only authenticated pending decisions retry; waiting never supplies proof."""
    result = observe()
    for _ in range(PENDING_ATTEMPTS):
        if not result.get("retryable", False):
            break
        time.sleep(10)
        result = observe()
    return result


def gate(env, event, root, request=policy.github):
    if env.get("OMIT_FULL") == "true":
        observe = lambda: route(env, event, root, request)
        result = bounded_observation(observe) if env["ROUTE_MODE"] == "candidate" else observe()
        require(result["omit_full"] is True and result["mode"] == env["ROUTE_MODE"]
                and result["proof"] == env["ROUTE_PROOF"], "Omitted-work proof no longer verifies")
    else:
        require(all(env.get(key) == "success" for key in
                    ("GUARD_RESULT", "TESTS_RESULT", "NO_SUBMODULE_RESULT", "PACKAGE_RESULT")),
                "Full suite did not succeed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("route", "gate"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        event = evidence.read_json(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
        if args.mode == "gate":
            gate(os.environ, event, root)
            return
        # Only authenticated pending observations merit bounded waits. Definite
        # full-only, malformed, failed or unknown outcomes return immediately.
        result = bounded_observation(lambda: route(os.environ, event, root))
        result.pop("retryable", None)
    except ERRORS:
        if args.mode == "gate":
            parser.exit(1, "Delivery gate refused incomplete, changed or unsuccessful evidence.\n")
        result = dict(FULL)
    print(json.dumps(result, sort_keys=True))
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"mode={result['mode']}\nomit_full={str(result['omit_full']).lower()}\n"
                     f"proof={result.get('proof', '')}\n")


if __name__ == "__main__":
    main()
