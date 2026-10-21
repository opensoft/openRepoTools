# Contract: `tests.yml` and `release.yml`

Both files are governed: `.github/workflows/` is governed in every
repository. Every action is pinned by a full commit, and its release tag is
written as a comment, the way `tests.yml` writes every one today:

- `actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4`
- `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065  # v5`
- `pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33  # v1.14.2`
- the artifact actions, at the commits the model's `release.yml` pins at
  v1.1.0.

Neither file may hold a host path that `HOST_ABSOLUTE_PATH`
(`tests/test_repo_hygiene.py`) flags, such as one user's home directory on
Linux or macOS. Use `$RUNNER_TEMP` and `$HOME`.

## `tests.yml`

### Triggers

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, labeled]   # unchanged
  push:
    branches: [main, 'release/v*']                    # was [main]
  schedule:
    - cron: '17 4 * * *'                              # unchanged
  workflow_dispatch:                                  # unchanged
```

### The header comment

- Lines 29 to 36 are rewritten. They now say that `push` covers `main` and
  every `release/v*` branch, and that every trigger runs the four jobs.
- Every other comment stays as it is.

### Jobs

- `guard-launch-mode`, `tests` and `tests-no-submodule` stay byte for byte.
  These are the gate's job ids, and the code leg keeps them (FR-046).
- `package` is new, with exactly that id and no `name:`. Its steps, in
  order:

1. `actions/checkout` with `submodules: true` and `fetch-depth: 1`.
2. `actions/setup-python` with `python-version: '3.9'`.
3. **Git identity**, by environment and never by global config, as the
   `tests` job sets it.
4. **The test tools.**
   - First `tomli==2.4.1`, by hash. The step extracts the build lock's
     whole `tomli` entry, the requirement line and every `--hash` line
     under it, into a file under `$RUNNER_TEMP`, and installs it with
     `--require-hashes --only-binary=:all:`. The job holds no digest of its
     own.
   - Then `pytest==8.3.4`.
5. **Build twice, then compare.**
   - `SOURCE_DATE_EPOCH="$(git log -1 --format=%ct HEAD)"`.
   - `python3 -m pip wheel --no-deps -w "$RUNNER_TEMP/a" .`, then the same
     into `"$RUNNER_TEMP/b"`.
   - Each directory holds exactly one `.whl`, and the two are one file
     (`cmp`).
6. **The wheel check**: a `python3 - <<'PY'` heredoc that runs
   [wheel.md](wheel.md)'s checks 2 to 6 against `HEAD`, with the stamp equal
   to the committed file. It names every problem, then exits 1 if there was
   any. The suite extracts this heredoc and runs it on synthetic wheels
   (`tests/test_tests_workflow.py`).
7. **pipx from its hash lock**: `.github/release-pipx-requirements.txt`, with
   `--require-hashes --only-binary=:all:`. On 3.9 that gives pipx 1.11.1.
   `PIPX_HOME` and `PIPX_BIN_DIR` sit under `$RUNNER_TEMP`.
8. **Install the wheel with pipx.** pipx must place exactly one entry in
   `PIPX_BIN_DIR`, the link `openRepoTools`.
9. **The unstamped `--version`.** Its output equals
   [cli-output.md](cli-output.md)'s unstamped lines exactly.
10. **An offline `--install` beside pipx's link.** The run has:
    - `HOME` a fresh directory under `$RUNNER_TEMP`;
    - `OPENREPOTOOLS_BIN_DIR="$PIPX_BIN_DIR"`;
    - `OPENREPOTOOLS_REPO=offline.invalid/sentinel`;
    - a `PATH` whose first directory holds a `gh` and a `curl` that each
      exit 1.

    The skip line and the count line must be exact, there must be 28 rows in
    the receipt, and the link must be unchanged.
11. **The package's tests, none skipped.**
    - `OPENREPOTOOLS_TEST_WHEEL` is the built wheel.
    - Run `python3 -m pytest tests/test_package.py tests/test_package_stamp.py tests/test_install_pipx.py -q -rs --junitxml="$RUNNER_TEMP/package-tests.xml"`.
    - Then a `python3` step reads the report and fails unless there is at
      least one test, and zero skipped, failures and errors.

## `release.yml` (new)

### The file's shape

```yaml
on:
  workflow_dispatch:
    inputs:
      version: {description: …, required: true, type: string}
