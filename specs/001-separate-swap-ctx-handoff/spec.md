# Feature Specification: Separate Swap, Context, and Handoff for Native Claude Lanes

**Feature Branch**: `001-separate-swap-ctx-handoff`
**Created**: 2026-09-16
**Status**: Approved architecture revision; implementation re-planning required
**Governing Change**: [separate-swap-ctx-handoff](../../openspec/changes/separate-swap-ctx-handoff/proposal.md)

## Authority and history

The [approved native-subagent decision](../../openspec/changes/separate-swap-ctx-handoff/native-subagent-decision.md)
is authoritative for this specification. The feature keeps Claude's native
subagent workflow in one coordinator execution lineage. Exact native worker
continuation is preferred when the pinned runtime and its evidence support it;
an ordinary model-assisted native worker restart is accepted only after the
target account is ready and the operator has explicitly released the lane.

Earlier proposal, implementation, and test artifacts described a different
worker architecture and native-participant exclusions. They remain history and
may provide reusable safety or profile work, but they are superseded: they are
not requirements, migration rules, or acceptance evidence for this revision.
This remains the sole implementation feature for the governing change.

## User Scenarios & Testing

### User Story 1 - Swap a Native Claude Lane Without Inference (Priority: P1)

An operator can select an explicitly authorized target profile and move an
opt-in Claude lane across accounts while preserving its native coordinator and
subagent lineage. The account-control portion stops admission, establishes
safe participant and tool boundaries, restores the exact coordinator
conversation under the target account, and leaves all restored work held until
an explicit release. Swap does not ask a model to explain or reconstruct work.

**Why this priority**: Account transition without spending the exhausted
account's remaining model capacity is the primary user value and the safety
boundary on which every worker outcome depends.

**Independent Test**: Use a disposable fake runtime and a reviewed pinned
runtime configuration containing one coordinator, unfinished native children,
one completed child, and a tracked native background Agent task. Initiate swap
with an authorized same-family target profile and verify the fence, stop
evidence, exact coordinator resume, held state, absence of model requests and
absence of generated swap artifacts.

**Acceptance Scenarios**:

1. **Given** an enrolled native coordinator lineage and a target profile that
   has been explicitly authorized and verified as the same transcript-storage
   family, **when** the operator requests swap, **then** new admission and
   mailbox delivery are fenced, the native roster is sealed, supported
   participants and tools reach an evidenced stop boundary, and the exact
   coordinator conversation loads under the target account in a held state.
2. **Given** the account-control phase is running, **when** swap performs its
   stop, profile, and exact-resume work, **then** it makes no model request and
   creates or requires no written summary, checkpoint, semantic handoff,
   commit, push, stash, reset, or worktree reconstruction.
3. **Given** an account, profile, permission, transcript, participant,
   lifecycle, tool, ownership, or external-effect check is missing or
   contradictory, **when** swap reaches that check, **then** it refuses or
   remains paused/indeterminate with the affected identity and reason, keeps
   the fence and claims, and does not release, replay, or create a competing
   writer.
4. **Given** dirty or untracked local work with no ownership conflict, **when**
   swap succeeds or refuses, **then** the work remains in place and unchanged.
5. **Given** the target profile is ambiguous, unauthorized, outside the
   transcript-storage family, or uses an unsupported authentication setup,
   **when** swap is requested, **then** it refuses before claiming successful
   transition and leaves the source work protected.

### User Story 2 - Continue or Restart Native Workers Honestly (Priority: P2)

An operator can see the verified disposition of every unfinished native child
and can continue it without changing the user's worker architecture. The
system prefers exact native continuation. A safely stopped child eligible for
that path is `resume-pending` while held; after release, correlated evidence
changes it to `exact-resumed`. If the runtime cannot externally restore that
child, it records `restart-pending`; after account readiness and explicit
release, it may issue an ordinary model instruction through the
coordinator/native interface to restart the child from existing native
conversation and task records. A restart is reported as a restart, not as proof
of the old conversation or identity.

**Why this priority**: The coordinator alone is not a faithful restoration of
the user's lane. Honest worker-level outcomes protect unfinished work while
allowing a supported fallback when exact native continuation is unavailable.

**Independent Test**: Exercise one exact-continuation case and one unavailable
continuation case against a fake runtime, then run the corresponding pinned
runtime stop/restart probe. Verify event correlation, release ordering,
preserved worker definitions, and the four operator-visible dispositions.

**Acceptance Scenarios**:

