# Spec Delta

## Purpose

Gives openRepoTools a release identity: annotated version tags, release
branches that carry patch lines, the CI runs a tag waits for, and release
notes that never name a version the index lacks.

## ADDED Requirements

### Requirement: A release is an annotated version tag

A release SHALL be an annotated tag `vX.Y.Z` on a commit that is on `main`
or on `release/vX.Y`. A release SHALL NOT be a branch, and SHALL NOT be a
version number committed to any file. The tag message SHALL have the form
`v1.0.0` already uses: the line `openRepoTools vX.Y.Z`, a paragraph, the
line `Tagged on Brett Heap's word (<time>, "<words>")` with `<time>` the
exact UTC second, and the line `Lane: <lane>`. A tag SHALL NOT be moved,
deleted or reused once pushed. A version that was uploaded badly SHALL be
fixed by the next patch version.

#### Scenario: The baseline tag stays as it is

- **WHEN** a later release is tagged
- **THEN** `v1.0.0` still names tag object `6a826f8` on commit `aaa7bc8`, and
  its message still says `2026-10-17T20:5xZ`

#### Scenario: A bad upload is fixed forward

- **WHEN** a published version is found to be broken
- **THEN** the fix is released as the next patch version, and the broken
  version's tag and upload are left in place

#### Scenario: A lightweight tag is not a release

- **WHEN** the release workflow is dispatched on a lightweight tag, or on an
  annotated tag whose object names a different commit
- **THEN** the build refuses, and nothing is built or uploaded

### Requirement: Release branches carry patch lines

`release/vX.Y` SHALL be cut at the `vX.Y.0` tag, right after that tag is
made. Each patch `vX.Y.Z` with Z above 0 SHALL be tagged on `release/vX.Y`.
Every PR SHALL land on `main`, the trunk.

#### Scenario: The first release branch

- **WHEN** v1.1.0 has been tagged and released from `openRepoTools-code`'s
  `main`
- **THEN** `release/v1.1` is cut at `v1.1.0`, and v1.1.1, when it comes, is
  tagged on `release/v1.1`

### Requirement: Back-ports land on main first

A fix SHALL land on `main` first, through its own review and CI, before it
reaches a release branch. While `main` holds only that patch line's work,
the back-port SHALL be a fast-forward of `release/vX.Y`, or a merge of
`main`. Otherwise it SHALL be a PR to `release/vX.Y` of
`git cherry-pick -x <squash commit>`. At most one HOLD SHALL be open at a
time on `release/vX.Y`. The lane that landed the PR SHALL make the back-port,
unless the release owner fast-forwards. The LANDED line SHALL name both
commits.

#### Scenario: main holds only the patch

- **WHEN** a fix lands on `main` and `main` has nothing since `release/v1.1`
  except that patch line's work
- **THEN** `release/v1.1` is fast-forwarded to it, and the LANDED line names
  the commit on both branches

#### Scenario: main has moved on

- **WHEN** a fix lands on `main` after work for the next minor version
- **THEN** it reaches `release/v1.1` only by a PR of
  `git cherry-pick -x <squash commit>`, which runs its own CI

### Requirement: A patch tag waits for its commit's CI

A patch SHALL be tagged on `release/vX.Y` only once that commit's
`tests.yml` runs have all finished, and the newest of them has succeeded.
When a commit reached the branch by fast-forward, it has `main`'s push run
and then the branch's own, and the newer run SHALL decide.

#### Scenario: A run is still in progress

- **WHEN** one of the commit's `tests.yml` runs has not finished
- **THEN** the patch is not tagged yet

#### Scenario: The newer run is red

- **WHEN** `main`'s push run for the commit succeeded, and the branch's newer
  push run for the same commit failed
- **THEN** the patch is not tagged

### Requirement: Release branches get the push runs the gate needs

`tests.yml` SHALL run on `push` to `main` and to every `release/v*` branch,
as well as on its existing triggers. Every run SHALL include the jobs
`guard-launch-mode`, `tests`, `tests-no-submodule` and `package`.

#### Scenario: A push to a release branch

- **WHEN** a commit is pushed to `release/v1.1`
- **THEN** a `tests.yml` push run runs all four jobs on that commit

### Requirement: Release notes and GitHub Releases

Each release SHALL have its notes in `docs/release-notes/vX.Y.Z.md`.
`docs/release-notes/v1.0.0.md` SHALL hold the body of the published v1.0.0
Release, byte for byte. A draft's placeholders SHALL be filled in or cut
before its tag is made. A release's GitHub Release SHALL be created from its
notes file, and, for a version published on PyPI, only after PyPI serves that
version. No step of the release workflow SHALL read the notes.

#### Scenario: The baseline notes

- **WHEN** `docs/release-notes/v1.0.0.md` is compared with the body
  `gh release view v1.0.0` returns
- **THEN** the two are identical

#### Scenario: The Release waits for the index

- **WHEN** the v1.1.0 release run has uploaded to TestPyPI, but PyPI does not
  serve 1.1.0 yet
- **THEN** no GitHub Release for v1.1.0 exists yet

### Requirement: Brett Heap decides every release act

Every tag, every release-branch cut and every upload SHALL wait for Brett
Heap's word. Each deployment to the `testpypi` and `pypi` environments SHALL
wait for his approval. Lane openRepoTools-3, the release owner, SHALL carry
out these acts on his word, and no other lane SHALL make them.

#### Scenario: An approval is missing

- **WHEN** a release run reaches an upload job and no approval for that
  environment has been given
- **THEN** the job waits, and nothing is uploaded

### Requirement: Tags in the triad

Release tags from v1.1.0 on SHALL be made in `openRepoTools-code`, where the
release is built. `v1.0.0`, and every `rc` rehearsal tag, SHALL stay in
`opensoft/openRepoTools`. Tags SHALL NOT be carried from one repository to
another at the cutover.

#### Scenario: The cutover

- **WHEN** `opensoft/openRepoTools` becomes the assembly
- **THEN** `v1.0.0` and `v1.1.0rc1` remain its tags, and neither is carried
  to `openRepoTools-code` or to the spec leg
