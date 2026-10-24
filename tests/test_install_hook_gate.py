# SPDX-License-Identifier: Apache-2.0
"""The gate on `--install`'s hook pair (opensoft/openRepoTools#237).

THE DEFECT. `--install` merged the `SessionStart` entry and Amendment 12's
`UserPromptSubmit` name guard into `~/.claude/settings.json` before anything had
placed the path both of them call, `~/projects/xFactory/lanes-edit.sh` — a
symlink `link-estates` makes, and that only `openRepoTools wip init` runs on a
fresh workstation, AFTER the install (opensoft/workBenches#107, whose `setup.sh`
orders the two that way on purpose). The `SessionStart` entry ends in `|| true`
and swallowed it; the guard has no such suffix by design, so a bare `claude`
got a command-not-found hook error at every prompt: exit 127, where the guard's
whole mechanism is exit 2.

THE RULE NOW IS THE LAUNCHER'S OWN (the lead's ruling 1, approach (A)). The pair
is merged only once that path exists, is executable and answers `guard`, by the
probe opensoft/workBenches' `claude-profile` puts to the same path before it
ensures the same two strings in each profile. Until then the pair is DEFERRED
and every run says so, with the remedy; where a file already carries OUR guard
entry and the path does not answer, that entry alone is taken out — the
launcher's downgrade (workBenches#90), filtered on the nested array
(workBenches#89) — and the `SessionStart` entry, which cannot fail a session, is
left. `wip init` completes the pair after `link-estates`, and on its "nothing
to do" path too.

THE CONTRACT CHANGE IS THE COUNT: twenty-nine artifacts always, plus the two
hook entries once the target answers. The strings, their exact-match identity,
the rival refusal, the receipt and the guard's real exit 2 do not move, and
the cases below hold each of them.

NO NETWORK, NO REAL HOME: every run is from the checkout into a sandbox `HOME`
under `tmp_path`, with every `LANES_*`, `TMUX*` and `CLAUDE_*` variable of the
shell running the suite taken out, and `wip init` meets the bare-repository
`gh` of `tests/test_wip_init_command.py`.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import stat
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
from test_install_skill_and_hook import (GUARD_COMMAND, GUARD_TIMEOUT,
                                         HOOK_COMMAND, HOOK_MATCHER,
                                         HOOK_TIMEOUT, hook_commands,
                                         run_signalled_at_the_settings_temporary,
                                         session_start_commands, settings_of,
                                         user_prompt_commands)
from test_openrepotools_command import (ALWAYS, ARTIFACTS, COMMAND,
                                        HOOK_ENTRIES, NEEDS_JQ, command_env,
                                        link_xfactory, placed_files,
                                        placement_temporaries, receipt_rows)
from test_wip_init_command import NEEDS_TEMPLATE, fake_gh, wip_env

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="openRepoTools is a bash script"),
              WINDOWS_SKIP, NEEDS_JQ]

#: The words every deferral and every removal ends with: the remedy, both ways.
REMEDY = ("`openRepoTools wip init` runs", "`link-estates`",
          "`openRepoTools --install` again")


def scrubbed(environ: dict) -> dict:
    """`environ` with nothing of the shell running the suite that a lane tool
    reads: no `LANES_*` (the real register), no `TMUX*` (the real window), no
    `CLAUDE_*` (`CLAUDE_NO_LANE` exempts the guard; `CLAUDE_USER_DIR` would move
    `~/.claude` out of the sandbox), no `WORKBENCHES_*`, no `PROJECTS_ROOT`,
    and no data directory but the sandbox's own."""
    for name in list(environ):
        if name.startswith(("LANES_", "TMUX", "CLAUDE_", "WORKBENCHES_")) or \
                name in ("PROJECTS_ROOT", "XDG_DATA_HOME", "OPENREPOTOOLS_DATA_DIR"):
            environ.pop(name)
    return environ


def install(home: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    """`openRepoTools --install` from the checkout, into `home`."""
    environ = scrubbed(command_env(home))
    environ["CLAUDE_PROFILES_HOME"] = str(home / ".claude-profiles")
    environ["CLAUDE_USER_DIR"] = str(home / ".claude")
    environ.update(env or {})
    return subprocess.run(["bash", str(COMMAND), "--install"],
                          capture_output=True, text=True, check=False,
                          input="", cwd=str(REPO), env=environ)


def wip_world(tmp_path: Path) -> tuple[Path, dict]:
    """A sandbox `HOME` and the environment both halves of a fresh workstation
    run in — `--install` and then `wip init`, workBenches' own order — with ONE
    bin directory, so the `link-estates` that `wip init` runs is the one this
    `--install` placed, and the `lanes-edit.sh` it links is that one too."""
    home = tmp_path / "home"
    (home / "projects").mkdir(parents=True)
    return home, scrubbed(wip_env(home, fake_gh(tmp_path)))


def run_with(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(COMMAND), *args], capture_output=True,
                          text=True, check=False, input="", cwd=str(REPO),
                          env=env)