1. **Given** a native child with a captured Agent/task identity, an evidenced
   safe stop, and a runtime-supported continuation path, **when** swap restores
   the native lineage, **then** the worker is reported `resume-pending` while
   held. **When** the operator later releases the held operation, **then**
   correlated native lifecycle events prove the same child continued and the
   report changes to `exact-resumed`.
2. **Given** a safely stopped unfinished child for which external native
   continuation is unavailable, **when** account readiness is committed,
   **then** the report says `restart-pending`, no restart is attempted against
   the exhausted source account, and the lane remains held until explicit
   release.
3. **Given** a `restart-pending` child and an authorized release, **when** the
   coordinator sends the mechanically composed restart instruction through the
   actual native interface, **then** the instruction uses the existing native
   conversation/task records, prescribed model/effort/custom-agent definition,
   and coordinator context; it creates no written handoff, summary, or
   checkpoint artifact.
4. **Given** the restart instruction is accepted, **when** correlated native
   task start/progress/notification/task-updated and tool/parent events identify
   the new child run, **then** the report says `restarted`; it never says
   `exact-resumed` or claims the old conversation or identity was preserved.
5. **Given** a restart starts only partially, is user-cancelled, returns no
   correlated native task, or cannot link the old task to the new run, **when**
   recovery evaluates it, **then** the report says `unresolved`, preserves
   ownership and uncertainty, and does not automatically retry or replay an
   external effect.
6. **Given** a runtime-owned native background Agent task has a captured task
   ID and lifecycle events, **when** swap evaluates it, **then** its stop and
   restart behavior is investigated and tested as a native participant. A
   background launch flag by itself is not evidence of quiescence or support.
7. **Given** a `PostToolUse(Agent)` event only says that background launch was
   accepted while the child remains active, **when** swap checks the native
   lifecycle ledger, **then** separate `SubagentStart`/`SubagentStop` evidence
   joined to `task_started`, `progress`, `notification`, `task_updated`, tool,
   and parent IDs keeps the active child in the roster and blocks the safe stop
   boundary.
8. **Given** an unmanaged detached shell/background process, a native team,
   or another participant kind without published stop/restart evidence, **when**
   it is discovered, **then** the configuration is unsupported or the operation
   refuses/holds. The system does not infer support from a background flag,
   parent exit, team membership, or a fake-only result.

### User Story 3 - Preserve Completion, Effects, and Ownership (Priority: P2)

An operator can trust that a swap, restart, retry, or crash recovery will not
replay completed work or ambiguous external effects. Writer ownership belongs to
the owning session lineage. A real isolated-worktree claim may be attached to
that lineage when it is present and evidenced; child task IDs do not receive
invented sessions, process groups, or worktree claims. Unknown stop, effect,
and ownership evidence remains held and visible.

**Why this priority**: A safe transition must protect repositories and external
systems even when native runtime evidence is incomplete or a process fails at a
boundary.

**Independent Test**: Run completion, active-tool, crash, retry, and concurrent
writer scenarios with equal, aliased, and ancestor/descendant worktree paths.
Verify lineage-level exclusion, dirty-work preservation, at-most-once effects,
and held outcomes for every injected unknown.

**Acceptance Scenarios**:

1. **Given** a read-only coordinator delegates to a native child whose actual
   Agent ID and immutable definition/permissions authorize writing to a real
   isolated worktree, **when** that child writes through the lineage, **then**
   the exclusive claim is recorded for the owning lineage and not fabricated as
   a separate claim for the child. A read-only lineage with no writer may have
   no claim, and an unknown or mismatched child refuses.
2. **Given** another lineage requests the same, aliased, or ancestor/descendant
   isolated worktree, **when** the request is admitted, **then** it refuses
   before changing files or claims. A unique dirty or untracked worktree is
   accepted and preserved.
3. **Given** a worker is authoritative complete and quiescent, **when** swap,
   restart, or retry runs, **then** its completion and effects remain complete,
   it is not replayed, and its claim is not reassigned until the required
   completion/stop evidence permits release.
4. **Given** a tool has no durable end event, a descendant is detached, a
   process or writer owner is unknown, or a remote effect may have completed,
   **when** recovery evaluates the lane, **then** it holds the affected claim
   and reports the uncertainty; it does not restart a writer or resend an
   ambiguous action.
5. **Given** a crash occurs before send, after possible send but before
   acknowledgement, after acknowledgement but before recording, or after a
   partial worker start, **when** the same operation is retried, **then** the
   durable request/operation identity reconciles first, release occurs at most
   once, and no uncertain message or external effect is automatically replayed.
