#!/usr/bin/env bash
#
# lanes-edit.sh — the sanctioned writer for the estate lane registry (LANES.md).
#
# Protocol: ~/.agents/protocols/lane-collision-protocol.md, Rule 9 (registry in
# git) and Rule 10 (workstation designation), Amendment 3, 2026-09-09 — moved
# to the person's workspace repository by Amendment 5, 2026-09-10.
#
# WHERE THE REGISTER LIVES (Amendment 5, 2026-09-10)
#   `lanes/LANES.md` in `opensoft/brett-wip`, on `main`. Direct commits to
#   `main` are the norm THERE by design: the repository is excluded from the
#   organisation's PR-only ruleset precisely so that a per-edit registry
#   commit can land, which is what Rule 9 requires and what the orphan
#   `lanes` branch of `opensoft/xFactory` used to be for. That branch is
#   RETIRED, and its history came across whole with this file.
#
#   Every path a lane already uses keeps resolving:
#   `~/projects/xFactory/LANES.md` and `~/projects/xFactory/lanes-edit.sh`
#   are symlinks into the checkout, placed by its `scripts/link-estates`.
#   This script never spells the checkout's own path — it discovers the
#   repository root with `git rev-parse --show-toplevel` from its own
#   directory, so the clone may live wherever a workstation likes.
#
# WHY THIS EXISTS
#   LANES.md is edited by many concurrent lanes on more than one workstation.
#   On 2026-09-08T23:46Z a whole-file write from one session dropped two other
#   lanes' rows and a day of Rule 6 LANDED lines, and there was no history to
#   recover from. Every write now goes through this script (or an equivalent
#   single-line in-place edit followed by commit + pull --rebase + push), so the
#   registry has a history and a lost row is one `git show` away.
#
# HAZARD — `sed -i` REPLACES A SYMLINK WITH A REGULAR FILE.
#   ~/projects/xFactory/LANES.md is a SYMLINK into this worktree. Plain
#   `sed -i` unlinks it and writes a new regular file, silently detaching the
#   registry from git. Use this helper, or `sed -i --follow-symlinks`, or
#   `cat tmp > LANES.md` (a redirect follows the symlink). `>>` appends,
#   `cat`, `cut`, `head`, `tail`, `grep`, `python open(...,'a')` are all safe.
#
# USAGE
#   lanes-edit.sh [--no-sweep|--sweep] verify-row         <lane>
#   lanes-edit.sh [--no-sweep|--sweep] append-row-status  <lane> "<text>"
#   lanes-edit.sh [--no-sweep|--sweep] replace-in-row     <lane> "<old>" "<new>" ["<why>"]
#   lanes-edit.sh [--no-sweep|--sweep] append-line        "<text>"            # LANDING/LANDED lines
#   lanes-edit.sh [--no-sweep|--sweep] add-row            "<full | row |>"
#   lanes-edit.sh                      commit             "<message>"         # commit a hand edit
#
# --no-sweep (DEFAULT, added 2026-09-09 after 0d84d34/a1f2438 swept another
#   lane's uncommitted hand edit into an unrelated commit): every mutating
#   subcommand checks, before making its own edit, whether LANES.md is
#   already dirty. If it is, that content is someone else's — never this
#   invocation's — so it is committed FIRST, on its own, as
#   `LANES(pre-existing@<workstation>): capture an uncommitted registry edit
#   (row <lane>)`, before this invocation's own edit is made and committed.
#   A WARNING (with `git diff --stat` and the first 200 chars of every
#   changed line) always prints first. This never fails the call — the
#   write still goes through.
# --sweep — the old behaviour: leave the pre-existing content staged so it
#   lands inside this invocation's own commit. Still warns exactly as above,
#   and appends " + sweeps uncommitted edit to row <lane>" to the commit
#   subject, so the sweep is never silent.
# `commit` has no edit of its own to separate from a pre-existing one — its
#   job IS to wrap whatever is already dirty. It instead warns and appends
#   the same " + sweeps uncommitted edit to row <lane>" note when the dirty
#   content touches a row other than the caller's own $LANES_LANE.
#
# ENVIRONMENT
#   LANES_FILE         registry path        (default: <script dir>/LANES.md)
#   LANES_DIR          dir holding it       (default: dir of the resolved script)
#   LANES_REPO         checkout root        (default: `git rev-parse --show-toplevel`
#                                            from LANES_DIR — one level up from
#                                            `lanes/`; never a literal path)
#   LANES_PATH         pathspec of the register RELATIVE to LANES_REPO
#                                           (default: `lanes/LANES.md`, derived
#                                            with `git rev-parse --show-prefix`)
#   LANES_BRANCH       branch to commit on  (default: main)
#   LANES_LANE         lane name for the commit subject when no lane argument
#   LANES_WORKSTATION  workstation name     (default: `hostname -s`)
#   LANES_NO_GIT=1     edit only, no commit/push (used by the test harness)
#
# Dependencies: bash, git, coreutils. No sed/awk substitution on the payload —
# every edit is computed with bash string operations, so `/`, `&`, `\` and `|`
# in the text are literal.

