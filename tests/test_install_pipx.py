# SPDX-License-Identifier: Apache-2.0
"""`--install` beside pipx's `openRepoTools`: the link it leaves to pipx, every
link it still refuses, and every other installer it meets
(opensoft/openRepoTools#228, User Stories 1 and 3).

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
  places what a checkout's install places, apart from the link;
- `test_coexist_*`: pipx's link beside the one-line install, a checkout and a
  package outside pipx's venv, and the count line that names where the other
  sixteen now come from and which release is beside the link (research R5),
  for a single repository and for each layout an assembly gives: the one-line
  install from an adopted assembly, the code mounted in one, and a code
  feature worktree;
- `test_pip_script_*`: pip's console script at `<dir>/openRepoTools`, in both
  forms pip writes, refused in every mode, and the files that only look like
  it, placed as today;
- `test_path_report_*`: the note a package-mode install prints last when the
  first `openRepoTools` on `PATH` is not its own, and its silence where the
  package's layout names no `<prefix>` (research R7);
- `test_pipx_upgrade_*` and `test_pipx_uninstall_*`: a second wheel in the
  same venv, and the link and the venv gone.

FAKE VENVS, NO PIPX, NO WHEEL. `tests/package_layout.py` lays each venv out
of this checkout's own files. EVERY PACKAGE RUN HERE IS
`bash <payload>/openRepoTools`, as the entry module's `exec` runs it, and never
the console script: `test_entry_*` in `tests/test_package.py` holds that half.
A one-line install is `bash -s` fed the installer's text, with a fake `gh`
serving the payload and a `curl` that refuses, so no run reaches a network.
An assembly's layouts take `World` from `tests/test_install_payload_source.py`,
whose `gh` and `curl` answer from bare repositories under the test's own
directory, and that file's `PATH` with no real `gh` or `curl` on it.

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
from conftest import REPO, WINDOWS_SKIP
from test_install_payload_source import (World, git, local_assembly, network,
                                         variant)
from test_openrepotools_command import (ARTIFACTS, COMMAND, FETCHED,
                                        HOOK_ENTRIES, INSTALLED, NEEDS_JQ,
                                        command_env, path_without,
                                        placed_files, placement_temporaries,
                                        receipt_path, receipt_rows,
                                        source_tree)

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

#: THE COUNT LINE OF ANY OTHER RUN BESIDE PIPX'S LINK (FR-019): a checkout's,
#: the one-line install's, or a package's from outside pipx's venv. `{source}`
#: is where this run's sixteen came from, and `{pipx}` names what is beside
#: the link. The contract's `the other 16` is the same number as `{placed}`.
OTHER_SOURCE_COUNT = ("openRepoTools: {placed} of {total} placed in {dir}, "
                      "and 1 left to pipx; the other {placed} now come from "
                      "{source}, not from {pipx}")

#: `{pipx}` when the stamp beside pipx's payload passes the reader (`0.0.0`
#: for an unstamped one), and the clause that takes its place when it fails.
PIPX_BY_ITS_VERSION = "openrepotools {version}"
PIPX_STAMP_UNREADABLE = ("the openrepotools beside pipx's link, whose stamp "
                         "cannot be read")
#: ...and the words no line may ever say instead (research R5).
NEVER_SAID = "openrepotools an unreadable stamp"

#: PIP'S CONSOLE SCRIPT AT `<dir>/openRepoTools` (FR-020): design.md Decision
#: 8's text with `die`'s prefix, the same for both forms pip writes. Its line
#: breaks and indents are the contract's own.
PIP_REFUSAL = (
    "REFUSED: `--install` will not replace {target}: it is pip's console "
    "script for openrepotools (`pip install --user openrepotools` leaves it "
    "there), and another installer's command is not this installer's to "
    "overwrite.\n"
    "    NOTHING was installed and nothing already installed was replaced.\n"
    "    pipx is the one package route. To move to it:\n"
    "        pip uninstall openrepotools\n"
    "        pipx install openrepotools\n"
    "        openRepoTools --install")

#: THE PATH REPORT (FR-021), and its form when `type -P` finds nothing, which
#: is the same up to its last `;`. `{want}` is `<prefix>/bin/openRepoTools`.
PATH_NOTE = ("openRepoTools: note: the first openRepoTools on your PATH is "
             "{first}, not this package's {want}, so the release you just "
             "installed is not the one that runs; put the directory that "
             "holds pipx's link to it ahead of {first_dir} on PATH")
PATH_NOTE_NONE = ("openRepoTools: note: the first openRepoTools on your PATH "
                  "is none, not this package's {want}, so the release you "
                  "just installed is not the one that runs; put the directory "
                  "that holds pipx's link to it on PATH")
NOTE_PREFIX = "openRepoTools: note: "

#: THE TWO RELEASES A COEXISTENCE CAN NAME: the one pipx placed, and another,
#: which a package outside pipx's venv carries. Two versions, so a line that
#: names one can never be read as naming the other. Both pass every rule of
#: contracts/stamp.md.
PIPX_RELEASE = {"VERSION": "1.1.0", "TAG": "v1.1.0",
                "COMMIT": "0123456789abcdef0123456789abcdef01234567",
                "DIGEST": "89abcdef01234567" * 4,
                "REPOSITORY": "opensoft/openRepoTools-code"}
OTHER_RELEASE = {"VERSION": "1.2.0rc1", "TAG": "v1.2.0rc1",
                 "COMMIT": "fedcba98" * 5,
                 "DIGEST": "0f1e2d3c4b5a6978" * 4,
                 "REPOSITORY": "opensoft/openRepoTools"}

#: `<repo> @ <ref>` when nothing names them, and a pair that does, with the
#: variables that name it.
DEFAULT_SOURCE = ("opensoft/openRepoTools", "main")
NAMED_SOURCE = ("someone/fork", "v1.2.3")
SOURCES = {
    "default-source": (DEFAULT_SOURCE, {}),
    "named-source": (NAMED_SOURCE, {"OPENREPOTOOLS_REPO": NAMED_SOURCE[0],
                                    "OPENREPOTOOLS_REF": NAMED_SOURCE[1]}),
}

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


# --- the other installers (User Story 3) -----------------------------------

def stamp_of(payload: Path) -> Path:
    """The stamp beside a payload: its `openrepotools/_release.py`."""
    return payload.parent / "_release.py"


#: WHAT THE STAMP BESIDE PIPX'S PAYLOAD CAN BE: the committed one, a
#: release's, and one fixture for each of contracts/cli-output.md's three
#: causes. The one that cannot be read is a directory, which no account reads
#: as a file, so that case holds for root too.
PIPX_SIDES = ("unstamped", "stamped", "cannot-be-read", "is-partial",
              "is-malformed")


def give_pipx_a_stamp(venv: Path, side: str) -> str:
    """Make the stamp beside `venv`'s payload what `side` names, and return
    what the count line says after "not from" (FR-019): `openrepotools
    <VERSION>` for a stamp the reader accepts, `0.0.0` for the unstamped one,
    and the unreadable-stamp clause for one it refuses. That stamp belongs to
    another install, so a run beside it goes on either way."""
    stamp = stamp_of(payload_of(venv))
    if side == "unstamped":
        assert stamp.read_bytes() == layout.STAMP_SOURCE.read_bytes(), (
            "the fixture is wrong: pipx's venv does not hold the committed stamp")
        return PIPX_BY_ITS_VERSION.format(version="0.0.0")
    if side == "stamped":
        stamp.write_bytes(layout.stamp_text(**PIPX_RELEASE).encode("utf-8"))
        return PIPX_BY_ITS_VERSION.format(version=PIPX_RELEASE["VERSION"])
    if side == "cannot-be-read":
        stamp.unlink()
        stamp.mkdir()
    elif side == "is-partial":
        stamp.write_bytes(layout.stamp_text(
            **{**PIPX_RELEASE, "DIGEST": ""}).encode("utf-8"))
    elif side == "is-malformed":
        stamp.write_bytes(layout.stamp_text(
            **{**PIPX_RELEASE, "TAG": "v1.2.0"}).encode("utf-8"))
    else:
        raise ValueError(side)
    return PIPX_STAMP_UNREADABLE


def mark(tree: Path, note: str) -> None:
    """`# <note>` appended to every payload file under `tree`, so that its
    bytes are its own and each placement can be traced to the tree it came
    from. A comment line after everything else, so each file still does what
    it did: bash never reads past the installer's final `exit 0`."""
    for rel in FETCHED:
        path = tree / rel
        path.write_bytes(path.read_bytes() + f"# {note}\n".encode("utf-8"))


