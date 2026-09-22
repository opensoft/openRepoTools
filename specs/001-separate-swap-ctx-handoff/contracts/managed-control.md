# Managed Native-Lineage Control Contract

Mode scope: [stop-then-resume-v1](stop-then-resume.md) has a separate approved
prepare/release boundary. Target-held and six-stage swap clauses below describe
strict mode; they are not silently relaxed for existing records. V1's public
wire/schema implementation remains gated by its own fixture and source proof.

This contract is for the approved native-subagent revision. A managed lane has
one coordinator execution lineage. Native Agent/Task children remain children
of that lineage; they are not independently launched workers, independently
logged-in SDK sessions, or separate control owners. The durable controller is
model-independent until an explicit `release`.

The native runtime and its actual event stream are the authority for child
identity and lifecycle. A coordinator transcript, a returned `Agent` tool
call, a process exit, a background flag, or a caller assertion is not a child
lifecycle fact. Missing or contradictory runtime evidence is reported as
unknown and keeps the relevant operation held or indeterminate.

## Versioned wire and durable state

The wire and durable state use `schema_version: 2` with the architecture marker
`native-coordinator-lineage`. A request is one JSON object of at most 1 MiB over
an owner-only local Unix socket. It contains `schema`, `schema_version`,
`request_id`, `lane`, the expected `generation`, `operation`, and an
operation-specific `body`. The default connect timeout is 5 seconds and the
default operation deadline is 120 seconds; a caller may choose a shorter
bounded deadline, never an unbounded one. A response repeats the request ID,
generation, and current phase, and carries either a result or a stable refusal
code.

The request ledger deduplicates a request ID by its canonical content digest.
An identical retry observes or reconciles the original operation. Reusing an
ID with different content, a stale generation, an invalid frame, or a deadline
expiry refuses before a new runtime action. Runtime facts and process handles
are local evidence, not caller-supplied authority.

Request validation preserves this order: frame/schema, generation and bound-lane
authority first; an already accepted request ID's canonical content comparison
second; mutable participant, profile, transcript and claim checks for a new
request afterwards. A changed bound lane remains an ownership refusal. Changed
same-lane request semantics are a request-content refusal, while an identical
accepted retry can observe its durable result despite later mutable facts.

Unenrollment recovery is a narrow no-runtime exception to the requirement for
nonempty participant evidence: after validating the current durable operation,
generation and `unenroll` mode, an empty participant map asks the controller to
reconcile its sealed participants against the trusted durable claim index. It
does not authorize a claim release, accept caller claim assertions or replay an
effect. Any still-active claim leaves the operation indeterminate. Other modes
retain their nonempty-evidence requirement.

At the internal daemon/controller boundary, an exact canonical SDK
`RunnerSpec` object is projected into durable runner fields rather than
persisting its transport serialization. Only a closed, reviewed set of
non-durable slots may be omitted, and only at their exact SDK defaults:
`environment`, `settings`, `extra_args`, `strict_mcp_config`,
`startup_deadline`, `operation_deadline`, `frame_limit`, `allowed_tools`,
`read_only_tools`, `read_only`, `disallowed_tools`, `add_dirs`,
`setting_sources`, `max_buffer_size`, `role`, `parent_id`, and `task_id`.
Non-default values in those slots refuse rather than being silently lost.
Unknown slots, subclasses and lookalike dataclasses receive no exemption.
Raw mappings still reject environment/settings bags even when empty or null.
The existing wire `supported_models` field is retained as a validated bounded
array of nonempty strings; it is a requested configuration value, never
runtime capability evidence. Nested secret checks and the durable size bound
apply after projection, and no credential material is persisted.

Every durable owner, operation, child ledger, claim, and dispatch/restart
intent carries the same schema marker. A record from the former independent
child-runner/mailbox prototype (including a version-1 record or independent
child UUID/open/release fields) is not interpreted as native state. Operations
refuse with `schema-mismatch`/`migration-required` until a separately reviewed,
explicit versioned migration has produced schema version 2. No operation
silently converts, deletes, resumes, or partially adopts that record; this
contract does not define a migration command.

Durable state is local and private below the resolved workspace Git common
directory at:

```text
openrepotools-managed/<host-identity>/<canonical-lane>/
```

State paths reject traversal, symlink components, unsafe ownership or modes,
and a mismatched workspace identity. Writes are bounded, atomic, and fsynced.
State stores no credentials, tokens, conversation bodies, generated prose, or
capability certificate. Native transcripts remain the conversation authority.

## Lineage record and evidence

The one managed owner records a canonical lane, case-folded ownership key,
workspace/common-directory identity, host identity, monotonic generation,
control-service incarnation, current operation, and the coordinator execution
lineage. The lineage record contains the following exact identity domains.

### Coordinator

There is exactly one active coordinator session for a lineage generation. Its
record includes:

- the exact native coordinator `session_uuid` and validated transcript/store;
- canonical target profile name, expected account email, storage family, and
  existing configuration identity;
- actual initialization account identity, permission mode, model, effort,
  tools, custom-agent definitions, workspace, and the stored launch/settings
  fingerprint;
- the coordinator runtime PID, process group, start token, process domain,
  and evidence that this controller owns and can exclude that process group;
- phase, release receipt/intent, and operation/generation correlation.

Exact coordinator resume uses the official exact UUID path with promptless
initialization. It does not use a title, picker, fork, continuation prompt, or
invented ID. Initialization need not echo `session_uuid` or selected model:
validated transcript identity, the exact loader argument, successful loader
initialization, actual account/permission evidence, and the stored launch
fingerprint are the proof. A truthy account object without the expected email
is not account evidence. A foreign or unobservable process domain is unknown,
not proof that the coordinator has exited.

The control-service PID is a separate process incarnation from the coordinator
runtime PID. Replacing a dead supervisor does not create a new coordinator or
lineage. Recovery must preserve the exact coordinator facts and either adopt
the same live coordinator after identity proof or retain the operation held.

### Profile and account preflight

The target profile is explicitly named and resolved read-only from the
workBenches manifest/metadata and an existing configuration directory. Its
canonical name, expected email, storage family, account state, and config
identity must be unambiguous and match the validated transcript store. A
setup-token profile, missing expected email, family/store mismatch, ambiguous
alias, or unsupported runtime refuses before source shutdown.

Resolution never changes workBenches or launcher/configuration files, copies or
logs credentials, or performs an auth, quota, or paid model probe. The target
launch removes inherited provider-auth/base-URL overrides while preserving the
profile's explicit model, effort, tools, permissions, custom-agent definitions,
and workspace settings. Actual initialization account and permission facts
must still match those preflight values; a caller or environment variable
cannot certify them.

### Native child task ledger

The child ledger is a durable projection of native runtime records and events,
not a roster of child runners. Each entry contains:

- the actual native agent/task ID(s), exact coordinator parent session UUID and
  native parent/task linkage where the runtime emits it, current parent
  invocation identity, and the event-watermark at which the task was observed;
