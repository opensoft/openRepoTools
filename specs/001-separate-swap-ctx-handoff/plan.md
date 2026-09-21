# Implementation Plan: Native Lineage Lane Operations

**Branch**: `001-separate-swap-ctx-handoff` | **Date**: 2026-09-16 | **Spec**: [spec.md](spec.md)

Deployment sequencing and release gates: [Fastest path to deployment](deployment-plan.md).

The bounded internal stop transaction is specified in
[native-stop.md](contracts/native-stop.md). Its implementation does not enable
held restore or close the live runtime gate.

The governed coordinator-wide interrupt and drain is specified separately in
[coordinator-interrupt.md](contracts/coordinator-interrupt.md). It is a
candidate internal transaction only: its sealed roster, at-most-once
authorization, independent drain evidence, and zero-request gate do not grant
runtime support or release capability.

The offline preservation and claim-reconciliation prerequisite is specified in
[native-source-history.md](contracts/native-source-history.md). It archives
validated source facts independently of active context and assesses the claim
index without adopting a target or retrying a transfer. Runtime-gate evidence
and a subsequent durable adoption transaction remain required.

The authorized follow-up is specified by
[native-adoption-transaction.md](contracts/native-adoption-transaction.md) and
[busy-parent-probe.md](contracts/busy-parent-probe.md). The adoption transaction
records held target ownership only; runtime publication and capability gates
remain separate. Legacy regression migration must preserve native equivalents
of applicable safety assertions.

## Named team roles

The Speckit workflow for this feature keeps the following assignments:

- **Astra** — architecture lead.
- **Sol High** — orchestration lead.
- **Luna Max** — implementation writer for the defined Speckit tasks.

The active agent platform supplies the models: Codex models when operating in
Codex, Claude models when operating in Claude. These named assignments are
platform-neutral and supplement the generic architect, orchestrator,
implementation writer, regression reviewer, and validation runner roles.

## Re-planning status

The approved [native-subagent decision](../../openspec/changes/separate-swap-ctx-handoff/native-subagent-decision.md)
is the architecture authority for this plan. The existing independent
top-level-worker implementation, requirements that prohibit native children,
and fake tests built around that model are historical and require rewrite; no
acceptance mark from them is carried forward. The governing specification and
contracts describe the native design. Implementation and runtime verification
remain tracked in `tasks.md`; the reconciled documents do not prove completion.

## Summary

Build an opt-in managed lane around exactly one top-level Claude SDK process,
session, and authorized account at a time. That coordinator owns the native
Agent/Task lineage. A durable child ledger records runtime identities and
lifecycle evidence; it does not create a top-level SDK session or process for a
child. Account control is model-independent through a monotonic source
admission fence distinct from the explicit release fence.
The coordinator's exact restore is mandatory; if the exact parent loader or its
identity checks fail, the operation refuses. Independently, an unfinished child
is held as `resume-pending` only where the pinned runtime proves that path;
otherwise it is marked `restart-pending` and may be restarted by a normal model
instruction after release, without a written handoff.

## Technical context

**Language/Version**: Python 3 for the controller/SDK adapter; Bash 3.2 for installed wrappers
**Dependencies**: standard library for state/transport; optional official Claude Agent SDK, pinned and capability-tested
**Storage**: owner-only, same-store JSON/journal under the workspace Git common directory; no credentials or transcript bodies
**Testing**: fake runtime/event source through canonical `tests/run.sh`; no live account, network, or model request in automated tests
**Platforms**: Linux, macOS, and WSL2
**Runtime gate**: unresolved until the actual selected CLI/transport path of the pinned runtime (version and executable/config digest) proves promptless parent startup, child admission/tool fencing, no startup auto-resume or inference, native lifecycle stop boundaries, and exact parent/optional child continuation
**Scale**: one active coordinator lineage per lane, with a small native child roster; at most one active top-level coordinator session

## Architecture

### 1. Coordinator boundary

