## Purpose

Specify the opt-in, externally supervised Claude account swap governed by
[`separate-swap-ctx-handoff`](../../proposal.md). The capability preserves the
coordinator's native conversation and the native subagents that belong to its
execution lineage, while refusing any participant or effect that cannot be
proven safe. A swap is an account transition, not a semantic handoff.

## ADDED Requirements

### Requirement: Explicit stop-then-resume v1 defers target creation until release

Under the approved [v1 decision](../../stop-then-resume-decision.md), the system
SHALL distinguish explicitly selected `stop-then-resume-v1` from existing
strict native swap. The target-held, pre-release exact-loading, durable orphan
clear, and six-stage target-proof requirements elsewhere in this specification
SHALL apply to strict mode, not v1. Both modes SHALL preserve source exclusion,
history, files, ownership, permissions, and uncertain-effect safety. Old or
unmarked records SHALL NOT be reinterpreted as v1. Graceful child/tool
drain-before-parent-shutdown ordering elsewhere below SHALL remain strict-only;
v1 MAY mechanically contain unfinished work before complete drain, but SHALL
prove full source exclusion and reconcile effects before readiness. Termination
SHALL NOT mean successful task completion.

#### Scenario: Source quota is exhausted

- **WHEN** an operator selects v1 with a supported source containment boundary
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
