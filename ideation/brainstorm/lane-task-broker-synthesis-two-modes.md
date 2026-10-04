# Synthesis: Swap and Broker Modes — Brainstorm

Status: brainstorm
Kind: architecture
Summary: LS swaps the parent and preserves task attachments while Omnigent manages independent local or remote workers.
Topics: lane-task-broker, lane-session-operations, worker-placement, omnigent-adapter, synthesis
Repository context: openRepoTools lane lifecycle and delegated execution
Captured: 2026-10-03

## Possible feats

- **Independent orchestration and execution** — Keep delegated tasks alive while the main lane changes accounts, using stable task/result attachments.

## Members and their joints

Atomic members: [Worker placement](lane-task-broker-placement.md),
[Omnigent adapter](lane-task-broker-omnigent-adapter.md) and
[Factory access and packaging](lane-task-broker-access-and-packaging.md).

### Semantic orchestration meets deterministic placement

A specifies work and acceptance; LS records the request; the admitted factory/
Omnigent layer selects resources and starts the worker; LS collects results;
A reviews the result and selects the next task. Only reasoning steps require
the main model. Waiting, routing, usage watching and result persistence run
outside its harness.

### Swap remains the account-transfer primitive

Swap mode retains the current qualified native-child architecture and exact
parent transfer. Broker mode introduces separately identified worker sessions
and prevents direct spawn bypass. A qualified worker can use existing swap
machinery through an owning execution-site integration while A orchestrates;
that worker controller is not yet implemented/qualified. A can still need its
own swap: LS fences A's task-control generation and supplies B existing task
references and buffered results while independent workers continue. Native
swap-mode children retain their shutdown/fresh-child rules.

### Remote placement retains local custody

Omnigent can select remote hosts, but runtime identity and exit facts come from
their custodians. Unknown worker ownership blocks duplicate execution. A
filesystem observation on A's machine is not a remote worker's workspace or
effect proof. Remote jobs belong to their site's EGS and retain site/supervisor/
job identities independently of the worker account or main-parent generation.
Isolated/accounted work can continue through parent swap; uncertain overlapping
workspace effects still retain the parent's release gate.

### Shared cloud entry meets engineer-owned compute

A shared cloud/Azure LS endpoint lets enrolled xFactory hosts initiate outbound
contact without exposing a workstation listener. Existing Omnigent/factory
registration and placement serve both CPC and engineer workers; local custody
controllers/EGS retain execution authority. Spare CPU grants no model-account
permission. Cloud loss preserves unknown remote state and can hold shared
admission while locally admitted work remains within its recorded authority.
Local CPC qualification can precede this distributed shape.

### Packaging preserves factory authority

The accepted first delivery keeps LS lifecycle control independent of Omnigent
and shared factory/cloud services. Factory broker clients use
codexFactory admission before existing Omnigent dispatch, with shared pool
grants independent of what is installed on the client. A selected lightweight
client consumes that same service without a full local factory installation.
Private Omnigent delegation is deferred outside the first delivery. A future
separate capability could serve owner workstation/VPS workers; it cannot acquire
CPC access or become a fallback for refused/unknown factory work. Exact API and
package layout remain implementation design work.

## Emergent behavior

Heavy work can move among worker accounts and computers without moving the
main orchestration session each time. The [task recovery default](speckit-task-recovery-overview.md)
provides bounded task scopes and a consistent review inventory across both
modes.

## Tensions to hold

Broker mode offers flexible placement and adds remote trust, workspace and
result-routing obligations. Omnigent supplies runtime plumbing; its worker
layer still needs allowance admission and qualified worker recovery. LS needs
stable consumer transfer and durable result delivery. Keep capability
records explicit so new worker sessions cannot be mistaken for native child
continuation in swap mode.

## Recombination opportunities

Connect task-purpose/model policy, registered worker capacity and usage
observations to Omnigent placement, with small tasks, estimated allowance plus
reserve and validated routing. Estimates reduce exhaustion risk but do not
replace qualified recovery or explicit held/failed outcomes.

## Open questions

Adapter/build qualification and remote custody evidence remain implementation
work; the [overview](lane-task-broker-overview.md) links the governed tranche.
