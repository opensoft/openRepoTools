# Lane Set Workspace Topology — Brainstorm

Status: brainstorm
Kind: architecture
Summary: An `lset` workspace could place each Claude lane in its own named tmux window and a Codex chat in a separate companion window.
Topics: lane-set-workspace, tmux, session-binding, lane-management
Repository context: openRepoTools lane orchestration, with workBenches profile launchers as dependencies
Captured: 2026-09-29

## Possible feats

- **One-window-per-lane workspace** — Assemble several existing lanes and a companion Codex chat under one tmux session without changing lane identity from window to pane.

## Focus

This document isolates the proposed tmux shape. A tmux session groups windows; each window groups panes; programs run in panes. The session is a workspace, not a Claude conversation. The current lane convention assigns one lane to a tmux **window**, whose name matches the lane name.

## Proposed model

For the user's example, `lset openxfactory team01a` could present one tmux session with six windows: five named `openxfactory-1` through `openxfactory-5`, each with a Claude pane, and a sixth Codex window with its own pane. Five is the example's count, not yet a rule for discovering set members.

The five lanes cannot instead be five panes in one window under the current name guard: one window cannot simultaneously have five lane names. Supporting that layout would require a separate pane-based identity design. Additional panes inside a lane window could host supporting shells, but they would not themselves become lanes merely by sharing the window.

## Interfaces and boundaries

This topology owns tmux grouping and visible window placement. It does not define lane registration, select a Claude or Codex profile, or make the Codex chat a Claude lane. The tmux session name may identify the set, but the lane guard's binding identity remains each window name plus its recorded conversation.

## Alternatives and tensions

- One tmux session with six windows preserves the existing window-name guard; two windows with five lane panes would not.
- Reusing an existing tmux session is less disruptive than creating another, but the intended behavior of repeated `lset` calls is undecided.
- Moving an already-live lane window into the set can change another tmux session's layout even though it does not duplicate the Claude process.

## Open questions

- Should `lset` create a new tmux session, reuse a named set session, or allow either explicitly?
- What should the set session and Codex window be named, and how should a name collision be handled?
- Should a live lane's window be moved into the set, linked, or left in place with a navigation aid?

## Relationships

- [Lane assembly](lane-set-workspace-lane-assembly.md) determines which lane windows appear and how they are reached.
- [Session assembly synthesis](lane-set-workspace-synthesis-session-assembly.md) combines this layout with lane and profile behavior.
- [Existing lane session operations](lane-session-operations-overview.md) concerns continuity within a lane, not multi-window workspace layout.
