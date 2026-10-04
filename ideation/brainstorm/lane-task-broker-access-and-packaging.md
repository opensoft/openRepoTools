# Factory Access and LS Packaging — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Select independent LS swap and a lightweight authenticated factory client for the first delivery, deferring private Omnigent delegation.
Topics: lane-task-broker, factory-access, service-packaging, delegation-backend
Repository context: openRepoTools LS interfaces; codexFactory admission and Omnigent worker execution remain owned by their components
Captured: 2026-10-03

## Possible feats

- **Factory execution client** — Give an authorized LS user access to admitted factory tasks without requiring a full local factory installation.
- **Future private worker adapter** — Allow explicitly enrolled owner-operated Omnigent workers under a later separate capability without granting access to factory pools.

## Focus

Brett asks whether LS delegation enters codexFactory or Omnigent directly,
and whether engineers without codexFactory need a lighter install for their
own local or VPS workers. Shared CPC access must retain factory admission.
Brett agreed on October 3 to independent LS swap and authenticated factory
delegation with a lightweight client. Private delegation is deferred outside
the first delivery. Exact package layout and the admission API remain design
work. This packet captures rationale; the
[decision record](../../openspec/changes/separate-swap-ctx-handoff/claude-cli-supervised-jobs-decision.md#october-3-decision-first-delivery-access-and-packaging)
and [contract](../../specs/001-separate-swap-ctx-handoff/contracts/lane-task-broker.md#accepted-access-and-packaging-scope)
govern the selected scope.

## Selected scope and deferred option

| Option | Delivery scope | Dependency and route | Worker access |
| --- | --- | --- | --- |
| LS lifecycle only | Selected | Native CLI, local custodian/ledger and EGS as required; no Omnigent or shared factory/cloud dependency | Lane swap and supervisor jobs; no independent broker workers. |
| LS factory client | Selected | LS → codexFactory admission adapter → existing Hermes/Omnigent dispatch → omniWorker | Only the authenticated principal's admitted projects, operations and worker pools, including CPC if granted. Full local factory installation is not a client prerequisite. |
| LS private broker | Deferred | LS → owner-operated Omnigent → explicitly enrolled owner workers, with local custody/EGS | Own workstation or VPS hosts/accounts; no CPC/factory pool access without a separate factory grant. Requires a later separate qualified capability. |

The selected factory client uses the same factory service and admission policy.
Private Omnigent delegation remains a possible later adapter,
not a fallback when factory admission fails. Existing ordinary swap can run
without either delegation backend; current managed lane modules do not import
Omnigent. This source observation does not close the pending swap release gate.

## Interfaces and boundaries

Factory deployment topology can put LS, admission and Omnigent in one service
or several. Preserve the admission boundary even if an implementation directly
invokes Omnigent internally. Installing/cloning codexFactory is not a worker
grant. Authenticate caller identity and bind tenant/project, approved task
scope, pool/account permission and capacity/budget policy at admission. Host
compute contribution, model-account permission and ability to consume shared
workers are separate grants.

The current CPC workflow has approved binding/tenant/readiness/compliance
gates. The hosted codexFactory MCP adapter has authenticated inspect/verify
tools, not a worker-dispatch interface. Omnigent supplies session/auth/runtime
building blocks; those do not grant access to CPC. The inspected internal
Hermes handler's general job/dispatch paths do not themselves establish a
public authenticated per-tenant admission boundary. Reuse existing factory
authentication patterns and enforce admission in a qualified service adapter.

Bind every task to its backend/authority realm and stable job identity.
Reattach after parent swap to that backend; unknown work is not permission to
switch it to another provider. A private session ID is not a factory approval
or job identity. Each execution site still owns runtime custody and EGS jobs.

## Alternatives and tensions

Requiring the whole factory for every LS user simplifies distribution but
couples ordinary swaps to unrelated engineering services. Giving LS direct
access to shared Omnigent risks creating another factory dispatch authority.
A thin factory client retains shared admission with a smaller installation.
Private delegation supports owner compute but adds another explicit backend
contract, configuration and qualification burden. A VPS is owner-operated
remote compute, not automatically a shared factory worker.

## Open questions

- Exact client package, admission API and identity-to-pool grant integration.
  The hosted inspect/verify endpoint does not already implement dispatch.
- If a future private capability is separately approved, whether its adapter
  embeds a local Omnigent service or connects to an owner-operated one.

## Relationships

- [Worker placement](lane-task-broker-placement.md) separates Omnigent workload from LS task attachments.
- [Omnigent adapter](lane-task-broker-omnigent-adapter.md) records existing mechanisms and missing worker swap.
- [Two-mode synthesis](lane-task-broker-synthesis-two-modes.md) connects product packaging to lifecycle and execution authority.
