# Implementation tasks: migrate openRepoTools to the triad

The sole executable task list for the governing OpenSpec change. Planning
artifacts and preliminary mapping validation do not complete these tasks.
Every task remains open. Run implementation from the selected feature
worktrees; actual repository creation/cutover require the approval gates.
The protocol refresh updates snapshot/mapping and planned workflow follow-ups;
owner decisions, private preservation/restore receipts and execution gates
remain pending. Retired checkouts are not instructions to recreate worktrees.

Preparation progress is recorded in [preparation.md](preparation.md): partial
T001–T005 evidence, an [upstream blocker reproduction](adopter-blocker.md),
and [T007–T010 installer/test design](installer-design.md). No execution task
is complete. The [October 6 candidate rehearsal](adopter-rehearsal.md) passes;
T005 still needs upstream landing and a tested consumer pin update. PRs #97
and #121 have landed. Real conversion waits for the remaining baseline PRs,
integration/preservation evidence and refreshed execution approval.

## Phase 1 — Preservation and baseline (Gate A)

- [ ] T001 [US1] Refresh `inventory.json`, PR/main/branch/worktree metadata and
  applicable estate-status output; distinguish retained work from retired
  cleanup records and remote-only refs. Until an estate manifest exists,
  relay `status --fetch openRepoTools`'s no-estate refusal without invoking
  `resume`. Resolve continuation/archive decisions for every retained object
  in a host-local/private migration receipt. Verify no branch, detached
  worktree or dirty/untracked/local-workflow content is omitted.
- [ ] T002 [US1] Coordinate owner breakpoints and preserve source refs/content,
  ignored workflow configuration and installed receipts/config using the
  existing estate/private backup contract. Verify restoration and per-object
  digests, including all feature 001 edits and new files, without altering
  workspace.yaml or broad process actions.
- [ ] T003 [US1] Confirm proposed leg names/visibility and inspect prerequisite
  availability; regenerate `adoption-plan.yaml` for the reviewed preliminary
  rehearsal source, retaining reasoned overrides. Verify standard `check`
  passes and records all source paths with no unapproved drops. Explicitly
  classify genuine bounded feature amendment folders as code until upstream
  qualification; preserve full proposals/archives/canonical Speckit as spec
  regardless of branch origin. Record no amendment paths when none exist;
  do not manufacture historical amendments or weaken shape pins.

## Phase 2 — Local adoption rehearsal (Gate B foundation)

- [ ] T004 [US1] Prepare a clean isolated source clone with no linked
  worktrees and approved `git-filter-repo` availability; rehearse the standard
  adoption against temporary local bare remotes. Verify source identity/history,
  path/blob accounting and recoverability without real GitHub creation.
- [ ] T005 [US1] Exercise the existing nested submodule path, original
  `.gitmodules` extraction/removal, pin integrity and recursive bootstrap.
  Verify the code gitlink/pin/registration remain coupled. If standard tooling
  refuses, record its refusal and resolve upstream before a tested pin bump;
  never patch `upstream/openRepoShape` in place or weaken verification.
- [ ] T006 [US3] Resolve materialized root collisions and new leg guidance in
  reviewable patches; bootstrap selected root workflow after manifest/legs
  exist. Verify first-line shape guidance, relative paths, actual `.specify`
  configuration and paired feature selection without copying machine secrets.
  Verify explicit full-spec/local-amendment roots and intended feature branches,
  local-root precedence over store pointers and supported CLI store selection.
  Keep manual records until schema/routing is qualified; check protocol/command
  distribution per target workstation through owning workBenches delivery,
  without treating a scaffold bootstrap as distribution of this manual decision.

## Phase 3 — Installation and checks (Gate B completion)

- [ ] T007 [US2] Add the assembly `openRepoTools` entry point and coherent
  payload-source resolution in the code installer after source byte accounting.
  Verify gh/raw one-liners resolve one code pin and do not duplicate installer
  mechanics or depend on developer checkouts after installation.
- [ ] T008 [US2] Cover local/offline, legacy monorepo overrides, adopted forks,
  branch/commit refs, immutable code selection, missing/mismatched pins and
  failed partial fetch. Verify unchanged command/artifact names, counts,
  destinations/modes, hooks, ownership receipts and all-or-none refusal.
- [ ] T009 [US3] Separate code/spec/assembly/dependency roots in fixture and
  hygiene consumers, including docs/OpenSpec/Speckit references. Verify the
  existing upstream pin checks run against code Git identity and required
  composed checks cannot silently skip absent spec/dependency context.
- [ ] T010 [US3] Adapt implementation CI and root exact-pin integration checks
  with explicit compatible checkout context; preserve current Linux/macOS/
  Windows/WSL policies, Bash 3.2 parsing and serialized `tests/run.sh` locking.
  Verify the exact rehearsed composed state passes required checks and the
  compatibility matrix, recording failures rather than deleting assertions.
- [ ] T011 [US1] Rehearse restoration/rollback of the local candidate and
  installed payload using preserved artifacts. Verify user work/jobs/claims
  survive and no force push, destructive reset or workspace-pointer rewrite
  is needed. Publish Gate A/B evidence and follow-up patch/commit inventory.

## Phase 4 — Reviewed real adoption (Gates C and D)

- [ ] T012 [US1] After #97 and #121 land, account for their final merged work
  in main and disposition any remaining local deltas. Freeze the coordinated
  source baseline and regenerate/check
  the full plan after any prerequisite/planning landings. Obtain explicit
  approval naming revisions, leg repositories/visibility, mapping, follow-ups
  and work dispositions. Verify current name availability, preservation and
  rehearsal evidence; refuse any source drift before execution.
