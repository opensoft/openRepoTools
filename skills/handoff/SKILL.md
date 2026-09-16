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

**THE FLAGS ARE ENDS, NOT SECOND KINDS OF RECORD.** Every one of them runs steps 1–5 first:

| | what it adds after the record | when |
|---|---|---|
| `/handoff [why]` | nothing — the restart line is printed and the person types it | a swap, a reset, a switch |
| `/ctx`, `/handoff --restart` | the lane's own pane is respawned through the launcher, the new session's first prompt being this handoff's top block (Amendment 17(f)) | a context clear: *"the one word is the whole act"* |
| `/handoff --exit [requested by …]` | `/exit` is typed into this lane's own pane, because a handoff to ANOTHER PLACE is a handoff and not a restart (Amendment 18(d)) | the bound session answering another place's `HANDOFF-REQUESTED` |
| `lane-handoff --late --at <UTC>` | nothing — it writes the record a swap NEVER LEFT, from a shell, BEFORE the relaunch | a session that died at a usage limit with no swap |

**A `/ctx` WHOSE RECORD COULD NOT BE WRITTEN REFUSES BEFORE IT KILLS ANYTHING** (Amendment 17(f)): a pane is
never respawned over an unrecorded lane, and a session is never ended without one.

Run every step, in order, before telling the operator it is safe to reset usage or switch profiles. `$L`
below is the symlink Amendment 5 left in place; every command is copy-pasteable as written once `lane` is
derived in step 1. **From a shell, `lane-handoff` is these same steps as one command** — it is the same act
and writes the same record; a session runs the steps here because a session can message its subagents and a
shell cannot.

```sh
L=~/projects/xFactory/lanes-edit.sh

# EVERY READ IN STEP 1 GOES THROUGH THIS ONE FENCE, and Amendment 7(d) is the
# whole of it: `0` an answer · `8` NO ANSWER · `2` a helper predating the read —
# both of those fall to the next rung — and ANYTHING ELSE is a read that FAILED,
# which is neither of them (#26, the review of `c3ebcfe`, this file's `:28` and
# `:72`). All three of step 1's reads collapsed every code into the ordinary
# case, and what is beneath them is not a refusal: it is THE NEXT RUNG, and the
# last rung is the workstation's NEWEST SWAP — a different lane. A register that
# could not be read is not "this window is not a lane", and step 4 would then
# write a PAUSED record, a stamp and a restart command for a lane this window
# is not.
#
# IT IS `/restart`'s `lread` WITH ONE DIFFERENCE, STATED RATHER THAN LEFT TO BE
# FOUND: step 4's `dir` read does NOT come through here, because this fence
# STOPS and that read may not — `R-A11-11`, *a swap is never left unwritten*.
# It drops the sub-field and names the read instead, where it stands.
#
# IT SETS A VARIABLE RATHER THAN PRINTING ITS ANSWER, and that is load-bearing:
# a refusal inside `$( )` kills only the substitution's subshell and the skill
# would carry on with an empty answer.
sread() {                      # sread <var> "<what the failure is NOT>" <verb> [args…]
  sr_var="$1"; sr_not="$2"; shift 2
  sr_out=""; sr_rc=0
  sr_out="$(LANES_NO_FETCH=1 "$L" "$@" 2>/dev/null)" || sr_rc=$?
  case "$sr_rc" in
    0)   : ;;
    8|2) sr_out="" ;;
    *)   printf 'REFUSED: `%s %s` failed (exit %s). That is NOT %s — a read that failed is never an answer (Amendment 7(d)), and this skill will not bind a lane, write a PAUSED record or print a restart command on one. Run it by hand to see what it says.\n' \
           "$L" "$1" "$sr_rc" "$sr_not" >&2
         exit 1 ;;
  esac
  eval "$sr_var=\$sr_out"
}
```

## 1. Usage, then the identity triple — derived, not asked

