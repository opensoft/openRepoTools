# Crash-Consistent Lane Worktree Recovery Overview — Brainstorm

Status: brainstorm
Kind: reference
Summary: Make a multi-worktree lane resumable by deriving its worktree inventory, journaling swap transitions, and reconciling persisted intent with live Git and process evidence before relaunch.
Topics: lane-worktree-recovery-state, lane-management, worktree-recovery, swap, resume
Repository context: openRepoTools, with integration boundaries at the lane collision protocol, openRepoShape, Speckit, and estate park/resume
Captured: 2026-09-15

## Possible feats

- **Structured lane recovery** — Deliver canonical lane worktree roots, crash-consistent swap state, and a guarded resume report as one capability.

## Motivation

A lane can coordinate several worktrees containing dirty files or unpushed commits. Today the lane launch record identifies one coordinator directory, while writer worktrees live primarily in the handoff and process context. Token exhaustion can happen before `/swap` or after `/swap` begins but before it completes, leaving the next session unable to distinguish a clean handoff from an interrupted one.

Legacy lanes add another ambiguity: their human-readable handoffs may name a directory while their machine-readable event history does not. Asking the operator for `--dir` recovers the coordinator but does not discover or verify every worktree the lane owned.

## Goals

- Derive the complete expected worktree inventory for a lane on a workstation.
- Distinguish normal running, an in-progress swap, and a completed swap across process death.
- Detect token exhaustion before and during `/swap` without claiming a clean handoff.
- Prevent duplicate coordinators and writers through locked, generation-fenced transitions.
- Find and preserve dirty or unpushed worktrees before resuming.
- Delegate reconstructable feature worktrees to the existing estate `resume` mechanism.

## Non-goals

- Reconstruct missing uncommitted file contents from metadata.
- Delete unknown worktrees or stale paths automatically.
- Replace the estate parked record or hand-roll its Git operations.
- Treat a profile, absolute host path, or branch name as the lane's stable identity.
- Ratify the coordinator-base invariant merely by recording this brainstorm.

## What the system delivers

The coordinator starts from a canonical base checkout resolved from stable repository identity. Writer worktrees have deterministic or indexed locations and sidecar manifests. `/swap` uses a two-phase `RUNNING -> SWAPPING -> SWAPPED` transition. Resume compares those records with live session holders, Git worktree registrations, actual directories, branches, commits, dirty files, and upstream state before allowing a new SessionStart to return the lane to `RUNNING`.

The result is an explainable outcome: attach to the existing owner, complete or recover an interrupted swap, resume a cleanly swapped lane, rebuild durable parked trees, or refuse with precise evidence of possible loss.

## System model

```text
                         /swap
confirmed session   ----------------> transition journal
      |                                  RUNNING
      |                                     |
      v                                     v
canonical base ----> lane tree index --> SWAPPING
                          |                  |
                          v                  v
                    Git worktrees ------> SWAPPED
                          |                  |
                          +---- reconcile <--+
                                   |
                     attach / recover / refuse / resume
                                   |
                         confirmed SessionStart
                                   |
                                RUNNING
```

## Cluster map

- [Resumable Lane Ownership](lane-worktree-recovery-state-synthesis-resumable-lanes.md) — joins physical discovery, transition authority, and evidence-based recovery.

## How it fits

The proposal extends rather than replaces existing roles. The lane event log remains the append-only audit history. The sidecar provides atomic current state and a bounded local inventory. The handoff remains the human and agent resume narrative. `git worktree list` and Git status remain filesystem truth. Estate `park`, `status`, and `resume` remain the only mechanism for durably recording and reconstructing governed feature worktrees.

Implementation must account for the current openRepoShape worktree convention. If lane-first physical paths conflict with feature-first paths, the canonical lane root should index existing paths rather than move them.

The governed change is [add-crash-consistent-lane-worktree-recovery](../../openspec/changes/add-crash-consistent-lane-worktree-recovery/proposal.md), tracked in [opensoft/openRepoTools#91](https://github.com/opensoft/openRepoTools/issues/91). The brainstorm remains non-normative; the OpenSpec proposal, capability specification, and design define the implementation boundary.

## Key decisions and open questions

- Proposed: `SWAPPING` is entered before any handoff work; `SWAPPED` is committed only after every mandatory step succeeds.
- Proposed: `RUNNING` is written only by a confirmed SessionStart.
- Proposed: every transition is locked and fenced by generation plus operation ID.
- Proposed: the coordinator launches from a canonical base checkout and feature changes live in writer worktrees.
- Open: whether `RESUMING` is a separate persisted state.
- Open: how the lane index coexists with Speckit's feature-first worktree paths.
- Open: which recovery discrepancies block only a writer versus the whole coordinator.
- Open: which metadata is local and which is replicated for another workstation.

## Document map

### Synthesis

- [Resumable Lane Ownership](lane-worktree-recovery-state-synthesis-resumable-lanes.md)

### Atomic concepts

- [Canonical Lane-Owned Worktree Layout](lane-worktree-recovery-state-canonical-layout.md)
- [Crash-Consistent Lane Lifecycle](lane-worktree-recovery-state-crash-consistent-lifecycle.md)
- [Resume-Time Worktree Reconciliation](lane-worktree-recovery-state-resume-reconciliation.md)
