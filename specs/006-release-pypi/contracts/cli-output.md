# Contract: what the command prints

Every line below is held exactly by a test. `<dir>` is
`$OPENREPOTOOLS_BIN_DIR`, by default `~/.local/bin`, written as the run
resolves it. Text in angle brackets is filled in at run time. Everything else
is literal, and two spaces mean two spaces.

`die` prints a blank line and then `REFUSED: <text>` to stderr, and exits 2
(`openRepoTools:86`). Every refusal below goes through it, except the one
from the entry module.

## `--version`

### From a stamped package (stdout, exit 0)

```text
openRepoTools <VERSION> (<REPOSITORY> @ <COMMIT>)
  version   <VERSION>
  tag       <TAG>
  commit    <COMMIT>
  digest    <DIGEST> (sorted-ls-tree-r-v1)
```

For v1.1.0, the first line is
`openRepoTools 1.1.0 (opensoft/openRepoTools-code @ <commit>)`.

### From an unstamped package (stdout, exit 0)

```text
openRepoTools 0.0.0 (an unstamped package)
  version   0.0.0, unstamped: a package built from a checkout, not a release
  tag       none
  commit    none
  digest    none
```

### From a checkout or the one-line install (stdout, exit 0)

```text
openRepoTools (<repo> @ <ref>)
```

This is unchanged. `<repo>` is `${OPENREPOTOOLS_REPO:-opensoft/openRepoTools}`
and `<ref>` is `${OPENREPOTOOLS_REF:-main}`. No `OPENREPOTOOLS_PACKAGE_*`
variable changes it. `tests/test_openrepotools_command.py:299-319` keeps its
assertions, and only the docstring at `:300-302` is rewritten.

The digest label `sorted-ls-tree-r-v1` is one literal. It is held equal to
the pinned `repo_shape.TREE_DIGEST_DEFINITION` and to
`contracts/openreposhape-pin.yaml`'s `digest_definition` (FR-029, design.md
Decision 10).

## A broken stamp, in package mode (stderr, exit 2)

It is printed for every invocation, `--help`, `--version` and `--install`
included, before any argument is acted on:

```text
REFUSED: this package's stamp (openrepotools/_release.py) names part of a release and not all of it: <why>. This build is broken. Reinstall it: pipx reinstall openrepotools
```

`<why>` is `stamp_read`'s `STAMP_WHY`. Each refusal reason has its own text,
as [stamp.md](stamp.md) lists them.

## No `bash` (the entry module; stderr, exit 2)

```text
REFUSED: openRepoTools needs bash, and there is no bash on this PATH. Nothing ran.
```

## `--install` with pipx's link

### The skip line (stdout), printed where the `openRepoTools:` per-file line would be

```text
openRepoTools: left to pipx at <dir>/openRepoTools (a link into pipx's openrepotools environment); update it with `pipx upgrade openrepotools`, then run `openRepoTools --install` again
```

### The count line, run from pipx's own environment (stdout)

```text
openRepoTools: 16 of 17 placed in <dir>, and 1 left to pipx
```

### The count line, run from anywhere else (stdout)

```text
openRepoTools: 16 of 17 placed in <dir>, and 1 left to pipx; the other 16 now come from <source>, not from openrepotools <version>
```

- `<source>` is `<PAYLOAD_REPO> @ <PAYLOAD_REV>` for an adopted source, and
  `<REPO> @ <REF>` otherwise (research R5).
- `<version>` is the `VERSION` of the stamp beside pipx's payload, `0.0.0`
  when it is unstamped. It is the literal `an unreadable stamp` when that
  stamp fails the reader, and the install still goes on.

### With no pipx link, the count line is today's

```text
openRepoTools: 17 of 17 placed in <dir>
```

### Receipt rows

The rows are 28 with pipx's link (16 + 6 + 6) and 29 without it. The receipt
format does not change.

## pip's console script at `<dir>/openRepoTools` (stderr, exit 2; planning phase)

This is design.md Decision 8's text, with `die`'s prefix:

```text
REFUSED: `--install` will not replace <dir>/openRepoTools: it is pip's console script for openrepotools (`pip install --user openrepotools` leaves it there), and another installer's command is not this installer's to overwrite.
    NOTHING was installed and nothing already installed was replaced.
    pipx is the one package route. To move to it:
        pip uninstall openrepotools
        pipx install openrepotools
        openRepoTools --install
```

## The PATH report (stdout; last in a package-mode `--install`; exit status unchanged)

```text
openRepoTools: note: the first openRepoTools on your PATH is <first, or "none">, not this package's <prefix>/bin/openRepoTools, so the release you just installed is not the one that runs; put the directory that holds pipx's link to it ahead of <first's directory> on PATH
```

- It is printed only on a mismatch, or when `type -P openRepoTools` finds
  nothing.
- `<first>` is that path as `type -P` gives it.
- `<first's directory>` is its `dirname`.
- When nothing is found, `<first's directory>` cannot be filled, so the line
  is the same up to its last `;`, and then ends differently:

  ```text
  openRepoTools: note: the first openRepoTools on your PATH is none, not this package's <prefix>/bin/openRepoTools, so the release you just installed is not the one that runs; put the directory that holds pipx's link to it on PATH
  ```
- `<prefix>` is five levels above `payload/` (research R7).

## A venv-looking link that fails the pipx rule (stderr, exit 2; planning phase)

The link resolves to `…/bin/openRepoTools` whose parent holds `pyvenv.cfg`,
but it fails the pipx rule. It is listed in `plan_install_targets`' refusal
as this entry:

```text
    <dir>/openRepoTools — a link into a Python environment, perhaps pipx's (<venv>), in a layout this installer does not recognise
```

- The refusal's `rm -f -- …` line names only the other bad targets.
- When that link is the only bad target, the "Clear them, then re-run" lines
  and the `rm -f` line are not printed at all.
- In every case, this paragraph follows the list:

```text
    Leave <dir>/openRepoTools where it is: it may be the only openRepoTools that can
    run `--install`. Run `pipx reinstall openrepotools`, then `openRepoTools --install`
    again, and if this refusal stays, open an issue on opensoft/openRepoTools naming
    the layout under <venv>.
```

## No `jq`, with pipx's link in place

The existing `plan_hook_merge` refusal (`openRepoTools:2500`) is unchanged.
The run reaches it because pipx's link is recognised before any link
refusal. Its whole output holds no `rm` line that names
`<dir>/openRepoTools`.

## Unchanged

Everything else stays as it is:

- the existing per-file lines (`installed at`, `updated at`, `already
  installed … (unchanged)`, `(mode restored to 755)`);
- every other refusal;
- the `export PATH=…` note;
- `venv_note`;
- `--help`'s usage text.
