# SPDX-License-Identifier: Apache-2.0
"""Offline executable-CLI smoke for one persistent managed service.

The test invokes the shipped ``lane-managed`` executable in a subprocess for
every control operation.  The peer is one persistent ``run_supervisor``
service backed by the real temporary ``ManagedStateStore`` and
``ManagedController``; its runner/profile/projection dependencies are the
existing explicit offline fakes from the native-swap integration harness.
No Claude SDK, account, credential, network, or environment-module injection
is used.  The executable path is therefore covered without mistaking a direct
``request_socket`` call for a CLI lifecycle.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Mapping

from lane_managed_daemon import run_supervisor
from test_lane_managed_daemon import _native_start_body
from test_lane_managed_native_swap_integration import (
    NativeSwapEvidenceProvider,
    NativeSwapHarness,
    NativeSwapRuntime,
)


REPO = Path(__file__).resolve().parents[1]
LANE_MANAGED = REPO / "lane-managed"
LANE = "build"


class _Projection:
    """Explicit local projection seam required by the supervisor harness."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def preflight(self, context: Mapping[str, Any]) -> bool:
        self.events.append(("preflight", dict(context)))
        return True

    def managed_owner(self, context: Mapping[str, Any]) -> bool:
        self.events.append(("managed-owner", dict(context)))
        return True

    def managed_clear(self, context: Mapping[str, Any]) -> bool:
        self.events.append(("managed-clear", dict(context)))
        return True


def _wait_for_socket(
        socket_path: Path, thread: threading.Thread,
        errors: list[BaseException], timeout: float = 3.0,
) -> None:
    deadline = time.monotonic() + timeout
    while (
        not socket_path.exists()
        and thread.is_alive()
        and time.monotonic() < deadline
    ):
        time.sleep(0.005)
    assert socket_path.exists(), f"persistent service did not publish {socket_path}"
    assert not errors, f"persistent service failed before readiness: {errors!r}"


def _cli_environment(tmp_path: Path) -> dict[str, str]:
    """Return a minimal no-auth environment for the executable subprocess."""

    home = tmp_path / "cli-home"
    home.mkdir(mode=0o700)
    return {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", ""),
        "LANG": "C",
        "LC_ALL": "C",
        "PYTHONNOUSERSITE": "1",
    }


def _native_start_body_for(fixture: NativeSwapHarness) -> dict[str, Any]:
    """Build the same trusted native start request used by the integration harness."""

    body = _native_start_body()
    workspace = fixture.state.identity.workspace
    body["coordinator"]["metadata"].update({
        "workspace": str(workspace),
        "transcript_project": str(Path(workspace) / "transcripts"),
    })
    spec = body["runner_specs"]["coordinator"]
    spec.update({
        "cwd": str(workspace),
        "transcript_project": str(Path(workspace) / "transcripts"),
    })
    spec["fingerprint"].update({"workspace": str(workspace)})
    spec["fingerprint"]["native_config"].update({
        "workspace": str(workspace),
        "repository": str(workspace),
    })
    return body


