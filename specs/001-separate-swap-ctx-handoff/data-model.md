# Data Model: Native Lineage Lane Operations

## V1 schema amendment

The [stop-then-resume contract](contracts/stop-then-resume.md) specifies a
distinct stored `stop-then-resume-v1` discriminator, digest-bound history
manifest, source-exclusion evidence and release-authorized launch intent.
`ready-to-resume` means no target exists; it is not `ready-held`. Exact field
schemas require implementation tests before use. Existing `native_swap`
six-stage records and absent mode fields retain their old interpretation;
they are never implicitly migrated to v1. The model below continues to describe
those strict records unless explicitly amended by the linked v1 contract.

All records carry `schema_version`, a canonical lane, owner/lane generation,
lineage generation, and an operation or event correlation where applicable.
Records are stored in the
existing owner-only same-store state area; transcript bodies and credentials
are never persisted.

## CoordinatorRecord

The only top-level runtime identity in an active lineage.

- `lineage_id`, canonical lane, durable `owner_generation`, lineage generation,
  workspace/common-directory identity
- exact `session_uuid` and transcript reference for the coordinator only
- selected `profile` and verified account identity (canonical name/email/family)
- pinned runtime/SDK fingerprint, model, effort, permission mode, workspace
  fingerprint, immutable launch configuration
- parent SDK process identity, `runner_incarnation`, and process-group/effect
  evidence
- state: `starting`, `held`, `active`, `stopping`, `completed`, `failed`, or
  `indeterminate`

For a dedicated native-swap target, the immutable launch specification carries
the restrictive marker at exactly
`RunnerSpec.fingerprint.native_config.native_swap_target: true`. The controller
sets it before calculating `target_spec_digest` and persisting the target open
intent. A literal `true` is required; false/non-boolean/null values,
malformed `native_config`, a top-level alias, or omission on a dedicated swap
target fails closed. Omission remains compatible only for ordinary initial and
`ctx` startup. This marker is a restriction, not a capability grant or
readiness proof. Marked targets retain the exact native-swap release binding
requirement even after a failed or uncertain authorization attempt.

There is at most one active coordinator for a lineage generation. `ctx` changes
the `lineage_id`, coordinator UUID, and lineage generation, but not durable
`owner_generation`; only proven unenroll/re-enroll changes the owner generation.
It does not rebind old children to the new parent. A native `ctx` target uses
the ordinary startup specification with any inherited
`native_swap_target` restriction removed; that swap-only marker is never a
ctx capability or publication field.

## NativeChildRecord

One record for each runtime-discovered native Agent/Task child. These fields
are required unless the runtime genuinely omits them, in which case the
operation is held or unsupported rather than filled with a fabricated value.

| Field | Meaning |
|---|---|
| `agent_id` | Exact native Agent identity |
| `task_id` | Exact native task identity, if supplied by the runtime |
| `type` | Native kind, such as foreground/background Agent or Task |
| `tool_use_id` | Parent tool invocation that launched or addressed it |
| `parent_links` | Coordinator session plus actual parent agent/task/tool IDs and current invocation watermark |
| `transcript` | Native transcript reference, availability, and optional digest; never body |
| `status` | `discovered`, `admitted`, `active`, `stopping`, `held`, `completed`, `resume-pending`, `restart-pending`, `restarting`, `exact-resumed`, `restarted`, `unresolved`, or `unsupported` |
| `stop_provenance` | Runtime/model/external stop kind, event ID, timestamp, and evidence digest |
| `model` / `effort` | Configured and observed values |
| `custom_definition` | Immutable custom-agent definition reference/content digest, role, tools, and permission policy |
| `restart_correlation` | Old IDs, owner/lineage generation, runner incarnation, parent-send/request ID, new IDs, lifecycle event IDs/watermark, and exact/assisted outcome |
| `admission_context` | Durable pending Agent admission, parent invocation, expected task hints, event watermark, and the optional controller-derived `parent_observation` causal join used to join sparse lifecycle events |
| `tool_events` | Tracked tool-use starts/ends, descendants, and external-effect evidence |
| `execution_mode` | `foreground` or runtime-owned `background` |
| `claim_ref` | Inherited lineage claim or exact isolated child-worktree claim |

The ledger deliberately has no per-child top-level session UUID, process group,
SDK open/shutdown/release operation, or independent account. A child uses the
coordinator's SDK process/session/account and is controlled through native
runtime events.

### Nested admission causal parent binding

The existing durable pending-`Agent` admission record has one optional
`parent_observation` extension. It is absent for a top-level admission, which
preserves the old record bytes, and is present and non-null exactly when
`admission.parent.agent_id` is non-null:

```text
parent_observation: {
  child_run_id: sha256,
  observation_id: str,
  observation_digest: sha256
}
```

The controller derives this binding before the pre-allow ACK; the SDK's strict
admission and ACK remain unchanged. The referenced committed observation must
belong to the same source context, identify the exact actual parent agent and
incarnation, have an active child with null `terminal_outcome`, contain a
fully joined admission and start, and satisfy
`observation_watermark < nested_admission.watermark`. A live admission also
requires the latest current parent to be active. Reload and archive validation
uses the latest parent state as of the nested admission watermark; a later
parent terminal event is not retroactively applied to that historical join.

Validation is two-pass: pure shape/digest validation first, then causal
context/admission/observation joins. The bounded ancestor chain must end at
the coordinator. Self-links, cycles, ambiguous runs, missing joins, stale or
reused child incarnations, and wrong-context references refuse the admission.
Current target-B authority is never used to validate archived source-A facts.
This is a causal admission join, not an SDK capability, mailbox, child owner,
or runtime continuation proof.

## NativeChildObservation

`native_child_observations` is an optional schema-v2 durable collection of
individual joined child observations. An absent collection loads as empty;
malformed, present-null, duplicate, stale, or over-capacity content fails
closed before effects. It is observation persistence only: it does not launch,
release, route, authorize a capability, prove parent/roster quiescence, or
select a continuation.

