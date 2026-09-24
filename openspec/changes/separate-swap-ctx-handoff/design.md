# Design: Native Claude Subagent Session Operations

## Current mode-specific amendment

The approved [stop-then-resume-v1 decision](stop-then-resume-decision.md)
introduces a distinct opt-in path: prepare and safely stop the source, retain
claims, report `ready-to-resume` without creating a target, then persist explicit
release authority before exact target resume. Read the linked
[v1 contract](../../../specs/001-separate-swap-ctx-handoff/contracts/stop-then-resume.md)
for ordering, recovery and proof obligations. All held-target and six-stage
flows below remain strict mode, not an implementation shortcut for v1.
Neither omission of a mode nor an old record selects v1. The first delivery
gate is its own bounded pinned-runtime experiment, not reuse of a probe that
starts the target before release.

## Bite 4 diagnostic status

The proposed [source-only diagnostic design](../../../specs/001-separate-swap-ctx-handoff/contracts/source-only-diagnostic.md)
and [five-bite operator runbook](../../../specs/001-separate-swap-ctx-handoff/runbook.md)
define a bounded experiment with separate source and target containers, an
external observer/custodian, source removal before target creation, immutable
source history plus an exact-byte target copy, and durable release before one
exact-parent target launch. T047/T048 and the T049 diagnostic query mode passed
architecture review and formal offline gates. The separately authorized
thirteenth runtime run exited 2, INCONCLUSIVE with
`effect-or-observer-uncertain`, after source stop/removal and target-state
volume creation but before copy, release, or target launch. The inner source
exception was not retained; an unbound `parent_uuid` reference in the
legacy/source initializer is a deterministic static cause candidate, not a
directly proven historical exception. T050 is the approved future-only
correction. No fourteenth run is authorized. This does not create a positive
production containment witness or change activation authority.
`support_claim: false` remains required; Bite 5 and production support remain
pending/unsupported.

## Context

The shipped lane workflow couples account swap, context reset, and semantic
handoff. That coupling can spend a model request when the source account is
exhausted, and it does not say what happens to native Claude subagents owned by
the coordinator. The approved revision keeps that native architecture. It
therefore needs an external, model-independent boundary around one native
coordinator lineage, plus evidence strong enough to distinguish exact child
continuation from a new model-assisted run.

This design governs the linked `001-separate-swap-ctx-handoff` feature. It is a
compatibility contract and evidence plan, not proof that a particular Claude
release supports every boundary below. A runtime or participant kind that
cannot pass the gates refuses before planned shutdown.

The [coordinator interrupt decision](coordinator-interrupt-decision.md) governs
the selected stop candidate. Its
[durable interrupt contract](../../../specs/001-separate-swap-ctx-handoff/contracts/coordinator-interrupt.md)
is distinct from the existing task-specific stop transaction. Stage 1 found
zero cancellation-phase requests for coordinator interrupt in one settled
scripted gateway fixture, while task-specific stop produced one. Full-interval,
busy-parent, multiple-child and actual-account support remain unverified.

## Goals and non-goals

### Goals

* Keep one native Claude coordinator transcript and its native Agent/Task
  subagents in one execution lineage.
* Start account `swap` outside model inference, make zero new model requests
  through readiness, and prevent startup orphan-child auto-resume before an
  explicit `release`.
* Prefer exact native child continuation where the pinned runtime proves it;
  otherwise permit a model-assisted worker restart only after release and
  without writing a handoff or generated semantic checkpoint.
* Capture actual agent/task IDs and parent, hook, lifecycle, tool, process, and
  effect evidence, and report resume-pending, exact-resumed, restart-pending,
  restarted, or unresolved honestly.
* Preserve completed work and uncertain-effect safety, dirty local work,
  lineage-level writer exclusion, and the reusable external supervisor,
  profile, state, transport, and legacy ownership safeguards.
* Keep `ctx`, `handoff`, and `release` materially distinct and observable.

### Non-goals

* Independently launched top-level child SDK sessions, per-child logins,
  top-level UUIDs, process groups, session names, mailboxes, or child-specific
  lifecycle APIs.
* Treating the parent `Agent` tool return as proof that a native child stopped,
  or treating `run_in_background`, parent exit, or OS suspension as proof of
  quiescence.
* Native teams in this release (they refuse by default), or assuming any
  background mode is supported without a pinned-runtime probe.
* Generated semantic handoffs/checkpoints during swap or worker restart,
  automatic account rotation, credential copying, or live quota probes.
* Silent interpretation, deletion, or takeover of durable state from the
  superseded independent-worker prototype.

## System architecture and authority

### One coordinator lineage

A managed lane has exactly one native coordinator transcript and the native
subagents/tasks that the coordinator actually creates. The coordinator's
transcript UUID is the exact conversation identity restored by `swap`. A child
is identified only by the agent/task identity emitted by the runtime, together
with its parent coordinator and task-definition linkage. The adapter must
capture these values from runtime records/events; it must never manufacture a
child identity or promote a child to a top-level SDK session. An opaque or
UUID-shaped native agent ID may be recorded, but it is not a per-child
top-level session UUID.

Native children share the coordinator's OS process tree, account, and session
naming. There is no per-child process group, login, tmux/session name, or
independent transcript owner for this design. Process containment is therefore
proved for the enclosing coordinator runtime tree, while native child
ownership is proved separately through agent/task, hook, lifecycle, and tool
evidence. A child-specific process-group handle cannot be substituted for
that evidence. The existing coordinator session/lane guard remains anchored to
the exact coordinator transcript/session identity; it is not bypassed or
generalized into invented child session identities.

