# SPDX-License-Identifier: Apache-2.0
"""`--install` beside pipx's `openRepoTools`: the link it leaves to pipx, and
every link it still refuses (opensoft/openRepoTools#228, User Story 1).

pipx places ONE command, `<dir>/openRepoTools`, as a symbolic link into its
own venv. `--install` must leave that link exactly where it is, place every
other artifact, and never advise removing it, because it may be the only
`openRepoTools` on the workstation that can run `--install` at all.
contracts/pipx-link.md is the rule and contracts/cli-output.md the exact
lines; this file holds both:

- `test_pipx_link_*`: the twelve layouts pipx 1.11.1, 1.17.8 and 1.18.3 leave
  under four homes, and the five that are not pipx's link;
- `test_pipx_skip_*`: the skip line, the count line, the 28 receipt rows, the
  link left alone by a refusal, a retirement and a later install, and the
  venv-shaped refusal that prints no `rm` for a link;
- `test_pipx_offline_*`: a package-mode install that reaches no network and
  places what a checkout's install places, apart from the link.

FAKE VENVS, NO PIPX, NO WHEEL. `tests/package_layout.py` lays each venv out
of this checkout's own files. EVERY RUN HERE IS `bash <payload>/openRepoTools`,
as the entry module's `exec` runs it, and never the console script:
`test_entry_*` in `tests/test_package.py` holds that half.

THE LINES THE CONTRACTS NAME, AND NO OTHERS. Nothing here compares a whole
`--install` output or reads a hook-entry line, because another change may add
lines of its own: opensoft/openRepoTools#237 holds the hook pair back in a
sandbox `HOME` and says so. The receipt rows are asserted whole, because hook
entries never had rows.

EVERY PATH IS CANONICAL. Each test resolves its `tmp_path` first, so `<dir>`,
the `<venv>` a refusal names and the receipt's canonical destinations are one
spelling of each path, on Linux and under macOS's `/private` alike.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

import package_layout as layout
from conftest import WINDOWS_SKIP
from test_openrepotools_command import (ARTIFACTS, COMMAND, HOOK_ENTRIES,
                                        INSTALLED, NEEDS_JQ, command_env,
                                        path_without, placed_files,
                                        placement_temporaries, receipt_path,
                                        receipt_rows, source_tree)

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="openRepoTools is a bash script"),
              WINDOWS_SKIP]

# --- the exact lines (contracts/cli-output.md) ------------------------------

#: The skip line, printed where the `openRepoTools:` per-file line would be.
SKIP_LINE = ("openRepoTools: left to pipx at {link} (a link into pipx's "
             "openrepotools environment); update it with `pipx upgrade "
             "openrepotools`, then run `openRepoTools --install` again")

#: The count line of a run from pipx's own environment. The contract spells
#: it `16 of 17`, which is today's `INSTALLED`, so it is derived from that list
#: as every count in this suite is.
PIPX_OWN_COUNT = ("openRepoTools: {placed} of {total} placed in {dir}, "
                  "and 1 left to pipx")

#: The receipt rows beside pipx's link: every placed regular file but the
#: link, 28 today (16 + 6 + 6).
ROWS_BESIDE_THE_LINK = ARTIFACTS - HOOK_ENTRIES - 1

#: A venv-shaped link's entry in `plan_install_targets`' refusal, and the
#: paragraph that follows the list. Its line breaks are the contract's own.
VENV_SHAPED_ENTRY = ("    {link} — a link into a Python environment, perhaps "
                     "pipx's ({venv}), in a layout this installer does not "
                     "recognise")
VENV_SHAPED_PARAGRAPH = (
    "    Leave {link} where it is: it may be the only openRepoTools that can\n"
    "    run `--install`. Run `pipx reinstall openrepotools`, then "
    "`openRepoTools --install`\n"
    "    again, and if this refusal stays, open an issue on "
    "opensoft/openRepoTools naming\n"
    "    the layout under {venv}.")

#: Today's link refusal, which every other link still gets: its first line,
#: the sentence that introduces the `rm -f` line, and the `jq` refusal.
TARGETS_REFUSAL = ("`--install` places a REGULAR FILE IT CAN WRITE at each of "
                   "these, and these are")
CLEAR_THEM = "Clear them, then re-run"
JQ_REFUSAL = "REFUSED: `--install` needs `jq` to merge its TWO hook entries into"

#: The repository a package-mode install must never need (research R14):
#: `.invalid` never resolves.
SENTINEL_REPO = "offline.invalid/sentinel"

# --- the layouts -----------------------------------------------------------

#: contracts/pipx-link.md's rows: the pipx releases the fixtures mirror.
RELEASES = tuple(layout.PIPX_RELEASES)

#: AND ITS FOUR COLUMNS, each a pipx home under the sandbox `HOME`. The home
#: with a space is `<tmp>/Library/Application Support/pipx`, macOS's default,
#: because the sandbox `HOME` is `<tmp>` itself.
PIPX_HOMES = {
    "PIPX_HOME": ("custom", "pipx-home"),
    "dot-local-pipx": (".local", "pipx"),
    "dot-local-share-pipx": (".local", "share", "pipx"),
    "home-with-a-space": ("Library", "Application Support", "pipx"),
}

#: THE TWELVE CASES. The link is absolute in half of them and relative in the
#: other half, alternating like a chessboard so that every release and every
#: home meets both forms.
MATRIX = [
    pytest.param(release, column, ("absolute", "relative")[(row + col) % 2],
                 id=f"pipx-{release}-{column}-"
                    f"{('absolute', 'relative')[(row + col) % 2]}")
    for row, release in enumerate(RELEASES)
    for col, column in enumerate(PIPX_HOMES)
]

#: contracts/pipx-link.md's five negative cases, by the outcome each gets.
VENV_SHAPED = ("no-payload", "no-pipx-metadata")
ORDINARY = ("not-in-bin", "chain-of-41-links", "two-link-cycle")


def bin_dir(home: Path) -> Path:
    """`<dir>`: `$OPENREPOTOOLS_BIN_DIR` unset, so `~/.local/bin`, which is
    also pipx's default `PIPX_BIN_DIR`."""
    return home / ".local" / "bin"