permissions: {}
concurrency: {group: release, cancel-in-progress: false}
defaults: {run: {shell: bash}}
env:
  VERSION: ${{ inputs.version }}     # scripts read it from the environment; no expression is pasted into a script
  PYTHONUTF8: '1'
jobs: {build, testpypi, install, pypi}
```

### The header (RELEASING), in this order

1. What the workflow does, and that it is adapted from openRepoShape v1.1.0
   (`190133d`), with design.md Decision 10's differences named.
2. **The procedure for a release.**
   - The release owner, lane openRepoTools-3, acts on Brett Heap's word: it
     tags, dispatches and creates the GitHub Release. Brett approves each
     deployment.
   - The tag message's form (FR-036).
   - A tag waits for its commit's `tests.yml` runs: all of them finished,
     and the newest green.
   - Dispatch on the tag, with `version` set to `X.Y.Z`.
   - Approve `testpypi`, then `pypi`.
   - After PyPI serves the version, run
     `gh release create v<version> --repo <repository> --verify-tag --notes-file <spec>/docs/release-notes/v<version>.md`.
   - Then, for `vX.Y.0`, cut `release/vX.Y` at the tag.
3. **The branch and tag policy**, from #850:
   - the trunk;
   - annotated tags only, never moved and never reused;
   - release branches cut at `vX.Y.0`;
   - back-ports by fast-forward or merge while `main` holds only that patch
     line, otherwise by a PR of `git cherry-pick -x`;
   - one HOLD at a time, the landing lane back-ports, and the LANDED line
     names both commits;
   - patch tags wait for the commit's runs, the newer run deciding;
   - one upload per version, with a bad one fixed by the next patch.
4. **The two rehearsals.**
   - A branch dispatch builds, checks and installs, and uploads nothing.
   - A `X.Y.ZrcN` dispatched on its annotated tag reaches TestPyPI and the
     install check, and the `pypi` job is skipped.
   - A branch rehearsal builds with the version of the tag it rehearses, as
     the model rehearsed v1.1.0 from its branch `l3-rehearsal-v1.1.0`.
     Before v1.1.0 that is the next pre-release, so
     `gh workflow run release.yml --ref <branch> -f version=1.1.0rc1` comes
     first.
   - The build's CI gate holds in a rehearsal too, and it counts only push
     and dispatch runs. A feature branch's commit has only `pull_request`
     runs, so dispatch `tests.yml` on that branch first, and wait for it to
     finish green.
   - No rehearsal uses `1.1.0`.
5. **Where releases come from.**
   - From v1.1.0 on, tags are made in `openRepoTools-code`.
   - `v1.0.0` and every `rc` tag stay in `opensoft/openRepoTools`.
   - The repository guard (FR-048) applies:
     - `opensoft/openRepoTools` sends a pre-release to TestPyPI and nothing
       to PyPI;
     - `opensoft/openRepoTools-code` sends a pre-release to TestPyPI only,
       and a final to TestPyPI and then to PyPI;
     - every other repository uploads nothing.

     `opensoft/openRepoTools` has no pypi.org publisher, which is the
     second line of defence.
   - The `testpypi` and `pypi` environments, the `v*` tag ruleset and the
     trusted publishers are Brett Heap's to create. The header says what the
     environments and the ruleset must be:
     - each environment has brettheap as the required reviewer, self-review
       allowed, administrators not bypassing, and a deployment limit of
       exactly one rule, of type tag, `v*`;
     - the ruleset is on the tags `v*`, and only the admin role creates,
       moves or deletes one.

     The workflow reads that each environment names a required reviewer (any,
     not brettheap in particular) and the deployment limit, in the build's
     step 5 and again in each upload job, and nothing else of these.
     Self-review, administrator bypass and the ruleset are not checked, and
     the header says so.
6. **What the workflow never reads**: the release notes, and anything
   outside the code leg (FR-046).

### `build` (`contents: read`, `actions: read`)

The checkout:

- `submodules: true`, because `repo_shape.py` exists here only in the
  submodule;
- `persist-credentials: false`;
- full history, for the main and release-branch check.

The steps are the model's, in its order. Each is a refusal on failure:

1. **The version, and the repository guard (FR-048).**
   - The version is `X.Y.Z`, not `0.0.0`, or `X.Y.ZrcN`.
   - The guard is a `bash` `run:` block that the suite runs. It reads
     `$GITHUB_REPOSITORY`, `$GITHUB_REF` and `$VERSION`, and decides by this
     table:

     | `$GITHUB_REPOSITORY` | Ref | Version | Build | `to-testpypi` | `to-pypi` |
     | --- | --- | --- | --- | --- | --- |
     | `opensoft/openRepoTools-code` | a tag | `X.Y.Z` | passes | `true` | `true` |
     | `opensoft/openRepoTools-code` | a tag | `X.Y.ZrcN` | passes | `true` | `false` |
     | `opensoft/openRepoTools` | a tag | `X.Y.ZrcN` | passes | `true` | `false` |
     | `opensoft/openRepoTools` | a tag | `X.Y.Z` | refuses | none | none |
     | any other | a tag | any | refuses | none | none |
     | any | a branch | any | passes, as the rehearsal | `false` | `false` |

   - The two repository names are compared exactly, as GitHub spells them
     in `$GITHUB_REPOSITORY`. Any other spelling counts as "any other",
     so the guard fails closed.
   - The build job asks for no approval, so a refused run asks for none.
     The model's workflow has no such guard, so this one is new here.
2. The ref:
   - on a tag, it is the annotated tag `v$VERSION`, whose object names
     `$GITHUB_SHA`, read from the forge and from git;
   - on a branch, it is a rehearsal, and the version must still parse;
   - any other ref is refused.
3. On a tag, `$GITHUB_SHA` is on `main` or on `release/v<X.Y>`. On a
   branch, the rehearsal has no release branch to be on, and the step says
   so and passes. This is the model's form (`release.yml:200-249` at
   v1.1.0), and every later step runs in a rehearsal too.
4. The checkout is `$GITHUB_SHA`, and it is clean.
5. Both environments:
   - each names at least one required reviewer;
   - each has `deployment_branch_policy.custom_branch_policies` true;
   - each has exactly one policy, of type `tag`, with the name `v*`.
6. The `tests.yml` runs on `$GITHUB_SHA`, by `push` or `workflow_dispatch`:
   - the jobs `guard-launch-mode`, `tests`, `tests-no-submodule` and
     `package` each ran;
   - none of those runs is in progress;
   - the newest to finish succeeded.
7. **The digest:**
   - `tree_digest` on the checkout equals `tree_digest_from_gh` on the
     forge, both run from `upstream/openRepoShape/scripts/repo_shape.py`;
   - `repo_shape.TREE_DIGEST_DEFINITION` equals the literal
     `sorted-ls-tree-r-v1`, and equals the pin's `digest_definition`.
8. The tools come from `.github/release-build-requirements.txt`, in a venv,
   with `--require-hashes --only-binary :all:`.
9. Extract the commit twice: `git archive` into two different directories.
10. Write the stamp into both extractions ([stamp.md](stamp.md)'s writer),
    with `REPOSITORY="$GITHUB_REPOSITORY"`.
11. Build each one with
    `python -m build --wheel --no-isolation`, at
    `SOURCE_DATE_EPOCH` the commit's time.
12. The two wheels are one file.
13. [wheel.md](wheel.md)'s checks 2 to 6, with the stamp as the release's.
    This is a heredoc, which `tests/test_release_workflow.py` extracts and
    runs on synthetic wheels.
14. Record these as job outputs: the wheel's name, its sha256, the digest,
    and step 1's `to-testpypi` and `to-pypi`. Keep the wheel as an
    artifact.

### `testpypi` (`environment: testpypi`; permissions exactly `id-token: write`, `actions: read`, `contents: read`)

These are the model's grants (`release.yml:691-694` at v1.1.0):
`id-token` for trusted publishing, `actions` for the environment's rules and
this run's approvals, and `contents` for the tag, read again.

- It runs only when `github.ref` is a `refs/tags/v*` tag, `build` succeeded,
  and `needs.build.outputs.to-testpypi == 'true'`.
- Its first step runs the repository guard again, on its own. It refuses in
  `opensoft/openRepoTools` unless the version is a pre-release, passes in
  `opensoft/openRepoTools-code`, and refuses in every other repository.
- Download the wheel, and check its sha256 against `build`'s output.
- Read again the environment's rules, this run's approval of `testpypi`,
  and the tag.
- TestPyPI's JSON for the version must list no file but the verified
  wheel, at the digest `build` recorded, or the job refuses:
  - a 404, a version with no file yet, passes;
  - the verified wheel already there at that digest, and not yanked, passes,
    and the upload (`skip-existing`) adds nothing new. This is a re-run of
    the job after an upload that went through;
  - a file of any other name, or the wheel's name at another digest,
    refuses the job before the upload, and so does the verified wheel when
    it is yanked.
- Upload with `pypa/gh-action-pypi-publish@dc37677…` and
  `repository-url: https://test.pypi.org/legacy/`.
