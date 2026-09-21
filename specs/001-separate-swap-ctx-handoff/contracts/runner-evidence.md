# Native Coordinator / Subagent Lineage Evidence Contract

This is the single evidence boundary between `ManagedController` and the
Claude runtime adapter. Test doubles implement this boundary, but a fake
runtime never establishes live native capability. The adapter may control one
coordinator runtime; native children are observed through that coordinator's
lineage and are not opened as independent top-level SDK sessions.

This contract supersedes the earlier independent-worker evidence shape. In
particular, a native child has no invented session UUID, runner instance, or
process-group identity. The child identity comes from the runtime's native
agent/task records and lifecycle events. A process tree and hook/tool evidence
can corroborate containment, but cannot manufacture a child identity.

## Authority and identity domains

The controller owns the durable lane generation, operation ID, external
request ID/content digest, sealed roster, lifecycle ledger, and release gate.
It rechecks the operation and generation after every runtime await before
applying a result. A mailbox message ID remains distinct from every control
request and native tool ID.

The coordinator is the only independently addressable runtime participant.
Its evidence MUST include all of the following before it is ready-held:

| Field | Required meaning |
| --- | --- |
| `session_id` | Exact native coordinator conversation/session identity used by the official loader. |
| `account` | Canonical selected profile and validated account identity, including expected email where the runtime supplies one. |
| `process` | The coordinator runner PID, start identity, containing process-group ownership, and current process-domain evidence. |
| `session_name` | The bounded native session name actually passed to the runtime and observed by the guard. |
| `bound_lane` | Canonical durable lane identity, not an inherited environment hint or caller-supplied owner claim. |
| `runner_instance_id` | Opaque coordinator process incarnation token; it changes when the coordinator runner is replaced. |
| `model` / `effort` | Configured values and the launch-definition fingerprint used for readiness. |
| `permission_mode` / `tools` | Actual effective permission mode and tool policy, not a nickname such as `read_only`. |

`session_name` and `bound_lane` are established before open/resume intent and
are preserved across an account swap. A duplicate or conflicting name in the
active roster refuses before launch. The prompt guard must compare the hook
session UUID and name with the durable coordinator/lineage record; environment
variables are lookup hints only.

Each native child record MUST carry the following evidence slots, keyed by the
runtime's native `agent_id`. Populate `task_id` only when an actual native
task event or authoritative native task record supplies it; preserve an absent
value as unknown rather than manufacturing one:

| Field | Required meaning |
| --- | --- |
| `agent_id` | Native child identity captured from `SubagentStart` or an equivalent authoritative runtime record. |
| `task_id` | Native task identity supplied by an actual task event/record for the child and its updates. It is not a made-up participant UUID or an inference from `SubagentStart`/`SubagentStop`. |
| `type` | Exact runtime kind from the native `agent_type`/task type, such as ordinary subagent, native background subagent, or team member. Teams are a separate capability class. |
| `tool_use_id` | The parent `Agent`/child-launch tool invocation joined from tool hooks, a task-start event, or session history when the runtime supplies one. It is not fabricated onto a `SubagentStart`/`SubagentStop` event. |
| `parent` | Direct parent linkage: containing coordinator `session_id` plus the direct parent `agent_id`/`task_id`/`parent_tool_use_id` when actual runtime metadata supplies it. Missing or contradictory linkage is unknown. |
| `transcript_record` | Validated native `transcript_path`/`agent_transcript_path` or task record reference and storage identity; never a copied conversation body. |
| `status` | Ledger status derived from lifecycle evidence, not from the last launch-tool result. |
| `stop_provenance` | Runtime-reported reason and actor for stopping, such as model stop, user cancel, SDK cancel, parent shutdown, failure, or process loss. |
| `model` / `effort` | The child configuration observed for this native run. |
| `custom_definition` | Immutable custom-agent definition identity/digest and definition metadata used by this run. |
| `permissions` / `tools` | Effective child hook/tool policy bound to this exact `agent_id`; parent policy is not substituted. |

The child record MUST NOT contain a per-child `session_id`, session UUID,
`runner_instance_id`, or `process_group_id`. A child can have an OS process
visible in the containing tree, but that observation is not a native child
identity and is not a second control handle.

`agent_id` is not guaranteed to be globally unique across native resumptions.
The ledger therefore binds each observation to a child-run incarnation made of
the captured actual `task_id` when supplied, direct parent
invocation/`tool_use_id`, and a monotonic runtime event watermark. The durable
record may keep this tuple as `lineage_incarnation`; it is correlation
evidence, not a child UUID. A stale completion notification for an earlier
watermark, even when it repeats the same `agent_id`, cannot terminate the
current child run. An absent actual task ID blocks exact continuation.

### Nested admission causal parent binding

The existing durable pending-`Agent` admission record has one optional causal
extension. It is absent for a top-level admission, preserving the old record
bytes, and is present and non-null exactly when `admission.parent.agent_id`
is non-null:

```text
parent_observation: {
  child_run_id: sha256,
  observation_id: str,
  observation_digest: sha256
}
```

This is a controller-derived join, not a caller assertion, SDK field, or new
RPC. The controller resolves it before the pre-allow admission ACK and keeps
the SDK's strict admission and ACK contract unchanged. The referenced
observation must be a committed observation from the same source context, with
the exact actual parent agent/incarnation, an active child and null
`terminal_outcome`, fully joined admission and start, and
`observation_watermark < admission.watermark` for the nested admission. A live
admission additionally requires the latest current parent to be active. A
reload or archived-source validation uses the latest parent state **as of** the
nested admission watermark; a later parent terminal event does not rewrite
that historical join.

The controller validates the causal chain in two passes: pure record shape and
digests first, then context/admission/observation joins. The bounded ancestor
chain must terminate at the coordinator. A self-link, cycle, ambiguous run,
missing join, stale/reused child incarnation, or wrong context refuses the
admission and preserves the pending record. An archived source is never
validated with current target-B authority, and a nested child never becomes a
second owner or mailbox.

