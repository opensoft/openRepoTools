# Swap rebuild — implementation handoff

## Current September 22 direction

The approved [stop-then-resume-v1 decision](../../openspec/changes/separate-swap-ctx-handoff/stop-then-resume-decision.md)
and [contract](contracts/stop-then-resume.md) supersede the strict-only scheduling
below. Work stays in this feature/worktree with Astra architecture, Sol High
sole test execution, and Luna Max implementation. Implement the bounded v1
experiment before broad public lifecycle changes; target creation must happen
only after explicit release. Preserve strict-mode evidence and old records.
The independent native unenroll ownership-conflict fix remains in scope.
Current results and concrete blockers belong in `verification.md` and
`live-validation.md`; no installation or live canary is implied.

V1 checkpoint: its probe and regression tests are implemented. The frozen
candidate passed 113 focused tests, then ran explicit-release, unknown-effect
and withheld-release arms against SDK 0.2.153 / CLI 2.1.273. Release ordering,
saved-edit preservation and refusals were observed. A startup task event blocked
the extra history query; exact parent history and native child recovery remain
unproven. Parent termination was harness-enforced, not natural graph shutdown.
Use the final hashes and scope in `verification.md`; the public v1 lifecycle,
unenroll correction, broad regression gates and installation remain undone.
Do not remove the task-event guard or revive strict held-load requirements to
make this result look successful. Correlate the event/history and establish
the supported source containment domain before public integration.

Follow-up checkpoint: the startup-event/history diagnostic now passes **137
focused tests** and has one new isolated release run. Startup reported a stopped
task matching source session/task, but omitted the source's tool-use identity;
agent identity remains absent. Parent and candidate-child original file prefixes
were preserved. Candidate child attribution, exact runtime loading and complete
source containment remain unproven, and the query guard stayed closed. See the
final hashes and durable `openrepotools-sol-t003-t004-sidecar.e63Nfv` evidence in
`verification.md` and `live-validation.md`. No more diagnostic helper work is
needed merely to repeat this observation: next establish authoritative native
identity/history joins and post-release reconciliation, with the source-domain
proof still required. Public v1 and activation remain blocked.

## 2026-09-21 takeover

Published checkpoint: `5e940f00ec4b1d82dc9be0510b94b881316db631` on
`origin/001-separate-swap-ctx-handoff`. A subsequent T012 fixture correction
publishes the supervisor runtime identity before simulated owner takeover;
the five fence cases plus native-swap integration now report **19 passed**.
See `verification.md` for frozen artifacts and limits. T012 remains open.
The next unblocked diagnostic slice is the 12 native-worker observation
integration failures (watermark and source-operation binding); native ctx
still needs the contract/emitter work below. Keep the broader 34-failure run
as historical evidence, not a count recomputed from this focused success.

The user authorized continuation in the existing feature worktree. See the
[takeover record](../../openspec/changes/separate-swap-ctx-handoff/takeover-2026-09-21.md)
for preservation evidence, current role ownership, the refused workspace-log
publication, and proposed sibling integration order. The September 18 agent
assignments and diagnostic counts below are historical, not current claims
or evidence that those agents are still writing. Current test results belong
in `verification.md`; runtime support remains unverified.

Current continuation order (supersedes the older assignments below):

1. Use the September 21 frozen managed diagnostic in `verification.md` as the
   failure census; do not add together counts from distinct overlays. The
   takeover's production fixes preserve original hashed source archives and
   accept either child-start event order while retaining admission authority.
2. Resolve the ctx-specific pre-shutdown worker-clear evidence contract and
   establish an authoritative runtime emitter before implementing native ctx.
   The exploratory draft was preserved privately and removed from the candidate;
   positive ctx/restoration tests remain required. Do not substitute swap proof
   or post-shutdown adoption proof for this missing observation.
3. Resolve remaining managed and legacy failures, then run T027/T028/T029 from
   one frozen source using the serialized wrapper. The user's isolated-mode
   authorization covers diagnostics only, not release acceptance.
4. Have the workspace owner resolve the unrelated workspace merge before
   retrying the sanctioned takeover-log publication. No hand-written registry
   or workspace-config repair is authorized.

No task closure, production capability, installation, or merge is claimed.
Commit/push authorization covers the published checkpoints above, not release.
The preserved September 18 instructions below
describe their historical snapshot, not current writer assignments.

## Preserved 2026-09-18 checkpoint