set -u

SELF="$0"
if command -v readlink >/dev/null 2>&1; then
  RESOLVED="$(readlink -f "$SELF" 2>/dev/null || printf '%s' "$SELF")"
else
  RESOLVED="$SELF"
fi
SCRIPT_DIR="$(cd -- "$(dirname -- "$RESOLVED")" && pwd)"

LANES_DIR="${LANES_DIR:-$SCRIPT_DIR}"
LANES_FILE="${LANES_FILE:-$LANES_DIR/LANES.md}"
WS="${LANES_WORKSTATION:-$(hostname -s)}"
NO_GIT="${LANES_NO_GIT:-0}"
LOCK="$LANES_DIR/.lanes-edit.lock"
LOCK_HELD=0

# The register is no longer the whole of its own worktree: since Amendment 5
# it is one file, `lanes/LANES.md`, inside the workspace repository. So every
# git call needs the checkout ROOT and a pathspec RELATIVE to it, both
# DISCOVERED from this script's own directory — never spelled — because the
# clone's path is a workstation's business. `--show-prefix` prints `lanes/`
# from here; outside a repository both fall back to the pre-Amendment-5
# behaviour, which is what the LANES_NO_GIT=1 test harness runs on.
LANES_REPO="${LANES_REPO:-$(git -C "$LANES_DIR" rev-parse --show-toplevel 2>/dev/null || :)}"
: "${LANES_REPO:=$LANES_DIR}"
LANES_PATH="${LANES_PATH:-$(git -C "$LANES_DIR" rev-parse --show-prefix 2>/dev/null || :)${LANES_FILE##*/}}"

# --no-sweep (default) / --sweep — see USAGE above. Consumed here, ahead of
# subcommand dispatch, so either flag may appear anywhere before the
# subcommand name.
SWEEP_MODE="no-sweep"
while [ $# -gt 0 ]; do
  case "${1-}" in
    --no-sweep) SWEEP_MODE="no-sweep"; shift ;;
    --sweep)    SWEEP_MODE="sweep"; shift ;;
    *) break ;;
  esac
done

die() { printf 'lanes-edit: %s\n' "$*" >&2; exit "${2:-1}"; }
note() { printf 'lanes-edit: %s\n' "$*" >&2; }

cleanup() {
  if [ "$LOCK_HELD" = 1 ]; then rmdir -- "$LOCK" 2>/dev/null || :; fi
  [ -n "${TMPD:-}" ] && [ -d "${TMPD:-}" ] && rm -rf -- "$TMPD"
  return 0
}
trap cleanup EXIT INT TERM

