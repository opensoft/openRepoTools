# Feature Specification: Release tags, release branches and the `openrepotools` package on PyPI

**Feature Branch**: `006-release-pypi`

**Created**: 2026-10-17

**Status**: Draft

**Input**: User description: the OpenSpec change `release-tags-pypi`, for
opensoft/openRepoTools#228. Brett Heap, 2026-10-17: "lets setup tagging and
release branches. we will publish on pypi. lets assume we are currently on
1.0.0 and we will do our first real release on pypi with v1.1.0. look at the
way we did this for openRepoShape and lets do similar."

**Governance**: this is the one Speckit feature of that change. Its sources,
and the only scope it takes, are:

- [proposal.md](../../openspec/changes/release-tags-pypi/proposal.md), with
  Brett Heap's decisions and his answers of 2026-10-17T21:51:50Z;
- [clarifications.md](../../openspec/changes/release-tags-pypi/clarifications.md),
  the council's constraints N1 to N5 and its dismissals D1 to D3;
- [design.md](../../openspec/changes/release-tags-pypi/design.md), with the
  lead's rulings of 2026-10-17 in its Open Questions;
- the two delta specs,
  [release-tags-and-branches](../../openspec/changes/release-tags-pypi/specs/release-tags-and-branches/spec.md)
  and [pypi-package](../../openspec/changes/release-tags-pypi/specs/pypi-package/spec.md).

**What this feature builds**: what lands in `opensoft/openRepoTools` by pull
request. That is the package, the installer's changes, the tests, the
`package` CI job, the release workflow and its hash locks, the release notes,
and the README and AGENTS.md corrections. It builds no act outside the
repository. Brett Heap makes those acts, or lane openRepoTools-3 makes them on
his word, and the change's `tasks.md` tracks them:

- the GitHub environments and rulesets;
- the trusted publishers;
- every tag, dispatch, upload, GitHub Release and release-branch cut;
- the assembly's README pull request after v1.1.0;
- the workBenches issue.

## User Scenarios & Testing *(mandatory)*

The terms used below:

- **`<dir>`** is `$OPENREPOTOOLS_BIN_DIR`, by default `~/.local/bin`.
- **The package** is the `openrepotools` wheel.
- **Package mode** is the installer run from inside an installed package.
- **pipx's link** is the `<dir>/openRepoTools` that pipx places. FR-015
  defines it exactly.

### User Story 1 - Install the toolset from the package, offline (Priority: P1)

A person installs `openrepotools` with pipx, then runs
`openRepoTools --install`. The install takes everything from inside the
package and reaches no network. pipx keeps its own `openRepoTools` command,
and the install places every other artifact.

**Why this priority**: decision 3 is that the wheel carries the whole tool
payload and installs offline. Every other story stands on a package that
installs.

**Independent Test**: build the wheel and install it with pipx into a
temporary pipx home. Then run `--install` into a temporary home with every
network path refused. The pipx-link behaviour can also be tested alone, on
fake venv layouts, with no pipx and no wheel.

**Acceptance Scenarios**:

1. **Given** the package installed by pipx, which placed exactly one command,
   pipx's link, **When** `openRepoTools --install` runs with a sentinel
   `$OPENREPOTOOLS_REPO`, no `gh` and a `curl` that fails, **Then** it
   succeeds, and:
   - it prints the skip line exactly (FR-016);
   - it places the other sixteen files, the three skills, the three command
     files and the two hook entries;
   - it prints `openRepoTools: 16 of 17 placed in <dir>, and 1 left to pipx`;
   - it writes 28 receipt rows;
   - it leaves the link as it was.
2. **Given** pipx's venv laid out as pipx 1.11.1, 1.17.8 or 1.18.3 lays it
   out, under `$PIPX_HOME`, `~/.local/pipx`, `~/.local/share/pipx` or a home
   whose path holds a space, **When** `--install` runs, **Then** the link is
   recognised the same way in every case.
3. **Given** `<dir>/openRepoTools` links into a venv that has no
   `openrepotools` payload, or no `pipx_metadata.json`, or a target not under
   `bin/`, **When** `--install` runs, **Then** it refuses before placing
   anything.
4. **Given** any target other than pipx's link is a symbolic link, **When**
   `--install` runs, **Then** it refuses, names that link, and places
   nothing.
5. **Given** no `jq` on `PATH` and pipx's link in place, **When** `--install`
   runs, **Then** it refuses for want of `jq`, and its output advises no `rm`
   of pipx's link.
6. **Given** the console script, **When** the payload refuses the person's
   arguments, **Then** the exit status and the message are the payload's
   own.
7. **Given** the console script, **When** a package-mode `--install` is
   interrupted by a signal while it is placing a file, **Then** no temporary
   placement file is left beside the target.
8. **Given** no `bash` on `PATH`, **When** the console script runs, **Then**
   it refuses, naming `bash`, and nothing else runs.
9. **Given** the package, **When** `wip init` runs from it, **Then** it reads
   the openRepoShape pin packaged with the release.

---

### User Story 2 - Know which release is running (Priority: P1)

A person runs `openRepoTools --version`. From a release, it names the
release: the version, the tag, the commit, the tree digest and the
repository it was built from. From a package built outside a release, it says
so. From a checkout or a one-line install, it prints what it prints today.
A package whose stamp is broken refuses to run at all.

**Why this priority**: "a workstation cannot say which release it runs" is the
first problem the proposal names. A wrong answer is worse than none.

**Independent Test**: build fake package layouts, each with a stamp file, and
run `--version`, `--help` and `--install` against each.

