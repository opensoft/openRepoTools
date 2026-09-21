# Coordinator-wide interrupt and drain

This is the contract for the governed, internal coordinator-wide interrupt
candidate. It does not expose a command, grant a runtime capability, or close
the selected-runtime Gate 0. The pinned SDK/CLI mode, initialization options,
transport, account/configuration, model, permissions, and custom-agent
definitions are part of the capability identity. A mode that cannot account
for the complete native roster or its effects is `unsupported` before a
disruptive effect.

This contract is separate from [the one-child native stop
transaction](native-stop.md). `coordinator_interrupts` is not a collection of
`native_stops`, and it does not issue one `stop_task` call per child.

## Internal persistence slice

The first implementation exposes trusted controller methods
`persist_coordinator_interrupt_intent(frame)` and
`persist_coordinator_interrupt_evidence(frame)`, authenticated daemon callbacks,
and separate `coordinator-interrupt-intent` / `coordinator-interrupt-evidence`
IPC request/acknowledgement namespaces. It records typed submitted observations;
it supplies no live roster producer, SDK interrupt dispatcher, public route,
runtime capability, or aggregate drain/readiness decision.

Authorization requires the existing native context to be durably fenced and
the intent to match the paused active operation and its complete, nonempty
sealed durable admission set. Coordinator-only interruption and pending or
unjoined admissions/tasks refuse in this slice. Known tool,
effect, and descendant inventories may remain unresolved; storing them does
not prove that the runtime has fenced or drained them. The broader runtime
fence and pending-admission reconciliation below remain required downstream.

Evidence uses eight closed kinds: `runtime-ack`, `member-terminal`,
`tool-terminal`, `effect-outcome`, `admission-closed`, `parent-drained`,
`request-observation`, and `process-excluded`. Each has bounded, typed fields
and correlated identities; arbitrary prompt, transcript, or credential bodies
are not accepted. Exact evidence retries preserve the stored bytes.

The only positive `authorize_send` is an ephemeral response after durable
persistence. The IPC receiver also consumes a positive reply at most once per
interrupt ID, so a delayed duplicate cannot authorize a later retry. The
durable record and source exclusion remain the authority across reloads.

## Fence and complete roster

### Live startup and send integration

Normal native startup fixes the coordinator's lineage identity, generation,
workspace claim, runner incarnation, and trusted definitions before opening
the held runner. A future parent invocation is not invented at startup. The
trusted supervisor binds the admission context to the actual durable mailbox
message ID before the first SDK query; hooks cannot admit a child before that
binding succeeds. Repeating the same binding is idempotent. A different
invocation requires explicit lifecycle reconciliation; it cannot erase an old
admission ledger.

The runner builds its interrupt roster from the actual native hook/event
ledger. A separate local fence blocks new managed queries, Agent/Task
admissions, and tool starts while event and persistence readers remain active.
An admission already awaiting persistence must recheck the fence after its
acknowledgement. Unknown or unjoined members refuse rather than disappear from
the sealed roster. Generic interrupt/cancel controls cannot bypass durable
authorization for a native-enabled runner.

After the one-time positive intent acknowledgement, a distinct authenticated
`coordinator-interrupt-validate` request checks the stored full intent digest
and current operation, source, fence, admissions, owner and claims. Its result
is eligibility only, carries no `authorize_send`, and cannot create or recover
an authorization. The runner then revalidates its local connection and sealed
roster, marks the attempt before awaiting the documented SDK interrupt, and
never retries it automatically. Hook and stream terminal facts are retained
independently of the runtime receipt, including facts buffered during intent
persistence.

The controller starts a stable request-observation epoch at external control
entry. A runner's first local receipt watermark is in its own event domain;
it is not inferred from wall time and does not prove observation of the prior
interval. The available SDK hooks do not expose all internal model attempts.
Their observations therefore retain `observable: false` and
`new_requests: null` unless a separately validated observer supplies complete
coverage. Blocking local query calls is not evidence of a runtime-wide
inference fence, and this integration grants no zero-request capability.

In this internal integration, `capability_digest` binds an immutable selected
reference; its presence is not proof that busy or multi-child interruption is
supported. The official runtime construction gate remains in force. Before
production activation, mode-specific capability admission must precede the
request epoch, fence, and disruptive SDK call. A verified held-start mode
alone cannot authorize a busy native interrupt mode.