6. **Given** a lane's coordinator has an exact canonical name, lane, and UUID,
   **when** the prompt guard checks the enrolled lane, **then** it validates
   that coordinator binding exactly. Native children may share its parent OS
   process, account, or session name; the guard does not demand a distinct
   top-level identity or process group for each child.
7. **Given** a durable record from the superseded worker prototype is found,
   **when** the revised supervisor loads it, **then** it refuses compatibility
   or migration explicitly, preserves the record for operator recovery, and
   never silently reinterprets, deletes, or treats it as native evidence.

### User Story 4 - Keep `ctx`, `handoff`, and `release` Distinct (Priority: P3)

An operator can choose a fresh context, a user-requested handoff, or release of
held work without one command silently performing another. `ctx` keeps the
current account and creates a deliberate fresh native coordinator context from
an explicitly supplied checkpoint. Its native worker policy is explicit:
`hold` stops and retains existing workers under their old lineage without
promising that they remain live beneath an exited parent; `restart` creates
new-lineage native workers from the supplied checkpoint only after explicit
release. Exact cross-parent native rebind is not promised. `handoff` records
only a checkpoint the user supplies. `release` is the sole inference boundary.

**Why this priority**: Separating these intents prevents an account swap from
silently changing context or creating a handoff, while giving operators a
deliberate way to reset context and communicate work.

**Independent Test**: Against one held native roster, execute `ctx` with both
explicit worker policies, execute user-requested `handoff`, and issue matching,
stale, and duplicate `release` requests. Verify account, native lineage,
checkpoint, worker, claim, and inference effects independently.

**Acceptance Scenarios**:

1. **Given** an explicit checkpoint and the current authorized profile, **when**
   `ctx --workers hold` runs, **then** it creates a fresh held coordinator
   context under that account, stops and retains existing native workers under
   their old lineage, and does not silently restart, drop, or cross-parent
   rebind them.
2. **Given** an explicit checkpoint and the current authorized profile, **when**
   `ctx --workers restart` runs, **then** it records the new coordinator and
   prescribed native worker definitions, keeps them held until release, and
   starts new-lineage workers from that supplied checkpoint only after explicit
   release. No exact cross-parent identity is claimed.
3. **Given** an omitted, ambiguous, or unsupported `ctx` worker policy, **when**
   `ctx` is requested, **then** it refuses without inventing a checkpoint,
   worker mapping, parent ID, or rebind operation.
4. **Given** an explicit checkpoint supplied by the user, **when** `handoff`
   runs, **then** it records that user-requested handoff only; it does not swap
   accounts, pause or restart workers, alter claims, or release inference.
5. **Given** a ready-held operation and its current generation, **when** the
   operator invokes `release` once, **then** queued normal work and permitted
   model-assisted restarts may dispatch. A stale, duplicate, or unresolved
   release refuses and does not dispatch twice.
6. **Given** a child-targeted message is submitted before release, **when** the
   lane is held, **then** it remains durably pending. After release, delivery
   uses the actual native coordinator/child interface and correlated native
   events; it never uses the obsolete per-worker SDK send/open path.
7. **Given** swap or worker restart is in progress, **when** `ctx`, `handoff`, or
   an implicit release would overlap it, **then** the operation remains distinct
   and the overlap is serialized or refused; neither is invoked implicitly.

### Edge Cases

- A canonical lane is literally named `swap`; command parsing treats it as
  data, not as a subcommand.
- A native child shares the coordinator's OS process, account, or session name,
  and has no independent top-level UUID or process group; coordinator process
  tree containment plus native Agent/task and lifecycle evidence is used.
- Native Agent/task identity, parent/task linkage, tool identity, or lifecycle
  evidence is absent, duplicated, stale, or contradictory.
- A live event such as `SubagentStart` lacks a direct `parent_agent_id` or task
  link. Correlation must use the current run, task, parent invocation, and an
  event watermark; an ambiguous join is unknown/refused.
- A native Agent ID is reused across runs, or a stale completion marker is
  present. Reuse is disambiguated by the current run/task/parent and event
  watermark; a stale marker never proves current quiescence.
- A child was model-stopped versus externally cancelled, and the pinned
  runtime gives different continuation behavior for those cases.
- `PostToolUse(Agent)` reports accepted background launch while a child remains
  active; `SubagentStart`/`SubagentStop` and task/tool/parent ledger events have
  not yet proved quiescence.
- A runtime-owned native background Agent task has captured IDs and events, but
  an adjacent detached shell, `nohup`, `setsid`, or other unmanaged descendant
  has an unknown effect. The tracked task can be evaluated; the detached effect
  keeps the lane held.
- A native team is present, or a background/participant kind has no tested
  stop/restart behavior for the pinned runtime. It is unsupported/unproven, not
  silently admitted.
