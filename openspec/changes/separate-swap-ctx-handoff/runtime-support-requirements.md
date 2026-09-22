# Runtime support required for lane swap

Status: requirements prepared for upstream discussion; not submitted upstream.
Decision, September 22: the user chose **keep the guarantees and leave
activation blocked until supported**. This decision does not ratify the
separate protocol migration or sibling integration proposals.

Implementation remains in Speckit feature `001-separate-swap-ctx-handoff`.
Its task list owns implementation; this document defines the missing runtime
boundary. No runtime fork, undocumented control, transcript edit, or weaker
acceptance rule is proposed.

## Required outcome

A controller outside the model must stop a coordinator and its native Agent/
Task lineage, account for outstanding work and effects, and load the exact
coordinator conversation under an authorized compatible account. Control entry
through target hold makes zero new model requests. The target stays held until
an explicit, uniquely authorized release. Native children remain native;
supported exact continuation or a new native restart happens only after release.

Conversation preservation alone is insufficient: the controller also needs to
know whether old workers can still write, whether pending runtime work can wake
after restore, and whether inference occurred during the control interval.

## Five independent runtime obligations

These are semantic requirements, not names of existing APIs or emitted events.
An upstream implementation may use other names or documented equivalent APIs.

| Boundary | Required supported behavior/evidence |
| --- | --- |
| Control entry and admission fence | Establish an observable epoch before preflight. Fence coordinator queries, native child/tool admission, pending continuations, and racing spawns, with a sealed complete roster or explicit uncertainty. |
| Run drain | Correlate interrupt acceptance separately from completion of every current child, tool, pending admission, parent continuation, and tracked effect. Report unresolved detached work and uncertain outcomes; an empty task list is insufficient. |
| Durable worker/orphan state | Identify a committed persistence revision at which stopped workers cannot autonomously resume or enqueue restart work during restore. Preserve task and transcript history for later authorized continuation/restart. |
| Exact held load | Confirm the exact coordinator UUID and persisted conversation revision are loaded under the selected account/configuration; report orphan reconciliation and enforce a hold covering coordinator and native children until explicit release. |
| Complete request observation | Cover every parent, child, retry, continuation, and orphan model-request attempt through the actual release boundary, including failed/cancelled attempts. Provide an ordered count with detectable gaps; a lost observation or crash ambiguity must remain unknown. |

The observations themselves must not initiate model requests. A supported
hold/fence must prevent work, rather than merely delay a caller's next prompt.
Runtime control must remain available when the source account cannot make
another inference request.

## Identity, durability, and recovery

- Publish the capability schema, supported participant kinds and launch modes,
  runtime/version/configuration identity, and explicit refusal behavior.
- Bind evidence to runtime incarnation, native coordinator/session/invocation,
  child agent/task/parent identities, immutable definitions/permissions,
  monotonic event sequence, persistence revision, and control epoch. The adapter
  joins those values to its durable lane operation/generation and release ID.
- Distinguish acceptance from completion and model transport acceptance from
  child delivery. Expose authoritative readback for interrupted observations.
- Preserve uncertainty across controller/runtime crashes, lost replies, reused
  task IDs, and account transitions. Reconciliation must not require reissuing
  an interrupt, model query, release, or uncertain external effect.
- For context rollover, support a distinct source entry-to-drain proof before
  shutdown and a fresh held-coordinator receipt. Exact swap evidence must not
  be reinterpreted as a fresh-context or cross-parent child-restore receipt.

Process exclusion and external-effect reconciliation remain separately required
controller responsibilities. Runtime receipts cannot authorize deleting claims
or replaying effects whose outcome is unknown.

## Acceptance evidence requested

Use the same pinned supported runtime and public controller path for each case:

| Case | Required result |
| --- | --- |
| Settled and busy parent with active native children/tools | Complete correlated roster and drain, durable worker-state revision, exact target held receipt, zero new control-phase requests. |
| Multiple/nested children and a racing spawn | Every admission is rejected by the fence or included in the sealed roster; no untracked writer. |
| Unfinished source restored after a crash | Positive orphan handling is observable; supported clearing and target hold prevent unauthorized wake/inference. |
| Interrupted control or lost reply at each boundary | Durable readback identifies the same operation/evidence; uncertainty remains visible and no uncertain action is replayed. |
| Explicit release and retries | One matching release crosses the hold; completed work stays complete and native continuation/restart has correlated identity evidence. |
| Wrong account, missing history, stale identity, unsupported worker, or observation gap | Visible refusal with preserved state/claims and no competing runtime execution. |

The positive-orphan control must distinguish persisted-record load, notification
enqueue, wake, and a model-dispatch attempt. The terminal-cleared held-target
case independently requires no restored orphan, enqueue, wake, or new request;
silence in a control that never exercised orphan restoration proves none of
those boundaries.

Release must provide a synchronous, correlated gate event and watermark that
closes the same uninterrupted observation epoch. A release acknowledgement
without that final proof leaves uncertainty and forbids replay or subsequent
pumping; recovery must not synthesize a successful boundary after the fact.

Disposable authenticated account validation follows only once these supported
interfaces are identified and the test accounts, lane, effects, and environment
are selected. Scripted/fake tests establish controller mechanics only.

## Current evidence and bounded leads

The inspected pin is Python SDK `0.2.153`, bundled CLI `2.1.273`, SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
The [feature evidence](../../../specs/001-separate-swap-ctx-handoff/live-validation.md)
records the independent missing authorities and historical probe limitations.

The documented `interrupt_receipt_v1` and `interrupt_cancel_queued_v1`
capabilities are a bounded investigation lead: they describe main-thread queued
messages and exclude subagent messages. Their documented minimum versions
precede the selected CLI, but selected-mode advertisement/behavior is not yet
verified. An empty receipt cannot establish whole-run drain or durable orphan
clearing. Queue cancellation also needs a separately agreed policy.

References for upstream discussion:
[Python API](https://code.claude.com/docs/en/agent-sdk/python#methods),
[interrupt response](https://code.claude.com/docs/en/agent-sdk/typescript#sdkcontrolinterruptresponse),
[session storage](https://code.claude.com/docs/en/agent-sdk/session-storage),
[telemetry limits](https://code.claude.com/docs/en/agent-sdk/observability#flush-telemetry-from-short-lived-calls).
Current documentation is discovery material, not certification of the pin.

The requested upstream response is a documented mapping for all five
obligations, with supported versions/modes and executable acceptance evidence,
or an explicit statement of the missing runtime work. A partial mapping remains
insufficient to activate production swap under the preserved guarantees.
