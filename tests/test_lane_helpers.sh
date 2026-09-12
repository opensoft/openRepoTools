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
#   the logs    Amendment 7's `lanes/log/<lane>.md` live in the sandbox clone,
#               never beside this file, and a SECOND clone plays the other
#               workstation so the lost-claim race is run for real.
#               NO TEST MAY REACH GITHUB, and the thing that guarantees it is
#               `export LANES_NO_GITHUB=1` below plus `--no-github` on every
#               case: with it set, gh_reads, gh_comment and gh_stale_claim_url
#               all return before any `gh` or `git ls-remote` call. The fake
#               bin is PREPENDED to PATH, not substituted for it, so a real
#               `gh` on this workstation is still on PATH and is not what
#               stops the call.
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

# Amendment 7: no test may reach GitHub, whatever a case forgets to pass.
export LANES_NO_GITHUB=1
STALE_H=4                      # lanes-edit.sh's default, Rule 1's four hours

# ------------------------------------------------------------- the register

ORIGIN="$SANDBOX/origin.git"
WIP="$HOME/projects/brett-wip"
git init -q --bare -b main "$ORIGIN"
git clone -q "$ORIGIN" "$WIP" 2>/dev/null
git -C "$WIP" config user.email "test@example.invalid"
git -C "$WIP" config user.name  "lane helper tests"
mkdir -p "$WIP/lanes"
cp -p "$SRC_DIR/lane-start" "$SRC_DIR/lane-end" "$SRC_DIR/lanes-edit.sh" "$SRC_DIR/repos.tsv" "$WIP/lanes/"

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

# Amendment 7 rows.
# repoF-1  a LIVE session whose record name is auto-DERIVED and does not match
#          the lane — the 2026-09-11 hole: it is still the holder.
# repoG-3  a LIVE session EXPLICITLY named for another lane — not a holder.
# repoG-1  holds a stale claim, a claim that is NOT stale because a PR names
#          it, and an open LANDING; repoG-2 is the lane that takes over.
# repoH-1 / repoH-2  the two sides of a race decided by which claim LANDS.
# repoP-1 / repoP-2  PRE-CUTOVER: no object log, ever.
# repoR-1  a row whose workstation column is another machine.
F_ID="aaaa0001-f1f1-4000-8000-aaaa0001f1f1"
G_ID="aaaa0002-6363-4000-8000-aaaa00026363"
R_ID="aaaa0003-4a4e-4000-8000-aaaa00034a4e"
H_ID="aaaa0004-8e8e-4000-8000-aaaa00048e8e"
add_seed_row "| \`repoF-1\` | harness \`$F_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoF/x.md | ACTIVE |"
add_seed_row "| \`repoG-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoG/x.md | ACTIVE |"
add_seed_row "| \`repoG-2\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoG/x.md | ACTIVE |"
add_seed_row "| \`repoG-3\` | harness \`$G_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoG/x.md | ACTIVE |"
add_seed_row "| \`repoH-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoH/x.md | ACTIVE |"
add_seed_row "| \`repoH-2\` | harness \`$DEAD_ID\` | Raven / test / brett | 2026-09-11T00:00Z | none | handoffs/repoH/y.md | ACTIVE |"
add_seed_row "| \`repoP-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoP/x.md | ACTIVE · LANDING #7 into repoP main |"
add_seed_row "| \`repoP-2\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoP/x.md | IDLE, NOTHING CLAIMED · no LANDING open |"
add_seed_row "| \`repoR-1\` | harness \`$R_ID\` | Raven / test / brett | 2026-09-11T00:00Z | none | handoffs/repoR/x.md | ACTIVE |"
add_seed_row "| \`repoH-3\` | harness \`$H_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoH/z.md | ACTIVE |"
# repoS-1 / repoS-2: rows whose LATER cells contain a literal `|`, so they
# split into 10 fields rather than 9. The live register has two such rows.
# For repoS-1, NF-2 is ` still open ` and the handoff path is field 7; for
# repoS-2, NF-1 is ` all good ` and the state cell is fields 8..NF-1 rejoined.
add_seed_row "| \`repoS-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoS/session-handoff-2026-09-11-lane-repoS-1.md | ACTIVE · re-cut | still open |"
add_seed_row "| \`repoS-2\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoS/x.md | ACTIVE · LANDING #7 into repoS main| all good |"

# Rule 6 lines in LANES.md itself: `who --landing` reads THESE, so a lane with
# no object log is still seen, and a retry that re-posts LANDING for one PR is
# one landing and not two.
printf 'LANDING — lane repoP-1, session %s@Eagle, 2026-09-11T01:00:00Z, PR #77 into workBenches main\n' "$DEAD_ID" >> "$LANES"
printf 'LANDING — lane repoP-1, session %s@Eagle, 2026-09-11T01:40:00Z, PR #77 into workBenches main\n' "$DEAD_ID" >> "$LANES"
# One lane, ONE PR number, TWO repositories — the shape this estate lands in
# every day. The LANDED closes the hold on Omni-B and must not touch Omni-A.
printf 'LANDING — lane repoP-1, session %s@Eagle, 2026-09-11T01:00:00Z, PR #5 into opensoft/Omni-A main\n' "$DEAD_ID" >> "$LANES"
printf 'LANDING — lane repoP-1, session %s@Eagle, 2026-09-11T01:10:00Z, PR #5 into opensoft/Omni-B main\n' "$DEAD_ID" >> "$LANES"
printf 'LANDED — lane repoP-1, session %s@Eagle, 2026-09-11T01:20:00Z, PR #5 into opensoft/Omni-B main → abc1234\n' "$DEAD_ID" >> "$LANES"
# A LANDING inside Rule 6'"'"'s thirty minutes, for the other half of the test.
printf 'LANDING — lane repoP-1, session %s@Eagle, %s, PR #91 into opensoft/repoFresh main\n' "$DEAD_ID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LANES"
git -C "$WIP" add -- lanes/LANES.md lanes/lane-start lanes/lane-end lanes/lanes-edit.sh lanes/repos.tsv
git -C "$WIP" commit -q -m "seed the sandbox register"
git -C "$WIP" push -q origin main

START="$WIP/lanes/lane-start"
END="$WIP/lanes/lane-end"

for r in repoA repoB repoC repoD repoE repoF repoG repoH; do mkdir -p "$HOME/projects/$r"; done
git init -q -b main "$HOME/projects/repoA"
# The lane's HOME repo is read from `git remote get-url origin` of its own
# directory. repoB has no remote on purpose: a lane whose home cannot be
# resolved must still start, and say so rather than guess.
git -C "$HOME/projects/repoA" remote add origin git@github.com:opensoft/repoA.git
for r in repoE repoF repoG; do
  git init -q -b main "$HOME/projects/$r"
  git -C "$HOME/projects/$r" remote add origin "https://github.com/opensoft/$r.git"
done

# openRepoShape's assembly-root shape: repoE with a spec and a code leg. Only
# `legs[].repository` is ever read from it.
cat > "$HOME/projects/repoE/project.yaml" <<'YAML'
schema_version: 1
kind: project-manifest
id: repoe
shape:
  repository: opensoft/openRepoShape
legs:
  - role: assembly
    repository: opensoft/repoE
    path: "."
  - role: spec
    repository: opensoft/repoE-spec
    path: spec
  - role: code
    repository: opensoft/repoE-code
    path: code
YAML

# Two levels down — `~/projects/InkRouter/IRRS/project.yaml` is the shape real
# register traffic uses today.
mkdir -p "$HOME/projects/nested/deepP"
cat > "$HOME/projects/nested/deepP/project.yaml" <<'YAML'
schema_version: 1
kind: project-manifest
legs:
  - role: assembly
    repository: opensoft/repoE
    path: "."
  - role: spec
    repository: opensoft/repoE-deep
    path: spec
YAML

# A manifest that still spells a leg the way the org was spelled before the
# move. `opensoft/codexFactory` and `codeXfactory/codexFactory` are ONE
# repository, and the alias table is what says so.
mkdir -p "$HOME/projects/legacyP"
cat > "$HOME/projects/legacyP/project.yaml" <<'YAML'
schema_version: 1
kind: project-manifest
legs:
  - role: assembly
    repository: opensoft/codexFactory
    path: "."
  - role: spec
    repository: opensoft/repoE
    path: spec
YAML

# A family is BROADER than a project: its members are separate projects with
# separate lanes, so `members:` must never read as "not a crossing".
mkdir -p "$HOME/projects/famR/famR"
cat > "$HOME/projects/famR/famR/family.yaml" <<'YAML'
schema_version: 1
kind: family-manifest
members:
  - project: repoE
    repository: opensoft/repoE
    path: members/repoE
  - project: repoFam
    repository: opensoft/repoFam
    path: members/repoFam
YAML

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
write_record_ns() { # <file> <sessionId> <pid> <procStart> <tmux> <name> <nameSource> <status>
  printf '{"pid":%s,"sessionId":"%s","cwd":"x","procStart":"%s","tmux":"%s","name":"%s","nameSource":"%s","status":"%s"}\n' \
    "$3" "$2" "$4" "$5" "$6" "$7" "$8" > "$1"
}
# repoC-1's session was RENAMED to another lane by a person, so its name IS
# evidence: `nameSource: user` is explicit and the record is not a holder.
write_record_ns "$HOME/.claude/sessions/$LIVE_PID.json" "$GONE_ID" "$LIVE_PID" "$live_start" "othersess:@9.%9" "somewhere-else-4" "user" "idle"
# repoF-1: live, and named `repof-99` because the harness DERIVED that from the
# working directory. It IS the holder — the name says nothing either way.
write_record_ns "$sessions_dir/live-derived.json" "$F_ID" "$LIVE_PID" "$live_start" "othersess:@9.%9" "repof-99" "derived" "busy"
# repoG-3: live, and a person renamed it to another lane. NOT the holder.
write_record_ns "$sessions_dir/live-explicit.json" "$G_ID" "$LIVE_PID" "$live_start" "othersess:@9.%9" "somewhere-else-7" "user" "idle"

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

# Seeded object logs, committed so the sandbox worktree stays clean. These are
# fixtures, not writes: everything else below goes through lanes-edit.sh.
OLD_UTC="$(date -u -d '-5 hours' +%Y-%m-%dT%H:%M:%SZ)"
MID_UTC="$(date -u -d '-4 hours -30 minutes' +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "$WIP/lanes/log"
{ printf '# lane repoF-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoF-1, session %s@Eagle, %s, lane:repoF-1 → home opensoft/repoF; estate repoF\n' "$F_ID" "$OLD_UTC"
} > "$WIP/lanes/log/repoF-1.md"
{ printf '# lane repoG-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoG-1, session %s@Eagle, %s, lane:repoG-1 → home opensoft/repoG; estate repoG\n' "$DEAD_ID" "$OLD_UTC"
  printf 'CLAIMED — lane repoG-1, session %s@Eagle, %s, opensoft/repoG#8\n' "$DEAD_ID" "$OLD_UTC"
  printf 'CLAIMED — lane repoG-1, session %s@Eagle, %s, opensoft/repoG#11\n' "$DEAD_ID" "$OLD_UTC"
  printf 'OPENED — lane repoG-1, session %s@Eagle, %s, opensoft/repoG#12 ← opensoft/repoG#11\n' "$DEAD_ID" "$MID_UTC"
  printf 'LANDING — lane repoG-1, session %s@Eagle, %s, opensoft/repoG#9\n' "$DEAD_ID" "$OLD_UTC"
} > "$WIP/lanes/log/repoG-1.md"
git -C "$WIP" add -- lanes/log
git -C "$WIP" commit -q -m "seed two object logs"
git -C "$WIP" push -q origin main

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
has  "the row write is its own commit" "$(git -C "$WIP" log --oneline -1 -- lanes/LANES.md)" "add row"
is   "the row write was pushed" "$(git -C "$WIP" rev-parse HEAD)" "$(git -C "$WIP" rev-parse origin/main)"

run "$START" --estate xFactory --dir "$HOME/projects/repoB" repoA 8 --no-launch
has  "--estate names the handoff directory" "$(grep '^| `repoA-8`' "$LANES")" "handoffs/xFactory/session-handoff-"

run "$START" repoA 1 --no-launch
is    "a free lane resumes THE ROW'S RECORDED SESSION, by id" "$out" "claude --resume $DEAD_ID"
hasnt "…and never by the ambiguous title" "$out" "--resume repoA-1"
has   "…saying it is the row's own transcript" "$err" "the row's current session is $DEAD_ID and its transcript is here"
has   "…having taken live-holder's 8 as the ANSWER it is: this lane is parked" "$err" "no live session holds repoA-1"
has  "a free lane appends a status, not a row" "$(git -C "$WIP" log --oneline -1 -- lanes/LANES.md)" "lane-start on"
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
has  "…in its own register commit" "$(git -C "$WIP" log --oneline -1 -- lanes/LANES.md)" "session cell: lane-start minted $REPOA14_SID"

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


echo "== Amendment 7: the per-lane object log =="

E="$WIP/lanes/lanes-edit.sh"
WS_S="$(hostname -s)"
LOGD="$WIP/lanes/log"

# ------------------------------------------ lane-start writes the STARTED line

run "$START" repoE 1 --no-launch
is   "lane-start on a lane with an origin exits 0" "$rc" 0
is   "…and creates the lane's own log file" "$( [ -f "$LOGD/repoE-1.md" ] && echo yes )" "yes"
is   "…whose line 1 is the header" "$(head -n1 "$LOGD/repoE-1.md")" "# lane repoE-1 — object log (lane-collision-protocol Amendment 7)"
E1_STARTED="$(grep '^STARTED' "$LOGD/repoE-1.md" | tail -n1)"
has  "…and whose STARTED line uses lane:<name> as its object" "$E1_STARTED" ", lane:repoE-1 → home opensoft/repoE; estate repoE"
has  "…with the home taken from git remote get-url origin" "$E1_STARTED" "home opensoft/repoE"
has  "…and the payload sub-fields separated by '; '" "$E1_STARTED" "; estate repoE"
has  "…written as its own LOG commit" "$(git -C "$WIP" log --oneline -1)" "LOG(repoE-1@$WS_S): STARTED lane:repoE-1"
is   "…and pushed" "$(git -C "$WIP" rev-parse HEAD)" "$(git -C "$WIP" rev-parse origin/main)"
is   "…while LANES.md keeps its own last commit" "$(git -C "$WIP" log --oneline -1 -- lanes/LANES.md | grep -c 'LOG(')" 0

