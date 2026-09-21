# Specification Quality Checklist: Separate Swap, Context, and Handoff for Native Claude Lanes

**Purpose**: Validate the revised specification against the approved native-subagent architecture before planning
**Created**: 2026-09-16
**Feature**: [spec.md](../spec.md)

## Revision authority and history

- [x] CHK001 The approved native-subagent decision is named as the authority,
  and this feature remains the sole implementation owner.
- [x] CHK002 Earlier worker-architecture artifacts are identified as history
  only; no superseded behavior is used as an acceptance target, migration rule,
  or proof.
- [x] CHK003 The specification does not require replacing native subagents
  with separate top-level worker conversations and does not carry a blanket
  native-participant prohibition forward.

## Content Quality

- [x] CHK004 The specification is written as operator outcomes and safety
  contracts, with implementation mechanics included only where they define
  observable acceptance evidence.
- [x] CHK005 All mandatory sections are complete: prioritized user stories,
  independent tests, acceptance scenarios, edge cases, requirements, entities,
  success criteria, assumptions, and planning questions.
- [x] CHK006 No template placeholders or clarification markers remain.
- [x] CHK007 Swap, ctx, handoff, and release are described as separate intents
  with distinct account, checkpoint, worker, and inference effects.

## Native lineage and runtime evidence

- [x] CHK008 The spec keeps the coordinator and native children in one
  coordinator execution lineage and treats runtime Agent/task identities and
  lifecycle events as authoritative.
- [x] CHK009 The spec permits shared parent OS process/account/session identity
  and avoids invented per-child top-level UUIDs, external open/release methods,
  or per-child process-group claims.
- [x] CHK010 The coordinator process tree is joined with native Agent/task,
  parent, and tool evidence; coordinator lane/name/UUID guarding remains exact.
- [x] CHK011 Exact native coordinator resume is required under the selected
  account when verified, with identity, account, permission, storage, and
  configuration evidence and no title/picker/fork/unknown fallback; missing
  exact parent resume refuses and coordinator-only success is not accepted.
- [x] CHK012 Every supported native participant kind and pinned runtime needs
  published discovery, stop, resume/restart evidence; native teams remain
  unsupported/unproven unless separately demonstrated.
- [x] CHK013 Tracked runtime-owned native background Agent tasks are evaluated
  through captured IDs and lifecycle evidence; no blanket background ban is
  used, and a background flag alone is not accepted as proof.
- [x] CHK014 Unmanaged detached shell/background processes and unknown
  descendants/effects refuse or hold; parent exit, cancellation acknowledgement,
  OS suspension, and fake-only evidence do not prove safety.
- [x] CHK015 `PostToolUse(Agent)` launch acceptance is distinguished from child
  quiescence through joined `SubagentStart`/`SubagentStop`, task, tool, and
  parent lifecycle ledger events, current-run/task/parent-invocation
  correlation, and an event watermark; reused IDs and stale completion markers
  do not prove quiescence.
- [x] CHK016 Startup orphan auto-resume is audited on the pinned runtime, and
  zero inference before release is proven or the public configuration refuses;
  the selected SDK/CLI path, version/digest, and launch mode are recorded.
  Print/stream-json behavior, including restored background tasks and pending
  notifications, is not accepted without terminal-stop, durable-clear, and
  target no-wake/no-model evidence.

## Worker continuation and release

- [x] CHK017 Exact native continuation is preferred when verified; eligible
  continuation is `resume-pending` while held and becomes `exact-resumed` only
  after correlated post-release evidence; unavailable continuation becomes
  `restart-pending` rather than silently changing worker architecture.
- [x] CHK018 Model-assisted native restart is allowed only after target account
  readiness and explicit release, uses existing native records/coordinator
  context, preserves prescribed model/effort/custom-agent definitions, and
  creates no written handoff/summary/checkpoint artifact.
- [x] CHK019 Restart acceptance is not treated as proof: correlated native
  task/lifecycle evidence is required for `restarted`; partial, cancelled, or
  unlinked runs are `unresolved`.
