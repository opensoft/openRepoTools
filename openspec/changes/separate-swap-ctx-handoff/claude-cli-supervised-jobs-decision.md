# Claude CLI account recovery with persistent supervised jobs

## Authority and scope

On September 25 Brett requested the prospective Claude CLI runtime boundary,
persistent L1 jobs, durable single-owner fence and two-phase stop-then-resume
protocol. On September 26 he clarified that many independent Claude CLI
sessions share the container and **the container must stay running**. This
amendment supersedes the dedicated-container delivery choice for
`claude-cli-supervised-jobs-v1`. The sole implementation feature remains
`001-separate-swap-ctx-handoff`; its `tasks.md` owns executable tasks. Astra
remains architecture lead. Under the current team assignment, Sol High is the
orchestration lead and Luna Max is the implementation writer for the defined
Speckit tasks. Use the active agent platform's models at appropriate effort.

The September 30, 2026 ruling authorizes this documentation amendment and its
documentation-only checkpoint before further T054/T055 code. It does not
authorize a canary run, account seat movement, merge or deployment. This
supersedes earlier deployment authorization language below. T052 documentation
and T053 private-ledger evidence remain recorded; T054–T057 remain open.
Existing strict and original SDK/PGID v1 records retain their validators and
meaning. Missing or unknown capability markers do not select this capability.

## October 3 direction: retain swap and add broker mode

