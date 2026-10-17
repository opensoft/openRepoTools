# Research: 006-release-pypi

Phase 0 of `/speckit.plan`. The governing change leaves no technical unknown
open: design.md answers N1 to N5, and the lead's rulings of 2026-10-17 settle
its remaining points. What is left are the choices that design.md delegates
to the plan ("as `/speckit.tasks` splits it", "one entry module", "a test
writes a stamp with the build's writer"), and two slips in design.md that
this phase found. Each entry is one decision, its rationale and the
alternatives considered.

Every fact below was read on 2026-10-17. The bash file was read at this
branch's head. openRepoShape v1.1.0 (`190133d`) and the current pin `7f84ca4`
were read read-only.

## R1. The entry module is `openrepotools.cli:main`

- **Decision**:
  - The one console script is `openRepoTools = "openrepotools.cli:main"`.
  - `src/openrepotools/__init__.py` holds a docstring and nothing else.
  - `src/openrepotools/cli.py` holds `main()`, which does what design.md
    Decision 3 says and nothing more.
- **Rationale**:
  - It mirrors the model's `openreposhape.cli`.
  - pip's console-script template then writes
    `from openrepotools.cli import main`. That is the line design.md
    Decision 8's pattern
    `^from openrepotools(\.[A-Za-z_][A-Za-z0-9_]*)* import ` matches.
  - An empty `__init__` keeps the import of the entry point free of side
    effects.
- **Alternatives considered**:
  - `openrepotools.__main__`: it would add `python -m openrepotools`, a
    second entry the proposal does not ask for.
  - Code in `__init__.py`: it would run on every import, including hatch's.

## R2. The wheel is declarative hatchling with a written-out force-include map

- **Decision**:
  - `[tool.hatch.build.targets.wheel] packages = ["src/openrepotools"]`.
  - `[tool.hatch.version] path = "src/openrepotools/_release.py"`, which is
    hatch's regex version source.
  - `[tool.hatch.build.targets.wheel.force-include]` lists the 24 entries of
    [contracts/wheel.md](contracts/wheel.md), each written as
    `"<P>" = "openrepotools/payload/<P>"`.
  - There is no build hook (design.md Decision 2).
- **Rationale**:
  - It is the model's form.
  - The map's keys are compared with `payload_names` by a test (FR-007), so
    the bash list stays the only list.
- **Alternatives considered**: a build hook that generates the map, rejected
  by design.md Decision 2.

## R3. The bash side: named functions, all in `openRepoTools`

- **Decision**: the installer gains these functions. The names are fixed
  here so that tasks touching one file in sequence agree on them.
  - `link_resolve <path>`: design.md Decision 6's loop. It uses plain
    `readlink`, at most 40 hops, joins a relative value to the link's own
    directory, and canonicalises the final directory with `cd -P` and
    `pwd -P`. It prints the canonical path, or returns 1 for a chain or a
    cycle.
  - `package_payload_dir`: design.md Decision 4. It prints `$SELF`'s resolved
    directory when that directory is named `payload`, its parent is named
    `openrepotools`, and that parent holds a regular `_release.py`.
    Otherwise it returns 1.
  - `stamp_read <file>`: design.md Decision 5's reader in `pin_parse`'s
    style. It sets `STAMP_VERSION`, `STAMP_TAG`, `STAMP_COMMIT`,
    `STAMP_DIGEST`, `STAMP_REPOSITORY` and `STAMP_STATE`
    (`unstamped` or `stamped`) and returns 0, or sets `STAMP_WHY` and
    returns 1.
  - `package_init`: called once, after every function is defined and before
    the argument loop.
    - In package mode it sets `PACKAGE_DIR` and runs `stamp_read`.
    - On a broken stamp it calls `die` with Decision 4's line (exit 2).
    - Outside package mode it sets nothing.
  - `pipx_link_match <target>`: design.md Decision 6's match. It sets
    `PIPX_LINK`, `PIPX_VENV` and `PIPX_PAYLOAD`.
  - `venv_shaped_link <target>`: the venv-looking link of Decision 6, for the
    refusal.
  - `pip_script_is <file>`: design.md Decision 8's recognition rule.
  - `path_report`: design.md Decision 8's report, run last in a package-mode
    `--install`.
- **Rationale**:
  - `plan_install_targets`, `install_commands` and the `--version` arm read
    these values, and each refusal stays in the planning phase.
  - `tests/test_install_by_rename.py` already cuts a function's text out of
    the script and runs it alone (`installer_function`). The new reader
    tests can do the same with `stamp_read` and `link_resolve`.
- **Alternatives considered**: a helper file beside the bash file. It would
  be an eighteenth installable, and AGENTS.md's one-file-per-command argument
  (`openRepoTools:244-257`) refuses that.

## R4. The `--version` arm reads the stamp `package_init` already read

- **Decision**:
  - `--version` prints [contracts/cli-output.md](contracts/cli-output.md)'s
    stamped or unstamped form when `PACKAGE_DIR` is set.
  - Otherwise it prints today's line.
  - It never reads an environment variable for the stamp. A test sets
    `OPENREPOTOOLS_PACKAGE_VERSION`, `OPENREPOTOOLS_PACKAGE_TAG`,
    `OPENREPOTOOLS_PACKAGE_COMMIT`, `OPENREPOTOOLS_PACKAGE_DIGEST` and
    `OPENREPOTOOLS_PACKAGE_REPOSITORY` on a checkout run, and requires today's
    line.
- **Rationale**: bash is the one reader, as D2 and design.md Decision 3
  require. The variable names in that test are the ones a future change
  might reach for, so the test proves that no channel exists.
- **Alternatives considered**: none. The spec fixes this.

## R5. The count line's `<source>` and `<version>`

- **Decision**:
  - "pipx's own environment" is package mode with `PACKAGE_DIR` under
    `$PIPX_VENV/lib/`, compared after both are canonicalised.
  - Otherwise `<source>` is `$PAYLOAD_REPO @ $PAYLOAD_REV` when
    `SOURCE_LAYOUT` is `adopted`, and `$REPO @ $REF` in every other case.
    That is `payload_where`'s pair (`openRepoTools:797-803`), with `@` in
    place of `at`.
  - `<version>` is `stamp_read`'s `VERSION` for
    `$(dirname "$PIPX_PAYLOAD")/_release.py`, or the literal
    `an unreadable stamp` when it returns 1.
- **Rationale**: this is design.md Decision 7 as written. The lead confirmed
  the exact line on 2026-10-17.
- **Edge left as written**: a package-mode run whose payload is not under
  `$PIPX_VENV`, such as another package install beside pipx's link, also
  takes the `$REPO @ $REF` form. The design does not distinguish it. It is
  reported to the lead as a LOW finding and not specified further.

## R6. pip's console script: the rule as design.md Decision 8 writes it

- **Decision**: `pip_script_is` reads the first line with `IFS= read -r`. It
  requires `#!`, and takes the first word after `#!`. Its last `/` segment
  must begin with `python`. Then one of the first 20 lines must match the
  import pattern. The check runs inside `plan_install_targets`, for a regular
  file (not a link) at `<dir>/openRepoTools`, in every mode.
- **Rationale**: design.md Decision 8, under N5.
- **Known gap, recorded and not widened**:
  - distlib, which pip uses, writes a `#!/bin/sh` launcher when the
    interpreter's path holds a space or is too long for a shebang. The
    following `'''exec' "<python>" "$0" "$@"` line carries the
    interpreter.
  - Such a script fails the first-line rule. It is then an ordinary regular
    file, and today's behaviour applies: it is replaced.
  - The plan does not extend the rule on its own authority. The gap is
    reported to the lead, LOW.

## R7. The PATH report's `<prefix>`: five levels above `payload/`

- **Decision**: `<prefix>` is the parent of the `lib/` above the payload.
  For `<prefix>/lib/pythonX.Y/site-packages/openrepotools/payload` that is
  five directories up from `payload/`, and the expected command is
  `<prefix>/bin/openRepoTools`.
- **Rationale**: the layout design.md Decision 8 writes out has five
  components between `<prefix>` and `payload`: `lib`, `pythonX.Y`,
  `site-packages`, `openrepotools` and `payload`. "Four levels above the
  payload" would name `lib/`. This is an arithmetic slip, and design.md is
  corrected in the same commit as this file.
- **Alternatives considered**: a `..`-count computed at run time from the
  path's shape. It is the same answer. The implementation checks that the
  component names match (`lib`, `python*`, `site-packages`) and skips the
  report, saying so, when they do not.

## R8. Which tests are "the package's tests", and how they get a wheel

- **Decision**: three new modules are the package's tests:
  - `tests/test_package.py`: the metadata, the map against `payload_names`,
    the entry module, the standard-library rule's companion checks, and the
    built wheel;
  - `tests/test_package_stamp.py`: the stamp reader, package mode,
    `--version` and the broken-stamp refusal;
  - `tests/test_install_pipx.py`: the pipx rule and its fixtures, the skip
    and count lines, the receipt rows, coexistence, pip, the PATH report,
    upgrade and uninstall.

  The tests that need a built wheel read its path from
  `OPENREPOTOOLS_TEST_WHEEL`, and skip naming it when it is unset. The
  `package` job builds the wheel, sets the variable, runs the three modules
  with `--junitxml`, and fails unless at least one test ran and none
  skipped.
- **Rationale**:
  - The suite reaches no network (AGENTS.md), and building a wheel in a test
    would fetch hatchling into pip's isolated build environment.
  - The variable is an input, not a switch that turns a skip into a failure,
    which design.md Decision 9 rejects. The JUnit count stays the enforcer.
  - In the `tests` job the wheel tests skip, and every other package test
    runs there.
- **Alternatives considered**:
  - A test that builds the wheel: rejected, it needs the network.
  - Only a job step that compares the wheel with `payload_names`: rejected,
    because design.md Decision 2 asks for a test.

## R9. The workflow tests read YAML with the pinned standard's `load_yaml`

- **Decision**:
  - `tests/test_release_workflow.py` holds `release.yml` and the two hash
    locks, and runs the workflow's stamp writer.
  - `tests/test_tests_workflow.py` holds `tests.yml`: the triggers, the four
    job ids and the `package` job's steps.
  - Both load YAML with `repo_shape.load_yaml` from
    `upstream/openRepoShape/scripts`. It exists at the current pin `7f84ca4`
    (`scripts/repo_shape.py:624`) and at v1.1.0 (`:1050`).
  - Both skip without the submodule, exactly as the command tests do.
- **Rationale**:
  - The model's `tests/test_release_workflow.py` reads its workflow that
    way.
  - The suite stays standard-library only, with no PyYAML.
  - A construct outside the standard's subset then fails in the suite first.
- **Fallback, inside the same task**: if `load_yaml` refuses a construct
  `tests.yml` already uses, the test reads that file's lines as text for the
  assertions it needs. It never adds a dependency.
- **Alternatives considered**: PyYAML, rejected because the suite imports
  only the standard library.

## R10. The stamp writer is a heredoc in `release.yml`, run by the suite

- **Decision**:
  - The build's "write the stamp" step is a `python3 -I - <a> <b> <<'PY'`
    heredoc, as the model's is (`release.yml:493-523` at v1.1.0).
  - It is adapted to five fields, with `REPOSITORY` taken from
    `$GITHUB_REPOSITORY`.
  - It replaces each of the five committed lines exactly once, refuses a
    file already stamped, and refuses a value no release carries.
  - `tests/test_release_workflow.py` extracts that heredoc the way the
    model's `heredoc()` does, and runs it on a copy of the committed
    `_release.py`. It reads the result back through `stamp_read`, in a fake
    package layout, by `--version`.
- **Rationale**: FR-013 needs one writer that the reader is tested against,
  and design.md Decision 5 asks that the test use "the build's writer".
- **Alternatives considered**: a writer script under `.github/`. It would be
  a new file the proposal's Impact list does not name, and a second place
  for release logic.

## R11. The hash locks are the model's, re-headed

- **Decision**:
  - `.github/release-build-requirements.txt` and
    `.github/release-pipx-requirements.txt` take the model's files at
    v1.1.0. The lines below each header stay byte for byte.
  - Each header is rewritten for this repository and #228. It keeps the
    resolving command, `uv pip compile`, uv 0.12.18, `--exclude-newer
    2026-10-01T00:00:00Z`.
  - The build lock pins `hatchling==1.27.0`, which is `pyproject.toml`'s
    pin.
  - The pipx lock gives pipx 1.11.1 below Python 3.10 and 1.17.8 from 3.10.
- **Rationale**:
  - These are the tools the model's release used, from PyPI as it stood
    then.
  - A copy is reproducible from its own header, and it adds no resolution
    nobody reviewed.
- **Alternatives considered**: a fresh resolution with a later date. It is
  allowed later as its own act, as the header says.

## R12. The `package` job's test tools

- **Decision**:
  - The job installs `tomli==2.4.1` first. It is installed by hash, with
    `--require-hashes --only-binary=:all:`, from a one-line requirements
    file the step writes. The hash is the build lock's own `tomli` entry.
  - Then it installs `pytest==8.3.4` as the other jobs do. pip then keeps
    the hashed `tomli`, which satisfies pytest's requirement on Python
    below 3.11.
  - A test holds the job's `tomli` hash equal to the build lock's.
- **Rationale**:
  - design.md Decision 9 asks for tomli at a pinned version, by hash,
    beside pytest.
  - The proposal's file list adds no third lock.
- **Alternatives considered**: a third lock file, rejected as a file nothing
  else needs.

## R13. The `package` job's checks are inline, and so are the release build's

- **Decision**:
  - Each workflow carries its own wheel check: the blob and mode check, the
    module check, the stamp check and the `.dist-info` set.
  - The `package` job builds from the checkout, with `pip wheel --no-deps`
    twice and `SOURCE_DATE_EPOCH` at the commit's time. The release build
    builds from two `git archive` extractions.
  - A test holds the two workflows' `.dist-info` sets to the same five names.
- **Rationale**:
  - These are the model's two forms.
  - A shared script would be read across jobs, and the release build's
    checks must not depend on a file the `package` job also runs.
- **Alternatives considered**: one script under `.github/`, rejected as R10's
  is.

## R14. The `package` job's install run

- **Decision**:
  - pipx comes from `.github/release-pipx-requirements.txt` by hash, which
    gives 1.11.1 on 3.9.
  - `PIPX_HOME` and `PIPX_BIN_DIR` sit under `$RUNNER_TEMP`, and
    `OPENREPOTOOLS_BIN_DIR` equals `PIPX_BIN_DIR`, so pipx's link is the
    installer's `<dir>/openRepoTools`.
  - `HOME` is a fresh directory under `$RUNNER_TEMP`.
  - The run has these settings:
    - `OPENREPOTOOLS_REPO=offline.invalid/sentinel`;
    - a `PATH` holding a `gh` and a `curl` that both exit 1;
    - the runner's `jq`.
  - The step compares the unstamped `--version`, the skip line and the count
    line with [contracts/cli-output.md](contracts/cli-output.md) exactly.
- **Rationale**: design.md Decision 9 and the proposal's offline install. The
  sentinel only needs to fail if anything fetches. `.invalid` is the
  reserved name that never resolves.
- **Alternatives considered**: none.

## R15. The v1.0.0 notes are fetched once, and checked by the task

- **Decision**:
  - `docs/release-notes/v1.0.0.md` is the output of
    `gh release view v1.0.0 --repo opensoft/openRepoTools --json body --jq .body`,
    unchanged.
  - The task's verify command runs the same command and compares the two
    with `cmp`.
  - The suite does not repeat the check, because it reaches no network.
- **Rationale**: the spec's "byte for byte as `gh release view v1.0.0`
  returns it". One command both writes the file and checks it, so the two
  cannot disagree about a trailing newline.
- **Alternatives considered**: a suite test with a recorded body. That would
  compare the file with itself.

## R16. Line caps move by dated entries

- **Decision**:
  - README.md is 485 lines against a cap of 486
    (`tests/test_repo_hygiene.py:2253`), and AGENTS.md is 314 against 316
    (`:1748`).
  - Each file's change is cut to the fewest lines that carry its facts. Where
    a cap still moves, the move goes in that test's docstring as a dated
    entry, in that test's own form. It names the lines and why, and states
    the assembly root's cap beside it.
- **Rationale**: those two tests require exactly this.
- **Alternatives considered**: none.

## R17. Two slips in design.md, corrected

- **Decision**:
  - Decision 8's `<prefix>`: "four levels" becomes "five levels above
    `payload/`, the parent of its `lib/`" (R7).
  - Decision 4's refusal names `pipx reinstall openrepotools` already, by the
    lead's ruling 3, which Step 0 recorded. Nothing further is needed there.
- **Rationale**: an analysis across the artifacts would otherwise find the
  plan and design.md in disagreement.
- **Alternatives considered**: leaving design.md as it was. That was
  rejected, because the plan would then contradict the decision it
  implements.

## R18. Where the gates come from: no ratified constitution

- **Decision**:
  - `.specify/memory/constitution.md` is the unfilled Spec Kit template, so
    it states no principle a gate could check.
  - The plan's gates are AGENTS.md's rules, the governed-invariant rule of
    the Speckit protocol, and the governing change's constraints.
- **Rationale**: the plan template's gate is "determined based on
  constitution file". With no principles, the plan must name the rules it
  does hold itself to.
- **Alternatives considered**: writing a constitution. That is
  `/speckit.constitution`'s act, and outside this feature.