- Promptless parent initialization automatically resumes an orphaned child,
  or the runtime cannot hold parent and child inference until release. The
  startup configuration refuses the zero-inference claim and public support.
  A trace of one installed CLI version is not evidence for another selected by
  the SDK; the exact SDK release, selected CLI path/version/digest, and launch
  mode are part of the audit.
- The selected CLI print path restores `running_background_tasks`, wakes a
  default-enabled orphan, or enqueues a pending notification before the first
  external query. Terminal stop plus durable state clearing and target no-wake/
  no-model evidence are required; print or stream-json mode alone is not proof.
- A tracked tool ends without a durable event, leaves a descendant, or may
  have completed a remote mutation even though cancellation was acknowledged.
- Exact coordinator transcript identity is missing; an empty session has a
  reserved UUID but no persisted transcript; loader initialization errors
  before its initialization response; or initialization omits session/model
  fields that are not required evidence.
- Exact native worker continuation is available but not yet released; the
  worker is `resume-pending`. If exact continuation is unavailable, it is
  `restart-pending`; release has not happened, or a restart acknowledgement has
  no correlated native task events.
- A restart is partially started, user-cancelled, retried after a crash, or
  starts under a different model, effort, or custom-agent definition. It must
  preserve the prescribed definition or become `unresolved`.
- A completed worker, queued message, writer claim, or remote effect is seen
  during retry; completion remains complete and uncertain work is not replayed.
- A target profile resolves ambiguously, changes account or transcript-storage
  family, uses unsupported setup-token authentication, has mismatched
  permissions, or inherits an unsafe provider-auth override.
- A worker claim is missing a real isolated worktree, collides through an alias
  or ancestor/descendant path, or is mistakenly represented as a per-child
  claim. Claims remain at the owning lineage level.
- A coordinator, child, tool, or supervisor crashes before or after any
  lifecycle, dispatch, acknowledgement, readiness, release, or claim record;
  recovery reconciles durable state before any new action.
- A request is malformed, oversized, concurrent, stale-generation, duplicated
  with changed content, or arrives while admission is fenced.
- The old independent-worker durable schema, an unknown local owner, a stale
  lane binding, or a missing runtime capability record is encountered. It is
  refused explicitly and never migrated by inference.
- A user requests cross-machine migration, automatic account discovery,
  credential copying, launcher mutation, quota guarantees, or a live action
  without explicit authorization. The request is outside this feature.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST support an explicitly enrolled Claude lane as
  one coordinator execution lineage containing Claude-native subagents. It MUST
  preserve that native worker architecture rather than requiring conversion to
  separate top-level worker sessions.
- **FR-002**: The system MUST discover and durably record the coordinator's
  native session identity, each supported Agent/task identity, parent/task
  relationships, participant kind, prescribed launch definition, mailbox/task
  references, lifecycle state, tool state, and ownership evidence. It MUST NOT
  invent a top-level session UUID, external open/release method, or independent
  process group for a native child.
- **FR-003**: The system MUST publish the exact pinned runtime versions and
  native participant kinds whose discovery, stop, resume, and restart behavior
  has been tested. Native teams and any other unverified kind MUST remain
  unsupported/unproven and MUST refuse before being advertised as supported.
- **FR-004**: The supervisor MUST serialize enrollment, admission, swap, ctx,
  handoff, submit, recovery, release, shutdown, and unenrollment for one
  canonical lane generation. A concurrent or stale operation MUST make no
  lifecycle change.
- **FR-005**: Swap MUST fence new parent/child admission and mailbox delivery,
  seal the native roster, preserve local work, resolve the explicitly selected
  authorized profile, and perform the account transition without a model
  request. It MUST restore the exact coordinator conversation under the target
  account and leave the operation held until explicit release.
- **FR-006**: Swap MUST establish a tested stop boundary for every supported
  native participant and tracked tool before replacement inference. It MUST
  distinguish runtime-owned native background Agent tasks with captured IDs and
  lifecycle events from unmanaged detached shell/background processes; the
  former require investigated stop/restart evidence and the latter keep the
  operation held or refused.
  A selected coordinator-wide interrupt MUST have a separate durable
  whole-roster authorization bound to the exact coordinator/runner, owner and
  lineage, fence and sealed native identities. Its possible-send marker MUST
  precede a single call; a task-specific stop intent MUST NOT authorize it.
  Unknown send outcomes MUST NOT be resent automatically, including under a
  different request ID. Receipt, parent-result drain, each current child
  terminal, tracked tool/effect outcome and old-writer exclusion MUST remain
  independent evidence. Interrupt MAY initiate child stopping; parent shutdown
  MUST follow proven child/tool quiescence and required supported state clear.