The external supervisor remains one model-independent coordinator for lane
admission, operation serialization, account transition, durable mechanical
state, legacy exclusion, and writer/effect safety. It may call boundaries that
the installed runtime actually exposes and may observe its events; it does not
run a second model workflow and does not own independent child runners.

Child-targeted submission after `release` is routed through the resumed
coordinator/native interface using the captured native identity. It never uses
the old independent per-worker SDK send/open path. This design invents no child
`open`, `shutdown`, or `release` API. If the runtime has no supported way to
route, stop, or observe a child, that capability is unsupported or unresolved;
the controller does not emulate it with an unrelated top-level session.

### Explicit record modes and legacy interlock

Every managed operation record declares its participant mode, for example
`native-lineage` or the superseded independent-worker prototype mode. Native
code refuses a record whose mode or schema it does not understand. A record
from the old prototype is preserved and either handled by its explicit legacy
contract or directed through an explicit migration/recovery decision; it is
never silently reinterpreted as a native graph, deleted, or overwritten.

Enrollment and legacy launch continue to use one atomic ownership boundary.
A live or unknown legacy holder causes a zero-change refusal. Once native
managed ownership is durable, legacy `lane`, `lane-start`, and
`lane-handoff`/handoff surfaces refuse that lane even if the supervisor is
temporarily unavailable. A supervisor crash leaves recoverable ownership, not
permission for a second coordinator.

The existing external state safeguards remain reusable: private path and mode
checks, a serialized lane lock, bounded local control transport, atomic
records, operation/generation IDs, crash/retry reconciliation, and a
human-facing register projection through supported helpers. The projection is
not a second lifecycle authority.

## Runtime adapter and evidence contract

The Claude adapter is lazy and versioned. Its capability result names the
installed runtime version, launch mode, participant kinds, hooks, event fields,
and tool classes actually tested. Fake runtimes can prove supervisor logic but
cannot turn a live capability into `SUPPORTED`.

### Discovery and native child ledger

Before a swap fence, the adapter discovers the coordinator and every native
child from runtime-owned records/events. It persists a mechanical child ledger
row containing, when available:

* coordinator transcript UUID and lane generation;
* actual native agent ID and task ID, parent/task linkage, and runtime event
  sequence or correlation token;
* immutable task/custom-agent definition and model, effort, tools,
  permissions, hooks, and workspace fingerprints;
* transcript/storage-family and account-access evidence;
* native lifecycle state, tool invocation state, enclosing process-tree
  ownership, optional isolated-worktree claim, and unresolved effect; and
* restoration state and every dispatch/restart attempt with its evidence.

The ledger joins native child lifecycle with hook and tool evidence. In
particular, `SubagentStart`/`SubagentStop` and the runtime's task events such
as `task_started`, `progress`, `notification`, and `task_updated` are recorded
when the pinned runtime exposes them. A `PostToolUse(Agent)` event means only
that the parent Agent tool invocation returned. It does not close the child
row: a background child can remain active after that return. The row remains
running until a correlated native stop/completion/failure event and all tool
and effect evidence are terminal. Missing or contradictory event joins leave
the child unresolved. A reused agent ID is not enough to correlate a later
notification: correlation also requires the task/parent invocation and an
event watermark or equivalent current-operation evidence, so a stale event
cannot prove a new run.

The adapter must distinguish a model-stopped child from one externally
cancelled by the SDK/user. The installed runtime's continuation behavior for
both outcomes is tested rather than assumed. A cancellation acknowledgement,
parent exit, or process disappearance alone is not a terminal native-child
proof.

### Participant kinds and background behavior

Native Agent/Task subagents are the intended participant kind. Native teams are
out of scope for this release and refuse by default; a later separately
governed extension may add a team kind after a versioned probe. Team support is
not an acceptance prerequisite here.

A runtime-owned native background subagent is evaluated, not blanket-rejected.
It must have an actual agent/task identity, lifecycle events, a tested parent
stop/hold boundary, and enough tool/effect evidence to remain accounted for
after the parent Agent tool returns. `run_in_background` is merely a mode bit,
not proof of danger or safety. An unmanaged detached shell/process, unknown
descendant, or unowned external effect has no such ledger and forces refusal or
held/indeterminate state.

### Parent startup hold is a capability gate

The target runtime must support a tested hold boundary that prevents native
children from inferring while the resumed coordinator is being initialized.
The gate specifically covers orphan-child auto-resume: promptless parent
initialization alone is insufficient evidence. Before stopping the source
runtime, the adapter checks the pinned runtime/configuration capability. If
startup can dispatch an orphan child without an explicit query and cannot be
held or durably observed and suppressed, the configuration is unsupported and
the source remains untouched.

The capability probe records the exact SDK package, selected CLI path,
binary/version digest, and launch mode; a version traced outside the SDK's
bundled-first selection is not evidence for the runtime actually used.
For the current probe, SDK 0.2.153's bundled-first selection has been observed
to choose CLI 2.1.273 rather than an installed 2.1.270; the earlier binary's
trace cannot close this gate. The full selected binary digest and mode remain
required evidence.
Interactive takeover is an orphan-auto-resume hazard, and print/stream-json
mode alone is not a no-inference boundary: the selected bundled runtime has
been observed to wake restored `running_background_tasks` through
`restoredOrphans`, the default-enabled wake path, and
`enqueuePendingNotification`. Before target startup, all source children
therefore need terminal stop evidence and durable orphan state must be
cleared without deleting the external child ledger; the target mode must pass a
no-wake/no-model fixture. SDK stream-json remains Gate 0 until that exact
fixture passes. A supported non-auto mode
still requires current-run child/tool quiescence and does not require a
synthetic classifier marker merely to suppress a callback.