def payload_of(prefix: Path) -> Path:
    """The one `lib/python*/site-packages/openrepotools/payload` under
    `prefix`: the directory the entry module runs `openRepoTools` from."""
    found = sorted(prefix.glob("lib/python*/site-packages/openrepotools/payload"))
    assert len(found) == 1, f"{prefix} holds {len(found)} payloads: {found}"
    return found[0]


def point(link: Path, target: Path, form: str = "absolute") -> None:
    """A symbolic link at `link` to `target`, spelled absolute or relative to
    the link's own directory."""
    link.parent.mkdir(parents=True, exist_ok=True)
    value = (os.path.relpath(target, link.parent) if form == "relative"
             else str(target))
    link.symlink_to(value)


def pipx_install(home: Path, release: str = "1.17.8",
                 pipx_home: Path | None = None,
                 form: str = "absolute") -> tuple[Path, Path]:
    """What `pipx install openrepotools` leaves: the venv under `pipx_home`
    (by default `~/.local/share/pipx`) and its link in `<dir>`. Returns
    `(venv, link)`."""
    venv = layout.pipx_venv(pipx_home or home / ".local" / "share" / "pipx",
                            release)
    link = bin_dir(home) / "openRepoTools"
    point(link, venv / "bin" / "openRepoTools", form)
    return venv, link


def chain(link: Path, final: Path, links: int) -> None:
    """`links` symbolic links in a row, the first at `link` and the last
    pointing at `final`; the ones between sit in `<home>/chain`."""
    between = [link.parent.parent.parent / "chain" / f"hop-{n:02d}"
               for n in range(1, links)]
    sequence = [link, *between, final]
    for here, there in zip(sequence, sequence[1:]):
        point(here, there)
    assert sum(p.is_symlink() for p in sequence) == links


def broken_link(kind: str, home: Path) -> tuple[Path, Path | None]:
    """`<dir>/openRepoTools` as one of the five negative cases leaves it.
    Returns the link, and for a venv-shaped one the venv its refusal names.

    Each starts from a whole pipx venv and takes away exactly one thing the
    rule asks for, so that one thing is what the refusal answers."""
    venv, link = pipx_install(home)
    script = venv / "bin" / "openRepoTools"
    if kind == "no-payload":
        (payload_of(venv) / "openRepoTools").unlink()
        return link, venv
    if kind == "no-pipx-metadata":
        (venv / "pipx_metadata.json").unlink()
        return link, venv
    link.unlink()
    if kind == "not-in-bin":
        elsewhere = venv / "Scripts" / "openRepoTools"
        elsewhere.parent.mkdir()
        shutil.copy2(script, elsewhere)
        point(link, elsewhere)
    elif kind == "chain-of-41-links":
        chain(link, script, 41)
    elif kind == "two-link-cycle":
        other = home / "cycle" / "openRepoTools"
        point(other, link)
        point(link, other)
    else:
        raise ValueError(kind)
    return link, None


