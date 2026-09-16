# `lanes/LANES.md` — how the estate lane register is stored, and the commands that write it

**THE TOOLING LIVES HERE; THE DATA LIVES IN YOUR WORKSPACE REPOSITORY.**
Amendment 9, 2026-09-13. This manual and the four commands it describes —
`lanes-edit.sh`, `lane-start`, `lane-end` and `link-estates` — came to
`opensoft/openRepoTools` from `opensoft/brett-wip` with their history, because
a `<user>-wip` is a person's DATA and its own rules file says so: "No secrets
and no code". They are INSTALLED COMMANDS now, placed by
`openRepoTools --install`, and none of them is a file in anybody's workspace
repository any more.

**So every command below is typed by bare name**, and every one of them finds
your register the same way: through `$AGENT_PROTOCOL_ROOT/workspace.yaml`
(default `~/.agents/workspace.yaml`), which names your workspace repository and
where it is checked out. `openRepoTools wip init` is the one command that
creates that repository and writes that file. A helper that cannot find it
refuses, exit 1, naming that command — it never guesses, and it never falls
back to a path derived from its own location.

**Moved 2026-09-10 (Amendment 5).** The register lived on the orphan `lanes`
branch of `opensoft/xFactory` from 2026-09-09; it moved to `main` of the
person's workspace repository — for Brett, `opensoft/brett-wip` — ratified by
Brett Heap 2026-09-10 ("since we now have the user-wip repo this is a better place
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
| repository | `<org>/<login>-wip` — the person's own workspace repository, private, org-owned (the `<user>-wip` form, `openRepoShape#81`); named by `repository:` in `~/.agents/workspace.yaml`. Brett's is `opensoft/brett-wip`; Scott's would be `opensoft/scott-wip`, and the commands below are the same commands |
| branch | `main`. Direct commits are the norm there **by design**: the repository is excluded from the organisation's PR-only ruleset precisely so a per-edit register commit can land |
| checkout | `~/projects/<login>-wip/`, named by `path:` in `~/.agents/workspace.yaml` and created by `openRepoTools wip init` |
| how every command finds it | `$AGENT_PROTOCOL_ROOT/workspace.yaml` — `repository:` and `path:`, and nothing else. Never from the command's own location (Amendment 9(a)) |
| the register | `<the checkout>/lanes/LANES.md` |
| the path every lane already uses | `~/projects/xFactory/LANES.md` — a **symlink** to `<the checkout>/lanes/LANES.md` |
| the writer | `lanes-edit.sh`, an installed command in `~/.local/bin` (still symlinked as `~/projects/xFactory/lanes-edit.sh`, which is what Amendment 8(e)'s `SessionStart` hook names) |
| the two ends of a lane | `lane-start` and `lane-end`, installed commands — **regular files, not symlinks any more** |
| their tests | `tests/test_lane_helpers.sh` in `opensoft/openRepoTools` — run it from a checkout of that repository; it touches nothing real |
| the object logs | `<the checkout>/lanes/log/<lane>.md` — one per lane (Amendment 7) |
| the alias table | two layers: `repos.tsv` shipped by openRepoTools and installed beside the commands, then `<the checkout>/lanes/repos.tsv` where you keep an override (Amendment 9(b)) |
| who places the symlinks | `link-estates`, an installed command. It places the handoffs links, the register link and the `lanes-edit.sh` link — **and no longer the two `~/.local/bin` ones**, which `--install` owns |
| who installs all of it | `openRepoTools --install` (thirteen files, idempotent, all-or-nothing) |
| the lane alias table | `<the checkout>/lanes/aliases.tsv` — `<old><TAB><new><TAB><UTC>`, written by `lane-rename` and by nothing else, resolved by every reader that takes a lane name (Amendment 16(e)) |

Why `main` of the workspace repository and not the aggregation's: the
aggregation repo's `main` is PR-only (org rulesets `xFactory Tier-1 main
protection`, `required-checks-main`, `Require Code Owner Review`, all scoped
to `~DEFAULT_BRANCH`), so a per-edit commit cannot land there — which is why
the register spent 2026-09-09 to 2026-09-10 on an **orphan `lanes` branch** of
that repo instead. The workspace repository has no such gate and no product
code at all, so the register can sit on its `main` next to the handoffs it
cross-references. Nothing here is ever released, pinned, swept or bumped.

**The register no longer owns its whole checkout.** The workspace checkout
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

# SET a row's state cell — the common case, and it REPLACES the cell
# (Amendment 13(a)). The UTC is stamped by the writer.
lanes-edit.sh set-row-state my-lane "LANDED · PR #123 merged as abc1234"

# the NARRATIVE — what the lane did, found, launched, left — goes to the
# lane's own log, never to the row (Amendment 13(b))
LANES_LANE=my-lane lanes-edit.sh log NOTED lane:my-lane "rebased on main; the flake is the fixture's clock"
LANES_LANE=my-lane lanes-edit.sh log RULED lane:my-lane → opensoft/openRepoTools#29 "Ratify as drafted"
lanes-edit.sh history my-lane --since 2026-09-13T00:00Z

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

Every mutating subcommand FIRST resolves its `<lane>` — and `LANES_LANE` — to
the register row's own spelling, case-insensitively, before it reads or writes
anything, so a name typed in another case edits the row that is there instead of
creating a second one; two rows differing only by case are a refusal naming both
(Amendment 15). Then it does the same five things:

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
edit survives as a local commit — but an aborted pull is not proof it never
reached origin: this checkout is shared with every lane on the workstation, so
the very next write out of it can pull this dangling commit onto its own and
push both together (#32). LOOK first: `git -C <the workspace checkout> fetch
origin main` — if THAT fails, STOP and retry it; a stale or unreachable origin
proves nothing either way, and is not permission to reset and redo. Only once
the fetch succeeds do you check by CONTENT whether your own commit is already
there, never by sha: the very peer write this recovery exists for carries a
dangling commit by rebasing it onto a newer base, which changes its hash, so
`merge-base --is-ancestor` alone can still say "not there" once the change is
actually published. `git -C <the workspace checkout> cherry origin/main <your
commit> | grep -c '^+'` compares by patch instead and still finds it; 0 means
it is already there, in which case STOP. Only once fetch succeeded AND this
prints something other than 0 do you read your edit back with
`git -C <the workspace checkout> diff origin/main..HEAD -- lanes/LANES.md`,
then `git -C <the workspace checkout> reset --hard origin/main` and redo it on
top of the peer's version.

The script spells no path of its own: it finds the checkout root with `git
rev-parse --show-toplevel` from its own directory and derives the pathspec
`lanes/LANES.md` with `--show-prefix`, so the clone may live anywhere. The
overrides `LANES_REPO`, `LANES_PATH` and `LANES_BRANCH` exist for tests.

## Starting and ending a lane

### One word: `lane`

```console
$ lane                          # the lanes, numbered, and ONE question: which?
$ lane openRepoShape-2          # straight to that one, asking nothing
$ lane openRepoShape-2 team-05e # …under another account (the late swap)
$ lane --all                    # every repository, grouped
```

**This is the word, and it is Brett Heap's own** (lane-collision-protocol
**Amendment 18 Addendum 1**, ratified 2026-09-14T14:05:54Z verbatim *"ratify the
addendum"*), out of his two messages that morning, verbatim: *"i dont understand
in another window i want to attach to that lane. what command do i use to do
that?"* and *"this is too hard for users. we need simple way to list the lanes
and then pick one to bind."*

A bare `lane` prints clause (i)'s listing as a **numbered pick** — available
lanes first (PARKED, or a binding this host proves dead), lanes **LIVE HERE**
next with where each one is (`window <n> of this session`, `detached session
<name>`), lanes **bound elsewhere** last with the workstation holding them;
closed and dormant lanes hidden (Amendment 19) — and asks **one** question:
`which? [1-N, f = a new lane at the next free position (<repo>-<n>), q]`. Inside
a checkout it is that repository's lanes; outside one, or with `--all`, every
repository, grouped.

**Three branches, one per state** (clause (i-2)):

| the lane is | `lane` does |
|---|---|
| **available** — PARKED, or a binding this host proves dead | `cd` to its **own recorded directory** and relaunch it **through the launcher** under its **own recorded profile**: `pclaude --lane <lane> <profile>`. Never a bare `lane-start` under whatever profile the shell carries, which outside a launcher session is the default config directory and therefore the wrong account. `lane <name> <profile>` names another one — the late swap |
| **LIVE HERE** | **attaches, and never starts a second process** (clause (h)). Inside tmux: `tmux move-window -a -s <session>:<@id>` then `tmux select-window -t <session>:<@id>` — the `@id` on both, so tmux resolves the window inside the session the record named or not at all — and where the window is already in this session, only the select. With `--switch`: the same select first, and `tmux switch-client` only after it worked. Outside tmux: `tmux attach -t <session>:<@id>` — the window named in the attach itself, which tmux resolves in that session or refuses — with that window selected first |
| **bound elsewhere** | clause (c)'s question, the **handoff request**. That request is `brettheap/new-workstation#38`'s act 4 and does not exist yet, so until it does `lane` **refuses and names where the lane is bound**. It never offers a launch: a second session on a lane another workstation holds is the collision |

**The window is matched by its id AND its session name.** tmux reissues `@` ids
from `@0` when its server is replaced — measured here on 2026-09-13, where 0 of
5 recorded windows resolved — so an id alone would attach to whatever pane has
since been given it. Where the two disagree `lane` refuses and names both.

**With no terminal on stdin it lists, suggests and asks nothing** (clause
(i-3)): an agent's stdin is not a terminal. **Bare `lane-start` is `lane`**
(clause (i-4)) — one implementation, and clause (i)'s ruled behaviour stands.

`lanes` is the same rows as a **read**: every column, closed lanes included, no
question. `/restart` is the act from **inside** a running session. And `restart`
is gone from the PATH — the section below.

### `lane-start` and `lane-end`

The lane rule, ruled by Brett Heap 2026-09-10: **lane = tmux window name =
Claude session name**, in the form `<repo>-<position across, left to right>`.
The working directory confers NO lane — two lanes may share one; a window
still called `claude` has no lane at all; and whether a name is free is
decided by whether the row's recorded session id is **live**, never by whether
a row exists.

**A lane name is ONE name under any case, and the register row's spelling is
canonical** (Amendment 15, in force 2026-09-14T00:07:18Z). `lane-start
openxfactory 2` and `lane-start openXfactory 2` are the same lane: every lookup
of a name — the row, the object log, the tmux window, the session name,
`LANES_LANE`, and every `<lane>` argument of the four commands — compares
case-insensitively, and the row's own spelling is what the window is renamed to,
what the launch is `--name`d with, what the log file is called, and what every
line and stamp writes. A name typed in another case RESOLVES to it and is never
written as typed. A lane with no row yet takes the checkout's REAL directory
name for its `<repo>` half, resolved under the projects root case-insensitively;
two directories differing only by case are a refusal naming both, because
choosing one of them is choosing which repository the lane is in. Where the
register already holds two rows differing only by case, **every writer refuses,
naming both**, until they are merged by hand — 15(d): the newer row's session
id(s) appended to the older row's session cell, in order, and the newer row
removed in the SAME commit, whose message names both spellings. `lanes-edit.sh
canon-lane <name>` is that resolver as a read, and the one all four commands
share: **0** with the canonical spelling (the typed one where no row matches, so
`add-row` can still create a lane), **2** for the pair, **64** usage — and that
2 is RELAYED by `lane-start`, `lane-end` and `lane` rather than carried past,
because the pair may be on `origin/<branch>` while this checkout still holds one
row. `add-row` asks the published register as well as this copy of it for the
same reason: a row a peer pushed is a refusal here, naming it and the `git pull
--rebase` that settles it, and never a second row. The LOG is held to the same
rule — two files under `lanes/log/` whose names differ only by case are two logs
for one lane, and every read and every write under that name refuses, naming
both, until they are merged.

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
   or `--dir <path>`. Both halves resolve case-insensitively under Amendment
   15: `<repo>` to the checkout's real directory name, and the lane to the
   register row's own spelling, which then wins over everything typed;
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
5. the row, through `lanes-edit.sh`: `add-row` when there is none under ANY
   case — it refuses one that exists under another and names it, and the
   liveness check above reaches the RESUME branch for that row rather than this
   one (Amendment 15(a)) — state `LIVE · <UTC> · <verb> by <uuid> (lane <lane>)
   — lane-start on <ws>: row created`, which is Amendment 13(a)'s phrase from
   birth (it was the bare word `STARTING` while the cell was a diary), session
   id `pending — set by the session's first act`,
   `<workstation> / <profile> / <user>` per Rule 10, handoff path
   `handoffs/<estate>/session-handoff-<date>-lane-<LANE>.md` — and
   `set-row-state` when there is one. Never a hand edit. **That state is
   Amendment 6(c)'s stamp**, written here rather than owed to the session
   afterwards — and since Amendment 13(a) it REPLACES the cell rather than
   being appended to it, with the UTC stamped by the writer:

   ```text
   LIVE · <UTC> · RESUMED by <uuid> (lane <lane>) — lane-start on <ws>: window renamed, launching <the command>; dir <dir>; window <ref>
   ```

   **The launch clause comes first and clause (c)'s `dir` and `window` follow
   it**, because the line is capped at 240 characters (Amendment 13, ratified
   decision O1) and a line long enough to be cut must lose what a reader can
   look up elsewhere: `dir` and `window` are sub-fields of this same act's
   `STARTED`/`RESUMED` line in the lane's own log and columns of `lanes`, while
   the exact command this run launched is written down nowhere else.

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
   *is* the messaging address). Four cases, in order: `exec claude --resume
   <id>`, where `<id>` is the **last** uuid in the row's session cell and this
   directory has its transcript (Amendment 6 — a lane is resumed by the id its
   row records, never by its title); the same exact command using the same
   agent's last `PAUSED … transcript <id>` when the row-last UUID has no
   transcript, restoring that exact ID to the end of the session cell first;
   `exec claude --resume <LANE>` when neither exact recorded id resolves but a
   transcript here carries the custom title `<LANE>`, which is the fallback and
   only filters the picker; and `exec claude --name <LANE> --session-id <fresh
   uuid>` for a lane with no history here. A live session in the current window
   remains authoritative over the PAUSED fallback. Anything after `--` is
   passed through to `claude`.

   **And the id it is about to resume is counted first, under two rules and not
   one.** Amendment 18(h)'s is this tooling's: a second LIVE PROCESS on one
   transcript is a refusal naming the pid and the retire act, and the harness
   permits that state — measured 2026-09-15 against `claude` 2.1.270, a
   `--resume` whose id a second *interactive* process holds starts anyway. The
   other rule is the HARNESS'S OWN, asked here because it decides whether the
   `exec` can happen at all: a `--resume <id>` whose id is carried by a live
   record whose `kind` is anything but `interactive` — a `--bg` job, a
   `bg-pty-host` child, the `bg` companion of Amendment 8 ruling (g) — prints
   `Session <id> is running as a background session … Add --fork-session to
   branch off a copy instead` and **exits 1 without starting**. Everything this
   command writes — the row, the object log, the handoff stamp — is written
   BEFORE the `exec`, so a launch the harness refuses leaves a lane recorded
   `RESUMED` by a session that never existed, and in a window `pclaude --lane`
   has just made, tmux prints `[exited]` over the message and closes it. So the
   count is asked on both sides of the current-window test and the refusal names
   where that session is (`tmux switch-client -t <window>`) and how to open it
   (`claude agents`, `claude attach <id>`, `claude stop <id>`) beside
   `lane-end <lane> --retire <pid>`.

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

Sets the row's state cell to `ENDED · <UTC> · lane-end on <workstation>:
window closing; NOTHING IN FLIGHT` — `RETIRED` under `--retire`, which since
Amendment 13(a) is the same write and not a second one — and **refuses (exit 2)
while the row says something is still open**: if the last `LANDING` or
`CLAIMED` in the state cell has no `LANDED`
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
# from a checkout of opensoft/openRepoTools, where the suite lives now:
bash tests/test_lane_helpers.sh     # the shell suite alone, touches nothing real
tests/run.sh                        # the same suite under pytest, SERIALIZED
```

`tests/run.sh` is the way to run it wherever lanes share a workstation
(opensoft/openRepoTools#51): it waits for any live run, takes
`${TMPDIR:-/tmp}/openrepotools-pytest.lock` — `flock` where there is one, a
`mkdir` lock on macOS, which has none — and only then runs `python3 -m pytest
tests -q`. Four suites ran at once on Eagle on 2026-09-14 past a guard written
`pgrep -af '…' | grep -v pgrep >/dev/null`, which never waits: `grep` there is
a shell function whose status is 1 when its stdout is `/dev/null`. The guard
that does wait is anchored, split so it cannot match its own command line, and
followed by the lock:

```sh
pat='^python3 -m pyt'"est"
while [ "$(pgrep -f "$pat" | awk 'END { print NR + 0 }')" -gt 0 ]; do sleep 20; done
flock "${TMPDIR:-/tmp}/openrepotools-pytest.lock" python3 -m pytest tests -q
```

`awk` and not `pgrep -fc`: `-c` is not in every `pgrep` this toolset runs
under, and it is the COUNT and never `pgrep`'s exit status that decides.
`tests/run.sh` is the canonical implementation of this guard — the lines above
are it in one place, for a person with no checkout in front of them.

The suite copies the four commands and the shipped alias table into a sandbox
BIN DIRECTORY, seeds a workspace repository with nothing but data in it, and
writes that sandbox's own `workspace.yaml` to join the two — which is the
world after Amendment 9, exactly. It unsets every `LANES_*` seam first, so
what every case exercises is the DEFAULT resolution and not an override.

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
| a lane's object log | `lanes/log/<lane>.md` — one file per lane, append-only. `<lane>` is the REGISTER ROW'S spelling (Amendment 15); a file left under another case is found by every reader and RENAMED to that spelling once, by the first write that touches it, inside that write's own commit — so git records the rename beside the line appended. Two plain `mv`s through a temporary name, because on a case-insensitive filesystem `mv a A` answers *identical* and renames nothing |
| line 1 of each | `# lane <lane> — object log (lane-collision-protocol Amendment 7)` |
| every other line | one EVENT, in the grammar below |
| the alias table | two layers (Amendment 9(b)): the shipped `repos.tsv` installed beside the commands, then `<the checkout>/lanes/repos.tsv` where you keep an override. `alias<TAB>owner/repo`, case-insensitive. An override row replaces the shipped row for the same alias and adds rows it does not carry; an alias in neither is still a refusal saying to spell it `owner/repo` |
| the only writer | `lanes-edit.sh` (`log`, `claim`, `release`), as for `LANES.md` |
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
| narrative | `NOTED`, `RULED [→ <object>]` (Amendment 13(b)) |
| race | `CLAIM-LOST → lane:<other>` |

There is no `MERGED`: Rule 6's `LANDED → <sha>` is already the post-merge line.

**Every line has an object**, lane-kind lines included — theirs is the lane:

```text
STARTED — lane openRepoProject-1, session 09dd34d1-3afe-43a1-88fc-c33c92c08088@Eagle, 2026-09-11T19:08:12Z, lane:openRepoProject-1 → home opensoft/openRepoProject; estate openRepoProject
```

`PAUSED`, `RESUMED`, `ENDED` and `RETIRED` carry the same `lane:<name>` object
and no payload. So do Amendment 13(b)'s `NOTED` and `RULED` — and `RULED` takes
one optional payload, the object the ruling bears on: `RULED — lane <lane>,
session <uuid>@<ws>, <UTC>, lane:<lane> → opensoft/openRepoTools#29 — <the
words, verbatim>`. **Neither is a transition**, so neither ever changes a lane's
state on any object or on itself: `who`, `lane-end`, `lanes` and `swapped` skip
them exactly as they skip `STARTED` and `RESUMED`.

**The `<lane>` field and the `lane:<name>` object are matched
case-insensitively, and a writer writes the register row's spelling into both**
(Amendment 15). A log is append-only and its lines carry whatever was typed on
the day it was written: `lanes/log/openxfactory-2.md` holds `lane
openXfactory-2` lines from 2026-09-02 beside the `lane openxfactory-2` lines of
the 23:51Z incident, in one file, about one lane. `who --lane`, `lane-end`'s
refusal and the `lanes` listing read both as that lane's; the old lines are
never rewritten.

**The object kinds in scope** are an issue or PR (`owner/repo#<n>`), an
OpenSpec change directory (`owner/repo:openspec/changes/<name>`), and — for
the lane-kind lines only — `lane:<name>`. `#<n>` is shorthand for the lane's
**own** home repo; a foreign repo is always spelled, so that crossing is
explicit at the moment it is typed. Human acts, realization groups, contract
cuts, file surfaces and Amendment 1's substrates stay where they are today, on
their governing records, and are an explicit non-goal; a later amendment may
add keys.

The alias table resolves an omitted owner and the register's legacy
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
| 3 | the edit is never a permanent loss, but this attempt cannot confirm whether it also reached origin — a rebase conflict (not pushed by this attempt; a later write from this checkout may already carry it to origin, so look by content before you retry), a network timeout on a push or a pull (a hung one often already landed), or six attempts exhausted because a peer's uncommitted file blocks every rebase |
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

**The home is canonical.** That spelling is resolved through the alias table
— both layers, the shipped `repos.tsv` and the checkout's override (Amendment
9(b)) — *before* the line is written, and every comparison of an object's
repository against a home resolves both sides — because a home is inherited by every `#<n>`
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
repoSW-1	2026-09-12T10:00:00Z	claude-team-05b-20260912102132-2699:0 @71	~/projects/repoSW	team-05b
repoSW-5	2026-09-12T11:00:00Z	sess-five:5
```

**Amendment 11 gives the row a fourth field, `<dir>`, and a fifth,
`<profile>`, and the `<window>` field a second ref, `<@id>`** — and the second
row above is what every record written before that looks like: the fields are
EMPTY rather than guessed (Amendment 7(i) cuts each lane over at its own next
start, and nothing is backfilled). **The first field before the first tab is
still the lane**, which is the contract both readers of this output take, and
it is what makes a fourth and a fifth field safe to add at all.

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
(`set-row-state`, `replace-in-row`, `append-line`, `add-row`, `log`,
`claim`, `release`, `commit`) and rule 8's list of tooling paths are both
unchanged by this amendment.

## Bind and list (Amendment 11, amended by Amendment 18)

**DRAFT, 2026-09-13, awaiting Brett Heap's word on the amendment itself**
(`brettheap/new-workstation#21`) — but **eight decisions inside it are
RATIFIED**, verbatim, on 2026-09-13T18:05:29Z: *"Ratify all four"*, *"Yes, build
`lanes` in A11"*, *"Ratify the bundle"*, *"Hotfix brett-wip now, move it with
history"*. Everything below rests on one of those eight.

Amendment 8 made a swap leave a record. Amendment 11 is what makes that record
enough to **restart from**, and it exists because on 2026-09-13 a restart of a
real lane printed `[exited]` and a second one came up in the wrong directory
without the repository's `CLAUDE.md` or the lane's memory, silently.

### The two words

```console
$ lane openRepoProject-1        # cd to its directory, relaunch through the launcher
$ lane                          # the lanes of this checkout, numbered — pick one
$ lanes                         # inside a checkout: ITS lanes, and the next free one
$ lanes --all                   # every lane the register and the logs know
$ lanes --fetch                 # any of them, after refreshing from origin
```

**`lane <name>` is Amendment 11's OUTSIDE half and `restart` is retired**
(**Amendment 18 Addendum 2**, ratified 2026-09-14T16:50:32Z verbatim *"ratify"*,
on Brett Heap's ruling *"i think we can drop restart as a cli command and keep
it inside a claude session with /restart. if we need it for ctx, keep it for
that, but I do not see any reason to expose this to the user. lane does all the
things a user wants"*). `openRepoTools --install` no longer places `restart`
**and REMOVES the copy an earlier install placed** — printing `restart: RETIRED`
beside the file it took away — because a word that merely stops being written
stays on the PATH of every workstation that already took it. It removes only
what it wrote: a file of that name carrying this installer's own header goes,
and one that does not is NAMED, left exactly as it is, and the `rm` that removes
it printed for the person to run. Everything decision 7 ratified about that act
is true of `lane <name>`, which does it and three things more. Everything below
is about `lane <name>` and was written about `restart <lane>`.

`lane <name>` needs **no window, no record of a window and no guess** — only
the lane's name, its `dir` and its `profile`, both of which the record now
carries. That is the whole point: measured on this estate after the tmux server
was replaced, each of the two surfaces the direction names met **one prompt
offering two choices, and the lane it offered was the wrong one**. Declining was
the only correct answer, and declining left the operator where they started.

**It never calls `claude` itself.** Every path goes through the launcher and
therefore through `lane-start`, which renames the window, writes the row stamp,
extends the session cell, writes the `RESUMED` object line, stamps the handoff —
and passes `--name <lane>`, without which the harness derives a record name like
`openrepoproject-b9` and that derived name is what the statusline and
`ListAgents` show.

**It `cd`s into the lane's directory before it launches**, and that is not a
convenience: the harness keys a session to the directory it was started in, so a
restart from the wrong one loads neither the repository's `CLAUDE.md` nor the
lane's memory, while `--resume <uuid>` goes on continuing the right transcript —
which is why the loss is silent.

**`lanes` is never a picker, and `lane` asks exactly one question.** Ratified
decision 3 refused a picker for the words Amendment 11 added, and Amendment 18
Addendum 1 is the later word on a question that decision was not asked: a person
who has to type a lane name has to know one. So `lanes` still asks nothing at
all — it is a read — and `lane` prints the listing, asks `which?` **once**, acts
on the one answer, and stops; with no terminal on stdin it asks nothing either.

`/restart [<lane>]` is the same act from **inside** a running session, and it is
a skill rather than a command because a session cannot `exec` a launcher over
itself: it binds the window through `lane-start --no-launch`, and where this
session is not the lane's conversation it prints exactly `claude --resume <uuid>`
and stops. It is unchanged by Addendum 2: what left the PATH is the outside
half, and `/restart` was always the inside one.

### The bare word narrows inside a checkout

**Brett Heap settled clause (j)'s default on 2026-09-13T20:38:11Z, verbatim
*"Narrow inside a checkout (Recommended)"*, and `lane-start <repo>` with no
position in the same breath, verbatim *"Yes, list and suggest (Recommended)"*.**

A bare `lanes` INSIDE a lane checkout lists **that repository's lanes** — the
checkout around the cwd as clause (i)'s `--dir`, and that checkout's `origin` as
`--repo`, which are an **OR and not an AND**, because a lane's home repository
and the checkout it sits in are not the same fact — and it ends with the **next
free position** and the exact `lane-start <repo> <n>` that takes it, filled in.
The position offered is the **lowest** one no lane of that repository holds,
never the highest plus one: positions come back as lanes end, and `lane-start`
refuses one that is taken, so this is a suggestion with a guard behind it rather
than an assertion.

**The repository is the one `origin` names, and the directory's name is only the
fallback.** Inside a worktree, `basename $(git rev-parse --show-toplevel)` is the
WORKTREE's name: run in a worktree of `openRepoTools` called `ort-a11` the
listing narrowed to a repository called `ort-a11`, found none, and offered
`lane-start ort-a11 1` — a lane whose `$PROJECTS_ROOT/<repo>` cannot exist. A
checkout with no `origin` keeps the directory name, because there is nothing
else to have.

`lanes --all`, and a bare `lanes` outside every checkout, are clause (j)'s
every-lane listing **unchanged**; any explicit narrowing — `--repo`, `--dir`,
`--ws`, `--here` — is the caller saying which lanes they mean and suppresses it
too. `--here` is the pre-Amendment-11 default, only the asking workstation's
lanes, kept as an option: "list the lanes" on a two-workstation estate means
both.

`lane-start <repo>` with **no position** prints that same listing and that same
next free position, and **launches nothing**. It still exits **2** — a
repository is not a lane, and a caller that scripted `lane-start <repo>`
expecting a session must not read 0 from a run that started none — and the
refusal names the position it has just given the reader a listing for. It
renders nothing of its own: it runs `lanes --prefix <repo>`, so the two surfaces
cannot offer different positions.

### What the record carries now

Two payload sub-fields are added to the lane's `STARTED`, `RESUMED` and swap
`PAUSED` lines, and the `window` sub-field gains a second ref:

```text
STARTED — lane openRepoProject-1, session a3ab3df2-…@Eagle, 2026-09-13T04:30:00Z, lane:openRepoProject-1 → home opensoft/openRepoProject; estate openRepoProject; dir ~/projects/openRepoProject; profile team-05a; window claude-team-05a-20260912213845-570498:0 @71
PAUSED — lane openRepoProject-1, session a3ab3df2-…@Eagle, 2026-09-13T04:32:00Z, lane:openRepoProject-1 → swap; window claude-team-05a-20260912213845-570498:0 @71; dir ~/projects/openRepoProject; profile team-05a; workstation Eagle
```

- **`dir <path>`** — the lane's checkout. Two writers put it there: `lane-start`
  from the directory it is about to `cd` into, and the swap from the live
  session's own record. A path containing `, `, ` — ` or `"` is **refused**,
  naming the path; a path containing a **space is written quoted**, which is
  what makes it one ref under Amendment 7(b)'s grammar, and every reader strips
  the quotes.
- **`profile <name>`** — from `$CLAUDE_PROFILE_NAME`, which the launcher exports
  into every session it starts. Without it a restart typed anywhere but in the
  lane's surviving window cannot name the profile the launcher needs.
- **`window <session>:<index> <@id>`** — two space-separated refs in one
  sub-field. **The name is the key and the id is information**: a tmux server
  restart reissues every id from `@0`, so a binding keyed on the id would lose
  the lane where one keyed on the name does not.

**A line written before this carries none of them, and a reader that finds none
says so rather than assuming one.** Nothing is backfilled.

### The lane's directory, in six rungs

`--dir <path>` → the **swap record's** `dir` → the **lane's log** (`lane-dir`) →
`$PROJECTS_ROOT/<repo>` → the estate's **`project.yaml` legs** → **a checkout
named for the home's repository** under `$PROJECTS_ROOT`. First answer wins, and
**the cwd's own checkout is ruled out by name**: deriving the directory from
wherever you happen to be standing is an inference, and `lane-start` writes the
lane's HOME from that directory's `origin`, which every `#n` the lane afterwards
writes inherits. A recorded directory that no longer exists is a **refusal
naming the path**, never a silent re-home.

**Rungs 5 and 6 were four until Evidence 7** (`708395e`), where a lane whose
checkout is NESTED — `~/projects/xFactory/xFactories/OpsxFactory`, not
`$PROJECTS_ROOT/opsXfactory` — met an exit 1 behind an `exec` and a pane that
said `[exited]`. Neither is a search for a directory that looks right:

- **Rung 5 is a DECLARATION.** openRepoShape's manifest carries a top-level
  `legs:` list of `repository:`/`path:`, and Amendment 7 decision 3 treats a leg
  as home. Where a manifest names the lane's recorded home as a leg, that leg's
  `path`, resolved against the manifest's own directory, IS the checkout.
- **Rung 6 is a NAME, and the name is the repository's.** One or two levels
  under `$PROJECTS_ROOT`, a directory named for the home's repository —
  `resolve-repo`'s canonical spelling, because `opsXfactory` the lane label and
  `OpsxFactory` the repository are not the same string.

**Both are proved by `origin` and both are skipped entirely where the lane has
no recorded home**, because there is then nothing to prove a candidate against
and a match would be the guess rung 4 already refuses to make. A candidate whose
`origin` is not the recorded home is passed over, not taken. And when all six
answer nothing the end is still a **refusal, exit 2**, one line a person can
type — never the exit 1 Evidence 7 met.

### The new reads

All read-only, all out of `origin/<branch>`, all following Amendment 7(d)'s
fail-closed convention — **0** an answer, **8** *no answer*, **64** a usage error
of their own — with one exception that every un-upgraded workstation is in:
**`2` is a helper predating Amendment 11**, expected and silent, and a caller
falls to its next rung there rather than refusing.

| read | what it answers |
|---|---|
| `lanes-edit.sh lane-dir <lane>` | the `dir ` of the lane's **last** lane-kind line carrying one, unquoted where it was written quoted |
| `lanes-edit.sh lane-profile <lane>` | the same read one sub-field along — the `profile ` of that last line. An addition to the amendment's own table, so that `lane <name>` can learn a profile with one `git show` instead of a listing that reads every log on the workstation |
| `lanes-edit.sh window-lane [<ws>] <@id>\|<session>:<index>` | the lane bound to a window **of the asking workstation** — the register row whose name is the window's name, else that workstation's swap record naming that ref. Both rungs answer in the **register row's own spelling** (Amendment 15): what this prints is renamed to, `--name`d with and typed as `lane <name>` |
| `lanes-edit.sh session-lane <uuid>` | the lane whose register row's **session cell** names that transcript uuid. Adoption act 0's; it is the read the `SessionStart` hook already made. **0** the lane · **8** no row's cell names it · **64** usage — like every other read in this table, by A11 Addendum 4 ruling 1, which corrects act 0's `2` · **2** a helper predating the read |
| `lanes-edit.sh last-session <lane>` | the lane's resume target: the last uuid in the published cell **whatever shape it is in**, and failing that the session of its last `PAUSED`/`RESUMED`. This is what `/restart`'s step 4 reads, by A11 Addendum 4 ruling 14, rather than clause (f)'s `register-row` alone — so a lane whose row was never stamped but whose log records the session it paused in still has a resume target |
| `lanes-edit.sh forks <lane>` | the **live forks** of the lane's transcript — never holders, and a defect to retire |
| `lanes-edit.sh lanes [--repo\|--dir\|--prefix\|--ws\|--lane\|--here\|--all\|--fetch]` | every lane, newest write first, tab-separated: clause (j)'s **ten columns in clause (j)'s order** — name, state, workstation, profile, window, last transcript uuid, directory, held objects, age, the line that binds it — then the read's own two, `home` and the count of live forks. `lanes` and `lane` each render the subset their surface needs (A11 Addendum 4 ruling 7), and column 10 is the read's so the two cannot offer different commands; since Amendment 18 Addendum 2 the word it names is `lane <name>`. **The one read whose default is local**, and `--lane <lane>` answers about one without walking the estate. `--prefix <repo>` is the LABEL fallback the checkout narrowing and `lane-start <repo>` both ask for, used only where a lane has neither a home nor a `dir` |
| `lanes-edit.sh lane-groups [<ws>]` | **the rows on STDIN**, each with the group the pick puts it in: `available` (PARKED, or a binding that workstation proves dead), `live`, `elsewhere`. Closed and dormant rows are DROPPED (Amendment 19). It reads nothing itself — the caller has already paid for `lanes`, and two surfaces computing one partition is how they come to disagree |
| `lanes-edit.sh next-free <repo>` | **the rows on STDIN**, and the LOWEST position no lane of that repository HAS EVER held — `ENDED` and `RETIRED` rows reserve theirs, because a lane's identity is its name and its object log `lanes/log/<lane>.md` is append-only, so a second lane at a retired position would write its life into the first one's file. The name before the position is compared whole, so `repo-foo-1` is no lane of `repo`. `lanes`'s footer and `lane`'s `f` answer both read it, so the two cannot offer different positions |
| `lanes-edit.sh workstation` | `<name><TAB><source>` — `seam`, `hostname`, or `container-unset` |
| `lanes-edit.sh fetch-age` | how old this checkout's answer is |

**`window-lane` owns the agreement rule, and it owns it once.** Existing-now is
not enough on its own: a record naming `claude-y:0 @97`, met from the window that
has since taken `claude-y:0` as `@200`, passes the existing-now test on its ref
and would bind the lane to a **stranger's pane** with no question. So a record
that carries an `<@id>` is matched on its `<session>:<index>` **only where the
window now holding that ref reports that same id**; a record with no id is
matched on the ref alone. Three callers share that one implementation — the
launcher's precedence 3, `/restart`'s step 2(c) and `/lane-swap`'s step 1 —
because three implementations of one rule is how they would come to disagree.

### Two things that are never taken

**A window named for another lane never lends its session.** `lane-start`'s step
3b learns a harness-minted uuid from the session live in the window it was typed
in — which is how a `/clear`, a usage reset and a profile switch stay recorded.
Its fence is **two vetoes and no permission**: the **register veto** (a uuid that
belongs to another row is never taken, read through `session-lane` and
fail-closed) and the **window-name veto** (a window named for another lane is
never taken). Neither the window's name being the lane nor `live-holder`
answering `here` is a *condition for taking* — at step 3b the window is usually
still called `claude` and there is no holder here, which is exactly the case the
mechanism exists for.

**A fork of a lane's transcript is never a holder and never writes the
register.** A `--fork-session` copies the parent's title and gets a **new id**,
so lineage is never the test: the holder is the session whose id the published
cell names. `lanes`, `/restart`, `who --lane` and the `SessionStart` hook all
show a live fork as a **defect to retire**, and none of them kills anything.
**Retiring it is `lane-end <lane> --retire <pid|uuid>`** — the one act, ratified
decision 8(e) and clause (k) rule (e). It is the **DOOR** to Amendment 6(d) and
not a record of one: it proves the pid or uuid is this lane's live fork and
prints 6(d) filled in. **It writes nothing** — a `RETIRED` carrying a payload
would be a seventh edit to in-force text, and Amendment 7(b) gives that verb
none — so every read goes on naming the fork until the person takes the printed
act. And it **kills nothing either**: stopping the process is a separate act and
it stays the person's.

### The workstation's name

`$LANES_WORKSTATION`, exported by the workBenches launcher from the host into
every session and container it starts. Outside a container it still defaults to
`hostname -s`. **Inside a container with no value, every writer refuses, exit 2,
naming the variable** — because a container's `hostname` is the container's id,
not a workstation, a row on a workstation that does not exist is a row no reader
can match, and the log is never rewritten. `lanes-edit.sh` already carries six
such lines in one lane's log, and they stay where they are.

## The name guard and the lock (Amendment 12)

**A lane session normally works while three names are one.** A readable,
recoverable lane/session mismatch now pauses for an explicit choice; unreadable,
ambiguous, duplicate, or superseded identity still refuses the prompt. Ratified
by Brett Heap 2026-09-13T18:20:44Z — *"Ratify revision 2"*, with M1 *"Type
/rename into the pane"*.

The three:

1. the tmux **WINDOW** it runs in is named for a lane;
2. the **SESSION's own name** — the live record's `name` — is that same name;
3. the register **ROW** keyed by that name records this session's id as the
   **LAST** id of its session cell (Amendment 6(b)).

`lanes-edit.sh guard` is the `UserPromptSubmit` hook that reads them. Where they
agree it is **silent and exits 0**; where they do not it **exits 2**, which is
what blocks a prompt, and prints the triple as it stands and the ONE command
that cures it, filled in. It is the only subcommand in that file that refuses a
person's work.

```console
$ # what the person sees on a blocked prompt
lanes-edit: THE NAME GUARD REFUSES THIS PROMPT (lane-collision-protocol Amendment 12). The three names:
lanes-edit:   window   eagle:@12 'claude'
lanes-edit:   session  d1ac715c-… 'openRepoTools-3' (nameSource user) pid 1924546 profile team-05f
lanes-edit:   row      this window names no lane, so no row is keyed by it
lanes-edit: this window is named 'claude', which is no lane, while the SESSION is named for lane openRepoTools-3 — …
lanes-edit: run: lane-start --no-launch openRepoTools 3
```

### The table — one row per state, one cure each

Every message prints the register's own spelling of the lane (Amendment 15) and
every command is filled in, never `<repo> <n>`.

| what it finds | what it does |
|---|---|
| the window is not a lane, the session name parses as `<repo>-<n>` | `lane-start --no-launch <repo> <n>` — **the 2026-09-10 case**, which ran for three days unrecorded |
| neither name is a lane | refuses and says so: WHICH lane this work is is yours to name, and a guard that guessed would bind a window to a row nobody chose |
| the window is a lane, this uuid is the row's last id, the session name differs **only by case** | the lock renames it to the ROW's spelling — a lane name is ONE name under any case (Amendment 15), so there is nothing here for a person to decide |
| … and the session name is a **FORMER name of this lane** | the lock renames it to the row's spelling — the alias table makes that name this lane for ever (Amendment 16(e)), so a rename run from another window is drift to finish, not a choice to put to anyone (Amendment 16(f)) |
| … and the session name differs by more — a non-lane word, a `<lane> (N)` title, ANOTHER lane's name, no name at all | **THE THREE-CHOICE OFFER** (below), and NOTHING is typed until a person picks `3` |
| the window is a lane, this uuid is IN the cell but not last | a SUPERSEDED transcript: exit, `lane-start <repo> <n>`, which resumes the id the row ends on |
| the window is a lane, this uuid is in NO row | the harness minted a transcript with nobody acting: `lane-start --no-launch <repo> <n>`, the recording act, no relaunch |
| the window's name matches TWO rows differing only by case | refuses naming both spellings and the merge, which is a person's act (Amendment 15(d)) |
| not inside tmux at all | refuses: a lane RUNS in a tmux window named for it (Rule 4, Amendment 2) |

### The lock

Under the projects root the session name is **not the person's to set freely; it
is the lane's** (clause (h), Brett Heap's D5). `lane-start` sets it at every
launch (`--name "$LANE"` on all three branches), and **the lock is what answers
the two drifts that are not decisions**:

* a name that differs from the row's only **by CASE**, which is the same lane
  under Amendment 15; and
* a name that is a **FORMER name of the row's own lane**, which is the same lane
  under Amendment 16(e) — the alias table resolves it to this row for ever, so
  a session still called `repoRen-1` on a lane the register now spells
  `repoRen-7` is not a lane anybody is moving to. It is what a `lane-rename` run
  from ANOTHER window leaves behind, and finishing it is clause (f)'s whole job.

There the guard renames it
for you — it types `/rename <lane>` into this session's own tmux pane, which is
the only path a running session's name has (M1 — the docs name `--name` at
launch, `/rename`, and `Ctrl+R` in the picker, and nothing else). That one
prompt is refused so the rename lands first; send it again. (The WINDOW's half
of the same drift needs nobody: a window's name is one tmux call, so the guard
simply makes it — Amendment 16(f).)

