## Purpose

Specify the opt-in, externally supervised Claude account swap governed by
[`separate-swap-ctx-handoff`](../../proposal.md). The selected CLI capability
resumes the coordinator's native conversation and preserves native-subagent
task/history evidence to start new children for unfinished work, while
refusing any participant or effect that cannot be proven safe. Persistent
execution-group jobs retain their identities. A swap is an account transition,
not a semantic handoff.

## ADDED Requirements

### Requirement: Profile, local Omnigent and lane entry points are explicit

`pclaude` MUST directly launch the selected native Claude profile outside a lane.
`oclaude` MUST use local Omnigent and the same profile launch primitive, outside
a lane by default, and MAY accept an explicit admitted lane binding. `lclaude`
MUST admit the lane through existing protocol/LS and enter `oclaude` with that
binding. Lane launch MUST require local Omnigent. Plain `pclaude`/`oclaude` MUST
NOT infer lane attachment from cwd, tmux or inherited variables. Direct-profile
lane compatibility forms MUST refuse with migration guidance.

The local native adapter MUST preserve per-runtime profile/auth, tool policy,
hooks and sealed native transcript/resume. The actual CLI MUST launch through
the per-session custodian with the existing wait/ECHILD witness. Shared
Omnigent server/runner/container processes MUST survive swaps. Source sealing
MUST fence keyboard, API/web and queued runner prompts, and fresh input before
sealing MUST invalidate the idle observation. Session/terminal status MUST NOT
substitute for native exit, child addressability or completion evidence.
Unqualified automatic restart/resume MUST NOT bypass LS claims/release.
Local lanes MUST require no codeXfactory/cloud service; broker work MUST retain
codeXfactory admission. Pin/measure the new adapter before lane activation.

#### Scenario: Direct profile launch inside a lane worktree

- **GIVEN** cwd, tmux or inherited variables identify an existing lane
- **WHEN** the operator runs plain `pclaude <profile>`
- **THEN** the selected native Claude starts outside Omnigent and outside a lane
- **AND** no lane is looked up, claimed or attached implicitly.

#### Scenario: Omnigent session without a lane

- **WHEN** the operator runs plain `oclaude <profile>`
- **THEN** the qualified local Omnigent adapter uses the same profile launch
  primitive without acquiring a lane claim
- **AND** session observations do not imply factory worker permission.

#### Scenario: Lane launch through local Omnigent

- **GIVEN** LS admits an explicit lane/profile/runtime binding
- **WHEN** the operator uses `lclaude <profile>`
- **THEN** it launches through `oclaude` and the qualified local Omnigent adapter
- **AND** the actual native CLI has custodian-owned identity and exit evidence.

#### Scenario: Local Omnigent cannot support the lane launch

- **GIVEN** local Omnigent or the required native adapter is unavailable/unqualified
- **WHEN** a lane launch is requested
- **THEN** it refuses before native spawn without falling back to a direct lane.

#### Scenario: A message arrives after source sealing

- **GIVEN** A has a sealed idle boundary and input fence for its generation
- **WHEN** keyboard, API/web or queued runner input targets A
- **THEN** no new prompt reaches A and no stale generation controls B
- **AND** permitted pending work is delivered only after B release/readiness.

### Requirement: Swap and broker are explicit operating modes

LS MUST retain the qualified existing swap mode and introduce broker mode only
as an explicit capability. Broker main agents MUST perform primary orchestration
and lane-facing delegated task requests, including new worker-requested tasks,
MUST pass through LS and existing factory admission. Omnigent's owning worker
layer MUST manage admitted workload, authorized account/model/harness/host
placement and persist placement/attempt intent before launch. Allowance
admission MUST use fresh observations, estimated task cost plus reserve and
concurrent reservations; stale/unknown or insufficient allowance MUST queue
or refuse. An estimate MUST NOT imply guaranteed completion before exhaustion.
Workers MUST have actual independent runtime identities, with correlated
durable results. Native/direct spawning MUST NOT bypass broker admission.

Qualified worker-account transfer MAY occur internally in Omnigent while the
main agent continues, retaining a stable logical factory task/job identity and
separate runtime-attempt evidence. Existing resume support MUST NOT establish
account-transfer qualification. Remote ownership/exit/effect evidence MUST come from the execution
site; disconnection MUST remain unknown and MUST NOT authorize duplicate work.
Persistent jobs MUST use their execution site's EGS, with site, supervisor
identity/incarnation and job ID recorded; a remote worker MUST NOT implicitly
use A's local EGS. Jobs and verified work MUST be preserved. Missing mode markers
MUST retain existing meanings, and broker work MUST NOT gate or silently
replace T054–T057's graceful swap delivery.

Broker integration MUST consume existing CPC omniWorker and
codexFactory/openxFactory job/worker surfaces. Factory scope, admission,
permitted operations and result enforcement MUST retain their authority,
while LS retains lane generations, task-consumer bindings, durable result
delivery and exact parent runtime custody. A direct runtime
API MUST NOT bypass factory admission or broaden a grandfathered route.
One-shot patch workers MUST NOT be represented as resumable sessions without
a qualified extension in the owning components.

Local lane swap MUST require the qualified local Omnigent adapter and remain
independent of codeXfactory/shared cloud services. The first broker delivery
MUST expose authenticated factory delegation
to a lightweight client through the same admission service, without requiring
a full local factory installation. Admission MUST bind caller identity,
tenant/project, task/operation scope, permitted pool/model account and budget/
capacity policy. Installation, compute contribution and Omnigent session access
MUST NOT confer factory worker grants. Task bindings MUST retain factory backend/
authority realm and stable job identity across parent recovery. Private
owner-operated Omnigent delegation MUST remain outside the first capability;
refused or unknown factory work MUST NOT fall back to it.

During main-parent swap, independent admitted workers MUST be preserved. LS
MUST fence A's task-control/consumer generation, buffer and deduplicate results,
and deliver existing task references and delivery watermarks to released B.
B MUST reattach without redispatch solely because A exited. Unknown overlapping
effects against the lane workspace MUST retain the applicable release gate;
isolated/accounted remote work MAY continue through parent handoff. Ordinary
swap-mode native children MUST retain their existing lifecycle rules.

Distributed engineer-host execution MUST use explicit enrollment and an
authenticated outbound connection to the shared LS/factory endpoint. The
integration MUST reuse existing host/worker registration and admission, with
task/workspace/resource scope bound to the enrolled owner/tenant. Compute
sharing MUST NOT imply authorization to use an engineer's model subscription.
Local execution-site controllers MUST retain exact runtime custody/swap and
EGS authority; cloud coordination MUST NOT replace local JSON fence/exit/release
authority. New placement/recovery requiring shared admission or reservations
MUST wait/refuse during loss of that authority. Already admitted work MAY
continue within recorded local authority; reconnect MUST reconcile identities,
generations and delivery watermarks without duplicate dispatch. Local CPC
operation MAY precede Azure deployment; distributed enrollment MUST NOT gate
T054–T057.

#### Scenario: An authorized engineer uses a lightweight factory client

- **GIVEN** an authenticated caller has admitted project/task/pool/model-account
  scope and uses the qualified client interface without a full factory install
- **WHEN** the caller requests delegated work through LS
- **THEN** the same factory admission and result-enforcement gates apply before
  existing Hermes/Omnigent dispatch
- **AND** LS preserves the factory backend/authority and task reference for B.

#### Scenario: A factory installation has no worker grant

- **GIVEN** an engineer has installed the factory but lacks the required
  project/task/pool/model-account grant
- **WHEN** the engineer requests shared CPC work
- **THEN** admission refuses before worker dispatch
- **AND** neither direct Omnigent access nor a private backend bypasses refusal.

#### Scenario: An engineer enrolls spare compute