def github_serving(root: Path, source: Path) -> Path:
    """A directory whose `gh` answers as GitHub answers for a single
    repository: each payload file `<P>` under `contents/<P>?ref=…`, from
    `source`, and the code pin `contracts/code-pin.yaml` as GitHub's 404
    (#186). Anything else it is asked, it refuses, and its `curl` refuses
    everything, so a run reaches no network whatever it asks. Returns the
    directory, to go first on `PATH`."""
    fake = root / "fake-github"
    fake.mkdir(parents=True)
    routes = "".join(
        f"*/contents/{rel}\\?*) exec cat {shlex.quote(str(source / rel))} ;;\n"
        for rel in FETCHED)
    routes += ("*/contents/contracts/code-pin.yaml\\?*) "
               "printf 'gh: Not Found (HTTP 404)\\n' >&2; exit 1 ;;\n")
    (fake / "gh").write_text(
        "#!/bin/sh\n"
        'case "$*" in\n' + routes + "esac\n"
        "printf 'fake gh: unexpected call: %s\\n' \"$*\" >&2\n"
        "exit 1\n", encoding="utf-8")
    (fake / "curl").write_text(
        "#!/bin/sh\n"
        "printf 'fake curl: no test here may reach the network\\n' >&2\n"
        "exit 1\n", encoding="utf-8")
    for tool in ("gh", "curl"):
        (fake / tool).chmod(0o755)
    return fake


def with_github(env: dict, root: Path, source: Path = REPO) -> dict:
    """`env`, with `github_serving(root, source)` first on its `PATH`."""
    fake = github_serving(root, source)
    return {**env, "PATH": f"{fake}{os.pathsep}{env['PATH']}"}


def install_piped(home: Path, env: dict,
                  script: Path = COMMAND) -> subprocess.CompletedProcess:
    """The one-line install: `script`'s text piped into `bash -s -- --install`,
    run in `home`, which holds nothing named `bash`, so `$SELF` is no file and
    every payload file is fetched."""
    home.mkdir(parents=True, exist_ok=True)
    return subprocess.run(["bash", "-s", "--", "--install"],
                          capture_output=True, text=True, check=False,
                          input=script.read_text(encoding="utf-8"), env=env,
                          cwd=str(home))


#: THE THREE WAYS AN `--install` RUNS THAT ARE NOT PIPX'S OWN: a checkout's,
#: the one-line install's, and a package's from outside any pipx venv.
MODES = ("checkout", "one-line-install", "package")


def install_as(how: str, root: Path, home: Path,
               env: dict) -> subprocess.CompletedProcess:
    """`--install` into `home`, run as `how` names, from a tree under `root`
    that holds this checkout's bytes."""
    if how == "checkout":
        return install(source_tree(root / "checkout") / "openRepoTools", home,
                       env)
    if how == "one-line-install":
        return install_piped(home, with_github(env, root / "github"))
    if how == "package":
        return install(layout.package_tree(root / "pip-prefix")
                       / "openRepoTools", home, env)
    raise ValueError(how)


def source_of(tree: Path, destination: str, name: str) -> Path:
    """The file under `tree` that a placed `destination` comes from: a command
    file, a skill or one of the seventeen, by the name `--install` printed."""
    if name.startswith("/"):
        return tree / "commands" / f"{name[1:]}.md"
    if destination.endswith("/SKILL.md"):
        return tree / "skills" / name / "SKILL.md"
    return tree / name


def file_state(path: Path) -> tuple:
    """A file as a test compares it: its type, mode, inode, mtime and bytes."""
    st = os.lstat(path)
    return (stat.S_IFMT(st.st_mode), stat.S_IMODE(st.st_mode), st.st_ino,
            st.st_mtime_ns, path.read_bytes())