def installer_for(mode: str, home: Path) -> Path:
    """An `openRepoTools` that is not pipx's: a checkout's, or the payload of
    a package installed outside any pipx venv."""
    if mode == "checkout":
        return source_tree(home / "checkout") / "openRepoTools"
    return layout.package_tree(home / "pip-prefix") / "openRepoTools"


def pipx_env(home: Path, pipx_home: Path | None = None,
             extra: dict | None = None) -> dict:
    """`command_env`, with every `PIPX_*` variable of the caller's shell
    removed, and `PIPX_HOME` set only where a case passes one: the column
    of contracts/pipx-link.md's matrix that shows nothing reads it."""
    env = command_env(home, extra)
    for name in [n for n in env if n.startswith("PIPX_")]:
        del env[name]
    if pipx_home is not None:
        env["PIPX_HOME"] = str(pipx_home)
    return env


def install(installer: Path, home: Path, env: dict) -> subprocess.CompletedProcess:
    """`bash <installer> --install`, as the entry module's `exec` runs it."""
    home.mkdir(parents=True, exist_ok=True)
    return subprocess.run(["bash", str(installer), "--install"],
                          capture_output=True, text=True, check=False,
                          input="", env=env, cwd=str(home))


def transcript(result: subprocess.CompletedProcess) -> str:
    return (f"exit {result.returncode}\n--- stdout\n{result.stdout}"
            f"--- stderr\n{result.stderr}")


def link_state(link: Path) -> tuple:
    """What "left as it was" means for a link: still a link, the same value,
    the same inode and the same mtime, so it was neither replaced nor
    rewritten."""
    st = os.lstat(link)
    return (stat.S_ISLNK(st.st_mode), os.readlink(link), st.st_ino,
            st.st_mtime_ns)


def tree_state(top: Path, skip: tuple = (), home: Path | None = None) -> dict:
    """Every regular file and link under `top`, by relative path: a file as
    its mode and digest, a link as its value. Paths under `skip` are left
    out. With `home`, a file's own mention of that home is read as `<HOME>`,
    so two installs into two homes compare by what they placed."""
    state: dict = {}

    def skipped(rel: str) -> bool:
        return any(rel == s or rel.startswith(s + "/") for s in skip)

    for dirpath, dirnames, filenames in os.walk(top):
        here = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames
                             if not skipped((here / d).relative_to(top).as_posix()))
        for name in dirnames + sorted(filenames):
            path = here / name
            rel = path.relative_to(top).as_posix()
            if skipped(rel):
                continue
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode):
                state[rel] = ("link", os.readlink(path))
            elif stat.S_ISREG(st.st_mode):
                data = path.read_bytes()
                if home is not None:
                    data = data.replace(os.fsencode(str(home)), b"<HOME>")
                state[rel] = ("file", oct(stat.S_IMODE(st.st_mode)),
                              hashlib.sha256(data).hexdigest())
    return state


def rm_lines_naming(text: str, path: Path) -> list[str]:
    """Every line of `text` that runs or advises an `rm` and names `path`."""
    return [line for line in text.splitlines()
            if re.search(r"\brm\b", line) and str(path) in line]


def rm_f_lines(text: str) -> list[str]:
    """Every `rm -f -- …` line of a refusal."""
    return [line for line in text.splitlines()
            if line.strip().startswith("rm -f --")]


# --- what each outcome looks like ------------------------------------------

def assert_left_to_pipx(result: subprocess.CompletedProcess, link: Path) -> None:
    """A run from pipx's own environment: exit 0, the exact skip line and the
    exact pipx-own count line, once each, and no per-file line and no
    seventeen-of-seventeen count for `openRepoTools`."""
    out = result.stdout.splitlines()
    total = len(INSTALLED)
    skip = SKIP_LINE.format(link=link)
    count = PIPX_OWN_COUNT.format(placed=total - 1, total=total, dir=link.parent)
    assert result.returncode == 0, transcript(result)
    assert out.count(skip) == 1, f"the skip line, once:\n{skip}\n{transcript(result)}"
    assert out.count(count) == 1, f"the count line, once:\n{count}\n{transcript(result)}"
    for verb in ("installed at", "updated at", "already installed at"):
        assert not [line for line in out
                    if line.startswith(f"openRepoTools: {verb}")], (
            f"openRepoTools was placed although it is pipx's:\n{transcript(result)}")
    assert f"openRepoTools: {total} of {total} placed" not in result.stdout