acquire_lock() {
  # Stale lock (>10 min) is removed: a helper run never takes that long.
  if [ -d "$LOCK" ]; then
    if [ -z "$(find "$LOCK" -maxdepth 0 -mmin -10 2>/dev/null)" ]; then
      note "removing stale lock $LOCK"
      rmdir -- "$LOCK" 2>/dev/null || :
    fi
  fi
  i=0
  while [ "$i" -lt 60 ]; do
    if mkdir -- "$LOCK" 2>/dev/null; then LOCK_HELD=1; return 0; fi
    i=$((i + 1))
    sleep 1
  done
  die "could not acquire $LOCK after 60s — another lanes-edit run is active" 4
}

# ---------------------------------------------------------------- row lookup

# Prints the 1-based line number of the row whose FIRST backticked token is the
# lane name. Exactly one match is required.
row_line() {
  lane="$1"
  hits="$(
    awk -v lane="$lane" '
      substr($0,1,1) == "|" {
        p1 = index($0, "`")
        if (p1 == 0) next
        rest = substr($0, p1 + 1)
        p2 = index(rest, "`")
        if (p2 == 0) next
        if (substr(rest, 1, p2 - 1) == lane) print NR
      }' "$LANES_FILE"
  )"
  n="$(printf '%s' "$hits" | grep -c . || :)"
  if [ "$n" != 1 ]; then
    # NOTE: row_line runs inside $( ), so it must RETURN, not exit — an `exit`
    # here would only leave the command substitution's subshell and the caller
    # would carry on with an empty line number.
    note "expected exactly 1 row for lane '$lane', found $n${hits:+ (lines: $(printf '%s' "$hits" | tr '\n' ' '))}"
    return 2
  fi
  printf '%s' "$hits"
}

count_occurrences() { # $1=haystack $2=needle
  hay="$1"; needle="$2"; c=0
  if [ -z "$needle" ]; then note "empty search string"; return 2; fi
  while :; do
    case "$hay" in
      *"$needle"*) c=$((c + 1)); hay="${hay#*"$needle"}" ;;
      *) break ;;
    esac
  done
  printf '%s' "$c"
}

rstrip_spaces() { s="$1"; while [ "${s% }" != "$s" ]; do s="${s% }"; done; printf '%s' "$s"; }

# --------------------------------------------------------------- file writes

# Replace line N with $2, leaving every other byte untouched. Verified with
# `git diff --no-index --numstat` (must be exactly 1 added / 1 deleted).
replace_line() {
  n="$1"; newline="$2"
  TMPD="$(mktemp -d)"
  pre="$TMPD/pre"; out="$TMPD/out"
  cat -- "$LANES_FILE" > "$pre"
  before="$(wc -l < "$pre")"
  {
    [ "$n" -gt 1 ] && head -n "$((n - 1))" -- "$pre"
    printf '%s\n' "$newline"
    tail -n "+$((n + 1))" -- "$pre"
  } > "$out"
  after="$(wc -l < "$out")"
  [ "$before" = "$after" ] || die "line count changed ($before -> $after); refusing" 5
  stat="$(git --no-pager diff --no-index --numstat -- "$pre" "$out" 2>/dev/null | head -n1 | cut -f1,2)"
  [ "$stat" = "$(printf '1\t1')" ] || die "edit touched more than one line (numstat: ${stat:-none}); refusing" 5
  cat -- "$out" > "$LANES_FILE"   # redirect FOLLOWS the symlink
  note "line $n rewritten in $LANES_FILE"
}

append_text_line() {
  newline="$1"
  TMPD="$(mktemp -d)"
  pre="$TMPD/pre"
  cat -- "$LANES_FILE" > "$pre"
  before_bytes="$(wc -c < "$pre")"
  before_lines="$(wc -l < "$pre")"
  printf '%s\n' "$newline" >> "$LANES_FILE"   # >> FOLLOWS the symlink
  after_lines="$(wc -l < "$LANES_FILE")"
  [ "$after_lines" = "$((before_lines + 1))" ] || die "append changed line count by $((after_lines - before_lines)); inspect $LANES_FILE" 5
  cmp -s -n "$before_bytes" -- "$pre" "$LANES_FILE" || die "append rewrote existing bytes; inspect $LANES_FILE" 5
  note "1 line appended to $LANES_FILE"
}

