# Separate Swap, Context, and Handoff with Native Claude Subagents

## Status and governing intent

**2026-10-03 two operating modes:** retain ordinary lane swap and add an
explicit broker mode. In swap mode the lane keeps its qualified workflow and
native children; LS transfers the exact parent under the existing safety
contract. In broker mode the main agent performs primary orchestration and
all agents request delegated workers through LS. LS selects the authorized
account, model/harness, host and container; workers may run locally or on
enrolled remote computers. Results return through LS to the main agent.

A can remain on its account while worker accounts change from B to C to D.
Existing swap remains available for qualified worker runtimes and A itself.
Low orchestration usage may help A reach its reset without a swap, but is not
a quota or context-lifetime guarantee. Broker workers are separately launched
sessions, not native children whose account/container is switched. Preserve
swap-mode policy; broker-mode delegation must not bypass LS through native or
direct session spawning. Remote loss of contact is unknown custody, not a
death witness or permission to duplicate work.

Reuse Omnigent session/inbox/policy/routing tools and registered worker-host
surfaces where qualified, with LS retaining admission/placement authority and
EGS retaining persistent-job custody. The installed CLI reports `omnigent
0.1.1`; actual dispatch/inbox code was inspected, but upstream documentation
alone is not runtime qualification. The
[broker contract](../../../specs/001-separate-swap-ctx-handoff/contracts/lane-task-broker.md)
and [rationale packet](../../../ideation/brainstorm/lane-task-broker-overview.md)
define this prospective extension. T059–T062 are a separate broker tranche;
they do not gate or silently replace T054–T057's graceful swap delivery.

**2026-10-03 preferred Speckit assignment default:** for Speckit-driven
implementation, prefer one task from the feature's `tasks.md` per native
subagent run. Several children may contribute to one task with explicit roles
and file boundaries. Keep tasks small and independently checkable, supporting
bounded Sonnet assignments. An orchestrator may record a bounded multi-task
exception and its reason; supporting reviews may have their own task or an
explicit related-task set. This is a preferred workflow default, not a
mandatory restriction on every agent or a lane-swap prerequisite.

