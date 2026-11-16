---
name: handoff
description: "/handoff (aliases /swap, /lane-swap; /ctx is /handoff --restart) hands this lane off — for a context clear, a usage reset, a profile switch, or a handoff another place requested. It fixes the identity triple, refreshes the handoff with a fresh Rule 3 top block listing every running writer, polls the writers, writes the PAUSED record with the window, the lane's directory, the profile, the agent and its transcript, and prints the one restart command (lane-collision-protocol Amendment 8(a), amended by Amendments 11, 17 and 18(d))."
---

<!-- PROMPTS TO THE PERSON: 1 — step 3, and only when a writer still holds
     unpushed work and has not replied. It was 3 before A8 Addendum 2 (R-A8-7):
     the identity fix, the row's leading state word and the restart command are
     all DERIVED here now, and step 5 prints one command, never a menu. If a
     step below cannot derive something, it stops and says so — it does not ask. -->

# `/handoff` — hand this lane off (the swap, the context clear, the handoff)

Lane-collision-protocol **Amendment 8(a) as Amendment 17(a) names it**: *"the act Amendment 8(a) calls the
swap is the HANDOFF"*. One act, three names — `/handoff` here, `/swap` and `/lane-swap` as its aliases, and
`lane-handoff` on `PATH` for the same steps from a shell. What differs between a context clear, a usage
reset, a profile switch and handing the lane to someone else is only WHY, and the record's free text has
always carried that.

**For `/ctx` or `--restart`, use this bounded legacy path instead of the ordinary
preservation sequence below.** Resolve the lane read-only, then run
`lanes-edit.sh legacy-restart-check <lane>` before renaming anything, updating a
handoff, messaging writers or writing lane state. Refuse managed ownership and
unreadable ownership; feature 001 owns those lanes. Collect the running writers'
worktree/branch/brief facts into a temporary TSV (`<worktree><TAB><brief>`) without
editing the canonical handoff. After the ownership check, ask those writers to
commit and push as this skill normally requires. Invoke `lane-handoff --restart
--lane <lane> --writers-file <temporary TSV> clear` once. Follow its refusal or
supervisor output; do not execute steps 1–5 as independent canonical writes, and
do not run a second tmux respawn recipe. The backend reserves `preparing` before
all preservation writes and completes that reservation as `pending` before respawn.

This compatibility path owns `restart-intent.yaml` only. It does not use PR #97's
lifecycle snapshot as a state or counter authority, and does not mutate the managed
JSON ledger. A failed restart recovers through the same-operation supervisor;
ordinary lane resume refuses it. A live or unknown child leaves `starting` and
blocks retry even if the supervisor was terminated.

**The other flags run the ordinary steps 1–5 below.** Their ends differ as follows:

| | what it adds after the record | when |
|---|---|---|
| `/handoff [why]` | nothing — the restart line is printed and the person types it | a swap, a reset, a switch |
| `/ctx`, `/handoff --restart` | the lane's own pane is respawned through the launcher, the new session's first prompt being this handoff's top block (Amendment 17(f)) | a context clear: *"the one word is the whole act"* |
| `/handoff --exit [requested by …]` | `/exit` is typed into this lane's own pane, because a handoff to ANOTHER PLACE is a handoff and not a restart (Amendment 18(d)) | the bound session answering another place's `HANDOFF-REQUESTED` |
| `lane-handoff --late --at <UTC>` | nothing — it writes the record a swap NEVER LEFT, from a shell, BEFORE the relaunch | a session that died at a usage limit with no swap |

**A `/ctx` WHOSE RECORD COULD NOT BE WRITTEN REFUSES BEFORE IT KILLS ANYTHING** (Amendment 17(f)): a pane is
never respawned over an unrecorded lane, and a session is never ended without one.

Run every step, in order, before telling the operator it is safe to reset usage or switch profiles. `$L`
below is `lanes-edit.sh` on `PATH` — `openRepoTools --install` puts it there — else the symlink Amendment 5
left in place, which is how `/restart` finds it; every command is copy-pasteable as written once `lane` is
derived in step 1. **From a shell, `lane-handoff` is these same steps as one command** — it is the same act
and writes the same record; a session runs the steps here because a session can message its subagents and a
shell cannot.

```sh
L="$(command -v lanes-edit.sh || printf '%s' ~/projects/xFactory/lanes-edit.sh)"

# EVERY READ IN STEP 1 GOES THROUGH THIS ONE FENCE, and Amendment 7(d) is the
# whole of it: `0` an answer · `8` NO ANSWER · `2` a helper predating the read —
# both of those fall to the next rung, save the one `2` that is a REFUSAL (the
# paragraph on `2` below) — and ANYTHING ELSE is a read that FAILED, which is
# neither of them (#26, the review of `c3ebcfe`, this file's `:28` and `:72`).
# The one code asked a second time before it is any of these is `69` (the
# paragraph on `69` below).
# All three of step 1's reads collapsed every code into the ordinary case, and
# what is beneath them is not a refusal: it is THE NEXT RUNG, and the last rung
# is the workstation's NEWEST SWAP — a different lane. A register that could
# not be read is not "this window is not a lane", and step 4 would then write a
# PAUSED record, a stamp and a restart command for a lane this window is not.
#
# IT IS `/restart`'s `lread` WITH THREE DIFFERENCES, STATED RATHER THAN LEFT TO
# BE FOUND. Step 4's `dir` read does NOT come through here, because this fence
# STOPS and that read may not — `R-A11-11`, *a swap is never left unwritten*.
# It drops the sub-field and names the read instead, where it stands. An exit 2
# carrying Amendment 15(d)'s words is a REFUSAL here (the paragraph on `2`
# below), where `lread` still reads every 2 as no answer. And a 69 is asked
# again from the mirror (the paragraph on `69` below), where `lread` does not.
#
# IT SETS A VARIABLE RATHER THAN PRINTING ITS ANSWER, and that is load-bearing:
# a refusal inside `$( )` kills only the substitution's subshell and the skill
# would carry on with an empty answer.
#
# AND `2` IS TWO ANSWERS (#72 item 8; `lane-handoff`'s own fence took it in
# Copilot round 2 on openRepoTools#47, and this is that fence's rule). It is
# what a helper predating a subcommand spends on an unknown one — the rung this
# fence falls through for — and it is ALSO `canon_lane`'s refusal of a register
# holding two rows that differ only by case (Amendment 15(d)), which every read
# that takes a lane name now carries. Falling through THAT is binding this
# window to whichever lane the next rung happens to answer with, and then
# renaming the window and writing a PAUSED record and a restart command for it.
# So the refusal is asked for BY ITS OWN WORDS — no old helper emits them from
# an unknown subcommand, which is how `lane-handoff`, `lane-start`, `lane-end`
# and `lane` tell the two apart — and relayed, with the fall-through for a
# genuinely old helper left as it was. The words come from asking the same read
# a second time with only its stderr kept, as `lane-handoff` does: the first
# answer's stderr is discarded, and asking a read twice changes nothing.
#
# AND `69` IS A THIRD ANSWER, which `*)` below used to refuse (design.md, "The
# callers' default arms", the `sread` row; feature 007, T406): the register's
# database could not be reached. A handoff must still be written with it down
# (`R-A11-11`), and the reads that NAME THE LANE before the handoff file is
# published read the mirror (YS:692), so those run with `LANES_READ_MIRROR=1`
# — `register-row`, `window-lane`, `swapped` and `canon-lane` through this fence
# in step 1, and `register-row`, `handoff-path` and `write-handoff` in step 2,
# where their calls carry it. A 69 from a read through this fence is then
# re-read ONCE with that variable set, whichever verb it came from, so a door
# that answers 69 to the first call still has the mirror asked. The
# re-read is held to the same rule as any read: `0` an answer, `8` no answer,
# and ANYTHING ELSE — a second 69, which is what a verb answers that the design
# has `lanes-edit.sh` not read from the mirror — is a read that FAILED and
# refuses here with the words `*)` uses, naming both codes. A 2 carrying
# Amendment 15(d)'s words is that refusal and its exit 2, as above.
#
# AND THE MIRROR SAYS SO. A read that answers from the mirror prints
# `read: mirror at <sha12>, …` on stderr, and this fence hides stderr, so it
# keeps the file the call's stderr went to and forwards the lines that begin
# `read: mirror at ` and nothing else (the shape `/restart`'s `lread` takes for
# its own stream), from the first call, or from the re-read where there was
# one. Where no file can be made the stream is hidden as before.
#
# AND IT REMEMBERS THAT IT READ THE MIRROR, in `mirror_read`, which it sets to
# `1` where it forwarded a label or re-read a 69, with a label printed or not,
# and never clears. It is the one fact this skill has of having read the mirror
# (lane 3's rulings on #165, 6754439281 item 5 and 6754607466, which make it the
# rule `lane-handoff` follows for `kept_block_say`), and step 1 prints it, for
# block 2's printed call to name `LANES_READ_MIRROR=1` by.
sread() {                      # sread <var> "<what the failure is NOT>" <verb> [args…]
  sr_var="$1"; sr_not="$2"; shift 2
  sr_out=""; sr_rc=0
  sr_err="$(mktemp "${TMPDIR:-/tmp}/handoff-sread.XXXXXX" 2>/dev/null || printf '')"
  sr_out="$(LANES_NO_FETCH=1 "$L" "$@" 2>"${sr_err:-/dev/null}")" || sr_rc=$?
  if [ -n "$sr_err" ]; then
    if [ "$sr_rc" -ne 69 ] && grep -e '^read: mirror at ' -- "$sr_err" >&2; then mirror_read=1; fi
    rm -f -- "$sr_err"
  fi
  case "$sr_rc" in
    0)   : ;;
    69)  sr_rc=0; sr_why=""; mirror_read=1
         sr_err="$(mktemp "${TMPDIR:-/tmp}/handoff-sread.XXXXXX" 2>/dev/null || printf '')"
         sr_out="$(LANES_READ_MIRROR=1 LANES_NO_FETCH=1 "$L" "$@" 2>"${sr_err:-/dev/null}")" || sr_rc=$?
         if [ -n "$sr_err" ]; then
           grep -e '^read: mirror at ' -- "$sr_err" >&2 || :
           sr_why="$(cat -- "$sr_err" 2>/dev/null || :)"
           rm -f -- "$sr_err"
         fi
         case "$sr_rc" in
           0) : ;;
           8) sr_out="" ;;
           *) case "$sr_rc:$sr_why" in
                2:*"Amendment 15(d)"*)
                  printf 'REFUSED: `%s %s` says the register holds two rows for this lane that differ only by case, so no read of it is unambiguous and this skill will not pick one (Amendment 15(d)). It will not bind a lane, rename the window, write a PAUSED record or print a restart command; merge the two rows by hand first. The helper said:\n%s\n' \
                    "$L" "$1" "$sr_why" >&2
                  exit 2 ;;
              esac
              printf 'REFUSED: `%s %s` failed (exit 69, then exit %s from the mirror). That is NOT %s — a read that failed is never an answer (Amendment 7(d)), and this skill will not bind a lane, write a PAUSED record or print a restart command on one. Run it by hand to see what it says.\n' \
                "$L" "$1" "$sr_rc" "$sr_not" >&2
              exit 1 ;;
         esac ;;
    2)   sr_why="$(LANES_NO_FETCH=1 "$L" "$@" 2>&1 >/dev/null || :)"
         case "$sr_why" in
           *"Amendment 15(d)"*)
             printf 'REFUSED: `%s %s` says the register holds two rows for this lane that differ only by case, so no read of it is unambiguous and this skill will not pick one (Amendment 15(d)). It will not bind a lane, rename the window, write a PAUSED record or print a restart command; merge the two rows by hand first. The helper said:\n%s\n' \
               "$L" "$1" "$sr_why" >&2
             exit 2 ;;
         esac
         sr_out="" ;;
    8)   sr_out="" ;;
    *)   printf 'REFUSED: `%s %s` failed (exit %s). That is NOT %s — a read that failed is never an answer (Amendment 7(d)), and this skill will not bind a lane, write a PAUSED record or print a restart command on one. Run it by hand to see what it says.\n' \
           "$L" "$1" "$sr_rc" "$sr_not" >&2
         exit 1 ;;
  esac
  eval "$sr_var=\$sr_out"
}
```

**THE WHY IS ONE LINE, AND IT IS REFUSED BEFORE STEP 1** (`opensoft/openRepoTools#85`; `lane-handoff` took
the same refusal in #218). `$why` below is the operator's words, verbatim: the `[why]` of `/handoff [why]`.
It reaches step 2's top block, where a line break writes a malformed prompt (a `---` line is where
`lane-start` ends the prompt it hands the next session), and step 4's object-log `PAUSED` line and register
line, two files nothing rewrites. Both of those writers refuse a newline or a carriage return before they
write, but step 4 runs after step 2 has refreshed and committed the handoff, so a refusal there would end the
act with a top block and no record behind it. So the test is made here, before step 1 renames anything and
before anything is written. It is the test `lane-handoff` makes right after reading its arguments, because
the skill and `lane-handoff` are one act (Amendment 17(a)) and refuse the same why. Step 4 still spells a
break `; `, as `lane-handoff`'s `sanitize` does, and that is the second line of defence, not this one. A
why the operator did not give is no why at all: it passes, and step 4 writes `handoff`. That holds in a shell
running under `set -u` too, which is why the check reads `${why-}`.

```sh
case "${why-}" in
  *$'\n'*|*$'\r'*)
    printf '%s\n' "REFUSED: the why is ONE line: it is written into the handoff's top block, the object log's PAUSED line and the register's file-level line, and a newline or carriage return in it would split each of them — the last two in files nothing rewrites. Nothing was renamed or written. Put it on one line, with '; ' where the break was, and run /handoff again." >&2
    exit 2 ;;
esac
```

## 1. Usage, then the identity triple — derived, not asked

