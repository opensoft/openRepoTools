# SPDX-License-Identifier: Apache-2.0
"""Native lineage claim cleanup after a proven managed shutdown."""

from __future__ import annotations

import asyncio

import pytest

from lane_managed_controller import ControllerError
from test_lane_managed_native_swap_integration import (
    NativeSwapEvidenceProvider,
    NativeSwapRuntime,
    _harness,
    _reload_fixture_controller,
    _start_and_release,
)


def test_native_unenroll_requires_shutdown_proof_before_claim_release(tmp_path):
    with _harness(
        tmp_path, provider=NativeSwapEvidenceProvider(),
        runtime=NativeSwapRuntime(),
    ) as fixture:
        _start_and_release(fixture)
        claims = fixture.state.read_lineage_claims()
        assert len(claims) == 1
        with pytest.raises(ControllerError) as raised:
            fixture.controller.unenroll(fixture.generation)
        assert raised.value.code in {"busy", "uncertain-effect"}
        assert fixture.state.read_lineage_claims() == claims


def test_native_unenroll_reconciles_post_release_crash_without_second_release(
    tmp_path,
):
    with _harness(
        tmp_path, provider=NativeSwapEvidenceProvider(),
        runtime=NativeSwapRuntime(),
    ) as fixture:
        _start_and_release(fixture)
        swapped = fixture.request(
            "native-unenroll-swap", "swap", {"profile": "team-b"}
        )
        assert swapped["ok"] is True, swapped
        released = fixture.request(
            "native-unenroll-target-release", "release",
            {"operation_id": swapped["result"]["operation_id"]},
        )
        assert released["ok"] is True, released
        stopped = asyncio.run(fixture.controller.shutdown(fixture.generation))
        assert stopped["phase"] == "complete"
        assert len(fixture.state.read_lineage_claims()) == 1

        original_read_owner = fixture.state.read_owner

        def changed_owner():
            owner = original_read_owner()
            owner["daemon_id"] = "foreign-daemon"
            return owner

        before = fixture.state.read_json("controller.json")
        fixture.state.read_owner = changed_owner
        with pytest.raises(ControllerError) as wrong_owner:
            fixture.controller.unenroll(fixture.generation)
        assert wrong_owner.value.code == "ownership-conflict"
        assert fixture.state.read_json("controller.json") == before
        assert len(fixture.state.read_lineage_claims()) == 1
        fixture.state.read_owner = original_read_owner

        original_release = fixture.state.release_lineage_claim
        release_calls = 0

        def release_then_crash(*args, **kwargs):
            nonlocal release_calls
            release_calls += 1
            original_release(*args, **kwargs)
            raise RuntimeError("simulated crash after durable lineage release")

        fixture.state.release_lineage_claim = release_then_crash
        with pytest.raises(ControllerError) as raised:
            fixture.controller.unenroll(fixture.generation)
        assert raised.value.code == "uncertain-effect"
        assert release_calls == 1
        assert fixture.state.read_lineage_claims() == []

        operation_id = fixture.state.read_json("controller.json")[
            "active_operation_id"
        ]
        _reload_fixture_controller(fixture)
        reconciled = asyncio.run(fixture.controller.recover(
            operation_id, fixture.generation,
            {"operation_id": operation_id, "generation": fixture.generation,
             "participants": {}},
        ))
        assert reconciled.phase == "complete"
        assert release_calls == 1
        assert fixture.state.read_lineage_claims() == []

        repeated = fixture.controller.unenroll(fixture.generation)
        assert repeated["phase"] == "complete"
        assert repeated["claims_released"] is True
        assert release_calls == 1
