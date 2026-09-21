# Approved revision: retain native Claude subagents

## Authority

Brett answered the restoration tradeoff on 2026-09-16:

> Keep native subagents; allow model-assisted worker restart after the account
> swap, but no written handoffs.

This decision supersedes the independent-top-level-worker-only architecture
and blanket native-subagent prohibition in this change and Speckit feature
`001-separate-swap-ctx-handoff`. Preserve earlier work as implementation history,
not the acceptance target. The same feature remains the sole implementation
owner; no parallel replacement feature or executable OpenSpec task list.

## Revised contract

1. Keep Claude's native subagent workflow. Do not force users to replace native
   subagents with independently supervised top-level worker conversations.
2. The external account transition remains model-independent: stop admission,
   establish safe participant/tool stop boundaries, preserve local work, select
   the explicitly requested authorized profile, and restore the coordinator's
   exact native conversation held under the target account. No model-generated
   summary, checkpoint, commit, push, or written handoff is a swap prerequisite.
3. Prefer native exact worker continuation where supported and verified. Where
   external native restoration is unavailable, model-assisted worker restart
   after the account transition is an accepted fallback, not a reason to change
   the user's worker architecture. Restart uses existing native conversation/
   task records and coordinator context, without generating handoff documents.
4. Keep `release` as the explicit inference boundary. Model-assisted restart
   runs after account readiness and authorized release, never against the
   exhausted source account as a prerequisite. Report its model usage separately
   from the zero-new-model-request account-control phase.
5. Before release, report safely stopped workers as `resume-pending` when
   eligible for exact native continuation, or `restart-pending` when a new run
   is required. After release, report `exact-resumed` or `restarted` only from
   correlated native evidence; uncertainty is `unresolved`. A restarted worker
   is not proven to have the same conversation or identity. Do not claim a
   full graph freeze/repoint or complete context preservation from coordinator
   resume alone. Completed workers remain separately `completed`.
6. Completed work stays complete. Neither exact resume nor model-assisted
   restart permits duplicate writers, replay of uncertain external effects,
   untracked active tools, or a claimed safe stop from OS suspension alone.
   Unknown stop/ownership remains held and reported; this decision changes
   restoration, not the old-writer exclusion requirement.
7. `ctx` remains a deliberate fresh coordinator context under the current
   account. `handoff` remains a separate user-requested operation. Neither is
   implicitly invoked by swap or worker restart. Native-worker treatment for
   ctx must be specified during re-planning rather than borrowing the obsolete
   independent-worker rebind implementation unchanged.

## Acceptance and implementation transition

The existing independent-worker fake tests do not validate this revision.
Retain reusable profile, storage, transport, ownership, and legacy safety work;
pause conflicting participant/SDK prohibition and worker orchestration tasks
until the specification, plan, tasks and analysis are reconciled.

Acceptance requires evidence for native worker discovery and stop boundaries,
exact coordinator resume under the selected account, explicit release-gated
model-assisted restart without handoff artifacts, completed-worker preservation,
and no duplicate effects across restart/retry. Publish which native participant
kinds and runtime versions were actually tested. Native teams and background
execution are not automatically proven supported by this decision.

Live account actions still require explicit authorization. This decision is a
product tradeoff, not evidence of runtime feasibility or a passed live probe.

## Native runtime boundaries for re-planning

A native child belongs to its coordinator's execution lineage; it is not a
new independently logged-in top-level SDK session. Do not invent per-child
top-level UUIDs or external open/release methods. Discover native agent/task
identities and lifecycle/tool evidence from the actual runtime. Missing or
contradictory evidence stays unresolved.

Distinguish runtime-owned native background subagents, with recorded task IDs
and lifecycle events, from unmanaged detached shell processes. Evaluate the
former for controlled stop/restart rather than copying the old blanket native
background prohibition. The latter still requires exclusion/effect evidence;
neither a background flag nor a parent exit proves safety.

Track native task lifetime separately from the tool call that launches it.
A completed `Agent` launch call can leave a background child running; its tool
completion must not mark that child quiescent. Link actual native lifecycle
events to the parent tool/task identity, retain active children after the launch
returns, and test swap while such a child is still doing work.

An agent ID may survive several runs. Terminal evidence must identify the
current run/task and its ordering relative to admission, not merely match an
agent ID with an old completed notification. Startup auto-resume exclusion and
current writer quiescence are separate proofs; neither substitutes for the other.

The claim owner is the coordinator execution lineage. Native children working
inside its workspace inherit that ownership; they are not competing independent
owners of the same directory. A genuinely isolated native child worktree needs
its own exact global claim. Preserve exclusion against other lanes and replaced
lineages, including realpath aliases and overlapping directories. Retain claims
while any owned writer or external effect is unresolved.

A read-only coordinator does not make its writable native children read-only.
Claim the lineage workspace whenever any member may write, and enforce each
agent's immutable tool/permission policy using its actual native identity.
Unknown child identity must not inherit writable access. If the runtime cannot
enforce distinct parent/child policies, report that configuration unsupported
rather than broadening the coordinator's permissions.

