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

## Brett Heap's decisions (2026-10-17T20:5xZ)

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
  - exactly one console script, `openRepoTools`.

  A test holds `dependencies` empty and the scripts table to that one entry.
- **`src/openrepotools/`** is new. It holds the stamp and an entry module that
  uses only the standard library. The entry module runs the packaged bash
  `openRepoTools` with its arguments unchanged and passes its exit status
  through.
- **The whole payload, byte for byte.** The wheel force-includes every file
  that `payload_names` lists:
  - the seventeen `INSTALLABLES`;
  - the three skills;
  - the three command files;
  - and also `contracts/openreposhape-pin.yaml`, so that `wip init` reads the
    release's own pin.

  A test compares the wheel with `payload_names`, so a file added to those
  lists but not to the wheel fails. The `package` job and the release build
  compare every packaged file with the commit's blob.
- **Offline install.** After `pipx install` of the wheel, run
  `openRepoTools --install` with every network path refused: a sentinel
  `$OPENREPOTOOLS_REPO`, no `gh`, and a `curl` that fails. It places the same
  artifacts and receipt rows as an install from beside a full checkout, except
  the one pipx link below.

### The stamp and `--version`

- **The committed stamp is unstamped:** `VERSION = "0.0.0"`, `TAG = ""`,
  `COMMIT = ""` and `DIGEST = ""`. Only the release build writes it. It
  writes four values:
  - the version, taken from the tag (`v1.1.0` gives `1.1.0`);
  - the tag;
  - the tag's 40-hex commit;
  - the commit's tree digest, `sorted-ls-tree-r-v1`. This is the definition
    `contracts/openreposhape-pin.yaml` already names.

  No other file carries a version number.
- **A stamped package's `--version`** prints
  `openRepoTools <version> (<repo> @ <commit>)`, then one line each for the
  tag, the commit and the digest. A stamp that sets some of the four values
  but not all of them is refused as a broken build.
- **An unstamped package's `--version`**, as the `package` job builds it,
  says the package is unstamped, gives version 0.0.0, and names no tag,
  commit or digest.
- **A checkout or a one-line install** prints exactly what it prints today,
  `openRepoTools (<repo> @ <ref>)`. The assertions in
  `tests/test_openrepotools_command.py:301-317` stay as they are. Only their
  docstring, which says "no version number", is rewritten.

### `--install` and pipx

- **The pipx link is skipped.** Suppose `$OPENREPOTOOLS_BIN_DIR/openRepoTools`
  is a symbolic link into a pipx environment of the `openrepotools` package.
  Then `--install`:
  - skips that one target;
  - prints one line that names the target, with `pipx upgrade openrepotools`
    as the way to update it;
  - places every other artifact;
  - writes no receipt row for the link.

  No later install, and no retirement of `restart`, ever removes the link,
  replaces it or writes through it.
- **Every other link is still refused.** Today `plan_install_targets` refuses
  the whole install when any target is a link ("NOTHING was installed"). That
  stays true for every link except pipx's `openRepoTools`.
- **This differs from opensoft/openRepoShape#563 on purpose.** In
  openRepoShape, a pipx link at the target is refused, because pipx and
  `--install` are rival installers of one command. Here, pipx's
  `openRepoTools` is the command that runs `--install`, so skipping the link
  is how the two installers coexist. The rule kept from #563 is that a link
  is never a place to copy to.

### The release workflow

- **`.github/workflows/release.yml`** is new, adapted from openRepoShape's at
  `190133d`. It runs on `workflow_dispatch` only, with a `version` input. It
  sets `permissions: {}` and grants each job its own permissions. Only one
  release runs at a time, and a running release is never cancelled.
