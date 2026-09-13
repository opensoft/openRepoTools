---
name: lane-swap
description: "/lane-swap prepares this lane for a usage reset or profile switch. It fixes the identity triple, refreshes the handoff, polls the writers, writes the swap record, and prints the one restart command (lane-collision-protocol Amendment 8)."
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
if [[ -z "$lane" ]]; then
  # The swap record, read exactly as the launcher reads it: the STATUS decides
  # whether there is an answer at all, and the contract is the tab. A row that
  # printed before a failed read, or one with no tab, is not a record row —
  # `cut -f 1` would hand back the whole line, lane-shaped and wrong.
  rows="$(LANES_NO_FETCH=1 "$L" swapped "$(hostname -s)" 2>/dev/null)" || rows=""
  first="$(printf '%s\n' "$rows" | head -n 1)"
  if [[ -n "$rows" && "$first" == *$'\t'* ]]; then
    candidate="${first%%$'\t'*}"
    [[ "$candidate" =~ ^[A-Za-z0-9_][A-Za-z0-9._-]*$ ]] && lane="$candidate"
  fi
fi
printf 'lane=%s\n' "${lane:-<none>}"
```

The window name answers first; the swap record answers second — the launcher's own order, so the skill and
the launcher never disagree about which lane this is. Then make the other two names match it, mechanically:

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
a stale handoff is how given words die with the session (Amendment 6(e)). Commit with an explicit pathspec
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
# (a) the Amendment 7 object-log PAUSED line — the record `swapped` reads
LANES_LANE="$lane" "$L" log PAUSED "lane:$lane" \
  → "swap; window $(tmux display-message -p '#S:#I'); workstation $(hostname -s)" \
  "on <operator>'s word: <sanitized verbatim>"
# (b) the LANES.md file-level line, the shape every prior PAUSED/RESUMED used
"$L" append-line "PAUSED — lane $lane, session $uuid@$(hostname -s), $(date -u +%Y-%m-%dT%H:%M:%SZ), on <operator>'s word \"<sanitized verbatim>\"; <what's open, or NOTHING CLAIMED>; handoff refreshed"
# (c) the row: flip its leading state word, DERIVED from the row itself. row_write_refused is what step 5
# reads: empty on success, "1" the moment either write below does not.
state="$(printf '%s' "$row" | grep -o '| [A-Z][A-Z]* ·' | head -n 1)"   # e.g. '| LIVE ·'
row_write_refused=""
"$L" replace-in-row "$lane" "$state" "| PAUSED ·" "swap" || row_write_refused=1
if [[ -z "$row_write_refused" ]]; then
  "$L" append-row-status "$lane" "PAUSED — swap; window $(tmux display-message -p '#S:#I'); workstation $(hostname -s)" \
    || row_write_refused=1
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
  restart_cmd="pclaude --lane $lane run ${CLAUDE_PROFILE_NAME:-<profile>}"
  restart_note=' (row write was refused; the lane must be named explicitly)'
else
  restart_cmd="pclaude run ${CLAUDE_PROFILE_NAME:-<profile>}"
  restart_note=''
fi
printf 'READY TO SWAP — restart with: %s%s\n' "$restart_cmd" "$restart_note"
lane-start --help 2>/dev/null | grep -q -- '--confirm' \
  && echo 'restart stamps: written by lane-start (Amendment 8(d))' \
  || echo 'restart stamps: MANUAL, as the next session first act (Rule 3 / Amendment 6(c))'
```

That one command is the whole restart: bare `pclaude run <profile>` resolves this lane from the window name,
and from the swap record step 4 just wrote when the window is gone (Amendment 8(c)). The profile argument is
the only part the operator changes, and only when switching accounts. **`--lane <lane>` is printed only
where step 4's row write was refused** — the row was never flipped to `PAUSED`, so a restart cannot resolve
this lane from it and the operator must name it explicitly. `--lane` is a **leading** option to
`claude-profile` (`claude-profile:555-560` accepts it only before the action), so it goes BEFORE `run`, never
after the profile: `pclaude run <profile> --lane <lane>` would be handed to Claude itself, not to the
launcher. The capability probe above decides whether the RESUMED stamps are `lane-start`'s act or the next
session's — do not assert either from memory.

**`/resume` and `claude --resume <title>` are not lane surfaces** (A8 Addendum 2, R-A8-6): a lane is entered
through `pclaude run` or `lane-start`, and by no other door. Do not offer either as a fallback.