def assert_rows_beside_the_link(home: Path, link: Path) -> None:
    """The 28 rows: one for every placed regular file but the link, each
    with the digest of the bytes now at its destination."""
    rows = receipt_rows(home)
    expected = placed_files(home)
    expected.pop(str(link))
    assert len(rows) == ROWS_BESIDE_THE_LINK == len(expected), (
        f"{len(rows)} rows:\n" + receipt_path(home).read_text(encoding="utf-8"))
    assert {row[1] for row in rows} == set(expected)
    for name, destination, digest, _utc in rows:
        assert name == expected[destination], destination
        assert digest == hashlib.sha256(
            Path(destination).read_bytes()).hexdigest(), destination


def assert_refused_before_placing(result: subprocess.CompletedProcess,
                                  home: Path, left: set) -> None:
    """Exit 2, one `REFUSED:`, and nothing placed: `<dir>` holds what the
    fixture put there and nothing else, and no skill, command file, hook
    entry or receipt exists."""
    assert result.returncode == 2, transcript(result)
    assert result.stderr.count("REFUSED:") == 1, transcript(result)
    assert {p.name for p in bin_dir(home).iterdir()} == left, transcript(result)
    for made in (home / ".claude", home / ".claude-profiles", receipt_path(home)):
        assert not made.exists(), f"{made} was made by a refused run"


def assert_ordinary_link_refusal(result: subprocess.CompletedProcess,
                                 link: Path) -> None:
    """Today's refusal of a link, unchanged: the entry naming it, and the
    `rm -f` line naming it alone."""
    lines = result.stderr.splitlines()
    assert TARGETS_REFUSAL in result.stderr, transcript(result)
    assert f"    {link} — a symlink to {os.readlink(link)}" in lines, transcript(result)
    assert CLEAR_THEM in result.stderr, transcript(result)
    assert rm_f_lines(result.stderr) == [f'        rm -f -- "{link}"'], (
        transcript(result))


def assert_venv_shaped_refusal(result: subprocess.CompletedProcess, link: Path,
                               venv: Path, others: tuple = ()) -> None:
    """contracts/cli-output.md's entry and paragraph, and no `rm` for the
    link. With no other bad target there is no "Clear them" and no `rm -f`
    line at all; with others, the `rm -f` line names only them."""
    venv = Path(os.path.realpath(venv))
    err = result.stderr
    entry = VENV_SHAPED_ENTRY.format(link=link, venv=venv)
    paragraph = VENV_SHAPED_PARAGRAPH.format(link=link, venv=venv)
    assert entry in err.splitlines(), f"the entry:\n{entry}\n{transcript(result)}"
    assert paragraph in err, f"the paragraph:\n{paragraph}\n{transcript(result)}"
    assert err.index(paragraph) > err.index(entry), "the paragraph follows the list"
    assert rm_lines_naming(result.stdout + err, link) == [], transcript(result)
    if not others:
        assert CLEAR_THEM not in err, transcript(result)
        assert rm_f_lines(err) == [], transcript(result)
        return
    assert CLEAR_THEM in err, transcript(result)
    (line,) = rm_f_lines(err)
    assert shlex.split(line)[3:] == [str(o) for o in others], transcript(result)


# --- test_pipx_link_: the matrix and its negative cases --------------------