## Evidence envelope

The successful coordinator result contains `coordinator`, `lineage`, and
`evidence` objects. `lineage` contains the ordered child records above and
the event cursor used to build them. `evidence` contains bounded, sanitized
facts only:

| Object | Required facts |
| --- | --- |
| `coordinator` | Exact session/account/process/name/lane identity, launch fingerprint, and runner incarnation. |
| `process_tree` | Root PID/start identity, containing process-group/domain, observed parent/descendant relationships, tree snapshot sequence, and exclusion status. OS PIDs may be recorded as observations; no child PGID is created. |
| `hooks` | Actual hook event name, coordinator session identity, native `agent_id` when present, joined `task_id` when available, `tool_use_id` when emitted, policy decision, and hook/runtime version. An event without a child ID cannot be attributed to a child by name or timing. |
| `tools` | Tool name, `tool_use_id`, start/end/failure facts, effect/descendant evidence, and whether the tool is still active or uncertain. |
| `lifecycle` | Raw event kind, normalized kind, sequence, parent/task/agent correlation, status transition, and stop provenance. |
| `transcript` | Exact coordinator transcript validation and child record references/store identities, with no bodies. |
| `uncertainty` | Missing, contradictory, unsupported, or potentially mutating observations that block ready/release/replay. |

The process tree is evidence about the coordinator's containing runtime, not a
claim that every descendant is controlled. A positive root process-group
exclusion is required before replacing the old coordinator. A parent exit,
OS suspension, `setsid`, `nohup`, or a background flag alone is not process or
effect exclusion. When the selected runtime mode is proven non-auto-resuming,
the required safety evidence is direct current-run native child/tool
quiescence and containing-tree exclusion; the adapter need not invent a
classifier marker merely because that mode has no auto-resume callback.

## Adapter methods and child boundary

The adapter exposes one exact, versioned method set for the coordinator:
`open(participant_id, spec)`, `interrupt(participant_id)`,
`status(participant_id)`, `shutdown(participant_id)`,
`release(participant_id, native_swap_binding=None)`, and
`send(participant_id, message_id, payload_ref)`. The optional release argument
is backward compatibility for non-native operations only; the controller
never probes alternate names or signatures.
`participant_id` identifies the enrolled coordinator in this boundary.

### Restrictive native-swap target startup marker

A dedicated native-swap target is admitted only when the controller's target
builder sets this exact marker **before** computing `target_spec_digest` and
before persisting the target open intent:

```text
RunnerSpec.fingerprint.native_config.native_swap_target: true
```

This is the only supported location and value. The value must be the literal
boolean `true`; `false`, `1`, `0`, `null`, a string, a malformed
`native_config`, or a top-level fingerprint alias is malformed and refuses.
The marker is copied into the immutable target specification and open intent;
it cannot be changed after either is durable. An absent marker remains
compatible only for ordinary initial or `ctx` startup. A dedicated swap target
may not omit it, and an adapter or raw runner must reject release for a marked
target unless the exact native-swap release binding is supplied, including
after a failed or uncertain authorization attempt. The marker is a
restriction/admission discriminator only: it grants no capability, proves no
readiness, and is not a substitute for the six-stage evidence or release
authorization contracts.

Native child start/stop/restart is not represented as another `open`,
`release`, or top-level SDK connection. The adapter consumes the coordinator's
native event stream and invokes the runtime's supported parent-level stop
boundary. If a runtime exposes a child-specific control operation, it may be
used only when the pinned runtime capability record says it is native,
identity-bound, and safe; it still does not create a child UUID/PGID or an
independent ownership lease.

Every successful coordinator result carries `participant_id`,
`session_id`, `runner_instance_id`, and the evidence envelope. A send returns
the exact mailbox `message_id`, `accepted: true`, and `ack_kind:
accepted-send`; that is transport acceptance, not child completion, model
completion, or proof that a restart happened. No lifecycle operation sends a
model prompt during its control phase.

One persistent reader drains runtime replies, stderr, hooks, and lifecycle
events even while no command is waiting. It routes replies to correlated
waiters and bounds raw-output retention. It MUST distinguish the lifetime of
the `Agent` launch tool from the lifetime of the child it created.

### Private native-child observation ingestion

The adapter may publish one observation of an actually joined native child
through the existing authenticated runner IPC. This is an observation
producer, not a child launch/release operation, route capability, continuation
authority, or quiescence proof. The private adapter seam is
`bind_native_child_observation(callback)`; the callback receives the entire
frame below. No public request, capability boolean, or caller-supplied child
row can create an observation.

The internal frame is exactly:

```text
{
  type: "native-child-observation",
  participant_id: str,
  session_id: str,
  runner_instance_id: str,
  observation: <the exact native-child-observation dictionary below>
}
```

The observation dictionary is exactly:

```text
{
  schema_version: 2,
  architecture: "native-coordinator-lineage",
  record_kind: "native-child-observation",
  observation_id: str,
  source_identity: {
    owner_generation: positive_int,
    lineage_id: str,
    lineage_generation: positive_int,
    session_uuid: str,
    runner_incarnation: str,
    invocation_id: str
  },
  context_binding_digest: sha256,
  claim_digest: sha256,
  observation_watermark: positive_int,
  terminal_outcome: null | "completed" | "stopped" | "failed" |
                    "cancelled" | "unknown",
  child: <the exact existing 15-field native child projection>
}
```

`source_identity` is the strict six-field identity above; the SDK derives it
from its real acknowledged admission/context and never invents an invocation.
`context_binding_digest` is the canonical SHA-256 of the validated native
admission-context with only its mutable `fenced` field omitted. No other
field may be omitted. `claim_digest` is the canonical SHA-256 of the
validated workspace claim. The daemon supplies its independently enrolled
`expected_daemon_id` out of band to the controller; it is deliberately not a
caller/SDK frame field. The controller resolves and persists the source
operation from this exact own-context identity rather than accepting a
fabricated operation ID from the runner.

