# SPDX-License-Identifier: Apache-2.0
"""`lane-start`'s row stamp under a long checkout path (opensoft/openRepoTools#180).

THE STAMP'S TAIL IS THE PART A CUT TAKES, AND THAT IS THE DESIGN. Amendment
11(c) puts the lane's `dir` and `window` in the tail of the stamp a resume
writes; Amendment 13(a) makes the cell ONE line under ratified decision O1's
240 characters; and `lane-start` orders that line so `cut_to_line` takes `dir`
and `window` first, because both are this same act's sub-fields in the lane's
own log and columns of Amendment 11's listing — a cut loses what a reader can
look up, never the head `row_stamp_is_unknown` reads.

So the tail's length is the CHECKOUT PATH's length, and #180 was a shell-suite
case that put its checkout under `$HOME/projects` inside the run root: green
under plain pytest's short `/tmp`, red under `tests/run.sh`'s per-run root
(`TMPDIR` about 71 characters, so a `$HOME` about 91). These cases drive a real
`lane-start` twice, `--no-launch`, in that shape — a `$HOME` at least as long
as `run.sh`'s — with the checkout at three EXACT lengths, so the answer does not
depend on where pytest itself was run:

  * a short checkout keeps the whole tail, however long `$HOME` is — which is
    what `tests/test_lane_helpers.sh`'s clause (c) TAIL case now uses, on a
    checkout of at most 65 characters;
  * a checkout whose path still fits loses only the `window` ref;
  * a longer one loses the path WHOLE, never a truncated path that reads as a
    real one. That is what #180's case read under `run.sh`'s root:
    `… window renamed, no launch; dir ...`, its cut landing on the `;` that
    follows the path, so the path went with it;

and in every one the head is intact, the line is inside the cap, and the
lane's log carries both facts in full.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP, rmtree

pytestmark = [pytest.mark.skipif(shutil.which("bash") is None,
                                 reason="lane-start is a bash script"),
              pytest.mark.skipif(shutil.which("git") is None,
                                 reason="the register is a git repository"),
              WINDOWS_SKIP]

LANE = "repoZ-1"
WINDOW = "testsess:0 @1"

#: `tests/run.sh`'s `$HOME` for the shell suite, as #180 measured it: a run
#: root `TMPDIR` of about 71 characters, the suite's `mktemp -d` beneath it
#: (`/tmp.XXXXXXXXXX`, 15) and `/home` (5).
RUN_SH_HOME = 91

SCRUBBED_PREFIXES = ("LANES_", "LANE_START_", "CLAUDE_", "OPENREPOTOOLS_",
                     "FAKE_", "GIT_", "TMUX")
SCRUBBED = {"AGENT_PROTOCOL_ROOT", "PROJECTS_ROOT", "XDG_CONFIG_HOME",
            "XDG_CACHE_HOME"}

#: The lane suite's fake tmux, cut down to one window, `testsess:0 @1`, whose
#: name is `$FAKE_TMUX_WINDOW_NAME` — `claude` on a first start and the lane
#: on the second, as a window lane-start renamed would answer.
FAKE_TMUX = r"""#!/usr/bin/env bash
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
        '#{window_name}')          echo "${FAKE_TMUX_WINDOW_NAME:-claude}" ;;
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
      '#W'|'#{window_name}')             echo "${FAKE_TMUX_WINDOW_NAME:-claude}" ;;
      *)                                 echo ;;
    esac ;;
  rename-window)
    printf 'rename-window %s\n' "${2-}" >> "$FAKE_TMUX_LOG" ;;
  *) : ;;
esac
"""

#: The workspace repository's first commit: a register with its header and no
#: rows, and the handoffs directory a row's handoff path points into.
WORKSPACE_SEED = {
    "lanes/LANES.md": "\n".join((
        "# LANES.md -- the sandbox register", "",
        "| lane | session id | workstation / env / user | started (UTC) | "
        "objects owned | handoff path | state |",
        "|---|---|---|---|---|---|---|", "")),
    "handoffs/README.md": "# handoffs\n",
}

FAKE_GH = """#!/usr/bin/env bash
printf 'FAKE gh REFUSED: %s -- this suite reaches no GitHub surface\\n' "$*" >&2
exit 90
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


