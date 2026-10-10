# The composed candidate carrying every follow-up — October 9, 2026

**For:** Gate B of [tasks.md](tasks.md), under
[#186](https://github.com/opensoft/openRepoTools/issues/186). It answers item 3 of
section 7 of `gate-ab-evidence-2026-10-09.md` (branch `004-migrate-to-triad-rollback`
at `fa44d75`): "No composed candidate carrying every follow-up has run the suite."
No task is checked complete by this record, and it approves nothing.
**Writer:** lane openRepoTools-1, 2026-10-09: 01:47Z–02:42Z (r1), 13:29Z–18:20Z (r2), and
the classification from 21:56Z to 2026-10-10T02:4xZ.
**Evidence branch:** `004-migrate-to-triad-candidate`, from `main` `63810dd`.
**Private receipt ID:** `candidate-20261009-JR8YyA` (brett-wip `migration/openRepoTools/`).
It holds every script, log, patch and install snapshot named below. Machine paths stay
there.

**Two builds.** **r1** was built at 01:5xZ from PR #190 `dbc6837` and PR #191 `2411f40`.
Its composed run was stopped at about 20% by the 02:42Z checkpoint for an account swap.
**r2** is the candidate of record. It was rebuilt at 13:3xZ from the moved heads, #190
`b50f197` and #191 `13cc752`, on the coordinator's order. Everything below is r2's unless
it says r1.

**State: final for r2 (2026-10-10T02:4xZ).** All three suite runs finished:

| Run | Passed | Failed | Skipped |
| --- | --- | --- | --- |
| composed | 1411 | 5 | 0 |
| standalone | 1389 | 3 | 24 |
| no-submodule | 1168 | 6 | 242 |

- **Two failures are candidate defects with owners.** F1 is fixed in #191's next head.
  F2 is #193 item 14.
- **The rest are environment.** Each is shown the same on main, or in isolation
  (section 5).
- **Two inputs have moved since r2:** #191 to `6568f08` (with F1's fix), and T007's
  entry-point patch to v3 (`004-migrate-to-triad-installer` `4f773b8`). Neither is in
  this record (section 6).

## 1. Inputs

Every input was read without checking it out in any existing worktree. Patches were
taken with `git show <branch>:<path>`, and the PR commits with `git format-patch` from
the shared checkout.

| Input | Where | Identity |
| --- | --- | --- |
| Run C's rehearsed arrangement | private prep `work-20261008/rehearsal` (read-only) | source `837928a`, split `69b8924`, spec `593250d`, code `73b04d6`, nested openRepoShape `7f84ca4` |
| T006 patches (5) | `004-migrate-to-triad-root-guidance` `041a273` | each blob equals `465fa6d`'s; sha256 `cd69c2a9…`, `574c0df1…`, `a7f8521b…`, `74b98ff9…`, `c11070f0…`, as `gate-ab-evidence` records |
| T010 patches (2) | `004-migrate-to-triad-ci` `cc7c7a1` (r1); the branch is at `d28e2cc` for r2, with both patch blobs unchanged | code `tests.yml` `7ee3c6d0…`; assembly `composed.yml` `6ee09f00…` |
| T007 entry point | `004-migrate-to-triad-installer` `51993a4` | `t007-assembly-entry-point.patch` `361c037d…`, as `installer-2026-10-08.md` records |
| PR #190 | r2: `b50f197` (on origin as `feat/test-roots-manual-guard`, a fast-forward of the PR head). r1: `dbc6837` | r2: 4 commits on `c4864ac`: `c139e88`, `e3a76b5`, `dbc6837`, `b50f197` |
| PR #191 | r2: `13cc752`, Linux CI green. r1: `2411f40` | r2: 5 commits on `c4864ac`: `6337a52`, `e406e0e`, `ecd7aa4`, `2411f40`, `13cc752` |
| The shape's `bump-leg.py` | a clone of the rehearsal's openRepoShape mirror, in scratch | `7f84ca4` |

`assembly-0002` and `assembly-0003` were **not applied**. As `root-guidance-2026-10-08.md`
says, they pin the rehearsal's own leg hashes; the two pins were regenerated here with
`bump-leg.py` against this candidate's legs.

#191 will move again in T007's fix cycle. This record is at `13cc752`; a later head
needs a delta rerun.

## 2. How it was built

All of it ran in private scratch (`work-20261008/ort-triad-candidate/`):

- **Own copies first.** Bare copies, made with `--no-hardlinks`, of run C's two leg
  remotes, of its assembly branch and of its openRepoShape mirror. Every write went to
  these copies. In every clone the submodule URLs were set to them before any commit, and
  a `url.<copy>.insteadOf` rule sent `.gitmodules`' run C paths and the nested GitHub URL
  to the copies. r2 has its own set of copies, so r1's commits stay where they were.
- **No network.** `PATH` began with refusing `gh`, `curl` and `wget` shims that log every
  call; `GIT_ALLOW_PROTOCOL=file`. The shim log is empty.
- **Run C unchanged.** A listing of the rehearsal directory (type, mode, size, mtime of
  every entry) was taken before the work and compared after it (section 8).

### Apply order and results (r2)

Every patch was applied with `git am`. **Every one exited 0; no hunk needed a resolution,
and none was dropped.**

| # | Leg | Patch | `git am` | Commit | Tree |
| --- | --- | --- | --- | --- | --- |
| 1–4 | code, on `73b04d6` | PR #190's four commits | exit 0 | `b112e01`, `4ee37cf`, `e80350e`, `6e294fe` | `08d5b4ca` after the fourth |
| 5–9 | code | PR #191's five commits | exit 0 | `eab478f`, `85e6ffb`, `5758859`, `69b4785`, `b52df0a` | `cceeb37d` after the fifth |
| 10 | code | T006 `code-0001` | exit 0 | `085ec81` | `c3437ded` |
| 11 | code | T010 `t010-code-leg-tests-workflow.patch` | exit 0 | **`4dbcf6c`** | **`c0bedc53`** |
| 12 | spec, on `593250d` | T006 `spec-0001` (r1's commit; no spec input moved) | exit 0 | **`9e1d006`** | **`10256135`**, the tree T006 and T011 recorded |
| 13 | assembly, on `69b8924` | T006 `assembly-0001` | exit 0 | `4f1e522` | `5060f3be` |
| 14 | assembly | T010 `t010-assembly-exact-pin-job.patch` (`composed.yml`) | exit 0 | `738857c` | `7905d570` |
| 15 | assembly | T007 `t007-assembly-entry-point.patch` | exit 0 | `f4133d6` | `8b0c860b` |
| 16 | assembly | `bump-leg.py --leg spec --to 9e1d006…` | exit 0 | `f0a4feb` | `94e9d9be` |
| 17 | assembly | `bump-leg.py --leg code --to 4dbcf6c…` | exit 0 | **`5d92962`** | **`d263907a`** |

Steps 12–16 are r1's commits, reused: none of their inputs moved. Step 17 is new.

What was checked at each step:

- **The PR commits are the PR heads.** Every path #190 touches has `b50f197`'s blob after
  the stack, and every path #191 touches has `13cc752`'s blob. The exception is the one
  file both touch.
- **The one shared file.** Both PRs touch `tests/test_openrepotools_command.py`. On top of
  #190, #191 applied the same hunks as its own diff, at an offset. The hunk bodies are
  identical: 14 lines at `13cc752`, and 26 at r1's `2411f40`.
- **T006's `.gitattributes` and #190's decision agree.** #190 reads `.gitattributes` from
  the code root, and `code-0001` puts the monorepo's blob `3560973` there.
  `git check-attr eol` on `openRepoTools`, `park` and `tests/run.sh` in the leg gives
  `lf`.
- **The entry point is T007's.** `openRepoTools` at the assembly root is blob `4c2525d`,
  mode 100755, sha256 `3b0d59f5…`, as `installer-2026-10-08.md` records.
- **Clean text.** `git diff --check` exits 0 over the code range (`73b04d6..4dbcf6c`), the
  spec range and the assembly range.

The legs' commits were pushed to `main` of their own bare copies, as fast-forwards from
run C's heads. The assembly was pushed as branch `candidate-r2`. `bump-leg.py` ran with
`--local-remote-dir` set to the copies, a dry run first each time, all exit 0. It added
`Lane:` and `Co-Authored-By:` trailers. Its `NEXT … push` line was not followed.

### The candidate's identities

| Repository | Commit | Tree | Pinned digest (`sorted-ls-tree-r-v1`) |
| --- | --- | --- | --- |
| assembly (`candidate-r2`) | `5d9296216fbf8255440c315344f29ac2aa1c19f8` | `d263907a4ab2b675c9b5272a4c60ffb2ea65ce12` | — |
| spec leg | `9e1d006e2c870615f159ad1ebab719bb7b38cc2a` | `10256135f87ae4d05166d2c5934a152c42ce19ae` | `3a4a84beb20b343390f5bae64cb166df4d0cfd693baff6309fc13c8060d1c866` (T006's spec digest) |
| code leg | `4dbcf6ce40fe897a8caf770abc5cf55535b5f0b6` | `c0bedc535b4c69afc32e6235140a874c05821c3a` | `7a5dc958db2ea74213f604b883bc2bfd374960015313bd4de24494965ccc32a6` |
| code's nested openRepoShape | `7f84ca42ca86a8902928345109d2bf6bad87bd91` | — | unchanged from run C |
| r1, superseded | assembly `3bd95a7`, code `f0af7d9` (tree `a832c8a0`, digest `6550ae2e…`), spec `9e1d006` | | |

The commit hashes are this run's alone, because `git am` stamps a new committer and date.
The trees are what reproduce.

## 3. Bootstrap, validators and the composed job's own steps

| Check (in the assembly) | Result |
| --- | --- |
| `python3 scripts/bootstrap.py` | exit 0; "spec: on main at 9e1d006e2c87 (branch tip == pin)", "code: on main at 4dbcf6ce40fe (branch tip == pin)", `pins ok`, `manifest ok`, "bootstrap ok" |
| `make validate` (naming, manifest, pins) and `make pins` | exit 0 and 0. Both gitlinks equal their pins, both tree digests recompute, and all 11 copied shape files match `contracts/shape-pin.yaml` |
| `composed.yml`'s step "every context the composed run claims is here", run as written | exit 0 |
| `composed.yml`'s `validate-manifest.py`, then `validate-pins.py` | exit 0, exit 0 |
| A fresh recursive clone of the candidate from its bare copy, then `bootstrap.py` and `make validate` | exit 0 and 0. Spec `9e1d006`, code `4dbcf6c`, nested `7f84ca4`. `status --ignored` is empty |
| The assembly's `AGENTS.md` and `README.md` | 340 and 510 lines, exactly #190's assembly caps |

`.gitmodules` still names run C's local remote paths, as the adopter wrote them in the
rehearsal. A recursive clone that does not redirect them fetches from run C, whose
remotes lack this candidate's leg commits. A real leg is an https remote and does not
have this problem.

## 4. The install, compared with today's main

Both installs used the same disposable home path, rebuilt from one seed, so that
absolute paths written into `settings.json` and the receipt compare byte for byte.
- **Environment:** `env -i`, with `HOME`, every `XDG_*` variable and `TMPDIR` in scratch.
  `PATH` was the refusing shims, then `/usr/bin:/bin`. `GIT_ALLOW_PROTOCOL=file`.
- **The seed:** an unrelated `settings.json` (model, env, permissions, a status line, and
  `SessionStart`, `UserPromptSubmit` and `Stop` hooks of its own), a foreign command in
  `~/.local/bin`, and a foreign skill under each of the two skill roots.
- **The shims logged 0 calls**, in r1 and in r2.

| Stage | Source | Result (r2, 13:34Z) |
| --- | --- | --- |
| A | today's main `63810dd` (a shallow clone of `origin/main`), `./openRepoTools --install` | exit 0; `17 of 17 placed`; 29 `installed at`; both hooks merged; 29 receipt rows |
| B | a freshly seeded home; the candidate assembly root `./openRepoTools --install` (the T007 entry point) | exit 0. First line: "source: the code mounted at `<clone>/code`, opensoft/openRepoTools-code at 4dbcf6ce40fe… as `<clone>` pins it; every payload file was checked against that commit and nothing fetched". Then `17 of 17 placed`, 29 `installed at`, both hooks merged, 29 receipt rows |
| B2 | the candidate again, over B | exit 0; 31 `unchanged` (29 files and 2 hooks) |
| C | today's main again, over B: rollback by reinstall | exit 0; `openRepoTools: updated at …`, 30 `unchanged` |
| — | the candidate's `./openRepoTools --version`; `./openRepoTools nope` | "openRepoTools (opensoft/openRepoTools @ main)", exit 0; exit 2 |

**Every difference between A and B**, by path, type, mode and sha256 over the whole home:

| Path | A (main) | B (candidate r2) |
| --- | --- | --- |
| `~/.local/bin/openRepoTools` | 755 `47cfe74ea96e6ce9e56b47220a71e1de8c608af2f51f33cfdffa351410a4f373` | 755 `a6eda1f4b7b72a8e832f93185dc4604de66dab5a677472f57452b3ee09342588` |
| `~/.local/share/openRepoTools/installed.tsv` | 600, its `openRepoTools` row names `47cfe74e…` | 600, its row names `a6eda1f4…`; the UTC column differs too |

Nothing else differs:
- **The other 28 placed files** have the same path, mode and sha256.
- **`settings.json`** is byte-identical: the seed's model, env, permissions, status line
  and three hooks of its own, plus the same two entries the installer merges, at mode 600.
- **The receipt's name, destination and sha256 columns** differ in the `openRepoTools`
  row only.
- **The foreign command and both foreign skills** are untouched.

The installed `openRepoTools` (`a6eda1f4…`) is the bytes of `code/openRepoTools`, PR #191's
implementation at `13cc752`. It is not the root entry point (`3b0d59f5…`), so the entry
point handed over as T007 designed. r1 gave the same result with `2411f40`'s
implementation, `118cc2cc…`; between r1's and r2's candidate installs, that file and its
receipt row are the only differences.

**Rollback by reinstall (C) restores main.** C's whole-home listing equals A's except for
the receipt file's own digest. The receipt's name, destination and sha256 columns equal
A's; only the UTC stamps differ. This is the (c2) path of `gate-ab-evidence-2026-10-09.md`
section 2, repeated at this candidate's own commits, as its section 2 asked.

## 5. The suite: composed, standalone, and standalone without the dependency

**How the runs were made.** The three runs ran one after another, 13:33Z–18:20Z, from one
driver script. Each took the workstation lock on its own and released it before the next.
- **Environment:** `env -i` with only `HOME`, `PATH=/usr/bin:/bin`, `LANG=C.UTF-8`, the
  user names and the CI jobs' four `GIT_AUTHOR_*`/`GIT_COMMITTER_*` variables. So no
  `LANES_*`, `TMUX`, `CLAUDE_*` or workstation binding variable reached the suite.
- **Composed.** `tests/run.sh -rfEs` waited 5 minutes on the workstation census. As
  briefed, this writer then stopped its own waiter and ran `run.sh`'s exact pytest line
  under `flock` on the same lock, with `run.sh`'s run root.
- **Standalone and no-submodule.** `tests/run.sh -rfEs` itself started pytest in each.
- **The load average at each run's start** was 131.7 (composed), 6.9 (standalone) and
  8.6 (no-submodule).

| Run | Where, and the variables | Result | Time |
| --- | --- | --- | --- |
| **Composed** | `<assembly>/code`; `OPENREPOTOOLS_COMPOSED=1`, `OPENREPOTOOLS_ASSEMBLY_ROOT=<assembly>`, `OPENREPOTOOLS_SPEC_ROOT=<assembly>/spec` | **1411 passed, 5 failed, 0 skipped** (1416) | 1:48:00 |
| **Standalone** | a clone of the code leg alone, its dependency initialized; no `OPENREPOTOOLS_*` variable | **1389 passed, 3 failed, 24 skipped** (1416) | 1:00:08 |
| **No submodule** | a clone of the code leg alone, dependency not initialized ("the submodule really is not materialized", the job's own check); `tests.yml`'s workflow env, `OPENREPOTOOLS_CODE_ROOT=<clone>` and `OPENREPOTOOLS_COMPOSED=0` | **1168 passed, 6 failed, 242 skipped** (1416) | 1:31:30 |

**The skips are the designed ones.** The composed run skipped nothing, so no check went
green by skipping. The standalone run's 24 skips are:
- 10 for `README.md`, 3 for `AGENTS.md` and 1 for `CLAUDE.md`, each naming the assembly
  root it needs;
- 3 for `docs/README-lanes.md`, naming the spec root;
- 7 composed-acceptance tests of #191, which skip in standalone code.

The no-submodule run has the same 24, plus 218 that name
`git submodule update --init upstream/openRepoShape`. Inside the lane helpers' shell suite
in both leg runs, the three manual sections printed `skip … no spec root in this run`.
There is no `unbound variable` anywhere: `b50f197`'s guard holds, and the abort that
`dbc6837` had in a code leg does not occur.

**Against CI.** All three runs collected 1416 tests: main's 1296 plus #190's and #191's
additions. On CI the PR heads read:
- main `63810dd`: `tests` 1296 passed; `tests-no-submodule` 1084 passed, 212 skipped;
- #190 `dbc6837`: 1318 passed; 1105 passed, 213 skipped;
- #191 `2411f40`: 1379 passed, 7 skipped; 1165 passed, 221 skipped.

None of those jobs is composed.

### Every failure, classified

| # | Test | Runs | First assertion line | Class | Owner |
| --- | --- | --- | --- | --- | --- |
| F1 | `test_install_payload_source.py::test_r14_the_documented_upstream_skip_is_unchanged` | composed only | `KeyError: 'reason'` at `conftest.NEEDS_UPSTREAM.kwargs["reason"]` (line 1697) | **Candidate defect, new, from combining #190 and #191.** Under #190's conftest a composed run makes `NEEDS_UPSTREAM` `pytest.mark.usefixtures("required_dependency")`, a fixture that fails, not a `skipif`, so it has no `reason`. #191's test assumed a `skipif`. It passes standalone (both leg runs) | **#191.** Fixed by the T007 writer in `6fa3b43`, inside #191's head `6568f08`: the test now reads the command from conftest's own text, which names it in both modes. Not re-run here |
| F2 | `test_repo_hygiene.py::test_agents_md_names_the_pin_rules` | composed only | `assert 'Never edit anything under \`upstream/openRepoShape\` in place' in "Read AGENTS-shape.md first …"` | **Candidate defect, known: #193 item 14**, predicted by lane 3. T006's `assembly-0001` rewrites the two `AGENTS.md` lines the test checks, and in the composed run the test reads the assembly's `AGENTS.md` | the decision is pending with lane 1's coordinator |
| F3 | `test_lane_helpers_suite.py::test_the_lane_helper_suite_passes`: shell `FAIL …with clause (c)'s directory and window in the tail` and `FAIL the row's stamp states clause (c)'s two facts for a person, in its TAIL` | all three | `expected to contain [; dir <sandbox HOME>/projects/repoA; window ]`, the sandbox HOME being `<run root>/tmp/tmp.*/home`; the row ends `…; dir <sandbox HOME>/projects/repoA; ... \|` | **Environment, pre-existing: #180.** The register row's stamp is cut, and under `run.sh` the directory sits under the long run root `~/.local/state/openRepoTools/tmp/<UTC>-<pid>/tmp`, so the expected text falls past the cut. **On main `63810dd` the same three FAIL.** The shell suite ran directly, at a run root of the same 71 characters as the standalone run's, under one `flock`: `4595 passed, 3 failed, 0 skipped`, F3's two and F4. CI's runner has a short `TMPDIR` and passes them. | #180 |
| F4 | the same shell suite: `FAIL …having found the checkout by its real directory name, not the typed one` | standalone and no-submodule only | `expected to contain [dir <sandbox HOME>/projects/repoCase;]`; the row ends `— lane-start on Eagle: window renamed, no launch; dir ... \|` | **Environment, pre-existing: #180, the same cut.** The run root here was one character longer than the composed run's (`<pid>` had 7 digits, against 6), and this third row crosses the cut at that length | #180 |
| F5 | `test_run_wrapper.py::test_a_killed_run_removes_its_run_root_and_stops_the_suite[flock-2-130]` and `[mkdir-lock-2-130]` | all three | `subprocess.TimeoutExpired: … tests/run.sh … timed out after 30 seconds` | **Environment, of this writer's harness, and not load.** The driver was launched as an asynchronous command of a non-interactive shell, so every run inherited SIGINT *ignored*, and bash cannot trap a signal ignored at entry. Only the SIGINT cases failed; the SIGTERM cases passed. Measured isolated at load 42–61: with SIGINT at its default, 4 passed in 1.9 s; launched the way the runs were, the same 2 failed with the same timeout. Main `63810dd` behaves identically (4 passed, then 2 failed) | none for the candidate. The test could start its wrapper with both signals at default, as `test_openrepotools_command.py::test_a_run_killed_mid_placement_leaves_no_temporary` already does (`preexec_fn=default_signals`, whose docstring names this very trap) (follow-up 4) |
| F6 | `test_supervised_restart_regressions.py::test_restart_observer_confirms_late_uuid_prepared_by_real_child[live]`, `::test_respawn_restores_configured_roots_in_new_pane`, `::test_completed_observer_cleanup_never_signals_saved_pid[signal]` | no-submodule only | `subprocess.TimeoutExpired: … lane-handoff --supervise …` / `Failed: observer never confirmed readiness` | **Environment: timing under load.** These files and `lane-handoff` are byte-identical to main's. All three passed in the composed and standalone runs of the same code. Rerun isolated at load 48–54: all three passed, once with SIGINT at default and once ignored. But a sibling, `test_completed_observer_cleanup_never_signals_saved_pid[exit]`, failed once in that rerun. So these tests are timing-sensitive on this bench, independent of the candidate | none for the candidate; the flake is pre-existing (follow-up 5) |

**Lane 2's reading** (#186 comment 6087267593) **checked against the logs.** Its counts are
right for all three runs, and so is its S2 finding (no abort on r2). One refinement and
one correction:
- **The lane-suite FAILs** are all #180 row-stamp cases, as lane 2 says. They are 2 in the
  composed run and 3 in each leg run; the third is F4.
- **The `test_run_wrapper` pair** is not a load timeout. It is the inherited ignored SIGINT
  of F5, and it fails the same way on main.

**One other test sends SIGINT:** `test_a_run_killed_mid_placement_leaves_no_temporary`.
It resets both signals in its child for exactly this reason, and it failed in none of the
three runs.

### r1's stopped composed run

It reached result 288 of 1408 before the 02:42Z checkpoint stopped it. Its one failure, at
result 211, was F1. That test alone, rerun in r1's tree, failed the same way. So it was
not the `$ln_doc` abort, which only a code leg without a spec root can reach; the composed
run has one.

## 6. What this proves for Gate B, and what it does not

**What it proves:**
- **Every recorded follow-up composes.** T006's three portable patches, T010's two, T007's
  entry point, #190 at `b50f197` and #191 at `13cc752` stack onto run C with no conflict
  and no resolution. That is the stack `gate-ab-evidence` section 5 only checked as
  text.
- **The result is a valid triad.** It bootstraps and validates: legs at their pins, both
  digests recomputed, all 11 copied shape files intact, and `composed.yml`'s own
  context and validator steps green.
- **The whole canonical suite has run on it.**
  - Composed at the exact pins, nothing skipped: **1411 of 1416 pass**.
  - Of the 5 failures, 2 are candidate defects with owners. F1's fix is in #191's head
    `6568f08`. F2 is #193 item 14, with a decision pending.
  - The other 3 are this bench's environment. F3 is #180, the same on main (section 5).
    F5 is this writer's harness, the same on main.
- **The standalone code leg behaves as T009/T010 designed.** Its document checks skip,
  naming the root they need. Its dependency checks skip, naming the command. Nothing
  aborts. It has no failure of its own: its 3 and 6 failures are F3–F6, all environment.
- **The install from the assembly root hands over to the code leg.** It places the same
  29 files as today's main, every one byte-identical except the implementation itself,
  and merges the same hooks into a byte-identical `settings.json`. A reinstall from main
  restores main.

**What it does not prove:**
- **Hosted CI.** Not the code leg's `tests`, `tests-no-submodule`, `tests-windows`,
  `parse-macos` or `tests-macos` jobs, and not `composed.yml` checking out over https.
  They need the real legs, which only exist after Gate C (checklist line 35).
- **The real legs and remotes.** This used local bare copies: https `.gitmodules`,
  `bump-leg.py` against the real legs, and the raw and `gh` one-liners against GitHub
  are T015's.
- **The final heads.** #191 is now `6568f08`, which carries F1's fix (`6fa3b43`) and
  changes the implementation `openRepoTools` (159 changed lines since `13cc752`).
  T007's entry-point patch is now v3 (`4f773b8`). #190 landed as `f87fd5a`, whose
  `tests/` equal `b50f197`'s, so that leg input is unchanged.
  - Neither moved input ran here: not the suite, and not the install comparison.
  - The T007 writer did run part of it (`installer-2026-10-08.md` at `3cca1e7`).
    - Its strict composed run of the install suites, `repo_hygiene` and
      `openrepotools_command` at `6568f08` with root v3: 429 passed, 1 failed. The one
      is `.gitattributes`: that code leg did not carry T006's `code-0001`.
    - CI on `6568f08`: `tests` 1416 passed, 9 skipped.
    - Neither is this candidate, and neither is the full composed suite.
  - The record owes a composed rerun at `6568f08` with T007 v3. The rebuild takes about 5
    minutes: the code leg plus a regenerated code bump, and the assembly with the v3
    patch in place of v1.
  - The full composed run took 1:48 at load 130 here. CI's `tests` takes 45–48 minutes.
    Add the wait for the lock.
  - A scoped composed rerun of the install modules (`test_install_payload_source.py`,
    `test_openrepotools_command.py`, `test_install_*`), plus the install comparison, is
    about 15–20 minutes.
- **A clean composed green.** Gate B's "passing compatibility test matrix" is not met
  until the composed rerun at `6568f08` shows F1 gone and F2 is decided. F3 and F5 do not occur on a CI
  runner (main's own `tests` is 1296 of 1296 there).
- **The bash 3.2 parse of the root entry point.** `parse-macos` parses the
  implementation, not the entry point.

## 7. Follow-ups

1. **#191 carries F1's fix** (`6fa3b43`, in its head `6568f08`: the r14 test reads
   conftest's text). The composed rerun at `6568f08` with T007 v3 is owed (section 6).
2. **F2, #193 item 14:** decide whether `test_agents_md_names_the_pin_rules` or T006's
   `assembly-0001` gives, before the composed run is the record.
3. **#180:** under `tests/run.sh`'s run root the row-stamp cases fail locally. There are 2
   at a 70-character run root and 3 at 71, the third being F4. CI is unaffected. Today
   any local full run is red on them, main included.
4. **`test_run_wrapper.py`:** start the wrapper with SIGINT and SIGTERM at their defaults,
   as `test_openrepotools_command.py` does. Otherwise a suite launched from a background
   shell reports two false failures (F5), on main too.
5. **`test_supervised_restart_regressions.py`'s observer tests are timing-sensitive** on a
   loaded bench (F6). They are pre-existing and unchanged by the candidate.
6. **Launch any rerun of this candidate with SIGINT at default (F5).**
7. **The rehearsed split's `.gitmodules` names run C's local remote paths.** A real
   adoption writes https URLs, so nothing is owed unless the rehearsal is reused for
   another candidate.

## 8. Acts outside scratch, and log SHA256s

**Every write went to private scratch** (`work-20261008/ort-triad-candidate/`), with these
exceptions, listed so nothing is hidden:
- **The evidence worktree.** `lane-worktrees add openRepoTools-1 ort-triad-candidate`
  made it (exit 0): the worktree, its new branch and one record in lane 1's host-local
  tree inventory.
- **This branch.** Its commits, and fast-forward pushes of `004-migrate-to-triad-candidate`.
- **In the shared checkout, reads only.** Fetches (remote-tracking refs only),
  `git show`/`format-patch` reads, and one shallow `file://` clone of `main` from its
  object store.
- **`gh`, reads only.** PR views, run lists, CI job logs, and issues #180, #184 and #193.
- **`tests/run.sh`'s own conventions.**
  - Run roots under `~/.local/state/openRepoTools/tmp/<UTC>-<pid>/`, each removed when
    its run ended. The r1 composed run's root was removed by hand after this writer
    stopped that run at the 02:42Z checkpoint.
  - Bytecode under `~/.cache/openRepoTools/pycache`.
- **The workstation lock.** This writer held `/tmp/openrepotools-pytest.lock`:
  - r1 composed, 02:10:40–02:42:37Z (stopped);
  - r2 composed, 13:59:33–15:47:49Z;
  - through `tests/run.sh`, the r2 standalone and no-submodule runs, 15:4xZ–18:20Z;
  - main's lane suite at the same run-root length, about 22:07Z to 23:09:57Z.

  It was released between runs. The isolated reruns of F5 and F6 (2 seconds to 2
  minutes 16 seconds each) ran without it, under the coordinator's rule for runs of about
  two minutes. The r1 test collection and F1's single-test reproduction took it with
  `flock -w 600`.
- **A stray file moved at once.** A temporary file was written into the private
  `work-20261008/` directory by mistake, outside the rehearsal tree, and moved into scratch
  within a minute.
- **The receipt and the comment.** One commit to brett-wip `main` (`git add -- <receipt
  dir>`), from a single-branch clone in scratch, never the shared checkout. One comment
  on #186.

**Real surfaces, before (2026-10-09T01:59Z) and after (2026-10-10T02:44Z):**
- the real home's 29 installed files (path, mode, sha256), its receipt and its
  `settings.json`: **unchanged**;
- `~/.agents/workspace.yaml` (size, inode, mtime, mode; its contents not read):
  **unchanged**;
- run C's rehearsal directory, as a whole-tree listing (type, mode, size, mtime of 1830
  entries): **byte-identical** before (2026-10-09T01:47Z) and after (2026-10-10T02:44Z).

**No network:** the refusing shims logged no call in any build, install or suite step.
Nothing was pushed to run C. No real repository was created, and the register was not
written.

| Log (in the receipt's `logs/`) | SHA256 |
| --- | --- |
| `41-r2-code-leg.log` | `053af3830c118885238f1f50dfc2ff50bf29c2f4ac9db9cc6d539f407633d12b` |
| `42-r2-assembly.log` | `7d8f086587e63e4a78c93cc2db5d1f4996aab4a983a28e0ab389d4265c7ad272` |
| `43-r2-clones-and-steps.log` | `295db90bcfe12c626919d0a49710d8e98e080851997deab68853d80bf03bd59b` |
| `run-51-r2-composed.log` | `d57492a6be710493c51b052eef14119c248d0d5de29f8d58f2dc8a99e7b1c5c6` |
| `run-52-r2-standalone.log` | `18562f7cf544179060917128660fef4d535b95e0ac94240cd101d862fd5171da` |
| `run-53-r2-nosub.log` | `1b9cc2668593e7c44075528acef9cbfc4540a12fe2a5f2a055819131f6e7d366` |
| `44-r2-install-check.log` | `ba9e6df4f0aff84e5e362c3de35bd236d45073e5b3b1aabfbe309f9d27ae4c3d` |
| `45-r2-install-compare.log` | `eb0de425bfee2214d39490498e5e0a2ed5fc8e331258cc48c498b8033cbe20d9` |
| `60-r14-classification.log` | `920cf5db6cdbf47b03294c022d5e15087fed61e30edabde2958ab39e236af088` |
| `61-rerun-run-wrapper.log` | `5ca28af487ca34b6957b7601672005a067bcc598358bfa209ce185d0616cefb4` |
| `62-rerun-supervised-restart.log` | `e6409f8fdd7d4a96ed8c158d85ad00bde77a6e214fec43bedb89f5ff8211c927` |
| `63-run-wrapper-on-main.log` | `f5a3724535d12ff887fc44613cf011dc2adc17d6a7416f6cebed068b32b4b29f` |
| `64-main-lane-suite-at-length.log` | `d07652d526e131d271347138c7c204efb3c15c86445e6b7f8c37a36de73dcdb9` |
| `killed/run-21-composed.r1-stopped-at-checkpoint.log` | `60c90271e3fb6acaa78ebbfd56b3483598b03cd67e5cfb19711ae0036e1daf7a` |
| `killed/r1-composed-F211-repro.log` | `3df58782bf4a317516cb5f098c2b8460e63e119e8fb5a98efb7159dd6f3cd750` |
| `10-code-leg.log` | `70f1af98b15b7f52fff2c47de6a68930f156138cfcfceacaf813382fac84a378` |
| `12-assembly.log` | `256decaff94d57c4fc14ddf0a6e03dbfa39c485e3056ccec66c65a68100d119d` |
| `13-bump.log` | `5523b0e9df43ff2f11b7207e901e1bf69e084dc461752a36b17104b2b458dfed` |
| `32-install-compare.log` | `c4f48b9f4649fb775874fa1bb962773a269778dc28eb92e6c4e28420d7cc4108` |
| `rehearsal-listing-before.txt` | `1dbf1ae38a9f98fac7b9f1ded1f0b6b2d699cc8ecb7b4f914c2cd5171f412038` |
| `rehearsal-listing-after.txt` | `1dbf1ae38a9f98fac7b9f1ded1f0b6b2d699cc8ecb7b4f914c2cd5171f412038` |
| `network-shim-calls.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

This record authorizes no conversion, repository creation, merge, default-branch move or
lane rebinding.
