#!/usr/bin/env bash
#
# test_lane_helpers.sh — lane-start and lane-end, exercised end to end in a
# sandbox that touches nothing real.
#
# WHAT IS FAKED, AND WHY
#   HOME        a temp directory, so the session records the liveness check
#               reads, the projects tree it looks for transcripts in, and
#               ~/projects are all the test's own.
#   the register  a bare repo plus a clone, seeded with a header and rows.
#               lanes-edit.sh runs FOR REAL against it — commit, pull, push —
#               so the tests prove the whole write path, not a stub of it.
#   tmux        a script that answers display-message and logs rename-window.
#   claude      a script that logs its argv, so the launch can be watched
#               even when lane-start exec's it.
#   liveness    a real `sleep` process for the live case and a reaped pid for
#               the dead one; nothing is mocked out of /proc.
#
# Run it from anywhere: ./lanes/test_lane_helpers.sh
# Exit 0 when every assertion passes, 1 otherwise.

set -uo pipefail          # NOT -e: a failing assertion must not end the run

SELF="$(readlink -f -- "${BASH_SOURCE[0]}")"
SRC_DIR="$(cd -- "$(dirname -- "$SELF")" && pwd)"

for f in lane-start lane-end lanes-edit.sh; do
  [ -x "$SRC_DIR/$f" ] || { echo "missing or not executable: $SRC_DIR/$f" >&2; exit 1; }
done

SANDBOX="$(mktemp -d)"
REAL_HOME="$HOME"
cleanup() {
  [ -n "${LIVE_PID:-}" ] && kill "$LIVE_PID" 2>/dev/null
  [ -n "${SANDBOX:-}" ] && [ -d "$SANDBOX" ] && rm -rf -- "$SANDBOX"
  return 0
}
trap cleanup EXIT INT TERM

export HOME="$SANDBOX/home"
export TMPDIR="$SANDBOX/tmp"
mkdir -p "$HOME/projects" "$TMPDIR" "$SANDBOX/fakebin"
export PATH="$SANDBOX/fakebin:$PATH"
export CLAUDE_CONFIG_DIR="$HOME/.claude"
unset LANES_FILE LANES_EDIT LANES_REPO LANES_PATH LANES_LANE PROJECTS_ROOT CLAUDE_PROJECTS_DIR CLAUDE_BIN 2>/dev/null

pass=0; fail=0
ok()  { pass=$((pass + 1)); printf 'ok   %s\n' "$1"; }
bad() { fail=$((fail + 1)); printf 'FAIL %s\n       %s\n' "$1" "${2-}"; }
is()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected [$3], got [$2]"; fi; }
has() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1" "expected to contain [$3]; got: $(printf '%s' "$2" | tr '\n' '~' | cut -c1-400)" ;; esac; }
hasnt() { case "$2" in *"$3"*) bad "$1" "did NOT expect [$3]; got: $(printf '%s' "$2" | tr '\n' '~' | cut -c1-400)" ;; *) ok "$1" ;; esac; }
# lane-start mints a fresh uuid for a NEW session, so its launch line carries a
# value no test can predict. `launch_of` removes just that pair, leaving the
# rest of the command line exactly comparable; `minted_of` returns the uuid.
UUID_RE='[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
launch_of() { printf '%s' "$1" | sed -E "s/ --session-id $UUID_RE//"; }
minted_of() { printf '%s' "$1" | grep -oE -- "--session-id $UUID_RE" | head -n1 | awk '{print $2}'; }

rc=0; out=""; err=""
run() { out="$("$@" 2>"$SANDBOX/stderr")"; rc=$?; err="$(cat "$SANDBOX/stderr")"; }

# ---------------------------------------------------------------- the fakes

cat > "$SANDBOX/fakebin/tmux" <<'FAKE'
#!/usr/bin/env bash
case "${1-}" in
  display-message)
    case "${3-}" in
      '#{session_name}:#{window_id}') printf '%s\n' "${FAKE_TMUX_WINDOW:-testsess:@1}" ;;
      '#W')                           printf '%s\n' "${FAKE_TMUX_WINDOW_NAME:-claude}" ;;
      *)                              printf '\n' ;;
    esac ;;
  rename-window) printf 'rename-window %s\n' "${2-}" >> "${FAKE_TMUX_LOG:-/dev/null}" ;;
  *) : ;;
