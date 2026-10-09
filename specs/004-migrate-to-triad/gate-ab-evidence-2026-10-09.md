# Gate A/B evidence, the restore and rollback rehearsal, and the follow-up inventory — October 9, 2026

**Task:** T011 of [tasks.md](tasks.md), under [#186](https://github.com/opensoft/openRepoTools/issues/186).
No task is checked complete by this record.
**Writer:** lane openRepoTools-1, 2026-10-09.
**Evidence branch:** `004-migrate-to-triad-rollback` (from main `837928a`).
**Private receipt ID:** `rollback-20261009-ILvoVC` (brett-wip `migration/openRepoTools/`).

This first commit records step 1 (the source restore). Steps 2 to 4 follow in the
next commits on this branch; until they are here, this document is incomplete.

## 1. Restore rehearsal of the source

From the Gate A backup `prep-20261007T100559Z` (host-local, read-only), following its
`RESTORE.md` commands with only the placeholder paths replaced by private scratch.
**90 checks passed, 0 failed.**

- The manifest (414 entries) passes `sha256sum -c`.
- `RESTORE.md`'s `git bundle verify`, run from the backup directory as written, exits **1**:
  `error: need a repository to verify a bundle`. Run inside the restored clone it exits 0.
  A defect in `RESTORE.md`'s text, recorded here; the backup is read-only and was not edited.
- The `--mirror` restore and the working clone (`clone`, then `fetch --update-head-ok
  --prune '+refs/*:refs/*'`) each list the same 33 refs with the same SHA as the live
  `for-each-ref` at bundle time. `git fsck --full` prints nothing and exits 0 for both.
- The 2902 objects reachable from the 50 bundled tips are identical
  (sorted-list SHA256 `338cb7bdd397076eeced1de0852eeb1510b4f97e02fb3f62de434531c7be327d`).
- Against the live repository **today**, two days on: of the 33 captured refs, 26 are
  identical, 7 moved **forward only** (`main`, `origin/main`, `origin/HEAD` to `837928a`;
  the three October 7 evidence branches and lane 3's `feat/triad-lane-tooling`), 0 were
  deleted and **0 moved by anything but a fast-forward**. 18 refs were added since.
- All 17 captured worktree HEADs resolve in the restore, each tree ID equals the live one,
  every index object is present, and the index a checkout of each HEAD makes equals the
  captured `index.ls-files-s` byte for byte (17 of 17).
- One tree by `RESTORE.md`'s own procedure, `main` (the capture with workflow files):
  `worktree add --detach`, the captured files copied back, the captured exclude file
  restored. Its index (100 entries) equals the capture, all 70 copied files match
  `files.sha256`, and its tracked status, untracked and ignored lists equal the capture's,
  less the 4 cache entries the capture lists as not copied.
- Both dependency commits resolve from the dependency bundle, and each one's own
  `tree_digest` gives the recorded value (`39d5c98` → `a44c0165…`, `7f84ca4` → `3be52767…`).

### A worktree captured dirty

The 17 Gate A captures were all clean, so the dirty case was rehearsed on a disposable
stand-in: a clone of the Gate A bundle given every kind of change (an unstaged edit, a
staged edit, a staged new file, a partly staged file, an unstaged and a staged deletion,
a mode change, an untracked note, ignored workflow configuration and an ignored cache).
Each capture was bundled and rebuilt into a fresh clone that held only the bundle's
objects, as a real restore would.

| Capture | Index equal | Status equal | Every file equal (100) |
| --- | --- | --- | --- |
| A: the per-worktree block of the backup's own `capture.sh`, verbatim | **no** — 3 staged blobs are in no bundle | **no** | **no** |
| B: A plus `git diff --cached --binary`, `git diff --binary` and every untracked file | yes | yes | yes |

**Finding for Gate A.** The October 7 capture takes a tree's index *listing*, its ignored
workflow configuration and nothing else of its working state. That was sufficient only
because all 17 trees were clean. The final capture at the owner-coordinated freeze must
take B's three extra artifacts for any tree that is not clean, or refuse to call that tree
captured. B's rebuild is `worktree add --detach <HEAD>`, `git apply --index staged.patch`,
`git apply unstaged.patch`, the untracked archive, then the workflow files.
