# Gate B status walk — 2026-10-09

**Reads:** 2026-10-09T13:29:20Z–13:48:37Z (UTC), plus one relay from lane 2's
coordinator received at about 13:4xZ (cited "(relay)"). Anything after 13:48:37Z is not
in this walk. **By:** lane openRepoTools-2's writer, under opensoft/openRepoTools#186.
**For:** lane openRepoTools-1, which walks the Gate B checklist before it asks Brett
Heap for Gate C.
**Walks:** the 46 lines of [gate-b-checklist.md](gate-b-checklist.md). It was written
2026-10-07 at `76dcb93` and landed on main as `63810dd` via #189. The checklist
is byte-identical at both commits: both blobs hash to sha256 `ab2a7351…`.

This walk records facts. It approves nothing, and it changes no status in `tasks.md`,
where all 19 tasks are still open on main. Main's `inventory.json:1642` still reads
`"gate_b_complete": false`. Gate C stays Brett Heap's explicit approval naming the
actual revisions (plan.md:161–163). Inferences are marked "(inferred)".

**Moving at the cutoff.** These reads saw the following, all within a few minutes of
13:48:37Z:
- Brett Heap gave the word "land 190 and 192" in lane 3's window at about 13:4xZ
  (relay). Lane 3 lands #192 first, then #190, by squash with proof. The follow-ups of
  both go to #193.
- #192 received `ready` at 13:42:03Z, at an unchanged head `71b05cb`.
- #193 opened at 13:42:32Z, titled "follow-ups deferred at the landing of #190 and
  #192".
- At 13:48:31Z main was still `63810dd`, and both PRs were still OPEN with `ready`:
  #190 at `dbc6837` and #192 at `71b05cb`. #192's `tests`, `tests-no-submodule` and
  `tests-macos` were running.

Lines whose only artifact is on #192 or #190 are therefore marked "unlanded; landing in progress by lane 3 on Brett's word". Main will move from `63810dd` twice (relay). A landing after
the cutoff changes those notes and nothing else (inferred).

## What was read

| Object | SHA |
| --- | --- |
| main | `63810dd0d3d1bfa54133d0fecd572be09abed550` |
| PR #190 head (`feat/test-roots-for-the-triad`) | `dbc6837ff329434e688147e8bae76cd4b3dec79c` |
| PR #191 head (`feat/installer-payload-source-resolution`) | `13cc75298143302cfa0805abce6271916ed912e5` |
| PR #192 head (`004-migrate-to-triad-evidence-2`) | `71b05cb58ed1dd882ef0953ef0e9fd9af0927001` |
| `004-migrate-to-triad-root-guidance` | `041a27302ad17cf3463cb9965691c524987be030` |
| `004-migrate-to-triad-installer` | `51993a40cef56424e9291a62572c199a2e36a5c1` |
| `004-migrate-to-triad-ci` | `d28e2cc8afcef0639712bc2938f921c904000a10` |
| `004-migrate-to-triad-rollback` | `fa44d75a7a4ed6cb255ecd74b75a7e27b01e9741` |
| `004-migrate-to-triad-rehearsal-c` | `1a264639a0ddbc35fbfde76aac388524a1225d33` |
| `004-migrate-to-triad-exec` | `e5f582a26661a2b902e1087c19de4e7f51855ff5` |
| `004-migrate-to-triad-candidate` | `935f53f8b497b1409fe4523a14a84ba416f19d95` |
| `004-migrate-to-triad-reads` (this branch, before this file) | `a6830a1b14fe2aa100478a5e16db3aa22b2bc53a` |
| `feat/test-roots-manual-guard` / `feat/test-roots-followups` (no PR) | `b50f1974f3aa4b78b1bcdc5d770e63795d42e4ac` / `7144eefba58038f591be7e7477f64242ae0e3c5b` |
| brett-wip `main` at the last fetch (13:43:18Z) | `8c00275a6194ed2d4c35a740cd219a0883f52287` |

| Private receipt (brett-wip `migration/openRepoTools/`) | brett-wip commit |
| --- | --- |
| `prep-20261007T100559Z` (Gate A) | `f0ea2df7d5c6d95c26413b68843451e953a50018` |
| `adopter-fix-20261007-iM20tv` (runs A and B) | `c311a78bc335cab685ab37fb963618328f7f9c71` |
| `adopter-fix-20261008-1HztL0` (run C) | `3de0d37c3160fa5751a1cd081c407e96078bfdcf` |
| `rollback-20261009-ILvoVC` (T011) | `56f1e7c421b94cf02b81bf39269b7213e49e3994`, then `076062af8f7c0b1b4ebbae2af865ff8a65514ca8` |
| `tools-20261009` (Gate A capture tooling v2) | `99eed358301154be89bf4ce2e612393ec941631c` |

**Short names.** These name documents under `specs/004-migrate-to-triad/`:
- **ckl**: `gate-b-checklist.md` on main.
- **ar7**: `adopter-rehearsal-2026-10-07.md` on main.
- **pres**: `preservation-2026-10-07.md` on main.
- **ar8**: `adopter-rehearsal-2026-10-08.md` on rehearsal-c and #192.
- **rg**: `root-guidance-2026-10-08.md` on root-guidance and #192.
- **inst**: `installer-2026-10-08.md` on installer.
- **trc**: `test-roots-and-ci-2026-10-08.md` on ci.
- **gab**: `gate-ab-evidence-2026-10-09.md` on rollback.
- **cand**: `candidate-2026-10-09.md` on candidate.

Branch names drop the `004-migrate-to-triad-` prefix. The checklist's own
`file:line` cites refer to `ff6f6a7`. Every planning file they cite is byte-identical
between `ff6f6a7` and main: `git diff --stat ff6f6a7 63810dd` over plan, tasks, spec,
adopter-blocker, adopter-rehearsal, installer-design, preparation, verification,
quickstart, data-model, protocol-review and the change's design, proposal, tasks and
capability spec is empty. `adoption-plan.yaml` is the exception (see "Facts noticed").

**#186 comments cited, by id:**