# ------------------------------------------------------------------ git side

LANES_BRANCH="${LANES_BRANCH:-main}"

remote_has_branch() { git -C "$LANES_REPO" ls-remote --exit-code --heads origin "$LANES_BRANCH" >/dev/null 2>&1; }

# Unstaged changes to TRACKED files OTHER than the register. New in Amendment
# 5 and unavoidable: the register shares its checkout with handoffs/ and
# workspaces/, which other lanes write. `git pull --rebase` refuses outright
# on ANY unstaged tracked change, so without this the refusal would surface as
# a bogus "REBASE CONFLICT" and the writer would be sent to a recovery that
# does not apply. Prints the offending paths, one per line.
dirty_elsewhere() {
  git -C "$LANES_REPO" --no-pager diff --name-only 2>/dev/null | grep -v -x -F -- "$LANES_PATH" || :
}

commit_push() {
  msg="$1"
  [ "$NO_GIT" = 1 ] && { note "LANES_NO_GIT=1 — not committing"; return 0; }
  git -C "$LANES_REPO" add -- "$LANES_PATH" || die "git add failed" 6
  if git -C "$LANES_REPO" diff --cached --quiet -- "$LANES_PATH"; then
    note "nothing staged for LANES.md — no commit made"
    return 0
  fi
  git -C "$LANES_REPO" commit -q -m "$msg" -- "$LANES_PATH" || die "git commit failed" 6
  note "committed: $msg"
  if ! remote_has_branch; then
    git -C "$LANES_REPO" push -q -u origin "$LANES_BRANCH" || die "initial push of '$LANES_BRANCH' failed" 6
    note "pushed (created origin/$LANES_BRANCH)"
    return 0
  fi
  attempt=1
  while [ "$attempt" -le 6 ]; do
    # A peer may have written LANES.md between our commit and this pull.
    if ! git -C "$LANES_REPO" diff --quiet -- "$LANES_PATH"; then
      cap="$(git -C "$LANES_REPO" --no-pager diff --numstat -- "$LANES_PATH" | cut -f1,2 | tr '\t' '/')"
      git -C "$LANES_REPO" commit -q -m "LANES(concurrent@$WS): capture an uncommitted registry edit ($cap lines +/-) made by whoever else is writing right now — its author should follow up with a commit that says what it was" -- "$LANES_PATH" || :
      note "captured a concurrent uncommitted edit ($cap lines +/-) as its own commit"
    fi
    others="$(dirty_elsewhere)"
    if [ -n "$others" ]; then
      # Someone else's uncommitted file in this shared checkout. Pulling is
      # impossible until they commit it, and it is NOT ours to commit — a
      # handoff mid-write is exactly the content Amendment 4(d) says its own
      # author commits. So skip the pull and try the push: it succeeds unless
      # the remote moved, and the register edit is already a local commit
      # either way.
      note "WARNING: this checkout has uncommitted changes to files OTHER than the register — not this invocation's:"
      printf '  %s\n' $others >&2
      note "skipping 'pull --rebase' (it refuses on any unstaged tracked change) and pushing straight out"
      if git -C "$LANES_REPO" push -q origin "$LANES_BRANCH"; then
        note "pushed origin/$LANES_BRANCH (attempt $attempt, no pull — see the warning above)"
        return 0
      fi
      note "push rejected and the pull is blocked by the files above (attempt $attempt)"
      if [ "$attempt" -ge 6 ]; then
        note "RECOVERY: their author commits those files (a handoff: handoff(<lane>@<workstation>): <what>),"
        note "  then re-run: LANES_LANE=<lane> lanes-edit.sh commit \"<what you wrote>\"  — your edit is already"
        note "  a local commit here: git -C $LANES_REPO log --oneline origin/$LANES_BRANCH..HEAD"
        die "could not push origin/$LANES_BRANCH: behind the remote, and a peer's uncommitted file blocks the rebase. Nothing was lost — your commit is local." 3
      fi
    elif git -C "$LANES_REPO" pull --rebase -q origin "$LANES_BRANCH"; then
      if git -C "$LANES_REPO" push -q origin "$LANES_BRANCH"; then
        note "pushed origin/$LANES_BRANCH (attempt $attempt)"
        return 0
      fi
      note "push raced (attempt $attempt) — retrying"
    else
      note "REBASE CONFLICT on origin/$LANES_BRANCH — conflicting lines follow:"
      grep -n -e '^<<<<<<<' -e '^=======' -e '^>>>>>>>' -- "$LANES_FILE" 2>/dev/null | head -n 40 >&2 || :
      grep -n -A2 -e '^<<<<<<<' -- "$LANES_FILE" 2>/dev/null | head -n 40 >&2 || :
      git -C "$LANES_REPO" rebase --abort 2>/dev/null || :
      note "rebase ABORTED — the worktree is clean and NOT mid-rebase. Your edit is safe in these local commits:"
      git -C "$LANES_REPO" --no-pager log --oneline "origin/$LANES_BRANCH..HEAD" 2>/dev/null | head -n 10 >&2 || :
      note "RECOVERY (in that order):"
      note "  git -C $LANES_REPO diff origin/$LANES_BRANCH..HEAD -- $LANES_PATH   # read back exactly what you wrote"
      note "  git -C $LANES_REPO reset --hard origin/$LANES_BRANCH                # drop the local commits (NOTE: also drops any"
      note "                                                          # uncommitted peer edit in this checkout)"
      note "  then re-read LANES.md and redo the edit with lanes-edit.sh, on top of the peer's version."
      die "rebase conflict on origin/$LANES_BRANCH — nothing was pushed." 3
    fi
    attempt=$((attempt + 1))
    sleep 3
  done
  die "could not push origin/$LANES_BRANCH after 6 attempts; your commit is local — retry later" 6
}