The follow-up directs reuse of the existing CPC omniWorker and
codexFactory/openxFactory execution rail. LS supplies lane-facing delegation,
stable task/result attachment and exact parent custody/swap correlation; existing factory
governance, worker registration, dispatch and result enforcement keep their
authority. The [integration contract](../../../specs/001-separate-swap-ctx-handoff/contracts/lane-task-broker.md#existing-factory-worker-rail-is-the-first-adapter)
records the observed one-shot patch worker, declared coder/worktree pools and
the pending `coding` clearing admission. T059–T062 consume admitted surfaces
and extend their owning components for measured gaps. A direct Omnigent API
call cannot create a second route around factory admission.

Brett selected two operating modes. Ordinary swap retains this qualified
native-child/per-session contract. Broker mode keeps the main agent doing
primary orchestration while lane-facing delegation passes through LS into the
factory rail. Omnigent's worker-management layer owns worker workload,
authorized account/model/harness/host placement, estimated allowance admission
and qualified worker recovery. Workers return results through LS and have
independent runtimes; this does not add cross-account native Agent spawning.

LS transfers A to B while independent workers continue; it moves their task
consumer binding and buffers/deduplicates results, without moving worker
accounts or redispatching work. Omnigent may replace worker attempts behind
the same logical factory task ID only after its execution-site safety boundary
is qualified. Prefer small tasks and an account with enough estimated allowance
plus reserve; actual consumption can exceed the estimate. Source inspection
found lifecycle/resume primitives, but not a complete safe worker account-swap
controller or subscription-allowance selector. These remain owning extensions.

Remote custodian evidence must establish worker ownership/exit; loss of contact
cannot justify duplicate work. Persistent commands belong to the worker site's
EGS, not automatically A's local EGS; bind site/supervisor/incarnation/job IDs.
Reuse Omnigent mechanisms after adapter/build qualification, preserving local
parent JSON/custody authority and existing factory governance. See the prospective
[broker contract](../../../specs/001-separate-swap-ctx-handoff/contracts/lane-task-broker.md)
and T059–T062. Broker work does not change T054–T057's scope or status.

## October 3 decision: service-owned worktree inventory

The October 3 worktree-inventory amendment incorporates PR #97's diagnostic
capability into this service's reconciliation. The managed JSON ledger remains
the sole lifecycle/readiness authority; historical recovery state does not
authorize release. The [inventory contract](../../../specs/001-separate-swap-ctx-handoff/contracts/claude-cli-supervised-jobs.md#worktree-inventory-integration)
and T055–T056 govern the adapter and its evidence. This documentation decision
does not decide PR #97's landing or grant new runtime/deployment authorization.

## October 3 preferred default: one Speckit task per implementation child

Brett agreed to prefer one Speckit task per implementation subagent run.
Multiple children may contribute to the same task with explicit roles and
file boundaries. Split tasks by small, independently verifiable deliverables
and acceptance criteria, supporting the intended Sonnet assignments. Record
bounded exceptions with task IDs and reasons; cross-task support work may have
its own review task or an explicit related-task set. The default is workflow
guidance, not a lane-swap prerequisite or a restriction on every agent role.

A supplies the semantic assignment. The lanes service persists its scope,
attempt, runtime identity joins, files/worktree, jobs and evidence references
as work proceeds. Speckit task IDs and runtime task IDs remain distinct.
Child termination is not task acceptance. The startup review set includes
tasks with unverified changes or outstanding jobs, including recently returned
children, plus parent edits and unmatched work. B checks acceptance evidence,
preserves verified completion and existing EGS jobs, and creates fresh children
only for safely accounted unfinished work. An assignment list alone cannot
prove complete attribution or safe source exclusion.

See the [contract](../../../specs/001-separate-swap-ctx-handoff/contracts/claude-cli-supervised-jobs.md#speckit-task-assignment-and-recovery)
and [rationale](../../../ideation/brainstorm/speckit-task-recovery-overview.md).
T055–T056 remain implementation and verification work. Hard-stop review informs
the future forced-recovery gate; first delivery retains its idle/exit witness.

## Staged named-lane deployment

The canary source and target profiles are selected by the operator when a
canary is separately authorized. `team05d` and `team05j` are the current
expectation only. Record the operative pair in the durable lane ledger before
any seat movement, and include that concrete pair in T056's runtime evidence.
The September 30 ruling authorizes none of those actions. A future installed
canary still requires a frozen inventory, passing shared-session route and
dependency checks, measured CLI/fault evidence, isolated installation and
rollback evidence, and separate authorization. No default or global activation
is included.

Run and retain the full canonical regression census. Native `ctx` adoption and
child-restoration acceptance tests remain open requirements: their positive
assertions must not be removed, skipped or rewritten to manufacture a pass.
Only failures individually demonstrated to belong to the unreachable,
explicitly refused native-`ctx` route may remain outside this staged gate.
Any shared-route/dependency regression, unexplained failure or changed refusal
boundary blocks the named-lane installation. Report the full-suite result
honestly alongside the scoped result. T057, general rollout, repository release
and feature completion retain their full-regression/CI gates and remain open.

## Shared container, separate session lifetimes

The source A and unrelated session C run in the same long-lived container.
Swapping A must not stop, kill, restart or replace that container, signal all
processes for its user, or kill a shared process group. No host Docker broker,
privileged cgroup access or supervisor move to WSL is a prerequisite of this
path. The supervisor may remain in the container provided its lifetime and
admitted jobs are independent of A's CLI and terminal lifecycle.

Persistent work is admitted before launch by the supervisor with stable job
identity, result custody and resource reservations. It survives A's exit and
B's account change. Native foreground children retain the exact parent's
conversation history; they are not persistent OS jobs or separately logged-in
CLI sessions. Unknown detached descendants are not adopted as jobs.

The earlier Docker provider code, probes and evidence remain a dormant,
superseded candidate. Its contract is preserved as
[historical dedicated-container design](../../../specs/001-separate-swap-ctx-handoff/contracts/historical-docker-source-container.md).
It supplies neither the current topology nor certification for shared-session
exit. Nothing in this amendment installs or activates it.

## October 2 ruling: no source model headroom dependency

Brett's October 2 inspection conclusion is adopted: the native wrap-up
allowance cannot be the shutdown budget for this system. Swap safety and
state reconstruction must work from durable service/runtime records when A
has zero model tokens available and produces no final handoff. Optional
cooperative wrap-up can improve context, but neither its availability nor a
successful final response is a readiness condition.

[Anthropic's allowance documentation](https://support.claude.com/en/articles/17040437-claude-code-wrap-up-allowance)
describes capped, discretionary usage charged to the weekly quota. It applies
to a response already in progress, not a new message after exhaustion, and
may be insufficient to finish work. It provides no shutdown budget the lanes
service can reserve. The October 2 ordinary-lane observation is recorded in
the [verification record](../../../specs/001-separate-swap-ctx-handoff/verification.md);
it does not qualify the managed provider or establish whether allowance was
unavailable or consumed.

Consume fresh profile-keyed usage observations directly in the service,
independently of user prompts, so an early request does not depend on the AI
reading a warning. Keep native child task definitions, lifecycle/output
references and admitted-job/effect records durably as work proceeds. Refresh
the filesystem inventory during reconciliation; no final source summary is
required to assemble B's transition packet. At known exhaustion, skip the
optional Stop-hook block and request no additional source model turn. If
exhaustion occurs during optional wrap-up, use the already recorded evidence
without a retry or a requirement to finish the handoff.

Zero headroom does not authorize an unsafe takeover. This graceful-only
delivery still needs a verified idle boundary, exact CLI exit, descendant
drain and accounted effects. A busy source waits within its deadline; missing
evidence or timeout retains claims and keeps B absent. Failed child responses
are unfinished or unknown tasks, not successful shutdown checkpoints. Safely
accounted unfinished work is reconstructed under B with new child IDs.

### Record whether startup repair is required

Brett's October 2 follow-up keeps two transfer outcomes. The service seals a
`handoff` sub-record in the authoritative JSON ledger, bound to this operation,
exact parent and source/target generations. `outcome: clean` means the
cooperative checkpoint completed before exhaustion and the service verified
the checkpoint, child task dispositions, job references and source exit/history
reconciliation. `outcome: repair-required` covers exhaustion before or during
that checkpoint, a missing checkpoint, unreconciled child failure or an
incomplete cooperative handoff. Failed child work already reconciled into an
explicit continuation plan does not by itself require extra repair. No positive
evidence means repair is required; A saying "done" cannot set the marker.

Both outcomes require the same source exclusion and ownership proof before B
starts. Unaccounted processes or effects still block B; startup repair cannot
substitute for that proof. A clean outcome does not mean every task finished,
Git is clean or admitted jobs stopped. Safely unfinished work must have an
explicit continuation plan, and continuing jobs retain their identities.

Include the outcome, reasons, checkpoint/evidence references and a bounded
repair list in B's transition packet before its first turn. For `clean`, B
checks the current service packet and follows the accounted continuation plan.
For `repair-required`, the service performs deterministic reconciliation and
permitted service-artifact cleanup first; B uses its new account for any
remaining semantic repair of assignments and progress before normal work.
Observe existing jobs, preserve user files, and start new child IDs only for
safely accounted unfinished tasks. Record repair completion separately; never
rewrite the original transfer as clean. A missing marker in an otherwise valid
packet requires repair. A stale or contradictory operation/generation binding
is invalid and cannot authorize startup.

## Normal path: optional foreground wrap-up, then actual CLI exit

A stays the sole owner during optional bounded foreground wrap-up. Any native
allowance is incidental; no source headroom is assumed. A final model response,
quota notice, completed turn or return to the prompt does not mean the CLI exited. After
foreground work reaches a supported stopping point, the launcher observes
actual exit of the exact admitted CLI through its owned child handle or
namespace/start-token identity and durable launch journal.

This first delivery supports graceful exit only. When the service has a pending
wrap-up request for this exact parent before known exhaustion, its registered
`Stop` hook may return
`{"decision":"block","reason":"<wrap-up instruction>"}` once for that
request ID. Persist deduplication across duplicate callbacks and service
restarts; this wrap-up request precedes durable control entry. The instruction
is: do not start new agents or long work, record state in the handoff, then
stop. Foreground-only children do not run at a
`Stop` boundary, so shutting down subagents is vacuous. Deduplicate by request
ID, honor `stop_hook_active`, and treat hook errors as no wrap-up. A blocked
`Stop` continues A's turn and is not exit evidence.

After optional wrap-up, or without it, fence relayed keyboard input to A until
its CLI has exited. Send
SIGTERM only to the exact admitted CLI PID through its owned child handle under
the subreaper custodian, and only after a verified idle boundary: a nonblocked
terminal `Stop` or `StopFailure` with no later `UserPromptSubmit`. Observe the
main process with the custodian's wait and require its `ECHILD` witness.
`SessionEnd` corroborates shutdown but is not the witness. If measurement shows
SIGTERM unsupported, the last-resort fallback is one atomic `/exit` PTY write
including carriage return, followed by a bounded wait for exit, `SessionEnd`,
or `Stop`. No observed change by the deadline is a refusal that retains claims;
do not retry. The pinned foreground tool policy and observed CLI/helper/child
lifecycles must account for all source activity, saved parent/child histories
and possible effects. Parent PID death, process silence, a process-group sample
or a host PID scan cannot certify unknown descendants. Refused exit, lost
runtime identity, an escaped or unaccounted child, incomplete journal or
uncertain effects blocks readiness and B. Forced per-session recovery is a
separate future gated mechanism; do not invent an automatic escalation or fall
back to container termination.

### Account-limit signals and native-child reconciliation

The shared container is never a stop target. The lanes service owns one
operation per lane and asks that lane's execution-group supervisor to manage
only its exact Claude CLI process tree. Other lanes, their profiles and the
supervisor's admitted jobs remain running in the same container. A retains
its source-account credentials until its exact CLI exits; B is a new CLI
launched with the target profile.

Before exhaustion, the service may record a pending swap request and ask A
at a verified turn boundary for bounded cooperative wrap-up. A remains the
controller while its foreground children finish or reach stopping points.
The service then fences new admissions and enters the durable stop operation.
A's reply is useful context, never proof that a child finished or the CLI
exited. If quota expires during wrap-up, the operation continues from its
recorded state without another request to A. At or after exhaustion, no
model response from A is required by the service. A source-bound
`StopFailure` with `error: rate_limit` is a structured failure signal; a
fresh profile-keyed status-line sample can trigger an earlier request.
workBenches already publishes that profile-keyed sample, but its current
95% guard only prints a prompt-directed handoff instruction; the lanes
service still needs to consume the sample directly and deduplicate requests.
Rate-limit text in the verified tmux pane is corroborating diagnostic input,
not a completion or takeover witness. Claude's possible five-hour-limit
wrap-up allowance is observed opportunistically, never assumed.

The current candidate has parent `SessionStart`, `UserPromptSubmit`, `Stop` and
`StopFailure` hooks. Add `SubagentStart` and `SubagentStop` observations tied to
the exact parent, source generation, native agent ID and initiating Agent tool
call. Reconcile the roster with Agent tool events, child transcript/sidecar
identities, parent results, supervisor process custody and admitted job/effect
records. A child stop means its response ended; task success, interrupted work
and unsettled effects are distinct dispositions. Missing or conflicting
evidence is `unknown`, never inferred clean. Defer the measured fail-closed
**mid-turn Agent admission fence** to a future gate beside forced recovery;
T054–T057 neither depend on nor test it. For first delivery, finish foreground
Agent calls and any wrap-up continuation, then seal the child roster only at a
verified nonblocked terminal `Stop` or `StopFailure` with no later
`UserPromptSubmit`. Foreground children have returned by that boundary. A busy
request remains pending until the idle boundary or reaches its bounded
refusal. The custodian fences relayed input and uses the headless exit path.
`SubagentStart` alone remains observational and cannot block a racing spawn;
first-delivery behavior does not rely on it doing so.

After exact A exit and full process/effect reconciliation, the service can
authorize one exact-parent B resume. Only the coordinator conversation is
resumed. A's native subagents ended with A's CLI; their old IDs and transcripts
are evidence for reconstruction, not execution handles to resume. Finished
children stay finished. For each unfinished, safely accounted child, the
service records `restart-pending` with its task, definition, proven output,
worktree and job references. After B receives the transition packet, B starts
a NEW native child with a new ID on the target account and the service links
old and new IDs without claiming exact child continuation. If A remains live,
or any child or effect cannot be accounted for, B remains absent under the
initial graceful capability. A future forced per-session recovery requires
its own gate.

The service records a bounded Git/worktree inventory and admitted-job state
at a named observation watermark, then refreshes them before B's first model
turn. A service-authored transition packet gives B the exact parent and
operation, child dispositions, job IDs/results/reservations, dirty and
untracked path inventory, changes since A's last observation and unresolved
facts. Deliver it through the managed `SessionStart` context or an
authenticated manager endpoint; label file observations provisional while
an admitted job may still write. Cleanup may remove only verified
service-owned temporary artifacts and stale references. It never resets,
commits, deletes, rewrites or replays lane work. A separately credentialed AI
API may summarize the packet, but deterministic service evidence alone
decides exit, completion, ownership and release.

Every long-running or external command requested by a managed lane follows
`lane -> MCP bridge -> lanes service -> execution-group supervisor`. Native
Edit, Write and NotebookEdit remain native tool calls. The lanes service checks
lane identity, owner generation, operation fence, worktree reservation and
request ID, journals the admission, then forwards external commands. The
execution-group supervisor starts or observes the OS job and retains its
process, output and result across A's exit and B's start. Status, output, wait
and cancellation return through the same service; the Claude process has no
direct execution-group control socket. An already admitted job may continue
while the lane's new dispatch is fenced. The present prototype connects its
MCP bridge directly to a per-lane job-supervisor socket, so this service
gateway and its no-bypass tests are still required before activation.

## Durable ownership and isolated launch configuration

The launcher claims the exact parent/lane/generation before A is spawned and
serializes every managed creation, adoption, restart, recovery and B release
against that claim. Binding includes source runtime incarnation, namespace and
start identity, launcher journal, exact parent UUID, profile and immutable
launch manifest. A PID or session title alone is insufficient. Duplicate source
admissions and competing targets refuse before spawn. A durable retired-source
fence survives launcher/supervisor restart; missing journal evidence is
indeterminate, never a reason to create a replacement.

A and B use runtime-specific immutable settings, MCP configuration and
profile/auth references; no overwrite of a shared configuration path or broad
credential/environment mutation may affect C. Supervisor authority remains
separate from each source-generation credential. Admitted job actions check
owner generation and resource reservations. Native edits do not consult job
reservations. The source cannot obtain
runtime-creation or owner-transfer authority through the job endpoint.

The pinned CLI policy keeps native children foreground and disables native
background tasks/agent view. Native Edit, Write and NotebookEdit are allowed:
they complete within their tool calls and cannot outlive A. Deny exactly Bash
and PowerShell. Persistent and long-running external commands continue through
the lane's MCP bridge, the lanes service and the execution-group supervisor.
The background-task flag keeps a native-child SendMessage reply awaited inline.
`CLAUDE_CODE_HARBOR_KITE=0` disables cross-session routing;
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0` and omission of `--agent-teams`
disable teammate routing. A native edit cannot consult an admitted job's
reservation; normal-operation concurrency between a parent native edit and an
admitted job is outside this feature. During the swap window, the source input
fence and verified exit witness close that overlap. A job's conflicting-write
refusal is enforced against the worktree reservation. Effective policy and
lifecycle behavior require measurement on the actual pinned CLI; launch flags
and hooks alone establish no capability.

### Pinned CLI measurements required before dependence

The npm-global Claude CLI binary currently reports version `2.1.286`. Before
T055 code depends on these behaviors, measure them on the pinned CLI and record
the exact binary/version tuple:

- A parent `StopFailure` fires with `error: rate_limit`.
- A `Stop` hook returning `decision: block` continues the turn with its reason.
- SIGTERM at an idle prompt runs the CLI's own shutdown and fires `SessionEnd`.
- `SessionStart` on `--resume` carries the injected transition-packet context.
- The parent's `Stop` hook is absent while a foreground Agent call remains in flight.

Until each behavior is measured, no T055 path may assume it. In particular,
the expected hook and signal behavior does not establish an exit witness by
itself.

## State repository and project identity

The September 26 resumed implementation resolves the state/project identity
ambiguity using the existing claim fields. `lanes-edit.sh workspace-root`
authoritatively identifies the WIP state repository. `common_dir` in managed
state, native claims and the supervised-jobs ledger remains that repository's
Git common directory; it anchors ownership, locking and the global claim
index. It is not the project being edited.

For this CLI capability, a workspace claim's `repository` is the independently
observed project Git common directory, and `workspace` is its registered Git
worktree root. The control service resolves both strictly from the explicit
launch directory before enrollment and source admission. The launch directory
may be inside that root. Non-Git paths, unresolved identities and bare
repositories refuse; the generic claim helper's fallback to a path supplies
no CLI admission authority. History reconciliation re-observes the registered
Git root and compares its project common directory with `repository`, while
state/owner checks continue comparing `common_dir` with the WIP identity.

Both identities already participate in the complete claim digest and resource
ID. Keep their checks and cross-lane overlap arbitration; do not relocate the
state store, manufacture workspace-helper output or reinterpret old schemas.
No automatic record migration is needed or allowed. A persisted claim whose
project identity cannot be verified blocks this capability; preserve the
claim, jobs and fences instead of rewriting it during recovery.

The assembly root is an additional lane identity; it does not replace the WIP
`common_dir` or `workspace` fields above. Resolve it from the worktree's
`project.yaml` entry whose `legs[].role` is `assembly`, falling back to the
aggregation's `project-register.yaml`. A single-repository project without
`project.yaml` uses its root as the assembly root; `openRepoTools` is this
shape.

### Native history location

Claude Code owns the transcript in its projects store; the service ledger
records a durable pointer. Add a transcript sub-record to the exact-parent
binding with profile family, resolved store path, encoded project key, parent
UUID, full parent transcript path, size, SHA-256 at seal time, and the complete
child transcript and metadata sidecar list. The project key is the encoded
launch cwd (for example, `-workspace` when launched from `/workspace`), not
the lane directory. Preserve the `history_manifest` resolver's
`projects_store`, project and source-cwd observations, and parent/child
digests. Seal the manifest after source exit and descendant drain, and
reverify it at release. Transcript bodies remain in Claude Code's store, not
the ledger.

Before release, compare resolved source and target projects-store identities.
Same-store transitions need no copy. If the identities differ, copy the parent
transcript and child sidecars into the target store while preserving their
relative layout, then verify the recorded digests before launch. The profile
resolver currently rejects duplicate same-family copies across stores; T055
must permit only the ledger-bound retired source plus verified target without
weakening live-holder uniqueness. The durable pointer belongs in the JSON
ledger.
The local JSON ledger under its local flock on the workstation holding the
exact PID remains the only authority. When a database URL is configured, use
QA Postgres; otherwise keep a SQLite index beside the JSON ledger. The swap
path never reads or waits for writes or reconciliation of this index, and QA
index availability is never a swap gate.
Write index updates behind JSON persistence as idempotent upserts keyed by
local record ID and digest; reconcile from JSON after an index wipe or outage.
Use a per-workstation configuration/environment that is not committed and a
service-only, schema-scoped credential distinct from supervisor authority. The
index may hold derived lane rows,
transcript pointers, swap state and job summaries. Index a `LANES.md` row only
after its projection is recorded in the local JSON ledger, so every indexed
row has a local-ledger source. It does not replace Git `LANES.md` and adds no
gate to T054–T057. T058, after T057, covers offline no-read and wiped-index
reconciliation checks.

## Prepare, reconciliation and explicit release

At the verified idle boundary after graceful foreground completion, preparation
durably fences A's generation and its keyboard input, sends SIGTERM to the
exact admitted CLI through its owned child handle, waits for the custodian's
exit and ECHILD witness, then reconciles histories, jobs, reservations and
effects. A `SessionEnd` hook only corroborates exit.
An early `/swap` can fence admissions and request only the validated graceful
exit path once graceful criteria hold; a busy transition requiring another
model turn after control entry blocks instead. B stays absent until the same
evidence is complete. The controller
initiates no new model requests. Cooperative wrap-up is A's work before control
entry; the requested handoff is context only, never proof of exit or release.

`ready-to-resume` records the exact target intent with no B process. Explicit
release revalidates exit, ownership, restart denial and reconciliation, then
persists one target launch intent before exact-parent CLI resume. Lost startup
acknowledgment retains uncertainty and prohibits another launch. A stale A
command or second B contender cannot create a job, runtime or transcript writer.
The released target's durable custodian locator is returned while startup is
pending, so an operator can answer only its exact fresh trust dialog. The
separate `observe-target` action returns the same locator until authenticated
SessionStart is present; it then adopts the same process and opens model input
after a final current-owner check. A pending nonempty prompt requires an
authenticated UserPromptSubmit begin and exact Stop/StopFailure settlement;
prompt repaint or a missing callback never clears it. `/help` and a proven
blank Enter are local terminal actions, not native model submissions.

Saved/restored context and successful model-task completion remain separate.
B may start a NEW native child for a safely unfinished task only after the
exact parent resumes and receives valid task/history and reconciled job state.
Completed children are not relaunched. Persistent jobs keep identity/output
and reservations; missing
transcript results never authorize repeating their effects.

## Concrete Linux session witness: child subreaper

Select `linux-session-subreaper-v1` as the initial per-session provider.
A single-purpose launcher wrapper sets and verifies Linux child-subreaper
status before forking A, journals source admission before permitting exec and
retains custody through release. Normal double-fork or `setsid` does not escape
its ancestry. Under this intact custody, source-main terminal status followed
by reaping all child types to `ECHILD` establishes no remaining local source
process, provided the wrapper can never spawn again. A surviving descendant
keeps the operation waiting/refused; it is not killed to obtain the witness.

The wrapper remains alive to authenticate fresh observations. Wrapper death,
unknown namespace/external-launch behavior or a missing journal breaks custody
and blocks takeover. Supervisor jobs are launched in an independent sibling
subtree. Kernel closure does not prove native history validity, task success
or remote-effect completion; those remain separate reconciliation gates.
The [provider implementation contract](../../../specs/001-separate-swap-ctx-handoff/contracts/linux-session-subreaper.md)
specifies admission, wait flags, custody, restart and integration tests.

## Evidence and implementation handoff

The [current capability contract](../../../specs/001-separate-swap-ctx-handoff/contracts/claude-cli-supervised-jobs.md)
and [delivery plan](../../../specs/001-separate-swap-ctx-handoff/deployment-plan.md)
define the T054–T057 evidence gates. The next planned fixture runs two
independent Claude sessions A and C in the same container: A wraps up with a
foreground child and exits naturally; a supervisor-admitted job retains
identity and advances output; C and the container remain running. After exit
and reconciliation, one explicit release starts B on A's exact parent, once.
Negative cases cover uncertain exit/descendants, duplicate targets, stale A
actions and launcher restart. Offline fixtures and real CLI observations must
be reported separately. No canary run, account seat movement or merge is
authorized by the September 30 documentation checkpoint. If a canary is
separately authorized later, the operator supplies the source/target pair and
the ledger records it before any seat movement.

The September 25 scratch seat-move probe observed one exact parent/native-child
continuation and surviving job, but used model preflight before release,
missed wrong-parent and duplicate-contender fences and did not prove late tool
or transcript-writer exclusion. Prior Docker probes tested a different
boundary. Neither changes T053's narrow offline result, the fourteen historical
Bite 4 outcomes, Bite 5's pending status or public support. Activation still
requires integrated runtime evidence, regression and installation/rollback
checks plus a separately authorized authenticated canary. The concrete pair
is selected by the operator at canary time, not fixed by this record.
