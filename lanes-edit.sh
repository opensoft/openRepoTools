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
#                                        (attribution: $LANES_LANE, else the
#                                         "lane <name>" the text itself names)
#   lanes-edit.sh [--no-sweep|--sweep] add-row            "<full | row |>"
#   lanes-edit.sh                      commit             "<message>"         # commit a hand edit
#
# AMENDMENT 7 — the per-lane object log (`lanes/log/<lane>.md`)
#   lanes-edit.sh log     <VERB> <object> [→|← <payload>] ["<text>"] [--text "<t>"]
#   lanes-edit.sh claim   <object> [--force] [--no-github] [--home owner/repo]
#   lanes-edit.sh release <object> ["<why>"] [--no-github] [--home owner/repo]
#   lanes-edit.sh who     <object> | --lane <lane> | --landing owner/repo
#
#   `--home owner/repo` is an option of all FIVE of `claim`, `release`, `who`,
#   `log` and `lane-end`, for a lane whose log has no STARTED line. All five
#   resolve it AFTER the fetch (R30), because the STARTED line that refuses it
#   may be a peer's and live only on `origin/<branch>`.
#
#   An object is `owner/repo#<n>`, `owner/repo:openspec/changes/<name>`, `#<n>`
#   for the lane's OWN home repo, or `lane:<name>` for the lane-kind lines.
#   `lanes/repos.tsv` (`alias<TAB>owner/repo`) resolves an omitted owner and
#   the register's legacy spellings; an unknown alias is refused, never guessed.
#   A LANE'S HOME GOES THROUGH THE SAME TABLE (R20, Addendum 5) — `lane-start`
#   resolves it before writing STARTED, and every comparison of an object's
#   repository against a home resolves BOTH sides. A home is inherited by every
#   `#<n>` that lane writes, so a legacy org spelling there gave one GitHub
#   issue two object keys and two lanes held it with no collision detected.
#
#   STATE IS PER LANE: a lane's state on an object is its own LAST line naming
#   it, and it HOLDS the object while that verb is open. Open is
#   {CLAIMED, TAKEOVER, OPENED, LANDING, WITHDRAWN}; closed — and it closes
#   only the writing lane's hold — is {RELEASED, CLAIM-LOST, CLOSED, LANDED}.
#
#   THAT APPLIES TO A TAKEOVER TOO (R18, Addendum 5): lane B's TAKEOVER on an
#   object supersedes lane A's CLAIMED only while the TAKEOVER is B's OWN LAST
#   LINE on it. Once B writes RELEASED, CLOSED or LANDED there, A's later
#   CLAIMED holds normally. A TAKEOVER is never removed from an append-only
#   log, so treating one as superseding for ever made a legitimate re-claim
#   invisible: `who` called a held object FREE and `claim` did not refuse the
#   next lane. Known and deliberate: two lanes each ending on a TAKEOVER of one
#   object are BOTH reported as holders — a visible conflict, and not reachable
#   through the helpers, since `claim --force` takes over a stale CLAIMED only.
#
#   AND "LAST" IS THE LAST LINE IN THE FILE (R14, Addendum 4). A lane's log is
#   append-only and single-writer, so the ORDER OF ITS LINES is the order of
#   that lane's writes. No state read here — `lane_objects`, `superseded_by`,
#   PER_LANE_AWK, `who` in any mode, `lane-end`'s refusal, `claim`'s pre-check
#   and its rescan — selects or orders lines by their UTC field. The UTC stays
#   on every line as INFORMATION, and is compared only where a DURATION is the
#   rule: Rule 1's four-hour staleness and Rule 6's thirty minutes, where a few
#   seconds are immaterial. On 2026-09-11 this workstation's realtime clock was
#   observed jumping ±25s in bursts and a log commit landed whose content
#   carried a UTC 26s after its own committer date; a max-UTC read made that
#   lane's newest line invisible. Two workstations never share a clock either.
#
#   `claim` is Rule 1 as one act, and THE RACE IS DECIDED BY WHICH CLAIMED
#   LANDS ON `main` FIRST, never by comparing timestamps: fetch, pre-check
#   against `origin/main`, append, commit, push; on a rebase, rescan, and if
#   another lane's claim is already there, write `CLAIM-LOST` and stop. Git's
#   push serialization is the arbiter between workstations; the `mkdir` mutex
#   below only serializes this one.
#
#   EVERY STATE READ IS OF `origin/<branch>`, AFTER A FETCH — never of the
#   working tree. What has LANDED is what other lanes can see; a working tree
#   can be behind by a peer's whole day. `who`, the pre-check, staleness, the
#   superseded filter, the crossing warning, `lane-end`'s refusal and
#   `lane-start`'s home lookup all read the same source, so they cannot
#   disagree with each other either.
#
#   THE REGISTER'S ROWS ARE READ THE SAME WAY (R19, Addendum 5). The session
#   cell, the handoff path and the workstation column come from
#   `git show origin/<branch>:lanes/LANES.md`; nothing in `who` reads the
#   working tree. THE ONE EXCEPTION IS THE `live-holder` SUBCOMMAND, and only
#   its id SET (R25, Addendum 6): it is the published row's union this
#   checkout's, because a session stamps its uuid on the row with
#   `replace-in-row` and that write is a LOCAL COMMIT until its push lands —
#   read from `origin` alone the rename gate would not see the uuid of the very
#   session it is being asked to rename over, would answer 8, and `lane-start`
#   would take the name. That is what mints `<lane> (2)` (AGENTS.md rule 7).
#   Liveness fails closed, so an id `origin` has not seen is a reason to refuse
#   a rename, never to allow one, and nothing that PRINTS uses the union.
#
#   A LANDED CLOSES THE LANDING IT ANSWERS (R17, Addendum 5): `who --landing`
#   pairs them by (lane, PR) in FILE ORDER and keys the result on
#   (lane, repository, PR). Most of the register's LANDED lines carry no
#   `into <repo> main` clause, and keying those on the repository they name
#   reported 232 phantom merge holds where one was real.
#
# EXIT CODES — every subcommand, one table, no two meanings on one number
#   0  done
#   1  environment (no register, no writer)
#   2  refusal: bad arguments, the object is held, an unknown alias, or a
#      checkout that cannot be rebased
#   3  rebase conflict — nothing was pushed, the edit is a local commit
#   4  the mutex could not be taken within 60s
#   5  an edit moved more than one line and was refused
#   6  git add / commit / push failed
#   7  CLAIM-LOST — another lane's claim landed on main first (`claim` only)
#   8  no record — `who` found nothing; `lane-objects` has no log file for the
#      lane; `live-holder` READ this workstation's session records and none of
#      them holds it. A read that could not be performed is never 8 (R22).
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
#   write still goes through. Amendment 7's `log`, `claim` and `release` take
#   the same capture for the REGISTER between the two halves of their
#   dirty-checkout guard, which is why a peer's half-written `lanes/LANES.md`
#   does not refuse them (Addendum 3, R11); any OTHER modified tracked file
#   still does, and is refused before the capture rather than after it.
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
#   LANES_LOG_DIR      the object logs     (default: <LANES_DIR>/log)
#   LANES_REPOS_TSV    the alias table     (default: <LANES_DIR>/repos.tsv)
#   LANES_SESSION      this session's TRANSCRIPT uuid, for the event lines
#                      (default: the last uuid in the lane's row — Amendment 6(b))
#   LANES_LANE_DIR     the lane's checkout, for project.yaml leg detection
#                      (default: $PROJECTS_ROOT/<repo part of the home repo>)
#   LANES_NO_GITHUB=1  skip every `gh` call (tests, offline); same as --no-github
#   LANES_NO_FETCH=1   skip the `git fetch` a read does first (offline; tests).
#                      It does NOT change WHAT is read: every state read is of
#                      `origin/<branch>`, which without the fetch is simply the
#                      ref as it already stands here.
#   LANES_STALE_HOURS  Rule 1's stale threshold, reused (default: 4)
#   LANES_DEBUG        non-empty: a refusal also prints its exit code
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

# The pathspecs the current invocation is writing. Every subcommand that
# predates Amendment 7 writes exactly one, the register; a LANDING or LANDED
# writes two. CP_AFTER_REBASE is a function commit_push calls after each
# `pull --rebase`, before it pushes — `claim` uses it to notice that another
# lane's claim landed first.
CP_PATHS=("$LANES_PATH")
CP_AFTER_REBASE=""

# --no-sweep (default) / --sweep — see USAGE above. Consumed here, ahead of
# subcommand dispatch, so either flag may appear anywhere before the
# subcommand name.
SWEEP_MODE="no-sweep"
while [ $# -gt 0 ]; do
  case "${1-}" in
    --no-sweep)  SWEEP_MODE="no-sweep"; shift ;;
    --sweep)     SWEEP_MODE="sweep"; shift ;;
    --no-github) LANES_NO_GITHUB=1; shift ;;
    *) break ;;
  esac
done

# die "<message>" [<exit code>] — the MESSAGE is $1 alone. It used to be "$*",
# which joined the exit code on to the end of every refusal that passed one:
# `… is not a stale claim. 2`. The code is the caller's business and the
# process's, not the reader's; LANES_DEBUG=1 prints it for whoever is debugging
# the codes themselves.
die() {
  printf 'lanes-edit: %s\n' "${1-}" >&2
  [ -n "${LANES_DEBUG:-}" ] && printf 'lanes-edit: (exit %s)\n' "${2:-1}" >&2
  exit "${2:-1}"
}
note() { printf 'lanes-edit: %s\n' "$*" >&2; }

cleanup() {
  if [ "$LOCK_HELD" = 1 ]; then rmdir -- "$LOCK" 2>/dev/null || :; fi
  [ -n "${TMPD:-}" ] && [ -d "${TMPD:-}" ] && rm -rf -- "$TMPD"
  [ -n "${SE_CACHE_FILE:-}" ] && rm -f -- "$SE_CACHE_FILE" "$SE_CACHE_FILE".* 2>/dev/null
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

# Prints the row's OWN spelling of a lane name that matches $1 ignoring case,
# when exactly one row does. Attribution only — never used to pick the line an
# edit rewrites, which stays exact-match. Rule 10's wire form is lowercase
# (`Lane: openxfactory-2`) while the row's token may be camel (`openXfactory-2`),
# so an exact lookup alone loses the author of a Rule 6 line.
row_lane_ci() {
  awk -v want="$1" '
    substr($0,1,1) == "|" {
      p1 = index($0, "`"); if (p1 == 0) next
      rest = substr($0, p1 + 1); p2 = index(rest, "`"); if (p2 == 0) next
      t = substr(rest, 1, p2 - 1)
      if (tolower(t) == tolower(want)) { n++; hit = t }
    }
    END { if (n == 1) print hit }' "$LANES_FILE"
}

# A Rule 6 line names its own lane in its text — "LANDING — lane <name>, …",
# "LANDED — lane <name> (<Window>), …". `append-line` takes no lane argument,
# so with LANES_LANE unset it used to commit as LANES(unknown@<ws>) and the
# line's author was lost from the log (this predates Amendment 5: the same
# `${LANES_LANE:-unknown}` is in the pre-move script). Read the name out of
# the text instead, and fall back to unknown only when there is nothing to
# read. Anything outside [A-Za-z0-9._-] is rejected rather than sanitised,
# and the caller checks the candidate against the register's own rows before
# trusting it — "…names no lane at all" must not be attributed to a lane
# called "at".
lane_from_text() {
  t="$1"; l=""
  case "$t" in
    *"lane "*)
      l="${t#*lane }"
      l="${l%%[ ,;:)]*}"
      l="${l//\`/}"
      ;;
  esac
  case "$l" in
    "" | *[!A-Za-z0-9._-]*) printf '' ;;
    *) printf '%s' "$l" ;;
  esac
}

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

# $2 is the file to append to, defaulting to the register. Amendment 7's
# per-lane object logs are appended with exactly the same proof — one line
# more, not one existing byte different.
append_text_line() {
  newline="$1"; target="${2:-$LANES_FILE}"
  TMPD="$(mktemp -d)"
  pre="$TMPD/pre"
  cat -- "$target" > "$pre"
  before_bytes="$(wc -c < "$pre")"
  before_lines="$(wc -l < "$pre")"
  printf '%s\n' "$newline" >> "$target"   # >> FOLLOWS the symlink
  after_lines="$(wc -l < "$target")"
  [ "$after_lines" = "$((before_lines + 1))" ] || die "append changed line count by $((after_lines - before_lines)); inspect $target" 5
  cmp -s -n "$before_bytes" -- "$pre" "$target" || die "append rewrote existing bytes; inspect $target" 5
  note "1 line appended to $target"
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
  git -C "$LANES_REPO" --no-pager diff --name-only 2>/dev/null \
    | grep -v -x -F -- "$(printf '%s\n' "${CP_PATHS[@]}")" || :
}

# Every TRACKED file in this checkout that differs from HEAD — staged or not,
# and whatever pathspec the caller happens to be writing. That is exactly the
# set `git pull --rebase` refuses on. `git status --porcelain` reports the same
# thing, with rename records and path quoting to parse first; these two
# plumbing reads answer the same question unambiguously, and neither reports an
# untracked file, which does not block a rebase.
tracked_dirty() {
  { git -C "$LANES_REPO" --no-pager diff --name-only 2>/dev/null
    git -C "$LANES_REPO" --no-pager diff --name-only --cached 2>/dev/null
  } | LC_ALL=C sort -u
}

# AMENDMENT 7 — `log`, `claim` and `release` REFUSE a checkout that cannot be
# rebased. $1 names the act; every remaining argument is a pathspec THIS write
# is about to append to and is therefore exempt.
#
# `lanes/LANES.md` is the one exemption that is not a pathspec of the write:
# it is CAPTURED rather than refused, by capture_register_edit below, and the
# guard is then re-run against the checkout that capture left behind. See
# there for why (Addendum 3, R11).
#
# The guard is computed over the WHOLE checkout, and from the same set the
# write will use, because the first version of it was not: `claim` measured
# "dirty elsewhere" against (log + LANES.md) while a CLAIMED writes the log
# alone, so a dirty `lanes/LANES.md` — the one dirty file this repository
# actually has, at ~500 register commits a day — passed the guard and then took
# commit_push's Amendment 5(d) branch, which skips `pull --rebase` and with it
# the rescan that decides the race. Two lanes ended up holding one object with
# no CLAIM-LOST. The guard and the write must never disagree about what this
# invocation is writing.
refuse_dirty_checkout() {
  rd_what="$1"; shift
  [ "$NO_GIT" = 1 ] && return 0
  git -C "$LANES_REPO" rev-parse --git-dir >/dev/null 2>&1 || return 0
  if [ "$#" -gt 0 ]; then
    rd_others="$(tracked_dirty | grep -v -x -F -- "$(printf '%s\n' "$@")" || :)"
  else
    rd_others="$(tracked_dirty)"
  fi
  [ -n "$rd_others" ] || return 0
  note "this checkout has uncommitted changes to tracked files that are not this $rd_what's:"
  printf '  %s\n' $rd_others >&2
  case "$rd_what" in
    claim) note "a claim is decided by which CLAIMED lands on main first, and 'pull --rebase' refuses on any"
           note "unstaged tracked change — so the race cannot be run safely here." ;;
    *)     note "an object-log write is ordered against other lanes by landing on main, and 'pull --rebase'"
           note "refuses on any unstaged tracked change — so this write cannot be ordered safely here." ;;
  esac
  note "RECOVERY — whoever wrote those files commits them, then re-run:"
  note "  lanes/LANES.md   LANES_LANE=<lane> lanes-edit.sh commit \"<what you wrote>\""
  note "  anything else    git -C $LANES_REPO commit -m \"handoff(<lane>@<workstation>): <what>\" -- <path>"
  die "refusing to $rd_what on a checkout that cannot be rebased" 2
}

