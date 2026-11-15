# SPDX-License-Identifier: Apache-2.0
"""Disabled v1.3 observations, never CI omission, admission or qualification."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

import shadow_scope as common

CONFIG = ".github/ci/v13-shadow-profiles.json"
BASELINE = ".github/ci/full-ci-baseline.json"
MARKERS = "tests/sql_register_landed/"
CONTROL_PATHS = {".github/workflows/tests.yml", BASELINE}
P01_TASKS = ("T200", "T201", "T203", "T205", "T206", "T207", "T280")
P01_FILES = ("tests/conftest.py", "tests/pgcluster.py",
             "tests/sql_register_gate.py", "tests/sql_register_helpers.py")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate policy key")
        result[key] = value
    return result


def read_policy(root, main):
    policy = json.loads(common.git(root, "show", f"{main}:{CONFIG}"),
                        object_pairs_hook=unique_pairs)
    if (type(policy["schema_version"]) is not int or policy["schema_version"] != 1
            or policy["efficiency_enabled"] is not False
            or policy["scope"] != "sql-register-v13"):
        raise ValueError("Not an explicitly disabled shadow policy")
    common.sha(policy["spec_revision"])
    prerequisite = policy["prerequisite"]
    if type(prerequisite["number"]) is not int or prerequisite["number"] != 88:
        raise ValueError("Unexpected prerequisite")
    common.sha(prerequisite["head"])
    if set(prerequisite["blobs"]) != CONTROL_PATHS:
        raise ValueError("Unexpected prerequisite control inventory")
    for blob in prerequisite["blobs"].values():
        common.sha(blob)
    if "foundation" in policy:
        epoch = policy["foundation"]
        if (not isinstance(epoch, dict) or set(epoch) != {"head", "blobs"}
                or not isinstance(epoch["blobs"], dict) or set(epoch["blobs"]) != set(P01_FILES)):
            raise ValueError("Invalid foundation epoch")
        common.sha(epoch["head"])
        for blob in epoch["blobs"].values():
            common.sha(blob)
    if set(policy["profiles"]) not in ({"P03", "P05"}, {"P05", "P06"}):
        raise ValueError("Unexpected proposed cuts")
    for profile in policy["profiles"].values():
        source = profile["source"]
        if (set(source) not in ({"number", "head", "branch"}, {"number", "head", "branch", "commits"})
                or type(source["number"]) is not int or source["number"] < 1
                or source["number"] == prerequisite["number"]
                or not common.valid_branch(source["branch"])
                or not common.source_branch(source["branch"])):
            raise ValueError("Invalid source binding")
        common.sha(source["head"])
        commits = source.get("commits", [source["head"]])
        if (not isinstance(commits, list) or not 1 <= len(commits) <= 3
                or any(not isinstance(commit, str) for commit in commits)
                or len(set(commits)) != len(commits) or commits[-1] != source["head"]):
            raise ValueError("Invalid source lineage")
        for commit in commits:
            common.sha(commit)
        for key, pattern in (("tasks", r"T[0-9]{3}"),
                             ("files", r"tests/test_sql_register_[a-z_]+[.]py")):
            values = profile[key]
            if (not isinstance(values, list) or not values
                    or any(not isinstance(value, str) or not re.fullmatch(pattern, value)
                           for value in values) or len(set(values)) != len(values)):
                raise ValueError("Invalid profile projection")
        if len(profile["files"]) + len(profile["tasks"]) > 6:
            raise ValueError("Test-only profile exceeds the staged file bound")
    if any(len({profile["source"][key] for profile in policy["profiles"].values()}) != 2
           for key in ("number", "head", "branch")):
        raise ValueError("Duplicate source binding")
    return policy


def proposed_cut(text, policy):
    if not isinstance(text, str):
        return None
    if [line.rstrip(" \t\r") for line in re.findall(r"(?m)^CI-Shadow:[^\n]*", text)] != [
            "CI-Shadow: sql-register-v13"]:
        return None
    lines = [line.rstrip(" \t\r") for line in re.findall(r"(?m)^CI-Task-Set:[^\n]*", text)]
    return next((cut for cut in policy["profiles"]
                 if lines == ["CI-Task-Set: " + cut]), None)


def scoped_diff(root, base, head, profile):
    fields = common.git(root, "diff", "--raw", "--no-abbrev", "--no-renames",
                        "-z", base, head, "--").split(b"\0")
    if fields[-1] != b"" or len(fields) < 3 or len(fields) % 2 != 1:
        return False
    expected = {MARKERS + task for task in profile["tasks"]}
    markers, files, seen = set(), set(), set()
    for header, raw_path in zip(fields[:-1:2], fields[1:-1:2]):
        if not header.startswith(b":"):
            return False
        old, new, _before, _after, status = header[1:].decode("ascii").split()
        path = raw_path.decode("utf-8")
        if path in seen or new != "100644":
            return False
        seen.add(path)
        if path in expected:
            if (status != "A" or old != "000000"
                    or common.git(root, "show", f"{head}:{path}") != b""):
                return False
            markers.add(path)
        elif path in profile["files"]:
            if (status, old) not in {("A", "000000"), ("M", "100644")}:
                return False
            files.add(path)
        else:
            return False
    return markers == expected and bool(files)


def p01_status(root, main, policy, pr):
    prerequisite = policy["prerequisite"]
    if (type(pr["number"]) is not int or pr["number"] != 88
            or common.side(pr, "base")[1] != "main"
            or common.side(pr, "head")[0] != prerequisite["head"]):
        return "anchor-drift"
    if pr["state"] == "open" and pr["merged"] is False:
        return "pending"
    if pr["state"] != "closed" or pr["merged"] is not True or pr["draft"] is not False:
        return "not-merged"
    common.git(root, "merge-base", "--is-ancestor", common.sha(pr["merge_commit_sha"]), main)
    common.git(root, "merge-base", "--is-ancestor", prerequisite["head"], main)
    for path, blob in prerequisite["blobs"].items():
        if common.git(root, "rev-parse", f"{main}:{path}").decode().strip() != blob:
            return "contract-drift"
    baseline = json.loads(common.git(root, "show", f"{main}:{BASELINE}"))
    if (baseline["environment"].get("OPENREPOTOOLS_REQUIRE_PG") != "1"
            or baseline["expanded_jobs"] != 13):
        return "contract-drift"
    for path in P01_FILES:
        common.git(root, "cat-file", "-e", f"{main}:{path}")
    for task in P01_TASKS:
        if common.git(root, "show", f"{main}:{MARKERS}{task}") != b"":
            return "contract-drift"
    try:
        require_foundation(root, main, policy)
    except (ValueError, subprocess.SubprocessError):
        return "contract-drift"
    return "merged-contract-observed"


def require_foundation(root, main, policy):
    """Verify an explicit immutable epoch, never discover one from moving main."""
    parent = policy["prerequisite"]["head"]
    epoch = policy.get("foundation")
    anchor = epoch["head"] if epoch is not None else parent
    if anchor != parent:
        common.git(root, "merge-base", "--is-ancestor", parent, anchor)
    common.git(root, "merge-base", "--is-ancestor", anchor, main)
    controls = list(policy["prerequisite"]["blobs"]) + [MARKERS + task for task in P01_TASKS]
    if epoch is None:
        common.git(root, "diff", "--quiet", "--no-ext-diff", parent, main,
                   "--", *controls, *P01_FILES)
        return
    expected = {f"100644 blob {blob}\t{path}" for path, blob in epoch["blobs"].items()}
    found = common.git(root, "ls-tree", anchor, "--", *P01_FILES).decode().splitlines()
    if set(found) != expected:
        raise ValueError("Foundation epoch tree differs")
    common.git(root, "diff", "--quiet", "--no-ext-diff", parent, main, "--", *controls)
    common.git(root, "diff", "--quiet", "--no-ext-diff", anchor, main, "--", *P01_FILES)


def source_lineage(root, parent, profile):
    """Only the trusted, bounded exact history; check every cumulative cut."""
    previous = parent
    for commit in profile["source"].get("commits", [profile["source"]["head"]]):
        if (common.git(root, "show", "-s", "--format=%P", commit).decode().split() != [previous]
                or not scoped_diff(root, parent, commit, profile)):
            return False
        previous = commit
    return True


def known_child(root, main, policy, cut, pr, prerequisite):
    """One immutable P01 cut only; this is not a merge or qualification proof."""
    profile = policy["profiles"][cut]
    source = profile["source"]
    if (type(pr["number"]) is not int or pr["number"] != source["number"]
            or common.side(pr, "head") != (source["head"], source["branch"])
            or pr["state"] != "open" or pr["draft"] is not False):
        return False
    parent, parent_ref = common.side(prerequisite, "head")
    base = common.side(pr, "base")
    if base not in {(parent, parent_ref), (main, "main")}:
        return False
    dependencies = [line.strip(" \t\r") for line in re.findall(
        r"(?im)^[ \t]*Depends-On:[ \t]*([^\n]*)", pr.get("body") or "")]
    if dependencies != ["#88"] and not (base == (main, "main") and not dependencies):
        return False
    paths = profile["files"] + [MARKERS + task for task in profile["tasks"]]
    common.git(root, "diff", "--quiet", "--no-ext-diff", parent, main, "--", *paths)
    return source_lineage(root, parent, profile)


def observe_pr(env, event, root, main, policy, request, prerequisite):
    number = event["number"]
    if type(number) is not int or number < 1:
        raise ValueError("Invalid PR number")
    pr = request(common.REPOSITORY, f"pulls/{number}")
    expected = event["pull_request"]
    if (type(pr["number"]) is not int or type(expected["number"]) is not int
            or pr["number"] != number or expected["number"] != number
            or common.side(pr, "head") != common.side(expected, "head")
            or common.side(pr, "base") != common.side(expected, "base")
            or pr.get("body") != expected.get("body")):
        raise ValueError("PR snapshot changed")
    head, branch = common.side(pr, "head")
    base, base_ref = common.side(pr, "base")
    cut = proposed_cut(pr.get("body"), policy)
    supported = (event["action"] in common.OPEN_ACTIONS
                 and pr["state"] == expected["state"] == "open"
                 and pr["draft"] is False and expected["draft"] is False
                 and common.source_branch(branch))
    observation = None
    if supported and cut:
        if known_child(root, main, policy, cut, pr, prerequisite):
            observation = cut
        elif (base_ref == "main" and base == main
              and not re.search(r"(?im)^\s*Depends-On:", pr.get("body") or "")):
            common.git(root, "merge-base", "--is-ancestor", main, head)
            if scoped_diff(root, base, head, policy["profiles"][cut]):
                observation = cut
    if common.snapshot(pr) != common.snapshot(request(common.REPOSITORY, f"pulls/{number}")):
        raise ValueError("PR changed during observation")
    return observation


def known_push(root, main, policy, branch, head, request, prerequisite):
    for cut, profile in policy["profiles"].items():
        source = profile["source"]
        if (source["branch"], source["head"]) != (branch, head):
            continue
        endpoint = f"pulls/{source['number']}"
        pr = request(common.REPOSITORY, endpoint)
        observation = None
        if proposed_cut(pr.get("body"), policy) == cut and known_child(
                root, main, policy, cut, pr, prerequisite):
            observation = cut
        if common.snapshot(pr) != common.snapshot(request(common.REPOSITORY, endpoint)):
            raise ValueError("Source PR changed during push observation")
        return observation
    return None


def observe_push(env, event, root, main, policy, request, prerequisite):
    head, ref = common.sha(event["after"]), event["ref"]
    if (event["repository"]["full_name"] != common.REPOSITORY
            or event["deleted"] is not False or event["forced"] is not False
            or ref != env["GITHUB_REF"] or head != common.sha(env["GITHUB_SHA"])
            or not isinstance(ref, str) or not ref.startswith("refs/heads/")):
        raise ValueError("Push identity changed")
    branch = ref[len("refs/heads/"):]
    if not common.valid_branch(branch) or not common.source_branch(branch):
        return None
    endpoint = "git/ref/heads/" + branch
    if common.sha(request(common.REPOSITORY, endpoint)["object"]["sha"]) != head:
        raise ValueError("Branch changed")
    bound = any((profile["source"]["branch"], profile["source"]["head"]) == (branch, head)
                for profile in policy["profiles"].values())
    if bound:
        observation = known_push(root, main, policy, branch, head, request, prerequisite)
    else:
        common.git(root, "merge-base", "--is-ancestor", main, head)
        cut = proposed_cut(common.git(root, "show", "-s", "--format=%B", head).decode().strip(), policy)
        observation = cut if cut and scoped_diff(root, main, head, policy["profiles"][cut]) else None
    if common.sha(request(common.REPOSITORY, endpoint)["object"]["sha"]) != head:
        raise ValueError("Branch changed during observation")
    return observation


def classify(env, event, root, request=common.github):
    result = {"mode": "shadow", "required_ci": "full", "efficiency_enabled": False,
              "skip_ci": False, "queue_admission": False, "qualification": "not-qualified",
              "proposed_cut": None, "p01_status": "unavailable",
              "reason": "unsupported-event", "policy_sha": None}
    try:
        if env.get("GITHUB_REPOSITORY") != common.REPOSITORY or not isinstance(event, dict):
            return result
        main = common.sha(common.git(root, "rev-parse", "HEAD").decode().strip())
        result["policy_sha"] = main
        if common.sha(request(common.REPOSITORY, "git/ref/heads/main")["object"]["sha"]) != main:
            result["reason"] = "policy-main-moved"
            return result
        policy = read_policy(root, main)
        prerequisite = request(common.REPOSITORY, "pulls/88")
        status = p01_status(root, main, policy, prerequisite)
        cut = None
        if status == "merged-contract-observed":
            if env.get("GITHUB_EVENT_NAME") == "pull_request":
                cut = observe_pr(env, event, root, main, policy, request, prerequisite)
            elif env.get("GITHUB_EVENT_NAME") == "push":
                cut = observe_push(env, event, root, main, policy, request, prerequisite)
        if (common.snapshot(prerequisite) != common.snapshot(request(common.REPOSITORY, "pulls/88"))
                or common.sha(request(common.REPOSITORY, "git/ref/heads/main")["object"]["sha"]) != main):
            raise ValueError("Prerequisite or main changed")
        result.update(p01_status=status, proposed_cut=cut,
                      reason="cut-observed-not-qualified" if cut else "full-fallback")
    except common.ERRORS:
        result.update(proposed_cut=None, p01_status="unavailable", reason="unreadable-or-stale-context")
    return result


def main():
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError):
        event = {}
    result = classify(os.environ, event, Path.cwd())
    print(json.dumps(result, sort_keys=True))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("### v1.3 shadow (disabled efficiency)\n\n"
                          f"P01: `{result['p01_status']}`; proposed cut: `{result['proposed_cut']}`; "
                          f"reason: `{result['reason']}`.\n\n"
                          "Full CI remains required. No skips, queue admission or live qualification.\n")


if __name__ == "__main__":
    main()
