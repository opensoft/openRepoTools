# SPDX-License-Identifier: Apache-2.0
"""Contract tests for read-only managed Claude profile resolution.

The profile fixture contains only synthetic metadata and temporary directories.
No test in this module invokes a launcher, reads credentials, or talks to a
live provider.  The implementation is intentionally added after these tests;
importing it is expected to fail until that implementation lands.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lane_managed_profiles import (
    ProfileError,
    ProfileReference,
    ProfileResolver,
    sanitize_environment,
)


def _entry(fixture, name: str) -> dict:
    """Return a copy of one fixture manifest entry."""
    for entry in fixture.entries:
        if entry["name"] == name:
            return dict(entry)
    raise AssertionError(f"fixture has no profile {name!r}")


def _write_manifest(fixture, entries: list[dict], path: Path | None = None) -> Path:
    target = path or fixture.manifest
    target.write_text(
        json.dumps({"version": 1, "profiles": entries}), encoding="utf-8"
    )
    return target


def _profile_dir(fixture, name: str) -> Path:
    entry = _entry(fixture, name)
    nested = fixture.profiles_home / "profiles" / Path(entry["profilePath"])
    if nested.is_dir():
        return nested
    return fixture.profiles_home / "profiles" / name


def _resolve(fixture, name: str, **kwargs):
    """Resolve through the public resolver with an isolated environment."""
    assert not kwargs, f"unexpected resolver options: {kwargs}"
    return ProfileResolver(env=dict(fixture.env)).resolve(name)


def _snapshot_tree(root: Path) -> dict[str, tuple]:
    """Capture temporary profile files without following symlink components."""
    result = {}
    for path in sorted(root.rglob("*")):
        info = os.lstat(path)
        mode = info.st_mode & 0o7777
        relative = str(path.relative_to(root))
        if path.is_symlink():
            result[relative] = ("symlink", mode, os.readlink(path))
        elif path.is_dir():
            result[relative] = ("directory", mode)
        elif path.is_file():
            result[relative] = ("file", mode, path.read_bytes())
    return result


def _workspace_project_key(workspace: Path) -> str:
    """Match Claude's conservative projects-directory spelling."""
    return "".join(
        character
        if (
            "A" <= character <= "Z"
            or "a" <= character <= "z"
            or "0" <= character <= "9"
        )
        else "-"
        for character in str(workspace).replace("\\", "/")
    )


def _current_process_start_token(pid: int) -> str | None:
    """Read the same portable process-incarnation identity as the resolver."""
    try:
        raw = Path("/proc/%d/stat" % pid).read_text(encoding="utf-8")
        suffix = raw.rsplit(")", 1)[-1].split()
        if len(suffix) > 19 and suffix[19].isdigit():
            return suffix[19]
    except (OSError, UnicodeError, ValueError):
        pass
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True,
            check=False,
            timeout=1.0,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[0] if len(lines) == 1 else None


def _current_process_domain() -> str | None:
    """Return the native Linux process-domain token, when the host exposes it."""
    try:
        machine_id = Path("/etc/machine-id").read_text(encoding="utf-8").strip()
        namespace = os.readlink("/proc/self/ns/pid")
    except (OSError, UnicodeError):
        return None
    if not machine_id or not namespace:
        return None
    return "linux:%s:%s" % (machine_id, namespace)


def _transcript_inputs(
    managed_profiles,
    tmp_path: Path,
    *,
    session_id: str = "11111111-1111-4111-8111-111111111111",
    profile_name: str = "team-a",
    shared_projects: bool = False,
    with_transcript: bool = True,
):
    """Create only native on-disk inputs for ``ProfileResolver.verify_transcript``."""
    resolver = ProfileResolver(env=dict(managed_profiles.env))
    profile = resolver.resolve(profile_name)
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    workspace.chmod(0o700)

    if shared_projects:
        shared_root = managed_profiles.profiles_home / "shared" / profile.family
        shared_root.mkdir(parents=True, mode=0o700)
        for parent in (managed_profiles.profiles_home / "shared", shared_root):
            parent.chmod(0o700)
        store = shared_root / "projects"
        store.mkdir(mode=0o700)
        store.chmod(0o700)
        for name in ("team-a", "team-b"):
            ref = resolver.resolve(name)
            projects_link = ref.config_dir / "projects"
            assert not projects_link.exists() and not projects_link.is_symlink()
            projects_link.symlink_to(store, target_is_directory=True)
    else:
        store = profile.config_dir / "projects"
        store.mkdir(mode=0o700)
        store.chmod(0o700)

    project = store / _workspace_project_key(workspace)
    project.mkdir(mode=0o700)
    project.chmod(0o700)
    transcript = project / (session_id + ".jsonl")
    if with_transcript:
        transcript.write_text('{"type":"user"}\n', encoding="utf-8")
        transcript.chmod(0o600)
    return resolver, profile, session_id, workspace, {
        "store": store.resolve(),
        "project": project.resolve(),
        "transcript": transcript,
    }


