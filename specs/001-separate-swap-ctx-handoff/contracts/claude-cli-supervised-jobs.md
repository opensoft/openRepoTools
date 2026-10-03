# Claude CLI with persistent supervised jobs

Authority: [September 26 shared-container architecture decision and September 30 amendments](../../../openspec/changes/separate-swap-ctx-handoff/claude-cli-supervised-jobs-decision.md).

## Scope and compatibility

The explicit capability discriminator is `claude-cli-supervised-jobs-v1`.
Its lifecycle follows `stop-then-resume-v1`: no target runtime before a
separate explicit release. Persist the capability discriminator in request
identity, operation state, intents and evidence. Missing and unknown values
never infer this capability, and caller overrides cannot change an existing
operation's capability. Existing strict and original PGID-based v1 records
retain their original behavior and proof requirements.

This contract defines an opt-in production target and an internal offline
foundation. Merely implementing its state records does not activate the
runtime path. Public capability remains unsupported until the production
supervisor and actual pinned CLI satisfy the acceptance gates. Unsupported
preflight refuses before stopping the source; uncertain effects after dispatch
retain claims and become indeterminate.

## Runtime and job domains

Four identities must remain distinct:

| Domain | Contents | Account transition |
| --- | --- | --- |
| Lanes service control domain | Lane operation, owner generation, job admission gateway and durable store | Persists across A and B |
| Source runtime domain | Claude CLI, native children, direct tools and all descendants not separately admitted as persistent jobs | Fenced and completely excluded before readiness |
| Execution-group supervisor domain | Exact CLI launch/exit custody and admitted OS job execution | Persists across A and B |
| Persistent job domain | Jobs launched by the execution-group supervisor, their output and result custody | Remains live with the same job IDs and reservations |

For this capability the source domain is the admitted session and all of its
accounted CLI/native-child/helper/tool activity under the pinned graceful
policy, not the enclosing shared container. Its complete lifecycle evidence
and the durable launcher fence must establish exclusion. The job domain has
independent supervisor custody and lifetime. Neither domain is established
merely by labelling a PID list. Unknown activity remains unsupported.

Every managed long-running or external command, including job start, status,
output, wait and cancellation, travels from the lane's scoped MCP bridge to the
lanes service, which authorizes and journals it, and then to the
execution-group supervisor. Native Edit, Write and NotebookEdit remain native
tool calls. The lane has no direct execution-group socket or authority. The
current candidate's MCP bridge directly calls the per-lane job supervisor;
that route is an implementation gap, not an approved shortcut. Persistent jobs
must be launched by the execution-group supervisor into their job domain
after durable service admission. The supervisor must never classify an already detached
unknown process as admitted merely because it can find the PID. A job is a
tracked OS execution and its effects; it is not a model response, native
child conversation or pending Claude tool-call object.

Native child identities remain scoped to their exact parent conversation.
The controller must not invent per-child CLI sessions, accounts or PGIDs.
For this CLI capability only the parent conversation resumes after swap.
Native children from A terminate with A; B creates new children for unfinished
tasks after it receives the service's transition packet. Old child IDs are
correlation evidence only. Persistent OS jobs are the processes that continue
without relaunch and retain their original job IDs.

## Selected initial path: graceful CLI exit in a shared container

The container holds multiple independent Claude CLI sessions and stays running
through A's swap. Source runtime identity is per session; container identity
only describes its environment and is never a stop target. No container stop,
kill, restart or replacement, broad per-user kill or shared-process-group kill
is permitted. L1 and its jobs may remain in the container with lifetimes
independent of the source CLI/terminal. Host Docker access, a host broker,
privileged cgroup delegation or moving L1 to WSL is not required by this path.

The initial supported operation is cooperative foreground wrap-up followed by
actual CLI exit. It supports only the pinned, measured CLI/tool configuration
whose source activity can be completely accounted for. Forced per-session
recovery is a separate gated future mechanism; unsupported or refused graceful
exit blocks B instead of escalating. The
[old Docker provider contract](historical-docker-source-container.md) is dormant
history and its implementation/probes do not certify this path.

The concrete Linux implementation uses a dedicated child-subreaper wrapper per
session. See [linux-session-subreaper.md](linux-session-subreaper.md) for the
admission pipe, exact custody journal, all-child drain, restart rules and
runtime tests. This supplies a source-process witness only under its explicit
conditions; history and external effects still require reconciliation.

### Admit and identify the source before spawn

Before A is spawned, atomically claim its exact parent/lane/generation and
persist the launch intent, immutable configuration digest and launcher journal
identity. Bind the returned process through an owned child handle or a
namespace identity plus non-reused process-start token, source incarnation,
profile, exact parent and generation. PID, title, container name or environment
variable alone is not authority. The launcher must reject a duplicate live
parent before spawning it. Do not retrospectively adopt an unmanaged CLI.