**Acceptance Scenarios**:

1. **Given** the v1.1.0 package from `openRepoTools-code`, **When**
   `--version` runs, **Then** it prints exactly five lines. The first is
   `openRepoTools 1.1.0 (opensoft/openRepoTools-code @ <commit>)`. The other
   four are the version, the tag `v1.1.0`, the commit and the digest
   (FR-014).
2. **Given** an unstamped package, as the `package` job builds it, **When**
   `--version` runs, **Then** it prints the five unstamped lines exactly
   (FR-014).
3. **Given** a checkout or a one-line install, **When** `--version` runs,
   with or without any `OPENREPOTOOLS_PACKAGE_*` variable set, **Then** it
   prints exactly `openRepoTools (<repo> @ <ref>)`, as today.
4. **Given** a package whose stamp has a commit but no digest, or breaks the
   all-or-nothing rule in any other way, **When** any invocation runs, such
   as `--version`, `--help` or `--install`, **Then** it refuses with exit 2.
   The refusal names the stamp file and the fix,
   `pipx reinstall openrepotools`, and prints no version.
5. **Given** a well-stamped package, **When** `--help`, `--install --version`
   or an unknown argument is given, **Then** it behaves as a checkout does.
6. **Given** the stamp that the release build's writer produces, **When** the
   command reads it, **Then** it reads the same five values. The build
   backend's version reader and the command read the same `VERSION`.

---

### User Story 3 - Move between installers without being misled (Priority: P2)

A workstation can carry pipx's command next to the one-line install, a
checkout's `--install`, pip, or workBenches' `./setup.sh`. Each pairing has
one defined outcome. None may leave a person believing they run a release
while they track `main`.

**Why this priority**: this is the failure the Why exists to prevent. It
matters only once the package exists (User Stories 1 and 2).

**Independent Test**: fake layouts for each pairing: a one-line install, a
checkout, pip's console script, two wheels in turn, a removed venv, and a
`PATH` that shadows the package.

**Acceptance Scenarios**:

1. **Given** a one-line install, then pipx's link in its place as
   `pipx install --force` leaves it, **When** `--install` runs from the venv's
   payload, **Then** the link is skipped and the other sixteen are replaced
   with the package's.
2. **Given** pipx's link, **When** a checkout's or the one-line install's
   `--install` runs, **Then** it skips the link and places the other sixteen
   from its own source. Its count line names that source, as
   `<repo> @ <ref>`, and the version of the stamp beside the link's payload
   (FR-019).
3. **Given** `<dir>/openRepoTools` is the regular file that
   `pip install --user openrepotools` writes, **When** `--install` runs in any
   mode, pip's own included, **Then** it refuses with the exact refusal, names
   the file as pip's console script, and places nothing (FR-020).
4. **Given** a finished package-mode `--install`, **When** the first
   `openRepoTools` on `PATH` is an older bash file in another directory, or
   pipx's bin directory differs from `$OPENREPOTOOLS_BIN_DIR`, or there is
   none, **Then** it prints the exact note naming the `openRepoTools` the
   shell will run and the one it expected. The exit status does not change
   (FR-021).
5. **Given** one wheel installed with `--install`, **When** pipx upgrades it
   to a second and `--install` runs again, **Then** the second wheel's files
   replace the sixteen, and the link is still skipped.
6. **Given** pipx's link and its environment are removed, **When** the person
   looks, **Then** the sixteen files are still there. A checkout's
   `--install` then places a regular file at `<dir>/openRepoTools`.

---

### User Story 4 - Every commit proves it packages (Priority: P2)

The release gate trusts only a commit whose own CI ran and passed. That CI
must therefore build the package, check it against the commit, install it
and run its tests, on every push to `main` and to every release branch.

**Why this priority**: the release workflow (User Story 5) refuses a commit
without a green `package` job. Without this story there is no release.

**Independent Test**: push a commit to a branch that `tests.yml` runs on, and
read the `package` job. Push a tree that has no `LICENSE`, or a payload file
that differs from its blob, and see the job fail.

**Acceptance Scenarios**:

1. **Given** a commit pushed to `release/v1.1`, **When** CI runs, **Then** a
   `tests.yml` push run runs `guard-launch-mode`, `tests`,
   `tests-no-submodule` and `package` on that commit.
2. **Given** the `package` job, **When** it builds the wheel twice at the
   commit's time, **Then** the two are one file, and:
   - every packaged payload file equals the commit's blob, in bytes and in
     mode;
   - the `.dist-info` holds exactly the five names, with the commit's
     `LICENSE`.
3. **Given** a tree with no `LICENSE`, **When** the `package` job runs,
   **Then** it fails.
4. **Given** the `package` job's unstamped wheel installed with pipx,
   **When** it runs `--version`, and then an offline `--install` into a
   temporary home with pipx's link in place, **Then** the unstamped lines,
   the skip line and the count line are exact.
5. **Given** the package's tests, **When** one of them reports skipped, or
   none is collected, **Then** the job fails.

---

### User Story 5 - Publish a release only through gates (Priority: P2)

The release owner dispatches the release workflow on an annotated tag. It
builds the wheel reproducibly from that commit and uploads it to TestPyPI.
It checks the install on three platforms, then uploads to PyPI. Each step
waits for Brett Heap's approval, and every check runs again where it can.
Nothing uploads from anywhere else, or by any other means.

**Why this priority**: this is how v1.1.0 reaches PyPI. Its real uploads wait
for the cutover and for Brett Heap's acts, but the workflow lands now and is
rehearsed now.

