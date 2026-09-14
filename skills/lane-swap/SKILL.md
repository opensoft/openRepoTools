---
name: lane-swap
description: "/lane-swap (alias /swap) prepares this lane for a usage reset or profile switch. It fixes the identity triple, refreshes the handoff, polls the writers, writes the swap record with the window, the lane's directory and the profile, and prints the one restart command (lane-collision-protocol Amendment 8(a), amended by Amendment 11)."
---

<!-- PROMPTS TO THE PERSON: 1 — step 3, and only when a writer still holds
     unpushed work and has not replied. It was 3 before A8 Addendum 2 (R-A8-7):
     the identity fix, the row's leading state word and the restart command are
     all DERIVED here now, and step 5 prints one command, never a menu. If a
     step below cannot derive something, it stops and says so — it does not ask. -->

# `/lane-swap` — pause this lane for a reset or profile switch

Lane-collision-protocol Amendment 8(a). Run every step, in order, before telling the operator it is safe to
reset usage or switch profiles. `$L` below is the symlink Amendment 5 left in place; every command is
copy-pasteable as written once `lane` is derived in step 1.

```sh
L=~/projects/xFactory/lanes-edit.sh
```

## 1. Usage, then the identity triple — derived, not asked

```bash
claude-usage
window="$(tmux display-message -p '#W')"                     # Amendment 8(b): the window IS the lane
lane="$window"
LANES_NO_FETCH=1 "$L" register-row "$lane" >/dev/null 2>&1 || lane=""
# THE WORKSTATION COMES FROM CONFIGURATION, NEVER FROM `hostname` (Amendment 11,
# ratified decision 8(d), from Evidence 6): a forked orchestrator wrote a bench
# container's id into a register whose every other row says `Eagle`, and a row
# on a workstation that does not exist is a row no reader can match. `$L`'s own
# `workstation` read is the one implementation; its second tab-separated field
# says which rung answered.
ws_pair="$("$L" workstation 2>/dev/null)"
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
ws_missing=""
if [[ "${ws_pair##*	}" == container-unset || -z "$ws" ]]; then
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
  candidate="$(LANES_NO_FETCH=1 "$L" window-lane "$ws" "$wl_ref" 2>/dev/null)" && \
    [[ "$candidate" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*$ ]] && lane="$candidate"
fi
if [[ -z "$lane" ]]; then
  # The swap record, read exactly as the launcher reads it: the STATUS decides
  # whether there is an answer at all, and the contract is the tab. A row that
  # printed before a failed read, or one with no tab, is not a record row —
  # `cut -f 1` would hand back the whole line, lane-shaped and wrong.
  rows="$(LANES_NO_FETCH=1 "$L" swapped "$ws" 2>/dev/null)" || rows=""
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

## 3. Subagents and worktrees — the one question

Run `ListAgents`, then send each running subagent one `SendMessage`: "Swap imminent: commit and push what
you have now, with the usual trailers and explicit pathspecs; reply with the sha or 'nothing to push'."
For every worktree an agent named (or found under the scratchpad) — `$worktree` below is each of those
paths in turn — report both:

```bash
git -C "$worktree" status --short              # dirty files
git -C "$worktree" log '@{u}..' --oneline      # unpushed commits
```

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
dir="$(LANES_NO_FETCH=1 "$L" lane-dir "$lane" 2>/dev/null)" || dir=""
[[ -n "$dir" ]] || dir="${WORKBENCHES_CLAUDE_LANE_DIR:-}"
if [[ -z "$dir" && -n "${CLAUDE_CODE_SESSION_ID:-}" && -n "${CLAUDE_CONFIG_DIR:-}" ]]; then
  dir="$(jq -r --arg id "$CLAUDE_CODE_SESSION_ID" \
    'select((.sessionId // "") == $id) | .cwd // empty' \
    "$CLAUDE_CONFIG_DIR"/sessions/*.json 2>/dev/null | head -n 1)"
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
[[ -n "$dir" ]] || printf 'NO dir sub-field: neither the lane log, the launcher nor this session record names the lane checkout, so the record is written without one (Amendment 11 clause (c)).\n'
# A PROFILE NAME IS A MANIFEST KEY — letters, digits, `.`, `_`, `-` — and the
# shape check is also how `profile` gets SPEC rev 6 §5's `; ` rule without a
# token of its own: the pattern admits neither a `;` nor a space, so a value
# carrying either is omitted rather than written. A record with no `profile` is
# complete; one naming a profile `pclaude list` does not print is not.
profile_name="${CLAUDE_PROFILE_NAME:-}"
[[ "$profile_name" =~ ^[A-Za-z0-9._-]+$ ]] || profile_name=""
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
# the dispatcher guard would refuse them anyway — `lanes-edit.sh:4187-4192`
# gates `log`, `append-line`, `append-row-status` and six more on a configured
# workstation. Skipping them here means the skill says WHY once, in its own
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
# (c) the row: flip its leading state word, DERIVED from the row itself. row_write_refused is what step 5
# reads: empty on success, "1" the moment either write below does not.
state="$(printf '%s' "$row" | grep -o '| [A-Z][A-Z]* ·' | head -n 1)"   # e.g. '| LIVE ·'
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
  echo "NOT WRITTEN: the row's state cell stays as it is, because every register write from a container with no \$LANES_WORKSTATION stops (clause (k) rule (d)). The handoff refreshed in step 2 names this gap, and step 5 prints the restart command with --lane, because a restart cannot resolve this lane from a row that was never flipped."
else
"$L" replace-in-row "$lane" "$state" "| PAUSED ·" "swap" || row_write_refused=1
if [[ -z "$row_write_refused" ]]; then
  "$L" append-row-status "$lane" "PAUSED — $payload" \
    || row_write_refused=1
fi
fi
```

If (a) still exits 2, re-run it with the free-text argument **dropped entirely** and say so in the report:
the PAUSED line is what the launcher reads on restart, and step 4 is never left unwritten. If `$state` came
back empty, re-read the row and take the first `| WORD ·` in it — `replace-in-row` requires exactly one
occurrence and exits 2 on a guess. If (c) is still refused after that re-read — a rebase conflict, a push
race, anything `replace-in-row`/`append-row-status` themselves report — leave `row_write_refused` set and
say so in the report; step 5 reads it, because a restart cannot resolve this lane from a record that was
never flipped to `PAUSED`.

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

**`--lane <lane>` is printed only where step 4's row write was refused** — the row was never flipped to
`PAUSED`, so a restart cannot resolve this lane from it and the operator must name it explicitly. `--lane`
is a **leading** option to `claude-profile`, read before the action or the profile — measured in the
launcher itself, *"the first token that is not one of them ends this loop"* — so it goes BEFORE the profile
and never after it: `pclaude <profile> --lane <lane>` would be handed to Claude itself, not to the
launcher, and the lane would never be taken. The capability probe above decides whether the RESUMED stamps
are `lane-start`'s act or the next session's — do not assert either from memory.

**`/resume` and `claude --resume <title>` are not lane surfaces** (A8 Addendum 2, R-A8-6): a lane is entered
through `pclaude` or `lane-start`, and by no other door. Do not offer either as a fallback.
