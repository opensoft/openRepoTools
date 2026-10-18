# Implementation Plan: Release tags, release branches and the `openrepotools` package on PyPI

**Branch**: `006-release-pypi` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-release-pypi/spec.md`

**Governance**: the OpenSpec change
[`release-tags-pypi`](../../openspec/changes/release-tags-pypi/proposal.md),
opensoft/openRepoTools#228. Its [design.md](../../openspec/changes/release-tags-pypi/design.md)
holds decisions 1 to 12, and the lead's rulings of 2026-10-17. Its
[clarifications.md](../../openspec/changes/release-tags-pypi/clarifications.md)
holds N1 to N5. This plan implements both, and reopens nothing they settle.

## Summary

openRepoTools becomes a release, as well as a checkout.

- **The package.** The `openrepotools` wheel is declarative hatchling 1.27.0
  under `src/`.
  - It carries the whole bash payload byte for byte, at
    `openrepotools/payload/`, together with the openRepoShape pin.
  - A standard-library entry module `exec`s `bash <payload>/openRepoTools`
    with the person's arguments unchanged.
- **The installer.** Bash stays the only reader and the only parser.
  - It recognises package mode from its own path.
  - It reads the five-field stamp beside its payload, with a fixed grammar.
  - It prints the release in `--version`.
  - It refuses a broken stamp before any argument.
  - `--install` skips pipx's link, refuses pip's console script and any
    other link, and reports a shadowed `PATH`. It decides each of these from
    paths and file existence alone.
- **CI.** `tests.yml` gains the `package` job, and push runs on
  `release/v*`.
- **The release workflow.** `release.yml` is new, adapted from openRepoShape
  v1.1.0 (`190133d`).
  - It gates on the annotated tag, the branch, the environments, the
    commit's four CI jobs and the tree digest.
  - It builds twice from `git archive`, stamps the build and compares the
    two.
  - It uploads by trusted publishing, first to TestPyPI, then through the
    install check, then to PyPI. An `rc` reaches TestPyPI only.
  - A repository guard in its code limits `opensoft/openRepoTools` to
    pre-releases on TestPyPI, and every other repository but the code leg
    to nothing (FR-048).
- **The documents.** The release notes, and the README and AGENTS.md
  corrections, follow.

[research.md](research.md) R1 to R20 record each choice design.md left to
this plan.

## Technical Context

**Language/Version**: Each part of the feature is written in one of these:

- bash, written for macOS's bash 3.2 and up, for `openRepoTools`;
- Python 3.9 or later, standard library only, for `src/openrepotools/`, the
  tests and the workflows' inline scripts;
- TOML (`pyproject.toml`);
- GitHub Actions YAML;
- Markdown.

**Primary Dependencies**:

- **At run time**: none. `dependencies = []`. The payload's own
  requirements do not change: bash, git, `jq` for `--install`, python3 for
  two commands, and `gh` or `curl` where they already fetch.
- **To build**: `hatchling==1.27.0`. The release adds `build`. Both come
  from `.github/release-build-requirements.txt`, by hash, wheels only.
- **In CI**: these, each pinned:
  - `actions/checkout` and `actions/setup-python`, at the commits
    `tests.yml` already pins;
  - the artifact actions, at the model's pins;
  - `pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33`
    (v1.14.2);
  - pipx 1.11.1 and 1.17.8, from `.github/release-pipx-requirements.txt`;
  - `pytest==8.3.4`, and `tomli==2.4.1` by hash, from the build lock's own
    entry (research R12).
- **Reused from the submodule**: openRepoShape's pinned
  `scripts/repo_shape.py`, for `tree_digest`, `tree_digest_from_gh`,
  `TREE_DIGEST_DEFINITION` and `load_yaml`. It is never copied.

**Storage**: files only.

- The stamp, `src/openrepotools/_release.py`, is new.
- The install receipt's TSV is unchanged in format.
- `settings.json`'s two hook entries are unchanged.

**Testing**:

- pytest through `tests/run.sh`. CI's `tests` job is the suite of record.
- The tests are standard-library only. Fake venv layouts stand in for pipx.
  Fake `gh` and `curl` refuse every fetch.
- Workflow YAML is read by the pinned `load_yaml`.
- Built-wheel tests read `OPENREPOTOOLS_TEST_WHEEL`. The `package` job fails
  on any skip, by a JUnit count.

**Target Platform**:

- **Runs on**: Linux and macOS, and WSL2 on Windows. Python 3.9 or later;
  bash 3.2 or later.
- **CI**: `ubuntu-latest`. The release install check adds `macos-latest`,
  run under `/bin/bash` 3.2.

**Project Type**: a command-line toolset, the bash installer and the
commands it places, published as one Python wheel, with CI and release
workflows.

**Performance Goals**: none at run time beyond today's. The build has one
goal: two builds of one commit are one file.

**Constraints**:

- The package install is offline.
- There is no channel from Python to bash, and no environment variable is
  trusted for the stamp.
- Every new refusal is made in the planning phase and places nothing.
- The installer's payload list is the only list.
- The code holds to bash 3.2: no `${x,,}`, `mapfile`, `declare -A`,
  `local -n`, `readlink -f` or `realpath`, and no multi-line `awk -v` value.
- The suite reaches no network, and creates no real repository.
- Command and workflow tests skip without the submodule, and never fail for
  its absence.
- No tracked file holds a host path.
- Line caps move only by dated entries.

**Scale/Scope**:

- 24 payload files in the wheel. 31 artifacts per install, of which 30 are
  placed and 1 is left to pipx when pipx's link is present.
- 1 console script.
- 4 CI jobs in `tests.yml`. 4 jobs in `release.yml`, with 3 install-check
  legs.
- 12 positive and 5 negative pipx fixtures.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is the unfilled Spec Kit template, so it
states no principle (research R18). The gates below are the rules this
repository and the governing change do state. Each was checked before
Phase 0 and again after Phase 1.

| # | Gate (source) | Before Phase 0 | After Phase 1 |
| --- | --- | --- | --- |
| G1 | Shipped bash holds to bash 3.2, and `awk -v` carries one line (AGENTS.md) | PASS: design.md Decisions 5 and 6 name the constructs | PASS: [contracts/pipx-link.md](contracts/pipx-link.md) and [contracts/stamp.md](contracts/stamp.md) use plain `readlink`, `cd -P`, `pwd -P`, `case` and loops |
| G2 | Nothing under `upstream/openRepoShape` is edited, and the pin does not move (AGENTS.md; proposal Non-goals) | PASS | PASS: the digest code and `load_yaml` are run from the submodule, and never copied (R9) |
| G3 | The suite reaches no network, and creates no real repository (AGENTS.md) | PASS | PASS: wheel tests take a built wheel by variable (R8); the v1.0.0 notes are checked by their task, not the suite (R15) |
| G4 | Tests skip without the submodule, naming it, and never fail for it (AGENTS.md; `tests-no-submodule`) | PASS | PASS: workflow tests skip like command tests (R9); the `package` job checks out with `submodules: true` and fails on a skip |
| G5 | AGENTS.md and README caps move only by dated entries (`tests/test_repo_hygiene.py:1748`, `:2253`) | PASS | PASS: R16 |
| G6 | Governed files (CI workflows, and every file recording a pin or a digest) are `[O]` work (Speckit protocol, Build Tiers) | PASS | PASS: `tests.yml`, `release.yml`, both hash locks, the stamp and every action pin are touched only by `[O]` tasks |
| G7 | Every refusal is in the planning phase, and a refusal places nothing (design.md Goals) | PASS | PASS: pipx's link, a venv-shaped link and pip's script are decided in `plan_install_targets`; a broken stamp in `package_init` before the argument loop |
| G8 | Brett Heap decides every tag, cut and upload; no lane act is a build task (proposal "Release owner") | PASS | PASS: environments, publishers, tags, dispatches, uploads, the Release and the assembly README PR stay in the change's `tasks.md` |
| G9 | No new runtime dependency, and the package's modules are standard-library only (proposal Non-goals) | PASS | PASS: `dependencies = []`, enforced by a hygiene test |
| G10 | One list of payload files (design.md Goals) | PASS | PASS: the force-include map and the wheel are held to `payload_names` (R2) |
| G11 | No host path in any tracked file (`HOST_ABSOLUTE_PATH`) | PASS | PASS: workflows use `$RUNNER_TEMP` and `$HOME` ([contracts/workflows.md](contracts/workflows.md)) |
| G12 | Nothing uploads to PyPI from `opensoft/openRepoTools`, and no rehearsal uses `1.1.0` (Brett Heap's answers 2 and 3) | PASS | PASS: the repository guard decides in `build`, before any approval, and again in each upload job's first step (FR-048, R19); `pypi` is skipped for a pre-release and refuses one if it starts; no pypi.org publisher exists for this repository; the RELEASING header states it |

No gate fails, so Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/006-release-pypi/
├── spec.md              # /speckit.specify
├── checklists/
│   └── requirements.md  # /speckit.specify's quality checklist
├── plan.md              # this file
├── research.md          # Phase 0: R1 to R20
├── data-model.md        # Phase 1: the stamp, layouts, the install result, releases
├── quickstart.md        # Phase 1: validating the feature by hand
├── contracts/
│   ├── cli-output.md    # every exact line the command prints
│   ├── stamp.md         # the stamp's grammar, reader, writer and hatch agreement
│   ├── pipx-link.md     # pipx's link, pip's script, the PATH report, the fixtures
│   ├── wheel.md         # pyproject.toml, the 24-entry map, the wheel and its checks
│   └── workflows.md     # tests.yml's package job, and release.yml
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
pyproject.toml                               # NEW: contracts/wheel.md
src/openrepotools/
├── __init__.py                              # NEW: a docstring only (R1)
├── cli.py                                   # NEW: main(), which execs bash (design.md Decision 3)
└── _release.py                              # NEW: the committed, unstamped stamp (contracts/stamp.md)
openRepoTools                                # CHANGED: link_resolve, package_payload_dir, stamp_read,
                                             #   package_init, the --version arm, pipx_link_match,
                                             #   venv_shaped_link, pip_script_is, path_report, and
                                             #   plan_install_targets and install_commands (R3)
.github/
├── release-build-requirements.txt           # NEW: the model's hash lock, re-headed (R11)
├── release-pipx-requirements.txt            # NEW: the model's hash lock, re-headed (R11)
└── workflows/
    ├── tests.yml                            # CHANGED: release/v* push, the package job, the header
    └── release.yml                          # NEW: contracts/workflows.md
tests/
├── package_layout.py                        # NEW: fixture builders, standard library only, no conftest import
├── test_package.py                          # NEW: metadata, the map, the entry module, built-wheel checks
├── test_package_stamp.py                    # NEW: the reader, package mode, --version, the broken stamp
├── test_install_pipx.py                     # NEW: pipx's link, coexistence, pip, PATH, upgrade, uninstall
├── test_release_workflow.py                 # NEW: release.yml, both locks, the stamp writer round trip
├── test_tests_workflow.py                   # NEW: tests.yml's triggers, job ids and package job
├── test_repo_hygiene.py                     # CHANGED: the standard-library rule, the compile set, caps
└── test_openrepotools_command.py            # CHANGED: one docstring (:300-302), assertions unchanged
docs/release-notes/
├── v1.0.0.md                                # NEW: the published body, byte for byte (R15)
└── v1.1.0.md                                # NEW: the draft
README.md                                    # CHANGED: the version paragraph and three passages
AGENTS.md                                    # CHANGED: the CI paragraph (lines 232-239)
```