# commit_push "<subject>" [<pathspec>...] — the pathspecs default to the
# register alone, which is every caller that predates Amendment 7. A LANDING
# or LANDED writes TWO (the register and the lane's log) so that both halves
# of one act land in one commit and no reader ever sees half of it.
commit_push() {
  msg="$1"; shift || :
  if [ "$#" -gt 0 ]; then CP_PATHS=("$@"); else CP_PATHS=("$LANES_PATH"); fi
  [ "$NO_GIT" = 1 ] && { note "LANES_NO_GIT=1 — not committing"; return 0; }
  git -C "$LANES_REPO" add -- "${CP_PATHS[@]}" || die "git add failed" 6
  if git -C "$LANES_REPO" diff --cached --quiet -- "${CP_PATHS[@]}"; then
    note "nothing staged for ${CP_PATHS[*]} — no commit made"
    return 0
  fi
  git -C "$LANES_REPO" commit -q -m "$msg" -- "${CP_PATHS[@]}" || die "git commit failed" 6
  note "committed: $msg"
  if ! remote_has_branch; then
    git -C "$LANES_REPO" push -q -u origin "$LANES_BRANCH" || die "initial push of '$LANES_BRANCH' failed" 6
    note "pushed (created origin/$LANES_BRANCH)"
    return 0
  fi
  attempt=1
  while [ "$attempt" -le 6 ]; do
    # A peer may have written LANES.md between our commit and this pull.
    if ! git -C "$LANES_REPO" diff --quiet -- "${CP_PATHS[@]}"; then
      cap="$(git -C "$LANES_REPO" --no-pager diff --numstat -- "${CP_PATHS[@]}" | cut -f1,2 | tr '\t' '/')"
      git -C "$LANES_REPO" commit -q -m "LANES(concurrent@$WS): capture an uncommitted registry edit ($cap lines +/-) made by whoever else is writing right now — its author should follow up with a commit that says what it was" -- "${CP_PATHS[@]}" || :
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
      # The rebase has just put this invocation's commit on top of whatever
      # landed first. `claim` hooks in HERE, because that is the moment the
      # race is decided: if a peer's claim is on this history, theirs landed.
      if [ -n "${CP_AFTER_REBASE:-}" ]; then
        "$CP_AFTER_REBASE" || return $?
      fi
      if git -C "$LANES_REPO" push -q origin "$LANES_BRANCH"; then
        note "pushed origin/$LANES_BRANCH (attempt $attempt)"
        return 0
      fi
      note "push raced (attempt $attempt) — retrying"
    else
      note "REBASE CONFLICT on origin/$LANES_BRANCH — conflicting lines follow:"
      for cp in "${CP_PATHS[@]}"; do
        grep -n -e '^<<<<<<<' -e '^=======' -e '^>>>>>>>' -- "$LANES_REPO/$cp" 2>/dev/null | head -n 40 >&2 || :
        grep -n -A2 -e '^<<<<<<<' -- "$LANES_REPO/$cp" 2>/dev/null | head -n 40 >&2 || :
      done
      git -C "$LANES_REPO" rebase --abort 2>/dev/null || :
      note "rebase ABORTED — the worktree is clean and NOT mid-rebase. Your edit is safe in these local commits:"
      git -C "$LANES_REPO" --no-pager log --oneline "origin/$LANES_BRANCH..HEAD" 2>/dev/null | head -n 10 >&2 || :
      note "RECOVERY (in that order):"
      note "  git -C $LANES_REPO diff origin/$LANES_BRANCH..HEAD -- ${CP_PATHS[*]}   # read back exactly what you wrote"
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
  git -C "$LANES_REPO" --no-pager diff -- "${CP_PATHS[@]}" 2>/dev/null | awk '
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
  git -C "$LANES_REPO" --no-pager diff --stat -- "${CP_PATHS[@]}" >&2
  git -C "$LANES_REPO" --no-pager diff -- "${CP_PATHS[@]}" 2>/dev/null | awk '/^[+-][^+-]/ {print substr($0,1,200)}' >&2
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
  if [ "$#" -gt 0 ]; then CP_PATHS=("$@"); else CP_PATHS=("$LANES_PATH"); fi
  [ "$NO_GIT" = 1 ] && return 0
  git -C "$LANES_REPO" diff --quiet -- "${CP_PATHS[@]}" 2>/dev/null && return 0
  lanes="$(identify_changed_lanes)"; lanes="${lanes:-unknown}"
  note "WARNING: LANES.md already has uncommitted changes before this edit (row: $lanes) — not this invocation's"
  warn_dirty
  if [ "$SWEEP_MODE" = "sweep" ]; then
    PRE_DIRTY_LANES="$lanes"
    note "SWEEP_MODE=sweep — leaving it staged; it will land inside this invocation's own commit, annotated"
  else
    git -C "$LANES_REPO" add -- "${CP_PATHS[@]}"
    git -C "$LANES_REPO" commit -q -m "LANES(pre-existing@$WS): capture an uncommitted registry edit (row $lanes)" -- "${CP_PATHS[@]}" || :
    note "captured pre-existing edit (row $lanes) as its own commit"
  fi
  return 0
}

# R11 (Addendum 3, 2026-09-11) — a peer's uncommitted REGISTER edit is
# CAPTURED, not refused. `lanes/LANES.md` is dirty in this shared checkout for
# much of the day — the register takes ~500 commits a day and a half-written
# row is what one of them looks like a second before it lands — so refusing
# every `claim`, `log` and `release` on it would push lanes to stop using the
# tool, and the pre-existing capture already exists precisely to make that
# state safe to rebase over. So: capture FIRST, exactly as every register
# write has done since --no-sweep (the warning included), and let the guard
# re-test the checkout afterwards.
#
# Only when the register is NOT one of this write's own pathspecs: a LANDING
# or a LANDED commits it itself, and the ordinary handle_preexisting call
# covers it there, --sweep included. There is nothing to sweep a register edit
# INTO when this commit does not touch the register, so this capture is always
# its own commit whatever --sweep says.
#
# It is reached only AFTER write_event's first guard, so it never commits on
# behalf of a write that is about to refuse: a checkout dirty in anything ELSE
# is refused before the lock and before this runs, and a refusal that had
# already committed a peer's register edit would be a refusal that wrote.
capture_register_edit() {
  case " $* " in *" $LANES_PATH "*) return 0 ;; esac
  cre_mode="$SWEEP_MODE"
  SWEEP_MODE="no-sweep"
  handle_preexisting "$LANES_PATH"
  SWEEP_MODE="$cre_mode"
  return 0
}

# ======================================================== Amendment 7 ======
#
# THE PER-LANE OBJECT LOG.
#
#   lanes/log/<lane>.md — one file per lane, append-only, line 1 a header,
#   every other line an EVENT. This helper is the only writer, for the same
#   reason it is the register's only writer. One file per lane is also what
#   makes two workstations safe: two lanes writing at once touch two files.
#
#   <VERB> — lane <lane>, session <uuid>@<ws>, <UTC>, <object>[ → <payload>][ — <free text>]
#
#   The verb is ONE token. The first four fields are separated by `, `. The
#   OBJECT token contains no space and no comma; everything after it up to
#   ` — ` is payload, whose sub-fields are separated by `; ` and whose refs
#   are space-separated.
#
#   STATE IS PER LANE. A lane's state on an object is that lane's LAST line
#   naming it — the last such line IN THE FILE, never the largest UTC (R14);
#   the lane HOLDS the object when that verb is in the OPEN set; the object is
#   HELD when any lane holds it. There is no index file: a read fetches and
#   greps, because 45 lanes' logs together are smaller than one of the
#   register's rows.
#
#   LANES.md is unchanged. Its rows stay its rows and its Rule 6 LANDING /
#   LANDED lines stay where every lane already reads them as the merge hold —
#   which is why `who --landing` reads THOSE and not the logs. A LANDING or
#   LANDED writes both files in one commit, with two pathspecs.

LANES_PREFIX="${LANES_PREFIX:-$(git -C "$LANES_DIR" rev-parse --show-prefix 2>/dev/null || :)}"
LANES_LOG_DIR="${LANES_LOG_DIR:-$LANES_DIR/log}"
LANES_LOG_PREFIX="${LANES_LOG_PREFIX:-${LANES_PREFIX}log/}"
LANES_REPOS_TSV="${LANES_REPOS_TSV:-$LANES_DIR/repos.tsv}"
PROJECTS_ROOT="${PROJECTS_ROOT:-$HOME/projects}"
NO_GITHUB="${LANES_NO_GITHUB:-0}"
STALE_HOURS="${LANES_STALE_HOURS:-4}"     # Rule 1's threshold, reused

# The field separator for every machine-read line below. NOT a tab: a tab is
# IFS WHITESPACE, so bash's `read` collapses runs of them and one empty field
# (an event with no payload) shifts every field after it one to the left.
# \037 — US, "unit separator" — is not whitespace, so empty fields survive it.
US="$(printf '\037')"

utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# ---------------------------------------------------------------- the verbs
#
# A lane HOLDS an object while its own last line on it is OPEN. WITHDRAWN is
# open on purpose: withdrawing a landing leaves the PR held by the lane that
# withdrew it. The CLOSED set closes only the WRITING lane's hold — another
# lane's claim on the same object is untouched by it.
is_open_verb()   { case "$1" in CLAIMED|TAKEOVER|OPENED|LANDING|WITHDRAWN) return 0 ;; esac; return 1; }
is_closed_verb() { case "$1" in RELEASED|CLAIM-LOST|CLOSED|LANDED) return 0 ;; esac; return 1; }
is_lane_verb()   { case "$1" in STARTED|PAUSED|RESUMED|ENDED|RETIRED) return 0 ;; esac; return 1; }
valid_verb() {
  is_open_verb "$1" || is_closed_verb "$1" || is_lane_verb "$1"
}
VERB_LIST="CLAIMED RELEASED TAKEOVER CLOSED | OPENED LANDING LANDED WITHDRAWN | STARTED PAUSED RESUMED ENDED RETIRED | CLAIM-LOST"

check_lane_name() {
  case "${1-}" in
    "" | *[!A-Za-z0-9._-]* | .* | -*)
      die "'${1-}' is not a lane name (letters, digits, . _ -, not opening with . or -)" 2 ;;
  esac
}

log_file_for() { printf '%s/%s.md\n' "$LANES_LOG_DIR" "$1"; }
log_path_for() { printf '%s%s.md\n' "$LANES_LOG_PREFIX" "$1"; }

ensure_log() {
  lane="$1"; lf="$(log_file_for "$lane")"
  [ -d "$LANES_LOG_DIR" ] || mkdir -p -- "$LANES_LOG_DIR"
  if [ ! -f "$lf" ]; then
    printf '# lane %s — object log (lane-collision-protocol Amendment 7)\n' "$lane" > "$lf"
    note "created $lf"
  fi
}

# ------------------------------------------------------- the alias table
#
# `lanes/repos.tsv`, `alias<TAB>owner/repo`. Consulted when the owner is
# omitted, and when a spelling the register really uses is not the canonical
# nameWithOwner (all four spellings of codexFactory resolve to
# `codeXfactory/codexFactory`, which is the redirect GitHub answers with).
# Matching is case-insensitive: the register spells one repo `OpsxFactory`,
# `opsXfactory` and `opsxfactory` in the same week.
alias_lookup() {
  [ -f "$LANES_REPOS_TSV" ] || return 1
  awk -F'\t' -v k="$1" '
    BEGIN { kl = tolower(k) }
    /^[ \t]*#/ { next }
    NF >= 2 { if (tolower($1) == kl) { print $2; found = 1; exit } }
    END { exit(found ? 0 : 1) }' "$LANES_REPOS_TSV"
}

