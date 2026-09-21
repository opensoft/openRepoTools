# Isolated Native-Worker Live Acceptance Plan

Status: **INCOMPLETE — LIVE UNVERIFIED**. The isolated initialization baseline
below ran without credentials or network access. Scripted gateway controls
below establish a bounded interrupt candidate. Authenticated acceptance is
**NOT RUN** and full Gate 0 acceptance remains incomplete.

## 2026-09-18 bounded busy-parent loopback observation

After explicit approval, one busy-parent run used the same disposable exact
SDK `0.2.153`, bundled CLI `2.1.273`, and required CLI SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
The frozen harness ran with `--control-mode interrupt
--busy-parent-before-control --release-target`; it did not use the settled
control-entry flag or repeat the orphan/crash arm. The existing local
`py-bench:brett` image had ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
The sandbox had `network=none`, no host mounts or real credentials, and used
only the scripted loopback endpoint and dummy key. No image was pulled. The
owned sandbox was removed, `sandbox_removed=true`, and no owned
`managed-loopback-*` container remained.

The gateway positively identified the pending parent **Agent** continuation
as request index 4. Immediately before control entry, the real child/task and
tracked Bash process were observed active with no prior terminal child event.
Under the gateway lock the barrier was pending and waiting, and the sticky
epoch began at index 5. This is the contracted
`immediate-pre-entry-not-atomic` liveness observation, not an atomic process
fact or a general busy-parent capability. The blocked response was released
after control but `response_completed=false`; that false value does **not**
prove cancellation or any other completion outcome.

The epoch crossed source, source-drain and target-held and closed at release.
Its `start_request_index=5` and `end_request_index=4` are the valid empty
range: zero new loopback `/v1/messages` arrivals occurred before release. The
separate release request was index 5, outside the closed epoch. This is only a
scripted loopback arrival observation, not zero-global inference or a
production continuous observer.

The interrupt receipt, stopped notification, tool terminal, tracked Bash exit
before cleanup and source process exit were all observed; forced cleanup was
false. The child Agent-header/task join remained false. The target was
requested to resume the source UUID, initialized and held with zero Messages
requests. `same_parent_uuid=true` is an aggregate that includes post-release
facts and therefore does not prove the exact parent was loaded during hold.
Exact held parent load, restored-task wake, worker-state clear and orphan clear
remain unknown, and the positive-orphan arm was not exercised.

After release, the request carried source/release markers and Agent tool
use/result history, and the target successful-result UUID digest matched the
source's observed session UUID digest. The interrupted source emitted no
successful result, however, so this does not prove completed-source
continuity. The report correctly records `eventual_continuity_observed=false`
with `continuity_scope=eventual-history-only` and reason codes
`target-parent-load-not-proven` and
`target-release-continuity-not-observed`.

The sanitized report is in private temporary artifact
`openrepotools-busy-parent.MfKev7/report.json`, SHA-256
`bd463d8fc4f0daa189b1cc11341e1f5309358dd2395e795a4c8c78cb2ed696b0`.
The eight-item source/probe/contract/SDK pin manifest has SHA-256
`1a24fea05c54b52053c9e551ac20f3a79650f6ea54469c8f0e0ed7facd97e42a`;
its pre/post comparison, image identity, SDK version and CLI version all
matched. The result remains `verdict=inconclusive` and `support_claim=false`.
It closes no task or acceptance checkbox and grants no public/runtime support.

## 2026-09-18 bounded control-entry loopback observation

After explicit approval, an exact SDK `0.2.153` copy was placed in a disposable
private environment and independently checked before one bounded run. Its
metadata artifact has SHA-256
`7eabac2bf2aaa90a695429eef92e1e5b097d005a09545611363ba22c897c77bb`;
the SDK selected bundled CLI `2.1.273` with the required full SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
The pre/post private-SDK manifest matched with SHA-256
`e889a8561914ecef5a03d1f1943a736467d537d8a06d69f04afcd58dbab7859a`.
No existing production interpreter was changed.

The frozen `managed_native_loopback.py` harness ran with `--control-mode
interrupt --control-entry-before-settle --release-target` against the existing
local `py-bench:brett` image. Its disposable child container used
`NetworkMode=none`, no host mounts or real credentials, a read-only root, all
capabilities dropped, no-new-privileges and bounded resources. No image was
pulled. The harness removed its owned container and reported
`sandbox_removed=true`; no owned loopback container remained.

The scripted source initialized and produced a native task, Agent header,
active Bash process and tracked sleeper. At actual control entry,
`parent_settled_at_control_entry=true`; the report classifies source-drain
causality as `settled-parent-before-control`. This observation therefore does
not exercise or prove an actually busy parent even though the observer was
configured to begin before the settlement wait.

