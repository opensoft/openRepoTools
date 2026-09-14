---
name: restart
description: "/restart binds THIS session to its lane and stamps the record, for a session that started bare or in a window nothing renamed. It reads its own window, its own uuid and the register, binds through lane-start --no-launch, and where this session is not the lane's conversation it prints exactly one command and stops. Never a picker (lane-collision-protocol Amendment 11 clause (f), ratified decisions 3 and 7)."
---

<!-- PROMPTS TO THE PERSON: 0. Every rung of step 2 is an EXACT MATCH — on the
     window's own name, on this session's own uuid, on the window the operator
     is standing in — and the last rung PRINTS THE PER-REPO LISTING AND STOPS
     rather than asking the one confirmation the first draft had. That
     confirmation offered the workstation's newest swap, which on the estate
     this was measured on was the WRONG lane and the only correct answer was to
     decline (decision 7 point 6, ratified 2026-09-13T18:05:29Z). The one
     OPERATOR ACT this skill ever asks for is `/rename <lane>`, at step 7, and
     it is not a question: there is exactly one lane and exactly one spelling
     of it. -->

# `/restart [<lane>]` — bind this session to its lane

Lane-collision-protocol **Amendment 11 clause (f)**, with **decision 7**'s argument. This is the act for a
session that **started bare or in an unnamed window** — the windows still called `claude`, a `claude` typed
by hand, a session that came up before the launcher carried clause (b). It runs **in** that session.

**What it never does, and why each one was paid for:**

- **It never runs the launcher and never resumes anything itself.** `lane <name>` is the outside half and
  it `exec`s; a session cannot exec a launcher over itself, so this one binds the window and prints.
  (That word was `restart <lane>` until Amendment 18 Addendum 2 retired it from the PATH; this skill,
  the INSIDE half, is unchanged by that and keeps its name.)
- **It never opens a picker and never names a title.** Ratified decision 3: *"never a picker, never a
  menu"*. The one command it may print carries an **exact uuid**, so no picker opens and no title is
  filtered.
- **It asks at most nothing.** A printed listing is not a picker: it asks nothing, returns nothing, and the
  next act is a new command the operator types.

`$L` is the register's reader and writer. Prefer it on `PATH` — `openRepoTools --install` puts it there —
and fall back to the symlink Amendment 5 left:

```sh
L="$(command -v lanes-edit.sh || printf '%s' ~/projects/xFactory/lanes-edit.sh)"
WS="$("$L" workstation 2>/dev/null | cut -f1)"    # decision 8(d): configuration, never `hostname`

# EVERY READ BELOW GOES THROUGH THIS ONE FENCE, and Amendment 7(d) is the whole
# of it: `0` an answer · `8` NO ANSWER · `2` a helper predating the read — both
# of those fall to the next rung — and ANYTHING ELSE is a read that FAILED,
# which is a REFUSAL naming the read and never a rung. It sets a VARIABLE rather
# than printing, because a refusal inside `$( )` would only kill the
# substitution's subshell and the skill would carry on with an empty answer.
lread() {                      # lread <var> "<what the failure is NOT>" <verb> [args…]
  ln_var="$1"; ln_not="$2"; shift 2
  ln_out=""; ln_rc=0
  # AND ITS STDERR IS KEPT, MINUS THE ONE SENTENCE THIS READ ASKS FOR (#34,
  # the third site of the shape `lanes` and `restart` took at `29d3417`).
  # `2>/dev/null` was written when the only thing on that stream was
  # `LANES_NO_FETCH=1 — not fetching …`, which is why the whole stream was
  # silenced; anything else there — this workstation's session records
  # unreadable, say — is a read this fence must still be able to name.
  ln_err_file="$(mktemp "${TMPDIR:-/tmp}/restart-lread.XXXXXX" 2>/dev/null || printf '')"
  if [ -n "$ln_err_file" ]; then
    ln_out="$(LANES_NO_FETCH=1 "$L" "$@" 2>"$ln_err_file")" || ln_rc=$?
    grep -v -e 'not fetching; reading origin/' -- "$ln_err_file" >&2 || :
    rm -f -- "$ln_err_file"
  else
    # No capture file, so nothing is filtered and everything reaches the
    # person — never silence in place of a stream this fence could not open.
    ln_out="$(LANES_NO_FETCH=1 "$L" "$@")" || ln_rc=$?
  fi
  case "$ln_rc" in
    0)   : ;;
    8|2) ln_out="" ;;
    *)   printf 'REFUSED: `%s %s` failed (exit %s). That is NOT %s — a read that failed is never an answer (Amendment 7(d)), and this skill will not bind a window, write a stamp or print a resume command on one. Run it by hand to see what it says.\n' \
           "$L" "$1" "$ln_rc" "$ln_not" >&2
         exit 1 ;;
  esac
  eval "$ln_var=\$ln_out"
}
```

