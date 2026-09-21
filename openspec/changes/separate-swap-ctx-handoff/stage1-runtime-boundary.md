# Stage 1 runtime-boundary investigation

CLAIMED — lane swap-runtime-gate, session
`01a0b3be-3f3b-7272-bd2c-e11fda90fbb6`, 2026-09-18T09:05:44Z, for the
Stage 1 runtime-feasibility investigation only.

Brett authorized this bounded follow-up with “lets do stage 1. do taht” after
reviewing the five-stage completion plan. This is a new investigation under
the existing feature, not a reuse of an older single-use handoff. No claim,
competing remote feature branch, or matching pull request was found in the
change records, the remote head lookup for `*separate-swap*`, or the GitHub
lookup for `001-separate-swap-ctx-handoff`. Existing recovery and context PRs
retain their own scope.

The executable tasks remain in
[the Speckit feature](../../../specs/001-separate-swap-ctx-handoff/tasks.md),
especially T003, T004 and T030. This record creates no duplicate task list.
Astra owns the architecture assessment, Sol High coordinates probe execution,
and Luna Max writes any required implementation changes.

## Authorized experiment boundary

Use disposable, unauthenticated, network-isolated runtime observations with
the exact SDK-selected executable. Preserve real profiles, sessions, lane
bindings, worktrees and existing feature edits. Do not manufacture runtime
state by rewriting transcripts or using undocumented flags. Authenticated
model-bearing fixture creation and account switching remain outside this
investigation.

## Evidence and disposition

The bounded investigation is complete: documented coordinator-wide interrupt
is a viable zero-request stop/restore candidate in the tested scripted
API/gateway mode. Task-specific `stop_task` fails the source zero-request
requirement. The later observations below establish the distinction. Full
Gate 0 remains open and no production capability is granted.

The exact isolated SDK was recovered after the bench restart: Python SDK
`0.2.153` again selected bundled CLI `2.1.273`, with recomputed SHA-256
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
The unrelated system CLI is not the test runtime.

The comparison baseline ran in a fresh literal `network=none` container with
no host mounts or credentials. Initialization succeeded with `tokenSource:
none`; stopping a nonexistent task again succeeded without a matching terminal
notification. The child was reaped and the sandbox removed. Its private report
is `managed-gate0-baseline-20260918.json`, SHA-256
`a6c3da53ae12280e546b9d651c1a991b30daf46ed28dfece66d4880f3d3f7598`.
This reproduces the acknowledgement limitation; it does not advance the
positive native-worker gate.

The new `missing-parent-resume` control used the official SDK's exact
`--resume=<fresh UUID>` argument in an empty sandbox and sent initialization
only. The selected CLI emitted `result/error_during_execution` for the missing
parent and exited naturally with status 1 before successful initialization.
There were no user frames, stop controls or transcript writes. The sandbox
was removed. The error frame echoed the requested UUID: an echo alone is not
proof of a loaded conversation. This reproduces the earlier rejection finding
and does not demonstrate a production false-readiness bug.

Private report: `managed-gate0-missing-parent-resume-20260918.json`, SHA-256
`5b74fef1f0420c2ad8516bdfbf87ab5c9ae7eb0e87603cfd392540455959dde8`.
The canonical focused probe suite passed **25 tests**, with 1,427 deselected.
Private JUnit: `missing-parent-probe-tests-20260918.xml`, SHA-256
`6353d77c86cdbca48d35faf579cfd660a51c50baf37a0d0e3422f5912de37058`.
No real-child stop, positive parent restore or model-dispatch observation is
claimed from this negative control.

## Offline native-runtime experiment

Astra approved a bounded additional experiment within Stage 1: a scripted
Messages API endpoint on loopback inside the same isolated container. The
selected Claude binary, rather than the test harness, creates native Agent
tasks and writes its own transcripts. The endpoint supplies deterministic
responses instead of contacting a real model service. An explicitly synthetic
fixture key is not a real credential; this is gateway/API-key mode, distinct
from the unauthenticated baseline and subscription-account acceptance.

The documented `ANTHROPIC_BASE_URL` configuration supplies the loopback
endpoint. Count inference `POST /v1/messages` requests separately from auxiliary
requests and separately for setup, stop, and target-held phases. A target
request is an observed dispatch attempt even if the fixture rejects it.
Native task termination, tool/process termination, persistent task state, and
exact parent restoration remain separate observations. The experiment must
not fabricate native events or modify transcript contents.

