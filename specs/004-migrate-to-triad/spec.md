# Feature specification: migrate openRepoTools to the triad

**Feature**: `004-migrate-to-triad`
**Created**: 2026-10-03
**Status**: Proposed; planning complete enough for review, execution gated
**Governing change**: [migrate-to-triad](../../openspec/changes/migrate-to-triad/proposal.md)

## User scenarios

### US1 — Preserve history and unfinished work (P1)

The operator reviews an exact adoption mapping and current branch/worktree
inventory, then converts the existing repository without losing unpublished
or dirty work. Validate byte-accounted baseline extraction, nested dependency
preservation, and replay receipts for a mixed spec/code feature and its new files.
Missing content, stale baseline, unavailable backup or an unresolved placement
blocks execution/cutover. Preserve source branches and local work on refusal.

### US2 — Install through the existing entry point (P1)

A user runs the existing raw-URL or `gh api` one-liner, or installs from an
offline local checkout. Every payload comes from one selected immutable code
revision; command names, permissions, artifact counts, hooks and receipts are
preserved. Test forks/ref overrides, missing pins and partial fetch refusal.

### US3 — Continue feature development and deliver exact pins (P2)

The operator continues existing feature IDs through paired spec/code worktrees
and lands their changes through leg PRs followed by a validated assembly pin
bump. Full OpenSpec proposals run in the selected spec checkout; genuine
bounded amendments use the code feature folder with explicit root selection.
Speckit runs from assembly with selected feature paths. A code-only clone
cannot falsely claim composed CI success.
The migration preserves feature 001's model-role assignments and open gates.

## Functional requirements

- **FR-001**: Keep `opensoft/openRepoTools` as assembly with full original
  history; extract spec/code using the reviewed standard procedure.
- **FR-002**: Pin a source commit; resolve every path with reasons, account
  for blobs/gitlinks, and reject a stale or unresolved plan.
- **FR-003**: Preserve and verify all active branches/PRs, detached worktrees,
  dirty/untracked content and ignored workflow configuration before cutover.
- **FR-004**: Preserve the code dependency unit: `.gitmodules`,
  `upstream/openRepoShape` and `contracts/openreposhape-pin.yaml`; verify nested
  extraction/recursive bootstrap and retain the standard's exact pin semantics.
- **FR-005**: Keep original installation entry points and one immutable payload
  revision, including forks/ref overrides, local/offline behavior and existing
  all-or-none ownership/receipt semantics; do not depend on developer checkouts.
- **FR-006**: Put full proposals, archives, canonical OpenSpec/Speckit/docs in
  spec and implementation plus shipped skills/commands/tests in code; project
  workflow stays at root. Genuine bounded feature amendments are the narrow
  code placement exception under FR-013, not a second spec baseline.
- **FR-007**: Continue selected feature deltas with old/new identity and
  content receipts, paired leg worktrees and unchanged feature/role meanings.
  Do not merge old monorepo branches over the adopted assembly.
- **FR-008**: Run canonical serialized tests and existing platform/CI policies
  against explicitly selected compatible roots; preserve required checks and
  prohibit silent context/dependency skips from claiming composed acceptance.
- **FR-009**: Land leg changes before the root pin bump; move gitlinks, pin
  records/digests and applicable workflow SHAs consistently with standard tools.
- **FR-010**: Require a clean isolated source, available prerequisites, local
  bare-remote rehearsal and explicit approval before real repository creation.
- **FR-011**: Preserve original worktrees and installed tools until cutover
  acceptance; use non-destructive rollback and existing estate/WIP contracts.
- **FR-012**: Treat visibility, baseline, branch disposition and lane rebinding
  as reviewed execution decisions; never infer approval from generated metadata.
- **FR-013**: Explicitly review genuine bounded
  `features/<NNN-feature>/openspec/` records as code until upstream placement
  is qualified. Full proposals retain their role regardless of source branch;
  do not manufacture local amendments for historical features or change pins
  to hide an unqualified placement rule.
- **FR-014**: Preserve approved original repository/commit/path provenance and
  verify correspondence to extracted spec identities after filtering. Repair
  cross-leg links, baseline references and selected feature roots/stores without
  guessing new hashes or editing pinned base mounts. Maintain records manually
  until schema/routing/distribution is qualified in its owning repositories.
- **FR-015**: Record accepted bounded adjustments with unique feature-local IDs,
  approved baseline, authority/source, affected requirements/tasks, verification
  impact and dispositions; update working spec/plan/acceptance/tasks before
  dependent implementation. Larger scope, runtime/authority or external-contract
  changes require full spec governance; unnecessary larger ideas remain deferred
  to linked future-proposal issues. Speckit is the only executable task list.
- **FR-016**: Create one spec reconciliation issue at the first amendment.
  Reconcile net tested effects once at completion, retaining all dispositions,
  approved history, as-built departures, verification and landed code identity.
  Completed assembly advancement requires landed reconciliation and matching
  spec/code pins. Close the issue after spec landing; explicitly archive the
  full spec root only after implementation and assembly landing, advancing any
  archive commit normally. Reopen for later behavior changes; cancellation
  records abandonment, not as-built completion.

## Success criteria

- **SC-001**: Every frozen baseline source path is accounted for exactly once;
  no unapproved drops or content mismatches.
- **SC-002**: Every retained feature's selected spec/code/root delta and
  dirty/untracked work has a verified receipt and preserved original.
- **SC-003**: Installation works through original entry points, offline and
  fork/ref scenarios, using one code revision with unchanged artifact behavior.
- **SC-004**: Recursive bootstrap, paired feature workflow, canonical tests and
  required CI pass for the selected composed project; no hidden skips.
- **SC-005**: A rehearsed rollback restores usable development/installation
  without discarding work, altering private workspace pointers or force pushes.
- **SC-006**: Every continued feature has verified baseline correspondence,
  explicit root selection and correct artifact roles; local archive cannot
  satisfy canonical reconciliation. Manual workflow and pending automation are
  separately evidenced on target workstations.
- **SC-007**: The tested migration has a final spec reconciliation and matching
  landed code identity before completed assembly advancement, with every
  amendment disposition accounted for and inactive deltas excluded.

## Assumptions and approval

Public new legs are proposed to match source visibility. Their creation is
not approved. `git-filter-repo` must be made available before rehearsal/execution;
it was absent in the inspected bench. The local constitution remains an
unfilled template and is not a ratified migration rule; repository/global
protocols and the pinned standard govern this plan. Refresh all snapshots
before execution. Source token/swap runtime gates are unaffected.
