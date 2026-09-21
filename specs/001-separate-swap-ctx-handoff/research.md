# Research: Native Lineage Lane Operations

## Decision: one top-level coordinator, native children

Keep Claude's native Agent/Task workflow. The managed boundary owns one exact
top-level SDK process/session/account; native children remain in that runtime's
execution lineage. A child is represented by observed native identity and
events, not by an independently logged-in SDK session. This follows the
approved native-subagent decision and preserves the user's architecture.

**Alternatives considered**: independent top-level workers (the current
prototype), coordinator-only recovery, and a model-written handoff. The first
changes the requested architecture; the others either lose native lineage or
add an unrequested handoff artifact. They remain historical/rewrite targets,
not acceptance evidence.

## Decision: ledger native identity and lifetime separately

Record `agent_id`, `task_id`, native `type`, `tool_use_id`, parent links,
transcript reference, status, stop provenance, model, effort, immutable custom
definition/policy, and restart correlation. Track child lifetime independently
from the Agent launch tool: a launch call may complete while a background Agent
continues. Use runtime lifecycle events to establish active, stopped, held, or
completed state. The runtime's `SubagentStart`/`SubagentStop` events do not
reliably carry task, tool, or parent IDs, so join them to a durable pending
Agent admission and task-event/history watermark. An ambiguous join is unknown;
a parent process exit or a background flag alone is not proof of quiescence.

**Rationale**: these are the runtime facts needed to distinguish an exact
continuation from an assisted restart and to retain uncertainty about tools or
effects. Child records must not grow top-level UUID, PGID, open, shutdown, or
release controls.

## Decision: exact restore has a pinned capability gate

The account-control phase fences admissions, tools, mail, and inference before
stopping work. A separately authorized coordinator-wide interrupt may initiate
native child stopping; native child/tool/effect drain and required supported
worker-state clearing precede parent shutdown and OS exclusion. It then may
restore the coordinator only through the official exact top-level session
loader on the actual selected CLI/transport path, with promptless
initialization and validated account, permission, model, transcript, workspace,
and runtime evidence. Record the selected path, runtime version, and
executable/config digest. Parent exact restore is mandatory; failure refuses.
Native child exact resume is preferred, but only after `release` and only when
the pinned runtime documents and demonstrates the child identity, stop, and
resume sequence. Before release, record only `resume-pending` eligibility (or
`restart-pending` when exact continuation is unavailable).

The gate must also demonstrate that retained parent/child state cannot
auto-resume or infer during startup. Stream-json force-print is not proof:
`print.ts` can derive restored orphans from `running_background_tasks` and wake
the session, while its classifier is called without a callback. Before source
exit, require terminal native-child stop and a durable clear of current
worker-state; the target stream-json connection must show no restored orphans,
wake events, or model request. If the runtime dispatches children from
initialization and offers no supported hold, the configuration is unsupported;
promptless parent startup by itself is insufficient evidence. No classifier
callback/state is fabricated or persisted.

## Decision: coordinator interrupt has separate whole-roster authority

The source cancellation candidate is now governed by
[coordinator-interrupt.md](contracts/coordinator-interrupt.md) and the
[OpenSpec decision](../../openspec/changes/separate-swap-ctx-handoff/coordinator-interrupt-decision.md).
Task-specific stop produced a new request in Stage 1; coordinator interrupt
did not in the settled single-child scripted fixture. The selected candidate
therefore needs a distinct durable whole-roster authorization and independent
drain. The experiment did not validate the continuous interval from control
entry before preflight, busy/multiple-child modes or actual accounts. Neither
the interrupt receipt nor external tool/query gating provides a persistent
inference fence. The capability gate remains open.

## Decision: post-release assisted restart is explicit and observable

