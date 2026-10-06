# SPDX-License-Identifier: Apache-2.0
"""THE WRITE `--install` PLACES EVERY FILE WITH, ON EVERY PLATFORM CI HAS (#167).

`openRepoTools --install` writes each file it places to a temporary beside the
target and renames it over the target, so a lane tool that is RUNNING from that
path when an install replaces it finishes on the text it started with. The
installer's own tests (`tests/test_openrepotools_command.py`) prove that end to
end, but they carry `WINDOWS_SKIP` — the whole installer needs `jq`, `make` and
shebang execution, and on Windows the way in is WSL2 — so they say nothing
about Git Bash. Git Bash is exactly where the rename's semantics differ most:
renaming over a file another process has open is the one step of this write
that Windows can refuse.

So this module runs the installer's OWN `place_by_rename` — its text, cut out
of the script, never a copy written here — under each platform's bash: `bash`
on PATH on Linux and macOS, and on Windows the Git Bash that ships with the
`git` running this suite (skipped where there is none). The function needs
only `die`, `$PLACING`, the `owner_of` beside it and coreutils, which is why
the two can be run on their own.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess

from pathlib import Path

import pytest

from conftest import REPO

COMMAND = REPO / "openRepoTools"


def platform_bash() -> str | None:
    """`bash` on PATH where the OS is POSIX, and GIT BASH on Windows.

    On Windows `shutil.which("bash")` can answer WSL's launcher in System32,
    which is not the shell this is about, so Git Bash is found through the
    `git` that runs this suite: `<git>/bin/bash.exe`, reached from either
    `git --exec-path` (`<git>/mingw64/libexec/git-core`) or `git.exe` itself
    (`<git>/cmd/git.exe`).
    """
    if os.name != "nt":
        return shutil.which("bash")
    git = shutil.which("git")
    if git is None:
        return None
    roots = [Path(git).resolve().parents[1]]
    exec_path = subprocess.run([git, "--exec-path"], capture_output=True,
                               text=True, check=False).stdout.strip()
    if exec_path:
        roots.insert(0, Path(exec_path).parents[2])
    for root in roots:
        candidate = root / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    return None


BASH = platform_bash()

pytestmark = pytest.mark.skipif(
    BASH is None, reason="no bash here (on Windows: no Git Bash beside git)")

#: The same running text as the installer's end-to-end test: it announces
#: itself, then waits — `sleep` forks, which is what makes bash seek back and
#: read on from its file — until `$GO` exists, and finishes. Bounded.
OLD_RUNNING = ("#!/usr/bin/env bash\n"
               "printf 'old: started\\n'\n"
               'i=0; until [ -e "$GO" ] || [ "$i" -ge 1200 ]; do '
               'sleep 0.05; i=$((i + 1)); done\n')
OLD_TAIL = "printf 'old: finished\\n'\nexit 0\n"


def posix(path: Path) -> str:
    """A path every bash here reads: Git Bash takes `C:/…` with forward
    slashes, and a backslash would be an escape to it."""
    return path.as_posix()


def installer_function(name: str) -> str:
    """One function as the installer carries it, cut out of the script."""
    text = COMMAND.read_text(encoding="utf-8")
    match = re.search(rf"^{re.escape(name)}\(\) \{{[^\n]*\n.*?^\}}\n", text,
                      re.MULTILINE | re.DOTALL)
    assert match, f"`{name}() {{` … `}}` is no longer in openRepoTools"
    return match.group(0)


def place(tmp_path: Path, source: Path, target: Path,
          mode: str = "755") -> subprocess.CompletedProcess:
    """One placement, through the installer's function, under this bash."""
    harness = tmp_path / "harness.sh"
    harness.write_bytes((
        "set -euo pipefail\n"
        'PLACING=""\n'
        "die() { printf 'REFUSED: %s\\n' \"$1\" >&2; exit 2; }\n"
        + installer_function("owner_of")
        + installer_function("place_by_rename")
        + 'place_by_rename "$1" "$2" "$3" "nothing else was placed."\n'
    ).encode("utf-8"))
    return subprocess.run([BASH, posix(harness), posix(source), posix(target),
                           mode], capture_output=True, text=True, check=False)


def temporaries(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir()
                  if ".openrepotools." in p.name)


def test_a_running_script_finishes_on_its_own_text_when_it_is_placed_over(
        tmp_path):
    """THE DEFECT #167 IS ABOUT, ON THIS PLATFORM'S BASH.

    A script is running from the target when the placement replaces it. The
    running process must finish on its own text, and the path must hold the
    new bytes afterwards. On Windows this is the question whether Git Bash's
    `mv -f` may replace a file a running bash has open; a rewrite in place
    would make the process read the new text from its old offset instead.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    target = bin_dir / "lanes-edit.sh"
    target.write_bytes((OLD_RUNNING + OLD_TAIL).encode("utf-8"))
    # A line of the NEW text starts at exactly the byte the old one resumes
    # reading at, so a rewrite in place reads it, says so, and exits 7.
    head = "#!/usr/bin/env bash\n# "
    new = (head + "x" * (len(OLD_RUNNING) - len(head) - 1) + "\n"
           + "printf 'new: read from the old offset\\n'; exit 7\n"
           ).encode("utf-8")
    source = tmp_path / "staged"
    source.write_bytes(new)

    go = tmp_path / "go"
    running = subprocess.Popen([BASH, posix(target)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               env={**os.environ, "GO": posix(go)})
    try:
        assert running.stdout.readline() == "old: started\n"
        placed = place(tmp_path, source, target)
        assert placed.returncode == 0, placed.stdout + placed.stderr
        go.touch()
        out, err = running.communicate(timeout=120)
    finally:
        if running.poll() is None:
            running.kill()
            running.communicate()
    assert (out, err, running.returncode) == ("old: finished\n", "", 0), (
        f"the running copy did not finish on its own text:\nstdout {out!r}\n"
        f"stderr {err!r}\nexit {running.returncode}")
    assert target.read_bytes() == new
    if os.name != "nt":
        assert target.stat().st_mode & 0o777 == 0o755
    assert temporaries(bin_dir) == []


def test_a_directory_at_the_target_is_refused_and_leaves_no_temporary(
        tmp_path):
    """`mv` MOVES A FILE INTO A DIRECTORY NAMED AS ITS DESTINATION rather than
    failing, so the function refuses one itself — the planners catch it a
    phase earlier, and this is the step that must not depend on that. The
    directory keeps exactly what it had, and the temporary is removed."""
    bin_dir = tmp_path / "bin"
    target = bin_dir / "park"
    target.mkdir(parents=True)
    (target / "kept").write_bytes(b"kept\n")
    source = tmp_path / "staged"
    source.write_bytes(b"#!/usr/bin/env bash\n")

    placed = place(tmp_path, source, target)
    assert placed.returncode == 2, placed.stdout + placed.stderr
    assert "REFUSED:" in placed.stderr and "is a directory" in placed.stderr, (
        placed.stderr)
    assert sorted(p.name for p in target.iterdir()) == ["kept"]
    assert temporaries(bin_dir) == []