## 1. The window

```sh
# THE PROBE'S OWN STATUS IS THE REFUSAL, not a sentence below it (#26, the
# review of `37632b1`, this file's `:64`). The paragraph under this block has
# always said "No tmux → REFUSED", and nothing here captured or tested the
# status: `tmux display-message` on a host with no server prints its error and
# exits non-zero, and the steps below would then go on resolving a lane for a
# window that does not exist — which is the one thing this skill binds.
win_line=""
win_line="$(tmux display-message -p '#{session_name}:#{window_index} #{window_id} #{window_name}' 2>/dev/null)" || win_line=""
if [ -z "$win_line" ]; then
  printf 'REFUSED: there is no tmux window to bind (`tmux display-message` answered nothing). This skill binds a WINDOW; with no window there is nothing to bind. The manual act is: lane-start --no-launch --dir <path> <lane>\n' >&2
  exit 1
fi
printf '%s\n' "$win_line"
```

**No tmux → REFUSED**, naming the manual act: `lane-start --no-launch --dir <path> <lane>`. This skill binds
a **window**; with no window there is nothing to bind — and the block above is where that refusal happens,
rather than in this sentence.

## 2. The lane

**With a `<lane>` argument, SKIP THIS STEP ENTIRELY and go to step 3 with that lane** — the operator's word
beats every inference, exactly as `--lane` does at clause (b)'s precedence 1 (decision 7 point 6). Check only
that the register has a row for it — `lread row_probe "'the register has no row for this lane'" register-row
<lane>`, through the same fence as every other read here, so the check is LOCAL (`LANES_NO_FETCH=1`, like
every read in this skill: a check in front of a bind must not sit on the network or block on ssh) and a read
that FAILED refuses instead of being read as "no such lane". An empty answer — the contract's 8 — is a
**REFUSED** naming `lanes`.

With no argument, four rungs, **first answer wins, and every one of them is an exact match**:

```sh
# (a) THE WINDOW'S OWN NAME. `lane-start` is the only thing that ever writes it,
#     so the name is a statement of intent in the way `--lane` is.
lane=""
win_name="$(tmux display-message -p '#{window_name}')"
lread row_probe "'this window is not a lane'" register-row "$win_name"
[ -z "$row_probe" ] || lane="$win_name"

# (b) THIS SESSION'S OWN UUID, in the register's session cell (R-A11-7).
#     THE READ THAT ANSWERED ON THIS ESTATE THE MORNING THIS WAS WRITTEN: this
#     lane's session had resumed through a bare `claude --resume`, Amendment
#     8(e)'s SessionStart hook fired and printed the lane, and NO STAMP WAS
#     WRITTEN and the window stayed `claude`, because `lane-start` did not run.
#     (a) answers nothing there; the window read answers nothing on a tmux
#     server that has just been replaced; and the swap record offers the
#     workstation's newest swap, which was a different lane. THE HOOK KNEW,
#     exactly and with no question, through this same read — `lane_of_session`,
#     which clause (h) exposes as a subcommand. One implementation, two callers.
[ -n "$lane" ] || lread lane "'no row names this session'" session-lane "$CLAUDE_CODE_SESSION_ID"

# (c) THE WINDOW THE OPERATOR IS STANDING IN, out of the swap records. The
#     `<@id>` first and the `<session>:<index>` second, and either only where
#     that window still exists — `window-lane` owns that fence AND the rule that
#     a record carrying an `<@id>` is matched on its ref only where the window
#     now holding that ref reports that same id. Three callers, one
#     implementation: this skill, the launcher's precedence 3 and `/lane-swap`.
if [ -z "$lane" ]; then
  wid="$(tmux display-message -p '#{window_id}')"
  lread lane "'no lane is bound to this window'" window-lane "$WS" "$wid"
  [ -n "$lane" ] || lread lane "'no lane is bound to this window'" window-lane "$WS" "$(tmux display-message -p '#S:#I')"
fi

# (d) NOTHING MATCHED — PRINT THE PER-REPO LISTING AND STOP (decision 7 point 6).
#     This replaces the first draft's one confirmation on the workstation's
#     newest swap, which on a real estate offered the wrong lane.
if [ -z "$lane" ]; then
  root="$(git rev-parse --show-toplevel 2>/dev/null)"
  origin="$(git -C "${root:-.}" remote get-url origin 2>/dev/null | sed -E 's#\.git$##; s#^git@[^:]+:##; s#^ssh://[^/]+/##; s#^https?://[^/]+/##')"
  # AND THIS ONE GOES THROUGH THE FENCE TOO, which the stop below made matter
  # (#26, the review of `90cef58`, this file's `:133`). It was the last read in
  # the file that ignored its own status, and while the block fell through that
  # cost nothing; the moment it ENDS in an outcome, a `lanes` that exited 1 or
  # 64 would be printed as **[8]**, *no lane for this window* — a refusal turned
  # into a no-answer, at the one rung whose next act is `lane-start`, which
  # CREATES a row. `lread` sets a variable rather than printing, so the listing
  # is printed from it.
  lread listing "'no lane of this checkout is in the register'" lanes ${origin:+--repo "$origin"} ${root:+--dir "$root"}
  [ -z "$listing" ] || printf '%s\n' "$listing"
  # AND THIS RUNG IS TERMINAL, WHICH THE BLOCK SAID EVERYWHERE BUT IN ITS CODE
  # (#26, the review of `29d3417`, this file's `:134`). The heading says PRINT
  # THE LISTING AND STOP and the outcome table ends step 2 here; with `$lane`
  # still empty the lines below would carry on — into a step 3 that resolves a
  # directory for no lane and a step 5 that binds one.
  printf 'NO LANE FOR THIS WINDOW [8] — the listing above is every lane of this checkout. Open one with: lane-start --no-launch <repo> <n>, filled in from this window name where it parses.\n' >&2
  exit 8
fi
```