The child projection is the existing closed dictionary, with no raw runtime
snapshot or extra field:

```text
{
  admission_id: str,
  tool_use_id: str,
  agent_id: str,
  task_id: str,
  parent_agent_id: str | null,
  invocation_id: str,
  lineage_incarnation: positive_int,
  trusted_definition_digest: sha256,
  start_watermark: positive_int,
  task_start_event: {
    event_uuid: str | null,
    watermark: positive_int,
    task_type: str
  },
  status: "active" | "completed" | "stopped",
  terminal_watermark: positive_int | null,
  active_tool_ids: [str, ...],
  uncertain_tool_ids: [str, ...],
  unresolved_effect_ids: [str, ...]
}
```

The child fields, identities, and join rules are exactly those of
`_native_interrupt_child` / SDK `_coordinator_child_roster`; the displayed
shape is not a second schema. `terminal_outcome` is the actual normalized
lifecycle result from the same task notification or established stop evidence:
it is null for an active child. A child is `completed` only when the outcome is
`completed`; a stopped projection cannot report completion. `failed`,
`cancelled`, and `unknown` never supply safe-stop or restoration eligibility
and project as unresolved. Even `completed` does not retire the run while
active/uncertain tools or unresolved effects remain. SDK send acceptance,
parent `Agent` return, timing, and absence of events cannot supply the outcome.
If the projection cannot represent an actual failed or unresolved result, the
observation is refused and readiness uncertainty is retained.
A missing nested durable parent remains unsupported; this seam does not loosen
the existing nested pre-allow authority or synthesize parent linkage.

The controller callback is exactly
`persist_native_child_observation(observation_id, generation, observation, *,
expected_daemon_id)`, one transaction. Its ACK is exactly:

```text
{
  recorded: true,
  observation_id: str,
  observation_digest: sha256,
  child_run_id: sha256,
  observation_watermark: positive_int
}
```

`observation_digest` is the canonical SHA-256 of the complete observation.
`child_run_id` is the canonical SHA-256 of exactly
`{source_identity, admission_id, tool_use_id, agent_id, task_id,
lineage_incarnation, start_watermark}`. The controller validates the frame's
transport participant/session/runner identity, fresh owner and out-of-band
daemon authority, exact current source context and claim, one unique durable
pre-allow admission, immutable definition/policy, and child join/start
watermarks strictly after admission and no later than `observation_watermark`.
The generation must be the exact current integer. A lower per-child watermark
is stale; immutable identities never overwrite; terminal-to-active or
terminal-to-new-task reuse of one child run is invalid.

An exact observation ID plus exact content retry returns the original ACK after
current authority validation even if the mutable fence changed. Changed
content under one ID is invalid. Terminal/inventory observations for an
already-admitted source child remain permitted while fenced, but they never
authorize launch or admission. An archived child, sealed terminal history, or
replaced source authority is refused; old source facts are never reattributed
to a target lineage. The SDK serializes the observation persistence queue so a
later observation cannot overtake an earlier one. A missing/failed callback or
ACK poisons local readiness and never triggers an automatic effect, restart, or
route.

Queued and in-flight observation ACKs participate in the persistent-reader
checkpoint/quiescence accounting alongside admission and coordinator-evidence
callbacks. A same-runner A-to-B preparation cannot seal or retire A while its
joined observations are uncommitted. Pending ACKs block preparation; missing
or failed ACKs preserve readiness uncertainty. Publication is serial and a
bound or cancelled queue cannot silently drop an observation. Controller
archival commits the observations before retiring the source. This bounded
producer never turns an incomplete roster, ambiguous event, or unresolved
framework error into a completed child or parent-drain proof.

### Conservative native restart slots

Restart correlation is a controller-owned durable slot, not an SDK field and
not a new runner RPC. The optional
`operation.metadata.native_restart_slots` map is keyed by
`restart_attempt_id`; each value is exactly:

```text
{
  schema_version: 2,
  architecture: "native-coordinator-lineage",
  record_kind: "native-restart-slot",
  restart_attempt_id: str,
  old_child_run_id: sha256,
  instruction_mailbox_id: str,
  target_source_identity: <the existing strict six-field source_identity>,
  agent_type: str,
  trusted_definition_digest: sha256,
  admission_binding: null | {
    admission_id: str,
    tool_use_id: str,
    admission_watermark: positive_int
  },
  new_child_run_id: null | sha256,
  evidence_refs: [str, ...],
  slot_digest: sha256                  # SHA-256 of all other fields
}
```

The existing `target_source_identity.invocation_id` must equal
`instruction_mailbox_id`; it is not duplicated at slot top level.

The slot's initial identity fields are immutable. `admission_binding` may
change only once, from `null` to one actual pre-allow binding, atomically
before its ACK; `new_child_run_id` may change only once, from `null` to one
joined actual fresh task/child. `slot_digest` is recomputed only for those
permitted monotonic additions; `evidence_refs` may only append observed durable
IDs and never replace or remove one. Existing `restoration` IDs must join the
exact slot. The map is bounded
to 256 slots and the existing complete-record one-MiB limit; it never evicts
history. Exact retries are observational and do not write a slot.
No additional phase enum is introduced; uncertainty remains represented by
the existing dispatch and restoration states.

The dedicated existing coordinator mailbox/invocation carries the controller's
mechanical restart instruction and caller checkpoint. On the first normal
pump, a slot can reserve a new task only under the exact invocation when the
actual `target_source_identity` and explicit release are proven, exactly one
unconsumed eligible old-child slot matches the trusted type/definition, and
the old disposition is `restart-pending`. Zero or multiple matches, a nested
or unexpected parent, a stale B, a repeated admission, or an unknown/partial
send refuses and leaves the child unresolved; no correlation is guessed.
The resulting actual joined task observation must match the reserved
`admission_id`, `tool_use_id`, definition, same B source, and causal watermark,
while carrying fresh task and agent IDs, before `new_child_run_id` and
`restoration: restarted` are recorded. Admission or send ACK alone is never a
restart or a conversation/exact-identity promise.