The private producer frame, callback, and exact ACK are frozen in
[runner-evidence.md](contracts/runner-evidence.md). The durable map is keyed
by `observation_id` and stores the original observation, its
`observation_digest`, derived `child_run_id`, resolved `source_operation_id`,
and the exact ACK. At most 256 child-run records and 16 observations per run
may be retained within the existing complete-record one-MiB bound; capacity
refuses rather than evicts history. `source_operation_id` is resolved from the
controller's exact current own-context identity, never from a fabricated SDK
field. The derived `child_run_id` is the stable current child-run key; later
observations advance only its monotonic evidence, while earlier observations
remain bounded history. Current routing remains in the separate dispatch
record and cannot be granted by this collection.

The observation's strict `source_identity` has exactly
`owner_generation`, `lineage_id`, `lineage_generation`, `session_uuid`,
`runner_incarnation`, and `invocation_id`. Its `context_binding_digest` is the
canonical digest of validated native admission-context with only mutable
`fenced` omitted; its `claim_digest` is the workspace-claim digest; and its
`observation_watermark` is a positive current-run watermark. The `child` is
the existing exact 15-field `_native_interrupt_child` /
`_coordinator_child_roster` projection, not a raw runtime snapshot. The
separate `terminal_outcome` is null for active and otherwise the actual
normalized `completed`, `stopped`, `failed`, `cancelled`, or `unknown` result.
`completed` requires that outcome; a stopped projection cannot report
completed, and failed/cancelled/unknown remain unresolved. A completed outcome
does not retire the child while active or uncertain tools or unresolved effects
remain.

The controller validates transport identity, current owner and daemon
authority, exact source context/claim, unique durable pre-allow admission,
definition/policy, and strictly ordered admission-to-start-to-observation
watermarks before one atomic persistence of observation, digest, derived
source operation, and ACK. An exact ID/content retry returns the same ACK
after authority validation even if the mutable fence changed; changed content
under one ID, a lower child watermark, immutable identity replacement,
terminal-to-active/new-task reuse, archived/sealed source history, or source
authority replacement refuses. Terminal/inventory observations for admitted
source children may be persisted while fenced but never grant launch/admission.
Old source facts are never rebound to a target lineage.

The SDK serializes publication so observations cannot overtake one another;
queued/in-flight ACKs participate in persistent-reader checkpoint/quiescence
accounting. A pending observation blocks same-runner rollover preparation or
source retirement, and missing/failed ACKs retain readiness uncertainty. A
bound/cancelled queue cannot silently drop an item. Source archival commits all
observations before retiring the source. This collection is not complete
parent/roster drain evidence and cannot be used as a route or exact-resume
capability.

The bounded public status projection is `status.native_children`, sorted by
`child_run_id`, with exactly:

```text
{
  child_run_id: sha256,
  source_identity: <the exact six-field source_identity>,
  admission_id: str,
  tool_use_id: str,
  agent_id: str,
  task_id: str,
  lineage_incarnation: positive_int,
  trusted_definition_digest: sha256,
  observation_id: str,
  observation_watermark: positive_int,
  lifecycle_status: "active" | "completed" | "stopped" | "unresolved",
  terminal_outcome: null | "completed" | "stopped" | "failed" |
                    "cancelled" | "unknown",
  restoration: null | {
    operation_id: str,
    policy: "hold" | "restart" | "prefer-exact",
    disposition: "completed" | "resume-pending" | "restart-pending" |
                  "exact-resumed" | "restarted" | "unresolved",
    restart_attempt_id: str | null,
    instruction_mailbox_id: str | null,
    new_child_run_id: sha256 | null,
    evidence_refs: [str, ...]
  }
}
```

`restoration` is null until a lifecycle operation selects the child. Once
created, its IDs are immutable and `evidence_refs` contains observed durable
IDs only. An active child with no restoration is not `completed` or
`restart-pending`. Completed is sticky and is never replayed; failed,
cancelled, or unknown is unresolved. A send ACK never makes a child
`restarted`. `exact-resumed` requires the documented supported post-release
same-child continuation; otherwise it is unsupported/unresolved. The
controller owns all restoration transitions and never accepts a disposition
from the SDK observation frame.

## NativeRestartSlots

`operation.metadata.native_restart_slots` is an optional controller-owned map
keyed by `restart_attempt_id`. It is not an SDK field or a new RPC. Each value
is exactly:

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

Initial identity fields are immutable. `admission_binding` can move only once
from `null` to one actual pre-allow binding atomically before its ACK, and
`new_child_run_id` can move only once from `null` to one joined actual fresh
task/child. `slot_digest` is recomputed only for those permitted monotonic
additions; `evidence_refs` may only append observed durable IDs and never
replace or remove one. Every existing `restoration` ID must join its exact
slot. The map is bounded to 256
slots and the existing complete-record one-MiB limit; it never evicts history.
Exact retries observe prior state and do not write a slot.
No additional phase enum is introduced; uncertainty remains represented by
the existing dispatch and restoration states.

The dedicated coordinator mailbox/invocation carries only the controller's
mechanical restart instruction and caller checkpoint. On the first normal
pump, a slot may reserve a new task only under the exact invocation when the
actual `target_source_identity` and explicit release are proven, exactly one
unconsumed eligible old-child slot matches the trusted type/definition, and
the old disposition is `restart-pending`. Zero or multiple matches, nested or
unexpected parents, stale B, repeated admission, or unknown/partial send
refuse and leave the child unresolved. The actual joined task observation must
match the reserved `admission_id`, `tool_use_id`, definition, same B source,
and causal watermark, while supplying fresh task and agent IDs, before
`new_child_run_id` and `restoration: restarted` are recorded. Admission or
send ACK alone is never restart or a conversation/exact-identity promise.