**Every wider mismatch is the offer below and nothing is typed into the pane
until a person picks `3`.** A session called `openrepotools-b9`, a
`<lane> (2)` title, ANOTHER lane's name, no name at all: which lane this
conversation is is a decision, and the guard asks rather than renaming on the
person's behalf — and two of the three answers would be wrong for a former
name, which is why that one is the lock's and not the offer's. What follows about the PANE — which one, and whether it may be
typed into at all — is the mechanism both the lock and choice `3` use.

The pane's **current command is asked first** and nothing is typed into a pane
running anything else — `claude` and nothing else, which is M1's own word:
`/rename openRepoTools-3` typed at a shell is a command that does not exist,
typed into an editor it is text nobody wrote, and typed into a Node REPL it is
input somebody has to clear. A pane whose command cannot be read is not typed
into either — fail closed. Every outcome but a successful typing prints the line
for you to type yourself, which is the cure and not a failure: on Eagle today
two panes report `bash` (a session under a launcher wrapper), and those are
exactly the windows where you will read it.

**Which pane**: the one the live record names, and where the record names none
— the harness has been seen to write no `tmux` field for a process plainly in a
window — the pane this hook is itself running in, `tmux display-message -p
'#{pane_id}'`. Both hooks run inside the session's own pane, so that is the same
pane, asked of tmux rather than guessed.