| Id | UTC | By | Subject |
| --- | --- | --- | --- |
| 6035767825 | 10-07 10:11:58 | lane 1 | Brett Heap's words; legs and visibility confirmed |
| 6036838832 | 10-07 11:20:38 | lane 2 | (3b): runs A/B verification, all six checks pass |
| 6068861167 | 10-08 20:54:03 | lane 1 | #187 → `44983ce`, #188 → `837928a`; the `/tmp` loss |
| 6068938765 | 10-08 20:59:02 | lane 1 | run C |
| 6069614034 | 10-08 21:42:44 | lane 2 | the composed-suite discovery is relaunched; the lock deviation |
| 6071777207 | 10-09 00:30:47 | lane 3 | #189 LAND |
| 6071824778 | 10-09 00:35:06 | lane 1 | T006 rebuilt on run C |
| 6072247322 | 10-09 01:14:55 | lane 1 | T011, with "Gate B still lacks" |
| 6072319462 | 10-09 01:21:53 | lane 2 | composed-suite discovery on run C |
| 6072333212 | 10-09 01:23:12 | lane 2 | addendum to the discovery |
| 6072724043 | 10-09 02:01:10 | lane 2 | (3c): run C verification, all six checks pass |
| 6072771795 | 10-09 02:05:42 | lane 3 | #192 LAND |
| 6072817992 | 10-09 02:10:09 | lane 3 | #190 LAND |
| 6072887742 | 10-09 02:16:57 | lane 3 | #191 DO NOT LAND |
| 6073036070 | 10-09 02:29:17 | lane 1 | Gate A capture tooling v2 |
| 6073063804 | 10-09 02:31:55 | lane 1 | T009/T010 |
| 6073209094 | 10-09 02:46:23 | lane 2 | T008 matrix of #191 at `2411f40` |
| 6073234714 | 10-09 02:48:55 | lane 2 | addendum to the T008 matrix |
| 6081924537 | 10-09 13:31:22 | lane 2 | five writers fanned out |
| 6082068576 | 10-09 13:38:57 | lane 3 | candidate `935f53f`: REPRODUCES |
| 6082139424 | 10-09 13:43:08 | lane 3 | T011 `fa44d75`: DO NOT LAND as a future PR |

**PR reviews cited:**

| PR | Review | Head | Verdict | Reviewer (as headed) |
| --- | --- | --- | --- | --- |
| #188 | 5440809537 | `e43b243` | LAND | lane openRepoTools-3 |
| #189 | 5464425616 | `3f7c48f` | LAND | lane openRepoTools-3 |
| #190 | 5464931249 | `dbc6837` | LAND | lane openRepoTools-3 |
| #190 | 5464938427 | `dbc6837` | LAND | lane openRepoTools-1 |
| #191 | 5464963807 | `2411f40` | DO NOT LAND | lane openRepoTools-3 |
| #191 | 5465121368 | `2411f40` | DO NOT LAND | lane openRepoTools-1 |
| #192 | 5464893559 | `71b05cb` | LAND | lane openRepoTools-3 |

#191 has no review at `13cc752`.

## How it was read

`<wt>` is lane 2's `triad-reads` worktree, fast-forwarded to `a6830a1`. `<bare>` is a
fresh bare clone of opensoft/openRepoTools in lane 2's scratch. `<reg>` is lane 2's
brett-wip register clone, read only through `origin/main`. Host paths are left out,
because the feature's public files carry no machine paths (plan.md:39–40). Every
`gh` call was a read.

```sh
git -C <wt> fetch -q origin 004-migrate-to-triad-reads main
git -C <wt> merge --ff-only origin/004-migrate-to-triad-reads
git -C <wt> show origin/main:specs/004-migrate-to-triad/gate-b-checklist.md | cat -n
git -C <wt> show origin/main:specs/004-migrate-to-triad/tasks.md | cat -n
git -C <wt> show 63810dd:specs/004-migrate-to-triad/preservation-2026-10-07.md | cat -n
git -C <wt> show 63810dd:specs/004-migrate-to-triad/adopter-rehearsal-2026-10-07.md | cat -n
git -C <wt> show 63810dd:specs/004-migrate-to-triad/inventory.json  # refreshed.*, gate_b_complete
git -C <wt> show "ae70dc5:specs/004-migrate-to-triad/consumer-reads-2026-10-07.md" | grep -n INSTALLABLES
git -C <wt> show "63810dd:specs/004-migrate-to-triad/consumer-reads-2026-10-07.md" | grep -n INSTALLABLES
git -C <wt> diff --stat ff6f6a7 63810dd -- <the planning files the checklist cites>
git -C <wt> for-each-ref refs/heads/adopt/ refs/remotes/origin/adopt/
git --git-dir=<bare> fetch origin 'refs/heads/004-migrate-to-triad*:…' 'refs/heads/feat/*:…' \
    refs/pull/190/head refs/pull/191/head refs/pull/192/head
git --git-dir=<bare> log refs/remotes/origin/main..<each evidence branch>
git --git-dir=<bare> diff --stat ff6f6a7 <installer, ci>     # the branches not yet retargeted
git --git-dir=<bare> show <branch>:specs/004-migrate-to-triad/<document> | cat -n   # ar8 rg inst trc gab cand
git --git-dir=<bare> show refs/pr/192:openspec/changes/migrate-to-triad/adoption-plan.yaml | grep -n 'path:\|leg:'
git --git-dir=<bare> ls-tree -r --name-only 837928a | grep -c '^features/'
git --git-dir=<bare> diff --stat cc7c7a1 d28e2cc
git --git-dir=<bare> show 004-migrate-to-triad-ci:specs/004-migrate-to-triad/patches/t010-code-leg-tests-workflow.patch
git -C <reg> fetch -q origin main
git -C <reg> log origin/main -- migration/openRepoTools/<id>
git -C <reg> ls-tree -r --name-only origin/main migration/openRepoTools/
git -C <reg> show 6266a03d4 c5436fc54 6060080c4 a9d00168c 41e1fc262    # lane handoffs and register rows
gh issue view 186 --repo opensoft/openRepoTools --json comments        # 13:29:40Z, 13:38:02Z, 13:43:47Z
gh issue view 193 --repo opensoft/openRepoTools --json body,comments
gh pr view <188…192> --repo opensoft/openRepoTools --json headRefOid,state,labels,reviews,statusCheckRollup,mergeCommit
gh api repos/opensoft/openRepoTools/pulls/<188…192>/reviews
gh api repos/opensoft/openRepoTools/pulls/190/reviews/5470865276/comments
gh api repos/opensoft/openRepoTools/issues/192/events
gh api 'repos/opensoft/openRepoTools/events?per_page=100&page=<1…3>'
gh api repos/opensoft/openRepoTools-spec; gh api repos/opensoft/openRepoTools-code
git ls-remote git@github.com:opensoft/openRepoTools 'refs/heads/adopt/*'
```

## State at read time

