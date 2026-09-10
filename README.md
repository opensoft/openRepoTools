# openRepoTools

Two commands for the estates [openRepoShape](https://github.com/opensoft/openRepoShape)
scaffolds, and the installer that places them:

```sh
park InkRouter                  # on workstation A, from any folder
resume InkRouter                # on workstation B, and the estate is back
```

`park` commits, pushes and RECORDS every open feature of one estate, so another
workstation can take the work up. `resume` clones or fast-forwards that estate
here, bootstraps it, places a family's members beside the holder, and recreates
those features.

**They add no mechanics.** They FIND THE ESTATE and run its own `make park` /
`make resume` — the family holder's, which fans out to each member's, or the
assembly root's — and those targets run the Speckit git extension's `park.sh`
and `resume.sh`, which are the one implementation of the WIP commit, the push,
the record, the `git worktree add` and the soft reset (ruled 2026-09-09,
openRepoShape #77). What these two files add is finding the estate, rebuilding
what is not here, and saying out loud what did NOT travel and why none of it is
theirs to touch.

`openRepoTools` itself installs and does nothing else. It has no verb: the
standard's front door is `openRepoShape`, which scaffolds projects and stays
there.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/opensoft/openRepoTools/main/openRepoTools | bash -s -- --install
```

or, inside an organisation whose policy blocks raw downloads, the same bytes
through the authenticated API:

```sh
gh api repos/opensoft/openRepoTools/contents/openRepoTools \
    -H 'Accept: application/vnd.github.raw' | bash -s -- --install
```

It places THREE files into `~/.local/bin` — `openRepoTools`, `park` and
`resume` — 755, idempotently: a second run prints `already installed …
(unchanged)` per file, and one whose bytes have drifted prints `updated at`.
ALL THREE ARE IN HAND BEFORE ANY IS PLACED, so a fetch that failed replaces
nothing and names the file it could not get. Then a `3 of 3 placed in <dir>`
line, and the `export PATH=…` line if that directory is not on your `PATH`.

Run from a checkout it copies the files beside it and needs no network and no
`gh` at all; run from stdin, as above, it fetches all three at the same ref.
The API is tried before the raw URL, because `gh` is authenticated and works
where `raw.githubusercontent.com` is blocked.

| Variable | Default | What it is |
|---|---|---|
| `$OPENREPOTOOLS_REPO` | `opensoft/openRepoTools` | the `owner/name` to fetch from — a fork or a mirror, named once |
| `$OPENREPOTOOLS_REF` | `main` | the ref to fetch it at |
| `$OPENREPOTOOLS_BIN_DIR` | `~/.local/bin` | where `--install` puts the three |

`openRepoTools --version` prints `openRepoTools (<repo> @ <ref>)`. There is no
version number here, for the reason openRepoShape has none: the identity is a
commit.

## Using them

`park --help` and `resume --help` are the reference, and openRepoShape's README
has the whole of "Carrying in-flight work to another workstation". In short:

```sh
park                            # the estate around the current directory
park InkRouter                  # a folder under your projects directory
park --repo <owner>/<name>      # the estate of a clone you ALREADY have
park InkRouter --dry-run        # rehearse; writes nothing
resume InkRouter --workspace <owner>/<your-wip-repo>   # the FIRST time here
resume InkRouter -- --feature 001-a-thing              # flags for the extension
```

`<Name>` is a folder under your projects directory: `~/projects/<Name>`, then
`~/Projects/<Name>` — people spell it both ways — or wherever `$PROJECTS_DIR`
points. A FAMILY folder (`<Name>/<Name>/family.yaml`) wins over a standalone
root (`<Name>/project.yaml`) of the same name, because the holder is what
drives the members. With no `<Name>` the estate around the current directory is
used; with no estate around it either, `park` REFUSES and lists the estates it
found — nothing is parked by guess.

`resume --workspace <owner>/<repo>` is the only thing in this toolset that
writes a file outside a repository (`~/.agents/workspace.yaml`), and it writes
it only on a machine that has none and only because you named the repository.

Windows: all three files are bash, and there is no PowerShell twin. On Windows
the way in is WSL2, exactly as it is for openRepoShape's `setup.sh`.

## The dependency direction

**Tools depend on the shape; the shape depends on nothing.** This repository
pins the openRepoShape commit its tests were verified against, as a submodule
at `upstream/openRepoShape` recorded in `contracts/openreposhape-pin.yaml`.
openRepoShape pins this repository NOWHERE, and knows of it only through one
pointer line its own `--install` prints — text, not a fetch. The reverse would
make the standard unbuildable without its tools.

MOUNTED, NOT COPIED. `tests/test_park_resume_commands.py` builds real estates
out of seven of the standard's own files — the two root Makefiles, their
`.gitignore`s, the two `bootstrap.py`s, `siblings.py` and
`scripts/repo_shape.py` — and a submodule hands those tests the standard's real
bytes at the pinned commit rather than copies here that could have been edited
into agreeing with a broken expectation.

`tests/test_upstream_pin.py` is what says the pin file and the gitlink still
agree. Four of its checks need no submodule at all — the gitlink is read out of
`git ls-tree HEAD` and nothing imports from the checkout — so the lockstep
check bites in a clone that never materialized it.

### Bumping the pin

```sh
git -C upstream/openRepoShape fetch origin
git -C upstream/openRepoShape checkout <40 hex on openRepoShape's main>
python3 -c "import sys; sys.path.insert(0, 'upstream/openRepoShape/scripts'); from repo_shape import tree_digest; print(tree_digest('upstream/openRepoShape', 'HEAD'))"
git add contracts/openreposhape-pin.yaml upstream/openRepoShape
```

Write that number into `digests.tree_sha256` and the commit into `commit:`, and
commit the pin and the gitlink TOGETHER — they are one fact in two places. The
digest is recomputed with the PINNED CHECKOUT'S OWN `scripts/repo_shape.py`
(`sorted-ls-tree-r-v1`), so this repository carries no copy of the standard's
code and the number is checked against the pinned commit's own definition of
it. **Never adjust the digest to make the test pass** — that records the local
checkout as the upstream. And never pin a commit that is not on
openRepoShape's `main`: that repository squash-merges, so a branch commit is
orphaned and the next person's fetch of it 404s.

## Tests

```sh
git clone --recurse-submodules https://github.com/opensoft/openRepoTools.git
cd openRepoTools && python3 -m pytest tests -q
```

From a clone that already exists, `git submodule update --init
upstream/openRepoShape` first. **Without the submodule the suite SKIPS rather
than fails**, naming that command: a fork's first `pytest` going red on a
missing submodule is a fork nobody finishes. The estate tests need `bash`,
`make` and `git`.

Nothing here reaches the network or creates a real repository. Every remote is
a bare repository in a temporary directory, every `$HOME` is a temporary
directory, and the fetch path is answered by a fake `gh` with a `curl` that
refuses.

CI runs the suite on ubuntu, windows and macOS, plus one ubuntu job that checks
out WITHOUT submodules to prove the skip path exits 0. The macOS job parses
each of the three bash files with `/bin/bash -n` — bash 3.2, the last GPLv2
release and what Apple still ships — because that is the claim the suite itself
cannot make.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
