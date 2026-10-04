# Semantic Handoff Before Restart — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Automatic rollover must invoke Claude's semantic `/ctx` workflow before the guarded backend may replace the pane.
Topics: automatic-context-rollover, semantic-handoff, lane-worktree-recovery-state, ctx
Repository context: openRepoTools handoff skill, lane-handoff backend, and crash-consistent lane lifecycle
Captured: 2026-09-15

## Possible feats

- **Automatic ctx parity** — Give threshold-triggered rollovers the same handoff narrative, writer accounting, durable state, and fresh-session first prompt as manual `/ctx`.

## Focus

This document isolates why a daemon calling `lane-handoff --restart` is not by itself equivalent to `/ctx`.

## Proposed model

Manual `/ctx` asks Claude to invoke the handoff skill with `--restart`. Claude captures current reasoning and unfinished intent, discovers and polls active writers, and refreshes the handoff. The backend then performs the durable lane writes and respawns the pane through the lane launcher.

Automatic rollover follows the same order. The threshold controller requests the semantic operation; it does not jump directly to pane replacement. The crash-consistent lifecycle enters `SWAPPING` before preservation and reaches `SWAPPED` only after every mandatory handoff and state write succeeds. A fresh session returns the lane to `RUNNING` only after confirmed SessionStart.

## Interfaces and boundaries

The handoff skill owns semantic state and writer communication. The lane backend owns durable transition and respawn mechanics. The prerequisite recovery capability owns generation fencing and reconciliation. The threshold controller owns none of these and must call their public seam.

A failure leaves the current pane alive. Missing uncommitted work cannot be recovered later merely because an automatic request existed.

## Alternatives and tensions

A shell-only handoff is faster and can operate after Claude has died, but it lacks the model's current reasoning and cannot message live subagents. It remains useful for late recovery, not as the normal automatic path.

At 65%, producing a semantic handoff consumes more context. That cost is intentional headroom, and argues against choosing a much later default.

## Open questions

- How should the fresh session distinguish an automatically requested rollover from a manual `/ctx` in its first prompt and audit record?
- Which failures should allow manual `/ctx` immediately and which require recovery of a stuck `SWAPPING` transition first?

## Relationships

This mechanism depends on the [Crash-Consistent Lane Worktree Recovery Overview](lane-worktree-recovery-state-overview.md) and completes the control loop in [Synthesis: Safe Automatic Context Rollover](automatic-context-rollover-synthesis-safe-rollover.md).