run "$START" --dir "$HOME/projects/repoB" --estate repoB repoQ-1 --no-launch
has  "a lane whose checkout has no origin still starts, and says the home is unknown" "$err" "has no 'origin' remote"
has  "…recording it as unknown rather than guessing" "$(cat "$LOGD/repoQ-1.md")" "lane:repoQ-1 → home unknown; estate repoB"

run "$START" repoA 1 --no-launch
is   "a resumed lane still resumes by id" "$out" "claude --resume $DEAD_ID"
has  "…and its log line is a RESUMED, not a STARTED" "$(cat "$LOGD/repoA-1.md")" "RESUMED — lane repoA-1, session "
has  "…carrying the same lane: object" "$(cat "$LOGD/repoA-1.md")" ", lane:repoA-1 → home opensoft/repoA; estate repoA"

before_rev="$(git -C "$WIP" rev-parse HEAD)"
run "$START" --dry-run repoE 1
is   "--dry-run writes no log commit either" "$(git -C "$WIP" rev-parse HEAD)" "$before_rev"
has  "…and says what it would log" "$err" "PLAN lanes-edit.sh log STARTED lane:repoE-1"

# ------------------------------------------------------------------ log

run env LANES_LANE=repoE-1 "$E" log OPENED "opensoft/repoE#12" "←" "opensoft/repoE#11"
is   "log OPENED exits 0" "$rc" 0
has  "…appending the event in the grammar's shape" "$(cat "$LOGD/repoE-1.md")" ", opensoft/repoE#12 ← opensoft/repoE#11"
has  "…in a LOG(<lane>@<ws>) commit naming the verb and the object" "$(git -C "$WIP" log --oneline -1)" "LOG(repoE-1@$WS_S): OPENED opensoft/repoE#12"

run env LANES_LANE=repoE-1 "$E" log MERGED "opensoft/repoE#12"
is   "MERGED is not a verb any more — LANDED is the post-merge line" "$rc" 2
has  "…and the refusal lists the verbs" "$err" "is not one of the Amendment 7 verbs"

run env LANES_LANE=repoE-1 "$E" log PAUSED
is   "a lane verb still needs its lane: object" "$rc" 2
run env LANES_LANE=repoE-1 "$E" log PAUSED "lane:repoE-1"
is   "…and takes it" "$rc" 0
has  "…writing a line whose object is the lane and which has no payload" "$(grep '^PAUSED' "$LOGD/repoE-1.md")" ", lane:repoE-1"

run env LANES_LANE=repoE-1 "$E" log OPENED "lane:repoE-1"
is   "an object verb refuses a lane: object" "$rc" 2
run env LANES_LANE=repoE-1 "$E" log STARTED "opensoft/repoE#1"
is   "…and a lane verb refuses an object key" "$rc" 2

run env LANES_LANE=repoE-1 "$E" log NOPE "opensoft/repoE#12"
is   "an unknown verb is refused" "$rc" 2
run env LANES_LANE=repoE-1 "$E" log OPENED "not-an-object"
is   "a malformed object key is refused" "$rc" 2
run env LANES_LANE=repoE-1 "$E" log OPENED "nosuchrepo#3"
is   "an unknown alias is refused" "$rc" 2
has  "…with the hint to spell owner/repo" "$err" "spell it owner/repo"

run env LANES_LANE=repoE-1 "$E" log CLOSED "opensoft/codexFactory#9" "→" "opensoft/openxFactory#4"
is   "a legacy spelling is accepted" "$rc" 0
has  "…and is written as the canonical nameWithOwner" "$(cat "$LOGD/repoE-1.md")" ", codeXfactory/codexFactory#9 → opensoft/openxFactory#4"
run env LANES_LANE=repoE-1 "$E" log CLOSED "Hermes-Install#3" "→" "opensoft/openxFactory#4"
has  "…as is an alias with no owner at all" "$(cat "$LOGD/repoE-1.md")" ", opensoft/Hermes-Install#3 → opensoft/openxFactory#4"

run env LANES_LANE=repoE-1 "$E" log OPENED "oxF#3"
is   "a spelling the register uses but nothing resolved is refused, not guessed" "$rc" 2

run env LANES_LANE=repoE-1 "$E" claim "#7" --no-github
is   "#<n> expands to the lane's own home repo" "$rc" 0
has  "…spelled out in the line" "$(cat "$LOGD/repoE-1.md")" ", opensoft/repoE#7"
run env LANES_LANE=repoQ-1 "$E" claim "#7" --no-github
is   "…and is refused for a lane whose home is unknown" "$rc" 2
has  "…naming --home as the way out" "$err" "--home owner/repo"
run env LANES_LANE=repoQ-1 "$E" claim "#7" --home opensoft/repoQ --no-github
is   "…which --home supplies for a pre-cutover lane" "$rc" 0
has  "…resolving the shorthand against it" "$(cat "$LOGD/repoQ-1.md")" ", opensoft/repoQ#7"

run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoE:openspec/changes/add-thing" --no-github
is   "an OpenSpec change directory is an object key too" "$rc" 0

# The four verbs that have a guarded subcommand of their own are not written by
# hand: `log CLAIMED` skipped the pre-check, the race and the rescan, and `who`
# reported the result identically to a real claim.
run env LANES_LANE=repoE-1 "$E" log CLAIMED "opensoft/repoE#33"
is   "log CLAIMED is refused — a claim is not a hand-written line" "$rc" 2
has  "…pointing at the subcommand that runs the race" "$err" "lanes-edit.sh claim opensoft/repoE#33"
run env LANES_LANE=repoE-1 "$E" log TAKEOVER "opensoft/repoE#33"
is   "log TAKEOVER is refused — only a STALE claim may be taken over" "$rc" 2
has  "…pointing at --force" "$err" "claim opensoft/repoE#33 --force"
run env LANES_LANE=repoE-1 "$E" log RELEASED "opensoft/repoE#33"
is   "log RELEASED is refused" "$rc" 2
has  "…pointing at release, which also posts the comment" "$err" "lanes-edit.sh release opensoft/repoE#33"
run env LANES_LANE=repoE-1 "$E" log CLAIM-LOST "opensoft/repoE#33"
is   "log CLAIM-LOST is refused — losing a race has no hand-written form" "$rc" 2
hasnt "…and not one of the four wrote a line" "$(cat "$LOGD/repoE-1.md")" "opensoft/repoE#33"
run env LANES_LANE=repoE-1 "$E" log WITHDRAWN "opensoft/repoE#34"
is   "…while a verb with no subcommand of its own is still accepted" "$rc" 0

# --home is validated, and refused where the lane's own log answers the question.
run env LANES_LANE=repoQ-1 "$E" log OPENED "#7" --home 'not a repo'
is   "an invalid --home is refused, never written into an object key" "$rc" 2
has  "…saying what a home is" "$err" "--home takes owner/repo"
hasnt "…and no unreadable line is written" "$(cat "$LOGD/repoQ-1.md")" "not a repo#7"
run env LANES_LANE=repoQ-1 "$E" log OPENED "#8" --home workBenches
is   "…while a known alias is accepted" "$rc" 0
has  "…and canonicalised to owner/repo" "$(cat "$LOGD/repoQ-1.md")" ", opensoft/workBenches#8"
run env LANES_LANE=repoE-1 "$E" log OPENED "#9" --home opensoft/SOMEWHEREELSE
is   "--home is REFUSED where the lane's STARTED line already answers it" "$rc" 2
has  "…naming the home the log records" "$err" "already records its home: opensoft/repoE"
hasnt "…and the flag never overrides the log" "$(cat "$LOGD/repoE-1.md")" "SOMEWHEREELSE"

# ------------------------------------------------------------ claim / who

run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoE#21" --no-github
is   "claim on a free object exits 0" "$rc" 0
has  "…printing Rule 1's three reads" "$out" "3. git ls-remote --heads"
has  "…which --no-github skips rather than performs" "$out" "not read (--no-github)"
has  "…and marking the line as not yet a Rule 1 claim" "$(cat "$LOGD/repoE-1.md")" ", opensoft/repoE#21 — no-github"

run "$E" who "opensoft/repoE#21"
is   "who finds it" "$rc" 0
has  "…naming the lane that holds it" "$out" "HOLDS    lane repoE-1"
has  "…and calling the object held" "$out" "state    HELD"
has  "…saying the line is local only until the comment exists" "$out" "local only — no GitHub claim comment"
has  "…and not stale" "$out" "stale    no"
has  "…the lane's home" "$out" "home     opensoft/repoE"
has  "…that the holder is parked, not live" "$out" "NOT LIVE (parked"
has  "…the address and the resume command" "$out" "address  @repoE-1 · claude --resume"
has  "…the handoff the row points at" "$out" "handoff  handoffs/repoE/session-handoff-"
has  "…and where the line itself lives" "$out" "log      lanes/log/repoE-1.md"

run "$E" who "opensoft/repoE#9999"
is   "who on an object no lane has touched exits 8" "$rc" 8
has  "…saying so" "$out" "no record of opensoft/repoE#9999"

# STATE IS PER LANE: one lane's RELEASED closes only its own hold.
run env LANES_LANE=repoG-3 "$E" release "opensoft/repoE#21" --no-github
run "$E" who "opensoft/repoE#21"
is   "another lane's RELEASED does not close this lane's hold" "$rc" 0
has  "…the holder is still the lane that claimed it" "$out" "HOLDS    lane repoE-1"
has  "…and the other lane's line is shown as closed" "$out" "closed   lane repoG-3"
has  "…with the object still HELD" "$out" "state    HELD"

run "$E" who --lane repoE-1
is   "who --lane lists the lane's open objects" "$rc" 0
has  "…including the claim" "$out" "opensoft/repoE#21"
hasnt "…and never the lane's own lane: lines" "$out" "lane:repoE-1"

run "$E" who --lane repoG-3
is   "who --lane on a lane that holds nothing is an ANSWER, exit 0" "$rc" 0
has  "…in words" "$out" "none open — lane repoG-3 holds nothing open"

run "$E" who --lane repoNOSUCH-4
is   "who --lane on a pre-cutover lane exits 8" "$rc" 8
has  "…with the pre-cutover sentence" "$out" "no log for repoNOSUCH-4; see its row's state cell"

run env LANES_LANE=repoF-1 "$E" claim "opensoft/repoE#21" --no-github
is   "claim on an object another lane holds exits 2" "$rc" 2
has  "…printing who holds it" "$out" "HOLDS    lane repoE-1"
has  "…and refusing in Rule 1's words" "$err" "stops and reports"
hasnt "…and writing nothing to the taker's log" "$(cat "$LOGD/repoF-1.md")" "opensoft/repoE#21"

# A claim is decided by which CLAIMED LANDS first, and a rebase is what makes
# that decidable — so a checkout that cannot be rebased is refused outright.
printf '# a peer left this here mid-write\n' >> "$WIP/lanes/lane-start"
run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoE#30" --no-github
is   "claim refuses on a checkout that cannot be rebased" "$rc" 2
has  "…naming the offending file" "$err" "lanes/lane-start"
has  "…and why it matters" "$err" "the race cannot be run safely here"
git -C "$WIP" checkout -q -- lanes/lane-start
run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoE#30" --no-github
is   "…and takes the claim once the tree is clean again" "$rc" 0

# R11 (Addendum 3) — the guard TOLERATES a peer's uncommitted REGISTER edit.
# `lanes/LANES.md` is dirty in this shared checkout for much of the day: the
# register takes ~500 commits a day and a half-written row is what one of them
# looks like a second before it lands, so refusing every claim on it would push
# lanes to stop using the tool. `claim`, `release` and `log` take the helper's
# existing pre-existing capture for the register FIRST — its own attributed
# commit, with the same warning every register write already prints — and only
# then re-test the checkout. What F1 fixed is untouched: the register never
# reaches commit_push dirty, so Amendment 5(d)'s skip-the-pull branch — the one
# that disables the rescan deciding the race — is still unreachable from all
# three.
before_rev="$(git -C "$WIP" rev-parse HEAD)"
printf 'a peer left this register line uncommitted\n' >> "$LANES"
run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoE#31" --no-github
is   "a dirty lanes/LANES.md no longer refuses a claim: it is CAPTURED first" "$rc" 0
has  "…warning that the content is not this invocation's" "$err" "not this invocation's"
has  "…and capturing it as its own attributed commit" "$err" "captured pre-existing edit"
has  "…while the claim itself is written to the lane's own log" "$(cat "$LOGD/repoE-1.md")" ", opensoft/repoE#31"
is   "…leaving the register clean behind it" "$(git -C "$WIP" status --porcelain -- lanes/LANES.md | grep -c .)" 0
is   "…as TWO commits, never one" "$(git -C "$WIP" rev-list --count "$before_rev..HEAD")" 2
has  "…the capture the older of the two" "$(git -C "$WIP" log --format=%s "$before_rev..HEAD" | tail -n1)" "LANES(pre-existing@"
is   "…carrying the register and nothing else" "$(git -C "$WIP" show --name-only --format= 'HEAD~1')" "lanes/LANES.md"
has  "…and the peer's own line, attributed to nobody else" "$(git -C "$WIP" show 'HEAD~1')" "+a peer left this register line uncommitted"
has  "…the claim the newer" "$(git -C "$WIP" log --format=%s -n1 HEAD)" "LOG(repoE-1@"
is   "…carrying the lane's log and nothing else" "$(git -C "$WIP" show --name-only --format= HEAD)" "lanes/log/repoE-1.md"

printf 'and a second peer line, still uncommitted\n' >> "$LANES"
run env LANES_LANE=repoE-1 "$E" log OPENED "opensoft/repoE#32" --no-github
is   "log takes the same capture and proceeds" "$rc" 0
has  "…capturing the peer's line first" "$err" "captured pre-existing edit"
has  "…and writing its own line" "$(cat "$LOGD/repoE-1.md")" ", opensoft/repoE#32"
printf 'and a third peer line, still uncommitted\n' >> "$LANES"
run env LANES_LANE=repoE-1 "$E" release "opensoft/repoE#31" "capture then release" --no-github
is   "release does too" "$rc" 0
has  "…capturing first" "$err" "captured pre-existing edit"
has  "…and writing the RELEASED line" "$(cat "$LOGD/repoE-1.md")" ", opensoft/repoE#31 — capture then release"

