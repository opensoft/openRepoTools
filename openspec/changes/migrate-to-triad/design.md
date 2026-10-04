# Design: in-place triad adoption

## Context

The refreshed preliminary source is main `82ecebee13edaa915b68550170faffdf761754d5`:
58 tracked paths, 79 commits, one nested standard submodule. The inspected
standard is `39d5c986fcfac1a160474bfe91c5f1c37fccc72c`. The October 4 refresh
found unchanged main, six worktrees including planning and the restored
`feat/claude-current` checkout, and six local branches. The three open PRs
are #134, #121 and #97; #134 is non-draft at `11037f0`. #61 and #146 are
included in main and need no separate replay. Feature 001 is now committed
and clean at `3c26041`, including restored rollover/workspace packets and the
selected local Omnigent launcher contract. Main extraction alone still omits
that branch work. Preserve its contracts, external launcher ownership and
unmet runtime gates during replay. Removed worktrees are not an active replay queue. The
[inventory](../../../specs/004-migrate-to-triad/inventory.json) is a snapshot.

## Goals / Non-Goals

Preserve project identity/history, all user work, installed command behavior
and a reproducible pinned assembly. Separate product decisions from shipped
implementation; migrate unfinished features without restarting specification.
Do not redesign swap, enable its experimental capability, change WIP ownership,
rewrite published source history or remove old worktrees during adoption.

## Decisions

### Assembly identity and source baseline

Use the standard's in-place adoption. `openRepoTools` stays the existing
assembly; `openRepoTools-spec` and `openRepoTools-code` are new legs mounted
at `spec` and `code`. Public visibility is a proposal matching current source
visibility, subject to final approval. A new assembly name would strand
existing issues, URLs and PRs, so is outside this design.

Run real adoption from a fresh clean default-branch clone with no linked
worktrees attached. Original working clones remain preserved. Freeze the
baseline only after planning and any agreed prerequisite changes land; refresh
the generated plan whenever that commit moves. Approval binds the actual
baseline, standard commit, complete mapping and follow-ups.

### Placement and dependency custody

The [resolved adoption plan](adoption-plan.yaml) accounts for all 58 baseline
paths: 17 spec, 35 code, six root, none dropped. It records reasons for all
14 originally unresolved paths and overrides for shipped Markdown payloads
and the dependency lock. Product documentation/OpenSpec/Speckit go to spec.
Root owns front-door guidance, license, project metadata and workflow bootstrap.

Keep executable files, `repos.tsv`, shipped `commands/` and `skills/`, tests
and implementation CI in code. The original `.gitmodules`, mounted standard
and `contracts/openreposhape-pin.yaml` also stay together in code. At this
baseline that contract is solely a dependency lock, not product governance.
Generated root shape/spec/code pins are distinct. Future governance contracts
belong in spec; regenerate the path plan if the source adds such contracts.

Keeping the standard in root would move its gitlink away from its dependency
pin and implementation consumers, and mutate the original `.gitmodules` during
the byte-accounted split. Keeping that dependency unit in code preserves its
existing paths. Existing-submodule handling still requires local rehearsal;
plan coverage validation alone is not execution certification.

### Public installation compatibility

After successful byte accounting, add a root `openRepoTools` compatibility
entry point. It resolves one assembly revision and its exact code pin, then
loads the implementation at that immutable commit. All install payloads come
from that same code commit. Preserve the existing `gh api .../openRepoTools`
and raw-URL one-liners, local/offline invocation, override/fork behavior,
destination names, artifact counts, permissions, hooks, receipts and atomic
refusal semantics. No request may silently combine root/spec/code main tips.

The code installer has a self-contained local payload tree; installed commands
must not depend on the developer's assembly checkout. Source/ref resolution
must support the existing monorepo override form, an adopted assembly fork and
explicit code checkout execution. Missing or inconsistent pins refuse before
installation effects. Implementation tests define the compatibility matrix;
this document does not invent a second installer implementation.

### Development and active work

The sole executable list is the linked Speckit feature. `.specify/` and agent
links are currently ignored local scaffolding, so baseline blob extraction
does not preserve them. Inventory local configuration and regenerate workflow
at the assembly root with the shape-aware bootstrap. Retain the root guidance
and the named team assignments in feature 001. Leg guidance points back to root.

Classify each active feature's delta relative to its own reviewed merge base;
translate it into selected spec/code/root changes with old-to-new commit/file
receipts. Include dirty/untracked files in preservation and replay validation.
Preserve original branches and PRs while replacement branches are reviewed.
Paired leg worktrees use the existing feature name under root `worktrees/`.
Do not cherry-pick a mixed monorepo commit wholesale into either leg, or merge
an old feature branch into the adopted assembly. Do not retire/rebind a live
lane until its owner has reached a safe breakpoint and replacement evidence
is reviewed. WIP records remain in their existing private repository and use
the supported estate workflow; public records contain no private backups.

### CI and exact-pin delivery

Code CI runs implementation checks; root CI validates manifest/pins and the
exact composed assembly. Supply explicit code/spec/assembly roots to tests
that inspect docs or history; preserve the nested dependency pin assertions
in the code Git repository. Use the canonical serialized `tests/run.sh`,
Bash 3.2 parsing and current platform/fixture timing policies. Missing-spec
context cannot turn a required integration check into a silent skip.

Land follow-up leg changes before the root pin bump that selects them. Root
gitlinks, leg pins and workflow SHAs move through the standard's bump tool.
The historical upstream dependency remains one-way and unedited; needed
standard fixes land there before a deliberate pin bump here.

## Risks / Trade-offs

- Local mapping passes while existing-submodule extraction fails: gate real
  execution on an isolated local bare-remote rehearsal with intact gitlink,
  module metadata, pin and recursive bootstrap.
- Historical commits/files change or disappear: retain original repository,
  bundles/private work backups and migration receipts; require blob accounting
  for the frozen baseline and explicit verification of each replayed delta.
- An active lane writes during capture: coordinate a bounded owner-approved
  breakpoint, then refresh capture and compare checksums before cutover.
- Installer entry point vanishes or mixes revisions: add compatibility before
  root merge; validate exact-ref/fork/offline and all-or-none installation.
- CI cannot read the selected assembly/spec context: publish explicit composed
  checkout instructions and preserve the original canonical regression gate.
- New roots make WIP paths stale: use supported park/resume contracts and
  reviewed migration records; never overwrite workspace pointers or force a
  refusal through with resets.

## Migration Plan

The [Speckit plan](../../../specs/004-migrate-to-triad/plan.md) owns sequencing,
gates, active PR decisions, cutover and rollback. This change is planning-only.
`git-filter-repo` is absent in the inspected `py-bench`; make prerequisite
availability an execution gate, without installing it during planning.

## Approval decisions

Confirm public new legs, the refreshed frozen baseline/mapping, branch/PR
dispositions, coordinated cutover and repository creation only after the
local rehearsal and compatibility work are reviewable. No approval is inferred
from OpenSpec artifact completeness or the generated election metadata.
