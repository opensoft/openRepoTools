#!/usr/bin/env bash
#
# lanes-edit.sh — the sanctioned writer for the estate lane registry (LANES.md).
#
# Protocol: ~/.agents/protocols/lane-collision-protocol.md, Rule 9 (registry in
# git) and Rule 10 (workstation designation), Amendment 3, 2026-09-09 — moved
# to the person's workspace repository by Amendment 5, 2026-09-10.
#
# WHERE THE REGISTER LIVES (Amendment 5, 2026-09-10; Amendment 9(a), 2026-09-13)
#   `lanes/LANES.md` on `main` of THE PERSON'S OWN workspace repository — the
#   `<org>/<login>-wip` that `$AGENT_PROTOCOL_ROOT/workspace.yaml` names, which
#   is `opensoft/brett-wip` for the person this file was written for and
#   `opensoft/scott-wip` for the next one. This file names no repository of its
#   own: Amendment 5's second-person clause put a second person's register in a
#   second repository, and Amendment 9 is what made that reachable. Direct commits to
#   `main` are the norm THERE by design: the repository is excluded from the
#   organisation's PR-only ruleset precisely so that a per-edit registry
#   commit can land, which is what Rule 9 requires and what the orphan
#   `lanes` branch of `opensoft/xFactory` used to be for. That branch is
#   RETIRED, and its history came across whole with this file.
#
#   Every path a lane already uses keeps resolving:
#   `~/projects/xFactory/LANES.md` and `~/projects/xFactory/lanes-edit.sh`
#   are symlinks into the checkout, placed by `link-estates`.
#   This script never spells the checkout's own path, and since Amendment 9(a)
#   it no longer derives it from its own location either: it reads
#   `repository:` and `path:` from `$AGENT_PROTOCOL_ROOT/workspace.yaml`, the
#   same pointer file `resume` and `status` already read. This file is an
#   installed command in `~/.local/bin` with no register anywhere near it, so
#   its own directory is evidence about the command and not about a person's
#   data. Failing to find the workspace is a refusal naming
#   `openRepoTools wip init`, never a guess.
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
#   lanes-edit.sh [--no-sweep|--sweep] append-session-id  <lane> "<anchor>" "<text to append>" ["<why>"]
#                                        (the anchor is matched INSIDE THE
#                                         SESSION CELL and nowhere else, and the
#                                         text is appended at the END of it)
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
# AMENDMENT 8 — swap and restart, the READ side (both read-only, never write)
#   lanes-edit.sh swapped       [<workstation>]
#   lanes-edit.sh session-start                  # the SessionStart hook; JSON on stdin
#
# AMENDMENT 12 — the name guard and the lock (the blocking hook)
#   lanes-edit.sh guard                          # the UserPromptSubmit hook; JSON on stdin
#
#   `guard` is the ONLY verb here that refuses a person's work. It reads the
#   hook's JSON, takes the WINDOW from tmux, the SESSION's own name from the
#   live record and the ROW from `origin/<branch>`, and where the three are not
#   one name it REFUSES THE PROMPT (exit 2) with the triple and the one command
#   that cures it. THE LOCK types `/rename <lane>` into this pane where the name
#   has merely drifted; a PERSON's rename to another lane is an OFFER, answered
#   `yes` or `no` at the next prompt. It is silent and cheap where the three
#   agree, silent outside `$PROJECTS_ROOT` and silent for a subagent's prompt.
#
# AMENDMENT 18(h) — one live process per transcript
#   lanes-edit.sh transcript-holders <uuid>      # every live process carrying it
#
#   A transcript is held by ONE live process; the harness can fork one or resume
#   one twice. This read is what `lane-start` asks before it binds or resumes an
#   id, what `lane-end <lane> --retire <pid>` proves a duplicate with, and what
#   `guard` refuses a prompt on. It sweeps EVERY profile's `sessions/`, because a
#   duplicate's record sits in another profile's — measured four times on
#   2026-09-14.
#
#   A SWAP is a planned stop — a usage reset, a profile switch — and a RESTART
#   is the launch that follows it. The RECORD a swap leaves is not a new file:
#   it is the lane's own `PAUSED` line, payload
#   `swap; window <tmux session>:<index>; workstation <ws>`. A lane is SWAPPED
#   on a workstation when that PAUSED is its LAST lane-kind line — no later
#   RESUMED, STARTED, ENDED or RETIRED — and `swapped` lists those lanes, which
#   is how a restart finds its lane once the new tmux session has lost the
#   window name. `session-start` is the whole output of the SessionStart hook:
#   it resolves the lane from the tmux window name, else from the session id in
#   the hook's JSON, prints ONE block, and ALWAYS exits 0 — a hook that fails
#   is a hook that breaks the session it was meant to orient.
#
# AMENDMENT 17 — the handoff is the swap, and the record names the agent
#   lanes-edit.sh lane-agent      <lane>    # the last record's `agent <name>`
#   lanes-edit.sh lane-transcript <lane>    # its `transcript <id|none>`
#   lanes-edit.sh lane-last       <lane>    # its LAST lane-kind line, as
#                                           # <verb><TAB><utc><TAB><session><TAB><payload>
#   lanes-edit.sh workspace-root            # the workspace repository's path
#   lanes-edit.sh log PAUSED … --utc <UTC>  # date a LATE record by its own field
#
#   Clause (b) gives the `PAUSED` payload two sub-fields beside Amendment
#   11(c)'s `window`, `dir` and `profile`: `agent <name>` — `claude`, `codex`,
#   or the launcher's name for whatever wrote the line, a manifest key (letters,
#   digits, `.`, `_`, `-`) — and `transcript <id|none>`, the agent's own
#   resumable id where it has one. THE WRITER VALIDATES BOTH (`pause_subfields_check`,
#   called from `write_event`) because the log is append-only: a malformed
#   sub-field there is malformed for ever, and `lane-start --agent` launches on
#   what it reads. `swapped` prints them as its sixth and seventh fields, after
#   the five it already had, and a record written before this amendment carries
#   neither — which is EMPTY in that output and 8 from the two reads, never a
#   guess (Amendment 7(i)'s cutover rule).
#
#   `--utc <UTC>` IS FOR THE LATE RECORD AND NOTHING ELSE (adoption act 7): the
#   `PAUSED` a swap never left, written after the fact and dated by the moment
#   the old session ENDED rather than by the clock of the shell writing it. It
#   changes which instant the line NAMES and never where the line goes: the log
#   is append-only and FILE ORDER is what every state read means by "last", so
#   `lane-handoff --late` refuses to write one that would land after the
#   relaunch's `RESUMED` — a lane that is running must never read as paused.
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
#   2  refusal: bad arguments, the object is held, an unknown alias, a
#      checkout that cannot be rebased, — Amendment 15 — a register holding
#      two rows whose lane names differ only by case, which every writer and
#      `canon-lane` refuse until 15(d)'s merge, or AMENDMENT 12's BLOCKED
#      PROMPT. SIX MEANINGS ON ONE NUMBER, and they
#      stay readable only because of where each can occur: bad arguments to a
#      subcommand that predates Amendment 11; `register-row`'s "not lane-shaped";
#      AN UNKNOWN SUBCOMMAND (the `*)` arm below), which is how a caller detects
#      a helper predating the amendment that added the read it asked for; and
#      Amendment 11's container refusal. The last is on WRITERS ONLY (the
#      dispatcher guard), so no READ can return it and clause (h)'s
#      fall-to-the-next-rung rule is unaffected by it.
#      THE SIXTH IS NOT THIS FILE'S NUMBER AT ALL: 2 is what a `UserPromptSubmit`
#      hook must exit to BLOCK a prompt (code.claude.com/docs/en/hooks), so
#      `guard` spends the one number the harness reads, and every refusal it
#      makes — a mismatch, an unreadable read, a pending offer's question and
#      its answer — is that 2. `guard` never exits anything else but 0.
#  64  usage — a caller's bad arguments to one of the reads Amendment 11 added
#      (`window-lane`, `lane-dir`, `lane-profile`, `last-session`, `forks`,
#      `duplicate-holder` (issue #39), `workstation`, `fetch-age`, `lanes`,
#      `session-lane`, and `swapped`, which
#      took it first), and to Amendment 15's `canon-lane`, which takes the same
#      contract because its four callers sit in front of a launch as those do. IT WAS IN NO TABLE AT ALL until this round (F-X16), while
#      being the code the contract gives every one of those reads.
#
#      WHY A SECOND USAGE CODE RATHER THAN 2. A read in front of a launch has to
#      tell "you called me wrong" from "this helper has never heard of you" —
#      and the second of those IS a 2, emitted by the `*)` arm, on every
#      workstation until adoption act 3's install reaches it. One number cannot
#      carry both without the caller guessing, so the newer reads spend a number
#      of their own and the older half of this file keeps 2 where it always was.
#      Clause (h)'s table is the contract for which read uses which.
#   3  the edit is never a permanent loss, but this attempt cannot confirm
#      whether it also reached origin. THREE CAUSES (Copilot round 3 on #50,
#      5203261904, naming the other two this row used to leave out): a
#      rebase conflict this attempt could not resolve — not pushed BY THIS
#      ATTEMPT; a later write from this checkout may already carry it to
#      origin, so LOOK by CONTENT before you retry (round 4, 5203455553:
#      SHA ancestry alone misses a peer's rebase of it, which changes the
#      hash but not the patch); `git_timeout_die`'s network timeout on a
#      push OR a pull, where a hung one often already landed; or six
#      attempts exhausted because a peer's own uncommitted file blocks
#      every rebase.
#   4  the mutex could not be taken within 60s
#   5  an edit moved more than one line and was refused — or, Amendment 15, a
#      lane's object log could not be renamed to the row's own spelling
#   6  git add / commit / push failed
#   7  CLAIM-LOST — another lane's claim landed on main first (`claim` only)
#   8  no record — `who` found nothing; `lane-objects` has no log file for the
#      lane; `live-holder` READ this workstation's session records and none of
#      them holds it; `swapped` found no lane swapped on the workstation;
#      `window-session` found no live session in the window. A read that could
#      not be performed is never 8 (R22). `session-start` never exits 8, or
#      anything but 0: it is a hook. `guard` never exits 8 either — it is a hook
#      too, and a BLOCKING one, so its two codes are 0 and 2 (see 2 above).
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
#   LANES_FILE         registry path        (default: <LANES_DIR>/LANES.md)
#   LANES_DIR          dir holding it       (default: <LANES_REPO>/lanes)
#   LANES_REPO         checkout root        (default: the `path:` in
#                                            $AGENT_PROTOCOL_ROOT/workspace.yaml,
#                                            checked to be a checkout of the
#                                            `repository:` beside it — Amendment
#                                            9(a); never a literal path)
#   LANES_WORKSPACE_ROOT  that `path:`, overridden  (the test seam; nothing else
#                                            sets it)
#   AGENT_PROTOCOL_ROOT  dir holding workspace.yaml  (default: ~/.agents)
#   LANES_PATH         pathspec of the register RELATIVE to LANES_REPO
#                                           (default: `lanes/LANES.md`, derived
#                                            with `git rev-parse --show-prefix`)
#   LANES_BRANCH       branch to commit on  (default: main)
#   LANES_LANE         lane name for the commit subject when no lane argument
#   LANES_WORKSTATION  workstation name     (the launcher exports it; else
#                                            `hostname -s` outside a container,
#                                            and inside one WITH NO VALUE every
#                                            WRITER refuses — Amendment 11,
#                                            decision 8(d), R-A11-14)
#   LANES_IN_CONTAINER 1|0                  force the container probe (test seam)
#   LANES_NO_GIT=1     edit only, no commit/push (used by the test harness)
#   LANES_LOG_DIR      the object logs     (default: <LANES_DIR>/log)
#   LANES_REPOS_TSV    the per-wip alias OVERRIDE (default: <LANES_DIR>/repos.tsv)
#   LANES_REPOS_TSV_SHIPPED  the organisation's alias table shipped by
#                      openRepoTools (default: beside this command)
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

# --- THE WORKSPACE REPOSITORY (lane-collision-protocol Amendment 9(a)) -------
#
# The person's data — the register `lanes/LANES.md`, the object logs
# `lanes/log/`, the handoffs, the manifests `park` writes, and a
# `lanes/repos.tsv` override — is found through
# `$AGENT_PROTOCOL_ROOT/workspace.yaml`, and NEVER from this file's own
# location. `resume:466` and `status:1673` already read that same file under
# that same name, and Amendment 9(a) mints no second one: a second way to find
# it is a second answer.
#
# Deriving it from here stopped being POSSIBLE the moment this became an
# installed regular file in `~/.local/bin` with no register anywhere near it,
# and it stopped being WANTED for a subtler reason: a file's location on disk
# is evidence about the file, not about a person's data.
#
# THESE FOUR FUNCTIONS ARE A DELIBERATE COPY, byte for byte, across
# `lanes-edit.sh`, `lane-start`, `lane-end` and `link-estates` — the same trade
# openRepoTools already makes for its own fetch shim (`openRepoTools:93-100`).
# A shared `lanes-common.sh` would be a TENTH file for `--install` to place and
# a broken helper the first time somebody copied only some of them. Each of
# these is one file a person has on PATH.
#
# FAILING TO FIND IT IS A REFUSAL, NEVER A GUESS. No file, no `path:`, no
# `repository:`, or a `path:` that is not the root of a checkout of the
# `repository:` named beside it → the caller refuses, exit 1 — the code
# `lanes-edit.sh` has always used for *registry not found* — with the fix
# named: `openRepoTools wip init`. Nothing here ever creates that file, writes
# a register, or falls back to a path derived from its own location. THE
# CHECKOUT TEST IS NEW: nothing validated it before this, so a `path:` pointing
# at some other repository used to be accepted and now is not.
#
# `LANES_WORKSPACE_ROOT` is the test seam and the only override — the seam
# `lane-start` already spelled for handoff resolution, widened to the whole
# question so `test_lane_helpers.sh` can point every helper at one sandbox.
# --- BEGIN shared workspace resolver (Amendment 9(a)) ----------------------
# BYTE-IDENTICAL IN ALL FOUR LANE HELPERS, and held there by
# `tests/test_repo_hygiene.py`. The estate commands carry the same discipline
# for their own estate resolver and for the same reason its guard gives: a
# drifted copy is TWO ANSWERS to one question, and "where is this person's
# workspace" is exactly the question Amendment 9(a) exists to give one answer
# to. Edit it in one file and the test names the other three.
LANES_WS_WHY=""

lanes_ws_yaml() { printf '%s\n' "${AGENT_PROTOCOL_ROOT:-$HOME/.agents}/workspace.yaml"; }

# `key: value` at the TOP LEVEL only, first occurrence, with an inline `#`
# comment and surrounding quotes stripped and a leading `~` expanded against
# $HOME (nothing expands a bare `~` inside a file). The anchored `^key:` never
# reaches into the INDENTED `orgs:` map, which Amendment 9(a) puts out of
# scope: these helpers read `repository:` and `path:` and nothing else, because
# one register in the first workspace repository is the whole rule — the
# register never follows that map. Two lines of sed, because a YAML parser is
# not a dependency any of these files will take for one scalar.
lanes_ws_field() {
  local v
  v="$(sed -n -e "s/^$1:[[:space:]]*//p" "$2" 2>/dev/null | head -n 1 |
    sed -e 's/[[:space:]]*#.*$//' -e 's/[[:space:]]*$//')"
  v="${v%\"}"; v="${v#\"}"
  v="${v%\'}"; v="${v#\'}"
  case "$v" in
  '~') v="$HOME" ;;
  '~/'*) v="$HOME/${v#'~/'}" ;;
  esac
  printf '%s\n' "$v"
}

# THE WORKSTATION'S NAME IS READ, NEVER INVENTED — AND NEVER `hostname` INSIDE A
# CONTAINER (lane-collision-protocol Amendment 11, ratified decision 8(d), as
# corrected by A11 Addendum 3's `R-A11-14`).
#
# WHAT WENT WRONG. `opensoft/brett-wip` `origin/main` carries SIX lines in
# `lanes/log/openRepoProject-1.md` whose workstation is a container id — five
# `@0e7d1a79a07e`, one `@55cceb3e5bc9` — in an append-only file, written by every
# writer inside that container and not only by Evidence 6's fork. A row on a
# workstation that does not exist is a row no reader can match, no crossing can
# detect and no `swapped <ws>` can answer for; and the log is never rewritten, so
# each one is wrong for ever.
#
# WHO OWNS THE VALUE. `R-A11-14`: the **workBenches launcher**, which runs on the
# host and exports `LANES_WORKSTATION=<the host's own hostname -s>` into every
# session AND every container it starts, beside the `CLAUDE_PROFILE_NAME` it
# already exports. These helpers READ it. They do not write it, they do not
# derive it from a second file, and THEY NEVER SUBSTITUTE A PLACEHOLDER: an
# `@unknown-workstation` is the same defect one field along from the `unknown`
# clause (e) refuses in the session field, and the rejected alternative — a
# `workstation:` key in `workspace.yaml` — is a SECOND PLACE FOR THE TRUTH TO BE
# WRONG beside the variable the launcher already sets.
#
# THE THREE ANSWERS, as `<name><TAB><source>`:
#
#   seam              `$LANES_WORKSTATION` is set. This is the ordinary case
#                     wherever the launcher started the session.
#   hostname          no seam, and this is NOT a container: `hostname -s`, which
#                     is what the seam has defaulted to since Amendment 6 and
#                     what every row written before this rung was written by.
#   container-unset   no seam, and this IS a container. The NAME still answers,
#                     because a read in front of every launch may not refuse —
#                     it will simply match nothing, which is the honest answer —
#                     but every WRITER refuses, exit 2, naming the variable and
#                     the launcher that sets it.
#
# IT ANSWERS AS A PAIR, AND THAT IS NOT A STYLE CHOICE. A caller reads the name
# with `$(lanes_workstation)`, which is a COMMAND SUBSTITUTION and therefore a
# subshell: a global the function set there dies with it. The source is on the
# same line as the name, which is the only way out of a subshell there is.
#
#   $LANES_IN_CONTAINER   1 or 0, forcing the probe. THE TEST SEAM, and nothing
#                         else sets it: the suite must be able to exercise both
#                         halves of this rule on one host, and the host it runs
#                         on is a container exactly when it is.
lanes_in_container() {
  case "${LANES_IN_CONTAINER:-}" in
  1) return 0 ;;
  0) return 1 ;;
  esac
  [ -e /.dockerenv ] || [ -e /run/.containerenv ]
}

lanes_workstation_pair() {
  local v
  if [ -n "${LANES_WORKSTATION:-}" ]; then
    printf '%s\t%s\n' "$LANES_WORKSTATION" seam
    return 0
  fi
  v="$(hostname -s 2>/dev/null || hostname 2>/dev/null || printf 'unknown')"
  if lanes_in_container; then
    printf '%s\t%s\n' "$v" container-unset
  else
    printf '%s\t%s\n' "$v" hostname
  fi
}

# THE NAME ALONE, which is what every writer of the workstation column wants.
lanes_workstation() { lanes_workstation_pair | cut -f1; }

# The ONE SENTENCE a writer refuses with, in one place, so the three writers
# cannot word it three ways. Empty on every other source, so
# `[ -n "$(lanes_workstation_why "$src")" ]` is the whole of the test.
lanes_workstation_why() {   # <source>
  [ "${1:-}" = container-unset ] || return 0
  printf '%s\n' "this is a container and \$LANES_WORKSTATION is not set, so there is no workstation name to write. This host's own \`hostname\` is the CONTAINER'S id, not a workstation, and a row on a workstation that does not exist is a row no reader can match — in a log nothing ever rewrites (Amendment 11, decision 8(d); R-A11-14). The value is the workBenches launcher's to export into every session and container it starts. Set it for this one and re-run: export LANES_WORKSTATION=<this host's name>"
}

# One of the spellings `git remote get-url origin` prints for one GitHub
# repository, reduced to a bare lowercased `<owner>/<name>` so it can be
# compared against workspace.yaml's own `<owner>/<name>`. A URL that is not
# GitHub's is compared as it stands, lowercased — which is what lets a sandbox
# name a bare local origin and still be checked.
lanes_ws_norm() {
  local u="${1%.git}"
  case "$u" in
  https://github.com/*) u="${u#https://github.com/}" ;;
  ssh://git@github.com/*) u="${u#ssh://git@github.com/}" ;;
  git@github.com:*) u="${u#git@github.com:}" ;;
  esac
  printf '%s' "$u" | tr '[:upper:]' '[:lower:]'
}

# Do these two name one repository? Equal after normalisation, OR the origin's
# path ENDS in the `<owner>/<name>` the pointer file spells — which is how a
# GitHub Enterprise host, an ssh alias and a local bare mirror laid out by
# owner and name all say the same thing as `https://github.com/<owner>/<name>`.
# The pointer file spells `<owner>/<name>` because that is what a person types;
# `git remote get-url` spells a URL because that is what git stores.
lanes_ws_same_repo() {
  local a b
  a="$(lanes_ws_norm "$1")"
  b="$(lanes_ws_norm "$2")"
  [ -n "$a" ] && [ -n "$b" ] || return 1
  [ "$a" = "$b" ] && return 0
  case "$a" in */"$b") return 0 ;; esac
  return 1
}

# Prints the workspace checkout's real root, or returns 1 having set
# $LANES_WS_WHY to the one sentence that says which of the five ways it failed.
# ROOT-NESS IS ITS OWN CHECK: `rev-parse --is-inside-work-tree` and
# `remote get-url origin` both succeed from any SUBDIRECTORY of a work tree, so
# a `path:` naming a subdirectory would otherwise be accepted and resolve
# `<path>/lanes/LANES.md` inside the wrong directory.
lanes_workspace_root() {
  local yaml repo path origin toplevel real
  LANES_WS_WHY=""
  if [ -n "${LANES_WORKSPACE_ROOT:-}" ]; then
    printf '%s\n' "$LANES_WORKSPACE_ROOT"
    return 0
  fi
  yaml="$(lanes_ws_yaml)"
  if [ ! -r "$yaml" ]; then
    LANES_WS_WHY="there is no $yaml"
    return 1
  fi
  repo="$(lanes_ws_field repository "$yaml")"
  path="$(lanes_ws_field path "$yaml")"
  if [ -z "$repo" ]; then
    LANES_WS_WHY="$yaml names no \`repository:\`"
    return 1
  fi
  if [ -z "$path" ]; then
    LANES_WS_WHY="$yaml names no \`path:\`"
    return 1
  fi
  if ! git -C "$path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    LANES_WS_WHY="$yaml names path: $path, which is not a git checkout"
    return 1
  fi
  origin="$(git -C "$path" remote get-url origin 2>/dev/null || :)"
  if ! lanes_ws_same_repo "$origin" "$repo"; then
    LANES_WS_WHY="$yaml names repository: $repo, but $path is a checkout of ${origin:-no origin at all}"
    return 1
  fi
  toplevel="$(git -C "$path" rev-parse --show-toplevel 2>/dev/null || :)"
  real="$(cd -- "$path" 2>/dev/null && pwd -P)" || real=""
  if [ -z "$real" ] || [ "$toplevel" != "$real" ]; then
    LANES_WS_WHY="$yaml names path: $path, which is not the ROOT of that checkout (${toplevel:-unknown} is)"
    return 1
  fi
  printf '%s\n' "$real"
}

# The refusal's body, so all four helpers say the same thing in the same words.
#
# THE REASON IS RE-DERIVED HERE, IN THE PARENT SHELL, and that is the whole
# point of this line. Every caller reaches the resolver through a command
# substitution — `LANES_WS_ROOT="$(lanes_workspace_root || :)"` — which runs it
# in a SUBSHELL, so the $LANES_WS_WHY it set died with that subshell and the
# parent still holds the empty string it started with. Six distinct diagnoses
# were being computed and all six were being thrown away; every one of the
# refusals Amendment 9(a) enumerates printed the same "no reason recorded".
# The resolver is read-only and cheap — two `sed`s and three `git` reads — and
# it is reached on the refusal path only, so running it again HERE is the one
# place its answer survives to be printed.
lanes_workspace_why() {
  [ -n "$LANES_WS_WHY" ] || lanes_workspace_root >/dev/null 2>&1 || :
  printf '%s' "the workspace repository could not be found — ${LANES_WS_WHY:-no reason recorded}.
    Amendment 9(a): every lane helper reads \`repository:\` and \`path:\` from
    $(lanes_ws_yaml), never from its own location. One command writes that
    file, creates or clones the repository and places the symlinks:
        openRepoTools wip init"
}
# --- END shared workspace resolver ------------------------------------------

# The register is no longer the whole of its own worktree: since Amendment 5
# it is one file, `lanes/LANES.md`, inside the workspace repository. So every
# git call needs the checkout ROOT and a pathspec RELATIVE to it. Amendment
# 9(a) says where the root comes from; `--show-prefix` still derives the
# pathspec, because `LANES_DIR` may be pointed anywhere by a caller and the
# pathspec must follow it.
#
# RESOLVED HERE, REFUSED LATER. An empty answer is carried rather than fatal,
# so `--help`, the usage and `session-start` — a hook that must exit 0 on a
# machine with no register at all — still run. The refusal is the
# `registry not found` guard below, which is exit 1: the code this script has
# always used for it and the code Amendment 9(a) quotes.
LANES_WS_ROOT=""
if [ -z "${LANES_REPO:-}" ] || { [ -z "${LANES_DIR:-}" ] && [ -z "${LANES_FILE:-}" ]; }; then
  LANES_WS_ROOT="$(lanes_workspace_root || :)"
fi
: "${LANES_REPO:=$LANES_WS_ROOT}"
if [ -z "${LANES_DIR:-}" ]; then
  if [ -n "${LANES_FILE:-}" ]; then
    LANES_DIR="$(dirname -- "$LANES_FILE")"
  else
    LANES_DIR="${LANES_WS_ROOT:+$LANES_WS_ROOT/lanes}"
  fi
fi
LANES_FILE="${LANES_FILE:-$LANES_DIR/LANES.md}"
WS_PAIR="$(lanes_workstation_pair)"
WS="${WS_PAIR%%	*}"
WS_SOURCE="${WS_PAIR##*	}"
NO_GIT="${LANES_NO_GIT:-0}"
LOCK="$LANES_DIR/.lanes-edit.lock"
LOCK_HELD=0
LANES_PATH="${LANES_PATH:-$(git -C "${LANES_DIR:-.}" rev-parse --show-prefix 2>/dev/null || :)${LANES_FILE##*/}}"

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

# AMENDMENT 8, ruling (h): THE LOCK NAMES ITS HOLDER, so a lock nobody holds can
# be told from a lock somebody does. The directory alone could only be aged out,
# and ten minutes of every lane on the workstation blocked is not a recovery.
release_lock() {
  rm -f -- "$LOCK/pid" 2>/dev/null || :
  rmdir -- "$LOCK" 2>/dev/null || :
  LOCK_HELD=0
  return 0
}

cleanup() {
  if [ "$LOCK_HELD" = 1 ]; then release_lock; fi
  [ -n "${TMPD:-}" ] && [ -d "${TMPD:-}" ] && rm -rf -- "$TMPD"
  [ -n "${SE_CACHE_FILE:-}" ] && rm -f -- "$SE_CACHE_FILE" "$SE_CACHE_FILE".* 2>/dev/null
  return 0
}
# AND A SIGNAL ACTUALLY STOPS IT (Amendment 8, ruling (h)). `trap cleanup EXIT
# INT TERM` ran the handler and then CARRIED ON, because a trap that returns
# resumes the command after the one that was interrupted — so a `kill` of a
# writer stuck in `acquire_lock`'s 60-second wait released the lock and then
# went on waiting for it, and a `kill` of one mid-write released the lock while
# it still had the register open. Measured: SIGTERM at 8s, the process still
# running at 56s. The handler now re-raises with the default disposition, which
# is the only way a shell reports "killed by that signal" and the only way the
# process actually stops.
trap cleanup EXIT
trap 'cleanup; trap - INT;  kill -INT  $$' INT
trap 'cleanup; trap - TERM; kill -TERM $$' TERM

# A LOCK WHOSE HOLDER IS DEAD IS STALE THE INSTANT ITS PID IS GONE — not ten
# minutes later. A helper killed at a usage reset, or an ssh that took the
# process down with it, leaves a directory no living process will ever remove,
# and until Amendment 8(h) every writer on the workstation waited out the full
# age-out behind it. A lock with NO pid file is from an older version of this
# script and keeps the age test, which is the only thing that could be said
# about it.
lock_steal_if_dead() {
  [ -d "$LOCK" ] || return 0
  lsd_pid="$(cat -- "$LOCK/pid" 2>/dev/null || :)"
  case "$lsd_pid" in ''|*[!0-9]*) return 0 ;; esac
  [ "$lsd_pid" = "$$" ] && return 0
  kill -0 "$lsd_pid" 2>/dev/null && return 0
  note "taking over $LOCK: its holder (pid $lsd_pid) is gone"
  rm -f -- "$LOCK/pid" 2>/dev/null || :
  rmdir -- "$LOCK" 2>/dev/null || :
  return 0
}

acquire_lock() {
  lock_steal_if_dead
  # Stale lock (>10 min) is removed: a helper run never takes that long. The
  # age test is now the FALLBACK — the pid test above is the real one.
  if [ -d "$LOCK" ]; then
    if [ -z "$(find "$LOCK" -maxdepth 0 -mmin -10 2>/dev/null)" ]; then
      note "removing stale lock $LOCK"
      rm -f -- "$LOCK/pid" 2>/dev/null || :
      rmdir -- "$LOCK" 2>/dev/null || :
    fi
  fi
  i=0
  while [ "$i" -lt 60 ]; do
    if mkdir -- "$LOCK" 2>/dev/null; then
      LOCK_HELD=1
      printf '%s\n' "$$" > "$LOCK/pid" 2>/dev/null || :
      return 0
    fi
    lock_steal_if_dead          # it may have died while we were waiting
    i=$((i + 1))
    sleep 1
  done
  die "could not acquire $LOCK after 60s — another lanes-edit run is active (holder pid $(cat -- "$LOCK/pid" 2>/dev/null || printf 'unrecorded'))" 4
}

# ---------------------------------------------------------------- row lookup

# AMENDMENT 15 — A LANE NAME IS ONE NAME UNDER ANY CASE, AND THE ROW'S SPELLING
# IS THE ONE IT CARRIES (ratified 2026-09-14T00:07:18Z).
#
# Every spelling the WORKING TREE's register carries for a name, compared
# case-insensitively, one per line. This is the set `row_line` counts and the
# set every refusal below NAMES: at 2026-09-13T23:51:56Z a `lane-start
# openxfactory 2` typed in lowercase for the lane `openXfactory-2` found NO row
# here — the row key was the one exact comparison left in this file — and
# appended a SECOND row for a lane that had run since 2026-09-02, while its
# object log went on into the one file both spellings had always shared.
rows_named_ci_local() {   # <typed name>
  awk -v want="$1" '
    substr($0,1,1) == "|" {
      p1 = index($0, "`"); if (p1 == 0) next
      rest = substr($0, p1 + 1); p2 = index(rest, "`"); if (p2 == 0) next
      t = substr(rest, 1, p2 - 1)
      if (tolower(t) == tolower(want)) print t
    }' "$LANES_FILE"
}

# Prints the 1-based line number of the row whose FIRST backticked token is the
# lane name, COMPARED CASE-INSENSITIVELY (Amendment 15). Exactly one match is
# required — and where there are two, that is the amendment's own refusal and
# not a puzzle about which row to edit: 15(d) says the two are merged into one,
# by hand, in a commit that names both spellings.
#
# THE LINE IT RETURNS IS STILL THE EXACT LINE. What changed is how the line is
# FOUND; every editor above still rewrites that one line byte for byte, so a row
# spelled `openXfactory-2` keeps its spelling when a caller typed the lowercase
# form. Which spelling gets WRITTEN into new text is `canon_lane`'s answer, one
# function along.
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
        if (tolower(substr(rest, 1, p2 - 1)) == tolower(lane)) print NR
      }' "$LANES_FILE"
  )"
  n="$(printf '%s' "$hits" | grep -c . || :)"
  if [ "$n" != 1 ]; then
    # NOTE: row_line runs inside $( ), so it must RETURN, not exit — an `exit`
    # here would only leave the command substitution's subshell and the caller
    # would carry on with an empty line number.
    note "expected exactly 1 row for lane '$lane', found $n${hits:+ (lines: $(printf '%s' "$hits" | tr '\n' ' '))}"
    if [ "$n" -gt 1 ]; then
      note "those rows are spelled $(rows_named_ci_local "$lane" | tr '\n' ' ')— a lane name is ONE name under any case (Amendment 15), so merge them into one row (Amendment 15(d)): append the newer row's session id(s) to the older row's session cell, in order, and remove the newer row in the SAME commit"
    fi
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

# A row split into HEAD (everything up to and including the SECOND `|`), the
# SESSION CELL, and TAIL (from the THIRD `|` on) — the three pieces
# `append-session-id` needs, and the only safe way to reach cell 3 of a row
# whose LATER cells may contain a literal `|` (the live register has two such
# rows). It splits from the LEFT for that reason, never from NF. The three
# pieces are asserted to reassemble into the row before anything is written.
RSC_HEAD=""; RSC_CELL=""; RSC_TAIL=""
row_split_session_cell() {   # <row>
  rsc_row="$1"; RSC_HEAD=""; RSC_CELL=""; RSC_TAIL=""
  case "$rsc_row" in *"|"*) : ;; *) return 1 ;; esac
  rsc_rest="${rsc_row#*|}"                 # after the 1st |
  case "$rsc_rest" in *"|"*) : ;; *) return 1 ;; esac
  rsc_rest2="${rsc_rest#*|}"               # after the 2nd |
  case "$rsc_rest2" in *"|"*) : ;; *) return 1 ;; esac
  RSC_CELL="${rsc_rest2%%|*}"
  RSC_TAIL="|${rsc_rest2#*|}"
  RSC_HEAD="${rsc_row%%|*}|${rsc_rest%%|*}|"
  [ "$RSC_HEAD$RSC_CELL$RSC_TAIL" = "$rsc_row" ] || return 1
  return 0
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
  before="$(wc -l < "$pre" | tr -d ' ')"
  {
    [ "$n" -gt 1 ] && head -n "$((n - 1))" -- "$pre"
    printf '%s\n' "$newline"
    tail -n "+$((n + 1))" -- "$pre"
  } > "$out"
  after="$(wc -l < "$out" | tr -d ' ')"
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
  # `| tr -d ' '`, THE SPELLING `park:564` AND `status:746` ALREADY USE — and
  # the one function that did not use it was the macOS job's LARGEST SINGLE
  # CAUSE (A9 Addendum 4, R-A9-11). BSD `wc` right-aligns every count in a
  # fixed-width field, so `wc -l < f` answers `"       5"` on macOS where GNU
  # answers `"5"`, while `$((before_lines + 1))` is arithmetic and is never
  # padded. `[ "       5" = "5" ]` is FALSE — so on BSD this refused EVERY
  # append it was ever asked to make, and refused it HAVING ALREADY APPENDED:
  # the `>>` on the line between them had run, so the `die` left the file
  # modified and uncommitted, and then every later `lanes-edit.sh` in that
  # checkout refused as well (`unstaged tracked change — so the race cannot be
  # run safely here`, 48 times in the macOS transcript at `9000e86`). The
  # message it died with read `append changed line count by 1`: the very
  # equality the test above it had just denied, which is what a comparison of
  # a padded string against an unpadded one looks like from the outside.
  # Measured: transcript line 454 of the macOS job at `9000e86`. And
  # reproduced on Linux under NOTHING BUT a `wc` that pads — the rest of the
  # tree exactly as `d3d59b5` shipped it — for **575 passed, 423 failed**
  # against that runner's own 560 / 438. Fifteen assertions apart, which is
  # about what the second defect (a liveness `sleep` too short for a 900 s
  # run, `tests/test_lane_helpers.sh:446`) has left to contribute once this
  # one has already taken the checkout down with it.
  before_lines="$(wc -l < "$pre" | tr -d ' ')"
  printf '%s\n' "$newline" >> "$target"   # >> FOLLOWS the symlink
  after_lines="$(wc -l < "$target" | tr -d ' ')"
  # `-eq`, not `=`: these are NUMBERS, and saying so is what makes a second
  # padded spelling arriving from anywhere unable to resurrect the defect.
  [ "$after_lines" -eq "$((before_lines + 1))" ] || die "append changed line count by $((after_lines - before_lines)); inspect $target" 5
  # THE WHOLE FILE REBUILT, and no `cmp -n`: the `-n <limit>` that reads
  # "compare at most this many bytes" is GNU's, and BSD `cmp`'s trailing
  # numbers are SKIPS, not a limit — so where GNU compared a prefix, BSD
  # answers `illegal option -- n`, exits 2, and this proof becomes a REFUSAL
  # of a write that was perfectly correct, dying 5 with the log line already
  # on disk and uncommitted. What the file must now be is exactly its old
  # bytes followed by the one new line, so that is what is built and compared:
  # `cat`, `printf` and cmp's `-` operand are POSIX, no byte count is needed
  # (`head -c 0` is an ERROR on BSD, which is what the first append to an
  # empty log would have hit), and the claim is STRONGER than the old one —
  # not merely that no existing byte moved, but that the line appended is the
  # line that was asked for.
  { cat -- "$pre"; printf '%s\n' "$newline"; } | cmp -s -- "$target" - ||
    die "append rewrote existing bytes; inspect $target" 5
  note "1 line appended to $target"
}

# ------------------------------------------------------------------ git side

LANES_BRANCH="${LANES_BRANCH:-main}"

# Bounded like every other network call (Amendment 8(h)). A timeout here is not
# fatal: the callers already degrade to "no remote branch", which costs a fetch
# that would have hung anyway.
remote_has_branch() {
  git_net -C "$LANES_REPO" ls-remote --exit-code --heads origin "$LANES_BRANCH" >/dev/null 2>&1 || {
    [ "$GIT_TIMED_OUT" = 1 ] && note "ls-remote timed out after ${GIT_TIMEOUT}s — treating origin/$LANES_BRANCH as unreachable"
    return 1
  }
  return 0
}

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

# ------------------------------------------- AMENDMENT 8, ruling (h): THE
# WRITER NEVER BLOCKS THE ESTATE.
#
# On 2026-09-12 at about 01:44Z an ssh `git-receive-pack` hung for five minutes
# AFTER its push had already landed, and `lanes-edit.sh append-row-status` sat
# inside it holding the mutex for the whole five minutes. Every lane on Eagle
# that wanted to write a row waited behind a lock whose holder was blocked on a
# socket, and the estate only moved again when the ssh was killed by hand.
#
# So every git call that touches the NETWORK — push, pull, fetch, ls-remote —
# runs under a timeout, and a timeout is not a failure to retry: it is a
# refusal to hold the mutex any longer. The helper aborts any rebase it started,
# releases the lock, prints how to find out whether the push landed anyway, and
# exits 3 with the edit safe in a local commit.
#
# `LANES_GIT_TIMEOUT` is the budget in seconds (default 60; 0 disables the
# bound). `LANES_GIT` is the binary, so a test can hand these calls — and ONLY
# these calls — a git that hangs, without shadowing git for the rest of the
# script.
GIT_TIMEOUT="${LANES_GIT_TIMEOUT:-60}"
GIT_BIN="${LANES_GIT:-git}"
GIT_TIMED_OUT=0
git_net() {
  GIT_TIMED_OUT=0
  gn_rc=0
  case "$GIT_TIMEOUT" in
    ''|0|*[!0-9]*) "$GIT_BIN" "$@" || gn_rc=$? ;;
    *)
      if command -v timeout >/dev/null 2>&1; then
        timeout -k 5 "$GIT_TIMEOUT" "$GIT_BIN" "$@" || gn_rc=$?
        case "$gn_rc" in 124|137) GIT_TIMED_OUT=1 ;; esac
      else
        "$GIT_BIN" "$@" || gn_rc=$?
      fi ;;
  esac
  return "$gn_rc"
}

# What a timed-out network call does. NEVER a retry: the point is to stop
# holding the lock, and a second call to the same hung endpoint holds it twice
# as long.
git_timeout_die() {   # <the command, for the reader>
  note "TIMED OUT after ${GIT_TIMEOUT}s: $1"
  note "  Amendment 8(h): the writer does not hold the estate's mutex on a hung"
  note "  network call. The lock is being released now, before this exits."
  "$GIT_BIN" -C "$LANES_REPO" rebase --abort 2>/dev/null || :
  note "  YOUR EDIT IS SAFE — it is already a local commit:"
  "$GIT_BIN" -C "$LANES_REPO" --no-pager log --oneline "origin/$LANES_BRANCH..HEAD" 2>/dev/null | head -n 5 >&2 || :
  note "  RECOVERY — a hung push often means it LANDED and the connection did not close,"
  note "  so look before you push again:"
  note "    git -C $LANES_REPO fetch origin $LANES_BRANCH && git -C $LANES_REPO log --oneline origin/$LANES_BRANCH -3"
  note "    git -C $LANES_REPO push origin $LANES_BRANCH      # only if it is not there"
  release_lock
  die "timed out after ${GIT_TIMEOUT}s on '$1' — the mutex is released and your commit is local; nothing was lost." 3
}

# commit_push "<subject>" [<pathspec>...] — the pathspecs default to the
# register alone, which is every caller that predates Amendment 7. A LANDING
# or LANDED writes TWO (the register and the lane's log) so that both halves
# of one act land in one commit and no reader ever sees half of it.
# AMENDMENT 15 — A CASE-ONLY RENAME IS STAGED IN THE INDEX AND COMMITTED FROM
# IT, because a PATH-LIMITED commit cannot record one at all on a
# case-INSENSITIVE filesystem — which is what this repository's macOS job runs
# on. `ensure_log` renames a lane's log to the register row's spelling and
# hands the OLD path in beside the new one. Three things are true there, and
# together they leave exactly one way through:
#
#   * `git add -- <old> <new>` under git's own `core.ignorecase=true` matches
#     both pathspecs to the ONE index entry and stages a MODIFICATION under the
#     old name, so the rename never reaches the commit. Measured on the macOS
#     job of openRepoTools#41 at `48f2111`: fifteen red assertions, the first
#     of them *"the rename landed in the WRITE's own commit"*, whose
#     `git log -- <the canonical path>` came back EMPTY.
#   * The same `add` under `core.ignorecase=false` is no better, and is worse:
#     the OPERATING SYSTEM still resolves `lanes/log/repocase-1.md` to the file
#     now named `repoCase-1.md`, so git stages the old entry as MODIFIED and
#     the new path as a SECOND entry. One file on disk, two paths in the tree —
#     and every checkout after it reports the one it cannot materialise as
#     deleted, so the writes behind it are refused (2) for a dirty checkout
#     they did not make. Measured at `e35f2a8` and `928908a`: eleven red
#     assertions, all of them behind `lanes/log/repocase-1.md` reported dirty.
#   * `git commit -- <paths>` is `--only`: it builds the tree from HEAD and the
#     WORKING TREE of those paths, disregarding what is staged. So an index
#     that holds the rename exactly is thrown away by the commit anyway, and
#     the old path — which the OS still resolves — comes back in the tree.
#
# So the old entry is dropped from the INDEX by its exact path, where no
# filesystem is consulted at all; the NEW path alone is added; and the commit
# is made from the index rather than from a pathspec.
# `update-index --force-remove` is the one git verb that removes an entry
# without asking the filesystem whether the file is still there, and it is a
# no-op on a path the index does not hold — so a log that was never committed
# renames just as quietly. The index commit is FAIL-CLOSED: anything staged
# that is not one of this write's own pathspecs refuses (6) instead of riding
# along, which is the guarantee the `--only` pathspec was there to give.
#
# `-c core.ignorecase=false` stays on every call that takes `CP_PATHS`, because
# a pathspec that means one thing to `add` and another to `diff` is the same
# defect one line along: with the old entry already gone it is what makes `add`
# record the new path in the spelling the code computed rather than the one the
# index used to hold. It narrows nothing else — these paths are this file's own,
# `lanes/LANES.md` and `lanes/log/<lane>.md`, spelled by the code that computes
# them.
CP_EXACT="core.ignorecase=false"
commit_push() {
  msg="$1"; shift || :
  if [ "$#" -gt 0 ]; then CP_PATHS=("$@"); else CP_PATHS=("$LANES_PATH"); fi
  [ "$NO_GIT" = 1 ] && { note "LANES_NO_GIT=1 — not committing"; return 0; }
  # THE OLD PATH IS A PATHSPEC FOR THE DIFFS AND NEVER FOR THE `add`: after the
  # index entry is force-removed it matches neither the index nor a directory
  # read that compares exactly, and `git add` FAILS on a pathspec that matches
  # nothing at all.
  cp_ren="${LOG_RENAMED_FROM:-}"
  cp_add=(); cp_add_n=0
  for cp_p in ${CP_PATHS[@]+"${CP_PATHS[@]}"}; do
    if [ -n "$cp_ren" ] && [ "$cp_p" = "$cp_ren" ]; then continue; fi
    cp_add+=("$cp_p"); cp_add_n=$((cp_add_n + 1))
  done
  if [ -n "$cp_ren" ]; then
    git -C "$LANES_REPO" -c "$CP_EXACT" update-index --force-remove -- "$cp_ren" \
      || die "git update-index --force-remove $cp_ren failed — the log is already renamed on disk and git still holds the old path, so nothing was committed. Re-run; if it refuses again, \`git -C $LANES_REPO rm --cached -- $cp_ren\` is the same act by hand." 6
  fi
  if [ "$cp_add_n" -gt 0 ]; then
    git -C "$LANES_REPO" -c "$CP_EXACT" add -- ${cp_add[@]+"${cp_add[@]}"} || die "git add failed" 6
  fi
  if git -C "$LANES_REPO" -c "$CP_EXACT" diff --cached --quiet -- "${CP_PATHS[@]}"; then
    note "nothing staged for ${CP_PATHS[*]} — no commit made"
    return 0
  fi
  if [ -n "$cp_ren" ]; then
    cp_staged="$(git -C "$LANES_REPO" -c "$CP_EXACT" diff --cached --name-only)"
    cp_extra=""
    while IFS= read -r cp_s; do
      [ -n "$cp_s" ] || continue
      cp_known=0
      for cp_p in ${CP_PATHS[@]+"${CP_PATHS[@]}"}; do
        if [ "$cp_s" = "$cp_p" ]; then cp_known=1; fi
      done
      if [ "$cp_known" = 0 ]; then cp_extra="$cp_extra $cp_s"; fi
    done <<EOF
$cp_staged
EOF
    if [ -n "$cp_extra" ]; then
      die "this commit carries a case-only rename of the lane's log, so it is made from the INDEX rather than from its pathspecs — and the index also holds$cp_extra, which is not this write's to commit. Stage-reset it — \`git -C $LANES_REPO restore --staged --\`$cp_extra — and re-run. Nothing was committed and the log is already renamed on disk." 6
    fi
    git -C "$LANES_REPO" -c "$CP_EXACT" commit -q -m "$msg" || die "git commit failed" 6
    # THE RENAME IS DONE AND IN HEAD: the old path is no longer a pathspec of
    # anything below, and the next `commit_push` of this run is not a rename.
    CP_PATHS=(${cp_add[@]+"${cp_add[@]}"})
    LOG_RENAMED_FROM=""
  else
    git -C "$LANES_REPO" -c "$CP_EXACT" commit -q -m "$msg" -- "${CP_PATHS[@]}" || die "git commit failed" 6
  fi
  note "committed: $msg"
  if ! remote_has_branch; then
    if ! git_net -C "$LANES_REPO" push -q -u origin "$LANES_BRANCH"; then
      [ "$GIT_TIMED_OUT" = 1 ] && git_timeout_die "git push -u origin $LANES_BRANCH"
      die "initial push of '$LANES_BRANCH' failed" 6
    fi
    note "pushed (created origin/$LANES_BRANCH)"
    return 0
  fi
  attempt=1
  while [ "$attempt" -le 6 ]; do
    # A peer may have written LANES.md between our commit and this pull.
    if ! git -C "$LANES_REPO" -c "$CP_EXACT" diff --quiet -- "${CP_PATHS[@]}"; then
      cap="$(git -C "$LANES_REPO" -c "$CP_EXACT" --no-pager diff --numstat -- "${CP_PATHS[@]}" | cut -f1,2 | tr '\t' '/')"
      git -C "$LANES_REPO" -c "$CP_EXACT" commit -q -m "LANES(concurrent@$WS): capture an uncommitted registry edit ($cap lines +/-) made by whoever else is writing right now — its author should follow up with a commit that says what it was" -- "${CP_PATHS[@]}" || :
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
      if git_net -C "$LANES_REPO" push -q origin "$LANES_BRANCH"; then
        note "pushed origin/$LANES_BRANCH (attempt $attempt, no pull — see the warning above)"
        return 0
      fi
      [ "$GIT_TIMED_OUT" = 1 ] && git_timeout_die "git push origin $LANES_BRANCH"
      note "push rejected and the pull is blocked by the files above (attempt $attempt)"
      if [ "$attempt" -ge 6 ]; then
        note "RECOVERY: their author commits those files (a handoff: handoff(<lane>@<workstation>): <what>),"
        note "  then re-run: LANES_LANE=<lane> lanes-edit.sh commit \"<what you wrote>\"  — your edit is already"
        note "  a local commit here: git -C $LANES_REPO log --oneline origin/$LANES_BRANCH..HEAD"
        die "could not push origin/$LANES_BRANCH: behind the remote, and a peer's uncommitted file blocks the rebase. Nothing was lost — your commit is local." 3
      fi
    elif git_net -C "$LANES_REPO" pull --rebase -q origin "$LANES_BRANCH"; then
      # The rebase has just put this invocation's commit on top of whatever
      # landed first. `claim` hooks in HERE, because that is the moment the
      # race is decided: if a peer's claim is on this history, theirs landed.
      if [ -n "${CP_AFTER_REBASE:-}" ]; then
        "$CP_AFTER_REBASE" || return $?
      fi
      if git_net -C "$LANES_REPO" push -q origin "$LANES_BRANCH"; then
        note "pushed origin/$LANES_BRANCH (attempt $attempt)"
        return 0
      fi
      [ "$GIT_TIMED_OUT" = 1 ] && git_timeout_die "git push origin $LANES_BRANCH"
      note "push raced (attempt $attempt) — retrying"
    else
      # A TIMED-OUT PULL IS NOT A CONFLICT. Read as one it would send the writer
      # to a recovery that does not apply, and `rebase --abort` would be the
      # only true line in it.
      [ "$GIT_TIMED_OUT" = 1 ] && git_timeout_die "git pull --rebase origin $LANES_BRANCH"
      note "REBASE CONFLICT on origin/$LANES_BRANCH — conflicting lines follow:"
      for cp in "${CP_PATHS[@]}"; do
        grep -n -e '^<<<<<<<' -e '^=======' -e '^>>>>>>>' -- "$LANES_REPO/$cp" 2>/dev/null | head -n 40 >&2 || :
        grep -n -A2 -e '^<<<<<<<' -- "$LANES_REPO/$cp" 2>/dev/null | head -n 40 >&2 || :
      done
      git -C "$LANES_REPO" rebase --abort 2>/dev/null || :
      cp_sha="$(git -C "$LANES_REPO" rev-parse HEAD 2>/dev/null)"
      note "rebase ABORTED — the worktree is clean and NOT mid-rebase. Your edit is safe in these local commits:"
      git -C "$LANES_REPO" --no-pager log --oneline "origin/$LANES_BRANCH..HEAD" 2>/dev/null | head -n 10 >&2 || :
      # #32 — AN ABORTED PULL IS NOT PROOF THIS COMMIT NEVER REACHED ORIGIN
      # (the same rule RV-B3 took for the handoff stamp's own push, in
      # lane-start). This checkout is shared with every lane on the
      # workstation, so the very next write out of it pulls this dangling
      # commit onto its own and pushes both together — three of the four
      # "rebase conflict … nothing was pushed" lines seen on Eagle in one
      # hour named a commit that was ALREADY on origin by the time anyone
      # read them. LOOK before you reset or redo anything — by ANCESTRY
      # (Copilot round 2 on #50, 5203033893): a log capped at a few entries
      # can bury this commit below the window while it stays an ancestor, the
      # moment four or more later writes land ahead of it.
      # ROUND 3 (Copilot 5203261904): `fetch && merge-base ... && echo A ||
      # echo B` is left-associative — a FAILED fetch also falls to the `||`
      # and prints the SAME "not-there" a genuine non-ancestor does, so a
      # stale or unreachable origin would silently wave the reset/redo path
      # through. Fetch is now its own line, checked before anything else.
      # ROUND 4 (Copilot 5203455553): SHA ancestry is the wrong test — the
      # very write this whole recovery exists to catch (a peer's own
      # `commit_push` pulling THIS dangling commit and rebasing it onto a
      # newer base, per the very next branch above) gives it a NEW sha, so
      # `merge-base --is-ancestor $cp_sha …` answers "not-there" even once
      # the CONTENT is published. `git cherry` compares by PATCH, not by
      # sha, so a rebase that only replays the same change (no real
      # conflict) is still found. Measured against a real bare repo: a
      # commit rebased by a peer this way answers `not-there` under
      # `merge-base --is-ancestor` and `-` (found, equivalent) under
      # `git cherry` — verified for the genuinely-absent case too (`+`) and
      # the plain same-sha case (no output at all, which the `-c '^+'`
      # count below also reads as zero, i.e. already there).
      note "RECOVERY (in that order):"
      note "  git -C $LANES_REPO fetch origin $LANES_BRANCH || echo FETCH-FAILED   # if that printed FETCH-FAILED, STOP and retry — a stale or unreachable origin proves nothing either way"
      note "  git -C $LANES_REPO cherry origin/$LANES_BRANCH $cp_sha | grep -c '^+'   # BY CONTENT, not by sha: a peer's rebase changes the hash but git cherry still finds the same patch"
      note "  if that printed 0, STOP — reset or redo now would write it a second time."
      note "  git -C $LANES_REPO diff origin/$LANES_BRANCH..HEAD -- ${CP_PATHS[*]}   # only if it is not there: read back exactly what you wrote"
      note "  git -C $LANES_REPO reset --hard origin/$LANES_BRANCH                # then drop the local commits (NOTE: also drops any"
      note "                                                          # uncommitted peer edit in this checkout)"
      note "  then re-read LANES.md and redo the edit with lanes-edit.sh, on top of the peer's version."
      die "rebase conflict on origin/$LANES_BRANCH — not pushed by this attempt; a later write from this checkout may already carry it, so look before you retry." 3
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

LANES_PREFIX="${LANES_PREFIX:-$(git -C "${LANES_DIR:-.}" rev-parse --show-prefix 2>/dev/null || :)}"
LANES_LOG_DIR="${LANES_LOG_DIR:-$LANES_DIR/log}"
LANES_LOG_PREFIX="${LANES_LOG_PREFIX:-${LANES_PREFIX}log/}"

# THE ALIAS TABLE IS TWO LAYERS, in this order (Amendment 9(b), ruling 3): the
# per-wip OVERRIDE in the person's own workspace repository, then the
# organisation's table shipped by openRepoTools and installed beside this
# command. An override row replaces the shipped row for the same alias and adds
# rows the shipped table does not carry; an alias in NEITHER layer is still a
# refusal naming the fix, spell it `owner/repo` (Amendment 7(a), unchanged).
#
# The shipped copy sits BESIDE this file because `--install` places from one
# list into one directory at one mode — the alternative was a second
# destination and a second mode in two repositories, which is why the table
# carries an executable bit it has no use for.
LANES_REPOS_TSV="${LANES_REPOS_TSV:-${LANES_DIR:+$LANES_DIR/repos.tsv}}"
if [ -z "${LANES_REPOS_TSV_SHIPPED:-}" ]; then
  if [ -n "${OPENREPOTOOLS_BIN_DIR:-}" ] && [ -f "$OPENREPOTOOLS_BIN_DIR/repos.tsv" ]; then
    LANES_REPOS_TSV_SHIPPED="$OPENREPOTOOLS_BIN_DIR/repos.tsv"
  else
    LANES_REPOS_TSV_SHIPPED="$SCRIPT_DIR/repos.tsv"
  fi
fi
PROJECTS_ROOT="${PROJECTS_ROOT:-$HOME/projects}"
NO_GITHUB="${LANES_NO_GITHUB:-0}"
STALE_HOURS="${LANES_STALE_HOURS:-4}"     # Rule 1's threshold, reused

# The field separator for every machine-read line below. NOT a tab: a tab is
# IFS WHITESPACE, so bash's `read` collapses runs of them and one empty field
# (an event with no payload) shifts every field after it one to the left.
# \037 — US, "unit separator" — is not whitespace, so empty fields survive it.
US="$(printf '\037')"
# THE ROW SEPARATOR FOR THE IN-SHELL LOOKUP TABLES (A11 Addendum 4 ruling 12).
# GS, one below US, and for the same reason US was chosen over a tab: it is not
# IFS whitespace, so an empty field does not shift every field after it.
GS="$(printf '\036')"

# ONE LINE OUT OF A TABLE THIS SHELL IS ALREADY HOLDING, WITHOUT A PROCESS.
# The listing's three tables — the published register's index, this checkout's,
# and one line of facts per lane — are a few dozen lines each and were read with
# `printf | awk` PER LANE, which is six processes a lane to look up strings that
# are already in memory. Fenced with `$GS` and keyed on the lane name
# lower-cased, the whole lookup is one parameter expansion.
#
# IT ASSIGNS A GLOBAL AND RETURNS, rather than printing: a function whose answer
# is taken with `$( … )` forks, which is the cost this exists to avoid.
LOOKUP_OUT=""
table_lookup() {   # <fenced table> <lower-cased lane>
  local tl_rest
  LOOKUP_OUT=""
  tl_rest="${1#*"$GS$2$US"}"
  [ "$tl_rest" = "$1" ] && return 1
  LOOKUP_OUT="${tl_rest%%"$GS"*}"
  return 0
}

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

# AMENDMENT 15 — THE LOG FILE IS `lanes/log/<canonical>.md`, AND A FILE OF
# ANOTHER CASE IS STILL THIS LANE'S LOG.
#
# The log's file name was lowercased from the start, which is exactly why the
# 2026-09-13 incident produced TWO ROWS AND ONE LOG: `openXfactory-2` and
# `openxfactory-2` had always shared `lanes/log/openxfactory-2.md`. The real
# register still carries `lanes/log/openxfactory-4.md` beside the row
# `openxfactory-4` — the same spelling, nothing to do — and the historical
# mismatch is the shape these two functions exist for. READERS find the file
# whatever its case; the first WRITE renames it to the canonical spelling, once,
# inside its own commit (`ensure_log` below).
#
# `ls` and one `awk`, not a `$(lc …)` per file: `lanes/log/` carries a file per
# lane of the estate and this is asked on the path a person is waiting on.
#
# AND THE `--` STAYS (Copilot round 3 on openRepoTools#41, DECLINED with a
# measurement). It was read as a macOS defect — *"BSD `ls` rejects `--`, and the
# suppressed error makes every case-insensitive log scan empty"* — which would
# mean no first write ever renames anything on the one platform this amendment's
# rename exists for. BSD `ls` ends its options at `--` through `getopt(3)`, as
# every POSIX utility does, and `tests-macos` has been GREEN on the two
# assertions that can only pass if this scan finds a file of another case there:
# the rename recorded inside the write's own commit, and `lane-start`'s own
# `repo repocase → repoCase` out of the twin scan at `lane-start:677`. The suite
# asserts the parse itself as well, on every platform. Dropping `--` would hand
# a directory whose name begins with `-` back to `ls` as flags and change
# nothing else.
log_files_named_ci() {   # <lane> — every existing log file for it, whatever its case
  ls -- "$LANES_LOG_DIR" 2>/dev/null | awk -v want="$1" -v d="$LANES_LOG_DIR" '
    BEGIN { w = tolower(want) ".md" }
    tolower($0) == w { print d "/" $0 }'
}

# The PUBLISHED path of a lane's log, found the same way — the canonical path
# where `origin/<branch>` has no file of another case, so a lane with no log at
# all still reads as the pre-cutover 8 rather than as a failure.
#
# TWO PATHS DIFFERING ONLY BY CASE ARE A REFUSAL AND NOT A CHOICE (Copilot round
# 4 on openRepoTools#41). The `exit` after the first match read a tree holding
# BOTH `lanes/log/repocase-1.md` and `lanes/log/repoCase-1.md` as though it held
# one, and every reader behind it — `lane_log_events`, `lane_log_exists`,
# `last-session`, the listing's per-lane facts — then consumed whichever `ls-tree`
# happened to name first and DROPPED the other file's lines without saying so.
# That is two logs for one lane, the state 15(d)'s hand merge exists for, and an
# append-only history half of which is invisible is worse than a refusal. Counted
# and REFUSED (2) naming both, in `canon_lane`'s own shape — it RETURNS rather
# than exits, because every caller takes it with `$( )`.
#
# AND THE WORKING TREE ANSWERS WHERE `origin` HAS NOTHING. The fallback was the
# canonical path outright, which is a path that need not exist: a lane whose log
# is still spelled the old way and has never been pushed has ONE file on disk and
# this named another. `claim`'s dirty-checkout exemption is computed from it, so
# the lane's own uncommitted log read as an unrelated dirty file and the claim was
# refused for it. The same case-insensitive scan every other reader uses answers
# that half (Copilot round 4).
log_path_ci() {   # <lane> — 0 with the ONE path, 2 where two differ only by case
  lpc_exact="$(log_path_for "$1")"
  if have_remote_ref; then
    lpc_hits="$(git -C "$LANES_REPO" ls-tree --name-only "origin/$LANES_BRANCH" -- "$LANES_LOG_PREFIX" 2>/dev/null \
      | awk -v want="$lpc_exact" 'BEGIN { w = tolower(want) } tolower($0) == w')"
    lpc_n="$(printf '%s' "$lpc_hits" | grep -c . || :)"
    if [ "$lpc_n" -gt 1 ]; then
      note "lane $1 has $lpc_n object logs on origin/$LANES_BRANCH whose names differ only by case: $(printf '%s\n' "$lpc_hits" | tr '\n' ' ')"
      note "one lane is ONE lane under any case and its log is ONE file (Amendment 15), so no read of it is unambiguous and nothing here picks one of them. Merge them by hand into $lpc_exact, oldest lines first, remove the others in the same commit (Amendment 15(d)), and re-run."
      return 2
    fi
    [ "$lpc_n" = 1 ] && { printf '%s\n' "$lpc_hits"; return 0; }
  fi
  lpc_loc="$(log_files_named_ci "$1")"
  lpc_ln="$(printf '%s' "$lpc_loc" | grep -c . || :)"
  if [ "$lpc_ln" -gt 1 ]; then
    note "lane $1 has $lpc_ln object logs in this checkout whose names differ only by case: $(printf '%s\n' "$lpc_loc" | tr '\n' ' ')"
    note "one lane is ONE lane under any case and its log is ONE file (Amendment 15), so no read of it is unambiguous and nothing here picks one of them. Merge them by hand into $(log_file_for "$1"), oldest lines first, remove the others in the same commit (Amendment 15(d)), and re-run."
    return 2
  fi
  [ "$lpc_ln" = 1 ] && { printf '%s\n' "${LANES_LOG_PREFIX}${lpc_loc##*/}"; return 0; }
  printf '%s\n' "$lpc_exact"
}

# The repo-relative path `ensure_log` renamed a log AWAY from, for the ONE
# caller that has to put it in the same commit as the write. Empty on every
# other run, and reset by every `ensure_log`, so "renamed" is never sticky.
LOG_RENAMED_FROM=""

ensure_log() {
  lane="$1"; lf="$(log_file_for "$lane")"
  LOG_RENAMED_FROM=""
  [ -d "$LANES_LOG_DIR" ] || mkdir -p -- "$LANES_LOG_DIR"
  el_hits="$(log_files_named_ci "$lane")"
  el_n="$(printf '%s' "$el_hits" | grep -c . || :)"
  if [ "$el_n" -gt 1 ]; then
    die "lane $lane has $el_n object logs whose names differ only by case: $(printf '%s\n' "$el_hits" | tr '\n' ' ')— one lane is ONE lane under any case and its log is ONE file (Amendment 15). Merge them by hand into $lf, oldest lines first, remove the others in the same commit, and re-run. Nothing was written." 2
  fi
  # A LOG THIS CHECKOUT HAS NOT PULLED IS STILL THIS LANE-S LOG, AND CREATING
  # THE CANONICAL FILE BESIDE IT IS THE SPLIT THIS FUNCTION EXISTS TO PREVENT.
  # `log_files_named_ci` reads the WORKING TREE, while every state reader here
  # deliberately answers out of `origin/<branch>` (R19): on a checkout that is
  # behind, a published `lanes/log/repocase-1.md` is invisible to the scan
  # above, this write would create `repoCase-1.md`, and `commit_push`-s own
  # rebase would then land BOTH. The refusal below is fail-closed and its cure
  # is one command, where the cure for two published files is 15(d)-s hand
  # merge (Copilot round 1 on openRepoTools#41).
  #
  # AND THE GUARD IS NOT ONLY FOR A CHECKOUT WITH NO FILE AT ALL (Copilot round 4
  # on openRepoTools#41). It ran under `el_n = 0`, so the state a rename leaves
  # when its COMMIT does not land — the canonical file here, the old-cased path
  # still in the remote tree — walked straight past it, and the next write staged
  # the canonical path alone and left the published one where it was: two files
  # for one lane again, by the path this function exists to close. The test is
  # therefore on the PATHS and not on the count: a published path that is neither
  # the canonical one NOR the one this checkout is about to rename FROM is a
  # refusal, which leaves the ordinary rename (local and published agree on the
  # old spelling) exactly as it was.
  el_from=""
  [ "$el_n" = 1 ] && el_from="$el_hits"
  if have_remote_ref; then
    el_pub="$(log_path_ci "$lane")" || die "lane $lane's object log is published twice (above) and nothing is written under a name that means two files. Merge them by hand (Amendment 15(d)) and re-run. Nothing was written." 2
    if [ "$el_pub" != "$(log_path_for "$lane")" ] && [ "${el_from##*/}" != "${el_pub##*/}" ]; then
      el_here="and this checkout does not have it"
      [ -n "$el_from" ] && el_here="while this checkout has ${LANES_LOG_PREFIX}${el_from##*/} instead — a case-only rename whose commit never landed"
      die "lane ${lane}'s object log is published as $el_pub $el_here: the row spells the lane $lane, so the log is $(log_path_for "$lane") (Amendment 15), and writing one here now would leave TWO files for one lane. Pull first — \`git -C $LANES_REPO pull --rebase\` — and re-run; the rename then happens once, inside this write's own commit. Nothing was written." 2
    fi
  fi
  if [ -n "$el_from" ] && [ "$el_from" != "$lf" ]; then
    # THE RENAME IS ONE ACT AND IT HAPPENS ONCE: after it the canonical name is
    # the only one `log_files_named_ci` can find, so the next write takes the
    # branch above and does nothing. THROUGH A TEMPORARY NAME, because on a
    # case-INSENSITIVE filesystem — macOS, which this repository's CI runs — the
    # two names are one file and `mv a A` answers "identical" rather than
    # renaming; two `mv`s do the same job on both kinds of filesystem, and
    # neither is `git mv`, whose own case-only rename is the thing that differs
    # between platforms. The caller puts the old path in this write's pathspecs
    # and `commit_push` drops its INDEX entry by that exact path before staging
    # the new one, then commits the index rather than the pathspecs — the one
    # sequence that records the rename on a case-insensitive filesystem as well
    # as on this one, argued in full above `CP_EXACT`.
    el_tmp="$lf.amendment15.$$"
    # THE REFUSAL SAYS WHERE THE FILE IS, and the two halves fail differently:
    # the first `mv` failing leaves the log exactly where it was, while the
    # SECOND failing leaves it at `$el_tmp` — a name no reader of this
    # directory looks for. A refusal that told a person to "move it by hand"
    # without saying which path to move is a refusal they cannot act on, and
    # this one costs a lane its whole history if it is acted on wrongly.
    if ! mv -- "$el_from" "$el_tmp" 2>/dev/null; then
      die "could not rename $el_from to $lf (Amendment 15: the register row's spelling names the lane's log). Nothing was written and the log is untouched at $el_from; rename it by hand and re-run." 5
    fi
    if ! mv -- "$el_tmp" "$lf" 2>/dev/null; then
      die "could not rename $el_tmp to $lf (Amendment 15: the register row's spelling names the lane's log). Nothing was written, and THIS LANE'S LOG IS NOW AT $el_tmp — rename it to $lf by hand, or back to $el_from, and re-run. It is not lost and no reader looks for it under that name." 5
    fi
    LOG_RENAMED_FROM="${LANES_LOG_PREFIX}${el_from##*/}"
    note "$el_from → $lf: the register row spells this lane $lane, and the row's spelling names its log (Amendment 15)"
  fi
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
  al_k="$1"
  for al_tsv in "${LANES_REPOS_TSV:-}" "${LANES_REPOS_TSV_SHIPPED:-}"; do
    [ -n "$al_tsv" ] && [ -f "$al_tsv" ] || continue
    awk -F'\t' -v k="$al_k" '
      BEGIN { kl = tolower(k) }
      /^[ \t]*#/ { next }
      NF >= 2 { if (tolower($1) == kl) { print $2; found = 1; exit } }
      END { exit(found ? 0 : 1) }' "$al_tsv" && return 0
  done
  return 1
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
      # AMENDMENT 15 — A LANE OBJECT CARRIES THE ROW'S SPELLING TOO. `lane:<name>`
      # is the object of every lane-kind line (7(b)), so a `log PAUSED
      # lane:openxfactory-2` on the lane `openXfactory-2` would write a key that
      # does not match the lane's own earlier lines — in a file nothing rewrites,
      # and against which `who lane:<name>` is then asked. Canonicalised here, so
      # the writers and the reader ask the same question of it.
      co_cl="$(canon_lane "${co_raw#lane:}")" || return 2
      printf 'lane:%s\n' "$co_cl"; return 0 ;;
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

# A TRANSCRIPT UUID, and nothing else — the shape `claude --resume` takes
# exactly and the one every event line's `session` field carries (Amendment
# 7(b), Definitions sense 1). Not a PR-footer `session_01…`, not a session
# NAME, and not the literal `unknown`: `write_event` refuses all three.
valid_uuid() { [[ "${1-}" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; }

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
# THE BUILD'S WARNINGS OUTLIVE THE BUILD, AND THAT IS NOT A CONVENIENCE.
# `LOG_AWK` writes `unreadable: <file>:<line>` and its count to stderr WHILE the
# stream is parsed — so they were emitted by whichever caller happened to build
# the cache first, and lost entirely when that caller was a command substitution
# with `2>/dev/null`. That was always true and never mattered, because the
# first builder in `who` was a call whose stderr reached the person. Ruling 12's
# one-pass listing moved the first build into exactly such a substitution — the
# `lr_facts` render — and the whole warning vanished from `who --lane`, caught
# by the two assertions that exist for it.
#
# So the build's stderr is CAPTURED beside the cache and replayed once per
# shell. `SE_WARNED` is deliberately a plain variable: a subshell that replays
# into `/dev/null` sets it only in ITSELF, so the parent still warns at its own
# first call — which is the call whose stderr a person is reading. An
# append-only log is never rewritten, so a line no parser reads is a hold no
# tool will mention again: this warning is the only notice there is.
SE_WARN_FILE="${SE_CACHE_FILE:+$SE_CACHE_FILE.warn}"
SE_WARNED=0
state_events_warn() {
  [ "$SE_WARNED" = 1 ] && return 0
  [ -n "$SE_WARN_FILE" ] && [ -s "$SE_WARN_FILE" ] || return 0
  SE_WARNED=1
  cat -- "$SE_WARN_FILE" >&2
  return 0
}
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
    remote_log_events > "$se_t" 2> "$se_t.warn"
    mv -f -- "$se_t.warn" "$SE_WARN_FILE" 2>/dev/null || rm -f -- "$se_t.warn"
    mv -f -- "$se_t" "$SE_CACHE_FILE" 2>/dev/null || { state_events_warn; cat -- "$se_t"; rm -f -- "$se_t"; return 0; }
  fi
  state_events_warn
  cat -- "$SE_CACHE_FILE"
}
state_events_flush() {
  [ -n "$SE_CACHE_FILE" ] && : > "$SE_CACHE_FILE"
  # The warnings belong to the stream that was parsed; a flush means it is
  # parsed again, so they are said again.
  [ -n "$SE_WARN_FILE" ] && : > "$SE_WARN_FILE"
  SE_WARNED=0
  return 0
}

# One lane's own events, and whether that lane has a log at all — from
# `origin/<branch>` for the same reason. A lane whose log exists only in this
# working tree has not published anything, and a lane whose log exists only on
# `origin` is a lane this checkout has not pulled: the second is the case that
# matters and the one that used to read as "pre-cutover".
#
# AMENDMENT 15 — AND THE FILE IS FOUND WHATEVER ITS CASE. A lane whose log was
# written under another spelling has not lost its history the moment its row's
# spelling becomes canonical; the first write renames the file, and until then
# every reader finds it.
#
# BOTH HALVES ASK `log_path_ci`, AND A `head -n1` IS NOT AN ANSWER (Copilot round
# 4 on openRepoTools#41). The working-tree branch took the first of the
# case-insensitive matches exactly as the published lookup did, so two local
# files made a read-only caller decide a lane's resume, its profile and its state
# out of half its history — silently, while the WRITER treats that same state as
# ambiguous and refuses. One resolver now answers both, and its 2 is carried:
# `lane_log_exists` spends it rather than 1, so "there are two logs" is never
# read as "there is no log".
lane_log_events() {
  ll_rel="$(log_path_ci "$1")" || return 2
  if have_remote_ref; then
    git -C "$LANES_REPO" show "origin/$LANES_BRANCH:$ll_rel" 2>/dev/null | parse_log_stream "$ll_rel"
  else
    ll_f="$LANES_LOG_DIR/${ll_rel##*/}"
    [ -f "$ll_f" ] || return 0
    log_events "$ll_f"
  fi
}
lane_log_exists() {
  lle_rel="$(log_path_ci "$1")" || return 2
  if have_remote_ref; then
    git -C "$LANES_REPO" cat-file -e "origin/$LANES_BRANCH:$lle_rel" 2>/dev/null
  else
    [ -f "$LANES_LOG_DIR/${lle_rel##*/}" ]
  fi
}

# The register, read the same way — `who --landing` is a state read about a
# merge hold other lanes are holding their merges for, so it must see what
# landed rather than what this checkout happens to have pulled.
# CACHED FOR THE LIFE OF ONE PROCESS, and Amendment 11's listing is the reason.
# The published register is a 1 MB file and this is a `git show` of it; every
# `row_of_lane`, `lane_named_ci`, `lane_of_session` and `lane_workstation` call
# makes one. A single lane's act makes a handful and nobody noticed — but
# `lanes` asks about EVERY lane in the register, so the same megabyte was being
# re-rendered dozens of times for one listing a person is waiting on.
#
# IT IS SAFE BECAUSE NOTHING INSIDE ONE INVOCATION MOVES IT. `origin/<branch>`
# is advanced by `log_sync`, which every subcommand runs BEFORE it reads, and by
# `commit_push`, which runs AFTER the last read of a write path — so the ref a
# process reads is fixed for as long as that process reads it. The one act that
# would break that assumption is a second `log_sync` mid-read, and there is
# none; `log_sync` clears this cache anyway, so a caller that adds one gets the
# fresh answer rather than a stale one.
# AND IN A FILE AS WELL AS A VARIABLE (A11 Addendum 4 ruling 12). The variable
# serves one shell; every caller of `row_of_lane`, `lane_workstation` and
# `session_ids_of_lane` reaches it through `$( … )`, which is a SUBSHELL, so the
# variable cache was rebuilt — a `git show` of 1.1 MB — by all four of the
# per-lane reads the listing makes, for every lane. The file survives the
# subshell that wrote it, so the megabyte is rendered once per process.
LANES_REGISTER_CACHE=""
register_text() {
  if [ -n "$LANES_REGISTER_CACHE" ]; then printf '%s\n' "$LANES_REGISTER_CACHE"; return 0; fi
  rt_c="${SE_CACHE_FILE:+$SE_CACHE_FILE.register}"
  if [ -n "$rt_c" ] && [ -s "$rt_c" ]; then cat -- "$rt_c"; return 0; fi
  if have_remote_ref && git -C "$LANES_REPO" cat-file -e "origin/$LANES_BRANCH:$LANES_PATH" 2>/dev/null; then
    LANES_REGISTER_CACHE="$(git -C "$LANES_REPO" show "origin/$LANES_BRANCH:$LANES_PATH" 2>/dev/null)"
  else
    LANES_REGISTER_CACHE="$(cat -- "$LANES_FILE")"
  fi
  if [ -n "$rt_c" ]; then
    printf '%s\n' "$LANES_REGISTER_CACHE" > "$rt_c.${BASHPID:-$$}" 2>/dev/null &&
      mv -f -- "$rt_c.${BASHPID:-$$}" "$rt_c" 2>/dev/null ||
      rm -f -- "$rt_c.${BASHPID:-$$}"
  fi
  printf '%s\n' "$LANES_REGISTER_CACHE"
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
# AMENDMENT 15 — KEYED ON THE LANE LOWER-CASED. The key decides how many rows
# come out of here, and the ROW is the whole line, so the spelling a reader sees
# is still the one the winning line carried. Keyed on the raw `$2`, a lane whose
# log spells it two ways emitted TWO rows for ONE lane — and `claim`-s rival
# test, which excludes its OWN row from this set, then met its own earlier
# CLAIMED as a stranger and refused the lane its own object (Copilot round 1 on
# openRepoTools#41).
PER_LANE_AWK='
function pos(pf, pn) { return pf "\034" sprintf("%09d", pn) }
BEGIN { FS = sep }
$6 == o { k = tolower($2); p = pos($10, $11); if (!(k in u) || p >= u[k]) { u[k] = p; L[k] = $0 } }
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

# A LANE NAME IS NOT A REGULAR EXPRESSION (Copilot round 4 on openRepoTools#41).
# Every filter of these US-delimited holder rows was `grep "^$lane$US"`, which
# hands a name straight to a matcher: `check_lane_name` admits `.`, so excluding
# `repo.a-1` also excludes the REAL rival `repoXa-1`, and `first_landed_of`'s
# `grep -q` could match a lane that is not in the set at all. A claim decided by
# that filter is a claim whose winner is whichever name happened to be a pattern
# — in a race whose whole point is that the arbiter is exact.
#
# So the comparison is `awk` on FIELD ONE, `tolower` on both sides, with no
# pattern anywhere: literal, case-insensitive (Amendment 15) and blind to `.`,
# `*`, `[` and `^`. `-v` carries one line, which a lane name is.
rows_not_named() {   # <lane> — every row whose first field is NOT it
  awk -v sep="$US" -v want="$1" 'BEGIN { FS = sep; w = tolower(want) } tolower($1) != w'
}
rows_named() {       # <lane> — every row whose first field IS it
  awk -v sep="$US" -v want="$1" 'BEGIN { FS = sep; w = tolower(want) } tolower($1) == w'
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
  # 8, not 1: "no log file" is an ANSWER. TWO LOGS IS NOT THAT ANSWER, and 2 is
  # carried through rather than flattened into it (Copilot round 4): `who --lane`
  # and `lane-end`'s refusal would otherwise report a lane whose history is split
  # across two files as a pre-cutover lane with no log at all.
  lo_ex=0
  lane_log_exists "$1" || lo_ex=$?
  case "$lo_ex" in
    0) : ;;
    2) return 2 ;;
    *) return 8 ;;
  esac
  # AMENDMENT 15 — THE LANE FIELD OF A LOG LINE IS MATCHED CASE-INSENSITIVELY,
  # and the caller has already resolved `$1` to the row's spelling. The line's
  # own spelling is whatever was TYPED on the day it was appended, and an
  # append-only log is never rewritten: `lanes/log/openxfactory-2.md` carries
  # `lane openXfactory-2` lines from 2026-09-02 and `lane openxfactory-2` lines
  # from the 23:51:56Z incident, in one file, about one lane. Read byte for
  # byte, half of that lane's claims are invisible to `who --lane` and to
  # `lane-end`'s refusal — which is the amendment's own sentence, that a lane
  # name is compared case-insensitively wherever a name is looked up, and the
  # OBJECT LOG is one of the places it lists.
  #
  # `mel` IS COMPUTED ONCE IN `BEGIN`, not per line: this stream is every line
  # of every lane's log on the estate.
  state_events | awk -v sep="$US" -v me="$1" '
    function pos(pf, pn) { return pf "\034" sprintf("%09d", pn) }
    BEGIN { FS = sep; mel = tolower(me) }
    $6 ~ /^lane:/ { next }
    tolower($2) == mel {
      if (!($6 in ord)) { ord[$6] = ++n; byn[n] = $6 }
      p = pos($10, $11)
      if (!($6 in mp) || p >= mp[$6]) { mp[$6] = p; utc[$6] = $1; verb[$6] = $3; ref[$6] = $7; pay[$6] = $8 }
    }
    # EVERY OTHER LANE, ITS OWN LAST LINE on each object, by the same file-order
    # rule this lane is read by (R14). The verb is kept, not only the TAKEOVERs,
    # because what decides supersession is whether a TAKEOVER is still the last
    # word of the lane that wrote it — see the END block.
    # KEYED ON THE OTHER LANE LOWER-CASED TOO, and its SPELLING carried beside
    # the key (Amendment 15): two spellings of one taker would otherwise be two
    # takers, and the one whose last line is a stale CLAIMED could hide the
    # other-s TAKEOVER. `on[]` keeps the spelling of the line that won the
    # position test, so what is PRINTED is still a name somebody wrote.
    tolower($2) != mel {
      q = pos($10, $11); okey = $6 SUBSEP tolower($2)
      if (!(okey in op) || q >= op[okey]) { op[okey] = q; ov[okey] = $3; ou[okey] = $1; on[okey] = $2 }
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
            split(kk, aa, SUBSEP); oo = aa[1]; ll = on[kk]
            if (!(oo in tp) || op[kk] >= tp[oo]) { tp[oo] = op[kk]; tlane[oo] = ll; tutc[oo] = ou[kk] } }
          for (i = 1; i <= n; i++) { o = byn[i]
            supv = ((o in tlane) && (verb[o] == "CLAIMED" || verb[o] == "TAKEOVER" || verb[o] == "OPENED" || verb[o] == "LANDING" || verb[o] == "WITHDRAWN"))
            sup = supv ? tlane[o] "@" tutc[o] : ""
            printf "%s%c%s%c%s%c%s%c%s\n", utc[o], 31, verb[o], 31, o, 31, (ref[o] ? ref[o] " " pay[o] : ""), 31, sup } }'
}

# The lane and UTC of a TAKEOVER on <object> that is STILL THAT LANE'S OWN LAST
# LINE on it — printed only when $3, our own last verb on the object, is one of
# the OPEN VERBS a takeover can displace: CLAIMED (decision 8(e)'s ordinary
# stale-claim shape), or TAKEOVER, OPENED, LANDING or WITHDRAWN (issue #30's
# dead-lane exception, `superseded_by`'s own case below). Empty when there is
# none. STALE UNTIL PR #61 (Copilot round 8): this line said "the CLAIMED a
# takeover displaces", singular, after the awk fragment just above it had
# already grown the full set — the code was never wrong, only this prose.
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
  # ANY OPEN VERB, NOT ONLY CLAIMED (Copilot round 7, PR #61, issue #30): a
  # dead lane's TAKEOVER — decision 8(e)'s stale-CLAIMED case is still the
  # common one, but opensoft/openRepoTools#30 added a dead-lane TAKEOVER that
  # displaces an OPENED, LANDING, WITHDRAWN or an earlier TAKEOVER too, exactly
  # the verbs `is_open_verb` already lists. Gating this early return on
  # `= CLAIMED` alone left every one of those un-superseded: `holders_of`
  # counted the dead lane's own OPENED as a live hold beside the taker's
  # TAKEOVER, and `who` reported two holders of one object — the very
  # collision #30 exists to end.
  case "${3-}" in
    CLAIMED|TAKEOVER|OPENED|LANDING|WITHDRAWN) : ;;
    *) return 0 ;;
  esac
  # AMENDMENT 15 — `tolower` ON BOTH SIDES, exactly as `lane_objects` above
  # reads the same stream: the lane field of a log line carries the spelling
  # that was typed on the day, and one lane's two spellings are one lane. The
  # NAME is still the one the winning line carried, because this is printed.
  state_events | awk -v sep="$US" -v o="$1" -v me="$2" '
    function pos(pf, pn) { return pf "\034" sprintf("%09d", pn) }
    BEGIN { FS = sep; mel = tolower(me) }
    $6 == o && tolower($2) != mel { p = pos($10, $11); ll = tolower($2)
      if (!(ll in q) || p >= q[ll]) { q[ll] = p; v[ll] = $3; u[ll] = $1; nm[ll] = $2 } }
    END { for (l in q) if (v[l] == "TAKEOVER" && (!seen || q[l] >= b)) { seen = 1; b = q[l]; bl = nm[l]; bu = u[l] }
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

# `date -u -d <stamp>` IS GNU-ONLY, AND THIS FUNCTION IS WHAT STALENESS IS MADE
# OF (A9 Addendum 4, R-A9-11). BSD `date` — macOS's — answers `illegal option
# -- d`, and `2>/dev/null || printf ''` turned that refusal into an EMPTY
# ANSWER rather than an error: `age_of` printed `age unknown` beside every row,
# `older_than_minutes` and `older_than_threshold` returned false for every
# stamp, and the whole of `who`'s idle and stale reporting was silently off on
# a platform this repository's own CI runs. BSD spells the same question
# `-j -f <format> <stamp>`, so both are asked, GNU first because it is what
# every lane workstation runs. TWO FORMATS, because this estate writes two:
# `utc_now`, `lane-end`'s RELEASED and every log line carry SECONDS, and a
# row's `Started` cell carries MINUTES. GNU reads either from one call; BSD
# must be told which, so it is asked twice. A stamp none of the three can read
# is still the empty string every caller here already tests for.
epoch_of() {
  date -u -d "$1" +%s 2>/dev/null ||
    date -u -j -f '%Y-%m-%dT%H:%M:%SZ' "$1" +%s 2>/dev/null ||
    date -u -j -f '%Y-%m-%dT%H:%MZ' "$1" +%s 2>/dev/null ||
    printf ''
}

# `age_of <utc> [<now, epoch seconds>]`. A CALLER WITH MANY STAMPS PASSES `now`
# ONCE (A11 Addendum 4 ruling 12): `date -u +%s` is a process, and asking the
# clock again for every row of a listing both costs one and lets the rows
# disagree about when "now" was.
age_of() {
  ao_t="$(epoch_of "$1")"
  if [ -z "$ao_t" ]; then printf 'age unknown'; return 0; fi
  ao_now="${2-}"; [ -n "$ao_now" ] || ao_now="$(date -u +%s)"
  ao_d=$(( ao_now - ao_t )); [ "$ao_d" -lt 0 ] && ao_d=0
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
    tolower($2) == tolower(l) && $3 == "OPENED" && $10 == f && ($11 + 0) > (ln + 0) {
      # the `←` payload is space-separated issue keys
      n = split($8, a, " ")
      for (i = 1; i <= n; i++) if (a[i] == o) { found = 1 }
    }
    END { exit(found ? 1 : 0) }'
}

# ------------------------------------------- issue #30: A DEAD LANE'S HOLD
#
# `claim_is_stale` answers Rule 1's own question — is THIS CLAIM old — and on
# purpose it refuses for anything that is not a CLAIMED issue: Rule 6 governs a
# PR's own thirty minutes, and an OPENED, LANDING or WITHDRAWN was never a
# claim to begin with. Neither test answers a DIFFERENT question Rule 1 never
# had a word for: the LANE holding the object is not coming back at all,
# whatever verb its last line on the object used. Measured 2026-09-13
# (opensoft/openRepoTools#30): lane openRepoProject-1 went silent and was
# retired (`lane-end --retire`, Amendment 6(d)), leaving an OPENED PR and two
# CLAIMED issues behind — `claim --force` refused all three, the verb-check
# refusing the PR and the four-hour clock refusing the issues (a CLAIMED lane
# that later OPENED a PR naming it is deliberately never stale by Rule 1's own
# test, which is exactly backwards for a lane that is dead). The workaround
# was a `release` on the dead lane's behalf, by hand, object by object.
#
# DEAD, HERE, MEANS THE REGISTER SAYS SO, FIRST: the holder's own object log's
# last LANE-KIND line (Amendment 7(b)'s STARTED/PAUSED/RESUMED/ENDED/RETIRED —
# `lane_row_facts`' own "last lane-kind line wins in file order" rule, R14,
# read for one lane rather than for a whole listing) is ENDED or RETIRED.
# PAUSED IS DELIBERATELY NOT DEAD — a swap is a planned, expected stop
# (Amendment 8) and stealing a swapped lane's claims would be exactly the
# collision this protocol exists to prevent — and neither is a log with no
# lane-kind line yet, which cannot hold an object through this path at all
# (`state_events` reads nothing for it either).
#
# AND CONFIRMED, NEVER ASSUMED, SECOND: a register that says RETIRED is not
# proof by itself that nothing is still running under that name — Amendment
# 6(d)'s retire act writes no signal and kills no process, and
# opensoft/openRepoTools#39 is exactly a register saying one thing while a
# duplicate process says another. So the verdict is checked against
# `live_holder` — the ONE liveness implementation this file has, over the same
# published-union-local id set `lanes-edit.sh live-holder` already builds, and
# never a new one — and a lane a live record on THIS workstation still holds is
# refused exactly as an untaken CLAIMED is: "refuse where the holder is live"
# is not a special case here, it is this same rule. A `live_holder` read that
# FAILS is not "confirmed live" (fail closed for the log half, as every other
# reader of this stream does) — but a RETIRED verdict this workstation simply
# cannot check against any records at all is not held back either, or issue
# #30 would stay exactly as unfixed as it is today for the one case it is
# about: only an ACTUAL live record (rc 0) withholds the takeover.
#
# 0 dead-and-confirmed (`HOLDER_DEAD_VERB` names the verdict), 1 not — refuse
# as before.
#
# A LINE WHOSE PAYLOAD OPENS `fork ` IS NEVER THE LANE'S OWN VERB (Copilot
# round 8, PR #61) — the same exclusion `lane_row_facts` already makes (above,
# "A FORK-S RETIRED IS NOT THE LANE-S OWN LAST VERB") and for the identical
# reason: the first build of ruling 8's retire act appended `RETIRED … lane:
# <lane> -> fork <sid>; pid <n>; kind <k>` to the LANE's own log for a FORK it
# retired, and nothing writes one any more but these logs are append-only, so
# one written under that build is still there. Read as this lane's own last
# line, it says the LANE was retired — backwards for a lane that may be alive
# beside the fork it disowned, and exactly the state a PAUSED (swapped) lane
# would be in if a stray line like this landed after its own last STARTED or
# RESUMED: `claim --force` would read it as ENDED and take over holds a
# planned, expected stop was never meant to surrender — the very collision
# Amendment 8 exists to prevent.
HOLDER_DEAD_VERB=""
holder_is_dead() {   # <lane>
  hid_l="${1-}"; [ -n "$hid_l" ] || return 1
  HOLDER_DEAD_VERB=""
  hid_rc=0
  hid_verb="$(lane_log_events "$hid_l" 2>/dev/null | awk -F"$US" '
    ($3=="STARTED"||$3=="PAUSED"||$3=="RESUMED"||$3=="ENDED"||$3=="RETIRED") && substr($8,1,5)!="fork " { v=$3 }
    END { print v }')" || hid_rc=$?
  [ "$hid_rc" = 0 ] || return 1
  case "$hid_verb" in
    ENDED|RETIRED) : ;;
    *) return 1 ;;
  esac
  hid_ids="$( { session_ids_of_lane "$hid_l" 2>/dev/null || :
                session_ids_local_of_lane "$hid_l" 2>/dev/null || :; } | awk 'NF && !seen[$0]++')"
  # THREE ANSWERS, NEVER TWO CONFLATED (Copilot round 1, opensoft/openRepoTools#61):
  # `live_holder` is 0 live, 8 read-and-confirmed-nothing, or any other code a
  # records tree this workstation could not read at all — and THAT is not
  # "confirmed dead" either, it is "not established", exactly as every other
  # caller of this one liveness implementation already treats it. Only 8 may
  # pass; 0 and every failure both refuse.
  live_holder "$hid_l" "$hid_ids" >/dev/null 2>&1; hid_lrc=$?
  [ "$hid_lrc" = 8 ] || return 1
  HOLDER_DEAD_VERB="$hid_verb"
  return 0
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
    SESSION_FILES_ERR="$(LC_ALL=C tr '\n' ';' < "$sf_err" | LC_ALL=C cut -c1-300)"
    sf_rc=1
  fi
  rm -f -- "$sf_err"
  return "$sf_rc"
}

jstr() { printf '%s' "$1" | grep -o "\"$2\":\"[^\"]*\"" | head -n1 | sed 's/^.*":"//; s/"$//'; }
jnum() { printf '%s' "$1" | grep -o "\"$2\":[0-9][0-9]*" | head -n1 | sed 's/^.*://'; }

# ------------------------------------------------- A11 Addendum 4 ruling 12:
# ONE PASS OVER THE SESSION RECORDS, FOR THE WHOLE PROCESS
#
# *"Decision 6's `lanes` gets a stated bar — it answers in about a second on
# this estate — and the per-lane fan-out is what changes to meet it."*
#
# WHERE THE TIME WENT, measured on a copy of the live register (46 rows, 15
# logs) before any of this was written: `lanes` took 14 m 30 s wall and ~23
# CPU-minutes. Not the register, and not the logs — a `git show` of the 1.1 MB
# register is 11 ms and the fifteen logs are one cached pass. It was THIS: 564
# session records on this workstation, each read with `cat` and then four or
# five `jstr`/`jnum` calls that are FOUR PROCESSES EACH (`printf | grep | head |
# sed`) — about twenty processes per record, eleven thousand per scan — and both
# scans were rebuilt FOR EVERY LANE, because `live_session_ids` and `fork_map`
# cached into a VARIABLE and every caller invoked them inside `$( … )`, which is
# a subshell whose variables die with it.
#
# So: the parse becomes ONE awk over every record file, and the caches become
# FILES, which a subshell's build leaves behind for its parent.
#
# `jstr` and `jnum` ARE REPRODUCED HERE RATHER THAN CALLED, and the reproduction
# is exact: `jstr` is the first `"key":"…"` whose value holds no `"`, `jnum` the
# first `"key":` followed immediately by a digit. Both are `grep -o … | head -n1`
# on the whole blob, so both take the FIRST occurrence and neither is anchored.
# A record is read the same way by either path, and `record_is_live` still makes
# the liveness decision in shell, on the fields this hands it.
SESSION_RECORD_AWK='
function jstr(s, k,   r, i, v) {
  r = "\"" k "\":\""
  i = index(s, r); if (i == 0) return ""
  v = substr(s, i + length(r))
  i = index(v, "\""); if (i == 0) return ""
  return substr(v, 1, i - 1)
}
function jnum(s, k,   r, i, v, rest) {
  r = "\"" k "\":"
  rest = s
  while ((i = index(rest, r)) > 0) {
    v = substr(rest, i + length(r))
    if (v ~ /^[0-9]/) { match(v, /^[0-9]+/); return substr(v, 1, RLENGTH) }
    rest = substr(rest, i + length(r))
  }
  return ""
}
function emit(   ) {
  if (f == "") return
  printf "%s%s%s%s%s%s%s%s%s%s%s%s%s%s%s%s%s\n", f, sep,
    jstr(blob, "sessionId"), sep, jstr(blob, "tmux"), sep, jstr(blob, "name"), sep,
    jnum(blob, "pid"), sep, jstr(blob, "kind"), sep, jstr(blob, "cwd"), sep,
    jstr(blob, "status"), sep, jstr(blob, "procStart")
}
FNR == 1 { emit(); f = FILENAME; blob = "" }
{ blob = blob $0 }
END { emit() }'

# A PER-PROCESS FILE CACHE. `$( … )` is a subshell, so a variable set by a
# builder called inside one is gone the moment it answers; a file is not.
# Named beside the events cache so `cleanup`'s `rm -f -- "$SE_CACHE_FILE".*`
# already takes them, and cleared by `log_sync` with everything else it moves.
#
# SPELLED AS A PARAMETER EXPANSION AND NOT A FUNCTION, because a function called
# as `$(cache_path register)` is a FORK — and this is reached on the per-lane
# path the ruling exists to take the forks out of. `${SE_CACHE_FILE:+…}` is the
# shell's own, costs nothing, and yields the empty string where there is no
# cache file at all, which is the one case every caller already tests for.

# Every session record on this workstation, parsed once:
#   <file><US><sessionId><US><tmux><US><name><US><pid><US><kind><US><cwd><US><status><US><procStart>
session_records() {
  sr_c="${SE_CACHE_FILE:+$SE_CACHE_FILE.records}"
  if [ -n "$sr_c" ] && [ -f "$sr_c" ]; then cat -- "$sr_c"; return 0; fi
  # AND A TREE THAT COULD NOT BE READ IS NOT A WORKSTATION WITH NO SESSIONS
  # (#26, the review of `37632b1`, `lanes-edit.sh:2008`). `session_files` sets
  # `SESSION_FILES_ERR` and returns 1 for exactly that case — the three callers
  # that read it DIRECTLY refuse on it, and say so where they do — and this one
  # read it through `|| :` inside a `$( )`, which discards the status and the
  # message with the subshell. The empty answer was then CACHED for the life of
  # the process, so every consumer after it was told the same untrue thing. The
  # status decides here and NOTHING IS WRITTEN to the cache on it: a cache of a
  # failure is a failure nobody can see.
  sr_files=""; sr_frc=0
  sr_files="$(session_files 2>/dev/null)" || sr_frc=$?
  [ "$sr_frc" = 0 ] || return 1
  sr_t=""
  [ -n "$sr_c" ] && sr_t="$sr_c.${BASHPID:-$$}"
  if [ -z "$sr_files" ]; then
    [ -n "$sr_t" ] && { : > "$sr_t"; mv -f -- "$sr_t" "$sr_c" 2>/dev/null || rm -f -- "$sr_t"; }
    return 0
  fi
  # One awk, however many files — `awk` takes them all on its command line and
  # `FILENAME` keeps each record attributable. The same shape `log_events` uses
  # for the lane logs, for the same reason.
  sr_arr=()
  while IFS= read -r sr_f; do [ -n "$sr_f" ] && sr_arr+=("$sr_f"); done <<EOF
$sr_files
EOF
  if [ "${#sr_arr[@]}" -eq 0 ]; then
    [ -n "$sr_t" ] && { : > "$sr_t"; mv -f -- "$sr_t" "$sr_c" 2>/dev/null || rm -f -- "$sr_t"; }
    return 0
  fi
  if [ -n "$sr_t" ]; then
    awk -v sep="$US" "$SESSION_RECORD_AWK" "${sr_arr[@]}" > "$sr_t" 2>/dev/null
    mv -f -- "$sr_t" "$sr_c" 2>/dev/null || { cat -- "$sr_t"; rm -f -- "$sr_t"; return 0; }
    cat -- "$sr_c"
  else
    awk -v sep="$US" "$SESSION_RECORD_AWK" "${sr_arr[@]}" 2>/dev/null
  fi
  return 0
}

pid_alive() {
  local pid="$1" want="$2" statline rest
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  [ -n "$want" ] || return 0
  [ -r "/proc/$pid/stat" ] || return 0
  # `read` AND NOT `$(cat …)`, WHICH IS A FORK PER RECORD (A11 Addendum 4
  # ruling 12). This runs once for every session record on the workstation —
  # 564 of them here — and `lanes` asked about every record for every lane, so
  # this one substitution was ~26,000 processes for one listing. A builtin read
  # of a one-line file is the same answer.
  statline=""
  read -r statline < "/proc/$pid/stat" 2>/dev/null || statline=""
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

# The three tests every record answers, wherever it was found: a status that is
# not one of {ended, exited, dead, stopped}, a pid that is alive, and a
# `/proc/<pid>/stat` field 22 still equal to the `procStart` the record wrote
# down — so a recycled pid cannot hold a name. `live_holder` adds the two that
# are about a LANE (the row's ids, and the nameSource rule); `window_session`
# adds the one that is about a WINDOW. One copy of the three, because two would
# drift and this is the check that decides whether a name may be taken.
record_is_live() {   # <the record's JSON blob>
  record_fields_are_live "$(jstr "$1" status)" "$(jnum "$1" pid)" "$(jstr "$1" procStart)"
}
# THE SAME THREE TESTS, ON FIELDS ALREADY IN HAND (ruling 12). `session_records`
# parses every record once; re-serialising its fields back into a blob so this
# could re-parse them would be the fork storm the one pass exists to remove.
# ONE copy of the three tests, because two would drift and this is the check
# that decides whether a name may be taken.
record_fields_are_live() {   # <status> <pid> <procStart>
  case "${1-}" in ended|exited|dead|stopped) return 1 ;; esac
  pid_alive "${2-}" "${3-}"
}

# ------------------------------------- AMENDMENT 8, ruling (g): WHOSE session
#
# Three facts about this estate's records, every one of them observed on
# 2026-09-12 while `lane-start` was refusing the very window that held the lane:
#
#   1. THE HARNESS EXPORTS `CLAUDE_CODE_SESSION_ID` into every shell a session
#      runs — so a `lane-start` that a session runs already knows its own
#      transcript id without asking the filesystem anything. That is the
#      cheapest and the most certain test there is, and it comes first.
#   2. ONE SESSION WRITES MORE THAN ONE RECORD. Beside the interactive process
#      in the pane the harness runs a companion: `kind: bg`, no `tmux`, no
#      `nameSource`, its own pid, and THE SAME `sessionId`. Records that share a
#      `sessionId` are one session, not a queue of rival holders, and there is
#      no contest between them to win.
#   3. A RECORD MAY CARRY NO `tmux` AT ALL. The pane's interactive record
#      usually has one, the companion never does, and the harness has been seen
#      to write none for a process plainly in a window. "No target" is not "no
#      window": it is a missing observation, and the process tree holds the
#      answer the record failed to write down.
#
# What those three produced: `live_holder` returned the COMPANION — its
# `sessionId` matched the row, its pid was alive, and carrying no `nameSource`
# it survived the name test — reported its target as `none`, and `lane-start`
# read "not this window" and refused the session that was running the command:
#
#   lane openRepoProject-1 is live in session c5701b54… (tmux none);
#   take openRepoProject-2 or resume that window
#
# The orphaned idle holder from the PREVIOUS profile was a real find and was
# correctly retired under Amendment 6(d); this one was the same shape read
# wrongly. The difference between them is not recency and never was — it is
# whether the process is in THIS pane's tree.

# A `kind: bg` record is a COMPANION: never a holder, never a rival, skipped by
# every read that asks who holds a lane or what is in a window. Only
# `interactive` records hold a lane; a record from a harness too old to say
# carries no `kind` at all and is read as interactive, because that is the only
# thing those harnesses ever wrote.
record_is_session() {   # <the record's JSON blob>
  record_fields_are_session "$(jstr "$1" kind)"
}
record_fields_are_session() {   # <kind>
  case "${1-}" in
    ''|interactive) return 0 ;;
    *) return 1 ;;
  esac
}

# THIS shell's own window and pane, asked of tmux and never guessed. Both are
# empty outside tmux, and an empty answer makes every test below fail SHUT — so
# a caller with no tmux behaves exactly as it did before Amendment 8. Cached
# because `who` asks about every lane in the register and this is two forks.
LANES_HERE_CTX=0
LANES_THIS_WINDOW=""
LANES_PANE_PID=""
here_context() {
  [ "$LANES_HERE_CTX" = 1 ] && return 0
  LANES_HERE_CTX=1
  [ -n "${TMUX:-}" ] || return 0
  command -v tmux >/dev/null 2>&1 || return 0
  LANES_THIS_WINDOW="$(tmux display-message -p '#{session_name}:#{window_id}' 2>/dev/null || :)"
  LANES_PANE_PID="$(tmux display-message -p '#{pane_pid}' 2>/dev/null || :)"
  case "$LANES_PANE_PID" in *[!0-9]*) LANES_PANE_PID="" ;; esac
  return 0
}

# pid_under <pid> <ancestor> — is <pid> the ancestor itself, or below it?
#
# `/proc/<pid>/stat` is `<pid> (<comm>) <state> <ppid> …`, and a comm may hold
# spaces and brackets, so the parse starts after the LAST `) ` — the same cut
# `pid_alive` makes for field 22. The walk stops at pid 1, at an entry it cannot
# read (a process it cannot see is not in this pane), and at 64 steps, so a
# /proc that lies about parentage cannot spin it.
pid_under() {   # <pid> <ancestor>
  pu_p="${1-}"; pu_anc="${2-}"; pu_i=0
  [ -n "$pu_p" ] && [ -n "$pu_anc" ] || return 1
  case "$pu_anc" in *[!0-9]*) return 1 ;; esac
  while [ "$pu_i" -lt 64 ]; do
    case "$pu_p" in ''|*[!0-9]*) return 1 ;; esac
    [ "$pu_p" = "$pu_anc" ] && return 0
    [ "$pu_p" -gt 1 ] 2>/dev/null || return 1
    [ -r "/proc/$pu_p/stat" ] || return 1
    pu_rest="$(cat "/proc/$pu_p/stat" 2>/dev/null || :)"
    [ -n "$pu_rest" ] || return 1
    pu_rest="${pu_rest##*) }"
    pu_p="$(printf '%s' "$pu_rest" | cut -d' ' -f2)"
    pu_i=$((pu_i + 1))
  done
  return 1
}

# record_is_here <blob> — is this record THIS window's own session? The ruling's
# order, cheapest and most certain first:
#   1. its `sessionId` is the one the harness exported into this very shell;
#   2. its `tmux` target names this window — the FAST PATH, and only a fast
#      path: a record without one is not thereby somewhere else;
#   3. its pid is this pane's process, or below it.
record_is_here() {   # <the record's JSON blob>
  here_context
  rih_sid="$(jstr "$1" sessionId)"
  if [ -n "${CLAUDE_CODE_SESSION_ID:-}" ] && [ -n "$rih_sid" ] \
     && [ "$rih_sid" = "$CLAUDE_CODE_SESSION_ID" ]; then return 0; fi
  rih_t="$(jstr "$1" tmux)"
  if [ -n "$rih_t" ] && [ -n "$LANES_THIS_WINDOW" ] \
     && [ "${rih_t%.*}" = "$LANES_THIS_WINDOW" ]; then return 0; fi
  pid_under "$(jnum "$1" pid)" "$LANES_PANE_PID"
}

# live_holder <lane> [<newline-separated session ids>]
#
# R22 — IT FAILS CLOSED AT THE SOURCE. Three answers, and they are distinct:
#   0  a live record holds the lane (the row is printed)
#   8  the records were READ, and none of them does
#   1  the records could not be read — a permissions or IO fault
#
# AND ON 0 IT SAYS WHOSE (Amendment 8, ruling (g)). The fifth field is the
# verdict — `here`, `elsewhere` or `orphan` — because the caller that has to act
# on it cannot work it out from the `tmux` column: a record with no target is
# not a record in no window, and `lane-start` refusing on that string is what
# refused this lane its own window. `here` beats `elsewhere` beats `orphan`, and
# a record with no target whose SESSION also wrote a windowed record is that
# same session seen twice, not a second holder — it is dropped, never ranked.
# `lane-start` renames a window on 8 and REFUSES on anything else, so collapsing
# a failed read into 8 is exactly how a running lane loses its address: the
# rename mints `<lane> (2)` (AGENTS.md rule 7). The first version returned 1 for
# both, which is the same fault one layer up; hardening the CALLER left this
# source with no way to say "I could not read".
live_holder() {
  local lane="$1" ids="${2-}" pats=() f blob pid name status target sid base src
  local lh_files lh_match lh_err kindv verdict c c_sid c_tgt c_name c_pid c_v
  local lh_bg="" lh_windowed="" lh_here="" lh_here_tgt="" lh_else="" lh_orph=""
  local cands=()
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
  # `xargs -r` IS GNU-ONLY and was dead weight: the `[ ! -s ]` guard above
  # returns before this line when there is no record to search at all, which
  # is the only thing `-r` would have caught (A9 Addendum 4, R-A9-11). The
  # `tr`s read arbitrary bytes — a path, and grep's own words about it — so
  # they read them as bytes: BSD `tr` answers `Illegal byte sequence` for a
  # multibyte character in a UTF-8 locale and prints NOTHING, which would turn
  # a record that cannot be read into a reason nobody can read either.
  LC_ALL=C tr '\n' '\0' < "$lh_files" | xargs -0 grep -l -F "${pats[@]}" > "$lh_match" 2>"$lh_err" || :
  if [ -s "$lh_err" ]; then        # a record that exists and cannot be read
    SESSION_FILES_ERR="$(LC_ALL=C tr '\n' ';' < "$lh_err" | LC_ALL=C cut -c1-300)"
    rm -f -- "$lh_files" "$lh_match" "$lh_err"
    return 1
  fi
  rm -f -- "$lh_files" "$lh_err"
  # PASS 1 — every live record the row's ids match, classified. Not the first
  # one found: the first one found is a directory order, and on 2026-09-12 the
  # directory order put the companion in front of the session at the keyboard.
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    blob="$(cat -- "$f" 2>/dev/null || :)"
    [ -n "$blob" ] || continue
    record_is_live "$blob" || continue
    sid="$(jstr "$blob" sessionId)"
    pid="$(jnum "$blob" pid)"
    name="$(jstr "$blob" name)"
    src="$(jstr "$blob" nameSource)"
    target="$(jstr "$blob" tmux)"
    # A COMPANION IS NOT A HOLDER. It is reported, on stderr, so that a person
    # who is looking at a `(tmux none)` record can see why it was not obeyed.
    if ! record_is_session "$blob"; then
      kindv="$(jstr "$blob" kind)"
      lh_bg="${lh_bg}${lh_bg:+, }pid ${pid:-unknown} (kind ${kindv:-none}, session ${sid:-unknown})"
      continue
    fi
    base="${name% (*)}"
    # `tr`, not `${x,,}`: openRepoTools' CI parses every shipped bash file with
    # macOS' /bin/bash 3.2, where `${x,,}` is a SYNTAX error and not a portable
    # lowercase (.github/workflows/tests.yml — that job names this very
    # construction as its example). Amendment 9's adoption act 3, obligation 4.
    base_lc="$(printf '%s' "$base" | tr '[:upper:]' '[:lower:]')"
    lane_lc="$(printf '%s' "$lane" | tr '[:upper:]' '[:lower:]')"
    if [ -n "$base" ] && [ "$base_lc" != "$lane_lc" ] && name_is_explicit "$src"; then continue; fi
    if record_is_here "$blob"; then verdict=here
    elif [ -n "$target" ];     then verdict=elsewhere
    else                            verdict=orphan
    fi
    [ -n "$target" ] && lh_windowed="${lh_windowed}${sid}
"
    cands+=("$(printf '%s%s%s%s%s%s%s%s%s' "$sid" "$US" "${target:-none}" "$US" "${name:-none}" "$US" "${pid:-unknown}" "$US" "$verdict")")
  done < "$lh_match"
  rm -f -- "$lh_match"
  [ -n "$lh_bg" ] && note "lane $lane: companion records, which are never holders: $lh_bg"

  # PASS 2 — the pick. `here` first, and among two records of one session the
  # WINDOWED one is the better witness of it; then a genuine rival in another
  # window; then an orphan, and only one whose session wrote no windowed record
  # at all, because the other kind is this same session seen twice.
  for c in ${cands[@]+"${cands[@]}"}; do
    IFS="$US" read -r c_sid c_tgt c_name c_pid c_v <<<"$c"
    case "$c_v" in
      here)
        if [ -z "$lh_here" ] || { [ "$lh_here_tgt" = none ] && [ "$c_tgt" != none ]; }; then
          lh_here="$c"; lh_here_tgt="$c_tgt"
        fi ;;
      elsewhere) [ -n "$lh_else" ] || lh_else="$c" ;;
      orphan)
        printf '%s' "$lh_windowed" | grep -qx -F -- "$c_sid" && continue
        [ -n "$lh_orph" ] || lh_orph="$c" ;;
    esac
  done
  if   [ -n "$lh_here" ]; then printf '%s\n' "$lh_here"; return 0
  elif [ -n "$lh_else" ]; then printf '%s\n' "$lh_else"; return 0
  elif [ -n "$lh_orph" ]; then printf '%s\n' "$lh_orph"; return 0
  fi
  return 8
}

# -------------------------------- AMENDMENT 8(f), R-A8-6: the ORPHANED HOLDERS
#
# A row's session cell is a HISTORY, and its EARLIER ids are history rather than
# alternatives — but a live process can still be holding one, which is Amendment
# 6(d)'s orphan and, on this lane, the reason the `/resume` picker offered two
# transcripts of which neither was the lane. `live_holder` answers about the
# lane's holder, one record, picked; this answers about ALL the earlier ids, and
# it answers to be READ.
#
# IT NAMES THEM AND DOES NOTHING ELSE. Retiring is `kill <pid>`, printed by the
# caller and run by a person: ending somebody's process is not a boundary
# script's act — an idle background session is exactly the shape of thing that
# turns out to be somebody's long-running job — and clause (f) rules it the
# operator's, for the same reason clause (a)'s step 3 pushes nobody's work for
# them.
#
# IDLE means a LIVE record (Amendment 6's three tests: a status that is not
# ended, a pid that is alive, a `procStart` that still matches) which is NOT a
# session in a window: a `kind: bg` companion, or a record carrying no `tmux`
# target at all. A live INTERACTIVE record with a window is not an orphan, it is
# a rival, and `live_holder` is the read that answers about those.
#
# One line per record, `<session id><TAB><pid><TAB><kind><TAB><profile>`.
# Exit 0 with rows, 8 with none, 1 where the records could not be read.
idle_holders() {   # <lane>
  ih_lane="${1-}"; ih_ids=""; ih_last=""; ih_earlier=""; ih_out=""
  ih_files=""; ih_match=""; ih_err=""; ih_f=""; ih_blob=""
  ih_sid=""; ih_pid=""; ih_kind=""; ih_tgt=""
  SESSION_FILES_ERR=""
  [ -n "$ih_lane" ] || return 8
  ih_ids="$(session_ids_of_lane "$ih_lane" 2>/dev/null || :)"
  [ -n "$ih_ids" ] || return 8
  ih_last="$(printf '%s\n' "$ih_ids" | tail -n1)"
  ih_earlier="$(printf '%s\n' "$ih_ids" | grep -vx -F -- "$ih_last" || :)"
  [ -n "$ih_earlier" ] || return 8
  ih_files="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-if.XXXXXX" 2>/dev/null || printf '')"
  ih_match="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-im.XXXXXX" 2>/dev/null || printf '')"
  ih_err="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-ie.XXXXXX" 2>/dev/null || printf '')"
  if [ -z "$ih_files" ] || [ -z "$ih_match" ] || [ -z "$ih_err" ]; then
    rm -f -- "$ih_files" "$ih_match" "$ih_err" 2>/dev/null || :
    SESSION_FILES_ERR="could not create a temporary file under ${TMPDIR:-/tmp}"
    return 1
  fi
  if ! session_files > "$ih_files"; then
    rm -f -- "$ih_files" "$ih_match" "$ih_err"
    return 1
  fi
  if [ ! -s "$ih_files" ]; then
    rm -f -- "$ih_files" "$ih_match" "$ih_err"
    return 8
  fi
  ih_pats=()
  for ih_sid in $ih_earlier; do ih_pats+=(-e "\"sessionId\":\"$ih_sid\""); done
  # `xargs -r` and the locale, for the reason `live_holder` gives above.
  LC_ALL=C tr '\n' '\0' < "$ih_files" | xargs -0 grep -l -F "${ih_pats[@]}" > "$ih_match" 2>"$ih_err" || :
  if [ -s "$ih_err" ]; then
    SESSION_FILES_ERR="$(LC_ALL=C tr '\n' ';' < "$ih_err" | LC_ALL=C cut -c1-300)"
    rm -f -- "$ih_files" "$ih_match" "$ih_err"
    return 1
  fi
  rm -f -- "$ih_files" "$ih_err"
  while IFS= read -r ih_f; do
    [ -n "$ih_f" ] || continue
    ih_blob="$(cat -- "$ih_f" 2>/dev/null || :)"
    [ -n "$ih_blob" ] || continue
    record_is_live "$ih_blob" || continue
    ih_sid="$(jstr "$ih_blob" sessionId)"
    ih_tgt="$(jstr "$ih_blob" tmux)"
    ih_kind="$(jstr "$ih_blob" kind)"
    # a session IN a window is not an orphan — it is a rival, and live_holder's
    # question, not this one's.
    if record_is_session "$ih_blob" && [ -n "$ih_tgt" ]; then continue; fi
    ih_pid="$(jnum "$ih_blob" pid)"
    ih_out="${ih_out}${ih_sid}\t${ih_pid:-unknown}\t${ih_kind:-none}\t$(record_profile "$ih_f")
"
  done < "$ih_match"
  rm -f -- "$ih_match"
  [ -n "$ih_out" ] || return 8
  printf '%b' "$ih_out"
  return 0
}

# ---------------------------------------------- the session in a tmux WINDOW
#
# AMENDMENT 8. `live_holder` asks "is any session this ROW names alive"; this
# asks "which live session is in THIS WINDOW", and the two answers differ in
# exactly the case Amendment 8 exists for. The harness mints a new transcript
# uuid without anybody acting — a `/clear` does it (Amendment 6, fact 4), and so
# did the 2026-09-12 usage reset that carried this lane's conversation into
# `4a91f1dc…` while its row still ended on `09dd34d1…`. That id is in no row, so
# `live_holder` cannot see it and answers 8, "this lane is parked", about the
# conversation sitting in the window it was asked about. Keyed on the WINDOW
# instead, the record is found, and `lane-start` appends its uuid to the cell
# before it stamps — which is what makes the next resume land in the right
# conversation.

# The profile a record belongs to, read off its own path — never guessed from
# the environment, because the process asking may be in another profile:
#   ~/.claude-profiles/profiles/<org>/<team>/<profile>/sessions/<pid>.json
#   ~/.claude/sessions/<pid>.json                                 -> default
record_profile() {
  rpf_d="${1%/*}"; rpf_d="${rpf_d%/sessions}"; rpf_n="${rpf_d##*/}"
  case "$rpf_n" in .claude|claude|"") printf 'default\n' ;; *) printf '%s\n' "$rpf_n" ;; esac
}

# window_session <tmux target> — the LIVE record whose own `tmux` field names
# that window. The target is `<tmux session>:<window id>`, which is what
# `tmux display-message -p '#{session_name}:#{window_id}'` prints and what the
# record's `tmux` field carries before its `.%<pane>` suffix.
#
# NO NAME TEST. `live_holder`'s fifth test skips a record explicitly named for
# another lane, because there the question is "does this record hold that lane".
# Here the question is "what is running in this window", and a window holds one
# interactive session whatever it is called: the record's name is REPORTED, so
# the caller can put it in front of a person, and decides nothing.
#
# R22 — three answers, never two of them conflated: 0 with the record, 8 when
# the records were READ and none is in that window, 1 when they could not be
# read at all.
# WHERE SEVERAL LIVE RECORDS NAME ONE WINDOW, IDENTITY DECIDES — NOT RECENCY
# (Amendment 8, ruling (g); this replaces the first version's "the most recently
# updated one wins", which was wrong in the case it was written for).
#
#   tier 3  its `sessionId` is `$CLAUDE_CODE_SESSION_ID`, which the harness
#           exported into this very shell — when the window asked about is this
#           one. Nothing beats a session naming itself.
#   tier 2  its pid is this pane's process or below it — again only for this
#           window. This is what lets a record with NO `tmux` be found: the
#           harness does not always write the target down, and a record without
#           one is not thereby in no window.
#   tier 1  its `tmux` field names the window. The fast path, and the only test
#           available for a window that is not this one.
#
# `updatedAt` breaks a tie WITHIN a tier and nowhere else, so the answer never
# depends on directory order. It cannot be the rule itself: it is a LIVENESS
# HEARTBEAT, and the idle companion beside a working session heartbeats later
# than the session does — in the 2026-09-12 records the companion's `updatedAt`
# was 1789235975177 against the interactive record's 1789235958137, so "the
# newest wins" picks precisely the record that is not in the window. Two records
# of ONE session are not a contest to win at all: the windowed one represents
# the session, and `record_is_session` has already dropped the companion.
window_session() {
  local target="$1" f blob sid tmuxv name pid upd best_upd best_out wsn_files
  local tier best_tier ws_is_self ws_pane
  SESSION_FILES_ERR=""
  [ -n "$target" ] || return 8
  # Tiers 2 and 3 are about THIS pane, so they apply only when the window asked
  # about is the one this process is in. Asked about somebody else's window,
  # this read is exactly the `tmux`-field match it always was.
  here_context
  ws_is_self=0; ws_pane=""
  if [ -n "$LANES_THIS_WINDOW" ] && [ "$LANES_THIS_WINDOW" = "$target" ]; then
    ws_is_self=1; ws_pane="$LANES_PANE_PID"
  fi
  wsn_files="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-ws.XXXXXX" 2>/dev/null || printf '')"
  if [ -z "$wsn_files" ]; then
    SESSION_FILES_ERR="could not create a temporary file under ${TMPDIR:-/tmp}"
    return 1
  fi
  # NOT `$( )`: session_files sets SESSION_FILES_ERR, and a subshell would keep
  # the reason for the failure to itself.
  if ! session_files > "$wsn_files"; then rm -f -- "$wsn_files"; return 1; fi
  best_upd=-1; best_tier=0; best_out=""
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    blob="$(cat -- "$f" 2>/dev/null || :)"
    [ -n "$blob" ] || continue
    record_is_live "$blob" || continue
    # A COMPANION IS NOT WHAT IS IN A WINDOW. `kind: bg` carries the interactive
    # record's own `sessionId`, so admitting it here would let the SAME uuid be
    # found by the wrong process — and would re-open the bug the moment a
    # harness starts writing a target on to companions.
    record_is_session "$blob" || continue
    sid="$(jstr "$blob" sessionId)"
    tmuxv="$(jstr "$blob" tmux)"
    tier=0
    if [ "$ws_is_self" = 1 ] && [ -n "${CLAUDE_CODE_SESSION_ID:-}" ] \
       && [ -n "$sid" ] && [ "$sid" = "$CLAUDE_CODE_SESSION_ID" ]; then
      tier=3
    elif [ -n "$ws_pane" ] && pid_under "$(jnum "$blob" pid)" "$ws_pane"; then
      tier=2
    elif [ -n "$tmuxv" ] && [ "${tmuxv%.*}" = "$target" ]; then
      tier=1
    else
      continue
    fi
    upd="$(jnum "$blob" updatedAt)"
    case "$upd" in ''|*[!0-9]*) upd=0 ;; esac
    if [ "$tier" -lt "$best_tier" ]; then continue; fi
    if [ "$tier" = "$best_tier" ] && [ "$upd" -le "$best_upd" ]; then continue; fi
    best_tier="$tier"; best_upd="$upd"
    name="$(jstr "$blob" name)"
    pid="$(jnum "$blob" pid)"
    best_out="$(printf '%s%s%s%s%s%s%s%s%s' "$sid" "$US" "${tmuxv:-$target}" "$US" "${name:-none}" "$US" "${pid:-unknown}" "$US" "$(record_profile "$f")")"
  done < "$wsn_files"
  rm -f -- "$wsn_files"
  [ -n "$best_out" ] || return 8
  printf '%s\n' "$best_out"
  return 0
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

# AMENDMENT 15 — `tolower` ON BOTH SIDES, like every other lookup of a lane
# name in this file. A caller reaches these two through `canon_lane`, so the
# name arriving here is already the ROW's own spelling; the comparison is
# case-insensitive anyway, because a caller that did not canonicalise must not
# silently read "this lane has no row" about a lane that has one.
ROW_AWK='
  substr($0,1,1) == "|" {
    p1 = index($0, "`"); if (p1 == 0) next
    rest = substr($0, p1 + 1); p2 = index(rest, "`"); if (p2 == 0) next
    if (tolower(substr(rest, 1, p2 - 1)) == tolower(lane)) print
  }'
row_of_lane()       { register_text | awk -v lane="$1" "$ROW_AWK"; }
# The same row as THIS CHECKOUT has it. One caller: the `live-holder`
# subcommand, which unions these ids with the published ones because liveness
# fails CLOSED — an id this checkout knows and `origin/main` does not yet is one
# more reason to refuse a rename, never a reason to allow one (AGENTS.md rule 7).
row_of_lane_local() { awk -v lane="$1" "$ROW_AWK" "$LANES_FILE"; }
row_cell() { printf '%s\n' "$1" | awk -F'|' -v i="$2" '{print $i}'; }

# ====================================================== AMENDMENT 15 =======
#
# THE RESOLVER. **A lane name is compared CASE-INSENSITIVELY wherever a name is
# looked up, and the spelling the register row carries is canonical** — it is
# what the window is named, what the session is named, what the log file is
# called, and what every line and stamp writes. A name typed in another case
# RESOLVES to it and is never written as typed.
#
# Every spelling the PUBLISHED register carries for a name, from
# `origin/<branch>` like every other state read (R19). `lane_named_ci` below is
# the same question asked for one answer and no refusal — it is the hook's read
# and the hook never refuses — so the two are one parse in two shapes rather
# than two rules.
#
# AND A THIRD SHAPE SINCE AMENDMENT 12: the prompt guard asks this one because
# it COUNTS. `canon_lane` below answers a caller that wants a name back and
# refuses two with `note` + 2 in this file's own voice; the guard has to print
# its triple FIRST and then say what is wrong, in its own shape, so it takes the
# spellings from here and makes the refusal itself. One parse, three readings,
# and no second rule about what a lane name is.
rows_named_ci() {   # <typed name>
  register_text | awk -v want="$1" '
    substr($0,1,1) == "|" {
      p1 = index($0, "`"); if (p1 == 0) next
      rest = substr($0, p1 + 1); p2 = index(rest, "`"); if (p2 == 0) next
      t = substr(rest, 1, p2 - 1)
      if (tolower(t) == tolower(want)) print t
    }'
}

# canon_lane <typed> — the name every `<lane>` argument and `$LANES_LANE` is
# read through BEFORE anything is read or written under it.
#
#   exactly one row matches, ignoring case   its OWN spelling
#   no row matches                           the typed spelling, unchanged —
#                                            which is what `add-row` needs, and
#                                            what makes a brand-new lane's
#                                            first act possible at all
#   two or more                              REFUSE (2), naming them all
#
# IT RETURNS AND NEVER EXITS, for `row_line`'s reason: every caller takes it
# with `$( )`, and an `exit` there would leave only the substitution's subshell
# while the caller carried on with an empty lane name. The callers spell it
# `lane="$(canon_lane "$lane")" || exit 2`.
#
# THE REFUSAL IS THE AMENDMENT'S OWN AND IT BELONGS TO EVERY WRITER, not only
# to `lane-start`, which has refused two rows for one name since Amendment 5:
# clause (b) says *"where the register already holds two rows that differ only
# by case, every writer REFUSES, naming both, until they are merged"*. Merging
# them is 15(d)'s act and a person's — the newer row's session id(s) appended to
# the older row's cell, in order, and the newer row removed in the same commit —
# because a tool that merged two rows of history on its own would be choosing
# which lane's record survives.
canon_lane() {   # <typed name>
  cl_want="${1-}"
  [ -n "$cl_want" ] || return 0
  cl_hits="$(rows_named_ci "$cl_want" 2>/dev/null || :)"
  cl_n="$(printf '%s' "$cl_hits" | grep -c . || :)"
  if [ "$cl_n" -gt 1 ]; then
    note "the register has $cl_n rows whose lane names differ only by case for '$cl_want': $(printf '%s' "$cl_hits" | tr '\n' ' ')"
    note "a lane name is ONE name under any case (Amendment 15), so no read and no write under it is unambiguous. Merge them into one row (Amendment 15(d)): append the newer row's session id(s) to the older row's session cell, in order, remove the newer row in the SAME commit, and name both spellings in the commit message."
    return 2
  fi
  if [ "$cl_n" = 1 ]; then printf '%s' "$cl_hits"; else printf '%s' "$cl_want"; fi
  return 0
}

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
# lane's current one (Amendment 6(b): the LAST id in the cell), else NOTHING.
#
# R-A11 (e) — IT NO LONGER SUBSTITUTES THE LITERAL `unknown`. It did, and that
# literal is in the append-only log four times already, in two lanes
# (`lanes/log/codeXfactory-1.md` ×3, `lanes/log/openxfactory-4-opendox-extraction.md`
# ×1 on `origin/main`) — written by `log PAUSED` from a swap skill that had the
# uuid in hand and did not pass it, and by `release`. Amendment 7(b) makes that
# field a transcript uuid and ONLY that. Returning empty hands the decision to
# `write_event`, which refuses the write and names the act that supplies the
# uuid; the four lines already written stay exactly where they are (Amendment
# 7(b) forbids editing them, 7(i)'s cutover rule governs).
session_for() {
  if [ -n "${LANES_SESSION:-}" ]; then printf '%s\n' "$LANES_SESSION"; return 0; fi
  last_session_id_of_lane "$1" 2>/dev/null || :
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
  # R-A11 (e) — THE `session` FIELD IS A TRANSCRIPT UUID AND ONLY THAT, AND THE
  # WRITER ITSELF IS WHERE THAT IS ENFORCED. Amendment 7(b) says so of the
  # grammar; nothing checked it, and the literal `unknown` is in the append-only
  # log four times already, in two lanes — three from `log PAUSED` (a swap skill
  # holding the uuid and not passing it) and one from `release`. The log is
  # append-only, so a line written wrong there is wrong for ever and no later
  # line can correct it. Refused HERE rather than in the `log` arm because the
  # same field is written by `claim` and `release` too, and one of the four came
  # from `release`: this is the writer, so this is the gate.
  #
  # It is the FIRST test in the function, before the lock, before the capture
  # and before the log file is created, so a refusal leaves the checkout exactly
  # as it found it — and it names the act that supplies the uuid rather than the
  # rule it broke, because the caller's next move is that act.
  #
  # This composes with `R-A8-2` rather than repeating it: `R-A8-2` stopped
  # `lane-start` WRITING `unknown` (its title-fallback path defers the line
  # instead); this stops the writer ACCEPTING it, from any caller.
  if ! valid_uuid "$we_uuid"; then
    we_bad="${we_uuid:-<empty>}"
    case "$we_uuid" in
      unknown) we_why="'unknown' is the one value this field must never carry: it is in this append-only log four times already, and no later line can correct any of them" ;;
      session_*) we_why="'$we_bad' is a PR-footer id, which is neither resumable nor liveness-checkable (Amendment 6(b))" ;;
      *) we_why="'$we_bad' is not a transcript uuid" ;;
    esac
    die "an event's session field is the TRANSCRIPT UUID and only that (Amendment 7(b)): $we_why. Nothing was written — not the $we_verb line, not the log file, not a commit. Name the session taking the act: LANES_SESSION=\"\$CLAUDE_CODE_SESSION_ID\" LANES_LANE=$we_lane lanes-edit.sh <subcommand> …   If lane $we_lane has no transcript uuid recorded at all, the act that gives it one is Amendment 6(c)'s session-cell append: run 'lane-start --no-launch <repo> <n>' in the lane's own window first" 2
  fi
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
  # AND A `, ` IN THE PAYLOAD, WHICH IS CLAUSE (c)'S OTHER SEPARATOR AND WAS IN
  # NO WRITER AT ALL. ` — ` divides the verb from the fields and the fields from
  # the free text; `, ` divides THE FIELDS FROM EACH OTHER — `lane <l>, session
  # <u>@<ws>, <utc>, <object>` — and the payload is the tail of that fourth
  # field, so a `, ` inside it reads back as a fifth field and a sixth that no
  # reader knows. `lane-start` fences its `dir`, `window` and `profile` values
  # one at a time (`:689-692`, `:728-731`, `:1574-1578`) and the `/lane-swap`
  # skill now fences the same two; this is the backstop under all of them, in the
  # writer, for the reason this file gives for putting the container guard at the
  # dispatcher: *"nine copies of one rule is how eight of them would come to
  # disagree"*.
  #
  # THE PAYLOAD AND NOT THE FREE TEXT. The free text is everything after the
  # SECOND ` — `, where a parser has already finished splitting fields, so a
  # comma there is ordinary prose and the estate's log is full of it. Refusing it
  # would refuse lines this estate legitimately writes.
  #
  # AND NOT THE `"` EITHER, WHICH IS WHY THIS GUARD IS NARROWER THAN THE ONES
  # ABOVE IT. Clause (c)'s own rule for a path containing a space is to WRITE IT
  # QUOTED — `dir "/checkouts/b/my projects/x"`, which is what makes it one ref
  # under 7(b)'s own grammar. (The amendment spells that example under a home
  # directory; it is spelled with a neutral root here because
  # `test_no_committed_file_names_a_host_absolute_path` refuses a `/home/<name>/`
  # path in any tracked file, and a rule that holds for a real path holds for an
  # example of one.) One ref under
  # 7(b) — so `quote_subfield` puts a `"` into the payload deliberately and a `"`
  # refusal here would refuse the very shape the clause mandates. The `"` belongs
  # in the per-VALUE fences, where it is, and not in the whole-payload one.
  #
  # MEASURED BEFORE IT WAS WRITTEN, against every line this estate has: 111
  # payloads in `opensoft/brett-wip`'s 15 lane logs carry `, ` 0 times and `"` 0
  # times, while 76 carry `; ` — the sub-field separator, which this guard must
  # therefore never touch.
  case "$we_pay" in
    *", "*) die "an event's payload may not contain ', ': that separator is what divides an event line's four fields from each other — 'lane <lane>, session <uuid>@<ws>, <utc>, <object>' — and the payload is the tail of the fourth, so a ', ' inside it reads back as fields the log's own parser cannot account for. The log is append-only and no later line can correct it. Use a semicolon, which is the sub-field separator: '$we_pay'" 2 ;;
  esac
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
  # AMENDMENT 17(b) — the two sub-fields, checked in the writer for the same
  # reason the session field is: from any caller, before the lock, before the
  # log file is created, and on a log no later line can correct.
  pause_subfields_check "$we_pay"
  we_line="$(event_line "$we_verb" "$we_lane" "$we_uuid" "$we_utc" "$we_obj" "$we_ref" "$we_pay" "$we_txt")"
  we_paths=("$(log_path_for "$we_lane")")
  we_r6=""
  case "$we_verb" in
    LANDING|LANDED) we_r6="$(rule6_line "$we_verb" "$we_lane" "$we_uuid" "$we_utc" "$we_obj" "$we_pay" 2>/dev/null || :)" ;;
  esac
  [ -n "$we_r6" ] && we_paths+=("$LANES_PATH")
  # THE EXEMPTION IS THE PATH THE LOG IS ACTUALLY AT, WHICH NEED NOT BE THE
  # CANONICAL ONE YET (Amendment 15; Copilot round 4 on openRepoTools#41).
  # `$we_lane` is the ROW's spelling by the time it reaches here, while the file
  # may still carry the spelling it was written under until THIS write renames
  # it — so a lane with uncommitted lines in its own old-cased log met the test
  # that exists to refuse somebody ELSE's uncommitted work, and could not write
  # at all. Only the two exemptions take it: `we_paths` is what the capture and
  # the commit are given and stays exactly what it was, with the old path joining
  # it below as `LOG_RENAMED_FROM` once the rename has actually happened.
  we_lp="$(log_path_ci "$we_lane")" || die "lane $we_lane's object log is published twice (above), and one lane is ONE lane under any case: its log is ONE file (Amendment 15). Merge them by hand (Amendment 15(d)) and re-run. Nothing was written." 2
  # R11 — the register is EXEMPT from this first test, because it is captured
  # below rather than refused. Everything ELSE this checkout has dirty is
  # refused HERE: before the lock, before the capture and before anything is
  # created, so that a refusal leaves the checkout exactly as it found it.
  refuse_dirty_checkout "write $we_verb" "${we_paths[@]}" "$we_lp" "$LANES_PATH"
  acquire_lock
  capture_register_edit "${we_paths[@]}"
  handle_preexisting "${we_paths[@]}"
  # AMENDMENT 15 — `ensure_log` IS BELOW THE CAPTURE AND NOT ABOVE IT, and the
  # order is load-bearing rather than tidy. It may now RENAME the lane's log to
  # the row's own spelling, and the amendment says that rename lands "in that
  # same commit" as the write — while `handle_preexisting` exists to commit
  # whatever it finds dirty in this write's pathspecs FIRST, as somebody else's
  # content. Run above it, the rename was exactly what that capture would
  # commit: the one act of this write, taken out of it and attributed to a peer.
  # Below it, the checkout is clean when the rename happens and the rename is
  # this write's own. The old path joins the pathspecs so the deletion is
  # committed beside the append.
  ensure_log "$we_lane"
  [ -n "$LOG_RENAMED_FROM" ] && we_paths+=("$LOG_RENAMED_FROM")
  # THEN re-test, against the checkout the capture left behind. The capture is
  # not assumed to have worked — handle_preexisting swallows a failed commit by
  # design, it never fails the call — and a register still dirty at this point
  # would send commit_push down Amendment 5(d)'s skip-the-pull branch, which is
  # the branch that disables the rescan deciding a race.
  refuse_dirty_checkout "write $we_verb" "${we_paths[@]}" "$we_lp"
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
  release_lock
  return "$we_rc"
}

# A read fetches first — there is no index, so "current" means "after a fetch".
#
# AND WHERE IT DID NOT FETCH IT RECORDS WHY, so the one caller with a freshness
# line can correct it (#26, the fail-closed family one layer out, `lanes:411`).
# FOUR of the five ways out of here never reach the fetch at all —
# `LANES_NO_GIT=1`, `LANES_NO_FETCH=1`, a `$LANES_REPO` that is not a checkout,
# and an `origin/$LANES_BRANCH` `ls-remote` could not confirm, THE TIMEOUT AMONG
# THEM — and every one of them answered 0 in silence. `lanes --fetch` reads this
# file's stderr for one phrase and prints *"as of a fetch just now"* when it does
# not find it, so all four printed that sentence over a fetch that never ran.
# `43b6320` closed the LOUD path, where the fetch was attempted and failed; this
# is the quiet one.
#
# IT IS RECORDED HERE AND SAID IN THE `lanes` ARM, not printed here, because
# EVERY subcommand in this file runs this function and only the one with a
# `--fetch` flag has a freshness line to be wrong. A note on every path would put
# a paragraph in front of every launch on the workstation to fix a sentence that
# is printed in one place.
LOG_SYNC_FETCH=""      # yes · fell-back · else WHY this run did not fetch
log_sync() {
  # THE CACHE ABOVE IS THE REF AS IT STOOD; a fetch moves the ref, so it is
  # dropped here rather than read past. Both copies of it: the variable this
  # shell holds and the file every subshell reads (ruling 12).
  LANES_REGISTER_CACHE=""
  ls_rc="${SE_CACHE_FILE:+$SE_CACHE_FILE.register}"; [ -n "$ls_rc" ] && rm -f -- "$ls_rc"
  LOG_SYNC_FETCH=""
  [ "$NO_GIT" = 1 ] && { LOG_SYNC_FETCH="LANES_NO_GIT=1 is set, so nothing in this run touches git"; return 0; }
  [ "${LANES_NO_FETCH:-0}" = 1 ] && { LOG_SYNC_FETCH="LANES_NO_FETCH=1 is set in this environment"; note "LANES_NO_FETCH=1 — not fetching; reading origin/$LANES_BRANCH as the ref already stands here"; return 0; }
  git -C "$LANES_REPO" rev-parse --git-dir >/dev/null 2>&1 || { LOG_SYNC_FETCH="$LANES_REPO is not a git checkout"; return 0; }
  if ! remote_has_branch; then
    LOG_SYNC_FETCH="origin/$LANES_BRANCH could not be reached"
    [ "$GIT_TIMED_OUT" = 1 ] && LOG_SYNC_FETCH="$LOG_SYNC_FETCH — ls-remote timed out after ${GIT_TIMEOUT}s"
    return 0
  fi
  if git_net -C "$LANES_REPO" fetch -q origin "$LANES_BRANCH" 2>/dev/null; then
    LOG_SYNC_FETCH=yes
  else
    LOG_SYNC_FETCH=fell-back
    note "fetch $([ "$GIT_TIMED_OUT" = 1 ] && printf 'timed out after %ss' "$GIT_TIMEOUT" || printf 'failed') — reading the logs as they stand locally"
  fi
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
        IFS="$US" read -r ph_hid ph_target ph_hname ph_hpid ph_where <<EOF
$ph_h
EOF
        case "$ph_where" in
          orphan) printf '  holder   lane %s — LIVE but in NO window (session %s, pid %s): an orphaned holder, Amendment 6(d) — retire it: kill %s\n' \
                    "$ph_lane" "$ph_hid" "$ph_hpid" "$ph_hpid" ;;
          here)   printf '  holder   lane %s — LIVE (session %s, pid %s, tmux %s) — this window\n' "$ph_lane" "$ph_hid" "$ph_hpid" "$ph_target" ;;
          *)      printf '  holder   lane %s — LIVE (session %s, pid %s, tmux %s)\n' "$ph_lane" "$ph_hid" "$ph_hpid" "$ph_target" ;;
        esac ;;
      8)
        printf '  holder   lane %s — NOT LIVE (parked: every session its row records has ended)\n' "$ph_lane" ;;
      *)
        printf '  holder   lane %s — UNKNOWN (this workstation'"'"'s session records could not be read; ask @%s or read its handoff)\n' "$ph_lane" "$ph_lane" ;;
    esac
  fi
  # R-A8-6, THE SECOND READER. `lane-start` names the row's orphaned holders to
  # the operator who is about to take the lane; `who` names them to everyone
  # else, because "who holds this" is exactly the question a person asks when a
  # picker has just offered them two transcripts of one lane. The `holder` line
  # above answers about the lane's CURRENT id; this answers about its EARLIER
  # ones, which are history rather than alternatives. It NEVER kills: the act is
  # `kill <pid>`, printed with the session and profile beside it so a person can
  # check first, and run by that person (clause (f)).
  #
  # Silent where there are none, where the lane is on another workstation (its
  # records are not local and this machine must not claim about them), and where
  # the read itself failed — an unreadable record is not an assertion that a
  # holder is absent, and `who`'s own `UNKNOWN` line has already said so.
  if ! lane_is_elsewhere "$ph_lane"; then
    ph_idle="$(idle_holders "$ph_lane" 2>/dev/null)"
    # NOT a pipe: `printf ... | while read; do …; done` runs the loop on the
    # STRIPPED command substitution with no trailing newline, so `read` hits
    # EOF on the (only) line before it ever completes one, returns failure,
    # and the loop body never runs at all — the one-holder case is exactly
    # the common case, and a pipe here would print nothing, ever. A here-string
    # always terminates the last line, which is why `lane-start`'s own reader
    # of this same helper (above) uses one instead of a pipe.
    if [ -n "$ph_idle" ]; then
      while IFS="$(printf '\t')" read -r ph_isid ph_ipid ph_ikind ph_iprof; do
        [ -n "$ph_isid" ] || continue
        printf '  idle     lane %s — an EARLIER session id of this row is still held: session %s, pid %s (kind %s, profile %s). History, not an alternative — retire it: kill %s\n' \
          "$ph_lane" "$ph_isid" "$ph_ipid" "${ph_ikind:-none}" "${ph_iprof:-unknown}" "$ph_ipid"
      done <<<"$ph_idle"
    fi
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
  # DECISION 8(e) — A LIVE FORK IS A DEFECT AND IS NAMED FIRST. It is printed
  # BEFORE the lane's objects and before the pre-cutover return, because a fork
  # is a fact about a lane whether or not that lane has an object log: Evidence
  # 6's fork wrote `RESUMED` and `PAUSED` lines into one that did. `who` names
  # it and does nothing; ending somebody's process is a person's act (Amendment
  # 8(f)).
  # A SURFACE THAT MAY NOT REFUSE SAYS IT COULD NOT LOOK (#26, the review of
  # `37632b1`). `|| :` printed the same nothing for "no fork is live" and for "I
  # could not read this workstation's session records", and those are the two
  # answers ratified decision 8(e) most needs kept apart.
  wl_fk=""; wl_fkrc=0
  wl_fk="$(lane_forks "$wl_lane" 2>/dev/null)" || wl_fkrc=$?
  case "$wl_fkrc" in
    0 | 8) : ;;
    *) printf 'UNKNOWN  this workstation'"'"'s session records could not be read, so whether a live FORK of lane %s'"'"'s transcript is running is NOT established — which is not the same as none. See: lanes-edit.sh forks %s\n' "$wl_lane" "$wl_lane" ;;
  esac
  if [ -n "$wl_fk" ]; then
    while IFS="$(printf '\t')" read -r wl_fid wl_fpid wl_fkind wl_fcwd; do
      [ -n "${wl_fid:-}" ] || continue
      printf 'DEFECT   %s is a live FORK of this lane'"'"'s transcript (pid %s, %s, cwd %s) — never a holder, and it must not write the register. Retire it: lane-end %s --retire %s\n' \
        "$wl_fid" "$wl_fpid" "${wl_fkind:-interactive}" "${wl_fcwd:-unknown}" "$wl_lane" "$wl_fpid"
    done <<EOF
$wl_fk
EOF
  fi
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
# The table is handed in through the ENVIRONMENT, as `LANES_RULE6_ALIASES`,
# one `<lowercased alias>\037<owner/repo>` per line — because awk cannot read
# `repos.tsv` for itself here (this program's stdin is the register) and
# because `awk -v`, which is where it used to go, carries ONE LINE: see
# `who_landing` for what a many-line `-v` does on macOS's awk.
#
# BOTH LAYERS, SHIPPED FIRST (Amendment 9(b)). This is the second reader of the
# table — `alias_lookup` is the other — and it layers them the same way by
# reading the shipped file before the override, so the LAST assignment to an
# alias wins and an override row REPLACES the shipped row for that alias while
# adding rows the shipped table does not carry. One map, emitted in the order
# the aliases were first seen, so the output is stable.
rule6_aliases() {
  r6_files=()
  for r6_tsv in "${LANES_REPOS_TSV_SHIPPED:-}" "${LANES_REPOS_TSV:-}"; do
    [ -n "$r6_tsv" ] && [ -f "$r6_tsv" ] || continue
    r6_files+=("$r6_tsv")
  done
  [ "${#r6_files[@]}" -gt 0 ] || return 0
  awk -F'\t' '
    /^[ \t]*#/ { next }
    NF >= 2 {
      a = $1; b = $2
      gsub(/^[ \t]+|[ \t]+$/, "", a); gsub(/^[ \t]+|[ \t]+$/, "", b)
      if (a != "" && b != "") {
        k = tolower(a)
        if (!(k in seen)) { seen[k] = 1; ord[++n] = k }
        m[k] = b
      }
    }
    END { for (i = 1; i <= n; i++) printf "%s\037%s\n", ord[i], m[ord[i]] }' "${r6_files[@]}"
}

RULE6_AWK='
function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
function canon(r,   l) { l = tolower(r); return (l in A) ? A[l] : r }
BEGIN {
  na = split(ENVIRON["LANES_RULE6_ALIASES"], ar, "\n")
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
  # `awk -v` CARRIES ONE LINE, AND THIS TABLE IS MANY (A9 Addendum 4, R-A9-11,
  # round 5; the `probe` step of run 34782845181 answered it on the runner).
  # A `-v name=value` is processed as if it were a STRING LITERAL, and a string
  # literal cannot span lines: macOS's awk (one-true-awk 20200816) refuses it
  # outright — `awk: newline in string … at source line 1`, exit 2, no output at
  # all — while gawk and mawk accept it silently. So this read, and only this
  # read, answered `none open` for every LANDING in the register on that
  # platform: fourteen of the job's twenty-six remaining failures, and the
  # estate's merge holds invisible on a workstation that runs macOS.
  #
  # `ENVIRON` has no such restriction and is POSIX awk, so the table goes
  # through the environment of this one command. The program is otherwise
  # untouched: the probe ran `RULE6_AWK` itself on that awk with an empty table
  # and it emitted both rows byte-for-byte, and `length`, `match`, `RSTART`,
  # `RLENGTH` and `substr` there all agree with each other on a line carrying
  # an em dash. There was nothing wrong with the parser or with the arithmetic;
  # the table could not get in.
  wd_aliases="$(rule6_aliases)"
  wd_rows="$(register_text | LANES_RULE6_ALIASES="$wd_aliases" awk "$RULE6_AWK")"
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

# ======================================================== Amendment 8 ======
#
# SWAP AND RESTART, THE READ SIDE.
#
#   A SWAP is a planned stop — a usage reset, a profile switch — and a RESTART
#   is the launch that follows it. Neither adds a file. The RECORD a swap
#   leaves is the lane's own PAUSED line, payload
#   `swap; window <tmux session>:<index>; workstation <ws>`, and a lane is
#   SWAPPED on a workstation when that PAUSED is its LAST lane-kind line.
#
#   Both reads here are READ-ONLY and neither ever writes. `swapped` is what a
#   launcher asks when the tmux window name is gone — a restart opens a NEW
#   tmux session, which is precisely why the window name cannot carry the lane
#   across one. `session-start` is the SessionStart hook's whole output.

# The register's own spelling of a lane whose name matches $1 ignoring case,
# read from `origin/<branch>` like every other state read (R19). Rule 10's wire
# form is lowercase and a tmux window may carry either, while the row's token is
# camel (`openRepoProject-1`): an exact lookup alone loses the lane.
lane_named_ci() {
  register_text | awk -v want="$1" '
    substr($0,1,1) == "|" {
      p1 = index($0, "`"); if (p1 == 0) next
      rest = substr($0, p1 + 1); p2 = index(rest, "`"); if (p2 == 0) next
      t = substr(rest, 1, p2 - 1)
      if (tolower(t) == tolower(want)) { print t; exit }
    }'
}

# The lane whose row's SESSION CELL names <uuid> — the second resolution the
# hook has, for a window that carries no lane name. ONLY the session cell is
# read: state cells quote other lanes' ids all the time ("RESUMED by <id>",
# "handed off to <id>"), and one of those is not this session's lane.
lane_of_session() {
  los_id="$(lc "${1-}")"
  [ -n "$los_id" ] || return 1
  register_text | awk -F'|' -v id="$los_id" '
    substr($0,1,1) != "|" { next }
    {
      if (index(tolower($3), id) == 0) next
      p1 = index($2, "`"); if (p1 == 0) next
      rest = substr($2, p1 + 1); p2 = index(rest, "`"); if (p2 == 0) next
      print substr(rest, 1, p2 - 1); exit
    }'
}

# ============================================================================
# AMENDMENT 11 — THE RECORD'S SUB-FIELDS, AND THE READS BUILT ON THEM
# ============================================================================
#
# Amendment 11 clause (c) gives the lane's `STARTED`/`RESUMED` lines and the
# swap record two new payload sub-fields, `dir <path>` and `profile <name>`,
# beside Amendment 8(b)'s `window`, which gains a second ref. Clause (h) turns
# the reads of them into subcommands, for the reason Amendment 7(d) already
# gives `live-holder` and `lane-objects`: EACH READ EXISTS SO THAT SEVERAL
# CALLERS SHARE ONE IMPLEMENTATION. `window-lane` has three (the launcher's
# precedence 3, `/restart`'s step 2(c), the `/lane-swap` skill's step 1);
# `session-lane` has two (`/restart`'s step 2(b) and the SessionStart hook);
# `lane-dir` has four. A rule implemented once cannot be implemented three
# ways, which is exactly how the launcher, the skill and `/restart` would come
# to disagree about which lane a window is.

# ONE PARSER OF A PAYLOAD'S SUB-FIELDS, AND ONE UNQUOTER.
#
# Amendment 7(b)'s grammar: sub-fields are separated by `; `, and SEVERAL REFS
# INSIDE ONE SUB-FIELD ARE SEPARATED BY SPACES — which is what the `window`
# sub-field's `<session>:<index> <@id>` relies on. So an unquoted
# `dir $HOME/my projects/x` (unquoted) parses as two refs and hands back a truncated
# path, and clause (c)'s rule is that the WRITER QUOTES a value containing a
# space and EVERY READER takes a value opening with `"` as running to its
# closing `"`, stripping both.
#
# Two modes, because the grammar has two kinds of value:
#   (default)  ONE REF — the value up to its first space, or the whole of a
#              quoted value. `dir` and `profile` are read this way.
#   all        EVERY REF — the whole sub-field, which is what `window` is:
#              two refs that a caller splits itself.
payload_subfield() {   # <payload> <name> [all]
  awk -v pay="$1" -v want="$2" -v mode="${3-}" '
    BEGIN {
      want = want " "
      n = split(pay, sf, "; ")
      for (i = 1; i <= n; i++) {
        if (substr(sf[i], 1, length(want)) != want) continue
        v = substr(sf[i], length(want) + 1)
        sub(/^[ \t]+/, "", v); sub(/[ \t]+$/, "", v)
        if (substr(v, 1, 1) == "\"") {
          q = index(substr(v, 2), "\"")
          if (q > 0) { print substr(v, 2, q - 1); exit }
        }
        if (mode != "all") { sub(/ .*$/, "", v) }
        print v; exit
      }
    }'
}

# ---------------------------------------- AMENDMENT 17(b): THE TWO SUB-FIELDS
#
# `agent <name>` and `transcript <id|none>`, VALIDATED BY THE WRITER. Amendment
# 17(b) gives the `PAUSED` payload both; nothing else in this file could check
# them, because a payload is free text to `write_event` — and this log is
# APPEND-ONLY, so a sub-field written wrong is wrong for ever and no later line
# corrects it. The check is the same shape `valid_uuid` gives the session field
# under clause (e): the WRITER is the gate, from any caller.
#
# WHAT EACH ADMITS, and why the pattern is the rule rather than a list:
#   agent       A MANIFEST KEY — letters, digits, `.`, `_`, `-`. It is what
#               `lane-start --agent <name>` reads back to choose a launcher, so
#               a value carrying a space or a `;` is a value that would come
#               back as two sub-fields or as an argument nobody meant. The
#               pattern is also how this sub-field gets SPEC rev 6 §5's `; `
#               rule without a token of its own — the same argument clause (c)'s
#               `profile` takes.
#   transcript  THE AGENT'S OWN RESUMABLE ID, or the literal `none` — which is
#               an ANSWER ("this agent has no resumable id") and not a gap.
#               Claude's is a uuid; another agent's is whatever that agent
#               prints, so the shape is the same manifest key rather than
#               `valid_uuid`, which would refuse every agent but one.
#
# A PAYLOAD CARRYING NEITHER IS VALID AND STAYS VALID. Every record written
# before this amendment carries neither, and Amendment 7(i)'s cutover rule is
# that a reader finding none says so rather than assuming one. The check fires
# only on a sub-field that is THERE.
# THE TWO ARE WRITTEN TOGETHER OR NOT AT ALL, AND AN EMPTY ONE IS NOT AN
# ABSENT ONE (Copilot rounds 1 and 2 on openRepoTools#47). The first shape of
# this gate entered on either sub-field and then accepted each empty result
# independently, which let a HALF record through: `agent codex` with no
# transcript, or `transcript <id>` with no agent, both of which `lane-start`
# reads one field of and defaults the other — launching Claude on a codex id,
# or codex on none. And a sub-field written EMPTY (`; agent ; …`) parsed
# identically to one that was never there, so a malformed line was indexed as a
# pre-amendment one for ever, in a log nothing rewrites.
#
# PRESENCE IS READ OFF THE SUB-FIELDS, never off the whole line: `dir
# /srv/agent-work` carries the letters and is not the field.
pause_subfields_check() {   # <payload>
  psc_pay="${1-}"
  case "$psc_pay" in *agent*|*transcript*) : ;; *) return 0 ;; esac
  psc_has_a=0; psc_has_t=0
  psc_rest="$psc_pay"
  while : ; do
    psc_one="${psc_rest%%; *}"
    case "$psc_one" in
      agent | 'agent '*)           psc_has_a=1 ;;
      transcript | 'transcript '*) psc_has_t=1 ;;
    esac
    case "$psc_rest" in
      *'; '*) psc_rest="${psc_rest#*; }" ;;
      *) break ;;
    esac
  done
  # A PAYLOAD CARRYING NEITHER IS VALID AND STAYS VALID: every record written
  # before this amendment carries neither, and Amendment 7(i)'s cutover rule is
  # that a reader finding none says so rather than assuming one.
  if [ "$psc_has_a" = 0 ] && [ "$psc_has_t" = 0 ]; then return 0; fi
  # EACH FIELD THAT IS THERE IS READ WITH `all`, WHICH IS THE WHOLE SUB-FIELD
  # AND NOT ITS FIRST REF. The default mode ends a value at its first space —
  # the rule `dir` and `profile` are read by — so `agent not a key` would come
  # back as `not`, a perfectly good manifest key, and the check would pass the
  # very value it exists to refuse. A gate reads what was written, never what a
  # reader would make of it. THE VALUE IS JUDGED BEFORE THE PAIR, so a payload
  # that is both malformed and half-written is refused for the malformation,
  # which is the thing the writer of it can see in what they typed.
  if [ "$psc_has_a" = 1 ]; then
    psc_a="$(payload_subfield "$psc_pay" agent all)"
    case "$psc_a" in
      '')
        die "the record's \`agent\` sub-field is THERE and EMPTY, which is not the same as absent: no reader can tell it from a pre-amendment record, so every one of them would default to \`claude\` for ever (Amendment 7(i)'s cutover rule is about a field that was never written, not one written blank). Write the agent, or write neither sub-field. Nothing was written" 2 ;;
      *[!A-Za-z0-9._-]*)
        die "the record's \`agent\` sub-field is a manifest key — letters, digits, '.', '_', '-' — and '$psc_a' is not one (Amendment 17(b)). Nothing was written: this log is append-only, and \`lane-start --agent\` launches on what it reads back from this field" 2 ;;
    esac
  fi
  if [ "$psc_has_t" = 1 ]; then
    psc_t="$(payload_subfield "$psc_pay" transcript all)"
    case "$psc_t" in
      '')
        die "the record's \`transcript\` sub-field is THERE and EMPTY. The word for an agent with no resumable id is \`none\`, which is an ANSWER; blank is a gap no reader can tell from a pre-amendment record. Nothing was written" 2 ;;
      *[!A-Za-z0-9._-]*)
        die "the record's \`transcript\` sub-field is the agent's own resumable id, or the word 'none' — '$psc_t' is neither (Amendment 17(b)). Nothing was written" 2 ;;
    esac
  fi
  # AND THE PAIR. `lane-start` reads ONE of these fields to choose a launcher
  # and the OTHER to choose what it hands that launcher, so a record carrying
  # one of them makes it default the other: Claude launched on a codex id, or
  # codex launched on none, out of a line nothing rewrites.
  if [ "$psc_has_a" != "$psc_has_t" ]; then
    psc_only=transcript
    [ "$psc_has_a" = 1 ] && psc_only=agent
    die "Amendment 17(b)'s two sub-fields are written TOGETHER or not at all, and this payload carries only \`$psc_only\`. A half record is worse than none: \`lane-start\` reads the field that is there and DEFAULTS the one that is not, so it would launch the wrong agent, or the right one on an id that is not its. Write both (\`agent <name>; transcript <id|none>\`), or neither. Nothing was written — this log is append-only" 2
  fi
  return 0
}

# The <name> sub-field of the lane's LAST lane-kind line that carries one, IN
# FILE ORDER — which is the order every other state read in this file uses, and
# for the reason `swapped_lanes` states below: a lane's log is append-only and
# single-writer, so a line further down the file is a line written later
# whatever the two UTC fields say.
#
# THE LAST LINE CARRYING ONE, NOT THE LAST LINE. A lane started under Amendment
# 11 and then PAUSED for a reason that is not a swap has a last line with no
# payload at all, and its directory has not stopped being true. Amendment 7(i)'s
# cutover rule is the same shape: a line written before this clause carries
# none, and a reader that finds none SAYS SO rather than assuming one.
# THE SIX FACTS A LISTING ROW NEEDS, FROM ONE PASS OVER ONE LANE'S EVENTS.
# `<verb><US><utc><US><dir><US><profile><US><window><US><home>` on one line.
# It is `payload_subfield`'s two rules and `home_of_lane`'s one, written once in
# awk instead of a dozen forks per lane — and the rules are restated here rather
# than referred to because a reader comparing the two must be able to see both:
#   * the LAST lane-kind line that carries a sub-field wins, in FILE ORDER;
#   * a value opening with `"` runs to its closing `"`, quotes stripped, and any
#     other value ends at its first space — except `window`, which is two
#     space-separated refs in ONE sub-field and is taken whole.
lane_row_facts() {   # events on stdin, ONE LINE PER LANE
  awk -v sep="$US" '
    function field(pay, want, whole,   n, i, sf, v, q) {
      want = want " "
      n = split(pay, sf, "; ")
      for (i = 1; i <= n; i++) {
        if (substr(sf[i], 1, length(want)) != want) continue
        v = substr(sf[i], length(want) + 1)
        sub(/^[ \t]+/, "", v); sub(/[ \t]+$/, "", v)
        if (substr(v, 1, 1) == "\"") {
          q = index(substr(v, 2), "\"")
          if (q > 0) return substr(v, 2, q - 1)
        }
        if (!whole) sub(/ .*$/, "", v)
        return v
      }
      return ""
    }
    function pos(pf2, pn) { return pf2 "\034" sprintf("%09d", pn) }
    BEGIN { FS = sep }
    $3 == "STARTED" || $3 == "PAUSED" || $3 == "RESUMED" || $3 == "ENDED" || $3 == "RETIRED" {
      # AMENDMENT 15 — KEYED ON THE LANE LOWER-CASED, WITH ITS SPELLING BESIDE
      # IT. Every consumer of this table already looks a lane up by its
      # lower-cased name (`lanes_rows`-s `table_lookup`, which reads the FIRST
      # line with that key), and the key used to be the spelling the LINE
      # carried: a log holding both spellings of one lane — which is what
      # `lanes/log/openxfactory-2.md` holds — emitted TWO lines under one key,
      # and the listing took the first and lost the other-s state, dir,
      # profile, window, home and session. `disp` is the first spelling seen,
      # for the second column; `lanes_rows` prints the register-s spelling over
      # it anyway, and this is what a lane with a log and no row shows as.
      l = tolower($2)
      if (!(l in seen)) { seen[l] = ++n; byn[n] = l }
      if (!(l in disp)) disp[l] = $2
      # A FORK-S RETIRED IS NOT THE LANE-S OWN LAST VERB (decision 8(c): a fork
      # is never the lane; A11 Addendum 4 ruling 8). Read as the lane-s own line
      # it would say the LANE was retired — the opposite of what happened, since
      # the lane may well be live beside the fork it disowned. So a line whose
      # payload opens `fork ` is skipped HERE, for the state fields only.
      # NOTHING WRITES ONE ANY MORE, and this comment said otherwise (#26, the
      # review of `29d3417`). The first build of ruling 8-s act appended
      # `RETIRED … lane:<lane> -> fork <sid>; pid <n>; kind <k>`; that line is a
      # seventh edit to in-force text and Amendment 7(b) gives `RETIRED` no
      # payload, so `lane-end --retire` PROVES the fork and prints 6(d) and
      # writes nothing at all (`lane_forks`-s own block argues it in full). The
      # skip stays because these logs are APPEND-ONLY and never rewritten: a log
      # that took one of those lines while that build was live still carries it.
      #
      # R14 IS NOT WEAKENED BY THIS. R14 decides WHICH of a lane-s own lines is
      # last; this decides which lines are the lane-s own. A line about
      # something that is never the lane was never in that set.
      if (substr($8, 1, 5) == "fork ") next
      # FILE ORDER decides which line is a lane-s LAST (R14), exactly as
      # `swapped_candidates` decides it: a lane-s log is append-only and
      # single-writer, so a line further down the file is a line written later
      # whatever the two UTC fields say.
      p = pos($10, $11)
      if (!(l in mp) || p >= mp[l]) { mp[l] = p; verb[l] = $3; utc[l] = $1; ws[l] = $5 }
      v = field($8, "dir", 0);     if (v != "") d[l] = v
      v = field($8, "profile", 0); if (v != "") pf[l] = v
      v = field($8, "window", 1);  if (v != "") w[l] = v
      if ($3 == "STARTED" || $3 == "RESUMED") {
        v = field($8, "home", 0); if (v != "" && v != "unknown") h[l] = v
      }
      # Clause (d) rule 3-s second source, out of the same pass: the session
      # field of the lane-s last PAUSED or RESUMED, which is the resume target
      # where the published cell names none.
      if (($3 == "PAUSED" || $3 == "RESUMED") && $4 ~ /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/) sid[l] = tolower($4)
      next
    }
    # THE OBJECTS EACH LANE HOLDS, from the same pass. A lane HOLDS an object
    # when its own LAST line on that object carries an OPEN verb — Amendment
    # 7(b)-s partition, and the one `lane-end` refuses on.
    #
    # IT CARRIES NO TAKEN-OVER ANNOTATION, AND THAT IS A DELIBERATE NARROWING.
    # `lane_objects` adds one by asking `superseded_by` per object, which is a
    # full pass over this stream per object per lane: on the suite-s own
    # register that turned a listing into eighteen minutes and counting. A
    # listing says WHAT A LANE HOLDS; `who --lane <lane>` is the authority that
    # says whether somebody has taken it over, and the listing points at it.
    $6 !~ /^lane:/ {
      l = tolower($2); k = l "\034" $6          # Amendment 15, as above
      p = pos($10, $11)
      if (!(k in omp) || p >= omp[k]) { omp[k] = p; overb[k] = $3; oobj[k] = $6; olane[k] = l
        if (!(k in okseen)) { okseen[k] = ++okn; okbyn[okn] = k } }
      if (!(l in seen)) { seen[l] = ++n; byn[n] = l }
      if (!(l in disp)) disp[l] = $2
    }
    END {
      for (i = 1; i <= okn; i++) {
        k = okbyn[i]
        if (overb[k] != "CLAIMED" && overb[k] != "TAKEOVER" && overb[k] != "OPENED" && overb[k] != "LANDING" && overb[k] != "WITHDRAWN") continue
        l = olane[k]
        if (l in have) obj[l] = obj[l] "; " overb[k] " " oobj[k]
        else { obj[l] = overb[k] " " oobj[k]; have[l] = 1 }
      }
      for (i = 1; i <= n; i++) {
        l = byn[i]
        # KEYED ON THE LANE LOWER-CASED, like the register index beside it and
        # for the same reason: the listing joins these two tables on the lane
        # name, and this file matches a lane name case-insensitively everywhere
        # else (`lane_named_ci`).
        printf "%s%c%s%c%s%c%s%c%s%c%s%c%s%c%s%c%s%c%s%c%s\n", l, 31, disp[l], 31, verb[l], 31, utc[l], 31, ws[l], 31, d[l], 31, pf[l], 31, w[l], 31, h[l], 31, sid[l], 31, obj[l]
      }
    }'
}

# 0 with the sub-field · 8 the log was read and carries none · 1 THE LOG COULD
# NOT BE READ, which is not the same fact and never was (#26, the fail-closed
# family one layer out, `lanes-edit.sh:3525`).
#
# THE READ WAS INSIDE THE HERE-DOCUMENT THAT FEEDS THE LOOP, and a command
# substitution's status THERE is not carried anywhere — not, as the review had
# it, carried as `awk`'s; it is discarded outright, because a here-document body
# is text and nothing tests it. So a `lane_log_events` that failed arrived as no
# lines at all and left through the `return 8` below, and 8 is the one code every
# caller of this function is entitled to read as *"this lane has not started
# under Amendment 11 yet"* — the pre-cutover answer that sends `restart`,
# `lane-start` and both skills to the rungs beneath a record they never
# established was readable. The read is its own step now and its status decides.
lane_payload_field() {   # <lane> <name> [all]
  lpf_lines=""; lpf_rc=0
  lpf_lines="$(lane_log_events "$1")" || lpf_rc=$?
  [ "$lpf_rc" = 0 ] || return 1
  # The scan is over EVERY lane-kind payload, newest last, and the answer is
  # the last one that actually carries the sub-field.
  lpf_v=""
  while IFS= read -r lpf_p; do
    [ -n "$lpf_p" ] || continue
    lpf_this="$(payload_subfield "$lpf_p" "$2" "${3-}")"
    [ -n "$lpf_this" ] && lpf_v="$lpf_this"
  done <<EOF
$(printf '%s\n' "$lpf_lines" | awk -F"$US" '
    $3 == "STARTED" || $3 == "PAUSED" || $3 == "RESUMED" || $3 == "ENDED" || $3 == "RETIRED" { print $8 }')
EOF
  [ -n "$lpf_v" ] || return 8
  printf '%s\n' "$lpf_v"
}

# --------------------------------------------- clause (h): `window-lane`
#
# WHAT TMUX SAYS ABOUT A REF, NOW. Empty where there is no tmux, no server, or
# no such window — and an empty answer is what makes every match below fail
# SHUT, which is clause (b)'s liveness fence: a record whose window is gone
# names a window somebody else's `:0` may since have been given, and matching a
# dead ref is how a lane binds to a stranger's pane.
tmux_window_field() {   # <ref> <format>
  [ -n "${1-}" ] || return 1
  command -v tmux >/dev/null 2>&1 || return 1
  tmux display-message -p -t "$1" "$2" 2>/dev/null | head -n1
}

# THE LANE BOUND TO A WINDOW OF THE ASKING WORKSTATION (Amendment 11 clause
# (h), `R-A11-8`/RV-T7 for the scoping and `R-A11-8`/RV-T6 for the agreement
# rule). Three callers, ONE implementation:
#
#   * the launcher's precedence 3 (clause (b) row 3),
#   * `/restart`'s step 2(c) (clause (f)),
#   * the `/lane-swap` skill's step 1 (Amendment 8(a) step 1, extended).
#
# TWO RUNGS, first answer wins:
#   1. the window's own NAME, where the register has a row for it. That is
#      clause (b)'s precedence 2 read through the same door, so a caller that
#      asks this read a ref gets the same answer the launcher would.
#   2. this workstation's swap records, matched on the ref.
#
# SCOPED TO THE ASKING WORKSTATION, IN THE CONTRACT AND NOT ONLY IN `Open`. A
# `<session>:<index>` is a local fact about one machine, and `claude-x:0`
# written on Raven collides with `claude-y:0` on Eagle far more easily than an
# `<@id>` will. `swapped` takes `[<ws>]` for exactly that reason and this read
# takes it for the same one: records written by another workstation are NOT
# CONSIDERED.
#
# THE AGREEMENT RULE, AND THIS READ OWNS IT. Existing-now is not enough on its
# own: a record naming `claude-y:0 @97`, met from the window that has since
# taken `claude-y:0` as `@200`, passes the existing-now test on its ref and
# would bind the lane to a stranger's pane with no question — which is the
# failure the liveness fence exists to stop, arriving through the LIVE ref
# instead of the dead one. So:
#
#   a record that carries an `<@id>` is matched on its `<session>:<index>` ONLY
#   WHERE THE WINDOW NOW HOLDING THAT REF REPORTS THAT SAME ID; a record with
#   no id is matched on the ref alone.
#
# It is stated once, here, and not restated in each of the read's three
# callers: three implementations of one rule is how they would come to
# disagree. The launcher PR withdrew its own copy of this clause on the same
# ground.
#
# 0 with the lane, 8 with none, 64 a usage error of its own.
window_lane() {   # <workstation> <ref>
  wl_ws="$(short_ws "${1:-$WS}")"; wl_ref="${2-}"
  [ -n "$wl_ref" ] || return 64
  # A WORKSTATION THAT IS NOT THIS ONE HAS NO WINDOW THIS PROCESS CAN SEE, and
  # the read says so rather than pretending. The window's NAME and the liveness
  # fence are both facts about the tmux server running HERE: asked about Raven,
  # a local `display-message` would answer about an Eagle window that happens to
  # share the ref — which is the collision the scoping exists to stop, made by
  # the fence itself. So a foreign workstation is answered from its RECORDS
  # alone, unfenced, and that is the cross-machine answer Amendment 7's open
  # item is about: this process cannot tell whether Raven's window still exists.
  wl_local=1
  [ "$wl_ws" = "$(short_ws "$WS")" ] || wl_local=0
  if [ "$wl_local" = 1 ]; then
    # RUNG 1 — the window's own name. Read from tmux, so a ref that names no
    # window answers nothing here either.
    wl_name="$(tmux_window_field "$wl_ref" '#{window_name}' 2>/dev/null || :)"
    if [ -n "$wl_name" ]; then
      wl_row="$(lane_named_ci "$wl_name" 2>/dev/null || :)"
      if [ -n "$wl_row" ]; then printf '%s\n' "$wl_row"; return 0; fi
    fi
  fi
  # RUNG 2 — that workstation's swap records. `swapped_candidates` is the one
  # reader of a `PAUSED … swap;` line in this file, so the record's shape is
  # parsed once however many reads are built on it.
  wl_now_id=""
  if [ "$wl_local" = 1 ]; then
    wl_now_id="$(tmux_window_field "$wl_ref" '#{window_id}' 2>/dev/null || :)"
    [ -n "$wl_now_id" ] || return 8        # the ref names no window HERE, now
  fi
  # THE FIELD LIST IS `swapped_candidates`' OWN, IN FULL, and it gains Amendment
  # 17(b)'s two: `read` puts every field it has no variable for into the LAST
  # one, so a short list would have quietly moved the pickaxe key — which is not
  # read here — into `wl_p` and the agent into it too. Named in full, the reader
  # and the writer of this row cannot drift apart.
  while IFS="$US" read -r wl_l wl_u wl_w wl_d wl_p wl_a wl_t wl_key; do
    [ -n "${wl_l:-}" ] || continue
    [ -n "${wl_w:-}" ] && [ "$wl_w" != unknown ] || continue
    # The sub-field's refs: `<session>:<index>` first, `<@id>` second.
    wl_rec_ref="${wl_w%% *}"
    wl_rec_id=""
    case "$wl_w" in *' '@*) wl_rec_id="${wl_w##* }" ;; esac
    case "$wl_ref" in
    @*)
      # Asked by id. The record must carry that id, and the id must resolve —
      # which `wl_now_id` has already proved, since tmux answered for it.
      [ -n "$wl_rec_id" ] && [ "$wl_rec_id" = "$wl_ref" ] || continue
      ;;
    *)
      # Asked by `<session>:<index>`. The record must name that ref, AND —
      # where the record carries an id and this workstation can see the window
      # — the window now holding the ref must report that same id.
      [ "$wl_rec_ref" = "$wl_ref" ] || continue
      if [ "$wl_local" = 1 ] && [ -n "$wl_rec_id" ] && [ "$wl_rec_id" != "$wl_now_id" ]; then continue; fi
      ;;
    esac
    # AMENDMENT 15 — AND THE ANSWER IS THE ROW'S SPELLING, as rung 1's already
    # is. `$wl_l` is the lane as its own `PAUSED … swap;` line spells it, which
    # is whatever the lane was PAUSED under; this read's three callers hand what
    # it prints to `tmux rename-window`, to `--name` and to `restart <lane>`, so
    # a record written before the row's spelling settled would rename a window
    # to the wrong one. A register holding the 15(d) pair keeps the record's own
    # spelling rather than refusing: this read is a rung in front of a launch and
    # its contract is 0, 8 or 64 — the refusal belongs to the writer it leads to.
    wl_can="$(canon_lane "$wl_l" 2>/dev/null || :)"
    printf '%s\n' "${wl_can:-$wl_l}"
    return 0
  done <<EOF
$(swapped_candidates "$wl_ws")
EOF
  return 8
}

# ------------------------------- clause (d) rules 3 and 4: the LAST UUID
#
# THE RESUME TARGET, READ ROBUSTLY AND NEVER FALLING TO A TITLE WHILE A UUID
# EXISTS (Amendment 11 clause (d), Evidence 2(b)). Two sources, in order, and
# the second is consulted ONLY where the first has no answer at all — Amendment
# 6(b) keeps the published cell as the resume target and this adds no second
# one:
#
#   1. THE PUBLISHED ROW'S SESSION CELL, OF ANY SHAPE. `uuids_in_cell` matches
#      the uuid by its shape rather than by the cell's punctuation, so
#      `harness \`x\` → after /clear \`y\``, a bare id, a `(profile team-02c)`
#      annotation and a cell carrying `session_01…` footer ids beside a uuid
#      all answer the same: the LAST uuid in it.
#   2. THE LANE'S OWN LOG — the session field of its last `PAUSED` or `RESUMED`
#      line, in file order, out of `origin/<branch>` exactly as every other
#      state read is. Clause (e) is what makes this source trustworthy, by
#      refusing `unknown` in that field: a log that may carry the literal there
#      is a log that cannot be read this way, and the two clauses are one act.
#
# A uuid whose transcript is not in the lane's directory IS STILL A UUID, and
# the caller says so rather than resuming a title into a picker.
#
# 0 with the uuid, 8 where neither source names one.
last_session_of() {   # <lane>
  lso_l="${1-}"; [ -n "$lso_l" ] || return 64
  lso_id="$(session_ids_of_lane "$lso_l" 2>/dev/null | tail -n1 || :)"
  if [ -n "$lso_id" ]; then printf '%s\n' "$lso_id"; return 0; fi
  lso_id="$(lane_log_events "$lso_l" 2>/dev/null | awk -F"$US" '
    ($3 == "PAUSED" || $3 == "RESUMED") && $4 ~ /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/ { id = $4 }
    END { if (id != "") print tolower(id) }')"
  [ -n "$lso_id" ] || return 8
  printf '%s\n' "$lso_id"
}

# ------------------------- decision 8(c) and 8(e): A FORK IS NEVER A HOLDER
#
# Evidence 6, 2026-09-13: an abandoned launch of a lane left behind a DAEMON
# FORK of its transcript — `--fork-session`, a NEW session id, `kind: bg`, no
# tmux, a cwd of `/workspace` — which went on orchestrating the same plan,
# relaunched writers on the same three branches, wrote `RESUMED` and `PAUSED`
# lines into the lane's log, and messaged the interactive session claiming to
# be the holder while citing a dead pid.
#
# Amendment 8 ruling (g) already skips a `kind: bg` companion, and that is not
# enough: a fork is a SESSION OF ITS OWN with an id no row carries, so the
# thing that makes it recognisable is neither its kind nor its id but ITS
# TRANSCRIPT'S TITLE. A `--fork-session` copies the parent's `custom-title`
# record, so the fork's transcript says `openRepoProject-1` while its id says
# something the lane's row has never heard of. That pair — THE LANE'S TITLE
# UNDER AN ID THE LANE DOES NOT RECORD — is the defect, and it is what this
# read finds.
#
# IT NAMES THEM AND DOES NOTHING ELSE, exactly as `idle_holders` does and for
# the same reason clause (f) of Amendment 8 gives. THE ACT IT NAMES IS
# `lane-end <lane> --retire <pid|uuid>` (clause (k) rule (e), A11 Addendum 4
# ruling 8) and never `kill <pid>`: that act is the DOOR to Amendment 6(d), it
# writes nothing and *"neither kills a process"*. So this read goes on naming a
# fork until 6(d) is actually taken on it — the retitle, or the process gone —
# which is what is TRUE; and stopping the process stays a person's act that no
# surface here prints as the one.
#
# One line per fork, `<session id><TAB><pid><TAB><kind><TAB><cwd>`.
# 0 with rows, 8 with none, 1 where the records could not be read.
# Every LIVE record on this workstation whose transcript carries a custom
# title, as
# `<lc title><US><title><US><sessionId><US><lc sessionId><US><pid><US><kind><US><cwd>`.
# Built ONCE per process: `who` asks about every lane in the register, and one
# find per record per lane would be a read nobody would run.
#
# CACHED IN A FILE for the reason `live_session_ids` gives, and this one was the
# more expensive of the two: `transcript_title` falls back to a `find` over the
# whole profiles tree, so a rebuild per lane was a filesystem walk per lane.
#
# THE LOWER-CASED TITLE AND ID ARE CARRIED rather than computed by the reader:
# `lc` is `printf | tr`, TWO PROCESSES, and `lane_forks` ran it on every entry of
# this map for every lane it was asked about — fifty lanes times however many
# live records, for two comparisons a `case` can make.
fork_map() {
  fm_c="${SE_CACHE_FILE:+$SE_CACHE_FILE.forks}"
  if [ -n "$fm_c" ] && [ -f "$fm_c" ]; then cat -- "$fm_c"; return 0; fi
  # THE READ IS ITS OWN STEP AND ITS STATUS DECIDES, because the loop below is
  # fed by a HERE-DOCUMENT and a here-document body is TEXT: the status of a
  # command substitution inside it is discarded outright (#26, the review of
  # `37632b1`; the same shape `f368a75` took out of `lane_payload_field`).
  fm_recs=""; fm_rc=0
  fm_recs="$(session_records)" || fm_rc=$?
  [ "$fm_rc" = 0 ] || return 1
  fm_out=""
  while IFS="$US" read -r fm_f fm_sid fm_tmux fm_name fm_pid fm_kind fm_cwd fm_status fm_start; do
    [ -n "${fm_sid:-}" ] || continue
    record_fields_are_live "$fm_status" "$fm_pid" "$fm_start" || continue
    fm_t="$(transcript_title "$fm_sid" "$fm_f" "$fm_cwd")"
    [ -n "$fm_t" ] || continue
    fm_out="${fm_out}$(lc "$fm_t")${US}${fm_t}${US}${fm_sid}${US}$(lc "$fm_sid")${US}${fm_pid}${US}${fm_kind}${US}${fm_cwd}
"
  done <<EOF
$fm_recs
EOF
  if [ -n "$fm_c" ]; then
    printf '%s' "$fm_out" > "$fm_c.${BASHPID:-$$}" 2>/dev/null &&
      mv -f -- "$fm_c.${BASHPID:-$$}" "$fm_c" 2>/dev/null ||
      rm -f -- "$fm_c.${BASHPID:-$$}"
  fi
  printf '%s' "$fm_out"
}

# The `customTitle` of a transcript, by its uuid. A `/rename` writes a
# `{"type":"custom-title",…}` record INTO the transcript and the LAST one wins,
# which is the same reading `lane-start`'s own `titled_transcript` makes.
# `<lane> (2)` is the same lane: that suffix is what a rename into a title
# something else still holds mints.
transcript_title() {   # <uuid> [<the record's file>] [<the record's cwd>]
  tt_id="${1-}"; [ -n "$tt_id" ] || return 1
  tt_f=""
  # THE CHEAP CANDIDATES FIRST, AND THE WALK ONLY WHERE THEY MISS. The harness
  # keeps one transcript directory per working directory, named by that
  # directory with every character that is not a letter or a digit replaced by
  # `-`; the record itself carries both the profile directory it was written in
  # (`<profile>/sessions/<pid>.json`) and the `cwd`. Two `[ -f ]` tests answer
  # for every ordinary session, and the `find` is what catches a transcript the
  # harness moved — which is the case Evidence 6's fork was in, its transcript
  # under `state/` rather than under the profile.
  if [ -n "${3-}" ]; then
    tt_slug="$(printf '%s' "$3" | sed 's/[^A-Za-z0-9]/-/g')"
    for tt_c in \
      "$(dirname -- "$(dirname -- "${2:-/nonexistent/x}")")/projects/$tt_slug/$tt_id.jsonl" \
      "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/$tt_slug/$tt_id.jsonl"; do
      [ -f "$tt_c" ] && { tt_f="$tt_c"; break; }
    done
  fi
  if [ -z "$tt_f" ]; then
    for tt_root in "${CLAUDE_PROFILES_HOME:-$HOME/.claude-profiles}" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; do
      [ -d "$tt_root" ] || continue
      tt_f="$(find "$tt_root" -maxdepth 8 -path '*/projects/*' -name "$tt_id.jsonl" -type f 2>/dev/null | head -n1)"
      [ -n "$tt_f" ] && break
    done
  fi
  [ -n "$tt_f" ] || return 1
  tt_last="$(grep -e '^{"type":"custom-title"' -- "$tt_f" 2>/dev/null | tail -n1 || :)"
  [ -n "$tt_last" ] || return 1
  tt_v="$(printf '%s' "$tt_last" | sed 's/.*"customTitle":"//; s/".*//')"
  [ -n "$tt_v" ] || return 1
  printf '%s\n' "${tt_v% (*)}"
}

# `lane_forks <lane> [<ids fence>]`
#
# THE TWO SETS AS ONE SPACE-FENCED STRING EACH, tested with `case` (A11
# Addendum 4 ruling 12). The `grep -qx` this replaces was a process per map
# entry per lane, and `lc` on the entry's title was two more; a `case` is the
# shell's own.
#
# AND A CALLER THAT ALREADY HAS THEM PASSES THEM. `lanes` asks this about every
# lane, and computing the row's ids here meant TWO renders of the published
# register plus one of the working tree's, per lane — the very reads the listing
# has already made in one pass. A caller with one lane in hand (`forks`, `who`)
# passes nothing and this computes them, so the read is unchanged for everybody
# else. The fences are `" a b c "`, lower-cased, spaces at both ends.
lane_forks() {   # <lane> [<ids fence>]
  lf_l="${1-}"; [ -n "$lf_l" ] || return 64
  lf_ll="$(lc "$lf_l")"
  if [ "$#" -ge 2 ]; then
    lf_ids="$2"
  else
    lf_ids=" $( { session_ids_of_lane "$lf_l" 2>/dev/null || :
                  session_ids_local_of_lane "$lf_l" 2>/dev/null || :; } | awk 'NF && !seen[$0]++' | tr '\n' ' ')"
  fi
  # AND THE MAP IS READ BEFORE THE LOOP, so that a session tree which could not
  # be read leaves here as **1** and not as the **8** that means "no fork of it
  # is live" (#26, the review of `37632b1`). The `forks` arm has carried the
  # refusal for that 1 since it was written — *"That is NOT 'no fork of it is
  # live'"* — and it was UNREACHABLE, because the status died in the
  # here-document below. A fork is a DEFECT under ratified decision 8(e); the
  # one thing worse than reporting one is reporting none without looking.
  lf_map=""; lf_mrc=0
  lf_map="$(fork_map)" || lf_mrc=$?
  [ "$lf_mrc" = 0 ] || return 1
  lf_out=""
  while IFS="$US" read -r lf_tl lf_t lf_sid lf_sidl lf_pid lf_kind lf_cwd; do
    [ -n "${lf_tl:-}" ] || continue
    [ "$lf_tl" = "$lf_ll" ] || continue
    # AN ID THE ROW RECORDS IS THE LANE ITSELF, never a fork of it.
    case "$lf_ids" in *" $lf_sid "*) continue ;; esac
    # AND THERE IS NO THIRD TEST, BECAUSE RETIRING WRITES NOTHING. The first
    # build of ruling 8's act appended `RETIRED … -> fork <sid>` to the lane's
    # log and this read filtered on it; that line is a SEVENTH edit to in-force
    # text — Amendment 7(b) gives `RETIRED` no payload and A11 clause (c) keeps
    # it that way — so it is gone (`lane-end`'s own block argues it in full).
    # `lane-end --retire <pid|uuid>` is the DOOR to Amendment 6(d) and performs
    # none of it, which is clause (k) rule (e)'s own posture, so a fork stays a
    # fork here until the operator's retitle or its process is gone. This read
    # keeps saying what is TRUE rather than what has been acknowledged.
    lf_out="${lf_out}${lf_sid}	${lf_pid}	${lf_kind:-interactive}	${lf_cwd}
"
  done <<EOF
$lf_map
EOF
  [ -n "$lf_out" ] || return 8
  printf '%s' "$lf_out"
}

# ------------------------------------------- issue #39: DUPLICATE HOLDERS
#
# `lane_forks` answers one question — a LIVE session recorded under an id the
# row does NOT carry, wearing the lane's own transcript title — and it answers
# it well: Evidence 6's `--fork-session` daemon had a fresh id nothing had
# heard of. Measured 2026-09-14 (opensoft/openRepoTools#39): a cross-profile
# resume leaves a SECOND kind of stray behind that `lane_forks` cannot see at
# all — a `bg-pty-host` running `claude --session-id <X> --fork-session
# --resume <parent>.jsonl` under a background pty host, where a LATER
# `lane-start --no-launch` went on to bind `<X>` itself as the row's own
# session. Once that happens the fork's id IS an id the row carries,
# `lane_forks`' own exclusion (`case "$lf_ids" in *" $lf_sid "*) continue`)
# fires exactly as designed, and the daemon goes invisible to it — while a
# second live process now holds the one transcript Amendment 18(h) says
# exactly one process may hold. `lane-end --retire <pid>` refused it outright,
# and the retirement was a bare `kill -TERM`, outside every tool this estate
# has.
#
# THE PROCESS TABLE, NOT A SESSION RECORD'S `sessionId` FIELD, because this
# question is not about what a record CLAIMS its id is — the fork's own record
# may say `<X>`, which is exactly the id the row now also carries and exactly
# why `lane_forks` cannot use it — it is about the ARGV a live process was
# actually started with: a `--fork-session` invocation whose `--resume` path
# ends in one of THIS LANE's own transcript ids. Every id the row has ever
# carried is checked, not only the last (Amendment 6(b): a chained cell's
# earlier link is still this lane's transcript).
#
# `pgrep -f` FIRST, THEN `ps -o pid=,ppid=,args= -p` PER CANDIDATE, both forms
# already used elsewhere in this tree for the same reason: GNU and BSD/macOS
# agree on `-f` (match the full argument list) and on `-o field=` (each `=`
# suppresses that field's own header, so the frame needs no trimming) where
# they do not agree on a fixed-column `ps aux`. Scoping the `ps` call to one
# candidate pid at a time, rather than walking the whole table once, is what
# lets the exact form stay `-p <pid>` instead of a table-wide parse this file
# would then own two implementations of.
#
# THE ROW'S OWN LIVE HOLDER IS EXCLUDED, never reported and never touched,
# over the SAME implementation `live-holder` already calls (`live_holder`,
# over the published-union-local id set) — never a new liveness primitive. In
# the ordinary case this exclusion never fires: a lane's real interactive
# session is never started WITH `--fork-session` in its own argv, so nothing
# this read finds can coincide with it. It stays in because a fence that is
# usually a no-op is exactly what a fence should be, and `lane-end` asks the
# same question again, in words, before it sends a single signal.
#
# One line per surviving match: `<parent pid><US><child pid, or empty><US>
# <the matched uuid>` — `$US`, never a TAB. A CONFIRMED CHILD OF THE CI RUN ON
# PR #61: with a real, honest, DOCUMENTED-empty child slot (the line just
# above — "the child slot stays empty" is not a race-only rarity, it is this
# read's ordinary answer for a parent with no confirmable fork-session child),
# a bare TAB is one of bash `read`'s own IFS-WHITESPACE characters, so
# `IFS=$'\t' read -r a b c` on `"<parent>\t\t<uuid>"` — TWO adjacent tabs
# either side of the empty middle field — COLLAPSES them into ONE delimiter
# exactly as it collapses repeated spaces, silently shifting the uuid into
# `b` and leaving `c` empty. Measured: `tests-no-submodule` on e4f9054,
# `test_the_lane_helper_suite_passes` read the empty child as a parent still
# "STILL ALIVE" (its own argv check comparing against `$dh_uuid_lc=""` could
# match nothing) and the uuid as a pid — `pid <uuid> (child): gone`. `$US` is
# not IFS whitespace, so `read` never merges it with itself; both consumers in
# `lane-end` read this format with `IFS=$'\037'` for the same reason
# `live-holder`'s own multi-field line already does.
# 0 with rows, 8 with none, 1 where `pgrep` is missing or
# this workstation's session records could not be read — a read that failed is
# never "nothing is a duplicate".
duplicate_holder_pids() {   # <lane>
  dhp_l="${1-}"; [ -n "$dhp_l" ] || return 64
  command -v pgrep >/dev/null 2>&1 || return 1
  command -v ps    >/dev/null 2>&1 || return 1
  dhp_ids="$( { session_ids_of_lane "$dhp_l" 2>/dev/null || :
                session_ids_local_of_lane "$dhp_l" 2>/dev/null || :; } | awk 'NF && !seen[$0]++')"
  [ -n "$dhp_ids" ] || return 8
  dhp_legit=""
  # NOT `$( … )` (Copilot round 2, PR #61): `live_holder` communicates a read
  # failure by setting `SESSION_FILES_ERR` in ITS CALLER's shell, exactly as
  # `session_files` documents and `window_session` already relies on — a
  # command substitution runs in a SUBSHELL, so that assignment would die with
  # it and the dispatcher's `${SESSION_FILES_ERR:-unknown error}` would print
  # "unknown error" always. The tmp file is what lets this call stay direct
  # and still hand the printed record back to the code after it.
  dhp_lh_f="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-dhp.XXXXXX" 2>/dev/null || printf '')"
  if [ -z "$dhp_lh_f" ]; then
    SESSION_FILES_ERR="could not create a temporary file under ${TMPDIR:-/tmp}"
    return 1
  fi
  live_holder "$dhp_l" "$dhp_ids" > "$dhp_lh_f" 2>/dev/null; dhp_lrc=$?
  case "$dhp_lrc" in
    0) dhp_legit="$(awk -F"$US" '{print $4}' "$dhp_lh_f")" ;;
    8) : ;;
    *) rm -f -- "$dhp_lh_f"; return 1 ;;
  esac
  rm -f -- "$dhp_lh_f"
  # `pgrep -f` ITSELF, THREE-WAY (Copilot round 2): 1 is its OWN "no process
  # matched" — the ordinary, honest 8 — and anything else (2 usage, 3 a fatal
  # error reading the process table) is a READ THAT FAILED, never "none is a
  # duplicate".
  dhp_cand=""; dhp_pgrc=0
  dhp_cand="$(pgrep -f 'fork-session' 2>/dev/null)" || dhp_pgrc=$?
  case "$dhp_pgrc" in
    0) : ;;
    1) return 8 ;;
    *) return 1 ;;
  esac
  [ -n "$dhp_cand" ] || return 8
  # A CANDIDATE'S OWN PARENT, WHEN IT IS ALSO A CANDIDATE, IS NEVER TREATED AS
  # A SECOND PARENT (Copilot round 2): `--fork-session`'s argv is inherited by
  # the child `claude` process as often as the bg-pty-host wrapper that
  # started it, so `pgrep -f` routinely returns BOTH — and reading the child
  # on its own turn, with no ppid fence, reported it as a headless parent of
  # its own (no child of ITS OWN to find), doubling one duplicate into two
  # rows and leaving `--retire <the real parent's pid>` unreachable if the
  # child's spurious row was taken instead.
  dhp_cand_fence=" $(printf '%s' "$dhp_cand" | tr '\n' ' ') "
  dhp_out=""
  while IFS= read -r dhp_pid; do
    [ -n "$dhp_pid" ] || continue
    [ -n "$dhp_legit" ] && [ "$dhp_pid" = "$dhp_legit" ] && continue
    dhp_psrc=0
    dhp_line="$(ps -o pid=,ppid=,args= -p "$dhp_pid" 2>/dev/null)" || dhp_psrc=$?
    # A `ps -p` MISS IS NOT A READ FAILURE, but a nonzero status alongside
    # OUTPUT would be (Copilot round 5/6, PR #61: "a failed ps lookup is read
    # as no candidate") — `ps -p <gone pid>` fails with EMPTY output, which is
    # the ordinary, honest "it already exited" race this whole scan expects;
    # a command that failed and still printed something is the one case
    # this file's fail-closed rule everywhere else applies to.
    if [ -z "$dhp_line" ]; then continue; fi
    [ "$dhp_psrc" = 0 ] || return 1
    read -r dhp_pid_chk dhp_ppid dhp_args <<DHPLINE
$dhp_line
DHPLINE
    case "$dhp_args" in *"--fork-session"*"--resume "*) : ;; *) continue ;; esac
    case "$dhp_cand_fence" in *" $dhp_ppid "*) continue ;; esac
    dhp_args_lc="$(printf '%s' "$dhp_args" | tr 'A-F' 'a-f')"
    # THE ACTUAL `--resume` VALUE, NOT A GLOB THAT CAN SPAN OTHER ARGUMENTS
    # (Copilot round 5, PR #61): `*"--resume"*"/$id.jsonl"*` also matches
    # `--resume /other.jsonl --label /<id>.jsonl`, since `*` between them
    # freely crosses argument boundaries. The token right after `--resume ` —
    # up to the next space or the end of argv — is what was actually
    # resumed, and that is the only thing compared now.
    dhp_resume="${dhp_args_lc#*--resume }"; dhp_resume="${dhp_resume%% *}"
    for dhp_id in $dhp_ids; do
      dhp_id_lc="$(printf '%s' "$dhp_id" | tr 'A-F' 'a-f')"
      # AN EXACT PATH COMPONENT, NOT AN ARBITRARY SUBSTRING (Copilot round 4,
      # PR #61): a bare substring also matches `other-<id>.jsonl` (no leading
      # `/`, so it is not THIS transcript's basename) and `<id>.jsonl.bak` —
      # `/<id>.jsonl` must be the resume token's own trailing path component.
      dhp_matched=0
      case "$dhp_resume" in */"$dhp_id_lc.jsonl") dhp_matched=1 ;; esac
      if [ "$dhp_matched" = 1 ]; then
          # THE CHILD, PREFERRING ONE THAT IS ITSELF A `--fork-session` MATCH
          # (the real `claude` leaf) over whichever child the process table
          # happens to list first. `pgrep -P`'s OWN status, three-way, same as
          # the top-level `pgrep -f` above (Copilot round 4): 1 is its own
          # "no children", honestly empty; anything else is a read that
          # FAILED, and this candidate is skipped rather than reported with a
          # child slot that only LOOKS empty on purpose.
          dhp_child=""; dhp_kids=""; dhp_kidrc=0
          dhp_kids="$(pgrep -P "$dhp_pid" 2>/dev/null)" || dhp_kidrc=$?
          case "$dhp_kidrc" in
            0 | 1) : ;;
            *) return 1 ;;
          esac
          # AN ARBITRARY CHILD IS NEVER GUESSED (Copilot round 6, PR #61): a
          # bg-pty-host can have children that are not the `claude` process it
          # wraps at all — a shell, a pty helper — and reporting the FIRST one
          # `pgrep -P` happens to list, when none of them is itself a
          # `--fork-session` candidate, could hand an unrelated process to
          # `lane-end --retire`'s TERM. Only a child THIS SAME SCAN also
          # confirmed as a fork-session candidate is ever named; otherwise the
          # child slot stays empty; the parent is still reported and retirable
          # on its own.
          #
          # A SECOND CANDIDATE MUST ALSO PROVE IT RESUMES THIS SAME TRANSCRIPT
          # (Copilot round 8, PR #61): being in `dhp_cand_fence` only proves a
          # child is SOME `--fork-session` process, not THIS one's — a wrapper
          # with more than one such child could otherwise attach a different
          # transcript's fork to this parent's row. Counted FIRST, because the
          # ordinary shape (one wrapper, one child — Amendment 8 ruling (g)'s
          # own `bg` companion is the only sibling this file documents) must
          # keep working exactly as `lane-end`'s own race case proves it does:
          # a SOLE fenced candidate is accepted on the fence alone, with no
          # `ps -p` call on it at all, so a child already unreadable by the
          # time discovery runs (the exact race the pre-kill recheck below
          # exists to catch a step later) is still named and still retirable.
          # Only with TWO OR MORE fenced candidates is the ambiguity real, and
          # only then is each put through the identical per-candidate `ps`
          # read and exact-path-component `--resume` match the parent above
          # just proved itself with, against the SAME `$dhp_id_lc`; a `ps -p`
          # miss on one of several is skipped for the next rather than
          # guessed, and NONE matching leaves the child empty rather than
          # naming an unverified one — the parent is still reported and
          # retirable on its own either way.
          dhp_kid_n=0; dhp_kid_first=""
          for dhp_c in $dhp_kids; do
            case "$dhp_cand_fence" in *" $dhp_c "*) : ;; *) continue ;; esac
            dhp_kid_n=$((dhp_kid_n + 1))
            [ -n "$dhp_kid_first" ] || dhp_kid_first="$dhp_c"
          done
          if [ "$dhp_kid_n" = 1 ]; then
            dhp_child="$dhp_kid_first"
          elif [ "$dhp_kid_n" -gt 1 ]; then
            for dhp_c in $dhp_kids; do
              case "$dhp_cand_fence" in *" $dhp_c "*) : ;; *) continue ;; esac
              dhp_c_line=""; dhp_c_psrc=0
              dhp_c_line="$(ps -o args= -p "$dhp_c" 2>/dev/null)" || dhp_c_psrc=$?
              [ -n "$dhp_c_line" ] || continue
              [ "$dhp_c_psrc" = 0 ] || return 1
              dhp_c_args_lc="$(printf '%s' "$dhp_c_line" | tr 'A-F' 'a-f')"
              case "$dhp_c_args_lc" in *"--fork-session"*"--resume "*) : ;; *) continue ;; esac
              dhp_c_resume="${dhp_c_args_lc#*--resume }"; dhp_c_resume="${dhp_c_resume%% *}"
              case "$dhp_c_resume" in */"$dhp_id_lc.jsonl") dhp_child="$dhp_c"; break ;; esac
            done
          fi
          dhp_out="${dhp_out}${dhp_pid}${US}${dhp_child}${US}${dhp_id}
"
          break
      fi
    done
  done <<EOF
$dhp_cand
EOF
  [ -n "$dhp_out" ] || return 8
  printf '%s' "$dhp_out"
}

# ------------------------------- decisions 6 and 7: THE LANE LISTING READ
#
# ONE READ, TWO LISTINGS. Decision 6 ratified the estate-wide `lanes`; decision
# 7 ratified `restart`'s per-repo listing and `/restart`'s. All three are the
# same rows with a different filter, so the filter is an argument here rather
# than three implementations in three commands — the rule clause (h) already
# gives `window-lane` and `session-lane`.
#
# READ-ONLY, out of `origin/<branch>` like every Amendment 7 read, and
# `LANES_NO_FETCH=1` is honoured by the one `log_sync` its caller makes. It
# never writes and never launches anything.
#
#   lanes_rows [--repo <owner/repo>] [--dir <path>] [--ws <ws>] [--all]
#
# `--repo` and `--dir` are decision 7's per-repo scope and they are an OR, not
# an AND: "rows whose register `home` is this checkout's `origin`, OR whose
# recorded `dir` is this checkout". That second half is a second use for clause
# (c)'s `dir` and an argument for recording it, because a lane's home
# repository and the checkout it sits in are not the same fact.
#
# Tab-separated, one line per lane, and the COLUMNS ARE THE DATA rather than a
# rendering: `restart` and `lanes` lay them out, and a third caller that wants
# a different shape does not need a fourth read.
#
#   <lane> <state> <workstation> <profile> <window> <last uuid> <dir>
#   <objects> <age> <restart line> <home> <forks>
#
# THE FIRST TEN ARE CLAUSE (j)'s TEN, IN CLAUSE (j)'s ORDER (A11 Addendum 4
# ruling 7): *"`lanes` and `restart` each render the subset of clause (j)'s ten
# columns their surface needs while the read carries all ten."* Column 10 — the
# restart line — used to be computed by each renderer, which is two
# implementations of one column; it is the read's now, so the two surfaces
# cannot disagree about which lane may be restarted or about what to type.
#
# `<home>` and `<forks>` are the read's own additions after the ten.
# `<forks>` is decision 8(e): the count of LIVE forks of this lane's transcript
# — a defect to retire, shown by both listings and never counted as a holder.
#
# Newest activity first, by the UTC of the lane's last lane-kind line. That is
# a clock and it decides nothing but the ORDER OF A LISTING, which is the one
# place a clock is allowed to: `swapped` ranks by landing order because a
# launcher BINDS from its first row, and nothing binds from this one.
# Every LIVE session id on this workstation with the window it is in, as
# `<sessionId><US><tmux target><US><name><US><pid>`. ONE pass over the records
# for the whole listing: `live_holder` answers about one lane and re-reads
# every record to do it, which for a 48-row register is 48 scans of the same
# directory.
#
# CACHED IN A FILE AND NOT IN A VARIABLE (A11 Addendum 4 ruling 12). Every
# caller invokes this inside `$( … )`, which is a SUBSHELL — so the variable the
# build set died with the build and the next lane rebuilt it, 564 records at a
# time, 46 times for one listing. A file survives the subshell that wrote it.
live_session_ids() {
  lsi_c="${SE_CACHE_FILE:+$SE_CACHE_FILE.live}"
  if [ -n "$lsi_c" ] && [ -f "$lsi_c" ]; then cat -- "$lsi_c"; return 0; fi
  # ITS OWN STEP, FOR THE HERE-DOCUMENT'S SAKE, exactly as in `fork_map`: a
  # session tree that could not be read is not a workstation with nothing live
  # on it, and this answer decides the STATE column of every row a listing
  # prints (#26, the review of `37632b1`).
  lsi_recs=""; lsi_rc=0
  lsi_recs="$(session_records)" || lsi_rc=$?
  [ "$lsi_rc" = 0 ] || return 1
  lsi_out=""
  while IFS="$US" read -r lsi_f lsi_sid lsi_tmux lsi_name lsi_pid lsi_kind lsi_cwd lsi_status lsi_start; do
    [ -n "${lsi_sid:-}" ] || continue
    record_fields_are_session "$lsi_kind" || continue
    record_fields_are_live "$lsi_status" "$lsi_pid" "$lsi_start" || continue
    lsi_out="${lsi_out}${lsi_sid}${US}${lsi_tmux}${US}${lsi_name}${US}${lsi_pid}
"
  done <<EOF
$lsi_recs
EOF
  if [ -n "$lsi_c" ]; then
    printf '%s' "$lsi_out" > "$lsi_c.${BASHPID:-$$}" 2>/dev/null &&
      mv -f -- "$lsi_c.${BASHPID:-$$}" "$lsi_c" 2>/dev/null ||
      rm -f -- "$lsi_c.${BASHPID:-$$}"
  fi
  printf '%s' "$lsi_out"
}

# Every lane the register has a row for — the union with `known_lanes` is what
# a listing shows, because a lane may have a row and no log (pre-cutover) or a
# log and a row that has been closed.
register_lanes() {
  register_text | awk '
    substr($0,1,1) == "|" {
      p1 = index($0, "`"); if (p1 == 0) next
      rest = substr($0, p1 + 1); p2 = index(rest, "`"); if (p2 == 0) next
      print substr(rest, 1, p2 - 1)
    }'
}

# ONE PASS OVER THE REGISTER FOR THE WHOLE LISTING (A11 Addendum 4 ruling 12).
#   `<lane><US><workstation><US><session ids, lower-cased, space separated>`
#
# The four facts the listing wants from a row — is there a row, whose
# workstation, which ids, which is last — were four separate reads per lane,
# each of them `register_text | awk` and each therefore a render of the
# published 1.1 MB register. This is the same three answers from one pass, and
# the parsing is the SAME parsing: `ROW_AWK`'s first-backticked-token rule for
# the name, `row_cell`'s "field k+1 because $1 is the empty string before the
# leading pipe" for the cells, `lane_workstation`'s strip-at-the-first-slash for
# the workstation, and `uuids_in_cell`'s shape match — restated here in awk
# because a reader comparing the two must be able to see both.
LANES_REGISTER_INDEX_AWK='
    substr($0, 1, 1) != "|" { next }
    {
      p1 = index($0, "`"); if (p1 == 0) next
      rest = substr($0, p1 + 1); p2 = index(rest, "`"); if (p2 == 0) next
      lane = substr(rest, 1, p2 - 1)
      n = split($0, c, "|")
      ses = (n >= 3 ? c[3] : "")
      ws  = (n >= 4 ? c[4] : "")
      sub(/^[ \t]+/, "", ws); sub(/[ \t]+$/, "", ws)
      sub(/ *\/.*$/, "", ws)
      sub(/[ \t].*$/, "", ws)
      # `short_ws` IS `printf | tr`, TWO PROCESSES, and the listing ran it per
      # lane to decide the workstation filter. It is one `sub` and a `tolower`
      # here, in the pass that already has the value.
      wss = tolower(ws); sub(/\..*$/, "", wss)
      ids = ""; s2 = tolower(ses)
      while (match(s2, /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/)) {
        ids = ids substr(s2, RSTART, RLENGTH) " "
        s2 = substr(s2, RSTART + RLENGTH)
      }
      sub(/ $/, "", ids)
      # KEYED ON THE LANE NAME LOWER-CASED, because `lane_named_ci` is the rule
      # everywhere else in this file: the register spells one lane three ways in
      # a week, and the names this listing joins on come from the LOG files.
      # (No apostrophe in this comment: the whole program is a single-quoted
      # shell string, and one would end it.)
      print tolower(lane) sep lane sep ws sep wss sep ids
    }'
# `--local` READS THIS CHECKOUT'S REGISTER instead of the published one, which
# is `session_ids_local_of_lane`'s source and is unioned with the published ids
# for the same fail-closed reason that read gives: an id this checkout knows and
# `origin/main` does not yet is one more reason to refuse, never to allow.
lanes_register_index() {   # [--local]
  if [ "${1-}" = --local ]; then
    awk -v sep="$US" "$LANES_REGISTER_INDEX_AWK" "$LANES_FILE" 2>/dev/null
  else
    register_text | awk -v sep="$US" "$LANES_REGISTER_INDEX_AWK"
  fi
}

# SCOPE, AFTER A11 Addendum 4 RULING 6 (ratified "a11 addendum 4 yes", ruling 6
# = NO to the workstation-scoped default):
#
#   default   EVERY lane the register and the logs know — clause (j) as
#             written. It used to be this workstation's, and that was never in
#             the contract: `window-lane` is scoped and the contract says so at
#             length (`R-A11-8`/RV-T7); this read is not. "List the lanes" on a
#             two-workstation estate means both.
#   --here    this workstation only. The old default, kept as an OPTION.
#   --ws <n>  a named workstation only, which implies the same narrowing.
#   --all     no narrowing of any kind: it CLEARS `--repo`, `--dir`, `--prefix`
#             and `--here`, so a caller that has narrowed can undo it in one
#             word. That is what the settlement means by "`--all` forces the
#             every-lane listing".
#
# `--prefix <repo>` is the LABEL fallback and nothing more: a lane whose log
# records NEITHER a home NOR a directory cannot be filed by either, and its
# name's `<repo>-` prefix is the only thing left. Amendment 7 calls that prefix
# a label rather than a fact, so it is used ONLY where the two facts are absent
# — never to override a home that disagrees with it, which is the case
# `openRepoTools#28` says must be SAID rather than filed twice.
lanes_rows() {
  lr_repo=""; lr_dir=""; lr_ws="$WS"; lr_here=0; lr_all=0; lr_one=""; lr_prefix=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --repo)   lr_repo="${2-}";   shift 2 || return 64 ;;
      --dir)    lr_dir="${2-}";    shift 2 || return 64 ;;
      --prefix) lr_prefix="${2-}"; shift 2 || return 64 ;;
      --ws)     lr_ws="${2-}"; lr_here=1; shift 2 || return 64 ;;
      --lane)   lr_one="${2-}";    shift 2 || return 64 ;;
      --here)   lr_here=1; shift ;;
      --all)    lr_all=1; shift ;;
      *) return 64 ;;
    esac
  done
  # `--all` LAST AND ABSOLUTE, whatever order the flags arrived in — AND THAT
  # INCLUDES `--lane`, which this reset used to leave standing (#26, the review
  # of `c3ebcfe`). `--lane <name>` is the narrowest selector there is: the block
  # below it sets `lr_names` to that one name and clears the other four filters
  # for itself, so `lanes --all --lane X` answered about ONE lane under the flag
  # that means every lane. The sentence above it has said "absolute" since it was
  # written; this is the code catching up with it, and it is the same defect the
  # wrapper's own `here_repo` had one file up (`lanes:143`, taken at `2f44da0`).
  if [ "$lr_all" = 1 ]; then lr_repo=""; lr_dir=""; lr_prefix=""; lr_here=0; lr_one=""; fi
  [ -n "$lr_dir" ] && lr_dir="$(cd -- "$lr_dir" 2>/dev/null && pwd -P || printf '%s' "$lr_dir")"
  # ONE LANE, WITHOUT SCANNING THE ESTATE. `restart <lane>` needs one row's
  # `profile` and nothing else, and building the whole listing for it would walk
  # every log, every row and every live session record on the workstation to
  # answer a question about one lane. Same rows, same columns, same code.
  # EACH NAME CARRIES ITS OWN LOWER-CASED KEY, emitted by the pass that already
  # computes it for the de-duplication: the three lookups below join on that key
  # and `lc` is two processes (ruling 12).
  if [ -n "$lr_one" ]; then
    lr_names="$(printf '%s\n' "$lr_one" | awk -v sep="$US" 'NF { print tolower($0) sep $0 }')"
    lr_here=0; lr_repo=""; lr_dir=""; lr_prefix=""
  else
    # THE REGISTER FIRST, AND THAT IS AMENDMENT 15 (it was the logs first).
    # The de-duplication has always been on the name LOWER-CASED, so for a lane
    # both sources know it is the FIRST source that decides which spelling the
    # listing prints — and the amendment says the register row's spelling is the
    # canonical one. Read the other way round, a lane whose log file predates
    # its row's spelling was listed under the file name, and column 10's
    # `restart <lane>` line offered that spelling back to the reader.
    lr_names="$( { register_lanes 2>/dev/null || :; known_lanes 2>/dev/null || :; } | awk -v sep="$US" 'NF && !seen[tolower($0)]++ { print tolower($0) sep $0 }')"
  fi
  [ -n "$lr_names" ] || return 8
  # ONE PASS OVER EVERY LANE'S EVENTS, NOT ONE READ PER LANE PER FIELD.
  # `lanes` asks about every lane the register and the logs know, and this loop
  # used to make a `git show` of each lane's log — and then a fork per sub-field
  # on top. Measured on the live register: 24 s for a listing that shows ONE
  # row, because the cost was the 74 lanes it filtered OUT. `state_events` is
  # the stream every other state read in this file is built on, it is already
  # cached for the life of the process, and `lane_row_facts` turns it into one
  # line per lane carrying the six facts a row needs — `payload_subfield`'s two
  # rules and `home_of_lane`'s one, applied in the same awk that parses.
  # `--lane` READS ONE LOG, NOT THE ESTATE'S. `restart <lane>` asks for one
  # lane's profile and nothing else, and `state_events` is a `git show` per log
  # file — nine seconds on the live register. The same parser over the same
  # grammar either way, so the two answers cannot differ.
  if [ -n "$lr_one" ]; then
    lr_facts="$(lane_log_events "$lr_one" 2>/dev/null | lane_row_facts)"
  else
    lr_facts="$(state_events 2>/dev/null | lane_row_facts)"
  fi
  # THE REGISTER AND THE LIVE RECORDS, EACH READ ONCE FOR THE WHOLE LISTING
  # (ruling 12). Both were per-lane before, and `live_session_ids` was rebuilt
  # from 564 session records for every one of them.
  # THE THREE TABLES, FENCED FOR AN IN-SHELL LOOKUP (ruling 12). `tr` turns each
  # newline into `$GS` once, and `table_lookup` then finds any lane's line with
  # one parameter expansion — instead of `printf | awk` per lane per table,
  # which for fifty lanes was a hundred and fifty processes spent reading
  # strings this shell was already holding.
  lr_index="$GS$(lanes_register_index 2>/dev/null | tr '\n' "$GS" || :)"
  lr_local_index="$GS$(lanes_register_index --local 2>/dev/null | tr '\n' "$GS" || :)"
  lr_facts_t="$GS$(printf '%s\n' "$lr_facts" | tr '\n' "$GS")"
  # THE LIVE SCAN, AND WHAT A LISTING DOES WHEN IT FAILS (#26, the review of
  # `37632b1`). NOT a refusal: this listing is the read a person makes IN FRONT
  # OF A LAUNCH, and `43b6320`'s rule for the fetch is the rule here — it
  # answers, and says what it could not establish. What it must never do is
  # print a lane's log verb as its STATE in silence, because a lane that is
  # LIVE then shows as IDLE or PAUSED and the row offers the `restart` line that
  # would start a second session on it. The collision itself is still refused
  # one surface along: `lane-start`'s own `live_holder` reads these same records
  # DIRECTLY and exits 1 where they cannot be read.
  lr_live_rows=""; lr_live_rc=0
  lr_live_rows="$(live_session_ids 2>/dev/null)" || lr_live_rc=$?
  lr_fork_rc=0
  lr_live_fence=" $(printf '%s\n' "$lr_live_rows" | awk -F"$US" 'NF { print tolower($1) }' | tr '\n' ' ')"
  lr_ws_short="$(short_ws "$lr_ws")"
  lr_now="$(date -u +%s)"
  # ONLY A LANE THE FORK MAP NAMES CAN HAVE A FORK (ruling 12). `lane_forks`
  # stays the ONE implementation of what a fork is and what disqualifies one;
  # this simply declines to ask it about the forty-five lanes of this estate
  # that no live transcript is titled for, each of which cost a subshell, a
  # `cat` of the map and a `grep` to be told nothing.
  lr_fork_map=""
  lr_fork_map="$(fork_map 2>/dev/null)" || lr_fork_rc=$?
  lr_fork_titles=" $(printf '%s\n' "$lr_fork_map" | awk -F"$US" 'NF { print $1 }' | tr '\n' ' ')"
  if [ "$lr_live_rc" != 0 ] || [ "$lr_fork_rc" != 0 ]; then
    note "this workstation's session records could not be read, so the STATE column below is the LOG's verb alone: a lane that is live may show as IDLE or PAUSED here, and no fork of any lane is established either way. Fix the read and re-run before acting on a restart line."
  fi
  lr_out=""
  while IFS="$US" read -r lr_ll lr_l; do
    [ -n "$lr_l" ] || continue
    lr_verb=""; lr_utc=""; lr_w=""; lr_d=""; lr_pf=""; lr_win=""; lr_home=""; lr_logsid=""; lr_obj=""
    if table_lookup "$lr_facts_t" "$lr_ll"; then
      IFS="$US" read -r lr_fl lr_verb lr_utc lr_w lr_d lr_pf lr_win lr_home lr_logsid lr_obj <<EOF2
$LOOKUP_OUT
EOF2
    fi
    # THE ROW'S THREE FACTS, OUT OF THE ONE PASS: is there a row at all, whose
    # workstation it names, and which transcript uuids its session cell carries.
    lr_ixl=""; lr_rw=""; lr_rws=""; lr_ids_sp=""
    if table_lookup "$lr_index" "$lr_ll"; then
      IFS="$US" read -r lr_ixl lr_rw lr_rws lr_ids_sp <<EOF2
$LOOKUP_OUT
EOF2
    fi
    lr_lixl=""; lr_lrw=""; lr_lrws=""; lr_lids_sp=""
    if table_lookup "$lr_local_index" "$lr_ll"; then
      IFS="$US" read -r lr_lixl lr_lrw lr_lrws lr_lids_sp <<EOF2
$LOOKUP_OUT
EOF2
    fi
    # THE REGISTER'S OWN WORKSTATION COLUMN WINS where the row has one: it is
    # what every other read in this file compares, and a lane may have a row
    # here and its last log line from another machine.
    [ -n "$lr_rw" ] && lr_w="$lr_rw"
    if [ "$lr_here" = 1 ] && [ -n "$lr_w" ]; then
      lr_wcmp="$lr_rws"; [ -n "$lr_wcmp" ] || lr_wcmp="$(short_ws "$lr_w")"
      [ "$lr_wcmp" = "$lr_ws_short" ] || continue
    fi
    lr_row="$lr_ixl"
    if [ -n "$lr_home" ]; then
      lr_hc="$(alias_lookup "$lr_home" 2>/dev/null || :)"
      [ -n "$lr_hc" ] && lr_home="$lr_hc"
    fi
    if [ -n "$lr_repo" ] || [ -n "$lr_dir" ] || [ -n "$lr_prefix" ]; then
      lr_keep=0
      [ -n "$lr_repo" ] && [ -n "$lr_home" ] && [ "$(lc "$lr_home")" = "$(lc "$lr_repo")" ] && lr_keep=1
      [ -n "$lr_dir" ]  && [ -n "$lr_d" ]    && [ "$lr_d" = "$lr_dir" ] && lr_keep=1
      # THE LABEL, AS A THIRD OR-TERM. Amendment 7 calls a lane name's
      # `<repo>-` prefix a LABEL rather than a fact, and the home is what FILES
      # a lane — but a listing is asked "which lanes are this repository's", and
      # two populations answer that and are missed by home and `dir` alike:
      #   * a lane with a ROW AND NO LOG, which this estate has, whose home and
      #     directory are simply not recorded anywhere yet;
      #   * a lane a person NAMED for this repository whose log records a
      #     different home — the disagreement `openRepoTools#28` says to SAY
      #     rather than resolve, and still a position `lane-start <repo> <n>`
      #     cannot hand out twice.
      # It never overrides a home: a lane matched only by its label is LISTED,
      # not re-homed.
      if [ "$lr_keep" = 0 ] && [ -n "$lr_prefix" ]; then
        case "$(lc "$lr_l")" in "$(lc "$lr_prefix")"-*) lr_keep=1 ;; esac
      fi
      [ "$lr_keep" = 1 ] || continue
    fi
    # FAILING THE CELL, THE LANE'S OWN LOG — clause (d) rule 3, out of the same
    # one pass rather than a second read of the same stream.
    lr_sid="${lr_ids_sp##* }"
    [ -n "$lr_sid" ] || lr_sid="$lr_logsid"
    # THE STATE. A live record naming one of the lane-s ids beats the log-s
    # own last verb, because a lane whose session is running is LIVE whatever
    # its last written line says; otherwise the verb answers.
    #
    # A `case` OVER A SPACE-FENCED STRING, AND NOT A `grep` PER RECORD (ruling
    # 12): this ran `printf | grep -qx` once for every live record for every
    # lane. The fence is built once above; the lookup of the WINDOW is an awk,
    # and it only happens for a lane that is actually live.
    lr_state=""
    lr_live_win=""
    for lr_one_id in $lr_ids_sp; do
      case "$lr_live_fence" in
        *" $lr_one_id "*)
          lr_state=LIVE
          lr_live_win="$(printf '%s\n' "$lr_live_rows" | awk -F"$US" -v i="$lr_one_id" 'tolower($1) == i { print $2; exit }')"
          break ;;
      esac
    done
    if [ -n "$lr_live_win" ]; then
      lr_win="$lr_live_win"
    elif [ -n "$lr_win" ]; then
      # SPEC rev 4 §15 column 5: the window is marked `gone` where the ref no
      # longer resolves. After a tmux server restart that is EVERY recorded
      # window on the workstation — measured on Eagle at 15:5xZ on 2026-09-13,
      # 0 of 5 — and a column that showed a dead ref as though it were live is
      # the column a person would try to attach to.
      lr_wref="${lr_win%% *}"
      [ -n "$(tmux_window_field "$lr_wref" '#{window_id}' 2>/dev/null || :)" ] || lr_win="$lr_win (gone)"
    fi
    if [ -z "$lr_state" ]; then
      case "$lr_verb" in
        PAUSED)  lr_state=PAUSED ;;
        ENDED)   lr_state=ENDED ;;
        RETIRED) lr_state=RETIRED ;;
        STARTED|RESUMED) lr_state=IDLE ;;
        *)       lr_state="$([ -n "$lr_row" ] && printf 'NO LOG' || printf 'UNKNOWN')" ;;
      esac
    fi
    [ -n "$lr_obj" ] || lr_obj="none open"
    lr_age="$([ -n "$lr_utc" ] && age_of "$lr_utc" "$lr_now" || printf 'age unknown')"
    # THE TWO SETS `lane_forks` WOULD OTHERWISE RE-READ THE REGISTER FOR, handed
    # to it out of the one pass this loop already made (ruling 12) — and asked
    # at all only where a live transcript carries this lane's title.
    lr_fk=0
    case "$lr_fork_titles" in
      *" $lr_ll "*)
        lr_fk="$(lane_forks "$lr_l" " $lr_ids_sp $lr_lids_sp " 2>/dev/null | grep -c . || :)"
        case "$lr_fk" in ''|*[!0-9]*) lr_fk=0 ;; esac ;;
    esac
    # `none` AND NEVER A DASH, because three of these columns are `none` on
    # this estate until adoption act 7 cuts each lane over — `profile`,
    # `directory` and the `<@id>` half of `window` all come from records written
    # under clause (c), and 0 of the 5 swap records on Eagle carry any of them.
    # A word a reader can act on beats a glyph they have to interpret.
    # COLUMN 10 — THE RESTART LINE — IS THE READ'S AND NOT A RENDERER'S
    # (A11 Addendum 4 ruling 7). Clause (j) gives TEN columns in order and this
    # carried nine; `lanes` computed the tenth and `restart` computed a
    # different tenth, which is two implementations of one column and is how
    # they would come to disagree about which lane may be restarted.
    #
    # A PAUSED LANE ONLY (clause (j) column 10, F-X20), and a PAUSED lane whose
    # record carries NO `profile` gets the form that works today with the
    # profile named as the one token the operator must supply — because a wrong
    # profile is a launch into another account and nothing here may guess one,
    # while a line that cannot be typed is worse than a column that says
    # `none`. Every other state gets `none`: a lane whose last act was its last
    # is not a lane a person restarts.
    lr_restart=none
    if [ "$lr_state" = PAUSED ]; then
      if [ -z "$lr_pf" ] || [ "$lr_pf" = none ]; then
        lr_restart="pclaude --lane $lr_l <profile>"
      else
        lr_restart="restart $lr_l"
      fi
    fi
    lr_out="${lr_out}${lr_utc:-0000}${US}${lr_l}	${lr_state}	${lr_w:-unknown}	${lr_pf:-none}	${lr_win:-none}	${lr_sid:-none}	${lr_d:-none}	${lr_obj:-none}	${lr_age}	${lr_restart}	${lr_home:-none}	${lr_fk}
"
  done <<EOF
$lr_names
EOF
  [ -n "$lr_out" ] || return 8
  printf '%s' "$lr_out" | LC_ALL=C sort -t"$US" -k1,1r | awk -F"$US" 'NF >= 2 { print $2 }'
}

# swapped_lanes [<workstation>] — one row per swapped lane, tab-separated:
#   <lane>	<UTC>	<window>	<dir>	<profile>	<agent>	<transcript>
#
# THE LAST TWO ARE AMENDMENT 17(b)'s, and they are added at the END for the
# reason the fourth and fifth were: the FIRST FIELD BEFORE THE FIRST TAB is the
# contract every reader of this output takes (the launcher, the `handoff`
# skill's step 1, `lane-start`'s directory rung 2 and `restart`'s, each with the
# same comment saying so), and each of the others is read by its own index. A
# record written before an amendment carries its fields EMPTY rather than
# guessed — Amendment 7(i)'s cutover rule, which is what makes a sixth and a
# seventh safe to add at all.
#
# WHICH LINE IS A LANE'S "LAST" IS FILE ORDER (R14), like every other state read
# here: a lane's log is append-only and single-writer, so a line further down
# the file is a line written later whatever the two UTC fields say — and this is
# the read a restart resolves its lane from, so letting a clock decide it would
# be the same fault Amendment 7 removed everywhere else.
#
# THE ROWS ARE ORDERED BY LANDING ORDER ON `origin/<branch>`, MOST RECENTLY
# LANDED FIRST — the position of the commit that ADDED each lane's PAUSED line,
# and never the UTC in it. File order does not reach across two lanes' files,
# and two lanes' UTCs are two clocks: they may be two workstations' (Amendment 7
# gives them no shared order at all) or one workstation's mid-jump — this one
# was observed stepping ±25 s in bursts, and a log commit landed whose content
# carried a UTC 26 s after its own committer date. Git's push serialization is
# the one order both lanes really share, and it is the same arbiter clause (f)
# already uses to decide a race. The UTC stays in the output as INFORMATION, and
# decides nothing.
#
# The rank is the DAG distance from the tip (`rev-list --count <sha>..origin`),
# not a committer date, so it is history order and not a clock either. Swapped
# lanes are few — one per window a swap paused — so one pickaxe per candidate is
# the cheap read. A candidate whose adding commit cannot be found (no remote ref
# here, or the harness's LANES_NO_GIT=1) ranks last, and those fall back to UTC
# order among themselves: an order that is merely unhelpful, never wrong.
swapped_candidates() {
  sw_want="$(short_ws "${1:-$WS}")"
  state_events | awk -v sep="$US" -v want="$sw_want" '
    function pos(pf, pn) { return pf "\034" sprintf("%09d", pn) }
    BEGIN { FS = sep }
    $6 !~ /^lane:/ { next }
    # AMENDMENT 15 — LOWER-CASED KEY, ORIGINAL SPELLING BESIDE IT. Which line is
    # a lane-s LAST is what decides whether that lane is SWAPPED at all, and
    # keyed on the raw `$2` a `PAUSED … swap;` under one spelling followed by a
    # `RESUMED` under the other left the PAUSED alive as a candidate: `restart`
    # would relaunch a lane that is not paused, and `window-lane` would bind a
    # window ref the lane has since left (Copilot round 1 on openRepoTools#41).
    { k = tolower($2); p = pos($10, $11)
      if (!(k in mp) || p >= mp[k]) {
        mp[k] = p; verb[k] = $3; utc[k] = $1; pay[k] = $8; uuid[k] = $4; ws[k] = $5; obj[k] = $6; nm[k] = $2 } }
    END {
      for (l in mp) {
        if (verb[l] != "PAUSED") continue
        if (substr(pay[l], 1, 5) != "swap;") continue
        w = ""; wst = ""; d = ""; pf = ""; ag = ""; tr = ""
        n = split(pay[l], sf, "; ")
        for (i = 1; i <= n; i++) {
          if (substr(sf[i], 1,  7) == "window ")      w   = substr(sf[i], 8)
          if (substr(sf[i], 1, 12) == "workstation ") wst = substr(sf[i], 13)
          # AMENDMENT 11 clause (c): two sub-fields added to the three
          # A8(b):202 gives this line.
          # A `dir` whose path carries a space is written QUOTED, so the quotes
          # are stripped here — one unquoter, in the one parser of this line.
          if (substr(sf[i], 1,  4) == "dir ")         d   = substr(sf[i], 5)
          if (substr(sf[i], 1,  8) == "profile ")     pf  = substr(sf[i], 9)
          # AMENDMENT 17(b): two more, and a record written before that
          # amendment carries neither — which is EMPTY here, never a guess
          # (the cutover rule of Amendment 7(i); no apostrophe in this comment,
          # because this awk program is single-quoted in the shell).
          if (substr(sf[i], 1,  6) == "agent ")       ag  = substr(sf[i], 7)
          if (substr(sf[i], 1, 11) == "transcript ")  tr  = substr(sf[i], 12)
        }
        sub(/[ \t]+$/, "", w); sub(/[ \t]+$/, "", wst); sub(/\..*$/, "", wst)
        sub(/^[ \t]+/, "", d);  sub(/[ \t]+$/, "", d)
        sub(/^[ \t]+/, "", pf); sub(/[ \t]+$/, "", pf)
        sub(/^[ \t]+/, "", ag); sub(/[ \t]+$/, "", ag)
        sub(/^[ \t]+/, "", tr); sub(/[ \t]+$/, "", tr)
        if (substr(d, 1, 1) == "\"") { q = index(substr(d, 2), "\""); if (q > 0) d = substr(d, 2, q - 1) }
        else                          { sub(/ .*$/, "", d) }
        sub(/ .*$/, "", pf)
        sub(/ .*$/, "", ag)
        sub(/ .*$/, "", tr)
        if (tolower(wst) != want) continue
        # The LAST field is the PICKAXE KEY: the head of the line as it was
        # written, up to and including its object, which is unique to it and
        # which `git log -S` can find without a regex.
        # `nm[l]` AND NEVER `l` (Amendment 15, `8345d2f`): the key is the lane
        # folded to one case and `nm` is the spelling the register row carries,
        # which is the one a caller of this output hands back to a read.
        printf "%s%c%s%c%s%c%s%c%s%c%s%c%s%c%s — lane %s, session %s@%s, %s, %s\n",
          nm[l], 31, utc[l], 31, (w == "" ? "unknown" : w), 31,
          (d == "" ? "" : d), 31, (pf == "" ? "" : pf), 31,
          (ag == "" ? "" : ag), 31, (tr == "" ? "" : tr), 31,
          verb[l], nm[l], uuid[l], ws[l], utc[l], obj[l]
      }
    }'
}

swapped_lanes() {
  sw_rows="$(swapped_candidates "${1:-$WS}")"
  [ -n "$sw_rows" ] || return 0
  while IFS="$US" read -r sw_l sw_u sw_w sw_d sw_p sw_a sw_t sw_key; do
    [ -n "${sw_l:-}" ] || continue
    sw_rank=999999999
    if have_remote_ref; then
      sw_sha="$(git -C "$LANES_REPO" log -1 --format=%H -S"$sw_key" "origin/$LANES_BRANCH" -- "$(log_path_for "$sw_l")" 2>/dev/null || :)"
      if [ -n "$sw_sha" ]; then
        sw_c="$(git -C "$LANES_REPO" rev-list --count "$sw_sha..origin/$LANES_BRANCH" 2>/dev/null || :)"
        case "$sw_c" in ''|*[!0-9]*) : ;; *) sw_rank="$sw_c" ;; esac
      fi
    fi
    printf '%09d%s%s%s%s%s%s%s%s%s%s%s%s%s%s\n' "$sw_rank" "$US" "$sw_l" "$US" "$sw_u" "$US" "$sw_w" \
      "$US" "${sw_d:-}" "$US" "${sw_p:-}" "$US" "${sw_a:-}" "$US" "${sw_t:-}"
  done <<EOF
$sw_rows
EOF
}

# The lane's open objects on ONE line, for the hook's block. `who --lane` prints
# a line per object and a heading; a hook has one line's worth of a reader's
# attention, and the objects are what the next act needs to know.
lane_open_summary() {
  los_l="$1"; los_out=""
  if ! lane_log_exists "$los_l"; then
    printf 'no log for %s (pre-cutover lane) — see its row'"'"'s state cell\n' "$los_l"
    return 0
  fi
  while IFS="$US" read -r lo_utc lo_verb lo_obj lo_ref lo_sup; do
    [ -n "${lo_verb:-}" ] || continue
    is_open_verb "$lo_verb" || continue
    los_out="${los_out}${los_out:+; }$lo_verb $lo_obj${lo_sup:+ (taken over by lane:${lo_sup%@*})}"
  done <<EOF
$(lane_objects "$los_l" 2>/dev/null || :)
EOF
  printf '%s\n' "${los_out:-none open}"
}

# HOW OLD THE ANSWER IS (Amendment 8, R-A8-1). The hook never fetches, so every
# line of its block is the checkout as it last stood. `.git/FETCH_HEAD` is
# rewritten by every fetch and by nothing else, so its mtime is when this
# checkout last heard from `origin` — and a block that says "4d ago" is a block
# a reader knows not to trust about another workstation's lane. Never a network
# call and never a failure: an unreadable one answers `unknown`.
fetch_age() {
  fa_dir="$(git -C "$LANES_REPO" rev-parse --git-dir 2>/dev/null || :)"
  [ -n "$fa_dir" ] || { printf 'unknown\n'; return 0; }
  case "$fa_dir" in /*) : ;; *) fa_dir="$LANES_REPO/$fa_dir" ;; esac
  [ -f "$fa_dir/FETCH_HEAD" ] || { printf 'never\n'; return 0; }
  fa_t="$(stat -c %Y -- "$fa_dir/FETCH_HEAD" 2>/dev/null || stat -f %m -- "$fa_dir/FETCH_HEAD" 2>/dev/null || :)"
  case "$fa_t" in ''|*[!0-9]*) printf 'unknown\n'; return 0 ;; esac
  fa_s=$(( $(date -u +%s) - fa_t ))
  [ "$fa_s" -lt 0 ] && fa_s=0
  if   [ "$fa_s" -lt 90 ];     then printf '%ss ago\n' "$fa_s"
  elif [ "$fa_s" -lt 5400 ];   then printf '%sm ago\n' "$((fa_s / 60))"
  elif [ "$fa_s" -lt 172800 ]; then printf '%sh ago\n' "$((fa_s / 3600))"
  else                              printf '%sd ago\n' "$((fa_s / 86400))"
  fi
}

# The last line of every block the hook prints, whichever branch wrote the rest,
# in the words clause (e) gives it: "every block ends with the line
# `as of <n>m ago (no fetch)`". It is the whole of what makes an unfetched read
# honest — a reader sees how stale the answer is instead of trusting a freshness
# nobody verified.
ssb_tail() {
  printf 'as of %s (no fetch)\n' "$(fetch_age)"
  return 0
}

# `lane-start`'s arguments FOR THIS LANE, filled in (Amendment 8, R-A8-7). The
# block used to print the literal `<repo> <n>` with the lane in hand, so every
# reader translated `openRepoProject-1` into `openRepoProject 1` by hand, on
# every mismatch, for ever. A lane is `<repo>-<position across>` (THE LANE
# RULE), so the split is on the LAST `-` — and ONLY when what follows it is a
# number: a lane named before that rule (`browser-ui-repair`) is started through
# `--dir`, and splitting it would print `browser-ui repair`, which is a command
# that does the wrong thing rather than one that does nothing.
lane_start_args() {
  lsa_l="${1-}"; lsa_n="${lsa_l##*-}"
  case "$lsa_l" in *-*) : ;; *) printf -- '--dir <path> %s\n' "$lsa_l"; return 0 ;; esac
  case "$lsa_n" in ''|*[!0-9]*) printf -- '--dir <path> %s\n' "$lsa_l"; return 0 ;; esac
  printf '%s %s\n' "${lsa_l%-*}" "$lsa_n"
}

# Has Rule 3's stamp for THIS session already been written? (Amendment 8,
# R-A8-7: the block told every resume to "stamp the handoff RESUMED" when
# `lane-start` had just written it — one manufactured decision per resume.) A
# local file read and nothing else: the row's handoff cell, resolved the way the
# row spells it, grepped for this session's own line. It is ASKED rather than
# assumed from the ids matching, because a window started by a bare `claude`
# rather than by `lane-start` has no stamp and does still owe one.
handoff_stamped_by() {   # <handoff cell> <session id>
  hsb_cell="${1-}"; hsb_id="${2-}"; hsb_f=""
  [ -n "$hsb_cell" ] && [ -n "$hsb_id" ] || return 1
  case "$hsb_cell" in
    '~/'*) hsb_f="$HOME/${hsb_cell#'~/'}" ;;
    /*)    hsb_f="$hsb_cell" ;;
    *)     [ -n "${LANES_REPO:-}" ] && hsb_f="$LANES_REPO/$hsb_cell" ;;
  esac
  [ -n "$hsb_f" ] && [ -r "$hsb_f" ] || return 1
  grep -qF -e "RESUMED by $hsb_id" -- "$hsb_f" 2>/dev/null
}

# DOES THE ROW'S NEWEST STAMP NAME A UUID, OR `unknown`? (Amendment 8(e), "the
# first cure carries one condition".) A real `lane-start` is the wrong-lineage
# remedy BECAUSE the cell's last id names a transcript the lane's directory has.
# Where the last launch took clause (d)'s title fallback, that id names a
# transcript this directory does not have — which is why the fallback was
# reached — and the row says so in its own words: the stamp that run wrote
# carries the literal `unknown`. A relaunch would take the same fallback again,
# so the cure there is the recording act instead.
#
# The row is read, never the directory: the hook is handed no lane checkout and
# the working directory confers no lane. `0` when the newest stamp says
# `unknown`, `1` otherwise — including a row with no stamp at all, where a
# relaunch is the ordinary remedy.
row_stamp_is_unknown() {   # <lane>
  rsu_lane="${1-}"; rsu_n=""; rsu_row=""; rsu_last=""
  [ -n "$rsu_lane" ] || return 1
  rsu_n="$(row_line "$rsu_lane" 2>/dev/null)" || return 1
  case "$rsu_n" in ''|*[!0-9]*) return 1 ;; esac
  rsu_row="$(sed -n -e "${rsu_n}p" "$LANES_FILE" 2>/dev/null || :)"
  [ -n "$rsu_row" ] || return 1
  rsu_last="$(printf '%s' "$rsu_row" | grep -o '[A-Z][A-Z]* by [^ |]*' | tail -n1 || :)"
  case "$rsu_last" in *" by unknown") return 0 ;; esac
  return 1
}

# session_start_block <hook json> <tmux window name> — the whole of what the
# SessionStart hook prints. It NEVER writes and its caller ALWAYS exits 0.
#
# `source` is one of startup, resume, clear, compact, fork. A COMPACT prints
# NOTHING: the same conversation carries on in the same window under the same
# id, and a block there would announce a lane's identity into the middle of a
# session that already has it. Everything else — a fork included, which is a new
# attachment to the lane's conversation — gets the block, and an unknown or
# missing source is treated as a startup rather than dropped.
#
# `cwd` is in the payload and is deliberately NOT read as a lane: THE WORKING
# DIRECTORY CONFERS NO LANE (Amendment 6(a)) — two lanes share one all day, and
# every nested checkout in the xFactory estate shares its parent's. The WINDOW
# and the REGISTER decide, in that order.
session_start_block() {
  ssb_json="${1-}"; ssb_win="${2-}"
  ssb_id="$(lc "$(jstr "$ssb_json" session_id)")"
  ssb_src="$(jstr "$ssb_json" source)"
  case "$ssb_src" in compact) return 0 ;; esac

  # AMENDMENT 15 — THE WINDOW NAME, THE SESSION NAME AND THE ROW KEY ARE
  # COMPARED CASE-INSENSITIVELY, AND EVERY LINE BELOW PRINTS THE ROW'S OWN
  # SPELLING. Both reads already answer with the register's spelling —
  # `lane_named_ci` lowercases both sides by name, and `lane_of_session` prints
  # the row's token — so `$ssb_lane` is canonical from here down, which is what
  # makes `lane_start_args` below hand a reader the commands filled in with the
  # spelling their window and their session are about to be named.
  # AMENDMENT 12'S GUARD AND LOCK PLUG IN HERE, and since #25 they ARE built —
  # `ssb_name_line` immediately below is clause (f), and the lock it types is
  # the same `guard_type` the `UserPromptSubmit` guard uses. A session whose
  # name differs from `$ssb_lane` only by case is renamed to the ROW's spelling
  # like any other drift, which is what makes this line and Amendment 15 one
  # rule rather than two.
  ssb_lane=""
  [ -n "$ssb_win" ] && ssb_lane="$(lane_named_ci "$ssb_win" 2>/dev/null || :)"
  [ -n "$ssb_lane" ] || [ -z "$ssb_id" ] || ssb_lane="$(lane_of_session "$ssb_id" 2>/dev/null || :)"
  # AMENDMENT 12 CLAUSE (f) AND AMENDMENT 18(h)'s READ — the name line and the
  # duplicate line, printed HERE rather than inside each of the three branches
  # below, because both are facts about this session and not about which of them
  # applies. `|| :` for the reason the whole block has one: this hook never
  # fails and always exits 0 (R-A8-1).
  # THE SUBSHELL IS THE `|| :` MADE TRUE OF MORE THAN A RETURN — see
  # `ssb_name_line`'s own header. It is the one line of this block that reads
  # every profile's session records, so it is the one most able to meet
  # something this hook may not die on.
  ( ssb_name_line "$ssb_id" "$ssb_lane" ) || :
  if [ -z "$ssb_lane" ]; then
    # THE ONE PLACE THE PLACEHOLDER IS RIGHT: no lane is known here, so there is
    # nothing to fill in. It is also the estate's ONE no-lane notice — the
    # launcher prints its own on stderr before the launch, and Amendment 8's
    # resume-choice table says one of the two goes; this is the one the session
    # itself can read.
    # THE ONE BRANCH THAT KEEPS ITS PLACEHOLDERS — no lane is known here, so
    # there is nothing to fill in. Except where the WINDOW NAME itself parses as
    # `<repo>-<n>`: the register has no such row, but the operator's own two
    # arguments are right there in the name, and printing them beats printing a
    # blank for them to fill. It is also the estate's ONE no-lane notice —
    # clause (c) step 4 stands down wherever this hook can speak.
    if [ -n "$ssb_win" ] && [ "$(lane_start_args "$ssb_win")" != "--dir <path> $ssb_win" ]; then
      printf 'no lane bound to this window — run: lane-start %s\n' "$(lane_start_args "$ssb_win")"
    else
      printf 'no lane bound to this window — run: lane-start <repo> <n>\n'
    fi
    ssb_tail
    return 0
  fi

  ssb_args="$(lane_start_args "$ssb_lane")"
  ssb_cur="$(last_session_id_of_lane "$ssb_lane" 2>/dev/null || :)"
  if [ -n "$ssb_id" ] && [ -n "$ssb_cur" ] && [ "$ssb_id" != "$ssb_cur" ]; then
    # THE BRANCH IS THE ID'S POSITION IN THE SESSION CELL, NOT ITS PRESENCE.
    # The cell is a history written oldest first and the LAST id is the lane
    # (Amendment 6(b)), so there are exactly three places an id can be, and
    # each is cured by a different act:
    #
    #   * the cell's LAST id — this session IS the lane. Handled below.
    #   * IN the cell but not last — a SUPERSEDED transcript of this lane. That
    #     is the 2026-09-11 wrong-lineage resume, caught at the first instant it
    #     can be caught, and the cure is a real `lane-start`, which resumes the
    #     id the row ends on. The conversation in this window is not the lane's,
    #     so the session is exited rather than carried on with.
    #   * in NO cell — the harness minted a new transcript with nobody acting (a
    #     /clear, a usage reset, a profile switch), or an operator's title-
    #     fallback pick landed on a transcript no row carries. The lane is right
    #     and the row is simply behind, so the cure is the recording act and no
    #     relaunch: `lane-start --no-launch`, which reads the live record in
    #     this window and appends that uuid to the cell.
    #
    # THE TWO CURES ARE NOT INTERCHANGEABLE. A reader who runs `--no-launch` on
    # a superseded transcript records the WRONG conversation as the lane's, in
    # the cell the next restart resumes from — the failure this block exists to
    # catch, performed by its own remedy.
    #
    # AND NO CURE SENDS A READER BACK THROUGH THE PICKER (clause (f)): where the
    # row's newest stamp says `unknown`, the cell's last id names a transcript
    # the lane's directory does not have, a relaunch would take the same title
    # fallback again, and the recording act is the cure there too. No branch
    # names `/resume` or the picker, because neither is a lane surface.
    #
    # EVERY COMMAND IS PRINTED FILLED IN (F-B6): the hook holds the lane, and a
    # reader trying to get back to work should not have to translate
    # `openRepoProject-1` into `openRepoProject 1` by hand at that moment.
    if printf '%s\n' "$(session_ids_of_lane "$ssb_lane" 2>/dev/null || :)" | grep -qx -F -- "$ssb_id"; then
      if row_stamp_is_unknown "$ssb_lane"; then
        printf 'WARNING: this is a superseded transcript of lane %s; the live one is %s, which the row records as `unknown` — a relaunch would record nothing either, so run: lane-start --no-launch %s\n' \
          "$ssb_lane" "$ssb_cur" "$ssb_args"
      else
        printf 'WARNING: this is a superseded transcript of lane %s; the live one is %s; you resumed %s — exit this session and run: lane-start %s\n' \
          "$ssb_lane" "$ssb_cur" "$ssb_id" "$ssb_args"
      fi
    else
      printf 'WARNING: this window is lane %s whose current session is %s; this session %s is in no row — the harness minted a new transcript — run: lane-start --no-launch %s\n' \
        "$ssb_lane" "$ssb_cur" "$ssb_id" "$ssb_args"
    fi
    ssb_tail
    return 0
  fi

  ssb_ho="$(handoff_of_lane "$ssb_lane" 2>/dev/null || :)"
  # AMENDMENT 11 CLAUSE (h) — THE BOUND LINE GAINS THE WINDOW, and gains
  # nothing else: `session-start` keeps all three of its safety properties, it
  # never writes, it never touches the network and it always exits 0 (R-A8-1),
  # and this is a field the block has already read out of the lane's own log.
  # It is here because the window is what clause (b)'s precedence 3 and clause
  # (f)'s step 2(c) bind from, and a reader who cannot see what the record says
  # the window is cannot tell a lane that will bind with no question from one
  # that will not.
  ssb_win="$(lane_payload_field "$ssb_lane" window all 2>/dev/null || :)"
  printf 'LANE %s — handoff %s — row session %s%s\n' \
    "$ssb_lane" "${ssb_ho:-none recorded}" "${ssb_cur:-none recorded}" \
    "${ssb_win:+ — window $ssb_win}"
  # DECISION 8(e) — A LIVE FORK OF THIS LANE'S TRANSCRIPT IS SHOWN AS A DEFECT
  # TO RETIRE. Evidence 6: an abandoned launch left a `--fork-session` daemon
  # orchestrating the same plan, relaunching writers on the same branches and
  # writing this lane's log under an id no row carries, while telling the
  # interactive session it was the holder. A session that starts into a lane
  # somebody else's fork is still running needs to know before it acts, and the
  # retirement is a person's act (Amendment 8(f)), so the line NAMES and does
  # nothing.
  ssb_fk=""; ssb_fkrc=0
  ssb_fk="$(lane_forks "$ssb_lane" 2>/dev/null)" || ssb_fkrc=$?
  # AND THE SAME HERE, for the same reason: this block is the first thing a
  # session that starts into a lane reads, and "no fork" is a fact it acts on.
  case "$ssb_fkrc" in
    0 | 8) : ;;
    *) printf 'UNKNOWN: this workstation'"'"'s session records could not be read, so whether a live FORK of this lane'"'"'s transcript is running is NOT established — which is not the same as none. See: lanes-edit.sh forks %s\n' "$ssb_lane" ;;
  esac
  if [ -n "$ssb_fk" ]; then
    while IFS='\t' read -r ssb_fid ssb_fpid ssb_fkind ssb_fcwd; do
      [ -n "${ssb_fid:-}" ] || continue
      printf 'DEFECT: %s is a live FORK of this lane'"'"'s transcript (pid %s, %s, cwd %s) — it is not the holder and must not write the register. Retire it: lane-end %s --retire %s\n' \
        "$ssb_fid" "$ssb_fpid" "${ssb_fkind:-interactive}" "${ssb_fcwd:-unknown}" "$ssb_lane" "$ssb_fpid"
    done <<EOF
$ssb_fk
EOF
  fi
  # THE BLOCK STOPS ASKING FOR A STAMP `lane-start` HAS ALREADY WRITTEN (R-A8-7,
  # resume-choice row 9: one manufactured decision per resume). It is DERIVED,
  # not assumed from the ids matching — a window started by a bare `claude`
  # rather than through the launcher has no stamp and does still owe one — so
  # the handoff the ROW names is read and grepped for THIS session's own line.
  # Where the row names no handoff at all the line says that instead.
  if [ -z "$ssb_ho" ]; then
    printf 'the row records no handoff path — there is none to stamp or to follow\n'
  elif handoff_stamped_by "$ssb_ho" "$ssb_id"; then
    printf 'handoff already stamped by lane-start — follow its top block\n'
  else
    printf 'stamp the handoff RESUMED (Rule 3) and follow its top block\n'
  fi
  printf 'open: %s\n' "$(lane_open_summary "$ssb_lane")"
  ssb_tail
  return 0
}

# ============================================================================
# AMENDMENT 12 — THE NAME GUARD AND THE LOCK, WITH AMENDMENT 18(h)'S ONE READ
# ============================================================================
#
# **A LANE SESSION WORKS ONLY WHILE THREE NAMES ARE ONE** — the tmux WINDOW it
# runs in, the SESSION's own name, and the register ROW whose session cell ends
# on this transcript — **and otherwise the prompt is REFUSED** (exit 2), with
# the triple as it stands and the ONE command that cures it, filled in. Ratified
# 2026-09-13T18:20:44Z, "Ratify revision 2", with M1 "Type /rename into the
# pane"; `brettheap/new-workstation#22`/#23, opensoft/openRepoTools#25.
#
# WHY THE RULE NEEDED AN ENFORCEMENT. Amendment 2 has said since 2026-09-05 that
# a lane is its window's name and its session's name; nothing refused anything
# for eight days, and between 2026-09-10 and 2026-09-12 this very lane ran as
# `openRepoTools-3`, `-4`, … `-14` — a fresh title per `/resume`, in a window
# still named `claude`, in profiles that changed at every usage reset — and no
# row was ever written. `session_start_block` above says which lane a window is
# and "ALWAYS exits 0"; `window_session` "decides nothing". This is the surface
# that decides.
#
# THE LOCK (clause (h), Brett Heap's D5). Under the projects root the session
# name is not the person's to set freely; it is the lane's. The tooling sets it
# at every launch (`lane-start --name "$LANE"`, clause (c)) and again whenever it
# drifts — by TYPING `/rename <lane>` into the session's own tmux pane, which is
# the only mechanism a running session has (M1, "Type /rename into the pane"):
# the docs name `--name` at launch, `/rename`, and `Ctrl+R` in the picker, and
# nothing else — no hook output field, no environment variable, no settings key.
# A PERSON'S rename to another lane's name is not drift but an INSTRUCTION, and
# it is OFFERED back before it is obeyed: yes moves this window to that lane, no
# renames the session back.
#
# FAIL CLOSED (clause (d)). A mismatch refuses; so does an INDETERMINATE read —
# session records unreadable, tmux not answering, the register unreadable —
# naming the read, because a triple that cannot be verified is not a triple that
# agrees. There is no environment flag that turns this off: `claude --safe-mode`
# disables every hook and is the one bypass, deliberate and visible in the
# prompt box, and a session started that way is not a lane session and may not
# write the register or claim an object.
#
# WHAT IT COSTS, AND THE ONE WAY IT FAILS OPEN. Measured on Eagle 2026-09-14
# against 329 session records and a 1.3 MB register: the register read is ~2 s
# wall and the `grep -l` over every profile's records ~0.4 s, so a refusal lands
# inside the ratified `timeout 5`. A hook that EXCEEDS its timeout is killed, and
# a killed hook does not exit 2 — so the timeout is the one path on which this
# guard fails open. It is the amendment's own number and is left at it; the
# cheap tests are made first so that the two reads happen only where they decide
# something.
#
# IT NEVER FETCHES. `session-start`'s R-A8-1 argument applies here several times
# over — that hook runs once per session and this one runs at EVERY PROMPT — so
# the row is read from `origin/<branch>` AS THIS CHECKOUT LAST HAD IT (R19, the
# same `register_text` every other state read takes) and the network is never
# opened. "The register not fetchable" (clause (d)) is therefore the READ
# failing, and that refuses.

# A LANE NAME IS `<repo>-<position>` (THE LANE RULE), and this is the predicate
# for it: `check_lane_name`'s character fence, plus a LAST `-` followed by
# digits. It agrees with `lane_start_args` by construction — that function
# prints `--dir <path> <lane>` for exactly the names this refuses — and the two
# exist separately because one answers a question and the other builds a command
# line. A name the register has a row for is a lane whatever its shape
# (`browser-ui-repair` is one); this asks only whether the two arguments of
# `lane-start` can be read OUT of a name nobody has a row for yet, which is what
# rows 1 and 6 of the table below need.
lane_shaped() {   # <name>
  lsh_n="${1-}"
  case "$lsh_n" in ''|*[!A-Za-z0-9._-]*|.*|-*) return 1 ;; esac
  case "$lsh_n" in *-*) : ;; *) return 1 ;; esac
  lsh_pos="${lsh_n##*-}"
  case "$lsh_pos" in ''|*[!0-9]*) return 1 ;; esac
  return 0
}

# CLAUSE (e)'s SCOPE, AND IT IS ASKED OF BOTH SPELLINGS OF A PATH. The guard
# applies to every session whose `cwd` is under the projects root and is silent
# elsewhere (D1, "Projects root only"). On a launcher-configured workstation
# `~/projects` is a SYMLINK — every profile's is one link to
# `~/.claude-profiles/state/opensoft/projects` — and the harness reports a `cwd`
# that has already been resolved through it, so a literal prefix test answers
# "outside the projects root" about every estate session there is. Both the
# typed path and its `pwd -P` are compared, and a match on either is inside:
# the direction that errs toward the guard APPLYING is the safe one, because
# the other direction is the guard never firing at all.
under_projects_root() {   # <cwd> <projects root>
  upr_c="${1-}"; upr_r="${2-}"
  [ -n "$upr_c" ] && [ -n "$upr_r" ] || return 1
  case "$upr_c/" in "$upr_r"/*) return 0 ;; esac
  upr_cr="$(cd -- "$upr_c" 2>/dev/null && pwd -P)" || upr_cr=""
  upr_rr="$(cd -- "$upr_r" 2>/dev/null && pwd -P)" || upr_rr=""
  [ -n "$upr_cr" ] && [ -n "$upr_rr" ] || return 1
  case "$upr_cr/" in "$upr_rr"/*) return 0 ;; esac
  return 1
}

# THE WINDOW A RECORD NAMES, UNDER AMENDMENT 11(h)'s AGREEMENT RULE. A record's
# `tmux` is `<session>:<@id>.<%pane>`, and tmux REUSES window ids once a window
# is gone — measured 2026-09-14, when a stale record's `@1` resolved to a window
# of another session. So the id alone is not the window: the id must resolve
# HERE and the session it resolves in must be the one the record wrote down.
#   0  the window exists and agrees
#   1  the id resolves nowhere here, or resolves in another tmux session
#   8  there is nothing to test — no target on the record, no `@id` in it, or no
#      tmux to ask (a record with no window is not thereby a record nowhere)
record_window_state() {   # <the record's tmux field>
  rws_t="${1-}"
  [ -n "$rws_t" ] && [ "$rws_t" != none ] || return 8
  rws_ref="${rws_t%.*}"
  rws_id="${rws_ref##*:}"
  rws_sess="${rws_ref%:*}"
  case "$rws_id" in @*) : ;; *) return 8 ;; esac
  command -v tmux >/dev/null 2>&1 || return 8
  rws_now="$(tmux_window_field "$rws_id" '#{session_name}' 2>/dev/null || :)"
  [ -n "$rws_now" ] || return 1
  [ "$rws_now" = "$rws_sess" ] || return 1
  return 0
}

# ------------------------------------- AMENDMENT 18(h): ONE LIVE PROCESS
#
# *"A transcript (one session id) is held by ONE live process. The harness can
# fork one (`--fork-session`, minting a new id in a background pty host) or
# resume one twice, and the tooling refuses to build on either."* Ratified
# 2026-09-14T13:15:18Z as revision 4 of Amendment 18;
# `brettheap/new-workstation#34`, opensoft/openRepoTools#39.
#
# MEASURED FOUR TIMES ON 2026-09-14, the fourth at 18:14Z: a `bg` record in ONE
# profile's `sessions/` and an interactive record in ANOTHER's, both live, both
# carrying one `sessionId` — which is why this sweeps EVERY profile's directory
# and not the asking session's. On a launcher-configured workstation every
# profile's `projects/` is one shared directory, so a transcript needs no move
# to be resumed under another profile and a duplicate is one `--resume` away.
#
# THREE CALLERS, ONE IMPLEMENTATION, for the reason clause (h) already gives
# `window-lane`: `lane-start` refuses to bind or resume an id another process
# holds, `lane-end --retire <pid>` retires that process, and the prompt guard
# refuses every prompt inside it. A rule implemented three times is a rule three
# surfaces come to disagree about.
#
# IT IS BUILT ON A `grep -l`, NOT ON `session_records`. This runs at every prompt
# under a five-second timeout, and the one-pass parse is a per-process CACHE that
# the first caller pays for in full — 329 records here. The question asked is
# about ONE id the harness has already handed the hook, so the cheap shape is the
# one `live_holder` uses: one grep for the id, then a parse of the one or two
# files that match. Measured at ~0.4 s against those 329.
#
#   <pid><US><kind><US><tmux|none><US><profile><US><where><US><verdict><US><file>
#
# `where` is for a person to read — `window <session>:<@id>`, the same with
# ` (gone)` where the agreement rule above refuses it, or `bg`.
#
# THE VERDICT IS THE WHOLE OF THE JUDGEMENT, and it has four values because
# THREE IN-FORCE RULES MEET HERE AND NONE OF THEM MAY BE OVERTURNED BY THIS ONE:
#
#   here        the record is THIS window's own process — its `tmux` names this
#               window, or its pid is this pane's or below it: `record_is_here`'s
#               TIERS 2 AND 3, and its tier 1 is left out because it cannot
#               discriminate here. That tier asks whether the record's
#               `sessionId` is `$CLAUDE_CODE_SESSION_ID`, and every candidate in
#               this set carries the very id being tested — so on the asking
#               session's own transcript it would answer `here` for the
#               duplicate too, which is the one reading this function exists to
#               prevent.
#   companion   not this window's, in the SAME profile's `sessions/` as this
#               window's own record of this id, AND NOT A SESSION RECORD.
#               AMENDMENT 8, RULING (g) names exactly one such thing: *"Beside
#               the interactive process in the pane the harness runs a companion:
#               `kind: bg`, no `tmux`, no `nameSource`, its own pid, and THE SAME
#               `sessionId` … Records that share a `sessionId` are one session,
#               not a queue of rival holders, and there is no contest between
#               them to win."* The harness writes a session's own records under
#               that session's own `$CLAUDE_CONFIG_DIR`, so same-profile is what
#               "the harness's own second record of one session" looks like —
#               and the `kind` is what tells that record apart from a SECOND
#               INTERACTIVE PROCESS in the same directory, which is one
#               transcript resumed twice and is 18(h)'s own case rather than the
#               harness's companion. The profile alone read a second `--resume`
#               UNDER ONE PROFILE as benign (Copilot round 1 on this PR), and
#               that is the cheapest way there is to make two live processes on
#               one transcript: no move, no swap, one command.
#               THE KIND IS `bg` AND NOTHING ELSE IS READ AS ONE. `not a session
#               record` was the first spelling of this test and it was too wide
#               by exactly the kinds nobody has ruled on: this suite's own
#               interactive fork carries `kind: user`
#               (`tests/test_lane_helpers.sh`, Amendment 11 clause (k)), and any
#               kind a later harness invents would have arrived here as the
#               harness's benign companion (Copilot round 2 on this PR). Ruling
#               (g) names ONE shape to pass over, so that shape is what this
#               matches; every other live record on this id — known kind or not,
#               and a record too old to carry a `kind` at all, which pass 1
#               writes down as `interactive` — is a duplicate, which is the
#               closed direction.
#   duplicate   EVERY OTHER live record carrying this id: a session record in
#               another window of this same profile, or any record at all in
#               ANOTHER profile's `sessions/` beside this window's own. That is
#               AMENDMENT 18(h)'s second live process. The MEASURED shape was the
#               second one — four times on 2026-09-14, the last at 18:14Z, the
#               second record sat in another profile's directory, and 18(h) says
#               why, *"on a launcher-configured workstation every profile's
#               `projects/` is one shared directory … which is also why a
#               duplicate is one `--resume` away"* — but the rule it states is
#               one live PROCESS per transcript, not one per profile.
#   unrelated   THIS WINDOW CARRIES NO RECORD OF THIS TRANSCRIPT AT ALL, so this
#               read says nothing about the processes that do. That is not
#               timidity: `live_holder` answers "is any session this row names
#               alive" and Amendment 8(f) rules an ORPHAN reported and never
#               refused, while `lane_forks` answers about a fork. A rule that
#               counted every live record here would overturn both from a read
#               that was not asked about either. ONE CALLER TAKES IT AS A
#               BLOCKER ANYWAY AND SAYS SO WHERE IT DOES: `lane-start`'s
#               `dup_check`, asked about the ONE id a run is about to resume,
#               where an `unrelated` holder is a second live process on the very
#               file that run is about to open (Amendment 18(h), *"never
#               launches a second resume of it"*). That is a narrower question
#               than this verdict answers, so the narrowing lives at that call
#               site and not in this table.
#
# 0 with rows, 8 with none, 1 where the records could not be read, 64 no uuid.
transcript_holders() {   # <session uuid>
  th_id="${1-}"; [ -n "$th_id" ] || return 64
  th_files=""; th_match=""; th_err=""; th_f=""; th_blob=""
  th_pid=""; th_kind=""; th_tgt=""; th_where=""; th_verdict=""; th_out=""
  # `th_here_prof` AND `th_here` AMONG THEM, and the omission was not cosmetic:
  # this file runs under `set -u` (line 292), pass 2's `[ -z "$th_here_prof" ]`
  # is reached for the FIRST record that is not this window's, and an unset
  # variable there exits the shell with `unbound variable` — a 1 every caller
  # reads as "the records could not be read" and refuses on. It cost the suite's
  # `the same lane live in THIS window is not a collision`, which asks
  # `lane-start` for an exit 0 and got `dup_check`'s fail-closed 1.
  th_here=""; th_here_prof=""; th_prof=""; th_wrc=0; th_final=""
  SESSION_FILES_ERR=""
  here_context
  th_files="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-tf.XXXXXX" 2>/dev/null || printf '')"
  th_match="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-tm.XXXXXX" 2>/dev/null || printf '')"
  th_err="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-te.XXXXXX" 2>/dev/null || printf '')"
  if [ -z "$th_files" ] || [ -z "$th_match" ] || [ -z "$th_err" ]; then
    rm -f -- "$th_files" "$th_match" "$th_err" 2>/dev/null || :
    SESSION_FILES_ERR="could not create a temporary file under ${TMPDIR:-/tmp}"
    return 1
  fi
  # NOT `$( )`: session_files sets SESSION_FILES_ERR, and a subshell would keep
  # the reason for the failure to itself.
  if ! session_files > "$th_files"; then
    rm -f -- "$th_files" "$th_match" "$th_err"
    return 1
  fi
  if [ ! -s "$th_files" ]; then
    rm -f -- "$th_files" "$th_match" "$th_err"
    return 8
  fi
  # The locale and the NUL separator for the reason `live_holder` states above:
  # these are arbitrary bytes and BSD `tr` prints nothing at all for a multibyte
  # character in a UTF-8 locale.
  LC_ALL=C tr '\n' '\0' < "$th_files" | xargs -0 grep -l -F -e "\"sessionId\":\"$th_id\"" > "$th_match" 2>"$th_err" || :
  if [ -s "$th_err" ]; then
    SESSION_FILES_ERR="$(LC_ALL=C tr '\n' ';' < "$th_err" | LC_ALL=C cut -c1-300)"
    rm -f -- "$th_files" "$th_match" "$th_err"
    return 1
  fi
  rm -f -- "$th_files" "$th_err"
  while IFS= read -r th_f; do
    [ -n "$th_f" ] || continue
    th_blob="$(cat -- "$th_f" 2>/dev/null || :)"
    [ -n "$th_blob" ] || continue
    # The id is matched EXACTLY and not by the grep alone: a record naming this
    # uuid inside some other field would otherwise be counted as a holder.
    [ "$(lc "$(jstr "$th_blob" sessionId)")" = "$(lc "$th_id")" ] || continue
    record_is_live "$th_blob" || continue
    th_pid="$(jnum "$th_blob" pid)"
    th_kind="$(jstr "$th_blob" kind)"
    th_tgt="$(jstr "$th_blob" tmux)"
    th_where=bg
    if record_fields_are_session "$th_kind" && [ -n "$th_tgt" ]; then
      th_wrc=0
      record_window_state "$th_tgt" || th_wrc=$?
      case "$th_wrc" in
        0) th_where="window ${th_tgt%.*}" ;;
        1) th_where="window ${th_tgt%.*} (gone)" ;;
        *) th_where="window ${th_tgt%.*} (not asked)" ;;
      esac
    elif record_fields_are_session "$th_kind"; then
      th_where="no window"
    fi
    th_here=no
    if [ -n "$th_tgt" ] && [ -n "$LANES_THIS_WINDOW" ] && [ "${th_tgt%.*}" = "$LANES_THIS_WINDOW" ]; then
      th_here=yes
    elif pid_under "$th_pid" "$LANES_PANE_PID"; then
      th_here=yes
    fi
    th_prof="$(record_profile "$th_f")"
    [ "$th_here" = yes ] && [ -z "$th_here_prof" ] && th_here_prof="$th_prof"
    th_out="${th_out}${th_pid:-unknown}${US}${th_kind:-interactive}${US}${th_tgt:-none}${US}${th_prof}${US}${th_where}${US}${th_here}${US}${th_f}
"
  done < "$th_match"
  rm -f -- "$th_match"
  [ -n "$th_out" ] || return 8
  # PASS 2 — THE VERDICT, WHICH NEEDS THE WHOLE SET AND SO CANNOT BE MADE ABOVE.
  th_final=""
  while IFS="$US" read -r tv_pid tv_kind tv_tgt tv_prof tv_where tv_here tv_file; do
    [ -n "${tv_pid:-}" ] || continue
    if [ "$tv_here" = yes ]; then
      tv_v=here
    elif [ -z "$th_here_prof" ]; then
      tv_v=unrelated
    elif [ "$tv_prof" = "$th_here_prof" ] && [ "$tv_kind" = bg ]; then
      tv_v=companion
    else
      tv_v=duplicate
    fi
    th_final="${th_final}${tv_pid}${US}${tv_kind}${US}${tv_tgt}${US}${tv_prof}${US}${tv_where}${US}${tv_v}${US}${tv_file}
"
  done <<EOF
$th_out
EOF
  printf '%s' "$th_final"
  return 0
}

# The UTC of the lane's last `STARTED` or `RESUMED` — Amendment 18(b)'s BINDING,
# read from the lane's own log out of `origin/<branch>` like every other state
# read. Clause (h) rule 2 compares a record's `nameSince` against it: a rename
# OLDER than the binding is a title this window inherited, not an instruction
# somebody has just given. 0 with the stamp, 8 where the log names none, 1 where
# it could not be read.
lane_binding_utc() {   # <lane>
  lbu_lines=""; lbu_rc=0
  lbu_lines="$(lane_log_events "$1")" || lbu_rc=$?
  [ "$lbu_rc" = 0 ] || return 1
  lbu_v="$(printf '%s\n' "$lbu_lines" | awk -F"$US" '$3 == "STARTED" || $3 == "RESUMED" { v = $1 } END { if (v != "") print v }')"
  [ -n "$lbu_v" ] || return 8
  printf '%s\n' "$lbu_v"
}

# ------------------------------------------------- (h)'s ONE ACT ON A PANE
#
# M1, ratified: *"the guard and the `SessionStart` hook rename by TYPING
# `/rename <lane>` into the session's own tmux pane with `tmux send-keys`: the
# only path that exists, run from inside the pane, only after the prompt has
# been refused and only while the pane's current command is `claude`."*
#
# THE PANE'S CURRENT COMMAND IS ASKED FIRST, and a pane that is running anything
# else is NOT typed into: `/rename openRepoTools-3` typed at a shell is a command
# that does not exist, and typed into an editor it is text somebody did not
# write.
#
# `claude` AND NOTHING ELSE, which is M1's own word — *"only while the pane's
# current command is `claude`"*. This test read `claude|node` for one round, on
# the reasoning that the harness is a node program and this format reports the
# process rather than the wrapper; MEASURED on Eagle 2026-09-14T23:4xZ, across
# the twelve panes tmux had, it is not: eleven lane panes report `claude`, two
# report `bash` (a pane whose session is under a launcher wrapper) and one
# `zsh`, and no pane reports `node` at all. So `node` bought nothing here and
# would have let a stray Node REPL in a pane take `/rename <lane>` as input
# (Copilot round 4 on this PR). A pane this refuses is not a lock that failed:
# the caller prints the line for the person to type, which is the cure — and on
# this estate today the `bash` panes are exactly where they will read it.
#
#   0  typed
#   1  no tmux, or `send-keys` itself refused
#   8  the pane's current command could not be read — fail closed, type nothing
#   9  the pane is running something else
guard_type() {   # <pane target> <the line to type>
  gt_pane="${1-}"; gt_text="${2-}"
  [ -n "$gt_text" ] || return 1
  command -v tmux >/dev/null 2>&1 || return 1
  # THE RECORD'S PANE, ELSE THIS ONE — AND THIS ONE IS THE RIGHT FALLBACK
  # BECAUSE OF WHERE THIS CODE RUNS. The pane comes from the live record's
  # `tmux` field, and the harness has been seen to write NO `tmux` at all for a
  # process plainly in a window (Amendment 8, ruling (g)'s third fact) — a
  # record `transcript_holders` and `record_is_here` still place HERE, by the
  # pane's own process tree. With an empty target the lock used to print "tmux
  # would not take the keys" and type nothing, for a session whose name it could
  # have fixed (Copilot round 2 on this PR). Both callers of this function run
  # INSIDE the session's own pane — a `UserPromptSubmit` hook and a
  # `SessionStart` hook do — so `#{pane_id}` with no `-t` is that session's
  # pane, asked of tmux rather than guessed, and M1's condition below is still
  # asked of whatever pane this resolves to.
  [ -n "$gt_pane" ] || gt_pane="$(tmux display-message -p '#{pane_id}' 2>/dev/null || :)"
  [ -n "$gt_pane" ] || return 1
  gt_cmd="$(tmux_window_field "$gt_pane" '#{pane_current_command}' 2>/dev/null || :)"
  [ -n "$gt_cmd" ] || return 8
  case "$gt_cmd" in claude) : ;; *) return 9 ;; esac
  tmux send-keys -t "$gt_pane" "$gt_text" Enter 2>/dev/null || return 1
  return 0
}

# THE PENDING OFFER, held per session id and expiring with the session (clause
# (h) rule 2). It is a file and not a variable because the next prompt is a
# different process: `$CLAUDE_CONFIG_DIR/lanes/offers/<uuid>`, the harness's own
# per-profile configuration directory, which is where a fact about one session
# belongs and is not the register.
guard_offer_file() {   # <session uuid>
  printf '%s/lanes/offers/%s\n' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${1-}"
}

# `lane-start`, found the way every word in this toolset finds its siblings:
# beside this file first — `--install` places them in one directory — then on
# PATH. One resolution, so a workstation with two copies never reads one and
# runs the other. `$LANES_LANE_START` is the seam the suite sets.
#
# NAMED AS A SIBLING OF THIS FILE AND NOT OF ANY PARTICULAR WORD, because
# Amendment 18 Addendum 2 (in force 2026-09-14T16:50:32Z) takes `restart` off a
# person's PATH altogether — "i think we can drop restart as a cli command and
# keep it inside a claude session with /restart … lane does all the things a
# user wants" — and opensoft/openRepoTools#43 removes the file. A comment that
# pointed at it for its resolution order would name a file that is going.
guard_lane_start() {
  if [ -n "${LANES_LANE_START:-}" ]; then printf '%s\n' "$LANES_LANE_START"; return 0; fi
  if [ -x "$SCRIPT_DIR/lane-start" ]; then printf '%s\n' "$SCRIPT_DIR/lane-start"; return 0; fi
  command -v lane-start 2>/dev/null || printf ''
}

# ------------------------------------------------------- the triple, printed
#
# EVERY REFUSAL PRINTS THE THREE NAMES AS THEY STAND, and prints them ONCE
# however many things are wrong. What a person sees is the state and then the
# one command, which is F-B6's rule — filled in, never `<repo> <n>`.
G_WINREF=""; G_WINNAME=""; G_ID=""; G_NAME=""; G_SRC=""; G_PID=""; G_PROF=""
G_ROW=""; G_LANE=""; G_SES_LANE=""
GUARD_TRIPLE_DONE=0
guard_triple() {
  [ "$GUARD_TRIPLE_DONE" = 0 ] || return 0
  GUARD_TRIPLE_DONE=1
  gt_s="${G_ID:-unknown} '${G_NAME:-none}'"
  [ -n "$G_SRC" ] && gt_s="$gt_s (nameSource $G_SRC)"
  [ -n "$G_PID" ] && gt_s="$gt_s pid $G_PID"
  [ -n "$G_PROF" ] && gt_s="$gt_s profile $G_PROF"
  note "THE NAME GUARD REFUSES THIS PROMPT (lane-collision-protocol Amendment 12). The three names:"
  note "  window   ${G_WINREF:-not in tmux} '${G_WINNAME:-none}'"
  note "  session  $gt_s"
  note "  row      ${G_ROW:-not read}"
  return 0
}

# THE ONE BYPASS, NAMED WHERE A PERSON COULD OTHERWISE BE STUCK (clause (d)).
# There is no environment flag that turns this guard off, deliberately; Claude's
# own `--safe-mode` disables every hook and is visible in the prompt box, and a
# session started that way is not a lane session and may not write the register
# or claim an object. It is printed by the INDETERMINATE refusals — the reads
# that could not be made — and not by the mismatches, which have a cure of their
# own one line above.
guard_bypass() {
  printf '%s' "If this workstation cannot answer at all, \`claude --safe-mode\` runs with every hook off — and a session started that way is NOT a lane session: it may not write the register or claim an object."
}

# <why> [<the one command, filled in>] — the shape of every row of the (b)
# table: the triple, one sentence saying what is wrong, and one line to type.
guard_refuse() {
  guard_triple
  note "$1"
  [ -n "${2-}" ] && note "run: $2"
  return 2
}

# ============================== `guard` ==============================
#
# THE (b) TABLE, ONE ROW PER STATE AND ONE CURE EACH, in the amendment's own
# order. Every message prints the register's own spelling of the lane
# (Amendment 15) and every command is filled in.
#
#   the window is not a lane, the session name parses as `<repo>-<n>`
#       -> `lane-start --no-launch <repo> <n>`               THE 2026-09-10 CASE
#   the window is not a lane, and neither is the session name
#       -> `lane-start <repo> <n>` for the lane this work is — the guard cannot
#          name it
#   the window is a lane, this uuid is the row's LAST id, the session name is
#   not a lane name (untitled, a fallback, `<lane> (N)`, any word that does not
#   parse)                       -> THE LOCK RENAMES IT, and says so
#   … the session name is ANOTHER lane's and a PERSON set it after the binding
#                                -> THE OFFER (D5)
#   the window is a lane, this uuid is IN the cell but not last
#       -> Amendment 8's cure: exit, `lane-start <repo> <n>`
#   the window is a lane, this uuid is in NO row
#       -> Amendment 8's cure: `lane-start --no-launch <repo> <n>`
#   the window is a lane whose name matches TWO rows, or the register cannot be
#   read                         -> refuse naming the read
#   not inside tmux at all       -> refuse (D2): a lane runs in a tmux window
#                                   named for it
#
# AND THE AGREEING CASE IS SILENT AND COSTS NOTHING, which is the property that
# makes a hook at every prompt bearable at all.
guard_run() {   # <the hook's JSON, on stdin already read>
  gr_json="${1-}"

  # ---- (e) SCOPE, and the two exemptions are the cheapest tests there are.
  #
  # A SUBAGENT IS EXEMPT: subagents do not submit prompts, and the lane that
  # runs them has already passed this guard. The hook input carries `agent_id`
  # for one and nothing else does.
  [ -z "$(jstr "$gr_json" agent_id)" ] || return 0
  # OUTSIDE THE PROJECTS ROOT THE GUARD IS SILENT (D1). A name there is a title
  # and nothing more. INPUT THAT NAMES NO `cwd` AT ALL is not "outside": it is a
  # read that did not happen, and clause (d) refuses those.
  gr_cwd="$(jstr "$gr_json" cwd)"
  if [ -z "$gr_cwd" ]; then
    guard_refuse "the hook input carried no \`cwd\`, so whether this session is under the projects root — the whole of clause (e)'s scope — could not be read, and an indeterminate read refuses (Amendment 12(d)). $(guard_bypass)"
    return 2
  fi
  under_projects_root "$gr_cwd" "${PROJECTS_ROOT:-$HOME/projects}" || return 0

  G_ID="$(lc "$(jstr "$gr_json" session_id)")"
  gr_prompt="$(jstr "$gr_json" prompt)"

  # ---- THE WORKSPACE. Every other subcommand dies 1 here (the dispatcher's
  # own guard, which this verb is exempt from); this one refuses with 2,
  # because 1 does not block a prompt and clause (d) is fail CLOSED: a register
  # that cannot be located is not a register that agrees.
  if [ -z "$LANES_REPO" ] || [ -z "$LANES_DIR" ] || [ ! -f "$LANES_FILE" ]; then
    guard_refuse "the ROW cannot be read, so the triple cannot be verified — and a triple that cannot be verified is not a triple that agrees (Amendment 12(d)). $(lanes_workspace_why) $(guard_bypass)"
    return 2
  fi

  # ---- (b)'s LAST ROW: NOT INSIDE TMUX AT ALL (D2, "Refuse").
  here_context
  if [ -z "$LANES_THIS_WINDOW" ]; then
    if [ -z "${TMUX:-}" ]; then
      guard_refuse "this session is not in a tmux window at all, and a lane RUNS in a tmux window named for it (Rule 4, Amendment 2). Open one and start the lane there." "lane-start <repo> <n>   (in a tmux window)"
    else
      guard_refuse "tmux did not answer \`display-message -p '#{session_name}:#{window_id}'\`, so the WINDOW half of the triple could not be read — and an indeterminate read refuses (Amendment 12(d)). $(guard_bypass)"
    fi
    return 2
  fi
  G_WINREF="$LANES_THIS_WINDOW"
  G_WINNAME="$(tmux display-message -p '#W' 2>/dev/null || :)"
  if [ -z "$G_WINNAME" ]; then
    guard_refuse "tmux did not answer \`display-message -p '#W'\` for $G_WINREF, so the WINDOW's name could not be read — and an indeterminate read refuses (Amendment 12(d)). $(guard_bypass)"
    return 2
  fi

  # ---- THE LIVE RECORD FOR THIS SESSION, AND AMENDMENT 18(h)'s COUNT, IN ONE
  # READ. The hook is handed its own `session_id` by the harness, so the
  # question asked is "which live processes carry THIS transcript", which is
  # both halves at once and is the cheap shape (`transcript_holders` states the
  # measurement). `window_session` asks the other question — "what is live in
  # this window" — by parsing every record on the workstation, and at 11.8 s
  # against 329 of them on 2026-09-14 it cannot run inside a five-second hook.
  #
  # NOT `$( )`: `transcript_holders` sets `SESSION_FILES_ERR`, and a subshell
  # would keep the reason for the failure to itself.
  gr_tmp="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-gd.XXXXXX" 2>/dev/null || printf '')"
  if [ -z "$gr_tmp" ]; then
    guard_refuse "no temporary file could be made under ${TMPDIR:-/tmp}, so this workstation's session records could not be read (Amendment 12(d)). $(guard_bypass)"
    return 2
  fi
  gr_rc=0
  transcript_holders "$G_ID" > "$gr_tmp" || gr_rc=$?
  if [ "$gr_rc" != 0 ] && [ "$gr_rc" != 8 ]; then
    rm -f -- "$gr_tmp"
    guard_refuse "this workstation's session records could not be read (${SESSION_FILES_ERR:-unknown error}), so the SESSION's own name could not be read — and an indeterminate read refuses (Amendment 12(d)). $(guard_bypass)"
    return 2
  fi
  gr_here=""; gr_here_tgt=""; gr_others=""
  while IFS="$US" read -r gh_pid gh_kind gh_tgt gh_prof gh_where gh_verdict gh_file; do
    [ -n "${gh_pid:-}" ] || continue
    # A COMPANION IS NEITHER — not this window's record and not a second
    # process — so it is passed over in silence, which is Amendment 8 ruling
    # (g)'s own posture. Two records of ONE session in ONE pane are that
    # session seen twice, and the WINDOWED one is the better witness of it.
    case "$gh_verdict" in
      here)
        if [ -z "$gr_here" ] || { [ "$gr_here_tgt" = none ] && [ "$gh_tgt" != none ]; }; then
          gr_here="$gh_pid$US$gh_kind$US$gh_tgt$US$gh_prof$US$gh_file"; gr_here_tgt="$gh_tgt"
        fi ;;
      duplicate)
        gr_others="${gr_others}${gr_others:+, }pid $gh_pid ($gh_where, kind $gh_kind, profile $gh_prof)" ;;
    esac
  done < "$gr_tmp"
  rm -f -- "$gr_tmp"
  if [ -z "$gr_here" ]; then
    guard_refuse "no live session record in THIS window ($G_WINREF) carries this session id, so the SESSION's own name could not be read — and an indeterminate read refuses (Amendment 12(d)). The records were read; none of them is this window's. $(guard_bypass)"
    return 2
  fi
  IFS="$US" read -r G_PID gr_kind gr_tgt G_PROF gr_file <<<"$gr_here"
  gr_blob="$(cat -- "$gr_file" 2>/dev/null || :)"
  G_NAME="$(jstr "$gr_blob" name)"
  G_SRC="$(jstr "$gr_blob" nameSource)"
  gr_since="$(jnum "$gr_blob" nameSince)"
  # THE PANE ONLY FROM A TARGET THAT NAMES THIS WINDOW. `here` is true by the
  # record's target OR by the pane's own process tree, and tmux REUSES window
  # ids — so a record that is here BY ANCESTRY can carry a target another
  # window now answers to, and `/rename` typed into it would land in somebody
  # else's pane. M1's gate cannot catch that one: the other pane is running
  # `claude` too (Copilot round 3 on this PR). Where the record's target does
  # not name this window the pane is left EMPTY, and `guard_type` asks tmux for
  # the pane this hook is running in, which is the session's own.
  gr_pane=""
  if [ -n "$gr_tgt" ] && [ -n "$LANES_THIS_WINDOW" ] && [ "${gr_tgt%.*}" = "$LANES_THIS_WINDOW" ]; then
    case "$gr_tgt" in *.%*) gr_pane="${gr_tgt##*.}" ;; esac
  fi

  # ---- THE ROW, from `origin/<branch>` as this checkout last had it (R19), and
  # every comparison case-insensitive with the register's spelling printed
  # (Amendment 15).
  gr_hits="$(rows_named_ci "$G_WINNAME" 2>/dev/null || :)"
  gr_n="$(printf '%s' "$gr_hits" | grep -c . || :)"
  if [ "$gr_n" -gt 1 ]; then
    guard_refuse "the register holds $gr_n rows whose lane names differ only by case for this window's name '$G_WINNAME': $(printf '%s' "$gr_hits" | tr '\n' ' '). A lane name is ONE name under any case (Amendment 15), so no read under it is unambiguous and a register that cannot be read is not a register that agrees (Amendment 12(b))." "merge them into one row (Amendment 15(d)) — append the newer row's session id(s) to the older row's session cell, in order, and remove the newer row in the SAME commit"
    return 2
  fi
  if [ "$gr_n" = 1 ]; then G_LANE="$gr_hits"
  elif lane_shaped "$G_WINNAME"; then G_LANE="$G_WINNAME"
  fi

  gr_snhits="$(rows_named_ci "$G_NAME" 2>/dev/null || :)"
  gr_snn="$(printf '%s' "$gr_snhits" | grep -c . || :)"
  if [ "$gr_snn" -gt 1 ]; then
    guard_refuse "the register holds $gr_snn rows whose lane names differ only by case for this session's name '$G_NAME': $(printf '%s' "$gr_snhits" | tr '\n' ' '). A lane name is ONE name under any case (Amendment 15)." "merge them into one row (Amendment 15(d))"
    return 2
  fi
  if [ "$gr_snn" = 1 ]; then G_SES_LANE="$gr_snhits"
  elif lane_shaped "$G_NAME"; then G_SES_LANE="$G_NAME"
  fi

  gr_ids=""; gr_last=""
  if [ -n "$G_LANE" ]; then
    gr_ids="$(session_ids_of_lane "$G_LANE" 2>/dev/null || :)"
    gr_last="$(printf '%s\n' "$gr_ids" | grep . | tail -n1 || :)"
    if [ -n "$(row_of_lane "$G_LANE" 2>/dev/null || :)" ]; then
      G_ROW="\`$G_LANE\` — last session ${gr_last:-none recorded}"
    else
      G_ROW="the register has no row for \`$G_LANE\`"
    fi
  else
    G_ROW="this window names no lane, so no row is keyed by it"
  fi

  # ---- AMENDMENT 18(h) — ONE LIVE PROCESS PER TRANSCRIPT, ASKED BEFORE THE
  # PENDING OFFER IS ANSWERED. Clause (h) refuses *"every prompt in a process
  # that shares its session id with another live one"*, and THE ANSWER TO THIS
  # GUARD'S OWN QUESTION IS A PROMPT: a `yes` consumed here runs `lane-start`,
  # writes a register row and appends a uuid to a cell, out of a process that
  # may not be writing anything at all — and the offer is held per SESSION ID,
  # so the second process answers the first one's question. The offer is KEPT
  # while the duplicate stands and is answered at the first prompt after the
  # other process is retired (Copilot round 1 on this PR).
  if [ -n "$gr_others" ]; then
    guard_triple
    note "ANOTHER LIVE PROCESS CARRIES THIS SESSION ID ($G_ID): $gr_others."
    note "A transcript is held by ONE live process (Amendment 18(h), ratified 2026-09-14): two of them append to one file, each overwriting what the other wrote, and the row records an id that two processes answer for. Measured four times on 2026-09-14, the last at 18:14Z — a harness \`--fork-session\` in a background pty host beside the interactive resume, its record in ANOTHER profile's sessions/ directory."
    if [ -n "$G_LANE" ]; then
      note "retire the other one — it proves the process is this lane's duplicate and prints Amendment 6(d)'s act for it, and it ends, writes and kills nothing:"
      note "run: lane-end $G_LANE --retire <pid>"
    else
      note "retire the other one: lane-end <lane> --retire <pid>. This window names no lane, so which lane it is is yours to name."
    fi
    return 2
  fi

  # ---- THE PENDING OFFER, ANSWERED BEFORE THE TABLE BELOW IS CONSULTED
  # (clause (h) rule 2). The answer prompt is the person's reply to a question
  # this guard asked, it is consumed here and never reaches the model, and the
  # triple still disagrees BECAUSE of the rename being answered — so this
  # cannot wait behind the table below. It DOES wait behind 18(h)'s count
  # above, for the reason stated there.
  gr_off="$(guard_offer_file "$G_ID")"
  if [ -f "$gr_off" ]; then
    guard_answer "$gr_off" "$gr_prompt" "$gr_pane"
    return 2
  fi

  # ---- AMENDMENT 18 CLAUSES (d) AND (e) PLUG IN HERE, AND NOT IN THIS PULL
  # REQUEST. Both are reads of THIS lane's own object log, made at this point
  # for the same reason (h)'s count is: the lane is known, nothing has been
  # judged yet, and a refusal here costs the prompt and nothing else.
  #
  #   (d) a `HANDOFF-REQUESTED` newer than this session's binding and not yet
  #       answered by a `PAUSED` of its own -> refuse this one prompt, naming
  #       who asked and from where, and type `/handoff --exit requested by …`
  #       into this pane ((h)1's mechanism, which `guard_type` already is);
  #   (e) a `PAUSED … on behalf of <this uuid>` newer than this session's
  #       binding that THIS session did not write -> refuse EVERY prompt from
  #       then on, naming the line and who forced it, until the person here
  #       runs the handoff themselves or ends the session.
  #
  # NEITHER CAN BE BUILT YET AND THAT IS A DEPENDENCY, not a deferral: (d)'s
  # answer IS Amendment 17(a)'s handoff under `--exit` (opensoft/openRepoTools#36)
  # and (e)'s line is written by the `--force` writer Amendment 18 adoption act 1
  # adds (#38). A guard that refused on a line no writer in this estate can yet
  # produce would be refusing on a read of a log that never carries it — and a
  # guard that TYPED `/handoff --exit` into a pane where that flag does not exist
  # would type a command into somebody's session that does nothing. #38 is where
  # both land, and Amendment 18's own adoption list puts it after this one.

  # ---- (b) ROWS 1 AND 2: THE WINDOW IS NOT A LANE.
  if [ -z "$G_LANE" ]; then
    if [ -n "$G_SES_LANE" ]; then
      guard_refuse "this window is named '$G_WINNAME', which is no lane, while the SESSION is named for lane $G_SES_LANE — so nothing binds this conversation to a row, no surface would refuse a second window taking the same lane, and the handoff this session writes is one only this profile can find. THAT IS THE 2026-09-10 CASE, which ran for three days." "lane-start --no-launch $(lane_start_args "$G_SES_LANE")"
    else
      guard_refuse "neither this window ('$G_WINNAME') nor this session ('${G_NAME:-none}') names a lane, so the guard cannot name one either: WHICH lane this work is is yours to say, and a guard that guessed would bind a window to a row nobody chose." "lane-start <repo> <n>   (for the lane this work is)"
    fi
    return 2
  fi

  # ---- THE WINDOW IS A LANE. Where the uuid sits in the row's cell decides
  # which of the next four rows applies, and the cell is a HISTORY written
  # oldest first whose LAST id is the lane (Amendment 6(b)).
  if [ -n "$gr_last" ] && [ "$G_ID" = "$gr_last" ]; then
    if [ "$(lc "$G_NAME")" = "$(lc "$G_LANE")" ]; then
      # THE THREE AGREE. Under Amendment 15 they agree under any case — and the
      # ROW's spelling is the one the session carries, so a name that differs
      # only by case is renamed to it rather than refused for ever.
      [ "$G_NAME" = "$G_LANE" ] && return 0
      guard_lock_rename "$gr_pane" "spells the lane '$G_NAME' where the register's row spells it '$G_LANE', and a lane name is ONE name under any case whose canonical spelling is the row's (Amendment 15)"
      return 2
    fi
    if [ -n "$G_SES_LANE" ] && [ "$(lc "$G_SES_LANE")" != "$(lc "$G_LANE")" ] \
       && [ "${G_SRC:-}" = user ] && guard_rename_is_newer "$G_LANE" "$gr_since"; then
      guard_offer "$gr_off" "$gr_pane"
      return 2
    fi
    guard_lock_rename "$gr_pane" "is '${G_NAME:-none}', which is not the lane's name"
    return 2
  fi

  if [ -n "$gr_ids" ] && printf '%s\n' "$gr_ids" | grep -qx -F -- "$G_ID"; then
    guard_refuse "this is a SUPERSEDED transcript of lane $G_LANE: the row's session cell carries $G_ID but ENDS on $gr_last, so the conversation in this window is not the lane's and renaming it would not make it one. Exit this session and start the lane, which resumes the id the row ends on." "lane-start $(lane_start_args "$G_LANE")"
    return 2
  fi

  guard_refuse "this window is lane $G_LANE, whose row ${gr_last:+ends on $gr_last and }does not name $G_ID at all — the harness minted a new transcript with nobody acting (a /clear, a usage reset, a profile switch). The lane is right and the ROW is behind, so the cure is the recording act and no relaunch: it reads the live record in this window and appends that uuid to the cell." "lane-start --no-launch $(lane_start_args "$G_LANE")"
  return 2
}

# (h) rule 2's third test: is the rename NEWER than this window's binding?
# Amendment 18(b) makes the binding the lane's last `STARTED`/`RESUMED`, and
# `nameSince` is an epoch in MILLISECONDS (measured on this estate's records,
# 2026-09-14). A rename OLDER than the binding is a title this window inherited
# and not an instruction somebody has just given, so it is drift and the lock
# renames it back. A record with NO `nameSince` — an older harness — cannot be
# told apart either way and is drift too, which is (h)1's default and the
# closed direction. A lane whose log records no binding at all cannot make a
# rename older than one, so there the rename is the instruction.
guard_rename_is_newer() {   # <lane> <nameSince, epoch ms>
  grn_lane="${1-}"; grn_since="${2-}"
  case "$grn_since" in ''|*[!0-9]*) return 1 ;; esac
  grn_utc="$(lane_binding_utc "$grn_lane" 2>/dev/null || :)"
  [ -n "$grn_utc" ] || return 0
  grn_e="$(epoch_of "$grn_utc")"
  [ -n "$grn_e" ] || return 0
  [ "$grn_since" -gt "$((grn_e * 1000))" ]
}

# ------------------------------------------------------ (h)1: THE LOCK RENAMES
#
# The guard refuses THIS ONE PROMPT so the rename lands first, types
# `/rename <lane>` into this pane, and says so. M1's conditions are
# `guard_type`'s; every outcome but a successful typing prints the line for the
# person to type themselves, because a lock that silently did nothing is a lock
# nobody knows is broken.
guard_lock_rename() {   # <pane> <what is wrong with the name, as a clause>
  glr_pane="${1-}"; glr_why="${2-}"
  glr_rc=0
  guard_type "$glr_pane" "/rename $G_LANE" || glr_rc=$?
  guard_triple
  note "the session name $glr_why, and under the projects root the session name is not the person's to set freely — it is the LANE's (Amendment 12(h), THE LOCK)."
  case "$glr_rc" in
    0) note "SO IT HAS BEEN RENAMED FOR YOU: \`/rename $G_LANE\` was typed into this pane ($glr_pane), which is the only path a running session's name has (M1). This one prompt is refused so the rename lands first — send it again." ;;
    8) note "the pane's current command could not be read, so NOTHING was typed: a \`/rename\` typed at a shell is a command that does not exist and typed into an editor is text nobody wrote. Type it yourself: /rename $G_LANE" ;;
    9) note "this pane is not running claude, so NOTHING was typed, for the reason above. Type it in the lane's own pane: /rename $G_LANE" ;;
    *) note "tmux would not take the keys, so NOTHING was typed. Type it yourself: /rename $G_LANE" ;;
  esac
  glr_base="${G_NAME% (*)}"
  if [ -n "$glr_base" ] && [ "$(lc "$glr_base")" = "$(lc "$G_LANE")" ] && [ "$glr_base" != "$G_NAME" ]; then
    note "AND THE ' (N)' SUFFIX IS EVIDENCE: it is exactly what a rename into a title something else still holds mints, so another holder of '$G_LANE' was live when this session was named (Amendment 6(d), ratified decision D4). Naming them is a read of its own, kept off this hook's path because it costs about three seconds: \`lanes-edit.sh forks $G_LANE\`. Retiring one is \`lane-end $G_LANE --retire <pid>\`, which proves it is a fork, prints Amendment 6(d)'s act filled in, and ends, writes and kills nothing."
  fi
  return 2
}

# F-B6 PRINTS EVERY COMMAND FILLED IN, AND THERE IS ONE LANE NAME THAT CANNOT
# BE. `lane_start_args` answers `<repo> <n>` for a lane named under Rule 4's
# `<repo>-<n>` form and `--dir <path> <lane>` for one named before it — and that
# `<path>` is a PLACEHOLDER, because nothing in the register, the window or this
# session says where such a lane's checkout is. Printing it in a diagnostic is
# honest; RUNNING it is not. `lane-start --no-launch --dir '<path>' legacy-ui`
# refuses on a directory that does not exist, and the offer that ran it would
# ask the same question at every prompt afterwards (Copilot round 1 on this PR).
# So the offer SAYS what it cannot fill in and the `yes` refuses instead of
# running it, with the offer kept so that `no` still answers.
guard_args_filled() {   # <lane>
  gaf_a="$(lane_start_args "$1")"
  case "$gaf_a" in *'<path>'*) return 1 ;; esac
  return 0
}

# ------------------------------------------------------------ (h)2: THE OFFER
#
# *"if the user does a rename, then we should offer to move to that lane or
# create a new lane if we do not have one as that name"* (D5, verbatim). The
# one thing the guard never does silently is decide, with nobody acting, which
# of two disagreeing LANES a window belongs to.
guard_offer() {   # <offer file> <pane>
  go_f="${1-}"; go_pane="${2-}"
  mkdir -p -- "${go_f%/*}" 2>/dev/null || :
  { printf 'from=%s\n' "$G_LANE"
    printf 'to=%s\n'   "$G_SES_LANE"
    printf 'uuid=%s\n' "$G_ID"
    printf 'utc=%s\n'  "$(utc_now)"
    printf 'window=%s\n' "$G_WINREF"
    printf 'pane=%s\n'   "$go_pane"
  } > "$go_f" 2>/dev/null || :
  guard_triple
  go_row="$(row_of_lane "$G_SES_LANE" 2>/dev/null || :)"
  if [ -n "$go_row" ]; then
    go_last="$(last_session_id_of_lane "$G_SES_LANE" 2>/dev/null || :)"
    note "you renamed this session to $G_SES_LANE — lane $G_SES_LANE EXISTS, last session ${go_last:-none recorded}."
  else
    note "you renamed this session to $G_SES_LANE — lane $G_SES_LANE DOES NOT EXIST yet."
  fi
  if guard_args_filled "$G_SES_LANE"; then
    note "Reply \`yes\` to move this window to it (creating the lane if there is none: \`lane-start --no-launch $(lane_start_args "$G_SES_LANE")\` is run for you, this window is renamed, the row created or this uuid appended, and $G_LANE is marked MOVED)."
  else
    note "Reply \`yes\` and it will say what it cannot do: $G_SES_LANE is named before Rule 4's \`<repo>-<n>\` form, so \`lane-start\` needs that lane's DIRECTORY and nothing here knows which one it is. Moving this window to it is \`lane-start --no-launch --dir <that lane's checkout> $G_SES_LANE\`, yours to run with the path filled in."
  fi
  note "Reply \`no\` to stay $G_LANE — the session is renamed back with \`/rename $G_LANE\`."
  note "The answer is the NEXT prompt, it is consumed here and never reaches the model, and anything but yes or no asks again. The offer expires with this session."
  [ -f "$go_f" ] || note "(the offer could not be written to $go_f, so the answer will be read as a fresh prompt and this question asked again — which is the safe direction)"
  return 2
}

# ------------- THE UUID INTO THE NEW LANE'S CELL, WHICH `lane-start` MAY NOT DO
#
# CLAUSE (h) RULE 2 NAMES THE END STATE AND RULE 3 REPEATS IT: after a `yes`,
# *"window X, session X, ROW X STAMPED WITH THIS UUID"*. `lane-start --no-launch`
# performs every other part of that and CANNOT perform this one, by a fence that
# is right and stays: its step 3b VETO 1 — Amendment 11 clause (d) rule 1 —
# never takes a uuid that belongs to ANOTHER ROW, and after a rename this uuid
# belongs to `$ga_from`'s. So it mints a fresh id for the new lane instead and
# the person's own transcript is left out of the cell the next resume follows.
#
# MEASURED, AND IT IS A LOOP AND NOT A BLEMISH. In the suite: `yes` moved the
# window to `repoGD-2`, whose row then read `STARTED by 7a01ae69…` while this
# session was `aaaa0012-1111…`. The NEXT prompt therefore finds a lane window
# whose row does not name this transcript — the last row of the (b) table — and
# refuses with `lane-start --no-launch repoGD 2`, which vetoes for the same
# reason and changes nothing. A blocking hook that refuses for ever, on a state
# it created by obeying the person, is the worst outcome this surface has.
#
# SO THE GUARD MAKES THE LAST WRITE ITSELF, and only after the person's `yes`.
# That is not a hole in veto 1: the veto exists for the take nobody asked for —
# *"`lane-start openXfactory-5` typed from a window named `openRepoProject-1`"*,
# Evidence 2(b) — and clause (h) rule 4's own limit is that the lock *"never
# moves a uuid between rows WITHOUT the person's `yes`"*. Here there is one, on
# the record, answered at this very prompt.
#
# THE ANCHOR DISCIPLINE IS `lane-start`'s, unvaried: the anchor is the PUBLISHED
# last id, so a checkout whose copy of the row is older than the one that landed
# REFUSES rather than writing a cell that no longer matches; a row whose cell
# records no uuid at all is anchored on `none recorded`, the one other text a
# cell this act can meet carries, and anything else prints the act and guesses
# at nothing.
#
#   0  the cell now ends on this uuid (it already did, or this appended it)
#   1  it does not, and the reason has been printed with the act that fixes it
guard_bind_uuid() {   # <the lane moved to> <the lane moved from>
  gbu_to="${1-}"; gbu_from="${2-}"
  # THE CACHED REGISTER IS THE ONE FROM BEFORE `lane-start` RAN, and this act is
  # the one place in the file that reads it AFTER a writer has moved it: a row
  # `lane-start` has just CREATED is not in it at all, and the anchor would then
  # be read as "no cell to append to" on the one path that most needs one. Both
  # copies are dropped — the variable this shell holds and the file every
  # subshell reads (A11 Addendum 4 ruling 12) — exactly as `log_sync` drops them
  # after a fetch, and for the same reason: the ref has moved under them.
  LANES_REGISTER_CACHE=""
  gbu_rc="${SE_CACHE_FILE:+$SE_CACHE_FILE.register}"; [ -n "$gbu_rc" ] && rm -f -- "$gbu_rc"
  gbu_last="$(last_session_id_of_lane "$gbu_to" 2>/dev/null || :)"
  [ "$(lc "$gbu_last")" = "$(lc "$G_ID")" ] && return 0
  gbu_anchor="$gbu_last"
  if [ -z "$gbu_anchor" ]; then
    gbu_cell="$(row_cell "$(row_of_lane "$gbu_to" 2>/dev/null || :)" 3 | sed -e 's/^ *//' -e 's/ *$//')"
    # THE TWO TEXTS A CELL THIS ACT CAN MEET CARRIES INSTEAD OF A UUID, and
    # both come from `lane-start` itself: `none recorded` for a row a person
    # wrote by hand, and `pending — set by the session's first act` for a row
    # `lane-start` has just CREATED with neither a minted uuid nor one it was
    # allowed to take (`lane-start:1914`). The second is exactly the state a
    # `yes` to a brand-new lane can leave — veto 1 refuses this window's uuid
    # because the source row still records it, and a run that minted none has
    # nothing else to write — so anchoring only on the first left the cure for
    # the loop unreachable in the one case the loop most needs it (Copilot
    # round 3 on this PR).
    case "$gbu_cell" in
      "none recorded") gbu_anchor="none recorded" ;;
      "pending — set by the session's first act") gbu_anchor="$gbu_cell" ;;
    esac
  fi
  gbu_add="→ harness $G_ID (transcript uuid; profile ${G_PROF:-unknown})"
  gbu_hint="LANES_LANE=$gbu_to lanes-edit.sh append-session-id $gbu_to \"<the session cell's last id>\" \"$gbu_add\""
  if [ -z "$gbu_anchor" ]; then
    note "…but $gbu_to's session cell carries no uuid to append after, and no text this act is willing to anchor on, so THIS TRANSCRIPT IS NOT IN IT. Stamp it as this session's first act, which is Amendment 6(c)'s own remedy:"
    note "   $gbu_hint"
    return 1
  fi
  if LANES_LANE="$gbu_to" "$RESOLVED" append-session-id "$gbu_to" "$gbu_anchor" "$gbu_add" "session cell: the name guard moved this window from $gbu_from on the person's yes (Amendment 12(h) rule 2)" >&2; then
    note "…and $gbu_to's session cell now ends on $G_ID, which is what the next \`lane-start $gbu_to\` resumes."
    return 0
  fi
  note "…but $gbu_to's session cell was NOT extended with $G_ID (this checkout's copy of the row does not carry '$gbu_anchor' exactly once in its SESSION CELL — it may be older than the published one). Its writer's words are above. Stamp it as this session's first act:"
  note "   $gbu_hint"
  return 1
}

# The answer, and it is the whole of clause (h) rule 2's second half.
guard_answer() {   # <offer file> <the prompt> <pane>
  ga_f="${1-}"; ga_p="${2-}"; ga_pane="${3-}"
  ga_from="$(sed -n -e 's/^from=//p' "$ga_f" 2>/dev/null | head -n1)"
  ga_to="$(sed -n -e 's/^to=//p' "$ga_f" 2>/dev/null | head -n1)"
  ga_ans="$(printf '%s' "$ga_p" | tr 'A-Z' 'a-z' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  if [ -z "$ga_from" ] || [ -z "$ga_to" ]; then
    rm -f -- "$ga_f"
    guard_refuse "the pending offer at $ga_f could not be read, so it has been dropped rather than answered on a guess. Send your prompt again and the question will be asked afresh."
    return 2
  fi
  case "$ga_ans" in
  y|yes)
    if ! guard_args_filled "$ga_to"; then
      guard_refuse "lane $ga_to is named before Rule 4's \`<repo>-<n>\` form, so the act that moves this window to it cannot be filled in here: \`lane-start\` needs that lane's DIRECTORY and nothing in the register, the window or this session says which one it is. NOTHING has been renamed, moved or written, and the offer is KEPT — run it yourself with the path, or answer \`no\` to stay $ga_from." "lane-start --no-launch --dir <that lane's checkout> $ga_to"
      return 2
    fi
    ga_start="$(guard_lane_start)"
    if [ -z "$ga_start" ] || [ ! -x "$ga_start" ]; then
      guard_refuse "there is no \`lane-start\` beside this file or on PATH, so this window has NOT moved to $ga_to and NOTHING has been written. The offer is kept: answer \`yes\` again once it is installed (\`openRepoTools --install\`)."
      return 2
    fi
    # THE WINDOW IS RENAMED FIRST, AND THAT ORDER IS LOAD-BEARING. Clause (h)
    # rule 2 lists the acts in it — *"window renamed, row created or this uuid
    # appended to its cell"* — and `lane-start` will not do the second while the
    # first is undone: its step 3b VETO 2 refuses to take the session live in a
    # window NAMED FOR ANOTHER LANE (Amendment 11 clause (d) rule 1, veto 2,
    # `R-A11-12`), which after a `yes` is exactly what this window is. Without
    # the rename the lane would be started and stamped and the person's
    # transcript left OUT of its session cell — the one thing the next resume
    # follows. The veto is right and stays: what changes is that the person has
    # just said this window is the other lane.
    if command -v tmux >/dev/null 2>&1; then
      tmux rename-window "$ga_to" 2>/dev/null ||
        note "the window could not be renamed to $ga_to, so lane-start may refuse to take this session as that lane's (its step 3b veto 2)."
    fi
    ga_rc=0
    # ITS STDOUT IS THE COMMAND IT WOULD HAVE LAUNCHED, and a hook's stdout is
    # not what a person reads: everything this act says goes to stderr, where
    # the blocking reason is shown.
    # UNQUOTED ON PURPOSE: `lane_start_args` prints TWO words, `<repo> <n>` —
    # or `--dir <path> <lane>` for a lane named before the `<repo>-<n>` rule.
    # shellcheck disable=SC2046
    "$ga_start" --no-launch $(lane_start_args "$ga_to") >&2 || ga_rc=$?
    if [ "$ga_rc" != 0 ]; then
      guard_refuse "\`lane-start --no-launch $(lane_start_args "$ga_to")\` exited $ga_rc (its own words are above), so this window has NOT moved and $ga_from has NOT been marked MOVED. The offer is KEPT, so answer \`yes\` again once that refusal is settled, or \`no\` to stay $ga_from."
      return 2
    fi
    rm -f -- "$ga_f"
    guard_triple
    note "MOVED: this window is now lane $ga_to — renamed, and stamped. The prompt that answered the question is consumed; send your work again."
    guard_bind_uuid "$ga_to" "$ga_from" || :
    if [ -n "$(row_of_lane "$ga_from" 2>/dev/null || :)" ]; then
      if "$RESOLVED" append-row-status "$ga_from" "MOVED → $ga_to" >&2; then
        note "…and $ga_from's row records \`MOVED → $ga_to\`."
      else
        note "…but $ga_from's row could NOT be marked (its writer's words are above). Run: lanes-edit.sh append-row-status $ga_from \"MOVED → $ga_to\""
      fi
    else
      note "…and the register has no row for $ga_from, so there is nothing to mark MOVED there."
    fi
    return 2 ;;
  n|no)
    ga_trc=0
    guard_type "$ga_pane" "/rename $ga_from" || ga_trc=$?
    rm -f -- "$ga_f"
    guard_triple
    case "$ga_trc" in
      0) note "STAYING $ga_from: \`/rename $ga_from\` was typed into this pane ($ga_pane) and the window is untouched. The prompt that answered the question is consumed; send your work again." ;;
      *) note "STAYING $ga_from, but the rename could NOT be typed into this pane, so the session is still named $ga_to and the guard will ask again at the next prompt. Type it yourself: /rename $ga_from" ;;
    esac
    return 2 ;;
  *)
    guard_triple
    note "that is not an answer to the pending question, so it has been refused rather than acted on: this window is lane $ga_from and this session is named $ga_to."
    note "Reply \`yes\` to move this window to $ga_to, or \`no\` to stay $ga_from."
    return 2 ;;
  esac
}


# ------------------------------- CLAUSE (f): THE `SessionStart` BLOCK'S LINE
#
# *"Where the record's name differs from the window's lane it prints
# `session name '<x>' was not the lane '<y>' — renamed` and types the rename
# ((h)1), so the first prompt already finds the three agreeing. It stays
# read-only against the register and non-blocking, as Amendment 8 made it; the
# refusal is the `UserPromptSubmit` hook's."*
#
# AND AMENDMENT 18(h)'s READ BESIDE IT, SAID AND NOT ACTED ON: where another
# live process carries this session id, the block NAMES it and the retire act.
# The guard refuses on that; this hook refuses nothing and never will — a hook
# that fails is a hook that breaks the session it was meant to orient (R-A8-1),
# and typing into its own pane writes nothing anywhere, which is why (h)1 gives
# it that one act and no other.
#
# EVERY PATH RETURNS 0. A read that failed prints nothing rather than guessing:
# the guard is the surface that refuses on an indeterminate read, and doing it
# twice, in the hook that may not, would be the same failure one layer up.
ssb_name_line() {   # <session uuid> <lane, or empty>
  snl_id="${1-}"; snl_lane="${2-}"
  [ -n "$snl_id" ] || return 0
  snl_tmp="$(mktemp "${TMPDIR:-/tmp}/lanes-edit-sn.XXXXXX" 2>/dev/null || printf '')"
  [ -n "$snl_tmp" ] || return 0
  snl_rc=0
  # IN A SUBSHELL, AND THAT IS R-A8-1 AND NOT TIDINESS. *"This hook never fails
  # and always exits 0"*; `|| snl_rc=$?` catches a RETURN and catches nothing
  # else, because a fatal inside a function called in this shell — an unbound
  # variable under `set -u`, a `die` on a path nobody expected to reach one —
  # exits the shell itself, `|| :` at the call site and all. Measured: with
  # `th_here_prof` unset, `lanes-edit.sh session-start` exited 1 and printed no
  # block at all, which is precisely the hook breaking the session it was
  # written to orient. Nothing here needs state from the call — the rows come
  # back through a file — so the subshell costs nothing and bounds it.
  ( transcript_holders "$snl_id" ) > "$snl_tmp" 2>/dev/null || snl_rc=$?
  if [ "$snl_rc" != 0 ]; then rm -f -- "$snl_tmp"; return 0; fi
  snl_file=""; snl_tgt=none; snl_others=""
  while IFS="$US" read -r sn_pid sn_kind sn_tgt sn_prof sn_where sn_verdict sn_file; do
    [ -n "${sn_pid:-}" ] || continue
    # The same three-way reading the guard makes, and for the same reasons.
    case "$sn_verdict" in
      here)
        if [ -z "$snl_file" ] || { [ "$snl_tgt" = none ] && [ "$sn_tgt" != none ]; }; then
          snl_file="$sn_file"; snl_tgt="$sn_tgt"
        fi ;;
      duplicate)
        snl_others="${snl_others}${snl_others:+, }pid $sn_pid ($sn_where, kind $sn_kind, profile $sn_prof)" ;;
    esac
  done < "$snl_tmp"
  rm -f -- "$snl_tmp"
  if [ -n "$snl_others" ]; then
    printf 'DEFECT: another live process carries this session id (%s): %s — a transcript is held by ONE live process (Amendment 18(h)), and two of them append to one file. Retire it: lane-end %s --retire <pid>\n' \
      "$snl_id" "$snl_others" "${snl_lane:-<lane>}"
  fi
  [ -n "$snl_lane" ] && [ -n "$snl_file" ] || return 0
  snl_blob="$(cat -- "$snl_file" 2>/dev/null || :)"
  snl_name="$(jstr "$snl_blob" name)"
  [ -n "$snl_name" ] || snl_name=none
  [ "$snl_name" = "$snl_lane" ] && return 0
  # THE SAME FENCE AS THE GUARD'S, for the same reason and in the same words:
  # a record that is here by ancestry can carry another window's target, and
  # this hook types into a pane. `here_context` is asked HERE because the read
  # above it runs in a subshell, which is where its answer would otherwise have
  # stayed.
  # A PERSON'S RENAME TO ANOTHER LANE IS THE GUARD'S TO OFFER, NOT THIS HOOK'S
  # TO UNDO. Clause (f) types the rename for (h)1's case — DRIFT, a name that is
  # no lane's — while (h) rule 2 makes a record whose `nameSource` is `user`,
  # whose name is another lane's, and whose `nameSince` is later than this
  # window's binding an INSTRUCTION, answered `yes` or `no` at the next prompt.
  # This hook runs on every startup, resume, clear and fork, so typing over such
  # a name would erase the person's choice before the guard could put the
  # question (Copilot round 4 on this PR): a rename, then a `/clear`, and the
  # offer never happens. It is SAID here and left to the prompt that follows.
  snl_src="$(jstr "$snl_blob" nameSource)"
  snl_since="$(jnum "$snl_blob" nameSince)"
  if [ "${snl_src:-}" = user ] && [ "$(lc "$snl_name")" != "$(lc "$snl_lane")" ] \
     && { [ -n "$(rows_named_ci "$snl_name" 2>/dev/null || :)" ] || lane_shaped "$snl_name"; } \
     && guard_rename_is_newer "$snl_lane" "$snl_since"; then
    printf "session name '%s' is a lane name YOU set, newer than this window's binding to '%s' — the name guard offers the move at your next prompt (Amendment 12(h) rule 2); nothing was renamed here\n" \
      "$snl_name" "$snl_lane"
    return 0
  fi
  here_context
  snl_pane=""
  if [ -n "$snl_tgt" ] && [ "$snl_tgt" != none ] && [ -n "$LANES_THIS_WINDOW" ] \
     && [ "${snl_tgt%.*}" = "$LANES_THIS_WINDOW" ]; then
    case "$snl_tgt" in *.%*) snl_pane="${snl_tgt##*.}" ;; esac
  fi
  snl_trc=0
  guard_type "$snl_pane" "/rename $snl_lane" || snl_trc=$?
  if [ "$snl_trc" = 0 ]; then
    printf "session name '%s' was not the lane '%s' — renamed\n" "$snl_name" "$snl_lane"
  else
    printf "session name '%s' is not the lane '%s' — run: /rename %s\n" "$snl_name" "$snl_lane" "$snl_lane"
  fi
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

# THE SIBLING READS NAME THE OBJECT, NOT ITS DIGITS (Amendment 8). Rule 1's
# reads 2 and 3 searched for the bare slug as a SUBSTRING, and a number is a
# substring of almost everything. Measured live on 2026-09-12 against the
# governing repository, `gh pr list --search 15` answered with PR #16 and PR
# #10 — GitHub had matched the digits inside "**15 of the register's 41 rows**"
# — and `ls-remote | grep 15` answered with a branch whose 40-character sha
# merely contains them, all under the heading "existing work on this object".
# A sibling that does not NAME the object is not evidence about it, and evidence
# that is not evidence is how a lane talks itself out of a claim it should make.
#
# TWO READS, TWO TESTS, because the two inputs are not the same kind of text.
#   pr      `gh pr list`'s rows, which are prose. A number in prose is a
#           number; a REFERENCE is `#<n>`, so the hash is required — and its
#           LEFT side is not bounded, because the canonical spelling of the
#           thing being looked for is `owner/repo#15` and the character before
#           the `#` is a letter. A row whose FIRST field is the number itself
#           is kept too: that is the PR the object IS.
#   branch  `ls-remote`'s refs, which are names. `issue-15-fix` names the
#           object and carries no hash, so the bare number as a whole token is
#           the test — after the leading sha is stripped, so a branch is matched
#           by its name and never by the digits of the commit it points at.
# An OpenSpec change directory has a word for a slug and takes the whole-token
# test in both modes.
#
# AND READ 2 FILTERS OVER THE BODY. `gh pr list`'s columns are number, title,
# branch and state; the reference that makes a PR a sibling is almost always in
# its BODY, which is what GitHub's own search matched and what the columns do
# not carry. Filtering the columns alone dropped PR #16 — the PR for this very
# issue, whose body says `brettheap/new-workstation#15` twice — while a filter
# with the hash optional kept #10 instead. So the body is fetched, flattened to
# one line, used for the test, and cut off again before anything is printed:
# under-reporting a sibling is the direction that lets a lane claim what
# somebody is already working on, and it is the one direction Rule 1 cannot
# afford.
ere_quote() { printf '%s' "${1-}" | sed -E 's/[][(){}.^$*+?|\\/]/\\&/g'; }
sibling_filter() {   # <object> [pr|branch]; candidate lines on stdin
  sfl_slug="$(object_slug "$1")"
  sfl_num="$(object_number "$1")"
  sfl_mode="${2:-pr}"
  if [ -z "$sfl_slug" ]; then cat; return 0; fi
  sfl_q="$(ere_quote "$sfl_slug")"
  if [ -n "$sfl_num" ] && [ "$sfl_mode" = pr ]; then
    # `#<n>` anywhere, or the row's own number column.
    awk -v sep="$(printf '\t')" -v n="$sfl_slug" -v re="#$sfl_q([^0-9A-Za-z]|$)" '
      { if ($0 ~ re) { print; next }
        split($0, f, sep); if (f[1] == n) print }'
    return 0
  fi
  sed -E 's/^[0-9a-fA-F]{40}[[:space:]]+//' \
    | grep -E -- "(^|[^0-9A-Za-z])$sfl_q([^0-9A-Za-z]|\$)" || :
}

gh_reads() {
  gr_obj="$1"; gr_repo="$(object_repo "$gr_obj")"; gr_n="$(object_number "$gr_obj")"; gr_slug="$(object_slug "$gr_obj")"
  gr_term="${gr_n:+#$gr_n}"; gr_term="${gr_term:-$gr_slug}"
  if [ "$NO_GITHUB" = 1 ]; then
    printf '1. existing claims on the object: not read (--no-github)\n'
    printf '2. gh pr list --state all --search: not read (--no-github)\n'
    printf '3. git ls-remote --heads: not read (--no-github)\n'
    return 0
  fi
  command -v gh >/dev/null 2>&1 || { note "gh is not on PATH — rerun with --no-github, or install it"; return 1; }
  printf '1. existing `CLAIMED —` comments on %s:\n' "$gr_obj"
  if [ -n "$gr_n" ]; then
    gr_c="$( { gh issue view "$gr_n" --repo "$gr_repo" --comments 2>/dev/null || gh pr view "$gr_n" --repo "$gr_repo" --comments 2>/dev/null; } | grep -n -e 'CLAIMED —' -e 'TAKEOVER —' -e 'RELEASED —' || : )"
  else
    gr_c=""
  fi
  printf '%s\n' "${gr_c:-   none}"
  printf '2. `gh pr list --repo %s --state all --search "%s"`, kept where the row or its body names `%s`:\n' "$gr_repo" "$gr_term" "${gr_n:+#}$gr_slug"
  # The body is fetched for the TEST and cut off before the print. `--json`
  # needs a gh that has it; where it does not, the four columns are filtered on
  # their own, which is strictly less recall and never a wrong answer.
  gr_raw="$(gh pr list --repo "$gr_repo" --state all --search "$gr_term" --limit 20 \
              --json number,title,headRefName,state,body \
              -q '.[] | [.number, .title, .headRefName, .state, (.body // "" | gsub("[\r\n]+"; " "))] | @tsv' 2>/dev/null || :)"
  [ -n "$gr_raw" ] || gr_raw="$(gh pr list --repo "$gr_repo" --state all --search "$gr_term" --limit 20 2>/dev/null || :)"
  gr_p="$(printf '%s\n' "$gr_raw" | sibling_filter "$gr_obj" pr | cut -f1-4 || :)"
  printf '%s\n' "${gr_p:-   none}"
  printf '3. `git ls-remote --heads git@github.com:%s` branches naming `%s` as a whole token:\n' "$gr_repo" "$gr_slug"
  gr_b="$(git ls-remote --heads "git@github.com:$gr_repo.git" 2>/dev/null | sibling_filter "$gr_obj" branch || :)"
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
      # THE JOIN IS FILE NAME → HOLDER ROW, AND THE TWO NEED NOT SPELL THE LANE
      # ALIKE (Copilot round 4). The file carries the row's canonical spelling
      # from the moment the first write renames it (Amendment 15); the holder row
      # carries whatever the winning LINE was typed with, which an append-only
      # log never rewrites. Byte for byte this join missed the winner and the
      # rescan fell back to the sorted-first holder — a CLAIM-LOST naming the
      # wrong lane. Literal and case-insensitive, both defects at once.
      if [ -n "$(printf '%s\n' "$fl_holders" | rows_named "$fl_lane")" ]; then printf '%s\n' "$fl_lane"; return 0; fi
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
  # CASE-INSENSITIVE ON BOTH EXCLUSIONS (Amendment 15), for the reason `claim`-s
  # own pre-check carries it: these two remove THIS lane and the lane it is
  # taking over from the set of rivals, and the row each removes carries whatever
  # spelling the winning line used. Byte for byte, a lane whose earlier CLAIMED
  # says `repohold-1` under the row `repoHold-1` loses the race to ITSELF and
  # writes a CLAIM-LOST naming itself as the winner — measured, exit 7.
  # AND LITERAL, not `grep -iv` (Copilot round 4): a name is not a pattern, and a
  # rival removed because a `.` in THIS lane's name matched its spelling is a
  # race this read reports as won when it was lost.
  crh="$(state_events | lane_states_on "$CLAIM_OBJ" | holders_of "$CLAIM_OBJ" \
         | rows_not_named "$CLAIM_LANE" | { [ -n "$CLAIM_SKIP" ] && rows_not_named "$CLAIM_SKIP" || cat; } || :)"
  [ -n "$crh" ] || return 0
  CLAIM_WINNER="$(first_landed_of "$CLAIM_OBJ" "$crh")"
  IFS="$US" read -r crh_lane crh_verb crh_utc crh_rest <<EOF
$(printf '%s\n' "$crh" | rows_named "$CLAIM_WINNER" | head -n1)
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
[ -n "$cmd" ] || { sed -n -e '1,2d' -e '/^#/!q' -e 's/^# \{0,1\}//' -e p "$RESOLVED"; exit 2; }
shift || :
# `session-start` is EXEMPT. It is a hook: it never writes, and it must exit 0
# even where there is no register to read at all — a hook that dies is a hook
# that breaks the session it was meant to orient.
# EVERY WRITER REFUSES WHERE THIS CONTAINER HAS NO CONFIGURED WORKSTATION
# (Amendment 11, decision 8(d), `R-A11-14`). ONE GUARD AT THE DISPATCHER rather
# than one per writer: `WS` is built into every event line's `session <uuid>@<ws>`
# and into every commit subject this file writes, so a container id reaches the
# append-only log through any of nine subcommands, and nine copies of one rule is
# how eight of them would come to disagree. The READS are untouched — a read in
# front of every launch may not refuse, and one that answers nothing for a
# workstation nobody configured is telling the truth.
case "$cmd" in
  append-row-status|replace-in-row|append-session-id|append-line|add-row|commit|log|claim|release)
    ws_why="$(lanes_workstation_why "$WS_SOURCE")"
    [ -z "$ws_why" ] || die "$ws_why" 2 ;;
esac

# `guard` JOINS THAT EXEMPTION AND REFUSES FOR ITSELF (Amendment 12(d)). It is
# a hook too, and a blocking one: `die … 1` here would print the workspace
# refusal and let the prompt THROUGH, because only exit 2 blocks a
# `UserPromptSubmit`. So the verb takes the same reads itself and answers them
# with a 2 — fail CLOSED, which is the clause.
case "$cmd" in
  session-start|guard) : ;;
  *)
    if [ -z "$LANES_REPO" ] || [ -z "$LANES_DIR" ]; then
      die "$(lanes_workspace_why)" 1
    fi
    [ -f "$LANES_FILE" ] || die "registry not found: $LANES_FILE
    $LANES_REPO is the workspace repository $(lanes_ws_yaml) names, and it
    carries no lanes/LANES.md. A repository seeded by \`openRepoTools wip init\`
    has one; re-run it (it is idempotent) or pull that checkout." 1
    ;;
esac

case "$cmd" in
  verify-row)
    lane="${1-}"; [ -n "$lane" ] || die "usage: verify-row <lane>" 2
    lane="$(canon_lane "$lane")" || exit 2
    n="$(row_line "$lane")" || exit 2
    row="$(sed -n -e "${n}p" "$LANES_FILE")"
    # Bash substrings, not `cut -c` and `rev`: `${#row}` counts CHARACTERS,
    # and a register row is full of `·` `—` `→`, so a byte-counting `cut`
    # disagrees with the length printed one field earlier — and BSD `rev` and
    # `cut` answer `Illegal byte sequence` on the same row rather than
    # disagreeing. The same rule `lane-end:566` states (R-A9-11).
    # `${row: -200}` on a row SHORTER than 200 answers the empty string, where
    # `rev | cut | rev` answered the whole row — so the short case is asked
    # for explicitly rather than left to the expansion.
    row_tail="$row"; [ "${#row}" -gt 200 ] && row_tail="${row: -200}"
    printf 'lane   : %s\nline   : %s\nlength : %s chars\nfirst200: %s\nlast200 : %s\n' \
      "$lane" "$n" "${#row}" "${row:0:200}" "$row_tail"
    ;;

  append-row-status)
    lane="${1-}"; text="${2-}"
    [ -n "$lane" ] && [ -n "$text" ] || die "usage: append-row-status <lane> \"<text>\"" 2
    # AMENDMENT 15 — THE ROW'S OWN SPELLING, BEFORE THE LOCK AND BEFORE THE
    # EDIT. `row_line` below finds the same line either way; this is what the
    # COMMIT SUBJECT and every message here then carry, and a register whose
    # rows differ only by case is refused here rather than edited at random.
    lane="$(canon_lane "$lane")" || exit 2
    acquire_lock; handle_preexisting
    n="$(row_line "$lane")" || exit 2
    row="$(sed -n -e "${n}p" "$LANES_FILE")"
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
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    acquire_lock; handle_preexisting
    n="$(row_line "$lane")" || exit 2
    row="$(sed -n -e "${n}p" "$LANES_FILE")"
    c="$(count_occurrences "$row" "$old")" || exit 2
    [ "$c" = 1 ] || die "'$old' occurs $c times in lane $lane's row (line $n); exactly 1 required" 2
    # NOT `${row/"$old"/"$new"}` (A9 Addendum 4, R-A9-11). Bash 4.3 and later
    # read the quotes there as "this half is a literal, not a pattern"; BASH
    # 3.2 KEEPS THE ONES AROUND THE REPLACEMENT AS CHARACTERS, so on macOS
    # every `replace-in-row` wrote its new text WRAPPED IN DOUBLE QUOTES. The
    # macOS job read `| "RETIRED 2026-09-13T20:39:04Z" · …` where the register
    # wanted `| RETIRED 2026-…`, and nothing else noticed: the write succeeded,
    # the commit landed, and the row was quietly wrong. (The pattern half is
    # unaffected — 3.2 does remove those quotes, which is how the replacement
    # got made at all.) Prefix and suffix instead, so `$new` never enters the
    # pattern machinery: `%%` leaves the shortest prefix and `#` the text after
    # the first match, and `count_occurrences` above has already proved there
    # is exactly one.
    ri_pre="${row%%"$old"*}"; ri_post="${row#*"$old"}"
    replace_line "$n" "$ri_pre$new$ri_post"
    msg="LANES($lane@$WS): ${why:-replace-in-row}"
    [ -n "$PRE_DIRTY_LANES" ] && msg="$msg + sweeps uncommitted edit to row $PRE_DIRTY_LANES"
    commit_push "$msg"
    ;;

  # AMENDMENT 8, R-A8-4 — THE UUID APPEND IS CELL-SCOPED.
  #
  # `replace-in-row` refuses unless its anchor occurs exactly once in the WHOLE
  # ROW, and the anchor for a session-cell append is a transcript uuid — which
  # the 6(c) stamp writes into the STATE cell again on every launch (`RESUMED by
  # <uuid> … launching claude --resume <uuid>` — twice more per launched start).
  # Measured against `origin/main` on 2026-09-12, `openRepoProject-1`'s own row
  # carries its current uuid THREE times and its previous one three times, so
  # the single most load-bearing new act in Amendment 8(d) — recording the
  # transcript the harness minted — could not run on the lane the amendment was
  # written for.
  #
  # So the anchor is matched INSIDE THE SESSION CELL and nowhere else, and must
  # occur exactly once THERE. `replace-in-row`'s whole-row rule is unchanged and
  # is still right for what it is for: a state cell says the same thing in two
  # places all the time, and a blind replace there would rewrite the wrong one.
  #
  # AND THE TEXT IS APPENDED AT THE END OF THE CELL, NOT AT THE ANCHOR. This is
  # the second half of the same finding and it is not cosmetic: the cell spells
  # its ids `harness `<uuid>`` — inside backticks — so a replace AT a bare-uuid
  # anchor writes `harness `<uuid> → harness <new>`` and puts the new id inside
  # the old one's code span. The anchor's job is to prove that the cell this
  # checkout holds is the published one the caller read (Amendment 6(b): the
  # cell is a HISTORY, oldest first, and the last id is the lane's current
  # session); the APPEND's job is to add a lineage after all of them. Those are
  # two different positions, and conflating them corrupted the cell.
  #
  # Anything that is not an append — a cell that must really be rewritten — is
  # `replace-in-row`'s business, in front of a person.
  append-session-id)
    lane="${1-}"; old="${2-}"; add="${3-}"; why="${4-}"
    [ -n "$lane" ] && [ -n "$old" ] && [ -n "$add" ] \
      || die "usage: append-session-id <lane> \"<anchor in the session cell>\" \"<text to append to the cell>\" [\"<why>\"]" 2
    case "$add" in
      *"|"*) die "append-session-id's appended text may not contain '|': it would forge a cell boundary in the row. Got '$add'." 2 ;;
    esac
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    acquire_lock; handle_preexisting
    n="$(row_line "$lane")" || exit 2
    row="$(sed -n -e "${n}p" "$LANES_FILE")"
    row_split_session_cell "$row" || die "lane $lane's row (line $n) does not have three '|' before its session cell ends; refusing to touch it" 2
    c="$(count_occurrences "$RSC_CELL" "$old")" || exit 2
    if [ "$c" != 1 ]; then
      whole="$(count_occurrences "$row" "$old" || printf '?')"
      die "'$old' occurs $c time(s) in lane $lane's SESSION CELL (line $n); exactly 1 required there. The row as a whole carries it $whole time(s) — that difference is exactly why this act is cell-scoped and not replace-in-row." 2
    fi
    replace_line "$n" "$RSC_HEAD$(rstrip_spaces "$RSC_CELL") $add $RSC_TAIL"
    msg="LANES($lane@$WS): ${why:-append-session-id}"
    [ -n "$PRE_DIRTY_LANES" ] && msg="$msg + sweeps uncommitted edit to row $PRE_DIRTY_LANES"
    commit_push "$msg"
    ;;

  append-line)
    text="${1-}"; [ -n "$text" ] || die "usage: append-line \"<text>\"" 2
    lane_tag="${LANES_LANE:-}"
    [ -z "$lane_tag" ] || lane_tag="$(canon_lane "$lane_tag")" || exit 2
    if [ -z "$lane_tag" ]; then
      cand="$(lane_from_text "$text")"
      # AMENDMENT 15 — `row_lane_ci` ALONE, and the exact branch that used to
      # sit above it is the same question asked twice now that `row_line`
      # compares case-insensitively too. It answers with the ROW's spelling
      # rather than the LINE's, which is what Rule 10's wire form needs: the
      # line says `Lane: openxfactory-2` in lowercase and the row's token is
      # `openXfactory-2`. It is still the register that decides — a candidate no
      # row matches prints nothing, so "…names no lane at all" is never
      # attributed to a lane called "at".
      #
      # AND THE 15(d) PAIR IS A REFUSAL HERE TOO, not an absence. `row_lane_ci`
      # answers EMPTY for two rows exactly as it does for none, and an empty
      # `lane_tag` is a commit attributed to nobody — a writer carrying on over
      # the one register state the amendment says every writer refuses (Copilot
      # round 1 on openRepoTools#41). `canon_lane` is asked for its STATUS only;
      # which of "no row" and "one row" it is stays `row_lane_ci`-s answer.
      if [ -n "$cand" ]; then
        canon_lane "$cand" >/dev/null || exit 2
        lane_tag="$(row_lane_ci "$cand")"
      fi
    fi
    acquire_lock; handle_preexisting
    append_text_line "$text"
    msg="LANES(${lane_tag:-unknown}@$WS): append line — ${text:0:72}"
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
    # AMENDMENT 15(a) — A ROW UNDER ANY CASE IS A ROW, AND THE REFUSAL NAMES IT.
    # This is the act the 2026-09-13 incident got past: `lane-start openxfactory
    # 2` found no row for `openXfactory-2` and appended a second one for a lane
    # that already had one. `row_line`'s exactly-one test cannot be the whole
    # gate here, because two rows differing only by case make it fail for the
    # OTHER reason and a failed `row_line` used to read as "no row, go ahead".
    #
    # AND THE PUBLISHED ROWS ARE ASKED TOO — R19, AND R30's FETCH IN FRONT OF IT
    # (Copilot round 4 on openRepoTools#41). The scan was of `$LANES_FILE` alone,
    # which a fetch does not move: on a checkout that is behind, a row `origin`
    # already carries as `repoCase-1` is invisible here, this appends
    # `repocase-1`, and `commit_push`'s own rebase then publishes the pair — the
    # exact duplicate 15(a) makes this command refuse, arrived at through the one
    # file the check never read. BOTH sets are asked and either is the refusal:
    # the local scan stays because a row added here and not yet pushed is on no
    # `origin` at all, and the published scan is the one the incident needed.
    if [ -n "$lane_new" ]; then
      log_sync
      ar_hits="$(rows_named_ci_local "$lane_new")"
      ar_pub="$(rows_named_ci "$lane_new" 2>/dev/null || :)"
      ar_all="$(printf '%s\n%s\n' "$ar_hits" "$ar_pub" | grep -v '^$' | LC_ALL=C sort -u || :)"
      ar_n="$(printf '%s' "$ar_all" | grep -c . || :)"
      ar_ln="$(printf '%s' "$ar_hits" | grep -c . || :)"
      if [ "$ar_n" -gt 0 ]; then
        ar_more=""
        [ "$ar_n" -gt 1 ] && ar_more=" Those $ar_n rows differ only by case and are themselves the refusal: merge them into one row first (Amendment 15(d))."
        ar_where="Use append-row-status / replace-in-row on the row that is there."
        [ "$ar_ln" = 0 ] && ar_where="That row is on origin/$LANES_BRANCH and this checkout has not pulled it, so adding one here would make two the moment this push rebases. Pull first — \`git -C $LANES_REPO pull --rebase\` — then use append-row-status / replace-in-row on the row that is there."
        die "lane '$lane_new' already has a row, spelled $(printf '%s\n' "$ar_all" | tr '\n' ' ')— a lane name is ONE name under any case (Amendment 15(a)), so a row under another case IS that lane's row and this would be a second one. $ar_where$ar_more" 2
      fi
    fi
    acquire_lock; handle_preexisting
    append_text_line "$row"
    msg="LANES(${lane_new:-${LANES_LANE:-unknown}}@$WS): add row"
    [ -n "$PRE_DIRTY_LANES" ] && msg="$msg + sweeps uncommitted edit to row $PRE_DIRTY_LANES"
    commit_push "$msg"
    ;;

  commit)
    msg="${1-}"; [ -n "$msg" ] || die "usage: commit \"<message>\"" 2
    # AMENDMENT 15 — `$LANES_LANE` passes through the resolver like every
    # `<lane>` argument does: it is the attribution in this commit's subject and
    # the name the "touches other rows" test compares against.
    [ -z "${LANES_LANE:-}" ] || LANES_LANE="$(canon_lane "$LANES_LANE")" || exit 2
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
    verb=""; obj_raw=""; ref=""; payload=""; text=""; home_override=""; utc_override=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --no-github) NO_GITHUB=1; shift ;;
        # AMENDMENT 17, adoption act 7 — THE LATE RECORD'S OWN DATE, AND
        # NOTHING ELSE USES IT. A `PAUSED` written after the fact for a swap
        # that never ran names the moment the OLD SESSION ENDED, not the moment
        # the shell writing it ran: `lane-handoff --late --at <UTC>` is the one
        # caller, and its own rule is that the line may only be written where it
        # is still the lane's last one (this log is append-only and FILE ORDER
        # is what every state read means by "last"). The shape is checked here
        # because a UTC field this parser cannot read is a line no reader can
        # date — and the log is never rewritten.
        --utc)       utc_override="${2-}"; [ -n "$utc_override" ] || die "--utc needs a UTC instant" 2; shift 2 ;;
        --utc=*)     utc_override="${1#--utc=}"; [ -n "$utc_override" ] || die "--utc needs a UTC instant" 2; shift ;;
        --home)      home_override="${2-}"; [ -n "$home_override" ] || die "--home needs owner/repo" 2; shift 2 ;;
        --home=*)    home_override="${1#--home=}"; [ -n "$home_override" ] || die "--home needs owner/repo" 2; shift ;;
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
    # AMENDMENT 15 — AFTER THE FETCH AND BEFORE EVERY READ AND WRITE BELOW IT.
    # The resolver reads the PUBLISHED register (R19), so it is asked once
    # `log_sync` has moved the ref — and what it answers is the lane this line
    # is WRITTEN with, the file it is written to, and the commit subject.
    lane="$(canon_lane "$lane")" || exit 2
    home="$(resolve_home "$lane" "$home_override")" || exit $?
    obj="$(canon_object "$obj_raw" "$home")" || exit 2
    if is_lane_verb "$verb"; then
      is_lane_object "$obj" || die "'$verb' is a lane verb: its object is lane:<name>, not $obj" 2
    else
      ! is_lane_object "$obj" || die "'$verb' is an object verb: lane:<name> is not one of its objects" 2
    fi
    log_utc="$(utc_now)"
    if [ -n "$utc_override" ]; then
      # `--utc` IS THE LATE `PAUSED`'s SEAM AND HAS NO OTHER CALLER (Amendment
      # 17, adoption act 7; Copilot round 2 on openRepoTools#47). The parser
      # above takes the option for every verb and only its SHAPE was checked
      # here, so a `STARTED` or a `RESUMED` could be dated by hand — and this
      # log is append-only with FILE ORDER deciding which line is a lane's
      # last, so a hand-dated line changes what every state read reports about
      # a lane that is running. The one line that legitimately carries its own
      # date is the record a swap never left, and `lane-handoff --late` has its
      # own rule for when even that may be written.
      [ "$verb" = PAUSED ] || die "--utc dates the LATE PAUSED that a swap never left (Amendment 17, adoption act 7) and nothing else — '$verb' is not one. Every other line is dated by the clock of the act that wrote it, because this log is append-only and a line dated by hand is a line whose order no reader can trust. Write it without --utc." 2
      case "$utc_override" in
        [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z) log_utc="$utc_override" ;;
        *) die "--utc takes a UTC instant spelled as this log spells it, YYYY-MM-DDTHH:MM:SSZ — '$utc_override' is not one, and a line nothing can date is a line no reader can order" 2 ;;
      esac
    fi
    write_event "$lane" "$verb" "$obj" "$ref" "$payload" "$text" "$log_utc" "$(session_for "$lane")"
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
        --home=*)    home_override="${1#--home=}"; [ -n "$home_override" ] || die "--home needs owner/repo" 2; shift ;;
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
    # AND THE EXEMPTION IS A PATH, SO ITS AMBIGUITY IS THIS CLAIM'S (Copilot
    # round 4): two logs differing only by case are a refusal, not a pathspec.
    claim_log="$(log_path_ci "$lane")" || exit 2
    refuse_dirty_checkout claim "$claim_log" "$LANES_PATH"

    # 1. FETCH FIRST OF ALL — then resolve `--home` against the lane's STARTED
    #    line (R30), canonicalise the object, and pre-check against what has
    #    actually LANDED on main. Never against a working tree, which can be
    #    anything, and never against a log this checkout has not pulled: a home
    #    a peer recorded is on `origin/<branch>` and nowhere else here.
    log_sync
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    home="$(resolve_home "$lane" "$home_override")" || exit $?
    obj="$(canon_object "$obj_raw" "$home")" || exit 2
    ! is_lane_object "$obj" || die "a lane is not a claimable object" 2
    takeover_payload=""; takeover_note=""; takeover_from=""; takeover_reason_phrase=""
    # CASE-INSENSITIVE, FOR THE SAME REASON THE KEY ABOVE IS LOWER-CASED
    # (Amendment 15). This is the lane REMOVING ITSELF from the holders of the
    # object it is about to claim, and the row it removes carries whatever
    # spelling the winning line used. Byte for byte, a lane whose own earlier
    # CLAIMED says `repohold-1` under the row `repoHold-1` is refused its own
    # object. AND LITERAL rather than `grep -iv` (Copilot round 4): `repo.-1`
    # excluding the rival `repoX-1` is a claim taken over a hold that is open.
    held="$(state_events | lane_states_on "$obj" | holders_of "$obj" | rows_not_named "$lane" || :)"
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
      # ISSUE #30 — a holder whose LANE is dead is takeable WHATEVER ITS VERB,
      # bypassing both gates below: neither one was ever about the lane being
      # gone, and a dead lane's OPENED PR has no CLAIMED to be stale in the
      # first place. `holder_is_dead` is checked first and, alone, decides
      # this branch; it is refused (as today) below wherever it says no.
      if holder_is_dead "$h_lane"; then
        takeover_from="$h_lane"
        takeover_note="lane $h_lane is dead (log ends $HOLDER_DEAD_VERB, no live session on this workstation, issue #30)"
        # A DIFFERENT PHRASE FOR THE PUBLIC COMMENT (Copilot round 3, PR #61):
        # the formatter below used to say every takeover was "of the stale
        # claim" unconditionally, which is simply false for this branch — the
        # object may be an OPENED PR that was never a CLAIMED issue to begin
        # with, and even a CLAIMED one is takeable here whatever its age. The
        # audit comment a person outside this estate reads must not misstate
        # why.
        takeover_reason_phrase=" (takeover of a dead lane's hold: $takeover_note)"
      else
        if [ "$h_verb" != CLAIMED ]; then
          # NAMES ITS OWN VERB, NOT ONLY THE THREE THAT USED TO BE POSSIBLE
          # HERE (Copilot round 8, PR #61): before issue #30, `$h_verb` could
          # only be OPENED, LANDING or WITHDRAWN by the time this branch is
          # reached (a live lane's own TAKEOVER on an object it still holds
          # falls through the `!= CLAIMED` test the same way) — but a dead
          # lane's own un-superseded TAKEOVER (an earlier stale-claim takeover
          # this lane never followed with a CLOSED/RELEASED/LANDED) reaches
          # here too when THIS lane is confirmed alive, and the enumeration
          # left it unnamed.
          die "--force takes over a stale CLAIMED and nothing else: $obj is $h_verb by lane $h_lane. An open TAKEOVER, OPENED, LANDING or WITHDRAWN is not a stale claim, and lane $h_lane's own log does not end on ENDED or RETIRED either (or a live session on this workstation still holds it)." 2
        fi
        if ! claim_is_stale "$h_lane" "$obj" "$h_utc" "$h_file" "$h_line"; then
          die "--force refused: lane $h_lane's claim on $obj is $(age_of "$h_utc") old (threshold ${STALE_HOURS}h), or it is a PR, or that lane has since OPENED a PR naming it. Rule 1 makes a claim takeable only when it is stale, and lane $h_lane's own log does not end on ENDED or RETIRED either (or a live session on this workstation still holds it)." 2
        fi
        takeover_from="$h_lane"
        takeover_note="stale claim by lane $h_lane, posted $h_utc, no PR after ${STALE_HOURS}h"
        takeover_reason_phrase=" (takeover of the stale claim held by lane $takeover_from)"
      fi
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
               "$(log_path_for "$lane")" "${sha:-unknown}" "$takeover_reason_phrase" "$reads")"
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
        --home=*)    home_override="${1#--home=}"; [ -n "$home_override" ] || die "--home needs owner/repo" 2; shift ;;
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
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    home="$(resolve_home "$lane" "$home_override")" || exit $?
    obj="$(canon_object "$obj_raw" "$home")" || exit 2
    ! is_lane_object "$obj" || die "a lane is not a releasable object" 2
    mine="$(state_events | lane_states_on "$obj" | awk -v sep="$US" -v lane="$lane" 'BEGIN{FS=sep} tolower($2) == tolower(lane)' || :)"
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
        --lane=*)    mode="lane";    arg="${1#--lane=}"; [ -n "$arg" ] || die "--lane needs a lane name" 2; shift ;;
        --landing)   mode="landing"; arg="${2-}"; [ -n "$arg" ] || die "--landing needs owner/repo" 2; shift 2 ;;
        --landing=*) mode="landing"; arg="${1#--landing=}"; [ -n "$arg" ] || die "--landing needs owner/repo" 2; shift ;;
        --home)      home_override="${2-}"; [ -n "$home_override" ] || die "--home needs owner/repo" 2; shift 2 ;;
        --home=*)    home_override="${1#--home=}"; [ -n "$home_override" ] || die "--home needs owner/repo" 2; shift ;;
        --no-fetch)  LANES_NO_FETCH=1; shift ;;
        --)          shift ;;
        -*)          die "unknown option '$1' for who" 2 ;;
        *)           [ -z "$arg" ] || die "who takes one argument" 2; arg="$1"; shift ;;
      esac
    done
    [ -n "$arg" ] || die "usage: who <object> | who --lane <lane> | who --landing owner/repo" 2
    log_sync
    case "$mode" in
      lane)    arg="$(canon_lane "$arg")" || exit 2          # Amendment 15
               who_lane "$arg" || exit $? ;;
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

  # ------------------------------------------- Amendment 8: swap and restart

  # Read-only. Exit 0 with rows, 8 with none — 8 is "no record" here exactly as
  # it is everywhere else, so a launcher may gate on it.
  # `swapped` EXITS 64 ON A USAGE ERROR OF ITS OWN, never the dispatcher's 2
  # (clause (c); F-B8, F-W4). The launcher gates its whole Amendment 8 degrade
  # on this subcommand's 2 meaning ONE thing — "this `lanes-edit.sh` predates
  # Amendment 8 and has no `swapped`" — and the dispatcher's unknown-subcommand
  # 2 is exactly that. A caller's own bug must not be indistinguishable from an
  # old helper at the one place the degrade is decided, so it gets a code of its
  # own: 0 rows, 8 none swapped, 64 a bad call, 2 no such subcommand.
  swapped)
    sw_arg=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --) shift ;;
        -*) die "unknown option '$1' for swapped (usage: swapped [<workstation>])" 64 ;;
        *)  [ -z "$sw_arg" ] || die "swapped takes at most one workstation: swapped [<workstation>]" 64
            sw_arg="$1"; shift ;;
      esac
    done
    log_sync
    # SEVEN FIELDS SINCE AMENDMENT 17(b), and the `NF >= 4` gate is unchanged:
    # it is the shape test for a row that got as far as carrying a window, not a
    # count of the fields a row has. `$7` and `$8` are the agent and its
    # transcript, EMPTY for every record written before that amendment.
    sw_out="$(swapped_lanes "${sw_arg:-$WS}" \
              | LC_ALL=C sort -t"$US" -k1,1 -k3,3r -k2,2 \
              | awk -v sep="$US" 'BEGIN { FS = sep; OFS = "\t" } NF >= 4 { print $2, $3, $4, $5, $6, $7, $8 }')"
    if [ -z "$sw_out" ]; then
      note "no lane on ${sw_arg:-$WS} is swapped — no lane's LAST lane-kind line is a PAUSED whose payload begins 'swap;' and names that workstation"
      exit 8
    fi
    printf '%s\n' "$sw_out"
    ;;

  # The SessionStart hook. IT NEVER WRITES, IT NEVER TOUCHES THE NETWORK, AND
  # IT ALWAYS EXITS 0 — the three properties that make it safe to put in front
  # of every session on this workstation. Its stdin is the hook's JSON; with a
  # terminal on stdin nobody piped one, and it is read as empty rather than
  # waited for, because a hook that blocks is worse than a hook that says
  # nothing.
  #
  # AMENDMENT 8, R-A8-1 — THERE IS NO `log_sync` HERE, AND THERE MUST NOT BE.
  # This branch used to fetch: `log_sync` runs `remote_has_branch` (an
  # `ls-remote`) and then a `fetch`, two network round-trips bounded at 60 s
  # EACH, in front of every session start on the workstation — writing
  # `.git/FETCH_HEAD`, objects and `refs/remotes/origin/main`, and advancing
  # `origin/main` under any `lane-start` running at the same time. Amendment 7's
  # "a read fetches first" governs STATE decisions (a claim, a refusal, who
  # holds what); this is an informational block printed at every session start,
  # and it must be fast and offline-safe instead. It reads the checkout AS LAST
  # FETCHED and says how old that is, so a reader can tell a current answer from
  # a stale one. `git_net` is the only door to the network in this file, and
  # nothing on this path opens it.
  session-start)
    if [ -t 0 ]; then ss_json=""; else ss_json="$(cat 2>/dev/null || :)"; fi
    ss_win=""
    command -v tmux >/dev/null 2>&1 && ss_win="$(tmux display-message -p '#W' 2>/dev/null || :)"
    session_start_block "$ss_json" "$ss_win" || :
    exit 0
    ;;

  # AMENDMENT 12 — THE `UserPromptSubmit` HOOK. The ONE surface in this file
  # that refuses a person's work, and the only one whose exit code is read by
  # the harness rather than by a script: 2 BLOCKS the prompt and its stderr is
  # what the person sees (code.claude.com/docs/en/hooks). Every other code lets
  # the prompt through, which is why every refusal below is a 2 and why this
  # verb is exempt from the dispatcher's `die … 1` above.
  #
  # AN ARGUMENT IS A USAGE REFUSAL AND NOT A SHRUG: a hook configured with a
  # stray word is a hook nobody has checked, and passing the prompt through on
  # one is exactly the silence Amendment 12 exists to end.
  guard)
    [ "$#" -eq 0 ] || die "usage: guard   (the UserPromptSubmit hook; the hook's JSON on stdin)" 2
    if [ -t 0 ]; then g_json=""; else g_json="$(cat 2>/dev/null || :)"; fi
    # IN A SUBSHELL, AND EVERY CODE BUT 0 IS A 2. This is clause (d) — *"fail
    # CLOSED"* — made true of the guard's OWN failures and not only of the
    # reads it makes, and it is here because the alternative was measured:
    # `transcript_holders` left `th_here_prof` unset, `set -u` (line 292) took
    # the whole shell down at the first record that was not this window's, and
    # `lanes-edit.sh guard` exited 1. A 1 does not block a `UserPromptSubmit`
    # — only 2 does — so the one defect this guard cannot have, a guard that
    # lets a prompt through in silence, is exactly what a fatal inside it
    # produced. The subshell contains it: `guard_run`'s effects are on the
    # filesystem (the offer file, `lane-start`, the register) and on stderr,
    # all of which cross it, and the only thing lost is shell state nothing
    # reads afterwards.
    #
    # A `die` reached from one of the reads it makes is caught the same way,
    # which is why the arm maps EVERY unexpected code rather than listing the
    # ones known today.
    g_rc=0
    ( guard_run "$g_json" ) || g_rc=$?
    case "$g_rc" in
      0 | 2) exit "$g_rc" ;;
      *) note "THE NAME GUARD ITSELF FAILED (exit $g_rc), so the three names were not verified — and a triple that cannot be verified is not a triple that agrees (Amendment 12(d)). This prompt is refused rather than let through, because only a 2 blocks one and a guard that fails open is the silence this amendment exists to end. $(guard_bypass)"
         exit 2 ;;
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
  # 0 prints `<uuid> <tmux> <name> <pid> <here|elsewhere|orphan>`, US-separated.
  # The fifth field is Amendment 8 ruling (g)'s: the caller must not have to
  # infer whose session it is from the `tmux` column, because a record with no
  # target is not a record in no window, and reading it as one is what refused
  # this lane the window it was running in.
  # AMENDMENT 8(f), R-A8-6 — the row's EARLIER ids, and who is still holding
  # them. Read-only, no fetch of its own (the caller has just made one), and it
  # runs nothing: `lane-end <lane> --retire <pid|uuid>` is printed by the caller
  # and typed by a person (clause (k) rule (e)).
  # 0 with rows, 8 with none, 1 where the records could not be read — the same
  # three answers `live-holder` gives, so a caller reads them the same way.
  idle-holders)
    lane="${1-}"; [ -n "$lane" ] || die "usage: idle-holders <lane>" 2
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    idle_holders "$lane"; ih_rc=$?
    case "$ih_rc" in
      0) : ;;
      8) exit 8 ;;
      *) die "could not read this workstation's session records for lane $lane: ${SESSION_FILES_ERR:-unknown error}." 1 ;;
    esac
    ;;

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
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    lh_ids="$( { session_ids_of_lane "$lane" 2>/dev/null || :
                 session_ids_local_of_lane "$lane" 2>/dev/null || :; } | awk 'NF && !seen[$0]++')"
    # DECISION 8(e) — A `--fork-session` OF THIS LANE'S TRANSCRIPT IS NEVER A
    # HOLDER, AND SAYING SO IS PART OF THE ANSWER. `live_holder` already
    # answers only about ids the ROW carries, so a fork — which has a new id
    # and the lane's title — cannot be returned by it and could pass unseen.
    # Amendment 8 ruling (g) skipped a `kind: bg` companion; Evidence 6's fork
    # was one AND was orchestrating, so the rule is extended to forks BY ID.
    # The note is on stderr, so the 0/8 contract this read's two callers gate
    # on is untouched.
    lh_fk=""; lh_fkrc=0
    lh_fk="$(lane_forks "$lane" 2>/dev/null)" || lh_fkrc=$?
    # ON STDERR, like the DEFECT line below it, so the 0/8 contract this read's
    # two callers gate on is untouched — and said at all, because a fork check
    # that could not be made is not a lane with no fork (#26, `37632b1`).
    case "$lh_fkrc" in
      0 | 8) : ;;
      *) note "this workstation's session records could not be read, so whether a live FORK of lane $lane's transcript is running is NOT established — which is not the same as none. See: lanes-edit.sh forks $lane" ;;
    esac
    if [ -n "$lh_fk" ]; then
      while IFS="$(printf '\t')" read -r lh_fid lh_fpid lh_fkind lh_fcwd; do
        [ -n "${lh_fid:-}" ] || continue
        note "DEFECT: $lh_fid is a live FORK of lane $lane's transcript (pid $lh_fpid, ${lh_fkind:-interactive}, cwd ${lh_fcwd:-unknown}) — it is NOT a holder of this lane and must not write the register. Retire it: lane-end $lane --retire $lh_fpid"
      done <<EOF
$lh_fk
EOF
    fi
    live_holder "$lane" "$lh_ids"; lh_rc=$?
    case "$lh_rc" in
      0) : ;;
      8) exit 8 ;;
      *) die "could not read this workstation's session records for lane $lane: ${SESSION_FILES_ERR:-unknown error}. That is NOT 'no live session holds it' — fix the records or the permissions and re-run." 1 ;;
    esac
    ;;

  # AMENDMENT 8 — which LIVE session is in a tmux WINDOW, keyed on the window
  # and not on a lane's recorded ids. `lane-start` asks it about the window it
  # is run in, because the harness mints a new transcript uuid with nobody
  # acting and that id is in no row for `live-holder` to find. 0 with
  # `<uuid> <tmux> <name> <pid> <profile>` (US-separated), 8 when the records
  # were read and no live one is in that window, 1 when they could not be read.
  window-session)
    wsub="${1-}"; [ -n "$wsub" ] || die "usage: window-session <tmux session>:<window id>" 2
    window_session "$wsub"; wsub_rc=$?
    case "$wsub_rc" in
      0) : ;;
      8) exit 8 ;;
      *) die "could not read this workstation's session records for window $wsub: ${SESSION_FILES_ERR:-unknown error}. That is NOT 'no live session is in that window'." 1 ;;
    esac
    ;;

  # ------------------------- AMENDMENT 18(h): ONE LIVE PROCESS PER TRANSCRIPT
  #
  # THREE CALLERS AND ONE IMPLEMENTATION — `lane-start` before it binds or
  # resumes an id, `lane-end --retire <pid>` when the duplicate's id is the
  # ROW'S OWN (opensoft/openRepoTools#39), and the prompt `guard`. It answers
  # about ONE transcript and says, per live process, where it is and whether it
  # is THIS window's:
  #
  #   <pid><TAB-as-US><kind><US><tmux|none><US><profile><US><where><US><here|other><US><record file>
  #
  # 0 with rows, 8 with none, 1 where the records could not be read, 64 usage.
  # The 1 is the fail-closed one: a caller that read it as 8 would bind a
  # transcript two processes hold, which is the whole defect.
  transcript-holders)
    thub="${1-}"; [ -n "$thub" ] || die "usage: transcript-holders <session uuid>" 64
    transcript_holders "$thub"; thub_rc=$?
    case "$thub_rc" in
      0) : ;;
      8) exit 8 ;;
      64) die "usage: transcript-holders <session uuid>" 64 ;;
      *) die "could not read this workstation's session records for session $thub: ${SESSION_FILES_ERR:-unknown error}. That is NOT 'no other live process carries it', and a caller that read it as one would bind a transcript two processes hold." 1 ;;
    esac
    ;;

  # ------------------------------ AMENDMENT 11, clause (h): the new reads
  #
  # ALL READ-ONLY; all answer out of `origin/<branch>` as every Amendment 7
  # read does; all honour `LANES_NO_FETCH=1`, because each one sits in front of
  # a launch and a launcher must not sit on the network to open a terminal; and
  # all follow Amendment 7(d)'s fail-closed convention — 0 an answer, 8 NO
  # ANSWER, 64 a usage error of their own, and anything else a failed read that
  # a caller must not read as "nothing to report".
  #
  # WITH ONE EXCEPTION, AND IT IS THE ONE EVERY UN-UPGRADED WORKSTATION IS IN:
  # a `lanes-edit.sh` that has never heard of one of these exits **2** for an
  # unknown subcommand, exactly as a pre-Amendment-8 one did for `swapped`.
  # That is A HELPER PREDATING THE AMENDMENT THAT ADDED THE READ — expected and
  # silent — and a caller falls to its next rung there rather than refusing.
  # The two kinds of 2 are told apart by the helper's own WORDS and not by its
  # status: the `*)` arm below says "unknown subcommand" and no other refusal
  # here does.

  # ADOPTION ACT 0 SHIPS `session-lane`, AND IT IS BELOW RATHER THAN HERE.
  # `opensoft/brett-wip#5` @`3719d97` added it and `openRepoTools#24` — MERGED as
# `d4b5710` on this repository's `main`, which is the sha act 3 is cited by from
# here on rather than a branch name — ported that
  # commit into this copy, so this branch carries NO second implementation of it
  # (A11 Addendum 3, CF-T11: act 0 ships FOUR items, and that is the fourth).
  # `3719d97` IS THE MERGE COMMIT. Act 0 merged 2026-09-13T19:14:37Z, squashed,
  # so the draft head `95e7a4c` this comment used to cite is not an ancestor of
  # `origin/main` at all (F-X18, A11 Addendum 4 ruling 13).
  # `/restart`'s step 2(b) and `lane-start`'s step 3b both call the ported arm.

  # The lane bound to a window OF THE ASKING WORKSTATION. Three callers share
  # this one implementation — the launcher's precedence 3, `/restart`'s step
  # 2(c), and the `/lane-swap` skill's step 1 — and it owns the `<@id>`-versus-
  # ref agreement rule for all three (A11 Addendum 2, `R-A11-8`).
  #
  # The optional workstation comes FIRST, exactly as `swapped [<ws>]` takes it,
  # and is told from the ref by shape: a ref is an `@id` or carries a `:`, and
  # a workstation name is neither.
  window-lane)
    wl_a=""; wl_b=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --) shift ;;
        -*) die "unknown option '$1' for window-lane (usage: window-lane [<workstation>] <@id>|<session>:<index>)" 64 ;;
        *)  if   [ -z "$wl_a" ]; then wl_a="$1"
            elif [ -z "$wl_b" ]; then wl_b="$1"
            else die "window-lane takes at most a workstation and one window ref" 64
            fi
            shift ;;
      esac
    done
    if [ -n "$wl_b" ]; then wl_in_ws="$wl_a"; wl_in_ref="$wl_b"
    else                    wl_in_ws="$WS";   wl_in_ref="$wl_a"
    fi
    [ -n "$wl_in_ref" ] || die "usage: window-lane [<workstation>] <@id>|<session>:<index>" 64
    case "$wl_in_ref" in
      @*|*:*) : ;;
      *) die "'$wl_in_ref' is neither an <@id> nor a <session>:<index>. A workstation is given FIRST: window-lane [<workstation>] <ref>" 64 ;;
    esac
    log_sync
    window_lane "$wl_in_ws" "$wl_in_ref"; wl_rc=$?
    case "$wl_rc" in
      0)  : ;;
      8)  exit 8 ;;
      64) die "usage: window-lane [<workstation>] <@id>|<session>:<index>" 64 ;;
      *)  die "window-lane could not read this workstation's records for $wl_in_ref (exit $wl_rc). That is NOT 'no lane is bound to that window'." 1 ;;
    esac
    ;;

  # The lane's RECORDED DIRECTORY: the `dir ` sub-field of its log's LAST
  # lane-kind line carrying one, in file order, unquoted where it was written
  # quoted (Amendment 11 clause (c)). Four callers: `lane-start`'s directory
  # precedence rung 3, the launcher's `--dir` default, `/restart`'s step 3 and
  # `restart`'s own.
  #
  # 8 IS THE ANSWER FOR EVERY LANE THAT HAS NOT STARTED UNDER THIS AMENDMENT,
  # and it is not a failure: adoption act 7 cuts each lane over at its own next
  # start, nothing is backfilled (Amendment 7(i)), and the default
  # `$PROJECTS_ROOT/<repo>` carries it until then, which is what it has always
  # done.
  lane-dir)
    lane="${1-}"; [ -n "$lane" ] || die "usage: lane-dir <lane>" 64
    [ "$#" -le 1 ] || die "lane-dir takes one lane: lane-dir <lane>" 64
    check_lane_name "$lane"
    log_sync
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    # THE READER'S STATUS DECIDES, AS IT DOES IN EVERY OTHER ARM OF THIS CLAUSE
    # (#26, the fail-closed family one layer out). `window-session`, `last-session`,
    # `forks` and `window-lane` all carry this `case`; these two carried
    # `|| :` and then read the EMPTINESS of the output, so a log that could not
    # be read left here as **8** — the pre-cutover answer, which is the one
    # answer every caller of this read treats as *"fall to the next rung"*.
    ld_out="$(lane_payload_field "$lane" dir)"; ld_rc=$?
    case "$ld_rc" in
      0) : ;;
      8) exit 8 ;;
      *) die "lane-dir could not read lane $lane's log (exit $ld_rc). That is NOT 'this lane has no recorded directory', and a caller that read it that way would resolve the directory from the rungs beneath a record it never read (Amendment 7(d))." 1 ;;
    esac
    [ -n "$ld_out" ] || exit 8
    printf '%s\n' "$ld_out"
    ;;

  # THE LANE'S RECORDED PROFILE — `lane-dir`'s sibling, and the same read one
  # sub-field along: the `profile ` of its log's LAST lane-kind line carrying
  # one, unquoted where it was written quoted.
  #
  # IT IS AN ADDITION TO SPEC §11's TABLE AND IS NAMED AS ONE. `restart <lane>`
  # needs exactly two facts about a lane it is not standing in — its directory
  # and its profile — and the directory already had a read of its own. Without
  # this the profile came out of the `lanes` listing, which must consult
  # `state_events` for the held-objects column and so reads EVERY log on the
  # workstation: measured at seventeen seconds on the live register, to answer
  # one question about one lane, on the path a person types to get back to work.
  # One `git show` instead, through the same `lane_payload_field` `lane-dir`
  # uses, so the two cannot disagree about which line is a lane's last.
  #
  # 8 IS THE ANSWER FOR EVERY LANE THAT HAS NOT STARTED UNDER THIS AMENDMENT,
  # and `restart` refuses on it rather than guessing: a wrong profile is a
  # launch into another account.
  lane-profile)
    lane="${1-}"; [ -n "$lane" ] || die "usage: lane-profile <lane>" 64
    [ "$#" -le 1 ] || die "lane-profile takes one lane: lane-profile <lane>" 64
    check_lane_name "$lane"
    log_sync
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    lp_out="$(lane_payload_field "$lane" profile)"; lp_rc=$?
    case "$lp_rc" in
      0) : ;;
      8) exit 8 ;;
      *) die "lane-profile could not read lane $lane's log (exit $lp_rc). That is NOT 'this lane's record names no profile', and a wrong profile is a launch into another account (Amendment 7(d))." 1 ;;
    esac
    [ -n "$lp_out" ] || exit 8
    printf '%s\n' "$lp_out"
    ;;

  # ------------------------------------------- AMENDMENT 17(b): the two reads
  #
  # `lane-agent` and `lane-transcript` are `lane-dir`'s siblings, one sub-field
  # along and through the same `lane_payload_field`, so the four cannot disagree
  # about which line is a lane's last. ONE CALLER EACH TODAY and that is the
  # point of the read existing rather than being inlined: `lane-start` reads the
  # agent to know WHICH LAUNCHER to use with no `--agent`, and reads the
  # transcript to know the id to append to the row's session cell in that
  # agent's own spelling (`Codex <id>`), which is the one id a launch of a
  # non-Claude agent has in hand.
  #
  # 8 IS THE ANSWER FOR EVERY RECORD WRITTEN BEFORE THIS AMENDMENT, and it is
  # not a failure: Amendment 7(i) cuts each lane over at its own next handoff,
  # nothing is backfilled, and `lane-start`'s default of `claude` carries it
  # until then — which is what it has always done.
  lane-agent)
    lane="${1-}"; [ -n "$lane" ] || die "usage: lane-agent <lane>" 64
    [ "$#" -le 1 ] || die "lane-agent takes one lane: lane-agent <lane>" 64
    check_lane_name "$lane"
    log_sync
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15: one name under any case
    la_out="$(lane_payload_field "$lane" agent)"; la_rc=$?
    case "$la_rc" in
      0) : ;;
      8) exit 8 ;;
      *) die "lane-agent could not read lane $lane's log (exit $la_rc). That is NOT 'this lane's record names no agent', and a caller that read it that way would launch the default agent over a lane another one paused (Amendment 7(d))." 1 ;;
    esac
    [ -n "$la_out" ] || exit 8
    printf '%s\n' "$la_out"
    ;;

  lane-transcript)
    lane="${1-}"; [ -n "$lane" ] || die "usage: lane-transcript <lane>" 64
    [ "$#" -le 1 ] || die "lane-transcript takes one lane: lane-transcript <lane>" 64
    check_lane_name "$lane"
    log_sync
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15: one name under any case
    lt_out="$(lane_payload_field "$lane" transcript)"; lt_rc=$?
    case "$lt_rc" in
      0) : ;;
      8) exit 8 ;;
      *) die "lane-transcript could not read lane $lane's log (exit $lt_rc). That is NOT 'this lane's record names no transcript' (Amendment 7(d))." 1 ;;
    esac
    [ -n "$lt_out" ] || exit 8
    printf '%s\n' "$lt_out"
    ;;

  # THE LANE'S LAST LANE-KIND LINE, in FILE ORDER — `<verb><TAB><utc><TAB><session><TAB><payload>`.
  # One caller: `lane-handoff --late`, which may only write the record a swap
  # never left where that line is still a `STARTED` or a `RESUMED` older than
  # the instant the late line claims. This log is APPEND-ONLY and file order is
  # what every state read means by "last", so a `PAUSED` appended after the
  # relaunch's `RESUMED` would make a lane that is RUNNING read as paused — and
  # this read is how that is refused instead of written.
  #
  # IT IS THE LANE'S OWN LINES AND NOT A FORK'S, which is `lane_row_facts`' rule
  # one function along (decision 8(c): a fork is never the lane).
  lane-last)
    lane="${1-}"; [ -n "$lane" ] || die "usage: lane-last <lane>" 64
    [ "$#" -le 1 ] || die "lane-last takes one lane: lane-last <lane>" 64
    check_lane_name "$lane"
    log_sync
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15: one name under any case
    ll_lines=""; ll_rc=0
    ll_lines="$(lane_log_events "$lane")" || ll_rc=$?
    [ "$ll_rc" = 0 ] || die "lane-last could not read lane $lane's log (exit $ll_rc). That is NOT 'this lane has no lane-kind line' (Amendment 7(d))." 1
    ll_out="$(printf '%s\n' "$ll_lines" | awk -F"$US" -v OFS='	' '
      $3 == "STARTED" || $3 == "PAUSED" || $3 == "RESUMED" || $3 == "ENDED" || $3 == "RETIRED" {
        if (substr($8, 1, 5) == "fork ") next
        v = $3; u = $1; s = $4; p = $8
      }
      END { if (v != "") print v, u, s, p }')"
    [ -n "$ll_out" ] || exit 8
    printf '%s\n' "$ll_out"
    ;;

  # THE WORKSPACE REPOSITORY'S PATH — the one resolver, printed. Amendment 9(a)
  # is explicit that a second way to find one thing is a second answer, and
  # `lane-handoff` needs this path to resolve the handoff cell of a row whose
  # spelling is repository-relative. Every other reader of it is in this file.
  workspace-root)
    [ "$#" = 0 ] || die "workspace-root takes no arguments" 64
    wr_out="$(lanes_workspace_root 2>/dev/null || :)"
    [ -n "$wr_out" ] || die "$(lanes_workspace_why)" 1
    printf '%s\n' "$wr_out"
    ;;

  # The lane's RESUME TARGET, read robustly (Amendment 11 clause (d) rules 3
  # and 4): the last uuid in the published row's session cell WHATEVER SHAPE
  # THAT CELL IS IN, and failing that the session field of the lane's last
  # `PAUSED` or `RESUMED` line. Never a title, and never an exit — a caller
  # that gets 8 has learnt that no uuid is knowable from either source, which
  # is the ONLY state in which Amendment 8(d)'s title fallback is reachable.
  last-session)
    lane="${1-}"; [ -n "$lane" ] || die "usage: last-session <lane>" 64
    [ "$#" -le 1 ] || die "last-session takes one lane: last-session <lane>" 64
    check_lane_name "$lane"
    log_sync
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    last_session_of "$lane"; ls_rc=$?
    case "$ls_rc" in
      0) : ;;
      8) exit 8 ;;
      *) die "last-session could not read the register or the log for $lane (exit $ls_rc)" 1 ;;
    esac
    ;;

  # DECISION 8(c) AND 8(e) — the live FORKS of this lane's transcript, which
  # are a defect to retire and never a holder. Evidence 6: an abandoned launch
  # left a `--fork-session` daemon orchestrating the same plan and writing this
  # lane's log under an id no row carries. It NAMES them and does nothing else:
  # the act is `lane-end <lane> --retire <pid|uuid>` (clause (k) rule (e)),
  # printed by the caller and typed by a person, for the reason Amendment 8(f)
  # gives — and it writes a record rather than killing anything.
  # 0 with rows, 8 with none, 1 where the records could not be read.
  forks)
    lane="${1-}"; [ -n "$lane" ] || die "usage: forks <lane>" 64
    [ "$#" -le 1 ] || die "forks takes one lane: forks <lane>" 64
    check_lane_name "$lane"
    log_sync
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    lane_forks "$lane"; fk_rc=$?
    case "$fk_rc" in
      0)  : ;;
      8)  exit 8 ;;
      64) die "usage: forks <lane>" 64 ;;
      *)  die "could not read this workstation's session records for lane $lane: ${SESSION_FILES_ERR:-unknown error}. That is NOT 'no fork of it is live'." 1 ;;
    esac
    ;;

  # ISSUE #39 — a live `--fork-session` DUPLICATE of this lane's OWN
  # transcript, found in the process table rather than in a session record's
  # `sessionId` field (which is exactly why `forks` cannot see it once the id
  # is bound to the row: `lane-end <lane> --retire <pid>` is the caller, for a
  # duplicate `lane_forks` was designed to stay silent about).
  # 0 with rows, 8 with none, 1 where `pgrep` is missing or the records could
  # not be read.
  duplicate-holder)
    lane="${1-}"; [ -n "$lane" ] || die "usage: duplicate-holder <lane>" 64
    [ "$#" -le 1 ] || die "duplicate-holder takes one lane: duplicate-holder <lane>" 64
    check_lane_name "$lane"
    log_sync
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    duplicate_holder_pids "$lane"; dh_rc=$?
    case "$dh_rc" in
      0)  : ;;
      8)  exit 8 ;;
      64) die "usage: duplicate-holder <lane>" 64 ;;
      *)  die "could not read this workstation's process table or session records for lane $lane: ${SESSION_FILES_ERR:-unknown error}. That is NOT 'no duplicate holder is live'." 1 ;;
    esac
    ;;

  # DECISION 8(d) — THE WORKSTATION'S NAME, AND WHERE IT CAME FROM. One
  # implementation, so `restart`, `lanes` and every other caller name the
  # workstation the same way the register's own writer does rather than each
  # running `hostname` and disagreeing with it. Prints `<name><TAB><source>`,
  # where the source is one of the THREE `lanes_workstation_pair` emits —
  # `seam`, `hostname` or `container-unset` (`:371-383`) — and on that last one
  # the sentence that says what to export goes to stderr, because a read must
  # still answer.
  #
  # THE TWO NAMES THAT WERE HERE DO NOT EXIST. `config` and
  # `hostname-in-container` are the vocabulary of the rung `R-A11-14` REMOVED:
  # a `workstation:` key in `workspace.yaml`, refused as a second place for the
  # truth to be wrong beside the variable the launcher already sets (`:337-339`).
  # `lanes:190` matched the second of them and could therefore never print, which
  # is how a dead branch went unnoticed (F-X1). SPEC rev 6's §11 row still lists
  # all four; that is the text's to correct, and the code's own emitters are the
  # authority for this comment.
  # Always 0: a workstation name that could refuse would be a refusal in front
  # of every launch on this machine.
  workstation)
    [ "$#" -eq 0 ] || die "workstation takes no arguments" 64
    ws_why="$(lanes_workstation_why "$WS_SOURCE")"
    [ -n "$ws_why" ] && note "$ws_why"
    printf '%s\t%s\n' "$WS" "$WS_SOURCE"
    ;;

  # HOW OLD THE CHECKOUT'S ANSWER IS (`R-A8-1`'s rule, given its own read).
  # `.git/FETCH_HEAD` is rewritten by every fetch and by nothing else, so its
  # mtime is when this checkout last heard from `origin` — and a listing that
  # says "4d ago" is a listing a reader knows not to trust about another
  # workstation's lane. Never a network call and never a failure: an unreadable
  # one answers `unknown`. Always 0.
  fetch-age)
    [ "$#" -eq 0 ] || die "fetch-age takes no arguments" 64
    fetch_age
    ;;

  # DECISIONS 6 AND 7 — THE LANE LISTING, as data. `lanes` renders the
  # estate-wide one and `restart` the per-repo one from these same rows, which
  # is why the filter is an argument rather than three implementations.
  # 0 with rows, 8 with none, 64 a usage error of its own.
  lanes)
    lns_args=(); lns_fetch=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --repo|--dir|--ws|--lane|--prefix) [ -n "${2-}" ] || die "$1 needs a value (usage: lanes [--repo <owner/repo>] [--dir <path>] [--prefix <repo>] [--ws <workstation>] [--lane <lane>] [--here] [--all] [--fetch])" 64
                           lns_args+=("$1" "$2"); shift 2 ;;
        --all|--here)      lns_args+=("$1"); shift ;;
        --fetch)           lns_fetch=1; shift ;;
        --)                shift ;;
        *)                 die "unknown argument '$1' for lanes (usage: lanes [--repo <owner/repo>] [--dir <path>] [--prefix <repo>] [--ws <workstation>] [--here] [--all] [--fetch])" 64 ;;
      esac
    done
    # THE ONE READ IN THIS FILE WHOSE DEFAULT IS LOCAL (SPEC rev 4 §15). Every
    # other read here sits in front of a LAUNCH, where a stale answer binds the
    # wrong lane; this one sits in front of a PERSON, who is waiting on it. So
    # `LANES_NO_FETCH=1` is its default rather than an override — still honoured
    # where it is already set — and `--fetch` is how a caller asks for the
    # network. `fetch-age` is the read beside it, so a listing can say how old
    # its answer is, exactly as Amendment 8(e)'s hook does under `R-A8-1`.
    [ "$lns_fetch" = 1 ] || LANES_NO_FETCH=1
    log_sync
    # A FETCH THAT DID NOT HAPPEN IS NOT A FETCH, AND IT IS SAID IN THE ONE
    # PHRASE THE CALLER ALREADY READS (#26, `lanes:411`). `log_sync` leaves four
    # ways out of itself that never reach the fetch and were silent on all four;
    # `lanes --fetch` matches its stderr for *"reading the logs as they stand
    # locally"* and prints *"as of a fetch just now"* where it does not find it.
    # So the phrase is the helper's, once, and the reason is named beside it.
    #
    # ONLY UNDER `--fetch`. Without it this read's default is LOCAL by design
    # (SPEC rev 4 §15) and the notice would be a line saying it did what it was
    # asked — which is why the wrapper renders the fetch path's stderr and not
    # the local path's.
    if [ "$lns_fetch" = 1 ] && [ "$LOG_SYNC_FETCH" != yes ] && [ "$LOG_SYNC_FETCH" != fell-back ]; then
      note "--fetch was asked for and NO FETCH WAS MADE: $LOG_SYNC_FETCH — reading the logs as they stand locally"
    fi
    # AMENDMENT 15 — `--lane <name>` IS A `<lane>` ARGUMENT AND GOES THROUGH THE
    # RESOLVER. The filter inside `lanes_rows` has always joined on the name
    # lower-cased, so the ROWS came back either way; what a typed spelling used
    # to do was put itself in column 1 and in column 10's `restart <lane>` line.
    # `${lns_args[@]+"${lns_args[@]}"}` AND NOT `${#lns_args[@]}` OR AN INDEX:
    # this file is parsed under macOS bash 3.2 in CI, where an EMPTY array under
    # `set -u` is the expansion this idiom exists for — it is the same one the
    # `lanes_rows` call below already uses, and a bare `lanes` with no flags is
    # exactly the empty case. The rebuild also stops assuming the value sits at
    # `i + 1`; it takes the word AFTER `--lane`, which is what the parser above
    # guarantees there is one of.
    # `--all` IS ABSOLUTE AND IT CLEARS `--lane` (the reset inside `lanes_rows`
    # says so in terms), so a `--lane` it is about to throw away must not be
    # resolved — and must not REFUSE. `lanes --all --lane <the 15(d) pair>` is
    # the every-lane listing, in either flag order, and exiting 2 on a selector
    # this run ignores would hide every lane for a name nothing was asked about
    # (Copilot round 1 on openRepoTools#41).
    lns_all=0
    for lns_a in ${lns_args[@]+"${lns_args[@]}"}; do
      case "$lns_a" in --all) lns_all=1 ;; esac
    done
    lns_new=(); lns_take=0
    for lns_a in ${lns_args[@]+"${lns_args[@]}"}; do
      if [ "$lns_take" = 1 ]; then
        lns_take=0
        if [ "$lns_all" = 0 ]; then
          lns_one="$(canon_lane "$lns_a")" || exit 2
        else
          lns_one="$lns_a"
        fi
        lns_new+=("$lns_one")
        continue
      fi
      case "$lns_a" in --lane) lns_take=1 ;; esac
      lns_new+=("$lns_a")
    done
    lns_args=(${lns_new[@]+"${lns_new[@]}"})
    lns_out="$(lanes_rows ${lns_args[@]+"${lns_args[@]}"})"; lns_rc=$?
    case "$lns_rc" in
      0)  : ;;
      8)  exit 8 ;;
      64) die "usage: lanes [--repo <owner/repo>] [--dir <path>] [--prefix <repo>] [--ws <workstation>] [--here] [--all]" 64 ;;
      *)  die "the lane listing could not be read (exit $lns_rc)" 1 ;;
    esac
    [ -n "$lns_out" ] || exit 8
    printf '%s\n' "$lns_out"
    ;;

  # AMENDMENT 8 — Rule 1's sibling reads, filtered to lines that NAME the
  # object. `gh_reads` pipes both of its searches through this; it is a
  # subcommand so that the filter can be held to account directly, and so a
  # person can run a search of their own through the same test.
  sibling-filter)
    sfsub=""; sfsub_mode=pr
    while [ $# -gt 0 ]; do
      case "$1" in
        --branch) sfsub_mode=branch; shift ;;
        --pr)     sfsub_mode=pr; shift ;;
        --)       shift ;;
        -*)       die "unknown option '$1' for sibling-filter" 2 ;;
        *)        [ -z "$sfsub" ] || die "sibling-filter takes one object" 2; sfsub="$1"; shift ;;
      esac
    done
    [ -n "$sfsub" ] || die "usage: sibling-filter <object> [--branch]   (candidate lines on stdin)" 2
    sfsub_home="$(resolve_home "${LANES_LANE:-}" "" 2>/dev/null || :)"
    sfsub_obj="$(canon_object "$sfsub" "$sfsub_home")" || exit 2
    sibling_filter "$sfsub_obj" "$sfsub_mode"
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
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
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
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    rr_row="$(row_of_lane "$lane")"
    [ -n "$rr_row" ] || exit 8
    printf '%s\n' "$rr_row"
    ;;

  # R-A11-7 — THE HOOK'S OWN uuid → lane READ, EXPOSED. `lane_of_session` has
  # answered "which lane's row's SESSION CELL names this uuid" since Amendment
  # 8(e), for a window that carries no lane name; nothing else could reach it.
  # `lane-start` step 3b needs the same answer to keep R-A11-1's fence — a live
  # session that belongs to ANOTHER row is never taken — so it is one read with
  # two callers rather than a second implementation of the same question.
  #
  # ONLY the session cell is read, exactly as the hook reads it: state cells
  # quote other lanes' ids all the time (`RESUMED by <id>`, `handed off to
  # <id>`), and one of those is not that session's lane.
  #
  # Read-only. 0 with the lane, 8 when no row's session cell names it —
  # Amendment 7(d)'s fail-closed convention, so a caller can tell *none* from
  # *could not read* — and 64 on a usage error of its own.
  #
  # 64 AND NOT 2 (A11 Addendum 4 ruling 1, ratified "a11 addendum 4 yes").
  # Adoption act 0 wrote this read with a usage `2` (`3719d97:lanes/lanes-edit.sh`)
  # and SPEC rev 6 §11 recorded the landed code; clause (h)'s own table said
  # `64 usage` for every read in it, and the contract contradicted itself. The
  # ruling settles it the other way: *"`session-lane`'s usage code is 64 like
  # every other read in clause (h); adoption act 0 item (4), which says 2, is
  # the line corrected."*
  #
  # IT MATTERS BECAUSE `2` HERE ALREADY MEANS SOMETHING ELSE. A helper that has
  # never heard of `session-lane` exits 2 from the `*)` arm, and that is what
  # every workstation answers until act 3's install reaches it. A caller that
  # cannot tell that 2 from a usage 2 cannot tell *"install the helper"* from
  # *"fix your call"* — and both of `session-lane`'s callers fail CLOSED on
  # anything but 0 or 8, so the distinction is the whole of what they can report.
  session-lane)
    sl_id="${1-}"; [ -n "$sl_id" ] || die "usage: session-lane <transcript-uuid>" 64
    [ "$#" -le 1 ] || die "session-lane takes one transcript uuid: session-lane <transcript-uuid>" 64
    log_sync
    sl_lane="$(lane_of_session "$sl_id")"
    [ -n "$sl_lane" ] || exit 8
    printf '%s\n' "$sl_lane"
    ;;

  # AMENDMENT 15 — THE RESOLVER, EXPOSED, because `lane-start`, `lane-end`,
  # `lanes` and `restart` all take a `<lane>` argument and the amendment gives
  # all four the SAME resolver. Four implementations of "which row is this
  # name's" is how the four would come to disagree about it — which is the whole
  # reason clause (h) turned `window-lane` and `session-lane` into subcommands.
  #
  # Read-only, out of `origin/<branch>` like every other state read (R19).
  #   0   the canonical spelling — the row's own where a row matches ignoring
  #       case, and the TYPED spelling where none does, because a lane with no
  #       row is a lane `add-row` is about to create and the typed name is all
  #       there is.
  #   2   the refusal: two or more rows differ only by case (15(d)). It is 2 and
  #       not 8 because it is a REFUSAL and not an absence — and `lane-start`
  #       already spends 2 on exactly this fact for two rows of one spelling.
  #   64  a usage error of its own, as every read in clause (h)'s table does.
  # A caller that meets 2 from a helper predating this amendment is meeting the
  # `*)` arm's unknown-subcommand 2, told apart by the helper's own WORDS as
  # every other read here is; the four callers fall through to the typed
  # spelling there, and each has its own refusal for a register that really does
  # hold two such rows.
  canon-lane)
    cl_in="${1-}"; [ -n "$cl_in" ] || die "usage: canon-lane <lane>" 64
    [ "$#" -le 1 ] || die "canon-lane takes one lane: canon-lane <lane>" 64
    check_lane_name "$cl_in"
    log_sync
    cl_res="$(canon_lane "$cl_in")" || exit 2
    printf '%s\n' "$cl_res"
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
    lane="$(canon_lane "$lane")" || exit 2          # Amendment 15
    rh_out="$(resolve_home "$lane" "${2-}")" || exit $?
    [ -n "$rh_out" ] || exit 8
    printf '%s\n' "$rh_out"
    ;;

  *)
    die "unknown subcommand '$cmd' (verify-row|append-row-status|replace-in-row|append-session-id|append-line|add-row|commit|log|claim|release|who|swapped|session-start|guard|idle-holders|live-holder|window-session|transcript-holders|session-lane|window-lane|lane-dir|lane-profile|lane-agent|lane-transcript|lane-last|workspace-root|last-session|forks|duplicate-holder|workstation|fetch-age|lanes|sibling-filter|resolve-repo|lane-objects|register-row|canon-lane|resolve-home)" 2
    ;;
esac
