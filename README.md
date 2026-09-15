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
their history, since lane-collision-protocol Amendment 9, and `lane` and `lanes`
joined them under Amendments 18 and 11:

```sh
lane                             # the lanes, numbered — pick one and it binds
lane openRepoShape-2             # straight to that one, asking nothing
lanes                            # this checkout's lanes, and the next free one
lanes --all                      # every lane the register and the logs know
lane-start openRepoShape 2       # name the window, register the row, launch
lane-end openRepoShape-2         # close it, refusing while anything is in flight
lane-rename openRepoShape-2 openRepoShape-7   # rename it: row, log, handoff and
                                 # lanes/aliases.tsv in ONE commit
```

**A lane is renamed by one word, in one commit, and its old name resolves for
ever** — lane-collision-protocol Amendment 16, on Brett Heap's request of
2026-09-14, verbatim *"we need the ability to rename a lane"*. `lane-rename`
moves the register row's key cell, `lanes/log/<old>.md`, the handoff the row
names and `lanes/aliases.tsv` in ONE commit, refused or whole; appends a
`RENAMED` line to the log; posts one comment on every object the lane holds;
renames the tmux window and types the `/rename` into the lane's own pane. Every
reader that takes a lane name — `who`, `lanes`, `lane-start`, Rule 6
attribution, the `SessionStart` block, the name guard, and the lane field of
every old log line — resolves through that alias table, case-insensitively, so
nothing written under the old name is ever lost. `lanes --rename` is refused and
names the word: `lanes` writes nothing.

**`lane` is the one word a person needs, and it is Brett Heap's own.**
2026-09-14, verbatim: *"this is too hard for users. we need simple way to list
the lanes and then pick one to bind"* — lane-collision-protocol Amendment 18
Addendum 1. Bare, it prints the lanes NUMBERED — available first, live here
next with where each one is, bound elsewhere last — and asks ONE question.
**Available** goes through the launcher, in the lane's own recorded directory
and under its own recorded profile; **live here** ATTACHES to its window and
never starts a second process; **bound elsewhere** names where it is bound. With
no terminal on stdin it lists, suggests and asks nothing. `restart` was that
first act without the pick and left the PATH in the same breath (Addendum 2,
*"lane does all the things a user wants"*); `/restart` is the INSIDE half, a
skill, because a running session cannot `exec` a launcher over itself. `lanes`
is the same rows as a READ, narrowed inside a checkout on Brett Heap's
settlement of 2026-09-13 (*"Narrow inside a checkout"*) and ending with the
**next free position** and the `lane-start <repo> <n>` that takes it, filled in.

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

**The seed commit is the template and nothing else**: it stages the paths it
wrote, each by name, and never `git add -A`. A checkout it ADOPTS that carries
modified, deleted or untracked files the template does not name is a refusal
naming them, asked before a byte is written into it — the repository on the
other end of that push is where your unfinished work lives.

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

It places THIRTEEN files into `~/.local/bin` — `openRepoTools`, `park`, `resume`,
`status`, `lane`, `lanes`, `lane-handoff`, `lane-rename`, `lanes-edit.sh`,
`lane-start`, `lane-end`, `link-estates` and the alias table `repos.tsv` — 755,
idempotently: a
second run prints `already installed … (unchanged)` per file, one whose bytes have
drifted prints `updated at`, and one whose bytes were right and whose MODE was not
prints `(mode restored to 755)`: the mode is stamped on every artifact on every
run, whether or not the bytes moved. ALL THIRTEEN ARE IN HAND BEFORE ANY IS
PLACED, so a fetch that failed replaces nothing and names the file it could not
get. A target that is **not a regular file, or not one this user can write** — a
symlink left by the pre-move `link-estates`, a directory, a file somebody made
read-only — is a refusal in that same planning phase, naming every one of them,
what it is, and the `rm` that clears them (`rm -f` takes a read-only file: a
removal needs the directory's write bit, not the file's), as is a directory it
must create a file in and cannot: that question is put to the NEAREST ANCESTOR
THAT EXISTS, so a bin directory that is not there yet is refused for the parent
that would not take it, and a create needs a directory's search bit as well as
its write bit. A refusal creates none of those directories either. `cp` follows
a symlink, and an install through one leaves the command uninstalled and writes
these bytes into whatever it points at. Then a `13 of 13 placed in <dir>` line,
and the `export PATH=…` line if that directory is not on your `PATH`.

