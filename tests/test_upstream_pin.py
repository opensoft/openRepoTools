# SPDX-License-Identifier: Apache-2.0
"""`contracts/openreposhape-pin.yaml` and the gitlink beside it are ONE fact.

A pin file and a submodule are two records of the same commit, written in two
places, and nothing but a test keeps them from drifting: a `git submodule
update --remote` moves the gitlink and no line of YAML, and a hand-edited
`commit:` moves the YAML and no byte of the tree. Either way the next reader is
told the tests were verified against a commit they were not.

FOUR OF THE FIVE CHECKS HERE NEED NO SUBMODULE, on purpose. The gitlink is read
out of `git ls-tree HEAD` in three lines of subprocess and nothing in this file
imports anything from `upstream/openRepoShape` — so a clone made without
`--recurse-submodules` still gets the lockstep check. Only the digest needs the
real bytes, and it is the one thing here that carries `NEEDS_UPSTREAM`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import NEEDS_UPSTREAM, REPO, UPSTREAM

PIN = REPO / "contracts" / "openreposhape-pin.yaml"
SUBMODULE_PATH = "upstream/openRepoShape"
SOURCE_REPOSITORY = "opensoft/openRepoShape"
SOURCE_URL = "https://github.com/opensoft/openRepoShape.git"

#: 40 means 40, and lowercase means lowercase. An abbreviated oid, a branch
#: name or a tag cannot pass — `openRepoShape`'s own `COMMIT_RE`, spelled here
#: rather than imported, because a pin check that had to import the thing it is
#: checking could not run in a clone that never materialized it.
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def pin_scalars() -> dict:
    """Every `key: value` in the pin file, at any indent, comments stripped.

    A ~15-line reader rather than a YAML dependency: this repository ships
    three bash files and installs nothing, and the file it reads is a flat map
    with one nested key written by hand. The nesting is flattened onto the leaf
    name (`tree_sha256`), which is unambiguous here because no leaf name
    repeats — asserted below, so a second `tree_sha256` under some other block
    would fail rather than shadow this one.
    """
    values: dict = {}
    for raw in PIN.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not value:
            continue
        assert key not in values, f"{key} appears twice in {PIN.name}"
        values[key] = value
    return values


def test_the_pin_records_a_full_lowercase_commit():
    """A tag can be moved and a commit cannot, and a pin the next person
    cannot fetch is a pin nobody can reproduce."""
    commit = pin_scalars()["commit"]
    assert COMMIT_RE.match(commit), (
        f"commit: {commit!r} is not 40 lowercase hex")


def test_the_gitlink_and_the_pin_name_the_same_commit():
    """THE LOCKSTEP CHECK, and the reason this file exists.

    `git ls-tree HEAD -- upstream/openRepoShape` prints the commit git has
    RECORDED for that path, which is what a `git clone --recurse-submodules`
    will check out — not what happens to be checked out here right now. So this
    bites on a moved gitlink whether or not the submodule is materialized, and
    it bites on a hand-edited `commit:` the same way.
    """
    proc = subprocess.run(["git", "ls-tree", "HEAD", "--", SUBMODULE_PATH],
                          cwd=str(REPO), capture_output=True, text=True,
                          check=True)
    row = proc.stdout.strip()
    assert row, (f"git records no gitlink at {SUBMODULE_PATH}; the pin file "
                 f"and the submodule are one commit, and this is half of it")
    mode, kind, rest = row.split(" ", 2)
    recorded = rest.split("\t", 1)[0]
    assert mode == "160000" and kind == "commit", (
        f"{SUBMODULE_PATH} is recorded as `{mode} {kind}`, not as a gitlink")
    assert recorded == pin_scalars()["commit"], (
        f"the gitlink is {recorded} and {PIN.name} says "
        f"{pin_scalars()['commit']}; they move in one commit")


def test_gitmodules_names_the_same_path_and_repository():
    """The third record of the same fact, and the one a `git submodule update`
    reads. A pin whose `submodule_path:` named a path `.gitmodules` does not
    would be a pin nothing materializes."""
    text = (REPO / ".gitmodules").read_text(encoding="utf-8")
    assert f'[submodule "{SUBMODULE_PATH}"]' in text
    assert f"path = {SUBMODULE_PATH}" in text
    assert f"url = {SOURCE_URL}" in text
    values = pin_scalars()
    assert values["submodule_path"] == SUBMODULE_PATH
    assert values["source_repository"] == SOURCE_REPOSITORY


def test_the_pin_says_mounted_and_names_its_verifier():
    """MOUNTED is a claim about this repository's whole arrangement: the tests
    run on the standard's real bytes at a commit, not on copies here. A pin
    that said `copied` would be describing a tree that does not exist."""
    values = pin_scalars()
    assert values["pin_role"] == "upstream-standard"
    assert values["materialization"] == "mounted"
    assert values["revision_kind"] == "commit"
    assert values["digest_algorithm"] == "sha256"
    assert values["verify_pin"] == "tests/test_upstream_pin.py"
    assert SHA256_RE.match(values["tree_sha256"]), (
        f"tree_sha256: {values['tree_sha256']!r} is not 64 lowercase hex")


@NEEDS_UPSTREAM
def test_the_tree_digest_is_the_pinned_commits_own_number():
    """Recomputed with the PINNED CHECKOUT'S OWN `scripts/repo_shape.py`.

    Two things fall out of importing the standard's code rather than copying
    it. This repository carries no copy of `tree_digest` to fall behind the
    definition it implements — the digest is checked against the pinned
    commit's own idea of what `sorted-ls-tree-r-v1` means, which is the only
    reading that can be right about a number that commit's tools produced. And
    a bump of the pin that changed the definition would fail HERE, naming the
    disagreement, instead of producing a number nothing could reproduce.
    """
    sys.path.insert(0, str(UPSTREAM / "scripts"))
    try:
        from repo_shape import TREE_DIGEST_DEFINITION, tree_digest
    finally:
        sys.path.pop(0)
    values = pin_scalars()
    assert values["digest_definition"] == TREE_DIGEST_DEFINITION, (
        f"the pin says `digest_definition: {values['digest_definition']}` and "
        f"the pinned openRepoShape's own repo_shape.py says "
        f"{TREE_DIGEST_DEFINITION!r}")
    computed = tree_digest(UPSTREAM, "HEAD")
    assert computed == values["tree_sha256"], (
        f"the pinned checkout's tree digests to {computed} and {PIN.name} "
        f"records {values['tree_sha256']}. RECOMPUTE the row from the commit "
        f"you meant to pin; never edit it to agree with this checkout")


@NEEDS_UPSTREAM
def test_the_checked_out_submodule_is_at_the_recorded_commit():
    """The fourth record: what is on disk right now. `git ls-tree` above says
    what a fresh clone gets; this says what THIS working tree has, which is
    what the rest of the suite actually reads its template bytes out of."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(UPSTREAM),
                          capture_output=True, text=True, check=True)
    assert head.stdout.strip() == pin_scalars()["commit"], (
        "the checked-out submodule is not at the pinned commit; "
        "run `git submodule update --init upstream/openRepoShape`")