# …and ANYTHING ELSE is still a refusal, exit 2. That refusal is taken BEFORE
# the lock and before the capture, so a write that refuses never leaves a
# commit of somebody else's register line behind either.
before_rev="$(git -C "$WIP" rev-parse HEAD)"
printf '# a peer left this here mid-write\n' >> "$WIP/lanes/lane-start"
printf 'and a register line at the same moment\n' >> "$LANES"
run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoE#35" --no-github
is   "a dirty file that is NOT the register still refuses a claim" "$rc" 2
has  "…naming it" "$err" "lanes/lane-start"
has  "…and why it matters" "$err" "the race cannot be run safely here"
has  "…with the recovery its own author runs" "$err" "handoff(<lane>@<workstation>)"
hasnt "…writing nothing to the lane's log" "$(cat "$LOGD/repoE-1.md")" "opensoft/repoE#35"
is   "…and making no commit at all" "$(git -C "$WIP" rev-parse HEAD)" "$before_rev"
hasnt "…not even the pre-existing capture: the refusal comes first" "$err" "captured pre-existing edit"
is   "…so the peer's register edit is left exactly as it was found" "$(git -C "$WIP" status --porcelain -- lanes/LANES.md | awk '{print $1}')" "M"
run env LANES_LANE=repoE-1 "$E" log OPENED "opensoft/repoE#36" --no-github
is   "log refuses on the same checkout" "$rc" 2
run env LANES_LANE=repoE-1 "$E" release "opensoft/repoE#32" "refused, never written" --no-github
is   "release refuses on it as well" "$rc" 2
hasnt "…so the release was not written either" "$(cat "$LOGD/repoE-1.md")" "refused, never written"
git -C "$WIP" checkout -q -- lanes/lane-start

# A LANDING reaches the same place by the other road: the register is one of
# ITS OWN pathspecs, so the ordinary handle_preexisting call captures it and
# R11's capture stands aside. One behaviour, two routes, and the register is
# never left dirty for commit_push either way.
run env LANES_LANE=repoE-1 "$E" log LANDING "opensoft/repoE#41" --no-github
is   "a LANDING still writes with a dirty register: that file is one of ITS pathspecs" "$rc" 0
has  "…capturing the peer's line as its own commit first" "$err" "captured pre-existing edit"
run env LANES_LANE=repoE-1 "$E" log LANDED "opensoft/repoE#41" "→" "def5678"
is   "…and its LANDED closes it again" "$rc" 0
printf '# a peer left this here mid-write\n' >> "$WIP/lanes/lane-start"
run env LANES_LANE=repoE-1 "$E" log LANDING "opensoft/repoE#42" --no-github
is   "…while an UNRELATED dirty file refuses a LANDING too: the exemption is those two paths and no others" "$rc" 2
has  "…naming it" "$err" "lanes/lane-start"
git -C "$WIP" checkout -q -- lanes/lane-start

# --------------------------------------------------- the cross-repo warning

run env LANES_LANE=repoE-1 "$E" claim "opensoft/workBenches#3" --no-github
is   "a cross-repo claim still succeeds — it warns, it never refuses" "$rc" 0
has  "…with the warning" "$err" "CROSS-REPO — opensoft/workBenches is not lane repoE-1's home (opensoft/repoE)"
has  "…saying explicitly that it proceeds" "$err" "it never refuses"

run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoE-spec#2" --no-github
is   "a claim on a leg of the same project.yaml exits 0" "$rc" 0
has  "…and is reported as not a crossing" "$err" "are legs of one project.yaml — not a crossing"
has  "…naming the manifest it read" "$err" "$HOME/projects/repoE/project.yaml"
hasnt "…so no cross-repo warning is printed" "$err" "CROSS-REPO"

run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoE-deep#2" --no-github
is   "a manifest two levels under PROJECTS_ROOT is found too" "$rc" 0
has  "…and named" "$err" "$HOME/projects/nested/deepP/project.yaml"

run env LANES_LANE=repoE-1 "$E" claim "codeXfactory/codexFactory#3" --no-github
is   "a manifest that spells a leg the pre-move way is still ONE project" "$rc" 0
has  "…both values resolved through repos.tsv before comparing" "$err" "are legs of one project.yaml — not a crossing"
hasnt "…so no crossing is reported" "$err" "CROSS-REPO — codeXfactory/codexFactory"

run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoFam#2" --no-github
is   "a claim on a family member is still a claim" "$rc" 0
has  "…and family membership does NOT suppress the crossing warning" "$err" "CROSS-REPO — opensoft/repoFam is not lane repoE-1's home"

run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoF#5" --no-github
has  "a crossing names the LIVE lane homed on the target repo" "$err" "LIVE lane homed on opensoft/repoF: @repoF-1"
has  "…with its last transcript uuid" "$err" "last transcript uuid $F_ID"
has  "…and the command that reaches it" "$err" "claude --resume $F_ID"

# -------------------------------------------------------- stale and takeover

run env LANES_LANE=repoG-1 "$E" claim "opensoft/repoG#10" --no-github
is   "a fresh claim by another lane is made" "$rc" 0
run env LANES_LANE=repoG-2 "$E" claim "opensoft/repoG#10" --no-github --force
is   "--force on a claim that is NOT stale is refused" "$rc" 2
has  "…naming the threshold" "$err" "threshold ${STALE_H}h"
hasnt "…and no takeover is written" "$(cat "$LOGD/repoG-2.md" 2>/dev/null)" "opensoft/repoG#10"

run "$E" who "opensoft/repoG#8"
has  "who reports a four-hour-old claim with no PR as stale" "$out" "stale    YES"
has  "…and says a takeover is allowed" "$out" "a takeover is allowed (claim --force)"

# Rule 1's own definition: a claim followed by a PR that names it is not stale.
run "$E" who "opensoft/repoG#11"
has  "an equally old claim whose lane has since OPENED a PR naming it is NOT stale" "$out" "stale    no"

run env LANES_LANE=repoG-2 "$E" claim "opensoft/repoG#9" --no-github --force
is   "--force takes over a stale CLAIMED and nothing else" "$rc" 2
has  "…refusing on an open LANDING" "$err" "is not a stale claim"

run env LANES_LANE=repoG-2 "$E" claim "opensoft/repoG#8" --no-github --force
is   "--force on a stale claim takes it over" "$rc" 0
G2="$(cat "$LOGD/repoG-2.md")"
has  "…writing a TAKEOVER line" "$G2" "TAKEOVER — lane repoG-2, session "
has  "…referencing the claim it supersedes with ←" "$G2" "opensoft/repoG#8 ← lane:repoG-1"
hasnt "…and no separate CLAIMED line: TAKEOVER is itself an open verb" "$G2" "CLAIMED — lane repoG-2, session .*opensoft/repoG#8"

run "$E" who "opensoft/repoG#8"
has  "…so the taker now holds it" "$out" "HOLDS    lane repoG-2"
has  "…by TAKEOVER, which is itself an open verb" "$out" "TAKEOVER  "
has  "…and the dispossessed lane's CLAIMED reads as superseded, not as a hold" "$out" "superseded by TAKEOVER (lane:repoG-2)"
has  "…naming the release that closes its own line" "$out" "lanes-edit.sh release opensoft/repoG#8"
is   "…and exactly one lane holds it" "$(printf '%s\n' "$out" | grep -c '^HOLDS')" 1

run "$END" repoG-1
is   "the dispossessed lane's lane-end refuses" "$rc" 2
has  "…and names the takeover rather than leaving it stuck" "$err" "taken over by lane:repoG-2 at"
has  "…with the exact release that frees it" "$err" "run: lanes-edit.sh release opensoft/repoG#8"
run env LANES_LANE=repoG-1 "$E" release "opensoft/repoG#8" "taken over by repoG-2" --no-github
is   "…and release closes its own line" "$rc" 0
run "$E" who "opensoft/repoG#8"
hasnt "…so it is no longer listed as superseded" "$out" "superseded by TAKEOVER"

# ------------------------------------------- LANDING, LANDED, who --landing

before_lanes="$(grep -c . "$LANES")"
run env LANES_LANE=repoE-1 "$E" log LANDING "opensoft/repoE#21"
is   "log LANDING exits 0" "$rc" 0
is   "…and appends exactly one line to LANES.md as well" "$(grep -c . "$LANES")" "$((before_lanes + 1))"
has  "…in Rule 6's own words, so other lanes read it as the merge hold" "$(tail -n1 "$LANES")" "LANDING — lane repoE-1, session "
has  "…naming the PR and the repo" "$(tail -n1 "$LANES")" "PR #21 into opensoft/repoE main"
is   "…and both files land in ONE commit, with two pathspecs" "$(git -C "$WIP" show --name-only --format= HEAD | grep -c .)" 2
has  "…the register" "$(git -C "$WIP" show --name-only --format= HEAD)" "lanes/LANES.md"
has  "…and the lane's log" "$(git -C "$WIP" show --name-only --format= HEAD)" "lanes/log/repoE-1.md"

run "$E" who --landing opensoft/repoE
is   "who --landing lists the open LANDING for a repo" "$rc" 0
has  "…naming the object and the lane" "$out" "LANDING  opensoft/repoE#21  lane repoE-1"

# R5: the merge hold is read from LANES.md, so a PRE-CUTOVER lane with no log
# of its own is still seen — and a retry that re-posts LANDING for the same PR
# is one landing, not two.
run "$E" who --landing opensoft/workBenches
is   "who --landing reads LANES.md, so a lane with no log is still seen" "$rc" 0
has  "…naming it" "$out" "LANDING  opensoft/workBenches#77  lane repoP-1"
is   "…and a re-posted LANDING for the same PR counts once" "$(printf '%s\n' "$out" | grep -c 'workBenches#77')" 1
has  "…and marks it past Rule 6's thirty minutes rather than reporting it as live" "$out" "STALE (Rule 6: >30 min)"

run "$E" who --landing opensoft/repoFresh
has  "…while a LANDING inside the window is listed unmarked" "$out" "LANDING  opensoft/repoFresh#91"
hasnt "…with no STALE against it" "$out" "STALE"

# The key is (lane, repo, PR). On (lane, PR) alone, this lane's LANDED on
# Omni-B closed its own still-open LANDING on Omni-A and the hold vanished.
run "$E" who --landing opensoft/Omni-A
is   "who --landing keys on (lane, repo, PR)" "$rc" 0
has  "…so a LANDED on ANOTHER repo does not close this hold" "$out" "LANDING  opensoft/Omni-A#5  lane repoP-1"
run "$E" who --landing opensoft/Omni-B
is   "…while the repo that really landed reports an answer, not an absence" "$rc" 0
has  "…in words" "$out" "none open"
hasnt "…and does not list it" "$out" "LANDING  opensoft/Omni-B#5"

run env LANES_LANE=repoE-1 "$E" log LANDED "opensoft/repoE#21" "→" "abc1234"
has  "LANDED closes the window in LANES.md as well" "$(tail -n1 "$LANES")" "PR #21 into opensoft/repoE main → abc1234"
run "$E" who --landing opensoft/repoE
is   "…so who --landing no longer lists it — and an empty answer is exit 0" "$rc" 0
has  "…saying none is open" "$out" "none open"
has  "…with the lane logs reported after it, as secondary" "$out" "from lane logs (secondary):"
has  "…naming this lane's own last line on the PR" "$out" "LANDED   opensoft/repoE#21"
run "$E" who "opensoft/repoE#21"
has  "…and the lane's own hold on it is closed" "$out" "closed   lane repoE-1"
has  "…by the LANDED that carries the merge sha" "$out" "LANDED    "
has  "…leaving the object free" "$out" "state    FREE"

# ------------------------------------------------------------ release

run env LANES_LANE=repoE-1 "$E" release "opensoft/workBenches#3" "not ours after all" --no-github
is   "release exits 0" "$rc" 0
has  "…writing a RELEASED line carrying the reason" "$(cat "$LOGD/repoE-1.md")" ", opensoft/workBenches#3 — not ours after all"

# ---------------------------------------------------------- CLAIM-LOST
#
# The race is decided by which CLAIMED LANDS on main first. The peer commits
# and pushes; this lane's fetch is deferred, so its pre-check sees a main that
# does not yet carry the peer's line — and the peer's claim arrives exactly
# where it arrives in life: in the rebase inside its own push.
CLONE2="$SANDBOX/clone2"
git clone -q "$ORIGIN" "$CLONE2" 2>/dev/null
git -C "$CLONE2" config user.email "peer@example.invalid"
git -C "$CLONE2" config user.name  "the other workstation"
mkdir -p "$CLONE2/lanes/log"
{ printf '# lane repoH-2 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'CLAIMED — lane repoH-2, session %s@Raven, %s, opensoft/repoH#4\n' "$DEAD_ID" "$(date -u -d '-2 minutes' +%Y-%m-%dT%H:%M:%SZ)"
} > "$CLONE2/lanes/log/repoH-2.md"
git -C "$CLONE2" add -- lanes/log/repoH-2.md
git -C "$CLONE2" commit -q -m "LOG(repoH-2@Raven): CLAIMED opensoft/repoH#4"
git -C "$CLONE2" push -q origin main

run env LANES_LANE=repoH-1 LANES_NO_FETCH=1 "$E" claim "opensoft/repoH#4" --no-github
is   "a claim whose rival landed first exits 7" "$rc" 7
has  "…naming the lane that landed first" "$err" "another lane's claim landed on main before this one: @repoH-2"
has  "…and citing Rule 1 rather than queueing" "$err" "stop and report"
has  "…writing a CLAIM-LOST line in this lane's own log" "$(cat "$LOGD/repoH-1.md")" "CLAIM-LOST — lane repoH-1, session "
has  "…that points at the winner with the lane: form" "$(cat "$LOGD/repoH-1.md")" "opensoft/repoH#4 → lane:repoH-2"
run "$E" who "opensoft/repoH#4"
has  "…and the object is the winner's" "$out" "HOLDS    lane repoH-2"
is   "…and the loser holds nothing" "$(printf '%s\n' "$out" | grep -c '^HOLDS')" 1

