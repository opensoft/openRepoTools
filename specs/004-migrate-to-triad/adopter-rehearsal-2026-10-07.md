# Gate B rehearsal with the merged adopter fix — October 7, 2026

**Task:** T003–T005 rehearsal evidence under [#186](https://github.com/opensoft/openRepoTools/issues/186).
No task is checked complete by it.
**Tool:** openRepoShape `7f84ca42ca86a8902928345109d2bf6bad87bd91`, the merged
[PR #162](https://github.com/opensoft/openRepoShape/pull/162) adopter fix on its
`main` (`compare main...7f84ca4`: `identical` at measurement).
**Rehearsal sources:** run A, main `c4864ac5e59db49d01f638a80ed38daf1d788182`;
run B, the repin candidate `chore/openreposhape-pin-7f84ca4`
([#188](https://github.com/opensoft/openRepoTools/pull/188)) at
`e43b2432976a22eb3bf8c419c96209399251d375`, whose only change from `c4864ac`
is the `upstream/openRepoShape` gitlink and its contract, both now at `7f84ca4`.
**Private receipt ID:** `adopter-fix-20261007-iM20tv`.

The [October 6 rehearsal](adopter-rehearsal.md) ran the draft candidate
`91d5685`. This run uses the fix as merged, which is the repeat
[adopter-blocker.md](adopter-blocker.md) asks for after repinning. It uses fresh isolated clones
and fresh disposable local remotes. Clone paths, local remote URLs, exact command lines
and complete logs stay in the private receipt.

## Setup

- `git-filter-repo` 2.47.0 in a private venv for this rehearsal only. The
  `pip download` wheel SHA256 is
  `2cd04929b9024e83e65db571cbe36aec65ead0cb5f9ec5abe42158654af5ad83`, matching
  the value recorded in [preparation.md](preparation.md).
  `git filter-repo --version` printed `a40bce548d2c`.
- The tool is a fresh clone of openRepoShape checked out at `7f84ca4`. Nothing
  in it was edited. The first `plan` run left an ignored `scripts/__pycache__/`,
  which was removed; bytecode writing stayed off after that. The clone was
  clean, ignored files included, after both runs.
- Each source is a fresh `--single-branch` clone with one worktree and no
  linked worktrees. The source's nested `upstream/openRepoShape` was **not**
  initialized: the tool's adoption documentation does not ask for it, and
  `plan`, `check` and `execute` read the source through `ls-tree` and
  non-recursive clones.
- Git transport was restricted to local files (`GIT_ALLOW_PROTOCOL=file`);
  `gh` and `curl` shims first on `PATH` logged and refused every call. No
  call was logged during `plan`, `check`, `execute`, the recursive clone or
  bootstrap. The recursive clone reached code's nested openRepoShape through a
  local URL rewrite to a bare mirror of the tool clone.
- Read-only lookups of `opensoft/openRepoTools-spec` and `-code` returned
  HTTP 404: not visible to the current credentials, which is not a guarantee
  of name availability or creation permission. Recheck at Gate C.

## Mapping (T003)

`plan` ran against each source with the committed plan's recorded election
values (`--org opensoft --visibility public --elected-by "Brett Heap"
--elected-on 2026-10-04`). It left 18 paths unresolved: `.gitmodules`,
`upstream/`, `repos.tsv` and fifteen executables. All 19 reasoned overrides of
the [October 4 mapping](../../openspec/changes/migrate-to-triad/adoption-plan.yaml)
were reapplied with their resolution text unchanged. Sixteen answer those
questions; three override the tool: `commands/` and `skills/` (installed
Markdown payloads) and `contracts/` (only the dependency lock) go to code.

Paths new since the October 4 source `daed209` (36 files) and the October 6
source `f5444c5` (6 files) were resolved by the same rules:

| New path | New since | Leg | Reason |
| --- | --- | --- | --- |
| `lane-worktrees` | `f5444c5` | code | Executable lane command in the installer's `INSTALLABLES`; the committed executable resolution text. |
| `lanes-index` | `daed209` | code | Same, as the October 6 rehearsal assigned it. |
| `ideation/` (12 files) | `daed209` | spec | The tool already says spec; a resolution line records the review. |
| 11 files under `openspec/changes/` | `daed209` | spec | Covered by `openspec/`. |
| 4 files under `specs/005-supervised-legacy-ctx/` | `daed209` | spec | Covered by `specs/`. |
| 7 test files under `tests/` (5 since `f5444c5`) | `daed209` | code | Covered by `tests/`. |

No bounded `features/<NNN>/openspec/` amendment paths exist, so none are
recorded. Nothing is dropped. The follow-ups are the tool's own
`follow_ups_for()` re-derived over the resolved entries (19), then the October
4 plan's ten reasoned follow-ups. One stale count in them changed: "64-file"
became the current source's file count. `check` printed `plan ok` and exited
0 for both runs.

## Run A — current main `c4864ac`

`execute --local-remote-dir … --work-dir … --yes` exited **0** and printed
`adoption verified: every source path is in exactly one place`.

| Source accounting (the standard's table) | Original entries |
| --- | ---: |
| Spec | 45 |
| Code | 49 |
| Assembly root | 6 |
| Dropped | 0 |
| Total | 100 |

The standard reported 18 added assembly paths: `project.yaml`, `Makefile`,
`AGENTS-shape.md`, `.github/workflows/validate.yml`, four `contracts/`
files (`code-pin.yaml`, `spec-pin.yaml`, `shape-pin.yaml`,
`repository-naming.yaml`), five `scripts/` files and five collision copies
under `shape/` (`.gitattributes`, `.gitignore`, `AGENTS.md`, `CLAUDE.md`,
`README.md`). The assembly also holds the two leg gitlinks and a fresh
`.gitmodules`, which its table does not count as added.

An independent comparison matched **path, mode, object type and object ID**
for all 100 entries of `ls-tree -r c4864ac`: 45 spec, 49 code, 6 root, with
zero missing owners, zero duplicate owners and zero owners that differ from
the plan's leg. Neither leg holds an entry that is not in the source. The
`160000` gitlink `upstream/openRepoShape` at `39d5c98` has exactly one owner,
code. The original `.gitmodules` blob is in code; the assembly's new one is
a different blob.

| Disposable repository | Commit | Kept commits |
| --- | --- | ---: |
| Spec | `558a12b674008bc9129e4f5438cdff42053963da` | 34 |
| Code | `48d98cd8793493646adb71163eac15b56fffee9c` | 87 |
| Assembly split | `9e5f934e98122c5da37428b064e044e807c9680e` | — |

The split commit's only parent is `c4864ac`. A recursive clone of the split
branch passed. The generated `scripts/bootstrap.py` exited 0 (`bootstrap ok`),
and its naming, manifest and pins checks passed. The three validators also
passed when run on their own. The assembly, both legs and the nested
dependency were clean afterwards. Code's nested openRepoShape was checked out
at `39d5c986fcfac1a160474bfe91c5f1c37fccc72c`, matching code's
`contracts/openreposhape-pin.yaml`. That checkout's own `scripts/repo_shape.py`
recomputed the tree digest as
`a44c0165beb9d3b6ddfce46925bf04b8d19934d5327b5a304b5f3f11af699b02`, which
matches the contract.

The source clone's `HEAD`, `status --porcelain --ignored`, existing refs, local
configuration and worktree list were unchanged. Local mode added one ref, as
documented: `refs/heads/adopt/three-repo-shape`, which points at the split
commit. The live checkout gained no `adopt/` ref.

## Run B — the repin candidate `e43b243`

`plan` produced the same 18 open questions. The resolved mapping is the same
as run A's, with the same 22 decisions and follow-ups and the same
45/49/6 split. It differs only in the source fields: commit, `commits: 91`,
and `default_branch: chore/openreposhape-pin-7f84ca4`. A single-branch clone
of that branch has no `origin/HEAD`, so the tool takes the checked-out branch
as the default. `check` passed. `execute` exited **0** and printed
`adoption verified: every source path is in exactly one place`.

| Source accounting (the standard's table) | Original entries |
| --- | ---: |
| Spec | 45 |
| Code | 49 |
| Assembly root | 6 |
| Dropped | 0 |
| Total | 100 |

The standard again reported 18 added assembly paths, the same set as in
run A. The independent path/mode/type/object comparison of all 100 entries
of `ls-tree -r e43b243` found 45 spec, 49 code and 6 root owners. It found
zero missing, duplicate or misplaced owners and no leg extras. The gitlink
`upstream/openRepoShape` at `7f84ca4` has exactly one owner, code.

| Disposable repository | Commit | Kept commits |
| --- | --- | ---: |
| Spec | `558a12b674008bc9129e4f5438cdff42053963da` | 34 |
| Code | `6d5216292186b5b2d2e4daa08afa3dd4580db80f` | 88 |
| Assembly split | `2726d3a935369c18472623b904c21ca3a825d09b` | — |

The spec leg is the same commit as in run A, because its paths and their
history did not change. Code has one more kept commit: the repin. The split
commit's only parent is `e43b243`. The recursive clone,
`scripts/bootstrap.py` (`bootstrap ok`) and the three validators all passed.
Every tree was clean afterwards. Code's nested openRepoShape was checked out
at `7f84ca42ca86a8902928345109d2bf6bad87bd91`, matching code's
`contracts/openreposhape-pin.yaml`. The pinned checkout's own
`scripts/repo_shape.py` recomputed
`3be52767e727d924dd05f9e78b18eb70f1682fe48614fab519f85331eeff5fa8`, which
matches the contract. Code still holds the source's original `.gitmodules`
blob, `8043147a`. The source clone was unchanged except for the one new ref
`refs/heads/adopt/three-repo-shape` at the split commit.

## Notes for review

- The regenerated follow-ups list nine code files that name `docs/`. The
  ninth, shown as "… and 1 more", is `tests/test_repo_hygiene.py`. Three code
  files name `openspec/`: `lane-handoff` is new since the October 4 list, at a
  `:2439` comment that cites the supervised-restart design. One file names
  `specs/`. Neither `lane-worktrees` nor `lane-end` names a spec-leg
  directory, so neither needs a follow-up.
- On this branch, the
  [mapping](../../openspec/changes/migrate-to-triad/adoption-plan.yaml) is
  the regenerated run B plan, with a header saying what it is. The October 4
  version is unchanged in history at `ff6f6a7`. [plan.md](plan.md),
  [quickstart.md](quickstart.md) and [preparation.md](preparation.md) still
  describe the October 4 version; the plan's owner decides when to refresh
  them.
- *Dated 2026-10-09 (#193 item 8):* since #192, the mapping link above opens
  run C's plan ([adopter-rehearsal-2026-10-08.md](adopter-rehearsal-2026-10-08.md)),
  and run B's stays in history at `63810dd`. #188 landed as `837928a`. The
  bench restart of 2026-10-08 cleared both runs' disposable repositories, so
  this file's receipt holds their only record.
- Each run used a fresh, empty `--local-remote-dir` and `--work-dir`. Without
  the first, `execute` calls `gh repo create`. The plan's
  `execution_authorized: false` is informational and the tool does not read it.
- The published plan differs from the executed run B plan in only three ways:
  the header, `local_path: .` instead of the scratch path, and the October 4
  file's two closing status fields. `check` against the published copy also
  passed.

## Private log SHA256s

- Run A execute: `885fa0d0f8b00513536683bafcf355ca15e2d26c34908935675c5898361f73a0`.
- Run A bootstrap: `e5d06e2e406d1b6ddae1dceb0b17004ce615c3d044cee4cb36828abdf27949fc`.
- Run A independent comparison: `9ae2fa322360b705761a9ca628a265c610cd7dceaaf29fc369fb1576cc84c5de`.
- Run B execute: `e894b78e1ca4b4ba8a95b2b5d2be428fa30d4a75b894ce48d90a550b0de78839`.
- Run B bootstrap: `6a010feb6a56b190690a097af396a94f29802ef125bf6c544afe0f807c557c0f`.
- Run B independent comparison: `fe933dd169375fb62a09967efb89fcac014d0c8d96868f0d007d0c1ed060a46b`.

The receipt holds every log with its SHA256. None was over 2 MB, so none was
trimmed.

## Remaining gates

**Gate B is not complete.** This evidence covers the extraction, accounting,
nested-pin and bootstrap parts of T003–T005 for both sources. T005's pin
bump is PR #188, which still follows the usual landing rules. T006–T011
remain open:

- root collisions and leg guidance;
- the installer entry point;
- composed tests and CI;
- the restore and rollback rehearsal.

Gate A preservation must be refreshed at a coordinated breakpoint. Before
Gate C, regenerate the plan from the frozen source that is actually chosen.
Brett Heap's explicit Gate C approval must name the revisions, the leg
repositories, their visibility and the final plan.

This evidence authorizes no real conversion, repository creation, merge,
default-branch move or lane rebinding.
