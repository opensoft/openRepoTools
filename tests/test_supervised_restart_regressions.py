# SPDX-License-Identifier: Apache-2.0
"""Restart fault cases through the real helper and lane-start entrypoints."""
from __future__ import annotations

import hashlib
import json
import shutil
import signal
import time
import os
import subprocess
from pathlib import Path

import pytest

from test_lane_start_claude_current import Sandbox, LANE, _write, pytestmark
from conftest import REPO


@pytest.fixture
def restart_box(tmp_path: Path) -> Sandbox:
    box = Sandbox(tmp_path)
    box.env["LANES_LANE_STATE_ROOT"] = str(tmp_path / "state")
    box.env["LANES_NO_FETCH"] = "1"
    box.env["TMUX_PANE"] = "%1"
    tmux = box.fakebin / "tmux"
    tmux.write_text(tmux.read_text().replace("#!/usr/bin/env bash\n", '''#!/usr/bin/env bash
if [ "${1-}" = respawn-pane ]; then
  printf 'respawn-pane %s\\n' "$*" >> "$FAKE_TMUX_LOG"
  exit 0
fi
''', 1))
    return box


def helper(box, *args):
    return subprocess.run([str(box.bin / "lanes-edit.sh"), *args],
                          cwd=box.lane_dir, env=box.env, text=True,
                          capture_output=True, timeout=30, check=False)


def intent_path(box):
    return Path(box.env["LANES_LANE_STATE_ROOT"]) / LANE / "restart-intent.yaml"


def write_intent(box, text):
    path = intent_path(box)
    _write(path, text, 0o600)
    return path


@pytest.mark.parametrize("state", ["", "unknown", "STARTING"])
def test_restart_unknown_state_is_diagnostic_not_launch_authority(restart_box, state):
    box = restart_box
    write_intent(box, f"schema: 1\nstate: {state}\n")
    result = helper(box, "restart-intent", LANE)
    assert result.returncode == 0, result.stderr
    assert "state\tUNKNOWN-STATE" in result.stdout
    box.resolver()
    result = box.start()
    assert result.returncode == 2, result.stderr
    assert box.claude_runs() == ""


@pytest.mark.parametrize("schema", ["", "2"])
def test_restart_writer_preserves_records_with_missing_or_unknown_schema(restart_box, schema):
    box = restart_box
    contents = f"schema: {schema}\nstate: pending\noperation: prior\n"
    path = write_intent(box, contents)
    result = helper(box, "set-restart-intent", LANE, "pending", "--expect", "none|ready|failed")
    assert result.returncode == 2, result.stderr
    assert path.read_text() == contents


def test_restart_nonregular_intent_refuses_read_and_replacement(restart_box):
    box = restart_box
    path = intent_path(box)
    path.mkdir(parents=True)
    for args in [("restart-intent", LANE),
                 ("set-restart-intent", LANE, "pending", "--expect", "none")]:
        result = helper(box, *args)
        assert result.returncode == 1, (result.stdout, result.stderr)
    assert path.is_dir()


def test_restart_failed_record_needs_launch_facts_before_retry(restart_box):
    box = restart_box
    write_intent(box, "schema: 1\nstate: failed\noperation: prior\nmode: fresh-from-handoff\n")
    result = helper(box, "restart-intent", LANE)
    assert result.returncode == 0, result.stderr
    assert "state\tINCOMPLETE" in result.stdout
    assert "intended_state\tfailed" in result.stdout
    missing = next(line.split("\t", 1)[1].split() for line in result.stdout.splitlines() if line.startswith("missing\t"))
    assert {"dir", "pane", "handoff", "digest", "agent", "window", "new_transcript"} <= set(missing)


@pytest.mark.parametrize("write_rc", [7, 1])
def test_restart_failed_prepared_transcript_write_never_executes(restart_box, write_rc):
    box = restart_box
    prepare_restart(box)
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    _write(box.bin / "lanes-edit.sh", f'''#!/usr/bin/env bash
case "$*" in
 *"lane-start prepared the launch"*) exit {write_rc} ;;
esac
exec "$(dirname -- "$0")/lanes-edit-real.sh" "$@"
''')
    result = box.start("--fresh", "--operation", "op-test")
    assert result.returncode == (2 if write_rc == 7 else 1), (result.stdout, result.stderr)
    assert "refused before exec" in result.stderr or "refused before exec" in result.stdout
    assert box.claude_runs() == ""


def test_restart_unreadable_intent_is_neither_absent_nor_replaceable(restart_box):
    if os.geteuid() == 0:
        pytest.skip("permission regression requires an unprivileged runner")
    box = restart_box
    contents = "schema: 1\nstate: pending\noperation: held\n"
    path = write_intent(box, contents)
    path.chmod(0)
    try:
        for args in [("restart-intent", LANE),
                     ("set-restart-intent", LANE, "pending", "--expect", "none|ready|failed")]:
            result = helper(box, *args)
            assert result.returncode == 1, (result.stdout, result.stderr)
    finally:
        path.chmod(0o600)
    assert path.read_text() == contents


@pytest.mark.parametrize("presence", [0, 1, 8])
def test_restart_managed_service_requires_confirmed_absence(restart_box, presence):
    box = restart_box
    calls = box.root / "managed-read.log"
    _write(box.bin / "lane-managed", f'''#!/usr/bin/env bash
printf '%s\\n' "$*" >> '{calls}'
exit {presence}
''')
    result = helper(box, "legacy-restart-check", LANE)
    assert result.returncode == (0 if presence == 8 else 2 if presence == 0 else 1)
    assert calls.read_text().strip() == f"legacy-check --lane {LANE}"


def test_restart_managed_storage_without_reader_refuses(restart_box):
    box = restart_box
    state = box.wip / ".git" / "openrepotools-managed" / "eagle" / LANE.lower()
    state.mkdir(parents=True)
    _write(state / "owner.json", '{"mode":"managed"}\n', 0o600)
    result = helper(box, "legacy-restart-check", LANE)
    assert result.returncode == 2, result.stderr
    assert "managed ownership storage" in result.stderr
    assert (state / "owner.json").read_text() == '{"mode":"managed"}\n'


def prepare_restart(box):
    box.resolver()
    initial = box.start("--no-launch")
    assert initial.returncode == 0, initial.stderr
    row = next(line for line in (box.wip / "lanes" / "LANES.md").read_text().splitlines()
               if line.startswith(f"| `{LANE}`"))
    source = box.wip / row.split("|")[6].strip()
    _write(source, "# restart handoff\n\nPreserved task.\n---\nHistory.\n", 0o600)
    box.git("-C", str(box.wip), "add", "--", str(source))
    box.git("-C", str(box.wip), "commit", "-qm", "seed handoff")
    box.git("-C", str(box.wip), "push", "-q", "origin", "main")
    result = helper(box, "set-restart-intent", LANE, "pending", "--expect", "none",
                    "--operation", "op-test", "--generation", "7", "--agent", "claude",
                    "--profile", "test-profile", "--dir", str(box.lane_dir),
                    "--pane", "testsess:@1.%1", "--handoff", str(source))
    assert result.returncode == 0, result.stderr
    return source


def test_restart_opening_prompt_cannot_switch_to_a_different_register_file(restart_box):
    box = restart_box
    source = prepare_restart(box)
    other = box.wip / "handoffs" / "other.md"
    _write(other, "# Another task\n\nWrong preserved work.\n", 0o600)
    registry = box.wip / "lanes" / "LANES.md"
    registry.write_text(registry.read_text().replace(str(source.relative_to(box.wip)),
                                                     str(other.relative_to(box.wip))))
    box.git("-C", str(box.wip), "add", "--", "lanes/LANES.md", "handoffs/other.md")
    box.git("-C", str(box.wip), "commit", "-qm", "move row handoff")
    box.git("-C", str(box.wip), "push", "-q", "origin", "main")
    result = box.start("--fresh", "--operation", "op-test")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "different handoffs" in result.stderr
    assert box.claude_runs() == ""


def test_restart_owned_resume_stamp_preserves_retry_digest(restart_box):
    box = restart_box
    source = prepare_restart(box)
    result = box.start("--fresh", "--operation", "op-test", TMUX_PANE="%1")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "Preserved task." in box.claude_runs()
    assert "RESUMED by" in source.read_text()
    result = helper(box, "restart-intent", LANE)
    digest = next(line.split("\t", 1)[1] for line in result.stdout.splitlines()
                  if line.startswith("digest\t"))
    assert digest == hashlib.sha256(source.read_bytes()).hexdigest()
    result = helper(box, "set-restart-intent", LANE, "failed", "--expect", "starting",
                    "--expect-operation", "op-test", "--expect-generation", "7")
    assert result.returncode == 0, result.stderr
    # Retrying in the same operation must accept only that owned stamp.
    result = helper(box, "set-restart-intent", LANE, "starting", "--expect", "failed",
                    "--expect-operation", "op-test", "--expect-generation", "7",
                    "--bump-attempt", "--new-transcript", "none")
    assert result.returncode == 0, result.stderr
    second = box.start("--fresh", "--operation", "op-test", TMUX_PANE="%1")
    assert second.returncode == 0, (second.stdout, second.stderr)
    assert source.read_text().count("RESUMED by") == 2


def test_restart_missing_supervisor_token_cannot_consume_pending_intent(restart_box):
    box = restart_box
    prepare_restart(box)
    result = box.start()
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "supervisor operation token" in result.stderr
    assert box.claude_runs() == ""


def test_restart_supervisor_token_cannot_select_a_newer_operation(restart_box):
    box = restart_box
    prepare_restart(box)
    result = box.start(LANE_RESTART_OPERATION="superseded")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "not lane" in result.stderr
    assert box.claude_runs() == ""


def test_restart_managed_lane_refuses_before_handoff_stamp(restart_box):
    box = restart_box
    source = prepare_restart(box)
    before = source.read_bytes()
    _write(box.bin / "lane-managed", "#!/usr/bin/env bash\nexit 0\n")
    result = box.start("--fresh", "--operation", "op-test")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "managed" in result.stderr
    assert source.read_bytes() == before
    assert box.claude_runs() == ""


@pytest.mark.parametrize("field,value", [("generation", "bad"), ("attempt", "-1"), ("state", "BOGUS")])
def test_restart_writer_never_normalizes_malformed_existing_identity(restart_box, field, value):
    box = restart_box
    prepare_restart(box)
    path = intent_path(box)
    lines = path.read_text().splitlines()
    path.write_text("\n".join(f"{field}: {value}" if line.startswith(f"{field}:") else line for line in lines) + "\n")
    before = path.read_bytes()
    result = helper(box, "set-restart-intent", LANE, "starting", "--expect-operation", "op-test")
    assert result.returncode == 2, result.stderr
    assert path.read_bytes() == before