def assert_placed_from(home: Path, link: Path, tree: Path) -> None:
    """Every file an install beside `link` places holds `tree`'s bytes: the
    sixteen as regular files at 755, the skills and command files beside
    them."""
    for destination, name in placed_files(home).items():
        if destination == str(link):
            continue
        path = Path(destination)
        assert path.is_file() and not path.is_symlink(), destination
        assert path.read_bytes() == source_of(tree, destination,
                                              name).read_bytes(), (
            f"{destination} does not hold the bytes of {tree}")
        if path.parent == link.parent:
            assert stat.S_IMODE(path.stat().st_mode) == 0o755, destination


def assert_beside_the_link(result: subprocess.CompletedProcess, link: Path,
                           source: str, pipx: str) -> None:
    """Any run but pipx's own, beside pipx's link (FR-019): exit 0, the exact
    skip line and the exact other-source count line once each, naming
    `source` and, after "not from", `pipx`. Not the pipx-own line, not a
    seventeen-of-seventeen count, no per-file line for `openRepoTools`, and
    never "openrepotools an unreadable stamp" anywhere."""
    out = result.stdout.splitlines()
    total = len(INSTALLED)
    skip = SKIP_LINE.format(link=link)
    count = OTHER_SOURCE_COUNT.format(placed=total - 1, total=total,
                                      dir=link.parent, source=source,
                                      pipx=pipx)
    own = PIPX_OWN_COUNT.format(placed=total - 1, total=total, dir=link.parent)
    assert result.returncode == 0, transcript(result)
    assert out.count(skip) == 1, f"the skip line, once:\n{skip}\n{transcript(result)}"
    assert out.count(count) == 1, (
        f"the count line, once:\n{count}\n{transcript(result)}")
    assert own not in out, (
        f"the line of a run from pipx's own environment:\n{transcript(result)}")
    for verb in ("installed at", "updated at", "already installed at"):
        assert not [line for line in out
                    if line.startswith(f"openRepoTools: {verb}")], (
            f"openRepoTools was placed although it is pipx's:\n{transcript(result)}")
    assert f"openRepoTools: {total} of {total} placed" not in result.stdout
    assert NEVER_SAID not in result.stdout + result.stderr, transcript(result)


# --- test_coexist_: pipx's link beside the other installers ----------------

@NEEDS_JQ
def test_coexist_pipx_install_force_over_the_one_line_install_then_install_replaces_the_sixteen(
        tmp_path):
    """US3 SCENARIO 1, THE MOVE FROM THE ONE-LINE INSTALL (FR-024). The
    one-line install places all seventeen from an older release. Then
    `pipx install --force openrepotools` puts pipx's link where that
    `openRepoTools` was, which is what `--force` is for, and `--install` runs
    from the venv's payload. The link is skipped with the exact skip line
    and the pipx-own count line; each of the other sixteen, and each skill
    and command file, is UPDATED to the package's bytes; the link and the
    venv are as they were; and the receipt holds the 28 rows, the one-line
    install's row for `<dir>/openRepoTools` gone with the file it was about.
    """
    root = tmp_path.resolve()
    home = root / "home"
    older = source_tree(root / "older-release")
    mark(older, "an older release, as the one-line install fetched it")
    env = pipx_env(home)
    one_line = install_piped(home, with_github(env, root / "github", older),
                             older / "openRepoTools")
    assert one_line.returncode == 0, transcript(one_line)
    link = bin_dir(home) / "openRepoTools"
    assert not link.is_symlink() and link.read_bytes() == (
        older / "openRepoTools").read_bytes(), transcript(one_line)
    assert len(receipt_rows(home)) == ARTIFACTS - HOOK_ENTRIES

    # `pipx install --force openrepotools`: the venv, and its link in place
    # of the one-line install's file.
    venv = layout.pipx_venv(home / ".local" / "share" / "pipx", "1.17.8")
    link.unlink()
    point(link, venv / "bin" / "openRepoTools")
    payload = payload_of(venv)
    before = link_state(link), tree_state(venv)

    result = install(payload / "openRepoTools", home, env)
    assert_left_to_pipx(result, link)
    assert (link_state(link), tree_state(venv)) == before, (
        "the install wrote through pipx's link or into its venv")
    out = result.stdout.splitlines()
    for destination, name in placed_files(home).items():
        if destination != str(link):
            assert f"{name}: updated at {destination}" in out, transcript(result)
    assert_placed_from(home, link, payload)
    assert_rows_beside_the_link(home, link)
    assert placement_temporaries(home) == []


@pytest.mark.parametrize("side", PIPX_SIDES)
@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("how", ["checkout", "one-line-install"])
@NEEDS_JQ
def test_coexist_a_checkout_or_the_one_line_install_names_its_source_and_pipx_s_release(
        tmp_path, how, source, side):
    """US3 SCENARIO 2 (FR-019). A checkout's `--install`, and the one-line
    install's, beside pipx's link: the link is skipped, the other sixteen
    are placed from the run's own source, and the count line is exactly
    contracts/cli-output.md's other-source line. It names that source as
    `<repo> @ <ref>`, `opensoft/openRepoTools @ main` where nothing names
    them, and the release beside the link by the `VERSION` of the stamp
    beside pipx's payload: `0.0.0` for an unstamped one, the release's for a
    stamped one. A stamp there that fails the reader ends the line in
    `the openrepotools beside pipx's link, whose stamp cannot be read`, for
    each of the three causes, and the install goes on; no output ever reads
    "openrepotools an unreadable stamp".

    pipx's payload carries bytes of its own, so the sixteen being the
    source's bytes shows they came from the run and not from the venv.
    """
    root = tmp_path.resolve()
    home = root / "home"
    venv, link = pipx_install(home, "1.18.3")
    clause = give_pipx_a_stamp(venv, side)
    mark(payload_of(venv), "pipx's release, which this run does not place")
    before = link_state(link), tree_state(venv)
    (repo, ref), named = SOURCES[source]

    result = install_as(how, root, home, pipx_env(home, extra=named))
    assert_beside_the_link(result, link, f"{repo} @ {ref}", clause)
    assert (link_state(link), tree_state(venv)) == before, (
        "the install wrote through pipx's link or into its venv")
    assert_placed_from(home, link, REPO)
    assert_rows_beside_the_link(home, link)


