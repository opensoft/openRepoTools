# Tasks: Native-Lineage Account Swap and Session Operations

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`,
and `openspec/changes/separate-swap-ctx-handoff/`.

**Tests**: Required. Fake and local no-auth runtimes use serialized
`tests/run.sh`; no task authorizes a real account/profile swap or network/model
request. Live validation remains `NOT RUN — UNVERIFIED` until an authorized
experiment completes and its evidence is assessed.

**Current Bite 4 status (2026-09-24)**: The one-run fourteenth
authorization has been consumed. Its result is INCONCLUSIVE with positive
reason `target-history-query-result-incomplete`; the query saw one extra
parsed frame, so no PASS or known FAIL was established. The negative arm did
not run solely because of `positive-cleanup-incomplete`. Zero labeled
containers and four unattached old/new source/target volumes remain preserved.
No further run, cleanup, retry, or deployment is authorized. Bite 5 remains
pending and production unsupported. See `verification.md` for sealed hashes
and the full frame evidence.

The coordinator-wide interrupt contract is test-first within the existing
task set: T009 defines the durable/fake-runtime cases, T010–T014 implement
and recover them, and T027 verifies the focused suite before T030 performs any
authorized selected-runtime observation. No task below treats a synthetic
interrupt as runtime support.

**Architecture**: One exact top-level coordinator owns a native child lineage.
Children use actual Agent/task evidence, not fabricated top-level UUIDs, process
groups, mailboxes, or runner APIs. Swap control makes zero model requests.
`exact-resumed` and `restarted` require correlated post-release evidence.

## Phase 1: Native Evidence and Gate 0 Foundations

- [ ] T001 [P] Write SDK 0.2.153 lifecycle tests for durable Agent admission, real `SubagentStart`/`SubagentStop` and task-event shapes, nested children, reused IDs, stale terminal events, per-agent policy, coordinator-interrupt send-boundary authorization, independent readers, buffered parent-drain results, and actual offline/fake-runtime A -> B -> C acceptance after terminal proof with a separate runtime acceptance result. Cover admission races, released-phase and daemon-incarnation post-await fences, duplicate reservations, busy B retention, stale-A rejection, crashes at preparation/runtime-reservation/atomic-binding/send boundaries, and ambiguous-send/no-replay cases in `tests/test_lane_managed_sdk.py`, `tests/test_lane_managed_sdk_interrupt.py`, and `tests/test_lane_managed_native_interrupt_runtime.py`
- [ ] T002 Implement the bounded native-lineage ledger, actual hook registration, immutable child definitions, nested correlation, per-agent tool policy, current-invocation quiescence gate, and the implementation-owned versioned `prepare-invocation` control frame in `lane_managed_sdk.py`; bind its bounded deadline/request-response fields, complete joined-roster and independent-drain proof, runtime reservation sealing, A -> B -> C sequencing, duplicate-reservation idempotence, strict watermarks, and stale-event fences without treating it as a Claude API
- [ ] T003 [P] Write a selected-runtime Gate 0 harness with a positive orphan-wake control and a supported terminal-cleared no-wake/no-model candidate in `tests/test_lane_managed_gate0.py` and `tests/fixtures/managed-native/`
- [ ] T004 Implement exact SDK/CLI path-version-digest reporting and promptless startup detection in `lane_managed_sdk.py`; distinguish notification enqueue from model dispatch and never use undocumented flags or transcript rewriting
- [X] T005 [P] Write schema-v2 tests for every state/controller/daemon/socket/recovery reader and writer, plus preserved read-only same-family profile resolution; prove absent optional history/rollover collections remain compatible, while malformed history/rollover/source-archive records, invalid historical context/admission/control bindings, duplicate identities, and count/byte capacity overflow refuse before effects. Prove schema-v1 records remain byte-identical and are refused without child aliases, and prove coordinator-interrupt records missing their distinct roster/source-exclusion/authorization fields or native-stop records presented under that kind are refused rather than defaulted or migrated in `tests/test_lane_managed_state.py`, `tests/test_lane_managed_controller.py`, `tests/test_lane_managed_daemon.py`, and `tests/test_lane_managed_profiles.py` — snapshot-scoped offline foundation closure only; see `verification.md`. Native/runtime acceptance remains open.
- [X] T006 Implement explicit schema markers and fail-closed old-record boundaries across `lane_managed_state.py`, `lane_managed_controller.py`, `lane_managed_daemon.py`, and `lane-managed`; read absent schema-v2 history/rollover collections as empty but refuse malformed entries, invalid source/A context, bad integrity digests, non-ascending watermarks, duplicate identities, and named count/byte-capacity overflow. Retain credential-free read-only profile resolution in `lane_managed_profiles.py`, and keep the distinct coordinator-interrupt record shape fail-closed with no native-stop migration — snapshot-scoped CLI/schema implementation closure from the old frozen overlay; see `verification.md`. This does not validate the in-progress native-swap source.
- [X] T007 [P] [US3] Write lineage-level claim tests for a read-only coordinator with an authorized writable child, nested writers, isolated child worktrees, aliases/ancestor overlap, and two lanes in `tests/test_lane_managed_state.py` and `tests/test_lane_managed_controller.py` — snapshot-scoped offline foundation closure only; see `verification.md`. Native/runtime acceptance remains open.
- [X] T008 [US3] Implement atomic lineage claims and optional isolated-child worktree claims in `lane_managed_state.py` and `lane_managed_controller.py`; unknown child identity or capability retains/refuses the claim — snapshot-scoped offline foundation closure only; see `verification.md`. Native/runtime acceptance remains open.

**Checkpoint**: Native evidence is captured without opening a target account;
unsupported startup behavior is an explicit public refusal.

## Phase 2: User Story 1 — Zero-Model Exact Coordinator Swap (P1) MVP

**Goal**: Fence one native lineage, stop every current child/tool, exclude the
old coordinator process tree, and load the exact parent under the selected
account held, without a model request.

- [ ] T009 [US1] Write controller tests for a distinct `coordinator_interrupts` intent: the source admission fence epoch, complete sealed rosters including accepted-but-unjoined and nested admissions, immutable identity/seal watermarks, at-most-one authorization across duplicate/lost-ACK/restart/cross-ID retries, independent receipt/child/tool/effect/process/request facts, natural completion, graph drain before parent shutdown, old-tree exclusion, unknown-capability refusal before effects, exact parent resume, target readiness, held dispositions, and missing-parent refusal in `tests/test_lane_managed_controller.py`, `tests/test_lane_managed_coordinator_interrupt.py`, and `tests/test_lane_managed_interrupt_integration.py`
- [ ] T010 [US1] Replace independent participant orchestration with native-lineage swap intent, a distinct coordinator interrupt/drain record, complete-roster seal, ordered admission fence, and post-await fences in `lane_managed_controller.py`; do not model the whole roster as per-child `stop_task` calls
- [ ] T011 [US1] Integrate the documented coordinator interrupt, exact parent resume, and lineage evidence in `lane_managed_sdk.py`; retain independent native child/tool/effect observations and do not open, shut down, or release a fictitious child runner
- [ ] T012 [US1] Write public socket tests for `start`, `status`, `swap`, `recover`, `release`, `shutdown`, and `unenroll` using a real temporary `ManagedStateStore` and fake/offline SDK, including one coordinator open/release boundary, actual A -> B -> C mail after terminal proof with separate runtime acceptance, admission races, B queued while A is busy, released-phase/daemon-incarnation post-await fences, duplicate reservations, durable immutable history plus mutable binding, stale-A rejection, and crashes at each preparation, reservation, atomic-binding, and possible-send boundary without replay, in `tests/test_lane_managed_daemon.py`, `tests/test_lane_managed_cli.py`, and `tests/test_lane_managed_native_start_integration.py`
- [ ] T013 [US1] Route the native controller through the persistent supervisor and CLI in `lane_managed_daemon.py` and `lane-managed`, preserving deadlines, secure discovery, one event loop, observational status, daemon-owned bounded invocation rollover, one open/release boundary, and no controller lock across runtime await
- [ ] T014 [US1] Implement mode-aware recovery around coordinator interrupt authorization, child/tool/effect drain, parent shutdown, process exclusion, target open, readiness, final persistence, strict schema/history/source validation, separate mutable preparation/reservation/binding records, immutable A terminal history, exact terminal proof, released-phase/daemon-incarnation fences, stale-event rejection, and staged A -> B rollover crash boundaries in `lane_managed_controller.py` and `lane_managed_daemon.py`; perform model-free bounded reconciliation of an existing exact reservation with proven no-send and current authority, return that exact proven-unsent committed dispatch to the normal released daemon pump, which performs the already-authorized send at most once after fresh authority/reservation checks, and never independently issue or replay a model query, replacement reservation, or uncertain effect

## Phase 3: User Story 2 — Honest Native Worker Continuation (P2)

**Goal**: After release, prefer proven exact continuation and otherwise allow a
model-assisted new native run from durable task/definition facts, with no
written handoff.

- [ ] T015 [P] [US2] Write post-release exact-resume, new-run restart, missing-child-history fallback, completed-child, cancellation, partial-start, wrong-definition/model, and accepted-send-without-start tests in `tests/test_lane_managed_sdk.py` and `tests/test_lane_managed_controller.py`
- [ ] T016 [US2] Implement release-gated exact continuation and mechanically composed new-native restart through the coordinator/native interface in `lane_managed_sdk.py` and `lane_managed_controller.py`, preserving model, effort, tools, permissions, and custom definition
- [ ] T017 [US2] Persist `completed`, `resume-pending`, `restart-pending`, `exact-resumed`, `restarted`, and `unresolved` with request deduplication and at-most-once restart admission in `lane_managed_controller.py`
- [ ] T018 [US2] Implement bounded supervisor wake/pump behavior for eligible released work in `lane_managed_daemon.py`; accept at most one eligible same-runner A -> B transition per bounded pump pass (not a lifetime limit), permit later B -> C passes after fresh terminal proof, retain B queued while A is busy, recheck phase/daemon identity after awaits and before send, reject stale A events, and preserve durable history/reservations across crashes without replay or starvation
- [ ] T019 [US2] Expose lineage, task correlation, dispositions, claims, coordinator-interrupt receipt/drain evidence, uncertainty, and experimental Gate 0 status through `lane-managed status` and `lane_managed_daemon.py`

## Phase 4: User Story 3 — Distinct Context and Handoff (P3)

- [ ] T020 [P] [US4] Write native `ctx hold`, `ctx restart`, checkpoint-only handoff, concurrency, stale-generation, and claim-transfer tests in `tests/test_lane_managed_controller.py` and `tests/test_lane_managed_cli.py`
- [ ] T021 [US4] Implement `ctx hold` as stopped retained worker records and `ctx restart` as a new coordinator UUID/lineage ID with unchanged owner generation in `lane_managed_controller.py`; restart only after release from the caller checkpoint
- [X] T022 [US4] Implement checkpoint-only `handoff` without account, release, lifecycle, or implicit model effects in `lane_managed_controller.py`, `lane_managed_daemon.py`, and `lane-managed` — scoped offline real public socket/state/controller and handoff (FR024/SC007) closure; authoritative mode-preserving gate reported 319 passed, 0 failures/skips, JUnit `2c76ac58c1a3c8e20aa022a97ca161729136c54aaaf69e5520c80de5231b2bcf`; see `verification.md`. Native/runtime acceptance remains open.

## Phase 5: Legacy Ownership and Installation

- [ ] T023 [P] [US3] Add legacy tests for managed projection parsing, malformed/absent helper output, verified launcher lineage, pending `--no-launch`, remote ownership, and prompt-guard lineage validation in `tests/test_lane_helpers.sh`
- [ ] T024 [US3] Preserve atomic legacy/managed exclusion and LANES projection through `lane`, `lane-start`, `lane-handoff`, and `lanes-edit.sh`; enrollment publishes before launch and unenroll clears projection before local owner state
- [X] T025 Update installer all-or-none inventory, `lane-swap <lane> --profile <profile>` literal-lane collision coverage, and installed help in `openRepoTools`, `lane-swap`, `tests/test_openrepotools_command.py`, and `tests/test_lane_managed_cli.py` — 25 focused packaging/wrapper tests passed on 2026-09-17; see `verification.md`.

## Phase 6: Verification and Release Evidence

- [X] T026 [P] Align `commands/swap.md`, `commands/ctx.md`, `commands/handoff.md`, `skills/lane-swap/SKILL.md`, `skills/handoff/SKILL.md`, and `docs/README-lanes.md` with native children, release-gated restart, no swap handoff, and explicit experimental refusal — reviewed all six documents on 2026-09-17; installed copies are self-contained and identify unpublished source records without broken relative links. This closes documentation alignment only, not native/runtime acceptance.
- [ ] T027 Run focused managed tests with `tests/run.sh -k 'test_lane_managed_state or test_lane_managed_profiles or test_lane_managed_sdk or test_lane_managed_controller or test_lane_managed_daemon or test_lane_managed_cli or test_lane_managed_native_admission or test_lane_managed_native_stop or test_lane_managed_native_interrupt_runtime or test_lane_managed_native_start_integration or test_lane_managed_stop_integration or test_lane_managed_coordinator_interrupt or test_lane_managed_interrupt_integration or test_lane_managed_probe or test_lane_managed_loopback_probe' --junitxml=<private-artifact>/junit.xml` and record hashes; this is the required test gate for T005–T014 and must run from the frozen implementation snapshot before runtime validation
- [ ] T028 Run `tests/run.sh -k test_the_lane_helper_suite_passes --junitxml=<private-artifact>/junit.xml` once legacy fixes freeze; never substitute positional paths
- [ ] T029 Run the full serialized `tests/run.sh` with the pinned submodule and resolve only in-scope regressions
- [X] T030 Execute no-auth/no-network Gate 0 positive-orphan and terminal-cleared controls against the selected SDK/CLI and, only where the selected capability exposes the complete busy/native-roster interrupt mode, its bounded interrupt/drain observation across settled, busy, multiple-child, nested, and in-flight-admission cases; keep one continuous request-observation epoch from account-control entry before preflight/fencing through held initialization until release with no reset, and record path, versions, full digests, enqueue evidence, and model-dispatch evidence in `live-validation.md`, otherwise record that mode as unsupported/unverified — completed only through the explicit unsupported/unverified disposition documented in `live-validation.md`; native/runtime/feature acceptance remains unsatisfied
- [ ] T031 Keep authenticated account-swap validation `NOT RUN — UNVERIFIED` until authorized; fake/no-auth results cannot mark it supported
- [ ] T032 Reconcile final evidence against every FR/SC and both OpenSpec delta specs in `verification.md`, leaving incomplete rows explicit
- [X] T033 Correct and offline-test the Bite 4 external volume-event witness in `tests/probes/managed_two_domain.py` and its focused tests: retain the run-label-filtered container stream, add a bounded unfiltered volume-only stream, preregister each exact unique volume name/role, require nonempty `Actor.ID` and reject conflicting top-level identity, and independently inspect each created volume for exact name/run+role labels/local driver+scope/no options before recording a sanitized attestation digest. Ignore unrelated volume events without storing/counting them. Under the existing lock/sequence, reject duplicates, name reuse, conflicting identities, unexpected destroy, missing events, and stream failures; bind mounts/unmounts/destroys to attested volumes, durable removal intent, and independently confirmed absence. Before the release inventory snapshot, bounded-wait for each planned volume's exact mount/unmount counts while checking both streams' health. Astra targeted architecture review passed; Sol ran `tests/run.sh --parallel-safe -k two_domain`: 39 passed, 2,293 deselected in 9.47s. JUnit `91b1b34dc62cf8e34035eea99b6bbdb37b3675518f1585fa469f220be580c6ba`; log `b62a03373d1fd2950579083ab6275d8b720143e8b7d5f4f9495fa5dcd1ec467e`. Frozen hashes and scope are in `verification.md`. This closes T033's future-only offline correction only; it does not runtime-verify Bite 4 or decide Bite 5. A later explicit user authorization for one separate Bite 4 follow-up is recorded in `runbook.md`; keep the original preserved volume untouched and do not infer authorization for any further attempt or cleanup.

## Dependencies and Parallel Work

### Approved v1 tranche within these existing tasks

The [v1 contract](contracts/stop-then-resume.md) extends this sole task list;
there is no second feature or parallel executable checklist. Historical closed
tasks remain scoped to their recorded snapshots and do not accept v1 behavior.

- T003/T004: first add the distinct no-auth v1 probe and test its saved edit,
  native child/tracked shell, source observations, delayed target creation,
  exact after-release resume and unknown-effect refusal. Preserve all existing
  probe semantics and keep `support_claim: false`.
  The first experiment is recorded at checkpoint `6c3cbfa`; its follow-up is
  bounded sanitized startup-event correlation and parent/child stored-history
  integrity evidence under the same contract. Preserve the startup-activity
  guard and distinguish bytes retained from history actually loaded. Neither
  diagnostic closes these tasks or authorizes public lifecycle integration.
  That follow-up is implemented and measured in `verification.md`: 137 focused
  tests plus one isolated release run, preserved bounded prefixes, unresolved
  native joins and restoration. The startup query guard remains unchanged.
  Bite 2 then froze the default-off `--observe-native-hooks` local correlation
  diagnostic at 153 focused passes; no runtime/account/production activation
  occurred, and the hook-to-history bridge remains unverified. The Bite 3
  containment/restart definition is recorded in
  `contracts/stop-then-resume.md`: bind the original runner PGID and complete
  source roster to operation/source-invocation IDs, owner/lineage/runner/daemon
  incarnations, and a monotonic observation watermark; require launch-to-
  exclusion membership/escape coverage, and a durable restart-deny fence
  consumed by every source creation and recovery path; and join it to current
  lane-supervisor lifecycle plus an OS-domain witness. The current producer
  cannot prove those facts, so production preflight refuses. The
  existing loopback container is not positive containment evidence because it
  co-locates source, target, and observer, keeps history in temporary storage,
  and does not validate the container restart policy. Its result retains
  `support_claim: false`. The scoped two-domain diagnostic proposal is in
  `contracts/source-only-diagnostic.md`, with the five-bite operator sequence
  in `runbook.md`; Astra approved the architecture and the focused frozen
  preceding offline candidate passed 26 tests; T033's repaired observer then
  passed 39 focused offline tests with Astra review. Sol invoked the outer
  two-domain harness once;
  it exited INCONCLUSIVE before source startup when the label-filtered Docker
  volume stream did not deliver the volume-create event. Read-only diagnosis
  found the matching engine event lacked run/role attributes although volume
  inspection showed the labels. At that first-run checkpoint, one
  source-state volume was preserved; no source SDK runtime, source history,
  release, target, or negative arm ran.
  This is not a completed Bite 4 runtime experiment and is not a Bite 5 verdict.
  T033 is complete as a future-only offline volume-observer correction. The
  single later-authorized Bite 4 follow-up was executed and aborted
  INCONCLUSIVE at Docker source-container create (exit 125) after the corrected
  observer passed volume creation. Exact daemon stderr was not retained. A
  writable volume `--mount` access token `rw` is a moderate-to-high-confidence
  suspected command-builder defect, not a confirmed cause. No source/runtime,
  history, release, target, or negative arm ran; zero run-labelled containers
  and two source-state volumes remain, with no cleanup or retry. The run and
  artifact digests are in `live-validation.md`. T034 has completed the
  offline-only mount-builder correction and private failure-stderr capture;
  Astra review and Sol's 41-test gate passed. At that T034 checkpoint no third
  runtime was authorized; the later single third run and its INCONCLUSIVE result
  are recorded separately below. Astra's Bite 5
  evidence assessment and verdict remain pending. Bite 5 assigns only
  PASS/FAIL/INCONCLUSIVE after evidence review. PASS must satisfy the complete
  Bite 3 source witness and all-path restart-fence contract; fixture ordering
  alone cannot pass. Only PASS permits public v1 lifecycle implementation.
- T009–T014: after the experiment establishes the required seams, implement
  and test stored mode routing, source proof, immutable history manifest,
  `ready-to-resume`, durable release-before-launch, SDK release-authorized
  startup and no-replay recovery. Strict six-stage behavior stays unchanged.
- T015–T019: reconcile restored child events before additional dispatch and
  report prepared intent separately from actual target/child restoration.
- T014/T024: correct native unenroll cleanup with exact child-worktree then
  lineage-claim release, authoritative stop/effect checks and recoverable
  discovery/owner finalization.
- T025/T026: their historical closure does not cover new public mode/help;
  reopen them when public v1 behavior is implemented, not for a probe alone.
- T027–T032: verify v1 separately. T030's historical unsupported disposition
  remains history, not a pass of the new experiment. Record new evidence in
  `live-validation.md`; all live support and deployment gates remain open.
- T033: the unfiltered volume observer, event identity checks, bounded
  cross-stream reconciliation, and fake-event tests are complete; Astra's
  targeted architecture review passed, and Sol's focused 39-test offline gate
  passed. The one separate user-authorized Bite 4 follow-up was executed. It
  aborted INCONCLUSIVE at source-container create with Docker exit 125 after
  volume creation; the exact daemon stderr was not retained. Two source-state
  volumes remain preserved, zero run-labelled containers exist, and no cleanup
  or retry occurred. The result is recorded separately in `live-validation.md`;
  do not repeat the consumed command in `runbook.md`.
- [X] T034 Correct the future-only Docker container command builder to omit an
  access token for writable volume mounts and use readonly for read-only
  mounts; add bounded Docker stderr capture to the private arm-abort ledger
  while keeping public diagnostics sanitized. Astra review passed. Sol's
  tests/run.sh --parallel-safe -k two_domain rerun passed 41 tests, 2,293
  deselected in 9.09s after fixing one redundant assertion in the first gate
  (40 passed, 1 failed). JUnit edb34b8404e20b3e8815e1b17a9b12f2b4347bfc1a75c6b1cebb0183cf552963;
  log 9376fd78c8c29678af02aefaa57c38d73bbefc7d0cf4bf0290fbe2d82e72b1f0.
  Astra's limits: stderr retained in the private ledger is capped at 4,096
  bytes, subprocess capture itself is unbounded, and timeout/pre-arm failures
  do not use this capture path. This offline-only task does not confirm the
  previous Docker exit-125 cause or authorize another runtime. A separately
  user-authorized create-only Docker smoke then passed with the same frozen
  builder: one fresh labelled container/volume, inspect showed Created,
  Running=false, and RW=true; only those resources were removed and verified
  absent. The two earlier source-state volumes remained untouched. This narrow
  PASS is recorded in runbook.md, live-validation.md, and verification.md; it
  proves neither the earlier exit-125 cause nor Bite 4 completion.

The future-only T035 correction for pre-start tmpfs validation and quarantine
is now architecture-reviewed and offline-verified. Sol ran
`tests/run.sh --parallel-safe -k two_domain`: 59 passed, 2,293 deselected in
6.74s. Exact frozen hashes and private output digests are in
`verification.md`. This does not runtime-verify Bite 4 or establish the Bite 3
production witness. A later separately authorized fourth run is recorded in
`live-validation.md`; it ended INCONCLUSIVE before any container exec and left
a fourth volume plus an Exited 137 container preserved. Preserve all four
volumes and both containers. That checkpoint's no-fifth-authorization statement
was superseded by the user's later authorization for exactly one fifth bounded
  run after T036 review, the combined offline gate, and fresh preflight. The
  fifth run then stopped before source start on the observed Docker
  `StdinOnce=true` mismatch and remains INCONCLUSIVE; its new Created container
  and attached volume are preserved. T038 corrects that interactive stdio profile
  for future runs. The user authorized exactly one sixth run; Astra review,
  Sol's 127-test offline gate, and fresh read-only preflight passed. Its
  distinct hash-guarded command is in `runbook.md`; Sol's outer and nested
  shell syntax reviews passed and root GO was issued. The one run's result is
  pending. No cleanup of earlier resources is authorized.
  Bite 5 remains pending with no verdict. The
held-swap and T009–T014-before-T030 dependencies below describe
strict-mode acceptance, not this initial v1 experiment. Broader T027–T032 gates
still apply to subsequent public integration and activation.

- T001/T003 may run in parallel; T002 depends on T001, and T004 on T003.
- T005/T006 and T007/T008 may run alongside SDK evidence work.
- T009-T014 require T002, T004, T006, and T008. T009 is authored and
  reviewed before T010/T011/T014 implementation changes; it is the meaningful
  fake-runtime acceptance order for the coordinator interrupt contract.
  Missing exact parent identity refuses; it is not a worker restart fallback.
- T015-T019 require a held swap and cannot dispatch before release.
- T020-T022 require the lineage/claim model but may use fake runtime evidence.
- T023-T025 are reusable and may proceed independently.
- T027 runs after the T009–T014 implementation snapshot freezes and before
  T030–T032. T027-T032 run only from frozen snapshots with one canonical test
  executor; no checkbox is implied closed by this ordering.

- [X] T035 Correct pre-start tmpfs validation and never-started quarantine in
  the opt-in two-domain diagnostic only. For a container independently
  inspected as Created, Running=false, Pid=0, and with both start and finish
  timestamps exactly equal to Docker's zero-time sentinel
  (`0001-01-01T00:00:00Z`), accept the exact configured HostConfig.Tmpfs
  destinations /tmp and
  /opt/loopback even when those destinations are absent from Mounts; reject
  extra or conflicting mount evidence. Missing, null, empty, or malformed
  timestamps are uncertain. Revalidate after wrapper start and
  before SDK startup; if a running container lacks actual tmpfs Mounts evidence,
  refuse before launching SDK. For a corroborated never-started Created
  container, preserve a sanitized never-started fact without requiring a die
  event or attempting cleanup. Ambiguous start history remains uncertain.
  Focused offline regressions cover the exact sentinel, missing/null/empty/
  malformed alternatives, conflicting inspect forms, post-start revalidation,
  and quarantine outcomes. Astra targeted review passed; Sol's canonical
  `tests/run.sh --parallel-safe -k two_domain` gate passed 59 tests, 2,293
  deselected in 6.74s. Hashes and output digests are in `verification.md`.
  This closes only the future-only offline correction; it does not imply
  runtime verification, cleanup, production enablement, or authorization for
  any additional attempt beyond the separate fourth run already recorded.

- [X] T036 Add a trusted active-tmpfs witness to the opt-in two-domain
  diagnostic for source, every helper, and target. A frozen startup wrapper
  reads two bounded `/proc/self/mountinfo` records before SDK/helper work;
  the external observer binds each capture to exact container ID, image,
  run/role, start epoch, and engine create/start evidence. The parser checks
  controlled destinations, effective mount and superblock flags, exact sizes,
  ancestor overmounts, duplicates, complete records, and bounds. The attach
  transport is bounded and remains tracked through stop. Missing, malformed,
  stale, duplicate, or ambiguous evidence refuses; active-mount proof is never
  waived from `HostConfig.Tmpfs` alone. Policy findings become FAIL only after
  identity/event binding and durable capture; uncertain evidence stays
  INCONCLUSIVE. Astra's targeted review passed; Sol's combined
  `tests/run.sh --parallel-safe -k two_domain` gate passed 110 tests, 2,293
  deselected. Exact frozen hashes are in `verification.md`. This is offline
  evidence only; Bite 4 remains live-unverified.

- [X] T037 Preserve volumes on every normal `fail` or `inconclusive` return
  from the two-domain harness. The current pre-release gate, unproven negative
  refusal, and final target-result branches call `_remove_run_volumes` at
  `tests/probes/managed_two_domain.py:2353`, `:2465`, and `:2680`, conflicting
  with the failed-arm preservation rule in `contracts/source-only-diagnostic.md`.
  Persist a bounded sanitized result and manual-review inventory, but do not
  request volume deletion or record cleanup complete on those outcomes. Add
  focused offline regressions for each failure/inconclusive branch and the
  fully successful custody boundary. Astra's targeted review passed; Sol's
  frozen focused offline gate passed 69 tests, 2,293 deselected in 9.10s.
  Exact hashes are in `verification.md`. T036 and T037 review and the combined
  offline gate pass. The fifth attempt was run and ended INCONCLUSIVE before
  source start; see `live-validation.md`. No cleanup of prior resources is
  authorized.

- [X] T038 Correct the Docker interactive wrapper's inspected stdio contract
  for future Bite 4 runs. Require exact `OpenStdin=true`, `AttachStdin=true`,
  `Tty=false`, and `StdinOnce=true` in both host wrapper-configuration checks
  and the native active-witness validator. Keep one continuous tracked attach
  through both challenge stages; EOF or transport loss refuses without a
  replacement attach or replay. Distinguish image-ID mismatch from wrapper
  configuration mismatch in sanitized diagnostics. Sol's fifth-run Created
  inspect confirmed `StdinOnce=true` while the previous code expected false;
  no wrapper or SDK work began. Astra targeted review passed. Sol's canonical
  `tests/run.sh --parallel-safe -k two_domain` gate passed 127 tests, 2,293
  deselected in 10.07s. Frozen hashes, JUnit and log digests are in
  `verification.md`. This is future-only offline evidence; it does not alter
  the fifth INCONCLUSIVE result or establish Bite 4 completion. One sixth run
  is user-authorized; fresh preflight and py-bench visibility checks passed.
  Its distinct hash-guarded command is in `runbook.md`, and Sol's outer and
  nested `bash -n` checks passed. Root GO remains required; do not clean prior
  resources.

- [X] T039 Execute the single user-authorized sixth full Bite 4 attempt using
  the distinct T038-hash-guarded command in `runbook.md`. It exited 2 / INCONCLUSIVE
  after source SDK activity, when the first custody COPY helper failed its
  bounded manifest scan on a file exceeding 64 KiB. Source stop/removal was
  observed; the target-state volume was created only afterward. Copy
  verification, pre-release history custody, release, target, and negative arm
  did not occur. The helper and seven volumes/four stopped containers remain
  preserved; zero are running. No cleanup or retry occurred. This sixth-run
  checkpoint preceded the T040 metadata diagnosis and later conditional user
  authorization for one seventh full attempt. The separately scoped
  metadata-only candidate is tracked in T040; it does not reuse the COPY helper
  or infer a history mismatch. Bite 5 remains pending.
  Only a PASS against Bite 3 evidence requirements permits public v1 lifecycle
  implementation.

- [X] T040 Prepare and execute the separately authorized stat-only metadata
  diagnostic against the sixth attempt's preserved source-state volume. The
  scanner uses bounded no-follow metadata traversal, reads no evidence bytes,
  reports oversized files rather than refusing on size alone, and emits a
  strictly validated path-free public projection. The isolated Docker
  protocol pins scanner source, image, exact read-only `volume-nocopy` mount,
  disabled healthcheck, and bounded capture/stop behavior; it preserves its
  diagnostic container and artifacts. Sol's scanner-only offline gate passed
  (14 passed, 2,420 deselected); Astra architecture review, Sol's command
  review, fresh preflight, shell syntax, and six Python parses passed. The one
  run exited 0 and reported nine files/14 directories totaling 394,590 bytes;
  the largest identified config `.json` is 306,896 bytes. No file contents
  were read. Seven volumes and five stopped containers remain; zero running.
  The source volume's contents remain unchanged, though its engine attachment
  metadata changed while mounted read-only. Exact digests are in
  `verification.md` and `live-validation.md`. This does not establish history
  custody or Bite 5. At the T040 checkpoint, one seventh full Bite 4 attempt
  was conditionally authorized after the separate fixture-tree-limit
  correction, review, offline gate, and fresh preflight. Those gates later
  passed; exact-command review and parent GO remain before execution.

- [X] T041 Separate whole-fixture tree limits from bounded history evidence in
  `tests/probes/managed_native_loopback.py`. Use consistent defaults of 512
  KiB per fixture file and 2 MiB per complete tree for manifest, copy and
  re-manifest, pre-release/final custody, and target prestart checks. Keep
  `MAX_HISTORY_CONTENT_BYTES` at 64 KiB and `MAX_HISTORY_SCAN_BYTES` at 512
  KiB; do not truncate or omit fixture paths. Add offline regressions for the
  measured 306,896-byte config JSON through exact copy/manifest/history custody,
  exact per-file and aggregate limits plus cap+1 refusal, and the unchanged
  oversized history-prefix refusal. Astra's architecture review passed. Sol's
  canonical selector `tests/run.sh --parallel-safe -k two_domain` passed 144
  selected tests, zero failures/errors/skips, in 14.434s. Frozen native/helper/
  test hashes and private output digests are in `verification.md`. This is
  offline evidence only and does not complete Bite 4. At this checkpoint a
  seventh attempt was authorized; that attempt and its result are recorded in
  T042 below. Bite 5 remains pending.

- [X] T042 Execute exactly one seventh full Bite 4 attempt with the separate
  T041-hash-guarded command in `runbook.md`, after Sol's exact-command review
  and parent GO. The public packaging exited 1 with
  `private-identifier-in-report`; the positive arm's private result was
  INCONCLUSIVE with `startup-task-event-observed`. Source stop/exclusion, exact
  copy, identity-linked parent-history custody, durable release, target
  startup/stop/removal, and final custody were observed. The target startup
  task event caused history query to be skipped, and the negative arm did not
  run. Nine engine volumes and five older stopped containers remain; zero are
  running, and no seventh-run container remains. The single-use authorization
  is consumed. Preserve resources and artifacts; no cleanup or eighth run is
  authorized. This is not a Bite 5 verdict.

- [X] T043 Correct the public image-ID sanitizer false positive in
  `tests/probes/managed_two_domain.py`. Keep `args.image`, the resolved image ID,
  and all other secret/private values in the check set. Validate the resolver's
  full immutable `sha256:<64 lowercase hex>` identity and mask only the exact
  `identities.image_id` leaf in a copied scan projection; retain the generic
  `_assert_no_private_values` behavior for every other field. Add focused tests
  for immutable-ID and tag inputs, malformed/mismatched leaf, duplicate digest
  elsewhere, and private path/tag leakage. Astra's integrated architecture
  review passed. Sol's canonical `tests/run.sh --parallel-safe -k two_domain`
  gate passed 151 tests with zero failures/errors/skips in 9.749s. The frozen
  source hashes and output digests are in `verification.md`. This only corrects
  future report packaging; it does not change the seventh run or authorize a
  runtime retry.

- [X] T044 Add a bounded sanitized startup native-task lifecycle projection for
  a future separately authorized diagnostic. Snapshot target task lifecycle
  after initial startup read and before any optional history query, with
  explicit `target-observed` provenance and unavailable source-seed provenance.
  Preserve the sticky startup gate, query branch, and refusal result; expose
  only bounded allowlisted subtype/status and identity digests, never raw IDs
  or frames. Cover normal, missing/conflicting identity, overflow, and
  event-after-snapshot cases offline. Astra's integrated architecture review
  and Sol's 151-test focused offline gate passed. The snapshot does not change
  the sticky history-query decision and did not itself authorize an eighth
  Bite 4 run.

- [X] T045 Execute exactly one eighth full Bite 4 attempt using the T043/T044
  hash-guarded command in `runbook.md` after separate user authorization,
  review, offline gate, and fresh preflight. The outer command exited 2 with a
  sanitized INCONCLUSIVE report. Source stop/exclusion, exact copy,
  pre-release identity-linked history custody, durable release, exact-parent
  target initialization/start/stop/removal, and final saved-edit/history
  custody were observed. The startup snapshot recorded one
  `system/task_notification` with `stopped` status and matching session
  correlation; task/agent remained unknown, source terminal seed unavailable,
  and identity unresolved. The sticky gate correctly skipped history query;
  the positive arm is INCONCLUSIVE and the negative arm did not run. Eleven
  volumes and five older stopped containers remain preserved, zero running,
  with no eighth-run containers. At that eighth-run checkpoint the
  authorization was consumed; no cleanup, ninth run, Bite 5 verdict, or
  production activation was authorized. Artifact hashes are in
  `verification.md` and `live-validation.md`.

- [X] T046 Add a fail-closed source-to-target native-task seed handoff in
  `tests/probes/managed_native_loopback.py` and
  `tests/probes/managed_two_domain.py`. Transfer only a bounded sanitized
  terminal task event and session/task/agent digests; bind its digest to the
  source invocation/parent, source-phase digest, durable release and
  target-launch intents, and target-spec fingerprint. Missing or incomplete
  linkage is INCONCLUSIVE before release and target creation. The target
  validates the full fingerprint before any CLI subprocess and initializes
  the existing strict correlation logic from the seed without changing the
  sticky startup gate. Astra architecture review passed. Sol's canonical
  `tests/run.sh --parallel-safe -k two_domain` gate passed 155 selected tests,
  zero failures/errors/skips, in 5.715s. Frozen hashes and private gate
  artifacts are in `verification.md`. The ninth Bite 4 run exercised the
  fail-closed `source-native-task-terminal-seed-unavailable` refusal and
  remained INCONCLUSIVE before release or target runtime creation. It did not
  exercise available-seed transfer, target fingerprint validation/correlation/
  startup/history query, or the negative arm; the exact missing
  identity/event condition remains unknown because the source projection lacks
  its detailed unavailable-reason envelope. The T046 focused offline closure
  remains valid. No tenth attempt, cleanup, or public v1 lifecycle
  implementation is authorized.

- [X] T047 Repair the source-native-task-terminal-seed-unavailable diagnostic
  without changing runtime authority. In `tests/probes/managed_native_loopback.py`
  and `tests/probes/managed_two_domain.py`, use lifecycle record schema v2 for
  tool-use correlation, preserve the source terminal observation unchanged,
  and retain bounded path-free seed-reason/lifecycle/hook diagnostics in the
  source projection bound by the source-phase digest. Enable source hook
  observation; construct an envelope with separate `task_started_event`,
  terminal `task_notification`, and direct-or-exact-hook `agent_proof` records.
  Require setup/drain ordering, actual session/task equality, unique
  tool-to-task and agent-to-task bindings, and exact hook joins by session plus
  tool-use ID (task ID when observed). Early unresolved hooks can join only
  through those digests; absent callback IDs, ambiguity, conflicts, error,
  malformed evidence, and overflow refuse. Sanitize SDK-optional fields without
  inventing values. Record `task_updated.patch.status` and conflicts accurately
  but do not promote update-only evidence to a seed. At target, require exact
  terminal subtype/status/session/task; absent optional agent/tool fields stay
  unknown and present conflicting IDs refuse. Keep the existing sticky startup
  gate unchanged. Frozen code hashes: native
  `86470ec387152debb46e507ba5e325117bf23d29e41808a65ad967654bfe0586`, harness
  `bb5161ba852aaa7f83c314d171b3929dcbca07c106b8899ee514f085ee111a77`, tests
  `5b417c029a7ab3ed934d1787069c6965ccd4acf3a345bdf5d80a2144286c21e4`.
  Luna's py-bench focused development selector passed 207 tests, 2,273
  deselected (`two_domain or native_task or native_hook`). Astra's final
  architecture review passed. Sol's formal gate
  `tests/run.sh --parallel-safe -k 'two_domain or native_task or native_hook or hook_ack or source_terminal_seed'`
  passed 210 tests, 2,270 deselected, zero failures/errors/skips, in 13.02s.
  Gate artifacts and hashes are in `verification.md`. This closes only T047's
  scoped implementation/review/offline gate. The tenth Docker/Bite attempt
  exercised the repair and was INCONCLUSIVE before release/target creation:
  `source-native-task-terminal-seed-unavailable`, detailed reason
  `terminal-task-hook-evidence-incomplete`. At that T047 checkpoint, its
  one-run authorization was consumed and no cleanup or eleventh attempt had
  yet been authorized. The later eleventh authorization and result are
  recorded under completed T048 below. Bite 4/Bite 5 remain
  open. Astra's post-run review says the callback mismatch was correctly
  rejected fail-closed; the SDK does not guarantee equality semantics and the
  retained summary lacks the rejected event kind/digests, so no CLI defect is
  established. Preserve the frozen hashes and detailed runtime evidence in
  `verification.md`.

- [X] T048 Preserve structurally valid hook callbacks whose callback tool ID
  differs from the current task tool ID as unresolved, task-ID-free hook
  evidence after full shape validation; ACK without rewriting the callback's
  observed digest. Add bounded digest-only mismatch diagnostics that keep
  callback, input, and current task/session/tool identities distinct, including
  rejected callback/input conflicts. Add a source-finalization SDK-sidecar
  identity bridge requiring a unique parent Agent `toolUseId` match, top-level
  parent session proof, matching child top-level session/agent proof, and exact
  `SubagentStop` transcript-path proof. Use bounded exhaustive no-follow scans,
  regular single-link files, duplicate-key JSON rejection, and fail-closed
  handling of missing, nested, conflicting, ambiguous, malformed, or overflow
  evidence. Use source seed envelope v3 and introduce distinct agent-proof v2
  and strictly detached SDK-sidecar-proof v1 schemas; validate the proof before
  the source seed can be marked available.
  Cover detached rehash tampering and adversarial sidecar/callback cases in the
  focused offline suite. This is offline-only implementation work: it does not
  itself launch a runtime or authorize cleanup. Astra's architecture review
  passed and Sol's formal selector passed 243 tests, 2,270 deselected, with
  zero failures/errors/skips; frozen code and artifact hashes are in
  `verification.md`. The separately authorized eleventh Bite 4 attempt then
  ran once and was INCONCLUSIVE with `startup-task-event-observed`; its
  authorization is consumed. Preserve all historical run artifacts/resources,
  with no cleanup, retry, or twelfth attempt. Bite 5 remains undecided pending
  required evidence.

  The later separately authorized twelfth full Bite 4 attempt also ran once
  and remained INCONCLUSIVE with `startup-task-event-observed`. Its one-run
  authorization is consumed. At that runtime checkpoint, no cleanup or
  thirteenth attempt had been authorized. The negative arm did not run, Bite 5
  remains pending, and production remains unsupported. After the sealed
  evidence was verified, Sol High completed a separately authorized exact
  cleanup: 19 labeled diagnostic volumes and five stopped containers were
  removed, and postflight confirmed all 24 absent. The sealed bundle and
  36-entry manifest remain unchanged; no prune, evidence deletion, or
  unrelated removal occurred. The private mode-0600 allowlist artifact
  SHA-256 is
  `d6ea783b66a4bee326ee23b83d80a82797f2f633db19831b131b0ac4cd0a4d78`. No
  thirteenth attempt was authorized at that historical checkpoint; the later
  one-run authorization and result are recorded in `verification.md`.

- [X] T049 Add a separate offline-only
  `two-domain-terminal-task-diagnostic-v1` progression in
  `tests/probes/managed_native_loopback.py`, while preserving
  `strict-v1` as the default and leaving `assess_v1_history_query_gate`
  unchanged. Bind the mode into the selected target profile/spec fingerprint
  and durable release/launch intents. Observe request arrivals from before
  `Popen` while the gateway is held; admit only one validated stopped source
  task and one exact stopped target `system/task_notification`, with the
  source `local_agent` start proof, exact parent/task digests, absent-or-null
  target task type left unsynthesized, and optional agent/tool conflicts
  refused. Require exactly one explicit `task-notification` startup result
  with exact top-level parent session, no error/abort/deferred tool, and no
  other activity, event, route, request, partial/unparsed frame, overflow,
  ambiguity, or reader error. For the selected query, require one direct,
  same-request, role-correct, ordered source marker/Agent-use/matching-result
  history before a fresh private nonce; validate model and dummy auth; reject
  split, nested, duplicate-key, child, extra-tool, and unexpected request
  evidence; write a separate unpredictable challenge and retain only bounded
  sanitized witness/digests. Require successful response write and message-ID
  digest, fresh exact-parent human-origin challenge result, assistant-ID join
  when present, post-query stdout EOF, closed server/arrival fence, zero
  in-flight/unexpected requests, and exactly one total task event after drain.
  Export the witness and require it in target acceptance. Keep the conclusion
  terminal-correlation-only: the listed source facts reached the target model
  request, while full history restoration, replay, quiescence, child
  restoration, and production support remain unproved. Fix negative-arm
  not-run reasons and require both positive and negative arms for overall
  `OBSERVED`. Add adversarial boundary tests and an all-green offline fixture
  in the probe and harness suites, update the linked OpenSpec design/contract/
  runbook, and record Bite 4 as historical INCONCLUSIVE with Bite 5 pending.
  Offline-only: no Docker/runtime test, cleanup, commit, push, deploy, or new
  runtime authorization.
  Astra approved the architecture and Sol's expanded canonical scoped gate
  passed (420 passed, 2,168 deselected, zero failed). At that checkpoint, the
  selected diagnostic was ready for a separately authorized runtime test, but
  T049 itself did not provide authorization. The later one-run authorization
  and thirteenth INCONCLUSIVE result are recorded in `verification.md`.
  Default `strict-v1` behavior remains unchanged; Bite 5 remains pending and
  production remains unsupported.

- [X] T050 Correct the source-phase fallback path offline in
  `tests/probes/managed_native_loopback.py` and
  `tests/probes/managed_two_domain.py`: remove the unbound legacy/source
  `parent_uuid` initializer, publish only allowlisted bounded `error_site`
  metadata in generic fallback reports, and persist the exact returned source
  report with invocation/container/report digests in the existing private
  append-once envelope immediately after `_runtime_exec` and before source
  stop/removal or target-volume creation. Validate schema, phase, support
  claim, target reach, and source bindings; malformed/fallback reports use the
  fixed public `source-runtime-report-invalid` INCONCLUSIVE path through
  quarantine while preserving private evidence. An otherwise-valid explicit
  `target_code_reached=true` remains a `KnownViolation`/FAIL; absent or unknown
  reach evidence remains INCONCLUSIVE. Add offline coverage for the source and
  legacy Popen boundary, bounded error-site redaction, accepted private report,
  fallback privacy/order/quarantine, explicit target reach, unknown reach, and
  persistence failure. Future-only: the thirteenth historical run remains
  INCONCLUSIVE and is not rewritten. Astra approved T050 and Sol's canonical
  focused gate passed 427 tests, with 2,168 deselected and zero failures;
  JUnit SHA-256 is
  `f887c8d09ccfd49c1a59165b2cf59c4102d108d1655821382266e38267619633`.
  At T050 completion no fourteenth run had been authorized; the later separate
  user authorization and consumed fourteenth-run result are recorded at the
  top of this file.
  Bite 5 remains pending and production unsupported. No runtime, Docker,
  cleanup, commit, push, or deployment is part of T050.

- [ ] T051 Add offline-only, bounded ordered query-frame header evidence after
  Astra architecture review. Project every target-query frame's type, subtype,
  schema, origin, session correlation, and stage (query read or shutdown drain)
  without retaining bodies, paths, or content; keep unknown discriminators in
  private evidence and persist the exact target report privately before
  teardown, following T050's source-report pattern. Add offline tests for an
  extra frame before/after the result, shutdown-drain frames, malformed
  headers, overflow, and privacy. Preserve the current fail-closed refusal for
  every extra frame until its discriminator is identified against the pinned
  schema; `rate_limit_event` and `turn_duration` are examples only, not
  observed types. Do not use this task to alter Bite 3, Bite 5, production, or
  runtime authority. The fourteenth run remains INCONCLUSIVE; no further run,
  cleanup, or deployment is authorized.
