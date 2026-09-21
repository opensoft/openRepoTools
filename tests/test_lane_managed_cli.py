# SPDX-License-Identifier: Apache-2.0
"""Fake-only tests for the bounded ``lane-managed`` control boundary.

T013 deliberately tests the command/parser and local transport boundary only.
The handler injected into these tests is a tiny dictionary-returning fake; no
controller, SDK, Claude account, authentication, daemon, or network service
is exercised here.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import io
import json
import os
import runpy
import shutil
import socket
import stat
import subprocess
import threading
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "lane-managed"
LANE_SWAP = REPO / "lane-swap"
OPENREPOTOOLS = REPO / "openRepoTools"

OPERATIONS = (
    "start",
    "status",
    "submit",
    "swap",
    "recover",
    "release",
    "shutdown",
    "unenroll",
)


def _load_cli() -> dict:
    """Load the executable as a module without triggering its CLI entrypoint."""
    namespace = runpy.run_path(str(SCRIPT), run_name="lane_managed_cli_test")
    # ``runpy.run_path`` returns a shallow copy of the execution namespace on
    # this interpreter, while function globals retain the original mapping.
    # Use that authoritative mapping so test-only monkeypatches of the socket,
    # clock, or injected handler seam are actually observed by loaded code.
    return namespace["main"].__globals__


def _request(operation: str = "status", *, request_id: str = "req-1",
             generation=7, **body) -> dict:
    """Build the wire envelope required by ``managed-control.md``."""
    return {
        "schema": 2,
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "request_id": request_id,
        "lane": "build",
        "generation": generation,
        "operation": operation,
        "body": body,
    }


def _wait_for_path(path: Path, thread: threading.Thread, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    while not path.exists() and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert path.exists(), "serve_once did not create its Unix socket"


def _start_server(api: dict, socket_path: Path, handler, *,
                  serve_name: str = "serve_once", **kwargs):
    """Start one injected-handler server and wait until its socket is live."""
    errors = []
    result = []

    def run():
        try:
            result.append(api[serve_name](str(socket_path), handler, **kwargs))
        except BaseException as exc:  # make a child failure visible to pytest
            errors.append(exc)

    thread = threading.Thread(target=run, name="lane-managed-test-server")
    thread.daemon = True
    thread.start()
    _wait_for_path(socket_path, thread)
    return thread, errors, result


def _join_server(thread: threading.Thread, errors: list):
    thread.join(timeout=2.0)
    assert not thread.is_alive(), "serve_once did not finish one request"
    assert not errors, "serve_once raised: %r" % (errors,)


def _read_wire_frame(client: socket.socket) -> bytes:
    """Read exactly one newline-delimited response from a local socket."""
    chunks = []
    while True:
        chunk = client.recv(65536)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    data = b"".join(chunks)
    assert data, "server closed the socket without a refusal/response frame"
    return data.split(b"\n", 1)[0]


def _raw_exchange(socket_path: Path, raw: bytes) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2.0)
        client.connect(str(socket_path))
        client.sendall(raw)
        frame = _read_wire_frame(client)
    try:
        response = json.loads(frame.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssertionError("server response was not one JSON object") from exc
    assert isinstance(response, dict), response
    return response


def _response_code(response: Mapping) -> str | None:
    """Read the contract's stable refusal code across response envelopes."""
    for key in ("refusal_code", "code"):
        value = response.get(key)
        if isinstance(value, str):
            return value
    error = response.get("error")
    if isinstance(error, Mapping) and isinstance(error.get("code"), str):
        return error["code"]
    return None


def _assert_refusal(response: Mapping, code: str):
    assert response.get("ok") is False, response
    assert _response_code(response) == code, response


def _parsed_lane(values: Mapping) -> str | None:
    """Read the canonical positional lane (or its optional compatibility dest)."""
    return values.get("lane_positional") or values.get("lane")


def _common_cli_args(operation: str, socket_path: Path,
                     request_id: str = "req-main") -> list[str]:
    """Use the documented ``lane-managed <operation> <lane>`` ordering."""
    return [
        operation,
        "build",
        "--socket", str(socket_path),
        "--generation", "7",
        "--request-id", request_id,
    ]


def _t020_cli_args(operation: str, socket_path: Path,
                   request_id: str = "req-t020", generation: int = 7) -> list[str]:
    """Build one documented ctx/handoff/swap command invocation."""
    arguments = [
        operation,
        "build",
        "--socket", str(socket_path),
        "--generation", str(generation),
        "--request-id", request_id,
    ]
    if operation == "swap":
        arguments.extend(["--profile", "team-b"])
    elif operation == "ctx":
        arguments.extend(["--checkpoint", "checkpoint-1", "--workers", "hold"])
    elif operation == "handoff":
        arguments.extend(["--checkpoint", "checkpoint-1"])
    return arguments


def _call_main(api: dict, argv: list[str], handler):
    """Capture main's operator output while accepting ``SystemExit`` style."""
    output = io.StringIO()
    error = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
        try:
            return_code = api["main"](argv, handler=handler)
        except SystemExit as exc:
            return_code = exc.code
    return return_code, output.getvalue(), error.getvalue()


def _wrapper_fixture(tmp_path: Path):
    """Copy the wrapper beside a fake ``lane-managed`` command.

    The production wrapper is expected to resolve its managed sibling (or the
    command on PATH) without sourcing a model-facing handoff.  The fake writes
    only argv, so a successful test proves forwarding without starting a
    controller, runtime, auth flow, or network process.
    """
    assert LANE_SWAP.is_file(), "lane-swap must be shipped as an executable script"
    command_dir = tmp_path / "commands"
    command_dir.mkdir(mode=0o700)
    wrapper = command_dir / "lane-swap"
    shutil.copy2(LANE_SWAP, wrapper)
    wrapper.chmod(0o700)

    fake = command_dir / "lane-managed"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "with open(os.environ['CAPTURE'], 'w', encoding='utf-8') as stream:\n"
        "    json.dump(sys.argv[1:], stream)\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)

    marker_dir = tmp_path / "fallback-markers"
    marker_dir.mkdir(mode=0o700)
    for name in ("lane-handoff", "handoff", "claude"):
        fallback = command_dir / name
        fallback.write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "from pathlib import Path\n"
            "Path(os.environ['MARKER_DIR'], " + repr(name + ".called") +
            ").write_text('called', encoding='utf-8')\n",
            encoding="utf-8",
        )
        fallback.chmod(0o700)

    capture = tmp_path / "lane-managed.argv.json"
    env = dict(os.environ)
    env.update({
        "PATH": str(command_dir) + os.pathsep + env.get("PATH", ""),
        "CAPTURE": str(capture),
        "MARKER_DIR": str(marker_dir),
        "HOME": str(tmp_path / "home"),
    })
    Path(env["HOME"]).mkdir(mode=0o700)
    return wrapper, capture, marker_dir, env


