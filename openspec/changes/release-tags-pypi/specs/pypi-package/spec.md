# Spec Delta

## Purpose

Publishes openRepoTools as the `openrepotools` wheel. The wheel carries the
whole tool payload, so `pipx install` followed by `openRepoTools --install`
works offline, names its release in `--version`, and coexists with every
other way the command is installed.

## ADDED Requirements

### Requirement: Package metadata

The package SHALL be named `openrepotools`, and SHALL require Python 3.9 or
later. It SHALL declare no dependencies, exactly one console script,
`openRepoTools`, and the licence `Apache-2.0` with the file `LICENSE`. It
SHALL declare no `readme`. Its version SHALL be read only from the package's
stamp. The wheel's `.dist-info` SHALL hold exactly `METADATA`, `WHEEL`,
`RECORD`, `entry_points.txt` and `licenses/LICENSE`, and that `LICENSE`
SHALL be the commit's. The `package` job and the release build SHALL refuse
any other wheel. The package SHALL NOT be made to tolerate a missing
`LICENSE`.

#### Scenario: The metadata is held by a test

- **WHEN** the suite reads `pyproject.toml`
- **THEN** `dependencies` is empty, the scripts table has the one entry
  `openRepoTools`, and there is no `readme` key

#### Scenario: A code leg without LICENSE

- **WHEN** a wheel is built from a tree that has no `LICENSE`
- **THEN** the `package` job and the release build refuse it, and nothing is
  uploaded

### Requirement: The entry point runs the payload's bash unchanged

The console script SHALL replace its own process with the first `bash` on
`PATH`, running the packaged `openRepoTools` with the person's arguments
unchanged. Signals, the exit status, and the payload's own clean-up on exit
SHALL pass through as if the person had run the payload with bash directly.
With no `bash` on `PATH`, it SHALL refuse with a message naming `bash`, and
SHALL run nothing. The package's Python modules SHALL import only the
standard library.

#### Scenario: The exit status passes through

- **WHEN** `openRepoTools` is run from the package with arguments that the
  payload refuses
- **THEN** it exits with the payload's own status, and prints the payload's
  own message

#### Scenario: An interrupted install

- **WHEN** a package-mode `--install` is interrupted by a signal while it is
  placing a file
- **THEN** no temporary placement file is left beside the target, as for a
  checkout's `--install`

#### Scenario: No bash

- **WHEN** the console script runs with no `bash` on `PATH`
- **THEN** it refuses, naming `bash`, and nothing else runs

#### Scenario: A third-party import

- **WHEN** a module of the package imports anything outside the standard
  library
- **THEN** a hygiene test fails

### Requirement: The wheel carries the whole payload byte for byte

The wheel SHALL include, at `openrepotools/payload/<path>`, every file that
the installer's payload list names: the seventeen installables (sixteen
commands and `repos.tsv`), the three skills, the three command files, and
`contracts/openreposhape-pin.yaml`. Each SHALL be byte-identical to the
commit's blob. Its mode in the wheel SHALL match the commit's mode, `100755`
or `100644`.

#### Scenario: A file added to the payload but not to the wheel

- **WHEN** a file is added to the installer's payload list and not to the
  wheel's contents
- **THEN** a test fails, naming that file

#### Scenario: A packaged file differs from its blob

- **WHEN** any packaged payload file differs from the commit's blob, in bytes
  or in mode
- **THEN** the `package` job and the release build both fail

### Requirement: An install from the package needs no network

After `pipx install` of the wheel, `openRepoTools --install` SHALL place
every artifact and write every receipt row from the payload inside the
package, with every network path refused. These SHALL be the same as an
install from beside a full checkout, except for pipx's link. `wip init` run
from the package SHALL read the release's own openRepoShape pin.

#### Scenario: Offline install

- **WHEN** `--install` runs from the package with a sentinel
  `$OPENREPOTOOLS_REPO`, no `gh`, and a `curl` that fails
- **THEN** it succeeds, and places the same artifacts and receipt rows as a
  checkout's install, apart from pipx's link

### Requirement: The stamp is all or nothing

