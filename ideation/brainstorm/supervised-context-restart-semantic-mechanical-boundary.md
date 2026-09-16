# Semantic and Mechanical Restart Boundary — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Let Claude produce semantic handoff content while one deterministic backend exclusively owns lifecycle writes, process replacement, and retry behavior.
Topics: supervised-context-restart, semantic-mechanical-boundary, semantic-handoff, ctx
Repository context: openRepoTools `/ctx` command, handoff skill, lane-handoff backend, and lane launch commands
Captured: 2026-09-15

## Possible feats

- **Single restart transaction API** — Accept model-produced handoff material and execute every mechanical state transition through one testable backend.
- **Thin `/ctx` command** — Reduce the model instruction to semantic capture followed by one guarded backend invocation.

## Focus

This document isolates the authority boundary between reasoning that requires the current model and mechanics that must behave identically every time. The current handoff skill includes extensive shell recipes, including direct `tmux respawn-pane` instructions, while `lane-handoff` contains overlapping mechanics. That duplication allows a session to reconstruct the destructive tail instead of calling one authoritative transaction.

## Proposed model

Split `/ctx` into two explicit phases:

1. **Semantic preparation:** Claude summarizes current reasoning, discovers and polls writers, and produces a structured handoff payload plus human-readable narrative.
2. **Mechanical commit and restart:** one backend validates identity, acquires the lane generation, snapshots trees, writes the handoff and protocol records, commits the transition, persists restart intent, and delegates replacement to the supervisor.

The backend accepts an operation-scoped input rather than asking the model to reproduce shell commands. It either completes the guarded pre-kill transaction or refuses with the old session intact. Once the restart commit point is crossed, the supervisor owns all subsequent process behavior.

The human-facing `lane` command remains responsible for lookup, attach, and operator-selected launch. It is not an internal primitive for a restart transaction. A private launch command has narrower semantics: launch this exact pending operation or refuse.

## Interfaces and boundaries

The model owns meaning, unresolved intent, and communication with live writers. It does not own compare-and-swap, tmux quoting, launcher selection, or success determination.

The backend owns state and process orchestration. It must not invent semantic handoff content when the old session is still available; late recovery after a crash remains a distinct degraded path.

## Alternatives and tensions

- Keeping all steps in a skill maximizes model flexibility but weakens reproducibility at the most destructive boundary.
- Making the entire handoff shell-only is deterministic but loses current reasoning and agent communication.
- A structured intermediate payload adds schema/versioning work but makes replay, validation, and tests substantially clearer.
- Direct in-process `/clear` could avoid process replacement if the harness offered a supported clear-and-seed operation; terminal keystroke injection is too race-prone to emulate that interface.

## Open questions

- What is the smallest structured payload that preserves semantic value without coupling the model to backend state schema?
- Does the backend write the final Markdown handoff, or splice a validated model-authored section into it?
- How should a partially prepared semantic handoff be exposed if lifecycle acquisition subsequently refuses?

## Relationships

This extends [Semantic Handoff Before Restart](automatic-context-rollover-semantic-handoff.md) by defining its implementation boundary. It produces [Durable Context-Restart Intent](supervised-context-restart-durable-intent.md) and hands process control to the [Pane-Resident Restart Supervisor](supervised-context-restart-pane-supervisor.md).