- **GIVEN** an engineer explicitly enrolls a qualified xFactory host with
  bounded task/workspace/resource scope
- **WHEN** the host initiates authenticated outbound contact with the cloud gateway
- **THEN** the integration uses its existing factory-issued host/worker identity
  and Omnigent places only admitted work through the local controller
- **AND** CPU enrollment does not authorize the engineer's model subscription.

#### Scenario: An enrolled host loses cloud contact

- **GIVEN** a host has admitted work and independently owned site EGS jobs
- **WHEN** cloud contact is lost
- **THEN** local execution may continue within recorded authority and new
  placement requiring shared admission waits/refuses
- **AND** the cloud neither certifies worker exit nor launches a duplicate
  from the timeout, and reconnect reconciles task/attempt/delivery identities.

#### Scenario: Ordinary swap retains native behavior

- **GIVEN** a lane enrolled in the qualified existing swap capability
- **WHEN** a broker capability is introduced elsewhere
- **THEN** the lane retains its native-child tool policy and exact-parent swap
- **AND** no record is silently converted to a broker worker session.

#### Scenario: Remote worker account changes while the main agent continues

- **GIVEN** a broker main agent and an LS-admitted task on a remote worker
- **WHEN** that worker's account exhausts and its qualified source/effect
  boundary permits replacement
- **THEN** Omnigent records internal replacement-attempt evidence under the
  same logical factory task ID and LS returns correlated results to the main agent
- **AND** existing EGS job identities and accepted task work are preserved.

#### Scenario: Remote contact is lost

- **GIVEN** an admitted remote worker with uncertain runtime or effects
- **WHEN** its heartbeat or control transport stops responding
- **THEN** the owning worker layer retains unknown ownership pending reconciliation
- **AND** LS exposes that unresolved state through the existing task reference
- **AND** it does not start a duplicate writer from elapsed time alone.

#### Scenario: A worker requests more help

- **GIVEN** a worker in broker mode that needs another task contribution
- **WHEN** it delegates that contribution
- **THEN** the new task request goes through LS/factory admission and Omnigent placement
- **AND** native or direct session-spawn routes cannot bypass that admission.

#### Scenario: A factory coding operation is not admitted

- **GIVEN** an existing CPC rider and a factory register that has not admitted
  the requested coding operation
- **WHEN** LS receives a broker request outside the existing admitted scope
- **THEN** it queues or refuses that request pending the owning admission
- **AND** it does not dispatch through a new direct runtime route or widen
  the grandfathered worker's scope.

#### Scenario: Main parent swaps while remote work continues

- **GIVEN** A owns a lane with admitted independent workers in isolated or
  reserved workspaces and accounted effects
- **WHEN** LS verifies A's exit and releases B under the parent swap contract
- **THEN** those workers and their site EGS jobs continue under their existing IDs
- **AND** B receives the outstanding factory task references and reattaches
  without starting replacement workers solely because A swapped.

#### Scenario: A result arrives between parent generations

- **GIVEN** LS has fenced A and B has not yet been released
- **WHEN** an admitted worker returns its correlated result
- **THEN** LS retains the result durably for B with its delivery watermark
- **AND** stale A control requests refuse and B consumes the result without redispatch.

#### Scenario: Worker allowance is insufficient

- **GIVEN** a task estimate plus reserve exceeds fresh account allowance after
  concurrent reservations, or the allowance is stale/unknown
- **WHEN** Omnigent evaluates that worker placement
- **THEN** it queues or refuses rather than dispatch into that binding
- **AND** LS retains the same outer request identity and reports its status.

#### Scenario: Estimated allowance is exceeded during a task

- **GIVEN** an admitted task exhausts its worker account despite the estimate
- **WHEN** no qualified replacement boundary is available
- **THEN** Omnigent reports blocked/failed or held work through the stable task
  interface and preserves artifacts, ownership facts and site job references
- **AND** LS does not infer safe replay from a rate-limit error or a resume API.

#### Scenario: Different supervisors issue the same job ID

- **GIVEN** local and remote supervisors have jobs with the same bare ID
- **WHEN** a worker's job is observed or controlled
- **THEN** the reference selects its exact execution site and supervisor incarnation
- **AND** local-parent control cannot act on or certify the remote job by bare ID.

#### Scenario: A bounded patch worker returns a result

- **GIVEN** a qualified existing factory task using the one-shot patch profile
- **WHEN** it returns a patch and task-result artifacts
- **THEN** LS correlates those existing job/run/result identities and preserves
  domain containment and reviewed-check enforcement
- **AND** it does not infer a resumable worker session from task completion.

### Requirement: Speckit task attribution supports focused recovery

For Speckit-driven implementation, the orchestrator SHOULD assign one Speckit
task per native implementation child run. Multiple children MAY contribute to
one task with explicit roles and file boundaries. A bounded multi-task
exception or support assignment MUST record covered task IDs and a reason.
This preferred default MUST NOT be a lane-swap admission prerequisite.

The lanes service MUST persist qualified repository/feature/task-definition,
assignment/attempt, observed native identity, file/worktree, job and evidence
references continuously. Speckit task IDs MUST remain distinct from runtime
task IDs. Startup review MUST include unverified contributions and outstanding
jobs, including recently returned children, plus parent edits and unmatched
work. A child ending MUST NOT imply whole-task acceptance. The resumed parent
or reviewer MUST verify acceptance and preserve verified completion, files and
admitted jobs. Task grouping MUST NOT substitute for source-exclusion, ownership
or effect proof, or establish forced-recovery support.

#### Scenario: Several children contribute to one task

- **GIVEN** implementation and review children are assigned to the same Speckit
  task with distinct roles and file boundaries
- **WHEN** one child returns and another contribution remains unverified
- **THEN** the service retains the separate assignments within one review group
- **AND** that task is not accepted solely because one child returned.

#### Scenario: Recently returned child still needs review

- **GIVEN** a child returned just before exhaustion and its task has unverified
  changes or an outstanding EGS job
- **WHEN** a transfer has independently satisfied source and effect safety
- **THEN** the transition packet includes that task for startup review
- **AND** B inspects existing work and observes the original job without replay.

#### Scenario: Task attribution does not cover all changes

- **GIVEN** four task groups, a declared multi-task exception and unmatched
  parent edits are recorded
- **WHEN** the service assembles the recovery inventory
- **THEN** it includes the exception tasks and unmatched items explicitly
- **AND** it does not claim the review is bounded to only the four groups.

#### Scenario: Recorded exception preserves swap eligibility

- **GIVEN** a bounded multi-task assignment with recorded scope and reason,
  and otherwise proven source, history, ownership and effect safety
- **WHEN** the service checks the selected CLI swap capability
- **THEN** the task-assignment preference alone does not refuse the swap
- **AND** verified completed work remains complete through startup repair.

### Requirement: Worktree diagnostics use the managed service authority

For `claude-cli-supervised-jobs-v1`, the lanes service SHALL incorporate bounded,
versioned worktree observations into its ledger reconciliation and B's packet.
Observations SHALL bind exact lane, operation, generation, canonical physical
repository/worktree identity, provenance and watermark, and SHALL refresh after
source exit and before release. Continuing-job observations SHALL be provisional.
The managed ledger SHALL remain the sole lifecycle/readiness authority. PR #97
sidecars MAY supply explicitly bound historical diagnostics, but their lifecycle,
counters and `resumable` verdict SHALL NOT authorize managed release.

Failed, missing, unreadable, malformed, unsupported, stale, incomplete and
contradictory evidence SHALL remain distinguishable; failed reads or missing
upstream SHALL NOT imply clean or published work. Identity SHALL resist path
encoding/repository-basename collisions and unify physical aliases. Required
identity, writer or effect uncertainty SHALL retain claims and block B.
Inventory persistence failure SHALL block successful readiness. Independently
safe diagnostic gaps MAY enter startup repair, without waiving exclusion/effect
checks. Collection and repair SHALL preserve user files, tasks and jobs and
SHALL NOT automatically modify or recreate worktrees or require A inference.

