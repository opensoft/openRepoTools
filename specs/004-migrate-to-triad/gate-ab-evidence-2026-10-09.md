# Gate A/B evidence, the restore and rollback rehearsal, and the follow-up inventory — October 9, 2026

**Task:** T011 of [tasks.md](tasks.md), under [#186](https://github.com/opensoft/openRepoTools/issues/186).
No task is checked complete by this record, and it approves nothing.
**Writer:** lane openRepoTools-1, 2026-10-09T00:36Z–01:1xZ.
**Evidence branch:** `004-migrate-to-triad-rollback` (from main `837928a`).
**Private receipt ID:** `rollback-20261009-ILvoVC` (brett-wip `migration/openRepoTools/`), holding every
script, log, snapshot and digest named below. Machine paths stay there.

T011 asks for three things. First, a rehearsal of restoring the local candidate and the
installed payload from the preserved artifacts. Second, proof that user work, jobs and claims
survive with no force push, no destructive reset and no workspace-pointer rewrite. Third,
publication of the Gate A/B evidence with the follow-up patch and commit inventory.
Sections 1–3 are the rehearsals, measured today. Sections 4–6 are the index and the
inventory. Section 7 is what Gate B still lacks.

**Short answer.**
- **Source restore:** passes, 90 checks of 90.
- **Installed payload:** restores to the main install exactly by either path.
- **What the rehearsals wrote:** only private scratch. Nothing in a real repository, the
  real home or the register.
- **Gate B is still open.** Section 7 lists what is missing.

## 1. Restore rehearsal of the source

The source is the Gate A backup `prep-20261007T100559Z` (host-local, read-only). The
rehearsal followed its `RESTORE.md` commands, with only the placeholder paths replaced by
private scratch. **90 checks passed, 0 failed.**

- The manifest (414 entries) passes `sha256sum -c`.
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
- **Against the live repository today, two days on**, the 33 captured refs are:
  - 26 identical;
  - 7 moved forward only: `main`, `origin/main` and `origin/HEAD` to `837928a`, the three
    October 7 evidence branches, and lane 3's `feat/triad-lane-tooling`;
  - 0 deleted;
  - **0 moved by anything other than a fast-forward**.

  18 refs were added since the capture.
- **All 17 captured trees:**
  - each HEAD resolves in the restore;
  - each tree ID equals the live one;
  - every index object is present;
  - the index a checkout of each HEAD makes equals the captured `index.ls-files-s` byte
    for byte (17 of 17).
- **One tree by `RESTORE.md`'s own procedure**: `main`, the capture with workflow files.
  - The steps: `worktree add --detach`, copy the captured files back, restore the captured
    exclude file.
  - Its index (100 entries) equals the capture.
  - All 70 copied files match `files.sha256`.
  - Its tracked status and its untracked and ignored lists equal the capture's, less the 4
    cache entries the capture lists as not copied.
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
| A: the per-worktree block of the backup's own `capture.sh`, verbatim | **no**: 3 staged blobs are in no bundle | **no** | **no** |
| B: A plus `git diff --cached --binary`, `git diff --binary` and every untracked file | yes | yes | yes |

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
  `code/openRepoTools`.
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

| Compared with (a) | H1 (b)→(c1) | H2 (b)→(c2) | H3 (b″)→(c1) | H4 (b″)→(c2) |
| --- | --- | --- | --- | --- |
| (b) placed files (path, mode, sha256) | same | same | **1 differs** | **1 differs** |
| (c) placed files (path, mode, sha256), 29 | same | same | same | same |
| (c) receipt rows (name, destination, sha256) | same | same | **1 stale row** | same |
| (c) the two hook entries | same | same | same | same |
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
- 12 installs and 10 refused ones;
- two copy-backs, snapshots and comparisons;
- the patch-application clones.

**No script pushes, stashes, cleans, kills a process, deletes a branch, removes a worktree,
runs `checkout -f` or `update-ref`, or writes `workspace.yaml`** (`grep` over every script
in the receipt). The one `reset --hard` is in a scratch clone of the rehearsal that section 5
patched. The live repository was only read, with `GIT_OPTIONAL_LOCKS=0`: `for-each-ref`,
`rev-parse`, `cat-file`, `merge-base`, `ls-tree`, `show`.

**Real surfaces, before (00:42:08Z) and after (00:53:06Z):**

| Surface | Result |
| --- | --- |
| The real home's 29 installed files, its receipt, its `~/.claude/settings.json` | unchanged (sha256 and mode) |
| `~/.agents/workspace.yaml` | exists; size, inode, mtime and mode unchanged; its contents were not read |
| The Gate A backup | manifest passes both times; whole-tree listing (size, mode, mtime) unchanged |
| The run C rehearsal | whole-tree listing (size, mode, mtime) unchanged |
| Lane 1's register row and objects (`lanes --all`, `lane-objects`, both with `LANES_NO_FETCH=1`) | the row unchanged but for its age column; objects gained one line, `LANDED opensoft/openRepoTools#189` (00:49:25Z, the coordinator's) |
| The live repository's 25 worktrees | the same 25 before and after; none locked, prunable or detached |
| The live repository's refs | this writer added `refs/heads/004-migrate-to-triad-rollback` and its remote-tracking ref (fast-forward pushes). Other writers' acts moved the rest: `main` to `63810dd`, the T006 and run C branches, `004-migrate-to-triad-evidence-2`, and the #190/#191 heads. |

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
| brett-wip (this run) | receipt `rollback-20261009-ILvoVC` | T011 | its own `SHA256SUMS` |
| host-local | backup `prep-20261007T100559Z`; rehearsal `work-20261008/rehearsal` | the preserved artifacts | **T011**, read-only, before and after |