A `<lane> (N)` title is a **mismatch** (ratified decision D4) and the suffix is
evidence: it is exactly what a rename into a title something else still holds
mints, so another holder of that name was live. That reading is printed **with
the offer's three choices**, where this state now arrives, and it names
`lanes-edit.sh forks <lane>` and `lane-end <lane> --retire <pid>` — never a
`kill`, because stopping a process is the person's act and stays theirs
(Amendment 11 clause (k) rule (e)).

### The offer

For a readable current lane/session mismatch, the guard now presents three
numbered choices rather than choosing a repair automatically:

1. **Allow this lane** — explicitly allow the current lane/session pair for
   this transcript. Later prompts warn without blocking until either name
   changes.
2. **Adjust lane to session** — move the window and register binding to the
   session's lane through the existing lane-start and UUID-anchor path.
3. **Adjust session to lane** — type /rename <lane> into the verified Claude
   pane. This choice never changes the register.

The answer is the next prompt and is consumed by the guard. Invalid answers
keep the offer pending. If the pane cannot accept choice 3, the guard prints
the manual /rename command and keeps the offer. Choice 1 is stored per
transcript under the session's offer directory and is invalidated when the
lane, session name, or transcript changes.

**And choice 1 is an answer to ONE row of the table above, honoured there and
nowhere earlier.** It is read at the row it was given for — a readable lane
whose uuid is the row's LAST id and whose session name is not the lane's — so
an unreadable register, an ambiguous one, a duplicate live process, a
SUPERSEDED transcript and a uuid the row does not name at all are refused
through it, exactly as they are without it: an allowance is not a bypass. The
three names agreeing again ends it too — that is one of them having changed —
so the file is dropped and a later drift is a fresh question rather than a
silent pass on an old answer.