esac
FAKE

cat > "$SANDBOX/fakebin/claude" <<'FAKE'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "${FAKE_CLAUDE_LOG:-/dev/null}"
FAKE

chmod +x "$SANDBOX/fakebin/tmux" "$SANDBOX/fakebin/claude"
export FAKE_TMUX_LOG="$SANDBOX/tmux.log" FAKE_CLAUDE_LOG="$SANDBOX/claude.log"
: > "$FAKE_TMUX_LOG"; : > "$FAKE_CLAUDE_LOG"
export TMUX="$SANDBOX/fake-tmux-socket,0,0"

# ------------------------------------------------------------- the register

ORIGIN="$SANDBOX/origin.git"
WIP="$HOME/projects/brett-wip"
git init -q --bare -b main "$ORIGIN"
git clone -q "$ORIGIN" "$WIP" 2>/dev/null
git -C "$WIP" config user.email "test@example.invalid"
git -C "$WIP" config user.name  "lane helper tests"
mkdir -p "$WIP/lanes"
cp -p "$SRC_DIR/lane-start" "$SRC_DIR/lane-end" "$SRC_DIR/lanes-edit.sh" "$WIP/lanes/"

LANES="$WIP/lanes/LANES.md"
{
  printf '# LANES.md — the sandbox register\n\n'
  printf '| lane | session id | workstation / env / user | started (UTC) | objects owned | handoff path | state |\n'
  printf '|---|---|---|---|---|---|---|\n'
} > "$LANES"

add_seed_row() { printf '%s\n' "$1" >> "$LANES"; }

# repoA-1  a lane whose session has ENDED — free, and resumable
# repoA-2  the same, with no transcript of its own
# repoB-1  a lane a LIVE session holds, in another window
# repoC-1  a row whose live session has been RENAMED to another lane
# repoD-1  a row with an open LANDING       (lane-end refuses)
# repoD-2  a row that says NOTHING CLAIMED  (lane-end must NOT refuse)
# repoD-3  LANDING then LANDED              (lane-end must NOT refuse)
DEAD_ID="00000000-dead-4000-8000-0000000dead0"
LIVE_ID="11111111-11ee-4000-8000-1111111111ee"
GONE_ID="22222222-c0de-4000-8000-2222222222ff"
# repoA-2 proves the NO-HISTORY path, so its recorded id must be one this
# directory has no transcript for (under Amendment 6 a resolvable id wins).
GHOST4_ID="88888888-9057-4000-8000-8888888888ff"
add_seed_row "| \`repoA-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA/x.md | ACTIVE |"
add_seed_row "| \`repoA-2\` | harness \`$GHOST4_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA/x.md | ACTIVE |"
add_seed_row "| \`repoB-1\` | harness \`$LIVE_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoB/x.md | ACTIVE |"
add_seed_row "| \`repoC-1\` | harness \`$GONE_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoC/x.md | ACTIVE |"
add_seed_row "| \`repoD-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoD/x.md | ACTIVE · LANDING #7 into repoD main |"
add_seed_row "| \`repoD-2\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoD/x.md | IDLE, NOTHING CLAIMED · no LANDING open |"
add_seed_row "| \`browser-ui-repair\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoD/x.md | ACTIVE |"
add_seed_row "| \`repoD-3\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoD/x.md | ACTIVE · LANDING #7 · LANDED — PR #7 → abc1234 |"