# canon_object <raw> [<home owner/repo>] — prints the canonical object key.
# THE KINDS IN SCOPE, and no others (a later amendment may add keys):
#   owner/repo#n                        an issue or a PR
#   owner/repo:openspec/changes/<name>  an OpenSpec change directory
#   #n                                  the lane's OWN home repo
#   lane:<name>                         a lane, for the lane-kind lines only
# Human acts, realization groups, contract cuts, file surfaces and Amendment
# 1's substrates stay where they are today — comments on their governing
# records — and are an explicit non-goal here.
canon_object() {
  co_raw="$1"; co_home="${2-}"; co_repo=""; co_rest=""; co_owner=""; co_hc=""
  case "$co_raw" in
    lane:*)
      case "${co_raw#lane:}" in
        "" | *[!A-Za-z0-9._-]*) note "'$co_raw' is not a lane object: lane:<name>"; return 2 ;;
      esac
      printf '%s\n' "$co_raw"; return 0 ;;
    '#'*)
      case "${co_raw#\#}" in
        "" | *[!0-9]*) note "'$co_raw' is not an object key: after '#' comes the issue or PR number"; return 2 ;;
      esac
      if [ -z "$co_home" ]; then
        note "'$co_raw' is shorthand for this lane's home repo, and no home is on record for it."
        note "  Spell it owner/repo$co_raw, or pass --home owner/repo (a pre-cutover lane has no STARTED line)."
        return 2
      fi
      if ! valid_nwo "$co_home"; then
        note "'$co_home' is not a repository, so '$co_raw' cannot be expanded against it."
        note "  A home is owner/repo. This one came from the lane's STARTED line or from --home."
        return 2
      fi
      # R20 — THE HOME GOES THROUGH THE ALIAS TABLE TOO, on the way into a key.
      # `home_of_lane` and `resolve_home` both resolve already; this is the last
      # gate, so no caller can reach a key by a path that skipped it. A checkout
      # whose origin still spells `opensoft/codexFactory` wrote `#5` as a key
      # nothing could reconcile with `codeXfactory/codexFactory#5`, and two lanes
      # held one issue with no collision detected.
      co_hc="$(alias_lookup "$co_home" 2>/dev/null || :)"
      [ -n "$co_hc" ] && co_home="$co_hc"
      printf '%s%s\n' "$co_home" "$co_raw"; return 0 ;;
    *:openspec/changes/*)
      co_repo="${co_raw%%:openspec/changes/*}"
      co_rest=":openspec/changes/${co_raw#*:openspec/changes/}"
      case "${co_rest#:openspec/changes/}" in
        "" | *[!A-Za-z0-9._-]*) note "'$co_raw' is not an object key: an OpenSpec change is owner/repo:openspec/changes/<name>"; return 2 ;;
      esac ;;
    *'#'*)
      co_repo="${co_raw%%#*}"
      co_rest="#${co_raw#*#}"
      case "${co_rest#\#}" in
        "" | *[!0-9]*) note "'$co_raw' is not an object key: after '#' comes the issue or PR number"; return 2 ;;
      esac ;;
    *)
      note "'$co_raw' is not an object key. In scope: owner/repo#<n>, owner/repo:openspec/changes/<name>, #<n> for this lane's home repo, lane:<name>."
      return 2 ;;
  esac
  [ -n "$co_repo" ] || { note "'$co_raw' names no repository"; return 2; }
  co_owner="$(alias_lookup "$co_repo" 2>/dev/null || :)"
  if [ -z "$co_owner" ]; then
    case "$co_repo" in
      */*) co_owner="$co_repo" ;;     # a spelled owner/repo is always accepted
      *)
        note "unknown repo alias '$co_repo' — spell it owner/repo (the canonical GitHub nameWithOwner), or add it to ${LANES_LOG_PREFIX%log/}repos.tsv"
        return 2 ;;
    esac
  fi
  case "$co_owner" in
    */*/*|*/) note "the alias table maps '$co_repo' to '$co_owner', which is not owner/repo"; return 2 ;;
    */*) : ;;
    *) note "the alias table maps '$co_repo' to '$co_owner', which is not owner/repo"; return 2 ;;
  esac
  case "$co_owner" in *[!A-Za-z0-9./_-]*) note "'$co_owner' is not a usable owner/repo"; return 2 ;; esac
  printf '%s%s\n' "$co_owner" "$co_rest"
}

# owner/repo, and nothing else: exactly one slash, and only the characters
# GitHub allows in either half. `--home 'not a repo'` used to go straight into
# an object key, and the helper wrote `not a repo#42` — a line its OWN parser
# cannot read back, in a log nothing ever rewrites.
valid_nwo() { [[ "${1-}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; }

# The home repo for this invocation. `--home` is for a PRE-CUTOVER lane — one
# whose log has no STARTED line — and is REFUSED where the log already answers
# the question, so the flag and the log can never disagree. It is resolved
# through the alias table and then validated, like any other spelling.
#
# R30 (Addendum 7) — AND EVERY CALLER ASKS AFTER THE FETCH. The STARTED line it
# reads is `origin/<branch>`'s, like every other state read, so a home a peer
# recorded is invisible here until `log_sync` has run: asked before it, `--home`
# was ACCEPTED on a lane whose own log already answers the question — the one
# refusal this flag has — and the object key it then built was the second
# spelling of an issue another lane was already holding. `who` and `lane-end`'s
# `resolve-home` preflight fetched first already; `log`, `claim` and `release`
# now do too, so the preflight and the write can still never disagree.
#
# Called as `home="$(resolve_home "$lane" "$override")" || exit $?` — a `die`
# in here runs inside the command substitution, so the caller must pass the
# code on rather than carry on with an empty home.
resolve_home() {
  rh_lane="${1-}"; rh_over="${2-}"; rh_log=""
  [ -n "$rh_lane" ] && rh_log="$(home_of_lane "$rh_lane" 2>/dev/null || :)"
  if [ -n "$rh_over" ]; then
    if [ -n "$rh_log" ]; then
      note "lane $rh_lane's own log already records its home: $rh_log (from its STARTED line)."
      die "--home is for a pre-cutover lane, one whose log has no STARTED line. Drop it, or correct the lane's home by appending a new STARTED line through lane-start." 2
    fi
    rh_res="$(alias_lookup "$rh_over" 2>/dev/null || :)"; rh_over="${rh_res:-$rh_over}"
    valid_nwo "$rh_over" || die "--home takes owner/repo (the canonical GitHub nameWithOwner), or an alias in ${LANES_LOG_PREFIX%log/}repos.tsv: '${2-}' is neither" 2
    printf '%s\n' "$rh_over"
    return 0
  fi
  printf '%s\n' "$rh_log"
}

is_lane_object() { case "$1" in lane:*) return 0 ;; esac; return 1; }
object_repo()    { case "$1" in lane:*) printf '\n' ;; *:openspec/changes/*) printf '%s\n' "${1%%:openspec/changes/*}" ;; *) printf '%s\n' "${1%%#*}" ;; esac; }
object_number()  { case "$1" in lane:*|*:openspec/changes/*) printf '\n' ;; *'#'*) printf '%s\n' "${1##*#}" ;; *) printf '\n' ;; esac; }
object_slug()    { case "$1" in *:openspec/changes/*) printf '%s\n' "${1##*/}" ;; *'#'*) printf '%s\n' "${1##*#}" ;; *) printf '%s\n' "$1" ;; esac; }

# ------------------------------------------------------- reading the logs
#
# One parser, used by everything. It prints US-separated fields, UTC first:
#   utc  lane  verb  uuid  ws  object  ref  payload  text  file  line
#
# The last two are the line's ADDRESS — the file it was read from and its
# number IN THAT FILE (FNR, so it is the number the reader sees in the log and
# the number an `unreadable:` report names). That address is what every state
# read orders by (R14): the log is append-only, so a line further down the file
# is a line written later, whatever the two lines' UTC fields say.
# `match()` is used for every multi-byte separator: RSTART and RLENGTH are in
# the same units as each other whatever the locale, and a hard-coded byte
# offset for " — " is not.
LOG_AWK='
function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
# A LINE IS NEVER DROPPED SILENTLY. This log is append-only and nothing in it
# is ever rewritten, so a line no parser can read is a hold no tool will
# mention again — `who` would call the object free, and it is not.
function bad(why,   f) {
  f = (FN != "" ? FN : FILENAME)
  printf "unreadable: %s:%d (%s)\n", f, FNR, why > "/dev/stderr"
  nbad++
}
{
  line = $0
  if (line ~ /^[ \t]*#/ || line ~ /^[ \t]*$/) next
  if (match(line, / — /) == 0) { bad("no \" — \" after the verb"); next }
  verb = trim(substr(line, 1, RSTART - 1))
  rest = substr(line, RSTART + RLENGTH)
  if (index(verb, " ") > 0) { bad("the verb is one token: \"" verb "\""); next }
  if (substr(rest, 1, 5) != "lane ") { bad("no \"lane <name>\" field"); next }
  rest = substr(rest, 6)
  q = index(rest, ","); if (q == 0) { bad("no \",\" after the lane"); next }
  lane = trim(substr(rest, 1, q - 1)); rest = trim(substr(rest, q + 1))
  if (substr(rest, 1, 8) != "session ") { bad("no \"session <uuid>@<ws>\" field"); next }
  rest = substr(rest, 9)
  q = index(rest, ","); if (q == 0) { bad("no \",\" after the session"); next }
  sess = trim(substr(rest, 1, q - 1)); rest = trim(substr(rest, q + 1))
  a = index(sess, "@")
  uuid = (a ? substr(sess, 1, a - 1) : sess)
  ws   = (a ? substr(sess, a + 1) : "")
  # The UTC is matched by SHAPE. Taking it up to the next comma would be
  # wrong for any line whose object is followed by nothing at all. The
  # seconds are optional: the register carries `…T20:31Z` lines from before
  # this helper existed, and refusing to read one loses a hold.
  if (match(rest, /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9](:[0-9][0-9])?Z/) == 0) { bad("no YYYY-MM-DDTHH:MM[:SS]Z"); next }
  utc = substr(rest, RSTART, RLENGTH)
  rest = substr(rest, RSTART + RLENGTH)
  if (substr(rest, 1, 1) != ",") { bad("no \",\" and object after the UTC"); next }
  rest = trim(substr(rest, 2))
  # The object token contains no space and no comma, so it ends at the first
  # space — which is what makes the payload unambiguous however it is spelled.
  sp = index(rest, " ")
  if (sp == 0) { obj = rest; rest = "" }
  else         { obj = substr(rest, 1, sp - 1); rest = substr(rest, sp + 1) }
  ref = ""; payload = ""; txt = ""
  # Every test below is a REGEX, never a substr() width: RSTART and RLENGTH
  # are in whatever unit the locale counts in, and they agree with each other.
  # A hard-coded 4 for "— " does not, and gawk counts characters.
  if (rest != "") {
    if (match(rest, /^— /)) { txt = trim(substr(rest, RSTART + RLENGTH)) }
    else {
      if (match(rest, / — /)) { txt = trim(substr(rest, RSTART + RLENGTH)); rest = trim(substr(rest, 1, RSTART - 1)) }
      if (match(rest, /^→ /))      { ref = "→"; payload = trim(substr(rest, RSTART + RLENGTH)) }
      else if (match(rest, /^← /)) { ref = "←"; payload = trim(substr(rest, RSTART + RLENGTH)) }
      else { payload = trim(rest) }
    }
  }
  printf "%s%c%s%c%s%c%s%c%s%c%s%c%s%c%s%c%s%c%s%c%d\n", utc, 31, lane, 31, verb, 31, uuid, 31, ws, 31, obj, 31, ref, 31, payload, 31, txt, 31, (FN != "" ? FN : FILENAME), 31, FNR
}
END { if (nbad > 0) printf "%d unreadable line(s) above — an append-only log is never rewritten, so a line no parser reads is a hold no tool will mention again\n", nbad > "/dev/stderr" }'

parse_log_stream() { awk -v FN="${1:-}" "$LOG_AWK"; }

log_files() {
  for le_f in "$LANES_LOG_DIR"/*.md; do
    [ -e "$le_f" ] || continue
    case "${le_f##*/}" in README.md) continue ;; esac
    printf '%s\n' "$le_f"
  done
}

log_events() {
  le_files=()
  if [ "$#" -gt 0 ]; then
    le_files=("$@")
  else
    while IFS= read -r le_f; do [ -n "$le_f" ] && le_files+=("$le_f"); done <<EOF
$(log_files)
EOF
  fi
  [ "${#le_files[@]}" -gt 0 ] || return 0
  awk -v FN="" "$LOG_AWK" "${le_files[@]}"
}

# Is there an `origin/<branch>` to read from at all? Outside a repository, and
# under the LANES_NO_GIT=1 harness, there is not, and the working tree is all
# there is.
have_remote_ref() {
  [ "$NO_GIT" = 1 ] && return 1
  git -C "$LANES_REPO" rev-parse --verify -q "origin/$LANES_BRANCH" >/dev/null 2>&1
}

# The same events, read from `origin/<branch>` instead of the working tree.
# EVERY state read goes through state_events() below, which reads THIS: what
# has LANDED is what other lanes can see, and a working tree can be anything —
# behind by a peer's whole day, or carrying a line that never lands.
remote_log_events() {
  [ "$NO_GIT" = 1 ] && { log_events; return 0; }
  git -C "$LANES_REPO" rev-parse --verify -q "origin/$LANES_BRANCH" >/dev/null 2>&1 || { log_events; return 0; }
  git -C "$LANES_REPO" ls-tree --name-only "origin/$LANES_BRANCH" -- "$LANES_LOG_PREFIX" 2>/dev/null \
  | while IFS= read -r rf; do
      [ -n "$rf" ] || continue
      case "${rf##*/}" in README.md) continue ;; esac
      git -C "$LANES_REPO" show "origin/$LANES_BRANCH:$rf" 2>/dev/null | parse_log_stream "$rf"
    done
}

# THE SOURCE OF EVERY STATE READ. Cached for the life of one invocation,
# because `who` on a held object asks for it eight or nine times (the state
# scan, the superseded filter once per holder, staleness twice, the crossing
# check) and reading it is 45 `git show`s. Any write flushes it: `claim`
# rescans after its rebase, and the ref has moved by then.
SE_CACHE_FILE="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-events.XXXXXX" 2>/dev/null || printf '')"
state_events() {
  if [ -z "$SE_CACHE_FILE" ]; then remote_log_events; return 0; fi
  if [ ! -s "$SE_CACHE_FILE" ]; then
    # BUILT ATOMICALLY, because `claim` asks for this from both ends of one
    # pipeline: `state_events | lane_states_on | holders_of`, and holders_of
    # calls superseded_by, which asks again while the first read is still
    # writing. A half-written cache read as a whole one loses lines, and a
    # lost line is a hold that has vanished. Write to a per-subshell name and
    # rename: a reader then sees either the empty file (and builds its own) or
    # the finished one, never half of it.
    se_t="$SE_CACHE_FILE.${BASHPID:-$$}"
    remote_log_events > "$se_t"
    mv -f -- "$se_t" "$SE_CACHE_FILE" 2>/dev/null || { cat -- "$se_t"; rm -f -- "$se_t"; return 0; }
  fi
  cat -- "$SE_CACHE_FILE"
}
state_events_flush() { [ -n "$SE_CACHE_FILE" ] && : > "$SE_CACHE_FILE"; return 0; }

# One lane's own events, and whether that lane has a log at all — from
# `origin/<branch>` for the same reason. A lane whose log exists only in this
# working tree has not published anything, and a lane whose log exists only on
# `origin` is a lane this checkout has not pulled: the second is the case that
# matters and the one that used to read as "pre-cutover".
lane_log_events() {
  ll_rel="$(log_path_for "$1")"
  if have_remote_ref; then
    git -C "$LANES_REPO" show "origin/$LANES_BRANCH:$ll_rel" 2>/dev/null | parse_log_stream "$ll_rel"
  else
    ll_f="$(log_file_for "$1")"
    [ -f "$ll_f" ] || return 0
    log_events "$ll_f"
  fi
}
lane_log_exists() {
  if have_remote_ref; then
    git -C "$LANES_REPO" cat-file -e "origin/$LANES_BRANCH:$(log_path_for "$1")" 2>/dev/null
  else
    [ -f "$(log_file_for "$1")" ]
  fi
}

# The register, read the same way — `who --landing` is a state read about a
# merge hold other lanes are holding their merges for, so it must see what
# landed rather than what this checkout happens to have pulled.
register_text() {
  if have_remote_ref && git -C "$LANES_REPO" cat-file -e "origin/$LANES_BRANCH:$LANES_PATH" 2>/dev/null; then
    git -C "$LANES_REPO" show "origin/$LANES_BRANCH:$LANES_PATH" 2>/dev/null
  else
    cat -- "$LANES_FILE"
  fi
}

# Each lane's LAST line on <object>, as
#   utc  lane  verb  uuid  ws  object  ref  payload  text  file  line
#
# R14 — "LAST" IS THE LAST LINE IN THE FILE, and never the largest UTC. One
# lane's log is append-only and single-writer, so its line order IS that lane's
# write order; a clock is not. It was a max-UTC read here that made a LANDED
# invisible behind the LANDING it closed, on the day this workstation's clock
# was jumping ±25s. `pos()` is the line's address — its file and its line
# number, zero-padded so that one string comparison orders both.
PER_LANE_AWK='
function pos(pf, pn) { return pf "\034" sprintf("%09d", pn) }
BEGIN { FS = sep }
$6 == o { p = pos($10, $11); if (!($2 in u) || p >= u[$2]) { u[$2] = p; L[$2] = $0 } }
END { for (l in u) print L[l] }'

# Ordered by LANE NAME, deliberately. These rows are one line per lane, so
# nothing about their order is a fact about the object: which lane got there
# first is LANDING ORDER ON `main` (F13), which `first_landed_of` reads out of
# git history. This sort used to be on the UTC field, and sorting a set of
# lanes by their clocks is exactly the comparison R14 removes.
lane_states_on() {   # <object> [events-producer-output on stdin]
  awk -v sep="$US" -v o="$1" "$PER_LANE_AWK" | LC_ALL=C sort -t"$US" -k2,2
}

# The lanes that HOLD <object> — those whose own last line on it is open.
# Prints  lane  verb  utc  file  line: the last two are the ADDRESS of that
# lane's own last line, which is what a staleness test needs in order to ask
# "has this lane written anything BELOW it in its own log" without a clock.
holders_of() {
  hf_obj="$1"
  while IFS="$US" read -r h_utc h_lane h_verb h_uuid h_ws h_o h_ref h_pay h_txt h_file h_line; do
    [ -n "${h_verb:-}" ] || continue
    is_open_verb "$h_verb" || continue
    # A CLAIMED that another lane has since taken over is not a hold.
    [ -z "$(superseded_by "$hf_obj" "$h_lane" "$h_verb")" ] || continue
    printf '%s%s%s%s%s%s%s%s%s\n' "$h_lane" "$US" "$h_verb" "$US" "$h_utc" "$US" "$h_file" "$US" "$h_line"
  done
}

# Every object this lane's OWN log mentions, with the lane's last verb on it.
# `lane-end`'s refusal and `who --lane` both read exactly this.
# Every object this lane's OWN log mentions, with the lane's last verb on it,
# plus — read from EVERY lane's log — whether another lane has since taken the
# object over. A lane closes only its own hold, so after someone else's
# TAKEOVER this lane's last line is still its CLAIMED; without the fifth field
# `lane-end` would refuse for ever and never say why.
#   utc  verb  object  ref+payload  superseded-by(lane@utc, or empty)
lane_objects() {
  lane_log_exists "$1" || return 8      # 8, not 1: "no log file" is an ANSWER
  state_events | awk -v sep="$US" -v me="$1" '
    function pos(pf, pn) { return pf "\034" sprintf("%09d", pn) }
    BEGIN { FS = sep }
    $6 ~ /^lane:/ { next }
    $2 == me {
      if (!($6 in ord)) { ord[$6] = ++n; byn[n] = $6 }
      p = pos($10, $11)
      if (!($6 in mp) || p >= mp[$6]) { mp[$6] = p; utc[$6] = $1; verb[$6] = $3; ref[$6] = $7; pay[$6] = $8 }
    }
    # EVERY OTHER LANE, ITS OWN LAST LINE on each object, by the same file-order
    # rule this lane is read by (R14). The verb is kept, not only the TAKEOVERs,
    # because what decides supersession is whether a TAKEOVER is still the last
    # word of the lane that wrote it — see the END block.
    $2 != me {
      q = pos($10, $11)
      if (!(($6 SUBSEP $2) in op) || q >= op[$6, $2]) { op[$6, $2] = q; ov[$6, $2] = $3; ou[$6, $2] = $1 }
    }
    # SUPERSEDED, WITHOUT ORDERING TWO FILES AGAINST EACH OTHER (R14), AND ONLY
    # WHILE THE TAKEOVER STILL STANDS (R18): another lane has a TAKEOVER on the
    # object AS ITS OWN LAST LINE, and this lane has written nothing on it since
    # — the last line here is still the CLAIMED that was taken. A TAKEOVER is
    # never removed from an append-only log, so testing for one ANYWHERE in the
    # file of the taker kept superseding these claims for ever: after that lane
    # released the object and this one legitimately re-claimed it, `who` called
    # the object FREE and a third lane was not refused. A TAKEOVER displaces a
    # CLAIMED and nothing else (`claim --force` refuses every other verb), so
    # that is the whole of the test; any later line of this lane is it speaking
    # after the fact and is reported as it stands. The two lines sit in two
    # different lanes, whose files share no clock, and this asks for none.
    END { for (kk in ov) if (ov[kk] == "TAKEOVER") {
            split(kk, aa, SUBSEP); oo = aa[1]; ll = aa[2]
            if (!(oo in tp) || op[kk] >= tp[oo]) { tp[oo] = op[kk]; tlane[oo] = ll; tutc[oo] = ou[kk] } }
          for (i = 1; i <= n; i++) { o = byn[i]
            sup = ((o in tlane) && verb[o] == "CLAIMED") ? tlane[o] "@" tutc[o] : ""
            printf "%s%c%s%c%s%c%s%c%s\n", utc[o], 31, verb[o], 31, o, 31, (ref[o] ? ref[o] " " pay[o] : ""), 31, sup } }'
}

