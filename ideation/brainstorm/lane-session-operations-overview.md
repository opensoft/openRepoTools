# Lane Session Operations Overview — Brainstorm

Status: brainstorm
Kind: reference
Summary: Separate swap, ctx, and handoff and deliver an externally controlled Claude account swap that reuses native conversations without generating handoffs.
Topics: lane-session-operations, profile-switch, ctx, semantic-handoff, claude-compatibility
Repository context: openRepoTools with workBenches profile launchers; Codex adapter deferred
Captured: 2026-09-16

## Possible feats

- **Claude-first session operations** — Preserve work across an account change with deterministic control, while retaining explicit context-reset and work-transfer workflows.

## Motivation

The current swap consumes model work to refresh a handoff, contact writers, and prepare a relaunch at the moment the account may have almost no quota left. The user wants to stop all participants quickly, switch to an account with available quota, and continue the same work. Existing native resume features make prose reconstruction potentially unnecessary.

## Goals

- Run account-swap preparation and control outside Claude, with no model request required from the exhausted account.
- Resume the exact coordinator and every supported unfinished worker, retaining worktrees and ownership.
- Make swap, ctx, and handoff have distinct visible outcomes.
- Deliver and verify Claude first; preserve an adapter boundary for Codex later.

## Non-goals

- An operating-system memory snapshot or restoration of arbitrary in-flight network requests.
- Cross-agent or cross-machine migration in the first release.
- Automatic account discovery/rotation, credential copying, context reduction during swap, or changes to estate park/resume mechanics.
- Claiming every native Claude team or child is restorable before the compatibility test proves it.

## What the system delivers

`swap` becomes an external account-switch transaction using native transcripts and a small operation record. `ctx` creates fresh context from an intentional semantic checkpoint. `handoff` communicates state and transfers work to another reader. The first release uses an explicitly selected authenticated Claude profile in the same configured storage family.

## System model

An external supervisor owns the lane's control connection and participant inventory. It preflights the target, stops new work, interrupts and drains participants, records a resumable boundary, replaces the old runtime under the new profile, and checks identity and liveness before releasing execution. Failure remains visible and retryable without a second writer.

## Cluster map

- [Claude-First Account Continuity](lane-session-operations-synthesis-claude-first.md) — relates operation semantics to external control, worker restoration, and delivery evidence.

## How it fits

The [OpenSpec proposal](../../openspec/changes/separate-swap-ctx-handoff/proposal.md) governs the requested split. It must reconcile Amendment 17's current alias contract and related restart/recovery work before shipping. The existing [supervised context restart](supervised-context-restart-overview.md) continues to describe fresh-context behavior, while [automatic context rollover](automatic-context-rollover-overview.md) remains a ctx consumer.

This packet is exploratory and non-normative. The user selected the direction and Claude-first priority; no implementation capability or protocol ratification is asserted.

## Key decisions and open questions

The selected direction is external account swapping without a generated handoff. The proposed first mechanism is controlled stop plus exact-ID native resume. The unresolved release gate is restoring all participant kinds in scope without model-mediated reconstruction. Unsupported configurations must be reported before intentional shutdown.

## Document map

- [Synthesis](lane-session-operations-synthesis-claude-first.md)
- [Command semantics](lane-session-operations-command-semantics.md)
- [External supervisor](lane-session-operations-external-supervisor.md)
- [Worker restoration](lane-session-operations-worker-restoration.md)
- [Evidence and delivery gates](lane-session-operations-evidence-and-delivery.md)
