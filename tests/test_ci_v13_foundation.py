# SPDX-License-Identifier: Apache-2.0
"""Reviewed foundation epochs in disposable Git histories, never live changes."""

from __future__ import annotations

import copy
import json
import subprocess

import pytest

from test_ci_delivery import batch, commit, delivery, git, request_for, verify
from test_ci_cutover import cutover
from test_ci_v13_delivery import route_source, v13, v13_batch, write


def advance_fixture(batch, base):
    """Reconstruct the same two immutable cuts on a new simulated main."""
    root, previous, prefixes = batch["root"], base, []
    for head in batch["heads"]:
        tree = git(root, "merge-tree", "--write-tree", previous, head)
        previous = git(root, "commit-tree", tree, "-p", previous, "-p", head,
                       "-m", "candidate fixture")
        prefixes.append(previous)
    replacements = dict(zip([batch["base"], *batch["prefixes"]], [base, *prefixes]))
    for key in ("data", "env", "event"):
        text = json.dumps(batch[key])
        for before, after in replacements.items():
            text = text.replace(before, after)
        batch[key] = json.loads(text)
    batch.update(base=base, prefixes=prefixes, candidate=previous)
    batch["prs"] = {number: batch["data"][f"pulls/{number}"] for number in (7, 8)}


def observe_foundation(v13, batch):
    """The same foundation facts never turn observer output into authority."""
    env = dict(batch["env"], GITHUB_EVENT_NAME="pull_request")
    event = {"action": "synchronize", "number": 7,
             "pull_request": copy.deepcopy(batch["prs"][7])}
    result = v13.projection.classify(env, event, batch["root"], request_for(batch))
    assert result["mode"] == "shadow" and result["required_ci"] == "full"
    assert result["efficiency_enabled"] is False and result["skip_ci"] is False
    assert result["queue_admission"] is False and result["qualification"] == "not-qualified"
    return result


@pytest.fixture
def epoch_batch(v13_batch, v13):
    batch, root = v13_batch, v13_batch["root"]
    write(root, "tests/pgcluster.py", "# explicitly reviewed new foundation\n")
    epoch = commit(root, "owner foundation landing")
    policy = copy.deepcopy(batch["policy"])
    policy["foundation"] = {"head": epoch, "blobs": {
        path: git(root, "rev-parse", epoch + ":" + path) for path in v13.projection.P01_FILES}}
    write(root, v13.projection.CONFIG, json.dumps(policy))
    base = commit(root, "trusted explicit foundation epoch")
    advance_fixture(batch, base)
    batch.update(policy=policy, epoch=epoch)
    return batch


def test_ci_v13_foundation_explicit_reviewed_epoch_keeps_source_and_heavy_proof(v13, cutover, delivery, epoch_batch):
    batch = epoch_batch
    assert v13.configuration(batch["root"], batch["base"])["foundation"]["head"] == batch["epoch"]
    assert route_source(cutover, batch)["omit_full"] is True
    proof = verify(delivery, batch)
    assert proof["full_ci_required"] is True and proof["scope"] == v13.SCOPE
    assert [row["head"] for row in proof["members"]] == batch["heads"]
    observed = observe_foundation(v13, batch)
    assert observed["p01_status"] == "merged-contract-observed"
    assert observed["proposed_cut"] == "P03"


@pytest.mark.parametrize("failure", ["absent", "null", "extra-key", "short-head", "extra-blob",
    "missing-blob", "wrong-blob", "unlanded", "unrelated", "unrelated-landed", "helper-drift", "mode-drift",
    "epoch-executable", "epoch-symlink",
    "workflow-drift", "baseline-drift", "marker-drift"])