## TeamObservation

Teams are a separate capability record, keyed by the runtime's team identity
and membership/lifecycle event references. It carries `status` and evidence
for admission, stop, and restore. It is never flattened into
`NativeChildRecord`; absent pinned evidence is `unsupported` and cannot be
treated as an exact child resume.

## WorkspaceClaim and ChildWorktreeClaim

`WorkspaceClaim` is the host/workspace-global owner for the canonical lineage
workspace. It is acquired whenever any member may write, even when the
coordinator is read-only, and names the lane, owner generation, lineage
generation, repository common directory, canonical realpath, and state (`held`,
`active`, `released`, or `uncertain`). Native children in this workspace inherit
the claim and do not become competing owners.

`ChildWorktreeClaim` is optional and only for a genuinely isolated native child
worktree. It carries the exact canonical realpath, repository/common-directory
identity, owning lineage/child IDs, and lifecycle. The global index rejects
equal paths, realpath aliases, and ancestor/descendant overlap across lanes.
Unknown child identity or unresolved effects retains the applicable claim.

## OperationRecord

- `schema_version`, operation ID, owner/lineage generation, mode (`start`,
  `swap`, `ctx-hold`, `ctx-restart`, `handoff`, `release`, `shutdown`,
  `unenroll`, or recovery), request ID and content digest
- phase: `preflight`, `fenced`, `quiescing`, `interrupting`, `draining`,
  `quiescent`, `worker-state-cleared`, `old-parent-excluded`, `held`,
  `parent-starting`,
  `ready-held`, `released`, `failed`, `unsupported`, or `indeterminate`
- source/target profile references, exact coordinator identity, sealed child
  IDs, deadlines, startup-gate evidence, unresolved tools/effects, and claim refs
- the immutable source capability decision and its exact source specification
  and source-runtime bindings; this decision is distinct from the target
  held-startup `runtime_identity_digest` used by the six-stage evidence record
- committed `native_child_observations` references and their exact
  source-operation/child-run joins; queued or in-flight observation
  persistence remains a readiness/quiescence dependency
- optional immutable `metadata.native_ctx_publication`, absent until the
  atomic target activation and never replaced by a later mutable controller
  digest
- optional controller-owned `metadata.native_restart_slots`, keyed by
  `restart_attempt_id` and validated by the exact bounded record in
  `NativeRestartSlots`; it is never an SDK field or a new RPC
- coordinator interrupt ID, independent admission-fence epoch, sealed roster
  identity digest, immutable roster seal watermark, advancing progress
  watermark, and the continuous
  request-observation epoch when a coordinator-wide interrupt is used
- native-swap evidence epoch/stage records, when the private constructor-only
  evidence provider is installed; the epoch ID and entry observation are
  immutable from account-control entry through release
- release token/count keyed by operation ID + owner generation + runner
  incarnation, native-swap `release_id`/intent digest, exact
  `native_swap_release_boundary` receipt and release-boundary binding when
  applicable, the private native-swap release authorization record
  (`validation_id`, exact binding, immutable `authorization_id`, ACK state and
  digest, and any uncertain/refusal result), and restart dispatch
  correlations; control-phase model request count must remain zero

`startup_gate_evidence` records the actual selected CLI/transport path, pinned
runtime version, executable/config digest, no-auth orphan-fixture result,
terminal source child-stop evidence, and current-worker-state-clear evidence
observed from supported runtime operations (never an external rewrite/clear),
target `restored_orphans=0`, wake-event absence, model-request count, and an
event watermark proving no startup auto-resume/inference before release. It is
observed capability evidence, not a persisted classifier callback or inferred
runtime field.

For `shutdown`, the control service, managed owner, claims, and managed
projection remain available for status/recovery. Only explicit `unenroll`,
after authoritative stop/effect proof and claim reconciliation, clears
ownership. Its durable managed projection-clear event precedes the owner-clear
event; incomplete ordering leaves the owner and legacy refusal state intact.

Allowed transitions are durable and monotonic. Recovery reads runtime lifecycle
events and process/effect evidence before advancing; it never rewinds, repeats
release, or replays an uncertain effect.

## NativeSwapEvidence

The optional `native_swap_evidence` stage collection is populated only through
the private constructor-only `_native_swap_evidence_provider(binding)` seam.
The absent default is `None`; no public request, public boolean, stored flag,
or caller assertion can create an entry. Stage metadata is mutable and separate
from the immutable `NativeSourceArchive`. At most one append-only record is
retained for each of the six stages, within the existing complete-record
one-MiB bound.

The exact provider request binding is:

```text
{
  schema_version: 2,
  architecture: "native-coordinator-lineage",
  record_kind: "native-swap-evidence-request",
  stage: "entry" | "graph-drained" | "source-excluded" | "target-held" |
         "pre-release" | "release-boundary",
  operation_id: str,
  owner_generation: positive_int,
  expected_daemon_id: str,
  source_identity: <the existing strict _native_source_identity object>,
  source_context_digest: sha256,
  source_claim_digest: sha256,
  target_spec_digest: sha256,
  request_epoch_id: str,
  interrupt_id: str | null,
  interrupt_intent_digest: sha256 | null,
  source_archive_digest: sha256 | null,
  target_runner_incarnation: str | null,
  release_id: str | null,
  release_intent_digest: sha256 | null,
  release_boundary: null | {
    binding: <the exact SDK native-swap-release-binding>,
    gate_event_id: str,
    gate_watermark: positive_int
  }
}
```

`release_boundary.binding` is exactly the frozen
`native_swap_binding` dictionary in [runner-evidence.md](contracts/runner-evidence.md);
the runtime receipt is its `native_swap_release_boundary` field on the
released acknowledgement/evidence object. The placeholder above is not a
second or looser schema.

