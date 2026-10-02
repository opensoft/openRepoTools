# Synthesis: Resumable Lane Ownership — Brainstorm

Status: brainstorm
Kind: architecture
Summary: A canonical worktree inventory, generation-fenced swap lifecycle, and evidence-based reconciliation together make lane recovery deterministic after token exhaustion or process death.
Topics: lane-worktree-recovery-state, resumable-lanes, worktree-ownership, crash-recovery, synthesis
Repository context: openRepoTools lane lifecycle integrated with openRepoShape estate worktree recovery
Captured: 2026-09-15

## Possible feats

- **Crash-explainable resume** — Report exactly where a lane stopped and what survived before any replacement process writes.
- **Recoverable multi-writer lane** — Restore the coordinator while preventing duplicate writers and preserving dirty or unpublished worktrees.

## Members and their joints

Atomic members: [Canonical Lane-Owned Worktree Layout](lane-worktree-recovery-state-canonical-layout.md), [Crash-Consistent Lane Lifecycle](lane-worktree-recovery-state-crash-consistent-lifecycle.md), and [Resume-Time Worktree Reconciliation](lane-worktree-recovery-state-resume-reconciliation.md).

```text
stable home/estate
       |
       v
canonical lane root -----> expected worktree inventory
       |                              |
       v                              v
RUNNING -> SWAPPING -> SWAPPED -> reconcile Git + disk + holders
                                      |
                         resume, attach, refuse, or recover
```

### Location makes recovery enumerable

The canonical layout turns an open-ended filesystem search into a bounded lane inventory. Repository identity and shape determine where to look; sidecars explain what each path was intended to be. This supplies the reconciliation process with expected inputs without making the sidecars the truth about Git.

### Transition state explains why the inventory was left

The same worktree state has different meanings depending on when the coordinator died. Dirty work beneath `RUNNING` with no holder means no swap began. The same work beneath abandoned `SWAPPING` means preservation began but did not complete. `SWAPPED` means the handoff procedure reached its commit point, although Git is still rechecked.

### Reconciliation controls the next transition

Resume does not blindly change `SWAPPED` to `RUNNING`. It first proves there is no competing holder and classifies every tree. Only a confirmed SessionStart owns the transition to `RUNNING`. Generation and operation fencing prevent either the old swap or a second resume from overwriting the new owner.

## Emergent behavior

Together, the three mechanisms distinguish clean pause, pre-swap crash, mid-swap crash, failed launch, stale process, lost path, and durable rebuild. None of the three can provide that result alone: layout finds things, lifecycle explains intent, and reconciliation tests reality.

## Tensions to hold

- Lane-first layout improves discovery but must not contradict shape-governed feature paths.
- More persisted state improves diagnosis but creates more transition and migration obligations.
- A coordinator-base invariant simplifies identity but changes today's permission to launch a lane directly in a feature worktree.
- Automatic recovery should reduce routine work without masking potentially uncommitted loss.

## Recombination opportunities

- Add the reconciliation report to `lanes` and the SessionStart orientation block.
- Let `/swap` use the same inventory engine as resume, with different allowed transitions.
- Reuse estate `status` findings and `resume` reconstruction rather than duplicating Git worktree mechanics.

## Open questions

- Does the current openRepoShape worktree contract adopt lane ownership directly, or does openRepoTools maintain a sidecar index over it?
- What is the minimum state that must be replicated through the workspace repository for cross-workstation recovery?
- Which component owns garbage collection after `CLOSED`?
