# Native Coordinator / Child Transcript Preflight Contract

Mode scope: [stop-then-resume-v1](stop-then-resume.md) preserves and revalidates
exact history before release but loads it only after release authorization.
The pre-release loaded-and-held/orphan-clear requirements below remain strict
mode. Transcript presence alone grants neither v1 readiness nor child recovery.

The profile resolver supplies read-only profile, transcript, native-child, and
process facts. The controller decides whether those facts authorize a
lifecycle transition. Neither public request fields nor a `trusted: true`
flag confer authority. Transcript presence by itself is not proof that a
native child can be continued.

For the selected coordinator-wide cancellation candidate,
[coordinator-interrupt.md](coordinator-interrupt.md) supplies the separate
source-run authorization and drain contract. Transcript preflight does not
authorize an interrupt, certify child quiescence or make externally cancelled
children exact-resumable. Its actual-account/runtime checks still precede
disruption; the scripted Stage 1 gateway observations do not satisfy them.

## Exact dependency boundary

The controller accepts this injected callable for the coordinator:

```python
transcript_verifier(profile_name, session_id, workspace)
```

The production daemon binds it exactly as follows:

```python
profiles.verify_transcript(profiles.resolve(profile_name), session_id, workspace)
```

`ProfileResolver.verify_transcript` retains its exact existing signature with
a resolved `ProfileReference`. Tests inject the same callable. There is no
second state-store verifier and no guessed method name or signature.

The result retains these canonical fields:

`profile`, `session_id`, `workspace`, `transcript_store`,
`transcript_project`, `transcript`, `holders`, `unknown_holders`, and
`ambiguous`.

For a native coordinator lineage it additionally supplies bounded,
read-only records under `native_children`, `child_transcript_stores`, and
`runtime_capabilities`. These additions do not turn a child into a separate
top-level session. `session_id` and holder process identity in the canonical
result refer to the coordinator unless a field explicitly says otherwise.

## Coordinator identity and holder checks

The requested profile identity must match the resolver's canonical profile,
expected account identity, storage family, and configuration directory. The
coordinator transcript check binds the exact native coordinator `session_id`
to its workspace and transcript store. The target profile may use another
configuration directory, but it must resolve the same supported transcript
storage and account relationship before shutdown is planned.

For a coordinator holder, compare the exact session, workspace, process
start identity, current process domain, and containing process-tree evidence.
The native runtime's process-domain value is an opaque whole value: compare it
with a freshly observed local value and do not split it on assumed delimiters.
A numeric PID that exists in another process domain is unknown, whether or not
its start token happens to match. A missing or unrecognized domain cannot prove
that a holder is stale or absent.

The native child has no independent transcript session UUID or process-group
identity in this contract. Its holder/process evidence is linked to the
coordinator's containing process tree and to native event records by
`agent_id`, `task_id`, `tool_use_id`, and parent linkage. Never require a
fabricated child `session_id` or child `process_group_id` to pass preflight.

## Native child record validation

Every child admitted to the sealed lineage must have a correlated native
record containing:

- `agent_id` captured from `SubagentStart` or another authoritative runtime
  record;
- `task_id` only when supplied by a correlated native task event or
  authoritative native task record, exact `type`, and direct parent linkage to
  the coordinator (or a captured parent `agent_id`/`task_id` for nesting);
- the creating/addressing `tool_use_id` joined from a tool hook, task-start
  event, or session history when the runtime provides one;
- a transcript/task record reference and the canonical store identity;
- current `status` and `stop_provenance` from the lifecycle ledger;
- observed `model` and `effort`; and
- the immutable custom-agent definition identity/digest, effective tools,
  permissions, writable paths, and hook-policy facts for this exact
  `agent_id`.

The verifier compares native IDs and links exactly; it does not derive a
child from a display name, task text, timing, filesystem path, or parent
read-only flag. A hook or tool event without `agent_id` is not child evidence.
An unknown child, duplicate `agent_id` within one current child-run
incarnation, reused `task_id` without a new parent invocation/watermark,
missing parent link, contradictory definition, or ambiguous tool correlation
is an unknown holder or admission refusal. Reuse of an agent ID across
resumptions is permitted only when the new incarnation tuple is proven.

