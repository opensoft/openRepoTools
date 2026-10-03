# Omnigent Broker Adapter — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Reuse Omnigent session and policy tools behind LS while retaining service authority over account placement and safe recovery.
Topics: lane-task-broker, omnigent-adapter, lane-session-operations, worker-placement
Repository context: openRepoTools LS adapter; Omnigent-Install and OmniWorker-Install retain their operational ownership
Captured: 2026-10-03

## Possible feats

- **Omnigent execution adapter** — Map LS-admitted requests to qualified Omnigent sessions and join their output and lifecycle evidence.

## Focus

Which Omnigent mechanisms can implement broker execution without creating
another independent account/ownership authority?

## Evidence and reuse

Read-only inspection found the installed `sys_session_send` and
`sys_read_inbox` tools, session inspection/closure code and model-override
fields. The `py-bench` CLI reports `omnigent 0.1.1`, built June 16; that label
does not by itself identify or qualify every installed capability.

[Upstream session tools](https://omnigent.ai/docs/programmatic) support
creation, dispatch and result/history inspection.
[Routing](https://omnigent.ai/docs/build/routing) offers model/harness selection
and an external router hook. [Policies](https://omnigent.ai/docs/policies/builtin)
and [custom policies](https://omnigent.ai/docs/policies/custom) can constrain
tool use and delegation. [Remote runner infrastructure](https://omnigent.ai/docs/deploy/cloud-sandbox-host)
supports execution away from the main computer. These are candidates for
reuse, not measured LS integration.

## Interfaces and boundaries

LS admits and selects the worker. The adapter executes that recorded choice
and returns actual session, result and custody references. Agents receive LS
delegation tools; native or direct Omnigent spawn routes must not bypass LS.
The documented smart router can fall back after errors, so LS must validate
the final choice against its allowed placement rather than accept fallback
as new authorization.

Omnigent-Install has worker selectors by pool, role, capability, availability
and capacity. OmniWorker-Install owns host/profile operational boundaries.
Reuse those surfaces where qualified while keeping the authoritative local
JSON swap/custody records and EGS persistent-job ownership.

## Alternatives and tensions

A direct headless-CLI adapter remains possible. Omnigent can reduce execution
and monitoring work, but does not establish subscription-quota selection,
native cancellation semantics or remote source exclusion for LS. Pin the
actual build and measure these boundaries before depending on them.

## Open questions

Choose and qualify the exact adapter build, delegation-policy enforcement,
credential isolation and remote receipt contract in T061–T062. No upgrade,
cloud provisioning or live worker launch is performed by this documentation.

## Relationships

- [Placement](lane-task-broker-placement.md) supplies the authoritative request/selection.
- [Two-mode synthesis](lane-task-broker-synthesis-two-modes.md) explains the adapter's place beside swap.