def _run_lane_swap(wrapper: Path, env: dict[str, str], args: list[str]):
    return subprocess.run(
        [str(wrapper), *args],
        cwd=str(wrapper.parent.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=2.0,
        check=False,
    )


_BASH_WRAPPER_SKIP = pytest.mark.skipif(
    os.name == "nt" or shutil.which("bash") is None,
    reason="lane-swap is a Bash command; Windows uses WSL2",
)

_INSTALLER_HELP_SKIP = pytest.mark.skipif(
    os.name == "nt" or shutil.which("bash") is None or shutil.which("jq") is None,
    reason="the isolated installer needs Bash and jq; Windows uses WSL2",
)


def test_lane_managed_script_surface_is_available():
    namespace = runpy.run_path(str(SCRIPT), run_name="lane_managed_cli_test")
    assert namespace["MAX_FRAME_BYTES"] == 1024 * 1024
    assert namespace["CONNECT_TIMEOUT"] == 5.0
    assert namespace["OPERATION_TIMEOUT"] == 120.0
    for name in (
        "build_parser",
        "encode_frame",
        "read_frame",
        "request_socket",
        "serve_once",
        "main",
    ):
        assert callable(namespace[name])


def test_external_help_lists_only_the_public_managed_operations():
    """The installed command advertises every T014 operation without a daemon."""
    assert SCRIPT.is_file(), "lane-managed must be shipped as an executable script"
    assert os.access(SCRIPT, os.X_OK), "lane-managed must be executable"
    process = subprocess.run(
        [str(SCRIPT), "--help"],
        cwd=str(REPO),
        env=dict(os.environ, PYTHONPATH=str(REPO)),
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    help_text = process.stdout + process.stderr
    for operation in OPERATIONS:
        assert operation in help_text
    assert "live" in help_text.lower()
    assert "unverified" in help_text.lower()


def test_parser_accepts_the_public_operations_and_wire_identity_fields(tmp_path):
    api = _load_cli()
    parser = api["build_parser"]()
    for operation in OPERATIONS:
        arguments = _common_cli_args(operation, tmp_path / "lane.sock")
        if operation == "swap":
            arguments.extend(["--profile", "team-b"])
        parsed = parser.parse_args(arguments)
        values = vars(parsed)
        assert values.get("operation", values.get("op")) == operation
        assert values.get("request_id") == "req-main"
        assert _parsed_lane(values) == "build"
        assert values.get("generation") == 7
        if "schema" in values:
            assert values["schema"] == 2

    literal_swap_lane = parser.parse_args(
        ["status", "swap", "--socket", str(tmp_path / "swap.sock"),
         "--generation", "7", "--request-id", "literal-swap"],
    )
    assert _parsed_lane(vars(literal_swap_lane)) == "swap"
    swap_operation_on_literal_lane = parser.parse_args(
        ["swap", "swap", "--profile", "team-b", "--socket",
         str(tmp_path / "swap-operation.sock"), "--generation", "7",
         "--request-id", "literal-swap-operation"],
    )
    assert vars(swap_operation_on_literal_lane).get("operation",
                                                     vars(swap_operation_on_literal_lane).get("op")) == "swap"
    assert _parsed_lane(vars(swap_operation_on_literal_lane)) == "swap"

    # ``--lane`` is an optional compatibility spelling.  If implemented, a
    # conflicting positional and option value must fail closed rather than
    # silently selecting one authority.  The conflict is a cross-field wire
    # validation rule, so it may be rejected by ``_request_from_args``/main
    # after argparse has accepted both values (rather than by argparse itself).
    conflict_calls = []

    def conflict_handler(request):
        conflict_calls.append(request)
        return {"ok": True}

    conflict_rc, conflict_out, conflict_err = _call_main(
        api,
        ["status", "build", "--lane", "other", "--socket",
         str(tmp_path / "conflict.sock"), "--generation", "7",
         "--request-id", "conflict"],
        conflict_handler,
    )
    assert isinstance(conflict_rc, int) and conflict_rc != 0
    assert not conflict_calls
    assert "positional lane and --lane disagree" in (
        conflict_out + conflict_err
    ).lower()

    with pytest.raises(SystemExit) as raised:
        parser.parse_args(["not-a-managed-operation"])
    assert raised.value.code == 2


def test_encode_and_read_frame_round_trip_and_one_mib_limit():
    api = _load_cli()
    encode_frame = api["encode_frame"]
    read_frame = api["read_frame"]
    maximum = api["MAX_FRAME_BYTES"]
    request = _request(body="round-trip")
    frame = encode_frame(request)
    assert isinstance(frame, (bytes, bytearray)), type(frame)
    assert frame.endswith(b"\n")
    assert read_frame(io.BytesIO(frame)) == request
    assert len(frame) <= maximum

    prefix = b'{"payload":"'
    suffix = b'"}\n'
    exact = prefix + (b"x" * (maximum - len(prefix) - len(suffix))) + suffix
    assert len(exact) == maximum
    assert read_frame(io.BytesIO(exact)) == {
        "payload": "x" * (maximum - len(prefix) - len(suffix))
    }

    oversized = prefix + (b"x" * (maximum - len(prefix) - len(suffix) + 1)) + suffix
    with pytest.raises(Exception):
        read_frame(io.BytesIO(oversized))


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_serve_once_creates_owner_only_parent_and_socket(tmp_path):
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"
    seen = []

    def handler(request):
        seen.append(request)
        return {
            "ok": True,
            "phase": "ready-held",
            "generation": request["generation"],
            "result": {"accepted": True},
        }

    thread, errors, _ = _start_server(api, socket_path, handler)
    parent_info = os.lstat(socket_path.parent)
    socket_info = os.lstat(socket_path)
    assert not stat.S_ISLNK(parent_info.st_mode)
    assert not stat.S_ISLNK(socket_info.st_mode)
    assert stat.S_IMODE(parent_info.st_mode) == 0o700
    assert stat.S_IMODE(socket_info.st_mode) == 0o600
    if hasattr(os, "getuid"):
        assert parent_info.st_uid == os.getuid()
        assert socket_info.st_uid == os.getuid()

    response = api["request_socket"](
        str(socket_path), _request(request_id="echo-me"),
        connect_timeout=0.5, operation_timeout=1.0,
    )
    assert response["ok"] is True
    assert response["request_id"] == "echo-me"
    assert seen == [_request(request_id="echo-me")]
    _join_server(thread, errors)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
@pytest.mark.parametrize("unsafe_parent", ["mode", "symlink"])
def test_serve_once_refuses_unsafe_parent_without_fallback(tmp_path, unsafe_parent):
    api = _load_cli()
    parent = tmp_path / "runtime"
    target = tmp_path / "real-runtime"
    target.mkdir(mode=0o700)
    if unsafe_parent == "mode":
        parent.mkdir(mode=0o755)
    else:
        parent.symlink_to(target, target_is_directory=True)
    socket_path = parent / "lane.sock"

    with pytest.raises(Exception) as raised:
        api["serve_once"](str(socket_path), lambda _request: {"ok": True})
    code = getattr(raised.value, "code", None)
    assert code in {"unsafe-state", "invalid", "permission"}, raised.value
    assert not socket_path.exists()
    assert not (target / "lane.sock").exists()


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_serve_once_refuses_socket_path_symlink(tmp_path):
    api = _load_cli()
    parent = tmp_path / "runtime"
    parent.mkdir(mode=0o700)
    target = tmp_path / "outside.sock"
    target.touch()
    socket_path = parent / "lane.sock"
    socket_path.symlink_to(target)

    with pytest.raises(Exception) as raised:
        api["serve_once"](str(socket_path), lambda _request: {"ok": True})
    code = getattr(raised.value, "code", None)
    assert code in {"unsafe-state", "invalid", "permission"}, raised.value
    assert target.is_file()


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_serve_once_rejects_symlink_ancestor_above_private_runtime(tmp_path):
    api = _load_cli()
    real_root = tmp_path / "real-root"
    real_root.mkdir(mode=0o700)
    alias = tmp_path / "runtime-alias"
    alias.symlink_to(real_root, target_is_directory=True)
    socket_path = alias / "private" / "lane.sock"

    with pytest.raises(Exception) as raised:
        api["serve_once"](str(socket_path), lambda _request: {"ok": True})
    code = getattr(raised.value, "code", None)
    assert code in {"unsafe-state", "invalid", "permission"}, raised.value
    assert not (real_root / "private" / "lane.sock").exists()


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_existing_live_socket_is_never_unlinked_or_rebound(tmp_path):
    api = _load_cli()
    parent = tmp_path / "runtime"
    parent.mkdir(mode=0o700)
    socket_path = parent / "lane.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    listener.listen(1)
    socket_path.chmod(0o600)
    before = os.lstat(socket_path)
    try:
        with pytest.raises(Exception) as raised:
            api["serve_once"](str(socket_path), lambda _request: {"ok": True})
        code = getattr(raised.value, "code", None)
        assert code in {"busy", "unsafe-state", "ownership-conflict", "invalid"}, raised.value
        after = os.lstat(socket_path)
        assert after.st_ino == before.st_ino
        assert stat.S_IMODE(after.st_mode) == 0o600
    finally:
        listener.close()
        socket_path.unlink(missing_ok=True)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_cleanup_does_not_unlink_a_replacement_socket_inode(tmp_path):
    """A path race cannot make serve_once delete another process's socket."""
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"
    replacement = {}

    def handler(_request):
        # Simulate a path replacement after the server accepted its client.
        os.unlink(socket_path)
        other = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        other.bind(str(socket_path))
        other.listen(1)
        socket_path.chmod(0o600)
        replacement["socket"] = other
        replacement["inode"] = os.lstat(socket_path).st_ino
        return {"ok": True, "phase": "ready-held", "generation": 7}

    try:
        thread, errors, _ = _start_server(api, socket_path, handler)
        response = api["request_socket"](
            str(socket_path), _request(request_id="replacement"),
            connect_timeout=0.5, operation_timeout=1.0,
        )
        assert response["ok"] is True
        _join_server(thread, errors)
        assert socket_path.exists()
        assert os.lstat(socket_path).st_ino == replacement["inode"]
    finally:
        other = replacement.get("socket")
        if other is not None:
            other.close()
        socket_path.unlink(missing_ok=True)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_socket_round_trip_delivers_the_complete_request_envelope(tmp_path):
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"
    seen = []

    def handler(request):
        seen.append(request)
        return {
            "ok": True,
            "phase": "preflight",
            "generation": request["generation"],
            "result": {"operation_seen": request["operation"]},
        }

    thread, errors, _ = _start_server(api, socket_path, handler)
    request = _request(
        operation="start",
        request_id="request-envelope-1",
        generation=19,
        participant_ids=["coordinator", "worker-a"],
    )
    response = api["request_socket"](
        str(socket_path), request, connect_timeout=0.5, operation_timeout=1.0,
    )
    assert response["ok"] is True
    assert response["request_id"] == request["request_id"]
    assert response["generation"] == request["generation"]
    assert seen == [request]
    assert set(seen[0]) >= {
        "schema", "request_id", "lane", "generation", "operation",
    }
    _join_server(thread, errors)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_production_server_keeps_one_asyncio_loop_and_reader_across_requests(
        tmp_path):
    """Sequential controls share a loop so adapter readers are not torn down."""
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"
    loops = []
    heartbeats = []
    reader_done = threading.Event()
    stop_reader = None

    async def handler(request):
        nonlocal stop_reader
        loops.append(asyncio.get_running_loop())
        if stop_reader is None:
            stop_reader = asyncio.Event()

            async def reader():
                try:
                    while not stop_reader.is_set():
                        heartbeats.append(time.monotonic())
                        await asyncio.sleep(0.005)
                finally:
                    reader_done.set()

            asyncio.create_task(reader())
            await asyncio.sleep(0)
        elif request["request_id"] == "reader-second":
            stop_reader.set()
            # Give the reader one scheduling turn to finish before the
            # persistent owner loop is shut down.
            await asyncio.sleep(0.02)
        return {
            "ok": True,
            "phase": "ready-held",
            "generation": request["generation"],
            "result": {"request": request["request_id"]},
        }

    thread, errors, _ = _start_server(
        api, socket_path, handler, serve_name="serve_daemon", max_requests=2,
    )
    first = api["request_socket"](
        str(socket_path), _request(request_id="reader-first"),
        connect_timeout=0.5, operation_timeout=1.0,
    )
    assert first["ok"] is True
    assert loops and heartbeats
    first_heartbeat_count = len(heartbeats)
    time.sleep(0.035)
    assert len(heartbeats) > first_heartbeat_count
    assert not reader_done.is_set(), "reader ended with the first request"

    second = api["request_socket"](
        str(socket_path), _request(request_id="reader-second"),
        connect_timeout=0.5, operation_timeout=1.0,
    )
    assert second["ok"] is True
    assert len(loops) == 2
    assert loops[0] is loops[1], "server created a fresh loop per request"
    _join_server(thread, errors)
    assert reader_done.is_set()


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_async_operation_cancellation_reconciles_before_next_mutation(
        tmp_path):
    """A timed-out async mutation is fully cancelled before admission resumes."""
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"
    started = threading.Event()
    cancellation_seen = threading.Event()
    reconciled = threading.Event()
    fast_admitted_before_reconcile = []
    first_result = []
    second_result = []

    async def handler(request):
        if request["request_id"] == "cancel-first":
            started.set()
            try:
                while True:
                    await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                cancellation_seen.set()
                # Simulate async adapter/tool reconciliation that cannot be
                # skipped merely because the operation deadline elapsed.
                await asyncio.sleep(0.15)
                reconciled.set()
                raise
        fast_admitted_before_reconcile.append(not reconciled.is_set())
        return {
            "ok": True,
            "phase": "ready-held",
            "generation": request["generation"],
            "result": {"request": request["request_id"]},
        }

    thread, errors, _ = _start_server(
        api, socket_path, handler,
        serve_name="serve_daemon", max_requests=2, operation_timeout=0.05,
    )

    def send_first():
        try:
            first_result.append(api["request_socket"](
                str(socket_path), _request(request_id="cancel-first"),
                connect_timeout=0.5, operation_timeout=1.0,
            ))
        except Exception as exc:
            first_result.append(exc)

    first_client = threading.Thread(target=send_first, name="cancel-first-client")
    first_client.daemon = True
    first_client.start()
    assert started.wait(1.0)
    # Connect while cancellation/reconciliation is still in progress.  A
    # persistent server must queue this request rather than admit its mutation.
    time.sleep(0.06)
    second_result.append(api["request_socket"](
        str(socket_path), _request(request_id="cancel-second"),
        connect_timeout=0.5, operation_timeout=1.0,
    ))
    first_client.join(timeout=1.5)
    assert not first_client.is_alive()
    assert cancellation_seen.is_set()
    assert reconciled.is_set()
    assert fast_admitted_before_reconcile == [False]
    assert first_result and isinstance(first_result[0], Mapping)
    assert first_result[0].get("ok") is False
    assert _response_code(first_result[0]) in {
        "timeout", "deadline", "operation-timeout", "unknown",
    }
    assert second_result and second_result[0]["ok"] is True
    _join_server(thread, errors)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_daemon_loop_survives_refused_stale_and_invalid_shutdown_before_status(
        tmp_path):
    """Refused shutdowns do not tear down the owner loop or its reader task."""
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "persistent-refusals.sock"
    loops = []
    requests = []
    heartbeats = []
    reader_done = threading.Event()
    stop_reader = None

    async def handler(request):
        nonlocal stop_reader
        loops.append(asyncio.get_running_loop())
        requests.append(request)
        if stop_reader is None:
            stop_reader = asyncio.Event()

            async def reader():
                try:
                    while not stop_reader.is_set():
                        heartbeats.append(time.monotonic())
                        await asyncio.sleep(0.005)
                finally:
                    reader_done.set()

            asyncio.create_task(reader())
            # Let the persistent reader start before this first refusal is
            # sent, so a later request can prove that it was not torn down.
            await asyncio.sleep(0)
        else:
            assert not reader_done.is_set(), (
                "a refused shutdown ended the daemon-owned reader task"
            )

        if request["request_id"] == "shutdown-stale":
            return {
                "ok": False,
                "phase": "held",
                "generation": 8,
                "refusal_code": "stale-generation",
            }
        if request["request_id"] == "shutdown-invalid":
            return {
                "ok": False,
                "phase": "held",
                "generation": request["generation"],
                "refusal_code": "invalid",
            }
        assert request["operation"] == "status"
        reader_alive_before_status = not reader_done.is_set()
        stop_reader.set()
        # Reconcile the background reader on the same owning loop before the
        # max_requests test seam permits serve_daemon to return.
        await asyncio.sleep(0.02)
        return {
            "ok": True,
            "phase": "released",
            "generation": request["generation"],
            "result": {
                "reader_alive_before_status": reader_alive_before_status,
                "refusals_seen": 2,
            },
        }

    thread, errors, _ = _start_server(
        api,
        socket_path,
        handler,
        serve_name="serve_daemon",
        max_requests=3,
        connect_timeout=0.5,
        operation_timeout=1.0,
    )

    stale = api["request_socket"](
        str(socket_path),
        _request(
            operation="shutdown", request_id="shutdown-stale", generation=7,
        ),
        connect_timeout=0.5,
        operation_timeout=1.0,
    )
    _assert_refusal(stale, "stale-generation")
    assert stale["request_id"] == "shutdown-stale"
    assert socket_path.exists(), "stale shutdown removed the daemon socket"
    assert loops and heartbeats
    heartbeat_count = len(heartbeats)
    time.sleep(0.025)
    assert len(heartbeats) > heartbeat_count

    invalid = api["request_socket"](
        str(socket_path),
        _request(
            operation="shutdown", request_id="shutdown-invalid", generation=8,
        ),
        connect_timeout=0.5,
        operation_timeout=1.0,
    )
    _assert_refusal(invalid, "invalid")
    assert invalid["request_id"] == "shutdown-invalid"
    assert socket_path.exists(), "invalid shutdown removed the daemon socket"
    assert not reader_done.is_set()

    status = api["request_socket"](
        str(socket_path),
        _request(operation="status", request_id="status-after-refusals", generation=8),
        connect_timeout=0.5,
        operation_timeout=1.0,
    )
    assert status["ok"] is True
    assert status["request_id"] == "status-after-refusals"
    assert status["result"]["reader_alive_before_status"] is True
    assert status["result"]["refusals_seen"] == 2
    assert len(loops) == 3
    assert loops[0] is loops[1] is loops[2]
    assert [request["request_id"] for request in requests] == [
        "shutdown-stale", "shutdown-invalid", "status-after-refusals",
    ]

    _join_server(thread, errors)
    assert reader_done.is_set()
    assert not socket_path.exists(), "persistent daemon did not clean up its socket"


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_request_socket_rejects_symlink_ancestor_before_connecting(tmp_path):
    api = _load_cli()
    real_root = tmp_path / "real-root"
    runtime = real_root / "runtime"
    runtime.mkdir(parents=True, mode=0o700)
    alias = tmp_path / "runtime-alias"
    alias.symlink_to(real_root, target_is_directory=True)
    socket_path = runtime / "lane.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    listener.listen(1)
    socket_path.chmod(0o600)
    accepted = []
    listener.settimeout(0.25)

    def observe_client():
        try:
            client, _ = listener.accept()
        except (socket.timeout, OSError):
            return
        accepted.append(client)
        client.close()

    observer = threading.Thread(target=observe_client, name="symlink-client-observer")
    observer.daemon = True
    observer.start()
    try:
        outcome = None
        exception = None
        try:
            outcome = api["request_socket"](
                str(alias / "runtime" / "lane.sock"),
                _request(request_id="symlink-client"),
                connect_timeout=0.05, operation_timeout=0.10,
            )
        except Exception as exc:
            exception = exc
        assert exception is not None or (
            isinstance(outcome, Mapping) and outcome.get("ok") is False
        )
        observer.join(timeout=0.5)
        assert not accepted, "client followed a symlinked socket ancestor"
    finally:
        listener.close()
        socket_path.unlink(missing_ok=True)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_request_socket_uses_an_absolute_read_deadline_not_idle_timeouts(tmp_path):
    """Slow trickle bytes must not extend one operation forever."""
    api = _load_cli()
    parent = tmp_path / "runtime"
    parent.mkdir(mode=0o700)
    socket_path = parent / "lane.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    listener.listen(1)
    socket_path.chmod(0o600)
    response = api["encode_frame"]({
        "ok": True,
        "request_id": "trickle",
        "generation": 7,
        "phase": "ready-held",
    })
    server_done = threading.Event()

    def trickle_server():
        try:
            listener.settimeout(1.0)
            client, _ = listener.accept()
            with client:
                client.settimeout(1.0)
                # Read the request before slowly dribbling a valid response.
                while b"\n" not in client.recv(65536):
                    pass
                for byte in response:
                    try:
                        client.send(bytes((byte,)))
                    except OSError:
                        break
                    time.sleep(0.015)
        finally:
            server_done.set()

    server = threading.Thread(target=trickle_server, name="lane-managed-trickle")
    server.daemon = True
    server.start()
    started = time.monotonic()
    outcome = None
    exception = None
    try:
        try:
            outcome = api["request_socket"](
                str(socket_path), _request(request_id="trickle"),
                connect_timeout=0.5, operation_timeout=0.08,
            )
        except Exception as exc:
            exception = exc
    finally:
        elapsed = time.monotonic() - started
    assert elapsed < 0.30, "read deadline reset on each trickled byte"
    if exception is None:
        assert isinstance(outcome, Mapping)
        assert outcome.get("ok") is False
        assert _response_code(outcome) in {
            "timeout", "deadline", "operation-timeout", "unknown",
        }
    else:
        assert isinstance(exception, (TimeoutError, OSError, RuntimeError))
    assert server_done.wait(2.5)
    listener.close()
    socket_path.unlink(missing_ok=True)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
@pytest.mark.parametrize(
    "raw,expected_code",
    [
        (b"not-json\n", "invalid"),
        (b"[]\n", "invalid"),
        (b'{"schema":1,"lane":"build"}\n', "invalid"),
        (b'{"schema":999,"request_id":"bad-schema","lane":"build",'
         b'"generation":7,"operation":"status"}\n', "invalid"),
        (b'{"schema":1,"request_id":7,"lane":"build",'
         b'"generation":7,"operation":"status"}\n', "invalid"),
        (b'{"schema":1,"request_id":"bad-lane","lane":"build/child",'
         b'"generation":7,"operation":"status"}\n', "invalid"),
        (b'{"schema":1,"request_id":"bad-generation","lane":"build",'
         b'"generation":true,"operation":"status"}\n', "invalid"),
        (b'{"schema":1,"request_id":"bad-op","lane":"build",'
         b'"generation":7,"operation":"unknown"}\n', "invalid"),
    ],
    ids="malformed non-object missing-field bad-schema bad-id bad-lane bad-generation bad-op".split(),
)
def test_socket_refuses_malformed_or_invalid_request_envelopes(
        tmp_path, raw: bytes, expected_code: str):
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"
    called = []
    thread, errors, _ = _start_server(
        api, socket_path, lambda request: called.append(request),
    )
    response = _raw_exchange(socket_path, raw)
    _assert_refusal(response, expected_code)
    assert not called
    if b"request_id" in raw and b'"request_id":"' in raw:
        request_id = raw.split(b'"request_id":"', 1)[1].split(b'"', 1)[0]
        assert response.get("request_id") == request_id.decode("utf-8")
    _join_server(thread, errors)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_socket_refuses_a_frame_larger_than_one_mib(tmp_path):
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"
    thread, errors, _ = _start_server(
        api, socket_path, lambda _request: pytest.fail("oversized request reached handler"),
    )
    maximum = api["MAX_FRAME_BYTES"]
    oversized = b'{"schema":1,"request_id":"too-large","lane":"build",'
    oversized += b'"generation":7,"operation":"status","body":"'
    oversized += b"x" * (maximum - len(oversized) + 1)
    oversized += b'"}\n'
    assert len(oversized) > maximum
    response = _raw_exchange(socket_path, oversized)
    _assert_refusal(response, "invalid")
    assert response.get("request_id") in {None, "too-large"}
    _join_server(thread, errors)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_request_socket_operation_deadline_is_short_and_bounded(tmp_path):
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"
    entered = threading.Event()

    def slow_handler(_request):
        entered.set()
        time.sleep(0.40)
        return {"ok": True, "phase": "ready-held", "generation": 7}

    thread, errors, _ = _start_server(api, socket_path, slow_handler)
    started = time.monotonic()
    outcome = None
    exception = None
    try:
        outcome = api["request_socket"](
            str(socket_path), _request(request_id="deadline"),
            connect_timeout=0.5, operation_timeout=0.05,
        )
    except Exception as exc:
        exception = exc
    elapsed = time.monotonic() - started
    assert entered.wait(1.0), "request never reached the injected handler"
    assert elapsed < 0.30, "operation timeout was not enforced: %.3fs" % elapsed
    if exception is None:
        assert isinstance(outcome, Mapping)
        assert outcome.get("ok") is False
        assert _response_code(outcome) in {
            "timeout", "deadline", "operation-timeout", "unknown",
        }
    else:
        assert isinstance(exception, (TimeoutError, OSError, RuntimeError))
    thread.join(timeout=1.5)
    assert not thread.is_alive()
    assert not errors, "serve_once raised: %r" % (errors,)


def test_request_socket_passes_a_bounded_connect_timeout_to_the_socket(tmp_path):
    """A caller-supplied connect deadline reaches a bounded socket wait.

    The transport may implement the wait with ``socket.settimeout`` or an
    asyncio ``sock_connect`` deadline.  The public contract is the bounded
    result, not either implementation detail.
    """
    api = _load_cli()
    calls = []
    real_socket_module = api["socket"]
    parent = tmp_path / "runtime"
    parent.mkdir(mode=0o700)
    socket_path = parent / "lane.sock"
    # Keep the path's security preflight realistic.  The injected socket then
    # fails at connect, which proves the deadline reaches the connect seam
    # rather than allowing a missing-path refusal to short-circuit the check.
    listener = real_socket_module.socket(
        real_socket_module.AF_UNIX, real_socket_module.SOCK_STREAM,
    )
    listener.bind(str(socket_path))
    listener.listen(1)
    socket_path.chmod(0o600)

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def settimeout(self, value):
            calls.append(("settimeout", value))

        def connect(self, address):
            calls.append(("connect", address))
            raise TimeoutError("injected connect timeout")

        def close(self):
            calls.append(("close",))

    class FakeSocketModule:
        AF_UNIX = real_socket_module.AF_UNIX
        SOCK_STREAM = real_socket_module.SOCK_STREAM
        timeout = TimeoutError
        error = OSError

        @staticmethod
        def socket(*args, **kwargs):
            calls.append(("socket", args, kwargs))
            return FakeSocket()

        @staticmethod
        def create_connection(address, timeout=None, **kwargs):
            calls.append(("create_connection", address, timeout, kwargs))
            raise TimeoutError("injected connect timeout")

    api["socket"] = FakeSocketModule
    started = time.monotonic()
    try:
        outcome = None
        exception = None
        try:
            outcome = api["request_socket"](
                str(socket_path),
                _request(request_id="connect-timeout"),
                connect_timeout=0.25, operation_timeout=0.50,
            )
        except Exception as exc:
            exception = exc
        assert exception is not None or (
            isinstance(outcome, Mapping) and outcome.get("ok") is False
        )
    finally:
        elapsed = time.monotonic() - started
        api["socket"] = real_socket_module
        listener.close()
        socket_path.unlink(missing_ok=True)
    assert elapsed <= 1.0, "connect wait exceeded its bounded deadline"
    assert any(call[0] in {"connect", "sock_connect", "create_connection"}
               for call in calls), "transport never reached its connect seam"


def test_request_socket_never_retries_after_a_request_has_been_sent(tmp_path):
    """A lost response cannot cause a second mutation attempt."""
    api = _load_cli()
    real_socket_module = api["socket"]
    parent = tmp_path / "runtime"
    parent.mkdir(mode=0o700)
    socket_path = parent / "lane.sock"
    listener = real_socket_module.socket(
        real_socket_module.AF_UNIX, real_socket_module.SOCK_STREAM,
    )
    listener.bind(str(socket_path))
    listener.listen(1)
    socket_path.chmod(0o600)
    calls = {"sockets": 0, "sends": 0, "receives": 0}

    class FakeSocket:
        def settimeout(self, _value):
            return None

        def connect(self, _address):
            return None

        def sendall(self, _frame):
            calls["sends"] += 1

        def recv(self, _size):
            calls["receives"] += 1
            return b""

        def close(self):
            return None

    class FakeSocketModule:
        AF_UNIX = real_socket_module.AF_UNIX
        SOCK_STREAM = real_socket_module.SOCK_STREAM
        timeout = TimeoutError
        error = OSError

        @staticmethod
        def socket(*_args, **_kwargs):
            calls["sockets"] += 1
            return FakeSocket()

    api["socket"] = FakeSocketModule
    try:
        with pytest.raises(BaseException) as raised:
            api["request_socket"](
                socket_path,
                _request(request_id="sent-once"),
                connect_timeout=0.1,
                operation_timeout=0.1,
            )
    finally:
        api["socket"] = real_socket_module
        listener.close()
        socket_path.unlink(missing_ok=True)

    assert getattr(raised.value, "code", None) == "invalid"
    assert calls == {"sockets": 1, "sends": 1, "receives": 1}


def test_request_socket_caps_caller_deadlines_at_published_defaults(tmp_path):
    """Large caller values cannot turn the local transport into an unbounded wait."""
    api = _load_cli()
    calls = []
    real_socket_module = api["socket"]

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def settimeout(self, value):
            calls.append(float(value))

        def connect(self, _address):
            return None

        def sendall(self, _frame):
            return None

        def recv(self, _size):
            raise TimeoutError("injected operation timeout")

        def makefile(self, *_args, **_kwargs):
            return self

        def readline(self, *_args, **_kwargs):
            raise TimeoutError("injected operation timeout")

        def close(self):
            return None

    class FakeSocketModule:
        AF_UNIX = real_socket_module.AF_UNIX
        SOCK_STREAM = real_socket_module.SOCK_STREAM
        timeout = TimeoutError
        error = OSError

        @staticmethod
        def socket(*_args, **_kwargs):
            return FakeSocket()

        @staticmethod
        def create_connection(_address, timeout=None, **_kwargs):
            if timeout is not None:
                calls.append(float(timeout))
            return FakeSocket()

    api["socket"] = FakeSocketModule
    try:
        outcome = None
        exception = None
        try:
            outcome = api["request_socket"](
                str(tmp_path / "unbounded.sock"), _request(),
                connect_timeout=999999.0, operation_timeout=999999.0,
            )
        except Exception as exc:
            exception = exc
        assert exception is not None or (
            isinstance(outcome, Mapping) and outcome.get("ok") is False
        )
    finally:
        api["socket"] = real_socket_module
    # Rejecting an over-large deadline before connecting is valid; if the
    # implementation clamps instead, every applied timeout must stay within
    # the published bounds.
    if calls:
        assert min(calls) <= api["CONNECT_TIMEOUT"]
        assert max(calls) <= api["OPERATION_TIMEOUT"]


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_serve_once_does_not_report_timeout_before_injected_handler_quiesces(
        tmp_path):
    """A bounded handler deadline cannot abandon a still-running side effect."""
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"
    started = threading.Event()
    finished = threading.Event()

    def handler(_request):
        started.set()
        # This event stands for an injected tool mutation.  The server may
        # refuse after a deadline, but it must not return while this callback
        # is still running and leave the mutation owner behind.
        time.sleep(0.20)
        finished.set()
        return {"ok": True, "phase": "ready-held", "generation": 7}

    thread, errors, _ = _start_server(
        api, socket_path, handler, operation_timeout=0.05,
    )
    outcome = None
    exception = None
    try:
        try:
            outcome = api["request_socket"](
                str(socket_path), _request(request_id="handler-deadline"),
                connect_timeout=0.5, operation_timeout=1.0,
            )
        except Exception as exc:
            exception = exc
        assert started.is_set()
        assert finished.is_set(), (
            "serve_once returned while its injected handler was still running"
        )
        if exception is None:
            assert isinstance(outcome, Mapping)
            if outcome.get("ok") is False:
                assert _response_code(outcome) in {
                    "timeout", "deadline", "operation-timeout", "unknown",
                }
    finally:
        thread.join(timeout=1.5)
    assert not thread.is_alive()
    assert not errors, "serve_once raised: %r" % (errors,)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
@pytest.mark.parametrize("argument", [None, float("inf"), -1.0],
                         ids=["none", "infinity", "negative"])
def test_request_socket_does_not_accept_an_unbounded_or_invalid_deadline(
        tmp_path, argument):
    api = _load_cli()
    socket_path = tmp_path / "missing.sock"
    started = time.monotonic()
    with pytest.raises(Exception) as raised:
        api["request_socket"](
            str(socket_path), _request(request_id="invalid-timeout"),
            connect_timeout=argument, operation_timeout=argument,
        )
    assert time.monotonic() - started < 0.30
    assert isinstance(raised.value, (ValueError, TimeoutError, OSError, RuntimeError))


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
@pytest.mark.parametrize("refusal_code", ["busy", "stale-generation"])
def test_transport_preserves_stable_busy_and_stale_refusals(tmp_path,
                                                             refusal_code):
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"

    def handler(request):
        return {
            "ok": False,
            "phase": "preflight",
            "generation": request["generation"],
            "refusal_code": refusal_code,
            "message": "injected deterministic refusal",
        }

    thread, errors, _ = _start_server(api, socket_path, handler)
    request_id = "refusal-" + refusal_code
    response = api["request_socket"](
        str(socket_path), _request(request_id=request_id),
        connect_timeout=0.5, operation_timeout=1.0,
    )
    _assert_refusal(response, refusal_code)
    assert response["request_id"] == request_id
    assert response["generation"] == 7
    _join_server(thread, errors)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"),
                    reason="managed control transport requires Unix sockets")
def test_status_is_always_live_unverified_even_when_fake_handler_claims_verified(
        tmp_path):
    """Fake transport evidence cannot publish a live capability certificate."""
    api = _load_cli()
    socket_path = tmp_path / "runtime" / "lane.sock"

    def fake_handler(request):
        assert request["operation"] == "status"
        return {
            "ok": True,
            "phase": "idle",
            "generation": request["generation"],
            "live_capability": "VERIFIED",
            "experimental": False,
            "result": {"source": "fake-handler"},
        }

    thread, errors, _ = _start_server(api, socket_path, fake_handler)
    response = api["request_socket"](
        str(socket_path), _request(request_id="status-fake"),
        connect_timeout=0.5, operation_timeout=1.0,
    )
    assert response["request_id"] == "status-fake"
    assert str(response.get("live_capability", "")).upper() == "UNVERIFIED"
    assert response.get("experimental") is True
    _join_server(thread, errors)


def test_main_injected_status_reports_unverified_experimental_capability(
        tmp_path):
    """The command's status output keeps the fake/live evidence boundary clear."""
    api = _load_cli()
    seen = []

    def fake_handler(request):
        seen.append(request)
        return {
            "ok": True,
            "phase": "idle",
            "generation": request["generation"],
            "live_capability": "VERIFIED",
            "experimental": False,
        }

    return_code, output, error = _call_main(
        api,
        _common_cli_args("status", tmp_path / "lane.sock", "main-status"),
        fake_handler,
    )
    assert return_code == 0
    assert not error
    assert seen and seen[0]["operation"] == "status"
    assert seen[0]["schema"] == 2
    assert seen[0]["schema_version"] == 2
    assert seen[0]["architecture"] == "native-coordinator-lineage"
    assert seen[0]["request_id"] == "main-status"
    assert seen[0]["lane"] == "build"
    assert seen[0]["generation"] == 7
    rendered = output.lower()
    assert "unverified" in rendered
    assert "experimental" in rendered
    assert "verified" not in rendered.replace("unverified", "")


def test_main_refusal_exit_mapping_is_stable_and_nonzero(tmp_path):
    api = _load_cli()

    def refusal_handler(request):
        refusal_code = (
            "stale-generation"
            if request["request_id"] == "main-stale"
            else "busy"
        )
        return {
            "ok": False,
            "phase": "preflight",
            "generation": request["generation"],
            "refusal_code": refusal_code,
        }

    busy_args = _common_cli_args("status", tmp_path / "busy.sock", "main-busy")
    stale_args = _common_cli_args("status", tmp_path / "stale.sock", "main-stale")

    busy_rc, busy_out, busy_err = _call_main(api, busy_args, refusal_handler)
    busy_again_rc, _, _ = _call_main(api, busy_args, refusal_handler)
    stale_rc, stale_out, stale_err = _call_main(api, stale_args, refusal_handler)
    stale_again_rc, _, _ = _call_main(api, stale_args, refusal_handler)

    assert isinstance(busy_rc, int) and busy_rc > 0
    assert busy_again_rc == busy_rc
    assert isinstance(stale_rc, int) and stale_rc > 0
    assert stale_again_rc == stale_rc
    assert busy_rc != stale_rc
    assert "busy" in (busy_out + busy_err).lower()
    assert "stale-generation" in (stale_out + stale_err).lower()


@_BASH_WRAPPER_SKIP
def test_lane_swap_forwards_positional_lane_and_profile_as_one_argv_each(tmp_path):
    wrapper, capture, markers, env = _wrapper_fixture(tmp_path)
    profile = "profile with spaces;$(touch should-not-run)"
    process = _run_lane_swap(wrapper, env, [
        "build", "--profile", profile,
    ])

    assert process.returncode == 0, process.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == [
        "swap", "build", "--profile", profile,
    ]
    assert not list(markers.iterdir()), "wrapper invoked a model/handoff fallback"


@_BASH_WRAPPER_SKIP
def test_lane_swap_preserves_literal_swap_lane_and_never_treats_it_as_command(
        tmp_path):
    wrapper, capture, markers, env = _wrapper_fixture(tmp_path)
    process = _run_lane_swap(wrapper, env, [
        "swap", "--profile", "target profile",
    ])

    assert process.returncode == 0, process.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == [
        "swap", "swap", "--profile", "target profile",
    ]
    assert not list(markers.iterdir())


@_BASH_WRAPPER_SKIP
@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_lane_swap_direct_help_is_local_and_successful(tmp_path, flag):
    """Help is a wrapper question and must not resolve or execute lane-managed."""
    wrapper, capture, markers, env = _wrapper_fixture(tmp_path)
    process = _run_lane_swap(wrapper, env, [flag])

    assert process.returncode == 0, process.stderr
    assert "usage: lane-swap <lane> --profile <profile>" in process.stdout
    assert "--operation-timeout" in process.stdout
    assert process.stderr == ""
    assert not capture.exists(), "help attempted to execute lane-managed"
    assert not list(markers.iterdir()), "help invoked a model/handoff fallback"


def _installed_lane_swap_help_fixture(tmp_path: Path):
    """Install into a private tree, then replace the target with a tripwire."""
    home = tmp_path / "install-home"
    bin_dir = tmp_path / "installed-bin"
    home.mkdir(mode=0o700)
    bin_dir.mkdir(mode=0o700)
    env = dict(os.environ)
    for name in (
        "OPENREPOTOOLS_REF", "OPENREPOTOOLS_REPO", "OPENREPOTOOLS_BIN_DIR",
        "CLAUDE_PROFILES_HOME", "CLAUDE_USER_DIR", "AGENT_PROTOCOL_ROOT",
        "PROJECTS_DIR",
    ):
        env.pop(name, None)
    env.update({
        "HOME": str(home),
        "OPENREPOTOOLS_BIN_DIR": str(bin_dir),
        "CLAUDE_PROFILES_HOME": str(home / ".claude-profiles"),
        "CLAUDE_USER_DIR": str(home / ".claude"),
        "AGENT_PROTOCOL_ROOT": str(home / ".agents"),
        "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
    })

    install = subprocess.run(
        ["bash", str(OPENREPOTOOLS), "--install"],
        cwd=str(tmp_path),
        env=env,
        input="",
        capture_output=True,
        text=True,
        check=False,
        timeout=10.0,
    )
    assert install.returncode == 0, install.stderr + install.stdout

    marker = tmp_path / "lane-managed-help-executed"
    env["HELP_MARKER"] = str(marker)
    target = bin_dir / "lane-managed"
    target.write_text(
        "#!/bin/sh\n"
        "touch \"$HELP_MARKER\"\n"
        "exit 37\n",
        encoding="utf-8",
    )
    target.chmod(0o700)
    return bin_dir / "lane-swap", env, marker


@_INSTALLER_HELP_SKIP
@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_lane_swap_installed_help_is_local_and_successful(tmp_path, flag):
    """The installed wrapper keeps help local before resolving its sibling."""
    wrapper, env, marker = _installed_lane_swap_help_fixture(tmp_path)
    process = _run_lane_swap(wrapper, env, [flag])

    assert process.returncode == 0, process.stderr
    assert "usage: lane-swap <lane> --profile <profile>" in process.stdout
    assert "--operation-timeout" in process.stdout
    assert process.stderr == ""
    assert not marker.exists(), "installed help executed lane-managed"


@_BASH_WRAPPER_SKIP
@pytest.mark.parametrize(
    "args",
    [
        [],
        ["build"],
        ["--profile", "team-a"],
        ["build", "--profile"],
        ["build", "--unknown", "flag", "--profile", "team-a"],
        ["build", "--profile", "team-a", "--unknown"],
        ["build", "--profile", "team-a", "extra"],
        ["build", "--profile", "team-a", "--profile", "team-b"],
    ],
    ids=[
        "missing-all",
        "missing-profile",
        "missing-lane",
        "missing-profile-value",
        "unknown-before-profile",
        "unknown-after-profile",
        "extra-positional",
        "duplicate-profile",
    ],
)
def test_lane_swap_refuses_missing_or_unknown_arguments_without_delegating(
        tmp_path, args):
    wrapper, capture, markers, env = _wrapper_fixture(tmp_path)
    process = _run_lane_swap(wrapper, env, args)

    assert process.returncode != 0
    assert not capture.exists(), "invalid wrapper input reached lane-managed"
    assert not list(markers.iterdir()), "invalid input fell back to a model/handoff"


@_BASH_WRAPPER_SKIP
def test_lane_swap_propagates_managed_refusal_without_handoff_or_model_fallback(
        tmp_path):
    wrapper, capture, markers, env = _wrapper_fixture(tmp_path)
    fake = wrapper.parent / "lane-managed"
    fake.write_text(
        fake.read_text(encoding="utf-8") + "raise SystemExit(23)\n",
        encoding="utf-8",
    )
    fake.chmod(0o700)

    process = _run_lane_swap(
        wrapper, env, ["build", "--profile", "team-a"],
    )

    assert process.returncode == 23
    assert json.loads(capture.read_text(encoding="utf-8")) == [
        "swap", "build", "--profile", "team-a",
    ]
    assert not list(markers.iterdir()), "managed refusal used a legacy fallback"


def _t020_ctx_restart_args(socket_path: Path,
                           request_id: str = "ctx-restart") -> list[str]:
    """Build the documented mapping-free ``ctx --workers restart`` form."""
    return [
        "ctx",
        "build",
        "--socket", str(socket_path),
        "--generation", "7",
        "--request-id", request_id,
        "--checkpoint", "checkpoint-1",
        "--workers", "restart",
    ]


def test_parser_exposes_ctx_and_checkpoint_only_handoff_forms(tmp_path):
    api = _load_cli()
    parser = api["build_parser"]()

    for operation in ("ctx", "handoff"):
        parsed = parser.parse_args(
            _t020_cli_args(operation, tmp_path / (operation + ".sock")),
        )
        values = vars(parsed)
        assert values.get("operation", values.get("op")) == operation
        assert _parsed_lane(values) == "build"
        assert values.get("generation") == 7
        assert values.get("request_id") == "req-t020"
        assert "mapping_json" not in values
        assert "mapping_option" not in values

    parsed = parser.parse_args(_t020_ctx_restart_args(tmp_path / "restart.sock"))
    assert vars(parsed).get("operation", vars(parsed).get("op")) == "ctx"

    help_process = subprocess.run(
        [str(SCRIPT), "ctx", "--help"],
        cwd=str(REPO),
        env=dict(os.environ, PYTHONPATH=str(REPO)),
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_process.returncode == 0, help_process.stderr
    assert "mapping" not in (help_process.stdout + help_process.stderr).lower()


@pytest.mark.parametrize(
    "args",
    [
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "missing-checkpoint", "--workers", "hold"],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "missing-workers", "--checkpoint", "checkpoint-1"],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "bad-policy", "--checkpoint", "checkpoint-1",
         "--workers", "legacy"],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "rebind-policy", "--checkpoint", "checkpoint-1",
         "--workers", "rebind"],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "restart-mapping", "--checkpoint", "checkpoint-1",
         "--workers", "restart", "--mapping", "{}"],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "restart-null-mapping", "--checkpoint", "checkpoint-1",
         "--workers", "restart", "--mapping", "null"],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "restart-positional-mapping", "--checkpoint", "checkpoint-1",
         "--workers", "restart", "{}"],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "body-mapping", "--checkpoint", "checkpoint-1",
         "--workers", "hold", "--body", '{"mapping": {}}'],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "body-null-mapping", "--checkpoint", "checkpoint-1",
         "--workers", "hold", "--body", '{"mapping": null}'],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "body-worker-mapping", "--checkpoint", "checkpoint-1",
         "--workers", "hold", "--body", '{"worker_mapping": {}}'],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "body-rebind-mapping", "--checkpoint", "checkpoint-1",
         "--workers", "hold", "--body", '{"rebind_mapping": null}'],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "body-rebind-policy", "--checkpoint", "checkpoint-1",
         "--body", '{"worker_policy": "rebind"}'],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "body-list", "--checkpoint", "checkpoint-1",
         "--workers", "hold", "--body", "[]"],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "body-null", "--checkpoint", "checkpoint-1",
         "--workers", "hold", "--body", "null"],
        ["ctx", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "body-scalar", "--checkpoint", "checkpoint-1",
         "--workers", "hold", "--body", '"ctx"'],
        ["handoff", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "missing-handoff-checkpoint"],
        ["handoff", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "handoff-workers", "--checkpoint", "checkpoint-1",
         "--workers", "hold"],
        ["handoff", "build", "--socket", "{socket}", "--generation", "7",
         "--request-id", "handoff-profile", "--checkpoint", "checkpoint-1",
         "--profile", "team-b"],
    ],
    ids=[
        "ctx-missing-checkpoint",
        "ctx-missing-workers",
        "ctx-unsupported-policy",
        "ctx-rebind-policy",
        "ctx-restart-mapping",
        "ctx-restart-null-mapping",
        "ctx-restart-positional-mapping",
        "ctx-body-mapping",
        "ctx-body-null-mapping",
        "ctx-body-worker-mapping",
        "ctx-body-rebind-mapping",
        "ctx-body-rebind-policy",
        "ctx-body-list",
        "ctx-body-null",
        "ctx-body-scalar",
        "handoff-missing-checkpoint",
        "handoff-has-workers",
        "handoff-has-profile",
    ],
)
def test_t020_missing_or_ambiguous_context_inputs_refuse_without_handler(
        tmp_path, args):
    api = _load_cli()
    socket_path = tmp_path / "t020-invalid.sock"
    rendered_args = [
        str(socket_path) if value == "{socket}" else value for value in args
    ]
    called = []

    def handler(request):
        called.append(request)
        return {"ok": True}

    return_code, output, error = _call_main(api, rendered_args, handler)
    assert isinstance(return_code, int) and return_code != 0
    assert not called, "invalid ctx/handoff input reached the handler"
    assert "invalid" in (output + error).lower() or return_code == 2


