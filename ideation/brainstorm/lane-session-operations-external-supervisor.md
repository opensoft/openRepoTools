# External Account-Swap Supervisor — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Move account-switch mechanics into a surviving controller that records intent, stops execution, and resumes exact sessions without asking a model to prepare the switch.
Topics: lane-session-operations, external-supervisor, profile-switch, crash-consistent-lifecycle
Repository context: openRepoTools lifecycle orchestration and workBenches account selection
Captured: 2026-09-16

## Possible feats

- **Model-independent swap** — Initiate account replacement even when the old account cannot produce another model response.
- **Recoverable replacement** — Keep a visible controller and a retryable operation record when launch or authentication fails.

## Focus

The coordinator cannot be the only process responsible for replacing itself. An external controller must own the operation before the coordinator stops, with a supported control connection established when the lane starts.

## Proposed model

The controller validates the target profile and complete participant roster, closes admission to new work, interrupts generation, drains final events, records unresolved tool operations, verifies persistence and writer shutdown, launches the same transcripts under the target account, and releases execution after readiness checks.

The durable record holds operation ID, lane generation, source and target profile references, runtime version, coordinator/worker session IDs, parent relationships, canonical directories, task/tool status, and phase. It contains no credentials or model-generated narrative. Stable workspace identities and relative paths belong in shared records; host-local process/pane references belong in explicitly host-local, uncommitted runtime state.

The proposed phases are `preflight`, `quiescing`, `paused`, `starting`, and `ready`, with `failed` or `indeterminate` outcomes. They describe one operation and should reuse the lifecycle owner introduced by the existing recovery work, rather than add a competing lane-state authority.

## Interfaces and boundaries

openRepoTools owns operation identity, exclusive ownership, records, status, and recovery. workBenches owns profile lookup, credential isolation, and launching through the selected account. The runtime adapter owns interruption, event draining, transcript persistence evidence, child discovery, and exact resume support.

The first Claude adapter must prove it can observe and control the relevant frontend. SDK controls do not imply that a new SDK connection can attach to any already-running interactive CLI. Legacy lanes without an attached controller require explicit managed-launch enrollment.

## Alternatives and tensions

- **Suspend a process and alter credentials:** attractive latency, but suspension alone does not reload in-memory credentials, stop remote work, or establish a durable transcript boundary.
- **Reauthenticate an idle live runtime:** potentially preserves more state; deferred unless supported account reload and descendant behavior are demonstrated.
- **Stop and resume saved sessions:** proposed first implementation because exact conversation IDs and separate profile launches already exist. Child reconstruction still needs proof.

A small machine record is necessary even though a prose handoff is not. Without it a dead controller cannot determine whether a replacement already owns the lane.

## Open questions

- Which supported Claude control surface can provide the full stop/persist/resume acknowledgement chain?
- What latency target is realistic after measuring idle, generating, and tool-running sessions separately?

## Relationships

- [Worker restoration](lane-session-operations-worker-restoration.md)
- [Claude-first synthesis](lane-session-operations-synthesis-claude-first.md)
- [Existing restart supervision](supervised-context-restart-pane-supervisor.md)