**Independent Test**: dispatch it on a branch, which is the branch rehearsal.
Every build check and the install check run, and no upload job runs. The
workflow's file is also checked offline by the suite, which runs the
workflow's stamp writer.

**Acceptance Scenarios**:

1. **Given** a dispatch on a lightweight tag, or on an annotated tag whose
   object names a different commit, **When** the build runs, **Then** it
   refuses, and nothing is built or uploaded.
2. **Given** the newest finished `tests.yml` run on the commit failed, or
   one is still running, **When** the build runs, **Then** it refuses.
3. **Given** the pinned openRepoShape digests by a definition other than
   `sorted-ls-tree-r-v1`, **When** the build runs, **Then** it refuses, and
   no wheel is uploaded with a wrong label.
4. **Given** the two builds are not byte-identical, **When** the build ends,
   **Then** nothing is uploaded.
5. **Given** the index already holds a file of the version, **When** an
   upload job runs, **Then** it refuses before uploading.
6. **Given** `1.1.0rc1` dispatched on its annotated tag in
   `opensoft/openRepoTools`, with the `testpypi` deployment approved,
   **When** the run proceeds, **Then** it reaches TestPyPI and the install
   check, and the `pypi` job refuses it.
7. **Given** a dispatch on a branch, **When** the run proceeds, **Then** every
   build check and the install check run, and no upload job runs.
8. **Given** an upload job and no approval for its environment, **When** the
   run reaches it, **Then** the job waits, and nothing is uploaded.
9. **Given** the macOS leg of the install check, **When** it reruns
   `--install` under `/bin/bash`, **Then** it prints a `BASH_VERSION` of 3.2,
   and the install succeeds with the same skip and count lines.

---

### User Story 6 - The record tells the truth about releases (Priority: P3)

A reader of the repository learns how releases work, and finds each one's
notes, without being offered anything that is not published. The documents
cover the tags, the release branches, the back-ports and the patch tags.

**Why this priority**: the procedure and the documents follow the mechanisms.
They are what a person reads, so they must not run ahead of what exists.

**Independent Test**: compare the v1.0.0 notes with the published Release
body. Then read README for the version paragraph, the three corrected
passages, and the absence of the pipx route.

**Acceptance Scenarios**:

1. **Given** `docs/release-notes/v1.0.0.md`, **When** it is compared with the
   body `gh release view v1.0.0` returns, **Then** the two are identical.
2. **Given** README, **When** PyPI does not serve `openrepotools` 1.1.0,
   **Then** README has no `pipx install openrepotools` line.
3. **Given** README's version paragraph, **When** it is read, **Then** it
   says that:
   - releases are annotated tags;
   - the version comes only from the tag;
   - it shows what `--version` prints, stamped and unstamped.
4. **Given** a workstation with pipx's link, **When** README's file count,
   symlink paragraph and artifact-count invariant are read, **Then** they say
   what that workstation sees: sixteen placed and one left to pipx, pipx's
   `openRepoTools` the one link skipped, and thirty placed with 28 receipt
   rows.
5. **Given** a later release is tagged, **When** `v1.0.0` is read, **Then** it
   still names tag object `6a826f8` on commit `aaa7bc8`.
6. **Given** a fix lands on `main` after work for the next minor version,
   **When** it is back-ported, **Then** it reaches `release/v1.1` only by a
   pull request of `git cherry-pick -x <squash commit>`.

---

### Edge Cases

- **A chain of links or a cycle.** A chain longer than the design's hop limit
  (40), or a cycle, is not pipx's link. It is refused as any other link is.
- **A future pipx layout.** A link into a directory that looks like a venv
  (it holds `pyvenv.cfg`) but fails the pipx rule is refused. The refusal
  calls it "a link into a Python environment, perhaps pipx's". It prints no
  `rm` for it, names `pipx reinstall openrepotools`, and asks for an issue
  with the layout. This keeps the person from deleting the only working
  command.
- **The stamp beside another install's payload.** When that stamp fails the
  reader, the checkout's count line names `an unreadable stamp`, and the
  install goes on: the stamp belongs to another install.
- **A carriage return, a repeated name or an unclosed docstring in the
  stamp.** Each is refused with its own reason, as a broken build.
- **A docstring line that the build backend could read as the version.** It
  is refused, so the backend and the command never disagree.
- **A plain `pipx install` over the one-line install's file.** pipx only
  warns and places no link. No package-mode run happens, so no report can
  appear. README gives `pipx install --force` for that reason.
- **`git archive` changing bytes through `.gitattributes`.** The blob check
  compares every packaged file with the commit's blob, so the build refuses
  and never ships. An `export-ignore` on a payload path fails the
  wheel-against-payload-list test.
- **A job id renamed in the code leg's `tests.yml`.** The gate finds no run
  of that job and refuses.
- **A later pin that changes the digest definition.** The build refuses
  rather than ship a wrong label.
- **The version `0.0.0`, or a pre-release on the `pypi` job.** Both are
  refused.
- **A rehearsal that would use `1.1.0`.** It is ruled out: an index never
  takes a file name twice, and v1.1.0 is later built from another commit.

## Requirements *(mandatory)*

### Functional Requirements

#### The package

- **FR-001**: The package MUST meet all of these:
  - it is named `openrepotools` and requires Python 3.9 or later;
  - it declares no dependencies, exactly one console script,
    `openRepoTools`, and the licence `Apache-2.0` with the file `LICENSE`;
  - it declares no `readme`;
  - its version is read only from the package's stamp.

  A test MUST hold `dependencies` empty, the scripts table to that one
  entry, and the `readme` key absent.
