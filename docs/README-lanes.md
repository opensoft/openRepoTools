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
Before attaching a LIVE lane, `lane` also checks that the window's live
transcript is the row's latest UUID and is named for that lane. It checks all
tmux windows for another window using the same lane name (ignoring multiple
links to the same window ID), then renames the selected window to the lane when
needed. A window already named for a different registered lane is not renamed.
If the transcript or row is behind, it refuses instead of disguising
the mismatch; run `lane-start --no-launch <lane>` in that window to record the
new transcript. `lane-start` applies the same name-uniqueness check before a
NEW lane's launch renames its window; an existing lane's own window in another
container keeps its name until it hands off (Amendment 18), so it is not asked there.

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
lane-end openRepoShape-2 --inventory-only  # …past the close-out gate (#163), trees left recorded
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

`--retire` is **the same single write**, carrying `RETIRED` instead of `ENDED`
— since Amendment 13(a) the state cell is one phrase that `set-row-state`
REPLACES, so there is no second act, no word to find inside the cell and no
history in it to preserve. `--state-was "<text>"` named the exact text the old
two-step had to replace; it is **accepted and ignored**, and a re-run that
passes it does the same thing a re-run without it does.

**It refuses (exit 2) while anything of the lane's is still on disk** — the
close-out gate of opensoft/openRepoTools#163, asked after the in-flight guard
and before any write, `--dry-run` included. The question is #162's sweep as a
dry run, `lane-worktrees sweep <lane> --branches --include-scratch
--include-caches --dry-run --porcelain` ([its exit
contract](#the-exit-contract-lane-ends-gate-163)): **3** (something to retire)
and **2** (the sweep refused the lane, or a read failed) are a refusal that
names every tree, branch, scratch directory and cache the table gives the lane,
relays the sweep's own reason where it refused, and prints the table's command
and the `--yes` that would retire them — which removes only what is on origin
or in a bundle, never a live writer's tree. **Any other exit, or
no `lane-worktrees` beside the command, is a gate nobody read: exit 1, never a
pass.** Beside the table the gate makes two reads of its own. Every tree of the
lane's is read with `git status --porcelain --ignored`, so a tree holding only
an `.env` or a `node_modules` is named as holding them and never as clean. And
every entry directly under the lane's own root, `.lane-worktrees/<lane>/`, that
no tree, scratch or cache row names is **residue** — the ignored leftovers no
row of the sweep reaches — and it refuses even where the sweep answered 0, as
a cache row does; a root that cannot be listed is the gate unread (exit 1,
whatever the sweep answered), never an empty one. Other lanes' trees in a shared checkout are FOREIGN, are
counted for nobody, and never hold this lane — but a FOREIGN row names nothing
for the residue read either, so a standalone clone directly under the lane's own
root, which the sweep keeps FOREIGN, is residue and holds it.

`--inventory-only` is **the one door past the gate**: the lane ends although the
gate found something, refused, or could not be read, nothing on disk is touched,
and the trees stay in the lane's #97 inventory, where the daily report lists them
as an ended lane's. The reason it was let past is **written down**: the row's
closing phrase gains `ENDED WITH --inventory-only: <what the gate found>; they stay
in its #97 inventory`, and the lane's own `ENDED` (or `RETIRED`) line carries the
same words in full. It does not pass the in-flight guard — that is `--force`'s,
and a lane with both wants both. **`--sweep` is not built**: retiring the trees
in the same run as the ending is not one act, so the word is refused by name
rather than read as an unknown option; `lane-worktrees sweep <lane> --yes`
retires them first, on its own.

`lane-end --retire-dormant <repo>` is a **different act again** and ends no
lane: it is Amendment 19(c)'s sweep of the rows that have no lane left to end.
It is described under [A closed or dormant lane leaves the
listing](#a-closed-or-dormant-lane-leaves-the-listing-amendment-19) below.

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
PYTHONPYCACHEPREFIX="${XDG_CACHE_HOME:-$HOME/.cache}/openRepoTools/pycache" flock "${TMPDIR:-/tmp}/openrepotools-pytest.lock" python3 -m pytest tests -q -p no:cacheprovider
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
one, and it is not reachable through the helpers in the ordinary case — a live
lane's `claim --force` takes over a stale `CLAIMED` and nothing else (or, per
the dead-lane exception below, a **dead** lane's hold of any verb, an earlier
`TAKEOVER` included), and refuses outright when more than one lane holds the
object.

*Known, NOT deliberate — opensoft/openRepoTools#74.* A CHAIN of two takeovers
on one object (`A` claims; `B` takes over from `A`; `C` later takes over from
`B` — the dead-lane exception's own `TAKEOVER`-of-a-`TAKEOVER` shape) makes
`who` report **zero** holders, neither `B` nor `C`: `superseded_by`'s "does
some other lane's last line here read `TAKEOVER`" test does not distinguish
the CURRENT taker from an earlier, already-superseded one, so `B`'s own
stale `TAKEOVER` is misread as proof that `C` is superseded too. Every log
line involved is correct and in order; only this derived view is wrong.

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
`--force` takes over a stale claim — or, per the dead-lane exception just
below, a dead lane's hold of any verb — and nothing else, writing one of TWO
payload forms for either reason (Copilot round 9, PR #61: this sentence
named only one). `TAKEOVER ← <the stale claim's comment URL>` when the hold
taken over was itself a `CLAIMED` posted as a GitHub comment and that
comment can still be found; `TAKEOVER ← lane:<the dispossessed lane>`
whenever it cannot — always true for a dead lane's own `OPENED`, `LANDING`,
`WITHDRAWN` or earlier `TAKEOVER` (none of those was ever a `CLAIMED`
comment to find), and also true under `--no-github` or a search that simply
comes up empty. `TAKEOVER` is itself an open verb, so no second line is
needed either way to say the taker holds it.

**Or the holder's LANE is dead, whatever the verb** (opensoft/openRepoTools#30).
Staleness answers Rule 1's own question about one claim; it says nothing about
a lane that went silent and was retired, leaving an `OPENED` PR or a fresh
`CLAIMED` issue behind that neither gate above will ever call takeable — the
verb-check refuses the PR outright, and a `CLAIMED` lane that later `OPENED` a
PR naming it is deliberately never stale, which is exactly backwards once the
lane itself is gone. `--force` also takes over a hold of ANY open verb when the
holder's own object log ends its lane-kind lines (`STARTED`/`PAUSED`/
`RESUMED`/`ENDED`/`RETIRED`) on `ENDED` or `RETIRED` — a swap (`PAUSED`) is
deliberately not dead — **and** no live session for it is found on this
workstation (`live_holder`, the one liveness implementation this file has,
never a second one): a `RETIRED` register line is not proof by itself that
nothing is still running under that name (opensoft/openRepoTools#39), so the
register's verdict is checked before it is trusted. **That check is made only
from inside the lane's last binding** (Amendment 18(b)): the `host` and
`container` of its last `STARTED`/`RESUMED` before the terminal line must be
this place's — a line from before Amendment 18(a) is matched on its own
workstation — or the binding's window must be gone from a tmux server this
host shares with it. A lane last bound anywhere else is UNKNOWN, never dead,
and `--force` refuses it, naming that binding. Before this the only path
was a `release` of the dead lane's held objects by hand, one at a time, run
under its own name on the taker's word.

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
| 7 | another act got there first and this one wrote nothing: `claim`'s `CLAIM-LOST` (another lane's claim landed first), and `set-lane-state` / `set-lane-tree`'s lifecycle fence (openRepoTools#91, below) |
| 9 | `CLAIM-LOST` — issue #30's own dead-lane verdict could not be reconfirmed before a `--force` takeover's push landed: the source lane resumed, a live session now backs it up, or that could not be read at all (`claim` only). Never 7 — that code is a RIVAL's claim, and this is the same lane the takeover was granted over |
| 10 | `lane-state`: the lane's lifecycle snapshot is there and could not be read (openRepoTools#91, below) — never the 8 that means it has none. It was 9 until #61 spent 9 on `claim` |
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
| `lanes-edit.sh lanes [--repo\|--dir\|--prefix\|--ws\|--lane\|--here\|--all\|--closed\|--fetch]` | every lane, newest write first, tab-separated: clause (j)'s **ten columns in clause (j)'s order** — name, state, workstation, profile, window, last transcript uuid, directory, held objects, age, the line that binds it — then the read's own three, `home`, the count of live forks, and — since Amendment 18(b) — whether THIS place may pronounce on that binding (`here`, `elsewhere`, or `none` for a row with no binding line at all), which is what `lane-groups` files an `IDLE` row by — then Amendment 19's four: the row's **class** (`closed`, `dormant` or `none`), its `started` cell, its state cell's **head** and the **flag words** in that cell. The last two are carried **for a row with no object log** — 19(a)'s dormant row, whose cell is all this read has to show — and are `none` for a row that has one, which has its log instead: they are free text of up to 280 characters per row and the table the listing joins on is walked once per lane, so carrying them for every row cost the whole estate 3x (42 s against 14 on a register of 132 rows, measured). **No column is ever empty**, because three readers split the row with a tab-IFS `read`, to which an empty field between two tabs is no field at all. **CLOSED and DORMANT rows are left out unless `--closed` is passed** (19(b)); `--lane <name>` is never filtered, because its caller has named the lane. `lanes` and `lane` each render the subset their surface needs (A11 Addendum 4 ruling 7), and column 10 is the read's so the two cannot offer different commands; since Amendment 18 Addendum 2 the word it names is `lane <name>`. **The one read whose default is local**, and `--lane <lane>` answers about one without walking the estate. `--prefix <repo>` is the LABEL fallback the checkout narrowing and `lane-start <repo>` both ask for, used only where a lane has neither a home nor a `dir` |
| `lanes-edit.sh lane-groups [<ws>]` | **the rows on STDIN**, each with the group the pick puts it in: `available` (PARKED, or a binding that workstation **and container** prove dead), `live`, `elsewhere` — an `IDLE` row whose binding is another container on this same host is **elsewhere**, because IDLE means this host saw no live record and across that seam the pid it would have read is in another namespace (Amendment 18(b)). Closed and dormant rows are DROPPED (Amendment 19). It reads nothing itself — the caller has already paid for `lanes`, and two surfaces computing one partition is how they come to disagree |
| `lanes-edit.sh next-free <repo>` | **the rows on STDIN plus every row of this checkout's register and of `lanes/archive/LANES-retired.md`** (Amendment 19(b) and (d): the rows the listing hides and the rows `archive-rows` has moved out still hold their positions), and the LOWEST position no lane of that repository HAS EVER held — `ENDED` and `RETIRED` rows reserve theirs, because a lane's identity is its name and its object log `lanes/log/<lane>.md` is append-only, so a second lane at a retired position would write its life into the first one's file. The name before the position is compared whole, so `repo-foo-1` is no lane of `repo`. `lanes`'s footer and `lane`'s `f` answer both read it, so the two cannot offer different positions |
| `lanes-edit.sh binding <lane>` | where the lane is bound, and whether this place may pronounce on it: `<host> <container> <window> <utc> <session> <os> <here\|elsewhere> <live\|gone\|unknown>` (Amendment 18(b)). **0** bound · **8** free · **1** the log could not be read, which is never "this lane is free" |
| `lanes-edit.sh workstation` | `<workstation> <source> <host> <source> <os> <source> <container> <source>` — eight tab-separated fields since Amendment 18(a), the first two unchanged. A source is `seam`, `hostname`, `workstation`, `kernel`, `outside`, or, for the workstation itself, `container-unset` |
| `lanes-edit.sh fetch-age` | how old this checkout's answer is |

**`request-handoff` is the one WRITE in that family** and is not a read at all:
`lanes-edit.sh request-handoff <lane> [--wait <s>] [--session <uuid>]` writes
clause (c)'s `HANDOFF-REQUESTED`, pushes it, types `/handoff --exit requested by
…` into the bound pane where that pane is on this tmux server, and waits;
`--force "<why>"` is clause (e)'s second invocation and releases the binding on
its holder's behalf. **0** the lane is free — bind it · **2** the wait ended
empty, or the request was refused · **8** the lane was already free · **1** a
read failed.

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

**A duplicate holder of a lane's OWN transcript is a different thing, and it IS
killed** (opensoft/openRepoTools#39, Amendment 18(h)). A cross-profile resume
can leave a `bg-pty-host` running `claude --fork-session --resume
<path>/<uuid>.jsonl` behind; once a later `lane-start --no-launch` binds that
forked id as the row's own session, the id is no longer one `forks` (decision
8(e)) will ever report — it is designed to stay silent about an id the row
DOES record — while a second live process now holds the one transcript
Amendment 18(h) says exactly one may. `lanes-edit.sh duplicate-holder <lane>`
finds it in the PROCESS TABLE instead (`pgrep -f` for a live `--fork-session`,
then `ps -o pid=,ppid=,args= -p` per candidate — portable across GNU and
BSD/macOS), matched against every id this lane's row has ever carried, and
excludes the lane's own live holder (`live_holder`, the same implementation
`live-holder` already calls) **and the harness's own companion of it** —
Amendment 8 ruling (g)'s `kind: bg` record carrying the same id in the same
profile as an interactive record of it, which is one session and not a rival
holder, together with any wrapper whose child is that companion. A records
tree that cannot be read for that test is a read that failed, never "no
companion". `lane-end <lane> --retire <pid>` tries `forks`
first and this second, and on a match here it TERMs the pair — the
`bg-pty-host` parent and its child — and reports the pids it signalled; it
refuses, naming the reason, when the pid given is the lane's own live session
rather than the duplicate. Before this the retirement was a bare `kill -TERM`,
outside every tool this estate has.

### The workstation's name

`$LANES_WORKSTATION`, exported by the workBenches launcher from the host into
every session and container it starts. Outside a container it still defaults to
`hostname -s`. **Inside a container with no value, every writer refuses, exit 2,
naming the variable** — because a container's `hostname` is the container's id,
not a workstation, a row on a workstation that does not exist is a row no reader
can match, and the log is never rewritten. `lanes-edit.sh` already carries six
such lines in one lane's log, and they stay where they are.

## One binding per lane (Amendment 18)

**A lane has ONE binding. The record says where it is — host, OS, container,
window — and a second place ASKS the first to hand off before it binds; nothing
is taken silently.** Ratified by Brett Heap 2026-09-14T13:15:18Z, verbatim
*"merge 37 and 78, ratify revision 4"*, on his observation of the same day:

> we are working on lanes tooling … if I run a lane, then i am on a host running
> macOS or linux or windows … and in all 3, i might be in a container. we should
> probably note the host name, OS type and container name if there is one. so if
> I am on wsl and I am in cloudBench and then move to pyBench, when I try to
> restart in pyBench, it should ask me if I want to pause the lane on cloudBench.
> we shoudl not allow two bindings to a lane … we need to send a signal to that
> session to shutdown. once it is shutdown, then we alow the new connection to
> bind

### Why — a pid does not cross a pid namespace

A lane's liveness is read from the harness's session records and a `kill -0` of
the recorded pid. Both are **local** facts. Across workstations the tooling
already said so — another machine's row is UNKNOWN and `who` says to ask that
lane. Across **containers on one machine** it did not: two bench containers on
Eagle share the profile directory, so pyBench can read a record cloudBench
wrote and then `kill -0` a pid **in cloudBench's namespace**, which is either
nothing or some other process. A lane live and writing in cloudBench read NOT
LIVE from pyBench, and `lane-start` there took the name.

### The three sub-fields

`STARTED`, `RESUMED` and `PAUSED` carry three more, after Amendment 11(c)'s
`dir`/`profile`/`window` and Amendment 17(b)'s `agent`/`transcript`:

```text
STARTED — lane openRepoTools-3, session d1ac715c-…@Eagle, 2026-09-15T12:38:51Z, lane:openRepoTools-3 → home opensoft/openRepoTools; estate openRepoTools; dir ~/projects/openRepoTools; profile team-05c; window claude-team-05c-…:0 @71; host eagle; os wsl; container cloud-bench
```

- **`host <name>`** — the MACHINE's short hostname **as it reads outside any
  container**. The launcher exports it (`LANES_HOST`); a writer outside a
  container reads `hostname -s`; a writer **inside** one with no export writes
  the **Rule 10 workstation name**, because in this estate a workstation is one
  host and a container's own `hostname` is its id.
- **`os <linux|macos|wsl|windows>`** — the HOST's operating system as the person
  means it. The launcher exports it (`LANES_OS`); with no export the kernel is
  probed: `Darwin` → `macos`; `Linux` whose `/proc/version` names `microsoft` →
  `wsl`; one naming `linuxkit` → `macos` (Docker Desktop's VM); any other
  `Linux` → `linux`. **`windows` is written only by a launcher on the Windows
  host itself** — this toolset is bash and runs in WSL2 there, so its own probe
  never says it.
- **`container <name|none>`** — the bench's name as the launcher exports it
  (`LANES_CONTAINER`: `py-bench`, `cloud-bench`, …); inside a container with no
  export, **that container's own `hostname`**, which for Docker's default is its
  id and is the one thing that tells two unnamed containers apart; outside every
  container, the word `none`.

They are written by **`write_event`**, the one writer every caller goes through
— `lane-start`'s `STARTED`/`RESUMED`, the handoff's `PAUSED`, and the forced
release below — so no boundary script carries a copy of the probe. **A value is
read live at every write and never carried across a run**: measured
2026-09-15T12:17Z, when a bench container on this estate was recreated with a
new hostname and its `~/.local/bin` went with it. A container's `hostname` names
that container for as long as it exists and names nothing afterwards.

**`ENDED` and `RETIRED` carry none of them.** Amendment 11(c) keeps those two
payload-free — edit 1 of six, `R-A11-15` — and a verb that RELEASES a binding
has no binding to describe. (Amendment 18's Adoption list names them in passing;
the RULE, clause (a), names `STARTED`, `RESUMED` and `PAUSED`, and the rule
governs.)

**A line written before this amendment carries none of the three and stays
valid**: readers treat its binding as *the window on the row's workstation*,
which is what they read before. Nothing is backfilled.

**"None of the three" means all three, not `host` alone.** The writer drops an
offending sub-field on its own and keeps the line, so a line carrying a
`container` and an `os` and no `host` is a MODERN line that lost one field — and
reading it as pre-amendment would ignore the container it does carry. All three
absent is the only shape that is really from before this clause; anything less
is matched on host **and** container like every other modern line.

### What the launcher must export

`opensoft/workBenches#77` — `claude-profile` and the bench shells export
`LANES_HOST`, `LANES_OS` and `LANES_CONTAINER` into **every session and every
container they start**, beside the `LANES_WORKSTATION` they already export. The
per-host act is nothing more than that export; this toolset only ever READS
them, exactly as it reads `LANES_WORKSTATION`, and its fallbacks above are what
answer until the export arrives.

### The binding, and who may pronounce it dead

A lane's **binding** is the `host`, `container` and `window` of its last
lane-kind line that is `STARTED` or `RESUMED` **with no `PAUSED`, `ENDED` or
`RETIRED` after it**. A lane whose last lane-kind line is one of those three, or
which has none, is **FREE**.

```sh
lanes-edit.sh binding <lane>
# <host> <container> <window> <utc> <session> <os> <here|elsewhere> <live|gone|unknown>
# 0 bound · 8 free · 1 the log could not be read · 64 usage
```

**Liveness is pronounced only from INSIDE the binding's own host and container**,
where the pid namespace is the record's. From anywhere else a binding is
**UNKNOWN, never dead**, whatever `kill -0` says — that is the seventh column.

A **modern** record is matched on the machine's own hostname AND the container;
the Rule 10 workstation name is accepted as the host only for a **pre-amendment**
line, which has nothing else to be matched on. Clause (a)'s own fallback still
works through that without a second rule: a writer inside a container with no
`$LANES_HOST` writes the workstation name into `host`, and a reader in that same
container computes the same name the same way.

That column is also what the pick reads. `lane_groups` asks it **before** the
state, so a row that reads `LIVE` because a live session record here names one
of its ids — the records are shared between containers, and the pid that record
names is in another namespace — is still filed **BOUND ELSEWHERE** when its
binding is another place's. The act there is clause (c)'s request; and because
watching a lane and taking it are two acts of which only the second is the
collision, that branch also names the attach filled in wherever the window is
live on this tmux server. A **parked** lane of another container is untouched by
all of it: column 13 carries the locality of a binding that STANDS, and parking
IS the handoff.

**The one exception is the window**, and it is the eighth column. One host's
launcher mounts ONE tmux socket into every container it starts, so where the
asker and the binding share a tmux server and the binding's window **no longer
exists there**, the binding is **DEAD** — the pane a session must live in is
gone. The window is matched by Amendment 11(h)'s agreement rule, the `<@id>`
TOGETHER with its `<session>`, because tmux reuses ids once a window is gone.
Amendment 6(d)'s retire act and openRepoTools#30's takeover path apply to that
case as they stand. A window on another **host** is `unknown` and never `gone`:
an id from another machine resolving here would be a coincidence.

**And so is a window this place cannot ASK about** — no tmux binary, no server
running, a socket this user cannot read, a `$TMUX_TMPDIR` that differs. `tmux`
answers an id that resolves nowhere and a server that is not there with the SAME
empty line, and only one of the two is a dead pane; so the server is asked a
question that does not mention the id, and a server that does not answer leaves
the binding `unknown`. The alternative is a container the host's socket was
never mounted into pronouncing every other container's lane DEAD, which is this
clause's own collision arriving through its own exception.

### The second place asks

`lane-start <repo> <n>` and `lane <name>` run from a place that is not the
binding — a different `host`, `container` or `window` — **REFUSE to bind**.
Where stdin is a terminal they first ask, naming the binding:

```text
lane openRepoTools-3 is bound to window cloudsess:4 @62 in container cloud-bench
on host eagle (session d1ac715c-…, last line 2026-09-15T12:39:07Z); this tmux
server says that window is live.
ask it to hand off, then bind here? [y/N]
```

A `y`, or the flag **`--request-handoff`** from a caller with no terminal (an
agent's stdin is not one, and the refusal names the flag), is **the request**:

```sh
lanes-edit.sh request-handoff <lane> [--wait <s>] [--session <uuid>] [--no-wait]
lanes-edit.sh request-handoff <lane> --force "<why>"
# 0 the lane is free — bind it · 2 the wait ended empty, or refused
# 8 the lane was already free · 1 a read failed · 64 usage
```

In the clause's own order, and the order is load-bearing:

1. **The line is written and PUSHED first**, so the bound session can read it
   from anywhere:
   `HANDOFF-REQUESTED — lane <l>, session <requester uuid>@<ws>, <UTC>, lane:<l> → by host <h>; container <c>; window <w>; wait <n>s`.
   `HANDOFF-REQUESTED` is a lane-kind verb that **changes no state**: every
   last-line reader skips it, and `lane-last` after a request still answers
   `STARTED`.
2. **Then, and only where the bound pane is on THIS tmux server**, the requester
   types `/handoff --exit requested by <uuid>@<host>/<container>` into it —
   Amendment 12's M1, the one mechanism a running session has, and only while
   that pane's current command is `claude`. It is an optimisation of the
   same-host case and never the request: a session that never reads it answers
   at its hook's next read of the pushed line.
3. **Then it waits** — `--wait <s>`, default **300** — polling the published log
   every fifteen seconds (`$LANES_POLL_SECONDS` is the test seam) for a
   `PAUSED`, `ENDED` or `RETIRED` newer than the request. When one arrives the
   lane is free and the requester binds as it would have.

The **session field is the requester's own transcript uuid** and Amendment 7(b)
admits nothing else there. Where none is knowable — a bare shell with no
`$CLAUDE_CODE_SESSION_ID` and no live record for its window — the request is
**refused** and names `--session <uuid>`, rather than writing the literal
`unknown` into a log no later line can correct.

### The bound session answers at its own prompt

The prompt guard (Amendment 12) makes two more reads of the lane's own log:

- **(d)** a `HANDOFF-REQUESTED` newer than this session's binding and not yet
  answered → it **refuses that one prompt**, names who asked and from where, and
  types `/handoff --exit requested by …` into its own pane. The handoff is
  Amendment 17(a)'s, unchanged in its steps, and under `--exit` the session
  **ENDS** — a handoff to another place is a handoff and not a restart. Nothing
  the person typed is lost: the refused prompt is theirs to type again in the
  new place.
- **(e)** a `PAUSED` newer than the binding that **this session did not write**
  → it refuses **every prompt from then on**, naming the line and who forced it,
  until the person there hands off or ends the session.

**A working session is never interrupted** (clause (f)): no `Escape`, no signal
to the process, no `respawn-pane` from a requester. A hook fires at a prompt
boundary; a session inside a long turn answers when that turn ends.

### The wait ends with nothing — refuse, and only a word forces

A wait that ends with no release is a **refusal, exit 2**, printing the facts a
person needs: the binding (host, container, window, the line and its UTC), the
request and its UTC, whether the pane was reachable and typed into, and the one
word that overrides.

**`--force` is a second invocation, never automatic**, and it takes a WHY. It
writes

```text
PAUSED — lane <l>, session <requester uuid>@<ws>, <UTC>, lane:<l> → on behalf of <bound uuid>; forced by <uuid>@<host>/<container>; why <why>; host …; os …; container …
```

— the **writer's own session in the session field**, so it is not impersonation
(the retired-lane release of 2026-09-13, openRepoTools#30, is the precedent) —
and then binds. The why is written as a NAMED sub-field, `why <text>`, which
clause (e) does not spell and which the log needs: every reader here matches a
sub-field by the word it OPENS with, so a why beginning `host is unreachable`
would be read as that line's `host`, refused by the writer's own check, and the
person would be told about a field they did not write. The line's own three
separators — `, `, `; `, ` — ` — are folded to a middle dot inside it rather
than refused, because the person typed a sentence and not a grammar. The bound session, if it is alive after all, reads that line at
its next prompt and stops, loudly. **Two places never both write a lane in
silence.**

### A live lane's one act is the attach

A lane that is LIVE is never started a second time — clause (h) is one live
process per transcript, and a `lane-start` or a `pclaude` on a running lane is
exactly the second one. So `lanes` prints the act for it, filled in:

```text
openRepoTools-3            LIVE     Eagle      team-05c     bindsess:0 @61
                           attach: tmux switch-client -t bindsess:@61   (it is LIVE — never a second lane-start on a running lane)
```

`tmux switch-client` inside tmux, `tmux attach` outside it. The target names the
session **and** the window, because `attach -t <session>` alone lands on
whatever that session has since made current — another lane. The choice between
the two is made in the READ (`lanes_rows`, column 10), so `lanes` and `lane`
cannot come to offer different acts for one row.

### What `workstation` prints now

```sh
lanes-edit.sh workstation
# <workstation> <source> <host> <source> <os> <source> <container> <source>
```

Eight tab-separated fields; the first two are unchanged, which is the contract
`lanes`, `lane` and `lane-handoff` already read with `cut -f1`/`cut -f2`. Each
source is `seam` (the launcher exported it), `hostname` (probed), `workstation`
(a container with no export, writing the Rule 10 name for its host), `kernel`
(the `uname` / `/proc/version` probe) or `outside` (no container) — **and, for
the WORKSTATION field alone, `container-unset`**, which is Rule 10's own answer
where this IS a container and nothing exported `$LANES_WORKSTATION`: the NAME
still answers there, because a read in front of every launch may not refuse,
while every WRITER refuses on it by name. It predates this clause and the reads
table above has carried it all along; a reader holding this paragraph to five
words would reject a valid eight-field line from exactly the containers this
amendment is about.

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

### Fail closed for lane sessions, and safe-mode recovery

A mismatch refuses, and so does an **indeterminate read** — session records
unreadable, tmux not answering, the register unreadable, a payload naming no
`cwd` — naming the read, because a triple that cannot be verified is not a
triple that agrees (clause (d)). The row is read from `origin/<branch>` as this
checkout last had it (R19) and **the guard never fetches**: this hook runs at
every prompt, and putting the network there would be R-A8-1's objection several
times over.

Profile-only launches with exact `CLAUDE_NO_LANE=1` are exempt, as described
under Scope below. For a session subject to the guard, `claude --safe-mode` runs
with every hook disabled — deliberate, visible in the
prompt box, and **a session started that way is not a lane session**: it may not
write the register or claim an object. The hook's `timeout 5` is the other way
it can fail open, and it is the amendment's own number: a hook that exceeds its
timeout is killed, and a killed hook does not exit 2.

### Scope

Sessions launched with `CLAUDE_NO_LANE=1` skip the prompt guard, silently. The
workBenches profile launcher supplies this marker for a launch without a lane
and clears it for an explicit lane launch. Explicit `--no-lane` wins over lane
options. Other marker values keep the normal checks. The hook stays installed
in profile settings so a concurrent lane session using the same profile still
receives enforcement. Existing sessions need a relaunch to change launch mode.

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
lanes-edit.sh history --all [--since <UTC>]          # every lane, on one timeline (Amendment 14)
lanes-edit.sh history --repo <owner/repo>           # the lanes whose home it is
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
place**: `tmux respawn-pane -k` on the lane's own pane, and what comes up is a
NEW session of the same agent whose **first prompt is the handoff's top block**.
What tmux starts is not that session but a SUPERVISOR that launches it — the two
subsections below are why, and they are `openRepoTools#94` — so the sentence
holds end to end and no longer holds only as far as tmux accepting a command.
That block's
`WRITERS` section lists every worktree the lane had running: its branch, its last
commit, what it was holding, and the brief it was given, so the new session finds
them rather than discovering them — and its first line is Addendum 1 (i)'s, the
COUNT. **`/ctx` says which it did** (j): this one respawns, so the record says
`kind respawn` and the count then finds none, which is what makes relaunching
each one right. A `/ctx` that clears IN PLACE is the other kind and must say so
(`--in-process`, `kind in-process`): the process survives, its writers survive
with it, and the block says to EXPECT every writer below live.

**The record comes first, always, and the record is FOUR writes** (it was three
until `openRepoTools#94`). A `/ctx` **refuses before it kills anything** where the
`PAUSED` line did not land, where the row was not flipped (the register would say
RUNNING about a session that has just been replaced), where the handoff could not
be refreshed (its top block is literally the new session's first prompt, and a
stale one hands over the instructions of another act), **or where the restart
intent could not be written and read back**. A pane is never respawned over an
unrecorded lane, and a pane respawned with no intent is a pane whose supervisor
has nothing to launch from — the same unrecorded restart one step along.

#### The restart intent — what makes the new session a FRESH one

`opensoft/openRepoTools#94`, measured on Eagle at 2026-09-15T20:59Z: `/ctx` wrote
its record, respawned its own pane with `LANE_START_FRESH=1 … lane <lane>`, and
what came up was `claude --name <lane> --resume <the uuid it had just paused>` —
the same conversation, not a fresh one. `lane-start` was right (both of its
`(( ! fresh ))` gates were in the installed copy), `lane` was right (its available
branch ends in a plain `exec`), and the variable simply never arrived. The
launcher re-creates its child through tmux, and **a command tmux starts gets the
tmux SERVER's environment, not the caller's** — `claude-profile`'s own code says
so, which is why it writes six values into the command string explicitly. The
seventh was never written, so it was never there.

An environment cannot cross a boundary another repository owns. **A file can.**
Before anything is killed, `/ctx` writes a RESTART INTENT under the lane's own
legacy control root, independently of lifecycle snapshots,
using an explicit `$LANES_LANE_STATE_ROOT` when configured. Otherwise, an existing
intent under the recorded checkout's parent or `$PROJECTS_ROOT/.lane-state/<lane>`
retains its location through reservation, preservation, cleanup and later reads.
Distinct occupied intent locations or unreadable candidate ancestry refuse.
Aliases of the same control-root directory count once; separate leaf symlink
or hardlink entries refuse. With no existing intent, the recorded-parent rung precedes
the projects-root fallback, with a checkout hint only when neither answers.
Root selection shares the writer mutex with CAS. Recording a nested checkout
cannot move this operation; PR #97 diagnostics retain their independent root
selection and may reside elsewhere:

```
$ lanes-edit.sh restart-intent openRepoTools-3
state            pending
generation       7
operation        ctx-20260915T210412Z-41233-1187
mode             fresh-from-handoff
agent            claude
profile          max-001
dir              /…/openRepoTools
pane             claude-…:@6.%6
handoff          /…/handoffs/openRepoTools/…md
digest           9f2c…
old_transcript   4135b2c9-…
new_transcript   none
attempt          0
```

It carries no credential and there is no field for one. `lane-start` reads it back
and **the intent is the authority**: with a `pending` or `starting` intent whose
mode is `fresh-from-handoff`, the launch is a new session named for the lane and
primed by the handoff's top block, whatever the row's last uuid or the lane's last
`PAUSED` record name and whether or not any environment variable survived. A
`ready` intent is history and authorises nothing, which is what makes the next
`lane <name>` an ordinary resume. `LANE_START_FRESH=1` still works and is no longer
the authority; `lane-start --fresh` is the same thing as an argument, for a caller
with no launcher between it and there.

Two refusals rather than substitutions: an intent naming another checkout, or an
`--operation` that is not the lane's current one, is a refusal that renames
nothing and starts nothing — and a handoff whose **digest** has changed since the
intent was written blocks the launch, because that file's top block IS the first
prompt.

#### Legacy compatibility and preparation recovery

Supervised manual `/ctx` is a legacy compatibility path for Claude. Readiness
uses trusted Claude-native interactive session records for agent provenance.
Before replacing the old pane, the backend verifies the complete pending launch,
an existing absolute checkout and the canonical handoff checksum. Equivalent
handoff symlink paths retain their filesystem identity. Intent records reject
unknown keys, malformed lines and control characters in launch facts; those facts
are never flattened into different paths. Lane rename refuses unfinished or
failed restart ownership under the shared writer mutex. Observer cleanup uses
private cancellation and owned-child waiting, never a saved numeric PID signal.

Supervised manual `/ctx` is a legacy compatibility path. Run
`lanes-edit.sh legacy-restart-check <lane>` before any preservation writes;
managed lanes and unreadable managed ownership refuse. The check uses feature
001's installed read-only `legacy-check`, or conservatively refuses any matching
managed storage when that reader is absent. It never edits JSON ownership.

The backend reserves `preparing` before changing a handoff, register, log or
window. A normal error or catchable signal changes only that exact reservation
to `failed`; it never respawns the old pane. If an uncatchable termination leaves
`preparing`, first verify the original pane/session is still alive and no
replacement was launched. Read operation, generation and attempt with
`lanes-edit.sh restart-intent <lane>`, then reconcile that exact reservation:

```sh
lanes-edit.sh set-restart-intent <lane> failed --expect preparing \
  --expect-operation <operation> --expect-generation <generation> \
  --expect-attempt <attempt> --reason 'preparation abandoned; old pane confirmed alive'
```

A new `/ctx` can then refresh the preservation record. This command authorizes
no child launch from a partially prepared record.

If preparation failed before `pending`, the failed intent keeps mode
`preservation-only`, attempt 0 and no new transcript. It is not a failed launch
and cannot be given to `--supervise`. Once every holder is confirmed absent,
`lane <name>` may use ordinary resume without restart operation/attempt tokens or fresh-session selectors.
It rechecks the same failed preparation before binding changes and before
launch, leaves the intent unchanged, and retains the normal binding safeguards.
A live or unknown holder still refuses. Failed `fresh-from-handoff` launches
remain restricted to their same-operation supervisor.

The first launch reserves `new_transcript` only while it is `none`. Every later
write expects its exact operation, generation, attempt and transcript. The
verified Rule 3 stamp is persisted with both `digest` and `prepared_digest`
before `lanes-edit.sh publish-handoff` checks the expected digest and exact
attempt under the workspace writer mutex, then atomically replaces the resolved
handoff target. Both backend refresh and resume stamps use this publisher; manual
semantic edits are staged in temporary files and use the same command. Interruption leaves
either complete version valid for retry; unrelated changed prose refuses.
Historical `ready` intents do not control an ordinary resume.

#### The supervisor — what tmux actually starts

The pane is respawned with `lane-handoff --supervise --lane <lane> --operation
<id>`, **by absolute path**, because a respawned pane's `PATH` is whatever the
person's shell profile makes of it. It is a MODE of a command that is already
installed and not a thirteenth word: Amendment 18 Addendum 2 (i-8) is explicit
that *"no word is kept on `PATH` for it alone"*, which is the ground on which
`restart` was taken off `PATH` in the first place.

The legacy supervisor requires both the recorded pane and current TMUX_PANE to
be known and agree before claiming an attempt. A respawn forwards the configured
control/protocol roots and the launcher's LANES_HOST, LANES_OS and
LANES_CONTAINER identity alongside LANES_WORKSTATION. An existing unusable
control-root directory or ancestor is a read failure; only genuinely absent
storage permits an ordinary first launch. Readiness checks the child process
state and refuses an exited child awaiting reap.

What the supervisor does, in order:

1. **claims** the intent — `pending`/`failed` → `starting`, compare-and-swap on
   the operation, legacy generation and attempt, so a stale supervisor writes nothing;
2. refuses before launching anything on a stale operation, a `starting` or
   `ready` one, a pane the intent does not name, a changed handoff digest, or a
   live holder of the lane (Amendment 18(h): a second session of one lane is the
   collision the whole protocol is about — and the act it prints is
   `lane-end <lane> --retire <pid>`, never a kill);
3. **runs the launch as its CHILD** — `pclaude --lane <lane> <profile>`, which is
   (i-8)'s second door, falling to `lane-start --fresh --operation <id>` where
   there is no launcher or the record names no profile. Never `lane <name>`: that
   is the human dispatcher, and attaching to a live session is one of its valid
   outcomes;
4. **confirms readiness** from a read-only predicate — the child alive, exactly
   one live holder of this lane, its transcript the new one and not the paused
   one, in the pane the intent names — and only then marks the legacy intent `ready`.
   It never uses PR #97 diagnostic lifecycle state to decide restart readiness or writes managed JSON state. Ordinary STARTED/RESUMED events may update diagnostics independently. Tmux accepting a command is **not** a started session, and nothing
   here treats it as one;
5. **stays in the pane**, whatever happens. Amendment 11's own invariant is *"No
   path the launcher opened exits the pane"*, and `/ctx` was the one path that
   did: what tmux used to start was the launch itself, so a launch that failed
   took the pane with it.

#### The retry surface

A launch that never reaches readiness leaves the intent `failed` with a bounded
reason, and the supervisor prints the stage, the fact that the handoff is intact,
and two lines — retry and read:

```
RESTART FAILED — lane openRepoTools-3, operation ctx-20260915T210412Z-41233-1187
  the launch ended with status 127 before readiness was confirmed

  retry:   lane-handoff --supervise --lane openRepoTools-3 --operation ctx-…
  read it: lane-handoff --restart-status --lane openRepoTools-3
```

Where there is a terminal it then asks once — `[r = retry, q = leave it]` — and a
retry is **the same operation**: the same generation, digest, directory, profile
and launch mode, with the attempt count incremented. Where there is no terminal
it exits 3 — or **4**, where the launch ran past the readiness deadline still
alive and only then ended, which the record says as well.

**A signal reconciles only a successfully claimed attempt.** Before claim,
`SIGTERM`/`SIGHUP` leaves the intent unchanged. After claim, a live or unknown
child leaves `starting` with `INDETERMINATE` and blocks retry; a proven ended
child may leave `failed`. Neither handler kills the child. Failure after the
launcher exits also requires an affirmative empty all-holder read before retry
is offered, because a descendant may still own the lane.

Ctrl-C in that pane belongs to the **session**, not to the supervisor: the
supervisor ignores `SIGINT` so that interrupting Claude cannot tear the pane down
under it, and the launch is started with `INT` and `QUIT` put back to their
defaults so the keystroke reaches the session itself. A deadline that expires with the child still ALIVE is a
third answer, `INDETERMINATE`: nothing is killed (Amendment 8(f) — ending
somebody's process is not a boundary script's act), nothing is retried, the lane
is not marked running, and the reason goes into the record, because an interactive
child owns the pane's screen.

`lane-handoff --restart-status --lane <lane>` reads all of it from any window —
the lane, the intent and its attempt, the operation and generation, the mode, the
agent and profile, the checkout, the pane, the handoff and its digest, both
transcripts, the bounded failure reason, and what act is open on it.

**A second `/ctx` never supersedes a restart in flight.** With the intent
`preparing`, `pending` or `starting`, an ordinary `/ctx` refuses before preservation writes and the kill and names
the status command. Taking over an abandoned operation is an explicit act and not
an automatic one.

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
lclaude <profile>      # and only then; use pclaude --lane <lane> if lclaude is unavailable
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

## A closed or dormant lane leaves the listing (Amendment 19)

**In force — ratified by Brett Heap 2026-09-14T13:46:16Z, verbatim *"ratify
19"*** (`brettheap/new-workstation#36`, text `#37`). It amends what `lanes`
lists (11(j), 18(i)), gives Amendment 6(d)'s retire act a **sweep** for rows
that predate the object log, and uses Amendment 13's `RETIRED` as a row's
current state.

It exists because of a measurement. On 2026-09-14 `lanes` inside the
openxFactory checkout listed **nineteen rows for five lanes**: the five live
under `team-01b`, and **fourteen marked `NO LOG`** — lanes that ran between
2026-08-27 and 2026-09-02, before Amendment 7 gave every lane a log, and that
were never ended under any rule that could end them. Their rows carry their own
last words (`ended`, `dormant`, `CLOSED 2026-09-04`, one `LIVE` that is not, and
five saying `ENDED WITHOUT PUSHING — loss risk`, `work unpushed` or `owes …`),
and **no writer today can close them**: `lane-end` wants a live session or a log
to write into, and they have neither.

### The two states below PARKED

| state | what it is | how it is read |
|---|---|---|
| **CLOSED** | the lane's own log has finished | the **last lane-kind line** of `lanes/log/<lane>.md` is `ENDED` or `RETIRED` |
| **DORMANT** | a row with **no object log** and no live session on this workstation | no lane-kind line anywhere in the logs for that name, and no live session record naming any of the row's transcript ids |

Neither is **bound** (18(b)) and neither is **available to bind** (18(i)): a
closed lane's name is finished, and a dormant row's is not known to be. Both
already left the numbered pick; this is what takes them out of the read.

**One row with no log is NOT dormant:** one whose state cell is Amendment
13(a)'s phrase and whose state word is something other than `ENDED`, `RETIRED`
or the migration's `MIGRATED`. The row says the lane is somewhere — `PAUSED`,
`LANDING #<n>`, `HANDED OFF` — and hiding it would hide a lane a person can
still pick up.

### The listing

```console
$ lanes                      # CLOSED and DORMANT rows are not here
$ lanes --closed             # …and now they are, each with a second line
$ lanes --closed --all       # every repository's
$ lanes --closed --here      # this workstation's
```

A CLOSED lane is shown with the closing line's **verb** (the `STATE` column) and
its **time** (the `AGE` column). A DORMANT row is shown as `NO LOG` with its
**start date** and its **state cell's head** — the row's own last words, which
are the only thing it has left to say — and with **FLAGS** where that cell says
the work was `unpushed`, `lost`, a `loss` or `owed`, or still says `LIVE`.

**An empty listing is not an empty register.** A repository whose every row is
closed or dormant lists nothing, so `lanes --prefix <repo>` says that in those
terms — *"no lane of `<repo>` is LISTED — and that is not the same as none being
recorded"* — points at `--closed`, and offers the position it read from the
register and the archive rather than assuming 1. And a closed or dormant row
never reaches the numbered pick even when it is asked for by name: `lane
<name>`'s read is deliberately unfiltered, so `lane-groups` drops it on its
CLASS rather than on its state word.

**The next free position is computed over EVERY row** — hidden rows and the
archive of the next section included — so a retired `<repo>-<n>` is **never
reissued**. A lane's identity is its name, its log is `lanes/log/<lane>.md` and
that file is append-only: a second lane at a retired position would write its
life into the first one's file, and every read of that log would answer for two
lanes at once. Positions are cheap; identities are not.

### The sweep — one act, on a word

```console
$ lane-end --retire-dormant openxFactory                      # DRY RUN
$ LANES_LANE=<your lane> lane-end --retire-dormant openxFactory \
      --reason "pre-Amendment-7 rows; no log, no session" --yes
```

Without `--yes` it **writes nothing** and prints every dormant row of that
repository with its start, its workstation and the head of its state cell,
flagging the ones above — *so the person sees what the sweep will close before
it closes it; an agent's stdin is not a terminal, so the word is `--yes` typed
by a person.*

With `--yes` it is **ONE commit** (`lanes-edit.sh retire-rows`, the lock held
once). Per dormant row:

* `lanes/log/<lane>.md` is created with a single line —
  `RETIRED — lane <lane>, session <the sweeping session's uuid>@<ws>, <UTC>,
  lane:<lane> → retired-dormant by lane <writer>; reason <why>; was: <the state
  cell's head, verbatim, capped at 240>`. The session field is the **writer's**
  transcript uuid (7(b)), and the row's own last words are carried into the log
  so that nothing the row said is lost when the row stops saying it;
* the row's state cell becomes `RETIRED · <UTC> · <why>; was: <head>`. Clause
  (c) writes that cell as `RETIRED <UTC> · <why> · was: <head>`, which is four
  parts where 13(a)'s cell has three and whose first word would be a state no
  reader knows; the phrase above carries the same four facts under the grammar
  every other writer obeys, and goes through the same `row_state_check` — so the
  240-character cap, the `|` and the second ` · ` are refused here exactly as
  they are for `set-row-state`. A `|` a legacy cell carries becomes `/` in the
  row (it would forge a cell boundary) and stays **verbatim** in the log line,
  which is not a table.

It **refuses**: a lane a live session holds on this workstation; a row whose log
already carries a lane-kind line other than `ENDED`/`RETIRED` (**a parked lane
is not dormant**); and a repository with no dormant row — *nothing to do is
said, not done* (exit **8**). Any one of them refuses the **whole run**, before
a byte is written, because it is one commit and therefore one decision. It also
refuses a session-record read that failed: *"a read that failed is not 'nothing
is live'"*.

It refuses six more things for the reason every writer here refuses them — a
half-written act is worse than no act: a checkout **behind** `origin` or dirty
in anything but the register; a row whose ` | ` count makes **which text is the
state cell** unknowable; a lane whose object log would need Amendment 15's
**case-only rename**, which is a write of its own and not one this commit
smuggles; an object log that exists here and is **NOT TRACKED**, which is
somebody's uncommitted work and would land inside this commit under this act's
message; a lane **named twice**, whose log would take the same line twice in a
file nothing can correct; and a `--reason` carrying a `|`, a second ` · ` or a
newline, which is refused as the **argument** it is (capped at 180 characters,
because the row's own last words go in beside it).

It touches **no file outside the register and the logs**. A retired row records
that a lane is finished; worktrees, branches and handoffs stay exactly where
they are.

**Nothing is half-PUBLISHED, because the commit is the only thing that
publishes.** Every refusal above is made in the scan, before a byte is written.
A failure in the writes themselves — a log whose append could not be proved, a
row whose rewrite touched more than one line — leaves this checkout DIRTY and
the register unpublished: that is what `git status` then shows, `git checkout --
lanes` undoes it whole, and the next run is REFUSED by the dirty-checkout guard
rather than made twice. `migrate-state-cells` has the same shape for the same
reason.

### The archive — a second act on a second word

```console
$ lanes-edit.sh archive-rows openxFactory                     # DRY RUN
$ lanes-edit.sh archive-rows openxFactory --yes               # ONE commit
```

It moves every **`RETIRED`** row of that repository out of `lanes/LANES.md` and
into **`lanes/archive/LANES-retired.md`**, in one commit whose message names
each lane moved. The archive is written **first** and the rows removed second,
so a refusal between the two leaves a copy in the archive and the register
whole, never a row in neither file.

Nothing reads a row differently for having moved: the listing reads the archive
beside the register (so `lanes --closed` still shows those rows) and so does
every reader of the next free position — and a published archive that cannot be
*rendered* is a REFUSAL that says so, never a fallback to this checkout's copy,
which may lack a retired position the published one holds: read as absent, or
from that copy, it would put a retired position back on offer. `add-row` refuses a lane
name the archive holds, so `lane-start <repo> <n>` cannot reissue one by hand
either. **Rule 9 holds either way** — a row is
one `git show` away — so the archive is for a register a person wants shorter,
and never a requirement.

## Crash-consistent lane recovery (openRepoTools#91)

**A lane is `RUNNING`, `SWAPPING`, `SWAPPED` or `CLOSED`, and which of those it
is WITH NO LIVE HOLDER is what says where its session stopped.** A session can
run out of tokens before the handoff, after the handoff began and before it
finished, or after it finished — and until this capability all three left the
same evidence: a last lane-kind line that is a `STARTED`/`RESUMED` (which is
also what a running lane looks like) or a `PAUSED` (which is also what a clean
swap looks like). The two crash kinds had no word.

Governed by `openspec/changes/add-crash-consistent-lane-worktree-recovery/` and
tracked on [opensoft/openRepoTools#91](https://github.com/opensoft/openRepoTools/issues/91).
It amends no protocol: **it adds no lane-kind verb to the append-only log**.
Amendment 7's five state verbs, `STARTED`, `PAUSED`, `RESUMED`, `ENDED` and
`RETIRED`, stand, and every reader of them — `swapped`, `lane-last`,
`lane-dir`, `who`, `lane-end` — is untouched. (Amendment 18(g) has since added a
sixth lane-kind verb, `HANDOFF-REQUESTED`, which changes no state; this change
adds none.) What is new is a SNAPSHOT beside that history.

### The four words, and the two crashes

```text
RUNNING --/handoff begins--> SWAPPING --record + row + handoff all landed--> SWAPPED
   ^                                                                          |
   +---------------- the act that confirms the next binding --------------—---+
```

| the snapshot says | a live holder? | what it means |
|---|---|---|
| `RUNNING` | yes | the lane is running — do not launch a second coordinator or a second writer |
| `RUNNING` | **no** | **ungraceful stop**: the session died before any handoff began, so nothing was polled, refreshed or recorded |
| `SWAPPING` | yes | a handoff is in flight — do not compete with it |
| `SWAPPING` | **no** | **interrupted swap**: the handoff began and did not finish, so the record, the row and the handoff file may each be half done |
| `SWAPPED` | no | the swap completed; the lane is resumable once its trees are read |
| `SWAPPED` | yes | inconsistent — a swapped lane has no holder, and neither side is overwritten |
| `CLOSED` | — | the lane is finished; a dirty or unpushed tree under it is a closure inconsistency and no cleanup is made |
| any | **unreadable** | `indeterminate`. A holder that could not be established is NOT "no holder" (`R22`, Amendment 7(d)), and no crash is pronounced on a read nobody got. |
| **unreadable** | — | `indeterminate` again, and for the same rule read one file earlier: a snapshot that IS THERE and cannot be opened is not a lane that has none. `lane-state` exits **10** for it, never the **8** that means *this lane has no snapshot, go on*. |
| any | — and the lane is **bound elsewhere** | `indeterminate`. Amendment 18(b): liveness is pronounced only from inside the binding's own host and container, and from anywhere else a binding is UNKNOWN, never dead — and this workstation's snapshot is this workstation's alone. The one exception is clause (b)'s own: a binding whose window is gone from this host's tmux is dead, and the local read decides. |
| — | — and the lane is **managed-owned** | `managed-owned`, and nothing else is read or pronounced: see *Managed-owned lanes* below. |

### The fence

Every transition carries a monotonic **generation** and a unique **operation
id**, and `set-lane-state --expect …` is the compare-and-swap:

```sh
lanes-edit.sh lane-state <lane>                     # state, generation, operation, owner, updated
lanes-edit.sh set-lane-state <lane> SWAPPING --expect RUNNING
lanes-edit.sh set-lane-state <lane> SWAPPED  --expect SWAPPING \
              --expect-generation <n> --expect-operation <id>
```

A finalizer whose state, generation or operation no longer matches writes
NOTHING and exits **7** — the number this file already spends on `claim`'s
CLAIM-LOST, and one meaning on it: *you lost the race*. That is what stops a
`/handoff` that stalled for an hour from marking a lane `SWAPPED` after somebody
has recovered and resumed it. A handoff that finds the lane still `SWAPPING`
**takes it over** with a new generation and names the operation that never
finished; nothing of that operation is undone.

`RUNNING` is written by the act that CONFIRMS the binding and never by the
SessionStart hook: `session-start` never writes, never touches the network and
always exits 0 (Amendment 8, `R-A8-1`), and a hook that writes is a hook that
can break the session it was meant to orient. So the snapshot follows the
`STARTED`/`RESUMED` line `lane-start` writes, in `lanes-edit.sh`'s own
`write_event`; `ENDED`/`RETIRED` become `CLOSED` there too.

### Where it lives

A LOCAL control root beside the lane's own checkouts — not the register (every
write of that is a commit, a pull and a push, and a transition happens three
times per handoff with no network), and not inside a git worktree (metadata
there dirties a checkout and disappears with the very directory whose loss it
explains). Three rungs, and never the caller's current directory:

1. `$LANES_LANE_STATE_ROOT/<lane>` — the explicit override and the suite's seam;
2. `<parent of the lane's recorded `dir`>/.lane-state/<lane>` — the same parent
   the lane's own `.lane-worktrees/<lane>` root sits in, and `dir` is Amendment
   11(c)'s recorded field rather than a guess;
3. `$PROJECTS_ROOT/.lane-state/<lane>`.

No rung answering is **8**, *this lane has no control root* — the ordinary
answer for a lane that has not started under Amendment 11(c), and not a failure.
Nothing is backfilled (Amendment 7(i)).

Because the snapshot is filed under NOTHING — never committed, never leaving the
machine that wrote it — `R-A11-14` does not reach it: a container with no
`$LANES_WORKSTATION` still keeps a lifecycle it can recover itself from, while
the register and object-log writes stop there exactly as they did.

### The worktree inventory

Every handoff polls the lane's writers in the two places a lane keeps them —
`<checkout>/.claude/worktrees/<name>` and
`<projects>/.lane-worktrees/<lane>/<name>` — and now records each one MACHINE
READABLY beside the lane as well as in the handoff's WRITERS section:

```sh
lanes-edit.sh lane-trees <lane>
# <id> <path> <branch> <head> <upstream> <dirty> <unpushed> <writer> <observed> <checkout> <generation> <operation> <schema>
lanes-edit.sh lane-tree-now <worktree path>
# <branch> <head> <upstream> <dirty> <unpushed>   — what git says about one tree NOW
```

Every lane's records on this workstation, one row per tree, are `lanes
--worktrees`; the derived index keeps them as its `worktrees` table, which no
act reads (*The derived index*, below).

The full `head` and the `upstream` are why this is not the prose section one
more time: `%h` is an abbreviation that lengthens as a repository grows, and
`0 unpushed` cannot be told from *this branch tracks nothing at all* without the
upstream. Every field is an OBSERVATION and none of them is truth about git.

**`lane-tree-now` is the one implementation of that observation**, and the
handoff, the sidecar and the reconciliation all go through it, so the WRITERS
section a person reads and the record a recovery reads can never be two
different readings. It does not convert a git read that FAILED into a
clean-looking value: `unknown`/`none`/`0` are answers, and a read that could not
be made exits **1** and prints nothing (`R22`, Amendment 7(d)). Two states are
answers rather than failures and are spelled as such — a branch with no commit
yet has `unborn` for its head, and a branch whose upstream is configured but
whose remote-tracking ref is not in this checkout (the ordinary state after a
merged branch is deleted) records that configured upstream with `unknown`
unpushed, never the `0` that reads as *everything here is published*.

**A sidecar this helper cannot read is one it will not replace.** A snapshot or
a tree record carrying a schema this version does not write is reported as
`UNKNOWN-SCHEMA` by every reader and REFUSED by every writer (exit 1), rather
than overwritten by a record an older helper can understand — the one act no
later reader can undo. And `set-lane-tree --generation/--operation` is COMPARED
with the lane's own snapshot under the mutex before the record is filed, so a
poll taken under an operation a recovery has since superseded is refused with
**7** instead of being filed over the current inventory.

**One path, one record.** A tree's record is named from its path and from
nothing else: `c<cksum>-<folded path>`, a `cksum` of the WHOLE absolute path
and then the path with every character outside the file-name alphabet folded to
`-`. The fold is for a person reading the directory; the checksum is what keeps
`…/a+b` and `…/a-b`, which fold alike, two records rather than one replacing the
other. And `set-lane-tree` takes a caller's observation **whole** — `--branch`,
`--head`, `--upstream`, `--dirty` and `--unpushed` together — or reads the tree
itself; a partial one is refused with **64** and nothing is written, because the
fields it lacks would be filed as a `dirty 0, unpushed 0` nobody observed.

### The reconciliation, which resets nothing

```sh
lanes-edit.sh lane-reconcile <lane>
```

It recomputes branch, HEAD, upstream, dirty and unpushed for every inventoried
tree, reads `git worktree list --porcelain` in the lane's checkout and the
directories under both lane roots, and prints one `TREE` line per tree with a
classification: `ok`, `dirty`, `unpushed`, `unpushed-unknown`,
`dirty+unpushed`, `dirty+unpushed-unknown`, `missing`, `possible-loss`,
`not-a-checkout`, `unreadable`, `unreadable-sidecar`, `unknown-schema`,
`unmanaged`, `stale-registration`. A `BINDING` line says where the lane is bound — `here`,
`free`, `gone` (bound on this host's tmux and its window is gone), `elsewhere`
(and where), or `unknown` (its log could not be read) — and `elsewhere` or
`unknown` turns every verdict into `indeterminate` (Amendment 18(b)). The last
line is the `VERDICT`. `lane-start` prints the report before it writes
anything, for any verdict that is not `running` or `closed` — and for
`resumable` as well whenever its `TREES` line counts a tree that is dirty or
unpushed, requires recovery, or is unmanaged or stale: `resumable` says the swap
completed, not that every tree it left is clean, published and where it was.

A **renamed** lane keeps its snapshot and inventory: `rename-lane` moves its
control root to the new name once the rename's commit has landed, and never
over something already there (Amendment 16). Its `.lane-worktrees/<old>` root
holds real git worktrees and is not moved — that is a `git worktree move`, and a
person's. A lane retired by Amendment 19's sweep is taken to `CLOSED` exactly as
a lane that ended itself is.

**It reads the published register first**, as every read in `lanes-edit.sh`
does: the lane's name resolves through the register and Amendment 16's alias
table, and its binding and any managed-owner marker are read from them, so a
stale ref would pronounce from a binding that has since moved. The fetch goes
into the register checkout and touches no lane tree; it is bounded by
`LANES_GIT_TIMEOUT` and, when it fails, the ref is read as it stands.
`LANES_NO_FETCH=1` skips it — which is how `lane-start` calls it, having fetched
in its step 3 — at the cost of reading what was last fetched. Whether a recovery
read should be local by default is opensoft/openRepoTools#157.

**It reports and it resets nothing.** `park` CREATES NOTHING and `resume` RESETS
NOTHING (`AGENTS.md` rule 1), so this read runs `git status`, `git log @{u}..`,
`git rev-parse` and `git worktree list --porcelain` and nothing else:

* a **missing** tree that was clean and published names the estate's own
  `resume <Name>` as the only rebuild — and NAMES it rather than running it,
  because that verb runs `make resume` across a whole estate and a report may
  not do that as a side effect;
* a missing tree whose last observation held dirty or unpushed work is
  **possible-loss** and is never claimed to be reconstructable — no metadata
  reconstructs a file's contents;
* an **unmanaged** tree — one git registers, or one sitting under a lane root,
  that no sidecar names — is reported and never deleted, adopted or overwritten:
  which lane a tree belongs to is a person's to say. One tree is named ONCE
  however many spellings of its path reach the report: a sidecar holds the path
  its poll was given, `git worktree list --porcelain` answers with the physical
  path, and the on-disk sweep walks the recorded `dir`, so every comparison
  resolves both sides — without which every tree of an estate that reaches its
  checkouts through a `projects` symlink is reported twice, the second time as a
  tree nobody manages;
* a **stale-registration** names the `git worktree prune` that clears it, and
  prunes nothing itself;
* an **unreadable** tree is one git answers in and cannot be read through —
  nothing is assumed about it, in either direction, and the line names the
  `git -C <path> status` a person runs;
* an **unreadable-sidecar** is a tree record that IS there and could not be
  read — a permission, an I/O error, a dangling link. The tree it recorded is
  NOT known, in any field; it counts toward recovery, the line names the file a
  person reads by hand, and it is never skipped as though the lane owned one
  tree fewer (`lane-trees` carries it as a row of its own whose schema is
  `<unreadable>`);
* an **unknown-schema** tree is a sidecar written by a newer tooling: it is
  named, and not one field of it is read, because a value taken out of a record
  whose shape this reader is guessing at is worse than no value.

### What a resumed session does with it

Read the verdict first, then the trees, then `ListAgents` — the count is still
what decides whether a writer is live (Amendment 17 Addendum 1 (i), and (k):
one worktree, one writer). `ungraceful-stop` and `interrupted-swap` both mean
**inspect every tree before relaunching anything**; the difference is that under
`interrupted-swap` the record, the row and the handoff file may each be half
written, so check all three rather than trusting the handoff's top block.

## Managed-owned lanes

**Brett Heap's ruling of 2026-10-04, verbatim: *"managed ledger owns enrolled lanes; #97 owns legacy — rework both"*.**
A lane the managed ledger has enrolled carries a **managed-owner marker** in its
register row's state cell, written by that ledger's own writer:

```text
LIVE · <UTC> · managed-owner mode=managed daemon=<id> generation=<n> bound-lane=<lane>
MANAGED OWNER · <token>        (the historical shorthand)
```

Every lane without one is a **legacy** lane — every lane in the register today —
and the lane tooling here answers for legacy lanes only. The marker is read by
one reader, ported byte for byte from branch `001-separate-swap-ctx-handoff`
(`3c26041:lanes-edit.sh:776-898`), and asked through one read:

```sh
lanes-edit.sh managed-projection <lane>
```

| exit | meaning | what every legacy act does |
|---|---|---|
| 0 | a valid marker; the owner is printed | **refuses with 2**, names the owner, writes nothing |
| 8 | no marker and no managed-owner vocabulary | runs exactly as it always has |
| 1 | managed-owner vocabulary that does not parse (a `generation=0`, an empty daemon, a `bound-lane` that is not this lane, an empty shorthand token, a `managed:` anywhere in the row), a row that is not seven columns, or a register that could not be read | **refuses with 1**: ownership is UNKNOWN, and an ownership nobody could establish is never read as legacy (Amendment 7(d)) |
| 64 | usage | — |

The acts that ask, each before its first write: `lane-start` (at the head of its
section 3, before Amendment 18's binding gate and `--request-handoff`),
`lane-handoff` (before the window is renamed — so `--late`, `--restart` and
`--exit` never reach `SWAPPING` or `SWAPPED`), `lane-end` (the ending,
`--retire` and `--retire <pid>`), the object log's `STARTED`, `RESUMED`, `ENDED`
and `RETIRED`, a swap's `PAUSED`, `request-handoff` (its `--dry-run` too),
`set-lane-state`, `set-lane-tree`, `retire-rows` (one managed or unknown lane
refuses the whole sweep), `migrate-state-cells` (one managed or unknown row it
would rewrite refuses the whole migration), `archive-rows` (one such RETIRED
row refuses the whole move), `append-session-id`, `add-row` for a lane that
already has a row, `set-row-state`, `replace-in-row` and `rename-lane`. Each
reads this checkout's row as well as the published one, because this
checkout's row is the one a legacy writer rewrites: vocabulary in one copy and
not the other is UNKNOWN (1). A claim or a release is about the object, not the
lane, and is not refused. `lane-reconcile` reads nothing of a managed lane and prints
`VERDICT managed-owned` (and `indeterminate` where ownership is unknown). And no
legacy writer — `set-row-state`, `add-row`, `replace-in-row`, `append-line`,
`append-session-id`, `rename-lane`'s new name, the sweep — may write the
marker's vocabulary into the register at all, so a marker is never forged.

What the managed ledger itself does with an enrolled lane is not this manual's:
branch `001-separate-swap-ctx-handoff`'s governance review is **PROPOSED — NOT
APPROVED**, and nothing here asserts that it supersedes Amendment 17.

## The derived index (Amendment 14)

**In force — ratified by Brett Heap 2026-10-05, verbatim *"ratify 48"***
(brettheap/new-workstation#48; the tooling is opensoft/openRepoTools#160).
**The register's truth stays where it is.** `lanes/LANES.md`, `lanes/log/`,
`lanes/aliases.tsv` and `lanes/archive/` are the record, written only by
`lanes-edit.sh`. `lanes-index` keeps a **derived index** of them — SQLite on
local disk, or QA Postgres where this workstation is configured for it —
written behind the sources, read only by tooling that decides nothing, and
never a gate. Where the index and the source disagree, the source is right and
the index is behind.

### What it is for, and what it never does

It is for the questions no act asks: every repository's rows at once, every
lane's history on one timeline, a dashboard, Eagle and Raven asking one store.
It is **never read by an act**: no `claim`, `release`, `log` verb or LANES
line; not the name guard or the `SessionStart` block; not `lane`, `lane-start`,
`lane-end`, `lane-handoff`, `lane-rename`, `/restart`, `/handoff`, `/ctx`; no
row writer, sweep, archive or migration; and none of the reads an act makes for
itself (`who`, `binding`, `live-holder`, `next-free`, `managed-projection`,
`lane-reconcile`). An index that is missing, stale, unreachable, wiped or wrong
changes no exit code and no output of any of them. It never writes back:
nothing in any source is ever written from it.

### The three words, and the one step `lanes-edit.sh` gained

```sh
lanes-index sync      [--source <s>]              # write behind what LANDED
lanes-index reconcile [--source <s>] [--dry-run]  # read the source whole; put the index right
lanes-index status                                 # per source: store, provenance, lag, last error
```

- **`sync`** reads the register as `origin/<branch>` of the workspace checkout
  stands — what the push left, never the working tree — and upserts every
  record whose content differs, keyed by **(source, record id)** and versioned
  by a **digest of its content**: an upsert bearing the stored digest changes
  nothing, so a replay or a crash is harmless. The source's indexed commit is
  compared and swapped **in the same transaction** as the rows it covers, and
  a sync from a commit that does not descend from it **writes nothing** — so
  two workstations syncing into one Postgres, even at once, cannot roll it
  back. A record its source no longer holds leaves in the same sync. One sync
  at a time per workstation: a second finds the lock held, leaves the holder a
  mark to sync again, and returns at once.
- **`reconcile`** reads the source whole, compares every stored row by what it
  **says** (not by the digest it carries, so a row changed by hand is found),
  upserts what differs and removes what is gone: on a wiped index, the
  rebuild. `--dry-run` prints the counts and writes nothing.
- **`status`** prints the store, each source's provenance against its tip, the
  lag in commits, and this workstation's last sync and last error.

**The nudge.** After every write whose push **landed**, and after its mutex is
released, `lanes-edit.sh` starts **one detached `lanes-index sync`**: stdin
closed, stdout and stderr on `/dev/null`, never waited, its status never read.
It carries no data. It is skipped where `lanes-index` is not on `PATH` (one
`command -v`, nothing printed) and wherever `LANES_INDEX=off`. A slow, failing
or absent indexer delays and fails no commit, push or swap.

### Reading it — `--index`, only when typed

```sh
lanes --index                       # any listing, out of the index
lanes-edit.sh history <lane> --index
lanes-edit.sh history --all  [--since <UTC>] [--index]      # every lane, one timeline
lanes-edit.sh history --repo <owner/repo> [--index]         # the lanes whose HOME it is
```

The flag is typed per invocation — **never** taken from the environment or a
configuration. It replaces the **published** reads (the register, the archive,
the alias table, the logs) and nothing else, so the live session records, tmux
and this checkout's own files are read as they are without it. Where the index
is current the answer is **byte for byte the source read's**, the clock's
columns aside (the listing's AGE and its "last heard from origin" age, computed
the same way at the moment of the read). One line on stderr says which was
read:

```text
read: index (sqlite) at register@1a2b3c4d5e6f; 0 commits behind
read: sources (index unreachable: psql: error: connection to server … failed)
```

Lag is said, never refused. Where the index cannot answer — `lanes-index` not
installed, the store `missing`, `unreachable`, `wiped` (no provenance for this
register), of an `unknown-schema`, a configuration it `refused`, or
`LANES_INDEX=off` — the line says so and the **sources** answer, with the
source read's own exit. `history --all` and `--repo` read the sources without
the flag; `history` over two lanes used to be refused.

### The store and its configuration

`${XDG_CONFIG_HOME:-~/.config}/openRepoTools/lanes-index.conf`, or the file
`$LANES_INDEX_CONFIG` names — per workstation, **never committed**, never under
`~/.agents/` (which on a workstation built from the workspace repository *is*
that repository):

```text
store=sqlite|postgres     default: postgres where url= is set, else sqlite
sqlite=<path>             default ${XDG_STATE_HOME:-~/.local/state}/openRepoTools/lanes-index.sqlite
url=<libpq URL>           the WRITER role — sync and reconcile
passfile=<path>           the 0600 libpq password file for it
reader_url=<libpq URL>    the SELECT-only READER role — status and the --index reads;
                          REQUIRED beside url=, or those reads are refused
reader_passfile=<path>    its password file, where it is not the same one
schema=<name>             the Postgres schema (default lanes_index)
```

Refused (exit 2, nothing read or written): a configuration that is group- or
world-readable, inside a git work tree or under `~/.agents/`; a URL that
carries a password in any spelling; a password file that is not 0600; a SQLite
path inside a git work tree. A Postgres configuration with no `reader_url=` is
refused for `status` and the read flags (`read: sources (index refused …)`):
**a read never connects with the writer's credential**, and there is no
fallback to it. Postgres is reached through `psql` and only where
`url=` is set — nothing imports a driver — with `PGPASSFILE` naming the
password file and an inherited `PGPASSWORD` or `PGPASSFILE` removed; with
no `passfile=` (a passwordless role), `PGPASSFILE` names an empty 0600 file of
the indexer's own, so libpq never falls back to `~/.pgpass`. No configuration at all
is SQLite at its default path, created 0600.

**The two roles are Postgres's to hold** (act 3, Brett Heap's on Eagle and
Raven — or nothing, and SQLite):

```sql
CREATE ROLE lanes_index_writer LOGIN;   -- the password lives in the 0600 passfile only
CREATE ROLE lanes_index_reader LOGIN;
CREATE SCHEMA lanes_index AUTHORIZATION lanes_index_writer;
GRANT USAGE ON SCHEMA lanes_index TO lanes_index_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE lanes_index_writer IN SCHEMA lanes_index
  GRANT SELECT ON TABLES TO lanes_index_reader;
```

The writer is confined to the index's schema and held by the indexer alone —
by no session, supervisor, launcher or ledger authority; a leaked writer can
damage only what a `reconcile` rebuilds. The reader may only `SELECT`.

### What is indexed (schema 1)

One versioned schema (`schema_version`); every row carries its `provenance`
(the register commit it was last written at), `indexed_utc` and
`schema_version`, and its `digest`.

| table | one row per | what it holds |
|---|---|---|
| `lanes` | lane | canonical name, `aliases` (Amendment 16(e)), `home`, the `workstation / env / user` cell, `started_utc`, `handoff_path` (a pointer), `state_phrase`, `objects_cell`, `session_ids` in order, `last_session` (the resume target), `archived`, the row's own text — and **`owner`**: `legacy`, `managed <owner>` or `unknown`, from `lanes-edit.sh managed-projection` (0, 8, 1) and never from a parser of the indexer's, so a malformed marker is never downgraded to `legacy` |
| `log_lines` | log line, by lane and file ordinal | verb, session, workstation, UTC as written, object, payload, its sub-fields as JSON, free text; a line the grammar cannot read is kept as `unreadable` with its file, line and reason, never dropped |
| `register_lines` | register line, by ordinal | Rule 6's `LANDING`/`LANDED` and Amendment 10's `HOLD`/`HOLD RELEASED`: lane, repository, PR, tip, UTC, the line itself |
| `lane_aliases` | alias-table line | `old_name`, `new_name`, UTC |
| `transcript_pointers` | pointer | a row's session-cell ids and each `transcript` a `PAUSED` names, with its `agent` — pointers only |
| `source_files` | file of the source | kind, blob, line counts — what the read flags need to answer as `origin` would |
| `holds` (a VIEW) | open hold | `holders_of`'s answer, which is `who`'s: per lane (case-insensitively), its last line on each object **in file order**, never by UTC, where its verb is open — and not while another lane's own last line there is a `TAKEOVER`. The object is keyed AS WRITTEN: a line naming a repository by a spelling `lanes/repos.tsv` has since renamed (R20) is its own key here, where `who` folds its argument into the canonical one. Computed, never stored |
| `provenance` | source | the indexed commit (or generation), UTC, schema version |

**Created empty and written by nothing here**: `swap_states` and
`job_summaries` — the managed ledger's half, `ledger:<Workstation>`, which the
001 feature's T058 writes (act 4). `worktrees` is the inventory's, below — the
same schema 1, whose table was created with #161's columns before a row was
written into it. Not indexed at all: transcript and handoff bodies,
credentials, the ledger's claims, fences, releases and exit witnesses.

### The `worktrees` table — every lane's #97 inventory (opensoft/openRepoTools#161)

**What it is for: the next account's first query.** A session that resumes a
lane — or that sits down at Raven after a day on Eagle — wants every open
worktree before it decides anything: whose it is, which branch, whether the
lane stopped `RUNNING` or `SWAPPED`, what was dirty or unpushed, when it was
last seen and whether a writer is still live. Each lane's handoff already
records that beside the lane (*The worktree inventory*, above); this table is
the same records in one place, under the source `inventory:<Workstation>` — one
per workstation, because the sidecars live on that workstation's disk and
nowhere else — so a store two workstations sync into answers for both.

```sh
lanes --worktrees [<lane> | --all]            # this workstation's sidecars
lanes --index --worktrees [<lane> | --all]    # the table: every workstation it holds
lanes-index sync      --source inventory      # what every inventory write nudges
lanes-index reconcile --source inventory [--dry-run]
```

| column | from |
|---|---|
| `workstation`, `lane` | the workstation's name (`lanes-edit.sh workstation`) and the lane's canonical one |
| `owner` | `legacy`, `managed <owner>` or `unknown` — the read `managed-projection` makes, never a parser of the indexer's |
| `path`, `branch`, `dirty_count`, `unpushed_count`, `last_seen_utc` | the tree's sidecar: the last observation, `detached <sha>` for a detached head, an `unknown` count as NULL. A sidecar that could not be read is `unreadable sidecar`, one of another schema `unknown schema <n>`, each with the record's id where its path would be |
| `base`, `last_commit` | two git reads of the RECORDED head, in the tree or, once it is gone, its recorded checkout: its merge-base with `origin/main` (else `main`, else `origin/HEAD`), and `<sha> <subject>` |
| `lifecycle`, `generation`, `operation` | the lane's snapshot (`lane-state`): `RUNNING`, `SWAPPING`, `SWAPPED` or `CLOSED` for a **legacy** lane; `INDETERMINATE` for a managed or unknown one, whose lifecycle this tooling does not pronounce on, and for a snapshot that is missing, unreadable or of another schema |
| `writer_live` | the listing's own LIVE — a session record on this workstation naming one of the row's ids — and NULL where those records could not be read or the lane is bound on another host, from where liveness is unknown and never dead (Amendment 18(b)) |
| `pr_number`, `pr_state` | `gh` at sync, best effort, the newest pull request whose head is the branch; NULL wherever it was not asked (`LANES_NO_GITHUB=1`) or did not answer. A MERGED or CLOSED answer is not asked again while the branch and its last commit stand |
| `provenance`, `indexed_utc` | the generation the TREE'S OWN record was filed under — behind `generation` exactly when the observation predates the lane's current transition — and the sync |

**Read through the helper, never around it.** The indexer reads `lanes-edit.sh
worktrees --all`, which lists each lane's sidecars through `lane-trees`' own
reader, its snapshot through `lane-state`'s and its owner through
`managed-projection`'s, and walks no directory for a tree no sidecar names —
that is `lane-reconcile`'s act. Nothing is recomputed: `dirty` and `unpushed`
are what the handoff saw, and `LAST SEEN` says when.

**Rows follow the inventory.** Keyed by (source, `<lane>:<path>`) and versioned
by a digest of the row and its provenance, so a replay writes nothing; a tree
the inventory no longer names — removed at landing, or by a sweep's disposition
— leaves in the same sync. The provenance moves only forward **per lane**: a
`sync` that reads a lane's lifecycle generation below the one its rows were
written at (a snapshot moved aside and begun again) writes nothing for that lane
and says so, and `reconcile --source inventory` is the act that takes the lane
as it now stands. A lane whose `trees` directory is there and cannot be listed
keeps its rows — it is not a lane with no worktrees. The source's own row
carries a fingerprint of the whole table as its compare-and-swap token and a
sync count that only goes up. A container with no `LANES_WORKSTATION` syncs
nothing (exit 2): a source named for a container's own id is one no restart
finds again.

**The nudge.** Every inventory write — `set-lane-state`, `set-lane-tree`, the
lifecycle follow after a `STARTED`, `RESUMED`, `ENDED` or `RETIRED`, and a
rename's move of the control root — starts the same detached `lanes-index sync`
a landed push does, as `sync --source inventory`, skipped where `lanes-index` is
not on `PATH` or `LANES_INDEX=off`. One sync at a time per workstation: a nudge
that finds the lock held leaves a mark NAMING ITS SOURCE, and the holder syncs
every source a mark names before it lets go.

**The read.** `lanes --worktrees` reads this workstation's sidecars; with
`--index` it reads the table — every `inventory:*` source the store holds, so
Raven sees Eagle's leftovers — and stderr says `read: index (<store>) at
inventory:<ws> synced <UTC>`, or `read: sources (index <why>)` and the sidecars
answer. Where the table is current, this workstation's rows are the same bytes
either way — and a store only this workstation syncs into (SQLite, or a
Postgres nobody else writes) prints exactly the source read, while a shared one
adds the other workstations' rows among them. Every row is a last observation: the current truth of a lane is `lanes-edit.sh lane-reconcile
<lane>`, which reads the disk, and the footer says so.

**What never reads it.** No act: not `lane-reconcile` — there is no
`lane-reconcile --index`, by Amendment 14(b) — not `lane-start`, `lane-end`,
`lane-handoff` or the worktree sweep (opensoft/openRepoTools#162). Each of them
reads the sidecars and the disk, exactly as before this table existed; an
inventory index that is missing, stale, unreachable, wiped or wrong changes no
answer of theirs.

### The tests' promise

`tests/test_lanes_index.py`, and a section of `tests/test_lane_helpers.sh` for
the acts only that suite drives, hold the index — the inventory's table
included, whose writers and `lane-reconcile` are among the acts — to Amendment
14's eight:
**offline no-read** (every act byte-identical against an unreachable store),
**poisoned index** (wrong rows change no act's answer), **wiped-index
reconcile** (the rebuild equals a synced index row for row), **replay**,
**monotonic provenance**, **a hung indexer** delaying no writer beyond the fork,
**the managed seam** (valid, malformed and plain rows as `managed`, `unknown`,
`legacy`, all through `managed-projection`), and **fallback** (each failure
says `read: sources` and gives the source read's answer). The parser is held
to `LOG_AWK`'s output line for line. No test creates a real database.

## Retiring a lane's worktrees — `lane-worktrees sweep` (#162)

**On Brett Heap's word of 2026-10-05 ("build 162")**, tracked on
[opensoft/openRepoTools#162](https://github.com/opensoft/openRepoTools/issues/162).
A swap that does not finish gracefully — a usage limit, a killed pane, a crashed
harness — leaves its writers' trees where they stood, and the protocol's
worktree-safety rule (a swap never commits, pushes, stashes, resets or cleans)
is right to leave them. This is the act that retires them afterwards, in one
place, under one rule: **nothing is deleted that is not first on origin or in a
bundle under the sweeps directory, and a tree a live writer owns is never
touched.**

```sh
lane-worktrees sweep <lane>                     # the DRY RUN: the table, nothing changed
lane-worktrees sweep <lane> --yes [--live <path>|--live none]
lane-worktrees sweep <lane> --dry-run --porcelain   # lane-end's gate (#163): 0 / 3 / 2
lane-worktrees add <lane> <slice> [--branch <b>] [--from <ref>]   # make a tree AND record it (#163)
lane-worktrees sweep --expire [--yes]           # archives past retention
```

**Which trees are the lane's** is #97's inventory (`lanes-edit.sh lane-trees`)
and the disk — **never the derived index** (Amendment 14 clause (b)). The sweep
also reads every registration of the lane's checkout and every checkout under
its two roots (`<checkout>/.claude/worktrees/*`, `.lane-worktrees/<lane>/*`).
A tree the inventory does not name is still **the lane's** when it stands under
the lane's own root, `.lane-worktrees/<lane>/` (only this lane's starts make it),
or sits in `<checkout>/.claude/worktrees` with its HEAD — a commit origin's
default branch lacks — carrying this lane's `Lane:` trailer AS ITS OWN (a tree
another lane stacked on this lane's commit is not this lane's, #174); its rows
say so. A lane with no #97 snapshot at all (state `NONE`) but trees of its own is
**refused, exit 2**: which trees are its is recorded nowhere, so #163's gate does
not pass it. Any other tree the inventory does not name is **FOREIGN**: reported and left, unless
`--include-foreign` and a `--word "<verbatim>"` (recorded in every register line
it causes). A tree ANOTHER lane's inventory names is that lane's and is never
taken from here, word or no word — and one BOTH inventories name is kept, since
records are history and a path can be reused. Other lanes' claims are read
wherever #97 keeps them (#170 G6): beside this lane's control root, under
`$LANES_LANE_STATE_ROOT` and `$PROJECTS_ROOT/.lane-state`, beside every checkout
the estate's shape walk finds, beside every lane's recorded `dir` in the
register's lane logs that lies in this sweep's estate (#174), and - where the whole estate is walked (a clone the table
could take, or `--include-scratch`) - in every `.lane-state` that walk finds, one
in a plain directory inside a repository included (#174). An inventory record that cannot be
read (no id, no path, an unknown schema; #170 G9) refuses the sweep, exit **2**: its tree's owner
is unknown — and so does ANOTHER lane's record or inventory directory, a lane
worktree root, a checkout's `git worktree list`, or the register's lane logs that
cannot be read, before anything is fetched (#170 G1, G5); another lane's claim
that cannot be read is a NOTE instead where this lane has no tree, since a claim
could only take one from it (#174). The lane's own checkout is never a candidate. The lane name is
resolved first (`lanes-edit.sh canon-lane`, Amendment 15), as `lane-start` and
`lane-end` resolve it; an alias table that cannot be read refuses.

**Who may act** is #97's reconciliation (`lanes-edit.sh lane-reconcile`), read
before anything is written — the fetch included. Under `--yes` the register is
FETCHED FIRST, by the sweep itself (`origin/<branch>` of the workspace
repository, an explicit refspec): `lanes-edit.sh`'s own fetch answers 0 when it
fails, and an inherited `LANES_NO_FETCH=1` skips it, so a lane rebound on another
host after this one's last fetch would read as bound HERE (#170 A1). A register
that cannot be fetched refuses, exit **2**, with nothing changed. The fetch of
each repository acted in pins its refspec as `status --fetch` does
(`+refs/heads/*:refs/remotes/origin/*`, `--refmap` the same, tag pruning off), so
a mirror-style `remote.origin.fetch` cannot let `--prune` delete a local branch
before it is classified (#170 item 6).

| the lane | dry run | `--yes` |
|---|---|---|
| bound on another host or container (Amendment 18(b): UNKNOWN, never dead) | the table, exit **2** | refused, exit **2** |
| its binding, holder or reconciliation could not be read | the table, exit **2** | refused, exit **2** |
| held by ANOTHER live session | the table, exit **2** | refused, exit **2** |
| managed-owned (ruling 2026-10-04) | refused, exit **2** | refused, exit **2** |
| held by THIS session, or with a tree THIS session recorded (an inventory `writer` that is the caller, #170 B5) | the table | only with the coordinator's writer count: `--live <worktree>` per live writer (its ListAgents count, Amendment 17 Addendum 1 (i)), or `--live none`. A path that names no tree of the table, or `none` beside a path, is usage, **64** (#170 B4) |
| `SWAPPING` in a live session | the table | refused: a handoff is in flight |
| no live holder, bound here, free or gone | the table | performed |

### The table, as implemented

Each tree is classified in this order; the first row that matches decides.

| tree | disposition | what `--yes` does |
|---|---|---|
| not in the lane's inventory | `foreign` | nothing (`--include-foreign --word …` applies the rows below) |
| a process stands in it or holds a file open there (`/proc`, else `lsof`), a tmux pane's current path is in it, it is named by `--live`, the sweep was started inside it, or the session that recorded it is live | `live` | nothing, ever — asked again at the moment of the act |
| liveness could not be read — the scan failed, or a process of THIS account whose `/proc` entries cannot be read (not dumpable) is placed in it by an absolute path in its command line or by its parent's working directory (#170 item 2) | `keep` | nothing |
| its directory is gone and git still registers it | `prune` | `git worktree remove <path>` — that one registration; a repository-wide `git worktree prune` is never run (it would unregister other lanes' and FOREIGN trees too); a directory that reappeared meanwhile is left for the next sweep to classify |
| … and its registration's git directory names a commit no branch, tag or origin holds — a detached HEAD, a reflog entry (#170 A4) | `rescue+prune` | a rescue branch pushed (where there is an origin) and a bundle, then that one registration removed |
| … and its registration's git directory keeps a submodule repository (`modules/`) with a branch, tag, stash or reflog entry no remote of it holds, or an annotated tag object none of them holds (#174) | `keep` | nothing: the prune would take that repository (asked again just before) |
| its directory is gone and nothing registers it | `gone` | nothing; the inventory record is history |
| another lane's inventory names it too | `keep` | nothing: which lane owns it now is a person's to say |
| a registration someone LOCKED; a file flagged skip-worktree or assume-unchanged that differs from the index (git status hides it, #170 A2); a submodule with uncommitted work, ignored files no commit carries (an `.env`), a branch, tag or HEAD no remote of it holds, a stash (#170 item 5), a commit only its reflog names, or a skip-worktree or assume-unchanged edit (#174) — its repository lives under the tree's git directory and goes with it; any submodule repository that git directory keeps under `modules/` with a branch, tag, HEAD, stash or reflog entry no remote of it holds, or an ANNOTATED tag whose very tag object none of them holds (asked of each remote at the act), a DEINITIALIZED submodule's included (#174); a repository nested anywhere inside it, a venv's `src/`, node_modules and a cache-named directory included (#170 A3, #174); a CLONE with a branch, a TAG (#170 item 4) or a stash origin lacks, or whose git directory linked worktrees share | `keep` | nothing, and the line says which |
| something leans on it — another repository's `objects/info/alternates`, or a remote whose URL is its path, read from every repository the estate walk finds: every directory of the estate but caches, tool environments and `site-packages`, a plain directory inside a repository included (#170 A11) | `load-bearing` | nothing; the line names every dependent and the remedy (`git repack -a -d`, then drop the alternates or re-point the remote) |
| a CLONE (removed by deleting its directory) when the search for what leans on it was partial: a directory of the estate could not be read, there is no estate root, or the clone lies outside it (#170 A11) | `keep` | nothing |
| no `origin` | `keep` (`bundle+remove` with `--bundle`) | a bundle is its only rescue |
| dirty or untracked work, where git-lfs is configured and an untracked file is `filter=lfs` content | `keep` | nothing: untracked files go to a bundle only (below), and a bundle carries an LFS pointer, never its bytes (#174); asked again at the act, before anything is pushed |
| dirty or untracked work | `wip-rescue+remove` | the tracked changes (`git add -u` into a COPY of its index), `commit-tree` on its head, `rescue/<lane>/<slice>-<UTC>` pushed and seen on origin; UNTRACKED files in a second commit on it that goes to the bundle ONLY, never to origin — an un-ignored key file is not something anyone meant to push (#170 A9; `--push-untracked` pushes them as before). Which files are untracked is read from the two snapshots taken AT THE ACT, never from the table's status, so a file that arrived since is held back too (#174); a bundle, then removed |
| an unborn branch, clean | `remove` | removed |
| detached at a commit origin holds | `remove` | removed |
| detached with commits of its own | `rescue+remove` | `rescue/<lane>/<slice>-<UTC>` pushed, a bundle, then removed |
| MERGED — its PR LANDED in the register, or `gh` says MERGED, into the default branch, and that PR's head holds this tip | `remove+delete-branch` | removed; local branch deleted at the SHA judged merged (`update-ref -d <old>`), and the remote branch too — under a lease on the judged SHA — where its `Lane:` trailer is this lane's, it holds nothing the PR did not, and `gh` does not still answer a PR of it OPEN (a LANDED line with a wrong number never closes an open PR, #170 A8) |
| clean, every commit on its own remote branch (an open PR is untouched) | `remove` | removed; the branch stays |
| clean, its head on some origin branch | `remove` | removed; the branch stays |
| unpublished commits on `main`/`master`, or on a branch origin has DIVERGED from | `rescue+remove` | the tip to `rescue/<lane>/<slice>-<UTC>`, then removed; the branch itself is never force-pushed |
| unpublished commits on a branch an OPEN pull request names (gh's OPEN wins over a register LANDED line naming that PR, #174), whose origin tip carries ANOTHER lane's `Lane:` trailer, or where whether a PR names it could not be read (#170 A7) | `rescue+remove` | the same: the lane's unreviewed commits never go onto somebody else's branch, and origin's branch is left as it is |
| unpublished commits otherwise | `push+remove` | pushed AS IS under its OWN name — never its upstream's, which for a branch made from `origin/main` is `main` — then removed |

**"Merged" is never `git branch --merged` alone**: a squash merge leaves no
ancestry, and a branch whose tip IS on `main` with no pull request naming it is
listed as unmerged and its branch kept. A PR merged into another base (a release
or feature branch) is no landing, and an OPEN PR protects its branch however an
older PR of the same branch was merged — unless the register has LANDED that
very PR. The branch's pull request comes from one `gh pr list --state all` per
repository; with `LANES_NO_GITHUB=1` or no `gh` nothing is called merged. The register's `LANDED` lines are read from
`origin/<branch>` of the workspace repository.

**Liveness is asked again before the rescue and again at the moment of
removal** — processes, open files, tmux panes and the recording session, afresh;
a scan that cannot be made leaves the tree. **At the moment of removal** the
head is re-read, and the tree must still be clean — or, after a WIP rescue, must still be byte for byte the tree the rescue
commit carries. A push that origin refuses leaves the tree exactly as it was:
the WIP commit is made BESIDE the tree, never into it, so its branch, index and
files never move. Every push is checked on origin (`git ls-remote`) before
anything goes, and where the repository has git-lfs configured (`filter.lfs.*`)
it runs its hooks, so git-lfs's pre-push uploads the objects (#170 A10).

**Before each removal git is asked what it would take.** A worktree's removal
takes its own git directory — its HEAD and that HEAD's reflog (and its branch
and the branch's reflog, where the branch is deleted after it); a pruned
registration's the same; a CLONE takes every ref but its remote-tracking ones,
and every reflog — a reflog directory that cannot be listed makes the answer
unknown, and the clone stays (#174) — and an ANNOTATED TAG is its own object,
kept where origin holds that very tag object (`ls-remote --tags`) and bundled,
its message with it, where it does not (#174); a `--branches` delete takes the
branch's tip and its reflog (#174). Commits there that no origin ref, surviving
branch, tag or stash keeps — a commit only a reflog names, after an amend or a checkout away
from it (#170 A5) — go to a bundle first, through temporary
`refs/lane-worktrees/<slice>-<UTC>/*` refs deleted once it verifies. **The
self-check** asks the same question once more right before the removal: a
commit the removal would take that is neither on origin, in a ref that stays,
in a push seen on origin this run, nor in a bundle this run verified is a
defect in the table, and the sweep REFUSES it — exit **2**, a line in
`DISPOSITION.md`, nothing after it acted on. A CLONE with a local git-lfs
store (`.git/lfs/objects`) whose commits would go to a bundle only is kept
instead: a bundle carries LFS pointers, never their bytes (#174). The first register line that
cannot be written stops the sweep the same way (exit 1, #170 B6).

**Ignored files that are not caches or build output** (an `.env`, a local
config) are archived to `<slice>-ignored.tar.gz` before a tree goes: a commit
cannot carry them, and the rule is that nothing goes that is not first saved.
They are listed again at the moment of removal, and a tree whose ignored files
changed, appeared or went since the archive was taken is left.
Build output (`target`, `build`, `dist`, `.tox`, `.next`, `*.egg-info`, …) is
generated and is not archived — judged by the ignored entry's OWN name, never an
ancestor's, so `docker/build/prod.env` is archived (#170 A6) — and so are
`docker/node_modules/prod.env` and `docker/.venv/prod.env`: the archive leaves
caches out only BENEATH an entry it was given, and is read back for every entry
selected, so one missing leaves the tree (#174). More than
`ignored_archive_mb` of the rest leaves the tree in place for a person.

### The other rows

| flag | what | disposition |
|---|---|---|
| `--branches` | local branches no worktree holds, in the lane's checkout | merged by PR evidence: `delete` (`delete+remote` where the `Lane:` trailer is this lane's, origin's tip is inside the PR and gh does not answer it OPEN), each at the SHA judged and only after a fetch of that checkout that worked under `--yes`, and only after what the delete would take — its tip and every commit its reflog names — is on origin, in a ref that stays or in a bundle (a `bundle:` ledger row), asked once more right before the delete: the self-check, exit **2** on a refusal (#174); an open PR's branch: `keep` — and still COUNTED where it is the lane's and `origin/<branch>` lacks its tip (#170 G2); a branch `origin/<branch>` holds, whatever its configured upstream, is published and not listed (#170 G7); unmerged with a missing, diverged, unpushed or unreadable upstream: `list` with its tip, distance from `origin/main`, last commit date and owner — never deleted; `main`, `master` and `rescue/*`: never touched |
| `--include-scratch` | `.lane-worktrees/<lane>/*-scratch`, `briefs/`, `bin/` that are no checkout | `archive+remove`: tar (caches left out) and sha256, then removed — only if no writer arrived and nothing outside the caches changed while the tar ran; `keep` while a tree of the table or any `.git` lies under it (#170 item 7), or the search for what leans on it was partial (#170 A11) |
| `--include-caches` | `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `node_modules`, any directory with `pyvenv.cfg` (and `venv/`, `.venv/` with an activate script), under `.lane-worktrees/<lane>/**` and the lane's inventory trees | `remove`, without archiving — never one git tracks or whose tracking cannot be read, one that is or holds a repository or a directory that cannot be read (`keep`: a venv's `src/` clone is work, #174; asked again just before), one inside scratch being archived, or one in a FOREIGN tree, a live one, one whose liveness is unknown or one left by its own act; the owning tree's liveness is asked again just before |
| `--include-sandboxes` | `tmp.*` and `pytest-of-$USER/pytest-*` in `/tmp` and `$TMPDIR` (or `LANE_WORKTREES_SANDBOX_ROOTS`), and `tests/run.sh`'s run roots, owned by this account | `remove` where the owning process is gone: a pytest `.lock` naming a dead pid (read again at the act), and no live process standing in it, holding it open or naming it in its environment. A `tmp.*` is NEVER removed (#170 item 1, option (b); #174): `mktemp -d` records no owner, so neither a suite's mark in it nor `aging_days` untouched proves a suite made it — one older than `sandbox_min_age_minutes` (by the newest file in it) is `list`ed and left, with its mark and any repository in it (a bare one included), since it may be a person's checkout or scratch |
| `--links` | every symlink under the estate and every worktree `.git` gitdir pointer | `broken`, listed with target and age; nothing changes |
| `--bundle` | every tree acted on | a `git bundle` beside the archive (always, for a rescue) |

### The sweeps directory, the register line, retention

`${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/sweeps/<lane>/<UTC>/`,
mode 0700, created EXCLUSIVELY by the first act of a `--yes` (a second sweep
started in the same second gets `<UTC>-2`) and never by a dry run:

* `DISPOSITION.md` — every tree and item acted on: what it was, why, what was
  done, where its rescue is, and the register line that records it;
* `rescues.tsv` — `origin`, rescue branch and sha for each rescue, which
  `--expire` reads; a bundle that is the ONLY copy of what it holds (untracked
  files, commits only a reflog named, a tree with no origin) is a row too, with
  origin `-` and branch `bundle:<file>` (#170 item 8);
* the bundles, `<slice>-ignored.tar.gz` and `scratch-<name>.tar.gz`;
* `MANIFEST.sha256` — `sha256sum` format, every file above.

**One register `NOTED` line per tree acted on** (`lanes-edit.sh log NOTED
lane:<lane>`), written after the act so it says what happened, naming the
disposition, the rescue and the archive; one more each for scratch, branches,
and caches with sandboxes, each written as the session that swept
(`LANES_SESSION`, #170 E7). A line the register refuses is printed whole for a
person to write by hand - quoted for the shell (#170 E6) and naming that same
session (#179) - and the exit is 1. The line is the pointer that
outlives the archive.

**Retention: 90 days** (`sweep.conf`). `sweep --expire` lists archives older than
that, and with `--yes` removes those whose every rescue branch is still on
origin AT THE RESCUED SHA (`git ls-remote`); an archive whose rescue branch is
gone from origin, or was remade at another commit, or that holds a `bundle:` row,
is the only copy and is NEVER expired. Nor is an archive that is not WHOLE — no `MANIFEST.sha256`, a file it
does not list or whose digest differs (a sweep interrupted after a bundle), or a
`rescues.tsv` that is missing or has a row that is not origin, branch and SHA,
or a manifest entry whose file is gone. What expired is appended to
`sweeps/EXPIRED.log`.

`${XDG_CONFIG_HOME:-$HOME/.config}/openRepoTools/sweep.conf` (or
`$LANE_WORKTREES_CONF`), `key=value` lines:

| key | default | what |
|---|---|---|
| `retention_days` | 90 | archive age before `--expire` may remove it |
| `aging_days` | 14 | a rescue branch or dirty inventory tree older than this is "awaiting disposition" in the report |
| `sandbox_min_age_minutes` | 60 | a `tmp.*` younger than this is never a killed suite's |
| `foreign_quiet_hours` | 24 | a FOREIGN tree active within this is treated as live, even with `--include-foreign` |
| `ignored_report_mb` | 50 | the report's threshold for an ignored directory |
| `ignored_archive_mb` | 200 | ignored files (not caches, not build output) a tree may carry into its archive; more, and the tree is left for a person |

### The exit contract (`lane-end`'s gate, #163)

`lane-worktrees sweep <lane> --dry-run --porcelain` prints one tab-separated
row per tree and item, between a `lane` row and a `summary` row:

```text
lane    <lane> <state> <holder> <holder uuid> <binding> <verdict>
refused <why>                                   (only when refused)
tree    <disposition> <retire|-> <path> <branch> <head> <why>
<kind>  <disposition> <retire|-> <path> <detail> <bytes> <why>     (branch, scratch, cache, sandbox, link)
leg     <disposition> <retire|-> <path> <branch> <head> <why>    (an assembly's checkouts only, T018)
summary <to retire> <trees> <live> <foreign>
```

**`lane-end` reads it with `--branches --include-scratch --include-caches`** and
refuses on 3 and on 2 — and on 0 too where a `cache` row is printed, because a
cache under the lane's root is still the lane's to clear though never its work to
retire, or where its own read of the lane's root finds residue no row names
(see [`lane-end <lane>`](#lane-end-lane)). It counts the rows whose second field
is `retire`, plus every `cache` row; a FOREIGN tree, another lane's branch and a
`gone` record count for nothing. It passes `LANES_EDIT` through and sets
`LANES_NO_FETCH=1`, having fetched in its own reads.

Every field is escaped — a backslash is written `\\`, a TAB `\t`, a newline `\n`
and a carriage return `\r` — so a path holding any of them is still one field
of one row; bytes that are not UTF-8 pass through as the bytes they are. The
command exits **0** (nothing to retire), **3** (something to retire — a tree of the
lane's on disk, live or not, a stale registration, an unpublished or merged
branch of the lane's, included scratch), or **2** (refused: bound elsewhere,
held by another session, managed, a lane with trees and no #97 snapshot, a read
failed — a lane root, a registration list, another lane's claim on a lane with
a tree, the register's lane logs, or under `--yes` the register's fetch — or an
error no read caught, which is never a traceback's exit 1 on a dry run). FOREIGN trees, links,
caches and sandboxes are never the lane's to retire. `--yes` exits 0 when every
act completed, 1 when one failed part-way (the rest go on — unless a register
line could not be written, which stops the rest; each failure is in
the table and in `DISPOSITION.md`, which is written even when an error no read
caught stops the run), and **2** when the self-check refused a removal; usage
is 64, a `--live` path that names no tree included.

### A triad: its legs, their worktrees and the paired trees (T018)

**Plan task T018 of the triad migration (opensoft/openRepoTools#186).** A lane's
checkout is an **assembly** when its own `project.yaml` declares a leg other than
itself — the standard's rule, as openRepoShape's `templates/assembly-root/project.yaml`
writes it: a top-level `legs:` list of `- role:` / `repository:` / `path:`, the
assembly's own leg at `path: "."`. One reader answers it for every lane tool:

```sh
lanes-edit.sh project-legs <checkout>   # <repository> TAB <path as declared> TAB <where it is checked out>
```

It is `lane-start`'s rung-5 reading of `legs:`, line for line (a test holds the two
equal), and reads `repository:` and `path:` only — the manifest confers nothing,
and `role:` is never read. 0 with legs; 8 with none (no `project.yaml`, or one naming
no leg but the checkout itself); 1 where the manifest is there and cannot be read,
which is never "no legs"; 64 usage. It touches no workspace.

**Why the sweep needed it.** A leg is a submodule: its `.git` is a file,
`git -C <assembly> worktree list` names none of its worktrees, and a feature's
trees in the standard's three-leg layout, `<assembly>/worktrees/<feature>/{spec,code}`,
are worktrees of the LEGS' repositories. So a code tree was invisible to the sweep,
to `lane-end`'s gate, to the handoff's poll and to the daily report unless it had
been recorded with the code leg as its checkout — and a lane with unpushed work in
one passed `lane-end`.

**Where the lane's checkout is an assembly**, `lane-worktrees sweep` also:

* reads every leg, and every dependency nested in one (an initialized submodule of
  the leg's own, as `code/upstream/openRepoShape` will be), as a **`leg` row** —
  `clean`, `dirty`, `unpushed`, `dirty+unpushed`, `absent` (not checked out here)
  or `unreadable`. A leg is the assembly's, shared by every lane the assembly
  homes, as the assembly's own checkout is: **no `--yes` acts on one**. It is
  COUNTED (exit 3, and `lane-end`'s gate) only where its HEAD's own `Lane:` trailer
  is this lane's and it holds edits or commits origin lacks — the rule the sweep
  already applies to `.claude/worktrees` — or where it could not be read; one
  that holds another lane's work, or nobody's, is listed and counted for nobody;
* lists the worktrees git registers in **every leg** — a FOREIGN row names the leg
  it is registered in — so a tree recorded with the leg as its checkout is the
  lane's as any recorded tree is;
* takes **`<assembly>/worktrees`** as a root: a tree there is the lane's by its
  HEAD's own `Lane:` trailer and by nothing else, because the paired root, like
  `.claude/worktrees`, is per feature and not per lane; a standalone clone there is
  FOREIGN; a directory there that cannot be listed refuses, exit **2**;
* with `--branches`, reads every leg's branches too, each row naming its leg; with
  `--fetch` (and under `--yes`), asks each leg's origin.

A manifest, or a leg's own submodule list, that cannot be read refuses, exit
**2**. **A checkout with no `project.yaml` is asked nothing** — no helper call, no
read, no row — so a single repository's sweep, gate, handoff, report and `add` are
byte for byte what they were; `tests/test_triad_lane_tooling.py` holds every one of
them to the output `c45a452`'s tools printed.

**`lane-end`'s gate** counts a `leg` row marked `retire` as a "leg checkout" it
names, with the remedy a person's (commit and push from inside it; no `--yes` is
offered when legs are all it counted), and lists a leg that holds work and is not
this lane's below the table as NOT counted — whether the gate passes or not.

### Two protocol lines this act assumes (proposed for the amendment that ratifies it)

1. **A lane creates worktrees, never clones.** Every tree a lane works in is a
   `git worktree` of the estate's checkout, recorded in its inventory (#97) —
   which `lane-worktrees add` does in one act (below). A
   standalone clone under a lane root is FOREIGN to every sweep, and one that is
   a shared store or a local remote is LOAD-BEARING. A lane adds no local remote
   and no alternates.
2. **Scratch lives in the session scratchpad or the lane's state directory,
   never beside repositories.** `.lane-worktrees/<lane>/*-scratch`, `briefs/`
   and `bin/` are grandfathered into the archive-then-remove row; new scratch
   goes to `${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/lanes/<lane>/scratch/`
   or the harness scratchpad.

### Making a lane's worktree — `lane-worktrees add` (#163)

**Creation records the tree, in the same act.** Nothing in this tooling made a
worktree before this verb — `lane-start` makes none, and every writer's tree was
a `git worktree add` typed into a brief — so the inventory was written only at a
handoff, and a lane that never handed off had none: lane `openRepoTools-3`'s was
empty while nine trees under its root were its own, and the sweep could not
judge them.

```sh
lane-worktrees add <lane> <slice> [--branch <name>] [--from <ref>] [--checkout <dir>] [--dry-run]
```

It makes `<parent of the lane's dir>/.lane-worktrees/<lane>/<slice>` as a `git
worktree` of the lane's recorded checkout (or `--checkout <dir>`, the root of a
checkout), on `--branch` (default: the slice) — checked out where that branch
exists, otherwise made from `--from` (default `HEAD`) **with `--no-track`**, so
a bare `git push` never aims a writer's commits at the branch it started from —
and then records it with `lanes-edit.sh set-lane-tree <lane> <path> --checkout
<dir>` (with `--writer` where the caller's session is a transcript uuid). The
path is the one line on stdout. It refuses, exit **2** and nothing made, a
managed lane or one whose ownership could not be read, a lane that records no
directory, an inventory that cannot be read, a path that already exists, a
branch name git does not take, and `--from` beside a branch that already exists.
**A record that fails after the tree is made — or a `git worktree add` that
fails after making it, as one does when a `post-checkout` hook fails — takes the
fresh tree and the branch this act made back out** (`git worktree remove`,
without `--force`, and `update-ref -d` at the commit it made) and exits 2; only
where something is left — the undo failed, a directory git does not register,
which is named and never deleted blind, or a new branch that has moved past the
commit this act started it at, which is kept so that commit stays reachable — is
the exit **1**, with the `set-lane-tree` that records it printed. Usage
is 64, and every flag of the sweep's is usage here.

A tree made any other way — a brief's own `git worktree add`, the harness's
`isolation: worktree` — is still legal git and is FOREIGN to every sweep until
`lanes-edit.sh set-lane-tree <lane> <path>` records it.

### The estate report — `sweep --all --dry-run --report`

The net under every actor that never runs `lane-end`: **creation outpacing
closeout as a number that is read every day.** It reads every lane's #97
inventory and snapshot in every `.lane-state` it can find (#170 G15, B8):
`<estate>/.lane-state`; beside every checkout the estate's shape walk finds,
so a nested checkout's lanes are read where #97 keeps them; under every
directory a walk of the whole estate finds, caches skipped, a plain directory
inside a repository included (`xFactory/xFactories/.lane-state`); beside every
lane's recorded `dir` in the register; and `$LANES_LANE_STATE_ROOT`. It also
reads the workspace repository's register on `origin/<branch>`, and the disk —
**never the derived index** (Amendment 14 clause (b)) — and CHANGES NOTHING:
no fetch, no index refresh (`GIT_OPTIONAL_LOCKS=0`), no expiry. A byte that is
not UTF-8, in a path or in the workspace's `.gitignore`, is carried as itself,
never an error (#170 G10-G12).

```sh
lane-worktrees sweep --all --dry-run --report [--estate <dir>] [--post <file> | --post <owner/repo>#<n>]
```

| section | what is listed |
|---|---|
| FOREIGN repositories | a CLONE inside a worktree container (`.lane-worktrees/<lane>`, `.claude/worktrees`, `worktrees`, `<x>-worktrees`), and a second clone of an origin the estate already has a checkout of: path, size, last commit, owner (the last `Lane:` trailer), and LOAD-BEARING with its dependents where something leans on it |
| Orphaned worktrees of ENDED lanes | trees an inventory records, and directories under `.lane-worktrees/<lane>`, of a lane whose snapshot is `CLOSED` or whose log's last lane line is `ENDED` or `RETIRED` — with the sweep that retires them. Empty beside a record it could not read — a lane snapshot, an inventory, the register's lines, a directory the walk could not list — it says "none found in what could be read", never "none" (#170 B8); a failure that is no lane record (an ignored-file listing, say) is still a row of the last section but leaves "none" as it is (#179); so does Awaiting disposition |
| Unmerged branches | local branches of every checkout with no upstream, a gone upstream, a diverged one, or unpushed commits: tip, state, age, owner, and whether a worktree holds it. Never deleted; `main`, `master` and `rescue/*` are not listed |
| Root main divergence | a checkout whose local `main` is ahead of `origin/main`; where every changed path is under `handoffs/` or `lanes/`, the remedy is Amendment 4's — those live in the workspace repository and are pushed per write |
| Awaiting disposition | a `rescue/*` branch (local or on origin) and a DIRTY inventory tree whose git directory has been still for `aging_days` (14), with owner and age |
| Caches and sandboxes | `--include-caches`' and `--include-sandboxes`' rows across every lane, by size |
| Ignored directories over `ignored_report_mb` | every ignored directory of every repository at or over 50 MB (`du -sk`) |
| Evidence-shaped paths | untracked or ignored — an ignored FILE as much as an ignored directory (#170 item 9) — `junit*.xml`, `MANIFEST*`, `*-report.md`, `*REPORT*.md`, `canary-*`, `*-evidence`, `deployment-evidence` inside a repository, and a directory of reports beside the repositories — each a finding to move to the evidence root below |
| Sweep archives past retention | `sweep --expire`'s own dry run: what WOULD expire, and what is past retention but kept because its rescue left origin. Expiring stays an act (`sweep --expire --yes`) |
| Workspace repository hygiene | the workspace's `.gitignore` lines it lacks (with the one command that adds them, its path quoted for the shell, #170 item 10), and bytecode already in its history (for a person's word: history is rewritten only on one) |
| Records the report could not read | a lane snapshot, inventory directory or record, or an inventory tree's `git status`, that could not be read; a directory the estate walk could not list, the estate root itself (#170 E10), the register's lane logs or its ENDED and RETIRED lines where the `git grep` failed (#170 G3), and a repository whose ignored or untracked files could not be listed (#179) — unknown is never absent, and the sections above may be missing what it holds |
| `status --all` findings | the estate command's ahead/behind, fork, shape-pin and parked-record lines, reported as what they are and never counted as dirt (`LANE_WORKTREES_STATUS` names the command when it is not beside this one) |

The summary table at its head also carries **the count of rescue branches** and
**the sweeps directory's size**, so the cleanup's own footprint is watched.
`--post <file>` writes the report there; `--post <owner>/<repo>#<n>` comments it
on that issue through `gh`; with no `--post` it is printed. `--all` and
`--report` come together, with no lane, no `--yes` and no `--expire` (usage, 64).

**`lane-start` runs it once a day per workstation**, after the row is written
and before the launch: the first start of a UTC day takes the stamp
`${XDG_STATE_HOME:-~/.local/state}/openRepoTools/report-<YYYYMMDD>.stamp`
(an atomic `set -C` create, so two starts at once run one report), removes
older stamps, and starts the report DETACHED — stdin, stdout and stderr closed,
in a subshell that exits at once, under `nohup` and, where there is a `setsid`
(Linux), in a session of its own, so a pane killed after the stamp was taken
does not take the report with it (#170 E8) — over the start's own
`$PROJECTS_ROOT`, writing `…/openRepoTools/reports/<UTC>.md`. The report names
every path, branch and lane of the estate, so it is private: the state and
reports directories are 0700 and the report is written under `umask 077`
(#170 item 11); where they cannot be made 0700 no report starts and no stamp
is taken, so the next start tries again (#179). Every step either works or is skipped in
silence: the report never delays a start and never fails one. `--dry-run`
starts none; `LANE_WORKTREES_REPORT=off` is the switch (both suites set it).

### Nothing new lands beside the code

The sweep retires what is already there; these keep more from arriving.

* **`tests/run.sh`** sends bytecode to
  `${XDG_CACHE_HOME:-~/.cache}/openRepoTools/pycache`, turns pytest's cache off,
  and roots every temporary directory of a run under
  `${XDG_STATE_HOME:-~/.local/state}/openRepoTools/tmp/<UTC>-<pid>/`, which its
  EXIT trap removes however the run ends — after stopping the suite's whole
  process group (TERM, then KILL at ten seconds, and only then the leader
  reaped, so a suite that ignores TERM cannot hold the lock for ever: #170 item
  3), so nothing it started outlives the run root or the lock. With
  a terminal on stdin the suite runs in the FOREGROUND instead, so `--pdb` or a
  `breakpoint()` can read it (a background group would be stopped by SIGTTIN,
  and the wrapper would wait on it holding the lock); it is then in the
  wrapper's own group, whose members are read before the suite starts, and
  what is there afterwards that was not, and is no sibling of the wrapper, is
  stopped the same way before the cleanup (#170 G14). `--basetemp` is the
  wrapper's own, and a caller's is refused, 64 (#170 G8). A SIGKILL is the one end no trap sees;
  the pid in the name is what lets `--include-sandboxes` tell its owner is gone.
* **One virtual environment per repository, outside the estate:**
  `${XDG_CACHE_HOME:-~/.cache}/openRepoTools/venvs/<repo>/`. `openRepoTools
  --install` names this repository's and says whether it is there; `tests/run.sh`
  runs from it when it has `pytest`. A `venv/` or `.venv/` inside a worktree is
  a legacy leftover for `--include-caches`.
* **One evidence root per repository:**
  `${XDG_STATE_HOME:-~/.local/state}/openRepoTools/evidence/<repo>/<UTC>-<slug>/`
  for JUnit files, manifests, reports, canary and deployment evidence — never
  inside a checkout and never beside the repositories. The report lists what is
  still found inside the estate.
* **The workspace repository never carries bytecode.** `openRepoTools wip init`
  seeds `__pycache__/`, `*.pyc`, `*.pyo`, `.pytest_cache/`, `.mypy_cache/`,
  `.ruff_cache/`, `node_modules/`, `.venv/`, `venv/` and `site-packages/` (a
  virtual environment under any other name) into the new
  workspace's `.gitignore` (a line the template already carries is not
  repeated). Every commit `lanes-edit.sh` makes asks git what its pathspec would
  stage (`git add --dry-run`) or holds staged already, and REFUSES, exit **2**,
  nothing staged, when any of it is bytecode, a cache, a dependency tree or a virtual environment — and
  offers the `.gitignore` lines a workspace without them lacks. A pathspec git
  cannot read (a malformed magic pathspec, an unreadable index) is refused the
  same way, never read as clean (#170 G13). Attachments are
  committed by hand, so the same question is a subcommand:

  ```sh
  lanes-edit.sh pathspec-check handoffs/<repo>/attachments/<slug>
  # 0 clean · 2 the offending paths on stdout, the offer on stderr, or the read failed · 64 usage
  ```

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

The legacy supervisor uses the current profile launcher's existing-TMUX path,
which keeps the exact operation as a child and forwards its operation/attempt
tokens. The historical #94 incident above describes the earlier launcher. A
respawn also forwards configured `LANES_LANE_STATE_ROOT` and
`AGENT_PROTOCOL_ROOT` with shell quoting so its durable intent remains readable.

Legacy lane rename is an explicit publication exception: it already holds the
writer mutex and now refuses unfinished/failed restart ownership before moving
inputs. Its existing four-file transaction uses EXIT rollback, including stamp
write failures; it is not crash atomic across those files. This change does not
claim stronger crash durability for ordinary rename. Restart preservation and
resume-stamp publishers use the atomic checksum-fenced publication helper.

Reconciliation with PR #97 keeps completed restart history under its original
lane name when a lane is renamed. Only the diagnostic lifecycle snapshot and
worktree inventory move to the new control root. The new canonical lane has no
inherited restart operation; unfinished or unreadable intents still refuse rename.
