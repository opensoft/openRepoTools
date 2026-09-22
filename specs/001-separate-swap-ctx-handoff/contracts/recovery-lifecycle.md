# Native-Lineage Recovery and Lifecycle Contract

Mode scope: [stop-then-resume-v1](stop-then-resume.md) requires recovery to route
by its stored discriminator and never create a target before explicit release.
Held-target/six-stage recovery below remains strict mode. Omitted markers and
old records never opt into v1. All shared ownership/no-replay safeguards apply.

Recovery reconciles one recorded coordinator execution lineage. It never
turns a failed operation into a swap, invents a child runner, or treats the
absence of a supervisor as proof that the native graph stopped. This contract
uses `schema_version: 2` and architecture `native-coordinator-lineage`, as
defined by [managed control](managed-control.md).

## Evidence that recovery may trust

The durable coordinator identity is the tuple of exact native session UUID,
validated transcript/store, canonical profile and expected account email,
actual initialization account and permission mode, launch/settings fingerprint,
workspace, and runtime process PID, process-group ID, start token, and process
domain. The control-service PID is a different process incarnation. A
replacement control service may adopt a live coordinator only after the whole
tuple and the ownership lock match; it must not open a second coordinator.

Each native child is joined from actual runtime records/events to its
coordinator parent, durable admission, current parent invocation, and an event
watermark. `SubagentStart`/`SubagentStop`, task events, session history, and
tool hooks do not all carry the same fields. The adapter uses only fields the
selected runtime emits: `SubagentStart`/`SubagentStop` carry agent ID/type and
base session/transcript/cwd facts (stop also carries transcript-path and
stop-hook state), while task events carry task ID/session/UUID and may carry a
tool-use ID. Tool hooks carry tool-use ID and may carry agent ID/type; no event
shape is padded with a fabricated task, tool, or parent-agent field. Session
history may supply parent metadata. An absent or ambiguous parent/task/tool
join is `unresolved`. A reused `agent_id`, stale terminal marker, old
watermark, parent exit, `PostToolUse(Agent)`, or a completed parent tool call
never proves the current child invocation stopped or completed.

Only after Gate0 independently proves the exact stream-json non-auto mode,
quiescence is based on current-run native child and tracked-tool events, not a
classifier-marker write. Stream-json selection or the `print.ts` callback is
not that proof; the callback is void and is not readiness, stop, or completion
evidence.
Unknown descendants, detached effects, foreign process domains, and missing
tool-end facts retain the fence, claim, and uncertainty.

## Gate0: startup and orphan behavior

No child state may be inferred before the matching operation is released. A
runtime is eligible for model-independent control only after an actual Gate0
probe establishes all of the following for the exact configuration selected:

1. Promptless coordinator initialization is held before any model query or
   native child admission.
2. The adapter records the exact SDK-selected CLI path, version, complete
   SHA-256 digest, and stream-json mode, and uses a no-auth orphan fixture to
   exercise the selected binary's restored-worker path. The positive orphan
   fixture must exercise `running_background_tasks` -> `restoredOrphans` -> a
   default-enabled wake -> `enqueuePendingNotification`; record that enqueue
   separately from an actual model-dispatch event. This fixture is not required
   to be silent: queueing a pending notification is not itself model dispatch.
   Stream-json or a `print` callback alone is not a non-auto proof. The current
   local observation is SDK 0.2.153 selecting that bundled CLI with SHA-256
   `6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`;
   this is probe evidence, not a portable support claim.
3. The terminal-cleared production candidate is observed through the
   supported runtime only: terminal-stop current native children/tools and
   prove durable worker-state clearing without editing transcripts. Its target
   held startup must then prove no pre-query wake and no model dispatch. Gate0
   passes only for an exact selected mode/configuration with that evidence.
4. Interactive takeover is tested separately because it may auto-resume a
   native orphan before a prompt. If the selected path can do that and has no
   supported hold boundary, it is `startup-orphan`/`unsupported` before source
   shutdown.
5. Parent admission, native child admission, and tracked-tool dispatch remain
   fenced until explicit `release`.

