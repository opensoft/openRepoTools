# Proposal: release tags, release branches and `openrepotools` on PyPI

Governing issue: opensoft/openRepoTools#228. Sole implementation feature:
Speckit `006-release-pypi`, on the branch of that name cut from main `aaa7bc8`.
`specs/006-release-pypi/` is written by `/speckit.specify`.

## Why

Brett Heap, 2026-10-17: "lets setup tagging and release branches. we will
publish on pypi. lets assume we are currently on 1.0.0 and we will do our first
real release on pypi with v1.1.0. look at the way we did this for openRepoShape
and lets do similar."

openRepoTools has no release identity. README.md says "There is no version
number here", and `--version` names only a repository and a ref. So:

- a workstation cannot say which release it runs;
- a fix cannot be shipped to an older line;
- the only way to install is a network fetch of whatever `$OPENREPOTOOLS_REF`
  (default `main`) holds at that moment.

openRepoShape now has a reviewed model for all three problems. It uses
annotated tags, `release/vX.Y` branches (opensoft/openRepoShape#850), and a
gated, reproducible upload to PyPI by trusted publishing
(opensoft/openRepoShape#563). If openRepoTools adopts that model now, the
regenerated triad adoption plan (#186) carries the packaging into
`openRepoTools-code`, which is where v1.1.0 is published.

## Brett Heap's decisions (2026-10-17, about 20:55Z, as recorded on #228)

No transcript-free source gives the exact second. The `v1.0.0` tag that
decision 2 made has the tagger time 20:57:55Z, so the answers came before it.

1. **v1.1.0 is published after the triad cutover.** The packaging and the
   release workflow land now and are rehearsed on TestPyPI now. v1.1.0 is
   published from `openRepoTools-code` after lane openRepoTools-1's cutover
   (#186).
2. **The baseline is done.** An annotated `v1.0.0` tag (tag object `6a826f8`)
   points at main `aaa7bc8`, and its GitHub Release was published at
   20:57:57Z. Nothing is on PyPI.
3. **The wheel carries the whole tool payload, installed offline.**
   `openRepoTools --install` learns to skip a target that pipx placed.
4. **Merging.** Lane openRepoTools-3 squash-merges the release-setup PRs once
   they are reviewed and green. Tags, the release branch and every upload
   still wait for Brett's word and for his approval in the environment.

**A correction to the record.** #228's decision 3 says `--install` skips a
pipx-placed command "as opensoft/openRepoShape#563 did". That was lane 3's
wording error, in its question to Brett. #563 *refuses* a target that is a
symbolic link (its decision 2, approved 2026-10-15T13:32:51Z).

### Addendum: Brett Heap's answers of 2026-10-17T21:51:50Z

He answered the alignment review's questions in lane 3's session. They are
recorded on #228 as comment 6241784787.

1. **Skip the pipx link.** `--install` skips the `openRepoTools` that pipx
   placed, places the other 16 files, and names `pipx upgrade openrepotools`
   as the way to update the skipped command. Every other link is still
   refused. The reason: pipx's command is the one that runs `--install`, so
   skipping is how the two installers coexist.
2. **Upload `1.1.0rc1` to TestPyPI.** A real pre-release upload proves the
   workflow, TestPyPI publishing and the pipx install end to end. It departs
   from openRepoShape, which uploads nothing before a final release. The
   `v1.1.0rc1` tag still needs his word, and the `testpypi` deployment his
   approval. The `pypi` job refuses every pre-release.
3. **No pypi.org publisher for opensoft/openRepoTools.** Nothing will ever
   upload to PyPI from this repository, and a pending publisher does not
   reserve the name. The pypi.org publisher is made only for
   `openRepoTools-code`, at the cutover. This supersedes the pypi.org part of
   #228's plan step 5. The test.pypi.org publisher for this repository is
   still needed, for the rc rehearsal.
4. **The openRepoShape pin waits for v1.1.0.** Lane openRepoTools-1 pins
   openRepoShape straight to v1.1.0, skipping v1.0.0: one pin update and one
   migration rehearsal, then the cutover (#186 comment 6241785035, his words
   "Yes, wait for v1.1.0"). openRepoShape v1.1.0 is the annotated tag
   `b9c5099` on `190133d`, tagged at 2026-10-17T21:29:43Z and published on
   PyPI by its `release.yml` run 39071178232.

## What Changes

Each item names what a test or a workflow run checks.

### The package

- **`pyproject.toml`** is a new root file. It declares:
  - the build backend, pinned at `hatchling==1.27.0`;
  - `name = "openrepotools"`;
  - `dynamic = ["version"]`, which `[tool.hatch.version]` reads from
    `src/openrepotools/_release.py`;
  - `requires-python = ">=3.9"` and `dependencies = []`;
  - `license = "Apache-2.0"`, with `license-files = ["LICENSE"]`;
  - exactly one console script, `openRepoTools`;
  - no `readme`, because README.md goes to the assembly root at the cutover
    (see "The cutover invariants"). openRepoShape's declares none either.

  A test holds `dependencies` empty, the scripts table to that one entry, and
  the `readme` key absent.
- **`src/openrepotools/`** is new. It holds the stamp and an entry module that
  uses only the standard library. The entry module replaces itself with
  `bash <payload>/openRepoTools` through `os.execvp`, with its arguments
  unchanged. `<payload>` is the wheel's `openrepotools/payload/`. Because this
  is an exec and not a subprocess, signals, the `EXIT` trap that removes
  `"$PLACING"*` (`openRepoTools:240`) and the exit status pass between the
  person and bash unchanged. A subprocess killed by a signal would instead
  return a negative code.
  - **Which bash.** It runs the first `bash` on `PATH`, as the payload's
    `#!/usr/bin/env bash` line would. With no `bash` on `PATH`, it refuses,
    naming the missing command, and runs nothing.
  - **Held to the standard library.** A new test in `tests/test_repo_hygiene.py`
    fails when a module under `src/openrepotools/` imports anything outside
    the standard library. No rule holds that today, and
    `test_the_python_files_compile` (`tests/test_repo_hygiene.py:2722-2741`)
    compiles only `tests/*.py`, `lanes-index` and `lane-worktrees`. It also
    compiles `src/openrepotools/*.py` from now on.
- **The whole payload, byte for byte.** The wheel force-includes every file
  that `payload_names` lists, each payload path P at `openrepotools/payload/P`:
  - the seventeen `INSTALLABLES`, which are sixteen commands and the data file
    `repos.tsv`;
  - the three skills;
  - the three command files;
  - and also `contracts/openreposhape-pin.yaml`, so that `wip init` reads the
    release's own pin.

  A test compares the wheel with `payload_names`, so a file added to those
  lists but not to the wheel fails. The `package` job and the release build
  compare every packaged file with the commit's blob, and its mode in the
  wheel with the commit's (`100755` or `100644`). Nothing at run time depends
  on those modes: the entry module runs `bash <file>`, and `--install` sets
  mode 755 on each file it places (`openRepoTools:1871-1919`).
- **Offline install.** After `pipx install` of the wheel, run
  `openRepoTools --install` with every network path refused: a sentinel
  `$OPENREPOTOOLS_REPO`, no `gh`, and a `curl` that fails. It places the same
  artifacts and receipt rows as an install from beside a full checkout, except
  the one pipx link below. This holds because:
  - `payload_select` takes its local mode only when every `payload_names` file
    sits beside `$SELF` (`openRepoTools:969-984`);
  - `assembly_above` finds no `contracts/code-pin.yaml` above
    `openrepotools/payload/` (`openRepoTools:843-861`, run first at :971);
  - `wip_shape_ref` reads `$selfdir/contracts/openreposhape-pin.yaml`
    (`openRepoTools:3242`).

### The stamp and `--version`

- **The committed stamp is unstamped:** `VERSION = "0.0.0"`, `TAG = ""`,
  `COMMIT = ""`, `DIGEST = ""` and `REPOSITORY = ""`. Only the release build
  writes it. It writes five values:
  - the version, taken from the tag (`v1.1.0` gives `1.1.0`);
  - the tag;
  - the tag's 40-hex commit;
  - the commit's tree digest, `sorted-ls-tree-r-v1`. This is the definition
    `contracts/openreposhape-pin.yaml` already names;
  - the source repository, the release run's `$GITHUB_REPOSITORY`:
    `opensoft/openRepoTools` for the rc rehearsal, and
    `opensoft/openRepoTools-code` for v1.1.0. `$REPO` cannot serve here. It
    defaults to `opensoft/openRepoTools` (`openRepoTools:70`), which becomes
    the assembly at the cutover, so a v1.1.0 `--version` would name the wrong
    repository.

  No other file carries a version number.
- **The stamp is all or nothing.** The rule is openRepoShape's
  (`src/openreposhape/standard.py:153-156` at v1.1.0), adapted to this
  stamp's five fields. With `TAG`, `COMMIT` and `DIGEST` all empty, the
  package is unstamped, and its `VERSION` is `0.0.0`. Otherwise every field
  is set, `VERSION` is not `0.0.0`, `COMMIT` is 40 hex digits and `DIGEST`
  is 64. Any other stamp is a broken build: it is refused, and never read as
  the part it holds.
- **The digest code is the pinned standard's.** The build job runs
  `upstream/openRepoShape/scripts/repo_shape.py` at the pin: `tree_digest` on
  the checkout, and `tree_digest_from_gh` on the forge's tree listing. Its
  checkout is at `submodules: true`, because the script exists here only
  inside the submodule, and `git archive` leaves the submodule out. No copy is
  added. openRepoShape runs its own checkout's copy the same way
  (`release.yml:417-452` at v1.1.0). The adoption plan puts `upstream/` in the
  code leg (`openspec/changes/migrate-to-triad/adoption-plan.yaml:381-382`), so
  `openRepoTools-code` has it.
- **How the stamp reaches `--version`.** The packaged bash stays the commit's
  own blob, so the stamp is never written into it. Bash reads the stamp
  itself, from the `_release.py` that sits beside its own payload directory
  (`openrepotools/_release.py`, next to `openrepotools/payload/`). It reads
  that file with a fixed grammar, as `pin_parse` reads the pin
  (`openRepoTools:458`), and never imports or runs it. No environment
  variable carries the stamp, and bash trusts none for it. So nothing leaks
  to bash's children, a variable left in an environment cannot make a
  checkout's `--version` name a release, and the tests have nothing to
  clear. Bash's `--version` arm prints the package form when it runs from a
  package's `openrepotools/payload/` with that `_release.py` beside it, and
  today's line when it does not. Bash alone still parses the arguments, so
  `--help`, `--install --version` and the refusal behave as they do in a
  checkout. Bash refuses a stamp that breaks the all-or-nothing rule as a
  broken build. The model is openRepoShape's `print_version`
  (`src/openreposhape/cli.py:366-396` at v1.1.0), adapted because this
  command's parser is bash.
- **A stamped package's `--version`** prints exactly these five lines:

  ```text
  openRepoTools 1.1.0 (opensoft/openRepoTools-code @ <commit>)
    version   1.1.0
    tag       v1.1.0
    commit    <commit>
    digest    <digest> (sorted-ls-tree-r-v1)
  ```
- **An unstamped package's `--version`**, as the `package` job builds it,
  prints exactly these five lines:

  ```text
  openRepoTools 0.0.0 (an unstamped package)
    version   0.0.0, unstamped: a package built from a checkout, not a release
    tag       none
    commit    none
    digest    none
  ```
- **A checkout or a one-line install** prints exactly what it prints today,
  `openRepoTools (<repo> @ <ref>)`. The assertions in
  `tests/test_openrepotools_command.py:299-319` stay as they are. Only their
  docstring, which says "no version number", is rewritten.

### `--install` and pipx

- **The pipx link is skipped,** on Brett Heap's answer 1. The detection rule
  is exact. `<dir>` is `$OPENREPOTOOLS_BIN_DIR`, by default `~/.local/bin`.
  `<dir>/openRepoTools` is pipx's link when all three of these hold:
  - it is a symbolic link;
  - its target, resolved, is a regular file `<venv>/bin/openRepoTools`;
  - that `<venv>` holds a `pipx_metadata.json`, and an
    `openrepotools/payload/` tree in its `lib/python*/site-packages/`.

  The rule reads paths and asks whether files exist, and nothing more. It
  needs no `jq`, and bash parses no JSON for it. It resolves the link with a
  loop of plain `readlink` that runs under bash 3.2, never `readlink -f` or
  `realpath`. It holds in every mode: the package's own `--install`, a
  checkout's and the one-line install's. It runs before any link refusal, so
  the refusal's `rm -f` advice (`openRepoTools:2466`) is never printed for
  pipx's link.

  Nothing reads `PIPX_HOME`, so a venv under `$PIPX_HOME`, `~/.local/pipx` or
  `~/.local/share/pipx` is found the same way. A test runs each of the three.
  **The pipx versions.** The fixtures mirror the layouts of three pipx
  releases: 1.11.1 and 1.17.8, which openRepoShape's install check locks for
  Python below 3.10 and from 3.10 on (`.github/release-pipx-requirements.txt:52-55`
  at v1.1.0), and 1.18.3, the newest on PyPI on 2026-10-17. 1.17.12 is only
  the version installed on the bench where this proposal was drafted.
  Then `--install`:
  - skips that one target, and prints exactly
    ``openRepoTools: left to pipx at <dir>/openRepoTools (a link into pipx's openrepotools environment); update it with `pipx upgrade openrepotools`, then run `openRepoTools --install` again``;
  - places every other artifact;
  - prints the count line exactly as
    `openRepoTools: 16 of 17 placed in <dir>, and 1 left to pipx`, in place of
    today's `$placed of ${#INSTALLABLES[@]}` (`openRepoTools:1921`), when it
    runs from pipx's own environment. Run from anywhere else, the line names
    its source too (see "Coexistence with the other installers");
  - writes no receipt row for the link. Today the rows come from the full
    `INSTALLABLES` list (`openRepoTools:1457`), so the receipt has 28 rows
    against a full install's 29 (17 + 6 + 6).

  No later install, and no retirement of `restart`, ever removes the link,
  replaces it or writes through it.
- **The upgrade order.** After `pipx upgrade openrepotools`, the other 16
  files, the skills, the command files and any merged hook entries stay the
  earlier release's until `openRepoTools --install` runs again, which the
  skip line says. A test installs one wheel, upgrades to a second, and checks
  that the second `--install` replaces the 16 files and still skips the
  link.
- **Uninstall.** `pipx uninstall openrepotools` removes only the link and its
  environment. The 16 files, the skills, the command files, any merged hook
  entries and the receipt stay, and README says so. A test removes the link
  and the environment, checks that the 16 files are still there, and checks
  that a checkout's `--install` then places a regular `openRepoTools` at that
  path.
- **`pip install --user`.** It places a regular file at `<dir>/openRepoTools`,
  not a link, so the skip never applies. `--install` refuses to replace it
  (see "Coexistence with the other installers").
- **Every other link is still refused.** Today `plan_install_targets` refuses
  the whole install when any target is a link ("NOTHING was installed"). That
  stays true for every link except pipx's `openRepoTools`.
- **This differs from opensoft/openRepoShape#563 on purpose.** In
  openRepoShape, a pipx link at the target is refused, because pipx and
  `--install` are rival installers of one command. Here, pipx's
  `openRepoTools` is the command that runs `--install`, so skipping the link
  is how the two installers coexist. The rule kept from #563 is that a link
  is never a place to copy to.

### Coexistence with the other installers

pipx's command can meet the one-line install, a checkout's `--install`, pip
and workBenches' `./setup.sh` on one workstation. Each pairing has one
defined outcome. None of them may leave a person believing they run a release
while they track `main`, which is the failure the Why exists to prevent.

- **From the one-line install to pipx.** Run
  `pipx install --force openrepotools`, then `openRepoTools --install`.
  - A plain `pipx install` meets the regular file the one-line install left
    at `<dir>/openRepoTools`. It only warns "File exists … Not modifying"
    (pipx's `commands/common.py`), places no link and exits 0. The bash file
    stays at that path and keeps running, and its next `--install` finds no
    payload beside it and fetches `main` (`payload_select`,
    `openRepoTools:966-997`). README gives `--force` for that reason.
  - A test covers this order with fake layouts: a one-line install, then
    pipx's link in its place as `--force` leaves it, then `--install` from
    the fake venv's payload, which skips the link and replaces the other 16.
- **A checkout's or the one-line install's `--install` meeting pipx's link.**
  It skips the link by the same rule, and places the other 16 from its own
  source. Its count line then says where they came from:
  `openRepoTools: 16 of 17 placed in <dir>, and 1 left to pipx; the other 16 now come from <repo> @ <ref>, not from openrepotools <version>`.
  `<version>` is the stamp beside the link's payload, read as `--version`
  reads it. A package-mode run from outside pipx's environment names its
  own release in place of `<repo> @ <ref>`: `openrepotools <its version>`,
  from its own stamp. A test holds each line.
- **Never replace another installer's command.** In every mode, `--install`
  refuses to replace a regular file at `<dir>/openRepoTools` that is pip's
  console script for openrepotools, as `pip install --user` leaves it.
  Today `--install` would rename the payload's bash file over it in silence.
  The refusal is made in the planning phase, like every other, so nothing is
  placed. README names pipx as the one package route. A test holds this.
- **Never shadow it either.** Once a package-mode `--install` has placed its
  files, it reports when the first `openRepoTools` on `PATH` is not that
  package's console script once links are resolved. That covers a
  `PIPX_BIN_DIR` that differs from `$OPENREPOTOOLS_BIN_DIR`, and an older
  bash file ahead of pipx's link on `PATH`. A test holds each case.
- **The workBenches condition.** This bullet is the only place that states
  it; the rest of the proposal calls it "the workBenches condition".
  - README's route on a new workstation is workBenches' `./setup.sh`
    (README.md:208-221). Its `scripts/setup-estate-commands.sh` lists
    `openRepoTools` in `TOOLS_FILES`. It refuses a symlinked target before it
    installs anything (`check_target_preflight`). After installing, it
    requires a regular file identical to its vendored copy
    (`verify_installed`). These are lines 191, 383-386 and 490-493 at
    workBenches main `bdab3e2`, and the same checks stand at `b2bed1c` before
    it. On a workstation with pipx's link, every `./setup.sh` therefore
    refuses its estate step and names that link.
  - **Position (c), decided by Brett Heap on 2026-10-18** ("go with (c)"):
    lane openRepoTools-3 has filed opensoft/workBenches#165, for workBenches
    to accept pipx's link. README offers pipx only after
    opensoft/workBenches#165 lands. Until then, README says that a
    workstation uses one route or the other, never both.

### The release workflow

- **`.github/workflows/release.yml`** is new, adapted from the one in
  openRepoShape v1.1.0 (`190133d`), as published on PyPI by run 39071178232.
  It runs on `workflow_dispatch` only, with a `version` input. It
  sets `permissions: {}` and grants each job its own permissions. Only one
  release runs at a time, and a running release is never cancelled.
- **The build job refuses unless every check passes:**
  - The version is a final `X.Y.Z`, and not `0.0.0`. A TestPyPI rehearsal may
    instead use `X.Y.ZrcN` (see "Two rehearsals" below).
  - On a dispatch on a tag, the dispatched ref is the annotated tag
    `v<version>`, and the tag object names the run's commit. This is read
    both from the forge and from git.
  - On a dispatch on a tag, that commit is on `main` or on `release/v<X.Y>`.
  - The dispatched ref is a tag or a branch, and nothing else.
  - The checkout is that commit, and it is clean.
  - The environments `testpypi` and `pypi` each name a required reviewer, and
    each has a deployment limit of exactly one rule, the tag pattern `v*`.
  - Each of the jobs `guard-launch-mode`, `tests`, `tests-no-submodule` and
    `package` ran in a push or dispatch run of `tests.yml` whose head is that
    commit. None of those runs is still running it, and the newest to finish
    succeeded. This is the model's rule, and #852's "its tests.yml runs have
    all finished, and the newest is green".
  - The tree digest computed locally equals the digest computed from the
    forge's tree listing, both by the pinned `repo_shape.py` (see "The digest
    code is the pinned standard's").
  - The pinned `repo_shape.py`'s `TREE_DIGEST_DEFINITION` equals
    `sorted-ls-tree-r-v1`, the definition `--version` labels the digest with
    and `contracts/openreposhape-pin.yaml` names. openRepoShape's build makes
    the same assertion (`release.yml:438-440` at v1.1.0). A later pin that
    changes the definition then refuses the build, and never ships a wrong
    label.

  A dispatch on a branch is the branch rehearsal (see "Two rehearsals"). The
  two tag-bound checks above stand down there, because a branch has no tag
  and no release branch to be on. Every other check still runs. This is
  openRepoShape's rule (`release.yml:200-249` at v1.1.0).
- **The build:**
  - The release tools are installed from `.github/release-build-requirements.txt`,
    which locks them by hash and installs wheels only. Hatchling is at
    `pyproject.toml`'s own pin.
  - `git archive` extracts the commit twice, into two different directories.
    Both copies are stamped, and each is built with `SOURCE_DATE_EPOCH` set to
    the commit's time.
  - The two wheels must be one file (`cmp`).
  - Every file in the wheel, except the stamp and the metadata, must be the
    commit's own blob.
  - The wheel's `.dist-info` must hold exactly `METADATA`, `WHEEL`, `RECORD`,
    `entry_points.txt` and `licenses/LICENSE`, and that `LICENSE` must be the
    commit's, as openRepoShape's build checks (`release.yml:649-655` at
    v1.1.0). This check, and not hatchling, is what makes a missing `LICENSE`
    fatal. Hatchling 1.27.0 builds its licence list from a `glob` of each
    `license-files` pattern and raises nothing when a pattern matches no file
    (`hatchling/metadata/core.py:757-770` in its published wheel), so a tree
    with no `LICENSE` would otherwise build a wheel without one.
  - The wheel's sha256 is recorded. It is checked again before and after each
    upload.
- **The uploads.** TestPyPI comes first, in the environment `testpypi`. Then
  the install check runs. Then PyPI, in the environment `pypi`.
  - Only the two upload jobs are granted `id-token: write`.
  - Both upload with
    `pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33`
    (v1.14.2). This is trusted publishing: there is no token and no stored
    secret.
  - Before it uploads, each upload job reads again its environment's rules,
    this run's approval and the tag. The index must hold no other file of
    that version.
  - After it uploads, the index must serve exactly the recorded digest.
  - **The repository guard,** on the lead's ruling of 2026-10-18, puts Brett
    Heap's answers 2 and 3 into the workflow's code:
    - in `opensoft/openRepoTools`, the `testpypi` job takes only a
      pre-release `X.Y.ZrcN`, and the `pypi` job refuses outright;
    - in `opensoft/openRepoTools-code`, a pre-release goes to TestPyPI
      only, and a final `X.Y.Z` goes to TestPyPI and then to PyPI;
    - in any other repository, both upload jobs refuse.

    The build decides this from the repository and the version, before any
    approval is asked. Each upload job checks the rule again before it
    uploads. The absence of a pypi.org publisher for
    `opensoft/openRepoTools` stays as the second line of defence.
    openRepoShape's v1.1.0 workflow has no such guard; it is new here.
- **The install check** runs on `ubuntu-latest` and `macos-latest` with
  Python 3.x, and on `ubuntu-latest` with Python 3.9. Each leg checks that:
  - pipx, installed from its own hash lock
    (`.github/release-pipx-requirements.txt`), installs the wheel, taken by
    its digest;
  - pipx placed exactly one command, `openRepoTools`;
  - `--version` names the source repository, the version, the tag, the commit
    and the digest;
  - `openRepoTools --install`, run offline into a temporary home, places every
    artifact and skips pipx's link, with the skip and count lines above;
  - on the macOS leg, that `--install` runs again with Apple's `/bin/bash`
    (3.2) first on `PATH`, and prints its `BASH_VERSION`. No other job runs
    the payload under bash 3.2;
  - on the Python 3.9 leg, Python compiles `lanes-index` and
    `lane-worktrees`.

  There is no Windows leg, because the payload is bash and on Windows it runs
  under WSL2 (AGENTS.md). The decision of 2026-10-15 took macOS out of the
  test suite. This macOS leg is a release check that runs only on dispatch,
  just as openRepoShape's `release.yml` kept its macOS leg after the same
  decision.
- **Two rehearsals.**
  - **The branch rehearsal.** A dispatch on a branch runs every build check,
    and runs the install check on the build's own wheel. It uploads nothing.
    This is openRepoShape's rehearsal. It builds with the version of the tag
    it rehearses, as the model rehearsed v1.1.0 from its branch
    `l3-rehearsal-v1.1.0`. Because no rehearsal uses `1.1.0` itself, that is
    the next pre-release, `1.1.0rc1` for the first.
  - **The TestPyPI rehearsal, which is new.** A pre-release `X.Y.ZrcN`,
    dispatched on its annotated tag, may reach TestPyPI and the install check.
    The first is `1.1.0rc1`, on the tag `v1.1.0rc1`. In it, the `pypi` job
    is skipped, because it never uploads a pre-release. This departs from openRepoShape, which uploads nothing
    before a final release ("Only final releases are published", #563
    decision 4). It is on Brett Heap's answer 2 of 21:51:50Z. The `v1.1.0rc1`
    tag still needs his word, and the `testpypi` deployment his approval.

  A rehearsal never uses `1.1.0` itself. An index never accepts the same file
  name twice, and v1.1.0 will later be built from a different commit, in
  `openRepoTools-code`. If a rehearsal uploaded a `1.1.0`, the real release's
  TestPyPI step would be refused.
- **The release procedure** (RELEASING) is written in `release.yml`'s header,
  as openRepoShape's is. It includes the branch rules from #850 (see "Branch
  and tag policy").

### `tests.yml`

- **The push trigger.** `push` runs on `main` and on `release/v*`. Every commit
  on a release branch then gets the push run that the build job requires. This
  is the first work item of opensoft/openRepoShape#850, drafted there as #852.
- **A new `package` job** runs on `ubuntu-latest` with Python 3.9. It:
  - builds the wheel twice at the commit's time and compares the two;
  - checks every packaged payload file against the commit's blob, and its
    mode against the commit's;
  - checks the wheel's `.dist-info`, `licenses/LICENSE` included, as the
    release build does;
  - installs the wheel with pipx;
  - runs the unstamped `--version`;
  - runs an offline `--install` into a temporary home with a pipx link in
    place;
  - runs the package's tests, the pipx-skip tests among them, and fails if
    any of them was skipped rather than run. The pipx-skip tests build fake
    venv layouts, with no real pipx and no wheel.
- The three existing jobs are unchanged.
- **The header comment** that says "`push` (main only)" and that the push and
  nightly runs run "those same three jobs" (`tests.yml:34-35`) is rewritten
  for the two branches and the four jobs. #852's concurrency fix does not
  apply here, because this `tests.yml` has no `concurrency:` block.
- **AGENTS.md's CI paragraph** (`AGENTS.md:232-239`) says `tests.yml` runs
  three jobs and pushes only on main. It is rewritten to match. AGENTS.md is
  314 lines against a cap of 316 (`tests/test_repo_hygiene.py:1748`), so any
  cap move goes in a dated entry, as that test requires.

### Release notes and README

- **`docs/release-notes/v1.0.0.md`** holds the body of the published v1.0.0
  Release, byte for byte as `gh release view v1.0.0` returns it.
- **`docs/release-notes/v1.1.0.md`** is a draft. Each of its placeholders is
  filled in or cut before the tag.
- **Each GitHub Release** is created from its file, after PyPI serves the
  version, so the notes never name a version that PyPI lacks.
- **README.md's paragraph** that says "There is no version number here" is
  rewritten. It says that releases are annotated tags, that the version comes
  only from the tag, and what `--version` prints when stamped and when
  unstamped.
- **Three README passages are corrected by feature 006** for a workstation
  with pipx's link:
  - the count (README.md:240, "SEVENTEEN"), which becomes sixteen placed and
    one left to pipx;
  - the symlink paragraph (README.md:251-262), which says every symlink is
    refused, and now names pipx's `openRepoTools` as the one link skipped;
  - the count invariant (README.md:302, "Twenty-nine artifacts always, plus
    the two hook entries once the path they call answers `guard`" since
    #237), where such a workstation has twenty-eight placed always, one left
    to pipx and 28 receipt rows, with the two hook entries on top once that
    path answers.
- **The pipx route's text is fixed now:**

  > **The second way, from PyPI:** `pipx install openrepotools`, then
  > `openRepoTools --install`. pipx owns `~/.local/bin/openRepoTools`. The
  > install places the other sixteen and says `1 left to pipx`. To update,
  > run `pipx upgrade openrepotools`, then `--install` again.
  > `pipx uninstall openrepotools` removes only that command.

  Beside it, README gives the move from the one-line install,
  `pipx install --force openrepotools` (see "Coexistence with the other
  installers").
- **README gains that text only** once PyPI serves v1.1.0 and the workBenches
  condition holds. After the cutover README sits at the assembly root, so the
  text goes there by PR. Lane openRepoTools-3 opens that PR, on Brett Heap's
  word (sequencing step 6). The README never offers a package that is not
  published.
- **The README's cap** in `tests/test_repo_hygiene.py` moves only by a dated
  entry, as that test requires.

## Branch and tag policy

This mirrors opensoft/openRepoShape#850 (Brett Heap's ruling of
2026-10-17T19:52:26Z).

- **The trunk.** `main` is the trunk, and every PR lands on main.
- **A release is an annotated tag `vX.Y.Z`.** It is never a branch, and never
  a committed version number. The tag message has the form `v1.0.0` already
  uses:
  - `openRepoTools vX.Y.Z`;
  - a paragraph;
  - `Tagged on Brett Heap's word (<time>, "<words>")`, where `<time>` is the
    exact UTC second. v1.0.0's message says `2026-10-17T20:5xZ`, and it stays,
    because a tag is never moved;
  - `Lane: <lane>`.
- **Release branches.** `release/vX.Y` is cut at the `vX.Y.0` tag, right after
  the tag. Each `vX.Y.Z` patch is tagged on that branch.
- **Back-ports.** A fix lands on main first, through its own review and CI.
  Then it is back-ported:
  - by fast-forwarding `release/vX.Y` (or a merge of main), while main holds
    only that patch line's work;
  - otherwise, by a PR to `release/vX.Y` of
    `git cherry-pick -x <squash commit>`.
- **Patch tags.** A patch is tagged on `release/vX.Y` only once that commit's
  `tests.yml` runs have all finished, and the newest is green. This is
  opensoft/openRepoShape#852's wording. A commit that reaches the branch by
  fast-forward has main's push run and then the branch's own, and the newer
  one decides.
- **The lanes' side,** as #850 states it:
  - one HOLD at a time on `release/vX.Y`;
  - the lane that landed a PR back-ports it, unless the release owner (see
    "Release owner") fast-forwards;
  - a LANDED line names both commits.
- **One upload per version.** A version is uploaded once. A bad upload is
  fixed by the next patch, never by moving a tag or reusing one.
- **Tags in the triad.** Release tags are made in `openRepoTools-code`, where
  the release is built. `v1.0.0`, and any `rc` rehearsal tag, stay in
  `opensoft/openRepoTools`, which becomes the assembly. Tags are not carried
  to the legs.

## Release owner

- **Brett Heap decides** every tag, every release-branch cut and every
  upload, and he approves each deployment to the `testpypi` and `pypi`
  environments.
- **Lane openRepoTools-3 carries them out on his word:** the tags, the
  dispatches, the GitHub Releases, the cut of `release/v1.1` and step 6 of the
  sequencing below. It is the release owner that #850's lanes' side names.
- **The code leg's `LICENSE`.** T006's patch `code-0001` is the code leg's
  first commit, right after `execute` and before any CI, package or release
  run there, because the wheel must carry `LICENSE` and the `package` job and
  the release build refuse one that does not (see "The build"). Lane
  openRepoTools-3 checks that `LICENSE` on `openRepoTools-code` is blob
  `261eeb9` before the first `package` run. The package never tolerates a
  missing `LICENSE`.

## Brett Heap's acts outside the repository

None of these acts is a lane's to perform. `release.yml` refuses every
dispatch until the two environments exist with their rules.

- **Now, in `opensoft/openRepoTools`.** Create the environments `testpypi` and
  `pypi`. Each names brettheap as a required reviewer and has a deployment
  limit of exactly the tag pattern `v*`. (Today the repository has only the
  environment `copilot`.) Recommended: a ruleset on the tags `v*` under which
  only the admin role creates, moves or deletes one.
- **Now, on test.pypi.org.** Create a pending trusted publisher with:
  - project `openrepotools`;
  - owner `opensoft`;
  - repository `openRepoTools`;
  - workflow `release.yml`;
  - environment `testpypi`. The environment is required here, though the form
    calls it optional.
- **For the TestPyPI rehearsal.** His word for the `v1.1.0rc1` tag, and his
  approval of the `testpypi` deployment (answer 2).
- **In the cutover sequence, after `execute`:**
  - in `opensoft/openRepoTools-code`, the environments `testpypi` and `pypi`,
    each naming brettheap as a required reviewer with a deployment limit of
    exactly the tag pattern `v*`, and the `v*` tag ruleset;
  - on test.pypi.org, the trusted publisher pointed at `openRepoTools-code`.
    The project exists by then, from the rc rehearsal;
  - on pypi.org, a pending publisher for `openrepotools`, naming
    `openRepoTools-code`, `release.yml` and the environment `pypi`. It is the
    only pypi.org publisher.

  v1.1.0 is published only after both publishers and both environments
  exist. There is no pypi.org publisher for `opensoft/openRepoTools` at all, on
  Brett Heap's answer 3 of 21:51:50Z. Nothing will ever upload to PyPI from
  that repository, and a pending publisher does not reserve the name. Until
  v1.1.0 is uploaded, nothing reserves `openrepotools` on pypi.org: PyPI's
  documentation says a pending publisher "does not create a project or
  reserve a project's name until it is actually used to publish". The rc
  rehearsal makes the project on TestPyPI only.
- **For v1.1.0:**
  - his word for the tag;
  - his approvals of both deployments;
  - his word for `release/v1.1`;
  - the `release/*` ruleset choice that #850 leaves to him. One option is no
    force-push and no deletion, which keeps fast-forward back-ports. The other
    is a rule that requires a PR, which makes every back-port a cherry-pick.

## Sequencing with the triad cutover (#186)

1. **Feature 006 lands** in `opensoft/openRepoTools` by squash merge
   (decision 4).
2. **The rehearsals.** Brett creates the environments and the TestPyPI
   publisher. Then a branch rehearsal runs. Then, on his word, the `v1.1.0rc1`
   TestPyPI rehearsal runs.
3. **The openRepoShape pin bump, before the plan.** On Brett Heap's answer 4, lane
   openRepoTools-1 moves the pin straight to openRepoShape v1.1.0
   (`190133d`), skipping v1.0.0, in its own PR (#186 comment 6241785035).
   The pinned `repo_shape.py` is then v1.1.0's, which digests by the same
   `sorted-ls-tree-r-v1`.
4. **One fresh migration rehearsal, and the regenerated adoption plan at that
   pin.** It belongs to lane openRepoTools-1, and it depends on step 1:
   #228's PRs land before lane 1's rehearsal and adoption plan, so the plan
   is generated on the tree that will be cut over (#186 comment 6242560541,
   D1, on Brett Heap's decision 1). A plan generated before them would be
   refused as `plan-uncovered` once they are in the baseline. The plan
   carries the new paths:
   - `pyproject.toml` and `src/` are new top-level paths, assigned to `code`.
   - `release.yml` and the two hash locks fall under the existing `.github/`
     entry, which goes to code (`adoption-plan.yaml:87-88`; under
     `consensus` at openRepoShape v1.1.0, as that comment reads it).
     `docs/release-notes/` falls under the `docs/` entry, which goes to spec
     (`adoption-plan.yaml:183-184`).
   - **The code leg's `LICENSE` comes from T006's patch `code-0001`.** The
     plan assigns `LICENSE` to the root (`adoption-plan.yaml:129-130`), and
     `code-0001` gives the code leg a byte-identical copy, blob `261eeb9`
     (`specs/004-migrate-to-triad/root-guidance-2026-10-08.md:160`). The code
     leg does not exist until `execute`, so `code-0001` cannot land before
     the cutover. It is the code leg's first commit, right after `execute`
     and before any CI, package or release run there (see "Release owner").
   - **The cutover invariants,** which this change depends on and the plan
     carries:
     - the release gate's required jobs, `guard-launch-mode`, `tests`,
       `tests-no-submodule` and `package`, keep those ids in the code leg's
       `tests.yml`. Today they are job ids with no `name:` (`tests.yml:50`,
       `:70`, `:124`), and the plan's follow-ups change the code leg's CI
       (`adoption-plan.yaml:414`);
     - no release step reads across legs: everything `release.yml` reads is
       in the code leg;
     - `pyproject.toml` declares no `readme`, because README.md goes to the
       root (`adoption-plan.yaml:137-138`). A test asserts this.

   Lane 1 edits that plan. This change asks for these entries, and does not
   edit `openspec/changes/migrate-to-triad/`.
5. **The cutover** (#186), through `execute`. `code-0001` is the code leg's
   first commit, right after it.
6. **After `execute`, in the cutover sequence.** Brett Heap decides each act,
   and lane openRepoTools-3 carries out each one on his word (see "Release
   owner"):
   - lane 3 checks that the code leg's `LICENSE` is blob `261eeb9` before
     the first `package` run;
   - Brett makes his code-side acts (see "Brett Heap's acts outside the
     repository"): the two environments and the `v*` tag ruleset in
     `openRepoTools-code`, the test.pypi.org publisher pointed at it, and the
     pypi.org pending publisher for it. Nothing below runs until both
     publishers and both environments exist;
   - v1.1.0 is tagged on `openRepoTools-code`'s `main` once that commit's
     `tests.yml` runs have all finished, and the newest is green;
   - the release is dispatched, and Brett approves both deployments;
   - the GitHub Release is created from `docs/release-notes/v1.1.0.md`;
   - `release/v1.1` is cut at `v1.1.0`;
   - lane 3 opens the assembly's README PR with the pipx route's text, once
     PyPI serves v1.1.0 and the workBenches condition holds.

If the cutover slips, only step 6 waits for it. Nothing is published to PyPI
in the meantime.

## Non-goals

- **No PyPI upload before the cutover,** and none ever from
  `opensoft/openRepoTools`. From there, TestPyPI takes pre-releases only.
- **No new runtime dependency.** The wheel's `dependencies` is empty. The
  entry module uses only the standard library, and the new test in
  `tests/test_repo_hygiene.py` holds it to that. The payload's own
  requirements do not change: bash, git, python3 for two commands, and `gh`
  or `curl` where they already fetch.
- **No change to the one-line install.** `curl … | bash -s -- --install` and
  its default `$OPENREPOTOOLS_REF=main` stay as they are. So does `wip init`'s
  fetch of the nine openRepoShape template files at the pin.
- **`--version` names the command's release, not the placed files'.** After
  `pipx upgrade`, the 16 placed files stay the earlier release's until
  `--install` runs again (see "The upgrade order"). Checking the placed
  files against the receipt is left to a later release.
- **No sdist, no native Windows command, and no second console script.**
- **No edit** to `upstream/openRepoShape`, to its pin, or to the triad
  change's files. The pin moves to v1.1.0 in lane openRepoTools-1's own PR.

## Open questions for review

The TestPyPI rehearsal and the pypi.org publisher were open here. Brett
Heap's answers 2 and 3 of 21:51:50Z settle them (see the addendum).

- **Where the release notes live.** `docs/release-notes/` can stay with
  `docs/` in the spec leg. This is recommended: it needs no exception in the
  plan, and nothing reads the notes at run time. Or it can move to code,
  beside the workflow that makes the release. The council left the choice to
  the design, under the cutover invariant that no release step reads across
  legs. Lane openRepoTools-1's reading of the plan at openRepoShape v1.1.0
  already puts `docs/release-notes/` in spec (#186 comment 6242560541).

## Capabilities

### New Capabilities

- `release-tags-and-branches`:
  - annotated `vX.Y.Z` tags and `release/vX.Y` branches;
  - back-ports and patch tags;
  - the push trigger on release branches;
  - release notes and GitHub Releases.
- `pypi-package`:
  - the `openrepotools` wheel and its offline payload;
  - the stamp and `--version`;
  - the pipx skip in `--install`;
  - coexistence with the one-line install, pip and workBenches;
  - the `package` CI job;
  - the release workflow: its gates, its reproducible build, its TestPyPI and
    PyPI uploads, and its install check.

### Modified Capabilities

None. `openspec list --specs` reports no canonical capability on main. The
triad change's `repository-triad-migration` capability is still in flight, so
this change depends on it (see the sequencing section) rather than modifying
it.

## Impact

- **New files:** `pyproject.toml`, `src/openrepotools/`,
  `.github/workflows/release.yml`, `.github/release-build-requirements.txt`,
  `.github/release-pipx-requirements.txt` and `docs/release-notes/`.
- **Changed files:**
  - `openRepoTools`: how `--install` handles links and pip's console
    script, its count line and its `PATH` report, and `--version` when run
    from a package;
  - `.github/workflows/tests.yml`: the trigger, the `package` job, and the
    header comment that says "`push` (main only)" (`tests.yml:34-35`);
  - `AGENTS.md`: the CI paragraph (`AGENTS.md:232-239`). AGENTS.md is 314
    lines against a cap of 316, so any cap move goes in a dated entry;
  - `README.md`;
  - `tests/test_openrepotools_command.py`, and `tests/test_repo_hygiene.py`
    with its new standard-library test;
  - new tests for the package, the stamp, the pipx skip and the release
    workflow.
- **Governed files:** `.github/workflows/` and every file that records a pin
  or a digest are governed in every repository (the protocol's "Governed
  invariants"). That includes the hash locks and the action pins.
- **Outside the repository:**
  - GitHub environments and rulesets, in two repositories;
  - trusted publishers on test.pypi.org and pypi.org;
  - the openRepoShape pin bump to v1.1.0, and the triad's regenerated
    adoption plan at that pin (#186), with the cutover invariants;
  - opensoft/workBenches, as the workBenches condition states.
- **Unchanged:** the behaviour of the sixteen commands and `repos.tsv`, except
  `--install`'s handling of pipx's link and pip's console script, its count
  line and `PATH` report, and the package's `--version`; the receipt format;
  `wip init`'s template fetch, and every lane tool.
