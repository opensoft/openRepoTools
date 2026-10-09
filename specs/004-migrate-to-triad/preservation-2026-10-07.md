# Gate A refresh: inventory and preservation, October 7

**Observation:** 2026-10-07. Inventory stamp 10:09:03Z; capture 10:05:59Z–10:06:08Z.
This is evidence for [T001–T002](tasks.md) on tracking issue opensoft/openRepoTools#186;
it does not complete them, and Gate A stays open. The
[October 4 receipt](preparation.md) remains historical evidence; the refreshed
[inventory](inventory.json) keeps the October 3 cleanup and the October 4 snapshot as history.

## Breakpoint

The coordinator's register facts at 09:5xZ: zero open PRs; lanes openRepoTools-1/2/3 idle with
no writers except this migration's; main `c4864ac5e59db49d01f638a80ed38daf1d788182` installed on
Eagle. This capture is a snapshot of that breakpoint while the migration's own writers were
starting, not an owner-coordinated freeze. Between 09:57Z and 10:03Z the migration's writers
added five worktrees (lane 1's pin, evidence and rehearsal trees; one tree each under lanes 2
and 3), and PR #187 (`004-migrate-to-triad` at `ff6f6a7`) opened at 10:03:43Z. Every worktree's
HEAD and `status --porcelain --ignored`, the worktree list and the ref listing were identical
before and after the capture, and refs were unchanged across bundle creation. After the
capture, the pin commit reached origin and PR #188 opened at 10:10:43Z.

## Inventory (T001)