Gate0 failure is a refusal, not an empty child roster. A promptless parent
`init`, idle status, process suspension, or startup success cannot prove that
children did not run. Once Gate0 is proven, recovery still uses current-run
events and exact watermarks; it does not create a marker to classify a stale
event. The same gate applies to nested children and to every target runtime
opened after a swap or `ctx`.

For a source transition, the control phase must terminal-stop every current
native child and tracked tool, prove that durable current worker state has
been cleared through the supported runtime without editing transcripts, and
only then connect the exact target coordinator in held mode. Target startup
must show no restored orphan, pre-query wake, or model request before release.
If any of those proofs is missing, recovery leaves the fence and claims in
place and refuses; `stream-json`, `print`, or an acknowledged stop alone
cannot substitute for terminal-stop/state-clear/no-wake evidence. The positive
orphan fixture above is intentionally different: its enqueue event is recorded
and distinguished from actual model dispatch rather than required to be
silent.

## Native swap evidence during recovery

The private constructor-only `_native_swap_evidence_provider(binding)` is
optional and defaults to absent (`None`). Recovery never enables it through a
public request, boolean, stored flag, or caller assertion. When present, it is
a synchronous read-only observation seam and can supply only the missing
continuous request-epoch or supported worker-state-clear fact. It cannot
interrupt, stop a native member/tool, exclude a process/effect, open or ready
a target, release a coordinator, or mutate runtime state. The exact binding
and response shapes are the `NativeSwapEvidence` shapes in
[the data model](../data-model.md): the binding carries schema 2,
`native-swap-evidence-request`, one of `entry|graph-drained|source-excluded|target-held|pre-release|release-boundary`,
operation/owner/daemon identity, strict `_native_source_identity`, source
and the stage-appropriate interrupt/archive/target-runner/release identities,
including the exact SDK release-boundary binding. Null identities are allowed
only before that identity exists and become immutable once bound.

Recovery validates that the response echoes the binding exactly, that its
runtime identity digest is the selected pinned runtime identity and is stable
across stages, and that source context/claim and target-spec digests match the
immutable records. Its request observation must use the same epoch and stable
entry reference with `observable: true`, `continuous: true`, and
`new_requests: 0` through the requested stage. `pre-release` follows the
durable release intent and precedes the native release call, including its
bounded idle delay. `release-boundary` observes the same historical interval
through the synchronous held-to-released gate event, and later requests are
outside that endpoint. `worker_state_clear` is null only at `entry`; later stages require the current source/interrupt identity,
supported pinned method, current correlated watermark, and `cleared: true`.
Positive, unknown, and gap observations are sticky, so a later zero does not
repair an earlier unsafe interval. Provider evidence is not a capability
certificate and never replaces actual interrupt, native-member, tool, effect,
process-exclusion, or target-open/ready facts.

The six observations map to the durable swap windows: `entry` with static
capability preflight; `graph-drained` after authoritative native graph
quiescence and clear evidence; `source-excluded` after a persisted shutdown
intent, at-most-once supported shutdown, and process exclusion; and
`target-held` after one dedicated target preparation, one held exact-UUID open,
and actual readiness; target preparation persists the new runner's exact
resume/open specification and intent; `pre-release` after the durable release intent and before
the native release call; and `release-boundary` at the SDK's synchronous
held-to-released gate event. Native swap retains the same coordinator UUID,
lineage, lineage generation, claim, and owner generation while using a new
target runner incarnation. Its immutable source archive remains until atomic
target activation; retries reuse that archive and never recapture a changed
snapshot.
The `native_adoption` CAS is not a swap recovery mechanism because its strict
claim-pair helper is for `ctx`'s new lineage/new UUID.

Recovery reconciles each durable stage window without issuing a replacement
runtime action. A possible interrupt, shutdown, open, or send is never
automatically replayed or queried, and is never followed by release. A
`target-held` snapshot alone does
not prove the zero-request interval through a later release: native swap
requires the fresh same-epoch `pre-release` observation and the new bound
`release-boundary` receipt. If final proof is missing or contradictory,
recovery records any receipt and uncertain effect, retains claims, and performs
no pump or replay; it does not claim the runtime is still held after an
acknowledged release gate. The backward-compatible `runtime.release` endpoint
for other operations is not a native-swap fallback. A fake constructor
provider is offline test evidence only and does not establish production
support.

## Recovery by operation