def test_ctx_body_policy_override_cannot_bypass_explicit_worker_choice(tmp_path):
    api = _load_cli()
    socket_path = tmp_path / "ctx-policy-override.sock"
    seen = []

    def handler(request):
        seen.append(request)
        return {
            "ok": True,
            "phase": "ready-held",
            "generation": request["generation"],
            "result": {"checkpoint_queued": True},
        }

    args = _t020_cli_args("ctx", socket_path, "ctx-policy-override")
    args.extend(["--body", '{"worker_policy": "rebind"}'])
    return_code, output, error = _call_main(api, args, handler)

    assert isinstance(return_code, int) and return_code != 0
    assert not seen, "invalid body policy reached the handler"
    assert "invalid" in (output + error).lower() or return_code == 2


@pytest.mark.parametrize("policy", ["hold", "restart"], ids=["hold", "restart"])
def test_ctx_forwards_explicit_checkpoint_and_worker_policy_without_prompt(
        tmp_path, policy):
    api = _load_cli()
    socket_path = tmp_path / ("ctx-" + policy + ".sock")
    seen = []

    def handler(request):
        seen.append(request)
        assert request["operation"] == "ctx"
        body = request["body"]
        assert body["checkpoint"] == "checkpoint-1"
        assert body == {
            "checkpoint": "checkpoint-1",
            "worker_policy": policy,
        }
        assert "profile" not in body
        assert "prompt" not in body
        return {
            "ok": True,
            "phase": "ready-held",
            "generation": request["generation"],
            "result": {"worker_policy": policy, "checkpoint_queued": True},
        }

    args = (
        _t020_cli_args("ctx", socket_path, "ctx-" + policy)
        if policy == "hold"
        else _t020_ctx_restart_args(socket_path, "ctx-restart")
    )
    return_code, output, error = _call_main(api, args, handler)
    assert return_code == 0, error
    assert not error
    assert len(seen) == 1
    assert seen[0]["request_id"] == args[args.index("--request-id") + 1]
    assert "prompt" not in output.lower()