- **FR-007**: The native lifecycle ledger MUST join `SubagentStart` and
  `SubagentStop` with `task_started`, `progress`, `notification`,
  `task_updated`, tool, and parent identifiers. Where a live event lacks a
  direct parent-agent or task link, it MUST be correlated to the current run,
  task, parent invocation, and event watermark; an ambiguous join MUST remain
  unknown/refused. Reused Agent IDs MUST be disambiguated by that current-run
  evidence, and a stale completion marker MUST NOT prove current quiescence. A
  `PostToolUse(Agent)` launch acknowledgement, a background flag, cancellation
  acknowledgement, parent exit, or OS suspension alone MUST NOT prove
  child/tool/writer quiescence.
- **FR-008**: If a participant, tool, descendant, writer, ownership fact, or
  external effect cannot be stopped and accounted for authoritatively, the
  system MUST keep the lane paused/indeterminate, preserve its claims, report
  the uncertainty, and block release, replay, or competing writers.
- **FR-009**: Before claiming a supported ready state, the system MUST audit
  startup behavior of the pinned runtime for orphaned native children and prove
  that parent and child inference cannot occur before explicit release. The
  audit MUST exercise the actual selected SDK and CLI startup path, recording
  the SDK release, selected executable path, CLI version/digest, and launch
  mode, including orphan handling after MCP setup/settle and before the first
  user query; a promptless-parent fake is insufficient. In a mode such as the
  traced CLI `2.1.270` path where startup
  may call `resumeOrphanedAgents` and
  `oW(agentId, continueInterruptedTurn: true)`, the implementation MUST either
  prove terminal stop/prevented orphan eligibility before startup or publicly
  refuse native-graph swap support. A trace of installed CLI `2.1.270` does not
  establish the default behavior when SDK `0.2.153` selects a bundled CLI
  `2.1.273`; each selected binary/mode needs its own evidence. In particular,
  a selected `2.1.273` print path that restores `running_background_tasks`,
  yields `restoredOrphans`, wakes default-enabled orphans, or enqueues a
  pending notification MUST be gated by terminal stop, durable state clearing,
  and target no-wake/no-model proof before startup. `connect(prompt=None)` and
  print/stream-json mode alone are not such proof. In a mode that does not
  auto-resume, the implementation MUST still prove current-run native
  child/tool quiescence and exclusion before release. If automatic orphan
  resume cannot be held safely, the public configuration MUST refuse
  zero-inference swap support.
- **FR-010**: Exact coordinator restoration MUST validate the existing native
  transcript identity, exact UUID, selected account, transcript-storage family,
  current permission mode, prescribed model/configuration fingerprint,
  workspace, and successful exact loader initialization. It MUST use the exact
  native resume path and MUST NOT fall back to a title, picker, fork,
  continuation prompt, or unknown ID. Failure to load that exact coordinator
  MUST refuse the operation; coordinator-only or parent-only resume MUST NOT
  count as a successful lane restoration.
- **FR-011**: For every unfinished native worker, the final operator report
  MUST assign exactly one of `exact-resumed`, `restart-pending`, `restarted`,
  or `unresolved`. While held, a child eligible for exact continuation MAY be
  shown as the interim `resume-pending` state, but MUST NOT be called
  `exact-resumed` before release. `exact-resumed` requires post-release
  correlated evidence that the original native task continued;
  `restart-pending` means exact continuation is unavailable and no new run has
  started; `restarted` requires post-release correlated evidence of a new native
  task; `unresolved` covers missing, contradictory, cancelled, or unlinked
  evidence.
- **FR-012**: The system MUST NOT claim that exact coordinator restoration
  alone proves a full native graph freeze, graph repoint, or complete worker
  context preservation. Such claims require worker-specific evidence and the
  reported disposition for every unfinished worker.
- **FR-013**: When exact native worker continuation is unavailable, the system
  MAY compose an ordinary restart instruction from durable native identities,
  statuses, prescribed model/effort/custom-agent definitions, and coordinator
  context, but MUST dispatch it only after target account readiness and explicit
  release. The instruction MUST NOT be persisted as a semantic handoff,
  summary, or checkpoint, and its accepted send MUST NOT prove restart.
- **FR-014**: Worker restart MUST use the actual native coordinator/child
  interface and existing native conversation/task records. It MUST preserve the
  worker's prescribed role, model, effort, and custom-agent definition, and
  MUST report `unresolved` when correlated native start/lifecycle evidence is
  absent, partial, user-cancelled, or linked to the wrong task. It MUST NOT
  restart against the exhausted source account.
