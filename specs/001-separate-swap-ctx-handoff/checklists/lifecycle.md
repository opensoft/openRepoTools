# Lifecycle Requirements Quality Checklist

**Purpose**: Formal release-gate review of operation phases, recovery, and concurrency requirements
**Created**: 2026-09-16
**Feature**: [spec.md](../spec.md)

- [x] CHK001 Are swap, ctx, handoff, recovery, and release effects distinct and non-overlapping? [Consistency, Spec §User Story 3]
- [x] CHK002 Are admission and mailbox fences, sealed roster, interruption, drain, pause, restore, ready-held, and release boundaries defined? [Completeness, Spec §FR-005–FR-007]
- [x] CHK003 Are concurrent and stale-generation operations required to refuse before mutation? [Coverage, Spec §FR-005/FR-016]
- [x] CHK004 Are crash/retry rules defined for every durable phase without duplicate restore, dispatch, replay, or release? [Recovery, Spec §SC-003]
- [x] CHK005 Are ambiguous tools, descendants, and external effects retained as visible blockers? [Exception Flow, Spec §FR-011]
- [x] CHK006 Is explicit release the sole boundary between promptless control and normal inference? [Clarity, Spec §FR-007/FR-014]

## Native Architecture Override — 2026-09-16

The checked items above preserve the checklist's earlier review history. Their
independent-worker lifecycle assumptions are historical and superseded by the
approved native-subagent decision; they are not current acceptance criteria.
The items below are the active native-architecture lifecycle release gate.

### Serialized phases and stop boundaries

- [ ] CHK007 Does the lifecycle contract explicitly replace the earlier independent-worker flow with one coordinator execution lineage and one serialized lane generation covering enrollment, admission, swap, ctx, handoff, submit, recovery, release, shutdown, and unenrollment? [History, Spec §FR-001/FR-004, Plan §Summary]
- [ ] CHK008 Are concurrent, stale-generation, duplicate-content, malformed, and overlapping lifecycle requests required to make no lifecycle change and to return a durable, distinguishable refusal? [Completeness, Spec §FR-004/FR-026, Data model §OperationRecord]
- [ ] CHK009 Does the swap fence cover new parent/child admission, tool starts, mailbox sends, and normal model dispatch before the native roster is sealed? [Clarity, Spec §FR-005/FR-020, Plan §Control phases and swap]
- [ ] CHK010 Are admission races specified with both safe outcomes—reject the child/tool before launch or include it in the sealed roster with lifecycle and ownership evidence—without a silent drop? [Coverage, Spec §FR-020, Data model §Control and safety invariants]
- [ ] CHK011 Does every supported native participant and tracked tool have a defined stop boundary based on lifecycle/effect evidence, rather than a completed Agent launch call, background flag, cancellation acknowledgement, or parent exit? [Completeness, Spec §FR-006/FR-007, Research §Decision: ledger native identity and lifetime separately]
- [ ] CHK012 Is the required ordering explicit: sealed native roster and durable whole-roster interrupt authorization, independent child/tool/effect drain, observed supported current-worker-state clear, parent shutdown and process-tree exclusion, then target parent launch, with receipt distinct from quiescence? [Clarity, Contract §coordinator-interrupt, Plan §Control phases and swap, Data model §Control and safety invariants]
- [ ] CHK013 Does the startup gate define zero parent/child inference before release on the selected path, with unsupported/held outcome when the runtime can dispatch or wake an orphan without a supported hold? [Safety, Spec §FR-009, Data model §OperationRecord]
- [ ] CHK014 Is exact coordinator restore mandatory and held, with no title/picker/fork/unknown fallback and no account-control model request before readiness? [Completeness, Spec §FR-005/FR-010/FR-015, Research §Decision: exact restore has a pinned capability gate]
- [ ] CHK015 Does ready-held status enumerate every child as completed, `resume-pending`, `restart-pending`, or `unresolved`, and prohibit normal dispatch while any held or unresolved blocker remains? [Clarity, Spec §FR-008/FR-011/FR-021, Plan §Control phases and swap]