Null interrupt, archive, target-runner, release, and release-boundary values
are allowed only before the corresponding identity exists. Once bound, each is
immutable; a daemon takeover or later stage never starts a new request epoch.

Each native swap also stores one exact `native_swap.entry_capture` metadata
record before any transcript/runtime preflight:

```text
{
  capture_id: str,
  binding: <the exact stage="entry" native-swap evidence request binding>,
  state: "pending" | "captured-unvalidated" | "accepted",
  observation_digest: null | sha256
}
```

The controller persists `pending`, invokes the synchronous private provider
once outside the lock and before any transcript/runtime preflight, and holds a
canonical deep copy of the raw response in
memory only (at most 64 KiB). It persists only the canonical SHA-256 capture digest and
`captured-unvalidated`, never an unchecked provider body. After independently
verifying the target held-startup pin, it validates the same capture, exact
entry binding, and fresh authority before atomically appending the ordinary
entry proof and marking `accepted`. No provider self-pin, second entry poll,
or new epoch is allowed; the `capture_id` and exact entry binding are
immutable once `pending` is durable. The capture is the actual released A
context with its
unfenced `fenced: false` state before the mutable later fence; entry covers
only pre-interrupt identity, capability, ownership, and a sealable roster, not
terminal quiescence; strict terminal child/tool/effect/process evidence is
required after interrupt. Missing/lost capture,
pin or validation failure, or crash preserves uncertainty and prevents
interrupt/target effects; recovery never recaptures. The same capture interval
continues through preflight, later stages, and release.

The provider response is exactly:

```text
{
  binding: <the exact echoed request binding>,
  runtime_identity_digest: sha256,
  evidence_reference: str,
  request_observation: {
    epoch_id: str,
    entry_evidence_ref: str,
    through_evidence_ref: str,
    observable: bool,
    continuous: bool,
    new_requests: int | null
  },
  worker_state_clear: null | {
    source_identity_digest: sha256,
    interrupt_id: str,
    method: str,
    evidence_reference: str,
    observation_watermark: positive_int,
    cleared: bool
  }
}
```

The controller canonicalizes the full response into an `evidence_digest` and
stores bounded references only; no response body or credential is stored. The
request epoch begins at account-control entry before target preflight and the
same `request_epoch_id` and `entry_evidence_ref` remain bound through the
release boundary.
The response must report that same epoch, an observable continuous interval,
and `new_requests: 0` through its requested stage. `pre-release` follows the
durable release intent and precedes the native release call, including its
bounded idle delay. `release-boundary` covers the same historical interval
through the synchronous held-to-released gate event; requests after that
endpoint are outside the swap-control interval. A positive, unknown, or gap
observation is sticky; a later zero cannot repair it. `worker_state_clear` is
null only at `entry`. Every later stage requires the exact current source and
interrupt identities, a supported pinned method, a current correlated positive
watermark, and `cleared: true`. An interrupt receipt, process exit, or
externally rewritten state does not satisfy this field.

The six-stage `runtime_identity_digest` is the independently selected exact
runtime pin for the **target held-startup** capability. It is accepted only
when it matches that target pin and is unchanged across all six stages. It is
not compared with the source pin: the runtime `config_digest` includes the
profile/configuration-directory identity, so source and target pins may
legitimately differ. `target_spec_digest` must equal the authorized normalized
target specification, while `source_context_digest` and `source_claim_digest`
must equal the immutable source context and claim. A different digest that is
merely well-formed is a binding mismatch and refuses.

Before any coordinator interrupt, the source operation also stores a separate
immutable `source_capability` decision, never the target six-stage pin:

```text
{
  verdict: "verified" | "unsupported" | "inconclusive",
  reason_code: str,
  reason: str,
  source_spec_digest: sha256 | null,
  source_runtime_identity_digest: sha256 | null,
  evidence_reference: str | null
}
```

The source decision is bound by the controller to the exact normalized source
runner specification (including profile/configuration-directory fields), the
current source runtime identity, source operation/coordinator identity, and
owner/lineage claim. It is retained as durable source evidence for the
coordinator-interrupt authorization; public requests, target evidence, and the
private six-stage provider cannot create or replace it. Missing, stale,
changed, unsupported, inconclusive, or unbound source proof is an unsupported
operation before interrupt and before any source effect. Source and target
profiles, configuration directories, and runtime pins must not be erased or
made equal to satisfy this contract.

The provider contributes only missing independent request-epoch and
worker-state-clear observations. Its digest is not a capability certificate
and does not stand in for actual interrupt, native member, tool, effect,
process-exclusion, or target-open/ready facts. Missing provider/pinned proof
refuses the swap before interrupt. A fake constructor provider is offline test
evidence only and cannot establish production support.

The stage record is bound to the durable swap sequence: `entry` with static
capability preflight; `graph-drained` after authoritative graph quiescence and
clear evidence; `source-excluded` after one persisted shutdown intent, one
supported shutdown, and process exclusion; `target-held` after one held target
open and actual readiness; target preparation persists the new runner's exact
resume/open specification and intent; `pre-release` after the durable release intent and
before the native release call; and `release-boundary` at the SDK's synchronous
held-to-released gate event. The target preparation records a new runtime
runner incarnation and exact resume/open spec while preserving the same
coordinator UUID, lineage, lineage generation, claim, and owner generation.
The immutable source archive remains until atomic target activation, and a
retry reuses it rather than recapturing a changed source. Native-adoption CAS
is not part of this swap model: its claim-pair helper is reserved for `ctx`'s
new lineage/new UUID. A stage failure or crash leaves the operation held or
indeterminate; recovery observes/reconciles the window and never automatically
replays an interrupt, shutdown, open, send, query, or release.

`target-held` is not a final guarantee through a later release. Native swap
requires the fresh same-epoch `pre-release` observation and the new bound
`release-boundary` receipt. If final proof is missing or contradictory, the
controller records any receipt and uncertain effect, retains claims, and does
not pump or replay; it does not claim the runtime is still held after an
acknowledged release gate. The backward-compatible `runtime.release` endpoint
for other operations is not a native-swap fallback.