*"if the user does a rename, then we should offer to move to that lane or create
a new lane if we do not have one as that name"* (D5, verbatim). A record whose
`nameSource` is `user`, whose `name` is another lane's, and whose `nameSince` is
later than this window's binding is a person saying **"this is that lane now"**
— so the guard **asks** rather than guessing:

```console
lanes-edit: WARNING: the lane and Claude session names disagree.
lanes-edit: 1) explicitly allow this lane for this transcript
lanes-edit: 2) adjust the lane to session openRepoShape-2
lanes-edit: 3) adjust the session to lane openRepoTools-3 (types `/rename openRepoTools-3`)
lanes-edit: Reply `1`, `2` or `3`.
```

The numbered answer is the **next prompt**; it is consumed by the guard and
never reaches the model. Anything other than `1`, `2` or `3` asks again.
The pending offer is held per session id under
`$CLAUDE_CONFIG_DIR/lanes/offers/<uuid>`. **An answer is a prompt**, so it
waits behind the duplicate read below: while a second live process carries this
transcript the answer is refused with that, and the offer is kept for the first
prompt after the other process is retired.

**A lane named before Rule 4's `<repo>-<n>` form is offered, not run.** The
register carries 22 of them, and `lane-start` needs such a lane's DIRECTORY,
which nothing in the register, the window or the session says. So the offer
says what it cannot fill in and choice `2` refuses rather than running a command
with a `<path>` placeholder in it: the move is
`lane-start --no-launch --dir <that lane's checkout> <lane>`, yours to run with
the path filled in, and the offer is kept. On choice `2` the **window is renamed first** and that order is
load-bearing: `lane-start`'s step 3b veto 2 refuses to take the session live in
a window named for another lane, which after choice `2` is exactly what this
window is — without the rename the lane would be started and stamped with this
transcript left out of its session cell.

