# Working in openRepoTools

Three installed commands, `park`, `resume` and `status`, and the
`openRepoTools --install` that places them. **The verbs add no mechanics.**
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
2. **`resume --workspace <owner>/<repo>` is the only writer of
   `~/.agents/workspace.yaml`**, and only on a machine that has none. Do not
   write that file yourself, and do not pass that flag on your own initiative:
   which private repository holds a person's unfinished work is theirs to name.
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
   exit is to park it again from there, or unless a STALE WORKTREE
   REGISTRATION is named, which is `git worktree prune`'s to clear before
   `resume` can do anything — a LOCKED one `git worktree unlock <path>`
   first, because prune SKIPS it, and a DIRECTORY the prune leaves behind
   yours to MOVE ASIDE rather than delete: it still holds that worktree's
   files, and `git worktree add` refuses a path that exists. Never `worktree
   add --force`, never a delete under `.git/worktrees/`; a worktree BEHIND a
   newer record — behind by more than the WIP commits `resume` itself
   un-committed — is what `resume` refuses, and rule 1 stands, no reset to
   make it pass; a worktree the record does not know wants `park`, not a
   hand-edit of the record. No config, or no record for the estate, is a
   note, not a finding.
   `status`'s bare form outside every estate reads them all WITHOUT asking, because a
   read — fetched or not — moves nothing of yours; `status --all` from
   anywhere says the same thing.

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
python3 -m pytest tests -q
```

Without the submodule the command tests SKIP, naming that first line; they
never fail, because a fork's first `pytest` going red on a missing submodule is
a fork nobody finishes. Everything here is bash and runs on macOS, Linux and
WSL2; on Windows the way in is WSL2, exactly as it is for openRepoShape's
`setup.sh`, and there is no PowerShell twin to write. The suite creates no real
repository and reaches no network — every remote is a bare repository in a
temporary directory, every `$HOME` is a temporary directory, and the one test
that exercises a fetch answers it with a fake `gh` and a `curl` that refuses.
Never test by creating a real GitHub repository.
