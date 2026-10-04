# Lane Set Profiles and Codex Companion — Brainstorm

Status: brainstorm
Kind: architecture
Summary: The proposed set would treat its Claude profile request and companion Codex chat as distinct launch choices without changing a live lane's existing account.
Topics: lane-set-workspace, profile-switch, claude-compatibility, command-semantics
Repository context: openRepoTools orchestration calling workBenches `pclaude`/`pcodex` profile launchers
Captured: 2026-09-29

## Possible feats

- **Companion Codex window** — Launch a Codex chat in a separate window while the other windows are assembled as Claude lanes.

## Focus

This document isolates process and profile selection. In the example `lset openxfactory team01a`, `team01a` names the requested Claude profile. A Codex chat needs its own profile decision; the Claude profile string does not establish a Codex login.

## Proposed model

Each newly started Claude lane would use the workBenches profile launcher under an explicitly defined rule for `team01a`. A lane already live on this workstation is different: reaching its window attaches to its existing Claude process and account. The set command cannot truthfully claim that all five lanes are running on `team01a` if one or more attached processes use another profile. It should surface that difference and require an explicit account-switch path if uniformity is required.

The sixth window could launch `pcodex` with a separately chosen Codex profile, or with an explicit default if the proposal defines one. It is a companion chat in the same tmux workspace, not a Claude lane and not automatically subject to the Claude lane name guard. No conversation sharing between Codex profiles or between Codex and Claude is implied.

## Interfaces and boundaries

`openRepoTools` would own `lset` orchestration and installation. `workBenches` continues to own the profile launchers and credential isolation. The set command must not copy credentials, reinterpret a Codex profile from `team01a`, or silently swap an already-live Claude process. Whether a future Codex lane has its own binding protocol is outside this sketch.

## Alternatives and tensions

- The Codex profile could be required, optional with a documented default, or selected interactively; each choice changes whether `lset openxfactory team01a` is a complete command.
- A strict Claude-profile contract could refuse mixed-profile live lanes. A looser workspace contract could attach them while accurately displaying their current profiles.
- Starting one fresh Codex chat per invocation may duplicate work; reusing an existing companion window needs a separate identity and liveness rule.

## Open questions

- Which Codex profile should the companion window use, and how is it supplied?
- Does `team01a` override recorded profiles only for available lanes, or must the set reject a lane that cannot run under it immediately?
- Is the Codex window new on every invocation, or should it attach to a known existing chat?

## Relationships

- [Lane assembly](lane-set-workspace-lane-assembly.md) supplies the available/live distinction that controls whether a profile can be chosen at launch.
- [Workspace topology](lane-set-workspace-topology.md) gives Codex a separate window without redefining a lane.
- [Existing lane session operations](lane-session-operations-command-semantics.md) distinguishes profile, lane, transcript, and process identities.