The public gateway protocol documents both the endpoint and the runtime
differences that prevent transferring its result to another account mode:
[gateway protocol](https://code.claude.com/docs/en/llm-gateway-protocol),
[subscriptions and gateways](https://code.claude.com/docs/en/llm-gateway#subscriptions-and-gateways).
Missing restoration or observability evidence remains unverified, even when
the fixture's local native lifecycle succeeds.

### First real native stop observation

The corrected fixture routes its Agent response only to the marked source
request advertising a native Agent/Task tool. Earlier attempts accidentally
answered an auxiliary request with no tools; their absent worker is a fixture
failure, not evidence that the runtime cannot create a worker.

On the corrected run, the selected CLI created a background Agent, emitted an
actual `task_started` identifier, executed the scripted Bash sleep, and wrote
its own task and transcript records. Stopping that actual task produced a
control receipt, a stopped notification, matching tool-terminal evidence and
sleep-process exit before parent teardown. Forced cleanup was unnecessary.
These are separate observations; a successful receipt alone remains
insufficient. The fixture did not independently correlate a child-header
agent identifier with the task event.

The endpoint saw four Messages requests during source setup and **one during
source drain after stop authorization**. This run therefore does not show a
model-request-free stop/drain interval; the count alone cannot distinguish
stop-triggered work from an already scheduled source continuation. Blocking
external query admission cannot be assumed to fence runtime-internal requests.
The exact source UUID was then
passed to a fresh target using the SDK-derived resume arguments. Target
initialization succeeded and its eight-second hold produced zero Messages,
token-count or hello requests. No target UUID was emitted during that hold,
so exact loaded conversation remained unknown in this run. Absence of frames
matching the probe's orphan/wake labels is not independent evidence about
internal notification enqueue or worker restoration.

Private report: `managed-native-loopback-repair1-20260918.json`, SHA-256
`f3ab5cc8dd806bb69a219f6ddbcff4abfd1fa5375e80a2bc4f59d54722a2438d`.
The sandbox was removed.

### Settled-parent stop and exact continuity

The next stopped-worker run waited for the parent's completed source result
while the native child and Bash tool remained active. It again observed real
task/tool/process termination, followed by one source-drain Messages request.
This narrows the result: the tested task-specific stop path does **not** meet
the zero-new-model-request account-control requirement, even after the initial
parent turn has settled. It does not establish that every supported control
path has the same behavior.

The target's eight-second initialization-only window again made zero endpoint
requests. Only after that window, an explicit release query caused one request.
The endpoint independently found the source-only prompt marker, original Agent
tool use and result in native conversation history. The successful target
result returned the same UUID as the source. This proves eventual exact
conversation continuity and calibrates the endpoint sensor; it does not locate
the internal load instant within the earlier held window.

Report: `managed-native-loopback-final-stopped-20260918.json`, SHA-256
`854ac243a5ffaca0d54d39a1e77cac29434976f6dacd622d7bab496aded01e12`.
Source SHA-256:
`3ca7772b58dfe1e81273ec98d1d3f122125882fde740bc1bf347de8b233c946b`.

The matching crash control created authentic unfinished task/transcript
records, then killed its owned source process group. The Bash sleeper remained
alive in another process group, so the probe correctly refused target launch.
This was a fixture-exclusion failure, not an orphan-restore result; cleanup
removed the sandbox. Report:
`managed-native-loopback-final-crash-left-unfinished-20260918.json`, SHA-256
`eef2abf08a5fe812a3bb7c23230f84c983d6c01dccab1c06add1e652ddc0a89e`.
The follow-up snapshots actual descendant PID/start identities before crash
and excludes only those identities. A separate documented-interrupt arm tests
the remaining supported cancellation candidate. Neither change rewrites
native records or changes the production stop contract.

### Final interrupt and unfinished-source controls

Both final controls ran with probe SHA-256
`b9902726a974f5a16006504df01095fdeb6e7f219d816de02f2f8cbfa31b0033`,
using the same SDK-selected CLI digest above.

| Observation | Task-specific stop | Coordinator interrupt | Crash-left unfinished input |
| --- | --- | --- | --- |
| Parent source turn settled before control | Yes | Yes | Yes |
| New source-control Messages requests | 1 | 0 | 0 |
| Native stopped notification and tool terminal | Both observed | Both observed | Not claimed from forced process termination |
| Observed fixture processes excluded before target | Yes | Yes, without forced cleanup | Yes, after identity-checked fixture cleanup |
| Target held Messages requests, eight seconds | 0 | 0 | 0 |
| Same parent UUID and native history after explicit release | Observed | Observed | Observed |

The interrupt control sent the documented `interrupt` operation instead of
`stop_task`. Receipt, native task stopped, tool terminal and tracked sleeper
exit were observed independently. No source-control Messages request arrived.
The exact-resume target initialized, emitted the source UUID, and made zero
held Messages/count-token/hello requests. One native task frame was observed
during hold; it does not identify internal orphan classification or wake. The
explicit release then produced one parent request containing original native
history and a successful result with the same UUID.

The repaired crash control created authentic unfinished runtime records,
killed its owned source group and identity-validated sleeper descendants, and
verified their exclusion before target launch. It did not send a native stop
or modify runtime records. Exact target resume remained request-free during
hold and preserved UUID/history after release. This is an unfinished-source
input control, **not** proof of the CCR `running_background_tasks` classifier
or a positive orphan-wake path.

Final private reports (mode 0600):

- `managed-native-loopback-final-interrupt-20260918.json`, SHA-256
  `7d95881095d760d073f836f1ba7c20bc2a76c2d87ed6443c73b8631b23f48e21`.
- `managed-native-loopback-final-crash-left-unfinished-rerun-20260918.json`,
  SHA-256
  `55962f20d0f568740f07520c8c9f5f102287c45e0da16cd216ac60442127dee5`.

Both sandboxes were removed. There were no real credentials, model-service
calls, profile switches or production lane changes.

### Architecture disposition

Astra accepts the bounded interrupt candidate for further governed design.
It is coordinator-wide, so it must not silently replace the task-specific
authorization in [the native stop contract](../../../specs/001-separate-swap-ctx-handoff/contracts/native-stop.md).
Next work needs a sealed native roster, durable whole-roster send intent,
independent per-child/task/tool drain evidence, writer exclusion and exact
held parent restore. The [official SDK interrupt contract](https://code.claude.com/docs/en/agent-sdk/python)
requires draining buffered results; it does not promise a persistent inference
fence. Tool permissions and rejecting an already-issued HTTP request do not
supply that missing guarantee.

Actual account/profile/permission/model modes, busy and multiple-child cases,
complete lineage identity/effects, native child continuation, and internal
orphan classification/positive wake remain unverified. Post-release cancelled
children retain the existing unresolved/restart path until their exact
continuation is separately supported. T003, T004 and T030 remain open; this
investigation does not waive their acceptance criteria.

### Verification and closure

Earlier canonical snapshots passed **25 missing-parent probe tests** and
**28 loopback probe tests**. The latter predates final routing, continuity,
interrupt and crash-cleanup changes and is not final-candidate validation.
Its private JUnit `native-loopback-probe-tests-20260918.xml` has SHA-256
`ed5a28eed53264d338047be08cc74db46999865e5b31654f3a733083255853b2`.

The final combined canonical suite was **NOT RUN**: `tests/run.sh` remained in
its mandatory pre-lock wait behind unrelated live pytest processes. Only this
investigation's queued waiters were cancelled, before pytest started; no final
JUnit or background waiter remains. The final four Python source/test files
passed syntax compilation, and all eight probe/test/document files have zero
trailing-whitespace findings. This does not substitute for the pending suite:

```sh
tests/run.sh -k 'test_lane_managed_probe or test_lane_managed_loopback_probe' \
  --junitxml="$PROBE_JUNIT_PATH"
```

Final loopback test SHA-256:
`4e150e267b2b736c6298c59463e7c08329be1ff902c347f0c9442c0b43429da2`.
Private `stage1-manifest-20260918.json` contains full source/artifact hashes,
commands and validation status; its SHA-256 is
`a4b41b96fcace355a1dceafac99ebe43105e669a2817806b995d39c8a14558f9`.
Source hashes remained unchanged across final runtime execution. No new probe
container remains. The unrelated pre-existing exited container was untouched.

The bounded Stage 1 investigation is closed with a viable experimental
candidate, an explicit pending-test gap, and full Gate 0 still open. Existing
feature changes are preserved; no production source edit, commit, merge,
installation or deployment was performed in this investigation.

### Subsequent unit-test closure, 2026-09-18

The next internal transaction implementation step ran the pending final probe
tests through the canonical serialized wrapper. A loopback test-fixture bug
was corrected by patching the helper's actual globals mapping; the probe
implementations remained unchanged. Both probe modules now pass **64 tests**.
The [verification record](../../../specs/001-separate-swap-ctx-handoff/verification.md#internal-coordinator-interrupt-implementation-2026-09-18)
records the source/test hashes and JUnit evidence. This supersedes the pending
unit-test gap above, without changing any runtime observation or closing Gate 0.

### Reproduction

Run the probe inside the declared development bench with the existing isolated
SDK interpreter and a locally available image. Choose a new private output
path for each invocation; the harness refuses to overwrite reports.

```sh
python3 tests/probes/managed_native_loopback.py \
  --sdk-python "$PROBE_SDK_PYTHON" --image "$PROBE_BENCH_IMAGE" \
  --control-mode stopped --release-target --output "$PROBE_REPORT_PATH"
```

Use `--control-mode crash-left-unfinished` for the unfinished-source control,
or `--control-mode interrupt` for documented coordinator-wide interruption
instead of task-specific `stop_task`.
`--release-target` sends one explicit test query only after the target-held
window; its requests and continuity observations are recorded separately.
Omit that option for an initialization-only target. The scripted endpoint
retains bounded metadata and continuity booleans/digests, not request bodies.
These commands exercise the selected native CLI protocol, not the installed
lane command or the complete SDK client lifecycle.