# Amendment 6 (resume the row's RECORDED SESSION, not its title).
# repoA-11  the row's id has NO transcript here, but a titled one exists  -> title fallback
# repoA-12  the cell is a HISTORY of two ids, both with transcripts       -> the LAST one wins
# repoA-13  the cell records only `session_…` footer ids (no uuid at all) -> new session + a hint
# repoA-14  one unique uuid, no transcript, no title                      -> new session + the cell is stamped
# repoA-15  the same as 14, with LANE_START_SESSION_ID=0                  -> new session, nothing minted
GHOST_ID="33333333-9057-4000-8000-3333333333aa"
OLD12_ID="44444444-01d0-4000-8000-4444444444bb"
NEW12_ID="55555555-0e00-4000-8000-5555555555cc"
GHOST2_ID="66666666-9057-4000-8000-6666666666dd"
GHOST3_ID="77777777-9057-4000-8000-7777777777ee"
GHOST5_ID="99999999-9057-4000-8000-99999999aabb"
add_seed_row "| \`repoA-11\` | harness \`$GHOST_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA/x.md | ACTIVE |"
add_seed_row "| \`repoA-12\` | harness \`$OLD12_ID\` → after /clear \`$NEW12_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA/x.md | ACTIVE |"
add_seed_row "| \`repoA-13\` | \`session_015byFrZSopmRbUWNMYt1zEA\` (profile team-02c); earlier \`session_01EdVCYtG7YQ4s347uCrHVLY\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA/x.md | ACTIVE |"
add_seed_row "| \`repoA-14\` | harness \`$GHOST2_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA/x.md | ACTIVE |"
add_seed_row "| \`repoA-15\` | harness \`$GHOST3_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA/x.md | ACTIVE |"
# repoA-16  the only transcript here carries the DEDUPE-SUFFIXED title
add_seed_row "| \`repoA-16\` | harness \`$GHOST5_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA/x.md | ACTIVE |"
git -C "$WIP" add -- lanes/LANES.md lanes/lane-start lanes/lane-end lanes/lanes-edit.sh
git -C "$WIP" commit -q -m "seed the sandbox register"
git -C "$WIP" push -q origin main

START="$WIP/lanes/lane-start"
END="$WIP/lanes/lane-end"

for r in repoA repoB repoC repoD; do mkdir -p "$HOME/projects/$r"; done
git init -q -b main "$HOME/projects/repoA"

# ---------------------------------------------------------- session records

sessions_dir="$HOME/.claude-profiles/profiles/opensoft/team/t1/sessions"
mkdir -p "$sessions_dir" "$HOME/.claude/sessions"

sleep 300 & LIVE_PID=$!
live_start="$(cut -d' ' -f22 "/proc/$LIVE_PID/stat" 2>/dev/null || printf '')"
sleep 0.05 & DEAD_PID=$!
wait "$DEAD_PID" 2>/dev/null

write_record() { # <file> <sessionId> <pid> <procStart> <tmux> <name> <status>
  printf '{"pid":%s,"sessionId":"%s","cwd":"x","procStart":"%s","tmux":"%s","name":"%s","status":"%s"}\n' \
    "$3" "$2" "$4" "$5" "$6" "$7" > "$1"
}
write_record "$sessions_dir/$DEAD_PID.json" "$DEAD_ID" "$DEAD_PID" ""            "testsess:@9.%9"  "repoA-1" "idle"
write_record "$sessions_dir/$LIVE_PID.json" "$LIVE_ID" "$LIVE_PID" "$live_start" "othersess:@9.%9" "repoB-1" "idle"
write_record "$HOME/.claude/sessions/$LIVE_PID.json" "$GONE_ID" "$LIVE_PID" "$live_start" "othersess:@9.%9" "somewhere-else-4" "idle"

# ----------------------------------------------------------- the transcript

sanitize() { printf '%s' "$1" | tr -c 'A-Za-z0-9' '-'; }
tdir="$HOME/.claude/projects/$(sanitize "$HOME/projects/repoA")"
mkdir -p "$tdir"
printf '{"type":"custom-title","customTitle":"repoA-1","sessionId":"%s"}\n' "$DEAD_ID" > "$tdir/$DEAD_ID.jsonl"
# A session that was renamed AWAY from repoA-2: the last title wins, so this
# must not be resumed as repoA-2.
{ printf '{"type":"custom-title","customTitle":"repoA-2","sessionId":"x"}\n'
  printf '{"type":"custom-title","customTitle":"something-else","sessionId":"x"}\n'; } > "$tdir/x.jsonl"