Every managed source/target create, restart, recovery and adoption route checks
the same durable owner claim and retired-generation fence. The journal tracks
pending actions as well as observed exit, so a queued launch cannot silently
complete after fencing. A lost spawn/exit acknowledgment is reconciled against
the same intent; it is never blindly repeated. Launcher or supervisor restart
must recover that identity and fence or leave the operation indeterminate.
An expired lease or missing PID cannot grant B ownership.

### Foreground policy and evidence of completed session activity

The launcher pins the foreground policy below and validates effective CLI,
child, hook and helper behavior for the supported version. Native children
operate through the parent's native foreground interface. Persistent commands
are supervisor-admitted jobs; arbitrary detached tools are unsupported.
Known CLI helpers and child/tool lifecycles must be observed and correlated
from admission through exit. Native Edit, Write and NotebookEdit are allowed
because they finish within their tool calls and cannot outlive A. Deny exactly
Bash and PowerShell. Long-running and external commands use the scoped MCP
bridge, lanes service and execution-group supervisor. Hooks and effects
already accepted remotely still require accounting. Read tools do not imply a
stable snapshot of a live job's files.

A completed model turn, quota wrap-up notice or return to a prompt is not a
CLI exit. A positive readiness witness joins the exact admitted CLI exit,
complete accounted child/helper/tool lifecycle for the pinned supported
configuration, pending-launch reconciliation, retired-source fence and
history/effect checks. Parent death is only one observation. A PID scan,
empty PGID, silence or CLI launch flags cannot certify unknown descendants.
An escaped/unaccounted child, opaque helper, lost journal or unreadable
identity blocks readiness and B. No universal per-session containment proof
is claimed; runtime validation must establish the supported graceful case
before that case can be enabled.

### Session isolation within the shared environment

Bind runtime-specific immutable settings and MCP configuration files, isolated
profile/auth references and a source-generation job credential in each launch
manifest. Fixed shared files such as the current candidate's
`/run/claude/profile/managed-mcp.json` and `managed-settings.json` must not be
overwritten by concurrent sessions; T055 replaces that assumption before
activation. A and B must not mutate C's files, credentials or inherited
configuration. No broad user environment or credential switch is part of swap.
Supervisor control credentials remain separate from source credentials, and
the job endpoint cannot create/adopt runtimes or transfer ownership.

Source and target history write ownership is serialized by the same claim.
Persistent jobs cannot write Claude history. Preserve exact valid saved bytes;
context save/restore does not mean the source task successfully completed.
External requests and buffered effects already accepted before exit require
separate reconciliation; process exit does not cancel remote work.

## Native transcript and lane identity

The transcript stays in Claude Code's projects store; the assembly repository
anchors lane identity and is not a transcript home. Add a `transcript`
sub-record to the exact-parent ledger binding with profile family, resolved
store path, encoded project key, parent UUID, full parent transcript path,
size, SHA-256 at seal time, and the complete child transcript and metadata
sidecar list. The project key is the encoded launch cwd, such as
`-workspace` for a launch from `/workspace`, not the lane directory. Preserve
the `history_manifest` resolver's `projects_store`, project and `source_cwd`
values, plus parent and child digests. Seal after source exit and descendant
drain; reverify at release. Transcript bodies remain in Claude Code's store.

Compare the resolved source and target projects-store identities. If they are
the same, no copy is needed. If they differ, copy the parent transcript and
child sidecars into the target store while preserving relative layout, then
verify the recorded digests before launch. The profile resolver currently
rejects duplicate same-family copies across stores; permit only the
ledger-bound retired source plus verified target without weakening live-holder
uniqueness. The durable pointer is in the JSON ledger. When a database URL is
configured, the derived index uses QA Postgres; otherwise it uses SQLite beside
the JSON ledger. The local JSON ledger under its local flock on the workstation
holding the exact PID is the sole authority. The swap path never reads or waits
for writes or reconciliation of the index, and QA index availability is never
a swap gate. Write index updates
behind JSON persistence as idempotent upserts keyed by local record ID and
digest. Rebuild/reconcile an unreachable or wiped index from the JSON ledger.
Per-workstation connection settings and environment stay uncommitted; use a
service-only, schema-scoped credential distinct from supervisor authority.
Index derived `LANES.md` rows only after their projection is recorded in the
local JSON ledger, so every indexed row has a local-ledger source. The index
may also contain transcript pointers, swap state and job summaries; it does not
replace Git `LANES.md`. T058 follows T057 with offline no-read and wiped-index
reconciliation checks and adds no T054–T057 gate.

Resolve the lane's assembly repository from the worktree's `project.yaml`
entry whose `legs[].role` is `assembly`, falling back to the aggregation's
`project-register.yaml`. If a single-repository project has no `project.yaml`,
its root is the assembly root; `openRepoTools` has that shape. This is an
additional identity and does not replace the WIP `common_dir` or `workspace`
claim fields.