- [x] CHK020 Every unfinished worker reports exactly one of
  `exact-resumed`, `restart-pending`, `restarted`, or `unresolved`; restarted
  workers are not claimed to retain the old conversation or identity, and
  held exact candidates are clearly `resume-pending` rather than
  `exact-resumed`.
- [x] CHK021 Swap has zero new model requests and no generated checkpoint,
  summary, handoff, commit, push, stash, reset, or worktree reconstruction;
  post-release restart usage is reported separately.
- [x] CHK022 Explicit release is the inference boundary, is generation-matched
  and at-most-once, and is blocked by held or unresolved stop/effect evidence.

## Completion, effects, and writer ownership

- [x] CHK023 Completed work remains complete across swap, restart, retry, and
  recovery; uncertain sends/effects are not automatically replayed.
- [x] CHK024 Writer claims belong to the owning session lineage and are optional
  only when a real isolated worktree is evidenced; a read-only coordinator may
  delegate to an explicitly authorized writable native child, while no
  fictitious per-child claim, session, or process group is required.
- [x] CHK025 Equal, aliased, and ancestor/descendant isolated-worktree claims
  are globally exclusive, while unique dirty/untracked work is preserved.
- [x] CHK026 Unknown tools, descendants, writers, ownership, or external
  effects retain claims and leave the lane paused/indeterminate with a reason.
- [x] CHK027 Admission races, dispatch intent/acknowledgement, crash phases,
  partial starts, user cancellation, stale retries, and duplicate releases
  have explicit fail-closed outcomes.
- [x] CHK028 Child-targeted delivery queues before release and uses the actual
  native coordinator/child interface after release; obsolete per-worker
  SDK-send/open behavior is not an acceptance path.

## `ctx`, `handoff`, compatibility, and scope

- [x] CHK029 `ctx` is re-specified for native workers: `hold` stops/retains
  workers under the old lineage, `restart` creates new-lineage workers after
  release from an explicit checkpoint, and exact cross-parent rebind is not
  implied.
- [x] CHK030 `ctx` refuses omitted or unsupported worker policy and does not
  invent checkpoint, parent/task, or child mappings.
- [x] CHK031 User-requested `handoff` records only an explicitly supplied
  checkpoint/reference and is never implicit in swap, ctx, release, or worker
  restart.
- [x] CHK032 Durable records from the superseded worker schema refuse explicit
  compatibility/migration and are never silently reinterpreted or deleted.
- [x] CHK033 Profile, credential, permission, storage-family, local-state,
  transport, legacy ownership, Bash 3.2, and literal `swap` boundaries remain
  testable and scoped without weakening native lineage requirements.
- [x] CHK034 Live actions require authorization; fake tests cannot establish
  live SDK/account/team/background support, and cross-machine or credential
  migration remains out of scope.

## Success criteria and readiness

- [x] CHK035 Success criteria are measurable and technology-agnostic at the
  user-outcome level while naming the runtime evidence needed for capability
  claims.
- [x] CHK036 Success criteria cover exact coordinator resume, all four worker
  dispositions, release gating, startup orphan safety, tracked background
  tasks, detached unknowns, completed-work preservation, duplicate-effect
  prevention, lineage-level writer exclusion, and the prohibition on claiming
  a full graph freeze/repoint from coordinator resume alone.
- [x] CHK037 Success criteria cover distinct ctx hold/restart, user-requested
  handoff, at-most-once release, coordinator guard behavior, explicit schema
  refusal, and canonical suite constraints.
- [x] CHK038 The specification is ready for implementation re-planning, with
  the open planning questions recorded as constraints rather than unresolved
  acceptance markers.

## Validation notes

- Reviewed every story, acceptance scenario, edge case, functional requirement,
  entity, success criterion, and assumption against the approved decision and
  the tracked-native-background refinement.
- All checklist items pass. No requirement relies on the superseded worker
  architecture as acceptance evidence.
- Runtime feasibility, pinned-version evidence, and live account behavior are
  intentionally still release gates; this checklist does not claim they have
  been run.
