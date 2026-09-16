# Synthesis: Reliable Context Rollover — Brainstorm

Status: brainstorm
Kind: architecture
Summary: A strict semantic boundary, durable launch intent, surviving supervisor, and positive readiness check turn `/ctx` into an observable and retryable transaction.
Topics: supervised-context-restart, reliable-rollover, durable-restart-intent, pane-supervisor, startup-confirmation, synthesis
Repository context: openRepoTools context clearing from handoff preparation through confirmed replacement
Captured: 2026-09-15

## Possible feats

- **Failure-visible `/ctx`** — Clear context automatically while ensuring every failed replacement leaves a pane, durable intent, and safe retry path.
- **Readiness-gated automatic rollover** — Give the 65% controller a completion condition stronger than tmux accepting a command.

## Members and their joints

Atomic members: [Semantic and Mechanical Restart Boundary](supervised-context-restart-semantic-mechanical-boundary.md), [Durable Context-Restart Intent](supervised-context-restart-durable-intent.md), [Pane-Resident Restart Supervisor](supervised-context-restart-pane-supervisor.md), and [Positive Replacement Startup Confirmation](supervised-context-restart-startup-confirmation.md).

```text
Claude semantic preparation
          |
          v
guarded SWAPPING -- mandatory writes --> SWAPPED + restart intent
                                              |
                                              v
                                    pane supervisor
                                      |         |
                               child ready   child fails
                                      |         |
                                      v         v
                                   RUNNING   visible retry
```

### Authority and commit points

The [semantic boundary](supervised-context-restart-semantic-mechanical-boundary.md) prevents model instructions from becoming an alternate mechanical implementation. The backend must own the lane generation before preservation begins. Failure to acquire ownership is a refusal, not a warning followed by process replacement.

`SWAPPED` is the preservation commit point, not proof of a running replacement. The [durable intent](supervised-context-restart-durable-intent.md) records exactly what must happen next and prevents a failed one-use environment variable from erasing fresh-session semantics.

### Process lifetime and feedback

The [supervisor](supervised-context-restart-pane-supervisor.md) is the first process started after the old session is replaced. Because it launches the agent as a child, launcher refusal or immediate exit cannot close the only diagnostic surface.

The [startup confirmation](supervised-context-restart-startup-confirmation.md) separates "tmux accepted a command" from "the intended new session owns the lane." That distinction controls when `RUNNING` and completed intent may be written.

### Failure and recovery flow

Failures before `SWAPPED` preserve the old session wherever it is still alive. Failures after `SWAPPED` preserve the completed handoff, restart intent, and supervisor. Retrying uses the same fenced operation unless an explicit recovery act proves it abandoned and advances the generation.

## Emergent behavior

Together these mechanisms make a destructive context reset recoverable at every boundary. The user can type one command in the successful case, while launch failures remain visible and machine-classifiable. Automatic rollover can wait for true completion rather than equating process replacement with success.

## Tensions to hold

- The SessionStart hook's read-only contract conflicts with using it as the writer of `RUNNING`; another bounded confirmation path may be required.
- A restart-only supervisor is easier to ship, while a permanent lane supervisor offers a cleaner general process model.
- Local restart intent enables immediate recovery but does not by itself provide cross-workstation continuation.
- Strict fail-closed generation handling can require explicit operator recovery for stale `SWAPPING` operations.

## Recombination opportunities

This cluster can become the execution prerequisite for [Automatic Context Rollover](automatic-context-rollover-overview.md). Its durable operation and error states can also strengthen ordinary profile swaps without making profile part of lane identity.

## Open questions

- Is a distinct persisted `STARTING` state needed, or is `SWAPPED` plus attempt status sufficient?
- Which repository owns the supervisor when `pclaude` is supplied by workBenches but lane state is supplied by openRepoTools?
- What positive evidence is portable enough for every supported agent?
