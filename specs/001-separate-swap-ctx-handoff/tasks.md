# Tasks: Native-Lineage Account Swap and Session Operations

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`,
and `openspec/changes/separate-swap-ctx-handoff/`.

**Tests**: Required. Fake and local no-auth runtimes use serialized
`tests/run.sh`; no task authorizes a real account/profile swap or network/model
request. Live validation remains `NOT RUN — UNVERIFIED` until authorized.

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

## Dependencies and Parallel Work

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