- `CoordinatorRuntime` is the only SDK/session/account owner. It records the
  exact top-level session UUID/transcript reference, selected profile/account,
  model, effort, permission mode, workspace fingerprint, and pinned runtime
  fingerprint. Its process group is owned and drained as a unit.
- Native children are invoked by that parent through the runtime's Agent/Task
  mechanism. They inherit the coordinator's SDK connection and account; the
  controller observes their native events rather than opening, shutting down,
  releasing, or assigning a top-level UUID/PGID per child.
- The parent adapter must expose lifecycle/tool events even after an Agent
  launch tool returns. A completed launch call is not child quiescence.

### 1.1 Coordinator-wide interrupt and drain

Account-control fencing has its own monotonic source admission epoch. After
the runner closes new parent inference, Agent/Task admissions, tool starts, and
mail, it acknowledges the same epoch and closes pending admissions before the
controller seals the complete live roster. The roster includes the coordinator,
active and terminal native children, accepted-but-unjoined admissions, nested
tasks, tools, descendants, and tracked effects. Actual identities and an
immutable identity digest are required; the progress watermark advances
separately with current-run events.

The controller persists a `coordinator_interrupts` intent with owner and
lineage generations, coordinator session, runner incarnation, fence epoch, and
roster digest before authorizing one documented coordinator SDK interrupt.
The authorization is at-most-once across duplicate requests, lost replies,
and runner restart; a cached positive authorization is never replayed. The
interrupt may run while children are active and starts a drain. Runtime receipt,
child terminality, tool termination, effect outcomes, parent-turn drain,
process exclusion, and model-request observation remain separate facts.

Parent shutdown follows proven complete-roster graph quiescence. A receipt,
parent exit, silence, or an empty participant map does not prove it. Process
tree exclusion is a separate gate after supported parent shutdown. The
operation retains claims and cannot release, launch a target, or use
model-assisted repair while any roster member, effect, process, request
interval, or capability fact is unknown. The interrupt is one control action
and is not assumed to be a persistent inference fence.

### 2. Native child lineage ledger

Each admitted native child gets one immutable identity record containing
`agent_id`, `task_id`, native `type`, launching `tool_use_id`, `parent_links`,
`transcript` reference/availability, `status`, `stop_provenance`, `model`,
`effort`, immutable `custom_definition`/policy fingerprint, and
`restart_correlation`. It also records tracked tool start/end and effect
evidence, execution mode (`foreground` or runtime-owned `background`), and an
optional isolated-worktree claim reference. A child transcript body is never
persisted. Because `SubagentStart`/`SubagentStop` events may omit task, tool,
and parent IDs, persist the pending Agent admission first and join events using
the current task/event-history watermark; an ambiguous join is unknown.

The ledger is lineage-scoped: the coordinator session is the sole root and
each child links to the actual native parent agent/task and launch tool. An
unknown or contradictory identity, permission, lifecycle, tool, or effect is
held/indeterminate, never guessed from the parent process exit.

Teams are a separate runtime capability and observation record. They are not
flattened into child entries and are not advertised as restorable until a
separate pinned-runtime probe supplies identity, membership, stop, and restart
evidence.

### 3. Control phases and swap

All transitions are serialized and journaled under one operation ID, durable
owner generation, lineage generation, and runner incarnation:

1. **Preflight** resolves the explicit profile read-only, validates schema,
   parent/child identities, claims, tracked tools/effects, and the pinned
   runtime capability record.
2. **Fence and roster seal** establishes the durable controller admission/mail
   fence and has the runner acknowledge that same epoch after closing new
   parent inference, child admissions, tool starts, and normal dispatch. The
   runner closes accepted but unjoined admissions and the controller seals the
   complete native roster, including nested tasks, tools, descendants, and
   effects, with actual identities, a roster identity digest, an immutable seal
   watermark, and a separate progress watermark. The adapter must prove on the actual selected
   CLI/transport path (recording runtime version and executable/config digest)
   that the parent can initialize promptlessly while both parent and children
   stay non-infering until `release`. The interactive takeover/restore path is
   known to be able to auto-resume native orphans before a prompt; it fails
   this gate. A stream-json/non-auto path must pass a no-auth orphan fixture;
   stream-json force-print alone is not proof because `print.ts` can derive
   restored orphans from runtime background-task state and wake the session.
   If the selected runtime cannot account for a complete roster or cannot
   expose the required interrupt/drain facts, refuse before any effect. Target
   connection must show no restored orphan, wake, or model-request evidence.
   If startup can dispatch and cannot be held, the operation is `unsupported`
   before account change. A `print.ts` classifier call without a callback is not
   evidence of a hold, and no callback/classifier state is invented or
   persisted.