### Worker outcomes and release boundary

- [ ] CHK016 Is the pre-release distinction unambiguous: a safely stopped exact candidate is `resume-pending`, while unavailable exact continuation is `restart-pending` and neither claims a post-release result? [Clarity, Spec §FR-011, Data model §Control and safety invariants]
- [ ] CHK017 Does `release` require the matching operation, owner/lineage generation, and coordinator runner incarnation, consume its token once, and refuse stale or duplicate requests without dispatch? [Acceptance Criteria, Spec §FR-021/FR-026, Data model §OperationRecord]
- [ ] CHK018 Are post-release exact-continuation requirements tied to correlated native lifecycle evidence for the original task, with `exact-resumed` withheld until that evidence exists? [Measurability, Spec §FR-011/FR-012, Research §Decision: post-release assisted restart is explicit and observable]
- [ ] CHK019 Are assisted restart requirements tied to the actual native coordinator/child interface and existing task records, with accepted parent send distinguished from `restarted` and absent, partial, cancelled, wrong-task, or ambiguous correlation becoming `unresolved`? [Completeness, Spec §FR-013/FR-014, Data model §DispatchRecord]
- [ ] CHK020 Are child-targeted messages explicitly pending while held, then routed through the actual native interface only after release with correlated acknowledgement, with the obsolete per-worker SDK send/open path excluded? [Consistency, Spec §FR-025, Plan §Control phases and swap]
- [ ] CHK021 Does the swap/restart contract prohibit generated semantic handoffs, summaries, checkpoints, commits, pushes, stashes, resets, and worktree reconstruction, while reserving user-requested checkpoint recording for `handoff`? [Scope, Spec §FR-015/FR-024, Plan §`ctx`, `handoff`, and claims]
- [ ] CHK022 Does `ctx --workers hold` explicitly create a fresh held coordinator while retaining stopped workers under the old lineage without promising that they remain live beneath an exited parent? [Clarity, Spec §FR-022, Plan §`ctx`, `handoff`, and claims]
- [ ] CHK023 Does `ctx --workers restart` explicitly create a new coordinator lineage from the supplied checkpoint, retain it held until release, and avoid claiming exact cross-parent child rebind? [Clarity, Spec §FR-022/FR-023, Data model §CoordinatorRecord]
- [ ] CHK024 Is `handoff` limited to a caller-supplied checkpoint/reference, with no implicit account transition, worker pause/restart, claim mutation, or release? [Consistency, Spec §FR-024, Research §Decision: `ctx`, `handoff`, and release remain separate]

### Recovery, effects, and monotonicity

- [ ] CHK025 Are crash boundaries before send, after possible send/before acknowledgement, after acknowledgement/before durable record, and during partial worker start mapped to durable reconciliation outcomes rather than automatic resend or replay? [Recovery, Spec §FR-026/FR-027, Data model §DispatchRecord]
- [ ] CHK026 Does the recovery contract preserve authoritative completion, hold unknown tools/descendants/ownership/effects, and block release or replay until evidence resolves the affected operation? [Exception Flow, Spec §FR-008/FR-016, SC-005]
- [ ] CHK027 Are allowed operation transitions durable and monotonic, with recovery reading runtime lifecycle/effect evidence before advancing and never rewinding or repeating release? [Clarity, Data model §OperationRecord, Data model §Control and safety invariants]
- [ ] CHK028 Is shutdown's ordering explicit—clear the managed projection first, journal that transition, then clear durable owner state—while unresolved shutdown/recovery continues to block legacy entry points? [Completeness, Plan §Durable state and compatibility]
- [ ] CHK029 Do durable request IDs/content digests and generation checks distinguish exact retries from changed-content, stale, malformed, duplicated, and concurrent requests, with at-most-once effects measurable in the acceptance criteria? [Measurability, Spec §FR-026/FR-027, SC-005/SC-008]