Date: 2026-09-18. Active implementation checkpoint; not paused.
This is a repository implementation checkpoint, not a lane binding or a
replacement for the workspace's formal lane-handoff record.

## Resume here

Continue in branch `001-separate-swap-ctx-handoff`, in the sibling worktree
`../openRepoTools-worktrees/001-separate-swap-ctx-handoff` relative to the main
checkout. Do not implement in the main checkout. The worktree contains extensive
inherited modified and untracked files: preserve all of them. No commit, push,
reset, stash, install, or additional test run was performed for this wrap-up.

Read [plan.md](plan.md), [tasks.md](tasks.md),
[verification.md](verification.md), [live-validation.md](live-validation.md),
and the active OpenSpec change `separate-swap-ctx-handoff` before resuming.
The latest counts below supersede the earlier correction snapshot at the top
of verification.md; older results remain historical evidence, not waivers.
The checkpoint is not an authorization to claim runtime support or final
acceptance. Keep the worktree's inherited dirty state intact.

Current bounded ownership is active: root coordinates the implementation;
Astra is architecture lead and read-only contract reviewer; Sol High is the
orchestration/evidence and test executor; Luna Max is the implementation
writer for the defined Speckit tasks and contract/handoff documentation.
Additional bounded Luna roles are `Luna_children` for pure-module child
observation/restart-slot contract consistency and `Luna_packaging` for
packaging/help/legacy-alias assertion wording. These are documentation and
pure-module coordination roles only; they do not claim production capability,
test completion, or task closure.
Count live writers before assigning overlapping source or test edits, and do
not infer that an agent has stopped from an old pause note.

## Overall position

Implementation and contract work is substantial, but integration validation
is incomplete. Task closure is **8/32 Speckit tasks** (the snapshot-scoped
offline closures T005, T006, T007, T008, T022, T025, T026, and T030).
Governance closure remains separately tracked; no additional governance
approval is claimed here. These are closure counts, not an estimate of
engineering percentage complete. No native/runtime acceptance checkbox was
closed by this checkpoint.

The three current tracks are:

1. Busy-parent runtime evidence: bounded probe and unit tests complete;
   production support remains inconclusive.
2. Durable held-target adoption: transaction and crash-recovery implementation
   present; both adoption test modules pass. No production evidence provider
   is wired and no runtime adoption/release is enabled.
3. Prior controller/daemon regression migration: in progress. The retained
   prior focused run had 12 failures; consult `verification.md` for the
   current T028 and six-stage diagnostics. Final combined managed validation
   remains outstanding.

The latest active evidence is a clean **65-pass controller consumer/history
slice**, while the SDK child/no-send gate remains **229 passed/3 failed** and
the six-stage fixture-10 gate remains **26 passed/7 failed**. These are
diagnostic overlays, not acceptance or new task closures; the child fixes are
approved for rerun and the six-stage native-key/legacy-collector fixes remain
active. The new native-swap integrity path was not included, and authenticated
account validation remains not run. See `verification.md` for artifact paths,
full hashes, and the invalidated partial checkpoints.

## Changes already in the worktree

- `tests/probes/managed_native_loopback.py` and
  `tests/test_lane_managed_loopback_probe.py`: opt-in
  `--busy-parent-before-control`, exact Agent request barrier, sticky request
  epoch through target hold, precise completion attribution, bounded cleanup.
- `lane_managed_state.py`, `lane_managed_controller.py`,
  `tests/test_lane_managed_adoption_transaction.py`, and
  `tests/test_lane_managed_target_adoption.py`: bounded schema-2
  `native-adoptions.json` ledger, immutable bindings, durable phases
  prepared → claim-cas-pending → claim-transferred → controller-committed,
  exact claim CAS, and crash recovery without replaying uncertain CAS/runtime
  actions. Controller metadata stores a compact reference. Target is an
  ownership descriptor only; source history stays fenced and intact.
- Internal `_native_adoption_evidence_provider(binding)` constructor seam:
  absent by default, exact binding plus digest/reference and five literal-true
  proofs required. Never accept this provider through a request or probe.
- Controller `recover()` permits empty participant evidence only for validated
  unenroll mode and reconciles the trusted claim index; other modes stay strict.
- `_safe_runner_projection` accepts the exact SDK `RunnerSpec` type and omits
  17 non-durable slots only at canonical type-preserving defaults. Raw mapping
  environment/settings remain forbidden, including empty/null values;
  subclasses, lookalikes and non-default runtime controls get no exemption.
  Validated `supported_models` is configuration, not capability evidence.