# Prints, to stdout, a comma-joined, de-duplicated list of the lane(s) whose
# row changed in the CURRENT unstaged diff of LANES.md — identified by the
# first backtick token on each changed (+/-) line — or "append" for a
# changed line that is not a `| ... |` row (e.g. a Rule 6 LANDING/LANDED
# line, which names no row of its own).
identify_changed_lanes() {
  git -C "$LANES_REPO" --no-pager diff -- "$LANES_PATH" 2>/dev/null | awk '
    /^[+-][^+-]/ {
      line = substr($0, 2)
      lane = "append"
      if (substr(line, 1, 1) == "|") {
        p1 = index(line, "`")
        if (p1 > 0) {
          rest = substr(line, p1 + 1)
          p2 = index(rest, "`")
          if (p2 > 0) lane = substr(rest, 1, p2 - 1)
        }
      }
      if (!(lane in seen)) { seen[lane] = 1; order[++n] = lane }
    }
    END { for (i = 1; i <= n; i++) printf "%s%s", (i > 1 ? "," : ""), order[i] }
  '
}

# Prints the standard WARNING block (diff --stat + first 200 chars of every
# changed line) to stderr. Takes no action beyond warning.
warn_dirty() {
  git -C "$LANES_REPO" --no-pager diff --stat -- "$LANES_PATH" >&2
  git -C "$LANES_REPO" --no-pager diff -- "$LANES_PATH" 2>/dev/null | awk '/^[+-][^+-]/ {print substr($0,1,200)}' >&2
}