@pytest.mark.parametrize("release, column, form", MATRIX)
@NEEDS_JQ
def test_pipx_link_is_recognised_in_every_layout_pipx_leaves(tmp_path, release,
                                                             column, form):
    """THE TWELVE LAYOUTS, RECOGNISED THE SAME WAY (contracts/pipx-link.md,
    SC-007): three pipx releases, each with its venv under `$PIPX_HOME`,
    `~/.local/pipx`, `~/.local/share/pipx` and a home whose path holds a
    space, linked absolute or relative. Run from that venv's own payload,
    each prints the exact skip line and the pipx-own count line, writes the
    28 rows, and leaves the link and the venv as they were.

    `PIPX_HOME` is set only in its own column, so the other nine show the
    rule finds the venv from the link alone.
    """
    home = tmp_path.resolve()
    pipx_home = home.joinpath(*PIPX_HOMES[column])
    venv, link = pipx_install(home, release, pipx_home, form)
    env = pipx_env(home, pipx_home if column == "PIPX_HOME" else None)
    assert ("PIPX_HOME" in env) == (column == "PIPX_HOME")
    before = link_state(link), tree_state(venv)

    result = install(payload_of(venv) / "openRepoTools", home, env)
    assert_left_to_pipx(result, link)
    assert (link_state(link), tree_state(venv)) == before, (
        "the install wrote through pipx's link or into its venv")
    assert_rows_beside_the_link(home, link)
    assert placement_temporaries(home) == []


@NEEDS_JQ
def test_pipx_link_followed_through_forty_links_is_still_pipx_s_link(tmp_path):
    """THE HOP LIMIT'S OTHER SIDE. `link_resolve` fails only past 40 hops
    (contracts/pipx-link.md), so a chain of exactly 40 links ending at pipx's
    console script is still pipx's link: skipped, and left as it was, with
    every link of the chain."""
    home = tmp_path.resolve()
    venv, link = pipx_install(home, "1.18.3")
    link.unlink()
    chain(link, venv / "bin" / "openRepoTools", 40)
    hops = sorted((home / "chain").iterdir())
    before = [link_state(p) for p in (link, *hops)]

    result = install(payload_of(venv) / "openRepoTools", home, pipx_env(home))
    assert_left_to_pipx(result, link)
    assert [link_state(p) for p in (link, *hops)] == before
    assert_rows_beside_the_link(home, link)


@pytest.mark.parametrize("mode", ["checkout", "package"])
@pytest.mark.parametrize("kind", VENV_SHAPED + ORDINARY)
def test_pipx_link_refuses_what_is_not_pipx_s_link_before_placing_anything(
        tmp_path, kind, mode):
    """THE FIVE NEGATIVE CASES, IN TWO MODES (contracts/pipx-link.md). Each
    refuses in the planning phase and places nothing, from a checkout's
    `openRepoTools` and from a package's outside any pipx venv:

    - a venv with no `openrepotools/payload/openRepoTools`, and one with no
      `pipx_metadata.json`: both hold `pyvenv.cfg`, so each is refused as
      venv-shaped, naming the venv, with no `rm` advice for the link;
    - a link to a console script that is not in a `bin/`, a chain of 41
      links, and a two-link cycle: none is pipx's link or venv-shaped, so
      each gets today's refusal, `rm -f` line and all.

    The link is left as it was in every case.
    """
    home = tmp_path.resolve()
    installer = installer_for(mode, home)
    link, venv = broken_link(kind, home)
    before = link_state(link)

    result = install(installer, home, pipx_env(home))
    assert_refused_before_placing(result, home, {"openRepoTools"})
    if venv is not None:
        assert_venv_shaped_refusal(result, link, venv)
    else:
        assert_ordinary_link_refusal(result, link)
    assert link_state(link) == before


# --- test_pipx_skip_: the skip, and the refusals beside it -----------------

@NEEDS_JQ
def test_pipx_skip_leaves_pipx_s_link_and_places_every_other_artifact(tmp_path):
    """THE SKIP ITSELF (FR-016, User Story 1 scenario 1). Run from pipx's own
    environment: the exact skip line, the other sixteen files placed from
    the payload at 755, the skills and command files placed, the exact
    pipx-own count line and 28 receipt rows, with no row for the link. The
    link, its console script and the rest of the venv are as they were."""
    home = tmp_path.resolve()
    venv, link = pipx_install(home, "1.17.8")
    payload = payload_of(venv)
    before = link_state(link), tree_state(venv)

    result = install(payload / "openRepoTools", home, pipx_env(home))
    assert_left_to_pipx(result, link)
    assert (link_state(link), tree_state(venv)) == before, (
        "the install wrote through pipx's link or into its venv")
    out = result.stdout.splitlines()
    for name in INSTALLED:
        if name == "openRepoTools":
            continue
        target = bin_dir(home) / name
        assert f"{name}: installed at {target}" in out, transcript(result)
        assert not target.is_symlink() and target.is_file(), name
        assert stat.S_IMODE(target.stat().st_mode) == 0o755, name
        assert target.read_bytes() == (payload / name).read_bytes(), name
    for destination, name in placed_files(home).items():
        if destination == str(link):
            continue
        if name.startswith("/"):
            source = payload / "commands" / f"{name[1:]}.md"
        elif destination.endswith("/SKILL.md"):
            source = payload / "skills" / name / "SKILL.md"
        else:
            source = payload / name
        assert Path(destination).read_bytes() == source.read_bytes(), destination
    assert_rows_beside_the_link(home, link)
    assert (f"receipt: {ROWS_BESIDE_THE_LINK} placed files recorded in "
            f"{receipt_path(home)}") in out, transcript(result)
    assert placement_temporaries(home) == []


