"""Grouped discovery through real commands; all writes use isolated registers."""
from pathlib import Path
import subprocess
import shutil
import pytest
from conftest import NEEDS_UPSTREAM, REPO, WINDOWS_SKIP
from test_park_resume_commands import (FAMILY, WORKSPACE_SLUG, git, home, estate, remotes, offline,
                                      probe_project, probe_family, sweepable_project, run)
from test_lane_start_claude_current import Sandbox

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    any(shutil.which(command) is None for command in ("bash", "git", "make")),
    reason="grouped CLI tests require bash, git and make")]


def block(name):
    text = (REPO / name).read_text()
    return text.split("# BEGIN GROUPED PROJECT DISCOVERY", 1)[1].split("# END GROUPED PROJECT DISCOVERY", 1)[0]


def test_discovery_copies_match():
    assert len({block(name) for name in ("park", "resume", "status", "lane-start")}) == 1


def rows(root):
    result = subprocess.run(["bash", "-c", block("park") + '\nproject_directory_rows "$1"', "lookup", str(root)], text=True, capture_output=True, check=True)
    return [[parts[0], parts[-1]] for parts in (line.split("\t") for line in result.stdout.splitlines())]


def test_bounds_support_collections_and_repository_boundaries(tmp_path):
    for group in ("workTrees", "laneWorkspaces", "brett-wip-lanes", "wip-lanes", "personal-register-lanes", "brett-wip-lane-registers", "worktrees"):
        probe_project(tmp_path / group, "Hidden")
    target = probe_project(tmp_path / "business" / "Company space", "Visible")
    probe_project(tmp_path / "business" / "Company space" / "too-deep", "Deep")
    outer = probe_project(tmp_path / "factories", "Outer")
    probe_project(outer / "members", "Pinned")
    family = probe_family(tmp_path / "healthcare", "Family")
    probe_project(family.parent / "members", "Sibling")
    found = rows(tmp_path)
    names = [r[0] for r in found]
    assert ["Visible", str(target)] in found
    assert not {"Hidden", "Deep", "Pinned", "Sibling"}.intersection(names)
    assert "Family" in names


