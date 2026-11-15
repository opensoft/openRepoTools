# SPDX-License-Identifier: Apache-2.0
"""Delivery-specific v1.3 checks; shadow output never supplies authority."""

from __future__ import annotations

import json
import re

import shadow_scope as common
import v13_shadow as projection

SCOPE = "sql-register-v13"
CONFIG = ".github/ci/delivery-v13-policy.json"


def intended(text):
    if not isinstance(text, str):
        return False
    for key, value in (("CI-Shadow", SCOPE), ("CI-Delivery", SCOPE)):
        lines = re.findall(r"(?im)^[ \t]*" + key + r":[^\n]*", text)
        if [line.rstrip(" \t\r") for line in lines] != [key + ": " + value]:
            return False
    return True


def configuration(root, base):
    value = json.loads(common.git(root, "show", f"{base}:{CONFIG}"),
                       object_pairs_hook=projection.unique_pairs)
    if (set(value) != {"schema_version", "scope", "enabled"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["scope"] != SCOPE or value["enabled"] is not True):
        raise ValueError("V1.3 delivery is not enabled")
    # Reuse the reviewed immutable projection, NOT classify() or its output.
    policy = projection.read_policy(root, base)
    projection.require_foundation(root, base, policy)
    return policy


def cut(root, base, head):
    policy = configuration(root, base)
    matches = [(name, profile) for name, profile in policy["profiles"].items()
               if profile["source"]["head"] == head]
    if len(matches) != 1:
        raise ValueError("Unrecognized v1.3 source head")
    name, profile = matches[0]
    parent = policy["prerequisite"]["head"]
    if not projection.source_lineage(root, parent, profile):
        raise ValueError("V1.3 source lineage differs")
    paths = profile["files"] + [projection.MARKERS + task for task in profile["tasks"]]
    common.git(root, "diff", "--quiet", "--no-ext-diff", parent, base, "--", *paths)
    return policy, name, profile


def source(root, base, pr, request):
    head, branch = common.side(pr, "head")
    policy, name, profile = cut(root, base, head)
    if (not intended(pr.get("body"))
            or projection.proposed_cut(pr["body"], policy) != name
            or re.search(r"(?im)^[ \t]*Depends-On:", pr["body"])
            or type(pr["number"]) is not int or pr["number"] != profile["source"]["number"]
            or branch != profile["source"]["branch"]
            or common.side(pr, "base") != (base, "main")
            or pr["state"] != "open" or pr["draft"] is not False
            or pr.get("merged") is not False):
        raise ValueError("V1.3 source metadata differs")
    prerequisite = request(common.REPOSITORY, "pulls/88")
    if projection.p01_status(root, base, policy, prerequisite) != "merged-contract-observed":
        raise ValueError("V1.3 prerequisite is not qualified")
    if (prerequisite != request(common.REPOSITORY, "pulls/88")
            or request(common.REPOSITORY, "git/ref/heads/" + branch)["object"]["sha"] != head):
        raise ValueError("V1.3 source prerequisite changed")
    return name


def prefix(root, base, head, previous, merged):
    _policy, _name, profile = cut(root, base, head)
    return projection.scoped_diff(root, previous, merged, profile)


def unchanged_policy(root, base, main):
    policy = configuration(root, base)
    configuration(root, main)
    allowed = {path for profile in policy["profiles"].values() for path in profile["files"]}
    allowed |= {projection.MARKERS + task for profile in policy["profiles"].values()
                for task in profile["tasks"]}
    changed = common.git(root, "diff", "--name-only", base, main, "--").decode().splitlines()
    return all(path in allowed for path in changed)
