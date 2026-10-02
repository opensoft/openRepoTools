# Synthesis: Claude-First Account Continuity — Brainstorm

Status: brainstorm
Kind: architecture
Summary: Combine separate command meanings, external control, and verified worker restoration into a Claude-first account-swap transaction.
Topics: lane-session-operations, claude-compatibility, external-supervisor, worker-restoration, synthesis
Repository context: openRepoTools with workBenches and Claude runtime boundaries
Captured: 2026-09-16

## Possible feats

- **Account continuity without a generated handoff** — Carry the same lane and supported conversation graph across credentials while a controller retains exclusive ownership.

## Members and their joints

Atomic members: [command semantics](lane-session-operations-command-semantics.md), [external supervisor](lane-session-operations-external-supervisor.md), [worker restoration](lane-session-operations-worker-restoration.md), and [evidence and delivery](lane-session-operations-evidence-and-delivery.md).

### Identity and execution

The command contract says which identity may change: swap changes the profile/account, ctx changes coordinator context, and handoff changes the reader or owner. The supervisor encodes that intent before touching a process. An operation intended to resume must never consume an outstanding fresh-context intent.

### Continuous accounting and fast stopping

The worker roster makes interruption bounded by actual in-flight work rather than a model-written inventory. The stop acknowledgements seal that roster. Persistence and old-writer checks then authorize exact-ID replacement, not merely a successful shell exit.

```text
external request -> preflight -> stop admission -> interrupt and drain
                 -> persist machine record -> confirm old writers stopped
                 -> launch exact sessions under target account -> verify -> continue
```

### Authority and recovery

Use one lane lock/generation owner across swap, ctx, and handoff. Existing recovery and supervisor proposals supply reusable mechanics, but their requirement to generate a handoff for every swap must be narrowed explicitly. Profile credentials remain the launcher's responsibility. A retry consumes the same operation record and first checks whether a replacement is already alive.

## Emergent behavior

Quota exhaustion no longer requires another model response just to preserve work. An interrupted or failed replacement has a visible recovery path, while the worktree stays where it was. Native conversation history supplies continuity; the machine record supplies process accountability.

## Tensions to hold

Stopping immediately and preserving an arbitrary tool mid-write cannot both be guaranteed. Restorable ordinary subagents and non-restorable native teammates cannot be presented as equivalent. A model-backed slash command cannot simultaneously promise zero model dispatch. These are explicit capability boundaries, not implementation details to hide behind a success message.

## Recombination opportunities

The same controller may later support a Codex adapter. Context rollover may reuse its launch and readiness mechanics with a different preservation mode. Neither extension changes the selected first delivery: Claude account swaps on a verified participant set.

## Open questions

If native Claude children cannot be restored through supported external controls, should independently supervised workers become the product architecture? That decision follows measured evidence and would expand the orchestration contract.
