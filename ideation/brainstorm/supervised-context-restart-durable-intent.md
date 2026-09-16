# Durable Context-Restart Intent — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Persist the exact fresh-session launch intent before `/ctx` replaces its current process so a failed launch remains diagnosable and idempotently retryable.
Topics: supervised-context-restart, durable-restart-intent, ctx, crash-consistent-lifecycle
Repository context: openRepoTools lane handoff, lifecycle state, and fresh-session launch behavior
Captured: 2026-09-15

## Possible feats

- **Restart intent record** — Store the lane, directory, profile, agent, handoff, generation, operation, and fresh-session requirement as one guarded launch request.
- **Idempotent context restart** — Retry the same unfinished launch without resuming the old transcript or minting competing operations.

## Focus

This document isolates the information that must survive between completing a semantic handoff and successfully starting its replacement session. Today `LANE_START_FRESH=1` exists only in the command passed to `tmux respawn-pane`; when that command exits, the durable lane records retain a pause but not the exact launch that was intended.

## Proposed model

After the handoff operation reaches its preservation commit point, write an atomic restart-intent sidecar under the lane's local control root:

```yaml
schema: 1
lane: openRepoTools-3
generation: 42
operation_id: <uuid>
state: pending
agent: claude
profile: team-01l
directory: /workspace/projects/openRepoTools
handoff: handoffs/openRepoTools/session-handoff-2026-09-15-lane-openRepoTools-3.md
mode: fresh-from-handoff
old_transcript: <uuid>
requested_at: <UTC>
```

The record is written before process replacement and compare-and-swap fenced by lane generation and operation ID. Launch attempts update bounded status such as `pending`, `starting`, `ready`, or `failed`, plus diagnostic details. The intended mode is data, not a one-use environment variable.

A retry consumes the same pending operation. It does not silently mint a second generation, resume the old transcript, or reinterpret a normal lane launch as a context clear.

## Interfaces and boundaries

The semantic handoff supplies the handoff path and old-session facts. The crash-consistent lifecycle supplies generation and operation ownership. The restart supervisor consumes the intent and records launch outcome.

The intent does not prove that a replacement is running. It records what must be attempted and preserves failure evidence. Positive startup confirmation remains a separate concern.

The local sidecar is sufficient for same-workstation pane replacement. Cross-workstation continuation still depends on the workspace repository and estate records; whether restart intent itself should be replicated remains open.

## Alternatives and tensions

- An environment variable is simple but disappears with the failed process and cannot support safe retry.
- Encoding launch intent only in prose inside the handoff is human-readable but makes exact, fenced consumption difficult.
- Reconstructing intent from the latest `PAUSED` event risks confusing a profile switch, ordinary handoff, and context clear.
- Retaining failed intents improves diagnosis but requires explicit cleanup rules after success, cancellation, or lane retirement.

## Open questions

- Should the intent use a distinct `STARTING` lifecycle state or remain a child record beneath `SWAPPED`?
- Which failure details are safe and useful to persist without capturing credentials or command-line secrets?
- Can an operator cancel a pending restart while keeping the lane cleanly `SWAPPED`?

## Relationships

The [Pane-Resident Restart Supervisor](supervised-context-restart-pane-supervisor.md) consumes this record, and [Positive Replacement Startup Confirmation](supervised-context-restart-startup-confirmation.md) decides when it is complete. Generation ownership comes from [Crash-Consistent Lane Lifecycle](lane-worktree-recovery-state-crash-consistent-lifecycle.md).