3. **Interrupt/drain** persists the distinct `coordinator_interrupts` intent
   and its `may_have_been_sent` marker before the one coordinator-level SDK
   interrupt authorization. The interrupt may be issued while children are
   active. Keep the event/persistence readers live and record receipt,
   current-run child terminal events, tool ends, effect outcomes, parent-turn
   drain, process identity, and request observations independently. Natural
   completion remains completion; no receipt or parent exit is relabeled as
   quiescence. A positive or unobservable request interval blocks success.
4. **Quiesce and old-parent exclusion** first require complete-roster graph
   quiescence: every native child and pending admission is accounted for,
   tools/effects and descendants are terminal or authoritative, and the parent
   turn is drained. Only then observe any supported current-worker-state clear
   and request SDK shutdown. After shutdown, identity-revalidate and exclude
   the old coordinator process tree; target launch follows only after that
   separate exclusion gate is proven. Inability to prove any boundary leaves
   the operation held/unsupported.
5. **Parent restore** loads the exact coordinator transcript under the target
   same-family account using the official exact UUID path and validates account,
   permissions, model, workspace, transcript, and runtime evidence. Parent
   exact restore is required; failure refuses and never falls back to child
   restart. No model request or semantic handoff is made in the control phase.
6. **Ready-held** publishes the managed projection and reports every child as
   `completed`, `resume-pending`, `restart-pending`, or `unresolved`; no child
   has been resumed and no normal inference occurs yet.
7. **Release** is an explicit, one-time transition for the matching operation,
   owner generation, and coordinator runner incarnation. Only after it may
   queued work dispatch, an exact child continuation, or a model-assisted
   native child restart instruction be attempted. A parent send
   acknowledgement is not a restart: the ledger requires correlated new native
   Agent/Task lifecycle events; only those events transition `resume-pending` to
   `exact-resumed` or `restart-pending` to `restarted`, and the child remains
   uncertain otherwise.

The release tuple is consumed only for that operation and runner incarnation;
later swap/ctx operations remain valid under the same enrollment and owner
generation.

Completed children remain complete and are never replayed. Uncertain effects,
unknown ownership, or a failed correlation leaves the operation held or
indeterminate and blocks automatic retry.

### 4. `ctx`, `handoff`, and claims

- `ctx --hold` creates a fresh held coordinator context from its explicit
  checkpoint while retaining stopped native-worker records and claims. It
  changes the `lineage_id`/coordinator UUID and lineage generation, not the
  durable owner/lane generation; that owner generation changes only after a
  proven unenroll/re-enroll. It does not promise that live children survive
  parent shutdown.
- `ctx --restart` creates a new coordinator lineage from the caller's explicit
  checkpoint under the current account, likewise without changing owner
  generation. After that fresh coordinator is explicitly released, it may
  issue ordinary model instructions to restart native workers. This is not an
  exact cross-parent child rebind and creates no handoff document or generated
  checkpoint.
- `handoff` remains an explicit checkpoint-only operation; it does not pause,
  restart, change account, change claims, or release work.
- The lineage workspace receives one host/workspace-global claim whenever any
  member may write, including a read-only coordinator with writable children.
  A child in the inherited workspace is not a competing owner. A genuinely
  isolated child worktree takes its own exact claim, with realpath and
  ancestor/descendant exclusion across lanes. Unknown child identity never
  inherits writable access, and a read-only parent policy is never copied to a
  writable child; immutable native policy must be enforced by actual identity.