## Durable ownership and launch manifest

Use an owner-private local store with bounded, strictly validated records,
atomic replacement, file and directory durability, and interprocess
serialization. Ownership changes are conditional on the stored generation
and full binding. Two concurrent claimants cannot both succeed. Do not accept
caller-provided evidence as authoritative supervisor or OS observations.

The immutable transition binding contains:

- Capability/schema, canonical lane, host and namespace identity, workspace
  identity, exact parent UUID and lineage identity.
- Operation and request IDs, canonical request digest, owner generation,
  source runtime incarnation, source invocation, owned child handle or namespace/start
  identity, launcher journal identity and supervisor incarnation.
- Explicit source and target profile references, source domain identity,
  target launch-manifest digest and registered worktree identities.
- Sealed native-child/job roster or explicit unresolved coverage, exclusion
  observation references and monotonic observation watermark.

The CLI manifest binds the executable digest/version, launch mode, resolved
project and working-directory identity, exact resume UUID, model, permissions,
settings sources, hooks, tool/MCP configuration and relevant launch flags.
Profile selection must not inherit conflicting authentication. Store bounded
references and digests without credential material or transcript bodies.
Do not assume native resume restores omitted launch settings.

The current source candidate accepts an optional `lane-managed-cli start
--model sonnet`. Without the option, it preserves the v1 manifest and argv;
with it, a strict v2 manifest binds the non-null `sonnet` selection to the exact
`--model sonnet` argv. The persisted source intent, target construction, target
reuse and release checks retain that same selection. This adds no model setting
to profile files and does not change the permission, hook, tool, or fallback
policy. The manifest proves the requested alias only: a live gate must record
the effective provider model, and any mismatch fails that gate without
disabling platform safeguards.

For the first managed Claude CLI capability, the trusted launcher pins
`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` and
`CLAUDE_CODE_DISABLE_AGENT_VIEW=1` in both A and B per-session launches. It
also pins `CLAUDE_CODE_HARBOR_KITE=0` and
`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=0`, with no `--agent-teams`, so
`SendMessage` cannot address an external session or teammate. Native
Read/Glob/Grep/Agent/SendMessage remain available, and native Edit, Write and
NotebookEdit are allowed. A SendMessage continuation is restricted to one of
this parent's native children and remains an awaited foreground reply under
the pinned background-task policy. Deny exactly Bash and PowerShell. Long-
running or external commands run as admitted supervisor MCP jobs under the
worktree reservation. Verify a native Edit and separately verify that an
admitted job is refused when it conflicts with a worktree reservation. A
native edit cannot consult a job reservation, so parent-edit versus job
concurrency during normal operation is outside this feature; the swap window
uses the input fence and verified exit witness. The reviewed CLI launch also uses
`--restricted` and a pinned settings file. `--strict-mcp-config` admits only the
reviewed L1 job-broker MCP server. The CLI's inherited settings, plugins,
hooks and subagent definitions must not add an alternate command executor or
override the effective background policy. Validate the effective launch and
all child tool rosters against the pinned manifest before model dispatch;
any unverified CLI version or setting refuses managed operation. Ordinary
subagents remain foreground CLI work and write their normal transcripts.
Persistent Linux commands are directly admitted by the L1 supervisor and
stay independent of the source CLI's lifetime, including when all share one container.

The scoped CLI records an authenticated `SessionStart` before accepting normal
terminal input. A fresh untrusted workspace may first show the pinned safety
dialog: after its initial 150 ms remount has settled, the custodian permits
only one exact default-No → selected-Yes → Enter transaction for the admitted
working directory. A later or incomplete selector revokes the Enter grant.
This startup input is allowed while B awaits adoption, but B cannot submit a
model prompt until its exact claim, configuration and control binding are
durable. A nonempty terminal submission stays pending until its own
authenticated `UserPromptSubmit` callback begins the parent turn; only the
corresponding Stop/StopFailure ticket settles it. Missing or refused callbacks,
unknown terminal editing, and ambiguous input keep `/swap` fenced. A proven
empty Enter is swallowed locally; the managed terminal intercepts `/help`
locally and never sends it to Claude. It accepts `/swap` only at an authenticated
idle prompt with a clean empty line.

The durable source fence rejects source-generation runtime creation,
adoption and supervisor mutations before dispatch. It remains effective
across adapter recreation, supervisor restart and controller takeover. All
managed launch paths must enforce it; an unknown bypass is unsupported.
Existing persistent jobs need no new A-authorized command to continue their
already admitted execution, but they cannot use a retired source credential
to admit a new independent job or runtime.