# repoA-11: a TITLED transcript whose id the row does not name — the fallback.
printf '{"type":"custom-title","customTitle":"repoA-11","sessionId":"titled-11"}\n' > "$tdir/titled-11.jsonl"
# repoA-12: both ids in the cell have a transcript; only the LAST may be resumed.
printf '{"type":"user"}\n' > "$tdir/$OLD12_ID.jsonl"
printf '{"type":"user"}\n' > "$tdir/$NEW12_ID.jsonl"
# repoA-16: the title a collided rename mints. `<lane> (2)` is the same lane.
printf '{"type":"custom-title","customTitle":"repoA-16 (2)","sessionId":"titled-16"}\n' > "$tdir/titled-16.jsonl"
# $GHOST_ID, $GHOST2_ID, $GHOST3_ID and $GHOST5_ID have no transcript at all.

echo "== lane-start =="

run "$START" --help
is   "lane-start --help exits 0" "$rc" 0
has  "lane-start --help prints the usage" "$out" "lane-start [options] <repo> <n>"

( unset TMUX; "$START" repoA 9 ) >/dev/null 2>"$SANDBOX/stderr"; rc=$?; err="$(cat "$SANDBOX/stderr")"
is   "outside tmux: exit 1 (environment)" "$rc" 1
has  "outside tmux: the refusal names the fix" "$err" "run this inside the tmux window that will carry the lane"

run "$START" repoZZ 1 --no-launch
is   "no such directory: exit 1" "$rc" 1
has  "no such directory: names --dir" "$err" "--dir"

run "$START" repoA "" --no-launch
is   "a non-position is refused with exit 2" "$rc" 2

before_rev="$(git -C "$WIP" rev-parse HEAD)"
before_sum="$(cksum < "$LANES")"
run "$START" --dry-run repoA 7
is   "--dry-run exits 0" "$rc" 0
is   "--dry-run writes no register commit" "$(git -C "$WIP" rev-parse HEAD)" "$before_rev"
is   "--dry-run leaves LANES.md byte-identical" "$(cksum < "$LANES")" "$before_sum"
is   "--dry-run renames no window" "$(grep -c 'repoA-7' "$FAKE_TMUX_LOG")" 0
has  "--dry-run says what it would add" "$err" "PLAN lanes-edit.sh add-row"

run "$START" repoA 7 --no-launch
REPOA7_SID="$(minted_of "$out")"
is   "a new lane exits 0" "$rc" 0
is   "a new lane launches with --name" "$(launch_of "$out")" "claude --name repoA-7"
has  "a new lane mints a session id for itself" "$out" "--session-id "
has  "a new lane renames the window" "$(cat "$FAKE_TMUX_LOG")" "rename-window repoA-7"
is   "a new lane gets exactly one row" "$(grep -c '^| `repoA-7`' "$LANES")" 1
has  "the new row starts STARTING" "$(grep '^| `repoA-7`' "$LANES")" "| STARTING |"
has  "the new row's session cell names the minted session" "$(grep '^| `repoA-7`' "$LANES")" "(minted by lane-start,"
hasnt "…so it no longer says 'pending'" "$(grep '^| `repoA-7`' "$LANES")" "pending — set by the session's first act"
has  "…and it is the very id claude was given" "$(grep '^| `repoA-7`' "$LANES")" "$REPOA7_SID"
has  "the new row names its workstation" "$(grep '^| `repoA-7`' "$LANES")" "$(hostname) / "
has  "the new row points at a handoff" "$(grep '^| `repoA-7`' "$LANES")" "handoffs/repoA/session-handoff-"
has  "the row write is its own commit" "$(git -C "$WIP" log --oneline -1)" "add row"
is   "the row write was pushed" "$(git -C "$WIP" rev-parse HEAD)" "$(git -C "$WIP" rev-parse origin/main)"

run "$START" --estate xFactory --dir "$HOME/projects/repoB" repoA 8 --no-launch
has  "--estate names the handoff directory" "$(grep '^| `repoA-8`' "$LANES")" "handoffs/xFactory/session-handoff-"

run "$START" repoA 1 --no-launch
is    "a free lane resumes THE ROW'S RECORDED SESSION, by id" "$out" "claude --resume $DEAD_ID"
hasnt "…and never by the ambiguous title" "$out" "--resume repoA-1"
has   "…saying it is the row's own transcript" "$err" "the row's current session is $DEAD_ID and its transcript is here"
has  "a free lane appends a status, not a row" "$(git -C "$WIP" log --oneline -1)" "lane-start on"
has  "the appended status says what it did" "$(grep '^| `repoA-1`' "$LANES")" "window renamed, launching claude"