### Native-swap release boundary

The legacy adapter release shape may be exposed as
`release(participant_id, native_swap_binding=None)` only for backward
compatibility with non-native operations. The `None` form is never a
native-swap path. Native swap refuses unless the pinned adapter capability
exposes the exact native-swap release boundary below; it never falls back to
the legacy `release(participant_id)` call or invents another method/signature.

The frozen `native_swap_binding` dictionary is exactly:

```text
{
  schema_version: 2,
  architecture: "native-coordinator-lineage",
  record_kind: "native-swap-release-binding",
  operation_id: str,
  owner_generation: positive_int,
  expected_daemon_id: str,
  participant_id: str,
  session_id: str,
  runner_incarnation: str,
  lineage_id: str,
  lineage_generation: positive_int,
  request_epoch_id: str,
  release_id: str,
  release_intent_digest: sha256,
  pre_release_evidence_digest: sha256,
  binding_digest: sha256
}
```

All fixed marker values and every field above are required. The
`binding_digest` is `sha256(canonical(binding without binding_digest))`; the
canonical form is the existing bounded canonical-record form, and the digest
is not included in its own input. The controller computes and verifies this
digest before the synchronous gate. The operation, owner generation, daemon,
participant/session, runner, lineage, request epoch, release intent, and
pre-release evidence are immutable once bound. A well-formed digest with a
different identity, generation, epoch, release intent, or pre-release evidence
is a stale-generation/binding refusal.

#### Private native-swap release authorization

The binding is an identity reference, not independent proof of the
controller-owned request epoch, release intent, or `pre-release` observation.
The SDK/runner MUST NOT authorize the synchronous gate from a binding first
received in a release payload or from a self-consistent digest alone. After the
operation is durably `ready-held`, the release intent is durable, and the
matching `pre-release` observation, owner generation, expected daemon, and
held claim have been independently checked, the runner uses the existing
authenticated runner IPC and daemon/controller callback for one private
authorization exchange. It is not a public request, method, capability flag,
caller boolean, or alternate adapter signature.

The internal request frame's type is exactly
`native-swap-release-authorize`; its body has exactly these fields:

```text
{
  validation_id: str,
  binding: <the exact frozen native_swap_binding dictionary>
}
```

The runner chooses `validation_id` once before its first authorization attempt
and never changes it. It never retries this exchange automatically. The
controller callback validates the binding against the independently stored
current held target, durable release intent, matching `pre-release` evidence,
owner generation, expected daemon, and claim. It then durably persists one
authorization before returning the ACK. The stored grant is immutable; a
digest in the request cannot substitute for any of those independently stored
facts.

The ACK body is exactly:

```text
{
  validation_id: str,
  authorized: bool,
  authorization_id: str,
  binding: <the exact frozen native_swap_binding dictionary>,
  authorization_digest: sha256
}
```

`authorization_digest` is
`sha256(canonical(ACK body without authorization_digest))`, using the existing
bounded canonical-record form. The first grant for a release is the only ACK
with `authorized: true`. An exact repeated `validation_id` plus exact binding
returns `authorized: false` as an observation of the prior authorization,
with the same `authorization_id`; it does not grant again or invoke the
release boundary. A changed binding with the same `validation_id` is invalid.
A different `validation_id` for a release that already has a grant is an
uncertain effect, not a new grant or reissue. The original grant and its
binding/digest are never overwritten.

The SDK gates only on the first `authorized: true` ACK matching the outstanding
`validation_id`, delivered through the authenticated private callback. The
runner then checks that ACK and its own actual startup/error/held state plus
current session, runner-incarnation, and lineage identity immediately before
the synchronous held-to-released gate; there is no await between that check
and the gate. A missing pinned callback/capability is `unsupported` native
swap. A lost ACK is uncertain and causes no gate, retry, or reissue. No public
payload, caller boolean, alternate callback, or legacy release call can grant
this authorization. The daemon/controller callback and its integration test
must be pinned before this capability is admitted; this contract records the
required private boundary and does not claim production support.

The existing released acknowledgement/evidence object carries the exact
`native_swap_release_boundary` receipt:

```text
{
  binding: <the exact frozen native_swap_binding dictionary>,
  gate_event_id: str,
  gate_watermark: positive_int
}
```

Immediately before the synchronous gate, the SDK revalidates the complete
binding against the current held participant/session, runner incarnation,
lineage, owner generation, request epoch, release ID/intent, and pre-release
evidence. A mismatch refuses before the held-to-released transition; a
controller-side digest check alone is insufficient.

The runtime captures this receipt at the synchronous held-to-released gate,
not when a later transport receipt arrives. It proves ordering and correlation
of that gate only. Even a receipt with the exact bound event is not the
continuous request-epoch proof: the independent native-swap evidence provider
must observe the same epoch through the gate and supply the `release-boundary`
proof before the controller marks the operation `released` or starts a daemon
pump. A missing/unsupported capability, missing receipt, mismatched binding,
or missing provider proof refuses or leaves the native swap uncertain while
retaining claims; it never invokes legacy release, replays the gate, or pumps.

### Native-swap entry capture ordering

The controller creates one durable `native_swap.entry_capture` record before
any target-profile/transcript preflight or other transcript/runtime effect. Its
exact metadata is:

```text
{
  capture_id: str,
  binding: <the exact stage="entry" native-swap evidence request binding>,
  state: "pending" | "captured-unvalidated" | "accepted",
  observation_digest: null | sha256
}
```

`pending` is persisted first. The controller then invokes the synchronous
private evidence provider exactly once, outside the state lock and before any
transcript or runtime preflight. It deep-copies the bounded raw response into
memory only (at most 64 KiB), computes its canonical SHA-256
`observation_digest`, and persists only `captured-unvalidated` plus that digest;
the unchecked provider response is never logged or stored durably. The
provider cannot choose or certify the runtime pin, and this capture does not
start a second request epoch or perform a second entry poll. The `capture_id`
and exact entry binding are immutable once `pending` is durable.

