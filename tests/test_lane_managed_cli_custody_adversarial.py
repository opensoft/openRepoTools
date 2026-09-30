# SPDX-License-Identifier: Apache-2.0
"""Real Linux custody failures that a PID or process-group scan could miss."""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from types import SimpleNamespace
import uuid

import pytest

import lane_managed_cli_source as source_module
from lane_managed_cli_source import (
    SharedParentRegistry, SourceCustodianLauncher, SourceCustodyError, request,
)


pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper contract")


@pytest.fixture
def short_root():
    # AF_UNIX socket names are short even when pytest's test name is long.
    with tempfile.TemporaryDirectory(prefix="lc-custody-") as directory:
        yield Path(directory)


def _until(predicate, timeout=6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.02)
    raise AssertionError("bounded custodian observation timed out")


def _stop_owned_wrapper(identity):
    """Reap only the test's direct child, with no process-group signaling."""
    if not identity:
        return
    pid = identity["pid"]
    try:
        ended, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return
    if ended:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        os.waitpid(pid, 0)
        return
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            ended, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return
        if ended:
            return
        time.sleep(0.02)
    # A stuck child is still ours, and remains unreaped so its PID cannot be reused.
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)


def _fixture_identity(directory, known):
    if known:
        return known
    for name, key in (("launch.json", "custodian"),
                      ("custodian.json", "custodian")):
        try:
            candidate = json.loads((directory / name).read_text()).get(key)
            if isinstance(candidate, dict) and isinstance(candidate.get("pid"), int):
                return candidate
        except (OSError, ValueError):
            pass
    return None


