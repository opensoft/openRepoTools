## Why

Account swaps currently invoke the model-driven handoff workflow, adding latency and consuming quota when a session may already be exhausted. The user requests separate `swap`, `ctx`, and `handoff` operations, with an externally controlled Claude account swap delivered first and native session resume used wherever the complete participant graph can be restored.

## What Changes

- **BREAKING**: Separate the three operation contracts. `swap` changes account and resumes existing conversations; `ctx` starts fresh coordinator context from a semantic checkpoint; `handoff` transfers work and understanding without an implicit profile change or restart.
- Add a model-independent terminal/control surface for Claude swap. Proposed syntax: `lane swap <lane> --profile <profile>`. When the old account can still process a turn, `/swap` submits the same request to a lane service; the command starts that service and waits for readiness if it is not running. The external command or a hotkey remains available when the old account has no quota; a prompt-backed `/swap` does not itself have a zero-model-request invocation guarantee.
- Use one persistent lanes service to watch registered bindings and own both `swap` and `ctx` transactions. For each managed lane it starts or reconnects to an execution-group supervisor that launches Claude, admits external shell/edit jobs, and survives replacement of the Claude process. The service verifies the bound host/container/window/pane, coordinates a durable stop, and directs the supervisor to launch the replacement with the selected conversation and profile semantics. Tmux remains the interaction surface, not a lifecycle authority; source-account processes remain on that account until stopped.
- Add opt-in automatic swap at 95% of the source account's five-hour usage window (5% remaining), using a fresh Claude status-line usage sample to submit the same operation to the lane service. A rate-limit `StopFailure` is a last-resort trigger. Automatic swaps require a previously configured, authorized target profile; a missing or stale reading or missing target cannot silently select an account.
- Replace swap's generated handoff requirement with native transcript persistence and a small durable operation record. Keep dirty/unpushed work in place; no forced commits, pushes, resets, or worktree reconstruction.
- Require verification of account identity, transcript continuity, participant restoration, and exclusive writer ownership before reporting success. Unsupported Claude worker kinds refuse the fast path before planned termination.
- Establish a Claude compatibility gate before choosing an API/frontend integration: native subagent history, native team restoration, task cancellation, and independent session control are distinct capabilities.
- Defer Codex implementation, open-ended unattended profile rotation, live credential replacement, and cross-machine/cross-agent moves. The runtime boundary permits a later Codex adapter.

## Capabilities

### New Capabilities

- `lane-session-operations`: Distinct swap, ctx, and handoff semantics, invocation guarantees, and migration behavior.
- `claude-account-swap`: External participant quiescence, durable account-switch intent, exact native resume, readiness, and recovery for supported Claude configurations.

### Modified Capabilities

None in the current canonical OpenSpec inventory. Shipped behavior is governed by the lane collision protocol and manual. Existing in-flight recovery and context-restart changes require integration decisions rather than silently edited delta specs.

## Impact

openRepoTools owns the command contracts, lane lifecycle, registry/log integration, machine operation records, status, and supervisor. Likely affected surfaces include `lane`, `lane-start`, `lane-handoff`, `lanes-edit.sh`, installed commands/skills, and the lane manual. workBenches continues to own profile selection, authentication, storage families, and launcher integration; any change there needs its own repository review.

The proposed persistent lane service is separate from Claude Code's background-session host and from the existing `/ctx` pane supervisor. The latter supervises one restart and is not a machine-wide service; swap must coordinate with its lifecycle records and lock before adding this service.

This proposal deliberately changes Amendment 17's one-act alias interpretation. It requires an explicit protocol amendment/migration decision before release; creating these files is not ratification. Existing records remain readable and are never rewritten to imply a completed fast swap.

[PR #121](https://github.com/opensoft/openRepoTools/pull/121) already owns supervised `/ctx` implementation. This proposal adds a separate account-swap preservation mode and reuses agreed lifecycle/restart mechanics rather than taking over that work. It also integrates with [lane worktree recovery](../add-crash-consistent-lane-worktree-recovery/proposal.md) and [automatic context rollover](../add-automatic-context-rollover/proposal.md).

Captured reasoning and evidence: [Lane Session Operations brainstorm](../../../ideation/brainstorm/lane-session-operations-overview.md). Scope is proposal documentation only; Claude comes first. Implementation will be handed to exactly one Speckit feature after the compatibility and governance decisions, with executable tasks owned there.