- immutable custom-agent definition, configured model/effort, effective tools,
  permission policy, workspace, and optional isolated child-worktree identity;
- participant kind and whether it is runtime-tracked background work;
- ordered lifecycle events, hook/tool start/end facts, containing process-tree
  evidence, unresolved effects, and the operation/generation that observed it;
  stop/completion must belong to the current parent invocation and a later
  watermark, not merely to an agent ID reused by a later run;
- any restart attempt ID, old task ID, new task ID, correlated acknowledgement,
  and task-event evidence.

While running, a native child shares the coordinator's Claude process,
account, and session name. A child event that identifies another account,
process domain, or session name is contradictory until the runtime proves an
authorized boundary; it is not a second owner. Native child process details
are containing evidence only and never synthetic per-child runner identity.

The ledger never invents a per-child top-level session UUID, account session,
process-group ID, SDK connection, or owner. There is no child `open`, child
`shutdown`, or child `release` operation. A child is controlled through the
coordinator's native boundary and observed through the event stream.

The adapter joins only fields the selected runtime actually emits. In the
currently measured SDK event shape, `SubagentStart`/`SubagentStop` provide
`agent_id`, type, and base session/transcript/cwd facts (stop also reports its
transcript path and stop-hook state); they do not provide a fabricated
`task_id`, `tool_use_id`, or `parent_agent_id`. Tool hooks provide
`tool_use_id` and may provide agent ID/type. `TaskStarted`, `TaskProgress`, and
`TaskNotification` provide task ID/session/UUID and may provide a tool-use ID;
`TaskUpdated` need not. Session history may provide parent-agent or
parent-tool metadata. Durable admission, the coordinator session, and a
current event watermark supply the remaining join boundary. A missing or
ambiguous join, including a nested child whose parent cannot be established,
is `unresolved`; nested children remain under the same coordinator fence and
claim rather than becoming independent owners.

#### Causal binding for nested admissions

The existing durable pending-`Agent` admission record gains only this optional
controller-derived extension:

```text
parent_observation: {
  child_run_id: sha256,
  observation_id: str,
  observation_digest: sha256
}
```

It is absent for a top-level admission, preserving the old bytes, and is
present/non-null exactly when `admission.parent.agent_id` is non-null. The
controller resolves and validates it before the pre-allow ACK; SDK admission
and ACK shapes remain unchanged. The referenced committed observation must be
from the same source context, identify the exact actual parent agent and
incarnation, be active with null `terminal_outcome`, contain fully joined
admission/start evidence, and have
`observation_watermark < nested_admission.watermark`. A live admission also
requires the latest current parent to be active. Pure reload/archive checks
the latest parent state as of the nested admission watermark, so a later
parent terminal event does not rewrite the historical join.

Validation first checks pure shape and digests, then performs causal joins.
The bounded ancestor chain must terminate at the coordinator. Self-links,
cycles, ambiguous or stale/reused child runs, missing joins, and wrong source
context refuse before admission; current target-B authority never validates
archived source-A facts. This join grants no child mailbox, owner, route, or
continuation capability.

For unfinished children, the final externally visible restoration disposition
is exactly one of `exact-resumed`, `restart-pending`, `restarted`, or
`unresolved`. While the operation is held, a safely stopped child that is
eligible for the tested exact-continuation path may additionally be shown as
the interim `resume-pending` state; it is not exact-resumed until a
post-release event proves continuation.

| Status | Required actual evidence |
| --- | --- |
| `resume-pending` (held interim) | Current-run safe-stop evidence and a tested exact-continuation candidate; no continuation is claimed before release. |
| `exact-resumed` | After release, a documented, tested same-agent continuation event correlated to the original native ID and coordinator parent. |
| `restart-pending` | The original child is unfinished but exact continuation is unavailable; no new task has yet been correlated. |
| `restarted` | A new native task event is correlated to the released coordinator, the restart attempt, old task ID, immutable definition, effective permissions, and tool/process facts. This does not claim conversation or identity preservation. |
| `unresolved` | Required identity, stop, effect, or task correlation is missing or contradictory, or a restart outcome is uncertain. |

An authoritative completed child remains `completed`; it is never resumed,
restarted, or replayed. `PostToolUse(Agent)` only proves that the parent tool
call returned. A child that continues after that event remains active until
its own native stop/completion and tool/effect evidence is observed.

### Conservative native restart slots

The controller stores optional `operation.metadata.native_restart_slots`, keyed
by `restart_attempt_id`, using the exact closed record in
[data-model.md](../data-model.md). The map is controller-owned: it adds no SDK
field and no RPC. Its immutable identity is the old child run, coordinator
source identity (whose existing `invocation_id` equals
`instruction_mailbox_id`), instruction mailbox, agent type, and trusted
definition digest.
`admission_binding` is null or one actual pre-allow
`{admission_id, tool_use_id, admission_watermark}` and may make only the
null-to-one atomic transition before ACK. `new_child_run_id` may make only
the null-to-one transition to one joined fresh task/child. Slot digests change
only for these monotonic additions; exact retries observe prior state. The
bounded 256-slot/one-MiB limit refuses rather than evicts, and every
`restoration` ID joins its exact slot.
No additional phase enum is introduced; uncertainty remains represented by
the existing dispatch and restoration states.

The dedicated coordinator mailbox/invocation carries the controller's
mechanical restart instruction and caller checkpoint. On the first normal
pump, the controller reserves a slot only when explicit release and the exact
target source identity are proven, exactly one unconsumed eligible old-child
slot matches trusted type/definition, and the old disposition is
`restart-pending`. Zero or multiple matches, a nested/unexpected parent, stale
B, repeated admission, or unknown/partial send refuses and leaves the child
unresolved. A subsequent actual joined task observation must match the
reserved admission/tool-use binding, definition, same B source, and causal
watermark, and supply fresh task/agent IDs, before the slot gets a new child
run or the restoration becomes `restarted`. An admission or send ACK alone is
never proof of restart, conversation continuity, or exact identity.

### Private native-child observation persistence

The runner may publish an actual joined child fact through the private
`native-child-observation` frame and
`bind_native_child_observation(callback)` seam defined in
[runner-evidence.md](runner-evidence.md). This seam observes one child; it
does not open, release, route, authorize, restart, or certify a complete
roster. The controller callback is exactly
`persist_native_child_observation(observation_id, generation, observation, *,
expected_daemon_id)`, one transaction. The daemon supplies the enrolled
expected daemon ID out of band; the SDK cannot assert it or invent a source
operation.

The controller accepts the frame only after validating transport
participant/session/runner identity, fresh owner and daemon authority, exact
current source context and workspace claim, unique durable pre-allow
admission, immutable definition/policy, and strict admission/start/observation
watermarks. It derives and persists the source operation and child-run ID from
that own context, then atomically stores the original observation, canonical
observation digest, and exact ACK. The observation's terminal outcome is
derived from actual task notification or established stop evidence. A child
projection cannot turn a stopped, failed, cancelled, or unknown outcome into
completed; send acceptance and parent-tool return are not lifecycle evidence.