The measured SDK event fields are narrower than the durable child record.
`SubagentStart` carries `session_id`, `transcript_path`, `cwd`, optional
`permission_mode`, `agent_id`, and `agent_type`; `SubagentStop` adds
`stop_hook_active` and `agent_transcript_path`. Neither event supplies
`task_id`, `tool_use_id`, or `parent_agent_id`. Tool hooks carry
`tool_use_id` and may carry `agent_id`/type. `TaskStarted`, `TaskProgress`, and
`TaskNotification` carry `task_id`, `session_id`, event `uuid`, optional
`tool_use_id`, and (for `TaskStarted`) `task_type`; `TaskUpdated` carries
`task_id`, `status`, `patch`, and optional `session_id`/event `uuid`, but no
`tool_use_id`. Session history metadata may supply `parent_tool_use_id` and
`parent_agent_id`. The event `uuid` is transport correlation, never a child
session UUID. Join a durable pending `Agent` admission to these actual fields
using current parent invocation and a monotonic watermark. A pending admission
or history record can join an actual task ID but cannot create one. A missing
or ambiguous join, including nested-child parent linkage, remains unresolved;
no field is filled by inference.

`stop_provenance` is derived from a correlated controller/runtime origin
(model stop, user cancel, SDK cancel, parent shutdown, failure, process loss,
or unknown). `stop_hook_active` alone does not identify that origin or prove
quiescence.

An `agent_id` may be reused by the native runtime after a child resumes. The
record therefore also binds each event to the current task, direct parent
invocation/`tool_use_id`, and a monotonic event watermark. A completion
notification from an earlier watermark is stale and cannot mark the current
run complete. This correlation tuple is an incarnation record, not a child
UUID or process-group identity.

`PostToolUse(Agent)` closes only the Agent launch tool. It does not close the
native child record. The verifier requires the `SubagentStop` or authoritative
correlated task terminal evidence described in the runner contract; a child
that outlives its launch call remains active or unresolved.

## Phase-aware authorization

The controller applies different checks to fresh start, ordinary resume, and
account swap. All phases use the same canonical profile/transcript/holder
result and keep missing evidence fail-closed.

| Phase | Required coordinator evidence | Required native-child evidence |
| --- | --- | --- |
| Initial fresh start | A durably reserved, never-written fixed coordinator UUID and no live/unknown conflicting holder. | No child is preassigned a UUID. Every child created during startup must appear in the actual native start/task ledger before it can be admitted or write. |
| Initial coordinator resume | Exact persisted coordinator transcript, exact loader path, workspace/store match, and no conflicting live/unknown holder. | Existing child records are checked independently. Transcript presence alone does not authorize a child continuation. |
| Swap preflight | Exact enrolled source coordinator holder is allowed before source shutdown; target profile, account, store, and runtime capability pass before interruption. | Complete sealed native lineage is present. The source holder may be linked to the coordinator tree, but unknown/additional children refuse. Target child store and resumability are checked before old writers are stopped. |
| Ctx | Current account and exact supplied checkpoint; fresh coordinator UUID is reserved and held. | Existing children remain held unless the caller supplies an explicit supported policy. Ctx does not infer exact child rebind or restart from a transcript. |
| Handoff | Only the caller's explicit checkpoint reference is recorded. | No child stop, resume, account, or permission conclusion is made. Handoff is not swap evidence. |

Initial fresh start must not mistake an empty transcript for proof that a
previously used UUID was never written. Once the coordinator or a native child
has written, known history wins over stale reservation metadata; known-written
state never falls back to fresh launch.

For swap-only reserved-to-written promotion, the trusted canonical lookup
must report the same UUID with `exists=true`, `written=true` and
`reserved=false`, plus exactly one holder that passes all existing source
profile, workspace, identity and owned-process-group checks. A stored flag or
caller assertion is insufficient. Only that fully validated transition may
replace the inferred fresh target with an exact resume target; the target
specification must be recomputed/revalidated and persisted as `mode=resume`,
`resume=true`, without `fresh`, before any open. An explicitly requested fresh
fallback against written history still refuses. Initial fresh admission,
ambiguous/foreign/missing holder evidence and every other lifecycle keep their
existing refusal rules. A refusal cannot publish a partially promoted target.

