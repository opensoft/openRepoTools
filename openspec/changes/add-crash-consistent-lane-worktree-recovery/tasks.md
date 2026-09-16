## 1. Structured State Model

- [x] 1.1 Define and version the lane-state and tree-sidecar schemas, including canonical lane, repository/estate identity, relative path, Git observations, owner, state, generation, operation ID, and timestamps.
- [ ] 1.2 Implement shape-aware resolution of the coordinator base, worktree root, and lane control root without deriving identity from profile or current directory.
- [x] 1.3 Implement atomic sidecar reads and writes under one lane transition lock, with conservative refusal for unknown schema versions and malformed state.
- [ ] 1.4 Append an auditable lane event for every successful current-state transition and detect disagreement between the snapshot and event history.

## 2. Worktree Inventory

- [x] 2.1 Implement registration and update of lane-owned tree sidecars without placing metadata inside Git worktrees.
- [ ] 2.2 Inventory governed feature worktrees by reference to their shape-prescribed paths rather than moving them into a conflicting lane-first layout.
- [x] 2.3 Reconcile expected sidecars, latest handoff writers, `git worktree list --porcelain`, and directories present beneath the resolved worktree root.
- [x] 2.4 Recalculate repository identity, branch or detached HEAD, commit, upstream, dirty files, untracked files, and unpushed commits for every discovered tree.

## 3. Crash-Consistent Swap

- [x] 3.1 Change `/swap` and `lane-handoff` to compare-and-swap `RUNNING` to `SWAPPING` before inventory or preservation work begins.
- [x] 3.2 Carry one generation and operation ID through writer polling, handoff refresh, lane pause records, and finalization.
- [x] 3.3 Finalize `SWAPPING` to `SWAPPED` only after every mandatory step succeeds, and print readiness only after that transition lands.
- [x] 3.4 Refuse stale or competing finalizers whose expected state, generation, operation ID, or owner no longer matches.
- [x] 3.5 Preserve `SWAPPING` on every refusal or interrupted path and report the unfinished operation and completed steps.

## 4. Guarded Resume

- [x] 4.1 Classify `RUNNING` without a verified owner as an ungraceful stop and `SWAPPING` without one as an interrupted swap.
- [ ] 4.2 Refuse duplicate coordinator or writer launches when a verified holder remains live.
- [x] 4.3 Produce a resume reconciliation report that distinguishes safe, dirty, unpushed, unmanaged, missing, stale-registration, and possible-loss trees.
- [x] 4.4 Keep state `SWAPPED` during launch and transition to `RUNNING` only after SessionStart confirms lane, transcript/session, agent, directory, and exclusive binding.
- [x] 4.5 Delegate eligible missing-tree reconstruction to estate `resume` and refuse hand-rolled recreation or recovery claims for missing unpublished work.

## 5. Compatibility and Migration

- [x] 5.1 Add a read-only compatibility path for lanes with no sidecar, preserving the existing explicit `--dir` refusal and launch behavior.
- [x] 5.2 Create structured state for a legacy lane only during an explicitly named, repository-verified start, swap, or migration.
- [ ] 5.3 Introduce coordinator-base enforcement in a staged mode that first reports legacy feature-worktree launches before making them refusals.
- [x] 5.4 Keep profile selection independent of lane identity and verify that profile rotation resumes the same coordinator and worktree inventory.

## 6. Verification and Delivery

- [x] 6.1 Add tests for token exhaustion before `/swap`, during every mandatory swap step, after `SWAPPED`, and before replacement SessionStart.
- [ ] 6.2 Add race tests for competing swaps, competing resumes, stale finalizers, and live duplicate writers.
- [ ] 6.3 Add worktree tests for dirty and unpushed trees, missing parked trees, missing unpublished trees, unknown trees, stale registrations, detached HEAD, and shape-governed paths.
- [ ] 6.4 Add migration tests for legacy lanes with no directory, verified explicit directories, invalid repository identities, and repeated idempotent migration.
- [x] 6.5 Update the lane manual and installed `/swap`/handoff guidance with the state meanings, recovery output, profile-switch sequence, and non-destructive boundaries.
- [x] 6.6 Run `tests/run.sh`, capture the exact acceptance evidence, and link the implementation PR and final behavior back to this OpenSpec change before archive.