For `release-boundary`, `release_boundary.binding` is the exact SDK
native-swap-release binding and the released acknowledgement/evidence
`native_swap_release_boundary` field carries `gate_event_id`/
`gate_watermark` for the synchronous held-to-released transition. The SDK
revalidates the binding and current held identity immediately before that
gate. The provider observes the historical
request interval through that endpoint; later requests are excluded by the
endpoint, not by a later controller timestamp. Even a receipt with the exact
bound event is ordering/correlation evidence only until the independent
provider supplies same-epoch `release-boundary` proof; a receipt without that
bound event is likewise insufficient.

## NativeSwapReleaseAuthorization

Native swap has one private release-authorization record in addition to its
six-stage evidence. It is created only after the operation is durably
`ready-held`, the release intent is durable, and the matching `pre-release`
observation has independently passed current held-target, owner-generation,
expected-daemon, and claim checks. The exact internal
`native-swap-release-authorize` request and ACK bodies are defined in
[runner-evidence.md](contracts/runner-evidence.md). They travel over the
existing authenticated runner IPC and daemon/controller callback; they are
not a public wire request, release method, capability flag, or caller boolean.

The durable record retains the runner's single `validation_id`, the exact
`native_swap_binding`, the immutable first `authorization_id`, the first
`authorized: true` ACK and its `authorization_digest`, plus any later
observational/refusal/uncertain result without overwriting the original grant.
The controller persists that first authorization before returning its ACK; the
binding's self-digest does not prove the controller-owned request epoch,
release intent, or pre-release evidence.

The runner chooses `validation_id` once and accepts only the first true ACK
for that outstanding ID through the authenticated private callback. An exact
repeated ID/binding observes the prior authorization with `authorized: false`
and the same authorization ID, without another grant or runtime call. A
changed binding with the same ID is invalid; a different ID for an already
authorized release is uncertain and cannot reissue. Immediately before the
synchronous gate, the runner independently checks the ACK and actual
startup/error/held state, session, runner incarnation, and lineage without an
await. Missing callback/capability or a lost ACK yields unsupported/uncertain
state respectively; neither permits a gate, retry, or reissue. The existing
`native_swap_release_boundary` receipt remains ordering/correlation only until
the independent same-epoch `release-boundary` provider proof. Until the
daemon/controller callback and its integration test are pinned, this native
authorization is unsupported and this model does not claim production
support.

## CoordinatorInterruptRecord

`coordinator_interrupts[interrupt_id]` is the durable record for one
coordinator-wide interrupt and drain. It is not a collection of child stop
records and has no per-child `stop_task` effect.

- **Source identity:** `operation_id`, canonical lane, `owner_generation`,
  `lineage_id`, `lineage_generation`, coordinator `session_uuid`,
  authenticated `runner_incarnation`, and independent monotonic `fence_epoch`
- **Sealed roster:** canonical `roster_identity_digest`, member references for
  the coordinator, admitted children, accepted-but-unjoined admissions,
  nested tasks, active tools, descendants, and effects, plus immutable
  `roster_seal_watermark` and advancing `progress_watermark`; unknown or
  contradictory membership is held or unsupported
- **Capability binding:** selected executable, SDK/CLI version, transport,
  initialization/configuration, account/mode, model, permissions, and custom
  definitions digest; changing any of these invalidates the capability result
- **Authorization:** request/content digest, `source_exclusion_key` covering
  owner/lineage-ID/generation/session/runner independent of request,
  operation, fence, and roster IDs, `may_have_been_sent`,
  `authorization_count`, and `authorize_send`; the first successful
  persistence sets the marker before the runtime await and returns the only
  positive authorization
- **Independent evidence:** `runtime_ack`, per-member terminal events,
  per-tool terminal events, effect/descendant outcomes, parent-turn drain,
  process exclusion, and the continuous request-observation interval; each
  carries the actual identity/incarnation and event watermark it proves
- **State:** `recorded`, `authorized`, `sent-unknown`, `draining`,
  `quiescent`, `cancelled-before-send`, `uncertain`, `unsupported`, or
  `recovery-required`; cancellation after the possible-send marker is
  `sent-unknown` or `uncertain`, never a successful no-send/quiescent state.
  There is no release state in this record

The identity digest and seal watermark are immutable; the progress watermark
advances only with authoritative current-run events. A new member or changed
incarnation after seal invalidates the pending authorization rather than
expanding the roster. Exact retries, runner restarts, and lost
acknowledgements never return a cached positive authorization or issue another
interrupt; an IPC reader may replay facts but not a send authorization. A
receipt cannot stand in for terminal, tool, effect, parent-turn, process, or
request-count evidence. A coordinator-wide interrupt may run while children
are active, but the parent is shut down only after the complete native graph
is proven quiescent. Process-tree exclusion is a separate post-shutdown gate.
`quiescent` retains claims and does not itself release, restore, or dispatch
work.

Records missing the coordinator-interrupt kind or any required roster,
source-exclusion, authorization, or evidence field are refused as unsupported;
they never default to unsent, empty-roster, or auto-authorized values.
`native_stops` records are not migrated or copied into
`coordinator_interrupts`, even when their surrounding schema version matches.

## NativeSourceArchive

An optional schema-v2 `native_source_archives` controller collection retains
immutable mechanical source snapshots for future adoption/recovery. Entries
bind `archive_id`, `operation_id`, owner/lineage/session/runner/invocation
identity, the complete canonical snapshot digest and the snapshot. The snapshot
omits the archive collection to prevent recursive history duplication and is
validated independently under its original source context. No active ledger,
claim or authorization is removed by archival. At most 16 entries fit within
the existing one-MiB complete-record bound; capacity refuses rather than
evicting history. See [the bounded contract](contracts/native-source-history.md).