Exact observation ID/content retries return the original ACK after authority
validation even if the mutable fence changed. Changed content under one ID,
lower child watermarks, immutable identity replacement,
terminal-to-active/new-task reuse, archived/sealed source history, and source
authority replacement refuse. Admitted source-child terminal/inventory facts
remain recordable while fenced but never authorize launch or admission. An
ambiguous nested parent, incomplete join, unsupported outcome projection, or
framework error retains readiness uncertainty rather than creating a child.
Old source facts are never rebound to a target lineage.

The SDK serializes this persistence queue. Its pending/in-flight callbacks are
part of the persistent-reader checkpoint and quiescence accounting alongside
admission and coordinator-evidence callbacks. A same-runner A-to-B operation
cannot seal or retire A while joined observations are uncommitted; pending
ACKs block preparation, and a missing/failed ACK poisons readiness or leaves
the operation uncertain. Publication is bounded and ordered, and cancellation
cannot silently drop an observation. Source archival commits all observations
before retiring the source. The observation collection is never substituted
for complete child/tool/effect drain or parent quiescence. Current dispatch
routing remains governed by its separate durable target/mailbox binding; an
observation cannot alter or authorize that route.

## Native capability and effect gates

The supported native set is the participant kinds and runtime versions for
which discovery, admission fencing, stop, continuation/restart, and effect
accounting have been demonstrated. A native team is a separate capability
from the Agent/Task child ledger. Teams are not silently treated as children,
and no team support is claimed without its own tested identity, stop, and
effect boundary.

A runtime-owned native background child may be admitted when the runtime
provides its native task ID, parent linkage, lifecycle events, controlled stop
boundary, and containing tool/process/effect evidence. `run_in_background` or
any other background flag alone proves nothing. A shell, `setsid`, `nohup`,
arbitrary detached descendant, or remote effect not represented by the native
ledger is a detached effect, not a child entry. Parent exit or OS suspension
does not contain it. Its exclusion/effect outcome must be proven separately;
otherwise the lane stays held or indeterminate and its claims remain held.

Before the matching `release` (including while the coordinator is
`ready-held`), no child status may be inferred from coordinator startup,
prompt text, ordering, a task record without events, absence of an event, or
the coordinator's account/session identity. Actual child events may be recorded
as facts during this phase, but no status is synthesized from their absence or
from parent state. In particular, every supported runtime configuration must
pass an actual startup-orphan gate:

1. exact promptless coordinator initialization is held before inference;
2. the adapter records the exact SDK-selected CLI path, version, full SHA-256
   digest, and stream-json mode, and uses a no-auth orphan fixture to exercise
   the selected binary's restored-worker path. The positive orphan fixture
   must exercise `running_background_tasks` -> `restoredOrphans` -> a
   default-enabled wake -> `enqueuePendingNotification`; record that enqueue
   separately from an actual model-dispatch event. This fixture is not required
   to be silent: queueing a pending notification is not itself model dispatch.
   Stream-json or a `print` callback alone is not a non-auto proof. The current
   local observation is SDK 0.2.153 selecting its bundled CLI 2.1.273, SHA-256
   `6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`;
   this is probe evidence, not a portable support claim;
3. the terminal-cleared production candidate is observed through the
   supported runtime only: terminal-stop current native children/tools and
   prove durable worker-state clearing without editing transcripts. Its target
   held startup must then prove no pre-query wake and no model dispatch. Gate0
   passes only for an exact selected mode/configuration with that evidence;
4. the adapter separately tests interactive takeover, which may auto-resume a
   native orphan before a prompt. If that path is selected and cannot be held,
   it is unsupported for zero-model-request control;
5. the adapter proves, with runtime evidence, that parent and child admission
   remain fenced until release.

If startup can auto-resume an orphan, dispatch a child, or infer an unrecorded
parent/child relationship before release and the runtime has no supported
hold boundary, preflight refuses before source shutdown with
`unsupported`/`startup-orphan`. The controller never labels such a child
active, completed, or safe merely because the parent reached idle.

Only after Gate0 independently proves the exact stream-json non-auto mode,
quiescence uses current-run child and tool events. Stream-json selection or a
`print.ts` callback is not that proof; the callback is void and cannot prove
readiness, stop, or completion. No classifier-marker write is needed or
accepted as evidence. A reused native `agent_id`, stale terminal marker,
parent exit, or old event watermark never proves that the current invocation
stopped. Every stop/completion/restart correlation must match the current
parent invocation, native task identity, process/effect evidence, and a
current event watermark.

The coordinator and every native child retain their configured model, effort,
tools, permissions, custom-agent definition, and workspace. A read-only
coordinator does not make writable children read-only. If any member may write,
the lineage must hold the workspace claim and the child's effective policy must
be explicitly authorized. If the runtime cannot enforce that child policy, the
configuration is unsupported; permissions are not broadened to make it work.

### Private native-swap evidence provider

The controller has one private, constructor-only seam for an independently
observed native-swap fact:
`_native_swap_evidence_provider(binding)`. Its default is absent (`None`); a
public request, public boolean, stored flag, or caller assertion cannot enable
it or grant evidence. The callable is synchronous and read-only. It supplies
only a missing observation of the continuous request epoch or supported
worker-state clearing. It does not interrupt, stop children or tools, exclude
processes/effects, open a coordinator, release it, or mutate runtime state.

The exact request binding is:

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
`native_swap_binding` dictionary in [runner-evidence.md](runner-evidence.md);
the runtime receipt is its `native_swap_release_boundary` field on the
released acknowledgement/evidence object. The placeholder above is not a
second or looser schema.

Null interrupt, archive, target-runner, release, and release-boundary values
are permitted only before that identity exists. Once a value is bound it is
immutable. The request epoch is created at account-control entry, before
target-profile/transcript preflight, and the same epoch ID and entry
observation remain bound through the release boundary; a daemon takeover or
later stage never starts a new epoch.

Before target-profile/transcript preflight, the controller durably creates
exactly one `native_swap.entry_capture`:

```text
{
  capture_id: str,
  binding: <the exact stage="entry" native-swap evidence request binding>,
  state: "pending" | "captured-unvalidated" | "accepted",
  observation_digest: null | sha256
}
```

It persists `state: "pending"`, invokes the synchronous private provider once
outside the state lock and before any transcript/runtime preflight, then keeps
only a canonical deep copy of the response in memory (at most 64 KiB). It
persists its canonical SHA-256 digest and `captured-unvalidated` state, never
an unchecked raw provider body. After independent verification of the selected
target held-startup pin, the controller validates that same capture, exact binding,
and fresh authority, then atomically appends the ordinary entry proof and
changes the marker to `accepted`. The provider cannot select/self-certify the
pin; no second entry poll or new epoch is permitted. The `capture_id` and
exact entry binding are immutable once `pending` is durable.

