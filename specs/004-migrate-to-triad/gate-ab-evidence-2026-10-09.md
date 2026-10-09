# Gate A/B evidence, the restore and rollback rehearsal, and the follow-up inventory — October 9, 2026

**Task:** T011 of [tasks.md](tasks.md), under [#186](https://github.com/opensoft/openRepoTools/issues/186).
No task is checked complete by this record, and it approves nothing.
**Writer:** lane openRepoTools-1, 2026-10-09T00:36Z–01:1xZ.
**Refreshed:** lane openRepoTools-2, 2026-10-09T18:51Z–20:4xZ, on branch
`004-migrate-to-triad-rollback-refresh` (from `fa44d75`). It answers lane 3's review of
`fa44d75` (#186 comment 6082139424, whose findings are cited here as F1–F22) and folds in
lane 2's verification of the receipt (#186 comment 6082370012). Each refreshed passage
starts with "Refreshed" or "Corrected"; the 01:1xZ text it qualifies stays as written
unless a finding showed it wrong. Origin was read at 2026-10-09T20:29:34Z–20:30:29Z, with
main at `f87fd5a`, and again before the push (section 8).
**Evidence branch:** `004-migrate-to-triad-rollback` (from main `837928a`).
**Private receipt ID:** `rollback-20261009-ILvoVC` (brett-wip `migration/openRepoTools/`),
holding every script, log, snapshot and digest named below. Machine paths stay there. It
has two commits (F17):
- `56f1e7c4` (00:59:32Z): 424 files, 423 of them listed in one `SHA256SUMS`;
- `076062af` (01:14:30Z): 18 more files, the final real-surface snapshot (`state/final/`,
  01:13:46Z; section 3) and the two hygiene logs (section 8), with `README.md` and
  `SHA256SUMS` updated: 442 files, 441 listed.

Refreshed: brett-wip `ea6c09d1` holds the receipt exactly as `076062af` left it, and
`sha256sum -c SHA256SUMS` gives 441 OK.

T011 asks for three things. First, a rehearsal of restoring the local candidate and the
installed payload from the preserved artifacts. Second, proof that user work, jobs and claims
survive with no force push, no destructive reset and no workspace-pointer rewrite. Third,
publication of the Gate A/B evidence with the follow-up patch and commit inventory.
Sections 1–3 are the rehearsals, measured today. Sections 4–6 are the index and the
inventory. Section 7 is what Gate B still lacks.

**Short answer.**
- **Source restore:** passes, 90 checks of 90.
- **Installed payload:** the 29 placed files restore to the main install exactly by either
  path; only the reinstall (c2) also restores the receipt. Refreshed (F13): the target is
  main's install, not the home before any install, because the first install rewrites
  `settings.json` at mode 600 and both rollbacks keep that.
- **Hooks and settings: not rehearsed** (F11). No stage changed a hook entry or
  `settings.json`, so section 2's hook rows test nothing about hooks, and the Gate A
  backup holds no `settings.json` for `RESTORE.md`'s copy-back to restore.
- **What the rehearsals wrote:** only private scratch. Nothing in a real repository, the
  real home or the register.
- **Gate B is still open.** Section 7 lists what is missing.

## 1. Restore rehearsal of the source

The source is the Gate A backup `prep-20261007T100559Z` (host-local, read-only). The
rehearsal followed its `RESTORE.md` commands, with only the placeholder paths replaced by
private scratch. **90 checks passed, 0 failed.**

Refreshed (F5): how the 90 add up, from receipt `logs/10-restore.log`.
- 22 single checks: the manifest 1; `RESTORE.md`'s mirror clone, working clone, fetch and
  `set-url` 4; `bundle verify` inside the clone 1; refs 3 (each restore against the
  capture, and the capture against the shared checkout today); `fsck` 2; the object set 1;
  `RESTORE.md`'s worktree procedure on `main` 6; the dependency bundle 4.
- 68 tree checks: 4 for each of the 17 captured trees.

The 97 of #189 (`preservation-2026-10-07.md:89`; receipt `prep-20261007T100559Z`,
`verify.log`) were 12 single checks plus 5 for each tree (85).
- This run did not repeat 18 of them: the status-and-lists comparison for the 16 trees
  other than `main` (October 7 made it for all 17, `preservation-2026-10-07.md:95–98`;
  this run made it for `main` only, below), the bundle's `HEAD` against the main
  checkout's, and the bundle's 16 per-worktree `HEAD` refs.
- It added 11: the manifest, the mirror clone, `set-url`, `bundle verify`, the capture
  against the shared checkout today, the second `fsck`, and five steps of the worktree
  procedure on `main`.
- 97 − 18 + 11 = 90.

- The manifest (414 entries) passes `sha256sum -c`. Refreshed (F4): it lists the two
  bundles restored here, source `60db3acd…` and dependency `aa5a6eca…`, which are the
  digests #189 published (`preservation-2026-10-07.md:49–50, 54`), and its own digest is
  #189's `2a46dff9…` (`:59`). So the bundle restored here is the one #189 recorded. Both
  bundle files still hash to those values (re-hashed 2026-10-09T20:35:05Z).
- **`RESTORE.md`'s `git bundle verify`, run from the backup directory as written, exits 1:**
  `error: need a repository to verify a bundle`. Run inside the restored clone, it exits 0.
  This is a defect in `RESTORE.md`'s text. It is recorded here; the backup is read-only and
  was not edited.
- The `--mirror` restore and the working clone each list the same 33 refs, with the same SHA
  each, as the live `for-each-ref` at bundle time. The working clone is a `clone`, then
  `fetch --update-head-ok --prune '+refs/*:refs/*'`. `git fsck --full` prints nothing and
  exits 0 for both.
- The 2902 objects reachable from the 50 bundled tips are identical. The sorted-list SHA256
  is `338cb7bdd397076eeced1de0852eeb1510b4f97e02fb3f62de434531c7be327d`.
- **Against the live repository today, two days on**, the 33 captured refs are as below.
  Corrected: "live" here is the shared checkout's own `for-each-ref`, read at 00:44:08Z
  (`10-restore.sh:58`, `logs/10-restore.log:1`), not GitHub. #189 had merged on GitHub as
  `63810dd` at 00:44:03Z, and that checkout's `main` still read `837928a`.
  - 26 identical;
  - 7 moved forward only: `main`, `origin/main` and `origin/HEAD` to `837928a`, the three
    October 7 evidence branches, and lane 3's `feat/triad-lane-tooling`;
  - 0 deleted;
  - **0 moved by anything other than a fast-forward**.

  18 refs were added since the capture.

  Refreshed 2026-10-09T20:29:34Z, against GitHub (`git ls-remote`; a local branch and its
  remote-tracking ref are read as the GitHub branch of that name, and `pr/N` as
  `refs/pull/N/head`): 15 identical, 9 moved forward only, 9 with no GitHub ref of that
  name, and **0 moved by anything other than a fast-forward**. Each of those 9 commits is
  still contained in a GitHub ref; for example `e43b243` is in `refs/pull/188/head`.
- **All 17 captured trees:**
  - each HEAD resolves in the restore;
  - each tree ID equals the live one;
  - every index object is present;
  - the index a checkout of each HEAD makes equals the captured `index.ls-files-s` byte
    for byte (17 of 17).

  Refreshed (F6): two of these four prove little on their own.
  - "Tree ID equals the live one" compares the tree of the same commit ID, read in the
    restore and in the shared checkout (`10-restore.sh:94–95`). A commit ID fixes its
    tree ID, and `fsck` already covers the objects.
  - All 17 captures were clean (`preservation-2026-10-07.md:69–85`, Dirty 0), so each
    captured index is its HEAD's tree. The byte-equal index proves that the objects are
    present, not that index state survives a restore. The dirty-tree stand-in below is
    the evidence on index state.
- **One tree by `RESTORE.md`'s own procedure**: `main`, the capture with workflow files.
  - The steps: `worktree add --detach`, copy the captured files back, restore the captured
    exclude file.
  - Its index (100 entries) equals the capture.
  - All 70 copied files match `files.sha256`. Refreshed (F7): these are the 70 regular
    files. With one symlink they are the 71 workflow entries #189 counts for `main`
    (`preservation-2026-10-07.md:61`; receipt `prep-20261007T100559Z`,
    `file-lists/main.classified.tsv`: 70 `workflow-copied-verified`, 1
    `workflow-copied-symlink-verified`), and `files.sha256` lists regular files only. 71
    ignored files are restored (`logs/10-restore.log:160`).
  - Its tracked status and its untracked and ignored lists equal the capture's, less the 4
    cache entries the capture lists as not copied. Corrected: those 4 are nested
    repositories (`nested-repository-not-copied` in the same file), not caches.
- Both dependency commits resolve from the dependency bundle. Each one's own `tree_digest`
  gives the recorded value: `39d5c98` → `a44c0165…`, `7f84ca4` → `3be52767…`.

### A worktree captured dirty

The 17 Gate A captures were all clean, so the dirty case was rehearsed on a disposable
stand-in: a clone of the Gate A bundle given every kind of change:
- an unstaged edit and a staged edit;
- a staged new file and a partly staged file;
- an unstaged deletion and a staged deletion;
- a mode change;
- an untracked note;
- ignored workflow configuration and an ignored cache.

Each capture was bundled and rebuilt into a fresh clone that held only the bundle's objects,
as a real restore would.

| Capture | Index equal | Status equal | Every file equal (100) |
| --- | --- | --- | --- |
| A: the per-worktree block of the backup's own `capture.sh`, verbatim (corrected below: a copy) | **no**: 3 staged blobs are in no bundle | **no** | **no** |
| B: A plus `git diff --cached --binary`, `git diff --binary` and every untracked file | yes | yes | yes |

Corrected (lane 2's verification, #186 comment 6082370012): the receipt's copy of that
block (`11-dirty.sh:42–66`) is not verbatim. Against the backup's `capture.sh:68–92` it
drops the info-exclude copy (`:75–77`) and the `skipped-secret-like.tsv` append (`:82`).
Lane 2 ran the backup's own block, verbatim, on the same stand-in: 0 of 3 again, with the
same 3 staged blobs in no bundle.

**Finding for Gate A.** The October 7 capture takes three things from a tree: its index
*listing*, its ignored workflow configuration, and its HEAD. It takes none of its working
state. That was enough only because all 17 trees were clean. For any tree that is not clean,
the final capture at the owner-coordinated freeze must take B's three extra artifacts, or
must refuse to call that tree captured. B's rebuild is:
1. `worktree add --detach <HEAD>`;
2. `git apply --index staged.patch`;
3. `git apply unstaged.patch`;
4. unpack the untracked archive;
5. copy back the workflow files.

## 2. Rollback rehearsal of the installed payload

All of it ran in disposable homes under private scratch, never the real home.
- Every `--install` ran under `env -i` with:
  - `HOME` and every `XDG_*` variable pointed into that home;
  - `TMPDIR` in scratch;
  - `PATH` = refusing `gh`/`curl`/`wget` shims, then `/usr/bin:/bin`;
  - `GIT_ALLOW_PROTOCOL=file`.
- **The shims logged 0 calls.**
- Each home was seeded with things an install must leave alone:
  - unrelated `settings.json` content: a model, an env, permissions, a status line, and
    unrelated `SessionStart`, `UserPromptSubmit` and `Stop` hooks;
  - a foreign command in `~/.local/bin`;
  - a foreign skill under each of the two skill roots.

| Stage | Source | Commit |
| --- | --- | --- |
| (a) today's main | a fresh clone of `origin/main` from GitHub, `./openRepoTools --install` | `63810dd` |
| (b) the rehearsed candidate | run C's assembly cloned recursively; installed from **`code/`**, the code leg's own `openRepoTools` | assembly `69b8924`, code `73b04d6` |
| (b″) a candidate whose payload differs | PR #191's head, a fresh clone | `ecd7aa4` |
| (c1) roll back by copy | `cp -a <backup>/installed/. "$HOME/"`, `RESTORE.md`'s command | the Gate A copies of the 2026-10-07T04:26:26Z install |
| (c2) roll back by reinstall | `./openRepoTools --install` from the source restored in section 1 | `c4864ac` |

Notes on the sources:
- **(a):** main moved during the run. #189 landed as `63810dd` at 00:44Z. It touched
  only `specs/` and `openspec/`, so its payload is byte-identical to `837928a`'s.
- **(b):** T007's assembly root entry point was **not** used. No
  `004-migrate-to-triad-installer` branch is on origin, so (b) installed through
  `code/openRepoTools`. Refreshed (F15): that branch has been on origin since 01:21:15Z,
  at `51993a4`, 7 min 40 s after this branch's last push (section 4).
- **(b″):** it is not the T007 candidate. It is used only because a rollback is shown best
  where the payload differs.

**The four homes:**
- H1: (a), (b), (c1).
- H2: (a), (b), (c2).
- H3: (a), (b″), (c1).
- H4: (a), (b″), (c2).

Every install exited 0, printed `17 of 17 placed` and wrote 29 receipt rows. The first in each
home merged the 2 hook entries; every later one printed `already installed … (unchanged)` for
both.

**Refreshed (F11): so no stage changed a hook, and the hook rollback is vacuous.**
- In all four homes the two hook entries and the canonical `settings.json` are identical at
  (a), at (b) or (b″), and at (c) (receipt `state/homes/H1`–`H4`, `hooks.ours` and
  `settings.canon`). Every candidate here writes the same two entries main writes.
- So the row "(c) the two hook entries: same" below shows that nothing moved, not that a
  moved hook comes back. Commit `849592b`'s subject, "both rollbacks return every placed
  file, mode and hook to main's install", holds for hooks only in that sense.
- (c1) cannot roll back a hook or a setting at all. The Gate A backup's `installed/` holds
  the 29 placed files and no `settings.json`; no file in the backup is a `settings.json`;
  and `RESTORE.md:45` copies back `installed/` only. The backup does hold the 29-row
  `installed.tsv` of 2026-10-07T04:26:26Z at its top level, which `RESTORE.md` does not
  copy back (F14; section 7, item 6).
- No candidate measured to date changes a hook or `settings.json`:
  - (b) and (b″) here;
  - PR #191 at `13cc752`: `settings.json` and both hook entries are byte-identical to
    main's install (lane 3's delta review 5471121210, finding 2);
  - the composed candidate at `935f53f`: `settings.json` is byte-identical (lane 3's
    review, #186 comment 6082068576, finding 4).

  A candidate that does change one would need this rollback rehearsed, by (c2), with a
  payload whose hook entry differs.

| Compared with (a) | H1 (b)→(c1) | H2 (b)→(c2) | H3 (b″)→(c1) | H4 (b″)→(c2) |
| --- | --- | --- | --- | --- |
| (b) placed files (path, mode, sha256) | same | same | **1 differs** | **1 differs** |
| (c) placed files (path, mode, sha256), 29 | same | same | same | same |
| (c) receipt rows (name, destination, sha256) | same | same | **1 stale row** | same |
| (c) the two hook entries (never changed; see above) | same | same | same | same |
| (c) `settings.json`, canonical; its mode | same; same | same; same | same; same | same; same |
| unrelated settings after every stage = the seed | yes | yes | yes | yes |
| foreign command and skills after every stage | untouched | untouched | untouched | untouched |
| (c) the set of paths under the home | same | same | same | same |

**Every difference, verbatim:**
- **(b″) vs (a), in H3 and H4.** `~/.local/bin/openRepoTools  755
  47cfe74ea96e6ce9e56b47220a71e1de8c608af2f51f33cfdffa351410a4f373` became
  `71e9ba2c9a06b755c79f3d01b52516ce0c1cfcc3a3c6a92b5fd200976b0787a4`, PR #191's installer.
  Both rollbacks put `47cfe74e…` back.
- **(c1) in H3: the copy-back leaves the receipt stale.** The receipt row
  `openRepoTools  ~/.local/bin/openRepoTools  71e9ba2c…` still names the replaced file. The
  file on disk is `47cfe74e…`. `RESTORE.md`'s copy-back restores the 29 files and not
  `installed.tsv`. A later `--install` that retires a file asks the receipt whether it wrote
  that file, and would get the wrong answer. **(c2) rewrites the receipt** and has no such
  row.
- **In every home, (c) vs (a), the whole-home comparison differs in one file only:**
  `installed.tsv`. That is its UTC stamp column, plus H3's stale row above. Examples:
  - H2: `145f4de8…` vs `09a03339…`;
  - H4: `74cfc104…` vs `9e8b2a59…`.
- **The first install changes `settings.json`'s mode from 644 to 600.** The installer prints
  that it writes the file back at mode 600. This is by design and is the same in (a) and (c).

**What this run cannot show.** The rehearsed candidate's payload is blob-identical to
main's: filter-repo keeps every blob. So (b)→(c) in H1/H2 rolls back no bytes, and only
checks the mechanism. Receipts, hooks, unrelated settings and foreign files hold through a
candidate install and a rollback. H3/H4 show a real byte rollback with PR #191's installer.
The real T014/T015 candidate, with #191 and the T007 entry point, must repeat (c2) at its
own exact commits.

Refreshed (F13): two more things it cannot show.
- **No stage adds or retires a placed file.** All 12 snapshots after the seed, in the four
  homes, place the same 29 paths (receipt `state/homes/*/*/placed.tsv`). So two hazards are
  argued here, not run: (c1) leaving behind a file a candidate added, and the stale receipt
  misleading a later `--install` that retires a file (above).
- **The rollback target is main's install, not the home before it.** The first install
  rewrites `settings.json` at mode 600, and neither rollback returns it to the seed's 644.

**Run 1, kept as evidence of all-or-none.** The first seed's unrelated `SessionStart`
command contained the word `session-start`. Every install refused it as a second writer of
that hook: 10 runs across main, the candidate, #191 and the restored source, exit 2,
`NOTHING was installed`. After each refusal, every file and `settings.json` was
byte-identical to the seed. The seed was then reworded and all four homes were rebuilt.

**The rollback targets match what Eagle runs today:**
- the real home's 29 installed files equal (a)'s placed files (path, mode, sha256), read-only;
- the Gate A backup's 29 copies carry the same 29 digests.

## 3. User work, jobs and claims survive

**Every command the rehearsals ran that writes anything** — 18 groups in the receipt's
`mutations.tsv` — wrote only into private scratch:
- **temp dir only: 18;**
- **real repository: 0;**
- **real home: 0;**
- **register: 0.**

The groups are:
- restore clones, the throwaway indexes, the `RESTORE.md` worktree and its copied files;
- the dirty stand-in and its two rebuilds;
- the install sources;
- the seeds;
- 10 installs and 10 refused ones. Corrected (F12): this said 12. The receipt's
  `README.md:35` and `mutations.tsv:15` say 12, but `logs/22-installs.log` has 10
  `--install` runs and the 2 copy-backs of the next line, 12 `exit=0` lines in all;
- two copy-backs, snapshots and comparisons;
- the patch-application clones.

**No script pushes, stashes, cleans, kills a process, deletes a branch, removes a worktree,
runs `checkout -f` or `update-ref`, or writes `workspace.yaml`** (`grep` over every script
in the receipt). The one `reset --hard` is in a scratch clone of the rehearsal that section 5
patched. The live repository was only read, with `GIT_OPTIONAL_LOCKS=0`: `for-each-ref`,
`rev-parse`, `cat-file`, `merge-base`, `ls-tree`, `show`.

Corrected (lane 2's verification, F22): the rehearsal scripts only read the live
repository, but not all of them with `GIT_OPTIONAL_LOCKS=0`. `10-restore.sh` (`:7`) and
`snapshot-real.sh` (`:5`) set it; `snapshot-real.sh:15` also runs `worktree list`, which
the list above omits. `24-patches.sh` runs `ls-tree` and `show` there (`:14–15`) without
it (`:7`). The four fetches under "Acts outside the rehearsals" did write there:
remote-tracking refs and their objects.

**Real surfaces, before (00:42:08Z) and after (00:53:06Z):**

Refreshed (F17): a third snapshot, final (01:13:46Z, `state/final/`, added by `076062af`),
came after this branch's three pushes (the last at 01:13:35Z) and the first brett-wip
commit. It came before the second brett-wip commit (01:14:30Z), which adds it, and before
the comment on #186 (01:14:55Z). The rows below hold at final too, except where a
correction says otherwise.

| Surface | Result |
| --- | --- |
| The real home's 29 installed files, its receipt, its `~/.claude/settings.json` | unchanged (sha256 and mode) |
| `~/.agents/workspace.yaml` | exists; size, inode, mtime and mode unchanged; its contents were not read |
| The Gate A backup | manifest passes both times; whole-tree listing (size, mode, mtime) unchanged |
| The run C rehearsal | whole-tree listing (size, mode, mtime) unchanged |
| Lane 1's register row and objects (`lanes --all`, `lane-objects`, both with `LANES_NO_FETCH=1`) | the row unchanged but for its age column; objects gained one line, `LANDED opensoft/openRepoTools#189` (00:49:25Z, the coordinator's). Corrected: they also gained two lines from another lane's log that the reader reports as unreadable (its count went from 3 to 5) |
| The live repository's 25 worktrees | the same 25 before and after; none locked, prunable or detached. Corrected: the same 25 paths at final, but four HEADs moved forward: the shared checkout's `main` `837928a` → `63810dd`, #191's branch `e406e0e` → `2411f40`, #190's `c139e88` → `e3a76b5`, and this writer's `837928a` → `fa44d75` |
| The live repository's refs | this writer added `refs/heads/004-migrate-to-triad-rollback` and its remote-tracking ref (fast-forward pushes). Other writers' acts moved the rest: `main` to `63810dd`, the T006 and run C branches, `004-migrate-to-triad-evidence-2`, and the #190/#191 heads. Corrected: the branch was already in the baseline at `837928a` (`state/before/live-refs.sorted:27`), made by this writer's `lane-worktrees add`; its commits moved it, and only its remote-tracking ref was new. The remote-tracking `origin/004-migrate-to-triad-evidence` (`3f7c48f`) was pruned before 00:53:06Z; #189's branch is no longer on GitHub. A remote-tracking ref here moves on a push from any worktree of this repository or on a fetch, this writer's four included, so which act moved each one is not recorded (F22) |

Corrected (lane 2's verification): the receipt's `README.md:65–67` says these final
surfaces "all equal `state/before/`". Byte for byte, three do not, as the rows above now
say: the register row (its age column), the register objects, and the worktree list (four
HEADs). The real home's files, receipt and `settings.json`, `workspace.yaml`'s metadata,
the backup and the rehearsal do.

The lane's register clone and brett-wip's shared checkout both moved during the window.
Both moves were other actors' commits: the coordinator's LANDING/LANDED lines for #189, and
other lanes' handoffs. This writer ran no register write.

**What a cutover, or a rollback after one, must preserve.**

Lane 1's live register row, read-only:
- `openRepoTools-1  LIVE  Eagle  team-008`;
- window `openRepoTools-1:@20`;
- transcript `df82f553-7803-49c4-8ddf-3f9acdcb8ee0`;
- the shared checkout as its directory;
- holds `CLAIMED opensoft/openRepoTools#186`.

In-place adoption keeps that directory, so neither the row nor the claim needs rewriting.
A rebinding is T018's, at a safe breakpoint, through `lane-start`/`lanes-edit.sh`.

`~/.agents/workspace.yaml` exists. Only `resume --workspace` and `wip init` write it, and
neither is in any rollback path; this run left its metadata unchanged.

**The rollback path in the plan's own words:** revert or pin-bump PRs, plus the preserved
installer, through (c2). It needs:
- no force push: every captured ref has only ever moved forward;
- no destructive reset;
- no pointer rewrite.

Refreshed (F8, F19): this is an argument, not a rehearsal.
- "Every captured ref has only ever moved forward" describes two days of other writers'
  work. It shows that nothing has needed a force push so far.
- No revert or pin-bump PR was rehearsed, and neither was a restore of the local
  candidate (run C's triad) from preserved artifacts. Section 7 lists both.
- Jobs: no before/after list of running jobs was taken, although the plan preserves
  "uncertain jobs" (plan.md:245). The only evidence is that no script kills a process.

**Acts outside the rehearsals.** These are publication and bookkeeping, listed so nothing is
hidden:
- four fetches in the live repository: three before the baseline, and one after the
  rehearsals to re-read the evidence branches that had moved (remote-tracking refs only);
- `lane-worktrees add openRepoTools-1 ort-triad-rollback`: the worktree, its new branch, and
  one record in lane 1's host-local tree inventory;
- the commits and fast-forward pushes of this branch;
- one commit to brett-wip `main` (`git add -- <receipt dir>`), from a sparse clone in scratch,
  never the shared checkout;
- one comment on #186;
- a stray empty file this writer made by mistake in the private `work-20261008` directory,
  outside the rehearsal tree, and removed at once.

## 4. Gate A/B evidence index

Verification marked "T011" was done by this run: checksums and the git identities it names.

| Branch, head | Document or receipt | What it proves | Verified by |
| --- | --- | --- | --- |
| main `63810dd` (#189) | `preservation-2026-10-07.md`, `inventory.json` | Gate A refresh (T001–T002): 17 trees, 33 refs, backup `prep-20261007T100559Z` | the writer's restore (97 PASS); lane 3's #189 review (LAND); **T011's restore today (90 PASS)** |
| main `63810dd` (#189) | `adopter-rehearsal-2026-10-07.md`, `adoption-plan.yaml` (run B's, source `e43b243`) | runs A and B at tool `7f84ca4`: 45/49/6 of 100, 0 dropped, bootstrap ok | lane 2's six-check verification (#186 comment 6036838832); #189 review |
| main `63810dd` (#189) | `consumer-reads-2026-10-07.md` | 33 outside consumers not covered, their timing | #189 review |
| main `63810dd` (#189) | `gate-b-checklist.md` | the 46-line Gate B walk of October 7 | #189 review |
| `004-migrate-to-triad-rehearsal-c` `1a26463` (#192, as `71b05cb`) | `adopter-rehearsal-2026-10-08.md`, run C's `adoption-plan.yaml` (source `837928a`) | run C: 65/49/6 of 120, 0 dropped, bootstrap ok; the arrangement T006–T011 used | **T011:** its receipt passes `sha256sum -c` (44); its three log digests are in it; the rehearsed commits resolve (`69b8924`, `593250d`, `73b04d6`, `7f84ca4`); its tree is unchanged by this run. #192 is not reviewed yet |
| `004-migrate-to-triad-root-guidance` `041a273` (#192) | `root-guidance-2026-10-08.md`, `patches/t006/` (5) | T006: 5 collisions, 32 repaired links, leg front doors, 35/35 provenance, bootstrap and validators | **T011:** the 5 patch digests match the document; every patch `git am`s onto its base; the trees equal the recorded ones (section 5). Lane 3's T006 review is not posted |
| `004-migrate-to-triad-ci` `cc7c7a1` (no PR) | `test-roots-and-ci-2026-10-08.md`, `patches/t010-*.patch` (2) | T009/T010: what the split breaks, the root rules, the composed contract, local proofs P1–P4 | **T011:** its 16 published log digests match the host-local logs (`sha256sum -c`, 16 OK); both patches apply (section 5). No review is recorded |
| PR #190 `e3a76b5` | the test-roots change | T009's explicit roots on today's layout | its own CI; lane 3's review is in progress |
| PR #191 `ecd7aa4` | the installer payload-source change | T007/T008's code side and the 15-row matrix as tests | its own CI; lane 3's review is in progress; lane 2's T008 verification is held |
| this branch | `gate-ab-evidence-2026-10-09.md` | T011 | — |
| brett-wip `f0ea2df7` | receipt `prep-20261007T100559Z` | Gate A's private record | **T011:** its manifest copy is the backup's (`2a46dff9…`), and the backup passes it |
| brett-wip `c311a78b` | receipt `adopter-fix-20261007-iM20tv` | runs A and B | **T011:** `sha256sum -c` 58 OK; the six published log digests are in it |
| brett-wip `3de0d37c` | receipt `adopter-fix-20261008-1HztL0` | run C | **T011:** `sha256sum -c` 44 OK |
| brett-wip `56f1e7c4` | receipt `rollback-20261009-ILvoVC` | T011 | its own `SHA256SUMS` (423 entries) |
| brett-wip `076062af` (refreshed, F17) | the same receipt, plus the final snapshot and two hygiene logs | T011 | its own `SHA256SUMS` (441 entries); lane 2's verification (#186 comment 6082370012) |
| host-local | backup `prep-20261007T100559Z`; rehearsal `work-20261008/rehearsal` | the preserved artifacts | **T011**, read-only, before and after |

No private receipt exists for T006 or T009/T010. Their logs are host-local only, in the
private prep area.

**Refreshed 2026-10-09T20:30Z (F15).** Origin moved after this index was written. Main is
`f87fd5a` (`git ls-remote`, 20:29:34Z): lane 3 landed #192 as `1abee1d` (20:24:59Z) and
then #190 as `f87fd5a` (20:26:03Z), on Brett Heap's word (#186 comment 6088703549). Each
squash equals its reviewed head: `1abee1d`'s tree is `71b05cb`'s, and `f87fd5a`'s diff is
`c4864ac..b50f197`'s. Every other move below is a fast-forward (`git merge-base
--is-ancestor`, each step).

| Branch or PR, head now | Since 01:13Z | Reviews and verification now |
| --- | --- | --- |
| #192, landed as `1abee1d` (head `71b05cb`; `004-migrate-to-triad-evidence-2` deleted) | run C's records, its plan and T006's `root-guidance-2026-10-08.md` and five patches are on main | lane 3: **LAND** on `71b05cb` (review 5464893559), with an exact rebuild of all five T006 patch commits; lane 2: run C's receipt verified, all six checks pass (#186 comment 6072724043) |
| `004-migrate-to-triad-root-guidance` `041a273`, `004-migrate-to-triad-rehearsal-c` `1a26463` | unchanged; their content landed with #192 | as #192 |
| #190, landed as `f87fd5a` (head `b50f197`; `feat/test-roots-for-the-triad` deleted) | `e3a76b5` → `dbc6837` (01:22:43Z) → `b50f197` (13:59:10Z, the manual guard, #193 item 1) | **LAND** on `dbc6837` from lane 3 (5464931249) and lane 1's independent review (5464938427); **LAND** on the `b50f197` delta (5471080687); CI green on `b50f197`, `tests-macos` included |
| `004-migrate-to-triad-ci` `d28e2cc` | `cc7c7a1` → `b4ef6b5` → `d28e2cc` (02:30:57Z); only `test-roots-and-ci-2026-10-08.md` changed, and both T010 patch blobs are identical at both heads | no review verdict posted; lane 3's reviewer of the T010 patches has resumed (#186 comment 6088703549) |
| #191 `13cc752` | `ecd7aa4` → `2411f40` (01:20:38Z) → `13cc752` (02:42:51Z) | **DO NOT LAND** on `2411f40` from lane 3 (5464963807) and lane 1's independent review (5465121368); **LAND** on `13cc752` from lane 3's delta review (5471121210), on condition that the PR body is corrected before the squash and `tests-macos` runs on `ready`. CI on `13cc752`: every job passed except `tests-macos`, skipped without `ready`. Lane 1's next head, `fdc5f18`, is announced and not on origin (#186 comment 6088714587, item 3) |
| `004-migrate-to-triad-installer` `51993a4` (new, 01:21:15Z; no PR) | T007's entry point, `patches/t007-assembly-entry-point.patch` (sha256 `361c037d…a277d`), and `installer-2026-10-08.md` | lane 3: **CHANGES REQUIRED** on the patch: confirm the gitlink before running the pinned implementation on the remote path (review 5471121210, T3). Lane 1 puts that change on this branch (#186 comment 6088714587, item 3) |
| `004-migrate-to-triad-candidate` `935f53f` (new, 01:58:43Z; no PR) | `candidate-2026-10-09.md`: the composed candidate, built from #190 `dbc6837` and #191 `2411f40` (`:29–30`); receipt `candidate-20261009-JR8YyA` | lane 3: **REPRODUCES**, fit for the composed run (#186 comment 6082068576). Its section 5 records that no suite run had finished. Lane 1's r2 runs finished at 18:20:47Z (lane 2's reading, #186 comment 6087267593); no record of them is on origin. The receipt is not on brett-wip `ea6c09d1` |
| `004-migrate-to-triad-t018` `63bff08` (new, 20:28:03Z; no PR) | lane 1's T018 exercise (#186 comment 6088703549) | — |
| `feat/triad-lane-tooling` `30f9dc0` | `c45a452` → `2aa8a59` → `96da9af` → `30f9dc0` (14:18:02Z) | no PR |
| `feat/test-roots-followups` `01ccc86` | #190's follow-ups (#193 items 2–7); `7144eef` → `01ccc86` (20:31:02Z), a merge of main `f87fd5a` (re-read 20:36:57Z) | lane 3's review has resumed (#186 comment 6088703549) |
| `004-migrate-to-triad-reads` `a7a8e00` | `a6830a1` → `a7a8e00` (13:50:08Z): lane 2's `gate-b-status-2026-10-09.md` | no PR; lane 1's own walk goes into its next evidence PR (#186 comment 6088714587, item 1) |
| brett-wip `99eed35` | Gate A capture tooling v2, which answers this record's three findings (#186 comment 6073036070) | lane 2's final verification: `capture.sh:170` rewrites its source's index, and `restore.sh:132` can aim at `/` (#186 comment 6087261307). Lane 1 accepts both; no capture runs on a real checkout until a fixed version is re-verified (#186 comment 6088714587, item 4) |
| issue #193 (13:42:32Z; updated 20:26:33Z) | the follow-ups deferred at the landing of #190 and #192: item 1 resolved by #190, item 15 added | — |

## 5. Follow-up patch and commit inventory

Every recorded patch for the rehearsed arrangement was re-applied by this run with `git am`,
in a fresh clone out of run C, onto the commit it names. Trees are compared, not commit
hashes: the committer differs, so the hashes do.

| # | Patch (branch, head) | sha256 | Leg | Applies to | Rehearsed result | Re-applied tree (T011) | At T014 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `patches/t006/assembly-0001-…front-door…` (root-guidance `041a273`) | `cd69c2a9…c5d096` | assembly | split `69b8924` | `3361812` | — (the three stack, below) | **applies as-is** onto the real split, after the frozen source's root files are checked unchanged |
| 2 | `patches/t006/assembly-0002-Bump-spec-leg-to-39c18877e042…` | `574c0df1…3647f9` | assembly | `3361812` | `1024f18` | — | **regenerated**: `bump-leg.py` against the real spec commit |
| 3 | `patches/t006/assembly-0003-Bump-code-leg-to-6169e8e96164…` | `a7f8521b…ec14aa` | assembly | `1024f18` | `3e87e39` | 1–3: `6eb8145e…`, as recorded | **regenerated**: `bump-leg.py` against the real code commit |
| 4 | `patches/t006/code-0001-…own-front-door…` | `74b98ff9…2ae1ec1` | code | code `73b04d6` | `6169e8e` | `ca65c3b9…`, as recorded | **applies as-is** |
| 5 | `patches/t006/spec-0001-…own-front-door…` | `c11070f0…8210b3` | spec | spec `593250d` | `39c1887` | `10256135…`, as recorded | **applies as-is** |
| 6 | `patches/t010-code-leg-tests-workflow.patch` (ci `cc7c7a1`) | `7ee3c6d0…786c3b` | code | code `73b04d6` | `b95d667` | alone: exit 0; on #4: exit 0 (`007509d2…`) | **applies as-is**; its env names mean something once PR #190 is in the code |
| 7 | `patches/t010-assembly-exact-pin-job.patch` | `6ee09f00…74670b` | assembly | split `69b8924` (proof commit `386be81` sat on the rehearsal-only bump `6ccdaf8`) | `386be81` | alone: exit 0 (`c37aa4f0…`); on #1–3: exit 0 (`b351c8e9…`) | **applies as-is** (a new file); `bash code/tests/run.sh` with `OPENREPOTOOLS_COMPOSED=1` needs PR #190 in the code leg |
| — | T007's assembly root `openRepoTools` entry point | — | assembly | — | — | — | **absent**: no `004-migrate-to-triad-installer` on origin; PR #191's body says it will be recorded there |
| — | the rehearsal-only bump `6ccdaf8` (code leg to `8ebf4ec`, PR #190 on `73b04d6`) | not a patch file | assembly | — | — | — | **regenerated**, like #2–3 |

**Counts:**
- **7 recorded patches:** T006 5, T010 2.
- **5 apply as-is:** #1, #4, #5, #6, #7.
- **2 regenerate at T014:** #2 and #3, plus the T010 proof's bump `6ccdaf8`, which has no
  patch file.
- **T007's entry point: 0 recorded.**

`git diff --check` exits 0 over the assembly stack (4) and the code stack (2).

**They stack:**
- **assembly:** #1, #2, #3, then #7;
- **code:** #4, then #6, then PR #190's code diff (`apply --check` 0), then PR #191's on top
  of that (`apply --check` 0, also with `--3way`);
- **spec:** #5 alone.

This is a text-level check only. **No test ran on the stacked candidate.**

Corrected (F20; lane 2's verification, #186 comment 6082370012):
- "As recorded" holds for the T006 trees (#1–#3 as a stack, #4, #5). Nothing recorded a
  tree for the T010 patches before this run. `test-roots-and-ci-2026-10-08.md` names commit
  `386be81` and no tree, and #6's commit `b95d667` appears only in the patch's own `From`
  line. So #6's and #7's trees above are this run's first record of them, not a match.
- #7 was re-applied on the split `69b8924`, not on its rehearsed base `6ccdaf8`.
- Commit `849592b`'s body says "the seven recorded patches re-applied onto their rehearsed
  bases with matching trees". The two points above are the exceptions.
- The first attempt to fetch the two PR heads ran under `GIT_ALLOW_PROTOCOL=file` and was
  refused (`fatal: transport 'ssh' not allowed`, exit 128; receipt
  `logs/24-patches.log:21–32`). `25-prs.sh` redid it, and the stack result above is the
  redo's (`logs/25-prs.log`).

**Refreshed 2026-10-09T20:30Z: the follow-up inventory (F15, F18).**
- T007's entry point has been recorded since 01:21:15Z, so "T007's entry point: 0
  recorded" above no longer holds.
- The stack check above used #190 `e3a76b5` and #191 `ecd7aa4`. Two later builds
  supersede it. One is the composed candidate at `dbc6837` and `2411f40`
  (`candidate-2026-10-09.md` section 2), which lane 3 rebuilt exactly (#186 comment
  6082068576). The other is lane 1's r2 at `b50f197` and `13cc752`, which lane 2 rebuilt
  with every `git am --3way` step exiting 0 and the same trees (#186 comment 6087232548,
  item 3).

Gate B asks for "reviewed follow-up patches" (plan.md:140–141). Each named follow-up below
maps to a patch, a branch or PR, an owner, or "deferred". Line numbers in run C's plan and
in `root-guidance-2026-10-08.md` are on main since #192 (`1abee1d`).

| Follow-up (where named) | Patch, branch or PR | Owner | State at 20:30Z |
| --- | --- | --- | --- |
| T006's five patches (the table above) | `patches/t006/`, on main since #192 | lane 1 (T006) | reviewed: LAND (5464893559). #2, #3 and the bump `6ccdaf8` regenerate at T014 |
| T010's two patches (the table above) | `004-migrate-to-triad-ci` `d28e2cc` | lane 1 (T010) | no review verdict posted; lane 3's reviewer has resumed (#186 comment 6088703549). Both are authored by the fixture identity, to carry a real author at T014 (#186 comment 6082068576, finding 9) |
| T007's assembly entry point | `004-migrate-to-triad-installer` `51993a4` | lane 1 (T007) | CHANGES REQUIRED (5471121210, T3) |
| T007/T008's code side | #191 `13cc752` | lane 1 (T007) | LAND with conditions (5471121210); next head `fdc5f18` announced. Open there: the parent-directory walk (delta 4, which `fdc5f18` answers per lane 1) and the hygiene test passing by spelling (delta 5) |
| #190's manual guard (#193 item 1) | in #190 since `b50f197` | lane 1 (T009) | resolved: landed with #190 |
| #190's other follow-ups (#193 items 2–7) | `feat/test-roots-followups` `01ccc86` (main merged in at 20:31:02Z) | lane 1 (T009) | no PR yet; one against main is now possible (#186 comment 6088703549). Its `AGENTS.md` hunk does not apply to the triad's assembly `AGENTS.md` (#186 comment 6082068576, finding 8) |
| The named-root refusal wording (#193 item 15) | — | lane 1 (T009) | open (#186 comment 6088714587, item 6) |
| T006 × #190, `test_agents_md_names_the_pin_rules` (#193 item 14) | — | lane 1 decides | open; it fails in r2's composed run (#186 comment 6087267593) |
| r2's other failures: `test_r14_the_documented_upstream_skip_is_unchanged` (`KeyError: 'reason'`), the lane suite's row-stamp cases, `test_run_wrapper`'s timeouts | — | lane 1 | being classified by lane 1 (#186 comment 6088714587, item 5) |
| #192's text findings (#193 items 8–13) | lane 2's `004-migrate-to-triad-evidence-2-followups` (#186 comment 6082466833, item 3) | lane 2, for lane 1 | on origin since 20:32:51Z at `096de93`, with main `f87fd5a` merged in; no PR (re-read 20:36:57Z) |
| Gate A capture tooling v2 | brett-wip `99eed35` | lane 1 | to be fixed and re-verified before any real capture (#186 comments 6087261307, 6088714587) |
| Run C's `follow_ups`: 29 entries (`adoption-plan.yaml:392–421`) | the next five rows | | |
| … 13 entries: a shipped command or test names `docs/`, `openspec/` or `specs/` (`:393–405`) | lane 3's `feat/triad-lane-tooling` `30f9dc0`, no PR; #190 (landed) for the suite's roots | `root-guidance-2026-10-08.md:188–194` routes the files it names: `lane-start`, `lanes-edit.sh`, `test_lane_helpers.sh` and the OpenSpec keys in `lanes-edit.sh` and `lane-handoff` to lane 3; `openRepoTools` to T007; `test_repo_hygiene.py`, `test_lane_start_claude_current.py` and `tests/run.sh` to T009/T010; `claude-current` to its text owner | that routing names neither `test_install_skill_and_hook.py` nor `test_park_resume_commands.py`, nor the plan's unnamed ninth `docs/` file: no owner is recorded for them |
| … 5 `shape/` collisions (`:406–410`) | T006's `assembly-0001` (`root-guidance-2026-10-08.md:70–76`) | lane 1 (T006) | merged in the patch; deleting the unpinned `shape/AGENTS.md`, `shape/CLAUDE.md` and `shape/README.md` is deferred to T014's reviewer (`:76`, `:394`) |
| … open the split as a pull request (`:411`) | — | T013 (tasks.md:96–98) | deferred |
| … the entry point (`:413`) and the test roots (`:414`) | the T007 rows above; #190 and the T010 row above | lane 1 | as above |
| … 8 more plan-level items (`:412`, `:415–421`) | `:412` was rehearsed in runs B and C; `:415`, the workflow bootstrap, in T006 | by tasks.md: `:412` and `:415` T013; `:416` T016–T018; `:417` T012; `:418` and `:420` T014; `:419` T016; `:421` T015 | deferred |
| The 33 outside consumers not covered (`consumer-reads-2026-10-07.md:303`) | — | the owners listed there | deferred |

## 6. Pull requests to main with layout-neutral changes

| PR | Head | Files | State at 00:5xZ |
| --- | --- | --- | --- |
| #190 `feat/test-roots-for-the-triad` | `e3a76b5` | `tests/` only (8 files) | open; `guard-launch-mode`, `tests-windows`, `parse-macos` and SonarCloud green; `tests` and `tests-no-submodule` running; no `ready` label |
| #191 `feat/installer-payload-source-resolution` | `ecd7aa4` | `openRepoTools`, two test files | open; the same green set, `tests` and `tests-no-submodule` running. At `e406e0e` (00:3xZ), `guard-launch-mode` and `tests-windows` had failed; `ecd7aa4` is the push after that |

Both are based on `c4864ac`. Both touch `tests/test_openrepotools_command.py`, and they
stack cleanly in the order #190 then #191. Neither touches a root front-door file, so T006's
`assembly-0001` is unaffected by either.

Lane 3's `feat/triad-lane-tooling` (`c45a452`) is on origin with no PR.

**Refreshed 2026-10-09T20:30Z (F15)** (`gh pr view`, 20:29:45Z; check runs, 20:30:23Z):

| PR | Head | State |
| --- | --- | --- |
| #190 | `b50f197` | **landed** as `f87fd5a` at 20:26:03Z, after #192. CI on `b50f197` was green, `tests-macos` included. |
| #191 | `13cc752` | open; no `ready` label. On `13cc752` every CI job passed except `tests-macos`, which was skipped. LAND from lane 3's delta review, with conditions (section 4). Next head announced, not pushed. |
| #192 | `71b05cb` | **landed** as `1abee1d` at 20:24:59Z. CI on `71b05cb` was green, `tests-macos` included. |

#191 is still based on `c4864ac`. It still stacks on #190 in that order:
- lane 2 applied `dbc6837` then `13cc752` cleanly onto the patched code leg (#186 comment
  6082370012, check (v));
- lane 2's rebuild of lane 1's r2 applied `b50f197` then `13cc752`, every `git am --3way`
  step exit 0 (#186 comment 6087232548, item 3).

Lane 3's `feat/triad-lane-tooling` is at `30f9dc0`, still with no PR.

## 7. What Gate B still lacks

Gate B is "complete local rehearsal evidence, restore rehearsal, reviewed follow-up patches,
resolved mapping and a passing compatibility test matrix" (plan.md). Against that:

1. **Restore rehearsal.** Done for the source and for the installed payload, with two
   findings:
   - for any tree that is not clean, the October 7 capture procedure is not a restore
     (section 1);
   - `RESTORE.md`'s copy-back leaves `installed.tsv` stale. Rollback should be (c2): a
     reinstall from the preserved source, or the copy-back followed by restoring the
     receipt.

   `RESTORE.md`'s `git bundle verify` line also needs a repository to run in.

   Refreshed 2026-10-09T20:30Z (F11, F13): the hook and settings rollback is not rehearsed,
   and no stage added or retired a placed file (section 2). Gate A's capture tooling v2
   (brett-wip `99eed35`, #186 comment 6073036070) answers the two findings and the
   `bundle verify` line. Lane 2's final verification found that its `capture.sh` rewrites
   its source's index (#186 comment 6087261307), and no capture runs on a real checkout
   until a fixed version is re-verified (#186 comment 6088714587, item 4).
2. **T007's root entry point is not published.** Without it the inventory has no assembly
   `openRepoTools`. PR #191, the code side, is open.

   Refreshed 2026-10-09T20:30Z (F15): it has been recorded since 01:21:15Z, on
   `004-migrate-to-triad-installer` @ `51993a4`. Lane 3 requires one change before it goes
   into the root-split PR: confirm the gitlink before running the pinned implementation on
   the remote path (review 5471121210, T3). #191 has LAND on `13cc752` with conditions,
   and a next head is announced (section 4).
3. **No composed candidate carrying every follow-up has run the suite.** That candidate is
   T006 + T010 + #190 + #191 + the entry point. It was only checked to apply (section 5).
   The October 8 proof P1 (285 passed, 2 failed) ran on run C's code leg with #190 alone:
   - one failure is the leg's missing `.gitattributes`, which T006's `code-0001` adds;
   - the other is two lane-suite assertions that depend on run-root length.

   Lane 2's run C composed-suite discovery has not reported on #186. The hosted-runner part
   (Windows, macOS) is blocked until real legs exist (checklist line 35).

   Refreshed 2026-10-09T20:30Z (F15):
   - Lane 2's discovery reported at 01:21:53Z (#186 comment 6072319462, with its addendum
     6072333212).
   - The composed candidate is recorded on `004-migrate-to-triad-candidate` @ `935f53f`,
     and lane 3 rebuilt it exactly (#186 comment 6082068576).
   - Lane 1's r2 runs (code with #190 at `b50f197` and #191 at `13cc752`) finished at
     18:20:47Z. In lane 2's reading of the logs (#186 comment 6087267593): composed, 5
     failed and 1411 passed; standalone, 3 failed; without the dependency, 6 failed.
     Lane 1 is classifying them (#186 comment 6088714587, item 5).
   - **No suite run of the composed candidate passes yet, and none is recorded on origin.**
4. **Reviews.** Lane 3's reviews of #190 and #191 are in progress. No review is recorded for
   the T006 patch set (#192) or the T010 patches (checklist line 46).

   Refreshed 2026-10-09T20:30Z (F15):
   - #190: LAND twice and on its delta, and landed (section 4).
   - The T006 patch set: lane 3's #192 review rebuilt all five patch commits exactly (LAND,
     5464893559), and #192 landed.
   - #191: LAND on `13cc752` with conditions (5471121210).
   - The T007 patch: CHANGES REQUIRED (5471121210).
   - The T010 patches: no verdict yet; lane 3's reviewer has resumed (#186 comment
     6088703549).
5. **Mapping.** Main carries run B's plan, source `e43b243`, which survives only as
   `refs/pull/188/head`. Run C's plan, source `837928a`, is in #192, unlanded.

   Corrected (F9): `e43b243` survives on origin only as `refs/pull/188/head` (`git
   ls-remote`, 20:29:34Z). It is also in the Gate A bundle, as the captured branch
   `chore/openreposhape-pin-7f84ca4` (`inventory.json` `local_branches`), and that branch
   was still in the shared checkout at 01:13:46Z (receipt `state/final/live-refs.sorted`).
   Refreshed 2026-10-09T20:30Z: #192 landed, so main now carries run C's plan, source
   `837928a`, in place of run B's.
6. **Gate A**, for orientation:
   - the final capture at an owner-coordinated freeze, taking finding 1;
   - installed-file receipts for py-bench and other profiles and workstations;
   - owner dispositions.

   Refreshed (F14): T002 asks for "installed receipts/config" (tasks.md:28–29; plan.md:79).
   The Gate A backup holds the receipt (`installed.tsv`, 29 rows) but no `settings.json`,
   and `RESTORE.md`'s copy-back restores neither (section 2). So the backup cannot restore
   the hooks and settings an install writes.
7. **T011's own acceptance (refreshed, F19).** This record checks no task complete.
   - Rehearsed: the source restore from the Gate A bundle, and the rollback of the
     installed payload's 29 files and receipt.
   - Not rehearsed:
     - a restore of the local candidate (run C's triad) from preserved artifacts;
     - the post-merge rollback the plan names, "reviewed revert/pin-bump PRs and the
       preserved installer" (plan.md:243);
     - a hook or settings rollback (section 2);
     - a before/after list of running jobs (plan.md:245).
   - Published: the evidence index and the follow-up inventory, refreshed above.

**Gate C is Brett Heap's explicit approval.** It names the source and standard revisions,
the leg repositories, their visibility and the final plan. Nothing here asks for it or
infers it.

## 8. Log SHA256s

The logs and snapshots are in the private receipt.

| Log | SHA256 |
| --- | --- |
| `10-restore.log` (section 1, 90 PASS) | `bb3a5829d3a1e5ea6924331456b9f6b81b4a8380d878617344adf2807e70a848` |
| `11-dirty.log` (section 1, A 0/3, B 3/3) | `e6d1448fd18ebe2889b7c564307024ef8e2e49b48e2ef642838c8e0f89d1a9da` |
| `21-clones.log` (section 2 sources) | `d4b39b1cabeae6d2395f5db3610157689863af40bb2fc1354a2116ddaf855139` |
| `22-installs.log` (section 2, 10 installs and 2 copy-backs; corrected from "12 installs") | `4a7beffda610253de630b389f1be09c07df660df4d06a8745e10ed8d1703f2a6` |
| `23-compare.log` (section 2 comparisons) | `dca56f959f8075ac0054745965896dd43e4eb9b58cc07409b89d583e0f91e72c` |
| `24-patches.log` (section 5) | `f6a385eef8a32d683643aa7637e31cc88900af69888836c7fef7923cfac6de66` |
| `25-prs.log` (section 5, the two PRs) | `4ae121cd04df1bc87b796ec2c6969ab355273582f763375b13f9f7adb5787300` |
| `network-shim-calls.log` (empty) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `mutations.tsv` (section 3) | `76fc8521b1738fde5471f99e1641c6d901ebf72a65bb677d612700caf7ed77b1` |
| `refs-vs-live-now.tsv` (section 1) | `d3b5de9d85fe9ae8fe8a7a965d9015cb177c1e67d77beb30639cd51a02644249` |
| `restore-trees.tsv` (section 1, 17 trees) | `ace098036ebcec7fe47dd56a0bb7f38b97b9b10bc4753c9dd2d652349a57db98` |

**This document's own check.** `tests/run.sh -k repo_hygiene` did not run:
- the wrapper waited 5 minutes (00:57–01:02Z) on 7 other repositories' pytest processes
  (corrected: the log says "7 foreign pytest processes", receipt `logs/31-hygiene-flock.log:1`);
- its exact pytest line under `flock` on the workstation lock then queued 10 minutes behind
  the T007/T008 writer's full suite and was stopped before pytest started.

Two hygiene tests read every tracked file: the host-absolute-path test and the act-0 citation
test. Their own regexes, taken from `tests/test_repo_hygiene.py`, find nothing in this
file. CI is the suite of record.

Refreshed (2026-10-09T20:4xZ): on this refreshed file, `git diff --check` exits 0. The same two
regexes, read from `tests/test_repo_hygiene.py` at `fa44d75` (`HOST_ABSOLUTE_PATH` and
`ACT0_CITATION`), find nothing, and neither does a stricter scan for any host-absolute path
prefix. No pytest ran: another lane's openRepoTools suite was live on the workstation. CI
is still the suite of record, and this branch has no PR. Origin was re-read before the
push, at 20:36:57Z (`git ls-remote`). Main `f87fd5a`, #191 `13cc752` and
`004-migrate-to-triad-rollback` `fa44d75` were unchanged since 20:29:34Z.
`feat/test-roots-followups` and `004-migrate-to-triad-evidence-2-followups` had moved,
and sections 4 and 5 say so.

This record authorizes no conversion, repository creation, merge, default-branch move or
lane rebinding.
