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
| [Claude subagent persistence](https://code.claude.com/docs/en/sub-agents#resume-subagents) | Ordinary subagent transcripts can persist across parent session restart; stop semantics affect subsequent resume | Automatic restart of every child without model involvement |
| [Claude team limitations](https://code.claude.com/docs/en/agent-teams#limitations) | In-process teammates are not restored by native session resume | That a coordinator-only successful resume restored the team |
| [Codex app-server](https://developers.openai.com/codex/app-server) | A later adapter can investigate explicit interrupt, thread, and auth APIs | A tested Codex account-swap transaction or first-release scope |

The prior read-only inspection reported Claude Code `2.1.270` and Codex CLI `0.154.0`. These identify observations, not a compatibility promise. Documentation was retrieved during the 2026-09-16 investigation. Native histories may contain more than one physical file or index; the adapter must identify all state its tested version requires.

## Proposed delivery gates

1. Measure Claude stop, persistence, exact resume, target-account selection, and child restoration on disposable sessions. Record unsupported kinds explicitly.
2. Define a managed-launch/control surface and implement the external transaction using fake runtimes for deterministic failure coverage.
3. Demonstrate the supported full coordinator/worker graph under a different authenticated profile, with zero model requests made for swap preparation or recovery.
4. Migrate command meanings and protocol guidance together. Add Codex only as a separately verified follow-on.

An idle coordinator-only prototype can establish plumbing, but cannot close the full worker-restoration acceptance gate. Real model calls used to create test work or continue after resume are separate from the requirement of no model calls to prepare the swap.

## Integration evidence

Read-only sibling inspection found [PR #121](https://github.com/opensoft/openRepoTools/pull/121), the supervised `/ctx` implementation, open during this session. That work remains owned by its existing lane. This packet proposes an account-swap contract beside it and does not claim or rewrite its implementation. The [existing recovery proposal](../../openspec/changes/add-crash-consistent-lane-worktree-recovery/proposal.md) and [restart proposal](../../openspec/changes/add-supervised-context-restart/proposal.md) remain historical inputs whose assumptions need explicit reconciliation.

## Open questions

- Which Claude worker kinds pass the no-model-call restore gate?
- What minimal workBenches launcher change is needed for direct supervised resume without a picker or attach fallback?
- What measured deadline should govern interruption before reporting that a swap could not finish?

## Relationships

- [Worker restoration](lane-session-operations-worker-restoration.md)
- [Claude-first synthesis](lane-session-operations-synthesis-claude-first.md)
