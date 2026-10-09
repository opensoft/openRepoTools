# Explicit test roots and the triad's CI — October 8, 2026

**Tasks:** T009 and T010 of [tasks.md](tasks.md), under
[#186](https://github.com/opensoft/openRepoTools/issues/186). No task is
checked complete by this record; Gate B stays open.
**Code change:** [PR #190](https://github.com/opensoft/openRepoTools/pull/190)
(`feat/test-roots-for-the-triad`, on `main` `c4864ac`).
**CI patches:** [patches/t010-code-leg-tests-workflow.patch](patches/t010-code-leg-tests-workflow.patch)
and [patches/t010-assembly-exact-pin-job.patch](patches/t010-assembly-exact-pin-job.patch).
**Rehearsed arrangement:** run C of 2026-10-08 (private prep
`work-20261008/rehearsal`): source `main` `837928a`, assembly split
`69b8924`, spec leg `593250d`, code leg `73b04d6`, code's nested
openRepoShape `7f84ca4`. Every clone here was taken *out* of it, with
`-c protocol.file.allow=always` (git 2.43 refuses `file://` submodule
transport by default) and an offline `insteadOf` for the nested
openRepoShape URL; nothing was written in it.

The first scratch of this work, and the October 7 run B arrangement it was
measured against, were lost when the bench restart cleared `/tmp`. An interim
reproduction of run B into disposable local remotes (adopter `check` and
`execute` exit 0, `gh`/`curl` shims never called) gave the same leg commits as
the October 7 receipt — spec `558a12b`, code `6d52162` — and is superseded by
run C for everything below.

## 1. What the split breaks — measured before the change

The suite at run C's code leg `73b04d6` (that is, `main` without PR #190), run
with `tests/run.sh -k 'repo_hygiene or upstream_pin or wip_init or park_resume' -rfEs`
in three contexts:

| Context | Result | Log SHA256 |
| --- | --- | --- |
| M1 — the code leg mounted in the recursive assembly clone (`assembly/code`) | **17 failed**, 350 passed | `e1658c99…eed0e` |
| M2 — the code leg cloned on its own, dependency initialized | **17 failed**, 350 passed | `442588dd…c8dd5` |
| M3 — the code leg cloned on its own, dependency **not** initialized | **17 failed**, 141 passed, 209 skipped | `59027b3c…08238` |

The 17 are the same tests, failing the same way, in all three: every one is
`FileNotFoundError` on a file the split moved out of the code leg. M1 equals
M2 because the suite never looked above its own root.

| Test (`tests/test_repo_hygiene.py`) | Missing file |
| --- | --- |
| `test_the_readme_prints_the_install_line_the_pointer_prints`, `…_also_carries_the_gh_api_form`, `…_carries_the_two_line_onboarding_chain`, `test_no_document_offers_a_windows_powershell_twin`, `test_the_documents_say_what_bare_park_does_now`, `…_what_status_is_and_is_not`, `…_the_sweep_skips_a_root_without_the_overlay`, `…_what_a_bare_lanes_lists`, `test_readme_is_short_enough_to_be_read` | `README.md` |
| `test_claude_md_points_at_agents_md` | `CLAUDE.md` |
| `test_agents_md_names_the_pin_rules`, `test_agents_md_is_short_enough_to_be_read`, `test_the_suite_wrapper_takes_one_lock_and_names_it_where_agents_read_it` | `AGENTS.md` |
| `test_the_directory_precedence_states_every_rung_it_implements`, `test_the_exit_3_documentation_agrees_with_the_die_message_it_describes`, `test_the_manual_offers_the_fork_act_and_not_a_kill` | `docs/README-lanes.md` |
| `test_the_root_carries_the_line_ending_rule` | `.gitattributes` |

What passed in all three is as informative: `tests/test_upstream_pin.py`
already read the code leg's own gitlink and pin, so it needed no rewiring to
stay correct in a leg — only names and a guard (below). The dependency-reading
estate, `wip init` and pin checks skipped in M3 with today's reason, as they
do today.

Two more readers are outside those selectors and were found by reading:
`tests/test_openrepotools_command.py`'s receipt-mode check reads `README.md`,
and two sections of `tests/test_lane_helpers.sh` (14 assertions) read
`docs/README-lanes.md` with `cat … 2>/dev/null || :`, so in a leg they would
have run against an empty string rather than fail on a missing file. PR #190
covers all of them: the 16 hygiene document tests, the installer's README
check, the two lane-suite sections, and the `.gitattributes` rule (kept on the
code root, section 2). The T006 writer's independent count of code-leg tests
reading those documents was 17 functions, two of them in the lane suite.

## 2. The root rules (PR #190)

| Root | Named by | Otherwise |
| --- | --- | --- |
| code | `OPENREPOTOOLS_CODE_ROOT` | the tree the suite was loaded from |
| assembly | `OPENREPOTOOLS_ASSEMBLY_ROOT` | the nearest directory above the code root that carries `contracts/code-pin.yaml` and `project.yaml`, is a repository's top level, and records the code root as the gitlink its code pin's `submodule_path` names; none on today's layout |
| spec | `OPENREPOTOOLS_SPEC_ROOT` | the assembly's spec leg (`contracts/spec-pin.yaml`'s `submodule_path`) when it is checked out; none otherwise |
| dependency | — | `<code root>/upstream/openRepoShape`, initialized or not |

A file is read from the root that owns it: `README.md`, `AGENTS.md` and
`CLAUDE.md` from the assembly; anything under `docs/`, `openspec/`, `specs/`
or `ideation/` from the spec root; everything else from the code root.
Today's single repository carries `openspec/` and `specs/` beside the code, so
it answers for all three roles, and every reader reads exactly the file it
read before. The layout is decided by those trees and never by the documents,
so a README deleted from today's tree is still a failure, not a skip.

`.gitattributes` stays the **code root's** in every layout, against the
placement table, because git never applies a superproject's attributes inside
a submodule. Measured in the composed candidate: `README.md` at the assembly
has `text: auto`, `eol: lf`; `park` and `tests/run.sh` in `code/` have
`text: unspecified`, `eol: unspecified` (`proof-check-attr.log`).

## 3. The composed-versus-standalone contract

* **Standalone** (the default, and the only mode today's layout has): a check
  whose root is absent skips, naming the root — the courtesy the missing
  submodule already gets. The no-submodule skip is today's, same condition and
  reason. On today's layout nothing new skips.
* **Composed** (`OPENREPOTOOLS_COMPOSED=1`): `tests/conftest.py` refuses the
  session (`pytest.UsageError`, exit 4, `ERROR: …`) when the assembly or spec
  root is absent, the dependency lacks `scripts/repo_shape.py` or
  `templates/workspace-root/README.md`, or the code or spec leg is not at the
  commit the assembly records or has changes to tracked files — naming each.
  `NEEDS_UPSTREAM` becomes a fixture that fails, and a document test that
  reaches an absent root fails. A variable naming the wrong kind of tree, or a
  mode other than `0`/`1`, is refused in either mode.

## 4. Red at the base, green on the branch

* **Red.** `tests/test_test_roots.py` (SHA256 `be4edff7…6cff`), copied
  unchanged into a clone of `origin/main` `c4864ac`, `tests/run.sh -k roots`:
  **18 failed**, every test of the module (3 passes are other modules' tests
  whose names contain `roots`). The seven behavioural tests failed on what they
  assert — the nested suite read this checkout's README, manual, gitlink and
  dependency whatever the variables named, a composed triad with its spec leg
  moved off its pin ran instead of exiting 4, and `tests/run.sh` passed a
  relative root through relative — and the eleven resolver tests failed
  because `conftest.resolve_roots` and `ROOTS` do not exist there. Log
  `eb7d2bc4…525c`.
* **Green, today's layout.** `tests/run.sh -k 'repo_hygiene or upstream_pin or roots or composed'`
  on `c139e88`: **188 passed, 0 skipped**. Log `b0289afa…cf4`.
* **CI on #190** (head `c139e88`): `tests` 1315 passed in 34m52s,
  `tests-no-submodule`, `tests-windows` (173 passed, 1142 skipped),
  `parse-macos`, `guard-launch-mode` and SonarCloud green; `tests-macos`
  waits for `ready`.

## 5. The two CI patches (T010)

**Code leg, `.github/workflows/tests.yml`** (against run C's code leg
`73b04d6`, whose copy is byte-identical to `main`'s). The six jobs and their
trigger policy are kept exactly — `tests`, `tests-no-submodule`,
`tests-windows`, `parse-macos` and `guard-launch-mode` on every pull-request
push, `tests-macos` on the `ready` label, on `main`, nightly and on dispatch.
The leg is cloned at its own root, so its checkout and submodule contexts were
already right; the patch names them: workflow `env`
`OPENREPOTOOLS_CODE_ROOT: ${{ github.workspace }}` and
`OPENREPOTOOLS_COMPOSED: '0'`, `-rs` on `tests` so the leg's document skips
are printed, and comments saying that nothing in the leg is composed
acceptance and that the leg must carry its own `.gitattributes`.
SonarCloud Code Analysis is a GitHub App check, not a job in this file; the
code leg needs its own SonarCloud project binding, which is an owner's act.

**Assembly, new `.github/workflows/composed.yml`** (against run C's split
`69b8924`). Its own file because the root `validate.yml` is a pinned shape
copy: `contracts/shape-pin.yaml` records it at
`fb8c0360863ad953af7825f3be01ed27f8cf1269e5cab19dc0d6c5423161b487`, which
the rehearsed file matches, so a job added there is drift that
`validate-pins.py` refuses. One Linux job, `exact-pins`: checkout with
`submodules: recursive` over https (no `file://` allowance anywhere in it),
a step that fails on any missing leg, pin or dependency file, then
`scripts/validate-manifest.py` and `scripts/validate-pins.py`, then
`bash code/tests/run.sh -rs` with `OPENREPOTOOLS_COMPOSED=1`,
`OPENREPOTOOLS_ASSEMBLY_ROOT=$GITHUB_WORKSPACE` and
`OPENREPOTOOLS_SPEC_ROOT=$GITHUB_WORKSPACE/spec`. The macOS, Windows and
no-submodule policies stay in the code leg's workflow.

**Neither patch can run on GitHub until the legs exist** (Gate C). Both
`git apply --check` cleanly against run C, and both were proven locally as
below.

## 6. Local proofs

The composed candidate is a clone of run C's assembly in which PR #190's
commit was applied onto the code leg (`8ebf4ec`, on `73b04d6`), pushed to a
private copy of the code leg's bare remote, and pinned with the standard's own
`bump-leg.py --leg code --to 8ebf4ec… --local-remote-dir …` (exit 0; commit
`6ccdaf8`, `contracts/code-pin.yaml` digest recomputed as `577cdcf1…d850`);
the composed workflow is commit `386be81` on top.

| Check (in the candidate, as the job runs it) | Exit | Log SHA256 |
| --- | ---: | --- |
| `python3 scripts/validate-manifest.py` | 0 | `0caaed6c…83a4` |
| `python3 scripts/validate-pins.py` (both legs at their gitlinks, both digests recompute, 11 shape copies match) | 0 | `fb085bee…cf4b` |
| `make validate` / `make pins` | 0 / 0 | `85c8fd9f…bbf0` / `440c5bf4…74e4` |
| the job's context step, all three legs present | 0 | `c4e4cdf2…ac22` |
| the job's context step, spec leg not checked out | **1** (`::error::the spec leg is not checked out at spec/`) | `fcf47871…444a` |
| P2: `code/tests/run.sh -k upstream_pin`, composed, spec leg not checked out | **4** — `ERROR: openRepoTools composed run (OPENREPOTOOLS_COMPOSED=1) refused … OPENREPOTOOLS_SPEC_ROOT=… is not a spec root` | `38889cab…1059` |
| P1: `code/tests/run.sh -k 'repo_hygiene or upstream_pin or roots or composed or openrepotools_command or lane_helpers_suite'`, composed, as the job runs it | 1: **285 passed, 2 failed, 0 skipped** | `f611c198…fe34` |
| P3: the code leg standalone with the patched workflow's context (`OPENREPOTOOLS_CODE_ROOT`=the leg, `COMPOSED=0`), same selector | 1: **268 passed, 2 failed, 17 skipped** | `0f5e8c21…6144` |
| P4: the code leg standalone without its dependency, `-k 'repo_hygiene or upstream_pin or roots'` | 1: **159 passed, 1 failed, 28 skipped** | `6cc26bb1…55d3` |

The failures, recorded rather than deleted:

* **`test_the_root_carries_the_line_ending_rule`, in P1, P3 and P4** — the
  code leg has no `.gitattributes`. A finding for T006: the leg must carry
  `* text=auto eol=lf` itself (section 2). Until it does, the leg's CI is red
  on this one test, which is the point of keeping it.
* **Two assertions of `tests/test_lane_helpers.sh`, in P1 and P3** — "…with
  clause (c)'s directory and window in the tail" and "the row's stamp states
  clause (c)'s two facts for a person, in its TAIL". Both expect the lane's
  directory in a register row that is cut at 240 characters, and under
  `tests/run.sh` that directory sits beneath the run root
  (`~/.local/state/openRepoTools/tmp/<UTC>-<pid>/tmp/tmp.*/home/projects/…`),
  long enough to fall past the cut. CI runs the same suite with a short
  `TMPDIR` and passed it (1315 passed on #190). These sections are untouched
  by PR #190; the length interaction belongs with the run-root work of
  #162/#184 (inferred from the expected and actual rows, not bisected).

Every skip in P3 and P4 names its root. P3's 17 are `README.md` ten times
(nine hygiene tests and the installer's check), `AGENTS.md` three times,
`CLAUDE.md` once and `docs/README-lanes.md` three times; inside the lane suite
its two manual sections printed `skip … no spec root in this run` as well.
P4's 28 are the hygiene module's 16 document skips plus today's 12 dependency
skips (`the pinned openRepoShape is not checked out; run git submodule update --init upstream/openRepoShape`).
P1 skipped nothing.

Both workflow files parse and hold their structure (`check_workflows.py`:
the leg's six jobs, triggers, `ready` gate, per-job submodule contexts and
`env`; the composed job's one Linux job, recursive checkout, step order and
`env`). `actionlint` passed both on 2026-10-07, on the same content less one
comment sentence in `composed.yml`; it was not installed after the bench
restart, so it was not rerun.

## 7. How the local runs were made

The workstation-wide `pgrep` census in `tests/run.sh` did not reach zero for
some runs (the xFactory worktrees keep 3–20 `python3 -m pytest` alive), so a
run that had not started within 5 minutes was replaced, by the coordinator's
interim rule, with run.sh's own pytest line under `flock` on the same lock
file (M1 was; each log says which). That census is now a comment on
[#184](https://github.com/opensoft/openRepoTools/issues/184#issuecomment-6069746447).
On this profile `~/bin/python3` resolves to a virtual environment without
pytest, so every local run had `/usr/bin` first on `PATH`. CI is the record.

## 8. What remains for T015

* Run both workflows on GitHub at the real exact pins once the legs exist,
  including `tests-macos` and `tests-windows` in the real code leg.
* T006: the code leg's own `.gitattributes`, before the leg's `tests` can be
  green.
* A SonarCloud binding for the code leg, and a leg credential for the
  composed job if the legs are ever private (`project.yaml` says public).
* Re-measure against the frozen source chosen at Gate C; the run C commits
  here are rehearsal identities, not the cutover's.

## Log SHA256s

The logs stay in the private prep area (`work-20261008/ort-test-roots/logs/`).

| Log | SHA256 |
| --- | --- |
| M1 `m1-assembly-code.log` | `e1658c99b088bb2b571369431942a0170a4c78b14da9f5bd88c959ddc89eed0e` |
| M2 `m2-code-standalone.log` | `442588dd56997ec00f5a2773dfe3e6102bf7b2cfd137b755057d62f2991c8dd5` |
| M3 `m3-code-nosub.log` | `59027b3ceed4f52e1e6b2d0be926b0b7f3a2c7abfda2846b4fc9656b35208238` |
| red at base `red-at-base.log` | `eb7d2bc460f5b4d474a71ccfb2a19ecca0798e4fc778685e620311d37384525c` |
| green on branch `green-branch.log` | `b0289afab41217eb3c1e8ece140233b8a458492b37042727c668066a0f5a8cf4` |
| P1 `p1-composed.log` | `f611c1981520c4d479556d4b5ec9094845166a69772779dee7539113f473fe34` |
| P2 `p2-composed-refuses-without-spec.log` | `38889cab1e4a3c842bfddc9687e30b21df9c183b238df0676088dd1e8e981059` |
| P3 `p3-leg-standalone.log` | `0f5e8c2163fbe1457bb692eba3bdbc4b67e03020cf7ec1ba0ee0fc7e38806144` |
| P4 `p4-leg-no-submodule.log` | `6cc26bb153da368df80752f0b935ea660c965bb06b135c090f0835d0dbb055d3` |
| `proof-validate-manifest.log` | `0caaed6c40864ebce25366b7599b3f56149f8698d02d2ba7a42dafb53bc283a4` |
| `proof-validate-pins.log` | `fb085bee84b9f76fc814a78ca8e5ed17d1d9fd5c0030726633fb92fd7b8fcf4b` |
| `proof-make-validate.log` | `85c8fd9f834556cc7f8c42ac9625108b4cd33c90cd7db2bf6fbe49bbb39bbbf0` |
| `proof-make-pins.log` | `440c5bf4b7250418076bce4fb0be5a21c21def76c5fe9990808fa6b1cbc874e4` |
| `proof-context-step.log` | `c4e4cdf2ed3d39dee6775d9a01a27ab76869e76feefc561399aa686227ffac22` |
| `proof-context-step-nospec.log` | `fcf47871f23e005da6f06ace2953acdb81a2117b4bc2d0009d80986ca4e7444a` |
| `bump.log` | `aee4d464a7ef847c92d0acc00c28d539ae24e9ea54426a1747c0ffec8220fc80` |

This record authorizes no conversion, repository creation, merge or
default-branch move.