The source claim is durable before initial spawn and rejects another admission
for that same parent. The target claim is bound to the exact parent, operation, target profile,
launch manifest and next authorized ownership generation. A different parent
refuses even if the child ID matches. A second claimant refuses even if it
requests the same target profile. An identical accepted request observes its
durable result; it is not a second owner or repeated launch.

An elapsed lease, PID disappearance, seat removal, quota exhaustion or hook
clearance cannot authorize takeover. Hooks may provide bounded context and
diagnostics. `SubagentStart` context is never a blocking ownership gate.

## Persistent jobs, worktrees and write reservations

Register each worktree before any managed participant edits it. Registration
binds canonical realpath and repository/common-directory identity; aliases
and cross-lane overlap must resolve to one owner or refuse. Subagents may
share the lane worktree; separate per-child worktrees are not required.

The state repository and the edited project have independent Git identities.
The canonical `lanes-edit.sh workspace-root` selects the WIP repository used
for managed state and global claim arbitration. Existing claim `common_dir`
continues to identify that state repository. For this CLI capability, claim
`repository` identifies the edited project's actual Git common directory,
and claim `workspace` identifies its Git worktree root. Resolve these project
facts strictly before enrollment/source admission from the explicit launch
directory; a launch directory beneath that root remains valid. A non-Git or
bare directory, failed Git read, or unverifiable canonical identity refuses.
The generic native claim API's fallback from repository discovery to a path
does not authorize a CLI source.

History reconciliation verifies the actual Git root against the registered
worktree path and its actual project common directory against `repository`.
State-owner and global claim checks independently retain their WIP
`common_dir` equality. A complete claim digest binds both fields and the
existing resource ID carries that digest through source/job/release records.
A changed claim, replaced project Git identity or changed worktree root
blocks readiness and release. No schema migration, silent claim rewrite or
fallback from project identity to state identity is permitted. Existing
unverifiable records remain fenced and require explicit recovery.

A job admission records its stable job ID, request-content digest, parent and
optional child identity, admitting generation, registered working directory,
command/configuration digest, domain identity, resources it may change and
durable launch intent. Runtime observations add process-start identity,
status, output custody, result digest and known or uncertain effects. Do not
persist secrets from command environments or raw credentials.

Job states must distinguish an admitted intent, possibly dispatched launch,
observed running process, completed result and uncertain execution. A crash
between launch and process-identity publication cannot be resolved by blindly
starting another job. The supervisor must find the existing execution through
authoritative domain/admission identity or retain uncertainty.

Job IDs and write reservations survive an account-generation change. A target
can read a completed result repeatedly. It can monitor or control an existing
job only with current owner authority and a matching job identity. It must
not create a replacement or repeat release/cancel actions whose outcomes are
unknown. A reserved resource cannot be assigned to a competing admitted job
writer while the job may still write. Native edits do not consult job
reservations. Unspecified resource scope requires a conservative
worktree reservation; shared Git metadata mutations also require coordination.

Tracked dirty files and untracked files remain intact. Inventory observations
include their observation point and which jobs may still change them. A
snapshot taken while a job writes is not a stable checkpoint. No automatic
reset, commit, abandon, cleanup or replay is part of account recovery.

## Prepare and release

### Graceful wrap-up before control entry

The October 2 ruling requires swap safety and state reconstruction with zero
source model tokens and no final source handoff. The service's durable task,
history, job and filesystem records provide B's packet. Cooperative wrap-up
may improve context **before** the supervisor accepts the swap operation; it
is not a readiness condition. A remains the sole Claude controller while it
wraps up. The supervisor does not move the seat, grant B ownership or interpret
a wrap-up message as source exclusion.

