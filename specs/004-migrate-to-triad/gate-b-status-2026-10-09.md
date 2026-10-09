# Gate B status walk and the Gate C open questions — October 9, 2026

**Checked:** 2026-10-09T20:30Z–20:55Z, refreshed 21:56Z–22:15Z (UTC). The git state is a
`fetch --all --prune` at 22:07:06Z. The GitHub reads were made between 20:32Z and 20:41Z and again
between 21:58Z and 22:10Z. #186's comments were read through 22:06:49Z. Anything later is not in
this walk.
**By:** lane openRepoTools-1's reviewer, under [#186](https://github.com/opensoft/openRepoTools/issues/186).
It ran read-only everywhere except this file and its own scratch. A first, unpublished pass was
made at 13:27Z–13:50Z; section 1 says which statuses moved since.
**Walks:** the 46 lines of [gate-b-checklist.md](gate-b-checklist.md) (main, from #189).
**Cross-check:** lane openRepoTools-2's independent walk, which has the same path as this file,
`specs/004-migrate-to-triad/gate-b-status-2026-10-09.md`, on `004-migrate-to-triad-reads` @
`a7a8e00` (reads to 13:48:37Z). Section 2 reconciles the two line by line, and also answers lane
2's review of this walk's first pass (#186 6088829392). Lane 2's copy stays on its branch as a
cross-check and goes into no PR.

This walk records facts. It approves nothing and changes no status in [tasks.md](tasks.md), where
all 19 tasks stay open. Gate C stays Brett Heap's explicit approval naming the actual revisions
(plan.md:160–163). Machine paths are left out (plan.md:38–39). Private receipts are named by id
only, and their contents are not quoted. Logs held only in lane 1's private scratch are cited
through the #186 comment that reported them.

## Refs read

Paths are under `specs/004-migrate-to-triad/` unless they start with `openspec/`.

| Short | Ref | Head read |
| --- | --- | --- |
| M | `main` | `f87fd5a` (#190), on `1abee1d` (#192), on `63810dd` (#189) |
| CI | `004-migrate-to-triad-ci` | `d28e2cc` |
| IN | `004-migrate-to-triad-installer` | `51993a4` |
| RB | `004-migrate-to-triad-rollback` | `fa44d75` |
| RR | `004-migrate-to-triad-rollback-refresh` (lane 2's slice A) | `2e7e55e` (`c1283b5`, `612ea94`, `2e7e55e` on RB) |
| EF | `004-migrate-to-triad-evidence-2-followups` (lane 2's slice B) | `096de93` |
| CA | `004-migrate-to-triad-candidate` | `935f53f` (the r1 build; r2 is not published) |
| T18 | `004-migrate-to-triad-t018` | `63bff08` |
| L2 | `004-migrate-to-triad-reads` | `a7a8e00` |
| #191 | `feat/installer-payload-source-resolution` | `13cc752` |
| FU | `feat/test-roots-followups` (no PR) | `01ccc86` |

Main's planning files (plan, spec, tasks, the capability spec and the change's tasks) are
unchanged since `63810dd`; `git diff --stat 63810dd f87fd5a` over them is empty. Every `plan.md`,
`spec.md` and `tasks.md` line cited below holds on `f87fd5a`.

**Live facts at the check:**
- `gh api repos/opensoft/openRepoTools-spec` and `-code`: HTTP 404 (20:32Z, 21:58Z and 22:08Z). The `gh`
  account is `brettheap`, an active admin of `opensoft`.
- openRepoShape `main` is `22c9fdd`, ahead 6 and behind 0 of the pinned and rehearsed `7f84ca4`:
  `b18cca9`, `21f5c33`, `f25d805`, `bc09bc5`, `4ce9cb0`, `22c9fdd` (question e1).
- `git ls-remote origin 'refs/heads/adopt/*'`: nothing.
- #191 is the only open PR, at `13cc752`. Lane 3's delta review 5471121210 is LAND, with
  conditions. Lane 1's next head was announced (#186 6088714587) and was not on origin at
  22:07Z. Lane 2's T008 matrix at `13cc752` is final (#186 6088812080).
- Lane 2's slices are on origin, both meant for the evidence-3 PR. A is RR: lane 3 reviewed
  `c1283b5` as LAND within evidence-3 (#186 6089982753), and `612ea94` and `2e7e55e` take in its
  notes N1–N9 (6090048356). B is EF `096de93` (6088799627); lane 3's review of it is in progress.
- Lane 3's review of FU and the T010 patches is posted (#186 6089801221, 21:47Z).
- The r2 composed candidate's three suites finished at 18:20:47Z. Lane 2's reading of the logs is
  #186 6087267593; this walk checked the summary lines against the logs. Lane 1's
  classification of them is in progress.
- In progress, so not counted as evidence: the Gate A capture-tool fix (#186 6087232548,
  6087261307; nothing new in brett-wip since `99eed35`, per 6089772323 and 6089982753); lane 2's
  verification of T18 (6089772323).
- Not counted, because its head is not on origin: lane 2's pre-push T008 matrix on lane 1's
  unpushed #191 head and v3 entry-point patch (#186 6090038382). It reports the ancestor-walk
  cases, (c) and (e) fixed, v3 refusing a gitlink that disagrees with the pin, and nine items
  still open. It is a preview of the next head's check.

## Status legend

- **MET**: the evidence named in the checklist's "Evidence that would satisfy it" column exists
  on a pushed ref and, where the line asks for a review, the review is recorded.
- **PARTLY**: evidence exists but is incomplete, unreviewed, measured on a head that has moved,
  or carries an open defect or an open decision.
- **OPEN**: no finished evidence.
- **AFTER-GATE-C**: cannot be met before real legs exist.

Publishing the T006–T011 records on `main` is not itself a checklist line. It is listed among the
blockers in section 5.

## 1. The 46 checklist lines, at 2026-10-09T22:1xZ

| # | Line (short) | Status | Evidence | What remains | Owner |
| --- | --- | --- | --- | --- | --- |
| 1 | Leg names and visibility confirmed (T003, FR-012) | MET | #186 6035767825 ("legs and visibility confirmed"); M:`openspec/changes/migrate-to-triad/adoption-plan.yaml` (legs; `visibility: public`) | Recheck at the Gate C request. 404 is not proof the names are free (preparation.md:53–56) | Brett (given); lane 1 (recheck) |
| 2 | `git-filter-repo` via the approved prerequisite path | PARTLY | M:adopter-rehearsal-2026-10-08.md#Setup; M:adopter-rehearsal-2026-10-07.md#Setup; #186 6072724043 (i) | No record names who approves the private-venv path for the real `execute` (plan.md:105–106, :160–162): question e4. Neither receipt carries the October 4 receipt's "existing bench/system installations were unchanged" (preparation.md:62–63), which the evidence column asks for (lane 2, 6088829392 item 10). The "no ensurepip" cause is withdrawn on EF; the refusal's cause is not established (#193 item 12) | Brett; lane 1 |
| 3 | Plan regenerated for the rehearsal source, overrides kept | MET | M:`openspec/changes/migrate-to-triad/adoption-plan.yaml` (source `837928a`, 22 resolutions); M:adopter-rehearsal-2026-10-08.md#Mapping (T003); #192 review 5464893559; #186 6072724043 (iv) | The final plan is regenerated at the frozen source before the request (question e2). `check` reads the clone's local `main`, so the committed plan is `plan-stale` against any later `main` (#193 item 10; EF:adopter-rehearsal-2026-10-08.md:107–119) | lane 1 |
| 4 | Standard `check` passes, every path, no unapproved drop | MET | M:adopter-rehearsal-2026-10-08.md#Run C (`plan ok`; 120 = 65/49/6/0); #186 6072724043 (ii) | Rerun at the frozen source | lane 1 |
| 5 | Amendment folders to code; full proposals and specs to spec | MET | M plan: `docs/`, `ideation/`, `openspec/`, `specs/` to spec; 0 `features/` paths on `main` | Re-observe at the frozen source | lane 1 |
| 6 | No amendment paths recorded where none exist | MET | M:inventory.json `refreshed.amendment_path_observations` (every head empty) | Re-observe at the Gate A final capture | lane 1 |
| 7 | Clean isolated source clone | MET | M:adopter-rehearsal-2026-10-08.md#Setup; receipt `adopter-fix-20261008-1HztL0`, verified in #186 6072724043 | — | — |
| 8 | Rehearsal into temporary local bare remotes | MET | M run C (`execute` 0, file transport only, 0 shim calls) | — | — |
| 9 | Identity, history and path/blob accounting | MET | M:adopter-rehearsal-2026-10-08.md#Run C; #186 6072724043 (iii); #192 review finding 4 | — | — |
| 10 | Recoverability; source unchanged | MET | M run C; M:adopter-rehearsal-2026-10-07.md#Run A; RB:gate-ab-evidence-2026-10-09.md#1; no `adopt/` ref on origin | — | — |
| 11 | Standard's refusal recorded | MET | M:adopter-blocker.md | — | — |
| 12 | Upstream resolution with regressions | MET | M:adopter-rehearsal.md#Regression evidence (draft `91d5685`: each case adopter-blocker.md:61–65 names); openRepoShape #162's CI at its head `6fa4e07`: `tests`, `tests-windows` and `tests-macos` SUCCESS (2026-10-07T00:57Z–01:06Z); its merge `7f84ca4`: `tests` (`python3 -m pytest tests -q`, `tests/test_adopt_submodules.py` included) SUCCESS at 01:13:26Z | The regression "does not qualify every mixed-registration plan" (adopter-rehearsal.md:30–32); this repository's plan is not one (line 14). openRepoShape `main` has moved 6 commits past `7f84ca4`: question e1. Lane 2 holds PARTLY (section 2) | Brett; openRepoShape owner |
| 13 | Tested consumer pin bump on `main` | MET | M@`837928a` (#188); #186 6068861167 | — | — |
| 14 | Nested submodule; original `.gitmodules` | MET | M runs B and C (code keeps blob `8043147a`; the assembly gets its own) | — | — |
| 15 | Pin integrity, coupled | MET | M run C (`3be52767…` MATCH); #186 6072724043 (v) | — | — |
| 16 | Recursive bootstrap | MET | M run C (`bootstrap ok`, three validators) | — | — |
| 17 | Root collisions and leg guidance as reviewed patches | MET | M:root-guidance-2026-10-08.md#1, #4; M:patches/t006/*; #192 review 5464893559 finding 7 (exact rebuild) | #193 items 8–13, the text fixes: on EF `096de93`, under lane 3's review, for evidence-3. The `shape/*.md` deletion is T014's reviewer's | lane 1 (EF by lane 2) |
| 18 | Shape-aware root bootstrap after the legs exist | PARTLY | M:root-guidance#7; T18:t018-disposable-2026-10-09.md#1 (a second run: `setup-openspeckit --shape on` exit 0, `worktree_root: worktrees`) | Neither run is reviewed, and neither has a receipt: EF now says so plainly (#193 item 11; EF:root-guidance-2026-10-08.md:31–57). Lane 2 is verifying T18 (6089772323). T18 finds the bootstrap leaves the root "dirty" to `resume` (T18 §5 item 1): question e7 | lane 1; Brett |
| 19 | First-line guidance, relative paths, actual `.specify`, paired selection, no secrets | PARTLY | M:root-guidance#2, #3 (both verified by #192 review finding 7), #7, #8; T18 §2 (paired selection from the root, either leg and either worktree; `check-prerequisites.sh` agrees ×5) | `.specify` was read from today's checkout, not from Gate A's captured configuration (lane 2, L2 line 19). The `.specify` posture is undecided (question e7). `SPECIFY_FEATURE` alone gives a branch and directory that disagree (T18 §5 item 8). T18 is unreviewed | lane 1; Brett |
| 20 | Provenance correspondence; link repair without guessed hashes | MET | M:root-guidance#6 (35/35; 47 citations resolve in the assembly), #3; #192 review finding 10 | EF marks "23 mentions in 9 files" as not established (#193 item 9). Feature 004's own pre-split paths are T017's | lane 1 |
| 21 | Explicit roots, local-root precedence, supported store selection | PARTLY | M:root-guidance#7 (store precedence; strict validate in the spec leg); T18 §3 (OpenSpec from each root with 1.2.0 and 1.6.0) | Store precedence rests on the document alone (#193 item 11). T18 shows the root and the code leg pass `validate --all --strict` vacuously, so validation must run in the spec leg (T18 §5 item 7). `--store` needs openspec 1.6.0 or later (question a) | lane 1; workBenches owner |
| 22 | Protocol/command distribution per target workstation through workBenches | PARTLY (no owner) | M:root-guidance#9: Eagle's two installed protocol files carry "Triad Feature Amendments" (sha256 `f9dd6464…`, `bbbc2b2c…`) | Not via workBenches delivery; command and skill digests absent; no other workstation; no target list; no writer holds it (lane 2 read only vendoring, consumer-reads-2026-10-07.md:85–105). Section 2 records lane 2's NOBODY | Brett (names the workstations); workBenches owner; a holder to be named by lane 1 |
| 23 | Installer design | MET | M:installer-design.md | — | — |
| 24 | Installer inventory refreshed | MET | M:consumer-reads-2026-10-07.md#The installer's own assumptions; IN:installer-2026-10-08.md#Lane 2's installer rows (17/23/29/31) | installer-design.md:61–64 still carries `daed209`'s counts | lane 1 |
| 25 | Entry point and payload-source resolution as reviewed patches | PARTLY | IN:patches/t007-assembly-entry-point.patch; #191 @ `13cc752`: LAND with conditions (review 5471121210; delta 8 is the stale PR body, plus `tests-macos` under `ready`) | The next #191 head needs its own check; it was not on origin at 22:07Z. The entry-point patch is CHANGES REQUIRED (5471121210 T3: on the remote path, confirm the gitlink before running the pinned implementation). Not landed | lane 1; lane 3 |
| 26 | One-liners resolve one code pin; no developer checkout | PARTLY | 5471121210 T1–T2 (a disposable assembly at `13cc752`: one code commit, the installed tree byte-identical to a checkout install, local delegation with no fallback); #186 6088812080 (final matrix at `13cc752`) | Rerun at the next head with the T3 fix. On the single layout a ref that moves mid-install mixes versions, as on `main` (6088812080 item 7); the PR body should scope "resolve once" to the adopted layout (5471121210 delta 8). Real one-liners are T015's | lane 2; lane 1 |
| 27 | 15-row compatibility matrix measured | PARTLY | #186 6073209094 and 6073234714 (15/15 at `2411f40`); #186 6088812080 (final at `13cc752`, 337 row logs; F1, F2, (b) and (d) fixed) | Rows 18–22 bear on the next head (6088812080 items 1–6): the layout search walks every ancestor, and a HOME holding `contracts/code-pin.yaml` refuses to reinstall; a missing ref or repository is read as a single repository and never named; a 502 on a probe refuses where `main` installs; the 404 path; garbage at 200 is reported as a moved ref; (c) and (e) remain. Rerun at the next head | lane 2; lane 1 |
| 28 | Names, counts, modes, hooks, receipts, all-or-none unchanged | PARTLY | 5471121210 delta 2 (offline install byte-identical at `13cc752`); #186 6088812080 (210 of 210 refusals placed nothing; 82 of 83 installs 29/29 byte-exact, the exception row 7's deliberate mixed case; 40 of 40 receipts consistent; both hook entries present); #186 6087267593 (the r2 install: 29 files byte-exact) | Rerun at the next head. An adopted `wip init` that refuses still leaves an empty server repository behind (#186 6087232548, its F2 row) | lane 2; lane 1 |
| 29 | Explicit roots in fixtures and hygiene checks | MET | M@`f87fd5a` (#190 at `b50f197`): LAND 5464931249, LAND 5464938427, delta LAND 5471080687; CI green including `tests-macos` | FU @ `01ccc86` (#193 items 2, 6): lane 3 finds it fit for a PR onto `main` after one edit, dropping or re-premising the 340 → 347 assembly cap (6089801221 finding 7). #193 items 3–7 and 15 stay open; item 5, the paired layout, is wanted before Gate C | lane 1; lane 3 |
| 30 | `tests/run.sh -k upstream_pin` inside the rehearsed code leg | MET | #186 6072319462 (all 14 `test_upstream_pin.py` pass in code leg `73b04d6`); CI:test-roots-and-ci-2026-10-08.md#1 | The runs used `tests/run.sh`'s own pytest line under the same lock, not its census (#184) | lane 1 |
| 31 | Composed checks refuse instead of skipping | MET | M@`f87fd5a` (#190); #186 6087267593 (five refusal cases exit 4 on an r2-equivalent); 6089801221 finding 15 | #193 item 4: conftest never reads a pin's `commit:`, closed in CI only by `composed.yml`'s step order (6089801221 finding 13). Item 15 (wording) is confirmed there (finding 14). About forty other conditional skips can still pass a composed run; none fires on ubuntu-latest today (finding 13 (ii)) | lane 1 |
| 32 | Code-leg CI and assembly exact-pin job patches | PARTLY | CI:patches/t010-*.patch; CI:test-roots-and-ci#5–#6; lane 3's review 6089801221 (c): fit for evidence-3, both patches apply to run C and the code-leg patch to `f87fd5a` | `composed.yml` runs the suite through `run.sh`, whose long run root makes #180's two row-stamp assertions fail, so `exact-pins` would be red until #180 is fixed or the job uses a short `TMPDIR` (finding 13 (i), inferred). Both patches need a real author at T014 (finding 13 (iv)). `actionlint` last ran 2026-10-07. SonarCloud and required checks: question e9 | lane 1; lane 3; Brett |
| 33 | Platform policies, Bash 3.2 and serialized locking kept | MET | CI:test-roots-and-ci#5; lane 3's review 6089801221 finding 12: all six jobs keep their names and order, `tests-macos` keeps its `ready` gate verbatim, the triggers, per-job `submodules:`, `parse-macos`'s bash 3.2 file list and the Windows env are unchanged, WSL stays a documentation policy, and locking is as today | The hosted run is line 35. The assembly has no `tests-macos` check, which T015's landing tooling must allow for (finding 12) | lane 1 |
| 34 | Exact composed state passes required checks and the matrix (local) | PARTLY | #186 6087267593: r2 = code `4dbcf6c` (#190 `b50f197`, #191 `13cc752`, T006, T010), spec `9e1d006`, assembly `5d92962`. Composed 5 failed / 1411 passed; standalone 3 failed / 1389 passed / 24 skipped; no dependency 6 failed / 1168 passed / 242 skipped | It does not pass yet. `test_agents_md_names_the_pin_rules` (T006 × #190, #193 item 14) and `test_r14_the_documented_upstream_skip_is_unchanged` (`KeyError: 'reason'`, first seen in r1, unanalysed) need fixes. The lane-helper shell FAILs (row stamps, #180 per 6089801221 finding 13), the `test_run_wrapper` timeouts and the observer timeouts (load, inferred) need classifying. r2 rests on `13cc752`, so the composed record is redone at #191's final head and the other final heads, then published | lane 1 |
| 35 | Hosted-runner part of T010 | AFTER-GATE-C | CI:test-roots-and-ci#5 ("Neither patch can run on GitHub until the legs exist"), #8 | Question d | Brett |
| 36 | Restore/rollback of the candidate and installed payload | PARTLY | RB:gate-ab-evidence-2026-10-09.md#1–#2; lane 2's independent check (#186 6082370012: restore 91 PASS, four homes reproduce); M:candidate record r1 §4 on CA; RR (the record now says the hook rollback is vacuous and the backup holds no `settings.json`; lane 3 LAND at `c1283b5`, 6089982753) | No hook-changing rollback, no restore of the local candidate from preserved artifacts and no post-merge revert/pin-bump rollback is rehearsed (lane 3 6082139424 findings 11 and 19; 6082370012 (iv)). The capture tooling v2 cannot stand as evidence until A1 is fixed (6087261307). RR is not on `main` | lane 1 |
| 37 | Work, jobs and claims survive; no force push, reset or pointer rewrite | PARTLY | RB:gate-ab-evidence#3; #186 6082370012 (verified; 0 non-fast-forward against GitHub); RR §3 | Jobs have no before/after record, only "no script … kills a process" (6082139424 finding 19). No force push is argued for a real rollback, not shown | lane 1 |
| 38 | Publish the Gate A evidence | MET | M:preservation-2026-10-07.md, M:inventory.json (#189); receipt `prep-20261007T100559Z` | Gate A itself stays open (section 5) | lane 1; Brett |
| 39 | Publish the Gate B rehearsal evidence (a receipt in adopter-rehearsal form) | MET | M:adopter-rehearsal-2026-10-07.md (runs A and B, #189) and M:adopter-rehearsal-2026-10-08.md (run C, #192); receipts `adopter-fix-20261007-iM20tv`, `adopter-fix-20261008-1HztL0`, verified in #186 6036838832 and 6072724043 | The other Gate B records are not on `main` (section 5, item 4) | lane 1 |
| 40 | Follow-up patch/commit inventory | PARTLY | RB:gate-ab-evidence#5 (7 patches); RR §5 (maps each follow-up to a patch, PR, owner or "deferred", including run C's 29 `follow_ups`; lane 3: finding 18 RESOLVED at `c1283b5` except N3, which `612ea94` takes in, 6089982753 and 6090048356) | Lane 3's finding 18 (6082139424) lists what the inventory lacked. Since 01:13Z: T007's entry point; #190's follow-ups (`b50f197`, the `ln_doc` abort fix, FU); #191's heads `2411f40` and `13cc752`; capture tooling v2. Known at 01:13Z: run C's 29 named `follow_ups`; the routing in root-guidance-2026-10-08.md:186–194; lane 3's `feat/triad-lane-tooling`; the 33 outside consumers not covered; the `shape/` deletion left to T014. The stack check used superseded heads. RR answers all of it, and states that T010's two patches have no recorded resulting tree (finding 20). It is not on `main`, and the heads it lists are not final: T007's entry point (T3), #191's next head and FU's edit, so it is refreshed once more at the final heads | lane 1 |
| 41 | Repeated into fresh remotes after the upstream fix | MET | M runs B and C at `7f84ca4` on openRepoShape `main` | A repin needs a new run (question e1) | — |
| 42 | Never the live consumer as `--source` | MET | M run C setup; no `adopt/` ref on origin | — | — |
| 43 | No in-place submodule edit; digests not adjusted | MET | #186 6035767825 and 6036838832 (v); M:root-guidance#1 (11/11 shape digests) | — | — |
| 44 | No real repository created for a test | MET | Both legs 404 at 20:32Z and 21:58Z; RB:gate-ab-evidence#3; T18 §1 (network namespace, 0 successful network calls) | Recheck at Gate C | lane 1 |
| 45 | Reviewed refreshed inventory (T001) with lines 2–6 | MET | M:inventory.json (stamp 2026-10-07T10:09:03Z; #189 LAND) | Refresh at the Gate A final capture | lane 1 |
| 46 | A review record for each T006–T010 patch | PARTLY | T006: 5464893559 LAND (landed). T009: #190 LAND ×2 and delta LAND (landed). T007/T008 code side: #191 `13cc752` LAND with conditions (5471121210). T010: lane 3 6089801221 (c), fit for evidence-3 | The T007 entry-point patch is CHANGES REQUIRED (5471121210 T3). #191's next head: unchecked. T010's `composed.yml` carries finding 13 (line 32) | lane 3; lane 1 |

**Counts (46):** MET 30 · PARTLY 15 · OPEN 0 · AFTER-GATE-C 1.
- **PARTLY:** 2, 18, 19, 21, 22, 25, 26, 27, 28, 32, 34, 36, 37, 40, 46.
- **AFTER-GATE-C:** 35.

**Moved since lane 1's first pass (13:27Z–13:50Z, unpublished; then MET 29 · PARTLY 15 · OPEN 1 ·
AFTER-GATE-C 1):**
- **29: PARTLY → MET.** #190 landed at `b50f197`.
- **33: PARTLY → MET.** Lane 3's review of the T010 patches (21:47Z) confirms every job, gate and
  policy the line names.
- **34: OPEN → PARTLY.** The r2 suites finished, with failures.
- **36 and 37: MET → PARTLY.** Lane 3's T011 review (13:43Z) shows the hook rollback, the
  candidate restore, the post-merge rollback and jobs are not rehearsed.
- **39: PARTLY → MET.** Run C landed with #192. This walk now reads line 39 by the checklist's own
  evidence column; the other records' publication moves to section 5.

## 2. Reconciliation with lane 2's walk at `a7a8e00`

Lane 2's walk is `004-migrate-to-triad-reads` @ `a7a8e00`:
`specs/004-migrate-to-triad/gate-b-status-2026-10-09.md`, the same path as this file. Lane 2
keeps it on that branch, unrevised, as a cross-check; it goes into no PR (lane 2, #186
6088829392). Lane 2 read to 13:48:37Z; this walk reads to 22:10Z.

Lane 2's legend is the checklist's own: EXISTS, IN PROGRESS, NOBODY, BLOCKED, DECIDED. It
describes who holds a line. This walk's legend describes the evidence. The two map as follows:
- DECIDED ≈ MET;
- BLOCKED ≈ AFTER-GATE-C;
- IN PROGRESS ≈ PARTLY;
- EXISTS is MET when nothing remains, and PARTLY when a review, a receipt or a decision does.

**Lines that differ in substance, with this walk's verdict:**

| # | Lane 2 | This walk | Verdict |
| --- | --- | --- | --- |
| 22 | NOBODY | PARTLY (no owner) | **Both are right about different things, and they agree on the gap.** Lane 2 records that no writer holds it. This walk records that a start exists: Eagle's installed protocol-file digests (root-guidance §9). But that start is not "through owning workBenches delivery" and has no command or skill digests, so even Eagle is partial. Kept as PARTLY, flagged as having **no owner**; no lane-2 writer holds it either (6088829392 item 6). It cannot finish until Brett names the target workstations (question e8) and the workBenches owner delivers. Lane 1 should name a holder. |
| 2 | EXISTS | PARTLY | Lane 2 itself notes that no source names who approved the private-venv path, and later adds that neither receipt says bench and system installs were left unchanged (6088829392 item 10). plan.md:105–106 asks for "the approved prerequisite path", and Gate C asks that "prerequisites … are current". Kept as PARTLY until Brett answers question e4. |
| 12 | EXISTS, candidate only; PARTLY in 6088829392 item 2 | MET | Lane 2 found no regression record at the merged head and asks this walk to cite #162's CI at `6fa4e07` or say there is none. This walk cites it: at #162's head `6fa4e07`, `tests`, `tests-windows` and `tests-macos` succeeded, and at its merge `7f84ca4` the `tests` job, `python3 -m pytest tests -q` with `tests/test_adopt_submodules.py` included, succeeded at 2026-10-07T01:13:26Z (Windows and macOS are skipped on that push). Each case adopter-blocker.md:61–65 names is covered by adopter-rehearsal.md:23–36, and those tests pass at the merged head. The stated limit, "does not qualify every mixed-registration plan", does not reach this repository, whose one registration moves whole to code (line 14). MET. |
| 18 | EXISTS (document only) | PARTLY | A row that exists only in the writer's document, with no receipt and no independent rerun, is evidence not yet checked (#193 item 11). T18 adds a second run by lane 1 itself, also unreviewed, and a new finding: the bootstrapped root is "dirty" to `resume`. PARTLY. |
| 19 | EXISTS | PARTLY | Lane 2's own note that `.specify` was read from today's checkout and not from Gate A's capture is a gap against the checklist's evidence column. The posture decision is open (e7), and T18 adds the `SPECIFY_FEATURE` disagreement. PARTLY. |
| 21 | EXISTS (document only) | PARTLY | As for 18. T18 also shows that validation run from the root passes vacuously. PARTLY. |

**Lines that agree in substance:**
- **Same status, different legend:** 1, 4–11, 13–16, 23, 24, 30, 35, 38, 41–45 (MET or
  AFTER-GATE-C here; DECIDED, EXISTS or BLOCKED there).
- **Unlanded at lane 2's cutoff, landed since:** 3, 17, 20, 29, 31 (lane 2's "EXISTS
  (unlanded)" are MET now).
- **Line 33:** EXISTS there, MET here since lane 3's review of the T010 patches (6089801221
  finding 12). This walk's earlier PARTLY waited only on that review.
- **IN PROGRESS there, PARTLY here:** 25–28, 32, 34, 36, 37, 40, 46.
  - The newer facts are 5471121210 (#191 LAND with conditions; T007 patch CHANGES REQUIRED),
    6088812080 (the final matrix at `13cc752`), 6087267593 (r2's three suites), 6089801221
    (lane 3's T010 review), 6089982753 (lane 3's LAND on RR), and RR and EF (lane 2's slices).
  - Lane 2 also holds 36 and 37 open on its T011 verification. That verification has since
    passed (6082370012), and lines 36 and 37 stay PARTLY on lane 3's review findings instead.
  - Lane 2's `a7a8e00` still names holders for lines 32, 36, 37 and 40 that have since finished
    (6088829392).
- **Line 39:** EXISTS there, MET here. Both read the run C receipt, which is now on `main`.

**Lane 2's "Facts noticed" — this walk's verdicts:**
- **Item 16 (a host-absolute path in IN:installer-2026-10-08.md:13): agree.** It must be removed
  before IN goes into the evidence-3 PR; plan.md:38–39.
- **Items 1 and 8 (the candidate receipt is absent from brett-wip; the record cites #191 at
  `2411f40`): agree.** Both are owed with the r2 publication (line 34).
- **Item 13 (two openspec results): agree.** It is question a. T18 §3 now measures 1.2.0 and
  1.6.0 side by side.
- **Item 14 (two reviews of lane 1's PRs are headed "lane openRepoTools-1"): agree; a note, not a
  status change.** The reviews of record for #190 and #191 are lane 3's; lane 1's are same-lane
  second opinions.
- **Items 2–7, 9–12, 15 and 17: agree.** They are overtaken by the landings, or are text fixes
  carried by #193.

**Lane 2's review of this walk's first pass (#186 6088829392), item by item:**
1. Lines 36 and 37 to PARTLY: **adopted.**
2. Line 12 to PARTLY: **not adopted.** The merged-head CI record it asks for is cited (the table
   above); MET stands.
3. Line 34 to PARTLY with the r2 numbers: **adopted**, with the note that r2 rests on `13cc752`.
4. Lines 25 and 46, 5471121210's CHANGES REQUIRED (T3) and #191's LAND with conditions:
   **adopted.**
5. Question e1 is stale: **adopted.** `main` is `22c9fdd`, and its `scripts/repo_shape.py` change
   is the only one of the six commits that touches a mounted file (question e1).
6. Line 22, drop "lane 2" from the owner: **adopted.**
7. Re-cites: **adopted.** Run C's records are cited on `main`; "Land #192" and "fold `b50f197`"
   are gone; line 39 is MET.
8. Question a, record `command -v` and `--version` for each CLI: **adopted** (question a).
9. Questions e6, c and b: **adopted** (section 4).
10. Lines 40 and 2: **adopted** (section 1).

Lane 2's corrections to its own records stand as it gives them: r14's `KeyError 'reason'` was
first seen in lane 1's r1, and #193 item 15 was found on lane 2's own r2-equivalent build, not in
lane 1's r2 logs (#193 now says so).

## 3. T001–T019 against the evidence

Every task stays open on `main`.

| Task | What the evidence already covers | What remains before Gate C | After Gate C |
| --- | --- | --- | --- |
| T001 inventory | M:inventory.json, M:preservation-2026-10-07.md (17 trees, 33 refs, the estate-status refusal relayed, amendment observations) | Owner dispositions for every retained object, approved by Brett (question e5); a refreshed inventory at the final capture | — |
| T002 preservation | Gate A bundle; restore 97 PASS (October 7), 90 PASS (RB), 91 PASS (lane 2's independent run) | Capture tooling v3: lane 2 found that v2 rewrites the source's index (A1) and can write under `/` (A2) (#186 6087232548, 6087261307). No fix was posted by 21:44Z, and no capture runs on a real checkout until lane 2 re-verifies one. Then the owner-coordinated freeze, the final capture, and installed-file receipts for py-bench and the other workstations | — |
| T003 mapping | Names and visibility confirmed; filter-repo; run C's plan (`plan ok`, 0 drops) on `main` | Approve the prerequisite path (e4); regenerate and `check` at the frozen source; the final mapping goes into the approval (e2) | — |
| T004 rehearsal | Run C on `main` | A rerun at the frozen source if question e3 requires one | The real `execute` is T013 |
| T005 nested pin | Refusal, upstream fix and repin; the nested pin and bootstrap in runs B and C; upstream CI at `6fa4e07` and `7f84ca4` | Question e1 (stay on `7f84ca4`, or repin and rehearse again) | — |
| T006 root/leg guidance | Collisions, 32 repairs, leg front doors, provenance 35/35 (on `main`); bootstrap, paired selection and OpenSpec roots measured twice (root-guidance §7; T18 §§1–3) | #193 items 8–13 (EF, unreviewed); lane 2's verification of T18, then a review; a receipt, or the sentence EF adds saying there is none; questions a, c, e7, e8 | T014 applies `assembly-0001`, `code-0001` and `spec-0001`, regenerates the two bumps with `bump-leg.py`, and settles `shape/*.md`. T18's follow-ups go to workBenches and lane 3 |
| T007 entry point | The entry-point patch (IN); #191's code side, LAND with conditions at `13cc752`; T1–T2 of 5471121210 | #191's next head: proof, lane 3's check, the PR body, `tests-macos`, landing, against the matrix findings of 6088812080. The entry-point patch's T3 change, then its re-review | T014: the entry point ships in the root-split PR itself (lane 3, #186 6072087071); T015: the real one-liners |
| T008 matrix | 15 rows at `2411f40`; the final matrix at `13cc752` (337 row logs) | A rerun at #191's next head (one command, lane 2) | T015 against the real GitHub; workBenches re-vendors (W1/W3/W8) once the legs exist |
| T009 test roots | #190 landed with `b50f197`; its CI green, macOS included | FU @ `01ccc86`: one edit (6089801221 finding 7), then a PR and landing; #193 items 3–7 and 15; item 5 (paired layout) before Gate C; item 14 settled by lane 1 | Verify at the real head (T015) |
| T010 CI | Two workflow patches; local proofs P1–P4; lane 3's review, fit for evidence-3 | `composed.yml` against #180 (finding 13 (i)); a composed run of the final candidate that passes (line 34); question d | Hosted runs at the real legs (T015); a real author on both patches (T014); SonarCloud binding and required checks (e9) |
| T011 restore/rollback | Source restore and four rollback homes, independently verified; RR refreshes the record, LAND by lane 3 within evidence-3 | A hook-changing rollback, the candidate restore and a post-merge pin-bump rollback, or a dated statement of what cannot be rehearsed; jobs before/after | Rollback checks at the real head (T015) |
| T012 freeze and approval | #97 and #121 landed and are in the baseline | Freeze; regenerate and `check`; recheck the names; present the plan, follow-ups and dispositions; Brett's approval | Refuse source drift before `execute` |
| T013–T015 | Prepared patches re-apply (RB §5; the candidate's §2) | — | All of them; T015 carries the hosted CI that question d moves there |
| T016–T019 | T18 is the disposable half of T018 (unreviewed, on its branch; lane 2 is verifying it) | — | All of them. T016–T018 are prepared in the candidate once the legs exist; the real half of T018 and T019 follow cutover |

## 4. Gate C open questions

Each question ends in text for Brett Heap to approve, correct or reject. None of it is approved
by being written here.

### (a) `openspec validate migrate-to-triad --strict` fails on `main` with the CLI first on `PATH`

**Run** in a scratch single-branch clone of `main` at `f87fd5a` (22:00Z; the first run, at
`63810dd`, gave the same results). The change's files are identical at both heads. On lane 1's
workstation, `command -v openspec` is `~/.npm-global/bin/openspec`, and `--version` prints
`1.2.0`. The system openspec, second on `PATH`, prints `1.6.0`.

```text
$ ~/.npm-global/bin/openspec validate migrate-to-triad --strict    # 1.2.0, first on PATH
Change 'migrate-to-triad' has issues
✗ [ERROR] repository-triad-migration/spec.md: ADDED "Installation retains the public interface and one revision" must contain SHALL or MUST
exit=1
$ <system openspec> validate migrate-to-triad --strict             # 1.6.0
Change 'migrate-to-triad' is valid
exit=0
```

On lane 2's host the system openspec is 1.13.1, and it passes `migrate-to-triad` and 5 of 5
changes on `main` (6088829392 item 8). EF records the bench's openspec as 1.13.1 too.

**Cause.** 1.2.0's `extractRequirementText` (`dist/core/validation/validator.js:369-390` in its
package) takes only the first non-blank body line of a requirement. Line 45 of
`openspec/changes/migrate-to-triad/specs/repository-triad-migration/spec.md` reads `Existing
one-line installation, command names, payload destinations/modes,`, and the requirement's SHALL
is on line 46. 1.6.0 reads the whole body. Every other requirement in the file puts SHALL on its
first body line. The same 1.2.0 rule fails `interactive-lane-name-repair` (two requirements),
which is not this migration's change. T18 §3 and §5 item 7 add that from the root or the code
leg, `validate --all --strict` finds no change and passes vacuously, so validation belongs in the
spec leg. verification.md:28, :66, :96, :126 and :144 record strict validation as passed without
naming a CLI version.

**Proposed minimal change.** Tested in scratch copies: 1.2.0 and 1.6.0 both exit 0. No
requirement is added, removed or renamed, and no scenario changes.

```diff
 ### Requirement: Installation retains the public interface and one revision

-Existing one-line installation, command names, payload destinations/modes,
-skills/hooks/receipts and supported fork/ref/local invocation SHALL remain
-usable. An adopted assembly entry point SHALL resolve one immutable code
-revision for the complete installation. Missing/inconsistent pin evidence
+The migration SHALL keep the existing one-line installation, command names,
+payload destinations/modes, skills/hooks/receipts and supported fork/ref/local
+invocation usable. An adopted assembly entry point SHALL resolve one immutable
+code revision for the complete installation. Missing/inconsistent pin evidence
 SHALL refuse before partial installation. Installed tools SHALL function
 without a developer assembly checkout.
```

A no-wording alternative also passes both CLIs: join the first sentence onto one line.

**Brett decides one of:**
1. "Approve replacing lines 45–48 of
   `openspec/changes/migrate-to-triad/specs/repository-triad-migration/spec.md` with: *The
   migration SHALL keep the existing one-line installation, command names, payload
   destinations/modes, skills/hooks/receipts and supported fork/ref/local invocation usable. An
   adopted assembly entry point SHALL resolve one immutable code revision for the complete
   installation. Missing/inconsistent pin evidence* (the rest unchanged). It changes no
   requirement's meaning."
2. "Leave the text. The validator of record is openspec 1.6.0 or later, run in the spec leg, and
   the 1.2.0 copy in `~/.npm-global/bin` is removed or upgraded on every workstation that
   validates."

Optional in the same edit: line 64 ends `…its manifest/pins; product` and line 65 begins `Full
proposals`, so the sentence reads "pins; product Full proposals". The stray word does not affect
validation.

### (b) "account move"

**Every use.** `git grep -n -i -E 'account[ -]?move'` over `main` and every evidence branch, and
#186's body and comments, find one line:

```text
specs/004-migrate-to-triad/adopter-rehearsal.md:103:conversion, merge, account move or lane rebinding.
```

It came in with `ff6f6a7` (2026-10-06, "docs: record successful triad adopter candidate
rehearsal"), squashed into `main` by #187 as `44983ce`.

**plan.md, spec.md and tasks.md never say it**, nor do the change's proposal, design, tasks and
capability spec. Their "account" words are all about accounting for content: "account for",
"accounting", "accounted" and "misaccounts" (for example plan.md:111–112, :152, :169, :209;
spec.md:14, :40, :95, :111; tasks.md:47, :66, :89, :97, :135, :163; the capability spec's :13).
Nothing in the plan defines an account move, and no task performs one.

**What it needs.** The phrase sits in a list of acts the October 6 receipt does not authorize.
Gate C's approval should say whether any account act belongs to the migration:
- the legs would be created in the `opensoft` organization (adoption-plan.yaml `org: opensoft`),
  and `gh` here is `brettheap`, an active admin of `opensoft`;
- in-place adoption keeps `opensoft/openRepoTools` where it is;
- no repository is transferred between accounts or organizations.

The lanes' Claude "account swaps" in #186's comments are operational and unrelated.
adopter-rehearsal.md is a dated receipt and is best left as written.

**Text for Brett to approve or correct:** "No account move is part of this migration:
`opensoft/openRepoTools` stays in place, `opensoft/openRepoTools-spec` and
`opensoft/openRepoTools-code` are created in the `opensoft` organization by `brettheap`, and no
repository is transferred between accounts or organizations."

### (c) `.gitattributes`: plan.md against the code on `main`

**The plan** (M:plan.md:55–62, § Target placement):

```text
57 | Assembly `openRepoTools` | `AGENTS.md`, `CLAUDE.md`, `README.md`, `LICENSE`, `.gitattributes`, `.gitignore`; generated manifest/Makefile/validators and assembly pins | Front door and project coordination across legs. |
59 | Code `openRepoTools-code` | All executable tools, `repos.tsv`, `commands/`, `skills/`, `tests/`, implementation CI | Shipped implementation and its installer payload. |
```

**The code on `main`** since #190: `f87fd5a:tests/conftest.py:62–68` says everything outside the
front-door documents and spec trees is the code leg's, "and that includes `.gitattributes`,
DELIBERATELY: the placement table puts it at the assembly, but git reads a submodule's attributes
from the submodule's own tree". So `main` now disagrees with plan.md:57 (6088829392 item 9).

Related, and unchanged by this question: `openspec/changes/migrate-to-triad/design.md:48` ("Root owns front-door guidance, license,
project metadata and workflow bootstrap") and adoption-plan.yaml's `.gitattributes` → `root`,
which is correct for extraction. The original file and its history stay at the root.

**Why** (#190's PR body, "Decision: `.gitattributes` stays in the code leg";
CI:test-roots-and-ci-2026-10-08.md#2):
- Git never applies a superproject's attributes inside a submodule. Measured in the composed
  candidate: `code/park` and `code/tests/run.sh` are `text: unspecified`.
- A leg split exactly by the table is red on `test_the_root_carries_the_line_ending_rule`.
- T006's `code-0001` adds the code leg's own copy, and `spec-0001` gives the spec leg one. The
  candidate confirms `text: auto`, `eol: lf` in the leg.

**Proposed amendment** (the plan is Brett's own). Row 57 is unchanged. Row 59 becomes:

```text
| Code `openRepoTools-code` | All executable tools, `repos.tsv`, `commands/`, `skills/`, `tests/`, implementation CI; its own `.gitattributes`, added after extraction | Shipped implementation and its installer payload. Git never applies the assembly's `.gitattributes` inside a submodule, so the leg carries the LF rule its bash files and byte-for-byte installer checks need. |
```

Add after the table:

```text
Extraction gives each original front-door file one owner, the assembly. T006's leg patches then
add new files to the legs: each leg's own `AGENTS.md`, `CLAUDE.md`, `README.md`, `LICENSE` and
`.gitattributes`, and the code leg's `.gitignore`. `spec-0001` also re-points three test paths in
the spec leg's `docs/README-claude-current.md`. These are reviewed changes after byte accounting,
not moved paths, so the adoption mapping does not change.
```

**Text for Brett:** "Approve amending plan.md § Target placement: the code leg carries its own
`.gitattributes` (and each leg its own short front door), added after extraction; the assembly
keeps the originals." The minimal form, exactly what #190 asks, is the row 59 change alone.

### (d) Hosted CI before the real legs exist

**The conflict.**
- T010 is in "Phase 3 — Installation and checks (Gate B completion)" and asks to "Verify the exact
  rehearsed composed state passes required checks and the compatibility matrix" (tasks.md:77–81).
- "T011 closes Gate B" (tasks.md:164).
- The rehearsed commits live only in host-local bare remotes, which GitHub-hosted runners cannot
  check out (checklist line 35).
- "No real repository is created for a test" (plan.md:253). #186's rules forbid a real leg
  repository or a PR to one before Gate C.
- CI:test-roots-and-ci#5: "Neither patch can run on GitHub until the legs exist."
- T015 already validates "the real exact assembled head using … required platform/CI"
  (tasks.md:107–108) before the root adoption merge.

**What exists today.** The code these jobs would test already runs on hosted runners, on today's
layout:
- #190: `tests`, `tests-no-submodule`, `tests-windows`, `parse-macos`, `tests-macos`,
  `guard-launch-mode` and SonarCloud, all green;
- #191: the same less `tests-macos`, which waits on `ready`.

What only the legs can show:
- the code leg standalone with its document checks skipping by name;
- the Windows LF check on the leg's own `.gitattributes`;
- the assembly's `composed.yml` with an https recursive checkout, which lane 3 expects to be red
  until #180 is fixed (6089801221 finding 13 (i)).

**Options for Brett:**
1. **(Recommended by this walk.)** "Gate B does not wait for hosted runners on rehearsed
   commits. The hosted runs of the code leg's `tests.yml` jobs (including `tests-windows`,
   `parse-macos` and `tests-macos`) and of the assembly's `composed.yml` move to T015, before the
   root adoption merge. Before Gate C, the same jobs green on the code-side PRs against today's
   layout and the local composed and standalone runs of the exact candidate stand in for them. No
   repository is created to host them." Matching addition to tasks.md T010: "Hosted-runner checks
   that need the real leg repositories run at T015 against the real exact assembled head."
2. "Approve a never-merged draft PR on `opensoft/openRepoTools` whose tree is the candidate code
   leg, to run its `tests.yml` on hosted runners before Gate C." It creates no repository, but it
   is a PR against the real assembly repository whose tree deletes most of `main`, and it cannot
   run `composed.yml`.
3. "Approve temporary repositories <names, visibility> for hosted CI of the rehearsed commits,
   deleted after T015." This contradicts plan.md:253, which would need amending in the same word.

Two facts T015 must carry whichever option is chosen:
- The assembly has no `tests-macos` check, so landing tooling that reads `tests-macos` by name
  has nothing to read on an assembly PR (6089801221 finding 12).
- After cutover the documented curl one-liner needs api.github.com, 5 API calls per install, and
  `jq` on the curl path. A gh-less, rate-limited machine cannot install (5471121210 T4; question
  e10).

### (e) Other decisions only Brett can make

In dependency order. Each is a sentence Brett approves, corrects or rejects.

1. **The standard revision.** openRepoShape `main` is `22c9fdd`, six commits past the pinned and
   rehearsed `7f84ca4`: #170 (`b18cca9`: `execute` refuses every finding `check` reports), #182
   (`21f5c33`: shape files past a source `.gitignore` are force-staged and verified), #187
   (`f25d805`: canonical leg mount paths), #185 (`bc09bc5`: scaffold force-staging), #186
   (`4ce9cb0`: shape-doctor's submodule note) and #193 (`22c9fdd`: `load_yaml` refuses a
   non-UTF-8 byte). Four of them change `adopt-project.py` itself. Only `22c9fdd` touches one of
   the eight files this repository mounts (`scripts/repo_shape.py`; the eight are listed in
   `837928a`'s message). A repin to `4ce9cb0` or earlier moves no mounted file. Gate C "names the
   actual source/standard revisions" (plan.md:161), and the rules allow only a commit on
   openRepoShape `main`.
   - Either: "Execute with openRepoShape `7f84ca42ca86a8902928345109d2bf6bad87bd91`, the pinned
     and rehearsed revision."
   - Or: "Repin to <a commit on openRepoShape `main`, for example
     `22c9fddc5635f7bfd2cc021ad7dfe3ade9c934f8`> first, through a pin PR with a recomputed digest,
     and rehearse again (run D) before Gate C."
2. **The frozen source, the landing hold and where the final plan lives.** A committed plan
   counts `openspec/`, which contains the plan, so no commit that carries the plan can be its
   source (#192 finding 17). `check` reads the clone's local `main` (#193 item 10).
   - Text: "Freeze `main` at <40-hex> once the pre-Gate-C PRs land. Hold every landing on `main`
     from then until the root-split PR merges or is abandoned. The final plan for that commit is
     presented in the Gate C request and kept in the private receipt, not committed to `main`
     before `execute`."
   - The freeze also starts Gate A's owner-coordinated final capture (plan.md:77, :154–155).
3. **Whether the rehearsal is repeated at the frozen source.** T012: "Verify current …
   rehearsal evidence; refuse any source drift before execution". Gate C: "Gate A/B evidence …
   current".
   - Either: "A source that differs from `837928a` only under paths the plan already assigns
     needs a regenerated plan and `check`, not a new rehearsal."
   - Or: "Rehearse again (run D) at the frozen source before Gate C."
4. **The prerequisite path.** "`git-filter-repo` 2.47.0, installed into a private venv from the
   wheel with SHA256 `2cd04929b9024e83e65db571cbe36aec65ead0cb5f9ec5abe42158654af5ad83`
   (`--no-index`), is the approved prerequisite path for the real `execute`; bench and system
   installs stay unchanged, and the execution receipt says so." (plan.md:105–106; checklist
   line 2)
5. **Work dispositions.** T012 asks for approval of "work dispositions", and the change's
   tasks.md 1.2 for "active-work dispositions". The October 7 inventory's dispositions are
   proposals held in a private receipt (M:preservation-2026-10-07.md#Inventory (T001)). Text:
   "Approve the dispositions in receipt <id> as listed."
6. **#191's behaviour on today's layout.** The review rule makes any change to today's
   single-repository behaviour before Gate C a Gate C item (#191 review 5464963807 finding 3).
   Measured differences at `13cc752`:
   - two extra probe requests per install (26 raw requests against `main`'s 24 with no gh; 25 gh
     contents against 23), each answered 404 (5471121210 delta 3);
   - an offline installed-copy reinstall refuses in new words that name the layout question,
     where `main` names the skills (delta 3);
   - the ancestor walk, unreachable in today's estate, adds an output line under an unrelated
     LF pin and exits 2 under a CRLF one (delta 4);
   - lane 2's matrix adds a 502 on a probe refusing where `main` installs, a missing ref read as
     a single repository after 34 requests with `main`'s words, and a HOME holding
     `contracts/code-pin.yaml` refusing a reinstall (6088812080 items 1–3).

   Re-check every one at #191's next head. Lane 2's pre-push matrix on that head (6090038382,
   not counted here) already reports the ancestor-walk and HOME-pin cases fixed, and the missing
   ref, the 502, the garbage body and the offline wording still different from `main`, plus a
   residual walk match where an unrelated pin's own `submodule_path` lines up. Text, for whatever
   remains: "Accept <the named differences> on today's layout as the price of telling the layouts
   apart, disclosed in #191's body."
7. **The `.specify` posture at the assembly root.** "Keep `.specify/`, the managed blocks and the
   generated agent files local and ignored per clone, as today (`.git/info/exclude`), with only
   `/worktrees/` in the tracked `.gitignore`." The alternatives are to ignore them in the tracked
   `.gitignore` or to commit `.specify/` (root-guidance §8). T18 §5 item 1 adds that a
   bootstrapped root is "dirty" to `resume`, and measures the options: land the spec leg's three
   OpenSpec scaffold files before cutover, run the bootstrap with `--no-repo-agent-pointers` or
   commit its block, and carry four exact-path root excludes.
8. **Target workstations** for T006's distribution check and SC-006: "The target workstations
   are <Eagle, …>; each needs the workBenches delivery receipt before cutover." Only Eagle has
   evidence (root-guidance §9).
9. **Owner acts on the new repositories** (after Gate C, but part of the plan approved there):
   "Bind SonarCloud to `opensoft/openRepoTools-code`; protect each leg's `main` with its
   `tests.yml` jobs required; require `composed / exact-pins` on the assembly's `main`."
   CI:test-roots-and-ci#5 and #8 name the SonarCloud binding as an owner's act.
10. **The post-cutover one-liner's dependencies** (5471121210 T4). Either: "Accept that after
    cutover the curl one-liner needs api.github.com (5 calls per install) and `jq`; document it
    beside the one-liner." Or: "Require the one-liner to install without the API, and make that
    a T007 change before Gate C."

**A Gate C approval sentence that would cover the above** (a draft for the request, with blanks):
"Gate C for #186: I approve the in-place adoption of `opensoft/openRepoTools` as the assembly,
executed once with openRepoShape `adopt-project.py` at <standard 40-hex>, from an isolated
single-branch clone of `main` at <source 40-hex>, with the plan regenerated for that source
(sha256 <…>); creating `opensoft/openRepoTools-spec` and `opensoft/openRepoTools-code`, both
public; `git-filter-repo` 2.47.0 from the private venv (wheel `2cd04929…ad83`); the follow-ups
<T006 assembly-0001, code-0001, spec-0001; T010's two workflows; T007's entry point; the two leg
bumps regenerated with `bump-leg.py`> applied after source verification through leg and root
PRs; the work dispositions in <receipt>; and a landing hold on `main` from <source> until the
root-split PR merges or is abandoned. It does not approve lane rebinding, closing old PRs or
retiring worktrees."

## 5. Blockers to requesting Gate C, in dependency order

1. **#191 to a landable head.** Push the next head; prove its red/green claims; lane 2's matrix
   rerun and lane 3's check at that head, against 6088812080's items 1–7 and the open items of
   lane 2's pre-push run (6090038382); correct the PR body
   (5471121210 delta 8); `tests-macos` under `ready`; land. Then the T007 entry-point patch's T3
   change and its re-review. Or Brett's ruling on any kept difference (question e6).
2. **The test-root follow-ups and the T010 patches.** FU's one edit (6089801221 finding 7), its
   PR and landing; `composed.yml` against #180 (finding 13 (i)); #193 item 14 settled by lane 1,
   and item 5 (paired-layout discovery) before Gate C.
3. **The composed candidate at the final heads (r3).** Every suite passing, or each failure
   classified with its cause: r14's `KeyError 'reason'`, `test_agents_md_names_the_pin_rules`,
   the row stamps (#180), the load-sensitive timeouts. Then the install and rollback recheck,
   and publication with its receipt (lines 34, 36, 40).
4. **The evidence-3 PR.** Fold CI (`d28e2cc`'s three new files), IN (with the host-absolute path
   at installer-2026-10-08.md:13 removed), RR at `2e7e55e` (the branch tip's file: a cherry-pick of
   `c1283b5` alone conflicts, 6089982753), EF `096de93`, the candidate record, T18
   and this walk onto `main`; do not reuse `849592b`'s subject or body (6088884829); review;
   land.
5. **Gate A.** Capture tooling v3 (A1, A2) and lane 2's re-verification; the owner-coordinated
   freeze; the final capture; owner dispositions (question e5); installed-file receipts for
   py-bench and the other workstations.
6. **Brett's decisions:** questions a–e, e10 included.
7. **The request.** Regenerate the plan at the frozen source and `check` it, rehearsing again if
   question e3 says so; recheck the leg names; present the plan, follow-ups, dispositions and the
   approval sentence above.

## 6. How this walk was read

Read-only except this file and scratch. `<checkout>` is lane 1's checkout of this repository and
`<scratch>` is lane 1's private scratch.

```sh
git -C <checkout> fetch --all --prune                                  # 20:30:48Z, 21:58:55Z, 22:07:06Z
git -C <checkout> rev-parse --short origin/<each ref in "Refs read">
git -C <checkout> show <ref>:<path>                                    # every document cited
git -C <checkout> diff --stat 63810dd f87fd5a -- <the planning files>  # empty
git -C <checkout> ls-remote origin 'refs/heads/adopt/*'                # empty
gh pr list --repo opensoft/openRepoTools --state open                  # #191 at 13cc752 only
gh issue view 186 --repo opensoft/openRepoTools --json body,comments   # through 22:06:49Z
gh issue view 193 --repo opensoft/openRepoTools --json body
gh pr view {190,191,192} --repo opensoft/openRepoTools --json body,reviews,comments
gh api repos/opensoft/openRepoTools-{spec,code}                        # 404, 404
gh api user; gh api user/memberships/orgs/opensoft                     # brettheap; admin, active
gh api repos/opensoft/openRepoShape/compare/7f84ca4...main             # ahead 6, behind 0
gh api repos/opensoft/openRepoShape/commits/<each of the six>          # files changed
gh api repos/opensoft/openRepoShape/pulls/162                          # head 6fa4e07, merge 7f84ca4
gh api repos/opensoft/openRepoShape/commits/{6fa4e07,7f84ca4}/check-runs
git clone -q --no-local --single-branch --branch main <checkout> <scratch>/main-clone
command -v openspec; which -a openspec; <each> --version               # 1.2.0 first, 1.6.0 second
(cd <scratch>/main-clone && ~/.npm-global/bin/openspec validate migrate-to-triad --strict)  # exit 1
(cd <scratch>/main-clone && <system openspec> validate migrate-to-triad --strict)          # exit 0
# the proposed text and the one-line join, each in a scratch copy: both CLIs exit 0
git grep -n -i -E 'account[ -]?move' <each ref> -- .
git grep -n -i account origin/main -- specs/004-migrate-to-triad openspec/changes/migrate-to-triad
```
