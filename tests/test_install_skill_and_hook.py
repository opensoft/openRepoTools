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
                                        COMMAND_NAMES, COMMAND_PATHS,
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


# --- the command file (A11 Addendum 4 ruling 9) -----------------------------

def command_paths(home: Path, name: str) -> tuple[Path, Path]:
    """The two places `--install` writes a command file — the pair a skill has,
    for the same two ways a session is started."""
    return (home / ".claude-profiles" / "shared" / "commands" / f"{name}.md",
            home / ".claude" / "commands" / f"{name}.md")


@NEEDS_JQ
@pytest.mark.parametrize("name", COMMAND_NAMES)
def test_install_places_the_command_file_at_both_paths(tmp_path, name):
    """AFTER `workBenches#74`, `/swap` HAS NO OTHER OWNER (F-X28).

    `#74` @`0b7f6bc` deletes `base-image/files/claude/commands/` along with the
    launcher's copy of the `lane-swap` skill, and adoption act 6 — which would
    have `--install` inherit command files — lands AFTER act 3, which is this
    PR's base. So on the day `#74` lands, clause (g)'s `/swap`, a ratified
    decision and one of the six edits to in-force text, would be installed by
    nobody. Ruling 9 puts it here.

    `setup-claude-profiles.sh:140,295` makes `<profiles>/shared/commands` and
    links it into every profile as `<profile>/commands`, exactly as it does for
    `skills` — so the shared copy is `/swap` under the launcher and the
    `~/.claude` copy is `/swap` in a bare `claude` run.
    """
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    source = (REPO / f"commands/{name}.md").read_bytes()
    for target in command_paths(tmp_path, name):
        assert target.is_file(), result.stdout
        assert target.read_bytes() == source, target
        assert stat.S_IMODE(target.stat().st_mode) == 0o644, target
        assert f"/{name}: installed at {target}" in result.stdout