## 7. What the first implementation left (opensoft/openRepoTools#91)

The unticked items above are not oversights; each is named here with what
stands in its place today.

- **1.2 / 5.3 — the coordinator base.** Only the lane CONTROL ROOT is resolved
  (design decision 11). The coordinator-base invariant and its staged
  enforcement are not implemented, so a lane launched from a feature worktree is
  neither refused nor reported as one.
- **1.4 — snapshot/history disagreement.** Every transition that follows a
  lane-kind line is audited by that line, and the swap's own `PAUSED` is the
  event for the handoff; `SWAPPING` has no log event by design decision 12, and
  there is no detector that compares the two and reports a divergence.
- **2.2 — shape-governed feature worktrees.** The inventory covers the two roots
  a lane already owns. Worktrees at Speckit's feature-first paths are not
  indexed, and moving them is forbidden either way.
- **4.2 — duplicate refusal.** `lane-reconcile` REPORTS a live holder;
  `lane-start`'s existing duplicate refusals are unchanged, and no new refusal
  is added by this change.
- **6.2 — races.** Competing swaps, competing resumes, stale finalizers, a
  lifecycle write overtaken between its event line and its snapshot, and an
  inventory write filed under a superseded operation each have a case; a live
  duplicate WRITER on one worktree does not.
- **6.3 — worktrees.** Dirty, unpushed, missing-and-clean, missing-with-work,
  unknown, stale-registration, detached HEAD, a tree git answers in and cannot
  be read through, and a sidecar whose schema this tooling does not write each
  have a case; shape-governed paths do not, because 2.2 does not.
- **6.4 — migration.** A lane with no snapshot answering 8 everywhere, and a
  snapshot created by the first transition that runs, both have cases; an
  invalid repository identity and a repeated idempotent migration do not.
- **Cross-workstation replication** remains the open question the design states.
  The snapshot is local to one machine by decision 10.

### The sixth review round, and where each of its fourteen findings went

Automated review rounds are capped at **two per pull request** (Brett Heap's
ruling of 2026-09-16), and this change is at round six. That round was therefore
TRIAGED rather than taken: the two findings that are safety holes this capability
could not land with are in the branch, and the other twelve are filed as issues,
claimed by this lane, and named below with what each costs and what decides it.
Nothing is left as a comment thread and nothing is left unnamed.

**Taken on this branch.**

- **An unreadable lifecycle snapshot is no longer read as a lane that has none.**
  `lane_state_read` answers **9** for a record that IS there and cannot be
  opened, `lane-state` exits 9 rather than the 8 a launcher goes past, and
  `lane-reconcile` reports `UNREADABLE` / `indeterminate`. Fail-OPEN on a crash
  pronouncement is the one class this change exists to close (`R22`,
  Amendment 7(d)).
- **Every inventory write is serialized under the lane mutex.** `set-lane-tree`
  took it only for a FENCED write; the atomic rename underneath stops a reader
  seeing half a file and stops nothing else, so an unfenced observation could
  land after a newer fenced one and replace it.

**Filed, claimed, and deferred.**

- **`opensoft/openRepoTools#113` — the four reads that still turn a failure into
  an answer.** The holder ids (`|| :`, so an unreadable register reads as *no
  holder* and a crash is pronounced on liveness nobody established), an
  unreadable tree sidecar (`[ -r ] || continue`, so a record nobody can read and
  no record at all are one silence — and one such sidecar alone answers *this
  lane owns no worktree*), `git config --get branch.<b>.remote` (`|| :`, so a
  failed read fabricates the local upstream `./<merge>`), and `git worktree list
  --porcelain` (`|| :`, so a checkout whose registrations cannot be read looks
  exactly like one with none and the report can still say `resumable`). Each
  costs a wrong verdict or an omitted tree on exactly the machine a recovery is
  running on; what decides them is whether `indeterminate` is the answer at
  every one of these reads, as it already is at the holder's — a decision for
  the round that also settles how `lane-trees` carries a row it could not read.