The single observer epoch covered source, source-drain and target-held phases
and closed on release. Its scope is only scripted loopback `/v1/messages`
arrivals, not global inference or a production continuous observer. Four
source arrivals preceded the epoch. Its `start_request_index=5` and
`end_request_index=4` form the valid empty observed range: zero arrivals were
inside it. The separate release request was index 5, outside the closed epoch,
and brought the endpoint sensor's run total to five. The interrupt produced a
receipt, stopped notification, tool terminal, tracked process exit before
cleanup and source-parent exit without forced cleanup. Those coherent facts
remain a bounded interrupt candidate, not capability.

The target was requested to resume the source UUID, initialized, and held with
zero `/v1/messages`, count-tokens or API-hello requests. Exact parent load,
restored task events and wake evidence remained unknown; worker and orphan
state-clear facts remained unknown, and the positive-orphan arm was not
exercised. After the separately requested release, one `/v1/messages` request
contained source and release markers plus Agent tool-use/result history and
returned the same source UUID. The report classifies this only as
`eventual-history-only` continuity. It reports `verdict=inconclusive`,
`support_claim=false`, with `target-parent-load-not-proven`; no public or
runtime capability follows.

The sanitized report's private temporary artifact basename is
`openrepotools-native-loopback-runtime.cyIjNi/report.json`, SHA-256
`fd329c35d988ecf0574d25ae06c8f3b5882e0c669b42a1abbcfe88f169fa6dec`.
The corresponding private log SHA-256 is
`aac8b025a0b350aec3bc561dbf263de4d0af9612509e31a92b1323b4b5607d85`.
All 45 frozen source, test, probe, contract and design files had identical
pre/post manifests with SHA-256
`2d000da7f0cebd551b719d0a6cc849023f42eb1c43f9168094357b573bc8f3f0`.
This bounded observation closes no task or acceptance checkbox.

## 2026-09-18 Stage 1 follow-up

The bounded follow-up and artifact hashes are in the
[runtime-boundary investigation](../../openspec/changes/separate-swap-ctx-handoff/stage1-runtime-boundary.md).
The isolated SDK was recovered after the bench restart; its selected bundled
CLI digest again matches the reference below. A fresh baseline reproduced
initialization with no credentials and acknowledgement of a nonexistent task
without a terminal notification.

The reproducible probe now offers `--case missing-parent-resume`. It derives
the exact resume argument through official SDK options, selects a fresh UUID
in an empty sandbox, and sends initialization only. On the selected runtime it
produced a missing-parent loader error and natural exit 1 before successful
initialization, with no transcript writes. The requested UUID was echoed in
the error frame; that echo alone is not restoration evidence. The focused
probe checks passed **25 tests**. Positive parent restoration and model
dispatch remain unproven by this negative control.

The additional native-worker experiment uses a **scripted loopback Messages
endpoint** and a dummy fixture key in the same `network=none` sandbox. This is
gateway/API-key mode, not the `tokenSource: none` baseline. It can exercise
real native runtime task creation and stopping without a real account or model
service. It must keep source setup, source stopping, and target-held request
counts separate and report task, tool, process, transcript and loader facts
independently. Its result cannot grant subscription-account or CCR support.
The selected CLI's stream-json protocol is exercised directly with SDK-derived
arguments; that is not the full Python SDK client or public lane workflow.

The first corrected run observed a real background Agent/task, a live Bash
process, and native task/transcript writes. `stop_task` for the actual task
produced separate receipt, stopped-notification, tool-terminal and process-exit
facts before parent teardown. The target then initialized with the exact
source UUID and held for eight seconds with zero endpoint requests. No target
session UUID was emitted during that hold, so exact loaded conversation was
still unknown. One Messages request arrived during source stopping; this run
does not prove the required zero-request account-control interval. Internal
orphan restoration/notification enqueue remain unobserved, not certified
absent.

The settled-parent repeat still emitted one source-control Messages request
for `stop_task`, but the documented coordinator-wide `interrupt` comparison
emitted **zero** while producing native stopped, tool-terminal and sleeper-exit
evidence before teardown. Its exact-resume target held for eight seconds with
**zero** endpoint requests; after explicit release, one request carried the
original source/Agent history and its successful result returned the same
session UUID. This establishes eventual native continuity independently of
the held interval's request count.

The final crash-left-unfinished control preserved native records, excluded its
observed source/sleeper processes by identity, and resumed with zero held
requests and preserved UUID/history after release. It does not establish a
positive CCR orphan-wake/classifier path. Both final targets emitted one
native task frame during hold; internal restore/enqueue remain unknown. All
disposable sandboxes were removed.

