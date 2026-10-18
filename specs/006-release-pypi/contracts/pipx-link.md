# Contract: pipx's link, pip's console script and the PATH report

All of this runs in `plan_install_targets` (`openRepoTools:3051`), for the
target `<dir>/openRepoTools` only, before `unplaceable_kind` is asked about
it. The one exception is the PATH report, which runs after every placement.
It is the same in every mode: package, checkout and one-line install.

## `link_resolve <path>`

```text
p := <path>; hops := 0
while p is a symbolic link:
    hops := hops + 1; if hops > 40: fail          # a longer chain, or a cycle
    v := `readlink -- "$p"`                        # plain readlink, never -f; never realpath
    if v is relative: v := "$(dirname -- "$p")/$v"
    p := v
dir := `cd -P -- "$(dirname -- "$p")" && pwd -P`  # fail if it does not cd
print "$dir/${p##*/}"
```

- Every expansion is quoted. macOS's default pipx home,
  `~/Library/Application Support/pipx`, holds a space.
- The PATH report reuses this function.

## `pipx_link_match <dir>/openRepoTools`

pipx's link holds when all of these are true:

1. `[ -L "$target" ]`.
2. `link_resolve` succeeds, and gives `R`.
3. `R` is a regular file, `${R##*/}` is `openRepoTools`, and the directory
   holding it is named `bin`.
4. `V` is that `bin`'s parent, and `"$V/pipx_metadata.json"` is a regular
   file.
5. For some `L` in `"$V"/lib/python*/site-packages/openrepotools/payload`,
   `"$L/openRepoTools"` is a regular file. The glob is looped over with a
   `-f` test, because an unmatched glob stays literal.

**On a match** it sets three variables:

- `PIPX_LINK="$target"`;
- `PIPX_VENV="$V"`;
- `PIPX_PAYLOAD=` the canonical `L`.

Nothing reads `PIPX_HOME`, parses `pipx_metadata.json`, or needs `jq`.

**Then the run does the following:**

- The placement loop in `install_commands` skips `openRepoTools`, and prints
  the skip line in its place.
- `placed` counts 16.
- The count line takes its pipx form ([cli-output.md](cli-output.md)).
- `receipt_add` already writes no row for a link (`openRepoTools:1515-1517`).
- `retire_commands` never names `PIPX_LINK`, because `RETIRED` does not hold
  `openRepoTools`. A test holds that.

## `venv_shaped_link <dir>/openRepoTools`

It is true when steps 1 to 3 of the match hold, the `bin`'s parent holds a
regular `pyvenv.cfg`, and the full match fails. Such a target is a refusal,
in [cli-output.md](cli-output.md)'s words, with no `rm` advice for it.

## The fixtures (`tests/test_install_pipx.py`)

A fake venv per case, with no real pipx and no wheel. Each holds:

- `bin/openRepoTools`, a console-script-shaped file;
- `pipx_metadata.json`, with placeholder content, since only its existence
  is read;
- `pyvenv.cfg`;
- `lib/python3.N/site-packages/openrepotools/payload/`, holding a copy of
  every payload file;
- `lib/python3.N/site-packages/openrepotools/_release.py`.

**The positive matrix**, twelve cases. Each is recognised the same way, and
each prints the exact skip and count lines:

| pipx release it mirrors | `python3.N` | under `$PIPX_HOME` | under `~/.local/pipx` | under `~/.local/share/pipx` | under a home with a space |
| --- | --- | --- | --- | --- | --- |
| 1.11.1 | `python3.9` | case | case | case | case |
| 1.17.8 | `python3.12` | case | case | case | case |
| 1.18.3 | `python3.13` | case | case | case | case |

- The venv directory is `<home>/venvs/openrepotools`, which is where each of
  these pipx releases puts a package's venv.
- The link in `<dir>` is absolute in some cases and relative in others.
- `PIPX_HOME` is set only in its own column, to show that nothing reads it.
- The home with a space is
  `<tmp>/Library/Application Support/pipx`.

**The negative cases.** Each refuses before anything is placed:

- a link into a venv with no `openrepotools/payload/openRepoTools`. It holds
  `pyvenv.cfg`, so it is refused as venv-shaped, with no `rm` advice;