def test_handoff_is_checkpoint_only_and_preserves_released_lifecycle(tmp_path):
    api = _load_cli()
    socket_path = tmp_path / "handoff.sock"
    state = {
        "lifecycle": "released",
        "dispatch_gate": "open",
        "dispatch_count": 3,
        "writer_claims": ["worker-a"],
        "prompt_calls": [],
    }
    before = json.loads(json.dumps(state))
    seen = []

    def handler(request):
        seen.append(request)
        assert request["operation"] == "handoff"
        assert request["body"] == {"checkpoint": "checkpoint-1"}
        assert state == before
        return {
            "ok": True,
            "phase": state["lifecycle"],
            "generation": request["generation"],
            "result": {
                "checkpoint": request["body"]["checkpoint"],
                "dispatch_gate": state["dispatch_gate"],
                "lifecycle": state["lifecycle"],
                "dispatch_count": state["dispatch_count"],
            },
        }

    return_code, output, error = _call_main(
        api, _t020_cli_args("handoff", socket_path, "handoff-only"), handler,
    )
    assert return_code == 0, error
    assert not error
    assert seen and seen[0]["body"] == {"checkpoint": "checkpoint-1"}
    assert state == before
    assert "released" in output
    assert "open" in output
    assert "prompt" not in output.lower()


def test_ctx_hold_queues_checkpoint_until_an_explicit_release_without_prompt(
        tmp_path):
    api = _load_cli()
    socket_path = tmp_path / "ctx-release.sock"
    state = {
        "lifecycle": "held",
        "dispatch_gate": "closed",
        "queued_checkpoints": [],
        "dispatch_count": 0,
        "release_count": 0,
        "prompt_calls": [],
        "profile": "current-profile",
    }
    seen = []

    def handler(request):
        seen.append(request)
        body = request["body"]
        if request["operation"] == "ctx":
            assert body == {
                "checkpoint": "checkpoint-1",
                "worker_policy": "hold",
            }
            assert state["lifecycle"] == "held"
            assert state["dispatch_gate"] == "closed"
            assert state["dispatch_count"] == 0
            assert "prompt" not in body
            state["queued_checkpoints"].append(body["checkpoint"])
            state["lifecycle"] = "ready-held"
            return {
                "ok": True,
                "phase": "ready-held",
                "generation": request["generation"],
                "result": {"checkpoint_queued": True, "dispatch_count": 0},
            }
        assert request["operation"] == "release"
        assert body == {}
        assert state["queued_checkpoints"] == ["checkpoint-1"]
        assert state["dispatch_count"] == 0
        state["release_count"] += 1
        state["dispatch_count"] += 1
        state["lifecycle"] = "released"
        state["dispatch_gate"] = "open"
        return {
            "ok": True,
            "phase": "released",
            "generation": request["generation"],
            "result": {"dispatch_count": state["dispatch_count"]},
        }

    ctx_rc, ctx_output, ctx_error = _call_main(
        api, _t020_cli_args("ctx", socket_path, "ctx-hold"), handler,
    )
    assert ctx_rc == 0, ctx_error
    assert state["lifecycle"] == "ready-held"
    assert state["dispatch_gate"] == "closed"
    assert state["dispatch_count"] == 0
    assert state["release_count"] == 0
    assert state["prompt_calls"] == []
    assert "prompt" not in ctx_output.lower()

    release_rc, release_output, release_error = _call_main(
        api, _common_cli_args("release", socket_path, "release-after-ctx"), handler,
    )
    assert release_rc == 0, release_error
    assert state["lifecycle"] == "released"
    assert state["dispatch_gate"] == "open"
    assert state["dispatch_count"] == 1
    assert state["release_count"] == 1
    assert state["prompt_calls"] == []
    assert "prompt" not in release_output.lower()
    assert [request["operation"] for request in seen] == ["ctx", "release"]


@pytest.mark.parametrize(
    "first,second",
    [
        ("swap", "ctx"),
        ("swap", "handoff"),
        ("ctx", "swap"),
        ("ctx", "handoff"),
        ("handoff", "swap"),
        ("handoff", "ctx"),
    ],
    ids=[
        "swap-ctx", "swap-handoff", "ctx-swap", "ctx-handoff",
        "handoff-swap", "handoff-ctx",
    ],
)
def test_concurrent_t020_operations_share_one_serialized_handler_boundary(
        tmp_path, first, second):
    """Concurrent operation calls cannot overlap a mutation in the handler."""
    api = _load_cli()
    # Avoid interleaved JSON output from the two deliberately concurrent main
    # calls; the request/response and exit mapping remain under test below.
    api["_print_response"] = lambda _response: None
    socket_path = tmp_path / (first + "-" + second + ".sock")
    first_id = "concurrent-first"
    second_id = "concurrent-second"
    lock = threading.Lock()
    first_entered = threading.Event()
    first_release = threading.Event()
    second_started = threading.Event()
    calls = []
    active = []
    busy_refusals = []

    def handler(request):
        request_id = request["request_id"]
        with lock:
            calls.append((request["operation"], request_id))
            if active:
                # A real controller would make this the stable busy refusal;
                # it must not allow a second mutation to overlap the first.
                busy_refusals.append((active[0], request_id))
                return {
                    "ok": False,
                    "phase": "held",
                    "generation": request["generation"],
                    "refusal_code": "busy",
                }
            active.append(request_id)
            if request_id == first_id:
                first_entered.set()
        if request_id == first_id:
            assert first_release.wait(1.0)
        with lock:
            active.remove(request_id)
        return {
            "ok": True,
            "phase": "ready-held",
            "generation": request["generation"],
            "result": {"operation": request["operation"]},
        }

    results = {}

    def invoke(label, args):
        if label == "second":
            second_started.set()
        results[label] = api["main"](args, handler=handler)

    first_thread = threading.Thread(
        target=invoke,
        args=("first", _t020_cli_args(first, socket_path, first_id)),
        name="t020-first-operation",
    )
    second_thread = threading.Thread(
        target=invoke,
        args=("second", _t020_cli_args(second, socket_path, second_id)),
        name="t020-second-operation",
    )
    first_thread.start()
    assert first_entered.wait(1.0)
    second_thread.start()
    assert second_started.wait(1.0)
    # Let a real serialized implementation either refuse the second request
    # as busy or queue it behind the first.  In both cases the first mutation
    # remains the only active one until its explicit test release.
    time.sleep(0.03)
    first_release.set()
    first_thread.join(timeout=1.5)
    second_thread.join(timeout=1.5)
    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert results["first"] == 0
    assert results["second"] in {0, 3}
    assert busy_refusals or results["second"] == 0
    assert [operation for operation, _request_id in calls] == [first, second]