**And the LAST write of choice `2` is the guard's own**, because `lane-start`
may not make it: its step 3b **veto 1** never takes a uuid that belongs to
ANOTHER row (Amendment 11 clause (d) rule 1), and after the rename this uuid
still belongs to the lane being left. So `lane-start` mints a fresh id for the
new lane and the person's own transcript stays out of the cell — and the next
prompt then finds a lane window whose row does not name this transcript and
refuses, with a cure that vetoes for the same reason and changes nothing. A
blocking hook that refuses for ever, on a state it created by obeying the
person, is the worst outcome this surface has, so after `lane-start` returns
the guard appends this uuid to the new lane's cell itself — with `lane-start`'s
own anchor discipline, the PUBLISHED last id, so a stale copy of the row
refuses rather than writing a cell that no longer matches. That is not a hole
in veto 1: the veto exists for the take nobody asked for, and clause (h) rule
4's limit is that the lock never moves a uuid between rows **without the person
saying so** — here they have, in the answer given at this very prompt.

### The duplicate read (Amendment 18(h))

**A transcript is held by ONE live process.** The harness can fork one
(`--fork-session`, minting a new id in a background pty host) or resume one
twice, and the tooling refuses to build on either. Measured four times on
2026-09-14, the last at 18:14Z: a `bg` record in one profile's `sessions/`
beside the interactive record in ANOTHER's, both live, both carrying one
`sessionId` — so the sweep is of **every** profile's directory, not the asking
session's.

The one live record this read passes over in silence is the harness's own
**companion**: `kind: bg`, beside this window's own record, in the same
profile's `sessions/` (Amendment 8, ruling (g) — *"records that share a
`sessionId` are one session, not a queue of rival holders"*). The **kind** is
what tells it from a second live process, not the profile: one profile can
resume one transcript twice — no move, no swap, one command — and the
interactive record that makes is 18(h)'s own case.

`lanes-edit.sh transcript-holders <uuid>` is the read, and three surfaces share
it rather than implementing the rule three times:

* **the guard** refuses every prompt in a process that shares its id with
  another live one, naming the pid, its window or `bg`, its profile, and the
  retire act `lane-end <lane> --retire <pid>`;
* **`lane-start`** counts the holders of the id it is about to resume or bind —
  at the window-binding step and in the row-resume branch — and refuses rather
  than appending such an id to the row or launching a second resume of it;
* **`lane-end <lane> --retire <pid>`** retires a duplicate whose id **IS** the
  row's own, which `forks` cannot see because its criterion is "an id the row
  does NOT record". A duplicate is named by its **pid** and never by a uuid —
  its uuid is the row's own and could not pick between the processes carrying
  it; the uuid form is for a fork. The window's own session is refused **by
  name**: retiring the session that IS the lane is how a lane loses the
  conversation it is, and ending the lane is the bare `lane-end <lane>`. The
  harness's own **companion** of that session is refused by name too: it is one
  half of the live session, not a rival to it.

A window is matched by **id AND session name** (Amendment 11(h)'s agreement
rule) because tmux reuses window ids once a window is gone.

### The `SessionStart` block's own line (clause (f))

The `SessionStart` hook gains one line — `session name '<x>' was not the lane
'<y>' — renamed` — and types the rename itself, so the first prompt already
finds the three agreeing. It types over DRIFT only: a name a PERSON set to
another lane's, newer than this window's binding, is clause (h) rule 2's
instruction and this hook leaves it alone, says so, and lets the guard put the
offer at the next prompt — otherwise a rename followed by a `/clear` would be
undone before anyone was asked. It is that hook's **one act on a pane and its only act
of any kind**: it stays read-only against the register and **always exits 0**,
because a hook that fails is a hook that breaks the session it was meant to
orient (R-A8-1). Where another live process carries this session id it **SAYS
so** and names the retire act; the refusal is the guard's.

### Fail closed, and the one bypass

A mismatch refuses, and so does an **indeterminate read** — session records
unreadable, tmux not answering, the register unreadable, a payload naming no
`cwd` — naming the read, because a triple that cannot be verified is not a
triple that agrees (clause (d)). The row is read from `origin/<branch>` as this
checkout last had it (R19) and **the guard never fetches**: this hook runs at
every prompt, and putting the network there would be R-A8-1's objection several
times over.