The committed stamp SHALL be unstamped: `VERSION` `0.0.0`, and `TAG`,
`COMMIT`, `DIGEST` and `REPOSITORY` empty. Only the release build SHALL
write a stamp. It writes the version taken from the tag, the tag, the tag's
40-hex commit, that commit's `sorted-ls-tree-r-v1` tree digest, and the
release run's source repository. With `TAG`, `COMMIT` and `DIGEST` all
empty, the package SHALL be read as unstamped, and its `VERSION` is `0.0.0`.
Otherwise every field SHALL be set, `VERSION` SHALL NOT be `0.0.0`, `COMMIT`
SHALL be 40 hex digits and `DIGEST` 64. Any other stamp SHALL be refused as a
broken build, and never read as the part it holds. The command SHALL read
the stamp only from the package's own stamp file, and SHALL trust no
environment variable for it. No other file SHALL carry a version number.

#### Scenario: A partial stamp

- **WHEN** a package's stamp has a commit but no digest
- **THEN** `--version` refuses, calling the build broken, and prints no
  version

#### Scenario: A variable in the environment

- **WHEN** a checkout's or the one-line install's `openRepoTools --version`
  runs with any `OPENREPOTOOLS_PACKAGE_*` variable set
- **THEN** it prints exactly what it prints without it,
  `openRepoTools (<repo> @ <ref>)`

### Requirement: `--version` names the release

A stamped package's `--version` SHALL print exactly five lines:

```text
openRepoTools <version> (<repository> @ <commit>)
  version   <version>
  tag       <tag>
  commit    <commit>
  digest    <digest> (sorted-ls-tree-r-v1)
```

An unstamped package's `--version` SHALL print exactly:

```text
openRepoTools 0.0.0 (an unstamped package)
  version   0.0.0, unstamped: a package built from a checkout, not a release
  tag       none
  commit    none
  digest    none
```

A checkout's and the one-line install's `--version` SHALL print what they
print today, `openRepoTools (<repo> @ <ref>)`. `--help`,
`--install --version` and the parser's refusals SHALL behave in the package
as they do in a checkout. `--version` names the command's release, not the
release of the files `--install` placed.

#### Scenario: v1.1.0

- **WHEN** the v1.1.0 package from `openRepoTools-code` runs `--version`
- **THEN** its first line is
  `openRepoTools 1.1.0 (opensoft/openRepoTools-code @ <commit>)`, followed by
  the version, the tag `v1.1.0`, the commit and the digest

#### Scenario: The package job's build

- **WHEN** the `package` job's unstamped wheel runs `--version`
- **THEN** it prints the five unstamped lines exactly

### Requirement: `--install` skips pipx's link and refuses every other link

`<dir>` is `$OPENREPOTOOLS_BIN_DIR`, by default `~/.local/bin`.
`<dir>/openRepoTools` SHALL be treated as pipx's link only when all of
these hold: it is a symbolic link; it resolves to a regular file
`<venv>/bin/openRepoTools`; and that `<venv>` holds a `pipx_metadata.json`
and an `openrepotools/payload/` tree in its `lib/python*/site-packages/`.
The check SHALL use only paths and the existence of files, SHALL need no
`jq`, and SHALL hold under bash 3.2. It SHALL hold in every mode: the
package's own `--install`, a checkout's and the one-line install's. It SHALL
NOT depend on `PIPX_HOME`. It SHALL be decided before any link refusal, and
no refusal SHALL advise removing pipx's link.