During a supported target startup, any child lifecycle or tool event before
the held-ready transition is correlated to the sealed operation. An
unapproved child dispatch, an event that cannot be held, or a startup event
whose parent/task identity is unknown makes the operation unsupported or
indeterminate; it is never described as zero-model-request success.

### Profile and cross-account transcript boundary

The profile resolver reads the explicitly selected target profile and metadata
through the supported workBenches boundary. It verifies expected account
identity, transcript-storage family, model, effort, permissions, tools,
workspace, custom-agent definitions, hooks, and other launch settings. It
removes inherited provider-auth overrides but does not copy credentials,
mutate launcher/configuration files, replace live authentication, or issue a
model/auth/quota request. Setup-token profiles, missing identity, incompatible
storage, or an unsupported runtime refuse before planned shutdown.

The coordinator uses the official exact transcript UUID resume path with
promptless loader initialization under the selected profile. The adapter does
not require initialization to echo optional session/model fields; it relies on
the prevalidated transcript, exact resume argument, loader success, and the
recorded fingerprints.

Cross-account access to a child transcript is a separate verification gate.
Loading the parent transcript under the target account does not establish that
the child transcript is readable, still has the same agent/task identity, or
retains its parent linkage, immutable definition, model/effort, permissions,
custom-agent definition, hooks, and tools. All of that evidence is required
before a child can be labeled `exact-resumed`; missing or inaccessible child
history therefore prevents exact resume. It does not alone prevent the
approved new-run fallback. If current-run stop/tool/effect state is proven and
the parent/native task records still provide the original task, model, and
definition, report `restart-pending` even when child history is inaccessible.
Missing or contradictory native identity, current-run stop/effect evidence, or
parent/native task records is `unresolved`; an unknown effect is never
downgraded to restart-pending and blocks readiness/release.

## Ownership and writer policy

### Lineage-level exclusion

The ownership principal for writes is the coordinator session lineage and lane
generation. There is one active writer owner per lane/lineage, not one
independent top-level owner per native child. If any native child can write,
the containing coordinator lineage retains the writer claim until every such
child is authoritatively stopped/completed, its tools are quiescent, and its
effects are reconciled. A read-only coordinator may therefore own an
authorized writable child; the coordinator's read-only label does not grant
that child additional tools or permissions.

The writable child must be attributable to its actual agent/task ID and an
immutable definition/permission fingerprint. An unknown child, a definition
that changed without evidence, or an SDK that cannot enforce the authorized
child boundary refuses. A replacement child is not allowed to write while the
old lineage or an ambiguous effect remains live.

### Optional isolated-worktree claims

An isolated worktree per native child is optional, not a new lifecycle model.
When selected and supported, the claim is keyed by the actual child agent/task
ID beneath the coordinator lineage and uses the existing realpath, alias, and
ancestor/descendant conflict rules across lanes. It never creates a child
process group or top-level session. Shared worktree writes are allowed only
under one lineage writer policy with no concurrent unaccounted writer.

Claims accept dirty and untracked files and preserve them. Swap does not
commit, push, stash, reset, clean, move, or reconstruct any worktree. A claim
is released only after authoritative native completion/stop, tool quiescence,
and effect reconciliation; a client completion flag alone is insufficient.

## Durable operation state and phases

The operation record stores only mechanical facts: schema/mode, operation and
generation IDs, source/target profile references, coordinator transcript UUID,
native child IDs and definitions, lifecycle/hook/tool/process evidence,
optional claims, readiness evidence, dispatch attempts, worker outcomes, and
unresolved effects. It stores no credentials, tokens, conversation bodies,
generated prose, semantic checkpoint, or handoff text. Runtime process handles
and resolved host paths remain host-local.

The shared lane authority serializes `enroll`, `submit`, `swap`, `ctx`,
`handoff`, `release`, recovery, shutdown, and unenrollment. Conceptual phases
are `preflight`, `fenced`, `quiescing`, `paused`, `starting`, `ready-held`,
`released`, and `failed`/`indeterminate`. A second operation receives the
active operation identity and performs no lifecycle change.

## Private native-swap evidence seam

The tranche-2 swap design admits one private constructor-only synchronous
read-only hook, `_native_swap_evidence_provider(binding)`, whose default is
absent (`None`). It is not a public operation, request field, stored boolean,
or caller authority. It supplies only a missing independent observation of the
continuous request epoch or supported worker-state clearing; it never performs
an interrupt, child/tool stop, process/effect exclusion, coordinator open,
release, or other runtime mutation. Static exact-mode admission still comes
from `_capability_evidence_provider` and `runtime.preflight_held_swap` first.

The exact binding is the schema-v2
`native-swap-evidence-request` binding in the [managed-control
contract](../../../specs/001-separate-swap-ctx-handoff/contracts/managed-control.md):
`stage` is one of `entry`, `graph-drained`, `source-excluded`, `target-held`,
`pre-release`, or `release-boundary`; it binds the operation, positive owner
generation, expected daemon, strict `_native_source_identity`, source context
and claim digests, normalized target-spec digest, one request epoch, and the
stage-appropriate interrupt, archive, target-runner, release ID/intent digest,
and exact SDK release-boundary binding. Null identities are allowed only before
they exist and become immutable once bound. The response echoes that binding
exactly and carries the pinned runtime identity digest, bounded evidence
reference, epoch observation, and stage-appropriate worker-state-clear
observation defined by [the data model](../../../specs/001-separate-swap-ctx-handoff/data-model.md).
The exact SDK release binding and synchronous boundary receipt are frozen in
[runner-evidence.md](../../../specs/001-separate-swap-ctx-handoff/contracts/runner-evidence.md);
the release-boundary receipt is not itself the independent epoch proof.