After the controller independently verifies the selected target held-startup
runtime pin, it validates the **same** in-memory capture against that pin, the
unchanged exact `entry` binding, and fresh operation/owner/lineage/claim
authority. Only then does one atomic transaction append the ordinary `entry`
evidence wrapper and change `entry_capture.state` to `accepted`. The accepted
entry response's `runtime_identity_digest` must equal the independently
selected target pin; a provider self-pin or a digest that merely parses is not
authority. The capture binds the actual released source A context at account
entry, including an un-fenced `fenced: false` context; the later mutable
admission fence is checked separately and never backfilled into or overwritten
on this snapshot.

Capture/pin failure, a crash before the local capture is available, a missing
capture, or a failed same-capture validation leaves the operation uncertain and
forbids interrupt, shutdown, target-open, and other runtime effects. Recovery
does not recapture the provider or create a new epoch. Entry proves only
pre-interrupt identity, capability, ownership, and a sealable roster; it is not
terminal quiescence. Strict terminal child/tool/effect/process evidence is
required after the interrupt at `graph-drained`/`source-excluded`. The original
capture epoch and evidence interval remain continuous through target preflight,
all later stages, and release.

### Child-target route binding

The coordinator `participant_id` and mailbox remain the only physical adapter
recipient. A child-targeted dispatch carries a separate semantic
`native_target` binding resolved by the controller from the durable joined
current-run native ledger. That binding includes the current lineage and
coordinator session, actual `agent_id`, actual `task_id` when emitted by the
runtime, the child-run incarnation (parent invocation/`tool_use_id` and event
watermark), and the immutable definition/effective-permission digest. The
adapter MUST NOT treat caller-asserted names, a stale ledger row, or a reused
`agent_id` as target authority, and it MUST NOT create a child session or
mailbox.

The pinned capability record for an active-child route must identify the
identity-bound native route, the target fields it accepts, and the native
acknowledgement/event correlation it can prove. This is an evidence contract,
not a claim that every installed runtime exposes such a route; fake or local
test doubles do not establish production capability. If the selected pinned
runtime has no supported route and correlation, the adapter reports
`unsupported` and leaves the controller's pending queue entry intact.

For every runtime await, and immediately before a route attempt, the
controller/adapter boundary revalidates the operation and generation, exact
`native_target` incarnation and joined-ledger watermark, effective target
permissions/definition, current coordinator parent session/invocation,
physical participant/mailbox, and capability binding. An unknown, stale,
reused, completed, or differently parented target refuses; it is not silently
retargeted after `ctx`, completion, or a new/restarted child. A changed target
requires an explicit durable reconciliation and a new dispatch intent.

A child-delivery acknowledgement is valid only when native evidence binds the
exact mailbox/message ID, the complete semantic `native_target`, the actual
native route, and the current parent invocation/event watermark. The existing
`accepted-send` response remains parent transport acceptance only: it is not a
child-delivery acknowledgement, child progress event, or restart proof. The
active-child route is separate from the internal full-terminal invocation
rollover; it does not alter or reuse the `prepare-invocation` reservation
interface below and does not require a terminal A-to-B transition.

### Internal terminal-invocation reservation

Same-runner invocation rollover uses one internal, versioned adapter control
frame named `prepare-invocation`. This is implementation-owned control
protocol, not a Claude API, public child identity, second SDK session, or
substitute for the existing stop/interrupt fences. The adapter advertises the
capability and frame version before any runtime query; an unsupported or
unknown capability refuses before a runtime query or send.

The `prepare-invocation` request has a bounded deadline and contains the
following exact binding fields:

- frame/reservation version, operation ID, owner and lineage generations, and
  the daemon incarnation making the request;
- coordinator `participant_id`, session UUID, runner incarnation, prior
  invocation A ID, next invocation B ID, and the prior A / next B mailbox IDs;
- the immutable definitions, effective permissions, workspace/claim binding,
  strict prior event watermark, and the requested reservation ID; and
- the request correlation needed to bind the controller preparation intent to
  the runtime response.

The response contains the same operation, daemon, coordinator participant,
runner, A/B invocation, A/B mailbox, reservation, and watermark bindings plus
the bounded deadline result. It MUST include a parent terminal result
correlated to invocation A and its A mailbox, an independent drain result, and
a complete joined roster: the exact coordinator incarnation and every
admitted child are terminal, with no pending admissions, pending tasks,
active tools, uncertain effects, contradictory evidence, or overflow. A busy
result, send acceptance, sampled quiescence, or a partial roster is
insufficient and does not produce a usable reservation.

The runtime-issued reservation atomically seals invocation A admissions and
work through the controller's B binding commit and reservation consumption.
It records the reservation version and ID, immutable identity/binding digest,
the terminal-proof evidence and sanitized runtime correlation, and strictly
ascending prior/current event watermarks. The seal prevents a new A admission
or work mutation from racing the B commit; it is not inferred from a status
sample.

There is at most one unconsumed runtime reservation for the current
coordinator invocation. A competing reservation ID or a different next
mailbox is a conflict that refuses before changing the seal or issuing work.
An exact retry with the existing reservation ID and byte-equivalent A/B
binding observes the existing reservation rather than issuing another one.

After the controller commits the exact B binding, `send` consumes only that
reservation with the same operation, daemon, coordinator participant, runner,
invocation B, B mailbox, binding digest, and reservation ID. A mismatch is a
conflict before send; no replacement reservation or later dispatch intent is
created. A normal successful delivery occurs once, while retry/recovery is
at-most-once and may leave the item uncertain when send crossing is unknown.

An exact retry with the same reservation ID and byte-equivalent immutable
bindings returns the existing reservation state and cannot issue a second
runtime reservation or send. Any changed identity, mailbox, definition,
permission, claim, reservation body, missing terminal proof, incomplete
roster, or non-ascending watermark is a conflict and refuses before runtime
effect. Callbacks carrying the old invocation ID or an old/equal watermark
are fenced after the new binding; they cannot mutate the current invocation
or immutable history.

