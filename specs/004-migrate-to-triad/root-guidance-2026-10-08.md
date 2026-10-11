# T006: root and leg guidance, collisions, and workflow bootstrap (run C rebuild)

**Task**: T006 of [tasks.md](tasks.md), for opensoft/openRepoTools#186.
**Writer**: lane openRepoTools-1, on 2026-10-08 and 2026-10-09.
**Evidence branch**: `004-migrate-to-triad-root-guidance`.
**State**: rehearsal evidence only. Nothing here lands on `main`, and today's layout is untouched.

The 2026-10-07 build of this task ran against run B. It was lost when the bench
restart cleared `/tmp`: clones, patches and logs alike. Nothing from it was ever
committed. This document is its rebuild on **run C**, the rehearsal regenerated
on 2026-10-08. Everything below was measured again on run C, and none of it is
carried over from run B.

## Inputs and outputs

| what | identity |
|---|---|
| source (`main` when run C cloned it) | `837928a` (includes #187's planning files and #188's openRepoShape repin) |
| rehearsed assembly split (`adopt/three-repo-shape`) | `69b8924` |
| spec leg / code leg (run C bare remotes) | `593250d` (35 commits) / `73b04d6` (88 commits) |
| code's nested `upstream/openRepoShape`, and the tool | `7f84ca4` (opensoft/openRepoShape `main`) |
| **code leg patch** (my bare copy, branch `t006/leg-guidance`) | `6169e8e` |
| **spec leg patch** (my bare copy, branch `t006/leg-guidance`) | `39c1887` |
| **assembly patch** (my bare copy, branch `t006/root-guidance-c2`) | `3361812`, then `bump-leg.py`'s `1024f18` (spec) and `3e87e39` (code) |

All work happened in host-local private scratch: my own bare copies of the
three run C remotes and of the openRepoShape mirror. Nothing was written into
the rehearsal directory, and nothing reached a real remote except this
evidence branch.

The patches are in [patches/t006/](patches/t006/), as `git format-patch`
output:

| patch | sha256 |
|---|---|
| `assembly-0001-…front-door…` | `cd69c2a9afb7bb11…` |
| `assembly-0002-Bump-spec-leg-to-39c18877e042…` | `574c0df16dddda7d…` |
| `assembly-0003-Bump-code-leg-to-6169e8e96164…` | `a7f8521bb7dbb9b5…` |
| `code-0001-…own-front-door…` | `74b98ff97b0b9b6b…` |
| `spec-0001-…own-front-door…` | `c11070f05a9e4611…` |

Each was applied with `git am` onto its base in a fresh clone, and each
reproduced the pushed tree exactly:

| patch set | `git am` | tree check | `git diff --check` on the range |
|---|---|---|---|
| assembly | exit 0 | `6eb8145e…` = `6eb8145e…` | exit 0 |
| code | exit 0 | `ca65c3b9…` = `ca65c3b9…` | exit 0 |
| spec | exit 0 | `10256135…` = `10256135…` | exit 0 |

`assembly-0002` and `-0003` are commits written by openRepoShape's
`bump-leg.py`, and they pin the rehearsal's leg hashes. At T014 they are
**regenerated against the real legs with the same tool, not applied**.
`assembly-0001`, `code-0001` and `spec-0001` are the portable patches.

The evidence branch's first commit, `f06e1af`, recorded an earlier `assembly-0001`.
Its root additions were 46 and 39 lines. The hygiene caps in section 7 made
those too long, so this commit replaces the three assembly patches with the
c2 versions. The legs' patches are unchanged.

## 1. Collision inventory at the assembly root

The root tree after run C's split, path by path. The front-door blobs are the
monorepo's own: `AGENTS.md` 443880a, `README.md` 18c8f7e, `.gitattributes`
3560973 and `.gitignore` a160f49, all equal to `main`'s.

| path | class | resolution in this patch set |
|---|---|---|
| `AGENTS.md` | **collision** (shape wrote `shape/AGENTS.md`) | Line 1 is the shape's exact pointer, then a short map, then the original text with 16 path repairs. This is the shape's own follow-up: "add the line … to the existing AGENTS.md rather than replacing it". |
| `CLAUDE.md` | **collision** (shape wrote `shape/CLAUDE.md`) | Unchanged. `Read AGENTS.md.` is byte-identical to the shape's own rendered `shape/CLAUDE.md` (`cmp` equal), so the pointer reaches it through `AGENTS.md` line 1. The shape's generic follow-up text ("add the line to the existing CLAUDE.md") is satisfied the way the shape's own scaffold satisfies it. |
| `README.md` | **collision** (shape wrote `shape/README.md`) | Merged. A "Three repositories" section and "The lockstep invariant" are added. `contracts/{spec,code}-pin.yaml` name `resync_runbook: "README.md#the-lockstep-invariant"`, an anchor that only `shape/README.md` had. Plus 12 path repairs and a re-rooted pin-bump block. |
| `.gitignore` | **collision** (shape wrote `shape/.gitignore`, pinned) | The project's file absorbs the shape's two extra lines, `.venv/` and `.DS_Store`, plus `/worktrees/`, the line the three-leg bootstrap requires. Nothing was lost: the root kept `__pycache__/`, `*.py[cod]` and `.pytest_cache/`. |
| `.gitattributes` | **collision** (shape wrote `shape/.gitattributes`, pinned) | Same rule, `* text=auto eol=lf`, with the comment rewritten for this root's pinned copies. The monorepo's reason (the installer's byte-for-byte comparisons) moved, word for word, to `code/.gitattributes`. |
| `LICENSE` | front door | Unchanged. A byte-identical copy is added to each leg, which had none. |
| `shape/.gitignore`, `shape/.gitattributes` | shape-generated, **pinned** (rows in `contracts/shape-pin.yaml`) | Left in place. Deleting or editing them is drift. `update-shape.py` knows a collision copy by its `shape/` row. |
| `shape/AGENTS.md`, `shape/CLAUDE.md`, `shape/README.md` | shape-generated, **not pinned** (no row; verified) | Left in place under this task's rule. The shape's own follow-up says to delete `shape/AGENTS.md` and `shape/CLAUDE.md` once the pointer line is in `AGENTS.md`, which this patch does, and to merge `shape/README.md`, which this patch also does. Removing all three is drift-free. **Decision for T014's reviewer.** `shape/README.md` also carries the rehearsal's local clone path, an artifact of rehearsing with local remotes. |
| `AGENTS-shape.md`, `Makefile`, `scripts/{bootstrap,repo_shape,validate-manifest,validate-pins,validate-repository-naming}.py`, `contracts/repository-naming.yaml`, `.github/workflows/validate.yml` | shape-generated, **pinned** | Untouched. 11 rows; all 11 digests match before and after. |
| `project.yaml`, `contracts/{spec,code,shape}-pin.yaml`, `.gitmodules` (the two mounts) | shape-generated, rendered | Untouched. The leg pins move only through `bump-leg.py`. |
| `spec`, `code` gitlinks | shape-generated | Moved only by `bump-leg.py`, each together with its pin. |
| `contracts/`, `.github/`, `.gitmodules` as **names** | not collisions | The source's `contracts/openreposhape-pin.yaml`, `.github/workflows/tests.yml` and `.gitmodules` left whole for the code leg. The root's same-named files are the shape's. No source path exists at `shape/`, `scripts/`, `Makefile`, `project.yaml`, `worktrees/` or `.specify/` (checked at `837928a`). |
| (lost by the split) | **legs' front door** | Neither leg has `AGENTS.md`, `CLAUDE.md`, `README.md`, `LICENSE`, `.gitattributes` or `.gitignore`. A superproject's attributes and ignore rules never reach into a submodule, so the code leg lost the LF rule its installer depends on. Section 4 restores them. |

## 2. Root agent instructions

- **`AGENTS.md`**, 316 → 340 lines.
  - Line 1 is `Read AGENTS-shape.md first — the rules of this repository's shape.`, the exact `SHAPE_POINTER_LINE` of openRepoShape 7f84ca4.
  - A seven-entry map follows:
    - `spec/`, with `openspec` run there;
    - `code/`, with the pinned standard;
    - this root;
    - where the tests run;
    - the lane tooling's code (`code/`) and its manual (`spec/docs/README-lanes.md`, or `docs/README-lanes.md` in `opensoft/openRepoTools-spec` standalone);
    - paired feature worktrees, with full proposals in spec and bounded amendments in code;
    - the local-rehearsal file-transport flag (the real https legs need none).
  - The original text follows, unchanged except for the 16 repairs in section 3.
  - The shape's 14-line rendered repository table is **not** repeated: the map names the same repositories, and the repository's length cap (section 7) admits lines only for a rule.
- **`README.md`**, 486 → 510 lines.
  - The front door is kept.
  - "Three repositories" says what the root is, what each leg holds, the recursive clone and `make bootstrap`, that nothing a person types changes, and how paths read.
  - "The lockstep invariant" is the anchor the leg pins name.
  - The install section adds: "Both lines are unchanged by the split: the `openRepoTools` they fetch is this root's entry point, which hands over to the installer `code/openRepoTools` at the commit this root pins." The entry point itself is T007's.
- **`CLAUDE.md`**: unchanged, as briefed.

## 3. Repaired links (32)

Line numbers refer to the original blobs at `69b8924`. Every repair was
asserted to match exactly once.

| file:line | was | now |
|---|---|---|
| AGENTS.md:22 | `docs/README-lanes.md` | `spec/docs/README-lanes.md` |
| AGENTS.md:44 | `openspec/changes/skip-no-lane-guard/` | `spec/openspec/changes/skip-no-lane-guard/` |
| AGENTS.md:200 | heading `upstream/openRepoShape` | `code/upstream/openRepoShape` |
| AGENTS.md:203 | `contracts/openreposhape-pin.yaml` | `code/contracts/openreposhape-pin.yaml` |
| AGENTS.md:206 | `upstream/openRepoShape` | `code/upstream/openRepoShape` |
| AGENTS.md:214 | `contracts/openreposhape-pin.yaml` | `code/contracts/openreposhape-pin.yaml` |
| AGENTS.md:216 | `tests/test_upstream_pin.py` | `code/tests/test_upstream_pin.py` |
| AGENTS.md:223 | `git submodule update --init upstream/openRepoShape` | `git -C code submodule update --init upstream/openRepoShape` |
| AGENTS.md:224 | `tests/run.sh` | `code/tests/run.sh` (the wrapper `cd`s to its own root, so it runs from here) |
| AGENTS.md:233 | `.github/workflows/tests.yml` | `code/.github/workflows/tests.yml` |
| AGENTS.md:247 | `bash tests/test_lane_helpers.sh` | `bash code/tests/test_lane_helpers.sh` (it derives `SRC_DIR` from its own path) |
| AGENTS.md:248, 250, 285 | `tests/run.sh` | `code/tests/run.sh` |
| AGENTS.md:291 | `tests/test_lane_helpers.sh` | `code/tests/test_lane_helpers.sh` |
| AGENTS.md:292 | `tests/test_lane_helpers_suite.py` | `code/tests/test_lane_helpers_suite.py` |
| README.md:157 | `docs/README-lanes.md`, `docs/README-claude-current.md` | `spec/docs/…` (2) |
| README.md:183 | `contracts/openreposhape-pin.yaml` | `code/contracts/openreposhape-pin.yaml` |
| README.md:263 | `tests/run.sh` | `code/tests/run.sh` |
| README.md:303 | `commands/swap.md` | `code/commands/swap.md` |
| README.md:417 | `upstream/openRepoShape`, `contracts/openreposhape-pin.yaml` | `code/…` (2) |
| README.md:422 | `tests/test_park_resume_commands.py` | `code/tests/test_park_resume_commands.py` |
| README.md:429 | `tests/test_upstream_pin.py` | `code/tests/test_upstream_pin.py` |
| README.md:437–442 | the pin-bump block (`upstream/openRepoShape` ×4, `contracts/openreposhape-pin.yaml` ×2) | re-rooted with one added line, `cd code`, because the pin and gitlink are a commit in the code leg |
| README.md:449 | `tests/test_upstream_pin.py` | `code/tests/test_upstream_pin.py` |
| README.md:464 | `cd openRepoTools && python3 -m pytest tests -q` | `cd openRepoTools/code && …` |
| README.md:467 | `git submodule update --init upstream/openRepoShape` | `git -C code submodule update --init upstream/openRepoShape` (the command the suite's skip message names, run in the code leg) |
| spec `docs/README-claude-current.md`:275–276 | `tests/test_claude_current.py`, `tests/test_claude_restart_check.py`, `tests/test_lane_start_claude_current.py` | `code/tests/…` (3) |

That is 16 repairs in `AGENTS.md`, 13 in `README.md` (12 rewrites and the
re-rooted block) and 3 in the spec leg. All six markdown links in the spec leg
that use relative `](…)` targets stay inside the spec leg, so none crossed a leg.

**Deliberately unchanged:**
- `AGENTS.md`'s `python3 -m pytest tests -q …` lines describe the command line `tests/run.sh` itself runs, inside the code leg, which is what every other lane's `pgrep` counts.
- `contracts/shape-pin.yaml` (AGENTS.md:118, README.md:46) names every estate's shape pin, not a path into a leg.
- README.md:242 `repos.tsv` is a file installed into `~/.local/bin`.
- README.md:41 `upstream/<branch>` is a git remote.

## 4. Leg guidance added

The shape does provide leg guidance. `templates/code-root/` and
`templates/spec-root/` carry `AGENTS.md`, `CLAUDE.md`, `README.md` and
`.gitignore`. `scaffold-project.py` writes them, and `adopt-project.py` seeds them
only into an empty leg, so an extracted leg gets none. The leg files below are those
templates, rendered by the shape's own `shape_materialize.copy_tree` with this
project's values; no placeholder is left. Each `AGENTS.md` and `README.md` then
appends one short openRepoTools section.

| leg | files | openRepoTools section says |
|---|---|---|
| code | `AGENTS.md`, `CLAUDE.md` ("Read AGENTS.md."), `README.md`, `.gitattributes` (monorepo blob 3560973, byte for byte), `.gitignore` (the shape's code-root template, a superset of the monorepo's three lines), `LICENSE` (blob 261eeb9) | The root's guidance governs. The suite runs here: `git submodule update --init upstream/openRepoShape`, then `tests/run.sh` behind `${TMPDIR:-/tmp}/openrepotools-pytest.lock`. The pinned standard's three rules, by pointer. The manuals and specifications are `../spec/` when mounted and `opensoft/openRepoTools-spec` standalone. A feature's code goes in its code worktree, a bounded amendment in `features/<NNN>/openspec/`. |
| spec | `AGENTS.md`, `CLAUDE.md`, `README.md`, `.gitattributes` (the LF rule the monorepo's root file applied to these documents), `LICENSE` | It holds `openspec/`, `specs/`, `docs/` and `ideation/`. Full proposals and canonical Speckit files live here; bounded amendments live in the code leg's feature folder, under the shared workflow's "Triad Feature Amendments". `openspec validate <change> --strict` runs here, never at the root, and a local root takes precedence over a store pointer. A pre-split path names a code-leg file (`code/…` once repaired), and a cited commit is the assembly's. |

`git add --renormalize .` changes nothing in either leg. Every file is LF:
code 54 + 1 gitlink, spec 70.

The spec leg gets no `.gitignore`. Nothing ignorable was lost there, and the
doctor's row for it is a `note`, which the shape's own agent rules say is
"not a finding and you do not 'fix' it".

**Shape agreement, measured:**
- **Doctor `leg shape files`.** Before: 6 files missing (AGENTS/CLAUDE/.gitignore × 2). After: "spec: AGENTS.md rendered, CLAUDE.md identical, .gitignore absent; code: AGENTS.md rendered, CLAUDE.md identical, .gitignore identical".
- **`scripts/shape_advisory.py`'s leg-clone reader on standalone clones.** Before: recognised by name only (`openRepoTools-code` … "is the code-leg form"). After: "its AGENTS.md is the code leg's, as templates/code-root/ writes it", with the assembly `opensoft/openRepoTools` named. The spec leg reads the same way.
- **Doctor `placement` finding.** Identical before and after: the same 21 flagged paths, `misplaced: 3`, `review_required: 18`. It comes from the adoption plan's reasoned overrides for `commands/`, `skills/` and `contracts/`, and none of the 11 added leg files is flagged. Per the shape's rule 4 it is relayed, not answered.

## 5. Cross-leg references this task does not repair, with owners

- **Spec records (approval provenance, FR-014): kept as written.**
  - Pre-split code paths appear in 17 files under `openspec/` and `specs/`.
  - In completed features (002, 003 and the four other changes) they record acts done against the monorepo at a commit. Example: specs/002 tasks.md:9, "`bash tests/run.sh -k …` passed 165 checks … on implementation commit `64f4e93`". Rewriting such a line would falsify the record.
  - **Feature 004's own working files** carry 23 mentions in 9 files: plan.md 4, installer-design.md 4, proposal.md 4, design.md 3, adoption-plan.yaml 3, tasks.md 2, adopter-rehearsal.md 2, and spec.md, quickstart.md, preparation.md and adopter-blocker.md with 1 each. These are T017's to translate with the feature.
  - 005's `analysis.md`:13 is likewise T016/T017's.
- **`docs/README-lanes.md` (lane 3: the manual's content).** 21 lines name code-leg files:
  - lines 72, 572, 3601, 4163: `tests/test_lane_helpers.sh`;
  - lines 573, 576, 594, 3777, 3979, 3997: `tests/run.sh`;
  - line 3601 (again): `tests/test_lanes_index.py`;
  - lines 74, 637, 1013, 1062, 1236, 2369, 2477, 4162: `repos.tsv` (some of these mean the installed table);
  - lines 2551–2553: `skills/handoff/SKILL.md`, `skills/lane-swap/SKILL.md`, `commands/{ctx,handoff,swap}.md`.
- **Code-leg citations of the manuals: 23 lines in 8 files.**
  - `lane-start` 2 and `lanes-edit.sh` 1, plus `tests/test_lane_helpers.sh` 4 (lines 3730, 3738, 6222, 6228), go to **lane 3**.
  - `openRepoTools` 1 (line 1218, the `venv_note` comment) goes to **T007**, which patches that file.
  - `tests/test_repo_hygiene.py` 11, `tests/test_lane_start_claude_current.py` 1 and `tests/run.sh` 1 (comment, line 36) go to **T009/T010**.
  - `claude-current` 2: line 89 is a comment, and line 123 is `--help` output, so changing it changes the shipped command. Its owner is whoever owns `claude-current`'s text; it is not changed here.
  - A comment-only repair ahead of the functional change beside it would leave the comment disagreeing with the code.
- **Code-leg OpenSpec object keys (lane 3).** `lanes-edit.sh` (12 lines, e.g. 280, 2770, 2814–2827, 2895–2897) and `lane-handoff`:2439 key a claim as `owner/repo:openspec/changes/<name>`. After the split a change lives in `opensoft/openRepoTools-spec`, not the assembly.
- **External referrers (lane 2's reads; follow-ups, not edited here).** From lane 2's `consumer-reads-2026-10-07.md` on `004-migrate-to-triad-reads` (76dcb93, which contains ae70dc5); line numbers are as lane 2 recorded them.
  - **brett-wip:**
    - `lanes/LANES.md`:36 and :1305;
    - 12 `docs/README-lanes` lines in 9 files (first: `handoffs/openRepoTools/brief-lane-openRepoTools-1-2026-09-16.md`:9, `session-handoff-2026-09-16-lane-openRepoTools-1.md`:33, `lanes/log/openRepoTools-1.md`:22);
    - `lanes/repos.tsv`:52, which has no leg aliases.
  - **`~/.agents`:**
    - `protocols/lane-collision-protocol-amendment-9.md`:735 and 943, `-11.md`:1511, `-12.md`:315, `-14.md`:185, `-17.md`:175 and `-18.md`:222, all naming the manual;
    - `AGENTS.md`:273-278 ("places from `opensoft/openRepoTools`");
    - `AGENTS.md`:327 and others ("the code lands in `opensoft/openRepoTools`").
  - **openRepoShape 7f84ca4:**
    - `templates/workspace-root/AGENTS.md`:32, 71-76, 91-95, plus `README.md`:16,18,31,58, `handoffs/README.md`:24, `lanes/LANES.md`:19,40, `lanes/log/README.md`:4,6 and `.gitattributes`:8, all in that template;
    - `scripts/shape_advisory.py`:509;
    - the `--install` pointer at `openRepoShape`:279-280.
  - **workBenches 7fd01e3:**
    - `README.md`:188 and 190;
    - `docs/claude-multi-account-profiles.md`:314;
    - the vendored openrepotools tree and its `upstream-pin.yaml` rows.
  - **Installed handoff skill:** `~/.claude/skills/handoff/SKILL.md`:329, whose writer-poll globs do not cover `<root>/worktrees/`.

## 6. Provenance correspondence (FR-014)

From run C's own filter-repo `commit-map`, copied read-only. For every
spec-leg commit, every path that commit changed was compared blob for blob
with its original commit: **35 of 35 match, 0 mismatches**.

Correspondence is deterministic. The first 34 spec commits have exactly the
hashes run B produced (for example `30d7bf7`, `b4e1cb7`, `558a12b`). Only
`593250d`, from #187's `44983ce`, is new. Re-extracting the same history
reproduces the same leg identities.

| # | spec leg (run C) | original (assembly history) | date | paths | of which openspec/ or specs/ | blob check |
|---|---|---|---|---|---|---|
| 1 | `af9806736072` | `3fc62156e798` | 2026-09-10 | 1 | 0 | ok=1 bad=0 |
| 2 | `7ab0b61163ec` | `9e3e241f4f3c` | 2026-09-10 | 1 | 0 | ok=1 bad=0 |
| 3 | `1a12f36f7b5e` | `792a9dede1ec` | 2026-09-10 | 1 | 0 | ok=1 bad=0 |
| 4 | `a1ebef63f4a6` | `3179f50d4d6c` | 2026-09-10 | 1 | 0 | ok=1 bad=0 |
| 5 | `46ef1be6a9af` | `e6044d3a4189` | 2026-09-12 | 1 | 0 | ok=1 bad=0 |
| 6 | `780b66740b1a` | `2108ce3ab6f7` | 2026-09-12 | 1 | 0 | ok=1 bad=0 |
| 7 | `e26759dffc6d` | `bd27fc346682` | 2026-09-13 | 1 | 0 | ok=1 bad=0 |
| 8 | `422f7f8b6ef4` | `9000e86796b2` | 2026-09-13 | 1 | 0 | ok=1 bad=0 |
| 9 | `f53e46c45137` | `f97530bb936e` | 2026-09-13 | 1 | 0 | ok=1 bad=0 |
| 10 | `cfae3d330bae` | `63a74af1b741` | 2026-09-14 | 1 | 0 | ok=1 bad=0 |
| 11 | `f245d9f16c86` | `8345d2f1dc42` | 2026-09-14 | 1 | 0 | ok=1 bad=0 |
| 12 | `7a76cad941fe` | `a95443591ab7` | 2026-09-14 | 1 | 0 | ok=1 bad=0 |
| 13 | `52acec4817a2` | `2faa883db081` | 2026-09-14 | 1 | 0 | ok=1 bad=0 |
| 14 | `17ba18660c6a` | `fcccbe08b1bd` | 2026-09-14 | 1 | 0 | ok=1 bad=0 |
| 15 | `6d8aa95504bb` | `f98d7347b8b3` | 2026-09-15 | 1 | 0 | ok=1 bad=0 |
| 16 | `21c1e268489d` | `9449557495b3` | 2026-09-15 | 1 | 0 | ok=1 bad=0 |
| 17 | `30d7bf7dc109` | `f9e63f44dc37` | 2026-09-15 | 6 | 5 | ok=6 bad=0 |
| 18 | `6a9f75c6f1a9` | `4c2ffefdec64` | 2026-09-16 | 1 | 0 | ok=1 bad=0 |
| 19 | `219184864a87` | `4218e6dacdaf` | 2026-09-23 | 1 | 0 | ok=1 bad=0 |
| 20 | `b4e1cb7a7797` | `a7d125716829` | 2026-09-30 | 9 | 8 | ok=9 bad=0 |
| 21 | `4fe91d309f75` | `cbb59813ceea` | 2026-09-30 | 3 | 3 | ok=3 bad=0 |
| 22 | `ac36505644f4` | `6faed35f418c` | 2026-10-02 | 1 | 0 | ok=1 bad=0 |
| 23 | `525a95dd752d` | `c1bac0dfc99a` | 2026-10-03 | 1 | 0 | ok=1 bad=0 |
| 24 | `03818f50c581` | `14641fd67cee` | 2026-10-03 | 1 | 0 | ok=1 bad=0 |
| 25 | `993d1e1d01c9` | `daed20957f2d` | 2026-10-04 | 1 | 0 | ok=1 bad=0 |
| 26 | `fa21860f9063` | `b1015f4672f9` | 2026-10-04 | 12 | 5 | ok=12 bad=0 |
| 27 | `705058619ba5` | `fea9a2904ce0` | 2026-10-05 | 1 | 0 | ok=1 bad=0 |
| 28 | `75ada176939b` | `00971b929f58` | 2026-10-06 | 18 | 10 | ok=18 bad=0 |
| 29 | `2374d2ec8f8f` | `f5444c5e1f3c` | 2026-10-06 | 1 | 0 | ok=1 bad=0 |
| 30 | `0c2b499dc1b4` | `2080f3d83520` | 2026-10-06 | 1 | 0 | ok=1 bad=0 |
| 31 | `74e48d3b605b` | `500687c4b746` | 2026-10-06 | 1 | 0 | ok=1 bad=0 |
| 32 | `659087420e44` | `5eb3d5f816f8` | 2026-10-06 | 1 | 0 | ok=1 bad=0 |
| 33 | `c9b870270cf5` | `2fb854f12855` | 2026-10-06 | 1 | 0 | ok=1 bad=0 |
| 34 | `558a12b67400` | `c4864ac5e59d` | 2026-10-07 | 1 | 0 | ok=1 bad=0 |
| 35 | `593250d600ca` | `44983ce250ab` | 2026-10-08 | 20 | 20 | ok=20 bad=0 |

**Per document.** These are the 51 files under `openspec/` and `specs/` at
`593250d`. They were computed with plain `git log -- <path>`. `--follow` falsely
linked the tiny `.openspec.yaml` files across changes.

| documents | files | introduced (spec <- original) | last changed (spec <- original) |
|---|---|---|---|
| `openspec/changes/add-crash-consistent-lane-worktree-recovery/` | 5 | `fa21860<-b1015f4` | `fa21860<-b1015f4` |
| `openspec/changes/add-supervised-context-restart/` | 6 | `75ada17<-00971b9` | `75ada17<-00971b9` |
| `openspec/changes/interactive-lane-name-repair/` | 5 | `30d7bf7<-f9e63f4` | `30d7bf7<-f9e63f4` |
| `openspec/changes/migrate-to-triad/` | 6 | `593250d<-44983ce` | `593250d<-44983ce` |
| `openspec/changes/skip-no-lane-guard/` | 5 | `b4e1cb7<-a7d1257` | `b4e1cb7<-a7d1257` |
| `openspec/config.yaml` | 1 | `593250d<-44983ce` | `593250d<-44983ce` |
| `specs/002-skip-no-lane-guard/` | 3 | `b4e1cb7<-a7d1257` | `b4e1cb7<-a7d1257` |
| `specs/003-binary-only-guard-runner/` | 3 | `4fe91d3<-cbb5981` | `4fe91d3<-cbb5981` |
| `specs/004-migrate-to-triad/` | 13 | `593250d<-44983ce` | `593250d<-44983ce` |
| `specs/005-supervised-legacy-ctx/` | 4 | `75ada17<-00971b9` | `75ada17<-00971b9` |

**Where cited hashes resolve.** The spec documents at `593250d` contain 85
distinct hex tokens. Each was resolved against the assembly's history (run C's
source, `main` only) and against the original checkout's branches:

| resolves | tokens | examples |
|---|---|---|
| assembly `main` history | 12 | `daed209`, `b1015f4`, `14641fd`, `82ecebe`, `c1bac0d`, `f5444c5` |
| original repository's branches or PR objects only | 35 | `3c26041` (001), `5164ce1`/`b20882a` (`feat/supervised-context-restart`), `11037f0` (`feat/claude-current`), `dda91f1`/`52ce64e` (004 planning branch), `64f4e93`/`708395e` (no local branch: PR heads) |
| openRepoShape | 2 | `39d5c98`, `91d5685` |
| not an openRepoTools commit | 36 | session uuids, pids, dates, examples (`abc1234`), commits of other repositories |

None of them resolves in the spec leg, whose history filter-repo rewrote. All
47 openRepoTools citations resolve in `opensoft/openRepoTools`, which keeps its
whole history and its branches because the adoption is in place. So the
recorded citations stay valid as written and are not rewritten. The spec
`AGENTS.md` says so.

One consequence: a citation of a squash-merged branch commit resolves only
while that branch or its PR ref survives. For example, feature 004's
`dda91f1` and `52ce64e` predate the #187 squash.

## 7. Bootstrap, validators, OpenSpec and Speckit: results

Every check ran against a fresh clone of my bare copies, with
`-c protocol.file.allow=always`. On git 2.43.0 the file transport is refused
without that flag: on run C, plain `submodule update` exits 1 and the flagged
one exits 0.

| check | before (split `69b8924`) | after (c2 `3e87e39`) |
|---|---|---|
| `python3 scripts/bootstrap.py` | exit 0; legs on `main` at their pins | exit 0; spec `39c1887`, code `6169e8e`, both "branch tip == pin" |
| `make validate` (naming, manifest, pins) | exit 0 | exit 0. Gitlinks equal their pins, tree digests recompute (spec `3a4a84be…`, code `697a080f…`), all 11 copied shape files match |
| `bump-leg.py --dry-run`, then the real bump (spec, code) | — | exit 0 ×4; the tool's own validators "pins ok" |
| `shape-doctor.py` | exit 1, `MISPLACED (3 paths)` (pre-existing; section 4) | exit 1, the same `MISPLACED (3 paths)`; `leg shape files` note down to 1 missing file |
| `setup-openspeckit --shape on --integration codex --base-branch main --no-global-agent-pointers`, in a disposable copy with an isolated HOME and agent root | — | exit 0. **Line 1 unchanged**; the managed block landed before the first `## ` heading (line 72, before line 94), as the protocol prescribes for an adopted root; `git-config.yml` reads `checkout_mode: worktree`, `base_branch: main`, `worktree_root: worktrees`; ".gitignore unchanged" (`/worktrees/` already present); the spec leg gains `openspec/README.md`, `changes/archive/.gitkeep` and `specs/.gitkeep`, and its tracked `openspec/config.yaml` is kept. No file in the real agent root is newer than the run. The only workBenches files newer than it are another writer's QA evidence under `sysBenches/cloudBench/devcontainer.example/tmp/qa1-*`; the bootstrap writes only to its `--repo`. |
| paired selection: the overlay's `create-new-feature.sh --number 4 --short-name migrate-to-triad` (dry run, then real) | — | exit 0 ×2. `004-migrate-to-triad` branched in both legs from `origin/main`; worktrees at `worktrees/004-migrate-to-triad/{spec,code}`; `.specify/feature.json` = `{"feature_directory":"worktrees/004-migrate-to-triad/spec/specs/004-migrate-to-triad"}`; `git status --ignored` at the root shows only `!! worktrees/` |
| `.specify/scripts/bash/check-prerequisites.sh --json --paths-only` from the root | — | exit 0; `BRANCH 004-migrate-to-triad`, `FEATURE_DIR worktrees/004-migrate-to-triad/spec/specs/004-migrate-to-triad` |
| `$SPECKIT_GIT_WORKTREE_ROOT=wt-override` (dry run) | — | exit 0; `WORKTREE_PATH wt-override/009-probe`. The override wins, but a root other than `worktrees/` is **not** covered by the root's ignore line, so point it at `worktrees/` or outside the root. |
| `openspec validate migrate-to-triad --strict` in the **spec leg** (`main`, `39c1887`) | — | exit 0, "Change 'migrate-to-triad' is valid" |
| the same in the feature's **spec worktree** | — | exit 0, valid |
| `openspec validate --changes --strict` in the spec leg | — | exit 0, 5 passed, 0 failed |
| the same command from the **assembly root** | — | exit 1, "Unknown item"; `openspec context`: "No OpenSpec root found" |
| store precedence (a disposable spec clone registered as store `ort-spec-main` in the isolated config) | — | spec worktree without `--store` resolves `source: nearest`, the worktree itself (**local root wins**). With `--store` it resolves `source: store`, the store clone (explicit selection overrides, so check where it points). The assembly root without `--store` gives exit 1, naming the store rather than picking it; with `--store` it is valid. |
| `git diff --check`, every patch range | — | exit 0 ×3 |
| code-leg hygiene subset, `PATH=/usr/bin:$PATH code/tests/run.sh -k repo_hygiene` (serialized: it waited for a live suite, then held the lock) | 17 failed, 135 passed | 13 failed, 139 passed (exit 1 both times; section 10, finding 6) |

**Tool versions on this bench, 2026-10-08:**
- git 2.43.0; `/usr/bin/openspec` 1.6.0; `specify` 0.12.12.dev0.
- `setup-openspeckit` is now a shim that runs workBenches' `devBenches/base-image/files/openspeckit/setup-openspeckit` (last changed in d86ba59, #140). Under an isolated HOME it needs `WORKBENCHES_ROOT`.
- The `openspec` first on PATH (`~/.npm-global/bin`, 1.2.0) has no `--store`. The checks above name `/usr/bin/openspec`.
- `python3` on PATH has no pytest, so locked runs need `PATH=/usr/bin:$PATH`.
- `~/.agents` is a symlink; an isolated copy must dereference it (`cp -rL`). `cp -a` copies the link, and that copy then writes to the real agent root.

## 8. `.specify/` today, and what the triad root needs

**Today, on `main`'s shared checkout:**
- `.specify/` is local and ignored. It is listed in `.git/info/exclude` (`/.specify/`, beside `.claude/`, `/.agents/`, `/.codex/` and `/handoffs`), not in the tracked `.gitignore`.
- Its values are machine-local: integration `codex`; Speckit `1.0.7.dev0`; `git-config.yml` with `worktree_root: ../openRepoTools-worktrees` (the single-repository layout); and a `feature.json` pointing into a sibling worktree.
- No agent file in this repository's history has ever carried the bootstrap's managed block (`git log -S'OPENSPEC-SPECKIT-GLOBAL'`: none).

**What the shape and protocol prescribe for a three-leg root:**
- `.specify/` at the root;
- `git-config.yml` with `worktree_root: worktrees`;
- `/worktrees/` in the root's own `.gitignore`;
- paired worktrees `worktrees/<NNN>/{spec,code}`;
- `$SPECKIT_GIT_WORKTREE_ROOT` as an override.

**The root scaffolding patch carries only `/worktrees/`** (plus the shape's
two ignore lines), and the bootstrap leaves it unchanged. It copies no
machine-specific configuration or secret: `feature.json`, `init-options.json`,
`integration.json`, `git-config.yml` and the skill links are all regenerated
by the bootstrap on each workstation.

It deliberately does **not** commit `.specify/`, the managed blocks, or the
twenty generated agent files. That keeps today's posture: local scaffolding
excluded per clone. The in-place checkout keeps its `.git/info/exclude`
through the adoption. On a fresh clone elsewhere these files show as untracked
after the bootstrap, exactly as they do on a fresh clone of today's
monorepo. Changing that posture, by ignoring them in the tracked
`.gitignore` or by committing `.specify/`, is Brett Heap's decision and is
not made here. The root `AGENTS.md` map carries what the managed block would
otherwise say about the split.

## 9. Distribution is not bootstrap

Running the shape-aware bootstrap in a root writes that root's scaffolding.
It does not distribute the October 4 manual decision ("Triad Feature
Amendments") to any workstation.

The installed `project-agent-bootstrap.md` says so itself: "Existing global
protocol files are written only when missing … Do not run a whole bootstrap
merely to apply this manual decision". The fixture run confirms it: it logged
"kept existing" for the agent root's `AGENTS.md` and both protocol files.

On this workstation (Eagle) the installed protocol files carry the "Triad
Feature Amendments" section. Their sha256 (`f9dd6464…`, `bbbc2b2c…`) are newer
than the October 4 snapshots recorded in protocol-review.md. Nothing here
speaks for any other workstation.

What workBenches delivery would carry to each target workstation:
- the updated `openspec-speckit-workflow.md` and `project-agent-bootstrap.md`;
- the amendment documents and templates (`docs/triad-feature-amendments.md`, `docs/triad-feature-amendment-templates.md`);
- the opsx command and Speckit skill guidance with its shape blocks;
- the `setup-openspeckit` installer and the speckit-worktree overlay templates in the bench image.

Each of these is verified per workstation through workBenches' own delivery,
under its governing `openspec/changes/adopt-triad-feature-amendments/`.
Lane 2 is reading that side.

## 10. Findings for the other writers

1. **T010.** The root `.github/workflows/validate.yml` has a row in `contracts/shape-pin.yaml` (sha256 `fb8c0360…`). A job added there is drift, and `validate-pins.py` will refuse it. The root integration job needs its own, unpinned workflow file.
2. **Legs lose their front door.** Neither leg has `AGENTS.md`, `CLAUDE.md`, `README.md`, `LICENSE`, `.gitattributes` or `.gitignore` after the split. The root's attributes never reach a submodule, so the code leg loses the LF rule behind its installer's byte-for-byte comparisons. `code-0001` and `spec-0001` restore them.
3. **Root README anchor.** `contracts/{spec,code}-pin.yaml` name `README.md#the-lockstep-invariant`, a section only `shape/README.md` had. `assembly-0001` adds it.
4. **`shape/` copies.** Keep `shape/.gitignore` and `shape/.gitattributes` (pinned). `shape/AGENTS.md`, `shape/CLAUDE.md` and `shape/README.md` are unpinned, and the shape's own follow-up says to delete the first two. Their deletion is left to T014's reviewer.
5. **Doctor placement.** `MISPLACED (3 paths)` (`code/commands/`, `code/contracts/`, `code/skills/`) is the adoption plan's reasoned overrides, identical before and after. Relay it; do not move files.
6. **T009: the hygiene tests read the wrong front door after the split.**
   - 17 test functions read `README.md`, `AGENTS.md`, `CLAUDE.md`, `.gitattributes` or `docs/README-lanes.md` at the **code leg's** root: 16 in `test_repo_hygiene.py`, 1 in `test_openrepotools_command.py`.
   - Measured on the code leg alone: before `code-0001`, 17 failed (all `FileNotFoundError`). After it, 13 fail (4 `FileNotFoundError` on `docs/README-lanes.md`, 9 assertions on the short leg README and AGENTS).
   - **4 now pass only because they read the leg's own files:** `test_agents_md_is_short_enough_to_be_read`, `test_readme_is_short_enough_to_be_read`, `test_claude_md_points_at_agents_md` and `test_the_root_carries_the_line_ending_rule`. A green there is about the wrong file.
   - Pointed back at the assembly root, the two length caps (`<= 316`, `<= 486`, today's counts) must rise to 340 and 510, each in a dated entry naming the rule its lines buy:
     - AGENTS.md: the shape's first-line pointer and the triad map the bootstrap protocol requires.
     - README.md: the lockstep-invariant anchor the leg pins name, and the three-repository front door.
   - `test_lane_helpers.sh`:3738 and :6228 read the manual through `cat … || :`, so a missing file reads as empty rather than failing.
7. **Lane 3 (lane tooling).**
   - `lanes-edit.sh` and `lane-handoff` key an OpenSpec claim as `owner/repo:openspec/changes/<name>`; the triad's changes live in `opensoft/openRepoTools-spec`.
   - The manual has 21 lines naming code-leg files (section 5).
   - `lane-worktrees`' and `lanes-edit.sh`'s lane roots (`.claude/worktrees`, `.lane-worktrees/<lane>`) do not include `<root>/worktrees/<NNN>/{spec,code}`.
   - `repos.tsv` has no `openRepoTools-spec` or `openRepoTools-code` aliases.
   - The installed handoff skill's writer-poll globs miss `<root>/worktrees/`.
   - The checkout's `/handoffs` symlink and `.git/info/exclude` persist through the in-place adoption.
8. **T017.** Feature 004's own working files in the spec leg carry 23 pre-split path mentions. Some cited 004 commits (`dda91f1`, `52ce64e`) resolve only while the 004 branch or #187's PR ref survives.
9. **T007.** `assembly-0001`'s README sentence assumes T007's design: the root `openRepoTools` hands over to `code/openRepoTools` at the pinned commit. `code/openRepoTools`:1218 (`venv_note`) still cites `docs/README-lanes.md`.

## 11. What this task did not do

- It patched no executable, test, workflow or lane-tooling file in the code leg. Lane 3, T007, T009 and T010 own those.
- It did not edit `docs/README-lanes.md`'s content (lane 3), any external referrer, any pinned shape copy, or any approval record.
- It did not delete the three unpinned `shape/*.md` copies (T014's reviewer decides).
- It did not commit `.specify/`, managed blocks or generated agent files.
- It did not change the `.specify/` posture.
- It did not run the full suite. Only the serialized `repo_hygiene` subset ran.
- It did not write anything into the rehearsal directory or any real remote except this evidence branch.

## 12. Nothing lands until the real legs exist

These patches apply only to run C's rehearsed arrangement. Today's layout on
`main` is unchanged. At T014, after Gate C and the real `execute`, the
portable patches (`assembly-0001`, `code-0001`, `spec-0001`) are applied
through the real leg and root pull requests. The pin bumps are then
regenerated with `bump-leg.py` against the real leg commits, and the
reviewer settles the `shape/*.md` deletion and the hygiene cap raises with
T009.
