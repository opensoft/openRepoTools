# Omnigent Broker Adapter — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Extend the existing Omnigent worker layer for allowance admission and safe recovery, behind LS task requests and results.
Topics: lane-task-broker, omnigent-adapter, lane-session-operations, worker-placement
Repository context: openRepoTools LS adapter; Omnigent-Install and OmniWorker-Install retain their operational ownership
Captured: 2026-10-03

## Possible feats

- **Worker recovery controller** — Extend the existing worker rail with qualified account replacement behind a stable task/result interface.

## Focus

Which Omnigent mechanisms can implement broker execution without creating
another independent account/ownership authority?

## Evidence and reuse

Brett's follow-up identifies the existing CPC omniWorker and
codexFactory/openxFactory process as the first integration surface. The
existing execution-lane caller sends an approved bounded bundle through
codexFactory prepare/enforce to a CPC rider and receives patch/task-result
artifacts. Omnigent-Install implements registered worker selection, job/run/
event/artifact records and a worker inbox. OmniWorker-Install declares
subscription-auth control/coder/tester/integrator pools and isolated-worktree
coder assignments. Consume those surfaces and their existing factory gates;
LS adds parent-generation/task-consumer/result correlations; worker allowance
admission and recovery extensions belong in the owning Omnigent components.

The CPC patch worker is a single no-tool Claude invocation with no session
persistence. Declared coder/worktree profiles are a separate capability and
need runtime evidence. The observed clearing register has not admitted
`coding`; its grandfathered rider is not a general broker permission. See the
[integration contract](../../specs/001-separate-swap-ctx-handoff/contracts/lane-task-broker.md#existing-factory-worker-rail-is-the-first-adapter)
for source anchors and the authority split. Existing codexFactory MCP tools
inspect/verify patches, not worker dispatch.

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

The October 4 [local launcher decision](lane-task-broker-local-launchers.md)
requires the local native-Claude communication adapter for admitted lanes.
`oclaude` uses the existing profile launch primitive; `lclaude` supplies lane
admission while direct `pclaude` stays outside Omnigent and lanes. This is local
parent session integration, distinct from the factory worker adapter and the
deferred private worker broker. T063–T065 qualify native custody/profile/history
and API/web/queued input fencing; session status alone proves none of these.

LS authenticates lane requests and retains stable factory task references.
Omnigent manages admitted workload, placement and internal worker recovery;
the adapter returns actual runtime/result/custody references. Agents receive
LS delegation tools; native/direct spawning cannot bypass factory admission.
The documented smart router can fall back after errors, so the owning placement
layer must validate the final route against the authorized pool and scope.

Omnigent-Install has worker selectors by pool, role, capability, availability
and capacity. OmniWorker-Install owns host/profile operational boundaries.
Reuse those surfaces where qualified while keeping local parent JSON swap/
custody records and each execution site's EGS persistent-job ownership.

Inspection found session interruption/history/resume and harness process
management, but no complete safe subscription-account worker-swap controller.
The existing dispatcher checks availability and concurrency, not remaining
subscription allowance. SDK interruption can terminate its process group;
`sys_session_close` marks a conversation closed rather than witnessing runtime
exit. Native cold resume reconstructs history and needs fidelity qualification
before serving this protocol. See the [bounded capability findings](../../specs/001-separate-swap-ctx-handoff/contracts/lane-task-broker.md#observed-lifecycle-support-and-missing-worker-swap).

Local controller installation belongs to OmniWorker-Install; shared cloud
gateway/orchestration integration belongs in the existing service owners.
Reuse a qualified outbound Omnigent host/tunnel connection for engineer hosts
where possible. The CPC manifest declares WSL Ubuntu/Docker CE; Linux custody
must run in the actual worker namespace. No cloud endpoint or host deployment
is implied by this direction.

## Alternatives and tensions

A direct headless-CLI adapter remains possible. Omnigent can reduce execution
and monitoring work, but does not establish subscription-allowance selection,
safe cancellation or remote source exclusion. Sharing qualified swap/custody
machinery with execution-site worker controllers is an option that avoids
duplicating the whole LS service. Pin and measure before depending on it.

## Open questions

Choose and qualify the exact adapter build, delegation-policy enforcement,
credential isolation and remote receipt contract in T061–T062. No upgrade,
cloud provisioning or live worker launch is performed by this documentation.

## Relationships

- [Placement](lane-task-broker-placement.md) describes the LS request and Omnigent placement boundary.
- [Two-mode synthesis](lane-task-broker-synthesis-two-modes.md) explains the adapter's place beside swap.
