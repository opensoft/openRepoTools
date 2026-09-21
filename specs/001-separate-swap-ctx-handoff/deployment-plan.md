# Fastest path to deployment

Date: 2026-09-17. Execution sequence for the existing feature
`001-separate-swap-ctx-handoff`; [tasks.md](tasks.md) remains the sole
implementation task list. This plan does not authorize deployment or change
the approved native-subagent architecture.

## Starting point

[Verification](verification.md) remains **INCOMPLETE — LIVE UNVERIFIED**.
Native admission has an internal seam but is not yet integrated into normal
native start/dispatch. Lifecycle replacement, recovery, ctx and release remain
incomplete. The recorded 129 CLI passes and one wrapper hygiene pass establish
limited local evidence; they do not establish feature readiness. All 32 Speckit
tasks were unchecked at planning time; that was an evidence backlog, not proof that no code
exists. Earlier percentage estimates should not be used to schedule deployment.

The critical path is **runtime feasibility → public native swap → release and
recovery → regression and live evidence → installed canary → rollout**.

Execution update: the reproducible no-auth initialization probe succeeded in
an isolated sandbox, but Gate 0 remains **inconclusive** because the orphan
positive control and supported terminal-stop/clear case were not exercised.
Astra's implementation decision is to complete the public capability-refusal
path before source disruption, continue independent state/packaging fixes,
and hold successful native stop/restore integration until its runtime boundary
is established. This preserves the approved feature scope. Detailed results
belong in [verification.md](verification.md) and [live-validation.md](live-validation.md).