Source main `c4864ac5e59db49d01f638a80ed38daf1d788182` equals GitHub main (PR #175's squash).
Seventeen worktrees as of the stamp: main plus 16 linked; the brief's expectation of 12 predates
the five migration trees. 19 local branches, 33 refs under `refs/`; origin has 10 heads and no
tags. No worktree is locked, prunable or detached. Eighteen PRs merged from October 3 to the
stamp; one PR (#187) was open at the stamp. The submodule gitlink is
`39d5c986fcfac1a160474bfe91c5f1c37fccc72c`, initialized in the main checkout.

Classes: 8 retained work (the source baseline, feature 001, the 004 plan and five migration
writer trees), 6 landed and preserved (trees and refs at the heads of merged PRs #121, #134,
#169, #174, #175 and #179), 3 empty shells (at main's #168 squash, no commits of their own).
Remote-only refs: `chore/preserve-local-planning-20261003`, `takeover/ort-a9-dirty-snapshot-20260913`
and `fix/install-by-rename-167` (PR #172's head). Local-only refs: `refs/lanes/a9-move` and two
stale `refs/remotes/pr/*`, all of merged history. Dispositions are proposals; owner decisions
are pending in the private receipt.

`status openRepoTools` (read-only, no fetch) still refuses: "no estate named 'openRepoTools'
under your projects directory", exit 2. `resume` was not run.

## Preservation evidence (T002)

Private backup ID: `prep-20261007T100559Z`, host-local on Eagle under the private prep
directory (`.openrepotools-private-prep/prep-<UTC stamp>/`) beside `prep-20261004T211123Z`.
File lists, ref listings, manifests and logs are in the private WIP repository's receipt.
No backup contents are published here.

- Source bundle (`git bundle create --all`): all 33 refs, `HEAD` and 16 per-worktree
  `HEAD`s; every ref present with the same SHA. SHA256:
  `60db3acd0753b3efde1ee6ae48d2c463e10fee57dbadcf8af543f12332c39c03`.
- Dependency bundle: the pinned standard `39d5c986fcfac1a160474bfe91c5f1c37fccc72c` and the
  migration's target `7f84ca42ca86a8902928345109d2bf6bad87bd91` (current openRepoShape main),
  from a fresh scratch clone. SHA256:
  `aa5a6eca83897516331466c2904ec786be3cf423cac3d6647aad5760bfb8d7cb`. The standard's own
  `tree_digest` gives `a44c0165beb9d3b6ddfce46925bf04b8d19934d5327b5a304b5f3f11af699b02`
  for the pin (matching the contract) and
  `3be52767e727d924dd05f9e78b18eb70f1682fe48614fab519f85331eeff5fa8` for the target.
- Manifest: 414 files, `sha256sum -c` passes; manifest SHA256
  `2a46dff9c00b0eba300bd0ad49a5cf42578f741b1e4a3cca2568d9c2784e88ed`.
- Worktrees: for all 17, HEAD, porcelain status with ignored entries, index entries, and full
  untracked and ignored lists. 141 ignored workflow-configuration entries were copied (main 71,
  feature 001 70); caches were listed but not copied; no path had a secret-like name.
  Repository-local config and excludes were preserved separately.
- Installed files: 29 receipt rows (install stamp 2026-10-07T04:26:26Z); 29 present, 0 missing,
  29 copies verified, 29 SHA256s match the install receipt.

| Worktree | Owner | Branch | HEAD | Dirty | Untracked | Ignored | Class |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| main | shared main checkout | `main` | `c4864ac5e59db49d01f638a80ed38daf1d788182` | 0 | 0 | 5 | retained-work |
| ort-179-tests | lane openRepoTools-1 | `feat/lane-worktrees-residue-tests` | `6c79121ea0288ac495ea5d0cd856083059c631bb` | 0 | 0 | 0 | landed-and-preserved |
| ort-install-followups | lane openRepoTools-1 | `fix/install-marker-on-every-file-and-one-install-lock` | `2080f3d83520bd1ea5632e754026f8ba3df4eb1f` | 0 | 0 | 0 | empty-shell |
| ort-shape-pin | lane openRepoTools-1 | `chore/openreposhape-pin-7f84ca4` | `e43b2432976a22eb3bf8c419c96209399251d375` | 0 | 0 | 0 | retained-work |
| ort-triad-exec | lane openRepoTools-1 | `004-migrate-to-triad-exec` | `ff6f6a7c7b7921ca1e0b0234e898900f98532366` | 0 | 0 | 0 | retained-work |
| ort-triad-rehearsal | lane openRepoTools-1 | `004-migrate-to-triad-rehearsal` | `ff6f6a7c7b7921ca1e0b0234e898900f98532366` | 0 | 0 | 0 | retained-work |
| ort-wip-init-followups | lane openRepoTools-1 | `fix/wip-init-step7-guarded-writes-and-step8-refusal-words` | `2080f3d83520bd1ea5632e754026f8ba3df4eb1f` | 0 | 0 | 0 | empty-shell |
| triad-reads | lane openRepoTools-2 | `004-migrate-to-triad-reads` | `ff6f6a7c7b7921ca1e0b0234e898900f98532366` | 0 | 0 | 0 | retained-work |
| triad-lane-tooling | lane openRepoTools-3 | `feat/triad-lane-tooling` | `c4864ac5e59db49d01f638a80ed38daf1d788182` | 0 | 0 | 0 | retained-work |
| 001-separate-swap-ctx-handoff | Brett Heap | `001-separate-swap-ctx-handoff` | `3c26041a4444a10bc240cb64a168ece4d9edf6c5` | 0 | 0 | 4 | retained-work |
| 004-migrate-to-triad | Brett Heap | `004-migrate-to-triad` | `ff6f6a7c7b7921ca1e0b0234e898900f98532366` | 0 | 0 | 0 | retained-work |
| 005-supervised-legacy-ctx | Brett Heap | `feat/supervised-context-restart` | `f13d32975d7457d662249385d23ee28a7f713c4c` | 0 | 0 | 3 | landed-and-preserved |
| feat-claude-current | Brett Heap | `feat/claude-current` | `11037f01a45a72fa3fc9a8a2b0e24a64cbf1ed12` | 0 | 0 | 2 | landed-and-preserved |
| a22-primary | lane openRepoTools-3 | `feat/amendment-22-sql-primary` | `2080f3d83520bd1ea5632e754026f8ba3df4eb1f` | 0 | 0 | 0 | empty-shell |
| closeout-2 | lane openRepoTools-3 | `feat/lane-end-closeout-rest` | `ed3655184d90e1ac21848aa4c3e294327b9561b6` | 0 | 0 | 0 | landed-and-preserved |
| suite-speed | lane openRepoTools-3 | `feat/shell-suite-wall-time` | `d2f80512902bf85b5993134a3cef6913d131565a` | 0 | 0 | 0 | landed-and-preserved |
| sweep-170 | lane openRepoTools-1 | `feat/lane-worktrees-residue` | `4ea84c8c8206347cef3cc5a626e79aee9e12b8c3` | 0 | 0 | 1 | landed-and-preserved |

## Restore rehearsal

97 checks passed, 0 failed, repeated from the backup's final location:

- A working clone and an independent mirror restored from the source bundle each list the same
  33 refs with the same SHA as the live listing at bundle time; `git fsck --full` is clean.
- The 2902 object IDs reachable from the 50 bundled tips are identical live and restored
  (sorted-list SHA256 `338cb7bdd397076eeced1de0852eeb1510b4f97e02fb3f62de434531c7be327d`).
- For each of the 17 worktrees, the HEAD commit resolves, its tree ID is unchanged, every
  index object exists, a worktree checked out from the restore has a byte-identical index, and
  after copying the captured configuration back, its tracked status and untracked and ignored
  lists match the capture (less the caches that were not copied).
- Both dependency commits resolve from the dependency bundle, and their tree digests,
  recomputed with each commit's own helper, match the values above.

The previous private backup `prep-20261004T211123Z` is still present (25 top-level entries,
including its `git-filter-repo` 2.47.0 wheel and venv, whose `--version` prints `a40bce548d2c`).
It was recorded read-only.

## What remains for Gate A

Owner dispositions for every retained object, and a final capture at an owner-coordinated freeze
after the migration's own writers stop. Installed-file receipts are still needed for py-bench and
any other profile or workstation. This backup is local to this workstation. No execution task is
checked complete by this evidence.