#### Scenario: Historical recovery verdict contradicts source evidence

- **GIVEN** a legacy snapshot says `SWAPPED` or its report says `resumable`,
  while exact source exclusion or a required worktree identity is unknown
- **WHEN** the service reconciles the managed operation
- **THEN** it SHALL retain claims and keep B absent
- **AND** it SHALL preserve the historical evidence without importing its state.

#### Scenario: Safe transfer has a diagnostic gap

- **GIVEN** source exclusion, ownership and effects are independently verified,
  but publication status is unknown for a branch without an upstream
- **WHEN** the service seals the transition packet
- **THEN** it SHALL report publication as unknown and identify startup repair
- **AND** it SHALL preserve dirty/untracked files and continuing jobs without
  requiring a final A response or automatically repairing the worktree.

#### Scenario: Collection is incomplete or cannot be persisted

- **GIVEN** a required Git read fails, collection omits a required worktree,
  or the managed inventory cannot be persisted
- **WHEN** the service attempts preparation
- **THEN** it SHALL NOT manufacture clean defaults or successful readiness
- **AND** it SHALL retain claims and reconcile under the same operation.

### Requirement: CLI swap safety requires no source model headroom

For `claude-cli-supervised-jobs-v1`, the service SHALL preserve swap safety and
construct the transition packet from durable runtime, task, history, job and
filesystem records with zero source model tokens and no final source handoff.
Native wrap-up allowance SHALL NOT be a dependency or readiness condition.
The service SHALL consume fresh profile-keyed usage observations independently
of user prompts and SHALL persist task/lifecycle references as work proceeds.
It MAY request one bounded cooperative wrap-up before known exhaustion and
before control entry; it SHALL NOT request an additional source model turn at
known exhaustion or retry after exhaustion during wrap-up.

The initial delivery SHALL still require a measured idle boundary, exact
source exit and accounted descendant/effect evidence. Missing evidence or a
bounded timeout SHALL retain claims and keep B absent. A child response that
ends with a usage failure SHALL NOT be recorded as task success.

#### Scenario: No allowance and no final source handoff

- **GIVEN** A is exhausted, receives no native allowance and writes no final
  handoff, but its child/task/history/job records are durable
- **WHEN** the service observes the verified idle boundary and exact source
  exit, and reconciles all activity and effects
- **THEN** preparation SHALL produce a service-authored transition packet and
  ready state with B absent, without requesting another source model turn
- **AND** safely unfinished child tasks SHALL be available for reconstruction
  with new IDs only after explicit target release.

#### Scenario: Allowance ends before a safe boundary is established

- **GIVEN** optional wrap-up ends with usage failure and the service cannot
  establish a supported idle boundary or account for a child effect
- **WHEN** the bounded preparation deadline expires
- **THEN** the service SHALL retain claims and keep B absent
- **AND** it SHALL NOT retry source inference, infer task success or force
  recovery under this capability.

### Requirement: Resumed parent receives the verified handoff outcome

For the CLI capability, the service SHALL persist an operation/parent/generation-
bound handoff outcome in the local JSON ledger and deliver it before B's first
turn. `clean` SHALL require a verified cooperative checkpoint completed before
exhaustion and reconciled child tasks, job references and source history/exit.
Exhaustion before checkpoint completion, missing checkpoint or unreconciled
child failure SHALL produce `repair-required`, with reasons and a bounded repair list.
An AI completion statement alone SHALL NOT establish `clean`.

Both outcomes SHALL require the same source exclusion and accounted effects
before startup. Repair SHALL NOT authorize takeover with unknown source effects.
A missing outcome in an otherwise valid packet SHALL require repair; an invalid
operation/generation binding SHALL refuse. B SHALL perform required startup
repair before normal work; the service SHALL record its completion separately
without rewriting the sealed outcome or replaying uncertain external effects.

#### Scenario: Verified clean transfer avoids unnecessary repair

- **GIVEN** A completed its cooperative checkpoint before exhaustion and the
  service verified all transfer evidence, including plans for unfinished tasks
- **WHEN** B starts after source exclusion and explicit release
- **THEN** its first packet SHALL identify `clean` and the continuation plan
- **AND** dirty files, continuing jobs and accounted unfinished tasks SHALL NOT
  be mistaken for failed handoff merely because they still exist.

#### Scenario: Exhausted transfer requires startup repair

- **GIVEN** A exhausted before its checkpoint completed, but source exit and
  all process/effect safety requirements have been verified
- **WHEN** B starts after explicit release
- **THEN** its first packet SHALL identify `repair-required` with the reasons,
  recovered state and pending repair items
- **AND** B SHALL reconcile assignments and progress before normal work,
  preserve user files and observe continuing jobs without duplicate dispatch.

### Requirement: Named-lane CLI deployment preserves wider acceptance gates

A staged deployment of `claude-cli-supervised-jobs-v1` SHALL be versioned and
explicitly selected for the named canary lane. It SHALL require passing frozen
shared-route and invoked-dependency regressions, applicable actual CLI/fault
evidence, isolated installation/rollback and an installed authenticated canary.
It SHALL preserve the full canonical regression census and open native `ctx`
and restoration acceptance assertions. Only individually mapped failures in
the unreachable, explicitly refused native-`ctx` route MAY remain outside this
staged gate. An unexplained or shared-path failure SHALL block deployment.
The stage SHALL NOT enable defaults/global activation or claim T057, general
rollout, repository release or complete-feature acceptance.

#### Scenario: Native context acceptance remains incomplete

- **GIVEN** the native-`ctx` route refuses before effects and its positive
  acceptance tests remain failing open requirements
- **WHEN** the separately selected shared-session swap passes every applicable
  named-lane gate
- **THEN** only that versioned named-lane capability MAY be activated
- **AND** the full-suite failures and wider acceptance gates SHALL remain
  explicitly open with their original assertions retained.

### Requirement: A supervised CLI job capability has a distinct durable authority

The system SHALL select `claude-cli-supervised-jobs-v1` only by an explicit
capability discriminator inside `stop-then-resume-v1`. An absent or different
capability SHALL keep its existing contract and record interpretation. The
direct CLI executable/version/configuration tuple SHALL be pinned independently
of SDK-selected CLI evidence. The durable lane supervisor SHALL own one
compare-and-set operation/generation claim, the source runtime and restart-deny
fence, registered worktrees, and separately admitted persistent jobs. It SHALL
not acquire an arbitrary detached process after the fact. A job admitted
before spawn SHALL retain its ID, output/result references, effect watermark
and resource reservations across the account change. Unknown or incomplete
jobs SHALL block conflicting writes and replay.

For this CLI capability, the managed lane's external commands and edits SHALL
enter the persistent lanes service, which validates owner generation,
operation fence, request identity and worktree reservations before forwarding
to the execution-group supervisor. The lane SHALL NOT address the execution-
group job socket directly. Only the coordinator conversation SHALL resume by
its exact Claude session ID. Native subagents from A SHALL NOT be represented
as resumed on B; each safely unfinished task SHALL receive a new native child
with a new ID after B receives the service's transition packet. Old child IDs
remain evidence for task linkage. Separately admitted supervisor OS jobs
SHALL keep running with their original IDs, outputs and reservations.

