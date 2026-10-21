# Contract: `pyproject.toml` and the wheel

## `pyproject.toml` (a new root file)

These are the declarations a test holds. Comments in the file follow the
model's style and give the reasons.

```toml
[build-system]
requires = ["hatchling==1.27.0"]
build-backend = "hatchling.build"

[project]
name = "openrepotools"
dynamic = ["version"]
requires-python = ">=3.9"
license = "Apache-2.0"
license-files = ["LICENSE"]
dependencies = []
# no `readme` key: README.md goes to the assembly root at the cutover

[project.scripts]
openRepoTools = "openrepotools.cli:main"

[tool.hatch.version]
path = "src/openrepotools/_release.py"

[tool.hatch.build.targets.wheel]
packages = ["src/openrepotools"]

[tool.hatch.build.targets.wheel.force-include]
# the 24 entries below, each "<P>" = "openrepotools/payload/<P>"
```

- The `description`, `authors`, `classifiers` and `[project.urls]` keys are
  allowed, as the model has them.
- No other table changes what the wheel holds.

**Held by `tests/test_package.py`:**

- `dependencies == []`;
- `[project.scripts]` is exactly `{"openRepoTools": "openrepotools.cli:main"}`;
- there is no `readme` key;
- `requires` is `["hatchling==1.27.0"]`, the same pin as the build lock's
  hatchling;
- `requires-python == ">=3.9"`;
- the license and `license-files` are as above;
- the force-include keys are exactly `payload_names` plus the pin;
- each value is `openrepotools/payload/<key>`.

## The force-include map and the committed modes

| # | Path `<P>` | Mode at this branch's head |
| --- | --- | --- |
| 1 | `openRepoTools` | `100755` |
| 2 | `park` | `100755` |
| 3 | `resume` | `100755` |
| 4 | `status` | `100755` |
| 5 | `lane` | `100755` |
| 6 | `lanes` | `100755` |
| 7 | `lane-handoff` | `100755` |
| 8 | `lane-rename` | `100755` |
| 9 | `lanes-edit.sh` | `100755` |
| 10 | `lane-start` | `100755` |
| 11 | `lane-end` | `100755` |
| 12 | `link-estates` | `100755` |
| 13 | `repos.tsv` | `100644` |
| 14 | `claude-current` | `100755` |
| 15 | `claude-restart-check` | `100755` |
| 16 | `lanes-index` | `100755` |
| 17 | `lane-worktrees` | `100755` |
| 18 | `skills/handoff/SKILL.md` | `100644` |
| 19 | `skills/lane-swap/SKILL.md` | `100644` |
| 20 | `skills/restart/SKILL.md` | `100644` |
| 21 | `commands/handoff.md` | `100644` |
| 22 | `commands/ctx.md` | `100644` |
| 23 | `commands/swap.md` | `100644` |
| 24 | `contracts/openreposhape-pin.yaml` | `100644` |

Rows 1 to 23 are `payload_names` in its own order. The test derives them
from the bash file and never from this table. The table records what the
file holds today.

## The wheel's members

```text
openrepotools/__init__.py
openrepotools/cli.py
openrepotools/_release.py
openrepotools/payload/<P>                      # each of the 24
openrepotools-<version>.dist-info/METADATA
openrepotools-<version>.dist-info/WHEEL
openrepotools-<version>.dist-info/RECORD
openrepotools-<version>.dist-info/entry_points.txt
openrepotools-<version>.dist-info/licenses/LICENSE
```

The wheel holds nothing else.

## The wheel checks

The `package` job and the release build both run these. Each fails the job,
naming every problem.

1. **One file.** The two builds are one file (`cmp`).
2. **The payload.** Each `openrepotools/payload/<P>`:
   - is byte-identical to `git show <commit>:<P>`;
   - has the commit's whole mode, as `git ls-tree <commit> -- <P>` records
     it: `100755` is a regular file at `0755` and `100644` a regular file at
     `0644`, with no other bit, so no other file type and no setuid, setgid
     or sticky bit (#278). Hatchling 1.27.0's reproducible build normalises
     the permission bits to `0755` or `0644` (clarifications N4) and leaves
     the file type as the file has it, so a regular file keeps its type
     (`hatchling/builders/utils.py:96-110`, `:122-127`). pip makes a member
     executable only when it is typed a regular file
     (`pip/_internal/utils/unpacking.py:111-115`, pip 26.2.1), so a `0755`
     member with no file type is not the commit's mode either.
3. **The modules.** Each `openrepotools/<name>.py` other than `_release.py`
   is byte-identical to `src/openrepotools/<name>.py` at the commit.
4. **The stamp.**
   - In the `package` job, `openrepotools/_release.py` is byte-identical to
     the committed file.
   - In the release build, it is the committed file with exactly its five
     assignment lines changed, to the release's values ([stamp.md](stamp.md)).
5. **The metadata.** The `.dist-info/` names are exactly the five above, and
   `licenses/LICENSE` is byte-identical to `git show <commit>:LICENSE`.
   - This check, and not hatchling, is what makes a missing `LICENSE`
     fatal. Hatchling 1.27.0's `license-files` glob raises nothing for a
     pattern that matches no file (`hatchling/metadata/core.py:757-770`).
6. **Nothing else.** No member falls outside the list above.

**When `OPENREPOTOOLS_TEST_WHEEL` names a built wheel**, `tests/test_package.py`
runs checks 2, 3, 5 and 6 against it, and compares its payload members with
`payload_names` plus the pin in both directions. Its check 2 holds a member's
permission bits, setuid, setgid and sticky included, to `0755` or `0644`, and
reads no file type, so it refuses a subset of what the two workflows refuse.

## Modes at run time

Nothing at run time depends on the wheel's modes:

- the entry module runs `bash <payload>/openRepoTools`;
- `--install` sets 755 on each command it places, and 644 or 600 on the
  rest (design.md Decision 12).
