# SPDX-License-Identifier: Apache-2.0
"""`claude-current`: the Claude Code a launch should start (opensoft/workBenches#119).

EVERYTHING HERE IS FAKED, AND NOTHING REACHES A NETWORK OR A REAL INSTALL.
`$HOME` is a temporary directory; `npm` and `node` are scripts first on the
command's own seams (`CLAUDE_CURRENT_NPM`, `CLAUDE_CURRENT_NODE`); every
candidate is a small script that answers `--version`; the user npm prefix,
the native versions directory, the image's system candidates and the lock
directory all live under `tmp_path`. `CLAUDE_CURRENT_SYSTEM_CANDIDATES` is
always set, so the real `/usr/local/bin/claude` and `/usr/bin/claude` of the
machine running the suite are never read.

The cases follow the issue's Ask 1-8: the published version with a bound,
candidates by ABSOLUTE PATH and never by PATH, the update when behind under a
lock, verify and hand back one path, refuse with one escape, offline is not a
refusal, say what launched.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

import test_repo_hygiene as hygiene

CMD = REPO / "claude-current"
PACKAGE = "@anthropic-ai/claude-code"

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="claude-current is a bash script"),
              WINDOWS_SKIP]

#: A candidate: answers `--version` with `<version> (Claude Code)`, logs every
#: other call, and, for a NATIVE install, answers `update` by writing the
#: version `$FAKE_NATIVE_UPDATE_TO` names beside itself.
FAKE_CLAUDE = r"""#!/usr/bin/env bash
v='@VERSION@'
printf '%s %s\n' "$0" "$*" >> "${FAKE_CLAUDE_LOG:-/dev/null}"
case "${1:-}" in
  --version) printf '%s (Claude Code)\n' "$v" ;;
  update)
    [ "${FAKE_NATIVE_UPDATE_RC:-0}" = 0 ] || exit "$FAKE_NATIVE_UPDATE_RC"
    to="${FAKE_NATIVE_UPDATE_TO:-}"
    if [ -n "$to" ]; then
      sed -e "s/^v='[^']*'/v='$to'/" "$0" > "$(dirname "$0")/$to"
      chmod 755 "$(dirname "$0")/$to"
    fi ;;
esac
"""

#: npm: `view` answers `$FAKE_NPM_PUBLISHED` (or fails, or sleeps); `install -g
#: --prefix <p> … <pkg>@<v>` lays the package out the way npm does — the
#: launcher linked from `<p>/bin/claude` into `lib/node_modules` — and, with
#: `$FAKE_NPM_HOOK_NEEDED=1`, leaves the launcher a stub until the package's
#: `install.cjs` has run, which is npm 12's skipped native-binary hook.
FAKE_NPM = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "${FAKE_NPM_LOG:-/dev/null}"
case "${1:-}" in
  view)
    [ -n "${FAKE_NPM_VIEW_SLEEP:-}" ] && sleep "$FAKE_NPM_VIEW_SLEEP"
    [ "${FAKE_NPM_VIEW_RC:-0}" = 0 ] || exit "$FAKE_NPM_VIEW_RC"
    printf '%s\n' "${FAKE_NPM_PUBLISHED:-}" ;;
  install)
    [ "${FAKE_NPM_INSTALL_RC:-0}" = 0 ] || { echo "npm ERR! fake failure" >&2; exit "$FAKE_NPM_INSTALL_RC"; }
    prefix=""; spec=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --prefix) prefix="$2"; shift 2 ;;
        @anthropic-ai/claude-code@*) spec="$1"; shift ;;
        *) shift ;;
      esac
    done
    v="${spec##*@}"
    pkg="$prefix/lib/node_modules/@anthropic-ai/claude-code"
    rm -rf "$pkg"; mkdir -p "$pkg/bin" "$prefix/bin"
    printf '{\n  "name": "@anthropic-ai/claude-code",\n  "version": "%s"\n}\n' "$v" > "$pkg/package.json"
    sed -e "s/@VERSION@/$v/" "$FAKE_CLAUDE_TEMPLATE" > "$pkg/claude.real"
    chmod 755 "$pkg/claude.real"
    if [ "${FAKE_NPM_HOOK_NEEDED:-0}" = 1 ]; then
      printf '#!/usr/bin/env bash\necho "the native binary was never installed" >&2\nexit 1\n' > "$pkg/bin/claude.exe"
    else
      cp "$pkg/claude.real" "$pkg/bin/claude.exe"
    fi
    chmod 755 "$pkg/bin/claude.exe"
    printf 'cp "%s" "%s"\n' "$pkg/claude.real" "$pkg/bin/claude.exe" > "$pkg/install.cjs"
    ln -sfn ../lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe "$prefix/bin/claude" ;;
esac
"""