**Structure Decision**: this is a single repository, with the package under
`src/` beside the root's bash file (design.md Decision 1). After the cutover,
`pyproject.toml`, `src/`, `.github/`, `tests/` and the payload go to the code
leg. `docs/release-notes/` goes to the spec leg, and README.md, AGENTS.md
and LICENSE to the root. Lane openRepoTools-1's regenerated adoption plan
carries that split. This feature does not edit
`openspec/changes/migrate-to-triad/`.

### The test layout

These names are fixed here, so that test and implementation tasks agree.

- **`tests/package_layout.py`** imports only the standard library, and
  finds the repository as `Path(__file__).resolve().parent.parent`. It
  provides these builders:
  - `package_tree(prefix, python="python3.12", stamp=None) -> Path` builds
    `<prefix>/lib/<python>/site-packages/openrepotools/` from the working
    tree: `__init__.py`, `cli.py`, `_release.py` (or the `stamp` text given)
    and `payload/` with the 24 files. It returns the payload directory.
  - `pipx_venv(pipx_home, release, python) -> Path` builds
    `<pipx_home>/venvs/openrepotools/` around `package_tree`, with
    `bin/openRepoTools`, `pipx_metadata.json` and `pyvenv.cfg`. It returns
    the venv. `release` is one of `"1.11.1"`, `"1.17.8"` and `"1.18.3"`.
  - `console_script(path, python)` writes pip's console-script template for
    `openrepotools.cli:main`, with `#!<python>`.
  - `stamp_text(**fields) -> str` gives the committed file's text with the
    given values.