A read-only claim adoption assessment reports `source-held`, `target-held`,
or `indeterminate` from exact source/target claim snapshots and current owner
authority. It is an observation, not a durable adoption record, runtime proof,
transfer authorization or completed recovery. Here `target-held` describes
the claim-ownership descriptor only; it does not mean that a target runtime is
held or that its `runtime.open` has run.

The bounded `native-adoptions.json` schema-v2 ledger binds immutable source
archives, exact source/target claim snapshots and digests, owner/daemon/operation
identity, and trusted internal evidence digests before a claim transfer. Its
phases distinguish preparation, a possible CAS, observed transfer and durable
controller acknowledgement. The controller operation retains a compact
`metadata.native_adoption` reference; source context and history remain fenced
and intact. Recovery never retries an uncertain CAS or starts a runtime, and
missing capability evidence refuses before preparation. This is held ownership
bookkeeping, not published target-runtime readiness. See
[the transaction contract](contracts/native-adoption-transaction.md).

## NativeCtxPublication

`operation.metadata.native_ctx_publication` is optional and is absent until
the one atomic target-activation publication. Once written, it is immutable.
It has exactly:

```text
{
  schema_version: 2,
  architecture: "native-coordinator-lineage",
  record_kind: "native-ctx-publication",
  operation_id: str,
  owner_generation: positive_int,
  expected_daemon_id: str,
  archive_id: str,
  archive_digest: sha256,
  adoption_id: str | null,
  adoption_intent_digest: sha256 | null,
  adoption_controller_commit_digest: sha256 | null,
  target_participant_id: str,
  target_session_uuid: str,
  target_lineage_id: str,
  target_lineage_generation: positive_int,
  target_runner_incarnation: str,
  target_spec_digest: sha256,
  target_open_evidence_digest: sha256,
  target_claim_digest: sha256 | null,
  publication_digest: sha256
}
```

All present IDs are nonempty, generations are positive, and every digest is a
canonical SHA-256. `publication_digest` covers every other field. For a
transferred workspace claim, `adoption_id`, `adoption_intent_digest`,
`adoption_controller_commit_digest`, and `target_claim_digest` are all
non-null. They are all null only for a genuinely claimless read-only target;
the controller never manufactures a synthetic CAS or adoption checkpoint.
The receipt records the finalized adoption checkpoint and actual held target
open. It is not permission to infer, replay, or authorize a runtime action.
There is no prepared/publication phase enum: the existing native ctx/open
intent owns prepublication windows.

The native ctx integration order is strict: fence A, drain the native graph,
and prove supported worker-state clear plus process/effect exclusion; validate
the immutable source archive under its original A context while retaining A's
source claim, UUID, and lineage; prepare and advance the existing adoption
transaction; finalize the claim-owned target descriptor; persist the exact
target-open intent; perform the actual target `runtime.open` in held mode;
recheck readiness, owner,
daemon, and target claim; then perform one controller write that publishes the
target participant/startup, retires A's live ledgers into the archive, queues
the caller checkpoint and child dispositions, and installs this receipt. The
target uses the same profile, a new UUID and lineage, lineage generation A+1,
and the same owner generation. Its launch specification removes the inherited
native-swap marker.

Every target field joins the immutable target specification, held-open
evidence, and adoption target claim. The prior `metadata.native_adoption`
reference remains unchanged, and `adoption_controller_commit_digest` remains
the finalized historical checkpoint captured at adoption commit; it is not
required to equal a later mutable controller digest. After publication, an
exact completed ctx retry or getter validates the immutable adoption and
publication joins plus current target authority when an action is requested;
it never re-enters source-only advancement/CAS checks or opens A again after A
has been fenced, archived, and retired. A lost publication acknowledgement
may recognize only the same immutable receipt; a missing or changed join
refuses. Claims persist across CAS/open uncertainty and are never rolled back.
Incompatible isolated-child multi-transfer remains unsupported; this record
adds no transfer mechanics or production provider/proof.

## DispatchRecord

An assisted restart instruction or child-targeted item is recorded separately
from its result. The record keeps semantic target identity distinct from the
physical coordinator recipient:

- `request_id` and `request_content_digest`, where the canonical digest is
  computed before mutable target lookup from caller semantics: requested child
  selector/task, `payload_ref`, sender, generation, and the other immutable
  caller fields. It excludes resolved targets, physical recipients, generated
  mailboxes, routes, and mutable policy;
- `native_target`, the semantic target resolved from the durable joined
  current-run native ledger: `lineage_id`/`lineage_generation`, coordinator
  `session_uuid`, actual `agent_id`, actual `task_id` when supplied, the
  child-run incarnation (parent invocation or `tool_use_id` plus event
  watermark), and the immutable custom-definition/effective-permission
  digest;
- `target_ledger_ref` and its joined-ledger identity/watermark, proving which
  current-run record supplied `native_target`;
- `physical_recipient`, containing the coordinator participant/session,
  `mailbox_id`, and selected route kind. It is never a child session or child
  mailbox;
- `routing_binding_digest`, covering the resolved `native_target`, target-ledger
  reference/watermark, physical recipient, generated mailbox, actual route, and
  effective policy;
- `owner_generation`, runner incarnation, release correlation, and the
  operation/generation binding;
- `dispatch_intent`, atomically durably written at first acceptance with both
  the caller content digest and `routing_binding_digest` before any send, with
  the exact `native_target`, physical recipient/mailbox, current parent
  invocation, route-capability digest, and immutable policy binding;
- parent `send_id` and accepted-send timestamp/status; and
- correlated native acknowledgement/evidence containing the exact mailbox and
  message ID, complete target identity/digest, actual native route, current
  coordinator parent invocation/event watermark, and lifecycle event IDs;
  for an assisted restart it also carries the correlated new native
  `agent_id`/`task_id` and outcome.