The operation creates a monotonic source-control fence epoch before sealing a
roster. The fence blocks new parent inference, Agent/Task admissions, tool
starts, mailbox sends, and other work that could add a native member. The
runner acknowledges the same epoch and closes its pending admission queue;
event and persistence readers remain live while this occurs. The fence is an
admission/control boundary, not the later release token and not a claim that a
runtime interrupt is a persistent scheduler fence.

The sealed roster is the complete set visible at that epoch, including:

- the current coordinator and its current parent turn;
- every admitted native child, whether active, stopping, terminal, foreground,
  or background, with actual agent, task, parent, launch-tool, and incarnation
  identities;
- every accepted but not yet joined Agent/Task admission, including an
  admission whose task ID has not arrived; and
- every nested task, active tool, descendant, and tracked external effect
  linked to those members.

An agent ID cannot fill a missing task ID, and a guessed or reused ID cannot
join an admission. An unknown member, detached descendant, contradictory
parent/tool link, or unclosed admission makes the roster incomplete and the
operation held or unsupported. A naturally completed child remains completed;
it is not relabeled `stopped` merely because an interrupt is in progress.

The roster has an immutable identity and two different watermarks:

1. `roster_identity_digest` is a canonical digest of member identities,
   parent/launch links, definition digests, admission references, and tracked
   tool/effect/descendant inventory. The full intent digest additionally binds
   the source, operation, fence epoch, and request-observation epoch. Under the
   same store transaction, the controller validates the referenced durable
   admissions and current lineage/workspace claim authority. The roster digest
   alone is neither authorization nor proof of completeness.
2. `roster_seal_watermark` is the event/history watermark at seal time and
   never changes.
3. `progress_watermark` advances only by authoritative current-run events and
   never changes the identity digest or seal watermark.

The runner must confirm the identity digest and both watermarks before
authorization. A newly discovered member, changed incarnation, or post-seal
admission invalidates the pending authorization; it does not silently expand
the roster or authorize another interrupt.

## Durable intent and at-most-once authorization

`coordinator_interrupts[interrupt_id]` is a durable record keyed to the source
operation. It contains, without transcript bodies or credentials:

- `operation_id`, canonical lane, `owner_generation`, `lineage_id`,
  `lineage_generation`, coordinator `session_uuid`, and the authenticated
  `runner_incarnation`;
- `fence_epoch`, `roster_identity_digest`, sealed member references,
  `roster_seal_watermark`, `progress_watermark`, and the immutable
  runtime/configuration
  capability digest;
- a canonical request/content digest and an unresolved-source exclusion key
  covering the owner generation, lineage ID/generation, coordinator session,
  and runner incarnation; this source key remains exclusive even if a retry
  uses different request, operation, fence, or roster IDs;
- `may_have_been_sent`, `authorization_count`, `authorize_send`, and durable
  timestamps; and
- independent fact slots for `runtime_ack`, per-member terminal events,
  tool/effect outcomes, parent-turn drain, process exclusion, and the
  request-observation interval.

The first successful persistence sets `may_have_been_sent: true`, increments
`authorization_count` to exactly one, and returns the only positive
`authorize_send`. This is an at-most-one authorization, not a guarantee that
the SDK call executes exactly once. Persistence is acknowledged before the
SDK call and no store or controller lock spans a runtime await. Exact retries,
daemon takeover, runner restart, a lost acknowledgement, and a changed
request, operation, fence, or roster ID all return `authorize_send: false` or
refuse while the source exclusion is unresolved. Conflicting content,
  generation, lineage, session, or runner identity refuses the operation. An IPC reader
may replay the persisted record and its facts, but must never replay a cached
positive authorization as a new send instruction. No automatic resend is
permitted, even when the SDK call may not have reached the runtime.

After persistence, the adapter revalidates the same coordinator connection,
runner, fence epoch, and roster digest, together with the full intent and
current claim/admission authority. A mismatch records uncertainty and
does not create a second authorization. When the validation succeeds, the
sole authorized attempt is to send one documented coordinator `interrupt` on
that existing SDK connection. This is one coordinator action; it is not a
loop over child task IDs. The interrupt may be sent while children and tools
are still running.

## Independent drain evidence

The following are independent facts and may arrive in any order:

- SDK/runtime receipt of the coordinator interrupt;
- a current-run terminal event for every native child, including an
  authoritative matching terminal already present at seal time, with a
  natural completion retained as completion and a cancellation/stop event
  retaining its actual status;
