# Implementation tasks: migrate openRepoTools to the triad

The sole executable task list for the governing OpenSpec change. Planning
artifacts and preliminary mapping validation do not complete these tasks.
Every task remains open. Run implementation from the selected feature
worktrees; actual repository creation/cutover require the approval gates.
The cleanup refresh updates the snapshot/mapping portion of T001/T003 only;
owner decisions, private preservation/restore receipts and execution gates
remain pending. Retired checkouts are not instructions to recreate worktrees.

## Phase 1 — Preservation and baseline (Gate A)

- [ ] T001 [US1] Refresh `inventory.json`, PR/main/branch/worktree metadata and
  applicable estate-status output; distinguish retained work from retired
  cleanup records and remote-only drafts. Until an estate manifest exists,
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
  passes and records all source paths with no unapproved drops.

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

- [ ] T012 [US1] Freeze the coordinated source baseline and regenerate/check
  the full plan after any prerequisite/planning landings. Obtain explicit
  approval naming revisions, leg repositories/visibility, mapping, follow-ups
  and work dispositions. Verify current name availability, preservation and
  rehearsal evidence; refuse any source drift before execution.
- [ ] T013 [US1] Execute the approved standard adoption from the isolated
  clone. Verify and relay the complete content-accounting table and root PR
  details; stop landing on any refusal/mismatch, retaining all source/evidence.
- [ ] T014 [US3] Apply reviewed follow-ups through leg/root PRs, land required
  leg commits, and advance root gitlinks/pins/workflow SHAs with standard tools.
  Verify no in-place edits to copied pinned shape files or the mounted standard.
- [ ] T015 [US2] Validate the real exact assembled head using canonical tests,
  required platform/CI, installed/local/raw compatibility, bootstrap and rollback
  checks. Verify all Gate D results belong to the selected commits before root
  adoption merge; keep original development/install available until then.

## Phase 5 — Continue features and controlled cutover (Gate E)

- [ ] T016 [US1] Translate the complete approved feature 001 delta and preserved
  dirty/untracked work into paired `001` spec/code branches/worktrees with
  reviewed root changes. Verify content/old-to-new receipts, roles, inventory
  amendment and open runtime gates; do not replay completed work or claim new
  runtime acceptance from migration.
- [ ] T017 [US1] Translate every other approved continued PR/branch/detached
  worktree, including this migration feature, with explicit spec/code/root
  mappings and conflict review. Verify each object has a complete receipt or
  approved archived-original disposition; preserve original PR review history.
  Current candidates are #97/#121/#134 and feature 004. Account for merged
  #61/#146 through the baseline and retired checkout history through its receipts;
  do not recreate cleaned worktrees or replay integrated changes.
- [ ] T018 [US3] Exercise OpenSpec/Speckit feature selection and estate
  park/resume in disposable triad fixtures, then perform reviewed binding/WIP
  transitions through supported tools at owner breakpoints. Verify correct
  feature roots/session bindings and relay refusals without force repairs.
- [ ] T019 [US3] Publish Gate E/cutover evidence and actual PR dispositions;
  verify all continued features are usable and recoverable before requesting
  separate old-worktree retirement. Do not auto-close old PRs or delete backups.

## Dependencies

T001–T003 precede rehearsal. T004–T006 precede integration validation;
T007–T010 may progress within the rehearsed topology after byte accounting.
T011 closes Gate B. T012 requires Gate A/B and is the real-creation approval
boundary. T013–T015 precede root adoption merge. T016–T018 can be prepared in
the candidate after legs exist, but actual lane rebinding follows reviewed
cutover and safe breakpoints. T019 requires validated retained feature receipts.

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
