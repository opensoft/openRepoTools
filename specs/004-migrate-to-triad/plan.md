# Migration plan: openRepoTools assembly/spec/code triad

**Feature**: `004-migrate-to-triad` | **Date**: 2026-10-03
**State**: Proposed plan; no migration, install or repository creation performed
**Spec**: [spec.md](spec.md)
**Governance**: [proposal](../../openspec/changes/migrate-to-triad/proposal.md)

## Baseline and deliverables

The [adoption mapping](../../openspec/changes/migrate-to-triad/adoption-plan.yaml)
is generated from main `c1bac0dfc99a62583cb62eafc93a192911b2ff22` using pinned
openRepoShape `39d5c986fcfac1a160474bfe91c5f1c37fccc72c`. All 58 tracked
paths are resolved: 17 spec, 35 code, six root, zero dropped. There are
21 named follow-ups. This is an inspected preliminary baseline; regenerate
after planning lands and the actual cutover source is frozen.

The [inventory](inventory.json) records 12 worktrees (including migration
planning), four open PRs and dirty feature 001 work. It omits machine paths,
secrets/transcripts and backup contents. Host-local/private preservation
records must capture actual paths, content and digests at the execution gate.

## Target placement

| Owner | Existing paths / generated responsibilities | Reason |
| --- | --- | --- |
| Assembly `openRepoTools` | `AGENTS.md`, `CLAUDE.md`, `README.md`, `LICENSE`, `.gitattributes`, `.gitignore`; generated manifest/Makefile/validators and assembly pins | Front door and project coordination across legs. |
| Spec `openRepoTools-spec` | `openspec/`, `specs/`, `docs/`; later feature ideation/governance artifacts | Product requirements, decisions and manual. |
| Code `openRepoTools-code` | All executable tools, `repos.tsv`, `commands/`, `skills/`, `tests/`, implementation CI | Shipped implementation and its installer payload. |
| Code dependency unit | Original `.gitmodules`, `upstream/openRepoShape`, `contracts/openreposhape-pin.yaml` | Keep module registration, exact gitlink and dependency lock together. |
| Root workflow bootstrap | `.specify/`, project agent links and selected feature pointer | Currently local/ignored; capture config and regenerate shape-aware root scaffolding. |

After byte-preserving extraction, add a root installation entry point that
resolves the exact code pin. The original installer implementation moves to
code; the root entry point selects and invokes it. Preserve the existing user
one-liner and installed command names. Do not duplicate installer mechanics.

## Phase 1 — Review and preserve work

Land the planning artifacts through normal review before freezing execution.
Refresh current estate status using `status --fetch`, open PR metadata and
branch/worktree observations. Verify the two proposed leg names are available
and decide visibility. Agree a bounded cutover with current lane owners.
Capture original history, all branch refs, detached HEADs, staged/unstaged and
untracked content, ignored workflow config and installed receipts/config.
Use host-local backups or the existing private WIP repository; public records
hold only safe identities/digests. Prove restoration before declaring capture
complete. Never edit workspace.yaml or recreate estate parking logic.

Recommended active-work dispositions are proposals, not merge/closure actions:

| Work | Proposed treatment |
| --- | --- |
| `001-separate-swap-ctx-handoff` | Preserve full branch delta and dirty/untracked additions; migrate to paired `001` spec/code worktrees. Keep tasks, evidence, roles and activation gates. |
| `002-skip-no-lane-guard`, `003-binary-only-guard-runner` | Inspect remaining deltas versus main; migrate useful unfinished work or retain archived branch receipts if already landed. |
| PR #97 | Preserve branch/review; carry useful diagnostics into feature 001 under its service authority. Do not merge unchanged or auto-close as part of adoption. |
| PR #121 | Preserve/review independently; translate selected context-runtime work to code/spec as needed, with its readiness integration still explicit. |
| PR #134 (draft), PR #61 | Keep current heads and review history; continue selected deltas in new legs after owner review. No automatic merge or abandonment. |
| Other branches/detached worktrees/preservation branch | Inspect individually, assign continue/archive decision, retain recovery receipt; no deletion implied. |
| Migration feature `004` | Carry this plan/spec/tasks into the spec leg; assembly/code follow-ups get separate reviewed changes. Keep its own pre-migration recovery receipt. |

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

Implement and review the necessary installer entry point/resolver, explicit
test-root context, CI layout, agent pointers, docs paths and workflow bootstrap
in the rehearsed arrangement. Record their patches and resulting commits so
real execution can apply the reviewed changes after source verification.
Add leg root guidance without overwriting original root guidance. Preserve
the Bash 3.2 floor and original no-submodule test behavior, while requiring
complete dependencies for composed acceptance.

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
new leg/root PRs. Resolve `shape/` collisions explicitly; do not overwrite
pinned shape files. Put `Read AGENTS-shape.md first...` guidance first in root
agent instructions and bootstrap shape-aware OpenSpec/Speckit only when both
legs exist. Land required leg changes; advance root gitlinks, pin digests and
workflow SHAs together using the standard bump tool.

**Gate D:** exact assembled commits pass manifest/pin checks, canonical code
tests/platform checks, install compatibility and bootstrap. The existing
source/install remain usable until root adoption review and merge complete.

## Phase 5 — Continue features and cut over lanes

Translate each approved retained feature delta into reviewed spec/code/root
changes and dirty/untracked replay with checksums. Use paired feature branches
and worktrees under `worktrees/<feature>/{spec,code}`; preserve feature IDs and
map old commits to new leg commits. Review conflicts semantically. Account
for completed/landed work before replaying it. Retain original worktrees.

Prove feature 001's amended service-owned inventory requirements and new
planning work are present without claiming runtime acceptance. Test feature
selection, OpenSpec/Speckit prerequisites and estate park/resume in disposable
fixtures. Apply supported WIP record updates only through their established
contracts; relay refusals. Rebind each lane at its reviewed safe breakpoint,
using the existing binding tools and exact session records.

**Gate E:** every continued feature has a reviewed migration receipt and
preserved source; bindings and workflow resolve the intended new trees.
Obsolete PR disposition and any old-worktree retirement are separate explicit
decisions after verification, never an automatic cleanup step.

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