- Swap-only reserved-to-written promotion requires the exact written UUID and
  exactly one trusted holder with profile/workspace/process-group ownership.
  Revalidates the resume spec before persistence/open. Missing, ambiguous or
  foreign holders and explicit fresh fallback refuse.
- Controller/daemon fixtures migrated toward coordinator-only native startup,
  real ownership claims, intent-before-open, explicit dispatch and no uncertain
  replay. Controller release does NOT dispatch inline: the public daemon
  release route owns one bounded pump tick.
- Added `tests/test_lane_managed_runner_projection.py` and
  `tests/test_lane_managed_reserved_transition.py`.
- Updated plan, data model, OpenSpec design and contracts, including
  [busy-parent-probe](contracts/busy-parent-probe.md),
  [native-adoption-transaction](contracts/native-adoption-transaction.md),
  [managed-control](contracts/managed-control.md), and
  [transcript-preflight](contracts/transcript-preflight.md).

## Retained test evidence from the prior checkpoint

Artifacts below are private temporary directories under the `py-bench`
container's temporary root; availability is not durable. Preserve hashes and
do not silently replace an old result with a new one.

The current T028 rerun and six-stage diagnostic are recorded in
[verification.md](verification.md); the table below is retained historical
evidence and is not the current acceptance result.

| Run | Result | Artifact | JUnit SHA-256 |
| --- | --- | --- | --- |
| Controller, daemon, target-adoption, adoption-transaction, reserved-transition | 257 passed, 12 failed, 1449 deselected | `openrepotools-five-module-focus.v4Yg5s/focused.xml` | `715dcbb1576e1417c00d6a484de24e49d58f39eaabf499180a9e8947cbebf467` |
| Runner projection | 45 passed, 1718 deselected | `openrepotools-runner-projection.5EdUFr/` | `dceed96eb3d6f1923d14abc69e96faa4216b8e0fa44315d156adace59af125dc` |
| Corrected probe units | 80 passed, 1629 deselected | `openrepotools-probe-unit-rerun.czlgLB/` | `0370573721966caa9a69e76c0a153196ffd1a3e772049d92ade8e53fca38b046` |

Selected manifests were unchanged across these runs. Both adoption modules
passed in the focused run. Do not add counts from different snapshots into a
single claimed green suite. Latest combined managed validation and final
strict OpenSpec validation are outstanding.

## Exact remaining failures and starting diagnoses

### Five reserved-transition tests — clear fixture defect

`_reserved_roster()` returns `_swap_roster(...)` directly, whose third return
value is a Participant, not the runtime. New tests unpack it as the runtime
and fail on `.opened` or `.calls`. Return `(controller, store, runtime)` using
the helper's locally constructed runtime, without changing the base helper.

- `test_swap_promotes_written_reserved_target_before_persist_and_open`
- `test_explicit_fresh_against_written_history_refuses_before_runtime`
- `test_written_fresh_without_exact_holder_refuses_before_metadata_mutation`
- `test_written_fresh_with_ambiguous_holder_refuses_before_runtime`
- `test_written_fresh_with_foreign_holder_refuses_before_runtime`

### Two controller tests — inspect contracts before changing assertions

- `test_recover_open_adopts_target_runner_spec_and_persists_profile_evidence`:
  actual phase `starting`, expected `ready-held`. This is an older mixed-roster
  recovery test with worker-b still pending; an overbroad expectation edit is
  suspected. Preserve accepted-open/no-replay assertions.
- `test_start_prevalidates_fixed_roster_and_records_ready_held_without_dispatch`:
  missing `intent["spec"]["fingerprint"]["lineage_context"]`. The prepared
  readiness spec and persisted launch-intent spec may differ by stage. Decide
  whether the binding is genuinely missing or the assertion targets the wrong
  representation; keep intent-before-open and identity checks.

### Five daemon tests — likely shared dispatch identity issue, not yet proven

- `test_real_controller_coordinator_busy_then_idle_dispatches_once_after_release`:
  message is `queued`, expected `fenced`, after explicit release and submit.
  Check released-state semantics; retain busy-no-send and idle-exactly-once.
- `test_real_controller_uncertain_dispatch_is_not_replayed_automatically`:
  `stale-generation` arrives before expected `uncertain-effect`.