- **Test-name prefixes**, so that each task's `verify:` can select exactly
  its tests with `-k`:

  | Module | Prefixes |
  | --- | --- |
  | `test_install_pipx.py` | `test_pipx_link_`, `test_pipx_skip_`, `test_pipx_offline_`, `test_coexist_`, `test_pip_script_`, `test_path_report_`, `test_pipx_upgrade_`, `test_pipx_uninstall_` |
  | `test_package.py` | `test_metadata_`, `test_payload_map_`, `test_wheel_`, `test_entry_` |
  | `test_package_stamp.py` | `test_stamp_reader_`, `test_stamp_hatch_`, `test_package_version_`, `test_package_broken_stamp_`, `test_package_no_env_channel_`, `test_package_parser_` |
  | `test_release_workflow.py` | `test_release_trigger_`, `test_release_build_`, `test_release_stamp_writer_`, `test_release_upload_`, `test_release_install_check_`, `test_release_lock_`, `test_release_header_`, `test_release_reads_`, `test_release_guard_` |
  | `test_tests_workflow.py` | `test_tests_yml_` |

- **Reuse.** The command helpers come from `tests/test_openrepotools_command.py`:
  `COMMAND`, `command_env`, `run_cmd`, `source_tree`, `placement_temporaries`
  and `NEEDS_JQ`. `tests/test_install_skill_and_hook.py` already imports
  them that way. The function-cutting helper is
  `tests/test_install_by_rename.py`'s `installer_function`.

### Governed files in this feature

Every task that touches one of these is `[O]`:

- `.github/workflows/tests.yml` and `.github/workflows/release.yml`;
- `.github/release-build-requirements.txt` and
  `.github/release-pipx-requirements.txt`;
- every action pin;
- the stamp, `src/openrepotools/_release.py`, and the code that reads or
  writes it.

### Delivery: a short series of pull requests

These follow design.md's Migration Plan step 1. Each lands by squash once it
is reviewed and green, as the change's `tasks.md` item 3.1 records. All of
them land before lane openRepoTools-1's rehearsal and adoption plan (item
3.2).

1. **The package and the installer.** User Stories 1, 2 and 3: Phases 1 to
   5 of `tasks.md`.
2. **CI.** User Story 4: the hash locks, `tests.yml` and AGENTS.md. The
   `package` job needs both locks.
3. **The release workflow.** User Story 5: `release.yml` and its tests.
4. **The record.** User Story 6: the release notes and README.

## Complexity Tracking

No gate fails, so there is nothing to justify.