**AN EXIT `2` FROM ANY RUNG FALLS TO THE NEXT RUNG, NEVER TO A REFUSAL.** `2` is what a `lanes-edit.sh` that
has never heard of `session-lane`, `window-lane` or `lane-dir` exits for an unknown subcommand, exactly as a
pre-Amendment-8 one did for `swapped` — **a helper predating the amendment that added the read, expected and
silent**, told from a caller's bug by the helper's own words rather than by its status. Until the tooling is
installed everywhere, **2 is the answer every workstation gives**, and a `/restart` that refused there would
refuse everywhere (`R-A11-8`, on RV-T3).

**Outcome where every rung answered 8 or 2: `NO LANE FOR THIS WINDOW` [8]**, with the listing above and
`lane-start --no-launch <repo> <n>` filled in from the window's own name where it parses as `<repo>-<n>`.

## 3. The directory

```sh
lread dir "'this lane has no recorded directory'" lane-dir "$lane"
if [ -z "$dir" ]; then                                # 8 → the default; nothing is backfilled
  # `<repo>` IS THE NAME WITH ITS POSITION REMOVED, AND A POSITION IS DIGITS.
  # `${lane%-*}` strips the last `-`-separated token WHATEVER it is, so for
  # `openxfactory-4-opendox-extraction` — a lane this estate has — it answered
  # `openxfactory-4-opendox`, a repository that does not exist. The rule is
  # `lane-start:565-578`'s, which is the writer of these names: a lane is
  # `<repo>-<position>` where the position matches `[0-9]+[A-Za-z]?`, and a name
  # that does not end that way has no position to strip and is its own `<repo>`.
  tail="${lane##*-}"
  case "${tail%[A-Za-z]}" in
    '' | *[!0-9]*) repo="$lane" ;;
    *)             repo="${lane%-*}" ;;
  esac
  dir="$PROJECTS_ROOT/$repo"
  # AND A DEFAULT THAT IS NOT THERE IS NOT A REFUSAL — IT IS `lane-start`'s
  # QUESTION (#26, the review of `c3ebcfe`, this file's `:152`). This rung is a
  # SECOND COPY of `lane-start`'s rung 4 and of nothing else, and `708395e` gave
  # that ladder two more: the estate's `project.yaml` legs, and a checkout named
  # for the lane's recorded home one or two levels under `$PROJECTS_ROOT`, each
  # PROVED by that directory's own `origin`. The paragraph below this step has
  # said since then that where those answer "step 5 resolves it and this step
  # never fires" — and that was not true, because this step fires FIRST: it
  # refused for EVIDENCE 7's own lane, whose checkout rung 5 or 6 can prove, and
  # told the operator to name a directory the estate could already find.
  # So where the DERIVED default is not there, none is passed on: step 5 runs
  # `lane-start` without `--dir`, the one implementation of clause (c)'s order
  # answers, and its own exit 2 is the line this step would have printed. Clause
  # (h) forbids the second implementation the alternative would need here.
  [ -d "$dir" ] || dir=""
fi
```