Source exclusion SHALL prove the old CLI/runtime domain empty and every old
creation/recovery route fenced while allowing only accounted supervisor jobs
to continue. A hook, seat revocation, parent PID exit, transcript snapshot or
one process-group sample SHALL NOT serve as that witness. Wrong parent, stale
generation, changed profile/manifest, unknown descendant and competing target
claim SHALL refuse before B starts. The preparation controller SHALL initiate
zero new model requests and create no target. Any old source request already
in flight remains source-domain activity until excluded and reconciled. An
exact-operation explicit release SHALL
durably authorize one target launch before direct CLI exact-parent resume;
uncertain launch or job effects SHALL be observed, not retried automatically.

The selected initial path SHALL preserve the shared container and unrelated
Claude sessions. It SHALL NOT stop, kill, restart or replace the container,
kill all processes for a user or signal a shared process group. The supervisor
MAY remain inside the container with independent job and control lifetimes.
Host Docker/cgroup authority SHALL NOT be a prerequisite for this path.
Forced per-session recovery SHALL remain separately gated and unavailable
without its own evidence.

The launcher SHALL claim the exact source parent/lane/generation before spawn,
retain namespace/start identity or its owned child handle with a durable
journal, and reject duplicate parent admission. Every runtime SHALL have
immutable per-session configuration and profile/auth bindings with a scoped
job credential distinct from supervisor authority; shared-path overwrite or
broad credential/environment mutation SHALL NOT affect unrelated sessions.

#### Scenario: A supervised job and unrelated session survive graceful exit

- **GIVEN** A and independent Claude session C share a running container
- **WHEN** A completes foreground wrap-up and its exact admitted CLI exits
- **THEN** the container and C SHALL remain running and the same supervisor job
  SHALL retain its identity, output and reservations without another spawn
- **AND** B SHALL start once on A's exact parent only after verified exit,
  complete supported session-activity accounting, reconciliation and release.

#### Scenario: B reconstructs children while a persistent job continues

- **GIVEN** A's unfinished native child and an independently admitted OS job
- **WHEN** B resumes the exact parent conversation on the target account
- **THEN** the job keeps its existing ID and execution-group process
- **AND** B starts a new native child with a new ID from the service's
  task, history, filesystem and job-result packet
- **AND** all new external job requests travel through the lanes service.

#### Scenario: Wrap-up returns to a prompt without exiting the CLI

- **WHEN** A produces a final response, quota notice or prompt after wrap-up
- **THEN** the supervisor SHALL NOT treat it as runtime exit or authorize B
- **AND** it SHALL require observed exact CLI exit and measured foreground
  child/helper lifecycle coverage, history and effect reconciliation.

#### Scenario: Graceful exit or descendant coverage is uncertain

- **WHEN** exit is refused, a child escapes or is unaccounted for, or the
  launcher loses its runtime identity or durable journal
- **THEN** the operation SHALL block readiness and B while preserving jobs,
  claims, unrelated sessions and the container
- **AND** it SHALL NOT infer exclusion from parent death or force a broad stop.

#### Scenario: Old source or second target races B

- **WHEN** A attempts a tool or restart after its durable fence, or two B
  contenders claim the same parent/generation
- **THEN** old-source dispatch and every second claim SHALL refuse without a
  job, target runtime, or transcript writer being created.

#### Scenario: Crash crosses release or job effect

- **WHEN** the supervisor reloads an uncertain job result, exclusion witness,
  release intent or target launch intent
- **THEN** it SHALL reconcile the existing ID and effect before proceeding
- **AND** it SHALL NOT replay a job, release, target startup or child message.

### Requirement: Explicit stop-then-resume v1 defers target creation until release

Under the approved [v1 decision](../../stop-then-resume-decision.md), the system
SHALL distinguish explicitly selected `stop-then-resume-v1` from existing
strict native swap. The target-held, pre-release exact-loading, durable orphan
clear, and six-stage target-proof requirements elsewhere in this specification
SHALL apply to strict mode, not v1. Both modes SHALL preserve source exclusion,
history, files, ownership, permissions, and uncertain-effect safety. Old or
unmarked records SHALL NOT be reinterpreted as v1. Graceful child/tool
drain-before-parent-shutdown ordering elsewhere below SHALL remain strict-only;
the original SDK/PGID v1 MAY mechanically contain unfinished work before complete drain, but SHALL
prove full source exclusion and reconcile effects before readiness. Termination
SHALL NOT mean successful task completion.

#### Scenario: Source quota is exhausted

- **WHEN** an operator selects the original SDK/PGID v1 with a supported source containment boundary
- **THEN** mechanical stop SHALL require no source model prompt, generated
  handoff, or natural completion of the unfinished task
- **AND** unknown writers or effects SHALL prevent readiness and target launch.

#### Scenario: Source is safely stopped and target is selected

- **WHEN** source exclusion, history and effect checks pass before release
- **THEN** the operation SHALL report `ready-to-resume`, retain claims, and
  create no target runtime
- **AND** it SHALL NOT claim the target session has loaded or workers resumed.

#### Scenario: Explicit release precedes exact loading

- **WHEN** a matching release passes fresh ownership, source and history checks
- **THEN** its bound authorization and launch intent SHALL be durable before
  target creation and exact parent resume
- **AND** target inference MAY occur after that authorization, while uncertain
  startup SHALL retain claims and SHALL NOT trigger a replacement startup or
  fresh conversation fallback.

#### Scenario: Only process disappearance is known

- **WHEN** tracked PIDs disappear but writer/effect ownership is incomplete
- **THEN** v1 SHALL remain unsupported or indeterminate and SHALL NOT launch a
  target, label unknown runtime state cleared, or replay uncertain work.

### Requirement: Managed enrollment and session-lineage ownership are explicit

The system SHALL require explicit managed enrollment. The external supervisor
SHALL durably own the coordinator session-lineage, operation lock, discovered
native child roster, lifecycle/tool ledger, and any optional isolated-worktree
claims. A native child SHALL remain a child of that coordinator's execution
lineage; it SHALL NOT become an independently launched top-level worker or an
independently logged-in SDK session.

At any running point, native children SHALL share the coordinator's Claude
process, account, and session name. The roster SHALL identify them with the
actual runtime's native agent/task IDs, explicit parent linkage, immutable
custom-agent definition, effective permissions, containing process-tree
evidence, and hook/tool lifecycle facts. The supervisor SHALL NOT invent a
per-child top-level UUID, process-group ID, open operation, shutdown operation,
release operation, or account session. A coordinator can be read-only and need
no worktree claim, but it MAY delegate to an explicitly authorized writable
native child. Any writer in that lineage requires the lineage claim.

Enrollment SHALL use the same atomic ownership boundary as legacy launch: a
live or unknown legacy holder causes refusal with zero changes. Durable managed
ownership SHALL remain authoritative if the supervisor process dies; legacy
launch SHALL NOT silently replace it. Bounded shutdown SHALL retain durable
ownership and live lineage/worktree claims. Unenrollment SHALL clear them only
after authoritative participant and tool quiescence. Managed state SHALL
project human-facing status only through supported `lanes-edit.sh` operations
and refuse helpers outside the tested capability contract rather than editing
register files directly.

#### Scenario: Legacy holder is live or unknown

- **WHEN** an operator enrolls a lane whose legacy holder is live or cannot be
  determined
- **THEN** enrollment refuses before killing, overwriting, or launching any
  participant
- **AND** the lane and filesystem remain unchanged

#### Scenario: Managed supervisor is unavailable

- **WHEN** a legacy `lane`, `lane-start`, or `lane-handoff`/handoff operation
  targets a lane with durable managed ownership
- **THEN** it refuses by canonical lane name
- **AND** it does not fall back to a legacy owner

#### Scenario: Independent-worker state is encountered

- **WHEN** an operation finds a durable record from the old independently
  supervised child-runner prototype
- **THEN** it refuses or performs an explicitly versioned migration before
  control begins
- **AND** it never silently reinterprets, deletes, or resumes that record as a
  native lineage