- **FR-015**: Swap MUST create or require no model-generated summary,
  checkpoint, written handoff, commit, push, stash, reset, or worktree
  reconstruction. Model usage for any post-release worker restart MUST be
  reported separately from the zero-new-model-request account-control phase.
  This interval MUST begin at account-control entry before preflight/fencing
  and continue through held readiness until explicit release without resetting
  its baseline at interrupt, restore or recovery. Already in-flight pre-entry
  requests MUST be distinguished from new attempts. An unknown interval or
  any new request MUST prevent success and retain claims. Interrupt receipts,
  external query/tool gates or rejection of an issued request MUST NOT be
  treated as a persistent runtime inference fence.
- **FR-016**: Authoritative completion MUST keep completed worker work complete;
  neither exact resume nor model-assisted restart MAY replay completed work,
  duplicate a message/effect, or reopen a released claim without fresh
  ownership evidence. Unknown external effects MUST remain held and reported.
- **FR-017**: Writer exclusion MUST be owned by the session lineage that
  actually owns the work. A real isolated-worktree claim MAY be attached to
  that lineage when its canonical path and ownership are evidenced; a
  read-only lineage MAY have no claim, while a read-only coordinator MAY
  delegate to an explicitly authorized writable native child. The system MUST
  not infer read-only status, permissions, tools, or claims from the parent;
  actual child agent ID and immutable definition/permission evidence governs.
  It MUST NOT fabricate per-child session, process-group, or worktree claims.
- **FR-018**: The system MUST prove containment of the coordinator runtime
  process tree and join it with native Agent/task IDs plus lifecycle and tool
  facts. Native children MAY share the coordinator's OS process, account, and
  session name; per-child OS identity or PGID MUST NOT be required as a false
  safety proof.
- **FR-019**: A real isolated-worktree claim MUST be exclusive and
  non-overlapping across the host/workspace index, including equal, aliased,
  and ancestor/descendant paths. A collision MUST refuse before changing files
  or claims, while unique dirty and untracked work MUST be preserved.
- **FR-020**: Admission MUST either reject a racing native child/tool before
  launch or include it in the sealed roster with lifecycle and ownership
  evidence. Mail submitted after fencing MUST be rejected or durably pending;
  it MUST NOT be silently dropped.
- **FR-021**: `release` MUST require the matching ready operation and generation,
  occur at most once, and be the explicit boundary that permits normal model
  inference, queued native delivery, and permitted model-assisted worker
  restart. Held or unresolved work MUST NOT dispatch.
- **FR-022**: `ctx` MUST retain the current account, require a checkpoint
  supplied by the caller, and create a deliberate fresh held native coordinator
  context. Its worker policy MUST be explicit: `hold` stops and retains workers
  under their old lineage without claiming they live beneath an exited parent;
  `restart` creates new-lineage native workers from the supplied checkpoint only
  after release. Exact cross-parent native rebind MUST NOT be implied.
- **FR-023**: `ctx` MUST refuse an omitted, ambiguous, or unsupported worker
  policy and MUST NOT invent a checkpoint, parent/task mapping, child identity,
  or implicit restart. Native worker definitions retained or restarted by ctx
  MUST remain explicit and verifiable.
- **FR-024**: `handoff` MUST remain a separate user-requested operation. It MAY
  record only a checkpoint or reference explicitly supplied by the user, and
  MUST NOT be implicitly invoked by swap, ctx, release, or worker restart. It
  MUST NOT change account, native worker state, claims, or release state.
- **FR-025**: Child-targeted submission MUST queue while the lane is held and,
  after release, route through the actual native coordinator/child interface
  with correlated native acknowledgement. It MUST NOT use the obsolete
  per-worker SDK send/open or external child-session path.
- **FR-026**: Requests MUST have durable IDs and content digests. Exact retries
  MUST return the recorded result; reuse with changed content, stale generation,
  malformed framing, or an overlapping lifecycle operation MUST refuse without
  dispatching twice.
- **FR-027**: Before any mailbox send, the supervisor MUST durably record a
  correlated dispatch intent. A possible send without acknowledgement MUST
  remain uncertain and MUST NOT be automatically resent; an acknowledgement
  without durable completion MUST be reconciled before any retry.
- **FR-028**: Durable local state MUST be outside product worktrees, owner-only,
  atomic, and protected against unsafe modes, ownership, symlinks, traversal,
  and workspace mismatch. It MUST store native IDs, status, and evidence but no
  credentials, tokens, conversation bodies, generated prose, or handoff
  documents.
