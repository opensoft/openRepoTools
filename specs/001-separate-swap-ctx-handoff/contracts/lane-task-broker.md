# Lanes service task broker

Status: prospective; implementation and runtime qualification pending

The October 4 [launcher amendment](claude-lane-launchers.md) requires local
Omnigent for lane communication in both operating modes: direct `pclaude`
profile launches remain outside lanes, `oclaude` is non-lane by default and
`lclaude` supplies an admitted lane binding. This local runtime dependency does
not require codeXfactory for ordinary local lanes or change factory admission
for broker work. It supersedes October 3's optional local-Omnigent wording.

## Two explicit operating modes

Brett's October 3 direction retains ordinary lane swap and adds broker mode.
Mode selection is explicit; missing markers preserve existing validators and
meanings. Do not reinterpret existing native-child or historical runner records.

| Mode | Main agent | Delegation and account changes |
| --- | --- | --- |
| Swap | Runs the lane's current workflow with its qualified native tools/children | LS transfers the exact parent using the existing swap contract and verified source exit; the shared container stays running. |
| Broker | Performs primary orchestration: planning, task/dependency decisions and result review | Lane-facing delegation goes through LS into the existing factory rail. Omnigent's worker-management layer selects authorized account/model/harness/host placement and manages worker recovery. LS preserves task attachments and results when the main lane swaps. |

Broker workers may run on the local computer or enrolled remote hosts. A worker
under another account is a separately launched runtime with its own actual
session identity, not a native child inside A's Claude process. Broker mode
does not make Claude's native Agent tool switch credentials or containers.
Existing swap remains available for the main lane. Worker account replacement
belongs to Omnigent's worker-management layer and requires its own qualified
execution-site integration; it is not an already implemented capability.

## Existing factory worker rail is the first adapter

Brett's follow-up directs LS to consume the existing CPC/omniWorker and
codexFactory/openxFactory execution system. Start with its admitted job and
worker surfaces. Extend their owning components for missing capabilities;
keep one worker registry, dispatch rail and factory approval authority.