### Requirement: Preflight resolves a compatible target without mutation

The system SHALL require an explicitly selected target profile in the same
transcript-storage family. The workBenches resolver SHALL read manifest and
metadata only; it SHALL NOT mutate launch/configuration files, copy
credentials, or perform a live model/auth/quota probe. Inherited provider-auth
environment overrides SHALL be removed, while the prescribed model, effort,
tools, permissions, workspace, custom-agent definitions, and other launch
settings SHALL be retained.

Setup-token authentication, missing expected account identity, incompatible
storage, a child with unknown identity or effective permissions, or a native
participant kind without a verified discovery/stop/control boundary SHALL
refuse before planned shutdown. Lack of an exact child continuation alone can
be represented as `restart-pending` when the control boundary is proven. A
read-only coordinator SHALL NOT cause a child to inherit broader tools or write
permissions: the child definition and effective permissions must be explicitly
authorized and validated.

The resolver SHALL publish the runtime version, launch mode, and native
participant kinds covered by compatibility evidence. A native team or a native
background form is not automatically supported merely because its name or a
background flag is present; it needs the corresponding runtime lifecycle and
stop evidence. This gate SHALL not turn a native child into an independent
worker as a workaround.

#### Scenario: Target profile is unsupported

- **WHEN** the selected profile uses setup-token authentication, lacks the
  expected account email, is outside the transcript family, or has a native
  participant kind with no verified discovery/stop/control evidence
- **THEN** preflight refuses and leaves the original runtime running
- **AND** no credential, launcher, or participant state is changed

#### Scenario: Inherited authentication conflicts with explicit profile

- **WHEN** the launch environment contains an inherited provider-auth override
- **THEN** the target launch removes that override
- **AND** retains the profile's explicit permission and launch settings

#### Scenario: Child authorization is missing or broadened

- **WHEN** a writable child has no immutable agent definition, actual effective
  permission set, or explicit authorization, or would broaden the
  coordinator's declared tools/permissions
- **THEN** preflight refuses before shutdown
- **AND** it does not infer authorization from a read-only parent or launch a
  replacement child

### Requirement: Native identities and continuation are lineage-scoped

The Claude adapter SHALL validate the coordinator's existing native transcript
identity and use the official exact `--resume <UUID>` path with promptless
`connect(prompt=None)` under the selected profile. It SHALL reject a missing
coordinator ID, a fork, title/picker selection, or any fallback that invents an
identity. An empty coordinator session SHALL receive a reserved fixed UUID
before user work.

Native children SHALL be discovered from actual runtime records and events:
their native agent/task IDs, coordinator parent ID, immutable definition,
effective permissions, containing process tree, and hook/tool facts are the
identity evidence. A child has no independent top-level transcript UUID,
process-group ID, account session, SDK open, SDK shutdown, or SDK release
operation for the supervisor to fabricate. Exact same-agent continuation SHALL
be preferred only where the pinned runtime and adapter have verified it. A
pre-release exact-continuation candidate is `resume-pending`; a child that
requires a new native run is `restart-pending`, not a reason to invent a child
identity. `exact-resumed` is reserved for a correlated continuation outcome
after the explicit release boundary.

An `agent_id` reused from an earlier task, a stale notification, or a generic
`SubagentStop` is not proof that the current run stopped. Continuation and
stop evidence SHALL correlate the current task instance, coordinator
invocation, parent linkage, and an event watermark (or an equivalent
runtime-provided generation), together with the containing process tree and
hook/tool facts.

Readiness MAY NOT require Claude initialization to echo a `session_id` or
selected model; coordinator identity is proven by the validated transcript,
exact resume argument, and successful loader initialization. Child identity is
proven by native task/agent evidence correlated to its coordinator, not by a
synthetic UUID.

#### Scenario: Initialization omits optional echoed fields

- **WHEN** the coordinator transcript identity was validated and initialization
  reports no `session_id` or selected model
- **THEN** exact coordinator resume remains eligible only when loader
  initialization succeeds and all other recorded checks pass
- **AND** the adapter does not invent an ID or model

#### Scenario: Native child identity is missing or contradictory

- **WHEN** a required child has no native agent/task ID, no verifiable parent
  linkage, or contradictory process-tree or hook/tool evidence
- **THEN** the child is recorded as `unresolved` and replacement execution is
  blocked
- **AND** no per-child SDK session or fallback identity is created

#### Scenario: Verified same-agent continuation is available

- **WHEN** the installed runtime exposes a documented, tested continuation for
  a native child and correlates the resumed task/agent event to the original
  parent and native ID
- **THEN** the child may be recorded as `resume-pending` until release and a
  correlated continuation event
- **AND** its coordinator lineage, account, process, and session name remain
  the ownership boundary

#### Scenario: Reused native ID or stale stop event

- **WHEN** a native `agent_id` is reused or a stop notification predates the
  current coordinator invocation/watermark
- **THEN** the event is not accepted as current child quiescence or exact
  continuation
- **AND** the child remains `unresolved`, `resume-pending`, or
  `restart-pending` until current-run evidence is correlated

### Requirement: The control phase proves explicit parent and child boundaries

Before interrupting the source coordinator or initializing the target
coordinator, the control phase SHALL atomically fence parent/child admission
and prove that no parent or child can infer or dispatch work outside the sealed
native roster. It SHALL test the pinned runtime's startup behavior, including
whether promptless parent initialization automatically resumes orphaned native
children. Parent initialization alone, a parent exit, an `Agent` tool return,
or a background flag is not proof of a held graph.

Interactive takeover that can auto-resume an orphan before the first prompt is
not a supported non-auto mode. A `print.ts`-style path whose callback cannot
prove a pre-dispatch hold is likewise unverified. SDK `stream-json` is
unverified until the exact SDK-selected CLI binary, runtime version, and
binary digest are pinned and a no-auth orphan fixture proves that startup does
not dispatch a child. A supported non-auto mode must prove current-run child
and tool quiescence/exclusion; an invented durable marker is not a substitute
for runtime evidence. For the observed SDK `0.2.153` bundled-first selection,
that evidence must identify bundled CLI `2.1.273` and its full SHA-256 (the
observed digest prefix is `6c752e2c`); a prior CLI `2.1.270` trace does not
prove support for that SDK pairing. The selected launch mode, executable path,
arguments, SDK version, CLI version, and digest are one compatibility tuple.
In particular, the CLI `2.1.273` print path can wake orphaned native tasks
through `restoredOrphans`' default-enabled wake and
`enqueuePendingNotification`; print or stream-json mode alone is not a
zero-inference guarantee. Before source-parent exit, every tracked child SHALL
be terminal-stopped and its durable current-state record SHALL be cleared.
Target startup must then prove no-wake/no-model behavior with that cleared
state; otherwise the configuration is refused.

The control phase SHALL refuse before planned shutdown when the runtime can
auto-resume an orphan child, dispatch a child from parent initialization, or
otherwise infer an unrecorded parent/child relationship without an explicit,
supported, tested hold boundary. It SHALL also refuse when it cannot establish
that no model inference is needed before release. It SHALL never infer lineage
from titles, prompt text, ordering, or process coincidence. Hook records alone
do not establish all parent/task joins; missing joins or ambiguous events stay
unknown until durable runtime evidence correlates them.

#### Scenario: Startup can auto-resume an orphan

- **WHEN** target startup may automatically dispatch an orphaned native child
  before an explicit query and the adapter cannot hold that behavior
- **THEN** the control phase refuses before source shutdown
- **AND** it reports that zero-model-request swap is unsupported for that
  runtime configuration

#### Scenario: Parent initialization cannot be held

- **WHEN** the adapter cannot prove that parent initialization and child
  admission remain held until `release`
