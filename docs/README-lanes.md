# The `lanes` branch — how the estate lane registry is stored

Status: in force — ratified by Brett Heap 2026-09-09 (in-session, verbatim
"track LANES.md in git. but we need to make sure we have a workstation
designation too in the rows right? so that Raven/opsXfactory-2 and
Eagle/opsXfactory-2 are not confused."). Implemented by lane
`provenance-autonomous-merge`, session `f1356e27-665d-4119-b47e-a5e66efdce00`,
window `codeXfactory-3`, on workstation **Eagle**.

Governing protocol:
`/home/brett/.agents/protocols/lane-collision-protocol.md` — Rule 9 (registry
in git) and Rule 10 (workstation designation), Amendment 3, 2026-09-09.

## Why

`LANES.md` is the estate's live-lane register (protocol Rule 4). Many
concurrent lanes on more than one workstation write to it. It used to be a
single untracked file with no history:

- **2026-09-08T23:46:33Z** — one session wrote the whole file from memory. That
  write dropped two other lanes' rows (`browser-ui-repair`,
  `doxbench-stewardship`) and a day of Rule 6 LANDING/LANDED lines. There was
  **no history to recover from**; peers rebuilt rows by hand from their
  handoffs and a 2026-09-04 `.bak`, and edits made in between are simply lost.

Git makes that recovery a `git show` instead of an archaeology exercise, and
the commit log makes every registry change attributable to a lane **and a
workstation**.

## Layout

| what | where |
|---|---|
| branch | `lanes` — an **orphan** branch of `opensoft/xFactory` (no shared history with `main`, never merged into it) |
| worktree | `/home/brett/projects/xFactory/.lanes/` (gitignored on `main`) |
| the registry | `/home/brett/projects/xFactory/.lanes/LANES.md` |
| the path every lane already uses | `/home/brett/projects/xFactory/LANES.md` — a **symlink** to `.lanes/LANES.md` |
| the writer | `/home/brett/projects/xFactory/.lanes/lanes-edit.sh` (symlinked as `/home/brett/projects/xFactory/lanes-edit.sh`) |

Why an orphan branch and not `main`: the aggregation repo's `main` is PR-only
(org rulesets `xFactory Tier-1 main protection`, `required-checks-main`,
`Require Code Owner Review`, all scoped to `~DEFAULT_BRANCH`), so a per-edit
commit cannot land there. `lanes` is covered only by rulesets that forbid
**force-pushes** (`non_fast_forward`), which this workflow never does. The
branch carries no product code, so it never enters a release, a pin, or a
sweep.

## THE ONE HAZARD — `sed -i` DESTROYS THE SYMLINK

`~/projects/xFactory/LANES.md` is a symlink. GNU `sed -i` writes a temp file
and **renames it over the path**, which unlinks the symlink and leaves a
regular file. The registry then silently detaches from git: your edit is
invisible to `git status` in `.lanes/`, and the next lane's helper run commits
the *old* content.

Verified on Eagle, 2026-09-09:

```console
$ ls -la LANES.md
lrwxrwxrwx  LANES.md -> .lanes/LANES.md
$ sed -i 's/x/y/' LANES.md
$ ls -la LANES.md
-rw-r--r--  LANES.md            # <-- the symlink is GONE
```

Safe ways to write:

| operation | safe? |
|---|---|
| `lanes-edit.sh …` | **yes — use this** |
| `sed -i --follow-symlinks …` | yes (verified: link preserved) |
| `cat tmp > LANES.md` (any `>` redirect) | yes |
| `printf '…\n' >> LANES.md` (`>>` append) | yes |
| `python3` `open(path,'a')` / `open(path,'w')` | yes |
| **plain `sed -i`** | **NO — replaces the symlink** |
| `mv tmp LANES.md`, `cp tmp LANES.md` (no `--no-dereference`… `cp` is fine, `mv` is not) | `mv` **NO** |

If it happens: `rm LANES.md && ln -s .lanes/LANES.md LANES.md` after copying
your content into `.lanes/LANES.md`, then commit with `lanes-edit.sh commit`.

## How to write to the registry