Astra accepts coordinator interrupt as the next bounded integration candidate
for this selected CLI and scripted API/gateway mode. It needs a governed
whole-roster authorization and durable drain contract; it must not replace
task-specific `stop_task` invisibly. Actual profiles/accounts, busy and
multiple-child paths, complete lineage/effect accounting, native child exact
continuation and persistent inference fencing remain unverified. T003, T004
and T030 stay open, and production capability remains disabled. See the
investigation record for frozen sources, report hashes and validation limits.

The follow-up design is now specified in
[coordinator-interrupt.md](contracts/coordinator-interrupt.md). Acceptance must
measure the entire interval from account-control entry before preflight, not
only Stage 1's settled-parent cancellation window. It must also cover active
parent turns, multiple/nested children, completion races, event gaps, lost
receipts and source-writer/effect uncertainty in the actual supported modes.
The contract and fake-runtime tests do not supply that live evidence.

## 2026-09-17 isolated initialization observation

The earlier shared-network probe container was inspected and confirmed exited,
with process ID zero. A fresh disposable container successfully used literal
Docker `NetworkMode=none`, no host mounts, a read-only root filesystem, all
capabilities dropped, no-new-privileges, resource limits and temporary writable
directories. No shared-network workaround was used. An initial executable
placement failed because the temporary mount was non-executable; that sandbox
was stopped and replaced before the observation with an explicitly executable
temporary binary directory.

The SDK was resolved from its existing isolated probe environment, not installed
into the production interpreter. SDK `0.2.153` selected its own
`claude_agent_sdk/_bundled/claude` through the installed transport's bundled-first
resolver. The full selected executable digest was recomputed:
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
A byte-identical copy in the disposable container reported `2.1.273 (Claude
Code)`. The SDK-selected command shape was:

```text
<selected-cli> --output-format stream-json --verbose --system-prompt "" --input-format stream-json
```

The observation executed those arguments against the copied selected binary;
it did not exercise the whole Python SDK client lifecycle. The child received
an allowlisted environment, empty home/config directories and exactly one
`initialize` control request. No user-query frame was sent. During the bounded
eight-second read it returned one successful `control_response`, reporting
account `tokenSource: none`; stdout contained 15,498 bytes and stderr zero.
Only sanitized frame types and token-source classification were retained in
this report. The child was terminated and reaped (return code 143); a process
listing showed only the sandbox's sleep process, and the sandbox was then
stopped and confirmed exited with process ID zero.

**Verdict: inconclusive; support claim: false.** Initialization is the only
case exercised. Model dispatch was not independently instrumented and remains
unknown. Positive orphan restoration and the supported terminal-stop/clear
candidate were not exercised. Static inspection of this exact binary found
that the ordinary structured-input transport starts with null restored worker
state, while the CCR worker-state path needs authentication headers. Neither a
silent startup nor that static distinction proves the required positive
control. The reason for withholding support is
`orphan-positive-control-unreachable` in the current no-auth harness, not an
observed successful hold boundary or proof that every runtime mode is unsafe.

The baseline is now reproducible with
[`tests/probes/managed_gate0.py`](../../tests/probes/managed_gate0.py). Run it
inside the declared bench, naming an existing isolated SDK interpreter, an
existing local bench image and a new private report path:

```sh
python3 tests/probes/managed_gate0.py \
  --sdk-python "$PROBE_SDK_PYTHON" \
  --image "$PROBE_BENCH_IMAGE" \
  --output "$PROBE_REPORT_PATH"
```

The harness never pulls an image, mounts host directories, loads real profiles,
or sends a user query. It checks the SDK-selected argument shape, verifies the
copied executable digest, rejects shared-network or weakened container
isolation and removes only its own container. Report paths are created
exclusively with mode 0600. The successful harness run reported the same
SDK/CLI/digest, successful no-token initialization and
`sandbox_removed: true`. Its **inconclusive** report is an observation artifact,
never a production capability grant. Isolation validation has 13 passing
offline tests, including rejection of the previous shared-namespace pattern.

Next evidence required: a supported way to exercise the relevant orphan
restore mechanism in isolation, independently observe wake and model dispatch,
and observe terminal-stop/state-clear through supported runtime operations.
Do not add credentials, undocumented flags or transcript rewriting to turn
this baseline into a passing result. T003/T004/T030 remain open until their
complete acceptance requirements are met.

This is a measurement plan, not authorization to access an account, start or
stop a session, switch a profile, send a prompt, or modify a worktree. Reading
or editing this file authorizes none of those actions, and this documentation
change performs none of them. A separately approved run may use only disposable
profiles, sessions, and directories; without that separate approval the gate
stays `UNVERIFIED`. Fake adapters and synthetic lifecycle events cannot satisfy
this gate.

## 2026-09-17 missing-task stop control