**A directory the lane's own RECORD names, which is not there → REFUSED**, and the refusal is ONE LINE that
names the act which RECORDS the directory — not just the flag that gets past this run. A restart that lands
in the right transcript and the wrong directory loses the repository's `CLAUDE.md` and the lane's memory,
silently (Evidence 3).

**A DERIVED default that is not there is a different case and is not that refusal.** Nothing was recorded,
so there is nothing to contradict; `$dir` is left empty and `lane-start`'s own ladder — rungs 2 to 6, three
of which this step cannot see — answers next. Step 5 passes no `--dir` there, and `lane-start`'s exit 2 is
this step's refusal, printed once by the command that owns the resolution.

**EVIDENCE 7 is this case, and it is why the refusal must be a refusal.** Measured 2026-09-13T23:01Z: a lane
whose record predates clause (c) carries `home` and `estate` and **no `dir`**, and whose checkout is nested —
`opsXfactory-5`, at `~/projects/xFactory/xFactories/OpsxFactory`. `lane-start` derived
`$PROJECTS_ROOT/<repo>`, found nothing, and **exited 1 behind the launcher's `exec`**: a pane that said
`[exited]` with the message scrolled past it. So print, verbatim and filled in:

```text
lane-start --dir <the lane's checkout> <repo> <n>
```

and say that it RECORDS the directory in the lane's own log, so no later restart on any surface has to be
told again (Amendment 11 clause (c); nothing is backfilled, Amendment 7(i)). **Do not guess a directory**:
`lane-start` writes the lane's home from that directory's `origin`, so a checkout that merely has the right
name re-homes the lane for every `#n` it writes afterwards. `lane-start` itself now tries two further rungs
before it refuses — the estate's `project.yaml` legs and a checkout of the lane's recorded home one or two
levels under `$PROJECTS_ROOT`, each **proved by that directory's own `origin`** — so where those answer, step
5 resolves it and this step never fires.

## 4. The decision — **before** anything is written

```sh
lread row "'the register has no row for this lane'" register-row "$lane"
# AND AN EMPTY ANSWER IS A REFUSAL HERE, not a rung: step 4 decides what to
# WRITE, and `lane-start --no-launch` on a lane-shaped name the register has
# never carried CREATES a row. A read that answered 8 must not reach it.
[ -n "$row" ] || { printf 'REFUSED: the register has no row for lane %s. Find it with `lanes`, or open it with `lane-start <repo> <n>` — this skill binds an existing lane and never creates one.\n' "$lane" >&2; exit 1; }
# `last-session` AND NOT `register-row` ALONE, AND THAT IS RULED RATHER THAN
# ASSUMED (A11 Addendum 4 ruling 14, ratified "a11 addendum 4 yes": *"`/restart`'s
# step 4 may read `last-session` (the cell, then the log) rather than clause
# (f)'s `register-row`, and clause (f) is corrected to say so."*).
#
# WHAT IT CHANGES, said rather than left to be found (F-X15). Clause (f) step 4
# named the last uuid in the PUBLISHED SESSION CELL. `last-session` reads that
# cell first and falls through to the LANE'S OWN LOG where the cell names none
# — the session field of its last `PAUSED`/`RESUMED` — so outcome 4(a)'s *"or
# the cell names no uuid"* stops being reachable for a lane whose log carries
# one, and 4(b) or 4(c) fires there instead. That is the better answer: a lane
# whose row was never stamped but whose log records the session it paused in
# HAS a resume target, and 4(a) would have walked past it into a bind that
# silently orphaned the transcript. The cost is that two sources answer where
# the clause named one, which is why it is a ruling and not a preference.
lread cell_last "'this lane has no resume target'" last-session "$lane"
```

Compare `$cell_last` with `$CLAUDE_CODE_SESSION_ID`:

- **(a) they MATCH, or the cell names no uuid → step 5.**
- **(b) they DIFFER and a transcript for `$cell_last` is in the lane's directory** →
  **print exactly `claude --resume <uuid>` and STOP.** Nothing appended, no window renamed, no stamp, no
  object line. Outcome `RESUME REQUIRED <lane>` **[0]**.