def test_restart_stale_attempt_cannot_write_or_launch(restart_box):
    box = restart_box
    source = prepare_restart(box)
    before = source.read_bytes()
    result = helper(box, "set-restart-intent", LANE, "starting", "--expect-attempt", "1")
    assert result.returncode == 7, result.stderr
    result = box.start("--operation", "op-test", LANE_RESTART_ATTEMPT="1")
    assert result.returncode == 2, result.stderr
    assert source.read_bytes() == before
    assert box.claude_runs() == ""


def test_restart_profile_mismatch_refuses_before_preservation(restart_box):
    box = restart_box
    source = prepare_restart(box)
    before = source.read_bytes()
    result = box.start("--operation", "op-test", CLAUDE_PROFILE_NAME="different")
    assert result.returncode == 2, result.stderr
    assert "profile disagrees" in result.stderr
    assert source.read_bytes() == before
    assert box.claude_runs() == ""


def test_restart_preparing_reservation_is_not_launchable(restart_box):
    box = restart_box
    source = prepare_restart(box)
    result = helper(box, "set-restart-intent", LANE, "preparing", "--expect", "pending")
    assert result.returncode == 0, result.stderr
    before = source.read_bytes()
    result = box.start("--operation", "op-test")
    assert result.returncode == 2, result.stderr
    assert "still preparing" in result.stderr
    assert source.read_bytes() == before


def test_restart_interrupted_stamp_publication_accepts_only_owned_bytes(restart_box):
    box = restart_box
    source = prepare_restart(box)
    original = source.read_bytes()
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    _write(box.bin / "lanes-edit.sh", '''#!/usr/bin/env bash
case "$*" in *"lane-start prepared the launch"*) exit 1 ;; esac
exec "$(dirname -- "$0")/lanes-edit-real.sh" "$@"
''')
    result = box.start("--operation", "op-test")
    assert result.returncode == 1, result.stderr
    assert source.read_bytes() != original
    record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
    assert record["digest"] == hashlib.sha256(original).hexdigest()
    assert record["prepared_digest"] == hashlib.sha256(source.read_bytes()).hexdigest()
    real.replace(box.bin / "lanes-edit.sh")
    assert helper(box, "set-restart-intent", LANE, "failed", "--expect", "starting").returncode == 0
    assert helper(box, "set-restart-intent", LANE, "starting", "--expect", "failed", "--bump-attempt", "--new-transcript", "none").returncode == 0
    result = box.start("--operation", "op-test")
    assert result.returncode == 0, result.stderr
    # The transaction does not whitelist edits made by anyone else.
    assert helper(box, "set-restart-intent", LANE, "failed", "--expect", "starting").returncode == 0
    source.write_text(source.read_text() + "Unrelated changed instructions.\n")
    result = box.start("--operation", "op-test")
    assert result.returncode == 2


def supervisor(box, *args):
    from conftest import REPO
    shutil.copy2(REPO / "lane-handoff", box.bin / "lane-handoff")
    return subprocess.run([str(box.bin / "lane-handoff"), *args], cwd=box.lane_dir,
                          env=box.env, text=True, capture_output=True, timeout=30)


def test_restart_failed_child_retries_in_same_supervisor_operation(restart_box):
    box = restart_box
    prepare_restart(box)
    child = _write(box.fakebin / "pclaude", "#!/usr/bin/env bash\nexit 127\n")
    box.env.update(PCLAUDE=str(child), LANE_SUPERVISOR_NO_PROMPT="1")
    for attempt in (1, 2):
        result = supervisor(box, "--supervise", "--lane", LANE, "--operation", "op-test")
        assert result.returncode == 3, (result.stdout, result.stderr)
        record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
        assert record["state"] == "failed"
        assert record["attempt"] == str(attempt)
        assert record["operation"] == "op-test"
        assert record["new_transcript"] == "none"


def test_restart_signal_with_live_child_does_not_offer_retry(restart_box):
    from conftest import REPO
    box = restart_box
    prepare_restart(box)
    shutil.copy2(REPO / "lane-handoff", box.bin / "lane-handoff")
    pidfile = box.root / "child.pid"
    child = _write(box.fakebin / "pclaude", f'''#!/usr/bin/env bash
printf '%s\n' "$$" > '{pidfile}'
exec sleep 30
''')
    box.env.update(PCLAUDE=str(child), LANE_SUPERVISOR_NO_PROMPT="1")
    with (box.root / "supervisor.out").open("w") as output:
        proc = subprocess.Popen([str(box.bin / "lane-handoff"), "--supervise", "--lane", LANE,
                                 "--operation", "op-test"], cwd=box.lane_dir, env=box.env,
                                stdout=output, stderr=output, start_new_session=True)
        try:
            deadline = time.monotonic() + 15
            while not pidfile.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            assert pidfile.exists(), (box.root / "supervisor.out").read_text()
            proc.send_signal(signal.SIGTERM)
            assert proc.wait(timeout=10) == 143
            record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
            assert record["state"] == "starting"
            assert "INDETERMINATE" in record["reason"]
            retry = supervisor(box, "--supervise", "--lane", LANE, "--operation", "op-test")
            assert retry.returncode == 2
        finally:
            # Only this sandbox's process group is stopped.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            if proc.poll() is None:
                proc.wait(timeout=10)


def test_restart_reserved_transcript_cannot_be_consumed_twice(restart_box):
    box = restart_box
    source = prepare_restart(box)
    first = box.start("--operation", "op-test")
    assert first.returncode == 0, first.stderr
    before = source.read_bytes()
    launched = box.claude_runs()
    second = box.start("--operation", "op-test")
    assert second.returncode == 2, second.stderr
    assert "lost ownership" in second.stderr
    assert source.read_bytes() == before
    assert box.claude_runs() == launched


def test_restart_atomic_stamp_failure_preserves_original_for_retry(restart_box):
    box = restart_box
    source = prepare_restart(box)
    before = source.read_bytes()
    real_mv = shutil.which("mv")
    _write(box.fakebin / "mv", f'''#!/usr/bin/env bash
case "$*" in *.resume.*) exit 1 ;; esac
exec '{real_mv}' "$@"
''')
    first = box.start("--operation", "op-test")
    assert first.returncode == 2, first.stderr
    assert "published atomically" in first.stderr
    assert source.read_bytes() == before
    assert box.claude_runs() == ""
    (box.fakebin / "mv").unlink()
    assert helper(box, "set-restart-intent", LANE, "failed", "--expect", "starting").returncode == 0
    assert helper(box, "set-restart-intent", LANE, "starting", "--expect", "failed", "--bump-attempt", "--new-transcript", "none").returncode == 0
    retry = box.start("--operation", "op-test")
    assert retry.returncode == 0, retry.stderr


def test_restart_historical_ready_intent_does_not_control_ordinary_resume(restart_box):
    box = restart_box
    prepare_restart(box)
    assert helper(box, "set-restart-intent", LANE, "ready", "--expect", "pending").returncode == 0
    before = intent_path(box).read_bytes()
    result = box.start()
    assert result.returncode == 0, result.stderr
    assert intent_path(box).read_bytes() == before
    assert box.claude_runs()


def test_restart_second_ctx_leaves_inflight_preservation_unchanged(restart_box):
    box = restart_box
    source = prepare_restart(box)
    before = {p: p.read_bytes() for p in (source, box.wip / "lanes" / "LANES.md", intent_path(box))}
    result = supervisor(box, "--restart", "--lane", LANE, "--dir", str(box.lane_dir), "clear")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "No handoff, row, log or window was changed" in result.stderr
    assert all(p.read_bytes() == contents for p, contents in before.items())


def test_restart_preparation_error_releases_only_its_reservation(restart_box):
    box = restart_box
    prepare_restart(box)
    assert helper(box, "set-restart-intent", LANE, "ready", "--expect", "pending").returncode == 0
    real_mktemp = shutil.which("mktemp")
    _write(box.fakebin / "mktemp", f'''#!/usr/bin/env bash
case "$*" in *lane-handoff-writers*) exit 1 ;; esac
exec '{real_mktemp}' "$@"
''')
    result = supervisor(box, "--restart", "--lane", LANE, "--dir", str(box.lane_dir), "clear")
    assert result.returncode == 2, (result.stdout, result.stderr)
    record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
    assert record["state"] == "failed"
    assert "preservation stopped" in record["reason"]
    assert record["generation"] == "8"
    assert record["mode"] == "preservation-only"
    retry = supervisor(box, "--supervise", "--lane", LANE, "--operation", record["operation"])
    assert retry.returncode == 2, (retry.stdout, retry.stderr)
    assert "only 'fresh-from-handoff'" in retry.stderr
    assert box.claude_runs() == ""
    assert "respawn-pane" not in box.tmux_log.read_text()
    (box.fakebin / "mktemp").unlink()
    prior = helper(box, "last-session", LANE)
    assert prior.returncode == 0, prior.stderr
    transcript = prior.stdout.strip()
    dirname = "".join(ch if ch.isascii() and ch.isalnum() else "-" for ch in str(box.lane_dir))
    _write(box.home / ".claude" / "projects" / dirname / (transcript + ".jsonl"),
           '{"type":"user","message":{"role":"user","content":"preserved work"}}\n', 0o600)
    unchanged = intent_path(box).read_bytes()
    status = supervisor(box, "--restart-status", "--lane", LANE)
    assert "PREPARATION FAILED" in status.stdout
    assert "RETRY:" not in status.stdout
    resumed = box.start()
    assert resumed.returncode == 0, (resumed.stdout, resumed.stderr)
    assert "--resume " + transcript in box.claude_runs()
    assert "--session-id" not in box.claude_runs()
    assert intent_path(box).read_bytes() == unchanged


def failed_preparation(box):
    prepare_restart(box)
    result = helper(box, "set-restart-intent", LANE, "failed", "--expect", "pending",
                    "--mode", "preservation-only", "--attempt", "0", "--new-transcript", "none")
    assert result.returncode == 0, result.stderr
    records = {p for root in (box.wip / "lanes", box.wip / "handoffs")
               for p in root.rglob("*") if p.is_file()}
    records.add(intent_path(box))
    return {p: p.read_bytes() for p in records}


@pytest.mark.parametrize("holder_rc", [0, 1, 2])
def test_preparation_recovery_requires_confirmed_holder_absence(restart_box, holder_rc):
    box = restart_box
    before = failed_preparation(box)
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    _write(box.bin / "lanes-edit.sh", f"""#!/usr/bin/env bash
[ "$1" != lane-holders ] || exit {holder_rc}
exec '{real}' "$@"
""")
    box.tmux_log.write_text("")
    result = box.start()
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "confirmed absence" in result.stderr
    assert all(p.read_bytes() == data for p, data in before.items())
    assert "rename-window" not in box.tmux_log.read_text()
    assert box.claude_runs() == ""


