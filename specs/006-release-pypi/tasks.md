---

description: "Task list for 006-release-pypi: release tags, release branches and the openrepotools package on PyPI"
---

# Tasks: Release tags, release branches and the `openrepotools` package on PyPI

**Input**: the design documents in `specs/006-release-pypi/`

**Prerequisites**: plan.md and spec.md, plus research.md, data-model.md,
contracts/ and quickstart.md

**Tests**: the spec requires them. Many requirements read "a test holds…".
Each story's test task comes first, and its tests MUST fail before that
story's implementation task begins.

**Organization**: tasks are grouped by user story, so that each story can be
built and tested on its own.

## Format: `[ID] [P?] [Story] [Tier] Description — files: … — verify: …`

- **[P]**: the task can run in parallel with the others marked so in its
  phase. They touch different files and depend on no incomplete task.
- **[Story]**: US1 to US6, as in spec.md.
- **[Tier]**:
  - `[S]` runs on `sonnet-xhigh`, `[O]` on `opus-xhigh`.
  - There is no `[H]`, because AGENTS.md has no `## Governed invariants`
    section.
  - Every task touching a governed file (plan.md, "Governed files in this
    feature") is `[O]`. So is every task that makes a design choice, a
    contract or a boundary, or that is security-sensitive (the release
    workflow, trusted publishing, the stamp).
- **`files:`** lists every path the task may create, change or delete,
  relative to the worktree root. A diff outside it fails the task.
- **`verify:`** is run from the worktree root, and exits 0 only when the task
  is done.
  - A test-writing task verifies with `--collect-only`. It exits 5 when no
    test is collected and 2 on an import error, so it fails until the tests
    exist and import cleanly.
  - `-k` selects tests by the name prefixes that plan.md fixes ("The test
    layout").

## Before Phase 1: bring the branch up to `main`

These are not tasks with a `files:` list, because a merge touches files of
every kind. They are recorded here because every task below assumes them.

- **The implementation's first act is to merge `origin/main` into
  `006-release-pypi`,** by a merge commit, never a rebase or a force-push.
  This is the lead's ruling of 2026-10-18, and `main` is not merged before
  then. The branch was cut at `aaa7bc8`, and `main`
  is at `83d2690` as of 2026-10-18. Since the cut:
  - `tests/conftest.py` gained the four-roots layout;
  - `tests/test_repo_hygiene.py` moved by about 260 lines;
  - AGENTS.md is 321 lines against a cap of 323;
  - `lane-start` and `skills/handoff/SKILL.md` changed in content. Both are
    payload files, but their modes and the payload list are unchanged, and
    the wheel copies whatever bytes the commit holds.
- **Line numbers.** Line numbers in plan.md, research.md and the contracts
  are at `aaa7bc8`. Find each test by its name, and each bash function by
  its name.
- **The test environment.** Run every verify command from a shell with no
  `LANES_*` or `TMUX` variable inherited from a lane session (quickstart.md).

---

## Phase 1: Setup (shared infrastructure)

**Purpose**: the package's fixed files, which every story reads.

- [X] T001 [P] [O] Create `src/openrepotools/__init__.py` holding the SPDX line and a docstring, and no code (research R1; the lead added the SPDX line on T001's report). Create the committed, unstamped stamp `src/openrepotools/_release.py` exactly as contracts/stamp.md gives it: a module docstring with no line that hatch could read as the version, then the five lines `VERSION = "0.0.0"`, `TAG = ""`, `COMMIT = ""`, `DIGEST = ""` and `REPOSITORY = ""`, LF only, with a final newline — files: `src/openrepotools/__init__.py`, `src/openrepotools/_release.py` — verify: `python3 -I -c "import re,pathlib;t=pathlib.Path('src/openrepotools/_release.py').read_text();assert chr(13) not in t and t.endswith(chr(10));a=re.findall(r'(?m)^([A-Z_]+) *= *\"(.*)\"$',t);assert a==[('VERSION','0.0.0'),('TAG',''),('COMMIT',''),('DIGEST',''),('REPOSITORY','')],a;assert not re.search(r'(?im)^(__version__|version) *=',t.split('VERSION = ')[0]);assert 'import' not in pathlib.Path('src/openrepotools/__init__.py').read_text()"`
- [X] T002 [P] [O] Create `pyproject.toml` per contracts/wheel.md, holding what is detailed below — files: `pyproject.toml` — verify: `python3 -I -c "import tomllib;d=tomllib.load(open('pyproject.toml','rb'));p=d['project'];w=d['tool']['hatch']['build']['targets']['wheel'];f=w['force-include'];assert d['build-system']['requires']==['hatchling==1.27.0'] and p['name']=='openrepotools' and p['dependencies']==[] and 'readme' not in p and p['requires-python']=='>=3.9' and p['scripts']=={'openRepoTools':'openrepotools.cli:main'} and w['packages']==['src/openrepotools'] and d['tool']['hatch']['version']['path']=='src/openrepotools/_release.py' and len(f)==24 and all(v=='openrepotools/payload/'+k for k,v in f.items())"`
  - the build system, pinned at `hatchling==1.27.0`;
  - `[project]`: the name `openrepotools`, a dynamic version, `requires-python = ">=3.9"`, `license = "Apache-2.0"` with `license-files = ["LICENSE"]`, `dependencies = []`, and no `readme`;
  - the one script, `openRepoTools = "openrepotools.cli:main"`;
  - the hatch version path, and the wheel's `packages`;
  - the 24-entry force-include map, in `payload_names` order, then the pin;
  - header comments in the model's style that give the reasons: `src/` for the case-insensitive clash, no `readme` because of the cutover, and the hatchling pin for Python 3.9.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the fixture builders that four test modules share.

**⚠️ CRITICAL**: No user story's tests can be written until this phase is
complete.

- [X] T003 [O] Create `tests/package_layout.py`, with the fixture builders `package_tree`, `pipx_venv`, `console_script` and `stamp_text` that plan.md's "The test layout" names, as detailed below — files: `tests/package_layout.py` — verify: `python3 -I -c "import sys,tempfile,pathlib;sys.path.insert(0,'tests');import package_layout as L;d=pathlib.Path(tempfile.mkdtemp())/'Application Support'/'pipx';v=L.pipx_venv(d,'1.11.1','python3.9');p=v/'lib'/'python3.9'/'site-packages'/'openrepotools'/'payload';assert (v/'pipx_metadata.json').is_file() and (v/'pyvenv.cfg').is_file() and (p/'openRepoTools').is_file() and (p/'contracts'/'openreposhape-pin.yaml').is_file() and len([x for x in p.rglob('*') if x.is_file()])==24 and 'from openrepotools.cli import main' in (v/'bin'/'openRepoTools').read_text()"`
  - imports only the standard library and never imports `conftest`, and finds the repository from its own path;
  - has `package_tree` copy every `src/openrepotools/*.py` that exists, and the 24 payload files;
  - has `pipx_venv` mirror pipx 1.11.1, 1.17.8 and 1.18.3, each with `venvs/openrepotools`, `bin/openRepoTools`, `pipx_metadata.json` with placeholder content, and `pyvenv.cfg`;
  - works under a path that holds a space.

**Checkpoint**: the foundation is ready, and the user stories can begin.

---

## Phase 3: User Story 1 - Install the toolset from the package, offline (Priority: P1) 🎯 MVP

**Goal**: an install from the package places every artifact offline, leaves
pipx's `openRepoTools` to pipx, and refuses every other link, without ever
advising the `rm` of a working command.

**Independent Test**: `bash tests/run.sh -k 'test_pipx_link_ or test_pipx_skip_ or test_pipx_offline_ or test_entry_'`.
The tests use fake venv layouts, with no pipx and no wheel.

### Tests for User Story 1 (write first; they MUST fail before T007 and T008)

- [X] T004 [P] [US1] [O] Write the US1 tests of `tests/test_install_pipx.py`, reusing `tests/package_layout.py` and `test_openrepotools_command`'s `command_env`, `source_tree` and `NEEDS_JQ`, as detailed below — files: `tests/test_install_pipx.py` — verify: `bash tests/run.sh --collect-only -q -k 'test_pipx_link_ or test_pipx_skip_ or test_pipx_offline_'`
  - `test_pipx_link_*`: the twelve-case matrix of contracts/pipx-link.md and its five negative cases, with `PIPX_HOME` set only in its own column.
  - `test_pipx_skip_*`:
    - the exact skip line and the pipx-own count line, 28 receipt rows, and the link left unchanged;
    - a second link at another target, refused with today's `rm -f` advice for that one alone;
    - the venv-shaped refusal: contracts/cli-output.md's entry and paragraph, with no `rm` line naming the link;
    - no `jq`: ends in the `jq` refusal, with no `rm` for the link;
    - `restart` retirement, and a later `--install`, both leaving the link.
  - `test_pipx_offline_*`: a package-mode `--install` with `OPENREPOTOOLS_REPO=offline.invalid/sentinel` and a `gh` and a `curl` that fail. It places the same artifacts and receipt rows as a checkout's install, apart from the link.
  - Every test here runs `bash <payload>/openRepoTools` directly, as the entry module's exec would. None runs the console script, which is `test_entry_*`'s job in T005. So these tests need T008 and not T007, and T007 and T008 stay parallel.
- [X] T005 [P] [US1] [O] Write `tests/test_package.py`, as detailed below — files: `tests/test_package.py` — verify: `bash tests/run.sh --collect-only -q -k 'test_metadata_ or test_payload_map_ or test_wheel_ or test_entry_'`
  - `test_metadata_*`: contracts/wheel.md's `pyproject.toml` rules, read with `tomllib`, falling back to `tomli`, and skipping, naming `tomli`, when neither imports.
  - `test_payload_map_*`: the force-include keys and values against `payload_names` (run from the bash file) plus the pin, in both directions, naming every difference.
  - `test_wheel_*`: read `OPENREPOTOOLS_TEST_WHEEL`, skipping and naming it when it is unset. Run contracts/wheel.md's checks 2, 3, 5 and 6 and the member comparison.
  - `test_entry_*`, run on a `package_tree`'s console script:
    - a refused argument gives the payload's own exit status and message;
    - a SIGTERM mid-placement leaves no placement temporary (`placement_temporaries`);
    - with no `bash` on `PATH`, the exact no-bash refusal, exit 2, and nothing run;
    - `wip_shape_ref`, cut out with `installer_function`, reads the packaged pin.
  - **Amended 2026-10-22, for #256:** `test_entry_*` also holds the entry module's second refusal (contracts/cli-output.md, "A `bash` on PATH that cannot be run"). Where the only `bash` on `PATH` is a file with no execute bit, a file in a directory that cannot be searched, or a file that is not a program, it prints the exact refusal with the system's reason, exits 2 and runs nothing. Where a runnable `bash` comes later on `PATH`, that one runs instead.
- [X] T006 [P] [US1] [S] Add the standard-library test to `tests/test_repo_hygiene.py`, and widen its compile test, as detailed below — files: `tests/test_repo_hygiene.py` — verify: `bash tests/run.sh -k 'standard_library or python_files_compile'`
  - add `test_the_package_imports_only_the_standard_library`. It parses every module under `src/openrepotools/` with `ast`, and holds its imports to an explicit allowlist. Where `sys.stdlib_module_names` exists, the allowlist is itself checked against it, so the test never skips on Python 3.9.
  - extend `test_the_python_files_compile` to compile `src/openrepotools/*.py`.

### Implementation for User Story 1

- [X] T007 [P] [US1] [O] Create `src/openrepotools/cli.py` with `main()` per design.md Decision 3, as detailed below — files: `src/openrepotools/cli.py` — verify: `bash tests/run.sh -k 'test_entry_ or test_metadata_ or test_payload_map_ or standard_library or python_files_compile'`
  - it calls `os.execvp("bash", ["bash", <payload>/openRepoTools, *sys.argv[1:]])`, where `<payload>` is the `payload` directory beside the module's own file;
  - on `FileNotFoundError`, it prints contracts/cli-output.md's no-bash refusal to stderr and returns 2;
  - it reads no stamp, and passes nothing else.
  - **Amended 2026-10-22, for #256:** `main()` now catches every `OSError`, not only `FileNotFoundError`. The two not-found errors, `FileNotFoundError` and `NotADirectoryError` (T026), keep the no-bash refusal above. Every other one prints contracts/cli-output.md's second refusal, for a `bash` on `PATH` that cannot be run, to stderr and returns 2 (design.md Decision 3, amended again 2026-10-21).
- [X] T008 [P] [US1] [O] Teach `openRepoTools` to recognise and skip pipx's link, holding to bash 3.2 throughout, as detailed below — files: `openRepoTools` — verify: `bash tests/run.sh -k 'test_pipx_link_ or test_pipx_skip_ or test_pipx_offline_ or openrepotools_command or install_skill or install_by_rename or install_payload'`
  - add `link_resolve`, `package_payload_dir`, `pipx_link_match` and `venv_shaped_link` (contracts/pipx-link.md);
  - call the pipx match in `plan_install_targets`, for `openRepoTools`, before `unplaceable_kind`;
  - skip that target in `install_commands`' placement loop, printing the exact skip line;
  - print the pipx-own count line when the run is package mode under `PIPX_VENV`, the same line in any other run that skipped the link (T013 adds its suffix), and today's line otherwise;
  - list a venv-shaped link with contracts/cli-output.md's entry and paragraph, and keep it out of the `rm -f` line.

- [X] T026 [US1] [O] Put back the signals Python ignores before the exec, and refuse a `PATH` that ends in a file, per design.md Decision 3 as amended by the lead on 2026-10-18 on T007's report, as detailed below — files: `src/openrepotools/cli.py`, `tests/test_package.py`, `tests/test_repo_hygiene.py` — verify: `bash tests/run.sh -k 'test_entry_ or standard_library or python_files_compile'`
  - `cli.py` sets SIGPIPE and SIGXFSZ to `SIG_DFL` before `os.execvp`, and treats `NotADirectoryError` as it treats `FileNotFoundError`;
  - `tests/test_repo_hygiene.py`'s allowlist gains `signal`, with its reason;
  - `tests/test_package.py` gains two `test_entry_*` cases:
    - a payload `bash` that reads its own ignored-signal set finds neither SIGPIPE nor SIGXFSZ ignored. On Linux it reads `/proc/self/status`'s `SigIgn`; elsewhere, a `yes | head -n 1` pipeline under `pipefail` ends in status 141;
    - with no `bash` on `PATH` and `PATH`'s last entry a file, the exact no-bash refusal, exit 2, and nothing run.
  - It runs after T007 and before T009. It was added after T025 by the lead's ruling, so its number is out of order.
  - **Amended 2026-10-22, for #256:** `FileNotFoundError` and `NotADirectoryError` still get the no-bash refusal. Every other `OSError` now gets contracts/cli-output.md's second refusal, for a `bash` on `PATH` that cannot be run, with exit 2. Both are printed after the exec has failed and the two signals have gone back to what they were before it (design.md Decision 3, amended again 2026-10-21).

**Checkpoint**: User Story 1 works and is tested on its own.

---

## Phase 4: User Story 2 - Know which release is running (Priority: P1)

**Goal**: `--version` names a stamped package's release, says when a package
is unstamped, and is unchanged for a checkout. A broken stamp refuses every
invocation.

**Independent Test**: `bash tests/run.sh -k 'test_package_stamp or test_version_'`.

### Tests for User Story 2 (write first; they MUST fail before T011)

- [X] T009 [P] [US2] [O] Write `tests/test_package_stamp.py`, as detailed below — files: `tests/test_package_stamp.py` — verify: `bash tests/run.sh --collect-only -q -k 'test_stamp_reader_ or test_stamp_hatch_ or test_package_version_ or test_package_broken_stamp_ or test_package_no_env_channel_ or test_package_parser_'`
  - `test_stamp_reader_*`: one fixture per row of contracts/stamp.md's refusal table, plus the committed and a stamped file, running `stamp_read` cut out with `installer_function`.
  - `test_stamp_hatch_*`: hatch's version pattern, copied with its citation (`hatchling/version/core.py:6` and `:32` in 1.27.0), against `stamp_read`, on the committed file, a stamped one and a guarded-docstring fixture.
  - `test_package_version_*`: the exact stamped and unstamped five lines, from `package_tree` layouts.
  - `test_package_broken_stamp_*`: exit 2 and the exact refusal for `--help`, `--version` and `--install`, with nothing placed. One fixture is used for each of the three causes of contracts/cli-output.md (`cannot be read`, `is partial:`, `is malformed:`), and each case requires the line to read as that contract gives it.
  - `test_package_no_env_channel_*`: a checkout's, and a piped one-line install's, exact `openRepoTools (<repo> @ <ref>)`, with each `OPENREPOTOOLS_PACKAGE_*` variable of research R4 set.
  - `test_package_parser_*`: `--help`, `--install --version` and an unknown argument behave as in a checkout.
- [X] T010 [P] [US2] [S] Rewrite only the docstring of `test_version_names_the_repository_and_the_ref` in `tests/test_openrepotools_command.py`. It now says that a checkout and the one-line install name the repository and ref they fetch from, and that a package names its release (contracts/cli-output.md). Every assertion of the three `test_version_*` tests stays byte for byte — files: `tests/test_openrepotools_command.py` — verify: `! git diff -U0 "$(git merge-base HEAD origin/main)" -- tests/test_openrepotools_command.py | command grep -qE '^[-+][[:space:]]*(assert|result =)' && bash tests/run.sh -k 'test_version_'`

### Implementation for User Story 2

- [X] T011 [US2] [O] Teach `openRepoTools` to read its stamp and print its release, as detailed below — files: `openRepoTools` — verify: `bash tests/run.sh -k 'test_package_stamp or test_version_ or test_pipx_ or test_entry_'`
  - add `stamp_read`: contracts/stamp.md's grammar and checks, in `pin_parse`'s style, holding to bash 3.2, and never sourcing the file;
  - add `package_init`, called once after every function definition and before the argument loop. In package mode it sets `PACKAGE_DIR` and reads the stamp, and on any refusal it calls `die` with contracts/cli-output.md's broken-stamp line;
  - make the `--version` arm print the stamped or unstamped five lines when `PACKAGE_DIR` is set, and today's line otherwise;
  - read no environment variable for the stamp.

**Checkpoint**: User Stories 1 and 2 both work on their own. Together they
are the MVP.

---

## Phase 5: User Story 3 - Move between installers without being misled (Priority: P2)

**Goal**: each pairing of pipx with the one-line install, a checkout, pip, an
upgrade or an uninstall has one defined, honest outcome.

**Independent Test**: `bash tests/run.sh -k 'test_coexist_ or test_pip_script_ or test_path_report_ or test_pipx_upgrade_ or test_pipx_uninstall_'`.

### Tests for User Story 3 (write first; they MUST fail before T013)

- [X] T012 [US3] [O] Add to `tests/test_install_pipx.py`, as detailed below — files: `tests/test_install_pipx.py` — verify: `bash tests/run.sh --collect-only -q -k 'test_coexist_ or test_pip_script_ or test_path_report_ or test_pipx_upgrade_ or test_pipx_uninstall_'`
  - `test_coexist_*`:
    - a one-line install, replaced by pipx's link as `pipx install --force` leaves it, then `--install` from the venv's payload: the link is skipped, and the sixteen are replaced;
    - a checkout's, and a piped one-line install's, `--install` beside pipx's link, with the exact count line naming `<repo> @ <ref>`, for an unstamped stamp, a stamped one and an unreadable one beside the link's payload. The unreadable case ends in contracts/cli-output.md's `the openrepotools beside pipx's link, whose stamp cannot be read`, and no output contains `openrepotools an unreadable stamp`;
    - a package-mode `--install` from a `package_tree` outside pipx's venv, beside pipx's link, whose count line names `openrepotools <its VERSION>` as the source, never `<repo> @ <ref>`.
  - `test_pip_script_*`: contracts/pipx-link.md's three refused fixtures (the shebang form; the trampoline with a quoted, spaced interpreter; the trampoline with an unquoted interpreter over 127 characters) and its five placed fixtures. One case is a package-mode run whose own command is pip's script. The refused cases give the exact refusal, and place nothing.
  - `test_path_report_*`: the four `PATH` fixtures, the exact note, and an unchanged exit status.
  - `test_pipx_upgrade_*`: one `package_tree` installed, then a second with different payload bytes. A second `--install` replaces the sixteen and still skips the link.
  - `test_pipx_uninstall_*`: the link and the venv are removed, the sixteen are still there, and a checkout's `--install` places a regular file.

### Implementation for User Story 3

- [X] T013 [US3] [O] Teach `openRepoTools` the coexistence rules, as detailed below — files: `openRepoTools` — verify: `bash tests/run.sh -k 'test_install_pipx or test_package_stamp or test_package or openrepotools_command or install_skill or install_by_rename or install_payload'`
  - add the other-source count line (research R5):
    - `<source>` is `openrepotools $STAMP_VERSION` in any package-mode run. In a checkout or the one-line install, it is `PAYLOAD_REPO @ PAYLOAD_REV` for an adopted source, and `REPO @ REF` otherwise;
    - `<version>` comes from `stamp_read` on the stamp beside `PIPX_PAYLOAD`. When that stamp fails the reader, the line ends in contracts/cli-output.md's unreadable-stamp clause;
  - add `pip_script_is`, recognising both of pip's forms, the Python shebang and the `/bin/sh` trampoline (contracts/pipx-link.md), with contracts/cli-output.md's planning-phase refusal, in every mode;
  - add `path_report`, run last in a package-mode `--install`. It uses research R7's `<prefix>` and `link_resolve` on both sides, prints the exact note, and keeps the exit status.

**Checkpoint**: User Stories 1 to 3 are complete. This is pull request 1 of
plan.md's delivery.

---

## Phase 6: User Story 4 - Every commit proves it packages (Priority: P2)

**Goal**: every push to `main` and to `release/v*` runs the four jobs. The
`package` job builds, checks, installs and tests the wheel, and fails on any
skip.

**Independent Test**: `bash tests/run.sh -k test_tests_yml_` offline. Then a
pushed commit's `package` job is green.

### Tests for User Story 4 (write first; they MUST fail before T016)

- [X] T014 [P] [US4] [O] Create `.github/release-build-requirements.txt` and `.github/release-pipx-requirements.txt` from openRepoShape v1.1.0's two files (research R11). Every line below each header stays byte for byte. Each header is rewritten for this repository and #228, with the same uv 0.12.18 command and date — files: `.github/release-build-requirements.txt`, `.github/release-pipx-requirements.txt` — verify: `bash -c 'for f in release-build-requirements.txt release-pipx-requirements.txt; do diff <(sed -n "/^[a-z]/,\$p" ".github/$f") <(gh api -H "Accept: application/vnd.github.raw" "repos/opensoft/openRepoShape/contents/.github/$f?ref=v1.1.0" | sed -n "/^[a-z]/,\$p") || exit 1; done'`
- [X] T015 [P] [US4] [O] Write `tests/test_tests_workflow.py`. Its `test_tests_yml_*` tests load `.github/workflows/tests.yml` with the pinned `repo_shape.load_yaml`, skipping without the submodule as the command tests do. Inside this task, research R9's text fallback applies if a construct is refused. The tests hold contracts/workflows.md's `tests.yml` list, as detailed below — files: `tests/test_tests_workflow.py` — verify: `bash tests/run.sh --collect-only -q -k test_tests_yml_`
  - the triggers;
  - the four job ids;
  - the three existing jobs' `runs-on`, checkout options, Python version and `run:` commands;
  - the `package` job's runner, Python 3.9, `submodules: true`, and steps 4 to 11 in order;
  - the `package` job's `tomli`, extracted from the build lock's own entry with every hash, and no `--hash` held in `tests.yml` itself;
  - the header comment naming both push branches and four jobs;
  - step 6's wheel-check heredoc, extracted and run on four synthetic wheels made from HEAD's blobs, with contracts/workflows.md's four outcomes: the wheel as built passes; no `licenses/LICENSE` fails, naming `LICENSE`; a changed payload byte fails, naming the file; a changed payload mode fails, naming the file.

### Implementation for User Story 4

- [X] T016 [US4] [O] Change `.github/workflows/tests.yml`, as detailed below — files: `.github/workflows/tests.yml` — verify: `actionlint .github/workflows/tests.yml && bash tests/run.sh -k 'test_tests_yml_ or repo_hygiene'`
  - push on `[main, 'release/v*']`;
  - rewrite the header comment of lines 29 to 36 for two push branches and four jobs;
  - add the `package` job, with exactly contracts/workflows.md's steps 1 to 11. Those are two `pip wheel` builds at `SOURCE_DATE_EPOCH` compared with `cmp`; the inline wheel check, with the stamp equal to the committed file; pipx 1.11.1 from the lock; the unstamped `--version`; the offline `--install` beside pipx's link, with exact lines and 28 receipt rows; and the three package test modules, with `OPENREPOTOOLS_TEST_WHEEL` and a JUnit count that fails on any skip;
  - leave the three existing jobs unchanged.
- [X] T017 [US4] [S] Rewrite AGENTS.md's CI paragraph (point 1 of "Testing your changes to this repository") to match FR-025 and FR-026, as detailed below — files: `AGENTS.md`, `tests/test_repo_hygiene.py` — verify: `bash tests/run.sh -k repo_hygiene`
  - `tests.yml` runs `guard-launch-mode`, `tests`, `tests-no-submodule` and `package`, all on ubuntu;
  - it runs on `pull_request`, push to `main` and `release/v*`, nightly, and `workflow_dispatch`;
  - the release workflow's macOS install leg, which runs on dispatch only, is the one place the payload runs under bash 3.2.

  Keep AGENTS.md within `test_agents_md_is_short_enough_to_be_read`'s cap, or add that test's dated entry for the lines this buys.

**Checkpoint**: User Story 4 is complete. This is pull request 2.

---

## Phase 7: User Story 5 - Publish a release only through gates (Priority: P2)

**Goal**: a release reaches the indexes only through every gate, from a
reproducible build, by trusted publishing, with Brett Heap's approvals. A
pre-release never reaches PyPI, and a branch dispatch uploads nothing.

**Independent Test**: `bash tests/run.sh -k test_release_` offline. The
branch rehearsal is the change's `tasks.md` item 4.2, once Brett Heap's
environments exist.

### Tests for User Story 5 (write first; they MUST fail before T019 to T021)

- [X] T018 [US5] [O] Write `tests/test_release_workflow.py`. It loads `release.yml` with the pinned `load_yaml`, skipping without the submodule, and holds contracts/workflows.md's `release.yml` list under these prefixes, as detailed below — files: `tests/test_release_workflow.py` — verify: `bash tests/run.sh --collect-only -q -k test_release_`
  - `test_release_trigger_`, `test_release_build_`, `test_release_upload_`, `test_release_install_check_`, `test_release_header_` and `test_release_reads_`;
  - `test_release_stamp_writer_`: the heredoc, extracted as the model's `heredoc()` does, is run on a copy of the committed stamp and read back by `--version` from a `package_tree`. The step must refuse a file already stamped, and a value no release carries;
  - `test_release_lock_`, for both locks: one version per entry, by sha256; hatchling equal to `pyproject.toml`'s pin; pipx 1.11.1 below Python 3.10 and 1.17.8 from 3.10.
  - `test_release_build_` also runs step 13's wheel-check heredoc on the four synthetic wheels of contracts/workflows.md, with their four outcomes. It also holds the ref step and the branch-membership step to the rehearsal rule: a branch passes as a rehearsal, and any other non-tag ref is refused.
  - `test_release_upload_` also holds each job's permissions exactly: `testpypi` and `pypi` get `id-token: write`, `actions: read` and `contents: read`; `build` gets `contents: read` and `actions: read`; `install` gets `contents: read`. It also holds the two upload conditions: `testpypi` reads `to-testpypi`, and `pypi` reads `to-pypi`, so `pypi` is skipped in an rc rehearsal.
  - `test_release_guard_` (FR-048) covers the repository guard:
    - `test_release_guard_build_*`: the build's guard block, run under each row of contracts/workflows.md's table, with `GITHUB_REPOSITORY`, `GITHUB_REF`, `VERSION` and `GITHUB_OUTPUT` set, must pass or refuse, and record `to-testpypi` and `to-pypi`, exactly as the row says;
    - `test_release_guard_upload_*`: each upload job's first-step guard must refuse what its job may not upload: `testpypi` a final in `opensoft/openRepoTools` and any version elsewhere, and `pypi` everything but a final in `opensoft/openRepoTools-code`.

  The tests also hold the digest-label literal equal to `openRepoTools`' `--version` arm and to the pin's `digest_definition`.

### Implementation for User Story 5

- [X] T019 [US5] [O] Create `.github/workflows/release.yml`'s shape and its `build` job, adapted from openRepoShape v1.1.0 (`190133d`) step for step, as detailed below — files: `.github/workflows/release.yml` — verify: `actionlint .github/workflows/release.yml && bash tests/run.sh -k 'test_release_trigger_ or test_release_build_ or test_release_stamp_writer_ or test_release_lock_ or test_release_reads_ or test_release_guard_build_'`
  - the shape: `workflow_dispatch` with `version`, `permissions: {}`, the `release` concurrency group without cancelling, `bash` by default, and `VERSION` and `PYTHONUTF8` in `env`;
  - contracts/workflows.md's build steps 1 to 14, with design.md Decision 10's differences: `X.Y.ZrcN` accepted; the stamp's `REPOSITORY` from `GITHUB_REPOSITORY`; the digest-definition assertion against the literal and the pin; the payload blob and mode check; and the repository guard of step 1 (FR-048), with its `to-testpypi` and `to-pypi` outputs;
  - the model's rehearsal rule in steps 2 and 3 (FR-029): on a branch, the tag and branch-membership checks pass as a rehearsal, and every other step runs;
  - every action pinned by a full commit.
- [X] T020 [US5] [O] Add `release.yml`'s `testpypi`, `install` and `pypi` jobs per contracts/workflows.md, as detailed below — files: `.github/workflows/release.yml` — verify: `actionlint .github/workflows/release.yml && bash tests/run.sh -k 'test_release_upload_ or test_release_install_check_ or test_release_reads_ or test_release_guard_'`
  - the order: TestPyPI, then the three-leg install check, then PyPI;
  - `id-token: write` on the two upload jobs alone, each in its environment, on a `v*` tag. Each upload job gets exactly `id-token: write`, `actions: read` and `contents: read`, and `install` gets `contents: read`;
  - the re-reads, the empty-index check and the served-digest check, around `pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33`;
  - the install legs: ubuntu 3.x, macOS 3.x and ubuntu 3.9, with no Windows leg. They check the exact skip and count lines; the macOS leg reruns under `/bin/bash`, printing `BASH_VERSION`; the 3.9 leg compiles the installed payload's own `lanes-index` and `lane-worktrees`;
  - the repository guard in the upload jobs (FR-048):
    - `testpypi` runs only when `needs.build.outputs.to-testpypi == 'true'`, and its first step runs the guard again;
    - `pypi` runs only when `needs.build.outputs.to-pypi == 'true'`, so it is skipped in an rc rehearsal;
    - `pypi`'s first step refuses anything but a final in `opensoft/openRepoTools-code`, so in `opensoft/openRepoTools` it refuses outright.
- [X] T021 [US5] [O] Write `release.yml`'s header, RELEASING, in contracts/workflows.md's six sections, as detailed below — files: `.github/workflows/release.yml` — verify: `actionlint .github/workflows/release.yml && bash tests/run.sh -k test_release_`
  - the procedure on Brett Heap's word, with the tag message's form, and the `gh release create` step after PyPI serves the version;
  - #850's branch and tag policy:
    - the trunk;
    - annotated tags, never moved and never reused;
    - `release/vX.Y` cut at `vX.Y.0`;
    - back-ports by fast-forward, by a merge, or by a PR of `cherry-pick -x`;
    - one HOLD at a time, the landing lane back-porting, and the LANDED line naming both commits;
    - patch tags waiting for the newest run;
  - the two rehearsals, and never `1.1.0`:
    - a branch rehearsal builds with the version of the tag it rehearses: before v1.1.0, the next pre-release, `1.1.0rc1` for the first (research R20);
    - its commit needs a finished, green push or dispatch run of `tests.yml`, so dispatch `tests.yml` on that branch first;
    - in an rc rehearsal the `pypi` job is skipped;
  - where releases come from:
    - the code leg's tags from v1.1.0, and `v1.0.0` and the `rc` tags staying here;
    - the repository guard's table (FR-048), with the missing pypi.org publisher as the second line of defence;
    - Brett Heap's environments, ruleset and publishers;
  - what the workflow never reads.

**Checkpoint**: User Story 5 is complete. This is pull request 3.

---

## Phase 8: User Story 6 - The record tells the truth about releases (Priority: P3)

**Goal**: the notes and README say what exists, and offer nothing that the
index does not serve.

**Independent Test**: the three verify commands below.

- [X] T022 [P] [US6] [S] Create `docs/release-notes/v1.0.0.md` as exactly the output of `gh release view v1.0.0 --repo opensoft/openRepoTools --json body --jq .body` (research R15) — files: `docs/release-notes/v1.0.0.md` — verify: `gh release view v1.0.0 --repo opensoft/openRepoTools --json body --jq .body | cmp - docs/release-notes/v1.0.0.md`
- [X] T023 [P] [US6] [S] Draft `docs/release-notes/v1.1.0.md`, as detailed below — files: `docs/release-notes/v1.1.0.md` — verify: `tail -n 1 docs/release-notes/v1.1.0.md | command grep -q 'openRepoTools-spec.*docs/release-notes/v1.1.0.md' && command grep -q '^## Before the tag' docs/release-notes/v1.1.0.md && command grep -q 'pipx install --force openrepotools' docs/release-notes/v1.1.0.md`
  - what v1.1.0 brings: the `openrepotools` package on PyPI; `pipx install` and the offline `--install` that leaves `openRepoTools` to pipx; `--version` naming the release; and the `package` job and the release workflow;
  - the move from the one-line install (FR-024): `pipx install --force openrepotools`, then `openRepoTools --install`, and why `--force` is needed;
  - each value not yet known as a named `<placeholder>`, every one listed in a closing `## Before the tag` checklist;
  - a last line naming the file's own path in the spec leg, `opensoft/openRepoTools-spec`'s `docs/release-notes/v1.1.0.md`.
- [X] T024 [P] [US6] [S] Correct `README.md`, as detailed below — files: `README.md`, `tests/test_repo_hygiene.py`, `tests/test_test_roots.py` — verify: `! command grep -qE 'pipx install( --force)? openrepotools' README.md && bash tests/run.sh -k 'repo_hygiene or readme'`
  - rewrite the paragraph that says "There is no version number here". It now says that releases are annotated tags, that the version comes only from the tag, and what `--version` prints, stamped and unstamped, quoting contracts/cli-output.md's first lines;
  - correct three passages for a workstation with pipx's link: the SEVENTEEN-files count (sixteen placed and one left to pipx), the symlink paragraph (pipx's `openRepoTools` is the one link skipped), and the artifact-count invariant, "Twenty-nine artifacts always, plus the two hook entries once the path they call answers `guard`" since #237 (twenty-eight placed always, one left to pipx and 28 receipt rows, with the hook pair still on top once that path answers, so that nothing contradicts README's #237 text);
  - add no pipx install route;
  - say, in one sentence beside the install routes, that a workstation uses one route or the other until opensoft/workBenches#165 lets workBenches' `setup-estate-commands.sh` accept pipx's link (FR-047: Brett Heap's option (c), 2026-10-18);
  - where README then passes `test_readme_is_short_enough_to_be_read`'s cap, add that test's dated entry.

**Checkpoint**: every user story is complete. This is pull request 4.

---

## Phase 9: Polish & cross-cutting concerns

- [X] T025 [O] Run quickstart.md's steps 1 to 8 on a workstation, as detailed below — files: `specs/006-release-pypi/quickstart.md`, `specs/006-release-pypi/plan.md`, `specs/006-release-pypi/contracts/cli-output.md` (the last two added by the lead's ruling, #228 comment 6255121743) — verify: `bash tests/run.sh`
  - the wheel built twice and compared;
  - the built-wheel tests, with no skip;
  - the pipx install into a temporary home;
  - the offline `--install`, and the checkout's count line;
  - the broken stamp refusing `--help`;
  - `actionlint`;
  - the v1.0.0 `cmp`.

  Correct quickstart.md where a step's text is wrong, and record the outcome in the pull request.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** has no dependency, once the branch is up to `main`.
- **Phase 2 (Foundational)** depends on Phase 1. It blocks every story's
  tests.
- **US1 (Phase 3)** depends on Phase 2.
- **US2 (Phase 4)** depends on US1, because `package_init` builds on
  `package_payload_dir`. T010 can start at any time.
- **US3 (Phase 5)** depends on US2, because its count line reads
  `stamp_read`.
- **US4 (Phase 6)** depends on US1 to US3, because the `package` job runs
  their tests and checks their exact lines. T014 and T015 can start once
  Phase 2 is done.
- **US5 (Phase 7)** depends on T014 (the locks), T011 (the `--version`
  label) and T003 (the fixture builders). It is landed after US4, because
  the release gate requires the `package` job's runs.
- **US6 (Phase 8)**: T022 and T023 can start at any time. T024 waits for US1
  to US3, so that README describes behaviour that exists.
- **Polish (Phase 9)** depends on everything.

### Within each story

- The tests come first, and fail.
- Then the implementation, then the checkpoint.
- Each task is committed on its own, with explicit pathspecs.

### Parallel opportunities

- T001 ∥ T002.
- T004 ∥ T005 ∥ T006, then T007 ∥ T008.
- T009 ∥ T010.
- T014 ∥ T015.
- T022 ∥ T023 ∥ T024.

No two `[P]` tasks of one phase share a path.

## Parallel Example: User Story 1

```bash
# The tests, together (each in its own file):
Task: "T004 the US1 tests of tests/test_install_pipx.py"
Task: "T005 tests/test_package.py"
Task: "T006 the standard-library test in tests/test_repo_hygiene.py"

# Then the implementation, together (one file each):
Task: "T007 src/openrepotools/cli.py"
Task: "T008 the pipx rule in openRepoTools"
```

## Implementation Strategy

### MVP first (User Stories 1 and 2, both P1)

1. Bring the branch up to `main`. Then Phases 1 and 2.
2. Phase 3 (US1). Stop, and validate the offline install beside a fake pipx
   venv.
3. Phase 4 (US2). Stop, and validate `--version` and the broken-stamp
   refusal.
4. US3 completes pull request 1, so that the coexistence lines are true
   before anything is published.

### Incremental delivery

The four pull requests of plan.md land in order, each by squash once it is
reviewed and green (the change's `tasks.md` item 3.1). All four land before
lane openRepoTools-1's rehearsal and adoption plan (item 3.2).

## Coverage outside this task list

These requirements are met by acts that the change's `tasks.md` tracks. They
are Brett Heap's, or lane openRepoTools-3's on his word, and no build task
makes them. The task list writes down what each act needs, in the RELEASING
header (T021), the release notes (T022, T023) and the README (T024).

| Requirement | Met by | Tracked at |
| --- | --- | --- |
| FR-029, FR-031: the `testpypi` and `pypi` environments, the `v*` ruleset, the trusted publishers | Brett Heap's acts | change `tasks.md` 4.1, 6.1 |
| FR-033: the branch rehearsal and the `1.1.0rc1` rehearsal | lane 3, on his word | 4.2, 4.3 |
| FR-036 to FR-041: tags, `release/v1.1`, back-ports, patch tags | lane 3, on his word | 6.2, 6.3, and later releases |
| FR-042: each GitHub Release, after PyPI serves the version | lane 3, on his word | 6.3 |
| FR-045: the pipx route in the assembly's README | lane 3, on his word, once the workBenches condition holds | 6.4 |
| FR-024: README's copy of the move from the one-line install, beside the pipx route (the v1.1.0 notes carry it already, T023) | lane 3, on his word | 6.4 |
| FR-031 and FR-048, the second line of defence: no pypi.org publisher for `opensoft/openRepoTools` | Brett Heap's answer 3; the code guard itself is T019 and T020 | 4.1, 6.1 |
| FR-046: the code leg's `LICENSE` blob `261eeb9`; the plan's entries | lane 3's check; lane openRepoTools-1's plan | 5.1, 5.2 |
| FR-047: the workBenches condition | decided: Brett Heap chose position (c) on 2026-10-18; lane 3 filed opensoft/workBenches#165 | 1.4 |

Brett Heap chose position (c) on 2026-10-18 ("go with (c)": spec.md's FR-047
and design.md's open question 12). The one sentence the README says until
opensoft/workBenches#165 lands, "one route or the other, never both", is
already a task: T024. No other task depends on FR-047.

## Notes

- The tier counts: 26 tasks, of which 20 are `[O]` and 6 are `[S]`, with no
  `[H]`.
- Every task carries one tier tag, a `files:` list and a `verify:` command.
- `actionlint` is used by T016 and T019 to T021. Install it where it is
  missing; CI does not run it.
- T014 and T022 read GitHub (`gh api`, `gh release view`). Every other
  verify command is offline.