Coordinator-wide interrupt recovery additionally follows
[coordinator-interrupt.md](coordinator-interrupt.md). Its sealed native roster,
source-run/fence exclusion, possible-send intent, independent receipt/drain
facts and uninterrupted request-observation epoch survive controller takeover.
Recovery never creates a new interrupt authorization by changing an operation
or request ID. A gap in runtime evidence is uncertainty, not evidence of no
call, no request, complete drain or a released claim.

The operation ID and generation are monotonic. A retry reloads the durable
record, rechecks the exact owner and generation after every runtime await, and
advances only when the required evidence is present.

| Operation | Facts that must survive a crash | Recovery conclusion |
| --- | --- | --- |
| `start` | Owner reservation, coordinator UUID/open intent, profile, workspace, Gate0 result, and any exact coordinator process identity. | Adopt the exact recorded coordinator if process/account/UUID evidence matches and keep it `ready-held`; otherwise remain held/indeterminate. Never infer or open children. |
| `fence` | Admission fence, seal watermark, roster, parent stop boundary, and all child/tool/effect uncertainty. | Keep admission closed. Reconcile current coordinator and native events; a racing task is rejected or retained only with its actual IDs. |
| `swap` | Source/target profiles, source coordinator UUID/process, sealed ledger, terminal child stop and durable worker-state clear, old-group exclusion, target open intent, target coordinator evidence, and the immutable request epoch plus append-only `entry`/`graph-drained`/`source-excluded`/`target-held`/`pre-release`/`release-boundary` records. | Reconcile the exact stage and prove old coordinator/process exclusion and target no-wake/no-model behavior before target activation. Open no child; safely stopped exact candidates remain `resume-pending` until post-release correlated events, otherwise `restart-pending`. Retain the source archive and same UUID/lineage/claim/owner generation; never use `native_adoption` CAS, fall back to source account, or release without the new bound receipt. |
| `release` | One coordinator release intent/receipt, native-swap `release_id`/intent digest, pre-release observation, exact SDK gate binding/event/watermark, and any one restart dispatch intent/ack. | For native swap, reconcile the pre-release and release-boundary records through the synchronous held-to-released endpoint. Missing or contradictory final proof records any receipt plus uncertain effect, retains claims, and performs no pump/replay; an acknowledged gate is not reported as still held. Other operations may use the backward-compatible release endpoint, but it is not a native-swap fallback. |
| `recover` | Recovery claimant identity, ownership CAS, prior operation history, roster, claims, and all unresolved intents/effects. | Replace only the dead control-service incarnation after exact exclusion; preserve the lineage and perform no implicit open, send, release, or child restart. |
| `status` | No mutation is permitted. | Read and report the durable facts and fresh read-only evidence; unknown remains unknown. |
| `shutdown` | Fence, coordinator stop intent, child/tool lifecycle events, process-group exclusion, detached-effect outcomes, and claims. | Keep owner/claims/control endpoint until all controlled writers and effects are authoritative. A parent exit alone does not complete shutdown. |
| `unenroll` | Exact quiescence, process/effect exclusion, helper projection result, and claim-removal intent. | Remove ownership only after the exact atomic proof; otherwise retain a recoverable intent and refuse. Never start a runtime. |
| `ctx hold` | Old coordinator exclusion, caller checkpoint reference, retained native child records/claims, and fresh coordinator open intent. | Keep old native workers stopped/retained under their old parent (without promising they survive parent shutdown); adopt only the exact fresh coordinator, held. No cross-parent child rebind. |
| `ctx restart` | Caller checkpoint, old lineage exclusion, new `lineage_id` and coordinator UUID, unchanged durable lane-owner generation, fresh coordinator identity, and post-release restart intent. | The new lineage is held until release while the durable lane owner generation remains unchanged; that owner generation advances only on unenrollment followed by re-enrollment. Correlate only new native task events after release; never exact-rebind an old child or replay a partial restart. |
| `handoff` | Caller-supplied checkpoint reference and record-only request digest. | Reconcile the record without changing account, process, UUID, claims, release, or child state. It is not a recovery gate for swap. |