# The lane and UTC of a TAKEOVER on <object> that is STILL THAT LANE'S OWN LAST
# LINE on it — printed only when $3, our own last verb on the object, is the
# CLAIMED a takeover displaces. Empty when there is none.
#
# R18 — "ITS OWN LAST LINE" IS THE WHOLE OF THE BOUND. Per-lane last-line
# semantics apply to the taker too: once the taker writes RELEASED, CLOSED or
# LANDED on the object, its TAKEOVER supersedes nothing and a later CLAIMED by
# the dispossessed lane holds. Matching any TAKEOVER anywhere in the taker's
# append-only file made a legitimate re-claim invisible for ever: `who` called
# a held object FREE, `claim` did not refuse the next lane — the single outcome
# Rule 1 exists to prevent — and `who --lane` and `lane-end` disagreed about the
# same object.
#
# NO TIMESTAMP IS COMPARED (R14): the two lines are in two lanes' files and
# there is no shared clock to order them by, so the question asked is the one
# file order can answer — is our own last line still the claim, and is a
# TAKEOVER still theirs. The UTC printed beside the lane is information for the
# reader, never a key. When two lanes both end on a TAKEOVER the file-ordered
# position picks which one is NAMED; both are holders either way, and that
# conflict is visible in `who` rather than resolved here (see README, "Known").
superseded_by() {   # <object> <lane> <that lane's own last verb on it>
  [ "${3-}" = CLAIMED ] || return 0
  state_events | awk -v sep="$US" -v o="$1" -v me="$2" '
    function pos(pf, pn) { return pf "\034" sprintf("%09d", pn) }
    BEGIN { FS = sep }
    $6 == o && $2 != me { p = pos($10, $11); if (!($2 in q) || p >= q[$2]) { q[$2] = p; v[$2] = $3; u[$2] = $1 } }
    END { for (l in q) if (v[l] == "TAKEOVER" && (!seen || q[l] >= b)) { seen = 1; b = q[l]; bl = l; bu = u[l] }
          if (seen) print bl "@" bu }'
}

# A lane's HOME repo, from the payload of its own STARTED (or RESUMED) line.
# `<repo>-<n>` is a label, not a scope: this is the only thing that says where
# a lane actually lives.
# R20 — and the answer is CANONICAL. A STARTED line records whatever spelling
# that checkout's `origin` had on the day, and the register's own history proves
# those drift (`opensoft/codexFactory` is today `codeXfactory/codexFactory`).
# Every comparison of an object's repository against a home — canon_object's
# `#n`, cross_repo_warn, same_project, who's CROSS-REPO note — resolves BOTH
# sides, and resolving here is what makes that true of all of them at once.
home_of_lane() {
  lane_log_exists "$1" || return 1
  hol_h="$(lane_log_events "$1" | awk -v sep="$US" '
    BEGIN { FS = sep }
    $3 == "STARTED" || $3 == "RESUMED" {
      if (match($8, /home [^ ;]+/)) h = substr($8, RSTART + 5, RLENGTH - 5)
    }
    END { if (h != "" && h != "unknown") print h; else exit 1 }')" || return 1
  [ -n "$hol_h" ] || return 1
  hol_c="$(alias_lookup "$hol_h" 2>/dev/null || :)"
  printf '%s\n' "${hol_c:-$hol_h}"
}

known_lanes() {
  if have_remote_ref; then
    git -C "$LANES_REPO" ls-tree --name-only "origin/$LANES_BRANCH" -- "$LANES_LOG_PREFIX" 2>/dev/null \
    | while IFS= read -r kl_f; do
        [ -n "$kl_f" ] || continue
        kl_n="${kl_f##*/}"
        case "$kl_n" in README.md) continue ;; esac
        printf '%s\n' "${kl_n%.md}"
      done
    return 0
  fi
  while IFS= read -r kl_f; do
    [ -n "$kl_f" ] || continue
    kl_n="${kl_f##*/}"; printf '%s\n' "${kl_n%.md}"
  done <<EOF
$(log_files)
EOF
}

# ---------------------------------------------------------- age and staleness

epoch_of() { date -u -d "$1" +%s 2>/dev/null || printf ''; }

age_of() {
  ao_t="$(epoch_of "$1")"
  if [ -z "$ao_t" ]; then printf 'age unknown'; return 0; fi
  ao_d=$(( $(date -u +%s) - ao_t )); [ "$ao_d" -lt 0 ] && ao_d=0
  printf '%dh %02dm' "$((ao_d / 3600))" "$(((ao_d % 3600) / 60))"
}

lc() { printf '%s' "${1-}" | tr 'A-Z' 'a-z'; }

older_than_minutes() {   # <utc> <minutes>
  om_t="$(epoch_of "$1")"; [ -n "$om_t" ] || return 1
  [ "$(( $(date -u +%s) - om_t ))" -gt "$(( $2 * 60 ))" ]
}

older_than_threshold() {
  st_t="$(epoch_of "$1")"; [ -n "$st_t" ] || return 1
  [ "$(( $(date -u +%s) - st_t ))" -gt "$((STALE_HOURS * 3600))" ]
}

# An object is treated as a PR once some lane has written OPENED on it. That
# is the only offline evidence there is, and it is exactly the evidence Rule 1
# cares about: a claim followed by a PR is not abandoned.
object_is_pr() {
  op_o="$1"
  state_events | awk -v sep="$US" -v o="$op_o" 'BEGIN{FS=sep} $6 == o && $3 == "OPENED" { f = 1 } END { exit(f ? 0 : 1) }'
}

# Rule 1's staleness, made checkable. A lane's CLAIMED on an ISSUE is stale
# when it is older than four hours AND that lane has written no later OPENED
# whose `←` payload names the issue. A PR is never stale by this rule — Rule 6
# governs PRs, with its own thirty minutes.
# "LATER" IS FURTHER DOWN THE SAME FILE (R14). The four hours above is a
# DURATION and stays on the clock, where ±25s is immaterial; this is an ORDER
# between two lines of one append-only log, and it is read off the log.
claim_is_stale() {   # <lane> <object> <utc-of-the-claim> <its file> <its line>
  cs_lane="$1"; cs_obj="$2"; cs_utc="$3"; cs_file="${4-}"; cs_line="${5-0}"
  older_than_threshold "$cs_utc" || return 1
  object_is_pr "$cs_obj" && return 1
  state_events | awk -v sep="$US" -v l="$cs_lane" -v o="$cs_obj" -v f="$cs_file" -v ln="$cs_line" '
    BEGIN { FS = sep }
    $2 == l && $3 == "OPENED" && $10 == f && ($11 + 0) > (ln + 0) {
      # the `←` payload is space-separated issue keys
      n = split($8, a, " ")
      for (i = 1; i <= n; i++) if (a[i] == o) { found = 1 }
    }
    END { exit(found ? 1 : 0) }'
}

# ------------------------------------------------------------- liveness
#
# ONE implementation, here, because `lane-start` and `who` must agree about
# what "live" means — `lane-start` asks for it with the `live-holder`
# subcommand rather than keeping a second copy that can drift.
#
# LIVE iff a session record ON THIS WORKSTATION carries one of the row's
# transcript uuids, its `status` is not one of {ended, exited, dead, stopped},
# its pid is alive, and `/proc/<pid>/stat` field 22 still equals the
# `procStart` the record wrote down.

# Every session record on this workstation, one path per line.
#
# R22 — AND IT SAYS WHETHER IT COULD READ THEM. Returns 0 when every records
# tree that EXISTS was listed without error, and 1 when one existed and could
# not be — a permissions or IO fault, which is not the same answer as "no record
# holds this lane" and must never be reported as one. A tree that is simply
# absent is not a failure: a workstation may have only one of the two.
SESSION_FILES_ERR=""
session_files() {
  sf_rc=0; sf_d=""; sf_err=""
  SESSION_FILES_ERR=""
  sf_err="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-sf.XXXXXX" 2>/dev/null || printf '')"
  if [ -z "$sf_err" ]; then
    SESSION_FILES_ERR="could not create a temporary file under ${TMPDIR:-/tmp}"
    return 1
  fi
  # Team profiles sit two levels down (profiles/<org>/<team>/<profile>/sessions/),
  # so that one is a -path find and not a one-level glob.
  for sf_d in "$HOME/.claude-profiles/profiles" "$HOME/.claude/sessions"; do
    [ -e "$sf_d" ] || continue
    case "$sf_d" in
      */sessions) find "$sf_d" -maxdepth 1 -name '*.json' -type f 2>>"$sf_err" || sf_rc=1 ;;
      *)          find "$sf_d" -path '*/sessions/*.json' -type f 2>>"$sf_err" || sf_rc=1 ;;
    esac
  done
  if [ -s "$sf_err" ]; then
    SESSION_FILES_ERR="$(tr '\n' ';' < "$sf_err" | cut -c1-300)"
    sf_rc=1
  fi
  rm -f -- "$sf_err"
  return "$sf_rc"
}

jstr() { printf '%s' "$1" | grep -o "\"$2\":\"[^\"]*\"" | head -n1 | sed 's/^.*":"//; s/"$//'; }
jnum() { printf '%s' "$1" | grep -o "\"$2\":[0-9][0-9]*" | head -n1 | sed 's/^.*://'; }

pid_alive() {
  local pid="$1" want="$2" statline rest
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  [ -n "$want" ] || return 0
  [ -r "/proc/$pid/stat" ] || return 0
  statline="$(cat "/proc/$pid/stat" 2>/dev/null || :)"
  rest="${statline##*) }"
  # shellcheck disable=SC2086
  set -- $rest
  [ "$#" -ge 20 ] || return 0
  [ "${20}" = "$want" ]
}

# A session record's `name` is EVIDENCE ABOUT ANOTHER LANE only when a person
# or a `--name` set it. The values real records carry on this estate are:
#
#   derived   the harness named the window after its working directory
#   auto      the harness named it without being told to
#   user      a person typed `/rename`, or `--name` was passed
#   peer      another session in the mesh set it
#
# EXPLICIT is {user, peer} — the two a person or `--name` produces. A record
# with any other value, or with none at all, says nothing either way about
# which lane it is, and is therefore NOT read as a denial.
#
# This is a fix, not a preference. On 2026-09-11 the orchestrator's own record
# read `name: openrepoproject-63, nameSource: derived` while it held lane
# openRepoProject-1 — pid alive, procStart matching, status busy — and the old
# filter skipped it on the name alone, so a dry run reported "no live session
# holds openRepoProject-1" and a second window would not have been refused.
# 274 of this estate's 341 records carry `derived`.
EXPLICIT_NAME_SOURCES="user peer"
name_is_explicit() {
  case " $EXPLICIT_NAME_SOURCES " in *" ${1:-} "*) return 0 ;; esac
  return 1
}

# live_holder <lane> [<newline-separated session ids>]
#
# R22 — IT FAILS CLOSED AT THE SOURCE. Three answers, and they are distinct:
#   0  a live record holds the lane (the row is printed)
#   8  the records were READ, and none of them does
#   1  the records could not be read — a permissions or IO fault
# `lane-start` renames a window on 8 and REFUSES on anything else, so collapsing
# a failed read into 8 is exactly how a running lane loses its address: the
# rename mints `<lane> (2)` (AGENTS.md rule 7). The first version returned 1 for
# both, which is the same fault one layer up; hardening the CALLER left this
# source with no way to say "I could not read".
live_holder() {
  local lane="$1" ids="${2-}" pats=() f blob pid name status target sid base src
  local lh_files lh_match lh_err
  SESSION_FILES_ERR=""
  [ -n "$ids" ] || ids="$(session_ids_of_lane "$lane" 2>/dev/null || :)"
  # A row with no transcript uuid in it is an ANSWER: nothing recorded can be
  # live. It is not a failed read.
  [ -n "$ids" ] || return 8
  for sid in $ids; do pats+=(-e "\"sessionId\":\"$sid\""); done
  [ "${#pats[@]}" -gt 0 ] || return 8
  lh_files="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-lf.XXXXXX" 2>/dev/null || printf '')"
  lh_match="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-lm.XXXXXX" 2>/dev/null || printf '')"
  lh_err="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-le.XXXXXX" 2>/dev/null || printf '')"
  if [ -z "$lh_files" ] || [ -z "$lh_match" ] || [ -z "$lh_err" ]; then
    rm -f -- "$lh_files" "$lh_match" "$lh_err" 2>/dev/null || :
    SESSION_FILES_ERR="could not create a temporary file under ${TMPDIR:-/tmp}"
    return 1
  fi
  # NOT `$( )`: session_files sets SESSION_FILES_ERR, and a subshell would keep
  # the reason for the failure to itself.
  if ! session_files > "$lh_files"; then
    rm -f -- "$lh_files" "$lh_match" "$lh_err"
    return 1
  fi
  if [ ! -s "$lh_files" ]; then
    rm -f -- "$lh_files" "$lh_match" "$lh_err"
    return 8                       # this workstation keeps no records at all
  fi
  tr '\n' '\0' < "$lh_files" | xargs -0 -r grep -l -F "${pats[@]}" > "$lh_match" 2>"$lh_err" || :
  if [ -s "$lh_err" ]; then        # a record that exists and cannot be read
    SESSION_FILES_ERR="$(tr '\n' ';' < "$lh_err" | cut -c1-300)"
    rm -f -- "$lh_files" "$lh_match" "$lh_err"
    return 1
  fi
  rm -f -- "$lh_files" "$lh_err"
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    blob="$(cat -- "$f" 2>/dev/null || :)"
    sid="$(jstr "$blob" sessionId)"
    status="$(jstr "$blob" status)"
    case "$status" in ended|exited|dead|stopped) continue ;; esac
    pid="$(jnum "$blob" pid)"
    pid_alive "$pid" "$(jstr "$blob" procStart)" || continue
    name="$(jstr "$blob" name)"
    src="$(jstr "$blob" nameSource)"
    base="${name% (*)}"
    if [ -n "$base" ] && [ "${base,,}" != "${lane,,}" ] && name_is_explicit "$src"; then continue; fi
    target="$(jstr "$blob" tmux)"
    printf '%s%s%s%s%s%s%s\n' "$sid" "$US" "${target:-none}" "$US" "${name:-none}" "$US" "$pid"
    rm -f -- "$lh_match"
    return 0
  done < "$lh_match"
  rm -f -- "$lh_match"
  return 8
}

# ------------------------------------------------------------ the row, read
#
# R19 — FROM `origin/<branch>`, LIKE EVERY OTHER STATE READ. These four reads
# (the row itself, its session cell, its handoff path and its workstation
# column) were the last ones taking the WORKING TREE, and `print_holder_detail`
# is built entirely out of them — so `who` routinely answered with a current log
# and a stale row: a holder recorded on the other workstation read `NOT LIVE`
# because a peer's UNCOMMITTED edit to column 3 said `Eagle`, and a row that
# exists only on `origin/main` was not seen at all, losing the resume uuid and
# the handoff path, which are the two things `who` exists to hand over. Nothing
# in `who` reads the working tree now.