The existing admission, coordinator-interrupt, stop, and release fences remain
authoritative and are rechecked around this reservation. If the selected
runtime cannot provide the bounded `prepare-invocation` control, its complete
joined-roster/independent-drain proof, or exact reservation consumption, the
capability is unsupported and the rollover refuses before query or send.

### Private native reservation no-send status evidence

The existing authenticated, correlated `status(participant_id)` response is
the only status acknowledgement used for a native reservation no-send
reconciliation. It carries no new public operation, ACK method, recovery flag,
or caller-supplied proof dictionary. When the adapter can prove the exact
reservation-bound transport continuity, the response may include
`status.evidence.native_reservation_no_send`; when it cannot, that field is
null or absent and the result is unknown.

The non-null field is exactly:

```text
{
  schema_version: 2,
  architecture: "native-coordinator-lineage",
  record_kind: "native-reservation-no-send",
  observation_id: str,
  reservation_binding: <the full existing strict version-1 reserved response>,
  reservation_digest: sha256,
  observation_watermark: positive_int,
  state: "reserved-unconsumed",
  transport_attempted: false,
  receipt_digest: sha256
}
```

`reservation_binding` is the complete existing strict version-1 reserved
response, including its request binding and terminal proof; this record does
not define a reduced or replacement reservation shape.
`reservation_digest` is the canonical SHA-256 of that complete binding, and
`receipt_digest` is the canonical SHA-256 of every other receipt field (with
`receipt_digest` omitted). `observation_id` is the actual newly correlated
runner `STATUS` request ID. `observation_watermark` is the exact positive
watermark of the fully processed existing reader cursor, in the same source
event domain as the reservation, and is at least the reservation's
`terminal_watermark`; the adapter never manufactures a cursor. The literal
`transport_attempted: false` is allowed only when implementation-owned
per-reservation transport history proves that no B query/control-frame write
or await was entered. The bounded receipt is body-free, contains no
credentials, is at most 64 KiB, and is retained under the existing aggregate
record bound without eviction or replay of a consumed receipt.

When the controller consumes this proof to return a committed B mailbox to
the normal queue, it persists the optional sibling
`native_reservation_no_send_consumption` on the same logical rollover. The
sibling is exactly:

```text
{
  observation_id: str,
  receipt_digest: sha256,
  mailbox_id: str,
  consumed: true
}
```

Its `observation_id` and `receipt_digest` must match the retained receipt and
its `mailbox_id` must match the immutable B/`next_mailbox_id`. The receipt,
sibling, and exact B queue transition are one atomic durable transaction (with
the existing reservation commit included when preparation is pending). The
pair is immutable and grants at most one requeue for that logical rollover. A
partial pair, null/non-literal-true `consumed`, mismatch, or extra field
refuses. Legacy absent/null receipts retain an absent sibling and are loaded
byte-for-byte without defaults. Observation IDs are unique across bounded
retained logical rollovers by scanning existing rollover/history records; no
new top-level collection or eviction is introduced, and an archived copy of
the same original rollover must agree rather than count as a new consumption.

The live owned SDK connection retains the exact cached reservation and a
non-evicted transport-attempt ledger for that reservation. It records the
attempt marker before any B query/control-frame write or await. A positive
receipt additionally requires A to remain sealed, the exact reservation to be
unconsumed, no queued or in-flight B write/reader/hook/evidence work or error,
no live prior controller/daemon dispatch for B's mailbox, and known
connection/owner continuity. The status request is serialized through the
existing control path; after its correlated response the adapter rechecks
those local facts synchronously before constructing the receipt. A missing
ledger, a new connection, a default false, an unobservable queue, an already
attempted B, or any ambiguity yields no receipt and preserves unsupported or
uncertain state.

The controller captures the durable preparation or committed binding and
authority under its lock, awaits the owned status call outside the lock, then
rechecks exact operation/phase, owner and daemon, runner, claim, current
context, immutable A history, and the same unconsumed reservation. It persists
the fresh receipt, exact `native_reservation_no_send_consumption` sibling, and
reconciliation/consumption record before any requeue decision. A pending
preparation may commit only the already-existing full reservation through the
ordinary history/binding validator. A committed binding may return only its
exact B mailbox to `queued`; no new reservation, B query/control-frame, or
send is created by recovery. The one existing status observation above is
evidence collection, not a direct recovery query. The normal released daemon
pump alone later sends with fresh fences. A reused receipt,
stale/conflicting binding, changed invocation, lost continuity, or
ambiguous/already-attempted B never requeues. A duplicate recovery while the
same B remains queued is read-only; after normal dispatch begins, no later
receipt or ambiguous outcome can requeue it. Negative/absent status evidence
remains unknown and never becomes a no-send proof.

## Lifecycle ledger

The ledger consumes native lifecycle events from the actual pinned runtime.
It retains raw event names and normalizes them without losing correlation:

The adapter records only fields the selected SDK actually emits. In the
measured SDK 0.2.153 shape, `SubagentStart` carries `session_id`,
`transcript_path`, `cwd`, optional `permission_mode`, `agent_id`, and
`agent_type`. `SubagentStop` carries those base facts plus
`stop_hook_active` and `agent_transcript_path`; neither event supplies a
`task_id`, `tool_use_id`, or `parent_agent_id`. The event `session_id` is the
containing coordinator/session context for this join; it never creates a
per-child UUID.

Tool hooks carry `tool_use_id` and may carry `agent_id` and `agent_type`.
`TaskStarted`, `TaskProgress`, and `TaskNotification` carry `task_id`,
`session_id`, and an event `uuid`, with an optional `tool_use_id`; `TaskStarted`
also carries `task_type`. `TaskUpdated` carries `task_id`, `status`, `patch`,
and optional `session_id`/event `uuid`, but no `tool_use_id`. Session history
metadata may supply `parent_tool_use_id` and `parent_agent_id`. The event
`uuid` is a transport/event correlation value, not a child session UUID or a
child identity.