@pytest.mark.parametrize("side", ["unstamped", "stamped", "is-partial"])
@pytest.mark.parametrize("own", ["unstamped", "stamped"])
@pytest.mark.parametrize("where", ["a-prefix", "another-pipx-venv"])
@NEEDS_JQ
def test_coexist_a_package_outside_pipx_s_venv_names_its_own_release_never_repo_and_ref(
        tmp_path, where, own, side):
    """US3 SCENARIO 7 (FR-019, research R5). A package-mode `--install` from a
    package outside the venv pipx's link resolves into, beside that link: a
    `package_tree` under a plain prefix, as pip leaves one, and one inside
    another pipx venv. The link is skipped, the sixteen are this package's
    bytes, and the count line names the package's own release from its own
    stamp, `openrepotools <its VERSION>`, as the source. It never names
    `<repo> @ <ref>`, though `$OPENREPOTOOLS_REPO` and `$OPENREPOTOOLS_REF`
    are set: a package never fetched from them. After "not from" it names
    the stamp beside pipx's payload, as every other run beside the link
    does."""
    root = tmp_path.resolve()
    home = root / "home"
    venv, link = pipx_install(home, "1.17.8")
    clause = give_pipx_a_stamp(venv, side)
    text = None if own == "unstamped" else layout.stamp_text(**OTHER_RELEASE)
    version = "0.0.0" if own == "unstamped" else OTHER_RELEASE["VERSION"]
    if where == "a-prefix":
        payload = layout.package_tree(root / "pip-prefix", stamp=text)
    else:
        payload = payload_of(layout.pipx_venv(root / "another-pipx-home",
                                              "1.11.1", stamp=text))
    mark(payload, "the package this run is")
    before = link_state(link), tree_state(venv)

    result = install(payload / "openRepoTools", home,
                     pipx_env(home, extra=SOURCES["named-source"][1]))
    assert_beside_the_link(result, link, f"openrepotools {version}", clause)
    for pair in (NAMED_SOURCE, DEFAULT_SOURCE):
        assert " @ ".join(pair) not in result.stdout, (
            f"a package named a source it never fetched:\n{transcript(result)}")
    assert (link_state(link), tree_state(venv)) == before
    assert_placed_from(home, link, payload)
    assert_rows_beside_the_link(home, link)


#: THE CODE LEG an assembly's `contracts/code-pin.yaml` names, as
#: `tests/test_install_payload_source.py` builds both: the repository the
#: sixteen come from once `opensoft/openRepoTools` is the assembly.
CODE_LEG = "opensoft/openRepoTools-code"


@NEEDS_JQ
def test_coexist_the_one_line_install_from_an_adopted_assembly_names_the_pinned_code(
        tmp_path):
    """US3 SCENARIO 2 AFTER THE CUTOVER (FR-019, research R5). The one-line
    install, beside pipx's link, from `opensoft/openRepoTools` at `main`,
    which is an assembly whose `contracts/code-pin.yaml` pins the code leg.
    The sixteen are fetched from `opensoft/openRepoTools-code` at the pinned
    commit, so the count line names that pair, `<PAYLOAD_REPO> @
    <PAYLOAD_REV>`, and never `opensoft/openRepoTools @ main`, the source
    the run was given."""
    root = tmp_path.resolve()
    world = World(root / "github-world")
    code = world.code()
    world.assembly(code)
    home = root / "home"
    venv, link = pipx_install(home, "1.18.3")
    clause = give_pipx_a_stamp(venv, "stamped")
    before = link_state(link), tree_state(venv)

    result = install_piped(home, pipx_env(home, extra={"PATH": network(world)}))
    assert_beside_the_link(result, link, f"{CODE_LEG} @ {code}", clause)
    assert " @ ".join(DEFAULT_SOURCE) not in result.stdout, transcript(result)
    assert (bin_dir(home) / "park").read_bytes() == variant("park", "pinned"), (
        f"the sixteen are not the pinned code's bytes:\n{transcript(result)}")
    assert (link_state(link), tree_state(venv)) == before, (
        "the install wrote through pipx's link or into its venv")


@NEEDS_JQ
def test_coexist_the_code_mounted_in_an_assembly_names_the_pin_s_own_pair(
        tmp_path):
    """THE CODE LEG MOUNTED IN AN ASSEMBLY CHECKOUT, `<assembly>/code`, run
    by its own `openRepoTools` beside pipx's link. Its payload is checked
    against the pin and fetched from nowhere, so nothing sets `PAYLOAD_REPO`
    or `PAYLOAD_REV`, and the count line names the pin's own pair,
    `<PIN_SOURCE_REPOSITORY> @ <PIN_COMMIT>` (contracts/cli-output.md's
    `<source>`): `opensoft/openRepoTools-code` at the commit the assembly
    pins, the pair a remote adopted run names."""
    root = tmp_path.resolve()
    world = World(root / "github-world")
    _assembly, code, pinned = local_assembly(world)
    home = root / "home"
    venv, link = pipx_install(home, "1.18.3")
    clause = give_pipx_a_stamp(venv, "stamped")
    before = link_state(link), tree_state(venv)

    result = install(code / "openRepoTools", home,
                     pipx_env(home, extra={"PATH": network(world)}))
    assert_beside_the_link(result, link, f"{CODE_LEG} @ {pinned}", clause)
    assert world.requests() == [], (
        f"the mounted code asked the fake GitHub: {world.requests()}")
    assert (bin_dir(home) / "park").read_bytes() == variant("park", "local"), (
        f"the sixteen are not the mounted code's bytes:\n{transcript(result)}")
    assert (link_state(link), tree_state(venv)) == before, (
        "the install wrote through pipx's link or into its venv")