def test_pipx_skip_a_second_link_is_refused_with_today_s_rm_for_it_alone(tmp_path):
    """EVERY OTHER LINK STILL REFUSES (FR-017, User Story 1 scenario 4).
    Beside pipx's link, `<dir>/park` is a link too. The install refuses in
    the planning phase, naming `park` with today's entry and an `rm -f` line
    for `park` alone: pipx's link is neither listed nor offered for removal,
    and neither link is touched."""
    home = tmp_path.resolve()
    venv, link = pipx_install(home, "1.18.3")
    mine = home / "my-own" / "park"
    mine.parent.mkdir()
    mine.write_text("#!/usr/bin/env bash\necho my own park\n", encoding="utf-8")
    park = bin_dir(home) / "park"
    point(park, mine)
    before = link_state(link), link_state(park)

    result = install(payload_of(venv) / "openRepoTools", home, pipx_env(home))
    assert_refused_before_placing(result, home, {"openRepoTools", "park"})
    assert_ordinary_link_refusal(result, park)
    assert f"    {link} — " not in result.stderr, (
        f"pipx's link was listed as a bad target:\n{transcript(result)}")
    assert rm_lines_naming(result.stdout + result.stderr, link) == [], (
        transcript(result))
    assert (link_state(link), link_state(park)) == before


def test_pipx_skip_a_venv_shaped_link_is_refused_without_rm_advice(tmp_path):
    """A LINK INTO A PYTHON ENVIRONMENT THAT FAILS THE RULE (FR-017, the
    "future pipx layout" edge case). The venv is macOS's, under
    `~/Library/Application Support/pipx`, linked relative, and holds a whole
    payload and `pyvenv.cfg` but no `pipx_metadata.json`: the layout
    `pip install openrepotools` leaves in a plain venv. A checkout's install
    refuses with contracts/cli-output.md's entry and paragraph, the venv's
    spaced path in both, and prints neither "Clear them" nor any `rm` line,
    because that link may be the only `openRepoTools` that can run
    `--install`."""
    home = tmp_path.resolve()
    pipx_home = home.joinpath(*PIPX_HOMES["home-with-a-space"])
    venv, link = pipx_install(home, "1.18.3", pipx_home, "relative")
    (venv / "pipx_metadata.json").unlink()
    installer = installer_for("checkout", home)
    before = link_state(link), tree_state(venv)

    result = install(installer, home, pipx_env(home))
    assert_refused_before_placing(result, home, {"openRepoTools"})
    assert_venv_shaped_refusal(result, link, venv)
    assert (link_state(link), tree_state(venv)) == before


def test_pipx_skip_a_venv_shaped_link_is_left_out_of_another_link_s_rm(tmp_path):
    """THE `rm -f` LINE NAMES ONLY THE OTHER BAD TARGETS (contracts/cli-output.md).
    A venv-shaped link at `<dir>/openRepoTools` and an ordinary link at
    `<dir>/park`: both are listed, the paragraph follows the list, and the
    one `rm -f` line names `park` and not the venv-shaped link."""
    home = tmp_path.resolve()
    venv, link = pipx_install(home, "1.11.1")
    (payload_of(venv) / "openRepoTools").unlink()
    mine = home / "my-own" / "park"
    mine.parent.mkdir()
    mine.write_text("#!/usr/bin/env bash\necho my own park\n", encoding="utf-8")
    park = bin_dir(home) / "park"
    point(park, mine)
    installer = installer_for("package", home)
    before = link_state(link), link_state(park)

    result = install(installer, home, pipx_env(home))
    assert_refused_before_placing(result, home, {"openRepoTools", "park"})
    assert f"    {park} — a symlink to {mine}" in result.stderr.splitlines(), (
        transcript(result))
    assert_venv_shaped_refusal(result, link, venv, others=(park,))
    assert (link_state(link), link_state(park)) == before