# The winner is whichever rival is ALREADY on the rebased history — the one
# that LANDED first — and never the earliest timestamp. Two rivals land during
# one rebase window: repoH-2 lands FIRST carrying the LATER UTC.
LATE_UTC="$(date -u -d '+10 minutes' +%Y-%m-%dT%H:%M:%SZ)"
EARLY_UTC="$(date -u -d '+5 minutes' +%Y-%m-%dT%H:%M:%SZ)"
git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
printf 'CLAIMED — lane repoH-2, session %s@Raven, %s, opensoft/repoH#60\n' "$DEAD_ID" "$LATE_UTC" >> "$CLONE2/lanes/log/repoH-2.md"
git -C "$CLONE2" add -- lanes/log/repoH-2.md
git -C "$CLONE2" commit -q -m "LOG(repoH-2@Raven): CLAIMED opensoft/repoH#60"
git -C "$CLONE2" push -q origin main
{ printf '# lane repoH-4 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'CLAIMED — lane repoH-4, session %s@Raven, %s, opensoft/repoH#60\n' "$DEAD_ID" "$EARLY_UTC"
} > "$CLONE2/lanes/log/repoH-4.md"
git -C "$CLONE2" add -- lanes/log/repoH-4.md
git -C "$CLONE2" commit -q -m "LOG(repoH-4@Raven): CLAIMED opensoft/repoH#60"
git -C "$CLONE2" push -q origin main

run env LANES_LANE=repoH-1 LANES_NO_FETCH=1 "$E" claim "opensoft/repoH#60" --no-github
is   "a claim that two rivals beat to main exits 7" "$rc" 7
has  "…naming the one that LANDED first" "$err" "@repoH-2"
hasnt "…never the one whose timestamp is earlier" "$err" "@repoH-4"
has  "…and the CLAIM-LOST line points at that winner" "$(cat "$LOGD/repoH-1.md")" "opensoft/repoH#60 → lane:repoH-2"

# ---------------------------------------------- every read is of origin/main
#
# A read must see what LANDED, not what this checkout happens to have pulled.
# The peer lands a claim from the other clone; this one never pulls it.
peer_log_line() { git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
  printf '%s\n' "$1" >> "$CLONE2/lanes/log/repoH-2.md"
  git -C "$CLONE2" add -- lanes/log/repoH-2.md
  git -C "$CLONE2" commit -q -m "LOG(repoH-2@Raven): $2"
  git -C "$CLONE2" push -q origin main; }

peer_log_line "CLAIMED — lane repoH-2, session $DEAD_ID@Raven, $(date -u +%Y-%m-%dT%H:%M:%SZ), opensoft/repoH#50" "CLAIMED opensoft/repoH#50"
is   "the peer's claim is on origin/main and NOT in this checkout's working tree" "$(grep -c 'repoH#50' "$LOGD/repoH-2.md" 2>/dev/null || :)" 0
run "$E" who "opensoft/repoH#50"
is   "who reads origin/main, so it sees a claim this checkout has not pulled" "$rc" 0
has  "…naming the lane that holds it" "$out" "HOLDS    lane repoH-2"
run env LANES_LANE=repoH-1 "$E" claim "opensoft/repoH#50" --no-github
is   "…and a claim on it is refused rather than raced" "$rc" 2
hasnt "…nothing written to the would-be taker's log" "$(cat "$LOGD/repoH-1.md")" "opensoft/repoH#50"

# Staleness comes from the same place. Rule 1: a claim its lane has since
# discharged with a PR that names the issue is NOT stale — and that OPENED
# line can only be seen by reading what landed.
peer_log_line "CLAIMED — lane repoH-2, session $DEAD_ID@Raven, $OLD_UTC, opensoft/repoH#51" "CLAIMED opensoft/repoH#51"
peer_log_line "OPENED — lane repoH-2, session $DEAD_ID@Raven, $MID_UTC, opensoft/repoH#52 ← opensoft/repoH#51" "OPENED opensoft/repoH#52"
is   "the peer's claim AND the PR that discharges it are on origin/main only" "$(grep -c 'repoH#51' "$LOGD/repoH-2.md" 2>/dev/null || :)" 0
run env LANES_LANE=repoH-1 "$E" claim "opensoft/repoH#51" --force --no-github
is   "--force reads staleness from origin/main too, so a four-hour-old claim with a PR is refused" "$rc" 2
has  "…in Rule 1's own words" "$err" "has since OPENED a PR naming it"
hasnt "…and no TAKEOVER is written on a claim that is not stale" "$(cat "$LOGD/repoH-1.md")" "opensoft/repoH#51"

# ------------------------- R11 and the race, in the same run (F1's own repro)
#
# The two halves together: a rival's CLAIMED is already on `main`, and THIS
# checkout carries a peer's half-written register line. Before F1 this sequence
# left an unpushed local CLAIMED and two lanes holding one object; after F1 and
# before R11 it was an exit-2 refusal on the one file this checkout is dirty in
# most of the day. Now the capture clears the way, `pull --rebase` runs, the
# rescan sees the rival, and the loser abandons the claim: one holder, exit 7.
peer_log_line "CLAIMED — lane repoH-2, session $DEAD_ID@Raven, $(date -u +%Y-%m-%dT%H:%M:%SZ), opensoft/repoH#70" "CLAIMED opensoft/repoH#70"
printf 'a peer left this register line uncommitted\n' >> "$LANES"
run env LANES_LANE=repoH-1 LANES_NO_FETCH=1 "$E" claim "opensoft/repoH#70" --no-github
is   "a claim raced from a checkout with a dirty register still LOSES, exit 7" "$rc" 7
has  "…having captured the peer's register line on the way" "$err" "captured pre-existing edit"
has  "…and naming the lane whose claim landed on main first" "$err" "another lane's claim landed on main before this one: @repoH-2"
has  "…writing CLAIM-LOST in this lane's own log" "$(cat "$LOGD/repoH-1.md")" "opensoft/repoH#70 → lane:repoH-2"
is   "…with the register left clean" "$(git -C "$WIP" status --porcelain -- lanes/LANES.md | grep -c .)" 0
run "$E" who "opensoft/repoH#70"
is   "…and exactly one lane holds the object" "$(printf '%s\n' "$out" | grep -c '^HOLDS')" 1
has  "…the one that landed first" "$out" "HOLDS    lane repoH-2"

# ------------------------------------- the row's cells, by header position

run env LANES_LANE=repoS-1 "$E" claim "opensoft/repoS#1" --no-github
is   "a row whose later cells contain a literal | splits into 10 fields" "$(grep '^| `repoS-1`' "$LANES" | awk -F'|' '{print NF}')" 10
run "$E" who "opensoft/repoS#1"
has  "…and its handoff path is found by header position, not by counting back from NF" "$out" "handoff  handoffs/repoS/session-handoff-2026-09-11-lane-repoS-1.md"
hasnt "…never the fragment NF-2 lands on" "$out" "handoff  still open"
has  "…while the workstation column is read from the left as before" "$out" "NOT LIVE (parked"

run "$END" repoS-2
is   "lane-end's pre-cutover scan reads the WHOLE state cell, pipes and all" "$rc" 2
has  "…finding the LANDING that the last fragment alone would have missed" "$err" "the last LANDING in its state cell"

# ------------------------------------------------------------- liveness

run "$E" live-holder repoF-1
is   "a live holder whose record name is DERIVED is still a holder" "$rc" 0
has  "…and it is the right session" "$out" "$F_ID"
run "$START" repoF 1 --no-launch
is   "…so a second window is refused the lane" "$rc" 2
has  "…naming the session that holds it" "$err" "is live in session $F_ID"

write_record_ns "$sessions_dir/live-renamed.json" "$H_ID" "$LIVE_PID" "$live_start" "othersess:@9.%9" "repoH-3" "user" "busy"
run "$E" live-holder repoH-3
is   "a record a person RENAMED to the lane is a holder" "$rc" 0
has  "…and it is the right session" "$out" "$H_ID"

run "$E" live-holder repoG-3
is   "a live record EXPLICITLY named for another lane is not a holder" "$rc" 8
run "$E" live-holder repoA-1
is   "…as is a lane whose every recorded session has ended" "$rc" 8

# ONLY 0 AND 8 ARE ANSWERS. A helper that fails is not a helper that said "no".
cat > "$SANDBOX/failedit" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  live-holder|lane-objects) printf '%s: simulated failure\n' "$1" >&2; exit 3 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/failedit"

before_renames="$(grep -c 'rename-window repoB-1' "$FAKE_TMUX_LOG" || :)"
run env REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/failedit" "$START" repoB 1 --no-launch
is   "lane-start REFUSES when live-holder fails, rather than taking the name" "$rc" 1
has  "…naming the helper and its exit code" "$err" "live-holder repoB-1 failed (exit 3)"
has  "…passing the helper's own stderr through instead of swallowing it" "$err" "live-holder: simulated failure"
hasnt "…and never saying the lane is free" "$err" "this is a resume of a lane whose sessions have all ended"
is   "…and renaming no window on an answer it did not get" "$(grep -c 'rename-window repoB-1' "$FAKE_TMUX_LOG" || :)" "$before_renames"

run "$E" lane-objects repoP-2
is   "lane-objects on a lane with no log exits 8 — the same 8 who uses for no record" "$rc" 8
run env REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/failedit" "$END" repoG-2
is   "lane-end REFUSES when lane-objects fails, rather than calling the lane pre-cutover" "$rc" 1
has  "…naming the helper and its exit code" "$err" "lane-objects repoG-2 failed (exit 3)"
has  "…passing the helper's own stderr through" "$err" "lane-objects: simulated failure"
hasnt "…and never asserting the lane is pre-cutover" "$err" "pre-cutover"
hasnt "…while writing no closing line to its row" "$(grep '^| `repoG-2`' "$LANES")" "window closing"
run "$START" repoG 3 --no-launch
is   "…so that lane is free to start" "$rc" 0

# A lane recorded on ANOTHER workstation cannot be liveness-checked from here:
# session records are local files, so the answer is UNKNOWN, never NOT LIVE.
run env LANES_LANE=repoR-1 "$E" claim "opensoft/repoR#1" --no-github
run "$E" who "opensoft/repoR#1"
has  "a holder on another workstation reads UNKNOWN, never NOT LIVE" "$out" "UNKNOWN (records are local to Raven"
hasnt "…and is never called parked" "$out" "NOT LIVE (parked"
has  "…telling the reader how to reach it" "$out" "ask @repoR-1 or read its handoff"

# ------------------------------------------------ the parser drops nothing

# An append-only log is never rewritten, so a line no parser can read is a hold
# no tool will mention again. Line 2 below uses a hyphen where the grammar wants
# an em dash; line 3 carries a UTC with no seconds, which the register has
# written since before this helper existed and which must still be READ.
{ printf '# lane repoBAD-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'CLAIMED - lane repoBAD-1, session %s@Eagle, 2026-09-11T19:15:00Z, opensoft/repoBAD#10\n' "$DEAD_ID"
  printf 'OPENED — lane repoBAD-1, session %s@Eagle, 2026-09-11T19:15Z, opensoft/repoBAD#11\n' "$DEAD_ID"
} > "$LOGD/repoBAD-1.md"
git -C "$WIP" add -- lanes/log/repoBAD-1.md
git -C "$WIP" commit -q -m "a hand-written log, one line of it unreadable"
git -C "$WIP" push -q origin main

run "$E" who --lane repoBAD-1
is   "a log with one unreadable line is still read" "$rc" 0
has  "…the unreadable line named with its file and line number" "$err" "unreadable: lanes/log/repoBAD-1.md:2"
has  "…and counted" "$err" "unreadable line(s) above"
has  "…while a UTC without seconds is READ rather than dropped" "$out" "opensoft/repoBAD#11"
run "$E" who "opensoft/repoBAD#10"
is   "…and the object on the unreadable line is NOT reported as free" "$rc" 8
has  "…it is reported as no record at all, with the unreadable line named" "$err" "unreadable: lanes/log/repoBAD-1.md:2"
git -C "$WIP" rm -q -- lanes/log/repoBAD-1.md
git -C "$WIP" commit -q -m "drop the unreadable-line fixture"
git -C "$WIP" push -q origin main