@NEEDS_JQ
def test_coexist_a_code_feature_worktree_names_repo_and_ref_never_the_pin(
        tmp_path):
    """A PAIRED FEATURE WORKTREE, `<assembly>/worktrees/<NNN>/code`, run by
    its own `openRepoTools` beside pipx's link. It installs its own bytes and
    is not an adopted source, so the count line names `<REPO> @ <REF>` as
    any other checkout does, `opensoft/openRepoTools @ main` where nothing
    names them (contracts/cli-output.md's `<source>`). It never names the
    pin's pair, `opensoft/openRepoTools-code @ <PIN_COMMIT>`: that is the
    code the assembly pins, which this run did not install."""
    root = tmp_path.resolve()
    world = World(root / "github-world")
    assembly, code, pinned = local_assembly(world)
    feature = assembly / "worktrees" / "001-x" / "code"
    git("clone", "-q", str(code), str(feature))
    home = root / "home"
    venv, link = pipx_install(home, "1.18.3")
    clause = give_pipx_a_stamp(venv, "stamped")
    before = link_state(link), tree_state(venv)

    result = install(feature / "openRepoTools", home,
                     pipx_env(home, extra={"PATH": network(world)}))
    assert_beside_the_link(result, link, " @ ".join(DEFAULT_SOURCE), clause)
    assert f"{CODE_LEG} @ {pinned}" not in result.stdout, transcript(result)
    assert world.requests() == [], (
        f"the feature worktree asked the fake GitHub: {world.requests()}")
    assert (link_state(link), tree_state(venv)) == before, (
        "the install wrote through pipx's link or into its venv")


# --- test_pip_script_: pip's console script at <dir>/openRepoTools ----------

#: contracts/pipx-link.md's fixtures: the three forms of pip's own script,
#: refused, and five files that only look like it, placed as today.
PIP_S_SCRIPTS = ("pip-s-shebang", "pip-s-trampoline-quoted-with-a-space",
                 "pip-s-trampoline-unquoted-and-long")
NOT_PIP_S = ("a-bash-shebang", "a-trampoline-to-ruby",
             "a-sh-file-with-no-exec-line",
             "a-python-script-importing-another-package", "this-installer")


def lines_of(path: Path) -> list:
    return path.read_text(encoding="utf-8").split("\n")


def put_fixture(target: Path, root: Path, which: str) -> None:
    """`<dir>/openRepoTools` as fixture `which` leaves it, at 0755, each
    checked to be the shape contracts/pipx-link.md names, so that a case
    proves what it says. Interpreters are paths under `root`, never run."""
    python = f"{root}/pyenv/bin/python3.12"
    if which == "pip-s-shebang":
        layout.console_script(target, python, form="shebang")
        assert lines_of(target)[:3] == [
            f"#!{python}", "import sys", "from openrepotools.cli import main"]
    elif which == "pip-s-trampoline-quoted-with-a-space":
        spaced = f"{root}/py env/bin/python3"
        layout.console_script(target, spaced, form="trampoline")
        assert lines_of(target)[:3] == [
            "#!/bin/sh", f"'''exec' \"{spaced}\" \"$0\" \"$@\"", "' '''"]
    elif which == "pip-s-trampoline-unquoted-and-long":
        long = f"{root}/{'p' * max(8, 130 - len(str(root)))}/bin/python3"
        assert len(long) > 127 and " " not in long
        layout.console_script(target, long, form="trampoline")
        assert lines_of(target)[:3] == [
            "#!/bin/sh", f"'''exec' {long} \"$0\" \"$@\"", "' '''"]
    elif which == "a-bash-shebang":
        layout.console_script(target, "/bin/bash", form="shebang")
        assert lines_of(target)[:3] == [
            "#!/bin/bash", "import sys", "from openrepotools.cli import main"]
    elif which == "a-trampoline-to-ruby":
        ruby = f"{root}/x/bin/ruby"
        layout.console_script(target, f'"{ruby}"', form="trampoline")
        assert lines_of(target)[:3] == [
            "#!/bin/sh", f"'''exec' \"{ruby}\" \"$0\" \"$@\"", "' '''"]
    elif which == "a-sh-file-with-no-exec-line":
        layout.console_script(target, "/bin/sh", form="shebang")
        lines = lines_of(target)
        assert lines[0] == "#!/bin/sh"
        assert "from openrepotools.cli import main" in lines
        assert not [line for line in lines if line.startswith("'''exec'")]
    elif which == "a-python-script-importing-another-package":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"#!{python}\n" + layout.SCRIPT_TEMPLATE % {
            "module": "openreposhape.cli", "import_name": "main",
            "func": "main"}, encoding="utf-8")
        target.chmod(0o755)
        assert "from openreposhape.cli import main" in lines_of(target)
    elif which == "this-installer":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(COMMAND.read_bytes())
        target.chmod(0o755)
    else:
        raise ValueError(which)
    assert stat.S_IMODE(target.stat().st_mode) == 0o755


def assert_pip_s_refusal(result: subprocess.CompletedProcess, home: Path,
                         target: Path, before: tuple) -> None:
    """FR-020's refusal, in the planning phase: exit 2, stderr exactly
    contracts/cli-output.md's text after `die`'s blank line, nothing placed,
    and pip's script exactly as it was."""
    assert_refused_before_placing(result, home, {"openRepoTools"})
    expected = "\n" + PIP_REFUSAL.format(target=target) + "\n"
    assert result.stderr == expected, (
        f"stderr is not exactly the pip refusal:\n{expected}\n"
        f"{transcript(result)}")
    assert file_state(target) == before, "pip's console script was touched"


def assert_placed_over(result: subprocess.CompletedProcess, home: Path,
                       target: Path, was: bytes) -> None:
    """PLACED AS TODAY: exit 0, `<dir>/openRepoTools` replaced by this
    installer's own bytes at 755 (or left as it was, where it already was
    them), today's count line, and a row for it among the 29."""
    total = len(INSTALLED)
    out = result.stdout.splitlines()
    assert result.returncode == 0, transcript(result)
    verb = (f"already installed at {target} (unchanged)"
            if was == COMMAND.read_bytes() else f"updated at {target}")
    assert f"openRepoTools: {verb}" in out, transcript(result)
    assert f"openRepoTools: {total} of {total} placed in {target.parent}" in out
    assert target.is_file() and not target.is_symlink()
    assert stat.S_IMODE(target.stat().st_mode) == 0o755
    assert target.read_bytes() == COMMAND.read_bytes()
    assert len(receipt_rows(home)) == ARTIFACTS - HOOK_ENTRIES
    assert str(target) in {row[1] for row in receipt_rows(home)}


