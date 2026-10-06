# Supervised Context Restart Overview — Brainstorm

Status: brainstorm
Kind: reference
Summary: Make `/ctx` a durable, generation-fenced restart transaction whose replacement launcher survives failure and marks the lane running only after confirmation.
Topics: supervised-context-restart, ctx, semantic-handoff, crash-consistent-lifecycle, automatic-context-rollover
Repository context: openRepoTools with an integration boundary at the workBenches-owned pclaude launcher
Captured: 2026-09-15

## Possible feats

- **Supervised `/ctx`** — Preserve the semantic handoff, replace the old context, start a fresh session automatically, and retain a visible recovery surface on every launch failure.
- **Safe automatic context execution** — Supply the confirmed restart primitive required by threshold-triggered rollover.

## Motivation

`/ctx` is intended to clear context and immediately continue from a handoff without another operator command. The current implementation successfully preserves the handoff before replacing the pane, but it passes `lane <name>` or `pclaude` directly to `tmux respawn-pane` and treats tmux's acceptance as success. The old Claude is then gone before anyone knows whether the replacement launched.

One observed run wrote its handoff and `PAUSED` record, killed the old process, and left no replacement session. The design has no surviving process to report a launcher error, and its fresh-session intent exists only in the lost command environment. The human-facing `lane` dispatcher can also legally choose an attach/select path in which nothing is launched, making it unsuitable as an internal restart primitive.

## Goals

- Preserve the one-command `/ctx` experience when all components succeed.
- Keep the old session alive until semantic preservation and exclusive lifecycle ownership are complete.
- Preserve exact fresh-session launch intent across child failure.
- Leave an observable process and safe retry path whenever replacement fails.
- Mark the lane running only after the intended replacement is positively identified and alive.
- Give manual and automatic context rollover one authoritative backend.

## Non-goals

- Replacing semantic handoff generation with a shell-only summary.
- Making the human-facing `lane` dispatcher a narrower internal API.
- Reconstructing work that was never written to a surviving worktree or handoff.
- Adding a continuously polling system daemon merely to supervise context restart.
- Changing profile rotation into lane identity.

## What the system delivers

The proposed system separates semantic preparation from deterministic mechanics. Claude captures reasoning and writer state, then calls one guarded backend. That backend acquires generation ownership, performs mandatory writes, and creates a durable restart intent. Tmux starts a pane-resident supervisor, which directly launches the exact fresh session as a child and remains visible on failure. A readiness check finally moves the lane to `RUNNING`.

For operators, success still looks like typing `/ctx` once. Failure changes substantially: the pane remains, explains the failed stage, and offers an idempotent retry rather than silently exiting.

## System model

```text
RUNNING
  |  semantic handoff + exclusive compare-and-swap
  v
SWAPPING
  |  writer inventory + handoff + protocol records
  v
SWAPPED + durable restart intent
  |  tmux starts surviving supervisor
  v
STARTING (or fenced attempt beneath SWAPPED)
  |  replacement identity and liveness confirmed
  v
RUNNING

Any pre-commit failure: old session remains alive.
Any launch failure: supervisor and restart intent remain available.
```

## Cluster map

- [Synthesis: Reliable Context Rollover](supervised-context-restart-synthesis-reliable-rollover.md) — joins semantic authority, durable intent, process supervision, and readiness into one transaction.

## How it fits

The proposal refines the replacement edge of [Crash-Consistent Lane Worktree Recovery](lane-worktree-recovery-state-overview.md). That work owns lane generations, worktree inventory, and interrupted-swap recovery. Supervised context restart owns the narrower interval from a completed handoff to a confirmed fresh process.

It also becomes a prerequisite for [Automatic Context Rollover](automatic-context-rollover-overview.md). The threshold controller may request the semantic workflow, but it should report completion only after supervised startup confirmation.

The pclaude launcher remains responsible for profile/account selection. Whether the supervisor belongs in openRepoTools or workBenches is an ownership decision; either way, the internal launch surface must be narrower than the operator-facing `lane` command.

## Key decisions and open questions

Load-bearing proposed decisions are to fail closed when transition ownership cannot be acquired, persist fresh launch semantics as data, never call `lane` from the internal restart path, and retain a pane process through launch failure.

The main unresolved decisions are whether to add a first-class `STARTING` state, where the supervisor is owned, how readiness is confirmed without violating the generic SessionStart hook contract, and whether restart-only supervision should later expand to every lane launch.

## Document map

### Synthesis

- [Reliable Context Rollover](supervised-context-restart-synthesis-reliable-rollover.md)

### Atomic documents

- [Semantic and Mechanical Restart Boundary](supervised-context-restart-semantic-mechanical-boundary.md)
- [Durable Context-Restart Intent](supervised-context-restart-durable-intent.md)
- [Pane-Resident Restart Supervisor](supervised-context-restart-pane-supervisor.md)
- [Positive Replacement Startup Confirmation](supervised-context-restart-startup-confirmation.md)