The capture binds the actual released A context at entry with its actual
unfenced `fenced: false` state, before the mutable later fence; it does not
synthesize or overwrite source identity. Entry covers
only pre-interrupt identity, capability, ownership, and a sealable roster, not
terminal quiescence. Strict terminal child/tool/effect/process evidence remains
required after interrupt. A missing capture, capture/pin failure, failed
validation, or crash that loses the in-memory capture leaves uncertainty and
prohibits interrupt, shutdown, target-open, and other effects; recovery never
recaptures the provider or starts a new epoch. The original capture interval
continues through target preflight, later stages, and release.

The exact response is:

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

`worker_state_clear` is null only for `entry`. For every later stage,
success requires the exact current source and interrupt identity, a supported
pinned method, a current correlated observation watermark, and `cleared: true`;
an interrupt receipt, process exit, or externally rewritten state is not a
clear proof. Request-epoch success requires the same epoch, the stable entry
evidence reference, an observable continuous interval, and
`new_requests: 0` through the requested stage. For `pre-release`, this
observation follows the durable release intent and precedes the runtime call,
including any bounded idle delay. For `release-boundary`, it covers the same
historical interval through the synchronous held-to-released gate event;
requests after that endpoint are outside the swap-control interval. A
positive, unknown, or gap observation is sticky: a later zero-request response
cannot repair it, and the operation remains held or unresolved.

The six-stage `runtime_identity_digest` is the independently selected exact
runtime pin for the **target held-startup** capability. The controller accepts
it only when it matches that target capability's pin and remains unchanged
across all six stages. It must not be compared with the source pin: the
runtime `config_digest` includes profile/configuration-directory identity, so
legitimate source and target profiles can have different runtime pins. It also
requires `target_spec_digest` to match the authorized
normalized target specification, and
`source_context_digest`/`source_claim_digest` to match the immutable source
context and claim. A syntactically valid digest with a different binding is a
refusal, not evidence.

Before the durable coordinator interrupt is selected or sent, the controller
must retain a separate immutable `source_capability` decision from the
source operation's own static capability gate. Its bounded projection is:

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

`source_spec_digest` is the canonical digest of the exact normalized source
runner specification, including its profile/configuration-directory fields;
`source_runtime_identity_digest` is the independently selected current source
runtime pin. The decision is joined to the source operation, coordinator
participant, owner/lineage identity, and current runtime record by the
controller; it is not supplied by the caller, six-stage evidence provider, or
target startup. A verified decision requires both exact bindings and bounded
evidence. The target `runtime_identity_digest` can never satisfy this source
grant, and source/target profile or pin equality is not required. A missing,
stale, changed, unbound, unsupported, or inconclusive source decision refuses
the operation as unsupported **before** any coordinator interrupt, shutdown,
or other source effect.

The controller canonicalizes the complete response into a bounded
`evidence_digest` and stores only bounded references and mechanical evidence;
it stores no response body or credential. At most six append-only stage records are
retained within the existing one-MiB record bound. The provider's digest is
not a capability certificate and cannot replace actual interrupt, native
member, tool, effect, process-exclusion, or target-open/ready evidence.

The existing `_capability_evidence_provider` and
`runtime.preflight_held_swap` still admit a static exact mode first. The swap
stages then use the private provider only at these boundaries: one synchronous
`entry_capture` before transcript/runtime preflight, followed—after the
independent target pin is verified—by validation of that same capture and the
ordinary accepted `entry` proof; `graph-drained` after
`coordinator_interrupt_status.graph_quiescent` and independent clear/epoch
evidence; `source-excluded` after one persisted shutdown intent, one supported
`runtime.shutdown`, and runtime process exclusion; and `target-held` after
the exact target has been opened once in held mode and `_runtime_ready` has
proved its target checks; `pre-release` after the durable release intent and
before the native release call; and `release-boundary` at the SDK's synchronous
held-to-released gate event. Native swap requires this new bound release
boundary receipt. The backward-compatible `runtime.release` endpoint used by
other operations is not a native-swap fallback. If the constructor hook or a
pinned proof is absent, swap refuses before interrupt. A fake constructor
provider is an offline test route only and does not claim a production native
capability.

The stage-to-boundary mapping is exact: durable `entry_capture` and its one
synchronous provider call before transcript/runtime preflight, followed by
`_runtime_capability_preflight` and same-capture validation/accepted `entry`
proof; durable interrupt selection followed by
`interrupt_native_coordinator`; `coordinator_interrupt_status.graph_quiescent`
and the independent `graph-drained` observation; persisted shutdown intent,
one `runtime.shutdown`, `_runtime_shutdown` exclusion, and `source-excluded`;
paused `archive_native_source` (reusing its immutable archive on retry);
dedicated `_prepare_native_swap_target_locked` with the new runner and exact
resume/open spec and intent; one held `runtime.open` and `_runtime_ready`; then
`target-held` and one controller snapshot that binds the target runner/profile/
native startup and records child dispositions. The snapshot retains the
source archive until atomic target activation.

Native swap keeps the exact coordinator UUID, `lineage_id`, lineage
generation, claim, and owner generation. It uses a dedicated staged target
preparation that records a new runner incarnation and exact resume/open spec;
the source archive is retained until the atomic target activation. The target
runner is a new runtime process with the same native identity, and a changed
runner is not smuggled past the startup helper's refusal. `native_adoption`
CAS is not used here: its strict claim-pair helper is for `ctx`'s new lineage
and new UUID. The existing released same-runner invocation rollover remains a
separate operation and reservation interface.

## Public operations

All lifecycle operations serialize under the managed owner/generation lock.
No lock is held across a runtime await, hook, or tool round trip; the exact
operation and generation are reloaded and rechecked before every durable
transition.

### `start`

`start` is explicit opt-in enrollment of one coordinator lineage. Under the
shared ownership boundary it refuses a live or unknown legacy holder and
preserves a durable managed owner if a later control process dies. It
preflights the workspace, profile, transcript, permissions, and supported
runtime, reserves the coordinator's fixed UUID when needed, and opens exactly
one coordinator with promptless initialization.

The successful boundary is an actual coordinator account, exact UUID,
permission/settings fingerprint, workspace identity, and owned process-group
identity in `ready-held`. Native children are only ledger entries backed by
actual startup events. No child is opened, released, or inferred by `start`.

### `fence`

`fence` durably closes new coordinator input, native child/task admission, and
restart/dispatch intent for the current generation, then seals the observed
native roster. A racing child spawn is rejected before launch or is recorded
with its actual parent/task IDs before the seal; no untracked writer is
admitted. Runtime-owned children and tracked tools drain through the
coordinator-level boundary. The fence records each actual event and leaves
unknown descendants/effects unresolved. A fence is not a child-level stop API
and does not release a claim.

### `swap`

The coordinator-wide candidate is specified in
[coordinator-interrupt.md](coordinator-interrupt.md). It requires a distinct
durable whole-roster intent before one SDK interrupt, independent native/tool/
effect drain evidence and a continuous zero-new-request interval from control
entry. This is an internal transaction, not a new public interrupt endpoint;
unknown send outcomes retain claims and never authorize automatic resend.