@pytest.mark.parametrize("family", [False, True])
def test_named_grouped_estate(tmp_path, family):
    home = tmp_path / "home"; home.mkdir()
    group = home / "projects" / "group space"
    root = (probe_family if family else probe_project)(group, "Atlas")
    result = run(REPO / "park", "Atlas", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {root}" in result.stdout


@pytest.mark.parametrize("command", ["park", "resume", "status"])
@NEEDS_UPSTREAM
def test_distinct_matching_estates_refuse(tmp_path, command, remotes):
    home = tmp_path / "home"; home.mkdir()
    name = FAMILY if command == "resume" else "Atlas"
    for group in ("one", "two"):
        probe_project(home / "projects" / group, name)
    args = [name]
    if command == "resume":
        args += ["--workspace", WORKSPACE_SLUG]
    result = run(REPO / command, *args, home=home, env=offline(remotes))
    assert result.returncode != 0
    assert "multiple estates named" in result.stderr
    assert "PROBE" not in result.stdout


def grouped_box(tmp_path):
    box = Sandbox(tmp_path)
    target = box.home / "projects" / "developerTools" / "repoZ"
    target.parent.mkdir(); box.lane_dir.rename(target); box.lane_dir = target
    box.resolver()
    return box


@pytest.mark.parametrize("alias", [None, "repoZ", "repoz"])
def test_new_lane_uses_grouped_canonical_target(tmp_path, alias):
    box = grouped_box(tmp_path)
    if alias:
        (box.home / "projects" / alias).symlink_to(box.lane_dir, target_is_directory=True)
    result = box.start()
    assert result.returncode == 0, result.stderr
    assert str(box.lane_dir) in box.lane_log()
    assert box.claude_runs()


def test_ambiguous_new_lane_refuses_without_register_writes(tmp_path):
    box = grouped_box(tmp_path)
    other = box.home / "projects" / "other" / "repoZ"; other.mkdir(parents=True)
    box.git("-C", str(other), "init", "-q")
    before = box.commits()
    result = box.start()
    assert result.returncode != 0
    assert box.commits() == before
    assert not box.lane_log()
    assert not box.claude_runs()


def test_explicit_lane_path_wins_over_grouped_ambiguity(tmp_path):
    box = grouped_box(tmp_path)
    other = box.home / "projects" / "other" / "repoZ"; other.mkdir(parents=True)
    box.git("-C", str(other), "init", "-q")
    result = box.start("--dir", str(box.lane_dir))
    assert result.returncode == 0, result.stderr
    assert str(box.lane_dir) in box.lane_log()


def test_grouped_sweep_runs_physical_estate_once(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    projects = home / "projects"
    root = sweepable_project(projects / "developerTools", "Atlas")
    (projects / "Atlas").symlink_to(root, target_is_directory=True)
    result = run(REPO / "park", "--all", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.count(f"PROBE park in {root}") == 1
    assert "1 estate(s) parked" in result.stdout


def test_configured_projects_directory_supports_groups(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    elsewhere = tmp_path / "elsewhere"
    root = probe_project(elsewhere / "group", "Atlas")
    result = run(REPO / "park", "Atlas", home=home, env={"PROJECTS_DIR": str(elsewhere)})
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {root}" in result.stdout


def test_missing_recorded_directory_does_not_fall_back_to_group(tmp_path):
    box = grouped_box(tmp_path)
    result = box.start()
    assert result.returncode == 0, result.stderr
    before = box.commits()
    moved = box.lane_dir.with_name("moved")
    box.lane_dir.rename(moved)
    original = box.lane_dir
    box.lane_dir = moved
    replacement = box.home / "projects" / "elsewhere" / "repoZ"
    replacement.mkdir(parents=True)
    box.git("-C", str(replacement), "init", "-q")
    result = box.start()
    assert result.returncode != 0
    assert str(original) in result.stderr
    assert box.commits() == before


def test_grouped_origin_lookup_and_duplicate_origin_refusal(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    projects = home / "projects"
    first = probe_project(projects / "business" / "Company", "Atlas")
    def origin(root):
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "remote", "add", "origin", "https://github.com/testorg/Atlas.git"], check=True)
    origin(first)
    result = run(REPO / "park", "--repo", "testorg/Atlas", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {first}" in result.stdout
    second = probe_project(projects / "other", "AtlasCopy"); origin(second)
    for command in ("park", "resume", "status"):
        result = run(REPO / command, "--repo", "testorg/Atlas", home=home)
        assert result.returncode != 0
        assert "multiple development checkouts" in result.stderr
        assert "PROBE" not in result.stdout


@pytest.mark.parametrize("kind", ["linked", "bare"])
def test_supporting_git_checkout_is_not_a_default_candidate(tmp_path, kind):
    box = grouped_box(tmp_path)
    other = box.home / "projects" / "other" / "repoZ"
    other.parent.mkdir()
    if kind == "linked":
        box.git("-C", str(box.lane_dir), "commit", "-q", "--allow-empty", "-m", "fixture base")
        box.git("-C", str(box.lane_dir), "worktree", "add", "--detach", str(other), "HEAD")
    else:
        box.git("clone", "--bare", str(box.lane_dir), str(other))
    result = box.start()
    assert result.returncode == 0, result.stderr
    assert str(box.lane_dir) in box.lane_log()


@NEEDS_UPSTREAM
def test_resume_grouped_existing_family(home, remotes, estate):
    target = home / "projects" / "group" / FAMILY
    target.parent.mkdir()
    estate["folder"].rename(target)
    result = run(REPO / "resume", FAMILY, "--workspace", WORKSPACE_SLUG,
                 home=home, env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    assert str(target) in result.stdout
    assert "Alpha.sh ran with:" in result.stdout
    assert not estate["folder"].exists()


@NEEDS_UPSTREAM
def test_resume_grouped_existing_standalone(home, remotes):
    target = home / "projects" / "group" / "Alpha"
    target.parent.mkdir()
    git("clone", "-q", str(remotes["members"]["Alpha"]), str(target), cwd=home)
    result = run(REPO / "resume", "Alpha", "--workspace", "tester/solo",
                 home=home, env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    assert str(target) in result.stdout
    assert "Alpha.sh ran with:" in result.stdout
    assert not (home / "projects" / "Alpha").exists()


def logical_family_aliases(home, storage, name):
    """A logical holder name unrelated to its physical container basename."""
    projects = home / "projects"; projects.mkdir(parents=True, exist_ok=True)
    physical = storage / "estate-data"
    holder = probe_family(storage, name)
    holder.parent.rename(physical)
    alias = projects / name
    alias.symlink_to(physical, target_is_directory=True)
    (projects / "000-invalid").symlink_to(physical, target_is_directory=True)
    group = projects / "group"; group.mkdir()
    (group / name).symlink_to(physical, target_is_directory=True)
    return alias, physical / name


@pytest.mark.parametrize("sweep", [False, True])
def test_logical_family_alias_park_dispatch_and_dedup(tmp_path, sweep):
    home = tmp_path / "home"
    alias, holder = logical_family_aliases(home, tmp_path / "storage", "Atlas")
    result = run(REPO / "park", "--all" if sweep else "Atlas", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert result.stdout.count(f"PROBE park in {holder}") == 1
    assert alias.is_symlink()


@pytest.mark.parametrize("sweep", [False, True])
def test_logical_family_alias_status_recognition(tmp_path, sweep):
    home = tmp_path / "home"
    alias, holder = logical_family_aliases(home, tmp_path / "storage", "Atlas")
    result = run(REPO / "status", "--all" if sweep else "Atlas", home=home)
    assert result.returncode in (0, 1), result.stderr + result.stdout
    assert "Atlas" in result.stdout
    assert "no estate" not in result.stderr
    assert alias.is_symlink()


def aliased_real_family(home, remotes, estate, tmp_path):
    physical = tmp_path / "storage" / "estate-data"; physical.parent.mkdir()
    estate["folder"].rename(physical)
    estate["folder"].symlink_to(physical, target_is_directory=True)
    (home / "projects" / "000-invalid").symlink_to(physical, target_is_directory=True)
    config = home / ".agents" / "workspace.yaml"; config.parent.mkdir()
    config.write_text(f"repository: {WORKSPACE_SLUG}\npath: ~/projects/wip\n")
    git("clone", "-q", str(remotes["workspace"]), str(home / "projects" / "wip"), cwd=home)
    return estate["folder"], physical


@pytest.mark.parametrize("by_id", [False, True])
@NEEDS_UPSTREAM
def test_logical_family_alias_resume_name_and_family_id(home, remotes, estate, tmp_path, by_id):
    alias, physical = aliased_real_family(home, remotes, estate, tmp_path)
    result = run(REPO / "resume", FAMILY.lower() if by_id else FAMILY,
                 "--dry-run", home=home, env=offline(remotes))
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"present         {alias} (family)" in result.stdout
    assert "would clone" not in result.stdout
    assert alias.is_symlink()


@pytest.mark.parametrize("command", ["park", "status"])
@NEEDS_UPSTREAM
def test_logical_family_alias_origin_lookup(home, remotes, estate, tmp_path, command):
    alias, physical = aliased_real_family(home, remotes, estate, tmp_path)
    slug = "testorg/" + FAMILY
    git("-C", str(alias / FAMILY), "remote", "set-url", "origin", "https://github.com/" + slug + ".git", cwd=home)
    args = ["--repo", slug]
    if command == "park": args.append("--dry-run")
    result = run(REPO / command, *args, home=home, env=offline(remotes))
    assert result.returncode in (0, 1), result.stderr + result.stdout
    assert "nothing at or above" not in result.stderr
    assert alias.is_symlink()


@pytest.mark.parametrize("matching_home", [True, False])
def test_recorded_home_without_directory_keeps_origin_proof(tmp_path, matching_home):
    box = grouped_box(tmp_path)
    result = box.start()
    assert result.returncode == 0, result.stderr
    log = box.wip / "lanes" / "log" / "repoZ-1.md"
    # Model an older record: home is known, but the directory field predates it.
    import re
    text = re.sub(r"; dir [^;\n]+", "", log.read_text())
    assert str(box.lane_dir) not in text
    log.write_text(text)
    box.git("-C", str(box.wip), "add", "--", str(log))
    box.git("-C", str(box.wip), "commit", "-q", "-m", "seed old home-only record")
    box.git("-C", str(box.wip), "push", "-q", "origin", "main")
    other = box.home / "projects" / "imposter" / "repoZ"
    other.mkdir(parents=True)
    box.git("init", "-q", str(other))
    box.git("-C", str(other), "remote", "add", "origin", "https://github.com/stranger/repoZ.git")
    if not matching_home:
        box.git("-C", str(box.lane_dir), "remote", "set-url", "origin", "https://github.com/stranger/also-wrong.git")
        moved = box.lane_dir.with_name("moved-away")
        box.lane_dir.rename(moved)
        box.lane_dir = moved
    before = box.commits()
    result = box.start("--dry-run")
    assert box.commits() == before
    assert f"cd {other}" not in result.stderr
    if matching_home:
        assert result.returncode == 0, result.stderr
        assert f"cd {box.lane_dir}" in result.stderr
        assert "Evidence 7" in result.stderr
    else:
        assert result.returncode == 2, result.stderr
        assert "nothing was started" in result.stderr


@pytest.mark.parametrize("workspace", ["wip", "brett-wip", "personal-register"])
@pytest.mark.parametrize("command", ["park", "resume", "status"])
def test_workspace_lane_collections_do_not_ambiguate_origin_lookup(tmp_path, workspace, command):
    home = tmp_path / "home"; home.mkdir()
    projects = home / "projects"
    root = probe_project(projects, workspace)
    lane = probe_project(projects / (workspace + "-lanes"), "repoA-1")
    (projects / "register-checkouts").symlink_to(lane.parent, target_is_directory=True)
    slug = "tester/" + workspace
    for checkout in (root, lane):
        subprocess.run(["git", "init", "-q", str(checkout)], check=True)
        subprocess.run(["git", "-C", str(checkout), "remote", "add", "origin", "https://github.com/" + slug + ".git"], check=True)
    result = run(REPO / command, "--repo", slug, home=home)
    assert "multiple development checkouts" not in result.stderr
    assert str(lane) not in result.stdout + result.stderr
    if command == "park":
        assert result.returncode == 0, result.stderr + result.stdout
        assert f"PROBE park in {root}" in result.stdout


def test_workspace_lane_collections_are_not_swept(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    projects = home / "projects"
    root = sweepable_project(projects, "wip")
    lane = sweepable_project(projects / "wip-lanes", "repoA-1")
    (projects / "register-checkouts").symlink_to(lane.parent, target_is_directory=True)
    result = run(REPO / "park", "--all", home=home)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"PROBE park in {root}" in result.stdout
    assert str(lane) not in result.stdout + result.stderr
    assert "1 estate(s) parked" in result.stdout


@pytest.mark.parametrize("physical_name", ["Atlas", "estate-data"])
def test_family_container_alias_does_not_expose_members(tmp_path, physical_name):
    home = tmp_path / "home"; home.mkdir()
    alias, holder = logical_family_aliases(home, tmp_path / "storage", "Atlas")
    physical = holder.parent
    if physical_name != physical.name:
        renamed = physical.with_name(physical_name)
        physical.rename(renamed)
        for link in (home / "projects" / "Atlas", home / "projects" / "000-invalid", home / "projects" / "group" / "Atlas"):
            link.unlink()
            link.symlink_to(renamed, target_is_directory=True)
        physical = renamed
    probe_project(physical, "Alpha")
    found = rows(home / "projects")
    assert "Atlas" in [row[0] for row in found]
    assert "Alpha" not in [row[0] for row in found]


@pytest.mark.parametrize("command", ["park", "status"])
def test_family_container_boundaries_span_both_projects_roots(tmp_path, command):
    home = tmp_path / "home"; home.mkdir()
    alias, holder = logical_family_aliases(home, tmp_path / "storage", "Atlas")
    other = home / "Projects"; other.mkdir()
    (home / "projects" / "000-invalid").rename(other / "000-invalid")
    sweepable_project(holder.parent, "Alpha")
    result = run(REPO / command, "--all", home=home)
    assert "Alpha" not in result.stdout + result.stderr
    if command == "park":
        assert result.returncode == 0, result.stderr + result.stdout
        assert result.stdout.count("PROBE park in ") == 1
    else:
        # The deliberately uncommitted probe holder has findings; enumeration
        # must still contain only the family, never its sibling as an estate.
        assert result.returncode == 1, result.stderr + result.stdout
        assert result.stdout.count("=== status Atlas ===") == 1
        assert "1 with findings" in result.stdout
