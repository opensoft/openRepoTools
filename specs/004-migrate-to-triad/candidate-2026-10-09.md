# The composed candidate carrying every follow-up — October 9, 2026

**For:** Gate B of [tasks.md](tasks.md), under
[#186](https://github.com/opensoft/openRepoTools/issues/186). It answers item 3 of
section 7 of `gate-ab-evidence-2026-10-09.md` (branch `004-migrate-to-triad-rollback`
at `fa44d75`): "No composed candidate carrying every follow-up has run the suite."
No task is checked complete by this record, and it approves nothing.
**Writer:** lane openRepoTools-1, 2026-10-09 from 01:47Z.
**Evidence branch:** `004-migrate-to-triad-candidate`, from `main` `63810dd`.
**Private receipt ID:** `candidate-20261009-JR8YyA` (brett-wip `migration/openRepoTools/`).
It holds every script, log, patch and install snapshot named below. Machine paths stay
there.

**State: checkpoint (02:42Z).** The candidate is built and its install is compared. No
suite run has finished yet; section 5 says where each one stands.

## 1. Inputs

Every input was read without checking it out in any existing worktree. Patches were
taken with `git show <branch>:<path>`, and the PR commits with `git format-patch` from
the shared checkout.

| Input | Where | Identity |
| --- | --- | --- |
| Run C's rehearsed arrangement | private prep `work-20261008/rehearsal` (read-only) | source `837928a`, split `69b8924`, spec `593250d`, code `73b04d6`, nested openRepoShape `7f84ca4` |
| T006 patches (5) | `004-migrate-to-triad-root-guidance` `041a273` | each blob equals `465fa6d`'s; sha256 `cd69c2a9…`, `574c0df1…`, `a7f8521b…`, `74b98ff9…`, `c11070f0…`, as `gate-ab-evidence` records |
| T010 patches (2) | `004-migrate-to-triad-ci` `cc7c7a1` | code `tests.yml` `7ee3c6d0…`; assembly `composed.yml` `6ee09f00…` |
| T007 entry point | `004-migrate-to-triad-installer` `51993a4` | `t007-assembly-entry-point.patch` `361c037d…`, as `installer-2026-10-08.md` records |
| PR #190 | `feat/test-roots-for-the-triad` `dbc6837` (the head at 01:45Z) | 3 commits on `c4864ac`: `c139e88`, `e3a76b5`, `dbc6837` |
| PR #191 | `feat/installer-payload-source-resolution` `2411f40` (the head at 01:45Z) | 4 commits on `c4864ac`: `6337a52`, `e406e0e`, `ecd7aa4`, `2411f40` |
| The shape's `bump-leg.py` | a clone of the rehearsal's openRepoShape mirror, in scratch | `7f84ca4` |

`assembly-0002` and `assembly-0003` were **not applied**. As `root-guidance-2026-10-08.md`
says, they pin the rehearsal's own leg hashes; the two pins were regenerated here with
`bump-leg.py` against this candidate's legs.

## 2. How it was built

All of it ran in private scratch (`work-20261008/ort-triad-candidate/`):

- **Own copies first.** Bare copies, made with `--no-hardlinks`, of run C's two leg
  remotes, of its assembly branch and of its openRepoShape mirror. Every write went to
  these copies. In every clone the submodule URLs were set to them before any commit, and
  a `url.<copy>.insteadOf` rule sent `.gitmodules`' run C paths and the nested GitHub URL
  to the copies.
- **No network.** `PATH` began with refusing `gh`, `curl` and `wget` shims that log every
  call; `GIT_ALLOW_PROTOCOL=file`. The shim log is empty.
- **Run C unchanged.** A listing of the rehearsal directory (type, mode, size, mtime of
  every entry) was taken before the work and compared after it (section 8).

### Apply order and results

Every patch was applied with `git am`. **Every one applied cleanly; no hunk needed a
resolution, and none was dropped.**

| # | Leg | Patch | `git am` | Commit | Tree |
| --- | --- | --- | --- | --- | --- |
| 1–3 | code, on `73b04d6` | PR #190's three commits | exit 0 | `a70ecad`, `66a191c`, `8377c56` | `b528173e` after the third |
| 4–7 | code | PR #191's four commits | exit 0 | `36d5ccc`, `80b2119`, `edb902f`, `de49a91` | `66c636e9` after the fourth |
| 8 | code | T006 `code-0001` | exit 0 | `d1ec0b5` | `15014778` |
| 9 | code | T010 `t010-code-leg-tests-workflow.patch` | exit 0 | **`f0af7d9`** | **`a832c8a0`** |
| 10 | spec, on `593250d` | T006 `spec-0001` | exit 0 | **`9e1d006`** | **`10256135`**, the tree T006 and T011 recorded |
| 11 | assembly, on `69b8924` | T006 `assembly-0001` | exit 0 | `4f1e522` | `5060f3be` |
| 12 | assembly | T010 `t010-assembly-exact-pin-job.patch` (`composed.yml`) | exit 0 | `738857c` | `7905d570` |
| 13 | assembly | T007 `t007-assembly-entry-point.patch` | exit 0 | `f4133d6` | `8b0c860b` |
| 14 | assembly | `bump-leg.py --leg spec --to 9e1d006…` | exit 0 | `f0a4feb` | `94e9d9be` |
| 15 | assembly | `bump-leg.py --leg code --to f0af7d9…` | exit 0 | **`3bd95a7`** | **`6191142c`** |

What was checked at each step:

- **The PR commits are the PR heads.** Every path PR #190 touches has `dbc6837`'s blob
  after step 3: 8 of 8. After step 7, `openRepoTools` (`04769c4`) and
  `tests/test_install_payload_source.py` have `2411f40`'s blobs.
- **The one shared file.** Both PRs touch `tests/test_openrepotools_command.py`. On top
  of #190, #191 applied the same two hunks as its own diff, three lines lower. The hunk
  bodies are identical (26 lines).
- **T006's `.gitattributes` and #190's decision agree.** #190 reads `.gitattributes` from
  the code root; `code-0001` puts the monorepo's blob `3560973` there. `git check-attr`
  on `openRepoTools`, `park` and `tests/run.sh` in the leg gives `text: auto`,
  `eol: lf`.
- **The entry point is T007's.** `openRepoTools` at the assembly root is blob `4c2525d`,
  mode 100755, sha256 `3b0d59f5…`, as `installer-2026-10-08.md` records.
- **Clean text.** `git diff --check` exits 0 over the code range (`73b04d6..f0af7d9`), the
  spec range and the assembly range (`69b8924..f4133d6`).

The legs' candidate commits were pushed to `main` of their own bare copies, as
fast-forwards from run C's heads. The assembly was pushed as branch `candidate` to its
bare copy. `bump-leg.py` ran with `--local-remote-dir` set to the copies, with a dry run
first for each leg: exit 0 ×4. It added `Lane:` and `Co-Authored-By:` trailers. Its
`NEXT … push` line was not followed.

### The candidate's identities

| Repository | Commit | Tree | Pinned digest (`sorted-ls-tree-r-v1`) |
| --- | --- | --- | --- |
| assembly (`candidate`) | `3bd95a7a57d0c1eb4d2e339ab34007756938b6a5` | `6191142cb360a71132e2783a9cadf0ce36374ab2` | — |
| spec leg | `9e1d006e2c870615f159ad1ebab719bb7b38cc2a` | `10256135f87ae4d05166d2c5934a152c42ce19ae` | `3a4a84beb20b343390f5bae64cb166df4d0cfd693baff6309fc13c8060d1c866` (T006's spec digest) |
| code leg | `f0af7d9be42d0e5fbfa9a220b6ab6805d81e804d` | `a832c8a058d6dab7bf61f3b7ce469d7b911851ea` | `6550ae2e44d1f78368bdb82f2416dff4828943efb7cfd8a896d1693911e14d95` |
| code's nested openRepoShape | `7f84ca42ca86a8902928345109d2bf6bad87bd91` | — | unchanged from run C |

The commit hashes are this run's alone, because `git am` stamps a new committer and date.
The trees are what reproduce.

## 3. Bootstrap, validators and the composed job's own steps

| Check (in the assembly) | Result |
| --- | --- |
| `python3 scripts/bootstrap.py` | exit 0; "spec: on main at 9e1d006e2c87 (branch tip == pin)", "code: on main at f0af7d9be42d (branch tip == pin)", `pins ok`, `manifest ok`, "bootstrap ok" |
| `make validate` (naming, manifest, pins) and `make pins` | exit 0 and 0. Both gitlinks equal their pins, both tree digests recompute, and all 11 copied shape files match `contracts/shape-pin.yaml` |
| `composed.yml`'s step "every context the composed run claims is here", run as written | exit 0 |
| `composed.yml`'s `validate-manifest.py`, then `validate-pins.py` | exit 0, exit 0 |
| A fresh recursive clone of the candidate from its bare copy, then `bootstrap.py` and `make validate` | exit 0 and 0. Spec `9e1d006`, code `f0af7d9`, nested `7f84ca4`. `status --ignored` is empty |

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
- **The shims logged 0 calls.**

| Stage | Source | Result |
| --- | --- | --- |
| A | today's main `63810dd` (a shallow clone of `origin/main`), `./openRepoTools --install` | exit 0; `17 of 17 placed`; 29 `installed at`; both hooks merged; 29 receipt rows |
| B | a freshly seeded home; the candidate assembly root `./openRepoTools --install` (the T007 entry point) | exit 0. First line: "source: the code mounted at `<clone>/code`, opensoft/openRepoTools-code at f0af7d9be42d… as `<clone>` pins it; every payload file was checked against that commit and nothing fetched". Then `17 of 17 placed`, 29 `installed at`, both hooks merged, 29 receipt rows |
| B2 | the candidate again, over B | exit 0; 31 `unchanged` (29 files and 2 hooks) |
| C | today's main again, over B: rollback by reinstall | exit 0; `openRepoTools: updated at …`, 30 `unchanged` |
| — | the candidate's `./openRepoTools --version`; `./openRepoTools nope` | "openRepoTools (opensoft/openRepoTools @ main)", exit 0; exit 2 |

**Every difference between A and B**, by path, type, mode and sha256 over the whole home:

| Path | A (main) | B (candidate) |
| --- | --- | --- |
| `~/.local/bin/openRepoTools` | 755 `47cfe74ea96e6ce9e56b47220a71e1de8c608af2f51f33cfdffa351410a4f373` | 755 `118cc2ccd376456e51f47d36f5fc9604a79fa0be285be9982d2304c0304c0f8f` |
| `~/.local/share/openRepoTools/installed.tsv` | 600, its `openRepoTools` row names `47cfe74e…` | 600, its row names `118cc2cc…`; the UTC column differs too |

Nothing else differs:
- **The other 28 placed files** have the same path, mode and sha256.
- **`settings.json`** is byte-identical: the seed's model, env, permissions, status line
  and three hooks of its own, plus the same two entries the installer merges, at mode 600.
- **The receipt's name, destination and sha256 columns** differ in the `openRepoTools`
  row only.
- **The foreign command and both foreign skills** are untouched.

The installed `openRepoTools` (`118cc2cc…`) is the bytes of `code/openRepoTools`
(PR #191's implementation, blob `04769c4`). It is not the root entry point (`3b0d59f5…`),
so the entry point handed over as T007 designed.

**Rollback by reinstall (C) restores main.** C's whole-home listing equals A's except for
the receipt file's own digest. The receipt's name, destination and sha256 columns equal
A's; only the UTC stamps differ. This is the (c2) path of `gate-ab-evidence-2026-10-09.md`
section 2, repeated at this candidate's own commits, as its section 2 asked.

## 5. The suite: composed, standalone, and standalone without the dependency

### State at checkpoint (2026-10-09T02:42Z)

**No suite run has finished. All three must be run, the composed one again from the
start.**

- **Composed.** `OPENREPOTOOLS_COMPOSED=1`, with the assembly and spec roots named. It
  took the workstation lock at 02:10:40Z, after `tests/run.sh` had waited 5 minutes on
  the census. By 02:42:37Z it had reached about 20%: the lane helpers' shell suite was
  running, and one non-pass result was printed near 15%. The coordinator then called a
  checkpoint for an account swap. This writer stopped its own run (one process group,
  TERM, nothing left), released the lock with it, and removed the run's own run root.
  The partial log is kept in the receipt. It is not a result.
- **Standalone and no-submodule.** Not started.

For comparison when they run, the CI numbers already read:

| Where | `tests` | `tests-no-submodule` |
| --- | --- | --- |
| main `63810dd` (run 37866269342) | 1296 passed | 1084 passed, 212 skipped |
| PR #190 `dbc6837` (run 37869489919) | 1318 passed | 1105 passed, 213 skipped |
| PR #191 `2411f40` (run 37869321635) | 1379 passed, 7 skipped | 1165 passed, 221 skipped |

## 6. What this proves for Gate B, and what it does not

To be written with section 5.

## 7. Follow-ups

To be written with section 5.

## 8. Acts outside scratch, and log SHA256s

To be written at the end of the run.

This record authorizes no conversion, repository creation, merge, default-branch move or
lane rebinding.
