# Lane Task Broker Overview — Brainstorm

Status: brainstorm
Kind: reference
Summary: Offer ordinary lane swap and a broker mode where the main agent orchestrates and LS delegates to local or remote workers.
Topics: lane-task-broker, lane-session-operations, task-assignment, worker-placement
Repository context: openRepoTools with workBenches profiles, Omnigent execution and OmniWorker host operations
Captured: 2026-10-03

## Possible feats

- **Brokered factory work** — Preserve task continuity through parent swaps while Omnigent manages workers on qualified accounts and execution hosts.

## Motivation

Brett wants main agents to spend their tokens on primary orchestration and
delegate heavy work through LS. Worker accounts may change as they exhaust
quota, and workers may run away from the main computer. Existing lane swap
must remain available as its own operating mode.

## Goals

- Preserve swap mode and introduce explicit broker enrollment.
- Use LS for lane-facing task requests and stable consumer/result attachments.
- Reuse Omnigent/factory worker placement, workload and qualified recovery.
- Collect task results and evidence durably without model-driven polling.
- Support enrolled local and remote workers with exclusive workspace custody.

## Non-goals

This packet does not claim native Claude children can switch accounts, certify
remote interruption, provision cloud hosts, upgrade Omnigent or activate a
new broker. Existing swap safety and its graceful-only gate remain intact.

## What the system delivers

The main agent submits task scope and reviews results. LS persists task
references/results and swaps the main parent. Omnigent selects authorized
placement and manages admitted workload/internal attempts; each site's EGS
owns that site's persistent commands. Small tasks and estimated allowance plus
reserve aim to avoid mid-task exhaustion; worker recovery still needs qualified
extensions. Existing artifacts and job records survive safely accounted work.

## System model

Main agent → LS → existing factory/Omnigent worker rail → local/remote worker
→ durable task result → LS → current main parent. New delegated tasks use
the same admission path. A→B changes the task consumer, leaving independent
workers running; LS supplies B outstanding references and buffered results.
Omnigent worker-account recovery keeps the outer task identity and changes
internal attempts only through a qualified execution-site boundary.

## Cluster map

- [Swap and Broker Modes](lane-task-broker-synthesis-two-modes.md) connects placement, Omnigent reuse and existing account-transfer safety.

## How it fits

The [proposal](../../openspec/changes/separate-swap-ctx-handoff/proposal.md)
and [broker contract](../../specs/001-separate-swap-ctx-handoff/contracts/lane-task-broker.md)
record the selected two-mode direction. T059–T062 define a separate broker
tranche in the existing feature, without gating T054–T057. The
[task recovery packet](speckit-task-recovery-overview.md) supplies assignment
and review rationale. This packet remains non-normative; implementation
acceptance comes from the governed contract and qualified runtime evidence.

## Key decisions and open questions

LS owns parent swap and stable task attachments; Omnigent owns worker workload,
placement and qualified recovery; agents own task reasoning. Session lifecycle
tools exist, but allowance-aware selection and safe worker account swaps were
not found as complete features. Sharing swap/custody machinery is an option,
not a component-layout ruling. Adapters, policy and remote custody need runtime
evidence. Reduced parent usage cannot guarantee avoiding quota/context limits.

## Document map

- Synthesis: [Swap and Broker Modes](lane-task-broker-synthesis-two-modes.md)
- Atomic: [Worker Placement](lane-task-broker-placement.md)
- Atomic: [Omnigent Adapter](lane-task-broker-omnigent-adapter.md)