def naming_the_target(home: Path) -> list[str]:
    """Every hook command in `home`'s settings that calls the gated path."""
    if not settings_of(home).exists():
        return []
    return [c for event in ("SessionStart", "UserPromptSubmit")
            for c in hook_commands(home, event)
            if "~/projects/xFactory/lanes-edit.sh" in c]


def our_pair(home: Path, *, mode: int = 0o644) -> Path:
    """`home`'s settings carrying both of OUR entries, as a run before #237
    left them, beside foreign hooks — one of them GROUPED with our guard in a
    single entry, the hand-edit workBenches#89 is about."""
    settings = settings_of(home)
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({
        "model": "opus",
        "statusLine": {"type": "command", "command": "~/.claude/statusline.sh"},
        "hooks": {
            "SessionStart": [
                {"matcher": HOOK_MATCHER,
                 "hooks": [{"type": "command", "command": HOOK_COMMAND,
                            "timeout": HOOK_TIMEOUT}]},
                {"matcher": "startup",
                 "hooks": [{"type": "command", "command": "~/bin/hello.sh"}]}],
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": GUARD_COMMAND,
                            "timeout": GUARD_TIMEOUT}]},
                {"hooks": [{"type": "command",
                            "command": "~/projects/xFactory/guard.sh",
                            "timeout": 5}]},
                {"note": "operator grouped these",
                 "hooks": [{"type": "command", "command": GUARD_COMMAND},
                           {"type": "command", "command": "~/bin/audit.sh"}]},
                {"hooks": []}],
            "PreToolUse": [{"matcher": "Bash",
                            "hooks": [{"type": "command", "command": "audit"}]}],
        },
    }, indent=2), encoding="utf-8")
    os.chmod(settings, mode)
    return settings


# --- a fresh workstation, before `wip init` -----------------------------------