## Cross-profile transcript and child stores

Profile-family equality is necessary but insufficient. Resolve and compare the
canonical coordinator transcript store, project/workspace identity, and every
native child store. A target profile may locate child records in a different
profile-specific store even when the family is shared. In that case exact
continuation is allowed only if the pinned runtime documents and the actual
preflight result prove a stable mapping from the source child record to the
target child record, preserving:

`parent session_id`, `agent_id`, `task_id` where supplied by an actual native
task event/record, `type`, `tool_use_id`, transcript record, status, stop
provenance, model, effort, custom definition, tools, and permissions.

If either profile's child store is missing, divergent, unreadable, or not
covered by the tested cross-profile runtime capability, the child is
`unresolved` or the configuration is `unsupported`; do not infer a shared
store from a family label, copy conversation bodies, or use a title/picker.
An exact coordinator resume cannot promote a child with an unresolved store.

## Permission and lineage-claim preflight

Permission evidence is per native identity. Hook/tool observations must bind
the exact `agent_id` to the immutable custom definition, effective permission
mode, allowed tools, writable paths, and the runtime's policy decision. A
parent `read_only` value does not make a child read-only. Conversely, a child
cannot receive broader parent permissions merely because its parent is
read-write or because the child asks for them.

If any coordinator or child may write, the coordinator execution lineage
claims the relevant canonical workspace/worktree before admission. Children
working in that workspace inherit the lineage's ownership—not an independent
top-level owner. An isolated child worktree needs its own path claim owned by
the same lineage and checked against the global equal/alias/
ancestor-descendant exclusion index. Claims remain held while any child,
tool, process, or external effect is uncertain.

An unknown child identity, missing custom definition, missing hook/tool
decision, or runtime that cannot enforce the child's distinct policy refuses
admission and keeps the lineage claim/fence. There is no safe inference from
the coordinator's `read_only` setting.

## Native lifecycle, stop provenance, and resumability

The verifier consumes the ledger fed by `SubagentStart`, `SubagentStop`,
`TaskStarted`/`task_started`, `TaskProgress`/`task_progress`/`progress`,
`TaskNotification`/`task_notification`/`notification`, and
`TaskUpdated`/`task_updated`. It separately checks the Agent tool's
`PreToolUse` and `PostToolUse` facts. The launch-tool end is never substituted
for child terminal state.

`resume-pending` is eligible while held only when safely stopped SOURCE
current-run evidence, exact target parent restoration, and the tested pinned
resumability capability all agree. The source child must have correlated
`SubagentStop` or authoritative task-terminal evidence for the current
invocation, terminal tracked tools, excluded source process containment, and
reconciled effects. The same coordinator parent must be restored by the exact
loader and kept held from inference; the captured `agent_id`, an actual
task-event/task-record `task_id`, parent linkage, definition, model/effort,
tools, permissions, and accessible child transcript/store must match. The
current invocation and monotonic watermark must match, and the pinned
runtime/version/platform capability must explicitly mark that stop provenance
resumable. A transcript or task file by itself is not that capability evidence.

No held/active child-continuation event is required or accepted before release.
After explicit release, and only then, a current correlated native lifecycle
event showing the child active under the same parent invocation and current
watermark changes `resume-pending` to `exact-resumed`. Same `agent_id` text
alone is insufficient.

Apply these stop outcomes without relabeling them:

| Observation | Preflight conclusion |
| --- | --- |
| Model-stopped child has safely stopped source evidence and the pinned capability says same-parent resume is supported | Eligible for `resume-pending` while held; after explicit release, a current correlated native continuation event changes it to `exact-resumed`. |
| User-cancelled or SDK-cancelled child | Exact continuation only if that exact provenance is documented and tested as resumable; otherwise `restart-pending` or `unresolved`. Do not assume a later parent prompt wakes it. |
| Parent process lost or in-process child state lost | A new parent process alone proves neither same parent nor child identity. Keep `unresolved` unless durable records and an actual pinned capability authorize a later new-run path. |
| New model-assisted child run | `restart-pending` before target readiness/release; `restarted` only after an explicit post-release instruction and correlated native task/start evidence. It is not exact identity. |
| Missing/contradictory event, transcript, store, policy, process, or effect | `unresolved`; retain claims and prevent release/replay. |

