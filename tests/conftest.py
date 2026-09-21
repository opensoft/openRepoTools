# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures, and the one thing this suite needs that it does not ship.

NO NETWORK AND NO GITHUB. Every test here runs `park`, `resume` or
`openRepoTools` against BARE REPOSITORIES IN A TEMPORARY DIRECTORY, a fake
`$HOME`, and — where a fetch is under test — a fake `gh` first on `$PATH` with
a `curl` that refuses. Nothing in this suite may create a real repository; if a
test ever needs a real `gh`, it is the wrong test.

THE STANDARD IS MOUNTED, NOT COPIED. `tests/test_park_resume_commands.py`
builds estates out of eight of openRepoShape's own files, and it reads them out
of the `upstream/openRepoShape` submodule this repository pins in
`contracts/openreposhape-pin.yaml`. A clone made WITHOUT `--recurse-submodules`
therefore has no template bytes to copy — so those tests SKIP, naming the one
command that fixes it. They never fail: a fork's first `pytest` going red on a
missing submodule is a fork nobody finishes.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: The pinned openRepoShape checkout. Every path this suite reads out of the
#: standard hangs off this one name, so a bump of the pin moves one line in
#: `contracts/openreposhape-pin.yaml` and the gitlink beside it, and nothing
#: here.
UPSTREAM = REPO / "upstream" / "openRepoShape"

#: THE TESTS THAT NEED THE STANDARD'S REAL BYTES. `scripts/repo_shape.py` is
#: the probe rather than the directory itself, because `git clone` without
#: `--recurse-submodules` leaves an EMPTY `upstream/openRepoShape/` behind —
#: the directory exists and holds nothing, so `is_dir()` would answer yes and
#: the tests would fail on a missing file instead of skipping.
NEEDS_UPSTREAM = pytest.mark.skipif(
    not (UPSTREAM / "scripts" / "repo_shape.py").is_file(),
    reason="the pinned openRepoShape is not checked out; "
           "run `git submodule update --init upstream/openRepoShape`")

#: THE TESTS THAT CANNOT RUN ON WINDOWS. Two shapes of test wear this: one that
#: runs `bash`, and one that puts a `#!`-shebang script named `gh` on PATH and
#: expects the operating system to execute it. Windows has neither — `bash.exe`
#: IS on the GitHub runner, so a `shutil.which("bash")` guard does not fire,
#: but `park`, `resume` and `openRepoTools` are bash scripts that run `make` in
#: a root which execs a shebang script, and a shebang means nothing to
#: CreateProcess. Skipping is honest because there is no Windows twin to run
#: instead: these three files are bash, and on Windows the way in is WSL2,
#: exactly as it is for openRepoShape's own `setup.sh`. What the Windows job
#: still proves is the checkout and the hygiene tests, which need no shell.
#: A shared `skipif` object rather than a named marker because there is no
#: pytest.ini to register one in, and an unregistered marker is a warning.
WINDOWS_SKIP = pytest.mark.skipif(
    os.name == "nt",
    reason="needs a POSIX shell and shebang execution; on Windows the way in "
           "is WSL2, as it is for openRepoShape's setup.sh")


def rmtree(path: Path) -> None:
    """`shutil.rmtree` that also works over a git object store on Windows.

    Git writes loose objects and packs READ-ONLY, and Windows refuses to
    unlink a read-only file — so a plain `rmtree` over a checkout raises
    PermissionError there and succeeds everywhere else. The handler clears the
    read-only bit and retries the one call that failed. `onerror` rather than
    `onexc`: the newer spelling is 3.12+, and this standard runs on 3.9.
    """
    def clear_readonly(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onerror=clear_readonly)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=False)
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} in {cwd} failed:\n"
                             f"{proc.stderr}{proc.stdout}")
    return proc