@NEEDS_JQ
def test_the_shipped_command_is_an_alias_and_restates_no_step():
    """CLAUSE (g) MAKES `/swap` AN ALIAS, AND AN ALIAS THAT RESTATES THE STEPS
    IS THE ALTERNATIVE IT REJECTS BY NAME: *"Two copies of one procedure that
    must stay byte-equal is the rejected alternative."*

    So the file's whole content is an instruction to invoke the skill, and it
    must not carry a step list of its own. Held here because the day someone
    "helpfully" pastes the procedure into it is the day the two can differ.
    """
    text = (REPO / "commands/swap.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), "a command file opens with front matter"
    assert "lane-swap" in text, "the alias must name the skill it invokes"
    assert "/swap" in text, "clause (g): the alias is named in its own description"
    # The skill's own numbered steps, which this file must NOT carry.
    skill = (REPO / SKILL_PATH).read_text(encoding="utf-8")
    for heading in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5."):
        assert heading in skill, f"the skill lost {heading} — this test is stale"
        assert heading not in text, (
            f"commands/swap.md restates the skill's {heading}; clause (g) makes "
            "it an alias, and two copies of one procedure is what it rejects")


@NEEDS_JQ
def test_a_drifted_command_file_is_replaced_and_an_identical_one_is_left_alone(tmp_path):
    """The same idempotence the skills have, for the same reason: a person who
    edits the installed copy gets it back, and a run that changes nothing says
    so instead of reporting a write."""
    assert run_cmd("--install", home=tmp_path).returncode == 0
    shared, _bare = command_paths(tmp_path, "swap")
    shared.write_text(shared.read_text(encoding="utf-8") + "\n<!-- drift -->\n",
                      encoding="utf-8")
    second = run_cmd("--install", home=tmp_path)
    assert second.returncode == 0, second.stderr
    assert f"/swap: updated at {shared}" in second.stdout
    assert shared.read_bytes() == (REPO / "commands/swap.md").read_bytes()
    third = run_cmd("--install", home=tmp_path)
    assert f"/swap: already installed at {shared} (unchanged)" in third.stdout


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


# --- the nine targets, and what they are (R-A9-12) --------------------------

@NEEDS_JQ
@NOT_ROOT
def test_a_leaf_destination_that_exists_unwritable_refuses_before_anything_is_placed(
        tmp_path):
    """THE `-w` ARM, WHICH THE TEST ABOVE NEVER REACHES (F6 of the #24 review,
    ruled R-A9-15).

    The case above chmods the PARENT, so `mkdir -p` is what refuses and
    `[ -w "$d" ] || die` is never asked. Measured: `mkdir -p` returns 0 on a
    directory that already EXISTS at 0500, so the leaf itself is the only way
    to reach that arm — and with the arm mutated to a no-op the whole review's
    run of this file stayed at 13 passed. A guard no test reaches is a guard
    nobody can rely on.

    The bin directory is the assertion that tells the two apart: the refusal
    here is a PLANNING one and nothing is placed, where the mutant places all
    nine files and dies on the `cp` into this same directory, which is the
    half-install the planning phase exists to prevent.
    """
    blocked = tmp_path / ".claude-profiles" / "shared" / "skills" / "lane-swap"
    blocked.mkdir(parents=True)
    blocked.chmod(0o500)
    bin_dir = tmp_path / ".local" / "bin"
    try:
        result = run_cmd("--install", home=tmp_path)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "is not writable" in result.stderr, result.stderr
        assert "NOTHING was installed" in result.stderr
        assert not bin_dir.exists() or not any(bin_dir.iterdir()), (
            "the nine files were placed against a leaf directory that was "
            "never going to take the skill")
    finally:
        blocked.chmod(0o700)


def _wip_with_links(tmp_path) -> tuple[Path, Path, dict]:
    """A bin directory carrying exactly what the pre-move `link-estates` leaves
    on a workstation: `lane-start` and `lane-end` as symlinks into a checkout.
    Returns the bin directory, the checkout, and each linked file's bytes."""
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    wip = tmp_path / "projects" / "brett-wip" / "lanes"
    wip.mkdir(parents=True)
    contents = {}
    for name in ("lane-start", "lane-end"):
        real = wip / name
        real.write_text(f"the {name} this checkout had before --install ran\n",
                        encoding="utf-8")
        contents[name] = real.read_bytes()
        (bin_dir / name).symlink_to(real)
    return bin_dir, wip, contents


@NEEDS_JQ
def test_a_symlinked_target_is_refused_and_nothing_is_written_through_it(tmp_path):
    """`cp` FOLLOWS A SYMLINK, AND THE FAR END IS THE REGISTER'S CHECKOUT
    (F5 of the #24 review, ruled R-A9-12).

    Measured before the fix, against exactly this fixture: `lane-start: updated
    at $BIN/lane-start`, `9 of 9 placed in $BIN`, exit 0 — and both claims
    false. The targets stayed symlinks, so the two commands were never
    installed (workBenches' `setup-estate-commands.sh` then refuses the whole
    estate install on them), and the post-move bytes landed in the working tree
    on the other end: `git -C $WIP status --porcelain` answered
    ` M lanes/lane-end` and ` M lanes/lane-start`. That is the repository every
    lane writes, so `lanes-edit.sh`'s `refuse_dirty_checkout` then refuses
    `log`, `claim` and `release` on that workstation.

    A host still carrying those links is the NORMAL pre-act-5 case, which is
    why the refusal names each path, what it is, and the `rm` that clears them.
    """
    bin_dir, wip, contents = _wip_with_links(tmp_path)
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "NOTHING was installed" in result.stderr
    for name in ("lane-start", "lane-end"):
        assert f"{bin_dir / name} — a symlink to {wip / name}" in result.stderr, (
            "the refusal must name every offending target and say what it "
            f"is:\n{result.stderr}")
    assert f'rm -f -- "{bin_dir / "lane-start"}" "{bin_dir / "lane-end"}"' in result.stderr, (
        f"the refusal must print the exact `rm` that clears them:\n{result.stderr}")
    # THE POINT OF THE WHOLE ROUND: the checkout on the far end is untouched.
    for name, before in contents.items():
        assert (wip / name).read_bytes() == before, (
            f"--install wrote through the symlink into {wip / name}")
        assert (bin_dir / name).is_symlink(), (
            f"{bin_dir / name} is no longer the link it was")
    # …and it refused in the PLANNING phase: none of the other seven arrived.
    assert sorted(p.name for p in bin_dir.iterdir()) == ["lane-end", "lane-start"]
    assert not (tmp_path / ".claude").exists(), (
        "the hook or the skill was placed by a run that refused")


@NEEDS_JQ
def test_a_directory_where_a_command_goes_is_refused_the_same_way(tmp_path):
    """THE RULE IS `A REGULAR FILE`, not `not a symlink`. A directory at
    `$BIN/park` is the same refusal for the same reason — `cp` cannot place a
    file over it, and finding that out after eight of the nine are placed is
    the half-install the planning phase exists to prevent."""
    bin_dir = tmp_path / ".local" / "bin"
    (bin_dir / "park").mkdir(parents=True)
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{bin_dir / 'park'} — a directory" in result.stderr, result.stderr
    assert sorted(p.name for p in bin_dir.iterdir()) == ["park"]


@NEEDS_JQ
def test_a_dangling_symlink_is_refused_rather_than_followed(tmp_path):
    """`[ -e ]` IS FALSE ON A DANGLING LINK, AND `cp` THROUGH ONE CREATES THE
    FILE AT THE FAR END. So the planning walk asks `-L` as well: a link into a
    checkout that is not on this machine yet is the same write into a
    repository this command was never told about, one `git clone` later."""
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    missing = tmp_path / "projects" / "brett-wip" / "lanes" / "lane-start"
    (bin_dir / "lane-start").symlink_to(missing)
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{bin_dir / 'lane-start'} — a symlink to {missing}" in result.stderr, result.stderr
    assert not missing.exists(), "--install created the file at the far end"



# --- R-A9-12 reaches the skill paths too (F-X17) -----------------------------

SKILL_TARGETS = tuple(
    (profiles, name)
    for name in ("lane-swap", "restart")
    for profiles in (True, False)
)


def skill_target(home: Path, shared: bool, name: str) -> Path:
    """The two places `--install` writes each skill, by Amendment 9(b)."""
    if shared:
        return home / ".claude-profiles" / "shared" / "skills" / name / "SKILL.md"
    return home / ".claude" / "skills" / name / "SKILL.md"


@NEEDS_JQ
@pytest.mark.parametrize("shared,name", SKILL_TARGETS)
def test_a_symlinked_skill_target_is_refused_and_nothing_written_through_it(
        tmp_path, shared, name):
    """R-A9-12 IS ABOUT WHAT `cp` DOES, NOT ABOUT WHICH DIRECTORY (F-X17).

    `plan_install_targets` refuses a symlink for every one of the eleven files
    in the bin directory. `plan_skill_targets` proved only the DIRECTORIES
    writable, and `place_skill_and_hook` then reached each `SKILL.md` with
    `[ -e ]`, `cmp -s` and `cp` — none of which can tell a regular file from a
    link to one. Measured before the fix on exactly this fixture: exit 0, the
    skill reported `updated at <target>`, the target still a symlink, and the
    skill's bytes written into the file on the far end.

    Four paths, because this round doubled them from two to four: the pre-A11
    exposure was `lane-swap` alone, and `restart` arrived beside it.
    """
    far = tmp_path / "elsewhere" / f"{name}-SKILL.md"
    far.parent.mkdir(parents=True)
    far.write_text("whatever was on the other end of this link\n", encoding="utf-8")
    before = far.read_bytes()
    target = skill_target(tmp_path, shared, name)
    target.parent.mkdir(parents=True)
    target.symlink_to(far)
    bin_dir = tmp_path / ".local" / "bin"

    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})

    assert result.returncode == 2, result.stdout + result.stderr
    assert "NOTHING was installed" in result.stderr, result.stderr
    assert f"{target} — a symlink to {far}" in result.stderr, (
        f"the refusal must name the offending skill path and say what it is:\n"
        f"{result.stderr}")
    assert f'rm -f -- "{target}"' in result.stderr, (
        f"the refusal must print the exact `rm` that clears it:\n{result.stderr}")
    assert far.read_bytes() == before, f"--install wrote through the link into {far}"
    assert target.is_symlink(), f"{target} is no longer the link it was"
    # AND IT REFUSED IN THE PLANNING PHASE: the eleven commands never arrived
    # either, which is what makes `NOTHING was installed` true rather than
    # nearly true.
    assert not bin_dir.exists() or not any(bin_dir.iterdir()), (
        "the commands were placed by a run that refused on a skill target")