@pytest.mark.parametrize("kind", ["attempt", "transcript", "launch", "preparing", "operation-token", "environment-operation", "environment-attempt", "fresh", "environment-fresh"])
def test_preparation_recovery_rejects_launch_ownership_or_tokens(restart_box, kind):
    box = restart_box
    failed_preparation(box)
    changes = {"attempt": ("--attempt", "1"),
               "transcript": ("--new-transcript", "11111111-2222-4333-8444-555555555555"),
               "launch": ("--mode", "fresh-from-handoff")}
    if kind in changes or kind == "preparing":
        result = helper(box, "set-restart-intent", LANE, "preparing" if kind == "preparing" else "failed",
                        *changes.get(kind, ()))
        assert result.returncode == 0, result.stderr
    before = intent_path(box).read_bytes()
    args, env = (), {}
    if kind == "operation-token": args = ("--operation", "op-test")
    if kind == "environment-operation": env["LANE_RESTART_OPERATION"] = "op-test"
    if kind == "environment-attempt": env["LANE_RESTART_ATTEMPT"] = "0"
    if kind == "fresh": args = ("--fresh",)
    if kind == "environment-fresh": env["LANE_START_FRESH"] = "1"
    box.tmux_log.write_text("")
    result = box.start(*args, **env)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert intent_path(box).read_bytes() == before
    assert "rename-window" not in box.tmux_log.read_text()
    assert box.claude_runs() == ""


@pytest.mark.parametrize("stage", [2, 3])
def test_preparation_recovery_rechecks_operation_before_launch(restart_box, stage):
    box = restart_box
    failed_preparation(box)
    count = box.root / "intent-reads"
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    _write(box.bin / "lanes-edit.sh", f"""#!/usr/bin/env bash
if [ "$1" = restart-intent ]; then
  n=$(cat '{count}' 2>/dev/null || printf 0)
  n=$((n + 1)); printf '%s\n' "$n" > '{count}'
  if [ "$n" = {stage} ]; then
    '{real}' set-restart-intent "$2" failed --operation newer-preparation --generation 8 --mode preservation-only --attempt 0 --new-transcript none >/dev/null || exit 1
  fi
fi
exec '{real}' "$@"
""")
    result = box.start()
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "changed during ordinary recovery" in result.stderr
    assert box.claude_runs() == ""
    final = helper(box, "restart-intent", LANE)
    assert "operation\tnewer-preparation" in final.stdout
    assert "generation\t8" in final.stdout
    assert "state\tfailed" in final.stdout


@pytest.mark.parametrize("stage,holder_rc", [(2, 0), (3, 1)])
def test_preparation_recovery_rechecks_holders_before_launch(restart_box, stage, holder_rc):
    box = restart_box
    failed_preparation(box)
    before = intent_path(box).read_bytes()
    count = box.root / "holder-reads"
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    _write(box.bin / "lanes-edit.sh", f"""#!/usr/bin/env bash
if [ "$1" = lane-holders ]; then
  n=$(cat '{count}' 2>/dev/null || printf 0)
  n=$((n + 1)); printf '%s\n' "$n" > '{count}'
  if [ "$n" = {stage} ]; then exit {holder_rc}; fi
  exit 8
fi
exec '{real}' "$@"
""")
    result = box.start()
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "confirmed absence" in result.stderr
    assert box.claude_runs() == ""
    assert intent_path(box).read_bytes() == before


@pytest.mark.parametrize("damage", ["attempt", "transcript"])
def test_preparation_recovery_rejects_malformed_identity(restart_box, damage):
    box = restart_box
    failed_preparation(box)
    path = intent_path(box)
    text = path.read_text()
    text = text.replace("attempt: 0\n", "attempt: -1\n") if damage == "attempt" else text.replace("new_transcript: none\n", "")
    path.write_text(text)
    before = {p: p.read_bytes() for root in (box.wip / "lanes", box.wip / "handoffs", path.parent)
              for p in root.rglob("*") if p.is_file()}
    box.tmux_log.write_text("")
    result = box.start()
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "INCOMPLETE" in result.stderr
    assert all(p.read_bytes() == data for p, data in before.items())
    assert "rename-window" not in box.tmux_log.read_text()
    assert box.claude_runs() == ""


def live_record(box, pid, transcript, suffix):
    proc = Path(f"/proc/{pid}/stat")
    start = proc.read_text().split()[21] if proc.exists() else ""
    path = box.home / ".claude" / "sessions" / f"{suffix}.json"
    _write(path, json.dumps(dict(pid=pid, sessionId=transcript, cwd=str(box.lane_dir),
                                procStart=start, tmux="testsess:@1.%1", name=LANE,
                                nameSource="user", status="busy"), separators=(",", ":")) + "\n", 0o600)
    return path


def test_restart_all_holders_retains_duplicate_processes_for_one_uuid(restart_box):
    box = restart_box
    prepare_restart(box)
    sid = "10101010-1111-4111-8111-111111111111"
    row = next(line for line in (box.wip / "lanes" / "LANES.md").read_text().splitlines()
               if line.startswith(f"| `{LANE}`"))
    anchor = row.split("|")[2].strip()
    result = helper(box, "append-session-id", LANE, anchor, f"`{sid}`")
    assert result.returncode == 0, result.stderr
    procs = [subprocess.Popen(["sleep", "20"]) for _ in range(2)]
    try:
        for n, proc in enumerate(procs):
            live_record(box, proc.pid, sid, str(n))
        result = helper(box, "lane-holders", LANE)
        assert result.returncode == 0, result.stderr
        assert len(result.stdout.splitlines()) == 2
        assert len(helper(box, "live-holder", LANE).stdout.splitlines()) == 1
    finally:
        for proc in procs:
            proc.terminate()
            proc.wait(timeout=5)