class Sandbox:
    """One workstation, one register, and a `$HOME` at least `run.sh`'s length."""

    def __init__(self, tmp_path: Path) -> None:
        pad = max(0, RUN_SH_HOME - len(str(tmp_path / "r" / "home")))
        self.root = tmp_path / ("r" * (pad + 1))
        self.home = self.root / "home"
        assert len(str(self.home)) >= RUN_SH_HOME
        self.bin = self.root / "bin"
        fakebin = self.root / "fakebin"
        origin = self.root / "origin.git"
        self.wip = self.home / "projects" / "wip"
        for d in (self.home / "projects", self.root / "tmp", fakebin, self.bin,
                  self.home / ".claude" / "sessions", self.home / ".agents"):
            d.mkdir(parents=True, exist_ok=True)

        env = {k: v for k, v in os.environ.items()
               if k not in SCRUBBED and not k.startswith(SCRUBBED_PREFIXES)}
        env.update({
            "HOME": str(self.home),
            "TMPDIR": str(self.root / "tmp"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "PATH": f"{fakebin}{os.pathsep}{self.bin}{os.pathsep}{env.get('PATH', '')}",
            "TMUX": f"{self.root}/fake-tmux-socket,0,0",
            "AGENT_PROTOCOL_ROOT": str(self.home / ".agents"),
            "OPENREPOTOOLS_BIN_DIR": str(self.bin),
            "CLAUDE_CONFIG_DIR": str(self.home / ".claude"),
            "LANES_WORKSTATION": "Eagle",
            "LANES_NO_GITHUB": "1",
            "LANES_INDEX": "off",
            "FAKE_TMUX_LOG": str(self.root / "tmux.log"),
            "GIT_AUTHOR_NAME": "lane-start row stamp tests",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "lane-start row stamp tests",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        self.env = env

        for name in ("lane-start", "lanes-edit.sh", "repos.tsv"):
            shutil.copy2(REPO / name, self.bin / name)
            (self.bin / name).chmod(0o755)
        _write(fakebin / "tmux", FAKE_TMUX)
        _write(fakebin / "gh", FAKE_GH)
        _write(fakebin / "claude", "#!/usr/bin/env bash\nexit 0\n")

        self.git("init", "-q", "--bare", "-b", "main", str(origin))
        self.git("clone", "-q", str(origin), str(self.wip))
        for rel, text in WORKSPACE_SEED.items():
            (self.wip / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.wip / rel).write_text(text, encoding="utf-8")
        for step in (("add", "--", *WORKSPACE_SEED), ("commit", "-q", "-m", "seed"),
                     ("push", "-q", "origin", "main")):
            self.git("-C", str(self.wip), *step)
        # AMENDMENT 23 S5: W, the readers' copy that workspace.yaml names, takes
        # no write. These cases write through `self.wip` by the explicit seam
        # (ort186 Q9) — `LANES_REPO`, and `LANES_FILE`, which lane-start derives
        # from W whenever it is empty — and W is a reader clone outside $HOME.
        self.ws = self.root / "ro" / "wip"
        self.git("clone", "-q", str(origin), str(self.ws))
        for key, value in (("gc.auto", "0"), ("maintenance.auto", "false")):
            self.git("-C", str(self.ws), "config", key, value)
        (self.home / ".agents" / "workspace.yaml").write_text(
            f"repository: {origin}\npath: {self.ws}\n", encoding="utf-8")
        self.env["LANES_REPO"] = str(self.wip)
        self.env["LANES_FILE"] = str(self.wip / "lanes" / "LANES.md")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], env=self.env, check=True,
                              capture_output=True, text=True).stdout

    def checkout(self, path: Path) -> None:
        self.git("init", "-q", "-b", "main", str(path))
        self.git("-C", str(path), "remote", "add", "origin",
                 "https://github.com/opensoft/repoZ.git")

    def start(self, *args: str, window_name: str, timeout: int = 120) -> subprocess.CompletedProcess:
        return subprocess.run([str(self.bin / "lane-start"), "repoZ", "1",
                               "--no-launch", *args],
                              env=dict(self.env, FAKE_TMUX_WINDOW_NAME=window_name),
                              capture_output=True, text=True, timeout=timeout,
                              check=False)

    def stamp_line(self) -> str:
        """The `<one line>` of the row's `<STATE> · <UTC> · <one line>` cell."""
        rows = [r for r in (self.wip / "lanes" / "LANES.md")
                .read_text(encoding="utf-8").splitlines()
                if r.startswith(f"| `{LANE}`")]
        assert len(rows) == 1, rows
        cell = rows[0].rstrip().rstrip("|").rstrip().rsplit(" | ", 1)[1]
        state, _utc, line = cell.split(" · ", 2)
        assert state == "LIVE", cell
        return line

    def last_log_line(self) -> str:
        return (self.wip / "lanes" / "log" / f"{LANE}.md").read_text(
            encoding="utf-8").splitlines()[-1]


@pytest.fixture
def short_root():
    """A short, FIXED-length directory outside the run root: `/tmp/` and
    `mkdtemp`'s name, whatever `TMPDIR` or pytest's basetemp say."""
    root = Path(tempfile.mkdtemp(prefix="ort-tail.", dir="/tmp"))
    try:
        yield root
    finally:
        rmtree(root)


def _checkout_of_length(root: Path, length: int | None) -> Path:
    """`<root>/repoZ`, padded between the two to exactly `length` characters."""
    if length is None:
        return root / "repoZ"
    pad = length - len(str(root)) - len("/repoZ") - 1
    assert pad > 0, (root, length)
    path = root / ("p" * pad) / "repoZ"
    assert len(str(path)) == length
    return path


@pytest.mark.parametrize("length, keeps", [
    pytest.param(None, "dir and window", id="short-fixed-checkout"),
    pytest.param(100, "dir", id="window-cut-dir-kept"),
    pytest.param(160, "nothing", id="path-dropped-whole-as-in-180"),
])
def test_the_stamp_tail_is_cut_by_the_checkout_path_and_never_the_head(
        tmp_path, short_root, length, keeps):
    box = Sandbox(tmp_path)
    lane_dir = _checkout_of_length(short_root, length)
    box.checkout(lane_dir)

    first = box.start("--dir", str(lane_dir), window_name="claude")
    assert first.returncode == 0, first.stderr
    # THE SECOND START STAMPS (Amendment 6(c)), and it finds the checkout in
    # the lane's own log, exactly as the shell suite's case does.
    second = box.start(window_name=LANE)
    assert second.returncode == 0, second.stderr
    line = box.stamp_line()

    assert len(line) <= 240, line
    assert (f"(lane {LANE}) — lane-start on Eagle: window renamed, "
            f"no launch; dir ") in line, line
    if keeps == "dir and window":
        assert line.endswith(f"; dir {lane_dir}; window {WINDOW}"), line
    elif keeps == "dir":
        assert f"; dir {lane_dir};" in line and line.endswith(" ..."), line
        assert WINDOW not in line, line
    else:
        assert line.endswith("no launch; dir ..."), line
        assert str(short_root) not in line, line

    # NOTHING IS LOST: what the cut took is this act's own log line.
    assert f"; dir {lane_dir}; window {WINDOW}; " in box.last_log_line()