@pytest.mark.parametrize("how", MODES)
@pytest.mark.parametrize("which", PIP_S_SCRIPTS)
def test_pip_script_is_refused_in_every_mode_and_nothing_is_placed(
        tmp_path, which, how):
    """US3 SCENARIO 3 (FR-020): pip's console script at `<dir>/openRepoTools`,
    as `pip install --user openrepotools` writes it, in each form pip writes:
    a Python shebang; the `/bin/sh` trampoline with a quoted interpreter path
    that holds a space; and the trampoline with an unquoted interpreter path
    longer than 127 characters. A checkout's `--install`, the one-line
    install's and a package's from outside any venv each refuse in the
    planning phase with the exact refusal, place nothing, and leave pip's
    script as it was."""
    root = tmp_path.resolve()
    home = root / "home"
    target = bin_dir(home) / "openRepoTools"
    put_fixture(target, root, which)
    before = file_state(target)

    result = install_as(how, root, home, pipx_env(home))
    assert_pip_s_refusal(result, home, target, before)


@pytest.mark.parametrize("form", ["shebang", "trampoline"])
def test_pip_script_a_package_whose_own_command_is_pip_s_script_is_refused(
        tmp_path, form):
    """IN EVERY MODE, PIP'S OWN INCLUDED (FR-020). `pip install --user
    openrepotools` puts the package under the user base, `~/.local`, and its
    console script at `~/.local/bin/openRepoTools`, which is `<dir>`'s. That
    script's own run, `bash <payload>/openRepoTools --install` as the entry
    module execs it, is refused with the exact refusal and places nothing:
    over its own command as over anyone else's. pip's own choice of form,
    for an interpreter at a short path and at one that holds a space."""
    root = tmp_path.resolve()
    home = root / "home"
    payload = layout.package_tree(home / ".local", "python3.12")
    python = ("/usr/bin/python3.12" if form == "shebang"
              else f"{root}/Python Framework/bin/python3.12")
    target = bin_dir(home) / "openRepoTools"
    layout.console_script(target, python)
    assert (lines_of(target)[0] == "#!/bin/sh") == (form == "trampoline")
    assert "from openrepotools.cli import main" in lines_of(target)
    before = file_state(target)

    result = install(payload / "openRepoTools", home, pipx_env(home))
    assert_pip_s_refusal(result, home, target, before)


@pytest.mark.parametrize("how", MODES)
@pytest.mark.parametrize("which", NOT_PIP_S)
@NEEDS_JQ
def test_pip_script_what_only_looks_like_pip_s_script_is_placed_as_today(
        tmp_path, which, how):
    """THE RULE IS BOTH HALVES (contracts/pipx-link.md): a Python interpreter,
    in one of pip's two forms, AND the import of `openrepotools`. So each of
    these is placed over as today, in every mode: the shebang form with
    `#!/bin/bash`; a trampoline that `exec`s ruby; a `#!/bin/sh` file with
    the import and no `'''exec'` line; a Python script that imports another
    package (pip's own script for `openreposhape`); and this installer's own
    bash file."""
    root = tmp_path.resolve()
    home = root / "home"
    target = bin_dir(home) / "openRepoTools"
    put_fixture(target, root, which)
    was = target.read_bytes()

    result = install_as(how, root, home, pipx_env(home))
    assert_placed_over(result, home, target, was)


@pytest.mark.parametrize("which", ["the-import-on-line-20",
                                   "the-import-on-line-21",
                                   "an-indented-import"])