`ready-held` is not `released`. If any coordinator, child, tool, process, or
effect fact needed for a transition is missing, the operation remains paused or
indeterminate. Recovery never repairs uncertainty by declaring a child
completed, stopping a writer, or sending a prompt.

## Coordinator and native-child lifecycle

There is one coordinator control path for `start`, `fence`, `swap`, `release`,
`shutdown`, and `status`; native child lifecycle is observed through that
coordinator's runtime stream. No child receives an SDK `open`, `shutdown`, or
`release` call. A runtime-tracked background child may be stopped only through
the supported parent boundary and only when its native stop/effect evidence is
available. A `run_in_background` flag does not make a child tracked.

Teams are a separate native capability. Recovery does not fold a team member
into the Agent/Task ledger, claim team support from an Agent/Task test, or
restart an unverified team. An unmanaged shell, `setsid`, `nohup`, arbitrary
detached descendant, or remote mutation remains a detached effect and must be
excluded or resolved independently.

For every unfinished child, recovery preserves the final status:
`exact-resumed`, `restart-pending`, `restarted`, or `unresolved`. Before
release, a safely stopped exact-continuation candidate may be shown as the
interim `resume-pending` state; it is not `exact-resumed` without a
post-release current-run event. An authoritative `completed` child stays
completed. In particular, a child that outlives the `Agent` launch tool
remains active until its own current-run native lifecycle and tool/effect
evidence ends.

## Release and restart crash rules

The coordinator release is the sole transition from model-independent control
to normal inference. Its intent is durable before the runtime call and can be
consumed at most once for the operation/generation. An accepted release result
does not complete a turn and does not prove child restart. Post-release model
usage is normal runtime use and is reported separately from account control.

After release, a `resume-pending` child may become `exact-resumed` only from a
correlated native continuation event for the current invocation. It cannot be
called exact-resumed while held.

After release, the controller may persist one mechanically composed restart
instruction for the unfinished native children. It contains durable child
agent/task IDs, their statuses, one restart-attempt ID, and the requested task
action; it contains no generated summary, semantic handoff, or new checkpoint.
The instruction is sent only through the coordinator/native interface. Its
transport acknowledgement is correlated to the exact instruction ID but means
only `accepted-send`.

Recovery handles the instruction as follows:

- no instruction is retried when a send may have occurred without an
  acknowledgement;
- an accepted instruction with no correlated `SubagentStart`/task event is
  `unresolved`, not `restarted`;
- a new task is `restarted` only when its actual event joins to the released
  coordinator parent, current invocation, old child ID, restart attempt,
  immutable definition, effective permissions, tool/process facts, and a
  current watermark;
- after a crash or timeout that starts only some requested children, known
  tasks and their statuses are retained, while the rest remain
  `restart-pending` or `unresolved`; and
- retry reconciles all existing task events and never replays the release,
  instruction, completed child, uncertain effect, or external action.

The only exception is a durable `pending` intent for which the controller can
prove that no runtime call or send was issued. That intent may be attempted
once under the same operation identity. `in-progress`, `accepted`, and
`uncertain` intents require fresh evidence, not another call.

For native swap, the durable release intent binds `release_id` and
`release_intent_digest`. The controller obtains `pre-release` after that write
and before the native release call, including its bounded idle delay. The SDK
must emit an exact bound held-to-released gate event synchronously; the
`release-boundary` provider observation proves the historical epoch through
that endpoint, while the receipt is only ordering/correlation evidence. The
controller cannot mark the operation `released` or start a daemon pump without
that new bound receipt. If the call or gate may have crossed and the final
proof is missing or contradictory, recovery retains the receipt/uncertain
effect and claims and performs no release replay, query, or pump. It must not
claim the runtime is still held after an acknowledged gate. The
backward-compatible release endpoint used by other operations is not a
native-swap fallback.

### Same-runner invocation rollover crash boundaries

The rollover has four separately recoverable stages:

1. If a crash occurs before the mutable preparation intent is durable,
   recovery reconciles only the local precommit marker under the controller
   lock; it performs no runtime query, reservation, model query, or send. If
   the preparation intent is durable but no runtime reservation is recorded,
   recovery may use only a bounded observational adapter reconciliation of the
   exact reservation. It never issues a model query or creates a replacement
   reservation.