`swap` changes only to the explicitly selected authorized profile in the same
transcript-storage family. It performs all profile, transcript, child-policy,
and startup-orphan checks before interrupting the source. It then:

1. durably fences admission and seals the native ledger;
2. terminal-stops current native children and tracked tools through the
   supported parent boundary, then proves through the supported runtime that
   durable worker state is cleared for the replacement startup; a launch-tool
   return is not that proof and transcripts are never edited;
3. persists the shutdown intent and invokes the supported `runtime.shutdown` at
   most once;
4. records and proves exclusion of the old coordinator process group and all
   controlled writer/effect ownership, records the `source-excluded` evidence,
   and archives the exact source mechanically. A retry reuses that immutable
   source archive; it never recaptures a changed snapshot;
5. runs dedicated staged target preparation, persisting a new target-runner
   incarnation and exact resume/open specification without relaxing the
   startup helper's changed-runner refusal. Before computing
   `target_spec_digest` or persisting the target open intent, the dedicated
   builder sets exactly
   `RunnerSpec.fingerprint.native_config.native_swap_target: true`. This
   literal boolean marker is immutable thereafter; a false, non-boolean,
   null, malformed `native_config`, top-level fingerprint alias, or omitted
   marker refuses the dedicated swap target. Omission remains compatible only
   for ordinary initial/`ctx` startup. It then opens the exact coordinator UUID
   promptlessly under the target profile once, in held mode;
6. verifies target account email, actual permission mode, launch fingerprint,
   workspace/transcript store, process identity, native event gate, and
   no-restored-orphan/no-model-request behavior, and records `target-held`
   evidence; and
7. atomically activates the target snapshot as `ready-held`, retaining the
   immutable source archive, completed children, every claim, and the exact
   UUID/lineage/generation binding.

The marked target may be released only through the exact
`native_swap_binding`. The adapter and raw runner reject a release that omits
or changes that binding, including after a failed or uncertain authorization
attempt; they do not fall back to the ordinary release signature. The marker
is a restriction only, not a capability grant or readiness proof.

The private provider stages are observations around these operations, not
replacements for them: `entry` precedes preflight effects, `graph-drained`
follows authoritative graph quiescence and clear proof, `source-excluded`
follows the persisted shutdown, at-most-once shutdown, and process exclusion,
`target-held` follows the one held target open and actual ready checks,
`pre-release` follows the durable release intent and precedes the native
release call, and `release-boundary` observes the historical interval through
the SDK's synchronous held-to-released gate event. A missing or sticky unknown
at any stage keeps the operation held/indeterminate. A target-held snapshot is
not a final proof through release; native swap requires the fresh same-epoch
pre-release observation and the new bound release-boundary receipt. If the
final proof is missing or contradictory, the controller records any receipt
and uncertain effect, retains claims, and performs no pump or replay. It does
not claim the runtime is still held after an acknowledged release gate. A
A crash in an interrupt, shutdown, open, or send window never causes automatic
replay, query, release, or a new target call; recovery reconciles the durable
intent and observed stage only.

No target child is opened or released separately. A safely stopped child that
has a tested same-agent continuation is `resume-pending` while held and may
become `exact-resumed` only after release and correlated native events. If
exact continuation is unavailable, an unfinished child is
`restart-pending` and held. No model request, generated summary, checkpoint,
commit, push, stash, reset, clean, move, worktree reconstruction, or written
swap handoff occurs during swap. Unknown stop/effect/identity evidence keeps
the lane paused or indeterminate.

### `release`

`release` accepts only the matching `ready-held` operation and generation. The
controller durably records one release intent. For non-native operations it
then invokes the coordinator's one explicit runtime release boundary at most
once and records its correlated receipt; native `swap` has the additional
private authorization sequence below between those durable facts and that
runtime gate. There is no child release call. Release is the first normal
inference boundary; no lifecycle operation invokes it implicitly. Any
resulting model usage, including assisted restart, is normal post-release use
and is reported separately from the zero-new-model-request account-control
phase.

For native `swap`, the release intent binds a new `release_id` and
`release_intent_digest`. After the operation is durably `ready-held`, that
intent is persisted and any bounded idle delay has elapsed, the controller
obtains the `pre-release` observation and verifies that it matches the current
held target, owner generation, expected daemon, and claim. It then sends the
private `native-swap-release-authorize` request over the existing authenticated
runner IPC and daemon/controller callback. The exact request/ACK bodies and
retry rules are frozen in [runner-evidence.md](runner-evidence.md). The
controller independently validates those durable facts and persists one
authorization before returning the ACK; the binding digest in a release
payload is never accepted as proof of the controller-owned epoch, intent, or
pre-release observation.

The runner chooses one `validation_id` before its first attempt. Only the
first `authorized: true` ACK matching that outstanding ID can reach the
authenticated private SDK callback. Immediately before the synchronous gate,
the runner verifies that ACK and its own actual startup/error/held state,
session, runner incarnation, and lineage without an intervening await. An
exact repeated ID/binding is an observational `authorized: false` response
with the original authorization ID and makes no call; a changed binding with
the same ID is invalid, and a different ID for an already-authorized release
is uncertain rather than a reissue. A missing pinned callback is unsupported;
a lost ACK is uncertain. Neither case permits a gate, retry, or reissue, and
no public request, capability flag, caller boolean, alternate signature, or
legacy `runtime.release` call can grant native swap.
Until the daemon/controller callback and its integration test are pinned, this
native authorization capability is `unsupported`; this contract makes no
production-support claim.

The SDK must emit the exact bound held-to-released gate event synchronously;
the `release-boundary` observation proves the historical epoch through that
event before the controller marks the phase `released` or lets a daemon pump
run. The receipt itself is only ordering/correlation evidence, even with the
bound event; independent same-epoch provider proof is required. Native swap
requires this new bound `native_swap_release_boundary` receipt. The
backward-compatible `runtime.release` endpoint used by other operations is not
a fallback. Missing or contradictory final evidence records the receipt and
uncertain effect, retains claims, and performs no pump or replay; an
acknowledged gate is not reported as still held.

After release, a `resume-pending` child may follow the tested exact native
continuation path; only its correlated current-run events may change it to
`exact-resumed`.

When an unfinished child is `restart-pending`, the released coordinator MAY
receive one mechanically composed restart instruction for that operation. The
instruction contains only durable native child IDs, statuses, restart attempt
identity, and the requested native task action; it is not a semantic summary,
checkpoint, or written handoff. It travels through the coordinator/native
interface, never through a child account or child session. If no restart is
needed, no instruction is sent.

The send has its own durable dispatch intent and must be correlated to the
exact instruction ID. `accepted-send` means transport acceptance only; it is
not proof that any child restarted. A `restarted` status requires correlated
new native task/lifecycle events tied to the same coordinator parent,
generation, old child ID, restart attempt, current parent invocation, event
watermark, immutable definition, effective permissions, and tool/process
evidence. A partial restart records each known new task and leaves the
remaining children `restart-pending` or `unresolved`.
An uncertain send, accepted send with no task event, or partial crash is never
resent or replayed automatically.