When child exact resume is unavailable, preserve the child ledger as
`restart-pending`. After account readiness and explicit `release`, the fresh or
restored coordinator may send an ordinary native restart instruction using the
durable IDs/statuses and its context. No semantic handoff or written document
is generated. An accepted parent send is only an instruction acknowledgement;
success requires correlated new native Agent/Task lifecycle events and a
restart correlation record. `agent_id` reuse requires the current task ID,
parent invocation, and an event watermark; a stale marker cannot correlate a
restart. Missing or ambiguous correlation remains unresolved and cannot be
automatically resent.

The control phase performs zero new model requests. Assisted restart requests
and their model usage are reported separately after release.

## Decision: background Agents are tracked; detached work is unsafe

Runtime-owned background Agents with task IDs and lifecycle events use the same
native ledger and stop boundary. A completed launch tool does not close their
record. Unmanaged detached shells, unknown descendants, missing lifecycle/effect
events, and potentially completed external mutations require held/indeterminate
state and effect reconciliation; they are never silently replayed. Native
teams are a separate participant capability, not a child-ledger entry, and
remain unsupported until a separate runtime probe establishes membership and
restoration semantics.

## Decision: lineage claims and native policy are distinct

The coordinator execution lineage owns the workspace claim whenever any member
may write. Children in that workspace inherit ownership and do not compete
with the parent. A genuinely isolated child worktree receives its own exact
host/workspace-global claim, with realpath and ancestor/descendant exclusion
across lanes. Claims remain held while any writer or effect is unresolved.

A read-only coordinator does not make writable native children read-only. Each
child's actual native identity must resolve to its immutable tools, permissions,
model, effort, and custom-agent definition. Unknown identity or an adapter that
cannot enforce distinct policies is a refusal; parent policy is never broadened
to make the child work.

## Decision: `ctx`, `handoff`, and release remain separate

`ctx --hold` creates a fresh held coordinator context while retaining stopped
worker records; it does not promise children survive parent shutdown. A `ctx`
restart creates a new coordinator lineage from the caller's explicit
checkpoint, and only after that coordinator is released may it instruct native
worker restarts. This is not exact cross-parent child rebind and does not
generate a checkpoint as part of swap. `handoff` records an explicit checkpoint
only. `release` is the one visible boundary at which normal model use begins.

## Decision: durable state is versioned and fail-closed

Retain the existing same-store location under the workspace Git common
directory, owner-only permissions, atomic writes/fsync, append-only journal,
request-content deduplication, and crash reconciliation. Add a schema version
and native-lineage record kind. Missing, unknown, or obsolete independent-worker
state is refused with an operator-visible migration/restart requirement; it is
not guessed into a native graph. State contains references and evidence, never
credentials or conversation bodies.

## Evidence and unresolved questions

An isolated no-auth probe on 2026-09-16 observed official Python SDK 0.2.153
`connect(None)` promptless initialization and an idle control response. The SDK's
bundled-first CLI resolver selected bundled CLI 2.1.273 (measured digest prefix
`6c752e2c`), rather than the separately installed CLI 2.1.270 (prefix
`3a624a`). A missing exact top-level resume UUID failed before successful
initialization. The response did not echo session UUID or selected model, and
the unauthenticated account object did not prove an email. These observations
justify strict prevalidated transcript/account checks, but are loader-shape
evidence only; they do not select or validate the stream-json non-auto path.

The pinned runtime gate is still unresolved: no live validation proves the
selected CLI/transport path's no-auto startup behavior, cross-account parent
restore, native child stop/resume, background lifecycle events, team behavior,
or that startup cannot auto-resume/infer before release. The interactive
takeover path can auto-resume native orphans before a prompt and is a known
refusal boundary, not evidence for the non-auto path. Gate 0 must publish the
selected path, exact runtime version, executable/config digest, source terminal
stop and durable worker-state-clear evidence, and a target no-auth orphan
fixture trace showing no restored orphan, wake, or model request. It must also
publish participant kinds, event traces, account/permission evidence, and
unsupported cases before claiming production support. See the approved decision
for the inspected SDK references:
[SDK subagents](https://code.claude.com/docs/en/agent-sdk/subagents#resume-subagents)
and [native subagent resume](https://code.claude.com/docs/en/subagents#resume-subagents).