ROW_AWK='
  substr($0,1,1) == "|" {
    p1 = index($0, "`"); if (p1 == 0) next
    rest = substr($0, p1 + 1); p2 = index(rest, "`"); if (p2 == 0) next
    if (substr(rest, 1, p2 - 1) == lane) print
  }'
row_of_lane()       { register_text | awk -v lane="$1" "$ROW_AWK"; }
# The same row as THIS CHECKOUT has it. One caller: the `live-holder`
# subcommand, which unions these ids with the published ones because liveness
# fails CLOSED — an id this checkout knows and `origin/main` does not yet is one
# more reason to refuse a rename, never a reason to allow one (AGENTS.md rule 7).
row_of_lane_local() { awk -v lane="$1" "$ROW_AWK" -- "$LANES_FILE"; }
row_cell() { printf '%s\n' "$1" | awk -F'|' -v i="$2" '{print $i}'; }

uuids_in_cell() { grep -oiE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | tr 'A-F' 'a-f' || :; }

session_ids_of_lane() {
  si_row="$(row_of_lane "$1")"
  [ -n "$si_row" ] || return 1
  row_cell "$si_row" 3 | uuids_in_cell
}
session_ids_local_of_lane() {
  sl_row="$(row_of_lane_local "$1")"
  [ -n "$sl_row" ] || return 1
  row_cell "$sl_row" 3 | uuids_in_cell
}
last_session_id_of_lane() { session_ids_of_lane "$1" 2>/dev/null | tail -n1; }
# The handoff path is the row's SIXTH column — awk field 7, because $1 is the
# empty string before the leading pipe. Counting back from NF was wrong for any
# row with a literal `|` inside a cell, and the live register has two: of 45
# rows, 43 split into 9 fields, one into 10 and one into 11, and for the last
# of those NF-2 is the tail of the state cell (` re-cut `) rather than the
# handoff. `lane_workstation` below counts from the left for the same reason.
handoff_of_lane() {
  hl_row="$(row_of_lane "$1")"
  [ -n "$hl_row" ] || return 1
  row_cell "$hl_row" 7 | sed 's/^ *//; s/ *$//'
}

short_ws() { printf '%s' "${1%%.*}" | tr 'A-Z' 'a-z'; }

# Column 3 of the row is `<workstation> / <env> / <user>`. A lane recorded on
# ANOTHER workstation cannot be liveness-checked from here at all: the session
# records are local files. Saying NOT LIVE about it would be a claim this
# machine has no way to make.
lane_workstation() {
  lw_row="$(row_of_lane "$1")"
  [ -n "$lw_row" ] || return 1
  row_cell "$lw_row" 4 | sed 's/^ *//; s/ *$//; s| */.*||' | awk '{print $1}'
}
lane_is_elsewhere() {
  lw="$(lane_workstation "$1" 2>/dev/null || :)"
  [ -n "$lw" ] || return 1
  [ "$(short_ws "$lw")" != "$(short_ws "$WS")" ]
}

# The session id an event line carries: what the caller says it is, else the
# lane's current one (Amendment 6(b): the LAST id in the cell), else unknown.
session_for() {
  if [ -n "${LANES_SESSION:-}" ]; then printf '%s\n' "$LANES_SESSION"; return 0; fi
  sf_id="$(last_session_id_of_lane "$1" 2>/dev/null || :)"
  printf '%s\n' "${sf_id:-unknown}"
}

# ----------------------------------------------------- project.yaml legs
#
# openRepoShape's assembly-root manifest: a top-level `legs:` list of
# `- role: assembly|spec|code` / `repository: owner/repo` / `path:`. Two
# repositories are legs of ONE project when one manifest names them both.
#
# ONLY `legs[].repository` is read, and only as navigation. The manifest says
# of itself that it CONFERS NOTHING — `role:` in particular grants nothing and
# is never read here.
#
# `family.yaml`'s `members:` is deliberately NOT read, though its entries carry
# a `repository:` too. A family is broader than a project — `InkRouter` holds
# `IRRS` and `IRSS`, separate projects with separate lanes — and the ruling
# said legs. Two repos in one family ARE a crossing.
project_legs_file() {
  [ -f "$1" ] || return 1
  awk '
    /^[A-Za-z_][A-Za-z0-9_]*:/ { inlegs = ($0 ~ /^legs:/); next }
    !inlegs { next }
    /^[ \t]*#/ { next }
    /^[ \t]+repository:[ \t]*/ {
      v = $0
      sub(/^[ \t]+repository:[ \t]*/, "", v)
      sub(/[ \t]+$/, "", v)
      gsub(/^"|"$/, "", v)
      gsub(/^'"'"'|'"'"'$/, "", v)
      if (v != "") print v
    }' "$1"
}

# Manifests are looked for where the estate keeps them: one level under
# $PROJECTS_ROOT (`~/projects/MedxEHR/project.yaml`) and two
# (`~/projects/InkRouter/IRRS/project.yaml`, the shape real register traffic
# uses today), plus the lane's own checkout when it names one.
# Every repository spelling, on both sides of the comparison, through the same
# alias table the object keys go through — a manifest that still spells a
# pre-move org (`opensoft/codexFactory` where the key canonicalises to
# `codeXfactory/codexFactory`) is one repository, and comparing the two
# literally reports a crossing that is not one.
canon_repo_list() {
  while IFS= read -r cr_v; do
    [ -n "$cr_v" ] || continue
    cr_c="$(alias_lookup "$cr_v" 2>/dev/null || :)"
    printf '%s\n' "${cr_c:-$cr_v}"
  done
}

same_project() {
  sp_home="$1"; sp_obj="$2"; sp_f=""; sp_legs=""
  SAME_PROJECT_FILE=""
  [ -n "$sp_home" ] && [ -n "$sp_obj" ] || return 1
  sp_c="$(alias_lookup "$sp_home" 2>/dev/null || :)"; sp_home="${sp_c:-$sp_home}"
  sp_c="$(alias_lookup "$sp_obj"  2>/dev/null || :)"; sp_obj="${sp_c:-$sp_obj}"
  [ "$sp_home" = "$sp_obj" ] && return 0
  for sp_f in ${LANES_LANE_DIR:+"$LANES_LANE_DIR/project.yaml"} \
              "$PROJECTS_ROOT"/*/project.yaml \
              "$PROJECTS_ROOT"/*/*/project.yaml; do
    [ -f "$sp_f" ] || continue
    sp_legs="$(project_legs_file "$sp_f" 2>/dev/null | canon_repo_list || :)"
    [ -n "$sp_legs" ] || continue
    printf '%s\n' "$sp_legs" | grep -qx -F -- "$sp_home" || continue
    printf '%s\n' "$sp_legs" | grep -qx -F -- "$sp_obj"  || continue
    SAME_PROJECT_FILE="$sp_f"
    return 0
  done
  return 1
}

# Decision 2, ratified by Brett Heap 2026-09-11 ("yes just warn"): a crossing
# WARNS and proceeds. It never refuses — the estate crosses routinely
# (opsXfactory-3 landed 32 distinct PRs into opensoft/Omnigent-Install, every
# one of them foreign to its home), and a refusal here would be a new gate
# nobody asked for.
cross_repo_warn() {
  cw_obj_repo="$1"; cw_home="$2"; cw_me="$3"; cw_found=0; cw_lane=""; cw_h=""; cw_id=""
  [ -n "$cw_obj_repo" ] || return 0
  if [ -z "$cw_home" ]; then
    note "NOTE: lane $cw_me has no home repo on record, so the cross-repo check did not run (pre-cutover lane: pass --home owner/repo)"
    return 0
  fi
  [ "$cw_obj_repo" = "$cw_home" ] && return 0
  if same_project "$cw_home" "$cw_obj_repo"; then
    note "$cw_obj_repo and $cw_home are legs of one project.yaml — not a crossing (${SAME_PROJECT_FILE:-?})"
    return 0
  fi
  note "WARNING: CROSS-REPO — $cw_obj_repo is not lane $cw_me's home ($cw_home). Proceeding: Amendment 7 warns here, it never refuses."
  while IFS= read -r cw_lane; do
    [ -n "$cw_lane" ] || continue
    [ "$cw_lane" = "$cw_me" ] && continue
    # Both sides through the alias table (R20): home_of_lane resolves its
    # answer, and the object's repository arrived canonical from canon_object,
    # so this comparison is between two canonical spellings. It is still made
    # case-insensitively, because the register spells one repository three ways
    # in a week and only the TABLE's lookup is case-blind, not its output.
    cw_h="$(home_of_lane "$cw_lane" 2>/dev/null || :)"
    [ "$(lc "$cw_h")" = "$(lc "$cw_obj_repo")" ] || continue
    cw_id="$(last_session_id_of_lane "$cw_lane" 2>/dev/null || :)"
    if lane_is_elsewhere "$cw_lane"; then
      note "  lane homed on $cw_obj_repo, on another workstation ($(lane_workstation "$cw_lane")): @$cw_lane — last transcript uuid ${cw_id:-unknown}"
      cw_found=1
    elif live_holder "$cw_lane" >/dev/null 2>&1; then
      note "  LIVE lane homed on $cw_obj_repo: @$cw_lane — last transcript uuid ${cw_id:-unknown} — claude --resume ${cw_id:-<uuid>}"
      cw_found=1
    fi
  done <<EOF
$(known_lanes)
EOF
  [ "$cw_found" = 1 ] || note "  no live lane is homed on $cw_obj_repo"
  return 0
}

# ---------------------------------------------------------------- writing

event_line() {
  el_verb="$1"; el_lane="$2"; el_uuid="$3"; el_utc="$4"; el_obj="$5"; el_ref="${6-}"; el_pay="${7-}"; el_txt="${8-}"
  el_line="$el_verb — lane $el_lane, session $el_uuid@$WS, $el_utc, $el_obj"
  [ -n "$el_ref" ] && [ -n "$el_pay" ] && el_line="$el_line $el_ref $el_pay"
  [ -z "$el_ref" ] && [ -n "$el_pay" ] && el_line="$el_line $el_pay"
  [ -n "$el_txt" ] && el_line="$el_line — $el_txt"
  printf '%s\n' "$el_line"
}

# Rule 6's own rendering of a LANDING / LANDED, for LANES.md — the phrasing
# every other lane already greps for as the merge hold.
rule6_line() {
  r6_verb="$1"; r6_lane="$2"; r6_uuid="$3"; r6_utc="$4"; r6_obj="$5"; r6_pay="${6-}"; r6_n=""
  r6_n="$(object_number "$r6_obj")"
  [ -n "$r6_n" ] || return 1
  r6_line="$r6_verb — lane $r6_lane, session $r6_uuid@$WS, $r6_utc, PR #$r6_n into $(object_repo "$r6_obj") main"
  [ -n "$r6_pay" ] && r6_line="$r6_line → $r6_pay"
  printf '%s\n' "$r6_line"
}

# write_event <lane> <verb> <object> <ref> <payload> <text> <utc> <uuid>
# Appends to the lane's log and commits — and for a LANDING or a LANDED
# appends Rule 6's line to LANES.md in the SAME commit, two pathspecs, so the
# register and the log can never disagree about a merge hold.
write_event() {
  we_lane="$1"; we_verb="$2"; we_obj="$3"; we_ref="$4"; we_pay="$5"; we_txt="$6"; we_utc="$7"; we_uuid="$8"
  # THE WRITER REFUSES A FIELD THAT WOULD MAKE THE LINE UNREADABLE (R21).
  # ` — ` divides a line into its three parts, and the grammar guarantees it
  # occurs AT MOST TWICE — once after the verb, once before the free text — so
  # that one parser reads every line. A payload or a free text carrying a third
  # one breaks that guarantee in a file nothing ever rewrites; so does a
  # newline, which `append_text_line` would notice only AFTER writing it. Both
  # are refused here, before the lock and before anything is created, rather
  # than hoped against.
  case "$we_pay$we_txt" in
    *" — "*) die "an event's payload and free text may not contain ' — ': that separator is what divides a line's verb from its fields and its fields from its free text, and a third one leaves the line ambiguous to its own parser. Use a semicolon or a colon instead: '$we_pay$we_txt'" 2 ;;
  esac
  if [ "${we_pay//[$'\n\r']/}" != "$we_pay" ] || [ "${we_txt//[$'\n\r']/}" != "$we_txt" ]; then
    die "an event's payload and free text are ONE line: a newline in either would append several lines to an append-only log, and the proof that only one was added would fail after the write, not before it" 2
  fi
  # AND IT REFUSES A FREE TEXT THAT BEGINS WITH AN ARROW (R26, Addendum 6).
  # `→` and `←` introduce the PAYLOAD, and the payload is its own argument.
  # Quoted into the free-text slot — `log LANDED <obj> "→ <sha>"`, the shape a
  # reader reaches for because that is how the finished line looks — it is
  # written AFTER the ` — `, where the parser reads it as prose: the event
  # carries no payload, `rule6_line` renders the register's Rule 6 line without
  # `→ <sha>`, and the merge sha is lost in two files that are never rewritten.
  # Nothing legitimate starts a sentence with an arrow, so the trap is closed
  # here rather than left to be noticed afterwards.
  case "$we_txt" in
    '→'*|'←'*)
      we_hint="LANES_LANE=$we_lane lanes-edit.sh log $we_verb $we_obj → <payload>"
      case "$we_verb" in
        RELEASED)                    we_hint="LANES_LANE=$we_lane lanes-edit.sh release $we_obj \"<why>\"  — a release takes a reason, not a payload" ;;
        CLAIMED|TAKEOVER|CLAIM-LOST) we_hint="LANES_LANE=$we_lane lanes-edit.sh claim $we_obj" ;;
      esac
      die "an event's free text may not begin with '→' or '←': those arrows introduce the PAYLOAD, which is its own argument and comes BEFORE the free text. Quoted into the text slot it is written after the ' — ', where no reader and no parser looks for it — a LANDED that way loses its merge sha from both the log and the register's Rule 6 line, in two files nothing rewrites. Write it positionally, e.g. 'lanes-edit.sh log LANDED <object> → <sha>'; for this call: $we_hint" 2 ;;
  esac
  we_line="$(event_line "$we_verb" "$we_lane" "$we_uuid" "$we_utc" "$we_obj" "$we_ref" "$we_pay" "$we_txt")"
  we_paths=("$(log_path_for "$we_lane")")
  we_r6=""
  case "$we_verb" in
    LANDING|LANDED) we_r6="$(rule6_line "$we_verb" "$we_lane" "$we_uuid" "$we_utc" "$we_obj" "$we_pay" 2>/dev/null || :)" ;;
  esac
  [ -n "$we_r6" ] && we_paths+=("$LANES_PATH")
  # R11 — the register is EXEMPT from this first test, because it is captured
  # below rather than refused. Everything ELSE this checkout has dirty is
  # refused HERE: before the lock, before the capture and before anything is
  # created, so that a refusal leaves the checkout exactly as it found it.
  refuse_dirty_checkout "write $we_verb" "${we_paths[@]}" "$LANES_PATH"
  acquire_lock
  ensure_log "$we_lane"
  capture_register_edit "${we_paths[@]}"
  handle_preexisting "${we_paths[@]}"
  # THEN re-test, against the checkout the capture left behind. The capture is
  # not assumed to have worked — handle_preexisting swallows a failed commit by
  # design, it never fails the call — and a register still dirty at this point
  # would send commit_push down Amendment 5(d)'s skip-the-pull branch, which is
  # the branch that disables the rescan deciding a race.
  refuse_dirty_checkout "write $we_verb" "${we_paths[@]}"
  append_text_line "$we_line" "$(log_file_for "$we_lane")"
  if [ -n "$we_r6" ]; then
    append_text_line "$we_r6" "$LANES_FILE"
    note "Rule 6 line also appended to $LANES_FILE (one commit, ${#we_paths[@]} pathspecs)"
  fi
  we_msg="LOG($we_lane@$WS): $we_verb $we_obj"
  [ -n "$PRE_DIRTY_LANES" ] && we_msg="$we_msg + sweeps uncommitted edit to row $PRE_DIRTY_LANES"
  commit_push "$we_msg" "${we_paths[@]}"
  we_rc=$?
  state_events_flush
  rmdir -- "$LOCK" 2>/dev/null && LOCK_HELD=0 || :
  return "$we_rc"
}

