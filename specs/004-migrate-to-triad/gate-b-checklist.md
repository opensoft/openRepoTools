# Gate B checklist walk — 2026-10-07

**Sources read:** 2026-10-07T10:05Z, from commit
`ff6f6a7c7b7921ca1e0b0234e898900f98532366` (branch `004-migrate-to-triad`,
also the head of PR #187). **Live state rechecked:** 2026-10-07T11:06Z.
**By:** lane openRepoTools-2's writer, under opensoft/openRepoTools#186.
**For:** lane openRepoTools-1, to walk before it asks Brett Heap for Gate C.

This walk records facts. It approves nothing, and it changes no status in
`tasks.md`, where all 19 tasks remain open. Gate C stays Brett Heap's explicit
approval naming the actual revisions (plan.md:161–163).

## How it was read

These commands ran inside lane 2's `triad-reads` worktree, which is checked out
at ff6f6a7. The host path given to `git -C` is left out here because the
feature's public files carry no machine paths (plan.md:38–39). All `gh` calls
were reads.

```sh
for f in plan tasks spec verification preparation adopter-blocker adopter-rehearsal \
         installer-design quickstart research data-model protocol-review; do
  git show ff6f6a7:specs/004-migrate-to-triad/$f.md | cat -n
done
git show ff6f6a7:specs/004-migrate-to-triad/inventory.json   # parsed with python3 -I json
git show ff6f6a7:openspec/changes/migrate-to-triad/tasks.md | cat -n
git show ff6f6a7:openspec/changes/migrate-to-triad/design.md | cat -n
git show ff6f6a7:openspec/changes/migrate-to-triad/proposal.md | cat -n
git show ff6f6a7:openspec/changes/migrate-to-triad/specs/repository-triad-migration/spec.md | cat -n
git show ff6f6a7:openspec/changes/migrate-to-triad/adoption-plan.yaml | cat -n | sed -n '1,80p;325,380p'
git grep -n -i -E 'gate ?b|gates a/b|gate a/b' ff6f6a7 -- .
git show c4864ac:.github/workflows/tests.yml | grep -n -E '^  [a-z][a-z0-9_-]*:$|runs-on'
git show c4864ac:tests/test_upstream_pin.py | sed -n '170,200p'
git ls-tree c4864ac upstream/openRepoShape
git ls-tree -r --name-only c4864ac | wc -l
git ls-tree -r --name-only c4864ac | grep -c '^features/'
git show --stat e43b243; git show --format= e43b243 -- contracts/openreposhape-pin.yaml
git worktree list --porcelain; git for-each-ref refs/heads    # branch heads only
gh issue view 186 --repo opensoft/openRepoTools --json body,comments
gh pr list --repo opensoft/openRepoTools --state open --json number,headRefName,title
gh pr view 187 --repo opensoft/openRepoTools --json body,headRefOid,state
gh pr view 188 --repo opensoft/openRepoTools --json statusCheckRollup,labels,reviews,headRefOid
gh pr view 162 --repo opensoft/openRepoShape --json state,mergedAt,mergeCommit,reviews,comments
gh api repos/opensoft/openRepoShape/compare/39d5c986fcfac1a160474bfe91c5f1c37fccc72c...7f84ca42ca86a8902928345109d2bf6bad87bd91
gh api repos/opensoft/openRepoTools-spec; gh api repos/opensoft/openRepoTools-code
gh api 'repos/opensoft/openRepoTools/branches?per_page=100' --paginate
```

Short names used below: **cap-spec** is
`openspec/changes/migrate-to-triad/specs/repository-triad-migration/spec.md`,
and **#186 first act N** is the numbered "First acts" list in #186's body.
Every `file:line` refers to ff6f6a7 unless another commit is named.

## State at read time

- openRepoTools `main` is `c4864ac`. Its gitlink `upstream/openRepoShape` is
  still `39d5c986fcfac1a160474bfe91c5f1c37fccc72c`, and it tracks 100 paths.
- Two PRs are open:
  - **#187**: `004-migrate-to-triad` at ff6f6a7 into `main`, opened
    10:03:43Z. Lane 1 lands it.
  - **#188**: `chore/openreposhape-pin-7f84ca4` at `e43b243`, opened 10:10:43Z.
    This is the repin PR.
- openRepoShape PR #162 is MERGED (2026-10-07T01:09:14Z) as `7f84ca4`, which
  is still openRepoShape `main`'s head. The compare `39d5c98...7f84ca4` shows
  ahead 2, behind 0: `1a9fc53` (#164) and `7f84ca4` (#162).
- The local branches `004-migrate-to-triad-exec` (Gate A writer),
  `004-migrate-to-triad-rehearsal` (rehearsal writer) and
  `004-migrate-to-triad-reads` (lane 2) all point at ff6f6a7. None of them is
  on the remote. Lane 2's reads branch then gained ae70dc556 (line 24).
- `opensoft/openRepoTools-spec` and `opensoft/openRepoTools-code` both return
  HTTP 404 to the read-only API. Neither the shared repository nor the remote
  has an `adopt/` ref.
- #186 comment
  [6035767825](https://github.com/opensoft/openRepoTools/issues/186#issuecomment-6035767825)
  (10:11:58Z) records four things:
  - Brett Heap's words "open the PR for the planning branch; legs and
    visibility confirmed".
  - The legs and visibility are CONFIRMED. The comment calls this "a Gate C
    input, not Gate C".
  - The Gate A backup root is host-local, beside `prep-20261004T211123Z`; the
    comment names the path.
  - Lane 3's independent recompute of the 7f84ca4 tree digest matches #188's
    row.

## Status legend

Each line has exactly one status.

- **EXISTS on ff6f6a7**: the artifact is in the tree at ff6f6a7. The cell
  cites it and says what it shows. Line 24 alone reads **EXISTS on
  004-migrate-to-triad-reads @ ae70dc556**: its artifact was committed on top
  of ff6f6a7 on this branch.
- **DECIDED**: settled by Brett Heap's word, recorded outside ff6f6a7. Line 1
  is the only line with this status, on the coordinator's instruction.
- **IN PROGRESS by …**: a named writer holds the work at read time. The cell
  says what was observed of that work.
- **NOBODY**: no lane writer holds the work at read time. If the work has to
  wait for something, the cell names it as "starts after".
- **BLOCKED on …**: lane work alone cannot satisfy the line as the plan
  stands. The cell names what it waits on.

## Gate B in the plan's words

> **Gate B:** complete local rehearsal evidence, restore rehearsal, reviewed
> follow-up patches, resolved mapping and a passing compatibility test matrix.
> Mapping `check` alone does not satisfy this gate. (plan.md:140–142)

> Stop adoption on this refusal; resolve upstream and repeat into fresh local
> remotes before treating Gate B as passed. Installer/topology design can
> proceed while that resolution is pending. (plan.md:146–148)

| Gate B term (plan.md:140–141) | Checklist lines |
| --- | --- |
| complete local rehearsal evidence | 2, 7–16, 39, 41–45 |
| restore rehearsal | 36–37 |
| reviewed follow-up patches | 17–22, 25–26, 29, 32–33, 40, 46 |
| resolved mapping | 1, 3–6 |
| passing compatibility test matrix | 27–28, 30–31, 34–35 |
| inputs and publication (design, consumer reads, Gate A evidence) | 23–24, 38 |

## Checklist

### T003: mapping, leg names, prerequisites (tasks.md:33–40)

T003 sits under the heading "Phase 1 — Preservation and baseline (Gate A)"
(tasks.md:19). Its mapping is Gate B's "resolved mapping" (plan.md:141), and
#186 first act 3 groups it with the rehearsal as "Gate B rehearsal (T003–T005)".

| # | Requirement (cite) | Evidence that would satisfy it | Status |
| --- | --- | --- | --- |
| 1 | "Confirm proposed leg names/visibility" (tasks.md:33). FR-012: "Treat visibility, baseline, branch disposition and lane rebinding as reviewed execution decisions" (spec.md:66–67). "Public new legs are proposed … Their creation is not approved." (spec.md:115–116) | Brett Heap's word naming the legs and their visibility, matching `visibility: public` (adoption-plan.yaml:21) and `legs:` (adoption-plan.yaml:27–30). | **DECIDED.** #186 comment 6035767825 quotes "open the PR for the planning branch; legs and visibility confirmed" and records `openRepoTools-spec`, `openRepoTools-code` and `public` as CONFIRMED, "a Gate C input, not Gate C". Name availability is a separate recheck at Gate C (preparation.md:53–56, plan.md:162–163). |
| 2 | "inspect prerequisite availability" (tasks.md:33–34). "Make `git-filter-repo` available through the approved prerequisite path" (plan.md:105–106). It "must be made available before rehearsal/execution" (spec.md:116–117). | The rehearsal receipt names the git-filter-repo version, its wheel SHA256 and the private venv, and states that bench/system installs were left unchanged. preparation.md:60–65 shows the form. | **IN PROGRESS by lane 1's rehearsal writer.** #186 first act 3 specifies "`git-filter-repo` 2.47.0 in a private venv". preparation.md:60–65 holds the October 4 receipt, for the 39d5c98 run only. No line on ff6f6a7 says who approved the private-venv path; it was installed "for this rehearsal" (preparation.md:62–63). |
| 3 | "regenerate `adoption-plan.yaml` for the reviewed preliminary rehearsal source, retaining reasoned overrides" (tasks.md:34–35). "Regenerate the mapping using the standard rather than editing its source SHA" (preparation.md:112). "Do not change the baseline field to suppress a stale-plan finding" (quickstart.md:29–30). | A plan produced by `adopt-project.py plan` at 7f84ca4 from the repinned candidate, with `source.commit` set to that candidate. Every earlier `resolution:` is kept or re-reasoned, and every path added since daed209 is resolved with a reason. adopter-rehearsal.md:44–48 shows the October 6 precedent: `lanes-index` to code, `ideation/` to spec. | **IN PROGRESS by lane 1's rehearsal writer.** The plan committed on ff6f6a7 is from daed209 at 39d5c98 and covers 64 paths (adoption-plan.yaml:13–16), marked `proposed-preliminary-baseline` (adoption-plan.yaml:374). Main `c4864ac` tracks 100 paths. |
| 4 | "Verify standard `check` passes and records all source paths with no unapproved drops" (tasks.md:35–36). FR-002 (spec.md:40–41). SC-001 (spec.md:95–96). | `check` exits 0 at 7f84ca4 against the regenerated plan. The plan summary shows `unresolved` 0, and drops are 0 or each one is approved. | **IN PROGRESS by lane 1's rehearsal writer.** #186 first act 3: "regenerate …, `check`". |
| 5 | "Explicitly classify genuine bounded feature amendment folders as code until upstream qualification; preserve full proposals/archives/canonical Speckit as spec regardless of branch origin" (tasks.md:36–38). FR-006 and FR-013 (spec.md:50–53, 68–72). plan.md:115–118. | The regenerated plan assigns `openspec/`, `specs/`, `docs/` and `ideation/` to spec. Any `features/<NNN-feature>/openspec/` path goes to code with a `resolution:`. | **IN PROGRESS by lane 1's rehearsal writer**, as part of the regeneration in line 3. Observation: `git ls-tree -r --name-only c4864ac \| grep -c '^features/'` prints 0. |
| 6 | "Record no amendment paths when none exist; do not manufacture historical amendments" (tasks.md:39–40). | A per-head record of bounded amendment paths at the rehearsal source and the retained heads, empty where there are none. The form is inventory.json `protocol_review.amendment_path_observations` (inventory.json:342), which on ff6f6a7 covers only daed209 and the October 4 heads. | **IN PROGRESS by lane 1's Gate A writer**, as part of the `inventory.json` refresh. That the refresh keeps this field is (inferred). |

### T004: isolated clone and local bare-remote rehearsal (tasks.md:44–47)

| # | Requirement (cite) | Evidence that would satisfy it | Status |
| --- | --- | --- | --- |
| 7 | "Prepare a clean isolated source clone with no linked worktrees" (tasks.md:44–45), "at the chosen source commit" (plan.md:104). FR-010 (spec.md:62–63). "Execution SHALL use a clean isolated source clone without linked worktrees" (cap-spec:147). | A receipt naming the clone's HEAD (the repinned candidate) and showing a single-branch clone, a clean status and one `git worktree list` entry. | **IN PROGRESS by lane 1's rehearsal writer.** #186 first act 3: "fresh isolated single-branch clone of the repinned candidate". |
| 8 | "rehearse the standard adoption against temporary local bare remotes" (tasks.md:45–46), "with no real GitHub repository creation or default-branch movement" (plan.md:107–108). | `execute --local-remote-dir … --work-dir … --yes` exits 0 at 7f84ca4, into fresh disposable bare remotes, with network transport disabled except local file transport. preparation.md:67–70 and adopter-rehearsal.md:51–54 show the form. | **IN PROGRESS by lane 1's rehearsal writer.** |
| 9 | "Verify source identity/history, path/blob accounting" (tasks.md:46–47). FR-002 and SC-001. Each tracked path accounted "by blob or gitlink identity in exactly one leg/root" (cap-spec:12–16). "full baseline accounting, leg histories" (plan.md:110–111). | The standard's accounting table (spec, code, root, dropped, total). An independent comparison of path, mode, object type and object ID showing zero missing or duplicate owners. The leg commits with their kept-commit counts. adopter-rehearsal.md:56–73 shows the form. | **IN PROGRESS by lane 1's rehearsal writer.** #186 first act 3: "Record source accounting, leg commits". #186 does not say whether the independent comparison is part of that writer's scope. |
| 10 | "… and recoverability without real GitHub creation" (tasks.md:46–47). "The source repository must remain unchanged if execution refuses" (adopter-blocker.md:58–59). | Source clone HEAD, refs and status identical before and after. The disposable legs kept for diagnosis. The live consumer's main, gitlink and pin contract unchanged. adopter-rehearsal.md:52–54 and 80–81 show the form. | **NOBODY.** It is not in #186 first act 3's record list ("source accounting, leg commits, recursive bootstrap, nested pin and digest"). |

### T005: nested dependency and pin (tasks.md:48–52)

| # | Requirement (cite) | Evidence that would satisfy it | Status |
| --- | --- | --- | --- |
| 11 | "If standard tooling refuses, record its refusal" (tasks.md:50–51). | The refusal, with the exact command, the exit status and the step that failed. | **EXISTS on ff6f6a7.** adopter-blocker.md:15–35 records `git submodule add` exiting 128 and `execute` returning 2. The same refusal is in preparation.md:72–77 and verification.md:13–16, and adopter-blocker.md:75–76 gives the private log's SHA256. |
| 12 | "resolve upstream" (tasks.md:51). The upstream regression "should cover a populated existing submodule, its registration explicitly assigned to code, the generated assembly registrations, recursive clone/bootstrap, exact mode/object accounting, and failure recovery", plus "partial registration ownership and no-existing-module inputs" (adopter-blocker.md:61–65). | Regression results covering each named case for the fix. | **EXISTS on ff6f6a7, for the candidate only.** adopter-rehearsal.md:15–37 records `tests/test_adopt_*.py` at 90 passed, 1 skipped, and four `test_adopt_submodules.py` cases at draft `91d5685`. The mixed-registration case "does not qualify every mixed-registration plan" (adopter-rehearsal.md:30–32). PR #162 merged at a later head. Its GitHub review list is empty, and its review is a PR comment (2026-10-07T01:08:38Z) titled "Review, and what changed since 91d5685". |
| 13 | "before a tested pin bump" (tasks.md:51). "bump to a commit on its main and recompute the dependency digest" (adopter-blocker.md:70). "use a commit on upstream main for the tested consumer pin/gitlink update and recomputed digest" (adopter-rehearsal.md:90–92). | One consumer commit that moves the gitlink and `contracts/openreposhape-pin.yaml` to a commit on openRepoShape main with `tree_sha256` recomputed, passes the required CI and lands on `main`. | **IN PROGRESS by lane 1's repin PR writer** (PR #188, open, not landed). `e43b243` (parent `c4864ac`) changes 2 files: gitlink to `7f84ca4`, `tree_sha256` to `3be52767e727d924dd05f9e78b18eb70f1682fe48614fab519f85331eeff5fa8`. Checks at 11:04Z: `guard-launch-mode`, `tests`, `tests-no-submodule`, `tests-windows` and `parse-macos` SUCCESS; `tests-macos` SKIPPED; no `ready` label. The upstream side is done: #162 MERGED as `7f84ca4`, openRepoShape main's head. Lane 3 holds the adversarial review. |
| 14 | "Exercise the existing nested submodule path, original `.gitmodules` extraction/removal" (tasks.md:48–49). FR-004 (spec.md:44–46). "source `.gitmodules` handling" (plan.md:110). | At 7f84ca4 the mount step that refused at 39d5c98 passes. The code leg carries the original `.gitmodules` bytes with the `upstream/openRepoShape` gitlink and contract. The assembly carries a fresh `.gitmodules` for spec and code only (the expected behavior, adopter-blocker.md:56–59). | **IN PROGRESS by lane 1's rehearsal writer.** |
| 15 | "pin integrity" and "Verify the code gitlink/pin/registration remain coupled" (tasks.md:49–50). "its registration, exact gitlink and coupled pin SHALL remain valid" (cap-spec:23–26). | In the extracted code leg: the gitlink equals the contract's `commit:`, the pinned checkout's own helper recomputes a digest equal to the contract's `tree_sha256`, and the registration is unchanged. preparation.md:90–94 and adopter-rehearsal.md:77–81 show the form. | **IN PROGRESS by lane 1's rehearsal writer.** #186 first act 3: "nested pin and digest". |
| 16 | "recursive bootstrap" (tasks.md:49). It must be "demonstrated by local rehearsal and recursive bootstrap" (cap-spec:25–26). SC-004 (spec.md:101–102). | A recursive clone of the disposable assembly and the generated `scripts/bootstrap.py` both pass (naming, manifest, exact leg and copy pins), and the trees are clean afterwards. adopter-rehearsal.md:75–77 shows the form. On October 4 this was "blocked" (preparation.md:94–95). | **IN PROGRESS by lane 1's rehearsal writer.** #186 first act 3: "recursive bootstrap". |

### T006: root collisions, leg guidance, workflow roots (tasks.md:53–61)

"T004–T006 precede integration validation" (tasks.md:162). Lane 2's consumer-side
reads for T006 (`consumer-reads-2026-10-07.md`, committed at ae70dc556) are reads. They are
not the patches these lines require.

| # | Requirement (cite) | Evidence that would satisfy it | Status |
| --- | --- | --- | --- |
| 17 | "Resolve materialized root collisions and new leg guidance in reviewable patches" (tasks.md:53–54). "Exercise all actual file-placement collisions" (plan.md:111–112). "Add leg root guidance without overwriting original root guidance" (plan.md:127). | The list of collisions that `execute` at 7f84ca4 actually materializes. At daed209 the plan lists five: `.gitattributes`, `.gitignore`, `AGENTS.md`, `CLAUDE.md` and `README.md` (adoption-plan.yaml:337–341). Then one reviewed patch per resolution against the rehearsed assembly commit, keeping the original root guidance. | **NOBODY.** Starts after line 8. |
| 18 | "bootstrap selected root workflow after manifest/legs exist" (tasks.md:54–55). "regenerate root workflow using setup-openspeckit after manifest/legs are present" (adoption-plan.yaml:346). | The shape-aware bootstrap run at the rehearsed assembly root, with its result recorded. | **NOBODY.** Starts after line 8. |
| 19 | "Verify first-line shape guidance, relative paths, actual `.specify` configuration and paired feature selection without copying machine secrets" (tasks.md:55–56). "Put `Read AGENTS-shape.md first...` guidance first" (plan.md:184–185). | The first lines of the root `AGENTS.md` and `CLAUDE.md`. The `.specify` configuration compared with the captured ignored workflow configuration, with no secret-bearing file copied. Paired feature selection resolving. | **NOBODY.** Its input, the Gate A writer's capture of ignored workflow configuration, is IN PROGRESS. |
| 20 | "Record original approved repository/commit/path and verified extracted spec correspondence … Repair relative links, selected roots/stores and task paths without guessing new baseline identities" (plan.md:118–121). FR-014 (spec.md:73–77), which tasks.md:188 maps to T006. | A correspondence table from original repository, commit and path to extracted spec commit and path. Reviewed patches for the cross-leg references; at daed209 the code files that name `docs/`, `openspec/` and `specs/` are listed at adoption-plan.yaml:325–336. | **NOBODY.** |
| 21 | "Verify explicit full-spec/local-amendment roots and intended feature branches, local-root precedence over store pointers and supported CLI store selection" (tasks.md:57–58, plan.md:131–135). | Runs in the rehearsed topology showing the selected root and branch for each operation, and a local root winning over a store pointer. `--store` is used only after recording that the installed CLI supports it. | **NOBODY.** |
| 22 | "check protocol/command distribution per target workstation through owning workBenches delivery, without treating a scaffold bootstrap as distribution" (tasks.md:59–61, plan.md:136–138). | For each target workstation, the identities and digests of the installed protocol and commands, in the form of protocol-review.md:11–16. | **NOBODY.** |

### T007: installer entry point (tasks.md:65–68)

| # | Requirement (cite) | Evidence that would satisfy it | Status |
| --- | --- | --- | --- |
| 23 | "Installer/topology design can proceed while that resolution is pending" (plan.md:148). The installer design "is ready for follow-up implementation after successful standard split verification" (plan.md:15–16). | A design naming the entry point, the payload-source resolution, the consumers that change and the acceptance matrix. | **EXISTS on ff6f6a7.** installer-design.md:1–97, prepared against daed209 (installer-design.md:3). |
| 24 | "refresh this inventory after landing" (installer-design.md:4–5). "Derive counts from the lists" (installer-design.md:64–65). At daed209 there were 15 `INSTALLABLES` and 29 artifacts (installer-design.md:61–64). | A read of the current source covering `INSTALLABLES`, the skills and commands lists, the destinations and the consumers at installer-design.md:52–59, with line cites. | **EXISTS on 004-migrate-to-triad-reads @ ae70dc556** (`specs/004-migrate-to-triad/consumer-reads-2026-10-07.md`). Its lines 235–239 cover the consumers at installer-design.md:52–59 with `openRepoTools` line cites. Line 241 records that main c4864ac has 17 `INSTALLABLES` and "31 artifacts, 29 of them files, 29 rows", while the design's numbers are those of daed209. |
| 25 | "Add the assembly `openRepoTools` entry point and coherent payload-source resolution in the code installer after source byte accounting" (tasks.md:65–66). FR-005 (spec.md:47–49). "Record their patches and resulting commits" (plan.md:125–126). | Reviewed patches with their resulting commit ids: the entry point in the rehearsed assembly and the resolution in the rehearsed code leg. | **NOBODY.** Starts after line 9 (tasks.md:163). |
| 26 | "Verify gh/raw one-liners resolve one code pin and do not duplicate installer mechanics or depend on developer checkouts after installation" (tasks.md:67–68). cap-spec:52–55. SC-003 (spec.md:99–100). | Runs in fresh disposable homes against disposable remotes, showing every payload coming from one immutable code commit and the installed commands working with the developer checkout absent. | **NOBODY.** |

### T008: compatibility matrix (tasks.md:69–72)

| # | Requirement (cite) | Evidence that would satisfy it | Status |
| --- | --- | --- | --- |
| 27 | "Cover local/offline, legacy monorepo overrides, adopted forks, branch/commit refs, immutable code selection, missing/mismatched pins and failed partial fetch" (tasks.md:69–71). "All rows below are pending measured tests in fresh disposable homes/remotes" (installer-design.md:70–71); the matrix has 15 rows (installer-design.md:75–89). | One measured test per matrix row, with its result recorded. | **NOBODY.** |
| 28 | "Verify unchanged command/artifact names, counts, destinations/modes, hooks, ownership receipts and all-or-none refusal" (tasks.md:71–72). cap-spec:43–50. | A before-and-after comparison against the current installer's derived lists (line 24), and refusal runs that leave the prior install unchanged. | **NOBODY.** |

### T009: explicit roots in fixtures and hygiene checks (tasks.md:73–76)

| # | Requirement (cite) | Evidence that would satisfy it | Status |
| --- | --- | --- | --- |
| 29 | "Separate code/spec/assembly/dependency roots in fixture and hygiene consumers, including docs/OpenSpec/Speckit references" (tasks.md:73–74, installer-design.md:91–94). | Reviewed patches giving the fixtures and hygiene tests explicit roots. `tests/test_repo_hygiene.py` reads the root README, the install line and the agent guidance (installer-design.md:92–94). | **NOBODY.** |
| 30 | "Verify the existing upstream pin checks run against code Git identity" (tasks.md:74–75). "Do not bypass the wrapper to obtain a pass" (preparation.md:99). | `tests/run.sh -k upstream_pin` passing inside the rehearsed code leg, with the output quoted. On October 4 the run stayed in the serialization wait and "No pytest assertion ran" (preparation.md:95–99). | **NOBODY.** #188's Linux `tests` job runs against the monorepo layout, not a code leg. Lane 2's verification pass (#186 comment 6035767825: the eight files `tests/test_upstream_pin.py` mounts are byte-identical between 39d5c98 and 7f84ca4) is evidence for the repin, not for this line. |
| 31 | "required composed checks cannot silently skip absent spec/dependency context" (tasks.md:75–76). "Preserve the Bash 3.2 floor and original no-submodule test behavior, while requiring complete dependencies for composed acceptance" (plan.md:127–129). SC-004, "no hidden skips" (spec.md:101–102). installer-design.md:88, 97. | A run with the spec or dependency context absent in which the composed checks refuse, while the documented standalone no-submodule skips stay as they are. | **NOBODY.** |

### T010: CI and composed acceptance (tasks.md:77–81)

| # | Requirement (cite) | Evidence that would satisfy it | Status |
| --- | --- | --- | --- |
| 32 | "Adapt implementation CI and root exact-pin integration checks with explicit compatible checkout context" (tasks.md:77–78). "The assembly exact-pin integration job must refuse absent required contexts" (installer-design.md:97). design.md:121–126. | Reviewed workflow patches for the code leg and for the assembly root. | **NOBODY.** |
| 33 | "preserve current Linux/macOS/Windows/WSL policies, Bash 3.2 parsing and serialized `tests/run.sh` locking" (tasks.md:78–79). | The patched workflows keep every job of `.github/workflows/tests.yml` at c4864ac and delete no assertion. The jobs are `guard-launch-mode`, `tests` and `tests-no-submodule` (ubuntu-latest), `tests-windows` (windows-latest), and `parse-macos` and `tests-macos` (macos-latest), at tests.yml:52, 72, 126, 157, 232 and 285. | **NOBODY.** |
| 34 | "Verify the exact rehearsed composed state passes required checks and the compatibility matrix, recording failures rather than deleting assertions" (tasks.md:80–81): the part that runs on this host. | `tests/run.sh` and the matrix run against the exact rehearsed assembly, spec, code and standard commits ("Composed candidate evidence", data-model.md:15), with failures recorded. | **NOBODY.** |
| 35 | The same clause (tasks.md:80–81): the part that needs GitHub-hosted runners (the `tests-windows`, `parse-macos` and `tests-macos` jobs). | Those jobs' results against the exact rehearsed commits. | **BLOCKED on somewhere GitHub-hosted runners can check the rehearsed commits out from (inferred).** The rehearsed legs exist only in disposable local bare remotes. The suite's checkouts take `submodules: true` (tests.yml:7). #186 allows "no real leg repository … before Gate C". T015 later validates "the real exact assembled head using … required platform/CI" (tasks.md:107–108). |

### T011: restore/rollback rehearsal and publication (tasks.md:82–85)

| # | Requirement (cite) | Evidence that would satisfy it | Status |
| --- | --- | --- | --- |
| 36 | "Rehearse restoration/rollback of the local candidate and installed payload using preserved artifacts" (tasks.md:82–83). Gate B's "restore rehearsal" (plan.md:140). Rollback (plan.md:238–247). SC-005 (spec.md:103–104). "Additional profiles/workstations and actual installer rollback still need receipts" (preparation.md:36–37). | A rollback-rehearsal receipt: the candidate left unmerged, original development and installation restored from the preserved artifacts, the installed payload returned to its pre-install receipt state, and digests compared. | **NOBODY.** Its input, the Gate A writer's preserved artifacts, is IN PROGRESS. The October 4 snapshot restores (preparation.md:22–30) are "not an owner-coordinated freeze or live rollback". |
| 37 | "Verify user work/jobs/claims survive and no force push, destructive reset or workspace-pointer rewrite is needed" (tasks.md:83–85, plan.md:243–247). | A before-and-after inventory of branches, worktrees and dirty content; register claims and WIP pointers unchanged; a command log with no force push and no hard reset. | **NOBODY.** |
| 38 | "Publish Gate A/B evidence" (tasks.md:85): the Gate A part. | A refreshed `inventory.json` and public-safe receipt identities and digests on `004-migrate-to-triad-exec`. The private bundle stays host-local beside `prep-20261004T211123Z`, and its receipt goes in the private WIP repository (#186 body, "Rules in force"; #186 comment 6035767825). | **IN PROGRESS by lane 1's Gate A writer.** At 11:06Z its branch is at ff6f6a7 locally and not on the remote. |
| 39 | "Publish Gate A/B evidence" (tasks.md:85): the Gate B rehearsal part. | A receipt for the 7f84ca4 rehearsal, in the form of adopter-rehearsal.md. | **IN PROGRESS by lane 1's rehearsal writer.** At 11:06Z its branch is at ff6f6a7 locally and not on the remote. |
| 40 | "… and follow-up patch/commit inventory" (tasks.md:85). "Record their patches and resulting commits so real execution can apply the reviewed changes after source verification" (plan.md:125–126). | One table of every T006–T010 patch, giving the target leg, the rehearsed base commit, the resulting commit and the review reference. | **NOBODY.** |

### Cross-cutting conditions that no single task owns

| # | Requirement (cite) | Evidence that would satisfy it | Status |
| --- | --- | --- | --- |
| 41 | "Stop adoption on this refusal; resolve upstream and repeat into fresh local remotes before treating Gate B as passed" (plan.md:146–148). "Repeat the consumer rehearsal with fresh remotes after repinning. Gate B still requires the reviewed upstream fix and the remaining integration work, even though the separate candidate rehearsal now succeeds" (adopter-blocker.md:71–73). | A rehearsal that runs the consumer's pinned openRepoShape at a commit on its main (7f84ca4) into fresh remotes. The October 6 run against draft `91d5685` (adopter-rehearsal.md:4–7) does not count. | **IN PROGRESS by lane 1's rehearsal writer.** "after repinning" depends on line 13. |
| 42 | "Never use the live consumer as `--source` for this reproduction: local mode still pushes an adoption branch to its source clone if execution reaches that step" (adopter-blocker.md:52–54). | The receipt shows `--source` was the fresh isolated clone. Afterwards neither the live repository nor the remote has an `adopt/three-repo-shape` branch (adoption-plan.yaml:23). | **IN PROGRESS by lane 1's rehearsal writer.** #186 first act 3 restates the rule. At 11:06Z neither the shared repository nor the remote has an `adopt/` ref. |
| 43 | "do not patch the pinned submodule or adjust digests to manufacture success" (plan.md:113–114). "never patch `upstream/openRepoShape` in place or weaken verification" (tasks.md:51–52). "pinned standard copies/digests SHALL NOT be edited to make placement pass" (cap-spec:84). #186 first act 1: "`tree_sha256` RECOMPUTED …, never adjusted". | The repin's `tree_sha256` equals an independent recomputation at 7f84ca4, `tests/test_upstream_pin.py` passes in the required CI, and the submodule has no in-place edit. | **IN PROGRESS by lane 1's repin PR writer** (#188, not landed). #186 comment 6035767825 records that lane 3's independent recompute at 7f84ca4 matches `3be52767…`. Lane 3 holds the adversarial review. |
| 44 | "No real repository is created for a test" (plan.md:253). plan.md:107–108. FR-010 (spec.md:62–63). Without approval the migration "SHALL create no real leg repositories" (cap-spec:151–154). #186 rules: "no real leg repository, PR to a real leg, default-branch move or lane rebinding before Gate C". | A rehearsal receipt recording transport restricted to local files and refusing `gh`/`curl` shims (the form of preparation.md:67–70). Read-only lookups of the leg names. | **IN PROGRESS by lane 1's rehearsal writer.** At 11:06Z both leg names return HTTP 404, which means "not visible to the current credentials, not a guarantee of name availability" (preparation.md:53–55). |
| 45 | "Reviewed preliminary inventory, mapping and prerequisite availability from T001–T003 permit disposable provisional rehearsal while writers remain active" (tasks.md:159–161). | A reviewed, refreshed `inventory.json` (T001), together with lines 2–6. | **IN PROGRESS by lane 1's Gate A writer**, as the T001 inventory refresh. The committed inventory was observed at 2026-10-04T21:24:50Z (`observed_at`). |
| 46 | "reviewed follow-up patches" (plan.md:140–141). Implement "and review" the follow-ups "in the rehearsed arrangement" (plan.md:123–125). | A review record for each T006–T010 patch: reviewer, verdict and the commit reviewed. | **NOBODY.** No reviewer is named for T006–T010; lane 3's review covers #188 only. |

## What closes Gate B

The Dependencies section in tasks.md:162–165 says, verbatim:

> T004–T006 precede integration validation;
> T007–T010 may progress within the rehearsed topology after byte accounting.
> T011 closes Gate B. T012 requires Gate A/B and is the real-creation approval
> boundary.

The plan adds that "Mapping `check` alone does not satisfy this gate"
(plan.md:142) and that Gate B is not passed until the consumer rehearsal is
repeated into fresh local remotes after the upstream resolution
(plan.md:146–148, adopter-blocker.md:71–73). Gate B is recorded as open in
three places on ff6f6a7: inventory.json:513 `"gate_b_complete": false`,
verification.md:25 "Gate B remains open", and adopter-rehearsal.md:101–102
"Gates A/B/C are not completed by this rehearsal".

**Counts (46 lines):**

| Status | Lines |
| --- | ---: |
| EXISTS (3 on ff6f6a7; 1 on 004-migrate-to-triad-reads @ ae70dc556) | 4 |
| DECIDED | 1 |
| IN PROGRESS | 19 |
| NOBODY | 21 |
| BLOCKED | 1 |

The 19 IN PROGRESS lines are held as follows: lane 1's rehearsal writer 14,
lane 1's Gate A writer 3, lane 1's repin PR writer 2.

**NOBODY lines (21):**

- 10: proof that the rehearsal left the source unchanged and recoverable
- 17: the collisions the rehearsal materializes, with a reviewed patch for each
- 18: the shape-aware root workflow bootstrap in the rehearsed assembly
- 19: first-line guidance, `.specify` and paired feature selection verified
- 20: provenance correspondence and cross-leg link repair
- 21: explicit spec/amendment roots, local-root precedence and store selection
- 22: per-workstation protocol/command distribution check
- 25: the assembly entry point and payload-source resolution patches
- 26: one-liners resolving one code pin with no developer checkout
- 27: the 15-row compatibility matrix measured
- 28: names, counts, modes, hooks, receipts and all-or-none refusal unchanged
- 29: explicit roots in fixtures and hygiene tests
- 30: `tests/run.sh -k upstream_pin` passing in the rehearsed code leg
- 31: composed checks refusing absent context instead of skipping
- 32: code-leg CI and root exact-pin integration patches
- 33: every current CI job and platform policy kept
- 34: the composed state passing the required checks and the matrix locally
- 36: the restore/rollback rehearsal of the candidate and installed payload
- 37: work, jobs, claims and WIP pointers surviving with no force or reset
- 40: the follow-up patch/commit inventory
- 46: a review record for each T006–T010 patch

**BLOCKED line (1):**

- 35: the hosted-runner part of T010's verification. It waits on somewhere
  GitHub-hosted runners can check out the rehearsed commits before Gate C
  (inferred).

## Outside Gate B (for orientation)

These conditions sit next to Gate B but belong to other gates:

- **Gate A completion.** "complete Gate A preservation is required before real
  source freeze" (tasks.md:161). Gate A is not a precondition of the
  rehearsal, but line 36 uses Gate A's preserved artifacts.
- **Gate C.** "approval names the actual source/standard revisions, leg
  repositories, visibility and final plan; prerequisites, Gate A/B evidence and
  no-name-collision checks are current" (plan.md:161–163). Governance item 1.2
  runs "after Gates A/B" (openspec/changes/migrate-to-triad/tasks.md:11–14). The
  leg names and visibility are a confirmed Gate C input (line 1). The frozen
  source commit and the final mapping are not yet approved.
