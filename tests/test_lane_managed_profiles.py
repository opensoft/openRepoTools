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
