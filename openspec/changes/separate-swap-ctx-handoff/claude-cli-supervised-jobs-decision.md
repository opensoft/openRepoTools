# Claude CLI account recovery with persistent supervised jobs

## Authority and scope

On September 25 Brett requested the prospective Claude CLI runtime boundary,
persistent L1 jobs, durable single-owner fence and two-phase stop-then-resume
protocol. On September 26 he clarified that many independent Claude CLI
sessions share the container and **the container must stay running**. This
amendment supersedes the dedicated-container delivery choice for
`claude-cli-supervised-jobs-v1`. The sole implementation feature remains
`001-separate-swap-ctx-handoff`; its `tasks.md` owns executable tasks. Astra
remains architecture lead. The later explicit user instruction, “use astra for
thinking and sol for implementing … and deploy the lane swap”, assigns current
implementation to Sol and supersedes the earlier Luna assignment for this
tranche. Use the active agent platform's models at appropriate effort.

The latest user instruction authorizes completing implementation, validation
and deployment. The preceding document-only boundary is historical. Account
seat changes remain user-operated against the concrete named canary; deployment
does not authorize disturbing unrelated sessions, relocating services or forced
recovery. T052 documentation and
T053 private ledger evidence remain recorded; T054–T057 remain open. Existing
strict and original SDK/PGID v1 records retain their validators and meaning.
Missing or unknown capability markers do not select this capability.

## Staged named-lane deployment

The user's account-swap deployment instruction permits a versioned, opt-in
installation of this capability for the named canary lane, with source
`team05d` and target `team05j`. This stage requires a frozen installed inventory,
passing tests for the shared-session route and every dependency it invokes,
the applicable real CLI/fault evidence, isolated install/rollback evidence and
an authenticated canary through that exact route. Seat movement remains the
operator's action after verified readiness. No default or global activation
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

## Normal path: foreground wrap-up, then actual CLI exit

A stays the sole owner during optional bounded foreground wrap-up, including
a supported five-hour-limit allowance. A final model response, quota notice,
completed turn or return to the prompt does not mean the CLI exited. After
foreground work reaches a supported stopping point, the launcher observes
actual exit of the exact admitted CLI through its owned child handle or
namespace/start-token identity and durable launch journal.

This first delivery supports graceful exit only. The pinned foreground tool
policy and observed CLI/helper/child lifecycles must account for all source
activity, saved parent/child histories and possible effects. Parent PID death,
process silence, a process-group sample or a host PID scan cannot certify
unknown descendants. Refused exit, lost runtime identity, an escaped or
unaccounted child, incomplete journal or uncertain effects blocks readiness
and B. Forced per-session recovery is a separate future gated mechanism; do
not invent an automatic escalation or fall back to container termination.

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

The current candidate has only parent `SessionStart`, `UserPromptSubmit`,
`Stop` and `StopFailure` hooks. It has no authenticated live child-completion
roster yet. Add `SubagentStart` and `SubagentStop` observations tied to the
exact parent, source generation, native agent ID and initiating Agent tool
call. At quiescence, seal admissions through a measured fail-closed native
Agent boundary; `SubagentStart` alone cannot block a racing spawn. Reconcile
the roster with Agent tool events, child transcript/sidecar identities,
parent results, supervisor process custody and admitted job/effect records.
A child stop means its response ended; task success, interrupted work and
unsettled effects are distinct dispositions. Missing or conflicting evidence
is `unknown`, never inferred clean. If the pinned CLI cannot enforce or
observe this boundary, managed swap refuses before stopping A.

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

Every external command or edit requested by a managed lane follows
`Claude/MCP bridge -> lanes service -> execution-group supervisor`. The lanes
service checks lane identity, owner generation, operation fence, worktree
reservation and request ID, journals the admission, then forwards it. The
execution-group supervisor starts or observes the OS job and retains its
process, output and result across A's exit and B's start. Status, output,
wait and cancellation return through the same service; the Claude process
has no direct execution-group control socket. An already admitted job may
continue while the lane's new dispatch is fenced. The present prototype
connects its MCP bridge directly to a per-lane job-supervisor socket, so this
service gateway and its no-bypass tests are still required before activation.

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
separate from each source-generation credential. Managed file and job actions
check owner generation and resource reservations. The source cannot obtain
runtime-creation or owner-transfer authority through the job endpoint.

The pinned CLI policy keeps native children foreground, disables native
background tasks/agent view and exposes only native
Read/Glob/Grep/Agent/SendMessage. The background-task flag keeps a native-child
SendMessage reply awaited inline. `CLAUDE_CODE_HARBOR_KITE=0` disables
cross-session routing; `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0` and omission
of `--agent-teams` disable teammate routing.
Native Edit/Write, Bash and PowerShell are omitted. Workspace editing remains
supported through supervisor MCP jobs, which acquire the registered worktree
reservation before executing the mutation. This makes conflicting file writes
and persistent commands share one enforced admission boundary. A native
PreToolUse hook alone cannot supply that boundary because command-hook errors
and timeouts may let the normal permission flow continue. Effective policy and lifecycle behavior require measurement on
the actual pinned CLI; launch flags and hooks alone establish no capability.

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

## Prepare, reconciliation and explicit release

After graceful foreground completion and actual CLI exit, preparation durably
fences A's generation, verifies exact-runtime exit and complete supported
session activity, and reconciles histories, jobs, reservations and effects.
An early `/swap` can fence admissions and request only the validated graceful
exit path once graceful criteria hold; a busy transition requiring another
model turn after control entry blocks instead. B stays absent until the same
evidence is complete. The controller
initiates no new model requests. Cooperative wrap-up is A's work before control
entry; no final model turn or generated handoff is required by preparation.

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
be reported separately. The latest deployment instruction authorizes the
implementation and validation workflow; record the concrete canary identities
and any user-operated seat change before that action.

The September 25 scratch seat-move probe observed one exact parent/native-child
continuation and surviving job, but used model preflight before release,
missed wrong-parent and duplicate-contender fences and did not prove late tool
or transcript-writer exclusion. Prior Docker probes tested a different
boundary. Neither changes T053's narrow offline result, the fourteen historical
Bite 4 outcomes, Bite 5's pending status or public support. Activation still
requires integrated runtime evidence, regression and installation/rollback
checks plus a separately scoped authenticated canary.
