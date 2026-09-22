# Fastest path to deployment

## Current direction: stop-then-resume v1

Brett subsequently approved implementing the
[stop-then-resume recommendation](../../openspec/changes/separate-swap-ctx-handoff/stop-then-resume-decision.md).
This supersedes the earlier guarantee-preservation scheduling decision below
for a new explicit v1 mode only. Strict mode and its historical records retain
their full guarantees and upstream requirements.

V1 first needs its own isolated runtime experiment with saved edits, unfinished
child/tool work, source exclusion/effect accounting and **no target creation
until release**. The existing probe's `--release-target` sends a later query;
it does not defer process creation and cannot be reused as v1 acceptance.
Then implement mode-specific preparation, release-authorized exact startup and
recovery against the measured boundary. Unknown source writers/effects remain
a blocker even though pre-release target held-loading is no longer required.

The native unenroll ownership-conflict correction remains an independent
prerequisite under T014/T024; it is deferred until after the first v1 experiment.
All subsequent regression, sibling integration, platform CI,
authenticated canary, installation and rollback gates below still apply.
No live account, lane or install destination has been selected by this approval.

The first v1 experiment is now implemented and executed: 113 focused tests
passed; three isolated arms demonstrated release-before-start ordering and
refusal behavior. Restoration remains inconclusive because target startup
emitted a task event and the probe correctly sent no additional history query.
See [live-validation.md](live-validation.md). Next establish source containment
and correlate startup child/history evidence, then implement the public
mode-specific lifecycle. No public option, production activation or deployment
is claimed by the probe.

The startup-event/history follow-up is also implemented and measured: **137
focused tests** pass, and the new isolated release run preserved the measured
history prefixes. The startup stopped notification matches source session/task
but lacks the source tool-use join; child identity and runtime restoration stay
unverified. Continue with authoritative joins, startup reconciliation and source
containment, not another uninstrumented quiet-window run. Evidence is in
`live-validation.md`; the public lifecycle and downstream release gates remain
unchanged.

## Earlier September 22 execution sequence (strict mode)

The user requested implementation of the completion/deployment plan on
September 22. This section supersedes the historical scheduling checkpoints
below; [tasks.md](tasks.md) remains the only executable task list. Existing
architecture and capability requirements still apply.

The user subsequently chose to preserve the guarantees, prepare the
[upstream runtime requirements](../../openspec/changes/separate-swap-ctx-handoff/runtime-support-requirements.md),
and leave activation blocked until supported. Continue independent offline
corrections and retain the deployment sequence below as gated future work.
No guarantee reduction, authenticated canary, or installed cutover follows
from this decision.

Lane `swap-rebuild-codex` holds this OpenSpec change through the sanctioned
workspace claim at `3577c1154efb20d208033e2a17b50c6e99dff409`.
Astra owns architecture review, Sol High owns orchestration and test execution,
and Luna Max owns implementation. Use Codex models in this execution. Keep
requests bounded, reuse these roles, and attach evidence to existing task IDs.

1. Verify the inherited transport-accept and historical-swap shutdown fixes
   with the worker/pump/persistent-lifecycle/swap/fence diagnostic on one frozen
   snapshot. Preserve uncommitted work and distinguish this result from the
   earlier 34-failure census. Sol is the sole test executor.
2. In parallel, establish whether supported runtime observations can satisfy
   worker/orphan clearing, run completion, exact parent loading while held,
   and continuous dispatch observation. Astra records a concrete supported
   interface or the missing boundary. Repeating quiet probes cannot establish
   an absent observation. Native ctx needs its own pre-shutdown evidence.
3. Complete native child semantic routing and durable coordinator transport
   bindings under T013/T018, then the remaining swap/release/recovery and
   ctx/restoration tasks against the established runtime contracts. Preserve
   pending entries and exact retries; unavailable routing refuses before send.
4. Agree one lifecycle authority and migration/landing order with recovery
   PR #97 and supervised-context PR #121. Both were open and conflicting at
   the planning read. Reconcile the semantic transition conflict before
   resolving textual merges. Command migration and external integration
   decisions remain explicit entries in the governance review.
5. Freeze the resulting candidate and run T027/T028/T029 through the serialized
   `tests/run.sh` in the declared bench, with the pinned submodule present.
   Isolated diagnostics remain diagnostics. Require platform CI, requirement
   reconciliation, and bounded real-account evidence for T031/T032.
6. Review and merge in the agreed dependency order. Rehearse installation and
   rollback in a disposable environment, then install the exact merge revision
   from a clean checkout of that revision with
   `OPENREPOTOOLS_REF=<merge-sha> ./openRepoTools --install` in the selected
   canary scope. The installer itself must come from that revision: an older
   installed command has an older file inventory even when its fetch ref is
   changed. Include commands, Python modules, skills, hooks, and settings
   in inventory verification; bin-directory isolation alone is insufficient.
7. Expand only after canary swap/release/recovery and legacy checks pass.
   Record installed revisions, runtime pins, destinations, and results before
   archiving the change. Rollback preserves journals and claims and uses
   tooling compatible with the durable state.

Named disposable accounts, lane, permitted effects, and installation destination
must be established before their corresponding live actions. This execution
request does not select those missing values or make unknown runtime evidence
true. The first scheduling milestone is the focused candidate result and
Astra's feasibility decision; completion requires passing release gates and
verified installation.

## Historical planning and checkpoints

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