```bash
claude-usage
window="$(tmux display-message -p '#W')"                     # Amendment 8(b): the window IS the lane
lane="$window"
mirror_read=""
# THIS READ CARRIES `LANES_READ_MIRROR=1` TOO (the paragraph on `69` above `sread`): it
# names the lane, so with the database down it reads the mirror from its first call.
LANES_READ_MIRROR=1 sread row_probe "'this window is not a lane'" register-row "$lane"
[[ -n "$row_probe" ]] || lane=""
# THE WORKSTATION COMES FROM CONFIGURATION, NEVER FROM `hostname` (Amendment 11,
# ratified decision 8(d), from Evidence 6): a forked orchestrator wrote a bench
# container's id into a register whose every other row says `Eagle`, and a row
# on a workstation that does not exist is a row no reader can match. `$L`'s own
# `workstation` read is the one implementation; its second tab-separated field
# says which rung answered.
ws_pair=""; ws_rc=0
ws_pair="$("$L" workstation 2>/dev/null)" || ws_rc=$?
ws="${ws_pair%%	*}"
# AND IT NEVER WRITES A PLACEHOLDER (`R-A11-14`). Inside a container with no
# `LANES_WORKSTATION`, the helper's own writers refuse — `@unknown-workstation`
# is the same defect one field along from the `unknown` clause (e) refuses in
# the session field, and the log is never rewritten.
#
# WHAT STOPS IS THE REGISTER AND LOG WRITES, NOT THE SWAP (A11 Addendum 4
# ruling 11, ratified "a11 addendum 4 yes"). This step used to `exit 2` HERE,
# before the handoff refresh, the subagent poll, the register line and the
# printed restart command — so a container with no workstation lost the one
# thing a swap exists to leave behind. Clause (k) rule (d)'s cost is *"until the
# value is exported, every lane write from a container stops"*, and that is the
# register and the logs; step 2's handoff is written by `write-handoff`, in the
# lane's own checkout (Amendment 23 S2), and that verb is not one of the writes
# the helper refuses for want of a workstation. Clause (e)'s shape for a fact a writer
# cannot carry is *"the gap named in the handoff"*, and that is what happens
# here: `$ws_missing` is carried to step 2, which names it, and to step 4, which
# skips (a), (b) and (c) alike — every register and log write.
#
# AND A HELPER PREDATING THE READ IS NOT A CONTAINER (#26, the review of
# `29d3417`, this file's `:70`). `workstation` is one of Amendment 11's reads,
# so a `lanes-edit.sh` that has not taken adoption act 3's install exits **2**
# from its unknown-subcommand arm and prints nothing — and `-z "$ws"` then told
# the operator of a perfectly ordinary host that they were in a container with
# `$LANES_WORKSTATION` unset, which is a sentence they cannot act on. Until the
# install reaches every workstation, **2 is the answer every one of them gives**
# (`R-A11-8`), so this is the common case and not the corner.
#
# THE OUTCOME IS THE SAME AND THE REASON IS NOT. The writes still stop, for the
# same reason they stop in a container: `$ws` is written into the PAUSED line's
# payload and into `session <uuid>@<ws>`, and a record filed under nothing is
# the placeholder `R-A11-14` refuses. What changes is that the gap is named
# truthfully and the act that closes it is the install rather than an export.
ws_missing=""
if [[ "$ws_rc" != 0 && "$ws_rc" != 8 ]] && [[ -z "$ws" ]]; then
  ws_missing=1
  echo "NO WORKSTATION READ: \`$L workstation\` exited $ws_rc and named none. Exit 2 is a lanes-edit.sh predating Amendment 11 — expected, and every workstation gives it until adoption act 3's install reaches it (\`R-A11-8\`); anything else is a read that failed. Either way this skill will not write a record filed under no workstation (\`R-A11-14\`), so the register and object-log writes of step 4 are NOT made and the row is NOT flipped. The swap itself goes on: the handoff is refreshed and NAMES this gap, and the restart command is still printed, with --lane. To close it: openRepoTools --install, then re-run step 4."
elif [[ "${ws_pair##*	}" == container-unset || -z "$ws" ]]; then
  ws_missing=1
  echo "NO WORKSTATION: this is a container and \$LANES_WORKSTATION is not set. The register and object-log writes of step 4 will NOT be made — a record filed under a container id is a record no restart of any workstation will ever find, and both logs are append-only (\`R-A11-14\`). The swap itself goes on: the handoff is refreshed and NAMES this gap, and the restart command is still printed — with --lane, because the row is NOT flipped either and a restart cannot resolve this lane from a row that was never written. The workBenches launcher exports the value into every session it starts and \`wave-container-shell.sh\` into every container it opens; to close the gap now: export LANES_WORKSTATION=<this host name> and re-run step 4."
fi
if [[ -z "$lane" ]]; then
  # AMENDMENT 11 CLAUSE (b) INSERTS A STEP BETWEEN THE NAME AND THE RECORD, AND
  # THIS SKILL TAKES IT TOO (clause (h): one read, three callers). `window-lane`
  # answers "the lane bound to THIS window of THIS workstation" — the register
  # row whose name is the window's name, else this workstation's swap record
  # whose `window` sub-field names this window's `<@id>` or its
  # `<session>:<index>`, and only where that window still exists. Without it the
  # skill and the launcher disagree in precisely the case the new step exists
  # for: a window whose name is gone but whose record names it.
  # 0 is a lane, 8 is none, and 2 is a `lanes-edit.sh` predating Amendment 11 —
  # expected and silent, and a fall to the next rung rather than a refusal.
  #
  # THIS NAMING READ, AND `swapped` BELOW, CARRY `LANES_READ_MIRROR=1` (the
  # paragraph on `69` above `sread`), AS DO THE OTHER READS OF THIS STEP: they
  # name the lane before the handoff file is published, so with the database
  # down they read the mirror and the handoff is still written (`R-A11-11`). The
  # variable is set for the one call and nothing after it sees it.
  wl_ref="$(tmux display-message -p '#{window_id}' 2>/dev/null)"
  [[ -n "$wl_ref" ]] || wl_ref="$(tmux display-message -p '#S:#I' 2>/dev/null)"
  LANES_READ_MIRROR=1 sread candidate "'no lane is bound to this window'" window-lane "$ws" "$wl_ref"
  [[ "$candidate" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*$ ]] && lane="$candidate"
fi
if [[ -z "$lane" ]]; then
  # The swap record, read exactly as the launcher reads it: the STATUS decides
  # whether there is an answer at all, and the contract is the tab. A row that
  # printed before a failed read, or one with no tab, is not a record row —
  # `cut -f 1` would hand back the whole line, lane-shaped and wrong.
  LANES_READ_MIRROR=1 sread rows "'this workstation has no swap record'" swapped "$ws"
  first="$(printf '%s\n' "$rows" | head -n 1)"
  if [[ -n "$rows" && "$first" == *$'\t'* ]]; then
    candidate="${first%%$'\t'*}"
    [[ "$candidate" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*$ ]] && lane="$candidate"
  fi
fi
# ONE NAME UNDER ANY CASE, WHICHEVER RUNG ANSWERED (Amendment 15; #72 item 8).
# Rung 1 reads the window's name through `register-row`, which resolves it
# through `canon_lane` and so refuses a register holding two rows that differ
# only by case. Rungs 2 and 3 answer with a record's lane field and the swap
# row's first cell, and nothing above reads either through the resolver, so a
# lane a case twin makes ambiguous bound from them. The bound name is therefore
# read once more, here, through `canon-lane` and the fence — `lane-handoff`'s
# own step after its rungs — before anything is renamed or written. Its 15(d)
# exit 2 refuses through the fence, an old helper's 2 keeps the name as it is,
# a read that failed stops the skill as every failed read does, and its answer
# is the register row's spelling, which the rename, the record and the restart
# line then carry. It is NOT a check that the lane has a row: `canon_lane`
# answers a name no row matches with the name as typed.
if [[ -n "$lane" ]]; then
  LANES_READ_MIRROR=1 sread lane_canon "'this lane has no row'" canon-lane "$lane"
  [[ "$lane_canon" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*$ ]] && lane="$lane_canon"
fi
printf 'lane=%s\n' "${lane:-<none>}"
# Printed only where `sread` forwarded a mirror label or re-read a 69, for block 2 to be given.
[[ -z "$mirror_read" ]] || printf 'mirror_read=%s\n' "$mirror_read"
```

The window name answers first, the window's own RECORD second and the workstation's newest swap third —
the launcher's own order, with Amendment 11 clause (b)'s new zero-question step in the middle, so the skill
and the launcher never disagree about which lane this is. Whichever of the three answered, the name is then
read once more through `canon-lane`, as `lane-handoff` does: a register holding two rows for it that differ
only by case refuses there, and the row's own spelling is the name used below. Then make the other two names
match it, mechanically:

- window name ≠ lane → `tmux rename-window "$lane"`;
- Claude session name ≠ lane → type `/rename <lane>` (Amendment 2: the session name is the lane's
  messaging address).

If `lane` is empty, **nothing binds this window**. Stop, and print the command FILLED IN — the repo and
the number are the window's own name split on its last `-` (clause (e) does the same, for the same reason:
nobody should have to translate a placeholder at the one moment they are trying to get back to work):

```bash
case "$window" in
  *-[0-9]*) printf 'run: lane-start --no-launch %s %s\n' "${window%-*}" "${window##*-}" ;;
  *)        printf 'run: lane-start --no-launch REPO N; this window is named "%s", which is not a lane name, so the repo and the number have to come from the operator\n' "$window" ;;
esac
```

Only the second branch leaves anything blank, and it leaves it blank because nothing here knows it.

## 2. Refresh the handoff

The handoff is written by ONE call, `lanes-edit.sh write-handoff --prepend` (Amendment 23, S2–S4), and this
skill holds no lock and runs no `git` of its own. Under the lane checkout's lock the verb brings that
checkout to origin, reads the handoff there, puts the new top block, a `---` line and a blank line in front
of it, proves byte for byte that the block and the old file both survive, replaces the file atomically
under the workstation's sidecar lock, commits it by its own pathspec with the Rule 5 `Lane:` trailer,
pushes with no pull, reads origin back, and replays the one write on a refused push. It refuses an active
restart owned by another operation. So the order below is: say where the handoff is, write the new top
block, and only it, to a temporary file, then run the block under "THE WRITE IS ONE CALL", which makes the
one call. Do not edit or redirect into the canonical handoff directly, do not write the complete new file
by hand, and do not commit it: the verb is the commit.
Legacy `rename-lane` is a separate four-file transaction under the workspace's writer mutex;
it refuses unfinished/failed restart ownership and uses EXIT rollback. Its
stamp now atomically replaces the handoff through a temporary file beside it
(#158), but the four-file rename itself is still not crash-atomic (#224).


The handoff path is the row's own handoff column. Derive it; do not guess it — and read the row FETCHED,
because this decides state (Amendment 7's read-after-fetch rule governs it; step 1's window/record probe is
the only no-fetch read this skill makes):

```sh
# THIS READ CARRIES `LANES_READ_MIRROR=1` (the paragraph on `69` above `sread`), AND IT HAS NO `sread` TO
# FALL BACK ON: with the database down, a 69 here is no row, and the handoff below is never located.
row="$(LANES_READ_MIRROR=1 "$L" register-row "$lane" 2>/dev/null | grep '^|' | tail -n 1)"
# The handoff path is the row's SIXTH column: awk field 7, because $1 is the empty string before the
# leading pipe — lanes-edit.sh's own row_cell/handoff_of_lane convention. NEVER count back from NF: this
# lane's own row alone carries 27 fields today, every extra one of them in the state history to the RIGHT
# of the handoff column, so `$(NF-2)` landed on the empty string and this step used to `git add ""` and
# commit nothing — silently, in the one step Amendment 6(e) exists for.
handoff="$(printf '%s' "$row" | awk -F'|' '{print $7}' | awk '{$1=$1};1')"
uuid="$(printf '%s' "$row" | awk -F'|' '{print $3}' \
  | grep -o '[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{12\}' | tail -n 1)"
# THE SESSION'S OWN ID COMES FIRST AND THE ROW'S SECOND, which is `lane-handoff`'s
# order (*"THE SHELL'S OWN SESSION BEATS THE RECORD"*) and `R-A11-5`'s premise: *"a
# swap taken by a running session always has a uuid: `$CLAUDE_CODE_SESSION_ID` is
# it"*. It is shape-checked, as the launcher's window exports and
# `$CLAUDE_PROFILE_NAME` are in step 4.
sid_re='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
[[ "${CLAUDE_CODE_SESSION_ID:-}" =~ $sid_re ]] && uuid="$CLAUDE_CODE_SESSION_ID"
printf 'handoff=%s\nuuid=%s\n' "${handoff:-<none>}" "${uuid:-<none>}"
# WHERE NEITHER ANSWERS, THE LANE HAS NEVER HAD A SESSION RECORDED, and `R-A11-5`
# (A11 Addendum 1, F7) has the skill SAY SO BEFORE IT WRITES, naming the act that
# supplies one: the writer's own refusal is the guard behind this one, and the
# caller who would meet it is mid-swap with a session about to die. IT IS ASKED
# OF A ROW THAT WAS READ — a read that failed is no row recording nothing
# (Amendment 7(d)), and that case is the `$handoff` stop below. THE SWAP GOES ON,
# as `ws_missing`'s does (*a swap is never left unwritten*, `R-A11-11`):
# `$uuid_missing` is carried to the handoff below, which names the gap, and to
# step 4, which skips the two writes that name a session. A `session_…` footer id
# is no uuid, here as to the writer, and reads as none.
uuid_missing=""
if [[ -n "$row" && -z "$uuid" ]]; then
  uuid_missing=1
  # SPLIT BY PARAMETER EXPANSION, AS STEP 1 DOES: zsh, a session's own shell,
  # fills `$match` and not `BASH_REMATCH`, so a split read from the match would
  # print this command with both fields empty.
  uuid_fix='lane-start --no-launch <repo> <n>'
  [[ "$lane" =~ ^.+-[0-9]+$ ]] && uuid_fix="lane-start --no-launch ${lane%-*} ${lane##*-}"
  uuid_cell="while the row's state cell still is"
  [[ -z "$ws_missing" ]] || uuid_cell="and neither is the row's state cell, for want of a workstation"
  echo "NO SESSION RECORDED: neither \$CLAUDE_CODE_SESSION_ID nor lane $lane's row carries a session uuid, so there is no session to name, and the writer refuses a \`session\` field that is not a transcript uuid (\`R-A11-5\`, clause (e)). Step 4's object-log PAUSED and register-line writes are therefore NOT made — the second would read \`session @<ws>\` — $uuid_cell. The swap itself goes on: the handoff is refreshed and NAMES this gap, and the restart command is still printed. The act that gives the lane a session is Amendment 6(c)'s session-cell append: run \`$uuid_fix\` in this lane's window, then re-run steps 2 and 4."
fi
```

If `$handoff` came back empty, **stop here** — this row does not split the way `row_cell` expects, the call
under "THE WRITE IS ONE CALL" would name no handoff while looking like it worked, and Amendment 6(e) exists
for exactly this step. Read the row's own text by hand and take its handoff token; do not guess one.

**WHERE THE HANDOFF IS, AND THE BYTES THIS WRITE IS MADE FROM.** `$handoff` is the row's own spelling, and the
check above is all this skill asks of it. The file `write-handoff` writes is `handoff-path`'s answer: that cell
translated into the lane's OWN checkout (Amendment 23 S2), derived here and never spelled. No checkout path is
written anywhere in this step, and none is taken from the environment or from the helper's workspace root as a
fallback. A read that failed is no answer (Amendment 7(d)), so nothing is guessed in its place. `--create`
makes that checkout first where this is its first use, so that there is a file to read: the session reads
it there for what its new top block carries forward. No digest is taken and no new file is built here: the
verb reads the handoff again under the lock, from what S3 has just brought from origin, and puts the block
in front of it as it is then, so a peer's block that landed meanwhile is kept under the new one, newest on
top. Where the block below prints `HANDOFF NOT FOUND` (`handoff-path`'s 8: no row, or a row
that names no handoff) there is no file to write into. Where it prints `HANDOFF READ FAILED`, the read
failed, and that is never "no handoff": every exit but 0 and 8 is one, and the line quotes it. A 2 whose words
say "unknown subcommand" is a `lanes-edit.sh` predating `handoff-path`, to be updated; a 4 is the lock that
makes the lane's checkout, and step 2 is run again. Any other 2 is a name refused, a clone that failed, or a
handoff cell the translation `handoff-path` and `write-handoff` share refuses: a handoff the row names in W
or in another checkout of the register beside it (finding 601 of lane openRepoTools-3's review of
opensoft/openRepoTools#312), a relative cell whose `.` or `..` components climb out of the lane's checkout
(602), or a path there that holds a glob character (607, which `handoff-path` refuses since 991). The file
such a cell names is not this lane's handoff, and nothing is written there, by this skill or by hand; the new
top block goes to the lane's own handoff once the row's cell is corrected to name it. In
every one of these cases the call under "THE WRITE IS ONE CALL" is not made, the new top block is still
written, to the `$block_file` the block prints, and kept whole in the report, and the swap goes on with the
gap in the report (`R-A11-11`, *a swap is never left unwritten*). Once the gap is answered, the block goes into
the handoff by the one call, `LANES_LANE=<lane> lanes-edit.sh write-handoff <lane> --prepend <block file>
--subject "<subject>"`, which the block under "THE WRITE IS ONE CALL" prints filled in, and never by a hand
edit: the handoff is the verb's to write (lane openRepoTools-3's finding 983 on #311).

```sh
# WHERE THE HANDOFF IS: derived, never spelled. `handoff-path` only reads, and `--create` makes the lane's own
# checkout first where this is its first use.
hf_rc=0; handoff_file=""; block_file=""; hf_said=""; hf_record=""
# THIS CALL CARRIES `LANES_READ_MIRROR=1` (the paragraph on `69` above `sread`): it comes before the handoff is
# published, so with the database down it reads the mirror and the handoff is still written (`R-A11-11`).
handoff_file="$(LANES_READ_MIRROR=1 "$L" handoff-path "$lane" --create)" || hf_rc=$?
# ONLY 8 IS "NO HANDOFF" (Amendment 7(d): a read that failed is no answer). 1 is a register it could not read
# (its own "R22: never 8"), 2 a name refused, a cell refused (601, 602, 607) or a clone that failed, 4 the lock
# that makes the checkout, and a `lanes-edit.sh` predating `handoff-path` says 2 from its unknown-subcommand
# arm. A 2 is asked a second time with only its stderr kept, as `sread` asks, to tell those apart: WITHOUT
# `--create`, so it is a read and clones nothing, and without the fetch.
[[ "$hf_rc" != 2 ]] || hf_said="$(LANES_NO_FETCH=1 "$L" handoff-path "$lane" 2>&1 >/dev/null || :)"
# THE NEW TOP BLOCK, AND ONLY IT, goes in `$block_file`, ending with a newline, WHATEVER THE READ ANSWERED.
# `write-handoff --prepend` puts it in front of the handoff as the verb reads it under the lock (lane
# openRepoTools-3's finding 981 on #311, option (a)); an empty `$block_file` is no block, and nothing is sent.
# Where the read failed, the file is still made: it is where the block is kept until the one call below can
# put it in the handoff, never a hand edit of the handoff (finding 983).
block_file="$(mktemp "${TMPDIR:-/tmp}/handoff-block.XXXXXX")" || block_file=""
hf_keep='Write the new top block all the same, to the block_file this block prints, and put it whole in the report: it is then the one copy, and once this is answered it goes into the handoff only by the one call LANES_LANE=<lane> lanes-edit.sh write-handoff <lane> --prepend <block file> --subject "<subject>", which the block under THE WRITE IS ONE CALL prints filled in, never by a hand edit. The swap goes on (R-A11-11).'
if [[ "$hf_rc" == 0 && -n "$handoff_file" && -f "$handoff_file" ]]; then
  printf 'handoff_file=%s\nblock_file=%s\n' "$handoff_file" "${block_file:-<none>}"
else
  case "$hf_rc:$hf_said" in
    0:*|8:*)
      printf 'HANDOFF NOT FOUND: `%s handoff-path %s --create` exited %s and named %s: the register has no row for this lane, its row names no handoff, or no file is there, so there is no handoff to write into and the call under "THE WRITE IS ONE CALL" is NOT made. %s\n' \
        "$L" "$lane" "$hf_rc" "${handoff_file:-no file}" "$hf_keep" ;;
    4:*)
      printf 'HANDOFF READ FAILED: `%s handoff-path %s --create` exited 4: another write held the lock that makes the lane checkout. The read failed, and that is not "no handoff" (Amendment 7(d)), so the call under "THE WRITE IS ONE CALL" is NOT made. Run step 2 again, from the block under WHERE THE HANDOFF IS. %s\n' \
        "$L" "$lane" "$hf_keep" ;;
    2:*"unknown subcommand"*)
      printf 'HANDOFF READ FAILED: `%s handoff-path %s --create` exited 2, and the helper says "unknown subcommand": this lanes-edit.sh predates handoff-path. The read failed, and that is not "no handoff" (Amendment 7(d)), so the call under "THE WRITE IS ONE CALL" is NOT made. Update lanes-edit.sh (openRepoTools --install installs it with this skill), then run step 2 again. %s\n' \
        "$L" "$lane" "$hf_keep" ;;
    2:*)
      # 601 (lane openRepoTools-3's review of #312, and its correction 6368669583): a row whose handoff is in W
      # or in another checkout of the register beside it, a relative cell that climbs out of the lane checkout
      # (602), and a path there with a glob character (607, `handoff-path`'s since 991) are refused by the
      # translation `write-handoff` shares with `handoff-path`, 2 with no path printed. The helper calls the
      # first "another checkout of the register" (985: never 8(d)'s "another repository"). That file is not this
      # lane's to write, by hand either; the kept block goes to the lane's own handoff once the row's cell
      # names it (983).
      printf 'HANDOFF READ FAILED: `%s handoff-path %s --create` exited 2 (its words are above): a name refused, a clone of the lane checkout that failed, or a handoff cell that handoff-path and write-handoff both refuse: a handoff the row names in W or in another checkout of the register beside it (601), a relative cell whose . or .. components climb out of the lane checkout (602), or a path there that holds a glob character (607). Where its words name such a cell, the file it names is not the handoff of this lane: nothing is to be written there, by this skill or by hand, and the new top block goes to the handoff of this lane, in its own checkout, once the handoff cell of its row is corrected to name it. The read failed, and that is not "no handoff" (Amendment 7(d)), so the call under "THE WRITE IS ONE CALL" is NOT made. %s\n' \
        "$L" "$lane" "$hf_keep" ;;
    *)
      printf 'HANDOFF READ FAILED: `%s handoff-path %s --create` exited %s (its words are above). The read failed, and that is not "no handoff" (Amendment 7(d)), so the call under "THE WRITE IS ONE CALL" is NOT made. %s\n' \
        "$L" "$lane" "$hf_rc" "$hf_keep" ;;
  esac
  # STEP 4'S REGISTER LINE SAYS THIS, and never "handoff refreshed" (rv3's SHOULD 3 on #311).
  hf_record="handoff NOT refreshed (the handoff read failed, exit $hf_rc)"
  [[ "$hf_rc" != 0 && "$hf_rc" != 8 ]] || hf_record="handoff NOT refreshed (no handoff found)"
  handoff_file=""
  # EVERY BASH CALL IS A NEW SHELL (lane openRepoTools-3's finding 984 on #311): what block 2 needs from here is
  # printed, to be set, quoted, in the shell that runs it.
  printf 'block_file=%s\nhf_record=%s\n' "${block_file:-<none>}" "$hf_record"
fi
```

`$uuid` is this session's own id — `$CLAUDE_CODE_SESSION_ID`, which a running session always has — else the
**last** id in the session cell, the only one Amendment 6(b) calls the lane's. Rewrite the handoff's state line, **every word given and not yet executed**, and the resume prompt;
a stale handoff is how given words die with the session (Amendment 6(e)).

**THE TOP BLOCK'S TEMPLATE GAINS A `WRITERS` SECTION AND A FIRST LINE** (Amendment 17(f): the block *"LISTS
EVERY WRITER THE LANE HAS RUNNING (its worktree, its branch, its brief, what it had committed)"*, as
**Addendum 1 (i)** reads that section — *"a list to COUNT, not a list to relaunch"*, in force 2026-09-14T20:59:31Z).
Write it exactly this shape, and prepend it — a handoff is the one document in this protocol whose purpose is
to be read by a later session, so nothing below is rewritten and everything already there stays as history
under a `---` rule. Write the block, and nothing else, to the `$block_file` the block above printed, and end
its last line with a newline; `write-handoff --prepend` puts it in front of the old file, so the history is
never retyped:

```text
Lane: <lane> (<profile>, session <uuid>) — single-use resume prompt: stamp RESUMED-by before acting (lane-collision-protocol rule 3)

## RESUME PROMPT — PAUSED <UTC> (<why>), agent <agent>, transcript <id|none>, kind <in-process|respawn|unknown> — <the kind's expectation, from the table below>

**FIRST ACTS, in order.** (1) You are lane `<lane>` in tmux window `<window>`, checkout `<dir>`. Stamp this
block RESUMED before anything else (Rule 3, single use). (2) Read AGENTS.md, then this block. (3) COUNT THE
LIVE WRITERS before relaunching anything — the WRITERS section below is a list to COUNT, not a list to
relaunch (Addendum 1 (i)). ONE WORKTREE, ONE WRITER (k): a worktree is one writer's for as long as that
writer is live, a relaunch onto a live writer's worktree is the writers' form of Amendment 18(h)'s second
binding, and where you find one made you retire the newer before either commits. <the kind's own sentence,
from the table below.> Older sections below are history.

**STATE at <UTC>.** <what is true, what is owed, every word given and not yet executed> Kind `<kind>`: <its
sentence>.

**WRITERS at <UTC>** (<n> found under `<dir>`) — FIRST count the live writers: `ListAgents` in Claude, the agent's equivalent elsewhere. A writer still live OWNS its worktree: do not relaunch it; one message telling it that its in-flight call died and who the coordinator now is, is enough. Relaunch only a writer that is NOT live, from where it stands — `git status` and `git log @{u}..` in its worktree, then its brief. WHERE THE COUNT AND THIS LIST DISAGREE, THE COUNT WINS: this list is what the paused session expected, the count is what is true.

- `<worktree>` — branch `<branch>`, last commit `<sha> <subject>`, <n> dirty, <m> unpushed; brief: <the brief that writer was given>
```

**THE KIND IS NOT COSMETIC, AND IT WAS MEASURED HERE ON 2026-09-14** — the measurement Amendment 17
Addendum 1 was drafted and ratified on the same day. A harness `/clear` — and any `/ctx` that clears IN PLACE
rather than respawning the pane — mints a NEW TRANSCRIPT ID IN THE SAME PROCESS: every subagent this lane has
running SURVIVES it, and only the tool calls they had in flight die (a `Bash` killed that way exits 137). The
handoff written a minute before that clear said *every agent dies with this context* and *relaunch every
writer below*; the live count a minute after it showed all five alive, each still on its worktree. Followed as
written, the block would have put a SECOND writer on each of five worktrees. Only a new process — the pane
respawned (`--restart`), the session ended (`--exit`), a profile switch, a usage-reset relaunch — takes the
writers with it.

| kind | when | the sentence act (3) carries | what the count then finds |
|---|---|---|---|
| `in-process` | a `/clear`, or a `/ctx` that clears in place | *THIS HANDOFF WAS WRITTEN FOR AN IN-PROCESS CLEAR: the process was not replaced, so expect every writer below live and the count to name them all.* | every writer below, live and owning its worktree |
| `respawn` | `--restart`, `--exit`, a profile switch, a usage-reset relaunch, `lane <name>` | *THIS HANDOFF WAS WRITTEN FOR A RESPAWN: the process that ran the writers is gone, so expect the count to name none of them.* | none of them — each is relaunched from where it stood |
| `unknown` | a plain `/handoff`, after which the person may `/clear` or may relaunch | *THIS HANDOFF CANNOT KNOW WHICH KIND FOLLOWED IT: a plain handoff may be followed by a `/clear` in this process or by a relaunch, so nothing below assumes either — the count is the answer.* | whatever is true; the count decides |

`lane-handoff` writes whichever of the three applies — `--in-process` for the first, `--restart`/`--exit` for
the second, nothing for the third — and the `PAUSED` payload carries it as `kind <in-process|respawn|unknown>`
beside `agent` and `transcript`, with the same word in the line's FREE TEXT after the why (`clear in-process`,
`clear respawn`, `kind unknown` — Addendum 1 (h)), because the record is what a later reader has. **THE KIND
SAYS WHAT TO EXPECT AND NEVER WHAT TO DO** (j): clause (i)'s count is what says what to do, it is the same in
all three, and where the count and the list disagree the count wins.

