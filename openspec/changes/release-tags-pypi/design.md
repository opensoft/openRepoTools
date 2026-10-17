# Design

## Context

See proposal.md for the why and the what, and the two delta specs for the
behaviour contract. This file covers how. It answers the five constraints in
clarifications.md (N1–N5) and does not reopen D1–D3.

What the design builds on, as the code stands at `aaa7bc8`:

- **`openRepoTools` is one bash file**, written for bash 3.2.
  - `SELF="${BASH_SOURCE[0]:-$0}"` (`openRepoTools:72`).
  - `die` prints `REFUSED: …` and exits 2 (`:86`).
  - `--install` plans everything before it places anything. The order is
    `plan_install_targets`, `payload_select`, the collection, then
    `plan_hook_merge` and `plan_skill_targets` (`:1848-1866`).
  - Each file is placed by renaming a temporary file over its path. The
    `EXIT` trap removes `"$PLACING"*` (`:240`, `:1801`).
  - `receipt_add` already skips a link (`:1291`).
  - `payload_select` copies locally when every `payload_names` file sits
    beside `$SELF` (`:966-997`).
  - `pin_parse` is the existing fixed-grammar reader (`:458`), with the shape
    helpers `is_lower_hex` and `is_slug` (`:395-406`).
- **The model is openRepoShape v1.1.0 (`190133d`).**
  - Its package is declarative hatchling 1.27.0 under `src/`, with
    force-include and no build hook.
  - Its stamp rule is `read_stamp` (`src/openreposhape/standard.py:141-162`).
  - Its `tests.yml` `package` job builds the wheel twice with `pip wheel`, and
    runs pipx 1.11.1 on Python 3.9 with `PIPX_HOME` and `PIPX_BIN_DIR` in the
    job's own temporary directories.
  - Its `release.yml` holds the gates, the two-build `cmp`, the blob check,
    the `.dist-info` check (`:649-655`) and the digest-definition assertion
    (`:438-440`).
- **Facts checked for this design:**
  - **Hatchling 1.27.0's published wheel:**
    - its reproducible mode is on by default and normalises modes to
      0644/0755 (clarifications N4);
    - a `license-files` pattern that matches nothing raises nothing
      (`hatchling/metadata/core.py:757-770`);
    - its version source searches its file with
      `(?i)^(__version__|VERSION) *= *(['"])v?(?P<version>.+?)\2` under
      `re.MULTILINE`, and takes the first match (`hatchling/version/core.py:6`
      and `:31`).
  - **pipx 1.17.12's source:**
    - the default home is platformdirs' user data directory
      (`pipx/paths.py:14`), which on macOS is
      `~/Library/Application Support/pipx`, a path with a space;
    - it falls back to `~/.local/pipx` where that exists (`:15`);
    - the default bin directory is `~/.local/bin` (`:19`).