@pytest.mark.parametrize("child_state", ["live", "zombie"])
def test_restart_observer_confirms_late_uuid_prepared_by_real_child(restart_box, child_state):
    box = restart_box
    prepare_restart(box)
    if child_state == "zombie":
        ps = shutil.which("ps")
        _write(box.fakebin / "ps", f"""#!/usr/bin/env bash
case "$*" in *"-o stat="*) printf 'Z\n'; exit 0 ;; esac
exec '{ps}' "$@"
""")
    box.env["FAKE_CHILD_STATE"] = child_state
    # A fake profile launcher forwards both supervisor tokens in the existing
    # pane. The child itself executes real lane-start, including the stamp.
    launcher = _write(box.fakebin / "pclaude", '''#!/usr/bin/env bash
export CLAUDE_PROFILE_NAME=test-profile
exec "$OPENREPOTOOLS_BIN_DIR/lane-start" repoZ 1
''')
    _write(box.resolved, r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
args=sys.argv[1:]
sid=args[args.index('--session-id')+1]
pid=os.getpid()
stat=pathlib.Path(f'/proc/{pid}/stat')
start=stat.read_text().split()[21] if stat.exists() else ''
record=dict(pid=pid, sessionId=sid, procStart=start, cwd=os.getcwd(),
            tmux='testsess:@1.%1', name='repoZ-1', nameSource='user', status='busy')
record_path=pathlib.Path(os.environ['HOME'])/'.claude'/'sessions'/'ready.json'
record_path.write_text(json.dumps(record, separators=(',', ':'))+'\n')
# /clear can leave a historical UUID witness for this same process.
registry=pathlib.Path(os.environ['HOME'])/'projects'/'wip'/'lanes'/'LANES.md'
import re
uuids=re.findall(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', registry.read_text())
if uuids:
    historical=dict(record, sessionId=uuids[0])
    (record_path.parent/'historical.json').write_text(json.dumps(historical, separators=(',', ':'))+'\n')

pathlib.Path(os.environ['FAKE_CLAUDE_LOG']).write_text(' '.join(args))
intent=pathlib.Path(os.environ['LANES_LANE_STATE_ROOT'])/'repoZ-1'/'restart-intent.yaml'
if os.environ.get('FAKE_CHILD_STATE') == 'zombie':
    time.sleep(1)
    record_path.unlink()
    historical_path=record_path.parent/'historical.json'
    if historical_path.exists(): historical_path.unlink()
    sys.exit(127)
for _ in range(150):
    if 'state: ready\n' in intent.read_text(): break
    time.sleep(.1)
else: sys.exit(4)
record_path.unlink()
''')
    box.env.update(PCLAUDE=str(launcher), LANE_SUPERVISOR_NO_PROMPT="1",
                   LANE_SUPERVISOR_READY_SECONDS="15", FAKE_CC_PATH=str(box.resolved), TMUX_PANE="%1")
    result = supervisor(box, "--supervise", "--lane", LANE, "--operation", "op-test")
    assert result.returncode == (0 if child_state == "live" else 3), (result.stdout, result.stderr)
    record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
    assert record["state"] == ("ready" if child_state == "live" else "failed")
    assert record["attempt"] == "1"
    assert record["new_transcript"] != "none"
    assert "Preserved task." in box.claude_runs()


def test_restart_signal_before_claim_preserves_pending_intent(restart_box):
    from conftest import REPO
    box = restart_box
    prepare_restart(box)
    before = intent_path(box).read_bytes()
    shutil.copy2(REPO / "lane-handoff", box.bin / "lane-handoff")
    marker = box.root / "preflight.marker"
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    _write(box.bin / "lanes-edit.sh", f'''#!/usr/bin/env bash
if [ "$1" = legacy-restart-check ]; then
  touch '{marker}'
  sleep 1
fi
exec "$(dirname -- "$0")/lanes-edit-real.sh" "$@"
''')
    with (box.root / "preflight.out").open("w") as output:
        proc = subprocess.Popen([str(box.bin / "lane-handoff"), "--supervise", "--lane", LANE,
                                 "--operation", "op-test"], cwd=box.lane_dir, env=box.env,
                                stdout=output, stderr=output, start_new_session=True)
        try:
            deadline = time.monotonic() + 10
            while not marker.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(.02)
            assert marker.exists()
            proc.send_signal(signal.SIGTERM)
            assert proc.wait(timeout=5) == 143
            assert intent_path(box).read_bytes() == before
        finally:
            try: os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            if proc.poll() is None: proc.wait(timeout=5)


def test_restart_missing_checksum_is_not_launch_authority(restart_box):
    box = restart_box
    source = prepare_restart(box)
    assert helper(box, "set-restart-intent", LANE, "pending", "--digest", "none").returncode == 0
    before = source.read_bytes()
    result = box.start("--operation", "op-test")
    assert result.returncode == 2, result.stderr
    assert "no complete handoff checksum" in result.stderr
    result = supervisor(box, "--supervise", "--lane", LANE, "--operation", "op-test")
    assert result.returncode == 2, result.stderr
    assert source.read_bytes() == before
    assert box.claude_runs() == ""


def test_restart_stale_supervisor_cannot_fail_or_retry_newer_operation(restart_box):
    box = restart_box
    prepare_restart(box)
    child = _write(box.fakebin / "pclaude", '''#!/usr/bin/env bash
"$OPENREPOTOOLS_BIN_DIR/lanes-edit.sh" set-restart-intent repoZ-1 pending \
  --expect starting --expect-operation op-test --operation newer --generation 8 \
  --reason 'new owner' >/dev/null || exit 9
exit 127
''')
    box.env.update(PCLAUDE=str(child), LANE_SUPERVISOR_NO_PROMPT="1")
    result = supervisor(box, "--supervise", "--lane", LANE, "--operation", "op-test")
    assert result.returncode == 2, (result.stdout, result.stderr)
    record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
    assert record["state"] == "pending"
    assert record["generation"] == "8"
    assert record["operation"] == "newer"
    assert record["reason"] == "new owner"
    assert "no retry is authorized" in result.stdout
    assert "RESTART FAILED" not in result.stdout


@pytest.mark.parametrize("field", ["agent", "window", "new_transcript", "created"])
def test_restart_truncated_intent_is_never_repaired_by_transition(restart_box, field):
    box = restart_box
    prepare_restart(box)
    path = intent_path(box)
    path.write_text("\n".join(line for line in path.read_text().splitlines() if not line.startswith(field + ":")) + "\n")
    before = path.read_bytes()
    result = helper(box, "restart-intent", LANE)
    assert "state\tINCOMPLETE" in result.stdout
    assert field in result.stdout
    result = helper(box, "set-restart-intent", LANE, "starting", "--expect", "pending")
    assert result.returncode == 2, result.stderr
    assert path.read_bytes() == before


def test_restart_publication_fences_changed_bytes_and_current_attempt(restart_box):
    box = restart_box
    source = prepare_restart(box)
    before = source.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    prepared = box.root / "prepared.md"
    _write(prepared, "# owned stamp\n\nPreserved task.\n", 0o600)
    args = ("publish-handoff", LANE, str(source), str(prepared), "--expect-digest", digest,
            "--operation", "op-test", "--generation", "7", "--attempt", "0",
            "--state", "pending", "--transcript", "none")
    # Changed source and stale intent must independently refuse publication.
    source.write_text(source.read_text() + "Other writer's instructions.\n")
    changed = source.read_bytes()
    result = helper(box, *args)
    assert result.returncode == 7, result.stderr
    assert source.read_bytes() == changed
    source.write_bytes(before)
    assert helper(box, "set-restart-intent", LANE, "starting", "--attempt", "1").returncode == 0
    result = helper(box, *args)
    assert result.returncode == 7, result.stderr
    assert source.read_bytes() == before


def test_plain_handoff_refuses_active_restart_before_preservation(restart_box):
    box = restart_box
    source = prepare_restart(box)
    before = {p: p.read_bytes() for p in (source, box.wip / "lanes" / "LANES.md", intent_path(box))}
    result = supervisor(box, "--lane", LANE, "--dir", str(box.lane_dir), "handoff")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "preservation refused before" in result.stderr
    assert all(p.read_bytes() == contents for p, contents in before.items())


@pytest.mark.parametrize("field,value", [("operation", "bad operation"), ("dir", "relative"),
                                         ("digest", "bad-sha"), ("lane", "other-1"),
                                         ("generation", "1:2"), ("attempt", "1:2")])
def test_restart_writer_preserves_invalid_existing_values(restart_box, field, value):
    box = restart_box
    prepare_restart(box)
    path = intent_path(box)
    text = path.read_text()
    contents = "\n".join(f"{field}: {value}" if line.startswith(f"{field}:") else line
                         for line in text.splitlines()) + "\n"
    path.write_text(contents)
    result = helper(box, "set-restart-intent", LANE, "starting", "--expect", "pending")
    assert result.returncode == 2, result.stderr
    assert path.read_text() == contents
    assert "state\tINCOMPLETE" in helper(box, "restart-intent", LANE).stdout


def test_handoff_publishers_serialize_checksum_and_replacement(restart_box):
    box = restart_box
    source = prepare_restart(box)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    ready, release = box.root / "publisher.locked", box.root / "publisher.release"
    first, second = box.root / "first.md", box.root / "second.md"
    first.write_text("First publisher.\n")
    second.write_text("Second publisher.\n")
    cp = shutil.which("cp")
    _write(box.fakebin / "cp", f"""#!/usr/bin/env bash
case "$*" in
  *.resume.*)
    : > '{ready}'
    while [ ! -e '{release}' ]; do sleep .05; done ;;
esac
exec '{cp}' "$@"
""")
    def command(prepared):
        return [str(box.bin / "lanes-edit.sh"), "publish-handoff", LANE, str(source),
                str(prepared), "--expect-digest", digest, "--operation", "op-test",
                "--generation", "7", "--attempt", "0", "--state", "pending",
                "--transcript", "none"]
    a = subprocess.Popen(command(first), cwd=box.lane_dir, env=box.env,
                         text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    b = None
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and a.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        assert ready.exists(), a.communicate(timeout=5)
        b = subprocess.Popen(command(second), cwd=box.lane_dir, env=box.env,
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        release.touch()
        out_a = a.communicate(timeout=20)
        out_b = b.communicate(timeout=20)
        assert a.returncode == 0, out_a
        assert b.returncode == 7, out_b
        assert source.read_text() == "First publisher.\n"
    finally:
        release.touch()
        for process in (a, b):
            if process is not None and process.poll() is None:
                process.terminate()
                process.communicate(timeout=10)


def test_new_lane_checkout_without_projects_root_can_launch(restart_box):
    box = restart_box
    box.env.pop("LANES_LANE_STATE_ROOT")
    box.env["PROJECTS_ROOT"] = str(box.root / "missing-projects")
    box.resolver()
    result = box.start("--dir", str(box.lane_dir))
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert box.claude_runs()


def test_new_lane_checkout_hint_still_refuses_unreadable_intent(restart_box):
    box = restart_box
    box.env.pop("LANES_LANE_STATE_ROOT")
    box.env["PROJECTS_ROOT"] = str(box.root / "missing-projects")
    (box.lane_dir.parent / ".lane-state" / LANE / "restart-intent.yaml").mkdir(parents=True)
    box.resolver()
    result = box.start("--dir", str(box.lane_dir))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert not box.claude_runs()


def test_interactive_retry_rechecks_holder_absence_before_launch(restart_box):
    import pty
    import fcntl
    import termios
    import errno
    from conftest import REPO
    box = restart_box
    prepare_restart(box)
    shutil.copy2(REPO / "lane-handoff", box.bin / "lane-handoff")
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    _write(box.bin / "lanes-edit.sh", f"""#!/usr/bin/env bash
if [ "$1" = lane-holders ] && command grep -q '^attempt: 2$' '{intent_path(box)}'; then
  printf 'another holder\n'
  exit 0
fi
exec "$(dirname -- "$0")/lanes-edit-real.sh" "$@"
""")
    launches = box.root / "launches"
    child = _write(box.fakebin / "pclaude", f"""#!/usr/bin/env bash
printf 'launch\n' >> '{launches}'
exit 127
""")
    box.env.update(PCLAUDE=str(child))
    box.env.pop("LANE_SUPERVISOR_NO_PROMPT", None)
    master, slave = pty.openpty()
    fcntl.fcntl(master, fcntl.F_SETFL, fcntl.fcntl(master, fcntl.F_GETFL) | os.O_NONBLOCK)
    output_path = box.root / "interactive.out"

    def drain_terminal():
        # Consume terminal echo as a pane does. Darwin waits for queued tty
        # output during session-leader exit, even when stdout is a file.
        while True:
            try:
                if not os.read(master, 4096):
                    return
            except BlockingIOError:
                return
            except OSError as error:
                if error.errno == errno.EIO:  # the slave has closed on Linux
                    return
                raise

    def wait_with_terminal(timeout):
        deadline = time.monotonic() + timeout
        while True:
            drain_terminal()
            status = proc.poll()
            if status is not None:
                return status
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(proc.args, timeout)
            time.sleep(.01)

    def own_terminal():
        # Match a pane: the supervisor owns a controlling tty in its session.
        # An openpty fd alone is only a tty, which differs on macOS.
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    with output_path.open("w") as output:
        proc = subprocess.Popen([str(box.bin / "lane-handoff"), "--supervise", "--lane", LANE,
                                 "--operation", "op-test"], cwd=box.lane_dir, env=box.env,
                                stdin=slave, stdout=output, stderr=output, start_new_session=True,
                                preexec_fn=own_terminal)
        os.close(slave)
        try:
            deadline = time.monotonic() + 15
            while "retry this restart?" not in output_path.read_text() and proc.poll() is None and time.monotonic() < deadline:
                drain_terminal()
                time.sleep(.05)
            assert "retry this restart?" in output_path.read_text(), output_path.read_text()
            os.write(master, b"r\n")
            # The terminal stays open for an indeterminate result until its
            # message is acknowledged, matching the real supervisor pane.
            deadline = time.monotonic() + 15
            while "Press Enter to close it" not in output_path.read_text() and proc.poll() is None and time.monotonic() < deadline:
                drain_terminal()
                time.sleep(.05)
            assert "INDETERMINATE" in output_path.read_text(), output_path.read_text()
            assert "Press Enter to close it" in output_path.read_text(), output_path.read_text()
            os.write(master, b"\n")
            try:
                status = wait_with_terminal(15)
            except subprocess.TimeoutExpired as error:
                raise AssertionError("supervisor did not exit after Enter:\n" + output_path.read_text()) from error
            assert status == 4, output_path.read_text()
            assert launches.read_text().splitlines() == ["launch"]
            record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
            assert record["state"] == "starting" and record["attempt"] == "2"
            assert "before attempt launch" in record["reason"]
        finally:
            # Disconnect even on assertion/timeout: an unread master must
            # not prevent Darwin from completing the owned process's exit.
            os.close(master)
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)


def test_checkout_hint_cannot_hide_existing_fallback_intent(restart_box):
    box = restart_box
    box.env.pop("LANES_LANE_STATE_ROOT")
    fallback = box.root / "established-projects"
    fallback.mkdir()
    box.env["PROJECTS_ROOT"] = str(fallback)
    source = box.wip / "handoffs" / "README.md"
    result = helper(box, "set-restart-intent", LANE, "pending", "--expect", "none",
                    "--operation", "established", "--agent", "claude", "--handoff", str(source))
    assert result.returncode == 0, result.stderr
    path = fallback / ".lane-state" / LANE / "restart-intent.yaml"
    before = path.read_bytes()
    box.resolver()
    result = box.start("--dir", str(box.lane_dir))
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "supervisor operation token" in result.stderr
    assert not box.claude_runs()
    assert path.read_bytes() == before


@pytest.mark.parametrize("holder_rc", [0, 1])
def test_signal_after_launcher_exit_keeps_live_or_unknown_holder_indeterminate(restart_box, holder_rc):
    from conftest import REPO
    box = restart_box
    prepare_restart(box)
    shutil.copy2(REPO / "lane-handoff", box.bin / "lane-handoff")
    exited, probed, release = (box.root / name for name in ("child.exited", "holder.probed", "holder.release"))
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    _write(box.bin / "lanes-edit.sh", f"""#!/usr/bin/env bash
if [ "$1" = lane-holders ] && [ -e '{exited}' ]; then
  : > '{probed}'
  while [ ! -e '{release}' ]; do sleep .05; done
  exit {holder_rc}
fi
exec "$(dirname -- "$0")/lanes-edit-real.sh" "$@"
""")
    child = _write(box.fakebin / "pclaude", f"""#!/usr/bin/env bash
: > '{exited}'
exit 127
""")
    box.env.update(PCLAUDE=str(child), LANE_SUPERVISOR_NO_PROMPT="1")
    output_path = box.root / "ended-child-signal.out"
    with output_path.open("w") as output:
        proc = subprocess.Popen([str(box.bin / "lane-handoff"), "--supervise", "--lane", LANE,
                                 "--operation", "op-test"], cwd=box.lane_dir, env=box.env,
                                stdout=output, stderr=output, start_new_session=True)
        try:
            deadline = time.monotonic() + 15
            while not probed.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            assert probed.exists(), output_path.read_text()
            proc.send_signal(signal.SIGTERM)
            release.touch()
            assert proc.wait(timeout=15) == 143, output_path.read_text()
            record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
            assert record["state"] == "starting"
            assert "INDETERMINATE" in record["reason"]
        finally:
            release.touch()
            try: os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            if proc.poll() is None: proc.wait(timeout=10)


def test_respawn_restores_configured_roots_in_new_pane(restart_box):
    box = restart_box
    protocol = box.root / "protocol with spaces"
    (box.home / ".agents").rename(protocol)
    box.env["AGENT_PROTOCOL_ROOT"] = str(protocol)
    box.env["LANES_LANE_STATE_ROOT"] = str(box.root / "state with spaces")
    box.env.update(LANES_HOST="fixture-host", LANES_OS="linux", LANES_CONTAINER="fixture-container")
    prepare_restart(box)
    assert helper(box, "set-restart-intent", LANE, "ready", "--expect", "pending").returncode == 0
    real_tmux = box.fakebin / "tmux-real"
    (box.fakebin / "tmux").rename(real_tmux)
    pane_result = box.root / "pane-result"
    _write(box.fakebin / "tmux", f"""#!/usr/bin/env bash
if [ "$1" = respawn-pane ]; then
  for arg in "$@"; do line="$arg"; done
  env -u LANES_LANE_STATE_ROOT -u AGENT_PROTOCOL_ROOT -u LANES_HOST -u LANES_OS -u LANES_CONTAINER sh -c "$line"
  printf '%s\n' "$?" > '{pane_result}'
  exit 0
fi
exec '{real_tmux}' "$@"
""")
    child = _write(box.fakebin / "pclaude", """#!/usr/bin/env bash
[ "$LANES_HOST" = fixture-host ] && [ "$LANES_OS" = linux ] && [ "$LANES_CONTAINER" = fixture-container ] || exit 66
exit 127
""")
    box.env.update(PCLAUDE=str(child), CLAUDE_PROFILE_NAME="test-profile",
                   LANE_SUPERVISOR_NO_PROMPT="1", TMUX_PANE="%1")
    result = supervisor(box, "--restart", "--lane", LANE, "--dir", str(box.lane_dir), "clear")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert pane_result.read_text().strip() == "3", (result.stdout, result.stderr)
    record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
    assert record["state"] == "failed" and record["attempt"] == "1"
    assert "127" in record["reason"]


@pytest.mark.parametrize("pane", ["", "%2"])
def test_supervisor_refuses_unknown_or_different_pane(restart_box, pane):
    box = restart_box
    prepare_restart(box)
    before = intent_path(box).read_bytes()
    box.env["TMUX_PANE"] = pane
    result = supervisor(box, "--supervise", "--lane", LANE, "--operation", "op-test")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "pane" in result.stderr
    assert intent_path(box).read_bytes() == before
    assert not box.claude_runs()


@pytest.mark.parametrize("kind", ["file", "ancestor-file", "broken-link"])
def test_existing_invalid_state_root_is_not_absent_intent(restart_box, kind):
    box = restart_box
    root = Path(box.env["LANES_LANE_STATE_ROOT"])
    if kind == "file":
        root.write_text("not a directory\n")
    elif kind == "ancestor-file":
        root.write_text("not a directory\n")
        box.env["LANES_LANE_STATE_ROOT"] = str(root / "child")
    else:
        root.symlink_to(box.root / "missing-target")
    assert helper(box, "restart-intent", LANE).returncode == 1
    box.resolver()
    result = box.start()
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert not box.claude_runs()


@pytest.mark.parametrize("extra", ["future_key: preserve-me\n", "garbage\n", "profile:test\n", "\n",
                                   "schema: 1\n", "prepared_digest: none\n",
                                   "pane: testsess:@1.%1\tignored\n"])
def test_restart_strict_schema_preserves_unrecognized_or_malformed_records(restart_box, extra):
    box = restart_box
    prepare_restart(box)
    path = intent_path(box)
    path.write_text(path.read_text() + extra)
    before = path.read_bytes()
    read = helper(box, "restart-intent", LANE)
    assert "state\tINCOMPLETE" in read.stdout, (read.stdout, read.stderr)
    write = helper(box, "set-restart-intent", LANE, "starting", "--expect", "pending")
    assert write.returncode == 2, write.stderr
    assert path.read_bytes() == before
    assert box.start("--operation", "op-test").returncode == 2
    assert not box.claude_runs()


@pytest.mark.parametrize("field", ["dir", "handoff", "pane", "window"])
@pytest.mark.parametrize("control", ["\n", "\r", "\t"])
def test_restart_writer_rejects_record_delimiters_without_changing_identity(restart_box, field, control):
    box = restart_box
    prepare_restart(box)
    before = intent_path(box).read_bytes()
    value = (str(box.lane_dir) if field in {"dir", "handoff"} else "testsess:@1.%1") + control + "tail"
    result = helper(box, "set-restart-intent", LANE, "pending", f"--{field}", value)
    assert result.returncode == 64, (result.stdout, result.stderr)
    assert intent_path(box).read_bytes() == before


def test_restart_writer_rejects_record_delimiters_all_ascii_controls(restart_box):
    box = restart_box
    prepare_restart(box)
    before = intent_path(box).read_bytes()
    for code in [*range(1, 32), 127]:
        result = helper(box, "set-restart-intent", LANE, "pending", "--pane",
                        "testsess:@1.%1" + chr(code) + "tail")
        assert result.returncode == 64, (code, result.stdout, result.stderr)
        assert intent_path(box).read_bytes() == before


def test_restart_writer_does_not_follow_predictable_temporary_symlink(restart_box):
    box = restart_box
    prepare_restart(box)
    sentinel = box.root / "sentinel"
    sentinel.write_text("unrelated bytes\n")
    result = subprocess.run(["bash", "-c", 'ln -s "$1" "$2.tmp.$$"; exec "$3" set-restart-intent "$4" starting --expect pending',
                             "_", str(sentinel), str(intent_path(box)), str(box.bin / "lanes-edit.sh"), LANE],
                            env=box.env, cwd=box.lane_dir, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert sentinel.read_text() == "unrelated bytes\n"
    assert list(intent_path(box).parent.glob("restart-intent.yaml.tmp.*"))[0].is_symlink()
    assert intent_path(box).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("alias", ["file", "parent"])
def test_restart_accepts_equivalent_handoff_file_identity(restart_box, alias):
    box = restart_box
    source = prepare_restart(box)
    physical = source
    if alias == "file":
        physical = source.with_name("backing.md")
        source.rename(physical)
        source.symlink_to(physical.name)
        box.git("-C", str(box.wip), "add", "--", str(source), str(physical))
        box.git("-C", str(box.wip), "commit", "-qm", "use leaf handoff alias")
        box.git("-C", str(box.wip), "push", "-q", "origin", "main")
    else:
        link = source.parent.with_name("handoff-alias")
        link.symlink_to(source.parent, target_is_directory=True)
        source = link / source.name
        registry = box.wip / "lanes" / "LANES.md"
        registry.write_text(registry.read_text().replace(str(physical.relative_to(box.wip)), str(source.relative_to(box.wip))))
        box.git("-C", str(box.wip), "add", "--", "lanes/LANES.md", str(link))
        box.git("-C", str(box.wip), "commit", "-qm", "use handoff directory alias")
        box.git("-C", str(box.wip), "push", "-q", "origin", "main")
    result = helper(box, "set-restart-intent", LANE, "pending", "--handoff", str(source.resolve()))
    assert result.returncode == 0, result.stderr
    first = box.start("--operation", "op-test")
    assert first.returncode == 0, (first.stdout, first.stderr)
    assert "Preserved task." in box.claude_runs()
    assert "RESUMED by" in physical.read_text()
    if alias == "file":
        assert source.is_symlink()
    assert helper(box, "set-restart-intent", LANE, "failed", "--expect", "starting").returncode == 0
    assert helper(box, "set-restart-intent", LANE, "starting", "--expect", "failed", "--bump-attempt", "--new-transcript", "none").returncode == 0
    retry = box.start("--operation", "op-test")
    assert retry.returncode == 0, (retry.stdout, retry.stderr)


@pytest.mark.parametrize("state", ["preparing", "pending", "starting", "failed", "ready"])
def test_restart_reconcile_rename_preserves_unfinished_operation_inputs(restart_box, state):
    box = restart_box
    source = prepare_restart(box)
    assert helper(box, "set-restart-intent", LANE, state, "--expect", "pending").returncode == 0
    if state == "ready":
        inventory = helper(box, "set-lane-tree", LANE, str(box.lane_dir))
        assert inventory.returncode == 0, inventory.stderr
        trees = {p.name: p.read_bytes() for p in intent_path(box).parent.glob("trees/*.yaml")}
        assert trees
    tracked = [p for p in box.wip.rglob("*") if p.is_file() and ".git" not in p.parts]
    before = {p: p.read_bytes() for p in tracked}
    record = intent_path(box).read_bytes()
    box.env["LANES_SESSION"] = "10101010-1111-4111-8111-111111111111"
    result = helper(box, "rename-lane", LANE, "repoZ-2", "--no-github")
    if state == "ready":
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "repoZ-2" in (box.wip / "lanes" / "LANES.md").read_text()
    else:
        assert result.returncode == 2, (result.stdout, result.stderr)
        assert "supervised recovery" in result.stderr
        assert {p: p.read_bytes() for p in tracked} == before
        assert set(tracked) == {p for p in box.wip.rglob("*") if p.is_file() and ".git" not in p.parts}
    assert intent_path(box).read_bytes() == record
    if state == "ready":
        # Completed history remains at the old name; diagnostics follow the row.
        new_root = intent_path(box).parent.with_name("repoZ-2")
        assert (new_root / "lane-state.yaml").is_file()
        assert {p.name: p.read_bytes() for p in new_root.glob("trees/*.yaml")} == trees
        assert not (intent_path(box).parent / "trees").exists()
        assert not (intent_path(box).parent / "lane-state.yaml").exists()
        assert helper(box, "restart-intent", "repoZ-2").returncode == 8
        resumed = box.start("--no-launch")
        assert resumed.returncode == 0, (resumed.stdout, resumed.stderr)
        assert intent_path(box).read_bytes() == record


@pytest.mark.parametrize("kind", ["relative", "missing", "none", "agent", "tab", "newline"])
def test_restart_refuses_unsupported_checkout_or_agent_before_preservation(restart_box, kind):
    box = restart_box
    source = prepare_restart(box)
    assert helper(box, "set-restart-intent", LANE, "ready", "--expect", "pending").returncode == 0
    before = source.read_bytes()
    registry = (box.wip / "lanes" / "LANES.md").read_bytes()
    box.tmux_log.write_text("")
    args = ["--restart", "--lane", LANE]
    if kind in {"relative", "missing"}:
        args += ["--dir", "relative" if kind == "relative" else str(box.root / "absent")]
    elif kind == "agent":
        args += ["--agent", "codex"]
    elif kind in {"tab", "newline"}:
        unsafe = box.root / ("checkout" + ("\t" if kind == "tab" else "\n") + "tail")
        unsafe.mkdir()
        args += ["--dir", str(unsafe)]
    else:
        real = box.bin / "lanes-edit-real.sh"
        (box.bin / "lanes-edit.sh").rename(real)
        _write(box.bin / "lanes-edit.sh", f"""#!/usr/bin/env bash
[ "$1" != lane-dir ] || exit 8
exec '{real}' "$@"
""")
        box.env.pop("WORKBENCHES_CLAUDE_LANE_DIR", None)
        box.env.pop("CLAUDE_CODE_SESSION_ID", None)
    result = supervisor(box, *args, "clear")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert source.read_bytes() == before
    assert (box.wip / "lanes" / "LANES.md").read_bytes() == registry
    assert "rename-window" not in box.tmux_log.read_text()
    assert "respawn-pane" not in box.tmux_log.read_text()
    if kind in {"tab", "newline"}:
        assert "control characters" in result.stderr


@pytest.mark.parametrize("fact", ["dir", "digest", "pane", "agent"])
def test_restart_verifies_complete_pending_record_before_respawn(restart_box, fact):
    box = restart_box
    prepare_restart(box)
    assert helper(box, "set-restart-intent", LANE, "ready", "--expect", "pending").returncode == 0
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    value = {"dir": "none", "digest": "none", "pane": "wrong-pane", "agent": "codex"}[fact]
    _write(box.bin / "lanes-edit.sh", f"""#!/usr/bin/env bash
if [ "$1" = set-restart-intent ] && [ "$3" = pending ]; then
  '{real}' "$@" || exit $?
  sed 's|^{fact}: .*|{fact}: {value}|' '{intent_path(box)}' > '{intent_path(box)}.fixture'
  mv '{intent_path(box)}.fixture' '{intent_path(box)}'
  exit 0
fi
exec '{real}' "$@"
""")
    result = supervisor(box, "--restart", "--lane", LANE, "--dir", str(box.lane_dir), "clear")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "before replacing the pane" in result.stderr
    assert "respawn-pane" not in box.tmux_log.read_text()
    assert not box.claude_runs()


@pytest.mark.parametrize("finish", ["exit", "signal"])
def test_completed_observer_cleanup_never_signals_saved_pid(restart_box, finish):
    box = restart_box
    prepare_restart(box)
    shutil.copy2(REPO / "lane-handoff", box.bin / "lane-handoff")
    signals = box.root / "positive-kill.log"
    bash_env = _write(box.root / "bash-env", f"""kill() {{
  case "$1" in -0) : ;; *) printf '%s\\n' "$*" >> '{signals}' ;; esac
  builtin kill "$@"
}}
""", 0o600)
    release = box.root / "release-child"
    launcher = _write(box.fakebin / "pclaude", '''#!/usr/bin/env bash
export CLAUDE_PROFILE_NAME=test-profile
exec "$OPENREPOTOOLS_BIN_DIR/lane-start" repoZ 1
''')
    _write(box.resolved, r'''#!/usr/bin/env python3
import json, os, pathlib, time
sid=os.sys.argv[os.sys.argv.index('--session-id')+1]
pid=os.getpid()
stat=pathlib.Path(f'/proc/{pid}/stat')
start=stat.read_text().split()[21] if stat.exists() else ''
record=pathlib.Path(os.environ['HOME'])/'.claude'/'sessions'/'owned.json'
record.write_text(json.dumps(dict(pid=pid,sessionId=sid,procStart=start,cwd=os.getcwd(),
    tmux='testsess:@1.%1',name='repoZ-1',nameSource='user',status='busy'),separators=(',',':'))+'\n')
release=pathlib.Path(os.environ['OBSERVER_TEST_RELEASE'])
for _ in range(300):
    if release.exists(): break
    time.sleep(.1)
record.unlink()
''')
    box.env.update(PCLAUDE=str(launcher), LANE_SUPERVISOR_NO_PROMPT="1",
                   LANE_SUPERVISOR_READY_SECONDS="15", BASH_ENV=str(bash_env),
                   OBSERVER_TEST_RELEASE=str(release), FAKE_CC_PATH=str(box.resolved))
    unrelated = subprocess.Popen(["sleep", "60"])
    proc = subprocess.Popen([str(box.bin / "lane-handoff"), "--supervise", "--lane", LANE,
                             "--operation", "op-test"], env=box.env, cwd=box.lane_dir,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if "state: ready\n" in intent_path(box).read_text(): break
            assert proc.poll() is None
            time.sleep(.1)
        else:
            pytest.fail("observer never confirmed readiness")
        # Let the observer return while the long-lived child remains alive.
        time.sleep(.3)
        if finish == "signal":
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)
            assert (box.home / ".claude" / "sessions" / "owned.json").exists()
        release.touch()
        out, err = proc.communicate(timeout=10)
        assert proc.returncode == (143 if finish == "signal" else 0), (out, err)
        assert not signals.exists(), signals.read_text() if signals.exists() else ""
        assert unrelated.poll() is None
        assert not list(Path(box.env["TMPDIR"]).glob("lane-observer.*"))
    finally:
        release.touch()
        if proc.poll() is None:
            proc.terminate()
            proc.communicate(timeout=10)
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_signal_between_observer_fork_and_pid_publication_reaps_owned_job(restart_box):
    box = restart_box
    prepare_restart(box)
    path = box.bin / "lane-handoff"
    shutil.copy2(REPO / "lane-handoff", path)
    source = path.read_text()
    assert '\t\tsr_watch=$!' in source
    path.write_text(source.replace('\t\tsr_watch=$!', '\t\tkill -TERM "$$"\n\t\tsr_watch=$!', 1))
    result = subprocess.run([str(path), "--supervise", "--lane", LANE, "--operation", "op-test"],
                            env=box.env, cwd=box.lane_dir, capture_output=True, text=True, timeout=15)
    assert result.returncode == 143, (result.stdout, result.stderr)
    assert not box.claude_runs()
    assert not list(Path(box.env["TMPDIR"]).glob("lane-observer.*"))
    assert "state: ready\n" not in intent_path(box).read_text()


def test_new_restart_explicitly_clears_previous_operations_profile(restart_box):
    box = restart_box
    prepare_restart(box)
    assert helper(box, "set-restart-intent", LANE, "ready", "--expect", "pending").returncode == 0
    # This pane has no current account profile; a historical account is not
    # permission to select it silently for this operation.
    box.env.pop("CLAUDE_PROFILE_NAME", None)
    result = supervisor(box, "--restart", "--lane", LANE, "--dir", str(box.lane_dir), "clear")
    assert result.returncode == 0, (result.stdout, result.stderr)
    record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
    assert record["state"] == "pending"
    assert record["profile"] == "none"
    assert record["operation"] != "op-test"
    assert "respawn-pane" in box.tmux_log.read_text()


@pytest.mark.parametrize("claim", ["success", "lost"])
def test_signal_during_claim_publication_reconciles_only_owned_attempt(restart_box, claim):
    box = restart_box
    prepare_restart(box)
    before = intent_path(box).read_bytes()
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    action = f"'{real}' \"$@\"; result=$?" if claim == "success" else "result=7"
    _write(box.bin / "lanes-edit.sh", f"""#!/usr/bin/env bash
case "$*" in
  *"supervisor claimed the operation"*)
    {action}
    kill -TERM "$PPID"
    exit "$result" ;;
esac
exec '{real}' "$@"
""")
    result = supervisor(box, "--supervise", "--lane", LANE, "--operation", "op-test")
    assert result.returncode == 143, (result.stdout, result.stderr)
    assert not box.claude_runs()
    if claim == "lost":
        assert intent_path(box).read_bytes() == before
        assert "before the restart claim" in result.stdout
    else:
        record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
        assert record["state"] == "failed" and record["attempt"] == "1"
        assert record["generation"] == "7" and record["operation"] == "op-test"
        assert "no child was launched" in record["reason"]
        assert "retry:" in result.stdout


def test_handoff_target_is_resolved_after_waiting_for_writer_mutex(restart_box):
    box = restart_box
    original = prepare_restart(box)
    assert helper(box, "set-restart-intent", LANE, "ready", "--expect", "pending").returncode == 0
    other = _write(box.wip / "handoffs" / "other.md", "other preserved work\n", 0o600)
    alias = box.wip / "handoffs" / "alias.md"
    alias.symlink_to(original.name)
    prepared = _write(box.root / "prepared.md", "replacement bytes\n", 0o600)
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    before = (original.read_bytes(), other.read_bytes())
    lock = box.wip / "lanes" / ".lanes-edit.lock"
    lock.mkdir()
    (lock / "pid").write_text(str(os.getpid()) + "\n")
    marker = box.root / "waiting-for-writer"
    real_mkdir = shutil.which("mkdir")
    _write(box.fakebin / "mkdir", f"""#!/usr/bin/env bash
case "$*" in *.lanes-edit.lock*) touch '{marker}' ;; esac
exec '{real_mkdir}' "$@"
""")
    proc = subprocess.Popen([str(box.bin / "lanes-edit.sh"), "publish-handoff", LANE,
                             str(alias), str(prepared), "--expect-digest", digest],
                            env=box.env, cwd=box.lane_dir, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and time.monotonic() < deadline:
            assert proc.poll() is None
            time.sleep(.02)
        assert marker.exists()
        alias.unlink()
        alias.symlink_to(other.name)
        (lock / "pid").unlink()
        lock.rmdir()
        out, err = proc.communicate(timeout=15)
        assert proc.returncode == 7, (out, err)
        assert "changed before publication" in err
        assert (original.read_bytes(), other.read_bytes()) == before
        assert alias.is_symlink() and alias.resolve() == other
    finally:
        if lock.exists():
            (lock / "pid").unlink(missing_ok=True)
            lock.rmdir()
        if proc.poll() is None:
            proc.terminate()
            proc.communicate(timeout=5)


@pytest.mark.parametrize("kind", ["non-executable", "directory", "broken-link"])
def test_existing_unusable_managed_reader_is_not_confirmed_absence(restart_box, kind):
    box = restart_box
    reader = box.bin / "lane-managed"
    if kind == "non-executable": _write(reader, "#!/bin/sh\nexit 8\n", 0o600)
    elif kind == "directory": reader.mkdir()
    else: reader.symlink_to(box.root / "missing-reader")
    result = helper(box, "legacy-restart-check", LANE)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "reader is unusable" in result.stderr
    assert not intent_path(box).exists()


@pytest.mark.parametrize("target", ["bound", "different"])
def test_operation_publication_requires_its_bound_handoff(restart_box, target):
    box = restart_box
    bound = prepare_restart(box)
    other = _write(box.wip / "handoffs" / "different.md", bound.read_text(), 0o600)
    prepared = _write(box.root / "prepared.md", "preserved replacement\n", 0o600)
    before = (bound.read_bytes(), other.read_bytes())
    chosen = bound if target == "bound" else other
    digest = hashlib.sha256(chosen.read_bytes()).hexdigest()
    result = helper(box, "publish-handoff", LANE, str(chosen), str(prepared),
                    "--expect-digest", digest, "--operation", "op-test", "--generation", "7",
                    "--attempt", "0", "--state", "pending", "--transcript", "none")
    assert result.returncode == (0 if target == "bound" else 2), (result.stdout, result.stderr)
    if target == "different":
        assert "operation-bound handoff" in result.stderr
        assert (bound.read_bytes(), other.read_bytes()) == before
    else:
        assert bound.read_bytes() == prepared.read_bytes()
        assert other.read_bytes() == before[1]


@pytest.mark.parametrize("marker", ["published", "malformed", "local-only"])
@pytest.mark.parametrize("entry", ["check", "supervise", "start", "restart", "intent", "publish"])
def test_restart_reconcile_managed_projection_refuses_every_writer(restart_box, marker, entry):
    box = restart_box
    source = prepare_restart(box)
    # A managed service claiming absence cannot overrule the register projection.
    _write(box.bin / "lane-managed", "#!/usr/bin/env bash\nexit 8\n")
    registry = box.wip / "lanes" / "LANES.md"
    lines = registry.read_text().splitlines()
    row = next(i for i, line in enumerate(lines) if line.startswith(f"| `{LANE}`"))
    cells = lines[row].split("|")
    generation = "0" if marker == "malformed" else "4"
    cells[7] = (f" LIVE · 2026-10-05T00:00:00Z · managed-owner mode=managed "
                f"daemon=ledger-test generation={generation} bound-lane={LANE} ")
    lines[row] = "|".join(cells)
    registry.write_text("\n".join(lines) + "\n")
    if marker != "local-only":
        box.git("-C", str(box.wip), "add", "--", "lanes/LANES.md")
        box.git("-C", str(box.wip), "commit", "-qm", "publish managed projection")
        box.git("-C", str(box.wip), "push", "-q", "origin", "main")
    prepared = _write(box.root / "prepared.md", "# Changed handoff\n", 0o600)
    roots = [box.wip, Path(box.env["LANES_LANE_STATE_ROOT"]), box.home / ".claude"]

    def snapshot():
        files = {str(path): path.read_bytes() for root in roots for path in root.rglob("*")
                 if path.is_file() and ".git" not in path.parts}
        return (files, box.git("-C", str(box.wip), "rev-parse", "HEAD"),
                box.git("--git-dir", str(box.origin), "rev-parse", "main"),
                box.git("-C", str(box.wip), "status", "--porcelain"),
                box.tmux_log.read_bytes(), box.claude_log.read_bytes())

    before = snapshot()
    if entry == "check":
        result = helper(box, "legacy-restart-check", LANE)
    elif entry == "supervise":
        result = supervisor(box, "--supervise", "--lane", LANE, "--operation", "op-test")
    elif entry == "start":
        result = box.start("--operation", "op-test")
    elif entry == "restart":
        result = supervisor(box, "--restart", "--lane", LANE, "--dir", str(box.lane_dir), "clear")
    elif entry == "intent":
        result = helper(box, "set-restart-intent", LANE, "starting", "--expect", "pending")
    else:
        result = helper(box, "publish-handoff", LANE, str(source), str(prepared),
                        "--expect-digest", hashlib.sha256(source.read_bytes()).hexdigest(),
                        "--operation", "op-test", "--generation", "7", "--attempt", "0",
                        "--state", "pending", "--transcript", "none")
    assert result.returncode != 0, (result.stdout, result.stderr)
    assert "managed" in result.stderr.lower() or "UNKNOWN" in result.stderr
    assert snapshot() == before


def test_restart_reconcile_state_stores_and_counters_are_independent(restart_box):
    box = restart_box
    prepare_restart(box)
    diagnostic = intent_path(box).with_name("lane-state.yaml")
    before_diagnostic = diagnostic.read_bytes()
    for state, previous in [("starting", "pending"), ("failed", "starting")]:
        result = helper(box, "set-restart-intent", LANE, state, "--expect", previous,
                        "--expect-operation", "op-test", "--expect-generation", "7")
        assert result.returncode == 0, result.stderr
        assert diagnostic.read_bytes() == before_diagnostic
    before_restart = intent_path(box).read_bytes()
    result = helper(box, "set-lane-state", LANE, "SWAPPING", "--expect", "RUNNING",
                    "--operation", "diagnostic-only")
    assert result.returncode == 0, result.stderr
    assert intent_path(box).read_bytes() == before_restart
    restart = helper(box, "restart-intent", LANE)
    assert "operation\top-test" in restart.stdout
    assert "generation\t7" in restart.stdout
    lifecycle = helper(box, "lane-state", LANE)
    assert "operation\tdiagnostic-only" in lifecycle.stdout
    assert "generation\t7" not in lifecycle.stdout


@pytest.mark.parametrize("unknown", ["diagnostic", "restart"])
def test_restart_reconcile_unknown_schema_is_confined_to_its_store(restart_box, unknown):
    box = restart_box
    prepare_restart(box)
    diagnostic = intent_path(box).with_name("lane-state.yaml")
    affected = diagnostic if unknown == "diagnostic" else intent_path(box)
    affected.write_text(affected.read_text().replace("schema: 1", "schema: 99", 1))
    preserved = affected.read_bytes()
    if unknown == "diagnostic":
        result = helper(box, "set-restart-intent", LANE, "starting", "--expect", "pending")
        assert result.returncode == 0, result.stderr
        assert "state\tstarting" in helper(box, "restart-intent", LANE).stdout
        assert helper(box, "set-lane-state", LANE, "SWAPPING").returncode == 1
    else:
        result = helper(box, "set-lane-state", LANE, "SWAPPING", "--expect", "RUNNING")
        assert result.returncode == 0, result.stderr
        assert "state\tSWAPPING" in helper(box, "lane-state", LANE).stdout
        assert helper(box, "set-restart-intent", LANE, "starting").returncode == 2
    assert affected.read_bytes() == preserved


def test_restart_reconcile_case_only_rename_preserves_completed_history(restart_box):
    box = restart_box
    prepare_restart(box)
    assert helper(box, "set-restart-intent", LANE, "ready", "--expect", "pending").returncode == 0
    roots = [box.wip, intent_path(box).parent]
    before = {str(p): p.read_bytes() for root in roots for p in root.rglob("*")
              if p.is_file() and ".git" not in p.parts}
    commit = box.git("-C", str(box.wip), "rev-parse", "HEAD")
    box.env["LANES_SESSION"] = "10101010-1111-4111-8111-111111111111"
    result = helper(box, "rename-lane", LANE, LANE.lower(), "--no-github")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "SPELLING" in result.stderr
    assert {str(p): p.read_bytes() for root in roots for p in root.rglob("*")
            if p.is_file() and ".git" not in p.parts} == before
    assert box.git("-C", str(box.wip), "rev-parse", "HEAD") == commit
    assert "state\tready" in helper(box, "restart-intent", LANE).stdout


def restart_root_without_recorded_checkout(box):
    source = prepare_restart(box)
    box.restart_root_seed = intent_path(box).read_bytes()
    intent_path(box).unlink()
    old_dir = box.lane_dir
    log = box.wip / "lanes" / "log" / f"{LANE}.md"
    log.write_text(log.read_text().replace(f"; dir {old_dir}", ""))
    box.git("-C", str(box.wip), "add", "--", str(log))
    box.git("-C", str(box.wip), "commit", "-qm", "legacy record without checkout")
    box.git("-C", str(box.wip), "push", "-q", "origin", "main")
    box.env.pop("LANES_LANE_STATE_ROOT")
    box.env["PROJECTS_ROOT"] = str(old_dir.parent)
    nested = old_dir.parent / "nested" / "repoZ"
    nested.mkdir(parents=True)
    box.git("init", "-q", "-b", "main", str(nested))
    box.git("-C", str(nested), "remote", "add", "origin", "https://github.com/opensoft/repoZ.git")
    box.lane_dir = nested
    assert helper(box, "lane-dir", LANE).returncode == 8
    fallback = old_dir.parent / ".lane-state" / LANE / "restart-intent.yaml"
    alternate = nested.parent / ".lane-state" / LANE / "restart-intent.yaml"
    return source, fallback, alternate


def record_nested_restart_checkout(box):
    prior = box.env
    session = helper(box, "last-session", LANE).stdout.strip()
    box.env = dict(prior, LANES_LANE=LANE, LANES_SESSION=session)
    try:
        result = helper(box, "log", "PAUSED", f"lane:{LANE}", "→", f"swap; dir {box.lane_dir}", "fixture")
    finally:
        box.env = prior
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_restart_root_retains_reservation_after_nested_checkout_preservation(restart_box):
    box = restart_box
    source, fallback, alternate = restart_root_without_recorded_checkout(box)
    result = supervisor(box, "--restart", "--lane", LANE, "--dir", str(box.lane_dir), "clear")
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "respawn-pane" in box.tmux_log.read_text()
    assert not alternate.exists()
    record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
    assert record["state"] == "pending" and record["file"] == str(fallback)
    assert record["dir"] == str(box.lane_dir) and record["handoff"] == str(source)
    status = supervisor(box, "--restart-status", "--lane", LANE)
    assert status.returncode == 0 and "intent      pending" in status.stdout
    before = fallback.read_bytes()
    result = box.start("--dir", str(box.lane_dir))
    assert result.returncode == 2 and "supervisor operation token" in result.stderr
    assert fallback.read_bytes() == before and not box.claude_runs()


def test_restart_root_cleanup_after_paused_fails_original_reservation(restart_box):
    box = restart_box
    _, fallback, alternate = restart_root_without_recorded_checkout(box)
    real = box.bin / "lanes-edit-real.sh"
    (box.bin / "lanes-edit.sh").rename(real)
    _write(box.bin / "lanes-edit.sh", f"""#!/usr/bin/env bash
if [ "$1" = set-restart-intent ] && [ "$3" = pending ]; then exit 1; fi
exec '{real}' "$@"
""")
    result = supervisor(box, "--restart", "--lane", LANE, "--dir", str(box.lane_dir), "clear")
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "PAUSED" in box.lane_log() and "respawn-pane" not in box.tmux_log.read_text()
    assert not alternate.exists()
    record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
    assert record["file"] == str(fallback) and record["state"] == "failed"
    assert record["mode"] == "preservation-only" and record["attempt"] == "0"


@pytest.mark.parametrize("entry", ["read", "write", "start", "rename"])
def test_restart_root_conflicts_refuse_without_changing_either_intent(restart_box, entry):
    box = restart_box
    _, fallback, alternate = restart_root_without_recorded_checkout(box)
    assert helper(box, "set-restart-intent", LANE, "preparing", "--expect", "none", "--operation", "held").returncode == 0
    record_nested_restart_checkout(box)
    alternate.parent.mkdir(parents=True, exist_ok=True)
    alternate.write_bytes(fallback.read_bytes())  # identical bytes are separate authority
    before = {p: p.read_bytes() for p in [fallback, alternate, box.wip / "lanes" / "LANES.md"]}
    box.resolver()
    if entry == "read":
        result = helper(box, "restart-intent", LANE)
    elif entry == "write":
        result = helper(box, "set-restart-intent", LANE, "failed", "--expect", "preparing")
    elif entry == "rename":
        result = helper(box, "rename-lane", LANE, "repoZ-2")
    else:
        result = box.start("--dir", str(box.lane_dir))
    assert result.returncode != 0, (result.stdout, result.stderr)
    assert all(p.read_bytes() == contents for p, contents in before.items())
    assert not box.claude_runs() and "respawn-pane" not in box.tmux_log.read_text()


@pytest.mark.parametrize("alias", ["lane-root", "state-root"])
def test_restart_root_directory_aliases_preserve_one_authority_across_replacement(restart_box, alias):
    box = restart_box
    _, fallback, alternate = restart_root_without_recorded_checkout(box)
    assert helper(box, "set-restart-intent", LANE, "preparing", "--expect", "none", "--operation", "held").returncode == 0
    record_nested_restart_checkout(box)
    target = alternate.parent if alias == "lane-root" else alternate.parent.parent
    # Move any independent diagnostic snapshot aside in this fixture before
    # making the alias. Restart selection must not mutate diagnostic files.
    if target.exists():
        target.rename(box.root / "pre-alias-diagnostics")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(fallback.parent if alias == "lane-root" else fallback.parent.parent, target_is_directory=True)
    result = helper(box, "set-restart-intent", LANE, "failed", "--expect", "preparing", "--expect-operation", "held")
    assert result.returncode == 0, (result.stdout, result.stderr)
    record = helper(box, "restart-intent", LANE)
    assert record.returncode == 0 and "operation\theld" in record.stdout
    assert "state\tfailed" in record.stdout
    assert alternate.resolve() == fallback.resolve()
    assert alternate.read_bytes() == fallback.read_bytes()


@pytest.mark.parametrize("alias", ["symlink", "hardlink"])
def test_restart_root_distinct_file_aliases_refuse_before_atomic_replacement(restart_box, alias):
    box = restart_box
    _, fallback, alternate = restart_root_without_recorded_checkout(box)
    assert helper(box, "set-restart-intent", LANE, "preparing", "--expect", "none", "--operation", "held").returncode == 0
    record_nested_restart_checkout(box)
    alternate.parent.mkdir(parents=True, exist_ok=True)
    if alias == "symlink":
        alternate.symlink_to(fallback)
    else:
        os.link(fallback, alternate)
    before = fallback.read_bytes()
    assert helper(box, "restart-intent", LANE).returncode == 1
    result = helper(box, "set-restart-intent", LANE, "failed", "--expect", "preparing")
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert alternate.read_bytes() == fallback.read_bytes() == before


@pytest.mark.parametrize("kind", ["malformed", "directory", "broken-link", "unusable-parent"])
def test_restart_root_does_not_hide_unusable_fallback_after_checkout_is_recorded(restart_box, kind):
    box = restart_box
    _, fallback, alternate = restart_root_without_recorded_checkout(box)
    fallback.parent.mkdir(parents=True, exist_ok=True)
    if kind == "malformed":
        fallback.write_text("schema: 1\nstate: pending\n")
    elif kind == "directory":
        fallback.mkdir()
    elif kind == "broken-link":
        fallback.symlink_to(box.root / "missing-intent")
    else:
        fallback.parent.rmdir()
        fallback.parent.write_text("not a directory\n")
    record_nested_restart_checkout(box)
    read = helper(box, "restart-intent", LANE)
    assert read.returncode != 8, (read.stdout, read.stderr)
    if kind == "malformed":
        assert read.returncode == 0 and "INCOMPLETE" in read.stdout
    else:
        assert read.returncode == 1, (read.stdout, read.stderr)
    result = helper(box, "set-restart-intent", LANE, "preparing", "--expect", "none", "--operation", "other")
    assert result.returncode != 0, (result.stdout, result.stderr)
    assert not alternate.exists()


def test_restart_root_waiting_writer_discovers_new_authority_under_mutex(restart_box):
    box = restart_box
    _, fallback, alternate = restart_root_without_recorded_checkout(box)
    record_nested_restart_checkout(box)
    lock = box.wip / "lanes" / ".lanes-edit.lock"
    lock.mkdir()
    (lock / "pid").write_text(str(os.getpid()))
    waited = box.root / "writer.waited"
    sleep = shutil.which("sleep")
    _write(box.fakebin / "sleep", f"""#!/usr/bin/env bash
: > '{waited}'
exec '{sleep}' "$@"
""")
    process = subprocess.Popen([str(box.bin / "lanes-edit.sh"), "set-restart-intent", LANE,
                                "preparing", "--expect", "none", "--operation", "waiting"],
                               cwd=box.lane_dir, env=box.env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 15
        while not waited.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        assert waited.exists()
        # Another writer establishes a valid fallback before this waiter owns
        # the mutex. It must discover that authority instead of creating nested.
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_bytes(box.restart_root_seed)
        before = fallback.read_bytes()
        lock.joinpath("pid").unlink()
        lock.rmdir()
        out = process.communicate(timeout=15)
        assert process.returncode == 7, out
        assert fallback.read_bytes() == before and not alternate.exists()
    finally:
        if lock.exists():
            lock.joinpath("pid").unlink(missing_ok=True)
            lock.rmdir()
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


@pytest.mark.parametrize("kind", ["file", "broken-link"])
def test_restart_root_unusable_configured_parent_cannot_disappear_from_selection(restart_box, kind):
    box = restart_box
    _, fallback, alternate = restart_root_without_recorded_checkout(box)
    record_nested_restart_checkout(box)
    bad = box.root / "unusable-projects"
    if kind == "file":
        bad.write_text("not a directory\n")
    else:
        bad.symlink_to(box.root / "missing-projects")
    box.env["PROJECTS_ROOT"] = str(bad)
    assert helper(box, "restart-intent", LANE).returncode == 1
    result = helper(box, "set-restart-intent", LANE, "preparing", "--expect", "none", "--operation", "other")
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert not alternate.exists() and not fallback.exists()


@pytest.mark.parametrize("candidate", ["recorded", "projects"])
def test_restart_root_unsearchable_parent_ancestry_is_unknown_not_absent(restart_box, candidate):
    if os.geteuid() == 0:
        pytest.skip("permission regression requires an unprivileged runner")
    box = restart_box
    _, fallback, alternate = restart_root_without_recorded_checkout(box)
    assert helper(box, "set-restart-intent", LANE, "preparing", "--expect", "none", "--operation", "held").returncode == 0
    record_nested_restart_checkout(box)
    before = fallback.read_bytes()
    if candidate == "recorded":
        blocked = box.lane_dir.parent
        box.lane_dir = Path(box.env["PROJECTS_ROOT"]) / "repoZ"  # accessible caller cwd
    else:
        blocked = box.root / "blocked"
        root = blocked / "projects"
        root.mkdir(parents=True)
        box.env["PROJECTS_ROOT"] = str(root)
    blocked.chmod(0)
    try:
        assert helper(box, "restart-intent", LANE).returncode == 1
        result = helper(box, "set-restart-intent", LANE, "failed", "--expect", "preparing")
        assert result.returncode == 1, (result.stdout, result.stderr)
    finally:
        blocked.chmod(0o755)
    assert fallback.read_bytes() == before and not alternate.exists()
