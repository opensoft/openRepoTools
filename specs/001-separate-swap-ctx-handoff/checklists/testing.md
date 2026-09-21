# Verification Requirements Quality Checklist

**Purpose**: Formal release-gate review of fake, integration, and acceptance evidence requirements
**Created**: 2026-09-16
**Feature**: [spec.md](../spec.md)

- [x] CHK001 Are tests explicitly required and routed through the canonical serialized wrapper? [Spec §SC-005]
- [x] CHK002 Are real auth, sessions, quota, model calls, and network excluded from automated tests? [Safety, Spec §FR-018]
- [x] CHK003 Are multi-worker exact restore and completed-worker non-restore measurable? [Acceptance, Spec §SC-001]
- [x] CHK004 Are ownership races, operation concurrency, process/tool uncertainty, and crash phases represented? [Coverage, Spec §SC-002–SC-004]
- [x] CHK005 Is the fake/live evidence boundary operator-visible and immutable by fake runs? [Integrity, Spec §FR-018–FR-019]
- [x] CHK006 Is a separate opt-in live evidence gate required before publishing supported configurations? [Release Gate, Spec §FR-019]

## Native Architecture Override — 2026-09-16

The checked items above preserve the checklist's earlier review history. Their
independent-worker test assumptions are historical and superseded by the
approved native-subagent decision; they are not current acceptance criteria.
The items below are the active native-architecture evidence release gate.

### Evidence model and runtime gate

- [ ] CHK007 Does the acceptance language explicitly replace independent-worker fixtures with one top-level coordinator and native Agent/Task children, while retaining old results only as historical rewrite context? [History, Spec §Authority and history, Plan §Implementation sequence]
- [ ] CHK008 Are automated checks required to use temporary local state and fake event/runtime sources through the canonical serialized `tests/run.sh` wrapper, with no live account, network, credential, or model request? [Completeness, Spec §FR-033, SC-010, repo AGENTS.md §Testing your changes]
- [ ] CHK009 Do native-lineage fixtures require real coordinator/child identity fields—`agent_id`, `task_id`, native kind, launch tool, parent links, lifecycle, tool, effect, and ownership evidence—without inventing child sessions or process groups? [Coverage, Spec §FR-002, Data model §NativeChildRecord]
- [ ] CHK010 Are tests for sparse lifecycle events required to exercise current-run/task/parent-invocation joins, event watermarks, reused IDs, stale markers, and ambiguous joins that remain unknown/refused? [Edge Case, Spec §FR-007, Research §Decision: ledger native identity and lifetime separately]
- [ ] CHK011 Does evidence distinguish a returned `PostToolUse(Agent)` background-launch acknowledgement from an active child, requiring joined `SubagentStart`/`SubagentStop` and task/tool/parent events for quiescence? [Clarity, Spec §FR-006/FR-007, User Story 2 §Acceptance Scenarios]
- [ ] CHK012 Are tracked runtime-owned background Agents and unmanaged detached shells/effects represented by separate evidence paths, with native teams defaulting to unsupported unless their own capability proof exists? [Coverage, Spec §FR-003/FR-006, Data model §TeamObservation]
- [ ] CHK013 Does the live Gate 0 checklist require the actual SDK-selected CLI/transport path, exact runtime/SDK versions, executable/configuration digest, launch mode, no-auth orphan fixture, source terminal stop/clear evidence, and target no-orphan/no-wake/no-model trace? [Release Gate, Spec §FR-009, Plan §Implementation sequence]
- [ ] CHK014 Are separate evidence records required for a separately installed CLI such as `2.1.270` and an SDK-bundled path such as `2.1.273`, so one trace cannot certify another executable or mode? [Traceability, Research §Evidence and unresolved questions]
- [ ] CHK015 Does the evidence contract publicly refuse the configuration when startup may auto-resume or infer before release and the selected path cannot hold that behavior, rather than allowing a promptless-parent fake or print mode to pass? [Fail Closed, Spec §FR-009, SC-004]

### Worker, release, and effect evidence

- [ ] CHK016 Do acceptance scenarios distinguish `resume-pending` and `restart-pending` before release from final `exact-resumed`, `restarted`, and `unresolved` outcomes after release for every unfinished child? [Measurability, Spec §FR-011, Data model §NativeChildRecord]
- [ ] CHK017 Does post-release evidence require correlated original-task lifecycle events for `exact-resumed` and correlated new native task/Agent events for `restarted`, while treating accepted parent sends, partial starts, cancellations, wrong-task links, and missing events as insufficient or `unresolved`? [Acceptance Criteria, Spec §FR-013/FR-014, Data model §DispatchRecord]
- [ ] CHK018 Are zero new model requests and zero generated summary/checkpoint/handoff/commit/push/stash/reset/worktree artifacts measured for account-control swap, with any post-release restart usage reported separately? [Integrity, Spec §FR-015, SC-002]
- [ ] CHK019 Are matching-generation release, stale/duplicate release, durable dispatch intent, acknowledgement uncertainty, crash boundaries, and retry behavior covered with an at-most-once result and no automatic resend? [Recovery, Spec §FR-021/FR-026/FR-027, SC-005/SC-008]
- [ ] CHK020 Do completion and uncertain-effect scenarios prove that completed children remain complete, unknown tools/descendants/effects retain claims, and no ambiguous external action is replayed? [Safety, Spec §FR-008/FR-016, SC-005]
- [ ] CHK021 Are read-only-coordinator/writable-child policy checks and lineage-owned claims covered, including absence of fabricated per-child sessions/claims and preservation of actual immutable child permissions? [Coverage, Spec §FR-017, Data model §WorkspaceClaim and ChildWorktreeClaim]
- [ ] CHK022 Do path-ownership scenarios cover equal, aliased, and ancestor/descendant isolated worktrees across lanes, refusal before mutation, and preservation of unique dirty/untracked work? [Acceptance Criteria, Spec §FR-019, SC-006]

### Distinct commands, compatibility, and publication

- [ ] CHK023 Are `ctx --workers hold`, `ctx --workers restart`, user-requested `handoff`, and one-time `release` covered as independent scenarios with explicit checkpoints, lineage effects, and no implicit account or inference transition? [Consistency, Spec §FR-021–FR-024, SC-007]
- [ ] CHK024 Do schema-compatibility scenarios refuse missing/unknown/obsolete independent-worker records without deletion or migration, and do legacy guards/projections refuse conflicting ownership while preserving native coordinator lane/name/UUID checks? [Compatibility, Spec §FR-030/FR-031, Plan §Durable state and compatibility]
- [ ] CHK025 Are public help/status acceptance requirements checked for the four worker dispositions, tracked-versus-detached background distinction, tested runtime/kinds, and explicit unverified labels? [Completeness, Spec §FR-035, SC-011]
- [ ] CHK026 Does the fake/live boundary require explicit authorization and disposable scope for live probes, and prevent fake results from changing production capability status or asserting teams/background/quota support? [Integrity, Spec §FR-033/FR-034, SC-001]
- [ ] CHK027 Are shell acceptance requirements constrained to Bash 3.2-compatible syntax and the literal-lane `swap` case, with the canonical suite remaining the only supported suite entry point? [Platform, Spec §FR-032, SC-010, repo AGENTS.md §Testing your changes]