The probe now follows successful initialization with the documented
`stop_task` control for `gate0-nonexistent-task` in its empty disposable runtime.
It creates no child/task record and sends no model query. This is a negative
control for acknowledgement semantics, not the required positive orphan or
real-child terminal-stop experiment.

On the same SDK `0.2.153`, selected CLI `2.1.273` and full digest recorded
above, the runtime returned **success for the nonexistent task**, followed by
**zero matching terminal notifications** during the bounded observation.
The sandbox was removed and the child reaped. Evidence is retained externally
at `py-bench:/tmp/managed-gate0-stop-control-20260917.json`.

This directly demonstrates why a control acknowledgement cannot prove child
quiescence or durable worker-state clearing. The SDK's documented
[`stop_task` method](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/client.py)
also describes a separate stopped-task notification; the installed version
was inspected before the probe. The capability result remains **inconclusive**,
with no production grant. All **17** probe isolation/observation tests pass;
they explicitly prevent even a synthetic terminal notification for the missing
task from being recorded as proof that a real child stopped.

## Scope and non-authority

The future run, if separately approved, must use the implemented public path
and the exact pinned native runtime configuration. It must not adopt, stop,
repoint, or inspect private data from an existing user session. It must not
create a written handoff as part of swap or worker restart. A user-requested
`handoff` remains a different operation and is not evidence for this gate.

No account names, credentials, tokens, raw environment, complete transcripts,
checkpoint contents, or private tool output belong in the result. Record only
sanitized identifiers, hashes, statuses, capability facts, and bounded process
or hook observations.

## Gate 0 — pin the actual runtime and startup behavior