# ------------------------------- R14: state is read in FILE ORDER, not by UTC
#
# A lane's log is append-only and single-writer, so the ORDER OF ITS LINES is
# the order of that lane's writes. A clock is not. On 2026-09-11 this
# workstation's realtime clock was jumping ±25s in bursts and a log commit
# landed whose content carried a UTC 26s AFTER its own committer date; two
# workstations never share a clock either. So every fixture below writes its
# NEWEST line with an OLDER UTC than the line above it, and every read must
# still take the newest LINE. Two of these are the exact shapes that made the
# suite fail intermittently at 08e8b05: a LANDED invisible behind the LANDING
# it closed, and a RELEASED still reported as superseded by a TAKEOVER.
JUMP_LATE="$(date -u -d '-3 hours' +%Y-%m-%dT%H:%M:%SZ)"
JUMP_BACK="$(date -u -d '-3 hours -26 seconds' +%Y-%m-%dT%H:%M:%SZ)"
JUMP_OLD="$(date -u -d '-5 hours' +%Y-%m-%dT%H:%M:%SZ)"
JUMP_OLDER="$(date -u -d '-5 hours -26 seconds' +%Y-%m-%dT%H:%M:%SZ)"
{ printf '# lane repoJ-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoJ-1, session %s@Eagle, %s, lane:repoJ-1 → home opensoft/repoJ; estate repoJ\n' "$DEAD_ID" "$JUMP_LATE"
  # #5 — a RELEASED that closes a CLAIMED, stamped 26s in the claim's past.
  printf 'CLAIMED — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#5\n' "$DEAD_ID" "$JUMP_LATE"
  printf 'RELEASED — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#5 — not ours after all\n' "$DEAD_ID" "$JUMP_BACK"
  # #6 — the first failure shape: a LANDED behind the LANDING it closes.
  printf 'LANDING — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#6\n' "$DEAD_ID" "$JUMP_LATE"
  printf 'LANDED — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#6 → abc1234\n' "$DEAD_ID" "$JUMP_BACK"
  # #7 — two OPEN verbs, so the state is the newest LINE and not the larger UTC.
  printf 'LANDING — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#7\n' "$DEAD_ID" "$JUMP_LATE"
  printf 'WITHDRAWN — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#7 — pulled back out of the queue\n' "$DEAD_ID" "$JUMP_BACK"
  # #8 — the second failure shape: this lane has already closed its own line
  # after the takeover, and the TAKEOVER in repoJ-2's log carries a stamp 26s
  # LATER than that RELEASED. "Is their takeover later than our line" then
  # reported a RELEASED as superseded, and the lane could never end.
  printf 'CLAIMED — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#8\n' "$DEAD_ID" "$JUMP_OLD"
  printf 'RELEASED — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#8 — taken over by repoJ-2\n' "$DEAD_ID" "$JUMP_BACK"
  # #9 — the same pair the other way round: the TAKEOVER that displaced this
  # CLAIMED carries an OLDER UTC than the claim it took.
  printf 'CLAIMED — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#9\n' "$DEAD_ID" "$JUMP_LATE"
  # #10 — Rule 1 staleness: the four hours are a DURATION and stay on the
  # clock, but "has this lane OPENED a PR since" is an ORDER — and the OPENED
  # that discharges this claim is below it in the file with an older stamp.
  printf 'CLAIMED — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#10\n' "$DEAD_ID" "$JUMP_OLD"
  printf 'OPENED — lane repoJ-1, session %s@Eagle, %s, opensoft/repoJ#11 ← opensoft/repoJ#10\n' "$DEAD_ID" "$JUMP_OLDER"
} > "$LOGD/repoJ-1.md"
{ printf '# lane repoJ-2 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoJ-2, session %s@Eagle, %s, lane:repoJ-2 → home opensoft/repoJ; estate repoJ\n' "$DEAD_ID" "$JUMP_LATE"
  printf 'TAKEOVER — lane repoJ-2, session %s@Eagle, %s, opensoft/repoJ#8 ← lane:repoJ-1\n' "$DEAD_ID" "$JUMP_LATE"
  printf 'TAKEOVER — lane repoJ-2, session %s@Eagle, %s, opensoft/repoJ#9 ← lane:repoJ-1\n' "$DEAD_ID" "$JUMP_BACK"
} > "$LOGD/repoJ-2.md"
git -C "$WIP" add -- lanes/log/repoJ-1.md lanes/log/repoJ-2.md
git -C "$WIP" commit -q -m "two logs whose newest lines carry older UTCs than the lines above them"
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoJ-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoJ/x.md | ACTIVE |" >/dev/null 2>&1
"$E" add-row "| \`repoJ-2\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoJ/y.md | ACTIVE |" >/dev/null 2>&1
is   "the two clock-jump fixture lanes have rows" "$(grep -c '^| `repoJ-[12]`' "$LANES")" 2

run "$E" who "opensoft/repoJ#6"
is   "who reads a LANDED written 26s 'before' the LANDING it closes" "$rc" 0
is   "…as the lane's last LINE, the closed state" "$(printf '%s\n' "$out" | grep -cE '^closed   lane repoJ-1 +LANDED ')" 1
hasnt "…and not as the LANDING the larger UTC would have won" "$out" "HOLDS"
has  "…leaving the object free" "$out" "state    FREE"

run "$E" who --lane repoJ-1
is   "who --lane drops an object whose newest line closed it" "$(printf '%s\n' "$out" | grep -c 'opensoft/repoJ#6')" 0
is   "…and lists the newest of two OPEN lines, not the one stamped later" "$(printf '%s\n' "$out" | grep -cE '^WITHDRAWN opensoft/repoJ#7')" 1

run "$E" who "opensoft/repoJ#7"
has  "who reports that newest line as the hold" "$out" "WITHDRAWN"
hasnt "…never the LANDING above it in the file" "$out" "LANDING"

run "$E" lane-objects repoJ-1
is   "lane-objects — what lane-end and the handoff fragment read — is file-ordered too" "$rc" 0
has  "…LANDED for the object whose LANDED came last" "$out" "$(printf '\037LANDED\037opensoft/repoJ#6\037')"
hasnt "…and never the LANDING it closed" "$out" "$(printf '\037LANDING\037opensoft/repoJ#6\037')"
has  "…WITHDRAWN for the object whose WITHDRAWN came last" "$out" "$(printf '\037WITHDRAWN\037opensoft/repoJ#7\037')"

run "$E" who --landing opensoft/repoJ
has  "the secondary lane-log listing under who --landing reads the last line too" "$out" "LANDED   opensoft/repoJ#6"
hasnt "…so a landed PR is not re-reported as an open merge hold" "$out" "LANDING  opensoft/repoJ#6"

run "$E" who "opensoft/repoJ#8"
is   "a lane's own RELEASED closes its line whatever a peer's TAKEOVER is stamped" "$rc" 0
is   "…reported as closed" "$(printf '%s\n' "$out" | grep -cE '^closed   lane repoJ-1 +RELEASED ')" 1
hasnt "…never 'superseded', which a TAKEOVER with a later stamp used to print over it" "$out" "super.   lane repoJ-1"
has  "…while the lane that took it over holds it" "$out" "HOLDS    lane repoJ-2"

run "$E" who "opensoft/repoJ#9"
has  "a TAKEOVER supersedes the CLAIMED it displaced even when stamped EARLIER" "$out" "superseded by TAKEOVER (lane:repoJ-2)"
is   "…so exactly one lane holds the object" "$(printf '%s\n' "$out" | grep -c '^HOLDS')" 1
has  "…the taker" "$out" "HOLDS    lane repoJ-2"

run "$E" who "opensoft/repoJ#10"
has  "a five-hour-old claim discharged by an OPENED BELOW it is not stale" "$out" "stale    no"
hasnt "…though that OPENED carries the older UTC" "$out" "stale    YES"
run env LANES_LANE=repoJ-2 "$E" claim "opensoft/repoJ#10" --force --no-github
is   "…so --force is refused on it" "$rc" 2
has  "…in Rule 1's own words" "$err" "has since OPENED a PR naming it"
hasnt "…and no TAKEOVER is written" "$(cat "$LOGD/repoJ-2.md")" "opensoft/repoJ#10"

run "$END" repoJ-1
is   "lane-end refuses on the objects whose NEWEST line is open" "$rc" 2
has  "…naming the WITHDRAWN and not the LANDING above it" "$err" "WITHDRAWN opensoft/repoJ#7"
hasnt "…and never an object whose newest line is a LANDED" "$err" "opensoft/repoJ#6"
has  "…while the claim taken over by an earlier-stamped TAKEOVER names its own way out" "$err" "taken over by lane:repoJ-2 at"

run "$END" repoJ-1 --force
is   "…and --force ends it" "$rc" 0
has  "the handoff fragment lists the LANDED under Done" "$out" "- LANDED — opensoft/repoJ#6 → abc1234"
hasnt "…and not the LANDING it closed" "$out" "- LANDING — opensoft/repoJ#6"
has  "…the RELEASED whose UTC is older than the CLAIMED it closes" "$out" "- RELEASED — opensoft/repoJ#5"
has  "…and the WITHDRAWN under Open" "$out" "- WITHDRAWN — opensoft/repoJ#7"
hasnt "…never the LANDING above it" "$out" "- LANDING — opensoft/repoJ#7"

# ---------------------------------------------------------------- lane-end

run "$END" repoE-1
is   "lane-end refuses while the lane's own log still shows an open object" "$rc" 2
has  "…reading it from the log, exactly, not from the state cell" "$err" "in-flight read from lanes/log/repoE-1.md (exact)"
has  "…and naming the object" "$err" "CLAIMED opensoft/repoE#7"
has  "…and the OpenSpec change it also holds" "$err" "CLAIMED opensoft/repoE:openspec/changes/add-thing"
hasnt "…while a LANDED object is not listed as open" "$err" "LANDING opensoft/repoE#21"

run "$END" repoE-1 --force
is   "--force ends it anyway" "$rc" 0
has  "…and the lane's log says it was forced, in the grammar's own shape" "$(cat "$LOGD/repoE-1.md")" "lane:repoE-1 — forced; open: "
has  "…as an ENDED line whose object is the lane" "$(grep '^ENDED' "$LOGD/repoE-1.md")" ", lane:repoE-1"
has  "…and the handoff fragment is on STDOUT" "$out" "## Done"
has  "…whose header names the CLOSED set it partitioned by" "$out" "## Done (RELEASED, CLAIM-LOST, CLOSED, LANDED)"
has  "…and the OPEN one" "$out" "## Open (CLAIMED, TAKEOVER, OPENED, LANDING, WITHDRAWN)"
has  "…listing what landed" "$out" "- LANDED — opensoft/repoE#21 → abc1234"
has  "…and what is still open" "$out" "## Open"
has  "…naming each open object" "$out" "- CLAIMED — opensoft/repoE#7"

run "$END" repoQ-1 --retire
is   "--retire is refused too while the lane still holds something" "$rc" 2
run "$END" repoQ-1 --retire --force
is   "…and writes a RETIRED line instead of an ENDED one once forced" "$rc" 0
has  "…in the lane's log" "$(cat "$LOGD/repoQ-1.md")" "RETIRED — lane repoQ-1, session "

run "$END" repoP-2
is   "a lane with NO log file still ends, on the state cell's substring scan" "$rc" 0
has  "…and its fragment says why it has no objects to list" "$out" "no object log for repoP-2 (pre-cutover lane)"
run "$END" repoP-1
is   "…and that fallback still refuses an open LANDING" "$rc" 2
has  "…saying it is the pre-cutover scan" "$err" "has no object log yet (pre-cutover)"


echo "== Addendum 5: R17–R23 =="

# ------------------- R17: a LANDED closes the LANDING it answers, by (lane, PR)
#
# 284 of the live register's 308 LANDED lines carry no `into <repo> main` clause
# at all. Keyed on the repository they NAME, those 284 key on the empty string
# and can never close the repository-qualified LANDING they belong to: measured
# over the real register, `who --landing` reported 232 phantom merge holds where
# the genuinely open count was ONE. So the PAIRING is by (lane, PR) in file
# order — a LANDED closes the most recent still-unmatched LANDING of that lane
# and PR — while the RESULT still keys on (lane, repository, PR), which is what
# keeps a LANDED on one repository from closing a LANDING on another.
{ printf 'LANDING — lane repoT-1, session %s@Eagle, 2026-09-11T02:00:00Z, PR #31 into opensoft/repoT main\n' "$DEAD_ID"
  printf 'LANDED — lane repoT-1, session %s@Eagle, 2026-09-11T02:05:00Z, PR #31 → 1111111\n' "$DEAD_ID"
  printf 'LANDING — lane repoT-1, session %s@Eagle, 2026-09-11T02:10:00Z, PR #32 into opensoft/repoT main\n' "$DEAD_ID"
  printf 'LANDED — lane repoT-1, session %s@Eagle, 2026-09-11T02:15:00Z, PR #32 into opensoft/repoOTHER main → 2222222\n' "$DEAD_ID"
  printf 'LANDING — lane repoT-2, session %s@Eagle, 2026-09-11T03:00:00Z, PR #40 into opensoft/repoT-A main\n' "$DEAD_ID"
  printf 'LANDING — lane repoT-2, session %s@Eagle, 2026-09-11T03:05:00Z, PR #40 into opensoft/repoT-B main\n' "$DEAD_ID"
  printf 'LANDED — lane repoT-2, session %s@Eagle, 2026-09-11T03:10:00Z, PR #40 → 3333333\n' "$DEAD_ID"
} >> "$LANES"
git -C "$WIP" add -- lanes/LANES.md
git -C "$WIP" commit -q -m "Rule 6 lines in the shapes the live register really uses"
git -C "$WIP" push -q origin main

run "$E" who --landing opensoft/repoT
is    "who --landing over the register's own shapes exits 0" "$rc" 0
hasnt "a LANDED with NO 'into <repo> main' still closes its own LANDING" "$out" "LANDING  opensoft/repoT#31"
has   "…while a LANDED naming a DIFFERENT repository closes nothing" "$out" "LANDING  opensoft/repoT#32"
run "$E" who --landing opensoft/repoOTHER
is    "…and that unpaired LANDED opens no hold of its own" "$rc" 0
has   "…it is reported against the repository it names, never dropped" "$out" "unpaired LANDED  opensoft/repoOTHER#32"
has   "…saying where the LANDING it would have closed actually is" "$out" "is on opensoft/repoT"

run "$E" who --landing opensoft/repoT-B
has   "a repo-less LANDED pairs with the MOST RECENT unmatched LANDING, in file order" "$out" "none open"
run "$E" who --landing opensoft/repoT-A
has   "…leaving the earlier one on another repository still open" "$out" "LANDING  opensoft/repoT-A#40  lane repoT-2"

# ------------------ R18: a TAKEOVER supersedes only while it is its lane's last
#
# The whole sequence through the HELPERS, with no hand-written line. A TAKEOVER
# is never removed from an append-only log, so matching one anywhere in the
# taker's file kept superseding the dispossessed lane's claims for ever: after
# the taker released the object and that lane legitimately re-claimed it, `who`
# called a held object FREE and `claim` did not refuse the next lane — the one
# outcome Rule 1 exists to prevent.
for l in repoU-1 repoU-2 repoU-3; do
  "$E" add-row "| \`$l\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoU/$l.md | ACTIVE |" >/dev/null 2>&1
done
run env LANES_LANE=repoU-1 "$E" claim "opensoft/repoU#40" --no-github
is   "repoU-1 claims the object" "$rc" 0
# R35 — THE MARGIN IS AN HOUR, AND THERE IS NO `sleep`. `STALE_HOURS` is only
# ever used as `$((STALE_HOURS * 3600))`, so `-1` asks `now - claimed > -3600`:
# the takeover path is taken exactly as before, a real `TAKEOVER` line is still
# written, and a claim stamped up to an hour in the FUTURE is still stale.
# `sleep 1` + `LANES_STALE_HOURS=0` asked `now - claimed > 0` with both sides
# from `date -u`, and this workstation's realtime clock jumps ±25s in bursts
# (R14's note above) — one backwards burst between the claim and the check took
# this assertion and the ten that read the result of it out at once. The one cosmetic cost is the free text reading `no PR after -1h`, in a
# sandbox. The suite gets the second back.
run env LANES_LANE=repoU-2 LANES_STALE_HOURS=-1 "$E" claim "opensoft/repoU#40" --no-github --force
is   "repoU-2 takes the now-stale claim over" "$rc" 0
run "$E" who "opensoft/repoU#40"
has  "…so the taker holds it while its TAKEOVER is its own last line" "$out" "HOLDS    lane repoU-2"
has  "…and the dispossessed CLAIMED reads as superseded" "$out" "superseded by TAKEOVER (lane:repoU-2)"
run "$E" who --lane repoU-1
has   "who --lane reads all FIVE of lane-objects' fields" "$out" "CLAIMED   opensoft/repoU#40"
has   "…so the superseded cell is reported as what it is" "$out" "(taken over by lane:repoU-2 at"
hasnt "…never printed bare, where a payload goes" "$out" "ago) repoU-2@"