- **Main** is `63810dd` (#189, landed 00:44:03Z). #187 landed as `44983ce` and #188 as
  `837928a`, both on 2026-10-08.
- **#190** is at `dbc6837` and carries `ready`. Every check is green, including
  `tests-macos` (04:05:46Z). It has two LAND reviews.
- **#191** is at `13cc752`, pushed 02:42:52Z. It has no label, and `tests-macos` was
  SKIPPED. Its two reviews, both DO NOT LAND, are on `2411f40`.
- **#192** is at `71b05cb` and has one LAND review. It received `ready` at 13:42:03Z,
  and its CI was re-running at the cutoff.
- **Lane 1** resumed at 13:21Z (brett-wip `a9d00168c`, `41e1fc262`). Its handoff names
  eight writers:
  - a #191 fix cycle;
  - `b50f197` onto #190, then the follow-ups PR;
  - a reviewer;
  - a candidate rebuild, "r2", with three suites (see lane 2 below);
  - a fold of the ci, installer and rollback branches into #192;
  - a read-only Gate B checklist walk of its own, with private output;
  - Gate C inputs;
  - a T018 exercise.
- **Lane 2** has five writers (#186 6081924537):
  1. a T008 re-run on #191 `13cc752`;
  2. a T011 verification against `rollback-20261009-ILvoVC`;
  3. a verification of Gate A capture tooling v2;
  4. the candidate's three suites, then a #191 `13cc752` variant;
  5. this walk.

  Writer 4 has since stopped its suites so as not to duplicate lane 1's (relay). Lane
  1's r2 writer has run the three suites since 13:33Z on r2: code `4dbcf6c` (`73b04d6`
  plus #190 at `b50f197`, #191 at `13cc752`, T006 `code-0001` and T010), spec
  `9e1d006`, assembly `5d92962`. Lane 2's writer 4 now only reproduces r2's trees and
  checks the composed refusal contract and the install.
- **Lane 3** has six writers (brett-wip `c5436fc54`, `6266a03d4`):
  - two T018 writers;
  - a review of the #191 delta and the T007 patch;
  - a review of `b50f197`, `7144eef` and the T010 patches;
  - a reproduction review of the candidate, posted at 13:38:57Z;
  - a review of T011's public record, posted at 13:43:08Z.
- **Leg names.** `opensoft/openRepoTools-spec` and `-code` both return HTTP 404 at
  13:34:01Z.
- **`adopt/` refs.** The remote lists none, and the repository's `refs/heads/adopt/`
  and `refs/remotes/origin/adopt/` are empty.

## Status legend

The legend is the checklist's own (ckl:86–100), restated for today. Each line has
exactly one status.
- **EXISTS**: the artifact is on main, a named branch or PR, or in a named receipt at
  read time. The cell cites it. "Unlanded" marks an artifact that is only on a PR or
  branch.
- **IN PROGRESS by …**: a named writer holds the work at read time. Lane 2's four
  running verifications are marked "result to follow on #186".
- **NOBODY**: no lane writer holds the work at read time.
- **BLOCKED on …**: lane work alone cannot satisfy the line as the plan stands.
- **DECIDED**: settled by Brett Heap's word.

"Changed" means the status differs from the checklist's status of 2026-10-07.

## The walk

### T003: mapping, leg names, prerequisites

| # (ckl row) | Requirement (checklist's cite) | 2026-10-07 | Now | Changed |
| --- | --- | --- | --- | --- |
| 1 (:131) | Confirm leg names and visibility (tasks.md:33; spec.md:66–67) | DECIDED | **DECIDED.** #186 6035767825 stands. Run C's plan keeps legs `openRepoTools-spec`/`-code` and visibility `public` (#192 `71b05cb` `adoption-plan.yaml`:39, :47–49, per 6072724043). Both names return 404 at 13:34:01Z; name availability remains a Gate C recheck. | no |
| 2 (:132) | Inspect prerequisite availability: `git-filter-repo` (tasks.md:33–34; spec.md:116–117) | IN PROGRESS (rehearsal writer) | **EXISTS.** ar7:23–27 on main covers 2.47.0, wheel `2cd04929…ad83` and a private venv "for this rehearsal only" (receipt `adopter-fix-20261007-iM20tv`). ar8:26–34 at rehearsal-c `1a26463` records the same wheel, a `--without-pip` venv and a `--no-index` install (receipt `adopter-fix-20261008-1HztL0`). 6072724043 (i) found both setup logs in the receipt. No source read names who approved the private-venv path; #186's first act 3 specifies it. | yes |
| 3 (:133) | Regenerate `adoption-plan.yaml` for the reviewed rehearsal source, keeping the reasoned overrides (tasks.md:34–35) | IN PROGRESS | **EXISTS (run C's plan unlanded; landing in progress by lane 3 on Brett's word).** Main carries run B's plan (source `e43b243`, 100 files; #189, review 5464425616). Run C's plan is on rehearsal-c `1a26463` and #192 `71b05cb`: source `837928a`, 120 files, 92 commits, all 22 resolutions reapplied verbatim (ar8:53–57). 6072724043 (iv) PASS; review 5464893559 LAND. #192 has `ready` since 13:42:03Z and is open at 13:48:31Z. | yes |
| 4 (:134) | Standard `check` passes and records every path, with no unapproved drop (tasks.md:35–36) | IN PROGRESS | **EXISTS.** Run C's `check` printed `plan ok`, exit 0, with 0 of 120 dropped (ar8:61–62, :73–79; receipt `runC-check.log`, per 6072724043 (i)–(iii)). Lane 2's own cover check found 0 uncovered and 0 double-covered. `check` reads the clone's local `main`, so it reports `plan-stale` (exit 1) against main `63810dd` and passes with `main` at `837928a` (6072724043 (ii); 6072771795 (3); #193 item 10). | yes |
| 5 (:135) | Bounded amendment folders go to code; full proposals and Speckit go to spec (tasks.md:36–38) | IN PROGRESS | **EXISTS.** In #192's plan, `docs/` (:183–184), `ideation/` (:191–192), `openspec/` (:308–309) and `specs/` (:355–356) go to spec. `git ls-tree -r --name-only 837928a \| grep -c '^features/'` prints 0, as at `63810dd`, so there is no amendment folder to classify. | yes |
| 6 (:136) | Record no amendment paths when none exist (tasks.md:39–40) | IN PROGRESS (Gate A writer) | **EXISTS.** On main, `inventory.json` `refreshed.amendment_path_observations` (from :1501) lists every October 7 head with empty `bounded_amendment_paths` and `working_bounded_amendment_paths`. ar7:69–70: "No bounded `features/<NNN>/openspec/` amendment paths exist, so none are recorded". Run C's source has no per-head entry of its own; its `features/` count is 0 (line 5). | yes |

### T004: isolated clone and local bare-remote rehearsal

| # (ckl row) | Requirement | 2026-10-07 | Now | Changed |
| --- | --- | --- | --- | --- |
| 7 (:142) | A clean isolated source clone with no linked worktrees (tasks.md:44–45) | IN PROGRESS | **EXISTS.** ar7:32–36 covers runs A and B. ar8:36–38 covers run C: "a fresh `--single-branch` clone of main, with one worktree and no linked worktrees". Receipts: iM20tv and 1HztL0. Lane 2's verifications 6036838832 and 6072724043 each pass all six checks. | yes |
| 8 (:143) | Rehearse against temporary local bare remotes, with no real GitHub creation (tasks.md:45–46; plan.md:107–108) | IN PROGRESS | **EXISTS.** `execute --local-remote-dir … --work-dir … --yes` exited 0 in run A (ar7:78–79), run B (ar7:134–135) and run C (ar8:70–71). All three ran with `GIT_ALLOW_PROTOCOL=file`, and the shims logged 0 calls. | yes |
| 9 (:144) | Source identity/history and path/blob accounting (tasks.md:46–47) | IN PROGRESS | **EXISTS.** Run C: 65/49/6/0 of 120. The independent path/mode/type/oid comparison found zero missing, duplicate or misplaced owners. Legs: spec `593250d` (35 kept), code `73b04d6` (88 kept); split `69b8924` (ar8:73–97). Runs A/B: 45/49/6/0 of 100 (ar7:81–155). 6072724043 (i) and (iii) PASS; 6072771795 found one owner per path. | yes |
| 10 (:145) | Recoverability without real GitHub creation (tasks.md:46–47; adopter-blocker.md:58–59) | NOBODY | **EXISTS.** ar7:122–125 (run A): the source clone's HEAD, status, refs, config and worktree list are unchanged apart from the one documented `adopt/three-repo-shape` ref, and "The live checkout gained no `adopt/` ref". ar7:167–168 records the same for run B. ar8:107–109 (run C): that ref and both leg remotes are kept read-only as T006–T010's input. gab:208–218 finds run C's tree listing unchanged. Runs A/B's disposable legs were lost to the 2026-10-08 restart (6068861167). | yes |

### T005: nested dependency and pin

| # (ckl row) | Requirement | 2026-10-07 | Now | Changed |
| --- | --- | --- | --- | --- |
| 11 (:151) | Record the standard tooling's refusal (tasks.md:50–51) | EXISTS on ff6f6a7 | **EXISTS** on main: adopter-blocker.md:15–35, byte-identical to `ff6f6a7`. | no |
| 12 (:152) | Resolve upstream, with regression coverage (tasks.md:51; adopter-blocker.md:61–65) | EXISTS, candidate only | **EXISTS, candidate only:** adopter-rehearsal.md:15–37 on main. No regression record at the merged `7f84ca4` was found in these reads. Runs A, B and C ran the populated existing submodule end to end at `7f84ca4` (line 14). That is rehearsal evidence, not the regression set adopter-blocker.md:61–65 names. | no |
| 13 (:153) | A tested pin bump (tasks.md:51) | IN PROGRESS (#188) | **EXISTS.** #188 (head `e43b243`) merged 2026-10-08T20:51:37Z as main `837928a`, with gitlink `7f84ca4` and `tree_sha256` `3be52767…`. 6068861167 records the squash and its byte-identical proof. #188's own check rollup shows every job SUCCESS, with `tests-macos` under `ready` at 2026-10-07T13:10:53Z. Review 5440809537: LAND. | yes |
| 14 (:154) | Exercise the existing nested submodule path and the original `.gitmodules` (tasks.md:48–49) | IN PROGRESS | **EXISTS.** The mount step passed at `7f84ca4` in runs A, B and C. Code holds the source's original `.gitmodules` blob `8043147a`; the assembly's new one is a different blob (ar7:101–103, :166–167). In run C the gitlink has exactly one owner, code (ar8:84–85). | yes |
| 15 (:155) | Pin integrity; gitlink, pin and registration stay coupled (tasks.md:49–50) | IN PROGRESS | **EXISTS.** In run C, code's nested checkout at `7f84ca4` matches code's contract. The pinned checkout's own `repo_shape.py` recomputes `3be52767…` (ar8:101–105). 6072724043 (v) reproduced the digest by two methods; the receipt's `runC-nested-pin.log` reads `-> MATCH` twice. | yes |
| 16 (:156) | Recursive bootstrap (tasks.md:49) | IN PROGRESS | **EXISTS.** Run C: the recursive clone, `bootstrap.py` (`bootstrap ok`) and the three validators passed, and the trees were clean afterwards (ar8:99–101). 6072724043 (i): validators exit 0 ×3, porcelain empty ×4. | yes |

### T006: root collisions, leg guidance, workflow roots

| # (ckl row) | Requirement | 2026-10-07 | Now | Changed |
| --- | --- | --- | --- | --- |
| 17 (:166) | Root collisions and leg guidance in reviewable patches (tasks.md:53–54) | NOBODY | **EXISTS (on #192, unlanded; landing in progress by lane 3 on Brett's word).** rg:61–81 at root-guidance `041a273`, also in #192 `71b05cb`: 5 root collisions (AGENTS.md, CLAUDE.md, README.md, .gitignore, .gitattributes), with the original guidance kept. Five patches are under `patches/t006/`. Review 5464893559 LAND: all five rebuild to their exact commits, and bootstrap plus `make validate` pass (6072771795). No private receipt is cited for T006 (gab:280–281; #193 item 11). The deletion of the three unpinned `shape/*.md` files is left to T014's reviewer (rg:76, :394). | yes |
| 18 (:167) | Bootstrap the selected root workflow after manifest and legs exist (tasks.md:54–55) | NOBODY | **EXISTS (document only; on #192, unlanded; landing in progress by lane 3 on Brett's word).** rg:314: `setup-openspeckit --shape on …` exited 0 in a disposable copy, line 1 unchanged and `/worktrees/` unchanged. 6072771795 and #193 item 11 note that this row "exist[s] only in the document". | yes |
| 19 (:168) | First-line guidance, relative paths, actual `.specify`, paired selection, no secrets (tasks.md:55–56) | NOBODY | **EXISTS (on #192, unlanded; landing in progress by lane 3 on Brett's word).** rg:85–86: AGENTS.md line 1 is `7f84ca4`'s shape pointer. rg:104–140: the relative-path repairs. rg:315–316: paired selection exits 0 twice, and `check-prerequisites.sh` resolves the feature directory. rg:347–361: no `.specify/`, managed block or machine configuration is committed. rg:333–338 reads `.specify/` from today's shared checkout, not from the Gate A capture that the checklist's evidence column names. | yes |
| 20 (:169) | Provenance correspondence and cross-leg link repair (plan.md:118–121; FR-014) | NOBODY | **EXISTS (on #192, unlanded; landing in progress by lane 3 on Brett's word).** rg:214–299: 35 of 35 spec commits match their originals blob for blob, and all 47 cited openRepoTools commits resolve in the assembly. rg:104–140: 32 repaired links. rg:175–212: the references left unrepaired, each with its owner (T017, lane 3, T007, T009/T010). | yes |
| 21 (:170) | Explicit spec/amendment roots, local-root precedence, store selection (tasks.md:57–58) | NOBODY | **EXISTS (document only; on #192, unlanded; landing in progress by lane 3 on Brett's word).** rg:315–322: the selected root and branch per operation. A spec worktree resolves `source: nearest` without `--store` (the local root wins) and `source: store` with it. rg:327–329 records that the `openspec` first on PATH (1.2.0) has no `--store`, so the checks used the system `openspec` 1.6.0. #193 item 11 applies. | yes |
| 22 (:171) | Per-workstation protocol and command distribution through workBenches delivery (tasks.md:59–61) | NOBODY | **NOBODY.** rg:363–387 records Eagle only: the installed protocol files carry "Triad Feature Amendments", sha256 `f9dd6464…` and `bbbc2b2c…`. It says "Nothing here speaks for any other workstation" and "Lane 2 is reading that side" (:387). No writer of lane 2 (6081924537), lane 3 (brett-wip `6266a03d4`) or lane 1 (brett-wip `41e1fc262`) holds it. | no |

### T007: installer entry point

| # (ckl row) | Requirement | 2026-10-07 | Now | Changed |
| --- | --- | --- | --- | --- |
| 23 (:177) | Installer/topology design (plan.md:148) | EXISTS on ff6f6a7 | **EXISTS** on main: installer-design.md:1–97, byte-identical. | no |
| 24 (:178) | A current-source inventory of `INSTALLABLES`, lists, destinations, consumers (installer-design.md:4–5, :61–65) | EXISTS on reads @ ae70dc556 | **EXISTS** on main `63810dd` (#189), at consumer-reads-2026-10-07.md:239–243 and :245. The checklist's cites :235–239 and :241 are four lines off on main. inst:168 at installer `51993a4` records "17 commands, 23 payload files, 29 placed files, 31 artifacts". | no |
| 25 (:179) | The assembly entry point and payload-source resolution, as reviewed patches with resulting commits (tasks.md:65–66; plan.md:125–126) | NOBODY | **IN PROGRESS by lane 1's #191 fix-cycle writer and lane 3's #191-delta + T007-patch review writer** (brett-wip `41e1fc262`, `6266a03d4`). The entry point is `patches/t007-assembly-entry-point.patch` (sha256 `361c037d…`; commit `8ed83b7`, tree `79db0a4` on split `69b8924`) at installer `51993a4` (inst:60–111). The code side is #191, now `13cc752`. Reviews: DO NOT LAND on `2411f40` (5464963807, 5465121368); none at `13cc752`; none of the T007 patch. | yes |
| 26 (:180) | gh/raw one-liners resolve one code pin with no developer checkout (tasks.md:67–68) | NOBODY | **IN PROGRESS by lane 2 (T008 re-run on #191 `13cc752`, 6081924537 item 1); result to follow on #186.** At `2411f40`, row 1 passed: 29/29 byte-exact, and the composed install asks `commits/main` once and fetches the payload from the pinned code commit (6073209094). inst:88–106 records the contract and a row-3 transcript with 0 network calls. | yes |

### T008: compatibility matrix

| # (ckl row) | Requirement | 2026-10-07 | Now | Changed |
| --- | --- | --- | --- | --- |
| 27 (:186) | The 15-row matrix, measured (tasks.md:69–71) | NOBODY | **IN PROGRESS by lane 2 (T008 re-run); result to follow on #186.** At `2411f40`, all 15 rows met their required observation (6073209094), and #191's module ran 90 passed / 0 skipped in composed strict mode (6073234714). The head moved to `13cc752` at 02:42:54Z. | yes |
| 28 (:187) | Names, counts, destinations and modes, hooks, receipts and all-or-none unchanged (tasks.md:71–72) | NOBODY | **IN PROGRESS by lane 2 (T008 re-run); result to follow on #186.** At `2411f40`: names identical; 47/47 installs placed 29 byte-identical files; 69/69 refusals placed nothing; four behaviour changes against main (6073209094). Review 5464963807 found the offline `--install` byte-identical to main's. | yes |

### T009: explicit roots in fixtures and hygiene checks

| # (ckl row) | Requirement | 2026-10-07 | Now | Changed |
| --- | --- | --- | --- | --- |
| 29 (:193) | Separate code/spec/assembly/dependency roots in fixtures and hygiene consumers, as reviewed patches (tasks.md:73–74) | NOBODY | **EXISTS (on #190, unlanded; landing in progress by lane 3 on Brett's word).** #190 `dbc6837` touches `tests/` only. It has LAND reviews 5464931249 and 5464938427, carries `ready`, and every check is green. Lane 3's finding (1), an `ln_doc` abort under `set -u` in a code leg with no spec root, is fixed on `b50f197`, not in #190 (6073063804 item 1; #193 item 1). Lane 1's handoff assigns a writer to fast-forward `b50f197` onto #190 (brett-wip `41e1fc262`). | yes |
| 30 (:194) | The upstream pin checks run against the code Git identity (tasks.md:74–75) | NOBODY | **EXISTS.** 6072319462: all 14 `test_upstream_pin.py` tests passed standalone in code leg `73b04d6`, with nothing skipped for a missing submodule. trc:37–59 (M1, M2): with `-k '…upstream_pin…'`, 350 passed and 17 failed (all hygiene `FileNotFoundError`), mounted and standalone alike; "tests/test_upstream_pin.py already read the code leg's own gitlink and pin". Both records ran `tests/run.sh`'s own pytest line under `flock` where the wrapper's census never reached zero (trc:310–317; 6069614034). preparation.md:99 reads "Do not bypass the wrapper to obtain a pass". | yes |
| 31 (:195) | Required composed checks cannot silently skip an absent spec or dependency context (tasks.md:75–76) | NOBODY | **EXISTS (on #190, unlanded; landing in progress by lane 3 on Brett's word).** In #190's composed mode (`OPENREPOTOOLS_COMPOSED=1`), the session is refused (exit 4) when a root or the dependency is absent (trc:117–131). P2 exits 4 with no spec leg; P4 keeps today's 12 dependency skips (trc:253–257, :297–298). Two related gaps are deferred: the conftest does not read the pins' `commit:` (trc:133–146; #193 item 4), and the paired layout is not discovered (#193 item 5). | yes |

### T010: CI and composed acceptance

| # (ckl row) | Requirement | 2026-10-07 | Now | Changed |
| --- | --- | --- | --- | --- |
| 32 (:201) | Code-leg CI and root exact-pin integration patches, reviewed (tasks.md:77–78) | NOBODY | **IN PROGRESS by lane 3's `b50f197`/`7144eef`/T010 review writer** (brett-wip `6266a03d4`). Lane 1's #192 fold writer is also folding the ci branch into #192 (brett-wip `41e1fc262`). The two patches are at ci `d28e2cc` (trc:200–232), and gab:296–297 re-applied both. No review of them is recorded. | yes |
| 33 (:202) | Keep every current job, the platform policies, the Bash 3.2 parse and the `tests/run.sh` lock (tasks.md:78–79) | NOBODY | **EXISTS.** trc:202–212: "The six jobs and their trigger policy are kept exactly". trc:301–306 records a structure check by `check_workflows.py`; `actionlint` was not rerun after the bench restart. The code-leg patch at `d28e2cc` removes no job and no assertion. Its two `-` lines are rewritten in place: `-q` becomes `-q -rs`, and one comment line is extended. | yes |
| 34 (:203) | The exact composed state passes the required checks and the matrix locally (tasks.md:80–81) | NOBODY | **IN PROGRESS by lane 1's r2 candidate writer** (brett-wip `41e1fc262`; relay). It has run the three suites since 13:33Z on r2: code `4dbcf6c`, spec `9e1d006`, assembly `5d92962`. Lane 2's writer 4 reproduces r2's trees and checks the composed refusal contract and the install; its result follows on #186. It found that lane 1's recorded candidate (r1, `935f53f`) rebuilds offline with code and spec trees equal to the record, and the assembly tree equal once lane 1's leg ids are substituted (relay). cand at `935f53f` builds assembly `3bd95a7`, spec `9e1d006` and code `f0af7d9` (cand:51–67). Bootstrap, `make validate` and `composed.yml`'s steps exit 0 (cand:104–112), and "No suite run has finished" (cand:164–176). 6082068576 finds that it REPRODUCES. It predicts a composed failure of `test_agents_md_names_the_pin_rules` (T006 × #190; #193 item 14) and a standalone abort on `ln_doc`. | yes |
| 35 (:204) | The same clause, on GitHub-hosted runners (`tests-windows`, `parse-macos`, `tests-macos`) | BLOCKED (inferred) | **BLOCKED on real leg repositories (Gate C).** Lane 1's records now say so: "Neither patch can run on GitHub until the legs exist (Gate C)" (trc:230). They file it under "What remains for T015" (trc:321–322; 6073063804). | no |

### T011: restore/rollback rehearsal and publication

| # (ckl row) | Requirement | 2026-10-07 | Now | Changed |
| --- | --- | --- | --- | --- |
| 36 (:210) | Rehearse restoration and rollback of the local candidate and the installed payload (tasks.md:82–83) | NOBODY | **IN PROGRESS by lane 2 (the T011 verification against `rollback-20261009-ILvoVC`, and the tooling-v2 verification; 6081924537 items 2–3); results to follow on #186.** gab:25–94: source restore 90 PASS; a dirty tree rebuilds 0/3 by the capture as written, 3/3 with the diffs. gab:96–182: four disposable homes; (c2) restores, while (c1) leaves `installed.tsv` stale. The receipt is at brett-wip `56f1e7c4` and `076062af`. cand:157–160 repeats (c2) at the candidate's commits. Tooling v2 is brett-wip `99eed358` (6073036070). 6082139424 judges `fa44d75` DO NOT LAND as a future PR; its finding 11 says the hook rollback was never exercised. | yes |
| 37 (:211) | User work, jobs and claims survive; no force push, destructive reset or pointer rewrite (tasks.md:83–85) | NOBODY | **IN PROGRESS by lane 2 (T011 verification); result to follow on #186.** gab:184–256: 18 write groups, with 0 in a real repository, 0 in the real home and 0 in the register. Real surfaces were unchanged 00:42:08Z–00:53:06Z. Lane 1's row and its claim on #186 are unchanged. 6082139424 finding 19: jobs get only "no script … kills a process". | yes |
| 38 (:212) | Publish Gate A/B evidence: the Gate A part (tasks.md:85) | IN PROGRESS (Gate A writer) | **EXISTS** on main `63810dd` (#189, review 5464425616): pres:1–111 and `inventory.json` `refreshed` (observed 2026-10-07T10:09:03Z). The receipt is `prep-20261007T100559Z` at brett-wip `f0ea2df7`. The bundle stays host-local. | yes |
| 39 (:213) | Publish Gate A/B evidence: the Gate B rehearsal part | IN PROGRESS | **EXISTS.** Runs A/B: ar7 on main (#189), receipt iM20tv, verification 6036838832. Run C: ar8 on #192 `71b05cb` (unlanded; landing in progress by lane 3 on Brett's word), receipt 1HztL0, verification 6072724043, review 5464893559 LAND. | yes |
| 40 (:214) | The follow-up patch and commit inventory (tasks.md:85; plan.md:125–126) | NOBODY | **IN PROGRESS by lane 2 (T011 verification); result to follow on #186.** gab:283–316 lists 7 recorded patches (T006 5, T010 2), each re-applied onto its rehearsed base with the recorded trees. It reads "T007's entry point: 0 recorded" (:306) and "No test ran on the stacked candidate" (:316). The T007 patch is on origin at installer `51993a4` and is absent from the inventory. 6082139424 findings 15 and 18 call the inventory stale and incomplete. | yes |

### Cross-cutting conditions

| # (ckl row) | Requirement | 2026-10-07 | Now | Changed |
| --- | --- | --- | --- | --- |
| 41 (:220) | Repeat into fresh local remotes after repinning (plan.md:146–148; adopter-blocker.md:71–73) | IN PROGRESS | **EXISTS.** Run B ran at the repin candidate `e43b243` (ar7:127–168). Run C ran at main `837928a` after the repin landed (ar8:68–109). Both used tool `7f84ca4` on openRepoShape main, each into fresh disposable local remotes. | yes |
| 42 (:221) | Never the live consumer as `--source`; no `adopt/three-repo-shape` on the live repository or the remote (adopter-blocker.md:52–54) | IN PROGRESS | **EXISTS.** Each source was a fresh single-branch clone (ar7:32–33; ar8:36–37). At 13:34:01Z, `ls-remote 'refs/heads/adopt/*'` lists nothing, and the repository's `refs/heads/adopt/` and `refs/remotes/origin/adopt/` are empty. | yes |
| 43 (:222) | No in-place submodule patch; digests never adjusted (plan.md:113–114; tasks.md:51–52) | IN PROGRESS (#188) | **EXISTS.** #188 landed as `837928a` (6068861167), and its check rollup shows every job SUCCESS, `tests-macos` included. `3be52767…` was recomputed independently by lane 3 (6035767825) and by lane 2 by two methods (6036838832 (v); 6072724043 (v)). Review 5440809537: LAND. | yes |
| 44 (:223) | No real repository for a test; transport limited; leg names looked up read-only (plan.md:253; #186 rules) | IN PROGRESS | **EXISTS.** Runs A, B and C used `GIT_ALLOW_PROTOCOL=file`, and the shims logged 0 calls (ar7:37–41; ar8:39–41). The T006, T011 and candidate records each state the same of their own runs (rg:26–29; gab:98–104; cand:46–47). Both leg names return 404 at 13:34:01Z. | yes |
| 45 (:224) | A reviewed preliminary inventory, mapping and prerequisites before provisional rehearsal (tasks.md:159–161) | IN PROGRESS (Gate A writer) | **EXISTS.** `inventory.json` was refreshed (observed 2026-10-07T10:09:03Z, source `c4864ac`) and is on main via #189, review 5464425616 LAND. Lines 2–6 are EXISTS above. | yes |
| 46 (:225) | A review record for each T006–T010 patch: reviewer, verdict, commit (plan.md:140–141) | NOBODY | **IN PROGRESS by lane 3's two review writers and lane 1's reviewer** (brett-wip `6266a03d4`, `41e1fc262`). Recorded so far: T006 has 5464893559 LAND on `71b05cb`. T009 (#190) has 5464931249 and 5464938427, both LAND on `dbc6837`. T007/T008's code side (#191) has 5464963807 and 5465121368, both DO NOT LAND on `2411f40`, and nothing at `13cc752`. The T007 entry-point patch and the two T010 patches have no review. | yes |

## Counts

| Status | 2026-10-07 | 2026-10-09 |
| --- | ---: | ---: |
| EXISTS | 4 | 33 |
| DECIDED | 1 | 1 |
| IN PROGRESS | 19 | 10 |
| NOBODY | 21 | 1 |
| BLOCKED | 1 | 1 |
| **Total** | **46** | **46** |

- **Changed: 39 lines.**
  - All 19 lines IN PROGRESS on 2026-10-07 are now EXISTS: 2–9, 13–16, 38, 39 and
    41–45.
  - Of the 21 NOBODY lines, 10 are now EXISTS (10, 17–21, 29–31, 33), 10 are IN
    PROGRESS (25–28, 32, 34, 36, 37, 40, 46) and 1 is still NOBODY (22).
- **Unchanged: 7 lines.** These are 1 (DECIDED), 11, 12, 23 and 24 (EXISTS), 22
  (NOBODY) and 35 (BLOCKED).

The 10 IN PROGRESS lines are held as follows; some have more than one holder:
- **lane 2:** 26, 27, 28, 34 (reproduction only), 36, 37 and 40 (7 lines);
- **lane 3:** 25, 32 and 46 (3 lines);
- **lane 1:** 25, 32, 34 (the r2 suites) and 46 (4 lines).

## What still stands between here and Gate B

**NOBODY and BLOCKED lines:**
- **22 (NOBODY).** No target workstation's installed protocol and command
  distribution has been checked through workBenches delivery except Eagle's (rg:374–377).
  No writer of any lane holds it.
- **35 (BLOCKED).** T010's hosted-runner verification (`tests-windows`, `parse-macos`,
  `tests-macos`) of the rehearsed commits waits on real leg repositories, which Gate C
  governs. Lane 1's records file it under T015.

The 10 IN PROGRESS lines above are the rest of what is open. They are verification,
review and composed-run work held by named writers.

**Lane 1's T011 list** (#186 6072247322, 2026-10-09T01:14:55Z), verbatim:

> - **Gate B still lacks:**
>   - T007's entry point;
>   - a composed suite run of the whole follow-up stack;
>   - reviews of the T006 and T010 patches (#190 and #191 are in progress);
>   - the run C mapping landing (#192);
>   - Gate A's final capture.
>
>   Gate C is Brett Heap's.

**Item by item against this walk:**

| Lane 1's item | Walk lines | Agree or differ |
| --- | --- | --- |
| T007's entry point | 25, 40, 46 | **Differ on the state.** The patch has been on origin at installer `51993a4` since 01:21:15Z (6082139424 finding 15), seven minutes after T011's record was pushed. What stands is its review (46), #191 at `13cc752` (25), and its place in the T011 inventory (40). |
| A composed suite run of the whole follow-up stack | 34 | **Agree.** No suite run of a candidate had finished by the cutoff. Lane 1's r2 writer runs the three suites; lane 2 reproduces r2. |
| Reviews of the T006 and T010 patches | 46 (also 25, 29, 32) | **Differ in part.** T006's five patches have a LAND review (5464893559, 02:01:33Z). #190 has two LANDs. #191 had two DO NOT LANDs at `2411f40`, and `13cc752` is unreviewed. **Agree on T010:** its two patches have no review yet. |
| The run C mapping landing (#192) | 3, 39 (EXISTS) | **Differ.** No checklist line requires a landing. Line 3 asks for the regeneration, which exists and is reviewed; line 39 asks for publication, which exists on #192. The landing is lane 1's. #192 has `ready` since 13:42:03Z. |
| Gate A's final capture | none | **Differ.** The checklist places Gate A completion "Outside Gate B" (ckl:291–293). Tooling v2 exists (brett-wip `99eed358`), and lane 2 is verifying it. The capture itself waits on the owner-coordinated freeze (6073036070; pres:108–111). |

**Lines in this walk that the list does not name:**
- 22 (NOBODY) and 35 (BLOCKED). Lane 1 places 35 under T015.
- 26–28: the matrix at #191's current head.
- 36, 37 and 40: verification of T011's own record. 6082139424 judges that record DO
  NOT LAND as a future PR, saying §§4–7 are stale.

## Facts noticed while walking

1. **Dangling receipt.** cand:10 names the private receipt `candidate-20261009-JR8YyA`
   in brett-wip `migration/openRepoTools/`. At brett-wip `origin/main` (read 13:32:56Z
   and 13:43:18Z), that directory holds `adopter-fix-20261007-iM20tv`,
   `adopter-fix-20261008-1HztL0`, `prep-20261007T100559Z`, `rollback-20261009-ILvoVC`
   and `tools-20261009`. The candidate receipt is not there. 6082068576 matched the id
   only against lane 1's scratch. Lane 2's writer 4 also reports it is not yet in brett-wip
   (relay).
2. **Dangling citation.** A reply on #190 (review 5470865276, 13:42:33Z) and #193's
   body both cite Brett Heap's word "land 190 and 192" (2026-10-09). The reply says
   "as lane 1 recorded on #186". No such comment was on #186 at 13:48:37Z. The relay
   places the word in lane 3's window.
3. **#193 describes a future that had not happened at the cutoff.** #193 (13:42:32Z)
   speaks of "Follow-ups deferred when #190 and #192 landed". At 13:48:31Z both were
   OPEN and main was `63810dd`.
4. **Lane 1's plan for `b50f197` disagrees with #193.** Lane 1's handoff (brett-wip
   `41e1fc262`, 13:40:04Z) assigns a writer to "fast-forward b50f197 onto #190". #193
   item 1 (13:42:32Z) says `b50f197` "now needs its own PR onto main".
5. **Two lanes announced the candidate's suites.** Lane 2 announced them at 13:31:22Z
   (6081924537 item 4). Lane 1's handoff (13:40:04Z) names its own candidate rebuild
   with three suites. Lane 2's writer then stopped its suites; lane 1's r2 writer runs
   them (relay). Lane 1's handoff also names a read-only Gate B checklist walk of its
   own, with private output.
6. **T011's record is stale on several points.** gab, written 00:36Z–01:1xZ, says no
   `004-migrate-to-triad-installer` is on origin (gab:122–124, :298). It says "T007's
   entry point: 0 recorded" (:306), "Lane 3's T006 review is not posted" (:269), and
   that lane 2's discovery "has not reported" (:353). Each was true when written. Later
   records contradict each one (6082139424 finding 15). Lane 3's #191 comment
   (6072887742, 02:16:57Z) also said the installer branch "is not on origin", although
   6082139424 dates its creation at 01:21:15Z.
7. **ci-branch citations.** gab §4/§5 and cand:27 cite ci at `cc7c7a1`; the branch is
   at `d28e2cc`. `git diff --stat cc7c7a1 d28e2cc` changes only
   `test-roots-and-ci-2026-10-08.md`, so both T010 patches are the same bytes.
8. **The candidate's #191 input.** cand:30 takes #191 at `2411f40`, the head both
   reviews marked DO NOT LAND. The PR is now at `13cc752`. inst:5 also cites
   `2411f40`, and inst:150 and :152 leave two runs "to be recorded on resume". Neither
   is recorded at `51993a4`.
9. **The checklist's own cites.** The row-24 cites into consumer-reads (:235–239, :241)
   are four lines off on main (:239–243, :245), as 6071777207 noted. The checklist's
   `adoption-plan.yaml` cites are to `ff6f6a7`'s October 4 plan (ckl:52). Main now
   carries run B's plan, so those line numbers do not hold on main.
10. **Mapping on main.** Main's `adoption-plan.yaml:25` names source `e43b243`. Run C's
    plan, source `837928a`, is on #192. 6082139424 finding 9 adds that `e43b243`
    survives on origin only as `refs/pull/188/head`.
11. **Counting inside rg.**
    - rg:180 says "23 mentions in 9 files", but its own list adds up to 26 in 11
      (4+4+4+3+3+2+2+1+1+1+1); rg:411 repeats 23.
    - rg:397–398 counts 17 front-door failures (16 hygiene, 1 command). trc:39–53
      counts 17 in the hygiene module alone, and 6072319462 lists 18 by test id.
    - #193 item 9 records both.
12. **ensurepip.** ar8:26–29 says the rebuilt bench has no `ensurepip`. Lane 2
    (6072333212, 6072724043) and lane 3 (6072771795) read it as present. #193 item 12
    records the contradiction. The refusal itself is in the receipt.
13. **`openspec validate migrate-to-triad --strict` gives two results.** Run C's comment
    (6068938765) reports a failure with openspec 1.2.0 on `837928a`: "must contain SHALL
    or MUST". rg:318–319 reports exit 0 in the spec leg with openspec 1.6.0 (rg:327).
    Lane 2's writer 4 reports exit 0 in the spec leg with openspec 1.13.1, so the
    1.2.0 failure does not reproduce there (relay). The CLI version is the visible
    difference (inferred cause).
14. **Who reviewed lane 1's PRs.** Review 5464938427 (LAND on #190) and review
    5465121368 (DO NOT LAND on #191) are both headed "Independent adversarial review —
    lane openRepoTools-1". Both PRs come from lane 1's writers (6073063804; inst:9), and
    trc:338 calls the #190 review "lane 1's reviewer".
15. **Landing order.** trc:113–115 says #192 should land with or before #190, because
    #190's dated cap entries cite `root-guidance-2026-10-08.md` on #192's branch. Both
    PRs carry `ready` at the cutoff.
16. **A host path in a public file.** inst:13 names a host-absolute path into lane 1's
    private prep area. plan.md:39–40 keeps machine paths out of the feature's public
    files. The other five evidence documents' diffs carry none (grep count 0 each).
17. **#192's readiness.** #192 received `ready` at 13:42:03Z with its head still
    `71b05cb`. Lane 3's six edits recommended "before `ready`" (6072771795) are
    deferred to #193 item 13.

This record authorizes no conversion, repository creation, merge, default-branch move or
lane rebinding.