def _write_native_holder(
    profile: ProfileReference,
    session_id: str,
    workspace: Path,
    *,
    pid: int,
    proc_start: str,
    pid_domain: str,
    filename: str = "holder.json",
    version: int = 1,
) -> Path:
    """Write exactly the native holder shape; no managed participant ID."""
    sessions = profile.config_dir / "sessions"
    sessions.mkdir(mode=0o700, exist_ok=True)
    sessions.chmod(0o700)
    holder = sessions / filename
    holder.write_text(
        json.dumps(
            {
                "pid": pid,
                "procStart": proc_start,
                "pidDomain": pid_domain,
                "sessionId": session_id,
                "cwd": str(workspace),
                "version": version,
            }
        ),
        encoding="utf-8",
    )
    holder.chmod(0o600)
    return holder


def _verify_transcript(
    resolver: ProfileResolver,
    profile: ProfileReference,
    session_id: str,
    workspace: Path,
):
    """Call the exact resolver seam with a resolved ``ProfileReference``."""
    return resolver.verify_transcript(profile, session_id, workspace)


def test_manifest_override_wins_and_preserves_canonical_identity(managed_profiles, tmp_path):
    """An explicit manifest path is authoritative over the default manifest."""
    override = _entry(managed_profiles, "team-a")
    override["email"] = "override@example.invalid"
    override_path = _write_manifest(
        managed_profiles, [override], tmp_path / "override.json"
    )
    env = dict(managed_profiles.env)
    env["CLAUDE_PROFILES_MANIFEST"] = str(override_path)

    profile = ProfileResolver(env=env).resolve("TEAM-A")

    assert isinstance(profile, ProfileReference)
    assert profile.name == "team-a"
    assert profile.email == "override@example.invalid"
    assert profile.family == "family-a"
    assert profile.authentication == {"type": "subscription_oauth"}
    assert profile.status == "active"
    assert Path(profile.config_dir) == _profile_dir(managed_profiles, "team-a")
    assert Path(profile.metadata_path) == Path(profile.config_dir) / ".profile.json"


def test_default_manifest_path_is_used_without_override(managed_profiles):
    """The XDG config location is used when no manifest override is set."""
    env = dict(managed_profiles.env)
    del env["CLAUDE_PROFILES_MANIFEST"]

    profile = ProfileResolver(env=env).resolve("team-a")

    assert profile.name == "team-a"
    assert profile.email == "a@example.invalid"
    assert profile.authentication == {"type": "subscription_oauth"}
    assert profile.status == "active"
    assert Path(profile.config_dir) == _profile_dir(managed_profiles, "team-a")


def test_profile_metadata_is_fallback_when_manifest_is_unavailable(managed_profiles):
    """A configured profile remains resolvable from its local metadata."""
    metadata_path = _profile_dir(managed_profiles, "team-a") / ".profile.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["email"] = "fallback@example.invalid"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    env = dict(managed_profiles.env)
    env["CLAUDE_PROFILES_MANIFEST"] = str(
        managed_profiles.manifest.parent / "does-not-exist.json"
    )
    profile = ProfileResolver(env=env).resolve("team-a")

    assert profile.name == "team-a"
    assert profile.email == "fallback@example.invalid"
    assert profile.family == "family-a"
    assert Path(profile.config_dir) == _profile_dir(managed_profiles, "team-a")


