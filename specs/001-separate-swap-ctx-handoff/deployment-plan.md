# Completion and deployment plan

## Local lane launch gate (October 4)

Install and qualify local Omnigent for lane launches under the
[launcher contract](contracts/claude-lane-launchers.md). The selected command
stack is `lclaude → oclaude → Omnigent native-Claude adapter → pclaude → Claude`;
plain `oclaude` runs outside a lane and `pclaude` stays direct/native outside a
lane. The shared server/runner and container survive swaps. T063–T065 add local
profile/custody/input/resume qualification before T055–T057 can claim end-to-end
delivery on this stack. Existing direct-CLI evidence retains its scope and is
not qualification of the new adapter. Local lanes require no factory/cloud
endpoint; broker mode still requires codeXfactory admission. Worktree/role and
runtime activation authorization rules remain in force.

## Prospective broker deployment: local CPC and cloud-connected engineer hosts

The accepted first delivery offers LS lifecycle-only swap and a lightweight
authenticated factory client. The October 4 amendment requires local Omnigent
for lanes, with no shared factory/cloud dependency. Delegation uses the existing
factory admission service without requiring a full local factory installation; installation
does not confer project/task/pool/model-account grants. Private owner-operated
Omnigent delegation is deferred outside the first delivery. Package/API design
and qualification belong to T059–T062 under the
[accepted scope](contracts/lane-task-broker.md#accepted-access-and-packaging-scope).

Brett's October 3 direction favors a local CPC installation and a shared cloud/
Azure LS gateway for engineers enrolling spare xFactory compute. Use both in
the distributed shape: cloud LS request/task/result coordination through the
existing Omnigent/Hermes factory layer, and local custody/swap controllers plus
EGS on each execution site. Reuse one registry/dispatch authority and an
authenticated outbound host connection. Model account admission is separate
from CPU enrollment. Cloud outage cannot override local JSON fences/exit proof
or authorize duplicate execution; new shared admission waits/refuses, while
existing locally admitted work remains within its recorded authority.

The inspected CPC manifest declares Ubuntu WSL, Docker CE and systemd; qualify
the Linux custodian in the actual runtime namespace. Extend OmniWorker-Install
for host setup and Omnigent-Install for orchestration integration. Qualify local
operation first, then cloud enrollment/transport under T059–T062. Azure resource
selection and provisioning are pending and not authorized here. Follow the
[deployment contract](contracts/lane-task-broker.md#deployment-direction-cloud-gateway-and-local-execution-control).
This adds no dependency or scope change to T054–T057's graceful swap delivery.

## Current delivery plan: `claude-cli-supervised-jobs-v1` (September 26, amended October 4)

[Tasks T052–T057 and T063–T065](tasks.md) own delivery; T058 is a separate non-gating index
follow-up. The
[current contract](contracts/claude-cli-supervised-jobs.md) defines acceptance.
Astra leads architecture, Sol High leads orchestration, and Luna Max writes the
defined Speckit implementation tasks. Use the active platform's models at the
effort appropriate to each task.

**Delivery target:** a graceful per-session swap in the existing shared
container. It hosts many independent Claude CLI sessions and **must stay
running**. A finishes optional foreground wrap-up, exits its CLI, and the
launcher verifies exact-runtime exit and reconciles session activity before
one explicit release starts B on A's exact parent. Admitted supervisor jobs
and unrelated Claude session C continue. No container stop/kill/restart, broad
user/shared-process-group kill or shared configuration/auth mutation is allowed.
The supervisor may stay in the container with a lifetime independent of A.
Only the parent Claude conversation resumes. Unfinished native child tasks
are reconstructed as NEW children under B with new IDs; the old IDs are
evidence. Existing execution-group OS jobs continue with their original IDs.
Long-running and external commands route through the lane's MCP bridge, lanes
service and execution-group supervisor; the current direct
MCP-to-supervisor socket is an implementation gap under T055. Native Edit,
Write and NotebookEdit remain available; only Bash and PowerShell are denied.

The dedicated Docker provider is a dormant superseded candidate. Preserve
its code and evidence; its host broker, Engine identity, cgroup access and
retained parent are not prerequisites for this delivery. No supervisor move
to WSL or another host is required. Forced per-session recovery remains a
separate future gated mechanism; the initial path blocks takeover if graceful
exit or complete activity accounting cannot be established.

**Evidence status:** T052 documentation and T053 private ledger remain
complete; T054–T057 stay open. The seven-test T053 ledger result, later 44-test
private Docker/runner gate and scratch OS/CLI probes retain their original
scope. They do not certify shared-container exit or effective foreground-child
policy. The current private launcher still assumes fixed settings/MCP paths;
T055 must isolate those per runtime. Full-suite failures recorded in
[verification.md](verification.md) remain unresolved. The earlier correction changed documents only. The latest user instruction
authorizes this documentation amendment and documentation-only checkpoint
before further T054/T055 code. It authorizes no canary run, seat movement,
merge or deployment. Use the [Linux subreaper implementation
contract](contracts/linux-session-subreaper.md) for T054.

### October 2: no source headroom requirement

The native allowance cannot be the shutdown budget. Safety and B's transition
packet must depend on durable service/runtime records with zero source model
tokens and no final handoff. Consume fresh profile usage directly, independently
of user prompts, and retain child/task/job evidence throughout normal work.
Optional Stop-hook wrap-up is attempted only before known exhaustion and
before control entry. Skip it at known exhaustion; do not retry if it runs out
of quota. The first delivery still requires a verified idle boundary and exact
exit/effect reconciliation. Otherwise the bounded outcome retains claims and
keeps B absent. T055 implements this behavior; T056 covers absent or insufficient
allowance and missing final handoff, with readiness and refusal arms separated.
No allowance behavior is itself a qualification gate or an authorization to
force recovery.

Seal and deliver the service-verified handoff outcome before B's first turn:
`clean` for a completed pre-exhaustion checkpoint with verified transfer
evidence, otherwise `repair-required` with reasons and identified repair items.
Both paths require source safety before release. B completes required startup
repair before normal work; record its completion separately and preserve the
original outcome. Dirty files, running jobs and unfinished tasks with accounted
continuation plans can be part of a clean transfer. T055 implements the marker
and repair record; T056 verifies both paths and rejects stale bindings.

### September 30 decision amendments

Keep Claude Code's parent transcript and child sidecars in its projects store;
the JSON ledger holds a sealed pointer and digest. Compare source and target
profile stores before release and copy with relative layout plus digest
verification only when their resolved stores differ. The assembly root is an
additional lane identity, resolved from `project.yaml` or the aggregation
register, and does not replace the WIP common-directory/worktree claim fields.
On the workstation holding A's exact PID, local JSON under flock is the sole
authority. Use QA Postgres when a database URL is configured and otherwise
SQLite beside the JSON ledger as an optional derived index. The swap path never
reads it, and QA index availability is not a gate. Write-behind upserts use
local record ID plus digest and recover from the JSON ledger. Keep connection
settings/environment uncommitted and credentials service-only, schema-scoped
and distinct from supervisor authority. Index a `LANES.md` row only after its
projection is stored in JSON; the index never replaces Git `LANES.md`. T058 is
a separate non-gating offline follow-up after T057.

The canary pair is supplied by the operator when a canary is separately
authorized. `team05d` / `team05j` are the current expectation only; record the
concrete pair in T056 evidence and in the ledger before any seat move.

If requested before known exhaustion, deliver the optional one-time wrap-up
through the exact parent's registered `Stop` hook before durable control entry.
At a verified idle boundary after any wrap-up continuation, fence input
and signal only A's exact PID through the custodian; use PTY `/exit` only if
SIGTERM is measured unsupported. Measure the pinned CLI behaviors before any
T055 path depends on them. Native Edit/Write/NotebookEdit are allowed; deny
exactly Bash and PowerShell. Defer the mid-turn Agent admission fence to a
future gate beside forced recovery; T054–T057 neither depend on nor test it.
Seal the first-delivery child roster at the verified idle boundary after
foreground children return, and hold busy requests until that boundary or a
bounded refusal.

### Dependency and acceptance sequence

| Task | Required work | Evidence to close the gate |
| --- | --- | --- |
| T054 | Exact per-session launch/exit identity and durable source owner/restart fence | Source exit is SIGTERM to the exact admitted PID at a verified idle boundary, observed through wait plus ECHILD; unknown activity blocks B; container, C and admitted job remain alive. |
| T055 | Service-routed supervisor jobs, isolated CLI manifests, sealed transcript pointer, measured hooks/signals, native tool policy and prepare/release | Source claim precedes spawn; target history is verified or copied before launch; per-runtime settings/auth cannot collide; ready has no B; one release starts the exact parent once. |
| T056 | Integrated shared-container positive and fault fixtures | Exit, history, jobs, C continuity and dispatch counts are observed; record the concrete operator-supplied canary pair in runtime evidence if a canary is separately authorized. |
| T057 | Review, full regression/CI, install/rollback and a separately authorized authenticated canary | Exact installed revision and measured CLI/configuration tuple, original job result and child continuation, no duplicate writer; no activation without a passing canary and separate authorization. |

T054 needs a genuinely admitted job, so implement T055's minimal independent
runner early and reuse it in MCP integration. No scratch outside process can
substitute for its identity, durable intent and result custody. These rows
order existing tasks rather than create another checklist.

### First implementation slice

Admit A through one launcher from initial entry, claiming exact parent/lane/
generation before spawn. Journal an owned child handle or namespace/start
identity, runtime incarnation, immutable configuration/profile references and
pending actions. Every source/target create, restart, recovery or adoption
path consumes the same durable fence. Duplicate parent admission refuses
before spawn. An unmanaged running CLI cannot be retrospectively adopted.

Pin foreground-only native Claude work and verify its actual helper/child
lifecycles. Native Edit, Write and NotebookEdit are allowed; deny exactly Bash
and PowerShell. Long-running and external commands use the MCP bridge, lanes
service and execution-group supervisor. Measure the pinned CLI before relying
on Stop-hook or signal behavior. Before known exhaustion, optionally deliver
one pre-control-entry wrap-up request through the exact parent's Stop hook;
honor `stop_hook_active`, durably
deduplicate by request ID, and treat hook errors as no wrap-up. The instruction
is to start no new agents or long work, record state in the handoff, then stop.
At a later nonblocked Stop or StopFailure idle boundary with no later
UserPromptSubmit, fence relayed keyboard input and send SIGTERM only to A's
exact PID through owned custody. Require the custodian's wait and ECHILD
witness; SessionEnd only corroborates. PTY `/exit` is a single atomic,
CR-terminated fallback only if SIGTERM is measured unsupported. A completed
turn, quota notice or prompt is not CLI exit. Refused exit, unknown/escaped
descendants, lost journal or unreadable identity block B and preserve claims;
there is no automatic forced-stop fallback.

Use runtime-specific immutable MCP/settings files, distinct profile/auth
bindings and a generation-scoped job credential separate from supervisor
credentials. Replace the private launcher's fixed shared file assumptions.
Changing A/B must not overwrite C's files or change broad user credentials or
environment. The native tool policy keeps Read/Glob/Grep/Agent/SendMessage,
Edit/Write/NotebookEdit and denies Bash/PowerShell. Same-parent native-child
replies stay foreground and external-session routing is disabled. Demonstrate
a native Edit and, separately, an admitted job's conflicting-write refusal
against the worktree reservation. A native Edit cannot consult that
reservation; parent-edit versus admitted-job concurrency during normal
operation is out of scope. During swap, the input fence and exit witness cover
the window. Read operations do not claim a stable snapshot of a live job's
files.

Add the T053 ledger transcript sub-record with profile family, resolved store,
encoded project key, parent UUID/path/size/digest and complete child transcript
and metadata sidecars. Seal after source exit and descendant drain. Compare
resolved source/target stores; copy across stores preserving relative paths,
then reverify digests before launch. Resolve assembly identity from the
worktree `project.yaml` or aggregation register, without replacing WIP identity
fields. Record measured behavior for StopFailure `rate_limit`, Stop block turn
continuation, idle-prompt SIGTERM shutdown/SessionEnd, and resumed SessionStart
transition-packet context on the pinned CLI (currently reported as 2.1.286)
before T055 depends on any of them.

Provide an external model-free control entry plus a validated `/swap` route.
The prior slash-hook diagnostic only established a bounded interception;
returning a prompt or hook result supplies no exit evidence. Optional bounded
wrap-up happens while A still owns the session, before control entry. Prepare
itself uses no model request; early swap can request only the supported graceful
exit path within a recorded bounded deadline; timeout/refusal retains claims
and blocks B. No model wrap-up is requested after control entry. Durable fencing and
reconciliation precede `ready-to-resume`; one explicit release is journaled
before B creation. Unknown startup acknowledgment prohibits replacement.

### Planned T056 fixture: A and C in the same container

Keep this as the planned integration matrix. The September 30 checkpoint
authorizes no canary run, seat movement or merge; any live account transition
requires separate authorization. Prepare the expected evidence and exact scope
before that authorization is requested.

1. Launch independent Claude sessions A and C inside the SAME existing
   long-lived container through the candidate session launcher. Record exact
   container/session identities and separate config/auth bindings; C has an
   independent observable activity marker. Register dirty/untracked fixtures.
2. Save at least one native foreground child history under A; the fuller
   T056 matrix covers completed and unfinished children. Admit a continuing
   supervisor job with stable ID, runtime identity, launch counter, output
   custody and resource reservation. It has no dependency on A's terminal.
3. Exercise both optional pre-exhaustion wrap-up through the exact parent's
   Stop hook and no-allowance/no-final-handoff cases without that block. At a
   nonblocked Stop or StopFailure with no later UserPromptSubmit, after any
   wrap-up continuation, fence relayed input and send SIGTERM to A's exact PID
   through owned custody; use
   the measured PTY fallback only if SIGTERM is unsupported: one atomic `/exit`
   write including carriage return, then a bounded wait for exit, SessionEnd
   or Stop. No observed change by the deadline is refusal with retained claims,
   never a retry. Observe the custodian wait and ECHILD witness plus correlated
   child/helper/tool lifecycle.
   C and the container stay running, while the original job's output advances.
   A saved context and a completed model task are distinct assertions.
4. Persist the source-generation fence, reconcile pending launches, histories,
   effects, jobs and worktree claims, and observe `ready-to-resume` with B absent.
   Verify stale A commands/restarts refuse and C's config/auth remains unchanged.
5. In an authorized runtime fixture only, explicitly release B once on A's
   exact parent. Verify actual parent/profile,
   B's service-authored task and filesystem packet, NEW child IDs for safely
   unfinished tasks, job identity/result readback and no duplicate worker,
   job or target. Completed children are not relaunched.

Negative arms must keep B absent on refused/uncertain exit, unknown/escaped
children, lost runtime identity/journal, competing B/source claims, stale A
actions and launcher restart with unresolved intent. Also cover changed
manifest/profile, late A effects, reserved-path conflicts, lost ACK and crashes
around admission, exit, fence, release, startup and result delivery. Intact
recovery may observe the same intent; it never infers permission to spawn again.

### Evidence layers and release

Offline tests use the canonical `tests/run.sh` wrapper and establish ledger,
identity and refusal behavior with fakes. They cannot establish real Claude
foreground-child/exit behavior. Bounded actual CLI observations must measure
that behavior in the shared topology. The authenticated installed canary
then proves account identity, exact parent resume and new-child task recovery through the same
production route. Report each layer independently with exact source/runtime/
configuration hashes, expected assertions, observed identities/counters and
PASS/FAIL/INCONCLUSIVE. Missing evidence never becomes PASS.

Any future versioned opt-in installation requires passing shared-route and
invoked-dependency tests, applicable actual CLI/fault evidence, strict OpenSpec
validation, isolated installation/rollback rehearsal and separate authorization
for the installed authenticated canary. The source/target pair is supplied by
the operator at that time; `team05d` / `team05j` are the current expectation
only. Record the concrete pair in T056 runtime evidence and in the ledger before
any seat movement. Record the full canonical regression census on the frozen
candidate. Retain positive native `ctx`/restoration acceptance assertions and
individually map any remaining failures to that unreachable, explicitly
refused route; they remain open requirements. An unexplained
failure, shared-path/dependency regression or altered native refusal boundary
blocks this stage. No default/global activation or T057 completion follows
from a scoped pass.

Before general rollout, complete review, strict OpenSpec validation, full regression
and applicable platform CI on a frozen candidate. Rehearse isolated install
and rollback, including per-session configuration and a surviving job. Preserve
the existing suite failure census and fix required failures before acceptance;
focused passes do not replace that general-rollout gate. Runtime support
remains disabled until a separately authorized installed canary passes; publish
only its measured graceful-session configuration.

For a later separately authorized canary, bind one disposable lane, the
operator-supplied A/B profiles, independent C, allowed effects and bounded
actions. Record the concrete pair in the ledger before any seat movement.
Preserve seats until source exit and reconciliation establish ready; only then
perform the specifically authorized seat change and explicit B release. No
target model preflight runs during preparation.

Rollback disables new admissions/target launches while retaining compatible
supervisor control, jobs, journals, claims and reservations. It must leave the
shared container and C running, avoid shared config/auth mutation and never
restart A, clear uncertainty or reset files. T057 closes only with installation,
rollback and canary evidence; broader OpenSpec archival still requires all
governed work to land or be explicitly dispositioned.

## Historical plans and evidence

The sections below retain earlier SDK/PGID and strict-mode scheduling records.
Follow the current delivery sequence above for this CLI capability. Historical
runtime approvals, support claims and next-step statements do not apply to it.

## Earlier stop-then-resume v1 plan (historical SDK path)

Brett subsequently approved implementing the
[stop-then-resume recommendation](../../openspec/changes/separate-swap-ctx-handoff/stop-then-resume-decision.md).
This supersedes the earlier guarantee-preservation scheduling decision below
for a new explicit v1 mode only. Strict mode and its historical records retain
their full guarantees and upstream requirements.

V1 first needs its own isolated runtime experiment with saved edits, unfinished
child/tool work, source exclusion/effect accounting and **no target creation
until release**. The existing probe's `--release-target` sends a later query;
it does not defer process creation and cannot be reused as v1 acceptance.
Then implement mode-specific preparation, release-authorized exact startup and
recovery against the measured boundary. Unknown source writers/effects remain
a blocker even though pre-release target held-loading is no longer required.

The native unenroll ownership-conflict correction remains an independent
prerequisite under T014/T024; it is deferred until after the first v1 experiment.
All subsequent regression, sibling integration, platform CI,
authenticated canary, installation and rollback gates below still apply.
No live account, lane or install destination has been selected by this approval.

The first v1 experiment is now implemented and executed: 113 focused tests
passed; three isolated arms demonstrated release-before-start ordering and
refusal behavior. Restoration remains inconclusive because target startup
emitted a task event and the probe correctly sent no additional history query.
See [live-validation.md](live-validation.md). Next establish source containment
and correlate startup child/history evidence, then implement the public
mode-specific lifecycle. No public option, production activation or deployment
is claimed by the probe.

The startup-event/history follow-up is also implemented and measured: **137
focused tests** pass, and the new isolated release run preserved the measured
history prefixes. The startup stopped notification matches source session/task
but lacks the source tool-use join; child identity and runtime restoration stay
unverified. Continue with authoritative joins, startup reconciliation and source
containment, not another uninstrumented quiet-window run. Evidence is in
`live-validation.md`; the public lifecycle and downstream release gates remain
unchanged.

## Earlier September 22 execution sequence (strict mode)

The user requested implementation of the completion/deployment plan on
September 22. This section supersedes the historical scheduling checkpoints
below; [tasks.md](tasks.md) remains the only executable task list. Existing
architecture and capability requirements still apply.

The user subsequently chose to preserve the guarantees, prepare the
[upstream runtime requirements](../../openspec/changes/separate-swap-ctx-handoff/runtime-support-requirements.md),
and leave activation blocked until supported. Continue independent offline
corrections and retain the deployment sequence below as gated future work.
No guarantee reduction, authenticated canary, or installed cutover follows
from this decision.

Lane `swap-rebuild-codex` holds this OpenSpec change through the sanctioned
workspace claim at `3577c1154efb20d208033e2a17b50c6e99dff409`.
Astra owns architecture review, Sol High owns orchestration and test execution,
and Luna Max owns implementation. Use Codex models in this execution. Keep
requests bounded, reuse these roles, and attach evidence to existing task IDs.

1. Verify the inherited transport-accept and historical-swap shutdown fixes
   with the worker/pump/persistent-lifecycle/swap/fence diagnostic on one frozen
   snapshot. Preserve uncommitted work and distinguish this result from the
   earlier 34-failure census. Sol is the sole test executor.
2. In parallel, establish whether supported runtime observations can satisfy
   worker/orphan clearing, run completion, exact parent loading while held,
   and continuous dispatch observation. Astra records a concrete supported
   interface or the missing boundary. Repeating quiet probes cannot establish
   an absent observation. Native ctx needs its own pre-shutdown evidence.
3. Complete native child semantic routing and durable coordinator transport
   bindings under T013/T018, then the remaining swap/release/recovery and
   ctx/restoration tasks against the established runtime contracts. Preserve
   pending entries and exact retries; unavailable routing refuses before send.
4. Agree one lifecycle authority and migration/landing order with recovery
   PR #97 and supervised-context PR #121. Both were open and conflicting at
   the planning read. Reconcile the semantic transition conflict before
   resolving textual merges. Command migration and external integration
   decisions remain explicit entries in the governance review.
5. Freeze the resulting candidate and run T027/T028/T029 through the serialized
   `tests/run.sh` in the declared bench, with the pinned submodule present.
   Isolated diagnostics remain diagnostics. Require platform CI, requirement
   reconciliation, and bounded real-account evidence for T031/T032.
6. Review and merge in the agreed dependency order. Rehearse installation and
   rollback in a disposable environment, then install the exact merge revision
   from a clean checkout of that revision with
   `OPENREPOTOOLS_REF=<merge-sha> ./openRepoTools --install` in the selected
   canary scope. The installer itself must come from that revision: an older
   installed command has an older file inventory even when its fetch ref is
   changed. Include commands, Python modules, skills, hooks, and settings
   in inventory verification; bin-directory isolation alone is insufficient.
7. Expand only after canary swap/release/recovery and legacy checks pass.
   Record installed revisions, runtime pins, destinations, and results before
   archiving the change. Rollback preserves journals and claims and uses
   tooling compatible with the durable state.

Named disposable accounts, lane, permitted effects, and installation destination
must be established before their corresponding live actions. This execution
request does not select those missing values or make unknown runtime evidence
true. The first scheduling milestone is the focused candidate result and
Astra's feasibility decision; completion requires passing release gates and
verified installation.

## Historical planning and checkpoints

Date: 2026-09-17. Execution sequence for the existing feature
`001-separate-swap-ctx-handoff`; [tasks.md](tasks.md) remains the sole
implementation task list. This plan does not authorize deployment or change
the approved native-subagent architecture.

## Starting point

[Verification](verification.md) remains **INCOMPLETE — LIVE UNVERIFIED**.
Native admission has an internal seam but is not yet integrated into normal
native start/dispatch. Lifecycle replacement, recovery, ctx and release remain
incomplete. The recorded 129 CLI passes and one wrapper hygiene pass establish
limited local evidence; they do not establish feature readiness. All 32 Speckit
tasks were unchecked at planning time; that was an evidence backlog, not proof that no code
exists. Earlier percentage estimates should not be used to schedule deployment.

The critical path is **runtime feasibility → public native swap → release and
recovery → regression and live evidence → installed canary → rollout**.

Execution update: the reproducible no-auth initialization probe succeeded in
an isolated sandbox, but Gate 0 remains **inconclusive** because the orphan
positive control and supported terminal-stop/clear case were not exercised.
Astra's implementation decision is to complete the public capability-refusal
path before source disruption, continue independent state/packaging fixes,
and hold successful native stop/restore integration until its runtime boundary
is established. This preserves the approved feature scope. Detailed results
belong in [verification.md](verification.md) and [live-validation.md](live-validation.md).

2026-09-18 Stage 1 update: the bounded scripted gateway investigation found a
viable coordinator-wide `interrupt` candidate: real native task/tool stop,
zero source-control requests, exact parent held resume with zero requests,
and preserved UUID/history after explicit release. Task-specific `stop_task`
still produced a request after the parent turn settled. An authentic
unfinished-source crash control also resumed quietly after fixture-process
exclusion. This advances feasibility without closing full Gate 0. The next
governed design step is now captured in
[coordinator-interrupt.md](contracts/coordinator-interrupt.md) and its
[decision record](../../openspec/changes/separate-swap-ctx-handoff/coordinator-interrupt-decision.md).
The first implementation slice is the internal durable whole-roster
authorization/drain transaction with fake-runtime, real-store and IPC tests;
it does not replace task-specific authority or enable public success. Actual account
modes and the remaining runtime/lineage gates still precede enabling swap.
See [the Stage 1 disposition](../../openspec/changes/separate-swap-ctx-handoff/stage1-runtime-boundary.md#architecture-disposition).

Implementation checkpoint: T025 packaging/wrapper acceptance and T026
documentation alignment are complete. The internal native stop transaction
now spans durable controller records, daemon callbacks and SDK transport;
acknowledgement, task termination, tool/effect quiescence and restore-state
clearing remain separate conclusions. The frozen managed census is
**735 passed, 16 failed**, including **49 passing stop-path tests**, with no
changes to its 36 hashed files during validation. Remaining failures are
11 controller and 5 daemon lifecycle cases; none is waived. See
[the frozen result](verification.md#frozen-follow-up-result) for artifacts and
limits. The selected-runtime missing-task stop succeeds without a terminal
event, reinforcing that an acknowledgement cannot establish safe restore.
No deployment has occurred.

The next offline integration package is coordinator-only public native start:
one coordinator runner and lineage claim, durable context before release or
admission, and no separate child runners/mailboxes. This precedes replacing
the remaining prototype lifecycle and dispatch paths. Runtime feasibility
remains the first release gate; neither this package nor internal stop tests
can certify held restore without the required selected-runtime observations.

## Ownership and parallel work

### 2026-09-18 dependency audit before lifecycle integration

The latest bounded offline batch passed 54 new tests; its combined census
was 878 passed and the same 20 existing failures. These results validate the
observational drain projection and internal claim CAS, not target adoption.
See [verification.md](verification.md) for the frozen evidence.

Inspection before the requested source-history/adoption, restore/recovery,
and release/ctx integration identified prerequisites that remain open under
the existing runtime gate:

- The SDK-generated request observation is explicitly unobservable, with an
  unknown request count. Local invocation watermarks do not establish the
  required external-control-entry-to-release observation interval.
- The adapter validates supplied worker-state-clear observations but exposes
  no supported operation or observation producer proving that durable runtime
  worker state has been cleared. Process-group exit is not that evidence.
- Generic post-release send acceptance is available, but native restart
  attempts and old/new task correlation are not implemented. Acceptance cannot
  become `restarted` or `exact-resumed` without those joins.
- Native source records still validate against the active context. History
  preservation and target adoption need a durable intent and a reconciler:
  the claim index and controller record are separate atomic writes, even when
  both occur under the same lock. An exact target claim may support finishing
  a recorded adoption; missing, duplicate or mismatched claims must remain
  indeterminate, never cause another open or blind CAS retry.

These are dependencies within the existing Speckit tasks, not a new task
list or permission to relax the zero-request or startup gates. The runtime
boundary must be established before enabling successful native restoration;
offline history/adoption work alone cannot close it. No implementation task
was closed by this audit and no runtime experiment was run.

Astra owns architecture and the runtime support decision. Sol High owns
sequencing, file ownership, integration and release evidence. Luna Max writes
the defined implementation tasks. These are the existing role assignments;
use Codex models in this Codex session. These roles were dispatched during
implementation, as recorded in the verification evidence. The product's SDK runtime is separate from the
platform used to develop it.

Sol should assign disjoint files and one integration owner before dispatching
work. Do not let multiple writers edit the controller, daemon or SDK adapter
at the same time. Begin with these independent streams:

| Stream | Existing tasks | Deliverable |
| --- | --- | --- |
| Runtime evidence | T001–T004; execute T030 early on a frozen probe snapshot | Actual native events and a supported held-restore boundary |
| Durable state | T005–T008 | Schema-v2 and atomic lineage claims against agreed contracts |
| Compatibility and packaging | T023–T026 | Legacy exclusion, complete installer inventory and accurate help |

Move Luna's implementation capacity to lifecycle integration as soon as the
runtime contract is established. Resolve uncertainty with Astra rather than
building competing lifecycle implementations.

## Ordered exit gates

1. **Establish runtime feasibility first.** Run the selected-runtime controls
   in [live-validation.md](live-validation.md), using the declared execution
   environment and its exact SDK-selected CLI, version and full digest.
   Demonstrate the positive orphan-wake control, then supported terminal
   stop/state clearing and held parent restore without wake or model dispatch.
   Missing credentials or a failed model request is not proof of no dispatch.
   Record a support decision before expanding controller work. If the runtime
   cannot meet this contract, Astra identifies a supported runtime path or
   raises a governed scope decision; do not ship the old independent-worker
   design as this feature. Unsupported paths must refuse explicitly.

2. **Complete one public swap path.** Integrate T009–T014 through the actual
   CLI/socket/daemon/controller boundary with temporary state and a fake
   runtime first: admitted native child → fence → proven child/tool stop →
   old writer excluded → exact parent restored under the target account,
   held. Use the same path later for live validation. Demonstrate refusal
   with claims retained when stop, identity or external effects are uncertain.
   Centralize fixture migration around the approved native contract; separate
   obsolete prototype expectations from real implementation defects. Review
   weakened assertions and restore meaningful bounds and precise outcomes.

3. **Close the remaining behavior.** Finish T015–T022 against that integrated
   path: explicit release, observed continuation or correlated at-most-once
   restart, bounded supervision, ctx and checkpoint-only handoff. Prove retry
   and crash recovery cannot duplicate writers or replay completed work.
   Account for all requirements in the same feature; narrowing scope requires
   a recorded governance decision rather than silently skipping tasks.

4. **Freeze and validate the candidate.** One executor runs T027–T029 using
   the canonical wrapper, with the pinned submodule present. Preserve JUnit
   results and source hashes. Run the expensive legacy selector after its
   fixes freeze, then the full serialized suite; rerun affected checks after
   fixes and ensure final evidence describes the final candidate. Verify
   platform CI, Bash 3.2 compatibility and installer inventory. Complete
   T031's authenticated gates only in explicitly authorized disposable
   profiles/lane, then reconcile every FR/SC under T032. No live-support claim
   may be based only on fake-runtime tests.

5. **Install a canary, then roll out.** Review and merge the verified feature.
   This repository deploys installed commands and skills through
   `openRepoTools --install`. First exercise the complete installer in
   disposable directories; isolating only the bin directory is insufficient
   because it also places skills, commands and settings. Install the exact
   reviewed merge revision into the approved canary scope and verify installed
   file hashes, command resolution, help, managed swap/release and legacy
   behavior. Expand only after the canary evidence passes. Record revision,
   installation scope, runtime digest and validation result as deployment
   evidence; a merge alone is not deployment.

## Concurrency and turnaround

Parallelize implementation and small focused tests, with at most two focused
test processes initially and one test coordinator. The existing opt-in
`tests/run.sh --parallel-safe` isolates ambient paths but does not cap resource
use. Two short passing runs do not prove that heavyweight suites can safely
overlap. Keep legacy/full suites serialized and avoid launching focused jobs
beside them. Stop increasing concurrency if durations or timeouts worsen.
Retain the canonical guard; do not bypass it with direct pytest invocations.

Use a failure census to fix shared contract/fixture causes once, rather than
rerunning the whole suite after every assertion edit. Do not loosen tests to
match incomplete behavior. Record task completion only with relevant evidence.

## Release scope and rollback

Before authenticated execution, name the disposable source/target profiles,
lane and permitted effects. Before installation, name the canary destination
and affected configuration. Existing sessions are outside that scope. Obtain
any missing authorization against this concrete scope after preparation.

Retain the last known-good installed inventory and affected configuration.
If a canary fails, preserve its journal and claims, fence/quiesce managed work,
and restore compatible tooling/configuration through the supported installer
path. Do not clear ownership records, downgrade schema-v2 state or resume an
old runtime merely to make rollback appear successful. If the previous
release cannot interpret that state, leave managed operations disabled and
recover with compatible tooling. Prove this procedure in the disposable
installation before rollout.

The next useful scheduling checkpoint is the Gate 0 result plus the native
integration failure census. Until then, a deployment date would hide the
largest uncertainty. Report gates completed, tasks with evidence and the next
blocking dependency instead of an unsupported percentage.

## Superseded dedicated-container delivery plan (September 26)

This section preserves the earlier plan as history. Its Docker-only target,
host prerequisites and forced-stop directions are superseded by the current
shared-container plan above and must not be executed for this capability.

[Speckit tasks T052–T057](tasks.md) remain the sole implementation checklist;
this is their dependency and release sequence. The
[historical Docker contract](contracts/historical-docker-source-container.md) defines
acceptance. Astra owns architecture, Sol High orchestration and evidence,
and Luna Max implementation, using Codex models in this execution.

**Delivery target:** one explicitly supported Linux Docker configuration in
which a lane keeps its admitted shell jobs and files while a replacement
Claude runtime resumes its exact parent session under another profile.
Native children continue through that parent; background Claude tasks are
disabled. Initial release is opt-in. Unsupported configurations refuse before
disrupting A. This milestone does not declare the whole older feature complete.

Start with the observed local Linux Engine 29.6.2/cgroupfs/cgroup-v2 topology
and pinned Claude 2.1.283 candidate; record the remaining kernel, image and
policy bindings before testing. These version observations are not certification.

**Current evidence:** T052 documentation and T053 private ledger are complete;
T054–T057 remain open. The latest private provider/adapter/runner focused gate
passed 44 offline tests. A model-free host-namespace helper retained a custom cgroup parent,
observed a detached source writer stop, and observed an outside job continue.
It did not use the production broker or an admitted persistent job. The
earlier seat-move probe used a scratch controller. Neither establishes the
integrated capability. The full repository suite has unresolved recorded
failures; see [verification.md](verification.md). Historical SDK/PGID results
remain INCONCLUSIVE.

The current implementation adds a private Engine transport/adapter, host
custody candidate, read-only host preflight, and a T053-backed runner whose
OS job domain is an injected trusted interface. No authenticated host IPC,
concrete job-cgroup process backend, waiting-entrypoint release, admitted
Engine exec path, or production supervisor/CLI bridge is implemented. The
controller cannot attest the Engine host: its cgroup mount is read-only, and
the Docker socket's peer PID is not visible even in the attempted disposable
host-namespace helper. The operator must identify where this Engine runs and
the service boundary available there before a production broker can be
placed. Retaining the private parent in the helper does not resolve that
authority gap.

The pinned CLI's restricted mode ignores user/project/local customization.
An isolated fake-API diagnostic found that an explicit local plugin loads one
namespaced command; typing `/swap` was normalized to `/swap:swap` and a
`UserPromptExpansion` hook matching `swap:swap` blocked before any fake API
request. A matcher for `swap` alone missed and caused eight fake API retries.
The event exposes the normalized prompt, not independently attested raw
keystrokes. This is CLI mechanism evidence only, not an installed, authenticated
or exhausted-quota `/swap` route. Preserve the external local control entry
until the complete command and failure behavior pass the T055 gates.

### Dependency order and evidence gates

| Order / task | Deliverable | Required evidence before advancing |
| --- | --- | --- |
| 1 — T054 feasibility; T055 runner prerequisite | Trusted Engine-host broker, real Docker adapter, retained source parent and minimal production job runner backed by T053 | On the selected host, an admitted job survives source exclusion with its identity/output intact; the source domain becomes empty and retired-generation restart attempts refuse. |
| 2 — finish T054; integrate T055 | All managed mutation paths fenced; scoped MCP job tools; pinned Claude launcher; model-free prepare, reconciliation and explicit release | Production components pass the model-free integrated path and reject missing evidence. CLI launch/tool-policy observations are recorded separately from simulated behavior. |
| 3 — T056 | Deterministic fault matrix over the integrated controller and production OS components | Each fault has an expected refusal, retained uncertainty or successful recovery; launch counters, history and resource reservations support the result. |
| 4 — T057 before merge | Frozen candidate, review, green regression/CI, isolated install and rollback rehearsal | Exact revision and complete installed inventory recorded; public activation still disabled. |
| 5 — T057 canary and rollout | Install the reviewed merge revision into the named canary scope; run the authorized account transition | Actual parent/account and native-child continuation, surviving job result, no duplicate launch, no late A effects, preserved files. Enable only the measured configuration after PASS. |

**Runner dependency:** T054 cannot close with the scratch outside process.
Implement T055's minimal supervisor job runner early, alongside the T054
broker, and reuse that runner in MCP integration. This scheduling overlap
does not complete T055 or introduce another implementation task list.

### First implementation slice and feasibility decisions

Preserve the dirty worktree and private evidence. Astra first reviews the
broker's Engine-host identity, authentication, privileges and parent-cgroup
lifecycle. Sol maps every managed create/start/exec/unpause/update/restart,
recovery and replacement path to the durable fence. Luna then implements one
bounded path: provision an empty parent, journal creation, start the waiting
entrypoint, attest actual membership, run a source writer, fence and stop A,
and observe `populated 0` through the same retained parent while a T053-admitted
job continues outside it. Include reparenting/`setsid` and an admitted Engine
exec task. Source-domain configuration and escape checks remain mandatory.

Resolve these feasibility questions before expanding the integration:

- Can a production host service retain and authenticate the witness on this
  Engine host? The current controller's namespace cannot see host PIDs.
  Record install/startup/restart/empty-parent disposal authority. The temporary
  privileged cleanup helper is not a production design. Broker restart must
  either re-establish custody under the contract or retain uncertainty; a new
  empty parent with the same path is not recovery evidence.
- Can the pinned CLI expose the required effective parent/child tool policy
  and exact-session/account observations? Test what the installed binary
  exposes before relying on flags in `lane_managed_claude_launch.py`. Defer
  observations requiring authentication to the scoped canary and identify
  them explicitly. Do not fill missing observations with a supplied manifest.
- Can `/swap` reach the supervisor without a model turn, including exhausted
  quota? Specify and test the actual CLI integration and an external local
  control entry for an unresponsive CLI. A model-expanded slash prompt does
  not satisfy this requirement. An unsupported in-CLI route needs a recorded
  product decision before claiming `/swap` is delivered.

If a required observation is unavailable, record that specific capability
gap before another full run. Do not repeatedly rerun unchanged probes or
weaken acceptance to obtain PASS.

### T055 integration and T056 fault coverage

Use the same admitted source launcher from initial lane entry onward; a live
unmanaged CLI cannot be adopted retrospectively. Keep the supervisor/job
domain outside A. Expose authenticated `run/status/output/wait/cancel` through
one MCP bridge with a generation-scoped credential. Check registration and
resource reservations for file tools as well as job launches: B and its
children cannot edit a live job's reserved resources. Jobs may still write
at readiness, so dirty/untracked inventories must identify their observation
point and reservations rather than claim a stable filesystem snapshot.

Route early `/swap`, natural CLI completion after wrap-up and forced stop
into the same prepare/exclude/reconcile/release transaction. Preparation must
work without quota or a final handoff message. Specify bounded command/IPC
deadlines and the observation-only recovery action for each timeout. Existing
supervised jobs continue independently; stop or result-delivery uncertainty
cannot trigger job replay.

T056 covers two foreground native-child histories, completed versus unfinished
children, multiple registered dirty/untracked worktrees, conflicting file
writes, graceful and incomplete wrap-up, a late complete A response, competing
B owners, wrong parent/profile, stale generation, broker reload, daemon loss,
lost ACK and crashes around admission, spawn, exclusion, release, startup and
result delivery. Measure dispatch counts and identities. The guarantee is
at-most-once dispatch with explicit uncertainty; arbitrary shell commands do
not acquire an exactly-once external-effect guarantee.

### Test layers and result recording

| Layer | What it establishes | What remains for later |
| --- | --- | --- |
| Offline `tests/run.sh` selectors | Ledger, protocol, fault handling and simulated CLI histories/responses | Actual Docker exclusion and actual Claude behavior |
| Explicit model-free OS integration | Production broker/runner, host membership, source stop, surviving jobs and restart denial | Authenticated resume, child continuation and real account identity |
| Installed authenticated canary | Actual pinned Claude and account transition through the production route | Support for any untested runtime or host configuration |

Keep privileged Docker fixtures explicit and isolated from the default offline
suite. Sol is the test executor. Use serialized `tests/run.sh` for code tests;
host tests were authorized for this checkout. Initialize the pinned submodule
for the full gate. Review the existing failure census early, fix shared causes,
and run affected selectors before the final full suite. A focused pass or a
documented baseline failure cannot substitute for the required full-suite pass.
Preserve existing platform CI; portable command checks do not certify the
Linux Docker provider on other platforms.

Each run records task, exact source revision or file-hash manifest, runtime
and host configuration, fixture, bounded actions/deadlines, expected assertions,
actual observations, outcome and artifact digests in `verification.md`.
Keep credentials and transcript bodies private. PASS requires every declared
assertion; a verified violation is FAIL; missing evidence is INCONCLUSIVE.
A negative case passes when its expected refusal is observed, but does not
establish successful recovery. Before retrying, name the defect or missing
evidence, the correction and the focused check proving it. Relevant changes
invalidate the affected gate's evidence.

Implementation checkpoints may precede the canary; acceptance claims that need
actual Claude behavior stay open until that runtime evidence exists. Check off
each Speckit task only against its full criteria, not its scheduling row here.

### T057 merge, installation and rollout

First complete review, regression, strict OpenSpec validation and applicable
CI on the frozen candidate, and rehearse installation/rollback in isolated
destinations. Resolve shared lifecycle/claim changes against the merge base,
including the recorded unenroll prerequisite, before landing. Merge the code
with public activation disabled; the authenticated canary is the subsequent
activation gate, so it is not a circular prerequisite for that merge.

Use a clean checkout of the merge revision and its own installer:
`OPENREPOTOOLS_REF=<merge-sha> ./openRepoTools --install`. Verify the exact
commands, Python modules, skills, hooks, settings, host service and pinned
image/runtime artifacts required by the new route. Isolate configuration and
service destinations as well as the bin directory during rehearsal. Produce
the concrete lane-entry, `/swap`, status, release and recovery commands in
`quickstart.md`; its current historical examples are not this capability.
Any merge-time change requires the affected validation again.

After a passing installed canary, record the supported host/Engine/cgroup
driver/CLI/image/configuration tuple and enable only its explicit opt-in route.
Record installed hashes, activation scope and operator instructions. Keep
unsupported hosts rejected. T057 closes only with that deployment evidence;
archive the broader OpenSpec change only when all of its governed work has
landed or been explicitly dispositioned.

Rollback first disables new admissions and target launches while keeping
compatible supervisor/job control available. Preserve the current jobs,
journals, claims, reservations and source evidence. Restore the previous
inventory only if it can read that durable state; otherwise retain compatible
recovery tooling with activation disabled. Rehearse this with a live job and
an indeterminate operation. Rollback must not clear claims, restart A or
reset files. Disposal of retained sources and empty cgroup parents is a
separately scoped operation after evidence and effects are reconciled.

### Seat movement and installed canary

Keep seats unchanged during T054–T056. Before the T057 canary, bind one
disposable lane, source profile A, target profile B, permitted file/job effects,
installation destinations and a bounded run scope. Prepare the concrete
commands and evidence collector before obtaining any missing live authorization;
previous seat-move approvals are not an open-ended retry allowance.

1. Start A through the managed launcher. Register worktrees, preserve deliberate
   dirty/untracked fixtures, save two foreground child histories and admit one
   continuing job with a unique marker and launch counter. Record which child
   is complete and which is eligible for explicit continuation.
2. Trigger early `/swap`; reaching a real usage limit is unnecessary for this
   canary. T056 separately tests completed/incomplete wrap-up control paths;
   simulated wrap-up does not certify the service's allowance behavior.
3. Wait for durable `ready-to-resume`: A is excluded, its restart fence holds,
   histories and effects are reconciled, job reservations persist and B is
   absent. Only then tell the operator to move the seat from A to B once.
4. After operator confirmation, revalidate the witness and ownership and
   explicitly release one exact-parent B launch. No target model preflight
   occurs during preparation. A delay or failed access check leaves the lane
   waiting or indeterminate; it does not authorize another launch.
   Attach to the returned target-starting custodian for the exact fresh trust
   dialog, then use `observe-target` until that same launch's SessionStart is
   authenticated and B input is admitted. A lost release response uses this
   observation path; it never triggers a second launch.
5. Verify actual parent/account identity and native continuation of the eligible
   child; the completed child is not relaunched. B reads the original job's
   result without restarting it. Check launch counts, saved history prefixes,
   dirty/untracked files, reservations and absence of late A writes/dispatch.
   Capture evidence before any permitted cleanup.

On FAIL or INCONCLUSIVE, leave activation disabled and preserve recovery state.
A further account test follows a diagnosed correction and a scoped authorization.