def _launch(directory, tmp_path, argv):
    launcher = SourceCustodianLauncher(str(directory))
    answer = launcher.launch(
        argv=argv, environment=dict(os.environ), cwd=str(tmp_path),
        intent={"digest": "a" * 64}, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return launcher, answer


_CLONE_SOURCE = r"""
#define _GNU_SOURCE
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>

static const char *release_file;
static const char *finished_file;
static int ready_read_fd;
static int ready_write_fd;

static int child(void *unused) {
    close(ready_read_fd);
    if (setsid() < 0) _exit(96);
    if (write(ready_write_fd, "1", 1) != 1) _exit(97);
    close(ready_write_fd);
    struct timespec pause = {0, 10000000};
    for (int i = 0; i < 500 && access(release_file, F_OK) != 0; ++i)
        nanosleep(&pause, NULL);
    FILE *out = fopen(finished_file, "w");
    if (!out) _exit(91);
    fputs("clone-finished\n", out);
    fclose(out);
    _exit(0);
}

int main(int argc, char **argv) {
    if (argc != 4) return 92;
    release_file = argv[1];
    finished_file = argv[2];
    void *stack = malloc(65536);
    if (!stack) return 93;
    int ready_pipe[2];
    if (pipe(ready_pipe) != 0) return 94;
    ready_read_fd = ready_pipe[0];
    ready_write_fd = ready_pipe[1];
    // Exit signal zero: ordinary SIGCHLD-only waitpid cannot reap this child.
    int pid = clone(child, (char *)stack + 65536, 0, NULL);
    if (pid < 0) return 95;
    close(ready_write_fd);
    char ready;
    if (read(ready_read_fd, &ready, 1) != 1 || ready != '1') return 96;
    close(ready_read_fd);
    FILE *out = fopen(argv[3], "w");
    if (!out) return 97;
    fprintf(out, "%d\n", pid);
    fclose(out);
    return 0;
}
"""


def test_non_sigchld_clone_keeps_source_open_until_all_wall_reap(short_root):
    tmp_path = short_root
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        pytest.skip("C compiler unavailable for real non-SIGCHLD clone fixture")
    fixture_source = tmp_path / "clone.c"
    executable = tmp_path / "clone"
    fixture_source.write_text(_CLONE_SOURCE)
    subprocess.run([compiler, "-O0", "-o", str(executable), str(fixture_source)],
                   check=True, capture_output=True, timeout=15)
    release = tmp_path / "release"
    finished = tmp_path / "finished"
    clone_pid_file = tmp_path / "clone-pid"
    identity = None
    try:
        launcher, started = _launch(
            tmp_path / "custodian", tmp_path,
            [str(executable), str(release), str(finished), str(clone_pid_file)],
        )
        identity = started["custodian"]
        exited = _until(lambda: (
            value if (value := launcher.challenge())["source_exit"] else None
        ))
        clone_pid = int(clone_pid_file.read_text())
        assert exited["source_exit"]["exited"] is True
        assert exited["drained"] is False
        assert not finished.exists()

        release.touch()
        drained = _until(lambda: (
            value if (value := launcher.challenge())["drained"] else None
        ))
        assert drained["phase"] == "drained"
        assert finished.read_text() == "clone-finished\n"
        journal = json.loads((tmp_path / "custodian" / "custodian.json").read_text())
        assert any(event["pid"] == clone_pid and event["exited"]
                   for event in journal["events"])
    finally:
        release.touch()
        if identity:
            try:
                _until(lambda: launcher.challenge()["drained"], timeout=5.5)
            except (AssertionError, SourceCustodyError, OSError):
                pass
        _stop_owned_wrapper(_fixture_identity(tmp_path / "custodian", identity))


def test_nested_subreaper_and_setsid_leaf_remain_in_source_closure(short_root):
    tmp_path = short_root
    nested_release = tmp_path / "nested-release"
    leaf_release = tmp_path / "leaf-release"
    nested_ready = tmp_path / "nested-ready"
    leaf_ready = tmp_path / "leaf-ready"
    nested_pid_file = tmp_path / "nested-pid"
    finished = tmp_path / "leaf-finished"
    program = textwrap.dedent("""
        import ctypes, os, pathlib, sys, time
        nested_release, leaf_release, nested_ready, leaf_ready, nested_pid_file, finished = (
            pathlib.Path(item) for item in sys.argv[1:])
        def wait_for(path):
            deadline = time.monotonic() + 5
            while not path.exists() and time.monotonic() < deadline:
                time.sleep(.01)
        nested = os.fork()
        if nested:
            nested_pid_file.write_text(str(nested))
            wait_for(nested_ready)
            wait_for(leaf_ready)
            if not nested_ready.exists() or not leaf_ready.exists():
                os._exit(97)
            os._exit(0)
        os.setsid()
        if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:
            os._exit(96)
        middle = os.fork()
        if middle == 0:
            leaf = os.fork()
            if leaf == 0:
                os.setsid()
                leaf_ready.touch()
                wait_for(leaf_release)
                finished.write_text('leaf-finished')
                os._exit(0)
            os._exit(0)
        os.waitpid(middle, 0)
        nested_ready.touch()
        wait_for(nested_release)
        os._exit(0)
    """)
    directory = tmp_path / "custodian"
    identity = None
    try:
        launcher, started = _launch(
            directory, tmp_path,
            [sys.executable, "-c", program, str(nested_release),
             str(leaf_release), str(nested_ready), str(leaf_ready),
             str(nested_pid_file), str(finished)],
        )
        identity = started["custodian"]
        _until(lambda: nested_ready.exists() and leaf_ready.exists())
        exited = _until(lambda: (
            value if (value := launcher.challenge())["source_exit"] else None
        ))
        assert exited["drained"] is False

        nested_release.touch()
        nested_pid = int(nested_pid_file.read_text())
        _until(lambda: any(event["pid"] == nested_pid for event in json.loads(
            (directory / "custodian.json").read_text())["events"]))
        assert launcher.challenge()["drained"] is False
        assert not finished.exists()

        leaf_release.touch()
        assert _until(lambda: launcher.challenge()["drained"])
        assert finished.read_text() == "leaf-finished"
    finally:
        nested_release.touch()
        leaf_release.touch()
        if identity:
            try:
                _until(lambda: launcher.challenge()["drained"], timeout=5.5)
            except (AssertionError, SourceCustodyError, OSError):
                pass
        _stop_owned_wrapper(_fixture_identity(directory, identity))


@pytest.mark.parametrize("damage", [
    "missing-launch", "changed-launch", "missing-custodian", "changed-custodian",
])
def test_lost_or_changed_journal_cannot_attest_prior_drain(short_root, damage):
    tmp_path = short_root
    directory = tmp_path / "custodian"
    identity = None
    try:
        launcher, started = _launch(
            directory, tmp_path, [sys.executable, "-c", "pass"],
        )
        identity = started["custodian"]
        assert _until(lambda: launcher.challenge()["drained"])
        journal = directory / ("launch.json" if "launch" in damage else "custodian.json")
        if damage.startswith("missing"):
            journal.unlink()
        else:
            journal.write_text('{"changed":true}\n')
        with pytest.raises(SourceCustodyError):
            SourceCustodianLauncher(str(directory)).challenge()
    finally:
        _stop_owned_wrapper(_fixture_identity(directory, identity))


def test_dead_original_wrapper_cannot_be_replaced_for_positive_challenge(short_root):
    tmp_path = short_root
    directory = tmp_path / "custodian"
    identity = None
    try:
        launcher, started = _launch(
            directory, tmp_path, [sys.executable, "-c", "pass"],
        )
        identity = started["custodian"]
        assert _until(lambda: launcher.challenge()["drained"])
        _stop_owned_wrapper(identity)
        identity = None
        with pytest.raises(SourceCustodyError):
            SourceCustodianLauncher(str(directory)).challenge()
        with pytest.raises(SourceCustodyError, match="already exists"):
            _launch(directory, tmp_path, [sys.executable, "-c", "pass"])
    finally:
        _stop_owned_wrapper(_fixture_identity(directory, identity))


def test_replayed_challenge_from_live_wrapper_is_not_fresh(short_root, monkeypatch):
    directory = short_root / "custodian"
    identity = None
    try:
        launcher, started = _launch(
            directory, short_root, [sys.executable, "-c", "pass"],
        )
        identity = started["custodian"]
        assert _until(lambda: launcher.challenge()["drained"])
        credential = (directory / "credential").read_text()
        old_answer = request(directory, credential, "challenge", nonce=uuid.uuid4().hex)
        real_request = source_module.request

        def replay(*args, **kwargs):
            if args[2] == "challenge":
                return old_answer
            return real_request(*args, **kwargs)

        monkeypatch.setattr(source_module, "request", replay)
        with pytest.raises(SourceCustodyError, match="differs"):
            launcher.challenge()
    finally:
        _stop_owned_wrapper(_fixture_identity(directory, identity))


def test_lost_start_ack_retains_admission_and_never_spawns_again(short_root, monkeypatch):
    tmp_path = short_root
    directory = tmp_path / "custodian"
    marker = tmp_path / "executions"
    code = ("from pathlib import Path; import time; "
            "p=Path(%r); p.open('a').write('executed\\n'); time.sleep(.3)" % str(marker))
    real_request = source_module.request
    identity = None

    def lose_start_ack(*args, **kwargs):
        answer = real_request(*args, **kwargs)
        if args[2] == "start":
            raise SourceCustodyError("simulated lost start acknowledgment")
        return answer

    monkeypatch.setattr(source_module, "request", lose_start_ack)
    try:
        with pytest.raises(SourceCustodyError, match="lost start acknowledgment"):
            _launch(directory, tmp_path, [sys.executable, "-c", code])
        # The process was admitted before the reply disappeared. A retry of
        # either the launcher or the wrapper start must not launch it twice.
        launch = json.loads((directory / "launch.json").read_text())
        assert launch["phase"] == "custodian-ready"
        identity = launch["custodian"]
        credential = (directory / "credential").read_text()
        monkeypatch.setattr(source_module, "request", real_request)
        assert _until(lambda: real_request(
            directory, credential, "challenge", nonce=uuid.uuid4().hex
        )["drained"])
        assert marker.read_text() == "executed\n"
        with pytest.raises(SourceCustodyError, match="already exists"):
            _launch(directory, tmp_path, [sys.executable, "-c", code])
        with pytest.raises(SourceCustodyError, match="already consumed"):
            request(directory, credential, "start", argv=[sys.executable],
                    environment={}, cwd=str(tmp_path), intent={"digest": "b" * 64})
        assert marker.read_text() == "executed\n"
    finally:
        _stop_owned_wrapper(_fixture_identity(directory, identity))


_CLAIM_SCRIPT = """
import json, pathlib, sys, time, uuid
from lane_managed_cli_source import SharedParentRegistry, SourceCustodyError
root, history, parent, lane, ready, gate = sys.argv[1:]
pathlib.Path(ready).touch()
deadline = time.monotonic() + 5
while not pathlib.Path(gate).exists() and time.monotonic() < deadline:
    time.sleep(.005)
try:
    result = SharedParentRegistry(root).claim_source(
        history_store=history, parent_uuid=parent, lane=lane, generation=1,
        runtime_id=str(uuid.uuid4()), manifest_digest='a' * 64)
    print(json.dumps({'claimed': True, 'lane': result['lane']}))
except SourceCustodyError as exc:
    print(json.dumps({'claimed': False, 'error': str(exc)}))
"""


_CLAIM_AND_SPAWN_SCRIPT = """
import json, pathlib, sys, uuid
from lane_managed_cli_source import SharedParentRegistry, SourceCustodyError
root, history, parent, lane, spawn_log = sys.argv[1:]
try:
    result = SharedParentRegistry(root).claim_source(
        history_store=history, parent_uuid=parent, lane=lane, generation=1,
        runtime_id=str(uuid.uuid4()), manifest_digest='a' * 64)
    with pathlib.Path(spawn_log).open('a') as output:
        output.write(result['lane'] + '\\n')
    print(json.dumps({'claimed': True, 'lane': result['lane']}))
except SourceCustodyError as exc:
    print(json.dumps({'claimed': False, 'error': str(exc)}))
"""


def _subprocess_claim_and_spawn(root, history, parent, lane, spawn_log, repo_root):
    env = dict(os.environ)
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run(
        [sys.executable, "-c", _CLAIM_AND_SPAWN_SCRIPT, str(root), str(history),
         parent, lane, str(spawn_log)],
        env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=8, check=False,
    )
    assert process.returncode == 0, process.stderr.decode(errors="replace")
    return json.loads(process.stdout)


def test_competing_processes_share_one_exact_parent_claim(tmp_path):
    root = tmp_path / "registry"
    root.mkdir(mode=0o700)
    history = tmp_path / "history"
    history.mkdir()
    gate = tmp_path / "go"
    parent = str(uuid.uuid4())
    repo_root = str(Path(__file__).resolve().parents[1])
    env = dict(os.environ)
    env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    contenders = []
    try:
        for number in range(4):
            ready = tmp_path / ("ready-%d" % number)
            process = subprocess.Popen(
                [sys.executable, "-c", _CLAIM_SCRIPT, str(root), str(history),
                 parent, "lane-%d" % number, str(ready), str(gate)],
                env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            contenders.append((process, ready))
        _until(lambda: all(ready.exists() for _, ready in contenders))
        gate.touch()
        answers = []
        for process, _ in contenders:
            stdout, stderr = process.communicate(timeout=8)
            assert process.returncode == 0, stderr.decode(errors="replace")
            answers.append(json.loads(stdout))
        winners = [answer for answer in answers if answer["claimed"]]
        assert len(winners) == 1
        assert all("already has" in answer["error"] for answer in answers
                   if not answer["claimed"])
        stored = SharedParentRegistry(str(root)).status(
            history_store=str(history), parent_uuid=parent,
        )
        assert stored["lane"] == winners[0]["lane"]
        assert stored["phase"] == "source-intent"
    finally:
        gate.touch()
        for process, _ in contenders:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)


def test_shared_parent_registry_initializes_once_and_reopens_with_same_identity(tmp_path):
    root = tmp_path / "registry"
    root.mkdir(mode=0o700)

    assert SharedParentRegistry(str(root)).status(
        history_store=str(tmp_path), parent_uuid=str(uuid.uuid4()),
    ) is None
    identity = json.loads((root / "parents.identity").read_text())
    registry = json.loads((root / "parents.json").read_text())
    assert identity["registry_id"] == registry["registry_id"]
    assert registry["entries"] == {}

    assert SharedParentRegistry(str(root)).status(
        history_store=str(tmp_path), parent_uuid=str(uuid.uuid4()),
    ) is None
    reopened = json.loads((root / "parents.identity").read_text())
    assert reopened["registry_id"] == identity["registry_id"]


def test_initial_identity_migration_preserves_legacy_claims(tmp_path):
    root = tmp_path / "registry"
    root.mkdir(mode=0o700)
    history = tmp_path / "history"
    history.mkdir()
    parent = str(uuid.uuid4())
    original = SharedParentRegistry(str(root)).claim_source(
        history_store=str(history), parent_uuid=parent, lane="lane-a",
        generation=1, runtime_id=str(uuid.uuid4()), manifest_digest="a" * 64,
    )
    data = json.loads((root / "parents.json").read_text())
    source_module._write_durable(root / "parents.json", {
        "schema": 1, "entries": data["entries"],
    })
    (root / "parents.identity").unlink()

    reopened = SharedParentRegistry(str(root))
    assert reopened.status(history_store=str(history), parent_uuid=parent) == original
    with pytest.raises(SourceCustodyError, match="already has"):
        reopened.claim_source(
            history_store=str(history), parent_uuid=parent, lane="lane-c",
            generation=1, runtime_id=str(uuid.uuid4()), manifest_digest="b" * 64,
        )


def test_registry_loss_in_another_process_blocks_second_claim_and_spawn(tmp_path):
    root = tmp_path / "registry"
    root.mkdir(mode=0o700)
    history = tmp_path / "history"
    history.mkdir()
    parent = str(uuid.uuid4())
    spawn_log = tmp_path / "spawn-log"
    repo_root = str(Path(__file__).resolve().parents[1])

    first = _subprocess_claim_and_spawn(
        root, history, parent, "lane-a", spawn_log, repo_root,
    )
    assert first == {"claimed": True, "lane": "lane-a"}
    registry_id = json.loads((root / "parents.identity").read_text())["registry_id"]
    (root / "parents.json").unlink()

    second = _subprocess_claim_and_spawn(
        root, history, parent, "lane-c", spawn_log, repo_root,
    )
    assert second["claimed"] is False
    assert "missing after initialization" in second["error"]
    assert spawn_log.read_text().splitlines() == ["lane-a"]
    assert json.loads((root / "parents.identity").read_text())["registry_id"] == registry_id


@pytest.mark.parametrize("damage", ["truncated", "digest"])
def test_registry_corruption_after_initialization_fails_closed(tmp_path, damage):
    root = tmp_path / "registry"
    root.mkdir(mode=0o700)
    history = tmp_path / "history"
    history.mkdir()
    parent = str(uuid.uuid4())
    registry = SharedParentRegistry(str(root))
    registry.claim_source(
        history_store=str(history), parent_uuid=parent, lane="lane-a",
        generation=1, runtime_id=str(uuid.uuid4()), manifest_digest="a" * 64,
    )

    if damage == "truncated":
        (root / "parents.json").write_text("{truncated")
    else:
        changed = json.loads((root / "parents.json").read_text())
        changed["entries"] = {}
        (root / "parents.json").write_text(json.dumps(changed))
        (root / "parents.json").chmod(0o600)
    with pytest.raises(SourceCustodyError):
        SharedParentRegistry(str(root)).status(
            history_store=str(history), parent_uuid=parent,
        )


def test_shared_source_exclusion_digest_binds_each_fresh_challenge_nonce(
        tmp_path, monkeypatch):
    parent = str(uuid.uuid4())
    custodian = {"pid": 101, "start_token": "custodian"}
    source = {"pid": 102, "start_token": "source"}
    operation_id = "operation-a"
    admission = {
        "runtime_id": "runtime-a", "parent_uuid": parent,
        "claim_generation": 7, "history_store": str(tmp_path),
        "custodian_dir": str(tmp_path / "custodian"), "custodian": custodian,
        "source": source, "integrity_digest": "a" * 64,
        "source_domain_id": "domain-a", "supervisor_incarnation": "supervisor-a",
    }
    operation = {
        "source_runtime_incarnation": admission["runtime_id"],
        "source_claim_generation": admission["claim_generation"],
        "parent_uuid": parent, "source_restart_denied": True,
        "operation_id": operation_id,
    }
    ledger_snapshot = {
        "operations": {operation_id: operation}, "retired_source_generations": [7],
        "observation_watermark": 20,
    }
    registered = {
        "lane": "lane-a", "runtime_id": admission["runtime_id"],
        "phase": "source-running", "custodian_identity": custodian,
        "source_identity": source,
    }
    provider = object.__new__(source_module.SharedSessionSourceProvider)
    provider.ledger = SimpleNamespace(
        status=lambda: ledger_snapshot,
        store=SimpleNamespace(identity=SimpleNamespace(lane="lane-a")),
    )
    provider.registry = SimpleNamespace(status=lambda **_kwargs: registered)
    provider.job_provider = SimpleNamespace(assert_ready=lambda: None)
    provider.next_watermark = lambda watermark: watermark + 1
    provider._matching_admission = lambda _binding: admission
    provider._launch_manifest = lambda _admission: {}

    launch_intent = {
        "runtime_id": admission["runtime_id"], "parent_uuid": parent,
        "operation_id": operation_id,
    }
    answers = []
    for nonce in ("1" * 32, "2" * 32):
        answers.append({
            "nonce": nonce, "custodian": custodian, "source": source,
            "source_exit": {"exited": True, "status": 0},
            "launch_intent": launch_intent, "subreaper": True, "drained": True,
            "phase": "drained", "sequence": 11, "journal_digest": "b" * 64,
        })
    monkeypatch.setattr(SourceCustodianLauncher, "challenge",
                        lambda _self: answers.pop(0))

    first = provider.source_exclusion({})
    second = provider.source_exclusion({})
    assert first["witness_digest"] != second["witness_digest"]
