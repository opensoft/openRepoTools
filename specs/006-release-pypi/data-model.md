# Data Model: 006-release-pypi

This feature stores nothing new, beyond the stamp. Its entities are files,
directory layouts and the state of a run. The receipt's format does not
change. Each entity names its fields, its validation rules and, where it has
them, its states.

## The stamp: `src/openrepotools/_release.py`, `openrepotools/_release.py` in the wheel

| Field | Unstamped (committed) | Stamped (release build only) |
| --- | --- | --- |
| `VERSION` | `0.0.0` | `X.Y.Z`, or `X.Y.ZrcN`; digits with no leading zeros; not `0.0.0` |
| `TAG` | empty | exactly `v<VERSION>` |
| `COMMIT` | empty | 40 lowercase hex digits (`is_lower_hex 40`), the tag's commit |
| `DIGEST` | empty | 64 lowercase hex digits (`is_lower_hex 64`), that commit's `sorted-ls-tree-r-v1` tree digest |
| `REPOSITORY` | empty | an owner/name slug (`is_slug`), the release run's `$GITHUB_REPOSITORY` |

**The file's shape**: one module docstring, then the five assignment lines in
the order above. [contracts/stamp.md](contracts/stamp.md) gives the grammar.

**States**:

```text
           release build's writer (five lines, once each)
unstamped ───────────────────────────────────────────────▶ stamped
    │                                                          │
    └────────── anything else the reader sees ─────────────────┘
                             ▼
                          broken  (always refused; never read in part)
```

- **unstamped**: `TAG`, `COMMIT` and `DIGEST` are all empty, `VERSION` is
  `0.0.0` and `REPOSITORY` is empty.
- **stamped**: every field is set and passes its rule in the table.
- **broken**: anything else. That includes a partial stamp (some of `TAG`,
  `COMMIT` and `DIGEST` set), a malformed field, an unreadable file, a
  carriage return, and a missing, repeated or unknown name. It also includes
  an unclosed docstring, and a docstring line that hatch's version pattern
  could take.

**Readers**: bash's `stamp_read`, which is the only one at run time, and
hatch's version source, at build time. The two must read the same `VERSION`
(FR-013).

## The payload list and the force-include map

- **The payload list**: the output of `payload_names` in `openRepoTools`. It
  is the 17 `INSTALLABLES`, then `skills/<n>/SKILL.md` for the 3 `SKILLS`,
  then `commands/<n>.md` for the 3 `COMMANDS`, in that order: 23 paths.
- **The force-include map**: those 23 paths plus
  `contracts/openreposhape-pin.yaml`, 24 in all. Each key `<P>` maps to the
  value `openrepotools/payload/<P>`.
- **Rule**: the map's keys, the built wheel's `openrepotools/payload/`
  members and the payload list plus the pin are one set, compared in both
  directions (FR-007).
- **Modes**: each entry has the commit's mode. At this branch's head that is
  16 at `100755` (the sixteen commands) and 8 at `100644` (`repos.tsv`, the
  three skills, the three command files and the pin). The full list is in
  [contracts/wheel.md](contracts/wheel.md).

## The package layout, installed

```text
<prefix>/                                  # a pipx venv, or pip's user base
├── bin/openRepoTools                      # pip's console script for openrepotools.cli:main
├── pipx_metadata.json                     # pipx's own file (its existence only is read)
├── pyvenv.cfg                             # present in every venv
└── lib/pythonX.Y/site-packages/openrepotools/
    ├── __init__.py
    ├── cli.py
    ├── _release.py                        # the stamp
    └── payload/                           # PACKAGE_DIR in package mode
        ├── openRepoTools  park  resume  …  lane-worktrees  repos.tsv
        ├── skills/<n>/SKILL.md
        ├── commands/<n>.md
        └── contracts/openreposhape-pin.yaml
```

- **Package mode** holds when the resolved directory of `$SELF` is named
  `payload`, its parent is named `openrepotools`, and that parent holds a
  regular `_release.py`.
- **`<prefix>`** is five directories above `payload/`, the parent of `lib/`
  (research R7).

## pipx's link