**There is no environment flag that turns it off.** `claude --safe-mode` runs
with every hook disabled and is the one bypass — deliberate, visible in the
prompt box, and **a session started that way is not a lane session**: it may not
write the register or claim an object. The hook's `timeout 5` is the other way
it can fail open, and it is the amendment's own number: a hook that exceeds its
timeout is killed, and a killed hook does not exit 2.

### Scope

The guard applies to every session whose `cwd` is under `$PROJECTS_ROOT`
(default `~/projects`), which is every estate session, and is **silent
elsewhere** (D1): a name there is a title and nothing more. A **subagent's**
prompt — hook input carrying `agent_id` — is exempt, because subagents do not
submit prompts and the lane that runs them has already passed.

Installing it is `openRepoTools --install`'s: the entry
`~/projects/xFactory/lanes-edit.sh guard`, timeout 5, under
`hooks.UserPromptSubmit` in `~/.claude/settings.json`, beside the `SessionStart`
one. It carries **no `|| true`** — on `SessionStart` that suffix is the whole
safety property, and here it would be the opposite of the mechanism, since
`cmd || true` exits 0 for every code the command can produce and a guard that
refuses nothing silently is the exact state this amendment exists to end.

## The row is current state; the log is history (Amendment 13)

**In force — ratified by Brett Heap 2026-09-13T21:08:36Z, verbatim "Ratify as
drafted (Recommended)".** The `state` column was defined as a cell and used as
a diary. Measured the day the amendment was drafted: the register was
1,141,283 bytes over 46 rows, its longest row 96,228 characters, and one lane's
cell 7,016 characters after a single day of appending — three different things
in one column (the lane's CURRENT state, which Rule 6 reads; a running
narrative; and rulings quoted verbatim), appended forever with ` · `, never
replaced, in a table nobody can read in the table.

### The cell is one phrase, and every write replaces it

```text
<STATE> · <UTC> · <one line>
```

`STATE` is one of `LIVE`, `PAUSED`, `LANDING #<n>`, `LANDED`, `ENDED`,
`RETIRED`, `HANDED OFF`. **Rule 6 is unchanged** and is now the whole of what
the cell says at that moment. The line is at most **240 characters** (ratified
decision O1) and carries neither a `|` (it would forge a cell boundary) nor a
second ` · ` (it would read back as a fourth part of the phrase).

```sh
lanes-edit.sh set-row-state my-lane "LANDING #123 · CI green; waiting on review"
```

The UTC is stamped by the writer, never passed in. `append-row-status` is
**RETIRED** and refuses, naming this and the two verbs below: the cell can
never grow again because the act that grew it is gone, not because every caller
remembered.

**Which text is the state cell** is decided by splitting the row on ` | `, and
a seven-column row has exactly six of those separators. A row with more has a
` | ` inside one of its cells, and the two readings of it — count six from the
left, take the last cell from the right — disagree about which text to
overwrite, so **that row is refused by name** rather than written at a guess.
Measured on the live register 2026-09-15 (52 rows): 50 split cleanly, and the
two that do not are cured by escaping the literal pipe as `\|`, the way a
Markdown table carries one, in a hand edit wrapped by `lanes-edit.sh commit`.
A bare `|` that is *not* spelled ` | ` is harmless and stays inside its cell.

### The narrative goes to the lane's own log

Two verbs join Amendment 7's, in the same file, with the same grammar:

```text
NOTED — lane <lane>, session <uuid>@<ws>, <UTC>, lane:<lane> — <what the lane did, found, launched, left>
RULED — lane <lane>, session <uuid>@<ws>, <UTC>, lane:<lane>[ → <object>] — <Brett Heap's words, verbatim>
```

```sh
LANES_LANE=my-lane lanes-edit.sh log NOTED lane:my-lane "rebased on main; the flake is the fixture's clock"
LANES_LANE=my-lane lanes-edit.sh log RULED lane:my-lane → opensoft/openRepoTools#29 "Ratify as drafted (Recommended)"
lanes-edit.sh history my-lane [--since <UTC>]
```

`NOTED` takes no payload; `RULED` takes one, the object it bears on, and that
object is canonicalised through `repos.tsv` like every other object this
tooling writes. **Neither is a transition of anything**, so neither ever moves
a lane's state: `who`, `lane-end`, Amendment 11's `lanes` and `swapped` skip
them exactly as they skip `STARTED` and `RESUMED`. `history` prints them in
**file order**, which is the order the lane wrote them (R14), and exits 8 for a
lane that has written none.

### The migration — one act, on Brett Heap's word

```sh
lanes-edit.sh migrate-state-cells            # DRY RUN: reads everything, writes nothing
lanes-edit.sh migrate-state-cells --yes      # the one act
```