# Called by every mutating subcommand BEFORE it makes its own edit. If
# LANES.md is already dirty at that point, that content is someone else's —
# a peer's hand edit, or a helper run interrupted before it could push —
# never this invocation's. Always warns. In the default --no-sweep mode it
# commits that content now, as its own attributed commit, so it can never
# land combined with this invocation's edit (the 0d84d34 / a1f2438
# incidents: another lane's row edit landed inside an unrelated commit with
# no trace of whose it was). In --sweep mode it leaves the content staged
# for this invocation's own commit and sets PRE_DIRTY_LANES so the caller
# can annotate its commit subject.
#
# Sets PRE_DIRTY_LANES to the affected lane list in --sweep mode; empty
# otherwise (nothing left to annotate — it was already committed separately).
handle_preexisting() {
  PRE_DIRTY_LANES=""
  [ "$NO_GIT" = 1 ] && return 0
  git -C "$LANES_REPO" diff --quiet -- "$LANES_PATH" 2>/dev/null && return 0
  lanes="$(identify_changed_lanes)"; lanes="${lanes:-unknown}"
  note "WARNING: LANES.md already has uncommitted changes before this edit (row: $lanes) — not this invocation's"
  warn_dirty
  if [ "$SWEEP_MODE" = "sweep" ]; then
    PRE_DIRTY_LANES="$lanes"
    note "SWEEP_MODE=sweep — leaving it staged; it will land inside this invocation's own commit, annotated"
  else
    git -C "$LANES_REPO" add -- "$LANES_PATH"
    git -C "$LANES_REPO" commit -q -m "LANES(pre-existing@$WS): capture an uncommitted registry edit (row $lanes)" -- "$LANES_PATH" || :
    note "captured pre-existing edit (row $lanes) as its own commit"
  fi
  return 0
}

# ---------------------------------------------------------------- subcommands

cmd="${1-}"
# The usage block is this file's own header: print from line 3 until the first
# line that is not a comment. (It used to be a hard-coded `3,59p`, which went
# stale the moment the header grew — as it did under Amendment 5.)
[ -n "$cmd" ] || { sed -n '3,${/^#/!q;s/^# \{0,1\}//;p}' -- "$RESOLVED"; exit 2; }
shift || :
[ -f "$LANES_FILE" ] || die "registry not found: $LANES_FILE"