def test_fresh_install_defers_the_hook_pair_and_says_so(tmp_path):
    """THE DEFECT'S OWN CASE: no workspace, no link. The pair is deferred —
    neither entry is written, so no settings file is made for nothing — and
    each entry's line says so, why, and what completes it."""
    result = install(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    settings = settings_of(tmp_path)
    target = tmp_path / "projects" / "xFactory" / "lanes-edit.sh"
    assert not settings.exists(), "a deferred pair has nothing to write"
    assert f"SessionStart hook: deferred, not added to {settings}, because " \
           f"{target} is not there" in result.stdout, result.stdout
    assert f"UserPromptSubmit guard: deferred, not added to {settings}, because " \
           f"{target} is not there" in result.stdout, result.stdout
    for words in REMEDY:
        assert words in result.stdout, f"the remedy lost {words!r}:\n{result.stdout}"
    assert "~/projects/xFactory has to exist first" in result.stdout, (
        "with no ~/projects/xFactory the remedy alone loops (the #237 review, N6)")
    assert "REMOVED" not in result.stdout, "there was nothing of ours to remove"


def test_deferred_install_places_29_and_writes_29_receipt_rows(tmp_path):
    """TWENTY-NINE ARTIFACTS ALWAYS: the seventeen files, the six skill copies
    and the six command files are placed whether or not the pair can be, and
    the receipt — which never had hook rows — says the same twenty-nine. A
    second run reports exactly those twenty-nine `unchanged`, and no line of
    the deferred pair claims to be one of them."""
    assert ALWAYS == ARTIFACTS - HOOK_ENTRIES == 29
    first = install(tmp_path)
    assert first.returncode == 0, first.stdout + first.stderr
    for dest in placed_files(tmp_path):
        assert Path(dest).is_file(), f"{dest} was not placed:\n{first.stdout}"
    assert len(placed_files(tmp_path)) == ALWAYS
    assert len(receipt_rows(tmp_path)) == ALWAYS
    second = install(tmp_path)
    assert second.returncode == 0, second.stdout + second.stderr
    assert second.stdout.count("unchanged") == ALWAYS, second.stdout
    assert "deferred, not added" in second.stdout


@pytest.mark.parametrize("state", ["nothing", "the estate directory",
                                   "settings of the person's own"])
def test_interrupted_setup_leaves_no_hook_naming_a_missing_path(tmp_path, state):
    """SETUP CUT OFF BETWEEN THE INSTALL AND `wip init`, in the three states it
    leaves: no `~/projects/xFactory` at all; the directory there and no link in
    it (`link-estates` never ran); and a settings file of the person's own.
    In none of them is there a hook that calls the missing path — so there is
    no prompt hook to fail, and the person's own hooks are exactly as they
    were — and so is that file's MODE: a deferred run with nothing of ours to
    add or take out writes nothing, so the 644 it found is the 644 it leaves
    (the #237 review, M1)."""
    own = {"hooks": {"UserPromptSubmit": [
        {"hooks": [{"type": "command", "command": "~/projects/xFactory/guard.sh"}]}]}}
    if state == "the estate directory":
        (tmp_path / "projects" / "xFactory").mkdir(parents=True)
    if state == "settings of the person's own":
        settings_of(tmp_path).parent.mkdir(parents=True)
        settings_of(tmp_path).write_text(json.dumps(own), encoding="utf-8")
        os.chmod(settings_of(tmp_path), 0o644)
    result = install(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert naming_the_target(tmp_path) == [], (
        "a hook calls a path that does not exist:\n" + result.stdout)
    if state == "settings of the person's own":
        assert json.loads(settings_of(tmp_path).read_text(encoding="utf-8")) == own
        assert stat.S_IMODE(settings_of(tmp_path).stat().st_mode) == 0o644, (
            "a run that wrote nothing into the file changed its mode")
    assert not (tmp_path / "projects" / "xFactory" / "lanes-edit.sh").exists()


# --- an existing install whose target stopped answering (the migration) -------

def test_dangling_link_strips_only_our_guard_entry_keeps_session_start_foreign_hooks_and_600(
        tmp_path):
    """THE WORKSTATION THAT ALREADY HAS THE PAIR, AND A LINK THAT DANGLES — a
    bench recreate that emptied the far end, or a link into a tree that went.

    Our exact guard entry is taken out, because left there it fails every
    prompt. NOTHING ELSE MOVES: the `SessionStart` entry (its `|| true` keeps
    it inert), the person's own `UserPromptSubmit` hooks, the foreign command
    GROUPED with ours in one entry — kept with that entry's own `note` — an
    entry with an empty `hooks`, and every key outside `hooks`. The file comes
    back at 600 from the 644 it had. A second run removes nothing more and
    writes nothing.
    """
    far = tmp_path / "gone" / "lanes-edit.sh"
    link_xfactory(tmp_path, far)
    settings = our_pair(tmp_path)
    before = json.loads(settings.read_text(encoding="utf-8"))

    result = install(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    after = json.loads(settings.read_text(encoding="utf-8"))
    target = tmp_path / "projects" / "xFactory" / "lanes-edit.sh"
    assert f"UserPromptSubmit guard: REMOVED from {settings}, because {target} " \
           f"is a symlink to {far}, which does not resolve" in result.stdout, result.stdout
    assert f"SessionStart hook: left in {settings} as an earlier run placed it" \
        in result.stdout, result.stdout
    for words in REMEDY:
        assert words in result.stdout, words

    assert after["hooks"]["UserPromptSubmit"] == [
        {"hooks": [{"type": "command", "command": "~/projects/xFactory/guard.sh",
                    "timeout": 5}]},
        {"note": "operator grouped these",
         "hooks": [{"type": "command", "command": "~/bin/audit.sh"}]},
        {"hooks": []}]
    assert after["hooks"]["SessionStart"] == before["hooks"]["SessionStart"]
    for key in ("model", "statusLine"):
        assert after[key] == before[key], key
    assert after["hooks"]["PreToolUse"] == before["hooks"]["PreToolUse"]
    assert stat.S_IMODE(settings.stat().st_mode) == 0o600

    written = settings.read_bytes()
    second = install(tmp_path)
    assert second.returncode == 0, second.stdout + second.stderr
    assert settings.read_bytes() == written, "a second deferred run rewrote the file"
    assert "REMOVED" not in second.stdout
    assert f"UserPromptSubmit guard: deferred, not added to {settings}" in second.stdout


def test_a_guard_entry_in_a_shape_it_cannot_take_apart_is_refused_not_rewritten(
        tmp_path):
    """A `UserPromptSubmit` that is not an array, carrying our command, against
    a target that does not answer: the entry would fail every prompt, and the
    file is not one this command understands well enough to rewrite. So it
    refuses, names the entry, and leaves the file exactly as it was — IN THE
    PLANNING PHASE, with nothing placed, like every other file this merge
    cannot handle (the #237 review, M2: it used to refuse after placing 29)."""
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    odd = json.dumps({"hooks": {"UserPromptSubmit": {"ours": {"hooks": [
        {"type": "command", "command": GUARD_COMMAND, "timeout": 5}]}}}})
    settings.write_text(odd, encoding="utf-8")
    result = install(tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "is not the array of entries this command takes apart" in result.stderr
    assert GUARD_COMMAND in result.stderr, "the refusal names the entry"
    assert "NOTHING was installed" in result.stderr, result.stderr
    assert settings.read_text(encoding="utf-8") == odd
    assert not (tmp_path / ".local" / "bin").exists(), (
        "the refusal came after the commands were placed")
    assert not (tmp_path / ".claude" / "skills").exists()


def test_an_odd_guard_entry_beside_a_link_the_bin_loop_repairs_is_not_refused(tmp_path):
    """THE ONE TARGET A RUN CAN STILL MAKE ANSWER is let through planning: a
    `link-estates` link to the bin directory's own `lanes-edit.sh`, dangling
    until this run's bin loop puts the far end back. After that loop the target
    answers, so the guard entry — whatever shape it is in — is ours and stays,
    and the run completes instead of refusing."""
    link_xfactory(tmp_path)
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    odd = {"hooks": {"UserPromptSubmit": {"ours": {"hooks": [
        {"type": "command", "command": GUARD_COMMAND, "timeout": 5}]}}}}
    settings.write_text(json.dumps(odd), encoding="utf-8")
    result = install(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    after = json.loads(settings.read_text(encoding="utf-8"))
    assert after["hooks"]["UserPromptSubmit"] == odd["hooks"]["UserPromptSubmit"]
    assert session_start_commands(tmp_path) == [HOOK_COMMAND]


@pytest.mark.parametrize("why", ["no guard verb", "not executable", "not readable"])
def test_lanes_edit_without_guard_verb_defers(tmp_path, why):
    """A `lanes-edit.sh` THAT IS THERE AND DOES NOT ANSWER `guard`: one that
    predates the verb, or one that is not executable. The probe is the
    launcher's — comment lines dropped, the case arm anchored where a line
    begins — so neither the word `guard` in a comment nor an arm that merely
    starts with it (`guards)`) passes for the verb. The pair is deferred, and a
    guard entry already there is taken out, with the reason named — an
    executable that cannot be READ by its own name, not as a missing verb."""
    if why == "not readable" and hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root reads a file whose mode says otherwise")
    old = tmp_path / "old" / "lanes-edit.sh"
    old.parent.mkdir()
    old.write_text(
        "#!/usr/bin/env bash\n"
        "# the dispatcher guard), so no READ can return it\n"
        'case "$1" in\n'
        "  session-start) exit 0 ;;\n"
        "  guards) exit 0 ;;\n"
        '  *) echo "unknown subcommand" >&2; exit 2 ;;\n'
        "esac\n", encoding="utf-8")
    if why == "no guard verb":
        old.chmod(0o755)
        reason = "has no `guard` subcommand"
    else:
        old.write_text(old.read_text(encoding="utf-8") + "# guard)\n  guard) exit 0 ;;\n",
                       encoding="utf-8")
        old.chmod(0o644 if why == "not executable" else 0o111)
        reason = "is " + why
    link_xfactory(tmp_path, old)
    settings = our_pair(tmp_path, mode=0o600)
    result = install(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    target = tmp_path / "projects" / "xFactory" / "lanes-edit.sh"
    assert f"REMOVED from {settings}, because {target} {reason}" in result.stdout, \
        result.stdout
    assert GUARD_COMMAND not in user_prompt_commands(tmp_path)
    assert session_start_commands(tmp_path)[0] == HOOK_COMMAND


def test_a_link_into_an_emptied_bin_directory_answers_once_the_bin_loop_refills_it(
        tmp_path):
    """THE GATE IS ASKED AFTER THE BIN LOOP, and this is why. A bench recreate
    empties `~/.local/bin` and leaves `link-estates`' link dangling over it; the
    next `--install` puts the far end back in its own bin loop. Asked before
    that loop, the gate would defer — and strip — the pair on the very run that
    repaired its target. Asked after it, the pair goes in on that run."""
    link = link_xfactory(tmp_path)
    assert not link.exists(), "the fixture's link must dangle before the install"
    result = install(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert session_start_commands(tmp_path) == [HOOK_COMMAND]
    assert user_prompt_commands(tmp_path) == [GUARD_COMMAND]
    assert "deferred" not in result.stdout


# --- the rival refusal does not move ------------------------------------------

@pytest.mark.parametrize("event,rival", [
    ("SessionStart", "~/bin/lane-hook.sh session-start || true"),
    ("UserPromptSubmit", "~/bin/lane-hook.sh guard"),
])
def test_rival_refuses_while_deferred(tmp_path, event, rival):
    """A SECOND WRITER OF EITHER HOOK REFUSES THE WHOLE INSTALL, deferred or
    not: the rival read comes before the gate is asked, so a workstation with
    no link yet is refused for the rival exactly as one with the link is, and
    nothing at all is placed."""
    entry = {"hooks": [{"type": "command", "command": rival, "timeout": 5}]}
    if event == "SessionStart":
        entry["matcher"] = HOOK_MATCHER
    settings = settings_of(tmp_path)
    settings.parent.mkdir(parents=True)
    before = json.dumps({"hooks": {event: [entry]}})
    settings.write_text(before, encoding="utf-8")
    result = install(tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "DIFFERENT command string" in result.stderr
    assert rival in result.stderr, "the refusal names the rival"
    assert "NOTHING was installed" in result.stderr
    assert settings.read_text(encoding="utf-8") == before
    assert not (tmp_path / ".local" / "bin").exists()


@pytest.mark.parametrize("target", ["answers", "does not answer"])
def test_without_jq_install_still_ends_in_the_jq_refusal(tmp_path, target):
    """THE `jq` REFUSAL COMES FIRST, WHATEVER THE GATE WOULD SAY. The gate is
    asked only at placement, after the bin loop; `plan_hook_merge` asks for
    `jq` before anything is placed, as it always has. So with no `jq` on the
    PATH, `--install` refuses naming it — exit 2, the message opening the
    stream, the two entries printed, nothing placed — both on a workstation
    whose target answers `guard` and on one where the pair would be deferred
    (006's FR-018, which its no-`jq` test depends on)."""
    if target == "answers":
        link_xfactory(tmp_path)
    stub = tmp_path / "nojq"
    stub.mkdir()
    for name in ("bash", "git", "cp", "mkdir", "chmod", "cmp", "printf",
                 "mktemp", "sed", "cat", "tr", "grep", "head", "dirname",
                 "rm", "mv", "awk", "readlink"):
        found = shutil.which(name)
        if found:
            (stub / name).symlink_to(found)
    result = install(tmp_path, env={"PATH": str(stub)})
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stderr.startswith(
        "\nREFUSED: `--install` needs `jq` to merge its TWO hook entries"), result.stderr
    assert HOOK_COMMAND in result.stderr and GUARD_COMMAND in result.stderr
    assert not (tmp_path / ".local" / "bin").exists(), "a file was placed"
    assert not settings_of(tmp_path).exists()


# --- `wip init` completes the pair ---------------------------------------------

@NEEDS_TEMPLATE
def test_wip_init_completes_the_pair_after_link_estates(tmp_path):
    """THE WORKSTATION'S WHOLE FIRST RUN, in workBenches' order: `--install`
    defers the pair, because nothing has linked its target yet; `wip init`
    creates the workspace, runs `link-estates` — which links
    `~/projects/xFactory/lanes-edit.sh` to the installed one — and then merges
    the pair, one entry each, at mode 600, without anyone touching the
    settings file by hand."""
    home, env = wip_world(tmp_path)
    (home / "projects" / "xFactory").mkdir()
    first = run_with(env, "--install")
    assert first.returncode == 0, first.stdout + first.stderr
    assert "deferred, not added" in first.stdout
    assert naming_the_target(home) == []

    result = run_with(env, "wip", "init")
    assert result.returncode == 0, result.stdout + result.stderr
    link = home / "projects" / "xFactory" / "lanes-edit.sh"
    assert link.is_symlink() and link.resolve() == (home / "bin" / "lanes-edit.sh").resolve()
    assert f"LINK  {link}" in result.stdout, result.stdout
    assert result.stdout.index("link-estates:") < result.stdout.index("hook entries in"), (
        "the pair is reconciled AFTER link-estates, which places its target")
    assert session_start_commands(home) == [HOOK_COMMAND]
    assert user_prompt_commands(home) == [GUARD_COMMAND]
    assert stat.S_IMODE(settings_of(home).stat().st_mode) == 0o600
    assert "SessionStart hook: installed in" in result.stdout, result.stdout
    assert "UserPromptSubmit guard: installed in" in result.stdout


@NEEDS_TEMPLATE
@pytest.mark.parametrize("signame", ["SIGINT", "SIGTERM"])
def test_a_wip_init_killed_while_the_settings_temporary_exists_leaves_none(
        tmp_path, signame):
    """`wip init` WRITES THE PAIR IN A SUBSHELL, AND THE SUBSHELL CLEANS UP
    AFTER ITSELF (#332). `wip_hook_pair` runs planning and the write in one
    `( … )`, which bash does not give the `EXIT` and `INT` traps `workdir` set,
    and the `$PLACING` that `hook_write_settings` sets there is the subshell's
    own: the traps of the shell around it ran with it empty, so a Ctrl-C or a
    `kill` of the group left `settings.json.openrepotools.<pid>.XXXXXX` in
    `~/.claude`, even where `--install`'s own run no longer did. The subshell's
    own `EXIT` trap removes it.

    The second `wip init` finds the workspace made, so it only reconciles the
    pair, and it writes the file whole because the first one's was removed. A
    `cp` that sleeps for the settings temporary holds it there, and the signal
    goes to the whole group, where the subshell is the first to take it."""
    home, env = wip_world(tmp_path)
    (home / "projects" / "xFactory").mkdir()
    assert run_with(env, "--install").returncode == 0
    first = run_with(env, "wip", "init")
    assert first.returncode == 0, first.stdout + first.stderr
    settings_of(home).unlink()

    code, out, err, seen = run_signalled_at_the_settings_temporary(
        home, env, ["wip", "init"], signame, True,
        tmp_path / "slow-settings-cp", cwd=REPO)
    sig = getattr(signal, signame)
    assert seen, (f"`wip init` never made a settings temporary for the signal "
                  f"to land beside: exit {code}\n{out}{err}")
    assert code in (-sig, 128 + sig), (
        f"`wip init` did not die of {signame}: exit {code}\n{out}{err}")
    assert placement_temporaries(home) == [], (
        f"a settings temporary outlived `wip init`: {seen}")


@NEEDS_TEMPLATE
def test_wip_init_nothing_to_do_still_reconciles_the_pair(tmp_path):
    """STEP 1's "NOTHING TO DO" IS NOT WHERE THE PAIR IS LEFT DEFERRED. A first
    `wip init` on a workstation with no `~/projects/xFactory` cannot link the
    target, so the pair stays deferred and says so; once the link is there, the
    next run — which finds the workspace and does nothing to it — completes the
    pair, and the one after that writes nothing."""
    home, env = wip_world(tmp_path)
    assert run_with(env, "--install").returncode == 0
    first = run_with(env, "wip", "init")
    assert first.returncode == 0, first.stdout + first.stderr
    assert "deferred, not added" in first.stdout, first.stdout
    assert naming_the_target(home) == []

    link_xfactory(home, home / "bin" / "lanes-edit.sh")
    second = run_with(env, "wip", "init")
    assert second.returncode == 0, second.stdout + second.stderr
    assert "nothing to do" in second.stdout
    assert session_start_commands(home) == [HOOK_COMMAND]
    assert user_prompt_commands(home) == [GUARD_COMMAND]

    written = settings_of(home).read_bytes()
    third = run_with(env, "wip", "init")
    assert third.returncode == 0, third.stdout + third.stderr
    assert settings_of(home).read_bytes() == written
    assert "UserPromptSubmit guard: already installed" in third.stdout


@NEEDS_TEMPLATE
def test_wip_init_rerun_links_and_completes_a_pair_a_cut_run_left_unlinked(tmp_path):
    """A RUN CUT OFF BEFORE LINKING HEALS ON THE NEXT RUN (the lead's ruling 3).
    The first `wip init` wrote the workspace and could not link the target —
    here, because `~/projects/xFactory` was not there yet. The re-run finds the
    workspace, sees the target does not answer and that the directory it goes
    into is there now, runs `link-estates` again, and completes the pair."""
    home, env = wip_world(tmp_path)
    assert run_with(env, "--install").returncode == 0
    assert run_with(env, "wip", "init").returncode == 0
    (home / "projects" / "xFactory").mkdir()
    rerun = run_with(env, "wip", "init")
    assert rerun.returncode == 0, rerun.stdout + rerun.stderr
    assert "nothing to do" in rerun.stdout
    assert "so link-estates runs again" in rerun.stdout, rerun.stdout
    assert (home / "projects" / "xFactory" / "lanes-edit.sh").is_symlink()
    assert user_prompt_commands(home) == [GUARD_COMMAND]
    assert session_start_commands(home) == [HOOK_COMMAND]


@NEEDS_TEMPLATE
@pytest.mark.parametrize("state", ["the target answers", "no ~/projects/xFactory"])
def test_wip_init_nothing_to_do_reruns_link_estates_only_where_ruling_9_says(
        tmp_path, state):
    """RULING 9's OTHER HALF: step 1 runs `link-estates` again ONLY where the
    target does not answer AND `~/projects/xFactory` is there for the link. A
    healthy workstation's re-run does not relink, and neither does one with no
    `~/projects/xFactory`, where a relink could change nothing."""
    home, env = wip_world(tmp_path)
    if state == "the target answers":
        (home / "projects" / "xFactory").mkdir()
    assert run_with(env, "--install").returncode == 0
    assert run_with(env, "wip", "init").returncode == 0
    rerun = run_with(env, "wip", "init")
    assert rerun.returncode == 0, rerun.stdout + rerun.stderr
    assert "nothing to do" in rerun.stdout
    for marker in ("link-estates runs again", "link-estates:",
                   "link-estates is not installed"):
        assert marker not in rerun.stdout, f"{marker!r} on a re-run:\n{rerun.stdout}"


@NEEDS_TEMPLATE
def test_a_hook_reconcile_wip_init_cannot_make_is_a_note_and_the_exit_stays_0(tmp_path):
    """ONE RULE ON BOTH PATHS (the #237 review, S1). A second writer of the
    guard, added after `--install`, makes the reconcile refuse — with
    `--install`'s own refusal, naming the rival. On step 10's path the
    workspace is made all the same, so the refusal is a note, `Done.` is
    printed and the exit is 0; on step 1's path, where the reconcile is the
    only act, the exit is 0 too, and the note says so. The file is left
    exactly as it was both times."""
    home, env = wip_world(tmp_path)
    (home / "projects" / "xFactory").mkdir()
    assert run_with(env, "--install").returncode == 0
    rival = "~/bin/other.sh guard"
    settings = settings_of(home)
    settings.parent.mkdir(parents=True, exist_ok=True)
    before = json.dumps({"hooks": {"UserPromptSubmit": [
        {"hooks": [{"type": "command", "command": rival, "timeout": 5}]}]}})
    settings.write_text(before, encoding="utf-8")

    fresh = run_with(env, "wip", "init")
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr
    assert "(not reconciled:" in fresh.stdout, fresh.stdout
    assert rival in fresh.stderr, "the refusal names the rival"
    assert "Done." in fresh.stdout, "the workspace step did not finish"
    assert settings.read_text(encoding="utf-8") == before

    again = run_with(env, "wip", "init")
    assert again.returncode == 0, again.stdout + again.stderr
    assert "nothing to do" in again.stdout
    assert "(not reconciled:" in again.stdout, again.stdout
    assert rival in again.stderr
    assert settings.read_text(encoding="utf-8") == before


@NEEDS_TEMPLATE
@pytest.mark.parametrize("where", ["a fresh workstation", "one with a workspace"])
def test_wip_init_dry_run_names_the_hook_merge(tmp_path, where):
    """`--dry-run` SAYS IT WOULD MERGE THE PAIR, and writes nothing: no settings
    file on a fresh workstation, and none on one whose workspace is there and
    whose target does not answer yet."""
    home, env = wip_world(tmp_path)
    if where == "one with a workspace":
        assert run_with(env, "wip", "init").returncode == 0
        assert not settings_of(home).exists()
        (home / "projects" / "xFactory").mkdir()
    result = run_with(env, "wip", "init", "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "would merge   the SessionStart and UserPromptSubmit hook entries" \
        in result.stdout, result.stdout
    assert f"{home / '.claude' / 'settings.json'}" in result.stdout
    assert not settings_of(home).exists(), "a dry run wrote the settings file"
    assert not (home / "projects" / "xFactory" / "lanes-edit.sh").exists()
    if where == "one with a workspace":
        assert "would run     link-estates" in result.stdout


@NEEDS_TEMPLATE
def test_repeat_install_after_init_is_unchanged_one_entry_each(tmp_path):
    """ONCE THE TARGET ANSWERS, `--install` IS WHAT IT WAS: a repeat after
    `wip init` reports all thirty-one artifacts `unchanged`, rewrites nothing,
    and leaves exactly one entry of each."""
    home, env = wip_world(tmp_path)
    (home / "projects" / "xFactory").mkdir()
    assert run_with(env, "--install").returncode == 0
    assert run_with(env, "wip", "init").returncode == 0
    written = settings_of(home).read_bytes()
    again = run_with(env, "--install")
    assert again.returncode == 0, again.stdout + again.stderr
    assert again.stdout.count("unchanged") == ARTIFACTS, again.stdout
    assert settings_of(home).read_bytes() == written
    assert session_start_commands(home) == [HOOK_COMMAND]
    assert user_prompt_commands(home) == [GUARD_COMMAND]


# --- the guard's real refusal is still exit 2 ------------------------------------

def guard_run(home: Path, tmp_path: Path, command: str) -> subprocess.CompletedProcess:
    """The hook's own command string, run the way the harness runs it: by a
    shell that expands its `~` against `HOME`, with the hook's JSON on stdin and
    a `cwd` under the projects root, outside tmux. `tmux` itself answers
    nothing, so no real server is ever asked."""
    cwd = home / "projects" / "somewhere"
    cwd.mkdir(parents=True, exist_ok=True)
    fakebin = tmp_path / "no-tmux"
    fakebin.mkdir(exist_ok=True)
    (fakebin / "tmux").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (fakebin / "tmux").chmod(0o755)
    environ = scrubbed(dict(os.environ))
    environ.update(HOME=str(home), AGENT_PROTOCOL_ROOT=str(home / ".agents"),
                   PATH=f"{fakebin}{os.pathsep}{environ.get('PATH', '')}")
    # COMPACT, as the harness writes it: the guard reads `"cwd":"…"` with no
    # space after the colon, and an input it cannot read a `cwd` out of is a
    # refusal of its own (clause (d)) — the right exit for the wrong reason.
    payload = json.dumps({"session_id": "a-bare-claude", "cwd": str(cwd),
                          "prompt": "do the work",
                          "hook_event_name": "UserPromptSubmit"},
                         separators=(",", ":"))
    return subprocess.run(["bash", "-c", command], input=payload, text=True,
                          capture_output=True, cwd=str(cwd), env=environ,
                          timeout=30, check=False)


def installed_guard(home: Path) -> str:
    [command] = [c for c in user_prompt_commands(home) if c == GUARD_COMMAND]
    return command


def test_genuine_guard_rejection_exits_2(tmp_path):
    """NO BLANKET `|| true`, AND THE PROOF IS THE EXIT CODE. With the pair
    merged against a target that answers, the installed entry — read back out
    of the settings file, not the constant — refuses a bare session under the
    projects root with no workspace by exit 2, which is what blocks a prompt:
    not 127 (the defect), and not the 0 a suffix would make of it."""
    link_xfactory(tmp_path)
    assert install(tmp_path).returncode == 0
    result = guard_run(tmp_path, tmp_path, installed_guard(tmp_path))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "THE NAME GUARD REFUSES" in result.stderr, result.stderr
    assert "the ROW cannot be read" in result.stderr, (
        "refused, but not for the missing workspace:\n" + result.stderr)
    assert "carried no `cwd`" not in result.stderr


@NEEDS_TEMPLATE
def test_after_wip_init_the_guard_still_refuses_by_exit_2(tmp_path):
    """…AND THE SAME ONCE THE WORKSPACE IS THERE: after `wip init` has linked
    and merged, a session outside any tmux window is refused by exit 2 — the
    register is readable now, and the refusal is the guard's own (D2), not a
    missing file."""
    home, env = wip_world(tmp_path)
    (home / "projects" / "xFactory").mkdir()
    assert run_with(env, "--install").returncode == 0
    assert run_with(env, "wip", "init").returncode == 0
    result = guard_run(home, tmp_path, installed_guard(home))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "not in a tmux window at all" in result.stderr, result.stderr
    assert "the ROW cannot be read" not in result.stderr
