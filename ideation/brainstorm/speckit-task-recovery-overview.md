# Speckit Task Recovery Overview — Brainstorm

Status: brainstorm
Kind: reference
Summary: Prefer one task per implementation child so interrupted lane work can be reviewed and continued from durable service evidence.
Topics: speckit-task-recovery, task-assignment, recovery-review, lane-session-operations
Repository context: openRepoTools owns swap recovery; Speckit-driven factory workflows consume the default
Captured: 2026-10-03

## Possible feats

- **Focused lane recovery** — Carry task attribution and acceptance evidence across an account transfer and give the resumed parent a bounded review plan.

## Motivation

Brett wants to identify the work needing review after a hard stop. Knowing
that children worked on four Speckit tasks should make those tasks the first
review targets. Small, checkable tasks also support the intended Sonnet work
assignments. A final source-account debrief cannot be required at exhaustion.

## Goals

- Prefer one Speckit task per implementation child run; permit multiple
  children on a task with explicit roles and file boundaries.
- Keep assignments, jobs and evidence traceable throughout work.
- Review uncertain contributions and continue useful work without replaying
  completed tasks or existing jobs.

## Non-goals

The default does not impose a mandatory one-task restriction on every agent,
prove runtime cancellation, authorize a hard stop, or change shipped global
Speckit policy. Support roles and declared exceptions retain bounded scope.

## What the system delivers

The proposed service records assignment facts and produces candidate review
groups in the existing transition packet. The resumed parent performs semantic
acceptance review and creates fresh children for safely unfinished work. Task
completion and repair completion remain evidence-based decisions.

## System model

The orchestrator assigns task scope; the service persists assignments and
observes children, files and jobs; an independently safe account transfer
produces the startup packet; B reviews uncertain tasks and continues accounted
work. Unmatched changes and effects stay visible even when they enlarge the
review beyond the named task set.

## Cluster map

- [Recovery of Interrupted Speckit Work](speckit-task-recovery-synthesis-interrupted-work.md) connects scope, evidence, persistent jobs and startup review.

## How it fits

The [lane-swap proposal](../../openspec/changes/separate-swap-ctx-handoff/proposal.md)
records Brett's October 3 preferred default. The [capability contract](../../specs/001-separate-swap-ctx-handoff/contracts/claude-cli-supervised-jobs.md#speckit-task-assignment-and-recovery)
and T055–T056 own implementation and verification in the existing feature.
The initial delivery remains graceful-only; hard-stop recovery is a future
gate. This brainstorm packet preserves the rationale and alternatives and is
non-normative; the linked governed documents carry the selected policy.

## Key decisions and open questions

The one-task default is preferred, with recorded bounded exceptions. Task
splitting follows independently checkable deliverables rather than line count.
Runtime association and evidence collection are pending implementation, and
the packet establishes no new installed capability.

## Document map

- Synthesis: [Recovery of Interrupted Speckit Work](speckit-task-recovery-synthesis-interrupted-work.md)
- Atomic: [Task Assignment](speckit-task-recovery-task-assignment.md)
- Atomic: [Recovery Review](speckit-task-recovery-recovery-review.md)