@pytest.fixture
def managed_workspace(tmp_path: Path) -> SimpleNamespace:
    """Private local workspace and project repositories for managed-lane tests.

    The fixture deliberately returns its environment instead of changing the
    test process environment. Tests must opt into the fake HOME/workspace and
    cannot accidentally consult the workstation's real lane registry.
    """
    home = tmp_path / "home"
    workspace_repo = tmp_path / "workspace-repository"
    project = tmp_path / "project"
    home.mkdir(mode=0o700)
    workspace_repo.mkdir(mode=0o700)
    project.mkdir(mode=0o700)
    git("init", "-q", cwd=workspace_repo)
    git("init", "-q", cwd=project)

    agents = home / ".agents"
    agents.mkdir(mode=0o700)
    workspace_yaml = agents / "workspace.yaml"
    workspace_yaml.write_text(
        "repository: local/test-workspace\n"
        f"path: {workspace_repo}\n",
        encoding="utf-8",
    )
    workspace_yaml.chmod(0o600)

    common_dir = Path(
        git("rev-parse", "--path-format=absolute", "--git-common-dir",
            cwd=workspace_repo).stdout.strip()
    )
    return SimpleNamespace(
        home=home,
        workspace_repo=workspace_repo,
        workspace_yaml=workspace_yaml,
        project=project,
        common_dir=common_dir,
        lane="build",
        env={"HOME": str(home), "AGENT_PROTOCOL_ROOT": str(agents)},
    )


@pytest.fixture
def managed_profiles(tmp_path: Path) -> SimpleNamespace:
    """A read-only-style workBenches manifest with safe synthetic accounts."""
    config_home = tmp_path / "config"
    profiles_home = tmp_path / "claude-profiles"
    manifest = config_home / "workbenches" / "claude-profiles.json"
    manifest.parent.mkdir(parents=True, mode=0o700)

    profiles = [
        ("team-a", "a@example.invalid", "family-a", ["teama"],
         "subscription_oauth"),
        ("team-b", "b@example.invalid", "family-a", ["teamb"],
         "subscription_oauth"),
        ("other-family", "c@example.invalid", "family-b", [],
         "subscription_oauth"),
        ("setup-token", "setup@example.invalid", "family-a", [],
         "setup_token"),
    ]
    entries = []
    for name, email, family, aliases, auth_type in profiles:
        metadata_relative = Path(family) / "team" / name
        # Deployed workBenches estates exist in both layouts: newer manifests
        # resolve `profilePath` below `profiles/`, while older/local materialized
        # profiles may be flat and are found by unique metadata fallback.
        if name == "team-b":
            profile_dir = profiles_home / "profiles" / name
        else:
            profile_dir = profiles_home / "profiles" / metadata_relative
        profile_dir.mkdir(parents=True, mode=0o700)
        metadata = {
            "name": name,
            "email": email,
            "family": family,
            "aliases": aliases,
        }
        (profile_dir / ".profile.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )
        entries.append({
            **metadata,
            "status": "active",
            "profilePath": str(metadata_relative),
            "authentication": {"type": auth_type},
        })

    manifest.write_text(
        json.dumps({"version": 1, "profiles": entries}), encoding="utf-8"
    )
    manifest.chmod(0o600)
    return SimpleNamespace(
        manifest=manifest,
        profiles_home=profiles_home,
        entries=entries,
        env={
            "XDG_CONFIG_HOME": str(config_home),
            "CLAUDE_PROFILES_HOME": str(profiles_home),
            "CLAUDE_PROFILES_MANIFEST": str(manifest),
        },
    )


@pytest.fixture
def fake_managed_runtime(tmp_path: Path):
    """Build a bounded JSON-lines runtime and expose its request journal.

    ``build`` accepts a mapping from request operation to response-event lists.
    The child records each request before emitting its configured events, which
    lets SDK/controller tests assert ordering without credentials or sessions.
    """
    def build(events_by_operation):
        runtime = tmp_path / "fake-managed-runtime.py"
        journal = tmp_path / "fake-managed-runtime.requests"
        encoded = json.dumps(events_by_operation)
        runtime.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, sys\n"
            f"EVENTS = json.loads({encoded!r})\n"
            f"JOURNAL = pathlib.Path({str(journal)!r})\n"
            "for raw in sys.stdin:\n"
            "    request = json.loads(raw)\n"
            "    with JOURNAL.open('a', encoding='utf-8') as stream:\n"
            "        stream.write(json.dumps(request) + chr(10))\n"
            "    for event in EVENTS.get(request.get('operation'), []):\n"
            "        print(json.dumps(event), flush=True)\n",
            encoding="utf-8",
        )
        runtime.chmod(0o700)
        return SimpleNamespace(command=[sys.executable, str(runtime)],
                               script=runtime, journal=journal)

    return build