2. If the runtime reservation is durable but the atomic A-history/B-binding
   snapshot is not, recovery may proceed only when it proves no send occurred
   and the exact reservation, released phase, daemon incarnation, operation,
   runner, and current authority are still valid. It may complete that exact
   binding or clear a proven-unused preparation; it does not query the model,
   reopen the coordinator, or create a replacement reservation.
3. If the atomic binding is durable but the send has not crossed its dispatch
   boundary, recovery again requires proven no-send plus the currently valid
   exact reservation and authority. It may return that exact, proven-unsent
   committed dispatch to the normal released daemon pump; the pump, not
   recovery, consumes the committed reservation and attempts the already-
   authorized send at most once after fresh authority and reservation checks.
   No later intent is created. A runtime status/acceptance sample or parent
   receipt is not proof of terminality or no-send.
4. If a send may have crossed the runtime boundary, the runtime disagrees
   with the reservation, the reservation is lost, the daemon/runner changes,
   or any evidence is missing or contradictory, recovery annotates the
   mutable rollover record `uncertain` (or its durable unresolved equivalent).
   It does not resend, reset, reopen, or release. Explicit reconciliation must
   establish a proven no-send result or a correlated accepted result before
   any later action. A stale callback from invocation A cannot complete B
   because its identity or watermark is fenced.

The reconciliation itself is model-free: only the bounded observational
adapter control may inspect an exact existing reservation. It may return an
exact, proven-unsent committed dispatch to the normal released daemon pump,
which performs the already-authorized send at most once only after fresh
released-phase, daemon-incarnation, operation, binding, and reservation
checks. Recovery itself never independently issues or replays a model query.
The immutable A history and its terminal proof remain unchanged in every crash
outcome; uncertainty belongs only to the mutable preparation/binding or
dispatch record.

`NativeSourceArchive` is unsuitable for this boundary: it is a mechanical
source snapshot for adoption/history and does not prove a live runtime
reservation, terminal invocation, send crossing, or same-runner binding.

`ctx hold` never releases retained native workers. `ctx restart` creates a new
`lineage_id` and coordinator UUID from the caller-supplied checkpoint while
leaving the durable lane owner generation unchanged; that owner generation
advances only on unenrollment followed by re-enrollment. Only after its
explicit release may the one mechanical instruction request new native child
tasks. The old task's parent remains immutable: cross-parent exact rebind is
never a recovery action. A new task is not proof of the old conversation or
identity.

## Claims and quiescence

The exclusive claim belongs to the coordinator execution lineage. Claim the
lineage workspace whenever any member may write, including a read-only parent
with a writable native child. Children in that workspace inherit the lineage
claim. A genuinely isolated child worktree may have an additional exact claim,
but it is indexed under the same lineage in the host/workspace-global
exclusion index. Equal real paths, symlink aliases, and ancestor/descendant
worktrees conflict across lineages. Dirty and untracked files are preserved
and are not an ownership conflict.

Recovery never releases a claim merely because a child or control service PID
is absent. Release requires authoritative native participant/tool quiescence,
process-group exclusion in the matching process domain, and no unresolved
detached effect. For a `ctx` writable-coordinator replacement, transfer the
claim in one durable atomic replacement after old-process exclusion; do not
write a release followed by a later acquire.

## Dead-supervisor bootstrap and unenrollment

When the control socket is unavailable, a replacement supervisor first reads
the exact durable owner and recorded control-service process identity. It
observes that process in its recorded host/PID namespace and serializes
contenders under the ownership lock. Missing endpoint, foreign namespace, PID
reuse, or failed observation is unknown, not death. A live or unknown old
service refuses takeover.

After exact exclusion, the replacement records its own process incarnation
before publishing an endpoint and preserves owner, generation, coordinator
UUID/process, child ledger, operation/request intents, restart uncertainty,
claims, and registry projection. Bootstrap performs no open, prompt, release,
send, orphan resume, or child termination. The next explicit `recover` applies
the operation table above.

Only successful `unenroll` clears the managed projection and global claims,
after all controlled native children/tools and the coordinator are quiescent
and all detached effects are resolved. A helper refusal, unknown child, stale
event, or unresolved send keeps the control service available. The generation
tombstone survives removal, so old requests cannot attach to a new enrollment.