#: node: runs the fake package's `install.cjs`, which is a shell line.
FAKE_NODE = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "${FAKE_NODE_LOG:-/dev/null}"
bash "$1"
"""


class Sandbox:
    """One hermetic world for one case."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.home = root / "home"
        self.bin = root / "bin"
        self.prefix = root / "prefix"
        self.native = self.home / ".local" / "share" / "claude" / "versions"
        self.system = root / "system"
        self.cache = root / "cache"
        for d in (self.home, self.bin, self.system, self.cache):
            d.mkdir(parents=True, exist_ok=True)
        self.template = root / "fake-claude.template"
        self.template.write_text(FAKE_CLAUDE)
        self._script(self.bin / "npm", FAKE_NPM)
        self._script(self.bin / "node", FAKE_NODE)
        self.npm_log = root / "npm.log"
        self.node_log = root / "node.log"
        self.claude_log = root / "claude.log"
        for log in (self.npm_log, self.node_log, self.claude_log):
            log.write_text("")
        self.system_candidates: list[Path] = []

    @staticmethod
    def _script(path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o755)
        return path

    def claude(self, path: Path, version: str) -> Path:
        return self._script(path, FAKE_CLAUDE.replace("@VERSION@", version))

    def native_version(self, version: str) -> Path:
        return self.claude(self.native / version, version)

    def user_copy(self, version: str) -> Path:
        """An npm install in the user prefix, laid out the way npm lays it out."""
        pkg = self.prefix / "lib" / "node_modules" / "@anthropic-ai" / "claude-code"
        exe = self.claude(pkg / "bin" / "claude.exe", version)
        (pkg / "package.json").write_text(
            f'{{\n  "name": "{PACKAGE}",\n  "version": "{version}"\n}}\n')
        link = self.prefix / "bin" / "claude"
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(Path("..") / "lib" / "node_modules" / "@anthropic-ai"
                        / "claude-code" / "bin" / "claude.exe")
        assert exe.is_file()
        return link

    def system_copy(self, name: str, version: str) -> Path:
        path = self.claude(self.system / name / "claude", version)
        self.system_candidates.append(path)
        return path

    def env(self, **extra: str) -> dict:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("CLAUDE_", "FAKE_", "NPM_CONFIG", "npm_config"))}
        env.update({
            "HOME": str(self.home),
            "PATH": f"{self.bin}{os.pathsep}{env.get('PATH', '/usr/bin:/bin')}",
            "XDG_CACHE_HOME": str(self.root / "xdg-cache"),
            "CLAUDE_CURRENT_NPM": str(self.bin / "npm"),
            "CLAUDE_CURRENT_NODE": str(self.bin / "node"),
            "CLAUDE_CURRENT_NPM_PREFIX": str(self.prefix),
            "CLAUDE_CURRENT_CACHE_DIR": str(self.cache),
            "CLAUDE_CURRENT_SYSTEM_CANDIDATES": ":".join(str(p) for p in self.system_candidates),
            "FAKE_NPM_LOG": str(self.npm_log),
            "FAKE_NODE_LOG": str(self.node_log),
            "FAKE_CLAUDE_LOG": str(self.claude_log),
            "FAKE_CLAUDE_TEMPLATE": str(self.template),
            "FAKE_NPM_PUBLISHED": "2.1.284",
        })
        env.update(extra)
        return env

    def run(self, *args: str, timeout: float = 60, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(CMD), *args], env=self.env(**extra),
                              capture_output=True, text=True, timeout=timeout,
                              check=False)

    def installs(self) -> list[str]:
        return [line for line in self.npm_log.read_text().splitlines()
                if line.startswith("install")]


