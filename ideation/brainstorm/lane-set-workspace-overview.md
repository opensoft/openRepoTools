# Lane Set Workspace Overview — Brainstorm

Status: brainstorm
Kind: reference
Summary: A proposed `lset` command would assemble several Claude lanes and one Codex chat into a tmux workspace while preserving one lane per named window.
Topics: lane-set-workspace, lane-management, tmux, session-binding
Repository context: openRepoTools command ownership with workBenches Claude and Codex profile launchers
Captured: 2026-09-29

## Possible feats

- **`lset` workspace command** — Open a repository's selected lanes as separate tmux windows alongside a Codex chat, using existing lane safety checks.

## Motivation

The user wants to enter a group of related lanes as one workspace instead of opening each manually. The discussion also clarified that tmux sessions group windows, windows group panes, and the present lane guard keys a lane to a **window name**, not to a pane or the enclosing tmux session. A recent attach to `openRepoTools-1` showed why this binding matters: the Claude conversation had the lane name but its tmux window was still `claude`, so the hook blocked prompts.

## Goals

- Present the chosen Claude lanes and a companion Codex chat together in one tmux session.
- Preserve one lane per named window and avoid duplicate Claude processes.
- Make actual lane state and profile visible, including refused or incomplete members.
- Keep the command and lane assembly logic in `openRepoTools` while reusing workBenches profile launchers.

## Non-goals

- Redesigning lane identity to place multiple lanes in panes of one window.
- Silently switching the profile of an already-live Claude process.
- Treating the Codex chat as a Claude lane or assuming a Claude profile selects a Codex login.
- Changing the lane collision protocol or claiming that `lset` is implemented or approved by this brainstorm.

## What the system delivers

The example `lset openxfactory team01a` expresses a desired workspace: five `openxfactory` lane windows and a sixth Codex window. The exact lane membership, whether five is fixed, the Codex profile, and repeat-invocation behavior remain proposal decisions. An assembled workspace would show which window carries each lane or companion process, without bypassing the existing attach/start/refusal rules.

## System model

```text
one tmux session: proposed openxfactory set
├── window openxfactory-1 → Claude lane pane
├── window openxfactory-2 → Claude lane pane
├── window openxfactory-3 → Claude lane pane
├── window openxfactory-4 → Claude lane pane
├── window openxfactory-5 → Claude lane pane
└── window codex          → Codex chat pane
```

The layout is an example, not a guarantee that positions 1–5 exist or are all eligible. Each lane window must agree with its Claude transcript and lane row. The set session groups them; its name is not itself a lane identity.

## Cluster map

- [Session assembly](lane-set-workspace-synthesis-session-assembly.md) — joins tmux layout, safe lane dispatch, and separate profile decisions into one proposed flow.

## How it fits

`openRepoTools` owns `lane`, `lanes`, `lane-start`, the lane manual, and command installation. A future `lset` belongs there. `workBenches` owns the profile launchers that such a command would invoke; this packet proposes no credential or launcher changes. The [lane session operations packet](lane-session-operations-overview.md) explores account continuity within lanes and is related but not a substitute for set assembly. This packet is non-normative and precedes the user's requested later proposal.

## Key decisions and open questions

The user chose one window per lane, plus a separate Codex window, and chose `openRepoTools` as the command's home. Still open: how members are selected; whether missing lanes are created; whether live windows move between sessions; how mixed Claude profiles are handled; which Codex profile is used; and what happens on partial failure or a repeat invocation.

## Document map

- [Synthesis: Lane Set Session Assembly](lane-set-workspace-synthesis-session-assembly.md)
  - [Workspace topology](lane-set-workspace-topology.md)
  - [Lane assembly](lane-set-workspace-lane-assembly.md)
  - [Profile and Codex companion](lane-set-workspace-profile-and-codex.md)