- terminal evidence for each tracked tool and its invocation/parent links;
- outcome or explicit uncertainty for every tracked external effect and
  descendant process;
- a drained or positively idle parent turn, with no fabricated terminal result,
  and a closed pending-admission queue; and
- after supported parent shutdown, identity-revalidated exclusion of the
  owned process tree.

A receipt is not a child terminal, tool terminal, effect outcome, process
exclusion, or graph-quiescence proof. Parent exit and silence supply none of
those facts. Evidence must match the sealed member/incarnation and follow the
relevant event watermark; stale, ambiguous, or missing evidence leaves the
record `indeterminate`.

The roster reaches `quiescent` only when every native child is accounted for,
pending admissions are closed, every tool/effect/descendant is terminal or
authoritatively resolved, and the parent turn is drained or positively idle.
A coordinator-wide
interrupt may initiate child cancellation while the roster is active, but
parent shutdown follows this proven graph quiescence. The controller must not
close the parent immediately after sending the interrupt. Process exclusion is
then proven against the shut-down parent and its owned descendants as a
separate gate; a running or unknown process keeps the source held.

The request-observation epoch begins at account-control entry, before
preflight or fencing, and remains continuous through roster seal, interrupt,
drain, source exclusion, recovery, and any target held initialization until
explicit release; it is never reset at a phase boundary. Every new model request
attempt in that epoch is counted independently of control receipts. A positive
count, an unobservable interval, or ambiguous initiation timing blocks
success and retains claims; an empty quiet window is not a persistent
no-inference fence.
FR015 therefore remains a zero-new-model-request requirement, not an
assumption about what the interrupt guarantees.

## Observational drain projection

The next bounded implementation derives
`coordinator_interrupt_status(interrupt_id)` from the validated durable record.
The existing public `status` response includes the same projections in
`coordinator_interrupt_summaries`, keyed by interrupt ID, without replacing the
raw `coordinator_interrupts` evidence. This is a read-only view, not a new
interrupt command or lifecycle transition. It reloads under the store lock and
does not write state, append a journal, call a runtime, advance an operation,
change a claim, or issue/recover authorization. Invalid durable records still
refuse rather than becoming reassuring summaries.

The projection separates `runtime_acknowledged` from `graph_quiescent`, retains
source/seal/progress identities, and reports child, tool, effect, admission,
parent-turn, process-exclusion, and request-observation facts with blockers.
Graph quiescence requires every sealed member and inventoried boundary to be
accounted for. A matching terminal already present at seal may count; natural
completion and observed failure retain their actual terminal status. Missing
ACK does not erase a terminal fact, and ACK alone closes nothing. Contradictory
facts accepted by the durable validators remain blockers even when they have
different evidence IDs. Contradictions already invalid under those validators
(including conflicting member/tool terminals) continue to refuse reload;
the projection does not weaken that boundary. Unmapped
descendants remain unproven; a process-exclusion digest is not a replacement
for descendant evidence.
Matched parent `drained` and `idle` facts are compatible terminal observations,
not a contradiction merely because their labels differ.

Process exclusion and the continuous request-observation interval remain
separate from graph quiescence. Earlier positive or unobservable request
observations cannot be erased by a later zero count. Runner-local watermarks
do not establish coverage from external control entry. No projection grants
`safe_to_restore`, runtime support, release, or a successful account swap.
The durable schema and existing native lifecycle refusals remain unchanged.
An earlier unknown count remains explicit even if its observation says it is
observable; a later known count cannot repair missing historical coverage.
The view also identifies when request observations end before the latest
recorded progress watermark.

## Cancellation, recovery, and release boundary

Cancellation before intent persistence has no runtime effect. Cancellation
after `may_have_been_sent` is durable is an uncertain effect even if the
caller never receives a receipt. Recovery reads the durable intent, live
runtime events, request observations, tool/effect evidence, and process
identity before advancing. It may reconcile a receipt or complete the drain,
but it never replays the interrupt, releases a claim, launches the target
parent, or performs model-assisted repair from an uncertain record.

There is no release token in this contract. `quiescent` is evidence for a
separate operation and does not enable model dispatch, exact restore, account
change, or held-worker continuation. No claim is released while any roster,
effect, process, request interval, or runtime capability fact is unknown.
Support remains `unverified` until the selected runtime demonstrates these
facts in the requested mode; synthetic tests can validate the transaction and
deduplication rules but cannot grant production support.