### 5. Durable state and compatibility

Keep the reusable profile/account resolver, same-store secure state, request
deduplication, journal/atomic writes, crash recovery, parent SDK process, and
legacy guard/projection/CLI safety. Add a schema version and native-lineage
record kind to every durable record. An older independent-participant record,
missing/unknown schema, or incompatible shape is refused explicitly; it is not
silently converted into native children. Recovery reconciles runtime events
before advancing a phase and never rewinds or repeats a release.

`shutdown` stops the active coordinator/lineage and retains the control service,
managed owner, workspace claims, and managed projection for status and recovery.
Only explicit `unenroll`, after authoritative stop/effect proof and claim
reconciliation, clears the managed projection and then the durable owner. The
projection transition must be journaled before owner clearing; legacy guards
continue to refuse while ownership or recovery remains unresolved.

The managed projection continues to use supported `lanes-edit.sh` operations.
Legacy `lane`/`lane-start`/`lane-handoff` entry points and the prompt guard must
refuse conflicting legacy ownership, while `lane-swap`, literal lane names,
bounded socket frames/deadlines, and malformed/stale request rejection remain
safe. No credential, provider override, workBenches mutation, or permission
bypass is introduced.

## Implementation sequence

1. Rewrite `lane_managed_state.py` and `lane_managed_controller.py` around the
   versioned coordinator/lineage schema, phase fences, global/inherited claims,
   deduplication, event journal, and crash recovery.
2. Refactor `lane_managed_sdk.py` and `lane_managed_daemon.py` to one parent
   SDK process and an event adapter for native Agent/Task/background lifetimes;
   keep teams on a separate capability path and fail closed without evidence.
3. Retain and verify the read-only profile resolver and mandatory exact parent resume,
   account identity/permission checks, and startup-gate probe. Gate 0 must
   resolve the actual SDK-selected stream-json/non-auto CLI, pin its runtime
   version and executable/config digest (or explicitly set and validate the
   CLI path), and run the no-auth orphan fixture with source terminal stop and
   a clear observed from supported runtime operations (never external state
   rewriting), plus target no-orphan/no-wake/no-model evidence; the prior
   system-CLI trace is informative only. Reject the known
   interactive auto-resume path. Implement child exact resume only behind a
   pinned capability record; otherwise implement the post-release
   model-assisted restart correlation, with current task/parent invocation and
   event-watermark checks for reused `agent_id` values.
4. Preserve CLI/socket and `lane-swap` behavior, legacy guards/projection,
   Bash 3.2 compatibility, and operation-specific `ctx`/`handoff`/`release`
   semantics.
5. Rewrite the independent-worker fake tests to emit native lifecycle events,
   including a background Agent whose launch call has returned, a read-only
   parent with an authorized writable child, unknown child identity refusal,
   detached/effect uncertainty, teams separation, startup auto-resume refusal,
   accepted-send-without-restart, exact-vs-assisted outcomes, and crash/dedup
   races. Run only through `tests/run.sh` when implementation is authorized.

Current independent prototype files and tests are a historical starting point.
Implementation follows the native tasks in this feature. Actual account changes
and authenticated runtime validation still require explicit authorization.

## Constitution and delivery gates

- PASS: this is the single Speckit feature handed from the governing OpenSpec
  change; no parallel replacement feature or duplicated task list.
- PASS: profile/account changes remain read-only, same-family, credential-free,
  and outside workBenches mutation.
- PASS: Bash remains 3.2-compatible and `tests/run.sh` is the canonical suite.
- PASS: fake evidence cannot mark live SDK support verified; no live session or
  network action is part of this plan slice.
- GATE: exact parent resume, native child stop/lifecycle semantics, and the
  startup no-auto-resume/no-inference fence remain `UNVERIFIED` for the pinned
  runtime. Until an opt-in probe publishes the selected CLI/transport path,
  runtime version, executable/config digest, no-auth orphan-fixture result,
  participant kinds, event evidence, and account/permission results,
  production status must say `unsupported` or `unverified`, never success.
