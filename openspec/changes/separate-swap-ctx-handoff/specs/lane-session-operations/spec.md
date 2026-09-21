## Purpose

Define separate account-swap, context-rollover, work-handoff, and native
worker-restart contracts so callers can select the intended operation without
hidden model work, semantic handoff, or lifecycle changes.

## ADDED Requirements

### Requirement: Swap preserves the coordinator conversation and native lineage

The system SHALL define `swap` as selecting an explicitly requested
authorized account profile and resuming the existing coordinator conversation
by its exact native transcript identity. Native subagents remain children in
that coordinator's execution lineage: their native agent/task IDs, parent
linkage, containing process tree, and hook/tool facts are reconciled by the
runtime. They are not independent top-level SDK sessions with their own UUID,
account, process group, open, shutdown, or release operation.

Swap SHALL prefer verified exact same-agent child continuation. A child whose
exact continuation is not available SHALL be reported `restart-pending` while
the coordinator remains held; this does not silently become a semantic
handoff or a coordinator-only success claim. Swap SHALL NOT require or
generate a semantic handoff, fresh coordinator conversation, commit, or push.
The prescribed role, model, effort, tools, permissions, custom-agent
definition, and effective child policy SHALL remain unchanged across the
transition. Any writer is claimed by the owning coordinator session-lineage;
an isolated native child worktree MAY have an additional exact global claim.
Before release, an exact-continuation candidate is `resume-pending`; after
release, only correlated current-run native events may transition it to
`exact-resumed`. A new child fallback transitions from `restart-pending` to
`restarted` only with the same evidence standard; otherwise it is
`unresolved`. Reused agent IDs, stale notifications, and hook records without
durable parent/task joins are not sufficient evidence.

#### Scenario: Account-only transition

- **WHEN** a supported lane swaps to a compatible target profile
- **THEN** the coordinator resumes its exact native transcript under the
  target account while held and each unfinished child receives an explicit
  `resume-pending`, `restart-pending`, or `unresolved` status
- **AND** completed children remain completed, with no generated handoff or
  repository housekeeping

#### Scenario: Exact child continuation is unavailable

- **WHEN** target runtime evidence cannot prove continuation of a native child
  as the same agent/task in its coordinator lineage
- **THEN** swap records `restart-pending` and does not invent a child UUID or
  independently open a child session
- **AND** no model-assisted restart occurs before explicit `release`

### Requirement: Swap uses an explicitly authorized coordinator stop transaction

When coordinator-wide interrupt is the selected stop candidate, swap SHALL
use durable whole-roster authority distinct from a task-specific stop. It
SHALL seal actual native membership and preserve per-child/tool/effect evidence
through drain, without granting child SDK sessions or per-child shutdown APIs.
An uncertain send SHALL NOT be repeated automatically. The zero-new-request
account-control interval SHALL include preflight and fencing and remain
continuous through held readiness until explicit release. A runtime mode
without the required request-observation and stop/restore evidence SHALL refuse
before disruption; a narrow scripted fixture SHALL NOT enable production swap.

#### Scenario: Whole-roster cancellation is selected

- **WHEN** swap selects a supported coordinator-wide interrupt path
- **THEN** one durable source-run authorization covers the complete sealed
  roster and independent evidence determines each child's outcome
- **AND** neither an interrupt receipt nor task-specific authority declares
  the lane quiescent or released

### Requirement: Explicit release gates a new native child restart

The system SHALL define native worker restart as a post-release model action
through the resumed coordinator/native interface. After target-account
readiness and an explicit `release`, the coordinator MAY receive an ordinary
model instruction to create a **new native child** using the existing native
task record and coordinator context. The instruction is not a written or
semantic handoff. A correlated native task/agent start and parent/tool/process
evidence records `restarted`; an accepted send without that evidence records
`unresolved`.

The controller SHALL never send a per-worker SDK request or create a fictitious
child account/session. Completed work, completed workers, and uncertain effects
are never replayed. Restart SHALL not imply that the new child has the original
conversation or identity.

#### Scenario: User explicitly releases a pending child

- **WHEN** the coordinator is ready under the target account, the user has
  explicitly invoked `release`, and a child is `restart-pending`
- **THEN** the restart instruction is routed through the coordinator/native
  interface and may create one new native child
- **AND** the controller records `restarted` only after correlated runtime
  events, never from an accepted-send acknowledgement alone

