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

- **It never runs the launcher and never resumes anything itself.** `restart <lane>` is the outside half and
  it `exec`s; a session cannot exec a launcher over itself, so this one binds the window and prints.
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
```

## 1. The window

```sh
tmux display-message -p '#{session_name}:#{window_index} #{window_id} #{window_name}'
```

**No tmux → REFUSED**, naming the manual act: `lane-start --no-launch --dir <path> <lane>`. This skill binds
a **window**; with no window there is nothing to bind.

## 2. The lane

**With a `<lane>` argument, SKIP THIS STEP ENTIRELY and go to step 3 with that lane** — the operator's word
beats every inference, exactly as `--lane` does at clause (b)'s precedence 1 (decision 7 point 6). Check only
that the register has a row for it (`"$L" register-row <lane>`, exit 0); a lane the register does not carry
is a **REFUSED** naming `lanes`.

With no argument, four rungs, **first answer wins, and every one of them is an exact match**:

```sh
# (a) THE WINDOW'S OWN NAME. `lane-start` is the only thing that ever writes it,
#     so the name is a statement of intent in the way `--lane` is.
lane=""
win_name="$(tmux display-message -p '#{window_name}')"
LANES_NO_FETCH=1 "$L" register-row "$win_name" >/dev/null 2>&1 && lane="$win_name"

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
[ -n "$lane" ] || lane="$(LANES_NO_FETCH=1 "$L" session-lane "$CLAUDE_CODE_SESSION_ID" 2>/dev/null)" || lane=""

# (c) THE WINDOW THE OPERATOR IS STANDING IN, out of the swap records. The
#     `<@id>` first and the `<session>:<index>` second, and either only where
#     that window still exists — `window-lane` owns that fence AND the rule that
#     a record carrying an `<@id>` is matched on its ref only where the window
#     now holding that ref reports that same id. Three callers, one
#     implementation: this skill, the launcher's precedence 3 and `/lane-swap`.
if [ -z "$lane" ]; then
  wid="$(tmux display-message -p '#{window_id}')"
  lane="$(LANES_NO_FETCH=1 "$L" window-lane "$WS" "$wid" 2>/dev/null)" || lane=""
  [ -n "$lane" ] || lane="$(LANES_NO_FETCH=1 "$L" window-lane "$WS" "$(tmux display-message -p '#S:#I')" 2>/dev/null)" || lane=""
fi

# (d) NOTHING MATCHED — PRINT THE PER-REPO LISTING AND STOP (decision 7 point 6).
#     This replaces the first draft's one confirmation on the workstation's
#     newest swap, which on a real estate offered the wrong lane.
if [ -z "$lane" ]; then
  root="$(git rev-parse --show-toplevel 2>/dev/null)"
  origin="$(git -C "${root:-.}" remote get-url origin 2>/dev/null | sed -E 's#\.git$##; s#^git@[^:]+:##; s#^ssh://[^/]+/##; s#^https?://[^/]+/##')"
  LANES_NO_FETCH=1 "$L" lanes ${origin:+--repo "$origin"} ${root:+--dir "$root"}
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
dir="$(LANES_NO_FETCH=1 "$L" lane-dir "$lane" 2>/dev/null)" || dir=""
[ -n "$dir" ] || dir="$PROJECTS_ROOT/${lane%-*}"      # 8 → the default; nothing is backfilled
```

**Not a directory → REFUSED**, naming `--dir`. A restart that lands in the right transcript and the wrong
directory loses the repository's `CLAUDE.md` and the lane's memory, silently (Evidence 3).

## 4. The decision — **before** anything is written

```sh
row="$(LANES_NO_FETCH=1 "$L" register-row "$lane")"
cell_last="$(LANES_NO_FETCH=1 "$L" last-session "$lane" 2>/dev/null)" || cell_last=""
```

Compare `$cell_last` with `$CLAUDE_CODE_SESSION_ID`:

- **(a) they MATCH, or the cell names no uuid → step 5.**
- **(b) they DIFFER and a transcript for `$cell_last` is in the lane's directory** →
  **print exactly `claude --resume <uuid>` and STOP.** Nothing appended, no window renamed, no stamp, no
  object line. Outcome `RESUME REQUIRED <lane>` **[0]**.
- **(c) they DIFFER and that uuid has no transcript here → step 5**, and step 5's report says so and names
  Amendment 8(d)'s deferral.

**THE DECISION COMES BEFORE THE BIND, AND THAT IS `R-A11-2`.** Binding first and comparing after makes the
comparison a **tautology**: `lane-start --no-launch` performs step 3b and the `append-session-id` itself, so
the cell's last id after it is by construction this session's, and the `RESUME REQUIRED` outcome could fire
only where that append had been **refused** — the one place printing an old uuid is wrong. Comparing first
also refuses the contamination clause (d) rule 1 names: a session that is not the lane's lineage must not
rename the lane's window or stamp its row on the way to telling the operator where the lane actually is.

## 5. The bind

```sh
lane-start --no-launch --dir "$dir" "$lane"
```

It renames the window, writes the row stamp, Amendment 6(c)'s session-cell append where it can prove the
window is the lane's, the lane's `RESUMED` object line with clause (c)'s `dir`, `profile` and `window`
sub-fields, and the handoff's Rule 3 stamp — and it prints the `claude` command on stdout.
**`/restart` does NOT run that command.**

## 6. The cell — **on 4(c) only**, and only after step 5 exited 0 and renamed the window

```sh
"$L" append-session-id "$lane" "<the uuid step 4 read>" \
  "→ harness <this session's uuid> (transcript uuid; profile ${CLAUDE_PROFILE_NAME:-unknown})"
```

Exit 0 → the cell now names the conversation the operator is in. **Refused → the cell is REPORTED STALE and
the act is printed verbatim; `RESTARTED` is never printed over a cell that stayed stale.**

**It is `/restart`'s act and not `lane-start`'s, and the reason is mechanical.** Under clause (d) rule 1
`lane-start` proves ownership by the window's **name** or by `live-holder` answering `here`; on the 2(c) path
the rename is `lane-start`'s own act a hundred lines **after** step 3b, so it correctly declines. `/restart`
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

**A live FORK of this lane's transcript is a defect, and it is named wherever this skill meets one**
(ratified decision 8(e), from Evidence 6). `"$L" forks <lane>` lists them. A fork is never the holder and
must never write the register; retiring one is `kill <pid>`, typed by a person, because ending somebody's
process is not a tool's act (Amendment 8(f)).

**`/restart` binds a window. It does not choose a conversation.** Those are two questions and this skill
answers only the first; the second is Amendment 6(b)'s and stays there.
