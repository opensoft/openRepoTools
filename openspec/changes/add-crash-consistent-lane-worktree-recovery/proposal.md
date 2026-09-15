## Why

A lane may coordinate several Git worktrees containing dirty or unpushed work, but its current launch record identifies only one directory and cannot distinguish a clean swap from token exhaustion before or during `/swap`. Resume therefore needs a structured, crash-consistent inventory that can find every lane-owned worktree and explain whether the previous session stopped cleanly before another process writes to it.

## What Changes

- Give each lane a structured worktree root derived from its stable repository/estate identity and canonical lane name, with one sidecar record per lane-owned tree.
- Record repository, branch, HEAD, upstream, writer/session identity, and last-observed dirty and unpushed state for each tree without placing orchestration files inside Git worktrees.
- Add a guarded lane lifecycle: `RUNNING` when SessionStart confirms the owner, `SWAPPING` before `/swap` begins preservation work, and `SWAPPED` only after every required handoff and pause write succeeds.
- Fence transitions with a generation and operation ID so a delayed swap or competing resume cannot overwrite a newer owner.
- Reconcile sidecar intent against live holders, `git worktree list --porcelain`, filesystem paths, branches, commits, dirty files, and unpushed commits before resuming.
- Classify `RUNNING` or `SWAPPING` without a matching live owner as recovery-required rather than treating it as a clean swap.
- Delegate reconstruction of durably parked feature worktrees to the existing estate `resume` mechanism; never recreate over unknown paths or claim that missing uncommitted files can be recovered.
- Migrate legacy lanes on an explicit, verified start or swap rather than inferring paths from prose or the caller's current directory.
- **BREAKING**: lane launch and swap become state transitions requiring exclusive ownership; ambiguous or inconsistent lane/worktree state blocks a competing launch instead of silently starting.

## Capabilities

### New Capabilities

- `lane-worktree-recovery`: Canonical lane worktree discovery, crash-consistent swap state, and evidence-based resume reconciliation for multi-writer lanes.

### Modified Capabilities

None. This repository has no existing OpenSpec capability specifications; current behavior is documented by the lane collision protocol and command manual.

## Impact

Tracked by [opensoft/openRepoTools#91](https://github.com/opensoft/openRepoTools/issues/91), with the existing `openRepoTools-3` Claude lane as the active implementation owner.

**Delivered in the first implementation**: the lifecycle snapshot with its generation and operation fence (`lane-state`, `set-lane-state`), the machine-readable worktree inventory taken at every handoff (`set-lane-tree`, `lane-trees`), the resume reconciliation that reports and resets nothing (`lane-reconcile`, printed by `lane-start` before it writes anything), the two-phase `/swap`, and `RUNNING` written by the act that confirms the binding. Design decisions 9 to 15 record where each of these departs from the decisions above and why.

**Not yet delivered**: the coordinator-base invariant and its staged enforcement, the inventory of shape-governed feature worktrees beyond the two roots a lane already owns, and any replication of this state to a second workstation. Each remains a task in `tasks.md`, and the lifecycle is local to one machine until they land.

The change affects `lane`, `lanes`, `lane-start`, `lane-handoff`, `/swap`/`/handoff`, the SessionStart integration, `lanes-edit.sh`, lane status rendering, and lane helper tests. It integrates with—but does not replace—the workspace register, handoff documents, `git worktree` plumbing, openRepoShape/Speckit worktree conventions, and estate `park`, `status`, and `resume` commands. Existing lane records and ad hoc writer worktrees require an explicit compatibility and migration path.