run env LANES_LANE=repoU-2 "$E" release "opensoft/repoU#40" "finished with it" --no-github
is   "the taker releases it" "$rc" 0
run env LANES_LANE=repoU-1 "$E" release "opensoft/repoU#40" "taken over by repoU-2" --no-github
is   "the dispossessed lane closes its own line" "$rc" 0
run env LANES_LANE=repoU-1 "$E" claim "opensoft/repoU#40" --no-github
is   "…and re-claims the object, which is now free" "$rc" 0
run "$E" who "opensoft/repoU#40"
has   "a TAKEOVER that is no longer its lane's last line supersedes nothing" "$out" "HOLDS    lane repoU-1"
hasnt "…so the clean re-claim is not reported as superseded" "$out" "super.   lane repoU-1"
has   "…and the object is HELD, not FREE" "$out" "state    HELD"
is    "…by exactly one lane" "$(printf '%s\n' "$out" | grep -c '^HOLDS')" 1
run env LANES_LANE=repoU-3 "$E" claim "opensoft/repoU#40" --no-github
is   "…so a third lane is REFUSED, which is the whole of Rule 1" "$rc" 2
has  "…naming the lane that holds it" "$err" "lane repoU-1 holds opensoft/repoU#40"

# ------------------------- R19: the ROW is read from origin/main, like the logs
#
# `who`'s register-derived half — the session cell, the handoff path, the
# workstation column — was the last thing reading the working tree, and
# print_holder_detail is built entirely out of it. A row that existed only on
# `origin/main` lost the resume uuid and the handoff path, which are the two
# things `who` exists to hand over; and a peer's UNCOMMITTED edit to column 3
# turned a Raven lane into `NOT LIVE`, which is the confident false report that
# sends a reader to `claim --force` against a live lane.
V_ID="aaaa0005-1111-4000-8000-aaaa00051111"
git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
printf '| `repoV-1` | harness `%s` | Raven / test / brett | 2026-09-11T00:00Z | none | handoffs/repoV/session-handoff-2026-09-11-lane-repoV-1.md | ACTIVE |\n' "$V_ID" >> "$CLONE2/lanes/LANES.md"
printf '# lane repoV-1 — object log (lane-collision-protocol Amendment 7)\nCLAIMED — lane repoV-1, session %s@Raven, %s, opensoft/repoV#1\n' \
  "$V_ID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$CLONE2/lanes/log/repoV-1.md"
git -C "$CLONE2" add -- lanes/LANES.md lanes/log/repoV-1.md
git -C "$CLONE2" commit -q -m "LANES(repoV-1@Raven): the peer's row and its claim"
git -C "$CLONE2" push -q origin main

is   "the peer's ROW is on origin/main and NOT in this checkout's working tree" "$(grep -c '^| `repoV-1`' "$LANES" || :)" 0
run "$E" who "opensoft/repoV#1"
has  "who reads the row from origin/main, so the resume uuid is the one that landed" "$out" "address  @repoV-1 · claude --resume $V_ID"
has  "…and so is the handoff path" "$out" "handoff  handoffs/repoV/session-handoff-2026-09-11-lane-repoV-1.md"
has  "…and the workstation column, so a Raven lane reads UNKNOWN" "$out" "UNKNOWN (records are local to Raven"

git -C "$WIP" pull -q --rebase origin main 2>/dev/null
# A peer's UNCOMMITTED edit, made the way the register's own writer makes one
# (`cat tmp > file` follows the symlink; `sed -i` would replace it — AGENTS.md
# rule 2).
awk '{ if ($0 ~ /^\| `repoV-1`/) { sub(/\| Raven \//, "| Eagle /") } print }' "$LANES" > "$SANDBOX/lanes.tmp"
cat -- "$SANDBOX/lanes.tmp" > "$LANES"
is   "a peer leaves that row edited and uncommitted" "$(git -C "$WIP" status --porcelain -- lanes/LANES.md | grep -c .)" 1
run "$E" who "opensoft/repoV#1"
has   "…and who's answer does not change: nothing in it reads the working tree" "$out" "UNKNOWN (records are local to Raven"
hasnt "…never turning a lane on the other workstation into NOT LIVE" "$out" "NOT LIVE (parked"
git -C "$WIP" checkout -q -- lanes/LANES.md

# ---------------------------------------------- R20: a lane's HOME is canonical
#
# `lanes/repos.tsv` maps `opensoft/codexFactory` to `codeXfactory/codexFactory`
# — the move the table exists for. A checkout whose origin still spells the old
# org recorded that spelling in STARTED, and every `#n` that lane wrote then
# keyed against a repository nothing could reconcile: two lanes held one GitHub
# issue under two keys and no collision was detected.
mkdir -p "$HOME/projects/legacyorg"
git init -q -b main "$HOME/projects/legacyorg"
git -C "$HOME/projects/legacyorg" remote add origin git@github.com:opensoft/codexFactory.git
run "$START" --dir "$HOME/projects/legacyorg" --estate cx repoW-1 --no-launch
is   "lane-start on a checkout spelling the pre-move org exits 0" "$rc" 0
has  "…resolving the home through repos.tsv BEFORE the STARTED line is written" "$err" "resolves through lanes/repos.tsv to codeXfactory/codexFactory"
has  "…so the STARTED line records the canonical spelling" "$(cat "$LOGD/repoW-1.md")" "lane:repoW-1 → home codeXfactory/codexFactory"
run env LANES_LANE=repoW-1 "$E" claim "#5" --no-github
is   "…and '#5' expands against it" "$rc" 0
has  "…to the canonical key" "$(cat "$LOGD/repoW-1.md")" ", codeXfactory/codexFactory#5"
run env LANES_LANE=repoW-2 "$E" claim "codeXfactory/codexFactory#5" --no-github
is   "…so the other spelling of the SAME issue is refused, not given a second key" "$rc" 2
has  "…naming the lane that holds it" "$err" "lane repoW-1 holds codeXfactory/codexFactory#5"

# …and a STARTED line written BEFORE this fix is resolved when it is READ.
{ printf '# lane repoW-3 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoW-3, session %s@Eagle, %s, lane:repoW-3 → home opensoft/codexFactory; estate cx\n' "$DEAD_ID" "$OLD_UTC"
} > "$LOGD/repoW-3.md"
git -C "$WIP" add -- lanes/log/repoW-3.md
git -C "$WIP" commit -q -m "a STARTED line carrying the pre-move spelling"
git -C "$WIP" push -q origin main
run env LANES_LANE=repoW-3 "$E" claim "#6" --no-github
is   "a legacy home already on record is resolved when it is read" "$rc" 0
has  "…so its shorthand keys canonically too" "$(cat "$LOGD/repoW-3.md")" ", codeXfactory/codexFactory#6"

# ------------------------- R21: lane-end's recovery text and its --force line
"$E" add-row "| \`repoX-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoX/x.md | ACTIVE |" >/dev/null 2>&1
run env LANES_LANE=repoX-1 "$E" claim "opensoft/repoX#11" --no-github
run env LANES_LANE=repoX-1 "$E" log LANDING "opensoft/repoX#12" --no-github
run "$END" repoX-1
is    "lane-end refuses while its log still shows open objects" "$rc" 2
has   "…printing the LANDED recovery in the helper's real CLI grammar" "$err" "lanes-edit.sh log LANDED <object> → <merge sha>"
has   "…release as the subcommand it is" "$err" "lanes-edit.sh release <object> \"<why>\""
has   "…and CLOSED for a PR that never merged" "$err" "lanes-edit.sh log CLOSED <object>"
hasnt "…never MERGED, which is not a verb at all" "$err" "MERGED"
hasnt "…and never 'log RELEASED', which log refuses outright" "$err" "log RELEASED"

before_lanes="$(grep -c . "$LANES")"
run env LANES_LANE=repoX-1 "$E" log LANDED "opensoft/repoX#12" "→" "abc9999"
is   "…and the LANDED form it prints is the one that actually works" "$rc" 0
has  "…carrying the merge sha as PAYLOAD in the lane's log" "$(cat "$LOGD/repoX-1.md")" ", opensoft/repoX#12 → abc9999"
has  "…and in the register's Rule 6 line, which the quoted form silently dropped" "$(tail -n1 "$LANES")" "PR #12 into opensoft/repoX main → abc9999"

run "$END" repoX-1 --force
is   "--force ends it" "$rc" 0
LX_LINE="$(grep '^ENDED' "$LOGD/repoX-1.md")"
has   "…writing an ENDED whose free text is 'forced; open: <object list>'" "$LX_LINE" ", lane:repoX-1 — forced; open: "
has   "…naming the object that was open" "$LX_LINE" "opensoft/repoX#11"
is    "…with ' — ' occurring exactly twice, which is the clause (b) guarantee" "$(printf '%s' "$LX_LINE" | grep -o ' — ' | grep -c .)" 2
hasnt "…and never an empty verb where a verb belongs" "$LX_LINE" "while  was"
has   "…while the register's line names the log it read, not the state cell" "$(grep '^| `repoX-1`' "$LANES")" "own object log still showed open:"

# The writer ENFORCES the grammar rather than hoping for it.
run env LANES_LANE=repoX-1 "$E" release "opensoft/repoX#11" "one — two" --no-github
is    "the writer REFUSES free text carrying ' — '" "$rc" 2
has   "…saying why" "$err" "may not contain ' — '"
hasnt "…and writes nothing" "$(cat "$LOGD/repoX-1.md")" "one — two"
run env LANES_LANE=repoX-1 "$E" release "opensoft/repoX#11" "$(printf 'one\ntwo')" --no-github
is    "…and free text carrying a newline, before it is appended rather than after" "$rc" 2
hasnt "…so no half-written line is left in an append-only log" "$(cat "$LOGD/repoX-1.md")" "two"

# ------------------------------- R22: live-holder fails closed AT THE SOURCE
#
# 8 means "the records were read and nothing live holds this lane"; lane-start
# renames a window on 8. Mapping a failed READ to 8 as well is exactly how a
# running lane loses its address: the rename mints `<lane> (2)` (AGENTS.md
# rule 7). Hardening the caller left the source with no way to say "I could not".
# The tree itself, not a path THROUGH it: with the tree at 000 a `$dir/..`
# spelling cannot be resolved, and even the chmod that restores it fails.
profiles_root="$HOME/.claude-profiles/profiles"
chmod 000 "$profiles_root"
run "$E" live-holder repoF-1
is   "an unreadable records tree exits 1, never the 8 that means 'nothing holds it'" "$rc" 1
has  "…and says what it could not read" "$err" "could not read this workstation's session records"
has  "…in the words that stop a reader believing the lane is free" "$err" "That is NOT 'no live session holds it'"
before_renames="$(grep -c 'rename-window repoF-1' "$FAKE_TMUX_LOG" || :)"
run "$START" repoF 1 --no-launch
is   "…so lane-start REFUSES rather than taking a name that may be held" "$rc" 1
is   "…and renames no window" "$(grep -c 'rename-window repoF-1' "$FAKE_TMUX_LOG" || :)" "$before_renames"
chmod 755 "$profiles_root"
run "$E" live-holder repoF-1
is   "…while a readable tree still finds the live holder" "$rc" 0
has  "…and it is the right session" "$out" "$F_ID"

# --------------------------------------------- R23: the small alignments
"$E" add-row "| \`repoY-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoY/x.md | ACTIVE |" >/dev/null 2>&1
run env LANES_LANE=repoY-1 "$E" claim "#1" --home opensoft/repoY --no-github
is   "--home is accepted by claim" "$rc" 0
run env LANES_LANE=repoY-1 "$E" log OPENED "#2" --home opensoft/repoY
is   "…by log" "$rc" 0
run env LANES_LANE=repoY-1 "$E" release "#1" "done" --home opensoft/repoY --no-github
is   "…by release, which both documents now say too" "$rc" 0
run "$E" who "#1" --home opensoft/repoY
is   "…by who" "$rc" 0
run "$END" repoY-1 --home opensoft/repoY --force
is   "…and by lane-end: five subcommands, and the docs list five" "$rc" 0

run env LANES_LANE=repoY-1 "$E" claim "opensoft/repoY#9" --nope
is    "an unknown option is refused" "$rc" 2
has   "…naming it" "$err" "unknown option '--nope' for claim"
hasnt "…and the refusal no longer ends with its own exit code" "$err" "for claim 2"
run env LANES_DEBUG=1 LANES_LANE=repoY-1 "$E" claim "opensoft/repoY#9" --nope
has   "…which LANES_DEBUG still prints, for whoever is debugging the codes" "$err" "(exit 2)"

run "$E" who "opensoft/repoG#11"
has   "a claim past the threshold says WHICH of Rule 1's discharges left it not stale" "$out" "has since written an OPENED naming it"
hasnt "…rather than two true halves that read as a contradiction" "$out" "old, threshold ${STALE_H}h"

echo "== Addendum 6: R24–R26, and the lifecycle reads =="

# ------- R24: a LANDED that NAMES a repository prefers a LANDING on that one
#
# Two LANDINGs open on ONE PR number in two repositories, and the lane lands the
# EARLIER one, naming its repository. R17's literal rule paired by (lane, PR)
# alone, took the most recent unmatched LANDING — the one on the OTHER
# repository — and reported the LANDED as `unpaired`: both holds stayed open
# until the second landed. It over-reported a merge hold, which is the direction
# that stalls other lanes' merges.
{ printf 'LANDING — lane repoZ-1, session %s@Eagle, 2026-09-11T04:00:00Z, PR #50 into opensoft/repoZ-A main\n' "$DEAD_ID"
  printf 'LANDING — lane repoZ-1, session %s@Eagle, 2026-09-11T04:05:00Z, PR #50 into opensoft/repoZ-B main\n' "$DEAD_ID"
  printf 'LANDED — lane repoZ-1, session %s@Eagle, 2026-09-11T04:10:00Z, PR #50 into opensoft/repoZ-A main → 4444444\n' "$DEAD_ID"
} >> "$LANES"
git -C "$WIP" add -- lanes/LANES.md
git -C "$WIP" commit -q -m "two LANDINGs on one PR number, and the EARLIER one lands"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

