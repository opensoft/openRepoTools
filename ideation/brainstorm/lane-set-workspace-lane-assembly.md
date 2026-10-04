# Lane Set Lane Assembly — Brainstorm

Status: brainstorm
Kind: process
Summary: An `lset` command could assemble lane windows by reusing the existing lane picker and starter's available, live, and bound-elsewhere safety rules.
Topics: lane-set-workspace, lane-management, session-binding, command-semantics
Repository context: openRepoTools lane register, picker, starter, and tmux integration
Captured: 2026-09-29

## Possible feats

- **Safe set assembly** — Resolve a requested group of lanes, attach live local holders, start available lanes, and report refusals without creating duplicate holders.

## Focus

This document isolates how a set command would choose and reach lanes. The user proposed `lset openxfactory team01a` and an example set of five lanes; neither the count nor the membership rule is settled. `openRepoTools` owns `lane`, `lanes`, and `lane-start`, while their register and logs live in the configured workspace repository.

## Proposed model

`lset` would first read the relevant lane records, decide which names belong to the set, and make one tmux window per selected lane. It must preserve the existing state distinction: an available lane can be started through the launcher; a lane already live on this workstation must be reached without launching a second Claude process; a lane bound elsewhere must not be started locally without a handoff. Closed or dormant lanes should not be silently revived merely to fill a target count.

The recent `openRepoTools-1` example shows why a window is not safe merely because its Claude transcript has a lane title: the picker attached a live conversation named for the lane while the tmux window remained `claude`, and the UserPromptSubmit name guard blocked work. A set command must verify the window, transcript, and row binding or report the mismatch; it must not rename or rewrite an uncertain holder by guesswork.

## Interfaces and boundaries

The command would orchestrate the existing `lane`/`lane-start` acts rather than invent another register writer or bypass their liveness checks. It would report each lane's final window and state. It does not itself define account swapping, handoff between workstations, or a new pane-based lane identity.

## Alternatives and tensions

- Positions 1–5 are predictable for the example, but some positions may not exist, may be closed, or may be bound elsewhere. “All eligible current lanes” follows the register but may yield a different count on every run.
- Attaching live windows avoids duplicate processes, but may move windows out of another session; starting all five afresh would conflict with live holders.
- An all-or-nothing set is easier to reason about, while partial assembly may be more useful when one lane refuses. The user-visible result must say which windows were actually assembled.

## Open questions

- Does the first argument identify a repository, a named saved set, or a prefix whose current eligible lanes are discovered?
- Are positions 1–5 explicitly requested, or is five only the example of currently active lanes?
- What happens when a lane is missing, already live in another tmux session, bound to another workstation, or fails a name-guard preflight?
- Should `lset` create missing lanes, or only assemble already registered ones?

## Relationships

- [Workspace topology](lane-set-workspace-topology.md) gives each selected lane its own tmux window.
- [Profile and Codex companion](lane-set-workspace-profile-and-codex.md) adds the distinction between starting and attaching under a requested profile.
- [Session assembly synthesis](lane-set-workspace-synthesis-session-assembly.md) describes the combined sequence and failure posture.
