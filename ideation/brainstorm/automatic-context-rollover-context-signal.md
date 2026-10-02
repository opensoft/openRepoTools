# Session-Scoped Context Signal — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Reuse Claude's atomic per-transcript status-line snapshot as the sole context-window signal for automatic rollover.
Topics: automatic-context-rollover, context-signal, claude-hooks, observability
Repository context: openRepoTools Claude session tooling and its installed status-line and usage-guard integration
Captured: 2026-09-15

## Possible feats

- **Reliable context threshold input** — Expose a fresh, session-bound context percentage to rollover policy without estimating tokens or scraping a terminal.

## Focus

This document isolates where the automatic rollover percentage comes from and how it remains attached to one transcript rather than a rotating Claude profile.

## Proposed model

The status-line command already receives `context_window` data from the Claude harness and writes `context_pct` atomically to a session-keyed file. The automatic controller reads that same snapshot. It accepts only a numeric value, a matching transcript identity, and an age inside a strict freshness window.

Context percentage is session-scoped. Five-hour and weekly limits are profile-scoped and cannot substitute for it. The default automatic threshold is 65% when the operator has enabled the policy, leaving headroom to create a meaningful handoff.

## Interfaces and boundaries

The status line owns observation and publication. The rollover controller owns freshness and threshold evaluation. Neither owns lane identity, handoff generation, or process restart.

Missing or stale input is not evidence that context is low. It is evidence that automatic action is unavailable; the session remains alive.

## Alternatives and tensions

Token estimation from transcript size is portable but disagrees with the harness's effective context accounting. A polling daemon can read the same snapshot continuously, but it adds no better signal and creates pressure to act during an active turn.

The freshness bound should be tighter for automatic action than for a warning, but the exact duration must tolerate ordinary status-line update cadence.

## Open questions

- What snapshot age should automatic action accept?
- Should the snapshot carry an explicit schema version and publisher timestamp in addition to filesystem modification time?

## Relationships

The signal feeds [Safe Completed-Turn Trigger](automatic-context-rollover-safe-turn-trigger.md). The combined control loop is described in [Synthesis: Safe Automatic Context Rollover](automatic-context-rollover-synthesis-safe-rollover.md).