```bash
cd /home/brett/projects/xFactory

# read (unchanged — every existing path and habit still works)
grep -n 'my-lane' LANES.md
./lanes-edit.sh verify-row my-lane          # first 200 / last 200 chars of the row

# append to a row's state cell (the common case)
./lanes-edit.sh append-row-status my-lane "LANDED PR #123 → abc1234 (2026-09-09T01:00Z)"

# change one exact substring inside a row (must match exactly once).
# The optional 4th argument becomes the commit subject — use it to record WHY.
./lanes-edit.sh replace-in-row my-lane "ACTIVE" "PARKED" "parked pending Brett's OQ-1 ruling"

# a Rule 6 LANDING / LANDED line (these are file-level lines, not rows)
./lanes-edit.sh append-line "LANDING — lane my-lane, session <uuid>@Eagle, 2026-09-09T01:00:00Z, PR #123 into openxFactory main"

# register a new lane
./lanes-edit.sh add-row "| \`my-lane\` | \`<uuid>\` / \`session_01…\` / window \`my-lane\` | Eagle / WSL2 / brett | 2026-09-09T01:00Z | <objects> | <handoff path> | ACTIVE |"

# you hand-edited .lanes/LANES.md with an allowed tool and want it committed
LANES_LANE=my-lane ./lanes-edit.sh commit "row rewritten by hand"
```

Every mutating subcommand does the same five things:

1. takes a `mkdir` lock in `.lanes/` (so two helper runs never interleave);
2. checks whether LANES.md is already dirty before making its own edit. If it
   is, that content is someone else's — never this invocation's — so it
   **warns** (`git diff --stat` plus the first 200 chars of every changed
   line, and the affected lane(s) identified by the first backtick token on
   each changed line, or `append` for a line with no row of its own) and, by
   **default (`--no-sweep`)**, commits that pre-existing content FIRST, as its
   own `LANES(pre-existing@<workstation>): capture an uncommitted registry
   edit (row <lane>)` commit, so a peer's in-flight edit is never combined
   with yours. Pass `--sweep` to fall back to the old combined-commit
   behaviour instead — never silently: it appends " + sweeps uncommitted
   edit to row \<lane\>" to the commit subject it is about to create. Either
   way the write still goes through — this never fails the call;
3. re-reads the file, edits **exactly one line** in place, and refuses if
   `git diff --numstat` says more than one line moved;
4. commits as `LANES(<lane>@<workstation>): <what>` — workstation from
   `hostname -s`;
5. `git pull --rebase origin lanes` then `git push`, retrying a lost push race
   up to six times.

**On a rebase conflict it aborts**, leaves the worktree clean and not
mid-rebase, prints the conflicting lines and prints the recovery commands. Your
edit survives as a local commit; read it back with
`git -C .lanes diff origin/lanes..HEAD -- LANES.md`, then
`git -C .lanes reset --hard origin/lanes` and redo it on top of the peer's
version.

## Hand edits

After **any** hand edit made with an allowed tool (python read/write, `sed -i
--follow-symlinks`, a `>>` append), run
`LANES_LANE=<lane> ./lanes-edit.sh commit "<message>"` **immediately** — don't
leave it sitting uncommitted while you do something else. Prefer
`append-row-status` / `replace-in-row` / `append-line` over a hand edit in the
first place: they commit in the same call, so there is no window where the
edit sits uncommitted at all.

An uncommitted hand edit left in the worktree is captured by the *next* lane's
helper run, not by yours — and that capture now comes with a warning and, by
default, a **separate** `LANES(pre-existing@<workstation>): …` commit (see
above), rather than silently landing inside that other lane's own commit with
no trace of whose it was (which is what happened in 0d84d34 and a1f2438:
content intact, authorship lost). The separation only helps if you commit
promptly — a hand edit is never truly "yours" in the history until it is
committed under your own lane's message. `lanes-edit.sh commit` itself cannot
split a hand edit that mixes your row with someone else's: it warns and
annotates its subject the same way when the dirty diff it is about to wrap
touches a row other than the one named by `$LANES_LANE`.

## What is forbidden

- **A whole-file write from memory.** This is the 2026-09-08 incident. If you
  find yourself about to write out all ~110 lines, stop: the rows you did not
  read are the rows you are about to delete.
- **`git add -A`, a bare `git commit`, `git stash`, `force-push`** — estate
  rules, and this worktree is shared.
- **Committing `LANES.md` to `main`** of any repo. It stays on `lanes`.

## Snapshots

`LANES.md.snap-*` / `LANES.md.bak-*` at the aggregation root are the pre-git
backup habit. They are no longer required — git history is the backup — and
they are gitignored on `main`, so leaving them is harmless. The last pre-git
snapshot is kept deliberately:
`/home/brett/projects/xFactory/LANES.md.snap-20260909T002735Z-pre-git`.

## Adopting this branch on another workstation (Raven)

See the "Raven setup (operator, Brett)" block in Amendment 3 of
`/home/brett/.agents/protocols/lane-collision-protocol.md`. The short version:
**diff Raven's local `LANES.md` against the branch and append its missing rows
with `lanes-edit.sh add-row` BEFORE replacing the local file with the symlink.**
Raven's file may hold rows this branch has never seen.