While the lane is held, the complete dispatch item, caller content digest, and
any accepted target/routing binding remain in the pending queue. For an exact
accepted retry, the controller compares `request_content_digest` before
mutable target lookup and observes/reconciles the recorded result without a
new send. An unknown, stale, reused, completed, or differently parented
target, or a changed permission or definition binding, refuses and preserves
that queue entry. `ctx`, a completed child, and a restarted/new-lineage child
never cause an implicit retarget. A target change is possible only through an
explicitly recorded reconciliation with a new request ID and new
caller-semantic content digest; the old accepted digest is never overwritten.

An active-child route after `release` is a separate capability from the
full-terminal same-runner invocation A-to-B rollover. It may not consume or
alter the existing `prepare-invocation` reservation interface, and it does not
turn a generic parent `accepted-send` into child delivery. Delivery is proven
only by the correlated native acknowledgement above. If the pinned runtime
does not provide identity-bound active-child routing and that acknowledgement,
the record is `unsupported` and the pending queue is preserved; fake/local
runtime evidence does not claim production capability. An uncorrelated send
is never automatically resent.

## NativeInvocationHistory and rollover records

`native_invocation_history` is an optional, bounded schema-v2 controller
collection of immutable terminal archives. A history entry is created only
after invocation A has been terminally archived; preparation and uncertainty
remain in the separate mutable `native_invocation_rollovers` collection. A
history entry has its own historical validation: it is checked against the
original A context and is never merged into live status or treated as current
runtime authority.

| Field | Meaning |
|---|---|
| `record_kind`, `history_schema`, `history_id`, `integrity_digest` | Explicit immutable record marker/version, unique bounded history identity, and canonical-record integrity digest. |
| `operation_id`, `owner_generation`, `lineage_id`/`lineage_generation`, `daemon_id`, `coordinator.session_uuid`, `runner_incarnation` | Immutable operation, owner/lineage, daemon, coordinator, and exact A-runner binding. |
| `invocation_id`, `mailbox_id` | Invocation A and the mailbox whose parent result is being archived; both are immutable. |
| `context`, `admissions`, `terminal_controls` | A's immutable definitions, permissions, workspace/claim, joined admissions/children, and applicable stop/interrupt/release-control bindings; every nested record validates against A's context. |
| `terminal_result`, `independent_drain`, `joined_roster` | Parent terminal result correlated to A and its mailbox, independent drain, and complete exact-incarnation roster proof. |
| `terminal_watermark`, `source_watermark` | Strictly ordered runtime/event watermarks proving the terminal archive follows the source context. |
| `terminal_proof_digest`, `runtime_correlation` | Sanitized terminal evidence digest and exact runtime response/event correlation; no uncertainty state is stored here. |

`NativeInvocationRollover` is the separate mutable preparation/binding record
in `native_invocation_rollovers`:

| Field | Meaning |
|---|---|
| `record_kind`, `rollover_schema`, `rollover_id`, `integrity_digest` | Explicit mutable record marker/version, unique rollover identity, and canonical-record integrity digest. |
| `operation_id`, `owner_generation`, `lineage_id`/`lineage_generation`, `daemon_id`/`daemon_incarnation`, `coordinator.session_uuid`, `runner_incarnation` | Current authority and post-await ownership binding. |
| `prior_invocation_id`/`next_invocation_id`, `prior_mailbox_id`/`next_mailbox_id` | Exact A/B invocation and mailbox pair; no identity substitution or reuse. |
| `preparation_intent`, `history_id`, `next_context`, `startup_binding`, `reservation_binding`, `dispatch_intent` | Early preparation intent, committed immutable A-history reference, current B context, B startup binding, exact runtime reservation, and B dispatch intent. |
| `reservation_version`, `reservation_id`, `prior_watermark`, `next_watermark` | Runtime reservation identity and strictly ascending rollover watermarks. |
| `native_reservation_no_send` | Optional exact private `status.evidence.native_reservation_no_send` receipt; null/absent means no proof and preserves uncertainty. It is bound to the full reservation, reader watermark, and transport-attempt history. |
| `native_reservation_no_send_consumption` | Optional exact sibling consumption marker, present only with the positive receipt and joined to its observation/digest and `next_mailbox_id`; it grants at most one exact-B requeue. |
| `state`, `uncertainty` | Mutable states `preparation-pending`, `runtime-reserved`, `bound`, `send-pending`, `delivered`, `uncertain`, or `reconciled`, plus an uncertainty annotation; uncertainty never mutates the immutable history. |

The optional `native_reservation_no_send_consumption` marker is exactly:

```text
{
  observation_id: str,
  receipt_digest: sha256,
  mailbox_id: str,
  consumed: true
}
```

Its `observation_id` and `receipt_digest` must equal the retained
`native_reservation_no_send` receipt, and its `mailbox_id` must equal the
rollover's immutable `next_mailbox_id`. The positive receipt and this sibling
are installed atomically with the exact B queue transition (and, for a
pending preparation, any existing-reservation commit); both are immutable
after that transaction. A partial positive pair, a null or non-literal-true
`consumed`, any mismatch, or any extra field is invalid. A legacy absent/null
receipt has an absent consumption marker and is reloaded byte-for-byte without
defaults. The rollover `integrity_digest` covers either optional field when it
is present.

The marker grants at most one requeue for one logical rollover. An exact
duplicate recovery while that same B mailbox remains queued is read-only; once
normal dispatch has begun, no later receipt, fresh observation, or ambiguous
outcome may requeue it. `observation_id` is unique across all bounded retained
logical rollovers, including archived copies; the store scans existing
rollover/history records rather than adding a top-level collection or evicting
an older marker. An immutable source-archive copy of the same original
rollover is the same logical record and must agree with it, not count as a
reusable new consumption.