- `test_real_controller_stale_generation_after_await_fence_blocks_send`:
  timeout waiting for resolver barrier.
- `test_real_controller_dispatch_releases_store_lock_before_runtime_await`:
  timeout waiting for send barrier.
- `test_public_cli_socket_uses_real_controller_for_held_release_and_one_ack`:
  release succeeds but no coordinator delivery before explicit pump.

Investigate the latter four together: `_native_start_body` uses incarnation
`daemon-native-runner`, while the fake runtime may expose `runner-coordinator`.
This is a hypothesis, not a diagnosed production bug. Inspect the early task
exception/pump diagnostics before waiting on barriers. Do not lengthen timeouts,
weaken stale-generation checks, change expected errors without reaching send,
or add inline dispatch to controller release.

## Busy-parent runtime evidence and limits

Exactly one corrected runtime run used SDK **0.2.153**, bundled CLI **2.1.273**,
with `--control-mode interrupt --busy-parent-before-control --release-target`.
Executable SHA-256:
`6c752e2cc7c110c9df15f26d8d134d438c5ae95dbd610efc1a308bf7f9c5f6c1`.
Private report `openrepotools-busy-parent.MfKev7/report.json`, SHA-256:
`bd463d8fc4f0daa189b1cc11341e1f5309358dd2395e795a4c8c78cb2ed696b0`.

The probe ran with no network, no host mounts, no real credentials, and a
scripted loopback. Sandbox removal succeeded. It observed the exact pending
parent Agent continuation request, child/Bash liveness immediately before
entry (not atomically at entry), zero new requests through target hold,
interrupt/terminal/process-exit facts, and no forced cleanup. A post-release
request carried source and Agent history with the same observed session UUID.

It did NOT prove blocked-response cancellation, exact parent load while held,
completed-source continuity, child-header/task correlation, worker-state clear,
or orphan clear. Positive orphan handling was not exercised; the inspected CCR
path needs authentication. `eventual_continuity_observed=false`,
`continuity_scope=eventual-history-only`, `support_claim=false`, verdict
`inconclusive`. Do not invent flags, edit transcripts or fabricate evidence.
No repeat probe is needed merely for fixture corrections.

## Historical executor mapping — superseded by active ownership above

The role names remain authoritative, but the individual executor mapping
below belongs to the earlier checkpoint and must not be treated as a current
assignment. Use the active ownership block above and coordinate before any
overlapping edit. Use Codex-platform models only, following the existing
multi-model protocol.

- Sol / Erdos (`01a0b4d0-1fa7-78d0-be07-2cadff50ab76`): sole test executor,
  frozen manifests, evidence documentation.
- Newton (`01a0b4d0-2008-7e41-8bb8-1257df0631fb`): controller production and
  reserved-transition tests.
- James (`01a0b4f2-6e7e-7162-bcc7-36070fae58e9`): controller test corrections.
- Locke (`01a0b4d0-2066-75b0-bfff-64e325beca72`): daemon tests; coordinate any
  real production fix with Newton, never concurrent writers on one file.
- Jason (`01a0b4d1-5929-77c1-9396-97b8a3f359fc`): state/projection tests,
  available for independent bounded verification.

Fix the three independent failure groups in parallel, then freeze all selected
dependencies and let Sol run the canonical wrapper inside `py-bench`:

```sh
tests/run.sh --parallel-safe -k 'test_lane_managed_controller or test_lane_managed_daemon or test_lane_managed_target_adoption or test_lane_managed_adoption_transaction or test_lane_managed_reserved_transition or test_lane_managed_runner_projection' --junitxml=<private-output-file>
```

User previously approved isolated mode. Never invoke pytest directly or pass
positional test filenames to the wrapper. Once focused green, run the prior
combined managed selector plus all four new modules (target adoption, adoption
transaction, reserved transition, runner projection), reconcile the original
20 failing nodes including renamed equivalents, and record exact results.
Do not select the unrelated slow lane-helper suite accidentally. Finish strict
OpenSpec and whitespace validation. Close tasks only against full acceptance.

Do not test with real accounts, production credentials, real repositories, or
new runtime authority. Native children are not independent runners/mailboxes;
native swap/ctx/release/restore/continuation support remains gated. Do not
modify the pinned upstream submodule, workspace pointer, or lane registry by
hand. This checkpoint does not authorize launching or respawning a session.