The same epoch and stable entry reference span account-control entry through
the synchronous release boundary. The controller validates the exact pinned
runtime identity across all six append-only stage observations, the authorized
normalized target specification, and immutable source context/claim digests.
`pre-release` runs after durable release intent and before the native release
call, including its bounded idle delay. The SDK's exact bound
held-to-released gate event and watermark define `release-boundary`; the
provider observes the historical interval through that endpoint, while later
requests are outside the interval. A receipt alone is ordering/correlation
evidence, not final proof.

Provider evidence is sticky: positive, unknown, and gap observations are not
repaired by a later zero. Missing or contradictory final proof records any
receipt and uncertain effect, retains claims, and permits neither a daemon
pump nor replay; it does not claim the acknowledged runtime is still held.
Missing hook/pinned proof refuses before source interrupt. Fake constructor
providers are offline test evidence only and do not claim production native
support.

The existing ownership boundaries remain: `controller.py` owns the private
seam and durable stage orchestration; runtime adapters own SDK capability,
interrupt, shutdown, open, ready, and release-boundary facts; daemon
route/socket fixtures own their route tests. This tranche adds no production
module and no public operation flag, and does not claim that a native runtime
capability is installed.

## Swap flow

1. **Preflight without model work.** Acquire the lane authority; create the
   immutable request-observation epoch and `entry` evidence binding, then
   validate canonical lane/workspace identity, native record mode, managed
   ownership, target profile, pinned runtime/version, startup hold capability,
   current writer/effect ownership, and the exact discovered child ledger.
   Refuse unsupported setup-token/profile/storage/runtime configurations before
   stopping the source.

2. **Fence and seal.** Atomically stop new coordinator input and native child
   admission through a boundary the runtime actually exposes, then seal the
   discovered roster. A racing child is either rejected before launch or
   appears in the sealed ledger with actual parent/task identity. A boundary
   that cannot account for the race is unsupported. Mechanical input can be
   retained as pending, but no model request is made.

3. **Stop and drain the native graph.** Use the supported coordinator/runtime
   interrupt boundary only after a complete native roster is sealed and a
   distinct whole-roster intent/possible-send marker is durable. Authorize at
   most one call on the existing coordinator connection; a lost receipt or a
   changed request ID never permits automatic resend. Keep persistence and
   event readers live while awaiting control. Do not call an invented child
   shutdown API or reuse a task-specific stop authorization. Join
   `SubagentStart`/`SubagentStop`, task lifecycle, hook, and tool evidence; do
   not close a child because `PostToolUse(Agent)` returned. Runtime-owned
   background children remain tracked until terminal. Unknown descendants,
   externally detached processes, active tools without terminal evidence, or
   an unowned effect keep the lane paused/indeterminate.

   Interrupt may initiate child stopping while the source parent remains
   alive. Its receipt, parent-turn drain, each current-run child terminal,
   each tool/effect outcome and process exclusion are independent facts.
   A child that naturally completes during drain remains completed. Membership,
   identity or definition drift after sealing invalidates the operation;
   ordinary correlated lifecycle progress advances evidence without rewriting
   the identity seal. Parent shutdown follows authoritative child/tool
   quiescence and required supported worker-state clearing. Record the
   `graph-drained` evidence only after the coordinator interrupt status is
   graph-quiescent and the independent epoch/clear observation is correlated.

4. **Persist the safe boundary.** Record the paused operation, writer claims,
   process-tree ownership, pending work, and completed children. Persist the
   shutdown intent and invoke the supported `runtime.shutdown` at most once;
   only then prove old coordinator/child/process/effect exclusion and record
   `source-excluded`. Archive the exact source mechanically and retain the
   immutable archive; retries reuse it and never recapture a changed snapshot.
   A possible external mutation whose result is unknown is unresolved and
   blocks replay; cancellation acknowledgement does not undo it.

   The request-observation epoch begins at account-control entry before
   preflight and spans fence, interrupt, drain, old-writer exclusion, held
   target readiness, pre-release, and the synchronous release boundary. It is
   not restarted after a control acknowledgement or daemon takeover. Already
   in-flight pre-entry
   requests are identified separately; every new attempt belongs to this
   interval. Any positive or unobservable interval blocks zero-request
   success, regardless of later termination. Interrupt is not itself a
   persistent inference fence, and a gateway rejection is already a request.

5. **Load one exact coordinator, still held.** After source exclusion, run
   dedicated staged target preparation, persisting a new target-runner
   incarnation and exact resume/open specification and intent without relaxing the
   startup helper's changed-runner refusal. Start the explicitly selected
   target profile and promptlessly resume the exact coordinator transcript
   UUID once. The runtime's startup hold prevents orphan-child inference.
   Verify account identity, storage family, permissions,
   model/effort/tools/workspace, custom-agent definitions/hooks, process
   ownership, writer claims, and workspace identity while no participant is
   released, then record `target-held`. The target runner is new, but the
   coordinator UUID, lineage, lineage generation, claim, and owner generation
   remain exact. Retain the source archive until atomic target activation.
   Native swap does not use the `native_adoption` claim-pair CAS: that strict
   helper belongs to `ctx`'s new lineage/new UUID path.

