# Quickstart: validating 006-release-pypi

How a writer or a reviewer proves the feature locally, from the root of the
feature's worktree. CI is the suite of record (AGENTS.md). These steps are
the same checks, run by hand.

Run every command from a shell that has no `LANES_*` or `TMUX` variable
inherited from a lane session. Temporary directories come from `mktemp -d`.

## 0. Prerequisites

```sh
git submodule update --init upstream/openRepoShape   # the command and workflow tests skip without it
command -v bash jq git python3                        # all four are needed
```

Three steps can need the network. Building the wheel (step 3) fetches
hatchling into pip's isolated build environment. A pipx that installs with
pip rather than uv (step 5) fetches pip into a new `PIPX_HOME`'s shared
libraries. Step 8 asks GitHub. Nothing else here does.

## 1. The package's tests, without a wheel

```sh
bash tests/run.sh -k 'test_package or test_install_pipx or test_release_workflow or test_tests_workflow' -rs
```

- Expect every test to pass, except the built-wheel tests in
  `tests/test_package.py`. Those skip, naming `OPENREPOTOOLS_TEST_WHEEL`.
- The pipx-link tests build fake venvs: the twelve layouts in
  [contracts/pipx-link.md](contracts/pipx-link.md) and the negative cases.
  They need no pipx.

## 2. The hygiene and command suites still hold

```sh
bash tests/run.sh -k 'repo_hygiene or openrepotools_command or install_'
```

- The standard-library rule now covers `src/openrepotools/`, and the compile
  test compiles it.
- The `--version` tests at `tests/test_openrepotools_command.py:323-344` keep
  their assertions.
- The README and AGENTS.md caps pass, with any dated entry the change needed.

## 3. Build the wheel twice and compare

```sh
out="$(mktemp -d)"
export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct HEAD)"
python3 -m pip wheel --no-deps -w "$out/a" .
python3 -m pip wheel --no-deps -w "$out/b" .
cmp "$out"/a/*.whl "$out"/b/*.whl && echo "one file"
python3 -m zipfile -l "$out"/a/*.whl
```

The listing must be exactly [contracts/wheel.md](contracts/wheel.md)'s
members: the three modules, the 24 payload files and the five `.dist-info`
names.

## 4. The built-wheel tests

```sh
OPENREPOTOOLS_TEST_WHEEL="$(ls "$out"/a/*.whl)" \
  bash tests/run.sh -k 'test_package' -rs
```

No test may skip.

## 5. Install with pipx, and install offline

```sh
t="$(mktemp -d)"
export PIPX_HOME="$t/pipx" PIPX_BIN_DIR="$t/bin"
pipx install "$(ls "$out"/a/*.whl)"
"$t/bin/openRepoTools" --version          # the five unstamped lines, exactly

mkdir -p "$t/user-home" "$t/offline"
printf '#!/bin/sh\nexit 1\n' > "$t/offline/gh";   chmod 755 "$t/offline/gh"
printf '#!/bin/sh\nexit 1\n' > "$t/offline/curl"; chmod 755 "$t/offline/curl"
HOME="$t/user-home" OPENREPOTOOLS_BIN_DIR="$t/bin" \
  OPENREPOTOOLS_REPO=offline.invalid/sentinel PATH="$t/offline:$PATH" \
  "$t/bin/openRepoTools" --install
```

Expect each of these:

- the skip line
  `openRepoTools: left to pipx at <t>/bin/openRepoTools (a link into pipx's openrepotools environment); …`;
- `openRepoTools: 16 of 17 placed in <t>/bin, and 1 left to pipx`;
- 28 rows in the receipt under
  `"$t/user-home/.local/share/openRepoTools/"`;
- `"$t/bin/openRepoTools"` still a link into
  `"$t/pipx/venvs/openrepotools/bin/"`;
- last, the PATH note, because `$t/bin` is not on `PATH`:
  `openRepoTools: note: the first openRepoTools on your PATH is <first, or "none">, not this package's <t>/pipx/venvs/openrepotools/bin/openRepoTools, …`.

Then run `--install` again from the checkout's own `openRepoTools`, with the
same environment:

```sh
HOME="$t/user-home" OPENREPOTOOLS_BIN_DIR="$t/bin" PATH="$t/offline:$PATH" \
  bash ./openRepoTools --install
```

Its count line now ends in
`; the other 16 now come from opensoft/openRepoTools @ main, not from openrepotools 0.0.0`.

## 6. A broken stamp refuses everything

Edit the installed package's stamp, under
`"$t/pipx/venvs/openrepotools/lib/python3.*/site-packages/openrepotools/_release.py"`,
so that it has a `COMMIT` and no `DIGEST`. Then:

```sh
"$t/bin/openRepoTools" --help; echo "exit $?"   # REFUSED: this package's stamp (openrepotools/_release.py) … pipx reinstall openrepotools; exit 2
```

## 7. The workflows

```sh
actionlint .github/workflows/tests.yml .github/workflows/release.yml   # where actionlint is installed
bash tests/run.sh -k 'test_release_workflow or test_tests_workflow'
```

- The suite runs the release workflow's stamp writer, and checks the file
  offline.
- Nothing here dispatches it. A branch rehearsal is the release owner's act,
  once Brett Heap has created the `testpypi` and `pypi` environments. The
  change's `tasks.md` tracks it (item 4.2).

## 8. The release notes

```sh
gh release view v1.0.0 --repo opensoft/openRepoTools --json body --jq .body \
  | cmp - docs/release-notes/v1.0.0.md && echo "byte for byte"
```

## 9. Clean up

```sh
pipx uninstall openrepotools    # with PIPX_HOME and PIPX_BIN_DIR still exported
rm -rf -- "$t" "$out"
```