def porcelain(result: subprocess.CompletedProcess) -> dict:
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines())
    assert sorted(fields) == ["path", "published", "status", "version"], result.stdout
    return fields


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path)


# --- Ask 4 and 7: verify, hand back one absolute path, say what launched ------

def test_a_current_user_copy_is_verified_and_printed_by_its_absolute_path(box):
    link = box.user_copy("2.1.284")
    result = box.run()
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{link}\n"
    assert f"claude-current: claude 2.1.284 (verified against npm 2.1.284) at {link}" \
        in result.stderr
    assert box.installs() == [], "a current copy must not be reinstalled"


def test_porcelain_is_four_lines_naming_path_version_published_and_status(box):
    link = box.user_copy("2.1.284")
    result = box.run("--porcelain")
    assert result.returncode == 0, result.stderr
    assert porcelain(result) == {"path": str(link), "version": "2.1.284",
                                 "published": "2.1.284", "status": "verified"}


def test_the_published_version_is_asked_of_npm_fresh(box):
    box.user_copy("2.1.284")
    box.run()
    views = [line for line in box.npm_log.read_text().splitlines()
             if line.startswith("view")]
    assert views == [f"view {PACKAGE} version --prefer-online"]


# --- Ask 2: candidates by absolute path, never through PATH ------------------

def test_a_claude_first_on_path_is_never_consulted(box):
    """The py-bench case of 2026-09-29: two installs competed on PATH. The one
    on PATH here is the NEWEST and is still never run, because a launch is
    decided by absolute paths alone."""
    box.claude(box.bin / "claude", "9.9.9")
    link = box.user_copy("2.1.284")
    result = box.run("--porcelain")
    assert porcelain(result)["path"] == str(link)
    assert str(box.bin / "claude") not in box.claude_log.read_text()


def test_the_image_copy_behind_npm_loses_to_the_user_copy_that_equals_it(box):
    box.system_copy("usr", "2.1.280")
    link = box.user_copy("2.1.284")
    result = box.run("--porcelain")
    assert porcelain(result)["path"] == str(link)


def test_an_image_copy_that_equals_npm_is_launched_when_it_is_the_only_one(box):
    image = box.system_copy("usr", "2.1.284")
    result = box.run("--porcelain")
    fields = porcelain(result)
    assert (fields["path"], fields["status"]) == (str(image), "verified")


def test_an_equal_candidate_beats_a_newer_one(box):
    box.native_version("2.1.285")
    link = box.user_copy("2.1.284")
    fields = porcelain(box.run("--porcelain"))
    assert (fields["path"], fields["status"]) == (str(link), "verified")


def test_the_native_versions_are_ordered_numerically_not_by_name(box):
    """workBenches #109's ordering: 2.1.10 is newer than 2.1.9."""
    box.native_version("2.1.9")
    newest = box.native_version("2.1.10")
    fields = porcelain(box.run("--porcelain", FAKE_NPM_PUBLISHED="2.1.10"))
    assert (fields["path"], fields["status"]) == (str(newest), "verified")


def test_one_file_under_two_spellings_is_read_once(box):
    """`~/.local/bin/claude` is the native installer's link to its version
    file. It is ONE candidate, kept under its first spelling."""
    native = box.native_version("2.1.283")
    local = box.home / ".local" / "bin" / "claude"
    local.parent.mkdir(parents=True)
    local.symlink_to(native)
    result = box.run(FAKE_NPM_INSTALL_RC="1", FAKE_NATIVE_UPDATE_RC="1")
    assert result.returncode == 2, result.stderr
    assert f"Installed: 2.1.283 at {native}." in result.stderr


# --- Ask 3: update when behind, under a lock ---------------------------------

