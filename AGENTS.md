# Working in openRepoTools

Two installed commands, `park` and `resume`, and the `openRepoTools --install`
that places them. **They add no mechanics.** They find the estate and run its
own `make park` / `make resume`, which run the Speckit git extension's scripts —
one implementation, ruled 2026-09-09 (openRepoShape #77, ruling 1). Never
hand-roll the WIP commit, the push, the `git worktree add` or the soft reset
because something refused: relay the refusal.

The shape itself is [openRepoShape](https://github.com/opensoft/openRepoShape),
and this repository pins the commit its tests were verified against. Read that
repository's `AGENTS.md` for the Make targets (`make park`, `make resume`) and
everything about a project's layout; what follows is only what changes when a
person is driving the two INSTALLED commands.

## Driving `park <Name>` and `resume <Name>`

`park <Name>` and `resume <Name>` are the estate verbs as commands on a PATH,
placed by `openRepoTools --install`. They find the estate — `$PROJECTS_DIR`,
else `~/projects/<Name>` then `~/Projects/<Name>`; a family folder beats a
standalone root of the same name; no `<Name>` means the estate around the
current directory — and run its own `make park` / `make resume`. `resume` also
clones and fast-forwards what is not current. Prefer them to a hand-built
sequence, and relay their per-repository lines rather than summarising them.

1. **`park` CREATES NOTHING and `resume` RESETS NOTHING.** With no `<Name>` and
   no estate around the current directory, `park` refuses and lists what it
   found: it does not park every estate, and that refusal is not a cue for you
   to pick one. `resume` fast-forwards a working clone with `--ff-only` and
   REFUSES BY NAME one that is dirty or on a feature branch, skipping it and
   leaving it exactly as it is — and not running the verb in it either. It
   also refuses a root whose LEG sits on a feature branch, because that root's
   own `make bootstrap` would walk the leg back onto its tracking branch; the
   superproject looks clean in that state, which is why the refusal names the
   leg. Never `git reset`, `git stash` or `git checkout -f` — and never
   `git checkout main` in a leg — to make the next run succeed: that is the
   work the refusal exists to protect.
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
