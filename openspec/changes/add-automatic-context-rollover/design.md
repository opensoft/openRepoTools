## Context

Claude's installed status-line command already receives the harness context-window measurement and atomically publishes `context_pct` to a session-keyed snapshot under `~/.claude/usage-snapshots/`. The installed `UserPromptSubmit` usage guard reads that snapshot and emits latched warnings at 70%, 85%, and 95%. It is globally armed on this workstation, but it does not initiate a context rollover.

Manual `/ctx` is intentionally more than a process restart. The command asks Claude to run the handoff skill with `--restart`, so Claude can capture current reasoning, discover and poll writers, refresh the handoff, persist lane state, and only then let `lane-handoff --restart` respawn the pane. A shell-only watchdog cannot produce that semantic handoff, while a continuously acting watchdog can race an active model turn or tool call.

This change therefore composes existing context observation with manual `/ctx` at a safe lifecycle boundary. It depends on `add-crash-consistent-lane-worktree-recovery` and issue #91 for exclusive transition ownership, generation fencing, and the `RUNNING -> SWAPPING -> SWAPPED` lifecycle.

## Goals / Non-Goals

**Goals:**

- Automatically request the existing `/ctx` behavior when an eligible lane session reaches 65% context usage by default.
- Trigger only after a Claude turn has completed and no foreground tool operation is active.
- Preserve the semantic handoff, writer accounting, durable transition, and fresh-session first prompt of manual `/ctx`.
- Make each crossing one-shot, observable, configurable, and fail safe.
- Reuse the existing status-line snapshot and hook installation paths.

**Non-Goals:**

- Continuously poll Claude from a separate daemon as the primary design.
- Interrupt an active response, tool call, edit, or user input.
- Automatically roll over sessions that do not own a lane.
- Treat account rate-limit percentages as context-window usage.
- Replace compaction for non-lane sessions or guarantee recovery of state that was never written.
- Let repository-controlled content silently enable process respawning.

## Decisions

### 1. Reuse the session snapshot as the sole context signal

The controller reads the status-line publisher's session-keyed `context_pct`; it does not scrape terminal text, estimate tokens, or use a profile-level usage percentage. Automatic action requires a recent, numeric snapshot associated with the current transcript ID.

This reuses the only component that receives the harness context payload and keeps context identity session-scoped. A stale, missing, malformed, or mismatched snapshot produces no automatic action and leaves a visible warning at the next available hook surface.

### 2. Evaluate at the completed-turn boundary

A Claude `Stop` hook is the preferred controller because it runs after the assistant has finished its response. It reads the latest snapshot and requests rollover only when the turn is stopping normally. It MUST ignore subagent-stop events and MUST use the hook's re-entry indicator plus the rollover latch to avoid a feedback loop.

The hook does not run `tmux send-keys` from a timer and does not kill the pane itself. When the threshold is crossed, it records a one-shot request and returns supported hook feedback directing the main Claude session to invoke the handoff skill with `--restart` before beginning any new work. If the installed Claude version cannot safely continue a stopped turn from hook feedback, the implementation degrades to a warning and manual `/ctx`; it does not synthesize terminal input.

### 3. Keep policy in user-owned configuration

Automatic rollover is opt-in. Its configuration belongs in user-owned OpenRepoTools configuration outside the repository and outside rotating profile identity. Enabling the policy with no explicit threshold selects 65%; a valid explicit threshold overrides it. A one-launch disable takes precedence over persistent configuration.

Repository files may arm warning-only behavior, as the existing usage guard permits, but repository-controlled content cannot enable automatic pane replacement. This prevents a cloned repository from causing an unexpected restart.

### 4. Admit only a verified lane coordinator

Before requesting rollover, the controller verifies all of the following:

- the event belongs to the main Claude coordinator, not a subagent;
- a canonical lane is bound to the current transcript and tmux pane;
- the lane is owned by this live session and is in `RUNNING`;
- no swap, resume, or rollover operation is already active;
- the context snapshot is fresh and belongs to this transcript;
- the configured threshold has been reached.