The inspected coding path is xFactory's execution-lane caller → codexFactory's
reusable prepare/enforce workflow → xFactory's CPC coding rider → patch and
task-result artifacts → deterministic containment, exact-base application and
reviewed checks. See the [caller](https://github.com/opensoft/xFactory/blob/main/.github/workflows/execution-lane.yml),
[domain workflow](https://github.com/codeXfactory/codexFactory/blob/84bfae38ec02705f1b1965cc03bbe8c2d298b84b/.github/workflows/execution-lane-reusable.yml)
and [worker profile](https://github.com/opensoft/OmniWorker-Install/blob/125d9636d6fed5589d628b4f32d812c0968d7979/workers/profiles/coding-patch-worker.yaml).

Omnigent-Install also implements job/run/event/artifact records, registered
worker selection and a worker inbox. OmniWorker-Install declares distinct
control, coder, tester and integrator pools with subscription auth, capability
and capacity limits; its coder profile specifies isolated per-job worktrees
and task-to-commit evidence. These declarations and local implementations are
reuse surfaces, not proof of their present deployment or end-to-end readiness.

| Owner | Authority retained by integration |
| --- | --- |
| Hermes/openxFactory and the domain factory | Factory intent, approval scope, permitted operations, workflow/job state and domain result enforcement. |
| Omnigent-Install's worker-management layer and existing dispatcher | Worker workload, placement within admitted policy, account allowance/capacity checks and qualified worker recovery; missing capabilities are extensions here. |
| OmniWorker-Install and worker execution-site custodian | Host installation, profiles, readiness, admitted transport and authenticated worker runtime/exit/effect observations. |
| LS local ledger and parent custodian | Lane requests, stable factory-task correlations, consumer-generation fences, durable result delivery and exact parent process custody/swap/release. |
| Each execution site's EGS | That site's admitted persistent commands and their output/effect ownership, addressed by site/supervisor/job identity. |

LS records references to factory job/run, worker, dispatch, result and actual
runtime identities. It does not reinterpret a factory approval, mirror factory
workflow state as a competing authority, or infer runtime death from a completed
workflow. The derived lane index retains its separate non-authoritative role.
Agents enter through LS; LS requests work through the existing factory rail.
Omnigent session APIs are runtime transport inside an admitted route. Qualify
the actual deployed endpoint and policy before selecting that transport.

The inspected interfaces leave these explicit integration gaps:

- The CPC `coding-patch-worker` runs one `claude -p --max-turns 1 --tools ''`
  invocation, returns a patch and task result, and declares no session
  persistence. Use it for qualified bounded patch tasks; interactive tools,
  worker interruption, EGS jobs and account resume require a qualified profile
  and lifecycle extension in their owners.
- The current openxFactory clearing register admits `readiness-diagnostic` and
  `deliberation`; `coding` is deliberately absent and its existing rider route
  is grandfathered. An LS integration must consume only a currently admitted
  scope or complete the owning governed admission; it cannot expand that route
  into arbitrary broker execution. The [register](https://github.com/opensoft/openxFactory/blob/de2ab7035663f6244c1408e94283571517040329/contracts/clearing/permitted-operations.registry.yaml)
  is the recorded October 3 observation, not a new permission.
- Account allowance/reset-aware placement and worker recovery require owning
  Omnigent extensions; stable task attachment across parent swaps requires LS
  integration. Execution-site custody, EGS persistence and resume/repair require
  measurement. Declared worker concurrency is not remaining account allowance.

The existing codexFactory MCP package exposes patch inspection and verification;
its presence is not an implemented worker-dispatch tool. T059–T062 integrate
the existing rail and add only demonstrated missing capabilities.

## Deployment direction: cloud gateway and local execution control

Brett's October 3 follow-up favors a local installation for the managed CPC,
and a shared cloud/Azure LS endpoint for engineers who install xFactory and
explicitly enroll spare compute for omniWorkers. The proposed distributed
shape uses both cloud coordination and local execution control. Azure resource,
subscription and deployment selection remain implementation choices; no cloud
deployment or engineer-host enrollment is authorized by this document.

| Component | Location and responsibility |
| --- | --- |
| LS gateway | Shared cloud endpoint for authenticated lane requests, factory-task correlation, result delivery and task-consumer reattachment. |
| Existing Omnigent/Hermes factory layer | Shared workload, registered worker selection, allowance/capacity reservations and qualified recovery orchestration. Reuse its existing registry, queues and approval authority. |
| LS runtime controller/custodian | On each execution site, with owned process handles in the worker's runtime namespace; validate local launch/stop/swap, witness exit and reconcile local workspace/effects. Reuse the shared swap machinery through the owning Omnigent integration. |
| Execution-site EGS | On that site, independently owning admitted commands/jobs across worker account changes. |

The same local execution control also serves parent lanes on their own machines.
Omnigent requests worker lifecycle actions through the admitted local controller
integration; it continues to own worker workload and account choice. The
controller validates the exact binding and local safety boundary before acting.
Cloud coordination does not gain PID custody by holding a session/job ID. Local
JSON under its local lock remains authoritative for swap ownership, fences,
exit witness and release; the QA derived index is not dispatch authority.

An enrolled engineer host initiates an authenticated outbound connection to
the shared endpoint, preferably reusing the qualified Omnigent host/tunnel
transport. Do not require incoming workstation ports or another worker
registry. Reuse factory-issued host/worker identities and record permitted
work scope, workspace and resource/concurrency limits. Spare CPU enrollment
does not authorize use of the engineer's model subscription; authorized model
account references are a separate admission input. Exact authentication,
transport and tenant/host isolation must be qualified under T061–T062.

On network/cloud loss, already admitted work and independently owned EGS jobs
may continue within their recorded authority, with durable local evidence for
reconciliation. New placement or recovery that requires fresh shared admission
or account reservations waits/refuses. An already authorized local swap may
finish only when all its existing local gates and authority remain satisfied;
offline recovery cannot acquire a new distributed permission. Cloud timeout
does not certify host/worker death or permit a duplicate writer. Reconnect
reconciles stable task/attempt IDs, current generations and delivery watermarks.

CPC local operation can be qualified first without making Azure availability a
T054–T057 gate; distributed enrollment is the prospective broker tranche. The
inspected [CPC host manifest](https://github.com/opensoft/OmniWorker-Install/blob/125d9636d6fed5589d628b4f32d812c0968d7979/clients/opensoft/worker-hosts/cpc-omni01.worker-host-manifest.yaml)
declares Ubuntu WSL, Docker CE and systemd. Put
Linux custody in the actual Linux execution namespace rather than assume the
Linux subreaper contract works against native Windows processes. This is a
declared substrate, not evidence of a live installed LS or remote EGS.
OmniWorker-Install owns host installation; Omnigent-Install owns its orchestration
integration. The gateway location does not transfer those repository boundaries.

## Accepted access and packaging scope

Brett's October 3 agreement selects LS lifecycle-only swap plus authenticated
factory delegation for the first delivery. The lightweight client consumes the
existing factory service. Private Omnigent delegation is deferred outside
T059–T062. This is accepted product scope with implementation/qualification
pending, not evidence of an installed dispatch capability.

For shared CPC engineering work, retain LS → codexFactory admission → existing
Hermes/Omnigent dispatch → omniWorker. Direct calls to Omnigent are transport
inside that admitted path, not an independent shared-pool entry. Authenticate
caller identity and bind tenant/project, operation/task scope, permitted pool/
account and budget/capacity policy. Installing the factory or presenting an
Omnigent session token does not grant factory worker access. Donating CPU,
authorizing a model account and consuming shared workers are separate grants.

LS lifecycle-only swap now requires the qualified local Omnigent lane adapter
plus native CLI/local custodian/ledger/EGS mechanisms under the October 4
launcher amendment. It remains independent of codeXfactory and shared cloud
services. Provide a lightweight authenticated factory client without requiring
a full local factory installation. This is client packaging around the same
admission/dispatch authority; exact package and API design remain implementation
work. Authentication and project/task/pool/model-account grants are still required.

In a future separately scoped capability, a private broker could connect LS
to an owner-operated Omnigent on a workstation or VPS, using only explicitly
enrolled owner hosts/accounts.
It would require a separate qualified capability and backend/authority identity;
the current factory-first broker marker must not silently select that path.
It supplies no CPC grant and cannot be an automatic fallback for rejected or
unknown factory work. Persist the selected backend/realm with task identity so
B reattaches to the same work. Private session IDs are not factory job/approval
records. This adapter is excluded from the first delivery; T059–T062 target
the existing factory rail. No private backend is selected by the first broker
capability marker.

The current hosted codexFactory MCP authenticates inspect/verify tools, not
worker dispatch. Omnigent's own user/session authentication does not establish
factory admission. The inspected internal Hermes general job/dispatch handlers
contain no caller authentication/tenant-pool authorization gate in those paths;
this does not establish how a deployed proxy may protect them. A public LS
factory adapter must qualify the complete authentication/admission path before
depending on it. Reuse existing identity components and factory gates; a new
task API or lighter client is not already implemented by the existing MCP.
See the [packaging rationale](../../../ideation/brainstorm/lane-task-broker-access-and-packaging.md).

## Division of responsibility

- **Main agent:** choose tasks, describe scope/acceptance/dependencies and
  capabilities needed, review results and decide semantic next steps.
- **LS:** authenticate and persist lane-facing requests, retain existing factory
  task references, collect/deliver results, and transfer their consumer binding
  from A to B under the main lane's swap fence. LS controls the main parent's
  usage/exit/recovery and does not maintain a competing worker account pool.
- **Omnigent worker-management layer:** manage admitted worker workload,
  authorized account/model/harness/host placement, allowance observations and
  capacity reservations, and qualified worker recovery behind stable task IDs.
  This extends the existing dispatcher and runtime components where needed.
- **Worker agent:** execute its bounded task and return progress, artifacts
  and evidence. New delegated task requests use the LS/factory admission path;
  admitted internal execution is managed by Omnigent within that scope.
- **Execution-group supervisor:** admit and own external commands/jobs with
  stable IDs and persistent output/effects on its own execution site.
- **Execution adapter:** launch/control the selected harness on its execution
  site and report actual runtime evidence through the owning worker layer.

Expose a service delegation interface, conceptually request/status/result/cancel,
to the main agent and workers. Names and transport remain implementation work.
Broker policy must prevent lane agents from bypassing LS/factory admission
through native or direct session spawning. Omnigent's admitted internal worker
management is not a second lane-facing dispatch path. Role instructions guide
behavior; measured tool/policy controls enforce scope. Preserve swap policy.

## Requests, placement and results

A request includes authenticated caller identity/generation, an idempotency
key, repository/feature/task-definition binding, assignment/attempt, purpose,
scope, acceptance criteria/evidence references, workspace/resource needs and
allowed execution constraints. One Speckit task per implementation worker is
the preferred default; record bounded exceptions. Several workers may
contribute to one task with explicit roles and file ownership.

Omnigent's worker-management layer selects account, model/effort/harness and
host/container from authorized qualified candidates. Prefer small bounded tasks
and admit only with fresh observations showing enough estimated remaining
allowance for the task plus a configured reserve, accounting for concurrent
assignments and applicable reset windows. An estimate cannot guarantee actual
consumption, so exhaustion remains a recovery case. Unknown/stale allowance
or no eligible candidate means queued/refused, with no unrecorded fallback.
Agents express capability needs/preferences; optional AI routing cannot
override factory scope, custody, permissions or resource ownership.

The owning worker layer persists placement/attempt and dispatch intent before
launch; LS persists the lane request and factory-task correlation. Preserve
one stable logical factory task/job ID across internal worker attempts, subject
to the owning factory contract. Acknowledgment is not completion. Correlate
actual runtimes, progress, artifacts and terminal/effect evidence to attempts.
Store results durably and deliver bounded summaries/references through LS.
Late results retain attempt identity; they cannot approve a replacement attempt
or erase unresolved effects. The outer request/status/result interface stays
stable whether or not Omnigent replaces a worker account.

## Parent swap preserves delegated tasks

LS swaps the main parent A to B while independent admitted workers continue.
It fences A's consumer/control generation, retains outstanding task references
and queues results during the gap. After verified A exit and B release/resume,
the transition packet supplies outstanding tasks, completed results, delivery
watermarks and unresolved facts. B reattaches to those existing tasks without
redispatching them. Only the task consumer binding moves from A to B; worker
accounts, sessions and execution-site jobs need not move because A swaps.
Deduplicate deliveries, reject stale A control requests and preserve task scope.

These workers are distinct from swap-mode native children, which still end
with A and are reconstructed as fresh children. Independent remote work can
continue through parent handoff when its workspace/effects are isolated or
explicitly reserved and accounted. A network outage alone does not prove a
worker dead or require duplicate dispatch. Unknown overlapping effects against
the parent's claimed workspace retain the applicable release safety gate.

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

On worker-account exhaustion, Omnigent stops new admission for that binding
and uses a qualified execution-site swap/recovery boundary. Preserve the stable
factory task ID, files, accepted work and site EGS job references; reconcile
uncertain work/effects and prove old-runtime exclusion before replacement.
Until that capability is qualified, report blocked/failed or held work through
the same outer task interface; do not assume automatic retry/resume is safe.
Remote placement does not itself add cross-machine transcript migration or
forced-stop support. The main agent may remain on its account while worker
accounts rotate, but low usage does not guarantee avoiding five-hour or weekly
limits or context growth.

The main local lane's command route remains lane → MCP bridge → LS → its EGS.
A CPC or other remote worker uses the admitted factory/service gateway to
the **worker execution site's EGS**, not the parent's local supervisor. An LS
relay may forward control, but cannot certify remote process exit with local
PIDs. References bind execution site, supervisor identity/incarnation and job
ID; a bare job ID is insufficient across sites. This route still requires
implementation and measurement in the existing worker components.
Cancelling a worker or its wait must not implicitly cancel an admitted EGS job;
job cancellation is a separately authenticated, recorded request.

## Omnigent reuse and qualification

[Programmatic session tools](https://omnigent.ai/docs/programmatic) provide
session creation, dispatch, status/history and closure.
[Smart routing](https://omnigent.ai/docs/build/routing) can select model/harness
and call an external routing service; the owning placement layer must validate
the final authorized route
because the documented router can fall back after an error.
[Policies](https://omnigent.ai/docs/policies/builtin) and
[custom policies](https://omnigent.ai/docs/policies/custom) offer mechanisms
for tool restrictions and bounded delegation.
[Cloud sandbox hosts](https://omnigent.ai/docs/deploy/cloud-sandbox-host) provide
remote-runner infrastructure. These are reusable components, not proof of an
integrated worker account pool or remote exit witness.

### Observed lifecycle support and missing worker swap

October 3 inspection found session create/send/status/history/interrupt/resume
primitives and harness subprocess lifecycle management. Installed Claude-native
cold resume can rebuild a local transcript from Omnigent session items; the
Claude SDK interrupt path closes its live session and can terminate its process
group. `sys_session_close` tombstones a conversation and refuses busy children;
it is not an exact-runtime exit witness. Neither interruption nor transcript
reconstruction has been qualified here for preserving site EGS jobs or the
swap contract's sealed native history.

The inspected Omnigent-Install selector checks pool, role, capabilities,
availability and concurrency, with no remaining-subscription-allowance check.
The launcher records process completion/failure without account replacement.
Current upstream source was observed at `f37a484a` on October 3: its
[harness process manager](https://github.com/omnigent-ai/omnigent/blob/f37a484a9238d21dac71b62dd79b87e016947c19/omnigent/runtime/harnesses/process_manager.py)
provides subprocess lifecycle primitives, and
[native failure classification](https://github.com/omnigent-ai/omnigent/blob/f37a484a9238d21dac71b62dd79b87e016947c19/omnigent/runner/launch_failure.py)
recognizes rate-limit/budget errors. No complete subscription-pool selection
and safe worker account-transfer controller was found in inspected code/docs.
This is a bounded source finding, not proof of every possible deployment.

Extend Omnigent-Install's existing worker management rather than introduce
another registry/queue or assume upstream implements our swap protocol. Sharing
the qualified custody/swap machinery between parent LS and execution-site
worker controllers is an implementation option, not a new ruled component
layout. Small tasks plus allowance admission can reduce swaps; automatic worker
account replacement remains a separate qualified capability.

Read-only inspection on October 3 found `omnigent 0.1.1` in `py-bench`, built
June 16. Current upstream documentation must not be treated as installed
capability. Pin and measure the chosen adapter/version and confirm session,
result, model/auth isolation, policy enforcement and remote custody behavior.
Reuse Omnigent-Install's worker selectors and OmniWorker-Install's host/profile
boundaries where qualified; do not introduce another authoritative lifecycle
database. T059–T062 are a separate broker tranche and do not gate T054–T057.