- **THEN** preflight refuses without creating a replacement or child session
- **AND** no parent/child inference is treated as successful restoration

#### Scenario: Runtime selection cannot prove non-auto startup

- **WHEN** the selected interactive or SDK path has no pinned binary/version
  evidence or its no-auth orphan fixture has not proved non-auto startup
- **THEN** the control phase marks the configuration unverified and refuses
  before source shutdown
- **AND** it does not advertise a zero-model-request account transition

#### Scenario: Orphan wake survives print startup

- **WHEN** the selected runtime can wake an orphan through
  `restoredOrphans`/`enqueuePendingNotification` without a proven target
  no-wake control, or terminal stop and durable current-state clear were not
  proven before source-parent exit
- **THEN** the control phase refuses before target startup or source shutdown
- **AND** print/stream-json initialization is not treated as a no-wake hold

### Requirement: Supported native participants and background work are explicit

The supported set SHALL be the native participant kinds and runtime versions
for which discovery, stop, continuation, and tool/effect accounting are
actually evidenced. Native teams and native background execution SHALL NOT be
advertised as supported automatically. A runtime-owned native background child
MAY be supported when its native task ID, parent linkage, lifecycle events, and
controlled stop/restart boundary are recorded and tested. An unmanaged
detached shell or arbitrary background process is not a native child and SHALL
remain excluded or unresolved; a `run_in_background` flag alone proves
nothing.

For every unfinished native worker, the held pre-release status SHALL be
`resume-pending` when exact same-agent continuation is the candidate,
`restart-pending` when a new native run is the approved fallback, or
`unresolved` when evidence is ambiguous. After explicit release, only a
correlated same-agent continuation may become `exact-resumed`, and only a
correlated new native child may become `restarted`; ambiguity remains
`unresolved`. The status SHALL retain the native agent/task ID and coordinator
lineage. `restarted` SHALL NOT claim the original conversation or identity was
preserved. Completed workers SHALL remain `completed`.

#### Scenario: Runtime-owned native background child is tracked

- **WHEN** a native background child has a recorded task ID, parent linkage,
  `SubagentStart`/`SubagentStop` and task lifecycle events, and containing
  process-tree and hook/tool evidence
- **THEN** the adapter evaluates it under the same controlled stop and
  continuation gates as other native children
- **AND** it is not rejected solely because it is runtime-owned background
  work

#### Scenario: Detached background process is found

- **WHEN** a shell, `setsid`/`nohup` process, or other detached process is not
  represented by the native task ledger
- **THEN** the lane remains paused or indeterminate and the process/effect is
  reported as excluded or unresolved
- **AND** the supervisor does not claim that parent exit or OS suspension made
  it safe

### Requirement: Admission and native routing fences seal a complete roster

The supervisor SHALL atomically fence new native child/task admission and any
mailbox traffic before quiescence and seal the roster. A racing spawn SHALL be
rejected before launch or included with its actual parent/task identity before
the roster is sealed. Mail received after the fence SHALL be rejected or
durably recorded as pending; it SHALL NOT be silently dropped or delivered to
an untracked writer. Explicit user/coordinator input SHALL enter through a
submit operation and remain queued while held.

After `release`, a child submit or model-assisted restart instruction SHALL go
through the coordinator's native interface. The supervisor SHALL NOT open a
per-worker SDK session or send through a fictitious child account/session.
Every control request SHALL be durably deduplicated by request ID and content.
Each native dispatch intent SHALL persist first and require correlated runtime
acknowledgement; an item possibly sent without acknowledgement SHALL become
uncertain and SHALL NOT be resent automatically. An accepted instruction
acknowledgement does not prove that a child restarted. Cross-process
exactly-once delivery is not claimed.

#### Scenario: Child spawn races with the fence

- **WHEN** a native child creation request races with swap admission closure
- **THEN** it is either rejected or recorded with its actual parent/task IDs
  before the roster is sealed
- **AND** no untracked process can write

#### Scenario: Restart routes through the coordinator

- **WHEN** an explicitly released coordinator receives a model-assisted native
  child restart instruction
- **THEN** the instruction is submitted through the coordinator/native
  interface using the existing task record and coordinator context
- **AND** no per-worker SDK `open`, `send`, `shutdown`, or `release` call is
  issued

### Requirement: Released coordinator invocation rollover is bounded and identity-bound

After explicit `release`, the supervisor MAY admit a later coordinator
invocation on the same runner only when the prior invocation is conclusively
terminal and the operation, owner/lineage, coordinator session, runner,
definitions, permissions, and claim bindings are unchanged. The daemon-owned
pump SHALL select one queued mailbox and persist a mutable preparation
intent, which is not a runtime reservation. Without holding a controller lock
across the runtime await, it SHALL recheck released phase and daemon
incarnation, obtain the bounded implementation-owned `prepare-invocation`
reservation and terminal proof, and then atomically persist invocation A's
immutable history, invocation B's current context and startup binding, the
exact reservation binding, B's dispatch intent, and the operation snapshot.
Immediately before send it SHALL recheck phase, daemon incarnation, operation,
B identity, mailbox, and reservation, consume that exact committed
reservation, and attempt delivery at most once; an ordinary successful
delivery occurs once and no later intent is created. It SHALL retain the
mailbox when A is busy or pending, fence stale A events, and preserve
uncertainty rather than retrying an ambiguous send. No new coordinator open or
release is implied. The bounded record and crash rules are defined in the
[managed control contract](../../../../../specs/001-separate-swap-ctx-handoff/contracts/managed-control.md),
[runner evidence contract](../../../../../specs/001-separate-swap-ctx-handoff/contracts/runner-evidence.md),
[data model](../../../../../specs/001-separate-swap-ctx-handoff/data-model.md),
and [recovery lifecycle contract](../../../../../specs/001-separate-swap-ctx-handoff/contracts/recovery-lifecycle.md).

#### Scenario: Later mail follows terminal proof on the same runner

- **WHEN** released invocation A is conclusively terminal and one later
  mailbox B is queued for the same operation and exact runner identity
- **THEN** the daemon binds invocation B under the same coordinator session,
  lineage, definitions, permissions, and claim and delivers that mailbox at
  most once; an ordinary successful delivery occurs once
- **AND** the operation has one coordinator open/release boundary rather than
  a second coordinator or per-worker SDK session

#### Scenario: Busy invocation retains later mail

- **WHEN** invocation A is busy, non-terminal, or lacks conclusive terminal
  proof while mailbox B is pending
- **THEN** B remains queued/pending and the pump reports the bounded busy
  condition without consuming a reservation or sending
- **AND** no open, release, reset, or inferred completion occurs

#### Scenario: A stale event arrives after B is bound

- **WHEN** a callback from invocation A arrives after invocation B has a newer
  binding and watermark
- **THEN** the callback is rejected as stale and cannot mutate B or the
  immutable invocation history
- **AND** the current mailbox and operation remain governed by B's identity

#### Scenario: Rollover send becomes ambiguous

- **WHEN** a crash, disagreement, lost reservation, or changed runner leaves
  the rollover send possibly crossed or its exact result unknown
- **THEN** the reservation and mailbox remain durable, immutable invocation A
  history remains unchanged, and uncertainty is recorded on the mutable
  rollover/dispatch record
- **AND** recovery does not resend, reset, reopen, or release without explicit
  no-send or correlated-result reconciliation

### Requirement: Coordinator interrupt has distinct durable whole-roster authority

A coordinator-wide interrupt SHALL use a distinct durable transaction bound
to the exact owner/lineage generation, coordinator session, runner incarnation,
fence epoch and complete sealed native roster. Task-specific stop authority
SHALL NOT authorize a coordinator-wide call. The supervisor SHALL reconcile
pending admissions and nested children before sealing; unknown identity or
coverage SHALL refuse authorization. The identity seal SHALL be separate from
advancing lifecycle watermarks so natural completion can remain completed.
New membership or identity/definition drift after seal SHALL invalidate the
operation rather than silently expand its authority.

