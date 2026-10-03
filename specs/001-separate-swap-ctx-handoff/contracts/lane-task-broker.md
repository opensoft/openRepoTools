# Lanes service task broker

Status: prospective; implementation and runtime qualification pending

## Two explicit operating modes

Brett's October 3 direction retains ordinary lane swap and adds broker mode.
Mode selection is explicit; missing markers preserve existing validators and
meanings. Do not reinterpret existing native-child or historical runner records.

| Mode | Main agent | Delegation and account changes |
| --- | --- | --- |
| Swap | Runs the lane's current workflow with its qualified native tools/children | LS transfers the exact parent using the existing swap contract and verified source exit; the shared container stays running. |
| Broker | Performs primary orchestration: planning, task/dependency decisions and result review | All worker delegation goes through LS. LS selects an authorized account, model/harness, execution host and container, and may replace worker accounts while the main agent continues. |

Broker workers may run on the local computer or enrolled remote hosts. A worker
under another account is a separately launched runtime with its own actual
session identity, not a native child inside A's Claude process. Broker mode
does not make Claude's native Agent tool switch credentials or containers.
Existing swap remains available for a qualified worker runtime and for the
main lane if it eventually needs an account change.

## Division of responsibility

- **Main agent:** choose tasks, describe scope/acceptance/dependencies and
  capabilities needed, review results and decide semantic next steps.
- **LS:** validate and persist requests, choose placement within configured
  authorized pools, bind attempts to owners, collect results, observe usage,
  perform safe account-transfer/recovery sequencing and enforce admission.
- **Worker agent:** execute its bounded task and return progress, artifacts
  and evidence. Further delegation also goes through LS.
- **Execution-group supervisor:** admit and own external commands/jobs with
  stable IDs and persistent output/effects across agent account changes.
- **Execution adapter:** launch/control the selected harness on its execution
  site and report actual runtime evidence. Omnigent is a candidate adapter.

Expose a service delegation interface, conceptually request/status/result/cancel,
to the main agent and workers. Names and transport remain implementation work.
Broker policy must prevent native or direct Omnigent session spawning from
bypassing LS admission. Role instructions guide behavior; measured tool/policy
controls enforce the delegation route. Preserve swap mode's native policy.

## Requests, placement and results

A request includes authenticated caller identity/generation, an idempotency
key, repository/feature/task-definition binding, assignment/attempt, purpose,
scope, acceptance criteria/evidence references, workspace/resource needs and
allowed execution constraints. One Speckit task per implementation worker is
the preferred default; record bounded exceptions. Several workers may
contribute to one task with explicit roles and file ownership.

LS selects account, model/effort/harness and host/container from authorized,
qualified candidates using task policy, fresh quota observations and capacity.
The agent may request capabilities or express a preference; LS owns the actual
selection. No eligible candidate means queued/refused with a reason, never an
unrecorded fallback or a second owner. A routing suggestion from an AI API is
optional and cannot override permissions, custody or ownership checks.

Persist placement and dispatch intent before launch. Acknowledgment is not
worker completion. Correlate actual session/runtime identity, progress, outputs,
artifact revisions and terminal/effect evidence to the exact attempt. Results
are stored durably and delivered through LS, with bounded summaries/references
so the main agent need not read every child turn or poll through model calls.
Late results retain their attempt identity; do not let stale results approve a
new attempt or erase unresolved effects.

## Remote execution and recovery

Bind each worker to workstation/host, container/process namespace, runtime
incarnation and exact workspace/repository revision. The execution site's
custodian provides authenticated local ownership/exit/effect observations;
local PIDs, pane text or elapsed heartbeat time cannot certify a remote exit.
Network loss makes an attempt unknown/pending reconciliation, not permission
to launch a duplicate writer. Preserve authoritative JSON-ledger/custody roles;
the derived SQL index never authorizes dispatch, source retirement or release.

Supply a declared checkout/revision and scoped artifacts to remote workers;
a local filesystem path does not transfer a workspace. Explicit workspace
claims prevent overlapping writers. Results identify their base revision,
changed artifacts and acceptance evidence so integration can be reviewed.
Credentials stay in the selected execution site's managed profile/credential
custody; main agents and task/result payloads do not carry them.

On worker-account exhaustion, stop new admission for that binding and use its
qualified swap/recovery boundary. Preserve files, accepted work and EGS job
IDs; reconcile uncertain work and effects before a replacement can execute.
Remote placement does not itself add cross-machine transcript migration or
forced-stop support. The main agent may remain on its account while worker
accounts rotate, but low usage does not guarantee avoiding five-hour or weekly
limits or context growth.

All long-running/external commands remain worker → MCP bridge → LS → EGS.
Cancelling a worker or its wait must not implicitly cancel an admitted EGS job;
job cancellation is a separately authenticated, recorded request.

## Omnigent reuse and qualification

[Programmatic session tools](https://omnigent.ai/docs/programmatic) provide
session creation, dispatch, status/history and closure.
[Smart routing](https://omnigent.ai/docs/build/routing) can select model/harness
and call an external routing service; LS must independently validate the route
because the documented router can fall back after an error.
[Policies](https://omnigent.ai/docs/policies/builtin) and
[custom policies](https://omnigent.ai/docs/policies/custom) offer mechanisms
for tool restrictions and bounded delegation.
[Cloud sandbox hosts](https://omnigent.ai/docs/deploy/cloud-sandbox-host) provide
remote-runner infrastructure. These are reusable components, not proof of an
integrated LS account pool or remote exit witness.

Read-only inspection on October 3 found `omnigent 0.1.1` in `py-bench`, built
June 16. Current upstream documentation must not be treated as installed
capability. Pin and measure the chosen adapter/version and confirm session,
result, model/auth isolation, policy enforcement and remote custody behavior.
Reuse Omnigent-Install's worker selectors and OmniWorker-Install's host/profile
boundaries where qualified; do not introduce another authoritative lifecycle
database. T059–T062 are a separate broker tranche and do not gate T054–T057.
