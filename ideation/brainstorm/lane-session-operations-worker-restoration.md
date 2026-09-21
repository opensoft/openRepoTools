# Worker Quiescence and Exact Restoration — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Treat a lane as a recorded coordinator-and-worker graph whose members must stop and resume without duplicate writers or invented recovery claims.
Topics: lane-session-operations, worker-restoration, worktree-inventory, resume-reconciliation
Repository context: openRepoTools Claude worker control and native session persistence
Captured: 2026-09-16

## Possible feats

- **Complete participant accounting** — Track workers and pending tool outcomes continuously so account exhaustion does not trigger an expensive discovery conversation.

## Focus

The user's target is to pause all workers and continue them after an account change. Restoring only the coordinator does not satisfy that target. Ordinary Claude subagents, agent-team teammates, independent background sessions, and shell jobs are different participant kinds.

## Proposed model

Maintain a roster from runtime events from launch onward. Each member records its native ID, parent, worktree, launch configuration, current turn/task, and restoration capability. A spawn racing with swap must be rejected or included before the roster is sealed.

Quiescence means no new model/tool work is admitted, accepted interruptions have produced terminal events, local writers have stopped or explicitly reached a safe boundary, and persisted histories identify what completed. It is not a promise that a remote request can be undone.

After replacement, reconcile the roster against live processes and saved conversations. Resume only unfinished supported workers, preserve parent/result routing, retain completed workers as completed, and prevent duplicate delivery of pending messages. Do not re-run a possibly successful external side effect solely because its result was lost.

Uncommitted files and unpushed commits can remain in their existing worktrees during a same-machine swap. No forced WIP commits, pushes, resets, moves, or worktree recreation are required. Their survival is local durability, not a backup or a cross-machine recovery guarantee.

## Evidence and limitations

Claude documents persisted ordinary subagent transcripts and their reuse after resuming the same parent. It also documents that user/SDK-stopped subagents do not automatically wake on a model message, and that in-process team members are not restored by session resume. See the [evidence register](lane-session-operations-evidence-and-delivery.md). Consequently, transcript existence alone is insufficient proof of resumability.

## Alternatives and tensions

Prefer native workers when their exact restore behavior passes tests. If the required control API is missing, independently resumable sessions owned by the supervisor are a possible later architecture. That would change delegation and message routing; it must be an explicit design decision, not a silent implementation fallback.

An unsupported worker kind blocks the fast path before planned termination. The command reports the exact limitation and may offer an explicit handoff path. It must not silently drop workers or spend model tokens to reconstruct them.

## Open questions

- Can the installed Claude version restore interrupted ordinary subagents externally under the new account without model-mediated relaunch?
- Can pending messages and result routing be recovered exactly, including nested workers?
- Which long-running tools can be detached and later reattached, and which require an indeterminate outcome?

## Relationships

- [External supervisor](lane-session-operations-external-supervisor.md)
- [Claude-first synthesis](lane-session-operations-synthesis-claude-first.md)