# A read fetches first — there is no index, so "current" means "after a fetch".
log_sync() {
  [ "$NO_GIT" = 1 ] && return 0
  [ "${LANES_NO_FETCH:-0}" = 1 ] && { note "LANES_NO_FETCH=1 — not fetching; reading origin/$LANES_BRANCH as the ref already stands here"; return 0; }
  git -C "$LANES_REPO" rev-parse --git-dir >/dev/null 2>&1 || return 0
  remote_has_branch || return 0
  git -C "$LANES_REPO" fetch -q origin "$LANES_BRANCH" 2>/dev/null \
    || note "fetch failed — reading the logs as they stand locally"
  return 0
}

# ------------------------------------------------------------------- who
#
# Exit 0 found, 8 no record.

print_holder_detail() {
  ph_lane="$1"; ph_obj="$2"; ph_rc=0
  ph_home="$(home_of_lane "$ph_lane" 2>/dev/null || :)"
  printf '  home     %s\n' "${ph_home:-unknown (pre-cutover lane: no STARTED line)}"
  ph_rowid="$(last_session_id_of_lane "$ph_lane" 2>/dev/null || :)"
  if lane_is_elsewhere "$ph_lane"; then
    # Session records are local files. This machine cannot see another
    # workstation's, so it must not say NOT LIVE about one.
    printf '  holder   lane %s — UNKNOWN (records are local to %s; ask @%s or read its handoff)\n' \
      "$ph_lane" "$(lane_workstation "$ph_lane")" "$ph_lane"
  else
    # 0 / 8 / anything else, and never two of them conflated (R22): a read this
    # workstation could not perform is UNKNOWN, exactly as another workstation's
    # records are. NOT LIVE is a claim, and it is the claim that sends a reader
    # to `claim --force` against a lane that is running.
    ph_h="$(live_holder "$ph_lane" 2>/dev/null)"; ph_rc=$?
    case "$ph_rc" in
      0)
        IFS="$US" read -r ph_hid ph_target ph_hname ph_hpid <<EOF
$ph_h
EOF
        printf '  holder   lane %s — LIVE (session %s, pid %s, tmux %s)\n' "$ph_lane" "$ph_hid" "$ph_hpid" "$ph_target" ;;
      8)
        printf '  holder   lane %s — NOT LIVE (parked: every session its row records has ended)\n' "$ph_lane" ;;
      *)
        printf '  holder   lane %s — UNKNOWN (this workstation'"'"'s session records could not be read; ask @%s or read its handoff)\n' "$ph_lane" "$ph_lane" ;;
    esac
  fi
  printf '  address  @%s · claude --resume %s\n' "$ph_lane" "${ph_rowid:-<no transcript uuid in the row>}"
  ph_ho="$(handoff_of_lane "$ph_lane" 2>/dev/null || :)"
  [ -n "$ph_ho" ] && printf '  handoff  %s\n' "$ph_ho"
  printf '  log      %s\n' "$(log_path_for "$ph_lane")"
  ph_objrepo="$(object_repo "$ph_obj")"
  if [ -n "$ph_home" ] && [ -n "$ph_objrepo" ] && [ "$ph_objrepo" != "$ph_home" ] && ! same_project "$ph_home" "$ph_objrepo"; then
    printf '  CROSS-REPO  %s is not lane %s'"'"'s home (%s)\n' "$ph_objrepo" "$ph_lane" "$ph_home"
  fi
}

who_object() {
  wo_obj="$1"
  wo_states="$(state_events | lane_states_on "$wo_obj")"
  if [ -z "$wo_states" ]; then
    printf 'no record of %s in any lane log\n' "$wo_obj"
    printf '  (a lane with no log file is pre-cutover: see its row'"'"'s state cell in LANES.md)\n'
    return 8
  fi
  printf 'object   %s\n' "$wo_obj"
  wo_held=0
  while IFS="$US" read -r s_utc s_lane s_verb s_uuid s_ws s_o s_ref s_pay s_txt s_file s_line; do
    [ -n "${s_verb:-}" ] || continue
    wo_sup="$(superseded_by "$wo_obj" "$s_lane" "$s_verb")"
    if [ -n "$wo_sup" ]; then
      printf 'super.   lane %-22s %-9s %s (%s ago) — superseded by TAKEOVER (lane:%s) at %s\n' \
        "$s_lane" "$s_verb" "$s_utc" "$(age_of "$s_utc")" "${wo_sup%@*}" "${wo_sup#*@}"
      printf '         this lane no longer holds it; it closes its own line with: lanes-edit.sh release %s "taken over by %s"\n' "$wo_obj" "${wo_sup%@*}"
    elif is_open_verb "$s_verb"; then
      printf 'HOLDS    lane %-22s %-9s %s (%s ago)%s\n' "$s_lane" "$s_verb" "$s_utc" "$(age_of "$s_utc")" "${s_pay:+ ${s_ref:-} $s_pay}"
      wo_held=1
    else
      printf 'closed   lane %-22s %-9s %s (%s ago)%s\n' "$s_lane" "$s_verb" "$s_utc" "$(age_of "$s_utc")" "${s_pay:+ ${s_ref:-} $s_pay}"
    fi
    # A line written with --no-github is not yet a Rule 1 claim: the comment a
    # person outside this estate reads does not exist.
    case "${s_txt:-}" in
      no-github|'no-github;'*) printf '         local only — no GitHub claim comment\n' ;;
      "") : ;;
      *) printf '         %s\n' "$s_txt" ;;
    esac
  done <<EOF
$wo_states
EOF
  if [ "$wo_held" = 0 ]; then
    printf 'state    FREE — no lane'"'"'s last line on it is open\n'
    return 0
  fi
  printf 'state    HELD\n'
  while IFS="$US" read -r s_utc s_lane s_verb s_uuid s_ws s_o s_ref s_pay s_txt s_file s_line; do
    [ -n "${s_verb:-}" ] || continue
    is_open_verb "$s_verb" || continue
    [ -z "$(superseded_by "$wo_obj" "$s_lane" "$s_verb")" ] || continue
    printf 'holder   lane %s (%s, %s)\n' "$s_lane" "$s_verb" "$s_utc"
    # NOT STALE, AND IT SAYS WHICH OF THE THREE REASONS. `stale no — 5h 00m
    # old, threshold 4h` is two true halves that read as a contradiction: both
    # of the other discharges (Rule 1's "a claim followed by a PR is not
    # abandoned", and Rule 6 governing a PR) leave a claim past the threshold
    # and NOT stale, and neither was named.
    if [ "$s_verb" = CLAIMED ] && claim_is_stale "$s_lane" "$wo_obj" "$s_utc" "$s_file" "$s_line"; then
      printf '  stale    YES — claimed %s ago with no OPENED naming it, past the %sh threshold; a takeover is allowed (claim --force)\n' "$(age_of "$s_utc")" "$STALE_HOURS"
    elif [ "$s_verb" = CLAIMED ]; then
      if ! older_than_threshold "$s_utc"; then
        printf '  stale    no — %s old, threshold %sh\n' "$(age_of "$s_utc")" "$STALE_HOURS"
      elif object_is_pr "$wo_obj"; then
        printf '  stale    no — %s old, past the %sh threshold, but this object is a PR: Rule 6'"'"'s thirty minutes govern it, not Rule 1'"'"'s hours\n' "$(age_of "$s_utc")" "$STALE_HOURS"
      else
        printf '  stale    no — %s old, past the %sh threshold, but lane %s has since written an OPENED naming it (Rule 1: a claim followed by a PR is not abandoned)\n' "$(age_of "$s_utc")" "$STALE_HOURS" "$s_lane"
      fi
    fi
    print_holder_detail "$s_lane" "$wo_obj"
  done <<EOF
$wo_states
EOF
  return 0
}

who_lane() {
  wl_lane="$1"
  if ! lane_log_exists "$wl_lane"; then
    printf 'no log for %s; see its row'"'"'s state cell\n' "$wl_lane"
    return 8
  fi
  wl_n=0
  # FIVE fields, because `lane_objects` prints five. Read into four, the fifth —
  # the superseded-by cell — arrived glued to the payload and printed where a
  # payload goes: `CLAIMED opensoft/repoX#40 2026-… bbb-1@2026-…`.
  while IFS="$US" read -r wl_utc wl_verb wl_obj wl_ref wl_sup; do
    [ -n "${wl_verb:-}" ] || continue
    is_open_verb "$wl_verb" || continue
    printf '%-9s %s  %s (%s ago)%s%s\n' "$wl_verb" "$wl_obj" "$wl_utc" "$(age_of "$wl_utc")" \
      "${wl_ref:+ $wl_ref}" "${wl_sup:+  (taken over by lane:${wl_sup%@*} at ${wl_sup#*@} — release it to close this line)}"
    wl_n=$((wl_n + 1))
  done <<EOF
$(lane_objects "$wl_lane")
EOF
  # An empty answer is an answer: 8 stays reserved for "there is no log".
  if [ "$wl_n" = 0 ]; then printf 'none open — lane %s holds nothing open\n' "$wl_lane"; return 0; fi
  return 0
}

# THE MERGE HOLD IS DECIDED FROM LANES.md, not from the logs. Rule 6's
# LANDING / LANDED lines are written for every lane, before this amendment and
# after it, and every lane already reads them there. The logs are secondary.
#
# Landings are counted as distinct (lane, repository, PR) TRIPLES, never as raw
# LANDING lines: a retry re-posts LANDING for the same PR, and the register has
# 571 such lines for far fewer landings.
#
# A LANDED CLOSES THE LANDING IT ANSWERS, PAIRED BY (lane, PR) IN FILE ORDER
# (R17). Most of the register’s LANDED lines carry no `into <repo> main` clause
# at all — 284 of 308 on the day this was measured — so keying a LANDED on the
# repository it names keyed 284 of them on the empty string, where they could
# never close the repository-qualified LANDING they belonged to: `who --landing`
# reported 201 phantom merge holds across five repositories, every one of them
# landed long ago, on a register whose genuinely open count was one. So the
# PAIRING is by (lane, PR) — the LANDED closes the most recent LANDING of that
# lane and PR that is still unmatched, and the pair’s repository is the
# LANDING’s — while the RESULT still keys on (lane, repository, PR), which is
# what keeps a LANDED on one repository from closing a LANDING on another.
# AND A LANDED THAT NAMES A REPOSITORY PREFERS A LANDING ON THAT REPOSITORY
# (R24, Addendum 6). Only a LANDED with NO `into <repo> main` clause takes the
# most recent unmatched LANDING regardless — it has said nothing about where it
# landed, so the LANDING is the only thing that can say. One that DOES name a
# repository takes the most recent unmatched LANDING naming the same one, and
# is reported as an `unpaired LANDED` — closing nothing — only when there is no
# such LANDING at all. Without the preference, a lane with two LANDINGs open on
# ONE PR number in two repositories that lands the EARLIER one, naming its
# repository, was unpaired and both holds stayed open until the second landed.
# The answer is identical everywhere else, including the (lane, repository, PR)
# result key: a LANDED on one repository still closes no LANDING on another.
#
# The repository is lower-cased IN THE KEY ONLY: the register spells one
# repository four ways in a week, and a LANDED spelled `OpsxFactory` must still
# close a LANDING spelled `opsXfactory`.
#
# AND BOTH SIDES GO THROUGH `lanes/repos.tsv` FIRST (R29, Addendum 7). Case is
# only half of it: the register writes `OpsxFactory` and `opensoft/OpsxFactory`
# for ONE repository — 23 Rule 6 lines against 70 at `8f9c04d` — and
# `codexFactory`, `codeXfactory/codexFactory` and `opensoft/codexFactory` for
# another. Compared literally, a LANDED spelled one way does not close the
# LANDING spelled the other: it reads as an `unpaired LANDED`, the hold stays
# open, and over-reporting a merge hold is the direction that stalls other
# lanes' merges. So every `into <repo> main` is resolved AS IT IS PARSED, which
# makes the pairing, R24's preference and the (lane, repository, PR) result key
# agree by construction — the key's repository is the canonical spelling, and
# an alias the table does not know keeps its own, case-blind like every other.
#
# WHAT THAT IS WORTH TODAY, measured read-only over `origin/main` at `6fa966b`:
# the VERDICT does not move — 1 open LANDING (lane browser-ui-repair's PR #401,
# genuinely in flight) and 0 unpaired LANDED, before this change and after it.
# No (lane, PR) pair in the register mixes its spellings YET, so this is a
# guard and not a repair, and it is worth saying so rather than claiming a hold
# it did not clear. What it does move there is the KEY: 17 result-key spellings
# collapse to the 11 repositories they name, and two LANDINGs a retry spelled
# two ways are one hold instead of two.
#
# The table is handed in as `aliases`, one `<lowercased alias>\037<owner/repo>`
# per line, because awk cannot read `repos.tsv` for itself here: this program's
# stdin is the register.
rule6_aliases() {
  [ -f "$LANES_REPOS_TSV" ] || return 0
  awk -F'\t' '
    /^[ \t]*#/ { next }
    NF >= 2 {
      a = $1; b = $2
      gsub(/^[ \t]+|[ \t]+$/, "", a); gsub(/^[ \t]+|[ \t]+$/, "", b)
      if (a != "" && b != "") printf "%s\037%s\n", tolower(a), b
    }' "$LANES_REPOS_TSV"
}