@pytest.mark.parametrize("operation", ["swap", "ctx", "handoff"],
                         ids=["swap", "ctx", "handoff"])
def test_t020_stale_generation_refusal_is_stable_and_does_not_mutate(
        tmp_path, operation):
    api = _load_cli()
    socket_path = tmp_path / (operation + "-stale.sock")
    seen = []
    current_generation = 8

    def handler(request):
        seen.append(request)
        assert request["generation"] == 7
        return {
            "ok": False,
            "phase": "held",
            "generation": current_generation,
            "refusal_code": "stale-generation",
            "result": {"mutated": False},
        }

    api["_print_response"] = lambda response: None
    first_rc, _, first_error = _call_main(
        api, _t020_cli_args(operation, socket_path, "stale-" + operation), handler,
    )
    second_rc, _, second_error = _call_main(
        api, _t020_cli_args(operation, socket_path, "stale-" + operation + "-again"),
        handler,
    )
    assert first_rc == 4
    assert second_rc == first_rc
    assert not first_error
    assert not second_error
    assert len(seen) == 2
    assert all(request["generation"] == 7 for request in seen)
    assert all(request["operation"] == operation for request in seen)


def _call_ownership_main(api: dict, argv: list[str], state_store: Any,
                         requests: list | None = None, process_identity=None):
    """Run one internal ownership command through an injected state store."""
    def handler(request):
        if requests is not None:
            requests.append(request)
        kwargs = {"state_store": state_store}
        if process_identity is not None:
            kwargs["process_identity"] = process_identity
        return api["durable_ownership_handler"](request, **kwargs)

    return _call_main(api, argv, handler)


def _ownership_cli_args(operation: str, request_id: str) -> list[str]:
    """Internal commands intentionally omit --socket and use the state seam."""
    return [
        operation,
        "build",
        "--generation", "7",
        "--request-id", request_id,
    ]


@pytest.mark.parametrize("pending", [False, True], ids=["ordinary", "pending"])
def test_legacy_begin_forwards_exact_creator_args_and_redacts_pending_token(
        pending):
    api = _load_cli()
    calls = []
    requests = []
    creator_pid = 4201
    creator_token = "creator-start-token"
    creator_pgid = 4200
    request_id = "legacy-begin-pending" if pending else "legacy-begin-ordinary"

    def process_identity(requested_pid):
        assert requested_pid == creator_pid
        return {
            "pid": creator_pid,
            "start_token": creator_token,
            "pgid": creator_pgid,
        }

    class StateStore:
        owner_record = {}

        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            yield self

        def read_owner(self, deadline=None):
            return dict(self.owner_record)

        def begin_legacy(self, *, pid, start_token, pgid):
            calls.append((
                "ordinary",
                {"pid": pid, "start_token": start_token, "pgid": pgid},
            ))
            return {
                "mode": "legacy-lease",
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            }

        def begin_pending_launch(self, *, request_id, pid, start_token, pgid):
            calls.append((
                "pending",
                {
                    "request_id": request_id,
                    "pid": pid,
                    "start_token": start_token,
                    "pgid": pgid,
                },
            ))
            return {
                "mode": "pending-launch",
                "pid": pid,
                "request_id": request_id,
                "lease_id": "lease-pending-1",
                "start_token": start_token,
                "pgid": pgid,
            }

    argv = _ownership_cli_args("legacy-begin", request_id)
    argv.extend(["--pid", str(creator_pid)])
    if pending:
        argv.append("--pending-launch")
    return_code, output, error = _call_ownership_main(
        api, argv, StateStore(), requests, process_identity,
    )

    assert return_code == 0, error
    assert not error
    assert len(requests) == 1
    expected_body = {
        "pid": creator_pid,
    }
    if pending:
        expected_body["pending_launch"] = True
        expected_call = (
            "pending",
            {
                "request_id": request_id,
                "pid": creator_pid,
                "start_token": creator_token,
                "pgid": creator_pgid,
            },
        )
    else:
        expected_call = (
            "ordinary",
            {
                "pid": creator_pid,
                "start_token": creator_token,
                "pgid": creator_pgid,
            },
        )
    assert requests[0]["body"] == expected_body
    assert calls == [expected_call]

    response = json.loads(output)
    assert response["schema"] == 2
    assert response["schema_version"] == 2
    assert response["architecture"] == "native-coordinator-lineage"
    assert response["request_id"] == request_id
    assert response["ok"] is True
    assert "start_token" not in output
    assert len(api["encode_frame"](response)) <= api["MAX_FRAME_BYTES"]
    if pending:
        assert response["result"]["lease_id"] == "lease-pending-1"
        assert "start_token" not in response["result"]
        assert response["result"]["pgid"] == creator_pgid
    else:
        assert response["result"]["mode"] == "legacy-lease"
        assert response["result"]["pgid"] == creator_pgid


def test_pending_launch_bind_forwards_exact_lease_and_allows_new_pid_token():
    api = _load_cli()
    creator_pid = 4201
    creator_token = "creator-start-token"
    creator_pgid = 4200
    target_pid = 9307
    target_token = "verified-launch-token"
    target_pgid = 9300
    calls = []
    requests = []

    def process_identity(requested_pid):
        if requested_pid == creator_pid:
            return {
                "pid": creator_pid,
                "start_token": creator_token,
                "pgid": creator_pgid,
                "parent_pid": target_pid,
            }
        assert requested_pid == target_pid
        return {
            "pid": target_pid,
            "start_token": target_token,
            "pgid": target_pgid,
        }

    class StateStore:
        owner_record = {
            "mode": "pending-launch",
            "lease_id": "lease-pending-1",
            "pid": creator_pid,
            "start_token": creator_token,
            "request_id": "bind-1",
        }

        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            yield self

        def read_owner(self):
            return dict(self.owner_record)

        def bind_pending_launch(self, *, lease_id, pid, start_token, pgid):
            assert pid != creator_pid
            assert start_token != creator_token
            assert pgid != creator_pgid
            calls.append({
                "lease_id": lease_id,
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            })
            return {
                "mode": "legacy-lease",
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            }

    argv = _ownership_cli_args("pending-launch-bind", "bind-1")
    argv.extend([
        "--lease-id", "lease-pending-1",
        "--pid", str(target_pid),
    ])
    return_code, output, error = _call_ownership_main(
        api, argv, StateStore(), requests, process_identity,
    )

    assert return_code == 0, error
    assert not error
    assert requests[0]["body"] == {
        "lease_id": "lease-pending-1",
        "pid": target_pid,
    }
    assert calls == [{
        "lease_id": "lease-pending-1",
        "pid": target_pid,
        "start_token": target_token,
        "pgid": target_pgid,
    }]
    response = json.loads(output)
    assert response["ok"] is True
    assert response["result"]["mode"] == "legacy-lease"
    assert response["result"]["pid"] == target_pid
    assert response["result"]["pgid"] == target_pgid
    assert "start_token" not in output


def test_pending_launch_abort_forwards_only_the_exact_lease_id():
    api = _load_cli()
    calls = []
    requests = []

    class StateStore:
        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            yield self

        def abort_pending_launch(self, *, lease_id):
            calls.append(lease_id)
            return {}

    argv = _ownership_cli_args("pending-launch-abort", "abort-1")
    argv.extend(["--lease-id", "lease-pending-1"])
    return_code, output, error = _call_ownership_main(
        api, argv, StateStore(), requests,
    )

    assert return_code == 0, error
    assert not error
    assert requests[0]["body"] == {"lease_id": "lease-pending-1"}
    assert calls == ["lease-pending-1"]
    response = json.loads(output)
    assert response["ok"] is True
    assert response["result"] == {}


@pytest.mark.parametrize(
    "args",
    [
        ["legacy-begin", "--pid", "0"],
        ["legacy-begin", "--pid", "not-a-pid"],
        ["legacy-begin", "--pid", "42"],
        ["legacy-begin", "--pid", "42", "--start-token", "token"],
        ["legacy-begin", "--pid", "42", "--body-json", '{"start_token":"token"}'],
        ["pending-launch-bind", "--lease-id", "lease", "--pid", "42"],
        ["pending-launch-bind", "--lease-id", "lease", "--pid", "42",
         "--start-token", "token"],
        ["pending-launch-bind", "--lease-id", "", "--pid", "42"],
        ["pending-launch-bind", "--lease-id", "lease", "--body-json",
         '{"start_token":"token"}', "--pid", "42"],
        ["pending-launch-abort"],
        ["pending-launch-abort", "--lease-id", "",],
        ["pending-launch-abort", "--lease-id", "lease", "--body-json",
         '{"start_token":"token"}'],
    ],
    ids=[
        "begin-zero-pid",
        "begin-noninteger-pid",
        "begin-missing-pid",
        "begin-start-token-option-rejected",
        "begin-body-token-rejected",
        "bind-missing-pid",
        "bind-start-token-option-rejected",
        "bind-empty-lease",
        "bind-body-token-rejected",
        "abort-missing-lease",
        "abort-empty-lease",
        "abort-body-token-rejected",
    ],
)
def test_internal_ownership_commands_refuse_malformed_args_without_state_call(
        args):
    api = _load_cli()
    state_calls = []

    class StateStore:
        def begin_legacy(self, **kwargs):
            state_calls.append(("begin", kwargs))
            return {}

        def begin_pending_launch(self, **kwargs):
            state_calls.append(("pending", kwargs))
            return {}

        def bind_pending_launch(self, **kwargs):
            state_calls.append(("bind", kwargs))
            return {}

        def abort_pending_launch(self, **kwargs):
            state_calls.append(("abort", kwargs))
            return {}

    argv = [args[0], "build", "--generation", "7", "--request-id", "bad-args"]
    argv.extend(args[1:])
    return_code, output, error = _call_ownership_main(
        api, argv, StateStore(),
    )
    assert isinstance(return_code, int) and return_code != 0
    assert not state_calls


def test_internal_ownership_state_failure_has_stable_sanitized_error():
    api = _load_cli()
    secret = "state-secret-that-must-not-leak"
    pid = 42
    token = "state-error-token"
    pgid = 41

    def process_identity(requested_pid):
        assert requested_pid == pid
        return {"pid": pid, "start_token": token, "pgid": pgid}

    class FailingStateStore:
        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            yield self

        def read_owner(self):
            return {}

        def begin_legacy(self, **_kwargs):
            raise RuntimeError(secret)

    argv = _ownership_cli_args("legacy-begin", "state-error")
    argv.extend(["--pid", str(pid)])
    first_rc, first_output, first_error = _call_ownership_main(
        api, argv, FailingStateStore(), process_identity=process_identity,
    )
    second_rc, second_output, second_error = _call_ownership_main(
        api, argv, FailingStateStore(), process_identity=process_identity,
    )

    assert first_rc == second_rc == 1
    assert first_output == second_output
    assert first_error == second_error == ""
    assert "unknown" in first_output
    assert secret not in first_output + first_error


def _call_ownership_main_with_identity(
        api: dict, argv: list[str], state_store: Any, process_identity,
        requests: list | None = None):
    """Run an ownership command with the one explicit process-identity seam."""
    def handler(request):
        if requests is not None:
            requests.append(request)
        return api["durable_ownership_handler"](
            request,
            state_store=state_store,
            process_identity=process_identity,
        )

    return _call_main(api, argv, handler)


def test_matching_process_identity_permits_legacy_begin_without_alias_fallback():
    """A live PID yields the token and process group persisted by begin."""
    api = _load_cli()
    pid = 5101
    token = "live-creator-token"
    pgid = 5100
    identities = {pid: {"pid": pid, "start_token": token, "pgid": pgid}}
    identity_calls = []
    state_calls = []

    def process_identity(requested_pid):
        identity_calls.append(requested_pid)
        return identities.get(requested_pid)

    class StateStore:
        owner_record = {}

        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            yield self

        def read_owner(self):
            return dict(self.owner_record)

        def begin_legacy(self, *, pid, start_token, pgid):
            state_calls.append({
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            })
            return {"mode": "legacy-lease", "pid": pid}

    argv = _ownership_cli_args("legacy-begin", "identity-begin")
    argv.extend(["--pid", str(pid)])
    return_code, output, error = _call_ownership_main_with_identity(
        api, argv, StateStore(), process_identity,
    )

    assert return_code == 0, error
    assert not error
    assert identity_calls == [pid]
    assert state_calls == [{"pid": pid, "start_token": token, "pgid": pgid}]
    response = json.loads(output)
    assert response["ok"] is True
    assert response["result"]["mode"] == "legacy-lease"


def test_matching_process_identity_permits_bind_to_a_different_live_holder():
    """The verified launcher may differ from the pending creator identity."""
    api = _load_cli()
    creator_pid = 5101
    creator_token = "creator-token"
    creator_pgid = 5100
    target_pid = 5202
    target_token = "launcher-token"
    target_pgid = 5200
    identities = {
        creator_pid: {
            "pid": creator_pid,
            "start_token": creator_token,
            "pgid": creator_pgid,
        },
        target_pid: {
            "pid": target_pid,
            "start_token": target_token,
            "pgid": target_pgid,
        },
    }
    identity_calls = []
    state_calls = []

    def process_identity(requested_pid):
        identity_calls.append(requested_pid)
        result = identities.get(requested_pid)
        if requested_pid == creator_pid and result is not None:
            result = dict(result, parent_pid=target_pid)
        return result

    class StateStore:
        owner_record = {
            "mode": "pending-launch",
            "lease_id": "lease-identity",
            "pid": creator_pid,
            "start_token": creator_token,
            "request_id": "identity-bind",
        }

        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            yield self

        def read_owner(self):
            return dict(self.owner_record)

        def bind_pending_launch(self, *, lease_id, pid, start_token, pgid):
            assert pid == target_pid and pid != creator_pid
            assert start_token == target_token and start_token != creator_token
            assert pgid == target_pgid and pgid != creator_pgid
            state_calls.append({
                "lease_id": lease_id,
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            })
            return {"mode": "legacy-lease", "pid": pid}

    argv = _ownership_cli_args("pending-launch-bind", "identity-bind")
    argv.extend([
        "--lease-id", "lease-identity",
        "--pid", str(target_pid),
    ])
    return_code, output, error = _call_ownership_main_with_identity(
        api, argv, StateStore(), process_identity,
    )

    assert return_code == 0, error
    assert not error
    assert identity_calls == [creator_pid, target_pid]
    assert state_calls == [{
        "lease_id": "lease-identity",
        "pid": target_pid,
        "start_token": target_token,
        "pgid": target_pgid,
    }]
    response = json.loads(output)
    assert response["ok"] is True
    assert response["result"]["pid"] == target_pid