| Field | Meaning |
| --- | --- |
| `PIPX_LINK` | `<dir>/openRepoTools`, the symbolic link |
| `PIPX_VENV` | the canonical `<venv>`, which is the parent of the resolved file's `bin/` |
| `PIPX_PAYLOAD` | the canonical `<venv>/lib/python*/site-packages/openrepotools/payload` that holds a regular `openRepoTools` |

**Match** (all of these):

- `<dir>/openRepoTools` is a symbolic link;
- it resolves, within 40 hops and with no cycle, to a regular file named
  `openRepoTools` in a directory named `bin`;
- `<venv>/pipx_metadata.json` is a regular file;
- some `<venv>/lib/python*/site-packages/openrepotools/payload/openRepoTools`
  is a regular file.

**The other kinds of `<dir>/openRepoTools`** each take one outcome in the
planning phase:

| What is at `<dir>/openRepoTools` | Outcome |
| --- | --- |
| nothing, or this installer's regular file | placed as today |
| pipx's link | skipped; the skip line is printed; no receipt row |
| a venv-looking link (it resolves to `…/bin/openRepoTools` whose parent holds `pyvenv.cfg`, but fails the match) | refused, with no `rm` advice; names `pipx reinstall openrepotools` |
| pip's console script (a regular file; shebang and import rule) | refused (design.md Decision 8) |
| any other link, a directory, or an unwritable file | refused as today, with today's `rm -f` advice |

## An install run's result

| Quantity | Full install | With pipx's link |
| --- | --- | --- |
| files placed in `<dir>` | 17 | 16 (1 left to pipx) |
| skill files (3 skills × 2 paths) | 6 | 6 |
| command files (3 × 2 paths) | 6 | 6 |
| hook entries | 2 | 2 |
| artifacts placed | 31 | 30 |
| receipt rows (files + skill files + command files) | 29 | 28 |

**The count line** takes one of three forms (see
[contracts/cli-output.md](contracts/cli-output.md)): today's form, pipx's
own environment, or another source beside pipx's link.

## A release

| Field | Rule |
| --- | --- |
| tag | annotated, `vX.Y.Z` (or `vX.Y.ZrcN` for a TestPyPI rehearsal); never moved, deleted or reused |
| tag message | `openRepoTools vX.Y.Z`, a paragraph, `Tagged on Brett Heap's word (<exact UTC second>, "<words>")`, `Lane: <lane>` |
| commit | on `main` or `release/vX.Y` |
| tests.yml runs on the commit | all finished; the newest succeeded; each ran the four jobs |
| tree digest | `sorted-ls-tree-r-v1`, the same locally and from the forge |
| notes | `docs/release-notes/vX.Y.Z.md`, in the spec leg after the cutover |
| GitHub Release | created by hand from the notes file, after PyPI serves the version |

**States of a version on the indexes**:

```text
tagged ─▶ built (two builds, one file) ─▶ on TestPyPI ─▶ install-checked ─▶ on PyPI ─▶ Released (GitHub)
             │ any gate fails: nothing uploaded       (pre-release stops at install-checked)
```

## A release branch

- **Name**: `release/vX.Y`, cut at `vX.Y.0` right after the tag.
- **What reaches it**: a fast-forward or a merge of `main` while `main`
  holds only that patch line's work. Otherwise a PR of
  `git cherry-pick -x <squash commit>`. One HOLD may be open at a time.
- **Patch tags**: `vX.Y.Z` with Z above 0, once that commit's `tests.yml`
  runs are all finished and the newest succeeded.

## A release run (`release.yml`)

| Job | Granted | Environment | Runs on |
| --- | --- | --- | --- |
| `build` | `contents: read`, `actions: read` | none | every dispatch |
| `testpypi` | exactly `id-token: write`, `actions: read`, `contents: read` | `testpypi` | a `v*` tag only |
| `install` | `contents: read` | none | every dispatch: on the build's wheel for a branch, from TestPyPI for a tag |
| `pypi` | exactly `id-token: write`, `actions: read`, `contents: read` | `pypi` | a `v*` tag of a final `X.Y.Z` only |

**Outputs of `build`**: the wheel's file name, its sha256, the tree digest,
and `final`. `final` is `true` only for a final `X.Y.Z`, and the `pypi`
job's condition reads it. The others are what each later job checks
against.

**The environments**, which Brett Heap creates: each names a required
reviewer, and each has a deployment limit of exactly one rule, the tag
pattern `v*`.