The supervisor SHALL persist possible-send intent before authorizing at most
one documented interrupt on the existing coordinator connection. Deduplication
SHALL cover the unresolved source run/fence and request content; changing a
request ID SHALL NOT authorize another call. Recovery SHALL reconcile evidence
without automatically repeating a possibly sent interrupt. Storage locks SHALL
NOT span runtime awaits, and independent persistence/event readers SHALL
remain available during drain.

Interrupt MAY initiate native child stopping. Its receipt, parent-result drain,
per-child terminal evidence, tool/effect outcomes, supported worker-state clear
and old-writer exclusion SHALL remain separate facts. Parent shutdown SHALL
follow authoritative native child/tool quiescence and required supported state
clearing; forced cleanup SHALL NOT fabricate those facts.

The request-observation interval SHALL start at account-control entry before
preflight/fencing and continue through held readiness until explicit release.
It SHALL retain its baseline across control, restore and recovery, distinguish
pre-existing in-flight requests, and count each new attempt. Unknown coverage
or any new request SHALL block success and retain claims. An interrupt receipt
SHALL NOT be treated as a persistent inference fence. Capability evidence SHALL
cover the actual selected runtime/account/configuration and requested
busy/settled and participant modes before disruptive effects.

#### Scenario: Crash after authorization but before receipt

- **WHEN** an interrupt has durable possible-send intent and its receipt is
  lost or the controller crashes
- **THEN** recovery preserves the intent and reconciles independent runtime
  evidence without automatically sending again
- **AND** a different request ID cannot bypass the unresolved source exclusion

#### Scenario: Natural completion races with interrupt

- **WHEN** a sealed child completes naturally with current-run correlated
  evidence during drain
- **THEN** its disposition remains completed and its tool/effect facts are
  reconciled independently
- **AND** the system does not invent a stopped event or replay completed work

#### Scenario: Native membership changes after seal

- **WHEN** a late child, unjoined admission or changed native incarnation is
  observed after the roster was sealed
- **THEN** the operation becomes indeterminate and preserves claims
- **AND** it does not widen the existing authorization, repeat interrupt or
  start a target from the invalidated seal

#### Scenario: Receipt arrives before tools have stopped

- **WHEN** interrupt succeeds but a tracked tool or external effect remains
  active or unknown
- **THEN** the operation remains held or indeterminate with its claims
- **AND** receipt does not authorize parent shutdown or replacement startup

#### Scenario: A runtime notification causes a new request

- **WHEN** an internally injected turn issues a new model request during
  account control despite external input being fenced
- **THEN** the operation fails the zero-request requirement and retains claims
- **AND** later termination or gateway rejection cannot turn the attempt into
  a zero-request result

#### Scenario: A requested mode lacks interrupt evidence

- **WHEN** only a settled single-child scripted gateway case is validated but
  the operation requires an unverified busy, multiple-child or account mode
- **THEN** capability preflight refuses before disruptive effects
- **AND** the narrow experiment is not promoted to a production support grant

### Requirement: Quiescence proves native participant and tool ownership

The supervisor SHALL interrupt and drain every supported native participant
and tracked tool, recording durable native task lifecycle and tool start/end
state plus containing process-tree ownership evidence. The ledger SHALL join
`SubagentStart`/`SubagentStop` and task lifecycle events to native agent/task
IDs, the coordinator parent, and hook/tool facts. A `PostToolUse(Agent)` event,
parent interruption, parent process exit, `setsid`, `nohup`, or OS suspension
alone SHALL NOT prove child quiescence.

Native task lifetime SHALL be tracked separately from the tool call that
launched it. A completed `Agent` launch call may leave a background child
running; its tool completion SHALL not mark that child quiescent. Terminal-stop
evidence SHALL identify the current task instance and its ordering relative to
the admission fence, not merely match an agent ID or an old completed
notification. Startup orphan exclusion and current-run writer/tool
quiescence are separate proofs, and neither substitutes for the other. The
terminal stop and durable current-state clear must precede source-parent exit;
target no-wake/no-model evidence must follow it.

An active native child after the parent `Agent` tool returns, an unknown
descendant, missing lifecycle/tool end state, an unmanaged detached process,
or ambiguous ownership SHALL leave the lane paused/indeterminate and block
replacement execution. A native child stop acknowledgement is evidence to
reconcile, not proof that an external effect did not occur.

#### Scenario: Child remains active after parent tool return

- **WHEN** `PostToolUse(Agent)` is observed but the native task ledger still
  reports an active child
- **THEN** quiescence fails and identifies the native agent/task ID
- **AND** readiness cannot be declared and no replacement writer starts

#### Scenario: Native stop is externally cancelled

- **WHEN** the SDK/user cancellation path reports a child stop but the pinned
  runtime does not guarantee that model-stopped and externally cancelled
  children have the same continuation behavior
- **THEN** the child remains held as `unresolved` until current-run terminal
  lifecycle and effect evidence is correlated
- **AND** the controller does not assume that a later model prompt can resume
  the child or replay its work

#### Scenario: Child or tool remains uncertain

- **WHEN** a child, descendant, or tool can still write or its ownership cannot
  be proven
- **THEN** the supervisor reports the specific uncertainty
- **AND** it does not start competing writers or declare the lane ready

### Requirement: Durable state is private, bounded, versioned, and non-secret

Managed state SHALL be stored locally under
`openrepotools-managed/<host-identity>/<canonical-lane>/` below the resolved
workspace Git common directory. The resolver SHALL reject symlinked components,
unsafe ownership/modes, path traversal, and mismatched workspace identity. The
Unix control socket SHALL be local-only with a 1 MiB frame limit, a 5-second
default connect timeout, and a 120-second default operation deadline.

The versioned operation record SHALL contain phase, operation/generation IDs,
profiles, the coordinator transcript UUID, native child agent/task IDs and
parent links, immutable child definitions/effective permissions, per-worker
status, lifecycle/tool/process evidence, optional lineage/worktree claims,
launch fingerprint, persistence/readiness evidence, and unresolved effects. It
SHALL contain no credentials, tokens, conversation bodies, generated prose, or
signed capability certificate. An old independent child-runner schema SHALL be
rejected or migrated by an explicit versioned operation; it SHALL never be
silently reinterpreted or deleted.

#### Scenario: State path is unsafe

- **WHEN** a state component is a symlink or has unsafe owner/mode/path
- **THEN** the operation refuses before reading or writing managed state
- **AND** it does not use a less-protected fallback location

#### Scenario: Legacy schema is not lineage-safe

- **WHEN** a durable record lacks native parent/task evidence or contains
  independent child UUID/open/release fields
- **THEN** the controller refuses or requires an explicit migration before
  control
- **AND** it leaves the record recoverable without treating it as native state

### Requirement: Swap restores the coordinator and reconciles native children while held

After successful quiescence, `swap` SHALL connect the supported coordinator by
its exact UUID under the selected target profile and preserve completed native
workers as completed. It SHALL not attempt an external child resume with a
synthetic UUID or child account. Before readiness it SHALL verify
`init.account` against the expected account email, actual
`init.current_permission_mode`, stored model/config fingerprint against the
supported-model list, effort, tools, permissions, workspace, prescribed
custom-agent definitions, coordinator parent/task routing, transcript store,
process ownership, lifecycle evidence, and exclusive claims.

