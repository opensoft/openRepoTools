# SPDX-License-Identifier: Apache-2.0
"""Public managed ``ctx`` wire-boundary tests.

These tests stop at the daemon router.  The controller fake records the exact
route arguments, but does not start a runtime or claim that native restart is
implemented.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from lane_managed_controller import Operation
from lane_managed_daemon import ManagedDaemon


LANE = "build"
GENERATION = 7


def _request(request_id: str, body: Any) -> dict[str, Any]:
    return {
        "schema": 2,
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "request_id": request_id,
        "lane": LANE,
        "generation": GENERATION,
        "operation": "ctx",
        "body": body,
    }


class CtxController:
    """Record the public route without implementing ctx lifecycle behavior."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def ctx(
        self,
        request_id: str,
        generation: Any,
        checkpoint: Any,
        worker_policy: Any,
        worker_mapping: Any = None,
    ) -> Operation:
        self.calls.append({
            "request_id": request_id,
            "generation": generation,
            "checkpoint": checkpoint,
            "worker_policy": worker_policy,
            "worker_mapping": worker_mapping,
        })
        return Operation(
            operation_id="ctx-wire-operation",
            request_id=request_id,
            mode="ctx",
            generation=generation,
            phase="ready-held",
            metadata={"wire_only": True},
        )


def _daemon(controller: CtxController) -> ManagedDaemon:
    daemon = ManagedDaemon(
        controller=controller,
        daemon_id="daemon-ctx-wire",
        opt_in=True,
        lane=LANE,
    )
    # This isolates the route from startup/lifecycle tests.  No enrollment,
    # profile resolution, SDK import, or runtime operation is performed.
    daemon.started = True
    return daemon


@pytest.mark.parametrize(
    "body",
    [
        {"checkpoint": "checkpoint-1", "worker_policy": "rebind"},
        {
            "checkpoint": "checkpoint-1",
            "worker_policy": "hold",
            "mapping": {},
        },
        {
            "checkpoint": "checkpoint-1",
            "worker_policy": "hold",
            "mapping": None,
        },
        {
            "checkpoint": "checkpoint-1",
            "worker_policy": "restart",
            "mapping": {
                "worker-a": {
                    "coordinator": "coordinator-new",
                    "task": "task-a",
                },
            },
        },
        {
            "checkpoint": "checkpoint-1",
            "worker_policy": "hold",
            "mapping": [],
        },
        {
            "checkpoint": "checkpoint-1",
            "worker_policy": "hold",
            "mapping": "{}",
        },
        {
            "checkpoint": "checkpoint-1",
            "worker_policy": "hold",
            "worker_mapping": {},
        },
        {
            "checkpoint": "checkpoint-1",
            "worker_policy": "hold",
            "rebind_mapping": None,
        },
        {"checkpoint": "checkpoint-1", "worker_policy": {}},
        {"checkpoint": "checkpoint-1", "worker_policy": []},
        {"checkpoint": "checkpoint-1", "worker_policy": None},
        {"checkpoint": "checkpoint-1", "worker_policy": False},
    ],
    ids=[
        "legacy-rebind",
        "empty-mapping",
        "null-mapping",
        "restart-mapping",
        "list-mapping",
        "string-mapping",
        "worker-mapping-alias",
        "rebind-mapping-alias",
        "object-policy",
        "list-policy",
        "null-policy",
        "bool-policy",
    ],
)
def test_ctx_wire_refuses_legacy_policy_and_mapping_forms_before_controller(
    body: dict[str, Any],
) -> None:
    controller = CtxController()
    daemon = _daemon(controller)

    response = asyncio.run(daemon.handle_request(_request("ctx-invalid", body)))

    assert response["ok"] is False
    assert response["code"] == "invalid"
    assert controller.calls == []


@pytest.mark.parametrize(
    "body",
    [None, [], "ctx", 1, False],
    ids=["null", "list", "string", "number", "bool"],
)
def test_ctx_wire_rejects_non_object_body_before_controller(body: Any) -> None:
    controller = CtxController()
    daemon = _daemon(controller)

    response = asyncio.run(daemon.handle_request(_request("ctx-body-type", body)))

    assert response["ok"] is False
    assert response["code"] == "invalid"
    assert controller.calls == []


def test_ctx_restart_wire_forwards_policy_unchanged_without_claiming_restart() -> None:
    controller = CtxController()
    daemon = _daemon(controller)
    request = _request(
        "ctx-restart-wire",
        {"checkpoint": "checkpoint-1", "worker_policy": "restart"},
    )

    response = asyncio.run(daemon.handle_request(request))

    assert response["ok"] is True
    assert controller.calls == [{
        "request_id": "ctx-restart-wire",
        "generation": GENERATION,
        "checkpoint": "checkpoint-1",
        "worker_policy": "restart",
        "worker_mapping": None,
    }]
    assert response["result"]["metadata"] == {"wire_only": True}