#### Scenario: Restart would replay uncertain work

- **WHEN** a pending child or external action has an unresolved stop, ownership,
  or effect result
- **THEN** the restart remains blocked or `unresolved` until explicit
  reconciliation
- **AND** no completed or uncertain action is replayed automatically

### Requirement: Context rollover and handoff remain distinct

The system SHALL define `ctx` as a fresh coordinator context under the current
account from an explicitly supplied semantic checkpoint, with native-worker
treatment governed by an explicit context-restart policy. Under `hold`, old
native workers are stopped and retained with their existing coordinator
lineage records; this does not promise that live children survive source-parent
shutdown. Under `restart`, new-lineage native workers may be created from the
supplied checkpoint only after explicit release. `ctx` SHALL never claim an
exact cross-parent child rebind or silently infer parent/child relationships.

The system SHALL define `handoff` as a separate, user-requested transfer of
work and understanding without an implicit account change or restart. Only an
explicit handoff request may produce or update transfer information. Neither
`ctx` nor `handoff` SHALL implicitly perform `swap`, and neither semantic
operation is invoked by native worker restart.

#### Scenario: Fresh context holds existing workers

- **WHEN** the user requests `ctx` with the explicit `hold` worker policy
- **THEN** the old native workers are stopped and retained with their
  coordinator/task records while a fresh coordinator context uses the
  unchanged account
- **AND** no exact cross-parent rebind, implicit swap, or worker restart is
  claimed

#### Scenario: Fresh context restarts from a supplied checkpoint

- **WHEN** the user requests `ctx` with the explicit `restart` worker policy
  and supplies a semantic checkpoint, then explicitly releases the new
  coordinator context
- **THEN** new-lineage native workers may be created through that coordinator's
  native interface and receive correlated lifecycle statuses
- **AND** old workers are not rebound across parents and no checkpoint is
  synthesized by a model

#### Scenario: Knowledge transfer is requested

- **WHEN** the user requests only `handoff`
- **THEN** the system produces or updates the requested transfer information
- **AND** it does not automatically change accounts, resume a native child, or
  restart the coordinator

#### Scenario: Swap or restart is requested without handoff

- **WHEN** a lane performs `swap` or an explicitly released native worker
  restart
- **THEN** it uses exact coordinator/native task records and coordinator
  context as applicable
- **AND** it generates no semantic handoff, checkpoint, or written handoff
  artifact unless the user separately requests `handoff`

### Requirement: External swap control does not dispatch model work

The system SHALL provide a swap control surface outside the model conversation.
Preflight, admission fencing, interruption, native task/tool quiescence,
persistence, exact coordinator resume, native identity reconciliation,
restart classification, and readiness verification SHALL NOT initiate model
requests or ask agents to write summaries. A slash frontend SHALL qualify for
this guarantee only when intercepted before model dispatch.

Usage from requests already initiated before account-control entry and from
deliberately released continuation SHALL be reported separately. Every new
request attempt during account control, including continuations or task
notifications from previously running work, SHALL count in its observation
epoch. The zero-new-model-request guarantee
ends only at the explicit `release` that authorizes ordinary model-assisted
native worker restart; that usage is reported separately.

The control phase SHALL prove that the selected runtime does not infer or
auto-resume parent/child work before the first explicit query. Interactive
takeover with pre-prompt orphan auto-resume and a print-style callback that
cannot establish a pre-dispatch hold are unverified. SDK `stream-json` remains
unverified until the exact SDK-selected executable, SDK/CLI versions, launch
mode/arguments, and binary digest are recorded with a no-auth orphan fixture;
the SDK's bundled-first choice (for example SDK `0.2.153` selecting CLI
`2.1.273`, observed digest prefix `6c752e2c`) is not interchangeable with an
earlier installed CLI trace. The source must terminal-stop every tracked child
and durably clear current state before parent exit, then target startup must
prove no-wake/no-model behavior. CLI `2.1.273` print startup can wake orphans
via `restoredOrphans`' default wake and `enqueuePendingNotification`; print or
stream-json alone cannot satisfy this proof.

#### Scenario: Current inference quota is exhausted

- **WHEN** the user invokes external swap while the current account cannot
  make another model request
- **THEN** the controller can attempt the supported stop, exact coordinator
  resume, and native child reconciliation sequence without requesting model
  assistance
