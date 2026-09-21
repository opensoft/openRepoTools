# SPDX-License-Identifier: Apache-2.0
"""`--install`'s artifacts that are not one of the THIRTEEN files: the three
skills at two paths each, the three command files at two more each, and the
TWO merged hook entries.

lane-collision-protocol Amendment 9(b), inheriting A8 Addendum 2's R-A8-5
unvaried — the skill into the SHARED skills directory every profile reads
through its own symlink, a copy into `~/.claude` for a bare `claude` run
outside the launcher, and the merged entries in `~/.claude/settings.json`:
the `SessionStart` one, and — since Amendment 12 adoption act 3
(opensoft/openRepoTools#25) — the `UserPromptSubmit` NAME GUARD beside it.

WHY THE HOOKS ARE THE HARD ONES, and why most of this file is about them. Every
other thing `--install` places is a whole file, so "already there and
identical" is a `cmp`. A hook is one entry inside a file somebody else owns
and two other programs also write, and its ONLY idempotence is an exact match
on the command string. So the tests below are about the four answers that
string can have — present, absent, differing, unreadable — asked of EACH entry,
and about the one rule that makes a wrong answer survivable: both merges are
computed with the thirteen files in hand, BEFORE any of them is placed, so a
refusal costs a whole install rather than half of one — and, since the pair,
a settings file never passes through a state carrying one entry of the two.

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
                                        INSTALLED, NEEDS_JQ, SKILL_NAMES,
                                        SKILL_PATH)

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

#: The CANONICAL skill's own name, derived from the path the installer test
#: derives from `SKILL_NAMES` — Amendment 17(a) renamed the act from `lane-swap`
#: to `handoff` and kept `lane-swap` as an alias file, so a name spelled here
#: would be a second place to rename.
SKILL_DIR_NAME = Path(SKILL_PATH).parent.name

#: AMENDMENT 12's SECOND ENTRY, adoption act 3: the NAME GUARD under
#: `UserPromptSubmit`, `~/projects/xFactory/lanes-edit.sh guard`, timeout 5.
#: Spelled once here for the reason the string above is, and with TWO
#: deliberate differences from it that the tests below assert separately:
#:
#:   * NO `|| true`. On `SessionStart` that suffix is the whole safety property
#:     — a hook that dies must not break the session it was meant to orient. On
#:     `UserPromptSubmit` it would be the OPPOSITE of the mechanism: exit 2 is
#:     what BLOCKS a prompt (code.claude.com/docs/en/hooks), and `cmd || true`
#:     exits 0 for every code the command can produce. An entry copied WITH its
#:     suffix is a guard that refuses nothing, silently, which is the exact
#:     state Amendment 12 exists to end.
#:   * NO MATCHER. `UserPromptSubmit` has no source to match on.
GUARD_COMMAND = "~/projects/xFactory/lanes-edit.sh guard"
GUARD_TIMEOUT = 5

def skill_paths(home: Path) -> tuple[Path, Path]:
    return (home / ".claude-profiles" / "shared" / "skills" / SKILL_DIR_NAME / "SKILL.md",
            home / ".claude" / "skills" / SKILL_DIR_NAME / "SKILL.md")


def settings_of(home: Path) -> Path:
    return home / ".claude" / "settings.json"


def hook_commands(home: Path, event: str) -> list[str]:
    data = json.loads(settings_of(home).read_text(encoding="utf-8"))
    out = []
    for entry in data.get("hooks", {}).get(event, []):
        for hook in entry.get("hooks", []):
            if "command" in hook:
                out.append(hook["command"])
    return out


def session_start_commands(home: Path) -> list[str]:
    return hook_commands(home, "SessionStart")


def user_prompt_commands(home: Path) -> list[str]:
    return hook_commands(home, "UserPromptSubmit")


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
        assert f"{SKILL_DIR_NAME}: installed at {target}" in result.stdout


@NEEDS_JQ
def test_the_shipped_skill_is_the_one_the_launcher_invokes(tmp_path):
    """`/handoff` is what Claude Code invokes, and what it invokes is the
    skill's own `name:` (Addendum 1(3) on brettheap/new-workstation#17).
    A directory named one thing and a front-matter name that is another is a
    skill nobody can call.

    HELD FOR EVERY SKILL SHIPPED, not just the canonical one: Amendment 17(a)
    renamed this act and left `lane-swap` as an ALIAS FILE at its old path, and
    an alias whose front matter still named the old directory would be a skill
    Claude Code invokes under one name and finds under another."""
    for name in SKILL_NAMES:
        path = REPO / f"skills/{name}/SKILL.md"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n"), name
        assert f"\nname: {name}\n" in text, name
    assert Path(SKILL_PATH).parent.name == "handoff", (
        "the canonical skill is `handoff` — Amendment 17(a): one act, three names")


@NEEDS_JQ
def test_a_drifted_skill_is_replaced_and_an_identical_one_is_left_alone(tmp_path):
    assert run_cmd("--install", home=tmp_path).returncode == 0
    shared, _bare = skill_paths(tmp_path)
    shared.write_text(shared.read_text(encoding="utf-8") + "\n<!-- drift -->\n",
                      encoding="utf-8")
    second = run_cmd("--install", home=tmp_path)
    assert second.returncode == 0, second.stderr
    assert f"{SKILL_DIR_NAME}: updated at {shared}" in second.stdout
    assert shared.read_bytes() == (REPO / SKILL_PATH).read_bytes()


@NEEDS_JQ
def test_a_skill_whose_bytes_are_right_and_whose_mode_is_not_is_re_moded(tmp_path):
    """THE MODE IS STAMPED WHETHER OR NOT THE BYTES MOVED (#40, finding 2).

    `chmod 644` sat inside the `else` of the bytes comparison, so a `SKILL.md`
    whose bytes were right and whose mode was not was reported `unchanged` and
    left exactly as it was — for ever, because every later `--install` compared
    the same matching bytes and took the same arm. 755 is the drift that
    actually happens: Amendment 9(b) describes `--install` as stamping 755 "on
    everything it places", and workBenches#63's own 0644 loop wrote this same
    path until adoption act 4b deleted it, so a host can carry either.

    And the LINE has to say which of the two happened: a run that repaired a
    mode and printed `unchanged` told a person there was nothing to look at.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    shared, bare = skill_paths(tmp_path)
    before = shared.read_bytes()
    os.chmod(shared, 0o755)

    second = run_cmd("--install", home=tmp_path)
    assert second.returncode == 0, second.stderr
    assert stat.S_IMODE(shared.stat().st_mode) == 0o644, (
        "the bytes matched, so the mode was never stamped")
    assert shared.read_bytes() == before, "it rewrote a file to repair a mode"
    # `{SKILL_DIR_NAME}` AND NEVER THE LITERAL, which is what `skill_paths`
    # above already derives from `SKILL_NAMES`: Amendment 17(a) renamed this act
    # from `lane-swap` to `handoff` and kept `lane-swap` as an ALIAS FILE, so a
    # name spelled here is a name that goes stale the next time the act is
    # named — and it did, in the merge that brought this case (#40, #44) on to
    # the branch that made the rename (#36). The paths above are the first
    # skill's; the line the installer prints for them carries that skill's name.
    assert f"{SKILL_DIR_NAME}: already installed at {shared} (mode restored to 644)" \
        in second.stdout, second.stdout
    # …and the copy that was already right still reports what it is.
    assert f"{SKILL_DIR_NAME}: already installed at {bare} (unchanged)" in second.stdout


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
@pytest.mark.parametrize("name", COMMAND_NAMES)
def test_the_shipped_command_is_an_alias_and_restates_no_step(name):
    """CLAUSE (g) MAKES `/swap` AN ALIAS, AND AN ALIAS THAT RESTATES THE STEPS
    IS THE ALTERNATIVE IT REJECTS BY NAME: *"Two copies of one procedure that
    must stay byte-equal is the rejected alternative."*

    So each command file's whole content is an instruction to invoke the skill,
    and none of them may carry a step list of its own. Held here because the day
    someone "helpfully" pastes the procedure into one is the day the copies can
    differ — and Amendment 17 made that THREE doors to one act (`/handoff`,
    `/ctx` = `/handoff --restart`, and `/swap`) plus the `lane-swap` alias skill,
    so the rule is checked per file rather than on the one that had it first.
    """
    text = (REPO / f"commands/{name}.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), "a command file opens with front matter"
    assert "handoff" in text, "the alias must name the skill it invokes"
    assert f"/{name}" in text, "the alias is named in its own description"
    # The skill's own numbered steps, which no command file may carry.
    skill = (REPO / SKILL_PATH).read_text(encoding="utf-8")
    for heading in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5."):
        assert heading in skill, f"the skill lost {heading} — this test is stale"
        assert heading not in text, (
            f"commands/{name}.md restates the skill's {heading}; the alias adds "
            "nothing, and two copies of one procedure is what is rejected")


@NEEDS_JQ
def test_the_alias_skill_names_the_act_and_restates_no_step():
    """The lane-swap skill exposes managed swap and preserves legacy access.

    The separate-operation feature supersedes the old one-act alias contract:
    managed lanes use the external swap surface, while unmanaged lanes retain
    the historical handoff behavior explicitly described in the skill.
    """
    text = (REPO / "skills/lane-swap/SKILL.md").read_text(encoding="utf-8")
    assert "\nname: lane-swap\n" in text, "the alias keeps its own invocable name"
    assert "lane-managed swap" in text
    assert "historical" in text.lower()
    assert "unmanaged" in text.lower()
    assert "silent fallback" in text.lower()
    assert "--workers hold" in text
    assert "--workers restart" in text
    assert "wire accepts" in text.lower()
    assert "native integration" in text.lower()
    assert "refuses" in text.lower()
    assert "parser does not accept `--workers restart`" not in text.lower()


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


@NEEDS_JQ
def test_a_command_file_whose_mode_drifted_is_re_moded_too(tmp_path):
    """The same stamp on the same arm, one directory along (#40, finding 2).
    A command file is a document a session READS, at 644 for the reason a
    `SKILL.md` is, and an installer that owns the mode owns it on every run."""
    assert run_cmd("--install", home=tmp_path).returncode == 0
    shared, _bare = command_paths(tmp_path, "swap")
    before = shared.read_bytes()
    os.chmod(shared, 0o600)

    second = run_cmd("--install", home=tmp_path)
    assert second.returncode == 0, second.stderr
    assert stat.S_IMODE(shared.stat().st_mode) == 0o644
    assert shared.read_bytes() == before
    assert f"/swap: already installed at {shared} (mode restored to 644)" \
        in second.stdout, second.stdout


# --- the one question the mode stamp asks (#44 round 1, `openRepoTools:277`) -

def helper_source(name: str) -> str:
    """One function lifted out of the command, so a test can ask it directly.

    Anchored on the function's own opening line and the `}` in the first column
    that closes it, which is how every function in that file is written — a
    rename or a reshape fails this loudly rather than silently testing nothing.
    """
    text = COMMAND.read_text(encoding="utf-8")
    start = text.index(f"\n{name}() {{")
    end = text.index("\n}\n", start)
    return text[start + 1:end + 3]


#: Every mode `--install` stamps, asked of a file at each of them: 755 for the
#: eleven, 644 for the four skill copies and the two command files, 600 for
#: `settings.json`.
MODE_ANSWERS = (
    (0o755, "755", True), (0o644, "644", True), (0o600, "600", True),
    (0o755, "644", False), (0o644, "755", False), (0o600, "644", False),
    (0o640, "600", False),
)


@pytest.mark.parametrize("on_disk,asked,expected", MODE_ANSWERS,
                         ids=[f"{o:03o} is {a}" for o, a, _ in MODE_ANSWERS])
def test_mode_is_answers_the_find_this_platform_ships(tmp_path, on_disk, asked,
                                                      expected):
    """THE CLAIM `mode_is` MAKES IS A PORTABILITY CLAIM, SO IT IS ASKED ON EACH
    PLATFORM THAT RUNS THIS SUITE (#44 round 1, `openRepoTools:277`).

    The round's review held that `find -maxdepth` is not in the stock BSD/macOS
    `find`, so `mode_is` would answer FALSE for every mode on that platform and
    every artifact would report `(mode restored …)` for ever. It is in it —
    `-maxdepth` is a FreeBSD primary, documented in that `find`'s own page in
    the words *"`-maxdepth 0` limits the whole search to the command line
    arguments"*, and this repository already ships three of them in
    `lanes-edit.sh` — and the `tests-macos` job is where that stops being a
    claim about a manual page: this test asks the helper the three octals
    `--install` actually stamps, and both answers for each, on whatever `find`
    the platform running it has.

    That is the whole reason the helper is `find` and not `stat`: GNU spells it
    `stat -c %a` and BSD `stat -f %Lp`, nothing here may reach for one without
    the other beside it (`test_repo_hygiene.py`'s GNU-only rule), and
    `-perm <octal>` with neither a `-` nor a `+` in front of it is EXACT on
    both.
    """
    target = tmp_path / "artifact"
    target.write_text("whatever this installer placed\n", encoding="utf-8")
    os.chmod(target, on_disk)
    script = helper_source("mode_is") + \
        f'\nif mode_is {asked} "$1"; then echo yes; else echo no; fi\n'
    done = subprocess.run(["bash", "-c", script, "mode_is", str(target)],
                          capture_output=True, text=True, check=False)
    assert done.stdout.strip() == ("yes" if expected else "no"), (
        f"`mode_is {asked}` on a file at {on_disk:03o} answered "
        f"{done.stdout.strip()!r} — this platform's `find` does not take the "
        f"one spelling GNU and BSD agree on:\n{done.stderr}")


def test_mode_is_says_no_about_a_path_that_is_not_there(tmp_path):
    """The other answer it has to get right: `find` prints a diagnostic and
    exits non-zero on a missing path, and a helper that read that as `yes`
    would report a mode on a file nothing placed."""
    script = helper_source("mode_is") + \
        '\nif mode_is 644 "$1"; then echo yes; else echo no; fi\n'
    done = subprocess.run(["bash", "-c", script, "mode_is",
                           str(tmp_path / "never-placed")],
                          capture_output=True, text=True, check=False)
    assert done.stdout.strip() == "no", done.stdout + done.stderr
    assert done.stderr == "", "the diagnostic reached a person's terminal"


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
def test_a_present_hook_in_a_widened_settings_file_is_narrowed_to_600(tmp_path):
    """`HOOK_PLAN=present` NEVER APPLIED THE DOCUMENTED MODE (#40, finding 3).

    The `nofile` and `absent` arms write this file through `mktemp` +
    `chmod 600` + `mv -f`, so a file THEY wrote is 600. The `present` arm — an
    existing settings file whose expected entry is already there — printed one
    line and touched nothing, so a direct `--install` could leave
    `~/.claude/settings.json` world-readable for ever, and no later run would
    ever narrow it: the entry stays present on every one of them.

    600 is not this installer's preference either. workBenches'
    `setup-claude-profiles.sh` writes this same file at 600 on every
    `./setup.sh`, so a wider mode left here is either silently undone by that
    script or widened behind its back.

    THE FILE IS NOT REWRITTEN TO FIX A MODE: a user's settings are not an
    installer's to own, and `chmod` changes no byte of them.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    settings = settings_of(tmp_path)
    before = settings.read_bytes()
    os.chmod(settings, 0o644)

    second = run_cmd("--install", home=tmp_path)
    assert second.returncode == 0, second.stderr
    assert stat.S_IMODE(settings.stat().st_mode) == 0o600, (
        "a `present` hook left the file at the mode it found")
    assert settings.read_bytes() == before, "it rewrote the file to repair a mode"
    assert session_start_commands(tmp_path) == [HOOK_COMMAND]
    assert f"SessionStart hook: already installed in {settings} " \
           f"(mode restored to 600)" in second.stdout, second.stdout


@NEEDS_JQ
@pytest.mark.parametrize("entry", ["present", "absent"])
def test_a_symlinked_settings_file_is_refused_rather_than_written_through(
        tmp_path, entry):
    """`chmod` FOLLOWS A SYMLINK, AND SO DOES NOTHING ELSE ABOUT IT (#44 round
    1, `openRepoTools:878`).

    The mode stamp this round put on the `present` arm is the sharper half: a
    `~/.claude/settings.json` linked into a dotfiles checkout — which is how a
    person who versions their settings has it — got the 600 stamped on the file
    at the FAR END, an unrelated file re-moded by a run that reported the entry
    `already installed`. The `absent` arm is the older half of the same
    question: it writes a temporary beside this path and `mv -f`s it here,
    which REPLACES the link with a regular file, so the link a person put there
    is gone and their dotfiles copy silently stops being what `claude` reads.

    One refusal answers both, in the planning phase and with the same shape the
    other seventeen artifacts are refused with: the path, what it is, and the
    `rm` that clears it. What is on the other end keeps its bytes and its mode,
    which is the assertion that tells this from either defect.
    """
    far = tmp_path / "dotfiles" / "settings.json"
    far.parent.mkdir(parents=True)
    payload = {"model": "opus"}
    if entry == "present":
        payload["hooks"] = {"SessionStart": [
            {"matcher": HOOK_MATCHER,
             "hooks": [{"type": "command", "command": HOOK_COMMAND,
                        "timeout": HOOK_TIMEOUT}]}]}
    far.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(far, 0o644)
    before = far.read_bytes()
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.symlink_to(far)
    bin_dir = tmp_path / ".local" / "bin"

    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})

    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{settings} — a symlink to {far}" in result.stderr, result.stderr
    assert f'rm -f -- "{settings}"' in result.stderr, result.stderr
    assert "NOTHING was installed" in result.stderr
    assert stat.S_IMODE(far.stat().st_mode) == 0o644, (
        "the mode was stamped through the link onto the file at the far end")
    assert far.read_bytes() == before, "the far end was written through"
    assert settings.is_symlink(), "the merge replaced the link with its own file"
    assert not bin_dir.exists() or not any(bin_dir.iterdir()), (
        "the eleven commands were placed by a run that refused")


@NEEDS_JQ
def test_a_differing_session_start_entry_refuses_and_places_nothing(tmp_path):
    """THE ENTRY INSTALLED BY HAND ON EAGLE DOES NOT MATCH, and refusing is the
    right outcome. Amendment 8's adoption act 6 placed
    `bash -lc '"$HOME/projects/xFactory/lanes-edit.sh" session-start
    2>/dev/null || true'` under the same matcher; its `command` is not clause
    (e)'s string, so merging would quietly add a SECOND entry and fire the hook
    twice.

    AND THE COST IS A WHOLE INSTALL, NOT HALF OF ONE: both merges are computed
    with the thirteen files in hand, before any of them is placed, so the bin
    directory is untouched. That is the same all-or-nothing rule `--install`
    already had, extended to the two artifacts that are not whole files.
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
    across twenty-seven artifacts, so nothing can make the last fourteen atomic
    with the first thirteen — but the failure that actually happens is not an
    exotic one, it
    is a directory that is not this installer's to write, and that question can
    be asked in the planning phase where the refusal still costs nothing.

    Without the check the run places thirteen files and some of the remaining
    artifacts, then dies — leaving a host with commands installed,
    neither hook entry, and an installer that reports the same "already
    installed (unchanged)" for the thirteen on every re-run while never reaching
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
            "the thirteen files were placed against a destination that was never "
            "going to take the other fourteen")
    finally:
        blocked.chmod(0o700)


# --- the thirteen targets, and what they are (R-A9-12) ---------------------

@NEEDS_JQ
@NOT_ROOT
def test_a_leaf_destination_that_exists_unwritable_refuses_before_anything_is_placed(
        tmp_path):
    """EVERY DESTINATION IS ASKED ABOUT, AND NOT ONLY THE ROOTS THEY HANG UNDER
    (F6 of the #24 review, ruled R-A9-15).

    When the arm was `mkdir -p` and then `[ -w "$d" ]`, the case above — which
    chmods the PARENT — never reached the `-w` at all, because the `mkdir`
    refused first; measured then: `mkdir -p` returns 0 on a directory that
    already EXISTS at 0500, so the leaf was the only way in, and with the arm
    mutated to a no-op the whole review's run of this file stayed at 13 passed.
    Since #44 round 1 the planner creates nothing and asks the nearest ancestor
    that exists, so both cases land on one arm — and this fixture is what says
    the walk covers the LEAF each artifact actually goes in, rather than the
    two roots above it. A guard no test reaches is a guard nobody can rely on.

    The bin directory is the assertion that tells the two apart: the refusal
    here is a PLANNING one and nothing is placed, where the mutant places all
    thirteen files and dies on the `cp` into this same directory, which is the
    half-install the planning phase exists to prevent.
    """
    blocked = tmp_path / ".claude-profiles" / "shared" / "skills" / SKILL_DIR_NAME
    blocked.mkdir(parents=True)
    blocked.chmod(0o500)
    bin_dir = tmp_path / ".local" / "bin"
    try:
        result = run_cmd("--install", home=tmp_path)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "is not writable" in result.stderr, result.stderr
        assert "NOTHING was installed" in result.stderr
        assert not bin_dir.exists() or not any(bin_dir.iterdir()), (
            "the thirteen files were placed against a leaf directory that was "
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
    file over it, and finding that out after twelve of the thirteen are placed is
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



@NEEDS_JQ
@NOT_ROOT
def test_an_unwritable_command_in_the_bin_directory_is_refused(tmp_path):
    """`unplaceable_kind` TREATED EVERY EXISTING REGULAR FILE AS WRITABLE
    (#40, finding 4).

    It answered `return 1` — placeable — for any `[ -f ]`, so a target this
    user may not write passed the plan and met `cp` instead. In the bin
    directory that is a run that dies part way through the eleven; one
    directory along it is worse, because `install_commands` has already copied
    all eleven by then.

    The remedy the refusal prints is still the right one for this kind: `rm -f`
    takes a read-only file, because what a removal needs is the DIRECTORY's
    write bit and not the file's.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    target = bin_dir / "park"
    target.write_text("the park a person chmod 444'd\n", encoding="utf-8")
    before = target.read_bytes()
    os.chmod(target, 0o444)
    try:
        result = run_cmd("--install", home=tmp_path,
                         env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
        assert result.returncode == 2, result.stdout + result.stderr
        assert f"{target} — a regular file this user cannot write" \
            in result.stderr, result.stderr
        assert f'rm -f -- "{target}"' in result.stderr, result.stderr
        assert "NOTHING was installed" in result.stderr
        assert target.read_bytes() == before, "it wrote the file anyway"
        assert sorted(p.name for p in bin_dir.iterdir()) == ["park"], (
            "the other ten were placed by a run that refused")
        assert not (tmp_path / ".claude").exists(), (
            "the skills or the hook were placed by a run that refused")
    finally:
        os.chmod(target, 0o644)


@NEEDS_JQ
@NOT_ROOT
def test_a_bin_directory_that_cannot_be_written_refuses_before_anything(tmp_path):
    """THE `-w` QUESTION FOR EVERY TARGET THAT IS NOT THERE YET (#40, finding
    4). An absent file is placeable exactly where the directory it would be
    created in takes a write, and `plan_skill_targets` has always asked that of
    the directories it writes into. The bin directory was never asked, so a
    `$OPENREPOTOOLS_BIN_DIR` that is not this user's failed at the first `cp`
    under `set -e` — exit 1, the code this toolset spends on "findings were
    printed", from a run that placed nothing and printed none.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    bin_dir.chmod(0o500)
    try:
        result = run_cmd("--install", home=tmp_path,
                         env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
        assert result.returncode == 2, result.stdout + result.stderr
        assert f"{bin_dir} is not writable" in result.stderr, result.stderr
        assert "NOTHING was installed" in result.stderr
        assert not any(bin_dir.iterdir())
        assert not (tmp_path / ".claude").exists(), (
            "the skills or the hook were placed by a run that refused")
    finally:
        bin_dir.chmod(0o700)


@NEEDS_JQ
@NOT_ROOT
def test_a_bin_directory_that_cannot_be_created_is_refused_in_planning(tmp_path):
    """THE `-w` THAT WAS NEVER ASKED, BECAUSE THE DIRECTORY WAS NOT THERE TO ASK
    (#44 round 1, Sourcery's `README.md:237`, and `openRepoTools:653`).

    The round before this one added the bin directory to the planning phase and
    asked `[ -d "$dir" ]` first, so a `$OPENREPOTOOLS_BIN_DIR` that does not
    exist YET was asked nothing at all — and an absent directory under a parent
    this user cannot write is the case that fails. It reached the `mkdir -p` in
    `install_commands`, which was unguarded: `set -e` exits 1 there, and 1 is
    the code this toolset spends on "findings were printed", so the run said
    nothing and a person reading the exit code was told the wrong thing.

    The question is put to the NEAREST ANCESTOR THAT EXISTS, which is the same
    question `-w` on an existing directory is — and it is put before the fetch,
    so a refusal costs no network round-trip either.
    """
    parent = tmp_path / "opt"
    parent.mkdir()
    bin_dir = parent / "bin"
    parent.chmod(0o500)
    try:
        result = run_cmd("--install", home=tmp_path,
                         env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
        assert result.returncode == 2, result.stdout + result.stderr
        assert f"{parent} is not writable" in result.stderr, (
            f"the refusal must name the ancestor that refuses the create:\n"
            f"{result.stderr}")
        assert "NOTHING was installed" in result.stderr
        assert not bin_dir.exists(), "the run created the directory it refused"
        assert not (tmp_path / ".claude").exists(), (
            "the skills or the hook were placed by a run that refused")
    finally:
        parent.chmod(0o700)


@NEEDS_JQ
@NOT_ROOT
@pytest.mark.parametrize("which", ["the bin directory", "a skill destination"])
def test_a_destination_whose_search_bit_is_off_is_refused_in_planning(
        tmp_path, which):
    """`-w` DOES NOT MAKE A DIRECTORY ONE A FILE CAN BE CREATED IN (#44 round 1,
    the suppressed comment at `openRepoTools:658`).

    Creating a file takes the directory's `w` AND its `x`, so a directory at
    0600 accepts nothing at all — and both planners asked only `-w`, passed it,
    and met the failure at a `cp` with artifacts already placed. The two halves
    are parametrized together because the rule is one implementation: two
    copies of it is how the bin half comes to refuse what the skill half
    allows.
    """
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    if which == "the bin directory":
        blocked = bin_dir
    else:
        blocked = tmp_path / ".claude-profiles" / "shared" / "skills"
        blocked.mkdir(parents=True)
    blocked.chmod(0o600)
    try:
        result = run_cmd("--install", home=tmp_path,
                         env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
        assert result.returncode == 2, result.stdout + result.stderr
        assert f"{blocked} is not searchable" in result.stderr, result.stderr
        assert "NOTHING was installed" in result.stderr
        assert not any(bin_dir.iterdir()), (
            "the eleven commands were placed against a directory that takes "
            "no file at all")
    finally:
        blocked.chmod(0o700)


@NEEDS_JQ
@NOT_ROOT
def test_a_planning_refusal_creates_none_of_the_destination_directories(tmp_path):
    """"NOTHING WAS INSTALLED" INCLUDED SEVEN DIRECTORIES (#44 round 1,
    Sourcery's `tests/test_install_skill_and_hook.py:658`).

    `plan_skill_targets` proved each destination writable by `mkdir -p`-ing it
    and reading the result, so a run that then refused — on a target one
    directory along, or on the hook — had already made `~/.claude`,
    `~/.claude/skills/<each>`, `~/.claude/commands` and the shared trio on a
    machine that had none of them. The refusal says nothing was installed, and
    a person who then removes what they were told about is left with the rest.

    The question is put to the nearest ancestor that exists instead, and the
    places are made in the placement phase by the guarded `mkdir -p` each `cp`
    already carries. The offending target here is in the SHARED tree, so
    `~/.claude` is the assertion: a fixture cannot both put a file at a path
    and leave that path's directory unmade.
    """
    target = skill_target(tmp_path, True, "lane-swap")
    target.parent.mkdir(parents=True)
    target.write_text("the SKILL.md a person made read-only\n", encoding="utf-8")
    os.chmod(target, 0o444)
    bin_dir = tmp_path / ".local" / "bin"
    try:
        result = run_cmd("--install", home=tmp_path,
                         env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
        assert result.returncode == 2, result.stdout + result.stderr
        assert "NOTHING was installed" in result.stderr
        assert not (tmp_path / ".claude").exists(), (
            "planning made ~/.claude on a machine that had none, over a "
            "refusal that says nothing was installed")
        assert not skill_target(tmp_path, True, "restart").parent.exists(), (
            "planning made the other skill's shared directory")
        assert not (tmp_path / ".claude-profiles" / "shared" / "commands").exists(), (
            "planning made the shared commands directory")
        assert not bin_dir.exists() or not any(bin_dir.iterdir())
    finally:
        os.chmod(target, 0o644)


@NEEDS_JQ
def test_a_dangling_symlink_ancestor_is_refused_rather_than_stepped_over(tmp_path):
    """`-e` FOLLOWS A SYMLINK AND IS FALSE ON A DANGLING ONE (#44 round 2,
    `openRepoTools:701`).

    `unusable_dir_kind`'s walk asked `[ ! -e "$d" ]` alone to decide "not there
    yet, keep walking up" — and `-e` is false on a DANGLING symlink exactly as
    it is on a path with nothing at it at all, so the walk stepped PAST a
    dangling `$OPENREPOTOOLS_BIN_DIR` parent and asked about its grandparent
    instead, which passed. `mkdir -p` then meets the dangling link and fails —
    on the one path that promises all or none.

    A symlink is something AT that path, dangling or not: the walk now stops
    there, exactly as it stops at a real directory or file.
    """
    parent = tmp_path / "opt"
    parent.symlink_to(tmp_path / "nowhere-at-all")
    bin_dir = parent / "bin"
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{parent} is a symlink to" in result.stderr, (
        f"the refusal must name the dangling ancestor, not step past it:\n"
        f"{result.stderr}")
    assert "NOTHING was installed" in result.stderr
    assert not bin_dir.exists(), "mkdir -p ran despite the dangling ancestor"
    assert not (tmp_path / ".claude").exists(), (
        "the skills or the hook were placed by a run that refused")


# --- R-A9-12 reaches the skill paths too (F-X17) -----------------------------

SKILL_TARGETS = tuple(
    (profiles, name)
    for name in SKILL_NAMES
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

    `plan_install_targets` refuses a symlink for every one of the thirteen files
    in the bin directory. `plan_skill_targets` proved only the DIRECTORIES
    writable, and `place_skill_and_hook` then reached each `SKILL.md` with
    `[ -e ]`, `cmp -s` and `cp` — none of which can tell a regular file from a
    link to one. Measured before the fix on exactly this fixture: exit 0, the
    skill reported `updated at <target>`, the target still a symlink, and the
    skill's bytes written into the file on the far end.

    Six paths, because each round has added a skill: the pre-A11 exposure was
    `lane-swap` alone, `restart` arrived beside it, and Amendment 17(a) added
    `handoff` — the act itself, with `lane-swap` kept as its alias file. The
    list is `SKILL_NAMES`, so the next skill is covered by existing itself.
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
    # AND IT REFUSED IN THE PLANNING PHASE: the thirteen commands never arrived
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
    target = skill_target(tmp_path, True, SKILL_DIR_NAME)
    target.mkdir(parents=True)
    result = run_cmd("--install", home=tmp_path,
                     env={"OPENREPOTOOLS_BIN_DIR": str(tmp_path / ".local" / "bin")})
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"{target} — a directory" in result.stderr, result.stderr


@NEEDS_JQ
@NOT_ROOT
@pytest.mark.parametrize("shared,name", SKILL_TARGETS)
def test_an_unwritable_skill_target_refuses_before_anything_is_placed(
        tmp_path, shared, name):
    """AN UNWRITABLE `SKILL.md` PASSED THE TARGET PLAN, AND THE ALL-OR-NOTHING
    RULE THEN COVERED ELEVEN OF THE EIGHTEEN (#40, finding 4).

    `unplaceable_kind` answered `return 1` for every `[ -f ]` and asked nothing
    else, so `plan_skill_targets` let a read-only `SKILL.md` through.
    `install_commands` copies the eleven PATH files BEFORE `place_skill_and_hook`
    reaches `cp`, so an ordinary permission failure there left a host with the
    eleven commands installed, no skills, no `/swap` and no `SessionStart`
    entry — on the one path in this file that promises all or none, and with
    every later `--install` reporting the eleven `already installed
    (unchanged)` while never reaching the one that failed.

    THE BIN DIRECTORY IS THE ASSERTION THAT TELLS THE FIX FROM THE DEFECT: the
    refusal here is a PLANNING one and nothing is placed at all.
    """
    target = skill_target(tmp_path, shared, name)
    target.parent.mkdir(parents=True)
    target.write_text("the SKILL.md a person made read-only\n", encoding="utf-8")
    before = target.read_bytes()
    os.chmod(target, 0o444)
    bin_dir = tmp_path / ".local" / "bin"
    try:
        result = run_cmd("--install", home=tmp_path,
                         env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
        assert result.returncode == 2, result.stdout + result.stderr
        assert f"{target} — a regular file this user cannot write" \
            in result.stderr, result.stderr
        assert f'rm -f -- "{target}"' in result.stderr, result.stderr
        assert "NOTHING was installed" in result.stderr
        assert target.read_bytes() == before, f"--install wrote over {target}"
        assert not bin_dir.exists() or not any(bin_dir.iterdir()), (
            "the eleven commands were placed against a skill target that was "
            "never going to take the skill")
    finally:
        os.chmod(target, 0o644)


@NEEDS_JQ
@NOT_ROOT
@pytest.mark.parametrize("name", COMMAND_NAMES)
def test_an_unwritable_command_target_is_refused_the_same_way(tmp_path, name):
    """The same rule at the command file's own pair of destinations, because
    the rule is `unplaceable_kind` and not a list of paths."""
    target = command_paths(tmp_path, name)[0]
    target.parent.mkdir(parents=True)
    target.write_text("the alias a person made read-only\n", encoding="utf-8")
    before = target.read_bytes()
    os.chmod(target, 0o444)
    bin_dir = tmp_path / ".local" / "bin"
    try:
        result = run_cmd("--install", home=tmp_path,
                         env={"OPENREPOTOOLS_BIN_DIR": str(bin_dir)})
        assert result.returncode == 2, result.stdout + result.stderr
        assert f"{target} — a regular file this user cannot write" \
            in result.stderr, result.stderr
        assert target.read_bytes() == before
        assert not bin_dir.exists() or not any(bin_dir.iterdir())
    finally:
        os.chmod(target, 0o644)


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
def test_our_own_entry_beside_a_rival_refuses_rather_than_reading_present(tmp_path):
    """`conflict` BEATS `present`, AND THE ORDER IS THE WHOLE OF #59.

    `present` was asked FIRST, so a settings file carrying our exact entry AND a
    second writer of the same hook answered `present`: `--install` added
    nothing, said nothing, and the person kept two writers of one hook — the
    state the arm above exists to refuse — with the run reporting success.

    NOTHING WAS INSTALLED TWICE BY SUCH A RUN, which is why it went unnoticed:
    with the exact entry already there, there is nothing to add and the file is
    unchanged. The defect is that the state was never NAMED, and that somebody
    who runs `--install` expecting it to police this hook was told everything
    was fine. The cost of naming it is this repository's own rule: `conflict`
    refuses the WHOLE install (R-A9-12), so a workstation carrying a rival
    cannot install or update any artifact until the rival is gone — which is
    already the answer a file with no entry of ours gets.

    THE REFUSAL NAMES BOTH, and here that is not a nicety. This file carries our
    entry as well as the rival, so "remove that entry" with nothing named is a
    line a person can read as "remove the block this installer just printed",
    which would take the working entry away and leave the second writer.

    The two halves of the same read are asserted beside this: the rival ALONE
    still refuses (the test above), and our entry alone still answers `present`,
    silently (`test_installing_twice_adds_one_entry_and_not_two`).
    """
    rival = "~/bin/lane-hook.sh session-start || true"
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    before = json.dumps({"hooks": {"SessionStart": [
        {"matcher": HOOK_MATCHER,
         "hooks": [{"type": "command", "command": HOOK_COMMAND,
                    "timeout": HOOK_TIMEOUT}]},
        {"matcher": HOOK_MATCHER,
         "hooks": [{"type": "command", "command": rival, "timeout": 5}]}]}},
        indent=2)
    settings.write_text(before, encoding="utf-8")
    os.chmod(settings, 0o644)

    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "a SessionStart entry that runs `session-start` with a" in result.stderr
    assert "DIFFERENT command string" in result.stderr
    assert rival in result.stderr, (
        "the refusal must NAME the rival: this file carries ours too, and "
        "'remove that entry' would otherwise be ambiguous\n" + result.stderr)
    assert HOOK_COMMAND in result.stderr, "the refusal prints the exact block"
    assert "NOTHING was installed" in result.stderr
    assert settings.read_text(encoding="utf-8") == before, "it changed the file"
    assert stat.S_IMODE(settings.stat().st_mode) == 0o644, (
        "the `present` arm's mode stamp ran on a file the merge refused")
    assert not (tmp_path / ".local" / "bin").exists(), (
        "the refusal must cost a whole install, not half of one")
    for target in skill_paths(tmp_path):
        assert not target.exists(), target


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


# --- Amendment 12's second entry: the UserPromptSubmit name guard ------------
#
# ADOPTION ACT 3, ratified 2026-09-13T18:20:44Z ("Ratify revision 2"):
# "`openRepoTools --install` places the hook string under `UserPromptSubmit` in
# the profile's `settings.json` beside the `SessionStart` one —
# `~/projects/xFactory/lanes-edit.sh guard`, timeout 5". The cases below are
# the pair's own, and each of them is a way the pair can go wrong that a single
# entry could not.

@NEEDS_JQ
def test_the_guard_entry_is_byte_identical_to_amendment_12(tmp_path):
    """THE STRING IS THE WHOLE MECHANISM HERE TOO, and the SHAPE is half of it.

    `UserPromptSubmit` takes no `matcher` — there is no source to match on —
    so the entry is `{"hooks": [ ... ]}` and nothing else, and an installer
    that copied the `SessionStart` block wholesale would write a key the event
    does not have.
    """
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    data = json.loads(settings_of(tmp_path).read_text(encoding="utf-8"))
    entries = data["hooks"]["UserPromptSubmit"]
    assert len(entries) == 1, entries
    assert "matcher" not in entries[0], (
        "UserPromptSubmit has no source to match on; the key belongs to the "
        "events that do")
    assert entries[0]["hooks"] == [{"type": "command",
                                    "command": GUARD_COMMAND,
                                    "timeout": GUARD_TIMEOUT}]
    assert GUARD_COMMAND in COMMAND.read_text(encoding="utf-8"), (
        "the command string this test asserts on is the one the file writes")


@NEEDS_JQ
def test_the_guard_entry_carries_no_or_true_and_that_is_the_mechanism(tmp_path):
    """`|| true` ON THIS ENTRY WOULD INSTALL A GUARD THAT REFUSES NOTHING.

    Exit 2 is what BLOCKS a `UserPromptSubmit` prompt
    (code.claude.com/docs/en/hooks) and `cmd || true` exits 0 for every code the
    command can produce, so the suffix that is the `SessionStart` entry's whole
    safety property is this one's whole defeat — and silently, which is the
    exact state Amendment 12 exists to end. Asserted separately from the shape
    above because copying the neighbouring string is the obvious way to write
    this and the result would pass every other test in this file.
    """
    assert run_cmd("--install", home=tmp_path).returncode == 0
    assert user_prompt_commands(tmp_path) == [GUARD_COMMAND]
    assert "|| true" not in GUARD_COMMAND
    assert "|| true" in HOOK_COMMAND, (
        "the SessionStart entry keeps its suffix; only this one must not")


@NEEDS_JQ
def test_installing_twice_adds_one_guard_entry_and_not_two(tmp_path):
    """Idempotent by EXACT MATCH, the same as the entry beside it — and firing
    this hook twice is two refusals for one prompt."""
    assert run_cmd("--install", home=tmp_path).returncode == 0
    second = run_cmd("--install", home=tmp_path)
    assert second.returncode == 0, second.stderr
    assert user_prompt_commands(tmp_path) == [GUARD_COMMAND]
    assert "UserPromptSubmit guard: already installed" in second.stdout


@NEEDS_JQ
def test_a_differing_guard_entry_refuses_and_places_nothing(tmp_path):
    """A SECOND WRITER OF THIS VERY HOOK, and the same refusal its neighbour
    makes: merging beside it would fire the name guard twice, which is two
    refusals for one prompt, and repairing a setting a person meant is not an
    installer's to do."""
    rival = "~/bin/lane-hook.sh guard"
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {"UserPromptSubmit": [
        {"hooks": [{"type": "command", "command": rival, "timeout": 5}]}]}}),
        encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "a UserPromptSubmit entry that runs `guard` with a" in result.stderr
    assert "DIFFERENT command string" in result.stderr
    assert "NOTHING was installed" in result.stderr
    assert GUARD_COMMAND in result.stderr, "the refusal prints the exact block"
    assert user_prompt_commands(tmp_path) == [rival], "it changed the file"
    assert not (tmp_path / ".local" / "bin").exists(), (
        "the refusal must cost a whole install, not half of one")


@NEEDS_JQ
def test_our_own_guard_entry_beside_a_rival_refuses_the_same_way(tmp_path):
    """THE SAME ORDER ON THIS ARM, IN THE SAME COMMIT (#59).

    The two reads are one question asked of two events, and the whole reason
    they are a byte-for-byte mirror is that an arm answering something the other
    does not is how a person comes to be policed for one entry of a pair and not
    for the other. So the ordering #59 fixes is the pair's, not the
    `SessionStart` arm's: with our guard entry beside a second writer of this
    very hook, the run refuses, names the rival as well as the block it would
    have placed, and installs nothing — two refusals for one prompt is the harm
    either way round, and it does not become harmless because one of the two
    writers is ours.
    """
    rival = "~/bin/other.sh guard"
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    before = json.dumps({"model": "opus", "hooks": {"UserPromptSubmit": [
        {"hooks": [{"type": "command", "command": GUARD_COMMAND,
                    "timeout": GUARD_TIMEOUT}]},
        {"hooks": [{"type": "command", "command": rival, "timeout": 5}]}]}},
        indent=2)
    settings.write_text(before, encoding="utf-8")
    os.chmod(settings, 0o644)

    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "a UserPromptSubmit entry that runs `guard` with a" in result.stderr
    assert "DIFFERENT command string" in result.stderr
    assert rival in result.stderr, (
        "the refusal must NAME the rival: this file carries ours too\n"
        + result.stderr)
    assert GUARD_COMMAND in result.stderr, "the refusal prints the exact block"
    assert "NOTHING was installed" in result.stderr
    assert settings.read_text(encoding="utf-8") == before, "it changed the file"
    assert stat.S_IMODE(settings.stat().st_mode) == 0o644, (
        "the `present` arm's mode stamp ran on a file the merge refused")
    assert session_start_commands(tmp_path) == [], (
        "the SessionStart entry would have merged cleanly, and must not be "
        "placed while its pair refuses")
    assert not (tmp_path / ".local" / "bin").exists(), (
        "the refusal must cost a whole install, not half of one")


@NEEDS_JQ
def test_an_entry_that_merely_names_guard_in_a_path_is_no_conflict(tmp_path):
    """THE VERB IS WHAT COLLIDES, NOT THE FILE THAT CARRIES IT — R-A9-14's rule
    one event over, and this is where it BITES rather than being a nicety.

    `~/projects/xFactory/guard.sh` is a plain `UserPromptSubmit` hook a person's
    settings may already carry, and this estate's do: the usage guard. Keyed on
    `guard` as a substring it would be read as a competing writer of Amendment
    12's hook and the whole install would refuse; keyed on the verb with a
    boundary on both sides it is what it is — somebody's own setting, kept
    exactly where it is, with ours added beside it.
    """
    other = "~/projects/xFactory/guard.sh"
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {"UserPromptSubmit": [
        {"hooks": [{"type": "command", "command": other, "timeout": 5}]}]}}),
        encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert user_prompt_commands(tmp_path) == [other, GUARD_COMMAND]


@NEEDS_JQ
def test_the_two_entries_are_one_all_or_nothing_merge(tmp_path):
    """A SETTINGS FILE THAT TOOK ONE OF THE PAIR IS A HALF-INSTALL OF A HOOK
    PAIR, and nothing on screen would say which half.

    The conflict here is on the GUARD entry alone — the file's `SessionStart`
    is empty and would merge cleanly — so this is the case that proves the
    all-or-nothing rule covers the pair and not each entry separately. Both
    merges are computed into one staged file before either is placed, so the
    refusal leaves the settings file exactly as it was: no `SessionStart` entry
    either.
    """
    rival = "~/bin/other.sh guard"
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    before = json.dumps({"model": "opus", "hooks": {"UserPromptSubmit": [
        {"hooks": [{"type": "command", "command": rival, "timeout": 5}]}]}})
    settings.write_text(before, encoding="utf-8")
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert settings.read_text(encoding="utf-8") == before, (
        "the refusal wrote nothing at all")
    assert session_start_commands(tmp_path) == [], (
        "the SessionStart entry would have merged cleanly, and must not be "
        "placed while its pair refuses")
    assert not (tmp_path / ".local" / "bin").exists()


@NEEDS_JQ
def test_one_write_places_both_entries_in_one_file(tmp_path):
    """ONE WRITE FOR THE TWO ENTRIES. They live in one file, and writing it
    twice would move a person's settings through a state carrying one of the
    pair — which is the half-install the test above refuses, reached by the
    happy path instead of by a conflict."""
    result = run_cmd("--install", home=tmp_path)
    assert result.returncode == 0, result.stderr
    assert session_start_commands(tmp_path) == [HOOK_COMMAND]
    assert user_prompt_commands(tmp_path) == [GUARD_COMMAND]
    assert stat.S_IMODE(settings_of(tmp_path).stat().st_mode) == 0o600
