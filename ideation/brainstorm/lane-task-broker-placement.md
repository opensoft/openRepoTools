# Broker Worker Placement — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Omnigent places delegated tasks on qualified accounts and hosts while LS preserves task attachments across parent swaps.
Topics: lane-task-broker, task-assignment, lane-session-operations, worker-placement
Repository context: openRepoTools broker mode with workBenches profiles and execution-site custodians
Captured: 2026-10-03

## Possible feats

- **Worker allowance admission** — Place a small task on a qualified account with enough estimated allowance plus reserve, using the existing factory dispatcher.

## Focus

Brett wants the main agent to perform primary orchestration while Omnigent
manages delegated workload, including workers on other computers. LS handles
the main lane's account transfer and its stable task/result attachments.

## Selected direction

Retain ordinary lane swap and add an explicit broker mode. In broker mode,
the main agent supplies task scope, acceptance criteria, dependencies and
capability needs. Lane-facing task requests, including new worker-requested
tasks, go through LS and existing factory admission. Omnigent's worker layer
selects authorized account/model/harness/host placement and records attempts
before launch. Admitted internal execution remains within that factory scope.

Prefer small tasks and fresh allowance observations covering estimated cost
plus reserve after concurrent reservations. Stale/unknown or insufficient
allowance queues/refuses; consumption can exceed an estimate. Account allowance
selection and worker replacement are extensions, not current proven features.

A worker using another account is a separate runtime/session. It is not a
Claude native child whose credentials are changed. Keep the preferred
one-Speckit-task-per-implementation-worker default and allow several workers
on a task with explicit roles and file boundaries.

## Interfaces and boundaries

LS owns lane request/consumer generations, parent swap and durable result
correlation; Omnigent owns admitted workload, placement and worker attempts;
agents own task reasoning/review. Execution-site custodians provide runtime/
exit/effect evidence. A remote worker uses its own site's EGS with site and
supervisor-qualified job references, not implicitly A's local EGS. Neither a
remote timeout nor an accepted launch proves worker exit/completion.

A→B moves the consumer attachment to existing factory tasks while independent
workers continue. LS buffers results and hands B task references/watermarks;
B does not redispatch those tasks. Worker account replacement is internal to
Omnigent under the same logical task ID, with separate attempt evidence.

For engineers contributing spare compute, propose a shared cloud/Azure LS
gateway and authenticated outbound enrollment, reusing the existing factory
host/worker registry. CPC can qualify local operation first. Each execution
site retains a local controller/custodian and EGS; cloud selection cannot
replace local swap authority. CPU permission and model account permission are
separate. Exact Azure resources and transport qualification remain pending.

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

- [Omnigent reuse](lane-task-broker-omnigent-adapter.md) identifies existing worker mechanisms and missing recovery capabilities.
- [Two-mode synthesis](lane-task-broker-synthesis-two-modes.md) relates placement to existing swap safety.