Persist task scope, assignment/attempt, actual child identity, files/worktree,
job IDs and progress/acceptance-evidence references continuously. After an
interruption, review every task with unverified changes or outstanding jobs,
including contributions from children that returned just before the stop.
Preserve verified completion and continuing jobs; continue existing work with
fresh children only after reconciliation. Parent edits and unmatched changes
remain explicit review items, so four assigned tasks bound the review only
when attribution is complete. Task grouping supplies no source-exclusion proof.
T055–T056 own the records and offline recovery cases; the first delivery remains
graceful-only, with forced recovery separately gated. See the
[assignment and recovery contract](../../../specs/001-separate-swap-ctx-handoff/contracts/claude-cli-supervised-jobs.md#speckit-task-assignment-and-recovery)
and [rationale packet](../../../ideation/brainstorm/speckit-task-recovery-overview.md).

**2026-10-03 worktree inventory integration:** incorporate PR #97's useful
local worktree observations into the lanes service's existing reconciliation
and B transition packet. Reuse diagnostic logic and preservation semantics;
the managed JSON ledger remains the sole lifecycle, ownership and readiness
authority. A legacy `SWAPPED` snapshot or `resumable` report cannot authorize
managed takeover. Historical sidecars require explicit schema, identity and
provenance binding and never supply managed operation/generation counters.

The service records bounded, versioned repository/worktree observations,
refreshes them after A exits and before release, and distinguishes dirty,
unpublished, missing, unreadable and unknown facts without inventing clean
defaults. Unknown writers, effects or required identity retain claims and
block B; independently safe diagnostic gaps become explicit startup repair
items. This adds no source model turn or automatic Git repair. See the
[inventory contract](../../../specs/001-separate-swap-ctx-handoff/contracts/claude-cli-supervised-jobs.md#worktree-inventory-integration).
T055 owns integration and T056 its fault matrix in the existing feature.
This decision does not merge or close PR #97, activate the capability or
authorize a canary; implementation and runtime evidence remain pending.

**2026-10-02 source token requirement:** the selected CLI swap must preserve safety
and reconstruct state with zero source model tokens and no final AI handoff.
Native allowance and cooperative wrap-up are optional context improvements.
The service consumes usage observations directly, records work continuously,
and reconciles exact exit, children, jobs and files independently of a final
response. Missing idle/exit/effect evidence still retains claims and blocks B;
forced recovery remains a future gate. See the
[amended decision](claude-cli-supervised-jobs-decision.md) and T055–T056.

The follow-up records a service-verified `clean` or `repair-required` handoff
outcome in the JSON ledger and B's first transition packet. Both require source
exclusion before release. B completes required startup repair before normal
work; repair completion is separate from the immutable original outcome.

**2026-09-30 selected CLI correction:** `claude-cli-supervised-jobs-v1`
resumes only the parent conversation. Safely unfinished source subagents end
with A and are reconstructed as new B subagents with new IDs, using the
service's task/history/job/filesystem packet. Existing execution-group OS
jobs keep their identities and continue. Long-running and external commands
go through the persistent lanes service to the execution-group supervisor;
native Edit, Write and NotebookEdit stay in the CLI;
the prototype's direct MCP-to-supervisor socket is not the selected route.
Older exact-child continuation language below remains historical SDK/strict
scope and is not a CLI-capability acceptance requirement.

**2026-09-26 shared-container amendment:** the
[Claude CLI supervised-jobs decision](claude-cli-supervised-jobs-decision.md)
now targets a graceful per-session swap inside the existing long-lived
container, which hosts many independent Claude sessions and must stay running.
A may complete optional foreground wrap-up and then exits its CLI; the launcher
verifies the exact runtime and known session activity, durably fences A's generation and
reconciles history/jobs before one explicit exact-parent B release. Persistent
supervisor jobs and unrelated session C stay live. Uncertain exit or descendants
block B; forced per-session recovery remains a separate gated mechanism.
Container stop/kill/restart, broad process kills and shared config/auth mutation
are forbidden. The supervisor may remain in the container independently of A.

This supersedes the dedicated Docker source-container choice, whose code and
evidence remain a dormant historical candidate. T053's offline ledger evidence
is unchanged; T054–T057 stay open. Existing strict/SDK/PGID records and all
fourteen Bite 4 outcomes retain their meaning. Public activation remains gated.
The September 30 ruling authorizes this documentation amendment only; it does
not authorize a canary, account seat move, merge or deployment. Astra leads
architecture, Sol High leads orchestration, and Luna Max writes implementation.
The operative canary profiles are selected and recorded when a future canary is
authorized. The initial Linux witness
is a dedicated per-session child subreaper under the current contract.

**2026-09-22 scope amendment:** the approved
[stop-then-resume-v1 decision](stop-then-resume-decision.md) adds an explicitly
selected mode with no target runtime until release and a `ready-to-resume`
pre-release outcome. The loaded-and-held target, durable orphan-clear and
six-stage target-evidence requirements below remain the strict-mode contract;
they are not v1 requirements or silently removed from historical records.
Source exclusion, exclusive claims and uncertain-effect safety remain required
in both modes. Production activation remains evidence-gated.

**Current approved revision:** [retain native Claude subagents](native-subagent-decision.md).
Brett's 2026-09-16 decision is authoritative for this change: keep native
subagents, prefer exact native continuation, and allow model-assisted worker
restart after the account transition, with no written handoff for swap or
restart.

The 2026-09-18 [coordinator interrupt decision](coordinator-interrupt-decision.md)
selects a distinct whole-roster interrupt/drain transaction for further
implementation, based on bounded Stage 1 evidence. It preserves the native
architecture and zero-request requirement; it grants no runtime capability.

This is an OpenSpec governance and implementation-handoff decision for the
single `001-separate-swap-ctx-handoff` Speckit feature. It is not evidence that
the installed Claude runtime can safely stop, restore, or restart every native
participant. The first release is Claude-only, opt-in, and limited to runtime
and participant configurations whose control and restoration evidence is
published.

The decision explicitly supersedes the independent top-level per-child runner
architecture and the blanket native-subagent prohibition previously described
in this change and its linked feature. It also supersedes any assumption that
`run_in_background` is inherently unsafe: runtime-owned native background
subagents must be evaluated with their actual task IDs and lifecycle events.
Unmanaged detached processes remain unaccounted for. Earlier proposals,
implementation artifacts, durable records, and task lists remain historical
until separately reconciled; they are not silently reinterpreted, deleted, or
treated as acceptance evidence.

## Why

The existing swap path is coupled to semantic handoff work. It can spend model
requests, latency, and an exhausted account's remaining capacity before it can
change accounts. It also conflates three different user intents:

* continue the same coordinator and supported native child conversations under
  another authorized account;
* begin a fresh coordinator lineage from an intentional context checkpoint; and
* transfer understanding and responsibility to another reader or operation.

The user needs an external, mechanical account transition that can preserve
local work and refuse when participants or effects cannot be accounted for.
Native children make that boundary more precise: the coordinator transcript is
the lineage authority, while child agent/task identity and lifecycle must come
from the runtime rather than from invented top-level sessions or handoff prose.

## What changes

### Four explicit operations

| Operation | User outcome | Account and inference boundary | Conversation/worker policy |
| --- | --- | --- | --- |
| `swap` | Continue one supported native coordinator lineage after selecting an explicitly named authorized profile. | Account-control is external and makes zero new model requests. Startup, stop, exact load, and readiness remain held until `release`. | Resume the exact coordinator. A safely stopped child becomes `resume-pending` until a correlated post-release native continuation proves `exact-resumed`; when native continuation is unavailable, report `restart-pending` and use only the release-gated restart fallback. No written handoff or generated semantic checkpoint. |
| `ctx` | Start a deliberate fresh coordinator context under the current account. | It is an intentional context operation, not account control. Any checkpoint is explicitly supplied by the caller. | A `hold` policy stops and retains old native workers; it does not promise workers live beneath an exited parent. A restart policy creates new-lineage workers from the supplied checkpoint only after release; it never claims exact cross-parent rebind. Native worker treatment is finalized during re-planning. |
| `handoff` | Transfer work to a different reader or later operation. | Account is unchanged and no release is implied. | It records only a checkpoint explicitly supplied by the caller. It is the sole operation here that may write handoff material, and it is never implicit in swap or worker restart. |
| `release` | Deliberately permit normal model use after a safe transition. | This is the explicit inference boundary. Model-assisted child restart may consume target-account requests only after it. | Releases a matching ready operation once. A restart is reported only after correlated native task evidence, not on transport acknowledgement alone. |

No operation silently invokes another. In particular, swap never invokes
`ctx`, `handoff`, or `release`; worker restart never creates a handoff or a
semantic checkpoint; and `ctx` never changes account.

### One native coordinator lineage

A managed lane contains one native Claude coordinator transcript and the native
Agent/Task subagents that the coordinator actually owns. Native children are
not independently launched top-level SDK sessions. The adapter captures the
runtime's actual agent ID, task ID, parent linkage, task definition, model,
effort, permissions, custom-agent definition, hooks, and lifecycle/tool facts;
it never invents a child identity. An opaque or UUID-shaped native agent ID is
still not a per-child top-level session UUID, process group, session name,
mailbox, or login.

Children share the coordinator's operating-system process tree, account, and
session naming. The external supervisor may own one durable lane operation and
prove containment of that enclosing runtime tree, but it must not pretend that
each child has an independently stoppable process group. Child-targeted input
after release travels through the coordinator/native interface using the
captured native identity. It never uses the old per-worker SDK send/open
surface, and this change does not invent child `open`, `shutdown`, or `release`
APIs. The existing coordinator session/lane guard remains anchored to the
exact coordinator transcript/session identity; it is not bypassed or
generalized into invented child session identities.

The reusable external coordinator/supervisor remains the model-independent
owner of lane admission, account transition, operation serialization, durable
mechanical evidence, legacy exclusion, and worktree safety. It observes and
requests supported parent/runtime boundaries; it does not replace the native
worker architecture with independent runners or model-authored orchestration.

### Native participant scope is evidence-led

Native teams are out of scope for this release and refuse by default; a later
separately governed extension may add a team participant after a pinned
runtime probe. Team support is not an acceptance prerequisite here. Native
background subagents are likewise not blanket-rejected: a runtime-owned
background task with a captured native task/agent ID and correlated lifecycle
events is evaluated for controlled stop and restart. A `run_in_background` flag
alone, a parent exit, or an operating-system suspension is not evidence of
quiescence.

An unmanaged detached shell/process, unknown descendant, or effect that cannot
be attributed to the coordinator lineage is unsupported. It causes a refusal
or held/indeterminate state rather than a claim that the native graph is safe.

## Model-independent account control

The external control phase makes no new model request. That guarantee covers
profile resolution, graph discovery, admission and input fencing, native stop
and drain, durable state writes, target startup, exact coordinator loading,
startup-orphan checks, child transcript verification, and readiness checks. It
does not cover ordinary model use after an explicit release.

Before planned shutdown, the adapter must prove that the selected pinned
runtime has a supported hold boundary during parent startup. In particular, it
must prevent or durably observe and suppress orphan-child auto-resume before
`release`. Promptless parent initialization by itself is insufficient: if
startup can dispatch an orphan child without an explicit query and the runtime
cannot hold that dispatch, the configuration is unsupported and the original
runtime remains untouched. A fake parent that merely reports initialization
does not establish this gate; the installed runtime/version must be tested.

The probe names the exact SDK package, selected CLI path, binary/version/digest,
and actual launch mode; a version traced outside the SDK's bundled-first
selection is not evidence for the runtime actually used. Interactive takeover
is an orphan-auto-resume hazard, and print/stream-json mode alone is not a
no-inference boundary: the selected bundled runtime has been observed to wake
restored `running_background_tasks` through `restoredOrphans`, the default
enabled wake path, and `enqueuePendingNotification`. Before target startup,
all source children therefore need terminal stop evidence and durable orphan
state must be cleared (without deleting the external child ledger); the target
mode must pass a no-wake/no-model fixture.
SDK stream-json remains Gate 0 until that exact fixture passes. A supported
non-auto mode still requires current-run child/tool quiescence and does not
rely on a synthetic classifier marker merely to suppress a callback.

The operator explicitly selects an authorized target profile. Read-only profile
resolution verifies account identity, transcript-storage family, model/effort,
tools, permissions, workspace, custom-agent definitions, and other launch
settings. It does not mutate launcher/configuration files, copy credentials,
perform a paid auth/model/quota probe, or weaken permissions. Inherited
provider-auth overrides are removed from the target environment. Setup-token
profiles, missing identity, incompatible storage, and unsupported runtime
boundaries refuse before planned shutdown.

The coordinator resumes by the official exact transcript UUID path with
promptless initialization under the target profile and remains held. A target
account loading the parent transcript does not prove that its children can be
continued. For exact continuation, cross-account transcript access is a
verification gate: the native child transcript, captured agent/task identity,
parent linkage, immutable task definition, and correlated runtime evidence
must all be valid under the target profile. Missing or inaccessible child
history prevents exact continuation and therefore cannot be labeled
`exact-resumed`. It does not alone prevent the approved new-run fallback: when
current-run stop/tool/effect state is proven and the parent/native task records
still provide the original task, model, effort, and custom-agent definition,
report
`restart-pending` even without child-history access. Missing or contradictory
identity, current-run stop/effect, or parent/native task records is
`unresolved`; an unknown effect is never downgraded to restart-pending.

## Honest worker outcomes and effect safety

Each unfinished child receives one observable restoration status. Before
`release`, an unfinished child is `resume-pending`, `restart-pending`, or
`unresolved`; `exact-resumed` and `restarted` require correlated post-release
evidence:

* **resume-pending** — the child was safely stopped and its exact native
  identity/transcript is eligible for the tested native continuation path, but
  no post-release continuation evidence exists yet;
* **exact-resumed** — after release, correlated native evidence proves that the
  same captured child identity and transcript continued under the resumed
  coordinator and target profile;
* **restart-pending** — safe coordinator restoration, current-run stop/tool/
  effect state, and original task/model/effort/custom-agent definition records
  from the parent/native runtime are available, but exact native continuation is
  unavailable or not proven. Child history need not be accessible for this
  new-run fallback. No restart instruction is sent before release;
* **restarted** — after explicit release, a model instruction through the
  resumed coordinator was accepted and a correlated native task/agent start or
  progress event proves a new run. This does not prove the new run has the old
  conversation or identity; or
* **unresolved** — required native IDs/parent linkage, current-run
  stop/tool/effect evidence, parent/native task records, ownership, startup
  hold, or effect state is missing or contradictory. Unknown effects remain
  unresolved even when a new-run fallback could otherwise be formed.

A `resume-pending` child may follow the tested native continuation path only
after `release`; the same identity/transcript and a correlated current-run
event are required before it becomes `exact-resumed`. If that path is not
available, the child is `restart-pending` for the model-assisted fallback only
when current-run stop/effects and parent/native task, model, and definition
records remain proven; otherwise it is `unresolved`.
An accepted-send acknowledgement means only that an instruction reached the
native/coordinator dispatch boundary. It is not proof of a restart. The
controller waits for a correlated native event and records the attempt; a
partially started set is reconciled by actual events, not resent wholesale.
A user-cancelled or interrupted restart remains pending or unresolved until
evidence establishes its terminal state. No automatic retry may duplicate a
possibly started child.

Completed child work remains complete and is never replayed. An unknown result
of a tool or external effect (for example a deployment, push, or remote
mutation) remains unresolved and blocks replay and release until explicitly
reconciled. Neither exact continuation nor model-assisted restart grants
permission to repeat work with an uncertain outcome.

## Writer and worktree safety

Writer exclusion belongs to the owning session lineage: a live writer is
attributable to exactly one coordinator transcript/lineage and lane owner, not
to an invented top-level child session. A read-only coordinator may own a
writable native child, but parent read-only status does not broaden that
child's tools or permissions. The child must be attributable by its actual
agent/task ID and immutable definition; an unknown child or unenforceable
permission boundary refuses.

An isolated worktree claim is optional for a native child. When selected and
supported, it is keyed by the actual child ID beneath its coordinator lineage
and uses the existing realpath, alias, and ancestor/descendant exclusion rules.
Claims never create a second owner or process group, and a claim is released
only after authoritative native completion/stop, tool quiescence, and effect
reconciliation. Shared worktree writes still require one lineage owner and
must not allow duplicate live writers. Dirty and untracked files remain in
place; swap never commits, pushes, stashes, resets, cleans, moves, or rebuilds
a worktree.

## Durable state and legacy safety

Retain the reusable external supervisor state, private path checks, atomic
operation lock, bounded local control transport, profile resolver, ownership
interlock, crash/retry identity, and legacy command refusal. The record is
mechanical evidence only: operation and generation IDs, profile references,
coordinator transcript identity, actual child agent/task IDs, parent links,
definitions/settings fingerprints, lifecycle and hook/tool events, enclosing
process-tree ownership, optional worktree claims, dispatch attempts, outcome
statuses, and unresolved effects. It contains no credentials, tokens,
conversation bodies, generated prose, semantic checkpoint, or handoff text.

The record declares its participant mode. A record written by the superseded
independent-worker prototype is not a native-lineage record and cannot be
silently interpreted as one. Recovery either uses that prototype's explicit
legacy contract or refuses with an explicit migration/recovery action; it does
not delete, rewrite, or launch over the old owner. Native enrollment also
refuses ambiguous live or unknown legacy ownership. A durable managed owner
continues to exclude legacy launch if its external supervisor is unavailable.

## Scope and non-goals

In scope:

* one external, model-independent supervisor for an explicitly enrolled
  coordinator/native-subagent lineage;
* actual native agent/task discovery and a child ledger joined to lifecycle,
  hook, parent, and tool evidence;
* exact coordinator resume and exact native child continuation where tested;
* release-gated model-assisted restart with no generated handoff/checkpoint;
* startup orphan-auto-resume prevention and zero-new-model-request account
  control;
* honest worker statuses, completed-work/effect preservation, and retry safety;
* lineage-level writer exclusion with optional isolated-worktree claims;
* reusable profile, state, local transport, ownership, and legacy safety; and
* separate `swap`, `ctx`, `handoff`, and `release` contracts.

Out of scope:

* independent top-level per-child sessions, per-child SDK lifecycle methods,
  child logins, child UUID/PGID/session-name ownership, or mailbox-based child
  orchestration;
* native teams in this release (they refuse by default), or a blanket claim
  that all background modes are supported;
* unmanaged detached process containment, OS memory/process snapshots, or
  safety inferred from suspension alone;
* generated semantic handoffs/checkpoints during swap or worker restart;
* automatic account discovery/rotation, credential migration, quota guarantees,
  cross-machine migration, or Codex support; and
* silently reinterpreting the superseded independent prototype state.

## Impact and ownership

openRepoTools owns managed enrollment, the external operation authority,
account-control sequencing, native evidence ledger, writer/effect safety,
status, and the thin `lane-swap` boundary. The Claude adapter owns only the
runtime-specific discovery, parent/runtime stop boundary, promptless exact
coordinator load, native event correlation, and capability report; it may not
invent child APIs. workBenches owns read-only profile metadata, credential
isolation, storage-family identity, and the supported launcher boundary.

The official Claude SDK/runtime is an optional, lazy adapter dependency. Its
absence or an unverified runtime boundary is a capability refusal, not an
installation side effect. Existing recovery/context owners must agree on one
lane operation authority and explicit record modes before implementation
resumes.

## Delivery and acceptance gates

1. Reconcile the protocol and aliases to this native-lineage decision while
   keeping `ctx` and `handoff` separate and preserving historical meanings.
2. Demonstrate, with fake/local runtimes for controller logic and the pinned
   runtime for capability claims, native child discovery and stop boundaries,
   the child ledger, an active child after `PostToolUse(Agent)` returns,
   runtime-owned background behavior, and startup orphan-auto-resume
   prevention without a model request.
3. Demonstrate exact coordinator resume under the selected account and the
   cross-account child-transcript gate. Publish actual runtime versions,
   participant kinds, task/agent fields, lifecycle/hook events, and tools.
4. Demonstrate completed-child/effect preservation, lineage writer exclusion,
   dirty-work preservation, retry/crash behavior, accepted-send versus
   correlated restart, resume-pending/exact-resumed and partial-start
   reconciliation, and user-cancel handling.
5. Keep model-assisted restart outside the account-control measurement and
   behind explicit `release`. If the runtime cannot hold startup or account
   control, refuse before shutdown. Live authentication/model use remains
   `UNVERIFIED` until a separately authorized probe supplies evidence.

The linked Speckit feature remains the sole executable implementation owner;
OpenSpec does not duplicate its task list. Existing conflicting specs/tasks
and implementation progress require re-planning against this governance
decision before release and do not establish acceptance by themselves.

## Open questions and unresolved architecture decisions

The following remain explicit release blockers rather than permission for a
silent fallback. The [governance review](governance-review.md) records a
**PROPOSED — NOT APPROVED** mapping for the Amendment 17 supersession,
PR #121 integration, shared lifecycle authority, capability dispositions, and
release decisions; it does not change these blockers or claim a landing.

* Which pinned Claude runtime/version and launch mode expose a hold boundary
  that prevents startup orphan auto-resume before release?
* Which actual native agent/task IDs, hook events, and task lifecycle events
  are stable enough to correlate across account transition and restart?
* Which native child stop behavior (model stop versus external cancellation),
  active-tool boundary, and runtime-owned background mode can be supported?
* What target-account transcript/storage evidence permits exact child
  continuation, and when can parent/native task records safely support the
  new-run fallback without child-history access while preserving model,
  effort, permissions, custom-agent definitions, hooks, and tools?
* Which shared lifecycle-record extension will existing recovery and context
  owners accept, including an explicit refusal/migration path for old
  independent-worker records?
* Which approving authority will cite the proposed [Amendment 17 and shared
  lifecycle governance review](governance-review.md), and which exact
  cross-repository revisions and disposable canary scope may proceed? Until
  then, PR #121 and its supervisor artifacts remain an unmerged integration
  input, not managed-native state or release evidence.

## References

* [Approved native-subagent decision](native-subagent-decision.md)
* [Lane Session Operations brainstorm](../../../ideation/brainstorm/lane-session-operations-overview.md)
* [External supervisor exploration](../../../ideation/brainstorm/lane-session-operations-external-supervisor.md)
* [Worker restoration exploration](../../../ideation/brainstorm/lane-session-operations-worker-restoration.md)
* [Claude-first evidence and delivery gates](../../../ideation/brainstorm/lane-session-operations-evidence-and-delivery.md)