- **(c) they DIFFER and that uuid has no transcript here → step 5**, and step 5's report says so and names
  Amendment 8(d)'s deferral.
- **`$dir` is empty — the record names no directory and no default exists → (b) CANNOT BE DECIDED AND IS NOT
  CLAIMED.** That test is a look inside the lane's directory and there is no directory yet. Say so, go to
  step 5 as (a) and (c) both do, and let `lane-start`'s own rungs resolve it; the report names the uuid step
  4 read and says the transcript could not be looked for — never (c)'s *"no transcript here"* about a place
  this skill never looked.

**THE DECISION COMES BEFORE THE BIND, AND THAT IS `R-A11-2`.** Binding first and comparing after makes the
comparison a **tautology**: `lane-start --no-launch` performs step 3b and the `append-session-id` itself, so
the cell's last id after it is by construction this session's, and the `RESUME REQUIRED` outcome could fire
only where that append had been **refused** — the one place printing an old uuid is wrong. Comparing first
also refuses the contamination clause (d) rule 1 names: a session that is not the lane's lineage must not
rename the lane's window or stamp its row on the way to telling the operator where the lane actually is.

## 5. The bind

```sh
lane-start --no-launch ${dir:+--dir "$dir"} "$lane"
```

`--dir` is passed only where step 3 HAS a directory — the lane's own record, or a default that exists. Where
it has none, the flag is absent and not empty: `--dir` with an empty value is refused by the two spellings of
that arm, and passing a directory this skill DERIVED as `--dir` would put a guess at rung 1, the operator's
own word, in front of the other five rungs `lane-start` reads for itself.

It renames the window, writes the row stamp, Amendment 6(c)'s session-cell append where it can prove the
window is the lane's, the lane's `RESUMED` object line with clause (c)'s `dir`, `profile` and `window`
sub-fields, and the handoff's Rule 3 stamp — and it prints the `claude` command on stdout.
**`/restart` does NOT run that command.**

## 6. The cell — **on 4(c) only**, and only after step 5 exited 0 and renamed the window

```sh
# THE `profile` SUB-FIELD IS WRITTEN ONLY WHERE THERE IS ONE. No
# `$CLAUDE_PROFILE_NAME` is a lane started outside the launcher, and inventing
# `unknown` for it is the same defect clause (e) refuses in the session field —
# which is the rule `lane-start` states and follows at `:1553-1558`, in this
# clause's own words: *"each sub-field is appended only where its value is
# actually in hand"*. The `:-unknown` that was here wrote the one literal the
# writer refuses, into the one cell Amendment 6(b) resumes from.
cell="→ harness <this session's uuid> (transcript uuid"
[ -n "${CLAUDE_PROFILE_NAME:-}" ] && cell="$cell; profile $CLAUDE_PROFILE_NAME"
"$L" append-session-id "$lane" "<the uuid step 4 read>" "$cell)"
```

Exit 0 → the cell now names the conversation the operator is in. **Refused → the cell is REPORTED STALE and
the act is printed verbatim; `RESTARTED` is never printed over a cell that stayed stale.**

**It is `/restart`'s act and not `lane-start`'s, and it is a step that can find its work already done.**
Under clause (d) rule 1 as corrected, `lane-start` takes the window's live session **unless a veto fires** —
so on the 4(c) path there are two cases and not one. Where the helper carries both reads, neither veto has
anything to fire on (step 2(b) already answered 8, so no row's cell names this session; and the window's name
is not yet the lane, because `lane-start` renames it a hundred lines **after** step 3b), and `lane-start`
performs Amendment 6(c)'s append **itself** — step 6 then finds the cell already naming this session and
appends nothing. Where the helper does **not** carry them, `lane-start` leaves the cell alone and step 6 is
the act that extends it: a helper predating `session-lane` exits 2 and the fence fails closed, which is the
state of every workstation until adoption act 0's read reaches it. Either way `/restart`
has the proof already: step 2 resolved this window to this lane out of the register, and step 4 read the
anchor out of the published cell. The cell is **appended to**, never replaced — Amendment 6(c)'s own act, so
the old id stays in the row as history.

Where the row records **no** uuid at all there is no anchor to append to: `lane-start` prints its own hint,
`/restart` passes that hint through **verbatim**, prints no `--resume` beside it, and reports the same
outcome.

## 7. The name — the last line, and the one act it ever asks for

