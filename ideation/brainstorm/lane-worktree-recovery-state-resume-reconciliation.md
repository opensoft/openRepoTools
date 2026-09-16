# Resume-Time Worktree Reconciliation — Brainstorm

Status: brainstorm
Kind: process
Summary: Resume a lane only after comparing its persisted intent with live holders, Git worktree registrations, filesystem state, branches, commits, and unpublished work.
Topics: lane-worktree-recovery-state, resume-reconciliation, git-worktree, loss-prevention
Repository context: openRepoTools lane restart behavior and the separate estate `park`, `resume`, and `status` mechanisms
Captured: 2026-09-15

## Possible feats

- **Lane recovery report** — Classify every expected and discovered worktree before launching a replacement writer.
- **Safe rebuild delegation** — Recreate only worktrees whose commits and branch state are durably represented by the estate parked record or origin.

## Focus

This document isolates what resume must prove. A sidecar state records intent, but only live-process evidence, `git worktree list --porcelain`, filesystem inspection, and Git status reveal what survived a crash.

## Proposed model

Resume acquires the lane lock, resolves the canonical lane root, and reconciles three inventories:

1. expected trees from the lane sidecars and latest handoff;
2. registered trees from each repository's `git worktree list --porcelain`;
3. directories actually present beneath the canonical lane root.

For every tree it recalculates repository identity, branch or detached HEAD, current commit, upstream, dirty count, untracked files, and unpushed commits. It also checks the recorded writer/session against live holders. Stored `dirty`, `unpushed`, branch, and HEAD values are comparison points, never current truth.

Suggested outcomes:

| Persisted state | Observed holder | Outcome |
|---|---|---|
| RUNNING | live and matching | Attach or refuse a duplicate launch |
| RUNNING | absent | Ungraceful stop; preserve and inspect every tree |
| SWAPPING | live and matching | Swap still executing; do not compete |
| SWAPPING | absent | Interrupted swap; recovery required |
| SWAPPED | absent | Validate trees, then permit resume |
| SWAPPED | live | Inconsistent state; refuse until reconciled |
| CLOSED | any dirty or unpushed tree | Closure inconsistency; refuse cleanup |

A missing worktree may be rebuilt only when its branch and commit are durably available and the existing estate `resume` contract authorizes reconstruction. A path that may have held uncommitted work is reported as possible loss; metadata cannot reconstruct missing file contents.

Unknown worktrees beneath the lane root are never deleted. They are reported as orphan or unmanaged candidates and require adoption or an explicit operator cleanup act.

## Interfaces and boundaries

This process reads lane sidecars, lane event history, handoffs, session holders, Git registrations, and filesystem state. It may delegate reconstruction to the estate's `resume` command. It does not hand-roll WIP commits, force-add worktrees, reset branches, or delete unknown directories.

The lane mechanism and estate mechanism remain distinct: lane resume restores orchestration identity; estate resume reconstructs previously parked feature worktrees from durable branch and commit records.

## Alternatives and tensions

- Automatically rebuilding every missing path is convenient but cannot distinguish a clean removed worktree from lost uncommitted work.
- Refusing on every discrepancy is safe but may make ordinary stale registrations expensive; classifications should include precise operator remedies.
- A lane-first physical directory makes enumeration cheap, while an index over shape-governed feature paths avoids changing the current worktree contract.

## Open questions

- Which discrepancies are warnings, and which must block the coordinator launch?
- Can the coordinator start while individual trees remain recovery-required?
- How are cross-repository writer worktrees represented under one lane root?
- Should a clean, pushed, unknown worktree be adoptable automatically or only on a person's word?

## Relationships

The expected inventory comes from [Canonical Lane-Owned Worktree Layout](lane-worktree-recovery-state-canonical-layout.md). The meaning of stale state comes from [Crash-Consistent Lane Lifecycle](lane-worktree-recovery-state-crash-consistent-lifecycle.md).
