# Migration plan: openRepoTools assembly/spec/code triad

**Feature**: `004-migrate-to-triad` | **Date**: 2026-10-03
**State**: Proposed plan; no migration, install or repository creation performed
**Refresh**: 2026-10-04; adopted amendment protocol and merged PR #134 incorporated
**Spec**: [spec.md](spec.md)
**Governance**: [proposal](../../openspec/changes/migrate-to-triad/proposal.md)

## Baseline and deliverables

The [adoption mapping](../../openspec/changes/migrate-to-triad/adoption-plan.yaml)
was regenerated from main `daed20957f2dd2f22cca24053bb5bc8636ff6b3f` using pinned
openRepoShape `39d5c986fcfac1a160474bfe91c5f1c37fccc72c`. All 64 tracked
paths are resolved: 18 spec, 40 code, six root, zero dropped. There are
28 named follow-ups, including protocol placement/provenance/reconciliation.
This is an inspected preliminary baseline; regenerate
after planning lands and the actual cutover source is frozen.

Main advanced with merged PR #134 and matches the read-only GitHub observation;
#61 and #146 remain included. There are six
worktrees and six local branches, including this planning checkout and the
retained `feat/claude-current` checkout, whose merged changes need no replay.
The two open PRs are #121 and #97. Feature 001 remains at
`3c26041a4444a10bc240cb64a168ece4d9edf6c5`, committing its broker/task-recovery
changes, restored rollover/workspace packets and October 4 launcher contracts.
Main and feature 001 remain clean. Concurrent work in PR #121's checkout now
includes staged/unstaged/untracked content and `005-supervised-legacy-ctx`;
the recovery branch also advanced. The inventory is an observation, not a
freeze of active writers.
The [inventory](inventory.json) keeps the October 3 cleanup as history and
records current heads, dirty counts and the two remote-only preservation refs.
Machine paths, secrets/transcripts and backup contents are omitted; private
receipts must capture them at the execution gate. Clean commits do not replace
verified preservation/restore receipts.

Cleanup does not require recreating removed worktrees. Continue only the
retained work below, and verify existing preservation receipts for retired
objects. Snapshot refresh alone does not complete preservation Gate A.

The [protocol review](protocol-review.md) records the October 4 manual default
and source snapshots. Full proposals, archives, canonical specs/contracts and
Speckit files stay in spec. Genuine bounded amendments belong in the code
feature folder and require immediate working-spec updates plus final docs
reconciliation. Schema/routing/distribution/placement automation is pending.

## Target placement

| Owner | Existing paths / generated responsibilities | Reason |
| --- | --- | --- |
| Assembly `openRepoTools` | `AGENTS.md`, `CLAUDE.md`, `README.md`, `LICENSE`, `.gitattributes`, `.gitignore`; generated manifest/Makefile/validators and assembly pins | Front door and project coordination across legs. |
| Spec `openRepoTools-spec` | `openspec/`, `specs/`, `docs/`; feature 001's retained `ideation/` and restored planning packets | Product requirements, decisions and manual; feature-only paths need separate replay accounting. |
| Code `openRepoTools-code` | All executable tools, `repos.tsv`, `commands/`, `skills/`, `tests/`, implementation CI | Shipped implementation and its installer payload. |
| Code dependency unit | Original `.gitmodules`, `upstream/openRepoShape`, `contracts/openreposhape-pin.yaml` | Keep module registration, exact gitlink and dependency lock together. |
| Code amendment exception | Genuine bounded `features/<NNN-feature>/openspec/` records, deltas and evidence references | Relative changes against an approved spec baseline; explicitly review placement until upstream qualification. No such tracked paths were observed in the current source or retained feature heads. |
| Root workflow bootstrap | `.specify/`, project agent links and selected feature pointer | Currently local/ignored; capture config and regenerate shape-aware root scaffolding. |

After byte-preserving extraction, add a root installation entry point that
resolves the exact code pin. The original installer implementation moves to
code; the root entry point selects and invokes it. Preserve the existing user
one-liner and installed command names. Do not duplicate installer mechanics.

## Phase 1 — Review and preserve work

Land the planning artifacts through normal review before freezing execution.
Refresh GitHub PR/main observations and local branch/worktree state. This
single repository has no estate manifest yet: `status --fetch openRepoTools`
currently refuses with no estate named openRepoTools and performs no fetch.
Relay that refusal; do not run `resume` to silence it. Use the estate status
surface after a valid adopted root exists. Verify the proposed leg names are available
and decide visibility. Agree a bounded cutover with current lane owners.
Capture original history, all branch refs, detached HEADs, staged/unstaged and
untracked content, ignored workflow config and installed receipts/config.
Use host-local backups or the existing private WIP repository; public records
hold only safe identities/digests. Prove restoration before declaring capture
complete. Never edit workspace.yaml or recreate estate parking logic.

Recommended active-work dispositions are proposals, not merge/closure actions:

| Work | Proposed treatment |
| --- | --- |
| `001-separate-swap-ctx-handoff` | Continue from committed, clean head `3c26041`; preserve the complete branch delta, restored rollover/workspace packets and launcher/broker contracts. Migrate to paired `001` worktrees; keep tasks, evidence, roles and activation gates. |
| PR #97 | Preserve its current advanced recovery branch, review history and diagnostic role separately from managed LS authority and PR #121. Carry useful diagnostics under feature 001's service authority without merging unchanged or auto-closing through adoption. |
| PR #121 / feature `005-supervised-legacy-ctx` | Preserve complete staged/unstaged/untracked contents and the full legacy authority decision. Continue paired `005` worktrees for confirmed legacy-only supervised restart; managed/unknown ownership refuses. Keep the existing merge hold and PR #97 ownership separate. The full proposal/decision/specs stay in spec, implementation/tests in code; this authority decision is not a bounded local amendment. |
| PR #146 / `fix/107-pty-driver-bound-and-lane-per-call-cost` | Merged as `82ecebe`; checkout and local branch removed during concurrent cleanup. Included by baseline extraction; do not replay separately. |
| PR #134 / `feat/claude-current` | Merged as `daed209`; the retained clean checkout at `11037f0` is preservation history. Resolver/checker, installer, preflight/fencing, timeout tests and manual are included by the regenerated baseline. Do not replay separately or retire the checkout as part of planning. |
| PR #61 | Merged as `14641fd`, an ancestor of current main; included by baseline extraction. Do not replay the retired claim-takeover branch separately. |
| Retired `002`, `003`, lclaude and detached worktrees | Removed from current registrations/local branches by cleanup. Verify cleanup/preservation receipts; remove from the active replay queue and do not recreate them from the old snapshot. |
| Remote-only preservation refs | `chore/preserve-local-planning-20261003` and `takeover/ort-a9-dirty-snapshot-20260913` remain locally observed remote-tracking refs with no checkout; review as preservation history, not active writers. |
| Migration feature `004` | Previous refresh committed at `dda91f1`; existing checkout reused for this update. This full proposal and canonical feature files stay in spec; any genuine bounded implementation amendments belong in code. |

**Gate A:** every preserved object is attributable and restorable; no active
writer can silently invalidate capture. Baseline, visibility and work
dispositions are ready for review, with any unresolved owner decision explicit.

## Phase 2 — Rehearse locally and make follow-ups reviewable

Use a fresh isolated source clone at the chosen source commit with no linked
worktrees. Make `git-filter-repo` available through the approved prerequisite
path. Regenerate the mapping, retain reasoned overrides and run standard check.
Rehearse the standard's adoption against temporary local bare remotes with no
real GitHub repository creation or default-branch movement.

Verify nested dependency extraction, source `.gitmodules` handling, full
baseline accounting, leg histories and recursive bootstrap. Exercise all
actual file-placement collisions. If the standard refuses or misaccounts
content, relay it and resolve through a reviewed standard change/pin bump;
do not patch the pinned submodule or adjust digests to manufacture success.
Review genuine amendment paths explicitly as code using a reasoned project-local
resolution until the upstream exception is qualified. Full proposals created
on feature branches remain full proposals in spec; do not manufacture amendments
for historical features. Record original approved repository/commit/path and
verified extracted spec correspondence: filtering may change commit hashes.
Repair relative links, selected roots/stores and task paths without guessing
new baseline identities or replacing approval provenance with the split tip.

Implement and review the necessary installer entry point/resolver, explicit
test-root context, CI layout, agent pointers, docs paths and workflow bootstrap
in the rehearsed arrangement. Record their patches and resulting commits so
real execution can apply the reviewed changes after source verification.
Add leg root guidance without overwriting original root guidance. Preserve
the Bash 3.2 floor and original no-submodule test behavior, while requiring
complete dependencies for composed acceptance.

Operate full proposals from the intended feature spec checkout and bounded
amendments from the code feature folder. Verify checkout, branch and root for
each operation; a local root takes precedence over a docs-store pointer.
Use explicit `--store` only if the installed CLI supports it and resolves the
intended feature checkout. Maintain amendments manually until schema/routing
is qualified. Check workBenches protocol/command distribution on each target
workstation; regeneration of root scaffolding alone does not distribute this
decision. Pending automation remains with workBenches/openRepoShape.

**Gate B:** complete local rehearsal evidence, restore rehearsal, reviewed
follow-up patches, resolved mapping and a passing compatibility test matrix.
Mapping `check` alone does not satisfy this gate.

## Phase 3 — Freeze and approve real adoption

Coordinate a bounded main landing hold using applicable lane protocol. Re-read
current main and owner state, finalize source commit, mapping, standard pin,
visibility, follow-ups and preservation receipts. Any source drift requires
plan regeneration and check, not editing the commit field by hand. Present
the final plan and follow-ups for explicit approval before real execution.

**Gate C:** approval names the actual source/standard revisions, leg repositories,
visibility and final plan; prerequisites, Gate A/B evidence and no-name-collision
checks are current. Do not infer consent from this planning request.

