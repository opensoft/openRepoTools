# Automatic Context Rollover Overview — Brainstorm

Status: brainstorm
Kind: reference
Summary: Automatically run the semantic `/ctx` workflow at a safe turn boundary when an opted-in lane coordinator reaches 65% context usage by default.
Topics: automatic-context-rollover, claude-hooks, ctx, lane-worktree-recovery-state
Repository context: openRepoTools with dependencies on Claude hook behavior and the lane collision protocol
Captured: 2026-09-15

## Possible feats

- **Proactive context continuity** — Move a lane into a fresh Claude session before compaction while preserving its reasoning, writers, directory, and durable lifecycle state.

## Motivation

The existing usage guard can see context pressure and warn, but the operator still has to notice and type `/ctx`. If that action is missed, compaction or exhaustion can arrive before the lane leaves a complete handoff. A separate daemon could watch the same percentage, but acting while Claude is generating or using tools creates a more dangerous failure mode.

## Goals

- Use the existing authoritative per-session context measurement.
- Default an enabled policy to a 65% threshold.
- Begin only after the current main-session turn completes.
- Produce the same semantic and durable result as manual `/ctx`.
- Prevent duplicate requests and stale-generation finalization.
- Keep the current session alive whenever safe rollover cannot be proven.

## Non-goals

- Interrupt Claude at the exact instant a metric crosses 65%.
- Replace non-lane compaction behavior.
- Use account rate limits as context-window measurements.
- Let a checked-out repository silently enable pane respawning.
- Ship before crash-consistent lane transitions exist.

## What the system delivers

An operator can explicitly enable automatic context rollover in user-owned configuration. The status line continues publishing context usage. At the end of a main Claude turn, a controller checks the fresh snapshot, policy, lane identity, ownership, and generation. At or above the threshold it records one request and asks Claude to run the semantic handoff skill with `--restart`. Successful handoff and lane writes respawn the pane into a fresh session; any uncertainty leaves the old session running with a precise warning.

## System model

```text
Claude harness
     |
     v
session context snapshot -----> completed-turn controller
                                      |  policy + lane admission
                                      v
                               one-shot request
                                      |
                                      v
                         Claude semantic handoff skill
                                      |
                                      v
                    RUNNING -> SWAPPING -> SWAPPED
                                      |
                                      v
                      fresh SessionStart -> RUNNING
```

## Cluster map

- [Safe Automatic Context Rollover](automatic-context-rollover-synthesis-safe-rollover.md) — joins observation, safe triggering, semantic handoff, and crash-consistent restart.

## How it fits

The status-line publisher and usage guard already provide observation and warning. `/ctx` already provides the user-invoked semantic workflow. The crash-consistent lane recovery proposal provides durable transition ownership. This proposal connects those capabilities without changing their authority boundaries.

The governed change is [add-automatic-context-rollover](../../openspec/changes/add-automatic-context-rollover/proposal.md), tracked by [opensoft/openRepoTools#92](https://github.com/opensoft/openRepoTools/issues/92). It depends on [add-crash-consistent-lane-worktree-recovery](../../openspec/changes/add-crash-consistent-lane-worktree-recovery/proposal.md) and [opensoft/openRepoTools#91](https://github.com/opensoft/openRepoTools/issues/91). This brainstorm is non-normative; the OpenSpec artifacts define implementation behavior.

## Key decisions and open questions

- Proposed: enabled policy defaults to 65% and remains configurable.
- Proposed: a main-session completed-turn hook is the trigger; no timer may interrupt active work.
- Proposed: enablement is user-owned and cannot come from repository content.
- Proposed: the hook requests Claude's semantic handoff rather than invoking only the shell restart tail.
- Open: the exact user command and configuration schema for enablement and threshold changes.
- Open: strict snapshot freshness and bounded retry policy.
- Open: whether a later `PreCompact` fallback should warn or request emergency rollover.

## Document map

### Synthesis

- [Safe Automatic Context Rollover](automatic-context-rollover-synthesis-safe-rollover.md)

### Atomic concepts

- [Session-Scoped Context Signal](automatic-context-rollover-context-signal.md)
- [Safe Completed-Turn Trigger](automatic-context-rollover-safe-turn-trigger.md)
- [Semantic Handoff Before Restart](automatic-context-rollover-semantic-handoff.md)