Failure of any admission check leaves the process untouched. Ambiguous lane identity never falls back to the current directory, profile, or window title alone.

### 5. Fence and latch before asking Claude to continue

The controller writes an atomic rollover request keyed by canonical lane, lane generation, transcript ID, threshold, and operation ID before it returns feedback to Claude. The same session generation cannot create a second request for the same crossing. A request records `requested`, `handoff-started`, `completed`, or `failed`, while the lane lifecycle remains authoritative for ownership.

The request is not permission to overwrite newer state. The handoff operation must acquire the prerequisite change's lane transition lock and match the recorded generation and operation ID before entering `SWAPPING`.

### 6. Invoke the semantic `/ctx` workflow, not only its shell tail

The automatic feedback tells Claude to invoke the handoff skill with `--restart`. The skill updates the human/agent narrative and polls writers before calling the backend. The backend then performs the durable transition and pane respawn. Calling `lane-handoff --restart` directly from an external watchdog is not equivalent unless the semantic handoff has already been refreshed for this operation.

If any mandatory handoff or transition write fails, the current pane remains alive, the request becomes `failed`, and the user receives a precise instruction for manual recovery. Automatic retry requires a new explicit retry action; a Stop-hook loop is forbidden.

### 7. Preserve manual control and existing warnings

Manual `/ctx` remains available below or above the threshold and uses the same transition machinery. Warning thresholds remain independent. When automatic rollover is disabled or ineligible, the existing warnings continue to work. The controller reports why an eligible-looking rollover did not run without blocking ordinary non-lane Claude sessions.

## Risks / Trade-offs

- **The snapshot can lag the exact model state.** → Require a fresh transcript-matched snapshot and use 65% as a conservative default; evaluate again only at a later completed turn.
- **A Stop hook can recursively stop after injecting rollover work.** → Persist the latch before feedback, honor the hook re-entry field, and allow one request per lane generation.
- **Claude could fail to follow the injected handoff instruction.** → Never kill the pane from the hook; retain a visible pending/failed request and allow manual `/ctx`.
- **Automatic rollover can surprise an operator.** → Keep it opt-in, announce the trigger, make the threshold configurable, and support a one-launch disable.
- **The threshold may be crossed during a long turn.** → Finish that turn rather than interrupting it; 65% intentionally leaves headroom for handoff generation.
- **The prerequisite crash-consistency work may change its state schema.** → Integrate through its public transition operations and generation token, not by duplicating sidecar writes.
- **A repository could try to enable disruptive automation.** → Read enablement only from user-owned configuration, never from the checkout.

## Migration Plan

1. Land and deploy the crash-consistent lane lifecycle from `add-crash-consistent-lane-worktree-recovery`.
2. Add red-first tests for signal freshness, policy resolution, lane admission, turn-boundary behavior, latching, re-entry, and failure preservation.
3. Add the Stop-hook controller in warning-only observation mode and verify decisions against real session snapshots.
4. Install the hook idempotently into bare Claude and every profile through the shared profile configuration path.
5. Add explicit user-owned enable/disable and threshold configuration, defaulting enabled policy to 65%.
6. Enable automatic action only after the controller proves it can acquire the guarded lane transition and invoke the semantic handoff path.
7. Roll back by disabling the user-owned policy and removing the Stop-hook entry; manual `/ctx` and warning hooks remain available.

## Open Questions

- Which user-facing command should manage the persistent policy: extending `/usage-guard`, adding `/auto-ctx`, or a lane configuration command?
- What maximum snapshot age is strict enough for automatic action while tolerating normal status-line update cadence?
- Should a failed automatic request remain latched until manual acknowledgement, or permit one bounded retry after a fresh completed turn?
- Should a later emergency `PreCompact` hook only warn, or request the same rollover when the 65% boundary was missed?
