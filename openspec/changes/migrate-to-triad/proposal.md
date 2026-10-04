# Proposal: migrate openRepoTools to the assembly/spec/code triad

## Why

Preparation is authorized while PRs #97/#121 are active; real conversion waits
for both to land. The [preparation receipt](../../../specs/004-migrate-to-triad/preparation.md)
records provisional preservation and a local adopter refusal. Resolve that
upstream blocker and refresh the merged baseline, preservation and rehearsal
before the existing real-execution approval gate.

openRepoTools currently keeps product decisions, implementation and project
workflow in one repository. Elect the openRepoShape triad so specifications
and implementation can evolve independently while the existing repository
pins their exact tested combination and preserves its identity and history.

## What Changes

- Adopt `opensoft/openRepoTools` in place as the assembly root; extract
  `opensoft/openRepoTools-spec` and `opensoft/openRepoTools-code` with history.
  Public legs are proposed to match the existing public source; execution
  requires explicit approval of the reviewed plan, visibility and follow-ups.
- Put OpenSpec, Speckit specifications and product documentation in `spec/`;
  executable tooling, shipped skills/commands, tests, CI and the mounted
  standard dependency in `code/`. Root agent guidance and workflow bootstrap
  span both legs. No source path is proposed for deletion.
- Apply the adopted October 4 manual amendment workflow: full proposals and
  canonical specs stay in spec; genuine bounded feature records stay in code.
  Preserve verified approved-baseline correspondence, update working Speckit
  files immediately and reconcile net tested effects once before completed
  assembly advancement. Schema/routing/distribution/placement automation remains
  pending with workBenches/openRepoShape.
- **BREAKING:** development paths and PR destinations change. Preserve command
  names, install artifacts, published one-line installation and installed
  behavior through a pinned assembly-to-code compatibility entry point.
- Preserve all open PRs, branch histories, dirty/untracked work, detached
  worktrees and workspace records before migration. Continue unfinished
  features through explicit paired spec/code branches with migration receipts;
  do not merge old monorepo feature branches over the adopted root.
- Validate a local bare-remote rehearsal before any real repository creation.
  Keep original clones/worktrees and the installed toolset usable until a
  reviewed assembly PR and exact-pin integration checks establish cutover.

## Capabilities

### New Capabilities

- `repository-triad-migration`: history-preserving adoption, placement,
  installation compatibility, active-work migration, exact-pin delivery and
  evidence-gated cutover/rollback.

### Modified Capabilities

None. No canonical capability inventory exists on the inspected source main.
Swap, context, handoff and estate-command semantics remain governed by their
existing changes; this migration does not activate experimental capabilities.

## Impact

- `openRepoTools` installer/default source selection and its bare-name payload
  lookups; assembly entry point and leg-pin resolution; fork/ref behavior.
- `tests/conftest.py`, pin/status/install/hygiene tests, `tests/run.sh`,
  `.github/workflows/tests.yml`, and cross-leg documentation references.
- `.gitmodules`, the mounted `upstream/openRepoShape` dependency and its
  `contracts/openreposhape-pin.yaml` lockstep relationship. Keep all three in
  code; generated assembly shape/spec/code pins are separate contracts.
- Global OpenSpec/Speckit bootstrap, currently ignored local `.specify/` and
  agent links, lane directory bindings, open PR destinations, and WIP records.
- Governing change: this directory. Sole implementation feature:
  [004-migrate-to-triad](../../../specs/004-migrate-to-triad/spec.md).
  See its [migration plan](../../../specs/004-migrate-to-triad/plan.md) and
  executable task list; the OpenSpec checklist records governance only.

## Planning status

Requested on October 3, 2026. Planning is authorized; migration execution,
repository creation, software installation, PR merge and lane relocation are
not authorized by this request. The attached adoption plan is a preliminary
mapping regenerated from source main `daed20957f2dd2f22cca24053bb5bc8636ff6b3f`, not a promise
that this will be the final split commit. Refresh after planning lands and the
cutover baseline is frozen. No runtime or migration success is claimed.

The protocol refresh retains the October 3 cleanup history and records six
current worktrees, including the retained merged PR #134 checkout. #134 is
included in the new main baseline; feature 001 is committed and clean at `3c26041` with
restored rollover/workspace packets and the selected local launcher contract.
Feature 001/main remain clean; concurrent #121 work now includes dirty/untracked
feature 005 and its full legacy authority decision. Both #61 and #146 remain
included through main. Open PRs are now #97 and #121. Continued feature branches and the two
remote-only preservation refs still require preservation/review receipts;
repository adoption does not implement or activate the feature 001 launch stack.
The [protocol review](../../../specs/004-migrate-to-triad/protocol-review.md)
records the adopted manual instructions and the working-draft source snapshots.
