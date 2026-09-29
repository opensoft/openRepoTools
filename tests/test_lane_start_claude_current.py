# SPDX-License-Identifier: Apache-2.0
"""`lane-start` and `claude-current`: which Claude Code a lane launches
(opensoft/workBenches#119, Brett Heap 2026-09-29, verbatim "for 2, we can run
update on every start, this ensures we have the latest models").

EVERY RUN HERE IS A REAL `lane-start` IN A SANDBOX, and the resolver is a
STUB. The sandbox is the lane suite's, cut down to one new lane: a bare origin
and a workspace clone whose register is a header, `workspace.yaml` pointing at
it, a fake `tmux` that answers the reads a launch makes, a fake `gh` that
refuses, and `$HOME`, `$TMPDIR` and `$OPENREPOTOOLS_BIN_DIR` all under
`tmp_path`. `claude-current` itself is `tests/test_claude_current.py`'s; the
stub here answers what a case needs and logs how it was called, so nothing
reaches npm or runs a real Claude Code.

The contract under test is docs/README-claude-current.md's:
  * CLAUDE_BIN unset: `claude-current --porcelain`, found beside `lane-start`
    or in $OPENREPOTOOLS_BIN_DIR and NEVER on PATH, names the launch by an
    absolute path; its exit 2 refuses the launch with 2 and its 1 with 1,
    before the register is written;
  * CLAUDE_BIN equal to CLAUDE_RESOLVED_BIN with no CLAUDE_VERIFIED_VERSION is
    inherited, not pinned, and is resolved again;
  * any other CLAUDE_BIN is a pin, launched as it is; with
    CLAUDE_VERIFIED_VERSION beside an equal CLAUDE_RESOLVED_BIN its version is
    recorded;
  * the log line carries `claude <version>`, and CLAUDE_VERIFIED_VERSION never
    reaches the session.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lane-start is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

LANE = "repoZ-1"
VERSION = "2.1.284"

#: The environment a case must not inherit from the host that runs it: every
#: seam `lane-start`, `lanes-edit.sh` and `claude-current` read.
SCRUBBED_PREFIXES = ("LANES_", "LANE_START_", "CLAUDE_", "OPENREPOTOOLS_",
                     "FAKE_", "GIT_", "NPM_CONFIG_", "npm_config_", "TMUX")
SCRUBBED = {"AGENT_PROTOCOL_ROOT", "PROJECTS_ROOT", "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME", "PCLAUDE"}

FAKE_TMUX = r"""#!/usr/bin/env bash
# The lane suite's fake tmux, cut down: this window is testsess:@1, index 0,
# named `claude`, and every other ref resolves nothing. rename-window and
# send-keys are logged; everything else answers nothing and succeeds.
case "${1-}" in
  display-message)
    shift
    t=""; f=""
    while [ $# -gt 0 ]; do
      case "$1" in
        -p) shift ;;
        -t) t="${2-}"; shift 2 ;;
        *)  f="$1"; shift ;;
      esac
    done
    if [ -n "$t" ]; then
      case "$t" in
        testsess:0|testsess:@1|@1) : ;;
        *) exit 1 ;;
      esac
      case "$f" in
        '#{window_id}')            echo '@1' ;;
        '#{window_name}')          echo 'claude' ;;
        '#{session_name}')         echo 'testsess' ;;
        '#{pane_current_command}') echo 'claude' ;;
        *)                         echo ;;
      esac
      exit 0
    fi
    case "$f" in
      '#{session_name}:#{window_id}')    echo 'testsess:@1' ;;
      '#{session_name}:#{window_index}') echo 'testsess:0' ;;
      '#S:#I')                           echo 'testsess:0' ;;
      '#{window_id}')                    echo '@1' ;;
      '#W'|'#{window_name}')             echo 'claude' ;;
      *)                                 echo ;;
    esac ;;
  rename-window)
    printf 'rename-window %s\n' "${2-}" >> "$FAKE_TMUX_LOG" ;;
  send-keys)
    shift
    printf 'send-keys %s\n' "$*" >> "$FAKE_TMUX_LOG" ;;
  *) : ;;