- **FR-029**: Profile resolution MUST be read-only, explicitly named,
  same-family, and authorized. It MUST verify the selected account and preserve
  each participant's prescribed permissions, model, effort, tools, workspace,
  and custom-agent settings; it MUST not silently inherit a read-only parent
  policy or broaden child capabilities. It MUST reject unsupported
  setup-token/auth combinations, remove inherited provider overrides, and never
  copy credentials or mutate launch configuration.
- **FR-030**: The coordinator's canonical lane/name/UUID guard and managed
  ownership projection MUST remain exact and fail closed. The guard MUST
  validate coordinator binding without requiring distinct child session names,
  UUIDs, or process groups, and MUST NOT be bypassed or removed.
- **FR-031**: A durable record using the superseded independent-worker schema
  MUST be refused as incompatible with an explicit reason. The system MUST
  NOT silently migrate, reinterpret, delete, or treat that record as evidence
  for native restoration.
- **FR-032**: The external `lane-swap <lane> --profile <profile>` boundary MUST
  remain compatible with Bash 3.2 and MUST preserve literal lane names,
  including `swap`. Managed and legacy front doors MUST refuse incompatible
  ownership or unsupported participant state rather than silently falling back.
- **FR-033**: Automated acceptance tests MUST use temporary local state and
  fake runtimes for deterministic control behavior. Fake evidence MUST NOT
  mark live Claude SDK, account transition, native participant, team,
  background-task, or quota support as verified.
- **FR-034**: Live account actions, profile transitions, and runtime probes MUST
  require explicit authorization and disposable scope. This feature MUST NOT
  perform unattended authentication, credential migration, account discovery,
  network setup, or quota claims.
- **FR-035**: Public status and help MUST distinguish swap, ctx, handoff, and
  release; identify the four worker dispositions; distinguish tracked native
  background tasks from unmanaged detached effects; publish tested runtime and
  participant kinds; and label all unverified capability claims explicitly.

### Key Entities

- **Coordinator lineage**: The canonical lane binding and one native
  coordinator conversation, including its native child Agent/task graph,
  process-tree containment evidence, account, generation, and release state.
- **Native worker record**: A runtime-owned Agent/task identity, parent/task
  linkage, participant kind, prescribed model/effort/custom-agent definition,
  mailbox/task/tool references, lifecycle evidence, completion state, and one
  of the four final unfinished-worker dispositions, with interim
  `resume-pending` permitted only while held before release.
- **Tracked background participant**: A native Agent task that has a captured
  runtime identity and correlated lifecycle events. A background launch flag is
  not itself an identity or quiescence proof.
- **Unmanaged effect**: A detached shell/background process, unknown
  descendant, ambiguous tool, or uncertain remote mutation that lacks
  authoritative stop/ownership evidence and therefore keeps the lane held.
- **Writer claim**: An exclusive optional claim owned by the session lineage
  that actually writes to a real isolated worktree. It is not a claim invented
  for each native child and is compared globally for path overlap.
- **Operation**: A durable swap, ctx, handoff, submit, recovery, release,
  shutdown, or unenrollment identity with generation, phase, fence, roster,
  profile, readiness, effects, claims, and release outcome.
- **Profile reference**: An explicitly selected authorized profile with
  non-secret account identity, transcript-storage family, model/configuration
  fingerprint, permissions, workspace, and custom-agent settings.
- **Checkpoint reference**: Content or a reference explicitly supplied by the
  user for `ctx` or `handoff`; swap and restart do not generate one.

## Success Criteria

### Measurable Outcomes

- **SC-001**: For every published native participant kind and pinned runtime
  version, acceptance evidence shows discovery, stop, lifecycle/tool
  accounting, and restart behavior, or records an explicit public refusal. The
  evidence names the actual versions and kinds tested; teams remain unproven
  unless separately demonstrated.
- **SC-002**: A deterministic swap scenario with one coordinator, at least two
  unfinished native workers, one completed worker, and one tracked native
  background Agent task reaches exact coordinator resume under the authorized
  target profile while held, with zero model requests during account control
  and zero generated swap handoff/summary/checkpoint artifacts.
- **SC-003**: The worker report assigns exactly one of `exact-resumed`,
  `restart-pending`, `restarted`, or `unresolved` to every unfinished worker;
  at least one post-release exact-continuation and one release-gated restart
  path are evidenced, and no restarted worker is described as the same
  conversation or identity.