def test_pipx_skip_without_jq_ends_in_the_jq_refusal_and_no_rm_for_the_link(
        tmp_path):
    """NO `jq`, AND PIPX'S LINK IN PLACE (FR-018, User Story 1 scenario 5).
    The link is recognised before any link refusal, so the run reaches the
    `jq` check where it stands and ends in that refusal, unchanged. Nothing
    is placed, no link refusal is printed, and no line advises an `rm` of
    the link."""
    home = tmp_path.resolve()
    venv, link = pipx_install(home, "1.17.8")
    before = link_state(link)
    env = pipx_env(home, extra={"PATH": path_without(home, "jq")})

    result = install(payload_of(venv) / "openRepoTools", home, env)
    assert_refused_before_placing(result, home, {"openRepoTools"})
    assert JQ_REFUSAL in result.stderr, transcript(result)
    assert "there is no `jq` on this PATH" in result.stderr, transcript(result)
    assert TARGETS_REFUSAL not in result.stderr, transcript(result)
    assert rm_lines_naming(result.stdout + result.stderr, link) == [], (
        transcript(result))
    assert link_state(link) == before


@NEEDS_JQ
def test_pipx_skip_a_restart_retirement_leaves_the_link(tmp_path):
    """THE RETIREMENT NEVER REACHES PIPX'S LINK (FR-016). A `restart` this
    installer once placed is retired in the same run that skips the link:
    `restart` goes, said out loud, and the link stays exactly as it was,
    named by no `RETIRED` line and no `rm`."""
    home = tmp_path.resolve()
    venv, link = pipx_install(home, "1.17.8")
    stale = bin_dir(home) / "restart"
    stale.write_text(
        "#!/usr/bin/env bash\n"
        "# SPDX-License-Identifier: Apache-2.0\n"
        "#\n"
        "# restart — the word this installer used to place.\n"
        "#\n"
        "# Installed on PATH by `openRepoTools --install`, which is where it came from.\n"
        "echo stale\n", encoding="utf-8")
    stale.chmod(0o755)
    before = link_state(link), tree_state(venv)

    result = install(payload_of(venv) / "openRepoTools", home, pipx_env(home))
    assert_left_to_pipx(result, link)
    assert not stale.exists(), transcript(result)
    assert "restart: RETIRED" in result.stdout, transcript(result)
    assert not [line for line in result.stdout.splitlines()
                if line.startswith("openRepoTools: RETIRED")], transcript(result)
    assert rm_lines_naming(result.stdout + result.stderr, link) == [], (
        transcript(result))
    assert (link_state(link), tree_state(venv)) == before
    assert_rows_beside_the_link(home, link)


def test_pipx_skip_no_retired_word_is_openrepotools():
    """WHY THE RETIREMENT CANNOT NAME THE LINK (contracts/pipx-link.md):
    `retire_commands` walks `RETIRED` alone, and `RETIRED` does not hold
    `openRepoTools`. Read out of the script, because no run can show a word
    the list does not carry."""
    found = re.findall(r"^RETIRED=\(([^)\n]*)\)$",
                       COMMAND.read_text(encoding="utf-8"), re.MULTILINE)
    assert len(found) == 1, f"{COMMAND} defines RETIRED {len(found)} times"
    words = found[0].split()
    assert words, "RETIRED is empty; this test is proving less than it says"
    assert "openRepoTools" not in words, words


@NEEDS_JQ
def test_pipx_skip_a_later_install_leaves_the_link_and_changes_nothing(tmp_path):
    """A SECOND `--install` FROM THE SAME VENV (FR-016, FR-022). The link is
    skipped again with the same two lines, the sixteen are already
    installed and unchanged, the receipt still holds 28 rows, one per
    destination, and the link and the venv are as they were before the
    first run."""
    home = tmp_path.resolve()
    venv, link = pipx_install(home, "1.11.1")
    installer = payload_of(venv) / "openRepoTools"
    before = link_state(link), tree_state(venv)
    first = install(installer, home, pipx_env(home))
    assert_left_to_pipx(first, link)

    second = install(installer, home, pipx_env(home))
    assert_left_to_pipx(second, link)
    out = second.stdout.splitlines()
    for name in INSTALLED:
        if name != "openRepoTools":
            target = bin_dir(home) / name
            assert f"{name}: already installed at {target} (unchanged)" in out, (
                transcript(second))
    assert (link_state(link), tree_state(venv)) == before
    assert_rows_beside_the_link(home, link)
    assert len({row[1] for row in receipt_rows(home)}) == ROWS_BESIDE_THE_LINK


