# Speckit Task Assignment — Brainstorm

Status: brainstorm
Kind: process
Summary: Prefer one Speckit task per implementation subagent run, with several children permitted to contribute to the same task.
Topics: speckit-task-recovery, task-assignment, lane-session-operations, worker-restoration
Repository context: openRepoTools lane swap; Speckit-driven factory implementation consumes the assignment policy
Captured: 2026-10-03

## Possible feats

- **Task assignment records** — Associate each implementation child run with a stable Speckit task scope and its evidence throughout execution.

## Focus

How can a replacement lane identify the work that might need review without
requiring an exhausted source account to summarize every child?

## Preferred default

Brett agreed on October 3 to prefer **one Speckit task per implementation
subagent run**. Several children may work on one task, with explicit roles and
file boundaries. A child taking a second independent task normally becomes a
new run with a new assignment. This is workflow guidance, not a lane-swap
prerequisite or a claim about existing Speckit behavior.

Break tasks into small, independently checkable deliverables with clear
acceptance criteria. This supports the intended use of Sonnet for bounded
implementation work; task size alone does not prove model suitability.

An orchestrator may record a bounded exception with the covered task IDs and
reason. Reviews spanning tasks may use their own review task or an explicit
supporting assignment covering the relevant IDs. Hidden scope expansion
defeats the recovery benefit.

## Interfaces and boundaries

Record repository and feature identity, task-list path and definition revision,
Speckit task ID, assignment/attempt, role, expected files/worktree, and progress
and acceptance-evidence references. Join these to the exact parent/source
generation, actual native child identity and initiating Agent call as observed;
include native runtime task IDs when available and admitted EGS job IDs as
they appear. A Speckit task ID is distinct from a Claude runtime task ID.

The orchestrator supplies semantic scope. The lanes service persists and joins
records as work proceeds. Neither child completion nor an unchecked statement
of success proves that the whole task meets its acceptance criteria.

## Alternatives and tensions

| Approach | Benefit | Cost |
| --- | --- | --- |
| One task per implementation run | Clear review and restart scope; simple progress accounting | More launches, repeated context and coordination |
| Several explicit tasks per run | Reuses context for tightly related work | A stop affects a larger review set; progress needs per-task evidence |
| Very small tasks | Easier verification and bounded assignments | Excessive splitting can hide integration work and add bookkeeping |

Several children sharing a task still need clear file ownership and one
coordinator responsible for reconciling their contributions and completion.
Split by deliverable and acceptance criteria rather than line count alone.

## Open questions

The default is selected in the [proposal](../../openspec/changes/separate-swap-ctx-handoff/proposal.md).
The assignment transport and runtime joins remain implementation work under
T055; this packet does not claim they are installed.

## Relationships

- [Recovery review](speckit-task-recovery-recovery-review.md) consumes these assignments.
- [Interrupted work synthesis](speckit-task-recovery-synthesis-interrupted-work.md) connects scope, evidence and recovery.