esac
"""

FAKE_GH = """#!/usr/bin/env bash
printf 'FAKE gh REFUSED: %s -- this suite reaches no GitHub surface\\n' "$*" >&2
exit 90
"""

#: A Claude Code that records how it was started and what it inherited. One
#: script, copied to every path a case launches, so the log says which one ran.
FAKE_CLAUDE = """#!/usr/bin/env bash
{
  printf 'ran %s: %s\\n' "$0" "$*"
  printf 'env CLAUDE_BIN=%s\\n' "${CLAUDE_BIN-<unset>}"
  printf 'env CLAUDE_RESOLVED_BIN=%s\\n' "${CLAUDE_RESOLVED_BIN-<unset>}"
  printf 'env CLAUDE_VERIFIED_VERSION=%s\\n' "${CLAUDE_VERIFIED_VERSION-<unset>}"
} >> "$FAKE_CLAUDE_LOG"
"""

#: The resolver stub: logs its arguments, then answers from FAKE_CC_* the way
#: `claude-current --porcelain` does.
FAKE_CLAUDE_CURRENT = """#!/usr/bin/env bash
printf '%s %s\\n' "$0" "$*" >> "$FAKE_CC_LOG"
if [ -n "${FAKE_CC_STDERR:-}" ]; then printf '%s\\n' "$FAKE_CC_STDERR" >&2; fi
if [ -n "${FAKE_CC_RAW:-}" ]; then printf '%s\\n' "$FAKE_CC_RAW"; exit "${FAKE_CC_RC:-0}"; fi
if [ "${FAKE_CC_RC:-0}" = 0 ]; then
  printf 'path=%s\\nversion=%s\\npublished=%s\\nstatus=%s\\n' \\
    "$FAKE_CC_PATH" "${FAKE_CC_VERSION-2.1.284}" "${FAKE_CC_PUBLISHED-2.1.284}" \\
    "${FAKE_CC_STATUS:-verified}"