For a model-assisted restart, preserve the original child `agent_id` and
actual native task record as source lineage. If the runtime emits a new native
`agent_id`, record it as a new run linked to the original task; never overwrite
the old identity or call it exact. An inaccessible child transcript/store
blocks exact continuation, including `resume-pending`, but does not alone
block a safe `restart-pending` fallback when current-run stop/effect facts and
the original parent/native task record, model/effort, and custom definition are
recoverable. Unknown effects remain unresolved. An accepted send
acknowledgement is not proof that the child restarted.

## Startup orphan gate

Promptless coordinator initialization does not establish native orphan
handling. Gate0 must use a disposable native lineage on the exact selected SDK
and binary version/digest, runtime mode, platform, profile, and participant
kind. The positive fixture deliberately seeds a durable native parent/task
record and measures persisted-record load, notification enqueue, child/parent
wake, and model-query attempt as separate outcomes. It must distinguish
`enqueuePendingNotification`, a wake, and a model request; an eventual `idle`
result cannot collapse them into one outcome.

The target safety criterion is: after a supported source stop produces
terminal child/tool evidence and the old `running_background_tasks` state is
durably cleared, target connect with inference fenced shows terminal-cleared
state, no orphan restored, no orphan wake/notification, and no model query. A
held connection is not evidence of child continuation. Interactive takeover
and SDK `stream-json` are separate modes: interactive
takeover may expose an autoresume callback, while the `print.ts` path has no
autoresume callback. The target probe must use the exact selected
SDK/binary/version/digest and cannot be replaced by a fake callback or a
different executable. The measured candidate is SDK 0.2.153 selecting bundled
CLI 2.1.273; a separate CLI 2.1.270 trace is informative only, and the full
selected executable digest must be retained for each acceptance record. The
measured bundled digest was
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`; this is
probe evidence, not a portable support claim. If the selected mode is proven
non-auto-resuming, preflight instead requires direct current-run native
child/tool quiescence and containing-process exclusion. It does not require a
classifier marker solely to suppress an absent callback. A fake adapter,
synthetic `SubagentStart`, or promptless parent fixture cannot close the gate.
If the target criterion or applicable non-auto proof is absent, refuse the
configuration as `unsupported` and do not advertise a zero-model-inference
swap.

The selected 2.1.273 print/stream path may restore persisted
`running_background_tasks` into `restoredOrphans`; its default-enabled
`tengu_ccr_orphan_restore_wake` can call `enqueuePendingNotification` and
trigger inference before an external query. Preflight must therefore prove
terminal child/tool stop and durable clearing of the old running-task state,
then observe target connect with no orphan wake and no model request.
Stream-json/print mode alone is not evidence; absent that proof, refuse the
configuration as unsupported.

## Failure, retry, and privacy rules

Preflight runs before intentional shutdown whenever possible. If it fails,
the original coordinator/children remain running and no target launch occurs.
After a safe pause, a failed or partial target start retains one operation
identity and reconciles the coordinator process tree, native children, stores,
hooks, tools, and effects before retry. It never creates duplicate children,
replays completed work, or automatically resends uncertain effects.

Completed native children remain completed in the ledger and are never resumed
or replayed during swap, startup, retry, or model-assisted worker restart.
Native runtime-owned background work is evaluated separately using its task
and lifecycle facts. An unmanaged detached process has no native stop/record
authority and remains an unknown writer/effect. Native teams are a separate
participant kind; coordinator resume does not prove team restoration and a
team is unsupported until its own pinned-runtime evidence passes.

Persist only IDs, references, hashes, statuses, version/capability facts, and
sanitized holder/process/hook/tool observations. Never read credential files
or copy tokens, conversation bodies, checkpoint contents, or generated
handoff prose into managed state. Swap and restart produce no written
handoff; a user-requested `handoff` remains its separate explicit operation.
