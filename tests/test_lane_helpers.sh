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
# WHERE THE FILES ARE, after lane-collision-protocol Amendment 9's move. The
# four commands and the shipped alias table live at the ROOT of
# `opensoft/openRepoTools` and are INSTALLED into a bin directory; the person's
# workspace repository holds data and no code at all. This suite reproduces
# exactly that: it copies the five files into a sandbox bin directory, seeds a
# workspace repository with nothing but data in it, and writes the sandbox's own
# `$AGENT_PROTOCOL_ROOT/workspace.yaml` to join the two — which is the default
# resolution under test, since `:55` unsets every LANES_* seam so that the
# DEFAULT is what runs.
#
# Run it from anywhere: ./tests/test_lane_helpers.sh
# Exit 0 when every assertion passes, 1 otherwise.

set -uo pipefail          # NOT -e: a failing assertion must not end the run

SELF="$(readlink -f -- "${BASH_SOURCE[0]}")"
TESTS_DIR="$(cd -- "$(dirname -- "$SELF")" && pwd)"
# RE-ANCHORED AT THE REPOSITORY ROOT (Amendment 9, act 3 obligation 5). This
# file used to require `lane-start`, `lane-end`, `lanes-edit.sh` and
# `repos.tsv` BESIDE it, because in `opensoft/brett-wip` they were. They are at
# the root of `opensoft/openRepoTools` now and this suite is in `tests/`.
SRC_DIR="$(cd -- "$TESTS_DIR/.." && pwd)"

for f in lane-start lane-end lanes-edit.sh link-estates; do
  [ -x "$SRC_DIR/$f" ] || { echo "missing or not executable: $SRC_DIR/$f" >&2; exit 1; }
done
[ -f "$SRC_DIR/repos.tsv" ] || { echo "missing: $SRC_DIR/repos.tsv" >&2; exit 1; }

SANDBOX="$(mktemp -d)"
REAL_HOME="$HOME"

# THE GUARDS AT THE FOOT OF THIS FILE, re-pointed (Amendment 9, act 3
# obligation 5). They used to watch `$SRC_DIR/log` and `$SRC_DIR`'s register,
# which after the move are not in this repository at all — against
# openRepoTools' root they would pass vacuously and stop guarding the thing
# they were written for. What they were written for is the OPERATOR'S OWN
# register and logs, and those are now somewhere this suite can name: the
# workspace repository the real `~/.agents/workspace.yaml` points at. Read here,
# before `$HOME` is redirected, and compared again at the end.
real_ws_path() {
  local y p
  y="$REAL_HOME/.agents/workspace.yaml"
  [ -r "$y" ] || return 1
  p="$(sed -n 's/^path:[[:space:]]*//p' -- "$y" 2>/dev/null | head -n1)"
  p="${p%\"}"; p="${p#\"}"; p="${p%\'}"; p="${p#\'}"
  case "$p" in '~') p="$REAL_HOME" ;; '~/'*) p="$REAL_HOME/${p#'~/'}" ;; esac
  [ -n "$p" ] && [ -d "$p" ] || return 1
  printf '%s\n' "$p"
}
REAL_WS="$(real_ws_path 2>/dev/null || :)"
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
# `LANES_WORKSPACE_ROOT` joins the list Amendment 9(a) made it part of: with
# every seam unset, the DEFAULT resolution — `$AGENT_PROTOCOL_ROOT/workspace.yaml`
# — is what every case below exercises, which is the whole point of unsetting
# them. `AGENT_PROTOCOL_ROOT` is then re-exported into the sandbox, two lines
# down, so the default finds the sandbox's file and never the operator's.
unset LANES_FILE LANES_EDIT LANES_REPO LANES_PATH LANES_LANE LANES_WORKSPACE_ROOT \
      LANES_REPOS_TSV LANES_REPOS_TSV_SHIPPED PROJECTS_ROOT CLAUDE_PROJECTS_DIR CLAUDE_BIN 2>/dev/null
export AGENT_PROTOCOL_ROOT="$HOME/.agents"
mkdir -p "$AGENT_PROTOCOL_ROOT"

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
      '#{pane_pid}')                  printf '%s\n' "${FAKE_TMUX_PANE_PID:-}" ;;
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

# Amendment 8, ruling (g): the harness exports `CLAUDE_CODE_SESSION_ID` into
# every shell a session runs, INCLUDING the one running this suite. It is a
# holder test now, so a case that does not set it deliberately must not inherit
# the real session's id and answer differently inside a session than outside one.
unset CLAUDE_CODE_SESSION_ID
STALE_H=4                      # lanes-edit.sh's default, Rule 1's four hours

# ------------------------------------------------------------- the register

# THE BIN DIRECTORY — the post-move world, where `--install` places the four
# commands and the shipped alias table as regular files at 755. The workspace
# repository below gets NONE of them: Amendment 9(a), data only.
export OPENREPOTOOLS_BIN_DIR="$SANDBOX/bin"
mkdir -p "$OPENREPOTOOLS_BIN_DIR"
cp -p "$SRC_DIR/lane-start" "$SRC_DIR/lane-end" "$SRC_DIR/lanes-edit.sh" \
      "$SRC_DIR/link-estates" "$SRC_DIR/repos.tsv" "$OPENREPOTOOLS_BIN_DIR/"
chmod 755 "$OPENREPOTOOLS_BIN_DIR"/lane-start "$OPENREPOTOOLS_BIN_DIR"/lane-end \
          "$OPENREPOTOOLS_BIN_DIR"/lanes-edit.sh "$OPENREPOTOOLS_BIN_DIR"/link-estates \
          "$OPENREPOTOOLS_BIN_DIR"/repos.tsv
# AFTER the fake bin, which must still win for `tmux` and `claude`.
export PATH="$SANDBOX/fakebin:$OPENREPOTOOLS_BIN_DIR:$PATH"

ORIGIN="$SANDBOX/origin.git"
WIP="$HOME/projects/brett-wip"
git init -q --bare -b main "$ORIGIN"
git clone -q "$ORIGIN" "$WIP" 2>/dev/null
git -C "$WIP" config user.email "test@example.invalid"
git -C "$WIP" config user.name  "lane helper tests"
mkdir -p "$WIP/lanes" "$WIP/handoffs"
printf '# handoffs — one directory per estate\n' > "$WIP/handoffs/README.md"

# THE POINTER FILE, which is the whole of the new resolution (Amendment 9(a)).
# `repository:` is the sandbox's own bare origin rather than a GitHub slug, and
# the helpers' checkout test compares the two after the same normalisation, so
# a non-GitHub origin is checked exactly as a GitHub one is.
{
  printf 'repository: %s\n' "$ORIGIN"
  printf 'path: %s\n' "$WIP"
} > "$AGENT_PROTOCOL_ROOT/workspace.yaml"

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
git -C "$WIP" add -- lanes/LANES.md handoffs/README.md
git -C "$WIP" commit -q -m "seed the sandbox register"
git -C "$WIP" push -q origin main

START="$OPENREPOTOOLS_BIN_DIR/lane-start"
END="$OPENREPOTOOLS_BIN_DIR/lane-end"

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
has  "the appended status says what it did — and a --no-launch run never says it launched (F-B5)" "$(grep '^| `repoA-1`' "$LANES")" "window renamed, no launch"
hasnt "…so the stamp of a run that launched nothing claims no launch" "$(grep '^| `repoA-1`' "$LANES")" "no launch, launching"

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
has  "…and naming the exact command, which is the cell-scoped one (R-A8-4)" "$err" "append-session-id repoA-13"
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
has  "…and the session cell is stamped with the minted id, AFTER the old id's code span" "$(grep '^| `repoA-14`' "$LANES")" "harness \`$GHOST2_ID\` → harness \`$REPOA14_SID\`"
hasnt "…never inside it, which a replace at a bare-uuid anchor would do (F-B1)" "$(grep '^| `repoA-14`' "$LANES")" "\`$GHOST2_ID → "
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

E="$OPENREPOTOOLS_BIN_DIR/lanes-edit.sh"
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
printf '# a peer left this here mid-write\n' >> "$WIP/handoffs/README.md"
run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoE#30" --no-github
is   "claim refuses on a checkout that cannot be rebased" "$rc" 2
has  "…naming the offending file" "$err" "handoffs/README.md"
has  "…and why it matters" "$err" "the race cannot be run safely here"
git -C "$WIP" checkout -q -- handoffs/README.md
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
printf '# a peer left this here mid-write\n' >> "$WIP/handoffs/README.md"
printf 'and a register line at the same moment\n' >> "$LANES"
run env LANES_LANE=repoE-1 "$E" claim "opensoft/repoE#35" --no-github
is   "a dirty file that is NOT the register still refuses a claim" "$rc" 2
has  "…naming it" "$err" "handoffs/README.md"
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
git -C "$WIP" checkout -q -- handoffs/README.md

