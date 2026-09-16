# Positive Replacement Startup Confirmation — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Keep a lane non-running until evidence confirms that the intended replacement process, transcript, directory, and binding are alive.
Topics: supervised-context-restart, startup-confirmation, session-binding, crash-consistent-lifecycle
Repository context: openRepoTools lane-start, SessionStart reporting, and lifecycle transition behavior
Captured: 2026-09-15

## Possible feats

- **Confirmed `RUNNING` transition** — Move from a completed handoff to `RUNNING` only after the intended replacement proves its identity and liveness.
- **Launch-time recovery classification** — Distinguish a pending restart, an active startup attempt, an immediate child failure, and a ready replacement.

## Focus

This document isolates what evidence is required before the lane may claim `RUNNING`. Current `lane-start` writes `LIVE` before its final `exec`, so a launcher or Claude failure can leave a positive state for a process that never existed.

## Proposed model

Keep the lifecycle at `SWAPPED`, or move it to a fenced `STARTING`, while the supervisor launches the child. Confirm readiness only when evidence agrees on:

- canonical lane name;
- generation and restart operation;
- new transcript/session identifier;
- agent and selected profile;
- expected coordinator directory;
- exclusive pane/session binding;
- a live replacement process associated with that binding.

The confirming mechanism must be local, bounded, and idempotent. If the generic SessionStart hook must remain read-only and always exit zero, confirmation can come from a separate launcher-owned acknowledgment or from a supervisor check combining child liveness with newly created transcript and binding evidence. It must not be inferred merely from `exec` being attempted.

Only confirmation may write `RUNNING` and mark the restart intent `ready`. A timeout or child exit leaves the intent retryable and the lifecycle non-running; it does not fabricate `RESUMED` success.

## Interfaces and boundaries

`lane-start` may prepare and validate a launch, but pre-exec validation is not runtime readiness. The supervisor observes the child. The lane-state writer owns the fenced transition. SessionStart may report identity without becoming a blocking networked hook.

This confirmation does not certify that all writers were relaunched or that the model correctly understood the handoff. Those are post-start semantic responsibilities.

## Alternatives and tensions

- A SessionStart write is semantically direct but conflicts with the current rule that the generic hook is read-only, network-free, and non-blocking.
- A short process-liveness grace period is easy but can mistake a hung or misbound client for a ready session.
- Transcript-file creation plus process liveness is stronger, but profile storage paths and timing must be handled without races.
- Letting the new model stamp itself `RESUMED` proves semantic execution but is too late and too nondeterministic to be the only process-level readiness signal.

## Open questions

- What is the minimum sufficient local readiness evidence on Claude, Codex, and future agents?
- How long may `STARTING` remain before the supervisor reports failure without killing a possibly slow but valid launch?
- Which component writes the append-only `RESUMED` event, and how is it ordered against local `RUNNING`?

## Relationships

This closes the operation recorded by [Durable Context-Restart Intent](supervised-context-restart-durable-intent.md) and observed by the [Pane-Resident Restart Supervisor](supervised-context-restart-pane-supervisor.md). It refines the replacement edge in [Crash-Consistent Lane Lifecycle](lane-worktree-recovery-state-crash-consistent-lifecycle.md).