- a link into a venv with no `pipx_metadata.json`. This is venv-shaped too;
- a link whose target is not in a `bin/` directory. It is an ordinary link,
  refused with today's text;
- a chain of 41 links. It is not pipx's link, and is refused;
- a two-link cycle. It is not pipx's link, and is refused.

**The cross-cutting cases:**

- no `jq` on `PATH`, with pipx's link in place, which ends in the `jq`
  refusal with no `rm` for the link;
- a second target that is a link, which is refused, naming it, with
  today's `rm -f` advice for it alone;
- a later `--install` with the link still in place;
- `restart` retirement with the link in place.

## `pip_script_is <dir>/openRepoTools`

It runs for a regular file that is not a link. It is true when both of
these hold.

1. **The interpreter is a Python**, in either of the two forms pip writes.
   - **The shebang form.** The first line begins with `#!`, and the first
     word after `#!` has a last `/` segment that begins with `python`.
   - **The trampoline form.** pip writes this when the interpreter's path
     holds a space or is too long for a shebang (pip 26.2.1,
     `pip/_vendor/distlib/scripts.py:180-182`; the lead's ruling of
     2026-10-18). It is three lines:

     ```text
     #!/bin/sh
     '''exec' "<python>" "$0" "$@"
     ' '''
     ```

     - Line 1 is exactly `#!/bin/sh`.
     - Line 2 begins with `'''exec' `. The interpreter follows: quoted, up
       to the next `"`, when it begins with `"`; otherwise up to the first
       space. Then comes anything, and line 2 ends with ` "$0" "$@"`. The
       interpreter's last `/` segment begins with `python`.
     - Line 3 is exactly `' '''`.
     - The interpreter is unquoted when its path is long and holds no space.
2. **It imports the entry point.** One of the first 20 lines matches
   `^from openrepotools(\.[A-Za-z_][A-Za-z0-9_]*)* import `. pip's own
   template writes that line at column 0, in both forms
   (`PipScriptMaker`, `pip/_internal/operations/install/wheel.py:417-424` in
   pip 26.2.1).

The rule reads lines with `IFS= read -r`, and uses `case` patterns and
parameter expansion. It holds to bash 3.2.

On true, the install is refused with [cli-output.md](cli-output.md)'s pip
refusal, in the planning phase, in every mode. That includes a package-mode
run whose own command is that script.

**The fixtures.** These are refused:

- pip's shebang form, `#!<abs python>` followed by
  `from openrepotools.cli import main`;
- pip's trampoline form, with a quoted interpreter path that holds a space
  (`'''exec' "<tmp>/py env/bin/python3" "$0" "$@"`);
- pip's trampoline form, with an unquoted interpreter path longer than 127
  characters.

These are placed as today:

- the shebang form's file with `#!/bin/bash` in place of the Python;
- a trampoline whose `exec` names a non-Python interpreter, such as
  `'''exec' "<tmp>/x/bin/ruby" "$0" "$@"`;
- a `#!/bin/sh` file that is not the trampoline, holding the import line
  but no `'''exec'` line;
- a Python script that imports something else;
- this installer's own bash file.

## `path_report`

It runs last in a package-mode `--install`, after `retire_commands` and the
`export PATH` note. It changes nothing, and leaves the exit status as it
was.

```text
P := PACKAGE_DIR                                   # …/lib/pythonX.Y/site-packages/openrepotools/payload
if the four directories above P are not named openrepotools, site-packages, python*, lib: say nothing more
prefix := the parent of that lib/                  # five levels above payload/
want := "$prefix/bin/openRepoTools"
first := `type -P openRepoTools` (empty means none)
if first is non-empty and link_resolve(first) == link_resolve(want): say nothing
otherwise: print the note (cli-output.md)
```

**The fixtures:**

- an older bash `openRepoTools` in a directory ahead of `<dir>` on `PATH`;
- `PIPX_BIN_DIR`'s link in a directory that differs from
  `$OPENREPOTOOLS_BIN_DIR`, and is not on `PATH`;
- no `openRepoTools` on `PATH` at all;
- pipx's link first on `PATH`, which gives no note.
