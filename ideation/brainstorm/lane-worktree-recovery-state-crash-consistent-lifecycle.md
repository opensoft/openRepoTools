# Crash-Consistent Lane Lifecycle — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Persist RUNNING, SWAPPING, and SWAPPED as guarded transitions so token exhaustion before or during a handoff is distinguishable and recoverable.
Topics: lane-worktree-recovery-state, crash-consistent-lifecycle, swap, session-binding
Repository context: openRepoTools `/swap`, `lane-handoff`, `lane-start`, and SessionStart behavior
Captured: 2026-09-15

## Possible feats

- **Two-phase swap** — Mark a swap in progress before preservation work and complete it only after every required handoff write succeeds.
- **Generation-fenced transition** — Prevent a delayed old process from overwriting the state of a newer resumed session.

## Focus

This document isolates lane-level lifecycle state and transition ordering. A session may exhaust tokens before `/swap`, during `/swap`, after a clean swap, or while a replacement is starting. Those cases must not collapse into one ambiguous `PAUSED` observation.

## Proposed model

Use an atomically replaced current-state sidecar plus the existing append-only lane event history:

```text
RUNNING --/swap begins--> SWAPPING --handoff complete--> SWAPPED
   ^                                                     |
   +------- confirmed replacement SessionStart ----------+
```

`/swap` first performs a compare-and-swap from `RUNNING` to `SWAPPING`. It then inventories worktrees, polls writers, records dirty and unpushed state, refreshes the handoff, and lands the protocol's pause writes. Only after every required step succeeds may it compare-and-swap the same operation from `SWAPPING` to `SWAPPED`.

Each transition carries at least:

```yaml
state: swapping
generation: 42
operation_id: 73989e7c-0000-0000-0000-000000000000
session_id: <transcript-uuid>
agent: claude
profile: team-01l
updated_at: <UTC>
```

The finishing write must match both `generation` and `operation_id`. A stale `/swap` process therefore cannot mark a lane `SWAPPED` after another process has recovered or resumed it.

The replacement must not write `RUNNING` merely because a launcher was invoked. `RUNNING` is written only after SessionStart confirms the new process, transcript, canonical lane, directory, and binding. An optional `RESUMING` state can make the launch interval explicit; without it, state remains `SWAPPED` until confirmation.

## Interfaces and boundaries

The lifecycle owns lane intent and transition authority. It consumes a verified session/binding identity and emits state changes. Liveness remains an observation from process/session records and must not be inferred from the state word alone.

This lifecycle does not claim that work is durable. `SWAPPED` means the required swap procedure completed; durability assertions come from the worktree reconciliation checks.

## Alternatives and tensions

- Reusing only append-only `PAUSED` and `RESUMED` events preserves one source but makes an interrupted multi-step swap harder to distinguish without an explicit `SWAPPING` event.
- A mutable sidecar gives a cheap current-state read but needs atomic replacement, locking, and an append-only audit event to explain every change.
- A heartbeat can identify abandoned `RUNNING` and `SWAPPING` states sooner, but process identity and namespace boundaries remain the stronger liveness evidence.

## Open questions

- Is `RESUMING` worth a fourth persisted state, or should `SWAPPED` remain until SessionStart?
- What timeout, if any, changes an indeterminate holder into a recovery candidate?
- Which swap steps are mandatory before `SWAPPED`, and which may finish asynchronously?
- Is recovery allowed to complete an interrupted operation ID, or must it always create a new generation?

## Relationships

The state refers to worktrees placed by [Canonical Lane-Owned Worktree Layout](lane-worktree-recovery-state-canonical-layout.md). Its crash outcomes are interpreted by [Resume-Time Worktree Reconciliation](lane-worktree-recovery-state-resume-reconciliation.md).