def test_a_user_copy_behind_npm_is_updated_in_the_user_prefix_and_verified(box):
    link = box.user_copy("2.1.283")
    result = box.run("--porcelain")
    assert result.returncode == 0, result.stderr
    assert box.installs() == [
        f"install -g --prefix {box.prefix} --no-fund --no-audit {PACKAGE}@2.1.284"]
    fields = porcelain(result)
    assert fields == {"path": str(link), "version": "2.1.284",
                      "published": "2.1.284", "status": "verified"}
    assert "updated" in result.stderr


def test_the_package_hook_npm_skipped_is_run_before_the_version_is_read(box):
    box.user_copy("2.1.283")
    result = box.run("--porcelain", FAKE_NPM_HOOK_NEEDED="1")
    assert result.returncode == 0, result.stderr
    hook = box.prefix / "lib" / "node_modules" / "@anthropic-ai" / "claude-code" / "install.cjs"
    assert box.node_log.read_text().splitlines() == [str(hook)]
    assert porcelain(result)["status"] == "verified"


def test_a_native_install_behind_npm_is_updated_with_claude_update(box):
    box.native_version("2.1.283")
    result = box.run("--porcelain", FAKE_NATIVE_UPDATE_TO="2.1.284")
    assert result.returncode == 0, result.stderr
    fields = porcelain(result)
    assert (fields["path"], fields["status"]) == (str(box.native / "2.1.284"), "verified")
    assert f"{box.native / '2.1.283'} update" in box.claude_log.read_text()
    assert box.installs() == [], "the native update reached npm's version"


def test_a_native_update_that_stops_short_falls_back_to_the_user_prefix(box):
    """A native install on another channel (npm's `stable` tag lags `latest`)
    cannot reach the published version with `claude update`, so the user
    prefix is installed instead."""
    box.native_version("2.1.283")
    result = box.run("--porcelain", FAKE_NATIVE_UPDATE_TO="")
    assert result.returncode == 0, result.stderr
    assert len(box.installs()) == 1
    fields = porcelain(result)
    assert (fields["path"], fields["status"]) == (str(box.prefix / "bin" / "claude"), "verified")


def test_nothing_installed_is_installed_into_the_user_prefix(box):
    fields = porcelain(box.run("--porcelain"))
    assert (fields["path"], fields["status"]) == (str(box.prefix / "bin" / "claude"), "verified")


def _hold_lock(box: Sandbox, seconds: int, then: str = ":") -> subprocess.Popen:
    """Hold the update lock the way a second launch would, then run `then`."""
    lock = box.cache / "claude-current.lock"
    if shutil.which("flock"):
        script = f'exec 9>>"{lock}"; flock 9; touch "{box.root}/held"; sleep {seconds}; {then}'
    else:
        script = (f'mkdir "{lock}.d"; echo $$ > "{lock}.d/pid"; touch "{box.root}/held"; '
                  f'sleep {seconds}; {then}; rm -rf "{lock}.d"')
    proc = subprocess.Popen(["bash", "-c", script], env=box.env())
    deadline = time.monotonic() + 10
    while not (box.root / "held").exists():
        assert time.monotonic() < deadline, "the lock holder never took the lock"
        time.sleep(0.05)
    return proc


def test_a_launch_waits_for_another_launchs_update_and_does_not_repeat_it(box):
    box.user_copy("2.1.283")
    installer = (f'"{box.bin / "npm"}" install -g --prefix "{box.prefix}" '
                 f'{PACKAGE}@2.1.284 >/dev/null 2>&1')
    holder = _hold_lock(box, 2, then=installer)
    try:
        result = box.run("--porcelain")
    finally:
        holder.wait(timeout=30)
    assert result.returncode == 0, result.stderr
    assert porcelain(result)["status"] == "verified"
    assert "updated by another launch" in result.stderr
    assert len(box.installs()) == 1, "only the other launch installed"


def test_a_lock_that_is_never_free_is_a_refusal_that_names_it(box):
    box.user_copy("2.1.283")
    holder = _hold_lock(box, 8)
    try:
        result = box.run(CLAUDE_CURRENT_LOCK_WAIT="1")
    finally:
        holder.kill()
        holder.wait(timeout=30)
    assert result.returncode == 2, result.stderr
    assert "was not free within 1s" in result.stderr
    assert box.installs() == []


