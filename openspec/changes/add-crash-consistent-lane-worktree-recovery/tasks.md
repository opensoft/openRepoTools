## 1. Structured State Model

- [ ] 1.1 Define and version the lane-state and tree-sidecar schemas, including canonical lane, repository/estate identity, relative path, Git observations, owner, state, generation, operation ID, and timestamps.
- [ ] 1.2 Implement shape-aware resolution of the coordinator base, worktree root, and lane control root without deriving identity from profile or current directory.
- [ ] 1.3 Implement atomic sidecar reads and writes under one lane transition lock, with conservative refusal for unknown schema versions and malformed state.
- [ ] 1.4 Append an auditable lane event for every successful current-state transition and detect disagreement between the snapshot and event history.

## 2. Worktree Inventory

- [ ] 2.1 Implement registration and update of lane-owned tree sidecars without placing metadata inside Git worktrees.
- [ ] 2.2 Inventory governed feature worktrees by reference to their shape-prescribed paths rather than moving them into a conflicting lane-first layout.
- [ ] 2.3 Reconcile expected sidecars, latest handoff writers, `git worktree list --porcelain`, and directories present beneath the resolved worktree root.
- [ ] 2.4 Recalculate repository identity, branch or detached HEAD, commit, upstream, dirty files, untracked files, and unpushed commits for every discovered tree.

## 3. Crash-Consistent Swap

- [ ] 3.1 Change `/swap` and `lane-handoff` to compare-and-swap `RUNNING` to `SWAPPING` before inventory or preservation work begins.
- [ ] 3.2 Carry one generation and operation ID through writer polling, handoff refresh, lane pause records, and finalization.
- [ ] 3.3 Finalize `SWAPPING` to `SWAPPED` only after every mandatory step succeeds, and print readiness only after that transition lands.
- [ ] 3.4 Refuse stale or competing finalizers whose expected state, generation, operation ID, or owner no longer matches.
- [ ] 3.5 Preserve `SWAPPING` on every refusal or interrupted path and report the unfinished operation and completed steps.

## 4. Guarded Resume

- [ ] 4.1 Classify `RUNNING` without a verified owner as an ungraceful stop and `SWAPPING` without one as an interrupted swap.
- [ ] 4.2 Refuse duplicate coordinator or writer launches when a verified holder remains live.
- [ ] 4.3 Produce a resume reconciliation report that distinguishes safe, dirty, unpushed, unmanaged, missing, stale-registration, and possible-loss trees.
- [ ] 4.4 Keep state `SWAPPED` during launch and transition to `RUNNING` only after SessionStart confirms lane, transcript/session, agent, directory, and exclusive binding.
- [ ] 4.5 Delegate eligible missing-tree reconstruction to estate `resume` and refuse hand-rolled recreation or recovery claims for missing unpublished work.

## 5. Compatibility and Migration

- [ ] 5.1 Add a read-only compatibility path for lanes with no sidecar, preserving the existing explicit `--dir` refusal and launch behavior.
- [ ] 5.2 Create structured state for a legacy lane only during an explicitly named, repository-verified start, swap, or migration.
- [ ] 5.3 Introduce coordinator-base enforcement in a staged mode that first reports legacy feature-worktree launches before making them refusals.
- [ ] 5.4 Keep profile selection independent of lane identity and verify that profile rotation resumes the same coordinator and worktree inventory.

## 6. Verification and Delivery

- [ ] 6.1 Add tests for token exhaustion before `/swap`, during every mandatory swap step, after `SWAPPED`, and before replacement SessionStart.
- [ ] 6.2 Add race tests for competing swaps, competing resumes, stale finalizers, and live duplicate writers.
- [ ] 6.3 Add worktree tests for dirty and unpushed trees, missing parked trees, missing unpublished trees, unknown trees, stale registrations, detached HEAD, and shape-governed paths.
- [ ] 6.4 Add migration tests for legacy lanes with no directory, verified explicit directories, invalid repository identities, and repeated idempotent migration.
- [ ] 6.5 Update the lane manual and installed `/swap`/handoff guidance with the state meanings, recovery output, profile-switch sequence, and non-destructive boundaries.
- [ ] 6.6 Run `tests/run.sh`, capture the exact acceptance evidence, and link the implementation PR and final behavior back to this OpenSpec change before archive.