Join a durable pending `Agent` admission to these actual fields using the
containing session, current parent invocation, task/event watermark,
transcript/cwd facts, tool-use metadata, and native IDs. A pending admission or
history record may join an actual task ID; it cannot create one. A missing or
ambiguous join—including a nested child's parent join—remains unknown; never
fill a field because a name, timing, or path looks plausible.

| Runtime event | Ledger action |
| --- | --- |
| `SubagentStart` | Create or update the child record from its actual `agent_id`, `agent_type`, containing `session_id`, transcript/cwd, and optional permission facts. Join parent and launch-tool fields from the pending admission/history; attach `task_id` only when an actual task event/native task record supplies it. Mark starting/active and start a new `lineage_incarnation` watermark when the runtime reuses an `agent_id`. |
| `SubagentStop` | Record terminal status and stop provenance only when its actual `agent_id`/transcript facts correlate to the current child-run incarnation (task, parent invocation, and monotonic watermark). `stop_hook_active` is hook state, not provenance by itself. Preserve whether the stop was model-, user-, SDK-, parent-, failure-, or process-caused only when that origin is evidenced. |
| `TaskStarted` / `task_started` | Bind the actual `task_id`, containing `session_id`, event `uuid`, task type, and optional tool ID to its parent/child record and mark work active; a task start is not a new top-level participant. |
| `TaskProgress` / `task_progress` / `progress` | Append bounded progress evidence using task/session/event-UUID and optional tool correlation; refresh activity without changing terminal state. |
| `TaskNotification` / `task_notification` / `notification` | Record routing/result notifications using task/session/event-UUID and optional tool correlation; a notification alone is not terminal. |
| `TaskUpdated` / `task_updated` | Apply the actual task ID/status/patch and optional session/event-UUID only when correlated to the current child-run incarnation and the pinned runtime defines the update as authoritative; it has no tool ID to invent. |
| `PreToolUse(Agent)` | Record admission, child/task correlation, and the immutable policy decision before execution. |
| `PostToolUse(Agent)` | Close the `Agent` launch tool's own tool record. **It is never a child terminal event.** A child remains active, stopping, or unknown until `SubagentStop` or an authoritative correlated task terminal event. |
| `PostToolUse` / `PostToolUseFailure` for other tools | Close or mark uncertain only that tool invocation; retain descendant/effect uncertainty independently of the child/task state. |

Events are ordered by a runtime sequence/cursor where available and retain an
arrival sequence otherwise. The controller records a monotonic event
watermark for each parent invocation and rejects a completion/status event
whose watermark predates the current child-run start. A later event cannot
erase an earlier uncertain effect. A completed `Agent` launch call may leave a
native background child running, so the child stays in the active set after
that call returns. A duplicate `agent_id` inside one current incarnation is
invalid; reuse across resumptions is allowed only with the new task,
invocation, and watermark tuple described above.

Terminal status is scoped to the child task, not to a tool call. Missing stop
events, contradictory parent/task/agent links, an event from an unknown
runtime, or an uncorrelated hook leaves the child `unresolved` and keeps the
lineage held. The ledger must continue reading until all admitted children and
tracked tools have a terminal, reconciled state.

## Claims, permissions, and effects

The ownership unit is the coordinator execution lineage. If the coordinator
or any native child may write, the lineage claims the relevant canonical
workspace/worktree before admission and retains it until every writer and
external effect is quiescent. Native children working in the coordinator's
workspace inherit the lineage claim, not an independent owner. A genuinely
isolated child worktree is an additional canonical claim owned by the same
lineage and is checked against the host/workspace-global exclusion index.

A read-only coordinator does **not** make its children read-only. For every
child, actual hook/tool permission evidence MUST bind the exact `agent_id` to
the immutable custom definition, configured permission mode, allowed tools,
and writable paths. The controller must not broaden the parent's policy or
infer a child policy from `read_only`, `dontAsk`, a prompt, a name, or an
environment variable. An unknown child ID, missing definition, or ambiguous
permission result refuses child execution and keeps any lineage claim held.

Runtime-owned native background work is eligible for controlled treatment only
when its native task ID, lifecycle events, parent linkage, process-tree
relationship, and hook/tool policy are all observed. An unmanaged detached
shell/process has no such native lifecycle authority; it remains an unknown
writer/effect and blocks release or automatic replay. Native teams are a
separate participant type and require their own capability evidence; ordinary
coordinator or subagent resume must never be presented as team restoration.

## Quiescence and swap ordering

The selected coordinator-wide candidate follows
[coordinator-interrupt.md](coordinator-interrupt.md), including a complete
identity seal, separate possible-send authorization before the single SDK
call, continuous request observation and independent readers during await.
The legacy raw interrupt loop and task-specific stop authorization do not
supply this contract. Lifecycle completion advances evidence without changing
the identity seal; a late member or changed incarnation invalidates it.

Swap validates the target profile, coordinator transcript, full native child
lineage, child stores, permissions, tools, runtime capability, and ownership
before interruption. It then durably fences new model/task/tool admission,
seals the observed roster, and drains the event stream. The control phase:

The supported parent-level stop request must make every admitted native child
and tracked tool terminal before the coordinator is shut down or its process
tree/group is excluded. Missing or contradictory terminal evidence blocks the
swap; it is never replaced by an interrupt receipt or parent exit.

1. issues the supported parent-level stop request and drains native child/tool
   events;
2. records correlated `SubagentStop`/task terminal events and tracked tool
   ends, or pauses on missing evidence;
3. shuts down the coordinator through the supported runtime boundary only after
   child/tool terminal evidence is present;
4. excludes the old coordinator process tree/group and reconciles descendants;
5. preserves every completed child as completed without replay;
6. opens the exact coordinator session under the target profile, held from
   inference; and
7. leaves every unfinished child held as `resume-pending`,
   `restart-pending`, or `unresolved` until explicit release. No child is
   restored or restarted during the account-control phase.