6. **Verify or defer each child.** For every unfinished child, first verify
   actual agent/task identity, parent linkage, immutable task/model/effort/
   custom-agent definition records, current-run lifecycle/tool stop, and effect
   state. If the
   cross-account child transcript is accessible and the tested native path is
   eligible, the child is `resume-pending`; `exact-resumed` is recorded only
   after release, when correlated post-release evidence proves the same native
   binding or continuation. Missing or inaccessible child history prevents
   exact resume but does not alone prevent the approved fallback: with the
   current-run and parent/native task, model, effort, and definition records
   proven, report `restart-pending`.
   Missing or contradictory native identity, stop/effect state, or
   parent/native task records is `unresolved`; an unknown effect blocks the
   fallback. No child inference occurs before release. Completed children
   remain completed and are never relaunched.

7. **Ready held, then explicit release.** Commit `ready-held` only after all
   safety and coordinator checks pass. `release` is a separate, explicit,
   at-most-once transition. For native swap, persist a new `release_id` and
   `release_intent_digest`, obtain the `pre-release` observation after the
   durable intent and before the native release call (including the bounded
   idle delay), then require the SDK's exact synchronous held-to-released gate
   event and `release-boundary` observation before phase `released` or any
   daemon pump. Native swap requires this new bound receipt; the
   backward-compatible `runtime.release` endpoint for other operations is not
   a fallback. Missing or contradictory final proof retains claims and records
   an uncertain effect without replay or pump, and does not claim the
   acknowledged runtime is still held. It permits normal model work only after
   the bound transition. A `restart-pending` child is not restarted by swap
   itself.

8. **Continue or restart after release.** A `resume-pending` child may use the
   tested native continuation path after release. A correlated post-release
   event for the same child identity/transcript, parent invocation, and current
   event watermark changes it to `exact-resumed`; no child is labeled exact
   before that evidence. If the native path is unavailable or fails without an
   uncertain effect, the child remains or becomes `restart-pending`. The
   resumed coordinator may then receive an ordinary mechanically composed
   instruction referring to the captured native task/agent identity, preserved
   model/effort/custom-agent definition, and recorded status. The instruction
   is not a written handoff or generated semantic checkpoint, and it is never
   sent against the exhausted source account as a prerequisite. An accepted-send
   acknowledgement records only dispatch acceptance. The adapter waits for a
   correlated native task/agent start or progress event, tied to the parent
   invocation and current event watermark, before marking `restarted`; the new
   run is not claimed to have the old conversation or identity.

Partial starts are reconciled by actual attempt and lifecycle IDs. A child
whose restart event is correlated is not sent again merely because a sibling
failed. A user cancellation, lost event, contradictory parent/task link, or
deadline leaves that child `restart-pending` or `unresolved`; retry never
resends a possibly started child wholesale.

### Released same-runner invocation rollover

After release, the coordinator may move from invocation A to invocation B on
the same runner only after A has conclusive terminal proof. This is a bounded
mail-pump transition inside one operation: it keeps one coordinator open and
release boundary, preserves the exact owner/lineage/session/runner,
definitions, permissions, and claim, and does not create a child runner. The
daemon first selects one queued mailbox and persists a mutable preparation
intent, which is not itself a runtime reservation. Without holding the
controller lock across the runtime await, it checks the released phase and
daemon incarnation, then requests the bounded implementation-owned
`prepare-invocation` reservation and terminal proof. One atomic controller
snapshot then archives A into immutable history and writes B's current
context, startup binding, exact reservation binding, dispatch intent, and
operation snapshot together. Immediately before send, the daemon rechecks the
released phase, daemon incarnation, operation, B identity, mailbox, and exact
reservation, consumes that committed reservation, and attempts the send at
most once; an ordinary successful delivery occurs once and no later intent is
created. The detailed reservation, history, and crash rules are in the [managed control
contract](../../../specs/001-separate-swap-ctx-handoff/contracts/managed-control.md),
[runner evidence contract](../../../specs/001-separate-swap-ctx-handoff/contracts/runner-evidence.md),
[data model](../../../specs/001-separate-swap-ctx-handoff/data-model.md), and
[recovery lifecycle contract](../../../specs/001-separate-swap-ctx-handoff/contracts/recovery-lifecycle.md).

The design cases are explicit:

* A terminal A admits one later B and records the exact same-runner binding
  before the at-most-once correlated send; an ordinary successful delivery
  occurs once.
* A busy or pending A leaves B queued and consumes no reservation; the pump
  reports the bounded busy condition rather than opening, releasing, or
  inferring completion.
* A stale A callback is fenced by B's invocation identity and strictly newer
  watermark and cannot rewrite current state.
* An ambiguous send or rollover crash preserves the reservation and mailbox;
  immutable A history remains unchanged while uncertainty is recorded on the
  mutable rollover/dispatch record. It never resets, reopens, releases, or
  automatically replays the send.

## Worker outcome rules

The durable child ledger exposes these user-facing meanings. Before release,
an unfinished child is `resume-pending`, `restart-pending`, or `unresolved`;
`exact-resumed` and `restarted` require correlated post-release evidence:

* **resume-pending:** the child was safely stopped and its exact native
  identity/transcript is eligible for the tested continuation path, but no
  post-release continuation evidence exists yet.
* **exact-resumed:** post-release native evidence proves that the same child
  identity and transcript continued under the target account and exact
  coordinator.
