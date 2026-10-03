# Synthesis: Recovery of Interrupted Speckit Work — Brainstorm

Status: brainstorm
Kind: process
Summary: Continuous task attribution lets the lanes service prepare focused startup review while agents verify and continue unfinished work.
Topics: speckit-task-recovery, task-assignment, recovery-review, lane-session-operations, synthesis
Repository context: openRepoTools lane swap and Speckit implementation orchestration
Captured: 2026-10-03

## Possible feats

- **Recovery by task** — Connect child assignments and persistent evidence to a startup review plan without a final source model response.

## Members and their joints

Atomic members: [Task assignment](speckit-task-recovery-task-assignment.md)
and [Recovery review](speckit-task-recovery-recovery-review.md).

### Scope becomes durable evidence

The orchestrator identifies a task and role before delegation. The service
persists the assignment and joins actual child identities, later job admissions
and evidence references. Multiple children may contribute to one task;
individual terminal events remain distinct from task acceptance. Recorded
exceptions expand the task set explicitly.

### Interruption becomes a review plan

After a permitted transfer, the service supplies the observed candidate tasks
and unmatched items in the transition packet. The new parent checks task
acceptance and decides what to continue using its new account. This division
keeps collection and ownership decisions outside the AI harness while retaining
agent judgment for semantic review.

### Persistent jobs remain continuous

An EGS job belongs to its durable job record, even if its requesting child has
ended. Task review observes that job rather than replaying its command. File
observations remain provisional while a job may write, so a task cannot be
declared complete from an earlier child response alone.

## Emergent behavior

A lane can recover an identifiable set of unfinished deliverables after
exhaustion without asking A or every child for another inference turn. The
default reduces review scope, and exception/unmatched-item handling keeps that
scope honest when assignments do not cover every change.

## Tensions to hold

Smaller assignments improve review precision but increase launch and context
costs. Shared-task children improve parallel work but need explicit file
ownership and contribution reconciliation. The service's evidence cannot
replace acceptance review, and task grouping cannot replace source exclusion.

## Recombination opportunities

Use the same assignments for progress reporting and model routing for small
implementation tasks. A future forced-recovery design can consume the review
inventory after its independent process and effect safety gates pass.

## Open questions

The implementation must qualify its runtime joins and evidence collection;
the selected default does not add a task-policy prerequisite to lane swap.
See the [overview](speckit-task-recovery-overview.md) and governed contract.