It also places **fourteen things that are not files in that directory**: THREE
SKILLS, `/handoff`, `/lane-swap` and `/restart`, each at
`${CLAUDE_PROFILES_HOME:-~/.claude-profiles}/shared/skills/<name>/SKILL.md`
(one write every profile reads through its own symlink) and at
`~/.claude/skills/<name>/SKILL.md` for a bare `claude` run outside the
launcher; **three command files**, `/handoff`, `/ctx` and `/swap`, at that same
pair of paths (`…/shared/commands/<name>.md` and `~/.claude/commands/<name>.md`),
because `opensoft/workBenches#74` deletes the launcher's copy; and **two merged
entries** in `~/.claude/settings.json` — `lanes-edit.sh session-start` under
`hooks.SessionStart`, and `lanes-edit.sh guard` under `hooks.UserPromptSubmit`,
which is lane-collision-protocol Amendment 12's NAME GUARD: at every prompt it
checks that the tmux window, the session's own name and the register row are
one lane, and refuses the prompt when they are not. Those merges need
`jq`, never write the file whole, write it back at mode 600, and are
idempotent by exact match on each entry's command string. That path must be a
REGULAR FILE: a symlink there — into a dotfiles checkout, say — is a refusal in
the same planning phase, because `chmod` follows a link and the merge replaces
what is at that path. The skills and the command files are 644 and that file 600
on every run — including the run that finds both entries already there and
changes no byte of them. An entry that runs
`session-start`, or one that runs `guard` as a whole argument, with a DIFFERENT
string — a second writer of one of these hooks — a
file it cannot parse, or a `hooks` that is not an object → it **refuses, prints
the exact block, and places nothing at all**, because both merges are computed
with the thirteen files in hand before either is placed. An installer that
repairs a file it does not understand is how you lose a setting you meant. Your
own `UserPromptSubmit` hooks are left exactly where they are, which is why that
arm keys on the VERB and not on the word anywhere in a path. It
never writes a profile's own `settings.json`: the launcher owns that one.

Twenty-seven artifacts, and the count is the invariant. It was sixteen until A11
Addendum 4 ruling 9 gave `--install` a command-file list and `commands/swap.md`
in it, at the same pair of paths a skill takes — because `opensoft/workBenches#74`
deletes the launcher's copy and `/swap` would otherwise be installed by nobody;
eighteen until Amendment 12 adoption act 3 added the name guard's entry; and
nineteen until lane-collision-protocol **Amendment 17** (ratified 2026-09-14)
made the swap and the handoff one act under one name, which put `lane-handoff`
on `PATH`, moved the skill's steps to `handoff` with `lane-swap` kept as an
alias naming it, and added the `/handoff` and `/ctx` command files.
`/ctx` is `/handoff --restart`: the record first, then this lane's own pane
respawned with a new session whose first prompt is that handoff's top block.
Twenty-six until **Amendment 16** (ratified the same day) put `lane-rename` on
`PATH`: a lane is renamed by one word, in one commit — the row, the object log,
the handoff and `lanes/aliases.tsv` — and its old name resolves for ever
afterwards, in every reader that takes a lane name.

Run from a checkout it copies the files beside it and needs no network and no
`gh` at all; run from stdin, as above, it fetches all of them at the same ref.
The API is tried before the raw URL, because `gh` is authenticated and works
where `raw.githubusercontent.com` is blocked.

| Variable | Default | What it is |
|---|---|---|
| `$OPENREPOTOOLS_REPO` | `opensoft/openRepoTools` | the `owner/name` to fetch from — a fork or a mirror, named once |
| `$OPENREPOTOOLS_REF` | `main` | the ref to fetch it at |
| `$OPENREPOTOOLS_BIN_DIR` | `~/.local/bin` | where `--install` puts the thirteen |
| `$AGENT_PROTOCOL_ROOT` | `~/.agents` | where `workspace.yaml` lives — the one pointer to your data |
| `$CLAUDE_PROFILES_HOME` | `~/.claude-profiles` | the profiles root `--install` places the shared skills under |
| `$LANES_WORKSTATION` | — | this workstation's name, exported by the workBenches launcher. Outside a container it defaults to `hostname -s`; **inside one with no value every writer refuses**, because a container id is not a workstation and the log is never rewritten (Amendment 11, decision 8(d)) |
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