## Phase 4 — Create the legs and assemble the reviewed candidate

Run the standard's approved `execute` from the isolated clone. It creates
the legs, extracts histories, mounts/pins them, opens the root split PR and
prints content accounting. Relay its table and refusals. A nonzero verification
stops landing; preserve source and newly created evidence/branches. Never rerun
over live legs or bypass a ruleset.

After successful source verification, apply reviewed follow-ups through the
new leg/root PRs and prepare docs/code review together. For bounded migration
adjustments, record decision authority, approved baseline, unique amendment ID,
affected requirements/tasks and evidence in code; update working Speckit files
in the paired spec worktree before dependent implementation. Create one spec
reconciliation issue at the first amendment and link every later record. Larger
scope, runtime, authority or external-contract changes require full spec
governance; defer unnecessary capabilities to linked future-proposal issues.
Speckit remains the sole executable task list.

Resolve `shape/` collisions explicitly; do not overwrite
pinned shape files. Put `Read AGENTS-shape.md first...` guidance first in root
agent instructions and bootstrap shape-aware OpenSpec/Speckit only when both
legs exist. Prepare continued-feature translations and disposable workflow
checks from Phase 5 in the candidate before the final migration batch; actual
lane rebinding still waits for reviewed cutover. After implementation and verification, reconcile the net tested
effect in one final spec batch: governing specs/contracts/design, dated departures,
as-built record, all amendment dispositions, evidence, deferred ideas and the
actual landed code commit. Retain superseded/reverted/deferred history while
excluding inactive deltas. Preserve archived approvals through linked records.
Code may land first; completed assembly advancement waits for reconciliation
to land and matching spec/code pins. Close the reconciliation issue after the
spec PR lands; the feature landing record tracks the assembly PR. Advance
gitlinks, pin digests and workflow SHAs together using the standard bump tool.

**Gate D:** prepared continued-feature receipts and disposable workflow checks
are reviewed; final reconciliation and matching spec/code commits are landed;
exact assembled commits pass manifest/pin checks, canonical code
tests/platform checks, install compatibility and bootstrap. The existing
source/install remain usable until root adoption review and merge complete.

## Phase 5 — Continue features and cut over lanes

Translate each approved retained feature delta into reviewed spec/code/root
changes and dirty/untracked replay with checksums. Use paired feature branches
and worktrees under `worktrees/<feature>/{spec,code}`; preserve feature IDs and
map old commits to new leg commits. Review conflicts semantically. Account
for completed/landed work before replaying it. Retain original worktrees.

Prove feature 001's service-owned inventory requirements, restored
`add-automatic-context-rollover` governance and lane-set workspace/rollover
brainstorm packets survive the replay. Carry its accepted October 4 launcher
contract and FR-047/T063–T065 without claiming runtime acceptance: workBenches
owns `pclaude`/`oclaude`/`lclaude`, openRepoTools owns LS admission/custody, and
Omnigent owns its local adapter/transport. Required local Omnigent qualification
for the selected lane stack and separate factory-broker admission gates remain
feature 001's delivery conditions. Repository adoption neither implements
those wrappers nor moves their ownership into this repository. Test feature
selection, OpenSpec/Speckit prerequisites and estate park/resume in disposable
fixtures. Apply supported WIP record updates only through their established
contracts; relay refusals. Rebind each lane at its reviewed safe breakpoint,
using the existing binding tools and exact session records.

**Gate E:** every continued feature has a reviewed migration receipt and
preserved source; bindings and workflow resolve the intended new trees.
Each continued feature retains its governing baseline and reconciliation
obligations; migration does not declare unfinished features implemented.
Obsolete PR disposition and any old-worktree retirement are separate explicit
decisions after verification, never an automatic cleanup step.
Archive the migration's full spec change only after implementation and assembly
pin landing. Explicitly select that root; a local amendment archive proves no
reconciliation. Pin subsequent archive-record spec commits normally. Reopen
reconciliation if behavior changes afterward; cancellation records abandonment
and dispositions rather than an as-built result.

## Rollback

Before root merge, leave the reviewed candidate unmerged and keep original
development/install active. Newly created legs/branches remain for diagnosis;
do not delete them automatically. After root merge, restore the last working
assembly/code selection through reviewed revert/pin-bump PRs and the preserved
installer, without force push/resetting user work. Preserve any post-cutover
feature edits and uncertain jobs before changing bindings. Return lanes only
through supported tooling at a safe breakpoint; private workspace pointers
and claims are not rewritten to hide a failure.

## Technical context and checks

Implementation remains Bash (macOS 3.2), Python standard-library tooling and
Git/GitHub workflows. Run build/test/CLI work in the project bench, with shared
`tests/run.sh` locking. No real repository is created for a test. The local
constitution is an unfilled template; no ratification is inferred. Preserve
the existing root rules, standard pin checks and global workflow protocols.

Planning checks: [verification.md](verification.md). Executable work and
requirement coverage: [tasks.md](tasks.md). All execution tasks remain open.