[Anthropic documents native wrap-up allowance](https://support.claude.com/en/articles/17040437-claude-code-wrap-up-allowance)
as capped, discretionary usage charged to the weekly quota, for a response
already in progress when the five-hour limit is reached. It may be insufficient
and does not permit a new message after exhaustion. Its presence, size or
successful completion is never assumed by the service.

A must subsequently exit the CLI through the supported graceful path; a
wrap-up message or returning to the prompt is not exit. While a wrap-up request
for this exact parent is pending before known exhaustion, the already
registered `Stop` hook may return
`{"decision":"block","reason":"<wrap-up instruction>"}` at most once for
the request ID, with durable deduplication across duplicate callbacks and
service restarts. Honor `stop_hook_active`; if the hook errors, treat it as no
wrap-up. The reason instructs A: do not start new
agents or long work, record state in the handoff, then stop. With foreground-
only children, no child is running at a `Stop` boundary, so shutting down
subagents is vacuous. A blocked `Stop` continues the turn and cannot certify an
idle exit boundary. Skip the optional block at known exhaustion; never request
a source continuation on the assumption that native allowance will pay for it.
If exhaustion interrupts the wrap-up, do not retry or require a final handoff.

After a nonblocked terminal `Stop` or `StopFailure` with no subsequent
`UserPromptSubmit`, the service fences the source and the custodian stops
relaying keyboard input to A until exit. It sends SIGTERM only to the exact
admitted CLI PID through the owned child handle under the subreaper custodian.
The custodian observes the main process with wait and requires the `ECHILD`
witness; `SessionEnd` is corroborating evidence only. Measure that SIGTERM at
an idle prompt runs the CLI's own shutdown before depending on it. If optional
wrap-up was requested, this boundary must occur after that continuation, not
at the blocked `Stop` that started it. If SIGTERM is measured unsupported,
the sole fallback is one atomic `/exit` PTY write including
carriage return and a bounded wait for an observed exit, `SessionEnd` or
`Stop`. No observed change by the deadline is a refusal that retains claims,
not a retry. If A cannot exit, quota is exhausted before a supported stopping
point, or any source child/tool effect remains uncertain, keep B absent and
preserve claims. Do not escalate to forced recovery under this initial
capability. The handoff and final model response are context, never release
authority.

| State | Required condition | Target runtime |
| --- | --- | --- |
| preflight | Read-only manifest, profile, history, ownership and supported graceful-lifecycle checks | Absent |
| source-stopping | Durable source/input fence; at a verified idle boundary send SIGTERM to the exact admitted CLI via owned custody (validated graceful exit request). Use one atomic CR-terminated PTY `/exit` write only if SIGTERM is measured unsupported. | Absent |
| reconciling | Complete source exclusion; job, history and file reconciliation | Absent |
| ready-to-resume | Fresh exclusion witness; claims, history and exact target intent bound | Absent |
| release-authorized | Durable explicit release and one startup intent | Startup permitted |
| target-starting | Exact-parent CLI launch under authorized target claim; existing attach locator returned | Started, input fenced |
| target-observed | Actual parent/account identity and durable adoption accounted for | Active |
| indeterminate | Preserve claims, intents and uncertain effects; observe only | No replacement launch |

Prepare first verifies that the graceful per-session path can account for A's
exit without disturbing the container, C or admitted jobs. If requested before
known exhaustion, the one optional cooperative wrap-up is delivered through
the exact parent's `Stop` hook before durable control entry. After a verified
idle boundary, it durably fences new source admissions and every managed
restart and stops relaying keyboard input
before signaling A. A busy source that would need another model turn after
control entry is unsupported for this initial transition and blocks B; the
controller does not request that turn. A refused exit or expired bounded
deadline retains claims and blocks B. A may already have exited naturally; the
same identity, journal and activity checks still apply. Unknown or refused
exit holds the operation. Stopping a runtime is never task-completion evidence.

Control entry is the durable acceptance of the operation by the supervisor.
From that point the controller initiates no model request and admits no new
source job/tool dispatch. An optional `Stop`-hook wrap-up permits at most one
continuation before that entry; preparation remains valid without it. Any old
in-flight source response or effect is still accounted for; the fence alone
does not block the CLI's network calls or prove
it has exited. B cannot start until exact-runtime exit and complete supported
session activity, transcript writers and effects are reconciled.

The witness binds source incarnation, exact parent/generation, launcher
journal/observation watermark, exact exit evidence, accounted foreground
child/helper/tool lifecycles, pending launch outcomes and enforced restart
fence. Revalidate these facts before release. The surviving job domain and
unrelated C are explicitly outside A's stop scope. Missing identity, escaped
children or uncertain effects retain indeterminate state. An empty PID list
or parent exit alone cannot pass.

After source exclusion, verify exact parent and child histories through a
bounded integrity manifest and actual identity/link evidence. Preserve valid
saved bytes; never edit internal Claude transcripts to manufacture recovery.
Record missing or interrupted history honestly. Reconcile job records and
filesystem effects before deciding which instructions can safely continue.
Known live jobs may remain live at readiness with retained reservations;
unaccounted-for work or effects remain unresolved and prevent readiness.

Explicit release revalidates the exclusion witness, current ownership,
history manifest, jobs/reservations and target launch manifest. Durably bind
the release ID and launch intent to this operation and generation before
creating any target process. Target selection, account-access checks and
operator seat movement are not release authorization. No model preflight is
performed during the prepare interval.

Launch only the pinned CLI's supported exact-parent resume path. Wrong or
missing actual parent/account evidence never falls back to a fresh session.
A possible target startup with lost acknowledgment retains the startup intent
and becomes indeterminate until observed. Do not automatically launch another
target, return to a held state, or run a second child continuation.
`release` returns the already journaled target-starting custodian locator;
the operator can attach there to answer that exact fresh trust dialog before
`SessionStart`. Explicit `observe-target` revalidates the original intent,
claim, profile history store, account, registry and process. If SessionStart
is still absent it returns the same pending locator without mutating the
operation. Once present, it adopts that same launch and opens model input only
after the current owner and all adoption artifacts are rechecked under lock.
A lost release ACK is recovered by observation, never another release.

## Child recovery and result delivery

The initial candidate's parent-only hooks do not establish a live native-child
roster. Before this capability reports graceful child shutdown, its pinned
runtime must emit authenticated `SubagentStart` and `SubagentStop` observations
and correlate them with initiating Agent tool calls and saved child histories.
Seal the first-delivery roster only at a verified nonblocked terminal `Stop`
or `StopFailure` after the wrap-up continuation and with no later
`UserPromptSubmit`. Foreground children have returned by that boundary. Defer a
measured fail-closed **mid-turn Agent admission fence** to a future gate beside
forced recovery; T054–T057 neither depend on nor test it. A busy request stays
pending until the idle boundary or reaches its bounded refusal. The custodian
fences relayed input and uses the headless exit path. A `SubagentStart` hook is
observational and cannot itself prevent a racing spawn; first-delivery behavior
does not rely on it doing so. The service distinguishes response ended, task
completed, interrupted with valid history, and unknown. A quota `StopFailure`
on the parent or child is a failure signal, not proof of child completion. If
the runtime lacks the idle-boundary and roster evidence, preparation refuses
before planned source exit.

The npm-global Claude CLI currently reports `2.1.286`. Before T055 depends on
the pinned CLI, record measurements for all of these behaviors on the exact
binary/version tuple: parent `StopFailure` with `error: rate_limit`; `Stop`
hook `decision: block` continuing the turn with its reason; SIGTERM at an idle
prompt running CLI shutdown and firing `SessionEnd`; `SessionStart` on
`--resume` carrying the injected transition-packet context; and the parent's
`Stop` hook being absent while a foreground Agent call remains in flight. No
T055 code path may assume a hook or signal behavior until it has been measured.

The lanes service accepts the swap trigger from the external command or a
fresh profile-keyed usage observation, consumed directly without waiting for
`UserPromptSubmit` or an AI warning response. Correlate samples and request
deduplication with source profile and usage reset window; resuming the same
parent must not suppress a request in a later window or on another profile.
Persist native child/task/lifecycle references and admitted-job/effect records
as work proceeds, so the packet does not depend on a final handoff. Source-bound
`StopFailure` with
`error: rate_limit` is its structured exhaustion event. Pane text may prompt
an inspection but cannot certify account state, child completion or readiness.
An early request can ask A for bounded cooperative wrap-up before durable
control entry; quota exhaustion during that work causes no second request or
automatic replay. No allowance is required; at known exhaustion skip the
optional wrap-up block entirely. The per-lane supervisor still requires exact
CLI exit and complete activity/effect accounting; the shared container and other lanes
continue running.

Before B's first model turn, the service supplies a bounded, versioned
transition packet from its own records: exact parent/operation/generation,
child dispositions and native IDs, current job IDs/results/reservations,
Git worktree identity, dirty/untracked path inventory, change observations
since A's last inventory, and unresolved or provisional facts. Refresh the
worktree observation after source exit and again before release; label it
provisional when a continuing job may write. The packet may be delivered by
managed `SessionStart` context or an authenticated read-only endpoint. An
optional AI API summary is non-authoritative and cannot mark any unknown
fact settled. No workspace cleanup may mutate user work; only verified
service-owned temporary artifacts and stale references can be removed.

### Speckit task assignment and recovery

For Speckit-driven implementation, the preferred default is one task from the
feature's `tasks.md` per native implementation child run. Multiple children may
contribute to one task with distinct roles and file boundaries. Taking another
independent task normally creates a new run/assignment. Supporting review work
may have its own task or a bounded related-task set; record any multi-task
exception and reason explicitly. This default is not a swap admission gate.

Tasks should represent small independently checkable deliverables with explicit
acceptance criteria, supporting the intended bounded Sonnet assignments. The
orchestrator supplies semantic scope; the service persists assignments before
work and joins actual runtime identities as they become observable. Keep
repository/feature identity, task-list path and task-definition revision,
Speckit task ID or explicit exception set, assignment/attempt, role, expected
files/worktree, exact parent/source generation, initiating Agent call, actual
native child ID and runtime task ID when emitted. Add admitted EGS job IDs and
progress/acceptance-evidence references continuously. A Speckit task ID must
never be substituted for a runtime task ID. Missing joins remain unknown.

The service derives candidate review groups for tasks with unverified changes
or outstanding jobs, including a child that returned immediately before the
stop. Retain separate contributions when several children share a task. Include
parent edits, declared exception tasks and unmatched changes/effects explicitly;
do not invent attribution or infer whole-task completion from a child ending.
The task list bounds review only to the extent attribution is complete.

B or an assigned reviewer checks deliverables and acceptance evidence after
source exclusion and effect/ownership reconciliation permit startup. Verified
completed work stays complete. Inspect and continue existing partial work with
fresh children; do not reset files, replay accepted tasks or relaunch admitted
jobs. Observe each continuing EGS job by its existing ID and reservations.
Unknown effects still block replay/release, and continuing writes make file
observations provisional. Record acceptance and repair evidence independently
of the immutable handoff outcome.

One-task guidance does not establish cancellation or forced-recovery support.
The initial capability retains its graceful idle/exit witness. A future hard
stop may consume the review groups only after its separate safety gate passes.
The [brainstorm packet](../../../ideation/brainstorm/speckit-task-recovery-overview.md)
preserves the rationale and tradeoffs; T055–T056 own implementation and cases.

### Worktree inventory integration

The October 3 amendment incorporates PR #97's local worktree diagnostics
through a service-owned observation adapter. The managed JSON ledger remains
the sole authority for operation/generation, lifecycle, claims, reconciliation
outcome and readiness. A recovery sidecar, `SWAPPED` state or `resumable` report
cannot authorize managed readiness, release or takeover. Integration must not
introduce a second lifecycle writer or depend on merging PR #97 unchanged.

Record bounded, versioned observations bound to canonical lane, exact
operation, owner generation, repository/worktree identity and observation
watermark. Include Git registration and disk presence, branch, full HEAD or
explicit unborn state, configured upstream, dirty/untracked paths, publication
evidence, collection status and provenance. Record collection limits and
omissions; a truncated or partial inventory is not complete evidence. Refresh
after source exit and before release. Continuing admitted jobs keep their
reservations and make filesystem observations provisional.

Resolve identity in the bound host/container from verified physical Git common
directory and worktree paths plus estate/shape configuration and canonical
lane identity. Keep observed spelling and provenance for diagnostics. Control
records remain outside product worktrees under the existing private state
root. Identity keys must resist collisions between path encodings and
repository basenames, while physical aliases share the same resource identity.
A branch, profile, basename or historical absolute path alone cannot select
the control root or identify a worktree. Ambiguous resolution stays unresolved.

Absent, unreadable, malformed, unsupported-schema, stale, incomplete and
contradictory observations remain distinguishable. Failed Git reads must not
become clean files, zero unpublished commits, absent trees or completed tasks.
A branch with no upstream or a detached HEAD is not proven published; record
publication as unknown unless supporting evidence exists. Remote-tracking
observations carry their freshness and cannot claim current remote currency
without a corresponding fetch. Inventory collection itself performs no fetch.
Absence of a historical sidecar proves neither loss nor safe clearance.

Existing PR #97 sidecars may be read as historical diagnostics only after
explicit schema, repository/worktree identity and provenance binding. Do not
silently migrate their lifecycle or reuse their operation/generation counters.
Stale records remain labeled; fresh service observations govern reconciliation.
Unreadable historical metadata is preserved, never overwritten to clear a
warning. Inventory persistence failure cannot produce successful managed
readiness; retry collection under the same operation without replaying work.

Unknown ownership, writers, effects or required worktree identity retain claims
and block B. A non-safety diagnostic gap may enter B's bounded repair list only
when independent source-exclusion and accounted-effect checks have passed;
repair cannot waive those checks. The original `clean`/`repair-required` rules
still apply, and an unresolved diagnostic repair item requires `repair-required`.
Dirty files or known unfinished work alone do not imply failed transfer.

Preserve dirty/untracked files, completed tasks and admitted jobs. Report
missing, stale or misplaced worktrees and the established estate remedy.
Inventory and repair must not automatically commit, push, stash, reset, clean,
prune, move, delete or recreate user worktrees. An operator-directed estate
action follows its own existing contract; inventory is not a replacement for
`park`, `resume` or `status`. No final source summary is required.

### Handoff outcome and startup repair

Before release, seal a `handoff` sub-record in the JSON ledger with the exact
operation, parent and source/target generations, outcome, reasons, checkpoint
and evidence references, observation watermark and identified repair items.
The service records `clean` only when the cooperative checkpoint completed
before exhaustion and it verified the checkpoint, child task dispositions,
job references and source history/exit reconciliation. Exhaustion before or
during checkpoint completion, missing checkpoint or unreconciled child failure
requires `repair-required`. A final AI response alone is not that evidence.

Both outcomes require identical source exclusion and accounted-effect checks.
Repair after resume cannot resolve an unknown old writer or authorize unsafe
release. Clean may include dirty/untracked files, continuing admitted jobs and
safely unfinished tasks with explicit continuation plans. It describes the
transfer checkpoint, not completion of the lane's work.

The first packet supplied to B names the outcome and pending repair items.
An absent marker in an otherwise valid packet requires repair; stale or
contradictory operation/generation binding refuses. For clean transfers, B
checks refreshed service state and follows the continuation plan. For transfers
requiring repair, the service first performs deterministic reconciliation and
permitted cleanup of its own artifacts. B may use target-account inference
to reconcile task meaning, assignments and proven progress. Required repair
precedes normal work. The service holds normal external job admission until
repair completes, while allowing inspection and bounded repair actions. The
startup packet instructs B to reconcile before ordinary native work; this
introduces no mid-turn native Agent fence. No repair automatically resets, commits or deletes user
files, relaunches a completed child, or repeats an uncertain job dispatch.
Persistent jobs are observed under their existing IDs.

Persist per-item repair evidence and completion against the sealed handoff
digest and target generation. Keep the original outcome immutable, even after
repair succeeds. A manager AI may assist reconstruction but cannot clear an
unknown ownership or effect assertion. New child assignments follow the
reconciled task plan and use new IDs.

After target startup is accounted for, each safely stopped unfinished child
is `restart-pending`. B receives a task-specific record with the old child ID
for correlation, the original assignment and definition, proven progress,
current job IDs, reservations and recovered result references. B starts a NEW
native child under the target account and records its new ID. The service
marks `restarted` only after a correlated new Agent start and ownership check;
the old child is never marked `exact-resumed` in this capability. An ambiguous
dispatch is not automatically resent. Unsupported or contradictory history or
effects remain unresolved. Completed children are not relaunched.

The supervisor's existing-job result is supplied as current recovered state.
Claude resume is not assumed to reattach an old pending Bash/tool-call object
to that job. A model response requested by A belongs to A's runtime; its
unsaved content is not transferred to B. Recover from valid saved history
and observed effects, including effects absent from the last transcript turn.

## Recovery and refusal

All external actions follow durable intents and at-most-once dispatch.
Readback is repeatable; unknown effects are not. Recovery observes and may
advance only when authoritative evidence resolves the same intent. It never
infers release, repeats an uncertain start/stop, relaxes a claim or changes the
stored capability discriminator.

Stale generations, wrong parent/profile/manifest, duplicate contenders,
unknown job identity, missing histories, unregistered worktrees, uncertain
effects, unknown restarters or incomplete domain witnesses refuse before new
effects. A post-dispatch failure retains claims as indeterminate. Explicit
unenrollment requires all remaining runtime and job writers/effects to be
reconciled before releasing their reservations and the lane claim.

The protection boundary is cooperative managed workloads under the local
user with enforced managed launch paths and verified graceful session lifecycle. This contract
does not claim isolation against a hostile process with equal user authority
or machine administrator access. A normal runtime path that bypasses the
fence is an unsupported configuration, not a successful recovery.

## Required verification

Offline tests must exercise independent process contenders, wrong parent
and stale-owner rejection, durable fence readback after supervisor restart,
job/result reconciliation and crash boundaries around every durable intent.
They must check effects and launch counts, not merely the returned state.

The next planned integrated fixture runs independent Claude sessions A and C
in the SAME long-lived container. A saves a foreground native child history,
finishes its bounded foreground work and exits naturally. A real
supervisor-admitted job retains its original ID/process/output and continues;
C and the container stay running and their configuration/auth bindings remain
unchanged. No B exists before verified exact-runtime exit, full supported
session-activity and effect/history reconciliation and explicit release. That
release starts B once on A's exact parent; native child continuation and job
result readback do not repeat completed work.

Negative fixtures must block B on refused/uncertain exit, an escaped/unknown
child, duplicate parent/source or target contenders, stale A dispatch/restart,
launcher restart with lost journal/identity, changed shared config and lost
startup acknowledgment. Recovery with intact journal/fence may observe the
same intent, never blindly launch again. Check identities, dispatch counts,
reservations and saved history; model/task completion and context restoration
are separate assertions.

Offline protocol fixtures do not establish real CLI foreground-child behavior.
Record the actual pinned CLI, launcher/supervisor, namespace and configuration
tuple for bounded runtime evidence. The canary's source and target profiles are
supplied by its operator when separately authorized; `team05d` and `team05j`
are the current expectation only. Record the concrete pair in T056 evidence at
run time and in the ledger before any seat movement. The September 30 ruling
authorizes this documentation checkpoint only; it does not authorize a canary,
seat movement, merge or deployment. A future canary gate requires a frozen
inventory, passing shared-route and invoked-dependency tests, actual CLI/fault
evidence, isolated installation and rollback, and separate authorization for
the authenticated run. Preserve the full-suite census and positive native
`ctx`/restoration acceptance tests. Individually mapped failures in the
unreachable, explicitly refused native-`ctx` route remain open; any
shared-path or unexplained failure blocks that stage. No default/global
activation or T057 completion follows from a scoped pass. General public
activation remains unavailable until the supported graceful path and effective
launch policy are measured, repository regression and install/rollback gates
pass, and the same production route passes a separately authorized canary.
T054–T057 remain open until evidence closes them.