* **restart-pending:** coordinator restoration and non-contradictory child
  records are safe, current-run stop/tool/effect state is proven, and the
  parent/native task records retain the original task, model, and definition,
  but external native continuation is unavailable or not proven. Child history
  need not be accessible for this new-run fallback. No model instruction has
  been sent before release.
* **restarted:** after release, the coordinator accepted a restart instruction
  and correlated native lifecycle evidence proves a new run. It is not proof of
  conversation or identity continuity.
* **unresolved:** required native identity/parent linkage, current-run
  stop/tool/effect evidence, parent/native task records, lifecycle, process,
  startup-hold, ownership, or effect evidence is absent or contradictory.
  Unknown effects remain unresolved even when a new-run fallback could
  otherwise be formed.

Completed work and known-complete external effects are retained as complete;
they are not included in exact-resume or restart instructions. Unknown effect
outcomes block replay and release until a separate explicit reconciliation.

## Context, handoff, and release flows

### `ctx`

`ctx` is a deliberate fresh coordinator context under the current account and
requires a checkpoint supplied explicitly by the caller. It does not derive a
checkpoint by asking a model during account control. Under a `hold` policy,
existing native workers are stopped and retained as records; they are not
promised to remain live beneath the exited parent. Under a restart policy,
workers are new-lineage workers created from the explicitly supplied
checkpoint only after `release`; there is no exact cross-parent rebind claim.
That caller-supplied checkpoint belongs to the existing context operation's
record, not the swap record; swap and worker restart never generate or persist
a semantic checkpoint.
Worker model, effort, tools, permissions, and custom-agent definitions remain
explicit requirements for any new run. Native worker hold/restart syntax and
its evidence are finalized in re-planning, not borrowed from the obsolete
independent-worker implementation.

### `handoff`

`handoff` is a separate, user-requested transfer operation. It may record an
explicitly supplied checkpoint for another reader, but it does not change
account, stop or restart native workers, alter writer claims, or release work.
Historical handoff records retain their original meaning and never establish
exact swap readiness. Swap and model-assisted worker restart write no handoff.

### `release`

`release` requires the matching `ready-held` operation and ownership generation
and is recorded once. It permits ordinary coordinator and native-worker model
requests, including a pending-worker restart, and is outside the
zero-new-model-request account-control phase. A stale, duplicate, or concurrent
release/swap/ctx/handoff refuses.

For native swap, that release is the six-stage boundary's final pair: the
controller persists `release_id`/`release_intent_digest`, obtains `pre-release`
before the native release call, and requires the exact SDK gate event and
`release-boundary` evidence through the synchronous held-to-released
transition. A receipt alone is not final proof. Missing or contradictory
evidence records the receipt and uncertain effect, retains claims, and starts
no pump or replay; it does not report an acknowledged gate as still held. The
backward-compatible `runtime.release` endpoint remains available only to
other operations and is not a native-swap fallback.

The existing released same-runner invocation rollover and its
`prepare-invocation` reservation interface remain unchanged. This native-swap
tranche begins only after that rollover integration; it does not consume,
replace, or generalize that reservation.

### Historical T047 bounded source terminal-task seed — future-only diagnostic

The ninth Bite 4 result was INCONCLUSIVE before release because its source
terminal seed was unavailable and its report projection did not retain the
reason. T047 repairs that diagnostic handoff only; it does not rewrite the
ninth-run evidence, change Bite 3 containment requirements, or enable public
lifecycle support. Astra's architecture review and Sol's 210-test formal
offline gate passed. The separately authorized tenth Bite 4 attempt ran once
and was INCONCLUSIVE before release/target creation because hook evidence was
incomplete. At that historical checkpoint its authorization was consumed and
no eleventh attempt had yet been authorized. T048 and the later separately
authorized eleventh run are recorded below; that later one-run authorization
is now consumed. No cleanup or twelfth attempt is authorized. Bite 5 remains
pending and production unsupported.

The source enables bounded `SubagentStart`/`SubagentStop` hook observation and
sanitizes SDK lifecycle subtypes with their actual optional-field shapes. A
`task_started` event is a source/setup or source/drain observation before the
terminal event. A transferable v2 seed keeps the started event, terminal
`task_notification`, and agent proof in separate digest-only envelope fields.
The terminal observation stays unchanged: source-side
`source_target_correlation` remains all `unknown` until target evidence
exists. Session/task proof must join the active source runtime and the exact
started task. The agent proof is either direct started-event evidence or a
hook binding exact on session and tool-use ID, with task ID also checked when
present. An unresolved early hook may be joined later only from those exact
digests; missing callback tool IDs, ambiguous/reused task or agent bindings,
conflicts, hook errors, malformed evidence, and overflow fail closed. No
single-child/cardinality or transcript-path inference is permitted.

Target correlation uses the terminal event's exact subtype, status, session,
and task. Missing SDK-optional `task_type`, `agent_id`, or `tool_use_id`
remains unknown rather than being synthesized; a present conflicting optional
agent/tool ID refuses correlation. `task_updated.patch.status` is recorded,
including `killed`, and a top-level/patch conflict is incomplete, but a
task_updated-only sequence is not promoted to a terminal seed in this bounded
tranche. The lifecycle record schema is v2 because its target-correlation
shape explicitly includes `tool_use_id`.

The private source projection binds a bounded unavailable reason, lifecycle
and hook summaries, and path-free ID-join diagnostics (tool-ID seen/missing,
mismatch, and exact-link candidate counts) into the source-phase digest. No
raw identifiers, hook payloads, local paths, or transcript bodies are carried.
These fields improve diagnosis only; the existing sticky startup gate remains
unchanged and a source seed cannot satisfy or bypass it.