Preserve native custom-agent definitions, configured role/model/effort, tools,
and permissions across the account transition and any worker restart. Do not
silently substitute a cheaper model, a different role, or broader permissions.

For `ctx`, holding native workers means keeping their stopped work and native
records, not promising that live children survive their parent shutdown.
Explicit worker restart belongs to the fresh coordinator lineage and uses the
caller's checkpoint after release; it is not exact cross-parent native rebind.
No checkpoint is generated as part of account swap.

Child transcript access is required for an exact-resume claim, not universally
for the approved new-run fallback. If current-run stop and effect accounting
are proven and the original task and definition remain available from parent
context or native task records, an unreadable child transcript can yield
`restart-pending`. Missing information needed to prove safety or identify the
task remains `unresolved`; do not reconstruct it into a handoff document.

A restart instruction may be mechanically composed from durable identities and
statuses and dispatched after release. It is an ordinary model instruction,
not a generated semantic handoff document. Its accepted-send acknowledgement
does not prove any worker restarted: require correlated native task events,
and preserve uncertainty when an old task cannot be linked to its new run.

Official SDK documentation describes subagent continuation by resuming the
same parent session and providing its captured agent ID to a subsequent model
prompt; custom definitions must be retained. This supports the model-assisted
direction, not an external child-resume guarantee. [SDK subagents](https://code.claude.com/docs/en/agent-sdk/subagents#resume-subagents)

Claude's native documentation distinguishes model-stopped subagents from
externally cancelled ones: SDK/user cancellation may prevent model messaging
from resuming that child. The installed version's stop/restart behavior must
therefore be tested before choosing the adapter path. [Native subagent resume](https://code.claude.com/docs/en/subagents#resume-subagents)

These references were inspected on 2026-09-16. They do not establish safe
active-tool interruption, cross-account resume, or compatibility for every
native participant kind. No live validation was performed for this decision.

Promptless parent initialization alone is insufficient evidence of a held
native graph. Check whether the pinned runtime automatically resumes orphaned
children during startup. The control phase must prevent both parent and child
inference until release through a supported, tested boundary. If startup can
dispatch children without an explicit query and cannot be held, report that
configuration unsupported rather than advertising zero-model-work swap.

The local CLI 2.1.270 investigation found an interactive takeover/adoption
orphan auto-resume path that does not wait for the first user query. Its print
path instead calls orphan reconciliation without an auto-resume callback.
The exact SDK launch-mode selection must be established before choosing the
held-start boundary; do not generalize interactive behavior to the SDK.

Bind compatibility evidence to the executable the SDK actually selects,
including its version/digest and launch arguments. Inspect the SDK's bundled
binary selection before relying on a separately installed `claude` binary.
Different or untested runtime/SDK pairings remain unverified.

The isolated SDK 0.2.153 probe selected bundled CLI 2.1.273, digest
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`,
not the separately installed 2.1.270. The earlier 2.1.270 trace is informative
only; it does not establish compatibility for that SDK pairing. This is probe
evidence, not a production dependency installation or live-account result.

The selected 2.1.273 print path has an additional mechanism: restored
`running_background_tasks` can populate `restoredOrphans`, which can enqueue
a restart notification during startup through a default-enabled orphan-wake
path. Absence of an explicit child-resume callback therefore does not prove
absence of startup inference. Validate the exact initialization/event loop
with orphan fixtures, including whether queued notifications dispatch before
the first user query. Do not disable undocumented experiment flags or rewrite
   native transcripts to manufacture a passing boundary.

Terminal-stop every tracked native child before source-parent exit. If the
selected launch mode can auto-resume orphans, additionally verify that durable
stop provenance excludes startup auto-resume; an acknowledgement alone is
insufficient if the startup classifier's required record is not persisted.
If the supported SDK mode is proven not to auto-resume, that mode supplies
the startup hold boundary, but not proof of old-child/tool quiescence. Never
load eligible orphans through an auto-resuming path and call that graph held.

Terminal-stopped unfinished workers may become `restart-pending`; their
post-release model-assisted restart is the explicitly approved tradeoff.
Any exact native continuation must also respect the startup hold boundary.
The classifier/stop interaction still requires pinned-runtime validation;
this static finding is not proof that the candidate stop sequence is safe.

The first disposable selected-runtime probe failed its isolation audit:
Docker reported a shared-container network namespace rather than `none`.
Its output is not no-network acceptance evidence. Graceful stop attempts did
not produce a confirmed exit, so neither cleanup nor runtime quiescence may
be inferred from the stop request. Do not relaunch the probe until the exact
test container is accounted for and the replacement's isolation is verified.
This does not authorize changing live profiles, other containers, or the
Docker daemon. Gate 0 remains open; static inspection and synthetic controls
do not close it.

The subsequent audit found that the shared namespace's target itself reported
`NetworkMode=none`; the problem was an unapproved isolation workaround, not
evidence of internet access. The probe had no host mounts, used empty temporary
configuration directories, and reported `tokenSource: none`. Its only input
was an initialization control frame, not a user query. Neither the positive
orphan fixture nor the terminal-cleared candidate was actually resumed, so
even a corrected isolation record would not turn this observation into Gate 0
proof. Do not repeat the shared-namespace workaround.
