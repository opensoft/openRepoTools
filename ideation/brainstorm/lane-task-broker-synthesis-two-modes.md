# Synthesis: Swap and Broker Modes — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Keep existing lane account transfer and add LS-brokered worker placement so orchestration can continue across local or remote worker changes.
Topics: lane-task-broker, lane-session-operations, worker-placement, omnigent-adapter, synthesis
Repository context: openRepoTools lane lifecycle and delegated execution
Captured: 2026-10-03

## Possible feats

- **Two-mode lanes service** — Use one service admission/recovery boundary for ordinary swaps and explicitly brokered task execution.

## Members and their joints

Atomic members: [Worker placement](lane-task-broker-placement.md) and
[Omnigent adapter](lane-task-broker-omnigent-adapter.md).

### Semantic orchestration meets deterministic placement

A specifies work and acceptance; LS records the request and selects permitted
resources; an adapter starts the worker; LS collects evidence and results;
A reviews the result and selects the next task. Only reasoning steps require
the main model. Waiting, routing, usage watching and result persistence run
outside its harness.

### Swap remains the account-transfer primitive

Swap mode retains the current qualified native-child architecture and exact
parent transfer. Broker mode introduces separately identified worker sessions
and prevents direct spawn bypass. A qualified worker can use existing swap
on its execution site, while A continues to orchestrate. A can still need its
own later swap; delegation does not eliminate its usage or context limits.

### Remote placement retains local custody

LS can select remote hosts, but runtime identity and exit facts come from
their custodians. Unknown remote ownership blocks duplicate execution. A
filesystem observation on A's machine is not a remote worker's workspace or
effect proof. EGS jobs retain IDs independently of whichever account runs
the worker agent.

## Emergent behavior

Heavy work can move among worker accounts and computers without moving the
main orchestration session each time. The [task recovery default](speckit-task-recovery-overview.md)
provides bounded task scopes and a consistent review inventory across both
modes.

## Tensions to hold

Broker mode offers flexible placement and adds remote trust, workspace and
result-routing obligations. Omnigent reduces runtime plumbing; LS still has
to prove account selection, admission and recovery safety. Keep capability
records explicit so new worker sessions cannot be mistaken for native child
continuation in swap mode.

## Recombination opportunities

Connect task-purpose/model policy, registered worker capacity and usage
observations to placement, keeping optional AI routing behind LS validation.

## Open questions

Adapter/build qualification and remote custody evidence remain implementation
work; the [overview](lane-task-broker-overview.md) links the governed tranche.