The adapter's live connection retains the exact cached reservation and a
non-evicted per-reservation transport-attempt ledger, marking an attempt
before any B query/control-frame write or await. The private status receipt is
the only native no-send evidence; a new connection, missing history, default
false, unobservable queue, attempted/ambiguous B, or changed invocation stores
no receipt and remains unsupported or uncertain. The controller captures the
durable binding under lock, obtains one fresh correlated status observation
outside the lock, rechecks operation/owner/daemon/runner/claim/context/history
and the same reservation, then atomically persists the receipt, exact
`native_reservation_no_send_consumption` sibling, and permitted queue
transition. A valid pending preparation can commit only the already-existing
full reservation, and a valid committed binding can return only its exact B
mailbox to `queued`/`send-pending`; recovery creates no replacement
reservation, B query/control-frame, or send. The one existing status
observation is evidence collection rather than a direct recovery query. The
normal released daemon pump performs the later send with fresh fences. Receipts
and their consumption marker are body-free, bounded by 64 KiB and the existing
aggregate limit, and are never evicted or replayed.

The first controller write persists only the preparation intent. The runtime
reservation is not treated as committed until the adapter response is bound.
After A's terminal archive exists, one atomic controller snapshot writes the
immutable A history, B's current context, B's startup binding, the exact
reservation binding, B's dispatch intent, and the operation snapshot together.
The next step consumes that committed reservation and attempts the send; it
creates no later intent. A normal successful delivery occurs once, while the
whole retry/recovery path is at-most-once.

Every history, rollover, and source-archive reader strictly validates its
record marker, schema, required fields, source/A context, identity bindings,
watermarks, integrity digest, and bounds before use. A malformed entry,
unknown marker, context disagreement, duplicate identity, or over-capacity
record refuses before effects; it is never treated as an empty or current
record. The named hard limits are `MAX_NATIVE_INVOCATION_HISTORY_ENTRIES =
16` per operation, `MAX_NATIVE_ROLLOVER_RECORDS = 4` live records per
operation, `MAX_NATIVE_INVOCATION_HISTORY_ENTRY_BYTES = 64 KiB`,
`MAX_NATIVE_ROLLOVER_RECORD_BYTES = 64 KiB`, and
`MAX_NATIVE_INVOCATION_LEDGER_BYTES = 1 MiB` for the complete canonical
controller record. No history is evicted and no invocation, reservation,
rollover, or history identity is reused.

If a schema-v2 record omits the optional history or rollover collections, the
reader treats them as empty and retains existing live-operation rules. If the
collections are present but malformed, validation refuses; it does not
default the malformed data to empty. Schema-v1 records remain unchanged and
are not silently upgraded. None of these records contains conversation
bodies, credentials, resolved payloads, or payload digests; only sanitized
mechanical proof, binding, and correlation evidence are retained.

## Control and safety invariants

1. Admission, tool starts, mailbox dispatch, and parent/child inference are
   fenced before swap/ctx hold. A coordinator-wide interrupt uses an
   independent monotonic fence epoch and seals the complete native roster,
   including pending and nested admissions, before its one durable send
   authorization. The interrupt may initiate child cancellation while members
   are active; it is not a persistent inference fence. Target readiness
   requires no restored orphan, wake event, or model request before release.
2. Before release, a safely stopped exact-continuation candidate is
   `resume-pending`; only a correlated post-release event may become
   `exact-resumed`. When exact continuation is unavailable, `restart-pending`
   may become `restarted` only through a correlated post-release native run.
3. An `agent_id` alone is not an identity match: a reused value requires the
   current `task_id`, parent invocation (`tool_use_id`), and an event watermark
   from this run. A stale ledger marker, parent exit, or accepted send cannot
   correlate a restart. Completed children are terminal. Unknown child identity, detached descendants,
   missing lifecycle/effect evidence, or changed custom policy leaves claims held
   and the operation held/indeterminate.
4. A read-only coordinator does not imply read-only children. Effective child
   tools/permissions are checked against the actual native identity; unknown
   identity cannot receive writable access.
5. A coordinator-wide interrupt may be sent while native children, tools, or
   the parent are active. Its receipt does not prove terminality. The complete
   native graph must first drain with authoritative child, tool, effect,
   parent-turn, and request-observation evidence; natural completion remains
   completed. Only after graph quiescence may supported runtime operations
   clear current worker state and the parent shut down. Identity-revalidated
   process-tree exclusion is a separate post-shutdown gate; the clear is
   observed, never externally rewritten, and target parent launch follows only
after exclusion is proven. `ctx` hold retains stopped worker records; `ctx`
changes lineage/coordinator identity without changing owner generation, and
never exact-rebinds children across parents. Native `ctx` does not treat the
adoption `target-held` descriptor as runtime-held: source archival and
fence/drain/exclusion precede the existing adoption CAS/finalized descriptor,
which precedes target-open intent, actual held open, fresh checks, and the one
atomic `native_ctx_publication`. A completed retry validates that immutable
publication and target authority rather than rerunning source-only adoption or
opening A. `handoff` changes only its explicit checkpoint.
6. Release is once per matching operation ID + owner generation + runner
   incarnation, not once per owner generation; later swap/ctx operations may
   use the same enrollment. Records with missing/unknown schema or the obsolete
   independent-worker participant shape are refused; no implicit migration
   creates native IDs.
7. Native swap release requires the append-only six-stage evidence sequence,
   including same-epoch `pre-release` and the exact synchronous
   `release-boundary` event/binding. A receipt without the bound gate event is
   not final proof, and even a receipt with that event is ordering/correlation
   evidence only until independent same-epoch provider proof; missing or
   contradictory final evidence retains claims and prevents pump/replay
   without claiming the acknowledged runtime is still held. Native swap never
   uses the `native_adoption` claim-pair CAS or the backward-compatible release
   endpoint as a fallback.