An interrupt receipt is not quiescence. An active/unknown child, tool,
detached descendant, or external effect keeps the operation paused or
indeterminate. No target runner is released while any lineage writer or
uncertain effect could still act.

## Exact continuation and honest fallback

`resume-pending` is permitted while held only when safely stopped SOURCE
current-run evidence, exact target parent restoration, and the tested pinned
resumability capability all agree:

- the source child run has correlated `SubagentStop` or authoritative
  task-terminal evidence for the current invocation, tracked tools are
  terminal, the source containing process tree is excluded, and effects are
  reconciled;
- the same coordinator parent `session_id` was restored by the exact loader and
  remains held from inference;
- the captured native `agent_id` and an actual `task_id` supplied by a native
  task event/record are addressable through the runtime's supported same-parent
  continuation path;
- the child `type`, direct parent linkage, accessible transcript record/store,
  model, effort, immutable custom definition, tools, and effective permissions
  match; and
- the pinned runtime/version/platform capability says that this source stop
  provenance is resumable (not merely that a transcript exists).

No held/active child-continuation event is required or accepted before
release. After explicit release, and only then, a current correlated native
lifecycle event showing the child active under that same parent invocation and
current event watermark upgrades `resume-pending` to `exact-resumed`, without
an intervening duplicate start or effect.

No child UUID, child session, child PGID, title, picker, fork, or guessed
identity may satisfy this predicate. A child whose native runtime cannot be
addressed by the captured `agent_id` remains non-exact even if its transcript
is present.

The controller reports the following status for every unfinished child:

| Status | Meaning and allowed action |
| --- | --- |
| `resume-pending` | Safely stopped source current-run evidence, exact restored parent, captured native identity/definition, and the pinned-runtime resumability predicate agree while held; await explicit release, then accept a current continuation event. |
| `exact-resumed` | Only after explicit release, a current same-parent/captured `agent_id` continuation event and same definition prove exact continuation. |
| `restart-pending` | Stop and task records are sufficient to compose a mechanical restart instruction, but exact native continuation is unavailable or not yet proven. Do not send it during swap; wait for target readiness and explicit release. |
| `restarted` | After target readiness and explicit release, a normal coordinator instruction produced a correlated new native task/child lifecycle event. This is model-assisted continuation, not proof of the old conversation or identity. An accepted send alone is insufficient. |
| `unresolved` | Identity, stop, transcript/store, policy, process, effect, or lifecycle evidence is missing/contradictory, or the participant kind is unsupported. Keep claims and the fence; never replay automatically. |

User cancellation or SDK cancellation is recorded as stop provenance. Exact
continuation is allowed only if the pinned runtime explicitly says that
provenance is resumable; otherwise the child is `restart-pending` or
`unresolved`, never silently treated as active. If the parent process is lost,
the controller cannot claim exact parent continuity from a new process alone.
It may use `restart-pending` when the durable parent transcript plus the
original native task record, model/effort, custom definition, and current-run
stop/effect facts are intact and a pinned capability permits the later new-run
path, even if the child transcript/store is inaccessible; otherwise it is
`unresolved`. Unknown effects remain unresolved. A model-assisted new run is reported as
`restarted` only after correlated native task events, and the newly assigned
native ID (if any) is recorded as a new run linked to the original task—not
as proof of exact identity.

Promptless parent initialization alone is insufficient evidence of native
orphan handling. Gate0 must use an isolated no-auth orphan fixture on the
actual selected binary/version/digest, mode, platform, and participant kind.
The positive fixture deliberately seeds a durable native parent/task record
and measures these as separate outcomes: persisted-record load, notification
enqueue, child/parent wake, and model-query attempt (including a failed query
in the no-auth mode). It must expose the distinction between
`enqueuePendingNotification`, a wake, and a model request; an eventual `idle`
result cannot collapse them into one outcome.

The target safety criterion is different: after a supported source stop has
produced terminal child/tool evidence and the old `running_background_tasks`
state is durably cleared, target connect with inference fenced MUST show
terminal-cleared state, no orphan restored, no orphan wake/notification, and no
model query. A held connection is not evidence of child continuation.
Interactive takeover and SDK `stream-json` startup are separate
modes: interactive takeover may expose an autoresume callback, while the
`print.ts` path has no such callback. The target probe must use the exact
selected binary/version/digest; it must not substitute a fake callback or a
different executable. For a mode proven non-auto-resuming, direct current-run
child/tool quiescence and process-tree exclusion are the safety evidence; do
not invent a classifier marker solely to account for the absent callback. A
fake runtime or synthetic startup event cannot close this gate. If the target
criterion or applicable non-auto proof is absent, the configuration is
`unsupported`, not a successful zero-model-inference swap.

The selected-runtime identity includes the SDK release as well as the binary:
the measured SDK 0.2.153 path selected bundled CLI 2.1.273, whereas a separate
2.1.270 executable was only an informative trace. Record the selected path as
external sanitized evidence and retain the full executable digest; never
assume a system binary or a prior trace represents the current stream-json
runtime. The measured bundled digest was
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`; it is
probe evidence, not a substitute for recording the selected path/mode on each
run.

The selected 2.1.273 print/stream path can restore persisted
`running_background_tasks` as `restoredOrphans`; its default-enabled
`tengu_ccr_orphan_restore_wake` behavior can call
`enqueuePendingNotification` and cause inference before an external query.
Therefore Gate0 must prove terminal child/tool stop plus durable clearing of
the old running-task state, and must observe target connect without an orphan
wake or model request. Stream-json/print mode by itself is not evidence. If
that proof cannot be obtained, the runtime configuration is unsupported.

## Privacy and bounded evidence

Persist IDs, refs, hashes, statuses, capability/version facts, and sanitized
process/hook/tool observations only. Do not persist credentials, tokens,
conversation bodies, generated handoff prose, or checkpoint contents. Native
transcripts remain the conversation authority. Missing evidence is unknown;
unknown is never converted into a successful stop, permission, ownership, or
exact-resume claim.