run "$START" repoA 2 --no-launch
is   "a free lane with no title of its own starts new" "$(launch_of "$out")" "claude --name repoA-2"

run "$START" repoB 1 --no-launch
is   "a lane live in another window: exit 2" "$rc" 2
has  "…and the refusal names the session" "$err" "is live in session $LIVE_ID"
has  "…and the refusal names the next position" "$err" "take repoB-2"
is   "…and it renames nothing" "$(grep -c 'repoB-1' "$FAKE_TMUX_LOG")" 0

export FAKE_TMUX_WINDOW="othersess:@9"
run "$START" repoB 1 --no-launch
is   "the same lane live in THIS window is not a collision" "$rc" 0
unset FAKE_TMUX_WINDOW

run "$START" repoC 1 --no-launch
is   "a live session RENAMED to another lane does not hold the row" "$rc" 0

: > "$FAKE_CLAUDE_LOG"
run "$START" repoA 3
is   "without --no-launch it exec's claude" "$rc" 0
has  "…with --name for a lane that is new" "$(cat "$FAKE_CLAUDE_LOG")" "--name repoA-3"

( cd "$HOME/projects/repoA" && "$START" 4 --no-launch ) >"$SANDBOX/o" 2>/dev/null; rc=$?
is   "<n> alone takes the repo from the cwd's git root" "$(launch_of "$(cat "$SANDBOX/o")")" "claude --name repoA-4"

run "$START" repoA-5 --no-launch
is   "the full lane name works as one argument" "$(launch_of "$out")" "claude --name repoA-5"

run "$START" repoA 6 --no-launch -- --dangerously-skip-permissions
is   "arguments after -- reach claude" "$(launch_of "$out")" "claude --name repoA-6 --dangerously-skip-permissions"
has  "…alongside the minted --session-id" "$out" "--session-id "

echo "== lane-start: Amendment 6 — resume the row's recorded session =="

# The fallback, unchanged in shape: the row names an id this directory has no
# transcript for, so the title is all that is left — and lane-start says so.
run "$START" repoA 11 --no-launch
is   "a recorded id with no transcript here falls back to the title" "$out" "claude --resume repoA-11"
has  "…naming the id it could not resolve" "$err" "$GHOST_ID has no transcript for this directory"
has  "…and warning that a title only filters the picker" "$err" "FILTERS THE PICKER"

# The cell is a history, oldest first, so the LAST id is the lane's current one.
run "$START" repoA 12 --no-launch
is    "the LAST id in the session cell is the one resumed" "$out" "claude --resume $NEW12_ID"
hasnt "…never an earlier id in the same cell" "$out" "$OLD12_ID"

# The codeXfactory-1 shape of 2026-09-11: a cell of `session_…` footer ids and
# no transcript id at all. Nothing to resume and nothing to append to — so it
# prints the act instead of guessing at the cell's text.
run "$START" repoA 13 --no-launch
is   "a cell with no transcript id at all starts a new session" "$(launch_of "$out")" "claude --name repoA-13"
has  "…telling the session to stamp the cell itself" "$err" "STAMP IT AS THIS SESSION'S FIRST ACT"
has  "…and naming the exact command" "$err" "replace-in-row repoA-13"
is   "…and the row is never rewritten by guesswork" "$(grep -c 'session_015byFrZSopmRbUWNMYt1zEA' "$LANES")" 1
has  "…and it names the footer ids as the reason it has no target" "$err" "the cell records only PR-footer ids (session_015byFrZSopmRbUWNMYt1zEA"

# A dedupe-suffixed title is the SAME lane — live_holder() already reads it
# that way, and a matcher that disagreed would hide a lane from itself.
run "$START" repoA 16 --no-launch
is   "a transcript titled '<lane> (2)' is still the lane's" "$out" "claude --resume repoA-16"
has  "…and the suffix is reported, not silently accepted" "$err" "that title carries a dedupe suffix"
has  "…with the retire act named" "$err" "retire the stale holders"