### T048 SDK-sidecar bridge and eleventh-run observation

T048 preserves structurally valid mismatched hook callbacks as unresolved,
task-ID-free observations and retains bounded, digest-only callback/input/
current-task identity diagnostics. At source finalization, the v3 seed can use
a distinct, strictly validated SDK-sidecar proof after bounded no-follow
scanning, unique parent Agent `toolUseId` binding, top-level parent/child
session-and-agent checks, and exact `SubagentStop` transcript-path proof.
Missing or ambiguous metadata, conflicts, unsafe files, malformed JSON, and
scan overflow remain unavailable. Astra's architecture review passed and
Sol's 243-test formal selector passed with zero failures/errors/skips. Frozen
code hashes and complete artifact digests are in the linked verification
record.

The separately authorized eleventh runtime attempt used the available source
seed and established a release candidate. It reached durable release, target
launch, target creation, and final custody, but exited 2 with
`startup-task-event-observed`. The target showed one complete stopped
`task_notification` matching session/task; optional agent/tool identity was
unknown and the UUID differed. The sticky gate correctly skipped history
query. No parent/child startup messages or loaded-history proof were observed;
the negative arm did not run. Source and target harness stop/removal were
exit 137. This is INCONCLUSIVE, not a Bite 3 or Bite 5 verdict. The eleventh
authorization is consumed; 17 volumes and the older stopped containers remain
preserved. No cleanup, retry, or twelfth attempt is authorized. Next is
read-only protocol investigation; any progression-rule change requires
separate governance.

## Tool, process, and effect safety

The native child ledger is separate from a generic ToolGuard ledger. Tool
start/end events are joined to the child/task and parent invocation, but a
parent Agent tool completion cannot close a still-running child. The enclosing
coordinator process tree, account, and session naming are checked as one owner;
per-child PGID/session checks are neither required nor invented.

For each supported tool, the adapter records durable start/end evidence and
owned effects. A missing end event, detached descendant, ambiguous ownership,
or remote mutation with an unknown result holds the lane. Model-stopped and
externally cancelled children are reported distinctly where the runtime makes
that fact available. A `setsid`, `nohup`, background flag, parent exit, or OS
suspension alone never proves that a writer or effect is gone.

## Failure, retry, and recovery

Failure before a safe pause leaves the original runtime running wherever
possible and changes no ownership. Failure after pause preserves the same
operation ID, managed owner, writer claims, and unresolved evidence in a
paused/indeterminate state. Retry first reconciles the source and target
runtime trees, native task ledger, event sequence, dispatch attempts, and
external effects; it never starts a second coordinator or replays an uncertain
action.

Release and restart instructions are deduplicated mechanically. An accepted
send with no correlated native event remains pending/unresolved, not restarted.
An event observed for only part of a restart set is retained and only the
unproven remainder can be considered on a later explicit release/recovery
decision. User cancellation does not authorize an automatic resend. A lost
old-child link, stale process, old independent-mode record, or ambiguous
worktree owner refuses until explicitly migrated or reconciled.

For native swap, recovery also retains the six append-only evidence stages and
the exact release binding. A crash or timeout in interrupt, shutdown, target
open, send, pre-release, or the release gate never triggers an automatic
query, replay, release call, or daemon pump. If the synchronous gate may have
crossed, the receipt and uncertain effect are retained with claims; recovery
does not falsely restore the `held` disposition after an acknowledged gate.

## Verification and rollout

Controller tests use fake/local runtimes and temporary state to prove
serialization, fencing, durable retries, ownership exclusion, dirty-work
preservation, effect uncertainty, and status transitions. They must include:

* one coordinator with multiple native children, actual agent/task IDs, and
  lifecycle/hook/tool joins;
* a child that remains active after `PostToolUse(Agent)` returns;
* model-stopped versus externally cancelled children;
* runtime-owned native background stop/restart evidence, plus refusal for an
  unmanaged detached descendant;
* a pinned-runtime startup probe that prevents orphan-child auto-resume before
  release and a refusal when that hold cannot be proven;
* absent-provider refusal, exact six-stage native-swap binding, sticky epoch/
  clear evidence, and fake-provider evidence kept offline-only;
* native-swap pre-release and synchronous release-boundary correlation,
  including receipt-with-uncertain-effect recovery without pump or replay;
* exact coordinator resume, cross-account child-transcript verification, and
  preservation of model/effort/custom-agent definitions;
* resume-pending, exact-resumed, restart-pending, restarted, unresolved,
  accepted-send, partial-start, user-cancel, and retry outcomes;
* completed work/effects not replayed, lineage-level writer exclusion, and
  optional isolated-worktree claims; and
* explicit refusal/migration for the old independent-worker record mode.

The pinned runtime probe must publish its actual version, launch settings,
supported participant kinds, event names/fields, tools, account/storage
behavior, and the tested background modes. Teams are refused by default in
this release; their support is not an acceptance gate. Coordinator-only or
fake-only evidence is a prototype, not a complete native swap capability. Live
account/model use remains `UNVERIFIED` until a separately authorized probe
supplies it.

## Open decisions

### Authorized offline prerequisites and isolated investigation

