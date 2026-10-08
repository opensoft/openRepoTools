# Pane-Resident Restart Supervisor — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Respawn `/ctx` into a small supervisor that launches the replacement as a child and remains visible with recovery instructions if that child cannot start.
Topics: supervised-context-restart, pane-supervisor, tmux, ctx
Repository context: openRepoTools pane replacement integrated with the installed pclaude launcher
Captured: 2026-09-15

## Possible feats

- **Surviving restart controller** — Keep one process alive in the lane pane while the old Claude exits and a fresh Claude is launched.
- **Visible launch failure** — Leave the exact launcher error and an idempotent retry command on screen instead of closing the pane.

## Focus

This document isolates which process owns the dangerous interval after `/ctx` kills the old Claude but before a fresh Claude is known to be running. `tmux respawn-pane` currently starts `lane <name>` or `pclaude` directly and treats tmux's acceptance as success. If the command returns or takes a no-launch route, the pane disappears with no surviving controller.

## Proposed model

Respawn the pane into a dedicated command such as:

```text
lane-restart-supervisor --lane <lane> --operation <operation-id>
```

The supervisor becomes the pane's root process. It reads and fences the durable restart intent, invokes a private launch primitive as a child, and waits for positive startup evidence. It never calls the human-facing `lane` dispatcher, whose job includes attach/select behavior and therefore permits successful outcomes in which nothing is launched.

If preparation or launch fails, the supervisor remains in the pane and prints:

- the lane, generation, and operation it attempted;
- the exact failed stage and exit status;
- the state and location of the handoff and restart intent;
- a safe retry command that consumes the same operation;
- a cancellation or inspection command where supported.

On success, the interactive child owns the terminal while the supervisor remains its parent. The implementation may either keep supervising for the life of the child or exit only after a tmux-safe handoff that preserves a failure surface for future restarts.

## Interfaces and boundaries

The supervisor owns process lifetime, diagnostics, retry, and launch-attempt status. It does not generate semantic handoff content, choose a lane from a picker, modify worktrees, or infer identity from the pane title.

The dedicated launch primitive owns exact directory/profile/agent argument construction. Existing `pclaude` may remain the account launcher, but it runs beneath the supervisor rather than replacing the only process capable of reporting failure.

## Alternatives and tensions

- A permanently resident supervisor around every Claude launch gives the cleanest lifecycle but changes the installed launcher architecture more broadly.
- A restart-only supervisor is smaller and fixes `/ctx`, although ordinary lane launches retain their existing process shape.
- A detached external daemon could supervise every lane but adds discovery, authorization, and service-lifecycle complexity that the pane itself already solves.
- A diagnostic shell on failure is convenient but must not accidentally imply the lane is `RUNNING` or permit an unfenced second launch.

## Open questions

- Should the supervisor live in openRepoTools or in the workBenches project that owns `pclaude`?
- Should the supervisor remain for the full Claude lifetime or only through confirmed startup?
- How should terminal signals and exit status propagate between tmux, the supervisor, `pclaude`, and Claude?

## Relationships

The supervisor consumes [Durable Context-Restart Intent](supervised-context-restart-durable-intent.md) and waits for [Positive Replacement Startup Confirmation](supervised-context-restart-startup-confirmation.md). Its launch request is produced only after the [Semantic and Mechanical Restart Boundary](supervised-context-restart-semantic-mechanical-boundary.md) completes preservation.