**Line 1 and the blank line after it are STRUCTURAL**: `lane-start` splices its `RESUMED by …` stamp at the
line immediately after the first blank line that follows line 1, so a block that does not open that way is a
block the stamps land in the middle of.

**If the read above set `$uuid_missing`, THE HANDOFF NAMES THAT GAP TOO** (`R-A11-5`: *"the gap named in the
handoff"*). Say in the state line, in as many words, that neither this session nor the lane's row names a
session uuid, that step 4's object-log `PAUSED` line and register line were therefore NOT written (nor the
row's state cell, where `$ws_missing` is also set), and that the `lane-start --no-launch` the message above
printed, filled in, is the act that records one — so the next session knows the log holds no record of this
swap, and that its next start is a start rather than a resume, instead of believing the lane never paused.
Write `session unknown` where the top block's first line carries `<uuid>`, as `lane-handoff` does.

**If step 1 set `$ws_missing`, THE HANDOFF IS WHERE THE GAP IS NAMED** (A11 Addendum 4 ruling 11, clause
(e)'s shape for a fact a writer cannot carry). Say in the state line, in as many words, that this session ran
in a container with no `LANES_WORKSTATION`, that step 4's register and object-log writes were therefore NOT
made, and that the row still reads as it did — so the next session knows the register is behind its own
handoff rather than believing the lane never paused. The handoff is written by `write-handoff`, in the lane's
own checkout, and that verb is not one of the writes the helper refuses for want of a workstation.

**THE WRITE IS ONE CALL, AND IT COMMITS THE HANDOFF'S OWN PATH AND NOTHING ELSE** (Amendment 4(d):
*"with explicit pathspecs — never `git add -A`, never a bare `git commit`"*; Amendment 5(c) and (d); Amendment 23
S3–S5). The block under this paragraph is the whole of it, and it is the only act in this step that writes.
THERE IS NO CHECKOUT FOR THIS SKILL TO RESOLVE AND NONE FOR IT TO SPELL: no `cd`, no commit, no pull and no push of
its own, and no fallback from one checkout to another. The verb writes in the lane's own checkout, under that
checkout's lock, and `LANES_LANE` names the lane. (This block used to commit in whichever checkout held the
file, the shared workspace checkout among them, with no lock, and to rebase on a pull before its push; finding
282 of the review of opensoft/openRepoTools#307 names it one of the three writers that did.) A STAGED ENTRY
THIS HANDOFF DID NOT MAKE and an operation in progress are the verb's refusals now, made before anything is
committed (2). So are, each a 2 with nothing written, a handoff target in W or in another checkout of the
register beside it (601, lane openRepoTools-3's finding on opensoft/openRepoTools#312), a relative cell that
climbs out of the lane's checkout (602) and a path there with a glob character (607), and since
`handoff-path` shares those refusals, the block under WHERE THE HANDOFF IS meets them first and this call is
not made.
THE NEW FILE IS MADE BY THE VERB, NEVER BY HAND (rv3's SHOULD 1 and lane openRepoTools-3's finding 981 on
#311, option (a)): `--prepend "$block_file"` reads the handoff under the lane checkout's lock, from the bytes
S3 has just brought to origin's, puts the new top block, a `---` line and a blank line in front of it, and
proves byte for byte that the block, the rule and the old file whole are all there before it replaces the
file. A file written whole from what a session remembered of the old one, the act that lost two lanes' rows on
2026-09-08, is never sent, and neither is a digest: a peer's block pushed after this session read the handoff
is not a refusal, it is kept under the new block, newest on top, which is the shape every handoff has. It is
`lane-handoff`'s own write of the same act (Amendment 17(a)). The verb refuses a block whose last byte is not
a newline (64) and writes nothing, because the `---` under it would join its last line and `lane-start` reads
the top block only to the first line that opens with `---`, so the next session's first prompt would run on
into the block before it: end the block file with a newline and run this block once more, once. A 7 with
`--prepend` is a restart's: an active restart owns the handoff, and that restart writes it, so the call is
not made again.
`$hf_subject` is the commit's one-line subject: the lane, the workstation (`unknown` where step 1 found none)
and the why in the operator's words, `handoff` where there is none, each control character made a space. It is
`lane-handoff`'s subject for the same act, spelled the same way.

```sh
# A CONTROL CHARACTER IS MADE A SPACE, NOT REFUSED OVER: the verb exits 64 on one in the subject and writes
# nothing, and a why with a stray tab must not cost the swap its handoff. `lane-handoff` writes the same act's
# subject the same way (its `subject_text`, and `unknown` for a missing workstation; rv3's NIT 1 on #311).
hf_subject="handoff($lane@${ws:-unknown}): PAUSED, ${why:-handoff}"
hf_subject="$(printf '%s' "$hf_subject" | LC_ALL=C tr '[:cntrl:]' ' ')"
# THE ONE CALL, PRINTED FILLED IN FOR A BLOCK THAT IS KEPT (lane openRepoTools-3's finding 983 on #311): a kept
# block goes into the handoff by this call once the gap is answered, never by a hand edit of the handoff. Each
# word is single-quoted, a quote in it spelled '\'', so the line runs as printed under bash and zsh alike.
hf_quote() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }
# IT NAMES `LANES_READ_MIRROR=1` ONLY WHERE THIS RUN'S `sread` FORWARDED A MIRROR LABEL OR RE-READ A 69 (`$mirror_read`,
# step 1's line; lane 3's rulings on #165, 6754439281 item 5 and 6754607466): then the store was down, and the same
# call by hand is a mirror read too. Anywhere else the skill cannot tell, and the call is printed as it always
# was, so that a run by hand during an outage refuses 69 and writes nothing, which is the failure that closes
# (item 2).
hf_mirror=""; [[ -z "${mirror_read:-}" ]] || hf_mirror="LANES_READ_MIRROR=1 "
hf_call="${hf_mirror}LANES_LANE=$(hf_quote "$lane") $(hf_quote "$L") write-handoff $(hf_quote "$lane") --prepend $(hf_quote "${block_file:-<block file>}") --subject $(hf_quote "$hf_subject")"
hf_rc=0; hf_out=""
# THE ONE CALL: the verb reads the handoff under the lock and puts the block in front of it (`--prepend`).
if [[ -n "$handoff_file" && -s "${block_file:-}" ]]; then
  hf_out="$(LANES_READ_MIRROR=1 LANES_LANE="$lane" "$L" write-handoff "$lane" --prepend "$block_file" \
    --subject "$hf_subject")" || hf_rc=$?
  # ITS STDOUT IS `<file><TAB><sha256>` ONCE THE FILE IS WRITTEN, whatever the exit; its own words are on stderr.
  hf_path="${hf_out%%$'\t'*}"
  hf_wrote="nothing was written"; [[ -z "$hf_out" ]] || hf_wrote="the file is written at $hf_path"
  hf_kept="The new top block is kept at $block_file: name that path in the report. Where it is still to go into the handoff once this is answered, it goes by this one call, never by a hand edit:"
  case "$hf_rc" in
    # A 0 MAY COMMIT NOTHING (lane openRepoTools-3's INFO 990 on #311; 2b's 721 and 728): LANES_NO_GIT=1, an
    # Amendment 8(d) handoff in no git work tree, or one in a clone of the register not beside W is written and
    # NOT committed, and the verb's note says so. So the words defer to that note and claim no commit.
    0) printf 'handoff written: %s (the note above, from write-handoff, says what was committed and where it was pushed, or that nothing was committed)\n' "$hf_path" ;;
    2) if [[ -n "$hf_out" ]]; then
         printf 'HANDOFF NOT COMMITTED: write-handoff refused the commit (exit 2; its words are above) and the file is written at %s, uncommitted. Nothing was pushed. Do not call it again: the new top block is at the head of the file now, and a second call would put a second copy of it on top. Answer the refusal, then commit and publish the file as the note above says.\n' "$hf_path"
       else
         printf 'HANDOFF NOT WRITTEN: write-handoff refused (exit 2; its words are above) and wrote nothing.\n'
       fi ;;
    3) printf 'HANDOFF PUSHED, NOT CONFIRMED: the push went, or timed out, and origin could not be read back to show the commit on it (exit 3; the note above names it). Do not call it published until it is read back.\n' ;;
    # A 6 IS SAID IN THE VERB'S WORDS (lane openRepoTools-3's finding 982 on #311): since 604 it is also an
    # Amendment 8(d) handoff, written, whose commit or push in its own repository failed, and `commit_publish`'s
    # failed add or commit is 6 with no commit at all. The verb's note says which, and where.
    6) printf 'HANDOFF NOT PUSHED: write-handoff exited 6, and the file is written at %s. The note above says where its commit is kept, or that there is none: on HEAD of the lane checkout, named, where every later write from that checkout refuses until it is published; for an Amendment 8(d) handoff, in its own repository, where its commit or push there failed; or nowhere, where its add or its commit failed. Do the act the note names. Never force.\n' "$hf_path" ;;
    # A 7 WITH `--prepend` IS A RESTART'S (lane openRepoTools-3's finding 981 on #311): no digest is sent, so
    # it is never "moved since it was read". The verb's own "changed before publication" is another act's
    # write in the instant between its read and its replace, under the lock, and the same call reads it again.
    7) printf 'HANDOFF NOT WRITTEN: an active restart owns this handoff (exit 7; its words are above), and nothing was published. Do not retry: that restart writes this handoff. (Where its words say instead that the handoff changed before publication, another act wrote it in the instant of this write: run this block once more, once.)\n' ;;
    # 64 IS A CALL THE VERB REFUSED AS GIVEN, and the one this block can make is a block whose last byte is no
    # newline (981): the `---` under it would join its last line. The verb never alters a caller's bytes.
    64) printf 'HANDOFF NOT WRITTEN: write-handoff refused the call (exit 64; its words are above) and wrote nothing. Where they say the block does not end with a newline, end it with one (echo >> %s) and run this block once more, once.\n' "$block_file" ;;
    *) printf 'HANDOFF NOT PUBLISHED: write-handoff exited %s (its words are above); %s.\n' "$hf_rc" "$hf_wrote" ;;
  esac
  # WHAT THIS CALL DID, CARRIED TO STEP 4'S REGISTER LINE (rv3's SHOULD 3 on #311), in the phrases lane
  # openRepoTools-3's answer 6 has the skill and 2b's `lane-handoff` share: refreshed only on a 0; written, NOT
  # published where the verb wrote the file (its stdout) and refused the commit (2) or kept it unpushed (6);
  # written, its publication NOT confirmed where it wrote the file and exited 3, or otherwise; else NOT refreshed.
  hf_record="handoff NOT refreshed (write-handoff exited $hf_rc and wrote nothing)"
  [[ -z "$hf_out" ]] || hf_record="handoff written, its publication NOT confirmed (write-handoff exited $hf_rc)"
  case "$hf_rc:${hf_out:+written}" in
    2:written|6:written) hf_record="handoff written, NOT published (write-handoff exited $hf_rc)" ;;
  esac
  [[ "$hf_rc" != 0 ]] || hf_record="handoff refreshed"
  # WHERE NOTHING WAS WRITTEN, THE NEW TOP BLOCK IS NOT LOST WITH THE SWAP: its temporary file is named for the report.
  [[ -n "$hf_out" ]] || printf '%s\n%s\n' "$hf_kept" "$hf_call"
else
  printf 'HANDOFF NOT WRITTEN: there is no handoff located, or no new top block written to its file, so write-handoff was NOT called. Write the new top block to %s if it is not written yet, and put it whole in the report. Once that is answered, it goes into the handoff by this one call, never by a hand edit:\n%s\nThe swap goes on (R-A11-11); the report carries this line.\n' \
    "${block_file:-a file of its own}" "$hf_call"
  # Block 1's reason where it gave one: a handoff not found, or a read that failed.
  hf_record="${hf_record:-handoff NOT refreshed (write-handoff was not called)}"
fi
# WHAT THIS STEP DID, PRINTED LAST, because step 4 runs in another Bash call, a new shell (984): set
# `hf_record` there, quoted, from this line.
printf 'hf_record=%s\n' "$hf_record"
```

A refusal, a conflict or a rejected push does not stop the swap (`R-A11-11`, *a swap is never left
unwritten*): where the lane's checkout refuses the commit (2), the verb has still written the handoff, commits
nothing and prints git's own words; where its push is refused it replays the write on origin's new tip, the
block put in front of origin's copy of the handoff, and where origin no longer has that handoff, or its row
names a file the replay cannot write, it keeps its commit on HEAD and names it (6). An Amendment 8(d)
handoff, in another repository, is committed and pushed there (604), and a commit or push there that failed
is 6 too, with the commit kept there or not made, as the verb's note says. The block prints what it did NOT
do, and the report carries that line. Never force, never
`git add -A`, and never commit staged entries you did not make.

**WHAT THIS STEP DID IS CARRIED TO STEP 4 in `$hf_record`,** so that the register's PAUSED line says it and
never claims it: `handoff refreshed` only where the call exited 0; `handoff written, NOT published
(write-handoff exited <n>)` where the verb wrote the file and exited 2 or 6; `handoff written, its publication
NOT confirmed (write-handoff exited <n>)` where it wrote the file and exited 3, or otherwise; and `handoff NOT
refreshed (<why>)` wherever nothing was written: the handoff was not found, its read failed, the call was not
made, or the verb wrote nothing. These are the phrases lane openRepoTools-3's answer 6 on #311 has 2b's
`lane-handoff` take too, through its fit (c), so the two writers of one act record its outcome alike. EVERY BASH CALL IS A NEW SHELL, so nothing one block sets reaches the next
by itself, and step 3 comes between step 2 and step 4 (lane openRepoTools-3's finding 984 on #311). Before
block 2, set `L`, `lane`, `ws` and `why` as step 1 has them, and each `name=value` line block 1 printed
(`handoff_file`, `block_file` and `hf_record`, those it printed), quoted. Set `mirror_read=1` too where step 1
printed it: it is what lets the call block 2 prints name `LANES_READ_MIRROR=1`. Before step 4, set `hf_record` from
block 2's last line, `hf_record=<what this step did>`, quoted, beside step 4's other values. A step 4 that it
never reached says `handoff NOT refreshed (step 2 left no outcome)`.

## 3. Subagents and worktrees — the one question, and the sweep that fills WRITERS

Run `ListAgents`, then send each running subagent one `SendMessage`: "Handoff imminent: commit and push what
you have now, with the usual trailers and explicit pathspecs; reply with the sha or 'nothing to push'."

**THEN SWEEP THE DISK, because an agent that has already died names nothing.** Every worktree under the
lane's own checkout and beside it is polled, and what it reports is what step 2's `WRITERS` section carries —
`$worktree` below is each of those paths in turn:

```bash
for worktree in "$dir"/.claude/worktrees/* "$(dirname "$dir")"/.lane-worktrees/"$lane"/*; do
  [ -d "$worktree" ] || continue
  git -C "$worktree" rev-parse --abbrev-ref HEAD  # its branch
  git -C "$worktree" log -1 --format='%h %s'      # what it had committed
  git -C "$worktree" status --short               # dirty files
  git -C "$worktree" log '@{u}..' --oneline       # unpushed commits
done
```

`lane-handoff` makes exactly this sweep and writes the section from it; the BRIEF of each writer is the one
fact only this session has, so it is the one this step supplies.

**Ask the operator exactly one question, and only if a writer still has unpushed work and has not replied:**
*"<agent> has unpushed work and has not replied — wait, or swap now?"* Everything else here is a report, not
a question. Never move on to step 4 with an unanswered writer unless the operator said so.

## 4. Write the swap record

First sanitize the operator's words **once**, as `lane-handoff`'s `sanitize` does: replace every ` — ` with
`; `, and spell every line break `; ` as well, whether it is a CRLF, a lone CR or a lone LF, one `; ` each
(#85). Amendment 7(b)/R26 refuses any payload or free text containing ` — ` (exit 2), because that separator
is what divides a line's fields from its free text, and both one-line writers below refuse a line break before
they write. The check before step 1 has already refused a why that carries a break, so spelling it here is
the second line of defence: where one arrives anyway, the record is still written, on one line. An empty why
is written `handoff`, as `lane-handoff` writes it. Both record writes then carry that text, `$why_text`
below, and never a template placeholder (#80 item 7).

**THE BLOCK OPENS WITH ITS OWN BASE AND READS THE IDENTITY AGAIN BEFORE IT WRITES** (feature 007, FR-029; design
Y:5678). On a SQL register a write can name the scopes it rests on, and the register's commit refuses it where
another place changed one of them after the act's base, which `lanes-edit.sh act-begin` prints. Each block of this
skill runs in its own shell, minutes apart, so a base cannot pass from step 1 to here except through the agent, and
step 1's reads were made before any base existed. So this block takes the base first. It then runs step 1's identity
reads again (`register-row`, `window-lane`, `swapped` and `canon-lane`) and REFUSES, writing nothing, where they no
longer answer the `lane` step 1 bound. **Those reads read the register and never the mirror,** so they do not go
through `sread`, whose 69 arm re-reads the mirror (feature 007's T406): a 69 from one of them, like a 69 from
`act-begin`, stops the writes (below), because a mirror's answer is older than the base and no expectation would see
a change in it. Its three writes then carry `LANES_EXPECT="row:<lane> bind:<lane> alias:<lane>"`, with
`row:<window name>` added where the window's name is not the lane (the set `lane-handoff`'s own PAUSED writes carry),
and `LANES_ACT` as a prefix on each call, never exported. **`alias:<lane>` stands for the walk's keys:** on a primary
base the block asks `canon-lane --walk` for the names the typed name walked through and lists `row:<n> alias:<n>` for
each, since the answer of `canon-lane` changes when a row or an alias line appears for any of them (Y:5624). **Where
`act-begin`, a read or the walk exits 69, 75 or 3, the block ends with that code.** The register cannot be consulted
and every write would be refused 69 as well, so none of the three is sent: the block prints the note below and exits
there, and step 5 prints the restart command with `--lane`. **Every other answer holds the writes the same way and
ends the block 1,** naming the verb and its code: `act-begin`'s 1 or 64, an `act-begin` that exited 0 with no line or a
malformed one, an identity read that failed, and any walk code but 0, 69, 75 and 3, a 2 included (lane 3, #165
6774499606, A2). **That 1 ends the act:** after the note it prints no `READY TO SWAP` line and no restart command,
and runs no step 5 or step 6 (REV-ACT2 S2; ruling A2: "the act exits 1"). **A 2 ends the act the same way:** the identity refusal's 2 and a write that was
sent and exited anything but 0, 3 or 69 under a seq base, which ends the block 2 with `THIS ACT STOPS` after the three writes have been tried. It is 2 alone
whatever code the writer gave, and its own 75 stays printed in its own stderr (lane 3, #165 6835210568, question 4), so a 75 from this block is always one
that held the writes. **A write that exits 69, and a block that sent none, print ONE note** that says how the
record is completed later (`lane-handoff --late --at <UTC> --lane <L>`, run from a shell by whoever relaunches the
lane, once the register answers and before the relaunch), after the third write however many of the three exited 69
(spec:692; B12b tasks:1361 and :1375). **Under a seq base the note names `--late` only where the object log's `PAUSED` line
itself exited 69 or was not sent and no write stopped the act** (lane 3, #165 6836816821, question 1; 6837908956, question 4),
because `--late` writes that line alone and refuses once the lane's last line is a `PAUSED`, and after a stop it would write a
second one. Where that line landed, or a write stopped the act, the note says to run
`/handoff` again from step 1 once the register answers (Y:5601), and where it exited 3 the note names that write's printed
`LANES_WRITE_ID` rerun first and then `/handoff` again (Y:5199, Y:5222) (below). Where the register's line or the row also exited 3, every one of these notes ends with the stop's own sentence, which names the rerun the writer printed for it and says to run it first (lane 3, #165 6837908956, questions 1 to 3). Where `act-begin` exits 2 the helper predates feature 007 and the writes go as
they always did, with `LANES_ACT` unset and `LANES_EXPECT` kept, which such a helper reads no more than it reads
`LANES_ACT`; this skill sets no `SWAPPING`, so the note says the lane stays as it is. Off a SQL register the base
reads `<id>@files` and both variables are ignored. Set `L`, `sread`, `lane`, `ws` and the rest as steps 1 and 2 have
them, as for every block here; `sread` is defined in the first block of this file.

```sh
# FEATURE 007 (FR-029; Y:5678) — THIS ACT'S BASE, TAKEN BEFORE ANYTHING IS READ OR
# WRITTEN HERE, AND THE IDENTITY READ AGAIN AFTER IT. Step 1's reads were made
# before any base existed, so the register's commit cannot tell this act that one
# of them has changed since. `act-begin` prints the base, `<act-id>@<seq>:<generation>`
# on a SQL register and `<act-id>@files` off one, and the three writes below carry
# it as `LANES_ACT`, a prefix on each call and never exported, with the scopes each
# rests on in `LANES_EXPECT`. Nothing of an earlier act's, and nothing inherited, is
# this act's base, so both are unset first.
#
# WHAT EACH ANSWER OF `act-begin` DOES (lane 3, #165 6770733371, its shared rulings
# 1 and 2, and 6774499606, A2). 0 with a base is kept. 2 is a helper predating
# feature 007: the writes go as they always did, `LANES_ACT` unset (it is left empty
# here, which every helper reads as unset) and every `LANES_EXPECT` kept, which such
# a helper reads no more than it reads `LANES_ACT`. 69, 75 and 3 mean the register
# cannot be consulted and every write below would be refused 69 as well, so none of
# the three is sent (`act_down`, as `$ws_missing` stops them), the note says how the
# record is completed, and the block ENDS WITH THAT CODE. Anything else is a read that
# FAILED or an answer that is not a base, and REFUSES BY HOLDING: the REFUSED line
# names the verb and its code, none of the three is sent, the note prints and the
# block ends 1. A container with no workstation writes nothing here, so it takes no base.
unset LANES_ACT LANES_EXPECT
act_line=""; act_scopes=""; act_down=""; act_exit=""; act_w69=""; act_w9_rc=""
act_also3=""; act_p69_also3=""
# A WRITE THAT WAS SENT AND DID NOT END 0, 3 OR 69 UNDER A SEQ BASE ENDS THE BLOCK, AND THE ACT
# (feature 007, T431; TP:5861-5864 "never 0"; tasks:1373, `:2817`'s rule; lane 3, #165
# 6834271321, and 6835210568 on lane 4's question 4: THE SKILL'S STOP USES 2 ALONE).
# `act_again_say` records it below, and the end of the block prints the stop and exits 2,
# whatever code the writer gave: the writer's own 75 stays printed in its own stderr. A 75
# is this block's exit only where `act-begin`, an identity read or the walk gave it
# (`act_down_say`), and step 5 then stands, so a write's 75 read as the block's would be two
# things at once and a 2 is one. A 3 and a 69 keep their own paths, as do the writes under
# `@files` and after `act-begin`'s 2.
act_stop=""; act_stop_names=""; act_d3=""
# THE BASE'S FORM (Y:5577-5579; REV-ACT2 N5), read with SPELLED-OUT bracket lists
# and no range: `[0123456789abcdef]` for a lower-case hex digit, `[123456789]` for a
# seq's first digit and `[0123456789]` for the rest. A range such as `[0-9a-f]` is
# read through the shell's locale, and a list is not. The same grammar as `act_parse`
# in `lanes-edit.sh` and `act_form` in `lane-handoff`.
act_re='^[0123456789abcdef]{32}@(files|(0|[123456789][0123456789]{0,17}):[0123456789abcdef]{8}-[0123456789abcdef]{4}-[0123456789abcdef]{4}-[0123456789abcdef]{4}-[0123456789abcdef]{12})$'
# THE 69 NOTE (spec:692, :700-702; Y:5573; lane 3, #165 6770733371, T429's
# question 5 and T431's question 3; 6774499606, REV-ACT 1 and 2). Where a `PAUSED`
# write exits 69 or none of them is sent, a note names how the record is completed
# later: the late `PAUSED` path, who runs it and when, with `--lane <L>`, because a
# shell outside the lane's window takes the workstation's newest swap, which can be
# another lane's. THE SKILL SETS NO `SWAPPING` AND SAYS NONE: the lane stays as it is,
# because `--late --lane` needs no `SWAPPING` (T431's question 4). IT PRINTS ONCE ON
# EVERY PATH, AND IT IS ONE OF FOUR TEXTS. A write that exited 69 sets
# `act_w69`, and the note prints after the third write, however many of the three
# exited 69 (lane 3's round B12b, tasks:1361 and :1375). `act_69_note` is the late
# path's. UNDER A SEQ BASE THE NOTE NAMES `--late` ONLY WHERE THE OBJECT LOG'S PAUSED
# LINE ITSELF EXITED 69 OR WAS NOT SENT AND NO WRITE STOPPED THE ACT (`act_w9_rc` is 69
# or empty and `act_stop` is empty; lane 3, #165 6836816821, question 1, and 6837908956,
# question 4). `--late` writes that line alone and refuses 2 where the lane's last line
# is already a `PAUSED`, so it is no way to complete the record anywhere else.
# WHERE THE LINE LANDED (`act_w9_rc` 0) the 69 came from the register's line or the row,
# and `act_69_landed_note` says to run the act again, as `lane-handoff`'s
# `paused_69_landed_note` does (T429's `4534a4af`; lane 3, #165 6835210568, "the 69 note
# needs mending either way"; Y:5601). WHERE IT EXITED 3 (`act_w9_rc` 3) `act_69_doubt_note`
# names the writer's printed `LANES_WRITE_ID` rerun first, which writes the line once or
# finds it, and then the act again (Y:5199, Y:5222): `--late` before that rerun would write
# a late line and the rerun a second, and after it `--late` refuses. WHERE A WRITE STOPPED
# THE ACT (`act_stop`: the object log's own 2, 75 or any other code, or a later write's
# beside a line that exited 69 or was not sent; the block ends 2 after `THIS ACT STOPS`)
# `act_69_again_note` says to run the act again from its start, as the stop's own line
# does (Y:5601), so the two never say different things: a `--late` after a stop writes two
# `PAUSED` lines (lane 3, #165 6836853700, question 8). WHERE W11'S OR W12'S WRITE ALSO
# EXITED 3, UNDER A SEQ BASE, each of the four ends with the stop's own sentence
# (`act_p69_also3`, set where the three writes are known; T429's `p69_also3`; lane 3, #165
# 6837908956, questions 1 to 3): the rerun the writer printed is what settles that write,
# and the way the note names is no way to settle it. It is empty everywhere else, `@files`
# and `act-begin`'s 2 included, so those notes keep their words, and W9's own 3 is named by
# `act_69_doubt_note` already. Where `act-begin`, an identity
# read or the walk stopped the writes, none was sent: the note prints at the end of the
# reads, before anything is built, and the block ends there, and it is always
# `act_69_note`. `act_down_say` and
# `act_hold` run here, not in a `$( )`, because they set `act_down`. They clear the
# base and the scopes, which no write below will use.
act_down_say() {   # act_down_say <the call that stopped the writes> <its exit code: 69, 75 or 3>
  act_down=1; act_exit="$2"; act_line=""; act_scopes=""
  echo "NO PAUSED WRITES: \`$1\` exited $2, so the register cannot be consulted and every write below would be refused 69 as well. None of the three is sent: no PAUSED line, no register line and no state cell is written. The handoff step 2 refreshed stands, and step 5 prints the restart command with --lane. This block ends $2."
}
act_hold() {   # act_hold: the REFUSED line above held the writes (A2); the block ends 1 and the act stops
  act_down=1; act_exit=1; act_line=""; act_scopes=""
  echo "NO PAUSED WRITES: the refusal above holds them. None of the three is sent: no PAUSED line, no register line and no state cell is written. The handoff step 2 refreshed stands. This block ends 1 and the act STOPS after the note below: no restart command is printed and step 5 and step 6 are not run. Fix what the refusal names and run /handoff again."
}
act_69_note() {
  echo "THE PAUSED RECORD IS INCOMPLETE, and the lane stays as it is, an interrupted swap. The record is completed later with \`lane-handoff --late --at <UTC> --lane ${lane:-<L>}\`, run from a shell by whoever relaunches the lane, once the register answers and BEFORE the relaunch (step 6 says why); the UTC is the moment this session ended.$act_p69_also3"
}
act_69_landed_note() {
  echo "THE PAUSED RECORD IS INCOMPLETE, and the lane stays as it is, an interrupted swap. The object log's PAUSED line is written, so \`lane-handoff --late\` is not the way to complete it: it refuses where the lane's last line is already a PAUSED, and it never writes the register's file-level line or the row. Once the register answers, run /handoff again from step 1 (Y:5601): it takes a new base.$act_p69_also3"
}
act_69_doubt_note() {
  echo "THE PAUSED RECORD IS INCOMPLETE, and the lane stays as it is, an interrupted swap. The object log's PAUSED line is in doubt (its write exited 3), so \`lane-handoff --late\` is not the way to complete it: where the rerun the writer printed above lands the line, \`--late\` refuses, and where it has not, a late line and that rerun would write two. Run that \`LANES_WRITE_ID\` rerun first, which writes the line once or finds it (Y:5199, Y:5222), and then, once the register answers, run /handoff again from step 1 (Y:5601): it takes a new base.$act_p69_also3"
}
act_69_again_note() {
  echo "THE PAUSED RECORD IS INCOMPLETE, and the lane stays as it is, an interrupted swap. The object log's PAUSED line did not land (it was not written, and this act stops, below), so \`lane-handoff --late\` is not the way to complete it. Once the register answers, run /handoff again from step 1 (Y:5601): it takes a new base.$act_p69_also3"
}
# A WRITE THAT EXITED 3 IS IN DOUBT, NOT REFUSED (Y:5698, F9; lane 3, #165 6770733371,
# T431's question 2 and its shared ruling 3). The act carries on, as it does after any
# write that did not land, and relays the writer's own printed rerun: T433's text, D8's
# words and then the files-mode sentence. The writers' stderr is kept, so the rerun is
# above, and this block prints no hint of its own beside it.
act_in_doubt() {   # act_in_doubt <which write>
  act_d3=1
  echo "IN DOUBT: $1 exited 3 (the writer's own code, above). On primary it may not be written; run the printed \`LANES_WRITE_ID\` rerun, which writes it once or finds it. Where the writer printed no such rerun (off primary), the commit is local and may already be on origin."
}
# NO HAND COMMAND AFTER A WRITE THAT DID NOT END 0, UNDER A SEQ BASE (lane 3, #165
# 6779688808, Q11; Y:5587, Y:5601). A hand re-run of a write that left out the act's
# two variables writes unchecked, and one that kept them would only be refused again,
# so the block prints none. A 3 keeps the writer's rerun (`act_in_doubt`), a 69 keeps
# the note, and every other code keeps the writer's own stderr, above, and says to run
# the act again from its start. Under `@files`, or with no base after `act-begin`'s 2,
# today's hand re-run stands and this prints nothing. AND THE WRITE IS RECORDED AS ONE
# THAT STOPS THE ACT (T431; lane 3, #165 6834271321 and 6835210568, question 4): the block
# ends with it, below, 2 and never 0, whatever code the writer gave.
act_again_say() {   # act_again_say <which write> <its exit code>
  case "$act_line" in ""|*@files) return 0 ;; esac
  case "$2" in 0|3|69) return 0 ;; esac
  act_stop=1; act_stop_names="${act_stop_names:+$act_stop_names, }$1"
  echo "RUN /handoff AGAIN FROM STEP 1: $1 exited $2 under a seq base, so no hand command is printed for it. The writer's own words are above, and a new run takes a new base."
}
act_scope_add() {   # act_scope_add <scope>: appended to act_scopes once, in lower case
  as_s="$(printf '%s' "$1" | tr 'A-Z' 'a-z')"
  case " $act_scopes " in *" $as_s "*) return 0 ;; esac
  act_scopes="${act_scopes:+$act_scopes }$as_s"
}
if [[ -z "$ws_missing" ]]; then
  act_rc=0
  act_line="$("$L" act-begin)" || act_rc=$?
  case "$act_rc" in
    0)  if [[ ! "$act_line" =~ $act_re ]]; then
          printf 'REFUSED: `%s act-begin` exited 0 and printed %s, which is not a base (a 32-digit act id, an @, then files or a seq and a generation). Every write below would be refused 2 for it, and this skill will not write a PAUSED record, a register line or a state cell on one. Run it by hand to see what it says.\n' "$L" "${act_line:-nothing}" >&2
          act_hold
        fi ;;
    2)  act_line=""
        echo "NO ACT BASE: \`$L act-begin\` exited 2, a lanes-edit.sh predating feature 007, so the writes below carry no base, as they did before." ;;
    69|75|3) act_down_say "$L act-begin" "$act_rc" ;;
    *)  printf 'REFUSED: `%s act-begin` failed (exit %s). That is NOT a base: a read that failed is never an answer (Amendment 7(d)), and this skill will not write a PAUSED record, a register line or a state cell without one. Run it by hand to see what it says.\n' "$L" "$act_rc" >&2
        act_hold ;;
  esac
fi
# THE IDENTITY, READ AGAIN UNDER THE BASE (Y:5678; the second of the three
# conditions under which every act can carry one). Step 1 bound `lane` from the
# window's own name, the window's own record or the workstation's newest swap,
# and read it through `canon-lane`. The SAME reads run here, in the SAME order,
# so a change to any of them after the base is one the commit refuses, and where
# they answer anything but `lane` the lane this window names is no longer the one
# step 1 bound: another session bound it, or a row or an alias moved. A PAUSED
# record, a register line and a state flip written now would be for a lane this
# window is not, so nothing below is written. It is not asked where nothing below
# is written: a container with no workstation, or a register that could not be read.
#
# THESE READS NEVER ASK THE MIRROR, AND A MIRROR ANSWER WOULD BE A 69 (lane 3, #165
# 6770733371, T431's question 5; its shared ruling 1). A mirror is older than the
# base, so no expectation would see a change in it. They do not go through `sread`,
# whose 69 arm re-reads the mirror once feature 007's T406 has landed, but through
# `act_read` below, which has `sread`'s answers for 0, 2, 8 and a failed read and
# stops the writes on a 69 (and a 75 or a 3) as `act-begin`'s own answer does,
# ending the block with that code, and which unsets `LANES_READ_MIRROR` for its call,
# so an inherited one is no answer. A read that failed any other way holds the writes
# and ends the block 1 (A2).
act_read() {   # act_read <var> "<what the failure is NOT>" <verb> [args…]
  ar_var="$1"; ar_not="$2"; shift 2
  ar_out=""; ar_rc=0
  if [[ -z "$act_down" ]]; then
    ar_out="$(env -u LANES_READ_MIRROR LANES_NO_FETCH=1 "$L" "$@" 2>/dev/null)" || ar_rc=$?
    case "$ar_rc" in
      0)  : ;;
      69|75|3) ar_out=""; act_down_say "$L $1" "$ar_rc" ;;
      2)  ar_why="$(env -u LANES_READ_MIRROR LANES_NO_FETCH=1 "$L" "$@" 2>&1 >/dev/null || :)"
          case "$ar_why" in
            *"Amendment 15(d)"*)
              printf 'REFUSED: `%s %s` says the register holds two rows for this lane that differ only by case, so no read of it is unambiguous and this skill will not pick one (Amendment 15(d)). It will not write a PAUSED record, a register line or a state cell; merge the two rows by hand first. The helper said:\n%s\n' \
                "$L" "$1" "$ar_why" >&2
              exit 2 ;;
          esac
          ar_out="" ;;
      8)  ar_out="" ;;
      *)  printf 'REFUSED: `%s %s` failed (exit %s). That is NOT %s — a read that failed is never an answer (Amendment 7(d)), and this skill will not write a PAUSED record, a register line or a state cell on one. Run it by hand to see what it says.\n' \
            "$L" "$1" "$ar_rc" "$ar_not" >&2
          ar_out=""; act_hold ;;
    esac
  fi
  eval "$ar_var=\$ar_out"
}
name_re='^[A-Za-z0-9_][A-Za-z0-9._-]*$'
id_window=""; id_lane=""; id_typed=""
if [[ -z "$ws_missing" && -z "$act_down" ]]; then
  id_window="$(tmux display-message -p '#W' 2>/dev/null)"
  id_lane="$id_window"
  if [[ -n "$id_lane" ]]; then
    act_read id_probe "'this window is not a lane'" register-row "$id_lane"
    [[ -n "$id_probe" ]] || id_lane=""
  fi
  if [[ -z "$id_lane" ]]; then
    id_ref="$(tmux display-message -p '#{window_id}' 2>/dev/null)"
    [[ -n "$id_ref" ]] || id_ref="$(tmux display-message -p '#S:#I' 2>/dev/null)"
    act_read id_cand "'no lane is bound to this window'" window-lane "$ws" "$id_ref"
    [[ "$id_cand" =~ $name_re ]] && id_lane="$id_cand"
  fi
  if [[ -z "$id_lane" ]]; then
    act_read id_rows "'this workstation has no swap record'" swapped "$ws"
    id_first="$(printf '%s\n' "$id_rows" | head -n 1)"
    if [[ -n "$id_rows" && "$id_first" == *$'\t'* ]]; then
      id_cand="${id_first%%$'\t'*}"
      [[ "$id_cand" =~ $name_re ]] && id_lane="$id_cand"
    fi
  fi
  if [[ -n "$id_lane" ]]; then
    id_typed="$id_lane"      # the name the act gave `canon-lane`, for its walk below
    act_read id_canon "'this lane has no row'" canon-lane "$id_lane"
    [[ "$id_canon" =~ $name_re ]] && id_lane="$id_canon"
  fi
fi
if [[ -z "$ws_missing" && -z "$act_down" ]]; then
  if [[ -z "$lane" || "$id_lane" != "$lane" ]]; then
    printf 'REFUSED: step 1 bound this window to lane "%s", and the same reads, run again after this block took its base, answer "%s". The lane this window names has changed since step 1 (another session bound it, or a row or an alias moved), so a PAUSED record, a register line and a state flip written now would be for a lane this window is not. Nothing of step 4 was written, and the handoff step 2 refreshed stands. Run /handoff again from step 1.\n' "${lane:-<none>}" "${id_lane:-<none>}" >&2
    exit 2
  fi
  # THE SCOPES THE THREE WRITES REST ON (Y:5678): `row:L bind:L alias:L`, the set
  # `lane-handoff`'s own PAUSED writes carry (its W9, W11 and W12), because the
  # `append-line` below is W11's. `row:<window name>` is added where the window's
  # name is not the lane: step 1's first read asked the register for a row of that
  # name. A WINDOW NAME `check_lane_name` would refuse is never listed, because a window
  # named `my window` is no walk answer and one token outside the six forms refuses every
  # write with 2. A walk's names are not filtered this way (below).
  #
  # `alias:L` STANDS FOR THE WALK'S KEYS (Y:5624; lane 3, #165 6770733371, its shared
  # ruling G2 and T431's question 4): `canon-lane`'s answer changes when a row or an
  # alias line appears for ANY name on its walk, so the act lists `row:<n>` and
  # `alias:<n>` for every name `canon-lane --walk` prints for the name it gave
  # `canon-lane`. The walk is asked on a primary base only, where the keys are read:
  # in files mode both variables are ignored, and a helper predating feature 007
  # has no `--walk`. A walk that exits 69, 75 or 3 is `act-begin`'s failure with the
  # same code (G2): the writes stop, as `act-begin`'s own 69, 75 and 3 stop them, and
  # the block ends with that code. EVERY OTHER END REFUSES BY HOLDING (A2): none of the
  # three is sent, the note prints and the block ends 1, and that includes a 2, which is
  # NOT `act-begin`'s 2: there the helper predates feature 007 and the writes go on. The
  # walk is asked only after `act-begin` took a primary base, so the helper has
  # `act-begin`, and a 2 from `canon-lane --walk` is `canon-lane`'s own refusal (it
  # spends 2 on two rows that differ only by case, Amendment 15(d), and on a name it
  # will not take), or a helper with no `--walk`. Neither gave the names, a key left
  # out is a change the write would not see, and a walk that names nobody (an empty one,
  # or one of white space only) refuses the same way:
  # refusing is the safer arm for the walk.
  act_scope_add "row:$lane"; act_scope_add "bind:$lane"; act_scope_add "alias:$lane"
  case "$act_line" in
    ""|*@files) : ;;
    *)  # THE WALK'S OWN WORDS ARE RELAYED WHERE IT FAILS (REV-ACT2 N4), as `lane-start` and
        # `lane-end` relay them, with no temporary file to leave behind: one call, its
        # stdout sent to fd 3, its stderr through `sed` to tag each line `E `, and its
        # exit code echoed as `rc=<n>` on fd 3, all into the one substitution, then
        # split by tag. A name `check_lane_name` accepts has no space and no `=`, so no such
        # line can be taken for a tag; one outside that class that begins `E ` or `rc=` would
        # be, which no tool can write today (lane 3, #165 6837908956, question 7). A missing
        # `rc=` line stays `unknown`, which refuses below.
        aw_rc=unknown; act_walk=""; aw_err=""
        aw_all="$( { { env -u LANES_READ_MIRROR LANES_NO_FETCH=1 "$L" canon-lane --walk "$id_typed" 1>&3 3>&-; echo "rc=$?" >&3; } 2>&1 | sed 's/^/E /'; } 3>&1 )"
        while IFS= read -r aw_l; do
          case "$aw_l" in
            "E "*) aw_err="$aw_err${aw_l#E }"$'\n' ;;
            "rc="*) aw_rc="${aw_l#rc=}" ;;
            *) [[ -z "$aw_l" ]] || act_walk="$act_walk$aw_l"$'\n' ;;
          esac
        done <<< "$aw_all"
        # A WALK OF ONLY SPACES OR TABS NAMES NOBODY EITHER (lane 3, #165 6837908956, question 8,
        # a NIT: tasks:1391 refuses "a walk that exits 0 and prints no name"). `lane-handoff` and
        # `lane-end` test the whole walk for a character that is not white space, and so does
        # this: a walk with none is refused 1 as an empty one is. Below, only an empty line is
        # skipped, and a line of white space beside a name still goes on to `LANES_EXPECT`,
        # where the writer refuses it with 2 (question 5).
        aw_named=""
        case "$act_walk" in *[![:space:]]*) aw_named=1 ;; esac
        if [[ "$aw_rc" != 0 || -z "$aw_named" ]]; then
          [[ -z "$aw_err" ]] || printf '%s' "$aw_err" >&2
        fi
        case "$aw_rc" in
          0)  if [[ -z "$aw_named" ]]; then
                printf 'REFUSED: `%s canon-lane --walk %s` exited 0 and printed no name, so the names lane %s was found through are NOT known, and the writes below would leave their keys out: a change to one of them would not refuse them (Y:5624). Nothing of step 4 was written.\n' "$L" "$id_typed" "$lane" >&2
                act_hold
              else
                # THE NAMES ARE PEELED BY PARAMETER EXPANSION, one line at a time, with no
                # here-string (RC-W10d's SHOULD): bash 3.2 backs a here-string with a temp
                # file in /tmp, and where none can be made the redirection fails, the loop
                # never runs, and the block goes on with no `row:<n>` or `alias:<n>` key for
                # any name the walk found (Y:5587: "never dropped"). No redirection, no file.
                # ONLY AN EMPTY LINE IS SKIPPED (lane 3, #165 6836816821, question 5, a NIT: no
                # tool writes a name outside `check_lane_name`'s class today, since the register
                # has no alias table and `rename-lane` checks both names). Any other name goes on
                # to `act_scope_add`, and so into `LANES_EXPECT`, where the writer refuses a token
                # outside the forms with 2 before any call (Y:5600), and the block ends 2 after
                # `THIS ACT STOPS`: a name is never dropped, since dropping a token under-checks
                # (Y:5583, Y:5587). The window name's own filter, above, stays.
                aw_nl=$'\n'; aw_rest="$act_walk"
                while [[ -n "$aw_rest" ]]; do
                  aw_n="${aw_rest%%"$aw_nl"*}"
                  case "$aw_rest" in
                    *"$aw_nl"*) aw_rest="${aw_rest#*"$aw_nl"}" ;;
                    *) aw_rest="" ;;
                  esac
                  [[ -n "$aw_n" ]] || continue
                  act_scope_add "row:$aw_n"; act_scope_add "alias:$aw_n"
                done
              fi ;;
          69|75|3) act_down_say "$L canon-lane --walk $id_typed" "$aw_rc" ;;
          *)  printf 'REFUSED: `%s canon-lane --walk %s` failed (exit %s), so the names lane %s was found through are NOT known, and the writes below would leave their keys out: a change to one of them would not refuse them (Y:5624). Nothing of step 4 was written. A `lanes-edit.sh` with no `--walk` is older than this skill.\n' "$L" "$id_typed" "$aw_rc" "$lane" >&2
              act_hold ;;
        esac ;;
  esac
  if [[ -z "$act_down" && -n "$id_window" && "$id_window" != "$lane" && "$id_window" =~ $name_re ]]; then
    act_scope_add "row:$id_window"
  fi
fi
# THE WRITES ARE HELD HERE, AND THE BLOCK ENDS (lane 3, #165 6774499606, A2 and T431's
# question 2). `act_down` is set only above, by `act-begin`, an identity read or the
# walk, and nothing below builds a record that no write will carry: the note prints
# ONCE and the block ends with `act_exit`, the 69, 75 or 3 that stopped the writes, or
# 1 where an answer refused them. The handoff step 2 refreshed stands. After a 69, 75 or
# 3 the swap goes on to step 5, which prints the restart command with `--lane`; after a 1
# the act STOPS here and prints none (REV-ACT2 S2). Say in the report which code and why.
if [[ -n "$act_down" ]]; then
  act_69_note
  exit "$act_exit"
fi
# AMENDMENT 11 CLAUSE (c) — THE RECORD'S TWO NEW SUB-FIELDS, AND ITS SECOND REF.
# A swap is the ONE moment the lane is certainly running, so it is the one
# moment both are certainly knowable; neither is derived and neither is guessed.
#   dir      the lane's CHECKOUT — its own recorded directory where it has one
#            (`lane-dir`, written by `lane-start` at every start under this
#            amendment), and only failing that this session's own checkout root.
#            NEVER a subagent's worktree: a lane's `dir` is where the lane is
#            restarted, and restarting into a worktree is Evidence 3's silent
#            loss of the repository's CLAUDE.md and the lane's memory.
#   profile  `$CLAUDE_PROFILE_NAME`, which the launcher exports into every
#            session it starts. Without it a `restart <lane>` typed anywhere but
#            in the lane's surviving window cannot name the profile the launcher
#            needs, because today the profile is recoverable only from the tmux
#            session name, which act 1's window reuse and any rename destroy.
#   window   gains its `<@id>` beside the `<session>:<index>` it already had —
#            two space-separated refs in ONE sub-field under 7(b)'s grammar.
# A path containing a space is WRITTEN QUOTED, which is what makes it one ref;
# a path containing `, `, ` — `, `; ` or `"` is DROPPED — the sub-field, not the
# line — and what was dropped is PRINTED (A11 Addendum 4 ruling 10; SPEC rev 6
# §5 for the `; `).
#
# WHY DROPPED HERE AND REFUSED IN `lane-start`, WHICH IS THE SAME RULE READ
# TWICE. Both writers refuse the same VALUES — the list is identical — and they
# differ only in what happens next, because of where they stand.
# `lane-start:686-690` is in front of a LAUNCH: it can exit 2 and the operator
# moves the checkout and starts again. This is the LAST act of a session that is
# about to die, and `R-A11-11` binds it: *a swap is never left unwritten*. An
# `exit 2` here loses the PAUSED line the launcher restarts from, over a
# sub-field that is information. So the offending sub-field goes, the line
# stays, and the reader is told which fact it does not carry — which is
# Amendment 7(i)'s reader rule given a writer that speaks.
#
# `window` IS NOT WIDENED to `; ` and that is a ruling rather than an oversight
# (SPEC rev 6 §5): its list is Amendment 8(b)'s, narrowing it would be a SEVENTH
# edit to in-force text where the ratified count is six (`R-A11-15`), and a
# `window` value is a launcher-built session name, an index and an `<@id>`.
#
# `dir` IS THE LANE'S CHECKOUT AND NEVER A WORKTREE (`R-A11-11`, A11 Addendum 2;
# Evidence 3). THREE SOURCES, every one of them a RECORD rather than a
# derivation:
#   1. the lane's own recorded `dir` (`lane-dir`), written by `lane-start` at
#      every start under this amendment — the lane's checkout as the lane's own
#      writer recorded it;
#   2. the launcher's `WORKBENCHES_CLAUDE_LANE_DIR`, exported only where the
#      directory order's rungs 1-3 answered;
#   3. THE LIVE SESSION'S OWN RECORD — the harness writes `"cwd"` beside
#      `"tmux"` in `$CLAUDE_CONFIG_DIR/sessions/<pid>.json`, keyed by
#      `sessionId`, which is this session's directory as the harness itself
#      keyed it, and the directory whose CLAUDE.md and memory it loaded.
#
# `git rev-parse --show-toplevel` AND `$PWD` WERE THE NEXT TWO RUNGS AND ARE
# GONE (ruling 10). They record the git toplevel of wherever the shell stands,
# which in a subagent's scratchpad worktree is THAT WORKTREE — and `restart
# <lane>` then `cd`s into it, losing the repository's CLAUDE.md and the lane's
# memory (Evidence 3). A record with NO `dir` is complete in the same way a
# record with no `@id` is; a record with the WRONG one is not, because
# `lane-start` writes the lane's home from that tree's `origin` and every `#n`
# after it inherits that.
# AND A READ THAT FAILED IS NOT A RECORD THAT NAMES NO DIRECTORY (#26, the
# review of `c3ebcfe`, this file's `:236`). `|| dir=""` made those two the same
# fact, and sources 2 and 3 are NOT rungs beneath a failed read: they answer for
# a lane whose record names no directory, and the third of them is THIS
# SESSION'S OWN `cwd`. A swap typed in one checkout for a lane that lives in
# another would then record this session's directory as that lane's, in a log
# nothing rewrites — Evidence 3's wrong checkout, written by the one act that
# exists to leave the lane findable. So a failed read takes no substitute: the
# two sources below are skipped and the sub-field is absent.
#
# IT DOES NOT STOP, AND THAT IS `R-A11-11`: *a swap is never left unwritten*.
# The offending sub-field goes and the line stays — the same answer this file
# already gives for a `dir` it may not write (the DROP below) — and the reader
# of the record is told WHICH READ was lost rather than handed a plausible wrong
# path. That is why this one read does not come through `sread`, which stops.
dir=""; dir_read_failed=""; dir_rc=0
dir="$(LANES_NO_FETCH=1 "$L" lane-dir "$lane" 2>/dev/null)" || dir_rc=$?
case "$dir_rc" in
  0)   : ;;
  8|2) dir="" ;;
  *)   dir=""; dir_read_failed="\`$L lane-dir $lane\` failed (exit $dir_rc)" ;;
esac
if [[ -z "$dir" && -z "$dir_read_failed" ]]; then
  dir="${WORKBENCHES_CLAUDE_LANE_DIR:-}"
  if [[ -z "$dir" && -n "${CLAUDE_CODE_SESSION_ID:-}" && -n "${CLAUDE_CONFIG_DIR:-}" ]]; then
    dir="$(jq -r --arg id "$CLAUDE_CODE_SESSION_ID" \
      'select((.sessionId // "") == $id) | .cwd // empty' \
      "$CLAUDE_CONFIG_DIR"/sessions/*.json 2>/dev/null | head -n 1)"
  fi
fi
# AN ABSOLUTE PATH OR NOTHING AT ALL: a relative one has no meaning without the
# writer's cwd, which no reader of this log has, and `~` is the writing shell's.
[[ "$dir" == /* ]] || dir=""
# AND BOTH REFS FALL BACK TO WHAT THE LAUNCHER EXPORTED, which is `F-X13`'s
# row (h) and is absorbed under `R-A11-26`'s own rule — *"the survivor is the
# SUPERSET, so a seventh divergence found after this is absorbed on the same
# ground and needs no ruling of its own"*. On the normal path the launcher
# started this session and threaded the window it captured across its re-exec
# (`WORKBENCHES_CLAUDE_WINDOW_REF`, `_WINDOW_ID`, clause (b) act 1); a `tmux`
# that is missing, a server that has gone, or a shim that answers nothing then
# costs the record a `window` sub-field it already had in hand. Each is SHAPE
# CHECKED before it is taken, by the same two tests the live reads get, because
# an environment variable is no more trustworthy than a shim.
# A `<session>:<index>` IS CHECKED AS A WHOLE STRING (#80 item 4, the same
# finding `lane-handoff`'s `window_ref_ok` took as item 3). `*:[0-9]*` was a
# prefix glob, so `s:1junk` passed — from a shim and from the launcher's export
# alike — and went into the append-only `window` sub-field, where `window-lane`
# can never resolve it: a live `#S:#I` always ends in an index, which is digits.
# So the value is held to `^.+:[0-9]+$`, the same form as the `<@id>` test
# below — a session part that is not empty, then digits and nothing else after
# the last `:`. AND IT CARRIES NO LINE BREAK: the regex's `.` matches a newline,
# so `junk<LF>s:1` passes it, and `log PAUSED` refuses a payload carrying a
# newline or a carriage return — the whole record, not the sub-field. So a
# value with either is dropped here, beside each regex check.
win="$(tmux display-message -p '#S:#I' 2>/dev/null)"
[[ "$win" =~ ^.+:[0-9]+$ ]] || win=""
case "$win" in *$'\n'*|*$'\r'*) win="" ;; esac
[[ -n "$win" ]] || win="${WORKBENCHES_CLAUDE_WINDOW_REF:-}"
[[ "$win" =~ ^.+:[0-9]+$ ]] || win=""
case "$win" in *$'\n'*|*$'\r'*) win="" ;; esac
wid="$(tmux display-message -p '#{window_id}' 2>/dev/null)"
[[ "$wid" =~ ^@[0-9]+$ ]] || wid="${WORKBENCHES_CLAUDE_WINDOW_ID:-}"
# AN `<@id>` IS `@<digits>` AND NOTHING ELSE (F-X13(a), A11 Addendum 4 ruling 10).
# `== @*` accepted anything starting with an at-sign, and two things that are
# not ids do: a tmux too old to know `#{window_id}` PRINTS THE FORMAT BACK, and
# a shim on PATH may print anything at all. Recording that string puts a lie in
# an append-only log — worse than an absence, because the sub-field then names a
# window `window-lane` can never resolve while looking complete. This is the
# same check the launcher makes on the same value (`claude-profile`'s own copy
# of this skill) and the one `lane-start:727` now makes.
[[ "$wid" =~ ^@[0-9]+$ ]] && win="${win:+$win }$wid"
# THE DROP, ON THE SAME VALUES `lane-start` REFUSES, BEFORE THE QUOTING — a test
# that ran after it would fire on the `"` the quoting adds itself.
refused=""
case "$win" in *', '*|*' — '*) refused="$refused window=$win"; win="" ;; esac
case "$dir" in *', '*|*' — '*|*'; '*|*'"'*) refused="$refused dir=$dir"; dir="" ;; esac
case "$dir" in *' '*) dir="\"$dir\"" ;; esac
[[ -z "$refused" ]] || printf 'DROPPED sub-field (not appended, and the line is still written):%s\n' "$refused"
# A MISSING `dir` IS SAID, NOT GUESSED AT (ruling 10). Where none of the three
# sources answered there is no sub-field, and the reader of this record is told
# which fact it will not carry rather than handed a plausible wrong one.
[[ -n "$dir" ]] || printf 'NO dir sub-field: %s, so the record is written without one (Amendment 11 clause (c)).\n' \
  "${dir_read_failed:-neither the lane log, the launcher nor this session record names the lane checkout}"
# A PROFILE NAME IS A MANIFEST KEY — letters, digits, `.`, `_`, `-` — and the
# shape check is also how `profile` gets SPEC rev 6 §5's `; ` rule without a
# token of its own: the pattern admits neither a `;` nor a space, so a value
# carrying either is omitted rather than written. A record with no `profile` is
# complete; one naming a profile `pclaude list` does not print is not.
profile_name="${CLAUDE_PROFILE_NAME:-}"
[[ "$profile_name" =~ ^[A-Za-z0-9._-]+$ ]] || profile_name=""
# AMENDMENT 17(b) — THE RECORD NAMES THE AGENT, in two sub-fields after
# Amendment 11(c)'s three:
#   agent       `claude`, `codex`, or the launcher's name for whatever wrote
#               the line — A MANIFEST KEY (letters, digits, `.`, `_`, `-`),
#               which is also how it gets SPEC rev 6 §5's `; ` rule without a
#               token of its own. `lane-start --agent <name>` reads it back to
#               know WHICH LAUNCHER to use with no flag, so a value this
#               pattern would not admit is a launch nobody can make.
#   transcript  the agent's own resumable id where it has one, else the word
#               `none` — which is an ANSWER and not a gap. For `claude` it is
#               this session's transcript uuid, the same id the row's session
#               cell ends on.
# `lanes-edit.sh`'s writer validates both and refuses the line rather than
# writing a sub-field no reader can use: this log is append-only.
agent_name="${LANES_AGENT:-claude}"
transcript_id="${uuid:-none}"
payload="swap"
[[ -z "$win" ]] || payload="$payload; window $win"
[[ -z "$dir" ]] || payload="$payload; dir $dir"
[[ -z "$profile_name" ]] || payload="$payload; profile $profile_name"
# `workstation <ws>` is NOT omitted the way `dir` and `profile` are, and that is
# the difference `R-A11-14` settles: those two say something about the lane, and
# this one is the KEY the records are filed under — a record without it is not
# incomplete, it is unfindable. So where there is none the register and log
# writes stop instead — (a), (b) and (c) below, all three (ruling 11, `R-A11-27`)
# — and what goes on is step 2's handoff, which is not one of them.
[[ -z "$ws" ]] || payload="$payload; workstation $ws"
payload="$payload; agent $agent_name; transcript $transcript_id"
# AND THE KIND, AFTER THEM (Amendment 17 Addendum 1 (h), in force
# 2026-09-14T20:59:31Z). `in-process` where the clear that follows keeps THIS
# process — a harness `/clear` — `respawn` where it does not (`/ctx`, `/exit`,
# a relaunch), and `unknown` where this act cannot know which will follow,
# which is a plain `/handoff`. `lane-handoff` writes the same sub-field, and a
# record from the skill that carried none would be a record no reader can tell
# a surviving writer from a dead one by. The same word goes in the line's FREE
# TEXT after the why — `clear in-process`, `clear respawn`, `kind unknown`.
kind="${kind:-unknown}"       # in-process | respawn | unknown
payload="$payload; kind $kind"
# THE OPERATOR'S WORDS, SANITIZED ONCE, AS `lane-handoff`'s `sanitize` DOES
# (#85): every line break is one `; `, CRLF first so that it is one and not
# two, and so is every ` — `. A why left empty is `handoff`, `lane-handoff`'s
# own word for it. The kind's word follows, as the free text carries it.
why_text="${why:-handoff}"
why_text="${why_text//$'\r\n'/; }"
why_text="${why_text//$'\r'/; }"
why_text="${why_text//$'\n'/; }"
why_text="${why_text// — /; }"
if [[ "$kind" == unknown ]]; then why_text="$why_text kind unknown"; else why_text="$why_text $kind"; fi
# BOTH RECORD WRITES BELOW CARRY THIS TEXT (#80 item 7). They used to carry the
# template's angle-bracket placeholders instead, for the operator's words and
# for what is open, so a block run as printed wrote the placeholders into two
# files nothing rewrites. `lane-handoff` hands both writes its computed text,
# and (b) is its line word for word where step 2's call exited 0. What is open
# is for the handoff's state line to say, as it is in `lane-handoff`'s record.
# (b)'S LAST PHRASE IS WHAT STEP 2 DID, NEVER A CLAIM (rv3's SHOULD 3 on #311):
# `$hf_record`, which step 2's two blocks set. A step 4 that step 2's outcome
# never reached (another shell, or a step 2 stopped before its call) says the
# handoff was NOT refreshed.
hf_record="${hf_record:-handoff NOT refreshed (step 2 left no outcome)}"

# (a) the Amendment 7 object-log PAUSED line — the record `swapped` reads.
# AMENDMENT 11 CLAUSE (e) — THE SKILL SUPPLIES THE UUID, AND `LANES_SESSION` IS
# HOW. The defect was never that the skill wrote `unknown`; it is that the skill
# HAS the uuid in hand ($uuid, bound in step 1 and written into the register's
# own PAUSED line two lines below) AND DOES NOT PASS IT, so `session_for()` fell
# to the row's last uuid and, for a row with none, to the literal — four such
# lines are in the append-only log in two lanes, and a log that may carry
# `unknown` in that field is a log clause (d) rule 3 cannot read as a resume
# target. One environment prefix is the fix; the writer's own refusal is the
# guard behind it, not the fix.
#
# AND THE SKILL'S OWN REFUSAL IS THE GUARD IN FRONT OF IT (`R-A11-5`: *"the skill
# refuses BEFORE it writes and says which act supplies the uuid"*). Step 2 set
# `$uuid_missing` where neither this session's id nor the row names a session —
# the rare case, because a running session always has the first — and there the
# writer would refuse (a) while (b) would read `session @<ws>`, the placeholder
# clause (e) keeps out of the log and `R-A11-14` out of this file. So neither is
# attempted, step 2 having said why and named the act. `lane-handoff` skips (b)
# the same way but still attempts (a) and prints the writer's refusal; the caller
# is told first here, which is the guard `R-A11-5` asks for. The row's state cell
# names no session and is still set below.
#
# (a) AND (b) ARE THE TWO WRITES A MISSING WORKSTATION STOPS (ruling 11), and
# the dispatcher guard would refuse them anyway — `lanes-edit.sh`'s dispatcher
# gates `log`, `append-line`, `set-row-state` and every other writer on a
# configured workstation (the list is the `case` above its `verify-row` arm; a
# line number here would be stale the next time a verb joined it). Skipping them here means the skill says WHY once, in its own
# words, instead of the helper saying it twice in the middle of a swap.
#
# EACH OF THE THREE WRITES CARRIES THE ACT (Y:5581, Y:5678): `LANES_ACT` and
# `LANES_EXPECT` as a prefix on its own call, the same scopes on all three,
# because (b) is `lane-handoff`'s W11 and (a) and (c) are its W9 and W12. Both
# are empty where the act has no base (a helper predating feature 007), which a
# helper and a files-mode register read as no act. Where the writes were held
# (`act_down`: the register could not be read, or an answer refused them) the
# block ended above, so none of the three is reached.
if [[ -z "$ws_missing" ]]; then
if [[ -z "$uuid_missing" ]]; then
wr_rc=0
LANES_ACT="$act_line" LANES_EXPECT="$act_scopes" LANES_LANE="$lane" LANES_SESSION="$uuid" "$L" log PAUSED "lane:$lane" \
  → "$payload" \
  "$why_text" || wr_rc=$?
[[ "$wr_rc" != 3 ]] || act_in_doubt "the object log's PAUSED line"
act_again_say "the object log's PAUSED line" "$wr_rc"
[[ "$wr_rc" != 69 ]] || act_w69=1
act_w9_rc="$wr_rc"
# (b) the LANES.md file-level line, the shape every prior PAUSED/RESUMED used.
# IT IS WRITTEN WHETHER OR NOT (a) COULD BE (A8(a) step 4, `R-A11-11`): a swap
# is never left unwritten, so a lane whose object line was refused still gets
# this line and the row's state cell, with the gap named in the handoff — EXCEPT
# where there is no uuid to name, which is the `$uuid_missing` that skips both.
# `LANES_LANE` NAMES THE LANE ON THIS WRITE AND ON (c)'S AS IT DOES ON (a)'S (Amendment
# 23 S2): a register write goes through the lane's own checkout, and `append-line` finds
# that lane from this variable first, so a line that names no lane with a row is not a
# write with no lane.
wr_rc=0
LANES_ACT="$act_line" LANES_EXPECT="$act_scopes" LANES_LANE="$lane" "$L" append-line "PAUSED — lane $lane, session $uuid@$ws, $(date -u +%Y-%m-%dT%H:%M:%SZ), $why_text; $hf_record" || wr_rc=$?
[[ "$wr_rc" != 3 ]] || act_in_doubt "the register's PAUSED line"
[[ "$wr_rc" != 3 ]] || act_also3=1
act_again_say "the register's PAUSED line" "$wr_rc"
[[ "$wr_rc" != 69 ]] || act_w69=1
fi
fi
# (c) the row: ONE WRITE, which sets the whole state cell (Amendment 13(a)).
# row_write_refused is what step 5 reads: empty on success, "1" the moment the
# write below does not land. The name is older than step 5's words: a 3 is not a
# refusal (Y:5700), so step 5 says the row write "may not be written", which is
# true of a refusal, a 3 and a write never sent alike.
# IT USED TO BE TWO WRITES AND BOTH WERE GUESSES AT A CELL THAT WAS A HISTORY:
# `replace-in-row` flipping the leading state word — found by grepping the row
# for `| WORD ·`, or `| WORD |` for a cell with no history after it, because the
# anchor had to occur exactly once — and then an `append-row-status` putting
# `PAUSED — <payload>` at the END of the same cell, so the row said PAUSED twice
# with a day of narrative between. The cell is now ONE PHRASE that
# `set-row-state` replaces: no anchor, no second write, and a row whose cell
# opens with anything at all takes the same call.
# FOUR THINGS THE CELL'S LINE MAY NOT CARRY, and `set-row-state` refuses all
# four: ` · ` (the phrase's own separator, spelled `; `), `|` (a cell boundary
# in the row, spelled `¦` — a `dir` or a launch flag may hold one), CR and LF (a
# row is ONE line of a table, so a newline would split it in two), and more than
# ratified decision O1's 240 characters. The cut is at 230 with the last partial
# WORD dropped, because `${s:0:n}` counts BYTES wherever the locale is not a
# UTF-8 one and a byte offset can land inside `—`, `·` or `→`. This is
# `cut_to_line` in `lane-start`, `lane-end` and `lane-handoff`, and it is kept
# in step with them — a copy that dropped one of the four would be refused by
# the writer where the command is not (Copilot round 4 on openRepoTools#82).
hs_line="${payload//$'\r'/ }"
hs_line="${hs_line//$'\n'/; }"
hs_line="${hs_line// · /; }"
hs_line="${hs_line//|/¦}"
if [[ ${#hs_line} -gt 230 ]]; then
  hs_line="${hs_line:0:230}"; hs_line="${hs_line% *} ..."
fi
row_write_refused=""
# AND (c) IS A REGISTER WRITE TOO, so a missing workstation stops it as well and
# says so ONCE rather than being refused twice by the helper. Ruling 11's
# *"still refreshes the handoff naming the gap"* is step 2's `write-handoff`, a
# write in the lane's own checkout that is no register write and is not one of
# the writes the helper refuses for want of a workstation; (c) is one. `#71`'s copy
# promised *"(c) below still runs"*, and against this repository's own
# dispatcher guard that promise is a write the helper refuses — so the promise
# is corrected here rather than repeated.
if [[ -n "$ws_missing" ]]; then
  row_write_refused=1
  echo "NOT WRITTEN: the row's state cell stays as it is, because every register write from a container with no \$LANES_WORKSTATION stops (clause (k) rule (d)). The handoff refreshed in step 2 names this gap, and step 5 prints the restart command with --lane, because a restart cannot resolve this lane from a row that was never set."
else
wr_rc=0
LANES_ACT="$act_line" LANES_EXPECT="$act_scopes" LANES_LANE="$lane" "$L" set-row-state "$lane" "PAUSED · $hs_line" || wr_rc=$?
if [[ "$wr_rc" != 0 ]]; then
  row_write_refused=1
  [[ "$wr_rc" != 3 ]] || act_in_doubt "the row's state cell"
  [[ "$wr_rc" != 3 ]] || act_also3=1
  act_again_say "the row's state cell" "$wr_rc"
  [[ "$wr_rc" != 69 ]] || act_w69=1
fi
fi
# THE 69 NOTE, ONCE (spec:692): after the third write, so a 69 from any one of the
# three prints it one time and not once per write. The writers' own stderr, above,
# says which write the register refused. Where none was sent, the note was printed
# above, where the block ended. UNDER A SEQ BASE THE NOTE IS `--late`'S ONLY WHERE THE
# OBJECT LOG'S PAUSED LINE ITSELF EXITED 69 OR WAS NOT SENT AND NO WRITE STOPPED THE ACT
# (lane 3, #165 6836816821, question 1, and 6837908956, question 4): `--late` writes that
# line alone and refuses 2 where the lane's last line is already a `PAUSED`. Where it
# landed, `act_69_landed_note` says to run the act again, as `lane-handoff`'s own note
# does; where it exited 3, `act_69_doubt_note` names the writer's printed rerun first and
# then the act again; where a write stopped the act (`act_stop`), the note says to run the
# act again, as the stop does. Off a seq base it is `--late`'s. Where the register's line
# or the row also exited 3 (`act_also3`), whichever note prints ends with the stop's own
# sentence, which names the rerun the writer printed for it and says to run it first.
if [[ -n "$act_w69" ]]; then
  case "$act_line" in
    ""|*@files) act_69_note ;;
    *) [[ -z "$act_also3" ]] || act_p69_also3=" A write of this act also exited 3 (the notes above): run the rerun the writer printed for it, which writes it once or finds it, before that."
       case "$act_w9_rc" in
         0)     act_69_landed_note ;;
         3)     act_69_doubt_note ;;
         ""|69) if [[ -n "$act_stop" ]]; then act_69_again_note; else act_69_note; fi ;;
         *)     act_69_again_note ;;
       esac ;;
  esac
fi
# A REFUSED WRITE ENDS THE BLOCK AND THE ACT (feature 007, T431; lane 3, #165 6834271321,
# on lane 4's question 3, and 6835210568, which rules question 4 for the skill alone:
# "the skill's stop uses 2 alone"; TP:5861-5864: the act exits with the code lane 4's
# arms give, "never 0"; the row `[skill-step-4-writes]`). Under a seq base a write that was
# sent and exited with any code but 0, 3 and 69 (a 2, a 75, any other) leaves this block at
# `act_stop`, and the block ends 2, whichever code or mix of codes the writes gave. It is not
# `lane-handoff`'s 75, because a 75 here would read as `act-begin`'s own (`NO PAUSED WRITES`,
# after which step 5 stands) and the session dispatches on the code; the writer's 75 stays
# printed in its own stderr, above. The line below says what the act then does not do: no
# `READY TO SWAP` and no restart command, and neither step 5 nor any act of step 6, as after
# the A2 refusal that ends the block 1. A 3 and a 69 keep their paths above, and so does
# every write under `@files` or after `act-begin`'s 2, where `act_stop` is never set and the
# block ends 0 as it did.
if [[ -n "$act_stop" ]]; then
  echo "THIS ACT STOPS: $act_stop_names exited with a code other than 0, 3 and 69 under a seq base (the writer's own words, and its own exit code, are above), so this block ends 2, whichever code that was. The handoff step 2 refreshed stands, and the lane stays as it is. Print no READY TO SWAP line and no restart command, and run neither step 5 nor any act of step 6. Run /handoff again from step 1, which takes a new base."
  if [[ -n "$act_d3" ]]; then
    echo "A write of this act also exited 3 (the IN DOUBT line above): run the rerun the writer printed for it, which writes it once or finds it, before you run /handoff again."
  fi
  exit 2
fi
```

**Under a seq base no write that did not end 0 is re-run by hand** (lane 3, #165 6779688808, Q11). Where one exits
anything but 0, 3 or 69, the block prints `RUN /handoff AGAIN FROM STEP 1` and no command: keep the writer's own words,
which are above it, say in the report which write and its code, and tell the operator to run `/handoff` again from
step 1, which takes a new base. After the third write the block then prints `THIS ACT STOPS` and **ends 2, whichever
code the writer gave, a 75 included** (lane 3, #165 6835210568, question 4: the skill's stop uses 2 alone; the writer's
own 75 stays printed in its own stderr, above the line). **That 2 ends the act,** as the 1 below does: print no `READY TO
SWAP` line and no restart command, run neither step 5 nor any act of step 6, and do not tell the operator the swap is
safe. A 75 that ends the block is therefore never a write's: it is `act-begin`'s, an identity read's or the walk's, the
`NO PAUSED WRITES` line says so, and step 5 stands after it (below). A 3 keeps the writer's rerun and a 69 the note,
below, and where a write of the act also exited 3, the stop's last line says to run that rerun before `/handoff` is run
again. Only where the block printed no
such line, under `@files` or after `act-begin`'s 2, does today's hand re-run stand: if (a) still exits 2 there, and its
words do not open `expectation:` (the paragraph below), re-run it with the free-text argument **dropped entirely** and
say so in the report:
the PAUSED line is what the launcher reads on restart, and step 4 is never left unwritten. If (c) is
refused — a rebase conflict, a push race, a row the writer calls ambiguous, anything `set-row-state` itself
reports — leave `row_write_refused` set and say so in the report; step 5 reads it, because a restart cannot
resolve this lane from a record that was never set to `PAUSED`.

**A 2 whose words open `expectation:` is NOT the free-text refusal** (the register's LR009): a scope the write
rested on, `row:`, `bind:` or `alias:` of this lane, was changed by another place after the base this block took.
Dropping the free text does not answer it, so it is not re-run with less. All three writes carry the same scopes,
so say in the report which of them were refused, with the scope and the other place's lane and verb as the writer
printed them, and that the lane changed under this swap. A `/handoff` run again from step 1 takes a new base and
reads who the lane is afresh, and under a seq base that 2 is a write that stopped the act, so the block ends 2 after
`THIS ACT STOPS` (above). A refusal above the writes, from the base or from the identity, wrote nothing at all: the base's
ends the block 1 and the identity's (its own `REFUSED` line, or Amendment 15(d)'s) ends it 2.

**A write that exits 3 is in doubt, not refused** (Y:5698; the register's in-doubt code). On primary the transaction
may or may not have committed, so the block goes on to the next write, as it does after any write that did not land,
and prints one line after the write: it exited 3, it may not be written, and the printed `LANES_WRITE_ID` rerun, which
writes it once or finds it, is what to run (off primary, where the writer prints no such rerun, the commit is local
and may already be on origin). The writers' own stderr is kept, so that rerun is printed above the line, and the block
adds no hint of its own beside it. Say in the report which of the three exited 3, and relay that rerun. A 3 from the
row write also sets `row_write_refused`, so that step 5 names the lane in the restart command, and step 5 then says
the row write may not be written, never that it was refused (Y:5700; lane 3, #165 6774499606, T431's question 1). Where
any write of the act exited 3 and a later one exits 69, the 69 note names that rerun first (below): the object log's own in
`act_69_doubt_note`, the register's line's or the row's in the sentence every note then ends with.

**A write that exits 69 prints the note, once** (spec:692: the three writes "SHALL exit 69 and then print a note"). The
block goes on to the next write, as after any write that did not land, and after the third prints the note of how
the record is completed later: the lane stays as it is, an interrupted swap, and whoever relaunches the lane runs
`lane-handoff --late --at <UTC> --lane <L>` from a shell, once the register answers and before the relaunch. It
prints one time whether one, two or all three writes exited 69, and the same one time where `act-begin`, a read or
the walk stopped them. **Under a seq base that note is `--late`'s only where the object log's `PAUSED` line itself exited
69 or was not sent and no write stopped the act** (lane 3, #165 6835210568, "the 69 note needs mending either way"; 6836816821,
question 1; 6837908956, question 4; `lane-handoff`'s `paused_69_landed_note`), because `lane-handoff --late` writes that line
alone and refuses 2 once the lane's last line is a `PAUSED`, and it never writes the file-level line or the row. In the other
cases the block prints `THE PAUSED RECORD IS INCOMPLETE` and names something else:

- **the first write exited 0** (it landed): the note says the object log's line is written, and to run `/handoff` again
  from step 1 once the register answers, which takes a new base (Y:5601);
- **it exited 3** (in doubt): the note names the writer's printed `LANES_WRITE_ID` rerun first, which writes the line once
  or finds it, and then `/handoff` again from step 1 (Y:5199, Y:5222), since a `--late` before that rerun would write a
  second line and one after it refuses;
- **a write stopped the act** (the first write's own 2, 75 or any other code, or a later write's beside a first write that
  exited 69 or was not sent; the block ends 2 after `THIS ACT STOPS`, below): the note says the line was not written and
  says to run `/handoff` again from step 1 once the register answers, which is what the stop's own line says too. A
  `--late` after a stop would write two `PAUSED` lines.

Say in the report which of the three exited 69 and which of these the note was, and in none of the three send the operator
to `--late`. Where the first write exited 69, or none was sent (`$uuid_missing`), and no write stopped the act, and where
`act-begin`, an identity read or the walk stopped the writes, the `--late` note stands. The writers' own stderr, above the note, names the refusal.

**Under a seq base, where the register's line or the row also exited 3, each of the four notes ends with the stop's own
sentence** (lane 3, #165 6837908956, "the 69 note names another write's 3 rerun first"; T429's `p69_also3`): "A write of this
act also exited 3 (the notes above): run the rerun the writer printed for it, which writes it once or finds it, before that."
Run that rerun first, relay it in the report, and only then run `/handoff` again: run before it, `/handoff` again would
append a second file-level line (Y:5224). The object log's own 3 is named by its own note, and off a seq base the notes keep
their words.

**A block that ends with a code held the writes** (lane 3, #165 6774499606, A2 and T431's question 2; REV-ACT2 S2).
Where `act-begin`, an identity read or the walk exited 69, 75 or 3, the block sent none of the three writes, printed
the note and ended with that code. The handoff step 2 refreshed stands and nothing of step 4 was written, so **the
swap goes on to step 5**: say in the report which code it ended with and which call it was, set
`row_write_refused=1`, and run step 5. Where an answer was not a base or a read failed any other way (`act-begin`'s
1 or 64, an exit 0 with no line or a malformed one, any walk code but 0, 69, 75 and 3), the block sent none, printed
the REFUSED line that names the verb and its code, then the note, and ended 1. **That 1 ends the act, as it does in
`lane-handoff`, which stops before its READY line:** print no `READY TO SWAP` line and no restart command, run
neither step 5 nor any act of step 6, say in the report the REFUSED line and the handoff step 2 refreshed, and tell
the operator to fix what the refusal names and run `/handoff` again.

**A 2 ends the act the same way** (lane 3, #165 6835210568, question 4: the skill's stop uses 2 alone). The block ends 2
where the identity, read again under the base, answered another lane or Amendment 15(d) refused it (its `REFUSED` line,
and nothing of step 4 was written), and where `THIS ACT STOPS` after a write that was sent and refused (the three writes
were tried). Print no `READY TO SWAP` line and no restart command, run neither step 5 nor any act of step 6, say in the
report which line it was, and tell the operator to run `/handoff` again from step 1, after fixing what a `REFUSED` line
names. So **step 5 runs after a block that ended 0, 3, 69 or 75, and after no other**, and a 75 that ends the block is
always one that held the writes (`NO PAUSED WRITES`), never a write's own: the writer's 75 stays printed in its stderr.

## 5. Print the restart command — one command, no menu

**Run this step only where step 4's block ended 0, 3, 69 or 75.** A block that ended 1 held the writes (A2) and the act
stopped after its note, and a block that ended 2 stopped it as well (the identity's `REFUSED` line, or `THIS ACT STOPS`
after a refused write; lane 3, #165 6835210568, question 4): after either, no `READY TO SWAP` line and no restart
command are printed (REV-ACT2 S2). After a 69, 75 or 3 the step stands, and its note says the row write "may not be
written".

```sh
if command -v lclaude >/dev/null 2>&1; then
  if [[ -n "${row_write_refused:-}" ]]; then
    restart_cmd="lclaude --lane $lane ${CLAUDE_PROFILE_NAME:-<profile>}"
  else
    restart_cmd="lclaude ${CLAUDE_PROFILE_NAME:-<profile>}"
  fi
else
  restart_cmd="pclaude --lane $lane ${CLAUDE_PROFILE_NAME:-<profile>}"
fi
restart_note=''
[[ -z "${row_write_refused:-}" ]] || restart_note=' (the row write may not be written; the lane must be named explicitly)'
printf 'READY TO SWAP — restart with: %s%s\n' "$restart_cmd" "$restart_note"
lane-start --help 2>/dev/null | grep -q -- '--confirm' \
  && echo 'restart stamps: written by lane-start (Amendment 8(d))' \
  || echo 'restart stamps: MANUAL, as the next session first act (Rule 3 / Amendment 6(c))'
# AND THE NAME THE NEXT SESSION COMES UP WITH — `R-A11-16` (A11 Addendum 3,
# ratified "a11 addendum 3 yes"), brought here by A11 Addendum 4 ruling 10
# because `opensoft/workBenches#74` deletes the copy the ruling was written
# into. THE ACT STAYS AND ITS PREMISE HAS MOVED, because the estate overtook it.
#
# THE TRUE PREMISE: `lane-start` names EVERY session it launches. Adoption act 0
# merged as `opensoft/brett-wip#5` @`3719d97` — "--name on every launch" — and at
# that commit `lanes/lane-start:846`, `:855` and `:866` all carry
# `--name "$LANE"`: the two branches that RESUME as well as the one that
# CREATES. So a restart that reaches `lane-start` comes up named for the lane
# and this line says nothing at all.
#
# WHAT IT IS STILL FOR is the session that comes up WITHOUT `lane-start`: the
# launcher's two documented degradations — no `lane-start` on PATH (Evidence 5)
# and a `lane-start` that refused, both of which start bare Claude in the same
# window — a `claude` typed by hand, and a workstation whose `lane-start`
# PREDATES `3719d97`, because the fix is in a checkout and not in the air. Those
# come up with the name the harness DERIVED (`openrepoproject-b9`, Evidence 4),
# and a lane whose messaging address (Amendment 2) is a derived name is a lane
# nobody can address.
#
# WHICH ACT REMOVES THIS LINE: none is scheduled, and that is why it is printed
# CONDITIONALLY rather than always — it is fenced on *if its name is not the
# lane*, and that test is the whole of it. There is no API to rename a running
# session from inside, but a keystroke is not an API, and Amendment 12's name
# guard sends it: the `SessionStart` hook (`lanes-edit.sh session-start`) and the
# `UserPromptSubmit` guard (`lanes-edit.sh guard`) TYPE `/rename <lane>` into the
# session's own tmux pane. So the session that comes up outside `lane-start` is
# usually renamed for the person, and the operator's `/rename <lane>` is the
# FALLBACK for where the guard has not run or could not type — hooks not
# installed, a pane that is not running `claude`, tmux not answering.
echo 'then, in the session that comes up: if its name is not the lane, type /rename <lane> (lane-start names every session it launches, the resume branches included, since adoption act 0 landed as opensoft/brett-wip#5 @3719d97; a session that came up WITHOUT it — a missing or refusing lane-start, a bare claude, or a workstation whose lane-start predates that commit — carries the name the harness derived, and no API renames one from inside)'
```

That one command is the whole restart: `lclaude <profile>` resolves this lane from the window name,
and from the swap record step 4 just wrote when the window is gone (Amendment 8(c)). **The SHORT form is
the printed one, and that is an edit to in-force text rather than a preference**: Amendment 11 clause (a) —
*"Every printed restart command becomes the short form … Amendment 8(a) step 5's prescribed
`pclaude run <profile>` becomes that short form wherever it is printed"* — which the amendment counts as
**edit 5 of six**. The verb was always optional and nothing breaks: the short and the long form build the
SAME argv (`claude-profile`'s `action="${1:-list}"` falls through to `run` on any first word that is not
`list|login|status|run`, without shifting), and the long form is not deprecated. What changes is what this
file prints. The profile argument is the only part the operator changes, and only when switching accounts.

The fallback for an older installation without `lclaude` is explicit `pclaude --lane <lane> <profile>`;
bare `pclaude` is profile-only on updated installations. With `lclaude`, **`--lane <lane>` is printed only
where step 4's row write may not have been written** — it was refused, it exited 3, or none was sent, and step 5 says
"may not be written" in every case, never "refused" (Y:5700) — so the row may never have been set to
`PAUSED`, a restart cannot resolve this lane from it, and the operator must name it explicitly. `--lane`
is a **leading** option to `claude-profile`, read before the action or the profile — measured in the
launcher itself, *"the first token that is not one of them ends this loop"* — so it goes BEFORE the profile
and never after it: `pclaude <profile> --lane <lane>` would be handed to Claude itself, not to the
launcher, and the lane would never be taken. The capability probe above decides whether the RESUMED stamps
are `lane-start`'s act or the next session's — do not assert either from memory.

**`/resume` and `claude --resume <title>` are not lane surfaces** (A8 Addendum 2, R-A8-6): a lane is entered
through `lclaude`, explicit `pclaude --lane`, or `lane-start`, and by no other door. Do not offer either as a fallback.

## 6. The end this handoff has — and the record comes first, always

Steps 1–5 are the whole act for a plain `/handoff`. The two flags add ONE act each, **after** the record,
and both refuse where step 4's `PAUSED` line did not land: *"a `/ctx` whose record could not be written
REFUSES before it kills anything (a pane is never respawned over an unrecorded lane)"* (Amendment 17(f)).
**Neither act runs where step 4's block ended 1 or 2** (step 5's gate: the act stopped there and printed no `READY TO
SWAP` line, and a `/exit` typed after it would end the session over a record that was refused or never written).
**And `/exit` is typed only where `lane-handoff --exit`'s own gates would let it pass** (lane 3, #165 6836816821, question 3;
6837908956, question 5; RC-W15c's SHOULD). The gates are step 4's three writes, which are `lane-handoff`'s W9, W11 and W12.
**Whatever the base, `/exit` is withheld where the row's write did not end 0 (`row_write_refused` is set),** since
`lane-handoff --exit` refuses an unflipped row in every mode, and where the object log's `PAUSED` line did not land or is in
doubt (the rule above). Under a seq base it is withheld where (b), the register's `PAUSED` line, exited 69 too. Step 6 needs
no base for that: its one seq-only gate, (b)'s 3 and 69, shows in what only a SQL register prints, a 69 or a 3 with a
`LANES_WRITE_ID` rerun printed above its line (Y:5200, Y:5746), and step 4's block prints nothing of its base. Each of those
leaves part of the record unwritten or in doubt, the lines above say what to do about it, and `/exit` would end the session
that is told to do it. **Where (b) exited 3 and the other gates pass, the rerun the writer
printed for it is run BEFORE `/exit`, and `/exit` is typed only if that rerun ends 0** (lane 3, #165 6835210568, question
1, and 6836816821, question 3: W11's 3, which `lane-handoff`'s `--exit` refuses 2 for under a seq base, T429). `/exit` ends
the session that holds that rerun, and the handoff's top block was written before the writes, so the next session never sees
it; a rerun that ends 3, 69, 75 or 2 settles nothing. **On any other code the pane is left as it is and no `/exit` is
typed: say in the report the rerun and its code.** Where `/exit` is withheld at any other gate, say in the report which write
exited which code, and what its note or its `IN DOUBT` line says to do. Say in the report what the rerun printed.

**`/ctx` (`/handoff --restart`) — the context clear, and the person types nothing else.** IT IS ONE COMMAND
AND THIS STEP DOES NOT SPELL IT OUT IN SHELL:

```sh
unset LANES_ACT LANES_EXPECT      # a launch inherits nothing of step 4's act: the session and its guard would carry it
lane-handoff --restart "$why"
```

**THE TMUX RECIPE THAT USED TO BE HERE IS GONE, AND `opensoft/openRepoTools#94` IS WHY.** This step used to
carry an executable respawn — `tmux respawn-pane -k -t "$pane" "LANE_START_FRESH=1 lane $lane"` — for a
session to run itself. On 2026-09-15T20:59Z that is what ran, with two extra environment assignments the
model added on the spot, and what came up in the pane was `claude --name <lane> --resume <the uuid the
handoff had just paused>`: the same conversation resumed by id, not a fresh session primed by the block
step 2 had just written, and no process left in the pane to notice. Two things were wrong and only one of
them was the recipe:

- **`LANE_START_FRESH=1` is an ENVIRONMENT seam and it does not cross the launcher.** `claude-profile`
  re-creates its child through tmux, and a command tmux starts gets the tmux SERVER's environment, not the
  caller's — the launcher's own code says so and threads six values into the command string for exactly
  that reason. The fresh-session requirement was not one of them. It is now a RESTART INTENT written to
  disk under the lane's own control root before anything is killed, and `lane-start` reads it back whatever
  the environment did.
- **A prose recipe is a second implementation of the destructive tail.** Two copies of one procedure that
  must stay byte-equal is the rejected alternative everywhere else in this file, and the one place it was
  allowed is the one place a session kills its own pane.

So the whole of `/ctx`'s end is the one command above, and `lane-handoff` owns it: the restart intent
written and read back as a FOURTH gate beside the `PAUSED` line, the row and the handoff; the pane
respawned with `lane-handoff --supervise --lane <lane> --operation <id>` **by absolute path**; the
supervisor claiming that intent, running the launch as its CHILD through the launcher, confirming the
replacement came up, and STAYING IN THE PANE with a diagnostic and a retry when it did not.

**WHAT TO DO WITH WHAT IT PRINTS.** Exit 0 is the pane handed over — this session is about to be killed by
the command it just ran, and there is nothing after it. **Exit 1 is a read that failed, which is never "nothing to
report" (Amendment 7(d)), or the act refused by A2** (feature 007; lane 3, #165 6774499606): `act-begin` answered
with anything but a base, 69, 75, 3 or an old helper's 2, or the walk of `canon-lane` with anything but a name, 69,
75 or 3. The handoff file is written and none of the `PAUSED` record's writes was sent; the 69 note is printed, and
no `READY` line, restart intent, respawn or `/exit` follows. Exit 2 is a REFUSAL and this pane is exactly as it
was: read the line, it names which of the four writes did not land, or says a restart is already in flight
(`lane-handoff --restart-status --lane <lane>` reads that one), or that tmux would not take the pane. **A 2 or a
75 whose line says the act stops there, and names the writes, is the stop under a seq base** (feature 007; lane 3,
#165 6834271321 and 6835210568, question 3): a write of the `PAUSED` record (the object log's line, the
register's line or the row's cell, W11's included) was sent and refused, so the act ends after the handoff file
with no `READY` line, restart intent, respawn or `/exit`, and the lane is not recorded SWAPPED. It is 75 only where
every write that stopped it gave 75 and none of the act's writes exited 3 (a 3 is in doubt, never "busy"), and 2
otherwise; where a write also exited 3, the line says to run that write's printed rerun first. **For that 1 and
that stop alike nothing was started and no restart line was printed, so there is none to fall back to:** read the
line, fix what it names (or wait for the register to answer, after a 75), and run `lane-handoff --restart` again
from its start, which takes a fresh base and supersedes the operation it left. **Every OTHER refusal says in its own
line what had landed, and where it stands decides what to do.** One before the `READY` line (an identity or ownership
refusal, a restart that another operation already owns, the window rename that did not take) prints no restart line,
and nothing of the `PAUSED` record had been written: its line says what to fix, and to read `lane-handoff
--restart-status --lane <lane>` where a restart owns the lane, or to run the same command again. A gate after the
`READY` line leaves the pane as it is and has printed the restart line, but the record is not always written. **Run every
rerun the line names first, in the order it names them** (under a seq base the gate that refuses first names the printed
rerun of every write of the act that exited 3, W9's, W11's and W12's in that order, since the gates behind it never run;
lane 3, #165 6837908956, T429's questions 1 to 3), and then take the way out it gives: where it says the `PAUSED` record is
in doubt or was NOT written, settle that, as it says, and where it says the row or the handoff was not set, or that the
file-level line was NOT appended (its write exited 69), settle that, then run `--restart` again or restart by hand with the printed line, as it says. **Where it says the file-level line may not be written (its
write exited 3), run the rerun the writer printed for it and then restart by hand with the printed line, never `--restart`
again:** that run would append a second line, since the line carries a UTC of its own (Y:5224), and the printed rerun is the
only one that finds the first (Y:5222). Only where the record, the row and the handoff are written and the pane was still not taken (the
restart intent could not be written or read back, the supervisor could not be found, tmux refused the pane) is the
printed restart line the fallback, and never a second `--restart`; a restart already in flight is read with
`lane-handoff --restart-status --lane <lane>` first.

**`lane <name>` IS STILL A PERSON'S DOOR AND IS NO LONGER THIS ONE** (Amendment 18 Addendum 2 (i-8) names
two doors: `lane <name>`, *"or through the launcher directly"*). The supervisor takes the second, because
`lane` is a HUMAN DISPATCHER whose valid outcomes include attaching to a live session without launching
anything — and because it was the door #94 came through. The clause's own ground is kept: *"no word is
kept on `PATH` for it alone"*, and none is — the supervisor is a mode of `lane-handoff`, which is already
installed.

**`/ctx` SAYS WHICH IT DID** (Addendum 1 (j)). The respawn above replaces the pane's process, so every writer
of this lane dies with it: the kind is `respawn`, and the count the next session makes first then finds none,
which is what makes relaunching each one right. If what is about to happen is an IN-PROCESS clear instead
(the harness's own `/clear`, which mints a new transcript id in the SAME process), the writers LIVE THROUGH
IT: write the record with `lane-handoff --in-process` (or the same two texts by hand), the kind is
`in-process`, and the block tells the next session to EXPECT every writer below live. Either way the block
carries clause (i)'s first line, because **the kind says what to expect and never what to do**. **Never
relaunch a writer that is still live** — a worktree is one writer's for as long as that writer is live
(clause (k)), and that is what this lane measured on 2026-09-14.

**`/handoff --exit requested by <uuid>@<host>/<container>` — the handoff another place asked for.** After
the record, `/exit` is typed into this lane's own pane (Amendment 12's M1, the one mechanism there is), and
the session ENDS: *"a handoff to another place is a handoff and not a restart"* (Amendment 18(d)). The `why`
is the requester, verbatim. `/exit` is typed only where the gates in the lead above let it pass (whatever the base, a row
write that did not end 0 withholds it, and under a seq base so does (b)'s 69), and where step 4's (b) exited 3, only after the
rerun it printed has run and ended 0.

```sh
tmux send-keys -t "$pane" '/exit' Enter
```

**`lane-handoff --late --at <UTC>` — the record a swap never left.** A session that died at a usage limit
wrote no `PAUSED`, and the lane's log still reads as running. The late record closes it, and **it is written
from a shell BEFORE the relaunch**: this log is append-only and FILE ORDER is what every state read means by
"last", so a `PAUSED` appended after the relaunch's `RESUMED` would make a lane that is RUNNING read as
paused. `lane-handoff --late` therefore requires `--at <UTC>` — the moment the old session ended, which is
what dates the line — and refuses unless the lane's last lane-kind line is a `STARTED` or `RESUMED` older
than that instant. Run from inside the session that has already been resumed, it refuses and says so: the
honest record of the state that session holds is its own next `/handoff`.

```sh
lane-handoff --late --at 2026-09-14T12:02:27Z "late; usage limit hit before the swap"
unset LANES_ACT LANES_EXPECT                     # a launch inherits no act's base or scopes (feature 007)
lclaude "${CLAUDE_PROFILE_NAME:-<profile>}"      # and only then; use pclaude --lane <lane> if lclaude is unavailable
```