Before any authenticated or model-bearing scenario, record the exact SDK
package/version, selected Claude binary path as an external observation,
binary version, full SHA-256 digest, runtime mode, platform, Python version,
launch settings, and profile/store configuration. The path and full digest
must be captured from the executable actually selected by the SDK; do not
substitute a system binary or a remembered version. The prior 2.1.270
system-executable trace is informative only. The measured candidate is SDK
0.2.153 selecting its bundled 2.1.273 executable; that observation is not a
passing capability result until its exact path, full digest, and mode are
recorded for the run.
The measured bundled digest was
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`; retain it
only as a probe reference and recompute/record the selected executable digest
for every future run.

Run a no-auth, no-model, disposable orphan fixture using that exact selected
runtime. Gate 0 must establish, from the actual pinned binary rather than a
fake runtime:

1. which startup mode is being tested (interactive takeover versus SDK
   `stream-json`/the `print.ts` path);
2. in a positive orphan case, whether a deliberately seeded durable native
   parent/task record is loaded, a notification is enqueued, a child/parent is
   woken, and a model-query attempt occurs—each as a separately observed
   outcome;
3. in the target safety case, after a supported source stop has produced
   terminal child/tool evidence and durably cleared the old
   `running_background_tasks` state, whether target connect with inference
   fenced reports terminal-cleared state, no orphan restored, no orphan
   wake/notification, and no model query; and
4. whether native lifecycle and hook/tool evidence remains correlated after
   startup.

The positive orphan case intentionally distinguishes
`enqueuePendingNotification`, a wake, and a model request; a no-auth failure
or eventual `idle` result cannot collapse them. A held connection is not
evidence of child continuation. Interactive takeover and SDK `stream-json` are
separate modes: interactive takeover may provide an
autoresume callback, while the `print.ts` path has no autoresume callback. The
result is valid only for the exact SDK, selected binary, version, digest, mode,
and platform tested. If the selected mode is proven non-auto-resuming, its
safety boundary is direct current-run native child/tool quiescence and
containing-process exclusion; do not require or invent a classifier marker
solely to suppress an absent callback. If the target criterion or applicable
non-auto safety boundary is not proven, mark the configuration `unsupported`.

The selected 2.1.273 print/stream path may restore persisted
`running_background_tasks` as `restoredOrphans`; its default-enabled
`tengu_ccr_orphan_restore_wake` may call `enqueuePendingNotification` and
trigger inference before an external query. Gate 0 therefore must prove
terminal child/tool stop and durable clearing of the old running-task state,
then prove that target connect emits no orphan wake and no model request.
Stream-json/print mode by itself is insufficient. If this evidence is missing,
the selected configuration is `unsupported`.

## Gate 1 — discover one native lineage

Use only a separately approved disposable lane. Start one coordinator and the
native child kinds under test through the public runtime. Capture the
coordinator's exact:

- native `session_id`, selected profile/account identity, and transcript/store
  reference;
- runner PID/start identity, containing process tree/process-group evidence,
  and current process-domain observation;
- bounded native `session_name` and canonical `bound_lane`; and
- model, effort, effective permission mode, tools, launch settings, and
  runtime incarnation.

Capture each child only as a native lineage record. It must include
`agent_id`; record `task_id` only when an actual native task event or
authoritative native task record supplies it. Also capture exact `type`,
`tool_use_id`, direct parent linkage, transcript/task record and child-store identity, current `status`,
`stop_provenance`, model, effort, immutable custom-agent definition identity,
and effective tools/permissions. A native child receives no invented session
UUID, top-level runner ID, or process-group ID. An OS process observed beneath
the coordinator is process-tree evidence only, not a child identity.

These fields must be assembled only from actual SDK fields and durable joins.
`SubagentStart` carries `session_id`, `transcript_path`, `cwd`, optional
`permission_mode`, `agent_id`, and `agent_type`; `SubagentStop` adds
`stop_hook_active` and `agent_transcript_path`, but neither supplies
`task_id`, `tool_use_id`, or `parent_agent_id`. Tool hooks carry
`tool_use_id` and may carry `agent_id`/type. `TaskStarted`, `TaskProgress`, and
`TaskNotification` carry `task_id`, `session_id`, event `uuid`, optional
`tool_use_id`, and `TaskStarted` also carries `task_type`; `TaskUpdated` carries
`task_id`, `status`, `patch`, and optional `session_id`/event `uuid`, but no
`tool_use_id`. Session history may supply `parent_tool_use_id` and
`parent_agent_id`. Join a durable pending Agent admission to these fields and
the current parent invocation/watermark; a pending admission may join an
actual task ID but cannot create one. A missing or ambiguous join is
`unresolved`, including a nested child whose parent cannot be established.
The task-event `uuid` is transport correlation, not a per-child UUID.

Record the containing process tree and actual hook/tool facts. Hooks must show
the coordinator identity and, where applicable, the exact child `agent_id`,
`task_id`, and `tool_use_id`; an event without an agent ID cannot be assigned
by name or timing. Tool facts must include start/end/failure, descendants,
and possible external effects. Keep parent process-tree ownership distinct
from native child identity.

### Gate 1a — child permission and ownership edge

Exercise a read-only coordinator with one explicitly authorized writable
native child. Bind that child's hook/tool decision to its actual `agent_id`,
immutable custom definition, effective permission mode, allowed tools, and
writable path. The parent `read_only` setting must not make the authorized
child read-only, and the child must not inherit broader permissions than its
own definition. Because any member may write, the coordinator execution
lineage must hold the workspace/worktree claim; an isolated child worktree
uses an additional path claim owned by that same lineage.

Then exercise an unknown child ID, missing definition, contradictory policy,
or ambiguous hook/tool record. Admission must refuse before that child can
write, without broadening the parent or releasing the lineage claim. Record
this as `unresolved`/refused, never as a read-only success.

## Gate 2 — seed and observe the lifecycle ledger

Using only the separately approved disposable prompts, establish unfinished
native tasks and at least one completed child. The ledger must consume and
correlate these actual event kinds:

- `SubagentStart` and `SubagentStop`;
- `task_started`, `task_progress`/`progress`,
  `task_notification`/`notification`, and `task_updated`; and
- `PreToolUse(Agent)`, `PostToolUse(Agent)`, and other tool hook events.

`PostToolUse(Agent)` closes only the Agent launch tool. It is not child
terminal evidence; a child that remains active after that call remains active.
Terminal status requires a correlated `SubagentStop` or an authoritative
task-terminal update. A stale status/notification from an earlier event
watermark cannot terminate the current task.

The runtime may reuse an `agent_id` after a child resumes. Bind terminal
evidence to the current actual `task_id` when supplied, direct parent
invocation/`tool_use_id`, and monotonic event watermark. Verify that a reused ID starts a new ledger
incarnation rather than allowing an old completion notification to mark the
new run complete.

## Gate 3 — stop provenance, background work, and effects

Perform the bounded stop while an unfinished child and, separately, a tracked
tool are active. Observe the durable fence, event drain, tool end/failure,
containing process-tree exclusion, and retained lineage claim. Record the
actual stop provenance: model stop, user cancel, SDK cancel, parent shutdown,
runtime failure, process loss, or unknown. An interrupt receipt, parent exit,
OS suspension, background flag, `setsid`, or `nohup` is not quiescence.

Test a runtime-owned native background subagent as its own participant kind.
Its native task ID, parent linkage, lifecycle events, process-tree relation,
and hook/tool policy must remain observable after the Agent launch tool ends.
Do not mark it stopped or complete merely because that launch call returned.

Test an unmanaged detached shell/process separately. If it lacks native task
and lifecycle ownership, or a remote/external effect may have happened, the
result is unknown: retain the lineage claim and fence, refuse release, and do
not replay. A background marker or parent exit cannot turn it into a controlled
native child.

Test native teams in a separate scenario and report them as a separate
participant type. Coordinator resume or ordinary subagent evidence does not
prove team restoration. Teams remain `unsupported` until their own exact
runtime, lifecycle, process, permission, and store behavior passes a reviewed
probe.

## Gate 4 — cross-profile preflight and exact restoration

For a separately approved source/target profile pair, compare canonical
profile identity, expected account identity, transcript family,
coordinator store, project/workspace, and every native child store. A shared
family label is not enough: if the child store is profile-specific, require an
actual tested source-to-target mapping preserving parent session, agent/task
IDs, type, launch tool, transcript record, status, stop provenance, model,
effort, custom definition, tools, and permissions. A missing/divergent or
untested cross-profile child store is `unresolved`/`unsupported` before stop.

After safe source quiescence, restore the exact coordinator `session_id` with
the official loader under the target account and keep it held. Verify its
account, process, name, lane, permission, model/effort, workspace, and
launch-definition evidence. During this control phase, accepted-send/query
counts must show no model request, generated checkpoint, continuation prompt,
semantic summary, commit, push, or written handoff.

Mark a native child `resume-pending` while held only when safely stopped SOURCE
current-run evidence, exact target parent restoration, and the tested pinned
resumability capability all agree: correlated `SubagentStop` or authoritative
task-terminal evidence, terminal tracked tools, source process exclusion, and
reconciled effects; the same parent; captured `agent_id` and actual native
task-record/event `task_id`; matching parent invocation, immutable definition,
model/effort, accessible transcript/store, tools, permissions, stop
provenance, and current event watermark. No held/active continuation event is
required or accepted before release. After explicit release, a current
correlated continuation event under that same parent/invocation/watermark
changes the disposition to `exact-resumed`. No child UUID or PGID is needed or
permitted.

If user/SDK cancellation or in-process loss is not documented and tested as
resumable, do not call the child exact. Preserve its records as
`restart-pending` when a mechanically composed restart is possible, or
`unresolved` when identity/effect evidence is incomplete. An inaccessible
child transcript/store blocks exact continuation, including `resume-pending`,
but does not alone block a safe `restart-pending` fallback when current-run
stop/effect facts and the original parent/native task record, model/effort, and
custom definition are recoverable. Unknown effects remain unresolved. A new
parent process alone never proves exact child continuity. Completed children
remain complete and are not resumed or replayed.

## Gate 5 — release-gated restart fallback

For each `restart-pending` child, first establish target coordinator readiness
and an explicit matching `release`. Only then may the coordinator receive the
ordinary model instruction that uses the durable task/identity record. This is
model-assisted worker restart, not a generated semantic handoff. The accepted
transport acknowledgement is not evidence that a child restarted.

Record `restarted` only after a correlated native task/start/lifecycle event
proves that the new run was created under the intended parent and definition.
If the runtime assigns a new `agent_id`, retain the original ID as the source
record and link the new ID as a new run; do not claim the old conversation or
identity was exactly resumed. If no correlated event arrives, retain
`restart-pending` or mark `unresolved`; never infer success from the model's
text or from a sent instruction.

The control phase may not send this instruction before release and may not use
the exhausted source account as a prerequisite. The fallback produces no
written handoff and does not replay completed work or uncertain external
effects.

## Gate 6 — partial start and retry

Inject a target-start failure after the coordinator and at least one native
child have reached held readiness, and separately after a child restart
instruction might have been sent. Keep the same durable operation identity.
On retry, reconcile the target coordinator process/tree, native child/task
records, event watermark, stores, hooks, tools, claims, and effects before any
new admission.

The expected result is per child, not all-or-nothing narrative:

| Result | Required proof and retry behavior |
| --- | --- |
| `resume-pending` | Safely stopped source current-run evidence, exact restored parent, actual native identity/task record, definition, and pinned-runtime predicate agree while held; no continuation event is accepted before release, and the post-release event is required for `exact-resumed`. Do not start a duplicate child. |
| `exact-resumed` | After release, a current same-parent/captured native ID continuation event and definition match prove exact continuation. Do not start a duplicate child. |
| `restart-pending` | Durable stop/task record exists but no exact continuation or correlated new run yet. Do not dispatch before target readiness and release. |
| `restarted` | A post-release instruction has a correlated native start/task event. Do not send the same restart again automatically. |
| `unresolved` | Any missing/contradictory identity, stop, policy, process, store, or effect evidence. Keep the fence/claims and require explicit reconciliation. |
| completed | Preserve completed state. Never replay or restart it during target retry. |

Verify that retry never creates a second parent owner, duplicate native child,
duplicate writer, duplicate tool effect, or automatic resend of uncertain mail
or external actions. A partial target start must remain visible and recoverable;
it is not permission to fall back silently to the old account or a handoff.

## Evidence record and gate decision

For a separately approved run, store a concise sanitized result containing:

- exact SDK/binary/version/full digest/mode/platform and launch settings;
- operation/request IDs and monotonic event watermarks;
- coordinator session/account/process/name/lane mapping;
- child `agent_id`/actual `task_id` where supplied/type/tool-use/parent
  mappings, transcript/store references, statuses, stop provenance, model/effort, definitions, and
  per-child hook/tool policy facts;
- process-tree and containing-group exclusion observations;
- accepted-send/query counts before/during/after swap, release, and restart;
- cross-profile child-store results, partial-start/retry outcomes, completed
  no-replay evidence, and refusal/uncertainty reasons; and
- the exact disposable configuration and elapsed bounded-stop/start times.

Do not record full transcripts or credentials. A passing run establishes only
the exact tested configuration and participant kinds. Missing evidence,
unexpected inference, uncorrelated child events, policy bypass, an unknown
detached effect, duplicate replay, or a manually bypassed hook fails the gate.
Live capability remains `UNVERIFIED` until a separately authorized and
reviewed result supports a narrower published claim.

## 2026-09-18 corrected evidence-harness disposition (documentation only)

This additive section records the disposition after the evidence-harness
semantic review. It is not a new probe run: Luna executed no probe, test,
runtime, network, account, or profile operation for this section, and no task
checkbox or acceptance gate is closed. The historical observations and their
limits above remain unchanged. In particular, a candidate arm being
executable in the harness is not evidence that the selected runtime supports
the lifecycle operation.

The corrected harness has bounded candidate dispatch for Gate 0 cases
`positive-orphan` and `terminal-cleared`. The former delegates to the
loopback runner's crash-owned-process-group/unfinished-record arm; the latter
delegates to the `stop_task` arm. Both verify the selected SDK/CLI identity and
retain `support_claim=false`. They are mechanical observation attempts, not
positive support paths. The checked-in event JSONL and source fixtures remain
extracted feasibility controls only; they are not selected-CLI output and are
not an authority for a runtime result.

### Current fact disposition

| Surface | What the harness can attempt | What is actually established now |
| --- | --- | --- |
| Gate 0 positive orphan | Seed an unfinished loopback record, end the owned source process group, and hold a target using the selected runtime. | No corrected runtime arm was executed in this lane. The selected CLI has no evidenced stream-JSON subtype or authoritative API for persisted-record load, restored-orphan admission, child-parent wake, or notification enqueue. Those facts are `UNKNOWN`; the arm is `unsupported`/`unverified` with no support claim. |
| Gate 0 terminal cleared | Exercise the bounded `stop_task` source control, then hold the target and assess worker/orphan clearing independently. | Historical `stop_task` runs observed receipts, stopped/task-terminal/tool/process facts, but also observed a new source `/v1/messages` request during source control. Therefore the corrected negative gate is `source-control-request-observed` and `control_request_free=false`; this is not a terminal-clear success. No independent selected-runtime emitter proves `worker_state_clear` or `orphan_state_clear`, so each remains `UNKNOWN`. |
| Busy parent | Identify the pending parent Agent continuation before control and correlate child/Bash activity. | The historical busy-parent artifact proves the pending-parent and pre-entry child/Bash observations. The blocked response was released with `response_completed=false`; that is not cancellation evidence. Response-write disposition, parent/session aggregation, or a later result cannot promote it to cancellation. Exact held parent load and restored-task wake remain `UNKNOWN`. |
| Coordinator interrupt | Attempt a turn-wide interrupt with one sticky loopback request-observation epoch. | The historical settled-parent candidate recorded native stop/tool/process facts and zero arrivals in its scoped epoch, but it was not a busy-parent, multiple-child, nested, completion-race, or in-flight-admission proof. The current corrected harness still lacks the authoritative lifecycle surfaces needed for those claims. The mode remains `unsupported`/`unverified` for production. |

The following distinctions are deliberate. A `control_response`, interrupt or
stop receipt, `task_started`/task notification, tool-terminal join, process
identity/exit, session UUID, or loopback `/v1/messages` route count is a real
mechanical observation when correlated in the report. None of those alone
proves exact parent loading, an orphan wake, durable state clearing, or
response cancellation. In particular, `launched && hold_complete` is not a
target-connect observation, and a zero uncalibrated wake counter is not a
target-no-wake observation. The corrected terminal assessment therefore keeps
`target_connect`, `target_no_wake`, `exact_parent_load`, `worker_state_clear`,
and `orphan_state_clear` independent and `UNKNOWN` unless their own
correlated surface is present.

### Missing selected-runtime event surface

No exact selected CLI stream-JSON emitter or authoritative state API has been
evidenced for the proposed labels `persisted-record-load`, `restored-orphans`,
`child-parent-wake`, `durable-worker-state-clear`, or the internal/source names
`restoredOrphans` and `enqueuePendingNotification`. The same applies to the
fixture/internal `running_background_tasks` and generic `durable_state_clear`
labels as proof of the independent worker and orphan facts. These names are
not protocol subtypes merely because they occur in extracted source or
synthetic JSONL. The corrected harness no longer treats a bare alias as an
observed control event; injected fixture events can validate parsing and
fail-closed classification only.

This is also why repeating a runtime arm cannot turn the aliases into
evidence. Repeating the same synthetic fixture repeats a parser/control-shape
test, not a selected-binary emission. Repeating the loopback arm can measure
bounded endpoint arrivals and process facts, but it cannot create the absent
CLI lifecycle event, correlate an internal durable record, or establish a
state-clear transition. A real supported stream-JSON emitter or authoritative
runtime state surface must first be identified and pinned; none is evidenced
by the artifacts recorded here. No repeated arm is therefore claimed as a
resolution of the positive-orphan or terminal-clear gap.

### Pinned identities and historical artifact references

The only selected-runtime identity evidenced by the historical runs is SDK
`claude-agent-sdk==0.2.153`, bundled CLI `2.1.273`, CLI SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`, and the
existing local image reference `py-bench:brett` with image ID
`sha256:bca9ff191ad16f350ccfff349c9dd59e7accde7d9da77e709cea349fcb2b7a8d`.
These pins describe the historical disposable environment; they do not grant
production access or imply that a corrected arm has run.

