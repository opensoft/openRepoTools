# Contract: the stamp's grammar, its reader and its writer

## The committed file, `src/openrepotools/_release.py`

```python
"""<a module docstring: what the file is, that only the release build writes
it, and that bash reads it with a fixed grammar and never imports it>"""
VERSION = "0.0.0"
TAG = ""
COMMIT = ""
DIGEST = ""
REPOSITORY = ""
```

- It is LF only, with a final newline.
- No line of the docstring begins, in any case, with `version` or
  `__version__` followed by optional spaces and `=`.

## The grammar the bash reader accepts (`stamp_read <file>`)

Lines are read in order.

1. A line holding a carriage return is refused, with its line number.
2. A blank line, or a line whose first character is `#`, is skipped.
3. **The docstring.** Before the first assignment, one line that begins
   with `"""` opens the docstring.
   - The docstring closes on that same line if a second `"""` follows the
     opening one. Otherwise it closes at the next line that contains `"""`.
   - Every docstring line is skipped, except one that begins, in any case,
     with `version` or `__version__` followed by optional spaces and `=`.
     Such a line is refused, because hatch would read it as the version.
   - A docstring with no close is refused.
4. Every other line MUST be `NAME = "VALUE"` from column 0, with one space
   either side of `=`.
   - `NAME` is one of `VERSION`, `TAG`, `COMMIT`, `DIGEST` and `REPOSITORY`.
   - `VALUE` holds no `"`, `\` or `$`.
5. Each of the five names appears exactly once. A repeated, unknown or
   missing name is refused.

The reader holds to bash 3.2: no `${x,,}`, `mapfile`, `declare -A` or
`local -n`, and no `awk -v` value with a newline in it. It never sources,
imports or runs the file.

## The checks after the read

| State | Condition |
| --- | --- |
| unstamped | `TAG`, `COMMIT` and `DIGEST` all empty, `VERSION` is `0.0.0` and `REPOSITORY` is empty |
| stamped | `VERSION` matches `^(0\|[1-9][0-9]*)\.(0\|[1-9][0-9]*)\.(0\|[1-9][0-9]*)(rc(0\|[1-9][0-9]*))?$` and is not `0.0.0`; `TAG` is `v$VERSION`; `is_lower_hex 40 "$COMMIT"`; `is_lower_hex 64 "$DIGEST"`; `is_slug "$REPOSITORY"` |
| broken | anything else |

## Refusal reasons (`STAMP_WHY`), one fixture each

Each reason begins with its cause, exactly one of `cannot be read`,
`is partial:` and `is malformed:`, so that the broken-stamp line in
[cli-output.md](cli-output.md) reads correctly. The rest of each reason's
text is the implementer's. Each MUST be distinct, and each MUST name the
field or the line it is about.

| Fixture | Cause | Reason names |
| --- | --- | --- |
| the file is unreadable (no read permission, or it is a directory) | `cannot be read` | the file |
| a carriage return on line N | `is malformed:` | line N |
| a name missing (each of the five in turn) | `is malformed:` | the missing name |
| a name repeated | `is malformed:` | the repeated name |
| an unknown name, such as `Version` or `BUILD` | `is malformed:` | the unknown name |
| a line that is not `NAME = "VALUE"` | `is malformed:` | the line number |
| an unclosed docstring | `is malformed:` | the docstring |
| a docstring line hatch could read as the version | `is malformed:` | that line |
| partial: a `COMMIT` and no `DIGEST` | `is partial:` | the empty fields |
| partial: a `TAG` alone | `is partial:` | the empty fields |
| unstamped-looking with a `REPOSITORY` | `is partial:` | `REPOSITORY` |
| all of `TAG`, `COMMIT` and `DIGEST`, with `VERSION` `0.0.0` | `is malformed:` | `VERSION` |
| a malformed `VERSION`, such as `1.1`, `01.1.0` or `1.1.0-rc1` | `is malformed:` | `VERSION` |
| `TAG` other than `v$VERSION` | `is malformed:` | `TAG` |
| `COMMIT` of 39 digits, or with upper case | `is malformed:` | `COMMIT` |
| `DIGEST` of 63 digits | `is malformed:` | `DIGEST` |
| `REPOSITORY` that is not a slug, such as `openRepoTools` or `a/b/c` | `is malformed:` | `REPOSITORY` |

## Agreement with hatch

- Hatch's version source finds the version with
  `(?i)^(__version__|VERSION) *= *(['"])v?(?P<version>.+?)\2` under
  `re.MULTILINE`, and takes the first match
  (`hatchling/version/core.py:6` and `:31` in 1.27.0).
- A test runs that pattern, copied with its citation, and `stamp_read` on
  each of these, and requires one `VERSION` from both:
  - the committed file;
  - a stamped file;
  - a fixture with a guarded docstring line, which the reader refuses and
    hatch would misread.

## The writer: `release.yml`'s "write the stamp into both extractions" step

- **Input**: the two extractions' `src/openrepotools/_release.py` paths as
  arguments, and `VERSION`, `TAG`, `COMMIT`, `DIGEST` and `REPOSITORY` from
  the step's environment. `REPOSITORY` is set from `$GITHUB_REPOSITORY`.
  Nothing is pasted into the script by an expression.
- **Checks before writing**: each value has the stamped shape above, and
  differs from its unstamped value.
- **The write**:
  - Each of the five committed lines (`VERSION = "0.0.0"`, `TAG = ""`,
    `COMMIT = ""`, `DIGEST = ""` and `REPOSITORY = ""`) is replaced exactly
    once.
  - A count other than one refuses, so a file already stamped is refused.
  - The docstring and every other byte stay as they are.
- **After writing**: the file is read again, and must assign exactly the
  five release values.
- **The test**:
  - `tests/test_release_workflow.py` extracts this heredoc and runs it on a
    copy of the committed file.
  - It then places the result as `_release.py` beside a fake
    `openrepotools/payload/`, and requires `--version`'s stamped lines to
    carry the same five values.
  - It also requires that the step refuses a file already stamped, and a
    value no release carries.