# A LANDING reaches the same place by the other road: the register is one of
# ITS OWN pathspecs, so the ordinary handle_preexisting call captures it and
# R11's capture stands aside. One behaviour, two routes, and the register is
# never left dirty for commit_push either way.
run env LANES_LANE=repoE-1 "$E" log LANDING "opensoft/repoE#41" --no-github
is   "a LANDING still writes with a dirty register: that file is one of ITS pathspecs" "$rc" 0
has  "…capturing the peer's line as its own commit first" "$err" "captured pre-existing edit"
run env LANES_LANE=repoE-1 "$E" log LANDED "opensoft/repoE#41" "→" "def5678"
is   "…and its LANDED closes it again" "$rc" 0
printf '# a peer left this here mid-write\n' >> "$WIP/handoffs/README.md"
run env LANES_LANE=repoE-1 "$E" log LANDING "opensoft/repoE#42" --no-github
is   "…while an UNRELATED dirty file refuses a LANDING too: the exemption is those two paths and no others" "$rc" 2
has  "…naming it" "$err" "handoffs/README.md"
git -C "$WIP" checkout -q -- handoffs/README.md

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
( LANES_WORKSPACE_ROOT="$CLONE2" LANES_LANE=repoZL-1 "$E" add-row \
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
( LANES_WORKSPACE_ROOT="$CLONE2" LANES_LANE=repoZS-1 "$E" replace-in-row repoZS-1 \
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
( LANES_WORKSPACE_ROOT="$CLONE2" LANES_LANE=repoZD-1 "$E" add-row \
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
# R-A8-2 — AND IT WRITES NO OBJECT-LOG LINE AT ALL. Amendment 7(b) makes the
# `session` field a transcript uuid and only that; `unknown` is not one, and the
# log is append-only, so the grammar's own writer does not write a line it
# cannot fill in. THE RULE IS THE CONDITION, NOT THE PATH: this is the
# new-session sub-case (nothing minted), and the title fallback below is the
# other. Both defer, and the same act writes both deferred records.
is    "…and no object-log line is written for it at all" "$([ -f "$LOGD/repoZN-1.md" ] && printf present || printf absent)" absent
has   "…the run saying which act will write it, its arguments filled in" "$err" "--no-launch repoZN 1"
has   "…and why it did not write one" "$err" "no transcript uuid is knowable at this instant"
has   "…the row's stamp still carrying the placeholder, where a reader can see it" "$(grep '^| `repoZN-1`' "$LANES")" "STARTED by unknown (lane repoZN-1)"
hasnt "…never the uuid of the session that has ended" "$(grep '^| `repoZN-1`' "$LANES")" "$GHOST2_ID (lane"

# lane-start: the title fallback cannot know which transcript the picker will
# choose, so its RESUMED says so instead of naming the row's last id.
printf '{"type":"custom-title","customTitle":"repoZT-1","sessionId":"titled-zt"}\n' > "$tdir/titled-zt.jsonl"
"$E" add-row "| \`repoZT-1\` | harness \`$GHOST_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoZT/x.md | ACTIVE |" >/dev/null 2>&1
run   "$START" --dir "$HOME/projects/repoA" repoZT-1 --no-launch
is    "the title fallback resumes by title" "$out" "claude --resume repoZT-1"
is    "…and writes NO object-log line, because \`unknown\` is not a transcript uuid (R-A8-2)" "$([ -f "$LOGD/repoZT-1.md" ] && printf present || printf absent)" absent
has   "…nor Rule 3's handoff stamp, which is the other deferred record" "$err" "Nor is the handoff's Rule 3 stamp"
has   "…naming the one act that writes both, at the first instant either can be right" "$err" "--no-launch repoZT 1"
has   "…while the ROW's stamp does carry the placeholder — the one place it is written on purpose" "$(grep '^| `repoZT-1`' "$LANES")" "RESUMED by unknown (lane repoZT-1)"
hasnt "…never the row's last id, whose transcript this directory does not have" "$(grep '^| `repoZT-1`' "$LANES")" "RESUMED by $GHOST_ID"

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
( LANES_WORKSPACE_ROOT="$CLONE2" LANES_LANE=repoZZ-1 "$E" append-row-status repoZZ-1 \
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
( LANES_WORKSPACE_ROOT="$CLONE2" LANES_LANE=repoZC-1 "$E" replace-in-row repoZC-1 \
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


echo "== Amendment 8: swap and restart =="

# ------------------------------------------------------------------ swapped
#
# The RECORD a swap leaves is the lane's own PAUSED line, payload
# `swap; window <s>:<i>; workstation <ws>`, and a lane is SWAPPED on a
# workstation when that PAUSED is its LAST lane-kind line. `swapped` is what a
# restart asks once the new tmux session has lost the window name.

run "$E" swapped "$WS_S"
is    "swapped with nothing swapped exits 8, the same 8 every other absence uses" "$rc" 8
has   "…saying what it looked for" "$err" "no lane on $WS_S is swapped"
is    "…and prints no row a launcher could mistake for one" "$out" ""

SW_ID="aaaa000a-5555-4000-8000-aaaa000a5555"
SW_OLD_UTC="2026-09-12T10:00:00Z"
SW_NEW_UTC="2026-09-12T11:00:00Z"
sw_seed() {   # <lane> <utc> <workstation> <window> [<extra line>...]
  sw_l="$1"; sw_u="$2"; sw_w="$3"; sw_win="$4"; shift 4
  { printf '# lane %s — object log (lane-collision-protocol Amendment 7)\n' "$sw_l"
    printf 'STARTED — lane %s, session %s@%s, 2026-09-12T09:00:00Z, lane:%s → home opensoft/%s; estate sw\n' "$sw_l" "$SW_ID" "$sw_w" "$sw_l" "$sw_l"
    printf 'PAUSED — lane %s, session %s@%s, %s, lane:%s → swap; window %s; workstation %s — on Brett Heap'"'"'s word\n' \
      "$sw_l" "$SW_ID" "$sw_w" "$sw_u" "$sw_l" "$sw_win" "$sw_w"
    for sw_x in "$@"; do printf '%s\n' "$sw_x"; done
  } > "$LOGD/$sw_l.md"
  git -C "$WIP" add -- "lanes/log/$sw_l.md"
  git -C "$WIP" commit -q -m "LOG($sw_l@$sw_w): PAUSED lane:$sw_l"
  git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
  git -C "$WIP" push -q origin main
  return 0
}

# LANDING ORDER, NOT THE CLOCK. repoSW-5 carries the LATER UTC and lands FIRST;
# repoSW-1 carries the EARLIER one and lands SECOND, so it is listed first. Two
# lanes' files share no clock — Amendment 7's file-order rule does not reach
# across files, and this workstation's own clock was observed stepping ±25s —
# so the order is the order the two PAUSED lines reached `main`.
sw_seed repoSW-5 "$SW_NEW_UTC" "$WS_S" "sess-five:5"
sw_seed repoSW-1 "$SW_OLD_UTC" "$WS_S" "claude-team-05b-20260912102132-2699:0"

run "$E" swapped "$WS_S"
is    "swapped exits 0 once a lane is swapped" "$rc" 0
is    "…one row per swapped lane" "$(printf '%s\n' "$out" | grep -c .)" 2
is    "…lane first, tab-separated, <lane><TAB><UTC><TAB><window>" \
      "$(printf '%s\n' "$out" | head -n1)" "$(printf 'repoSW-1\t%s\tclaude-team-05b-20260912102132-2699:0' "$SW_OLD_UTC")"
is    "…MOST RECENTLY LANDED first, though its UTC is the older of the two" \
      "$(printf '%s\n' "$out" | head -n1 | cut -f1)" "repoSW-1"
is    "…and the lane whose UTC is later, having landed first, comes second" \
      "$(printf '%s\n' "$out" | sed -n 2p | cut -f1)" "repoSW-5"
is    "…every row carries exactly three tab-separated fields" \
      "$(printf '%s\n' "$out" | awk -F'\t' 'NF != 3' | grep -c .)" 0
hasnt "…and nothing is written by a read" "$(git -C "$WIP" log --format=%s -n1)" "swapped"

# A lane that has since RESUMED is not swapped: its last lane-kind line is the
# RESUMED, and this lane's own real log carries exactly that shape.
sw_seed repoSW-2 "$SW_NEW_UTC" "$WS_S" "sess-two:2" \
  "RESUMED — lane repoSW-2, session $SW_ID@$WS_S, 2026-09-12T12:00:00Z, lane:repoSW-2 → home opensoft/repoSW-2; estate sw"
run   "$E" swapped "$WS_S"
hasnt "a lane whose PAUSED was followed by a RESUMED is not swapped" "$out" "repoSW-2"
is    "…and the swapped count is unchanged" "$(printf '%s\n' "$out" | grep -c .)" 2

# The workstation is part of the record, and the default is this one.
sw_seed repoSW-3 "$SW_NEW_UTC" Raven "raven-sess:3"
run   "$E" swapped "$WS_S"
hasnt "a lane swapped on ANOTHER workstation is not listed here" "$out" "repoSW-3"
run   "$E" swapped Raven
is    "…and is listed when that workstation is asked for" "$rc" 0
has   "…by name" "$out" "repoSW-3"
has   "…with the window its /swap recorded" "$out" "raven-sess:3"
run   "$E" swapped
is    "swapped with no argument answers for this workstation" "$rc" 0
hasnt "…which is not the other one" "$out" "repoSW-3"

# A PAUSED that is not a swap is not a record. The lane paused for some other
# reason, and nothing may restart into it.
{ printf '# lane repoSW-4 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'PAUSED — lane repoSW-4, session %s@%s, %s, lane:repoSW-4\n' "$SW_ID" "$WS_S" "$SW_NEW_UTC"
} > "$LOGD/repoSW-4.md"
git -C "$WIP" add -- lanes/log/repoSW-4.md
git -C "$WIP" commit -q -m "LOG(repoSW-4@$WS_S): PAUSED with no swap payload"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
run   "$E" swapped "$WS_S"
hasnt "a PAUSED whose payload is not 'swap; …' is not a swap record" "$out" "repoSW-4"

# The launcher calls it with LANES_NO_FETCH=1: a record this workstation wrote
# is in its own clone, and a restart must not wait on the network.
run env LANES_NO_FETCH=1 "$E" swapped "$WS_S"
is    "swapped honours LANES_NO_FETCH and still reads origin/main" "$rc" 0
has   "…answering the same" "$out" "repoSW-1"
has   "…saying it did not fetch" "$err" "LANES_NO_FETCH=1"
run env LANES_NO_FETCH=1 "$E" register-row repoA-1
is    "register-row honours it too — the launcher's other probe" "$rc" 0
run   "$E" swapped --nope
is    "swapped's OWN usage error is 64, never the dispatcher's 2 (F-B8, F-W4)" "$rc" 64
has   "…naming the option" "$err" "unknown option '--nope' for swapped"
run   "$E" swapped Eagle extra
is    "…a second workstation argument is the same 64" "$rc" 64
run   "$E" no-such-subcommand-at-all
is    "…while 2 is left to mean ONE thing: no such subcommand, which is the launcher's whole degrade gate" "$rc" 2
has   "…and the list it prints names swapped" "$err" "swapped"
run   "$E" register-row 'not a lane name'
is    "register-row exits 2 for a name that is not lane-shaped, never 8" "$rc" 2
run   "$E" register-row no-such-lane-9
is    "…and 8 for a lane-shaped name the published register has no row for" "$rc" 8

# --------------------------------------------------------- window-session
#
# `live-holder` asks whether any session a ROW names is alive; this asks what is
# alive in a WINDOW, and the gap between the two is the whole of the case below.
HW_OLD="aaaa000b-1111-4000-8000-aaaa000b1111"
HW_NEW="aaaa000b-2222-4000-8000-aaaa000b2222"
printf '{"type":"user"}\n' > "$tdir/$HW_OLD.jsonl"
printf '{"type":"user"}\n' > "$tdir/$HW_NEW.jsonl"
write_record_ns "$sessions_dir/live-harness.json" "$HW_NEW" "$LIVE_PID" "$live_start" "hwsess:@7.%7" "openrepoproject-7e" "derived" "busy"

run "$E" window-session "hwsess:@7"
is   "window-session finds the live record in a window" "$rc" 0
has  "…naming the session" "$out" "$HW_NEW"
has  "…the window it reported itself in" "$out" "hwsess:@7.%7"
has  "…the name the harness derived, which decides nothing and is reported" "$out" "openrepoproject-7e"
has  "…and the PROFILE, read off the record's own path" "$out" "t1"
run "$E" window-session "nosuch:@99"
is   "…and exits 8 for a window no live record names" "$rc" 8

# A session that outlives the window it started in keeps the `tmux` value it was
# born with, so a backgrounded predecessor whose pid is still alive matches the
# same target as the session at the keyboard. The most recently updated record
# wins, and the answer does not depend on which the filesystem listed first.
HW_STALE="aaaa000b-3333-4000-8000-aaaa000b3333"
printf '{"pid":%s,"sessionId":"%s","cwd":"x","procStart":"%s","tmux":"hwsess:@7.%%7","name":"old-one","nameSource":"derived","status":"idle","updatedAt":1000}\n' \
  "$LIVE_PID" "$HW_STALE" "$live_start" > "$sessions_dir/aaa-live-stale.json"
printf '{"pid":%s,"sessionId":"%s","cwd":"x","procStart":"%s","tmux":"hwsess:@7.%%7","name":"openrepoproject-7e","nameSource":"derived","status":"busy","updatedAt":2000}\n' \
  "$LIVE_PID" "$HW_NEW" "$live_start" > "$sessions_dir/zzz-live-current.json"
run  "$E" window-session "hwsess:@7"
is   "with two live records in one window, the most recently updated one wins" "$rc" 0
has  "…which is the session at the keyboard" "$out" "$HW_NEW"
hasnt "…never the backgrounded predecessor that still names the window" "$out" "$HW_STALE"
rm -f "$sessions_dir/aaa-live-stale.json" "$sessions_dir/zzz-live-current.json"
write_record_ns "$sessions_dir/live-harness.json" "$HW_NEW" "$LIVE_PID" "$live_start" "hwsess:@7.%7" "openrepoproject-7e" "derived" "busy"

# ------------------- lane-start: the harness's new transcript uuid (Amendment 8)
#
# THE CASE THIS AMENDMENT IS FOR, and the one this lane lived at 2026-09-12T16:5xZ:
# the usage reset carried the conversation into a NEW transcript uuid while the
# row's session cell still ended on the old one. That id is in no row, so
# `live-holder` cannot look it up and answers 8 — "this lane is parked" — about
# the conversation sitting in the very window it was asked about. Without the
# window read, lane-start resumes the lane's PREVIOUS conversation and writes
# that uuid on to an append-only line.
"$E" add-row "| \`repoHU-1\` | harness \`$HW_OLD\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoHU/x.md | ACTIVE |" >/dev/null 2>&1
export FAKE_TMUX_WINDOW="hwsess:@7"
run   "$START" --dir "$HOME/projects/repoA" repoHU-1 --no-launch
is    "lane-start exits 0" "$rc" 0
has   "…having read the live session out of THIS window" "$err" "this window's live session is $HW_NEW"
has   "…and said the published cell does not name it" "$err" "the PUBLISHED session cell does not name it"
has   "…the cell is EXTENDED with it, after the id it already ended on" \
      "$(grep '^| `repoHU-1`' "$LANES")" "harness \`$HW_OLD\` → harness $HW_NEW (transcript uuid; profile t1)"
has   "…in its own register commit that says why" "$(git -C "$WIP" log --format=%s -- lanes/LANES.md | head -n2 | tail -n1)" "the harness minted $HW_NEW for this window"
is    "…and the launch resumes the NEW id, not the one the cell used to end on" "$out" "claude --resume $HW_NEW"
has   "…while the row's status is Amendment 6(c)'s stamp, naming that uuid" \
      "$(grep '^| `repoHU-1`' "$LANES")" "RESUMED by $HW_NEW (lane repoHU-1) — lane-start on"
has   "…and the object log's RESUMED carries it too" "$(cat "$LOGD/repoHU-1.md")" "RESUMED — lane repoHU-1, session $HW_NEW@"
hasnt "…never the stale id, which no later line could correct" "$(grep '^RESUMED' "$LOGD/repoHU-1.md")" "$HW_OLD"

# Run it again: the cell now names that uuid, so there is nothing to append and
# nothing is written to the cell — only the stamp.
hu_before="$(git -C "$WIP" rev-parse HEAD)"
run   "$START" --dir "$HOME/projects/repoA" repoHU-1 --no-launch
is    "a second run exits 0" "$rc" 0
has   "…saying step 3 already found that session holding the lane here" "$err" "already holds repoHU-1"
has   "…so there is nothing for the window read to add" "$err" "the cell is current"
is    "…so the cell is not extended twice" "$(grep -o "harness $HW_NEW" "$LANES" | grep -c .)" 1
is    "…and the only register commit is the stamp" "$(git -C "$WIP" rev-list --count "$hu_before..HEAD" -- lanes/LANES.md)" 1
has   "…which still names the uuid it resumed" "$(git -C "$WIP" log --format=%s -n1 -- lanes/LANES.md)" "RESUMED by $HW_NEW"
unset FAKE_TMUX_WINDOW

# ---- R-A8-4: THE UUID APPEND IS CELL-SCOPED, AND THIS IS WHY -------------
#
# The row above has now been stamped TWICE, so it carries `$HW_NEW` three
# times: once in its session cell and once in each Amendment 6(c) stamp
# (`RESUMED by <uuid> …`; a stamp that really launches carries it twice, in
# `launching claude --resume <uuid>` as well). That is the real shape of
# `openRepoProject-1`'s own row on `origin/main`, measured 2026-09-12 — three
# occurrences of the current uuid and three of the previous one — and it is the
# shape on which the whole-row anchor refuses. The second harness event for any
# lane this tool has stamped is therefore the common case, not an edge.
hu_row="$(grep '^| `repoHU-1`' "$LANES")"
is    "two stamps later, the row carries that uuid three times — openRepoProject-1's own shape" \
      "$(printf '%s' "$hu_row" | grep -o "$HW_NEW" | grep -c .)" 3
run   env LANES_LANE=repoHU-1 "$E" replace-in-row repoHU-1 "$HW_NEW" "$HW_NEW → harness nope"
is    "replace-in-row REFUSES it, and its whole-row rule is unchanged" "$rc" 2
has   "…counting the occurrences it found" "$err" "occurs 3 times"
is    "…and writing nothing" "$(grep '^| `repoHU-1`' "$LANES")" "$hu_row"

# The harness mints a THIRD transcript in the same window — a second usage
# reset, which is what this lane lives through twice a day.
HW_NEW2="aaaa000b-4444-4000-8000-aaaa000b4444"
printf '{"type":"user"}\n' > "$tdir/$HW_NEW2.jsonl"
rm -f "$sessions_dir/live-harness.json"
write_record_ns "$sessions_dir/live-harness2.json" "$HW_NEW2" "$LIVE_PID" "$live_start" "hwsess:@7.%7" "openrepoproject-7e" "derived" "busy"
export FAKE_TMUX_WINDOW="hwsess:@7"
run   "$START" --dir "$HOME/projects/repoA" repoHU-1 --no-launch
is    "lane-start appends the new transcript anyway, because the act is cell-scoped" "$rc" 0
has   "…the session cell now ends on the third transcript" \
      "$(grep '^| `repoHU-1`' "$LANES")" "→ harness $HW_NEW2 (transcript uuid; profile t1)"
is    "…the previous uuid's three occurrences are untouched, stamp included" \
      "$(grep '^| `repoHU-1`' "$LANES" | grep -o "$HW_NEW" | grep -c .)" 3
is    "…the row is still one line" "$(grep -c '^| `repoHU-1`' "$LANES")" 1
is    "…and the launch resumes the id the cell now ends on" "$out" "claude --resume $HW_NEW2"
unset FAKE_TMUX_WINDOW
rm -f "$sessions_dir/live-harness2.json"

# ---- append-session-id, held to account directly --------------------------
AS_ID="aaaa000d-1111-4000-8000-aaaa000d1111"
AS_NEW="aaaa000d-2222-4000-8000-aaaa000d2222"
"$E" add-row "| \`repoAS-1\` | harness \`$AS_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoAS/x.md | ACTIVE · 2026-09-12T10:00:00Z RESUMED by $AS_ID (lane repoAS-1) — lane-start on Eagle: window renamed, launching claude --resume $AS_ID |" >/dev/null 2>&1
is    "the fixture carries its uuid three times across the row" \
      "$(grep '^| `repoAS-1`' "$LANES" | grep -o "$AS_ID" | grep -c .)" 3
as_before="$(git -C "$WIP" rev-parse HEAD)"
run   env LANES_LANE=repoAS-1 "$E" append-session-id repoAS-1 "$AS_ID" "→ harness $AS_NEW (transcript uuid; profile t1)" "session cell: the harness minted $AS_NEW"
is    "append-session-id appends where replace-in-row refuses" "$rc" 0
has   "…the cell carrying both, oldest first, which is what makes it a history" \
      "$(grep '^| `repoAS-1`' "$LANES")" "harness \`$AS_ID\` → harness $AS_NEW (transcript uuid; profile t1) |"
is    "…the state cell's two copies untouched, so the stamp still reads as written" \
      "$(grep '^| `repoAS-1`' "$LANES" | grep -o "$AS_ID" | grep -c .)" 3
is    "…in exactly one commit" "$(git -C "$WIP" rev-list --count "$as_before..HEAD" -- lanes/LANES.md)" 1
has   "…that says why" "$(git -C "$WIP" log --format=%s -n1 -- lanes/LANES.md)" "the harness minted $AS_NEW"
is    "…and it was pushed" "$(git -C "$WIP" rev-parse HEAD)" "$(git -C "$WIP" rev-parse origin/main)"
hasnt "…and the new id landed AFTER the old one's code span, never inside it" \
      "$(grep '^| `repoAS-1`' "$LANES")" "\`$AS_ID → harness"

as_row="$(grep '^| `repoAS-1`' "$LANES")"
run   env LANES_LANE=repoAS-1 "$E" append-session-id repoAS-1 "lane-start on Eagle" "lane-start on Eagle → x"
is    "an anchor that is only in the STATE cell is not in the session cell: refused" "$rc" 2
has   "…naming both counts, so the refusal explains itself" "$err" "occurs 0 time(s) in lane repoAS-1's SESSION CELL"
has   "…and why this act is not replace-in-row" "$err" "The row as a whole carries it 1 time(s)"
run   env LANES_LANE=repoAS-1 "$E" append-session-id repoAS-1 "harness" "harness → x"
is    "an anchor that occurs twice INSIDE the cell is refused too" "$rc" 2
has   "…counting them there" "$err" "occurs 2 time(s) in lane repoAS-1's SESSION CELL"
run   env LANES_LANE=repoAS-1 "$E" append-session-id repoAS-1 "$AS_NEW" "→ harness x | Raven / test"
is    "appended text carrying a '|' would forge a cell boundary: refused" "$rc" 2
has   "…saying exactly that" "$err" "may not contain '|'"
run   env LANES_LANE=repoAS-1 "$E" append-session-id repoAS-1 "$AS_NEW"
is    "…and three arguments are required" "$rc" 2
is    "…none of which wrote anything" "$(grep '^| `repoAS-1`' "$LANES")" "$as_row"

# The stamp follows the LAUNCH decision, exactly as the object-log verb does: a
# new session is STARTED and a resume is RESUMED, and the uuid is the one this
# run really resumes or mints.
"$E" add-row "| \`repoHU-2\` | harness \`$GHOST2_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoHU/y.md | ACTIVE |" >/dev/null 2>&1
run   "$START" --dir "$HOME/projects/repoA" repoHU-2 --no-launch
HU2_SID="$(minted_of "$out")"
is    "a lane that takes a NEW session still exits 0" "$rc" 0
has   "…and its stamp reads STARTED, not RESUMED" "$(grep '^| `repoHU-2`' "$LANES")" "STARTED by $HU2_SID (lane repoHU-2) — lane-start on"
run   "$START" repoA 1 --no-launch
has   "…while a resume-by-id lane's stamp reads RESUMED by that id" "$(grep '^| `repoA-1`' "$LANES")" "RESUMED by $DEAD_ID (lane repoA-1) — lane-start on"
has   "…and the --no-launch tail behind it states what really happened" "$(grep '^| `repoA-1`' "$LANES")" "RESUMED by $DEAD_ID (lane repoA-1) — lane-start on $(hostname): window renamed, no launch"

# ---- R-A8-2: ONE record written, TWO deferred, and the act that settles them
#
# The title fallback is a person choosing at a picker, and no writer knows which
# transcript they took at the instant the stamps would be written. So the row's
# stamp carries the literal `unknown` — the state cell is a history of ACTS and
# the act happened — and BOTH the object-log line (Amendment 7(b): that field is
# a transcript uuid and only that, in an append-only file) and Rule 3's handoff
# stamp are deferred to the first act that knows the uuid. This is the pair: the
# run that defers, and the `--no-launch` run that settles it.
DW_OLD="aaaa000e-1111-4000-8000-aaaa000e1111"
DW_NEW="aaaa000e-2222-4000-8000-aaaa000e2222"
mkdir -p "$WIP/handoffs/repoDW"
printf 'Lane: repoDW-1 — single-use resume prompt\n\n# state\n' > "$WIP/handoffs/repoDW/x.md"
git -C "$WIP" add -- handoffs/repoDW/x.md
git -C "$WIP" commit -q -m 'handoff fixture for repoDW-1'
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoDW-1\` | harness \`$DW_OLD\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoDW/x.md | ACTIVE |" >/dev/null 2>&1
printf '{"type":"custom-title","customTitle":"repoDW-1","sessionId":"titled-dw"}\n' > "$tdir/titled-dw.jsonl"

run   "$START" --dir "$HOME/projects/repoA" repoDW-1 --no-launch
is    "the title fallback resumes by title, the picker not yet run" "$out" "claude --resume repoDW-1"
is    "…and writes NO object-log line: \`unknown\` is not a transcript uuid (A7(b))" \
      "$([ -f "$LOGD/repoDW-1.md" ] && printf present || printf absent)" absent
hasnt "…nor Rule 3's stamp on the handoff the row names" "$(cat "$WIP/handoffs/repoDW/x.md")" "RESUMED by"
has   "…the ROW's stamp carrying the placeholder, the one place it is written on purpose" \
      "$(grep '^| `repoDW-1`' "$LANES")" "RESUMED by unknown (lane repoDW-1) — lane-start on"
is    "…and \`unknown\` never entering the SESSION cell, which Amendment 6(b) resumes from" \
      "$(grep '^| `repoDW-1`' "$LANES" | awk -F'|' '{print $3}' | grep -c unknown || :)" 0
has   "…while the run names the one act that writes both deferred records" "$err" "--no-launch repoDW 1"

# The operator's pick is now the live session in this window, so the act the
# hook prints can read it: no flag, no id, and it learns the uuid itself.
printf '{"type":"user"}\n' > "$tdir/$DW_NEW.jsonl"
write_record_ns "$sessions_dir/live-dw.json" "$DW_NEW" "$LIVE_PID" "$live_start" "dwsess:@8.%8" "repodw-1" "derived" "busy"
export FAKE_TMUX_WINDOW="dwsess:@8"
run   "$START" --dir "$HOME/projects/repoA" repoDW-1 --no-launch
is    "the deferred run exits 0" "$rc" 0
has   "…APPENDING the real uuid to the session cell — nothing is replaced there" \
      "$(grep '^| `repoDW-1`' "$LANES")" "harness \`$DW_OLD\` → harness $DW_NEW (transcript uuid; profile t1)"
is    "…so the cell now ends on the transcript a reader could finally name" \
      "$(printf '%s' "$(grep '^| `repoDW-1`' "$LANES" | awk -F'|' '{print $3}')" | grep -o '[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{12\}' | tail -n1)" "$DW_NEW"
has   "…and NOW the lane's RESUMED log line, carrying that uuid" \
      "$(cat "$LOGD/repoDW-1.md")" "RESUMED — lane repoDW-1, session $DW_NEW@"
hasnt "…never \`session unknown@\`, which is the line Amendment 7(b) forbids" "$(cat "$LOGD/repoDW-1.md")" "session unknown@"
has   "…and NOW Rule 3's handoff stamp, the same uuid again" \
      "$(cat "$WIP/handoffs/repoDW/x.md")" "RESUMED by $DW_NEW (lane repoDW-1) at "
is    "…spliced under the header block, one line added and none changed" \
      "$(sed -n 3p "$WIP/handoffs/repoDW/x.md" | cut -c1-19)" "RESUMED by aaaa000e"
has   "…in its own commit, with the handoff subject Amendment 8(d) gives it" \
      "$(git -C "$WIP" log --format=%s -n5 | grep -m1 'handoff(' || :)" "handoff(repoDW-1@"
is    "…and one set of records that agree: the row's newest stamp names it too" \
      "$(grep '^| `repoDW-1`' "$LANES" | grep -o 'RESUMED by [^ ]*' | tail -n1)" "RESUMED by $DW_NEW"
unset FAKE_TMUX_WINDOW
rm -f "$sessions_dir/live-dw.json"

# ---- RV-B2: the handoff stamp's DEGRADED pushes, and which recovery each is
#
# F-B7's whole deliverable is a SENTENCE — `hs_carry_note` telling the reader
# whether anything on this workstation will ever push the commit `lane-start`
# just made — and at `77a2f49` not one assertion in this suite read either
# branch of it (`grep -c "register's own checkout" test_lane_helpers.sh` -> 0).
# An untested sentence is what drifts, and this one is the difference between a
# stamp that lands by itself and a stamp nobody will ever see again.
#
# THE REJECTION IS SCOPED BY THE COMMIT, NOT BY THE DIRECTORY. In the first case
# the handoff repo IS the register's checkout, so a blanket refusal of `push -C
# $WIP` would fail `append-row-status` instead — and `lane-start` runs under
# `set -e`, so it would never reach the handoff block the case is about.
# Amendment 8(d) gives the stamp commit the subject `handoff(<lane>@<ws>): …`,
# which no register write carries, and the push follows its own commit
# immediately: HEAD is therefore an exact discriminator. `commit_push` commits
# before it pulls or pushes for the same reason, so the register's own calls are
# always looking at a register commit when this fake reads HEAD.
cat > "$SANDBOX/rejectgit" <<'FAKE'
#!/usr/bin/env bash
# Refuses $RJ_VERB (`push` or `pull`) for the handoff stamp's commit ONLY;
# everything else, the register's own writes included, goes to the real git.
rj_dir="."; rj_hit=0; rj_prev=""
for a in "$@"; do
  [ "$rj_prev" = "-C" ] && rj_dir="$a"
  [ "$a" = "${RJ_VERB:-push}" ] && rj_hit=1
  rj_prev="$a"
done
if [ "$rj_hit" = 1 ]; then
  case "$(git -C "$rj_dir" log --format=%s -n1 2>/dev/null)" in
    handoff\(*) printf 'fake git: %s refused\n' "${RJ_VERB:-push}" >&2; exit 1 ;;
  esac
fi
exec git "$@"
FAKE
chmod +x "$SANDBOX/rejectgit"

# The paths as GIT spells them, which is what `lane-start` prints: `hs_repo` is
# `rev-parse --show-toplevel` of the handoff's real path, so comparing against
# the shell's own `$WIP`/`$WS2` would compare two spellings of one directory.
WIP_REAL="$(git -C "$WIP" rev-parse --show-toplevel)"

# (a) THE HANDOFF IS IN THE REGISTER'S OWN CHECKOUT. The next `lanes-edit.sh`
#     write out of it pushes the branch, and the orphaned commit rides out with
#     it — so the note may promise the carry, and does.
CN_A="cccc0001-1111-4000-8000-cccc00011111"
printf '{"type":"custom-title","customTitle":"repoCN-1","sessionId":"%s"}\n' "$CN_A" > "$tdir/$CN_A.jsonl"
mkdir -p "$WIP/handoffs/repoCN"
printf 'Lane: repoCN-1 — single-use resume prompt\n\n# state\n' > "$WIP/handoffs/repoCN/a.md"
git -C "$WIP" add -- handoffs/repoCN/a.md
git -C "$WIP" commit -q -m 'handoff fixture for repoCN-1'
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoCN-1\` | harness \`$CN_A\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoCN/a.md | ACTIVE |" >/dev/null 2>&1

run env LANES_GIT="$SANDBOX/rejectgit" RJ_VERB=push "$START" --dir "$HOME/projects/repoA" repoCN-1 --no-launch
is   "a handoff stamp whose PUSH is rejected still exits 0 — the record is not the licence" "$rc" 0
has  "…the stamp really written and committed all the same" "$(cat "$WIP/handoffs/repoCN/a.md")" "RESUMED by $CN_A (lane repoCN-1) at "
has  "…in its own commit, which is the one nothing pushed" "$(git -C "$WIP" log --format=%s -n1)" "handoff(repoCN-1@"
has  "…and the reader told what state that leaves, in the branch's own words" "$err" "the push was rejected — the stamp is a local commit here and other workstations cannot see it yet."
has  "…told to LOOK before pushing again, never to push blind" "$err" "git -C $WIP_REAL fetch origin main && git -C $WIP_REAL log --oneline origin/main -3"
has  "…the re-push conditional on what that look finds" "$err" "git -C $WIP_REAL push origin main      # only if it is not there"
has  "…and F-B7's sentence for a handoff INSIDE the register's checkout, verbatim" "$err" "(this handoff is in the register's own checkout, so the next lanes-edit.sh write out of it pushes the branch and carries this commit with it.)"
hasnt "…never the other branch's, which would be the wrong promise here" "$err" "no lanes-edit.sh write will ever push it"

# (b) THE HANDOFF IS RESOLVED THROUGH `LANES_WORKSPACE_ROOT`, into a checkout no
#     `lanes-edit.sh` write ever goes out of. Nothing will carry this commit,
#     and promising a carry that will not happen is worse than printing the
#     command — so the note names the checkout and says the command is the whole
#     of the recovery. Its own bare origin, because the point is that this is a
#     SECOND repository: `hs_resolve`'s case (b) must miss before case (c) hits,
#     which is why the cell names a file `$WIP` does not have.
WS2_ORIGIN="$SANDBOX/ws2-origin.git"; WS2="$SANDBOX/ws2"
git init -q --bare -b main "$WS2_ORIGIN"
git clone -q "$WS2_ORIGIN" "$WS2" 2>/dev/null
git -C "$WS2" config user.email "test@example.invalid"
git -C "$WS2" config user.name  "lane helper tests"
mkdir -p "$WS2/handoffs/repoCN"
printf 'Lane: repoCN-2 — single-use resume prompt\n\n# state\n' > "$WS2/handoffs/repoCN/b.md"
git -C "$WS2" add -- handoffs/repoCN/b.md
git -C "$WS2" commit -q -m 'handoff fixture for repoCN-2'
git -C "$WS2" push -q origin main
WS2_REAL="$(git -C "$WS2" rev-parse --show-toplevel)"
CN_B="cccc0002-2222-4000-8000-cccc00022222"
printf '{"type":"custom-title","customTitle":"repoCN-2","sessionId":"%s"}\n' "$CN_B" > "$tdir/$CN_B.jsonl"
"$E" add-row "| \`repoCN-2\` | harness \`$CN_B\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoCN/b.md | ACTIVE |" >/dev/null 2>&1
is   "the cell names a handoff the register's checkout does NOT hold" "$([ -e "$WIP/handoffs/repoCN/b.md" ] && printf present || printf absent)" absent

run env LANES_GIT="$SANDBOX/rejectgit" RJ_VERB=push LANES_FILE="$LANES" LANES_REPO="$WIP" \
        LANES_WORKSPACE_ROOT="$WS2" "$START" --dir "$HOME/projects/repoA" repoCN-2 --no-launch
is   "…and a rejected push on THAT checkout exits 0 too" "$rc" 0
has  "…the stamp written into the second checkout, not the register's" "$(cat "$WS2/handoffs/repoCN/b.md")" "RESUMED by $CN_B (lane repoCN-2) at "
is   "…which the register's checkout never gained a copy of" "$([ -e "$WIP/handoffs/repoCN/b.md" ] && printf present || printf absent)" absent
has  "…and F-B7's OTHER sentence, naming the checkout nothing will ever push" "$err" "(this handoff is NOT in the register's checkout ($WS2_REAL), so no lanes-edit.sh write will ever push it: the command above is the whole of the recovery.)"
hasnt "…never promising a carry that no write will perform" "$err" "carries this commit with it"

# ---- RV-B3: an ABORTED PULL is not proof the commit stayed here
#
# The case, live on 2026-09-12T23:04Z: this lane's handoff commit hit a
# `pull --rebase` abort on a peer lane's untracked log file, and the peer's own
# helper then rebased and pushed — carrying this lane's local commit `59a2576`
# out to origin UNDERNEATH its own `f053245`. The branch's recovery was a bare
# re-push, so a reader who ran it at that moment would have landed the same Rule
# 3 stamp twice, in the one document this protocol never rewrites. The
# push-rejected branch has always told the reader to look first; this one now
# does too, and the test pins the ORDER as well as the text, because a look
# printed after the push it is meant to gate is not a look.
CN_C="cccc0003-3333-4000-8000-cccc00033333"
printf '{"type":"custom-title","customTitle":"repoCN-3","sessionId":"%s"}\n' "$CN_C" > "$tdir/$CN_C.jsonl"
printf 'Lane: repoCN-3 — single-use resume prompt\n\n# state\n' > "$WIP/handoffs/repoCN/c.md"
git -C "$WIP" add -- handoffs/repoCN/c.md
git -C "$WIP" commit -q -m 'handoff fixture for repoCN-3'
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoCN-3\` | harness \`$CN_C\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoCN/c.md | ACTIVE |" >/dev/null 2>&1

run env LANES_GIT="$SANDBOX/rejectgit" RJ_VERB=pull "$START" --dir "$HOME/projects/repoA" repoCN-3 --no-launch
is   "a handoff stamp whose PULL aborts still exits 0" "$rc" 0
has  "…the stamp written and committed here all the same" "$(git -C "$WIP" log --format=%s -n1)" "handoff(repoCN-3@"
has  "…the branch saying what happened, not the timeout's words" "$err" "the pull before the push did not apply (a conflict, or no reachable origin) — the rebase is aborted, the checkout is clean, and the stamp is a local commit here that was not pushed."
hasnt "…and never ruling (h)'s line, which is a different failure" "$err" "the pull before the push TIMED OUT"
has  "…then the LOOK, because a peer's push may already carry this very commit" "$err" "git -C $WIP_REAL fetch origin main && git -C $WIP_REAL log --oneline origin/main -3   # a peer's push may already carry it"
has  "…and the re-push conditional on what it finds" "$err" "git -C $WIP_REAL pull --rebase origin main && git -C $WIP_REAL push origin main      # only if it is not there"
cn_look="$(printf '%s\n' "$err" | grep -n -- 'log --oneline origin/main -3' | head -n1 | cut -d: -f1)"
cn_push="$(printf '%s\n' "$err" | grep -n -- 'pull --rebase origin main && ' | head -n1 | cut -d: -f1)"
is   "…the look printed BEFORE the re-push it gates, which is the whole of RV-B3" \
     "$([ -n "$cn_look" ] && [ -n "$cn_push" ] && [ "$cn_look" -lt "$cn_push" ] && printf 'look first' || printf "look $cn_look, push $cn_push")" "look first"
has  "…and F-B7's carry note under it, the same two branches as the push case" "$err" "(this handoff is in the register's own checkout, so the next lanes-edit.sh write out of it pushes the branch and carries this commit with it.)"

# ------------------------------------------------- lane-start --confirm / --yes
#
# A window whose name is not the lane is a window whose lane came from somewhere
# else — the swap record, or a flag. Taking it renames the window and writes the
# register, so `--confirm` puts the three facts that disagree in front of a
# person first.
"$E" add-row "| \`repoCF-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoCF/x.md | ACTIVE |" >/dev/null 2>&1
"$E" add-row "| \`repoCF-2\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoCF/y.md | ACTIVE |" >/dev/null 2>&1
"$E" add-row "| \`repoCF-3\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoCF/z.md | ACTIVE |" >/dev/null 2>&1

# R-A8-3 — A LAUNCHER NEVER REFUSES TO START CLAUDE, and `claude-profile` EXECS
# this script, so a refusal here is an exited pane with no Claude in it. `N`
# means NOT THIS LANE, not NOT AT ALL: both answers fall through to Claude bare,
# with the pass-through arguments, exit 0, one notice, nothing renamed and
# nothing written. Under `--no-launch` the bare command is what stdout carries,
# which is the contract the launcher execs.
cf_before="$(git -C "$WIP" rev-parse HEAD)"
cf_renames="$(grep -c 'rename-window repoCF-2' "$FAKE_TMUX_LOG" || :)"
out="$("$START" --confirm --dir "$HOME/projects/repoA" repoCF-2 --no-launch </dev/null 2>"$SANDBOX/stderr")"; rc=$?
err="$(cat "$SANDBOX/stderr")"
is    "--confirm with no terminal and no --yes launches Claude BARE, exit 0" "$rc" 0
is    "…and the command it prints is the bare one, with no lane in it" "$(launch_of "$out")" "claude"
has   "…saying a question nobody can answer is not a yes" "$err" "there is no terminal to ask on"
has   "…and that nothing was done" "$err" "Nothing has been renamed and nothing has been written"
has   "…naming the act that takes the lane later, its arguments filled in" "$err" "to take it later, run: lane-start repoCF 2"
is    "…renaming no window" "$(grep -c 'rename-window repoCF-2' "$FAKE_TMUX_LOG" || :)" "$cf_renames"
is    "…and writing nothing at all" "$(git -C "$WIP" rev-parse HEAD)" "$cf_before"

run env LANE_START_ANSWER=n "$START" --confirm --dir "$HOME/projects/repoA" repoCF-2 --no-launch
is    "--confirm answered N launches Claude bare too, exit 0 — never exit 2" "$rc" 0
is    "…the bare command, with no --resume and no --name" "$(launch_of "$out")" "claude"
has   "…quoting the answer it got" "$err" "the answer was 'n'"
has   "…in ONE notice" "$err" "Starting Claude with no lane"
is    "…and still writes nothing" "$(git -C "$WIP" rev-parse HEAD)" "$cf_before"
run env LANE_START_ANSWER= "$START" --confirm --dir "$HOME/projects/repoA" repoCF-2 --no-launch
is    "…as does an empty answer, which is the [y/N] default" "$rc" 0
has   "…and says so" "$err" "<empty, which is N>"
: > "$FAKE_CLAUDE_LOG"
run env LANE_START_ANSWER=n "$START" --confirm --dir "$HOME/projects/repoA" repoCF-2 -- --dangerously-skip-permissions
is    "…and a real launch execs it, carrying the pass-through arguments" "$rc" 0
is    "…bare, which is what the operator asked for by saying N" "$(cat "$FAKE_CLAUDE_LOG")" "--dangerously-skip-permissions"
is    "…with the register still untouched by any of it" "$(git -C "$WIP" rev-parse HEAD)" "$cf_before"

run env LANE_START_ANSWER=y "$START" --confirm --dir "$HOME/projects/repoA" repoCF-1 --no-launch
is    "--confirm answered y takes the lane" "$rc" 0
has   "…having printed the WINDOW" "$err" "window   testsess:@1 'claude'"
has   "…the SESSION live in it, when there is one to name" "$err" "session  none — no live session record names this window"
has   "…the ROW" "$err" "row      | \`repoCF-1\`"
has   "…and named the auto-named window as what it is" "$err" "auto-named 'claude'"
has   "…then renamed the window" "$(cat "$FAKE_TMUX_LOG")" "rename-window repoCF-1"

run "$START" --confirm --yes --dir "$HOME/projects/repoA" repoCF-3 --no-launch -- --dangerously-skip-permissions
is    "--yes answers it without a terminal and without the seam" "$rc" 0
has   "…saying which of the two answered" "$err" "(--yes)"
is    "…with the flags BEFORE the lane and -- passing through to claude" \
      "$(launch_of "$out")" "claude --resume $DEAD_ID --dangerously-skip-permissions"

export FAKE_TMUX_WINDOW_NAME=repoCF-1
run env LANE_START_ANSWER=n "$START" --confirm --dir "$HOME/projects/repoA" repoCF-1 --no-launch
is    "--confirm asks nothing when the window is ALREADY named for the lane" "$rc" 0
has   "…and says so" "$err" "already named repoCF-1 — nothing to confirm"
unset FAKE_TMUX_WINDOW_NAME

run "$START" --dir "$HOME/projects/repoA" repoCF-1 --no-launch
is    "without --confirm nothing is asked, which is today's behaviour" "$rc" 0
hasnt "…and no triple is printed" "$err" "Take lane repoCF-1 in this window?"
has   "lane-start --help LISTS --confirm, which is what the launcher greps for" "$("$START" --help)" "  --confirm  "
has   "…and --yes beside it" "$("$START" --help)" "  --yes  "

# ------------------------------------------------------------- session-start
#
# The SessionStart hook's whole output. It NEVER writes and it ALWAYS exits 0:
# a hook that fails is a hook that breaks the session it was meant to orient.
SS_OLD="aaaa000c-1111-4000-8000-aaaa000c1111"
SS_CUR="aaaa000c-2222-4000-8000-aaaa000c2222"
SS_NEW="aaaa000c-3333-4000-8000-aaaa000c3333"
"$E" add-row "| \`repoSS-1\` | harness \`$SS_OLD\` → after /clear \`$SS_CUR\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoSS/session-handoff-2026-09-12-lane-repoSS-1.md | ACTIVE |" >/dev/null 2>&1
run env LANES_LANE=repoSS-1 "$E" claim "opensoft/repoSS#5" --home opensoft/repoSS --no-github
is   "the hook's lane holds an object to report" "$rc" 0

ss_hook='{"session_id":"%s","source":"%s","cwd":"/home/x/projects/repoSS","hook_event_name":"SessionStart"}'
ss_run() {   # <session id> <source>
  ssr_id="$1"; ssr_src="$2"
  out="$(printf "$ss_hook" "$ssr_id" "$ssr_src" | "$E" session-start 2>"$SANDBOX/stderr")"; rc=$?
  err="$(cat "$SANDBOX/stderr")"
  return 0
}
ss_before="$(git -C "$WIP" rev-parse HEAD)"
export FAKE_TMUX_WINDOW_NAME=repoSS-1

ss_run "$SS_CUR" resume
is   "session-start exits 0" "$rc" 0
is   "…printing exactly four lines" "$(printf '%s\n' "$out" | grep -c .)" 4
has  "…the lane, its handoff and the session its row records" "$out" "LANE repoSS-1 — handoff handoffs/repoSS/session-handoff-2026-09-12-lane-repoSS-1.md — row session $SS_CUR"
has  "…what Rule 3 owes" "$out" "stamp the handoff RESUMED (Rule 3) and follow its top block"
has  "…and the lane's open objects, on one line" "$out" "open: CLAIMED opensoft/repoSS#5"
has  "…and how old the answer is, because it never fetches to get it (R-A8-1)" "$out" "as of "
has  "…saying in the same breath that it did not fetch to get it — clause (e)'s own last line" "$out" "(no fetch)"
is   "…which is the LAST line of the block, on every branch" "$(printf '%s\n' "$out" | tail -n1 | sed 's/as of .*(no fetch)/TAIL/')" "TAIL"

ss_run "$SS_OLD" resume
is   "an EARLIER session of the same lane exits 0 too" "$rc" 0
is   "…and prints the warning and the age of the read, and nothing else" "$(printf '%s\n' "$out" | grep -c .)" 2
is   "…the SUPERSEDED-TRANSCRIPT warning, with <repo> <n> FILLED IN" "$(printf '%s\n' "$out" | head -n1)" \
     "WARNING: this is a superseded transcript of lane repoSS-1; the live one is $SS_CUR; you resumed $SS_OLD — exit this session and run: lane-start repoSS 1"
hasnt "…which never names /resume or the picker, neither being a lane surface (clause (f))" "$out" "resume the"
hasnt "…so no reader has to translate repoSS-1 into repoSS 1 by hand, ever again" "$out" "<repo> <n>"

ss_run "$SS_NEW" startup
is   "a session id NO row carries is the OTHER mismatch" "$rc" 0
has  "…and the block says which of the two it is" "$out" "this session $SS_NEW is in no row — the harness minted a new transcript"
has  "…sending it at the act that fixes it, which is not a plain lane-start" "$out" "run: lane-start --no-launch repoSS 1"
hasnt "…so it is not confused with resuming an earlier lineage" "$out" "you resumed"

ss_run "$SS_CUR" fork
is   "a FORK is an attachment to the lane, so it gets the block" "$rc" 0
has  "…in full" "$out" "LANE repoSS-1 — handoff"
ss_run "$SS_CUR" compact
is   "a COMPACT exits 0" "$rc" 0
is   "…and prints NOTHING: the same session carries on in the same window" "$out" ""
ss_run "$SS_CUR" clear
has  "a CLEAR gets the block" "$out" "LANE repoSS-1"
out="$(printf '{"session_id":"%s","cwd":"/home/x"}' "$SS_CUR" | "$E" session-start 2>/dev/null)"; rc=$?
is   "a payload with NO source at all exits 0" "$rc" 0
has  "…and is treated as a startup rather than dropped" "$out" "LANE repoSS-1"
out="$(printf '{"session_id":"%s","source":"teleport"}' "$SS_CUR" | "$E" session-start 2>/dev/null)"; rc=$?
has  "…as is a source no harness has invented yet" "$out" "LANE repoSS-1"

export FAKE_TMUX_WINDOW_NAME=claude
ss_run "$SS_CUR" resume
is   "a window that names no lane falls back to the session id" "$rc" 0
has  "…and resolves the lane out of the register's session cells" "$out" "LANE repoSS-1"
ss_run "$SS_NEW" startup
is   "…and when neither answers, it says so" "$rc" 0
is   "…in ONE notice — the launcher's own is the second of two, and Amendment 8 drops it" "$(printf '%s\n' "$out" | head -n1)" "no lane bound to this window — run: lane-start <repo> <n>"
has  "…and the age of the read it answered from" "$out" "(no fetch)"

export FAKE_TMUX_WINDOW_NAME=REPOSS-1
ss_run "$SS_CUR" resume
has  "the window name is matched case-blind: Rule 10's wire form is lowercase" "$out" "LANE repoSS-1"
unset FAKE_TMUX_WINDOW_NAME

out="$(printf 'not json at all' | "$E" session-start 2>/dev/null)"; rc=$?
is   "garbage on stdin exits 0 — a hook must never break the session" "$rc" 0
out="$(printf '' | LANES_FILE="$SANDBOX/no-such-register.md" "$E" session-start 2>/dev/null)"; rc=$?
is   "…and so does no register at all, which every other subcommand refuses" "$rc" 0
is   "session-start wrote nothing, through all of that" "$(git -C "$WIP" rev-parse HEAD)" "$ss_before"
is   "…and left the checkout clean" "$(git -C "$WIP" status --porcelain | grep -c .)" 0

# NO CURE SENDS A READER BACK THROUGH THE PICKER (clause (f); clause (e)'s "the
# first cure carries one condition"). A real `lane-start` is the superseded-
# transcript remedy BECAUSE the cell's last id names a transcript the lane's
# directory has. Where the last launch took the title fallback, it does not —
# and the row says so in its own words, `RESUMED by unknown` — so a relaunch
# would put the reader in front of the same picker, and the recording act is the
# cure there too. The hook reads the row, never a directory it was not handed.
SU_OLD="aaaa0010-1111-4000-8000-aaaa00101111"
SU_CUR="aaaa0010-2222-4000-8000-aaaa00102222"
"$E" add-row "| \`repoSU-1\` | harness \`$SU_OLD\` → harness $SU_CUR (transcript uuid; profile t1) | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoSU/x.md | ACTIVE |" >/dev/null 2>&1
export FAKE_TMUX_WINDOW_NAME=repoSU-1
ss_run "$SU_OLD" resume
is   "a superseded transcript of a normally-resumable lane is cured by a real lane-start" "$(printf '%s\n' "$out" | head -n1)" \
     "WARNING: this is a superseded transcript of lane repoSU-1; the live one is $SU_CUR; you resumed $SU_OLD — exit this session and run: lane-start repoSU 1"
"$E" append-row-status repoSU-1 "2026-09-12T23:00:00Z RESUMED by unknown (lane repoSU-1) — lane-start on Eagle: window renamed, no launch" >/dev/null 2>&1
ss_run "$SU_OLD" resume
has  "…but one whose NEWEST row stamp says unknown is cured by the RECORDING act" "$out" "run: lane-start --no-launch repoSU 1"
has  "…saying why, in the row's own word" "$out" "which the row records as \`unknown\`"
hasnt "…never by a relaunch that would take the same title fallback again" "$out" "exit this session and run"
hasnt "…and no branch of this block ever names the picker" "$out" "/resume"
unset FAKE_TMUX_WINDOW_NAME


# R-A8-1 — SESSION-START NEVER FETCHES AND NEVER WRITES, and this is the test
# that was missing: the four-way review removed `log_sync` from the branch as a
# mutation and the suite stayed at 760/0, so nothing pinned whether the hook in
# front of EVERY session start on this workstation opened the network. The fake
# `git` aborts on the four verbs that do — fetch, ls-remote, pull, push — and
# records the attempt, so a re-added fetch is not merely slow here, it is
# CAUGHT. The tree, the refs, HEAD and FETCH_HEAD's own mtime are compared
# either side of the call, because "never writes" is about the .git directory
# as much as the working tree.
NONET="$SANDBOX/nonet"; mkdir -p "$NONET"
REAL_GIT="$(command -v git)"
cat > "$NONET/git" <<FAKE
#!/usr/bin/env bash
for a in "\$@"; do
  case "\$a" in
    fetch|ls-remote|pull|push) printf 'git %s\n' "\$*" >> "$SANDBOX/gitnet.log"; exit 99 ;;
  esac
done
exec "$REAL_GIT" "\$@"
FAKE
chmod +x "$NONET/git"
: > "$SANDBOX/gitnet.log"
# RV-B1 — THE DIGEST IS sha256, and that is not a detail. Comparing a directory
# with itself needs no cryptographic strength at all, so `sha1sum` was the
# obvious reach; but `sha1sum` in a shell script is `shell:S4790` ("weak hash
# algorithm"), CRITICAL, and ONE such issue on a PR's new lines is a Security
# rating of D, which fails the `new_security_rating` gate condition on its own —
# issue `AaCXxOSfi2WmFx-_lncg`, this file, this line, 2026-09-12T22:37Z. A test
# file is not the place to argue an exception, and a `# NOSONAR` marker would
# hide the finding rather than answer it. `sha256sum` costs nothing here.
tree_of() {   # <checkout>
  local to_dir="$1"
  ( cd "$to_dir" && find . -path ./.git -prune -o -type f -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum | sha256sum )
  return 0
}
ss_tree_before="$(tree_of "$WIP")"
ss_refs_before="$(git -C "$WIP" for-each-ref --format='%(refname) %(objectname)')"
ss_head2_before="$(git -C "$WIP" rev-parse HEAD)"
ss_fh_before="$(stat -c %Y "$WIP/.git/FETCH_HEAD" 2>/dev/null || printf 'none')"
export FAKE_TMUX_WINDOW_NAME=repoSS-1
out="$(printf "$ss_hook" "$SS_CUR" resume | PATH="$NONET:$PATH" "$E" session-start 2>"$SANDBOX/stderr")"; rc=$?
err="$(cat "$SANDBOX/stderr")"
is   "session-start exits 0 with a git that refuses every network call" "$rc" 0
is   "…having made NONE of them: no fetch, no ls-remote, no pull, no push" "$(cat "$SANDBOX/gitnet.log")" ""
has  "…and still printing the whole block, from the checkout as it last stood" "$out" "LANE repoSS-1 — handoff"
is   "…the working tree byte-identical either side of it" "$(tree_of "$WIP")" "$ss_tree_before"
is   "…every ref where it was, origin/main included" "$(git -C "$WIP" for-each-ref --format='%(refname) %(objectname)')" "$ss_refs_before"
is   "…HEAD where it was" "$(git -C "$WIP" rev-parse HEAD)" "$ss_head2_before"
is   "…and .git/FETCH_HEAD not even touched, which is what a fetch would move" "$(stat -c %Y "$WIP/.git/FETCH_HEAD" 2>/dev/null || printf 'none')" "$ss_fh_before"
unset FAKE_TMUX_WINDOW_NAME

# R-A8-7 — the block stops asking for a stamp `lane-start` has already written.
# Derived, not assumed: the handoff the ROW names is read, and the line is the
# one THIS session would owe. A window started by a bare `claude` has no stamp
# and is still told to write one.
mkdir -p "$WIP/handoffs/repoSS"
SS_HO="$WIP/handoffs/repoSS/session-handoff-2026-09-12-lane-repoSS-1.md"
printf 'Lane: repoSS-1 — single-use resume prompt\n\n# state\n' > "$SS_HO"
export FAKE_TMUX_WINDOW_NAME=repoSS-1
ss_run "$SS_CUR" resume
has  "an UNSTAMPED handoff is still asked for Rule 3's stamp" "$out" "stamp the handoff RESUMED (Rule 3)"
printf 'Lane: repoSS-1 — single-use resume prompt\nRESUMED by %s (lane repoSS-1) at 2026-09-12T20:00:00Z — lane-start on Eagle\n\n# state\n' "$SS_CUR" > "$SS_HO"
ss_run "$SS_CUR" resume
is   "…and one lane-start has already stamped says so instead, in clause (e)'s words" "$(printf '%s\n' "$out" | sed -n 2p)" "handoff already stamped by lane-start — follow its top block"
hasnt "…so the block never manufactures a decision the launch already took" "$out" "stamp the handoff RESUMED (Rule 3) and follow"
rm -rf -- "$WIP/handoffs"
unset FAKE_TMUX_WINDOW_NAME

# The row that carries only `session_…` FOOTER ids — 15 of the live register's
# 42 — has no transcript uuid to mismatch AGAINST, so it is not one of clause
# (e)'s two mismatches and must not be reported as one: the block says what the
# row records, which is nothing this hook can check.
export FAKE_TMUX_WINDOW_NAME=repoA-13
ss_run "$SS_NEW" startup
is    "a footer-only row's session start exits 0" "$rc" 0
has   "…and gets the bound block, because there are exactly TWO mismatches (F-T2)" "$out" "LANE repoA-13 — handoff"
has   "…saying honestly that the row records no session it can read" "$out" "row session none recorded"
hasnt "…and never a WARNING, which would be a third mismatch the amendment does not define" "$out" "WARNING:"

# A lane named before the `<repo>-<n>` rule cannot be split on its last `-`.
export FAKE_TMUX_WINDOW_NAME=browser-ui-repair
ss_run "$SS_NEW" startup
has  "a lane whose name is not <repo>-<n> is started through --dir, not by a bad split" "$out" "run: lane-start --no-launch --dir <path> browser-ui-repair"
hasnt "…never 'browser-ui repair', which is a command that does the wrong thing" "$out" "browser-ui repair"
unset FAKE_TMUX_WINDOW_NAME

# A lane with no log of its own says so rather than reporting nothing open.
"$E" add-row "| \`repoSS-2\` | harness \`$SS_CUR\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoSS/y.md | ACTIVE |" >/dev/null 2>&1
export FAKE_TMUX_WINDOW_NAME=repoSS-2
ss_run "$SS_CUR" startup
has  "a pre-cutover lane's block says where to look instead" "$out" "open: no log for repoSS-2 (pre-cutover lane)"
unset FAKE_TMUX_WINDOW_NAME

# RV-B4 — THE README QUOTES THE HOOK, and these are what keep it quoting it.
# `README-lanes.md`'s `session-start` section had drifted to lines the code does
# not print — a `— run: lane-start <repo> <n>` where the hook says `— exit this
# session and run: lane-start repoSS 1`, no `unknown`-stamp sub-branch at all,
# and not one example block carrying the `as of … (no fetch)` line Amendment
# 8(e) requires on EVERY block — and nothing noticed, because no assertion in
# this suite had ever read the document. A quoted line nobody reads is the same
# defect as an untested sentence (RV-B2), one file over. Read from `$SRC_DIR`,
# the checkout's own copy, which is the one a person opens.
ss_doc="$(cat "$SRC_DIR/docs/README-lanes.md" 2>/dev/null || :)"
has  "the README states the subcommand's THIRD safety property, not just two" "$ss_doc" "It never writes, it never touches the network, and it always exits 0"
has  "…and carries the line every block ends with" "$ss_doc" "as of 4m ago (no fetch)"
has  "…quoting the superseded-transcript branch as the hook really prints it" "$ss_doc" "WARNING: this is a superseded transcript of lane repoSS-1; the live one is <U>; you resumed <V> — exit this session and run: lane-start repoSS 1"
has  "…its \`unknown\`-stamp sub-branch, which sends the reader to the RECORDING act" "$ss_doc" "which the row records as \`unknown\` — a relaunch would record nothing either, so run: lane-start --no-launch repoSS 1"
has  "…the in-no-row branch, its command filled in too" "$ss_doc" "this session <V> is in no row — the harness minted a new transcript — run: lane-start --no-launch repoSS 1"
has  "…and the third bound-branch line, the one Rule 3's stamp is owed on" "$ss_doc" "stamp the handoff RESUMED (Rule 3) and follow its top block"
hasnt "…never the drifted spelling, which no branch of the hook has ever printed" "$ss_doc" "whose current session is <U>; you resumed <V> — run: lane-start <repo> <n>"

# ------------------------------------------------- Rule 1's sibling reads
#
# Measured live on 2026-09-12 against the governing repository: `gh pr list
# --search 15` answered with PR #16 and PR #10 — GitHub had matched the digits
# inside "**15 of the register's 41 rows**" — and `ls-remote | grep 15` answered
# with a branch whose SHA merely contains them. TWO READS, TWO TESTS, because
# the two inputs are not the same kind of text.

# `gh pr list`'s rows are PROSE, so a reference is `#<n>` and a bare number is
# not one. The `#`'s LEFT side is unbounded on purpose: the canonical spelling
# is `owner/repo#15` and the character before the `#` is a letter — the reason
# the columns-only filter dropped the real PR for this very issue.
SIB_PR="$(printf '15\tthe amendment 8 work\tlanes/a8\tOPEN\tthis body says nothing\n10\tbump the pin to 1150\tchore/pin\tMERGED\t15 of the register rows carry no uuid\n7\tsomething else\tfix/x\tOPEN\tGoverning issue: opensoft/repoE#15. three pieces in parallel\n8\tanother\tfix/y\tOPEN\tcloses #150 and nothing else\n')"
out="$(printf '%s\n' "$SIB_PR" | "$E" sibling-filter "opensoft/repoE#15" 2>/dev/null)"; rc=$?
is    "sibling-filter exits 0" "$rc" 0
has   "…keeping the row whose own number IS the object" "$out" "15	the amendment 8 work"
has   "…and the row whose BODY names owner/repo#15, where a LETTER precedes the #" "$out" "7	something else"
hasnt "…dropping the row that merely says 15 in prose, which is what the old read returned" "$out" "1150"
hasnt "…and the one that names a longer number" "$out" "8	another"

# `ls-remote`'s refs are NAMES: `issue-15-fix` names the object and carries no
# hash, so the bare number as a whole token is the test — after the sha, which
# is 40 characters of digits nobody meant, has been taken off the front.
SIB_BR="$(printf '0000000000000000000000000000000000000015\trefs/heads/unrelated\nabc123def4560000000000000000000000000000\trefs/heads/issue-15-fix\n1111111111111111111111111111111111111111\trefs/heads/topic-150\n')"
out="$(printf '%s\n' "$SIB_BR" | "$E" sibling-filter --branch "opensoft/repoE#15" 2>/dev/null)"
has   "a branch NAMED for the object is kept, by the bare number" "$out" "refs/heads/issue-15-fix"
hasnt "…with the sha stripped, so a branch is matched by its name and never by its commit" "$out" "abc123def456"
hasnt "…and a branch whose SHA merely contains the digits is dropped" "$out" "refs/heads/unrelated"
hasnt "…as is one whose name carries a longer number" "$out" "topic-150"
out="$(printf '%s\n' "$SIB_BR" | "$E" sibling-filter "opensoft/repoE#15" 2>/dev/null)"
hasnt "…and the pr test would have dropped that branch, which is why there are two" "$out" "issue-15-fix"

# An OpenSpec change directory has a word for a slug and takes the whole-token
# test in either mode, with the slug's own regex characters quoted.
out="$(printf 'x add.thing y\nx addXthing y\n' | "$E" sibling-filter "opensoft/repoE:openspec/changes/add.thing" 2>/dev/null)"
has   "an OpenSpec change is matched by its own slug" "$out" "x add.thing y"
hasnt "…and not by a name that merely matches it with '.' read as any character" "$out" "addXthing"
run   "$E" sibling-filter --nope "opensoft/repoE#1"
is    "an unknown option is refused" "$rc" 2


# =========================================================================
# AMENDMENT 8, RULING (g) — WHOSE SESSION IS THIS?
#
# Live, on 2026-09-12: `lane-start --no-launch openRepoProject 1` REFUSED in the
# very window whose own session was running it. Two records carried one
# `sessionId` — the pane's `kind: interactive` process, and a `kind: bg`
# companion with no `tmux` and no `nameSource` — and `live_holder` returned the
# COMPANION, whose target read `none`, which is not this window, so the lane was
# refused to itself:
#
#   lane openRepoProject-1 is live in session c5701b54… (tmux none);
#   take openRepoProject-2 or resume that window
#
# The companion also carried the LATER `updatedAt` of the two (…975177 against
# …958137), so recency picks exactly the wrong record. Identity decides:
# `$CLAUDE_CODE_SESSION_ID`, then the window, then this pane's process tree.
# -------------------------------------------------------------------------

# Two live processes: one stands in for the pane's own, the other is alive and
# under no pane at all. Both are children of this shell, so neither is under the
# OTHER — which is exactly the distinction the ruling turns on.
sleep 300 & G_PANE=$!
g_pane_start="$(cut -d' ' -f22 "/proc/$G_PANE/stat" 2>/dev/null || printf '')"
sleep 300 & G_OUT=$!
g_out_start="$(cut -d' ' -f22 "/proc/$G_OUT/stat" 2>/dev/null || printf '')"

# The fields the older helpers never write: `kind`, an ABSENT `tmux` (which is
# what the harness really writes for a companion — not the string "null"), and
# `updatedAt`. `-` means "omit this key entirely".
write_record_g() { # <file> <sessionId> <pid> <procStart> <kind> <tmux|-> <name> <nameSource|-> <updatedAt>
  g_f="$1"; g_sid="$2"; g_pid="$3"; g_start="$4"; g_kind="$5"
  g_tgt="$6"; g_name="$7"; g_src="$8"; g_upd="$9"
  g_t=""; [ "$g_tgt" = "-" ] || g_t="$(printf ',"tmux":"%s"' "$g_tgt")"
  g_ns=""; [ "$g_src" = "-" ] || g_ns="$(printf ',"nameSource":"%s"' "$g_src")"
  printf '{"pid":%s,"sessionId":"%s","cwd":"x","procStart":"%s","kind":"%s"%s,"name":"%s"%s,"status":"busy","updatedAt":%s}\n' \
    "$g_pid" "$g_sid" "$g_start" "$g_kind" "$g_t" "$g_name" "$g_ns" "$g_upd" > "$g_f"
  return 0
}
g_clear() { rm -f "$sessions_dir"/g-*.json; return 0; }

# ---- R-A8-6: THE ORPHANED HOLDERS ARE NAMED, AND NOTHING IS EVER KILLED ----
#
# A row's session cell is a history and its EARLIER ids are history, not
# alternatives — but a live process can still be holding one, which is Amendment
# 6(d)'s orphan and the whole reason this lane's `/resume` picker offered two
# transcripts of which neither was the lane. `idle-holders` answers about ALL of
# them; `lane-start` prints each with the exact act, `kill <pid>`; and clause
# (f) rules the running of it the operator's, because an idle background session
# is exactly the shape of thing that turns out to be somebody's long-running job.
IH_OLD="aaaa000f-1111-4000-8000-aaaa000f1111"
IH_CUR="aaaa000f-2222-4000-8000-aaaa000f2222"
printf '{"type":"user"}\n' > "$tdir/$IH_CUR.jsonl"
"$E" add-row "| \`repoIH-1\` | harness \`$IH_OLD\` → harness $IH_CUR (transcript uuid; profile t1) | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoIH/x.md | ACTIVE |" >/dev/null 2>&1

run   "$E" idle-holders repoIH-1
is    "with no record at all, idle-holders answers 8 — none, not a failed read" "$rc" 8

write_record_g "$sessions_dir/g-ih-orphan.json" "$IH_OLD" "$LIVE_PID" "$live_start" "bg" "-" "repoih-1" "-" 3000
run   "$E" idle-holders repoIH-1
is    "a live \`kind: bg\` record holding an EARLIER id is an orphan" "$rc" 0
is    "…named with its session, pid, kind and profile, one per line" "$out" "$(printf '%s\t%s\tbg\tt1' "$IH_OLD" "$LIVE_PID")"

run   "$START" --dir "$HOME/projects/repoA" repoIH-1 --no-launch
is    "…and lane-start reports it without refusing the launch" "$rc" 0
has   "…with the exact retire act, which is the real one" "$err" "retire it: kill $LIVE_PID"
has   "…and the profile beside it, so a person can check before running it" "$err" "kind bg, profile t1"
has   "…saying what the earlier ids are" "$err" "history, not alternatives"
is    "…having killed nothing: the record is where it was" \
      "$([ -f "$sessions_dir/g-ih-orphan.json" ] && printf present || printf absent)" present
is    "…and the process it names is still alive" "$(kill -0 "$LIVE_PID" 2>/dev/null && printf alive || printf gone)" alive

# `who` IS THE SECOND READER (R-A8-6): the SAME orphan, named to everyone else
# who asks who holds this lane's object — not only the operator about to take
# it. The log line is written directly (as the repoJ-1/repoJ-2 fixtures above
# do), never through `claim`: the earlier `rm -rf -- "$WIP/handoffs"` fixture
# cleanup left the checkout with an unstaged deletion outside this test's
# control, and `claim` would refuse to write against any dirty checkout,
# whoever dirtied it. Writing the log line and pushing it directly proves the
# same thing `print_holder_detail` proves for any other reader: `who` is
# reading a real committed line, not a local artifact of this process.
{ printf '# lane repoIH-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'CLAIMED — lane repoIH-1, session %s@Eagle, 2026-09-12T00:00:00Z, opensoft/repoIH#1\n' "$IH_CUR"
} > "$LOGD/repoIH-1.md"
git -C "$WIP" add -- lanes/log/repoIH-1.md
git -C "$WIP" commit -q -m "fixture: repoIH-1 holds an object, for who's second-reader test"
git -C "$WIP" push -q origin main

run   "$E" who "opensoft/repoIH#1"
is    "who finds it" "$rc" 0
has   "…and the SECOND reader names the very same orphan" "$out" "idle     lane repoIH-1 — an EARLIER session id of this row is still held"
has   "…with its session, pid, kind and profile" "$out" "session $IH_OLD, pid $LIVE_PID (kind bg, profile t1)"
has   "…and the exact retire act, which is the real one" "$out" "History, not an alternative — retire it: kill $LIVE_PID"
hasnt "…and never an \`end pid\` subcommand, because there is none" "$out" "end pid"
is    "…still having killed nothing" \
      "$([ -f "$sessions_dir/g-ih-orphan.json" ] && printf present || printf absent)" present
is    "…and the process it names is still alive" "$(kill -0 "$LIVE_PID" 2>/dev/null && printf alive || printf gone)" alive

# The cell's LAST id is the lane, and a lane is never an orphan of itself.
g_clear
write_record_g "$sessions_dir/g-ih-cur.json" "$IH_CUR" "$LIVE_PID" "$live_start" "bg" "-" "repoih-1" "-" 3000
run   "$E" idle-holders repoIH-1
is    "the cell's LAST id is the lane, never one of its own orphans" "$rc" 8

# A live INTERACTIVE record IN a window is a rival, which is live-holder's
# question, not this one's.
g_clear
write_record_g "$sessions_dir/g-ih-rival.json" "$IH_OLD" "$LIVE_PID" "$live_start" "interactive" "ihsess:@4.%4" "repoih-1" "derived" 3000
run   "$E" idle-holders repoIH-1
is    "a live session IN a window is a rival, not an orphan" "$rc" 8
g_clear

GH_ID="cccc000c-1111-4000-8000-cccc000c1111"
printf '{"type":"user"}\n' > "$tdir/$GH_ID.jsonl"
"$E" add-row "| \`repoGH-1\` | s \`$GH_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | handoffs/repoGH/x.md | ACTIVE |" >/dev/null 2>&1
export FAKE_TMUX_WINDOW="gwsess:@3" FAKE_TMUX_PANE_PID="$G_PANE"
US_SEP="$(printf '\037')"

# -- (g)(2)(3) the incident itself: one session, two records ------------------
g_clear
write_record_g "$sessions_dir/g-interactive.json" "$GH_ID" "$G_PANE" "$g_pane_start" \
  interactive "gwsess:@3.%3" "openrepoproject-45" derived 1789235958137
write_record_g "$sessions_dir/g-companion.json"  "$GH_ID" "$G_OUT"  "$g_out_start" \
  bg - "repoGH-1" - 1789235975177
run "$E" live-holder repoGH-1
is    "one session's two records: live-holder still answers 0" "$rc" 0
has   "…and the verdict is 'here', not a refusal" "$out" "${US_SEP}here"
has   "…reporting the INTERACTIVE record, which is the one in the window" "$out" "gwsess:@3.%3"
hasnt "…never the companion, whose updatedAt is the NEWER of the two" "$out" "${US_SEP}none${US_SEP}"
has   "…and the companion is named on stderr as what it is" "$err" "companion records, which are never holders"
has   "…by its kind" "$err" "kind bg"

run   "$START" --dir "$HOME/projects/repoA" repoGH-1 --no-launch
is    "lane-start does NOT refuse the window its own session is running in" "$rc" 0
has   "…it recognises the session as this window's own" "$err" "already holds repoGH-1"
hasnt "…and never prints the refusal that fired on 2026-09-12" "$err" "take repoGH-2"

# -- (g) addendum: a bg record is never a holder, even alone ------------------
g_clear
write_record_g "$sessions_dir/g-companion.json" "$GH_ID" "$G_OUT" "$g_out_start" \
  bg - "repoGH-1" - 1789235975177
run "$E" live-holder repoGH-1
is    "a bg record ALONE is not a holder at all" "$rc" 8
run   "$START" --dir "$HOME/projects/repoA" repoGH-1 --no-launch
is    "…so it cannot refuse a lane either" "$rc" 0
hasnt "…and nothing claims the lane is live" "$err" "is live in session"

# -- (g)(1) the env var the harness exports beats every other test ------------
g_clear
write_record_g "$sessions_dir/g-envonly.json" "$GH_ID" "$G_OUT" "$g_out_start" \
  interactive - "somewhere-else" - 1000
run env CLAUDE_CODE_SESSION_ID="$GH_ID" "$E" live-holder repoGH-1
is    "CLAUDE_CODE_SESSION_ID names this session: exit 0" "$rc" 0
has   "…and the verdict is 'here' though it has no tmux and no pane-tree pid" "$out" "${US_SEP}here"
run   "$E" live-holder repoGH-1
has   "…while without it the very same record is an ORPHAN, not a rival" "$out" "${US_SEP}orphan"

# -- (g)(3) tmux absent + pid under this pane = this window's session ---------
g_clear
write_record_g "$sessions_dir/g-nulltmux.json" "$GH_ID" "$G_PANE" "$g_pane_start" \
  interactive - "openrepoproject-45" derived 1000
run "$E" live-holder repoGH-1
is    "a record with NO tmux whose pid is in this pane's tree: exit 0" "$rc" 0
has   "…is this window's own session" "$out" "${US_SEP}here"
run   "$START" --dir "$HOME/projects/repoA" repoGH-1 --no-launch
is    "…and lane-start carries on in it" "$rc" 0
has   "…naming it as this window's" "$err" "already holds repoGH-1"

# -- (g)(3) tmux absent + pid under NO pane = an orphan, reported not refused --
g_clear
write_record_g "$sessions_dir/g-orphan.json" "$GH_ID" "$G_OUT" "$g_out_start" \
  interactive - "repoGH-1" - 1000
run "$E" live-holder repoGH-1
is    "a live record in no window and no pane tree: still exit 0" "$rc" 0
has   "…but the verdict is 'orphan'" "$out" "${US_SEP}orphan"
run   "$START" --dir "$HOME/projects/repoA" repoGH-1 --no-launch
is    "lane-start does not refuse a lane over an orphan" "$rc" 0
has   "…it reports it with Amendment 6(d)'s act, which is the real one" "$err" "retire it: kill $G_OUT"
hasnt "…and never an \`end pid\` subcommand, because there is none" "$err" "end pid"
has   "…saying what it is" "$err" "orphaned holder, not a rival"
hasnt "…and never the rival refusal" "$err" "take repoGH-2"

# -- (g)(4) a REAL rival in another window is still a refusal -----------------
g_clear
write_record_g "$sessions_dir/g-rival.json" "$GH_ID" "$G_OUT" "$g_out_start" \
  interactive "othersess:@9.%9" "repoGH-1" derived 1000
run "$E" live-holder repoGH-1
has   "a live record in ANOTHER window is 'elsewhere'" "$out" "${US_SEP}elsewhere"
run   "$START" --dir "$HOME/projects/repoA" repoGH-1 --no-launch
is    "…and that is the one case that still refuses" "$rc" 2
has   "…naming the window that holds it" "$err" "is live in session"

# -- (g) window-session: the pane tree beats the newer record ----------------
#
# THE SIXTH COMMIT'S RULE, CORRECTED. `updatedAt` is a liveness HEARTBEAT, so
# the record that beats on last is not the record at the keyboard — in the real
# 2026-09-12 pair it was the idle companion. Identity decides; recency only
# separates two records of the same tier.
g_clear
write_record_g "$sessions_dir/g-ws-newer.json" "aaaa000c-9999-4000-8000-aaaa000c9999" "$G_OUT" "$g_out_start" \
  interactive "gwsess:@3.%3" "stale-but-chatty" derived 9999999999
write_record_g "$sessions_dir/g-ws-here.json"  "$GH_ID" "$G_PANE" "$g_pane_start" \
  interactive - "openrepoproject-45" derived 1000
run "$E" window-session "gwsess:@3"
is    "window-session: exit 0" "$rc" 0
has   "…the record in THIS pane's process tree wins" "$out" "$GH_ID"
hasnt "…even though the other names the window and updated far later" "$out" "aaaa000c-9999"

# …and asked about SOMEBODY ELSE'S window, neither the env var nor this pane's
# tree may answer: those two tests are about this window and nothing else.
run env CLAUDE_CODE_SESSION_ID="$GH_ID" "$E" window-session "farsess:@42"
is    "window-session about another window ignores this pane entirely" "$rc" 8

# -- (g) window-session skips a companion even if one names a window ---------
g_clear
write_record_g "$sessions_dir/g-ws-bg.json" "$GH_ID" "$G_OUT" "$g_out_start" \
  bg "gwsess:@3.%3" "repoGH-1" - 5000
run "$E" window-session "gwsess:@3"
is    "a bg record that names a window is still not what is IN it" "$rc" 8

g_clear
unset FAKE_TMUX_WINDOW FAKE_TMUX_PANE_PID
kill "$G_PANE" "$G_OUT" 2>/dev/null || :

# =========================================================================
# AMENDMENT 8, RULING (h) — THE WRITER NEVER BLOCKS THE ESTATE
#
# On 2026-09-12 at ~01:44Z an ssh `git-receive-pack` hung for five minutes AFTER
# its push had landed, with `lanes-edit.sh append-row-status` inside it holding
# the mutex the whole time. Every lane on Eagle was blocked until the ssh was
# killed by hand.
# -------------------------------------------------------------------------

H_LOCK="$WIP/lanes/.lanes-edit.lock"
# Handed to `LANES_GIT`, so it bounds ONLY the network calls — shadowing `git`
# on PATH would change every other call this suite makes.
cat > "$SANDBOX/hanggit" <<'FAKE'
#!/usr/bin/env bash
for a in "$@"; do
  if [ "$a" = push ]; then sleep 30; exit 0; fi
done
exec git "$@"
FAKE
cat > "$SANDBOX/peekgit" <<'FAKE'
#!/usr/bin/env bash
for a in "$@"; do
  if [ "$a" = push ]; then cat "$PEEK_LOCK/pid" > "$PEEK_OUT" 2>/dev/null || :; fi
done
exec git "$@"
FAKE
chmod +x "$SANDBOX/hanggit" "$SANDBOX/peekgit"

run env LANES_GIT="$SANDBOX/hanggit" LANES_GIT_TIMEOUT=2 "$E" append-row-status repoGH-1 "2026-09-12T20:00Z HUNGPUSH"
is    "a push that hangs past the timeout exits 3" "$rc" 3
has   "…saying so, with the budget it was given" "$err" "TIMED OUT after 2s"
has   "…and that the mutex is not held through it" "$err" "the mutex is released"
has   "…telling the writer a hung push may have LANDED before it looks again" "$err" "often means it LANDED"
is    "…the lock is released, not left for the next lane to age out" "$([ -d "$H_LOCK" ] && printf held || printf free)" "free"
has   "…and the edit is safe as a local commit" "$(git -C "$WIP" log --oneline -n1)" "HUNGPUSH"
has   "…which is the row, really written" "$(grep '^| `repoGH-1`' "$LANES")" "HUNGPUSH"

# The lock names its holder, and a lock whose holder is DEAD is stale at once —
# not ten minutes later, which is how long every other writer used to wait.
sleep 0.05 & H_DEAD=$!
wait "$H_DEAD" 2>/dev/null || :
mkdir -p "$H_LOCK"; printf '%s\n' "$H_DEAD" > "$H_LOCK/pid"
run "$E" append-row-status repoGH-1 "2026-09-12T20:01Z AFTERDEADLOCK"
is    "a lock whose holder is dead is taken over" "$rc" 0
has   "…with one line saying whose it was" "$err" "taking over"
has   "…and naming the pid that is gone" "$err" "(pid $H_DEAD) is gone"
has   "…the write then happens" "$(grep '^| `repoGH-1`' "$LANES")" "AFTERDEADLOCK"

# A lock whose holder is ALIVE is not stealable, and the writer records its own
# pid in it — proved from inside the critical section, by a `git` that reads the
# lock while the push is running.
PEEK_LOCK="$H_LOCK" PEEK_OUT="$SANDBOX/peek.pid" \
  env PEEK_LOCK="$H_LOCK" PEEK_OUT="$SANDBOX/peek.pid" LANES_GIT="$SANDBOX/peekgit" \
  "$E" append-row-status repoGH-1 "2026-09-12T20:02Z PEEK" >/dev/null 2>&1 || :
h_peek="$(cat "$SANDBOX/peek.pid" 2>/dev/null || printf '')"
is    "the lock carries the holder's pid while the holder is inside it" \
      "$(case "$h_peek" in ''|*[!0-9]*) printf no ;; *) printf yes ;; esac)" "yes"

mkdir -p "$H_LOCK"; printf '%s\n' "$LIVE_PID" > "$H_LOCK/pid"
h_t0=$SECONDS
timeout 3 "$E" append-row-status repoGH-1 "2026-09-12T20:03Z NEVER" >/dev/null 2>"$SANDBOX/h.err" || :
is    "a lock whose holder is ALIVE is not taken over" "$(grep -c 'taking over' "$SANDBOX/h.err" || :)" "0"
# …and a signal STOPS the writer. `trap cleanup EXIT INT TERM` ran the handler
# and then resumed the wait: measured, SIGTERM at 8s and the process still going
# at 56s, with the lock already released under it.
is    "…and a SIGTERM ends it there and then, instead of resuming the wait" \
      "$(( SECONDS - h_t0 < 15 ))" "1"
rm -rf "$H_LOCK"

# ------------------------------------------------------- nothing real touched
#
# The check is that the suite CREATED nothing here, which is not the same as
# this directory being empty: `lanes/log/` carries real lanes' logs on `main`
# now, and asserting a count of zero failed on the checkout's own committed
# records rather than on anything the suite did. The list is taken before the
# first case runs (SRC_LOG_BEFORE, at the top) and compared with the list after
# the last one.
is   "the suite never created a log outside the sandbox" \
     "$(ls "$REAL_WS/lanes/log" 2>/dev/null | grep -c '^repo[A-Z]' || :)" 0
is   "the suite never wrote the real register" \
     "$(grep -c '^| `repo[A-Z]' "$REAL_WS/lanes/LANES.md" 2>/dev/null || :)" 0
# NEVER VACUOUS, whatever this host has. The two above compare the operator's
# own workspace with itself and degrade to a true statement about nothing on a
# CI runner that has no workspace at all; this one asserts the positive — the
# logs the suite DID create are inside the sandbox, under the workspace the
# sandbox's own workspace.yaml names, and there is at least one of them.
is   "…and every log it did create is inside the sandbox workspace" \
     "$( [ "$(ls "$WIP/lanes/log" 2>/dev/null | grep -c .)" -gt 0 ] && echo yes || echo no )" "yes"

echo "----"
printf '%s passed, %s failed\n' "$pass" "$fail"
[ "$fail" = 0 ] || exit 1
exit 0
