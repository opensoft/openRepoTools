# Synthesis: Lane Set Session Assembly — Brainstorm

Status: brainstorm
Kind: architecture
Summary: A multi-window lane workspace becomes coherent when tmux placement, lane-state dispatch, and profile-specific launch or attachment are decided together.
Topics: lane-set-workspace, session-binding, lane-management, profile-switch, synthesis
Repository context: openRepoTools set orchestration across tmux and workBenches profile launchers
Captured: 2026-09-29

## Possible feats

- **Verified set launch** — Produce a workspace map that names each lane, tmux window, running profile, and any refusal before presenting the Codex companion.

## Members and their joints

Atomic members: [Workspace topology](lane-set-workspace-topology.md), [Lane assembly](lane-set-workspace-lane-assembly.md), and [Profile and Codex companion](lane-set-workspace-profile-and-codex.md).

### Identity and placement

The topology requires one lane per named window. Lane assembly determines whether that window is newly started or already holds a live conversation. These cannot be independent: attaching a live transcript in a window still named `claude` leaves the guard's identity triple broken. The set should verify that each selected window is actually bound before presenting it as ready.

### Process and account flow

An available lane may be launched with a selected Claude profile; a live lane is reached as-is. The requested `team01a` profile therefore cannot be applied uniformly by window placement alone. The companion Codex pane uses its own launcher and profile choice, not a sixth Claude lane.

### Proposed sequence

1. Resolve the repository or set name and the intended lane membership.
2. Read lane state and profile information; preflight name bindings and external holds.
3. Create or reuse the tmux set session, then place or start one window for each eligible lane through the existing lane commands.
4. Launch or attach the separately specified Codex companion window.
5. Report the actual window-to-lane/profile map and every refusal or incomplete step.

This is an exploration of sequencing, not a promise that the current commands implement a transaction.

## Emergent behavior

The set could become a reproducible way to open a whole work context without weakening the one-lane-per-window guard. It could also expose profile mismatches and partially assembled sets that single-lane commands leave to the operator to notice.

## Tensions to hold

- Moving live tmux windows changes another session's layout; not moving them weakens the “one session contains the set” goal.
- A partial set might be useful but can make a six-window expectation false. All-or-nothing behavior may require rollback of newly created windows without touching pre-existing live processes.
- A live lane on another profile cannot be made `team01a` merely by attaching it; a separate governed swap behavior would be needed.

## Recombination opportunities

The [lane session operations packet](lane-session-operations-overview.md) may later supply explicit account-switch behavior, while this packet supplies workspace assembly. Neither depends on making the other an implicit side effect.

## Open questions

- Is the desired success condition “all requested windows exist” or “all requested lanes are running on the requested profile”?
- Should the set be transactional, partially successful with a report, or interactive at each refusal?
- What consent is required before relocating an already-live window from another tmux session?
