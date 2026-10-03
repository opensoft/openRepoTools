# Lane Task Broker Overview — Brainstorm

Status: brainstorm
Kind: reference
Summary: Offer ordinary lane swap and a broker mode where the main agent orchestrates and LS delegates to local or remote workers.
Topics: lane-task-broker, lane-session-operations, task-assignment, worker-placement
Repository context: openRepoTools with workBenches profiles, Omnigent execution and OmniWorker host operations
Captured: 2026-10-03

## Possible feats

- **Brokered factory work** — Keep orchestration alive while LS places bounded tasks across qualified accounts, models and execution hosts.

## Motivation

Brett wants main agents to spend their tokens on primary orchestration and
delegate heavy work through LS. Worker accounts may change as they exhaust
quota, and workers may run away from the main computer. Existing lane swap
must remain available as its own operating mode.

## Goals

- Preserve swap mode and introduce explicit broker enrollment.
- Make LS the admission and placement path for every broker delegation.
- Collect task results and evidence durably without model-driven polling.
- Support enrolled local and remote workers with exclusive workspace custody.

## Non-goals

This packet does not claim native Claude children can switch accounts, certify
remote interruption, provision cloud hosts, upgrade Omnigent or activate a
new broker. Existing swap safety and its graceful-only gate remain intact.

## What the system delivers

The main agent submits task scope and reviews results. LS selects the account,
model/harness and host/container and manages the worker's recorded attempt.
An execution adapter runs the worker; EGS owns persistent commands. Fresh
workers consume the preferred one-task default and use existing artifacts
and job records when continuing safely unfinished work.

## System model

Main agent → LS → qualified local/remote worker → LS result → main agent.
Further worker delegation returns through LS. A worker-account transfer uses
its execution site's qualified swap/custody boundary; it does not require A's
main session to change accounts.

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

LS owns placement; agents own task reasoning; workers may be remote. Omnigent
has reusable tools, but the exact installed adapter, policy enforcement and
remote custody joins require measurement. Reduced main-agent usage does not
guarantee avoiding quota resets or context limits.

## Document map

- Synthesis: [Swap and Broker Modes](lane-task-broker-synthesis-two-modes.md)
- Atomic: [Worker Placement](lane-task-broker-placement.md)
- Atomic: [Omnigent Adapter](lane-task-broker-omnigent-adapter.md)