Previously recorded private artifacts remain historical evidence only:

- busy-parent report `openrepotools-busy-parent.MfKev7/report.json`,
  SHA-256 `bd463d8fc4f0daa189b1cc11341e1f5309358dd2395e795a4c8c78cb2ed696b0`;
- settled control-entry report
  `openrepotools-native-loopback-runtime.cyIjNi/report.json`, SHA-256
  `fd329c35d988ecf0574d25ae06c8f3b5882e0c669b42a1abbcfe88f169fa6dec`;
- its private log, SHA-256
  `aac8b025a0b350aec3bc561dbf263de4d0af9612509e31a92b1323b4b5607d85`;
- the initial Gate 0 baseline artifact
  `managed-gate0-baseline-20260918.json`, SHA-256
  `a6c3da53ae12280e546b9d651c1a991b30daf46ed28dfece66d4880f3d3f7598`.

The busy-parent report remains `verdict=inconclusive` and
`support_claim=false`; the control-entry report has the same disposition.
Sol's focused immutable-snapshot unit/fake slice reported 279 passed, one
unrelated SDK-rollover failure, and 1543 deselected; that result was not a
runtime arm and was captured before this semantic correction. The failure was
`_consumed_reservation_ids.append(...)` on a set in the SDK lane and is not
evidence for or against the lifecycle controls here. No corrected probe-test
result is asserted in this section.