def test_ci_v13_foundation_uncertain_or_drifted_epoch_refuses(v13, cutover, epoch_batch, failure):
    batch, root = epoch_batch, epoch_batch["root"]
    policy = copy.deepcopy(batch["policy"])
    epoch = policy["foundation"]
    if failure == "absent": policy.pop("foundation")
    elif failure == "null": policy["foundation"] = None
    elif failure == "extra-key": epoch["allow_drift"] = True
    elif failure == "short-head": epoch["head"] = epoch["head"][:7]
    elif failure == "extra-blob": epoch["blobs"]["lanes-index"] = "a" * 40
    elif failure == "missing-blob": epoch["blobs"].pop("tests/pgcluster.py")
    elif failure == "wrong-blob": epoch["blobs"]["tests/pgcluster.py"] = "a" * 40
    elif failure == "unlanded": epoch["head"] = batch["heads"][0]
    elif failure in {"unrelated", "unrelated-landed"}:
        epoch["head"] = git(root, "commit-tree", git(root, "rev-parse", "HEAD^{tree}"),
                            "-m", "unrelated unlanded foundation")
        if failure == "unrelated-landed":
            joined = git(root, "commit-tree", git(root, "rev-parse", "HEAD^{tree}"),
                         "-p", git(root, "rev-parse", "HEAD"), "-p", epoch["head"], "-m", "joined unrelated root")
            git(root, "checkout", "-q", "--detach", joined)
    elif failure in {"epoch-executable", "epoch-symlink"}:
        helper = root / "tests/pgcluster.py"
        if failure == "epoch-executable":
            helper.chmod(0o755)
        else:
            helper.unlink()
            helper.symlink_to("missing-template")
        epoch["head"] = commit(root, "bad mode inside the declared epoch")
        epoch["blobs"] = {path: git(root, "rev-parse", epoch["head"] + ":" + path)
                          for path in v13.projection.P01_FILES}
    elif failure == "mode-drift":
        (root / "tests/pgcluster.py").chmod(0o755)
    else:
        path = {"helper-drift": "tests/pgcluster.py", "workflow-drift": ".github/workflows/tests.yml",
                "baseline-drift": v13.projection.BASELINE,
                "marker-drift": v13.projection.MARKERS + v13.projection.P01_TASKS[0]}[failure]
        write(root, path, "changed after the reviewed epoch\n")
    write(root, v13.projection.CONFIG, json.dumps(policy))
    base = commit(root, "uncertain foundation fixture")
    advance_fixture(batch, base)
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        v13.configuration(root, base)
    assert route_source(cutover, batch) == cutover.FULL
    assert observe_foundation(v13, batch)["proposed_cut"] is None


@pytest.mark.parametrize("v13_batch", ["reviewed-pair"], indirect=True)
def test_ci_v13_foundation_reviewed_pair_uses_unchanged_narrow_proof(v13, cutover, delivery, epoch_batch):
    batch = epoch_batch
    assert set(batch["policy"]["profiles"]) == {"P05", "P06"}
    assert all(len(profile["source"]["commits"]) == 2 for profile in batch["policy"]["profiles"].values())
    assert route_source(cutover, batch)["omit_full"] is True
    proof = verify(delivery, batch)
    assert proof["scope"] == v13.SCOPE and proof["full_ci_required"] is True
    assert [row["head"] for row in proof["members"]] == batch["heads"]
    observed = observe_foundation(v13, batch)
    assert observed["p01_status"] == "merged-contract-observed"
    assert observed["proposed_cut"] == "P05"


@pytest.mark.parametrize("v13_batch", ["reviewed-pair"], indirect=True)
@pytest.mark.parametrize("failure", ["old-task", "head", "unknown-pair", "too-many-files", "too-many-markers"])
def test_ci_v13_foundation_reviewed_pair_does_not_broaden_scope(v13, cutover, delivery, epoch_batch, failure):
    batch, root = epoch_batch, epoch_batch["root"]
    if failure == "old-task":
        batch["prs"][7]["body"] = batch["prs"][7]["body"].replace("P05", "P03")
    elif failure == "head":
        batch["prs"][7]["head"]["sha"] = batch["heads"][1]
    else:
        policy = copy.deepcopy(batch["policy"])
        if failure == "unknown-pair":
            policy["profiles"]["P04"] = policy["profiles"].pop("P06")
        elif failure == "too-many-files":
            policy["profiles"]["P05"]["files"] += [
                "tests/test_sql_register_extra_one.py", "tests/test_sql_register_extra_two.py",
                "tests/test_sql_register_extra_three.py"]
        else:
            policy["profiles"]["P06"]["tasks"].append("T299")
        write(root, v13.projection.CONFIG, json.dumps(policy))
        advance_fixture(batch, commit(root, "unqualified profile fixture"))
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        verify(delivery, batch)
    assert route_source(cutover, batch) == cutover.FULL