# An existing row with one readable id and a new session: the cell is made
# current automatically, so the NEXT start resumes by id.
run "$START" repoA 14 --no-launch
REPOA14_SID="$(minted_of "$out")"
is   "an existing row with a stale id starts a new session" "$(launch_of "$out")" "claude --name repoA-14"
has  "…and the session cell is stamped with the minted id" "$(grep '^| `repoA-14`' "$LANES")" "$GHOST2_ID → harness \`$REPOA14_SID\`"
has  "…in its own register commit" "$(git -C "$WIP" log --oneline -1)" "session cell: lane-start minted $REPOA14_SID"

# And the loop closes: run it again, and the id just written is resumed by id.
printf '{"type":"user"}\n' > "$tdir/$REPOA14_SID.jsonl"
run "$START" repoA 14 --no-launch
is   "the next start resumes exactly what the previous one recorded" "$out" "claude --resume $REPOA14_SID"

# The minting is switchable, and switching it off restores the old row text.
LANE_START_SESSION_ID=0 run "$START" repoA 15 --no-launch
is    "LANE_START_SESSION_ID=0 mints nothing" "$out" "claude --name repoA-15"
hasnt "…and passes no --session-id" "$out" "--session-id"
has   "…leaving the old 'stamp it yourself' contract" "$(grep '^| `repoA-15`' "$LANES")" "$GHOST3_ID"

# --dry-run still writes nothing, on the resume path too.
before_rev="$(git -C "$WIP" rev-parse HEAD)"
before_sum="$(cksum < "$LANES")"
run "$START" --dry-run repoA 12
is   "--dry-run on a resume-by-id lane exits 0" "$rc" 0
is   "--dry-run writes no register commit" "$(git -C "$WIP" rev-parse HEAD)" "$before_rev"
is   "--dry-run leaves LANES.md byte-identical" "$(cksum < "$LANES")" "$before_sum"
has  "--dry-run plans the exact resume" "$err" "PLAN exec claude --resume $NEW12_ID"

echo "== lane-end =="

run "$END" --help
is   "lane-end --help exits 0" "$rc" 0

run "$END" repoD-1
is   "an open LANDING is refused" "$rc" 2
has  "…naming what it found" "$err" "the last LANDING in its state cell"
has  "…and the fix" "$err" "append-row-status repoD-1"
hasnt "…and nothing is written" "$(grep '^| `repoD-1`' "$LANES")" "lane-end on"

run "$END" repoD-2
is   "NOTHING CLAIMED / no LANDING open is not something in flight" "$rc" 0
has  "…and the closing line is written" "$(grep '^| `repoD-2`' "$LANES")" "window closing; NOTHING IN FLIGHT"

run "$END" repoD-3
is   "LANDING followed by LANDED is closed" "$rc" 0

run "$END" repoD-1 --force
is   "--force ends it anyway" "$rc" 0
has  "…and says so in the register" "$(grep '^| `repoD-1`' "$LANES")" "ENDED WITH --force"

run "$END" repoA-7 --retire
is   "--retire exits 0" "$rc" 0
has  "…and the state cell now opens RETIRED" "$(grep '^| `repoA-7`' "$LANES")" "| RETIRED 20"
has  "…while the history it had is still there" "$(grep '^| `repoA-7`' "$LANES")" "window closing; NOTHING IN FLIGHT"
is   "…and the window is never renamed" "$(grep -c 'rename-window repoA-7$' "$FAKE_TMUX_LOG")" 1

run "$END" no-such-lane-4
is   "a lane with no row is refused" "$rc" 2
has  "…naming the fix" "$err" "add-row"

before_rev="$(git -C "$WIP" rev-parse HEAD)"
run "$END" --dry-run repoA-2
is   "lane-end --dry-run exits 0" "$rc" 0
is   "lane-end --dry-run writes nothing" "$(git -C "$WIP" rev-parse HEAD)" "$before_rev"

run "$END" browser-ui-repair --retire
is   "a lane named before the <repo>-<n> rule can still be ended" "$rc" 0
has  "…verbatim, and retired" "$(grep '^| `browser-ui-repair`' "$LANES")" "| RETIRED 20"

echo "----"
printf '%s passed, %s failed\n' "$pass" "$fail"
[ "$fail" = 0 ] || exit 1
exit 0
