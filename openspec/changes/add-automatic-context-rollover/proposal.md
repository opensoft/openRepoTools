## Why

Claude already publishes a per-session context percentage and warns as the context window fills, but the operator must notice the warning and type `/ctx` before compaction or token exhaustion. A missed warning can strand an active lane without the semantic handoff and durable state transition that a controlled context rollover requires.

## What Changes

- Add an opt-in automatic context rollover policy with a default trigger at 65% session-context usage.
- Reuse the existing per-session status-line snapshot as the context signal; do not introduce a polling daemon as the primary controller.
- Evaluate automatic rollover only at a completed-turn boundary, never while Claude is generating, editing files, or running tools.
- Route the automatic action through the same semantic handoff-and-restart workflow as `/ctx`, including writer discovery and polling, handoff refresh, durable lane-state writes, and fresh-session relaunch.
- Latch each threshold crossing so one session generation can request at most one automatic rollover.
- Keep the current session alive and report a warning when the snapshot is stale, lane identity is missing, a handoff write fails, or crash-consistent transition ownership cannot be acquired.
- Preserve manual `/ctx` and allow the automatic policy or threshold to be disabled or overridden explicitly.
- Make this change depend on `add-crash-consistent-lane-worktree-recovery` and [opensoft/openRepoTools#91](https://github.com/opensoft/openRepoTools/issues/91); automatic rollover must not ship before the guarded `RUNNING -> SWAPPING -> SWAPPED` transition is available.

## Capabilities

### New Capabilities

- `automatic-context-rollover`: Fresh context-signal evaluation, safe turn-boundary triggering, one-shot policy control, and delegation to the governed `/ctx` workflow.

### Modified Capabilities

None. The prerequisite lane-recovery capability is being introduced by a separate active OpenSpec change and is consumed rather than redefined here.

## Impact

Tracked by [opensoft/openRepoTools#92](https://github.com/opensoft/openRepoTools/issues/92), queued for the existing `openRepoTools-3` Claude lane after prerequisite issue #91.

The change affects the Claude status-line snapshot contract, usage/context guard, Claude hook configuration, `/ctx` and `handoff` integration, per-session latch state, installation into bare and profiled Claude configurations, and hook/integration tests. It adds no requirement for a continuously running service and must not bypass the lane collision protocol, the handoff skill, or the crash-consistent transition controller.