### `recover`

`recover` reconciles the recorded operation and process/effect evidence. It
does not open a child, send a prompt, release the coordinator, resume an
orphan, or replay an uncertain instruction. A dead control service may be
replaced only after exact owner/process identity and the shared ownership lock
prove that the old service is excluded; the replacement preserves lineage,
coordinator UUID, child ledger, operation/request intents, and claims.

#### Native invocation rollover recovery entry seam

The existing public `recover` body remains exactly
`{operation_id: str}`. It has no caller-supplied evidence, transport-proof,
`no_send` flag, status value, or capability grant. `recover_dispatch` remains
the synchronous legacy entry point for the other recovery modes. A native
unresolved-rollover dispatch is the uncertainty-reconciliation branch and
rejects any supplied evidence; it never turns a caller assertion into a
no-send result or a send authorization.

For that native branch, the daemon first identifies the current released
native operation and requires exactly one unresolved invocation-rollover
record, a fresh owner/operation/generation/daemon authority check, and a
no-live-original-dispatch fence. If any of those facts is absent, stale,
ambiguous, or duplicated, it does not dispatch recovery or queue B. With the
fence established, the daemon skips generic `_collect_recovery_evidence` and
calls the existing `controller.recover(operation, generation)` without an
evidence argument. Other recovery modes retain their existing entry and
evidence rules.

The controller's native branch runs before generic evidence-required and
mode-specific recovery paths and rejects an evidence argument. It reaches the
private async helper
`_recover_native_invocation_rollover(operation_id, generation) -> Operation`
only through that existing public body. The helper captures the exact current
authority and either the mutable preparation or committed binding under the
controller lock, calls the owned `runtime.status(participant)` path once
outside the lock under its existing bounded deadline, then rechecks the
operation/phase, owner and generation, daemon and runner, claim/context,
immutable A history, and the same unconsumed reservation when one is already
controller-bound. If preparation has no controller reservation, the exact SDK
reserved response must instead pass the ordinary validator below. It validates
the frozen `native_reservation_no_send` receipt and persists its
receipt/digests and one-time consumption before any queue transition.

When preparation is pending and the controller has no reservation, the helper
may use `_native_commit_rollover_locked` only with the exact SDK-existing
reserved response, after the ordinary cross-record history/binding validator
passes. It never creates a replacement reservation. When the binding is
already committed, only its exact B mailbox may be returned to `queued` (and
its rollover to `send-pending`) after the same cross-record validation. The
helper returns the durable operation; it performs no inline preparation,
runtime send, dispatch pump, or new query/control frame. The normal released
daemon pump alone owns the later send with fresh fences.

An exact repeated successful reconciliation is observational: it returns the
existing durable result without another authorization, reservation, queue
creation, or send attempt. Missing or contradictory receipt evidence, stale
authority, changed invocation/binding, lost continuity, or any attempted or
ambiguous B leaves the rollover uncertain and cannot queue it. No native
recovery path falls through to the generic collector or to a legacy release or
send path.

Recovery obtains fresh native lifecycle, tool, process-domain, account, and
effect evidence. It may mark a child `exact-resumed`, `restarted`, or
`completed` only from the corresponding actual runtime event and identity
correlation. Missing evidence remains `unresolved`; no parent status or
coordinator transcript inference is accepted.

### `status`

`status` is observational and does not fence, release, restart, unenroll,
clear state, or mutate a worktree. It reports schema/migration state, owner,
generation, operation phase, exact coordinator account/session/process facts,
child ledger statuses and event sources/timestamps, tracked tools, detached or
uncertain effects, claims, release/restart intents and acknowledgements, and
the tested runtime capability gate. It prints `unknown` when evidence is
missing or stale; it never upgrades an unknown child to stopped or completed.
The public `status.native_children` projection is the bounded, sorted
`child_run_id` record defined in [data-model.md](../data-model.md): its
`terminal_outcome` is actual lifecycle evidence, and its `restoration`
disposition is controller-owned. An active child without a selected lifecycle
operation is not reported as completed or restart-pending; a transport/send
ACK never reports `restarted`. The native-reservation no-send receipt is
private controller-generated status evidence only; no public `status` or
`recover` argument can supply a proof flag or dictionary.

### `shutdown`

`shutdown` first fences admission and then requests one bounded coordinator
stop boundary covering the controlled native lineage. It has no per-child
shutdown operation. The supervisor records native child/task stop events,
tracked-tool quiescence, process-group exclusion, and detached-effect
outcomes. Parent exit alone is insufficient.

Shutdown leaves the durable managed owner, control endpoint, lineage
generation, claims, and unresolved effects in place so `status`, `recover`, and
`unenroll` remain reachable. It is successful only when all controlled writers
and tools are authoritatively quiescent and excluded; otherwise it returns a
specific held/indeterminate refusal and changes no claim into free space.
Shutdown never falls back to a legacy launcher.

### `unenroll`

`unenroll` is allowed only after authoritative coordinator and native-child
quiescence, tracked-tool completion, detached-effect resolution, process-group
exclusion, and exact claim-removal proof. Under the same lock it clears the
managed projection through the supported registry helper, removes lineage
claims, and commits the owner removal atomically. A helper refusal or uncertain
child/effect retains the owner and a recoverable intent. The generation tombstone
remains so a stale request cannot be accepted by a later enrollment. No
runtime is opened, released, or restarted by unenrollment.

## `ctx` and `handoff` are separate

`ctx` requires a checkpoint reference supplied by the caller and keeps the
current account/profile. It fences the existing lineage, proves the old
coordinator process is excluded, and creates a fresh coordinator with a new
UUID and lineage generation held before inference. The checkpoint is queued as
caller data; the controller does not generate prose or send it during `ctx`.

The caller chooses one explicit worker policy:

- `hold` stops and retains the native workers' old task records, parent links,
  claims, and unresolved effects. They stay stopped/retained under the old
  lineage; the fresh coordinator does not exact-rebind them or release them.
- `restart` creates a new `lineage_id` and coordinator UUID from the
  caller-supplied checkpoint. The durable lane owner and its generation remain
  unchanged; owner generation advances only on unenrollment followed by a new
  enrollment. Only after the fresh coordinator's explicit `release` may one
  mechanical ID/status instruction ask it to create new native child tasks.
  New task IDs are correlated to old records but are not cross-parent exact
  continuation and do not prove old conversation identity.

### Native ctx adoption and publication

For native `ctx`, an adoption `target-held` result is only the finalized claim
ownership descriptor; it is not runtime-held evidence and does not imply that
the target has been opened. The integration order is fixed:

1. fence A, drain the native graph, and prove supported worker-state clear
   plus process/effect exclusion; then
   validate the immutable source archive under A's original context while
   retaining A's source claim, UUID, and lineage;