- [ ] T013 [US1] Execute the approved standard adoption from the isolated
  clone. Verify and relay the complete content-accounting table and root PR
  details; stop landing on any refusal/mismatch, retaining all source/evidence.
- [ ] T014 [US3] Apply reviewed follow-ups and prepare code/spec PRs together.
  For accepted bounded adjustments, retain authority/baseline/requirements/tasks
  and dispositions in manual code-local records, update working Speckit files
  before implementation and create one spec reconciliation issue at the first
  amendment. Escalate larger current scope to full governance; defer unnecessary
  capabilities to linked future issues. Prepare final reconciliation against
  tested behavior; code may land first, but completed assembly advancement waits
  for matching reconciled spec. Verify no in-place pinned-shape edits.
- [ ] T015 [US2] Validate the real exact assembled head using canonical tests,
  required platform/CI, installed/local/raw compatibility, bootstrap and rollback
  checks, including prepared continued-feature translations and disposable
  workflow evidence from T016–T018. Complete one final spec reconciliation batch with net tested effects,
  every amendment disposition, dated departures/as-built record, archived approval
  provenance, deferred issues and actual landed code/evidence. Land spec, close
  its reconciliation issue and advance matching root gitlinks/pins/workflow SHAs
  with standard tools; verify final Gate D results at the actual selected commits
  before root adoption merge. Keep original development/install available.

## Phase 5 — Continue features and controlled cutover (Gate E)

- [ ] T016 [US1] Translate the complete approved feature 001 delta and any
  dirty/untracked work captured at cutover into paired `001` spec/code branches/worktrees with
  reviewed root changes. Verify content/old-to-new receipts, roles, inventory
  amendment and open runtime gates. Carry the clean `3c26041` checkpoint's
  restored rollover/workspace packets, launcher contract and FR-047/T063–T065;
  preserve workBenches/Omnigent ownership and required local adapter qualification
  separately from factory-broker admission. Preserve approved original repository/
  commit/path and verify extracted spec correspondence, repairing links/task roots
  without guessed hashes. Full feature-branch proposals remain in spec; preserve
  any actual bounded records in code and continued reconciliation obligations.
  Do not replay completed work or claim new
  runtime acceptance from migration.
- [ ] T017 [US1] Translate every other approved continued PR/branch/detached
  worktree, including this migration feature, with explicit spec/code/root
  mappings and conflict review. Verify each object has a complete receipt or
  approved archived-original disposition; preserve original PR review history.
  Current candidates are #97/#121 and feature 004. Account for merged
  #61/#146/#134 through the baseline and retired/retained merged checkout history
  through receipts; do not recreate cleaned worktrees or replay integrated changes.
  Verify approved baseline correspondence and artifact roles for every continued
  feature, including this migration's full proposal in spec.
  Capture PR #121's complete active index/working files and untracked `005`
  feature/full legacy authority decision; carry its confirmed-legacy-only scope,
  managed/unknown refusal and merge hold into paired `005` continuation. Keep
  PR #97's separately owned diagnostics and current branch head independent.
- [ ] T018 [US3] Exercise OpenSpec/Speckit feature selection and estate
  park/resume in disposable triad fixtures, then perform reviewed binding/WIP
  transitions through supported tools at owner breakpoints. Verify correct
  feature roots/session bindings and relay refusals without force repairs.
- [ ] T019 [US3] Publish Gate E/cutover evidence and actual PR dispositions;
  verify all continued features are usable and recoverable before requesting
  separate old-worktree retirement. Verify each continued feature retains its
  outstanding reconciliation/runtime gates rather than declaring it implemented.
  Archive the migration's full spec change only after implementation and assembly
  pin landing; explicitly select its root and pin any later archive commit normally.
  Reopen reconciliation for subsequent behavior changes; record cancellation as
  abandonment. Do not auto-close old PRs or delete backups.

## Dependencies

Reviewed preliminary inventory, mapping and prerequisite availability from
T001–T003 permit disposable provisional rehearsal while writers remain active;
complete Gate A preservation is required before real source freeze.
T004–T006 precede integration validation;
T007–T010 may progress within the rehearsed topology after byte accounting.
T011 closes Gate B. T012 requires Gate A/B and is the real-creation approval
boundary. T013–T015 precede root adoption merge. Prepare T016–T017 translations
and T018 disposable workflow checks in the candidate after legs exist, before
T015's final reconciliation. Actual T018 lane rebinding follows reviewed root
adoption/cutover and safe breakpoints. T019 requires validated retained feature
receipts; later behavior changes reopen reconciliation before another completed
assembly advancement.

## Requirement coverage

| Requirement | Tasks |
| --- | --- |
| FR-001, FR-002 | T003–T005, T012–T013 |
| FR-003 | T001–T002, T016–T017 |
| FR-004 | T005, T009, T014 |
| FR-005 | T007–T008, T015 |
| FR-006 | T003, T006, T009 |
| FR-007 | T016–T018 |
| FR-008 | T009–T010, T015 |
| FR-009 | T014–T015 |
| FR-010 | T003–T005, T011–T013 |
| FR-011 | T002, T011, T018–T019 |
| FR-012 | T001, T012, T018–T019 |
| FR-013 | T003, T006, T016–T017 |
| FR-014 | T006, T016–T018 |
| FR-015 | T014–T015 |
| FR-016 | T014–T015, T019 |