@pytest.mark.parametrize("missing", ["email", "family"])
def test_fallback_metadata_requires_account_identity_fields(managed_profiles, missing):
    """Local fallback metadata cannot omit the account or transcript family."""
    metadata_path = _profile_dir(managed_profiles, "team-a") / ".profile.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    del metadata[missing]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    env = dict(managed_profiles.env)
    env["CLAUDE_PROFILES_MANIFEST"] = str(
        managed_profiles.manifest.parent / "does-not-exist.json"
    )

    with pytest.raises(ProfileError, match=missing):
        ProfileResolver(env=env).resolve("team-a")


def test_canonical_name_and_alias_are_case_insensitive_but_exact(managed_profiles):
    """Names and aliases case-fold, while prefixes do not select a profile."""
    canonical = _resolve(
        managed_profiles,
        "TeAm-A",
    )
    alias = _resolve(
        managed_profiles,
        "TEAMB",
    )

    assert canonical.name == "team-a"
    assert alias.name == "team-b"
    with pytest.raises(ProfileError, match="unknown|not found"):
        _resolve(
            managed_profiles,
            "team",
        )


def test_missing_profile_refuses_without_fallback_to_a_similar_name(managed_profiles):
    """A misspelled or absent profile cannot select a nearby canonical name."""
    with pytest.raises(ProfileError, match="unknown|not found|missing"):
        _resolve(managed_profiles, "team-a-typo")


def test_ambiguous_canonical_name_or_alias_refuses(managed_profiles):
    """Case-folding may not turn two manifest owners into one target."""
    team_b = _entry(managed_profiles, "team-b")
    team_b["aliases"] = [*team_b["aliases"], "TEAMa"]
    entries = [_entry(managed_profiles, name) for name in (
        "team-a", "team-b", "other-family", "setup-token"
    )]
    entries[1] = team_b
    _write_manifest(managed_profiles, entries)

    with pytest.raises(ProfileError, match="ambiguous|duplicate|alias"):
        _resolve(managed_profiles, "teama")


def test_inactive_profile_refuses_before_config_is_selected(managed_profiles):
    """Manifest status is an explicit eligibility gate, not a hint."""
    inactive = _entry(managed_profiles, "team-a")
    inactive["status"] = "inactive"
    entries = [_entry(managed_profiles, name) for name in (
        "team-a", "team-b", "other-family", "setup-token"
    )]
    entries[0] = inactive
    _write_manifest(managed_profiles, entries)

    with pytest.raises(ProfileError, match="inactive|disabled|unavailable"):
        _resolve(managed_profiles, "team-a")


@pytest.mark.parametrize("missing", ["email", "family"])
def test_expected_account_identity_fields_are_required(managed_profiles, missing):
    """A profile without its account email or storage family is unusable."""
    broken = _entry(managed_profiles, "team-a")
    del broken[missing]
    entries = [_entry(managed_profiles, name) for name in (
        "team-a", "team-b", "other-family", "setup-token"
    )]
    entries[0] = broken
    _write_manifest(managed_profiles, entries)

    with pytest.raises(ProfileError, match=missing):
        _resolve(managed_profiles, "team-a")


def test_same_family_target_is_required(managed_profiles):
    """A target in another transcript family is refused without mutation."""
    resolver = ProfileResolver(env=dict(managed_profiles.env))
    source = resolver.resolve("team-a")
    same_family = resolver.resolve("team-b")
    other_family = resolver.resolve("other-family")

    resolver.require_same_family(source, same_family)
    with pytest.raises(ProfileError, match="family|mismatch|incompatible"):
        resolver.require_same_family(source, other_family)


def test_setup_token_authentication_is_unsupported(managed_profiles):
    """Managed restore accepts subscription OAuth metadata only."""
    with pytest.raises(ProfileError, match="setup.?token|unsupported"):
        _resolve(managed_profiles, "setup-token")


def test_manifest_profile_path_prefers_the_nested_config_directory(managed_profiles):
    """A valid manifest path resolves below the profiles home, not by name alone."""
    profile = _resolve(managed_profiles, "team-a")

    expected = (
        managed_profiles.profiles_home
        / "profiles"
        / "family-a"
        / "team"
        / "team-a"
    )
    assert Path(profile.config_dir) == expected
    assert Path(profile.config_dir).is_dir()


