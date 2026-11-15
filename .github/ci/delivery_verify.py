# SPDX-License-Identifier: Apache-2.0
"""Additive delivery proof; no queue, status, ruleset or release writes.

Candidate mode runs only from trusted main. Git merge-tree may create private
immutable objects in that disposable checkout; it changes no ref/index/worktree.
Successful verification still requires the entire heavy suite and a final recheck.
"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import shadow_scope as policy
import delivery_v13 as v13

REPOSITORY = policy.REPOSITORY
FAST = "openrepotools-pr-fast"
FAST_WORKFLOW = ".github/workflows/task-set-fast.yml"
LOCAL_REVIEW = "<!-- openrepotools-local-review:"
LOCAL_FIELDS = {"schema_version", "repository", "pull_request", "head_sha", "base_sha",
                "reviewer", "skill", "status", "unresolved_findings", "findings",
                "resolution", "validation"}
LOCAL_SKILLS = {"pre-pr-review", "pr-review", "branch-or-pr-review"}


def delivery_intended(text):
    if v13.intended(text):
        return True
    if not policy.intended(text):
        return False
    lines = re.findall(r"(?m)^CI-Delivery:[^\n]*", text)
    return [line.rstrip(" \t\r") for line in lines] == ["CI-Delivery: claude-current"]


class Refused(ValueError):
    """A fixed-vocabulary refusal safe to expose in the CI log."""


class PendingEvidence(Refused):
    """Authenticated work is still running; waiting grants no CI omission."""


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def read_threads(number):
    require(type(number) is int and number > 0, "Invalid PR identity")
    query = ('query { repository(owner:"opensoft",name:"openRepoTools-code") { '
             f'pullRequest(number:{number}) {{ reviewThreads(first:100) {{ '
             'pageInfo { hasNextPage } nodes { isResolved } } '
             'comments(first:100) { pageInfo { hasNextPage } '
             'nodes { databaseId lastEditedAt body } } } } }')
    data = subprocess.run(["gh", "api", "--hostname", "github.com", "graphql",
                           "-f", "query=" + query], check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=15).stdout
    result = json.loads(data)["data"]["repository"]["pullRequest"]
    return dict(result["reviewThreads"], comments=result["comments"])


def read_base_changes(number):
    require(type(number) is int and number > 0, "Invalid PR identity")
    query = ('query { repository(owner:"opensoft",name:"openRepoTools-code") { '
             f'pullRequest(number:{number}) {{ timelineItems(first:100, '
             'itemTypes:[BASE_REF_CHANGED_EVENT]) { pageInfo { hasNextPage } '
             'nodes { ... on BaseRefChangedEvent { createdAt } } } } } }')
    data = subprocess.run(["gh", "api", "--hostname", "github.com", "graphql",
                           "-f", "query=" + query], check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=15).stdout
    return json.loads(data)["data"]["repository"]["pullRequest"]["timelineItems"]


def local_object(pairs):
    require(len(pairs) == len(dict(pairs)), "Duplicate local review key")
    return dict(pairs)


def local_writer(comment, request, permissions):
    user = comment["user"]
    if user["type"] != "User":
        return None
    login, identity = user["login"], user["id"]
    require(isinstance(login, str) and re.fullmatch(
        r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", login, flags=re.ASCII)
        and type(identity) is int and identity > 0, "Invalid local review author")
    if login not in permissions:
        permissions[login] = request(REPOSITORY, f"collaborators/{login}/permission")
    permission = permissions[login]
    current = permission["user"]
    require(current["login"] == login and type(current["id"]) is int
            and current["id"] == identity and current["type"] == "User"
            and permission["permission"] in {"none", "read", "write", "admin"},
            "Local review author permission identity differs")
    return permission["permission"] if permission["permission"] in {"write", "admin"} else None


def consistent_comments(comments, response):
    # Reconcile before choosing local OR hosted review: otherwise a newly added
    # local revocation can be hidden by the hosted-fallback path.
    edits = response["comments"]
    nodes = edits["nodes"]
    require(edits["pageInfo"]["hasNextPage"] is False and isinstance(nodes, list)
            and len(nodes) == len(comments) < 100
            and all(type(row["databaseId"]) is int and row["databaseId"] > 0 for row in nodes)
            and all(type(row["id"]) is int and row["id"] > 0 for row in comments)
            and len({row["databaseId"] for row in nodes}) == len(nodes)
            and {row["databaseId"]: row["body"] for row in nodes}
                == {row["id"]: row["body"] for row in comments},
            "Incomplete or inconsistent review comment history")


def local_review(comments, number, head, base, request, response):
    candidates = [row for row in comments if LOCAL_REVIEW in row["body"]]
    require(len(candidates) <= 10, "Local review history exceeds bound")
    authorized = []
    identities = set()
    permissions = {}
    for comment in candidates:
        permission = local_writer(comment, request, permissions)
        if permission is None:
            continue
        identity, created = comment["id"], comment["created_at"]
        require(type(identity) is int and identity > 0 and identity not in identities,
                "Invalid or duplicate local comment identity")
        identities.add(identity)
        datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ")
        authorized.append((created, identity, comment, permission))
    if not authorized:
        return None
    policy.sha(head)
    policy.sha(base)
    created, identity, comment, permission = max(authorized, key=lambda row: row[:2])
    nodes = response["comments"]["nodes"]
    selected = [row for row in nodes if row["databaseId"] == identity]
    require(len(selected) == 1 and selected[0]["lastEditedAt"] is None,
            "Local review comment has been edited")
    text = comment["body"]
    require(comment["updated_at"] == created
            and comment["issue_url"] == f"https://api.github.com/repos/{REPOSITORY}/issues/{number}"
            and comment["html_url"] == f"https://github.com/{REPOSITORY}/pull/{number}#issuecomment-{identity}"
            and len(text.encode("utf-8")) <= 16384, "Local review comment is edited or misplaced")
    match = re.fullmatch(r"<!-- openrepotools-local-review:v1 -->\n```json\n(.+)\n```\n?",
                         text, flags=re.DOTALL)
    require(match is not None, "Malformed local review envelope")
    record = json.loads(match[1], object_pairs_hook=local_object,
                        parse_constant=lambda _value: require(False, "Non-finite local JSON"))
    require(isinstance(record, dict) and set(record) == LOCAL_FIELDS,
            "Invalid local review schema")
    require(type(record["schema_version"]) is int and record["schema_version"] == 1
            and record["repository"] == REPOSITORY
            and type(record["pull_request"]) is int and record["pull_request"] == number
            and record["head_sha"] == head and record["base_sha"] == base
            and record["reviewer"] == "codex-local" and record["skill"] in LOCAL_SKILLS
            and record["status"] == "accepted"
            and type(record["unresolved_findings"]) is int and record["unresolved_findings"] == 0,
            "Local review is not accepted for this head/base")
    require(all(isinstance(record[key], str) and record[key].strip() and len(record[key]) <= 4000
                for key in ("findings", "resolution", "validation")),
            "Local review report is incomplete")
    return {"kind": "local-codex-review", "comment_id": identity,
            "author_id": comment["user"]["id"], "author_login": comment["user"]["login"],
            "created_at": created, "permission": permission,
            "body_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def hosted_review(comments, head):
    receipts = []
    for comment in comments:
        user = comment["user"]
        if user["login"] != "chatgpt-codex-connector[bot]" or user["type"] != "Bot":
            continue
        if "<!-- codex-pull-request-review-summary -->" not in comment["body"]:
            continue
        matches = re.findall(r"<!-- codex-review-state:v1 (.+?) -->", comment["body"])
        if matches:
            require(len(matches) == 1, "Ambiguous Codex summary")
            receipts.append((comment["updated_at"], json.loads(matches[0])["code_review"]))
    require(bool(receipts), "No completed Codex summary")
    review = max(receipts, key=lambda entry: entry[0])[1]
    require(review["commit_sha"] == head and review["status"] == "completed"
            and review["has_any_findings"] is False
            and review["has_unresolved_findings"] is False, "Codex head is not clean")
    return max(receipts, key=lambda entry: entry[0])


def clean_review(number, head, request, threads, *, base=None):
    comments = request(REPOSITORY, f"issues/{number}/comments?per_page=100")
    require(isinstance(comments, list) and len(comments) < 100,
            "Incomplete review comments")
    response = threads(number)
    consistent_comments(comments, response)
    receipt = local_review(comments, number, head, base, request, response)
    if receipt is None:
        receipt = hosted_review(comments, head)
    response = {"pageInfo": response["pageInfo"], "nodes": response["nodes"]}
    require(response["pageInfo"]["hasNextPage"] is False
            and isinstance(response["nodes"], list) and len(response["nodes"]) <= 100
            and all(row["isResolved"] is True for row in response["nodes"]),
            "Unresolved or incomplete review threads")
    return receipt, response


def receipt_pending(value, allow_pending):
    pending = value["status"] in {"queued", "in_progress"} and value["conclusion"] is None
    require((value["status"] == "completed" and value["conclusion"] == "success")
            or (allow_pending and pending), "Fast evidence is not successful or authenticated pending work")
    return pending


def fast_run_scope(run, pr, head):
    return (run["event"] == "pull_request" and run["path"] == FAST_WORKFLOW
            and run["head_sha"] == head and run["head_branch"] == pr["head"]["ref"]
            and run["head_repository"]["full_name"] == REPOSITORY
            and type(run["run_attempt"]) is int and run["run_attempt"] >= 1)


def same_fast_attempt(run, observed):
    return all(type(run[key]) is int and run[key] == observed[key]
               for key in ("id", "run_number", "workflow_id", "check_suite_id", "run_attempt"))


def fast_runs(pr, head, request):
    """A complete, bounded catalogue; workflow sequence is not check array order."""
    path = ("actions/workflows/task-set-fast.yml/runs?head_sha=" + policy.sha(head)
            + "&event=pull_request&per_page=100&page=1")
    response = request(REPOSITORY, path)
    rows = response["workflow_runs"]
    require(isinstance(rows, list) and type(response["total_count"]) is int
            and response["total_count"] == len(rows) and 0 < len(rows) <= 100,
            "Missing or ambiguous fast check")
    for row in rows:
        require(fast_run_scope(row, pr, head)
                and all(type(row[key]) is int and row[key] > 0
                        for key in ("id", "run_number", "workflow_id", "check_suite_id")),
                "Fast run belongs to another workflow/head or is incomplete")
    require(len({row["id"] for row in rows}) == len(rows)
            and len({row["run_number"] for row in rows}) == len(rows)
            and len({row["workflow_id"] for row in rows}) == 1,
            "Missing or ambiguous fast check")
    # GitHub's per-workflow run_number is increasing and unchanged on rerun.
    return {row["id"]: row for row in rows}, max(rows, key=lambda row: row["run_number"])


def fast_receipt(pr, head, request, base_changes, *, allow_pending=False):
    endpoint = f"commits/{head}/check-runs?check_name={FAST}&filter=latest&per_page=100"
    response = request(REPOSITORY, endpoint)
    checks = response["check_runs"]
    require(isinstance(checks, list) and type(response["total_count"]) is int
            and response["total_count"] == len(checks) and len(checks) <= 100,
            "Missing or ambiguous fast check")
    catalog, latest = fast_runs(pr, head, request)
    matches, seen = [], set()
    for check in checks:
        require(check["name"] == FAST and check["head_sha"] == head
                and check["app"]["slug"] == "github-actions",
                "Fast check is not successful exact-head Actions evidence")
        link = re.fullmatch(
            r"https://github[.]com/opensoft/openRepoTools-code/actions/runs/([1-9]\d*)/job/([1-9]\d*)",
            check["details_url"], flags=re.ASCII)
        require(link is not None, "Unrecognized fast workflow identity")
        run_id, job_id = (int(value) for value in link.groups())
        require(type(check["id"]) is int and check["id"] == job_id, "Fast job identity differs")
        require(run_id in catalog and run_id not in seen
                and check["check_suite"]["id"] == catalog[run_id]["check_suite_id"],
                "Missing or ambiguous fast check")
        seen.add(run_id)
        if run_id == latest["id"]:
            matches.append((check, job_id))
    run_id = latest["id"]
    run = request(REPOSITORY, f"actions/runs/{run_id}")
    require(fast_run_scope(run, pr, head) and same_fast_attempt(run, latest),
            "Fast run belongs to another workflow/head or is incomplete")
    pending = receipt_pending(latest, allow_pending)
    pending = receipt_pending(run, allow_pending) or pending
    associated = run["pull_requests"]
    require(isinstance(associated, list) and len(associated) == 1,
            "Fast run has no unique source PR")
    source = associated[0]
    api = "https://api.github.com/repos/" + REPOSITORY
    require(type(source["number"]) is int and source["number"] == pr["number"]
            and source["url"] == f"{api}/pulls/{pr['number']}"
            and source["head"]["sha"] == head
            and source["head"]["ref"] == pr["head"]["ref"]
            and source["head"]["repo"]["url"] == api
            and source["base"]["ref"] == "main"
            and source["base"]["sha"] == pr["base"]["sha"]
            and source["base"]["repo"]["url"] == api,
            "Fast run source association differs")
    history = base_changes(pr["number"])
    require(history["pageInfo"]["hasNextPage"] is False
            and isinstance(history["nodes"], list) and len(history["nodes"]) <= 100,
            "Incomplete base-change history")
    # Run PR associations are mutable. Its immutable creation time plus complete
    # retarget history proves the current base was already selected for this run.
    created = datetime.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    require(all(datetime.strptime(row["createdAt"], "%Y-%m-%dT%H:%M:%SZ") < created
                for row in history["nodes"]), "Fast run predates a base change")
    require(len(matches) == 1, "Missing or ambiguous fast check")
    check, job_id = matches[0]
    pending = receipt_pending(check, allow_pending) or pending
    job = request(REPOSITORY, f"actions/jobs/{job_id}")
    require(type(job["id"]) is int and job["id"] == job_id
            and type(job["run_id"]) is int and job["run_id"] == run_id and job["head_sha"] == head
            and job["run_attempt"] == run["run_attempt"] and job["name"] == FAST,
            "Fast job does not match the current successful run")
    pending = receipt_pending(job, allow_pending) or pending
    # Pending observations grant no proof. Re-poll all evidence afresh, allowing
    # work to finish during these reads without accepting a mixed-state proof.
    if pending:
        raise PendingEvidence("Authenticated fast workflow is pending")
    require(run == request(REPOSITORY, f"actions/runs/{run_id}")
            and response == request(REPOSITORY, endpoint),
            "Fast run/check changed during verification")
    final = fast_runs(pr, head, request)[1]
    require(same_fast_attempt(run, final)
            and final["status"] == run["status"] and final["conclusion"] == run["conclusion"],
            "Fast run/check changed during verification")
    return response, run, job, history


def source_pr(head, main, root, request, threads, base_changes):
    associated = request(REPOSITORY, f"commits/{head}/pulls?per_page=100")
    require(isinstance(associated, list) and len(associated) < 100,
            "Incomplete source PR discovery")
    candidates = [pr for pr in associated if pr["state"] == "open"
                  and pr["head"]["sha"] == head
                  and pr["head"]["repo"]["full_name"] == REPOSITORY]
    require(len(candidates) == 1, "Source head has no unique open PR")
    number = candidates[0]["number"]
    require(type(number) is int and number > 0, "Invalid member number")
    pr = request(REPOSITORY, f"pulls/{number}")
    require(pr["number"] == number and pr["state"] == "open" and pr["draft"] is False,
            "Member is not open and ready")
    actual_head, branch = policy.side(pr, "head")
    base, base_ref = policy.side(pr, "base")
    is_v13 = v13.intended(pr.get("body"))
    require(actual_head == head and policy.source_branch(branch) and base_ref == "main"
            and base == main and (is_v13 or policy.intended(pr["body"]))
            and not re.search(r"(?m)^Depends-On:", pr["body"]),
            "Member scope/identity/topology is not the independent pilot")
    if is_v13:
        v13.source(root, main, pr, request)
    else:
        policy.git(root, "merge-base", "--is-ancestor", main, head)
        require(policy.regular_scope(root, main, head), "Member changes unsupported paths or modes")
    evidence = (fast_receipt(pr, head, request, base_changes),
                clean_review(number, head, request, threads, base=base))
    return pr, evidence


def verify_fast(env, event, root):
    require(env["GITHUB_REPOSITORY"] == REPOSITORY
            and env["GITHUB_EVENT_NAME"] == "pull_request"
            and event["action"] in {"opened", "synchronize", "reopened"},
            "Unsupported fast source event")
    tested = policy.sha(env["GITHUB_SHA"])
    require(policy.git(root, "rev-parse", "HEAD").decode().strip() == tested,
            "Fast checkout differs from the event")
    pr = event["pull_request"]
    base, head = policy.sha(pr["base"]["sha"]), policy.sha(pr["head"]["sha"])
    pair = policy.git(root, "show", "-s", "--format=%P", tested).decode().split()
    require(pair == [base, head], "Fast test-merge parents differ from event identities")
    policy.git(root, "diff", "--check", base, tested, "--")
    paths = policy.git(root, "diff", "--name-only", "--diff-filter=AM", "-z", base, tested, "--")
    for path in paths.decode("utf-8").split("\0"):
        if re.fullmatch(r"tests/test_sql_register_[a-z_]+[.]py", path):
            # Parse immutable test-merge blobs, never import/execute a SQL test
            # or follow a worktree path. Required-engine execution stays heavy.
            ast.parse(policy.git(root, "show", f"{tested}:{path}"), filename=path)
    return {"tested": tested, "base": base, "head": head, "full_ci_required": True}


def verify_candidate(env, event, root, request=policy.github, threads=read_threads,
                     base_changes=read_base_changes):
    require(env["GITHUB_REPOSITORY"] == REPOSITORY and env["GITHUB_EVENT_NAME"] == "push"
            and env["GITHUB_ACTOR"] == "mergify[bot]"
            and event["sender"]["login"] == "mergify[bot]"
            and event["repository"]["full_name"] == REPOSITORY
            and event["deleted"] is False and event["forced"] is False,
            "Not a genuine supported queue push")
    ref, candidate = env["GITHUB_REF"], policy.sha(env["GITHUB_SHA"])
    require(isinstance(ref, str) and ref.startswith("refs/heads/"),
            "Unrecognized candidate ref")
    branch = ref[len("refs/heads/"):]
    require(policy.QUEUE.fullmatch(branch) is not None and event["ref"] == ref
            and policy.sha(event["after"]) == candidate, "Candidate event/ref mismatch")
    main = policy.sha(policy.git(root, "rev-parse", "HEAD").decode().strip())
    require(policy.sha(request(REPOSITORY, "git/ref/heads/main")["object"]["sha"]) == main,
            "Trusted main moved")
    endpoint = "git/ref/heads/" + branch
    require(policy.sha(request(REPOSITORY, endpoint)["object"]["sha"]) == candidate,
            "Queue ref changed")
    chain, current = [], candidate
    for _ in range(2):
        if current == main:
            break
        pair = policy.git(root, "show", "-s", "--format=%P", current).decode().split()
        require(len(pair) == 2, "Candidate is not a bounded merge chain")
        previous, head = (policy.sha(value) for value in pair)
        chain.append((previous, head, current))
        current = previous
    require(current == main and 1 <= len(chain) <= 2, "Candidate is not rooted at current main")
    members, snapshots, seen_heads, scope = [], [], set(), None
    for previous, head, prefix in reversed(chain):
        require(head not in seen_heads, "Duplicate source head")
        pr, evidence = source_pr(head, main, root, request, threads, base_changes)
        member_scope = v13.SCOPE if v13.intended(pr.get("body")) else "claude-current"
        require(scope is None or scope == member_scope, "Candidate mixes delivery scopes")
        scope = member_scope
        anchor = v13.configuration(root, main)["prerequisite"]["head"] if scope == v13.SCOPE else main
        for other in seen_heads:
            require(policy.git(root, "merge-base", "--all", other, head).decode().split() == [anchor],
                    "Source members share non-main history")
        seen_heads.add(head)
        require(pr["number"] not in [row["number"] for row in members], "Duplicate source member")
        expected = policy.sha(policy.git(
            root, "merge-tree", "--write-tree", previous, head).decode().strip())
        tree = policy.sha(policy.git(root, "rev-parse", prefix + "^{tree}").decode().strip())
        scoped = (v13.prefix(root, main, head, previous, prefix) if scope == v13.SCOPE
                  else policy.regular_scope(root, previous, prefix))
        require(expected == tree and scoped,
                "Candidate prefix is not the expected clean scoped merge")
        members.append({"number": pr["number"], "head": head, "prefix": prefix, "tree": tree,
                        "delivery": delivery_intended(pr["body"])})
        snapshots.append((pr, evidence))
    for pr, evidence in snapshots:
        require(policy.snapshot(pr) == policy.snapshot(
            request(REPOSITORY, f"pulls/{pr['number']}")), "Source changed during verification")
        if scope == v13.SCOPE:
            v13.source(root, main, pr, request)
        require(evidence == (fast_receipt(pr, pr["head"]["sha"], request, base_changes),
                             clean_review(pr["number"], pr["head"]["sha"], request, threads,
                                          base=pr["base"]["sha"])),
                "Source evidence changed during verification")
        require(policy.snapshot(pr) == policy.snapshot(
            request(REPOSITORY, f"pulls/{pr['number']}")), "Source changed during evidence recheck")
    require(policy.sha(request(REPOSITORY, endpoint)["object"]["sha"]) == candidate
            and policy.sha(request(REPOSITORY, "git/ref/heads/main")["object"]["sha"]) == main,
            "Candidate/main changed during verification")
    if scope != v13.SCOPE:
        require(policy.regular_scope(root, main, candidate), "Combined candidate is outside scope")
    return {"verified": True, "full_ci_required": True, "base": main, "candidate": candidate,
            "tree": members[-1]["tree"], "members": members,
            **({"scope": v13.SCOPE} if scope == v13.SCOPE else {})}


def write_record(record, env):
    # The CLI cannot select a destination. Only the Actions-owned canonical
    # temp directory is accepted; exclusive creation refuses files/symlinks.
    directory = Path(env["RUNNER_TEMP"])
    require(directory.is_absolute() and directory.is_dir()
            and directory.resolve(strict=True) == directory and not directory.is_symlink(),
            "Proof directory is not a canonical runner temporary directory")
    data = json.dumps(record, sort_keys=True) + "\n"
    require(len(data.encode("utf-8")) <= 32768, "Proof record is oversized")
    with (directory / "proof.json").open("x", encoding="utf-8") as output:
        output.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("fast", "candidate"))
    parser.add_argument("--proof-kind", choices=("admission", "qualified"))
    parser.add_argument("--require-delivery", action="store_true")
    args = parser.parse_args()
    mode = args.mode
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        result = (verify_fast(os.environ, event, Path.cwd()) if mode == "fast"
                  else verify_candidate(os.environ, event, Path(__file__).resolve().parents[2]))
        if args.require_delivery:
            require(mode == "candidate" and all(row["delivery"] is True for row in result["members"]),
                    "Member delivery intent is missing")
        if args.proof_kind:
            require(mode == "candidate", "Proof output requires a candidate phase")
            # Imported lazily to keep the existing standalone fast CLI unchanged.
            from delivery_evidence import make_record
            record = make_record(result, args.proof_kind, os.environ)
            write_record(record, os.environ)
    except Refused as error:
        parser.exit(1, f"Delivery verification refused: {error}.\n")
    except policy.ERRORS:
        parser.exit(1, "Delivery verification refused: incomplete, stale or unsupported evidence.\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