- Then TestPyPI must serve exactly `{wheel: sha256}`. Read it up to 20
  times, as the model does.

### `install` (read only)

- It needs `build` and `testpypi`. It runs on a tag after `testpypi`
  succeeded, and on a branch when `testpypi` was skipped. This is the
  model's condition.
- The matrix is `ubuntu-latest` on `3.x`, `macos-latest` on `3.x`, and
  `ubuntu-latest` on `3.9`. There is no Windows leg.
- `PIP_INDEX_URL` is PyPI's, as the model has it.

The steps:

1. On a tag, fetch the wheel from TestPyPI by its recorded digest. On a
   branch, take the build's artifact. In both cases, check the sha256.
2. pipx from `.github/release-pipx-requirements.txt`, by hash.
3. `pipx install` the wheel. pipx must place exactly one command,
   `openRepoTools`.
4. `--version`:
   - on a tag, its five lines must name `$GITHUB_REPOSITORY`, `$VERSION`,
     `v$VERSION`, `$GITHUB_SHA` and the digest;
   - on a branch, the build's stamp values.
5. An offline `--install` into a fresh temporary `HOME`, set up as in the
   `package` job's step 10. The skip line and the count line must be exact.
6. On macOS only, run step 5 again with `PATH="/bin:$PATH"`, and print
   `BASH_VERSION`, which must begin with `3.2`.