def test_metadata_fallback_finds_a_flat_profile_when_manifest_path_is_stale(
    managed_profiles,
):
    """A flat configured profile can be found from its local identity metadata."""
    env = dict(managed_profiles.env)
    env["CLAUDE_PROFILES_MANIFEST"] = str(
        managed_profiles.manifest.parent / "missing-manifest.json"
    )
    profile = ProfileResolver(env=env).resolve("TEAMB")

    assert profile.name == "team-b"
    assert profile.email == "b@example.invalid"
    assert profile.family == "family-a"
    assert Path(profile.config_dir) == (
        managed_profiles.profiles_home / "profiles" / "team-b"
    )


def test_divergent_duplicate_metadata_fallback_is_ambiguous(managed_profiles):
    """Two local configs for one identity must not be guessed between."""
    duplicate = managed_profiles.profiles_home / "profiles" / "duplicate" / "team-a"
    duplicate.mkdir(parents=True, mode=0o700)
    (duplicate / ".profile.json").write_text(
        json.dumps(
            {
                "name": "team-a",
                "email": "different@example.invalid",
                "family": "family-a",
                "aliases": ["teama"],
            }
        ),
        encoding="utf-8",
    )
    env = dict(managed_profiles.env)
    env["CLAUDE_PROFILES_MANIFEST"] = str(
        managed_profiles.manifest.parent / "missing-manifest.json"
    )

    with pytest.raises(ProfileError, match="ambiguous|duplicate"):
        ProfileResolver(env=env).resolve("team-a")


@pytest.mark.parametrize(
    "unsafe_profile_path",
    ["../outside", "../../outside", "/outside"],
)
def test_profile_path_traversal_or_absolute_path_refuses(
    managed_profiles, unsafe_profile_path
):
    """Manifest paths are lexical and physical boundaries, not trusted input."""
    broken = _entry(managed_profiles, "team-a")
    broken["profilePath"] = unsafe_profile_path
    entries = [_entry(managed_profiles, name) for name in (
        "team-a", "team-b", "other-family", "setup-token"
    )]
    entries[0] = broken
    _write_manifest(managed_profiles, entries)

    with pytest.raises(ProfileError, match="path|traversal|outside|boundary|unsafe"):
        _resolve(managed_profiles, "team-a")


def test_profile_path_symlink_component_refuses(managed_profiles):
    """A profile path must not cross a symlink, even when its target is readable."""
    outside = managed_profiles.profiles_home.parent / "outside-profile"
    outside_profile = outside / "team-a"
    outside_profile.mkdir(parents=True, mode=0o700)
    (outside_profile / ".profile.json").write_text(
        json.dumps(
            {
                "name": "team-a",
                "email": "a@example.invalid",
                "family": "family-a",
                "aliases": ["teama"],
            }
        ),
        encoding="utf-8",
    )
    link = managed_profiles.profiles_home / "profiles" / "linked"
    link.symlink_to(outside, target_is_directory=True)
    broken = _entry(managed_profiles, "team-a")
    broken["profilePath"] = "linked/team-a"
    entries = [_entry(managed_profiles, name) for name in (
        "team-a", "team-b", "other-family", "setup-token"
    )]
    entries[0] = broken
    _write_manifest(managed_profiles, entries)

    with pytest.raises(ProfileError, match="symlink|link|path|unsafe"):
        _resolve(managed_profiles, "team-a")


def test_missing_profile_config_refuses_without_metadata_guess(managed_profiles):
    """A manifest target with no config metadata is not silently reconstructed."""
    missing = managed_profiles.profiles_home / "profiles" / "missing" / "team-a"
    missing.mkdir(parents=True, mode=0o700)
    broken = _entry(managed_profiles, "team-a")
    broken["profilePath"] = "missing/team-a"
    entries = [_entry(managed_profiles, name) for name in (
        "team-a", "team-b", "other-family", "setup-token"
    )]
    entries[0] = broken
    _write_manifest(managed_profiles, entries)

    with pytest.raises(ProfileError, match="config|metadata|profile|not configured"):
        _resolve(managed_profiles, "team-a")