@NEEDS_UPSTREAM
@pytest.mark.parametrize("rel", [
    "scripts/repo_shape.py",
    "templates/assembly-root/Makefile",
    "templates/assembly-root/.gitignore",
    "templates/assembly-root/scripts/bootstrap.py",
    "templates/family-root/Makefile",
    "templates/family-root/.gitignore",
    "templates/family-root/scripts/bootstrap.py",
    "templates/family-root/scripts/siblings.py",
])
def test_the_pinned_commit_carries_what_this_suite_reads(rel):
    """The eight files `test_park_resume_commands.py` copies.

    EIGHT, not the seven openRepoShape #92 counted: the two root Makefiles, the
    two `.gitignore`s, the two `bootstrap.py`s, `siblings.py` and
    `scripts/repo_shape.py`. The issue's prose miscounted its own list; this
    parametrization is the list, so it cannot.

    They are what makes the submodule worth having, and a pin bumped past
    a rename would otherwise fail deep inside a fixture with a `FileNotFound`
    naming a path nobody was looking for.

    `park`, the pre-carve witness, leaves this list in THIS commit: the one
    that bumps the pin past openRepoShape#94, which deleted it from the tree.
    """
    assert (UPSTREAM / rel).is_file(), (
        f"the pinned openRepoShape has no {rel}")
