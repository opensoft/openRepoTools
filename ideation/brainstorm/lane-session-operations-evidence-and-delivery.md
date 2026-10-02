# Claude-First Evidence and Delivery Gates — Brainstorm

Status: brainstorm
Kind: reference
Summary: Deliver the account-swap design against measured Claude capabilities first and retain Codex as a later adapter.
Topics: lane-session-operations, claude-compatibility, profile-switch, verification
Repository context: openRepoTools proposal evidence with workBenches launcher dependencies
Captured: 2026-09-16

## Possible feats

- **Versioned capability report** — Publish which coordinator, subagent, team, and tool modes actually support a no-handoff swap on each tested Claude version.

## User direction

On 2026-09-16 the user requested separate swap, ctx, and handoff operations, with Claude delivered first, and a proposal as the next step. The earlier suggestion to begin with Codex is not the selected sequence. This is a documentation/proposal stage; no runtime implementation or account switch has been performed.

## Evidence register

| Evidence | What it supports | What it does not establish |
| --- | --- | --- |
| [Shipped swap alias](../../commands/swap.md) and [handoff skill](../../skills/handoff/SKILL.md) | Current swap uses the semantic handoff workflow | That the requested split is already implemented or ratified |
| [Claude profile setup](../../../workBenches/scripts/setup-claude-profiles.sh) | Profiles in one family share projects, tasks, history, and related storage while credentials are isolated | Complete live child restoration across account changes |
| [Claude SDK controls](https://code.claude.com/docs/en/agent-sdk/python) | External interruption and task stopping, with final messages to drain | Generic attachment to an arbitrary interactive CLI, or a reversible whole-tree pause |
| [Claude background sessions](https://code.claude.com/docs/en/agent-view) | `--bg` starts a background session, `claude attach <id>` opens it in a terminal, and `claude agents --json` exposes session state; `--bg --resume <id>` can attempt to continue a saved conversation | That tmux detachment changes account, that a resumed session keeps its exact ID rather than becoming a copy, or that unfinished workers are restored |
| [Profile-only `pclaude` entry point](../../../workBenches/base-image/files/pclaude) | A bare `pclaude <profile>` passes `--no-lane`; an explicit `--lane` requests lane resolution | That the existing `/swap` skill's printed bare restart command automatically restores its lane |
| [Claude status-line data](https://code.claude.com/docs/en/statusline) and [workBenches publisher](../../../workBenches/base-image/files/claude-statusline-command.sh) | Claude provides account-scoped `rate_limits.five_hour.used_percentage` after an API response; workBenches publishes a profile-keyed snapshot | A native threshold hook or guaranteed updates while detached/idle |
| [Claude hook events](https://code.claude.com/docs/en/hooks) and [workBenches usage guard](../../../workBenches/base-image/files/claude-usage-guard.sh) | `StopFailure` distinguishes `rate_limit`; the existing `UserPromptSubmit` guard reads fresh samples and injects a 95% model-directed automatic `/handoff` instruction | That the existing guard itself starts an external service, or that a next prompt arrives before exhaustion |
| [Claude subagent persistence](https://code.claude.com/docs/en/sub-agents#resume-subagents) | Ordinary subagent transcripts can persist across parent session restart; stop semantics affect subsequent resume | Automatic restart of every child without model involvement |
| [Claude team limitations](https://code.claude.com/docs/en/agent-teams#limitations) | In-process teammates are not restored by native session resume | That a coordinator-only successful resume restored the team |
| [Codex app-server](https://developers.openai.com/codex/app-server) | A later adapter can investigate explicit interrupt, thread, and auth APIs | A tested Codex account-swap transaction or first-release scope |

The 2026-09-16 read-only inspection reported Claude Code `2.1.270` and Codex CLI `0.154.0`. A later read-only inspection on 2026-09-28 found Claude Code `2.1.284` with `--bg` and `claude attach` in its local help, and the installed `pclaude` wrapper matching the profile-only entry point above. These identify observations, not a compatibility promise. Native histories may contain more than one physical file or index; the adapter must identify all state its tested version requires.

On 2026-09-28, the official hook list had no configurable percent-remaining event. The status-line input did expose five-hour and seven-day percentages, and the hook reference documented `StopFailure` on API rate-limit errors. The installed guard's 95% automatic directive runs only at `UserPromptSubmit` and asks Claude to perform the old handoff workflow; it does not invoke a controller. The proposed automatic swap instead sends a fresh five-hour threshold event directly to the persistent lane service and uses `StopFailure` as a late fallback. Its target profile must be configured ahead of time. The first policy does not act on the weekly bucket, matching the existing guard's separate weekly warning.

The lane register/log has a host/container/window binding where recorded, so a service can enumerate registered lanes and inspect the pane on a reachable tmux server. The pane is not the authoritative usage source: workBenches' `rate_segment` rounds raw percentages to a displayed integer, while the same status-line command writes the unrounded five-hour value to a profile-keyed JSON snapshot. A displayed `95%` could therefore be a raw value below 95%, and pane text has no sample timestamp. Monitoring another host or an inaccessible container needs a monitor there or a verified relay; registry metadata alone does not expose its live pane.

## Proposed delivery gates

1. Measure Claude background-session stop, persistence, exact resume without a copied ID, target-account selection, tmux attachment, and child restoration on disposable sessions. Include a `/swap`-started controller that survives old-session shutdown. Record unsupported kinds explicitly.
2. Define a managed-launch/control surface and implement the external transaction using fake runtimes for deterministic failure coverage.
3. Demonstrate the supported full coordinator/worker graph under a different authenticated profile, with zero model requests made for swap preparation or recovery.
4. Migrate command meanings and protocol guidance together. Add Codex only as a separately verified follow-on.

An idle coordinator-only prototype can establish plumbing, but cannot close the full worker-restoration acceptance gate. Real model calls used to create test work or continue after resume are separate from the requirement of no model calls to prepare the swap.

## Integration evidence

Read-only sibling inspection found [PR #121](https://github.com/opensoft/openRepoTools/pull/121), the supervised `/ctx` implementation, open during this session. That work remains owned by its existing lane. This packet proposes an account-swap contract beside it and does not claim or rewrite its implementation. The [existing recovery proposal](../../openspec/changes/add-crash-consistent-lane-worktree-recovery/proposal.md) and [restart proposal](../../openspec/changes/add-supervised-context-restart/proposal.md) remain historical inputs whose assumptions need explicit reconciliation.

## Open questions

- Which Claude worker kinds pass the no-model-call restore gate?
- What workBenches launcher change is needed to start and resume Claude background sessions under the selected profile, then run the matching `claude attach <id>` client in the lane's tmux pane?
- What measured deadline should govern interruption before reporting that a swap could not finish?
- Does the status-line publisher run and deliver fresh usage while the managed background session is detached or waiting on children? If not, which supported local usage source can the lane service observe without requesting a model response?

## Relationships

- [Worker restoration](lane-session-operations-worker-restoration.md)
- [Claude-first synthesis](lane-session-operations-synthesis-claude-first.md)