# --- Ask 5: refuse, with one escape ------------------------------------------

def test_a_launch_still_behind_after_the_update_is_refused(box):
    link = box.user_copy("2.1.283")
    result = box.run(FAKE_NPM_INSTALL_RC="1")
    assert result.returncode == 2
    assert result.stdout == "", "a refusal hands back no path to launch"
    for want in ("REFUSED", "npm publishes claude 2.1.284",
                 f"the newest installed is 2.1.283 at {link}",
                 f"Fix: npm install -g --prefix {box.prefix} {PACKAGE}@2.1.284",
                 "CLAUDE_ALLOW_STALE=1 launches 2.1.283 anyway"):
        assert want in result.stderr, want


def test_claude_allow_stale_launches_the_newest_and_says_it_is_stale(box):
    link = box.user_copy("2.1.283")
    result = box.run("--porcelain", FAKE_NPM_INSTALL_RC="1", CLAUDE_ALLOW_STALE="1")
    assert result.returncode == 0, result.stderr
    assert porcelain(result) == {"path": str(link), "version": "2.1.283",
                                 "published": "2.1.284", "status": "stale"}
    assert "STALE:" in result.stderr


def test_a_copy_ahead_of_npm_launches_as_ahead_and_nothing_is_installed(box):
    link = box.user_copy("2.1.285")
    result = box.run("--porcelain")
    assert result.returncode == 0, result.stderr
    fields = porcelain(result)
    assert (fields["path"], fields["status"]) == (str(link), "ahead")
    assert "ahead of npm 2.1.284" in result.stderr
    assert box.installs() == []


# --- Ask 6: offline is not a refusal -----------------------------------------

def test_npm_unreachable_launches_the_newest_installed_unverified(box):
    box.native_version("2.1.280")
    link = box.user_copy("2.1.283")
    result = box.run("--porcelain", FAKE_NPM_VIEW_RC="1")
    assert result.returncode == 0, result.stderr
    assert porcelain(result) == {"path": str(link), "version": "2.1.283",
                                 "published": "", "status": "unverified"}
    assert "UNVERIFIED: could not reach npm" in result.stderr
    assert box.installs() == []


def test_npm_that_hangs_is_bounded_by_the_timeout(box):
    box.user_copy("2.1.283")
    started = time.monotonic()
    result = box.run("--porcelain", FAKE_NPM_VIEW_SLEEP="30", CLAUDE_CURRENT_TIMEOUT="1")
    assert time.monotonic() - started < 20, "npm view was not bounded"
    assert result.returncode == 0, result.stderr
    assert porcelain(result)["status"] == "unverified"
    assert "took longer than 1s" in result.stderr


def test_offline_reads_no_npm_and_installs_nothing(box):
    link = box.user_copy("2.1.283")
    result = box.run("--porcelain", "--offline")
    assert result.returncode == 0, result.stderr
    assert porcelain(result)["path"] == str(link)
    assert porcelain(result)["status"] == "unverified"
    assert box.npm_log.read_text() == ""


def test_nothing_installed_and_npm_unreachable_is_exit_1(box):
    result = box.run(FAKE_NPM_VIEW_RC="1")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "no runnable Claude Code was found by absolute path" in result.stderr


def test_no_npm_at_all_is_unverified_not_a_crash(box):
    link = box.user_copy("2.1.283")
    result = box.run("--porcelain", CLAUDE_CURRENT_NPM=str(box.root / "no-such-npm"))
    assert result.returncode == 0, result.stderr
    assert porcelain(result)["path"] == str(link)
    assert "there is no npm" in result.stderr


# --- the user prefix ----------------------------------------------------------

def test_the_user_prefix_falls_back_to_npm_config_prefix_then_to_npm_global(box):
    elsewhere = box.root / "configured-prefix"
    env = {"CLAUDE_CURRENT_NPM_PREFIX": ""}
    result = box.run("--porcelain", NPM_CONFIG_PREFIX=str(elsewhere), **env)
    assert porcelain(result)["path"] == str(elsewhere / "bin" / "claude")
    result = box.run("--porcelain", **env)
    assert porcelain(result)["path"] == str(box.home / ".npm-global" / "bin" / "claude")