def test_local_pid_identity_derives_token_and_pgid_without_cli_alias():
    """The real verifier supplies both durable identity fields from our PID."""
    api = _load_cli()
    pid = os.getpid()
    live, expected_token, expected_pgid = api["_process_identity"](pid)
    assert live is True
    assert isinstance(expected_token, str) and expected_token
    assert isinstance(expected_pgid, int) and expected_pgid > 0
    calls = []

    class StateStore:
        owner_record = {}

        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            yield self

        def read_owner(self):
            return dict(self.owner_record)

        def begin_legacy(self, *, pid, start_token, pgid):
            calls.append({
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            })
            return {
                "mode": "legacy-lease",
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            }

    request = _request(
        operation="legacy-begin",
        request_id="local-pid-agreement",
        pid=pid,
    )
    result = api["durable_ownership_handler"](
        request,
        state_store=StateStore(),
    )

    assert calls == [{
        "pid": pid,
        "start_token": expected_token,
        "pgid": expected_pgid,
    }]
    assert result["ok"] is True
    assert result["result"]["pid"] == pid
    assert result["result"]["pgid"] == expected_pgid
    assert "start_token" not in json.dumps(result)


def test_runtime_discovery_uses_exact_read_runtime_and_validates_pgid(tmp_path):
    """Runtime discovery is read-only and binds the endpoint to one PGID."""
    api = _load_cli()
    local_process_domain = api["_current_process_domain"]()
    runtime_parent = tmp_path / "runtime"
    runtime_parent.mkdir(mode=0o700)
    socket_path = runtime_parent / "daemon.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(socket_path))
    socket_path.chmod(0o600)
    listener.listen(1)
    try:
        pid = 6101
        pgid = 6100
        token = "runtime-start-token"
        runtime = {
            "version": 1,
            "daemon_id": "daemon-1",
            "generation": 7,
            "lane": "build",
            "lane_key": "build",
            "host": "test-host",
            "pid": pid,
            "start_token": token,
            "pgid": pgid,
            "process_domain": local_process_domain,
            "socket_path": str(socket_path),
            "timestamp": 1.0,
        }
        owner = {
            "mode": "managed",
            "daemon_id": "daemon-1",
            "generation": 7,
            "lane": "build",
            "lane_key": "build",
            "host": "test-host",
            "process_domain": local_process_domain,
            "created_at": 1.0,
        }
        identity_calls = []

        def process_identity(requested_pid):
            identity_calls.append(requested_pid)
            return {"pid": pid, "start_token": token, "pgid": pgid}

        class StateStore:
            def __init__(self, value, owner_value=None):
                self.value = value
                self.reads = 0
                self.read_deadlines = []
                self.owner_value = dict(owner if owner_value is None else owner_value)

            def read_owner(self, *, deadline=None):
                self.read_deadlines.append(("owner", deadline))
                return dict(self.owner_value)

            def read_runtime(self, *, deadline=None):
                self.read_deadlines.append(("runtime", deadline))
                self.reads += 1
                return dict(self.value)

            def read_daemon_runtime(self):
                raise AssertionError("legacy runtime alias must not be called")

            def read_json(self, *_args):
                raise AssertionError("filesystem JSON alias must not be called")

        request = _request(operation="status", request_id="runtime-read")
        store = StateStore(runtime)
        discovery_deadline = time.monotonic() + 1.0
        discovered = api["_read_runtime_discovery"](
            request,
            state_store=store,
            process_identity=process_identity,
            deadline=discovery_deadline,
        )
        assert discovered == (socket_path, runtime)
        assert store.reads == 1
        assert identity_calls == [pid]
        assert store.read_deadlines == [
            ("runtime", discovery_deadline), ("owner", discovery_deadline),
        ]

        bad_group = dict(runtime, pgid=pgid + 1)
        with pytest.raises(BaseException) as raised:
            api["_read_runtime_discovery"](
                request,
                state_store=StateStore(bad_group),
                process_identity=process_identity,
            )
        assert getattr(raised.value, "code", None) == "ownership-conflict"

        malformed_group = dict(runtime, pgid="not-a-pgid")
        with pytest.raises(BaseException) as raised:
            api["_read_runtime_discovery"](
                request,
                state_store=StateStore(malformed_group),
                process_identity=process_identity,
            )
        assert getattr(raised.value, "code", None) == "invalid"

        foreign_runtime = dict(runtime, process_domain="foreign:pid:[999]")
        with pytest.raises(BaseException) as raised:
            api["_read_runtime_discovery"](
                request,
                state_store=StateStore(foreign_runtime),
                process_identity=process_identity,
            )
        assert getattr(raised.value, "code", None) == "unknown"

        missing_runtime = dict(runtime)
        missing_runtime.pop("process_domain")
        with pytest.raises(BaseException) as raised:
            api["_read_runtime_discovery"](
                request,
                state_store=StateStore(missing_runtime),
                process_identity=process_identity,
            )
        assert getattr(raised.value, "code", None) == "invalid"

        foreign_owner = dict(owner, process_domain="foreign:pid:[999]")
        with pytest.raises(BaseException) as raised:
            api["_read_runtime_discovery"](
                request,
                state_store=StateStore(runtime, foreign_owner),
                process_identity=process_identity,
            )
        assert getattr(raised.value, "code", None) == "unknown"

        missing_owner = dict(owner)
        missing_owner.pop("process_domain")
        with pytest.raises(BaseException) as raised:
            api["_read_runtime_discovery"](
                request,
                state_store=StateStore(runtime, missing_owner),
                process_identity=process_identity,
            )
        assert getattr(raised.value, "code", None) == "invalid"
    finally:
        listener.close()
        socket_path.unlink(missing_ok=True)


def test_default_socket_path_is_short_deterministic_and_owner_private(tmp_path):
    """Long workspace identities still yield one safe AF_UNIX endpoint."""
    api = _load_cli()
    long_common_dir = tmp_path / ("workspace-" + ("x" * 36)) / ("common-" + ("y" * 36))
    long_common_dir.mkdir(parents=True, mode=0o700)
    runtime_base = Path(tempfile.mkdtemp(prefix="openrepotools-cli-", dir="/tmp"))
    runtime_base.chmod(0o700)

    class Identity:
        common_dir = long_common_dir
        host = "test-host"

    class StateStore:
        identity = Identity()

    env = {"XDG_RUNTIME_DIR": str(runtime_base)}
    first = api["_default_socket_path"](
        "Build", env=env, state_store=StateStore()
    )
    second = api["_default_socket_path"](
        "build", env=env, state_store=StateStore()
    )
    assert first == second
    assert first.is_absolute()
    assert len(os.fsencode(str(first))) < 104

    api["_prepare_socket_parent"](first)
    parent_info = os.lstat(first.parent)
    assert stat.S_ISDIR(parent_info.st_mode)
    assert stat.S_IMODE(parent_info.st_mode) == 0o700
    if hasattr(os, "getuid"):
        assert parent_info.st_uid == os.getuid()
    current = first.parent
    while current != current.parent:
        assert not current.is_symlink(), "socket path has a symlink ancestor"
        current = current.parent
    runtime_base.rmdir()


def test_start_boot_uses_one_absolute_deadline_across_spawn_discovery_and_connect(
        tmp_path):
    """Boot never replenishes the operation budget after a slow spawn."""
    api = _load_cli()
    events = []

    class Clock:
        def __init__(self):
            self.now = 100.0

        def monotonic(self):
            return self.now

    clock = Clock()

    class StateStore:
        pass

    def resolve_state_store(_request):
        events.append(("resolve", clock.monotonic()))
        return StateStore()

    def read_runtime(request, *, state_store, deadline):
        assert request["operation"] == "start"
        assert isinstance(state_store, StateStore)
        events.append(("discover", deadline))
        return None

    socket_path = tmp_path / "managed.sock"

    def default_socket_path(_lane, *, state_store):
        assert isinstance(state_store, StateStore)
        return socket_path

    def spawn_and_discover(request, *, socket_path, connect_timeout, deadline,
                           state_store):
        assert request["operation"] == "start"
        assert socket_path == socket_path_arg
        assert connect_timeout == 0.1
        assert isinstance(state_store, StateStore)
        events.append(("spawn", deadline))
        clock.now += 0.08
        return socket_path

    socket_path_arg = socket_path

    def request_socket(path, request, *, connect_timeout, operation_timeout):
        assert path == socket_path_arg
        assert request["operation"] == "start"
        events.append(("connect", connect_timeout, operation_timeout))
        return {"ok": True, "result": {"started": True}}

    original_time = api["time"]
    original_resolve = api["_resolve_state_store"]
    original_discover = api["_read_runtime_discovery"]
    original_default = api["_default_socket_path"]
    original_spawn = api["_spawn_supervisor_and_discover"]
    original_request = api["request_socket"]
    api["time"] = clock
    api["_resolve_state_store"] = resolve_state_store
    api["_read_runtime_discovery"] = read_runtime
    api["_default_socket_path"] = default_socket_path
    api["_spawn_supervisor_and_discover"] = spawn_and_discover
    api["request_socket"] = request_socket
    try:
        return_code, output, error = _call_main(
            api,
            [
                "start", "build", "--opt-in", "--connect-timeout", "0.1",
                "--operation-timeout", "0.2", "--request-id", "boot-deadline",
            ],
            handler=None,
        )
    finally:
        api["time"] = original_time
        api["_resolve_state_store"] = original_resolve
        api["_read_runtime_discovery"] = original_discover
        api["_default_socket_path"] = original_default
        api["_spawn_supervisor_and_discover"] = original_spawn
        api["request_socket"] = original_request

    assert return_code == 0, (output, error)
    assert not error
    assert [event[0] for event in events] == ["resolve", "discover", "spawn", "connect"]
    discovery_deadline = events[1][1]
    spawn_deadline = events[2][1]
    assert discovery_deadline == spawn_deadline
    assert events[3][1] <= 0.1
    assert events[3][2] < 0.2
    assert events[3][2] <= spawn_deadline - clock.now + 1e-9


def test_default_socket_path_resolves_trusted_os_tmp_before_private_namespace(
        monkeypatch):
    """The trusted system temp root is canonicalized before owner isolation."""
    if not hasattr(os, "getuid"):
        pytest.skip("owner-private Unix temp namespace requires getuid")
    api = _load_cli()

    class Identity:
        common_dir = Path("/tmp")
        host = "test-host"

    class StateStore:
        identity = Identity()

    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    prepared = []
    original_prepare = api["_prepare_socket_parent"]
    api["_prepare_socket_parent"] = lambda path: prepared.append(path)
    try:
        path = api["_default_socket_path"](
            "build", state_store=StateStore(), env={}
        )
    finally:
        api["_prepare_socket_parent"] = original_prepare

    canonical_tmp = Path("/tmp").resolve()
    expected_parent = canonical_tmp / ("openrepotools-managed-%d" % os.getuid())
    assert prepared == [path]
    assert path.parent == expected_parent
    assert not path.parent.is_symlink()
    assert len(os.fsencode(str(path))) < 104


def test_symlink_inside_private_namespace_and_runtime_endpoint_refuse(
        tmp_path):
    """Neither a private-directory alias nor an endpoint alias is trusted."""
    api = _load_cli()
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    nested = private / "nested"
    nested.mkdir(mode=0o700)
    namespace_alias = private / "nested-alias"
    namespace_alias.symlink_to(nested, target_is_directory=True)

    class Identity:
        common_dir = tmp_path / "common"
        host = "test-host"

    class StateStore:
        identity = Identity()

    Identity.common_dir.mkdir(mode=0o700)
    with pytest.raises(BaseException) as raised:
        api["_default_socket_path"](
            "build",
            env={"XDG_RUNTIME_DIR": str(namespace_alias)},
            state_store=StateStore(),
        )
    assert getattr(raised.value, "code", None) in {
        "permission-mismatch", "permission",
    }

    real_socket = nested / "real.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(real_socket))
    real_socket.chmod(0o600)
    listener.listen(1)
    endpoint_alias = private / "endpoint.sock"
    endpoint_alias.symlink_to(real_socket)
    try:
        with pytest.raises(BaseException) as raised:
            api["request_socket"](
                endpoint_alias,
                _request(request_id="endpoint-alias"),
                connect_timeout=0.1,
                operation_timeout=0.1,
            )
        assert getattr(raised.value, "code", None) in {
            "permission-mismatch", "permission",
        }
    finally:
        listener.close()
        real_socket.unlink(missing_ok=True)


def test_supervisor_enrolls_and_publishes_runtime_before_transport_start(tmp_path):
    """Durable ownership may lead transport, but no socket is implied by it."""
    daemon_namespace = runpy.run_path(
        str(REPO / "lane_managed_daemon.py"),
        run_name="lane_managed_daemon_startup_test",
    )
    # As with the executable loader above, use the function's authoritative
    # globals so the injected identity and transport seams are observed by
    # ``run_supervisor``.  ``runpy.run_path`` may return a shallow copy of
    # the execution namespace while function globals retain the original.
    daemon_api = daemon_namespace["run_supervisor"].__globals__
    socket_path = tmp_path / "runtime" / "managed.sock"
    socket_path.parent.mkdir(mode=0o700)
    events = []

    class StateStore:
        def enroll_managed(self, daemon_id, process_domain=None):
            events.append(("enroll", daemon_id, socket_path.exists()))
            return {
                "mode": "managed",
                "daemon_id": daemon_id,
                "generation": 7,
                "lane": "build",
                "lane_key": "build",
                "process_domain": process_domain,
            }

        def register_runtime(self, **kwargs):
            events.append(("runtime", dict(kwargs), socket_path.exists()))
            return {
                "version": 1,
                "daemon_id": kwargs["daemon_id"],
                "generation": kwargs["generation"],
                "lane": "build",
                "lane_key": "build",
                "host": "test-host",
                "pid": kwargs["pid"],
                "start_token": kwargs["start_token"],
                "pgid": kwargs["pgid"],
                "socket_path": str(socket_path),
                "timestamp": 1.0,
            }

        def clear_runtime(self, **kwargs):
            events.append(("clear", dict(kwargs), socket_path.exists()))
            return {}

    class Projection:
        def preflight(self, context):
            events.append(("preflight", dict(context), socket_path.exists()))
            return True

        def managed_owner(self, context):
            events.append(("projection", dict(context), socket_path.exists()))
            return True

    def current_process_identity():
        return 7401, "supervisor-start-token", 7400

    def fake_transport(path, _handler, **kwargs):
        events.append(("transport", path, kwargs, socket_path.exists()))
        assert path == socket_path
        assert not socket_path.exists()
        ready = kwargs.get("on_ready")
        assert callable(ready)
        events.append(("on-ready", socket_path.exists()))
        ready()
        return []

    original_identity = daemon_api["_current_process_identity"]
    original_transport = daemon_api["serve_daemon"]
    daemon_api["_current_process_identity"] = current_process_identity
    daemon_api["serve_daemon"] = fake_transport
    try:
        result = daemon_api["run_supervisor"](
            "build",
            socket_path,
            "daemon-startup",
            True,
            state=StateStore(),
            projection=Projection(),
        )
    finally:
        daemon_api["_current_process_identity"] = original_identity
        daemon_api["serve_daemon"] = original_transport

    assert result == []
    assert [event[0] for event in events] == [
        "preflight", "enroll", "projection", "transport", "on-ready",
        "runtime", "clear",
    ]
    assert events[0][2] is False
    assert events[1][2] is False
    assert events[2][2] is False
    assert events[3][3] is False
    assert events[4][1] is False
    assert events[5][2] is False
    assert events[6][2] is False
    assert events[1][1] == "daemon-startup"
    assert events[2][1]["daemon_id"] == "daemon-startup"
    assert events[5][1]["daemon_id"] == "daemon-startup"
    assert events[6][1]["daemon_id"] == "daemon-startup"


