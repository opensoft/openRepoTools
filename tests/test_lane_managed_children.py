# SPDX-License-Identifier: Apache-2.0
"""Pure native-child observation and nested-causality contract tests."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from lane_managed_children import (
    NativeChildContractError,
    canonical_digest,
    derive_parent_binding,
    observation_run_id,
    require_live_parent,
    validate_observation,
    validate_observation_progress,
    validate_parent_binding,
)


GENERATION = 7
LINEAGE_ID = "lineage-test"
SESSION = "session-coordinator"
RUNNER = "runner-a"
INVOCATION = "invocation-a"
DEFINITION_DIGEST = "a" * 64


def _context(*, fenced: bool = False) -> dict[str, object]:
    claim = {
        "claim_kind": "workspace",
        "lineage_id": LINEAGE_ID,
        "owner_generation": GENERATION,
        "lineage_generation": 3,
        "workspace": "/tmp/native-child-workspace",
        "common_dir": "/tmp/native-child-workspace",
        "state": "held",
    }
    fact = {
        "name": "writer",
        "digest": DEFINITION_DIGEST,
        "tools": ["Read"],
        "model": "model",
        "effort": "medium",
        "permissionMode": "default",
        "permissions": {"allow": ["Read"]},
        "writable_paths": None,
    }
    return {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "admission-context",
        "lineage": {
            "owner_generation": GENERATION,
            "lineage_id": LINEAGE_ID,
            "lineage_generation": 3,
            "session_uuid": SESSION,
            "workspace_claim": claim,
        },
        "runner_incarnation": RUNNER,
        "invocation_id": INVOCATION,
        "invocation_watermark": 1,
        "prompt_id": None,
        "definitions": {"writer": fact},
        "fenced": fenced,
    }


def _admission(
    admission_id: str,
    *,
    watermark: int,
    agent_id: str | None = None,
    parent_prompt: str | None = None,
) -> dict[str, object]:
    context = _context()
    parent: dict[str, object] = {
        "session_id": SESSION,
        "invocation_id": INVOCATION,
    }
    if agent_id is not None:
        parent["agent_id"] = agent_id
    if parent_prompt is not None:
        parent["prompt_id"] = parent_prompt
    return {
        "admission_id": admission_id,
        "tool_use_id": "tool-" + admission_id,
        "agent_type": "writer",
        "invocation_id": INVOCATION,
        "parent": parent,
        "custom_definition": copy.deepcopy(context["definitions"]["writer"]),  # type: ignore[index]
        "definition_digest": DEFINITION_DIGEST,
        "trusted_definition_digest": DEFINITION_DIGEST,
        "watermark": watermark,
        "owner_generation": GENERATION,
        "lineage_id": LINEAGE_ID,
        "runner_incarnation": RUNNER,
        "launch_completed": False,
    }


def _observation(
    admission: dict[str, object],
    *,
    observation_id: str,
    agent_id: str,
    task_id: str,
    start_watermark: int,
    task_watermark: int,
    observation_watermark: int,
    parent_agent_id: str | None = None,
    lineage_incarnation: int = 1,
    status: str = "active",
    terminal_watermark: int | None = None,
    terminal_outcome: str | None = None,
    uncertain_tool_ids: list[str] | None = None,
    unresolved_effect_ids: list[str] | None = None,
) -> dict[str, object]:
    context = _context()
    child = {
        "admission_id": admission["admission_id"],
        "tool_use_id": admission["tool_use_id"],
        "agent_id": agent_id,
        "task_id": task_id,
        "parent_agent_id": parent_agent_id,
        "invocation_id": INVOCATION,
        "lineage_incarnation": lineage_incarnation,
        "trusted_definition_digest": DEFINITION_DIGEST,
        "start_watermark": start_watermark,
        "task_start_event": {
            "event_uuid": "event-" + observation_id,
            "watermark": task_watermark,
            "task_type": "Agent",
        },
        "status": status,
        "terminal_watermark": terminal_watermark,
        "active_tool_ids": [],
        "uncertain_tool_ids": uncertain_tool_ids or [],
        "unresolved_effect_ids": unresolved_effect_ids or [],
    }
    source = {
        "owner_generation": GENERATION,
        "lineage_id": LINEAGE_ID,
        "lineage_generation": 3,
        "session_uuid": SESSION,
        "runner_incarnation": RUNNER,
        "invocation_id": INVOCATION,
    }
    context_for_digest = copy.deepcopy(context)
    context_for_digest.pop("fenced")
    return {
        "schema_version": 2,
        "architecture": "native-coordinator-lineage",
        "record_kind": "native-child-observation",
        "observation_id": observation_id,
        "source_identity": source,
        "context_binding_digest": canonical_digest(context_for_digest),
        "claim_digest": canonical_digest(context["lineage"]["workspace_claim"]),  # type: ignore[index]
        "observation_watermark": observation_watermark,
        "terminal_outcome": terminal_outcome,
        "child": child,
    }


def _validated(observation: dict[str, object], admission: dict[str, object]) -> dict[str, object]:
    return validate_observation(observation, context=_context(), admission=admission)


def _assert_refusal(fn, code: str | None = None) -> None:
    with pytest.raises(NativeChildContractError) as raised:
        fn()
    if code is not None:
        assert raised.value.code == code


def test_canonical_digest_is_strict_and_matches_contract_form():
    value = {"z": ["é", 2], "a": {"b": True}}
    expected = hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    assert canonical_digest(value) == expected
    _assert_refusal(lambda: canonical_digest(float("nan")), "invalid")


def test_validate_observation_joins_context_and_returns_detached_projection():
    admission = _admission("admission-1", watermark=2)
    observation = _observation(
        admission,
        observation_id="observation-1",
        agent_id="agent-1",
        task_id="task-1",
        start_watermark=3,
        task_watermark=4,
        observation_watermark=5,
    )
    normalized = _validated(observation, admission)
    assert normalized == observation
    observation["child"]["active_tool_ids"].append("caller-mutation")  # type: ignore[index]
    assert normalized["child"]["active_tool_ids"] == []  # type: ignore[index]

    fenced_context = _context(fenced=True)
    assert validate_observation(observation, context=fenced_context, admission=admission)


@pytest.mark.parametrize(
    "start_watermark, task_watermark",
    [(3, 4), (4, 3)],
)
def test_validate_observation_accepts_independent_start_and_task_watermarks(
        start_watermark: int, task_watermark: int,
):
    admission = _admission("admission-1", watermark=2)
    observation = _observation(
        admission,
        observation_id="observation-1",
        agent_id="agent-1",
        task_id="task-1",
        start_watermark=start_watermark,
        task_watermark=task_watermark,
        observation_watermark=5,
    )
    assert _validated(observation, admission) == observation


@pytest.mark.parametrize("task_watermark", [1, 2])
def test_validate_observation_rejects_task_start_at_or_before_admission(
        task_watermark: int,
):
    admission = _admission("admission-1", watermark=2)
    observation = _observation(
        admission,
        observation_id="observation-1",
        agent_id="agent-1",
        task_id="task-1",
        start_watermark=4,
        task_watermark=task_watermark,
        observation_watermark=5,
    )
    _assert_refusal(lambda: _validated(observation, admission), "stale-generation")


def test_validate_observation_rejects_task_start_after_observation():
    admission = _admission("admission-1", watermark=2)
    observation = _observation(
        admission,
        observation_id="observation-1",
        agent_id="agent-1",
        task_id="task-1",
        start_watermark=3,
        task_watermark=6,
        observation_watermark=5,
    )
    _assert_refusal(lambda: _validated(observation, admission), "stale-generation")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["child"].update({"invocation_id": "other-invocation"}),
        lambda value: value.update({"unknown": True}),
        lambda value: value.update({"context_binding_digest": "b" * 64}),
        lambda value: value["child"].update({"start_watermark": 2}),
        lambda value: value["child"].update({"status": "completed"}),
    ],
)
def test_validate_observation_rejects_identity_or_watermark_substitution(mutation):
    admission = _admission("admission-1", watermark=2)
    observation = _observation(
        admission,
        observation_id="observation-1",
        agent_id="agent-1",
        task_id="task-1",
        start_watermark=3,
        task_watermark=4,
        observation_watermark=5,
    )
    mutation(observation)
    _assert_refusal(lambda: _validated(observation, admission))


def test_run_id_uses_only_the_frozen_identity_projection():
    admission = _admission("admission-1", watermark=2)
    observation = _observation(
        admission,
        observation_id="observation-1",
        agent_id="agent-1",
        task_id="task-1",
        start_watermark=3,
        task_watermark=4,
        observation_watermark=5,
        uncertain_tool_ids=["uncertain-1"],
    )
    normalized = _validated(observation, admission)
    expected_input = {
        "source_identity": normalized["source_identity"],
        "admission_id": normalized["child"]["admission_id"],  # type: ignore[index]
        "tool_use_id": normalized["child"]["tool_use_id"],  # type: ignore[index]
        "agent_id": normalized["child"]["agent_id"],  # type: ignore[index]
        "task_id": normalized["child"]["task_id"],  # type: ignore[index]
        "lineage_incarnation": normalized["child"]["lineage_incarnation"],  # type: ignore[index]
        "start_watermark": normalized["child"]["start_watermark"],  # type: ignore[index]
    }
    assert observation_run_id(normalized) == canonical_digest(expected_input)


def test_progress_requires_ascending_watermarks_and_sticky_unresolved_inventory():
    admission = _admission("admission-1", watermark=2)
    previous = _validated(
        _observation(
            admission,
            observation_id="observation-1",
            agent_id="agent-1",
            task_id="task-1",
            start_watermark=3,
            task_watermark=4,
            observation_watermark=5,
            uncertain_tool_ids=["tool-1"],
        ),
        admission,
    )
    candidate = copy.deepcopy(previous)
    candidate["observation_id"] = "observation-2"
    candidate["observation_watermark"] = 6
    candidate["child"]["uncertain_tool_ids"] = ["tool-1"]  # type: ignore[index]
    assert validate_observation_progress(previous, candidate)["observation_id"] == "observation-2"

    cleared = copy.deepcopy(candidate)
    cleared["observation_id"] = "observation-3"
    cleared["observation_watermark"] = 7
    cleared["child"]["uncertain_tool_ids"] = []  # type: ignore[index]
    _assert_refusal(lambda: validate_observation_progress(candidate, cleared), "uncertain-effect")

    stale = copy.deepcopy(candidate)
    stale["observation_id"] = "observation-4"
    stale["observation_watermark"] = 5
    _assert_refusal(lambda: validate_observation_progress(previous, stale), "stale-generation")

    terminal = copy.deepcopy(previous)
    terminal["observation_id"] = "observation-terminal"
    terminal["observation_watermark"] = 6
    terminal["terminal_outcome"] = "stopped"
    terminal["child"]["status"] = "stopped"  # type: ignore[index]
    terminal["child"]["terminal_watermark"] = 5  # type: ignore[index]
    validate_observation_progress(previous, terminal)
    rewritten_terminal = copy.deepcopy(terminal)
    rewritten_terminal["observation_id"] = "observation-terminal-rewritten"
    rewritten_terminal["observation_watermark"] = 7
    rewritten_terminal["child"]["terminal_watermark"] = 6  # type: ignore[index]
    _assert_refusal(
        lambda: validate_observation_progress(terminal, rewritten_terminal),
        "stale-generation",
    )


def test_top_level_parent_has_no_binding_and_nested_parent_derives_exact_binding():
    top = _admission("parent-admission", watermark=2)
    nested = _admission("nested-admission", watermark=20, agent_id="parent-agent")
    parent_observation = _observation(
        top,
        observation_id="parent-observation",
        agent_id="parent-agent",
        task_id="parent-task",
        start_watermark=3,
        task_watermark=4,
        observation_watermark=5,
    )
    normalized_parent = _validated(parent_observation, top)
    assert derive_parent_binding(
        top, context=_context(), admissions={}, observations={}
    ) is None
    binding = derive_parent_binding(
        nested,
        context=_context(),
        admissions={top["admission_id"]: top},
        observations={normalized_parent["observation_id"]: normalized_parent},
    )
    assert binding is not None
    assert validate_parent_binding(
        nested,
        binding,
        context=_context(),
        admissions={top["admission_id"]: top},
        observations={normalized_parent["observation_id"]: normalized_parent},
    ) == binding
    require_live_parent(
        nested,
        binding,
        context=_context(),
        observations={normalized_parent["observation_id"]: normalized_parent},
    ) is None


def test_historical_parent_binding_survives_later_terminal_but_live_check_refuses():
    top = _admission("parent-admission", watermark=2)
    nested = _admission("nested-admission", watermark=10, agent_id="parent-agent")
    active = _validated(
        _observation(
            top,
            observation_id="parent-active",
            agent_id="parent-agent",
            task_id="parent-task",
            start_watermark=3,
            task_watermark=4,
            observation_watermark=5,
        ),
        top,
    )
    later_terminal_raw = _observation(
        top,
        observation_id="parent-terminal",
        agent_id="parent-agent",
        task_id="parent-task",
        start_watermark=3,
        task_watermark=4,
        observation_watermark=12,
        status="stopped",
        terminal_watermark=11,
        terminal_outcome="stopped",
    )
    later_terminal_raw["child"]["task_start_event"]["event_uuid"] = (  # type: ignore[index]
        active["child"]["task_start_event"]["event_uuid"]  # type: ignore[index]
    )
    later_terminal = _validated(later_terminal_raw, top)
    observations = {
        active["observation_id"]: active,
        later_terminal["observation_id"]: later_terminal,
    }
    binding = derive_parent_binding(
        nested,
        context=_context(),
        admissions={top["admission_id"]: top},
        observations=observations,
    )
    assert binding is not None and binding["observation_id"] == "parent-active"
    _assert_refusal(
        lambda: require_live_parent(
            nested, binding, context=_context(), observations=observations
        ),
        "stale-generation",
    )


def test_nested_parent_missing_observation_and_two_runs_are_refused():
    top = _admission("parent-admission", watermark=2)
    nested = _admission("nested-admission", watermark=20, agent_id="parent-agent")
    _assert_refusal(
        lambda: derive_parent_binding(
            nested,
            context=_context(),
            admissions={top["admission_id"]: top},
            observations={},
        ),
        "ownership-conflict",
    )
    first = _validated(
        _observation(
            top,
            observation_id="parent-1",
            agent_id="parent-agent",
            task_id="task-1",
            start_watermark=3,
            task_watermark=4,
            observation_watermark=5,
        ),
        top,
    )
    second = copy.deepcopy(first)
    second["observation_id"] = "parent-2"
    second["observation_watermark"] = 8
    second["child"]["task_id"] = "task-2"  # type: ignore[index]
    second["child"]["lineage_incarnation"] = 2  # type: ignore[index]
    second["child"]["start_watermark"] = 6  # type: ignore[index]
    second["child"]["task_start_event"]["event_uuid"] = "event-parent-2"  # type: ignore[index]
    second["child"]["task_start_event"]["watermark"] = 7  # type: ignore[index]
    _assert_refusal(
        lambda: derive_parent_binding(
            nested,
            context=_context(),
            admissions={top["admission_id"]: top},
            observations={first["observation_id"]: first, second["observation_id"]: second},
        ),
        "ownership-conflict",
    )


def test_parent_cycle_is_refused_without_mutating_records():
    cyclic_parent = _admission("parent-admission", watermark=2, agent_id="parent-agent")
    nested = _admission("nested-admission", watermark=20, agent_id="parent-agent")
    parent_observation = _validated(
        _observation(
            cyclic_parent,
            observation_id="parent-observation",
            agent_id="parent-agent",
            task_id="parent-task",
            start_watermark=3,
            task_watermark=4,
            observation_watermark=5,
            parent_agent_id="parent-agent",
        ),
        cyclic_parent,
    )
    before = copy.deepcopy(parent_observation)
    _assert_refusal(
        lambda: derive_parent_binding(
            nested,
            context=_context(),
            admissions={cyclic_parent["admission_id"]: cyclic_parent},
            observations={parent_observation["observation_id"]: parent_observation},
        ),
        "ownership-conflict",
    )
    assert parent_observation == before


def test_recomputed_binding_digest_substitution_is_refused():
    top = _admission("parent-admission", watermark=2)
    nested = _admission("nested-admission", watermark=20, agent_id="parent-agent")
    observation = _validated(
        _observation(
            top,
            observation_id="parent-observation",
            agent_id="parent-agent",
            task_id="parent-task",
            start_watermark=3,
            task_watermark=4,
            observation_watermark=5,
        ),
        top,
    )
    admissions = {top["admission_id"]: top}
    observations = {observation["observation_id"]: observation}
    binding = derive_parent_binding(
        nested, context=_context(), admissions=admissions, observations=observations
    )
    assert binding is not None
    changed = dict(binding)
    changed["observation_digest"] = "b" * 64
    _assert_refusal(
        lambda: validate_parent_binding(
            nested, changed, context=_context(), admissions=admissions, observations=observations
        ),
        "ownership-conflict",
    )