def test_the_user_prefix_is_read_from_the_npmrc_prefix_line(box):
    (box.home / ".npmrc").write_text("fund=false\nprefix = ~/tools/npm\n")
    result = box.run("--porcelain", CLAUDE_CURRENT_NPM_PREFIX="")
    assert porcelain(result)["path"] == str(box.home / "tools" / "npm" / "bin" / "claude")


# --- usage --------------------------------------------------------------------

def test_help_and_an_unknown_argument(box):
    result = box.run("--help")
    assert result.returncode == 0
    assert result.stdout.startswith("claude-current [--porcelain] [--offline]\n")
    result = box.run("--bogus")
    assert result.returncode == 64
    assert "unknown argument: --bogus" in result.stderr


@pytest.mark.parametrize("name", ["TIMEOUT", "VERSION_TIMEOUT", "UPDATE_TIMEOUT", "LOCK_WAIT"])
def test_a_malformed_bound_is_refused_before_anything_runs(box, name):
    result = box.run(**{f"CLAUDE_CURRENT_{name}": "soon"})
    assert result.returncode == 1
    assert f"CLAUDE_CURRENT_{name} must be a whole number" in result.stderr
    assert box.npm_log.read_text() == ""


# --- the file itself ------------------------------------------------------------

#: The rules `tests/test_repo_hygiene.py` holds every listed bash file to,
#: asked of the two #119 commands, which its lists do not name yet (that file
#: is another open pull request's, opensoft/openRepoTools#93, so this one
#: calls its rules rather than editing its lists).
HYGIENE_RULES = [
    hygiene.test_shipped_bash_parses_under_bash,
    hygiene.test_no_shipped_bash_ends_its_options_after_an_operand,
    hygiene.test_no_shipped_bash_leaves_a_variable_name_to_bash_3_2s_locale,
    hygiene.test_no_shipped_bash_quotes_the_replacement_half_of_a_substitution,
    hygiene.test_no_shipped_bash_opens_a_case_inside_a_command_substitution,
    hygiene.test_no_shipped_bash_reaches_for_gnu_only_utilities_unaccompanied,
]


@pytest.mark.parametrize("rule", HYGIENE_RULES, ids=lambda r: r.__name__)
@pytest.mark.parametrize("name", ["claude-current", "claude-restart-check"])
def test_the_two_commands_keep_the_repositorys_bash_rules(name, rule):
    rule(name)


def test_claude_current_fails_loudly_and_claude_restart_check_never_does():
    """`claude-current` is a launch's gate, so it stops at the first failure;
    `claude-restart-check` runs inside every status line render, so it takes
    `set -u` and never `set -e` — `lane-handoff`'s exception, for its reason."""
    hygiene.test_shipped_bash_is_executable_and_fails_loudly("claude-current")
    hygiene.test_the_lane_helpers_are_executable_and_declare_their_discipline(
        "claude-restart-check")
    code = [line for line in
            (REPO / "claude-restart-check").read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")]
    assert not [line for line in code if re.match(r"\s*set\s+-[a-z]*e", line)], (
        "claude-restart-check must not `set -e`: a failed read has to reach its "
        "own 'print nothing, exit 0', not end the status line's render")


def test_the_macos_job_parses_both_commands_with_bash_3_2():
    workflow = (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    for name in ("claude-current", "claude-restart-check"):
        assert f"/bin/bash -n {name}" in workflow, name


def _function(text: str, name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", text, re.S | re.M)
    assert match, f"no {name}() in the file"
    return match.group(0)


@pytest.mark.parametrize("name", ["numcmp", "vercmp"])
def test_both_commands_order_versions_with_the_same_code(name):
    """One idea of "newer" in both commands: a restart notice that disagreed
    with the resolver about which version is newer would contradict it."""
    current = (REPO / "claude-current").read_text(encoding="utf-8")
    check = (REPO / "claude-restart-check").read_text(encoding="utf-8")
    assert _function(current, name) == _function(check, name)