```bash
claude-usage
window="$(tmux display-message -p '#W')"                     # Amendment 8(b): the window IS the lane
lane="$window"
sread row_probe "'this window is not a lane'" register-row "$lane"
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
# register and the logs; step 2's handoff commit is a commit in the LANE'S OWN
# repository and is not one of them. Clause (e)'s shape for a fact a writer
# cannot carry is *"the gap named in the handoff"*, and that is what happens
# here: `$ws_missing` is carried to step 2, which names it, and to step 4, which
# skips (a) and (b) and still does (c).
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
  wl_ref="$(tmux display-message -p '#{window_id}' 2>/dev/null)"
  [[ -n "$wl_ref" ]] || wl_ref="$(tmux display-message -p '#S:#I' 2>/dev/null)"
  sread candidate "'no lane is bound to this window'" window-lane "$ws" "$wl_ref"
  [[ "$candidate" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*$ ]] && lane="$candidate"
fi
if [[ -z "$lane" ]]; then
  # The swap record, read exactly as the launcher reads it: the STATUS decides
  # whether there is an answer at all, and the contract is the tab. A row that
  # printed before a failed read, or one with no tab, is not a record row —
  # `cut -f 1` would hand back the whole line, lane-shaped and wrong.
  sread rows "'this workstation has no swap record'" swapped "$ws"
  first="$(printf '%s\n' "$rows" | head -n 1)"
  if [[ -n "$rows" && "$first" == *$'\t'* ]]; then
    candidate="${first%%$'\t'*}"
    [[ "$candidate" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*$ ]] && lane="$candidate"
  fi
fi
printf 'lane=%s\n' "${lane:-<none>}"
```

The window name answers first, the window's own RECORD second and the workstation's newest swap third —
the launcher's own order, with Amendment 11 clause (b)'s new zero-question step in the middle, so the skill
and the launcher never disagree about which lane this is. Then make the other two names match it, mechanically:

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

The handoff path is the row's own handoff column. Derive it; do not guess it — and read the row FETCHED,
because this decides state (Amendment 7's read-after-fetch rule governs it; step 1's window/record probe is
the only no-fetch read this skill makes):

```sh
row="$("$L" register-row "$lane" 2>/dev/null | grep '^|' | tail -n 1)"
# The handoff path is the row's SIXTH column: awk field 7, because $1 is the empty string before the
# leading pipe — lanes-edit.sh's own row_cell/handoff_of_lane convention. NEVER count back from NF: this
# lane's own row alone carries 27 fields today, every extra one of them in the state history to the RIGHT
# of the handoff column, so `$(NF-2)` landed on the empty string and this step used to `git add ""` and
# commit nothing — silently, in the one step Amendment 6(e) exists for.
handoff="$(printf '%s' "$row" | awk -F'|' '{print $7}' | awk '{$1=$1};1')"
uuid="$(printf '%s' "$row" | awk -F'|' '{print $3}' \
  | grep -o '[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{12\}' | tail -n 1)"
printf 'handoff=%s\nuuid=%s\n' "${handoff:-<none>}" "${uuid:-<none>}"
```

If `$handoff` came back empty, **stop here** — this row does not split the way `row_cell` expects, a
`git add ""` below commits nothing while looking like it worked, and Amendment 6(e) exists for exactly this
step. Read the row's own text by hand and take its handoff token; do not guess one.

`$uuid` is the **last** id in the session cell — this session, and the only one Amendment 6(b) calls the
lane's. Rewrite the handoff's state line, **every word given and not yet executed**, and the resume prompt;
a stale handoff is how given words die with the session (Amendment 6(e)).

**THE TOP BLOCK'S TEMPLATE GAINS A `WRITERS` SECTION AND A FIRST LINE** (Amendment 17(f): the block *"LISTS
EVERY WRITER THE LANE HAS RUNNING (its worktree, its branch, its brief, what it had committed)"*, as
**Addendum 1 (i)** reads that section — *"a list to COUNT, not a list to relaunch"*, in force 2026-09-14T20:59:31Z).
Write it exactly this shape, and prepend it — a handoff is the one document in this protocol whose purpose is
to be read by a later session, so nothing below is rewritten and everything already there stays as history
under a `---` rule:

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

