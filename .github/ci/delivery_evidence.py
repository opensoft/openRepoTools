# SPDX-License-Identifier: Apache-2.0
"""Read-only candidate receipts and separate historical landing verification.

No archive extraction, arbitrary URLs, settings/status writes or closed-as-open
admission. Missing/expired/ambiguous evidence is a refusal, never a skip grant.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import io
import json
import re
import subprocess
import tempfile
import zipfile

import shadow_scope as policy
import delivery_v13 as v13
from delivery_verify import PendingEvidence, require

REPOSITORY = policy.REPOSITORY
REPOSITORY_ID = 1434660228
CALLER = ".github/workflows/task-set-candidate-shadow.yml"
CALLEES = {".github/workflows/task-set-candidate.yml", ".github/workflows/tests.yml"}
HEAVY = "openrepotools-batch-heavy"
MERGIFY = "mergify[bot]"
TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"
FULL_JOBS = {"guard-launch-mode", "tests", "tests-no-submodule", "package",
             "delivery-route", "openrepotools-delivery"} | {
    f"{name} ({shard})" for name, shards in {
        "tests-shard": ["pytest-1", "pytest-2", "pytest-3", "pytest-4", "shell"],
        "tests-no-submodule-shard": ["pytest-1", "pytest-2", "pytest-3", "shell"]}.items()
    for shard in shards}
CANDIDATE_JOBS = {"probe", "candidate / Verify queue candidate",
                  "candidate / Candidate full-suite qualification", HEAVY} | {
    "candidate / full-ci / " + name for name in FULL_JOBS}
ARCHIVE_LIMIT = 262144
JSON_LIMIT = 32768


def positive(value):
    require(type(value) is int and value > 0, "Invalid numeric identity")
    return value


def unique_object(pairs):
    require(len(pairs) == len(dict(pairs)), "Duplicate JSON key")
    return dict(pairs)


def read_json(data):
    return json.loads(data, object_pairs_hook=unique_object,
                      parse_constant=lambda _value: require(False, "Non-finite JSON"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def run_identity(run, candidate=None, branch=None, completed=False):
    positive(run["id"])
    require(run["repository"]["full_name"] == REPOSITORY
            and run["repository"]["id"] == REPOSITORY_ID
            and run["head_repository"]["full_name"] == REPOSITORY
            and run["head_repository"]["id"] == REPOSITORY_ID
            and run["event"] == "push" and run["path"] == CALLER
            and run["actor"]["login"] == MERGIFY
            and run["triggering_actor"]["login"] == MERGIFY
            and type(run["run_attempt"]) is int and run["run_attempt"] == 1
            and policy.QUEUE.fullmatch(run["head_branch"]) is not None,
            "Run is not an authentic first-attempt candidate caller")
    policy.sha(run["head_sha"])
    require(candidate is None or run["head_sha"] == candidate, "Run candidate differs")
    require(branch is None or run["head_branch"] == branch, "Run branch differs")
    if completed:
        require(run["status"] == "completed" and run["conclusion"] == "success",
                "Candidate run is not successful")
        expected = {f"{REPOSITORY}/{path}@{run['head_sha']}" for path in CALLEES}
        workflows = run["referenced_workflows"]
        require(len(workflows) == 2 and {row["path"] for row in workflows} == expected
                and all(row["sha"] == run["head_sha"]
                        and row["ref"] == "refs/heads/" + run["head_branch"]
                        for row in workflows), "Unexpected immutable workflow reuse")
    else:
        require(run["status"] in {"queued", "in_progress", "completed"}
                and (run["status"] != "completed" or run["conclusion"] == "success"),
                "Candidate run failed or stopped")
    return run


def record_valid(record, run, phase):
    require(set(record) == {"schema_version", "phase", "repository", "repository_id",
                            "run_id", "run_attempt", "branch", "proof"}
            and type(record["schema_version"]) is int and record["schema_version"] == 1
            and record["phase"] == phase and phase in {"admission", "qualified"}
            and record["repository"] == REPOSITORY
            and record["repository_id"] == REPOSITORY_ID
            and positive(record["run_id"]) == run["id"]
            and type(record["run_attempt"]) is int and record["run_attempt"] == 1
            and record["branch"] == run["head_branch"], "Receipt provenance differs")
    proof = record["proof"]
    fields = {"verified", "full_ci_required", "base", "candidate", "tree", "members"}
    scoped = "scope" in proof
    require(set(proof) == fields | ({"scope"} if scoped else set())
            and (not scoped or proof["scope"] == v13.SCOPE)
            and proof["verified"] is True and proof["full_ci_required"] is True
            and proof["candidate"] == run["head_sha"], "Receipt proof differs")
    for key in ("base", "candidate", "tree"):
        policy.sha(proof[key])
    members = proof["members"]
    require(isinstance(members, list) and 1 <= len(members) <= 2, "Invalid member inventory")
    for row in members:
        require(set(row) == {"number", "head", "prefix", "tree", "delivery"}
                and type(row["delivery"]) is bool, "Invalid member schema")
        positive(row["number"])
        for key in ("head", "prefix", "tree"):
            policy.sha(row[key])
    require(len({row["number"] for row in members}) == len(members)
            and len({row["head"] for row in members}) == len(members)
            and members[-1]["prefix"] == proof["candidate"]
            and members[-1]["tree"] == proof["tree"], "Ambiguous final member")
    return record


def make_record(proof, phase, env, request=policy.github):
    require(env["GITHUB_REPOSITORY"] == REPOSITORY
            and env["GITHUB_EVENT_NAME"] == "push", "Unsupported proof writer context")
    run_id = positive(int(env["GITHUB_RUN_ID"]))
    require(env["GITHUB_RUN_ATTEMPT"] == "1", "Rerun cannot publish admission")
    run = run_identity(request(REPOSITORY, f"actions/runs/{run_id}"),
                       policy.sha(env["GITHUB_SHA"]), env["GITHUB_REF"].removeprefix("refs/heads/"))
    record = {"schema_version": 1, "phase": phase, "repository": REPOSITORY,
              "repository_id": REPOSITORY_ID, "run_id": run_id, "run_attempt": 1,
              "branch": run["head_branch"], "proof": proof}
    return record_valid(record, run, phase)


def pages(request, endpoint, field, limit=3):
    """Exhaust all bounded pages; saturation at the cap refuses, not truncates."""
    rows = []
    separator = "&" if "?" in endpoint else "?"
    for page in range(1, limit + 1):
        response = request(REPOSITORY, f"{endpoint}{separator}per_page=100&page={page}")
        values = response[field] if field else response
        require(isinstance(values, list) and len(values) <= 100, "Malformed API page")
        rows.extend(values)
        if len(values) < 100:
            if field and "total_count" in response:
                require(type(response["total_count"]) is int
                        and response["total_count"] == len(rows), "Incomplete API inventory")
            return rows
    require(False, "API inventory exceeds safe bound")


def download(artifact_id):
    # Known GitHub endpoint only; never a URL or command taken from a receipt.
    positive(artifact_id)
    with tempfile.TemporaryFile() as output:
        subprocess.run(["gh", "api", "--hostname", "github.com",
                        f"repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip"],
                       check=True, stdout=output, stderr=subprocess.PIPE, timeout=15)
        require(output.tell() <= ARCHIVE_LIMIT, "Oversized artifact archive")
        output.seek(0)
        return output.read(ARCHIVE_LIMIT + 1)


def artifact_record(run, phase, request=policy.github, fetch=download, *, allow_pending=False):
    run_identity(run)
    name = f"candidate-{phase}-{run['head_sha']}-a1"
    rows = pages(request, f"actions/runs/{run['id']}/artifacts", "artifacts")
    selected = [row for row in rows if row["name"] == name]
    if (allow_pending and phase == "admission" and not selected
            and run["status"] in {"queued", "in_progress"}):
        # This observation grants no artifact proof. Reacquire the authenticated
        # caller and real receipt afresh after the existing bounded wait.
        raise PendingEvidence("Authenticated candidate has not published admission yet")
    require(len(selected) == 1, "Missing or duplicate receipt artifact")
    item = selected[0]
    artifact_id = positive(item["id"])
    require(item["expired"] is False and type(item["size_in_bytes"]) is int
            and 0 < item["size_in_bytes"] <= ARCHIVE_LIMIT
            and item["workflow_run"]["id"] == run["id"]
            and item["workflow_run"]["repository_id"] == REPOSITORY_ID
            and item["workflow_run"]["head_repository_id"] == REPOSITORY_ID
            and item["workflow_run"]["head_sha"] == run["head_sha"],
            "Artifact belongs to another run/repository/head")
    data = fetch(artifact_id)
    require(0 < len(data) <= ARCHIVE_LIMIT
            and item["digest"] == "sha256:" + hashlib.sha256(data).hexdigest(),
            "Artifact archive digest differs")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        require(len(infos) == 1 and infos[0].filename == "proof.json"
                and not infos[0].is_dir() and 0 < infos[0].file_size <= JSON_LIMIT
                and not infos[0].flag_bits & 1, "Unsupported artifact contents")
        record = record_valid(read_json(archive.read(infos[0])), run, phase)
    require(item == request(REPOSITORY, f"actions/artifacts/{artifact_id}"),
            "Artifact changed while reading")
    current = request(REPOSITORY, f"actions/runs/{run['id']}")
    if allow_pending and phase == "admission" and run != current:
        run_identity(current, run["head_sha"], run["head_branch"])
        require(current["id"] == run["id"]
                and (current["status"] == "completed" or current["conclusion"] is None),
                "Admission caller identity/state changed")
        # A moving caller supplies no record. The existing bounded observer
        # must reacquire the real archive and every independent source proof.
        raise PendingEvidence("Authenticated admission caller changed while reading")
    require(run == current, "Artifact/run changed while reading")
    return record


def completed_jobs(run, request=policy.github):
    run_identity(run, completed=True)
    rows = pages(request, f"actions/runs/{run['id']}/attempts/1/jobs", "jobs")
    require(len(rows) == len(CANDIDATE_JOBS)
            and {row["name"] for row in rows} == CANDIDATE_JOBS
            and len({positive(row["id"]) for row in rows}) == len(rows),
            "Candidate job inventory differs")
    for row in rows:
        require(row["run_id"] == run["id"] and row["run_attempt"] == 1
                and row["head_sha"] == run["head_sha"]
                and row["status"] == "completed" and row["conclusion"] == "success",
                "Candidate job did not complete successfully")
        datetime.strptime(row["completed_at"], TIMESTAMP)
    return max(row["completed_at"] for row in rows)


def ensure_commit(root, value):
    """Acquire a validated immutable public object, never its checkout or refs."""
    commit = policy.sha(value)
    try:
        policy.git(root, "cat-file", "-e", commit + "^{commit}")
    except subprocess.CalledProcessError:
        policy.git(root, "-c", "credential.helper=", "-c", "credential.interactive=false",
                   "-c", "fetch.recurseSubmodules=false", "fetch", "--no-tags",
                   "--no-write-fetch-head", "https://github.com/" + REPOSITORY + ".git", commit)
    policy.git(root, "cat-file", "-e", commit + "^{commit}")
    return commit


def candidate_chain(record, root):
    proof = record["proof"]
    is_v13 = proof.get("scope") == v13.SCOPE
    # Queue branches may already be deleted at main-push time.
    ensure_commit(root, proof["candidate"])
    previous, heads = proof["base"], []
    for row in proof["members"]:
        head, prefix = row["head"], row["prefix"]
        require(row["delivery"] is True, "Member did not opt into delivery")
        if is_v13:
            projection, _cut, _profile = v13.cut(root, proof["base"], head)
            anchor = projection["prerequisite"]["head"]
        else:
            anchor = proof["base"]
            policy.git(root, "merge-base", "--is-ancestor", anchor, head)
        for other in heads:
            require(policy.git(root, "merge-base", "--all", other, head).decode().split()
                    == [anchor], "Member histories are not independent")
        heads.append(head)
        scoped = (v13.prefix(root, proof["base"], head, previous, prefix) if is_v13 else
                  policy.regular_scope(root, proof["base"], head)
                  and policy.regular_scope(root, previous, prefix))
        require(policy.git(root, "show", "-s", "--format=%P", prefix).decode().split()
                == [previous, head] and scoped, "Candidate chain differs")
        tree = policy.git(root, "rev-parse", prefix + "^{tree}").decode().strip()
        require(tree == row["tree"] == policy.git(
            root, "merge-tree", "--write-tree", previous, head).decode().strip(),
            "Candidate prefix tree differs")
        previous = prefix
    return proof


def candidate_runs(candidate, request):
    policy.sha(candidate)
    rows = pages(request, f"actions/workflows/task-set-candidate-shadow.yml/runs?head_sha={candidate}",
                 "workflow_runs", limit=1)
    matching = [row for row in rows if row["head_sha"] == candidate and row["event"] == "push"]
    require(len(matching) == 1, "No unique candidate caller")
    run = request(REPOSITORY, f"actions/runs/{positive(matching[0]['id'])}")
    return run_identity(run, candidate)


def landing(record, run, env, event, root, request=policy.github):
    """Closed records are historical proof, never open candidate admission."""
    require(env["GITHUB_EVENT_NAME"] == "push" and env["GITHUB_REF"] == "refs/heads/main"
            and env["GITHUB_ACTOR"] == MERGIFY
            and event["sender"]["login"] == MERGIFY
            and event["repository"]["full_name"] == REPOSITORY
            and event["ref"] == env["GITHUB_REF"] and event["forced"] is False
            and event["deleted"] is False, "Not an authentic main landing event")
    after = policy.sha(event["after"])
    require(after == policy.sha(env["GITHUB_SHA"]), "Main event identity differs")
    main = policy.sha(policy.git(root, "rev-parse", "HEAD").decode().strip())
    require(request(REPOSITORY, "git/ref/heads/main")["object"]["sha"] == main,
            "Trusted main moved")
    policy.git(root, "merge-base", "--is-ancestor", after, main)
    proof = candidate_chain(record_valid(record, run, "qualified"), root)
    if proof.get("scope") == v13.SCOPE:
        stable = v13.unchanged_policy(root, proof["base"], main)
    else:
        changed = policy.git(root, "diff", "--name-only", proof["base"], main, "--").decode().splitlines()
        stable = all(path in policy.SCOPE for path in changed)
    require(stable, "Policy/commands changed since qualification")
    finished = completed_jobs(run, request)
    # Reconstruct the prefix ending at this event, not any lookalike final tree.
    chain, current = [], after
    for _ in range(2):
        if current == proof["base"]:
            break
        pair = policy.git(root, "show", "-s", "--format=%P", current).decode().split()
        require(len(pair) == 2, "Landing is not a bounded merge prefix")
        chain.append((current, pair))
        current = pair[0]
    require(current == proof["base"] and 1 <= len(chain) <= len(proof["members"]),
            "Landing has another root/member count")
    require(policy.sha(event["before"]) == chain[0][1][0], "Main event did not land one prefix")
    snapshots = []
    for (commit, pair), member in zip(reversed(chain), proof["members"]):
        pr = request(REPOSITORY, f"pulls/{member['number']}")
        require(pair[1] == member["head"]
                and policy.git(root, "rev-parse", commit + "^{tree}").decode().strip() == member["tree"]
                and pr["number"] == member["number"] and pr["state"] == "closed"
                and pr["merged"] is True and pr["merge_commit_sha"] == commit
                and policy.side(pr, "head")[0] == member["head"]
                and policy.side(pr, "base")[1] == "main"
                and datetime.strptime(pr["merged_at"], TIMESTAMP)
                >= datetime.strptime(finished, TIMESTAMP),
                "Landed source/merge record differs from completed qualification")
        snapshots.append(pr)
    require(all(pr == request(REPOSITORY, f"pulls/{pr['number']}") for pr in snapshots)
            and run == request(REPOSITORY, f"actions/runs/{run['id']}")
            and request(REPOSITORY, "git/ref/heads/main")["object"]["sha"] == main,
            "Historical provenance changed")
    return {"candidate": proof["candidate"], "after": after, "record": digest(record)}
