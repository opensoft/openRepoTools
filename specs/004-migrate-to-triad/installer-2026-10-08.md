# Installer payload source and the assembly entry point: October 8–9, 2026

**Task:** T007 and T008 of [tasks.md](tasks.md), under [#186](https://github.com/opensoft/openRepoTools/issues/186). Neither task is checked complete by this record.

**Code:** [#191](https://github.com/opensoft/openRepoTools/pull/191), branch `feat/installer-payload-source-resolution` (head `8246983`, based on `c4864ac` with main `f87fd5a` merged in as `45979a4`).

**Assembly entry point:** [patches/t007-assembly-entry-point.patch](patches/t007-assembly-entry-point.patch). It cannot land on `main` before the split, because its path is the implementation's.

**Writer:** lane openRepoTools-1.

## The rehearsed arrangement relied on

Run C (`/workspace/projects/.openrepotools-private-prep/work-20261008/rehearsal/README.txt`), cloned out of it read-only:

| Repository | Commit |
| --- | --- |
| Source (`main` when cloned) | `837928a1029ac53b050a9bdcbc0ef4055b10719b` |
| Assembly split (`adopt/three-repo-shape`) | `69b89245029d0339afd3317df7c9b1b3bbaf7fc1` |
| Spec leg | `593250d600ca291f610671d993c2a6fc36cd690e` |
| Code leg | `73b04d637634f897ad24e22ee4c12bed287172d6` |
| Code's nested openRepoShape | `7f84ca42ca86a8902928345109d2bf6bad87bd91` |

Clone commands:

```sh
git -c protocol.file.allow=always clone -b adopt/three-repo-shape <rehearsal>/source <clone>
git -C <clone> -c protocol.file.allow=always \
  -c url.<rehearsal>/mirror/openRepoShape.git.insteadOf=https://github.com/opensoft/openRepoShape.git \
  submodule update --init --recursive
```

The brief named run B (split `2726d3a`, code `6d52162`, spec `558a12b`). The 2026-10-08 bench restart wiped it from `/tmp`. Before run C existed, this writer rebuilt run B in its own scratch to see whether it reproduces. The rebuild used the same tool (`adopt-project.py` at `7f84ca4`), the same published plan (`004-migrate-to-triad-rehearsal` at `36c0324`), the same source (`e43b243`), local bare remotes, and refusing `gh`/`curl` shims (zero calls).

- `execute` exited 0 with the same 45/49/6/0 accounting and 18 added paths.
- Spec reproduced as `558a12b` and code as `6d52162`, byte for byte.
- The split (`fea6ad8`) differed from `2726d3a` only in its commit time and in three files that embed local paths: `.gitmodules`, `shape/README.md` and `shape/AGENTS.md`.

Run C, which the coordinator made the arrangement of record, superseded it.

### The pin grammar validated

This is `contracts/code-pin.yaml` as run C's adopter writes it. It is read with `read` and `case`; there is no YAML runtime.

| Field | Required value |
| --- | --- |
| `schema_version` | `1` |
| `kind` | `pinned_contract_manifest` |
| `leg_role` | `code` |
| `source_repository` | an owner/name slug; never inferred by appending `-code` |
| `submodule_path` | one path segment |
| `commit` | 40 lowercase hex |
| `revision_kind` | `commit` |
| `digest_algorithm` | `sha256` |
| `digest_definition` | `sorted-ls-tree-r-v1` |
| `digests.tree_sha256` | 64 lowercase hex |
| `verify_pin`, `resync_runbook` | present |

Each key that is read must appear once. The file must be LF-only, quotes must close, and backslashes are refused.

## T007: the assembly entry point

- Commit `6acc147f751e5a2ca57b4814395769b7b75b339e` sits on `69b8924` in the writer's clone, on branch `t007-assembly-entry-point-v3`.
  - Tree: `87782af2ff3075284682f02fa41763d5df7112ff`.
  - `openRepoTools`: blob `ff432c6dc189ce272e778a89e375076094737b48`, mode 100755, sha256 `8248224d3bb425f69a944a41cdfe0a68f0b449d13978f67c76b6bc5a0a73a773`.
  - The patch file's sha256 is `67d8e7ce8b0f7008d2151a44c0eabaf74cda7cd2697c6e09ee7da0c341c671b5`.
  - `git am` of the patch on a fresh clone of run C's split reproduces tree `87782af` exactly.
  - History:
    - v1, `a02a45c` (tree `a9fa46e`): the first version.
    - v2, `8ed83b7` (tree `79db0a4`): `recorded_gitlink` reads the gitlink with `read` instead of `awk` (see the runs below).
    - v3, this commit: on the remote path, the gitlink is now checked against the pin BEFORE any implementation is fetched or run. This answers lane 3's review of the v2 patch (#191 review 5471121210, T3), which found a stale or rolled-back pin running whichever installer it selected, with a misleading refusal.
- **In a checkout,** it requires the pin (strict grammar), the gitlink (index first, then HEAD) and `code/openRepoTools`'s raw bytes (`hash-object --no-filters`) to name one commit. Then it `exec`s `code/openRepoTools` with every argument. That is the same process, so the exit status, signals and the implementation's own temporary-file cleanup are the implementation's. There are no temporaries of its own.
- **Anywhere else** (stdin, or a copy of the file on its own), it does four things:
  - it resolves `OPENREPOTOOLS_REF` once, `gh` first and `curl` second;
  - it reads `contracts/code-pin.yaml` at that commit;
  - it reads the gitlink at the pin's `submodule_path` in that commit (one level of the tree, by `gh api --jq`, or by `curl` and `jq`). It refuses, naming both commits and with "nothing ran", unless the gitlink is the pinned commit;
  - it fetches `openRepoTools` from the pin's `source_repository` at the pinned commit (the file must begin `#!`);
  - it runs it from stdin, as the one-liners always ran it, with `OPENREPOTOOLS_REF` set to the resolved commit, so the implementation reads the same pin and checks it again.
- **It has no installer mechanics.** It does no placement, receipt, merge or retirement.
- **It assumes nothing the legs may not carry.** That covers `.gitattributes`, README, AGENTS and LICENSE (T006 §10.2).
- **It is bash 3.2-clean.** Arguments are forwarded as `${1+"$@"}`, because a bare `"$@"` under `set -u` is unbound in 3.2.
- **Its pin reader is a deliberate copy** of the implementation's (10 definitions: three character constants, the six pin-reader functions and `recorded_gitlink`). `test_r15_composed_the_root_entry_points_pin_reader_is_the_implementations` fails when the two differ.

**Rehearsal-only pin moves (not part of the patch).**

- Openrepotools' PR #191 was applied to code `73b04d6` in a clone. It was pushed only to the writer's own bare copy of the code remote, never to run C.
- The standard's `scripts/bump-leg.py` (tool `7f84ca4`, with `--local-remote-dir` pointing at that copy) made the lockstep commits. Its validators printed `pins ok` and `manifest ok` and recomputed both digests:
  - on `t007-assembly-entry-point`, `9321107` moved the code pin to `ecb4ef3` (PR at `e406e0e`), and `58e3ac5` moved it to `d12345b` (PR at `ecd7aa4`);
  - on `t007-assembly-entry-point-v2`, `7bbd60b` moved it to `ea17f30` (PR at `2411f40`), then `e5a901e` and `316aed6` to the round-1 heads;
  - on `t007-assembly-entry-point-v3`, `4c6a0b7` moved it to `fa460f2`. That commit is the whole code leg as the PR head `6568f08` has it, merged with main `f87fd5a`. It includes #190's test roots, and every one of the leg's paths is the PR head's blob.
- Each bump printed bump-leg's `NEXT … push -u origin …` line. It was deliberately not followed.
- The clone's push URL is disabled.

### The one-liner contract

| Command line | What it resolves |
| --- | --- |
| `curl -fsSL https://raw.githubusercontent.com/opensoft/openRepoTools/main/openRepoTools \| bash -s -- --install` (README:228; openRepoShape's `--install` pointer, openRepoShape:280 at `7f84ca4`, byte for byte) | 1. The root entry point at `main`.<br>2. `main` resolved once to assembly commit *A*.<br>3. `contracts/code-pin.yaml` at *A*.<br>4. The gitlink at `submodule_path` in *A* must be `commit`, or nothing runs.<br>5. `openRepoTools` from `source_repository` at `commit`.<br>6. That implementation, with `OPENREPOTOOLS_REF=A`, resolves *A* (a commit, which cannot move), lists *A*'s tree, re-reads and re-checks the pin, checks the gitlink, confirms the commit exists in `source_repository`, fetches the 23 payload files from there, and places 29 files and 2 hook entries. |
| `gh api repos/opensoft/openRepoTools/contents/openRepoTools -H 'Accept: application/vnd.github.raw' \| bash -s -- --install` (README:236–237) | The same, through `gh`. |
| `./openRepoTools --install` in an assembly checkout | Checks that pin, gitlink and implementation bytes agree, then `exec`s `code/openRepoTools`. The implementation checks every payload file against the pinned commit and copies offline. |
| `openRepoTools --install`, installed in `~/.local/bin` | The implementation alone. Its default `REPO` is the assembly, which it resolves itself. It never needs the root file or a checkout again. |

With run C's identities, *A* = `69b8924` and the pin names `opensoft/openRepoTools-code` at `73b04d6`. `73b04d6` predates T007, so the real cutover must pin a code commit that carries this change. That is T015's to verify at the assembled head.

Transcript of row 3 in the writer's clone (assembly `7bbd60b`, code pin `ea17f30`), into a throwaway `HOME` with `gh`/`curl` shims that log and refuse:

- exit 0, and **0 network calls**;
- first line: `openRepoTools: source: the code mounted at <clone>/code, opensoft/openRepoTools-code at ea17f302310fa75fdf61ad7199912a74971513bd as <clone> pins it; every payload file was checked against that commit and nothing fetched`;
- 29 `installed at` lines and 29 receipt rows;
- the installed `openRepoTools` is byte-identical to `code/openRepoTools`, the implementation and not the root file;
- `--version` prints `openRepoTools (opensoft/openRepoTools @ main)`;
- `./openRepoTools nope` exits 2.

**Against T006's README sentence** (root-guidance-2026-10-08.md §10.9: "the `openRepoTools` they fetch is this root's entry point, which hands over to the installer `code/openRepoTools` at the commit this root pins"), the contract matches, with two precisions:

1. Remotely, the implementation is fetched from the pin's `source_repository` at the pinned commit, which is the repository `code/` mounts.
2. In a one-liner run, `--version` prints the resolved commit rather than `main`, because the handover freezes `OPENREPOTOOLS_REF`.

## T008: the compatibility matrix

The tests are in `tests/test_install_payload_source.py` on #191. The fixtures build their own GitHub out of bare repositories, answered by one fake for `gh api`, `gh repo` and `curl` that runs `git` and logs every request. There is no real `gh` or `curl` on `PATH`, and every `$HOME` is temporary.

| # | Row | Tests | Base `c4864ac` | After | Composed (run C clone) |
| --- | --- | --- | --- | --- | --- |
| 1 | Raw/gh one-liners | `test_r01_the_one_liner_against_a_single_repository_installs_as_before`; `test_r01_the_one_liner_against_an_adopted_assembly_installs_the_pinned_code[gh,curl]`; `test_r01_composed_the_documented_one_liners_resolve_through_the_root_entry_point[openRepoShape,gh]`; `test_r01_composed_the_root_entry_point_delegates_locally`; `test_r01_composed_a_signal_reaches_the_implementation_and_its_temporaries_go` | pass / 2 red / skip | pass | pass |
| 2 | Offline local single / adopted checkout | `test_r02_a_complete_single_repository_tree_installs_offline_byte_for_byte` (sentinel REPO/REF, zero requests); `test_r02_an_adopted_checkout_installs_its_pinned_code_offline` | pass / red | pass | pass |
| 3 | Explicit local code feature | `test_r03_an_explicit_code_feature_checkout_installs_its_own_bytes_and_names_them`; `test_r03_an_incomplete_code_feature_checkout_is_refused_not_completed_from_elsewhere` | 2 red | pass | pass |
| 4 | Installed reinstall / skill-only | `test_r04_an_installed_copy_reinstalls_from_the_adopted_source_without_any_checkout`; `test_r04_an_installed_copy_on_a_single_repository_keeps_the_sibling_rule` | red / pass | pass | pass |
| 5 | Override / adopted fork | `test_r05_a_single_repository_fork_named_by_the_override_installs_as_before`; `test_r05_an_adopted_fork_follows_its_own_pin_not_a_guessed_code_name` | pass / red | pass | pass |
| 6 | Branch, tag, commit, slash refs | `test_r06_every_ref_form_is_resolved_once_and_every_payload_names_one_commit` (4 forms × 2 layouts) | 8 red | pass | pass |
| 7 | Branch moves between downloads | `test_r07_a_branch_that_moves_between_downloads_never_mixes_versions[adopted,single]` | 2 red (single installed mixed versions) | pass | pass |
| 8 | Missing pin (single) / partial or wrong pin | `test_r08_a_single_repository_without_a_code_pin_is_permitted`; `…an_adoption_manifest_without_a_code_pin_is_refused`; `…a_malformed_code_pin_is_refused_never_read_as_a_single_repository` (19 malformations); `…a_pin_the_gitlink_disagrees_with_is_refused`; `…a_pin_naming_a_commit_its_repository_lacks_is_refused` | pass / 22 red (base exited 0 installing the assembly root's decoys) | pass | pass |
| 9 | API answer missing/malformed, auth, transport | `test_r09_an_api_failure_is_a_refusal_never_a_fallback_to_a_single_repository` (5 steps × 401/403/404/transport/garbage, both transports) | 25 red (decoys installed) | pass | pass |
| 10 | Changed gitlink / payload, incomplete local set | `test_r10_a_local_gitlink_that_disagrees_with_the_pin_is_refused_before_staging`; `…a_changed_local_payload_is_refused_before_staging`; `…an_incomplete_local_adopted_payload_is_refused_without_a_fetch` | 3 red | pass | pass |
| 11 | Missing command/skill/alias, failed merge | `test_r11_a_payload_file_missing_from_the_pinned_code_changes_nothing[park,skills/restart/SKILL.md,commands/swap.md]`; `test_r11_a_settings_merge_that_cannot_be_computed_changes_nothing` | 4 red | pass | pass |
| 12 | Modes, receipts, targets, foreign files, hooks | `test_r12_an_adopted_install_keeps_modes_receipts_targets_and_what_is_not_ours` | red | pass | pass |
| 13 | WIP init / template lookup | `test_r13_wip_init_takes_the_standard_from_codes_dependency_pin_not_the_assemblys` | red (seeded from the assembly's decoy pin commit) | pass | pass |
| 14 | Missing nested dependency | `test_r14_with_no_nested_standard_anywhere_the_dependency_pin_alone_selects`; `test_r14_the_documented_upstream_skip_is_unchanged`; `test_r14_composed_acceptance_requires_the_nested_dependency` | red (seeded from `main`) / pass / skip | pass | pass |
| 15 | bash 3.2, Windows/WSL | `test_r15_the_adopted_path_holds_under_macos_one_true_awk`; `test_r15_the_installer_uses_nothing_bash_3_2_lacks`; `test_r15_the_three_lists_stay_one_line_arrays_a_consumer_parses`; `test_r15_composed_the_root_entry_points_pin_reader_is_the_implementations`; `test_r15_composed_the_root_entry_point_parses_and_uses_nothing_bash_3_2_lacks` | red / pass / pass / skip / skip | pass | pass |

The module is `WINDOWS_SKIP`, like every bash-driven test here. The composed tests skip in standalone code, and under `OPENREPOTOOLS_COMPOSED=1` (T009's convention) they fail instead.

### Runs

Locked runs used `tests/run.sh`'s own invocation under its lock. That is the coordinator's deviation for a census that never reaches zero. They ran with `PATH=/usr/bin:$PATH`, because this profile's `~/bin/python3` is a venv without pytest. Runs marked "unlocked" are scoped proofs of about two minutes, run under the coordinator's rule of 2026-10-09, with HOME, TMPDIR, `--basetemp` and `PYTHONPYCACHEPREFIX` all in the writer's scratch.

| Run | Code | Selection | Result |
| --- | --- | --- | --- |
| Red at base, 2026-10-08T21:04–21:10Z | `6337a52` (installer `c4864ac`) | the module | **75 failed, 8 passed, 6 skipped**. The 8 are the single-repository preservation tests, two static checks and the documented-skip check; every red was checked against its first failing assertion. |
| Green | `e406e0e` | module + `openrepotools_command`, `install_skill_and_hook`, `install_by_rename`, `wip_init` | **318 passed, 7 skipped** (the composed cases) |
| CI on `e406e0e` | | | `test_the_installer_reaches_only_this_repository` failed. Every fetching line must name `$REPO`; the helpers took the repository as an argument. Fixed in `ecd7aa4` (one current source, `${PAYLOAD_REPO:-$REPO}`), with no behaviour change. |
| Green with hygiene | `ecd7aa4` | the above + `repo_hygiene`, `upstream_pin` | **479 passed, 5 failed, 7 skipped**. All 5 are `test_wip_init_and_the_lane_helpers_read_one_pointer_file_the_same_way` cases whose failing assertion is the exit status of `lanes-edit.sh`, which is unchanged from base, as are its test and conftest. They passed in the green run above. This session inherits `LANES_WORKSPACE_ROOT` and other `LANES_*` binding variables, and with those unset 3 still fail on workstation state. CI's clean runner is the record. |
| Composed, strict | entry point `a02a45c` + code `ecb4ef3` | the module | **90 passed, 0 skipped** |
| Composed, strict, 2026-10-09T00:47–01:01Z | entry point `a02a45c` + code `d12345b` (= `ecd7aa4`) | module + install suites + `repo_hygiene` | **395 passed, 19 failed**. 17 `repo_hygiene` checks and `test_the_help_and_the_readme_say_the_mode_the_receipt_is_born_at` are T006 §10.6's front-door findings (T009's): they read root documents the code leg does not carry. The 19th was this change's. `test_without_jq_it_refuses_and_places_nothing` saw exit 2 but `line 734: awk: command not found` instead of "needs `jq`": the mounted-leg path read the gitlink with `awk`, which the test's minimal `PATH` lacks. Fixed in `2411f40` and in the entry point (`8ed83b7`) by reading it with `read`. |
| Green with the `read` fix, 2026-10-09T01:05–01:20Z | `2411f40` | as "Green with hygiene" | **479 passed, 5 failed, 7 skipped**: the same five `lanes-edit.sh` cases, nothing else. |
| Composed, strict | entry point `8ed83b7` + code `ea17f30` (= `2411f40`) | module + install suites + `repo_hygiene` | Not completed. The 2026-10-09T01:3xZ account swap stopped it, and `6568f08`'s run below superseded it. |
| CI on `ecd7aa4` | | | All jobs green (run 37866464029). |
| CI on `2411f40` | | | All jobs green (run 37869321635). `tests-macos` skipped (no `ready`). |
| Review of #191 at `2411f40` | | | DO NOT LAND (review 5465121368). F1: on today's layout, the curl path needed api.github.com and `jq`. F2: an installed `wip init` refused at step 7 where base fell back to `main`. |
| F1/F2 fix | `13cc752` | module | 90 passed, 7 skipped. CI on `13cc752`: green. Lane 3's delta review: LAND (5471121210), with the stale body (delta 8) and the `ready` macOS run as conditions. |
| Round 2 | `fdc5f18`, `6fa3b43`, `6568f08` | | Dropped the `project.yaml` probe; bounded the assembly search (delta 4); the adopted pin refusal now says what answered (delta 6); r14 reads conftest's text (the `KeyError 'reason'` under #190's composed mode); a composed test for the root's gitlink check; merged main `f87fd5a`. |
| Module, under the lock | `fdc5f18` content | `-k payload_source` | **96 passed, 7 skipped** |
| New and changed tests × four installers, unlocked | `c4864ac` / `2411f40` / `13cc752` / `fdc5f18` | the 20 new and changed tests | **19 pass + 1 fail** (the adopted step-7 words, which are new behaviour) / **20 fail** / **16 pass + 4 fail** (the `project.yaml` request, the parent walk ×2, the partial refusal) / **20 pass** |
| Delta 6 and r14, unlocked | `6fa3b43` | what-answered, documented skip, malformed pins, gitlink pins | **23 passed** |
| Composed root gitlink test, strict, unlocked | root v2 `8ed83b7` / v3 `6acc147`, with code `fa460f2` | the module's composed tests | v2: the new test fails ×2. v3: **9 passed**. |
| Broader suites, under the lock | `6568f08` | `payload_source`, `openrepotools_command`, `wip_init`, `install_skill_and_hook`, `install_by_rename`, `repo_hygiene`, `upstream_pin`, `test_roots` | **516 passed, 9 skipped, 5 failed**. The 5 are the `lanes-edit.sh who` exit-8 cases on this workstation's lane state. That file and its test are outside the diff, and CI runs them green. |
| Composed, strict, under the lock, 2026-10-09T22:08–23:18Z | assembly `4c6a0b7` = root v3 `6acc147` + code `fa460f2` (this head's whole code leg) | module + install suites + `repo_hygiene` + `openrepotools_command` | **429 passed, 1 failed**. The failure is `test_the_root_carries_the_line_ending_rule`, which needs `.gitattributes` in the code leg; run C's legs carry none (T006 §10.2). After #190's roots, the 17 earlier front-door failures read the assembly root and pass. |
| CI on `6568f08` | | | Run 37997688693: `tests` 1416 passed, 9 skipped. `tests-no-submodule`: 1196 passed, 229 skipped. `tests-windows`: 177 passed. `guard-launch-mode`: 165 passed. `parse-macos`, SonarCloud and Sourcery: pass. `tests-macos` waits on `ready`. |
| Copilot round 1, on `6568f08` | `cddd1f7` | | Three findings. Fixed: a copy-time race on the mounted-leg path (the checked snapshot is what is installed), and a commented `submodule_path` that `pin_mounts` missed (its new test fails at `6568f08` and passes at `cddd1f7`, scoped and unlocked). Kept: the index-then-HEAD gitlink fallback, which is openRepoShape's `recorded_gitlink` contract. Local rows r02/r03/r10/r15, scoped and unlocked: **13 passed, 2 skipped**. |
| Copilot round 2, on `cddd1f7` | `8246983` | | One finding: the PR body overclaimed a refusal for a ref that moves between the probe and the resolution. The body is corrected, and a test (moved right after the probe: adopted → installed whole at the second commit; single → refused) passes, together with row 7, scoped and unlocked: **3 passed**. The cap is reached. |
| Composed, strict, unlocked | assembly `4b8b05a` = root v3 + code `3fc1e95` (= `8246983`) | the module's composed tests + r02, r03, r07, r10 | **22 passed** |

## Lane 2's installer rows

These are the 15 rows of "The installer's own assumptions" in `consumer-reads-2026-10-07.md`.

| Row (`openRepoTools` at `c4864ac`) | Disposition |
| --- | --- |
| `:6-11`, README one-liners | Covered: the entry point patch and the composed one-liner tests. |
| `:70-72` `REPO`/`REF`/`SELF` | Covered: the meanings are unchanged; the adopted source is resolved through the pin. |
| `:258-275` `fetch_from_repo` | Covered: it reads the resolved source, still `gh` first. |
| `:282-285, 338, 962-990` `INSTALLABLES`/`collect_commands` | Covered: the names sit at the code root, and the three arrays stay one line (`test_r15_…one_line_arrays…`, the W4 constraint). |
| `:1290-1398` `collect_skills` from `~/.local/bin` | Covered: rows 4 and 11. |
| `:2502-2517` `wip_shape_ref` | Covered: rows 13 and 14. `main` stays the fallback only for a source that carries no pin. |
| `:2519-2523` `wip_fetch_template_file` | Unchanged. Row 13 shows the template comes from the standard the code pins. |
| `:1218-1222` `venv_note` names `docs/README-lanes.md` | **Not changed.** It is a comment this PR does not touch, and it names a spec-leg path after the split. Listed for T014's reconciliation (also T006 §10.9). |
| `:28-56, 393-396` counts vs design `:61-64` | Recorded: 17 commands, 23 payload files, 29 placed files, 31 artifacts on this layout, derived from the lists. The design's 15/27/29 are `daed209`'s. |
| Paths unmapped against `daed209` | Not this task's (plan regeneration, T003/T012). Run C's accounting covers all 120 entries. |
| `repos.tsv` leg aliases | Not this task's (lane 3; waits for real legs). |
| `:1320, 1352, 2211` hooks, `workspace.yaml` | Unchanged. |
| `lane-worktrees`/`lanes-edit.sh` lane roots | Not this task's (lane 3, I4). |
| `:291-292, 298-300, 322` consumer comments | Unchanged. |
| `.gitmodules`, `upstream/`, `contracts/openreposhape-pin.yaml` | Covered: the dependency unit is code's, and `wip init` reads code's pin. |

workBenches-side: the sentinel REPO/REF partial row is covered (`test_r02_…byte_for_byte`), and so is W4 (one-line arrays). W1, W3 and W8 (re-vendoring from `openRepoTools-code`) are workBenches follow-ups that wait for real legs; nothing here changes workBenches.

## For other tasks

- **T009:** `test_the_installer_reaches_only_this_repository` holds because every fetching line names `$REPO`. Its docstring should say that the one other repository reached is the one `$REPO`'s own validated pin names. The composed hygiene results above are T006 §10.6's front-door findings.
- **T010:** a composed run whose code leg is checked out at a commit other than its pin will see `--install` from the mounted leg refuse (changed payload). Run install tests from the pinned state or from a standalone copy.
- **T014:**
  - `venv_note`'s `docs/README-lanes.md` comment.
  - The README's one-liners need a sentence on network needs after the cutover, next to the one-liner (lane 3's T4 on the v2 patch). Today's single repository needs raw.githubusercontent.com only, or `gh`. After the cutover, the curl one-liner needs api.github.com and `jq`. By reading v3 and the PR head, that is 6 api.github.com requests per install: the root makes 2 (`commits`, `git/trees`), and the implementation makes 4 (`commits`, two `git/trees`, the pinned commit). Lane 3 measured 5 on v2, which had no root tree read. So a gh-less machine that is rate-limited (60 an hour per address, unauthenticated) cannot install.
- **T015:** validate at the real assembled head, with a code pin that carries this change, against the real GitHub. That includes the one-liners and `bump-leg.py`'s lockstep, and the 3.2 parse of the root entry point (`parse-macos` covers the implementation only).

## What this does not do

It creates no repository, pushes nothing to run C, moves no default branch, rebinds no lane and authorizes no real conversion. Gate B remains open; Gate C is Brett Heap's word.
