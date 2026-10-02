## Why

`/ctx` currently kills its own pane after writing a handoff and treats `tmux respawn-pane` accepting a command as proof that a fresh Claude session started. A measured failure left the lane `PAUSED` with a valid handoff but no replacement process or visible error, and the planned automatic 65% rollover would reproduce that unsafe boundary without a stronger restart primitive.

## What Changes

- Make context restart a generation-fenced transaction that preserves exact fresh-session launch intent before replacing the old process.
- Replace direct respawn into the human-facing `lane` dispatcher with a pane-resident supervisor and a narrow internal launch operation.
- Keep a diagnostic and retry surface alive when profile resolution, launcher execution, Claude startup, or readiness confirmation fails.
- Keep the lane non-running until the replacement's transcript, agent, directory, binding, and liveness are positively confirmed.
- Require lifecycle ownership and mandatory preservation writes to succeed before `/ctx` can kill the current process.
- Separate model-authored semantic handoff preparation from deterministic state, tmux, launch, and retry mechanics.
- Add real process-lifecycle tests that distinguish tmux command acceptance from a confirmed replacement session.

## Capabilities

### New Capabilities

- `supervised-context-restart`: Defines the guarded `/ctx` transaction, durable restart intent, surviving pane supervisor, internal fresh-session launch, readiness confirmation, and idempotent failure recovery.

### Modified Capabilities

None. This repository currently has no baseline OpenSpec capabilities; relationships to the in-progress crash-recovery and automatic-rollover changes are expressed as dependencies rather than fictional baseline modifications.

## Impact

The change affects `commands/ctx.md`, the handoff skill, `lane-handoff`, `lane-start`, `lanes-edit.sh`, lane lifecycle sidecars, tmux process management, and lane helper tests. It introduces an integration boundary with the installed `pclaude` launcher owned by workBenches: either the new supervisor invokes that launcher as a child, or coordinated work there supplies the equivalent non-`exec` supervision seam. The `add-crash-consistent-lane-worktree-recovery` change must expose fail-closed transition ownership, and `add-automatic-context-rollover` must depend on confirmed supervised restart rather than raw respawn acceptance.
