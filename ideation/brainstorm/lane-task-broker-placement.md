# Broker Worker Placement — Brainstorm

Status: brainstorm
Kind: architecture
Summary: The lanes service selects account, model and local or remote execution placement for delegated tasks.
Topics: lane-task-broker, task-assignment, lane-session-operations, worker-placement
Repository context: openRepoTools broker mode with workBenches profiles and execution-site custodians
Captured: 2026-10-03

## Possible feats

- **Worker placement service** — Admit each delegated task once, choose a qualified account/model/host and collect correlated results.

## Focus

Brett wants the main agent to perform primary orchestration while LS places
implementation work, including workers on other computers.

## Selected direction

Retain ordinary lane swap and add an explicit broker mode. In broker mode,
the main agent supplies task scope, acceptance criteria, dependencies and
capability needs. Every delegation, including workers requesting further
help, goes through LS. LS selects the authorized account, model/harness,
host and container and records dispatch before launch.

A worker using another account is a separate runtime/session. It is not a
Claude native child whose credentials are changed. Keep the preferred
one-Speckit-task-per-implementation-worker default and allow several workers
on a task with explicit roles and file boundaries.

## Interfaces and boundaries

LS owns admission, assignment attempts, placement and result correlation;
agents own task reasoning and semantic review. Execution-site custodians
provide authenticated local runtime/exit evidence. EGS owns persistent jobs
separately from worker inference. Neither a remote heartbeat timeout nor an
accepted launch handle proves that a worker exited or finished.

The main agent can remain on its account while worker bindings change from
B to C to D. This reduces main-agent implementation usage but does not
guarantee that it avoids five-hour/weekly limits or context growth.

## Alternatives and tensions

Local workers share convenient filesystem access; remote workers need an
explicit repository revision, workspace custody and artifact-return path.
Native children preserve one runtime's behavior but cannot independently
select accounts/hosts. Brokered sessions provide that placement freedom at
the cost of more session, permission and result bookkeeping.

## Open questions

The API names, qualified adapters and host pools remain implementation choices
under the [broker contract](../../specs/001-separate-swap-ctx-handoff/contracts/lane-task-broker.md).
The selected modes do not assert runtime acceptance.

## Relationships

- [Omnigent reuse](lane-task-broker-omnigent-adapter.md) supplies candidate runtime mechanisms.
- [Two-mode synthesis](lane-task-broker-synthesis-two-modes.md) relates placement to existing swap safety.