7. On 3.9 only, compile the installed package's own
   `payload/lanes-index` and `payload/lane-worktrees` with `python3 -c`
   `compile(...)`. The shipped bytes are what must compile on 3.9.

### `pypi` (`environment: pypi`; permissions exactly `id-token: write`, `actions: read`, `contents: read`)

These are the model's grants (`release.yml:1133-1136` at v1.1.0).

- It needs `build`, `testpypi` and `install`.
- Its job-level `if:` requires a `refs/tags/v*` tag and
  `needs.build.outputs.to-pypi == 'true'`, which holds only for a final
  `X.Y.Z` in `opensoft/openRepoTools-code`. An expression cannot test a
  pattern, so the build's record decides. In an rc rehearsal the job is
  skipped, and never asks for the `pypi` approval.
- Its first step refuses unless `$GITHUB_REPOSITORY` is
  `opensoft/openRepoTools-code` and the version is a final `X.Y.Z`. So in
  `opensoft/openRepoTools` it refuses outright, in case the condition is
  ever loosened.
- Then come the same download, sha256 check, re-reads and empty-index check
  as `testpypi`, against PyPI.
- The upload uses the same pinned action, with the default index.
- Then PyPI must serve exactly `{wheel: sha256}`.

### Held by `tests/test_release_workflow.py` (offline)