Each row's cell is split on ` · ` into entries, oldest first. Each becomes one
log line: `RULED` where the entry begins with `RULING`, `RULINGS` or
`RATIFIED`, else `NOTED`; the entry's own leading timestamp becomes the line's
UTC (a row's `started` where it carries none), the session is the **last uuid**
of the row's session cell, and the workstation is the first `/`-separated part
of the row's own column. The cell is then replaced by the state the **last**
entry's leading verb names, else by `MIGRATED · <UTC> · history in
lanes/log/<lane>.md`.

**One commit** carries the archive `lanes/archive/LANES-pre-amendment-13-<UTC>.md`,
every log it appended to, and the register — so the narrative exists three
times over (git history, the archive, the logs), which is the posture
Amendment 3 took after the 2026-09-08 loss. It **refuses** when no cell holds a
` · ` entry it can migrate, so a second run is a no-op that says so.

A row it cannot take is **skipped and named**, never half-written, and its cell
keeps every character so that a re-run after the row is settled migrates
exactly it. Five reasons: the row is ambiguous (above); its session cell holds
no transcript uuid, so the line could only name `unknown` in the one field an
append-only log must never carry it in; two rows differ only by case
(Amendment 15(d)); the lane's log is two files or is published under a spelling
this checkout does not have; or the first cell is not a lane name.

## Renaming a lane (Amendment 16)

**In force 2026-09-14T09:24:35Z**, ratified verbatim *"Ratify as drafted
(Recommended)"* on Brett Heap's request of the same day, verbatim: *"we need the
ability to rename a lane. maybe lanes --rename <current lane name> <new lane
name>."* **A LANE IS RENAMED BY ONE WORD, IN ONE COMMIT, AND ITS OLD NAME KEEPS
RESOLVING FOR EVER.**

Why it exists: on 2026-09-14 two lanes renamed themselves **by hand**, each as
one `RENAMED` line appended to `LANES.md`. The lines are honest and they are all
there is — the rows still carried the old keys, the logs and the handoffs the old
names, and a reader of either lane's history had to know the rename to follow it.

```sh
lane-rename openxfactory-4-opendox-extraction openxfactory-4 "Brett Heap's word: shorten it"
lane-rename hermes-wallet-exercise codeXfactory-2 --no-github
lanes --rename a b        # REFUSED, and it names `lane-rename`
```

The first two lines above are the amendment's own **adoption act**, and they
have not been run: clause (i) says the two hand renames of 2026-09-14 are *regularised by the
adoption act, not re-done* — their rows, logs and handoffs moved by this command
**on Brett Heap's word**, with their existing `RENAMED` lines in `LANES.md` left
exactly where they are.

### What one command does

| # | clause | the move |
|---|---|---|
| 1 | (b) | the register row's key cell becomes `` `<new>` ``, and the text beside it gains `` *(ex `<old>`, renamed <UTC>)* `` — the form the register already uses for a lane named later than it started. Nothing else in the row changes; **the session cell keeps its history** (Amendment 6(b)) |
| 2 | (c) | `lanes/log/<old>.md` → `lanes/log/<new>.md`, plus one line: `RENAMED — lane <new>, session <uuid>@<ws>, <UTC>, lane:<new> ← lane:<old> — <why>` |
| 3 | (d) | the handoff the row names → the same date with `lane-<new>`, plus a Rule 3 stamp under its header block: `RENAMED from <old> by <uuid> (lane <new>) at <UTC>`. The row's handoff column follows |
| 4 | (e) | `lanes/aliases.tsv` gains one TAB-separated record, `<old><TAB><new><TAB><UTC>` |
| 5 | (g) | **after** the commit lands, one GitHub comment per object the lane HOLDS, citing its sha — the same partition `who --lane` reports and `lane-end` refuses on. `--no-github` skips it |
| 6 | (f) | the tmux window is renamed, and `/rename <new>` is typed into the lane's own pane (Amendment 12(h)'s M1 — the only path a running session's name has) |

**The first four are ONE commit, refused or whole.** Any two of them apart is a
state no reader can read: a row under `<new>` whose log is still `<old>.md` is a
lane whose history `who --lane` cannot find, and an alias without the row it
points at is a name that resolves to nothing.

### The refusals — clause (a), before anything is written

| the state | why |
|---|---|
| no row under `<old>` in any case, and none through an alias | a rename moves a row that exists; `lanes --all` lists the ones that do |
| a row under `<new>` in any case | two rows for one name is what every writer here refuses (Amendment 15(a)) |
| `<old>` and `<new>` are one name under any case | that is not a rename but a change to the row's own SPELLING, which every reader already resolves to — Amendment 15(d)'s hand act |
| `<new>` is not `<repo>-<n>` and no `--verbatim` | Rule 4's form is what `lanes --prefix`, the next free position and `lane-start <repo> <n>` are computed from |
| a **LIVE** session holds `<old>` in another window | its own name is locked to the lane and only it can change that (Amendment 12(h)); renaming from elsewhere would leave a running conversation named for a lane the register no longer has |
| two rows under `<old>` differing only by case | there is no ONE row to rename (Amendment 15(d) merges them first) |
| the alias table would gain a **cycle** | a chain that returns to its own start has no end to resolve to |
| `<new>` is already an alias **key** | a row wins over an alias, so a row under a name some other lane was renamed away from would END that lane's old name resolving |
| `lanes/log/<new>.md` exists in **any case**, here or on `origin` | one lane's history appended to another's is the one thing an append-only log cannot be walked back from |
| the row's handoff is **outside the workspace repository** | a commit cannot carry a file outside its own checkout, so the rename would be three moves and a note |
| an unreadable register, log, handoff or alias table | fail closed, naming the read — an alias table that cannot be READ is not an estate with no renames |

Each of them says **"Nothing was written."** The command moves four files, and a
half-done rename is not something a second run can finish.

And a filesystem can still refuse the third of four moves. Every write between
the first byte and the commit is made against a **snapshot** taken before it, and
every exit path — a `die`, a signal, the shell — restores it: the log, the
handoff and `lanes/aliases.tsv` go back to what they were and nothing is
committed. The register is not in the snapshot and does not need to be:
`replace_line` proves the new file before it writes a byte of `LANES.md`.

### The alias table, and the one seat every reader shares

`lanes/aliases.tsv` lives beside the register — `<old><TAB><new><TAB><UTC>`,
comments on `#` lines — and `lane-rename` is its only writer. It has **one
layer**, unlike `repos.tsv`: a repository alias is an organisation's fact and a
lane rename is one person's register moving, so openRepoTools ships none.

Clause (e) lists the readers that resolve through it — `who`, `lanes`,
`live-holder`, `history`, Rule 6 attribution, `lane-start`'s row lookup, the
`SessionStart` block and Amendment 12's guard — and **that list is not built as a
list.** Amendment 15 already put `canon_lane` in front of every one of them, so
the resolution is hooked there, once:

* **a name with no row** is looked up in the table, case-insensitively, and the
  chain (`a→b`, `b→c`) is walked to its end — stopping at **the first name along
  it that has a row**, because **a row wins over an alias at every hop**, not only
  at the start. That is what makes renaming a lane back to an old name readable,
  and it is what keeps a lane legitimately minted under a freed name (`a→b` frees
  `a`, and the next free position hands it out) as its own lane rather than a
  second reading of `b`. The walk is bounded by the table's own size, never by a
  fixed number of hops: a chain longer than the cap would otherwise resolve to an
  intermediate name and clause (e)'s "for ever" would quietly end there;
* **the lane field of every old log line** is resolved *on the way in*, in
  `LOG_AWK`. Clause (c) is explicit that the lines above the `RENAMED` are never
  rewritten, so a renamed lane's log holds its history under two names in one
  file; read byte for byte, half of that lane's holds would be invisible to
  `who --lane` and to `lane-end`'s refusal. One rule in the parse serves every
  reader behind it;
* **the tmux window's name.** A rename run from another window leaves that
  window carrying the old name — and the name guard resolves it, **renames the
  window itself** (one tmux call, unlike a session name), and types the
  `/rename`. So a rename made from anywhere is finished by the lane at its next
  prompt, with nobody typing anything.

The old name resolves **for ever**: nothing in this toolset ever removes a row
from that table.

### `RENAMED` is a lane-kind verb that changes no state

It joins Amendment 7's verb list as a lane verb — its object is `lane:<name>` —
and it is outside the last-line rule **by construction**: every state read here
enumerates the five verbs that do change state (`STARTED PAUSED RESUMED ENDED
RETIRED`), so a lane's last `STARTED` or `PAUSED` is still its last one after a
rename, which is what decides whether it is running, swapped or closed. It is not
written by hand: `lanes-edit.sh log RENAMED …` is refused and names `lane-rename`,
because a line on its own is exactly the 2026-09-14 hand rename this amendment
replaces.

### `lanes` stays read-only

Amendment 11(j)'s *"it writes nothing"* is untouched (clause (h)). `lanes
--rename` is refused with the one word to type — the flag is answered rather than
left unknown, because the request that produced this amendment spelled it that
way.


## The handoff (Amendment 17)

**In force 2026-09-14T09:45:33Z** (revision 2, `/ctx` included), with Amendment
18(d)'s `--exit` and Addendum 2's respawn line. **A HANDOFF IS THE SWAP, UNDER
ONE NAME; A LANE RESUMES FROM ANY AGENT THAT CAN READ IT; AND `/ctx` IS THE
WHOLE ACT IN ONE WORD.**

### One act, three names

| where you are | the word |
|---|---|
| in the lane's session | `/handoff [why]` — and `/swap` and `/lane-swap` are its aliases, kept so that nothing written about them stops working |
| in a shell in the lane's window | `lane-handoff [why]`, placed on `PATH` by `openRepoTools --install` |
| clearing the context | `/ctx`, which is `/handoff --restart` |

The steps are Amendment 8(a)'s and Amendment 11's, unchanged: the identity
triple fixed, the handoff file refreshed with a fresh Rule 3 top block, the
writers polled, `PAUSED` written, the restart line printed. What differs between
a context clear, a usage reset, a profile switch and handing the lane to someone
else is only **why**, and the record's free text has always carried that. The
word was wrong, not the act.

The skill `skills/handoff/SKILL.md` is the single source of the act; the files at
`skills/lane-swap/SKILL.md`, `commands/handoff.md`, `commands/ctx.md` and
`commands/swap.md` name it and add nothing — two copies of one procedure that
must stay byte-equal is the alternative the amendment rejects by name.

### The record's two new sub-fields

The `PAUSED` payload gains two beside Amendment 11(c)'s `window`, `dir` and
`profile`:

```text
PAUSED — lane repoHF-1, session a17a0001-…@Eagle, 2026-09-14T17:05:11Z, lane:repoHF-1 → swap; window hfsess:0 @21; dir ~/projects/repoHF; profile team-05a; workstation Eagle; agent claude; transcript a17a0001-… — clear
```

- **`agent <name>`** — `claude`, `codex`, or the launcher's name for whatever
  wrote the line. A **manifest key**: letters, digits, `.`, `_`, `-`. The
  pattern is also how this sub-field gets the `; ` rule without a token of its
  own, and `lane-start --agent` reads it back to choose a launcher.
- **`transcript <id|none>`** — the agent's own resumable id where it has one.
  `none` is an **answer**, not a gap.

And the tooling writes a third beside them, `kind <in-process|respawn|unknown>`,
because it is the one fact about the act that FOLLOWS the record and no later
reader can infer it: **an in-process clear does not kill this lane's writers**
(**Amendment 17 Addendum 1**, clauses (h)–(k), in force 2026-09-14T20:59:31Z).
Measured here on 2026-09-14 — a harness `/clear` mints a new transcript id in the
SAME process, so every subagent survives it and only its in-flight tool calls die
(a `Bash` killed that way exits 137); the handoff written a minute earlier said
*relaunch every writer below*, and the live count a minute later showed all five
alive on their worktrees.

| kind | what happened to the process | written by |
|---|---|---|
| `in-process` | it keeps running, and every writer with it | `lane-handoff --in-process` |
| `respawn` | it is replaced or ended — the pane respawned, the session exited, a profile switch, a usage-reset relaunch | `--restart`, `--exit`, `--late` |
| `unknown` | not this command's to know: a plain handoff may be followed by a `/clear` or by a relaunch | a plain `lane-handoff` |

The same word is in the line's FREE TEXT after the why — `clear in-process`,
`clear respawn`, `kind unknown` (clause (h)) — so the person reading the record
reads it too. **THE KIND SAYS WHAT TO EXPECT AND NEVER WHAT TO DO** (j). What
says what to do is clause (i), and it is the same in every kind: the `WRITERS`
section is **a list to COUNT, not a list to relaunch** — `ListAgents` in Claude,
the agent's equivalent elsewhere; a writer still live OWNS its worktree and is
sent one message rather than relaunched; only a writer that is NOT live is
relaunched, from where it stands. Where the count and the block disagree, **the
count wins**: the block is what the paused session expected and the count is what
is true. And one worktree is one writer's for as long as that writer is live (k).

**The writer validates both** (`pause_subfields_check`, called from
`write_event`) and refuses the line rather than writing a sub-field no reader can
use: this log is append-only, and `lane-start` launches on what it reads back.

Three reads answer for them, all read-only: `lanes-edit.sh lane-agent <lane>`,
`lanes-edit.sh lane-transcript <lane>` and `lanes-edit.sh lane-last <lane>` (the
lane's last lane-kind line as `<verb>	<utc>	<session>	<payload>`). `swapped`
gains a sixth and a seventh field for the same two:

```console
$ lanes-edit.sh swapped Eagle
repoHF-1	2026-09-14T17:05:11Z	hfsess:0 @21	~/projects/repoHF	team-05a	claude	a17a0001-…
repoSW-1	2026-09-12T10:00:00Z	claude-team-05b-20260912102132-2699:0
```

The second row is every record written before an amendment: the fields are
**empty rather than guessed**, and the two reads answer **8**. Nothing is
backfilled (Amendment 7(i)); each lane cuts over at its own next handoff. **The
first field before the first tab is still the lane**, which is the contract every
reader of this output takes and what makes a sixth and a seventh safe to add.

### The launcher table — `lane-start --agent <name>`

`lane-start <repo> <n>` reads the row and the last `PAUSED`. With no `--agent`
the default is **the agent that paused**; with no `PAUSED`, `claude`.

| agent | what is launched |
|---|---|
| `claude`, its transcript here | `claude --name <lane> --resume <id>` — Amendment 6's case (a), unchanged |
| `claude`, no transcript here (or `--agent claude` named, or `LANE_START_FRESH=1`) | `claude --name <lane> --session-id <fresh uuid> "<the handoff's top block>"` |
| `codex` | `codex "<the handoff's top block>"`; its resumable id is read back where it prints one |
| anything else | **a refusal naming the two it knows** — a lane is resumed by an agent whose launch has been taught and tested, never by a guessed argv |

**The top block is the head of the handoff down to its first `---` rule** (200
lines at the outside), and it is delivered **after** the Rule 3 stamp is written,
so the session reads a prompt that already carries the record of its own resume.
The stamp names the agent where the agent is not Claude — `RESUMED by codex
<id> (lane <lane>) at <UTC>` — and the row's session cell is appended in that
agent's own spelling, `harness <uuid>` / `Codex <id>` / `<agent> <id>`, which is
how the register has spelled Codex sessions since 2026-09-05.

### `/ctx` — one word, and everything after it is automatic

`/ctx` (`/handoff --restart`) performs the handoff and then **restarts in
place**: `tmux respawn-pane -k` on the lane's own pane, with a NEW session of the
same agent whose **first prompt is the handoff's top block**. That block's
`WRITERS` section lists every worktree the lane had running: its branch, its last
commit, what it was holding, and the brief it was given, so the new session finds
them rather than discovering them — and its first line is Addendum 1 (i)'s, the
COUNT. **`/ctx` says which it did** (j): this one respawns, so the record says
`kind respawn` and the count then finds none, which is what makes relaunching
each one right. A `/ctx` that clears IN PLACE is the other kind and must say so
(`--in-process`, `kind in-process`): the process survives, its writers survive
with it, and the block says to EXPECT every writer below live.

**The record comes first, always, and the record is THREE writes.** A `/ctx`
**refuses before it kills anything** where the `PAUSED` line did not land, where
the row was not flipped (the register would say RUNNING about a session that has
just been replaced), or where the handoff could not be refreshed (its top block
is literally the new session's first prompt, and a stale one hands over the
instructions of another act). A pane is never respawned over an unrecorded lane.

**The respawn line is `lane <lane>`**, and never `restart <lane>` — Amendment 18
Addendum 2 (i-8): the respawn *"relaunches the lane's own pane with `lane <name>`
(its parked branch is exactly Amendment 11(i)'s act), or through the launcher
directly"*, and `restart` leaves the person's `PATH` with `openRepoTools#43`.
`lane <name>` needs no profile argument: its parked branch reads the record the
handoff has just written — the lane's recorded directory and profile — and asks
nothing. **Where `lane` is not on `PATH`** (it arrives with #43, and this act
shipped first) the line is `pclaude --lane <lane> <profile>`, the same act one
door along, and a `lane` on `PATH` that is not this estate's word is passed over
for it with a line saying so: a respawn is the one act no later refusal can undo,
so the word is used only where it can be SEEN. `LANE_START_FRESH=1` is the one
seam that says *a new session, primed by the top block* — which is what a
context clear is, and why `/ctx` does not resume the transcript it has just
paused. It rides in the ENVIRONMENT, so it survives `lane` handing the launch on
to `lane-start` exactly as it survives the launcher doing so.

`/handoff --exit requested by <uuid>@<host>/<container>` is the other end
(Amendment 18(d)): after the record, `/exit` is typed into this lane's own pane
and the session **ends**, because a handoff to another place is a handoff and
not a restart.

### `--late` — the record a swap never left

A session that died at a usage limit wrote no `PAUSED`, and the lane's log still
reads as running. `lane-handoff --late --at <UTC> [why]` writes that record after
the fact — and **it is written from a shell BEFORE the relaunch**:

```sh
lane-handoff --late --at 2026-09-14T12:02:27Z "late; usage limit hit before the swap"
pclaude <profile>      # and only then
```

**The rule, and it is the whole of why `--at` is required.** A lane's state is
its log's last lane-kind line **in file order** (R14), and the log is
append-only. A late `PAUSED` appended after the `RESUMED` that `lane-start`
writes at the relaunch would make a lane that is **running** read as paused, in a
file nothing rewrites. So a late line is **dated by its own field** — the moment
the old session ended, which the caller names — and it is written only where the
lane's last lane-kind line is a `STARTED` or `RESUMED` **older** than that
instant. A last line that is already a `PAUSED`, an `ENDED`/`RETIRED`, or a
`STARTED`/`RESUMED` at or after it is a **refusal that writes nothing** and names
the act to take instead. Run from inside the session that has already been
resumed, `--late` refuses: the honest record of the state that session holds is
its own next `/handoff`.

### The transcript follows the lane

`lane-start`'s resume case (a) looked for `<the row's last id>.jsonl` only under
the **current profile's** projects directory, so a lane restarted under a new
profile after a usage limit never resumed its conversation.

**Measured first, and the fact shrank the act** (2026-09-14T12:35Z): on a
launcher-configured workstation every profile's `projects/` is ONE shared
directory — `readlink -f ~/.claude-profiles/profiles/<org>/<team>/<any>/projects`
→ `~/.claude-profiles/state/opensoft/projects`. So a transcript needs **no move**
to be resumed under another profile. `lane-start` therefore **says where it found
the transcript**, and says when that directory is shared:

```text
lane-start: transcript a17a…f3 found in this profile's projects directory
(~/.claude/projects), which IS the directory profile(s) t3 read too (one
shared directory: a profile switch resumes this lane by id and moves nothing)
```

Where the two profiles' `projects/` really are two directories — a workstation
without the launcher's layout — the transcript is **moved** into this profile's
(the `<uuid>.jsonl` and its sibling `<uuid>/` directory), a pointer
`<uuid>.jsonl.moved-to-<profile>-<UTC>` is left where it was, and the move is
said on one line. A **copy** would leave two live transcripts of one uuid to
diverge, and nothing merges them.

**A uuid whose holder is LIVE in the other profile is a refusal, never a move**
(Amendment 18(h): a transcript is held by ONE live process). The refusal names
the pid, where that process is (its window, or `bg`), the profile it is under,
and the retire act — `lane-end <lane> --retire <pid>` — and nothing is moved and
nothing is launched.

## Hand edits

After **any** hand edit made with an allowed tool (python read/write, `sed -i
--follow-symlinks`, a `>>` append), run
`LANES_LANE=<lane> ./lanes-edit.sh commit "<message>"` **immediately** — don't
leave it sitting uncommitted while you do something else. Prefer
`set-row-state` / `replace-in-row` / `append-line` over a hand edit in the
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

**Two commands, and the second one is the same one that creates a workspace
repository from nothing** (Amendment 9(c)). `wip init` is idempotent, so on a
machine whose repository already exists it clones it, adds nothing to a seeded
repository, writes the pointer file and runs `link-estates`:

```sh
openRepoTools --install     # the thirteen commands, the three skills, the three command files and the hook entry
openRepoTools wip init      # create or adopt the workspace, and link it
```

If the host was set up from `opensoft/workBenches`, `./setup.sh` has already
run both and there is nothing to type at all — **and that is the whole of
Amendment 11's decision 8(b) as `R-A11-13` corrected it: there is NO second
installer.** `setup.sh` already runs `openRepoTools --install`, so `lane`,
`lanes` and the `/restart` skill ride the step that is there rather than a new
one. What Evidence 5 actually measured was narrower and is worth saying: after a
machine rebuild the launcher was present and `lane-start` and `lane-end` were
**not on `PATH` at all**, so the launcher's documented degradation ran a bare
`claude --resume <uuid>` — no stamps, a derived session name, a window left
`claude`, three stampless restarts in one day. The gap was never that nothing
runs `--install`; it was that the installed `openRepoTools` predated the move
and placed no lane helper.

**And the launcher exports this workstation's name.** `$LANES_WORKSTATION` is
written once per host and exported into every session and container the launcher
starts (`R-A11-14`). Outside a container `hostname -s` still answers; **inside
one with no value every writer here refuses**, because a container's hostname is
the container's id and this log is never rewritten.

The warning from Amendment 3's "Raven setup (operator, Brett)" block still
stands and the linker does not do it for you: **diff Raven's local `LANES.md`
against this one and append its missing rows with `lanes-edit.sh add-row`
BEFORE the local file becomes the symlink.** Raven's file may hold rows this
register has never seen. `link-estates` never deletes a real file — it moves
one aside as `<path>.pre-link-estates-<UTC>` — so the content survives either
way, but a row nobody re-appends is a row nobody reads.

### Coming from the pre-move world

A workstation that ran lanes before Amendment 9 carries
`~/.local/bin/lane-start` and `~/.local/bin/lane-end` as **symlinks** into its
workspace checkout, placed by the old `link-estates`. Remove them before the
first `--install`, in this order:

```sh
rm -f ~/.local/bin/lane-start ~/.local/bin/lane-end   # while they are still symlinks
openRepoTools --install                               # places them as regular files
link-estates                                          # repoints ~/projects/xFactory/lanes-edit.sh
```

**You are not asked to remember it: `--install` refuses** (A9 Addendum 4,
R-A9-12). In its planning phase, before any of the twenty-seven artifacts is placed,
it walks all thirteen targets and dies naming every one that is not a regular file,
what it is, and the one `rm` that clears them. `cp` FOLLOWS A SYMLINK, so an
install over these would leave the two commands UNINSTALLED — the targets stay
links — and would write the post-move bytes into `opensoft/brett-wip`'s working
tree, which is the repository every lane writes: `lanes-edit.sh`'s
`refuse_dirty_checkout` then refuses `log`, `claim` and `release` on that
workstation until somebody runs `git checkout -- lanes/`.

It is not tidiness. workBenches' `setup-estate-commands.sh` refuses the WHOLE
estate install when any target "already exists as a symlink", and `setup.sh`
swallows that exit into one `⚠` line — so a host that skips this looks set up
and has no estate commands on it. The installed `link-estates` reports either
stale symlink it finds, with the command that replaces it.

**The helpers no longer resolve the register from their own real path.** They
read `~/.agents/workspace.yaml`, which is what makes an installed command in
`~/.local/bin` able to find a register that is nowhere near it.

Also drop the retired worktree if this workstation still has one:
`git -C ~/projects/xFactory worktree remove .lanes` (Eagle did this on
2026-09-10).

## Reading the history from before either move

**There have been two moves and they used different mechanisms**, so the two
halves of the history are read differently. The REGISTER moved in 2026-09-10
under Amendment 5, by `git subtree`, from the orphan `lanes` branch of
`opensoft/xFactory` into the workspace repository. The CODE — these four
commands, their suite and this manual — moved in 2026-09-13 under Amendment
9(f)(2), by ONE `git filter-repo` run with a written path map and an
`--allow-unrelated-histories` merge, from the workspace repository into
`opensoft/openRepoTools`. `git subtree split` was rejected for that second
move because it carves one prefix and renames nothing, while the move was two
source prefixes landing on three destinations with a rename on every path.

**The code half**, in a checkout of `opensoft/openRepoTools`, where
`--follow` crosses the rename and the unrelated-histories merge:

```sh
git log --follow --oneline -- lanes-edit.sh      # reaches lanes/lanes-edit.sh
git log --follow --oneline -- lane-start         # and so for lane-end,
                                                 # link-estates, repos.tsv,
                                                 # tests/test_lane_helpers.sh
                                                 # and this file
```

The rollback for that move is the annotated tag **`pre-amendment-9-move`** on
`opensoft/brett-wip`, placed at the commit that still carried all seven paths,
immediately before the strip. Checking it out and running its
`scripts/link-estates` puts a workstation back on the pre-move world with its
data untouched, because no data moved.

**The register half**, which is untouched by the 2026-09-13 move — no data
moved. `git subtree add` imports commits unchanged, so the 1242 register
commits made between 2026-09-09 and the Amendment 5 move carry their pre-move
path (`LANES.md`, at the root of the orphan branch), and git's default history
simplification stops at the subtree merge. Its own two halves are one command
each, in the workspace checkout:

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