RULE6_AWK='
function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
function canon(r,   l) { l = tolower(r); return (l in A) ? A[l] : r }
BEGIN {
  na = split(aliases, ar, "\n")
  for (ai = 1; ai <= na; ai++) { ap = index(ar[ai], "\037")
    if (ap > 1) A[substr(ar[ai], 1, ap - 1)] = substr(ar[ai], ap + 1) }
}
/^(LANDING|LANDED) — / {
  line = $0
  verb = substr(line, 1, index(line, " ") - 1)
  lane = ""; pr = ""; repo = ""; utc = ""
  if (match(line, /lane [A-Za-z0-9._-]+/))            lane = substr(line, RSTART + 5, RLENGTH - 5)
  if (match(line, /PR #[0-9]+/))                      pr   = substr(line, RSTART + 4, RLENGTH - 4)
  if (match(line, /into [A-Za-z0-9\/._-]+ main/))     repo = canon(substr(line, RSTART + 5, RLENGTH - 10))
  if (match(line, /[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9](:[0-9][0-9])?Z/)) utc = substr(line, RSTART, RLENGTH)
  if (lane == "" || pr == "") next
  g = lane "\037" pr
  if (verb == "LANDING") {
    k = g "\037" tolower(repo)
    if (!(k in ST)) { gk[g, ++gn[g]] = k }
    ST[k] = "LANDING"; U[k] = utc; L[k] = lane; P[k] = pr; R[k] = repo; O[k] = NR
    next
  }
  best = ""; bord = -1; bestr = ""; bordr = -1
  for (i = 1; i <= gn[g]; i++) { kk = gk[g, i]
    if (ST[kk] != "LANDING") continue
    if (O[kk] > bord) { bord = O[kk]; best = kk }
    if (repo != "" && tolower(repo) == tolower(R[kk]) && O[kk] > bordr) { bordr = O[kk]; bestr = kk } }
  if (bestr != "") best = bestr        # R24: a LANDED that NAMES a repository
  if (best == "") next
  if (repo != "" && tolower(repo) != tolower(R[best])) {
    printf "UNPAIRED%c%s%c%s%c%s%c%s%c%s\n", 31, lane, 31, pr, 31, utc, 31, repo, 31, R[best]
    next
  }
  ST[best] = "LANDED"; U[best] = utc; O[best] = NR
}
END { for (k in ST) printf "%s%c%s%c%s%c%s%c%s%c\n", ST[k], 31, L[k], 31, P[k], 31, U[k], 31, R[k], 31 }'

# Rule 6's window, in minutes. A LANDING past it with no LANDED is still a
# line somebody wrote and is still listed — but it is marked, because reporting
# a 253-day-old LANDING as a live merge hold with nothing to say it is not one
# is how the estate ends up holding its merges for a lane that stopped.
LANDING_MINUTES="${LANES_LANDING_MINUTES:-30}"

# The lane logs are SECONDARY here and are reported after the register: every
# lane writes its Rule 6 line into LANES.md, pre- and post-cutover alike, and
# that is what decides the hold. A lane's own LANDING/LANDED is evidence
# beside it, never instead of it.
who_landing_logs() {
  wll_repo="$1"; wll_rows=""
  wll_rows="$(state_events | awk -v sep="$US" -v repo="$wll_repo" '
    function pos(pf, pn) { return pf "\034" sprintf("%09d", pn) }
    BEGIN { FS = sep }
    $6 ~ /^lane:/ { next }
    {
      o = $6; r = o; sub(/#.*$/, "", r); sub(/:openspec\/changes\/.*$/, "", r)
      if (tolower(r) != tolower(repo)) next
      # The LAST line this lane wrote on the object, in FILE ORDER (R14).
      # A LANDED is often written in the same second as the LANDING it closes,
      # and on a workstation whose clock steps back it is stamped before it.
      k = $2 sep o
      p = pos($10, $11)
      if (!(k in P) || p >= P[k]) { P[k] = p; u[k] = $1; V[k] = $3; L[k] = $2; O[k] = o }
    }
    END { for (k in P) if (V[k] == "LANDING" || V[k] == "LANDED")
            printf "%s%c%s%c%s%c%s\n", V[k], 31, L[k], 31, O[k], 31, u[k] }' \
    | LC_ALL=C sort -t"$US" -k3,3 -k2,2)"
  [ -n "$wll_rows" ] || return 0
  printf 'from lane logs (secondary):\n'
  while IFS="$US" read -r wl_verb wl_lane wl_obj wl_utc; do
    [ -n "${wl_verb:-}" ] || continue
    printf '  %-8s %s  lane %s, %s (%s ago)\n' "$wl_verb" "$wl_obj" "$wl_lane" "$wl_utc" "$(age_of "$wl_utc")"
  done <<EOF
$wll_rows
EOF
}

who_landing() {
  wd_repo="$1"; wd_n=0; wd_rows=""
  wd_rows="$(register_text | awk -v aliases="$(rule6_aliases)" "$RULE6_AWK")"
  while IFS="$US" read -r wd_verb wd_lane wd_pr wd_utc wd_r wd_other; do
    [ "${wd_verb:-}" = LANDING ] || continue
    wd_c="$(alias_lookup "${wd_r:-}" 2>/dev/null || :)"; wd_c="${wd_c:-$wd_r}"
    [ "$(lc "$wd_c")" = "$(lc "$wd_repo")" ] || continue
    wd_stale=""
    older_than_minutes "$wd_utc" "$LANDING_MINUTES" && wd_stale="  STALE (Rule 6: >${LANDING_MINUTES} min)"
    printf 'LANDING  %s#%s  lane %s, %s (%s ago)%s\n' "$wd_repo" "$wd_pr" "$wd_lane" "$wd_utc" "$(age_of "$wd_utc")" "$wd_stale"
    wd_n=$((wd_n + 1))
  done <<EOF
$wd_rows
EOF
  # "No hold on this repository" is an ANSWER, and a script that gates on
  # `if who --landing <repo>` must read it as one. 8 is reserved for absence.
  [ "$wd_n" = 0 ] && printf 'none open — no LANDING on %s is still open (read from LANES.md'"'"'s Rule 6 lines)\n' "$wd_repo"
  # A LANDED that names THIS repository while the LANDING it would close is on
  # another closes nothing (R17), and is said so rather than dropped: an
  # append-only register is never rewritten, so a line no tool mentions again is
  # a line nobody will ever reconcile.
  while IFS="$US" read -r wd_verb wd_lane wd_pr wd_utc wd_r wd_other; do
    [ "${wd_verb:-}" = UNPAIRED ] || continue
    wd_c="$(alias_lookup "${wd_r:-}" 2>/dev/null || :)"; wd_c="${wd_c:-$wd_r}"
    [ "$(lc "$wd_c")" = "$(lc "$wd_repo")" ] || continue
    printf 'unpaired LANDED  %s#%s  lane %s, %s — the open LANDING for (lane %s, PR #%s) is on %s, so this closes nothing\n' \
      "$wd_repo" "$wd_pr" "$wd_lane" "$wd_utc" "$wd_lane" "$wd_pr" "${wd_other:-an unnamed repository}"
  done <<EOF
$wd_rows
EOF
  who_landing_logs "$wd_repo"
  return 0
}

# ----------------------------------------------------------------- GitHub
#
# Rule 1 is one act: the three reads, the local line, and the comment that
# another person reads. The LOG is authoritative for a claim made through
# `claim` — a log line IS a live claim for Rule 1 purposes — and the GitHub
# comment is the copy that a person outside this estate can see.
# --no-github skips every call here, which is what the tests and an offline
# lane run with.

gh_reads() {
  gr_obj="$1"; gr_repo="$(object_repo "$gr_obj")"; gr_n="$(object_number "$gr_obj")"; gr_slug="$(object_slug "$gr_obj")"
  if [ "$NO_GITHUB" = 1 ]; then
    printf '1. existing claims on the object: not read (--no-github)\n'
    printf '2. gh pr list --state all --search: not read (--no-github)\n'
    printf '3. git ls-remote --heads: not read (--no-github)\n'
    return 0
  fi
  command -v gh >/dev/null 2>&1 || { note "gh is not on PATH — rerun with --no-github, or install it"; return 1; }
  printf '1. existing `CLAIMED —` comments on %s:\n' "$gr_obj"
  if [ -n "$gr_n" ]; then
    gr_c="$( { gh issue view "$gr_n" --repo "$gr_repo" --comments 2>/dev/null || gh pr view "$gr_n" --repo "$gr_repo" --comments 2>/dev/null; } | grep -n 'CLAIMED —\|TAKEOVER —\|RELEASED —' || : )"
  else
    gr_c=""
  fi
  printf '%s\n' "${gr_c:-   none}"
  printf '2. `gh pr list --repo %s --state all --search "%s"`:\n' "$gr_repo" "$gr_slug"
  gr_p="$(gh pr list --repo "$gr_repo" --state all --search "$gr_slug" --limit 20 2>/dev/null || :)"
  printf '%s\n' "${gr_p:-   none}"
  printf '3. `git ls-remote --heads git@github.com:%s` matching `%s`:\n' "$gr_repo" "$gr_slug"
  gr_b="$(git ls-remote --heads "git@github.com:$gr_repo.git" 2>/dev/null | grep -i -- "$gr_slug" || :)"
  printf '%s\n' "${gr_b:-   none}"
  return 0
}

gh_comment() {
  gc_obj="$1"; gc_body="$2"; gc_repo="$(object_repo "$gc_obj")"; gc_n="$(object_number "$gc_obj")"
  [ "$NO_GITHUB" = 1 ] && return 1
  [ -n "$gc_n" ] || { note "$gc_obj is a change directory, not an issue or a PR — no GitHub comment to post"; return 1; }
  command -v gh >/dev/null 2>&1 || return 1
  gc_url="$(printf '%s' "$gc_body" | gh issue comment "$gc_n" --repo "$gc_repo" --body-file - 2>/dev/null \
         || printf '%s' "$gc_body" | gh pr comment "$gc_n" --repo "$gc_repo" --body-file - 2>/dev/null || :)"
  gc_url="$(printf '%s\n' "$gc_url" | grep -o 'https://[^ ]*' | tail -n1 || :)"
  [ -n "$gc_url" ] || return 1
  printf '%s\n' "$gc_url"
}

# The hook `commit_push` calls after every `pull --rebase`, before it pushes.
# If another lane's CLAIMED or TAKEOVER on this object is on the rebased
# history, THEIRS LANDED FIRST and this claim has lost. Git's push
# serialization is the arbiter across workstations; the local `mkdir` mutex
# only serializes one workstation, and never decides a race.
# Of the rival lanes in <holders>, the one whose line on <object> LANDED
# first. Landing order is the arbiter and a timestamp is not: two
# workstations' clocks are not a shared order, which is the whole reason this
# amendment decides the race by which CLAIMED reaches `main` first. The
# pickaxe lists the commits that added a line naming the object, oldest first;
# the first of them that touched a rival's log names the winner.
first_landed_of() {   # <object> <holder rows>
  fl_obj="$1"; fl_holders="$2"
  fl_first="$(printf '%s\n' "$fl_holders" | head -n1 | cut -d"$US" -f1)"
  [ "$(printf '%s\n' "$fl_holders" | grep -c .)" -gt 1 ] || { printf '%s\n' "$fl_first"; return 0; }
  have_remote_ref || { printf '%s\n' "$fl_first"; return 0; }
  while IFS= read -r fl_sha; do
    [ -n "$fl_sha" ] || continue
    while IFS= read -r fl_f; do
      [ -n "$fl_f" ] || continue
      fl_lane="${fl_f##*/}"; fl_lane="${fl_lane%.md}"
      if printf '%s\n' "$fl_holders" | grep -q "^$fl_lane$US"; then printf '%s\n' "$fl_lane"; return 0; fi
    done <<EOF
$(git -C "$LANES_REPO" show --name-only --format= "$fl_sha" -- "$LANES_LOG_PREFIX" 2>/dev/null)
EOF
  done <<EOF
$(git -C "$LANES_REPO" log --reverse --format=%H -S"$fl_obj" "origin/$LANES_BRANCH" -- "$LANES_LOG_PREFIX" 2>/dev/null)
EOF
  printf '%s\n' "$fl_first"
}

claim_rescan_hook() {
  CLAIM_WINNER=""
  # The pull has just moved `origin/<branch>`, and OUR commit is not on it —
  # so everything this read can see landed before ours, which is the whole
  # test. Flush the cache first: the ref moved a moment ago.
  state_events_flush
  crh="$(state_events | lane_states_on "$CLAIM_OBJ" | holders_of "$CLAIM_OBJ" \
         | grep -v "^$CLAIM_LANE$US" | { [ -n "$CLAIM_SKIP" ] && grep -v "^$CLAIM_SKIP$US" || cat; } || :)"
  [ -n "$crh" ] || return 0
  CLAIM_WINNER="$(first_landed_of "$CLAIM_OBJ" "$crh")"
  IFS="$US" read -r crh_lane crh_verb crh_utc crh_rest <<EOF
$(printf '%s\n' "$crh" | grep "^$CLAIM_WINNER$US" | head -n1)
EOF
  note "another lane's claim landed on main before this one: @$CLAIM_WINNER ($crh_verb, $crh_utc)"
  return 7
}

# The URL of the stale claim a TAKEOVER supersedes — Rule 1's takeover comment
# must name it. Read from GitHub, because that is where the comment is.
gh_stale_claim_url() {
  gs_obj="$1"; gs_lane="$2"; gs_repo="$(object_repo "$gs_obj")"; gs_n="$(object_number "$gs_obj")"
  [ "$NO_GITHUB" = 1 ] && return 1
  [ -n "$gs_n" ] || return 1
  command -v gh >/dev/null 2>&1 || return 1
  gh issue view "$gs_n" --repo "$gs_repo" --json comments \
     -q '.comments[] | select(.body | test("CLAIMED — lane '"$gs_lane"'")) | .url' 2>/dev/null | tail -n1
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
    lane_tag="${LANES_LANE:-}"
    if [ -z "$lane_tag" ]; then
      cand="$(lane_from_text "$text")"
      if [ -n "$cand" ]; then
        if row_line "$cand" >/dev/null 2>&1; then
          lane_tag="$cand"
        else
          lane_tag="$(row_lane_ci "$cand")"
        fi
      fi
    fi
    acquire_lock; handle_preexisting
    append_text_line "$text"
    msg="LANES(${lane_tag:-unknown}@$WS): append line — $(printf '%s' "$text" | cut -c1-72)"
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
    if [ "$NO_GIT" != 1 ] && ! git -C "$LANES_REPO" diff --quiet -- "${CP_PATHS[@]}" 2>/dev/null; then
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

  log)
    lane="${LANES_LANE:-}"
    [ -n "$lane" ] || die "log needs the lane: LANES_LANE=<lane> lanes-edit.sh log <VERB> <object> …" 2
    check_lane_name "$lane"
    verb=""; obj_raw=""; ref=""; payload=""; text=""; home_override=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --no-github) NO_GITHUB=1; shift ;;
        --home)      home_override="${2-}"; [ -n "$home_override" ] || die "--home needs owner/repo" 2; shift 2 ;;
        --home=*)    home_override="${1#--home=}"; shift ;;
        --text)      text="${2-}"; shift 2 ;;
        --text=*)    text="${1#--text=}"; shift ;;
        --)          shift ;;
        '→'|'->')    ref="→"; payload="${2-}"; [ -n "$payload" ] || die "'$1' needs a payload after it" 2; shift 2 ;;
        '←'|'<-')    ref="←"; payload="${2-}"; [ -n "$payload" ] || die "'$1' needs a payload after it" 2; shift 2 ;;
        -*)          die "unknown option '$1' for log" 2 ;;
        *)
          if   [ -z "$verb" ];    then verb="$1"
          elif [ -z "$obj_raw" ]; then obj_raw="$1"
          elif [ -z "$text" ];    then text="$1"
          else die "log takes <VERB> <object> [→|← <payload>] [\"<free text>\"] — '$1' is one argument too many" 2
          fi
          shift ;;
      esac
    done
    [ -n "$verb" ] && [ -n "$obj_raw" ] || die "usage: log <VERB> <object> [→|← <payload>] [\"<free text>\"]   ($VERB_LIST)" 2
    valid_verb "$verb" || die "'$verb' is not one of the Amendment 7 verbs ($VERB_LIST)" 2
    # The four verbs that have a subcommand of their own are NOT written by
    # hand. `log CLAIMED` skipped the pre-check, the race and the rescan and
    # `who` reported the result identically to a real claim; `log TAKEOVER`
    # skipped the staleness test that is the only thing making a takeover
    # legitimate. Refusing them here costs nothing that is actually needed.
    case "$verb" in
      CLAIMED)
        die "a CLAIMED is not written by hand: it is Rule 1's act, and 'log' skips the pre-check, the race and the rescan. Use: LANES_LANE=$lane lanes-edit.sh claim $obj_raw" 2 ;;
      TAKEOVER)
        die "a TAKEOVER is not written by hand: it is only legitimate against a claim that is STALE, and that is the test 'log' does not make. Use: LANES_LANE=$lane lanes-edit.sh claim $obj_raw --force" 2 ;;
      RELEASED)
        die "a RELEASED is not written by hand: 'release' also posts the Rule 1 comment. Use: LANES_LANE=$lane lanes-edit.sh release $obj_raw \"<why>\"" 2 ;;
      CLAIM-LOST)
        die "a CLAIM-LOST is written by 'claim' when it loses the race for an object, and by nothing else — there is no hand-written form of losing a race" 2 ;;
    esac
    # R30 — THE FETCH COMES FIRST. `log` had no `log_sync` of its own at all:
    # it read the STARTED line that REFUSES `--home` out of an `origin/<branch>`
    # nothing here had moved, and the pull inside `commit_push` comes far too
    # late to be that read.
    log_sync
    home="$(resolve_home "$lane" "$home_override")" || exit $?
    obj="$(canon_object "$obj_raw" "$home")" || exit 2
    if is_lane_verb "$verb"; then
      is_lane_object "$obj" || die "'$verb' is a lane verb: its object is lane:<name>, not $obj" 2
    else
      ! is_lane_object "$obj" || die "'$verb' is an object verb: lane:<name> is not one of its objects" 2
    fi
    write_event "$lane" "$verb" "$obj" "$ref" "$payload" "$text" "$(utc_now)" "$(session_for "$lane")"
    ;;

  claim)
    lane="${LANES_LANE:-}"
    [ -n "$lane" ] || die "claim needs the lane: LANES_LANE=<lane> lanes-edit.sh claim <object>" 2
    check_lane_name "$lane"
    obj_raw=""; force=0; home_override=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --force)     force=1; shift ;;
        --no-github) NO_GITHUB=1; shift ;;
        --home)      home_override="${2-}"; [ -n "$home_override" ] || die "--home needs owner/repo" 2; shift 2 ;;
        --home=*)    home_override="${1#--home=}"; shift ;;
        --)          shift ;;
        -*)          die "unknown option '$1' for claim" 2 ;;
        *)           [ -z "$obj_raw" ] || die "claim takes exactly one object" 2; obj_raw="$1"; shift ;;
      esac
    done
    [ -n "$obj_raw" ] || die "usage: claim <object> [--force] [--no-github] [--home owner/repo]" 2

    # THE RACE IS DECIDED BY WHICH CLAIM LANDS ON main FIRST, and a rebase is
    # what makes that decidable. Amendment 5(d) SKIPS the rebase when a peer
    # has left uncommitted changes to other files in this shared checkout — a
    # sensible default for a row edit, and unacceptable for a claim, which
    # would then race unprotected. Refuse, and name the files — BEFORE the
    # reads and before anything is written, and against exactly the pathspec
    # this claim will write (the lane's log; a CLAIMED is not a LANDING).
    # The register is exempt HERE and only here: write_event captures a peer's
    # uncommitted `lanes/LANES.md` as its own commit and re-tests the checkout
    # afterwards (R11), so a claim is not refused for the one file this
    # checkout is dirty in most of the day.
    refuse_dirty_checkout claim "$(log_path_for "$lane")" "$LANES_PATH"

    # 1. FETCH FIRST OF ALL — then resolve `--home` against the lane's STARTED
    #    line (R30), canonicalise the object, and pre-check against what has
    #    actually LANDED on main. Never against a working tree, which can be
    #    anything, and never against a log this checkout has not pulled: a home
    #    a peer recorded is on `origin/<branch>` and nowhere else here.
    log_sync
    home="$(resolve_home "$lane" "$home_override")" || exit $?
    obj="$(canon_object "$obj_raw" "$home")" || exit 2
    ! is_lane_object "$obj" || die "a lane is not a claimable object" 2
    takeover_payload=""; takeover_note=""; takeover_from=""
    held="$(state_events | lane_states_on "$obj" | holders_of "$obj" | grep -v "^$lane$US" || :)"
    if [ -n "$held" ]; then
      who_object "$obj" || :
      IFS="$US" read -r h_lane h_verb h_utc h_file h_line <<EOF