- **AND** any child needing model-assisted restart remains `restart-pending`
  until explicit release

#### Scenario: Slash input would reach the model

- **WHEN** the installed frontend cannot intercept `/swap` before model
  dispatch
- **THEN** it is not advertised as the token-free swap path
- **AND** documentation identifies the external command

#### Scenario: Released restart consumes model usage

- **WHEN** an explicitly released coordinator receives a native child restart
  instruction
- **THEN** that model usage is recorded separately from account-control work
- **AND** its accepted send is not treated as proof of restart without native
  task events

#### Scenario: Startup can infer an orphan child

- **WHEN** the selected interactive or SDK launch mode can auto-resume an
  orphan before the first prompt, or the adapter cannot establish a
  pre-dispatch hold
- **THEN** control refuses before source shutdown and does not advertise the
  mode as a zero-model-request swap
- **AND** a promptless parent load is not treated as proof of a held graph

#### Scenario: Parent tool return leaves a child active

- **WHEN** `PostToolUse(Agent)` returns but current-run native task events still
  report a child active
- **THEN** the child remains unresolved and readiness is blocked
- **AND** a reused agent ID, stale stop event, or hook-only record cannot mark
  it quiescent

### Requirement: Claude-first native capability boundaries are explicit

The initial implementation SHALL target Claude and publish tested runtime
versions, launch modes, and native participant kinds. Native Agent/Task forms,
teams, and runtime-owned background children SHALL be accepted only where
their actual native discovery, parent linkage, stop boundary, continuation or
restart, and tool/effect evidence has been demonstrated. Unmanaged detached
shell/background processes remain outside the native participant boundary.

The implementation SHALL refuse an unsupported preservation configuration
before planned termination and SHALL report per-worker status as
`resume-pending`, `restart-pending`, `exact-resumed`, `restarted`, or
`unresolved`. It SHALL NOT silently substitute a semantic handoff, fresh
context, invented child session, or unverified parent-only graph claim. Codex
support SHALL remain a separate future delivery.

Native task lifetime SHALL be tracked independently of the launching tool call.
`PostToolUse(Agent)`, a reused `agent_id`, or a stale stop notification is not
current-run quiescence; current task/parent invocation and event-watermark
correlation plus tool/process facts are required. A tracked native background
child may be evaluated, while an unmanaged detached process blocks readiness.

#### Scenario: Unsupported native participant

- **WHEN** a lane contains an unfinished native participant whose complete
  discovery and stop/restart behavior has not been demonstrated for the
  published runtime configuration
- **THEN** swap refuses before planned shutdown or records the explicitly
  bounded `restart-pending`/`unresolved` state only where the coordinator
  control contract permits it
- **AND** no handoff, fresh-context fallback, fictitious child session, or
  silent worker drop is started automatically

#### Scenario: Tracked native background versus detached process

- **WHEN** a native background child has task/lifecycle events joined to its
  coordinator but another background process is detached and unmanaged
- **THEN** the tracked child is evaluated by the tested native boundary
- **AND** the detached process blocks readiness or remains unresolved rather
  than being treated as a safe child

### Requirement: Lifecycle and alias migration are coordinated

All operations, including explicit native worker restart, SHALL coordinate
through one per-lane operation authority and shared compatible lifecycle
records. The changed alias semantics SHALL require an explicit protocol
migration. Historical records SHALL remain readable and SHALL NOT be relabeled
as successful native swaps or native child continuations.

Old independent-worker prototype records that contain per-child top-level
session/open/shutdown/release state SHALL be refused or handled by an explicit
versioned migration. They SHALL not be silently reinterpreted, deleted, or
treated as coordinator-lineage records.

#### Scenario: Swap races with context restart

- **WHEN** a context restart already owns the lane transition
- **THEN** a swap cannot independently shut down or relaunch the coordinator
  or native children
- **AND** the controller reports the active operation

#### Scenario: Native restart races with handoff

- **WHEN** a handoff operation already owns the lane transition
- **THEN** native worker restart cannot create a child or alter transfer state
  independently
- **AND** the controller reports the active operation without generating a
  second semantic record

#### Scenario: Legacy handoff or independent-worker record is read

- **WHEN** the controller encounters a historical handoff, context-restart, or
  old independent-worker record
- **THEN** it interprets the record using its original contract or requests the
  explicit migration required by its version
- **AND** it does not infer exact native-session or native-child readiness from
  that record
