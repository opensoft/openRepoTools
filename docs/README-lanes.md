# `lanes/LANES.md` — how the estate lane register is stored

**Moved 2026-09-10 (Amendment 5).** The register lived on the orphan `lanes`
branch of `opensoft/xFactory` from 2026-09-09; it now lives HERE, on `main` of
`opensoft/brett-wip`, the person's workspace repository — ratified by Brett
Heap 2026-09-10 ("since we now have the user-wip repo this is a better place
to store our lanes", "create opensoft/brett-wip and move it all there"),
implemented by lane `openRepoShape-2`, session
`8fa66b30-4cf5-4b80-b40c-ac3640cf45ab`, on workstation **Eagle**. All 1242
register commits came across with it as a `git subtree`; the orphan branch is
retired behind a pointer. Rules 9 and 10 are unchanged in every mechanic:
every write is still one commit, made by `lanes-edit.sh`, and every row still
names its workstation.

Status of the original ruling: in force — ratified by Brett Heap 2026-09-09 (in-session, verbatim
"track LANES.md in git. but we need to make sure we have a workstation
designation too in the rows right? so that Raven/opsXfactory-2 and
Eagle/opsXfactory-2 are not confused."). Implemented by lane
`provenance-autonomous-merge`, session `f1356e27-665d-4119-b47e-a5e66efdce00`,
window `codeXfactory-3`, on workstation **Eagle**.

Governing protocol: `~/.agents/protocols/lane-collision-protocol.md` — Rule 9
(register in git) and Rule 10 (workstation designation), Amendment 3,
2026-09-09; **Amendment 5, 2026-09-10** (the register lives in the person's
workspace repository).

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
| repository | `opensoft/brett-wip` — Brett's workspace repository, private, org-owned (the `<user>-wip` form, `openRepoShape#81`) |
| branch | `main`. Direct commits are the norm there **by design**: the repository is excluded from the organisation's PR-only ruleset precisely so a per-edit register commit can land |
| checkout | `~/projects/brett-wip/` |
| the register | `~/projects/brett-wip/lanes/LANES.md` |
| the path every lane already uses | `~/projects/xFactory/LANES.md` — a **symlink** to `~/projects/brett-wip/lanes/LANES.md` |
| the writer | `~/projects/brett-wip/lanes/lanes-edit.sh` (symlinked as `~/projects/xFactory/lanes-edit.sh`) |
| the two ends of a lane | `lanes/lane-start` and `lanes/lane-end` (symlinked as `~/.local/bin/lane-start` and `~/.local/bin/lane-end`) |
| their tests | `lanes/test_lane_helpers.sh` — run it from anywhere; it touches nothing real |
| the object logs | `lanes/log/<lane>.md` — one per lane (Amendment 7), with `lanes/repos.tsv`, the repo alias table |
| who places the symlinks | `~/projects/brett-wip/scripts/link-estates` (idempotent, `--dry-run`) |

Why `main` of the workspace repository and not the aggregation's: the
aggregation repo's `main` is PR-only (org rulesets `xFactory Tier-1 main
protection`, `required-checks-main`, `Require Code Owner Review`, all scoped
to `~DEFAULT_BRANCH`), so a per-edit commit cannot land there — which is why
the register spent 2026-09-09 to 2026-09-10 on an **orphan `lanes` branch** of
that repo instead. The workspace repository has no such gate and no product
code at all, so the register can sit on its `main` next to the handoffs it
cross-references. Nothing here is ever released, pinned, swept or bumped.

**The register no longer owns its whole checkout.** `~/projects/brett-wip/`
also holds `handoffs/` and `workspaces/`, which other lanes write. That is why
the writer now (a) uses a pathspec on every `git add` and `git commit`, so a
peer's half-written handoff can never ride along in a register commit, and (b)
SKIPS `pull --rebase` when the checkout has unstaged changes to other tracked
files — `pull --rebase` refuses outright on any unstaged tracked change — and
pushes straight out instead, warning and naming the files. If the push is also
rejected (the remote moved), it stops with exit 3, leaves your edit as a local
commit, and prints the recovery: the owner of that file commits it, then you
re-run `lanes-edit.sh commit`.

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
cd ~/projects/xFactory

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
5. `git pull --rebase origin main` then `git push`, retrying a lost push race
   up to six times — or, if a peer has uncommitted changes to other files in
   this checkout, a warning naming them and a straight push (see the Layout
   note above).

**On a rebase conflict it aborts**, leaves the worktree clean and not
mid-rebase, prints the conflicting lines and prints the recovery commands. Your
edit survives as a local commit; read it back with
`git -C ~/projects/brett-wip diff origin/main..HEAD -- lanes/LANES.md`, then
`git -C ~/projects/brett-wip reset --hard origin/main` and redo it on top of
the peer's version.

The script spells no path of its own: it finds the checkout root with `git
rev-parse --show-toplevel` from its own directory and derives the pathspec
`lanes/LANES.md` with `--show-prefix`, so the clone may live anywhere. The
overrides `LANES_REPO`, `LANES_PATH` and `LANES_BRANCH` exist for tests.

## Starting and ending a lane

The lane rule, ruled by Brett Heap 2026-09-10: **lane = tmux window name =
Claude session name**, in the form `<repo>-<position across, left to right>`.
The working directory confers NO lane — two lanes may share one; a window
still called `claude` has no lane at all; and whether a name is free is
decided by whether the row's recorded session id is **live**, never by whether
a row exists.

Honouring that by hand is five acts at one end of a lane and one at the other,
and this register records where they get dropped: rows added hours late (`ROW
ADDED LATE 2026-09-09T18:05Z — the lane worked from 00:10Z without a row, a
Rule 4 gap this row closes`), windows left named `claude`, `(2)`-suffixed
session names minted when a rename collided with a title that was still held,
and lanes that stopped without ever updating their row. `lane-start` and
`lane-end` are those acts, one command at each boundary — never mid-session,
because renaming a running window's session is exactly what mints the `(2)`.

```sh
lane-start openRepoShape 2          # in the tmux window that will carry the lane
lane-start openRepoShape-2          # the full lane name works too
lane-start 2                        # <repo> from the cwd's git root

lane-end openRepoShape-2            # the window is closing
lane-end openRepoShape-2 --retire   # …and the lane is not coming back
```

Both print every step to **stderr** and refuse with a message that names the
fix. Exit codes: **0** done, **1** environment, **2** refusal — and under
Amendment 8 (R-A8-3) `lane-start`'s **2 is for ARGUMENT ERRORS and nothing
else**: a name that is not a lane, a position that is not a position, a name a
window cannot take, a lane whose register holds two rows, a lane live in
another window. **A person's answer is never an argument error.** `--confirm`
answered `N`, and `--confirm` with no terminal and no `--yes`, rename nothing,
write nothing, print one notice and `exec` Claude **bare** with the
pass-through arguments, **exit 0**; under `--no-launch` that bare command is
printed on stdout so a launcher can exec it. `claude-profile` **`exec`s**
`lane-start`, so this script's status *is* the launcher's, and a refusal here
would be an exited pane with no Claude in it — the one failure the change
exists to prevent. `--help` prints the file's own header, which is the whole
manual.

### `lane-start <repo> <n>`

1. derives `LANE=<repo>-<n>` and the lane's directory — `~/projects/<repo>`,
   or `--dir <path>`;
2. **refuses unless it is already inside tmux.** It renames the window it is
   run in and never creates a tmux session: the window is the lane;
3. **liveness check, before it takes the name — and it is always asked.** It
   reads the session id(s) out of the row's *session cell* — not the whole row,
   which quotes other lanes' ids all the time — and looks for a live record in
   every profile's `sessions/*.json`. The row it reads is the PUBLISHED one,
   fetched, unioned with this checkout's (see `live-holder` below), because a
   gate that runs only when THIS checkout already names an id skips exactly when
   the answer matters: a uuid another workstation has stamped and pushed reads
   here as "no ids, nothing to check". `lane-start` also asks the published
   register whether the lane already HAS a row before it adds one, and refuses
   rather than writing a second — two rows for one lane is a register
   `lanes-edit.sh` cannot edit at all, because `row_line` requires exactly one. A record is
   live when its pid is alive **and** `/proc/<pid>/stat`'s start time still
   matches what the record wrote down, so a recycled pid cannot lock a name.
   A live holder in **another** tmux window is a refusal that names the next
   position; a row whose recorded sessions have all ended is a lane you are
   **resuming**, which is allowed and expected. A record whose session *name*
   is some other lane is not a holder either: this register carries rows whose
   session retired from the lane and was renamed, and refusing on those would
   lock free names forever;
3b. **the live session in THIS window** (Amendment 8), which is not step 3's
   question. Step 3 asks whether any session the *row* names is alive; this
   asks what is alive in this *window*, through `lanes-edit.sh window-session`.
   The harness mints a new transcript uuid with nobody acting — a `/clear` does
   it, and so did the 2026-09-12 usage reset that carried this lane's
   conversation into `4a91f1dc…` while its row still ended on `09dd34d1…`. An
   id in no row is an id `live-holder` cannot look up: it answers 8, *this lane
   is parked*, about the conversation sitting in the very window it was asked
   about, and `lane-start` would then resume the lane's **previous**
   conversation and write that uuid on to an append-only line. Read off the
   record instead, the id is appended to the session cell in step 5 — before
   the stamp — and it is what this run resumes and stamps. There is no flag for
   it and there could not be one: the id does not exist until the session does.
   The act is `lane-start --no-launch <repo> <n>` run **in** that window, which
   is what the SessionStart hook's block asks the new session to do;
3c. `--confirm`, when it was passed and this window is not already named for
   the lane: the **triple** — the window, the session live in it, the row — and
   the question `Take lane <lane> in this window? [y/N]`. Before the rename and
   before any write, so a No costs nothing. `--yes` answers it for a caller
   that has already asked. **Every answer leads somewhere and no answer
   exits.** An explicit `N` — and no terminal with no `--yes`, which is the
   same answer with nobody there to give it — renames nothing, writes nothing,
   prints **one** notice naming the lane it declined, and `exec`s Claude bare
   with the pass-through arguments, **exit 0**: `N` means *not this lane*, not
   *not at all*, and an unattended launch must still not take a lane on an
   inference nobody confirmed. The launcher passes `--confirm` exactly when the
   lane came from the swap *record* rather than from the window name or a flag;
4. `tmux rename-window <LANE>` — which also turns automatic-rename **off** for
   that window, so the name survives the next command it runs;
5. the row, through `lanes-edit.sh`: `add-row` when there is none — state
   `STARTING`, session id `pending — set by the session's first act`,
   `<workstation> / <profile> / <user>` per Rule 10, handoff path
   `handoffs/<estate>/session-handoff-<date>-lane-<LANE>.md` — and
   `append-row-status` when there is one. Never a hand edit. **That status is
   Amendment 6(c)'s stamp**, written here rather than owed to the session
   afterwards:

   ```text
   <UTC> RESUMED by <uuid> (lane <lane>) — lane-start on <ws>: window renamed, launching <the command>
   ```

   The **tail states what happened**, so a `--no-launch` run ends `window
   renamed, no launch` and never claims to have launched anything.
   `STARTED` where a new session takes the name, and the uuid is the one this
   run actually resumes or mints, read from the **published** row. Under
   Amendment 6(b) that stamp is load-bearing — it is what the next `lane-start`
   resumes — so a stamp that is owed to a session which dies at a usage reset
   before its first act is a lost lane, which is the shape this estate hits
   daily. A brand-new row needs no stamp: it is created with that uuid already
   in its session cell;
6. the launch — decided *before* the row is written, because a brand-new
   session's id is minted there and the row must record it. **Resume beats
   new**, because a rename into a title that is still held is exactly what mints
   `<LANE> (2)` and costs the lane its address (Amendment 2: the session name
   *is* the messaging address). Three cases, in order: `exec claude --resume
   <id>`, where `<id>` is the **last** uuid in the row's session cell and this
   directory has its transcript (Amendment 6 — a lane is resumed by the id its
   row records, never by its title); `exec claude --resume <LANE>` when no
   recorded id resolves but a transcript here carries the custom title `<LANE>`,
   which is the fallback and only filters the picker; and `exec claude --name
   <LANE> --session-id <fresh uuid>` for a lane with no history here. Anything
   after `--` is passed through to `claude`.

   **The session cell it reads is the PUBLISHED one**, fetched, through the same
   `register-row` step 3 asks — like every other state read in this tooling. A
   `git fetch` does not move a working tree, so a uuid a peer stamped from
   another clone and pushed is absent from this checkout's copy of the row until
   something pulls: read from there, a cell published as `<U1> → <U2>` still
   ends at `<U1>`, and the lane resumes its **previous** conversation, appends a
   status naming that id, and writes a `RESUMED` line into `lanes/log/<lane>.md`
   carrying a session uuid that is not the lane's current one — in a file
   nothing ever rewrites. A row this checkout has and `origin/main` has not is
   an unpushed commit: `lane-start` says so, names the ids only this copy
   carries, and takes a new session rather than resuming one of them.

`--dry-run` prints all six and writes nothing. `--no-launch` does the first
five and prints the `claude` command on **stdout** instead of running it —
that is the hook a launcher uses, and it is the only thing either script ever
writes to stdout.

The env column records the Claude **profile** (`team-05b`), which is the thing
that actually varies between lanes on one workstation; `WSL2` in the older
rows is the same column.

### `lane-end <lane>`

Appends `<UTC> lane-end on <workstation>: window closing; NOTHING IN FLIGHT`
to the row, and **refuses (exit 2) while the row says something is still
open**: if the last `LANDING` or `CLAIMED` in the state cell has no `LANDED`
or `RELEASED` after it, the lane still owns something and Rule 6 is holding
other lanes' merges. It prints the offending excerpt and the two ways out —
post the `LANDED`/`RELEASED` first, or `--force`, which ends the lane and says
in the register that it did.

The phrases that *say* nothing is open — `NOTHING CLAIMED`, `no LANDING open`,
`LANDING WITHDRAWN`, `UNCLAIMED` and their kin — are removed
case-insensitively before that scan. Without that, a substring match on
`CLAIMED` inside `NOTHING CLAIMED` would refuse on every healthy lane in the
register.

`--retire` also marks the cell `RETIRED <UTC>`, by replacing the **state word
the cell opens with** — never the whole cell, which is the row's history and
the reason the register exists. `replace-in-row` requires that word to be
unique in the row; when it is not, the refusal prints the exact
`--state-was "<text>"` re-run.

It **never renames the window.** The name is the lane's history until the next
`lane-start` takes that window, and a window renamed back to `claude` is a
window nobody can attribute.

One argument is taken verbatim, so a lane named before the `<repo>-<n>` rule
(`browser-ui-repair`, `hermes-wallet-exercise`) can be ended by its own name.

### The tests

```sh
bash lanes/test_lane_helpers.sh     # 713 assertions, ~2m, touches nothing real
```

A temp `HOME`, a bare repo and a clone seeded with a header and twenty-seven
rows, a fake `tmux` that logs its renames and a fake `claude` that logs its
argv. Amendment 7 adds a SECOND clone — the other workstation — so the race a
claim can lose is run for real rather than described, and `project.yaml` /
`family.yaml` fixtures for the leg detection. **No test may reach GitHub, and
what guarantees that is `LANES_NO_GITHUB=1`**, exported over every case,
plus `--no-github` on each: with it set, `gh_reads`, `gh_comment` and
`gh_stale_claim_url` all return before any `gh` or `git ls-remote` call. The
fake bin is *prepended* to `PATH`, not substituted for it, so a real `gh` on
this workstation is still reachable and is not what stops the call. The last
two assertions check that the real register and the real `lanes/log/` of the
clone the suite was run from are untouched — the log check compares the
directory listing taken before the first case with the one after the last,
because `lanes/log/` carries real lanes' records now and *empty* was never the
property being asserted.
`lanes-edit.sh` runs **for real** against the sandbox register, so the commit,
pull and push path is covered rather than stubbed, and liveness is a real
`sleep` process and a reaped pid rather than a mocked `/proc`.

## The object log (Amendment 7)

**DRAFT, 2026-09-11, awaiting Brett Heap's word.** The register says where a
lane *is*. It does not say what a lane *holds*: Rule 1 claims live in GitHub
comments, Rule 6 landings live in `LANES.md` as free text, and "does anyone own
this issue" has no answer short of reading 607 appended lines and 44 handoffs.
This is the tooling half of that answer.

### Layout

| what | where |
|---|---|
| a lane's object log | `lanes/log/<lane>.md` — one file per lane, append-only |
| line 1 of each | `# lane <lane> — object log (lane-collision-protocol Amendment 7)` |
| every other line | one EVENT, in the grammar below |
| the alias table | `lanes/repos.tsv` — `alias<TAB>owner/repo`, case-insensitive |
| the only writer | `lanes/lanes-edit.sh` (`log`, `claim`, `release`), as for `LANES.md` |
| the reader | `lanes-edit.sh who` |

One file per lane is what makes this safe from two workstations at once: two
lanes writing at the same moment touch two different files, so what a shared
file would turn into a conflict is a fast-forward here. **There is no index.**
A read fetches and greps; 45 lanes' logs together are smaller than one of the
register's rows.

**Every state read is of `origin/main`, after a `git fetch` — never of the
working tree.** What has LANDED is what other lanes can see, and a working
tree can be behind by a peer's whole day: `who`, `claim`'s pre-check, the
staleness test, the superseded filter, the crossing warning, `lane-end`'s
refusal and `lane-start`'s home lookup all read the same source, so they
cannot disagree with each other either. `LANES_NO_FETCH=1` (and `who
--no-fetch`) skips the fetch for an offline lane and for the tests; it does
not change what is read, only how current the ref is.

`LANES.md` is unchanged. Its rows are still its rows, and its Rule 6 `LANDING`
/ `LANDED` lines still land in it, because every lane already reads them there
as the merge hold — which is why `who --landing` reads *those* and not the
logs. A `LANDING` or a `LANDED` therefore writes **both files in one commit,
with two pathspecs**: there is no moment at which only one of them has been
written.

### The grammar

```text
<VERB> — lane <lane>, session <transcript-uuid>@<workstation>, <UTC>, <object>[ → <payload> | ← <payload>][ — <free text>]
```

The verb is **one token**. The first four fields are separated by `, `. The
**object token contains no space and no comma**, so the payload begins
unambiguously at the first space after it; payload sub-fields are separated by
`; ` and several refs are space-separated.

| kind | verbs |
|---|---|
| issue | `CLAIMED`, `RELEASED`, `TAKEOVER ← <stale claim URL>`, `CLOSED → owner/repo#pr` |
| PR | `OPENED ← owner/repo#i [owner/repo#j …]`, `LANDING`, `LANDED → <sha>`, `WITHDRAWN`, `CLOSED` |
| lane | `STARTED`, `PAUSED`, `RESUMED`, `ENDED`, `RETIRED` |
| race | `CLAIM-LOST → lane:<other>` |

There is no `MERGED`: Rule 6's `LANDED → <sha>` is already the post-merge line.

**Every line has an object**, lane-kind lines included — theirs is the lane:

```text
STARTED — lane openRepoProject-1, session 09dd34d1-3afe-43a1-88fc-c33c92c08088@Eagle, 2026-09-11T19:08:12Z, lane:openRepoProject-1 → home opensoft/openRepoProject; estate openRepoProject
```

`PAUSED`, `RESUMED`, `ENDED` and `RETIRED` carry the same `lane:<name>` object
and no payload.

**The object kinds in scope** are an issue or PR (`owner/repo#<n>`), an
OpenSpec change directory (`owner/repo:openspec/changes/<name>`), and — for
the lane-kind lines only — `lane:<name>`. `#<n>` is shorthand for the lane's
**own** home repo; a foreign repo is always spelled, so that crossing is
explicit at the moment it is typed. Human acts, realization groups, contract
cuts, file surfaces and Amendment 1's substrates stay where they are today, on
their governing records, and are an explicit non-goal; a later amendment may
add keys.

`lanes/repos.tsv` resolves an omitted owner and the register's legacy
spellings — all four spellings of `codexFactory` resolve to
`codeXfactory/codexFactory`, which is the redirect GitHub itself answers with —
and an alias that is **not** in the table is refused, with the hint to spell
`owner/repo`. Guessing is how a fifth spelling of one repository gets created,
so spellings that could not be resolved (`oxF`, `xF`, `OMI`, `OWI`, and the
bare `InkRouter` and `IRSS`, which are ambiguous between two orgs) are left out
deliberately rather than guessed at.

### State is per lane

**A lane's state on an object is that lane's own LAST line naming it.** The
lane HOLDS the object while that verb is open; the object is HELD when any lane
holds it.

- **open** — `CLAIMED`, `TAKEOVER`, `OPENED`, `LANDING`, `WITHDRAWN`. A
  withdrawn landing leaves the PR held by the lane that withdrew it.
- **closed** — `RELEASED`, `CLAIM-LOST`, `CLOSED`, `LANDED`. **A closing verb
  closes only the writing lane's hold**, never another lane's.

That last sentence has a consequence worth knowing before it bites: after
another lane's `TAKEOVER`, the dispossessed lane's own last line is still its
`CLAIMED`, so `who` marks it `superseded by TAKEOVER (lane:<X>)` rather than
counting it as a holder, and `lane-end` — which would otherwise refuse for
ever — names the one act that frees it:

```text
CLAIMED opensoft/repoG#8 (…) — taken over by lane:repoG-2 at 2026-09-11T20:00:51Z;
  run: lanes-edit.sh release opensoft/repoG#8 "taken over by repoG-2"
```

**A `TAKEOVER` supersedes only while it is the taker's own last line on the
object.** Per-lane last-line semantics apply to the taker too: once lane B
writes `RELEASED`, `CLOSED` or `LANDED` on the object, B's `TAKEOVER` supersedes
nothing, and a later `CLAIMED` by the lane it dispossessed holds normally. A
`TAKEOVER` is never removed from an append-only log, so treating one as
superseding *for ever* made a legitimate re-claim invisible: `who` called a held
object FREE, `claim` did not refuse the next lane — the one outcome Rule 1
exists to prevent — and `who --lane` and `lane-end` disagreed about the same
object. No clock and no cross-file order is needed to ask this: both halves are
"what is this lane's last line", read off two append-only files.

*Known, deliberate.* Two lanes that each end on a `TAKEOVER` of one object are
**both** reported as holders. That is a visible conflict rather than a silent
one, and it is not reachable through the helpers — `claim --force` takes over a
stale `CLAIMED` and nothing else, and refuses outright when more than one lane
holds the object.

**State is read in FILE ORDER, never by comparing timestamps.** A lane's log is
append-only and single-writer, so its line order *is* that lane's write order,
and "its last line naming the object" means the last such line **in the file** —
a `LANDING` and its `LANDED` are often written in the same second, and on a
workstation whose clock steps backwards the second of them is stamped earlier.
The UTC stays on every line as information and is compared only where a
**duration** is the rule — Rule 1's four hours and Rule 6's thirty minutes —
because no two workstations share a clock (this one was observed jumping ±25s
on 2026-09-11, and a log commit landed carrying a UTC 26s after its own
committer date), and which lane got somewhere first is landing order on `main`
rather than a stamp.

**No line is ever dropped silently.** A line the parser cannot read is
reported as `unreadable: lanes/log/<lane>.md:<n> (<why>)` and counted, because
in an append-only log that nothing rewrites, a dropped line is a hold no tool
will mention again — `who` would call the object free, and it is not. A UTC
without seconds (`2026-09-10T20:31Z`) is read, not dropped: the register has
been writing that form since before this helper existed.

### `log` — the generic append

```sh
LANES_LANE=openRepoProject-1 lanes-edit.sh log OPENED opensoft/brett-wip#14 ← brettheap/new-workstation#11
```

Validates the verb and the object key, appends one line, and commits it as
`LOG(<lane>@<workstation>): <VERB> <object>`. A lane verb takes a `lane:<name>`
object and an object verb refuses one.

It **refuses the four verbs that have a guarded subcommand of their own** —
`CLAIMED` and `TAKEOVER` (use `claim`, `claim --force`), `RELEASED` (use
`release`), and `CLAIM-LOST`, which only a lost race writes — and names the
subcommand in the refusal. `log CLAIMED` would otherwise skip the pre-check,
the race and the rescan while `who` reported the result identically to a real
claim, and `log TAKEOVER` would skip the staleness test that is the only thing
making a takeover legitimate. `OPENED`, `LANDING`, `LANDED`, `WITHDRAWN`,
`CLOSED` and the lane verbs are exactly what `log` is for. `--text "<t>"` sets the free text when
there is no payload to put it after. The session id is `$LANES_SESSION`, else
the **last** transcript uuid in the lane's row — the lane's current session
under Amendment 6(b).

### `claim` — Rule 1 as one act

```sh
LANES_LANE=openRepoProject-1 lanes-edit.sh claim brettheap/new-workstation#11
```

**The race is decided by which `CLAIMED` LANDS on `main` first — never by
comparing timestamps.** Two workstations' clocks are not a shared order; git's
push serialization is, and the `mkdir` mutex in this helper only serializes one
workstation. So:

1. `git fetch origin`, and pre-check against **`origin/main`** — what has
   landed is what other lanes can see, and a working tree can be anything.
2. If another lane holds it, print `who` and **exit 2**: Rule 1 says the lane
   stops and reports, it does not author a successor. Nothing is written.
3. Run Rule 1's three reads and print them; warn if this is a crossing.
4. Append the `CLAIMED` line, commit, push. Inside that push, after every
   `pull --rebase`, rescan: if another lane's `CLAIMED` or `TAKEOVER` is
   already on this history, **theirs landed first** — append
   `CLAIM-LOST → lane:<winner>`, push both lines, and **exit 7**. The claim is
   *abandoned*, not queued; Rule 7's queueing is for substrates, which this
   amendment does not touch.
5. Post the GitHub `CLAIMED —` comment **after** the push, citing the commit
   that carries the line. The line is never rewritten to cite the comment.

A claim needs a checkout it can rebase. Amendment 5(d) *skips* `pull --rebase`
when a peer has left uncommitted changes to other files in this shared
checkout — the right default for a row edit, and unacceptable for a race — so
`claim` **refuses (exit 2) and names the files** instead of racing unprotected.

The guard is computed over the **whole checkout** — every tracked file that
differs from `HEAD`, staged or not — minus exactly the pathspecs this write
will commit, and `log` and `release` are guarded the same way. Scoped to
anything narrower it was a hole: measured against (the lane's log + `LANES.md`)
while a `CLAIMED` writes the log alone, a dirty `lanes/LANES.md` — the one file
this checkout routinely has dirty — passed the guard, took the skip-the-pull
branch, and raced with the rescan disabled, leaving two lanes holding one
object. The exception is plural on purpose: a `LANDING` or `LANDED` writes two
files, so a dirty register is *its* business and is captured as its own
attributed commit, exactly as before.

`claim`, `release` and `log` first take that same pre-existing capture for the
register — a peer's uncommitted `lanes/LANES.md` lands as its own attributed
`LANES(pre-existing@<workstation>): …` commit, with the warning every register
write already prints — and only then re-test the checkout, because this clone
carries a half-written register line most of the day and refusing every claim
on it would push lanes to stop using the tool. Any **other** modified tracked
file outside the write's own pathspecs is still a refusal (exit 2), and it is
taken before the lock and before the capture, so a write that refuses never
leaves a commit of somebody else's line behind.

**Reads 2 and 3 name the object, not its digits** (Amendment 8). They searched
for the bare slug as a *substring*, and a number is a substring of almost
everything: claiming `brettheap/new-workstation#15` printed somebody else's
PR #10 — GitHub's own search had matched `15` in its text — and a 40-character
commit sha out of `ls-remote`, both under the heading *existing work on this
object*. Evidence that is not evidence is how a lane talks itself out of a claim
it should make, or into one it should not. **Two reads, two tests**, because the two
inputs are not the same kind of text. `gh pr list`'s rows are **prose**, so a
reference is `#<n>` — the hash required, its left side unbounded, because the
canonical spelling is `owner/repo#15` and the character before the `#` is a
letter — or the row's own number column, which is the PR the object *is*.
`ls-remote`'s refs are **names**: `issue-15-fix` carries no hash, so there the
test is the bare number as a whole token, after the leading sha has been
stripped, so a branch is matched by its name and never by the digits of the
commit it points at. An OpenSpec change directory has a word for a slug and
takes the whole-token test in both.

**Read 2 filters over the body.** `gh pr list`'s columns are number, title,
branch and state; the reference that makes a PR a sibling is almost always in
its **body**, which is what GitHub's own search matched and what the columns do
not carry. Filtering the columns alone dropped the real PR for this very
issue — whose body says `brettheap/new-workstation#15` twice — while a filter
with the hash optional kept the wrong one instead. So the body is fetched,
flattened to one line, used for the test, and cut off again before anything is
printed: under-reporting a sibling is the direction that lets a lane claim what
somebody else is already working on, and it is the one direction Rule 1 cannot
afford.

The filter is the `sibling-filter <object> [--branch]` subcommand, which both
reads pipe through and which can be held to account on its own:

```console
$ printf '10\tbump the pin to 1150\n15\tthe amendment 8 work\n' | lanes-edit.sh sibling-filter opensoft/repoE#15
15	the amendment 8 work
```

`--no-github` skips every `gh` call, for the tests and for an offline lane. A
line written that way is **not yet a Rule 1 claim**, because the comment a
person outside this estate reads does not exist, so it carries the free text
`no-github` and `who` prints it as `local only — no GitHub claim comment`.
Otherwise **the log is authoritative for a claim made through `claim`** — a log
line *is* a live claim for Rule 1 purposes — and the GitHub comment is the copy
another person reads.

**Stale**, made checkable from Rule 1's own words: a lane's `CLAIMED` on an
**issue** is stale when it is older than four hours *and* that lane has written
no later `OPENED` whose `←` payload names the issue. A PR is never stale by
this rule — Rule 6 governs PRs, with its own thirty minutes. An object is taken
to be a PR once some lane has written `OPENED` on it, which is the only
offline evidence there is and exactly the evidence Rule 1 cares about.
`--force` takes over a stale claim and nothing else, writing
`TAKEOVER ← <the stale claim's comment URL>`; `TAKEOVER` is itself an open
verb, so no second line is needed to say the taker holds it.

**A crossing warns; it never refuses** (Brett Heap, 2026-09-11: "yes just
warn"). Crossing is routine — `opsXfactory-3` landed **32 distinct PRs** into
`opensoft/Omnigent-Install`, every one of them foreign to its home, and
`openXfactory-3` landed 23 foreign of 31 — so a refusal here would be a new
gate nobody asked for. `claim` names every lane homed on the target repo that
is live (or on another workstation), with its address and last transcript uuid:

```text
WARNING: CROSS-REPO — opensoft/workBenches is not lane openRepoProject-1's home (opensoft/openRepoProject).
  LIVE lane homed on opensoft/workBenches: @workBenches-2 — last transcript uuid 4f2c8e10-...
```

Repos that are **legs of one `project.yaml`** are not a crossing: the manifest
is looked for one and two levels under `~/projects`, and only
`legs[].repository` is read — the manifest says of itself that it confers
nothing, and `role:` is never consulted. A `family.yaml`'s `members:` is
deliberately *not* read: a family is broader than a project, and two of its
members are two projects with two lanes.

### `release`

```sh
LANES_LANE=openRepoProject-1 lanes-edit.sh release brettheap/new-workstation#11 "superseded by #12"
```

A `RELEASED` line and the matching GitHub comment (`--no-github` skips it). It
never refuses: releasing something this lane does not hold is a note, not an
error, and it is also the act that closes a dispossessed lane's own line after
someone else's takeover.

### `who` — the read

```console
$ lanes-edit.sh who brettheap/new-workstation#11
object   brettheap/new-workstation#11
HOLDS    lane openRepoProject-1        CLAIMED   2026-09-11T19:08:12Z (2h 14m ago)
state    HELD
holder   lane openRepoProject-1 (CLAIMED, 2026-09-11T19:08:12Z)
  stale    no — 2h 14m old, threshold 4h
  home     opensoft/openRepoProject
  holder   lane openRepoProject-1 — LIVE (session 09dd34d1-3afe-43a1-88fc-c33c92c08088, pid 779114, tmux claude-team-05f-20260911150206-778763:@460.%460)
  address  @openRepoProject-1 · claude --resume 09dd34d1-3afe-43a1-88fc-c33c92c08088
  handoff  handoffs/openRepoProject/session-handoff-2026-09-11-lane-openRepoProject-1.md
  log      lanes/log/openRepoProject-1.md
```

```sh
lanes-edit.sh who --lane openRepoProject-1     # what this lane holds open
lanes-edit.sh who --landing opensoft/brett-wip # the Rule 6 merge hold on a repo
```

`who --landing` reads **LANES.md's own Rule 6 lines**, not the logs, because
those are written for every lane, before this amendment and after it. Landings
are counted as distinct `(lane, repository, PR)` **triples**, never as raw
`LANDING` lines: a retry re-posts `LANDING` for the same PR, and the register
holds 571 such lines for far fewer landings. The repository is part of the key
because one lane landing into several repositories is this estate's norm —
keyed on `(lane, PR)` alone, a lane's `LANDED` on one repository closed its own
still-open `LANDING` on another whenever the two PR numbers matched, and the
merge hold went invisible. The repository is lower-cased in the key only, so a
`LANDED` spelled `OpsxFactory` still closes a `LANDING` spelled `opsXfactory`.
Both sides are resolved through `repos.tsv` before they are compared, so a
`LANDED` into `opensoft/OpsxFactory` closes a `LANDING` into `OpsxFactory` —
one repository the register writes both ways, 70 Rule 6 lines against 23 at
`8f9c04d` — the triple's repository is the canonical `owner/repo`, and an
alias the table does not know keeps its own spelling.

**A `LANDED` closes the `LANDING` it answers, paired by `(lane, PR)` in file
order.** Every `LANDING` in the register carries `into <repo> main`; most
`LANDED` lines do not — 300 of 329 on 2026-09-12 — so keying a `LANDED` on the
repository *it* names keyed those 300 on the empty string, where they could
never close the repository-qualified `LANDING` they belonged to. Measured over
the real register at `ee0e07c`, that reported **232 open merge holds** where
the genuinely open count was **one**: on cutover day `who --landing` would have
told the first lane to ask that essentially every repository it wanted to land
into was held. So the *pairing* is by `(lane, PR)` — a `LANDED` closes the most
recent still-unmatched `LANDING` of that lane and PR, and the pair's repository
is the **LANDING's** — while the *result* still keys on the triple, which is
what keeps a `LANDED` on one repository from closing a `LANDING` on another.

A `LANDED` that *does* name a repository must name that `LANDING`'s. If it does
not, it closes nothing and is printed against the repository it names as

```text
unpaired LANDED  opensoft/repoOTHER#32  lane repoT-1, … — the open LANDING for
  (lane repoT-1, PR #32) is on opensoft/repoT, so this closes nothing
```

rather than being dropped: an append-only register is never rewritten, so a
line no tool mentions again is a line nobody will reconcile. One consequence is
worth knowing: when a lane has two `LANDING`s open on one PR number in two
repositories and lands the **earlier** one while naming its repository, the
`LANDED` reads as unpaired and both holds stay open until the second lands.
Two holds reported where one is real is the safe direction, and the shape is
rare; a `LANDED` naming a repository at all is one line in eleven.

A `LANDING` past **Rule 6's thirty minutes** with no `LANDED` is marked
`STALE (Rule 6: >30 min)` and still listed — the line is reported, the reader
is told it is past the window. After the register's holds, the lane logs are
reported under `from lane logs (secondary):`: they are evidence beside the
register, never instead of it.

**An empty answer is an answer.** `who --lane <lane that holds nothing>` and
`who --landing <repo with no hold>` print `none open …` and exit **0**; 8 is
reserved for genuine absence — a lane with no log file, or an object no line
anywhere names. A script that gates on `if who --landing <repo>` must be able
to read the healthy case as success.

`--home owner/repo` supplies the home repo for a lane whose log has no
`STARTED` line yet, which is what `#<n>` needs to expand. It is an option of
`claim`, `release`, `who`, `log` and `lane-end` — **five**. It is resolved through `repos.tsv` and
then **validated** against `owner/repo`, and it is **refused (exit 2) where the
lane's own `STARTED` line already answers the question**, so the log and the
flag can never disagree. All five resolve it **after the fetch**, because the
`STARTED` line that refuses it may be a peer's and live only on `origin/main`.
Unvalidated it was a hole straight through the alias discipline: `--home 'not
a repo'` wrote `not a repo#42` into the log — a line the log's own parser
cannot read back, in a file nothing ever rewrites.
`lane-start` checks its own answer the same way, so a checkout whose `origin`
is a path or a mirror records `home unknown` rather than something every `#n`
in that lane would then inherit.

### Liveness

**One implementation**, in `lanes-edit.sh`, which `lane-start` asks for through
its internal `live-holder` subcommand. Two copies would drift, and this is the
check that decides whether a lane name is free.

Amendment 8 adds a second read over the same records, keyed on the **window**
rather than on a lane: `window-session <tmux session>:<window id>` prints the
live record whose own `tmux` field names that window —
`<uuid> <tmux> <name> <pid> <profile>`, `\037`-separated, **0** with the
record, **8** when the records were read and none is in that window, **1** when
they could not be read at all. Where several live records name one window — a
session that outlives the window it started in keeps the `tmux` value it was
born with — the most recently updated one wins, so the answer does not depend on
which the filesystem listed first. The three live tests are shared with
`live-holder`; the two that are about a *lane* — the row's ids and the
`nameSource` rule — are not applied, because a window holds one interactive
session whatever it is called, and the record's name is reported rather than
believed. The profile is read off the record's own path, never from the
environment of whoever is asking.

A lane is LIVE when a session record **on this workstation** carries one of the
row's transcript uuids, its `status` is not one of `ended`, `exited`, `dead`,
`stopped`, its pid is alive, and `/proc/<pid>/stat` field 22 still equals the
`procStart` the record wrote down. Every uuid in the row's session cell is
tried, not only the last: a lane whose earlier lineage is still running is
still held.

A record's `name` is evidence about *another* lane only when a person or a
`--name` set it. **The rule is the SET: EXPLICIT is `{user, peer}`, and
everything else — `derived`, `auto`, any other value, and no field at all — is
MACHINE**; a record is skipped for a differing name only when its `nameSource`
is EXPLICIT. The census is evidence for the set, not the rule, and it moves:
measured across this workstation's records at 2026-09-11T21:04Z, `derived`
273, `user` 31, `peer` 9, `auto` **0**, and 26 records carrying no
`nameSource` at all — which is why "no field" has to be named in the rule
rather than left to a census that happens to contain a value today.

This is a fix, not a preference. On 2026-09-11 this orchestrator's own record
read `name: openrepoproject-63, nameSource: derived` while it held lane
`openRepoProject-1` — pid alive, `procStart` matching, status `busy` — and the
old filter skipped it on the name alone, so `lane-start --dry-run` reported *no
live session holds openRepoProject-1* and a second window would not have been
refused the lane. After the operator ran `/rename openRepoProject-1` the same
record read `openRepoProject-1` / `user`, and the check reported the holder.
Records are enumerated with `find … -path '*/sessions/*.json'`, never a
one-level glob: team profiles live two levels down.

A holder recorded on **another workstation** reads
`UNKNOWN (records are local to <ws>; ask @<lane> or read its handoff)`, never
`NOT LIVE` — session records are local files, and this machine has no way to
make that claim about another.

**And so does a read this workstation could not perform.** `live-holder` has
three answers and never two of them conflated: **0** with the holder, **8** for
"the records were read and nothing live holds this lane", and any other non-zero
for "I could not read them" — an unreadable tree, an unreadable record, a
permissions or IO fault. `lane-start` renames a window on 8, so mapping a failed
read to 8 as well is exactly how a running lane loses its address: the rename
mints `<lane> (2)`. `who` prints that third answer as
`UNKNOWN (this workstation's session records could not be read…)`, for the same
reason it never says `NOT LIVE` about another machine.

**Every row `who` reads comes from `origin/main`, like the logs.** The session
cell, the handoff path and the workstation column are read with
`git show origin/main:lanes/LANES.md` after the fetch — nothing in `who` reads
the working tree. A row that existed only on `origin/main` used to lose the
resume uuid and the handoff path, which are the two things `who` exists to hand
over; and a peer's *uncommitted* edit to column 3 turned a lane on Raven into
`NOT LIVE`, which is the confident false report that sends a reader to
`claim --force` against a live lane.

**The one read that also consults this checkout is the `live-holder`
subcommand, and only its id SET** — the union of the published row's transcript
uuids with this checkout's row's. A session stamps its own uuid on the row with
`replace-in-row`, and that write is a local commit for as long as its push takes
(and longer, whenever a peer's file is blocking the rebase): read from
`origin/main` alone, the rename gate would not see the uuid of the session it is
being asked to rename over, would answer 8, and `lane-start` would take the name
— which is exactly what mints `<lane> (2)` and costs a running lane its address
(AGENTS.md rule 7). Liveness fails closed, so an id `origin/main` has not seen
yet is one more reason to REFUSE a rename and never a reason to allow one, and
nothing that PRINTS uses the union: `who` reads the published row and nothing
else.

### Exit codes

| code | meaning |
|---|---|
| 0 | done |
| 1 | environment — no register, no writer |
| 2 | refusal — bad arguments, the object is held, an unknown alias, a checkout that cannot be rebased |
| 3 | rebase conflict — nothing pushed, the edit is a local commit |
| 4 | the mutex could not be taken within 60s |
| 5 | an edit moved more than one line and was refused |
| 6 | `git add` / `commit` / `push` failed |
| 7 | `CLAIM-LOST` — another lane's claim landed first (`claim` only) |
| 8 | no record — and no other meaning |
| 64 | `swapped`'s own usage error — never the dispatcher's 2 |

3 to 6 are the codes this helper already used; 7 and 8 were free.

**8 means "there is no such record", and nothing else.** `who <object>` exits 8
when no line anywhere names the object; `who --lane <lane>` exits 8 when the
lane has no log file; the internal reads `lane-start` and `lane-end` use follow
the same rule — `lane-objects` exits 8 for a lane with no log, `live-holder`
exits 8 when the session records were READ and no live one holds the lane
(the ordinary answer for a parked lane) and never when it could not read them,
`register-row` exits 8 when the PUBLISHED register has no row for the lane
(and **2**, not 8, for a name that is not lane-shaped at all — a malformed
argument is a refusal, never an absence), `resolve-home` exits 8 when the lane
has no home on record and none was passed, `swapped` exits 8 when no lane is
swapped on the workstation, `idle-holders` exits 8 when no live but idle
session holds one of the row's earlier ids, and `window-session` exits 8 when
no live session is in the window.

**`swapped` exits 64 on a usage error of its own, never 2.** The launcher gates
its whole Amendment 8 degrade on a `2` from `swapped` meaning one thing —
*this `lanes-edit.sh` predates Amendment 8 and has no such subcommand*, which
is the dispatcher's unknown-subcommand code. A caller's own bug must not be
indistinguishable from an old helper at the one place the degrade is decided,
so `swapped` answers `0` rows, `8` none swapped, `64` a bad call, and leaves
`2` to mean *no such subcommand* alone. `session-start` is the one subcommand that never exits
anything but **0**: it is a hook.
Every other non-zero code from any of them is a FAILURE, and `lane-start`
and `lane-end` treat only 0 and 8 as answers: anything else is a refusal
(exit 1) that prints the helper's own stderr and renames and writes nothing.
They used to return 1 for both, and both scripts read 1 as an answer — a
broken helper made `lane-end` end a lane that was holding an open claim while
telling the next session it was pre-cutover, and made `lane-start` announce
`no live session holds <lane>` about a session that was live in another
window.

### Before the cutover

A lane with **no log file** has not written a line since this amendment landed,
and nothing pretends otherwise:

- `who --lane <lane>` says `no log for <lane>; see its row's state cell` and
  exits 8;
- `lane-end` falls back to the old substring scan of the state cell, and says
  that is what it is doing — over BOTH this checkout's row and the published
  one (`register-row`), either of which showing a hold being a refusal: a fetch
  does not move a working tree, so a peer's `LANDING` appended to the row and
  pushed was invisible to the one path that still decides a merge hold from
  prose;
- `who --landing` still sees that lane, because it reads `LANES.md`;
- existing rows keep their state cells untouched. Nothing is migrated and no
  history is rewritten.

### `lane-start` and `lane-end` under this amendment

`lane-start` appends `STARTED` (or `RESUMED`, following its launch decision)
**after** the row write, carrying `home owner/repo` taken from
`git remote get-url origin` of the lane's own directory. `<repo>-<n>` is a
label, not a scope; this line is the only thing that says where a lane actually
lives. A checkout with no `origin` records `home unknown` rather than a guess,
and says so.

**The home is canonical.** That spelling is resolved through `lanes/repos.tsv`
*before* the line is written, and every comparison of an object's repository
against a home resolves both sides — because a home is inherited by every `#<n>`
that lane ever writes. A checkout whose `origin` still said
`opensoft/codexFactory` wrote object keys that could never collide with another
lane's `codeXfactory/codexFactory#<n>`, so two lanes held one GitHub issue under
two keys and nothing detected it. A spelling the table has no row for is
recorded exactly as `origin` gives it, with a note asking for a row — guessing
is how the fifth spelling of one repository got into the register.

`lane-end`'s refusal is now **exact**: every object whose last line in this
lane's own log is open is named, with the takeover case naming its own fix, and
the recovery it prints is in the helper's real CLI grammar — one of

```sh
LANES_LANE=<lane> lanes-edit.sh log LANDED <object> → <merge sha>    # the PR merged
LANES_LANE=<lane> lanes-edit.sh release <object> "<why>"             # the claim is given up
LANES_LANE=<lane> lanes-edit.sh log CLOSED <object>                  # closed without merging
```

The arrow is its **own argument**. Quoted into the free-text slot
(`log LANDED <obj> "→ <sha>"`) the sha lands *after* the ` — `, the line stops
matching `LANDED → <sha>`, and the register's Rule 6 line loses the merge sha
for good in a file nothing rewrites. There is no `MERGED` verb at all, and
`log RELEASED` is refused — `release` is the subcommand, and it posts the Rule 1
comment too.

`--force` records what it overrode, in the grammar's own shape:

```text
ENDED — lane X, session <uuid>@<ws>, <UTC>, lane:X — forced; open: opensoft/repoX#11, opensoft/repoX#12
```

` — ` occurs exactly **twice**, which is the guarantee that lets one parser read
every line, and the free text names the objects the lane's own log showed open
rather than blaming a state cell the script never read. **The writer enforces
that**: it refuses any payload or free text containing ` — `, or a newline,
before the lock and before anything is created. It
also prints a generated handoff fragment on **stdout** — `## Done (RELEASED,
CLAIM-LOST, CLOSED, LANDED)` and `## Open (CLAIMED, TAKEOVER, OPENED, LANDING,
WITHDRAWN)`, from the log, each header naming the set it partitioned by — to be
pasted into the handoff the row points at,
because a handoff written from memory is how an object goes missing between two
sessions of one lane. That fragment is the only thing `lane-end` writes to
stdout.

A `CLAIMED` another lane has taken over is listed under `## Open` as
`superseded by TAKEOVER (lane:<X>) — release it`. It belongs there because it is
still this lane's last line on the object and only this lane's `release` closes
it; what it is not is work the next session still holds. The fragment is the one
surface here that becomes a **durable document**, so an object `who` gives to
another lane must not be pasted into the next handoff as simply open — the
refusal, `who <object>` and `who --lane` all carry the takeover already.

### Archivability

A lane's log is archivable when the lane is `RETIRED` and every object in it is
`CLOSED`, `LANDED`, `RELEASED` or `CLAIM-LOST`. **Nothing prunes
automatically.** The amendment states the rule and stops there.

## Swap and restart (Amendment 8)

**DRAFT, 2026-09-12, awaiting Brett Heap's word** (`brettheap/new-workstation#15`).
A **swap** is a planned stop — a usage reset, a profile switch. A **restart** is
the launch that follows it. The lane has to survive the gap, and on
2026-09-12 it twice did not: the restart opened a **new tmux session**, which
loses the window name that carries the lane, and the reset minted a **new
transcript uuid** while the row's session cell still ended on the old one.

Neither half adds a file. The **record** a swap leaves is the lane's own
`PAUSED` line in `lanes/log/<lane>.md`, payload
`swap; window <tmux session>:<index>; workstation <ws>` — an ordinary event line
under Amendment 7's grammar, not a new kind of thing:

```text
PAUSED — lane openRepoProject-1, session 09dd34d1-…@Eagle, 2026-09-12T16:52:39Z, lane:openRepoProject-1 → swap; window claude-team-05b-20260912102132-2699:0; workstation Eagle — on Brett Heap's word: shutdown and i will reset the usage
```

A lane is **swapped** on a workstation when that `PAUSED` is its **last
lane-kind line** — no later `RESUMED`, `STARTED`, `ENDED` or `RETIRED`. The line
above is real, and that lane is *not* swapped today, because a `RESUMED` follows
it seven minutes later.

Two read-only subcommands. **Neither ever writes**, and both honour
`LANES_NO_FETCH=1` — the launcher passes it, because a record this workstation
wrote is already in its own clone and a restart must not wait on the network.
In that mode they still read `origin/main`, exactly as they do after a fetch;
what is skipped is the fetch, never the ref.

### `swapped [<workstation>]`

The lanes a swap paused on a workstation and nothing has resumed. Default
workstation is `hostname -s`. One row per lane, **tab-separated, lane first**:

```console
$ lanes-edit.sh swapped Eagle
repoSW-1	2026-09-12T10:00:00Z	claude-team-05b-20260912102132-2699:0
repoSW-5	2026-09-12T11:00:00Z	sess-five:5
```

`<lane>`, `<UTC>`, `<window>` — the window being the `window <s>:<i>` the
`/swap` recorded, which is where that lane was. **Exit 0** with rows, **8** with
none (and the reason on stderr, so stdout is only ever rows). A launcher takes
the first row's lane as its default and hands it to `lane-start --confirm`.

**The rows are in LANDING ORDER — most recently landed first — and not in UTC
order.** Amendment 7's file-order rule orders one lane's own lines and does not
reach across two lanes' files, and two lanes' UTCs are two clocks: they may be
two workstations' (which share no order at all) or one workstation's mid-jump —
this one was observed stepping ±25 s in bursts, and a log commit landed whose
content carried a UTC 26 s after its own committer date. Git's push
serialization is the one order both lanes really share, and it is the same
arbiter `claim` already uses to decide a race. So the key is the position of the
commit that **added** each lane's `PAUSED` line, measured as its distance from
the tip of `origin/main` — history, not a committer date either. The UTC stays
in the output as **information**, and decides nothing. The example above is the
test's own: `repoSW-5` carries the later UTC and landed first, so it is second.

### `session-start`

The whole output of Claude Code's **SessionStart hook**. It reads the hook's
JSON on stdin (`session_id`, `source`, `cwd`) and the tmux window name, resolves
the lane — **the window name first, then the session id against every row's
session cell** — and prints ONE block. The working directory is in the payload
and is deliberately *not* read as a lane: the working directory confers no lane
(Amendment 6(a)), two lanes share one all day, and every nested checkout in the
xFactory estate shares its parent's.

**It never writes, it never touches the network, and it always exits 0** —
including on garbage stdin and on no register at all, which every other
subcommand refuses. A hook that fails is a hook that breaks the session it was
meant to orient; a hook that fetches puts the network in front of every session
start on the workstation, and R-A8-1 rules it out for exactly that reason.

So every line of the block is **this checkout as it last stood**, and the block
says how long ago that was — the line `ssb_tail` prints **unconditionally**, as
the last line of every block whichever branch wrote the rest (Amendment 8(e)):

```text
as of 4m ago (no fetch)
```

The age is `.git/FETCH_HEAD`'s mtime — rewritten by every fetch and by nothing
else — rendered `<n>s`/`<n>m`/`<n>h`/`<n>d ago`; `never` where this checkout has
never fetched, `unknown` where it cannot be read. Neither is a failure and
neither costs a network call. A block that says `as of 4d ago (no fetch)` is a
block a reader knows not to trust about another workstation's lane, which is the
whole of what makes an unfetched read honest.

The lane's session is the one the row records, and the hook says so:

```console
$ lanes-edit.sh session-start   # stdin: {"session_id":"4a91f1dc-…","source":"resume","cwd":"…"}
LANE openRepoProject-1 — handoff handoffs/openRepoProject/session-handoff-2026-09-11-lane-openRepoProject-1.md — row session 4a91f1dc-46dc-48be-a75a-1789fab038d0
stamp the handoff RESUMED (Rule 3) and follow its top block
open: CLAIMED brettheap/new-workstation#15; OPENED brettheap/new-workstation#16; OPENED opensoft/workBenches#63
as of 4m ago (no fetch)
```

The first line's last field reads `row session none recorded` where the row
carries no id this hook can read — the rows that hold only `session_…` footer
ids, which have no transcript uuid to mismatch *against* and are therefore not
reported as a mismatch at all.

The second line is one of three, and it is **derived** rather than assumed from
the ids agreeing: the handoff the ROW names is read and grepped for the line
this session would owe, because a window started by a bare `claude` has no stamp
and does still owe one. Already stamped by the launcher → `handoff already
stamped by lane-start — follow its top block`; no handoff in the row at all →
`the row records no handoff path — there is none to stamp or to follow`.

The third line is the lane's open objects, `who --lane`'s answer on one line;
`open: none open` when it holds nothing, and
`open: no log for <lane> (pre-cutover lane) — see its row's state cell` when it
has no log at all.

**Two different mismatches, and the block says which.** An id the cell *carries*
but does not end on is a superseded transcript of this lane — the 2026-09-11
wrong-lineage resume. The conversation in this window is not the lane's, so it
is left rather than carried on with:

```text
WARNING: this is a superseded transcript of lane repoSS-1; the live one is <U>; you resumed <V> — exit this session and run: lane-start repoSS 1
as of 4m ago (no fetch)
```

That mismatch has one **sub-branch**: where the lane's newest row stamp says
`unknown`, the cell's last id names a transcript this directory does not have, a
relaunch would take the same title fallback again and record nothing either — so
the cure there is the recording act, not a relaunch:

```text
WARNING: this is a superseded transcript of lane repoSS-1; the live one is <U>, which the row records as `unknown` — a relaunch would record nothing either, so run: lane-start --no-launch repoSS 1
as of 4m ago (no fetch)
```

An id the cell does not carry **at all** is the harness having minted a new
transcript with nobody acting. The lane is right and the row is simply behind,
so the cure is the act that reads the live record in this window and appends
that uuid to the cell:

```text
WARNING: this window is lane repoSS-1 whose current session is <U>; this session <V> is in no row — the harness minted a new transcript — run: lane-start --no-launch repoSS 1
as of 4m ago (no fetch)
```

There is no third mismatch, and **no branch names `/resume` or the picker**:
neither is a lane surface, and a reader sent back through the picker performs
the very failure this block exists to catch. Every command is printed **filled
in** — the hook holds the lane, so `<repo> <n>` reads `repoSS 1` by the time
anyone sees it, and a lane named before the `<repo>-<n>` rule gets
`--dir <path> browser-ui-repair` rather than the bad split `browser-ui repair`.

And when neither the window nor the register answers — the one branch that keeps
its placeholders, because no lane is known there to fill them in with, unless
the window name itself parses as `<repo>-<n>`:

```text
no lane bound to this window — run: lane-start <repo> <n>
as of 4m ago (no fetch)
```

`source` is one of `startup`, `resume`, `clear`, `compact`, `fork`. A
**compact** prints **nothing**: the same conversation carries on in the same
window under the same id, and a block there would announce a lane's identity
into the middle of a session that already has it. Everything else gets the
block — a **fork** included, which is a new attachment to the lane's
conversation — and an unknown or missing `source` is treated as a `startup`
rather than dropped.

Installing it is user-local configuration, not part of this repository:
`hooks.SessionStart` in `~/.claude/settings.json`, command
`~/projects/xFactory/lanes-edit.sh session-start`.

### What Amendment 8 does not add

**No new script and no new path.** `swapped`, `session-start`,
`window-session` and `sibling-filter` are subcommands of the writer that already
exists, and every one of them is a **read**: AGENTS.md rule 1's list of writers
(`append-row-status`, `replace-in-row`, `append-line`, `add-row`, `log`,
`claim`, `release`, `commit`) and rule 8's list of tooling paths are both
unchanged by this amendment.

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
  rules, and this checkout is shared with `handoffs/` and `workspaces/` and
  with every other lane on this workstation.
- **Committing `LANES.md` to a governed or product repository.** It lives on
  `main` of the workspace repository and nowhere else — never in an
  aggregation, a member, or any repo that is released, pinned or swept.
  (Before Amendment 5 this line read "it stays on `lanes`"; the branch that
  named is retired.)

## Snapshots

`LANES.md.snap-*` / `LANES.md.bak-*` at the aggregation root are the pre-git
backup habit. They are no longer required — git history is the backup — and
they are gitignored on `main`, so leaving them is harmless. The last pre-git
snapshot is kept deliberately:
`~/projects/xFactory/LANES.md.snap-20260909T002735Z-pre-git`.

## Adopting this on another workstation (Raven)

```sh
git clone git@github.com:opensoft/brett-wip.git ~/projects/brett-wip
~/projects/brett-wip/scripts/link-estates --dry-run   # rehearse
~/projects/brett-wip/scripts/link-estates             # place the symlinks
```

The warning from Amendment 3's "Raven setup (operator, Brett)" block still
stands and the linker does not do it for you: **diff Raven's local `LANES.md`
against this one and append its missing rows with `lanes-edit.sh add-row`
BEFORE the local file becomes the symlink.** Raven's file may hold rows this
register has never seen. `link-estates` never deletes a real file — it moves
one aside as `<path>.pre-link-estates-<UTC>` — so the content survives either
way, but a row nobody re-appends is a row nobody reads.

`link-estates` also places `~/.local/bin/lane-start` and
`~/.local/bin/lane-end` (creating that directory if it is missing, and saying
so when it is not on your PATH). The helpers resolve the register and its
writer from their own real path, so the symlink is all they need.

Also drop the retired worktree if this workstation still has one:
`git -C ~/projects/xFactory worktree remove .lanes` (Eagle did this on
2026-09-10).

## Reading the history from before the move

`git subtree add` imports commits unchanged, so the 1242 register commits made
between 2026-09-09 and the move carry their pre-move path (`LANES.md`, at the
root of the orphan branch), and git's default history simplification stops at
the subtree merge. Both halves are one command each, in
`~/projects/brett-wip`:

```sh
git log --oneline -- lanes/LANES.md              # since the move
git log --oneline pre-move/lanes -- LANES.md     # the 1242 up to the import
git log --oneline --full-history -- LANES.md     # 1256: those, plus the 12 the
                                                 # orphan branch took while the
                                                 # move was in flight, which came
                                                 # in on a later sync and are not
                                                 # under the tag
git show <sha>:LANES.md                          # a lost row, pre-move
git show <sha>:lanes/LANES.md                    # a lost row, since
```

`pre-move/lanes` is an annotated tag on the last commit the orphan branch ever
took. The same shape applies to `pre-move/handoffs` and
`pre-move/workspaces`.