- **FR-002**: The wheel's `.dist-info` MUST hold exactly `METADATA`, `WHEEL`,
  `RECORD`, `entry_points.txt` and `licenses/LICENSE`, and that `LICENSE`
  MUST be the commit's.
  - The `package` job and the release build MUST refuse any other wheel,
    including one built from a tree that has no `LICENSE`.
  - The package MUST NOT be made to tolerate a missing `LICENSE`.
- **FR-003**: The console script MUST replace its own process with the first
  `bash` on `PATH`. That bash runs the packaged `openRepoTools` with the
  person's arguments unchanged. Signals, the exit status and the payload's
  clean-up on exit MUST pass through as if the person had run the payload
  with bash directly. The console script MUST pass bash nothing beyond the
  arguments, and MUST NOT read the stamp.
- **FR-004**: With no `bash` on `PATH`, the console script MUST refuse with
  exit 2 and a message naming `bash`, and MUST run nothing.
- **FR-005**: The package's Python modules MUST import only the standard
  library. A hygiene test MUST fail when one imports anything else. The
  existing compile test MUST compile them too.
- **FR-006**: The wheel MUST hold each of these at
  `openrepotools/payload/<path>`, every one byte-identical to the commit's
  blob and with the commit's mode (`100755` or `100644`):
  - every file the installer's payload list names: the seventeen
    installables (sixteen commands and `repos.tsv`), the three skills and
    the three command files;
  - and `contracts/openreposhape-pin.yaml`.
- **FR-007**: The installer's payload list MUST stay the only list of payload
  files. A test MUST fail, naming the file, when a file is in that list but
  missing from the wheel's declared contents or from the built wheel, or the
  other way round.
- **FR-008**: The install from the package MUST need no network.
  - After `pipx install` of the wheel, `openRepoTools --install` MUST place
    every artifact and write every receipt row from the payload inside the
    package, with every network path refused.
  - The result MUST be the same as an install from beside a full checkout,
    except for pipx's link.
  - `wip init` run from the package MUST read the release's own openRepoShape
    pin.

#### The stamp and `--version`

- **FR-009**: The committed stamp MUST be unstamped: `VERSION` is `0.0.0`,
  and `TAG`, `COMMIT`, `DIGEST` and `REPOSITORY` are empty.
  - Only the release build MUST write a stamp. It writes the version taken
    from the tag, the tag, the tag's 40-hex commit, that commit's
    `sorted-ls-tree-r-v1` tree digest, and the release run's source
    repository.
  - No other file MUST carry a version number.
- **FR-010**: The stamp MUST be all or nothing.
  - It is unstamped when `TAG`, `COMMIT` and `DIGEST` are all empty, and then
    `VERSION` MUST be `0.0.0` and `REPOSITORY` empty.
  - Otherwise every field MUST be set, and:
    - `VERSION` is a final `X.Y.Z`, or a pre-release `X.Y.ZrcN`, and is not
      `0.0.0`;
    - `TAG` is exactly `v<VERSION>`;
    - `COMMIT` is 40 lowercase hex digits and `DIGEST` is 64;
    - `REPOSITORY` is an owner/name slug.
  - Any other stamp MUST be refused as a broken build, and never read as the
    part it holds.
- **FR-011**: The command MUST read the stamp only from the package's own
  stamp file, beside its payload directory.
  - It reads it by a fixed grammar, and never sources, imports or runs it.
  - The reader MUST hold to bash 3.2.
  - The command MUST trust no environment variable for the stamp.
  - The reader MUST refuse each of these, each with its own reason: an
    unreadable file, a carriage return, a missing, repeated or unknown name,
    a partial stamp, and a malformed field.
- **FR-012**: In package mode the command MUST read its stamp before it acts
  on any argument. A broken stamp MUST refuse every invocation, `--help`
  included, with exit 2. The refusal MUST name the stamp file and the fix,
  `pipx reinstall openrepotools`.
- **FR-013**: Readers and writer MUST agree.
  - The release build's stamp writer and the command's reader MUST agree, and
    a test MUST pass the writer's output through the reader.
  - The build backend's version reader and the command's reader MUST read the
    same `VERSION` from the committed stamp and from a stamped one.
- **FR-014**: `--version` MUST print exactly:
  - from a stamped package:

    ```text
    openRepoTools <version> (<repository> @ <commit>)
      version   <version>
      tag       <tag>
      commit    <commit>
      digest    <digest> (sorted-ls-tree-r-v1)
    ```

  - from an unstamped package:

    ```text
    openRepoTools 0.0.0 (an unstamped package)
      version   0.0.0, unstamped: a package built from a checkout, not a release
      tag       none
      commit    none
      digest    none
    ```

  - from a checkout or the one-line install, what it prints today:
    `openRepoTools (<repo> @ <ref>)`. The existing assertions stay as they
    are, and only their docstring, which says "no version number", is
    rewritten.

  In a package whose stamp passes FR-010, `--help`, `--install --version`
  and the parser's refusals MUST behave as they do in a checkout. A broken
  stamp refuses all of them first (FR-012). `--version` names the command's
  release, not the release of the files `--install` placed.

#### `--install` and pipx

