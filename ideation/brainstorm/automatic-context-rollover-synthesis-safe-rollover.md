# Synthesis: Safe Automatic Context Rollover — Brainstorm

Status: brainstorm
Kind: architecture
Summary: A fresh context signal, completed-turn trigger, and semantic handoff transaction combine into a safe automatic `/ctx` at 65% by default.
Topics: automatic-context-rollover, context-signal, turn-boundary-trigger, semantic-handoff, synthesis
Repository context: openRepoTools Claude context observation, hooks, handoff, and lane lifecycle
Captured: 2026-09-15

## Possible feats

- **Opt-in automatic `/ctx`** — Roll a lane coordinator into a fresh session before compaction without interrupting active work or bypassing handoff guarantees.

## Members and their joints

Atomic members: [Session-Scoped Context Signal](automatic-context-rollover-context-signal.md), [Safe Completed-Turn Trigger](automatic-context-rollover-safe-turn-trigger.md), and [Semantic Handoff Before Restart](automatic-context-rollover-semantic-handoff.md).

```text
status-line snapshot -> completed-turn admission -> latched request
                                                    |
                                                    v
                                      semantic /ctx handoff
                                                    |
                                                    v
                                  guarded swap -> fresh session
```

### Observation becomes policy only at a safe boundary

The session snapshot says how full the context is, not whether a restart is safe. The completed-turn trigger adds freshness, opt-in policy, lane ownership, and lifecycle admission. This separation prevents a metric publisher from becoming a process controller.

### A request becomes a rollover only through the handoff transaction

The latch prevents duplicate requests, but it does not authorize pane replacement. Claude must produce the semantic handoff, and the lane controller must acquire the current generation before changing state. Only that sequence turns threshold observation into a completed rollover.

### Failure flows back to a live operator surface

Every uncertain condition stops before respawn. A stale metric, ambiguous lane, hook incompatibility, handoff failure, or generation conflict leaves the current session alive and explains why manual action is required.

## Emergent behavior

Together these mechanisms can clear context proactively while retaining lane identity, unfinished intent, writer ownership, and crash evidence. None can do that alone: the signal lacks authority, the hook lacks semantic state, and the backend lacks Claude's current reasoning.

## Tensions to hold

- Earlier thresholds leave more recovery headroom but cause more frequent session churn.
- A fully automatic experience competes with operator predictability, so enablement must remain explicit and visible.
- Hook portability may require a warning-only fallback on older Claude versions.

## Recombination opportunities

The same boundary and latch model could later support policy-driven profile rotation or usage-limit handoffs, but those use profile-scoped signals and should not be folded into context rollover without separate governance.

## Open questions

- Should automatic context rollover be globally enabled, lane-scoped, or support both with explicit precedence?
- How should telemetry distinguish requested, started, completed, refused, and failed rollovers?