2. prepare and advance the existing native-adoption transaction and finalize
   its claim-owned target descriptor; a possible CAS is never retried
   automatically;
3. persist the exact target-open intent;
4. perform the actual target `runtime.open` in held mode and recheck target
   readiness, current owner/daemon authority, and the target claim; and
5. perform one controller write that publishes the target participant/startup,
   keeps the target's current context unset until a real first mailbox, retires
   A's live ledgers into the immutable archive, queues the caller checkpoint
   and child dispositions, and installs the immutable
   `metadata.native_ctx_publication` receipt defined in
   [data-model.md](../data-model.md).

The target keeps the same profile and owner generation, but uses a new
coordinator UUID, new lineage, lineage generation A+1, and new runner
incarnation. Its startup specification explicitly removes any inherited
`RunnerSpec.fingerprint.native_config.native_swap_target` marker; ordinary
`ctx` release remains governed by the existing release gate. All publication
target fields must join the immutable target specification, held-open evidence,
and adoption target claim. The prior `metadata.native_adoption` reference is
retained unchanged, and its `controller_commit_digest` is the finalized
historical checkpoint at adoption commit, not a digest that must track later
mutable controller state.

The publication record is absent until that atomic activation and has no
prepared/publication phase. After publication, an exact completed `ctx` retry
or getter validates the immutable adoption/publication joins and current
target authority when an action is requested; it never re-enters source-only
adoption advancement or CAS checks and never reopens A after A was fenced,
archived, and retired. A lost publication acknowledgement may recognize only
the same immutable receipt; a missing or changed join refuses. Claims persist
through CAS/open uncertainty and are never rolled back. A genuinely claimless
read-only target has null adoption fields and target claim digest, with no
synthetic CAS. Incompatible isolated-child multi-transfer remains unsupported;
this publication boundary adds no transfer mechanics or production
provider/proof.

`rebind` is not a supported ctx policy. No old native task may be retargeted to
a new parent, and a read-only parent does not transfer or erase a writable
child's claim. Any claim transfer for a writable fresh coordinator is one
atomic replacement after old-process exclusion; there is no unclaimed gap.

`handoff` is a distinct user-only, record-only operation. The caller supplies
an explicit checkpoint reference; the controller records that reference and
does not pause, restart, change account/UUID/process, alter claims, or release
work. Swap never writes a handoff or generated checkpoint. A handoff record is
not evidence of a child stop, restart, or exact continuation.

## Claims and dispatch boundary

The claim owner is the coordinator execution lineage, not an individual child.
The lineage claims its workspace whenever any member may write, including a
read-only parent with a writable native child. Native children working in that
workspace inherit the lineage claim. A genuinely isolated native child
worktree may carry one additional exact claim, but it is still owned by the
lineage and indexed globally across managed lanes. Equal paths, realpath
aliases, and ancestor/descendant paths conflict; dirty or untracked content is
not itself a conflict. Claims remain held while any writer, detached effect,
or ownership evidence is unknown.

There is no per-child mailbox. Explicit user/coordinator input is addressed to
the coordinator's durable dispatch ledger and remains fenced/queued until the
matching release. Before a coordinator send, the dispatch intent is persisted
and the runtime acknowledgement must carry the same message/instruction ID.
An acknowledgement of acceptance is not turn completion. A possibly sent
unacknowledged item is `uncertain` and is never resent automatically; only the
exact private native-reservation no-send status receipt below may return an
already-committed reservation to the normal released pump. No operation may
deliver to an untracked native child or use a fictitious child account/session.

A child-targeted item has two deliberately separate identities:

- `native_target` is the semantic child the item requests. It is resolved from
  the durable, joined, current-run native ledger and binds the current
  `lineage_id`, coordinator session, actual `agent_id`, actual `task_id` when
  the runtime supplies one, the child-run incarnation (parent invocation or
  `tool_use_id` plus event watermark), and the immutable definition/permission
  binding. A caller-supplied agent or task name is never authority for this
  resolution.
- `physical_recipient` is the coordinator participant/session and its mailbox
  through which the runtime may carry the item. It is a transport recipient,
  not a child session or child mailbox, and it never changes the semantic
  target.