- **FR-015**: `<dir>/openRepoTools` MUST be treated as pipx's link only when
  all of these hold:
  - it is a symbolic link;
  - it resolves to a regular file `<venv>/bin/openRepoTools`;
  - that `<venv>` holds a `pipx_metadata.json`, and an
    `openrepotools/payload/` tree in its `lib/python*/site-packages/`.

  The check:
  - MUST use only paths and the existence of files;
  - MUST parse no JSON and need no `jq`;
  - MUST NOT depend on `PIPX_HOME`;
  - MUST hold under bash 3.2;
  - MUST hold in every mode: the package's own `--install`, a checkout's and
    the one-line install's;
  - MUST be decided before any link refusal.
- **FR-016**: On pipx's link, `--install` MUST skip that one target and print
  exactly
  ``openRepoTools: left to pipx at <dir>/openRepoTools (a link into pipx's openrepotools environment); update it with `pipx upgrade openrepotools`, then run `openRepoTools --install` again``.
  - It MUST place every other artifact.
  - It MUST write no receipt row for the link: 28 rows, against a full
    install's 29.
  - Run from pipx's own environment, its count line MUST be exactly
    `openRepoTools: 16 of 17 placed in <dir>, and 1 left to pipx`.
  - No install, and no retirement, MUST ever remove, replace or write through
    pipx's link.
- **FR-017**: Every other link at a target MUST still refuse the whole install
  before anything is placed, and no refusal MUST advise removing pipx's
  link. A venv-looking link that fails FR-015 MUST be refused in these terms:
  - the refusal calls it "a link into a Python environment, perhaps pipx's";
  - it prints no `rm` for that link;
  - it names `pipx reinstall openrepotools`;
  - it asks for an issue with the layout.
- **FR-018**: The `jq` check MUST stay where it is, after the targets are
  asked about. With no `jq` and pipx's link in place, the run MUST refuse for
  want of `jq` and print no `rm` for the link.
- **FR-019**: A checkout's or the one-line install's `--install` that meets
  pipx's link MUST skip it. Its count line MUST be exactly
  `openRepoTools: 16 of 17 placed in <dir>, and 1 left to pipx; the other 16 now come from <repo> @ <ref>, not from openrepotools <version>`.
  - `<repo> @ <ref>` is the source the run collected from.
  - `<version>` is the stamp beside the link's payload, read as `--version`
    reads it: `0.0.0` when that stamp is unstamped, and `an unreadable stamp`
    when it fails the reader. In that last case the install goes on.
- **FR-020**: In every mode, `--install` MUST refuse to replace a regular file
  at `<dir>/openRepoTools` that is pip's console script for openrepotools.
  - The refusal MUST come in the planning phase, so nothing is placed.
  - Its text MUST be design.md Decision 8's: it names the file as pip's
    console script, says nothing was installed, and names pipx as the way
    out.
  - Such a script is recognised by its first line, a `#!` naming a Python,
    together with the import of the `openrepotools` entry point that pip's
    console-script template writes.
- **FR-021**: Once a package-mode `--install` has placed its files, it MUST
  report when the first `openRepoTools` on `PATH`, with its links resolved,
  is not that package's console script, or when there is none.
  - The report is design.md Decision 8's one line. It names the
    `openRepoTools` that `PATH` finds and the one expected.
  - It MUST change nothing, and MUST leave the exit status as it was.
- **FR-022**: After `pipx upgrade openrepotools`, the placed files, skills,
  command files and hook entries MUST stay the earlier release's until
  `--install` runs again. That `--install` MUST replace them and still skip
  the link.
- **FR-023**: `pipx uninstall openrepotools` removes only the link and its
  environment.
  - The placed files, the skills, the command files, the hook entries and
    the receipt MUST stay.
  - A later checkout's `--install` MUST place a regular `openRepoTools` at
    the freed path.
- **FR-024**: The documented move from the one-line install to pipx MUST be
  `pipx install --force openrepotools`, then `openRepoTools --install`.

#### Continuous integration

- **FR-025**: `tests.yml` MUST run on `push` to `main` and to every
  `release/v*` branch, as well as on its existing triggers.
  - Every run MUST include the jobs `guard-launch-mode`, `tests`,
    `tests-no-submodule` and `package`.
  - The three existing jobs MUST stay unchanged.
  - The header comment that says "`push` (main only)" and "those same three
    jobs" MUST be rewritten for the two branches and the four jobs.
- **FR-026**: `tests.yml` MUST have a `package` job on ubuntu with Python 3.9.
  It MUST do each of these:
  - build the wheel twice at the commit's time, and require the two to be
    one file;
  - check every packaged payload file against the commit's blob and mode;
  - check the `.dist-info` as FR-002 states;
  - install the wheel with pipx;
  - run the unstamped `--version`;
  - run an offline `--install` into a temporary home with a pipx link in
    place;
  - run the package's tests, the pipx-skip tests among them, and fail if any
    of them was skipped rather than run, or none ran.

  The pipx-skip tests MUST use fake venv layouts, with no real pipx and no
  wheel.
- **FR-027**: AGENTS.md's CI paragraph MUST be rewritten to match FR-025 and
  FR-026. Its line cap MUST move only by a dated entry, as the hygiene test
  requires.

#### The release workflow

- **FR-028**: `.github/workflows/release.yml` MUST meet all of these:
  - it runs only on `workflow_dispatch`, with a `version` input;
  - it grants no permission at the workflow level, and each job grants its
    own;
  - it runs one release at a time, and never cancels one in progress;
  - it is adapted from openRepoShape v1.1.0's (`190133d`), taking over that
    workflow's checks as they are, except where design.md Decision 10 names
    a difference.
- **FR-029**: The build MUST refuse unless every one of these holds:
  - the version is a final `X.Y.Z` other than `0.0.0`, or a pre-release
    `X.Y.ZrcN` bound for TestPyPI;
  - on a dispatch on a tag, the dispatched ref is the annotated tag
    `v<version>`, and the tag object names the run's commit, as read both
    from the forge and from git;
  - on a dispatch on a tag, that commit is on `main` or on `release/v<X.Y>`;
  - the dispatched ref is a tag or a branch, and nothing else;
  - the checkout is that commit, and it is clean;
  - the environments `testpypi` and `pypi` each name a required reviewer,
    and each has a deployment limit of exactly one rule, the tag pattern
    `v*`;
  - each of `guard-launch-mode`, `tests`, `tests-no-submodule` and `package`
    ran in a push or dispatch run of `tests.yml` on that commit, none of
    those runs is still in progress, and the newest to finish succeeded;
  - the tree digest computed locally equals the one computed from the
    forge's tree listing, both by the pinned openRepoShape's own digest code;
  - the pinned standard's digest definition is `sorted-ls-tree-r-v1`, the
    literal that `--version` labels the digest with and that
    `contracts/openreposhape-pin.yaml` names.

  A dispatch on a branch is the rehearsal of FR-033, as in the model
  (`release.yml:200-249` at v1.1.0). The two tag-bound checks above stand
  down, because a branch has no tag and no release branch to be on. Every
  other check still runs, and no upload job runs.
- **FR-030**: The build MUST be reproducible.
  - It installs its tools from a hash lock, wheels only, with hatchling at
    the package's own pin.
  - It extracts the commit twice with `git archive`, into two different
    directories, and stamps and builds each with `SOURCE_DATE_EPOCH` at the
    commit's time.
  - The two wheels MUST be one file.
  - Every file in the wheel apart from the stamp and the metadata MUST be the
    commit's own blob, with its mode, and the `.dist-info` MUST pass FR-002.
  - The wheel's sha256 MUST be recorded, and checked again before and after
    each upload.
  - No copy of the digest code MUST be added: the build runs the pinned
    submodule's.
- **FR-031**: The uploads MUST go by trusted publishing only.
  - The order is TestPyPI in the environment `testpypi`, then the install
    check, then PyPI in the environment `pypi`.
  - Only the two upload jobs MUST be granted `id-token: write`, and there
    MUST be no token and no stored secret.
  - Each upload job, before it uploads, MUST read again its environment's
    rules, this run's approval and the tag.
  - The index MUST hold no other file of that version before the upload, and
    MUST serve exactly the recorded digest after it.
  - The `pypi` job MUST refuse every pre-release.
  - Nothing MUST ever upload to PyPI from `opensoft/openRepoTools`.
  - v1.1.0 MUST be published from `openRepoTools-code`, and only once both of
    its environments and both trusted publishers exist.
- **FR-032**: The install check MUST run on ubuntu and macOS with a current
  Python 3, and on ubuntu with Python 3.9. Each leg MUST:
  - install pipx from its own hash lock;
  - install the wheel by its digest, and check that pipx placed exactly one
    command, `openRepoTools`;
  - check that `--version` names the source repository, the version, the
    tag, the commit and the digest;
  - check that an offline `--install` into a temporary home places every
    artifact and skips pipx's link, with the exact skip and count lines.

  The macOS leg MUST run that `--install` again with Apple's `/bin/bash` 3.2
  first on `PATH`, and print its `BASH_VERSION`. The Python 3.9 leg MUST
  compile `lanes-index` and `lane-worktrees`. There is no Windows leg.
- **FR-033**: Rehearsals MUST never spend the real version.
  - A dispatch on a branch MUST run every build check and the install check
    on its own wheel, and MUST upload nothing.
  - A TestPyPI rehearsal MUST use a pre-release `X.Y.ZrcN`, on its annotated
    tag.
  - No rehearsal MUST use the version `1.1.0` itself.
- **FR-034**: The release procedure (RELEASING) MUST be written in
  `release.yml`'s header, as the model's is. It MUST include the branch and
  tag policy of FR-036 to FR-041. It MUST also include the step that creates
  each GitHub Release by hand from its notes file, after PyPI serves the
  version. No step of the release workflow MUST read the release notes.
- **FR-035**: Every pin MUST be exact.
  - Every action the release workflow uses MUST be pinned by a full commit,
    as `tests.yml` pins its own.
  - Both uploads MUST use
    `pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33`
    (v1.14.2).
  - The release build's tools MUST come from
    `.github/release-build-requirements.txt`, and the install check's pipx
    from `.github/release-pipx-requirements.txt`. Each is installed by hash,
    wheels only.
  - These files record pins and digests, so they are governed files.

#### Release identity

- **FR-036**: A release MUST be an annotated tag `vX.Y.Z` on a commit that is
  on `main` or on `release/vX.Y`.
  - It MUST NOT be a branch, nor a version number committed to any file.
  - The tag message MUST have the form `v1.0.0` uses: the line
    `openRepoTools vX.Y.Z`, a paragraph, the line
    `Tagged on Brett Heap's word (<time>, "<words>")` with `<time>` the exact
    UTC second, and the line `Lane: <lane>`.
  - A tag MUST NOT be moved, deleted or reused once pushed.
  - A version is uploaded once. A bad upload MUST be fixed by the next patch
    version.
- **FR-037**: `release/vX.Y` MUST be cut at the `vX.Y.0` tag, right after that
  tag is made. Each patch `vX.Y.Z` with Z above 0 MUST be tagged on
  `release/vX.Y`. Every PR MUST land on `main`, the trunk.
- **FR-038**: A fix MUST land on `main` first, through its own review and CI.
  - While `main` holds only that patch line's work, the back-port MUST be a
    fast-forward of `release/vX.Y` or a merge of `main`.
  - Otherwise it MUST be a PR to `release/vX.Y` of
    `git cherry-pick -x <squash commit>`.
  - At most one HOLD MUST be open at a time on `release/vX.Y`.
  - The lane that landed the PR MUST make the back-port, unless the release
    owner fast-forwards.
  - The LANDED line MUST name both commits.
- **FR-039**: A patch MUST be tagged on `release/vX.Y` only once that commit's
  `tests.yml` runs have all finished, and the newest of them has succeeded.
  When a commit reached the branch by fast-forward, the newer of `main`'s
  push run and the branch's own MUST decide.
- **FR-040**: Every tag, every release-branch cut and every upload MUST wait
  for Brett Heap's word, and each deployment to `testpypi` and `pypi` for his
  approval. Lane openRepoTools-3, the release owner, MUST carry out these
  acts on his word, and no other lane MUST make them.
- **FR-041**: From v1.1.0 on, release tags MUST be made in
  `openRepoTools-code`, where the release is built. `v1.0.0` and every `rc`
  rehearsal tag MUST stay in `opensoft/openRepoTools`. No tag MUST be carried
  from one repository to another at the cutover.

#### Release notes and README

- **FR-042**: Each release MUST have its notes in
  `docs/release-notes/vX.Y.Z.md`.
  - `docs/release-notes/v1.0.0.md` MUST hold the body of the published v1.0.0
    Release, byte for byte.
  - `docs/release-notes/v1.1.0.md` is a draft. Each of its placeholders MUST
    be filled in or cut before its tag. It ends with a line naming its own
    path in the spec leg.
  - Each GitHub Release MUST be created from its notes file, and, for a
    version published on PyPI, only after PyPI serves that version.
  - The notes stay under `docs/`, which goes to the spec leg.
- **FR-043**: README's paragraph that says "There is no version number here"
  MUST be rewritten. It MUST say:
  - that releases are annotated tags;
  - that the version comes only from the tag;
  - what `--version` prints, stamped and unstamped.
- **FR-044**: README MUST correct three passages for a workstation with
  pipx's link:
  - the count of seventeen files: sixteen placed and one left to pipx;
  - the symlink paragraph: pipx's `openRepoTools` is the one link skipped;
  - the artifact-count invariant: thirty placed, one left to pipx, and 28
    receipt rows.
- **FR-045**: README MUST NOT offer the pipx route until PyPI serves the
  version it installs, and the workBenches condition holds.
  - This feature MUST NOT add the pipx route's text.
  - That text is fixed in the proposal, and lane openRepoTools-3 adds it to
    the assembly's README by a later PR, on Brett Heap's word.
  - README's line cap MUST move only by a dated entry.

#### The cutover invariants

- **FR-046**: The release gate's four job ids MUST stay as job ids in
  `tests.yml`: `guard-launch-mode`, `tests`, `tests-no-submodule` and
  `package`.
  - No step of `release.yml` MUST read a file outside what the code leg will
    hold. That rules out what the adoption plan sends to the spec leg or the
    root: `docs/`, `openspec/`, `specs/`, `README.md`, `AGENTS.md` and
    `CLAUDE.md`.
  - `LICENSE` is the one root file the build reads, because `code-0001`
    gives the code leg a byte-identical copy.
  - The code leg's `LICENSE` MUST be blob `261eeb9` from its first commit
    after `execute` on, before any CI, package or release run there. Lane
    openRepoTools-3 checks it; the change's `tasks.md` item 5.2 tracks that
    check.
  - This feature asks lane openRepoTools-1's adoption plan to carry these
    invariants, and does not edit `openspec/changes/migrate-to-triad/`.

#### Pending Brett Heap's word (not a blocker)

- **FR-047 (pending)**: The workBenches condition.
  - workBenches' `./setup.sh` refuses a symlinked `openRepoTools` before it
    installs anything (`check_target_preflight`).
  - After installing, it requires a regular file identical to its vendored
    copy (`verify_installed`).
  - Both checks stand at workBenches main `bdab3e2`. So on a workstation
    with pipx's link, every `./setup.sh` refuses its estate step.
  - Brett Heap's choice of (a), (b) or (c) is pending.
  - Under position (c), lane openRepoTools-3 files a workBenches issue on his
    word, for workBenches to accept pipx's link. README offers pipx only
    after that fix lands, and until then says that a workstation uses one
    route or the other, never both.
  - This changes only when FR-045's README text may appear. No task in this
    feature depends on it until his word arrives.

### Key Entities

- **The stamp**: the package's `_release.py`. It holds five fields:
  `VERSION`, `TAG`, `COMMIT`, `DIGEST` and `REPOSITORY`. It is in one of
  three states: unstamped (the committed file), stamped (written only by the
  release build), or broken (anything else, always refused).
- **The payload list**: the installer's own list of every file `--install`
  reads, the seventeen installables, three skills and three command files.
  The wheel adds the openRepoShape pin.
- **The package**: the `openrepotools` wheel. It holds the entry module, the
  stamp, and the payload at `openrepotools/payload/`, with a `.dist-info` of
  exactly five names.
- **pipx's link**: `<dir>/openRepoTools` as FR-015 defines it, with its venv
  and that venv's payload. Its counterparts are pip's console script (a
  regular file) and a venv-looking link that is not provably pipx's.
- **An install run's result**: what was placed and counted, what was left to
  pipx, and the receipt rows. Thirty-one artifacts are 17 files, 6 skill
  files, 6 command files and 2 hook entries. With pipx's link, 30 are placed,
  1 is left to pipx, and there are 28 receipt rows.
- **A release**: an annotated tag `vX.Y.Z`, with its tag message, its commit,
  its tree digest, its notes file and its GitHub Release. A pre-release
  `vX.Y.ZrcN` reaches TestPyPI only.
- **A release branch**: `release/vX.Y`, cut at `vX.Y.0`, carrying patch tags
  and back-ports.
- **A release run**: one dispatch of `release.yml`. It has a build and its
  gates, a recorded wheel and sha256, two environments with their rules and
  approvals, two trusted publishers, and the install check's legs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A workstation with no network gets a complete install from the
  package in one `--install` run: 30 of 31 artifacts placed, 1 left to pipx,
  and 28 receipt rows. The `package` job and every install-check leg show
  it.
- **SC-002**: Every `--version` from a stamped package names all five facts:
  the version, tag, commit, digest and repository. No `--version` from a
  checkout or a one-line install prints a version number, whatever is in the
  environment.
- **SC-003**: Every broken stamp is refused before any argument is acted on,
  `--help` included, and no broken build places a file.
- **SC-004**: Every commit pushed to `main` or to a `release/v*` branch gets a
  `package` run. In it the two builds are byte-identical, every packaged
  file equals the commit's blob, and no package test is skipped unnoticed.
- **SC-005**: No upload happens without Brett Heap's approval in its
  environment. No pre-release reaches PyPI, nothing uploads to pypi.org from
  `opensoft/openRepoTools`, and no rehearsal uses `1.1.0`.
- **SC-006**: A person who follows the advice any refusal prints never
  removes the only command that can run `--install`. No refusal prints an
  `rm` for pipx's link or for a venv-looking link.
- **SC-007**: Each of the 12 pipx fixture layouts is recognised: 3 pipx
  releases, each under 4 homes. Each negative layout is refused before
  anything is placed.
- **SC-008**: The macOS install-check leg completes the offline install
  under bash 3.2, with the same skip and count lines.
- **SC-009**: README never names an install route the index does not serve:
  it has no `pipx install openrepotools` line before PyPI serves 1.1.0.
- **SC-010**: The v1.0.0 notes file matches the published Release body, byte
  for byte.

## Assumptions

- **The baseline is done.** The annotated `v1.0.0` (tag object `6a826f8`) is
  on main `aaa7bc8`, and its GitHub Release was published at 20:57:57Z.
  Nothing is on PyPI.
- **v1.1.0 is published after the triad cutover (#186),** from
  `openRepoTools-code`. Before then, the workflow is rehearsed on a branch.
  On Brett Heap's word it is also rehearsed as `1.1.0rc1` on TestPyPI from
  `opensoft/openRepoTools`.
- **Brett Heap makes the acts outside the repository.** That means:
  - the `testpypi` and `pypi` environments, each with brettheap as required
    reviewer and the deployment limit `v*`, in both repositories in turn;
  - the `v*` tag rulesets;
  - the test.pypi.org publisher, for this repository and then for the code
    leg;
  - the one pypi.org pending publisher, for `openRepoTools-code` only.

  `release.yml` refuses every dispatch until the environments exist with
  their rules.
- **The `release/*` ruleset is Brett Heap's choice,** which #850 leaves to
  him: no force-push and no deletion, or a rule that requires a pull
  request. Both back-port forms are specified, so his choice changes only
  which one applies.
- **The text of `docs/release-notes/v1.1.0.md`** is drafted here, and settled
  before the tag.
- **The model is openRepoShape v1.1.0** (tag `b9c5099` on `190133d`),
  published on PyPI by its `release.yml` run 39071178232.
- **Lane openRepoTools-1's work comes after this feature lands.**
  - Lane 1 moves the openRepoShape pin straight to v1.1.0.
  - Lane 1 regenerates the adoption plan after this feature lands. The plan
    sends `pyproject.toml`, `src/` and `.github/` to code, `docs/` to spec
    and `LICENSE` to the root.
  - T006's patch `code-0001` is the code leg's first commit, right after
    `execute`. Lane openRepoTools-3 checks that the code leg's `LICENSE` is
    blob `261eeb9` before the first `package` run there.
- **The facts the design checked hold:**
  - hatchling 1.27.0 normalises wheel modes to 0644 or 0755;
  - its `license-files` glob does not fail on a missing file;
  - its version source takes the first line that matches its
    case-insensitive pattern;
  - pipx's default home on macOS holds a space.
- **The pipx layouts.** The fixtures mirror pipx 1.11.1 and 1.17.8, which the
  model's install check locks for Python below 3.10 and from 3.10 on, and
  1.18.3, the newest on PyPI on 2026-10-17.
- **Out of scope, the proposal's non-goals.** This feature makes none of
  these:
  - an upload to PyPI before the cutover, or from `opensoft/openRepoTools`
    ever;
  - a new runtime dependency;
  - a change to the one-line install, or to `wip init`'s template fetch;
  - an sdist, a native Windows command, or a second console script;
  - a check of the placed files against the receipt;
  - an edit to `upstream/openRepoShape`, to its pin, or to the triad change's
    files.
- **Windows** is reached through WSL2, as for every bash command here.
