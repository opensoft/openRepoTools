# Working in openRepoTools

Three estate commands, `park`, `resume` and `status`; the lane tooling
`lanes-edit.sh`, `lane-start`, `lane-end` and `link-estates`, which came here
with their history under lane-collision-protocol Amendment 9; and the
`openRepoTools` that places all twelve files and creates the workspace they read.
**The verbs add no mechanics.**
They find the estate and run its own `make park` / `make resume`, which run
the Speckit git extension's scripts — one implementation, ruled 2026-09-09
(openRepoShape #77, ruling 1). Never hand-roll the WIP commit, the push, the
`git worktree add` or the soft reset because something refused: relay the
refusal. `status` is the read-only view of the same estate, and runs nothing.

The shape itself is [openRepoShape](https://github.com/opensoft/openRepoShape),
and this repository pins the commit its tests were verified against. Read that
repository's `AGENTS.md` for the Make targets (`make park`, `make resume`) and
everything about a project's layout; what follows is only what changes when a
person is driving the two INSTALLED commands.

The lane tooling answers to a different document — the lane collision protocol
at `$AGENT_PROTOCOL_ROOT/protocols/lane-collision-protocol.md` and its
amendments — and `docs/README-lanes.md` is its manual. **The code is here; the
data is not.**

**A LANE HAS ONE BINDING** (Amendment 18, in force 2026-09-14): the `host`,
`container` and `window` of its last `STARTED`/`RESUMED`, read back by
`lanes-edit.sh binding <lane>`. **Liveness is pronounced only from inside that
binding's own host and container** — a pid does not cross a pid namespace, so
from another container on the same machine a binding is UNKNOWN and never dead,
whatever `kill -0` says; the one exception is a window gone from a tmux server
the two share. A second place ASKS (`--request-handoff`, or `lanes-edit.sh
request-handoff`) and waits; only `--force`, a second invocation and never
automatic, releases a binding on its holder's behalf. `LANES_HOST`, `LANES_OS`
and `LANES_CONTAINER` are the launcher's to export beside `LANES_WORKSTATION`.

Every one of the four finds the register, the logs and the
handoffs through `$AGENT_PROTOCOL_ROOT/workspace.yaml`'s `repository:` and
`path:`, never from its own location on disk, and refuses with exit 1 naming
`openRepoTools wip init` where that file does not answer — with ONE exception,
and it is a mechanism and not a taste: `lanes-edit.sh guard`, the
`UserPromptSubmit` name guard Amendment 12 adds, answers that same unreadable
workspace with **2**, because only a 2 blocks a prompt and a 1 would print the
refusal and let the work through it. Their exit codes are
the protocol's and not this toolset's — 1 is *registry not found* there and
*findings were printed* here — so never read a number without knowing which
command produced it.

## Driving `park <Name>`, `resume <Name>` and `status <Name>`

`park <Name>` and `resume <Name>` are the estate verbs as commands on a PATH,
placed by `openRepoTools --install`. They find the estate — `$PROJECTS_DIR`,
else `~/projects/<Name>` then `~/Projects/<Name>`; a family folder beats a
standalone root of the same name; no `<Name>` means the estate around the
current directory — and run its own `make park` / `make resume`. `resume` also
clones and fast-forwards what is not current. Prefer them to a hand-built
sequence, and relay their per-repository lines rather than summarising them.

1. **`park` CREATES NOTHING and `resume` RESETS NOTHING.** With no `<Name>`,
   `park` parks the estate around the current directory. With no estate
   around it either, it lists every estate under the projects directory and
   ASKS whether to park them all; `park --all` (`-a`) is that sweep without
   the question, in name order, continuing past a refusal (Brett Heap's RULING
   of 2026-09-10, superseding his openRepoShape #91 ruling of the same day,
   under which the bare form swept unasked). YOUR STDIN IS NOT A TERMINAL, so
   in your hands a bare `park` outside every estate refuses and names `--all`:
   when the person wants everything parked, run `park --all`; when they named
   one estate, or you stand in one, never reach for it. In the sweep a root
   with NO Speckit git overlay is SKIPPED and named, never failed (his RULING
   of the same day, openRepoShape #92) — a sweep that ends with
   `…, 4 skipped (no overlay)` and exits 0 is a CLEAN run, and what those four
   want is `setup-openspeckit` in each, not a rerun. `park <Name>` on one of
   them still refuses; relay that refusal.
   `resume`'s OWN bare form still refuses with no `<Name>` and no estate around
   it, deliberately, and it has no `--all`: rebuilding every estate on a fresh
   machine by accident is the opposite risk, so relay that refusal rather than
   naming one estate on the person's behalf. `resume` fast-forwards a working
   clone with `--ff-only` and REFUSES BY NAME one that is dirty or on a feature
   branch, skipping it and leaving it exactly as it is — and not running the
   verb in it either. It also refuses a root whose LEG sits on a feature
   branch, because that root's own `make bootstrap` would walk the leg back
   onto its tracking branch; the superproject looks clean in that state, which
   is why the refusal names the leg. Never `git reset`, `git stash` or
   `git checkout -f` — and never `git checkout main` in a leg — to make the
   next run succeed: that is the work the refusal exists to protect.
2. **`~/.agents/workspace.yaml` has exactly TWO writers and you are neither.**
   `resume --workspace <owner>/<repo>` writes it because a person named the
   repository; `openRepoTools wip init` writes it because a person asked for
   the repository by running it (Amendment 9(c) step 9). Both write it only on
   a machine that has none, and neither overwrites one. Do not write that file
   yourself, and do not pass `--workspace` or run `wip init` on your own
   initiative: which private repository holds a person's unfinished work is
   theirs to name.
3. **READ THE LINES, not the exit code.** `park` passes `make park`'s own
   status straight through and can exit 0 with a report of what it left behind,
   which is the point of printing that report. `resume` exits non-zero whenever
   anything was refused, even when `make resume` exited 0 — a skip is not a
   pass. A member that REFUSED is not resumed, and one SKIPPED for want of a
   working clone was never asked.
4. **`status` READS AND CHANGES NOTHING, and fetches nothing unless told to**:
   every ahead/behind line is AS OF THE LAST FETCH, and it says which. Exit 1
   means findings were printed, not that anything failed — relay them per
   repository, as you would `park`'s report. `status --fetch` is the ONE way
   it reaches the network (Brett Heap's RULING of 2026-09-11, "next layer:
   --fetch", on his RULING of 2026-09-10, "start with the local status
   layer"): `git fetch --prune origin` in every repository first, the one
   write it makes — remote-tracking refs, the objects behind them and
   `FETCH_HEAD`, never a local branch or tag, because the refspec is pinned;
   a fetch that fails is a finding on that row, and an ssh prompt is ssh's
   own and still blocks. So when the person wants a CURRENT answer, run
   `status --fetch`, never `git fetch` by hand on its behalf.
   That is the local layer and `--fetch`. A FORK is read against a remote
   named `upstream` from local refs (`--fetch` fetches it too), and, with no
   such remote and only under `--fetch`, an origin whose host is github.com
   is asked about with `gh api` (his RULING of the same day, "next layer:
   fork against upstream") — read-only, and with the shape check below the
   estate commands' only use of `gh`; a fork is a finding naming the
   parent and the `git remote add upstream …` to run, which is theirs to run.
   THE SHAPE PIN (`contracts/shape-pin.yaml`) is read too (his RULING of the
   same day, "next layer: shape-pin drift"): a copied shape file whose sha256
   differs is DRIFT, and the exit is upstream — never re-digest it, never edit
   the pin; a pin behind the standard's `main` names `update-shape.py check
   --root <root>`, which is the person's to run. Currency comes from a clone
   of the source under the projects directory (found by its origin, never by
   folder name), else under `--fetch` from GitHub, once per pin; "currency
   not read" in the note means neither answered — a clone missing or never
   fetched, GitHub not asked or refusing — never that the pin is current.
   THE PARKED RECORD (his RULING of the same day, "next layer: parked record
   against disk") is read from the workspace repository `~/.agents/
   workspace.yaml` names, as of its last pull: a recorded feature with no
   worktree here is `resume <Name>`'s to bring back, never a `git worktree
   add` of yours — unless the record says `--no-push`, when the WIP commit
   never left the workstation that parked it, `resume` refuses it, and the
   exit is to park it again from there, or unless its `pushed:` is missing
   or neither true nor false, which `resume` refuses the same way and the
   same re-park settles, or unless it names NO PARKED COMMIT for that leg,
   which `resume` refuses as moved-on and that same re-park settles, or
   unless ORIGIN HAS LOST THE BRANCH — only `status --fetch` settles that —
   which `resume` refuses as GONE FROM ORIGIN, the WHOLE feature with it:
   delete the record's entry where the feature landed, or push the branch
   again from the workstation that parked it, never a re-park, or
   unless a leg of it has NO ROLE, or a ROLE THIS SHAPE HAS NO PLACE FOR —
   one it does not mount, or one `resume` maps only in the other shape, or
   in neither, as it maps `assembly` — or NO LEG AT ALL, which `resume`
   refuses the whole feature for: that re-park settles a misspelling,
   another shape's role wants a checkout of that shape, and a role of
   NEITHER shape is a record no checkout resumes. Or unless the record's KEY
   ORDER leaves a `- branch:` or a `- role:` where `resume` READS NEITHER —
   `workspace_load_project` shuts the `features:` list at the next key at
   project indent and a feature's `legs:` list at the next key at feature
   indent — so a feature below a moved key is one it never makes and a leg
   below one is a leg it never collects, costing that feature every leg, or
   the feature itself. The first exit is putting the key back, THE ONE
   HAND-EDIT OF THE RECORD these rules ask for; the re-park settles it only
   FROM THE WORKSTATION THAT HAS THAT FEATURE, because a park anywhere else
   rewrites the whole block out of what its own loader read and takes those
   lines with it. Or unless a STALE
   WORKTREE REGISTRATION is named, which is
   `git worktree prune`'s to clear before `resume` can do anything — a
   LOCKED one `git worktree unlock <path>` first, because prune SKIPS it,
   and a DIRECTORY the prune leaves behind yours to MOVE ASIDE rather than
   delete: it still holds that worktree's files, and `git worktree add`
   refuses a path that exists. OR UNLESS ANYTHING ELSE SITS AT THE PATH
   BOTH VERBS COMPUTE for that leg — a directory, a file, or a worktree of
   ANOTHER BRANCH — which `resume` refuses the WHOLE feature for before it
   reads origin, overwriting nothing it did not create ("'…' exists and is
   not a registered worktree of the <role> leg … Move it aside"); moving it
   aside FIRST is the person's, a `git worktree move` where git holds it as
   a worktree and a plain `mv` where it does not, with the `worktree unlock`
   a LOCKED registration wants in front of either and the `worktree prune` a
   dead one wants beside the `mv`. Never `worktree add --force`, never a delete
   under `.git/worktrees/`; a worktree BEHIND a newer record — behind by
   more than the WIP commits `resume` itself un-committed — is what `resume`
   refuses, and rule 1 stands, no reset to make it pass. A WORKTREE ON A
   RECORDED BRANCH AT ANOTHER PATH IS NOT THAT FEATURE'S WORKTREE: both verbs
   compute `<worktree_root>/<branch>` — the leg's own mount under it in a
   three-leg root — out of `$SPECKIT_GIT_WORKTREE_ROOT`, else THIS checkout's
   `git-config.yml`, else the SHAPE's default — `worktrees` inside a three-leg
   root, `../<root folder>-worktrees` beside a single one — and never out of
   the record, so `resume` refuses the WHOLE feature — every leg of it — at
   whichever of its checks that leg reaches first (with the branch still at
   the parked commit, the `git worktree add` it makes LAST of all cannot take
   a branch another worktree holds) and `park` never parks it; the exit is a
   `git worktree move` to that path, the PERSON'S to run, with a `worktree
   prune` in front of it where git still holds that path registered with
   nothing on disk and a `worktree unlock` where git holds the worktree LOCKED
   — AND THERE IS NO MOVE AT ALL for the leg's own checkout, for a leg
   declared `path: "."` (whose computed path ends in `/.`, which no command
   takes), or for ANY SYMLINK in the computed path's own parents — the
   worktree root, the feature directory, a mount above it — because git
   registers what is made there under the path that link resolves to while
   `resume` compares the one you wrote, so the move runs and changes nothing;
   the line names the component, and the remedy is to respell `worktree_root`
   where the link is at or above it and to make that component a real
   directory where it is below. A worktree the record does not know wants
   `park`, not a hand-edit of the record. No config, or no record for the
   estate, is a note, not a finding. `status`'s bare form outside every estate
   reads them all WITHOUT asking, because a read — fetched or not — moves
   nothing of yours; `status --all` from anywhere says the same thing.

## The pinned standard at `upstream/openRepoShape`

The suite builds real estates out of eight of openRepoShape's own files, and it
reads them out of a submodule pinned by `contracts/openreposhape-pin.yaml`.
Three rules, and none of them is negotiable:

1. **Never edit anything under `upstream/openRepoShape` in place.** It is
   somebody else's repository, checked out detached at a commit. A change the
   standard needs is a pull request THERE, then a pin bump here.
2. **Never pin a commit that is not on that repository's `main`.**
   openRepoShape squash-merges, so a branch commit is orphaned the moment the
   pull request lands and the next person's fetch of it 404s. Check with
   `gh api repos/opensoft/openRepoShape/compare/main...<sha>` — `identical` or
   `behind`.
3. **The digest is RECOMPUTED, never adjusted.** `contracts/openreposhape-pin.yaml`
   carries the bump command. A `tree_sha256` edited to make
   `tests/test_upstream_pin.py` pass records this checkout as the upstream,
   which is the one thing the row exists to prevent. The pin file and the
   gitlink move in ONE commit.

## Testing your changes to this repository

```sh
git submodule update --init upstream/openRepoShape
tests/run.sh                      # the suite, serialized — pass any pytest argument
```

**`tests/run.sh` IS HOW THIS SUITE IS RUN, and `python3 -m pytest tests -q` by
hand is the thing it exists to stop.** The run is minutes of bash and hundreds
of `git` processes, and several lanes build in sibling worktrees of one
checkout: the wrapper waits for any live run, takes
`${TMPDIR:-/tmp}/openrepotools-pytest.lock` (`flock` where there is one, a
`mkdir` lock on macOS, which has none), waits again inside it, then runs
`python3 -m pytest tests -q "$@"`. Every lane on one workstation must name the
SAME lock file or there is no lock, which is the whole reason the path is
written here as well as in the file.

Two measured defects on 2026-09-14 (opensoft/openRepoTools#51), both of them
inside a guard that had been copied into four briefs:

```sh
while pgrep -af 'python3 -m pytest' | grep -v pgrep >/dev/null; do sleep 20; done
```

It NEVER WAITED — under the harness `grep` is a shell function whose status is 1
when its stdout is `/dev/null`, even where it matched, so four suites ran at
once — and the pattern is unanchored, so it also matches the guard's own command
line. Read `command grep` wherever an exit status matters. A poll ALONE is the
second defect: every waiter starts the instant the run it watched ends, which is
the same collision one step later. Anchored, split so it cannot match itself,
and locked:

```sh
pat='^python3 -m pyt'"est"                       # split so it cannot match itself
while [ "$(pgrep -f "$pat" | awk 'END { print NR + 0 }')" -gt 0 ]; do sleep 20; done
flock "${TMPDIR:-/tmp}/openrepotools-pytest.lock" python3 -m pytest tests -q
```

`awk` AND NOT `pgrep -fc`, which is what `tests/run.sh` does and for the reason
it gives: `-c` is not in every `pgrep` this repository runs under, and the
count — never `pgrep`'s exit status — is what decides. The wrapper is the
canonical implementation of this guard; the lines above are it in one place for
a person with no checkout in front of them.

`tests/test_lane_helpers.sh` is 122 KB of bash that arrived with the move;
`tests/test_lane_helpers_suite.py` is what makes `pytest` run it, so it is one
slow test rather than no test at all. Everything shipped here is parsed under
macOS **bash 3.2** in CI, where `${x,,}`, `mapfile`, `declare -A` and
`local -n` are syntax errors — write `tr '[:upper:]' '[:lower:]'` and a loop.

Without the submodule the command tests SKIP, naming that first line; they
never fail, because a fork's first `pytest` going red on a missing submodule is
a fork nobody finishes. Everything here is bash and runs on macOS, Linux and
WSL2; on Windows the way in is WSL2, exactly as it is for openRepoShape's
`setup.sh`, and there is no PowerShell twin to write. The suite creates no real
repository and reaches no network — every remote is a bare repository in a
temporary directory, every `$HOME` is a temporary directory, and the one test
that exercises a fetch answers it with a fake `gh` and a `curl` that refuses.
Never test by creating a real GitHub repository.