case "$cmd" in
  verify-row)
    lane="${1-}"; [ -n "$lane" ] || die "usage: verify-row <lane>" 2
    n="$(row_line "$lane")" || exit 2
    row="$(sed -n "${n}p" -- "$LANES_FILE")"
    printf 'lane   : %s\nline   : %s\nlength : %s chars\nfirst200: %s\nlast200 : %s\n' \
      "$lane" "$n" "${#row}" "$(printf '%s' "$row" | cut -c1-200)" \
      "$(printf '%s' "$row" | rev | cut -c1-200 | rev)"
    ;;

  append-row-status)
    lane="${1-}"; text="${2-}"
    [ -n "$lane" ] && [ -n "$text" ] || die "usage: append-row-status <lane> \"<text>\"" 2
    acquire_lock; handle_preexisting
    n="$(row_line "$lane")" || exit 2
    row="$(sed -n "${n}p" -- "$LANES_FILE")"
    trimmed="$(rstrip_spaces "$row")"
    case "$trimmed" in
      *"|") : ;;
      *) die "row $n does not end with '|' — refusing to append a status" 2 ;;
    esac
    body="$(rstrip_spaces "${trimmed%|}")"
    replace_line "$n" "$body · $text |"
    msg="LANES($lane@$WS): status · $text"
    [ -n "$PRE_DIRTY_LANES" ] && msg="$msg + sweeps uncommitted edit to row $PRE_DIRTY_LANES"
    commit_push "$msg"
    ;;

  replace-in-row)
    lane="${1-}"; old="${2-}"; new="${3-}"; why="${4-}"
    [ -n "$lane" ] && [ -n "$old" ] || die "usage: replace-in-row <lane> \"<old>\" \"<new>\" [\"<why>\"]" 2
    acquire_lock; handle_preexisting
    n="$(row_line "$lane")" || exit 2
    row="$(sed -n "${n}p" -- "$LANES_FILE")"
    c="$(count_occurrences "$row" "$old")" || exit 2
    [ "$c" = 1 ] || die "'$old' occurs $c times in lane $lane's row (line $n); exactly 1 required" 2
    replace_line "$n" "${row/"$old"/"$new"}"
    msg="LANES($lane@$WS): ${why:-replace-in-row}"
    [ -n "$PRE_DIRTY_LANES" ] && msg="$msg + sweeps uncommitted edit to row $PRE_DIRTY_LANES"
    commit_push "$msg"
    ;;

  append-line)
    text="${1-}"; [ -n "$text" ] || die "usage: append-line \"<text>\"" 2
    acquire_lock; handle_preexisting
    append_text_line "$text"
    msg="LANES(${LANES_LANE:-unknown}@$WS): append line — $(printf '%s' "$text" | cut -c1-72)"
    [ -n "$PRE_DIRTY_LANES" ] && msg="$msg + sweeps uncommitted edit to row $PRE_DIRTY_LANES"
    commit_push "$msg"
    ;;

  add-row)
    row="${1-}"; [ -n "$row" ] || die "usage: add-row \"<full | row |>\"" 2
    case "$row" in
      "| "*) : ;;
      *) die "a row must start with '| '" 2 ;;
    esac
    case "$(rstrip_spaces "$row")" in
      *"|") : ;;
      *) die "a row must end with '|'" 2 ;;
    esac
    pipes="$(count_occurrences "$row" "|")" || exit 2
    [ "$pipes" -ge 8 ] || die "a 7-column row needs at least 8 '|' characters, found $pipes" 2
    lane_new="$(printf '%s' "$row" | cut -d'`' -f2)"
    if [ -n "$lane_new" ] && row_line "$lane_new" >/dev/null 2>&1; then
      die "lane '$lane_new' already has a row — use append-row-status / replace-in-row" 2
    fi
    acquire_lock; handle_preexisting
    append_text_line "$row"
    msg="LANES(${lane_new:-${LANES_LANE:-unknown}}@$WS): add row"
    [ -n "$PRE_DIRTY_LANES" ] && msg="$msg + sweeps uncommitted edit to row $PRE_DIRTY_LANES"
    commit_push "$msg"
    ;;

  commit)
    msg="${1-}"; [ -n "$msg" ] || die "usage: commit \"<message>\"" 2
    acquire_lock
    # `commit` has no edit of its own to separate from a pre-existing one —
    # its whole job is to wrap whatever is already dirty (a hand edit made
    # with an allowed tool). The best it can do is warn when that dirty
    # content ALSO touches a ROW other than the caller's own $LANES_LANE,
    # and say so in the commit subject (0d84d34: a hermes-wallet-exercise
    # `commit` call silently absorbed an unrelated openXfactory-2 row edit).
    # "append" (a plain line with no row of its own, e.g. this call's own
    # Rule 6 LANDING/LANDED line) is excluded from "other" — it is the
    # normal, expected shape of exactly what `commit` is for, and flagging
    # it would warn on every ordinary use.
    if [ "$NO_GIT" != 1 ] && ! git -C "$LANES_REPO" diff --quiet -- "$LANES_PATH" 2>/dev/null; then
      touched="$(identify_changed_lanes)"
      other="$(printf '%s\n' "$touched" | tr ',' '\n' | grep -v -x -e "${LANES_LANE:-}" -e '' -e 'append' | paste -sd, - 2>/dev/null || :)"
      if [ -n "$other" ]; then
        note "WARNING: uncommitted LANES.md changes touch row(s) other than this lane (${LANES_LANE:-unknown}): $other"
        warn_dirty
        msg="$msg + sweeps uncommitted edit to row $other"
      fi
    fi
    commit_push "LANES(${LANES_LANE:-unknown}@$WS): $msg"
    ;;

  *)
    die "unknown subcommand '$cmd' (verify-row|append-row-status|replace-in-row|append-line|add-row|commit)" 2
    ;;
esac