- **The triad.**
  - The adoption plan sends `.github/`, `upstream/` and `contracts/` to the
    code leg, and `docs/` to the spec leg. `README.md`, `LICENSE` and
    `.gitattributes` go to the root (`adoption-plan.yaml:79-80`, `:87-88`,
    `:129-130`, `:137-138`, `:183-184`, `:381-382`).
  - openRepoShape v1.1.0's split appends a 10-line LF block to the root's
    `.gitattributes` (#186 comment 6242560541).

## Goals / Non-Goals

**Goals:**

- **One list of payload files.** Bash's `payload_names` stays the only list.
  The wheel's force-include map is written out once and held to that list by
  a test.
- **No channel from Python to bash.** Bash decides package mode, reads the
  stamp and recognises pipx's link from paths and files alone. The entry
  module passes nothing but the person's arguments.
- **Every new refusal happens in the planning phase.** That means pipx's
  link, pip's console script and a broken stamp, so a refusal places
  nothing.
- **The model's checks are taken as they are wherever they apply.** Each
  place this design departs from them is named below.

**Non-Goals:**

- No hatch build hook, and no code that runs at build time apart from
  hatchling.
- No change to the receipt's format, to `payload_select`'s modes or to the
  one-line install's fetch.
- No reading of `pipx_metadata.json`'s contents, and no use of `PIPX_HOME`.
- No Windows behaviour. `os.execvp` is not a true exec on Windows, and there
  is no native Windows command (proposal, Non-goals).

## Decisions

### 1. The package lives in `src/openrepotools/`

The wheel holds `openrepotools/__init__.py`, `openrepotools/_release.py`
(the stamp), one entry module, and `openrepotools/payload/<P>` for every
payload path P. `[tool.hatch.build.targets.wheel] packages` names
`src/openrepotools`.

- **Why `src/`.** The root already holds the bash file `openRepoTools`. A
  directory `openrepotools/` beside it is the same name on a
  case-insensitive disk, macOS's and Windows' default, so one clone could not
  hold both. openRepoShape made the same choice for the same reason (its
  `pyproject.toml` header).
- **Alternative rejected:** a top-level package directory, for the collision
  above.

### 2. The force-include map is written out, and a test holds it to `payload_names`

`pyproject.toml` lists each payload path explicitly, as
`"<P>" = "openrepotools/payload/<P>"`, plus
`"contracts/openreposhape-pin.yaml"`.

A test runs `payload_names` from the bash file and compares its output, plus
the pin file, with the map's keys and with the built wheel's names, in both
directions.

- **Alternative rejected:** a hatch build hook that generates the map from
  `payload_names`. It would put repository code into every build, change
  what the reproducibility check proves, and depart from the model's
  declarative build.

### 3. The entry module execs bash, and reads nothing

The console script's function does one thing. It calls
`os.execvp("bash", ["bash", <payload>/openRepoTools, *sys.argv[1:]])`, where
`<payload>` is the `payload` directory beside the module's own file.

- On `FileNotFoundError` it prints `REFUSED: openRepoTools needs bash, and
  there is no bash on this PATH. Nothing ran.` to stderr and exits 2, the
  same status as bash's `die`.
- It does not read the stamp. Bash is the one reader (Decision 5), so Python
  and bash can never disagree about a stamp.
- **Alternative rejected:** a `subprocess` that passes the status back. A
  signal would come back as a negative return code, and the `EXIT` trap would
  run in a child the person's terminal does not own.
- **Alternative rejected:** validating the stamp in Python as well, as the
  model's `read_stamp` does. That makes two readers that can drift, which is
  why D2 was dismissed.

### 4. Bash decides package mode from paths

Package mode holds when `$SELF`'s directory, resolved with `cd -P` and
`pwd -P`, is named `payload`, its parent is named `openrepotools`, and that
parent holds a regular file `_release.py`.

- A checkout's `$SELF` is the root's `openRepoTools`, whose directory is the
  root, so a checkout never matches. Neither does the one-line install, whose
  `$SELF` is a pipe or a placed file in `<dir>`.
- **In package mode bash reads its own stamp at start-up, before any
  argument is acted on.** A broken stamp refuses every invocation, `--help`
  included, with exit 2:

  ```text
  REFUSED: this package's stamp (openrepotools/_release.py) names part of a release and not all of it: <why>. This build is broken. Reinstall it: pipx reinstall openrepotools
  ```

  This is the model's wording, adapted. The refusal names the stamp file and
  the fix, `pipx reinstall openrepotools` (the lead's ruling 3, Open
  Questions).
- **Alternative rejected:** reading the stamp only for `--version`. A broken
  build would then run `--install` and place files under a release identity
  nobody can name.

### 5. The stamp's grammar, the writer and the reader (N2)

**The file.** It has a module docstring, then exactly five lines, in this
order:

```text
VERSION = "<v>"
TAG = "<t>"
COMMIT = "<c>"
DIGEST = "<d>"
REPOSITORY = "<r>"
```

The committed file has `0.0.0` and four empty strings. The release build
rewrites only those five lines, from the tag, the commit, the digest and
`$GITHUB_REPOSITORY`, and leaves the docstring byte for byte.

**The reader** is a bash function in `pin_parse`'s style. It sets `STAMP_*`
and returns 0, or sets `STAMP_WHY` and returns 1.

- It reads LF only. A carriage return is refused with its line number.
- It skips blank lines, `#` comments, and the one leading docstring: from a
  line that begins with `"""` to the next line that contains `"""`.
- Every other line must be `NAME = "value"` at column 0. NAME is one of the
  five, each appears exactly once, and the value holds no `"`, `\` or `$`.
- An unknown name, a repeated name, a missing name or an unclosed docstring is
  refused.

**The checks, after the read:**

- **Unstamped** is `TAG`, `COMMIT` and `DIGEST` all empty. Then `VERSION`
  must be `0.0.0` and `REPOSITORY` empty. Anything else is a partial stamp.
  - This is stricter than the model, which returns `version or "0.0.0"`. The
    proposal says an unstamped package's `VERSION` is `0.0.0`, and a
    `REPOSITORY` without a commit names nothing.
- **Stamped** is everything else. Then:
  - `VERSION` matches `X.Y.Z` or `X.Y.ZrcN` (digits, no leading zeros) and is
    not `0.0.0`;
  - `TAG` is exactly `v$VERSION`;
  - `is_lower_hex 40 "$COMMIT"` and `is_lower_hex 64 "$DIGEST"` both hold;
  - `is_slug "$REPOSITORY"` holds.
  - Any failure is "a malformed field", named in `STAMP_WHY`.
  - The `TAG = v$VERSION` and slug checks go further than the model, which
    asks only that the tag is non-empty.

**Hatch and bash read the same `VERSION`.**

- Hatch takes the first line anywhere in the file that matches its
  case-insensitive pattern.
- So the reader also refuses a docstring line that begins, in any case, with
  `version` or `__version__` followed by optional spaces and `=`.
- A test runs hatch's pattern and the reader on the committed file and on a
  stamped one, and requires one answer.

**Writer and reader agree.** A test writes a stamp with the build's writer,
reads it back with the bash reader, and covers each refusal with one fixture:

- an unreadable file;
- a carriage return;
- a missing, repeated or unknown name;
- a partial stamp, each way;
- each malformed field.

### 6. Recognising pipx's link (N1, proposal VALID 5)

The check runs inside `plan_install_targets`, for the target `openRepoTools`
only, before `unplaceable_kind` is asked about it.

**Resolve.**

- While the path is a link, read it with plain `readlink`. Join a relative
  value to the link's own directory.
- Stop after 40 hops. A longer chain, or a cycle, is not pipx's link.
- Then canonicalise the final file's directory with `cd -P -- … && pwd -P`.
- Every expansion is quoted, because macOS's default pipx home contains a
  space.

**Match.**

- The resolved file is a regular file named `openRepoTools`, in a directory
  named `bin`.
- `<venv>` is that directory's parent. `<venv>/pipx_metadata.json` is a
  regular file.
- Some `<venv>/lib/python*/site-packages/openrepotools/payload/openRepoTools`
  is a regular file. The glob is looped with a `-f` test, because an
  unmatched glob stays literal in bash.

**Result.** On a match, three variables record the skip:
`PIPX_LINK=<dir>/openRepoTools`, `PIPX_VENV` and `PIPX_PAYLOAD`.

- The placement loop skips that name.
- `receipt_add` already writes no row for a link.
- The count line and the skip line are the proposal's.
- Retirement code never touches `PIPX_LINK`.

**The `jq` check stays where it is (N1's open choice).**

- Since pipx's link is recognised before any link refusal, a missing `jq` no
  longer leads to `rm` advice for it. The run reaches `plan_hook_merge`'s
  `jq` refusal instead.
- Moving `jq` ahead of `plan_install_targets` would change the order of
  refusals that A9 Addendum 4 (R-A9-12) fixed, "the targets are asked about
  first", for no further gain.

**A venv-shaped link that fails the rule** (a future pipx layout, say) is
still refused, because it is not provably pipx's. It resolves to
`…/bin/openRepoTools` in a directory that also holds `pyvenv.cfg`.

- Its refusal line calls it "a link into a Python environment, perhaps
  pipx's".
- It prints no `rm -f` for it. It names `pipx reinstall openrepotools`, and
  asks for an issue with the layout.
- That keeps ADV3's failure, deleting the only working command, out of every
  path.

**The fixtures.**

- A fake venv tree per case: `bin/openRepoTools`, `pipx_metadata.json` with
  placeholder content (the rule reads only its existence),
  `lib/python3.X/site-packages/openrepotools/payload/…`, and `pyvenv.cfg`.
- The cases cross pipx 1.11.1, 1.17.8 and 1.18.3 with four homes:
  `$PIPX_HOME`, `~/.local/pipx`, `~/.local/share/pipx`, and a home with a
  space in it, which is the macOS default.
- The python directory differs as those releases' Pythons do: `python3.9`
  for 1.11.1's leg, and a 3.1x for the others.
- The negative cases: a link into a venv without the payload, without the
  metadata file, or not under `bin/`; a chain of 41 links; a cycle.

### 7. The count line when the run is not pipx's own

"pipx's own environment" means package mode with `$SELF` under
`$PIPX_VENV`'s `site-packages`. Then the count line is
`openRepoTools: 16 of 17 placed in <dir>, and 1 left to pipx`.

Otherwise the line adds
`; the other 16 now come from <source>, not from openrepotools <version>`.

- `<source>` is the repository and ref the run collected from, the pair
  `payload_where` names (`openRepoTools:797-803`), written `<repo> @ <ref>`
  as `--version` writes it. For an adopted source it is the pinned code
  repository and revision. One test pins the exact line for each layout.
- `<version>` comes from the reader of Decision 5, run on the `_release.py`
  beside `PIPX_PAYLOAD`. An unstamped one gives `0.0.0`.
- A stamp there that fails the reader gives `an unreadable stamp`, and the
  install goes on. That stamp belongs to another install, and this run's own
  bytes are not in question.

### 8. pip's console script, and the PATH report (N5, VALID 9)

**Recognising it.** A regular file at `<dir>/openRepoTools` is pip's console
script for openrepotools when:

- its first line is `#!` and names a path whose last segment begins with
  `python`;
- and one of its first 20 lines matches
  `^from openrepotools(\.[A-Za-z_][A-Za-z0-9_]*)* import `, which is the line
  pip's console-script template writes.

The check runs in `plan_install_targets`, in every mode. That includes a
package-mode `--install` run from a `pip install --user` of this package, so
the pip route is refused even when it is pip's own command running.

**The refusal (exit 2):**

```text
REFUSED: `--install` will not replace <dir>/openRepoTools: it is pip's console script for openrepotools (`pip install --user openrepotools` leaves it there), and another installer's command is not this installer's to overwrite.
    NOTHING was installed and nothing already installed was replaced.
    pipx is the one package route. To move to it:
        pip uninstall openrepotools
        pipx install openrepotools
        openRepoTools --install
```

**The PATH report** runs last in a package-mode `--install`, after every
placement, and changes nothing.

- `type -P openRepoTools` finds the first on `PATH`. bash 3.2 has `type -P`.
- It is resolved with Decision 6's loop.
- It is compared with `<prefix>/bin/openRepoTools`, where `<prefix>` is the
  directory four levels above the payload
  (`<prefix>/lib/pythonX.Y/site-packages/openrepotools/payload`).
- On a mismatch, or when nothing is found, it prints one line, and the exit
  status is unchanged:

  ```text
  openRepoTools: note: the first openRepoTools on your PATH is <first, or "none">, not this package's <prefix>/bin/openRepoTools, so the release you just installed is not the one that runs; put the directory that holds pipx's link to it ahead of <first's directory> on PATH
  ```

- **Alternative rejected:** refusing the install on a mismatch. The files are
  placed correctly, and only the order of `PATH` is wrong, which is the
  person's to change.

### 9. The `package` job and the package tests

The job runs on `ubuntu-latest` with Python 3.9.

- **The checkout uses `submodules: true`**, because the command tests skip
  without the submodule (AGENTS.md).
- **The build follows the model's `package` job:** `pip wheel` twice with
  `SOURCE_DATE_EPOCH` at the commit's time, then `cmp`. The isolated build
  takes hatchling at `pyproject.toml`'s pin.
- **The wheel checks:**
  - each file outside `.dist-info` is checked against its blob:
    `openrepotools/payload/<P>` against `git show HEAD:<P>` with its mode
    against `git ls-tree`, and every module against `src/<name>`;
  - the `.dist-info` names are checked, `licenses/LICENSE` included, as the
    release build checks them;
  - the stamp is checked to be byte-identical to the committed
    `_release.py`.
- **pipx is the model's:** 1.11.1 on 3.9, with `PIPX_HOME` and
  `PIPX_BIN_DIR` under `$RUNNER_TEMP`. Then come the unstamped `--version`,
  and an offline `--install` into a temporary `HOME`. The skip and count
  lines are compared exactly.
- **The package tests, run so that a skip fails the job:**
  - pytest at the suite's pin, with `--junitxml`;
  - a step then fails unless the report has at least one test and zero
    skipped.
  - The package tests read `pyproject.toml` with `tomllib`, or with `tomli`
    where `tomllib` is missing. The job installs `tomli` at a pinned
    version, by hash, beside pytest.
  - **Alternative rejected:** an environment switch inside the tests that
    turns a skip into a failure. That couples the tests to CI, and a JUnit
    count also catches zero tests collected.
- **The pipx-skip tests build Decision 6's fixtures,** with no pipx and no
  wheel. So they also run in the `tests` job, and skip in
  `tests-no-submodule` exactly as the other command tests do.

### 10. The release workflow: the model's, with these differences

`release.yml` is adapted from openRepoShape v1.1.0. Its gates, the two
`git archive` builds, the `cmp`, the blob check, the `.dist-info` check, the
sha256 record, the upload re-reads and the served-digest check are taken
over as they are. It differs in these places:

- **The version.** `X.Y.ZrcN` is accepted for TestPyPI, and the `pypi` job
  refuses every version that is not a final `X.Y.Z`.
- **The stamp's fifth field.** `REPOSITORY` is set to `$GITHUB_REPOSITORY`.
- **The digest-definition assertion.** It compares the pinned
  `repo_shape.TREE_DIGEST_DEFINITION` with the literal `sorted-ls-tree-r-v1`
  and with `contracts/openreposhape-pin.yaml`'s `digest_definition`.
  - A test holds bash's `--version` label to the same literal, so the three
    are tied.
  - The model compares with its package's constant instead, which this
    package does not have.
- **The payload blob and mode check** covers `openrepotools/payload/`
  against the commit's paths, not `src/`.
- **The install check.**
  - Its legs are ubuntu and macOS on Python 3.x, and ubuntu on 3.9, with no
    Windows leg.
  - Each leg runs `--version`, then an offline `--install` into a temporary
    `HOME`, and compares the skip and count lines exactly.
  - On macOS, the leg reruns `--install` with `PATH="/bin:$PATH"` so that
    `/bin/bash` 3.2 runs, and prints `BASH_VERSION`.
  - On 3.9, the leg runs `py_compile` on `lanes-index` and `lane-worktrees`.
- **The release notes.** `release.yml` reads none (Decision 11).

### 11. The release notes stay in the spec leg, and no release step reads them (N3)

- `docs/release-notes/` stays under `docs/`, which goes to spec. That is the
  plan's own mapping, and lane openRepoTools-1's reading at v1.1.0 (#186
  comment 6242560541).
- No step of `release.yml` reads a notes file, and no code-leg test reads
  one.
- The GitHub Release is created by the release owner, by hand, after PyPI
  serves the version: `gh release create v<version> --repo <repository>
  --verify-tag --notes-file <spec>/docs/release-notes/v<version>.md`, from a
  checkout that has the spec leg. `<repository>` is the one the tag is in,
  `opensoft/openRepoTools-code` for v1.1.0.
  - That is a person's act and not a release step, so it does not break the
    invariant.
  - The Release's body is the notes file's text, as v1.0.0's is. The v1.1.0
    draft ends with a line naming its own path in the spec leg, so the
    Release also links to the notes, as N3's default asks.
  - `release.yml`'s RELEASING header writes the step down.
- **Alternative rejected:** moving the notes to code. It needs an exception
  in the plan, and buys nothing, since nothing at run time reads them.

### 12. File modes: the installer is the source (N4)

- `--install` already sets 755 on each command it places, and 644 or 600 on
  everything else, on every run. That stays the only thing modes depend on
  at run time.
- The wheel's mode check stays as a build check. Hatchling 1.27.0 normalises
  to 0644/0755 from the owner's execute bit, so a `100755` blob is 0755 in
  the wheel and a `100644` blob is 0644.

## Risks / Trade-offs

- **[A pipx release changes its venv layout]** → The path rule then stops
  matching, and the install is refused. The venv-shaped refusal of Decision 6
  prints no `rm` for that link, and names `pipx reinstall`. The fixtures name
  the three pipx versions they mirror, so a new layout gets a new fixture.
- **[`readlink` behaves differently across platforms]** → Only plain
  `readlink <path>` is used, which prints the link's own value on Linux,
  macOS and BSD alike. The canonicalisation is bash's `cd -P` and `pwd -P`.
  The macOS install-check leg runs the rule under bash 3.2.
- **[Hatch and bash read different versions from `_release.py`]** →
  Decision 5's reader refuses every line hatch could match before the real
  `VERSION`, and a test runs both readers on the same files.
- **[The code leg ships without `LICENSE`]** → Hatchling would build a wheel
  without it. The `.dist-info` check in the `package` job and in the release
  build refuses that wheel. `code-0001` is the code leg's first commit, and
  lane openRepoTools-3 checks blob `261eeb9` before the first `package` run
  (proposal, "Release owner").
- **[`git archive` changes bytes through `.gitattributes`]** → The blob check
  compares every packaged file with `git show`, so an `eol`, `ident`,
  `export-subst` or `filter` transform refuses the build, never ships. An
  `export-ignore` on a payload path fails the wheel-versus-`payload_names`
  test. The plan puts `.gitattributes`, with openRepoShape v1.1.0's appended
  LF block, at the assembly root and not in the code leg (Context). An `eol=lf`
  rule on files that are already LF changes no byte in any case.
- **[A job id changes in the code leg's `tests.yml`]** → The gate finds no
  run of that job and refuses (delta spec, "The cutover invariants"). Lane
  openRepoTools-1's plan carries the four ids as an invariant.
- **[A stale bash `openRepoTools` shadows pipx's]** → Decision 8's report
  names it after a package-mode install. After a plain `pipx install` over
  the one-line install's file, no package-mode run happens, so no report can
  appear. pipx's own warning is then the only signal, and README gives
  `pipx install --force` for that reason.
- **[Strictness costs compatibility]** → Decision 5 refuses some stamps the
  model would accept: a non-`0.0.0` version with no commit, a tag other than
  `v<version>`, or a repository that is not a slug. Only the release build
  writes a stamp, and its writer is tested against the reader, so no
  legitimate stamp is refused.

## Migration Plan

Proposal "Sequencing with the triad cutover" holds the order. What the design
adds to it:

1. **Feature 006 lands in `opensoft/openRepoTools`.** One PR, or a short
   series, as `/speckit.tasks` splits it. Each lands by squash once it is
   reviewed and green. These land before lane openRepoTools-1's rehearsal
   and plan.
2. **A branch rehearsal of `release.yml`** builds and runs the install check,
   and uploads nothing. Then, on Brett Heap's word, the `v1.1.0rc1` TestPyPI
   rehearsal runs.
3. **The cutover.** `execute` runs, then `code-0001` as the code leg's first
   commit, then the `LICENSE` blob check. Then Brett's code-side acts, then
   v1.1.0, then the README PR.

**Rollback.**

- Before any upload, a defect is fixed by a PR on `main`, or the PR that
  introduced it is reverted. Nothing outside the repository has changed.
- After an upload, a defect is fixed forward by the next patch version. A
  tag is never moved, and an index never takes a file name twice.
- A workstation can always leave the package: `pipx uninstall openrepotools`,
  then the one-line install's `--install`. The uninstall scenario in the
  `pypi-package` delta spec holds this.

## Open Questions

### Resolved by the lead

Lane openRepoTools-3, the lead, ruled on the points this file's writer
raised. Each is marked with the date of the ruling.

1. **The `.dist-info` check is confirmed.** Resolved by the lead,
   2026-10-17.
   - The release build and the `package` job both require the wheel's
     `.dist-info` to hold exactly `METADATA`, `WHEEL`, `RECORD`,
     `entry_points.txt` and `licenses/LICENSE`, with that `LICENSE` equal to
     the commit's (Decisions 9 and 10).
   - This check is how "the package never tolerates a missing `LICENSE`" is
     enforced, because hatchling 1.27.0's `license-files` glob does not fail
     on a missing file.
   - The order stands: T006's `code-0001` is the code leg's first commit,
     right after `execute`.
2. **workBenches main is noted at `bdab3e2`.** Resolved by the lead,
   2026-10-17. Both of its checks, `check_target_preflight` and
   `verify_installed`, still hold there, and this change cites `bdab3e2`.
3. **The stricter stamp rules are confirmed.** Resolved by the lead,
   2026-10-17.
   - Unstamped means `VERSION` `0.0.0` with an empty `REPOSITORY`.
   - `TAG` equals `v$VERSION`.
   - `REPOSITORY` is an owner/name slug.
   - A broken stamp refuses every package-mode invocation, `--help`
     included (Decision 4).
   - The refusal names the stamp file and the fix,
     `pipx reinstall openrepotools`. Decision 4's line says so, in place of
     the `pipx install --force openrepotools` it named before this ruling.
4. **The design's additions are confirmed.** Resolved by the lead,
   2026-10-17.
   - The `jq` check stays where it is (Decision 6).
   - A venv-looking link that fails the pipx rule is refused, with no `rm`
     advice (Decision 6).
   - The stamp reader keeps the docstring guard (Decision 5).
   - The fixtures include a pipx home with a space in it (Decision 6).
5. **The checkout's count line is confirmed.** Resolved by the lead,
   2026-10-17. It is exactly the line the proposal ("Coexistence with the
   other installers") and the `pypi-package` delta spec fix (Decision 7).

### Still open

- **The workBenches condition.** Brett Heap's choice of (a), (b) or (c) is
  still open, as the lead recorded on 2026-10-17. The proposal's single
  bullet that depends on it, position (c), stays marked pending his word.
  Whatever he chooses changes only that bullet in the proposal and when the
  README PR of step 6 can open. It changes none of the code, specs or
  decisions here.
- **The `release/*` ruleset.** #850 leaves the choice to Brett: no
  force-push and no deletion, or a rule requiring PRs. It decides only
  whether a back-port is a fast-forward or a cherry-pick PR, and both are
  specified.
- **The text of `docs/release-notes/v1.1.0.md`** is drafted in feature 006
  and settled before the tag.
