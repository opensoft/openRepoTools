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


@pytest.fixture
def restart_box(tmp_path: Path) -> Sandbox:
    box = Sandbox(tmp_path)
    box.env["LANES_LANE_STATE_ROOT"] = str(tmp_path / "state")
    box.env["LANES_NO_FETCH"] = "1"
    box.env["TMUX_PANE"] = "%1"
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
    output_path = box.root / "interactive.out"
    with output_path.open("w") as output:
        proc = subprocess.Popen([str(box.bin / "lane-handoff"), "--supervise", "--lane", LANE,
                                 "--operation", "op-test"], cwd=box.lane_dir, env=box.env,
                                stdin=slave, stdout=output, stderr=output, start_new_session=True)
        os.close(slave)
        try:
            deadline = time.monotonic() + 15
            while "retry this restart?" not in output_path.read_text() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            assert "retry this restart?" in output_path.read_text(), output_path.read_text()
            os.write(master, b"r\n")
            assert proc.wait(timeout=15) == 4, output_path.read_text()
            assert launches.read_text().splitlines() == ["launch"]
            record = dict(line.split("\t", 1) for line in helper(box, "restart-intent", LANE).stdout.splitlines())
            assert record["state"] == "starting" and record["attempt"] == "2"
            assert "before attempt launch" in record["reason"]
        finally:
            os.close(master)
            try: os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            if proc.poll() is None: proc.wait(timeout=10)


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
    box.env.update(PCLAUDE=str(child), LANE_SUPERVISOR_NO_PROMPT="1", TMUX_PANE="%1")
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