def test_sanitized_environment_removes_inherited_auth_and_provider_overrides(
    managed_profiles,
):
    """Only the selected existing config directory supplies profile context."""
    profile = _resolve(
        managed_profiles,
        "team-a",
    )
    source = {
        "PATH": "/usr/bin",
        "HOME": "/tmp/fake-home",
        "KEEP_ME": "unrelated",
        "ANTHROPIC_API_KEY": "api-key-must-not-leak",
        "ANTHROPIC_AUTH_TOKEN": "auth-token-must-not-leak",
        "CLAUDE_CODE_OAUTH_TOKEN": "oauth-token-must-not-leak",
        "ANTHROPIC_BASE_URL": "https://provider.invalid",
        "ANTHROPIC_API_URL": "https://api.invalid",
        "CLAUDE_CODE_USE_BEDROCK": "1",
        "CLAUDE_CODE_USE_VERTEX": "1",
        "CLAUDE_CODE_PROVIDER": "provider-override",
        "CLAUDE_PROVIDER": "provider-override",
        "CLAUDE_CONFIG_DIR": "/tmp/wrong-profile",
    }

    sanitized = sanitize_environment(source, profile)

    assert sanitized is not source
    for forbidden in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_URL",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_PROVIDER",
        "CLAUDE_PROVIDER",
    ):
        assert forbidden not in sanitized
    assert sanitized["PATH"] == "/usr/bin"
    assert sanitized["HOME"] == "/tmp/fake-home"
    assert sanitized["KEEP_ME"] == "unrelated"
    assert sanitized["CLAUDE_CONFIG_DIR"] == str(profile.config_dir)
    assert source["CLAUDE_CONFIG_DIR"] == "/tmp/wrong-profile"


def test_profile_resolution_and_environment_sanitization_are_read_only(
    managed_profiles,
):
    """Resolver calls do not modify manifests, metadata, modes, or input env."""
    manifest_snapshot = _snapshot_tree(managed_profiles.manifest.parent)
    profiles_snapshot = _snapshot_tree(managed_profiles.profiles_home)
    source = {"KEEP_ME": "unchanged", "CLAUDE_CONFIG_DIR": "wrong"}
    source_snapshot = dict(source)

    profile = _resolve(managed_profiles, "team-a")
    sanitized = sanitize_environment(source, profile)

    assert sanitized["KEEP_ME"] == "unchanged"
    assert source == source_snapshot
    assert _snapshot_tree(managed_profiles.manifest.parent) == manifest_snapshot
    assert _snapshot_tree(managed_profiles.profiles_home) == profiles_snapshot


def test_credentials_are_neither_copied_nor_logged(managed_profiles, capsys):
    """Credential-looking files remain untouched and secret bytes stay private."""
    token = "synthetic-oauth-token-never-copy-or-log"
    credential_file = _profile_dir(managed_profiles, "team-a") / "credentials.json"
    credential_file.write_text(token, encoding="utf-8")
    before = _snapshot_tree(managed_profiles.profiles_home)

    profile = _resolve(managed_profiles, "team-a")
    sanitize_environment({"KEEP_ME": "yes"}, profile)
    captured = capsys.readouterr()

    assert token not in captured.out
    assert token not in captured.err
    assert token not in repr(profile)
    assert _snapshot_tree(managed_profiles.profiles_home) == before


def test_verify_transcript_accepts_exact_regular_resume_and_canonical_store_workspace(
    managed_profiles, tmp_path
):
    """Resume requires the exact regular transcript and canonical bindings."""
    resolver, profile, session_id, workspace, paths = _transcript_inputs(
        managed_profiles, tmp_path
    )

    evidence = _verify_transcript(resolver, profile, session_id, workspace)

    assert evidence["profile"]["name"] == profile.name
    assert evidence["profile"]["email"] == "a@example.invalid"
    assert evidence["profile"]["family"] == profile.family
    assert evidence["session_id"] == session_id
    assert evidence["workspace"] == str(workspace)
    assert evidence["transcript_store"] == str(paths["store"])
    assert evidence["transcript_project"] == str(paths["project"])
    assert evidence["transcript"]["session_id"] == session_id
    assert evidence["transcript"]["path"] == str(paths["transcript"])
    assert evidence["transcript"]["exists"] is True
    assert evidence["transcript"]["written"] is True
    assert evidence["transcript"]["regular"] is True
    assert evidence["transcript"]["private"] is True
    assert evidence["holders"] == []
    assert evidence["unknown_holders"] == []
    assert evidence["ambiguous"] is False