On 2026-09-18 Brett authorized a disposable unauthenticated, network-isolated
runtime investigation alongside offline source-history/adoption work, after
the dependency audit identified missing request-observation, worker-state-clear
and restart-correlation evidence. The bounded offline contract is
[native source history and adoption assessment](../../../specs/001-separate-swap-ctx-handoff/contracts/native-source-history.md).
It adds immutable historical validation and read-only claim reconciliation
assessment, not successful target adoption or a runtime capability. Executable
work remains in the existing Speckit tasks; no task list is duplicated here.

The investigation may extend the existing scripted loopback fixture to measure
one continuous control interval earlier than the settled-parent stop window.
It must keep setup, account-control and released requests distinct, retain
unknown internal worker-state/orphan facts as unknown, use no real credentials
or external model/network service, and clean up only its own disposable
sandbox. Results for that fixture cannot grant actual-account support.

The subsequent approved three-workstream follow-up adds a deterministic
busy-parent control fixture, durable target-adoption intent/reconciliation,
and migration of the remaining legacy regression cases to native-lineage
semantics. A missing parent result is not a busy-parent witness: the fixture
must expose a positively observed in-flight parent request and an explicit
barrier at control entry. Request observation remains continuous through the
same-epoch pre-release interval and synchronous release boundary; orphan wake,
worker-state clearing, and exact held restoration stay unknown unless
separately observed through supported runtime interfaces.

Adoption is an internal, held, recoverable state transition. Its intent must
bind the immutable archive, exact source/target claims, operation, owner and
daemon before a claim-index change; uncertainty never permits replay of a
runtime action or an automatic claim transfer. The source history remains
readable independently of the adopted controller. Public lifecycle and
runtime capability gates are unchanged. Regression migration must preserve
each applicable safety assertion and identify genuinely missing native
behavior rather than deleting, skipping, or weakening the failing tests.
The existing Speckit tasks remain the sole implementation task list.

* Which pinned Claude runtime/version and launch mode supplies a reliable
  startup hold that prevents orphan-child auto-resume?
* Which native agent/task IDs and lifecycle/hook event fields remain stable
  across account transition and model-assisted restart?
* Which native child stop behavior, active-tool boundary, and runtime-owned
  background configurations pass the evidence gate?
* What target-account transcript/storage conditions permit exact child
  continuation, and what minimum mechanical records permit safe restart?
* Which existing recovery/context owner will host the explicit record modes and
  migration refusal for the old independent prototype?

### T049 separate terminal-task diagnostic progression

The twelfth Bite 4 observation remains historical `INCONCLUSIVE` with
`startup-task-event-observed`; its authorized run and the separately
authorized cleanup are complete. Bite 5 remains pending and production remains
unsupported. T049 defines an offline-only candidate for one bounded diagnostic
history query under an explicitly selected target profile. The existing
`strict-v1` default and `assess_v1_history_query_gate` behavior remain
unchanged. The exception is selected and fingerprinted separately; it cannot
be inferred from a source seed or from the strict gate refusing.

The candidate admits only one complete, exact `system/task_notification` with
`status=stopped` that matches a validated stopped source task by parent session
and task ID. The task event's public frame has no origin field; a present
origin is a conflict. A missing target `task_type` remains missing; the
validated source `task_started` record supplies the `local_agent` constraint.
One successful injected startup result must have explicit
`origin.kind=task-notification`, exact parent session, and no error, abort, or
deferred tool evidence. Assistant/tool activity, other lifecycle events,
unexpected frames or routes, partial/unparsed output, observer gaps, request
arrivals during startup, or ambiguity refuse the query.

Before target launch, the gateway begins bounded request-arrival observation
and stays held. A single separately authorized query uses a fresh private
nonce distinct from an unpredictable response challenge and an explicit human
origin. The gateway requires one parent request with valid model and dummy
authorization, and the source prompt marker, exact Agent use and matching
result in that same ordered message list before the nonce. It writes only the
challenge, and records successful write/message-ID evidence. Completion
requires the fresh exact-parent human-origin challenge result, stream EOF,
closed gateway/request windows, no in-flight or unexpected arrivals, and no
later native task events. This is terminal-correlation-only: bounded retained
source facts reached the target model request and the fresh challenge returned.
Full history restoration remains unproved; replay, quiescence, and child
restoration also remain outside the evidence.

The T049 candidate is architecture approved and Sol's canonical focused gate
passed 420 tests, with 2,168 deselected and zero failures. The separately
authorized thirteenth run did not reach its copy/release/query stages and
remains INCONCLUSIVE. T049 does not authorize a fourteenth runtime attempt,
cleanup, deployment, or production support claim. Bite 5 remains pending.

### T050 future-only source-report failure correction

T050 records a future-only offline correction after the thirteenth run's
source-report schema failure. Remove the unbound `parent_uuid` reference from
the legacy/source runtime initializer and publish generic fallback
`error_site` evidence as only an allowlisted component/function and integer
line; do not expose exception messages, paths, or locals. Immediately after
source `_runtime_exec` returns, persist the exact mapping and source
invocation/container/report digests in a private append-once envelope before
source stop/removal or target-volume creation. Validate schema, phase,
`support_claim=false`, `target_code_reached=false`, and exact source bindings
before progression. Invalid fallback reports remain private and return the
fixed public `source-runtime-report-invalid` INCONCLUSIVE result through
quarantine. An otherwise-valid explicit `target_code_reached=true` remains a
FAIL; absent or unknown reach remains INCONCLUSIVE. Astra approved the
architecture and Sol's canonical offline gate passed 427 tests, 2,168
deselected, zero failures. This repairs future behavior only: the thirteenth
run remains INCONCLUSIVE, no fourteenth run is authorized, Bite 5 is pending,
and production remains unsupported.
