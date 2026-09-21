# Ownership Requirements Quality Checklist

**Purpose**: Formal release-gate review of lane, process, tool, and worktree ownership requirements
**Created**: 2026-09-16
**Feature**: [spec.md](../spec.md)

- [x] CHK001 Is managed enrollment atomically excluded from legacy launch rather than check-then-act? [Race Safety, Spec §FR-003]
- [x] CHK002 Are live, absent, unknown, read-failure, and dead-daemon ownership outcomes distinct? [Coverage, Spec §User Story 2]
- [x] CHK003 Are read-only coordinator and exclusive non-overlapping writer claim rules complete? [Completeness, Spec §FR-004]
- [x] CHK004 Is dirtiness explicitly allowed and separated from ownership conflict? [Consistency, Spec §FR-004]
- [x] CHK005 Are participant process group and tracked tool evidence requirements bounded without claiming detached-process containment? [Clarity, Spec §FR-011]
- [x] CHK006 Does completion release a writer claim before reassignment? [Lifecycle, Spec §User Story 2]

## Native Architecture Override — 2026-09-16

The checked items above preserve the checklist's earlier review history. Their
independent-worker ownership assumptions are historical and superseded by the
approved native-subagent decision; they are not current acceptance criteria.
The items below are the active native-architecture ownership release gate.

### Lineage and effective authority

- [ ] CHK007 Does the ownership model explicitly replace separate top-level worker ownership with one coordinator lineage that owns the native child graph and its writer exclusion? [History, Spec §FR-001/FR-017, Plan §Summary]
- [ ] CHK008 Are native child records prohibited from receiving fabricated top-level session UUIDs, SDK open/shutdown/release controls, process groups, or independent account ownership? [Completeness, Spec §FR-002/FR-018, Data model §NativeChildRecord]
- [ ] CHK009 Is the read-only-coordinator/writable-child case explicit, requiring the child's actual Agent identity, immutable definition, tools, permissions, model, effort, and custom-agent policy rather than inheriting the parent's read-only policy? [Clarity, Spec §FR-017/FR-029, Research §Decision: lineage claims and native policy are distinct]
- [ ] CHK010 Does a workspace-global lineage claim apply whenever any member may write, including a read-only coordinator with a writable native child, while children in that inherited workspace do not become competing owners? [Completeness, Data model §WorkspaceClaim and ChildWorktreeClaim, Plan §`ctx`, `handoff`, and claims]
- [ ] CHK011 Is an isolated child-worktree claim optional and limited to a real, canonical worktree whose owning lineage/child IDs and lifecycle are evidenced, rather than being inferred from a child task ID? [Clarity, Spec §FR-017/FR-019, Data model §ChildWorktreeClaim]
- [ ] CHK012 Are equal, realpath-aliased, and ancestor/descendant isolated-worktree paths defined as globally overlapping across lanes, with no path spelling loophole? [Coverage, Spec §FR-019, Data model §ChildWorktreeClaim]
- [ ] CHK013 Does a claim collision require refusal before files or claims change, while a unique dirty or untracked worktree remains accepted and unchanged? [Acceptance Criteria, Spec §FR-019, User Story 3 §Acceptance Scenarios]
- [ ] CHK014 Does the contract state that unknown or contradictory child identity, permissions, tools, ownership, or effects cannot inherit writable access and instead keep the lineage held or indeterminate? [Safety, Spec §FR-008/FR-017, Research §Decision: lineage claims and native policy are distinct]

### Native event and participant ownership

- [ ] CHK015 Are coordinator process-tree containment and native Agent/task, parent, invocation, lifecycle, and tool evidence joined without requiring a distinct OS process or process group for each native child? [Consistency, Spec §FR-007/FR-018, Data model §Control and safety invariants]
- [ ] CHK016 Does the ownership requirement keep a tracked runtime-owned background Agent in the native roster until lifecycle/effect evidence reaches a terminal boundary, while an unmanaged detached descendant keeps claims held? [Coverage, Spec §FR-006/FR-008, Research §Decision: background Agents are tracked; detached work is unsafe]
- [ ] CHK017 Are admission races defined so a native child/tool is either rejected before launch or admitted into the sealed roster with ownership evidence, and never silently omitted from the owner set? [Race Safety, Spec §FR-020, Plan §Control phases and swap]
- [ ] CHK018 Does authoritative worker completion keep its effects and claim complete through swap, retry, restart, and recovery until the required evidence permits release, with no claim reassignment by inference? [Lifecycle, Spec §FR-016, Data model §Control and safety invariants]
- [ ] CHK019 Are crash, unknown-holder, detached-effect, and missing lifecycle evidence requirements explicit enough to retain the applicable claim and block competing writers or automatic replay? [Recovery, Spec §FR-008/FR-016/FR-027, SC-005]
- [ ] CHK020 Are owner generation and lineage generation distinguished, with `ctx` changing the lineage/coordinator identity but not silently releasing or reassigning the durable owner claim? [Clarity, Spec §FR-022, Data model §CoordinatorRecord]
- [ ] CHK021 Is one active coordinator per lineage generation and one serialized operation boundary required to prevent concurrent native writers even when children share the coordinator's account, process, or session name? [Completeness, Spec §FR-004/FR-018, Data model §CoordinatorRecord]
- [ ] CHK022 Are native teams represented as a separate capability observation rather than flattened child ownership, and refused or unproven by default without identity, membership, stop, and restart evidence? [Scope, Spec §FR-003, Data model §TeamObservation]

### Projection, legacy, and preservation boundaries

- [ ] CHK023 Do legacy guards and managed projections refuse unknown local owners, stale bindings, conflicting legacy ownership, and unresolved native claims without bypassing the coordinator's canonical lane/name/UUID guard? [Compatibility, Spec §FR-030, Plan §Durable state and compatibility]
- [ ] CHK024 Does swap ownership explicitly preserve local work and prohibit worktree reconstruction, forceful claim takeover, or destructive cleanup when the operation succeeds or refuses? [Preservation, Spec §FR-005/FR-015, User Story 1 §Acceptance Scenarios]