def test_verify_transcript_accepts_no_holder_reserved_fresh(
    managed_profiles, tmp_path
):
    """A never-written fixed UUID with no holder is a valid fresh reservation."""
    resolver, profile, session_id, workspace, paths = _transcript_inputs(
        managed_profiles, tmp_path, with_transcript=False
    )

    evidence = _verify_transcript(resolver, profile, session_id, workspace)

    assert evidence["profile"]["email"] == "a@example.invalid"
    assert evidence["session_id"] == session_id
    assert evidence["workspace"] == str(workspace)
    assert evidence["transcript_store"] == str(paths["store"])
    assert evidence["transcript_project"] == str(paths["project"])
    assert evidence["transcript"]["session_id"] == session_id
    assert evidence["transcript"]["path"] is None
    assert evidence["transcript"]["exists"] is False
    assert evidence["transcript"]["written"] is False
    assert evidence["transcript"]["reserved"] is True
    assert evidence["transcript"]["mode"] == "fresh"
    assert evidence["holders"] == []
    assert evidence["unknown_holders"] == []
    assert evidence["ambiguous"] is False


def test_verify_transcript_refuses_written_missing_transcript(
    managed_profiles, tmp_path
):
    """A matching native record prevents an absent UUID from becoming fresh."""
    resolver, profile, session_id, workspace, paths = _transcript_inputs(
        managed_profiles, tmp_path, with_transcript=False
    )
    _write_native_holder(
        profile,
        session_id,
        workspace,
        pid=2**31 - 1,
        proc_start="stale-start-token",
        pid_domain=_current_process_domain() or "linux:test-machine-id:pid:[0]",
    )

    with pytest.raises(ProfileError) as caught:
        _verify_transcript(resolver, profile, session_id, workspace)
    assert caught.value.code == "unknown"
    assert "proven" in str(caught.value).casefold() or "unknown" in str(caught.value).casefold()


def test_verify_transcript_accepts_same_domain_dead_holder_for_resume(
    managed_profiles, tmp_path
):
    """A verified local-domain ESRCH holder is stale when its transcript exists."""
    resolver, profile, session_id, workspace, paths = _transcript_inputs(
        managed_profiles, tmp_path
    )
    process_domain = _current_process_domain()
    if process_domain is None:
        pytest.skip("the host exposes no native Linux process-domain token")
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(0.1)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        process_start = _current_process_start_token(child.pid)
        child.wait(timeout=5)
        if process_start is None:
            pytest.skip("the host exposes no portable child-process start token")
        _write_native_holder(
            profile,
            session_id,
            workspace,
            pid=child.pid,
            proc_start=process_start,
            pid_domain=process_domain,
        )

        evidence = _verify_transcript(resolver, profile, session_id, workspace)

        assert evidence["transcript"]["exists"] is True
        assert evidence["transcript"]["written"] is True
        assert evidence["transcript"]["mode"] == "resume"
        assert evidence["holders"] == []
        assert evidence["unknown_holders"] == []
        assert evidence["ambiguous"] is False
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


@pytest.mark.parametrize("mutation", ["symlink", "permissions"])
def test_verify_transcript_refuses_unsafe_transcript_file(
    managed_profiles, tmp_path, mutation
):
    """A transcript must be a private regular file, never an alias or leak."""
    resolver, profile, session_id, workspace, paths = _transcript_inputs(
        managed_profiles, tmp_path
    )
    if mutation == "symlink":
        outside = tmp_path / "outside-transcript.jsonl"
        outside.write_text('{"type":"user"}\n', encoding="utf-8")
        outside.chmod(0o600)
        paths["transcript"].unlink()
        paths["transcript"].symlink_to(outside)
    else:
        paths["transcript"].chmod(0o644)

    with pytest.raises(ProfileError) as caught:
        _verify_transcript(resolver, profile, session_id, workspace)
    assert caught.value.code == "invalid"
    assert any(
        word in str(caught.value).casefold()
        for word in ("symlink", "link", "permission", "mode", "regular", "private")
    )