def test_transport_socket_is_not_connectable_between_bind_chmod_and_listen(
        tmp_path):
    """The endpoint becomes usable only after mode 0600 and listen ordering."""
    api = _load_cli()
    real_socket_module = api["socket"]
    real_os_module = api["os"]
    socket_path = tmp_path / "runtime" / "readiness.sock"
    events = []

    class TracedServerSocket:
        def __init__(self, inner):
            self.inner = inner

        def bind(self, path):
            result = self.inner.bind(path)
            info = Path(path).lstat()
            events.append((
                "bind", Path(path).exists(), stat.S_IMODE(info.st_mode),
            ))
            return result

        def listen(self, backlog):
            info = socket_path.lstat()
            events.append(("before-listen", stat.S_IMODE(info.st_mode)))
            probe = real_socket_module.socket(
                real_socket_module.AF_UNIX, real_socket_module.SOCK_STREAM,
            )
            try:
                probe.settimeout(0.05)
                try:
                    probe.connect(str(socket_path))
                except OSError:
                    events.append(("pre-listen-connect", "refused"))
                else:
                    events.append(("pre-listen-connect", "connected"))
            finally:
                probe.close()
            result = self.inner.listen(backlog)
            info = socket_path.lstat()
            events.append(("listen", stat.S_IMODE(info.st_mode)))
            return result

        def __getattr__(self, name):
            return getattr(self.inner, name)

    class SocketProxy:
        AF_UNIX = real_socket_module.AF_UNIX
        SOCK_STREAM = real_socket_module.SOCK_STREAM

        def __init__(self):
            self.created = 0

        def socket(self, *args, **kwargs):
            self.created += 1
            inner = real_socket_module.socket(*args, **kwargs)
            if self.created == 1:
                return TracedServerSocket(inner)
            return inner

        def __getattr__(self, name):
            return getattr(real_socket_module, name)

    class OSProxy:
        def chmod(self, path, mode, *args, **kwargs):
            result = real_os_module.chmod(path, mode, *args, **kwargs)
            info = Path(path).lstat()
            events.append(("chmod", Path(path).exists(), stat.S_IMODE(info.st_mode)))
            return result

        def __getattr__(self, name):
            return getattr(real_os_module, name)

    socket_proxy = SocketProxy()
    api["socket"] = socket_proxy
    api["os"] = OSProxy()
    try:
        thread, errors, _ = _start_server(
            api,
            socket_path,
            lambda _request: {"ok": True, "result": {"ready": True}},
            serve_name="serve_daemon",
            max_requests=1,
            connect_timeout=0.5,
            operation_timeout=1.0,
        )
        deadline = time.monotonic() + 1.0
        while not any(event[0] == "listen" for event in events):
            assert time.monotonic() < deadline, "server did not reach listen"
            time.sleep(0.005)
        response = api["request_socket"](
            socket_path,
            _request(request_id="readiness-after-listen"),
            connect_timeout=0.5,
            operation_timeout=1.0,
        )
        _join_server(thread, errors)
    finally:
        api["socket"] = real_socket_module
        api["os"] = real_os_module
        socket_path.unlink(missing_ok=True)

    assert response["ok"] is True
    labels = [event[0] for event in events]
    assert labels == ["bind", "chmod", "before-listen", "pre-listen-connect", "listen"]
    assert events[0][1] is True
    assert events[1][1] is True and events[1][2] == 0o600
    assert events[2][1] == 0o600
    assert events[3][1] == "refused"
    assert events[4][1] == 0o600


def test_spawn_waits_for_exact_child_runtime_then_returns_published_socket(tmp_path):
    """Discovery waits for the child identity and endpoint before connecting."""
    api = _load_cli()
    runtime_parent = tmp_path / "runtime"
    runtime_parent.mkdir(mode=0o700)
    socket_path = runtime_parent / "managed.sock"
    request = _request(operation="start", request_id="spawn-success")
    child_pid = 7201
    child_token = "child-start-token"
    child_pgid = 7200
    process_domain = _load_cli()["_current_process_domain"]()
    reads = []
    listeners = []

    class Child:
        pid = child_pid

        def __init__(self):
            self.stopped = False
            self.terminated = False
            self.wait_timeouts = []

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.wait_timeouts.append(timeout)
            self.stopped = True
            return 0

    child = Child()

    class FakeSubprocess:
        DEVNULL = object()

        def Popen(self, argv, **_kwargs):
            assert argv[argv.index("--lane") + 1] == "build"
            store.daemon_id = argv[argv.index("--daemon-id") + 1]
            return child

    class StateStore:
        def __init__(self):
            self.daemon_id = None
            self.read_count = 0

        def read_owner(self, deadline=None):
            return {
                "mode": "managed",
                "daemon_id": self.daemon_id or "daemon-pending",
                "generation": 7,
                "lane": "build",
                "lane_key": "build",
                "host": "test-host",
                "process_domain": process_domain,
                "created_at": 1.0,
            }

        def read_runtime(self, deadline=None):
            self.read_count += 1
            if self.read_count == 1:
                reads.append(("missing", not socket_path.exists()))
                return None
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(socket_path))
            socket_path.chmod(0o600)
            listener.listen(1)
            listeners.append(listener)
            reads.append(("published", socket_path.exists()))
            return {
                "version": 1,
                "daemon_id": self.daemon_id,
                "generation": 7,
                "lane": "build",
                "lane_key": "build",
                "host": "test-host",
                "pid": child_pid,
                "start_token": child_token,
                "pgid": child_pgid,
                "process_domain": process_domain,
                "socket_path": str(socket_path),
                "timestamp": 1.0,
            }

    store = StateStore()

    def process_identity(pid):
        assert pid == child_pid
        return {"pid": pid, "start_token": child_token, "pgid": child_pgid}

    original_subprocess = api["subprocess"]
    original_identity = api["_process_identity"]
    api["subprocess"] = FakeSubprocess()
    api["_process_identity"] = process_identity
    try:
        result = api["_spawn_supervisor_and_discover"](
            request,
            socket_path=socket_path,
            connect_timeout=0.2,
            deadline=time.monotonic() + 1.0,
            state_store=store,
        )
    finally:
        api["subprocess"] = original_subprocess
        api["_process_identity"] = original_identity
        for listener in listeners:
            listener.close()
        socket_path.unlink(missing_ok=True)

    assert result == socket_path
    assert reads == [("missing", True), ("published", True)]
    assert store.read_count == 2
    assert not child.terminated
    assert not child.wait_timeouts


@pytest.mark.parametrize(
    "kind, expected_code",
    [
        ("foreign", "unknown"),
        ("stale", "unknown"),
        ("malformed", "invalid"),
        ("missing-socket", "unknown"),
    ],
    ids=["foreign-runtime", "stale-runtime", "malformed-runtime", "missing-socket"],
)
def test_spawn_refuses_foreign_or_bad_runtime_and_stops_child_without_retry(
        tmp_path, kind, expected_code):
    """A published-but-untrusted record is terminal for this child attempt."""
    api = _load_cli()
    runtime_parent = tmp_path / "runtime"
    runtime_parent.mkdir(mode=0o700)
    socket_path = runtime_parent / "managed.sock"
    request = _request(operation="start", request_id="spawn-refused-" + kind)
    child_pid = 7301
    child_token = "child-refused-token"
    child_pgid = 7300
    process_domain = api["_current_process_domain"]()
    process_calls = []

    class Child:
        pid = child_pid

        def __init__(self):
            self.stopped = False
            self.terminated = 0
            self.wait_timeouts = []

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            self.terminated += 1

        def wait(self, timeout=None):
            self.wait_timeouts.append(timeout)
            self.stopped = True
            return 0

    child = Child()

    class FakeSubprocess:
        DEVNULL = object()

        def Popen(self, argv, **_kwargs):
            store.daemon_id = argv[argv.index("--daemon-id") + 1]
            return child

    class StateStore:
        def __init__(self):
            self.daemon_id = None
            self.read_count = 0

        def read_owner(self, deadline=None):
            owner_daemon = "daemon-foreign" if kind == "foreign" else self.daemon_id
            return {
                "mode": "managed",
                "daemon_id": owner_daemon,
                "generation": 7,
                "lane": "build",
                "lane_key": "build",
                "host": "test-host",
                "process_domain": process_domain,
                "created_at": 1.0,
            }

        def read_runtime(self, deadline=None):
            self.read_count += 1
            if kind == "malformed":
                return {"version": 1}
            daemon_id = "daemon-foreign" if kind == "foreign" else self.daemon_id
            runtime_pid = child_pid + 1 if kind == "stale" else child_pid
            endpoint = (
                runtime_parent / "missing.sock"
                if kind == "missing-socket" else socket_path
            )
            return {
                "version": 1,
                "daemon_id": daemon_id,
                "generation": 7,
                "lane": "build",
                "lane_key": "build",
                "host": "test-host",
                "pid": runtime_pid,
                "start_token": child_token,
                "pgid": child_pgid,
                "process_domain": process_domain,
                "socket_path": str(endpoint),
                "timestamp": 1.0,
            }

    store = StateStore()

    def process_identity(pid):
        process_calls.append(pid)
        return {"pid": pid, "start_token": child_token, "pgid": child_pgid}

    def forbidden_request(*_args, **_kwargs):
        raise AssertionError("spawn refusal must not retry the control request")

    original_subprocess = api["subprocess"]
    original_identity = api["_process_identity"]
    original_request = api["request_socket"]
    api["subprocess"] = FakeSubprocess()
    api["_process_identity"] = process_identity
    api["request_socket"] = forbidden_request
    try:
        with pytest.raises(BaseException) as raised:
            api["_spawn_supervisor_and_discover"](
                request,
                socket_path=socket_path,
                connect_timeout=0.2,
                deadline=time.monotonic() + 1.0,
                state_store=store,
            )
    finally:
        api["subprocess"] = original_subprocess
        api["_process_identity"] = original_identity
        api["request_socket"] = original_request

    assert getattr(raised.value, "code", None) == expected_code
    assert store.read_count == 1
    assert child.terminated == 1
    assert len(child.wait_timeouts) == 1
    assert child.stopped
    assert process_calls == []


@pytest.mark.parametrize(
    "identity_result",
    [
        {"pid": 5302, "start_token": "different-process-token", "pgid": 5301},
        {"pid": 5301, "start_token": "stale-token", "pgid": 5300, "live": False},
        None,
        {"pid": 5302, "start_token": "other-process-token", "pgid": 5301},
        {"pid": 5301, "start_token": "token-without-pgid"},
    ],
    ids=[
        "mismatched-pid",
        "stale-incarnation",
        "missing-process",
        "other-process",
        "missing-process-group",
    ],
)
def test_untrusted_process_identity_refuses_begin_without_state_mutation(
        identity_result):
    """PID reuse, disappearance, and cross-process identities fail closed."""
    api = _load_cli()
    requested_pid = 5301
    state = {"owner": "unchanged", "mutations": []}
    identity_calls = []

    def process_identity(pid):
        identity_calls.append(pid)
        return identity_result

    class StateStore:
        owner_record = {}

        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            yield self

        def read_owner(self):
            return dict(self.owner_record)

        def begin_legacy(self, *, pid, start_token, pgid):
            state["mutations"].append({
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            })
            return {"mode": "legacy-lease", "pid": pid}

    before = json.loads(json.dumps(state))
    argv = _ownership_cli_args("legacy-begin", "identity-refused")
    argv.extend(["--pid", str(requested_pid)])
    return_code, output, error = _call_ownership_main_with_identity(
        api, argv, StateStore(), process_identity,
    )

    assert isinstance(return_code, int) and return_code != 0
    assert identity_calls == [requested_pid]
    assert state == before
    assert "different-process-token" not in output + error


@pytest.mark.parametrize(
    "identity_result",
    [
        {"pid": 5402, "start_token": "different-process-token", "pgid": 5401},
        {"pid": 5401, "start_token": "stale-target-token", "pgid": 5400,
         "live": False},
        None,
        {"pid": 5402, "start_token": "other-target-token", "pgid": 5401},
        {"pid": 5401, "start_token": "token-without-pgid"},
    ],
    ids=[
        "bind-mismatched-pid",
        "bind-stale-incarnation",
        "bind-missing-process",
        "bind-other-process",
        "bind-missing-process-group",
    ],
)
def test_untrusted_process_identity_refuses_bind_without_state_mutation(
        identity_result):
    api = _load_cli()
    creator_pid = 5399
    creator_token = "pending-creator-token"
    creator_pgid = 5398
    requested_pid = 5401
    state = {"owner": "pending", "mutations": []}
    identity_calls = []

    def process_identity(pid):
        identity_calls.append(pid)
        if pid == creator_pid:
            return {
                "pid": creator_pid,
                "start_token": creator_token,
                "pgid": creator_pgid,
                "parent_pid": requested_pid,
            }
        return identity_result

    class StateStore:
        owner_record = {
            "mode": "pending-launch",
            "lease_id": "lease-identity",
            "pid": creator_pid,
            "start_token": creator_token,
            "request_id": "identity-bind",
        }

        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            yield self

        def read_owner(self):
            return dict(self.owner_record)

        def bind_pending_launch(self, *, lease_id, pid, start_token, pgid):
            state["mutations"].append({
                "lease_id": lease_id,
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            })
            return {"mode": "legacy-lease", "pid": pid}

    before = json.loads(json.dumps(state))
    # Match the durable pending request so this test reaches process identity
    # validation rather than refusing earlier at the lease/request fence.
    argv = _ownership_cli_args("pending-launch-bind", "identity-bind")
    argv.extend([
        "--lease-id", "lease-identity",
        "--pid", str(requested_pid),
    ])
    return_code, output, error = _call_ownership_main_with_identity(
        api, argv, StateStore(), process_identity,
    )

    assert isinstance(return_code, int) and return_code != 0
    assert identity_calls == [creator_pid, requested_pid]
    assert state == before
    assert "different-process-token" not in output + error


def test_ownership_deadline_covers_global_lock_and_prevents_delayed_mutation():
    """A lock timeout returns before release and never mutates afterward."""
    api = _load_cli()
    pid = 5501
    token = "deadline-live-token"
    pgid = 5500
    lock_ready = threading.Event()
    release_lock = threading.Event()
    state = {"mutations": []}

    class LockTimeout(RuntimeError):
        code = "busy"

    class StateStore:
        def __init__(self):
            self._lock = threading.Lock()

        @contextlib.contextmanager
        def locked(self, *, deadline=None):
            if deadline is None:
                acquired = self._lock.acquire()
            else:
                remaining = deadline - time.monotonic()
                acquired = remaining > 0 and self._lock.acquire(timeout=remaining)
            if not acquired:
                raise LockTimeout("global state lock deadline elapsed")
            try:
                yield self
            finally:
                self._lock.release()

        def begin_legacy(self, *, pid, start_token, pgid):
            # ``durable_ownership_handler`` owns this critical section.  The
            # fake method must not reacquire the same non-reentrant lock.
            state["mutations"].append({
                "pid": pid,
                "start_token": start_token,
                "pgid": pgid,
            })
            return {"mode": "legacy-lease", "pid": pid, "pgid": pgid}

    store = StateStore()

    def process_identity(requested_pid):
        assert requested_pid == pid
        return {"pid": pid, "start_token": token, "pgid": pgid}

    def hold_global_lock():
        with store.locked():
            lock_ready.set()
            assert release_lock.wait(1.0)

    holder = threading.Thread(target=hold_global_lock, name="ownership-lock-holder")
    holder.daemon = True
    holder.start()
    assert lock_ready.wait(1.0)
    result = []
    started = time.monotonic()

    def invoke():
        request = _request(
            operation="legacy-begin",
            request_id="ownership-deadline",
            pid=pid,
        )
        try:
            result.append(api["durable_ownership_handler"](
                request,
                state_store=store,
                process_identity=process_identity,
                deadline=time.monotonic() + 0.05,
            ))
        except BaseException as error:
            result.append(error)

    contender = threading.Thread(target=invoke, name="ownership-lock-contender")
    contender.daemon = True
    contender.start()
    contender.join(timeout=0.30)
    returned_before_release = not contender.is_alive()
    elapsed_before_release = time.monotonic() - started
    # A compliant handler has returned at its absolute deadline while the
    # holder is still inside the critical section.  Releasing afterward must
    # not wake a delayed mutation that was abandoned by the caller.
    release_lock.set()
    holder.join(timeout=1.0)
    contender.join(timeout=1.0)
    assert not holder.is_alive()
    assert not contender.is_alive()
    assert returned_before_release, "ownership deadline did not bound lock wait"
    assert elapsed_before_release < 0.30
    assert len(result) == 1
    assert isinstance(result[0], BaseException)
    assert getattr(result[0], "code", None) in {
        "busy", "timeout", "unknown",
    }
    assert state["mutations"] == []