def _run_cli(
        env: Mapping[str, str], socket_path: Path, generation: int,
        operation: str, request_id: str, *,
        operation_id: str | None = None,
        body: Mapping[str, Any] | None = None,
        options: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Invoke the shipped executable and decode its one JSON response."""

    argv = [
        str(LANE_MANAGED), operation, LANE,
        "--socket", str(socket_path),
        "--generation", str(generation),
        "--request-id", request_id,
    ]
    if operation_id is not None:
        argv.extend(("--operation-id", operation_id))
    argv.extend(options)
    if body is not None:
        argv.extend((
            "--body",
            json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        ))
    completed = subprocess.run(
        argv,
        cwd=str(REPO),
        env=dict(env),
        capture_output=True,
        text=True,
        timeout=15.0,
        check=False,
    )
    assert completed.stdout.strip(), (
        f"lane-managed {operation} emitted no response: {completed.stderr!r}"
    )
    try:
        response = json.loads(completed.stdout)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AssertionError(
            f"lane-managed {operation} emitted non-JSON output: {completed.stdout!r}"
        ) from exc
    assert isinstance(response, dict), response
    assert response.get("request_id") == request_id, response
    if response.get("ok") is True:
        assert completed.returncode == 0, (completed.returncode, response)
    else:
        assert completed.returncode != 0, (completed.returncode, response)
    return response


def _assert_ok(response: Mapping[str, Any], operation: str) -> Mapping[str, Any]:
    assert response.get("ok") is True, (
        f"{operation} refused: {json.dumps(dict(response), sort_keys=True)}"
    )
    result = response.get("result")
    assert isinstance(result, Mapping), response
    return result


def test_executable_cli_drives_persistent_native_lifecycle(tmp_path: Path) -> None:
    """Exercise start/status/swap/recover/release/shutdown/unenroll over one service."""

    provider = NativeSwapEvidenceProvider()
    runtime = NativeSwapRuntime(crash_boundary="shutdown")
    fixture = NativeSwapHarness(tmp_path, provider=provider, runtime=runtime)
    projection = _Projection()
    socket_path = fixture.socket_path
    stop_event = threading.Event()
    errors: list[BaseException] = []
    served: list[list[dict[str, Any]]] = []

    def serve() -> None:
        try:
            served.append(run_supervisor(
                LANE,
                socket_path,
                "daemon-native-swap",
                True,
                env=fixture.env,
                state=fixture.state,
                profiles=fixture.profiles,
                controller=fixture.controller,
                adapter=runtime,
                projection=projection,
                operation_timeout=10.0,
                stop_event=stop_event,
            ))
        except BaseException as error:  # make service failures visible
            errors.append(error)

    service_thread = threading.Thread(
        target=serve, name="managed-cli-persistent-service", daemon=True
    )
    service_thread.start()
    try:
        _wait_for_socket(socket_path, service_thread, errors)
        cli_env = _cli_environment(tmp_path)
        generation = int(fixture.state.read_owner()["generation"])

        started = _run_cli(
            cli_env, socket_path, generation, "start", "cli-start",
            body=_native_start_body_for(fixture),
        )
        start_result = _assert_ok(started, "start")
        source_operation_id = str(start_result["operation_id"])
        assert start_result["phase"] == "ready-held"

        before_release = _run_cli(
            cli_env, socket_path, generation, "status", "cli-status-before"
        )
        before_result = _assert_ok(before_release, "status before release")
        assert before_result["live_sdk"] == "UNVERIFIED"

        submitted = _run_cli(
            cli_env, socket_path, generation, "submit", "cli-submit",
            options=(
                "--recipient-id", "coordinator",
                "--sender-id", "user",
                "--payload-ref", "opaque://cli-lifecycle",
                "--task-id", "task-root-coordinator",
            ),
        )
        submitted_result = _assert_ok(submitted, "submit")
        assert submitted_result["state"] in {"fenced", "queued"}

        source_released = _run_cli(
            cli_env, socket_path, generation, "release", "cli-release-source",
            operation_id=source_operation_id,
        )
        source_release_result = _assert_ok(source_released, "release source")
        assert source_release_result["phase"] == "released"

        first_swap = _run_cli(
            cli_env, socket_path, generation, "swap", "cli-swap-crash",
            options=("--profile", "team-b"),
        )
        assert first_swap["ok"] is False
        assert first_swap["code"] == "uncertain-effect"
        swap_operation_id = str(
            fixture.state.read_json("controller.json")["active_operation_id"]
        )

        recovered = _run_cli(
            cli_env, socket_path, generation, "recover", "cli-recover",
            operation_id=swap_operation_id,
        )
        recover_result = _assert_ok(recovered, "recover")
        assert recover_result["phase"] == "paused"

        lifecycle_counts = (
            len(runtime.coordinator_interrupt_calls),
            len(runtime.shutdown_calls),
            len(runtime.open_calls),
            len(runtime.send_calls),
        )
        busy_retry = _run_cli(
            cli_env, socket_path, generation, "swap", "cli-swap-new-id",
            options=("--profile", "team-b"),
        )
        assert busy_retry["ok"] is False
        assert busy_retry["code"] == "busy"
        assert (
            len(runtime.coordinator_interrupt_calls),
            len(runtime.shutdown_calls),
            len(runtime.open_calls),
            len(runtime.send_calls),
        ) == lifecycle_counts

        swapped = _run_cli(
            cli_env, socket_path, generation, "swap", "cli-swap-crash",
            options=("--profile", "team-b"),
        )
        swap_result = _assert_ok(swapped, "swap retry")
        assert swap_result["phase"] == "ready-held"
        assert swap_result["operation_id"] == swap_operation_id
        assert len(runtime.coordinator_interrupt_calls) == lifecycle_counts[0]
        assert len(runtime.shutdown_calls) == lifecycle_counts[1]
        assert len(runtime.open_calls) == lifecycle_counts[2] + 1
        assert len(runtime.send_calls) == lifecycle_counts[3]
        target_operation_id = str(swap_result["operation_id"])

        target_released = _run_cli(
            cli_env, socket_path, generation, "release", "cli-release-target",
            operation_id=target_operation_id,
        )
        target_release_result = _assert_ok(target_released, "release target")
        assert target_release_result["phase"] == "released"

        after_release = _run_cli(
            cli_env, socket_path, generation, "status", "cli-status-after"
        )
        assert _assert_ok(after_release, "status after release")["phase"] == "released"

        shutdown = _run_cli(
            cli_env, socket_path, generation, "shutdown", "cli-shutdown"
        )
        shutdown_result = _assert_ok(shutdown, "shutdown")
        assert shutdown_result["phase"] == "complete"

        after_shutdown = _run_cli(
            cli_env, socket_path, generation, "status", "cli-status-stopped"
        )
        assert _assert_ok(after_shutdown, "status after shutdown")["phase"] is None

        unenrolled = _run_cli(
            cli_env, socket_path, generation, "unenroll", "cli-unenroll"
        )
        unenroll_result = _assert_ok(unenrolled, "unenroll")
        assert unenroll_result["owner_cleared"] is True
    finally:
        stop_event.set()
        service_thread.join(timeout=5.0)

    assert not service_thread.is_alive()
    assert errors == []
    assert served and len(served[0]) >= 1
    assert [name for name, _context in projection.events] == [
        "preflight", "managed-owner", "managed-clear",
    ]