run   "$E" who --landing opensoft/repoZ-A
is    "a LANDED naming a repository closes the LANDING on THAT repository" "$rc" 0
has   "…so the hold it answers is closed" "$out" "none open"
hasnt "…and it is not reported as unpaired any more" "$out" "unpaired LANDED"
run   "$E" who --landing opensoft/repoZ-B
has   "…while the other repository's LANDING on the same PR number stays open" "$out" "LANDING  opensoft/repoZ-B#50  lane repoZ-1"

# The rest of R17 is unchanged, and the two cases that prove it are the ones
# above in the R17 block: a repo-less LANDED still takes the most recent
# unmatched LANDING, and a LANDED naming a repository with NO LANDING of its own
# is still reported as unpaired rather than dropped.

# ------------------- R26: free text may not begin with an arrow (finding 5)
#
# `→` and `←` introduce the PAYLOAD, and the payload is its own argument.
# Quoted into the free-text slot it lands after the ` — `, where the parser
# reads it as prose: the LANDED carries no payload and the register's Rule 6
# line loses the merge sha, in two files nothing ever rewrites.
"$E" add-row "| \`repoZA-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZA/x.md | ACTIVE |" >/dev/null 2>&1
run env LANES_LANE=repoZA-1 "$E" log LANDING "opensoft/repoZA#13" --no-github
is    "a LANDING is written" "$rc" 0
run env LANES_LANE=repoZA-1 "$E" log LANDED "opensoft/repoZA#13" "→ dead999" --no-github
is    "free text that BEGINS with '→' is refused" "$rc" 2
has   "…printing the positional form" "$err" "log LANDED <object> → <sha>"
has   "…and the form this very call should have taken" "$err" "log LANDED opensoft/repoZA#13 → <payload>"
hasnt "…writing nothing to the lane's log" "$(cat "$LOGD/repoZA-1.md")" "dead999"
hasnt "…and nothing to the register" "$(cat "$LANES")" "dead999"
run env LANES_LANE=repoZA-1 "$E" log OPENED "opensoft/repoZA#14" "← opensoft/repoZA#2" --no-github
is    "…and so is free text that begins with '←'" "$rc" 2
hasnt "…with nothing written for that one either" "$(cat "$LOGD/repoZA-1.md")" "opensoft/repoZA#14"
run env LANES_LANE=repoZA-1 "$E" log LANDED "opensoft/repoZA#13" "→" "dead999" --no-github
is    "…while the positional form it prints is the one that works" "$rc" 0
has   "…carrying the merge sha as a payload" "$(cat "$LOGD/repoZA-1.md")" ", opensoft/repoZA#13 → dead999"

# -------- the lifecycle reads: a row is read from origin/main, like the logs
#
# Copilot's two leads on `2590b53`, and the three suppressed ones on lane-start.
# All of them are the same fault in five places: a boundary act deciding
# something from `$LANES_FILE`, which is the WORKING TREE — and a `git fetch`
# does not move a working tree.

# live-holder: the id set is the published row's, and a read fetches first.
ZL_ID="aaaa0006-2222-4000-8000-aaaa00062222"
write_record_ns "$sessions_dir/live-zl.json" "$ZL_ID" "$LIVE_PID" "$live_start" "othersess:@9.%9" "repozl-99" "derived" "busy"
git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
( cd "$CLONE2" && LANES_LANE=repoZL-1 ./lanes/lanes-edit.sh add-row \
    "| \`repoZL-1\` | harness \`$ZL_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZL/x.md | ACTIVE |" ) >/dev/null 2>&1
is    "the peer's row is on origin/main and not in this checkout" "$(grep -c '^| `repoZL-1`' "$LANES" || :)" 0
run env LANES_NO_FETCH=1 "$E" live-holder repoZL-1
is    "without the fetch, a session id only origin/main carries is invisible" "$rc" 8
run   "$E" live-holder repoZL-1
is    "…and live-holder fetches first, like every other read, so it is found" "$rc" 0
has   "…and it is the right session" "$out" "$ZL_ID"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :

# lane-start: the liveness check is asked UNCONDITIONALLY, not only when this
# checkout's row already names an id.
ZS_ID="aaaa0007-3333-4000-8000-aaaa00073333"
write_record_ns "$sessions_dir/live-zs.json" "$ZS_ID" "$LIVE_PID" "$live_start" "othersess:@9.%9" "repozs-99" "derived" "busy"
"$E" add-row "| \`repoZS-1\` | pending — set by the session's first act | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZS/x.md | ACTIVE |" >/dev/null 2>&1
git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
( cd "$CLONE2" && LANES_LANE=repoZS-1 ./lanes/lanes-edit.sh replace-in-row repoZS-1 \
    "pending — set by the session's first act" "harness \`$ZS_ID\`" "the session stamps its own row" ) >/dev/null 2>&1
is    "this checkout's row still records no session id" "$(grep '^| `repoZS-1`' "$LANES" | grep -c 'pending' || :)" 1
zs_before="$(grep -c 'rename-window repoZS-1' "$FAKE_TMUX_LOG" || :)"
run   "$START" --dir "$HOME/projects/repoA" repoZS-1 --no-launch
is    "lane-start refuses a lane whose LIVE session id only the published row carries" "$rc" 2
has   "…naming the session that holds it" "$err" "is live in session $ZS_ID"
is    "…and renames no window, which is what mints '<lane> (2)'" "$(grep -c 'rename-window repoZS-1' "$FAKE_TMUX_LOG" || :)" "$zs_before"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :

# lane-start: "this lane is new" is decided against what has LANDED, so a
# second row is refused rather than written.
git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
( cd "$CLONE2" && LANES_LANE=repoZD-1 ./lanes/lanes-edit.sh add-row \
    "| \`repoZD-1\` | harness \`$DEAD_ID\` | Raven / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZD/x.md | ACTIVE |" ) >/dev/null 2>&1
is    "the peer's row for repoZD-1 is on origin/main and not here" "$(grep -c '^| `repoZD-1`' "$LANES" || :)" 0
zd_before="$(grep -c 'rename-window repoZD-1' "$FAKE_TMUX_LOG" || :)"
run   "$START" --dir "$HOME/projects/repoA" repoZD-1 --no-launch
is    "lane-start refuses to add a row origin/main already has" "$rc" 2
has   "…saying which register it read" "$err" "ALREADY has a row for repoZD-1"
is    "…and adds no second row, which no helper could then edit" "$(grep -c '^| `repoZD-1`' "$LANES" || :)" 0
is    "…and renames no window" "$(grep -c 'rename-window repoZD-1' "$FAKE_TMUX_LOG" || :)" "$zd_before"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :

# lane-start: a new session is never attributed to the session that ended.
"$E" add-row "| \`repoZN-1\` | harness \`$GHOST2_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZN/x.md | ACTIVE |" >/dev/null 2>&1
run env LANE_START_SESSION_ID=0 "$START" --dir "$HOME/projects/repoA" repoZN-1 --no-launch
is    "with nothing minted, a new session still starts" "$(launch_of "$out")" "claude --name repoZN-1"
has   "…and its STARTED names no session at all" "$(cat "$LOGD/repoZN-1.md")" "STARTED — lane repoZN-1, session unknown@"
hasnt "…never the uuid of the session that has ended" "$(cat "$LOGD/repoZN-1.md")" "$GHOST2_ID"

# lane-start: the title fallback cannot know which transcript the picker will
# choose, so its RESUMED says so instead of naming the row's last id.
printf '{"type":"custom-title","customTitle":"repoZT-1","sessionId":"titled-zt"}\n' > "$tdir/titled-zt.jsonl"
"$E" add-row "| \`repoZT-1\` | harness \`$GHOST_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZT/x.md | ACTIVE |" >/dev/null 2>&1
run   "$START" --dir "$HOME/projects/repoA" repoZT-1 --no-launch
is    "the title fallback resumes by title" "$out" "claude --resume repoZT-1"
has   "…and its RESUMED names no session, because the picker has not chosen one" "$(cat "$LOGD/repoZT-1.md")" "RESUMED — lane repoZT-1, session unknown@"
hasnt "…never the row's last id, whose transcript this directory does not have" "$(cat "$LOGD/repoZT-1.md")" "$GHOST_ID"

# lane-end: --home is checked BEFORE the row is closed.
"$E" add-row "| \`repoZH-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZH/x.md | ACTIVE |" >/dev/null 2>&1
run env LANES_LANE=repoZH-1 "$E" log STARTED "lane:repoZH-1" "→" "home opensoft/repoZH; estate repoZH"
is    "the lane's log records its home" "$rc" 0
zh_row="$(grep '^| `repoZH-1`' "$LANES")"
run   "$END" repoZH-1 --home opensoft/somewhere-else
is    "lane-end refuses --home for a lane whose log already records a home" "$rc" 2
has   "…with the writer's own reason, not a second copy of the rule" "$err" "--home is for a pre-cutover lane"
has   "…saying the row is untouched" "$err" "Nothing has been written"
is    "…and the row really is untouched, not closed and then complained about" "$(grep '^| `repoZH-1`' "$LANES")" "$zh_row"
hasnt "…so no ENDED line is missing from a closed lane" "$(cat "$LOGD/repoZH-1.md")" "ENDED"

# lane-end: the pre-cutover fallback reads the PUBLISHED row too. This is the
# one path that still decides a merge hold from prose, and it was reading a
# working tree that a fetch does not move.
"$E" add-row "| \`repoZZ-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZZ/x.md | IDLE, NOTHING CLAIMED |" >/dev/null 2>&1
git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
( cd "$CLONE2" && LANES_LANE=repoZZ-1 ./lanes/lanes-edit.sh append-row-status repoZZ-1 \
    "2026-09-11T05:00Z LANDING #8 into repoZZ main" ) >/dev/null 2>&1
is    "the peer's LANDING is on origin/main and not in this checkout's row" "$(grep '^| `repoZZ-1`' "$LANES" | grep -c 'LANDING #8' || :)" 0
run   "$END" repoZZ-1
is    "lane-end refuses a merge hold that only the PUBLISHED row shows" "$rc" 2
has   "…naming the row it read it from" "$err" "the published row on origin/main"
has   "…and it is Rule 6's word that stopped it" "$err" "the last LANDING in its state cell"

echo "== Addendum 7: R29–R30 =="

# ---------------- R29: the Rule 6 pairing resolves spellings through repos.tsv
#
# The register spells one repository several ways in the same week —
# `OpsxFactory` and `opensoft/OpsxFactory` (23 Rule 6 lines against 70 at
# `8f9c04d`), `codexFactory`, `codeXfactory/codexFactory` and
# `opensoft/codexFactory`. Compared literally, a LANDED spelled one way does
# not close the LANDING spelled the other: it reads as an `unpaired LANDED`,
# the hold stays open, and over-reporting a merge hold is the direction that
# stalls other lanes' merges. Both sides now go through `lanes/repos.tsv`
# before they are compared, and the result key's repository is the canonical
# spelling. The live register's verdict does not move at `6fa966b` — the same
# 1 open / 0 unpaired before and after, no (lane, PR) pair there mixing its
# spellings yet — so these fixtures are where the mechanism is held to
# account.
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
{ printf 'LANDING — lane repoZQ-1, session %s@Eagle, 2026-09-12T01:00:00Z, PR #60 into OpsxFactory main\n' "$DEAD_ID"
  printf 'LANDED — lane repoZQ-1, session %s@Eagle, 2026-09-12T01:20:00Z, PR #60 into opensoft/OpsxFactory main → 5555555\n' "$DEAD_ID"
  # R24's two-repo edge, with the two LANDINGs spelled two ways: the LANDED
  # names one repository and must still prefer ITS LANDING — the EARLIER one —
  # over the more recent one on the other repository.
  printf 'LANDING — lane repoZQ-2, session %s@Eagle, 2026-09-12T02:00:00Z, PR #61 into codexFactory main\n' "$DEAD_ID"
  printf 'LANDING — lane repoZQ-2, session %s@Eagle, 2026-09-12T02:05:00Z, PR #61 into opensoft/openRepoTools main\n' "$DEAD_ID"
  printf 'LANDED — lane repoZQ-2, session %s@Eagle, 2026-09-12T02:10:00Z, PR #61 into codeXfactory/codexFactory main → 6666666\n' "$DEAD_ID"
  # An alias the table does not know keeps its own spelling, and is compared
  # case-blind like every other.
  printf 'LANDING — lane repoZQ-3, session %s@Eagle, 2026-09-12T03:00:00Z, PR #62 into opensoft/repoUnknown main\n' "$DEAD_ID"
  printf 'LANDED — lane repoZQ-3, session %s@Eagle, 2026-09-12T03:10:00Z, PR #62 into opensoft/REPOUNKNOWN main → 7777777\n' "$DEAD_ID"
  # And the (lane, repository, PR) key carries the CANONICAL spelling: this
  # LANDED closes nothing, and the unpaired report names the LANDING's
  # repository as repos.tsv spells it, not as the register typed it.
  printf 'LANDING — lane repoZQ-4, session %s@Eagle, 2026-09-12T04:00:00Z, PR #63 into Omnigent-Install main\n' "$DEAD_ID"
  printf 'LANDED — lane repoZQ-4, session %s@Eagle, 2026-09-12T04:10:00Z, PR #63 into opensoft/openRepoShape main → 8888888\n' "$DEAD_ID"
  # A RETRY re-posts LANDING for the same PR — the register holds far more
  # LANDING lines than landings — and a retry can spell the repository the
  # other way. Keyed literally those are TWO triples, and the LANDED closes
  # only the one it names: a hold left open on a PR that has merged.
  printf 'LANDING — lane repoZQ-5, session %s@Eagle, 2026-09-12T05:00:00Z, PR #64 into OpsxFactory main\n' "$DEAD_ID"
  printf 'LANDING — lane repoZQ-5, session %s@Eagle, 2026-09-12T05:05:00Z, PR #64 into opensoft/OpsxFactory main\n' "$DEAD_ID"
  printf 'LANDED — lane repoZQ-5, session %s@Eagle, 2026-09-12T05:10:00Z, PR #64 into opensoft/OpsxFactory main → 9999999\n' "$DEAD_ID"
} >> "$LANES"
git -C "$WIP" add -- lanes/LANES.md
git -C "$WIP" commit -q -m "Rule 6 lines in the spellings the live register mixes"
git -C "$WIP" push -q origin main
# `none open` is also what an ABSENT line answers, so the fixture proves it
# landed before anything reads it — twelve lines, PR #60 to #64.
is    "the mixed-spelling Rule 6 fixture is on origin/main" \
      "$(git -C "$WIP" show origin/main:lanes/LANES.md | grep -c 'PR #6[0-4] into' || :)" 12