# ---------------------------------------------------------------------------
# Hidden UserPromptSubmit roster guard
# ---------------------------------------------------------------------------


_ROSTER_PARTICIPANT_UUID = "participant-build-worker"
_ROSTER_SESSION_NAME = "build-worker-1"
_ROSTER_LANE = "build"
_ROSTER_HOST = "roster-test-host"
_ROSTER_PID = 6101
_ROSTER_PGID = 6100
_ROSTER_START_TOKEN = "runner-start-token-6101"


def _roster_body(
        *, participant_uuid: str = _ROSTER_PARTICIPANT_UUID,
        session_name: str = _ROSTER_SESSION_NAME,
        bound_lane: str = _ROSTER_LANE,
        pid: int = _ROSTER_PID,
        start_token: str = _ROSTER_START_TOKEN,
        pgid: int = _ROSTER_PGID) -> dict[str, Any]:
    """Build the canonical guard envelope fields, without alias spellings."""
    return {
        "participant_uuid": participant_uuid,
        "session_name": session_name,
        "bound_lane": bound_lane,
        "runner_pid": pid,
        "runner_start_token": start_token,
        "runner_pgid": pgid,
    }


def _roster_cli_args(
        body: Mapping[str, Any], *, request_id: str = "roster-request",
        lane: str = _ROSTER_LANE, generation: int = 7,
        participant_uuid: str | None = None,
        session_name: str | None = None,
        bound_lane: str | None = None) -> list[str]:
    """Build the hidden command using its documented canonical fields."""
    participant_uuid = participant_uuid or body["participant_uuid"]
    session_name = session_name or body["session_name"]
    bound_lane = bound_lane or body["bound_lane"]
    return [
        "roster-validate",
        lane,
        "--generation", str(generation),
        "--request-id", request_id,
        "--participant-uuid", participant_uuid,
        "--session-name", session_name,
        "--bound-lane", bound_lane,
        "--body-json", json.dumps(
            dict(body), ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ),
    ]


def _roster_fixture(
        tmp_path: Path, *, process_updates: Mapping[str, Any] | None = None,
        drop_process_keys: tuple[str, ...] = (),
        owner_updates: Mapping[str, Any] | None = None,
        runtime_updates: Mapping[str, Any] | None = None,
        identity_result: Any = None):
    """Return a controller-shaped durable roster and a strict identity seam.

    The participant mapping mirrors ``lane_managed_controller.Participant``'s
    persisted ``to_dict`` shape and nests the safe runner specification.  It
    intentionally uses the durable ``session_name``/``bound_lane`` fields and
    canonical process evidence; the test does not exercise controller methods,
    a model, an SDK, or a global operation lock.
    """
    process_domain = _load_cli()["_current_process_domain"]()
    process = {
        "pid": _ROSTER_PID,
        "process_start_token": _ROSTER_START_TOKEN,
        "process_group_id": _ROSTER_PGID,
        "process_group_owned": True,
        "exited": False,
        "group_excluded": False,
    }
    for key in drop_process_keys:
        process.pop(key, None)
    if process_updates:
        process.update(process_updates)

    coordinator = {
        "participant_id": "participant-build-coordinator",
        "session_id": "session-build-coordinator",
        "session_name": "build-coordinator",
        "bound_lane": _ROSTER_LANE,
        "role": "coordinator",
        "parent_id": None,
        "task_id": "task-build",
        "mailbox_id": "mailbox-build-coordinator",
        "kind": "independent",
        "state": "active",
        "writer_claim": None,
        "read_only": False,
        "background": False,
        "detached": False,
        "model": "claude-test-model",
        "permission_mode": "default",
        "fingerprint": {"model": "claude-test-model"},
        "metadata": {
            "session_name": "build-coordinator",
            "bound_lane": _ROSTER_LANE,
        },
    }
    worker = {
        "participant_id": "participant-build-worker-record",
        "session_id": _ROSTER_PARTICIPANT_UUID,
        "session_name": _ROSTER_SESSION_NAME,
        "bound_lane": _ROSTER_LANE,
        "role": "worker",
        "parent_id": "participant-build-coordinator",
        "task_id": "task-build-worker",
        "mailbox_id": "mailbox-build-worker",
        "kind": "independent",
        "state": "reserved",
        "writer_claim": {
            "participant_id": "participant-build-worker-record",
            "worktree": str(tmp_path / "worktree"),
        },
        "read_only": False,
        "background": False,
        "detached": False,
        "model": "claude-test-model",
        "permission_mode": "default",
        "fingerprint": {
            "model": "claude-test-model",
            "profile": "profile-build",
        },
        "metadata": {
            "session_name": _ROSTER_SESSION_NAME,
            "bound_lane": _ROSTER_LANE,
            "runner_spec": {
                "session_name": _ROSTER_SESSION_NAME,
                "bound_lane": _ROSTER_LANE,
                "runner_process": process,
            },
        },
    }
    owner = {
        "mode": "managed",
        "daemon_id": "daemon-roster-test",
        "generation": 7,
        "lane": _ROSTER_LANE,
        "lane_key": _ROSTER_LANE,
        "host": _ROSTER_HOST,
        "process_domain": process_domain,
        "created_at": 1234567890.0,
    }
    if owner_updates:
        owner.update(owner_updates)
    runtime = {
        "version": 1,
        "daemon_id": owner["daemon_id"],
        "generation": owner["generation"],
        "lane": owner["lane"],
        "lane_key": owner["lane_key"],
        "host": _ROSTER_HOST,
        "pid": 6201,
        "start_token": "daemon-start-token-6201",
        "pgid": 6200,
        "process_domain": process_domain,
        "socket_path": str(tmp_path / "managed.sock"),
        "timestamp": 1234567890.0,
    }
    if runtime_updates:
        runtime.update(runtime_updates)
    controller = {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "generation": 7,
        "coordinator_id": coordinator["participant_id"],
        "active_operation_id": None,
        "participants": [coordinator, worker],
        "archived_participants": [],
        "session_history": [],
        "mailboxes": [],
        "operations": [],
        "requests": {},
        "checkpoints": [],
    }

    class Identity:
        lane_key = _ROSTER_LANE
        host = _ROSTER_HOST

    class StateStore:
        identity = Identity()

        def read_owner(self):
            return copy.deepcopy(owner)

        def read_runtime(self):
            return copy.deepcopy(runtime)

        def read_controller(self):
            return copy.deepcopy(controller)

    def process_identity(pid: int, **_kwargs):
        assert pid == _ROSTER_PID
        if identity_result is not None:
            return copy.deepcopy(identity_result)
        return {
            "pid": _ROSTER_PID,
            "alive": True,
            "start_token": _ROSTER_START_TOKEN,
            "pgid": _ROSTER_PGID,
        }

    return _roster_body(), StateStore(), process_identity


def _call_roster_main(
        api: dict, argv: list[str], state_store: Any, process_identity,
        *, env: Mapping[str, str] | None = None):
    """Route the hidden CLI command through the real handler and fake reads."""
    original = api["durable_roster_handler"]

    def injected(request, *, deadline=None):
        return original(
            request,
            state_store=state_store,
            process_identity=process_identity,
            env=env,
            deadline=deadline,
        )

    api["durable_roster_handler"] = injected
    try:
        return _call_main(api, argv, handler=None)
    finally:
        api["durable_roster_handler"] = original


def test_roster_validate_route_accepts_exact_controller_projection_and_bounds_json(
        tmp_path):
    """Valid guard proof is exact, correlated, and deliberately small."""
    api = _load_cli()
    body, store, process_identity = _roster_fixture(tmp_path)
    request_id = "roster-valid-route"
    return_code, output, error = _call_roster_main(
        api,
        _roster_cli_args(body, request_id=request_id),
        store,
        process_identity,
        env={
            # Inherited hints are intentionally foreign to the durable proof.
            "CLAUDE_SESSION_NAME": "inherited-foreign-session",
            "LANE_MANAGED_BOUND_LANE": "foreign-lane",
        },
    )

    assert return_code == 0
    assert error == ""
    assert len(output.encode("utf-8")) <= api["MAX_FRAME_BYTES"]
    response = json.loads(output)
    assert response["request_id"] == request_id
    assert response["ok"] is True
    assert response["valid"] is True
    assert response["mode"] == "managed"
    assert response["lane"] == _ROSTER_LANE
    assert response["bound_lane"] == _ROSTER_LANE
    assert response["participant_uuid"] == _ROSTER_PARTICIPANT_UUID
    assert response["session_name"] == _ROSTER_SESSION_NAME
    assert response["owner"] == "daemon-roster-test"
    assert response["result"]["generation"] == 7
    # Process/start/group evidence is used for admission, not returned as an
    # unbounded or reusable prompt-guard credential.
    for secret_key in (
        "pid", "pgid", "start_token", "process_start_token",
        "runner_process", "process_group_owned",
    ):
        assert secret_key not in response
        assert secret_key not in response["result"]
    assert len(api["encode_frame"](response)) <= api["MAX_FRAME_BYTES"]


def test_roster_validate_confirmed_absence_is_exit_eight_with_empty_stdout(tmp_path):
    """Only an empty durable owner projection proves unmanaged absence."""
    api = _load_cli()
    body = _roster_body()

    class AbsentStore:
        def read_owner(self):
            return {}

    return_code, output, error = _call_roster_main(
        api,
        _roster_cli_args(body, request_id="roster-absent-route"),
        AbsentStore(),
        lambda _pid, **_kwargs: None,
    )

    assert return_code == 8
    assert output == ""
    assert error == ""


def test_roster_validate_unknown_identity_is_participant_refusal_exit_two(tmp_path):
    """A live-PID proof failure is unknown, never an exit-eight absence."""
    api = _load_cli()
    body, store, _ = _roster_fixture(tmp_path)

    return_code, output, error = _call_roster_main(
        api,
        _roster_cli_args(body, request_id="roster-unknown-route"),
        store,
        lambda _pid, **_kwargs: None,
    )

    assert return_code == 2
    assert "managed roster" not in error.lower()
    if output:
        response = json.loads(output)
        assert response["request_id"] == "roster-unknown-route"
        assert response["ok"] is False
        assert response["code"] == "unknown"


@pytest.mark.parametrize(
    ("process_updates", "drop_process_keys", "identity_result", "expected_codes"),
    [
        ({}, ("process_group_id",), None, {"invalid", "unknown"}),
        ({"process_group_id": "synthetic-pgid"}, (), None, {"invalid", "unknown"}),
        ({"process_group_id": 0}, (), None, {"invalid", "unknown"}),
        ({"process_group_owned": False}, (), None, {"unknown"}),
    ],
    ids=["missing-pgid", "string-pgid", "synthetic-pgid", "group-not-owned"],
)
def test_roster_validate_rejects_missing_or_untrusted_process_group_evidence(
        tmp_path, process_updates, drop_process_keys, identity_result,
        expected_codes):
    """The guard needs owned integer PGID evidence in addition to PID/token."""
    api = _load_cli()
    body, store, process_identity = _roster_fixture(
        tmp_path,
        process_updates=process_updates,
        drop_process_keys=drop_process_keys,
        identity_result=identity_result,
    )
    request = _request(
        operation="roster-validate",
        request_id="roster-group-refusal",
        generation=7,
        **body,
    )
    before = copy.deepcopy(store.read_controller())
    with pytest.raises(api["ManagedCLIError"]) as raised:
        api["durable_roster_handler"](
            request,
            state_store=store,
            process_identity=process_identity,
        )

    assert getattr(raised.value, "code", None) in expected_codes
    assert store.read_controller() == before


def test_roster_validate_rejects_foreign_live_process_group_without_mutation(tmp_path):
    """A matching PID/start token with a different observed PGID is foreign."""
    api = _load_cli()
    body, store, _ = _roster_fixture(
        tmp_path,
        identity_result={
            "pid": _ROSTER_PID,
            "alive": True,
            "start_token": _ROSTER_START_TOKEN,
            "pgid": _ROSTER_PGID + 1,
        },
    )
    request = _request(
        operation="roster-validate",
        request_id="roster-foreign-pgid",
        generation=7,
        **body,
    )
    before = copy.deepcopy(store.read_controller())
    with pytest.raises(api["ManagedCLIError"]) as raised:
        api["durable_roster_handler"](
            request,
            state_store=store,
            process_identity=lambda _pid, **_kwargs: {
                "pid": _ROSTER_PID,
                "alive": True,
                "start_token": _ROSTER_START_TOKEN,
                "pgid": _ROSTER_PGID + 1,
            },
        )
    assert getattr(raised.value, "code", None) == "ownership-conflict"
    assert store.read_controller() == before


def test_roster_validate_uses_durable_name_and_lane_over_inherited_hints(tmp_path):
    """Foreign environment hints cannot replace durable safe identity fields."""
    api = _load_cli()
    body, store, process_identity = _roster_fixture(tmp_path)
    return_code, output, error = _call_roster_main(
        api,
        _roster_cli_args(body, request_id="roster-hints-ignored"),
        store,
        process_identity,
        env={
            "CLAUDE_SESSION_NAME": "wrong-inherited-session",
            "LANE_MANAGED_BOUND_LANE": "wrong-inherited-lane",
            "LANE": "wrong-inherited-lane",
        },
    )
    assert return_code == 0
    assert error == ""
    response = json.loads(output)
    assert response["session_name"] == _ROSTER_SESSION_NAME
    assert response["bound_lane"] == _ROSTER_LANE
    assert response["lane"] == _ROSTER_LANE


@pytest.mark.parametrize(
    "field, value",
    [("session_name", "foreign-session"), ("bound_lane", "foreign-lane")],
    ids=["foreign-session-name", "foreign-bound-lane"],
)
def test_roster_validate_rejects_caller_identity_mismatch_even_with_matching_env(
        tmp_path, field, value):
    """Caller-supplied name/lane cannot be repaired by an environment hint."""
    api = _load_cli()
    body, store, process_identity = _roster_fixture(tmp_path)
    kwargs = {field: value}
    return_code, output, error = _call_roster_main(
        api,
        _roster_cli_args(
            body,
            request_id="roster-identity-mismatch-" + field,
            **kwargs,
        ),
        store,
        process_identity,
        env={
            "CLAUDE_SESSION_NAME": _ROSTER_SESSION_NAME,
            "LANE_MANAGED_BOUND_LANE": _ROSTER_LANE,
        },
    )
    assert return_code != 0
    assert output
    assert error == ""
    response = json.loads(output)
    assert response["ok"] is False
    assert response["code"] == "ownership-conflict"


def test_roster_validate_rejects_stale_runtime_generation_before_runner_probe(tmp_path):
    """Exact owner/runtime generation is required before process admission."""
    api = _load_cli()
    body, store, process_identity = _roster_fixture(
        tmp_path,
        runtime_updates={"generation": 6},
    )
    request = _request(
        operation="roster-validate",
        request_id="roster-stale-generation",
        generation=7,
        **body,
    )
    with pytest.raises(api["ManagedCLIError"]) as raised:
        api["durable_roster_handler"](
            request,
            state_store=store,
            process_identity=process_identity,
        )
    assert getattr(raised.value, "code", None) == "stale-generation"