@NEEDS_JQ
def test_a_dangling_skill_symlink_is_refused_rather_than_followed(tmp_path):
    """`[ -e ]` IS FALSE ON A DANGLING LINK and `cp` through one CREATES the
    file at the far end — the same sharper case the bin half already refuses,
    one directory along."""
    missing = tmp_path / "elsewhere" / "restart-SKILL.md"
    target = skill_target(tmp_path, False, "restart")
    target.parent.mkdir(parents=True)
    target.symlink_to(missing)
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(tmp_path / ".local" / "bin")})
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{target} — a symlink to {missing}" in result.stderr, result.stderr
    assert not missing.exists(), "--install created the file at the far end"


@NEEDS_JQ
def test_a_directory_where_a_skill_goes_is_refused_the_same_way(tmp_path):
    """THE RULE IS `A REGULAR FILE`, not `not a symlink` — the same sentence
    the bin half's own directory case is written for."""
    target = skill_target(tmp_path, True, "lane-swap")
    target.mkdir(parents=True)
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(tmp_path / ".local" / "bin")})
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{target} — a directory" in result.stderr, result.stderr


# --- what the conflict arm keys on (R-A9-14) --------------------------------

@NEEDS_JQ
def test_a_second_writer_of_this_hook_refuses_whatever_file_carries_it(tmp_path):
    """THE VERB IS WHAT COLLIDES, NOT THE FILE THAT CARRIES IT (F7 of the #24
    review, ruled R-A9-14).

    A9 Addendum 3's R-A9-8 narrows clause (b)'s unqualified "whose `command`
    DIFFERS" to the case the clause gives a REASON for: "an entry that runs
    `session-start` with a DIFFERENT command — a competing writer of our own
    hook", whose harm is that merging fires the hook twice. Keyed on
    `lanes-edit.sh` instead, this arm merged beside exactly that — a second
    program running the same hook verb — and refused an entry that runs
    `lanes-edit.sh who`, which competes with nothing.
    """
    rival = "~/bin/lane-hook.sh session-start || true"
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {"SessionStart": [
        {"matcher": HOOK_MATCHER,
         "hooks": [{"type": "command", "command": rival, "timeout": 5}]}]}}),
        encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "a SessionStart entry that runs `session-start` with a" in result.stderr
    assert session_start_commands(tmp_path) == [rival], "it changed the file"
    assert not (tmp_path / ".local" / "bin").exists(), (
        "the refusal must cost a whole install, not half of one")


@NEEDS_JQ
def test_an_entry_that_merely_names_the_same_file_is_no_conflict(tmp_path):
    """…AND THE OTHER HALF OF THE SAME RULING. `lanes-edit.sh who` under
    `SessionStart` is somebody's own setting: it writes nothing, it is not this
    hook, and firing it does not fire ours twice. It is kept, and ours is added
    beside it — the same answer any unrelated entry gets."""
    other = "~/projects/xFactory/lanes-edit.sh who || true"
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {"SessionStart": [
        {"matcher": "startup",
         "hooks": [{"type": "command", "command": other, "timeout": 5}]}]}}),
        encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert session_start_commands(tmp_path) == [other, HOOK_COMMAND]