run   "$E" who --landing opensoft/OpsxFactory
is    "a LANDED into opensoft/OpsxFactory closes a LANDING into OpsxFactory" "$rc" 0
has   "…so the hold it answers is closed" "$out" "none open"
hasnt "…and it is not reported as unpaired, holding a merge that landed" "$out" "unpaired LANDED"
run   "$E" who --landing OpsxFactory
has   "…and the alias form of the question answers the same" "$out" "none open"

run   "$E" who --landing codeXfactory/codexFactory
has   "R24's preference is made between canonical spellings too" "$out" "none open"
hasnt "…so the LANDED that named the EARLIER LANDING's repository is not unpaired" "$out" "unpaired LANDED"
run   "$E" who --landing opensoft/openRepoTools
has   "…while the other repository's LANDING on the same PR number stays open" "$out" "LANDING  opensoft/openRepoTools#61  lane repoZQ-2"

run   "$E" who --landing opensoft/repoUnknown
has   "an alias the table does not know keeps its own spelling, case-blind" "$out" "none open"
run   "$E" who --landing opensoft/REPOUNKNOWN
has   "…however the question spells it" "$out" "none open"

run   "$E" who --landing opensoft/openRepoShape
has   "a LANDED on another repository still closes nothing" "$out" "unpaired LANDED  opensoft/openRepoShape#63"
has   "…and the LANDING it names is reported by its CANONICAL spelling" "$out" "is on opensoft/Omnigent-Install"
run   "$E" who --landing Omnigent-Install
has   "…which is where the hold really is, still open" "$out" "LANDING  opensoft/Omnigent-Install#63  lane repoZQ-4"

run   "$E" who --landing opensoft/OpsxFactory
has   "a retry that spelled the repository the other way is ONE triple" "$out" "none open"
hasnt "…so its LANDED closes it, and PR #64 leaves no hold behind" "$out" "#64"

# ------------------- R30: `--home` is resolved AFTER the fetch, in all of them
#
# The STARTED line that REFUSES `--home` is read from `origin/<branch>`, so a
# home a peer recorded is invisible here until `log_sync` has run. `claim` and
# `release` resolved it BEFORE their own fetch and `log` never fetched at all:
# the flag was accepted on a lane whose own log answers the question, and the
# key the write then built was a second spelling of an object that lane already
# has a home for — measured on the old code, `claim '#3' --home
# opensoft/elsewhere` committed `CLAIMED … opensoft/elsewhere#3` and only the
# rebase stopped it. `lane-end` has asked through `resolve-home`, which fetches,
# since Addendum 6; these three now agree with it.
ZR_ID="aaaa0008-4444-4000-8000-aaaa00084444"
peer_started() {   # <lane> <home> — the peer records a home on origin/main only
  git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
  { printf '# lane %s — object log (lane-collision-protocol Amendment 7)\n' "$1"
    printf 'STARTED — lane %s, session %s@Raven, %s, lane:%s → home %s; estate repoZR\n' \
      "$1" "$ZR_ID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2"
  } > "$CLONE2/lanes/log/$1.md"
  git -C "$CLONE2" add -- "lanes/log/$1.md"
  git -C "$CLONE2" commit -q -m "LOG($1@Raven): STARTED"
  git -C "$CLONE2" push -q origin main
}

peer_started repoZR-1 opensoft/repoZR
is    "the peer's STARTED line is on origin/main and not in this checkout" "$([ -f "$LOGD/repoZR-1.md" ] && echo yes || echo no)" "no"
run env LANES_NO_FETCH=1 "$E" resolve-home repoZR-1 opensoft/elsewhere
is    "without the fetch, a home only origin/main records is invisible" "$rc" 0
is    "…and --home is taken at its word" "$out" "opensoft/elsewhere"
run env LANES_LANE=repoZR-1 "$E" log OPENED "#4" --home opensoft/elsewhere
is    "log fetches before it resolves --home, so the refusal fires" "$rc" 2
has   "…naming the home the peer recorded" "$err" "already records its home: opensoft/repoZR"
is    "…and nothing is written, here or anywhere" "$([ -f "$LOGD/repoZR-1.md" ] && echo yes || echo no)" "no"

peer_started repoZR-2 opensoft/repoZR
run env LANES_LANE=repoZR-2 "$E" claim "#3" --home opensoft/elsewhere --no-github
is    "claim resolves --home after its fetch, not before it" "$rc" 2
has   "…with the same refusal" "$err" "already records its home: opensoft/repoZR"
hasnt "…and writes no claim under a home the lane does not have" "$(git -C "$WIP" show origin/main:lanes/log/repoZR-2.md 2>/dev/null || :)" "opensoft/elsewhere"

peer_started repoZR-3 opensoft/repoZR
run env LANES_LANE=repoZR-3 "$E" release "#3" "never mine" --home opensoft/elsewhere --no-github
is    "…and so does release" "$rc" 2
has   "…with the same refusal" "$err" "already records its home: opensoft/repoZR"

git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
run env LANES_LANE=repoZR-1 "$E" claim "#3" --no-github
is    "…while the claim itself uses the home the peer recorded" "$rc" 0
has   "…expanding '#3' against it" "$(cat "$LOGD/repoZR-1.md")" ", opensoft/repoZR#3"

echo "== Addendum 8: R33–R35 =="

# ---------- R33: the resume target and the RESUMED uuid are the PUBLISHED cell's
#
# The last working-tree read in either boundary act, and the one that puts a
# wrong fact into a file nothing rewrites. A peer stamps the lane's new session
# id from another clone and pushes; this checkout's copy of the row still ends
# on the OLD id. Read from there, `lane-start` resumes the lane's PREVIOUS
# conversation, appends a status naming that id, and writes a `RESUMED` line
# into `lanes/log/<lane>.md` carrying a session uuid that is not the lane's
# current one.
ZC1="aaaa0009-1111-4000-8000-aaaa00091111"
ZC2="aaaa0009-2222-4000-8000-aaaa00092222"
printf '{"type":"user"}\n' > "$tdir/$ZC1.jsonl"
printf '{"type":"user"}\n' > "$tdir/$ZC2.jsonl"
"$E" add-row "| \`repoZC-1\` | harness \`$ZC1\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZC/x.md | ACTIVE |" >/dev/null 2>&1
git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
( cd "$CLONE2" && LANES_LANE=repoZC-1 ./lanes/lanes-edit.sh replace-in-row repoZC-1 \
    "harness \`$ZC1\`" "harness \`$ZC1\` → harness \`$ZC2\`" "the session stamps its own row" ) >/dev/null 2>&1

# First, the reviewer's own sequence: this checkout is BEHIND and has not pulled.
# `--dry-run`, because a checkout that is behind cannot write its row at all —
# `commit_push` rebases the status on to the peer's line, conflicts, and aborts,
# which is a different refusal and already the right one.
is    "the peer's new session id is on origin/main and not in this checkout" \
      "$(grep '^| `repoZC-1`' "$LANES" | grep -c "$ZC2" || :)" 0
before_rev="$(git -C "$WIP" rev-parse HEAD)"
run   "$START" --dry-run --dir "$HOME/projects/repoA" repoZC-1
is    "lane-start on a stale copy of the row exits 0" "$rc" 0
has   "…reading the session cell from origin/main, which names BOTH ids" "$err" "its session cell on origin/main names 2 session id(s)"
has   "…so the row's current session is the one that LANDED" "$err" "the row's current session is $ZC2"
has   "…and that is what it plans to resume" "$err" "PLAN exec claude --resume $ZC2"
hasnt "…never the id this checkout's copy ends on" "$err" "$ZC1"
has   "…and the status it plans to append names the same id" "$err" "launching claude --resume $ZC2"
is    "…while --dry-run still writes nothing" "$(git -C "$WIP" rev-parse HEAD)" "$before_rev"

# And the durable half: the same divergence with HEAD already current, so the
# row write lands and the `RESUMED` line is really written. This checkout's COPY
# of the row is the older one — the shape R19's second reproduction uses, and
# the shape this register is in for much of the day (R11).
git -C "$WIP" pull -q --rebase origin main 2>/dev/null
awk -v drop=" → harness \`$ZC2\`" '{ if ($0 ~ /^\| `repoZC-1`/) { i = index($0, drop); if (i) $0 = substr($0, 1, i - 1) substr($0, i + length(drop)) } print }' \
  "$LANES" > "$SANDBOX/lanes.tmp"
cat -- "$SANDBOX/lanes.tmp" > "$LANES"
is    "this checkout's copy of the row is older than the one on origin/main" \
      "$(grep '^| `repoZC-1`' "$LANES" | grep -c "$ZC2" || :)" 0
is    "…while origin/main still names both ids" \
      "$(git -C "$WIP" show origin/main:lanes/LANES.md | grep '^| `repoZC-1`' | grep -c "$ZC2" || :)" 1
run   "$START" --no-launch --dir "$HOME/projects/repoA" repoZC-1
is    "lane-start exits 0" "$rc" 0
is    "…resuming the id the PUBLISHED cell ends on" "$out" "claude --resume $ZC2"
has   "…and the RESUMED line carries THAT uuid, in a file nothing rewrites" \
      "$(cat "$LOGD/repoZC-1.md")" "RESUMED — lane repoZC-1, session $ZC2@"
hasnt "…never the stale one, which no later line could correct" "$(cat "$LOGD/repoZC-1.md")" "$ZC1"

# A row HERE and none on origin/main is the one case with no published cell to
# read: it is an unpushed commit, and the answer is to say so, not to fall back
# to the working tree — falling back is the fault. The id this copy carries has
# a transcript, so nothing but the rule stops it being resumed.
ZF1="aaaa0009-3333-4000-8000-aaaa00093333"
printf '{"type":"user"}\n' > "$tdir/$ZF1.jsonl"
is    "the register is clean before the unpublished row is added" \
      "$(git -C "$WIP" status --porcelain -- lanes/LANES.md | grep -c .)" 0
printf '| `repoZF-1` | harness `%s` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZF/x.md | ACTIVE |\n' "$ZF1" >> "$LANES"
run   "$START" --dry-run --dir "$HOME/projects/repoA" repoZF-1
is    "a row this checkout has and origin/main does not still exits 0" "$rc" 0
has   "…and says there is no published cell to read" "$err" "the register on origin/main has none"
has   "…naming the id nothing outside this checkout can see" "$err" "which nothing else can see: $ZF1"
has   "…and the act that publishes it" "$err" "push the register from here"
has   "…taking a NEW session rather than resuming an unpublished id" "$err" "PLAN exec claude --name repoZF-1"
hasnt "…which is the whole of the rule: no decision comes off the working tree" "$err" "--resume $ZF1"
git -C "$WIP" checkout -q -- lanes/LANES.md
is    "…and the fixture leaves the register as it found it" \
      "$(git -C "$WIP" status --porcelain -- lanes/LANES.md | grep -c .)" 0

# ---------- R34: the handoff fragment honours lane_objects' fifth field
#
# The refusal reads it and says so; the fragment read it into a variable and
# never used it. The fragment is the surface that becomes a DURABLE document —
# it is pasted into the next session's handoff — so an object `who` gives to
# another lane was handed on as work this lane still had.
for l in repoZG-1 repoZG-2; do
  "$E" add-row "| \`$l\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZG/$l.md | ACTIVE |" >/dev/null 2>&1
done
run env LANES_LANE=repoZG-1 "$E" claim "opensoft/repoZG#40" --no-github
is   "repoZG-1 claims an object" "$rc" 0
run env LANES_LANE=repoZG-1 "$E" log LANDING "opensoft/repoZG#77" --no-github
is   "…and opens a landing nobody contests" "$rc" 0
run env LANES_LANE=repoZG-2 LANES_STALE_HOURS=-1 "$E" claim "opensoft/repoZG#40" --no-github --force
is   "repoZG-2 takes the claim over" "$rc" 0

run   "$END" repoZG-1
is    "lane-end still refuses while the taken-over line is open" "$rc" 2
has   "…naming the release that closes it" "$err" "taken over by lane:repoZG-2 at"
run   "$END" repoZG-1 --force
is    "--force ends it and prints the fragment" "$rc" 0
has   "…whose ## Open marks the superseded claim as what it is" "$out" "superseded by TAKEOVER (lane:repoZG-2) — release it"
is    "…once, on the line that carries the object" \
      "$(printf '%s\n' "$out" | grep -c 'superseded by TAKEOVER')" 1
has   "…on the CLAIMED bullet itself" "$out" "- CLAIMED — opensoft/repoZG#40 ("
has   "…while an object no other lane touched is listed plain" "$out" "- LANDING — opensoft/repoZG#77 ("
hasnt "…and that one carries no takeover of its own" "$(printf '%s\n' "$out" | grep 'repoZG#77')" "superseded"
is    "…the fragment still lists both under ## Open" \
      "$(printf '%s\n' "$out" | sed -n '/^## Open/,$p' | grep -c '^- ')" 2

# ------------------------------------------------------- nothing real touched
is   "the suite never created a log outside the sandbox" "$(ls "$SRC_DIR/log" 2>/dev/null | grep -v '^README.md$' | grep -c .)" 0
is   "the suite never wrote the real register" "$(git -C "$SRC_DIR" status --porcelain -- LANES.md 2>/dev/null | grep -c .)" 0

echo "----"
printf '%s passed, %s failed\n' "$pass" "$fail"
[ "$fail" = 0 ] || exit 1
exit 0