No private receipt exists for T006 or T009/T010. Their logs are host-local only, in the
private prep area.

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

## 6. Pull requests to main with layout-neutral changes

| PR | Head | Files | State at 00:5xZ |
| --- | --- | --- | --- |
| #190 `feat/test-roots-for-the-triad` | `e3a76b5` | `tests/` only (8 files) | open; `guard-launch-mode`, `tests-windows`, `parse-macos` and SonarCloud green; `tests` and `tests-no-submodule` running; no `ready` label |
| #191 `feat/installer-payload-source-resolution` | `ecd7aa4` | `openRepoTools`, two test files | open; the same green set, `tests` and `tests-no-submodule` running. At `e406e0e` (00:3xZ), `guard-launch-mode` and `tests-windows` had failed; `ecd7aa4` is the push after that |

Both are based on `c4864ac`. Both touch `tests/test_openrepotools_command.py`, and they
stack cleanly in the order #190 then #191. Neither touches a root front-door file, so T006's
`assembly-0001` is unaffected by either.

Lane 3's `feat/triad-lane-tooling` (`c45a452`) is on origin with no PR.

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
2. **T007's root entry point is not published.** Without it the inventory has no assembly
   `openRepoTools`. PR #191, the code side, is open.
3. **No composed candidate carrying every follow-up has run the suite.** That candidate is
   T006 + T010 + #190 + #191 + the entry point. It was only checked to apply (section 5).
   The October 8 proof P1 (285 passed, 2 failed) ran on run C's code leg with #190 alone:
   - one failure is the leg's missing `.gitattributes`, which T006's `code-0001` adds;
   - the other is two lane-suite assertions that depend on run-root length.

   Lane 2's run C composed-suite discovery has not reported on #186. The hosted-runner part
   (Windows, macOS) is blocked until real legs exist (checklist line 35).
4. **Reviews.** Lane 3's reviews of #190 and #191 are in progress. No review is recorded for
   the T006 patch set (#192) or the T010 patches (checklist line 46).
5. **Mapping.** Main carries run B's plan, source `e43b243`, which survives only as
   `refs/pull/188/head`. Run C's plan, source `837928a`, is in #192, unlanded.
6. **Gate A**, for orientation:
   - the final capture at an owner-coordinated freeze, taking finding 1;
   - installed-file receipts for py-bench and other profiles and workstations;
   - owner dispositions.

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
| `22-installs.log` (section 2, 12 installs, 2 copy-backs) | `4a7beffda610253de630b389f1be09c07df660df4d06a8745e10ed8d1703f2a6` |
| `23-compare.log` (section 2 comparisons) | `dca56f959f8075ac0054745965896dd43e4eb9b58cc07409b89d583e0f91e72c` |
| `24-patches.log` (section 5) | `f6a385eef8a32d683643aa7637e31cc88900af69888836c7fef7923cfac6de66` |
| `25-prs.log` (section 5, the two PRs) | `4ae121cd04df1bc87b796ec2c6969ab355273582f763375b13f9f7adb5787300` |
| `network-shim-calls.log` (empty) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `mutations.tsv` (section 3) | `76fc8521b1738fde5471f99e1641c6d901ebf72a65bb677d612700caf7ed77b1` |
| `refs-vs-live-now.tsv` (section 1) | `d3b5de9d85fe9ae8fe8a7a965d9015cb177c1e67d77beb30639cd51a02644249` |
| `restore-trees.tsv` (section 1, 17 trees) | `ace098036ebcec7fe47dd56a0bb7f38b97b9b10bc4753c9dd2d652349a57db98` |

This record authorizes no conversion, repository creation, merge, default-branch move or
lane rebinding.