$(printf '%s\n' "$held" | head -n1)
EOF
      if [ "$force" = 0 ]; then
        die "lane $h_lane holds $obj ($h_verb, $h_utc). Rule 1: the lane stops and reports; it does not author a successor. If that claim is stale (CLAIMED on an issue, older than ${STALE_HOURS}h with no OPENED naming it), take it over with --force." 2
      fi
      if [ "$(printf '%s\n' "$held" | grep -c .)" != 1 ]; then
        die "--force takes over ONE stale claim, and $obj is held by $(printf '%s\n' "$held" | grep -c .) lanes" 2
      fi
      if [ "$h_verb" != CLAIMED ]; then
        die "--force takes over a stale CLAIMED and nothing else: $obj is $h_verb by lane $h_lane. An open OPENED, LANDING or WITHDRAWN is not a stale claim." 2
      fi
      if ! claim_is_stale "$h_lane" "$obj" "$h_utc" "$h_file" "$h_line"; then
        die "--force refused: lane $h_lane's claim on $obj is $(age_of "$h_utc") old (threshold ${STALE_HOURS}h), or it is a PR, or that lane has since OPENED a PR naming it. Rule 1 makes a claim takeable only when it is stale." 2
      fi
      takeover_from="$h_lane"
      takeover_note="stale claim by lane $h_lane, posted $h_utc, no PR after ${STALE_HOURS}h"
      if [ "$NO_GITHUB" = 1 ]; then
        takeover_payload="lane:$h_lane"
      else
        takeover_payload="$(gh_stale_claim_url "$obj" "$h_lane")"
        [ -n "$takeover_payload" ] || takeover_payload="lane:$h_lane"
      fi
    fi

    # 2. Rule 1's three reads, printed.
    reads="$(gh_reads "$obj")" || exit 1
    printf '%s\n' "$reads"

    # 3. decision 2 — a crossing warns and proceeds.
    cross_repo_warn "$(object_repo "$obj")" "$home" "$lane"

    # 4. append, commit, push. CP_AFTER_REBASE runs on every rebase inside the
    #    push loop: if another lane's claim is on the rebased history, theirs
    #    landed first and this one has lost.
    uuid="$(session_for "$lane")"
    utc="$(utc_now)"
    CLAIM_OBJ="$obj"; CLAIM_LANE="$lane"; CLAIM_SKIP="$takeover_from"
    CP_AFTER_REBASE=claim_rescan_hook
    # A line written with --no-github is NOT a Rule 1 claim until its GitHub
    # comment exists, and it says so on its face rather than in a habit.
    ng=""; [ "$NO_GITHUB" = 1 ] && ng="no-github"
    if [ -n "$takeover_from" ]; then
      write_event "$lane" TAKEOVER "$obj" "←" "$takeover_payload" "${ng:+$ng; }$takeover_note" "$utc" "$uuid"
    else
      write_event "$lane" CLAIMED "$obj" "" "" "$ng" "$utc" "$uuid"
    fi
    wrc=$?
    CP_AFTER_REBASE=""

    # 5. lost: Rule 1 says the lane STOPS AND REPORTS. The claim is abandoned,
    #    never queued — Rule 7's queueing is for substrates, which this
    #    amendment does not touch.
    if [ "$wrc" = 7 ]; then
      note "CLAIM LOST — lane $CLAIM_WINNER's claim on $obj landed on main first. Rule 1: stop and report; do not author a successor."
      write_event "$lane" CLAIM-LOST "$obj" "→" "lane:$CLAIM_WINNER" "abandoned: $CLAIM_WINNER landed its claim first" "$(utc_now)" "$uuid"
      who_object "$obj" || :
      exit 7
    fi
    [ "$wrc" = 0 ] || exit "$wrc"

    # 6. the comment, AFTER the push, citing the commit that carries the line.
    sha="$(git -C "$LANES_REPO" rev-parse HEAD 2>/dev/null || printf '')"
    if [ "$NO_GITHUB" != 1 ]; then
      body="$(printf '%s — lane %s, session %s@%s, %s, for %s\n\nLogged in `%s` at `%s`%s.\n\nThe three reads (lane-collision-protocol Rule 1):\n\n```text\n%s\n```\n' \
               "${takeover_from:+TAKEOVER}${takeover_from:-CLAIMED}" "$lane" "$uuid" "$WS" "$utc" "$obj" \
               "$(log_path_for "$lane")" "${sha:-unknown}" "${takeover_from:+ (takeover of the stale claim held by lane $takeover_from)}" "$reads")"
      url="$(gh_comment "$obj" "$body" 2>/dev/null || :)"
      if [ -n "$url" ]; then
        note "comment posted: $url"
      else
        note "WARNING: the GitHub comment could not be posted. The log line IS the claim and it has landed; post the comment by hand so that a reader outside this estate can see it."
      fi
    fi
    note "lane $lane now holds $obj (${sha:-no sha})"
    ;;

  release)
    lane="${LANES_LANE:-}"
    [ -n "$lane" ] || die "release needs the lane: LANES_LANE=<lane> lanes-edit.sh release <object>" 2
    check_lane_name "$lane"
    obj_raw=""; why=""; home_override=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --no-github) NO_GITHUB=1; shift ;;
        --home)      home_override="${2-}"; [ -n "$home_override" ] || die "--home needs owner/repo" 2; shift 2 ;;
        --home=*)    home_override="${1#--home=}"; shift ;;
        --)          shift ;;
        -*)          die "unknown option '$1' for release" 2 ;;
        *)
          if   [ -z "$obj_raw" ]; then obj_raw="$1"
          elif [ -z "$why" ];     then why="$1"
          else die "release takes <object> [\"<why>\"]" 2
          fi
          shift ;;
      esac
    done
    [ -n "$obj_raw" ] || die "usage: release <object> [\"<why>\"] [--no-github] [--home owner/repo]" 2
    log_sync                      # R30 — the fetch, then --home and the STARTED line
    home="$(resolve_home "$lane" "$home_override")" || exit $?
    obj="$(canon_object "$obj_raw" "$home")" || exit 2
    ! is_lane_object "$obj" || die "a lane is not a releasable object" 2
    mine="$(state_events | lane_states_on "$obj" | awk -v sep="$US" -v lane="$lane" 'BEGIN{FS=sep} $2 == lane' || :)"
    if [ -z "$mine" ]; then
      note "NOTE: this lane has no line on $obj — releasing anyway, and the log will show that it did."
    else
      IFS="$US" read -r m_utc m_lane m_verb m_rest <<EOF
$mine
EOF
      is_open_verb "$m_verb" || note "NOTE: this lane's last line on $obj is $m_verb, which is not an open state — releasing anyway."
    fi
    uuid="$(session_for "$lane")"
    utc="$(utc_now)"
    write_event "$lane" RELEASED "$obj" "" "" "$why" "$utc" "$uuid" || exit $?
    if [ "$NO_GITHUB" != 1 ]; then
      url="$(gh_comment "$obj" "$(printf 'RELEASED — lane %s, session %s@%s, %s, for %s%s\n' \
               "$lane" "$uuid" "$WS" "$utc" "$obj" "${why:+ — $why}")" 2>/dev/null || :)"
      [ -n "$url" ] && note "release comment posted: $url"
    fi
    note "lane $lane released $obj"
    ;;

  who)
    mode="object"; arg=""; home_override=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --lane)      mode="lane";    arg="${2-}"; [ -n "$arg" ] || die "--lane needs a lane name" 2; shift 2 ;;
        --lane=*)    mode="lane";    arg="${1#--lane=}"; shift ;;
        --landing)   mode="landing"; arg="${2-}"; [ -n "$arg" ] || die "--landing needs owner/repo" 2; shift 2 ;;
        --landing=*) mode="landing"; arg="${1#--landing=}"; shift ;;
        --home)      home_override="${2-}"; [ -n "$home_override" ] || die "--home needs owner/repo" 2; shift 2 ;;
        --home=*)    home_override="${1#--home=}"; shift ;;
        --no-fetch)  LANES_NO_FETCH=1; shift ;;
        --)          shift ;;
        -*)          die "unknown option '$1' for who" 2 ;;
        *)           [ -z "$arg" ] || die "who takes one argument" 2; arg="$1"; shift ;;
      esac
    done
    [ -n "$arg" ] || die "usage: who <object> | who --lane <lane> | who --landing owner/repo" 2
    log_sync
    case "$mode" in
      lane)    who_lane "$arg" || exit $? ;;
      landing)
        wl_repo="$(alias_lookup "$arg" 2>/dev/null || :)"; wl_repo="${wl_repo:-$arg}"
        case "$wl_repo" in */*) : ;; *) die "--landing needs owner/repo (or an alias in ${LANES_LOG_PREFIX%log/}repos.tsv); '$arg' is neither" 2 ;; esac
        who_landing "$wl_repo" || exit $? ;;
      *)
        home="$(resolve_home "${LANES_LANE:-}" "$home_override")" || exit $?
        obj="$(canon_object "$arg" "$home")" || exit 2
        who_object "$obj" || exit $? ;;
    esac
    ;;

  # --- internal reads, for lane-start and lane-end -------------------------
  # Not part of the protocol's surface: they exist so that the two boundary
  # scripts share ONE implementation of liveness and ONE parser of the log,
  # instead of carrying copies that drift apart.
  # Both answer with 8 for "there is no such record", the same 8 `who` uses,
  # and with anything else ONLY when they failed. `lane-start` and `lane-end`
  # treat 0 and 8 as answers and every other code as a refusal, because the
  # first version of this returned 1 for both and both scripts read 1 as "no
  # holder" / "pre-cutover lane" — a broken helper turned a refusal into a
  # silent pass, which is the one thing a boundary act must never do.
  live-holder)
    lane="${1-}"; [ -n "$lane" ] || die "usage: live-holder <lane>" 2
    # A READ FETCHES FIRST, like every other read here. This one did not, and
    # "the published row" then meant whatever `origin/<branch>` happened to say
    # when this checkout last pulled: a session started from another clone on
    # this workstation stamps its uuid on the row, and until something unrelated
    # fetched, the rename gate could not see it and answered 8 — a rename into a
    # name that is held, which is what mints `<lane> (2)`. The fetch can only
    # ADD ids, and an id is only ever a reason to refuse.
    log_sync
    # The id SET is the published row's union the working tree's (R25): this is
    # the boundary read that decides whether a window may take a name, and an id
    # only ever adds a reason to refuse.
    lh_ids="$( { session_ids_of_lane "$lane" 2>/dev/null || :
                 session_ids_local_of_lane "$lane" 2>/dev/null || :; } | awk 'NF && !seen[$0]++')"
    live_holder "$lane" "$lh_ids"; lh_rc=$?
    case "$lh_rc" in
      0) : ;;
      8) exit 8 ;;
      *) die "could not read this workstation's session records for lane $lane: ${SESSION_FILES_ERR:-unknown error}. That is NOT 'no live session holds it' — fix the records or the permissions and re-run." 1 ;;
    esac
    ;;

  # R20 — a lane's HOME goes through `repos.tsv` like every other spelling, and
  # `lane-start` has no alias table of its own. 0 with the canonical
  # nameWithOwner, 8 when the table has no row for it (the caller records the
  # spelling it derived, and warns), 2 when the table maps it to something that
  # is not owner/repo.
  resolve-repo)
    rr="${1-}"; [ -n "$rr" ] || die "usage: resolve-repo <owner/repo|alias>" 2
    rr_c="$(alias_lookup "$rr" 2>/dev/null || :)"
    [ -n "$rr_c" ] || { printf '%s\n' "$rr"; exit 8; }
    valid_nwo "$rr_c" || die "the alias table maps '$rr' to '$rr_c', which is not owner/repo" 2
    printf '%s\n' "$rr_c"
    ;;

  lane-objects)
    lane="${1-}"; [ -n "$lane" ] || die "usage: lane-objects <lane>" 2
    log_sync
    lane_objects "$lane" || exit $?
    ;;

  # The lane's ROW as it has LANDED — fetched, and read from
  # `origin/<branch>:lanes/LANES.md` like every other state read (R19). 0 with
  # the row, 8 when the published register has none. `lane-end`'s pre-cutover
  # fallback and `lane-start`'s "is this lane new" test both used to read the
  # working tree, which a fetch does not move: a peer's LANDING appended to the
  # state cell, or a peer's whole row, was invisible to both, so `lane-end`
  # wrote NOTHING IN FLIGHT over a live merge hold and `lane-start` added a
  # SECOND row for a lane that already had one — and two rows is a register no
  # helper can edit (`row_line` requires exactly one).
  register-row)
    lane="${1-}"; [ -n "$lane" ] || die "usage: register-row <lane>" 2
    check_lane_name "$lane"
    log_sync
    rr_row="$(row_of_lane "$lane")"
    [ -n "$rr_row" ] || exit 8
    printf '%s\n' "$rr_row"
    ;;

  # `--home`'s validation, WITHOUT a write — the same `resolve_home` the writers
  # call, so a preflight and the write can never disagree. 0 with the canonical
  # home, 8 when the lane has none and none was given, 2 when the option is
  # refused (the lane's log already records its home) or is not owner/repo.
  # `lane-end` forwards `--home` to its own ENDED line, which is written AFTER
  # the row has been closed: without this the refusal arrived too late to
  # refuse anything, and left a closed row with no ENDED line behind it.
  resolve-home)
    lane="${1-}"; [ -n "$lane" ] || die "usage: resolve-home <lane> [<owner/repo|alias>]" 2
    check_lane_name "$lane"
    log_sync
    rh_out="$(resolve_home "$lane" "${2-}")" || exit $?
    [ -n "$rh_out" ] || exit 8
    printf '%s\n' "$rh_out"
    ;;

  *)
    die "unknown subcommand '$cmd' (verify-row|append-row-status|replace-in-row|append-line|add-row|commit|log|claim|release|who)" 2
    ;;
esac