The canonical `request_content_digest` is computed from caller semantics before
any mutable target lookup: the requested child selector/task, `payload_ref`,
sender, and generation (plus the operation's other immutable caller fields).
It does not include a resolved target, physical recipient, generated mailbox,
route, or mutable policy. An exact retry of an already accepted request checks
this digest before resolving the current target and observes/reconciles the
existing durable result without another send. Reusing the request ID with
changed caller semantics or a stale generation refuses.

The first acceptance atomically persists both `request_content_digest` and a
separate `routing_binding_digest`. The latter covers the resolved
`native_target`, joined-ledger identity/watermark, `physical_recipient`,
generated mailbox, actual route, and effective policy, and is stored with the
dispatch intent. Before dispatch, the controller verifies that routing digest
and all of its bindings. While the lane is held, the item, caller digest, and
any accepted routing binding remain durably pending; holding does not drop the
item or defer target resolution to a mutable caller name.

After every runtime await, and again immediately before send, the controller
reloads and validates the operation/generation, the joined current-run target,
its effective definition and permissions, the current coordinator parent
session/invocation, the physical recipient/mailbox, and the pinned route
capability. An unknown, stale, reused, completed, or differently parented
agent/task/incarnation, or any changed permission/definition binding, refuses
the dispatch and retains the pending item. It is never silently retargeted
across `ctx`, a completed child, or a restarted/new-lineage child. A target
change can proceed only through an explicitly recorded reconciliation that
closes or preserves the old intent and creates a new request ID, caller-
semantic content digest, routing binding digest, and dispatch intent; it never
overwrites an accepted request digest.

Child delivery is acknowledged only by native evidence correlated to the exact
mailbox/message, the complete `native_target`, the actual native route, and the
current coordinator parent invocation and event watermark. A generic parent
`accepted-send` acknowledgement remains transport acceptance only; it is not
child delivery, child progress, or a restart result.

### Active-child routing and terminal invocation rollover

After explicit `release`, a pinned runtime may provide a supported route to a
currently active native child through the coordinator/native interface. That
active-child route is a separate capability and transaction from the full
terminal coordinator invocation A-to-B rollover below: it does not require A to
be terminal and it does not create a child mailbox, child session, or top-level
SDK path. The existing `prepare-invocation` reservation interface and its
full-terminal A-to-B rules remain unchanged and are not reused as an active
child route.

If the pinned capability does not provide identity-bound active-child routing
and correlated acknowledgement, the item is recorded as unsupported while its
pending queue entry is preserved. The controller does not imitate the route
with a prompt, a generic parent acceptance, or an unrelated top-level session.

### Released coordinator invocation rollover

A released operation may admit a later coordinator invocation on the same
runner only after the prior invocation is conclusively terminal: current
tasks, tools, effects, and the parent turn have authoritative terminal or
reconciled evidence, with no unknown work remaining. This is an internal
same-runner transition, not a new coordinator `open`, `release`, operation, or
lineage. The operation ID, owner generation, lineage ID/generation,
coordinator session, runner incarnation, immutable definitions, effective
permissions, and workspace/claim identity must match exactly. A disagreement
is refused before consuming mail.

The daemon-owned pump performs one bounded rollover in this order:

1. select one durable mailbox and persist an early mutable rollover
   **preparation intent**. This controller record is not a runtime-issued
   reservation and does not authorize a send;
2. outside the controller lock, after checking the released phase and daemon
   incarnation, obtain the bounded runtime `prepare-invocation` reservation
   and conclusive terminal proof for invocation A;
3. under one atomic controller transaction, recheck the released phase,
   daemon incarnation, operation/generation, and all identity/claim bindings,
   then persist A's immutable terminal history, B's current invocation
   context, B's startup binding, the exact runtime-reservation binding, and
   B's dispatch intent in the same snapshot; and
4. immediately before send, recheck the released phase, daemon incarnation,
   operation/generation, current B invocation/watermark, mailbox, claim, and
   committed reservation. Consume that exact reservation and attempt the
   selected B mailbox with no later intent creation. A normal successful
   delivery occurs once; retries and recovery are at-most-once, with the
   acknowledgement correlated to B and that mailbox.

Every runtime await is followed by a released-phase and daemon-incarnation
recheck, and the same checks occur immediately before send. Each durable
boundary also rechecks all identity and claim bindings, the current
invocation and strict event watermark, mailbox state, preparation intent, and
runtime reservation. A busy or non-terminal A leaves B queued or pending and
does not open, release, consume, or send. A lost reservation, identity
disagreement, or ambiguous send preserves the mutable preparation/binding
record and uncertainty for recovery; it never resets, reopens, creates a
later intent, or replays the item. The daemon owns this pump, and no
controller/state lock is held across a runtime await.

#### Native reservation no-send reconciliation

Native dispatch recovery does not accept a public `transport_proof`, a
`no_send`/`not_sent` boolean, a string status, or an ad-hoc
`send_occurred: false` mapping. Such values are refused for native rollover
and cannot clear uncertainty. The controller uses only the existing
authenticated, correlated `runtime.status(participant)` path and the private
`status.evidence.native_reservation_no_send` receipt defined in
[runner-evidence.md](runner-evidence.md). A null or absent receipt preserves
the recorded negative/unknown state; it is not a no-send result, and recovery
does not perform a direct recovery query. The durable rollover may carry the
optional sibling `native_reservation_no_send_consumption`, exactly
`{observation_id: str, receipt_digest: sha256, mailbox_id: str,
consumed: true}`. Its observation and receipt digest must match the positive
receipt and its mailbox must be the immutable B/`next_mailbox_id`; a partial
pair, null/non-literal-true value, mismatch, or extra field refuses. A
legacy absent/null receipt retains an absent sibling without defaults.

For a pending preparation or an uncertain/dispatch-pending native rollover,
the controller captures the exact durable preparation or committed binding,
operation/generation, owner/daemon, runner, claim, current context, immutable
A history, and unconsumed version-1 reservation under the state lock. It then
awaits one fresh owned status observation outside that lock. After the
correlated response, it rechecks every captured binding and the SDK's local
reservation/transport continuity before accepting the receipt. A reused
receipt, stale or conflicting reservation, changed invocation, new runner or
connection, lost owner continuity, queued/in-flight B work, or any attempted
or ambiguous B leaves the item uncertain and never requeues it.

Only an exact receipt and its exact consumption sibling can be persisted,
with their canonical reservation/receipt digests and one-time
reconciliation/consumption record, before a requeue decision. The pair and
the exact B queue transition are one atomic transaction; a pending preparation
may then commit only its already-existing complete reservation through the
ordinary history/binding validator. A committed binding may return only its
exact B mailbox to `queued` and its rollover to `send-pending`. This grants at
most one requeue for the logical rollover: duplicate recovery while that B
remains queued is read-only, and once normal dispatch begins no later receipt,
fresh observation, or ambiguous outcome can requeue it. Recovery creates no
replacement reservation, B query/control-frame, or send. The normal released
daemon pump alone later consumes the exact reservation and attempts the send
after fresh fences. No receipt or consumption marker is evicted or replayed,
and unknown evidence never becomes a successful no-send claim.

### Internal workspace-claim compare-and-swap prerequisite

The bounded state-store prerequisite is
`transfer_lineage_workspace_claim(expected_claim, *, target_lineage_id,
target_coordinator_session_uuid, target_lineage_generation,
expected_daemon_id, authoritative)`.
It is not a public operation and is not wired into native `ctx` in this slice.
The trusted controller must first prove old-writer exclusion and resolved
effects; the `authoritative` argument is a caller precondition, not runtime
evidence that the store can manufacture.

Under the existing exclusive global lock, the store requires the complete
expected source claim to match one validated active workspace row and the
current managed owner generation and explicitly expected daemon identity.
Same-generation daemon takeover invalidates the old caller's compare-and-swap.
Owner/generation/recovery records must be consistent, and a pending owner
recovery transaction refuses before any transfer journal or index write.
The source must include its coordinator identity; an unbound workspace claim
is insufficient for this transfer even though other claim APIs permit it.
The replacement has a different lineage
and coordinator identity and the next lineage generation, while retaining
lane, host, workspace, repository/common-directory identity, owner generation,
and parent policy. Missing, duplicate, stale, or changed source claims refuse.
Retained isolated child claims, a target-identity collision, or any conflicting
path/alias/ancestor claim also refuse without releasing anything. An owner
record pinned to identities that this single-index primitive cannot update
atomically refuses; it is never silently made inconsistent.
Target lineage or coordinator identity already present in any active claim
refuses independently, including a disjoint path or a different identity pair.

The store journals bounded source/target intent before replacing the single
claim-index row in one atomic write, followed by a result journal entry.
Unrelated rows and owner/controller records are untouched, and the existing
claim schema is unchanged. Before the index replacement, the source still
owns the workspace; after it, the target does. A journal or acknowledgement
failure must not remove the remaining claim or roll back into an ownership
gap. The index, not an intent or receipt alone, identifies the current holder.
Repeating the old compare-and-swap after replacement refuses, including after
a lost acknowledgement; no automatic retry or successful recovery is implied.

Controller adoption, crash reconciliation across controller/claim records,
retention of old native task history, and transfers involving child claims
remain later work. This primitive does not close native ctx acceptance.

Stable refusal classes include `invalid`, `unknown`, `busy`,
`ownership-conflict`, `profile-mismatch`, `account-mismatch`,
`permission-mismatch`, `unsupported`, `startup-orphan`, `loader-failed`,
`uncertain-effect`, `schema-mismatch`, `migration-required`, and
`stale-generation`. Any unknown helper result, malformed/oversized frame,
foreign process domain, missing lifecycle/tool/effect evidence, or ambiguous
restart is fail-closed.