**If step 1 set `$ws_missing`, THE HANDOFF IS WHERE THE GAP IS NAMED** (A11 Addendum 4 ruling 11, clause
(e)'s shape for a fact a writer cannot carry). Say in the state line, in as many words, that this session ran
in a container with no `LANES_WORKSTATION`, that step 4's register and object-log writes were therefore NOT
made, and that the row still reads as it did — so the next session knows the register is behind its own
handoff rather than believing the lane never paused. This commit is in the LANE'S OWN repository and is not
one of the writes that stop. Commit with an explicit pathspec
and the Rule 5 `Lane:` trailer, then pull-rebase and push:

```sh
cd ~/projects/brett-wip
git add "$handoff"
git commit -m "handoff(<lane>@<ws>): PAUSED, <one-line state>" -m "Lane: <lane>"
git pull --rebase && git push
```

On a rebase conflict: abort, leave the tree clean, report it, and never force.

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

First sanitize the operator's words **once**: replace every ` — ` with `; `. Amendment 7(b)/R26 refuses any
payload or free text containing ` — ` (exit 2), because that separator is what divides a line's fields from
its free text.

```sh
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
win="$(tmux display-message -p '#S:#I' 2>/dev/null)"
case "$win" in *:[0-9]*) : ;; *) win="" ;; esac
[[ -n "$win" ]] || win="${WORKBENCHES_CLAUDE_WINDOW_REF:-}"
case "$win" in *:[0-9]*) : ;; *) win="" ;; esac
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
# incomplete, it is unfindable. So where there is none the two WRITES stop
# instead (ruling 11), and (c) below still runs.
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
why_text="$why"
if [[ "$kind" == unknown ]]; then why_text="$why kind unknown"; else why_text="$why $kind"; fi

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
# (a) AND (b) ARE THE TWO WRITES A MISSING WORKSTATION STOPS (ruling 11), and
# the dispatcher guard would refuse them anyway — `lanes-edit.sh`'s dispatcher
# gates `log`, `append-line`, `set-row-state` and every other writer on a
# configured workstation (the list is the `case` above its `verify-row` arm; a
# line number here would be stale the next time a verb joined it). Skipping them here means the skill says WHY once, in its own
# words, instead of the helper saying it twice in the middle of a swap.
if [[ -z "$ws_missing" ]]; then
LANES_LANE="$lane" LANES_SESSION="$uuid" "$L" log PAUSED "lane:$lane" \
  → "$payload" \
  "on <operator>'s word: <sanitized verbatim>"
# (b) the LANES.md file-level line, the shape every prior PAUSED/RESUMED used.
# IT IS WRITTEN WHETHER OR NOT (a) COULD BE (A8(a) step 4, `R-A11-11`): a swap
# is never left unwritten, so a lane whose object line was refused still gets
# this line and the row's state cell, with the gap named in the handoff.
"$L" append-line "PAUSED — lane $lane, session $uuid@$ws, $(date -u +%Y-%m-%dT%H:%M:%SZ), on <operator>'s word \"<sanitized verbatim>\"; <what's open, or NOTHING CLAIMED>; handoff refreshed"
fi
# (c) the row: ONE WRITE, which sets the whole state cell (Amendment 13(a)).
# row_write_refused is what step 5 reads: empty on success, "1" the moment the
# write below does not land.
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
# *"still refreshes the handoff naming the gap"* is step 2's commit, which is in
# the LANE'S OWN repository and is not a register write; this is. `#71`'s copy
# promised *"(c) below still runs"*, and against this repository's own
# dispatcher guard that promise is a write the helper refuses — so the promise
# is corrected here rather than repeated.
if [[ -n "$ws_missing" ]]; then
  row_write_refused=1
  echo "NOT WRITTEN: the row's state cell stays as it is, because every register write from a container with no \$LANES_WORKSTATION stops (clause (k) rule (d)). The handoff refreshed in step 2 names this gap, and step 5 prints the restart command with --lane, because a restart cannot resolve this lane from a row that was never set."
else
"$L" set-row-state "$lane" "PAUSED · $hs_line" || row_write_refused=1
fi
```

If (a) still exits 2, re-run it with the free-text argument **dropped entirely** and say so in the report:
the PAUSED line is what the launcher reads on restart, and step 4 is never left unwritten. If (c) is
refused — a rebase conflict, a push race, a row the writer calls ambiguous, anything `set-row-state` itself
reports — leave `row_write_refused` set and say so in the report; step 5 reads it, because a restart cannot
resolve this lane from a record that was never set to `PAUSED`.

## 5. Print the restart command — one command, no menu

```sh
if [[ -n "${row_write_refused:-}" ]]; then
  restart_cmd="pclaude --lane $lane ${CLAUDE_PROFILE_NAME:-<profile>}"
  restart_note=' (row write was refused; the lane must be named explicitly)'
else
  restart_cmd="pclaude ${CLAUDE_PROFILE_NAME:-<profile>}"
  restart_note=''
fi
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
# session from inside, so wherever a session comes up outside `lane-start` the
# operator's `/rename <lane>` is the only act there is.
echo 'then, in the session that comes up: if its name is not the lane, type /rename <lane> (lane-start names every session it launches, the resume branches included, since adoption act 0 landed as opensoft/brett-wip#5 @3719d97; a session that came up WITHOUT it — a missing or refusing lane-start, a bare claude, or a workstation whose lane-start predates that commit — carries the name the harness derived, and no API renames one from inside)'
```

That one command is the whole restart: bare `pclaude <profile>` resolves this lane from the window name,
and from the swap record step 4 just wrote when the window is gone (Amendment 8(c)). **The SHORT form is
the printed one, and that is an edit to in-force text rather than a preference**: Amendment 11 clause (a) —
*"Every printed restart command becomes the short form … Amendment 8(a) step 5's prescribed
`pclaude run <profile>` becomes that short form wherever it is printed"* — which the amendment counts as
**edit 5 of six**. The verb was always optional and nothing breaks: the short and the long form build the
SAME argv (`claude-profile`'s `action="${1:-list}"` falls through to `run` on any first word that is not
`list|login|status|run`, without shifting), and the long form is not deprecated. What changes is what this
file prints. The profile argument is the only part the operator changes, and only when switching accounts.

**`--lane <lane>` is printed only where step 4's row write was refused** — the row was never set to
`PAUSED`, so a restart cannot resolve this lane from it and the operator must name it explicitly. `--lane`
is a **leading** option to `claude-profile`, read before the action or the profile — measured in the
launcher itself, *"the first token that is not one of them ends this loop"* — so it goes BEFORE the profile
and never after it: `pclaude <profile> --lane <lane>` would be handed to Claude itself, not to the
launcher, and the lane would never be taken. The capability probe above decides whether the RESUMED stamps
are `lane-start`'s act or the next session's — do not assert either from memory.

**`/resume` and `claude --resume <title>` are not lane surfaces** (A8 Addendum 2, R-A8-6): a lane is entered
through `pclaude` or `lane-start`, and by no other door. Do not offer either as a fallback.

## 6. The end this handoff has — and the record comes first, always

Steps 1–5 are the whole act for a plain `/handoff`. The two flags add ONE act each, **after** the record,
and both refuse where step 4's `PAUSED` line did not land: *"a `/ctx` whose record could not be written
REFUSES before it kills anything (a pane is never respawned over an unrecorded lane)"* (Amendment 17(f)).

**`/ctx` (`/handoff --restart`) — the context clear, and the person types nothing else.** IT IS ONE COMMAND
AND THIS STEP DOES NOT SPELL IT OUT IN SHELL:

```sh
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
the command it just ran, and there is nothing after it. Exit 2 is a REFUSAL and this pane is exactly as it
was: read the line, it names which of the four writes did not land, or says a restart is already in flight
(`lane-handoff --restart-status --lane <lane>` reads that one), or that tmux would not take the pane. In
every refusal the record is already written, so the fallback is the printed restart line and never a second
`--restart`.

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
is the requester, verbatim.

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
pclaude <profile>      # and only then
```
