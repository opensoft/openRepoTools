# Internal native stop transaction

This implements part of T002/T014 within the approved native architecture.
It does not enable swap or add a public command. Gate 0 and native restore
remain unverified. Architecture review: Astra; orchestration: Sol High;
implementation: Luna Max in the active Codex environment.

## Authority and ordering

Only the existing coordinator runner may report a stop intent over its
authenticated internal bridge. The adapter validates participant, coordinator
session and runner incarnation against its connection before invoking the
daemon callback. The daemon routes to the real controller; there is no
state-only fallback or public native-stop socket route.

The runner resolves the target from its live native ledger. It must have an
actual observed agent ID, task ID, launch tool, current invocation and child
incarnation. An agent ID never substitutes for a missing task ID. The bounded
observation retains the actual start/task-event provenance, watermarks and
tool/effect observations; missing facts are not supplied as empty arrays.

Within one durable transaction, the controller validates owner generation,
lineage, current coordinator runner, existing admission, immutable definition
digest and workspace claim. It persists the observation, canonical content
digest, target-run exclusion key and `may_have_been_sent: true` before returning
one send authorization. No controller/store lock spans a runtime await.

The runtime target is revalidated after the persistence acknowledgement and
before calling `client.stop_task(actual_task_id)` on the coordinator's existing
connection. Admission/restart of that target must be excluded while stop is
unresolved: revalidation alone cannot make a task-ID-only SDK operation
incarnation-specific. If exclusion cannot be established, refuse the send.

The IPC acknowledgement reader remains independent of the control consumer
waiting for persistence. Stop/evidence callbacks remain available after
fencing; they must not inherit admission's released-and-unfenced condition.

## Scope boundary

This contract is one task-specific native stop. Its target key identifies one
observed child incarnation and its SDK effect is the documented
`stop_task(actual_task_id)` operation. It does not represent a coordinator-wide
interrupt and it must not be repeated once to emulate one.

The coordinator-wide operation has its own [durable interrupt and drain
contract](coordinator-interrupt.md), `coordinator_interrupts` records, sealed
complete roster, and one coordinator-level interrupt authorization. That
operation may interrupt while children are still active; parent shutdown
still waits for proven child, tool, effect, and parent-turn graph quiescence,
with process-tree exclusion as a separate post-shutdown gate. It
does not change this task-specific record, add per-child stop receipts, or
assume that the runtime interrupt is a persistent inference fence.

## Durable records and retries

`native_stops[stop_id]` retains the sanitized intent, its digest, target-run
identity, `may_have_been_sent`, `authorization_count`, separate `runtime_ack`
and `terminal_evidence`, and bounded evidence-ID/digest/result deduplication.
The target key includes owner/lineage, runner incarnation, invocation,
agent/task, launch tool and child incarnation; changing only the stop ID does
not permit a second send.

The first successful persistence returns `recorded: true` and
`authorize_send: true`. Exact duplicates, including after process restart,
return `authorize_send: false` without changing the record. Reusing a stop or
evidence ID with different content refuses. A crash or lost acknowledgement
can leave uncertainty even if no SDK call occurred; automatic resend is never
the recovery action.

SDK receipt and correlated terminal evidence are persisted independently in
either arrival order. Terminal watermarks must follow the stop observation
and match its current task/launch/incarnation. An SDK receipt can retain the
intent watermark; it does not fabricate a lifecycle advance. Conflicting
terminal evidence cannot overwrite an earlier fact.

The bounded terminal form requires an observed `task_notification` with
`status: stopped`. Progress updates and other terminal status names do not
become this evidence by renaming them. A persistence refusal cannot count as
a durable acknowledgement. Exact transport retries reach durable deduplication
without replaying a cached positive send authorization or terminating other
pending transactions.

Fencing blocks new child admissions and parent invocations while retaining
the ability to stop other already observed children. Stop-transaction state
is separate from task progress: a current nonterminal update does not erase
the pending stop, while lifecycle uncertainty invalidates send eligibility.

## Separate conclusions

- **Accepted stop:** the SDK acknowledged a request. The actual selected CLI
  also acknowledges a nonexistent task, so this is not terminal evidence.
- **Task termination:** a current, correlated native terminal event was
  observed. Preserve it even while tools or effects remain unresolved.
- **Tool/effect quiescence:** separate current evidence accounts for active
  tools, descendants and possible effects. A task notification cannot supply it.
- **Restore-state clearing:** remains unknown until supported runtime
  operations and observations establish it. Neither receipt, terminal event,
  parent exit nor silence certifies this boundary.

No stop observation releases a claim, enables model dispatch, marks the whole
lineage quiescent, or grants held-restore capability. Tests use synthetic
runtime events and private temporary stores; their results establish only the
internal transaction and recovery contract.