On pipx's link, `--install` SHALL skip that one target and print exactly
``openRepoTools: left to pipx at <dir>/openRepoTools (a link into pipx's openrepotools environment); update it with `pipx upgrade openrepotools`, then run `openRepoTools --install` again``.
It SHALL place every other artifact, and SHALL write no receipt row for the
link: 28 rows, against a full install's 29. Run from pipx's own environment,
its count line SHALL be exactly
`openRepoTools: 16 of 17 placed in <dir>, and 1 left to pipx`. No install,
and no retirement, SHALL ever remove, replace or write through pipx's link.
Every other link at a target SHALL still refuse the whole install before
anything is placed.

#### Scenario: A package-mode install with pipx's link

- **WHEN** `--install` runs from the package and `<dir>/openRepoTools` is
  pipx's link
- **THEN** it prints the skip line and the count line exactly, places the
  other sixteen files, and leaves the link as it was

#### Scenario: Any pipx home

- **WHEN** pipx's venv lives under `$PIPX_HOME`, under `~/.local/pipx`, or
  under `~/.local/share/pipx`, with the layout of pipx 1.11.1, 1.17.8 or
  1.18.3
- **THEN** the link is recognised the same way in each case

#### Scenario: A link into a venv without the payload

- **WHEN** `<dir>/openRepoTools` links to `<venv>/bin/openRepoTools`, but
  that venv has no `openrepotools/payload/` tree
- **THEN** it is an ordinary link, and the install refuses before placing
  anything

#### Scenario: No jq on a machine with pipx's link

- **WHEN** `--install` runs with no `jq` on `PATH`, and `<dir>/openRepoTools`
  is pipx's link
- **THEN** it refuses for want of `jq`, and its output advises no `rm` of
  pipx's link

#### Scenario: Another link

- **WHEN** any target other than pipx's `openRepoTools` is a symbolic link
- **THEN** `--install` refuses, names it, and places nothing

### Requirement: Upgrade and uninstall

After `pipx upgrade openrepotools`, the placed files, skills, command files
and hook entries SHALL stay the earlier release's until `--install` runs
again. That `--install` SHALL replace them and still skip the link.
`pipx uninstall openrepotools` removes only the link and its environment.
The placed files, the skills, the command files, the hook entries and the
receipt SHALL stay, and a later checkout's `--install` SHALL place a regular
`openRepoTools` at the freed path.

#### Scenario: Upgrade

- **WHEN** one wheel is installed with `--install`, then upgraded to a
  second, then `--install` runs again
- **THEN** the second `--install` replaces the sixteen files with the second
  wheel's and still skips the link

#### Scenario: Uninstall

- **WHEN** pipx's link and its environment are removed
- **THEN** the sixteen files are still there, and a checkout's `--install`
  places a regular file at `<dir>/openRepoTools`

### Requirement: Coexistence with the other installers

The documented move from the one-line install to pipx SHALL be
`pipx install --force openrepotools`, then `openRepoTools --install`. A
checkout's or the one-line install's `--install` that meets pipx's link
SHALL skip it, and its count line SHALL be exactly
`openRepoTools: 16 of 17 placed in <dir>, and 1 left to pipx; the other 16 now come from <repo> @ <ref>, not from openrepotools <version>`,
where `<version>` is the stamp beside the link's payload. A package-mode run
from outside pipx's environment SHALL name `openrepotools <its version>`,
from its own stamp, in place of `<repo> @ <ref>`. In every mode,
`--install` SHALL refuse to replace a regular file at `<dir>/openRepoTools`
that is pip's console script for openrepotools, before anything is placed.
Once a package-mode `--install` has placed its files, it SHALL report when
the first `openRepoTools` on `PATH`, with its links resolved, is not that
package's console script.

#### Scenario: From the one-line install

- **WHEN** a one-line install is followed by pipx's link in its place, as
  `pipx install --force` leaves it, and then by `--install` from the venv's
  payload
- **THEN** the link is skipped and the other sixteen are replaced with the
  package's

#### Scenario: A checkout's install beside pipx

- **WHEN** a checkout's `--install` meets pipx's link
- **THEN** it skips the link, places the sixteen from the checkout, and its
  count line names the checkout's repository and ref and pipx's version

#### Scenario: pip's console script

- **WHEN** `<dir>/openRepoTools` is the regular file `pip install --user`
  writes for openrepotools
- **THEN** `--install` refuses, names that file as pip's, and places nothing

#### Scenario: A shadowed command

- **WHEN** a package-mode `--install` finishes, and the first
  `openRepoTools` on `PATH` is an older bash file in another directory, or
  pipx's bin directory differs from `$OPENREPOTOOLS_BIN_DIR`
- **THEN** it reports which `openRepoTools` the shell will run, and which it
  expected

### Requirement: The README offers only a published package

README SHALL NOT offer the pipx route until PyPI serves the version it
installs, and the workBenches condition stated in this change's proposal
holds. Feature 006 SHALL correct the README's file count, its symlink
paragraph and its artifact-count invariant for a workstation with pipx's
link.

#### Scenario: Before v1.1.0 is on PyPI

- **WHEN** PyPI does not serve `openrepotools` 1.1.0
- **THEN** README has no `pipx install openrepotools` line

### Requirement: The package job

`tests.yml` SHALL have a `package` job on ubuntu with Python 3.9. It SHALL
build the wheel twice at the commit's time and require the two to be one
file. It SHALL check every packaged payload file against the commit's blob
and mode, install the wheel with pipx, and run the unstamped `--version`.
It SHALL run an offline `--install` into a temporary home with a pipx link
in place. It SHALL run the package's tests, the pipx-skip tests among them,
and SHALL fail if any of them was skipped rather than run. The pipx-skip
tests SHALL use fake venv layouts, with no real pipx and no wheel.

#### Scenario: A package test skips

- **WHEN** a package test reports skipped in the `package` job
- **THEN** the job fails

### Requirement: The release build's gates

The release workflow SHALL run only on `workflow_dispatch`, with a
`version` input. It SHALL grant no permission at the workflow level, and
SHALL run one release at a time, never cancelling one in progress. Its build
SHALL refuse unless all of these hold:
- the version is a final `X.Y.Z` other than `0.0.0`, or a pre-release
  `X.Y.ZrcN` bound for TestPyPI;
- on a dispatch on a tag, the dispatched ref is the annotated tag
  `v<version>`, and the tag object names the run's commit, read both from
  the forge and from git;
- on a dispatch on a tag, that commit is on `main` or on `release/v<X.Y>`;
- the dispatched ref is a tag or a branch, and nothing else;
- the checkout is that commit, and it is clean;
- the environments `testpypi` and `pypi` each name a required reviewer, and
  each has a deployment limit of exactly one rule, the tag pattern `v*`;
- each of `guard-launch-mode`, `tests`, `tests-no-submodule` and `package`
  ran in a push or dispatch run of `tests.yml` on that commit, none of those
  runs is still in progress, and the newest to finish succeeded;
- the tree digest computed locally equals the one computed from the forge's
  tree listing, both by the pinned openRepoShape's own digest code;
- the pinned standard's digest definition is `sorted-ls-tree-r-v1`.

A dispatch on a branch is the rehearsal. The two tag-bound checks above
SHALL stand down there, as in openRepoShape's `release.yml:200-249` at
v1.1.0, and every other check SHALL still run.

#### Scenario: A branch dispatch is a rehearsal, not a refusal

- **WHEN** the release workflow is dispatched on a branch
- **THEN** the tag check and the release-branch check pass it as a
  rehearsal, and every other check runs

#### Scenario: A changed digest definition

- **WHEN** the pinned openRepoShape digests by a definition other than
  `sorted-ls-tree-r-v1`
- **THEN** the build refuses, and no wheel is uploaded with a wrong label

#### Scenario: A red or running CI

- **WHEN** the newest finished `tests.yml` run on the commit failed, or one
  is still running
- **THEN** the build refuses

### Requirement: The release build is reproducible

The build SHALL install its tools from a hash lock, wheels only. It SHALL
extract the commit twice with `git archive`, into two different
directories, and stamp and build each with `SOURCE_DATE_EPOCH` at the
commit's time. The two wheels SHALL be one file. Every file in the wheel,
apart from the stamp and the metadata, SHALL be the commit's own blob. The
wheel's sha256 SHALL be recorded, and checked again before and after each
upload.

#### Scenario: Two builds differ

- **WHEN** the two wheels are not byte-identical
- **THEN** nothing is uploaded

### Requirement: Uploads by trusted publishing only

TestPyPI SHALL come first, in the environment `testpypi`, then the install
check, then PyPI, in the environment `pypi`. Only the two upload jobs SHALL
be granted `id-token: write`. There SHALL be no token and no stored secret.
Before it uploads, each upload job SHALL read again its environment's rules,
this run's approval and the tag. The index SHALL hold no other file of that
version, and after the upload it SHALL serve exactly the recorded digest.
The `pypi` job SHALL never upload a pre-release. Nothing SHALL be uploaded
to PyPI from `opensoft/openRepoTools`. v1.1.0 SHALL be published from
`openRepoTools-code`, only once both of its environments and both trusted
publishers exist.

The uploads SHALL be guarded by repository, in the workflow's code:
- in `opensoft/openRepoTools`, the `testpypi` job SHALL take only a
  pre-release `X.Y.ZrcN`, and the `pypi` job SHALL refuse outright;
- in `opensoft/openRepoTools-code`, a pre-release SHALL go to TestPyPI only,
  and a final `X.Y.Z` to TestPyPI and then to PyPI;
- in any other repository, both upload jobs SHALL refuse.

The build SHALL decide this before any approval is asked, and each upload
job SHALL check it again before it uploads. The absence of a pypi.org
publisher for `opensoft/openRepoTools` stays as a second line of defence.

#### Scenario: The rc rehearsal

- **WHEN** `1.1.0rc1` is dispatched on its annotated tag in
  `opensoft/openRepoTools`, and the `testpypi` deployment is approved
- **THEN** it reaches TestPyPI and the install check, and the `pypi` job
  is skipped

#### Scenario: A final version in the wrong repository

- **WHEN** a final `X.Y.Z` is dispatched on its tag in
  `opensoft/openRepoTools`, or any version on a tag in a repository other
  than the two
- **THEN** the build refuses before any approval is asked, and both upload
  jobs refuse if they are ever reached

#### Scenario: The index already holds the version

- **WHEN** the index already holds a file of the version being uploaded
- **THEN** the upload job refuses before uploading

### Requirement: The install check

The install check SHALL run on ubuntu and macOS with a current Python 3, and
on ubuntu with Python 3.9. Each leg SHALL install pipx from its own hash lock
and install the wheel by its digest. Each SHALL check that pipx placed
exactly one command, `openRepoTools`, and that `--version` names the source
repository, the version, the tag, the commit and the digest. Each SHALL
check that an offline `--install` into a temporary home places every artifact
and skips pipx's link with the exact skip and count lines. The macOS leg
SHALL run that `--install` again with Apple's `/bin/bash` 3.2 first on
`PATH`, and print its `BASH_VERSION`. The Python 3.9 leg SHALL compile
`lanes-index` and `lane-worktrees`.

#### Scenario: bash 3.2

- **WHEN** the macOS leg reruns `--install` under `/bin/bash`
- **THEN** it prints a `BASH_VERSION` of 3.2, and the install succeeds with
  the same skip and count lines

### Requirement: Rehearsals never spend the real version

A dispatch on a branch SHALL run every build check and the install check on
its own wheel, and SHALL upload nothing. It builds with the version of the
tag it rehearses; before v1.1.0 that is the next pre-release, `1.1.0rc1` for
the first. A TestPyPI rehearsal SHALL use a pre-release `X.Y.ZrcN` on its
annotated tag. No rehearsal SHALL use the version `1.1.0` itself.

#### Scenario: The branch rehearsal

- **WHEN** the release workflow is dispatched on a branch
- **THEN** every build check and the install check run, and no upload job
  runs

### Requirement: The cutover invariants

In `openRepoTools-code`, `tests.yml` SHALL keep the job ids
`guard-launch-mode`, `tests`, `tests-no-submodule` and `package` that the
release gate requires. No release step SHALL read a file outside the code
leg. The code leg's `LICENSE` SHALL be blob `261eeb9`, from its first commit
after `execute` on, before any CI, package or release run there.

#### Scenario: A missing job

- **WHEN** the code leg's `tests.yml` no longer has one of the four job ids
- **THEN** the release build refuses, because no run of that job on the
  commit succeeded
