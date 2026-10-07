# SPDX-License-Identifier: Apache-2.0
"""`lane-worktrees sweep --all --dry-run --report` and the start that runs it
once a day (opensoft/openRepoTools#162, the "nightly report" fold).

The report is the net under every actor that never runs `lane-end`. Held here:

  * every section the issue names finds what it is for, in an estate built
    under `tmp_path`: a FOREIGN clone (inside a worktree container, and a
    second clone of one origin), an orphaned tree of an ENDED lane, unmerged
    branches with a missing or diverged upstream, root-`main` divergence that
    is handoff and register paths only, a rescue branch and a dirty inventory
    tree past the aging threshold, caches and a killed suite's sandbox,
    ignored directories over the threshold, evidence-shaped paths, archives
    past retention, the workspace's `.gitignore` and its bytecode history,
    and `status --all`'s findings;
  * it changes nothing - the estate is snapshotted around it;
  * `--post <file>` writes it, `--post owner/repo#n` comments it through `gh`;
  * `lane-start` runs it detached, once a day per workstation, and a report
    that is slow, failing or switched off neither delays nor fails a start.

The `lane-start` cases reuse `tests/test_lane_start_claude_current.py`'s
sandbox: a real `lane-start` against a register in `tmp_path`.
"""

from __future__ import annotations

import datetime as _dt
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import REPO, WINDOWS_SKIP
import test_lane_worktrees as LW
import test_lane_start_claude_current as LS

pytestmark = [WINDOWS_SKIP, pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("bash") is None,
    reason="the report reads git, and lane-start is bash")]

FAKE_STATUS = """#!/bin/sh
cat <<'OUT'
status --all: reading every estate:

=== status repoA ===
  root   main   /x/repoA
    - shape pin 71cf5de is 1 commit(s) behind opensoft/openRepoShape main
OUT
printf '    - estate read at %s\n' "${PROJECTS_DIR:-unset}"
exit 1
"""