- **The build job refuses unless every check passes:**
  - The version is a final `X.Y.Z`, and not `0.0.0`. A TestPyPI rehearsal may
    instead use `X.Y.ZrcN` (see "Two rehearsals" below).
  - The dispatched ref is the annotated tag `v<version>`, and the tag object
    names the run's commit. This is read both from the forge and from git.
  - That commit is on `main` or on `release/v<X.Y>`.
  - The checkout is that commit, and it is clean.
  - The environments `testpypi` and `pypi` each name a required reviewer, and
    each has a deployment limit of exactly one rule, the tag pattern `v*`.
  - In a push or dispatch run of `tests.yml` whose head is that commit, the
    jobs `guard-launch-mode`, `tests`, `tests-no-submodule` and `package` all
    succeeded.
  - The tree digest computed locally equals the digest computed from the
    forge's tree listing.
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
- **The install check** runs on `ubuntu-latest` and `macos-latest` with
  Python 3.x, and on `ubuntu-latest` with Python 3.9. Each leg checks that:
  - pipx, installed from its own hash lock
    (`.github/release-pipx-requirements.txt`), installs the wheel, taken by
    its digest;
  - pipx placed exactly one command, `openRepoTools`;
  - `--version` names the version, the tag, the commit and the digest;
  - `openRepoTools --install`, run offline into a temporary home, places every
    artifact and skips pipx's link;
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
    This is openRepoShape's rehearsal.
  - **The TestPyPI rehearsal, which is new.** A pre-release `X.Y.ZrcN`,
    dispatched on its annotated tag, may reach TestPyPI and the install check.
    The first is `1.1.0rc1`, on the tag `v1.1.0rc1`. The `pypi` job refuses
    every pre-release.

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
  - checks every packaged payload file against the commit's blob;
  - installs the wheel with pipx;
  - runs the unstamped `--version`;
  - runs an offline `--install` into a temporary home with a pipx link in
    place.
- The three existing jobs are unchanged.

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
- **The `pipx install openrepotools` line** is added to the assembly's README
  by PR, but only once PyPI serves v1.1.0. The README never offers a package
  that is not published.
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
  - `Tagged on Brett Heap's word (<time>, "<words>")`;
  - `Lane: <lane>`.
- **Release branches.** `release/vX.Y` is cut at the `vX.Y.0` tag, right after
  the tag. Each `vX.Y.Z` patch is tagged on that branch.
- **Back-ports.** A fix lands on main first, through its own review and CI.
  Then it is back-ported:
  - by fast-forwarding `release/vX.Y`, while main holds only that patch line's
    work;
  - otherwise, by a PR to `release/vX.Y` of
    `git cherry-pick -x <squash commit>`.
- **Patch tags.** A patch is tagged on `release/vX.Y` only once that commit's
  push run of `tests.yml` is green.
- **One upload per version.** A version is uploaded once. A bad upload is
  fixed by the next patch, never by moving a tag or reusing one.
- **Tags in the triad.** Release tags are made in `openRepoTools-code`, where
  the release is built. `v1.0.0`, and any `rc` rehearsal tag, stay in
  `opensoft/openRepoTools`, which becomes the assembly. Tags are not carried
  to the legs.

## Brett Heap's acts outside the repository

None of these acts is a lane's to perform. `release.yml` refuses every
dispatch until the two environments exist with their rules.

- **Now, in `opensoft/openRepoTools`.** Create the environments `testpypi` and
  `pypi`. Each names brettheap as a required reviewer and has a deployment
  limit of exactly the tag pattern `v*`. (Today the repository has only the
  environment `copilot`.) Recommended: a ruleset on the tags `v*` that lets
  only him create, move or delete one.
- **Now, on test.pypi.org.** Create a pending trusted publisher with:
  - project `openrepotools`;
  - owner `opensoft`;
  - repository `openRepoTools`;
  - workflow `release.yml`;
  - environment `testpypi`. The environment is required here, though the form
    calls it optional.
- **For the TestPyPI rehearsal.** His word for the `v1.1.0rc1` tag, and his
  approval of the `testpypi` deployment.