fi
exit "${FAKE_CC_RC:-0}"
"""


def _write(path: Path, text: str, mode: int = 0o755) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)
    return path


class Sandbox:
    """One workstation with one register and one lane directory, repoZ."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.home = root / "home"
        self.bin = root / "bin"
        self.fakebin = root / "fakebin"
        self.origin = root / "origin.git"
        self.wip = self.home / "projects" / "wip"
        self.lane_dir = self.home / "projects" / "repoZ"
        self.claude_log = root / "claude.log"
        self.cc_log = root / "claude-current.log"
        self.tmux_log = root / "tmux.log"
        for d in (self.home / "projects", root / "tmp", self.fakebin, self.bin,
                  self.home / ".claude" / "sessions", self.home / ".agents"):
            d.mkdir(parents=True, exist_ok=True)
        for f in (self.claude_log, self.cc_log, self.tmux_log):
            f.write_text("", encoding="utf-8")

        base = {k: v for k, v in os.environ.items()
                if k not in SCRUBBED and not k.startswith(SCRUBBED_PREFIXES)}
        base.update({
            "HOME": str(self.home),
            "TMPDIR": str(root / "tmp"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "PATH": f"{self.fakebin}{os.pathsep}{self.bin}{os.pathsep}{base.get('PATH', '')}",
            "TMUX": f"{root}/fake-tmux-socket,0,0",
            "AGENT_PROTOCOL_ROOT": str(self.home / ".agents"),
            "OPENREPOTOOLS_BIN_DIR": str(self.bin),
            "CLAUDE_CONFIG_DIR": str(self.home / ".claude"),
            "LANES_WORKSTATION": "Eagle",
            "LANES_NO_GITHUB": "1",
            "FAKE_TMUX_LOG": str(self.tmux_log),
            "FAKE_CLAUDE_LOG": str(self.claude_log),
            "FAKE_CC_LOG": str(self.cc_log),
            "GIT_AUTHOR_NAME": "lane-start claude-current tests",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "lane-start claude-current tests",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        self.env = base

        for name in ("lane-start", "lanes-edit.sh", "repos.tsv"):
            shutil.copy2(REPO / name, self.bin / name)
            (self.bin / name).chmod(0o755)
        _write(self.fakebin / "tmux", FAKE_TMUX)
        _write(self.fakebin / "gh", FAKE_GH)
        self.path_claude = _write(self.fakebin / "claude", FAKE_CLAUDE)
        # A resolver on PATH that no case may ever reach.
        _write(self.fakebin / "claude-current",
               '#!/usr/bin/env bash\nprintf "PATH-DECOY %s\\n" "$*" >> "$FAKE_CC_LOG"\nexit 3\n')
        self.resolved = _write(root / "resolved" / "bin" / "claude", FAKE_CLAUDE)

        self.git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.git("clone", "-q", str(self.origin), str(self.wip))
        (self.wip / "lanes").mkdir()
        (self.wip / "handoffs").mkdir()
        (self.wip / "handoffs" / "README.md").write_text(
            "# handoffs\n", encoding="utf-8")
        (self.wip / "lanes" / "LANES.md").write_text(
            "# LANES.md -- the sandbox register\n\n"
            "| lane | session id | workstation / env / user | started (UTC) "
            "| objects owned | handoff path | state |\n"
            "|---|---|---|---|---|---|---|\n", encoding="utf-8")
        self.git("-C", str(self.wip), "add", "--", "lanes/LANES.md",
                 "handoffs/README.md")
        self.git("-C", str(self.wip), "commit", "-q", "-m", "seed")
        self.git("-C", str(self.wip), "push", "-q", "origin", "main")
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {self.origin}\npath: {self.wip}\n", encoding="utf-8")

        self.git("init", "-q", "-b", "main", str(self.lane_dir))
        self.git("-C", str(self.lane_dir), "remote", "add", "origin",
                 "https://github.com/opensoft/repoZ.git")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout

    def resolver(self, where: Path | None = None) -> Path:
        return _write((where or self.bin) / "claude-current", FAKE_CLAUDE_CURRENT)

    def start(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        full = dict(self.env)
        full.setdefault("FAKE_CC_PATH", str(self.resolved))
        full.update(env)
        return subprocess.run([str(self.bin / "lane-start"), "repoZ", "1", *args],
                              env=full, cwd=str(self.lane_dir),
                              capture_output=True, text=True, timeout=120,
                              check=False)

    def claude_runs(self) -> str:
        return self.claude_log.read_text(encoding="utf-8")

    def resolver_calls(self) -> str:
        return self.cc_log.read_text(encoding="utf-8")

    def lane_log(self) -> str:
        path = self.wip / "lanes" / "log" / f"{LANE}.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def commits(self) -> int:
        return int(self.git("-C", str(self.wip), "rev-list", "--count",
                            "HEAD").strip())


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path)


def _started_line(box: Sandbox) -> str:
    lines = [ln for ln in box.lane_log().splitlines() if ln.startswith("STARTED")]
    assert len(lines) == 1, box.lane_log()
    return lines[0]


def test_an_unset_claude_bin_launches_what_claude_current_names(box):
    stub = box.resolver()
    result = box.start()
    assert result.returncode == 0, result.stderr
    assert box.resolver_calls() == f"{stub} --porcelain\n"
    runs = box.claude_runs()
    assert runs.startswith(f"ran {box.resolved}: --name {LANE} --session-id "), runs
    assert f"ran {box.path_claude}" not in runs
    assert f"env CLAUDE_BIN={box.resolved}\n" in runs
    assert f"env CLAUDE_RESOLVED_BIN={box.resolved}\n" in runs
    assert "env CLAUDE_VERIFIED_VERSION=<unset>\n" in runs
    assert f"launching claude {VERSION} (verified) at {box.resolved}" in result.stderr


def test_the_log_line_records_the_version_claude_current_read(box):
    box.resolver()
    result = box.start()
    assert result.returncode == 0, result.stderr
    line = _started_line(box)
    assert line.endswith(f"; claude {VERSION}"), line
    assert "lane:repoZ-1 → home opensoft/repoZ; " in line, line


def test_a_refusal_ends_the_run_with_2_before_anything_is_written(box):
    box.resolver()
    before = box.commits()
    refused = ("claude-current: REFUSED: npm publishes claude 2.1.284 and the "
               "newest installed is 2.1.283")
    result = box.start(FAKE_CC_RC="2", FAKE_CC_STDERR=refused)
    assert result.returncode == 2, result.stderr
    assert refused in result.stderr
    assert "claude-current refused the launch (exit 2" in result.stderr
    assert "Nothing was written" in result.stderr
    assert box.claude_runs() == ""
    assert box.commits() == before
    assert box.lane_log() == ""
    assert "repoZ-1" not in (box.wip / "lanes" / "LANES.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("fake", [
    {"FAKE_CC_RC": "1"},
    {"FAKE_CC_RAW": "not porcelain"},
    {"FAKE_CC_PATH": "relative/claude"},
    {"FAKE_CC_PATH": "/nonexistent/claude-current-test/claude"},
])
def test_a_resolver_that_names_nothing_runnable_ends_the_run_with_1(box, fake):
    box.resolver()
    before = box.commits()
    result = box.start(**fake)
    assert result.returncode == 1, result.stderr
    assert "Nothing was written" in result.stderr
    assert box.claude_runs() == ""
    assert box.commits() == before


def test_a_launchers_verified_version_is_trusted_recorded_and_removed(box):
    """claude-profile ran its own claude-current and hands on all three."""
    box.resolver()
    result = box.start(CLAUDE_BIN=str(box.resolved),
                       CLAUDE_RESOLVED_BIN=str(box.resolved),
                       CLAUDE_VERIFIED_VERSION="2.1.290")
    assert result.returncode == 0, result.stderr
    assert box.resolver_calls() == ""
    runs = box.claude_runs()
    assert runs.startswith(f"ran {box.resolved}: --name {LANE}"), runs
    assert "env CLAUDE_VERIFIED_VERSION=<unset>\n" in runs
    assert _started_line(box).endswith("; claude 2.1.290")


def test_an_operator_pin_is_launched_as_it_is_and_records_no_version(box):
    box.resolver()
    pinned = _write(box.root / "pinned" / "claude", FAKE_CLAUDE)
    result = box.start(CLAUDE_BIN=str(pinned))
    assert result.returncode == 0, result.stderr
    assert box.resolver_calls() == ""
    assert box.claude_runs().startswith(f"ran {pinned}: --name {LANE}")
    assert "; claude " not in _started_line(box)


def test_a_version_beside_a_different_resolved_path_is_not_the_pins(box):
    """CLAUDE_VERIFIED_VERSION describes CLAUDE_RESOLVED_BIN. A CLAUDE_BIN
    that is some other path is a pin, and that version is not its version."""
    box.resolver()
    pinned = _write(box.root / "pinned" / "claude", FAKE_CLAUDE)
    result = box.start(CLAUDE_BIN=str(pinned),
                       CLAUDE_RESOLVED_BIN=str(box.resolved),
                       CLAUDE_VERIFIED_VERSION="2.1.290")
    assert result.returncode == 0, result.stderr
    assert box.resolver_calls() == ""
    assert "env CLAUDE_VERIFIED_VERSION=<unset>\n" in box.claude_runs()
    assert "; claude " not in _started_line(box)


def test_an_inherited_resolution_is_resolved_again(box):
    """A session's own environment carries CLAUDE_BIN and CLAUDE_RESOLVED_BIN
    from the launch that started it. A launch from inside it is not pinned."""
    stub = box.resolver()
    old = _write(box.root / "old" / "claude", FAKE_CLAUDE)
    result = box.start(CLAUDE_BIN=str(old), CLAUDE_RESOLVED_BIN=str(old))
    assert result.returncode == 0, result.stderr
    assert box.resolver_calls() == f"{stub} --porcelain\n"
    assert box.claude_runs().startswith(f"ran {box.resolved}: --name {LANE}")
    assert _started_line(box).endswith(f"; claude {VERSION}")


def test_dry_run_plans_the_resolution_and_runs_nothing(box):
    stub = box.resolver()
    before = box.commits()
    result = box.start("--dry-run")
    assert result.returncode == 0, result.stderr
    assert f"lane-start: PLAN {stub} --porcelain" in result.stderr
    assert box.resolver_calls() == ""
    assert box.claude_runs() == ""
    assert box.commits() == before


def test_no_launch_resolves_nothing(box):
    """The first act inside a running session: nothing is launched, so there
    is nothing to choose, and nothing may be updated under the session."""
    box.resolver()
    result = box.start("--no-launch")
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(f"claude --name {LANE}"), result.stdout
    assert box.resolver_calls() == ""
    assert box.claude_runs() == ""


def test_no_resolver_beside_it_launches_the_path_claude_and_says_so(box):
    """The lane suite's shape: `lane-start` copied without claude-current.
    The decoy on PATH proves the resolver is never looked for there."""
    result = box.start()
    assert result.returncode == 0, result.stderr
    assert box.resolver_calls() == ""
    assert box.claude_runs().startswith(f"ran {box.path_claude}: --name {LANE}")
    assert "no claude-current beside this command" in result.stderr
    assert "; claude " not in _started_line(box)


def test_the_resolver_is_found_in_the_bin_dir_when_not_beside_it(box):
    elsewhere = box.root / "installed"
    stub = box.resolver(elsewhere)
    result = box.start(OPENREPOTOOLS_BIN_DIR=str(elsewhere))
    assert result.returncode == 0, result.stderr
    assert box.resolver_calls() == f"{stub} --porcelain\n"
    assert box.claude_runs().startswith(f"ran {box.resolved}: --name {LANE}")


def test_a_version_that_is_not_one_is_left_off_the_log_line(box):
    box.resolver()
    result = box.start(FAKE_CC_VERSION="2.1; rm")
    assert result.returncode == 0, result.stderr
    assert "is not x.y.z" in result.stderr
    assert "; claude " not in _started_line(box)


def test_another_agent_never_asks_claude_current(box):
    box.resolver()
    _write(box.fakebin / "codex", FAKE_CLAUDE)
    result = box.start("--agent", "codex")
    assert result.returncode == 0, result.stderr
    assert box.resolver_calls() == ""
    assert box.claude_runs().startswith(f"ran {box.fakebin / 'codex'}: ")
