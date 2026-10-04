# openRepoTools Ideation

This directory holds non-normative brainstorm material. Documents under
`brainstorm/` describe possibilities for later specification and implementation;
they do not amend the lane collision protocol or the shipped command contracts.

## Brainstorm packets

- [Lane Set Workspace](brainstorm/lane-set-workspace-overview.md) — a proposed `lset` command that assembles one tmux window per Claude lane plus a separate Codex chat window, with lane membership and profile choices left for a later proposal.

- [Lane Task Broker](brainstorm/lane-task-broker-overview.md) — local lane communication through Omnigent with distinct profile/session/lane launchers; LS preserves parent swaps and task attachments, while the factory layer owns admitted local or remote worker placement and recovery.
- [Speckit Task Recovery](brainstorm/speckit-task-recovery-overview.md) — one task per implementation child as a preferred default, continuous task attribution and focused review after interruption.
- [Crash-Consistent Lane Worktree Recovery](brainstorm/lane-worktree-recovery-state-overview.md) — a proposed canonical lane worktree layout, two-phase swap state, and resume-time reconciliation model.
- [Automatic Context Rollover](brainstorm/automatic-context-rollover-overview.md) — an opt-in 65%-by-default, completed-turn trigger for the semantic `/ctx` workflow, dependent on crash-consistent lane transitions.
- [Supervised Context Restart](brainstorm/supervised-context-restart-overview.md) — a durable `/ctx` restart transaction with a surviving pane supervisor, explicit fresh-launch intent, and positive replacement readiness.
