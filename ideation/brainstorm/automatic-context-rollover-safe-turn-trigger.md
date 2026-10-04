# Safe Completed-Turn Trigger — Brainstorm

Status: brainstorm
Kind: process
Summary: Evaluate automatic rollover after a main Claude turn completes so context pressure never interrupts generation, tools, edits, or user input.
Topics: automatic-context-rollover, turn-boundary-trigger, claude-hooks, concurrency
Repository context: openRepoTools Claude hook installation and lane coordinator lifecycle
Captured: 2026-09-15

## Possible feats

- **Turn-boundary rollover request** — Add a one-shot Stop-hook controller that requests handoff work only after the coordinator finishes its current turn.

## Focus

This document isolates when an automatic context rollover is allowed to begin.

## Proposed model

The preferred trigger is the main session's completed-turn hook. At that boundary, no foreground model response or tool call should be interrupted. The hook reads the fresh session snapshot, verifies that automatic policy is enabled, and admits only a verified lane coordinator in `RUNNING` state.

Before returning feedback to Claude, it atomically records a request keyed by lane generation, transcript, threshold, and operation ID. Hook re-entry and repeated status renders then observe the latch and do nothing. The feedback directs Claude to perform the same semantic handoff as `/ctx` before taking new work.

## Interfaces and boundaries

The trigger decides whether to request rollover. It does not write the semantic handoff, kill a pane, or claim a lane transition. Those belong to the handoff workflow and crash-consistent lifecycle controller.

Subagent stop events are out of scope. An external timer may observe metrics, but it cannot inject keystrokes or restart the coordinator while the pane is busy.

## Alternatives and tensions

A `UserPromptSubmit` trigger is naturally serialized before the next model turn but risks consuming or delaying a prompt the user just submitted. A Stop trigger has no pending user prompt and is therefore the cleaner boundary.

An external service can react immediately at 65%, but immediacy is harmful when it means terminating active work. The safe boundary is more important than exact wall-clock timing.

## Open questions

- Which supported Stop-hook response best requests one additional handoff turn across installed Claude versions?
- Should a failed request remain latched until the user acknowledges it, or receive one bounded retry?

## Relationships

The trigger consumes [Session-Scoped Context Signal](automatic-context-rollover-context-signal.md) and delegates to [Semantic Handoff Before Restart](automatic-context-rollover-semantic-handoff.md).