Where the harness's record name for **this** session is not `<lane>`, the **last** line printed is:

```text
/rename <lane>
```

**Printed, never run.** There is no API to rename a running session from inside. Evidence 4: this lane's
transcript carries `customTitle: openRepoProject-1`, set once by `/rename`, while every process that resumed
it through a bare `claude --resume <uuid>` carried a **derived** record name — `openrepoproject-b9`, `-1e`,
`-27`, `-45` — and the derived name is what the statusline's `session_name` and `ListAgents` display.
Amendment 8(e)'s `SessionStart` hook prints the same line where the record's name differs from the lane, for
the session that never runs `/restart` at all. It is not a question and not a choice: there is exactly one
lane and exactly one spelling of it.

## The outcomes

A skill has no process exit status, so these are the words `/restart` prints; the helper codes it read are in
brackets, on Amendment 7(d)'s fail-closed convention. **`3` is not among them**, because `lanes-edit.sh`
already uses 3 for an unpushed commit or a rebase conflict and a code that already means something else is a
code a caller cannot act on.

| outcome | when | what is printed |
|---|---|---|
| `RESUME REQUIRED <lane>` **[0]** | 4(b) | exactly one line, `claude --resume <uuid>`, and stop. Nothing is written. |
| `RESTARTED <lane>` **[0]** | 4(a) with step 5 at 0; or 4(c) with step 5 at 0 **and** step 6 extending the cell | the lane, the window, the directory, and the `claude` command step 5 printed and `/restart` did not run. On 4(c), two further lines: that the recorded session has no transcript here, naming Amendment 8(d)'s deferral, and that the cell now names this session |
| `RESTARTED <lane>, CELL STALE` **[8]** | step 5 at 0, but step 6 was refused **or** the row records no uuid to anchor to | everything the `RESTARTED` row prints, plus the exact `append-session-id` act verbatim and which of the two cases it is. **8**, not 0: the bind happened and one fact is still missing |
| `NO LANE FOR THIS WINDOW` **[8]** | **every** rung of step 2 answered **8** or **2** | the per-repo listing, and `lane-start --no-launch <repo> <n>` filled in from the window's own name where it parses |
| `REFUSED: <reason>` **[2]** | no tmux, no directory, a `<lane>` the register does not carry, or step 5 exited 2 | the reason, and the helper's own stderr verbatim |
| `REFUSED: <reason>` **[1]** | any other non-zero from any helper, step 4's read included | which read failed, and its stderr |

**Step 3b's fence is TWO VETOES and no permission, and `/restart` never trips either.** When step 5 runs
`lane-start --no-launch`, that script decides whether to learn the uuid live in this window. Its fence is the
**register veto** — a uuid that belongs to another row is never taken, read through `session-lane` and
fail-closed — and the **window-name veto**: a window named for another lane never lends its session. Neither
the window's name being the lane nor `live-holder` answering `here` is a *condition for taking*, because at
step 3b the window is usually still called `claude` and there is no holder here (`R-A11-12`, which corrects
`R-A11-1` a second time). `/restart` reaches step 5 only after step 2 resolved this window to this lane out
of the register and step 4 compared the ids, so by then neither veto has anything to fire on — which is why
step 6 is `/restart`'s act and not `lane-start`'s.

**A live FORK of this lane's transcript is a defect, and it is named wherever this skill meets one**
(ratified decision 8(e), from Evidence 6). `"$L" forks <lane>` lists them, one `<uuid> <pid> <kind> <cwd>`
per fork. A fork is never the holder and must never write the register, and the ONE act is clause (k) rule
(e)'s — **`lane-end <lane> --retire <pid|uuid>`**, typed by a person. It is the DOOR to Amendment 6(d)'s
retire act, not a record of one: it proves the pid or uuid is this lane's live fork and prints 6(d) filled
in — the `/rename <lane> · retired <date>` for a session with a prompt, 6(d)'s *"an idle background session
still holding a lane name is ended"* for a `kind: bg` holder that has none. It writes **nothing** (a
`RETIRED` carrying a payload would be a seventh edit to in-force text, and Amendment 7(b) gives that verb
none) and it does **not** kill the process, because ending somebody's process is not a tool's act
(Amendment 8(f)). This skill used to print `kill <pid>` here, which is the act the ruling says neither
surface prints.

**`/restart` binds a window. It does not choose a conversation.** Those are two questions and this skill
answers only the first; the second is Amendment 6(b)'s and stays there.