def _commit_files(e, cwd, message, when, files):
    """A commit whose author and committer dates are `when`."""
    for rel, text in files.items():
        path = Path(cwd) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    e.git("add", "-A", cwd=cwd)
    e.git("commit", "-q", "-m", message, cwd=cwd,
          env={"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})
    return e.git("rev-parse", "HEAD", cwd=cwd)


def build_estate(e) -> dict:
    """An estate with one finding of every kind the report lists."""
    f = {}
    # FOREIGN: a clone inside the lane's worktree root, and a second clone of
    # repoA's origin beside the repositories.
    f["clone"] = e.lane_root / "cloned"
    e.git("clone", "-q", LW.GH_URL, f["clone"], cwd=e.root)
    f["dup"] = e.projects / "repoA-copy"
    e.git("clone", "-q", LW.GH_URL, f["dup"], cwd=e.root)
    # ... and two clones of one origin NEITHER of which is named for it: one
    # is still the checkout, the other still a finding.
    c_origin = e.root / "remotes" / "repoC.git"
    e.git("init", "-q", "--bare", "-b", "main", c_origin, cwd=e.root)
    for name in ("c-one", "c-two"):
        e.git("clone", "-q", c_origin, e.projects / name, cwd=e.root)
    f["c-two"] = e.projects / "c-two"
    # ORPHANED: a tree in the inventory of a lane whose snapshot is CLOSED.
    f["orphan"] = e.projects / ".lane-worktrees" / "repoA-9" / "left"
    e.git("worktree", "add", "-q", "-b", "feat/left", f["orphan"], "origin/main")
    closed = e.projects / ".lane-state" / "repoA-9"
    (closed / "trees").mkdir(parents=True)
    (closed / "lane-state.yaml").write_text("schema: 1\nstate: CLOSED\n")
    (closed / "trees" / "c1.yaml").write_text(f"schema: 1\npath: {f['orphan']}\n")
    # ... and one of a lane whose checkout is NESTED: #97 keeps its control
    # root, and lane-start its worktree root, beside the checkout's own
    # parent, `projects/group/`, never at the estate's top.
    nested_origin = e.root / "remotes" / "repoB.git"
    e.git("init", "-q", "--bare", "-b", "main", nested_origin, cwd=e.root)
    e.git("clone", "-q", nested_origin, e.projects / "group" / "repoB", cwd=e.root)
    group_closed = e.projects / "group" / ".lane-state" / "repoB-2"
    group_closed.mkdir(parents=True)
    (group_closed / "lane-state.yaml").write_text("schema: 1\nstate: CLOSED\n")
    f["nested-orphan"] = e.projects / "group" / ".lane-worktrees" / "repoB-2" / "leftover"
    f["nested-orphan"].mkdir(parents=True)
    # UNMERGED: no upstream at all, and an upstream that diverged.
    e.git("branch", "--no-track", "feat/nowhere", "origin/main")
    e.git("checkout", "-q", "-b", "feat/diverged", "origin/main")
    e.commit(e.checkout, "d1", {"d.txt": "1\n"})
    e.git("push", "-q", "-u", "origin", "feat/diverged")
    e.git("reset", "-q", "--hard", "HEAD~1")
    e.commit(e.checkout, "d2", {"d.txt": "2\n"})
    e.git("checkout", "-q", "main")
    # ROOT MAIN DIVERGENCE: local main ahead by a handoff only.
    e.commit(e.checkout, "handoff(repoA-1@Eagle): x", {"handoffs/repoA/h.md": "h\n"})
    # AGING: a rescue branch 30 days old, and a dirty inventory tree of a live
    # lane whose git directory has been still for 30 days.
    e.git("checkout", "-q", "-b", "rescue/repoA-1/old-20260101T000000Z", "origin/main")
    _commit_files(e, e.checkout, "old rescue", (_dt.datetime.now(_dt.timezone.utc)
                  - _dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"), {"r.txt": "r\n"})
    e.git("checkout", "-q", "main")
    f["stale-dirty"] = e.lane_root / "stale"
    e.git("worktree", "add", "-q", "-b", "feat/stale", f["stale-dirty"], "origin/main")
    (f["stale-dirty"] / "wip.txt").write_text("unsaved\n")
    live = e.projects / ".lane-state" / LW.LANE / "trees"
    live.mkdir(parents=True)
    (live / "s.yaml").write_text(f"schema: 1\npath: {f['stale-dirty']}\n")
    old = time.time() - 30 * 86400
    gitdir = Path(e.git("rev-parse", "--absolute-git-dir", cwd=f["stale-dirty"]))
    for name in ("index", "HEAD", "logs/HEAD"):
        if (gitdir / name).exists():
            os.utime(gitdir / name, (old, old))
    # CACHES and a killed suite's SANDBOX.
    (e.lane_root / "x-scratch" / "__pycache__").mkdir(parents=True)
    (e.lane_root / "x-scratch" / "__pycache__" / "a.pyc").write_bytes(b"\0" * 2048)
    f["sandbox"] = e.sandboxes / "tmp.killedrun1"
    f["sandbox"].mkdir()
    (f["sandbox"] / "f").write_text("x")
    os.utime(f["sandbox"] / "f", (old, old))
    os.utime(f["sandbox"], (old, old))
    # IGNORED over the threshold (0 MB in this estate's sweep.conf), and
    # EVIDENCE: an untracked JUnit file, and a directory of reports.
    (e.checkout / "build").mkdir()
    (e.checkout / "build" / "out.bin").write_bytes(b"\0" * 4096)
    (e.checkout / ".gitignore").write_text((e.checkout / ".gitignore").read_text() + "build/\n")
    (e.checkout / "junit-results.xml").write_text("<testsuite/>\n")
    f["reports"] = e.projects / "cleanup-20261005"
    f["reports"].mkdir()
    (f["reports"] / "FINAL-REPORT.md").write_text("# report\n")
    # PAST RETENTION: an archive 120 days old that would expire, and one 150
    # days old kept because the rescue branch it records left origin.
    f["archive"] = LW._archive(e, 120, None)
    f["kept"] = LW._archive(e, 150, "rescue/repoA-1/gone-1")
    # THE WORKSPACE: a .gitignore without the bytecode lines, and a .pyc in
    # its history.
    wip_origin = e.root / "wip.git"
    wip = e.projects / "wip"
    e.git("init", "-q", "--bare", "-b", "main", wip_origin, cwd=e.root)
    e.git("clone", "-q", wip_origin, wip, cwd=e.root)
    (wip / "lanes" / "log").mkdir(parents=True)
    (wip / "lanes" / "LANES.md").write_text("# register\n")
    (wip / "lanes" / "log" / "repoA-9.md").write_text(
        f"STARTED — lane repoA-9, session {LW.ME}@Eagle, 2026-09-01T00:00:00Z, lane:repoA-9\n"
        f"ENDED — lane repoA-9, session {LW.ME}@Eagle, 2026-09-02T00:00:00Z, lane:repoA-9\n")
    (wip / ".gitignore").write_text("*.swp\n")
    (wip / "handoffs" / "a" / "__pycache__").mkdir(parents=True)
    (wip / "handoffs" / "a" / "__pycache__" / "m.cpython-312.pyc").write_bytes(b"\0")
    e.git("add", "-A", cwd=wip)
    e.git("commit", "-q", "-m", "seed", cwd=wip)
    e.git("push", "-q", "origin", "main", cwd=wip)
    e.workspace = str(wip)
    f["wip"] = wip
    (e.fakebin / "status").write_text(FAKE_STATUS)
    (e.fakebin / "status").chmod(0o755)
    e.env["LANE_WORKTREES_STATUS"] = str(e.fakebin / "status")
    conf = e.root / "sweep.conf"
    conf.write_text("ignored_report_mb=0\n")
    e.env["LANE_WORKTREES_CONF"] = str(conf)
    return f


def report(e, *args, env=None, estate=True):
    e.write_spec()
    child = dict(e.env)
    child.update(env or {})
    where = ["--estate", str(e.projects)] if estate else []
    return subprocess.run([sys.executable, str(LW.LW), "sweep", "--all", "--dry-run", "--report",
                           *where, *args],
                          capture_output=True, text=True, env=child, timeout=300,
                          cwd=str(e.root), stdin=subprocess.DEVNULL)


def section(text: str, title: str) -> str:
    start = text.index(f"## {title}")
    end = text.find("\n## ", start + 3)
    return text[start:end if end != -1 else len(text)]


def test_the_report_finds_every_kind_of_leftover_and_changes_nothing(tmp_path):
    e = LW.Estate(tmp_path)
    f = build_estate(e)
    before = LW.snapshot(e.root, skip=("helper.log", "helper-spec.json", "prs.json"))
    proc = report(e)
    after = LW.snapshot(e.root, skip=("helper.log", "helper-spec.json", "prs.json"))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout
    assert out.startswith("# Estate report")
    foreign = section(out, "FOREIGN repositories")
    assert str(f["clone"]) in foreign and "a CLONE inside" in foreign
    assert str(f["dup"]) in foreign and "a second clone of" in foreign
    assert f"{e.checkout} ·" not in foreign, "the estate's own checkout is not foreign"
    assert f"{f['c-two']} · a second clone of {e.projects / 'c-one'}'s origin (no single" \
        in foreign
    assert f"{e.projects / 'c-one'} ·" not in foreign
    orphans = section(out, "Orphaned worktrees of ENDED lanes")
    assert str(f["orphan"]) in orphans and "repoA-9" in orphans
    assert f"{f['nested-orphan']} \u00b7 repoB-2 \u00b7 its snapshot is CLOSED" in orphans
    branches = section(out, "Unmerged branches")
    assert "feat/nowhere" in branches and "no upstream" in branches
    assert "feat/diverged" in branches and "diverged from origin/feat/diverged" in branches
    assert "rescue/repoA-1/old" not in branches
    root_main = section(out, "Root main divergence")
    assert "ahead of origin by 1" in root_main and "only handoff/register paths" in root_main
    aging = section(out, "Awaiting disposition")
    assert "rescue/repoA-1/old-20260101T000000Z \u00b7 rescue branch, 30 d \u00b7 repoA-1" in aging
    assert str(f["stale-dirty"]) in aging and "dirty inventory tree" in aging
    caches = section(out, "Caches and sandboxes")
    assert "x-scratch/__pycache__" in caches and str(f["sandbox"]) in caches
    ignored = section(out, "Ignored directories over")
    assert str(e.checkout / "build") in ignored
    evidence = section(out, "Evidence-shaped paths")
    assert "junit-results.xml" in evidence and str(f["reports"]) in evidence
    archives = section(out, "Sweep archives past retention")
    assert f"{f['archive']} \u00b7 120 d \u00b7 would expire" in archives
    assert f"{f['kept']} \u00b7 150 d \u00b7 kept past retention" in archives
    assert "gone from origin" in archives
    hygiene = section(out, "Workspace repository hygiene")
    assert "lacks __pycache__/" in hygiene and "bytecode path(s) in history" in hygiene
    status = section(out, "`status --all` findings")
    assert "shape pin 71cf5de is 1 commit(s) behind" in status
    assert f"estate read at {e.projects}" in status
    assert "| rescue branches (all ages) | 1 |" in out
    assert before == after, sorted(set(before.items()) ^ set(after.items()))[:10]


def test_status_reads_the_estate_the_report_resolved(tmp_path):
    """Copilot on #169: with no `--estate` - lane-start's daily run - the
    report resolves `$PROJECTS_ROOT`, and `status --all` is pointed at that
    same estate, never at its own default."""
    e = LW.Estate(tmp_path)
    build_estate(e)
    proc = report(e, estate=False)
    assert proc.returncode == 0, proc.stderr
    assert f"over `{e.projects}`" in proc.stdout
    assert f"estate read at {e.projects}" in section(proc.stdout, "`status --all` findings")


def test_a_record_the_report_cannot_read_is_a_finding_never_absence(tmp_path):
    """Copilot round 2 on #169: an inventory or snapshot the report could not
    read would otherwise make it clean."""
    e = LW.Estate(tmp_path)
    build_estate(e)
    trees = e.projects / ".lane-state" / "repoA-5" / "trees"
    trees.mkdir(parents=True)
    (trees / "c1.yaml").write_text("schema: 1\n")
    locked = e.projects / ".lane-state" / "repoA-6"
    locked.mkdir()
    (locked / "lane-state.yaml").write_text("schema: 1\nstate: CLOSED\n")
    (locked / "lane-state.yaml").chmod(0)
    try:
        proc = report(e)
    finally:
        (locked / "lane-state.yaml").chmod(0o644)
    assert proc.returncode == 0, proc.stderr
    found = section(proc.stdout, "Records the report could not read")
    assert f"{trees / 'c1.yaml'} \u00b7 an inventory record that names no path" in found
    if os.geteuid() != 0:
        assert f"{locked / 'lane-state.yaml'} \u00b7 could not be read" in found
    assert "| Records the report could not read | " in proc.stdout


def test_post_writes_a_file_or_comments_on_an_issue(tmp_path):
    e = LW.Estate(tmp_path)
    build_estate(e)
    target = e.state / "openRepoTools" / "reports" / "today.md"
    proc = report(e, "--post", str(target))
    assert proc.returncode == 0, proc.stderr
    assert target.read_text().startswith("# Estate report")
    log = e.root / "gh.log"
    (e.fakebin / "gh").write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FAKE_GH_LOG\"\n"
        "[ \"$1 $2\" = 'issue comment' ] && { cat \"$7\" >> \"$FAKE_GH_LOG\"; "
        "echo https://github.com/opensoft/repoA/issues/9#c1; exit 0; }\nexit 1\n")
    proc = report(e, "--post", "opensoft/repoA#9", env={"FAKE_GH_LOG": str(log)})
    assert proc.returncode == 0, proc.stderr
    text = log.read_text()
    assert "issue comment 9 --repo opensoft/repoA --body-file" in text
    assert "# Estate report" in text


def test_the_report_is_only_a_report(tmp_path):
    e = LW.Estate(tmp_path)
    for argv in (["--all", "--report", "--yes"], ["--all"], ["--report"],
                 [LW.LANE, "--all", "--report"]):
        e.write_spec()
        proc = subprocess.run([sys.executable, str(LW.LW), "sweep", *argv], capture_output=True,
                              text=True, env=e.env, timeout=60)
        assert proc.returncode == 64, (argv, proc.stdout, proc.stderr)


# ================================================== lane-start runs it daily

FAKE_REPORTER = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_REPORT_LOG"
if [ -n "${FAKE_REPORT_SLEEP:-}" ]; then
  sleep "$FAKE_REPORT_SLEEP" &
  echo "$!" > "$FAKE_REPORT_LOG.sleeper"
  wait
  echo finished >> "$FAKE_REPORT_LOG"
fi
exit "${FAKE_REPORT_RC:-0}"
"""


def _reporter(box, state: Path) -> Path:
    log = box.root / "report.log"
    LS._write(box.bin / "lane-worktrees", FAKE_REPORTER)
    box.env.update(LANE_WORKTREES_REPORT="on", XDG_STATE_HOME=str(state),
                   FAKE_REPORT_LOG=str(log))
    return log


def _no_report_state(state: Path) -> bool:
    """No stamp and no reports directory: the report's own state only - the
    start writes other state of its own there (#164's index nudge)."""
    base = state / "openRepoTools"
    return not list(base.glob("report-*.stamp")) and not (base / "reports").exists()


def _wait_for(path: Path, timeout: float = 15) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and path.read_text():
            return path.read_text()
        time.sleep(0.1)
    return ""


def test_lane_start_runs_the_report_detached_once_a_day(tmp_path):
    box = LS.Sandbox(tmp_path)
    state = tmp_path / "state"
    log = _reporter(box, state)
    try:
        result = box.start("--no-launch", FAKE_REPORT_SLEEP="90")
        assert result.returncode == 0, result.stderr
        calls = _wait_for(log)
        # The report sleeps 90 s and then writes `finished`: a start that
        # waited on it would have returned after that line.
        assert "finished" not in calls, "the start waited on the report"
    finally:
        sleeper = Path(str(log) + ".sleeper")
        if _wait_for(sleeper, 5).strip().isdigit():
            try:
                os.kill(int(sleeper.read_text()), 15)
            except OSError:
                pass
    assert calls.startswith("sweep --all --dry-run --report --post "), calls
    assert f"{state}/openRepoTools/reports/" in calls
    assert calls.rstrip().endswith(f"--estate {box.home / 'projects'}"), calls
    day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
    assert (state / "openRepoTools" / f"report-{day}.stamp").exists()
    assert "the estate's daily report is running, detached" in result.stderr


def test_a_stamp_from_today_runs_no_second_report_and_yesterdays_is_replaced(tmp_path):
    box = LS.Sandbox(tmp_path)
    state = tmp_path / "state"
    log = _reporter(box, state)
    day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
    (state / "openRepoTools").mkdir(parents=True)
    (state / "openRepoTools" / f"report-{day}.stamp").write_text("")
    result = box.start("--no-launch")
    assert result.returncode == 0, result.stderr
    time.sleep(1)
    assert not log.exists() or log.read_text() == "", "a second report ran today"
    (state / "openRepoTools" / f"report-{day}.stamp").unlink()
    (state / "openRepoTools" / "report-20200101.stamp").write_text("")
    box2 = LS.Sandbox(tmp_path / "second")
    log2 = _reporter(box2, state)
    assert box2.start("--no-launch").returncode == 0
    assert _wait_for(log2)
    assert not (state / "openRepoTools" / "report-20200101.stamp").exists()


def test_a_failing_or_switched_off_report_never_fails_a_start(tmp_path):
    box = LS.Sandbox(tmp_path)
    state = tmp_path / "state"
    log = _reporter(box, state)
    result = box.start("--no-launch", FAKE_REPORT_RC="1")
    assert result.returncode == 0, result.stderr
    assert _wait_for(log), "the failing reporter was never run"
    off = LS.Sandbox(tmp_path / "off")
    off_log = _reporter(off, tmp_path / "off-state")
    result = off.start("--no-launch", LANE_WORKTREES_REPORT="off")
    assert result.returncode == 0, result.stderr
    time.sleep(1)
    assert not off_log.exists()
    assert _no_report_state(tmp_path / "off-state")


def test_a_dry_run_start_runs_no_report(tmp_path):
    box = LS.Sandbox(tmp_path)
    state = tmp_path / "state"
    log = _reporter(box, state)
    result = box.start("--dry-run")
    assert result.returncode == 0, result.stderr
    time.sleep(1)
    assert not log.exists()
    assert _no_report_state(state)