def test_verify_transcript_refuses_ambiguous_same_family_stores(
    managed_profiles, tmp_path
):
    """Two same-family canonical stores are ambiguous, not a selection hint."""
    resolver, profile, session_id, workspace, paths = _transcript_inputs(
        managed_profiles, tmp_path
    )
    sibling = resolver.resolve("team-b")
    sibling_projects = sibling.config_dir / "projects"
    sibling_projects.mkdir(mode=0o700)
    sibling_projects.chmod(0o700)
    sibling_project = sibling_projects / _workspace_project_key(workspace)
    sibling_project.mkdir(mode=0o700)
    sibling_project.chmod(0o700)
    sibling_transcript = sibling_project / (session_id + ".jsonl")
    sibling_transcript.write_text('{"type":"user"}\n', encoding="utf-8")
    sibling_transcript.chmod(0o600)
    # The selected profile's projects store and a same-family sibling store
    # are both real canonical stores; neither public field can select one.
    selected_store = profile.config_dir / "projects"
    selected_project = selected_store / _workspace_project_key(workspace)
    selected_project_transcript = selected_project / (session_id + ".jsonl")
    assert selected_store.resolve() == paths["store"]
    assert selected_project_transcript == paths["transcript"]

    with pytest.raises(ProfileError) as caught:
        _verify_transcript(resolver, profile, session_id, workspace)
    assert caught.value.code == "invalid"
    assert any(
        word in str(caught.value).casefold()
        for word in ("ambiguous", "multiple", "store", "canonical")
    )


def test_verify_transcript_accepts_exact_source_holder_during_target_preflight(
    managed_profiles, tmp_path
):
    """A managed source holder is evidence, not a target-profile conflict."""
    resolver, target, session_id, workspace, paths = _transcript_inputs(
        managed_profiles,
        tmp_path,
        profile_name="team-b",
        shared_projects=True,
    )
    source = resolver.resolve("team-a")
    process_start = _current_process_start_token(os.getpid())
    process_domain = _current_process_domain()
    if process_start is None or process_domain is None:
        pytest.skip("the host exposes no portable native process identity")
    _write_native_holder(
        source,
        session_id,
        workspace,
        pid=os.getpid(),
        proc_start=process_start,
        pid_domain=process_domain,
    )

    evidence = _verify_transcript(resolver, target, session_id, workspace)

    assert evidence["profile"]["name"] == "team-b"
    assert evidence["profile"]["email"] == "b@example.invalid"
    assert evidence["transcript_store"] == str(paths["store"])
    assert evidence["transcript_project"] == str(paths["project"])
    assert len(evidence["holders"]) == 1
    holder = evidence["holders"][0]
    assert holder["profile_name"] == "team-a"
    assert holder["session_id"] == session_id
    assert holder["pid"] == os.getpid()
    assert holder["process_start_token"] == process_start
    assert holder["workspace"] == str(workspace)
    assert holder["projects_store"] == str(paths["store"])
    assert "participant_id" not in holder


@pytest.mark.parametrize("same_start_token", [True, False])
def test_verify_transcript_refuses_foreign_pid_domain(
    managed_profiles, tmp_path, same_start_token
):
    """A live PID in a foreign domain is unknown even when its token matches."""
    resolver, profile, session_id, workspace, _paths = _transcript_inputs(
        managed_profiles, tmp_path
    )
    process_start = _current_process_start_token(os.getpid())
    if process_start is None:
        pytest.skip("the host exposes no portable current-process start token")
    _write_native_holder(
        profile,
        session_id,
        workspace,
        pid=os.getpid(),
        proc_start=process_start if same_start_token else "different-start-token",
        pid_domain="linux:foreign-machine-id:pid:[999999]",
    )

    with pytest.raises(ProfileError) as caught:
        _verify_transcript(resolver, profile, session_id, workspace)
    assert caught.value.code == "unknown"
    assert "domain" in str(caught.value).casefold() or "holder" in str(caught.value).casefold()