2026-09-18 Stage 1 update: the bounded scripted gateway investigation found a
viable coordinator-wide `interrupt` candidate: real native task/tool stop,
zero source-control requests, exact parent held resume with zero requests,
and preserved UUID/history after explicit release. Task-specific `stop_task`
still produced a request after the parent turn settled. An authentic
unfinished-source crash control also resumed quietly after fixture-process
exclusion. This advances feasibility without closing full Gate 0. The next
governed design step is now captured in
[coordinator-interrupt.md](contracts/coordinator-interrupt.md) and its
[decision record](../../openspec/changes/separate-swap-ctx-handoff/coordinator-interrupt-decision.md).
The first implementation slice is the internal durable whole-roster
authorization/drain transaction with fake-runtime, real-store and IPC tests;
it does not replace task-specific authority or enable public success. Actual account
modes and the remaining runtime/lineage gates still precede enabling swap.
See [the Stage 1 disposition](../../openspec/changes/separate-swap-ctx-handoff/stage1-runtime-boundary.md#architecture-disposition).

Implementation checkpoint: T025 packaging/wrapper acceptance and T026
documentation alignment are complete. The internal native stop transaction
now spans durable controller records, daemon callbacks and SDK transport;
acknowledgement, task termination, tool/effect quiescence and restore-state
clearing remain separate conclusions. The frozen managed census is
**735 passed, 16 failed**, including **49 passing stop-path tests**, with no
changes to its 36 hashed files during validation. Remaining failures are
11 controller and 5 daemon lifecycle cases; none is waived. See
[the frozen result](verification.md#frozen-follow-up-result) for artifacts and
limits. The selected-runtime missing-task stop succeeds without a terminal
event, reinforcing that an acknowledgement cannot establish safe restore.
No deployment has occurred.

The next offline integration package is coordinator-only public native start:
one coordinator runner and lineage claim, durable context before release or
admission, and no separate child runners/mailboxes. This precedes replacing
the remaining prototype lifecycle and dispatch paths. Runtime feasibility
remains the first release gate; neither this package nor internal stop tests
can certify held restore without the required selected-runtime observations.

## Ownership and parallel work

### 2026-09-18 dependency audit before lifecycle integration

The latest bounded offline batch passed 54 new tests; its combined census
was 878 passed and the same 20 existing failures. These results validate the
observational drain projection and internal claim CAS, not target adoption.
See [verification.md](verification.md) for the frozen evidence.

Inspection before the requested source-history/adoption, restore/recovery,
and release/ctx integration identified prerequisites that remain open under
the existing runtime gate:

- The SDK-generated request observation is explicitly unobservable, with an
  unknown request count. Local invocation watermarks do not establish the
  required external-control-entry-to-release observation interval.
- The adapter validates supplied worker-state-clear observations but exposes
  no supported operation or observation producer proving that durable runtime
  worker state has been cleared. Process-group exit is not that evidence.
- Generic post-release send acceptance is available, but native restart
  attempts and old/new task correlation are not implemented. Acceptance cannot
  become `restarted` or `exact-resumed` without those joins.
- Native source records still validate against the active context. History
  preservation and target adoption need a durable intent and a reconciler:
  the claim index and controller record are separate atomic writes, even when
  both occur under the same lock. An exact target claim may support finishing
  a recorded adoption; missing, duplicate or mismatched claims must remain
  indeterminate, never cause another open or blind CAS retry.

These are dependencies within the existing Speckit tasks, not a new task
list or permission to relax the zero-request or startup gates. The runtime
boundary must be established before enabling successful native restoration;
offline history/adoption work alone cannot close it. No implementation task
was closed by this audit and no runtime experiment was run.

Astra owns architecture and the runtime support decision. Sol High owns
sequencing, file ownership, integration and release evidence. Luna Max writes
the defined implementation tasks. These are the existing role assignments;
use Codex models in this Codex session. These roles were dispatched during
implementation, as recorded in the verification evidence. The product's SDK runtime is separate from the
platform used to develop it.

Sol should assign disjoint files and one integration owner before dispatching
work. Do not let multiple writers edit the controller, daemon or SDK adapter
at the same time. Begin with these independent streams:

| Stream | Existing tasks | Deliverable |
| --- | --- | --- |
| Runtime evidence | T001–T004; execute T030 early on a frozen probe snapshot | Actual native events and a supported held-restore boundary |
| Durable state | T005–T008 | Schema-v2 and atomic lineage claims against agreed contracts |
| Compatibility and packaging | T023–T026 | Legacy exclusion, complete installer inventory and accurate help |

Move Luna's implementation capacity to lifecycle integration as soon as the
runtime contract is established. Resolve uncertainty with Astra rather than
building competing lifecycle implementations.

## Ordered exit gates

1. **Establish runtime feasibility first.** Run the selected-runtime controls
   in [live-validation.md](live-validation.md), using the declared execution
   environment and its exact SDK-selected CLI, version and full digest.
   Demonstrate the positive orphan-wake control, then supported terminal
   stop/state clearing and held parent restore without wake or model dispatch.
   Missing credentials or a failed model request is not proof of no dispatch.
   Record a support decision before expanding controller work. If the runtime
   cannot meet this contract, Astra identifies a supported runtime path or
   raises a governed scope decision; do not ship the old independent-worker
   design as this feature. Unsupported paths must refuse explicitly.

2. **Complete one public swap path.** Integrate T009–T014 through the actual
   CLI/socket/daemon/controller boundary with temporary state and a fake
   runtime first: admitted native child → fence → proven child/tool stop →
   old writer excluded → exact parent restored under the target account,
   held. Use the same path later for live validation. Demonstrate refusal
   with claims retained when stop, identity or external effects are uncertain.
   Centralize fixture migration around the approved native contract; separate
   obsolete prototype expectations from real implementation defects. Review
   weakened assertions and restore meaningful bounds and precise outcomes.

3. **Close the remaining behavior.** Finish T015–T022 against that integrated
   path: explicit release, observed continuation or correlated at-most-once
   restart, bounded supervision, ctx and checkpoint-only handoff. Prove retry
   and crash recovery cannot duplicate writers or replay completed work.
   Account for all requirements in the same feature; narrowing scope requires
   a recorded governance decision rather than silently skipping tasks.

4. **Freeze and validate the candidate.** One executor runs T027–T029 using
   the canonical wrapper, with the pinned submodule present. Preserve JUnit
   results and source hashes. Run the expensive legacy selector after its
   fixes freeze, then the full serialized suite; rerun affected checks after
   fixes and ensure final evidence describes the final candidate. Verify
   platform CI, Bash 3.2 compatibility and installer inventory. Complete
   T031's authenticated gates only in explicitly authorized disposable
   profiles/lane, then reconcile every FR/SC under T032. No live-support claim
   may be based only on fake-runtime tests.

5. **Install a canary, then roll out.** Review and merge the verified feature.
   This repository deploys installed commands and skills through
   `openRepoTools --install`. First exercise the complete installer in
   disposable directories; isolating only the bin directory is insufficient
   because it also places skills, commands and settings. Install the exact
   reviewed merge revision into the approved canary scope and verify installed
   file hashes, command resolution, help, managed swap/release and legacy
   behavior. Expand only after the canary evidence passes. Record revision,
   installation scope, runtime digest and validation result as deployment
   evidence; a merge alone is not deployment.

## Concurrency and turnaround

Parallelize implementation and small focused tests, with at most two focused
test processes initially and one test coordinator. The existing opt-in
`tests/run.sh --parallel-safe` isolates ambient paths but does not cap resource
use. Two short passing runs do not prove that heavyweight suites can safely
overlap. Keep legacy/full suites serialized and avoid launching focused jobs
beside them. Stop increasing concurrency if durations or timeouts worsen.
Retain the canonical guard; do not bypass it with direct pytest invocations.

Use a failure census to fix shared contract/fixture causes once, rather than
rerunning the whole suite after every assertion edit. Do not loosen tests to
match incomplete behavior. Record task completion only with relevant evidence.

## Release scope and rollback

Before authenticated execution, name the disposable source/target profiles,
lane and permitted effects. Before installation, name the canary destination
and affected configuration. Existing sessions are outside that scope. Obtain
any missing authorization against this concrete scope after preparation.

Retain the last known-good installed inventory and affected configuration.
If a canary fails, preserve its journal and claims, fence/quiesce managed work,
and restore compatible tooling/configuration through the supported installer
path. Do not clear ownership records, downgrade schema-v2 state or resume an
old runtime merely to make rollback appear successful. If the previous
release cannot interpret that state, leave managed operations disabled and
recover with compatible tooling. Prove this procedure in the disposable
installation before rollout.

The next useful scheduling checkpoint is the Gate 0 result plus the native
integration failure census. Until then, a deployment date would hide the
largest uncertainty. Report gates completed, tasks with evidence and the next
blocking dependency instead of an unsupported percentage.