- **SC-004**: The pinned-runtime startup audit covers every supported
  participant kind and proves zero parent or child inference before release;
  any configuration that cannot prevent or hold orphan auto-resume is publicly
  refused rather than marked supported from fake-only evidence.
- **SC-005**: Across crash, retry, partial-start, user-cancel, active-tool, and
  uncertain-effect scenarios, completed work is replayed zero times, an
  unacknowledged possible send/effect is automatically resent zero times, and
  unresolved claims remain held until authoritative evidence exists.
- **SC-006**: Concurrent lineage-level writer tests show zero duplicate or
  overlapping claims for equal, aliased, and ancestor/descendant real
  isolated-worktree paths, while unique dirty and untracked work remains
  unchanged.
- **SC-007**: `ctx` tests show a new held coordinator under the current account
  for explicit `hold` and `restart` policies, with old workers retained or new
  workers started only at the declared boundary; `handoff` changes only the
  explicitly supplied checkpoint/reference; neither operation changes swap
  account state implicitly.
- **SC-008**: Matching `release` permits each eligible queued native delivery or
  permitted restart at most once; stale, duplicate, unresolved, and held
  releases dispatch zero work.
- **SC-009**: Coordinator lane/name/UUID guard tests pass for native children
  sharing parent process/account/session identity, while incompatible managed
  ownership and superseded durable schemas refuse with explicit reasons and no
  destructive migration.
- **SC-010**: The canonical `tests/run.sh` suite passes on supported Linux and
  macOS-compatible Bash 3.2 syntax using temporary local/fake runtimes only;
  no test accesses real credentials, accounts, sessions, network services, or
  quota.
- **SC-011**: Public help/status documentation distinguishes swap, ctx,
  handoff, release, worker dispositions, tracked versus unmanaged background
  effects, tested runtime boundaries, and unverified live capability status.

## Assumptions

- Claude's native runtime and its authoritative Agent/task/lifecycle events are
  the source of truth for child identity and state. Child IDs are not assumed
  to be top-level session UUIDs.
- One lane has one coordinator lineage for swap. Native children may share its
  parent process, account, and session name; containment and joined runtime
  evidence, not fictitious per-child OS ownership, establish safety.
- Exact coordinator transcript identity and target account identity can be
  verified before a ready-held state. A missing or contradictory identity is a
  refusal, not a guessed replacement.
- Exact native worker continuation is runtime-dependent. The feature tests and
  publishes only the combinations it can prove; unsupported combinations stay
  `restart-pending` or `unresolved` and do not silently fall back.
- Runtime-owned native background Agent tasks may be supported only when their
  Agent/task IDs, parent/tool relationships, stop boundary, and restart events
  are captured and tested. A `run_in_background` flag or detached shell process
  is not evidence; unmanaged detached effects are held/refused.
- Native teams are outside the supported claim unless a later, separately
  evidenced runtime contract covers them. This decision does not infer team
  support.
- Writer claims are optional and belong to the owning session lineage only.
  Any isolated-worktree path used for a claim is real, canonical, and globally
  checked for overlap; read-only lineages need no claim, while a read-only
  coordinator may delegate to an authorized writable child whose own immutable
  definition and permissions are verified.
- `release` is explicitly authorized by the operator. Model-assisted restart
  may consume normal model capacity only after release and its usage is
  reported separately from account-control activity.
- `ctx` checkpoints and worker policies are explicit caller inputs. `hold`
  retains stopped workers under the old lineage; `restart` creates new-lineage
  workers after release from the supplied checkpoint. Exact cross-parent native
  rebind is not assumed.
- `handoff` is user-requested and may record a supplied checkpoint/reference;
  swap and restart generate no handoff, summary, or checkpoint document.
- Existing profile/storage, transport, ownership, and legacy safety work may be
  reused only after it is reconciled with native lineage semantics. A durable
  record from the superseded schema is incompatible and is not migrated.
- Cross-machine migration, automatic account rotation, credential copying,
  launcher/config mutation, quota guarantees, and unauthorised live actions
  are outside this feature.

## Open Questions for Planning

These questions are implementation-planning constraints, not permission to
weaken the acceptance contract:

- Which exact pinned Claude runtime and native participant kinds first pass the
  startup zero-inference, stop-boundary, exact-continuation, and release-gated
  restart probes?
- Which native lifecycle events and tool records are sufficient to correlate a
  partial or user-cancelled restart, and what deadline makes missing evidence
  unresolved?
- Which durable managed-state fields can be reused without accepting or
  silently migrating the superseded independent-worker schema?
- What operator-facing status and command syntax best exposes the four worker
  dispositions while keeping `ctx` hold/restart and user-requested `handoff`
  distinct?
