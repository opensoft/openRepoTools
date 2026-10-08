# Adopter fix and disposable rehearsal — October 6, 2026

**Task:** T005, with additional T003/T004 rehearsal evidence.
**Upstream candidate:** [openRepoShape PR #162](https://github.com/opensoft/openRepoShape/pull/162),
draft, commit `91d568563f98ddbe159167d82652d8e85214bb93`, based on
`39d5c986fcfac1a160474bfe91c5f1c37fccc72c`.
**Consumer rehearsal source:** `f5444c5e1f3c6c9ed43aeafcc000b0e78b10497a`.

The [October 4 refusal](adopter-blocker.md) is reproduced by a new regression
on the unchanged upstream revision. The candidate creates and stages a fresh
assembly `.gitmodules` after extraction only when that file is absent. It
preserves registrations retained in assembly. Original registrations remain
with their dependency gitlinks in the extracted leg. Verification is unchanged.

## Regression evidence

Ran inside py-bench with the existing private git-filter-repo 2.47.0 venv:

```sh
python3 -m pytest tests/test_adopt_*.py -q
```

Result: **90 passed, 1 skipped**. A final run of
`tests/test_adopt_submodules.py` after adding explicit gitlink-mode and
bootstrap assertions passed all **4** cases. Those cases cover:

- A populated dependency moved with its original `.gitmodules` into either
  code or spec: registration blob, gitlink mode/identity, dependency bytes and
  registration history survive; recursive clone, validators and bootstrap pass.
- A retained assembly registration survives mounting alongside a moved
  dependency. This exercises the mount boundary; it does not qualify every
  mixed-registration plan for complete adoption.
- A mount failure after the first new leg leaves the original source refs,
  registration bytes and worktree intact; mounting from a fresh clone succeeds.

Existing adopter coverage includes sources without submodules. No full
consumer suite or upstream CI pass is claimed by these local runs.

## Current-main local rehearsal

Private receipt ID: `adopter-fix-20261006-c2G9Dp`. Clone paths, local remote
URLs, commands and complete logs stay host-local outside the repository.

Generated a new plan from a clean, single-branch isolated source clone.
Reapplied the previous reasoned ownership overrides; explicitly assigned the
new `lanes-index` executable to code. The new `ideation/` content is spec.
The only existing dependency contract remains with code's registration/gitlink.
All ownership questions were resolved before `check` and execution.
This private plan is preliminary rehearsal input, not the final cutover plan.

`check` and `execute --local-remote-dir … --yes` both passed with the candidate.
Git transport was restricted to local files. The two leg remotes, assembly and
adoption branch exist only in the disposable rehearsal; no real leg repository
was created. The source remained clean on its original main commit.

| Source accounting | Original entries |
| --- | ---: |
| Spec | 45 |
| Code | 43 |
| Assembly root | 6 |
| Dropped | 0 |
| Total | 94 |

The standard reported every source path in exactly one place and 18 added
assembly paths. An independent comparison also checked **path, mode, object
type and object ID** for every original entry: zero missing or duplicate
owners. This includes the existing dependency gitlink.

| Disposable repository | Commit | Kept commits |
| --- | --- | ---: |
| Spec | `2374d2ec8f8f448c3d086b4546920f875c392ca6` | 29 |
| Code | `af25d6d9094285aa2f1d540c839518e6610adf89` | 81 |
| Assembly split | `52f0c18f239b3fbda1c0656e2aefd9c387164d26` | — |

Recursive clone and the generated `scripts/bootstrap.py` passed, including
naming, manifest and exact leg/copy pin validation. Assembly and legs were
clean afterwards. Code's nested openRepoShape remained at
`39d5c986fcfac1a160474bfe91c5f1c37fccc72c`; the recomputed tree digest is
`a44c0165beb9d3b6ddfce46925bf04b8d19934d5327b5a304b5f3f11af699b02`,
matching the original dependency contract. Live consumer main, its gitlink and
that contract were unchanged.

Private log SHA256s:

- Execute: `0e25dbec207e34694321c604201fb0437d70cbb0e4aba8314d34fbeae11636b3`.
- Bootstrap: `d83e3ca6b76e13bb6f4ec7d99ee64ea159634079d87015c3cc10b5699f042b9a`.

## Remaining delivery gates

T005 remains open: review and land the upstream fix, then use a commit on
upstream main for the tested consumer pin/gitlink update and recomputed digest.
The existing consumer pin has not been changed to the candidate branch.

PRs #97 and #121 have landed. On October 6 the remaining open consumer PRs
were #168, #169, #174 and draft #172. Refresh the final source mapping,
inventory and coordinated preservation after their landings and any other
baseline changes. The October 4 committed adoption plan and preservation
snapshot remain historical inputs.

Installer adaptations, composed code/spec tests and CI, rollback receipts,
owner dispositions and explicit execution approval remain required. Gates
A/B/C are not completed by this rehearsal. This evidence authorizes no real
conversion, merge, account move or lane rebinding.