@NEEDS_JQ
def test_pip_script_the_import_counts_at_column_0_in_the_first_20_lines(
        tmp_path, which):
    """THE IMPORT'S RULE, AT ITS EDGES (contracts/pipx-link.md, rule 2): one of
    the first 20 lines matches `^from openrepotools(\\.<name>)* import `, at
    column 0, as pip's template writes it. A Python script whose import is
    line 20 is pip's and refused; one whose import is line 21 is not, and
    is placed over; and so is one whose only import is indented, which pip
    never writes (research R6)."""
    root = tmp_path.resolve()
    home = root / "home"
    target = bin_dir(home) / "openRepoTools"
    python = f"{root}/pyenv/bin/python3.12"
    if which == "an-indented-import":
        lines = [f"#!{python}", "import sys", "if __name__ == '__main__':",
                 "    from openrepotools.cli import main", "    sys.exit(main())"]
        refused = False
    else:
        at = int(which.rsplit("-", 1)[1])
        lines = ([f"#!{python}"] + [f"# line {n}" for n in range(2, at)]
                 + ["from openrepotools.cli import main", "import sys",
                    "sys.exit(main())"])
        assert lines[at - 1] == "from openrepotools.cli import main"
        refused = at <= 20
    target.parent.mkdir(parents=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(0o755)
    before = file_state(target)

    result = install_as("checkout", root, home, pipx_env(home))
    if refused:
        assert_pip_s_refusal(result, home, target, before)
    else:
        assert_placed_over(result, home, target, before[-1])


# --- test_path_report_: the openRepoTools a shell will run -----------------

def a_path(root: Path, *ahead: Path) -> str:
    """A `PATH` of `ahead`, in order, then every tool the suite's own `PATH`
    carries except `openRepoTools`: so the first `openRepoTools` on it is one
    a case put there, or none at all, whatever the workstation has."""
    farm = path_without(root, "openRepoTools")
    return os.pathsep.join([*(str(p) for p in ahead), farm])


def notes(result: subprocess.CompletedProcess) -> list:
    return [line for line in result.stdout.splitlines()
            if line.startswith(NOTE_PREFIX)]


def assert_the_note(result: subprocess.CompletedProcess, note: str) -> None:
    """FR-021: the exact note, once, on stdout, as the run's last line (it
    runs last in a package-mode `--install`), with the exit status of an
    install that succeeded: the report changes nothing."""
    assert result.returncode == 0, transcript(result)
    assert "REFUSED:" not in result.stderr, transcript(result)
    assert notes(result) == [note], (
        f"the note, once:\n{note}\n{transcript(result)}")
    assert result.stdout.splitlines()[-1] == note, (
        f"the PATH report is not the run's last line:\n{transcript(result)}")


@NEEDS_JQ
def test_path_report_names_an_older_openrepotools_ahead_on_path(tmp_path):
    """US3 SCENARIO 4, THE FIRST FIXTURE: an older bash `openRepoTools`, in a
    directory ahead of `<dir>` on `PATH`. After a package-mode `--install`
    from pipx's venv, the note names that file as the first on `PATH`, and
    `<venv>/bin/openRepoTools` as this package's, and says to put pipx's
    link's directory ahead of that one. The exit status is the install's."""
    root = tmp_path.resolve()
    home = root / "home"
    venv, link = pipx_install(home, "1.17.8")
    older = root / "older-bin" / "openRepoTools"
    older.parent.mkdir()
    older.write_bytes(COMMAND.read_bytes()
                      + b"# an older openRepoTools, which a shell runs first\n")
    older.chmod(0o755)
    env = pipx_env(home, extra={"PATH": a_path(root, older.parent,
                                                bin_dir(home))})

    result = install(payload_of(venv) / "openRepoTools", home, env)
    assert_left_to_pipx(result, link)
    assert_the_note(result, PATH_NOTE.format(
        first=older, want=venv / "bin" / "openRepoTools",
        first_dir=older.parent))


@NEEDS_JQ
def test_path_report_names_this_installer_s_copy_when_pipx_s_bin_dir_is_elsewhere(
        tmp_path):
    """THE SECOND FIXTURE: `PIPX_BIN_DIR`'s link is in a directory other than
    `$OPENREPOTOOLS_BIN_DIR`, and that directory is not on `PATH`. So
    `<dir>` holds no link, the install places all seventeen there with
    today's count line, and the first `openRepoTools` on `PATH` is the bash
    file it just placed in `<dir>`: the note names it, and the package's
    `<venv>/bin/openRepoTools`. pipx's own link is left as it was."""
    root = tmp_path.resolve()
    home = root / "home"
    venv = layout.pipx_venv(home / ".local" / "share" / "pipx", "1.18.3")
    pipx_bin = home / "pipx-bin"
    pipx_link = pipx_bin / "openRepoTools"
    point(pipx_link, venv / "bin" / "openRepoTools")
    before = link_state(pipx_link)
    target_dir = bin_dir(home)
    target_dir.mkdir(parents=True)
    env = pipx_env(home, extra={"PATH": a_path(root, target_dir),
                                "OPENREPOTOOLS_BIN_DIR": str(target_dir)})
    env["PIPX_BIN_DIR"] = str(pipx_bin)

    result = install(payload_of(venv) / "openRepoTools", home, env)
    total = len(INSTALLED)
    placed = target_dir / "openRepoTools"
    assert (f"openRepoTools: {total} of {total} placed in {target_dir}"
            in result.stdout.splitlines()), transcript(result)
    assert placed.is_file() and not placed.is_symlink()
    assert_the_note(result, PATH_NOTE.format(
        first=placed, want=venv / "bin" / "openRepoTools",
        first_dir=target_dir))
    assert link_state(pipx_link) == before


@NEEDS_JQ
def test_path_report_says_none_when_no_openrepotools_is_on_path(tmp_path):
    """THE THIRD FIXTURE: no `openRepoTools` on `PATH` at all, `<dir>` among
    the absent. The note is its `none` form, which cannot name a directory
    to put ahead of, and it comes after the `export PATH` note, last."""
    root = tmp_path.resolve()
    home = root / "home"
    venv, link = pipx_install(home, "1.11.1")
    env = pipx_env(home, extra={"PATH": a_path(root)})

    result = install(payload_of(venv) / "openRepoTools", home, env)
    assert_left_to_pipx(result, link)
    note = PATH_NOTE_NONE.format(want=venv / "bin" / "openRepoTools")
    assert_the_note(result, note)
    out = result.stdout.splitlines()
    export = f'    export PATH="{link.parent}:$PATH"'
    assert export in out, transcript(result)
    assert out.index(export) < out.index(note)


@pytest.mark.parametrize("column, form", [("dot-local-share-pipx", "absolute"),
                                          ("home-with-a-space", "relative")])
@NEEDS_JQ
def test_path_report_says_nothing_when_pipx_s_link_is_first_on_path(
        tmp_path, column, form):
    """THE FOURTH FIXTURE: pipx's link is the first `openRepoTools` on
    `PATH`, and it resolves to this package's `<venv>/bin/openRepoTools`, so
    there is no note. Both sides go through `link_resolve`, so a relative
    link into a venv under a home whose path holds a space is the same file."""
    root = tmp_path.resolve()
    home = root / "home"
    venv, link = pipx_install(home, "1.18.3", home.joinpath(*PIPX_HOMES[column]),
                              form)
    env = pipx_env(home, extra={"PATH": a_path(root, link.parent)})

    result = install(payload_of(venv) / "openRepoTools", home, env)
    assert_left_to_pipx(result, link)
    assert notes(result) == [], transcript(result)


#: LAYOUTS THAT NAME NO `<prefix>` (research R7): a package's own
#: `openrepotools/` under directories that are not `lib/python*/site-packages`,
#: each wrong in one of the names `path_report` reads above it. The fourth
#: name, `openrepotools`, is one package mode itself requires (design.md
#: Decision 4), so no package-mode run reaches the skip that reads it.
NO_PREFIX = {
    "dist-packages": ("lib", "python3.12", "dist-packages"),
    "a-pypy-directory": ("lib", "pypy3.10", "site-packages"),
    "lib64": ("lib64", "python3.12", "site-packages"),
}


def package_under(prefix: Path, *between: str) -> Path:
    """A `package_tree`'s `openrepotools/`, every byte and mode kept, moved to
    `<prefix>/<between…>/openrepotools/`. Returns its `payload/`."""
    built = layout.package_tree(prefix.parent / f"{prefix.name}-built")
    package = prefix.joinpath(*between, "openrepotools")
    package.parent.mkdir(parents=True)
    built.parent.rename(package)
    return package / "payload"


@pytest.mark.parametrize("shape", NO_PREFIX)
@NEEDS_JQ
def test_path_report_says_nothing_where_the_layout_names_no_prefix(tmp_path,
                                                                  shape):
    """THE SILENT SKIP (research R7, contracts/cli-output.md). A package whose
    directories above `openrepotools/` are not `lib/python*/site-packages`
    names no `<prefix>`, so there is no `<prefix>/bin/openRepoTools` to
    compare the first `openRepoTools` on `PATH` with, and the report prints
    nothing. No `openRepoTools` is on `PATH`, which in R7's shape is the
    `none` note (`test_path_report_says_none_when_no_openrepotools_is_on_path`).
    The run is in package mode, as its `--version` shows, and the install
    exits 0 with today's count line: the skip changes nothing else."""
    root = tmp_path.resolve()
    home = root / "home"
    payload = package_under(root / "prefix", *NO_PREFIX[shape])
    env = pipx_env(home, extra={"PATH": a_path(root)})
    home.mkdir()
    version = subprocess.run(["bash", str(payload / "openRepoTools"),
                              "--version"], capture_output=True, text=True,
                             check=False, input="", env=env, cwd=str(home))
    assert (version.returncode, version.stdout.splitlines()[:1]) == (
        0, ["openRepoTools 0.0.0 (an unstamped package)"]), (
        f"the fixture is wrong: not a package-mode run:\n{transcript(version)}")

    result = install(payload / "openRepoTools", home, env)
    total = len(INSTALLED)
    assert result.returncode == 0, transcript(result)
    assert "REFUSED:" not in result.stderr, transcript(result)
    assert (f"openRepoTools: {total} of {total} placed in {bin_dir(home)}"
            in result.stdout.splitlines()), transcript(result)
    assert notes(result) == [], transcript(result)


@NEEDS_JQ
def test_path_report_is_a_package_s_report_and_a_checkout_prints_none(tmp_path):
    """THE REPORT BELONGS TO A PACKAGE-MODE `--install` (FR-021). A checkout's
    `--install`, with no `openRepoTools` on `PATH` before it ran, places its
    own `openRepoTools` and prints no note, because it has no package
    whose console script could be the one expected."""
    root = tmp_path.resolve()
    home = root / "home"
    env = pipx_env(home, extra={"PATH": a_path(root)})

    result = install_as("checkout", root, home, env)
    assert result.returncode == 0, transcript(result)
    assert notes(result) == [], transcript(result)


# --- test_pipx_upgrade_: a second wheel in the same venv --------------------

@NEEDS_JQ
def test_pipx_upgrade_a_second_wheel_replaces_the_sixteen_and_the_link_is_still_skipped(
        tmp_path):
    """US3 SCENARIO 5 (FR-022). One release installed by pipx and placed by
    `--install`; then `pipx upgrade openrepotools` puts a second package, with
    payload bytes of its own, in the same venv. Until `--install` runs
    again, nothing it placed has moved. Then it does: each of the sixteen, the
    skills and the command files is UPDATED to the second package's bytes,
    the link is skipped with the same two lines and left as it was, and the
    28 rows carry the new digests."""
    root = tmp_path.resolve()
    home = root / "home"
    pipx_home = home / ".local" / "share" / "pipx"
    venv = layout.pipx_venv(pipx_home, "1.17.8",
                            stamp=layout.stamp_text(**PIPX_RELEASE))
    link = bin_dir(home) / "openRepoTools"
    point(link, venv / "bin" / "openRepoTools")
    env = pipx_env(home)
    first = install(payload_of(venv) / "openRepoTools", home, env)
    assert_left_to_pipx(first, link)
    before = link_state(link)
    pipx_tree = pipx_home.relative_to(home).as_posix()
    placed_by_the_first = tree_state(home, (pipx_tree,))

    # `pipx upgrade openrepotools`: the second wheel's package, in this venv.
    second_release = {**PIPX_RELEASE, "VERSION": "1.2.0", "TAG": "v1.2.0"}
    assert layout.pipx_venv(pipx_home, "1.17.8", stamp=layout.stamp_text(
        **second_release)) == venv
    mark(payload_of(venv), "the second wheel")
    assert tree_state(home, (pipx_tree,)) == placed_by_the_first, (
        "something placed changed before `--install` ran again")

    second = install(payload_of(venv) / "openRepoTools", home, env)
    assert_left_to_pipx(second, link)
    assert link_state(link) == before
    out = second.stdout.splitlines()
    for destination, name in placed_files(home).items():
        if destination != str(link):
            assert f"{name}: updated at {destination}" in out, transcript(second)
    assert_placed_from(home, link, payload_of(venv))
    assert_rows_beside_the_link(home, link)


# --- test_pipx_uninstall_: the link and the venv gone ----------------------

@NEEDS_JQ
def test_pipx_uninstall_leaves_what_was_placed_and_a_checkout_then_places_a_regular_file(
        tmp_path):
    """US3 SCENARIO 6 (FR-023). `pipx uninstall openrepotools` removes its link
    and its venv, and nothing else: the sixteen, the skills, the command
    files, `settings.json` and the receipt are as the install left them.
    A checkout's `--install` then places a regular `openRepoTools` at the
    freed path, with today's count line and a row for it among the 29."""
    root = tmp_path.resolve()
    home = root / "home"
    venv, link = pipx_install(home, "1.18.3")
    first = install(payload_of(venv) / "openRepoTools", home, pipx_env(home))
    assert_left_to_pipx(first, link)
    pipx_tree = venv.parent.parent.relative_to(home).as_posix()
    the_link = link.relative_to(home).as_posix()
    kept = tree_state(home, (pipx_tree, the_link))

    # `pipx uninstall openrepotools`: its link and its venv.
    link.unlink()
    shutil.rmtree(venv)
    assert not os.path.lexists(link) and not venv.exists()
    assert tree_state(home, (pipx_tree, the_link)) == kept
    assert_placed_from(home, link, REPO)
    assert len(receipt_rows(home)) == ROWS_BESIDE_THE_LINK

    result = install_as("checkout", root, home, pipx_env(home))
    total = len(INSTALLED)
    out = result.stdout.splitlines()
    assert result.returncode == 0, transcript(result)
    assert f"openRepoTools: installed at {link}" in out, transcript(result)
    assert f"openRepoTools: {total} of {total} placed in {link.parent}" in out
    assert "left to pipx" not in result.stdout, transcript(result)
    assert link.is_file() and not link.is_symlink()
    assert stat.S_IMODE(link.stat().st_mode) == 0o755
    assert link.read_bytes() == COMMAND.read_bytes()
    for name in INSTALLED:
        if name != "openRepoTools":
            target = link.parent / name
            assert f"{name}: already installed at {target} (unchanged)" in out
    rows = receipt_rows(home)
    assert len(rows) == ARTIFACTS - HOOK_ENTRIES
    assert ("openRepoTools", str(link), hashlib.sha256(
        link.read_bytes()).hexdigest()) in {row[:3] for row in rows}