def test_verify_transcript_refuses_inaccessible_pid_domain_as_unknown(
    managed_profiles, tmp_path
):
    """An unobservable process domain is not stale/absent proof."""
    resolver, profile, session_id, workspace, _paths = _transcript_inputs(
        managed_profiles, tmp_path
    )
    _write_native_holder(
        profile,
        session_id,
        workspace,
        pid=2**31 - 1,
        proc_start="unobservable-start-token",
        pid_domain="linux:foreign-machine-id:pid:[999998]",
    )

    with pytest.raises(ProfileError) as caught:
        _verify_transcript(resolver, profile, session_id, workspace)
    assert caught.value.code == "unknown"
    assert any(
        word in str(caught.value).casefold()
        for word in ("domain", "observable", "holder", "process", "unknown")
    )


def test_verify_transcript_refuses_extra_ambiguous_native_holder(
    managed_profiles, tmp_path
):
    """Two live native records for one UUID are an ownership conflict."""
    resolver, profile, session_id, workspace, _paths = _transcript_inputs(
        managed_profiles, tmp_path
    )
    parent_start = _current_process_start_token(os.getpid())
    process_domain = _current_process_domain()
    if parent_start is None or process_domain is None:
        pytest.skip("the host exposes no portable native process identity")
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        child_start = _current_process_start_token(child.pid)
        if child_start is None:
            pytest.skip("the host exposes no portable child-process start token")
        _write_native_holder(
            profile,
            session_id,
            workspace,
            pid=os.getpid(),
            proc_start=parent_start,
            pid_domain=process_domain,
            filename="holder-a.json",
        )
        _write_native_holder(
            profile,
            session_id,
            workspace,
            pid=child.pid,
            proc_start=child_start,
            pid_domain=process_domain,
            filename="holder-b.json",
        )

        with pytest.raises(ProfileError) as caught:
            _verify_transcript(resolver, profile, session_id, workspace)
        assert caught.value.code == "ownership-conflict"
        assert "holder" in str(caught.value).casefold()
    finally:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def test_verify_transcript_refuses_duplicate_native_holder_identity(
    managed_profiles, tmp_path
):
    """Duplicate live records for one native holder remain ambiguous."""
    resolver, profile, session_id, workspace, _paths = _transcript_inputs(
        managed_profiles, tmp_path
    )
    process_start = _current_process_start_token(os.getpid())
    process_domain = _current_process_domain()
    if process_start is None or process_domain is None:
        pytest.skip("the host exposes no portable native process identity")
    holder_kwargs = {
        "pid": os.getpid(),
        "proc_start": process_start,
        "pid_domain": process_domain,
    }
    _write_native_holder(
        profile, session_id, workspace, filename="holder-a.json", **holder_kwargs
    )
    _write_native_holder(
        profile, session_id, workspace, filename="holder-b.json", **holder_kwargs
    )

    with pytest.raises(ProfileError) as caught:
        _verify_transcript(resolver, profile, session_id, workspace)
    assert caught.value.code == "ownership-conflict"
    assert "holder" in str(caught.value).casefold()


def test_verify_transcript_does_not_trust_inline_authority_fields(
    managed_profiles, tmp_path
):
    """Metadata trust flags cannot replace native transcript/process proof."""
    resolver, profile, session_id, workspace, paths = _transcript_inputs(
        managed_profiles, tmp_path, with_transcript=False
    )
    metadata_path = profile.config_dir / ".profile.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({"trusted": True, "authoritative": True})
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    metadata_path.chmod(0o600)
    _write_native_holder(
        profile,
        session_id,
        workspace,
        pid=2**31 - 1,
        proc_start="unobservable-start-token",
        pid_domain=_current_process_domain() or "linux:test-machine-id:pid:[0]",
    )

    with pytest.raises(ProfileError) as caught:
        _verify_transcript(resolver, profile, session_id, workspace)
    assert caught.value.code == "unknown"
    assert "proven" in str(caught.value).casefold() or "unknown" in str(caught.value).casefold()
