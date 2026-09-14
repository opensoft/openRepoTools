# openRepoTools

The commands for the estates [openRepoShape](https://github.com/opensoft/openRepoShape)
scaffolds, the lane tooling that records the work in them, and the installer
that places all of it:

```sh
park InkRouter                  # on workstation A, from any folder
resume InkRouter                # on workstation B, and the estate is back
status InkRouter                # what is in and out of sync, and changes nothing
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

`status` is the read-only view of the same estate: for the holder or root,
each member's working clone and every mounted leg, what is ahead of or behind
its origin, dirty or stashed, on a feature branch that was never pushed or
whose remote branch is gone, or checked out away from its pin. It changes
nothing and fetches nothing unless you say `--fetch`, so every answer is as of
the last fetch — the one it just made, or the one before — and it says which.
`status --fetch` runs `git fetch --prune origin` in every repository first:
the one write it ever makes — remote-tracking refs, the objects behind them
and `FETCH_HEAD`, never a local branch, tag, HEAD, index or working tree,
because the refspec is pinned on the command line rather than trusted from
config (Brett Heap's RULING of 2026-09-11, "next layer: --fetch", on top of
his RULING of 2026-09-10, "start with the local status layer"). A FORK is
read against what it was forked from (his RULING of the same day, "next
layer: fork against upstream"): with a remote named `upstream`,
`origin/<branch>` against `upstream/<branch>` from local refs, and `--fetch`
fetches upstream too; with none, and only under `--fetch`, an origin on
github.com is asked about once with `gh api`, and a fork is a finding naming
the parent and the `git remote add upstream …` that makes the drift readable
here. THE SHAPE PIN is read too (his RULING of the same day, "next layer:
shape-pin drift"): every root and holder carries `contracts/shape-pin.yaml`,
the openRepoShape commit its copied shape files came from and a sha256 per
copy; a copy whose digest differs is drift, whose exit is upstream and never a
re-digest, a `shape:` mirror naming another commit (or missing) is out of
step, and the pin is compared with the source's default branch — from a clone
of the source under your projects directory, found by its origin the way
`--repo` finds an estate, or else under `--fetch` from GitHub, once per pin —
naming `update-shape.py check --root <root>` as the exit when it has fallen
behind; "currency not read" in the note means neither source answered.
Those two questions to GitHub, the fork and the pin, are the only uses of `gh`
in the three estate commands; the installer has its own. THE PARKED RECORD is
read against disk too (his RULING of the same day, "next layer: parked record
against disk"): the record `park` wrote into the workspace repository that
`~/.agents/workspace.yaml` names, found by the estate's id as `park` files it
and then by its folder name as `resume` looks it up, gives a finding for a
recorded feature with no worktree here (`resume <Name>` brings it back; with
`--no-push`, a `pushed:` that is missing or neither true nor false, no parked
commit named for that leg, a leg given no role at all, a role this shape has no
place for — unmounted, or one `resume` maps only in the other shape or in
neither — or no leg at all, only the workstation that parked it can — and
where that role is really another shape's, only a checkout of that shape,
where it is neither shape's, none; with the branch gone from origin, which
only `--fetch` settles, `resume` refuses the WHOLE feature as gone from origin
and the exits are the record's own entry where the feature landed or a push
from the workstation that parked it; with a `- branch:` or a `- role:` left by
the record's KEY ORDER where the loader reads neither — it shuts the
`features:` list at the next key at project indent and a feature's `legs:`
list at the next key at feature indent — the exits are putting that key back,
which is yours to do, and a re-park only from the workstation that has the
feature, since a park anywhere else rewrites the block without those lines;
and where `git worktree list` still holds a
registration that is no longer a worktree, a `worktree prune` — after a
`worktree unlock` if it is locked, with any directory it leaves behind moved
aside — has to clear it first; and where anything else sits at the path both
verbs compute for that leg — a directory, a file, a worktree of another
branch — `resume` refuses the whole feature for it, before it reads origin
and without overwriting a path it did not create, so moving that aside is
yours first: a `git worktree move` where git holds it as a worktree and a
plain `mv` where it does not, with the `unlock` a locked registration wants
in front of either and the `prune` a dead one wants beside the `mv`), a
worktree whose tip moved on from, fell behind (by more than the WIP commits
`resume` itself un-committed), or diverged from the parked commit — or a record
naming no parked commit to compare it with — a recorded branch this repository
has no `origin/<branch>` for, a leg parked with `--no-push` or with a `pushed:`
that is missing or unreadable, a leg the record gives no role or a role this
shape has no place for, a feature the record lists no leg for, a worktree on a
recorded branch that is not at the path BOTH verbs compute for that leg —
`<worktree_root>/<branch>`, the leg's own mount under it in a three-leg root,
read out of `$SPECKIT_GIT_WORKTREE_ROOT`, this checkout's `git-config.yml`, or
the shape's own default — which `resume` refuses the whole feature for and
`park` never parks, leaving a `git worktree move` of yours as the exit — except
where no move works: the leg's own checkout, a leg declared `path: "."`, and a
symlink anywhere in the computed path's own parents, each of which says so and
names the component — and a worktree the record does not know, which was never
parked. No config, or no record, is a note.
That is all five layers: the local layer, `--fetch`, the fork, the pin and
the record.

## The lane tooling

`lane-start`, `lane-end`, `lanes-edit.sh` and `link-estates` are here too, with
their history, since lane-collision-protocol Amendment 9:

```sh
lane-start openRepoShape 2       # name the window, register the row, launch
lane-end openRepoShape-2         # close it, refusing while anything is in flight
lanes-edit.sh who --lane <lane>  # what that lane holds
```

They record who is working on what across an estate — the register
`lanes/LANES.md`, the per-lane object logs, the handoffs — and all of that is
**data, in the person's own workspace repository**, which is where Amendments 4
and 5 put it and where it stays. What moved here is the CODE. A `<user>-wip` is
a private repository whose own rules file says "No secrets and no code", nobody
would look inside somebody else's for a command, and until this move the four
helpers existed in exactly one place in the world: one person's private
repository. `docs/README-lanes.md` is the manual.

Every one of them finds that data through `$AGENT_PROTOCOL_ROOT/workspace.yaml`
— `repository:` and `path:`, the same pointer file `resume` and `status`
already read — and never from its own location on disk. Failing to find it is a
refusal naming `openRepoTools wip init`, never a guess.

## `openRepoTools wip init`

The one act that creates the workspace those commands read:

```sh
openRepoTools wip init
```

It asks you **at most one question**, and only where an administrator has to
create the repository for you — and then it prints the exact commands, every
value already filled in. Everything else is derived: your login from
`gh api user` lowercased, the organisation from this toolset's own default, the
team from `gh api /user/teams` where exactly one matches (and where none or
several do, `--team` is dropped from what it runs AND from what it prints, with
one line saying why — a placeholder you have to fill is a question wearing a
different hat).

Then it clones the repository, seeds it from openRepoShape's
`templates/workspace-root/` at the commit pinned in
`contracts/openreposhape-pin.yaml`, and pushes one commit to `main` — **which is
also the check that matters**: a new repository is inside the organisation's
PR-only ruleset until an administrator excludes it, and until it is, every
register write will be refused by that gate. Better to meet it here than at
your first `lane-start` — a refused push is exit 2 naming the ruleset, with
the clone and the commit left where they are, so the re-run after an
administrator acts has only to push. Last it writes `~/.agents/workspace.yaml`
and runs `link-estates`.

**Idempotent**: a workstation that already has a workspace does nothing at all,
decided by a file test and not a network call. Exit 0 is done or already done;
exit 2 is a refusal. `--dry-run` rehearses and writes nothing. It scaffolds no
product repository — that is `openRepoShape`'s, the standard's front door, and
nothing here touches it.

## Install

**From nothing, on a new workstation, it is two lines** — and neither of them
is one of this repository's (lane-collision-protocol Amendment 9(e)):

```sh
gh repo clone opensoft/workBenches && cd workBenches && ./setup.sh
pclaude run <profile> --lane <repo>-<n>
```

`./setup.sh` runs `openRepoTools --install` and then `openRepoTools wip init`
for you, each best-effort, so neither is a line you have to know to type. Its
two preconditions are `gh auth login` — `wip init` derives your login from
`gh api user` — and `~/.local/bin` on your `PATH`, which that script exports
and which needs a restarted terminal. `pclaude list` names the profiles;
`<repo>-<n>` is the lane naming rule.

On a host that has this toolset without workBenches, the same two acts by
hand, in this order, because the second refuses where no openRepoTools is
installed:

```sh
curl -fsSL https://raw.githubusercontent.com/opensoft/openRepoTools/main/openRepoTools | bash -s -- --install
openRepoTools wip init
```

or, inside an organisation whose policy blocks raw downloads, the same bytes
through the authenticated API:

```sh
gh api repos/opensoft/openRepoTools/contents/openRepoTools \
    -H 'Accept: application/vnd.github.raw' | bash -s -- --install
```

It places NINE files into `~/.local/bin` — `openRepoTools`, `park`, `resume`,
`status`, `lanes-edit.sh`, `lane-start`, `lane-end`, `link-estates` and the
alias table `repos.tsv` — 755, idempotently: a second run prints
`already installed … (unchanged)` per file, and one whose bytes have drifted
prints `updated at`. ALL NINE ARE IN HAND BEFORE ANY IS PLACED, so a fetch that
failed replaces nothing and names the file it could not get. A target that is
**not a regular file** — a symlink left by the pre-move `link-estates`, a
directory — is a refusal in that same planning phase, naming every one of them,
what it is, and the `rm` that clears them: `cp` follows a symlink, and an
install through one leaves the command uninstalled and writes these bytes into
whatever it points at. Then a `9 of 9 placed in <dir>` line, and the
`export PATH=…` line if that directory is not on your `PATH`.

It also places **three things that are not files in that directory**: the
`/lane-swap` skill at
`${CLAUDE_PROFILES_HOME:-~/.claude-profiles}/shared/skills/lane-swap/SKILL.md`
(one write every profile reads through its own symlink) and at
`~/.claude/skills/lane-swap/SKILL.md` for a bare `claude` run outside the
launcher, and **one merged entry** under `hooks.SessionStart` in
`~/.claude/settings.json`. That merge needs `jq`, never writes the file whole,
writes it back at mode 600, and is idempotent by exact match on the entry's
command string. An entry that runs `session-start` with a DIFFERENT string — a
second writer of this very hook — a file it cannot parse, or a `hooks` that is
not an object → it **refuses, prints the exact block, and places nothing at
all**, because the merge is computed with the nine files in hand before any of
them is placed. An installer that repairs a
file it does not understand is how you lose a setting you meant. It never
writes a profile's own `settings.json`: the launcher owns that one.

Twelve artifacts, and the count is the invariant.

Run from a checkout it copies the files beside it and needs no network and no
`gh` at all; run from stdin, as above, it fetches all of them at the same ref.
The API is tried before the raw URL, because `gh` is authenticated and works
where `raw.githubusercontent.com` is blocked.

| Variable | Default | What it is |
|---|---|---|
| `$OPENREPOTOOLS_REPO` | `opensoft/openRepoTools` | the `owner/name` to fetch from — a fork or a mirror, named once |
| `$OPENREPOTOOLS_REF` | `main` | the ref to fetch it at |
| `$OPENREPOTOOLS_BIN_DIR` | `~/.local/bin` | where `--install` puts the nine |
| `$AGENT_PROTOCOL_ROOT` | `~/.agents` | where `workspace.yaml` lives — the one pointer to your data |
| `$CLAUDE_PROFILES_HOME` | `~/.claude-profiles` | the profiles root `--install` places the shared skill under |
| `$PROJECTS_DIR` | `~/projects` | where `wip init` clones your workspace repository |

`openRepoTools --version` prints `openRepoTools (<repo> @ <ref>)`. There is no
version number here, for the reason openRepoShape has none: the identity is a
commit.

## Using them

`park --help`, `resume --help` and `status --help` are the reference, and
openRepoShape's README has the whole of "Carrying in-flight work to another
workstation". In short:

```sh
park                            # the estate around the current directory
park InkRouter                  # a folder under your projects directory
park --all                      # every estate under it, unasked (also -a)
park --repo <owner>/<name>      # the estate of a clone you ALREADY have
park InkRouter --dry-run        # rehearse; writes nothing
resume InkRouter --workspace <owner>/<your-wip-repo>   # the FIRST time here
resume InkRouter -- --feature 001-a-thing              # flags for the extension
status                          # the estate around you; outside one, every estate
status InkRouter                # one estate, read-only, as of the last fetch
status --fetch InkRouter        # ask origin first: the one write status makes
```

`<Name>` is a folder under your projects directory: `~/projects/<Name>`, then
`~/Projects/<Name>` — people spell it both ways — or wherever `$PROJECTS_DIR`
points. A FAMILY folder (`<Name>/<Name>/family.yaml`) wins over a standalone
root (`<Name>/project.yaml`) of the same name, because the holder is what
drives the members. With no `<Name>` the estate around the current directory is
parked. With no estate around it either, `park` lists every estate it finds
under your projects directory and ASKS whether to park them all — `y` runs the
sweep, anything else parks nothing, and where stdin is not a terminal nothing
is asked: it refuses and names `--all`. `park --all` (or `park -a`) is that
same sweep without the question, from anywhere: each estate in name order,
continuing past a refusal, then one summary (Brett Heap's RULING of
2026-09-10, superseding his openRepoShape #91 ruling of the same day, under
which the bare form swept unasked). A root with no Speckit git overlay is
SKIPPED in that sweep rather than run and failed: it is named, counted apart
(`…, 4 skipped (no overlay)`) and left out of the exit code, under Brett
Heap's RULING of the same day on openRepoShape #92 — a root nobody installed
the overlay in is not a park that FAILED. `park <Name>` on that same root
still relays its own `make park` refusal, which names `setup-openspeckit`.
`resume` has no `--all`, and keeps that old refusal for its own bare form —
rebuilding every estate on a fresh machine by accident is the opposite risk
from failing to park the one you meant.

**TWO things in this toolset write a file outside a repository, and both write
the same one**, `~/.agents/workspace.yaml`, both only on a machine that has
none. `resume --workspace <owner>/<repo>` writes it because you named the
repository; `openRepoTools wip init` writes it because you asked for the
repository by running it (lane-collision-protocol Amendment 9(c) step 9).
Neither ever overwrites one that is already there. Nothing else in this toolset
writes outside a repository at all.

`status` reads and changes nothing, and takes no lock while it reads. Exit 0
means every repository read is in sync and clean as of the last fetch; exit 1
means findings were printed — read them, one line per repository, as you
would `park`'s report — and exit 2 is a refusal. Its bare form outside every
estate reads them all WITHOUT asking, because nothing here writes; `status
--all` (or `-a`) says the same from anywhere. `status --fetch` asks origin in
every repository first and says what moved; a fetch that fails is a finding
on that row, and the row is then read as of the last fetch that worked. An
https credential prompt fails and is reported; an ssh host-key or passphrase
prompt is ssh's own and still blocks, so run `--fetch` where ssh is already
non-interactive.

Windows: all four files are bash, and there is no PowerShell twin. On Windows
the way in is WSL2, exactly as it is for openRepoShape's `setup.sh`.

## The dependency direction

**Tools depend on the shape; the shape depends on nothing.** This repository
pins the openRepoShape commit its tests were verified against, as a submodule
at `upstream/openRepoShape` recorded in `contracts/openreposhape-pin.yaml`.
openRepoShape pins this repository NOWHERE, and knows of it only through one
pointer line its own `--install` prints — text, not a fetch. The reverse would
make the standard unbuildable without its tools.

MOUNTED, NOT COPIED. `tests/test_park_resume_commands.py` builds real estates
out of EIGHT of the standard's own files — the two root Makefiles, their two
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
# NOW EDIT contracts/openreposhape-pin.yaml: that number into
# `digests.tree_sha256`, the commit into `commit:`. Only then:
git add contracts/openreposhape-pin.yaml upstream/openRepoShape
git commit
```

**The edit comes before the `git add`, and the block is in that order for a
reason.** Staging first and editing after stages the moved gitlink with the OLD
pin file — and that is invisible where you are standing, because
`tests/test_upstream_pin.py` reads the pin out of the WORKING TREE and the
gitlink out of `git ls-tree HEAD`: green in your checkout, red in CI, which is
the wrong way round. The pin and the gitlink are one fact in two places. The
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
each of the four bash files with `/bin/bash -n` — bash 3.2, the last GPLv2
release and what Apple still ships — because that is the claim the suite itself
cannot make.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