- A dispatch with `version` is the only trigger, and `permissions: {}` is
  set at the top.
- Only `testpypi` and `pypi` hold `id-token: write`, each in its own
  environment and on a `v*` tag alone. Each holds exactly `id-token: write`,
  `actions: read` and `contents: read`. `build` holds exactly
  `contents: read` and `actions: read`, and `install` holds exactly
  `contents: read`.
- The ref step passes a branch as a rehearsal and refuses any other non-tag
  ref, and the branch-membership step passes a rehearsal.
- The wheel-check heredoc is run on four synthetic wheels made from HEAD's
  blobs:
  - the wheel as built, which passes;
  - one with no `licenses/LICENSE`, which fails, naming `LICENSE`;
  - one with a payload file's byte changed, which fails, naming that file;
  - one with a payload file's mode changed, which fails, naming that file.
- Every `uses:` is pinned by 40 hex digits, and the publish action is
  `dc37677…`.
- Every `pip install` is from a hash lock, with `--require-hashes`.
- Every entry in both locks is one version, named by its sha256.
- The build lock's hatchling is `pyproject.toml`'s pin.
- The pipx lock gives 1.11.1 below Python 3.10 and 1.17.8 from 3.10.
- The build gate names exactly the four job ids.
- The digest step compares `TREE_DIGEST_DEFINITION` with the literal and
  with the pin.
- The literal equals the label in `openRepoTools`' `--version` arm.
- The stamp heredoc round-trips through `stamp_read` ([stamp.md](stamp.md)).
- The repository guard (`test_release_guard_*`). The build's guard block is
  run under each row of step 1's table, with `GITHUB_REPOSITORY`,
  `GITHUB_REF`, `VERSION` and `GITHUB_OUTPUT` set. It must pass or refuse,
  and record `to-testpypi` and `to-pypi`, exactly as the row says.
- Each upload job's first-step guard is run in the same way. `testpypi`
  refuses a final in `opensoft/openRepoTools` and any version elsewhere.
  `pypi` refuses everything but a final in `opensoft/openRepoTools-code`.
- `testpypi`'s condition reads `to-testpypi`, and `pypi`'s reads `to-pypi`.
  So in an rc rehearsal `pypi` is skipped.
- The install matrix is exactly the three legs. The macOS leg reruns under
  `/bin/bash`, and the 3.9 leg compiles the two Python commands.
- No step reads `docs/`, `openspec/`, `specs/`, `README.md`, `AGENTS.md` or
  `CLAUDE.md`.
- The header has the RELEASING sections above.

### Held by `tests/test_tests_workflow.py` (offline)

- `push.branches` is exactly `[main, 'release/v*']`, and the other triggers
  are as above.
- The four job ids are present.
- The three existing jobs keep today's `runs-on`, checkout options, Python
  version and `run:` commands. These are asserted from the file's text, not
  from history, because CI checks out one commit at `fetch-depth: 1`. The
  pull request's diff review confirms the rest of "unchanged".
- The `package` job runs on `ubuntu-latest` with Python `3.9` and
  `submodules: true`, and carries steps 4 to 11 in order.
- Its `tomli` comes from the build lock's own entry, and the job holds no
  `--hash` of its own.
- Its wheel-check heredoc (step 6) is run on the same four synthetic wheels
  as the release build's, with the same four outcomes.
- The header comment names both push branches and four jobs.