# --- test_pipx_offline_: the package install, offline ----------------------

def refusing_network(root: Path) -> tuple[str, Path]:
    """A `PATH` whose first `gh` and `curl` fail, each recording that it was
    called. Returns the `PATH` and the record, which no offline run makes."""
    fake = root / "refusing-network"
    fake.mkdir()
    calls = root / "network-calls.log"
    for tool in ("gh", "curl"):
        (fake / tool).write_text(
            "#!/bin/sh\n"
            f"printf '%s %s\\n' {tool} \"$*\" >> '{calls}'\n"
            f"printf 'fake {tool}: this install must reach no network\\n' >&2\n"
            "exit 1\n", encoding="utf-8")
        (fake / tool).chmod(0o755)
    return f"{fake}{os.pathsep}{os.environ['PATH']}", calls


@pytest.mark.parametrize("release", RELEASES)
@NEEDS_JQ
def test_pipx_offline_a_package_install_places_what_a_checkout_does_but_the_link(
        tmp_path, release):
    """FROM INSIDE THE PACKAGE, AND NO NETWORK (FR-008, User Story 1
    scenario 1). A package-mode `--install` from pipx's venv, with
    `OPENREPOTOOLS_REPO=offline.invalid/sentinel` and a `gh` and a `curl`
    that fail, succeeds without calling either. Beside it, a checkout's
    install into a second home, under the same settings. Every file and
    link the two placed is the same, in bytes and mode, apart from
    `<dir>/openRepoTools`, which is the checkout's file in one and pipx's
    untouched link in the other; and the receipts hold the same rows, apart
    from the checkout's row for that file.
    """
    root = tmp_path.resolve()
    path, calls = refusing_network(root)
    offline = {"OPENREPOTOOLS_REPO": SENTINEL_REPO, "PATH": path}

    package_home = root / "package-home"
    venv, link = pipx_install(package_home, release)
    before = link_state(link)
    package = install(payload_of(venv) / "openRepoTools", package_home,
                      pipx_env(package_home, extra=offline))
    assert_left_to_pipx(package, link)
    assert link_state(link) == before

    checkout_home = root / "checkout-home"
    checkout = install(source_tree(root / "checkout") / "openRepoTools",
                       checkout_home, pipx_env(checkout_home, extra=offline))
    assert checkout.returncode == 0, transcript(checkout)
    assert not calls.exists(), (
        "an install reached for the network:\n" + calls.read_text(encoding="utf-8"))

    the_link = link.relative_to(package_home).as_posix()
    receipt = receipt_path(package_home).relative_to(package_home).as_posix()
    pipx_tree = venv.parent.parent.relative_to(package_home).as_posix()
    got = tree_state(package_home, (pipx_tree, receipt, the_link), package_home)
    want = tree_state(checkout_home, (receipt, the_link), checkout_home)
    assert got == want, (
        f"placed by the checkout only: {sorted(set(want) - set(got))}\n"
        f"placed by the package only: {sorted(set(got) - set(want))}\n"
        f"placed differently: "
        f"{sorted(k for k in set(got) & set(want) if got[k] != want[k])}")
    assert (checkout_home / the_link).is_file()
    assert not (checkout_home / the_link).is_symlink()

    def rows(home: Path) -> set:
        return {(name, Path(dest).relative_to(home).as_posix(), digest)
                for name, dest, digest, _utc in receipt_rows(home)}

    package_rows, checkout_rows = rows(package_home), rows(checkout_home)
    assert package_rows - checkout_rows == set(), (
        f"rows only the package wrote: {sorted(package_rows - checkout_rows)}")
    assert checkout_rows - package_rows == {(
        "openRepoTools", the_link,
        hashlib.sha256((checkout_home / the_link).read_bytes()).hexdigest())}
    assert len(package_rows) == ROWS_BESIDE_THE_LINK