- **`opensoft/openRepoTools#114` — the inventory fence, and the partial
  observation.** `SWAPPING -> SWAPPED` keeps the generation AND the operation by
  design (decision 13), so `set-lane-tree --generation G --operation O` still
  succeeds after that operation was finalized and a delayed poll overwrites the
  completed inventory; and the *all five empty* guard means `--dirty 1` alone
  files `upstream none, 0 unpushed` for a tree nobody read, which is the
  clean-and-published shape decision 18 removed from the other path. The cost is
  a superseded or invented reading that nothing downstream can tell from a
  current one; what decides the first is whether the lifecycle STATE joins the
  compare-and-swap (at minimum `SWAPPING`) or the operation id is invalidated at
  finalization, and the second is whether a partial observation is a usage
  refusal or is completed from one `lane_tree_now`.
- **`opensoft/openRepoTools#115` — validation beyond the `schema:` line.**
  `lane_sidecar_schema_ok` asks one question, so a truncated `schema: 1` file
  with no state and no generation passes it: readers emit empty fields and
  writers replace it, which is the act decision 17 refuses for an UNKNOWN schema
  performed against a known one whose content is not valid. The cost is the one
  loss no later reader can undo; what decides it is which keys, types and
  identity each kind of sidecar requires, and whether a malformed record of a
  known schema takes the same refusal path an unknown schema takes.
- **`opensoft/openRepoTools#116` — the tree's identity.** `tree_id_for` folds
  every character outside the manifest-key set to `-` and squeezes repeats, so
  `/tmp/a/b` and `/tmp/a-b` share one sidecar and a lane with two valid trees
  loses one from the inventory and from every classification; and the recorded
  `checkout` is never compared with the repository git reports, so a path
  occupied by a different checkout on the same branch at the same commit reads
  `ok` and a recovery relaunches a writer into it. Both cost a tree that is
  silently the wrong tree; what decides them is an injective id — or the `cksum`
  prefix on every path rather than on long ones only — WITH a migration for the
  sidecars already on disk, and a repository identity that is stable across a
  clone and answerable for a worktree.
- **`opensoft/openRepoTools#117` — what the READY line and the report claim.**
  `writer_count` rises before the observation and the sidecar write are known to
  have worked, so the READY line says *N worktree(s) recorded* for trees
  `lane-trees` does not carry; and the seen-set is seeded from every sidecar
  before the registration sweep, so a tree that WAS inventoried and whose
  directory is gone is reported `missing`/`possible-loss` and never
  `stale-registration`, with the `git worktree prune` remedy omitted and the
  estate's `resume` left to fail on it. The cost is a completeness signal a
  recovery operator should not trust; what decides the second is the tension
  with *one tree, one row* (`612ba5c`) — whether one row can carry both facts,
  or the registered-but-gone case is decided before the path is deduplicated.
- **`opensoft/openRepoTools#118` — `lane-handoff` takes a `CLOSED` lane to
  `SWAPPING`.** `--expect` asks only *has the lane moved since I read it*, so
  every state is a legal source for the swap transition and a terminal lane is
  reopened, polled, and finished at `SWAPPED` with a `PAUSED` record appended.
  The cost is a lifecycle that says a swap is what last happened to a lane that
  was ended; what decides it is a ruling rather than a guard, because
  `R-A11-11` binds this command — *a swap is never left unwritten* — so refusing
  the handoff would be the first time the lifecycle stopped the swap, and
  declining the transition silently would leave a `PAUSED` record beside a
  `CLOSED` snapshot.