- **At the cutover:**
  - In `opensoft/openRepoTools-code`, the same two environments and the same
    tag ruleset.
  - On test.pypi.org, a second trusted publisher on the project, which by then
    exists, for `openRepoTools-code`.
  - On pypi.org, a pending publisher for `openrepotools`, naming
    `openRepoTools-code`, `release.yml` and the environment `pypi`.

  This proposal recommends no pypi.org publisher for `openRepoTools` at all.
  Nothing uploads to PyPI from that repository, and a pending publisher does
  not reserve the name.
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
3. **The regenerated adoption plan carries the new paths.** It belongs to lane
   openRepoTools-1.
   - `pyproject.toml` and `src/` are new top-level paths. They must be
     assigned to `code`, or `check` refuses them as `plan-uncovered`.
   - `release.yml` and the two hash locks fall under the existing `.github/`
     entry, which goes to code. `docs/release-notes/` falls under the `docs/`
     entry, which goes to spec.
   - **The code leg needs its own `LICENSE`.** The plan assigns `LICENSE` to
     the root, and openRepoShape's code-root template has no licence file. A
     wheel that declares `license-files = ["LICENSE"]` cannot build in
     `openRepoTools-code` without one.

   Lane 1 edits that plan. This change asks for these entries, and does not
   edit `openspec/changes/migrate-to-triad/`.
4. **After the cutover:**
   - Brett makes his code-side acts.
   - v1.1.0 is tagged on `openRepoTools-code`'s `main` once that commit's push
     run is green.
   - The release is dispatched and approved.
   - The GitHub Release is created from `docs/release-notes/v1.1.0.md`.
   - `release/v1.1` is cut at `v1.1.0`.

If the cutover slips, only step 4 waits for it. Nothing is published to PyPI
in the meantime.

## Non-goals

- **No PyPI upload before the cutover,** and none ever from
  `opensoft/openRepoTools`. From there, TestPyPI takes pre-releases only.
- **No new runtime dependency.** The wheel's `dependencies` is empty. The
  entry module uses only the standard library, and `tests/test_repo_hygiene.py`
  holds it to that. The payload's own requirements do not change: bash, git,
  python3 for two commands, and `gh` or `curl` where they already fetch.
- **No change to the one-line install.** `curl … | bash -s -- --install` and
  its default `$OPENREPOTOOLS_REF=main` stay as they are. So does `wip init`'s
  fetch of the nine openRepoShape template files at the pin.
- **No sdist, no native Windows command, and no second console script.**
- **No edit** to `upstream/openRepoShape`, to its pin, or to the triad
  change's files.

## Open questions for review

- **The TestPyPI rehearsal.** The `X.Y.ZrcN` rehearsal on TestPyPI is new to
  this estate: openRepoShape has only the branch rehearsal, which uploads
  nothing. This proposal reads Brett's "Rehearse on TestPyPI now" as asking
  for a real upload.
- **Where the release notes live.** `docs/release-notes/` can stay with
  `docs/` in the spec leg. This is recommended: it needs no exception in the
  plan, and nothing reads the notes at run time. Or it can move to code,
  beside the workflow that makes the release.
- **The name is not reserved.** Until v1.1.0 is uploaded, nothing reserves
  `openrepotools` on pypi.org. PyPI's documentation says that a pending
  publisher "does not create a project or reserve a project's name until it
  is actually used to publish". Decision 1 accepts that risk. The rehearsal
  reserves the name on TestPyPI only.

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
  - `openRepoTools`: how `--install` handles links, and `--version` when
    stamped;
  - `.github/workflows/tests.yml`: the trigger and the `package` job;
  - `README.md`;
  - `tests/test_openrepotools_command.py` and `tests/test_repo_hygiene.py`;
  - new tests for the package, the stamp and the release workflow.
- **Governed files:** `.github/workflows/` and every file that records a pin
  or a digest are governed in every repository (the protocol's "Governed
  invariants"). That includes the hash locks and the action pins.
- **Outside the repository:**
  - GitHub environments and rulesets, in two repositories;
  - trusted publishers on test.pypi.org and pypi.org;
  - the triad's regenerated adoption plan (#186).
- **Unchanged:** the behaviour of the seventeen commands, the receipt format,
  `wip init`'s template fetch, and every lane tool.
