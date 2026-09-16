## Why

`/ctx` currently kills its own pane after writing a handoff and treats `tmux respawn-pane` accepting a command as proof that a fresh Claude session started. A measured failure left the lane `PAUSED` with a valid handoff but no replacement process or visible error, and the planned automatic 65% rollover would reproduce that unsafe boundary without a stronger restart primitive.

**The measured failure is `opensoft/openRepoTools#94`** (Eagle, 2026-09-15T20:59Z, lane `openRepoTools-3`), and the cause was established before this change was implemented rather than inferred from it. `/ctx` respawned its own pane with `LANE_START_FRESH=1 … lane openRepoTools-3` and what came up was `claude --name openRepoTools-3 --resume <the uuid the /ctx had just paused>`. `lane-start` was not at fault — both of its `(( ! fresh ))` gates are present in the installed copy and in PR #87's branch version — and neither was `lane`, whose available branch ends in a plain `exec`. The variable never arrived: the installed launcher re-creates its child through tmux, and `claude-profile`'s own `act1_compose_child_command` states the rule it has to obey — *"`tmux new-session` hands the command the SERVER's environment, not this client's, so a variable the operator exported in their own shell reaches the child only if it is written into the command string"* — which is why it threads six values explicitly, and `LANE_START_FRESH` is not one of them. The defect capture's window, `claude-max-001-20260915205926-456327:@6`, is that launcher's own `claude-<profile>-<timestamp>-<pid>` pattern, so this is what happened rather than what might have.

Two consequences follow, and they are what this change is:

- **An environment seam cannot carry the fresh-session requirement**, because the boundary it must cross belongs to another repository; a seventh threaded variable would move the same fragility one release along. The requirement becomes a durable restart intent on disk, written before the old process is killed and read back whatever the environment did.
- **Nothing noticed**, because what tmux started *was* the launch: a launch that ends takes the pane with it. Amendment 11's own invariant is *"No path the launcher opened exits the pane"*, and `/ctx` opened a path that did.

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

## Dependencies and cross-links

- **`opensoft/openRepoTools#94`** — the measured failure this change answers. Its root cause is quoted above and recorded as a comment on the issue.
- **`opensoft/openRepoTools#91`** (`add-crash-consistent-lane-worktree-recovery`) — the lane control root, the `RUNNING → SWAPPING → SWAPPED → CLOSED` lifecycle and the generation/operation fence the restart intent is meant to sit beside. That change is in flight on `feat/crash-consistent-lane-worktree-recovery` and is **not on `main`**, so the restart intent is implemented as a sibling sidecar under the *same* control root, resolved by a `lane_control_root` written to be byte-identical to #91's, and the `SWAPPED → RUNNING` finalization is made through #91's `set-lane-state` **where the workstation has it** and skipped in silence where it does not. Nothing here blocks on #91 landing, and nothing here re-implements it.
- **`add-automatic-context-rollover`** — consumes this change's readiness-confirmed completion rather than raw `respawn-pane` acceptance.
- **Lane collision protocol** — Amendment 17(f) (the record before the kill), Amendment 17 Addendum 1 (h)–(k) (the kind, the writer count, one worktree one writer), Amendment 18(h) (one binding), Amendment 18 Addendum 2 (i-8) (the respawn's two doors, and *"no word is kept on `PATH` for it alone"*), Amendment 8(f) (ending somebody's process is not a boundary script's act), Amendment 8(a) step 4 / `R-A11-5` (a swap is never left unwritten) and `R-A8-1` (the `SessionStart` hook never writes, never touches the network, always exits 0).

## Impact

The change affects `commands/ctx.md`, the handoff skill, `lane-handoff`, `lane-start`, `lanes-edit.sh`, lane lifecycle sidecars, tmux process management, and lane helper tests. It introduces an integration boundary with the installed `pclaude` launcher owned by workBenches: either the new supervisor invokes that launcher as a child, or coordinated work there supplies the equivalent non-`exec` supervision seam. The `add-crash-consistent-lane-worktree-recovery` change must expose fail-closed transition ownership, and `add-automatic-context-rollover` must depend on confirmed supervised restart rather than raw respawn acceptance.