All target participants SHALL remain held from inference until a durable ready
state exists. For each unfinished child, the controller SHALL prefer verified
same-agent continuation and mark the safely stopped child `resume-pending`
until release. When exact continuation is unavailable but the controlled
native new-run fallback is allowed, it SHALL mark the child `restart-pending`
and leave it held. `release` SHALL be a separate explicit normal-model-use
action and SHALL occur at most once. Only after account readiness and explicit
release MAY a model-assisted instruction ask the coordinator/native interface
to continue the same native agent or create a **new native child** from the
existing task record and coordinator context. A correlated same-agent
continuation is `exact-resumed`; a correlated new child is `restarted`; an
accepted send without correlated lifecycle evidence is `unresolved`.

Restart is not semantic handoff: no written handoff, generated summary, or
model checkpoint is a swap prerequisite or restart artifact. A restarted child
is not proven to have the original conversation or identity. Completed workers,
uncertain effects, and unresolved children SHALL never be replayed.

#### Scenario: Coordinator and child exact continuation restore

- **WHEN** the supported coordinator has a validated transcript and a native
  child is a `resume-pending` candidate and, after explicit release, verified
  same-agent continuation has correlated current-run task events
- **THEN** the coordinator resumes its original UUID while held and the child
  is recorded `exact-resumed` under that coordinator lineage
- **AND** completed workers remain `completed` and no model reconstruction or
  handoff is generated

#### Scenario: Child requires post-release new-native restart

- **WHEN** the exact child continuation is unavailable but the coordinator
  reaches target-account readiness and the user explicitly invokes `release`
- **THEN** the child is recorded `restart-pending` until the coordinator/native
  interface dispatches a restart instruction
- **AND** a correlated new native child may become `restarted` only after its
  native task events, parent linkage, immutable definition, effective
  permissions, and tool/process facts are recorded

#### Scenario: Accepted restart send has no child event

- **WHEN** a restart instruction is acknowledged by the coordinator/native
  interface but no correlated native child start/task event arrives
- **THEN** the worker is recorded `unresolved`
- **AND** the instruction, child work, and any uncertain effect are not resent
  or replayed automatically

#### Scenario: Partial native restart starts

- **WHEN** a model-assisted restart creates only some requested native children
  before interruption, timeout, or loss of lifecycle evidence
- **THEN** started children are correlated and retained with their actual
  statuses while unstarted children remain `restart-pending` or
  `unresolved`
- **AND** retry does not launch a duplicate child or replay completed work

#### Scenario: User cancels a pending restart

- **WHEN** the user cancels a model-assisted native restart after `release`
- **THEN** no further child is launched, the operation records the cancellation
  and each child status honestly
- **AND** cancellation does not mark an unobserved child as completed or safe

#### Scenario: Account or permission does not match

- **WHEN** initialization reports a different account email or permission mode
  than the recorded target
- **THEN** readiness fails while participants remain held
- **AND** the controller does not silently downgrade, escalate, or release

### Requirement: Writer claims belong to the owning session-lineage

Each native writer SHALL be covered by one exclusive claim owned by its
coordinator session-lineage. A worker's native agent/task ID and parent
linkage identify the writer within that claim; they do not create a separate
top-level owner. An isolated writer MAY additionally hold one exclusive,
non-overlapping worktree claim in a host/workspace-global index shared across
managed lanes. Read-only children need no worktree claim.

Equal real paths, aliases, and ancestor/descendant paths SHALL conflict across
lineages. A lineage SHALL release its claim only after authoritative completion
or stop plus native participant and tool quiescence. A new registration SHALL
allow existing dirty and untracked files and preserve them. It SHALL refuse
only an occupied/overlapping worktree or an ambiguous prior writer, before
changing a claim or filesystem. Swap SHALL NOT commit, push, stash, reset,
clean, move, or reconstruct those worktrees. The lineage workspace claim SHALL
remain held while any owned writer or external effect is unresolved, including
when the source coordinator has exited.

#### Scenario: Dirty isolated worktree is requested

- **WHEN** a native writer requests an untracked or uncommitted isolated
  worktree that is not occupied or overlapping
- **THEN** the owning coordinator session-lineage claim and optional worktree
  claim succeed without cleaning or rewriting the worktree
- **AND** dirty and untracked files remain present

#### Scenario: Worktree or lineage ownership is ambiguous

- **WHEN** a requested worktree is occupied, overlaps another claim, or has an
  ambiguous prior lineage writer
- **THEN** registration refuses with zero state and filesystem changes
- **AND** existing ownership remains intact

#### Scenario: Registered work is dirty

- **WHEN** a quiescent managed lineage contains uncommitted or untracked files
- **THEN** a successful swap leaves those files in the same worktree
- **AND** no clean-tree or push prerequisite is imposed

### Requirement: Completed work and uncertain effects are never replayed

The supervisor SHALL distinguish interruption acknowledgement from proof that
an external effect did not occur. An unknown deployment, push, tool side
effect, native child effect, or other external result SHALL be recorded as
`unresolved` and SHALL block automatic replay and release until explicitly
reconciled. A completed worker or completed effect SHALL be immutable for the
operation and SHALL not be restarted, duplicated, or replayed.

#### Scenario: Response is lost after an external mutation

- **WHEN** interruption occurs after an external action may have completed but
  before its result is known
- **THEN** the action and affected worker are marked unresolved
- **AND** retry or model-assisted restart does not issue the action again
  automatically

#### Scenario: Completed child is present at swap

- **WHEN** a native child has an authoritative completed state before the
  roster is sealed
- **THEN** it remains `completed` without resume or restart
- **AND** its effects are not replayed

### Requirement: Failure and retry retain one operation identity

The supervisor SHALL use bounded quiescence/startup deadlines and retain
paused or indeterminate state after failure. Retry SHALL reuse the operation
identity, reconcile surviving coordinator/lineage ownership and native task
events first, and avoid duplicate participants, child instructions, mail
delivery, external actions, or release. A restart-pending worker remains
pending until an explicit post-release restart is correlated; retry SHALL not
silently turn it into a new child.

#### Scenario: Target coordinator startup fails

- **WHEN** the source runtime is safely paused but the exact target coordinator
  session cannot initialize before the deadline
- **THEN** the lane remains visibly paused/indeterminate with recoverable native
  state and per-worker statuses
- **AND** retry does not launch a second owner, replay completed work, or
  require a generated handoff

### Requirement: Compatibility evidence is explicit and bounded

Release acceptance SHALL include fake-runtime evidence for the coordinator and
native-child lineage, native agent/task discovery, parent/child admission
fences, the no-model-request control path, startup orphan behavior, exact
coordinator resume, verified same-agent continuation where claimed,
`resume-pending`/`restart-pending`/`exact-resumed`/`restarted`/`unresolved`
status transitions, runtime-owned
tracked background children, active tools, process-tree ownership, lineage and
isolated-worktree claim exclusion, dirty work, uncertain effects,
completed-worker preservation, crash/retry, cancellation, partial restart,
and concurrent operations. Evidence SHALL include the case where a child
remains active after `PostToolUse(Agent)`, and SHALL identify the native
runtime versions, SDK-selected CLI binary and digest, and participant kinds
actually tested. The evidence SHALL include a no-auth orphan fixture proving
non-auto startup for every advertised mode. Native teams and background modes
without that evidence remain outside the supported set.

Live Claude SDK integration SHALL remain `UNVERIFIED` until a separately
opt-in real probe; this capability SHALL make no live auth, quota, or model
call during control. Coordinator-only evidence SHALL not be presented as
complete native-worker restoration; workers must retain explicit statuses and
unsupported scope must be reported.

#### Scenario: Only coordinator restoration is proven

- **WHEN** evidence proves exact coordinator resume but lacks native child
  discovery, stop-boundary, and continuation/restart evidence
- **THEN** the capability is not released as a complete native-worker swap
- **AND** the implementation reports worker scope and refuses unsupported
  configurations instead of silently dropping or replaying workers
