# Speckit Recovery Review — Brainstorm

Status: brainstorm
Kind: process
Summary: Review tasks with unverified changes or outstanding jobs after interruption, preserving accepted work and continuing jobs.
Topics: speckit-task-recovery, recovery-review, lane-session-operations, worker-restoration
Repository context: openRepoTools service reconciliation and resumed-parent startup repair
Captured: 2026-10-03

## Possible feats

- **Task recovery inventory** — Produce a bounded review set from assignments, file observations, acceptance evidence and persistent job records.

## Focus

Which work needs review after exhaustion or a hard stop, and what does
restarting that work actually mean?

## Proposed review model

The lanes service derives candidate tasks from durable assignments and joins
them to child results/history, worktree changes, acceptance evidence and EGS
(execution-group supervisor) jobs. Include tasks with unverified changes or
outstanding jobs even when the child returned just before the stop. An ended
child response is not evidence that its task is accepted.

For example, children assigned to four task IDs produce four candidate task
groups. A reviewer checks each group's deliverables and acceptance evidence.
Already verified work stays complete. Partially implemented or uncertain work
is inspected and continued, or assigned to a fresh child after its effects are
accounted for. Multiple children on one task remain separate contributions
within that task group.

The four groups bound the review only when attribution is complete. Include
parent edits, declared multi-task exceptions, unassigned changes and unresolved
effects as additional review items. Do not guess a task from a filename or
discard unmatched work to keep the set small.

## Interfaces and boundaries

The service records deterministic facts and candidate scope. The resumed
parent or a reviewer evaluates semantic completeness against acceptance
criteria and supplies evidence. Repairs and verification are recorded
separately from the original immutable handoff outcome.

Restart means inspecting and continuing existing work. It does not reset user
files, replay accepted tasks or relaunch an EGS job that already has a stable
identity. Observe continuing jobs and retain their reservations; unknown
effects require reconciliation before further execution.

Apply the review after source exclusion and ownership/effect checks permit
startup. The initial delivery still requires its graceful idle/exit witness.
Hard-stop task review informs the future forced-recovery gate and does not
establish that a busy source can safely be killed or replaced.

## Alternatives and tensions

A broad review of the whole feature remains available when task attribution
is incomplete. Task grouping reduces repeated reconstruction, but task labels
alone cannot prove file ownership, successful completion or safe job replay.
Continuous evidence collection has a storage and bookkeeping cost; it removes
dependence on a final source-account debrief.

## Open questions

The service's assignment-to-evidence joins and candidate-list implementation
remain T055 work. T056 needs offline coverage for recently returned children,
shared tasks, outstanding jobs and unmatched changes.

## Relationships

- [Task assignment](speckit-task-recovery-task-assignment.md) supplies the grouping key and exceptions.
- [Interrupted work synthesis](speckit-task-recovery-synthesis-interrupted-work.md) explains the service/agent handoff.
