# SPDX-License-Identifier: Apache-2.0
"""`--install`'s three artifacts that are not one of the nine files.

lane-collision-protocol Amendment 9(b), inheriting A8 Addendum 2's R-A8-5
unvaried — the skill into the SHARED skills directory every profile reads
through its own symlink, a copy into `~/.claude` for a bare `claude` run
outside the launcher, and ONE merged entry in `~/.claude/settings.json`.

WHY THE HOOK IS THE HARD ONE, and why most of this file is about it. Every
other thing `--install` places is a whole file, so "already there and
identical" is a `cmp`. The hook is one entry inside a file somebody else owns
and two other programs also write, and its ONLY idempotence is an exact match
on the command string. So the tests below are about the four answers that
string can have — present, absent, differing, unreadable — and about the one
rule that makes a wrong answer survivable: the merge is computed with the nine
files in hand, BEFORE any of them is placed, so a refusal costs a whole install
rather than half of one.

NO NETWORK: every run here is from the checkout, so nothing is fetched at all.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from test_openrepotools_command import (COMMAND, command_env, run_cmd,
                                        INSTALLED, NEEDS_JQ, SKILL_PATH)

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="openRepoTools is a bash script"),
              WINDOWS_SKIP]

#: The hook entry, byte for byte Amendment 8 clause (e)'s and byte for byte
#: what opensoft/workBenches#63's launcher ensures in each profile. Spelled
#: once here and compared against the command's own copy, because two
#: spellings of a string whose only idempotence is exact match is one of them
#: being wrong — and because `--install` and the launcher write DIFFERENT
#: files, so nothing but the shared string keeps an exact-match ensure from
#: treating one as absent.
HOOK_COMMAND = "~/projects/xFactory/lanes-edit.sh session-start || true"
HOOK_MATCHER = "startup|resume|clear|fork"
HOOK_TIMEOUT = 5

def skill_paths(home: Path) -> tuple[Path, Path]:
    return (home / ".claude-profiles" / "shared" / "skills" / "lane-swap" / "SKILL.md",
            home / ".claude" / "skills" / "lane-swap" / "SKILL.md")


def settings_of(home: Path) -> Path:
    return home / ".claude" / "settings.json"


def session_start_commands(home: Path) -> list[str]:
    data = json.loads(settings_of(home).read_text(encoding="utf-8"))
    out = []
    for entry in data.get("hooks", {}).get("SessionStart", []):
        for hook in entry.get("hooks", []):
            if "command" in hook:
                out.append(hook["command"])
    return out


# --- the skill --------------------------------------------------------------

@NEEDS_JQ
def test_install_places_the_skill_at_both_paths(tmp_path):
    """ONE WRITE FOR 418 PROFILES, plus one for the bare run. Measured on Eagle
    2026-09-12: every `pclaude run` execs with `CLAUDE_CONFIG_DIR=<profile
    dir>`, and every profile's `skills` is a symlink to one shared directory —
    so `~/.claude/skills` is NOT read under the launcher and the shared
    directory is the one write that reaches all of them (R-A8-5(a)). The
    `~/.claude` copy stays for a bare `claude` run outside it (R-A8-5(c))."""
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    source = (REPO / SKILL_PATH).read_bytes()
    for target in skill_paths(tmp_path):
        assert target.is_file(), result.stdout
        assert target.read_bytes() == source, target
        assert stat.S_IMODE(target.stat().st_mode) == 0o644, target
        assert f"lane-swap: installed at {target}" in result.stdout


@NEEDS_JQ
def test_the_shipped_skill_is_the_one_the_launcher_invokes(tmp_path):
    """`/lane-swap` is what Claude Code invokes, and what it invokes is the
    skill's own `name:` (Addendum 1(3) on brettheap/new-workstation#17).
    A directory named one thing and a front-matter name that is another is a
    skill nobody can call."""
    text = (REPO / SKILL_PATH).read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "\nname: lane-swap\n" in text
    assert Path(SKILL_PATH).parent.name == "lane-swap"


@NEEDS_JQ
def test_a_drifted_skill_is_replaced_and_an_identical_one_is_left_alone(tmp_path):
    assert run_cmd("--install", home=tmp_path).returncode == 0
    shared, _bare = skill_paths(tmp_path)
    shared.write_text(shared.read_text(encoding="utf-8") + "\n<!-- drift -->\n",
                      encoding="utf-8")
    second = run_cmd("--install", home=tmp_path)
    assert second.returncode == 0, second.stderr
    assert f"lane-swap: updated at {shared}" in second.stdout
    assert shared.read_bytes() == (REPO / SKILL_PATH).read_bytes()


# --- the hook entry ---------------------------------------------------------

@NEEDS_JQ
def test_the_hook_entry_is_byte_identical_to_the_amendments(tmp_path):
    """THE STRING IS THE WHOLE MECHANISM. `--install` writes the user-local
    file and the launcher writes each profile's; the two never write one file,
    and only the shared string keeps an exact-match ensure from treating one as
    absent and adding a second entry that fires the hook twice (R-A9-4)."""
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    data = json.loads(settings_of(tmp_path).read_text(encoding="utf-8"))
    entries = data["hooks"]["SessionStart"]
    assert len(entries) == 1, entries
    assert entries[0]["matcher"] == HOOK_MATCHER
    assert entries[0]["hooks"] == [{"type": "command",
                                    "command": HOOK_COMMAND,
                                    "timeout": HOOK_TIMEOUT}]
    assert HOOK_COMMAND in COMMAND.read_text(encoding="utf-8"), (
        "the command string this test asserts on is the one the file writes")


@NEEDS_JQ
def test_the_merge_keeps_every_other_setting_and_the_mode(tmp_path):
    """IT NEVER WRITES THE FILE WHOLE. The file already carries a
    `UserPromptSubmit` hook (Amendment 8(e)) and a `statusLine` that
    workBenches' own `setup-claude-profiles.sh` writes on every `./setup.sh` —
    and a user's settings are not an installer's to own.

    MODE 600 IS PRESERVED for the same reason: that script writes this file
    through `jq` + `mktemp` + `chmod 600` + `mv -f`, so an installer that
    widened the mode would be silently undone, or would widen it behind that
    script's back.
    """
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({
        "statusLine": {"type": "command", "command": "~/.claude/statusline-command.sh"},
        "model": "opus",
        "hooks": {"UserPromptSubmit": [{"hooks": [
            {"type": "command", "command": "~/projects/xFactory/guard.sh", "timeout": 5}]}]},
    }, indent=2), encoding="utf-8")
    os.chmod(settings, 0o600)

    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["model"] == "opus"
    assert data["statusLine"]["command"] == "~/.claude/statusline-command.sh"
    assert data["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"] \
        == "~/projects/xFactory/guard.sh"
    assert session_start_commands(tmp_path) == [HOOK_COMMAND]
    assert stat.S_IMODE(settings.stat().st_mode) == 0o600
    assert "merged into" in result.stdout


@NEEDS_JQ
def test_installing_twice_adds_one_entry_and_not_two(tmp_path):
    assert run_cmd("--install", home=tmp_path).returncode == 0
    second = run_cmd("--install", home=tmp_path)
    assert second.returncode == 0, second.stderr
    assert session_start_commands(tmp_path) == [HOOK_COMMAND]
    assert "SessionStart hook: already installed" in second.stdout
    assert "unchanged" in second.stdout


@NEEDS_JQ
def test_a_differing_session_start_entry_refuses_and_places_nothing(tmp_path):
    """THE ENTRY INSTALLED BY HAND ON EAGLE DOES NOT MATCH, and refusing is the
    right outcome. Amendment 8's adoption act 6 placed
    `bash -lc '"$HOME/projects/xFactory/lanes-edit.sh" session-start
    2>/dev/null || true'` under the same matcher; its `command` is not clause
    (e)'s string, so merging would quietly add a SECOND entry and fire the hook
    twice.

    AND THE COST IS A WHOLE INSTALL, NOT HALF OF ONE: the merge is computed
    with the nine files in hand, before any of them is placed, so the bin
    directory is untouched. That is the same all-or-nothing rule `--install`
    already had, extended to the one artifact that is not a whole file.
    """
    hand = ('bash -lc \'"$HOME/projects/xFactory/lanes-edit.sh" session-start '
            '2>/dev/null || true\'')
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {"SessionStart": [
        {"matcher": HOOK_MATCHER,
         "hooks": [{"type": "command", "command": hand, "timeout": 5}]}]}}),
        encoding="utf-8")
    bin_dir = tmp_path / ".local" / "bin"

    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "a SessionStart entry that runs `session-start` with a" in result.stderr
    assert "DIFFERENT command string" in result.stderr
    assert "NOTHING was installed" in result.stderr
    assert HOOK_COMMAND in result.stderr, "the refusal prints the exact block"
    assert session_start_commands(tmp_path) == [hand], "it changed the file"
    assert not bin_dir.exists() or not any(bin_dir.iterdir()), (
        "the refusal must cost a whole install, not half of one")
    for target in skill_paths(tmp_path):
        assert not target.exists(), target


@NEEDS_JQ
def test_a_settings_file_that_is_not_json_refuses_and_places_nothing(tmp_path):
    """The same refusal workBenches' own writer of this file already makes
    (`setup-claude-profiles.sh` hard-exits 1 when it is not valid JSON). An
    installer that repairs a file it does not understand is how a person loses
    a setting they meant."""
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text("{ this is not json\n", encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "is not valid JSON" in result.stderr
    assert "NOTHING was installed" in result.stderr
    assert settings.read_text(encoding="utf-8") == "{ this is not json\n"
    assert not (tmp_path / ".local" / "bin").exists()


@NEEDS_JQ
def test_a_hooks_value_that_is_not_an_object_refuses(tmp_path):
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": ["not", "an", "object"]}),
                        encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "not an object" in result.stderr
    assert not (tmp_path / ".local" / "bin").exists()


@NEEDS_JQ
def test_an_unrelated_session_start_entry_is_kept_and_ours_is_added(tmp_path):
    """Somebody else's SessionStart hook is not ours to remove. Only an entry
    that runs `session-start` with a different string is a conflict — anything
    else is a setting a person meant, and this merges beside it."""
    other = "~/bin/say-hello.sh"
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {"SessionStart": [
        {"matcher": "startup",
         "hooks": [{"type": "command", "command": other, "timeout": 3}]}]}}),
        encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert session_start_commands(tmp_path) == [other, HOOK_COMMAND]


def test_without_jq_it_refuses_and_places_nothing(tmp_path):
    """`jq` IS A NEW DEPENDENCY AND THE TEXT NAMES IT rather than assuming it:
    this repository carried no JSON-handling code before the merge. It is not
    bash, so the macOS bash-3.2 parse gate is unaffected."""
    stub = tmp_path / "nojq"
    stub.mkdir()
    for name in ("bash", "git", "cp", "mkdir", "chmod", "cmp", "printf",
                 "mktemp", "sed", "cat", "tr", "grep", "head", "dirname",
                 "rm", "mv"):
        found = shutil.which(name)
        if found:
            (stub / name).symlink_to(found)
    result = subprocess.run(
        ["bash", str(COMMAND), "--install"], capture_output=True, text=True,
        check=False, input="", cwd=str(REPO),
        env=command_env(home=tmp_path, env={"PATH": str(stub)}))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "needs `jq`" in result.stderr
    assert HOOK_COMMAND in result.stderr, "the refusal prints the entry"
    assert not (tmp_path / ".local" / "bin").exists(), (
        "NOTHING was installed: the merge is computed before any file is placed")


# --- the destination, proved before anything is placed ----------------------

NOT_ROOT = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root may write a directory whose mode says otherwise")


@NEEDS_JQ
@NOT_ROOT
@pytest.mark.parametrize("which", ["shared skills", "~/.claude"])
def test_a_destination_that_cannot_be_written_refuses_before_anything_is_placed(
        tmp_path, which):
    """THE MERGE COMPUTING FINE AGAINST A DIRECTORY NOBODY MAY WRITE IS THE SAME
    FAILURE ONE STEP LATER.

    Amendment 9(b) computes the merge in hand "so a merge that cannot be
    computed refuses having placed nothing". A filesystem offers no transaction
    across twelve artifacts, so nothing can make the last three atomic with the
    first nine — but the failure that actually happens is not an exotic one, it
    is a directory that is not this installer's to write, and that question can
    be asked in the planning phase where the refusal still costs nothing.

    Without the check the run places nine files and two of the three remaining
    artifacts, then dies on the third — leaving a host with commands installed,
    no `SessionStart` entry, and an installer that reports the same "already
    installed (unchanged)" for the nine on every re-run while never reaching
    the one that failed.
    """
    if which == "shared skills":
        blocked = tmp_path / ".claude-profiles" / "shared" / "skills"
    else:
        blocked = tmp_path / ".claude"
    blocked.mkdir(parents=True)
    blocked.chmod(0o500)
    bin_dir = tmp_path / ".local" / "bin"
    try:
        result = run_cmd("--install", home=tmp_path)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "NOTHING was installed" in result.stderr
        assert not bin_dir.exists() or not any(bin_dir.iterdir()), (
            "nine files were placed against a destination that was never "
            "going to take the other three")
    finally:
        blocked.chmod(0o700)


@NEEDS_JQ
@NOT_ROOT
def test_a_leaf_destination_that_exists_and_is_unwritable_refuses(tmp_path):
    """THE `[ -w "$d" ]` ARM, WHICH NOTHING REACHED (F6 of the #24 review).

    Its sibling above chmods the PARENT 0500, so `mkdir -p` is what refuses and
    the writability test one line below it is never evaluated — the reviewer
    replaced that line with a no-op and the file stayed 13 passed. `mkdir -p`
    returns 0 on a directory that ALREADY EXISTS whatever its mode (measured),
    so the leaf existing at 0500 is the shape that reaches the guard: the
    directory is there, `mkdir -p` is happy, and nothing may be written into
    it. That is also the real-world shape — a skills directory somebody made
    read-only — rather than an unwritable parent, which would have broken the
    profile set long before `--install` ran.
    """
    leaf = tmp_path / ".claude-profiles" / "shared" / "skills" / "lane-swap"
    leaf.mkdir(parents=True)
    leaf.chmod(0o500)
    bin_dir = tmp_path / ".local" / "bin"
    try:
        result = run_cmd("--install", home=tmp_path)
        assert result.returncode == 2, result.stdout + result.stderr
        assert f"{leaf} is not writable" in result.stderr, (
            "the refusal must come from the -w guard, not from mkdir")
        assert "NOTHING was installed" in result.stderr
        assert not bin_dir.exists() or not any(bin_dir.iterdir())
        assert not (leaf / "SKILL.md").exists()
    finally:
        leaf.chmod(0o700)


# --- the nine targets, before any of the twelve is placed (R-A9-12) ---------

def plant_wip_checkout(tmp_path) -> Path:
    """The shape every workstation is in BEFORE Amendment 9's adoption act 6:
    `link-estates` put `lane-start` and `lane-end` in the bin directory as
    SYMLINKS into `opensoft/brett-wip`'s checkout, which is the repository
    every lane writes."""
    wip = tmp_path / "projects" / "brett-wip" / "lanes"
    wip.mkdir(parents=True)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    for name in ("lane-start", "lane-end"):
        source = wip / name
        source.write_text(f"#!/usr/bin/env bash\n# the pre-move {name}\n",
                          encoding="utf-8")
        (bin_dir / name).symlink_to(source)
    return wip


@NEEDS_JQ
def test_a_symlinked_target_refuses_and_the_checkout_it_points_at_is_untouched(tmp_path):
    """`cp` FOLLOWS A SYMLINK, AND THE THING ON THE OTHER END IS THE REGISTER
    REPOSITORY (R-A9-12, from F5 of the #24 review).

    Measured before the fix: `--install` printed `lane-start: updated at
    <bin>/lane-start`, `openRepoTools: 9 of 9 placed`, and exit 0 — while the
    two targets STAYED SYMLINKS (so the commands were not installed, and
    workBenches' `setup-estate-commands.sh:206-218` still refuses the whole
    estate install on them) and the post-move bytes landed inside
    `opensoft/brett-wip`'s worktree, where `lanes-edit.sh`'s
    `refuse_dirty_checkout` then refuses `log`, `claim` and `release` on that
    workstation.

    This is the NORMAL pre-act-5 state of both workstations, and the Raven
    sequence sends a person to type `--install` by hand — so the tool enforces
    act 6 step 1 rather than leaving it to a person to remember it.
    """
    wip = plant_wip_checkout(tmp_path)
    bin_dir = tmp_path / ".local" / "bin"
    before = {name: (wip / name).read_bytes() for name in ("lane-start", "lane-end")}

    result = run_cmd("--install", home=tmp_path)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "places REGULAR FILES" in result.stderr
    for name in ("lane-start", "lane-end"):
        target = bin_dir / name
        assert f"{target} — a symlink to {wip / name}" in result.stderr, (
            "the refusal names EVERY offending path and what it is")
        assert target.is_symlink(), "it must not have replaced the link either"
        assert (wip / name).read_bytes() == before[name], (
            "it wrote THROUGH the symlink into the workspace checkout")
    assert f"rm -f {bin_dir / 'lane-start'} {bin_dir / 'lane-end'}" in result.stderr, (
        "the refusal carries the exact `rm` that clears them, in one line")
    assert "adoption act 6" in result.stderr, "and names the act whose step 1 this is"
    # NOTHING PLACED, not eight of nine: the check is in the planning phase.
    assert sorted(p.name for p in bin_dir.iterdir()) == ["lane-end", "lane-start"]
    for target in skill_paths(tmp_path):
        assert not target.exists(), target
    assert not settings_of(tmp_path).exists()


@NEEDS_JQ
def test_a_dangling_symlink_target_refuses_too(tmp_path):
    """`-e` IS FALSE FOR A DANGLING SYMLINK, so the link test has to come
    first. A link whose target no longer exists is exactly what adoption act 5
    leaves behind on a host that has not done act 6 — and `cp` through it
    CREATES the file it points at, inside the stripped checkout."""
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    gone = tmp_path / "projects" / "brett-wip" / "lanes" / "lanes-edit.sh"
    (bin_dir / "lanes-edit.sh").symlink_to(gone)

    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{bin_dir / 'lanes-edit.sh'} — a symlink to {gone}" in result.stderr
    assert not gone.exists(), "it created the file the dangling link pointed at"
    assert [p.name for p in bin_dir.iterdir()] == ["lanes-edit.sh"]


@NEEDS_JQ
def test_a_directory_where_a_command_goes_refuses(tmp_path):
    """The other non-regular file `--install` can meet. `cp` into a directory
    puts the file INSIDE it, so this one would have reported nine placed and
    left `~/.local/bin/park/park` where `~/.local/bin/park` was asked for."""
    bin_dir = tmp_path / ".local" / "bin"
    (bin_dir / "park").mkdir(parents=True)
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{bin_dir / 'park'} — a directory" in result.stderr
    assert [p.name for p in bin_dir.iterdir()] == ["park"]


@NEEDS_JQ
def test_a_regular_file_at_a_target_is_still_replaced(tmp_path):
    """THE REFUSAL IS NARROW. An ordinary previous install is a regular file
    and is updated in place, which is what `--install` is for; only a target
    that is not a regular file costs a run."""
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "park").write_text("#!/usr/bin/env bash\n# an older park\n",
                                  encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"park: updated at {bin_dir / 'park'}" in result.stdout
    assert (bin_dir / "park").read_bytes() == (REPO / "park").read_bytes()


# --- what the conflict arm keys on (R-A9-14) -------------------------------

@NEEDS_JQ
def test_a_lanes_edit_entry_that_is_not_a_session_start_is_not_a_conflict(tmp_path):
    """KEYED ON `lanes-edit.sh`, THIS REFUSED, AND IT IS NOT A COMPETING WRITER
    (F7 of the #24 review; R-A9-14).

    `lanes-edit.sh who` under `SessionStart` prints the register's view of this
    lane. It writes no hook, fires nothing twice, and blocking `--install` on
    it for ever is the literal reading of clause (b) doing exactly the harm the
    narrowing exists to avoid. The clause's REASON is a second writer of THIS
    hook, and what two such entries collide on is the verb.
    """
    other = "~/.local/bin/lanes-edit.sh who"
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {"SessionStart": [
        {"matcher": "startup",
         "hooks": [{"type": "command", "command": other, "timeout": 3}]}]}}),
        encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert session_start_commands(tmp_path) == [other, HOOK_COMMAND]


@NEEDS_JQ
def test_a_competing_session_start_writer_under_another_name_is_a_conflict(tmp_path):
    """AND THE MIRROR OF IT. `~/bin/lane-hook.sh session-start` names no file
    of ours and IS the thing clause (b) is about: two entries running
    `session-start`, so the hook fires twice. Keyed on `lanes-edit.sh` this one
    merged straight past."""
    other = "~/bin/lane-hook.sh session-start"
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {"SessionStart": [
        {"matcher": HOOK_MATCHER,
         "hooks": [{"type": "command", "command": other, "timeout": 5}]}]}}),
        encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "runs `session-start` with a" in result.stderr
    assert session_start_commands(tmp_path) == [other], "it changed the file"
    assert not (tmp_path / ".local" / "bin").exists(), (
        "the refusal must cost a whole install, not half of one")