### Safe candidate invocations for Sol (not executed here)

When Sol has the separately authorized isolated bench, these are the exact
bounded candidate invocations against the existing image reference. The
selected SDK interpreter must already be the pinned isolated interpreter; no
package install, image pull, credential, profile, or network access is part
of these commands. The Gate 0 wrapper creates the disposable child with
`network=none`, no host mounts, and bounded cleanup, and reserves each output
file as a new private `0600` artifact:

```sh
python3 tests/probes/managed_gate0.py \
  --sdk-python "$PROBE_SDK_PYTHON" \
  --image "py-bench:brett" \
  --case positive-orphan \
  --output "$PROBE_DIR/positive-orphan.json"

python3 tests/probes/managed_gate0.py \
  --sdk-python "$PROBE_SDK_PYTHON" \
  --image "py-bench:brett" \
  --case terminal-cleared \
  --output "$PROBE_DIR/terminal-cleared.json"
```

These commands are candidate no-auth/no-network validation attempts, not
acceptance commands: any output must preserve the unknown facts and
`support_claim=false`, including the terminal-cleared negative gate when the
source control request is observed. Their use cannot turn the missing event
surface into production capability.

### T030 alternative disposition

For Astra's review, the explicit T030 fallback is now documented: the
selected runtime's positive-orphan, terminal-cleared, busy-cancellation,
exact-parent-load, worker-clear, orphan-clear, and complete coordinator
roster surfaces are `unsupported`/`unverified` wherever the required
authoritative observation is absent. Thus T030 is complete only through its
explicit **unsupported/unverified alternative**. This closes T030's evidence
disposition requirement, not native/runtime/feature acceptance: no
selected-runtime support claim is made. Authenticated account/profile
validation remains **NOT RUN — UNVERIFIED**.
