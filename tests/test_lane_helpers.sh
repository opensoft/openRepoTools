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

for f in lane-start lane-end lanes-edit.sh link-estates lane lanes lane-rename; do
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
  p="$(sed -n -e 's/^path:[[:space:]]*//p' "$y" 2>/dev/null | head -n1)"
  p="${p%\"}"; p="${p#\"}"; p="${p%\'}"; p="${p#\'}"
  case "$p" in '~') p="$REAL_HOME" ;; '~/'*) p="$REAL_HOME/${p#'~/'}" ;; esac
  [ -n "$p" ] && [ -d "$p" ] || return 1
  printf '%s\n' "$p"
}
REAL_WS="$(real_ws_path 2>/dev/null || :)"
cleanup() {
  # Every long-lived fixture process, because they now outlive the whole run by
  # design (see `sleep 3000` below) and a suite that dies early must not leave
  # one behind. `kill` on an empty or already-reaped pid is a no-op here.
  [ -n "${LIVE_PID:-}" ] && kill "$LIVE_PID" 2>/dev/null
  [ -n "${G_PANE:-}" ] && kill "$G_PANE" 2>/dev/null
  [ -n "${G_OUT:-}" ] && kill "$G_OUT" 2>/dev/null
  [ -n "${GD_DUP:-}" ] && kill "$GD_DUP" 2>/dev/null
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
# THE ONE `LANES_*` SEAM THIS SUITE SETS RATHER THAN UNSETS, for the reason the
# line above unsets the rest (A9 Addendum 4, R-A9-13). Every seed row below
# spells the workstation column `Eagle` — 55 of them — and what those rows are
# for is the REGISTER'S READING of that column: which rows are this
# workstation's, which are another's, which crossing is a live lane here and
# which an orphan there. The host's own name is not under test in any of them,
# so taking it from the host made the whole file green on a workstation
# literally named Eagle and red on every other machine, GitHub's runners
# included: `lanes-edit.sh:438` reads `${LANES_WORKSTATION:-$(hostname -s)}`
# and `lane-start`/`lane-end` now read the same. Pinned here, the rows and the
# helpers agree wherever this runs.
#
# THE DEFAULT IS STILL UNDER TEST, one section from the end: `== the
# workstation seam ==` unsets this variable and asserts all three writers fall
# back to `hostname -s` — so pinning it here cannot hide a helper that stopped
# reading the host at all.
export LANES_WORKSTATION=Eagle

# `timeout(1)` IS GNU coreutils AND A STOCK macOS DOES NOT SHIP IT (A9 Addendum
# 4, R-A9-11). `lanes-edit.sh:810` bounds its network calls with it and reaches
# for it through `command -v`, so on such a host Amendment 8(h)'s bound is
# simply ABSENT: a push that hangs holds the mutex until it is killed. That is
# a real platform gap and it is recorded rather than shimmed — a fake `timeout`
# in `$SANDBOX/fakebin` would make these cases green on a host where the
# behaviour they assert does not happen. Read AFTER the fake bin is on PATH, so
# it answers for the PATH the cases actually run under.
HAVE_TIMEOUT=0; command -v timeout >/dev/null 2>&1 && HAVE_TIMEOUT=1
NO_TIMEOUT_WHY="no timeout(1) on this host, so lanes-edit.sh's Amendment 8(h) bound is absent here and there is nothing to assert"

pass=0; fail=0; skipped=0
ok()  { pass=$((pass + 1)); printf 'ok   %s\n' "$1"; }
bad() { fail=$((fail + 1)); printf 'FAIL %s\n       %s\n' "$1" "${2-}"; }
# A THIRD ANSWER, because two were not enough and the third was being given
# SILENTLY (A9 Addendum 4, R-A9-11). A case that cannot run on this host must
# say so: `timeout(1)` is not on a stock macOS, and the four cases that drive
# `lanes-edit.sh`'s hung-push bound were not passing there — two were red, and
# two more were GREEN AND VACUOUS, having asserted that a command which never
# ran printed nothing. A skip is printed, counted, and named in the footer.
skip() { skipped=$((skipped + 1)); printf 'skip %s\n       %s\n' "$1" "${2-}"; }
# AN ASSERTION THAT IS OWED TO A COMMIT LANDING IN ANOTHER REPOSITORY, NAMED
# RATHER THAN OMITTED. Amendment 11's tooling round was directed to build ON the
# `opensoft/brett-wip` hotfix of 2026-09-13 — step 3b's ownership fence, `--name`
# on every launch branch, and `log` refusing `unknown` — which `openRepoTools#24`
# (Amendment 9's adoption act 3, merged as `d4b5710`) ports into this tree, and NOT to write those three a second time. The tests
# that would catch each are written here anyway, because a test written after the
# fix is a test that never proved anything; until the port arrives they report
# PENDING with the exact expectation, and the moment it does they are ordinary
# assertions that pass or fail. PENDING is neither a pass nor a failure and the
# count is printed at the foot, so nothing is hidden by it.
pending_n=0; pending_list=""
pending() {   # <name> <got> <want> <what lands it>
  if [ "$2" = "$3" ]; then ok "$1"; return 0; fi
  pending_n=$((pending_n + 1))
  pending_list="${pending_list}  $1
      expected [$3], got [$2]
      lands with: $4
"
  printf 'PEND %s\n       expected [%s], got [%s]\n       lands with: %s\n' "$1" "$3" "$2" "$4"
}
is()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected [$3], got [$2]"; fi; }
# NO `tr` AND NO `cut`: THE ONLY PLACE A FAILURE IS EVER RENDERED MUST NOT
# DEPEND ON EITHER (A9 Addendum 4, R-A9-11), and this estate's messages are
# full of em dashes. Both spellings this line has already had were lost on the
# macOS job, in opposite directions:
#
#   `tr '\n' '~' | cut -c1-400`   BSD `tr` is not multibyte-aware and answers
#   (`9000e86`)                   `Illegal byte sequence` for an em dash,
#                                 printing NOTHING. A failure whose `got:` is
#                                 empty is a failure nobody can read.
#   `LC_ALL=C tr | LC_ALL=C cut`  fixes that, and then truncates BYTES — which
#   (`dcf1027`, `d3d59b5`)        split one em dash in half and cost the WHOLE
#                                 998-line transcript to a single
#                                 `UnicodeDecodeError` in the pytest wrapper.
#
# Bash does both jobs with no process at all: `${e//…}` swaps the newlines and
# `${e:0:400}` truncates by CHARACTER wherever the locale is a UTF-8 one. The
# macOS runner's is — that is not an assumption, it is what the first spelling
# proved: BSD `tr` reports `Illegal byte sequence` only in a multibyte locale,
# and it reported it there. And the guarantee does not rest on that reading
# anyway: `tests/test_lane_helpers_suite.py` decodes this transcript with
# `errors="replace"`, so the very worst a locale nobody expected can now do is
# put one `\ufffd` in one line, where it used to hide all 998.
#
# `$tilde`, NOT a literal `~`: bash TILDE-EXPANDS the replacement half of
# `${var//pattern/replacement}`, so a bare `~` there puts `$HOME` between every
# pair of lines — measured, and it made a one-line excerpt unreadable in
# exactly the failures it exists to render.
excerpt() { local e tilde='~'; e="${1//$'\n'/$tilde}"; printf '%s' "${e:0:400}"; }
has() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1" "expected to contain [$3]; got: $(excerpt "$2")" ;; esac; }
hasnt() { case "$2" in *"$3"*) bad "$1" "did NOT expect [$3]; got: $(excerpt "$2")" ;; *) ok "$1" ;; esac; }
# lane-start mints a fresh uuid for a NEW session, so its launch line carries a
# value no test can predict. `launch_of` removes just that pair, leaving the
# rest of the command line exactly comparable; `minted_of` returns the uuid.
UUID_RE='[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
launch_of() { printf '%s' "$1" | sed -E "s/ --session-id $UUID_RE//"; }
minted_of() { printf '%s' "$1" | grep -oE -- "--session-id $UUID_RE" | head -n1 | awk '{print $2}'; }

rc=0; out=""; err=""
run() { out="$("$@" 2>"$SANDBOX/stderr")"; rc=$?; err="$(cat "$SANDBOX/stderr")"; }

# THIS SUITE'S CLOCK, AND IT IS PORTABLE (A9 Addendum 4, R-A9-11). Ten fixture
# stamps below are written relative to now, and `date -u -d '-5 hours'` is
# GNU-only: BSD `date` — macOS's, and this file RUNS on the macOS job, because
# obligation 4's gate is a run gate by design — answers `illegal option -- d`
# and prints its usage, which is what every one of those ten used to get. BSD
# spells the same arithmetic `-v-5H`, so the adjustments are written HERE in
# that spelling, once, and translated for GNU: `utc_at -3H -26S` is three hours
# and twenty-six seconds ago on either. GNU is asked first, because it is what
# every lane workstation runs.
#
# `ua_bsd` is declared and assigned on separate lines because `local x=()` is
# not something bash 3.2 — the bash this file is parsed by on that runner — can
# be relied on to take.
utc_at() {   # <+|-><n><H|M|S> …
  local ua_a ua_n ua_unit ua_gnu=""
  local ua_bsd; ua_bsd=()
  [ $# -gt 0 ] || { echo "utc_at: needs at least one <+|-><n><H|M|S>" >&2; return 1; }
  for ua_a in "$@"; do
    ua_n="${ua_a%?}"; ua_unit="${ua_a#"$ua_n"}"
    case "$ua_unit" in
    H) ua_unit=hours ;; M) ua_unit=minutes ;; S) ua_unit=seconds ;;
    *) echo "utc_at: '$ua_a' is not <+|-><n><H|M|S>" >&2; return 1 ;;
    esac
    ua_gnu="${ua_gnu:+$ua_gnu }$ua_n $ua_unit"
    ua_bsd+=("-v$ua_a")
  done
  date -u -d "$ua_gnu" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null ||
    date -u "${ua_bsd[@]}" +%Y-%m-%dT%H:%M:%SZ
}

# ---------------------------------------------------------------- the fakes

cat > "$SANDBOX/fakebin/tmux" <<'FAKE'
#!/usr/bin/env bash
# AMENDMENT 11 — THIS FAKE NOW ANSWERS A TARGETED READ, because clause (h)'s
# `window-lane` is built on one: `tmux display-message -p -t <ref> '#{window_id}'`
# is the LIVENESS FENCE itself — a record whose window is gone names a window
# somebody else's `:0` may since have been given, and matching a dead ref is how
# a lane binds to a stranger's pane. A fake that answered every ref would make
# every one of those cases vacuous.
#
#   $FAKE_TMUX_WINDOWS   the workstation's live windows, one per line,
#                        `<session>:<index><TAB><@id><TAB><name>`. A ref that is
#                        in no line RESOLVES NOTHING and the fake exits 1,
#                        exactly as tmux does for a window that is gone.
#
# The untargeted reads keep their old seams and DERIVE the two new formats from
# `$FAKE_TMUX_WINDOW`, so every case written before Amendment 11 goes on
# describing one window rather than three variables that could disagree.
#
# AMENDMENT 12 ADDS TWO COLUMNS AND TWO FORMATS, both optional and both inert
# for every line written before it. The columns are `<TAB><%pane><TAB><pane's
# current command>`; a targeted read now matches a `%pane` as well as a ref and
# an `@id`, because the lock types into a PANE. The formats are:
#
#   '#{session_name}'          Amendment 11(h)'s agreement rule, asked of an
#                              `@id`: tmux REUSES window ids, so a record's id
#                              resolving is not the record's window unless the
#                              session it resolves in is the one the record
#                              wrote down.
#   '#{pane_current_command}'  M1's condition on typing at all — `/rename` typed
#                              at a shell is a command that does not exist. It
#                              answers `claude` for a line that carries no fifth
#                              column, so every case written before this one
#                              describes a pane running claude, which is what
#                              they all were.
#
# AND `send-keys` IS LOGGED, exactly as `rename-window` always was: the lock and
# the offer's `no` are acts on a pane and this is how a case sees them.
case "${1-}" in
  display-message)
    shift
    fake_t=""; fake_f=""
    while [ $# -gt 0 ]; do
      case "$1" in
        -p) shift ;;
        -t) fake_t="${2-}"; shift 2 ;;
        *)  fake_f="$1"; shift ;;
      esac
    done
    if [ -n "$fake_t" ]; then
      fake_l="$(printf '%s\n' "${FAKE_TMUX_WINDOWS:-}" | awk -F'\t' -v t="$fake_t" '$1 == t || $2 == t || ($4 != "" && $4 == t) { print; exit }')"
      [ -n "$fake_l" ] || exit 1
      fake_sess="$(printf '%s' "$fake_l" | cut -f1)"
      fake_cmd="$(printf '%s' "$fake_l" | cut -f5)"
      case "$fake_f" in
        '#{window_id}')            printf '%s\n' "$(printf '%s' "$fake_l" | cut -f2)" ;;
        '#{window_name}')          printf '%s\n' "$(printf '%s' "$fake_l" | cut -f3)" ;;
        '#{session_name}')         printf '%s\n' "${fake_sess%%:*}" ;;
        '#{pane_current_command}') printf '%s\n' "${fake_cmd:-claude}" ;;
        *)                         printf '\n' ;;
      esac
      exit 0
    fi
    fake_w="${FAKE_TMUX_WINDOW:-testsess:@1}"
    case "$fake_f" in
      '#{session_name}:#{window_id}')    printf '%s\n' "$fake_w" ;;
      '#{session_name}:#{window_index}') printf '%s\n' "${fake_w%%:*}:${FAKE_TMUX_WINDOW_INDEX:-0}" ;;
      '#S:#I')                           printf '%s\n' "${fake_w%%:*}:${FAKE_TMUX_WINDOW_INDEX:-0}" ;;
      '#{window_id}')                    case "${fake_w#*:}" in @*) printf '%s\n' "${fake_w#*:}" ;; *) printf '%s\n' "${FAKE_TMUX_WINDOW_ID:-@1}" ;; esac ;;
      '#W'|'#{window_name}')
        # AMENDMENT 12 — AN OPT-IN STICKY RENAME, and it is opt-in because the
        # fake's `#W` has been a CONSTANT for every case written before it: a
        # `rename-window` that started changing the answer would rewrite the
        # premise of every case that renames and then reads it again. Under
        # `$FAKE_TMUX_RENAME_STICKS=1` the rename lands, which is what real tmux
        # does and what Amendment 12(h)'s offer needs: `lane-start`'s veto 2
        # reads `#W`, and after a `yes` this window really has been renamed.
        fake_n="${FAKE_TMUX_WINDOW_NAME:-claude}"
        if [ "${FAKE_TMUX_RENAME_STICKS:-0}" = 1 ] && [ -s "${FAKE_TMUX_NAME_FILE:-/nonexistent}" ]; then
          fake_n="$(cat "$FAKE_TMUX_NAME_FILE")"
        fi
        printf '%s\n' "$fake_n" ;;
      '#{pane_id}')                      printf '%s\n' "${FAKE_TMUX_PANE_ID:-}" ;;
      '#{pane_pid}')                     printf '%s\n' "${FAKE_TMUX_PANE_PID:-}" ;;
      *)                                 printf '\n' ;;
    esac ;;
  rename-window)
    printf 'rename-window %s\n' "${2-}" >> "${FAKE_TMUX_LOG:-/dev/null}"
    if [ "${FAKE_TMUX_RENAME_STICKS:-0}" = 1 ] && [ -n "${FAKE_TMUX_NAME_FILE:-}" ]; then
      printf '%s\n' "${2-}" > "$FAKE_TMUX_NAME_FILE"
    fi ;;
  send-keys)
    shift
    fake_st=""; fake_sk=""
    while [ $# -gt 0 ]; do
      case "$1" in
        -t) fake_st="${2-}"; shift 2 ;;
        *)  fake_sk="${fake_sk}${fake_sk:+ }$1"; shift ;;
      esac
    done
    printf 'send-keys -t %s %s\n' "$fake_st" "$fake_sk" >> "${FAKE_TMUX_LOG:-/dev/null}" ;;
  *) : ;;
esac
FAKE

cat > "$SANDBOX/fakebin/claude" <<'FAKE'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "${FAKE_CLAUDE_LOG:-/dev/null}"
FAKE

# A FAKE `gh`, AND IT MAKES THIS SUITE SAFER RATHER THAN LOOSER (Copilot round 7
# on openRepoTools#81). `LANES_NO_GITHUB=1` below stops every `gh` call this
# helper would make, which is why there was no fake at all — and why Amendment
# 16(g)'s POST-COMMIT COMMENT, the one act of `rename-lane` that happens after
# the push, had no test: every case here switches it off. The fake is the way to
# test it without reaching anything, and note what it changes for the rest of the
# file: the fakebin is PREPENDED to `$PATH`, so until now a call that slipped
# past `LANES_NO_GITHUB` would have found the WORKSTATION'S OWN `gh`. It cannot
# now. Anything but the two comment forms `gh_comment` makes is a loud refusal.
cat > "$SANDBOX/fakebin/gh" <<'FAKE'
#!/usr/bin/env bash
# `gh issue comment <n> --repo <owner/repo> --body-file -` and its `pr` twin are
# the only calls this fake answers; the body arrives on stdin.
fake_gh_kind="${1-}"; fake_gh_verb="${2-}"; shift 2 2>/dev/null || :
case "$fake_gh_kind/$fake_gh_verb" in
  issue/comment | pr/comment) : ;;
  *)
    printf 'FAKE gh REFUSED: %s %s — this suite reaches no GitHub surface
'       "$fake_gh_kind" "$fake_gh_verb" >&2
    exit 90 ;;
esac
fake_gh_n="${1-}"; fake_gh_repo=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) fake_gh_repo="${2-}"; shift 2 ;;
    *) shift ;;
  esac
done
[ "${FAKE_GH_FAIL:-0}" = 1 ] && { printf 'FAKE gh: refusing on purpose
' >&2; exit 1; }
{ printf '=== %s %s %s %s
' "$fake_gh_kind" "$fake_gh_verb" "$fake_gh_repo" "$fake_gh_n"
  cat
  printf '
'
} >> "${FAKE_GH_LOG:-/dev/null}"
printf 'https://github.com/%s/issues/%s#issuecomment-%s
'   "${fake_gh_repo:-owner/repo}" "${fake_gh_n:-0}" "$$"
FAKE

chmod +x "$SANDBOX/fakebin/tmux" "$SANDBOX/fakebin/claude" "$SANDBOX/fakebin/gh"
export FAKE_TMUX_LOG="$SANDBOX/tmux.log" FAKE_CLAUDE_LOG="$SANDBOX/claude.log"
export FAKE_GH_LOG="$SANDBOX/gh.log"
: > "$FAKE_TMUX_LOG"; : > "$FAKE_CLAUDE_LOG"; : > "$FAKE_GH_LOG"
export TMUX="$SANDBOX/fake-tmux-socket,0,0"

# Amendment 7: no test may reach GitHub, whatever a case forgets to pass. The
# fake above is the second lock on the same door: this variable stops the call
# being made, and the fake stops the workstation's own `gh` being what answers
# it if a case switches the variable off on purpose — which exactly one does.
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
      "$SRC_DIR/link-estates" "$SRC_DIR/lane" "$SRC_DIR/lanes" \
      "$SRC_DIR/lane-rename" "$SRC_DIR/repos.tsv" "$OPENREPOTOOLS_BIN_DIR/"
chmod 755 "$OPENREPOTOOLS_BIN_DIR"/lane-start "$OPENREPOTOOLS_BIN_DIR"/lane-end \
          "$OPENREPOTOOLS_BIN_DIR"/lanes-edit.sh "$OPENREPOTOOLS_BIN_DIR"/link-estates \
          "$OPENREPOTOOLS_BIN_DIR"/lane "$OPENREPOTOOLS_BIN_DIR"/lanes \
          "$OPENREPOTOOLS_BIN_DIR"/lane-rename "$OPENREPOTOOLS_BIN_DIR"/repos.tsv
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

# 3000 SECONDS, AND THE NUMBER IS TIED TO THE RUNNER'S OWN BOUND (A9 Addendum
# 4, R-A9-11). This process IS the liveness fixture: every "a live holder …"
# case from here to the foot of the file asks whether it is still running, and
# `lane-start`'s own refusals name its pid. On macOS it is the ONLY thing they
# ask — there is no `/proc` there, so `live_start` below is empty and
# `lanes-edit.sh:1719`'s `procStart` half never runs, leaving `kill -0` on this
# pid as the whole of the answer.
#
# At `sleep 300` this fixture outlived the suite on Linux (136 s here, 229 s
# under pytest) and ran out of seconds INSIDE it on anything slower. The macOS
# job takes ~900 s for this file alone, so the fixture died a third of the way
# in and every liveness case after that point got a quiet, plausible-looking
# wrong answer. Measured, by starting it already reaped: 196 of 998. (It was
# not the largest cause of the 438 at `d3d59b5` — `lanes-edit.sh`'s padded `wc`
# was, and the two overlap — but it is the one that would have been left
# standing after that fix, which is the whole reason a suite fixes both at
# once.)
#
# The number must exceed `TIMEOUT_SECONDS` (2400) or the suite can outlive its
# own evidence on a runner slow enough to hit the bound; `cleanup` kills it on
# every exit path, and the last assertion in this file checks it was still
# running when the run ended.
sleep 3000 & LIVE_PID=$!
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
OLD_UTC="$(utc_at -5H)"
MID_UTC="$(utc_at -4H -30M)"
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

# EVIDENCE 7 MOVED THIS FROM 1 TO 2. A lane with no recorded checkout and none
# that can be PROVED is a refusal a person fixes with one flag, not an
# environment that failed — and as a `1` behind the launcher's `exec` it was a
# pane that said `[exited]` with the message scrolled past it. `restart` already
# spends 2 on the same fact (clause (i), `R-A11-20`).
run "$START" repoZZ 1 --no-launch
is   "a lane with no provable checkout REFUSES with 2, not the 1 that printed [exited]" "$rc" 2
has  "no such directory: names --dir" "$err" "--dir"
has  "…filled in as the act that RECORDS it" "$err" "lane-start --dir <path> repoZZ 1"
has  "…and says nothing was started" "$err" "nothing was started"

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
# AMENDMENT 13(a) — A NEW ROW IS BORN IN THE PHRASE, not with the bare word
# `STARTING` the cell used to open with: `<STATE> · <UTC> · <one line>`, so that
# no row ever exists outside the shape `set-row-state` is the only writer of.
a13_new="$(grep '^| `repoA-7`' "$LANES")"
has  "the new row's state cell is Amendment 13's phrase" "$a13_new" "| LIVE · 20"
has  "…whose line names the act that created it" "$a13_new" "lane-start on Eagle: row created |"
hasnt "…and never the bare word the cell used to open with" "$a13_new" "| STARTING |"
has  "the new row's session cell names the minted session" "$(grep '^| `repoA-7`' "$LANES")" "(minted by lane-start,"
hasnt "…so it no longer says 'pending'" "$(grep '^| `repoA-7`' "$LANES")" "pending — set by the session's first act"
has  "…and it is the very id claude was given" "$(grep '^| `repoA-7`' "$LANES")" "$REPOA7_SID"
has  "the new row names its workstation" "$(grep '^| `repoA-7`' "$LANES")" "$LANES_WORKSTATION / "
has  "the new row points at a handoff" "$(grep '^| `repoA-7`' "$LANES")" "handoffs/repoA/session-handoff-"
has  "the row write is its own commit" "$(git -C "$WIP" log --oneline -1 -- lanes/LANES.md)" "add row"
is   "the row write was pushed" "$(git -C "$WIP" rev-parse HEAD)" "$(git -C "$WIP" rev-parse origin/main)"

run "$START" --estate xFactory --dir "$HOME/projects/repoB" repoA 8 --no-launch
has  "--estate names the handoff directory" "$(grep '^| `repoA-8`' "$LANES")" "handoffs/xFactory/session-handoff-"

run "$START" repoA 1 --no-launch
is    "a free lane resumes THE ROW'S RECORDED SESSION, by id" "$out" "claude --name repoA-1 --resume $DEAD_ID"
hasnt "…and never by the ambiguous title" "$out" "--resume repoA-1"
has   "…saying it is the row's own transcript" "$err" "the row's current session is $DEAD_ID and its transcript is here"
has   "…having taken live-holder's 8 as the ANSWER it is: this lane is parked" "$err" "no live session holds repoA-1"
has  "a free lane appends a status, not a row" "$(git -C "$WIP" log --oneline -1 -- lanes/LANES.md)" "lane-start on"
# AMENDMENT 11 CLAUSE (c) — THE ROW STAMP'S TAIL STATES THE DIRECTORY AND THE
# WINDOW BESIDE WHAT IT DID. Its HEAD is unchanged (Amendment 8(d): the verb,
# the uuid and the lane), and the tail still says what actually happened, so a
# `--no-launch` run still ends `no launch` and never claims to have launched
# anything.
has  "the appended status says what it did — and a --no-launch run never says it launched (F-B5)" "$(grep '^| `repoA-1`' "$LANES")" ", no launch"
has  "…with clause (c)'s directory and window in the tail, for the person reading the row" "$(grep '^| `repoA-1`' "$LANES")" "; dir $HOME/projects/repoA; window "
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
is   "a recorded id with no transcript here falls back to the title" "$out" "claude --name repoA-11 --resume repoA-11"
has  "…naming the id it could not resolve" "$err" "$GHOST_ID has no transcript for this directory"
has  "…and warning that a title only filters the picker" "$err" "FILTERS THE PICKER"

# The cell is a history, oldest first, so the LAST id is the lane's current one.
run "$START" repoA 12 --no-launch
is    "the LAST id in the session cell is the one resumed" "$out" "claude --name repoA-12 --resume $NEW12_ID"
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
is   "a transcript titled '<lane> (2)' is still the lane's" "$out" "claude --name repoA-16 --resume repoA-16"
has  "…and the suffix is reported, not silently accepted" "$err" "that title carries a dedupe suffix"
has  "…with the retire act named" "$err" "retire the stale holders"

# An existing row with one readable id and a new session: the cell is made
# current automatically, so the NEXT start resumes by id.
run "$START" repoA 14 --no-launch
REPOA14_SID="$(minted_of "$out")"
is   "an existing row with a stale id starts a new session" "$(launch_of "$out")" "claude --name repoA-14"
has  "…and the session cell is stamped with the minted id, AFTER the old id's code span" "$(grep '^| `repoA-14`' "$LANES")" "harness \`$GHOST2_ID\` → harness \`$REPOA14_SID\`"
hasnt "…never inside it, which a replace at a bare-uuid anchor would do (F-B1)" "$(grep '^| `repoA-14`' "$LANES")" "\`$GHOST2_ID → "
# ITS OWN REGISTER COMMIT, AND THE ONE BEFORE THE STAMP (Copilot round 5 on
# openRepoTools#82): Amendment 8's rule is THE CELL FIRST, THEN THE STAMP — the
# stamp names a uuid, so the cell that carries it is written first — and this
# path used to do the opposite. Both commits are asserted, in that order.
has  "…in its own register commit" "$(git -C "$WIP" log --format=%s -- lanes/LANES.md | head -n2 | tail -n1)" "session cell: lane-start minted $REPOA14_SID"
has  "…with the state stamp committed after it, naming the same id" "$(git -C "$WIP" log --format=%s -n1 -- lanes/LANES.md)" "state · LIVE · STARTED by $REPOA14_SID"

# And the loop closes: run it again, and the id just written is resumed by id.
printf '{"type":"user"}\n' > "$tdir/$REPOA14_SID.jsonl"
run "$START" repoA 14 --no-launch
is   "the next start resumes exactly what the previous one recorded" "$out" "claude --name repoA-14 --resume $REPOA14_SID"

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
has  "--dry-run plans the exact resume" "$err" "PLAN exec claude --name repoA-12 --resume $NEW12_ID"

echo "== lane-end =="

run "$END" --help
is   "lane-end --help exits 0" "$rc" 0

run "$END" repoD-1
is   "an open LANDING is refused" "$rc" 2
has  "…naming what it found" "$err" "the last LANDING in its state cell"
has  "…and the fix" "$err" "set-row-state repoD-1"
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
has  "…and the state cell now reads RETIRED, in Amendment 13(a)'s phrase" "$(grep '^| `repoA-7`' "$LANES")" "| RETIRED · 20"
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
has  "…verbatim, and retired" "$(grep '^| `browser-ui-repair`' "$LANES")" "| RETIRED · 20"


echo "== Amendment 7: the per-lane object log =="

E="$OPENREPOTOOLS_BIN_DIR/lanes-edit.sh"
WS_S="${LANES_WORKSTATION:-$(hostname -s)}"
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
is   "a resumed lane still resumes by id" "$out" "claude --name repoA-1 --resume $DEAD_ID"
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
  printf 'CLAIMED — lane repoH-2, session %s@Raven, %s, opensoft/repoH#4\n' "$DEAD_ID" "$(utc_at -2M)"
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
LATE_UTC="$(utc_at +10M)"
EARLY_UTC="$(utc_at +5M)"
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
JUMP_LATE="$(utc_at -3H)"
JUMP_BACK="$(utc_at -3H -26S)"
JUMP_OLD="$(utc_at -5H)"
JUMP_OLDER="$(utc_at -5H -26S)"
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
# `LANES_SESSION` because repoW-3 has a LOG and no register ROW, so nothing else
# can answer what its transcript uuid is — and under R-A11 (e) a write with no
# uuid is refused rather than stamped `unknown`. Before that rule this scenario
# passed while appending `session unknown@Eagle` to an append-only log, which is
# the defect, uncaught, inside the suite that was meant to catch it.
run env LANES_LANE=repoW-3 LANES_SESSION="$DEAD_ID" "$E" claim "#6" --no-github
is   "a legacy home already on record is resolved when it is read" "$rc" 0
has  "…so its shorthand keys canonically too" "$(cat "$LOGD/repoW-3.md")" ", codeXfactory/codexFactory#6"
hasnt "…and the line it wrote carries a real uuid, never \`unknown\`" "$(cat "$LOGD/repoW-3.md")" "session unknown@"

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
# AMENDMENT 13(a) — THE COUNT AND THE PATH, NOT THE LIST. The line is one line
# and capped at 240 characters (ratified decision O1); a lane forced closed over
# eleven open objects named them in 300. The objects are in the ENDED line of
# the lane's own log, which is where this line now points.
has   "…while the register's line names the log it read, not the state cell" "$(grep '^| `repoX-1`' "$LANES")" "own object log still showed"
has   "…and names the log the objects are in, since the line itself is capped" "$(grep '^| `repoX-1`' "$LANES")" "they are in lanes/log/repoX-1.md"

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
is    "the title fallback resumes by title" "$out" "claude --name repoZT-1 --resume repoZT-1"
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
( LANES_WORKSPACE_ROOT="$CLONE2" LANES_LANE=repoZZ-1 "$E" set-row-state repoZZ-1 \
    "LANDING #8 · into repoZZ main, posted by the peer" ) >/dev/null 2>&1
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

# --- the alias table must not enter awk through `-v` (A9 Addendum 4, R-A9-11)
#
# `awk -v name=value` processes the value AS A STRING LITERAL, and a string
# literal cannot span lines. macOS's awk — one-true-awk, `awk version
# 20200816` on the runner — refuses one outright: `awk: newline in string … at
# source line 1`, exit 2, nothing on stdout. gawk and mawk accept it without a
# word. `who_landing` handed it the WHOLE repos.tsv alias table that way, one
# `<alias>\037<owner/repo>` per line, so on macOS the register half of `who
# --landing` produced nothing at all and every open LANDING in the estate read
# as `none open` — fourteen of that job's failures, the last group standing
# after four rounds, and, off CI, the estate's merge holds invisible on a
# workstation that runs macOS. Every `who --landing` that PASSED there was
# being answered by the lane's own object log, which is the secondary source.
#
# THIS IS THE ONE macOS DEFECT OF THIS ACT A LINUX BOX CAN PROVE FOR ITSELF,
# so it is proved here rather than bought for another twenty-minute round. The
# proxy refuses exactly what that awk refuses and hands everything else to the
# real awk, so it cannot make a case pass that would not pass on the platform;
# it is written into the sandbox, it is never on PATH for any other case, and
# it is never shipped. On a host whose awk already refuses (macOS itself) it
# changes nothing — the refusal simply happens one process earlier.
#
# The three behaviour cases below are the register's own mixed-spelling
# fixture, read back through the proxy: the first two were red on the macOS
# job by these exact names, and the third is the empty answer that made the
# other twelve red.
BSDAWK="$SANDBOX/awk-of-bsd"
mkdir -p "$BSDAWK"
LANES_TEST_REAL_AWK="$(command -v awk)"; export LANES_TEST_REAL_AWK
cat > "$BSDAWK/awk" <<'BSDAWKSHIM'
#!/usr/bin/env bash
# A LOCAL PROXY FOR one-true-awk's `-v`, NEVER SHIPPED. Its `setclvar` runs the
# value through `qstring`, which stops at a literal newline. Nothing else about
# this awk is imitated: every other call goes straight through.
awk_nl='
'
awk_next=0
for awk_arg in "$@"; do
  awk_val=""
  if [ "$awk_next" = 1 ]; then awk_val="$awk_arg"; awk_next=0
  else
    case "$awk_arg" in
      -v)   awk_next=1 ;;
      -v?*) awk_val="${awk_arg#-v}" ;;
    esac
  fi
  case "$awk_val" in
    *=*) case "${awk_val#*=}" in
           *"$awk_nl"*)
             printf 'awk: newline in string %s... at source line 1\n' \
               "${awk_val#*=}" >&2
             exit 2 ;;
         esac ;;
  esac
done
exec "${LANES_TEST_REAL_AWK:?no real awk recorded}" "$@"
BSDAWKSHIM
chmod +x "$BSDAWK/awk"

is    "the awk proxy refuses a many-line -v, as one-true-awk does" \
      "$(PATH="$BSDAWK:$PATH" awk -v t="$(printf 'x\ny')" \
         'BEGIN { print "TAKEN" }' 2>/dev/null; printf 'rc=%s' "$?")" "rc=2"
is    "…and hands a one-line -v to the real awk, unchanged" \
      "$(PATH="$BSDAWK:$PATH" awk -v t=kept 'BEGIN { print t }')" "kept"

run   env PATH="$BSDAWK:$PATH" "$E" who --landing Omnigent-Install
is    "who --landing exits 0 under an awk that refuses a many-line -v" "$rc" 0
has   "…and the register half still answers, so the hold is still reported" \
      "$out" "LANDING  opensoft/Omnigent-Install#63  lane repoZQ-4"
run   env PATH="$BSDAWK:$PATH" "$E" who --landing opensoft/openRepoShape
has   "…and the alias table still reached awk, so the LANDED is still placed" \
      "$out" "is on opensoft/Omnigent-Install"

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
# `LANES_SESSION` for the same reason as repoW-3 above: a peer lane has a log on
# origin/main and no row here, so R-A11 (e) refuses a write that cannot name a
# transcript uuid instead of writing `unknown` into a file nothing rewrites.
run env LANES_LANE=repoZR-1 LANES_SESSION="$ZR_ID" "$E" claim "#3" --no-github
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
has   "…and that is what it plans to resume" "$err" "PLAN exec claude --name repoZC-1 --resume $ZC2"
hasnt "…never the id this checkout's copy ends on" "$err" "$ZC1"
has   "…and the status it plans to append names the same id" "$err" "launching claude --name repoZC-1 --resume $ZC2"
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
is    "…resuming the id the PUBLISHED cell ends on" "$out" "claude --name repoZC-1 --resume $ZC2"
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
# AMENDMENT 11 CLAUSE (h) — `swapped` GAINS A FOURTH FIELD `<dir>` AND A FIFTH
# `<profile>`, and the tab-is-the-contract rule is what makes that safe: both
# readers of this output take the FIRST FIELD BEFORE THE FIRST TAB (the launcher
# at `claude-profile:548-554` and the `/lane-swap` skill at its step 1, each with
# the same comment saying so), so a fourth and a fifth break neither. These rows
# were written before clause (c), so both new fields are EMPTY — which is what
# every record on the estate looks like until adoption act 7 cuts each lane over
# at its own next start, and a reader that finds none says so rather than
# assuming one (Amendment 7(i)).
# AMENDMENT 17(b) ADDS A SIXTH AND A SEVENTH, `<agent>` and `<transcript>`, on
# the same argument the fourth and fifth were added on: the FIRST FIELD BEFORE
# THE FIRST TAB is the contract every reader takes, and a record written before
# an amendment carries its fields EMPTY rather than guessed. These rows were
# written before both amendments, so four of the seven are empty.
is    "…lane first, tab-separated, <lane><TAB><UTC><TAB><window><TAB><dir><TAB><profile><TAB><agent><TAB><transcript>" \
      "$(printf '%s\n' "$out" | head -n1)" "$(printf 'repoSW-1\t%s\tclaude-team-05b-20260912102132-2699:0\t\t\t\t' "$SW_OLD_UTC")"
is    "…MOST RECENTLY LANDED first, though its UTC is the older of the two" \
      "$(printf '%s\n' "$out" | head -n1 | cut -f1)" "repoSW-1"
is    "…and the lane whose UTC is later, having landed first, comes second" \
      "$(printf '%s\n' "$out" | sed -n 2p | cut -f1)" "repoSW-5"
is    "…every row carries exactly seven tab-separated fields" \
      "$(printf '%s\n' "$out" | awk -F'\t' 'NF != 7' | grep -c .)" 0
is    "…and the FIRST field before the first tab is still the lane, which is the contract both its readers take" \
      "$(printf '%s\n' "$out" | head -n1 | cut -f1)" "repoSW-1"
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
is    "…and the launch resumes the NEW id, not the one the cell used to end on" "$out" "claude --name repoHU-1 --resume $HW_NEW"
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
# The row above has now been stamped TWICE, and it carries `$HW_NEW` more than
# once: in its session cell, and in the Amendment 6(c) stamp the cell holds
# (`RESUMED by <uuid> …`). It used to be THREE times — one per stamp, because
# every stamp was APPENDED — which is the shape `openRepoProject-1`'s own row
# had on `origin/main`, measured 2026-09-12: three occurrences of the current
# uuid and three of the previous one. Amendment 13(a) REPLACES the cell on every
# write, so the stamps no longer accumulate and the count is two.
#
# TWO IS STILL NOT ONE, which is the whole of what this case is for: the
# whole-row anchor refuses on it exactly as it refused on three, and the act
# that can extend the session cell is therefore still the cell-scoped one.
hu_row="$(grep '^| `repoHU-1`' "$LANES")"
is    "two stamps later, the row carries that uuid twice — the cell and the one stamp it keeps" \
      "$(printf '%s' "$hu_row" | grep -o "$HW_NEW" | grep -c .)" 2
run   env LANES_LANE=repoHU-1 "$E" replace-in-row repoHU-1 "$HW_NEW" "$HW_NEW → harness nope"
is    "replace-in-row REFUSES it, and its whole-row rule is unchanged" "$rc" 2
has   "…counting the occurrences it found" "$err" "occurs 2 times"
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
# THE SESSION CELL IS A HISTORY AND THE STATE CELL IS NOT (Amendment 13(c) and
# (a)): the previous uuid stays exactly where Amendment 6(b) put it, in the
# session cell, while the stamp that named it has been REPLACED by this one. It
# used to be three occurrences — the cell plus two appended stamps.
is    "…the previous uuid stays in the session cell, which Amendment 13 leaves alone" \
      "$(grep '^| `repoHU-1`' "$LANES" | grep -o "$HW_NEW" | grep -c .)" 1
is    "…the row is still one line" "$(grep -c '^| `repoHU-1`' "$LANES")" 1
is    "…and the launch resumes the id the cell now ends on" "$out" "claude --name repoHU-1 --resume $HW_NEW2"
unset FAKE_TMUX_WINDOW
rm -f "$sessions_dir/live-harness2.json"

echo "== Amendment 11 hotfix: R-A11-1, --name on every branch, unknown refused =="

# ---- R-A11-1: A LIVE SESSION THAT BELONGS TO ANOTHER ROW IS NEVER TAKEN ----
#
# Evidence 2(b) on `brettheap/new-workstation#20`: `lane-start openXfactory-5`
# typed in lane `openRepoProject-1`'s window planned to resume openRepoProject-1's
# transcript AS openXfactory-5, and to put openRepoProject-1's uuid into
# openXfactory-5's session cell — the cell Amendment 6(b) resumes from, in a row
# every later reader trusts, through an append nothing rewrites. Step 3b fired on
# ANY live session in the typing window; WHOSE it was was never asked. Ratified
# as R-A11-1 (corrected, ownership alone) by Brett Heap 2026-09-13T18:05:29Z,
# verbatim "Ratify all four".
#
# THE FENCE IS THE REGISTER, NOT THE WINDOW'S NAME, and that is the correction's
# whole point. The three cases step 3b exists for — a `/clear`, a usage reset, a
# profile switch — all happen in a window the launcher has just made and still
# calls `claude` (step 4 renames it AFTERWARDS), carrying a uuid the harness has
# just minted, which no row names at all. Fencing on the name would refuse
# exactly those three and leave the cell-stamping dead, which is `RV-T1`'s
# finding against the withdrawn "and the row carries no transcript yet" conjunct.
# An id that some OTHER row already names is the one thing provably not this
# lane's, and that is what is refused.
XL_X="aaaa0011-1111-4000-8000-aaaa00111111"     # lane X's own recorded session
XL_Y="aaaa0011-2222-4000-8000-aaaa00112222"     # lane Y's session, live in the window
XL_FREE="aaaa0011-3333-4000-8000-aaaa00113333"  # a harness mint, in no row at all
printf '{"type":"user"}\n' > "$tdir/$XL_X.jsonl"
"$E" add-row "| \`repoXL-1\` | harness \`$XL_X\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoXL/x.md | ACTIVE |" >/dev/null 2>&1
"$E" add-row "| \`repoXL-2\` | harness \`$XL_Y\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoXL/y.md | ACTIVE |" >/dev/null 2>&1
write_record_ns "$sessions_dir/live-xl.json" "$XL_Y" "$LIVE_PID" "$live_start" "xlsess:@11.%11" "repoXL-2" "user" "busy"
xl_y_row_before="$(grep '^| `repoXL-2`' "$LANES")"
export FAKE_TMUX_WINDOW="xlsess:@11"
run   "$START" --dir "$HOME/projects/repoA" repoXL-1 --no-launch
is    "lane-start X typed in lane Y's window exits 0" "$rc" 0
has   "…having read Y's live session out of the window it was typed in" "$err" "this window's live session is $XL_Y"
has   "…and answering WHOSE it is from the register, not from the window's name" "$err" "the register says it is lane repoXL-2's, not repoXL-1's"
hasnt "…so Y's uuid reaches no cell of X's row at all" "$(grep '^| `repoXL-1`' "$LANES")" "$XL_Y"
is    "…the resume target stays X's OWN row uuid, never Y's transcript" "$out" "claude --name repoXL-1 --resume $XL_X"
is    "…and Y's row is left exactly as it was" "$(grep '^| `repoXL-2`' "$LANES")" "$xl_y_row_before"
hasnt "…with no line of X's log naming Y's session either" "$(cat "$LOGD/repoXL-1.md")" "$XL_Y"

# The POSITIVE case, and the one the correction rescued: the same window, the
# same script, but the live session's uuid is in NO row — the harness minted it
# at a /clear, a usage reset or a profile switch. Nothing contradicts ownership,
# so it IS taken and the cell is extended (Amendment 6(c)'s stamp).
rm -f "$sessions_dir/live-xl.json"
printf '{"type":"user"}\n' > "$tdir/$XL_FREE.jsonl"
write_record_ns "$sessions_dir/live-xl2.json" "$XL_FREE" "$LIVE_PID" "$live_start" "xlsess:@11.%11" "repoxl-42" "derived" "busy"
run   "$START" --dir "$HOME/projects/repoA" repoXL-1 --no-launch
is    "a live session NO row names is the harness's own mint, and is taken" "$rc" 0
has   "…the cell extended from the id it ended on, not replaced" \
      "$(grep '^| `repoXL-1`' "$LANES")" "harness \`$XL_X\` → harness $XL_FREE (transcript uuid; profile t1)"
is    "…and the launch resumes it, not the id the cell used to end on" "$out" "claude --name repoXL-1 --resume $XL_FREE"
unset FAKE_TMUX_WINDOW
rm -f "$sessions_dir/live-xl2.json"

# `session-lane` is the read that answers it — the hook's own `lane_of_session`,
# exposed for a second caller rather than implemented twice (R-A11-7).
run "$E" session-lane "$XL_Y"
is   "session-lane names the lane whose row's session cell carries the uuid" "$out" "repoXL-2"
is   "…exiting 0" "$rc" 0
run "$E" session-lane "aaaa0011-4444-4000-8000-aaaa00114444"
is   "…and 8 when no row's session cell names it, so a caller can tell none from could-not-read" "$rc" 8
run "$E" session-lane
is   "…64 on a usage error, like every other read in clause (h) (ruling 1)" "$rc" 64
is   "…and it writes nothing: no commit is made by a read" "$(git -C "$WIP" status --porcelain | wc -l | tr -d ' ')" 0

# ---- EVIDENCE 4: `--name <lane>` IS ON EVERY LAUNCH BRANCH, NOT ONE ---------
#
# The session NAME is the lane's messaging address (Amendment 2): `ListAgents`,
# `SendMessage`, `@<lane>` and the statusline all read the harness record's
# name. Measured on lane openRepoProject-1 2026-09-13 — the transcript carried
# `customTitle: openRepoProject-1`, set once by `/rename`, while every process
# that resumed it that day carried a DERIVED name (`openrepoproject-b9`, `-1e`,
# `-27`, `-45`), because only the new-session branch passed the flag. There are
# three launch branches and the rule is one: a launch names its session after
# the lane, or the lane has no address for the life of that session, and there
# is no API to rename a running one from inside.
NM_ID="aaaa0013-1111-4000-8000-aaaa00131111"
NM_GONE="aaaa0013-2222-4000-8000-aaaa00132222"
printf '{"type":"user"}\n' > "$tdir/$NM_ID.jsonl"
printf '{"type":"custom-title","customTitle":"repoNM-2","sessionId":"titled-nm"}\n' > "$tdir/titled-nm.jsonl"
"$E" add-row "| \`repoNM-1\` | harness \`$NM_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoNM/x.md | ACTIVE |" >/dev/null 2>&1
"$E" add-row "| \`repoNM-2\` | harness \`$NM_GONE\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoNM/y.md | ACTIVE |" >/dev/null 2>&1
run   "$START" --dir "$HOME/projects/repoA" repoNM-1 --no-launch
has   "branch 1, resume by id: the launch carries --name <lane>" "$(launch_of "$out")" "--name repoNM-1"
is    "…and it is the whole command, in the order lane-start builds it" "$(launch_of "$out")" "claude --name repoNM-1 --resume $NM_ID"
run   "$START" --dir "$HOME/projects/repoA" repoNM-2 --no-launch
has   "branch 2, the title fallback: it carries --name <lane> too" "$(launch_of "$out")" "--name repoNM-2"
is    "…beside the title that filters the picker" "$(launch_of "$out")" "claude --name repoNM-2 --resume repoNM-2"
run   "$START" --dir "$HOME/projects/repoA" repoNM-3 --no-launch
has   "branch 3, a new session: it always did, and still does" "$(launch_of "$out")" "--name repoNM-3"
is    "…which is the branch the other two were measured against" "$(launch_of "$out")" "claude --name repoNM-3"

# ---- R-A11 (e): `unknown` IS REFUSED BY THE WRITER, FROM ANY CALLER --------
#
# Amendment 7(b) makes an event's `session` field the transcript uuid and only
# that. Nothing checked it, and the literal is on `origin/main` in the
# append-only log four times, in two lanes — `lanes/log/codeXfactory-1.md` ×3 and
# `lanes/log/openxfactory-4-opendox-extraction.md` ×1. Three came from
# `log PAUSED` (a swap skill holding the uuid and not passing it) and ONE FROM
# `release`, which is why the gate is in `write_event` — the writer every one of
# `log`, `claim` and `release` goes through — and not in the `log` arm alone. It
# is the first test in that function, before the lock and before the log file is
# created, so a refusal leaves the checkout as it found it. The four lines
# already written are not rewritten and not deleted (Amendment 7(b), 7(i)).
UK_ID="aaaa0012-1111-4000-8000-aaaa00121111"
"$E" add-row "| \`repoUK-1\` | harness \`$UK_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoUK/x.md | ACTIVE |" >/dev/null 2>&1
env LANES_LANE=repoUK-1 LANES_SESSION="$UK_ID" "$E" log STARTED "lane:repoUK-1" '→' "home opensoft/repoUK; estate repoUK" >/dev/null 2>&1
un_before="$(cat "$LOGD/repoUK-1.md")"
un_head="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_LANE=repoUK-1 LANES_SESSION=unknown "$E" log OPENED "opensoft/repoUK#9"
is   "log refuses the literal \`unknown\` as a session" "$rc" 2
has  "…naming the field and the rule it answers to" "$err" "session field is the TRANSCRIPT UUID and only that (Amendment 7(b))"
has  "…saying why this value in particular" "$err" "no later line can correct any of them"
has  "…and naming the act that supplies a uuid" "$err" "lane-start --no-launch"
is   "…while writing nothing to the log" "$(cat "$LOGD/repoUK-1.md")" "$un_before"
is   "…and making no commit" "$(git -C "$WIP" rev-parse HEAD)" "$un_head"
run env LANES_LANE=repoUK-1 LANES_SESSION="session_015byFrZSopmRbUWNMYt1zEA" "$E" log OPENED "opensoft/repoUK#9"
is   "a PR-footer id is refused too: neither resumable nor liveness-checkable" "$rc" 2
has  "…and the refusal says which kind of id it was handed" "$err" "PR-footer id"
run env LANES_LANE=repoUK-1 LANES_SESSION="$UK_ID" "$E" log OPENED "opensoft/repoUK#9"
is   "…while a real transcript uuid writes the line" "$rc" 0
has  "…carrying that uuid in the session field" "$(cat "$LOGD/repoUK-1.md")" "session $UK_ID@"
hasnt "…and the lane's log carries no \`session unknown@\` anywhere" "$(cat "$LOGD/repoUK-1.md")" "session unknown@"

# `release` is the other half of the same defect, and one of the four lines on
# origin/main is a RELEASED. The gate is the writer, so it answers here too.
run env LANES_LANE=repoUK-1 LANES_SESSION=unknown "$E" release "opensoft/repoUK#9" "not mine after all"
is   "release refuses it as well — the gate is the writer, not the subcommand" "$rc" 2
hasnt "…leaving no RELEASED line behind" "$(cat "$LOGD/repoUK-1.md")" "RELEASED"

# And the second rung: with no LANES_SESSION at all, `session_for` no longer
# substitutes the literal — a row that records no uuid yields none, and the
# write is refused rather than stamped `unknown` for ever.
"$E" add-row "| \`repoUK-2\` | pending — set by the session's first act | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoUK/y.md | ACTIVE |" >/dev/null 2>&1
run env LANES_LANE=repoUK-2 "$E" log STARTED "lane:repoUK-2" '→' "home opensoft/repoUK; estate repoUK"
is   "a lane whose cell records no uuid is refused too, with no LANES_SESSION to save it" "$rc" 2
is   "…and no log file is created for it: the guard runs before the file does" \
     "$([ -f "$LOGD/repoUK-2.md" ] && printf present || printf absent)" absent

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
has   "…and the --no-launch tail behind it states what really happened" "$(grep '^| `repoA-1`' "$LANES")" "RESUMED by $DEAD_ID (lane repoA-1) — lane-start on $LANES_WORKSTATION: window renamed, no launch; dir "

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
is    "the title fallback resumes by title, the picker not yet run" "$out" "claude --name repoDW-1 --resume repoDW-1"
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
# $WIP` would fail `set-row-state` instead — and `lane-start` runs under
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
      "$(launch_of "$out")" "claude --name repoCF-3 --resume $DEAD_ID --dangerously-skip-permissions"

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

ss_hook='{"session_id":"%s","source":"%s","cwd":"/sandbox/projects/repoSS","hook_event_name":"SessionStart"}'
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
out="$(printf '{"session_id":"%s","cwd":"/sandbox"}' "$SS_CUR" | "$E" session-start 2>/dev/null)"; rc=$?
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
"$E" set-row-state repoSU-1 "LIVE · RESUMED by unknown (lane repoSU-1) — lane-start on Eagle: window renamed, no launch" >/dev/null 2>&1
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
#
# AND IT IS SPELLED TWO WAYS, because neither spelling is everywhere (A9
# Addendum 4, R-A9-11). A stock macOS has `shasum -a 256` and no `sha256sum` at
# all; this runner image happens to carry both, which is exactly the kind of
# fact a test must not depend on — with the digest missing, this function
# prints NOTHING and the two comparisons below compare the empty string with
# itself: green, and asserting no fact. `sort -z`'s `-z` is GNU-only and goes
# the same way — sorting the DIGEST LINES needs no NUL and is as deterministic.
# `xargs -r` goes because it is GNU-only and this `find` always names a file.
if command -v sha256sum >/dev/null 2>&1; then SHA256=(sha256sum); else SHA256=(shasum -a 256); fi
tree_of() {   # <checkout>
  local to_dir="$1"
  ( cd "$to_dir" && find . -path ./.git -prune -o -type f -print0 \
      | xargs -0 "${SHA256[@]}" | LC_ALL=C sort | "${SHA256[@]}" )
  return 0
}
# `stat -c` is GNU and `stat -f` is BSD, the same two-spelling rule, and
# `lanes-edit.sh:2969` already reads FETCH_HEAD's mtime both ways. Spelled `-c`
# only, this answered `none` on BOTH sides of the call on macOS and the
# assertion compared `none` with `none`.
mtime_of() { stat -c %Y -- "$1" 2>/dev/null || stat -f %m -- "$1" 2>/dev/null || printf 'none'; }
ss_tree_before="$(tree_of "$WIP")"
ss_refs_before="$(git -C "$WIP" for-each-ref --format='%(refname) %(objectname)')"
ss_head2_before="$(git -C "$WIP" rev-parse HEAD)"
ss_fh_before="$(mtime_of "$WIP/.git/FETCH_HEAD")"
export FAKE_TMUX_WINDOW_NAME=repoSS-1
out="$(printf "$ss_hook" "$SS_CUR" resume | PATH="$NONET:$PATH" "$E" session-start 2>"$SANDBOX/stderr")"; rc=$?
err="$(cat "$SANDBOX/stderr")"
is   "session-start exits 0 with a git that refuses every network call" "$rc" 0
is   "…having made NONE of them: no fetch, no ls-remote, no pull, no push" "$(cat "$SANDBOX/gitnet.log")" ""
has  "…and still printing the whole block, from the checkout as it last stood" "$out" "LANE repoSS-1 — handoff"
is   "…the working tree byte-identical either side of it" "$(tree_of "$WIP")" "$ss_tree_before"
is   "…every ref where it was, origin/main included" "$(git -C "$WIP" for-each-ref --format='%(refname) %(objectname)')" "$ss_refs_before"
is   "…HEAD where it was" "$(git -C "$WIP" rev-parse HEAD)" "$ss_head2_before"
is   "…and .git/FETCH_HEAD not even touched, which is what a fetch would move" "$(mtime_of "$WIP/.git/FETCH_HEAD")" "$ss_fh_before"
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
sleep 3000 & G_PANE=$!
g_pane_start="$(cut -d' ' -f22 "/proc/$G_PANE/stat" 2>/dev/null || printf '')"
sleep 3000 & G_OUT=$!
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
# AMENDMENT 18(h) MOVED THIS ONE'S EXIT CODE AND NOTHING ELSE IT SAYS, and the
# two rules meeting here are both still true of it. A `bg` record is still NOT A
# HOLDER — `live-holder` answers 8 one case above, nothing says the lane is live,
# and the rival refusal is still absent (Amendment 8, ruling (g)) — and that is
# a fact about the LANE. 18(h) is about the TRANSCRIPT: this run's next act is
# `claude --resume <the row's id>`, a live process already carries that file,
# and the clause says *"it never appends such an id to the row and never
# launches a second resume of it"* (ratified 2026-09-14T13:15:18Z as revision 4;
# opensoft/openRepoTools#39's own incident IS a resume of a transcript a live
# process held). Amendment 8(f)'s orphan sentence is not overturned by this and
# does not reach it either: it rules on *"a row's EARLIER session ids … still
# held by live but idle sessions"*, which nothing resumes; this is the id the
# row ENDS on, which is the one the next `lane-start` opens. The cure is 6(d)'s
# act through the tooling — `lane-end <lane> --retire <pid>`, which proves the
# process is this lane's duplicate and kills nothing — where 8(f) printed a bare
# `kill`, and #39 is the issue that asked for the difference.
run   "$START" --dir "$HOME/projects/repoA" repoGH-1 --no-launch
is    "…so it cannot refuse the LANE either — but its transcript is not resumed under one (18(h))" "$rc" 1
hasnt "…and nothing claims the lane is live" "$err" "is live in session"
has   "…the refusal being about the file two processes would write" "$err" "another live process already carries transcript $GH_ID"
has   "…and naming the retire act, never a kill" "$err" "lane-end repoGH-1 --retire <pid>"

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
# THE SAME LINE MOVED BY THE SAME CLAUSE, and Amendment 8(f)'s whole reading is
# still asserted below it: the orphan is REPORTED, named as "not a rival", given
# 6(d)'s act, and the rival refusal ("take repoGH-2") is still absent — the lane
# is NOT taken by it. What 18(h) stops is the line after that report, where this
# run used to go on and `--resume` the very transcript the orphan is holding.
run   "$START" --dir "$HOME/projects/repoA" repoGH-1 --no-launch
is    "lane-start does not refuse a LANE over an orphan — and does not resume the transcript it holds (18(h))" "$rc" 1
has   "…it reports it with Amendment 6(d)'s act, which is the real one" "$err" "retire it: kill $G_OUT"
hasnt "…and never an \`end pid\` subcommand, because there is none" "$err" "end pid"
has   "…saying what it is" "$err" "orphaned holder, not a rival"
hasnt "…and never the rival refusal" "$err" "take repoGH-2"
has   "…while the refusal it DOES make names the transcript, not the lane" "$err" "another live process already carries transcript $GH_ID"
has   "…and the retire act, which is 6(d)'s through the tooling" "$err" "lane-end repoGH-1 --retire <pid>"

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
# its push had landed, with a `lanes-edit.sh` row write inside it holding
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

run env LANES_GIT="$SANDBOX/hanggit" LANES_GIT_TIMEOUT=2 "$E" set-row-state repoGH-1 "LIVE · HUNGPUSH"
if [ "$HAVE_TIMEOUT" = 1 ]; then
  is    "a push that hangs past the timeout exits 3" "$rc" 3
  has   "…saying so, with the budget it was given" "$err" "TIMED OUT after 2s"
  has   "…and that the mutex is not held through it" "$err" "the mutex is released"
  has   "…telling the writer a hung push may have LANDED before it looks again" "$err" "often means it LANDED"
else
  skip  "a push that hangs past the timeout exits 3" "$NO_TIMEOUT_WHY"
  skip  "…saying so, with the budget it was given" "$NO_TIMEOUT_WHY"
  skip  "…and that the mutex is not held through it" "$NO_TIMEOUT_WHY"
  skip  "…telling the writer a hung push may have LANDED before it looks again" "$NO_TIMEOUT_WHY"
fi
is    "…the lock is released, not left for the next lane to age out" "$([ -d "$H_LOCK" ] && printf held || printf free)" "free"
has   "…and the edit is safe as a local commit" "$(git -C "$WIP" log --oneline -n1)" "HUNGPUSH"
has   "…which is the row, really written" "$(grep '^| `repoGH-1`' "$LANES")" "HUNGPUSH"

# The lock names its holder, and a lock whose holder is DEAD is stale at once —
# not ten minutes later, which is how long every other writer used to wait.
sleep 0.05 & H_DEAD=$!
wait "$H_DEAD" 2>/dev/null || :
mkdir -p "$H_LOCK"; printf '%s\n' "$H_DEAD" > "$H_LOCK/pid"
run "$E" set-row-state repoGH-1 "LIVE · AFTERDEADLOCK"
is    "a lock whose holder is dead is taken over" "$rc" 0
has   "…with one line saying whose it was" "$err" "taking over"
has   "…and naming the pid that is gone" "$err" "(pid $H_DEAD) is gone"
has   "…the write then happens" "$(grep '^| `repoGH-1`' "$LANES")" "AFTERDEADLOCK"

# A lock whose holder is ALIVE is not stealable, and the writer records its own
# pid in it — proved from inside the critical section, by a `git` that reads the
# lock while the push is running.
PEEK_LOCK="$H_LOCK" PEEK_OUT="$SANDBOX/peek.pid" \
  env PEEK_LOCK="$H_LOCK" PEEK_OUT="$SANDBOX/peek.pid" LANES_GIT="$SANDBOX/peekgit" \
  "$E" set-row-state repoGH-1 "LIVE · PEEK" >/dev/null 2>&1 || :
h_peek="$(cat "$SANDBOX/peek.pid" 2>/dev/null || printf '')"
# THE `case` IS HOISTED OUT OF THE `$( )`, and it has to be (A9 Addendum 4,
# R-A9-11). Bash 3.2's parser reads the `)` that closes a case PATTERN as the
# one that closes the command substitution, so this exact expression is a
# syntax error on macOS and nowhere else: the job answered `command
# substitution: line 3284: syntax error near unexpected token 'newline'` and
# the assertion then compared a fragment of THIS FILE'S OWN SOURCE against
# `yes`. Same test, one variable earlier.
case "$h_peek" in ''|*[!0-9]*) h_peek_ok=no ;; *) h_peek_ok=yes ;; esac
is    "the lock carries the holder's pid while the holder is inside it" \
      "$h_peek_ok" "yes"

mkdir -p "$H_LOCK"; printf '%s\n' "$LIVE_PID" > "$H_LOCK/pid"
h_t0=$SECONDS
# BOTH OF THESE ARE THE SUITE'S OWN USE OF `timeout`, and where there is none
# they were not merely red — they were GREEN AND MEANINGLESS. `timeout 3 …`
# failed as `command not found`, so `$SANDBOX/h.err` was empty, `grep -c`
# answered 0, the elapsed time was zero, and both assertions passed having
# tested nothing at all. The writer WAITS on a live lock by design, so with no
# bound available this case cannot be run at all rather than run unbounded and
# hang the suite behind its own fixture.
if [ "$HAVE_TIMEOUT" = 1 ]; then
  timeout 3 "$E" set-row-state repoGH-1 "LIVE · NEVER" >/dev/null 2>"$SANDBOX/h.err" || :
  is    "a lock whose holder is ALIVE is not taken over" "$(grep -c 'taking over' "$SANDBOX/h.err" || :)" "0"
  # …and a signal STOPS the writer. `trap cleanup EXIT INT TERM` ran the handler
  # and then resumed the wait: measured, SIGTERM at 8s and the process still going
  # at 56s, with the lock already released under it.
  is    "…and a SIGTERM ends it there and then, instead of resuming the wait" \
        "$(( SECONDS - h_t0 < 15 ))" "1"
else
  skip  "a lock whose holder is ALIVE is not taken over" "$NO_TIMEOUT_WHY"
  skip  "…and a SIGTERM ends it there and then, instead of resuming the wait" "$NO_TIMEOUT_WHY"
fi
rm -rf "$H_LOCK"

# =========================================================================
# #32 — `commit_push` NAMES THE ATTEMPT THAT ACTUALLY LANDED, NEVER AN
# EARLIER ONE ORIGIN HAS SINCE OVERTAKEN.
#
# Observed on Eagle, three to four times in one hour on 2026-09-13/14 while
# several lanes wrote the register concurrently: `set-row-state` /
# `append-line` printed "rebase conflict on origin/main — nothing was
# pushed" for a commit that WAS on origin by the time anyone read the line —
# carried out by the very next lanes-edit.sh write through this same shared
# checkout, which pulls this dangling local commit onto its own and pushes
# both together. A caller who trusted "nothing was pushed" and redid the
# write wrote a duplicate line (issue #32). The second clone plays the peer
# that moves origin between this invocation's own commit and its push,
# exactly as it does for the lost-claim race above.
#
# THIS SANDBOX'S OWN CHECKOUT IS ALREADY DIRTY, from the rejectgit cases
# above (a stamp whose push or pull was faked to fail leaves its commit
# local, and the fixture files those cases wrote are still uncommitted
# where their own act never got to commit them) — real content, and none of
# it this section's. `dirty_elsewhere` would read it as "someone else's
# uncommitted file" and route every case below through Amendment 5(d)'s
# skip-the-pull branch instead of the rebase this section means to exercise,
# so it is committed first, exactly as its own author would.
# -------------------------------------------------------------------------
if [ -n "$(git -C "$WIP" diff --name-only 2>/dev/null)" ]; then
  git -C "$WIP" add -u -- .
  git -C "$WIP" commit -q -m "fixture cleanup: commit content earlier cases left uncommitted, before the #32 race/conflict cases"
  git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
  git -C "$WIP" push -q origin main
fi
git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
RC_ID="aaaa0005-c0c0-4000-8000-aaaa0005c0c0"
"$E" add-row "| \`repoRC-1\` | harness \`$RC_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoRC/x.md | ACTIVE |" >/dev/null 2>&1

# -- a race a LATER attempt wins: not a conflict, and the message must name
#    the attempt that actually pushed, never attempt 1's rejection — and the
#    retry must not write the row's own text twice.
RACE_FLAG="$SANDBOX/race-peer-landed"
rm -f -- "$RACE_FLAG"
cat > "$SANDBOX/racegit" <<FAKE
#!/usr/bin/env bash
# Plays the second workstation, landing its own commit in the exact window
# the retry loop exists for: after this attempt's own pull --rebase has
# already succeeded and just before its push, so the push is rejected and
# the NEXT attempt's own pull --rebase is what actually meets the peer.
for a in "\$@"; do
  if [ "\$a" = push ] && [ ! -e "$RACE_FLAG" ]; then
    touch "$RACE_FLAG"
    git -C "$CLONE2" pull -q --rebase origin main >/dev/null 2>&1
    printf 'CLAIMED — lane repoH-2, session %s@Raven, %s, opensoft/repoH#92\n' \
      "$DEAD_ID" "\$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$CLONE2/lanes/log/repoH-2.md"
    git -C "$CLONE2" add -- lanes/log/repoH-2.md
    git -C "$CLONE2" commit -q -m "LOG(repoH-2@Raven): lands between this attempt's pull and its push"
    git -C "$CLONE2" push -q origin main >/dev/null 2>&1
  fi
done
exec git "\$@"
FAKE
chmod +x "$SANDBOX/racegit"

run env LANES_GIT="$SANDBOX/racegit" "$E" set-row-state repoRC-1 "LIVE · RACE-RETRY-WINS"
is    "a peer landing between this attempt's pull and its push still exits 0" "$rc" 0
has   "…the message names attempt 2, the one that actually pushed" "$err" "pushed origin/main (attempt 2)"
hasnt "…never claiming attempt 1 pushed it" "$err" "pushed origin/main (attempt 1)"
is    "…and the retry writes the row's text once, never twice" "$(grep -c 'RACE-RETRY-WINS' "$LANES")" 1

# -- a race the rebase truly cannot resolve: the peer rewrote the SAME row.
#    `rebase --abort` must leave the tree clean, the message must say so
#    truthfully, and — because a write that runs after this one carries the
#    dangling commit out regardless of what conflicted here — it must say to
#    LOOK before resetting or redoing anything, the same rule RV-B3 took for
#    the handoff stamp's own push in `lane-start`.
git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null
PC_LINE="$(grep -n '^| `repoRC-1`' "$CLONE2/lanes/LANES.md" | head -n1 | cut -d: -f1)"
PC_ROW="$(sed -n -e "${PC_LINE}p" "$CLONE2/lanes/LANES.md")"
PC_TMP="$(mktemp -d)/pre"
cat -- "$CLONE2/lanes/LANES.md" > "$PC_TMP"
{ [ "$PC_LINE" -gt 1 ] && head -n "$((PC_LINE - 1))" -- "$PC_TMP"
  printf '%s\n' "${PC_ROW%|}· PEER-CONFLICT |"
  tail -n "+$((PC_LINE + 1))" -- "$PC_TMP"
} > "$CLONE2/lanes/LANES.md"
git -C "$CLONE2" add -- lanes/LANES.md
git -C "$CLONE2" commit -q -m "LANES(repoRC-1@Raven): peer rewrites the same row"
git -C "$CLONE2" push -q origin main

run "$E" set-row-state repoRC-1 "LIVE · OURS-CONFLICT"
is    "a peer's rewrite of the SAME row is a real conflict: exit 3" "$rc" 3
has   "…REBASE CONFLICT is still named" "$err" "REBASE CONFLICT on origin/main"
has   "…the abort runs and says the tree is clean" "$err" "rebase ABORTED — the worktree is clean and NOT mid-rebase"
is    "…and it really is clean" "$(git -C "$WIP" status --porcelain | grep -c .)" 0
has   "…told to fetch before resetting or redoing anything" "$err" \
      "fetch origin main || echo FETCH-FAILED"
has   "…and STOP named for a FAILED fetch too, never treated as leave to redo" "$err" \
      "if that printed FETCH-FAILED, STOP and retry — a stale or unreachable origin proves nothing either way"

# Copilot's round-4 review of #50 (5203455553): the very peer write this
# recovery exists for carries a dangling commit by REBASING it onto a newer
# base — which the branch just above this one takes — and a rebase changes
# the commit's sha without changing its patch. `merge-base --is-ancestor
# $cp_sha …` (round 2's own fix) checks the OLD sha, so it can still answer
# "not-there" once the change is published under a new one. `git cherry`
# compares by PATCH, so it finds it either way; verified against a real bare
# repo for a peer-rebased commit (0, correctly ALREADY THERE — where
# `merge-base --is-ancestor` on the same sha answered "not-there"), a
# genuinely local-only one (1, correctly not-there), and a fetch against a
# bad remote (FETCH-FAILED, cherry never run against a stale ref).
has   "…checked by CONTENT (git cherry), never by a sha a peer's rebase can change" "$err" \
      "cherry origin/main"
cp_sha_printed="$(printf '%s\n' "$err" | grep -oE 'cherry origin/main [0-9a-f]{7,40}' | head -n1 | awk '{print $3}')"
is    "…naming a real local commit to check, not a placeholder" \
      "$([ -n "$cp_sha_printed" ] && printf 'has-sha' || printf 'MISSING')" "has-sha"
has   "…counting only the patches git cherry could not find upstream" "$err" \
      "grep -c '^+'"
has   "…the reset is now conditional on that look, not unconditional" "$err" \
      "only if it is not there: read back exactly what you wrote"
has   "…and the die itself is scoped to this attempt, never a permanent claim" "$err" \
      "not pushed by this attempt; a later write from this checkout may already carry it"
hasnt "…never the old unconditional claim an aborted pull cannot prove" "$err" \
      "rebase conflict on origin/main — nothing was pushed."
pc_fetch="$(printf '%s\n' "$err" | grep -n -- 'fetch origin main || echo FETCH-FAILED' | head -n1 | cut -d: -f1)"
pc_look="$(printf '%s\n' "$err" | grep -n -- 'cherry origin/main' | head -n1 | cut -d: -f1)"
pc_reset="$(printf '%s\n' "$err" | grep -n -- 'reset --hard origin/main' | head -n1 | cut -d: -f1)"
is    "…fetched, THEN checked by content, THEN reset — the same order RV-B3 pins" \
      "$([ -n "$pc_fetch" ] && [ -n "$pc_look" ] && [ -n "$pc_reset" ] && [ "$pc_fetch" -lt "$pc_look" ] && [ "$pc_look" -lt "$pc_reset" ] && printf 'ordered' || printf "fetch $pc_fetch, look $pc_look, reset $pc_reset")" "ordered"

# Copilot's review of #50 (5202640056), suppressed comment on lanes-edit.sh:1180:
# the gate above was attached only to the diagnostic `diff` line — a caller
# whose fetch/look just showed the commit already on origin was still told, by
# the next two unconditional lines, to reset and redo, which is the exact
# duplicate this PR exists to prevent. A single STOP between the look and the
# reset gates all three lines below it (diff, reset, redo) at once, the same
# job the existing "only if it is not there" qualifier does for the diff line
# alone.
has   "…and told to STOP there instead of resetting or redoing a landed commit" "$err" \
      "if that printed 0, STOP — reset or redo now would write it a second time."
pc_stop="$(printf '%s\n' "$err" | grep -n -- 'STOP — reset or redo now' | head -n1 | cut -d: -f1)"
is    "…the STOP sits between the look and the reset, gating both reset and redo" \
      "$([ -n "$pc_look" ] && [ -n "$pc_stop" ] && [ -n "$pc_reset" ] && [ "$pc_look" -lt "$pc_stop" ] && [ "$pc_stop" -lt "$pc_reset" ] && printf 'ordered' || printf "look $pc_look, stop $pc_stop, reset $pc_reset")" "ordered"

# Suite housekeeping: this conflict is real and stays real (the peer's row
# rewrite is still on origin), so nothing later inherits this section's own
# dangling commit — and nothing later finds $WIP behind the peer's push
# either, which every case below this one assumes it never is. Fully synced
# to the CURRENT origin/main (the abort's own fetch already has it), not
# merely one commit back from wherever HEAD happened to be.
git -C "$WIP" fetch -q origin main 2>/dev/null || :
git -C "$WIP" reset --hard origin/main >/dev/null 2>&1

# --------------------------------------- the pointer file, when it does NOT answer
#
# AMENDMENT 9(a): "Failing to find it is a refusal, never a guess." Six ways it
# can fail, each with its own sentence, and every one of them is exit 1 — the
# code `lanes-edit.sh` has always used for `registry not found` and the code the
# amendment quotes. Until these cases existed, six diagnoses were computed and
# every one was thrown away in a subshell: what a person actually saw was "no
# reason recorded", for all six, in all four helpers.
#
# THE YAML IS SAVED AND RESTORED around this block. Every case above it depends
# on the sandbox's own valid pointer file, and a test that broke it and walked
# away would take the rest of the suite with it.
WS_YAML="$AGENT_PROTOCOL_ROOT/workspace.yaml"
WS_YAML_SAVED="$SANDBOX/workspace.yaml.saved"
cp -- "$WS_YAML" "$WS_YAML_SAVED"

# SETS TWO VARIABLES; IT DOES NOT PRINT. A function's assignments survive into
# its caller, but a command substitution's do not — `msg="$(ws_refusal …)"`
# would run this in a SUBSHELL and take `$WS_RC` down with it, which is the
# exact defect these cases exist to pin in the helpers themselves.
WS_MSG=""; WS_RC=0
ws_run() {
  WS_MSG="$("$@" 2>&1 >/dev/null)"
  WS_RC=$?
}

FOREIGN="$SANDBOX/foreign"
git init -q -b main "$FOREIGN"
git -C "$FOREIGN" remote add origin "https://github.com/opensoft/not-your-wip.git"

for helper in lanes-edit.sh lane-start lane-end link-estates; do
  case "$helper" in
  lanes-edit.sh) args=(who --lane repoA-1) ;;
  lane-start)    args=(repoA 9) ;;
  lane-end)      args=(repoA-1) ;;
  # `--dry-run` rather than no argument at all: the refusal is reached before
  # anything is linked either way, and an EMPTY array under `set -u` is an
  # unbound-variable error on the bash 3.2 this repository still ships for.
  link-estates)  args=(--dry-run) ;;
  esac

  rm -f -- "$WS_YAML"
  ws_run "$helper" "${args[@]}"
  is   "$helper refuses with exit 1 when there is no workspace.yaml" "$WS_RC" 1
  has  "…and names the file that is missing" "$WS_MSG" "there is no $WS_YAML"
  has  "…and names the one command that writes it" "$WS_MSG" "openRepoTools wip init"

  printf 'path: %s\n' "$WIP" > "$WS_YAML"
  ws_run "$helper" "${args[@]}"
  is   "$helper refuses a workspace.yaml with no repository:" "$WS_RC" 1
  has  "…saying which key is missing" "$WS_MSG" "names no \`repository:\`"

  printf 'repository: %s\n' "$ORIGIN" > "$WS_YAML"
  ws_run "$helper" "${args[@]}"
  is   "$helper refuses a workspace.yaml with no path:" "$WS_RC" 1
  has  "…saying which key is missing" "$WS_MSG" "names no \`path:\`"

  { printf 'repository: %s\n' "$ORIGIN"; printf 'path: %s/nowhere\n' "$SANDBOX"; } > "$WS_YAML"
  ws_run "$helper" "${args[@]}"
  is   "$helper refuses a path: that is not a git checkout" "$WS_RC" 1
  has  "…saying so in those words" "$WS_MSG" "which is not a git checkout"

  { printf 'repository: %s\n' "$ORIGIN"; printf 'path: %s\n' "$FOREIGN"; } > "$WS_YAML"
  ws_run "$helper" "${args[@]}"
  is   "$helper refuses a path: that is a checkout of something ELSE" "$WS_RC" 1
  has  "…naming both repositories" "$WS_MSG" "is a checkout of"

  { printf 'repository: %s\n' "$ORIGIN"; printf 'path: %s/lanes\n' "$WIP"; } > "$WS_YAML"
  ws_run "$helper" "${args[@]}"
  is   "$helper refuses a path: that is a SUBDIRECTORY, not the root" "$WS_RC" 1
  has  "…naming the root it should have been" "$WS_MSG" "not the ROOT of that checkout"

  hasnt "$helper never prints \`no reason recorded\`" "$WS_MSG" "no reason recorded"
done

# AND IT NEVER GUESSES. With no pointer file at all, no helper falls back to a
# path derived from its own location — which is what Amendment 9(a) retired,
# and what an installed command in ~/.local/bin could not do anyway.
rm -f -- "$WS_YAML"
ws_run lanes-edit.sh who --lane repoA-1
hasnt "the refusal names no path derived from the command's own location" \
      "$WS_MSG" "$OPENREPOTOOLS_BIN_DIR/lanes"

cp -- "$WS_YAML_SAVED" "$WS_YAML"
is   "the sandbox's own pointer file is restored for the guards below" \
     "$(sed -n 's/^path:[[:space:]]*//p' "$WS_YAML" | head -n1)" "$WIP"

echo "== Amendment 11: the record's fields, and clause (h)'s reads =="

# THE SHAPE EVERY CASE BELOW IS ABOUT, in one place: a lane whose log carries
# clause (c)'s three sub-fields, and a live window table for the reads that
# fence on a window still existing.
A11_ID="bbbb0001-1111-4000-8000-bbbb00011111"
A11_ID2="bbbb0002-2222-4000-8000-bbbb00022222"
A11_DIR="$HOME/projects/repoA11"
mkdir -p "$A11_DIR"
# AND THE SPELLING `pwd -P` GIVES IT, which on macOS is not the same string:
# `$TMPDIR` there is under `/var`, a symlink to `/private/var`, so every case
# that asserts a path a command RESOLVED must assert the resolved one. `lane`
# resolves `--dir` ONCE, where the operator typed it, because it `cd`s and then
# hands the same string to a launcher that would resolve it a second time from
# somewhere else — so a `--dir` case compares against this and a case reading
# the RECORD's own path compares against `$A11_DIR`, which is never resolved.
# Asserting the sandbox's own spelling for a resolved path is asserting that
# the resolution did not happen, which is the one thing it must do; caught by
# `tests-macos` on #45, where the two `--dir` assertions were the only red.
# AFTER THE `mkdir`, because `cd` into a directory that does not exist yet
# falls back to the unresolved spelling and is the same defect written twice.
A11_DIR_R="$(cd -- "$A11_DIR" 2>/dev/null && pwd -P || printf '%s' "$A11_DIR")"
git init -q -b main "$A11_DIR"
git -C "$A11_DIR" remote add origin "https://github.com/opensoft/repoA11.git"
add_seed_row "| \`repoA11-1\` | harness \`$A11_ID\` → after /clear \`$A11_ID2\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA11/x.md | ACTIVE |"
add_seed_row "| \`repoA11-2\` | pending — set by the session's first act | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA11/y.md | ACTIVE |"
add_seed_row "| \`repoA11-3\` | harness \`$A11_ID\` | Raven / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA11/z.md | ACTIVE |"
{ printf '# lane repoA11-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoA11-1, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoA11-1 → home opensoft/repoA11; estate repoA11; dir %s; profile team-05a; window a11sess:0 @71\n' "$A11_ID" "$A11_DIR"
  printf 'PAUSED — lane repoA11-1, session %s@Eagle, 2026-09-12T10:00:00Z, lane:repoA11-1 → swap; window a11sess:0 @71; dir %s; profile team-05a; workstation Eagle\n' "$A11_ID2" "$A11_DIR"
} > "$LOGD/repoA11-1.md"
# A lane whose record was written before clause (c): no dir, no profile, no id.
{ printf '# lane repoA11-2 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoA11-2, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoA11-2 → home opensoft/repoA11; estate repoA11\n' "$A11_ID"
  printf 'PAUSED — lane repoA11-2, session %s@Eagle, 2026-09-12T10:30:00Z, lane:repoA11-2 → swap; window a11old:0; workstation Eagle\n' "$A11_ID"
} > "$LOGD/repoA11-2.md"
# The same window ref, recorded on ANOTHER workstation.
{ printf '# lane repoA11-3 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'PAUSED — lane repoA11-3, session %s@Raven, 2026-09-12T10:00:00Z, lane:repoA11-3 → swap; window a11sess:0 @71; dir /elsewhere/repoA11; profile team-09z; workstation Raven\n' "$A11_ID"
} > "$LOGD/repoA11-3.md"
# A directory containing a SPACE, written quoted — clause (c)'s one rule rather
# than its refusal.
{ printf '# lane repoA11-4 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoA11-4, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoA11-4 → home opensoft/repoA11; estate repoA11; dir "%s/my projects/x"; profile team-05a; window a11sess:0 @71\n' "$A11_ID" "$HOME"
} > "$LOGD/repoA11-4.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed Amendment 11 records"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

# The workstation's live windows, for every read that fences on one existing.
#   a11sess:0  is LIVE and still reports @71  — the record agrees with it
#   a11live:0  is LIVE and reports @200       — a ref reused since the record
#   a11gone:0  is in no line at all           — the window is gone
export FAKE_TMUX_WINDOWS="$(printf 'a11sess:0\t@71\trepoA11-1\na11live:0\t@200\tclaude\na11named:0\t@88\trepoA11-2\n')"

# ---------------------------------------------------------------- lane-dir
run "$E" lane-dir repoA11-1
is   "lane-dir exits 0 for a lane whose log records one" "$rc" 0
is   "…and prints the path the LAST lane-kind line carrying one names" "$out" "$A11_DIR"
run "$E" lane-dir repoA11-2
is   "lane-dir exits 8 for a lane started before clause (c) — no answer, not a failure" "$rc" 8
is   "…and prints no path a caller could mistake for one" "$out" ""
run "$E" lane-dir repoA11-4
is   "lane-dir exits 0 for a path written QUOTED because it contains a space" "$rc" 0
is   "…and hands it back whole, quotes stripped, rather than truncated at the space" "$out" "$HOME/my projects/x"
# `lane-profile` IS `lane-dir` ONE SUB-FIELD ALONG, and it exists so that
# `lane <name>` can learn a profile with ONE `git show` rather than through
# the listing, which must read every log on the workstation for its held-objects
# column — seventeen seconds on the live register, to answer one question about
# one lane, on the path a person types to get back to work.
run "$E" lane-profile repoA11-1
is   "lane-profile exits 0 for a lane whose log records one" "$rc" 0
is   "…and prints it" "$out" "team-05a"
run "$E" lane-profile repoA11-2
is   "lane-profile exits 8 for a lane started before clause (c)" "$rc" 8
is   "…printing nothing a caller could launch with" "$out" ""
run "$E" lane-profile
is   "lane-profile with no lane exits 64, like its sibling" "$rc" 64

run "$E" lane-dir
is   "lane-dir with no lane exits 64, its own usage code and never the dispatcher's 2" "$rc" 64
run "$E" lane-dir repoA11-1 repoA11-2
is   "…and 64 for a second argument, for the same reason" "$rc" 64

# A LOG THAT COULD NOT BE READ IS **1** AND NOT THE PRE-CUTOVER **8** (#26, the
# review of `c3ebcfe`, `lanes-edit.sh:3525`). `lane_payload_field` read the
# events inside the HERE-DOCUMENT that feeds its loop, where a command
# substitution's status is discarded outright, so an unreadable log arrived as no
# lines and left through `return 8` — the one code `restart`, `lane-start` and
# both skills are entitled to read as "this lane has not started under Amendment
# 11 yet" and to fall past. These two arms carry their siblings' `case` now.
#
# THE LOG IS MADE UNREADABLE FOR REAL rather than stubbed, because the defect is
# INSIDE this file and a stub of `$E` would not exercise it. `LANES_NO_GIT=1`
# forces the local branch of `lane_log_events` — with a remote ref present it
# reads `git show`'s stdout, where a file mode cannot fail — and `awk` then
# exits non-zero on the file it cannot open. Skipped for a root that can read it
# anyway.
if [ "$(id -u)" = 0 ]; then
  skip "a log that cannot be read is a refusal and not 'no record'" "running as root, which can read a mode-000 file"
else
  chmod 000 "$LOGD/repoA11-1.md"
  run env LANES_NO_GIT=1 "$E" lane-dir repoA11-1
  is   "a lane-dir whose log could not be READ exits 1, never the pre-cutover 8" "$rc" 1
  has  "…saying what that is NOT, in Amendment 7(d)'s words" "$err" "is NOT 'this lane has no recorded directory'"
  run env LANES_NO_GIT=1 "$E" lane-profile repoA11-1
  is   "…and its sibling the same, because a wrong profile is another account" "$rc" 1
  has  "…naming the read and the code it came back with" "$err" "lane-profile could not read lane repoA11-1's log"
  chmod 644 "$LOGD/repoA11-1.md"
  # …AND THE PRE-CUTOVER 8 IS UNTOUCHED, so nothing that used to fall through
  # refuses now: `repoA11-2` is the lane with no `dir` sub-field at all.
  run env LANES_NO_GIT=1 "$E" lane-dir repoA11-2
  is   "a readable log with no dir sub-field is still the contract's 8" "$rc" 8
  run env LANES_NO_GIT=1 "$E" lane-dir repoA11-1
  is   "…and a readable one still answers 0" "$rc" 0
  is   "…with the same path it always gave" "$out" "$A11_DIR"
fi

# ------------------------------------------------------------ session-lane
run "$E" session-lane "$A11_ID2"
is   "session-lane exits 0 for a uuid the register's session cell names" "$rc" 0
is   "…and prints that lane — the read Amendment 8(e)'s hook already made, exposed" "$out" "repoA11-1"
run "$E" session-lane "$A11_ID"
is   "…and answers for an EARLIER id in the same cell, which is a history and not an alternative" "$rc" 0
run "$E" session-lane "cccc0000-9999-4000-8000-cccc00009999"
is   "session-lane exits 8 for a uuid no row names" "$rc" 8
is   "…printing nothing" "$out" ""
# 64 AND NOT ADOPTION ACT 0'S 2 (A11 Addendum 4 ruling 1). `2` here is already
# spoken for: it is what a helper with no `session-lane` exits from the `*)`
# arm, which is every workstation until act 3's install arrives — and both of
# this read's callers fail CLOSED on anything but 0 or 8, so telling "install
# the helper" from "fix your call" is the whole of what they can report.
run "$E" session-lane
is   "session-lane with no uuid exits 64, like every other read in clause (h)" "$rc" 64
has  "…naming what it takes" "$err" "usage: session-lane <transcript-uuid>"
run "$E" session-lane "$A11_ID2" "$A11_ID"
is   "…and 64 for a second argument it does not take" "$rc" 64
has  "…saying it takes one" "$err" "takes one transcript uuid"
# AND THE OTHER `2` IS STILL THE OTHER `2`: an unknown subcommand, which is how
# a caller detects a helper predating the read it asked for.
run "$E" session-lane-that-does-not-exist "$A11_ID2"
is   "…while an unknown subcommand still exits 2, which is the OLD HELPER code" "$rc" 2
has  "…and says so in its own words rather than in its status" "$err" "unknown subcommand"
run "$E" session-lane "repoA11-1"
is   "…and a name that is not a uuid is simply no answer: no row's session cell can contain it" "$rc" 8

# ------------------------------------------------------------- window-lane
run "$E" window-lane "a11named:0"
is   "window-lane exits 0 where the WINDOW'S OWN NAME is a lane the register has a row for" "$rc" 0
is   "…which is clause (b)'s precedence 2 read through the same door" "$out" "repoA11-2"
run "$E" window-lane "@71"
is   "window-lane exits 0 for an <@id> a live record names" "$rc" 0
is   "…and prints the lane that record belongs to" "$out" "repoA11-1"
run "$E" window-lane "Eagle" "a11sess:0"
is   "…and 0 for the <session>:<index> where the window now holding it reports the recorded @id" "$rc" 0
is   "…the same lane" "$out" "repoA11-1"
# THE AGREEMENT RULE (A11 Addendum 2, `R-A11-8`/RV-T6). `a11live:0` exists NOW
# and reports @200; nothing recorded it. Existing-now is not enough on its own:
# a record naming `x:0 @97`, met from the window that has since taken `x:0` as
# @200, passes the existing-now test on its ref and would bind the lane to a
# STRANGER'S PANE with no question.
{ printf '# lane repoA11-5 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'PAUSED — lane repoA11-5, session %s@Eagle, 2026-09-12T10:00:00Z, lane:repoA11-5 → swap; window a11live:0 @97; dir %s; profile team-05a; workstation Eagle\n' "$A11_ID" "$A11_DIR"
} > "$LOGD/repoA11-5.md"
add_seed_row "| \`repoA11-5\` | harness \`$A11_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA11/w.md | ACTIVE |"
{ printf '# lane repoA11-6 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'PAUSED — lane repoA11-6, session %s@Eagle, 2026-09-12T10:00:00Z, lane:repoA11-6 → swap; window a11gone:0 @5; dir %s; profile team-05a; workstation Eagle\n' "$A11_ID" "$A11_DIR"
} > "$LOGD/repoA11-6.md"
add_seed_row "| \`repoA11-6\` | harness \`$A11_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA11/v.md | ACTIVE |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed Amendment 11 disagreement and dead-window records"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
run "$E" window-lane "a11live:0"
is   "window-lane REFUSES a record whose @id disagrees with the window now holding its ref" "$rc" 8
is   "…binding nothing, which is the whole of the fence" "$out" ""
run "$E" window-lane "a11gone:0"
is   "window-lane exits 8 for a ref that resolves to no window at all" "$rc" 8
run "$E" window-lane "@5"
is   "…and 8 for an <@id> tmux does not resolve, however plainly a record names it" "$rc" 8
# THE WORKSTATION SCOPING (`R-A11-8`/RV-T7): a `<session>:<index>` is a local
# fact about one machine, and repoA11-3's record spells exactly the same ref on
# Raven.
run "$E" window-lane "Raven" "a11sess:0"
is   "window-lane asked about Raven answers from Raven's records" "$rc" 0
is   "…and names Raven's lane, not this workstation's, for the very same ref" "$out" "repoA11-3"
run "$E" window-lane
is   "window-lane with no ref exits 64" "$rc" 64
run "$E" window-lane "Eagle"
is   "…and 64 where the one argument is neither an @id nor a <session>:<index>" "$rc" 64
has  "…saying which shapes it takes and that the workstation comes first" "$err" "window-lane [<workstation>] <ref>"

# ------------------------------------------------------------ last-session
run "$E" last-session repoA11-1
is   "last-session exits 0 for a lane whose cell names uuids" "$rc" 0
is   "…and prints the LAST one, which is what Amendment 6(b) resumes" "$out" "$A11_ID2"
run "$E" last-session repoA-13
is   "last-session reads a cell of ANY shape — this one holds only PR-footer ids" "$rc" 8
run "$E" last-session repoA11-2
is   "last-session falls to the LANE'S OWN LOG where the cell names no uuid" "$rc" 0
is   "…taking the session field of its last PAUSED or RESUMED line" "$out" "$A11_ID"
run "$E" last-session
is   "last-session with no lane exits 64" "$rc" 64

# -------------------------------------- swapped's fourth and fifth fields
run "$E" swapped Eagle
is   "swapped exits 0 with Amendment 11's records in the log" "$rc" 0
A11_ROW="$(printf '%s\n' "$out" | awk -F'\t' '$1 == "repoA11-1" { print; exit }')"
is   "…and the row's FOURTH field is the recorded directory" "$(printf '%s' "$A11_ROW" | cut -f4)" "$A11_DIR"
is   "…its FIFTH the recorded profile" "$(printf '%s' "$A11_ROW" | cut -f5)" "team-05a"
is   "…and its THIRD carries the window's two refs, <session>:<index> and <@id>" \
     "$(printf '%s' "$A11_ROW" | cut -f3)" "a11sess:0 @71"
A11_ROW2="$(printf '%s\n' "$out" | awk -F'\t' '$1 == "repoA11-2" { print; exit }')"
is   "a record written before clause (c) has an EMPTY fourth field rather than a guessed one" \
     "$(printf '%s' "$A11_ROW2" | cut -f4)" ""

# ----------------------------------------------------- the workstation name
#
# DECISION 8(d) AS CORRECTED BY `R-A11-14`. Evidence 6: `opensoft/brett-wip`
# `origin/main` carries SIX log lines whose workstation is a container id, in an
# append-only file, written by every writer inside that container. The VALUE is
# the workBenches launcher's to export (`LANES_WORKSTATION`); these helpers READ
# it; outside a container `hostname -s` stays the default; and INSIDE one with
# no value every WRITER refuses rather than substituting a placeholder.
A11_HOST="$(hostname -s 2>/dev/null || hostname)"
run "$E" workstation
is   "workstation exits 0" "$rc" 0
is   "…and the seam wins, printing the name this suite pinned" "$(printf '%s' "$out" | cut -f1)" "Eagle"
is   "…naming the rung that answered, so a reader can tell a configured name from a hostname" \
     "$(printf '%s' "$out" | cut -f2)" "seam"
run env -u LANES_WORKSTATION LANES_IN_CONTAINER=0 "$E" workstation
is   "outside a container with no value, the host answers — which is what the seam has defaulted to since Amendment 6" \
     "$(printf '%s' "$out" | cut -f1)" "$A11_HOST"
is   "…and says so" "$(printf '%s' "$out" | cut -f2)" "hostname"
run env -u LANES_WORKSTATION LANES_IN_CONTAINER=1 "$E" workstation
is   "inside a container with no value the READ still answers, because a read in front of every launch may not refuse" "$rc" 0
is   "…and names the case rather than the rung" "$(printf '%s' "$out" | cut -f2)" "container-unset"
has  "…saying on stderr which variable is missing and who sets it" "$err" "LANES_WORKSTATION"
# AND EVERY WRITER REFUSES THERE. One guard at the dispatcher, because `WS` is
# built into every event line and every commit subject this file writes.
run env -u LANES_WORKSTATION LANES_IN_CONTAINER=1 env LANES_LANE=repoA11-1 "$E" log RESUMED "lane:repoA11-1"
is   "a WRITER inside a container with no configured workstation REFUSES" "$rc" 2
has  "…naming the variable" "$err" "LANES_WORKSTATION"
has  "…and saying why a container id is not a workstation" "$err" "is the CONTAINER"
hasnt "…and writes nothing" "$(git -C "$WIP" log --format=%s -n1)" "RESUMED lane:repoA11-1"
run env -u LANES_WORKSTATION LANES_IN_CONTAINER=1 "$E" register-row repoA11-1
is   "…while a READ in the same container is untouched" "$rc" 0
run env -u LANES_WORKSTATION LANES_IN_CONTAINER=1 "$START" --dry-run repoA11 1
is   "lane-start refuses there too, BEFORE the row and before the log" "$rc" 2
has  "…in the same words, from the one place they are written" "$err" "LANES_WORKSTATION"
run "$E" workstation Eagle
is   "workstation takes no arguments, and says so with its own 64" "$rc" 64

# ------------------------------- clause (c): the writer's OWN `, ` backstop
#
# THE SECOND SEPARATOR, WHICH WAS IN NO WRITER AT ALL (F-X12). `write_event`
# refused a third ` — ` and a newline; `, ` divides the four FIELDS from each
# other, and the payload is the tail of the fourth, so a `, ` inside it reads
# back as fields no reader knows — in a file nothing ever rewrites. Measured
# against every line this estate has before the guard was written: of 111
# payloads in the 15 live lane logs, 0 carry `, ` and 0 carry `"`, while 76
# carry `; `.
# ON A LANE OF THEIR OWN, because two of these cases WRITE and what they write
# is read by the `lane-start` directory cases far below: pointed at
# `repoA11-1`, the quoted-path case left `dir "/a b/c"` as that lane's last
# recorded directory and three later assertions failed with `no such directory:
# /a b/c`. A fixture that changes what a later case reads is a fixture that has
# to be its own.
add_seed_row "| \`repoA11w-1\` | harness \`$A11_ID2\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA11/w.md | ACTIVE |"
{ printf '# lane repoA11w-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoA11w-1, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoA11w-1 → home opensoft/repoA11; estate repoA11\n' "$A11_ID2"
} > "$LOGD/repoA11w-1.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the clause (c) write cases their own lane"
git -C "$WIP" push -q origin main
run env LANES_LANE=repoA11w-1 "$E" log RESUMED "lane:repoA11w-1" '→' "swap; dir /a, b; workstation Eagle"
is   "the writer refuses a ', ' in the payload — clause (c)'s other separator" "$rc" 2
has  "…naming the four fields it would break" "$err" "session <uuid>@<ws>"
has  "…and the separator that is legitimate there" "$err" "Use a semicolon"
hasnt "…while writing nothing at all" "$(git -C "$WIP" log --format=%s -n1)" "RESUMED lane:repoA11w-1"
# AND IT IS THE PAYLOAD ONLY. The free text is everything after the SECOND
# ` — `, where the fields are already split, so prose commas are ordinary there
# — the estate's own log is full of them, and refusing them would refuse lines
# it legitimately writes.
#
# THE TWO CASES BELOW ARE THE FIRST IN THIS SUITE THAT MUST ACTUALLY WRITE AT
# THIS POINT, and the sandbox checkout is not clean here: the handoff cases far
# above leave four tracked DELETIONS behind, so `refuse_dirty_checkout` refused
# both with exit 2 and the guard under test was never reached. Committed first,
# exactly as the Amendment 11 `lane-start` cases below already do for the same
# reason — a fixture step, not a fix to anything under test.
git -C "$WIP" add -A >/dev/null 2>&1
git -C "$WIP" commit -q -m "commit pending handoff edits before the clause (c) write cases" >/dev/null 2>&1 || :
run env LANES_LANE=repoA11w-1 "$E" log RESUMED "lane:repoA11w-1" '→' "swap; workstation Eagle" "tick 8.4 landed, and 5.7a, 5.9a stay unheld"
is   "…while a comma in the FREE TEXT is ordinary prose and is written" "$rc" 0
has  "…exactly as it was given" "$(tail -n1 "$LOGD/repoA11w-1.md")" "landed, and 5.7a, 5.9a stay unheld"
# AND NOT THE `"`, BECAUSE CLAUSE (c) WRITES ONE. A path with a space is written
# QUOTED — that is what makes it one ref under 7(b) — so a `"` refusal in the
# whole-payload guard would refuse the shape the clause mandates.
run env LANES_LANE=repoA11w-1 "$E" log RESUMED "lane:repoA11w-1" '→' 'swap; dir "/a b/c"; workstation Eagle'
is   "…and a quoted path, which clause (c) requires for a space, still goes through" "$rc" 0
has  "…with both quotes intact" "$(tail -n1 "$LOGD/repoA11w-1.md")" 'dir "/a b/c"'


# ------------------ the `/restart` skill's own lines, RUN (F-X9, F-X10, F-X11)
#
# A SKILL IS PROSE NOTHING EXECUTES, which is the review's own F-X22: the rungs
# are each tested as reads and the LADDER is held only by its own text. So the
# one part of it that is arithmetic — rung 4's `<repo>` — is extracted FROM THE
# FILE and run here, against the names this estate really has. Not a copy: a
# copy is what would go on passing after the file drifted.
RSKILL="$SRC_DIR/skills/restart/SKILL.md"
skill_repo_of() {   # <lane> — evaluates the SKILL's own `tail=`/`case` block
  local sro_lane="$1" sro_snip sro_out
  sro_snip="$(awk '/^  tail="/,/^  esac$/' "$RSKILL")"
  [ -n "$sro_snip" ] || { printf 'NO SNIPPET IN %s\n' "$RSKILL"; return 1; }
  sro_out="$(lane="$sro_lane"; repo=""; eval "$sro_snip"; printf '%s' "$repo")"
  printf '%s' "$sro_out"
}
# THE LANE THE OLD LINE GOT WRONG, and it is in this register today: SPEC rev 2
# §0.8 lists `openxfactory-4-opendox-extraction`, for which `${lane%-*}` answered
# `openxfactory-4-opendox` — a directory `$PROJECTS_ROOT` does not have, so rung
# 4 handed `/restart` a `cd` target that cannot exist and the refusal below it
# fired for the wrong reason.
is "rung 4's <repo> leaves a lane with no position alone (F-X11)" \
   "$(skill_repo_of openxfactory-4-opendox-extraction)" "openxfactory-4-opendox-extraction"
is "…and still strips a real position" "$(skill_repo_of openRepoProject-1)" "openRepoProject"
is "…including a lettered one, which is a position too" "$(skill_repo_of repoX-5a)" "repoX"
is "…and a pre-rule name is its own repo" "$(skill_repo_of browser-ui-repair)" "browser-ui-repair"
# IT IS `lane-start`'S RULE AND NOT A SECOND ONE. `lane-start:565-578` is the
# WRITER of these names — `<repo>-<position>` with the position `[0-9]+[A-Za-z]?`,
# and `:577`'s `repo="${repo:-$LANE}"` for a name that has none — so a reader
# deriving a different `<repo>` from the same name would send `/restart` to a
# directory the writer never used.
hasnt "the skill no longer derives the directory with a bare \${lane%-*}" \
      "$(cat "$RSKILL")" 'dir="$PROJECTS_ROOT/${lane%-*}"'
# F-X10 — THE LITERAL THE WRITER REFUSES TO INVENT. `lane-start:1546-1560`:
# "inventing `unknown` for it would be the same defect clause (e) refuses in the
# session field", and it omits the sub-field instead. The skill wrote it into the
# one cell Amendment 6(b) resumes from.
hasnt "the skill invents no \`unknown\` profile (F-X10)" "$(cat "$RSKILL")" 'profile ${CLAUDE_PROFILE_NAME:-unknown}'
has   "…it appends the sub-field only where there is a value" "$(cat "$RSKILL")" 'CLAUDE_PROFILE_NAME:-}" ] && cell='
# F-X9 — THE WITHDRAWN RULING. `R-A11-12`: "Neither the window's name being the
# lane nor `live-holder` answering `here` is a condition for taking." The skill
# restated its twice-corrected predecessor two sections above the place it has
# it right.
hasnt "the skill no longer restates the withdrawn permission form (F-X9)" \
      "$(cat "$RSKILL")" "proves ownership by the window's"
has   "…and says what the vetoes actually do on the 4(c) path" \
      "$(cat "$RSKILL")" "takes the window's live session **unless a veto fires**"

# THE SKILL'S OWN FAIL-CLOSED FENCE, EXTRACTED AND RUN (#26's fail-closed
# family; Brett Heap, "Take it first, then land"). Six reads in this file
# collapsed every code into the ordinary case: `|| lane=""`, `|| dir=""`,
# `&& lane="$win_name"`, and one that ignored the status altogether. Amendment
# 7(d) gives `8` and `2` to the fall-through — no answer, and a helper predating
# the read — and everything else to a read that FAILED, which may not bind a
# window or write a stamp. `lread` is that rule, once, and these four cases run
# THE FILE'S OWN COPY of it against a helper in each state.
#
# IT SETS A VARIABLE RATHER THAN PRINTING, and that is load-bearing: a refusal
# inside `$( )` would kill only the substitution's subshell and the skill would
# carry on with an empty answer — the same trap `lanes-edit.sh:673-676` names
# for `row_line`.
rskill_fence="$(awk '/^lread\(\) \{/,/^\}$/' "$RSKILL")"
is   "the skill carries the fence its reads go through" \
     "$( [ -n "$rskill_fence" ] && printf yes || printf no )" "yes"
fence_probe() {   # <helper exit code> — runs the SKILL's own fence against it
  printf '#!/usr/bin/env bash\nprintf "ANSWER\\n"\nexit %s\n' "$1" > "$SANDBOX/fencehelper"
  chmod +x "$SANDBOX/fencehelper"
  ( L="$SANDBOX/fencehelper"; eval "$rskill_fence"
    v=unset; lread v "'a thing it is not'" some-verb 2>"$SANDBOX/fence.err"
    printf 'rc=%s v=[%s]' "$?" "$v" )
}
is   "an answer reaches the variable" "$(fence_probe 0)" "rc=0 v=[ANSWER]"
is   "…8 is NO ANSWER and falls to the next rung" "$(fence_probe 8)" "rc=0 v=[]"
is   "…2 is a helper predating the read and falls through too" "$(fence_probe 2)" "rc=0 v=[]"
is   "…and a read that FAILED stops the skill where it stands" "$(fence_probe 6)" ""
has  "…naming the read and the code it came back with" "$(cat "$SANDBOX/fence.err")" "some-verb\` failed (exit 6)"
has  "…and saying what that is NOT, in Amendment 7(d)'s words" "$(cat "$SANDBOX/fence.err")" "a read that failed is never an answer"

# #34 — THE FENCE'S OWN STDERR IS KEPT, MINUS THE ONE SENTENCE THIS READ ASKS
# FOR (Copilot's final round on #26, review 5194970614; the third site of the
# shape `lanes` and `restart` took at `29d3417`). `2>/dev/null` was written
# when the only thing on that stream was `LANES_NO_FETCH=1 — not fetching …`,
# on every local read — which is why the whole stream was silenced. Anything
# else there, on a read that still ANSWERED, used to be thrown away with it.
printf '#!/usr/bin/env bash\nprintf "LANES_NO_FETCH=1 — not fetching; reading origin/main as the ref already stands here\\n" >&2\nprintf "ANSWER\\n"\nexit 0\n' > "$SANDBOX/fencehelper"
chmod +x "$SANDBOX/fencehelper"
( L="$SANDBOX/fencehelper"; eval "$rskill_fence"
  v=unset; lread v "'a thing it is not'" some-verb 2>"$SANDBOX/fence2.err"
  printf 'rc=%s v=[%s]' "$?" "$v" ) > "$SANDBOX/fence2.out"
is   "the known no-fetch notice still reaches the variable, not the person" \
     "$(cat "$SANDBOX/fence2.out")" "rc=0 v=[ANSWER]"
is   "…the notice itself is dropped from stderr" "$(grep -c 'not fetching' "$SANDBOX/fence2.err")" 0

printf '#!/usr/bin/env bash\nprintf "session records for this workstation could not be read: permission denied\\n" >&2\nprintf "ANSWER\\n"\nexit 0\n' > "$SANDBOX/fencehelper"
chmod +x "$SANDBOX/fencehelper"
( L="$SANDBOX/fencehelper"; eval "$rskill_fence"
  v=unset; lread v "'a thing it is not'" some-verb 2>"$SANDBOX/fence3.err"
  printf 'rc=%s v=[%s]' "$?" "$v" ) > "$SANDBOX/fence3.out"
is   "a read that still ANSWERS is unaffected by its own other stderr" \
     "$(cat "$SANDBOX/fence3.out")" "rc=0 v=[ANSWER]"
has  "…and that other line reaches the person now, never dropped with the notice" \
     "$(cat "$SANDBOX/fence3.err")" "session records for this workstation could not be read"

# Copilot's round-1 review of #53 (5202775204): the fence's OWN `grep -v
# 'pattern' -- "$file"` puts the PATTERN before `--`, so a NON-PERMUTING
# getopt — BSD's, and every macOS shell — reads the pattern as the first
# OPERAND and then reads `--` itself as a second one, a FILENAME (the exact
# anti-pattern tests/test_repo_hygiene.py names for `sed` and `grep` alike,
# just on a file that hygiene test does not walk: SKILL.md is not in
# ALL_BASH). GNU grep hides this by PERMUTING; `POSIXLY_CORRECT=1` turns that
# off and reproduces the same failure right here, no macOS runner needed —
# measured against the unfixed line, this exact case printed `grep: --: No
# such file or directory` to stderr and prefixed the real line with the temp
# file's own name, because grep then believed there were two files.
( L="$SANDBOX/fencehelper"; eval "$rskill_fence"
  export POSIXLY_CORRECT=1
  v=unset; lread v "'a thing it is not'" some-verb 2>"$SANDBOX/fence3b.err"
  printf 'rc=%s v=[%s]' "$?" "$v" ) > "$SANDBOX/fence3b.out"
is   "…and under a NON-PERMUTING getopt (BSD's shape) the read still answers" \
     "$(cat "$SANDBOX/fence3b.out")" "rc=0 v=[ANSWER]"
is   "…the other line reaches the person UNPREFIXED, exactly as the helper wrote it" \
     "$(cat "$SANDBOX/fence3b.err")" "session records for this workstation could not be read: permission denied"
hasnt "…and grep itself never errors on \`--\` as though it were a missing file" \
     "$(cat "$SANDBOX/fence3b.err")" "No such file or directory"

# AND WITH NO CAPTURE FILE AT ALL, NOTHING IS FILTERED — silence in place of a
# stream this fence could not open would be the same defect the notice fix
# exists to correct, only quieter.
( L="$SANDBOX/fencehelper"; eval "$rskill_fence"
  mktemp() { return 1; }
  v=unset; lread v "'a thing it is not'" some-verb 2>"$SANDBOX/fence4.err"
  printf 'rc=%s v=[%s]' "$?" "$v" ) > "$SANDBOX/fence4.out"
is   "with no capture file, the read still answers" "$(cat "$SANDBOX/fence4.out")" "rc=0 v=[ANSWER]"
has  "…and everything on stderr reaches the person, filtered or not" \
     "$(cat "$SANDBOX/fence4.err")" "session records for this workstation could not be read"

# AND EVERY READ IN THE FILE GOES THROUGH IT: none of the four old shapes is left.
hasnt "no read is left on \`|| lane=\"\"\`" "$(cat "$RSKILL")" '2>/dev/null)" || lane=""'
hasnt "…nor on \`|| dir=\"\"\`" "$(cat "$RSKILL")" '2>/dev/null)" || dir=""'
hasnt "…nor on \`|| cell_last=\"\"\`" "$(cat "$RSKILL")" '2>/dev/null)" || cell_last=""'
hasnt "…nor on a bare && that cannot tell 8 from 1" "$(cat "$RSKILL")" '>/dev/null 2>&1 && lane="$win_name"'
has   "…and step 4 refuses a lane the register does not carry, before anything is written" \
      "$(cat "$RSKILL")" "this skill binds an existing lane and never creates one"

# AND THE DERIVED DEFAULT IS NOT A REFUSAL WHERE IT IS NOT THERE (#26, the
# review of `c3ebcfe`, `skills/restart/SKILL.md:152`). Step 3's fallback is a
# SECOND COPY of `lane-start`'s rung 4 and of nothing else; `708395e` gave that
# ladder rungs 5 and 6 for EVIDENCE 7 — the estate's `project.yaml` legs and a
# checkout named for the lane's recorded home, each proved by that directory's
# own `origin` — and the paragraph below the step has said since then that
# "step 5 resolves it and this step never fires". It fired first: the step
# refused for the very lane those rungs can prove. The block is EXTRACTED AND
# RUN, against a `$PROJECTS_ROOT` that has one of the two repositories.
rskill_dirblk="$(awk '/^if \[ -z "\$dir" \]; then/,/^fi$/' "$RSKILL")"
is   "the skill carries step 3's fallback block" \
     "$( [ -n "$rskill_dirblk" ] && printf yes || printf no )" "yes"
mkdir -p "$SANDBOX/proots/repoA11"
skill_dir_of() {   # <lane> — evaluates the SKILL's own step 3 fallback
  ( lane="$1"; PROJECTS_ROOT="$SANDBOX/proots"; dir=""
    eval "$rskill_dirblk"; printf '%s' "$dir" )
}
is   "step 3 derives \$PROJECTS_ROOT/<repo> where that checkout is there" \
     "$(skill_dir_of repoA11-1)" "$SANDBOX/proots/repoA11"
is   "…and derives NOTHING where it is not, so lane-start's rungs 5 and 6 are reached" \
     "$(skill_dir_of opsXfactory-5)" ""
has  "…which is why step 5 passes --dir only where step 3 has one" \
     "$(cat "$RSKILL")" 'lane-start --no-launch ${dir:+--dir "$dir"} "$lane"'
hasnt "…and never the unconditional flag, which put a GUESS at rung 1" \
      "$(cat "$RSKILL")" 'lane-start --no-launch --dir "$dir" "$lane"'


# ------------------------------------------- decision 8(e): a FORK is a DEFECT
#
# Evidence 6: an abandoned launch left a `--fork-session` daemon orchestrating
# the same plan, relaunching writers on the same branches and writing the lane's
# log under an id no row carries, while telling the interactive session it was
# the holder. A fork copies the parent's `custom-title` record, so its
# transcript says the lane's name while its id says something the row has never
# heard of — and that pair is the defect.
FORK_ID="dddd0001-f0f0-4000-8000-dddd0001f0f0"
fork_tdir="$HOME/.claude/projects/$(sanitize "/workspace")"
mkdir -p "$fork_tdir"
printf '{"type":"custom-title","customTitle":"repoA-1","sessionId":"%s"}\n' "$FORK_ID" > "$fork_tdir/$FORK_ID.jsonl"
printf '{"pid":%s,"sessionId":"%s","cwd":"/workspace","procStart":"%s","kind":"bg","name":"openrepoproject-b9","status":"busy"}\n' \
  "$LIVE_PID" "$FORK_ID" "$live_start" > "$sessions_dir/live-fork.json"
run "$E" forks repoA-1
is   "forks exits 0 where a live fork of the lane's transcript is running" "$rc" 0
has  "…naming the fork's own id, which is in no row" "$out" "$FORK_ID"
has  "…and the directory it is running in, which is not the lane's" "$out" "/workspace"
run "$E" who --lane repoA-1
has  "who --lane calls it a DEFECT rather than a holder" "$out" "DEFECT"
# F-X8 — THE ONE ACT, AND IT IS THE TEXT'S OWN. Clause (k) rule (e): *"both
# print the one act: retire it … Neither kills a process … and `lane-end`'s
# `--retire` is the door."* Every surface printed something else: a READ, a
# "Name them", or `kill <pid>` — which is the one act the ruling says neither
# prints.
has   "…and prints clause (k) rule (e)'s one act, filled in" "$out" "lane-end repoA-1 --retire $LIVE_PID"
hasnt "…and never \`kill <pid>\`, which the ruling refuses by name" "$out" "kill $LIVE_PID"
run "$E" live-holder repoA-1
hasnt "live-holder never returns a fork as the holder" "$out" "$FORK_ID"
has   "…and says on stderr that one is live, because a read that cannot return it could otherwise hide it" "$err" "live FORK"
has   "…printing the same one act as every other surface" "$err" "lane-end repoA-1 --retire $LIVE_PID"
hasnt "…and not the kill" "$err" "kill $LIVE_PID"
# THE TWO LISTINGS, WITH THE FORK STILL LIVE — the surfaces F-X8 names besides
# the reads. `$LANES_CMD` and `$LANE` are bound further down; the bin
# directory is where `--install` puts them and is what those bindings use.
run env LANES_NO_FETCH=1 "$OPENREPOTOOLS_BIN_DIR/lanes" --all
has   "the estate listing prints the act rather than only naming the forks" "$out" "retire each: lane-end repoA-1 --retire <pid>"
has   "…and its footer names the act too, saying the process is not killed" "$out" "lane-end <lane> --retire <pid|uuid>"
hasnt "…with no \`kill\` anywhere in it" "$out" "kill <pid>"
# `lane`'s own pick renders the same rows and is held by the hygiene
# test that walks every fork line in every shipped surface at once
# (`test_every_fork_surface_prints_the_one_act`), because it reads the CHECKOUT
# the shell is in and this suite does not move.
run "$E" forks repoA11-1
is   "forks exits 8 for a lane with no fork of its transcript running" "$rc" 8

# ---- ruling 12: THE TWO WAYS INTO `lane_forks` MUST NOT DIVERGE ------------
#
# `lanes` now hands `lane_forks` the row's ids and the retired set out of the
# pass it has already made, instead of having it render the published register
# twice and this checkout's once PER LANE. That is a second entrance to one
# read, and two entrances is how two answers begin — so the suite asks the same
# question both ways and compares.
run "$E" forks repoA-1
FK_DIRECT="$rc:$out"
run "$E" lanes --lane repoA-1
FK_VIA_LISTING="$(printf '%s' "$out" | awk -F'\t' '{print $12}')"
is "the fork column of the listing agrees with the \`forks\` read beside it" \
   "$FK_VIA_LISTING" "$(printf '%s' "${FK_DIRECT#*:}" | grep -c . || printf 0)"
# ---- ruling 7: THE READ CARRIES ALL TEN OF CLAUSE (j)'s COLUMNS, IN ORDER ---
#
# *"`lanes` and `restart` each render the subset of clause (j)'s ten columns
# their surface needs while the read carries all ten."* It carried NINE: column
# 10, the line that binds the lane, was computed by `lanes` and computed
# DIFFERENTLY by `restart`, which is two implementations of one column. The word
# that column names is `lane <name>` since Amendment 18 Addendum 2 retired
# `restart` from the PATH — one change, in the read, and both surfaces took it.
run "$E" lanes --lane repoA11-1
is "the read's row has twelve fields: clause (j)'s ten, then home and forks" \
   "$(printf '%s' "$out" | awk -F'\t' '{print NF}')" 12
is "…and column 10 is the line that binds the lane, which both surfaces print" \
   "$(printf '%s' "$out" | awk -F'\t' '{print $10}')" "lane repoA11-1"
run "$E" lanes --lane repoA11-2
is "…which for a PAUSED lane with no profile is the form that works today" \
   "$(printf '%s' "$out" | awk -F'\t' '{print $10}')" "pclaude --lane repoA11-2 <profile>"
run "$E" lanes --lane repoA11-4
is "…and for a lane that is not PAUSED it is \`none\`, because column 10 is a PAUSED lane's" \
   "$(printf '%s' "$out" | awk -F'\t' '{print $10}')" "none"

# AND THE ONE-LANE PATH AND THE ESTATE PATH AGREE ON A ROW. `--lane` reads one
# log where the listing reads them all; they are the same parser over the same
# grammar, and this is the assertion that keeps it true.
run "$E" lanes --lane repoA11-1
ONE_ROW="$out"
run "$E" lanes --all
ALL_ROW="$(printf '%s\n' "$out" | awk -F'\t' '$1 == "repoA11-1" { print; exit }')"
is "one lane read alone is the same row the estate listing gives it" "$ONE_ROW" "$ALL_ROW"

# ------------------- ruling 8: `lane-end --retire <pid|uuid>` IS THE ONE ACT
#
# Clause (k) rule (e): *"both print the one act: **retire it**, under Amendment
# 6(d) … **Neither kills a process** … and `lane-end`'s `--retire` is the
# door."* The door did not exist — three surfaces printed three other things —
# so A11 Addendum 4 ruling 8 (ratified "a11 addendum 4 yes") has it built here.
#
# AND IT IS A DOOR, NOT A RECORD. This round's first build of the act appended
# `RETIRED … → fork <sid>; pid <n>; kind <k>` to the lane's own log. That line
# cannot be written: Amendment 7(b) says `PAUSED`, `RESUMED`, `ENDED` and
# `RETIRED` *"take no payload"* and A11 clause (c) — which narrows that sentence
# for `RESUMED` and counts the narrowing as edit 1 of six — says `ENDED` and
# `RETIRED` *"stay payload-free"*. So the assertions below hold the opposite of
# what they first held: the act PROVES the fork and PRINTS Amendment 6(d) for
# it, and the log is untouched.
#
# THE FIXTURE IS EVIDENCE 6's OWN SHAPE — `kind: bg`, cwd `/workspace`, a
# transcript titled for the lane under an id no row carries — so the branch it
# takes is 6(d)'s second half, the one a `/rename` cannot reach.

# REFUSED ON ANYTHING THAT IS NOT A LIVE FORK OF THIS LANE, because naming an
# act against a stranger is how the wrong process gets stopped.
run "$END" repoA-1 --retire 999999
is   "--retire refuses a pid that is not a live fork of this lane" "$rc" 2
has  "…naming what IS live, so the operator can pick one" "$err" "$FORK_ID"
has  "…and saying nothing was named" "$err" "nothing is named"
# AND ON A LANE WITH NO FORK AT ALL — 8, which is "no record", not a refusal.
run "$END" repoA11-1 --retire "$FORK_ID"
is   "…and exits 8 for a lane no fork of which is live" "$rc" 8
# A `forks` READ THAT FAILED IS NEVER "IT IS NOT A FORK" (Amendment 7(d)).
cat > "$SANDBOX/forkbroke" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  forks) printf 'lanes-edit: simulated failure\n' >&2; exit 1 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/forkbroke"
run env REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/forkbroke" "$END" repoA-1 --retire "$FORK_ID"
is   "…and 1, never 8, where the forks read BROKE" "$rc" 1
has  "…saying so in Amendment 7(d)'s words" "$err" "NOT 'no fork of it is live'"
# THE AMBIGUOUS SPELLING IS REFUSED RATHER THAN GUESSED AT: a bare number is
# both a lane POSITION and a pid, and the two are different acts.
run "$END" --retire 3
is   'a bare `--retire <number>` with no lane named is refused as ambiguous' "$rc" 2
has  "…printing both acts it could have been" "$err" "is both a lane POSITION"
# THE ACT ITSELF — AND IT WRITES NOTHING ANYWHERE.
A11F_BEFORE="$(cat "$LOGD/repoA-1.md" 2>/dev/null || :)"
A11F_ROW_BEFORE="$(grep '^| `repoA-1`' "$LANES")"
run "$END" repoA-1 --retire "$FORK_ID"
is   "lane-end --retire <uuid> exits 0 on a proved live fork" "$rc" 0
has  "…saying it proved the fork and wrote nothing" "$err" "NOTHING has been written or stopped"
has  "…printing the pid a person needs to find the process" "$err" "pid $LIVE_PID"
has  "…and the cwd that is not the lane's" "$err" "/workspace"
# AMENDMENT 6(d), FILLED IN, FOR THE KIND OF SESSION THIS ACTUALLY IS.
has  "…naming Amendment 6(d)'s act for a BACKGROUND holder" "$err" "an idle background session still holding a lane name is ended"
has  "…and saying whose act it is" "$err" "YOUR act and no tool's"
hasnt "…and never \`kill <pid>\`, which R-A11-24 says is printed by nothing" "$err" "kill $LIVE_PID"
is   "…the log is BYTE-IDENTICAL: a RETIRED with a payload is a seventh edit to in-force text" \
     "$(cat "$LOGD/repoA-1.md" 2>/dev/null || :)" "$A11F_BEFORE"
is   "…and the row is untouched too: this ends nothing" "$(grep '^| `repoA-1`' "$LANES")" "$A11F_ROW_BEFORE"
is   "…and the process really is still running: the door never kills" "$(kill -0 "$LIVE_PID" 2>/dev/null && echo live)" "live"
# THE READ GOES ON SAYING WHAT IS TRUE. The fork is still a fork until the
# operator takes 6(d), so `forks` still names it — which is the honest answer
# and is what the first build's filter would have hidden.
run "$E" forks repoA-1
is   "forks still names a fork nobody has retired yet, because it is still one" "$rc" 0
has  "…by its own id" "$out" "$FORK_ID"
# --dry-run IS THE SAME RUN, AND SAYS SO RATHER THAN PRETENDING.
run "$END" repoA-1 --retire "$FORK_ID" --dry-run
is    "--dry-run exits 0" "$rc" 0
has   "…and says it changes nothing here, because the act writes nothing on any path" "$err" "--dry-run changes nothing here"
# AN INTERACTIVE FORK GETS 6(d)'s OTHER HALF: the retitle, which is the one a
# session with a prompt can take and a `kind: bg` one cannot.
printf '{"pid":%s,"sessionId":"%s","cwd":"/workspace","procStart":"%s","kind":"user","name":"openrepoproject-b9","status":"busy"}\n' \
  "$LIVE_PID" "$FORK_ID" "$live_start" > "$sessions_dir/live-fork.json"
run "$END" repoA-1 --retire "$FORK_ID"
is   "an INTERACTIVE fork is proved the same way" "$rc" 0
has  "…and gets Amendment 6(d)'s retitle, typed in that session" "$err" "/rename repoA-1 · retired "
has  "…said to be typed there, because no API renames one from outside" "$err" "there is no API to rename one from outside"
hasnt "…and still never a kill" "$err" "kill $LIVE_PID"

rm -f "$sessions_dir/live-fork.json" "$fork_tdir/$FORK_ID.jsonl"

# --------------------------- clause (c): lane-start RECORDS dir and profile
mkdir -p "$HOME/projects/repoA11b"
git init -q -b main "$HOME/projects/repoA11b"
git -C "$HOME/projects/repoA11b" remote add origin "https://github.com/opensoft/repoA11b.git"
git -C "$WIP" add -A >/dev/null 2>&1
git -C "$WIP" commit -q -m "commit pending handoffs before the Amendment 11 lane-start cases" >/dev/null 2>&1 || :
FAKE_TMUX_WINDOW="a11start:@42" FAKE_TMUX_WINDOW_INDEX=3 FAKE_TMUX_WINDOW_NAME=claude \
  CLAUDE_PROFILE_NAME=team-05a run "$START" repoA11b 1 --no-launch
is   "lane-start exits 0 for a new lane under Amendment 11" "$rc" 0
A11B_LOG="$(cat "$LOGD/repoA11b-1.md" 2>/dev/null || :)"
has  "…and its STARTED line records the lane's DIRECTORY" "$A11B_LOG" "dir $HOME/projects/repoA11b"
has  "…its PROFILE, from the launcher's own CLAUDE_PROFILE_NAME" "$A11B_LOG" "profile team-05a"
has  "…and its WINDOW as two refs, <session>:<index> and <@id>" "$A11B_LOG" "window a11start:3 @42"
has  "…keeping the home and estate the line already carried" "$A11B_LOG" "home opensoft/repoA11b; estate repoA11b"
# THE ROW'S STAMP IS AMENDMENT 6(c)'s AND IS WRITTEN ON A RESUME, never on the
# row's own creation: a brand-new row is created with the uuid already in its
# session cell, so there is nothing for a stamp to say that the row does not.
# The second start of the same lane is the one that stamps, and its TAIL is what
# clause (c) extends — the head (verb, uuid, lane) is Amendment 8(d)'s and is
# untouched.
FAKE_TMUX_WINDOW="a11start:@42" FAKE_TMUX_WINDOW_INDEX=3 FAKE_TMUX_WINDOW_NAME=repoA11b-1 \
  CLAUDE_PROFILE_NAME=team-05a run "$START" repoA11b 1 --no-launch
is   "lane-start exits 0 on a second start of the same lane" "$rc" 0
has  "the row's stamp states clause (c)'s two facts for a person, in its TAIL" \
     "$(grep '^| `repoA11b-1`' "$LANES")" "dir $HOME/projects/repoA11b; window a11start:3 @42"
has  "…and that tail still says what actually happened, so --no-launch never claims a launch" \
     "$(grep '^| `repoA11b-1`' "$LANES")" ", no launch"
has  "…while its HEAD is Amendment 8(d)'s and is untouched" \
     "$(grep '^| `repoA11b-1`' "$LANES")" "(lane repoA11b-1) — lane-start on Eagle: window renamed, no launch; dir "
# NO PROFILE IS NO SUB-FIELD, never a guessed one (Amendment 7(i)).
mkdir -p "$HOME/projects/repoA11c"
git init -q -b main "$HOME/projects/repoA11c"
git -C "$HOME/projects/repoA11c" remote add origin "https://github.com/opensoft/repoA11c.git"
FAKE_TMUX_WINDOW="a11start:@42" FAKE_TMUX_WINDOW_INDEX=3 FAKE_TMUX_WINDOW_NAME=claude \
  run env -u CLAUDE_PROFILE_NAME "$START" repoA11c 1 --no-launch
is    "lane-start exits 0 for a lane started outside the launcher" "$rc" 0
hasnt "…and writes NO profile sub-field rather than inventing one" "$(cat "$LOGD/repoA11c-1.md")" "profile "
has   "…while still recording the directory, which it does know" "$(cat "$LOGD/repoA11c-1.md")" "dir $HOME/projects/repoA11c"

# CLAUSE (c)'s SEPARATOR FENCE, ON THE WRITER THAT DID NOT HAVE IT. SPEC rev 6
# §5 adds `; ` to `, ` and ` — ` for `dir` and `profile` — *"A value containing
# `, `, ` — ` or `; ` is refused, exit 2, naming it — not truncated, not escaped,
# and not appended"* — and the `/lane-swap` skill, the other writer the clause
# names, has refused all three since `68614bf` (the `skill_subfield` cases
# below prove it). THIS writer refused two of them.
#
# THE QUOTING DOES NOT COVER THE GAP, which is why this is a refusal and not a
# shrug: `payload_subfield` splits the payload on `; ` BEFORE it honours a
# quote, so `dir "/p/a; b"` — quoted, because a path with a space is written
# quoted — splits into `dir "/p/a` and `b"`, and `lane-dir` answers `"/p/a`: a
# path that is wrong, carries a quote mark, and nobody ever wrote. A restart
# then lands in the right transcript and the wrong directory, silently, which is
# Evidence 3 exactly.
A11F="$HOME/projects/repoA11f"
mkdir -p "$A11F/a; b"
git init -q -b main "$A11F/a; b"
git -C "$A11F/a; b" remote add origin "https://github.com/opensoft/repoA11f.git"
FAKE_TMUX_WINDOW="a11start:@42" FAKE_TMUX_WINDOW_INDEX=3 FAKE_TMUX_WINDOW_NAME=claude \
  CLAUDE_PROFILE_NAME=team-05a run "$START" --dir "$A11F/a; b" repoA11f 1 --no-launch
is    "lane-start REFUSES a directory carrying the payload's sub-field separator" "$rc" 2
has   "…naming the path, rather than truncating or escaping it" "$err" "$A11F/a; b"
has   "…and the separator, beside the two this fence always had" "$err" "'; '"
is    "…having written no log for the lane at all" \
      "$( [ -f "$LOGD/repoA11f-1.md" ] && printf wrote || printf none )" "none"
# THE COMMA IS STILL REFUSED, so the widening added a separator and removed none.
mkdir -p "$A11F/c, d"
git init -q -b main "$A11F/c, d"
git -C "$A11F/c, d" remote add origin "https://github.com/opensoft/repoA11f.git"
FAKE_TMUX_WINDOW="a11start:@42" FAKE_TMUX_WINDOW_INDEX=3 FAKE_TMUX_WINDOW_NAME=claude \
  CLAUDE_PROFILE_NAME=team-05a run "$START" --dir "$A11F/c, d" repoA11f 1 --no-launch
is    "…and a ', ' is refused exactly as it was" "$rc" 2
# A PROFILE CARRYING IT IS DROPPED AND NEVER REFUSED, because a profile is not
# the thing the run needs to be correct — the same asymmetry this file already
# holds for `, ` and `"`.
mkdir -p "$HOME/projects/repoA11g"
git init -q -b main "$HOME/projects/repoA11g"
git -C "$HOME/projects/repoA11g" remote add origin "https://github.com/opensoft/repoA11g.git"
FAKE_TMUX_WINDOW="a11start:@42" FAKE_TMUX_WINDOW_INDEX=3 FAKE_TMUX_WINDOW_NAME=claude \
  CLAUDE_PROFILE_NAME='team; 05a' run "$START" repoA11g 1 --no-launch
is    "a PROFILE carrying the separator does not stop the start" "$rc" 0
hasnt "…and no profile sub-field is written rather than an unreadable one" \
      "$(cat "$LOGD/repoA11g-1.md" 2>/dev/null || :)" "profile "
has   "…while the run says which separator took it out" "$err" "'; '"

# AN `<@id>` IS `@<digits>` AND NOTHING ELSE (F-X13(a), A11 Addendum 4 ruling 10).
# `case … in @*)` accepted anything that merely STARTED with an at-sign. Two
# things that are not ids do: a `tmux` too old to know `#{window_id}` prints the
# FORMAT back, and a shim on PATH may print anything at all — a pane ref beside
# the window's, say. Either recorded here is a lie in an append-only log, and
# worse than an absence: the sub-field would then name a window `window-lane`
# can never resolve while looking complete. `claude-profile` makes exactly this
# check on exactly this value, so two writers of one field had two standards.
mkdir -p "$HOME/projects/repoA11d"
git init -q -b main "$HOME/projects/repoA11d"
git -C "$HOME/projects/repoA11d" remote add origin "https://github.com/opensoft/repoA11d.git"
FAKE_TMUX_WINDOW="a11start:0" FAKE_TMUX_WINDOW_INDEX=3 FAKE_TMUX_WINDOW_ID='@42 %7' \
  FAKE_TMUX_WINDOW_NAME=claude CLAUDE_PROFILE_NAME=team-05a \
  run "$START" repoA11d 1 --no-launch
is    "lane-start exits 0 when tmux answers something that is not an <@id>" "$rc" 0
A11D_LOG="$(cat "$LOGD/repoA11d-1.md" 2>/dev/null || :)"
hasnt "…and records NO id rather than a string that is not one" "$A11D_LOG" "%7"
hasnt "…not even the part of it that looked like one" "$A11D_LOG" "@42"
has   "…while the <session>:<index> IS recorded, because a record with no id is COMPLETE" \
      "$A11D_LOG" "window a11start:3"
# THE OTHER SHAPE THE COMMENT NAMES, held so it stays held: an old `tmux` prints
# the format back, which does not begin with `@` at all and was already refused.
mkdir -p "$HOME/projects/repoA11e"
git init -q -b main "$HOME/projects/repoA11e"
git -C "$HOME/projects/repoA11e" remote add origin "https://github.com/opensoft/repoA11e.git"
FAKE_TMUX_WINDOW="a11start:0" FAKE_TMUX_WINDOW_INDEX=3 FAKE_TMUX_WINDOW_ID='#{window_id}' \
  FAKE_TMUX_WINDOW_NAME=claude CLAUDE_PROFILE_NAME=team-05a \
  run "$START" repoA11e 1 --no-launch
is    "lane-start exits 0 when a tmux too old prints the format back" "$rc" 0
hasnt "…and records the format string nowhere" "$(cat "$LOGD/repoA11e-1.md" 2>/dev/null || :)" "#{window_id}"

# ----------- rulings 10 and 11: the `/lane-swap` skill absorbs #71's six
#
# `opensoft/workBenches#74` @`0b7f6bc` DELETES the launcher's copy of this skill,
# so after it lands `openRepoTools --install` is the only writer of it on every
# host and this copy must be the superset (F-X13). Ruling 10 names the six
# things #71 had and this did not; ruling 11 moves the container case. Six of
# the seven are prose a test can only read; the SUB-FIELD RULE is arithmetic and
# is extracted from the file and run, like `/restart`'s rung 4 beside it.
# THE FILE MOVED WITH THE ACT (Amendment 17(a), ratified 2026-09-14): the steps
# these cases read are `skills/handoff/SKILL.md`'s now, and `skills/lane-swap/`
# holds the ALIAS that names it. Every assertion below is the same assertion
# against the file that carries the act.
SWSK="$SRC_DIR/skills/handoff/SKILL.md"
SWSK_TEXT="$(cat "$SWSK")"
skill_subfield() {   # <win> <dir> — runs the skill's own two `case` lines
  local ss_win="$1" ss_dir="$2" ss_a ss_b ss_c
  # MATCHED ON WHAT EACH LINE DOES, with `grep -F`, because the patterns
  # themselves are full of the characters a regex would eat.
  ss_a="$(grep -F 'refused="$refused window=$win"' "$SWSK" | head -n1)"
  ss_b="$(grep -F 'refused="$refused dir=$dir"' "$SWSK" | head -n1)"
  ss_c="$(grep -F "in *' '*) dir=" "$SWSK" | head -n1)"
  [ -n "$ss_a" ] && [ -n "$ss_b" ] && [ -n "$ss_c" ] || { printf 'NO LINES\n'; return 1; }
  ( win="$ss_win"; dir="$ss_dir"; refused=""
    eval "$ss_a"; eval "$ss_b"; eval "$ss_c"
    printf 'win=[%s] dir=[%s] refused=[%s]' "$win" "$dir" "$refused" )
}
is "a clean window and directory go through untouched" \
   "$(skill_subfield 'sess:0 @71' '/checkouts/b/x')" 'win=[sess:0 @71] dir=[/checkouts/b/x] refused=[]'
is "a space in the path is QUOTED, which is what makes it one ref under 7(b)" \
   "$(skill_subfield 'sess:0' '/checkouts/b/my projects/x')" 'win=[sess:0] dir=["/checkouts/b/my projects/x"] refused=[]'
is "a ', ' in the path DROPS the sub-field, keeps the line, and says what went" \
   "$(skill_subfield 'sess:0' '/checkouts/b/a, b')" 'win=[sess:0] dir=[] refused=[ dir=/checkouts/b/a, b]'
is "…and a '; ', which SPEC rev 6 §5 adds for dir and profile" \
   "$(skill_subfield 'sess:0' '/checkouts/b/a; b')" 'win=[sess:0] dir=[] refused=[ dir=/checkouts/b/a; b]'
is "…and a '\"', which clause (c) writes itself and so may not be in the value" \
   "$(skill_subfield 'sess:0' '/checkouts/b/a"b')" 'win=[sess:0] dir=[] refused=[ dir=/checkouts/b/a"b]'
is "a ', ' in the WINDOW drops that sub-field, on A8(b)'s list and not widened" \
   "$(skill_subfield 'sess:0, x' '/checkouts/b/x')" 'win=[] dir=[/checkouts/b/x] refused=[ window=sess:0, x]'
is "…and a '; ' in the window is NOT refused, because A8(b)'s list is not widened (R-A11-15)" \
   "$(skill_subfield 'sess:0; x' '/checkouts/b/x')" 'win=[sess:0; x] dir=[/checkouts/b/x] refused=[]'
# (b) THE NO-WORKTREE `dir` RUNGS — `R-A11-11`, and the rung the launcher round
# was ORDERED to drop, kept by the copy that survives.
hasnt "the skill no longer falls to this shell's git toplevel for the lane's dir" \
      "$SWSK_TEXT" 'dir="$(git rev-parse --show-toplevel'
has   "…it asks the lane's own recorded checkout first" "$SWSK_TEXT" '"$L" lane-dir "$lane"'
has   "…then the launcher's own word" "$SWSK_TEXT" 'WORKBENCHES_CLAUDE_LANE_DIR'
has   "…then the live session's own record, which is what clause (c) names" "$SWSK_TEXT" 'CLAUDE_CONFIG_DIR"/sessions/*.json'
has   "…and an absolute path or nothing at all" "$SWSK_TEXT" '[[ "$dir" == /* ]] || dir=""'
# (d) A MISSING `dir` IS SAID, NOT GUESSED AT.
has   "a missing dir is SAID rather than omitted in silence" "$SWSK_TEXT" "NO dir sub-field"
# (e) THE CLOSING `/rename` ACT, with the premise that is true today.
has   "the skill ends with the /rename act (R-A11-16)" "$SWSK_TEXT" "type /rename <lane>"
has   "…on act 0's MERGED sha, which is the premise that moved" "$SWSK_TEXT" "3719d97"
# (f) THE ALIAS IS IN THE DESCRIPTION — clause (g).
has   "the description names the aliases" "$SWSK_TEXT" "aliases /swap, /lane-swap"
has   "…and the word a context clear uses" "$SWSK_TEXT" "/ctx is /handoff --restart"
has   "…and the amendments that amended it" "$SWSK_TEXT" "amended by Amendments 11, 17 and 18(d)"
# RULING 11 — the container case stops the WRITES, not the swap.
hasnt "a container with no workstation no longer exits at step 1" "$SWSK_TEXT" 'export LANES_WORKSTATION=<this host name>"
  exit 2'
has   "…it records the gap and carries on" "$SWSK_TEXT" "ws_missing=1"
has   "…the handoff of step 2 is where the gap is named (clause (e))" "$SWSK_TEXT" "THE HANDOFF IS WHERE THE GAP IS NAMED"
has   "…and step 4's two log writes are the ones that stop" "$SWSK_TEXT" 'if [[ -z "$ws_missing" ]]; then'

# THE SWAP SKILL'S OWN FAIL-CLOSED FENCE, EXTRACTED AND RUN (#26, the review of
# `c3ebcfe`, this file's `:28`, `:72` and `:236`; the same family `73caa5d` took
# in `/restart`). Step 1's three reads collapsed every code into the ordinary
# case, and beneath them is not a refusal but THE NEXT RUNG — the last of which
# is the workstation's NEWEST SWAP, a different lane. A register that could not
# be read is not "this window is not a lane", and step 4 would then write a
# PAUSED record and a restart command for a lane this window is not.
swsk_fence="$(awk '/^sread\(\) \{/,/^\}$/' "$SWSK")"
is   "the swap skill carries the fence its step 1 reads go through" \
     "$( [ -n "$swsk_fence" ] && printf yes || printf no )" "yes"
sfence_probe() {   # <helper exit code> — runs the SKILL's own fence against it
  printf '#!/usr/bin/env bash\nprintf "ANSWER\\n"\nexit %s\n' "$1" > "$SANDBOX/sfencehelper"
  chmod +x "$SANDBOX/sfencehelper"
  ( L="$SANDBOX/sfencehelper"; eval "$swsk_fence"
    v=unset; sread v "'a thing it is not'" some-verb 2>"$SANDBOX/sfence.err"
    printf 'rc=%s v=[%s]' "$?" "$v" )
}
is   "an answer reaches the variable" "$(sfence_probe 0)" "rc=0 v=[ANSWER]"
is   "…8 is NO ANSWER and falls to the next rung" "$(sfence_probe 8)" "rc=0 v=[]"
is   "…2 is a helper predating the read and falls through too" "$(sfence_probe 2)" "rc=0 v=[]"
is   "…and a read that FAILED stops the skill where it stands" "$(sfence_probe 6)" ""
has  "…naming the read and the code it came back with" "$(cat "$SANDBOX/sfence.err")" "some-verb\` failed (exit 6)"
has  "…and what it will not do on one" "$(cat "$SANDBOX/sfence.err")" "will not bind a lane, write a PAUSED record"
hasnt "no step 1 read is left on the shape that cannot tell 8 from 1" \
      "$SWSK_TEXT" 'register-row "$lane" >/dev/null 2>&1 || lane=""'
hasnt "…nor the swap record's on \`|| rows=\"\"\`" "$SWSK_TEXT" '2>/dev/null)" || rows=""'
hasnt "…nor the window read's bare \`&&\`, which reads every failure as no candidate" \
      "$SWSK_TEXT" 'window-lane "$ws" "$wl_ref" 2>/dev/null)" &&'

# AND THE `dir` READ, WHICH MAY NOT STOP — `R-A11-11`, *a swap is never left
# unwritten* — SO IT DROPS THE SUB-FIELD AND NAMES THE READ. Its two lower
# sources are not rungs beneath a failed read: the third is THIS SESSION'S own
# `cwd`, and a swap typed in one checkout for a lane that lives in another would
# record this session's directory as that lane's, in a log nothing rewrites.
# Extracted from the file and run against a helper in each state.
swap_dir_blk="$(awk '/^dir=""; dir_read_failed=/,/^fi$/' "$SWSK")"
is   "the swap skill carries the dir read as its own step" \
     "$( [ -n "$swap_dir_blk" ] && printf yes || printf no )" "yes"
cat > "$SANDBOX/dirhelper" <<'WRAP'
#!/usr/bin/env bash
[ -n "${STUB_OUT:-}" ] && printf '%s\n' "$STUB_OUT"
exit "${STUB_RC:-0}"
WRAP
chmod +x "$SANDBOX/dirhelper"
swap_dir_probe() {   # <helper exit code> <what it prints> <what the launcher exported>
  ( L="$SANDBOX/dirhelper"; lane=repoA11-1
    STUB_RC="$1"; STUB_OUT="$2"; export STUB_RC STUB_OUT
    WORKBENCHES_CLAUDE_LANE_DIR="$3"
    CLAUDE_CODE_SESSION_ID=""; CLAUDE_CONFIG_DIR=""
    eval "$swap_dir_blk"
    printf 'dir=[%s] failed=[%s]' "$dir" "${dir_read_failed:+named}" )
}
is   "the lane's own recorded checkout is taken where the read answered" \
     "$(swap_dir_probe 0 /checkouts/lane /launcher/export)" "dir=[/checkouts/lane] failed=[]"
is   "…8 is a record naming none, and the launcher's word is the next source" \
     "$(swap_dir_probe 8 '' /launcher/export)" "dir=[/launcher/export] failed=[]"
is   "…as is a helper predating the read" \
     "$(swap_dir_probe 2 '' /launcher/export)" "dir=[/launcher/export] failed=[]"
is   "…while a read that FAILED takes NO substitute and names itself" \
     "$(swap_dir_probe 6 '' /launcher/export)" "dir=[] failed=[named]"
has  "…and the record still says which fact it does not carry" "$SWSK_TEXT" "NO dir sub-field: %s"

# THE `/lane-swap` SKILL MAKES THE SAME TEST, and it is run FROM THE FILE rather
# than restated — the same reason `/restart`'s rung 4 is: a copy is what would
# go on passing after the file drifted.
SWSKILL="$SRC_DIR/skills/handoff/SKILL.md"
# THE WHOLE `window` BLOCK IS EXTRACTED AND RUN, not one line of it: the block
# is now four reads and two shape checks (F-X13 row (h) put the launcher's own
# exports behind the live reads, under `R-A11-26`'s superset rule), and a test
# that eval'd one line would go green over a broken neighbour. `tmux` is a
# FUNCTION here, so the block's own `tmux display-message` calls are answered
# by the case rather than by whatever is on PATH.
skill_win_of() {   # <what tmux answers for #S:#I> <…for #{window_id}> [<REF env>] [<ID env>]
  local swo_win="$1" swo_wid="$2" swo_ref="${3-}" swo_id="${4-}" swo_blk
  swo_blk="$(awk '/^win="\$\(tmux display-message -p .#S:#I/,/^\[\[ "\$wid" =~ \^@\[0-9\]\+\$ \]\] && win=/' "$SWSKILL")"
  case "$swo_blk" in *'&& win='*) : ;; *) printf 'NO BLOCK IN %s\n' "$SWSKILL"; return 1 ;; esac
  (
    tmux() { case "$*" in *'#S:#I'*) printf '%s\n' "$swo_win" ;; *window_id*) printf '%s\n' "$swo_wid" ;; esac; }
    WORKBENCHES_CLAUDE_WINDOW_REF="$swo_ref" WORKBENCHES_CLAUDE_WINDOW_ID="$swo_id"
    export WORKBENCHES_CLAUDE_WINDOW_REF WORKBENCHES_CLAUDE_WINDOW_ID
    eval "$swo_blk"; printf '%s' "$win"
  )
}
is "the skill records an <@id> that is one" "$(skill_win_of 'a11sess:0' '@71')" "a11sess:0 @71"
is "…and records none where tmux answered a pane beside it" "$(skill_win_of 'a11sess:0' '@71 %7')" "a11sess:0"
is "…nor where a tmux too old printed the format back" "$(skill_win_of 'a11sess:0' '#{window_id}')" "a11sess:0"
is "…nor for a bare at-sign" "$(skill_win_of 'a11sess:0' '@')" "a11sess:0"
# F-X13 ROW (h) — THE LAUNCHER'S OWN EXPORTS ARE READ WHERE THE LIVE ONES
# ANSWER NOTHING. `#71`'s copy read `WORKBENCHES_CLAUDE_WINDOW_REF` and
# `_WINDOW_ID`; `#26`'s ignored all of them, and `R-A11-26` makes the surviving
# copy the SUPERSET, so a seventh divergence is absorbed on the same ground. On
# the normal path the launcher started this session and threaded the window it
# captured across its re-exec, so a `tmux` that has gone costs the record a
# sub-field the process already had in hand.
is "…and falls back to what the launcher exported when tmux answers nothing" \
   "$(skill_win_of '' '' 'a11sess:4' '@88')" "a11sess:4 @88"
is "…taking the exported id beside a live ref" \
   "$(skill_win_of 'a11sess:0' '' '' '@88')" "a11sess:0 @88"
# AND AN EXPORT IS NO MORE TRUSTED THAN A SHIM: both are shape-checked.
is "…while an exported ref that is not one is dropped, like a live one" \
   "$(skill_win_of '' '' 'not-a-window-ref' '@88')" "@88"
is "…and an exported id that is not one is dropped too" \
   "$(skill_win_of 'a11sess:0' '' '' 'window-id-please')" "a11sess:0"
is "…and with nothing anywhere the sub-field is simply absent" \
   "$(skill_win_of '' '' '' '')" ""

# ---------------------------- clause (c): the DIRECTORY PRECEDENCE, four rungs
run "$START" --dry-run repoA11 1
is   "lane-start finds the lane's directory without --dir, from its own record" "$rc" 0
has  "…naming the rung that answered" "$err" "from the swap record"
has  "…and planning the cd into it, which Evidence 3 makes load-bearing for CLAUDE.md and the lane's memory" "$err" "cd $A11_DIR"
# RUNG 1 BEATS THE RECORD: the operator's word is first.
run "$START" --dry-run --dir "$HOME/projects/repoA" repoA11 1
has  "--dir beats the record, because rung 1 is the operator's own word" "$err" "cd $HOME/projects/repoA"
# RUNG 3: a lane with a STARTED that carries a dir and no swap record at all.
{ printf '# lane repoA11-7 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoA11-7, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoA11-7 → home opensoft/repoA11; estate repoA11; dir %s; profile team-05a; window a11sess:0 @71\n' "$A11_ID" "$A11_DIR"
} > "$LOGD/repoA11-7.md"
add_seed_row "| \`repoA11-7\` | harness \`$A11_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA11/u.md | ACTIVE |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a lane whose only record of its directory is its STARTED line"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
run "$START" --dry-run repoA11 7
has  "…and failing a swap record, the lane's LOG answers" "$err" "from the lane's log"
has  "…with the same directory" "$err" "cd $A11_DIR"
# RUNG 4: the default, and ONLY for a lane that has never been started under
# this amendment.
run "$START" --dry-run repoA11b 1
has  "a lane with no recorded directory falls to \$PROJECTS_ROOT/<repo>, which is what it always did" \
     "$err" "cd $HOME/projects/repoA11b"
# AND THERE IS NO FIFTH RUNG: a lane whose recorded directory is GONE is a
# refusal naming --dir, never a silent re-home from the cwd.
{ printf '# lane repoA11-8 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoA11-8, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoA11-8 → home opensoft/repoA11; estate repoA11; dir %s/a-directory-that-is-gone; profile team-05a; window a11sess:0 @71\n' "$A11_ID" "$HOME"
} > "$LOGD/repoA11-8.md"
add_seed_row "| \`repoA11-8\` | harness \`$A11_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA11/t.md | ACTIVE |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a lane whose recorded directory no longer exists"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
run "$START" --dry-run repoA11 8
is   "a recorded directory that is gone is a REFUSAL" "$rc" 1
has  "…naming the path" "$err" "a-directory-that-is-gone"
has  "…the rung it came from" "$err" "from the lane's log"
has  "…and the one flag that fixes it" "$err" "--dir"

# ------------------------------- EVIDENCE 7: THE LANE WHOSE CHECKOUT IS NESTED
#
# Reported by Brett Heap 2026-09-13T23:01:02Z
# (brettheap/new-workstation#20, comment 5656793094). `pclaude team03m`
# auto-selected the saved lane `opsXfactory-5`, `lane-start` derived
# `~/projects/opsXfactory` — which does not exist — and EXITED 1 BEFORE CLAUDE
# STARTED, leaving a pane that said `[exited]`. The real checkout is
# `~/projects/xFactory/xFactories/OpsxFactory`.
#
# THE RECORD SHAPE IS COPIED FROM THE LIVE LOG (read only): that lane's last
# RESUMED and PAUSED lines carry `home opensoft/OpsxFactory; estate xFactory`
# and `window …; workstation docker-desktop` — and NO `dir`, the field this
# amendment adds and that nothing backfills (Amendment 7(i)). The lane label
# and the repository are not even the same string: `opsXfactory` against
# `OpsxFactory`.
E7_ID="e7e70001-0007-4000-8000-e7e700010007"
mkdir -p "$HOME/projects/xFactory/xFactories/OpsxFactory"
git init -q -b main "$HOME/projects/xFactory/xFactories/OpsxFactory"
git -C "$HOME/projects/xFactory/xFactories/OpsxFactory" remote add origin "git@github.com:opensoft/OpsxFactory.git"
add_seed_row "| \`opsXfactory-5\` | harness \`$E7_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/xFactory/o.md | ACTIVE |"
{ printf '# lane opsXfactory-5 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'RESUMED — lane opsXfactory-5, session %s@Eagle, 2026-09-13T03:30:02Z, lane:opsXfactory-5 → home opensoft/OpsxFactory; estate xFactory\n' "$E7_ID"
  printf 'PAUSED — lane opsXfactory-5, session %s@docker-desktop, 2026-09-13T22:41:57Z, lane:opsXfactory-5 → swap; window claude-team-03l-20260913220714-66271:0; workstation docker-desktop — on Brett Heap'"'"'s word: nothing in flight\n' "$E7_ID"
} > "$LOGD/opsXfactory-5.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed Evidence 7's record shape: home and estate, and no dir"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
# THE DEFAULT IS NOT THERE, AND THAT USED TO BE THE WHOLE STORY.
is   "Evidence 7's default checkout really is absent, which is the fixture" \
     "$([ -d "$HOME/projects/opsXfactory" ] && printf present || printf absent)" "absent"
# RUNG 6 ANSWERS: a checkout of the lane's RECORDED HOME, two levels under
# $PROJECTS_ROOT, proved by its own `origin` — not by its name.
run "$START" --dry-run opsXfactory 5
is   "lane-start no longer dies on a lane whose checkout is nested (Evidence 7)" "$rc" 0
has  "…finding the checkout of the home its own record names" "$err" "cd $HOME/projects/xFactory/xFactories/OpsxFactory"
has  "…and naming the rung that answered" "$err" "Evidence 7"
# AND IT IS PROVED BY `origin`, NEVER BY THE NAME. A directory with the right
# name and somebody else's origin is not this lane's checkout, and taking it
# would re-home the lane for every `#n` it writes afterwards.
mkdir -p "$HOME/projects/imposter/OpsxFactory"
git init -q -b main "$HOME/projects/imposter/OpsxFactory"
git -C "$HOME/projects/imposter/OpsxFactory" remote add origin "git@github.com:someone/else.git"
run "$START" --dry-run opsXfactory 5
has  "…and a same-named checkout with another origin is never taken" "$err" "cd $HOME/projects/xFactory/xFactories/OpsxFactory"
# NOW THE REFUSAL: the same record shape with no provable checkout anywhere.
mv "$HOME/projects/xFactory/xFactories/OpsxFactory" "$HOME/projects/xFactory/xFactories/OpsxFactory-moved-away"
run "$START" --dry-run opsXfactory 5
is   "…and with nothing provable it REFUSES with 2, not the 1 that printed [exited]" "$rc" 2
has  "…saying nothing was started" "$err" "nothing was started"
has  "…naming the one act that RECORDS the directory, filled in" "$err" "lane-start --dir <path> opsXfactory 5"
has  "…and what it tried, so the refusal is readable" "$err" "project.yaml legs of opensoft/OpsxFactory"
hasnt "…and it never guesses the same-named checkout with the wrong origin" "$err" "cd $HOME/projects/imposter"
# RUNG 5 — THE ESTATE'S `project.yaml` LEGS, which are a DECLARATION rather
# than a search: the leg's `path` is resolved against the manifest's own
# directory, and the candidate is still proved by its `origin`.
mkdir -p "$HOME/projects/xFactory/legged/inner"
git init -q -b main "$HOME/projects/xFactory/legged/inner"
git -C "$HOME/projects/xFactory/legged/inner" remote add origin "git@github.com:opensoft/OpsxFactory.git"
{ printf 'schema_version: 1\nkind: project-manifest\nid: xf\nname: "xFactory"\nlegs:\n'
  printf '  - role: assembly\n    repository: opensoft/Something-Else\n    path: "."\n'
  printf '  - role: code\n    repository: opensoft/OpsxFactory\n    path: inner\n'
} > "$HOME/projects/xFactory/legged/project.yaml"
run "$START" --dry-run opsXfactory 5
is   "the estate's project.yaml legs answer before the refusal" "$rc" 0
has  "…taking the leg's own path, resolved against the manifest" "$err" "cd $HOME/projects/xFactory/legged/inner"
has  "…and saying which manifest declared it" "$err" "legs of"
rm -rf "$HOME/projects/xFactory/legged" "$HOME/projects/imposter"
mv "$HOME/projects/xFactory/xFactories/OpsxFactory-moved-away" "$HOME/projects/xFactory/xFactories/OpsxFactory"
# AND ONE `--dir` CLOSES IT FOR EVER: the field is written, and every later
# read — `lane-dir`, and `restart`'s `cd` — takes it from the lane's own log
# rather than from a rung at all.
FAKE_TMUX_WINDOW="e7sess:@51" FAKE_TMUX_WINDOW_INDEX=0 FAKE_TMUX_WINDOW_NAME=claude \
  CLAUDE_PROFILE_NAME=team-03l \
  run "$START" --dir "$HOME/projects/xFactory/xFactories/OpsxFactory" opsXfactory 5 --no-launch
is   "one lane-start --dir records the field Evidence 7's record was missing" "$rc" 0
has  "…in the lane's own log" "$(cat "$LOGD/opsXfactory-5.md")" "dir $HOME/projects/xFactory/xFactories/OpsxFactory"
run "$E" lane-dir opsXfactory-5
is   "…so lane-dir answers for it now" "$rc" 0
is   "…with the path that was named once" "$out" "$HOME/projects/xFactory/xFactories/OpsxFactory"
run "$START" --dry-run opsXfactory 5
has  "…and the next start takes it from the LOG rather than from any rung" "$err" "from the lane's log"

echo "== Amendment 11: the cross-lane write clause (d) rule 1 forbids =="
#
# THE TEST THAT WOULD HAVE CAUGHT EVIDENCE 2(b), written here and owed to the
# `opensoft/brett-wip` hotfix that `openRepoTools#24` — act 3, merged as
# `d4b5710` — ports into this tree.
# `lane-start:630-640` — step 3b — overwrites the resume target with the uuid of
# whatever session is live in the window the command was typed in, whenever that
# uuid is not in the lane's published cell. Typed from ANOTHER lane's window
# that is a cross-lane write: lane X is resumed as lane Y's transcript, and X's
# row is stamped with Y's uuid, in the one cell Amendment 6(b) makes the resume
# target. The fence is OWNERSHIP ALONE (`R-A11-1` corrected): the window's name
# is the lane, or `live-holder` answered `here`.
VT_ID="eeee0001-1111-4000-8000-eeee00011111"
add_seed_row "| \`repoVT-1\` | harness \`$VT_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoVT/x.md | ACTIVE |"
add_seed_row "| \`repoVT-2\` | pending — set by the session's first act | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoVT/y.md | ACTIVE |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the cross-lane window case"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
mkdir -p "$HOME/projects/repoVT"
git init -q -b main "$HOME/projects/repoVT"
git -C "$HOME/projects/repoVT" remote add origin "https://github.com/opensoft/repoVT.git"
# lane Y's window: named for repoVT-1, and repoVT-1's own live session is in it.
write_record_ns "$sessions_dir/live-vt.json" "$VT_ID" "$LIVE_PID" "$live_start" "vtsess:@31.%31" "repoVT-1" "user" "busy"
FAKE_TMUX_WINDOW="vtsess:@31" FAKE_TMUX_WINDOW_INDEX=0 FAKE_TMUX_WINDOW_NAME="repoVT-1" \
  run "$START" --dry-run --dir "$HOME/projects/repoVT" repoVT-2
# THE TWO `case`s ARE HOISTED OUT OF THE `$( )`, and they have to be (A9
# Addendum 4, R-A9-11, and `test_no_shipped_bash_opens_a_case_inside_a_command_substitution`
# is what holds the rule now). Bash 3.2 reads the `)` that closes a case PATTERN
# as the one that closes the command substitution, so both of these were a
# syntax error on macOS and nowhere else: at `708395e` the assertion compared a
# fragment of THIS FILE'S OWN SOURCE — `printf 'resumed Y' ;; *) printf 'did
# not' ;; esac)` — against `did not`, and `tests-macos` was two cases redder
# than every GNU runner for a defect in the test rather than in `lane-start`.
# Same two tests, two variables earlier.
case "$err" in *"--resume $VT_ID"*) vt_resumed="resumed Y" ;; *) vt_resumed="did not" ;; esac
case "$err" in *"append-session-id repoVT-2"*"$VT_ID"*) vt_stamped="stamped Y" ;; *) vt_stamped="did not" ;; esac
is  "lane-start X typed from lane Y's window never resumes X as Y's transcript" \
    "$vt_resumed" "did not"
is  "…and never plans X's row to be stamped with Y's uuid" \
    "$vt_stamped" "did not"
has "…saying which window vetoed it and why" "$err" "which is another lane the register has a row for"
is  "…and the run itself still exits 0, because a veto is not a refusal" "$rc" 0
# A NAME IS A VETO AND NEVER A PERMISSION (`R-A11-12`). A window still called
# `claude` vetoes nothing, and the taking goes ahead — which is the case the
# first correction was made to preserve and the second broke: 8 of this
# workstation's 16 windows were named `claude`, and this lane was in one three
# times in a day. The uuid here is in NO row at all, which is what a `/clear`, a
# usage reset and a profile switch leave behind — so neither veto has anything
# to fire on and step 3b does exactly what it exists for.
VT_FRESH="eeee0002-2222-4000-8000-eeee00022222"
rm -f "$sessions_dir/live-vt.json"
write_record_ns "$sessions_dir/live-vt2.json" "$VT_FRESH" "$LIVE_PID" "$live_start" "vtsess:@31.%31" "openrepoproject-b9" "derived" "busy"
FAKE_TMUX_WINDOW="vtsess:@31" FAKE_TMUX_WINDOW_INDEX=0 FAKE_TMUX_WINDOW_NAME="claude" \
  run "$START" --dry-run --dir "$HOME/projects/repoVT" repoVT-2
has "a window named claude vetoes nothing, so step 3b still stamps the cell" "$err" "the harness minted a new transcript"
# AND THE SAME UUID IS STILL REFUSED FROM A WINDOW NAMED FOR ANOTHER LANE. The
# register veto cannot reach it — no row names it — so this is the case veto 2
# exists for, and the one Evidence 2(b) actually was.
FAKE_TMUX_WINDOW="vtsess:@31" FAKE_TMUX_WINDOW_INDEX=0 FAKE_TMUX_WINDOW_NAME="repoVT-1" \
  run "$START" --dry-run --dir "$HOME/projects/repoVT" repoVT-2
has "…while the very same uuid IS vetoed from a window named for another lane" "$err" "which is another lane the register has a row for"
# THE ASSERTION IS ON THE PAYLOAD, NOT ON THE VERB. A vetoed run still prints
# `lane-start`'s own "stamp it as this session's first act" hint for the FRESH
# session it is about to mint, and that hint names `append-session-id` — which
# is the legitimate act, not the cross-lane write. What must never appear is the
# OTHER lane's uuid inside that cell edit, which is step 3b's own `→ harness
# <uuid>` payload.
hasnt "…so the other session's uuid reaches no cell edit of repoVT-2's row" "$err" "→ harness $VT_FRESH"

# AND VETO 2 FAILS CLOSED, WHICH UNTIL THIS ROUND IT DID NOT (`R-A11-12`, clause
# (d) rule 1 verbatim: *"Both reads fail closed: any answer but 0 naming another
# lane or 8 leaves the cell and the resume target alone, because here an empty
# answer is what PERMITS the take"*). The arm was `0) veto ;; *) : ;;`, so EVERY
# code but 0 permitted the take and a `register-row` that could not answer was
# read as "the session is free" — the one reading the ruling forbids. The
# register veto beside it (adoption act 0's, `3719d97`) has always been written
# this way and says so; this is the second layer catching up with it.
#
# The window is named for another lane and the live uuid is in NO row, so veto 1
# has nothing to fire on: this layer is the only thing between that session and
# repoVT-2's append-only cell.
cat > "$SANDBOX/vetoedit" <<'WRAP'
#!/usr/bin/env bash
case "${1-}:${2-}" in
  register-row:repoVT-1) printf 'register-row: simulated failure\n' >&2; exit "${VETO_RC:-1}" ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/vetoedit"
# 1 an environment failure · 2 the code an older helper and a name that is not
# lane-shaped both give · 6 a code no read of this window's name can legitimately
# answer with. None of the three is 0-naming-another-lane and none is 8.
for vrc in 1 2 6; do
	FAKE_TMUX_WINDOW="vtsess:@31" FAKE_TMUX_WINDOW_INDEX=0 FAKE_TMUX_WINDOW_NAME="repoVT-1" \
	  run env REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/vetoedit" VETO_RC="$vrc" \
	    "$START" --dry-run --dir "$HOME/projects/repoVT" repoVT-2
	has   "a window-name read exiting $vrc VETOES the take rather than permitting it" \
	      "$err" "is NOT taken as repoVT-2's"
	has   "…naming the code it came back with, so a failed read reads differently from a real row" \
	      "$err" "exited $vrc"
	hasnt "…so that session's uuid reaches no cell edit of repoVT-2's row" "$err" "→ harness $VT_FRESH"
	hasnt "…and it is not made repoVT-2's resume target either" "$err" "--resume $VT_FRESH"
	is    "…while the run itself still exits 0, because a veto is not a refusal" "$rc" 0
done
# AND 8 IS STILL PERMISSION, which is the half that keeps step 3b alive: a window
# whose lane-shaped name no row knows does not veto, and the take goes ahead.
cat > "$SANDBOX/vetoedit8" <<'WRAP'
#!/usr/bin/env bash
case "${1-}:${2-}" in
  register-row:repoVT-1) exit 8 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/vetoedit8"
FAKE_TMUX_WINDOW="vtsess:@31" FAKE_TMUX_WINDOW_INDEX=0 FAKE_TMUX_WINDOW_NAME="repoVT-1" \
  run env REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/vetoedit8" \
    "$START" --dry-run --dir "$HOME/projects/repoVT" repoVT-2
has "…while an 8 from that same read still PERMITS it — fail-closed is not refuse-always" \
    "$err" "the harness minted a new transcript"

rm -f "$sessions_dir/live-vt2.json"
rm -f "$sessions_dir/live-vt.json"
unset FAKE_TMUX_WINDOWS

echo "== Amendment 11 decision 7, as Amendment 18 Addendum 2 leaves it: \`lane <name>\` =="
#
# THE TWO SURFACES BRETT HEAP'S DIRECTION NAMES, and the count they met before
# this word existed. Measured on Eagle on 2026-09-13, after the tmux server was
# replaced: EACH MET 1 PROMPT OFFERING 2 CHOICES AND WAS OFFERED THE WRONG
# LANE — every `@id` on the workstation had been reissued from `@0`, four of
# five windows were named `claude`, and all five swap records named sessions
# from the old server, so the launcher's precedences 2 and 3 answered nothing
# and precedence 4 offered the workstation's newest swap, `openXfactory-5`, to a
# session that was `openRepoProject-1`. Declining was the only correct answer,
# and declining left the operator where they started.
#
# `lane <name>` needs no window, no record of a window and no guess: only the
# lane's name, its `dir` and its `profile`. Both cases below run it FOR REAL
# with stdin closed, so a command that asked anything would die rather than
# quietly pass.
#
# THE WORD IS `lane <name>` AND THE CASES ARE `restart <lane>`'s (AMENDMENT 18
# ADDENDUM 2, ratified 2026-09-14T16:50:32Z verbatim "ratify", on Brett Heap's
# ruling *"i think we can drop restart as a cli command … lane does all the
# things a user wants"*). The act is the same act — the launcher's path, the
# lane's own recorded directory and profile, asking nothing — so every case
# below is the case decision 7 was proved with, re-pointed at the word that is
# now on the person's PATH.
#
# TWO OF `restart`'s CASES ARE NOT HERE, AND BOTH BECAME SOMETHING ELSE: the
# bare word that restarted THIS WINDOW's lane, and the bare word that printed
# the per-repo listing and stopped. Bare `lane` is the numbered PICK (Addendum
# 1) and has its own section below, where the listing, the one question, each
# answer and the no-terminal case are run. Nothing that was asserted about the
# act is dropped; what moved is which word performs it.
LANE="$OPENREPOTOOLS_BIN_DIR/lane"
LANES_CMD="$OPENREPOTOOLS_BIN_DIR/lanes"
cat > "$SANDBOX/fakebin/pclaude" <<'FAKE'
#!/usr/bin/env bash
printf 'cwd=%s argv=%s\n' "$PWD" "$*" >> "${FAKE_PCLAUDE_LOG:-/dev/null}"
FAKE
chmod +x "$SANDBOX/fakebin/pclaude"
export FAKE_PCLAUDE_LOG="$SANDBOX/pclaude.log"
: > "$FAKE_PCLAUDE_LOG"

# THE LANE-NAME FENCE IS THE HELPER'S OWN, and it was a first-character test
# (#26 review of `3d06a2b`, `restart:268`). `[A-Za-z0-9]*)` pins one character,
# so a string that is not a lane name reached `register-row` and the person was
# told "the register has no row for lane repoA11-1/extra" — sent looking for a
# missing row instead of being told what they typed. The pattern moved to `lane`
# with the act, and `test_lane_fences_a_lane_name_the_way_the_helper_does` holds
# the two spellings to one rule.
run env -u TMUX "$LANE" "repoA11-1/extra" </dev/null
is   "lane refuses a lane name that is not one, whole-string" "$rc" 2
has  "…saying what a lane name is, in lanes-edit.sh's own words" "$err" "not opening with . or -"
hasnt "…and never reporting it as a missing row" "$err" "has no row for lane"
run env -u TMUX "$LANE" "repoA11-1 x" </dev/null
is   "…a space is refused too" "$rc" 2
# A `-`-LED WORD IS AN OPTION BEFORE `--` AND A LANE NAME AFTER IT, and both
# refusals are asked for: the parser's 64 for the word it cannot be, and the
# FENCE's own 2 for the name it is not. `restart` had only the second, because
# its parser spent 2 on an unknown option too.
run env -u TMUX "$LANE" "-repoA11-1" </dev/null
is   "…a leading dash is refused as the option it looks like" "$rc" 64
has  "…naming it as one" "$err" "unknown option '-repoA11-1'"
run env -u TMUX "$LANE" -- "-repoA11-1" </dev/null
is   "…and past \`--\`, where it can only be a name, the helper's own fence refuses it" "$rc" 2
has  "…in lanes-edit.sh's words again" "$err" "not opening with . or -"

# CASE 1 — A FRESH TERMINAL OUTSIDE TMUX. No window, no record of one, nothing
# to guess from.
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX "$LANE" repoA11-1 </dev/null
is   "lane <name> from a fresh terminal outside tmux exits 0" "$rc" 0
has  "…launching through the launcher, never \`claude\` itself (Evidence 4)" \
     "$(cat "$FAKE_PCLAUDE_LOG")" "argv=--lane repoA11-1 team-05a"
has  "…after cd-ing into the lane's own recorded directory (Evidence 3)" \
     "$(cat "$FAKE_PCLAUDE_LOG")" "cwd=$A11_DIR"
has  "…saying which profile it took and where from" "$out" "from the lane record"
hasnt "…and NOTHING is asked: no confirmation" "$out$err" "[y/N]"
hasnt "…and no question of any kind" "$out$err" "which?"

# THE LATE SWAP — `lane <name> <profile>` NAMES THE ACCOUNT (Brett Heap's
# refinement of 2026-09-14T14:1xZ, from his question "when do i use lane vs
# restart … they seem almost the same to me"): the recorded profile is what a
# person gets by typing nothing, and the second argument is how they switch,
# exactly as `pclaude --lane <lane> <profile>` already takes it.
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX "$LANE" repoA11-1 team-09z </dev/null
is   "lane <name> <profile> exits 0" "$rc" 0
has  "…handing the launcher the profile that was NAMED, not the one recorded" \
     "$(cat "$FAKE_PCLAUDE_LOG")" "argv=--lane repoA11-1 team-09z"
has  "…in the same recorded directory" "$(cat "$FAKE_PCLAUDE_LOG")" "cwd=$A11_DIR"
has  "…and saying the profile came from the command line" "$out" "named on the command line"

# EVIDENCE 7's LANE, AFTER THE ONE `--dir`: `lane` cd's into the checkout the
# record now names, which is the whole point of naming it once. Before the
# `lane-start --dir` above, this lane's record carried `home` and `estate` and
# no `dir` at all and the launcher's own derivation was
# `$PROJECTS_ROOT/opsXfactory`, which does not exist.
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX "$LANE" opsXfactory-5 </dev/null
is   "lane exits 0 for Evidence 7's lane once its directory is recorded" "$rc" 0
has  "…cd-ing into the nested checkout and not into \$PROJECTS_ROOT/<repo>" \
     "$(cat "$FAKE_PCLAUDE_LOG")" "cwd=$HOME/projects/xFactory/xFactories/OpsxFactory"
has  "…with the profile that one start recorded" \
     "$(cat "$FAKE_PCLAUDE_LOG")" "argv=--lane opsXfactory-5 team-03l"
# AND THE REFUSAL A LANE WITH NO RECORDED DIRECTORY STILL GETS is ONE LINE
# naming the act that RECORDS it — never an exit 1 with nothing on screen,
# which is what Evidence 7 actually met.
# A PROFILE AND NO DIRECTORY, because the profile is refused first and this case
# is about the OTHER refusal.
add_seed_row "| \`repoE7x-1\` | harness \`$E7_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA11/e7.md | ACTIVE |"
{ printf '# lane repoE7x-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoE7x-1, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoE7x-1 → home opensoft/repoE7x; estate repoE7x; profile team-05a\n' "$E7_ID"
} > "$LOGD/repoE7x-1.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a lane with a profile and no recorded directory"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX "$LANE" repoE7x-1 </dev/null
is   "lane refuses with 2 for a lane whose record names no directory" "$rc" 2
has  "…naming the act that RECORDS it, filled in" "$err" "lane-start --dir <the lane's checkout> repoE7x 1"
has  "…saying that later runs then read it back" "$err" "reads it back"
is   "…and launching nothing at all" "$(cat "$FAKE_PCLAUDE_LOG")" ""

# CASE 2 — THE SAME, TYPED IN A WINDOW NAMED `claude`. 8 of this workstation's
# 16 windows were in that state; the launcher's precedence 2 cannot fire in any
# of them, and precedence 3 cannot either, because a window `lane-start` never
# renamed had no swap written from it.
: > "$FAKE_PCLAUDE_LOG"
FAKE_TMUX_WINDOW_NAME=claude FAKE_TMUX_WINDOW="a11sess:@71" FAKE_TMUX_WINDOW_INDEX=0 \
  run "$LANE" repoA11-1 </dev/null
is   "lane <name> in a window named 'claude' exits 0" "$rc" 0
has  "…launching the same lane with the same profile, from the record" \
     "$(cat "$FAKE_PCLAUDE_LOG")" "argv=--lane repoA11-1 team-05a"
hasnt "…asking nothing here either" "$out$err" "[y/N]"

# A LANE WITH NO RECORDED PROFILE IS A REFUSAL AND NEVER A GUESS: a wrong
# profile is a launch into another account, and nothing here may invent one.
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX "$LANE" repoA11-2 </dev/null
is   "lane refuses a lane whose record names no profile" "$rc" 2
has  "…saying it will not guess, because a wrong profile is another account" "$err" "will not guess"
has  "…naming the form this word itself takes" "$err" "lane repoA11-2 <profile>"
has  "…and printing the launcher form that works in the interval" "$err" "pclaude --lane repoA11-2 <profile>"
is   "…launching nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""
# …AND THE SECOND ARGUMENT IS WHAT THAT REFUSAL NAMES, so it is run. This lane's
# record carries no `dir` either — it is the pre-clause-(c) shape — so `--dir`
# is named here too, which is the one run that proves the flag reaches the
# launcher rather than being resolved and dropped.
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX "$LANE" --dir "$A11_DIR" repoA11-2 team-05a </dev/null
is   "…while the profile named on the command line is enough for that same lane" "$rc" 0
has  "…launching it under the profile that was typed, with the directory named" \
     "$(cat "$FAKE_PCLAUDE_LOG")" "argv=--lane repoA11-2 --dir $A11_DIR_R team-05a"
has  "…from that directory, in the spelling the resolution gave it" \
     "$(cat "$FAKE_PCLAUDE_LOG")" "cwd=$A11_DIR_R"
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX "$LANE" repoNoSuch-9 </dev/null
is   "lane refuses a lane the register and the logs do not carry" "$rc" 2
has  "…saying so about the name that was typed" "$err" "no lane called 'repoNoSuch-9'"
has  "…and names the command that opens one" "$err" "lane-start <repo> <n>"
is   "…launching nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""

# A LANE NAME IS ONE NAME UNDER ANY CASE (Amendment 15). The one-lane read is
# asked for the spelling that was TYPED — one log rather than the estate's —
# and only where that answers nothing of the lane's own is the estate-wide read
# made and matched case-insensitively. Either way the act runs on the ROW'S OWN
# spelling, which is what `canon_lane` writes into every line below it.
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX "$LANE" REPOa11-1 </dev/null
is   "lane <name> resolves a name typed in another case" "$rc" 0
has  "…and launches the lane under the spelling the register carries" \
     "$(cat "$FAKE_PCLAUDE_LOG")" "argv=--lane repoA11-1 team-05a"
hasnt "…never the spelling that was typed" "$(cat "$FAKE_PCLAUDE_LOG")" "REPOa11-1"

# THE FAIL-CLOSED FAMILY, ON THE READS THIS SURFACE MAKES (#26; Brett Heap,
# "Take it first, then land"). Amendment 7(d) gives each answer its own code —
# `0` an answer · `8` NO ANSWER · `2` a helper predating the amendment that
# added the read · anything else a read that FAILED — and `restart` collapsed
# every one of them into the ordinary case at three sites. `lane` makes TWO
# reads in front of a launch, the rows and their grouping, and both are held to
# the same rule: a register that cannot be read is not "there are no lanes", and
# a grouping that failed is not "no lane is available".
: > "$FAKE_PCLAUDE_LOG"
cat > "$SANDBOX/rowbroke" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  lanes) printf 'lanes-edit: simulated failure\n' >&2; exit 6 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/rowbroke"
run env -u TMUX REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/rowbroke" "$LANE" repoA11-1 </dev/null
is    "a row read that FAILED refuses rather than falling through" "$rc" 1
has   "…saying what it is not, in Amendment 7(d)'s terms" "$err" "is NOT 'there are no lanes'"
is    "…and launches nothing at all" "$(cat "$FAKE_PCLAUDE_LOG")" ""
# …while the code that means AN OLDER WORKSTATION is named as one.
cat > "$SANDBOX/rowold" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  lanes) printf "lanes-edit: unknown subcommand 'lanes'\n" >&2; exit 2 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/rowold"
run env -u TMUX REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/rowold" "$LANE" repoA11-1 </dev/null
is    "a helper predating Amendment 11 is the contract's 2, not a read that failed" "$rc" 2
has   "…saying it is an un-upgraded workstation rather than a fault" "$err" "predates lane-collision-protocol Amendment 11"
has   "…and naming the one act that fixes it" "$err" "openRepoTools --install"
# THE GROUPING, which is the read Addendum 1 adds and the one that decides
# WHICH BRANCH a lane takes. A failure there is not "no lane is available".
: > "$FAKE_PCLAUDE_LOG"
cat > "$SANDBOX/grpbroke" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  lane-groups) printf 'lanes-edit: simulated failure\n' >&2; exit 6 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/grpbroke"
run env -u TMUX REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/grpbroke" "$LANE" repoA11-1 </dev/null
is    "a grouping read that FAILED refuses rather than guessing a branch" "$rc" 1
has   "…saying what THAT is not" "$err" "is NOT 'no lane is"
is    "…and launches nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""
cat > "$SANDBOX/grpold" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  lane-groups) printf "lanes-edit: unknown subcommand 'lane-groups'\n" >&2; exit 2 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/grpold"
run env -u TMUX REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/grpold" "$LANE" repoA11-1 </dev/null
is    "…and a helper predating Addendum 1 is the contract's 2 as well" "$rc" 2
has   "…naming the read that is missing" "$err" "lane-groups"
has   "…and the act that upgrades the workstation" "$err" "openRepoTools --install"
has   "…while still naming the read that answers today" "$err" "lanes"

# THE PLAN IS A THING A PERSON TYPES (#26, the review of `c3ebcfe`,
# `restart:472`). Clause (c) admits a directory with a SPACE in it — `lane-start`
# writes it quoted, which is what makes it one ref under 7(b), and `lane-dir`
# hands it back unquoted — so `cd /p/spaced dir` was a line that cd's into
# `/p/spaced`. `lane-start:550`'s one-line `quoted` has printed its own plan that
# way since it had one; the sibling command printed `${cmd[*]}`.
SPACE_ID="aaaa0007-5555-4000-8000-aaaa00075555"
mkdir -p "$HOME/projects/spaced dir"
add_seed_row "| \`repoSpace-1\` | harness \`$SPACE_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoA11/s.md | ACTIVE |"
{ printf '# lane repoSpace-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoSpace-1, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoSpace-1 → home opensoft/repoSpace; estate repoSpace; dir "%s"; profile team-05a\n' "$SPACE_ID" "$HOME/projects/spaced dir"
} > "$LOGD/repoSpace-1.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a lane whose recorded directory carries a space"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX "$LANE" --dry-run repoSpace-1 </dev/null
is    "lane --dry-run exits 0 for a lane whose directory has a space" "$rc" 0
has   "…printing a cd line that can be typed" "$out" "cd $HOME/projects/spaced\\ dir"
hasnt "…and never the one that cd's into half the path" "$out" "cd $HOME/projects/spaced dir"
has   "…and an exec line quoted the same way" "$out" "exec "
is    "…launching nothing, which is what --dry-run means" "$(cat "$FAKE_PCLAUDE_LOG")" ""
# AND THE ORDINARY PLAN IS UNCHANGED: a path with no space is printed as itself.
run env -u TMUX "$LANE" --dry-run repoA11-7 </dev/null
has   "a directory with nothing to quote is printed as itself" "$out" "cd $A11_DIR"
has   "…and the lane's own log answers for a lane with no swap record" "$out" "profile team-05a"
echo "== Amendment 11 decision 6: \`lanes\` =="
# ------- ruling 6: EVERY LANE BY DEFAULT, NARROWED INSIDE A CHECKOUT ---------
#
# A11 Addendum 4 ruling 6 was answered NO — clause (j)'s estate-wide default
# STANDS — over Brett Heap's settlement of 2026-09-13T20:38:11Z, verbatim
# "Narrow inside a checkout (Recommended)". So: the bare word outside any
# checkout is every lane the register and the logs know, whatever workstation
# they are on; inside a lane checkout it is THAT REPOSITORY's lanes and ends
# with the next free position; `--all` forces the first from anywhere; `--here`
# is the old workstation-scoped default, kept as an option.
#
# THE SUITE RUNS FROM A CHECKOUT — this repository's — so every bare `lanes`
# below would narrow to it. `--all` is what asks the estate-wide question, and
# the `--dir` cases are what ask the narrowed one.
run "$LANES_CMD" --all </dev/null
is   "lanes --all exits 0 with rows" "$rc" 0
has  "…and a lane of ANOTHER workstation is in it, which is clause (j)'s default" "$out" "repoA11-3"
run "$LANES_CMD" --here </dev/null
is   "lanes --here exits 0" "$rc" 0
hasnt "…and scopes to this workstation, which is what the old default did" "$out" "repoA11-3"
has   "…while this workstation's lanes are all there" "$out" "repoA11-1"
# THE NARROWING, AND THE HALF OF THE SETTLEMENT THAT IS NOT A FILTER.
run "$LANES_CMD" --prefix repoA11 </dev/null
is   "a narrowed listing exits 0" "$rc" 0
has  "…carrying the lanes named for that repository" "$out" "repoA11-1"
hasnt "…and nothing that is not" "$out" "repoA-1"
has   "…ending with the NEXT FREE POSITION" "$out" "next free position:"
has   "…and the exact line that takes it, filled in" "$out" "lane-start repoA11 "
has   "…with the way back to every lane" "$out" "lanes --all"
# THE LOWEST FREE ONE, not the highest plus one: repoA11-1..-8 exist in this
# fixture with gaps, and a register that hands out 12 while 9 is free grows a
# column nobody reads.
NEXTFREE="$(printf '%s\n' "$out" | sed -n 's/^ *next free position: *//p' | head -n1)"
is   "…which is the lowest position no lane of that repository holds" "$NEXTFREE" "9"
# THE NARROWING NAMES THE REPOSITORY `origin` NAMES, AND NOT THE DIRECTORY THIS
# SHELL IS STANDING IN. `basename $(git rev-parse --show-toplevel)` is a
# WORKTREE's own name inside one, so a bare `lanes` run in a worktree of
# `openRepoTools` called `ort-a11` narrowed to a repository called `ort-a11` and
# offered `lane-start ort-a11 1` — a lane whose `$PROJECTS_ROOT/<repo>` cannot
# exist. Every lane on this estate is named for the repository, which is what
# `origin` says. Proved in a worktree, because a plain clone cannot tell the two
# apart.
A11WT="$SANDBOX/a-worktree-named-nothing-like-its-repo"
git -C "$HOME/projects/repoA11" worktree add -q -b lanes-prefix-probe "$A11WT" 2>/dev/null \
  || git -C "$HOME/projects/repoA11" worktree add -q "$A11WT" 2>/dev/null || :
if [ -d "$A11WT" ]; then
  run env LANES_CWD_PROBE=1 sh -c 'cd "$1" && exec "$2" ' _ "$A11WT" "$LANES_CMD" </dev/null
  has   "the checkout narrowing names the repository origin names" "$out$err" "repoA11"
  hasnt "…and never the worktree directory it happens to be standing in" "$out$err" "a-worktree-named-nothing-like-its-repo"
  git -C "$HOME/projects/repoA11" worktree remove --force "$A11WT" 2>/dev/null || :
else
  skip "the checkout narrowing names the repository origin names" "git worktree add refused in this sandbox"
fi
# AN EMPTY REPOSITORY STILL GETS THE ANSWER A PERSON CAME FOR.
run "$LANES_CMD" --prefix repoNoLanesAtAll </dev/null
is   "a repository with no lanes exits 8" "$rc" 8
has  "…saying so in its own name" "$out" "no lane of repoNoLanesAtAll is recorded"
has  "…and still giving the next free position, which is 1" "$out" "next free position:  1"
has  "…and the line that takes it" "$out" "lane-start repoNoLanesAtAll 1"
# `lane-start <repo>` WITH NO POSITION LISTS AND SUGGESTS, and launches nothing.
: > "$FAKE_CLAUDE_LOG"
run "$START" repoA11
is    "lane-start <repo> with no position still exits 2" "$rc" 2
has   "…saying what it is" "$err" "is a repository and not a lane"
has   "…printing that repository's lanes" "$err" "repoA11-1"
has   "…and the next free position, filled in" "$err" "lane-start repoA11 "
has   "…while the refusal names the position it now has a listing for" "$err" "with a position from the listing above"
is    "…and launches nothing" "$(cat "$FAKE_CLAUDE_LOG")" ""
# AND THE REFUSAL PROMISES A LISTING ONLY WHERE ONE WAS MADE (#26, the review of
# `c3ebcfe`, `lane-start:602`). `|| :` made every code of that read the same
# code, so a `lanes` that FAILED still ended "with a position from the listing
# above" — pointing a person at its refusal. `0` and `8` both print one (8 is the
# empty repository, whose listing IS the next free position), `2` says in its own
# words that the workstation has not taken act 3's install, and anything else is
# a read that failed. Nothing of the listing is re-rendered here on any of them.
cat > "$SANDBOX/lsbroke" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  lanes) printf 'lanes-edit: simulated failure\n' >&2; exit 6 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/lsbroke"
: > "$FAKE_CLAUDE_LOG"
run env REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/lsbroke" "$START" repoA11
is    "lane-start <repo> still refuses with 2 when the listing read fails" "$rc" 2
has   "…naming the read that failed rather than being silent about it" "$err" "that listing FAILED (exit 1)"
hasnt "…and never pointing at a listing nobody got" "$err" "from the listing above"
has   "…while the form that works is still there" "$err" "is not a lane: a lane is <repo>-<position>"
is    "…and launches nothing" "$(cat "$FAKE_CLAUDE_LOG")" ""

# THE TWO SPELLINGS OF ONE FLAG GIVE ONE ANSWER (#26, the review of `c3ebcfe`,
# `lane-start:707`). `--dir ""` refuses; `--dir=` set the variable to nothing and
# fell through as if no directory had been named at all, so the rungs below it
# ran — one of which is `$PROJECTS_ROOT/<repo>` — and `lane-start --dir= <repo>
# <n>` started in a checkout the operator never asked for. `restart:151`, the
# same flag on the sibling command, has carried the guard on both spellings all
# along, which is what makes this a divergence rather than a decision.
: > "$FAKE_CLAUDE_LOG"
run "$START" --dir= repoA11 9
is    "lane-start --dir= refuses, exactly as --dir \"\" already did" "$rc" 2
has   "…in that arm's own words" "$err" "--dir needs a path"
is    "…and launches nothing" "$(cat "$FAKE_CLAUDE_LOG")" ""
run "$START" --estate= repoA11 9
is    "…and its neighbour --estate= the same" "$rc" 2
has   "…in ITS arm's own words" "$err" "--estate needs a name"

# AND THE MANUAL SAYS SO, which is RV-B4 one settlement on: the code took the
# narrowing in the round that documented the OPPOSITE, and `README-lanes.md`
# went on calling `lanes` "every lane on this workstation, newest write first"
# — the pre-settlement default, wrong twice over, because the scope is the
# ESTATE now and inside a checkout it is one repository. Nothing was red for it:
# no assertion had ever read that sentence. Read from `$SRC_DIR`, the checkout's
# own copy, which is the one a person opens.
ln_doc="$(cat "$SRC_DIR/docs/README-lanes.md" 2>/dev/null || :)"
has   "the manual quotes the settlement that narrowed the bare word" "$ln_doc" \
      "Narrow inside a checkout (Recommended)"
has   "…and the one that made \`lane-start <repo>\` list and suggest" "$ln_doc" \
      "Yes, list and suggest (Recommended)"
has   "…saying what a bare \`lanes\` lists inside a checkout" "$ln_doc" \
      "A bare \`lanes\` INSIDE a lane checkout lists **that repository's lanes**"
has   "…that it ends with the next free position and the line that takes it" "$ln_doc" \
      "free position** and the exact \`lane-start <repo> <n>\` that takes it, filled in."
has   "…that the position is the LOWEST free one, which is what this suite proves above" "$ln_doc" \
      "The position offered is the **lowest** one no lane of that repository holds,"
has   "…and the way back to every lane, which is the word the stale sentence lacked" "$ln_doc" \
      "\`lanes --all\`, and a bare \`lanes\` outside every checkout, are clause (j)'s"
hasnt "…never the pre-settlement default it documented while building the narrowing" "$ln_doc" \
      "every lane on this workstation"

run "$LANES_CMD" --all </dev/null
is   "lanes exits 0 with rows" "$rc" 0
has  "…naming this workstation's lanes" "$out" "repoA11-1"
has  "…with the recorded profile" "$out" "team-05a"
has  "…the recorded directory" "$out" "$A11_DIR"
has  "…and the exact line that binds a PAUSED lane, which is what column 10 is" "$out" "bind it: lane repoA11-1"
has  "…saying it read locally and how old that answer is" "$out" "read locally"
# F-X20 — COLUMN 10 IS *"for a **paused** lane"*, AND THE LISTING PRINTED ONE
# FOR EVERY STATE BUT `LIVE`. A lane whose last act was its last is not a lane
# a person restarts, and offering `lane <name>` for an `ENDED` or a `RETIRED`
# one is the listing telling them to reopen something that was closed on
# purpose. Two fixtures, because the two closing verbs are two words.
add_seed_row "| \`repoFX20-1\` | harness \`$A11_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoFX20/a.md | ENDED |"
add_seed_row "| \`repoFX20-2\` | harness \`$A11_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoFX20/b.md | RETIRED |"
{ printf '# lane repoFX20-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoFX20-1, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoFX20-1 → home opensoft/repoA11; estate repoA11; dir %s; profile team-05a\n' "$A11_ID" "$A11_DIR"
  printf 'ENDED — lane repoFX20-1, session %s@Eagle, 2026-09-12T11:00:00Z, lane:repoFX20-1 — window closing; NOTHING IN FLIGHT\n' "$A11_ID"
} > "$LOGD/repoFX20-1.md"
{ printf '# lane repoFX20-2 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoFX20-2, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoFX20-2 → home opensoft/repoA11; estate repoA11; dir %s; profile team-05a\n' "$A11_ID" "$A11_DIR"
  printf 'RETIRED — lane repoFX20-2, session %s@Eagle, 2026-09-12T11:00:00Z, lane:repoFX20-2 — not coming back\n' "$A11_ID"
} > "$LOGD/repoFX20-2.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed an ENDED and a RETIRED lane for column 10"
git -C "$WIP" push -q origin main
# `--all`, FOR THE REASON THIS SECTION'S OWN HEADER GIVES: the suite runs from a
# checkout, so a bare word here asks the NARROWED question and these four
# assertions are about the estate-wide listing. They were bare and were the four
# red ones at `0303baa` — the listing they read was "no lane of <this checkout>
# is recorded", which is the right answer to a question they were not asking.
run "$LANES_CMD" --all </dev/null
has   "an ENDED lane is still a row in the listing" "$out" "repoFX20-1"
hasnt "…with no line that binds it, because column 10 is a PAUSED lane's" "$out" "lane repoFX20-1"
has   "a RETIRED lane is still a row too" "$out" "repoFX20-2"
hasnt "…and gets no line that binds it either" "$out" "lane repoFX20-2"
has   "…while a PAUSED lane still gets one, so the column still means something" "$out" "bind it: lane repoA11-1"
run "$LANES_CMD" --here </dev/null
hasnt "a lane of ANOTHER workstation is not in the --here listing" "$out" "repoA11-3"
run "$LANES_CMD" --all </dev/null
has  "…and the default estate-wide listing has it" "$out" "repoA11-3"
run "$LANES_CMD" --repo opensoft/repoA11 </dev/null
is   "lanes --repo narrows to one repository's lanes" "$rc" 0
has  "…which is decision 7's per-repo listing, read through the same helper" "$out" "repoA11-1"
# THE CONTRACT'S FOUR CODES, WHICH ARE NOT THE ONES THIS COMMAND USED (F-X4).
# SPEC §15 and clause (h)'s row for the read behind it: `0` rows · `8` none ·
# `64` usage · `2` a helper predating Amendment 11. A typo exited 2, where the
# contract gives 64; and a workstation whose helper predates this amendment —
# every workstation until adoption act 3's install reaches it — exited 1, the
# code for a read that broke.
# `--all` CLEARS THE LABEL AS WELL AS THE FILTERS, IN EITHER ORDER. The helper's
# `--all` drops `--repo`, `--dir` and `--prefix`, so the ROWS were always right;
# `here_repo` is the wrapper's own, and `lanes --all --prefix repoA11` listed
# every lane in the estate under a footer that said "of repoA11" and offered a
# next free position computed from one repository's rows (#26 review of
# `3d06a2b`, `lanes:143`).
run "$LANES_CMD" --all --prefix repoA11 </dev/null
is    "lanes --all --prefix exits 0" "$rc" 0
has   "…listing every lane, which is what --all asks for" "$out" "repoA11-3"
hasnt "…and labelling the count for no repository" "$out" "of repoA11,"
hasnt "…nor offering a next free position it did not narrow to" "$out" "next free position"
run "$LANES_CMD" --prefix repoA11 --all </dev/null
is    "…and the other order is the same command" "$rc" 0
has   "…with the same every-lane listing" "$out" "repoA11-3"
hasnt "…and the same absent label" "$out" "of repoA11,"
# …while `--prefix` ALONE still narrows and still offers the position.
run "$LANES_CMD" --prefix repoA11 </dev/null
has   "a --prefix on its own still names the repository in its count" "$out" "of repoA11,"
has   "…and still ends with the next free position" "$out" "next free position"
# AND `--all` IS ABSOLUTE OVER `--lane` TOO, which the helper's own reset left
# standing (#26, the review of `c3ebcfe`, `lanes-edit.sh:3999`). `--lane` is the
# narrowest selector there is and it clears the other four for itself, so
# `--all --lane X` answered about ONE lane under the flag whose comment has said
# "LAST AND ABSOLUTE" since it was written. The wrapper takes no `--lane`, so
# this is asked of the helper, which is where the selector lives.
run "$E" lanes --all --lane repoA11-1
is    "lanes --all --lane exits 0" "$rc" 0
has   "…listing every lane, which is what --all asks for" "$out" "repoA11-3"
run "$E" lanes --lane repoA11-1
is    "…while --lane on its own is still the one-lane read restart makes" "$rc" 0
hasnt "…and still reads one log rather than the estate's" "$out" "repoA11-3"

run "$LANES_CMD" repoA11-1 </dev/null
is   "lanes takes no positional argument, and spends the contract's 64 on it" "$rc" 64
has  "…and points at the command that does" "$err" "lane repoA11-1"
run "$LANES_CMD" --repo </dev/null
is   "…and a flag with no value is refused rather than guessed, with the same 64" "$rc" 64
run "$LANES_CMD" --nosuchflag </dev/null
is   "…as is an option it has never heard of" "$rc" 64
# AND `2` IS KEPT FOR THE ONE THING THE CONTRACT GIVES IT. A helper with no
# `lanes` subcommand exits 2 (`lanes-edit.sh:4818-4826`), which is expected and
# silent rather than broken, and the command must not report it as a read that
# failed.
cat > "$SANDBOX/oldedit" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  lanes) printf "lanes-edit: unknown subcommand 'lanes'\n" >&2; exit 2 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/oldedit"
run env REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/oldedit" "$LANES_CMD" </dev/null
is   "a lanes-edit.sh predating Amendment 11 is the contract's 2, not a read that failed" "$rc" 2
has  "…saying it is an un-upgraded workstation rather than a fault" "$err" "predates lane-collision-protocol Amendment 11"
has  "…and naming the one act that fixes it" "$err" "openRepoTools --install"
# A read that genuinely broke is still 1, so the two are told apart.
cat > "$SANDBOX/brokeedit" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  lanes) printf 'lanes-edit: simulated failure\n' >&2; exit 6 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/brokeedit"
run env REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/brokeedit" "$LANES_CMD" </dev/null
is   "…while a read that actually failed stays 1, and is never read as 'no lanes'" "$rc" 1
has  "…saying so in Amendment 7(d)'s words" "$err" "NOT 'there are no lanes'"
# A FETCH THAT DID NOT ANSWER IS NOT A FETCH, AND THE FOOTER MAY NOT SAY IT WAS
# (#26's fail-closed family, `lanes:236`; Brett Heap, "Take it first, then
# land"). A read in front of a launch MAY NOT REFUSE, so `log_sync` falls back
# to the local refs, says so on stderr — *"fetch failed — reading the logs as
# they stand locally"* (`lanes-edit.sh:2902`) — and answers 0. This command
# threw that sentence away and printed "as of a fetch just now" over it: the one
# line a person reads to decide whether the answer is CURRENT, asserting the
# opposite of what the run had already been told.
#
# THE STUB IS THE HELPER IN THAT STATE, not a broken one: it prints the same
# sentence on stderr and still answers from the local refs, exit 0.
cat > "$SANDBOX/fetchfallback" <<'WRAP'
#!/usr/bin/env bash
if [ "${1-}" = lanes ]; then
  printf 'lanes-edit: fetch failed — reading the logs as they stand locally\n' >&2
  shift
  ff_args=()
  for ff_a in "$@"; do [ "$ff_a" = --fetch ] || ff_args+=("$ff_a"); done
  exec "$REAL_LANES_EDIT" lanes ${ff_args[@]+"${ff_args[@]}"}
fi
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/fetchfallback"
run env REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/fetchfallback" "$LANES_CMD" --fetch --all </dev/null
is    "lanes --fetch still exits 0 when the fetch did not answer" "$rc" 0
has   "…and the rows are there, because a read in front of a launch may not refuse" "$out" "repoA11-1"
has   "…while the footer says the answer is LOCAL" "$out" "read LOCALLY: the fetch did not answer"
has   "…quoting the helper's own sentence rather than a copy of it" "$out" "reading the logs as they stand locally"
hasnt "…and never claims a fetch it did not get" "$out" "as of a fetch just now"
# AND THE EMPTY LISTING IS THE CASE THAT MATTERS MOST: "no lane is recorded",
# read off a stale checkout, is the answer a person is likeliest to act on.
run env REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/fetchfallback" "$LANES_CMD" --fetch --prefix repoNoLanesAtAll </dev/null
is    "an empty listing after a fetch that fell back still exits 8" "$rc" 8
has   "…saying so in its own name" "$out" "no lane of repoNoLanesAtAll is recorded"
has   "…and that the fetch did not answer, which is why it may be stale" "$out" "the fetch did not answer"
# …while a fetch that DID answer says so, so the sentence keeps its meaning.
run "$LANES_CMD" --fetch --all </dev/null
is    "a fetch that answered exits 0" "$rc" 0
has   "…and says it is as of a fetch just now" "$out" "as of a fetch just now"
hasnt "…with no fallback notice anywhere in it" "$out" "the fetch did not answer"

# THE QUIET HALF OF THE SAME DEFECT (#26, the review of `c3ebcfe`, `lanes:411`).
# `43b6320` closed the LOUD path — the fetch was attempted, failed, and the
# helper said so. FOUR ways out of `log_sync` never reach the fetch at all and
# said NOTHING: `LANES_NO_GIT=1`, a `LANES_NO_FETCH=1` already in the
# environment, a `$LANES_REPO` that is not a checkout, and an
# `origin/$LANES_BRANCH` `ls-remote` could not confirm — the TIMEOUT among them.
# On every one of them `--fetch` printed "as of a fetch just now" over a fetch
# that never ran. The helper records WHY and the `lanes` arm says it in the one
# phrase the wrapper already reads.
run env LANES_NO_FETCH=1 "$LANES_CMD" --fetch --all </dev/null
is    "lanes --fetch with LANES_NO_FETCH=1 already set still exits 0" "$rc" 0
has   "…with the rows, because a listing may not refuse over a freshness note" "$out" "repoA11-1"
hasnt "…and never claims the fetch it was told not to make" "$out" "as of a fetch just now"
has   "…saying instead that the answer is LOCAL" "$out" "read LOCALLY: the fetch did not answer"
has   "…and naming which of the four reasons this run had" "$out" "LANES_NO_FETCH=1 is set in this environment"
run env LANES_NO_GIT=1 "$LANES_CMD" --fetch --all </dev/null
is    "…and the same for a run in which nothing touches git" "$rc" 0
hasnt "…which also never says 'just now'" "$out" "as of a fetch just now"
has   "…and names ITS reason rather than the other one" "$out" "LANES_NO_GIT=1 is set"
# THE HELPER SAYS IT ONLY UNDER `--fetch`, because without it the local read is
# the documented default (SPEC rev 4 §15) and the notice would be a line saying
# the command did what it was asked.
run "$LANES_CMD" --all </dev/null
hasnt "a listing with no --fetch carries no no-fetch notice of its own" "$out" "NO FETCH WAS MADE"
hasnt "…on stderr either" "$err" "NO FETCH WAS MADE"

# AND THE CAPTURE FILE THAT COULD NOT BE MADE THREW THE SAME NOTICE AWAY (#26,
# the review of `c3ebcfe`, `lanes:280`). `mktemp` under a `$TMPDIR` that does not
# exist fails, and this command's fallback ran the read with `2>/dev/null` — the
# exact line the fix above replaced — so the footer went back to asserting a
# fetch it could not check. The notes go to the terminal now and the footer says
# it does not know.
run env TMPDIR="$SANDBOX/no-such-tmpdir" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/fetchfallback" "$LANES_CMD" --fetch --all </dev/null
is    "lanes --fetch with no usable TMPDIR still exits 0" "$rc" 0
has   "…with the rows" "$out" "repoA11-1"
hasnt "…and never claims a fetch it could not check on" "$out" "as of a fetch just now"
has   "…saying in terms that it does not know" "$out" "whether the fetch answered is UNKNOWN"
has   "…while the helper's own notes reach the person instead of /dev/null" "$err" "reading the logs as they stand locally"

# A RECORDS TREE THAT COULD NOT BE READ IS NOT A LANE WITH NO FORK (#26, the
# review of `37632b1`). `session_files` returns 1 and sets its own message for
# exactly that case — `live-holder` has refused on it since `R-A8-3`, which this
# suite proves a thousand lines above — but `session_records` read it through
# `|| :` inside a `$( )`, which discards the status with the subshell, and
# `fork_map`, `live_session_ids` and `lane_forks` each read THEIR source inside a
# HERE-DOCUMENT, where a substitution's status is discarded outright. The empty
# answer was then CACHED for the life of the process. So `forks` answered 8 —
# "no fork of it is live" — and the refusal its own arm has carried since it was
# written was UNREACHABLE.
#
# THE SAME FIXTURE THE `live-holder` CASES USE, and the same reason: the tree
# itself, not a path through it.
if [ "$(id -u)" = 0 ]; then
  skip "an unreadable records tree is a refusal and not 'no fork of it is live'" "running as root, which can read a mode-000 tree"
else
  # THE FORK FIXTURE, RE-MADE: the retire cases removed it above, and these two
  # answers are about a fork that IS live. Removed again below, so nothing after
  # this block sees a world this block made.
  printf '{"type":"custom-title","customTitle":"repoA-1","sessionId":"%s"}\n' "$FORK_ID" > "$fork_tdir/$FORK_ID.jsonl"
  printf '{"pid":%s,"sessionId":"%s","cwd":"/workspace","procStart":"%s","kind":"bg","name":"openrepoproject-b9","status":"busy"}\n' \
    "$LIVE_PID" "$FORK_ID" "$live_start" > "$sessions_dir/live-fork.json"
  chmod 000 "$profiles_root"
  run "$E" forks repoA-1
  is    "forks exits 1 where this workstation's session records could not be read" "$rc" 1
  has   "…saying what that is NOT, in its own arm's words" "$err" "That is NOT 'no fork of it is live'"
  run "$E" who --lane repoA-1
  hasnt "…and who names no DEFECT it could not establish" "$out" "DEFECT"
  has   "…saying instead, in terms, that it could not look" "$out" "is NOT established"
  # THE LISTING ANSWERS AND SAYS WHAT IT COULD NOT ESTABLISH, which is
  # `43b6320`'s rule for the fetch: this is the read a person makes in FRONT of
  # a launch, and the collision itself is refused one surface along, by
  # `lane-start`'s own direct read of the same records.
  run "$LANES_CMD" --all </dev/null
  is    "a listing still ANSWERS where the records could not be read" "$rc" 0
  has   "…with the rows" "$out" "repoA11-1"
  has   "…and the notice, which reaches the person now the local read's stderr is kept" "$err" "session records could not be read"
  has   "…saying what that costs the STATE column" "$err" "may show as IDLE or PAUSED"
  chmod 755 "$profiles_root"
  run "$E" forks repoA-1
  is    "…while a readable tree still finds the fork" "$rc" 0
  has   "…naming the fork's own id" "$out" "$FORK_ID"
  rm -f "$sessions_dir/live-fork.json" "$fork_tdir/$FORK_ID.jsonl"
  run "$LANES_CMD" --all </dev/null
  hasnt "…and a listing off a readable tree carries no notice at all" "$err" "session records could not be read"
fi

# A RELATIVE `--dir` NAMED TWO DIRECTORIES (#26, the review of `37632b1`,
# `restart:505`). `restart` cd's into the directory and then execs the launcher
# WITH THE SAME STRING, which `lane-start` resolves a second time — from the new
# working directory — so `--dir ../x` meant one checkout to the test here and
# another to the launch. Asked with `--dry-run`, which prints the exact argv.
# THE EXPECTATION IS COMPUTED THE WAY THE CODE COMPUTES IT, and that is not
# pedantry: `pwd -P` is the estate's own idiom for this (`lanes_rows` resolves
# `--dir` with it), and on macOS `/var` is a symlink to `/private/var`, so the
# resolved path of this sandbox is the physical one and the sandbox's own
# spelling is not. Asserting the sandbox's spelling would be asserting that the
# path was NOT resolved on the one runner where the two differ. `$A11_DIR_R` is
# that spelling, computed once beside `$A11_DIR` itself.
run env -u TMUX -C "$A11_DIR" "$LANE" --dry-run --dir . repoA11-1 </dev/null
is    "lane --dry-run with a relative --dir exits 0" "$rc" 0
has   "…and the launcher is handed the directory RESOLVED, not the relative spelling" "$out" "--dir $A11_DIR_R"
hasnt "…never the '.' that means something else after the cd" "$out" "--dir ."
has   "…and the cd goes to the same resolved path" "$out" "cd $A11_DIR_R"

# THE INSTALLER'S STAGING COMMENT COUNTED FOUR FILES OF ELEVEN (#26, the review
# of `37632b1`, `openRepoTools:226`) — the same defect as the stale artifact
# counts `2f44da0` corrected, and the fix is to spell NO number where the code
# below already derives every one it prints.
ort_text="$(cat "$SRC_DIR/openRepoTools")"
hasnt "the installer's staging block no longer counts four of eleven files" "$ort_text" "ALL FOUR IN HAND"
hasnt "…nor says each of the four is fetched at this ref" "$ort_text" "each of the four is fetched"
has   "…and says it in the words that cannot go stale" "$ort_text" "ALL OF THEM IN HAND"
has   "…while the counts it PRINTS stay derived from the list itself" "$ort_text" '${#INSTALLABLES[@]} files or none'

# A HELPER PREDATING THE READ IS NOT A CONTAINER (#26, the review of `29d3417`,
# `skills/lane-swap/SKILL.md:70`). `workstation` is one of Amendment 11's reads,
# so a `lanes-edit.sh` that has not taken act 3's install exits 2 and prints
# nothing — and `-z "$ws"` alone then told the operator of an ordinary host that
# they were in a container with `$LANES_WORKSTATION` unset, a sentence they
# cannot act on. Until the install reaches every workstation, 2 is the answer
# every one of them gives (`R-A11-8`), which makes this the common case. The
# block is EXTRACTED FROM THE FILE and run against a helper in each state.
swsk_ws_blk="$(awk '/^ws_pair=""; ws_rc=0$/,/^fi$/' "$SWSK")"
is   "the swap skill carries its workstation read as a fenced step" \
     "$( [ -n "$swsk_ws_blk" ] && printf yes || printf no )" "yes"
swap_ws_probe() {   # <helper exit code> <what it prints>
  ( L="$SANDBOX/dirhelper"; STUB_RC="$1"; STUB_OUT="$2"; export STUB_RC STUB_OUT
    eval "$swsk_ws_blk"
    printf ' ws=[%s] missing=[%s]' "$ws" "${ws_missing:-}" )
}
has  "a workstation the helper named is taken, and nothing is said" \
     "$(swap_ws_probe 0 "$(printf 'Eagle\tseam')")" "ws=[Eagle] missing=[]"
has  "…a helper predating the read names the INSTALL, not a container" \
     "$(swap_ws_probe 2 '')" "NO WORKSTATION READ"
has  "…saying which code it came back with" "$(swap_ws_probe 2 '')" "exited 2 and named none"
has  "…and still stopping the writes, because a record filed under nothing is the placeholder R-A11-14 refuses" \
     "$(swap_ws_probe 2 '')" "missing=[1]"
hasnt "…while never calling that host a container" "$(swap_ws_probe 2 '')" "this is a container"
has  "…and a container with no value still gets ITS own sentence" \
     "$(swap_ws_probe 0 "$(printf 'abc123\tcontainer-unset')")" "NO WORKSTATION: this is a container"
has  "…with the writes stopped there too" \
     "$(swap_ws_probe 0 "$(printf 'abc123\tcontainer-unset')")" "missing=[1]"

# STEP 2(d) IS TERMINAL, WHICH THE BLOCK SAID EVERYWHERE BUT IN ITS CODE (#26,
# the review of `29d3417`, `skills/restart/SKILL.md:134`).
rskill_text="$(cat "$RSKILL")"
has   "the skill's listing rung stops where the outcome table ends it" "$rskill_text" "NO LANE FOR THIS WINDOW [8] —"
has   "…on the code the table gives it" "$rskill_text" "exit 8"
# AND THE READ IT ENDS ON GOES THROUGH THE FENCE (#26, the review of `90cef58`).
# It was the last read in the file that ignored its own status, and once the rung
# ENDS in an outcome a `lanes` that exited 1 or 64 would print as [8] — a refusal
# turned into a no-answer, at the rung whose next act CREATES a row.
has   "…and its listing read goes through the same fence as every other" \
      "$rskill_text" 'lread listing "'"'"'no lane of this checkout is in the register'"'"'" lanes'
hasnt "…with no read left outside it" "$rskill_text" 'LANES_NO_FETCH=1 "$L" lanes ${origin'

# AND `--retire` WRITES NOTHING, WHICH THREE SURFACES STILL SAID IT DID (#26,
# the review of `29d3417`). The act is the DOOR to Amendment 6(d) and performs
# none of it: a `RETIRED` carrying a payload is a seventh edit to in-force text
# and Amendment 7(b) gives that verb none. `lanes`'s own FOOTER has said so
# since it was written; its header comment, the helper's parser comment and the
# manual's paragraph had not caught up.
lanes_text="$(cat "$SRC_DIR/lanes")"
le_text="$(cat "$SRC_DIR/lanes-edit.sh")"
hasnt "the listing no longer says the retire act writes a record" "$lanes_text" "which writes the record that"
has   "…it says what the act does, which is prove and print" "$lanes_text" "which PROVES the pid or uuid is"
hasnt "the helper's parser comment no longer says one writer still writes that line" "$le_text" '`<pid|uuid>` writes `RETIRED'
has   "…it names the line as the legacy an append-only log still carries" "$le_text" "NOTHING WRITES ONE ANY MORE"
hasnt "the manual no longer promises an Amendment 6(d) record" "$ln_doc" "which writes the Amendment 6(d) record"
has   "…and says in terms that it writes nothing" "$ln_doc" "**It writes nothing**"
# A PAUSED LANE WITH NO RECORDED PROFILE GETS NO `restart` LINE — it gets the
# form that works, with the profile named as the one token to supply.
has  "a lane with no recorded profile is offered the launcher form, not a line it cannot type" \
     "$(run "$LANES_CMD" --all </dev/null; printf '%s' "$out")" "pclaude --lane repoA11-2 <profile>"

# THE CONTAINER NOTICE PRINTS, AND IT NAMES THE VARIABLE RATHER THAN THE KEY
# `R-A11-14` REJECTED (F-X1). The branch it hung on was `hostname-in-container`,
# a source `lanes_workstation_pair` has never emitted, so the notice was DEAD;
# and the act it named — a top-level `workstation:` line in `workspace.yaml` — is
# the alternative this toolset refuses by name (`lanes-edit.sh:337-339`), from a
# command that could not execute to name it.
#
# THE EMPTY LISTING IS THE CASE THAT MATTERS. With no `LANES_WORKSTATION` inside
# a container the workstation column is the CONTAINER'S id, so no row matches and
# the read exits 8 — the reader whose lanes have just vanished is exactly the one
# owed the sentence, and a notice printed only after rows would never reach them.
run env -u LANES_WORKSTATION LANES_IN_CONTAINER=1 "$LANES_CMD" </dev/null
has  "lanes inside a container with no configured workstation says so" "$out" "LANES_WORKSTATION"
has  "…in the one sentence its own writers refuse with" "$out" "is the CONTAINER"
has  "…naming the launcher whose job the value is" "$out" "launcher"
hasnt "…and never the \`workstation:\` key R-A11-14 rejected by name" "$out" "workstation: "
hasnt "…nor the source token nothing in the estate emits" "$out" "hostname-in-container"
# AND IT IS SILENT ON EVERY ORDINARY RUN, so the notice means what it says.
run "$LANES_CMD" </dev/null
hasnt "…while a run whose seam answered prints no container notice at all" "$out" "LANES_WORKSTATION"

echo "== Amendment 12: the name guard and the lock =="

# THE THREE NAMES, AND WHAT HAPPENS WHEN THEY ARE NOT ONE. Every case below
# feeds the guard a `UserPromptSubmit` payload on stdin and reads its exit code
# and its stderr, which is what the harness shows a person: 2 BLOCKS the prompt,
# 0 lets it through silently. The sandbox's fake tmux logs the `send-keys`, so
# the LOCK's one act on a pane is watched rather than assumed.
#
# THE FIXTURE THIS SECTION BORROWS IS CAPTURED AND PUT BACK, and that is not
# tidiness either: this section sits BETWEEN two others in one long file, it
# needs a `$FAKE_TMUX_WINDOWS` of its own for the targeted reads the lock makes,
# and a section that left the sandbox's window table unset would be changing the
# premise of every case after it from a distance. Captured here, restored at the
# end, so the Amendment 15 section below reads exactly what it read when it was
# written against `main`.
# A LIVE PROCESS OF THIS SECTION'S OWN, AND IT HAS TO BE ITS OWN. `$G_OUT` —
# the liveness section's second process — is KILLED at the end of that section,
# hundreds of cases above this one, so a record naming it is a record
# `record_is_live` correctly judges dead, and a duplicate that is not live is no
# duplicate at all: the guard exits 0, `lane-start` binds, and `lane-end
# --retire` answers 8. Every Amendment 18(h) case here rests on this pid being
# alive, so it is started here and killed at the end of the section.
sleep 3000 & GD_DUP=$!
gd_dup_start="$(cut -d' ' -f22 "/proc/$GD_DUP/stat" 2>/dev/null || printf '')"
GD_SAVE_WINDOWS="${FAKE_TMUX_WINDOWS-}"
GD_SAVE_WINDOW="${FAKE_TMUX_WINDOW-}"
GD_SAVE_NAME="${FAKE_TMUX_WINDOW_NAME-}"
GD_OLD_ID="aaaa0012-0000-4000-8000-aaaa00120000"
GD_LANE_ID="aaaa0012-1111-4000-8000-aaaa00121111"
GD_FREE_ID="aaaa0012-2222-4000-8000-aaaa00122222"
"$E" add-row "| \`repoGD-1\` | harness \`$GD_OLD_ID\` → harness $GD_LANE_ID (transcript uuid; profile t1) | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoGD/x.md | ACTIVE |" >/dev/null 2>&1
"$E" add-row "| \`repoGD-2\` | none recorded | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoGD/y.md | ACTIVE |" >/dev/null 2>&1
mkdir -p "$HOME/projects/repoGD"
git init -q -b main "$HOME/projects/repoGD"
git -C "$HOME/projects/repoGD" remote add origin "https://github.com/opensoft/repoGD.git"
# THE BINDING (Amendment 18(b)) — the lane's last STARTED, which clause (h)
# rule 2 compares a person's `nameSince` against.
run env LANES_LANE=repoGD-1 LANES_SESSION="$GD_LANE_ID" "$E" log STARTED "lane:repoGD-1" --home opensoft/repoGD
is   "the guard lane has a STARTED line, which is its binding" "$rc" 0

# ANOTHER PROFILE'S `sessions/` DIRECTORY, MADE ONCE AT THE TOP OF THE SECTION:
# Amendment 18(h)'s duplicate sat in one when it was measured, and three blocks
# below need it — the offer's answer, the duplicate refusals and clause (f)'s
# line. It is a variable this file reads under `set -u`, so it is defined before
# the first case rather than beside the first one that happened to need it.
gd_t2="$HOME/.claude-profiles/profiles/opensoft/team/t2/sessions"
mkdir -p "$gd_t2"

# The sandbox's window: `gdsess:@12`, pane `%12`, running claude.
export FAKE_TMUX_WINDOW="gdsess:@12"
export FAKE_TMUX_WINDOW_NAME=repoGD-1
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude"

# The fields the older writers never wrote: `nameSince`, which is an epoch in
# MILLISECONDS on this estate's real records (measured 2026-09-14), and `kind`.
write_record_a12() { # <file> <sessionId> <pid> <procStart> <kind> <tmux|-> <name> <nameSource|-> <nameSince|->
  a_f="$1"; a_sid="$2"; a_pid="$3"; a_start="$4"; a_kind="$5"
  a_tgt="$6"; a_name="$7"; a_src="$8"; a_since="$9"
  a_t=""; [ "$a_tgt" = "-" ] || a_t="$(printf ',"tmux":"%s"' "$a_tgt")"
  a_ns=""; [ "$a_src" = "-" ] || a_ns="$(printf ',"nameSource":"%s"' "$a_src")"
  a_si=""; [ "$a_since" = "-" ] || a_si="$(printf ',"nameSince":%s' "$a_since")"
  printf '{"pid":%s,"sessionId":"%s","cwd":"%s/projects/repoGD","procStart":"%s","kind":"%s"%s,"name":"%s"%s%s,"status":"busy","updatedAt":9000}\n' \
    "$a_pid" "$a_sid" "$HOME" "$a_start" "$a_kind" "$a_t" "$a_name" "$a_ns" "$a_si" > "$a_f"
  return 0
}
gd_rec() {   # <sessionId> <name> <nameSource|-> <nameSince|->
  write_record_a12 "$sessions_dir/gd.json" "$1" "$LIVE_PID" "$live_start" interactive "gdsess:@12.%12" "$2" "$3" "$4"
}
gd_hook='{"session_id":"%s","cwd":"%s","prompt":"%s","hook_event_name":"UserPromptSubmit"}'
# `${3-…}` AND NOT `${3:-…}`: an EMPTY cwd is a case of its own — a payload
# that names none is an indeterminate read, not "outside the projects root" —
# and `:-` would substitute the default for it and test nothing.
gd_run() {   # <session id> [<prompt>] [<cwd>]
  out="$(printf "$gd_hook" "$1" "${3-$HOME/projects/repoGD}" "${2-do the work}" | "$E" guard 2>"$SANDBOX/stderr")"; rc=$?
  err="$(cat "$SANDBOX/stderr")"
  return 0
}
gd_keys() { grep -c 'send-keys' "$FAKE_TMUX_LOG" || :; }
# A rename a person made an hour ago is OLDER than the binding written a moment
# ago; one an hour from now is newer. The clock is read once, in milliseconds.
gd_now_ms="$(( $(date -u +%s) * 1000 ))"
GD_OLD_MS="$(( gd_now_ms - 3600000 ))"
GD_NEW_MS="$(( gd_now_ms + 3600000 ))"

# ---- THE AGREEING CASE IS SILENT, AND THAT IS THE PROPERTY THAT MAKES A HOOK
# AT EVERY PROMPT BEARABLE AT ALL.
gd_rec "$GD_LANE_ID" repoGD-1 user "$GD_OLD_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "the three names agreeing exits 0" "$rc" 0
is    "…silently: a guard that speaks when nothing is wrong is a guard people turn off" "$err" ""
is    "…and types nothing into the pane" "$(gd_keys)" "$gd_before"

# ---- CLAUSE (e)'s TWO EXEMPTIONS.
gd_run "$GD_LANE_ID" "do the work" "$SANDBOX/elsewhere"
is    "a cwd outside the projects root exits 0 — a name there is a title and nothing more (D1)" "$rc" 0
is    "…silently" "$err" ""
out="$(printf '{"session_id":"%s","cwd":"%s/projects/repoGD","agent_id":"agent-7","prompt":"x"}' "$GD_LANE_ID" "$HOME" | "$E" guard 2>"$SANDBOX/stderr")"; rc=$?
err="$(cat "$SANDBOX/stderr")"
is    "a SUBAGENT's prompt exits 0 — subagents do not submit prompts and the lane that runs them has passed" "$rc" 0
is    "…silently" "$err" ""

# ---- (b) ROW 3: THE LOCK RENAMES IT, AND SAYS SO.
gd_rec "$GD_LANE_ID" repogd-7e derived "$GD_OLD_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "a session named something that is no lane BLOCKS the prompt" "$rc" 2
has   "…printing the triple as it stands" "$err" "THE NAME GUARD REFUSES THIS PROMPT"
has   "…the window" "$err" "window   gdsess:@12 'repoGD-1'"
has   "…the session, with the nameSource the lock turns on" "$err" "session  $GD_LANE_ID 'repogd-7e' (nameSource derived)"
has   "…and the row it is measured against" "$err" "row      \`repoGD-1\` — last session $GD_LANE_ID"
has   "…and THE LOCK renames it rather than asking a person to" "$err" "SO IT HAS BEEN RENAMED FOR YOU"
is    "…by typing into this pane, once (M1: the only path a running session's name has)" "$(( $(gd_keys) - gd_before ))" 1
has   "…the one line there is to type" "$(tail -n1 "$FAKE_TMUX_LOG")" "send-keys -t %12 /rename repoGD-1 Enter"

# ---- D4: `<lane> (N)` IS A MISMATCH, AND THE SUFFIX IS EVIDENCE.
gd_rec "$GD_LANE_ID" "repoGD-1 (2)" user "$GD_OLD_MS"
gd_run "$GD_LANE_ID"
is    "a \`<lane> (N)\` title is a mismatch, not the lane (ratified decision D4)" "$rc" 2
has   "…and the lock renames it to the lane" "$err" "SO IT HAS BEEN RENAMED FOR YOU"
has   "…with the note that a stale holder of the title was live when it was minted" "$err" "another holder of 'repoGD-1' was live"
has   "…naming the retire act and never a kill (A11 clause (k) rule (e))" "$err" "lane-end repoGD-1 --retire <pid>"
hasnt "…so no surface offers to kill a process" "$err" "kill $LIVE_PID"

# ---- AMENDMENT 15: A LOWERCASE WINDOW IS THE SAME LANE, AND THE ROW'S
# SPELLING IS WHAT EVERY MESSAGE AND EVERY TYPED COMMAND CARRIES.
export FAKE_TMUX_WINDOW_NAME=repogd-1
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repogd-1	%12	claude"
gd_rec "$GD_LANE_ID" repogd-7e derived "$GD_OLD_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "a window spelled in another case resolves to the same row (Amendment 15)" "$rc" 2
has   "…and every message prints the REGISTER's spelling" "$err" "row      \`repoGD-1\` — last session"
has   "…including the command typed into the pane" "$(tail -n1 "$FAKE_TMUX_LOG")" "/rename repoGD-1"
gd_rec "$GD_LANE_ID" repogd-1 user "$GD_OLD_MS"
gd_run "$GD_LANE_ID"
is    "a session name that differs from the row ONLY by case is still renamed to the row's spelling" "$rc" 2
has   "…saying why, in Amendment 15's own terms" "$err" "a lane name is ONE name under any case"
export FAKE_TMUX_WINDOW_NAME=repoGD-1
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude"

# ---- (b) ROWS 1 AND 2: THE WINDOW IS NOT A LANE.
export FAKE_TMUX_WINDOW_NAME=claude
export FAKE_TMUX_WINDOWS="gdsess:0	@12	claude	%12	claude"
gd_rec "$GD_LANE_ID" repoGD-1 user "$GD_OLD_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "a window named \`claude\` holding a session named for a lane BLOCKS the prompt" "$rc" 2
has   "…and names the one command, filled in (F-B6)" "$err" "run: lane-start --no-launch repoGD 1"
has   "…saying that this is the case that ran for three days unrecorded" "$err" "THAT IS THE 2026-09-10 CASE"
is    "…and types nothing: a window that is not a lane is not renamed without a person" "$(gd_keys)" "$gd_before"
gd_rec "$GD_LANE_ID" zsh derived "$GD_OLD_MS"
gd_run "$GD_LANE_ID"
is    "neither name being a lane BLOCKS the prompt too" "$rc" 2
has   "…and the guard refuses to name the lane, because it cannot" "$err" "the guard cannot name one either"
has   "…printing the form a person fills in themselves" "$err" "run: lane-start <repo> <n>"
export FAKE_TMUX_WINDOW_NAME=repoGD-1
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude"

# ---- (b) ROWS 5 AND 6: WHERE THE UUID SITS IN THE CELL.
gd_rec "$GD_OLD_ID" repoGD-1 user "$GD_OLD_MS"
gd_run "$GD_OLD_ID"
is    "an id IN the cell but not LAST is a superseded transcript and is blocked" "$rc" 2
has   "…named as one" "$err" "this is a SUPERSEDED transcript of lane repoGD-1"
has   "…and cured by a real lane-start, which resumes the id the row ends on" "$err" "run: lane-start repoGD 1"
hasnt "…never by the recording act, which would record the WRONG conversation" "$err" "--no-launch"
gd_rec "$GD_FREE_ID" repoGD-1 user "$GD_OLD_MS"
gd_run "$GD_FREE_ID"
is    "an id in NO row is the OTHER mismatch and is blocked" "$rc" 2
has   "…named as the harness minting a transcript with nobody acting" "$err" "the harness minted a new transcript"
has   "…and cured by the recording act, with no relaunch" "$err" "run: lane-start --no-launch repoGD 1"

# ---- (b) ROW 7: TWO ROWS FOR ONE NAME, AND A REGISTER THAT CANNOT BE READ.
# SEEDED AND NOT ADDED, because `add-row` is one of the writers Amendment 15(b)
# has REFUSED this very state since #41 landed — which is the point of the
# guard's own row for it: the pair can no longer be created by the tooling, only
# met, exactly as `openXfactory-2`'s was met on 2026-09-13. So it is written the
# way that state actually arrives, straight into the register and pushed, the
# same `add_seed_row` + commit the Amendment 15 section below uses.
add_seed_row "| \`repoGC-1\` | harness \`$GD_FREE_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoGC/x.md | ACTIVE |"
add_seed_row "| \`repogc-1\` | harness \`$GD_LANE_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoGC/y.md | ACTIVE |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed Amendment 12's case pair: two rows for one lane name, which add-row refuses"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
export FAKE_TMUX_WINDOW_NAME=repoGC-1
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGC-1	%12	claude"
gd_rec "$GD_LANE_ID" repoGC-1 user "$GD_OLD_MS"
gd_run "$GD_LANE_ID"
is    "a window whose name matches TWO rows that differ only by case is blocked" "$rc" 2
has   "…naming both spellings" "$err" "repoGC-1 repogc-1"
has   "…and the merge that is a person's act, never a tool's (Amendment 15(d))" "$err" "merge them into one row"
export FAKE_TMUX_WINDOW_NAME=repoGD-1
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude"

gd_rec "$GD_LANE_ID" repoGD-1 user "$GD_OLD_MS"
chmod 000 "$profiles_root"
gd_run "$GD_LANE_ID"
chmod 755 "$profiles_root"
is    "session records that cannot be READ block the prompt — fail CLOSED (clause (d))" "$rc" 2
has   "…naming the read that failed" "$err" "session records could not be read"
has   "…and the one bypass, which is not an environment flag" "$err" "claude --safe-mode"
# AND THE `SessionStart` HOOK MEETS THE SAME UNREADABLE RECORDS AND STILL EXITS
# 0. The two hooks read the same directories through the same function and are
# held to OPPOSITE contracts — one refuses on a read it could not make (clause
# (d)), the other may never fail at all (R-A8-1) — so the one fixture is asked
# of both. This is the case that was RED while `transcript_holders` left
# `th_here_prof` unset: an unbound variable under `set -u` exits the shell where
# it stands, so `|| :` at the call site caught nothing and `session-start`
# exited 1 with no block at all — the hook breaking the session it exists to
# orient. The read now happens in a subshell, which is what bounds it.
chmod 000 "$profiles_root"
out="$(printf '{"session_id":"%s","source":"resume","cwd":"%s/projects/repoGD"}' "$GD_LANE_ID" "$HOME" | "$E" session-start 2>/dev/null)"; rc=$?
chmod 755 "$profiles_root"
is    "…while the SessionStart hook, on the very same unreadable records, still exits 0 (R-A8-1)" "$rc" 0
# THE TAIL AND NOT THE HEAD: `ssb_tail` prints UNCONDITIONALLY as the last line
# of every block, whichever branch wrote the rest (Amendment 8(e)) — so it is
# the one assertion that says "a WHOLE block came out" without pinning which
# branch this fixture happens to take.
has   "…having printed its block down to the tail every branch ends with, because a hook that dies breaks the session it orients" "$out" "(no fetch)"

# ---- THE WORKSPACE THAT CANNOT BE READ, AND THE ONE NUMBER THAT DECIDES.
#
# EVERY OTHER SUBCOMMAND DIES 1 HERE — the dispatcher's own guard — and `guard`
# is exempt from it and refuses for itself with a 2. That is not a preference:
# only a 2 blocks a `UserPromptSubmit`, so a 1 would print the workspace refusal
# and let the prompt THROUGH, which is the silence Amendment 12 exists to end.
# AGENTS.md's lane paragraph carries the exception for the same reason.
out="$(printf "$gd_hook" "$GD_LANE_ID" "$HOME/projects/repoGD" "do the work" | LANES_FILE="$SANDBOX/no-such-register.md" "$E" guard 2>"$SANDBOX/stderr")"; rc=$?
err="$(cat "$SANDBOX/stderr")"
is    "a register this workstation cannot read blocks the prompt with 2, never the dispatcher's 1" "$rc" 2
has   "…saying it is the ROW half of the triple that could not be read" "$err" "the ROW cannot be read"
has   "…and the one bypass" "$err" "claude --safe-mode"
out="$(printf '' | LANES_FILE="$SANDBOX/no-such-register.md" "$E" session-start 2>/dev/null)"; rc=$?
is    "…while session-start on the same missing register still exits 0, as it always has" "$rc" 0
gd_run "$GD_LANE_ID" "do the work" ""
is    "a payload naming no cwd at all is an indeterminate read, not 'outside the root'" "$rc" 2
has   "…and says which read did not happen" "$err" "carried no \`cwd\`"

# ---- (b)'s LAST ROW: NOT INSIDE TMUX AT ALL (ratified decision D2, "Refuse"),
# AND THE READ THAT DID NOT HAPPEN IS NOT THE SAME STATE.
#
# A lane RUNS in a tmux window named for it (Rule 4, Amendment 2), so a session
# with no window has no WINDOW half to compare — and this is the one row of the
# table whose command cannot be filled in, because which lane a windowless
# session is is exactly what nothing here knows. `$TMUX` unset is that row; the
# same guard with `$TMUX` set and tmux answering NOTHING is clause (d)'s
# indeterminate read instead, and the two say different things because a person
# who is not in tmux and a person whose tmux is broken have different work to do.
gd_rec "$GD_LANE_ID" repoGD-1 user "$GD_OLD_MS"
gd_before="$(gd_keys)"
out="$(printf "$gd_hook" "$GD_LANE_ID" "$HOME/projects/repoGD" "do the work" | TMUX= "$E" guard 2>"$SANDBOX/stderr")"; rc=$?
err="$(cat "$SANDBOX/stderr")"
is    "a session in no tmux window at all is refused (ratified decision D2)" "$rc" 2
has   "…saying a lane RUNS in a window named for it" "$err" "not in a tmux window at all"
has   "…printing the triple with nothing in its window half" "$err" "window   not in tmux 'none'"
has   "…and naming the act, the one cure in this table that cannot be filled in" "$err" "run: lane-start <repo> <n>   (in a tmux window)"
is    "…and typing nothing, because there is no pane to type into" "$(gd_keys)" "$gd_before"
# A `tmux` ON PATH THAT ANSWERS NOTHING, which is what a dead server looks like
# from inside a pane whose session has gone: the WINDOW half was not read, so
# nothing is judged against it (clause (d)) and the bypass is printed.
mkdir -p "$SANDBOX/deadtmux"
printf '#!/usr/bin/env bash\nexit 1\n' > "$SANDBOX/deadtmux/tmux"
chmod +x "$SANDBOX/deadtmux/tmux"
out="$(printf "$gd_hook" "$GD_LANE_ID" "$HOME/projects/repoGD" "do the work" | PATH="$SANDBOX/deadtmux:$PATH" "$E" guard 2>"$SANDBOX/stderr")"; rc=$?
err="$(cat "$SANDBOX/stderr")"
is    "…while a tmux that answers nothing is an indeterminate read and not 'no window'" "$rc" 2
has   "…naming the read that did not happen" "$err" "tmux did not answer"
has   "…and the one bypass" "$err" "claude --safe-mode"

# ---- CLAUSE (h) RULE 2: THE OFFER, AND ITS THREE ANSWERS.
GD_OFFER="$CLAUDE_CONFIG_DIR/lanes/offers/$GD_LANE_ID"
gd_rec "$GD_LANE_ID" repoGD-2 user "$GD_NEW_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "a PERSON's rename to another lane's name is blocked, not obeyed" "$rc" 2
has   "…and read as an instruction about the LANE (D5)" "$err" "you renamed this session to repoGD-2"
has   "…saying whether that lane exists" "$err" "lane repoGD-2 EXISTS"
has   "…with the two answers, and no third" "$err" "Reply \`yes\` to move this window to it"
has   "…the other one" "$err" "Reply \`no\` to stay repoGD-1"
is    "…and the offer is written under the harness's own config directory, per session" "$( [ -f "$GD_OFFER" ] && echo yes || echo no )" yes
is    "…and NOTHING is typed into the pane until a person answers" "$(gd_keys)" "$gd_before"
gd_run "$GD_LANE_ID" "what does that mean?"
is    "anything that is not an answer is refused, and the offer is asked again" "$rc" 2
has   "…in the same two words" "$err" "Reply \`yes\` to move this window to repoGD-2"
is    "…and the offer is still pending" "$( [ -f "$GD_OFFER" ] && echo yes || echo no )" yes

# AN ANSWER IS A PROMPT, AND A PROMPT IN A DUPLICATED PROCESS IS REFUSED.
# Clause (h) refuses "every prompt in a process that shares its session id with
# another live one", and consuming a `yes` here would run `lane-start` — a
# register write — out of a process that may not be writing at all, on an offer
# file the OTHER process could equally have answered. So 18(h)'s count is asked
# in front of the answer, and the offer is KEPT for the prompt after the
# duplicate is retired (Copilot round 1 on this PR).
write_record_a12 "$gd_t2/dup-answer.json" "$GD_LANE_ID" "$GD_DUP" "$gd_dup_start" bg "-" "repoGD-1" - "$GD_OLD_MS"
gd_run "$GD_LANE_ID" "yes"
is    "a pending offer is NOT answered while a second live process holds this transcript" "$rc" 2
has   "…the duplicate being what the refusal names" "$err" "ANOTHER LIVE PROCESS CARRIES THIS SESSION ID"
hasnt "…so nothing moved" "$err" "MOVED: this window is now lane"
is    "…and the offer is kept, to be answered when the other process is retired" "$( [ -f "$GD_OFFER" ] && echo yes || echo no )" yes
rm -f "$gd_t2/dup-answer.json"

gd_run "$GD_LANE_ID" "no"
is    "\`no\` is consumed and blocks that prompt too — an answer is not work" "$rc" 2
has   "…renaming the session back" "$err" "STAYING repoGD-1"
has   "…by typing it into the pane" "$(tail -n1 "$FAKE_TMUX_LOG")" "send-keys -t %12 /rename repoGD-1 Enter"
is    "…and the offer is consumed" "$( [ -f "$GD_OFFER" ] && echo yes || echo no )" no

gd_rec "$GD_LANE_ID" repoGD-2 user "$GD_NEW_MS"
gd_run "$GD_LANE_ID"
is    "the offer is made again at the next prompt, because the rename still stands" "$rc" 2
# THE RENAME HAS TO LAND FOR THIS ONE, so the fake's opt-in sticky rename is on:
# `lane-start`'s step 3b veto 2 reads `#W`, and the whole point of the guard
# renaming the window BEFORE it runs lane-start is that the veto then does not
# fire and this session reaches the new lane's session cell.
export FAKE_TMUX_RENAME_STICKS=1 FAKE_TMUX_NAME_FILE="$SANDBOX/tmux-window-name"
rm -f "$FAKE_TMUX_NAME_FILE"
gd_run "$GD_LANE_ID" "yes"
is    "\`yes\` is consumed and blocks that prompt" "$rc" 2
has   "…and this window is the other lane now" "$err" "MOVED: this window is now lane repoGD-2"
has   "…the window renamed by lane-start's own act" "$(grep 'rename-window' "$FAKE_TMUX_LOG" | tail -n1)" "rename-window repoGD-2"
has   "…this session appended to that lane's cell, which is what the next resume follows" \
      "$("$E" register-row repoGD-2 2>/dev/null || :)" "$GD_LANE_ID"
# AND THE GUARD SAYS IT MADE THAT WRITE, because `lane-start` cannot: its step
# 3b veto 1 never takes a uuid another row records, and after the rename this
# one is repoGD-1's. Without this the new row would carry a FRESH id, the next
# prompt would find a lane whose row does not name this transcript, and the
# guard would refuse for ever on a state it created by obeying the person.
has   "…the guard having made that one write itself, on the person's yes" "$err" "session cell now ends on $GD_LANE_ID"
has   "…and the lane it LEFT marked PAUSED, so the register says where the work went" \
      "$("$E" register-row repoGD-1 2>/dev/null || :)" "PAUSED · "
has   "…naming the lane this window moved to (Amendment 13(a): the cell is SET, never appended to)" \
      "$("$E" register-row repoGD-1 2>/dev/null || :)" "this window moved to lane repoGD-2"
is    "…and the offer is consumed" "$( [ -f "$GD_OFFER" ] && echo yes || echo no )" no
unset FAKE_TMUX_RENAME_STICKS FAKE_TMUX_NAME_FILE

# ---- AMENDMENT 18(h): ONE LIVE PROCESS PER TRANSCRIPT.
#
# THE SHAPE MEASURED FOUR TIMES ON 2026-09-14, the last at 18:14Z: a `bg` record
# in ONE profile's `sessions/` beside the interactive record in ANOTHER's, both
# live, both carrying one session id. The second profile is the point — the
# sweep is of every profile's directory, not of the asking session's.
export FAKE_TMUX_WINDOW_NAME=repoGD-1
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude"
gd_rec "$GD_LANE_ID" repoGD-1 user "$GD_OLD_MS"
write_record_a12 "$gd_t2/fork.json" "$GD_LANE_ID" "$GD_DUP" "$gd_dup_start" bg "-" "repoGD-1" - "$GD_OLD_MS"
gd_run "$GD_LANE_ID"
is    "a second LIVE process on one transcript blocks every prompt (Amendment 18(h))" "$rc" 2
has   "…naming it" "$err" "ANOTHER LIVE PROCESS CARRIES THIS SESSION ID"
has   "…by pid, and as the \`bg\` it is" "$err" "pid $GD_DUP (bg, kind bg"
has   "…in the profile whose sessions/ directory it sits in — the sweep is of every one" "$err" "profile t2"
has   "…and names the retire act, filled in" "$err" "run: lane-end repoGD-1 --retire <pid>"
is    "…and the read that finds them is a subcommand two other surfaces share" \
      "$("$E" transcript-holders "$GD_LANE_ID" >/dev/null 2>&1; echo $?)" 0

run   "$START" repoGD 1 --no-launch
is    "…and lane-start REFUSES to bind a transcript two processes hold" "$rc" 1
has   "…naming the pid and where it is" "$err" "another live process already carries transcript $GD_LANE_ID"
has   "…and the same one act" "$err" "lane-end repoGD-1 --retire <pid>"
hasnt "…having launched nothing" "$err" "exec: "

run   "$END" repoGD-1 --retire "$GD_DUP"
is    "lane-end --retire <the duplicate's pid> retires it, where the row records its id (#39)" "$rc" 0
has   "…proving it first, and writing nothing" "$err" "IS a live DUPLICATE of lane repoGD-1's own transcript"
has   "…and naming Amendment 6(d)'s act for a background holder, which has no prompt to type into" "$err" "an idle background session still holding a lane name is ended"
has   "…the lane itself untouched" "$err" "ended nothing, wrote nothing and killed nothing"
run   "$END" repoGD-1 --retire "$LIVE_PID"
is    "…while the WINDOW's own session is refused: retiring the session that IS the lane is not an act" "$rc" 2
has   "…saying so" "$err" "IS lane repoGD-1's own live session"
has   "…and naming the act that DOES end a lane" "$err" "To end the lane, run: lane-end repoGD-1"
rm -f "$gd_t2/fork.json"

# AND THE SECOND PROCESS IS NOT ALWAYS IN ANOTHER PROFILE. One profile can
# resume one transcript twice — no move, no swap, one command — and the record
# that makes is an INTERACTIVE one beside this window's own. Amendment 8 ruling
# (g)'s companion, which this read passes over in silence, is the harness's
# `kind: bg` record and only that; a second interactive holder in the same
# directory is 18(h)'s own case (Copilot round 1 on this PR: the profile alone
# read the cheapest duplicate there is as benign).
write_record_a12 "$sessions_dir/twin.json" "$GD_LANE_ID" "$GD_DUP" "$gd_dup_start" interactive "gdsess:@77.%77" "repoGD-1" - "$GD_OLD_MS"
gd_run "$GD_LANE_ID"
is    "a second INTERACTIVE process on one transcript in the SAME profile is a duplicate too" "$rc" 2
has   "…named as one" "$err" "ANOTHER LIVE PROCESS CARRIES THIS SESSION ID"
has   "…by pid, and as the interactive record it is" "$err" "pid $GD_DUP (window gdsess:@77"
has   "…in this window's own profile, which is no longer a reason to pass it over" "$err" "profile t1"
rm -f "$sessions_dir/twin.json"
# AND THE COMPANION IS THE `bg` RECORD AND NOTHING ELSE IS READ AS ONE: this
# suite's own interactive fork carries `kind: user` (Amendment 11 clause (k)'s
# section above), and "not a session record" — the first spelling of this test
# — would have taken that, and every kind a later harness invents, as the
# harness's benign companion (Copilot round 2 on this PR).
write_record_a12 "$sessions_dir/usertwin.json" "$GD_LANE_ID" "$GD_DUP" "$gd_dup_start" user "-" "repoGD-1" - "$GD_OLD_MS"
gd_run "$GD_LANE_ID"
is    "a kind this file has no rule for is a duplicate and not the companion" "$rc" 2
has   "…named with the kind as found" "$err" "kind user"
rm -f "$sessions_dir/usertwin.json"
# THE HARNESS'S OWN COMPANION IS STILL SILENT, and this is the case that says
# the verdict turns on the record's KIND and not on the profile: the same
# profile, the same id, live — and `kind: bg` (Amendment 8 ruling (g), "records
# that share a sessionId are one session, not a queue of rival holders").
write_record_a12 "$sessions_dir/bgtwin.json" "$GD_LANE_ID" "$GD_DUP" "$gd_dup_start" bg "-" "repoGD-1" - "$GD_OLD_MS"
gd_run "$GD_LANE_ID"
is    "…while the harness's own \`bg\` companion beside it is no duplicate at all" "$rc" 0
is    "…and says nothing" "$err" ""
# AND `--retire` MAY NOT NAME IT EITHER, which is the same rule one surface
# over: the pid a person could reach for here is the OTHER HALF of the session
# that IS the lane, so ending it is not Amendment 6(d)'s act on anything
# (Copilot round 2 on this PR — the target was selected by pid alone and the
# verdict was not read).
run   "$END" repoGD-1 --retire "$GD_DUP"
is    "lane-end refuses to retire the harness's own companion of this lane's live session" "$rc" 2
has   "…naming what the pid actually is" "$err" "is the HARNESS'S OWN COMPANION"
has   "…in ruling (g)'s own words" "$err" "not a queue of rival holders"
has   "…and naming the read that says which process is which" "$err" "transcript-holders $GD_LANE_ID"
hasnt "…never 6(d)'s ending for it" "$err" "an idle background session still holding a lane"
rm -f "$sessions_dir/bgtwin.json"

# ---- AMENDMENT 18(h) IN THE LAUNCH BRANCH: THE ID A RUN IS ABOUT TO RESUME.
# The clause counts the holders of "the id it is about to resume or bind", and
# the two are different ids: the binding step asks about THIS WINDOW's session,
# the row-resume branch about the id the ROW records. This window carries no
# record of that second one — the branch is reached only when they differ — so
# every live holder of it is `unrelated` to this window, which is exactly the
# process that must stop the resume (Copilot round 1 on this PR: counting only
# `duplicate` made this branch's check one that could never fire).
GD_ROW3_ID="aaaa0012-3333-4000-8000-aaaa00123333"
"$E" add-row "| \`repoGD-3\` | harness $GD_ROW3_ID (transcript uuid; profile t1) | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoGD/z.md | ACTIVE |" >/dev/null 2>&1
gd_tdir="$HOME/.claude/projects/$(sanitize "$HOME/projects/repoGD")"
mkdir -p "$gd_tdir"
printf '{"type":"user"}\n' > "$gd_tdir/$GD_ROW3_ID.jsonl"
write_record_a12 "$gd_t2/fork3.json" "$GD_ROW3_ID" "$GD_DUP" "$gd_dup_start" bg "-" "repoGD-3" - "$GD_OLD_MS"
export FAKE_TMUX_WINDOW_NAME=repoGD-3
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-3	%12	claude"
run   "$START" repoGD 3 --no-launch
is    "lane-start REFUSES to RESUME an id another live process carries (the launch branch)" "$rc" 1
has   "…naming the transcript and the pid" "$err" "another live process already carries transcript $GD_ROW3_ID"
has   "…and the retire act for the lane it was starting" "$err" "lane-end repoGD-3 --retire <pid>"
hasnt "…having launched nothing" "$out" "--resume $GD_ROW3_ID"
rm -f "$gd_t2/fork3.json"
run   "$START" repoGD 3 --no-launch
is    "…and resumes it once the other process is gone" "$out" "claude --name repoGD-3 --resume $GD_ROW3_ID"
export FAKE_TMUX_WINDOW_NAME=repoGD-1
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude"

# ---- THE ONE COMMAND THE OFFER CANNOT FILL IN (F-B6).
#
# A lane named before Rule 4's `<repo>-<n>` form — the register carries 22 of
# them — has no `<repo> <n>` to pass, and `lane_start_args` answers `--dir
# <path> <lane>` for it: a PLACEHOLDER, because nothing in the register, the
# window or this session says where that lane's checkout is. Printing it in a
# diagnostic is honest; RUNNING it would refuse on a directory that does not
# exist and ask the same question at every prompt afterwards (Copilot round 1
# on this PR).
"$E" add-row "| \`legacy-ui\` | none recorded | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/legacy/z.md | ACTIVE |" >/dev/null 2>&1
gd_rec "$GD_LANE_ID" legacy-ui user "$GD_NEW_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "a rename to a lane named before the \`<repo>-<n>\` rule is the offer too" "$rc" 2
has   "…saying that lane exists" "$err" "lane legacy-ui EXISTS"
has   "…and saying what it cannot fill in, rather than printing a placeholder as a command" "$err" "needs that lane's DIRECTORY"
gd_run "$GD_LANE_ID" "yes"
is    "\`yes\` refuses rather than running a command with a \`<path>\` in it" "$rc" 2
has   "…naming the act with the one word left to the person" "$err" "run: lane-start --no-launch --dir <that lane's checkout> legacy-ui"
has   "…having moved and written nothing" "$err" "NOTHING has been renamed, moved or written"
is    "…and typing nothing into the pane" "$(gd_keys)" "$gd_before"
is    "…with the offer KEPT, because \`no\` still answers it" "$( [ -f "$GD_OFFER" ] && echo yes || echo no )" yes
gd_run "$GD_LANE_ID" "no"
is    "…which it does" "$rc" 2
has   "…staying the lane this window is" "$err" "STAYING repoGD-1"
is    "…and the offer is consumed" "$( [ -f "$GD_OFFER" ] && echo yes || echo no )" no

# ---- THE OTHER TEXT A SESSION CELL CAN CARRY INSTEAD OF A UUID.
#
# `lane-start` writes `pending — set by the session's first act` into a row it
# creates with neither a minted uuid nor one it was allowed to take
# (`lane-start:1914`), and after a `yes` that is exactly the shape the
# destination can be in: veto 1 refuses this window's uuid because the row being
# LEFT still records it. Anchored only on `none recorded`, the guard's own last
# write could not be made there and the next prompt refused for ever on a state
# it had created by obeying the person (Copilot round 3 on this PR).
"$E" add-row "| \`repoGD-4\` | pending — set by the session's first act | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoGD/w.md | ACTIVE |" >/dev/null 2>&1
export FAKE_TMUX_RENAME_STICKS=1 FAKE_TMUX_NAME_FILE="$SANDBOX/tmux-window-name"
printf 'repoGD-1\n' > "$SANDBOX/tmux-window-name"
gd_rec "$GD_LANE_ID" repoGD-4 user "$GD_NEW_MS"
gd_run "$GD_LANE_ID"
is    "a rename to a lane whose cell carries no uuid at all is the offer" "$rc" 2
has   "…naming the lane it would move to" "$err" "you renamed this session to repoGD-4"
gd_run "$GD_LANE_ID" "yes"
is    "…and \`yes\` moves the window" "$rc" 2
has   "…saying so" "$err" "MOVED: this window is now lane repoGD-4"
has   "…with the guard's own last write anchored on the cell's \`pending\` text" "$err" "session cell now ends on $GD_LANE_ID"
has   "…which the register carries" "$("$E" register-row repoGD-4 2>/dev/null || :)" "$GD_LANE_ID"
unset FAKE_TMUX_RENAME_STICKS FAKE_TMUX_NAME_FILE
export FAKE_TMUX_WINDOW_NAME=repoGD-1
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude"

# ---- M1's TWO CONDITIONS ON TYPING AT ALL, AND THE PANE IT TYPES INTO.
#
# (a) THE PANE IS THE RECORD'S, ELSE THIS ONE. The harness has been seen to
# write no `tmux` at all for a process plainly in a window (Amendment 8, ruling
# (g)'s third fact), and `record_is_here`'s tier 3 still places such a record
# HERE by the pane's own process tree — so the lock had a session to rename and
# no pane to type into, and printed "tmux would not take the keys" for a name it
# could have fixed (Copilot round 2 on this PR). Both hooks run INSIDE the
# session's own pane, so `#{pane_id}` with no `-t` is that pane, asked of tmux
# rather than guessed. The fake answers it only for a case that opts in, so
# every case written before this one still describes a record with a target.
# THE PANE THE FALLBACK FINDS IS A REAL ONE AND NOT THE RECORD'S: a second
# window in the fake's table, so that the pane typed into can only have come
# from tmux's own `#{pane_id}`. M1's gate is asked of it like any other, which
# is why it has to be a pane the table knows: a `%99` in no window at all is
# read as "the pane's current command could not be read" and nothing is typed,
# which is the case below this one and not this one.
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude
gdsess:9	@99	repoGD-1	%99	claude"
# THE PANE PID IS THE RECORD'S OWN, AND THAT IS A PORTABILITY FACT AND NOT A
# convenience: `pid_under` answers 0 at its FIRST step when the pid IS the
# ancestor, and walks `/proc` only to climb. macOS has no `/proc`, so a
# record whose pid is a CHILD of this pane is "here" on Linux and nowhere on
# the macOS job — which is what `tests-macos` said at `6cf5359`, three red
# lines under a green Linux run. A record whose pid IS the pane's needs no
# walk at all and is this window's on both.
export FAKE_TMUX_PANE_PID="$LIVE_PID" FAKE_TMUX_PANE_ID="%99"
write_record_a12 "$sessions_dir/gd.json" "$GD_LANE_ID" "$LIVE_PID" "$live_start" interactive "-" repogd-7e derived "$GD_OLD_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "a live record with NO tmux target is still this window's, and the lock still renames it" "$rc" 2
has   "…saying it did" "$err" "SO IT HAS BEEN RENAMED FOR YOU"
is    "…typing once" "$(( $(gd_keys) - gd_before ))" 1
has   "…into the pane tmux itself names, the record having named none" "$(tail -n1 "$FAKE_TMUX_LOG")" "send-keys -t %99 /rename repoGD-1 Enter"
# AND A TARGET THAT NAMES ANOTHER WINDOW IS NOT A PANE THIS HOOK MAY TYPE INTO.
# `here` is true by the record's target OR by the pane's process tree, and tmux
# REUSES window ids — so a record that is here BY ANCESTRY can carry a target
# some other window now answers to, and M1's gate cannot catch that one: the
# other pane is running `claude` too (Copilot round 3 on this PR).
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude
othersess:0	@5	repoGD-1	%5	claude
gdsess:9	@99	repoGD-1	%99	claude"
export FAKE_TMUX_PANE_PID="$LIVE_PID" FAKE_TMUX_PANE_ID="%99"
write_record_a12 "$sessions_dir/gd.json" "$GD_LANE_ID" "$LIVE_PID" "$live_start" interactive "othersess:@5.%5" repogd-7e derived "$GD_OLD_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "a stale target naming another window is not the pane the lock types into" "$(( $(gd_keys) - gd_before ))" 1
has   "…which is the one tmux names for THIS window" "$(tail -n1 "$FAKE_TMUX_LOG")" "send-keys -t %99 /rename repoGD-1 Enter"
hasnt "…and never the pane the record named, which another session is sitting in" "$(tail -n1 "$FAKE_TMUX_LOG")" "-t %5 "
unset FAKE_TMUX_PANE_ID FAKE_TMUX_PANE_PID
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude"

# (b) AND NOTHING ELSE IS TYPED INTO. M1 ratified the mechanism with its
# condition: the keys go in *"only while the pane's current command is
# `claude`"* — a `/rename` typed at a shell is a command that does not exist and
# typed into an editor is text nobody wrote. Neither half of that gate had a
# case, and it is the only barrier between this hook and somebody else's process
# (Copilot round 2 on this PR).
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	bash"
gd_rec "$GD_LANE_ID" repogd-7e derived "$GD_OLD_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "a pane running something other than claude is NOT typed into" "$(gd_keys)" "$gd_before"
is    "…and the prompt is still refused" "$rc" 2
has   "…saying why nothing was typed" "$err" "this pane is not running claude, so NOTHING was typed"
has   "…with the line for the person to type in the lane's own pane" "$err" "/rename repoGD-1"
# AND `node` IS NOT `claude` EITHER, which is M1's own word: *"only while the
# pane's current command is `claude`"*. This gate read `claude|node` for one
# round, on the reasoning that the harness is a node program — measured on Eagle
# 2026-09-14T23:4xZ across the twelve panes tmux had, eleven lane panes report
# `claude`, two `bash` and one `zsh`, and none reports `node`. So the second
# word bought nothing and would have let a stray Node REPL take `/rename <lane>`
# as input (Copilot round 4 on this PR).
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	node"
gd_rec "$GD_LANE_ID" repogd-7e derived "$GD_OLD_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "a pane running \`node\` is not typed into either" "$(gd_keys)" "$gd_before"
has   "…for the reason M1 gives, in one word" "$err" "this pane is not running claude"
export FAKE_TMUX_WINDOWS="gdsess:0	@12	repoGD-1	%12	claude"
# A PANE THAT COULD NOT BE ASKED IS THE OTHER HALF, and it fails the same way:
# the record names a pane this window does not have, so the targeted read
# resolves nothing and the gate has no answer to test.
write_record_a12 "$sessions_dir/gd.json" "$GD_LANE_ID" "$LIVE_PID" "$live_start" interactive "gdsess:@12.%77" repogd-7e derived "$GD_OLD_MS"
gd_before="$(gd_keys)"
gd_run "$GD_LANE_ID"
is    "a pane whose current command could not be read is not typed into either" "$(gd_keys)" "$gd_before"
is    "…and that prompt is refused too" "$rc" 2
has   "…fail closed, and saying what a stray \`/rename\` would have landed in" "$err" "the pane's current command could not be read"

# ---- CLAUSE (f): THE `SessionStart` BLOCK'S OWN LINE, WHICH REFUSES NOTHING.
gd_rec "$GD_LANE_ID" repogd-7e derived "$GD_OLD_MS"
gd_before="$(gd_keys)"
out="$(printf '{"session_id":"%s","source":"resume","cwd":"%s/projects/repoGD"}' "$GD_LANE_ID" "$HOME" | "$E" session-start 2>/dev/null)"; rc=$?
is    "the SessionStart hook still exits 0 with the name wrong — it never refuses (R-A8-1)" "$rc" 0
has   "…and says the name was not the lane's, in clause (f)'s own words" "$out" "session name 'repogd-7e' was not the lane 'repoGD-1' — renamed"
is    "…having typed the rename itself ((h)1: its ONE act on the pane)" "$(( $(gd_keys) - gd_before ))" 1
write_record_a12 "$gd_t2/fork.json" "$GD_LANE_ID" "$GD_DUP" "$gd_dup_start" bg "-" "repoGD-1" - "$GD_OLD_MS"
out="$(printf '{"session_id":"%s","source":"resume","cwd":"%s/projects/repoGD"}' "$GD_LANE_ID" "$HOME" | "$E" session-start 2>/dev/null)"; rc=$?
is    "…and a duplicate process is SAID and not acted on there" "$rc" 0
has   "…named as the defect it is, with the retire act" "$out" "another live process carries this session id"
has   "…and never a kill" "$out" "lane-end repoGD-1 --retire <pid>"
rm -f "$gd_t2/fork.json"
# AND IT LEAVES A PERSON'S OWN RENAME TO ANOTHER LANE ALONE. Clause (f) types
# the rename for (h)1's case — DRIFT, a name that is no lane's — while (h) rule
# 2 makes a `nameSource: user` rename to another lane's name an INSTRUCTION,
# answered at the next prompt. This hook runs on every startup, resume, clear
# and fork, so typing over such a name would erase the person's choice before
# the guard could put the question: a rename, then a `/clear`, and the offer
# never happens (Copilot round 4 on this PR).
gd_rec "$GD_LANE_ID" repoGD-2 user "$GD_NEW_MS"
gd_before="$(gd_keys)"
out="$(printf '{"session_id":"%s","source":"resume","cwd":"%s/projects/repoGD"}' "$GD_LANE_ID" "$HOME" | "$E" session-start 2>/dev/null)"; rc=$?
is    "the SessionStart hook does not type over a rename a PERSON made to another lane" "$(gd_keys)" "$gd_before"
is    "…still exiting 0, as it always does" "$rc" 0
has   "…and saying the guard will put the question at the next prompt" "$out" "the name guard offers the move at your next prompt"
rm -f "$sessions_dir/gd.json"
kill "$GD_DUP" 2>/dev/null || :
# THE FIXTURE PUT BACK EXACTLY AS IT WAS FOUND — an empty capture means the
# variable was unset here and is unset again, which `${x:+…}` alone could not
# express.
if [ -n "$GD_SAVE_WINDOWS" ]; then export FAKE_TMUX_WINDOWS="$GD_SAVE_WINDOWS"; else unset FAKE_TMUX_WINDOWS; fi
if [ -n "$GD_SAVE_WINDOW" ]; then export FAKE_TMUX_WINDOW="$GD_SAVE_WINDOW"; else unset FAKE_TMUX_WINDOW; fi
if [ -n "$GD_SAVE_NAME" ]; then export FAKE_TMUX_WINDOW_NAME="$GD_SAVE_NAME"; else unset FAKE_TMUX_WINDOW_NAME; fi

echo "== Amendment 15: a lane name is one name under any case =="

# RATIFIED BY BRETT HEAP 2026-09-14T00:07:18Z, verbatim *"Ratify as drafted
# (Recommended)"*, on his question of the day before, verbatim *"can we make
# lane names case insenstive?"*. **A lane name is compared CASE-INSENSITIVELY
# wherever a name is looked up, and the spelling the register row carries is
# canonical.**
#
# WHAT IT COST TO LEARN, five minutes before it was asked about. At
# 2026-09-13T23:51:56Z a `lane-start openxfactory 2`, typed in lowercase for the
# lane `openXfactory-2` that had run since 2026-09-02, found NO row — the row
# key was the one exact comparison left in the tooling, while `repos.tsv`,
# `lane_named_ci`, Rule 6 attribution and home matching already lowercased —
# minted a new session, named the window `openxfactory-2` and appended a SECOND
# row, while its object log went on into `lanes/log/openxfactory-2.md`, the one
# file both spellings had always shared. Two rows, one lane, one log.
#
# THE CHECKOUT IS COMMITTED FIRST, for the reason the section below this one
# gives in the same words: the cases above leave the sandbox workspace dirty on
# purpose, and `lanes-edit.sh` REFUSES an object-log write on a checkout it
# cannot rebase — which is those cases' subject and not this one's.
git -C "$WIP" add -A >/dev/null 2>&1
git -C "$WIP" commit -q -m "commit the sandbox's pending edits before the Amendment 15 cases" >/dev/null 2>&1 || :

# THE FIXTURE IS THE INCIDENT'S OWN SHAPE: a MIXED-CASE row, a checkout whose
# directory is spelled that way too, and a log file already written under the
# LOWERCASE name — which is the state `openXfactory-2` was actually in.
mkdir -p "$HOME/projects/repoCase"
git init -q -b main "$HOME/projects/repoCase"
git -C "$HOME/projects/repoCase" remote add origin "https://github.com/opensoft/repoCase.git"
casedir="$HOME/.claude/projects/$(sanitize "$HOME/projects/repoCase")"
mkdir -p "$casedir"
printf '{"type":"custom-title","customTitle":"repoCase-1","sessionId":"%s"}\n' "$DEAD_ID" > "$casedir/$DEAD_ID.jsonl"
add_seed_row "| \`repoCase-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoCase/x.md | ACTIVE |"
{ printf '# lane repocase-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoCase-1, session %s@Eagle, %s, lane:repoCase-1 → home opensoft/repoCase; estate repoCase\n' "$DEAD_ID" "$OLD_UTC"
} > "$LOGD/repocase-1.md"
# A LOG THAT SPELLS ITS OWN LANE BOTH WAYS, which is not a contrivance: an
# object log is APPEND-ONLY and its lane field carries whatever was typed on the
# day, so `lanes/log/openxfactory-2.md` holds `lane openXfactory-2` lines from
# 2026-09-02 beside the `lane openxfactory-2` lines of the 23:51:56Z incident,
# in one file, about one lane. The CLAIMED here is written in the OTHER case
# from the row and it is a REAL HOLD. Matched byte for byte it would belong to
# no lane at all: `who --lane` would say this one holds nothing and `lane-end`
# would end it without a word.
add_seed_row "| \`repoHold-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoHold/x.md | ACTIVE |"
{ printf '# lane repoHold-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoHold-1, session %s@Eagle, %s, lane:repoHold-1 → home opensoft/repoHold; estate repoHold\n' "$DEAD_ID" "$OLD_UTC"
  printf 'CLAIMED — lane repohold-1, session %s@Eagle, %s, opensoft/repoHold#9\n' "$DEAD_ID" "$OLD_UTC"
} > "$LOGD/repoHold-1.md"
# THE ROW'S SPELLING IS NOT THE DIRECTORY'S, AND THE ROW STILL WINS. `repoMix`
# is the checkout on disk and `repoMIX-1` is the register's row: the `<repo>`
# half resolves to the directory (15(a)) and the LANE resolves to the row, and
# a run that took one answer for both would get one of the two wrong.
mkdir -p "$HOME/projects/repoMix"
git init -q -b main "$HOME/projects/repoMix"
git -C "$HOME/projects/repoMix" remote add origin "https://github.com/opensoft/repoMix.git"
mixdir="$HOME/.claude/projects/$(sanitize "$HOME/projects/repoMix")"
mkdir -p "$mixdir"
printf '{"type":"custom-title","customTitle":"repoMIX-1","sessionId":"%s"}\n' "$DEAD_ID" > "$mixdir/$DEAD_ID.jsonl"
add_seed_row "| \`repoMIX-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoMix/x.md | ACTIVE |"
# A LANE WHOSE OWN LOG SPELLS IT BOTH WAYS, AND WHOSE FACTS ARE IN BOTH LINES:
# the directory and the profile are on the STARTED the row's way, the state and
# the swap record are on the PAUSED the other way. One lane, one set of facts.
add_seed_row "| \`repoWin-1\` | harness \`$DEAD_ID\` | Raven / test / brett | 2026-09-11T00:00Z | none | handoffs/repoWin/x.md | ACTIVE |"
{ printf '# lane repoWin-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoWin-1, session %s@Raven, %s, lane:repoWin-1 → home opensoft/repoWin; dir /elsewhere/repoWin; profile team-09z\n' "$DEAD_ID" "$OLD_UTC"
  printf 'PAUSED — lane repowin-1, session %s@Raven, 2026-09-12T09:00:00Z, lane:repowin-1 → swap; window casewin:3; workstation Raven\n' "$DEAD_ID"
} > "$LOGD/repoWin-1.md"
# A TRANSCRIPT TITLED IN THE OTHER CASE, which is `openXfactory-2`'s own state:
# the launcher named its session `openxfactory-2` on 2026-09-13 and the row has
# said `openXfactory-2` since the 15(d) merge. The row's recorded id has NO
# transcript in this directory, so the TITLE is all that is left — and a matcher
# that compares it byte for byte finds nothing and mints a second conversation
# on a lane that already has one.
TITLE_ID="00000000-7171-4000-8000-000000007171"
mkdir -p "$HOME/projects/repoTitle"
git init -q -b main "$HOME/projects/repoTitle"
git -C "$HOME/projects/repoTitle" remote add origin "https://github.com/opensoft/repoTitle.git"
titledir="$HOME/.claude/projects/$(sanitize "$HOME/projects/repoTitle")"
mkdir -p "$titledir"
printf '{"type":"custom-title","customTitle":"repotitle-1","sessionId":"titled-15"}\n' > "$titledir/titled-15.jsonl"
add_seed_row "| \`repoTitle-1\` | harness \`$TITLE_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoTitle/x.md | ACTIVE |"
# A SECOND MIXED-CASE ROW WITH A LOWERCASE LOG, kept for the case-INSENSITIVE
# INDEX below — which needs a rename that has not happened yet.
add_seed_row "| \`repoIgn-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoIgn/x.md | ACTIVE |"
{ printf '# lane repoign-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoIgn-1, session %s@Eagle, %s, lane:repoIgn-1 → home opensoft/repoIgn; estate repoIgn\n' "$DEAD_ID" "$OLD_UTC"
} > "$LOGD/repoign-1.md"
# PAUSED UNDER ONE SPELLING, RESUMED UNDER THE OTHER — which is what decides
# whether a lane is SWAPPED at all. Keyed on the spelling each line used, the
# PAUSED survives as a swap candidate for ever and `restart` relaunches a lane
# that is running.
add_seed_row "| \`repoSwap-1\` | harness \`$DEAD_ID\` | Raven / test / brett | 2026-09-11T00:00Z | none | handoffs/repoSwap/x.md | ACTIVE |"
{ printf '# lane repoSwap-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'PAUSED — lane reposwap-1, session %s@Raven, 2026-09-12T09:00:00Z, lane:reposwap-1 → swap; window swapwin:4; workstation Raven\n' "$DEAD_ID"
  printf 'RESUMED — lane repoSwap-1, session %s@Raven, 2026-09-12T10:00:00Z, lane:repoSwap-1 → home opensoft/repoSwap\n' "$DEAD_ID"
} > "$LOGD/repoSwap-1.md"
# THE PAIR THE AMENDMENT MAKES IMPOSSIBLE, seeded as it existed: two rows whose
# lane names differ only by case. Every writer refuses on it until 15(d)'s merge.
add_seed_row "| \`repoPair-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoPair/x.md | ACTIVE |"
PAIR_ID="abcdef01-15c5-4000-8000-abcdef0115c5"
add_seed_row "| \`repopair-1\` | harness \`$PAIR_ID\` | Eagle / test / brett | 2026-09-13T23:51Z | none | handoffs/repoPair/x.md | STARTING |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the Amendment 15 fixtures: a mixed-case row with a lowercase log, a hold spelled the other way, a row spelled unlike its checkout, a log that spells its own lane twice, and the case pair 15(d) merges"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

# ---------------------------------------------- act 2: lane-start, both halves

: > "$FAKE_TMUX_LOG"
run env FAKE_TMUX_WINDOW_NAME=claude FAKE_TMUX_WINDOW="testsess:@1" FAKE_TMUX_WINDOW_INDEX=0 \
    "$START" repocase 1 --no-launch
is    "a lowercase <repo> <n> resolves to the mixed-case row and exits 0" "$rc" 0
is    "…resuming the row's recorded session, --name'd with the ROW's spelling" \
      "$(launch_of "$out")" "claude --name repoCase-1 --resume $DEAD_ID"
has   "…renaming the window to the row's spelling" "$(cat "$FAKE_TMUX_LOG")" "rename-window repoCase-1"
hasnt "…and never to the spelling that was typed" "$(cat "$FAKE_TMUX_LOG")" "rename-window repocase-1"
# WHICH HALF SPOKE, AND IN WHICH ORDER. `<repo>` is resolved to the directory
# BEFORE `$LANE` is built out of it, so for a lane whose row and whose checkout
# are spelled the same the repo half has already produced the canonical name and
# the lane half has nothing left to change. That is the right order and not an
# accident: the directory is a fact on this workstation and the row may not
# exist yet. The pure LANE resolution — a row spelled unlike its directory — is
# asserted on `repoMIX-1` below, where only the register can settle it.
has   "…saying which spelling of <repo> it resolved to, and why" "$err" "repo repocase → repoCase"
has   "…naming the rule that settles it" "$err" "Amendment 15(a)"
is    "…the register still has exactly ONE row for the lane" "$(grep -c '^| `repoCase-1`' "$LANES")" 1
is    "…and no second row under the typed spelling — the 23:51:56Z defect" \
      "$(grep -c '^| `repocase-1`' "$LANES")" 0
has   "…it APPENDED a status rather than adding a row" \
      "$(git -C "$WIP" log --oneline -1 -- lanes/LANES.md)" "lane-start on"
has   "…and the stamp it appended carries the canonical spelling" \
      "$(grep '^| `repoCase-1`' "$LANES")" "(lane repoCase-1)"
has   "…having found the checkout by its real directory name, not the typed one" \
      "$(grep '^| `repoCase-1`' "$LANES")" "dir $HOME/projects/repoCase;"

# THE LOG FILE IS THE ROW'S SPELLING, AND THE RENAME IS PART OF THE WRITE.
is    "the lane's log is now named for the row" \
      "$(ls "$LOGD" | grep -c '^repoCase-1\.md$' || :)" 1
is    "…and the lowercase name it was written under is gone from the directory" \
      "$(ls "$LOGD" | grep -c '^repocase-1\.md$' || :)" 0
is    "…so there is exactly ONE log for this lane, whatever the case" \
      "$(ls "$LOGD" | grep -ci '^repocase-1\.md$' || :)" 1
has   "…and the line lane-start wrote is in it, under the canonical lane" \
      "$(cat "$LOGD/repoCase-1.md")" "RESUMED — lane repoCase-1,"
has   "…with the lane OBJECT canonical too, so the log's own key does not fork" \
      "$(cat "$LOGD/repoCase-1.md")" "lane:repoCase-1 →"
case_sha="$(git -C "$WIP" log -1 --format=%H -- lanes/log/repoCase-1.md)"
has   "the rename landed in the WRITE's own commit, not a commit of its own" \
      "$(git -C "$WIP" log -1 --format=%s "$case_sha")" "LOG(repoCase-1@Eagle): RESUMED"
has   "…which names the old path" \
      "$(git -C "$WIP" show --name-status --format= "$case_sha")" "lanes/log/repocase-1.md"
has   "…and the new one, in the one commit" \
      "$(git -C "$WIP" show --name-status --format= "$case_sha")" "lanes/log/repoCase-1.md"
# AND THE TREE HOLDS ONE PATH, WHICH IS THE ASSERTION THE TWO ABOVE CANNOT
# MAKE: both of them pass on a commit that MODIFIED the old path and ADDED the
# new one, which is what a case-insensitive index produces and what leaves a
# lane TWO committed logs — the state Amendment 15 exists to make impossible.
# Counted case-INSENSITIVELY on purpose, so a second path under any spelling is
# a second path. (Measured red on the macOS job of this PR at `928908a`; this
# line is what names it on any filesystem.)
is    "…and HEAD holds ONE path for that log, not the two a case-insensitive index leaves" \
      "$(git -C "$WIP" ls-tree -r --name-only HEAD -- lanes/log | grep -ci '^lanes/log/repocase-1\.md$' || :)" 1
# ONCE. The file is already the row's spelling now, so there is nothing left to
# rename and the next write must not say there was.
run env LANES_LANE=repocase-1 LANES_SESSION="$DEAD_ID" "$E" log PAUSED lane:repocase-1 --no-github
is    "a second write to the same lane exits 0" "$rc" 0
hasnt "…and renames nothing, because the rename happened once" "$err" "the row's spelling names its log"
is    "…the directory still holds one log for the lane" \
      "$(ls "$LOGD" | grep -ci '^repocase-1\.md$' || :)" 1
has   "…and the line it wrote is under the row's spelling, from a lowercase LANES_LANE" \
      "$(tail -n1 "$LOGD/repoCase-1.md")" "PAUSED — lane repoCase-1,"

# AND THE RENAME REACHES THE COMMIT ON A CASE-INSENSITIVE INDEX TOO, which is
# the filesystem this repository's macOS job runs on and the one where the two
# names are ONE name to git. `core.ignorecase` is the config git SETS from that
# probe, so setting it by hand on a case-sensitive filesystem reproduces the
# index half of it exactly: `git add` then matches the pathspec to the entry it
# already has, stages the appended content under the OLD name, and the commit
# records a modification where a rename belongs. Measured that way on the macOS
# job of this PR at `48f2111`: `git log -- <the canonical path>` came back
# EMPTY and fifteen assertions went red behind it.
# SAVED AND RESTORED, NEVER UNSET. `core.ignorecase` is the value `git init`
# WRITES from its own probe of the filesystem, so on a case-insensitive one it
# is already `true` and setting it here is a no-op there — this case reproduces
# the INDEX half on a case-sensitive filesystem, and only that half. The other
# half is the operating system resolving both spellings to one file, which no
# config reproduces; what covers it is the tree count below, asserted on every
# platform.
ign_was="$(git -C "$WIP" config --local core.ignorecase 2>/dev/null || printf '')"
git -C "$WIP" config core.ignorecase true
run env LANES_LANE=repoign-1 LANES_SESSION="$DEAD_ID" "$E" log PAUSED lane:repoign-1 --no-github
if [ -n "$ign_was" ]; then git -C "$WIP" config core.ignorecase "$ign_was"
else                      git -C "$WIP" config --unset core.ignorecase || :
fi
is    "a write under a case-INSENSITIVE index exits 0" "$rc" 0
is    "…and the lane's log is the row's spelling on disk" \
      "$(ls "$LOGD" | grep -c '^repoIgn-1\.md$' || :)" 1
ign_sha="$(git -C "$WIP" log -1 --format=%H -- lanes/log/repoIgn-1.md)"
has   "…the rename reaching the WRITE's own commit, not an index that never saw it" \
      "$(git -C "$WIP" log -1 --format=%s "$ign_sha" 2>/dev/null)" "LOG(repoIgn-1@Eagle): PAUSED"
has   "…which names the old path" \
      "$(git -C "$WIP" show --name-status --format= "$ign_sha" 2>/dev/null)" "lanes/log/repoign-1.md"
has   "…and the new one, in the one commit" \
      "$(git -C "$WIP" show --name-status --format= "$ign_sha" 2>/dev/null)" "lanes/log/repoIgn-1.md"
is    "…and HEAD holds ONE path for this lane's log as well" \
      "$(git -C "$WIP" ls-tree -r --name-only HEAD -- lanes/log | grep -ci '^lanes/log/repoign-1\.md$' || :)" 1
is    "…leaving the checkout clean, so the next write is not refused for it" \
      "$(git -C "$WIP" status --porcelain -- lanes | grep -c . || :)" 0

# THE ROW WINS OVER THE DIRECTORY, AND THE DIRECTORY IS STILL ITS OWN SPELLING.
# `repoMix` on disk, `repoMIX-1` in the register: the `<repo>` half answers from
# the checkout and the LANE half answers from the row, and this is the run where
# the two answers differ, so neither can be standing in for the other.
: > "$FAKE_TMUX_LOG"
run env FAKE_TMUX_WINDOW_NAME=claude FAKE_TMUX_WINDOW="testsess:@1" FAKE_TMUX_WINDOW_INDEX=0 \
    "$START" repomix 1 --no-launch
is    "a lane whose row is spelled unlike its checkout exits 0" "$rc" 0
has   "…the repo half answering from the directory" "$err" "repo repomix → repoMix"
has   "…and the LANE half answering from the register row, over it" "$err" "lane repoMix-1 → repoMIX-1"
is    "…so the launch is --name'd with the ROW's spelling" \
      "$(launch_of "$out")" "claude --name repoMIX-1 --resume $DEAD_ID"
has   "…and the window is renamed to it" "$(cat "$FAKE_TMUX_LOG")" "rename-window repoMIX-1"
hasnt "…never to the spelling the directory would give" "$(cat "$FAKE_TMUX_LOG")" "rename-window repoMix-1"
is    "…with no second row added under either spelling" \
      "$(grep -c '^| `repoMix-1`' "$LANES")" 0
has   "…and the lane's directory is still the CHECKOUT's own spelling, which the row does not carry" \
      "$(grep '^| `repoMIX-1`' "$LANES")" "dir $HOME/projects/repoMix"

# A TRANSCRIPT TITLED IN THE OTHER CASE IS STILL THIS LANE'S, AND IS RESUMED.
# The row's id has no transcript here, so this is the TITLE fallback — the
# branch that decides resume versus mint — and the amendment names the session
# name among the lookups that compare case-insensitively.
: > "$FAKE_TMUX_LOG"
run env FAKE_TMUX_WINDOW_NAME=claude FAKE_TMUX_WINDOW="testsess:@1" FAKE_TMUX_WINDOW_INDEX=0 \
    "$START" repotitle 1 --no-launch
is    "a transcript titled in ANOTHER case is found, and resume beats a new session" \
      "$(launch_of "$out")" "claude --name repoTitle-1 --resume repoTitle-1"
has   "…saying which title it actually found" "$err" "carries the title 'repotitle-1'"
has   "…and that the two spellings are one lane" "$err" "spells this lane in another case"
hasnt "…never calling it a dedupe suffix, which is a different fact with a different cure" \
      "$err" "dedupe suffix"
hasnt "…and minting no new session id for a lane that already has a conversation" \
      "$out" "--session-id"

# AND `--confirm` DOES NOT TELL A PERSON THEIR OWN LANE'S WINDOW IS NOT THE LANE.
# The window here is named `repotitle-1` and the row says `repoTitle-1`: the
# rename still happens, to the row's spelling, but the sentence the operator is
# asked to answer decides whether they say y — and "which is not the lane" about
# their own window earns an N that abandons a legitimate resume.
: > "$FAKE_TMUX_LOG"
run env FAKE_TMUX_WINDOW_NAME=repotitle-1 FAKE_TMUX_WINDOW="testsess:@1" FAKE_TMUX_WINDOW_INDEX=0 \
    "$START" repotitle 1 --no-launch --confirm --yes
is    "--confirm in a window named for this lane in ANOTHER case exits 0" "$rc" 0
has   "…telling the operator it is THIS LANE under another case" "$err" "THIS LANE under another case"
hasnt "…and never that their own lane's window is not the lane" "$err" "which is not the lane"
has   "…while still renaming it to the register row's spelling" \
      "$(cat "$FAKE_TMUX_LOG")" "rename-window repoTitle-1"

# add-row REFUSES THE CASE-DUPLICATE, AND NAMES THE ROW THAT IS THERE. This is
# the act the incident got past: `row_line`'s exactly-one test failing for the
# OTHER reason used to read as "no row, go ahead".
run "$E" add-row "| \`repocase-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoCase/x.md | ACTIVE |"
is    "add-row refuses a row whose lane differs from an existing one only by case" "$rc" 2
has   "…naming the row that is already there, in its own spelling" "$err" "spelled repoCase-1"
has   "…and citing the clause that makes the two one lane" "$err" "Amendment 15(a)"
is    "…adding nothing" "$(grep -c '^| `repocase-1`' "$LANES")" 0

# A REPO DIRECTORY TYPED IN THE WRONG CASE IS FOUND — asserted above through the
# recorded `dir` — AND TWO THAT DIFFER ONLY BY CASE ARE A REFUSAL NAMING BOTH.
# On a case-INSENSITIVE filesystem the pair cannot exist and the case is skipped
# rather than asserted vacuously.
mkdir -p "$HOME/projects/repoTwin" "$HOME/projects/repotwin" 2>/dev/null || :
twin_n="$(ls "$HOME/projects" | grep -ci '^repotwin$' || :)"
if [ "$twin_n" = 2 ]; then
  run "$START" repotwin 1 --no-launch
  is    "two \$PROJECTS_ROOT directories differing only by case refuse with 2" "$rc" 2
  has   "…saying how many there are" "$err" "holds 2 directories whose names differ only by case"
  has   "…naming the one that is not what was typed" "$err" "repoTwin"
  has   "…citing the clause" "$err" "Amendment 15(a)"
  has   "…and naming the flag that settles it" "$err" "--dir <path>"
  is    "…and renaming nothing" "$(grep -c 'repotwin-1' "$FAKE_TMUX_LOG")" 0
  # AND `--dir` IS THE ANSWER THAT REFUSAL ITSELF PRINTS, so a run that already
  # carries one is not ambiguous about where the lane is and must not be
  # refused by the remedy it was given.
  git init -q -b main "$HOME/projects/repoTwin"
  : > "$FAKE_TMUX_LOG"
  run env FAKE_TMUX_WINDOW_NAME=claude FAKE_TMUX_WINDOW="testsess:@1" FAKE_TMUX_WINDOW_INDEX=0 \
      "$START" --dir "$HOME/projects/repoTwin" repotwin 1 --no-launch
  is    "…while a run that HAS named the checkout with --dir is not refused" "$rc" 0
  has   "…saying which ambiguity is left and which is not" "$err" "--dir has named the checkout"
  has   "…and taking the directory it was given" "$err" "$HOME/projects/repoTwin"
else
  skip "two \$PROJECTS_ROOT directories differing only by case refuse with 2" \
       "this filesystem is case-insensitive, so the pair cannot exist on it"
fi

# ------------------------------- act 1: every writer refuses the pair, by name

for a15_cmd in "log" "claim" "append-session-id"; do
  case "$a15_cmd" in
    log)               run env LANES_LANE=repopair-1 LANES_SESSION="$DEAD_ID" "$E" log PAUSED lane:repopair-1 --no-github ;;
    claim)             run env LANES_LANE=repopair-1 LANES_SESSION="$DEAD_ID" "$E" claim "opensoft/repoPair#1" --no-github ;;
    append-session-id) run "$E" append-session-id repopair-1 "$DEAD_ID" "→ harness \`$PAIR_ID\`" ;;
  esac
  is   "$a15_cmd refuses a register holding two rows that differ only by case" "$rc" 2
  has  "…naming the older spelling" "$err" "repoPair-1"
  has  "…naming the newer one beside it" "$err" "repopair-1"
  has  "…and citing the merge that is a person's act" "$err" "Amendment 15(d)"
done
is   "…and none of the three wrote a log for the lane" \
     "$(ls "$LOGD" | grep -ci '^repopair-1\.md$' || :)" 0

# AND `lane-end` REFUSES THE PAIR. Two reads can see it and BOTH are asserted:
# `canon-lane`'s refusal, which this command now relays by its own words rather
# than spending a generic 1 on (Copilot round 4, the stale-checkout case below),
# and `lane-end`'s OWN row scan, which is the whole of the refusal where the
# helper predates the amendment — asserted with exactly such a helper below.
# Compared byte for byte that scan found exactly ONE row and went on to end a
# lane whose register is ambiguous.
run "$END" repopair-1
is   "lane-end refuses the 15(d) pair, naming both rows" "$rc" 2
has  "…naming the spelling that was typed" "$err" "repopair-1"
has  "…and the one beside it" "$err" "repoPair-1"
has  "…citing the merge that is a person's act" "$err" "Amendment 15(d)"

# ------------------------------------------- act 1: Rule 6 attribution, Rule 10
#
# Rule 10's wire form is LOWERCASE — `Lane: openxfactory-2 (openXfactory-2)` —
# while the row's token is camel, which is why `append-line` has matched the
# name case-insensitively since `5219569`. Under this amendment it must still
# match, and the commit it makes must carry the ROW's spelling.
run "$E" append-line "LANDING — lane repocase-1, session $DEAD_ID@Eagle, 2026-09-11T01:00:00Z, PR #3 into opensoft/repoCase main"
is   "append-line with a lowercase lane name in its text exits 0" "$rc" 0
has  "…attributing the commit to the ROW's spelling, not the line's" \
     "$(git -C "$WIP" log --oneline -1 -- lanes/LANES.md)" "LANES(repoCase-1@Eagle)"
has  "…and the line itself lands verbatim, because a Rule 6 line is never rewritten" \
     "$(tail -n5 "$LANES")" "LANDING — lane repocase-1,"
# AND A LINE NAMING THE 15(d) PAIR IS A REFUSAL, not a commit attributed to
# nobody: two rows answer the attribution read exactly as no rows do.
run "$E" append-line "LANDING — lane repopair-1, session $DEAD_ID@Eagle, 2026-09-11T01:00:00Z, PR #4 into opensoft/repoPair main"
is   "append-line refuses a line whose lane the register spells two ways" "$rc" 2
has  "…citing the merge that is a person's act" "$err" "Amendment 15(d)"
hasnt "…and writing no line for it" "$(tail -n3 "$LANES")" "PR #4 into opensoft/repoPair"

# ------------------------------------- acts 1 and 3: the reads take either case

run "$E" who --lane repocase-1 --no-fetch
has  "who --lane takes the lowercase spelling and answers about the mixed-case row" \
     "$out$err" "repoCase-1"
# AND THE OBJECT LOG IS ONE LANE'S WHATEVER CASE ITS LINES SPELL THE LANE IN.
# `repoHold-1`'s CLAIMED says `lane repohold-1`; matched byte for byte it is
# another lane's line and that lane reads as holding nothing. The amendment's
# own sentence names the object log among the places a name is looked up.
run  "$E" who --lane repoHold-1 --no-fetch
has  "who --lane names a hold its log recorded in the OTHER case" \
     "$out" "opensoft/repoHold#9"
run  "$END" repoHold-1
is   "…and lane-end REFUSES to end that lane, which is the hold's whole point" "$rc" 2
has  "…naming the object it still holds" "$err" "opensoft/repoHold#9"
has  "…and the one word that ends it anyway" "$err" "--force"
# AND THE LANE DOES NOT MEET ITS OWN HOLD AS A RIVAL. `claim` removes THIS
# lane's row from the holders of the object it is claiming; byte for byte, a
# hold its log recorded in the other case is a stranger's and the lane is
# refused its own object.
run env LANES_LANE=repoHold-1 LANES_SESSION="$DEAD_ID" "$E" claim "opensoft/repoHold#9" --no-github
is    "claim does not meet this lane's own hold, spelled otherwise, as a rival" "$rc" 0
# THE REFUSAL'S OWN WORDS AND THE RACE'S OWN WORDS, not the word "holds" — the
# line this claim SUCCEEDS with says *"lane repoHold-1 now holds …"*, and an
# assertion that cannot tell that from *"lane repohold-1 holds …"* is asserting
# the wrong half. The two failures this case exists for are the pre-check
# meeting the lane's own row as a rival, and `claim_rescan_hook` meeting it
# again after the rebase and calling the lane the winner against itself.
hasnt "…never stopping and reporting against itself, which is the pre-check" \
      "$err" "Rule 1: the lane stops and reports"
hasnt "…and never losing the race to itself, which is the read after the rebase" \
      "$err" "CLAIM LOST"
run "$E" lanes --lane repocase-1
is   "lanes --lane takes the lowercase spelling" "$rc" 0
is   "…and column 1 is the row's own spelling, never the typed one" \
     "$(printf '%s' "$out" | cut -f1)" "repoCase-1"
# ONE LANE, TWO SPELLINGS IN ITS OWN LOG, ONE SET OF FACTS. `repoWin-1`'s
# STARTED carries its directory and profile the row's way and its PAUSED carries
# the state the other way. Keyed on the spelling each LINE used, the listing
# emitted two rows under one lower-cased key and took the first: the state of
# one and the fields of the other, and column 10 could not be a restart line at
# all, because that needs the PAUSED and the profile together.
run "$E" lanes --lane repowin-1
is   "lanes --lane reads a log that spells its lane two ways as ONE lane" "$rc" 0
is   "…taking the state from the LAST line, which spells it lowercase" \
     "$(printf '%s' "$out" | awk -F'\t' '{print $2}')" "PAUSED"
is   "…and the profile from the STARTED, which spells it the row's way" \
     "$(printf '%s' "$out" | awk -F'\t' '{print $4}')" "team-09z"
is   "…and the directory from that same line" \
     "$(printf '%s' "$out" | awk -F'\t' '{print $7}')" "/elsewhere/repoWin"
is   "…so column 10 is the line that binds it, which needs both halves at once" \
     "$(printf '%s' "$out" | awk -F'\t' '{print $10}')" "lane repoWin-1"

# THE WINDOW-TO-LANE READ ANSWERS WITH THE ROW'S SPELLING FROM EITHER RUNG. Its
# second rung reads the swap RECORD, which spells the lane however it was paused
# — and what this read prints is handed to `tmux rename-window`, to `--name` and
# to `lane <name>` by its three callers (`restart <lane>` until Amendment 18
# Addendum 2 retired that word from the PATH; the act and this read are the
# same, and only the word a person types moved).
run "$E" window-lane Raven casewin:3
is   "window-lane finds the lane from a record that spells it in another case" "$rc" 0
is   "…and answers with the register row's spelling" "$out" "repoWin-1"

# `--all` CLEARS `--lane`, SO IT MUST NOT REFUSE FOR ONE EITHER. The register
# here holds the 15(d) pair; `--all` is the every-lane listing and a `--lane`
# it is about to throw away is not a question anybody asked.
run "$E" lanes --all --lane repopair-1
is   "lanes --all --lane <the pair> lists every lane rather than refusing" "$rc" 0
has  "…including a lane the selector never named" "$out" "repoCase-1"

# THE SWAP CANDIDATE IS THE LANE'S LAST LANE-KIND LINE, whatever case each of
# them spells the lane in. `repoSwap-1` was PAUSED as `reposwap-1` and RESUMED
# as `repoSwap-1`: it is NOT swapped, and a read that keyed those two lines
# apart kept the PAUSED alive for ever.
run "$E" window-lane Raven swapwin:4
is   "a lane RESUMED under the other spelling is no longer a swap candidate" "$rc" 8
is   "…and names no lane at all" "$out" ""

run "$E" register-row repocase-1
is   "register-row takes it too" "$rc" 0
has  "…answering with the mixed-case row" "$out" "| \`repoCase-1\` |"
run "$E" canon-lane REPOCASE-1
is   "canon-lane answers 0 for a name the register spells differently" "$rc" 0
is   "…with the row's own spelling" "$out" "repoCase-1"
run "$E" canon-lane repoNoRow-9
is   "…and 0 with the TYPED spelling for a lane no row carries, so add-row can create it" "$rc" 0
is   "…unchanged" "$out" "repoNoRow-9"
run "$E" canon-lane repopair-1
is   "…and 2 for the pair, which is a refusal and not an absence" "$rc" 2
has  "…naming both spellings" "$err" "repoPair-1"

run env -u TMUX "$LANE" repocase-1 </dev/null
hasnt "lane <name> takes the lowercase spelling and never reports a missing row" "$err" "has no row for lane"
has   "…speaking of the lane by the row's own spelling" "$out$err" "repoCase-1"

run "$END" repocase-1 --force
is   "lane-end takes the lowercase spelling" "$rc" 0
has  "…and the status it appends names the row's own spelling" \
     "$(grep '^| `repoCase-1`' "$LANES")" "lane-end on Eagle: window closing"
has  "…as does the ENDED line in the lane's log" \
     "$(tail -n1 "$LOGD/repoCase-1.md")" "ENDED — lane repoCase-1,"

# ------------------------------------------ Copilot round 4: names and paths
#
# Round 4 of the review on openRepoTools#41 is six defects with one shape: a
# name or a path that means TWO things, read as though it meant one. Five of
# them can only be seen from a checkout that is BEHIND — `origin/<branch>` is
# the register (R19) and `$LANES_FILE` is one workstation's copy of it — so the
# peer below publishes what this checkout never pulls, exactly as the
# `origin/main` cases above this section do.
#
# EVERY LOCAL SEED FIRST, THE PEER'S AFTER IT, and the order is not tidiness:
# both ends append to the register at EOF, so a local commit rebased over the
# peer's is a textual conflict in `lanes/LANES.md` — a rebase left in progress
# and every case after it red for a reason that is not about this amendment.
git -C "$WIP" add -A >/dev/null 2>&1
git -C "$WIP" commit -q -m "commit the sandbox's pending edits before the round-4 cases" >/dev/null 2>&1 || :
add_seed_row "| \`repoTwo-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoTwo/x.md | ACTIVE |"
add_seed_row "| \`repoLate-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoLate/x.md | ACTIVE |"
add_seed_row "| \`repoDrop-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoDrop/x.md | ACTIVE |"
add_seed_row "| \`repoLocal-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoLocal/x.md | ACTIVE |"
add_seed_row "| \`repo.x-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoDot/x.md | ACTIVE |"
add_seed_row "| \`repoXx-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoDot/y.md | ACTIVE |"
add_seed_row "| \`repoRace-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoRace/x.md | ACTIVE |"
# A LANE NAME THAT IS ALSO A PATTERN, AND THE RIVAL IT MATCHES. `check_lane_name`
# admits `.`, and `^repo.x-1` as a regular expression matches `repoXx-1`.
{ printf '# lane repo.x-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repo.x-1, session %s@Eagle, %s, lane:repo.x-1 → home opensoft/repoDot; estate repoDot\n' "$DEAD_ID" "$OLD_UTC"
} > "$LOGD/repo.x-1.md"
{ printf '# lane repoXx-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoXx-1, session %s@Eagle, %s, lane:repoXx-1 → home opensoft/repoDot; estate repoDot\n' "$DEAD_ID" "$OLD_UTC"
  printf 'CLAIMED — lane repoXx-1, session %s@Eagle, %s, opensoft/repoDot#1\n' "$DEAD_ID" "$OLD_UTC"
} > "$LOGD/repoXx-1.md"
{ printf '# lane repoRace-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoRace-1, session %s@Eagle, %s, lane:repoRace-1 → home opensoft/repoRace; estate repoRace\n' "$DEAD_ID" "$OLD_UTC"
} > "$LOGD/repoRace-1.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the round-4 fixtures: a lane with two published logs, a pair this checkout has half of, a rename whose commit did not land, a log on no origin, a lane name that is a pattern, and a race with two rivals"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

# A BARE PEER, AND PLUMBING RATHER THAN A WORKING TREE. One of these cases needs
# TWO PATHS DIFFERING ONLY BY CASE in one published tree, and no working tree on
# a case-INSENSITIVE filesystem can hold both — which is the filesystem this
# repository's macOS job runs on. `hash-object`, `update-index --cacheinfo`,
# `write-tree` and `commit-tree` never touch one, so the case runs everywhere
# rather than skipping where it matters most.
A15_PEER="$SANDBOX/a15-peer"
git clone -q "$ORIGIN" "$A15_PEER" 2>/dev/null
git -C "$A15_PEER" config user.email "peer@example.invalid"
git -C "$A15_PEER" config user.name  "the other workstation"
# <path> <content> … — publishes files at exactly these paths, in one commit,
# and fetches it into this checkout's `origin/main` WITHOUT pulling it.
a15_publish() {
  git -C "$A15_PEER" fetch -q origin 2>/dev/null || :
  git -C "$A15_PEER" read-tree origin/main
  while [ "$#" -gt 1 ]; do
    ap_b="$(printf '%s\n' "$2" | git -C "$A15_PEER" hash-object -w --stdin)"
    git -C "$A15_PEER" update-index --add --cacheinfo "100644,$ap_b,$1"
    shift 2
  done
  ap_t="$(git -C "$A15_PEER" write-tree)"
  ap_c="$(git -C "$A15_PEER" commit-tree "$ap_t" -p origin/main -m "the peer publishes what this checkout has not pulled")"
  git -C "$A15_PEER" push -q origin "$ap_c:main"
  git -C "$WIP" fetch -q origin 2>/dev/null || :
}
# … and takes them off again, which one case has to do: every later
# `pull --rebase` in this suite would otherwise try to materialise two paths a
# case-INSENSITIVE filesystem cannot hold at once, and leave the checkout dirty
# for cases that are not about this at all.
a15_unpublish() {
  git -C "$A15_PEER" fetch -q origin 2>/dev/null || :
  git -C "$A15_PEER" read-tree origin/main
  for au_p in "$@"; do git -C "$A15_PEER" update-index --force-remove "$au_p"; done
  au_t="$(git -C "$A15_PEER" write-tree)"
  au_c="$(git -C "$A15_PEER" commit-tree "$au_t" -p origin/main -m "the peer takes the pair off main again")"
  git -C "$A15_PEER" push -q origin "$au_c:main"
  git -C "$WIP" fetch -q origin 2>/dev/null || :
}
# The register as the peer leaves it, with <row> appended.
a15_publish_row() {
  git -C "$A15_PEER" fetch -q origin 2>/dev/null || :
  a15_publish "lanes/LANES.md" "$(git -C "$A15_PEER" show origin/main:lanes/LANES.md)
$1"
}

# ---- TWO PUBLISHED LOGS FOR ONE LANE ARE A REFUSAL, NOT A COIN TOSS ----------
#
# `log_path_ci` took the FIRST case-insensitive match and `lane_log_events` took
# `head -n1` of the local scan, so a tree holding both `lanes/log/repoTwo-1.md`
# and `lanes/log/repotwo-1.md` read as a tree holding one: every reader behind
# them — the resume target, the profile, the directory, `lanes --lane` — decided
# out of HALF an append-only history and said nothing, while the writer treats
# the same state as ambiguous and refuses.
a15_publish \
  "lanes/log/repoTwo-1.md" "# lane repoTwo-1 — object log (lane-collision-protocol Amendment 7)
STARTED — lane repoTwo-1, session $DEAD_ID@Eagle, $OLD_UTC, lane:repoTwo-1 → home opensoft/repoTwo; estate repoTwo" \
  "lanes/log/repotwo-1.md" "# lane repotwo-1 — object log (lane-collision-protocol Amendment 7)
CLAIMED — lane repotwo-1, session $DEAD_ID@Eagle, $OLD_UTC, opensoft/repoTwo#3"
is   "the peer published two logs for one lane, differing only by case" \
     "$(git -C "$WIP" ls-tree -r --name-only origin/main -- lanes/log | grep -ci '^lanes/log/repotwo-1\.md$' || :)" 2
run "$E" lane-objects repotwo-1
is   "a lane with two published logs is a REFUSAL and not an answer" "$rc" 2
has  "…saying how many there are" "$err" "has 2 object logs on origin/main"
has  "…naming the one spelled the row's way" "$err" "lanes/log/repoTwo-1.md"
has  "…and the one spelled the other way, beside it" "$err" "lanes/log/repotwo-1.md"
has  "…citing the merge that is a person's act" "$err" "Amendment 15(d)"
run env LANES_LANE=repotwo-1 LANES_SESSION="$DEAD_ID" "$E" log PAUSED lane:repotwo-1 --no-github
is   "…and a WRITE under that name is refused before it appends anything" "$rc" 2
has  "…naming both files it will not choose between" "$err" "differ only by case"
is   "…writing no log here" "$(ls "$LOGD" | grep -ci '^repotwo-1\.md$' || :)" 0
a15_unpublish "lanes/log/repoTwo-1.md" "lanes/log/repotwo-1.md"

# ---- THE PAIR IS PUBLISHED AND THIS CHECKOUT HAS ONE ROW ---------------------
#
# `canon-lane` spends 2 on 15(d)'s pair AND on the unknown subcommand of a
# helper predating this amendment, so all three commands carried on with the
# name as typed — on the reading that each makes the refusal again out of its
# own read of the register. That read is `$LANES_FILE`, THE WORKING TREE, and a
# fetch does not move it: with the pair on `origin/main` and one row here, the
# local scan passes and what was left was a `register-row` call with its stderr
# suppressed, whose own 2 became a generic exit 1 naming neither spelling.
LATE_ID="abcdef01-15dd-4000-8000-abcdef0115dd"
a15_publish_row "| \`repolate-1\` | harness \`$LATE_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoLate/x.md | STARTING |"
is   "the pair is on origin/main" \
     "$(git -C "$WIP" show origin/main:lanes/LANES.md | grep -ci '^| `repolate-1` ' || :)" 2
is   "…and this checkout's own copy still has exactly one of them" \
     "$(grep -ci '^| `repolate-1` ' "$LANES" || :)" 1
run "$E" canon-lane repolate-1
is   "canon-lane refuses the PUBLISHED pair from a checkout that has one row" "$rc" 2
: > "$FAKE_TMUX_LOG"
run env FAKE_TMUX_WINDOW_NAME=claude FAKE_TMUX_WINDOW="testsess:@1" FAKE_TMUX_WINDOW_INDEX=0 \
    "$START" repolate 1 --no-launch
is   "lane-start relays that refusal rather than spending a generic 1 on it" "$rc" 2
has  "…naming the spelling that was typed" "$err" "repolate-1"
has  "…and the one beside it" "$err" "repoLate-1"
has  "…citing the merge that is a person's act" "$err" "Amendment 15(d)"
hasnt "…never reporting the helper as broken, which it is not" "$err" "register-row repolate-1 failed"
is   "…and renaming no window on the way" "$(grep -c 'repolate' "$FAKE_TMUX_LOG" || :)" 0
run "$END" repolate-1
is   "lane-end relays it too" "$rc" 2
has  "…naming both spellings" "$err" "repoLate-1"
has  "…and citing the merge" "$err" "Amendment 15(d)"
run env -u TMUX "$LANE" repolate-1 </dev/null
is   "and lane <name> relays it, instead of reporting the read as a failure" "$rc" 2
has  "…naming both spellings" "$err" "repoLate-1"
has  "…and citing the merge" "$err" "Amendment 15(d)"
hasnt "…never calling that a helper failure" "$err" "register-row repolate-1 failed"

# AND THE LOCAL SCAN IS STILL WHAT ANSWERS WHERE THE HELPER CANNOT. A helper
# predating this amendment spends 2 on `canon-lane` as an unknown subcommand and
# says nothing about any amendment, so the relay above must not fire for it —
# and `lane-end`'s own row scan is then the whole of the refusal, which is what
# it was written to be.
A15_OLD="$SANDBOX/old-lanes-edit.sh"
{ printf '#!/bin/sh\n'
  printf 'printf "lanes-edit.sh: unknown subcommand '\''%%s'\''\\n" "$1" >&2\n'
  printf 'exit 2\n'
} > "$A15_OLD"
chmod +x "$A15_OLD"
run env LANES_EDIT="$A15_OLD" "$END" repopair-1
is   "lane-end with a helper that predates canon-lane still refuses the pair" "$rc" 2
has  "…out of its own read of the register, naming the typed spelling" "$err" "repopair-1"
has  "…and the one beside it" "$err" "repoPair-1"
has  "…citing the merge that is a person's act" "$err" "Amendment 15(d)"

# ---- add-row ASKS THE PUBLISHED REGISTER, NOT ONLY THIS COPY OF IT -----------
#
# The case-duplicate refusal scanned `$LANES_FILE` alone, so a row `origin`
# already carries is invisible on a checkout that is behind: `add-row` appends
# the second spelling, `commit_push` rebases the first in underneath it, and the
# pair 15(a) makes this command refuse is published by the command that refuses
# it.
a15_publish_row "| \`repoPush-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoPush/x.md | ACTIVE |"
is   "the row is on origin/main and not in this checkout" \
     "$(grep -ci '^| `repopush-1` ' "$LANES" || :)" 0
run "$E" add-row "| \`repopush-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoPush/y.md | ACTIVE |"
is   "add-row refuses a row the PUBLISHED register already carries under another case" "$rc" 2
has  "…naming the row that is there, in its own spelling" "$err" "spelled repoPush-1"
has  "…citing the clause that makes the two one lane" "$err" "Amendment 15(a)"
has  "…and naming the one command that makes this checkout current" "$err" "pull --rebase"
is   "…adding nothing" "$(grep -ci '^| `repopush-1` ' "$LANES" || :)" 0
# AND IT STILL REFUSES A ROW ONLY THIS CHECKOUT HAS, which is the half the local
# scan is there for: a row added here and not yet pushed is on no origin at all.
run "$E" add-row "| \`REPOTWO-1\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoTwo/y.md | ACTIVE |"
is   "…and a row this checkout has is still a row" "$rc" 2
has  "…named in its own spelling" "$err" "spelled repoTwo-1"

# ---- A RENAME WHOSE COMMIT NEVER LANDED IS STILL TWO LOGS -------------------
#
# `ensure_log`'s published-path guard ran only where this checkout had NO file
# at all, so the state a failed rename leaves — the canonical file here, the
# old-cased path still in the remote tree — walked past it, and the next write
# staged the canonical path alone and left the published one where it was.
a15_publish "lanes/log/repodrop-1.md" "# lane repodrop-1 — object log (lane-collision-protocol Amendment 7)
STARTED — lane repoDrop-1, session $DEAD_ID@Eagle, $OLD_UTC, lane:repoDrop-1 → home opensoft/repoDrop; estate repoDrop"
{ printf '# lane repoDrop-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoDrop-1, session %s@Eagle, %s, lane:repoDrop-1 → home opensoft/repoDrop; estate repoDrop\n' "$DEAD_ID" "$OLD_UTC"
} > "$LOGD/repoDrop-1.md"
run env LANES_LANE=repodrop-1 LANES_SESSION="$DEAD_ID" "$E" log PAUSED lane:repodrop-1 --no-github
is   "a canonical file beside an old-cased PUBLISHED path is refused" "$rc" 2
has  "…naming the path that is published" "$err" "published as lanes/log/repodrop-1.md"
has  "…and saying which half of the rename landed" "$err" "rename whose commit never landed"
has  "…with the one command that settles it" "$err" "pull --rebase"
is   "…appending nothing to the file it would have split the lane across" \
     "$(grep -c '^PAUSED' "$LOGD/repoDrop-1.md" || :)" 0
rm -f -- "$LOGD/repoDrop-1.md"

# ---- A LOG THIS CHECKOUT HAS AND ORIGIN DOES NOT IS STILL THIS LANE'S --------
#
# `claim` exempts its own log from the dirty-checkout refusal, and computes that
# path with `log_path_ci` — whose fallback was the canonical path outright, a
# path that need not exist. A lane whose log is still spelled the old way and
# has never been pushed therefore had its OWN uncommitted log read as an
# unrelated dirty file, and the claim was refused for it.
{ printf '# lane repolocal-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoLocal-1, session %s@Eagle, %s, lane:repoLocal-1 → home opensoft/repoLocal; estate repoLocal\n' "$DEAD_ID" "$OLD_UTC"
} > "$LOGD/repolocal-1.md"
git -C "$WIP" add -- lanes/log/repolocal-1.md >/dev/null 2>&1
git -C "$WIP" commit -q -m "LOG(repoLocal-1@Eagle): STARTED — committed here and pushed nowhere"
printf 'RESUMED — lane repoLocal-1, session %s@Eagle, %s, lane:repoLocal-1 → home opensoft/repoLocal\n' "$DEAD_ID" "$OLD_UTC" >> "$LOGD/repolocal-1.md"
is   "the lane's own log is dirty here and on no origin" \
     "$(git -C "$WIP" status --porcelain -- lanes/log/repolocal-1.md | grep -c . || :)" 1
run env LANES_LANE=repolocal-1 LANES_SESSION="$DEAD_ID" "$E" claim "opensoft/repoLocal#1" --no-github
is   "a claim is not refused for its own log, written under the other case" "$rc" 0
hasnt "…never reading that log as somebody else's uncommitted work" \
      "$err" "refusing to claim on a checkout that cannot be rebased"
is   "…and the log is the row's spelling afterwards" \
     "$(ls "$LOGD" | grep -c '^repoLocal-1\.md$' || :)" 1

# ---- A LANE NAME IS NOT A REGULAR EXPRESSION --------------------------------
#
# Every filter of these US-delimited holder rows handed the name straight to
# `grep`: excluding THIS lane `repo.x-1` also excluded the real rival
# `repoXx-1`, so the pre-check found the object free and the claim was taken
# over a hold that is open.
run env LANES_LANE=repo.x-1 LANES_SESSION="$DEAD_ID" "$E" claim "opensoft/repoDot#1" --no-github
is   "a lane whose name contains '.' does not filter away the rival it matches" "$rc" 2
has  "…naming the lane that actually holds the object" "$err" "lane repoXx-1 holds opensoft/repoDot#1"
has  "…and citing Rule 1 rather than taking it" "$err" "the lane stops and reports"
is   "…writing nothing to the would-be taker's log" \
     "$(grep -c 'repoDot#1' "$LOGD/repo.x-1.md" || :)" 0

# ---- AND `--dir` WITH A SPACE IN IT IS ONE ARGUMENT -------------------------
#
# Round 4 read the four `${lns_args[@]+"${lns_args[@]}"}` expansions in the
# `lanes` block as unquoted and called a path with a space in it split. They are
# the bash 3.2 idiom for an array that may be EMPTY under `set -u`, and the
# quotes inside the `+word` half are honoured: the elements survive whole.
# Asserted rather than argued — a split would reach `lanes_rows` as three
# arguments and come back 64 with the usage line.
run "$E" lanes --dir "$HOME/projects/a lane dir with spaces"
hasnt "lanes --dir with a space in the path is not a usage error" "$err" "usage: lanes"
hasnt "…and no word of it arrives as an argument of its own" "$err" "unknown argument"
is    "…it is simply a directory no lane is in" "$rc" 8

# ---- AND `--` IS NOT A DEFECT IN `ls` ON ANY PLATFORM THIS SHIPS TO ---------
#
# Round 3 read `ls -- "$LANES_LOG_DIR"` (`log_files_named_ci`) and its twin
# `ls -- "$PROJECTS_ROOT"` (`lane-start`-s `projects_dir_matches`) as a macOS
# failure — *"BSD `ls` rejects `--`, and the suppressed error makes every
# case-insensitive log scan empty"* — under which no first write renames a log
# on the one platform the rename exists for, and `<repo>` never resolves to the
# checkout's real directory. It does not: BSD `ls` ends its options at `--`
# through `getopt(3)` like every other POSIX utility, and the macOS job has been
# green throughout on the two assertions that can only pass if both scans answer
# there — the rename inside the write's own commit, and the `repo repocase →
# repoCase` step line. Asserted here as well, directly and on every platform,
# because a decline that is argued rather than measured is one the next round
# makes again.
is   "this platform's ls accepts the -- that both case-insensitive scans pass it" \
     "$(ls -- "$LOGD" >/dev/null 2>&1; echo $?)" 0
is   "…and lists exactly what the bare form lists, neither more nor fewer" \
     "$(ls -- "$LOGD" 2>/dev/null | grep -c . || :)" "$(ls "$LOGD" 2>/dev/null | grep -c . || :)"
has  "…including the log a lane's own scan has to find in it" \
     "$(ls -- "$LOGD" 2>/dev/null)" "repoCase-1.md"

# ---- THE RACE'S WINNER IS JOINED ON A FILE NAME, AND THE LINE SPELLS IT FREELY
#
# LAST IN THIS SECTION, because it is decided by an `origin/main` this checkout
# must not have fetched yet. `first_landed_of` reads the pickaxe's oldest commit
# that touched a rival's LOG FILE and joins that file's name against the holder
# rows. The file carries the row's canonical spelling from the moment the first
# write renames it (Amendment 15); the holder row carries whatever the winning
# LINE was typed with, which an append-only log never rewrites. Byte for byte
# the join missed the winner and the rescan fell back to the sorted-first
# holder — a CLAIM-LOST naming the wrong lane, in the one read whose whole job
# is to say who won.
#
# repoRace-2 LANDS FIRST and its CLAIMED spells the lane lowercase; repoRace-3
# lands second and spells it the row's way. `LC_ALL=C` sorts `repoRace-3` above
# `reporace-2`, so the fallback this defect reaches for names the wrong one.
git -C "$CLONE2" pull -q --rebase origin main 2>/dev/null || :
{ printf '# lane repoRace-2 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'CLAIMED — lane reporace-2, session %s@Raven, %s, opensoft/repoRace#7\n' "$DEAD_ID" "$(utc_at -2M)"
} > "$CLONE2/lanes/log/repoRace-2.md"
git -C "$CLONE2" add -- lanes/log/repoRace-2.md
git -C "$CLONE2" commit -q -m "LOG(repoRace-2@Raven): CLAIMED opensoft/repoRace#7"
git -C "$CLONE2" push -q origin main
{ printf '# lane repoRace-3 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'CLAIMED — lane repoRace-3, session %s@Raven, %s, opensoft/repoRace#7\n' "$DEAD_ID" "$(utc_at -1M)"
} > "$CLONE2/lanes/log/repoRace-3.md"
git -C "$CLONE2" add -- lanes/log/repoRace-3.md
git -C "$CLONE2" commit -q -m "LOG(repoRace-3@Raven): CLAIMED opensoft/repoRace#7"
git -C "$CLONE2" push -q origin main
run env LANES_LANE=repoRace-1 LANES_NO_FETCH=1 LANES_SESSION="$DEAD_ID" "$E" claim "opensoft/repoRace#7" --no-github
is   "a claim two rivals beat to main exits 7" "$rc" 7
has  "…naming the one that LANDED first, whose own line spells it in another case" \
     "$err" "@repoRace-2"
hasnt "…and never the one that merely sorts first" "$err" "@repoRace-3"
has  "…with the CLAIM-LOST line pointing at that winner" \
     "$(cat "$LOGD/repoRace-1.md")" "opensoft/repoRace#7 → lane:repoRace-2"

echo "== Amendment 16: a lane is renamed by one word, in one commit =="

# RATIFIED BY BRETT HEAP 2026-09-14T09:24:35Z, verbatim *"Ratify as drafted
# (Recommended)"*, on his request of the same day, verbatim: *"we need the
# ability to rename a lane. maybe lanes --rename <current lane name> <new lane
# name>."* **A LANE IS RENAMED BY ONE WORD, IN ONE COMMIT, AND ITS OLD NAME
# KEEPS RESOLVING FOR EVER.**
#
# WHAT IT COST TO LEARN: on 2026-09-14 two lanes renamed themselves BY HAND,
# each as one `RENAMED` line appended to `LANES.md` with `append-line`. The
# lines are honest and they are all there is — the rows still carried the old
# keys, the logs and the handoffs the old names, and a reader of either lane's
# history had to know the rename to follow it.
#
# THE CHECKOUT IS COMMITTED FIRST, for the reason the section above this one
# gives in the same words: the cases before it leave the sandbox workspace dirty
# on purpose, and a write that has to `pull --rebase` refuses on a checkout it
# cannot rebase — which is those cases' subject and not this one's.
git -C "$WIP" add -A >/dev/null 2>&1
git -C "$WIP" commit -q -m "commit the sandbox's pending edits before the Amendment 16 cases" >/dev/null 2>&1 || :
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main 2>/dev/null || :

# THE FIXTURE IS A WHOLE LANE: a row, a log with a HELD object in it, and a
# handoff named for the lane — because the act under test moves all three in one
# commit, and a fixture missing any of them would leave a move untested.
REN_ID="12ab34cd-16a1-4000-8000-12ab34cd16a1"
RENH="$WIP/handoffs/repoRen"
mkdir -p "$RENH"
add_seed_row "| \`repoRen-1\` | harness \`$REN_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoRen/session-handoff-2026-09-11-lane-repoRen-1.md | ACTIVE |"
{ printf '# lane repoRen-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoRen-1, session %s@Eagle, %s, lane:repoRen-1 → home opensoft/repoRen; estate repoRen\n' "$REN_ID" "$OLD_UTC"
  printf 'CLAIMED — lane repoRen-1, session %s@Eagle, %s, opensoft/repoRen#4\n' "$REN_ID" "$OLD_UTC"
} > "$LOGD/repoRen-1.md"
{ printf 'Lane: repoRen-1 (opensoft/team-05b, session %s) — single-use resume prompt\n' "$REN_ID"
  printf '\n'
  printf '## RESUME PROMPT — written %s\n' "$OLD_UTC"
} > "$RENH/session-handoff-2026-09-11-lane-repoRen-1.md"
# The row a rename INTO that name would collide with.
add_seed_row "| \`repoRen-9\` | harness \`$DEAD_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoRen/x.md | ACTIVE |"
# A LANE A LIVE SESSION HOLDS, for clause (a)'s live-holder refusal and for the
# one window that is exempt from it. Its recorded id is the suite's live one, so
# `live_holder` finds a real record of a real process.
add_seed_row "| \`repoRenL-1\` | harness \`$LIVE_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoRen/live.md | ACTIVE |"
git -C "$WIP" add -A -- lanes handoffs >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the Amendment 16 fixtures: a lane with a row, a held object, a handoff named for it, a collision row and a live-held lane"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

# ------------------------------------------- clause (a): every refusal, FIRST
#
# EVERY ONE OF THEM MUST LEAVE THE CHECKOUT EXACTLY AS IT FOUND IT, and that is
# the assertion under all of them: this command moves four files, and a
# half-done rename is not something a second run can finish.
ren_before="$(git -C "$WIP" rev-parse HEAD)"

run env LANES_SESSION="$REN_ID" "$E" rename-lane repoNope-1 repoNope-2 --no-github
is   "a rename of a lane with no row is refused" "$rc" 2
has  "…naming the absence, and the read that lists the rows there are" "$err" "no row for lane 'repoNope-1'"
has  "…and saying nothing was written" "$err" "Nothing was written."

run env LANES_SESSION="$REN_ID" "$E" rename-lane repoRen-1 repoRen-9 --no-github
is   "a rename into a name that already has a row is refused" "$rc" 2
has  "…naming the row that is there" "$err" "lane 'repoRen-9' already has a row"

run env LANES_SESSION="$REN_ID" "$E" rename-lane repoRen-1 REPOREN-1 --no-github
is   "a CASE-ONLY rename is refused: that is the row's own spelling" "$rc" 2
has  "…and it names 15(d), which is the act that changes one" "$err" "Amendment 15(d)"

run env LANES_SESSION="$REN_ID" "$E" rename-lane repoRen-1 renamed_lane --no-github
is   "a <new> that is not <repo>-<n> is refused" "$rc" 2
has  "…naming what that form is computed for" "$err" "lane-start <repo> <n>"
has  "…and the flag that means it" "$err" "--verbatim"

run env LANES_SESSION="$REN_ID" "$E" rename-lane repoRenL-1 repoRenL-2 --no-github
is   "a rename while a LIVE session holds the lane in another window is refused" "$rc" 2
has  "…naming that session" "$err" "$LIVE_ID"
has  "…and the two ways out: its own window, or a handoff first" "$err" "lane-handoff"

run env LANES_SESSION="$REN_ID" "$E" rename-lane repoPair-1 repoPairX-1 --no-github
is   "two rows differing only by case refuse the rename" "$rc" 2
has  "…with Amendment 15(d)'s merge, not a coin toss" "$err" "Amendment 15(d)"

run env LANES_SESSION=not-a-uuid "$E" rename-lane repoRen-1 repoRen-4 --no-github
is   "a session field that is not a transcript uuid is refused" "$rc" 2
has  "…by the rule that owns it" "$err" "TRANSCRIPT UUID and only that"

is   "…and NOT ONE of those refusals committed anything" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
is   "…nor moved the lane's log" "$( [ -f "$LOGD/repoRen-1.md" ] && echo yes )" "yes"
is   "…nor its handoff" "$( [ -f "$RENH/session-handoff-2026-09-11-lane-repoRen-1.md" ] && echo yes )" "yes"
is   "…nor created an alias table" "$( [ -e "$WIP/lanes/aliases.tsv" ] && echo yes || echo no )" "no"

# ---- THE WINDOW THE COMMAND RUNS IN IS THE ONE EXEMPTION (clause (f)): a lane
# renames ITSELF, and `live_holder`'s `here` verdict is what tells that apart.
run env LANES_SESSION="$LIVE_ID" CLAUDE_CODE_SESSION_ID="$LIVE_ID" "$E" rename-lane repoRenL-1 repoRenL-2 --no-github
is   "the same rename from the lane's OWN session is allowed" "$rc" 0
is   "…and the row moved" "$(command grep -c '^| `repoRenL-2`' "$LANES")" 1

# ------------------------------- clauses (b)–(e): the four moves, ONE commit
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN_ID" "$E" rename-lane repoRen-1 repoRen-4 "Brett Heap's word: shorten it" --no-github
is   "the rename exits 0" "$rc" 0
is   "…(b) the row's key cell is the new name" "$(command grep -c '^| `repoRen-4`' "$LANES")" 1
# THE ROW ITSELF, TAKEN ONCE. A `\`` inside the SINGLE-QUOTED pattern of a
# `$( )` is a literal BACKSLASH to grep — the quotes have already made the
# backtick literal — and the pattern then matches nothing at all, which reads in
# a failure as "the cell is empty" rather than as "this test asked the wrong
# question".
ren_row="$(command grep '^| `repoRen-4`' "$LANES")"
has  "…with the ex-name and the instant beside it, the form the register already uses" \
     "$ren_row" "*(ex \`repoRen-1\`, renamed 20"
is   "…and no row is left under the old name" "$(command grep -c '^| `repoRen-1`' "$LANES")" 0
has  "…the session cell keeping its whole history (Amendment 6(b))" \
     "$ren_row" "harness \`$REN_ID\`"
is   "…(c) the object log moved to the new name" \
     "$( [ -f "$LOGD/repoRen-4.md" ] && [ ! -e "$LOGD/repoRen-1.md" ] && echo yes )" "yes"
has  "…and gained a RENAMED line under the new name" "$(tail -n1 "$LOGD/repoRen-4.md")" "RENAMED — lane repoRen-4, session $REN_ID@$WS_S,"
has  "…whose payload is lane:<new> ← lane:<old>, with the why the person gave" \
     "$(tail -n1 "$LOGD/repoRen-4.md")" ", lane:repoRen-4 ← lane:repoRen-1 — Brett Heap's word: shorten it"
has  "…while the lines ABOVE it are never rewritten and still say the old name" \
     "$(cat "$LOGD/repoRen-4.md")" "CLAIMED — lane repoRen-1,"
is   "…(d) the handoff moved to the same date with lane-<new>" \
     "$( [ -f "$RENH/session-handoff-2026-09-11-lane-repoRen-4.md" ] && [ ! -e "$RENH/session-handoff-2026-09-11-lane-repoRen-1.md" ] && echo yes )" "yes"
has  "…and gained its Rule 3 stamp under the header block" \
     "$(cat "$RENH/session-handoff-2026-09-11-lane-repoRen-4.md")" "RENAMED from repoRen-1 by $REN_ID (lane repoRen-4) at 20"
is   "…with the stamp SPLICED in: the file's own first line is untouched" \
     "$(head -n1 "$RENH/session-handoff-2026-09-11-lane-repoRen-4.md")" \
     "Lane: repoRen-1 (opensoft/team-05b, session $REN_ID) — single-use resume prompt"
has  "…and the row's handoff column following the file" \
     "$ren_row" "handoffs/repoRen/session-handoff-2026-09-11-lane-repoRen-4.md"
has  "…(e) lanes/aliases.tsv gained <old> <new> <UTC>" \
     "$(cat "$WIP/lanes/aliases.tsv")" "$(printf 'repoRen-1\trepoRen-4\t20')"

ren_show="$(git -C "$WIP" show --name-only --format=%s HEAD)"
has  "…and all four are in ONE commit, whose subject names the act" "$ren_show" "RENAMED lane repoRen-1 → repoRen-4"
has  "…carrying the register" "$ren_show" "lanes/LANES.md"
has  "…the log at its new name" "$ren_show" "lanes/log/repoRen-4.md"
has  "…the handoff at its new name" "$ren_show" "handoffs/repoRen/session-handoff-2026-09-11-lane-repoRen-4.md"
has  "…and the alias table" "$ren_show" "lanes/aliases.tsv"
is   "…ONE commit and not four" "$(git -C "$WIP" rev-list --count "$ren_before..HEAD")" 1
is   "…and it is pushed" "$(git -C "$WIP" rev-parse HEAD)" "$(git -C "$WIP" rev-parse origin/main)"
hasnt "…--no-github reached no GitHub surface at all" "$err" "comment posted"

# ------------------ clause (e): the old name resolves, in every reader at once
run "$E" canon-lane repoRen-1
is   "canon-lane answers the NEW name for the old one" "$out" "repoRen-4"
has  "…and SAYS it resolved a former name" "$err" "is a FORMER name of lane repoRen-4"

run "$E" who --lane repoRen-1
is   "who --lane <old> answers for the lane it is now" "$rc" 0
has  "…reporting the hold whose own log line still spells the old name" "$out" "opensoft/repoRen#4"

run "$E" lane-objects repoRen-1
has  "lane-objects <old> reads the renamed log" "$out" "opensoft/repoRen#4"

run "$E" register-row repoRen-1
has  "register-row <old> answers with the row that is there now" "$out" "\`repoRen-4\`"

run "$E" who "opensoft/repoRen#4"
has  "the object's holder is reported under the lane's CURRENT name" "$out" "repoRen-4"
hasnt "…and never under the name its own line was written with" "$out" "lane repoRen-1 "

run "$E" live-holder repoRen-1
is   "live-holder <old> reads the new row and answers 8, not 'no such lane'" "$rc" 8

# THE SessionStart BLOCK IS NAMED IN CLAUSE (e)'s OWN LIST, and it is the read
# that orients a session which has just come up in a window nobody renamed.
ss_save_name="${FAKE_TMUX_WINDOW_NAME-}"
export FAKE_TMUX_WINDOW_NAME=repoRen-1
ss_run "$REN_ID" resume
is    "the SessionStart block exits 0 for a window carrying the lane's FORMER name" "$rc" 0
has   "…orienting the session to the lane it is now" "$out" "LANE repoRen-4"
hasnt "…and never telling a bound lane that nothing binds its window" "$out" "no lane bound to this window"
has   "…with the hold it still has, under the object's own key" "$out" "open: CLAIMED opensoft/repoRen#4"
export FAKE_TMUX_WINDOW_NAME="$ss_save_name"

run "$E" lanes --all
has  "the listing carries the lane under its new name" "$out" "repoRen-4"
is   "…exactly once, and not as two lanes" "$(printf '%s\n' "$out" | command grep -c 'repoRen-4')" 1

run env LANES_SESSION="$REN_ID" "$E" append-line "LANDING — lane repoRen-1, session $REN_ID@$WS_S, $(utc_at -1M), PR #4 into opensoft/repoRen main"
is   "a Rule 6 line naming the OLD lane is appended" "$rc" 0
has  "…and ATTRIBUTED to the lane it is now" "$(git -C "$WIP" log --oneline -1)" "LANES(repoRen-4@$WS_S): append line"

# ---------------------------------------------- a chain resolves to its end
run env LANES_SESSION="$REN_ID" "$E" rename-lane repoRen-4 repoRen-7 "again" --no-github
is   "a second rename of the same lane exits 0" "$rc" 0
run "$E" canon-lane repoRen-1
is   "…and the FIRST name resolves through the chain to its end" "$out" "repoRen-7"
run "$E" canon-lane repoRen-4
is   "…as does the middle one" "$out" "repoRen-7"
run "$E" who --lane repoRen-1
has  "…and the hold is still found under the oldest name of all" "$out" "opensoft/repoRen#4"

# ---------------------------- renaming BACK into its own chain is refused, and
# a cycle in the table is refused at write time
#
# THE TWO REFUSALS OVERLAP ON PURPOSE. Every name on a chain is an alias KEY, so
# the key refusal (Copilot round 1) is the one a rename back meets first — and
# it is the broader rule: a row under a former name would end that name
# resolving whether or not the chain closes. The cycle test behind it is what
# still answers for a table somebody edited by hand, which is the only other way
# one can arrive.
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN_ID" "$E" rename-lane repoRen-7 repoRen-1 --no-github
is   "renaming back to a name in its own chain is refused" "$rc" 2
has  "…because a row under a former name would end that name resolving" "$err" "already a FORMER name"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"

# ---- A CYCLE PUT THERE BY HAND IS READ AS NO ANSWER, NOT AS A LANE.
ren_cyc="$SANDBOX/aliases-cycle.tsv"
{ printf '# a table somebody edited by hand\n'
  printf 'cycA-1\tcycB-1\t2026-09-15T00:00:00Z\n'
  printf 'cycB-1\tcycA-1\t2026-09-15T00:00:01Z\n'
} > "$ren_cyc"
run env LANES_NO_FETCH=1 LANES_ALIASES_TSV="$ren_cyc" LANES_ALIASES_PATH=lanes/aliases-cycle.tsv "$E" canon-lane cycA-1
is   "a hand-written CYCLE answers the name exactly as typed" "$out" "cycA-1"
has  "…and says the table names no lane at all" "$err" "CYCLE"

# --------------------------------- the verb: a lane kind that changes no state
run env LANES_LANE=repoRen-7 LANES_SESSION="$REN_ID" "$E" log RENAMED "lane:repoRen-7" --no-github
is   "a RENAMED written by hand is refused" "$rc" 2
has  "…naming the one word that writes it" "$err" "lane-rename"
run env LANES_LANE=repoRen-7 LANES_SESSION="$REN_ID" "$E" log PAUSED "lane:repoRen-7" → "swap; window rensess:0; workstation Eagle" --no-github
is   "the lane's own PAUSED still writes" "$rc" 0
run "$E" lane-last repoRen-7
has  "…and the RENAMED above it is skipped by the last-lane-kind-line read" "$out" "PAUSED"
run "$E" swapped Eagle
has  "…so a renamed lane that has since PAUSED still reads as swapped" "$out" "repoRen-7"

# --------------------------------------- clause (h): `lanes` stays read-only
run "$OPENREPOTOOLS_BIN_DIR/lanes" --rename repoRen-7 repoRen-8
is   "lanes --rename is refused" "$rc" 64
has  "…naming the one word to type, filled in" "$err" "lane-rename repoRen-7 repoRen-8"
has  "…and saying why it is not an option of this command" "$err" "writes nothing"

# ------------- clause (f): the guard finishes a window that carries the old name
#
# THE FIXTURE IS CAPTURED AND PUT BACK, exactly as the Amendment 12 section
# above does and for its reason: this section sits between two others in one
# long file, and a section that left the sandbox's window table changed would be
# changing the premise of every case after it from a distance.
A16_SAVE_WINDOWS="${FAKE_TMUX_WINDOWS-}"
A16_SAVE_WINDOW="${FAKE_TMUX_WINDOW-}"
A16_SAVE_NAME="${FAKE_TMUX_WINDOW_NAME-}"
export FAKE_TMUX_WINDOW="rensess:@16"
export FAKE_TMUX_WINDOW_NAME=repoRen-1
export FAKE_TMUX_WINDOWS="$(printf 'rensess:0\t@16\trepoRen-1\t%%16\tclaude')"
write_record_a12 "$sessions_dir/a16.json" "$REN_ID" "$LIVE_PID" "$live_start" interactive "rensess:@16.%16" "repoRen-1" user "$GD_OLD_MS"
a16_keys="$(command grep -c 'send-keys' "$FAKE_TMUX_LOG" || :)"
a16_ren="$(command grep -c 'rename-window' "$FAKE_TMUX_LOG" || :)"
out="$(printf '{"session_id":"%s","cwd":"%s/projects/repoRen","prompt":"do the work","hook_event_name":"UserPromptSubmit"}' "$REN_ID" "$HOME" | "$E" guard 2>"$SANDBOX/stderr")"; rc=$?
err="$(cat "$SANDBOX/stderr")"
is   "a window still carrying the lane's FORMER name does not read as 'no lane'" "$rc" 2
hasnt "…so the guard never sends a running lane to bind a row it already has" "$err" "lane-start --no-launch"
has  "…the triple naming the window as a former name of the lane" "$err" "a former name of repoRen-7"
has  "…and the guard renames the WINDOW itself, which needs nobody" "$err" "it has been renamed to repoRen-7 for you"
is   "…as one tmux call" "$(command grep -c 'rename-window repoRen-7' "$FAKE_TMUX_LOG" || :)" 1
has  "…while the SESSION's name is typed, which is the only path it has" "$(cat "$FAKE_TMUX_LOG")" "send-keys -t %16 /rename repoRen-7"
rm -f "$sessions_dir/a16.json"

# ---------------------------------- the word: `lane-rename` on PATH (clause (f))
REN2_ID="12ab34cd-16a2-4000-8000-12ab34cd16a2"
add_seed_row "| \`repoRenW-1\` | harness \`$REN2_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoRen/w.md | ACTIVE |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the lane-rename word's own lane"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
RENAME="$OPENREPOTOOLS_BIN_DIR/lane-rename"

export FAKE_TMUX_WINDOW_NAME=some-other-window
run env LANES_SESSION="$REN2_ID" "$RENAME" repoRenW-1 repoRenW-2 --no-github
is   "lane-rename from another window still renames the lane" "$rc" 0
has  "…and says the window and the session are the lane's own to fix" "$out" "tmux rename-window repoRenW-2"
has  "…naming the guard as what does it at the lane's next prompt" "$out" "/rename repoRenW-2"

export FAKE_TMUX_WINDOW="rensess:@17"
export FAKE_TMUX_WINDOW_NAME=repoRenW-2
export FAKE_TMUX_WINDOWS="$(printf 'rensess:0\t@17\trepoRenW-2\t%%17\tclaude')"
write_record_a12 "$sessions_dir/a16w.json" "$REN2_ID" "$LIVE_PID" "$live_start" interactive "rensess:@17.%17" "repoRenW-2" user "$GD_OLD_MS"
: > "$FAKE_TMUX_LOG"
run env LANES_SESSION="$REN2_ID" CLAUDE_CODE_SESSION_ID="$REN2_ID" "$RENAME" repoRenW-2 repoRenW-3 --no-github
is   "lane-rename in the lane's OWN window exits 0" "$rc" 0
is   "…renaming the window in the same breath" "$(command grep -c 'rename-window repoRenW-3' "$FAKE_TMUX_LOG" || :)" 1
has  "…and typing the one line a running session's name can only take that way" \
     "$(cat "$FAKE_TMUX_LOG")" "send-keys -t %17 /rename repoRenW-3"
rm -f "$sessions_dir/a16w.json"

run env LANES_SESSION="$REN2_ID" "$RENAME" repoRenW-3
is   "lane-rename with one argument is a usage refusal" "$rc" 2
run env LANES_SESSION="$REN2_ID" "$RENAME" repoRenW-3 repoRenW-9 --nonsense
is   "…as is an option it does not know" "$rc" 2


# ============ Copilot round 1 on openRepoTools#81: the states it found ========

# ---- A `<new>` THAT IS ALREADY AN ALIAS KEY IS REFUSED.
#
# A row wins over an alias at every hop, so minting a row under a name some
# other lane was renamed AWAY from would END that lane's old name resolving —
# the one thing clause (e) promises never happens.
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN2_ID" "$E" rename-lane repoRenW-3 repoRen-1 --no-github
is   "renaming INTO a name that is already an alias key is refused" "$rc" 2
has  "…because a row under it would end that lane's old name resolving" "$err" "already a FORMER name"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"

# ---- A ROW WINS OVER AN ALIAS AT EVERY HOP, NOT ONLY AT THE START.
#
# `repoRen-1` was renamed away, so the NAME is free and a lane may legitimately
# be created under it again — which `lane_next_free` will hand out. Read through
# the chain's END that lane's own log lines would be remapped on to repoRen-7,
# whose holds are somebody else's.
REN3_ID="12ab34cd-16a3-4000-8000-12ab34cd16a3"
add_seed_row "| \`repoRen-1\` | harness \`$REN3_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | handoffs/repoRen/again.md | ACTIVE |"
{ printf '# lane repoRen-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoRen-1, session %s@Eagle, %s, lane:repoRen-1 → home opensoft/repoRen; estate repoRen\n' "$REN3_ID" "$OLD_UTC"
  printf 'CLAIMED — lane repoRen-1, session %s@Eagle, %s, opensoft/repoRen#12\n' "$REN3_ID" "$OLD_UTC"
} > "$LOGD/repoRen-1.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a NEW lane under a name that is already an alias key"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

run "$E" canon-lane repoRen-1
is    "a name that is an alias key AND a row again answers the ROW" "$out" "repoRen-1"
hasnt "…without claiming it resolved a former name" "$err" "FORMER name"
run "$E" who --lane repoRen-1
has   "…and that lane's own holds are its own" "$out" "opensoft/repoRen#12"
hasnt "…never the holds of the lane that used to have the name" "$out" "opensoft/repoRen#4"
run "$E" who --lane repoRen-7
has   "…while the renamed lane keeps its own, read under its current name" "$out" "opensoft/repoRen#4"
hasnt "…and does not collect the new lane's" "$out" "opensoft/repoRen#12"

# ---- A CASE-VARIANT LOG FOR `<new>` IS FOUND AND REFUSED.
ren_before="$(git -C "$WIP" rev-parse HEAD)"
printf '# lane REPOREN-20 — object log\n' > "$LOGD/REPOREN-20.md"
run env LANES_SESSION="$REN3_ID" "$E" rename-lane repoRen-1 repoRen-20 --no-github
is   "a rename into a name whose log exists under ANOTHER CASE is refused" "$rc" 2
has  "…naming the file that is there" "$err" "REPOREN-20.md"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
rm -f "$LOGD/REPOREN-20.md"

# ---- A HANDOFF OUTSIDE THE WORKSPACE REPOSITORY IS REFUSED, NOT NOTED.
#
# Four moves in ONE commit cannot carry a file outside the checkout the commit
# is made in, so a row naming one is refused before anything is written.
REN4_ID="12ab34cd-16a4-4000-8000-12ab34cd16a4"
mkdir -p "$SANDBOX/outside"
printf 'Lane: repoOut-1 — single-use resume prompt\n\n## RESUME\n' > "$SANDBOX/outside/h.md"
add_seed_row "| \`repoOut-1\` | harness \`$REN4_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | $SANDBOX/outside/h.md | ACTIVE |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a lane whose handoff is outside the workspace repository"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN4_ID" "$E" rename-lane repoOut-1 repoOut-2 --no-github
is   "a handoff outside the workspace repository is refused" "$rc" 2
has  "…saying a commit cannot carry it" "$err" "outside the workspace repository"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
is   "…the row still under its own name" "$(command grep -c '^| `repoOut-1`' "$LANES")" 1

# ---- A WRITE THAT FAILS PART-WAY IS ROLLED BACK, NOT LEFT HALF-RENAMED.
#
# The handoff is made UNWRITABLE, so Rule 3's stamp cannot land — the failure
# that used to leave the log moved, its RENAMED line appended and the rename
# committed anyway.
REN5_ID="12ab34cd-16a5-4000-8000-12ab34cd16a5"
mkdir -p "$WIP/handoffs/repoRoll"
printf 'Lane: repoRoll-1 — single-use resume prompt\n\n## RESUME\n' > "$WIP/handoffs/repoRoll/session-handoff-2026-09-12-lane-repoRoll-1.md"
add_seed_row "| \`repoRoll-1\` | harness \`$REN5_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | handoffs/repoRoll/session-handoff-2026-09-12-lane-repoRoll-1.md | ACTIVE |"
{ printf '# lane repoRoll-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoRoll-1, session %s@Eagle, %s, lane:repoRoll-1 → home opensoft/repoRoll; estate repoRoll\n' "$REN5_ID" "$OLD_UTC"
} > "$LOGD/repoRoll-1.md"
git -C "$WIP" add -A -- lanes handoffs >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the rollback lane"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
roll_log_before="$(cat "$LOGD/repoRoll-1.md")"
ren_before="$(git -C "$WIP" rev-parse HEAD)"
chmod 0444 "$WIP/handoffs/repoRoll/session-handoff-2026-09-12-lane-repoRoll-1.md"
chmod 0555 "$WIP/handoffs/repoRoll"
run env LANES_SESSION="$REN5_ID" "$E" rename-lane repoRoll-1 repoRoll-2 --no-github
chmod 0755 "$WIP/handoffs/repoRoll"
chmod 0644 "$WIP/handoffs/repoRoll"/*.md 2>/dev/null || :
if [ "$rc" = 0 ]; then
  skip "a handoff that cannot take its stamp refuses and rolls back" "this filesystem let the write through (running as a user that ignores the mode)"
else
  is   "a handoff that cannot take its Rule 3 stamp refuses" "$rc" 5
  is   "…rolling the object log back to where it was" "$(cat "$LOGD/repoRoll-1.md" 2>/dev/null)" "$roll_log_before"
  is   "…leaving no log under the new name" "$( [ -e "$LOGD/repoRoll-2.md" ] && echo yes || echo no )" "no"
  is   "…the handoff still at its own path" "$( [ -f "$WIP/handoffs/repoRoll/session-handoff-2026-09-12-lane-repoRoll-1.md" ] && echo yes )" "yes"
  is   "…and nothing committed" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
  is   "…with the row untouched" "$(command grep -c '^| `repoRoll-1`' "$LANES")" 1
  has  "…and it says the rename was rolled back" "$err" "rolled back"
fi
git -C "$WIP" checkout -- lanes handoffs 2>/dev/null || :

# ---- AN UNREADABLE ALIAS TABLE FAILS CLOSED RATHER THAN READING AS EMPTY.
#
# POINTED AT A PATH `origin` DOES NOT CARRY, because the published copy is a git
# OBJECT and no mode on the working tree can stop `git show` reading it — which
# is the right answer for a checkout whose file is merely unreadable, and the
# wrong fixture for the question asked here.
ren_unread="$WIP/lanes/aliases-unreadable.tsv"
printf 'someLane-1\tsomeLane-2\t2026-09-15T00:00:00Z\n' > "$ren_unread"
chmod 0000 "$ren_unread"
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_NO_FETCH=1 LANES_SESSION="$REN3_ID" \
    LANES_ALIASES_TSV="$ren_unread" LANES_ALIASES_PATH=lanes/aliases-unreadable.tsv \
    "$E" rename-lane repoRen-1 repoRen-21 --no-github
if [ "$rc" = 0 ]; then
  skip "an unreadable alias table refuses the write" "this filesystem let the read through (running as a user that ignores the mode)"
else
  is    "an alias table that cannot be READ refuses the write" "$rc" 1
  has   "…rather than reading as an estate with no renames" "$err" "could not be read"
  has   "…naming the table and the read that failed" \
        "$err" "aliases-unreadable.tsv is there and could not be read"
  hasnt "…and never 'unknown error', which is what a reason lost to a subshell said" \
        "$err" "unknown error"
  is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
fi
chmod 0644 "$ren_unread"; rm -f "$ren_unread"

# ---- THE WORD'S REPAIR RUN: the write has landed, the window has not.
export FAKE_TMUX_WINDOW="rensess:@18"
export FAKE_TMUX_WINDOW_NAME=repoRenW-2
export FAKE_TMUX_WINDOWS="$(printf 'rensess:0\t@18\trepoRenW-2\t%%18\tclaude')"
: > "$FAKE_TMUX_LOG"
run env LANES_SESSION="$REN2_ID" "$RENAME" repoRenW-2 repoRenW-3 --no-github
is   "re-running the word after the write has landed exits 0" "$rc" 0
has  "…saying the rename itself is already done" "$err" "already landed"
is   "…and doing the half that is left: the window" "$(command grep -c 'rename-window repoRenW-3' "$FAKE_TMUX_LOG" || :)" 1


# ============ Copilot round 3 on openRepoTools#81 ============================

# ---- AN UNREADABLE ALIAS TABLE REFUSES THE READERS TOO, not only the writes.
#
# `canon_lane`'s answer is what `lane-start` decides "is this lane new" by, so
# carrying on with the typed spelling is not a read-only shrug: a renamed lane
# would read as new and get a SECOND row.
ren_unread2="$WIP/lanes/aliases-unread2.tsv"
printf 'someLane-1\tsomeLane-2\t2026-09-15T00:00:00Z\n' > "$ren_unread2"
chmod 0000 "$ren_unread2"
run env LANES_NO_FETCH=1 LANES_ALIASES_TSV="$ren_unread2" LANES_ALIASES_PATH=lanes/aliases-unread2.tsv \
    "$E" canon-lane repoRen-4
if [ "$rc" = 0 ]; then
  skip "canon-lane refuses on an alias table it cannot read" "this filesystem let the read through"
else
  is    "canon-lane REFUSES on an alias table it cannot read" "$rc" 66
  has   "…rather than answering the typed spelling" "$err" "NOT established"
  hasnt "…and answers nothing at all" "$out" "repoRen"
fi

# ---- AND THE NAME GUARD REFUSES THE PROMPT ON IT (clause (d) is fail closed).
gd_save_w="${FAKE_TMUX_WINDOW-}"; gd_save_n="${FAKE_TMUX_WINDOW_NAME-}"; gd_save_ws="${FAKE_TMUX_WINDOWS-}"
# THE WINDOW CARRIES A NAME WITH NO ROW, which is what makes the guard ASK the
# alias table at all: `repoRen-4` is a middle name of this lane's chain, so a
# name that does have a row would be answered by the register alone and this
# case would prove nothing.
export FAKE_TMUX_WINDOW="rensess:@19"
export FAKE_TMUX_WINDOW_NAME=repoRen-4
export FAKE_TMUX_WINDOWS="$(printf 'rensess:0\t@19\trepoRen-4\t%%19\tclaude')"
write_record_a12 "$sessions_dir/a16g.json" "$REN_ID" "$LIVE_PID" "$live_start" interactive "rensess:@19.%19" "repoRen-4" user "$GD_OLD_MS"
out="$(printf '{"session_id":"%s","cwd":"%s/projects/repoRen","prompt":"do the work","hook_event_name":"UserPromptSubmit"}' "$REN_ID" "$HOME" \
      | env LANES_ALIASES_TSV="$ren_unread2" LANES_ALIASES_PATH=lanes/aliases-unread2.tsv "$E" guard 2>"$SANDBOX/stderr")"; rc=$?
err="$(cat "$SANDBOX/stderr")"
if [ "$rc" = 0 ]; then
  skip "the guard refuses a prompt on an alias table it cannot read" "this filesystem let the read through"
else
  is    "the guard REFUSES the prompt on an alias table it cannot read" "$rc" 2
  has   "…because a triple that cannot be verified is not a triple that agrees" "$err" "could not be read"
  hasnt "…and never sends a running lane to bind a row it already has" "$err" "lane-start --no-launch"
fi
rm -f "$sessions_dir/a16g.json"
export FAKE_TMUX_WINDOW="$gd_save_w"; export FAKE_TMUX_WINDOW_NAME="$gd_save_n"; export FAKE_TMUX_WINDOWS="$gd_save_ws"
chmod 0644 "$ren_unread2"; rm -f "$ren_unread2"

# ---- A HANDOFF PATH THAT EXISTS AND IS NOT A REGULAR FILE IS REFUSED.
REN6_ID="12ab34cd-16a6-4000-8000-12ab34cd16a6"
mkdir -p "$WIP/handoffs/repoKind/session-handoff-2026-09-12-lane-repoKind-1.md"
add_seed_row "| \`repoKind-1\` | harness \`$REN6_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | handoffs/repoKind/session-handoff-2026-09-12-lane-repoKind-1.md | ACTIVE |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a lane whose handoff path is a directory"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN6_ID" "$E" rename-lane repoKind-1 repoKind-2 --no-github
is   "a handoff path that is a DIRECTORY is refused, not read as absent" "$rc" 2
has  "…saying what it found there" "$err" "is not a regular file"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
rmdir "$WIP/handoffs/repoKind/session-handoff-2026-09-12-lane-repoKind-1.md"

# ---- AN ALIAS TABLE PUBLISHED AND NOT PULLED IS REFUSED, NOT OVERWRITTEN.
rm -f "$WIP/lanes/aliases.tsv"
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN6_ID" "$E" rename-lane repoKind-1 repoKind-2 --no-github
is   "an alias table origin carries and this checkout does not is refused" "$rc" 2
has  "…because appending here would drop every alias already published" "$err" "drop every alias already published"
has  "…and it names the pull" "$err" "pull --rebase"
is   "…with nothing written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
git -C "$WIP" checkout -- lanes/aliases.tsv

# ---- THE LANE'S OWN SESSION KEEPS ITS FORMER NAME UNTIL ITS NEXT PROMPT,
# AND IS STILL ITS HOLDER (Amendment 16(e) meeting Amendment 8's explicit-name
# rule). Without this the rename's own window loses the `/rename` clause (f)
# gives it, and `who` calls a running lane NOT LIVE.
# `repoRen-4`, NOT `repoRen-1`: the first name of this chain is a row again —
# a different lane — so a session named for it IS another lane's, which is the
# case below. `repoRen-4` is the middle name and belongs to nobody else.
write_record_a12 "$sessions_dir/a16h.json" "$REN_ID" "$LIVE_PID" "$live_start" interactive "rensess:@20.%20" "repoRen-4" user "$GD_OLD_MS"
run "$E" live-holder repoRen-7
is   "a live session still named for the lane's FORMER name is its holder" "$rc" 0
has  "…named as the session it is" "$out" "$REN_ID"
rm -f "$sessions_dir/a16h.json"

# ---- AND A FORMER NAME THAT IS A ROW AGAIN IS ANOTHER LANE (the row wins).
write_record_a12 "$sessions_dir/a16j.json" "$REN_ID" "$LIVE_PID" "$live_start" interactive "rensess:@20.%20" "repoRen-1" user "$GD_OLD_MS"
run "$E" live-holder repoRen-7
is   "…while a former name somebody has since taken as a LANE is not this one" "$rc" 8
rm -f "$sessions_dir/a16j.json"

# ---- AND A SESSION A PERSON NAMED FOR ANOTHER LANE IS STILL NOT (Amendment 8).
write_record_a12 "$sessions_dir/a16i.json" "$REN_ID" "$LIVE_PID" "$live_start" interactive "rensess:@20.%20" "repoD-2" user "$GD_OLD_MS"
run "$E" live-holder repoRen-7
is   "…while a session named for a DIFFERENT lane is not a holder, as before" "$rc" 8
rm -f "$sessions_dir/a16i.json"


# ============ Copilot round 4 on openRepoTools#81 ============================

# ---- THE ALIAS-READ REFUSAL HAS ITS OWN EXIT CODE, because 2 already carries
# two meanings to the four commands that read `canon-lane`.
ren_unread3="$WIP/lanes/aliases-unread3.tsv"
printf 'someLane-1\tsomeLane-2\t2026-09-15T00:00:00Z\n' > "$ren_unread3"
chmod 0000 "$ren_unread3"
run env LANES_NO_FETCH=1 LANES_ALIASES_TSV="$ren_unread3" LANES_ALIASES_PATH=lanes/aliases-unread3.tsv \
    "$E" canon-lane repoRen-4
if [ "$rc" = 0 ]; then
  skip "canon-lane spends EX_NOINPUT on a table it cannot read" "this filesystem let the read through"
else
  is   "canon-lane spends 66 (EX_NOINPUT) on a table it cannot read, never 2" "$rc" 66
  # ---- AND live-holder FAILS CLOSED ON IT rather than answering 'no holder'.
  write_record_a12 "$sessions_dir/a16k.json" "$REN_ID" "$LIVE_PID" "$live_start" interactive "rensess:@21.%21" "repoRen-4" user "$GD_OLD_MS"
  run env LANES_NO_FETCH=1 LANES_ALIASES_TSV="$ren_unread3" LANES_ALIASES_PATH=lanes/aliases-unread3.tsv \
      "$E" live-holder repoRen-7
  is   "live-holder fails CLOSED on a table it cannot read" "$rc" 1
  hasnt "…rather than answering 8, which reads as 'no live session holds it'" "$rc" 8
  has  "…naming the read that could not be made" "$err" "could not be read"
  rm -f "$sessions_dir/a16k.json"
  # ---- AND lane-start REFUSES rather than adding a second row.
  mkdir -p "$HOME/projects/repoRen"
  run env LANES_NO_FETCH=1 LANES_ALIASES_TSV="$ren_unread3" LANES_ALIASES_PATH=lanes/aliases-unread3.tsv \
      "$START" --no-launch --dir "$HOME/projects/repoRen" repoRen-4
  is   "lane-start REFUSES a name it cannot resolve through the alias table" "$rc" 2
  has  "…saying it would add a second row for a lane that is running" "$err" "second row"
fi
chmod 0644 "$ren_unread3"; rm -f "$ren_unread3"

# ---- A SYMLINKED OBJECT LOG, HANDOFF OR ALIAS TABLE IS REFUSED.
#
# All three are written IN PLACE with a redirect or an append, which follows a
# link: the bytes would land at the far end while the commit recorded the link.
REN7_ID="12ab34cd-16a7-4000-8000-12ab34cd16a7"
mkdir -p "$SANDBOX/faraway" "$WIP/handoffs/repoLink"
printf '# lane repoLink-1 — object log (lane-collision-protocol Amendment 7)\n' > "$SANDBOX/faraway/log.md"
printf 'Lane: repoLink-1 — single-use resume prompt\n\n## RESUME\n' > "$WIP/handoffs/repoLink/session-handoff-2026-09-12-lane-repoLink-1.md"
add_seed_row "| \`repoLink-1\` | harness \`$REN7_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | handoffs/repoLink/session-handoff-2026-09-12-lane-repoLink-1.md | ACTIVE |"
git -C "$WIP" add -A -- lanes handoffs >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the symlink-refusal lane"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

ln -s "$SANDBOX/faraway/log.md" "$LOGD/repoLink-1.md"
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN7_ID" "$E" rename-lane repoLink-1 repoLink-2 --no-github
is   "a SYMLINKED object log is refused" "$rc" 2
has  "…because an append-only log is written in place" "$err" "is a SYMLINK"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
is   "…and the far end is untouched" "$(wc -l < "$SANDBOX/faraway/log.md" | tr -d ' ')" 1
rm -f "$LOGD/repoLink-1.md"
printf '# lane repoLink-1 — object log (lane-collision-protocol Amendment 7)\n' > "$LOGD/repoLink-1.md"
# AND COMMITTED, because an UNTRACKED source log is its own refusal now (round
# 6) and would answer every case below this one instead of the one it asks.
git -C "$WIP" add -- lanes/log/repoLink-1.md >/dev/null 2>&1
git -C "$WIP" commit -q -m "commit the symlink-refusal lane's own log"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

mv "$WIP/handoffs/repoLink/session-handoff-2026-09-12-lane-repoLink-1.md" "$SANDBOX/faraway/h.md"
ln -s "$SANDBOX/faraway/h.md" "$WIP/handoffs/repoLink/session-handoff-2026-09-12-lane-repoLink-1.md"
run env LANES_SESSION="$REN7_ID" "$E" rename-lane repoLink-1 repoLink-2 --no-github
is   "a SYMLINKED handoff is refused" "$rc" 2
has  "…because Rule 3's stamp is written in place" "$err" "is a SYMLINK"
hasnt "…and the far end took no stamp" "$(cat "$SANDBOX/faraway/h.md")" "RENAMED from"
rm -f "$WIP/handoffs/repoLink/session-handoff-2026-09-12-lane-repoLink-1.md"
mv "$SANDBOX/faraway/h.md" "$WIP/handoffs/repoLink/session-handoff-2026-09-12-lane-repoLink-1.md"

ren_alias_real="$WIP/lanes/aliases.tsv"
mv "$ren_alias_real" "$SANDBOX/faraway/aliases.tsv"
ln -s "$SANDBOX/faraway/aliases.tsv" "$ren_alias_real"
run env LANES_SESSION="$REN7_ID" "$E" rename-lane repoLink-1 repoLink-2 --no-github
is   "a SYMLINKED alias table is refused" "$rc" 2
has  "…because the alias row is appended in place" "$err" "is a SYMLINK"
rm -f "$ren_alias_real"
mv "$SANDBOX/faraway/aliases.tsv" "$ren_alias_real"

# ---- AN UNCOMMITTED ALIAS TABLE IS SOMEBODY ELSE'S HALF-FINISHED RENAME.
printf 'peerLane-1\tpeerLane-2\t2026-09-15T00:00:00Z\n' >> "$ren_alias_real"
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN7_ID" "$E" rename-lane repoLink-1 repoLink-2 --no-github
is   "a DIRTY alias table refuses the rename rather than being swept into it" "$rc" 2
has  "…naming the file that is not this write's" "$err" "aliases.tsv"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
git -C "$WIP" checkout -- lanes/aliases.tsv

# ---- THE REGISTER IS IN THE ROLLBACK TOO.
#
# `commit_push` can die on `git add` or `git commit` BEFORE any commit exists,
# and the row is written before it. A `pre-commit` hook that refuses is the
# smallest honest way to reach that branch: no commit is made, so all FOUR must
# come back — the register with them, or the checkout is left in a split rename.
ren_reg_before="$(cat "$LANES")"
ren_log_before="$(cat "$LOGD/repoLink-1.md")"
ren_alias_before="$(cat "$ren_alias_real")"
ren_before="$(git -C "$WIP" rev-parse HEAD)"
mkdir -p "$WIP/.git/hooks"
printf '#!/bin/sh\nexit 1\n' > "$WIP/.git/hooks/pre-commit"
chmod 755 "$WIP/.git/hooks/pre-commit"
run env LANES_SESSION="$REN7_ID" "$E" rename-lane repoLink-1 repoLink-2 --no-github
rm -f "$WIP/.git/hooks/pre-commit"
is   "a commit that never happens leaves NOTHING renamed" "$rc" 6
is   "…the register back, row and all" "$(cat "$LANES")" "$ren_reg_before"
is   "…the object log back under its own name" "$(cat "$LOGD/repoLink-1.md" 2>/dev/null)" "$ren_log_before"
is   "…and no log under the new one" "$( [ -e "$LOGD/repoLink-2.md" ] && echo yes || echo no )" "no"
is   "…the alias table back" "$(cat "$ren_alias_real")" "$ren_alias_before"
is   "…the handoff back under its own name" \
     "$( [ -f "$WIP/handoffs/repoLink/session-handoff-2026-09-12-lane-repoLink-1.md" ] && echo yes )" "yes"
is   "…and nothing committed" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
is   "…with nothing left staged for the next writer to commit by accident" \
     "$(git -C "$WIP" diff --cached --name-only | grep -c . || :)" 0
has  "…and it says the rename was rolled back" "$err" "rolled back"

# ---- AND THE SAME RENAME THEN GOES THROUGH, which is what "refused or whole"
# is worth: a refusal leaves a checkout a re-run can use.
run env LANES_SESSION="$REN7_ID" "$E" rename-lane repoLink-1 repoLink-2 --no-github
is   "the same rename then goes through" "$rc" 0
is   "…and the row moved" "$(command grep -c '^| `repoLink-2`' "$LANES")" 1
is   "…with the log at its new name" "$( [ -f "$LOGD/repoLink-2.md" ] && echo yes )" "yes"


# ============ Copilot round 5 on openRepoTools#81 ============================

REN8_ID="12ab34cd-16a8-4000-8000-12ab34cd16a8"
mkdir -p "$WIP/handoffs/repoEdge" "$HOME/projects/outside"
printf 'Lane: repoEdge-1 — single-use resume prompt\n\n## RESUME\n' > "$HOME/projects/outside/h.md"
add_seed_row "| \`repoEdge-1\` | harness \`$REN8_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | handoffs/../../outside/h.md | ACTIVE |"
{ printf '# lane repoEdge-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoEdge-1, session %s@Eagle, %s, lane:repoEdge-1 → home opensoft/repoEdge; estate repoEdge\n' "$REN8_ID" "$OLD_UTC"
} > "$LOGD/repoEdge-1.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the round-5 edge lane"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

# ---- A HANDOFF THAT LEAVES THE WORKSPACE THROUGH `..` IS STILL OUTSIDE IT.
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN8_ID" "$E" rename-lane repoEdge-1 repoEdge-2 --no-github
is   "a handoff that leaves the workspace through '..' is refused" "$rc" 2
has  "…by the physical path, not by a string prefix" "$err" "outside the workspace repository"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
is   "…the far end untouched" "$(command grep -c 'RENAMED from' "$HOME/projects/outside/h.md" || :)" 0

# ---- A DANGLING SYMLINK AT THE DESTINATION IS OCCUPIED, NOT ABSENT.
"$E" replace-in-row repoEdge-1 "handoffs/../../outside/h.md" "handoffs/repoEdge/session-handoff-2026-09-12-lane-repoEdge-1.md" "point it inside the workspace" >/dev/null 2>&1
printf 'Lane: repoEdge-1 — single-use resume prompt\n\n## RESUME\n' > "$WIP/handoffs/repoEdge/session-handoff-2026-09-12-lane-repoEdge-1.md"
ln -s "$HOME/projects/outside/gone.md" "$WIP/handoffs/repoEdge/session-handoff-2026-09-12-lane-repoEdge-2.md"
git -C "$WIP" add -A -- handoffs >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the dangling destination" >/dev/null 2>&1
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN8_ID" "$E" rename-lane repoEdge-1 repoEdge-2 --no-github
is   "a DANGLING symlink at the handoff's destination is occupied" "$rc" 2
has  "…and says something is already there" "$err" "already there"
is   "…with nothing written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
git -C "$WIP" rm -q --cached -- handoffs/repoEdge/session-handoff-2026-09-12-lane-repoEdge-2.md >/dev/null 2>&1 || :
rm -f "$WIP/handoffs/repoEdge/session-handoff-2026-09-12-lane-repoEdge-2.md"
git -C "$WIP" commit -q -m "remove the dangling destination" >/dev/null 2>&1 || :
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main 2>/dev/null || :

# ---- A FIFO AT THE OLD LOG PATH IS REFUSED RATHER THAN READ.
#
# `cat` of one BLOCKS, for ever, holding this lane's mutex.
if command -v mkfifo >/dev/null 2>&1; then
  ren_log_keep="$(cat "$LOGD/repoEdge-1.md")"
  rm -f "$LOGD/repoEdge-1.md"
  mkfifo "$LOGD/repoEdge-1.md"
  ren_before="$(git -C "$WIP" rev-parse HEAD)"
  run env LANES_SESSION="$REN8_ID" "$E" rename-lane repoEdge-1 repoEdge-2 --no-github
  is   "a FIFO at the old log path is refused rather than read" "$rc" 2
  has  "…saying a read of one would block this write and its lock" "$err" "not a regular file"
  is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
  rm -f "$LOGD/repoEdge-1.md"
  printf '%s\n' "$ren_log_keep" > "$LOGD/repoEdge-1.md"
else
  skip "a FIFO at the old log path is refused rather than read" "no mkfifo on this host"
fi

# ---- AN ALIAS TABLE WITH NO TRAILING NEWLINE IS REFUSED.
#
# `>>` would put this record on the END of the previous line, and
# `append_text_line`'s own proof passes because it concatenates the same way —
# so the parser would never see the alias and the old name would stop resolving.
ren_alias_keep="$(cat "$WIP/lanes/aliases.tsv")"
printf '%s' "$ren_alias_keep" > "$WIP/lanes/aliases.tsv"
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN8_ID" "$E" rename-lane repoEdge-1 repoEdge-2 --no-github
is   "an alias table with no trailing newline is refused" "$rc" 2
has  "…because the record would join the line before it" "$err" "does not end with a newline"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
git -C "$WIP" checkout -- lanes/aliases.tsv

# ---- AN EXISTING UNTRACKED ALIAS TABLE IS SOMEBODY'S HAND EDIT.
#
# `tracked_dirty` deliberately omits untracked files, so the dirty-checkout
# refusal never sees one.
ren_alias_tracked="$(cat "$WIP/lanes/aliases.tsv")"
git -C "$WIP" rm -q --cached -- lanes/aliases.tsv >/dev/null 2>&1
git -C "$WIP" commit -q -m "make the alias table untracked for one case" >/dev/null 2>&1
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main 2>/dev/null || :
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN8_ID" "$E" rename-lane repoEdge-1 repoEdge-2 --no-github
is   "an existing UNTRACKED alias table is refused" "$rc" 2
has  "…because git does not track it and this command commits what it writes" "$err" "git does not track it"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
git -C "$WIP" add -- lanes/aliases.tsv >/dev/null 2>&1
git -C "$WIP" commit -q -m "track the alias table again" >/dev/null 2>&1
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main 2>/dev/null || :

# ---- AND WITH EVERY EDGE CLEARED, THE RENAME GOES THROUGH.
run env LANES_SESSION="$REN8_ID" "$E" rename-lane repoEdge-1 repoEdge-2 --no-github
is   "with every edge cleared the rename goes through" "$rc" 0
is   "…the row moved" "$(command grep -c '^| `repoEdge-2`' "$LANES")" 1
is   "…the log at its new name" "$( [ -f "$LOGD/repoEdge-2.md" ] && echo yes )" "yes"
is   "…the handoff at its new name" \
     "$( [ -f "$WIP/handoffs/repoEdge/session-handoff-2026-09-12-lane-repoEdge-2.md" ] && echo yes )" "yes"
has  "…and the alias table carries the pair" "$(cat "$WIP/lanes/aliases.tsv")" "$(printf 'repoEdge-1\trepoEdge-2\t20')"


# ============ Copilot round 6 on openRepoTools#81 ============================

# ---- A RENAMED IS SKIPPED BY THE ONE READER THAT TAKES THE LAST LANE-KIND
# LINE WHATEVER IT IS. `swapped_candidates` names the verbs it skips, so a lane
# whose LAST line is its rename must still read as PAUSED — otherwise `swapped`
# loses it and `restart` cannot bring it back.
REN9_ID="12ab34cd-16a9-4000-8000-12ab34cd16a9"
add_seed_row "| \`repoRSw-1\` | harness \`$REN9_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | handoffs/repoRSw/x.md | ACTIVE |"
{ printf '# lane repoRSw-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoRSw-1, session %s@Eagle, %s, lane:repoRSw-1 → home opensoft/repoRSw; estate repoRSw\n' "$REN9_ID" "$OLD_UTC"
  printf 'PAUSED — lane repoRSw-1, session %s@Eagle, 2026-09-14T09:00:00Z, lane:repoRSw-1 → swap; window swsess:2; workstation Eagle\n' "$REN9_ID"
} > "$LOGD/repoRSw-1.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a swapped lane about to be renamed"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
run "$E" swapped Eagle
has  "a PAUSED lane reads as swapped before the rename" "$out" "repoRSw-1"
# ITS ROW NAMES A HANDOFF DIRECTORY NOTHING HAS CREATED, which is the ordinary
# state of every lane before its first swap — `lane-start` puts the path in the
# row and `lane-handoff` writes the file later — so this case also holds the
# containment test to the nearest ancestor that EXISTS.
run env LANES_SESSION="$REN9_ID" "$E" rename-lane repoRSw-1 repoRSw-2 --no-github
is   "…and the rename goes through" "$rc" 0
run "$E" swapped Eagle
has  "…and it STILL reads as swapped, under its new name, with RENAMED as its last line" "$out" "repoRSw-2"
hasnt "…and not under the old one" "$out" "repoRSw-1	" 
run "$E" lane-last repoRSw-2
has  "…while the last LANE-kind line a state read takes is still the PAUSED" "$out" "PAUSED"

# ---- AN UNTRACKED OBJECT LOG OR HANDOFF IS SOMEBODY'S UNCOMMITTED WORK.
#
# `tracked_dirty` reports no untracked file, so the dirty-checkout refusal never
# sees one — and this rename would MOVE it to a path it always stages.
REN10_ID="12ab34cd-16b0-4000-8000-12ab34cd16b0"
add_seed_row "| \`repoUnt-1\` | harness \`$REN10_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | handoffs/repoUnt/session-handoff-2026-09-12-lane-repoUnt-1.md | ACTIVE |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the untracked-source lane"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
{ printf '# lane repoUnt-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoUnt-1, session %s@Eagle, %s, lane:repoUnt-1 → home opensoft/repoUnt; estate repoUnt\n' "$REN10_ID" "$OLD_UTC"
} > "$LOGD/repoUnt-1.md"
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN10_ID" "$E" rename-lane repoUnt-1 repoUnt-2 --no-github
is   "an UNTRACKED object log is refused, not moved into this commit" "$rc" 2
has  "…because its lines have never been committed by anyone" "$err" "git does not track it"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
is   "…the log still under its own name" "$( [ -f "$LOGD/repoUnt-1.md" ] && echo yes )" "yes"
git -C "$WIP" add -- "lanes/log/repoUnt-1.md" >/dev/null 2>&1
git -C "$WIP" commit -q -m "commit the lane's own log, as the refusal asks"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

mkdir -p "$WIP/handoffs/repoUnt"
printf 'Lane: repoUnt-1 — single-use resume prompt\n\n## RESUME\n' > "$WIP/handoffs/repoUnt/session-handoff-2026-09-12-lane-repoUnt-1.md"
ren_before="$(git -C "$WIP" rev-parse HEAD)"
run env LANES_SESSION="$REN10_ID" "$E" rename-lane repoUnt-1 repoUnt-2 --no-github
is   "an UNTRACKED handoff is refused, not stamped into this commit" "$rc" 2
has  "…for the same reason" "$err" "git does not track it"
is   "…and nothing was written" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
hasnt "…the handoff took no stamp" "$(cat "$WIP/handoffs/repoUnt/session-handoff-2026-09-12-lane-repoUnt-1.md")" "RENAMED from"
git -C "$WIP" add -- handoffs >/dev/null 2>&1
git -C "$WIP" commit -q -m "commit the lane's own handoff, as the refusal asks"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

run env LANES_SESSION="$REN10_ID" "$E" rename-lane repoUnt-1 repoUnt-2 --no-github
is   "…and with both committed the rename goes through" "$rc" 0
is   "…the log at its new name" "$( [ -f "$LOGD/repoUnt-2.md" ] && echo yes )" "yes"
is   "…the handoff at its new name" \
     "$( [ -f "$WIP/handoffs/repoUnt/session-handoff-2026-09-12-lane-repoUnt-2.md" ] && echo yes )" "yes"


# ---- CLAUSE (g): ONE COMMENT PER OBJECT THE LANE HOLDS, AFTER THE COMMIT.
#
# The one act of this command that happens AFTER the push, and the one every
# case above switches off — so it is exercised here against the fake `gh` the
# head of this file puts first on `$PATH`, with `LANES_NO_GITHUB=0` for this
# case alone. Nothing reaches GitHub: the fake answers the two comment forms
# `gh_comment` makes and REFUSES every other call loudly.
REN11_ID="12ab34cd-16b1-4000-8000-12ab34cd16b1"
add_seed_row "| \`repoCmt-1\` | harness \`$REN11_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | handoffs/repoCmt/x.md | ACTIVE |"
{ printf '# lane repoCmt-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoCmt-1, session %s@Eagle, %s, lane:repoCmt-1 → home opensoft/repoCmt; estate repoCmt\n' "$REN11_ID" "$OLD_UTC"
  printf 'CLAIMED — lane repoCmt-1, session %s@Eagle, %s, opensoft/repoCmt#11\n' "$REN11_ID" "$OLD_UTC"
  printf 'OPENED — lane repoCmt-1, session %s@Eagle, %s, opensoft/repoCmt#12\n' "$REN11_ID" "$OLD_UTC"
  printf 'CLAIMED — lane repoCmt-1, session %s@Eagle, %s, opensoft/repoCmt#13\n' "$REN11_ID" "$OLD_UTC"
  printf 'RELEASED — lane repoCmt-1, session %s@Eagle, %s, opensoft/repoCmt#13\n' "$REN11_ID" "$OLD_UTC"
} > "$LOGD/repoCmt-1.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the comment lane: two objects open, one released"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

: > "$FAKE_GH_LOG"
run env LANES_NO_GITHUB=0 LANES_SESSION="$REN11_ID" "$E" rename-lane repoCmt-1 repoCmt-2
is   "a rename with GitHub ON exits 0" "$rc" 0
ren_sha="$(git -C "$WIP" rev-parse HEAD)"
is   "…posting ONE comment per object the lane HOLDS, and no more" \
     "$(command grep -c '^=== issue comment' "$FAKE_GH_LOG" || :)" 2
has  "…on the first of them" "$(cat "$FAKE_GH_LOG")" "=== issue comment opensoft/repoCmt 11"
has  "…and the second" "$(cat "$FAKE_GH_LOG")" "=== issue comment opensoft/repoCmt 12"
hasnt "…never on the one it released, which it does not hold" "$(cat "$FAKE_GH_LOG")" "opensoft/repoCmt 13"
has  "…the body in the amendment's own words" "$(cat "$FAKE_GH_LOG")" \
     "Lane repoCmt-1 renamed repoCmt-2 at 20"
has  "…with Rule 10's wire form, lower-case and canonical" "$(cat "$FAKE_GH_LOG")" \
     "Lane: repocmt-2 (repoCmt-2)"
has  "…citing the commit that carries the rename" "$(cat "$FAKE_GH_LOG")" "$ren_sha"
has  "…and naming the table that keeps the old name resolving" "$(cat "$FAKE_GH_LOG")" \
     "lanes/aliases.tsv\` resolves \`repoCmt-1\` to \`repoCmt-2\`"
has  "…reporting each comment's URL" "$err" "comment posted on opensoft/repoCmt#11"

# ---- AND A COMMENT THAT CANNOT BE POSTED LEAVES THE RENAME WHERE IT LANDED.
#
# The commit IS the rename (clause (g): the comment is posted AFTER it), so a
# `gh` that refuses must warn and never undo anything.
REN12_ID="12ab34cd-16b2-4000-8000-12ab34cd16b2"
add_seed_row "| \`repoCmt-5\` | harness \`$REN12_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | handoffs/repoCmt/y.md | ACTIVE |"
{ printf '# lane repoCmt-5 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoCmt-5, session %s@Eagle, %s, lane:repoCmt-5 → home opensoft/repoCmt; estate repoCmt\n' "$REN12_ID" "$OLD_UTC"
  printf 'CLAIMED — lane repoCmt-5, session %s@Eagle, %s, opensoft/repoCmt#21\n' "$REN12_ID" "$OLD_UTC"
} > "$LOGD/repoCmt-5.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the lane whose comment will fail"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
: > "$FAKE_GH_LOG"
run env LANES_NO_GITHUB=0 FAKE_GH_FAIL=1 LANES_SESSION="$REN12_ID" "$E" rename-lane repoCmt-5 repoCmt-6
is   "a rename whose comment cannot be posted still exits 0" "$rc" 0
has  "…warning, and naming the object it could not reach" "$err" "could not be posted on: opensoft/repoCmt#21"
has  "…saying the commit IS the rename and it has landed" "$err" "it has landed"
is   "…with the row moved all the same" "$(command grep -c '^| `repoCmt-6`' "$LANES")" 1
is   "…the log at its new name" "$( [ -f "$LOGD/repoCmt-6.md" ] && echo yes )" "yes"
is   "…and the commit still on origin" \
     "$(git -C "$WIP" rev-parse HEAD)" "$(git -C "$WIP" rev-parse origin/main)"
is   "…and nothing was posted" "$(command grep -c '^=== ' "$FAKE_GH_LOG" || :)" 0

# ---- AND THE FAKE REFUSES ANY OTHER GITHUB CALL, LOUDLY.
run env FAKE_GH_LOG="$SANDBOX/gh-probe.log" gh repo view opensoft/openRepoTools
is   "the fake gh refuses every call but the two comment forms" "$rc" 90
has  "…saying this suite reaches no GitHub surface" "$err" "reaches no GitHub surface"


# ============ Copilot round 8 on openRepoTools#81 ============================

# ---- THE READER'S FALLBACK REFUSES A PATH THAT IS NOT A TABLE, and the reason
# it is worth a round of its own is that the old behaviour failed OPEN.
#
# With no alias blob on `origin`, `-f` is false for a directory, a FIFO and a
# dangling link alike, so the branch was simply SKIPPED: `# no lane aliases` was
# cached and handed back with status 0, and a FORMER lane name then read as NEW.
# Each shape is put to both readers that matter — `canon-lane`, which is clause
# (e)'s one seat, and `lane-start`, which is what would append the second row.
# `repoRen-4` is the MIDDLE name of this section's chain and belongs to nobody,
# so the table is the only thing that can answer for it.
mkdir -p "$HOME/projects/repoRen"
ren_kind_tsv="$WIP/lanes/aliases-kind.tsv"
ren_kind() {   # <what is at the path>
  run env LANES_NO_FETCH=1 LANES_ALIASES_TSV="$ren_kind_tsv" \
      LANES_ALIASES_PATH=lanes/aliases-kind.tsv "$E" canon-lane repoRen-4
  is    "an alias table that is $1 refuses the read" "$rc" 66
  has   "…saying what is at the path instead" "$err" "not a regular file"
  hasnt "…and never 'unknown error', which is what a reason lost to a subshell said" \
        "$err" "unknown error"
  hasnt "…and answers no lane name at all" "$out" "repoRen"
  run env LANES_NO_FETCH=1 LANES_ALIASES_TSV="$ren_kind_tsv" \
      LANES_ALIASES_PATH=lanes/aliases-kind.tsv \
      "$START" --no-launch --dir "$HOME/projects/repoRen" repoRen-4
  is    "…and lane-start refuses over $1 rather than adding a row" "$rc" 2
  has   "…saying it would be a second row for a lane that is running" "$err" "second row"
}
mkdir -p "$ren_kind_tsv"
ren_kind "a DIRECTORY"
rmdir "$ren_kind_tsv"
ln -s "$WIP/lanes/no-table-is-here.tsv" "$ren_kind_tsv"
ren_kind "a DANGLING SYMLINK"
rm -f "$ren_kind_tsv"
if command -v mkfifo >/dev/null 2>&1; then
  mkfifo "$ren_kind_tsv"
  ren_kind "a FIFO"
  rm -f "$ren_kind_tsv"
else
  skip "an alias table that is a FIFO refuses the read" "no mkfifo on this host"
fi

# ---- AND A LIVE LINK TO A REAL TABLE IS STILL READ, because the reader's rule
# is narrower than the writer's on purpose: the writer refuses a symlink because
# it APPENDS in place and a redirect follows one, while a reader that follows
# the same link gets the table's own bytes and is right to.
printf 'farLane-1\tfarLane-2\t2026-09-15T00:00:00Z\n' > "$WIP/lanes/aliases-far.tsv"
ln -s "$WIP/lanes/aliases-far.tsv" "$ren_kind_tsv"
run env LANES_NO_FETCH=1 LANES_ALIASES_TSV="$ren_kind_tsv" \
    LANES_ALIASES_PATH=lanes/aliases-kind.tsv "$E" canon-lane farLane-1
is   "a symlink to a table that IS one is read, not refused" "$rc" 0
is   "…answering the name that table names" "$out" "farLane-2"
rm -f "$ren_kind_tsv" "$WIP/lanes/aliases-far.tsv"

# ---- THE UNDO'S PATHSPECS SURVIVE A SPACE IN A PATH.
#
# Flattened into one string and expanded unquoted, `handoffs/team notes/…` was
# TWO pathspecs that match nothing — and `git reset` is SILENT about a pathspec
# it cannot match, so the reset did not happen for that file and the rename
# stayed STAGED for the next writer to commit by accident: half a transaction,
# left behind by the mechanism that exists to leave none.
REN13_ID="12ab34cd-16b3-4000-8000-12ab34cd16b3"
REN13_H="handoffs/team notes/session-handoff-2026-09-12-lane-repoSpc-1.md"
REN13_H_NEW="handoffs/team notes/session-handoff-2026-09-12-lane-repoSpc-2.md"
mkdir -p "$WIP/handoffs/team notes"
printf 'Lane: repoSpc-1 — single-use resume prompt\n\n## RESUME\n' > "$WIP/$REN13_H"
add_seed_row "| \`repoSpc-1\` | harness \`$REN13_ID\` | Eagle / test / brett | 2026-09-12T00:00Z | none | $REN13_H | ACTIVE |"
{ printf '# lane repoSpc-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoSpc-1, session %s@Eagle, %s, lane:repoSpc-1 → home opensoft/repoSpc; estate repoSpc\n' "$REN13_ID" "$OLD_UTC"
} > "$LOGD/repoSpc-1.md"
git -C "$WIP" add -A -- lanes handoffs >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a lane whose handoff lives under a directory with a space"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
ren_reg_before="$(cat "$LANES")"
ren_log_before="$(cat "$LOGD/repoSpc-1.md")"
ren_alias_before="$(cat "$WIP/lanes/aliases.tsv" 2>/dev/null || :)"
ren_before="$(git -C "$WIP" rev-parse HEAD)"
mkdir -p "$WIP/.git/hooks"
printf '#!/bin/sh\nexit 1\n' > "$WIP/.git/hooks/pre-commit"
chmod 755 "$WIP/.git/hooks/pre-commit"
run env LANES_SESSION="$REN13_ID" "$E" rename-lane repoSpc-1 repoSpc-2 --no-github
rm -f "$WIP/.git/hooks/pre-commit"
is   "a rename rolled back over a path with a SPACE commits nothing" "$rc" 6
is   "…the register back" "$(cat "$LANES")" "$ren_reg_before"
is   "…the object log back under its own name" "$(cat "$LOGD/repoSpc-1.md" 2>/dev/null)" "$ren_log_before"
is   "…the alias table back" "$(cat "$WIP/lanes/aliases.tsv" 2>/dev/null || :)" "$ren_alias_before"
is   "…the handoff back under its own name, space and all" \
     "$( [ -f "$WIP/$REN13_H" ] && [ ! -e "$WIP/$REN13_H_NEW" ] && echo yes )" "yes"
is   "…HEAD unmoved" "$(git -C "$WIP" rev-parse HEAD)" "$ren_before"
is   "…and NOTHING left staged, which is what a split pathspec leaves behind" \
     "$(git -C "$WIP" diff --cached --name-only | command grep -c . || :)" 0

# ---- AND THE SAME RENAME THEN GOES THROUGH, spaces and all.
run env LANES_SESSION="$REN13_ID" "$E" rename-lane repoSpc-1 repoSpc-2 --no-github
is   "the same rename then goes through" "$rc" 0
is   "…moving the handoff under the spaced directory" \
     "$( [ -f "$WIP/$REN13_H_NEW" ] && [ ! -e "$WIP/$REN13_H" ] && echo yes )" "yes"
is   "…and the row names it there" "$(command grep -c "$REN13_H_NEW" "$LANES")" 1
has  "…in ONE commit that carries the spaced path" \
     "$(git -C "$WIP" show --name-only --format= HEAD)" "$REN13_H_NEW"


export FAKE_TMUX_WINDOWS="$A16_SAVE_WINDOWS"
export FAKE_TMUX_WINDOW="$A16_SAVE_WINDOW"
export FAKE_TMUX_WINDOW_NAME="$A16_SAVE_NAME"

echo "== Amendment 17: the handoff is the swap =="

# THE ACT UNDER ITS THREE NAMES, AND THE TWO SUB-FIELDS THAT MAKE A LANE
# RESUMABLE BY ANY AGENT. lane-collision-protocol Amendment 17, ratified
# 2026-09-14T09:45:33Z (clause (f), `/ctx`, included); Amendment 18(d)'s
# `--exit` and Addendum 2's respawn line; adoption acts 6 (the transcript
# follows the lane) and 7 (`--late`).
#
# EVERYTHING THIS SECTION ADDS IS ITS OWN — its own bin copy of `lane-handoff`,
# its own fakes in their own directory, its own lanes, its own profiles — so
# that it can be read, moved or merged in one piece. The shared fakes at the
# head of this file are not edited; `$SANDBOX/a17bin/tmux` DELEGATES to the
# shared one for every read, and adds the two writes tmux makes here.

HANDOFF_CMD="$OPENREPOTOOLS_BIN_DIR/lane-handoff"
# `cp -p` AND NO `chmod` AFTER IT, deliberately: the mode this case reads back
# is the one the REPOSITORY carries, so a `lane-handoff` that is not 100755 in
# the index is a failure here rather than a file the fixture quietly made
# runnable. The first Amendment 17(a) commit landed it 100644 and a `chmod 755`
# on this line saw nothing; `e25b54c` made it 100755 and this fixture is what
# holds it there. (`git ls-files -s lane-handoff` is the answer to any claim
# that it is not.)
cp -p "$SRC_DIR/lane-handoff" "$OPENREPOTOOLS_BIN_DIR/" 2>/dev/null
is   "lane-handoff is installed beside the helper it reads through, executable as the repository ships it" \
     "$( [ -x "$HANDOFF_CMD" ] && echo yes || echo no )" yes

mkdir -p "$SANDBOX/a17bin"
# A FAKE `codex`, LOGGING ITS ARGV — the whole of what a launcher table can be
# tested against. It also records, at the instant it is launched, how many
# `RESUMED by codex` stamps the handoff carries: that is how "the stamp is
# written BEFORE the launch" is proved rather than assumed.
cat > "$SANDBOX/a17bin/codex" <<'FAKE'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "${FAKE_CODEX_LOG:-/dev/null}"
if [ -n "${FAKE_CODEX_WATCH:-}" ]; then
  printf 'stamps-at-launch=%s\n' \
    "$(grep -c 'RESUMED by codex' "$FAKE_CODEX_WATCH" 2>/dev/null || printf 0)" \
    >> "${FAKE_CODEX_LOG:-/dev/null}"
fi
exit 0
FAKE
# THE TWO WRITES TMUX MAKES IN THIS SECTION, and the same trick: each records
# how many PAUSED lines the lane's log carried at the instant it ran. Amendment
# 17(f) is an ORDER — *"a pane is never respawned over an unrecorded lane"* —
# and an order is proved by what the second act could see of the first.
cat > "$SANDBOX/a17bin/tmux" <<'FAKE'
#!/usr/bin/env bash
case "${1-}" in
  send-keys|respawn-pane)
    printf '%s' "$*" >> "${FAKE_TMUX_A17_LOG:-/dev/null}"
    printf ' | paused-lines=%s\n' \
      "$(grep -c '^PAUSED' "${FAKE_TMUX_A17_WATCH:-/dev/null}" 2>/dev/null || printf 0)" \
      >> "${FAKE_TMUX_A17_LOG:-/dev/null}"
    exit 0 ;;
esac
exec "${FAKE_TMUX_REAL:?}" "$@"
FAKE
cat > "$SANDBOX/a17bin/pclaude" <<'FAKE'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "${FAKE_PCLAUDE_LOG:-/dev/null}"
FAKE
chmod +x "$SANDBOX/a17bin/codex" "$SANDBOX/a17bin/tmux" "$SANDBOX/a17bin/pclaude"
export FAKE_TMUX_REAL="$SANDBOX/fakebin/tmux"
export FAKE_CODEX_LOG="$SANDBOX/codex.log" FAKE_TMUX_A17_LOG="$SANDBOX/tmux-a17.log"
export FAKE_PCLAUDE_LOG="$SANDBOX/pclaude.log"
: > "$FAKE_CODEX_LOG"; : > "$FAKE_TMUX_A17_LOG"; : > "$FAKE_PCLAUDE_LOG"
A17PATH="$SANDBOX/a17bin:$PATH"

# ------------------------------------------------------------- the fixtures

HF_ID="a17a0001-1111-4000-8000-a17a00011111"
HF2_ID="a17a0002-2222-4000-8000-a17a00022222"
HF3_ID="a17a0003-3333-4000-8000-a17a00033333"
HF4_ID="a17a0004-4444-4000-8000-a17a00044444"
CODEX_ID="01JCODEXSESSION0000000001"

mkdir -p "$HOME/projects/repoHF"
git init -q -b main "$HOME/projects/repoHF"
git -C "$HOME/projects/repoHF" remote add origin "https://github.com/opensoft/repoHF.git"
HF_DIR="$HOME/projects/repoHF"

# ONE RUNNING WRITER, on disk, exactly as a lane keeps them: a worktree under
# the lane's own checkout with work in it that is neither committed nor pushed.
mkdir -p "$HF_DIR/.claude/worktrees/w1"
git init -q -b feat/w1 "$HF_DIR/.claude/worktrees/w1"
git -C "$HF_DIR/.claude/worktrees/w1" config user.email "test@example.invalid"
git -C "$HF_DIR/.claude/worktrees/w1" config user.name "lane helper tests"
printf 'first\n' > "$HF_DIR/.claude/worktrees/w1/a.txt"
git -C "$HF_DIR/.claude/worktrees/w1" add -A >/dev/null 2>&1
git -C "$HF_DIR/.claude/worktrees/w1" commit -q -m "the writer's last commit"
printf 'uncommitted\n' > "$HF_DIR/.claude/worktrees/w1/b.txt"

mkdir -p "$WIP/handoffs/repoHF"
hf_seed_handoff() {   # <file> <lane>
  { printf 'Lane: %s (team-05a, session %s) — single-use resume prompt: stamp RESUMED-by before acting (lane-collision-protocol rule 3)\n' "$2" "$HF_ID"
    printf '\n'
    printf 'Written before Amendment 17, by hand.\n'
  } > "$1"
}
for hf_l in repoHF-1 repoHF-2 repoHF-3 repoHF-4 repoHF-5 repoHF-6 repoHF-7 repoHF-8 repoHF-9 repoHF-10; do
  hf_seed_handoff "$WIP/handoffs/repoHF/$hf_l.md" "$hf_l"
done
git -C "$WIP" add -- handoffs/repoHF >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the Amendment 17 handoffs"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

hf_row() {   # <lane> <session cell>
  "$E" add-row "| \`$1\` | $2 | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoHF/$1.md | ACTIVE |" >/dev/null 2>&1
}
hf_row repoHF-1 "harness \`$HF_ID\`"
hf_row repoHF-2 "\`session_01A17NOUUIDATALL000000\` (profile team-05a)"
hf_row repoHF-3 "harness \`$HF2_ID\`"
hf_row repoHF-4 "harness \`$HF3_ID\`"
hf_row repoHF-5 "harness \`$HF_ID\`"
hf_row repoHF-6 "harness \`$HF_ID\`"
hf_row repoHF-7 "harness \`$HF4_ID\`"
# The two lanes Amendment 18 Addendum 2 (i-8) is asked on: one respawned where
# `lane` IS on PATH, one where the `lane` on PATH is somebody else's word.
hf_row repoHF-8 "harness \`$HF_ID\`"
hf_row repoHF-9 "harness \`$HF_ID\`"
# The lane the IN-PROCESS clear is recorded on: its writers live through it.
hf_row repoHF-10 "harness \`$HF_ID\`"

# The lane's own log, with the STARTED a running lane has.
hf_seed_log() {   # <lane> <utc> [<extra line>…]
  hf_l="$1"; hf_u="$2"; shift 2
  { printf '# lane %s — object log (lane-collision-protocol Amendment 7)\n' "$hf_l"
    printf 'STARTED — lane %s, session %s@Eagle, %s, lane:%s → home opensoft/repoHF; estate repoHF; dir %s\n' \
      "$hf_l" "$HF_ID" "$hf_u" "$hf_l" "$HF_DIR"
    for hf_x in "$@"; do printf '%s\n' "$hf_x"; done
  } > "$LOGD/$hf_l.md"
  git -C "$WIP" add -- "lanes/log/$hf_l.md"
  git -C "$WIP" commit -q -m "LOG($hf_l@Eagle): seed"
  git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
  git -C "$WIP" push -q origin main
  return 0
}
for hf_l in repoHF-1 repoHF-2 repoHF-3 repoHF-5 repoHF-6 repoHF-7 repoHF-8 repoHF-9 repoHF-10; do
  hf_seed_log "$hf_l" "2026-09-14T09:00:00Z"
done

# The live record of the window this lane is in, so the pane `--exit` and
# `--restart` type into is the one the harness itself recorded.
write_record_ns "$sessions_dir/live-a17.json" "$HF_ID" "$LIVE_PID" "$live_start" "hfsess:@21.%21" "repoHF-1" "user" "busy"

# ------------------------------------- 1. the record, and its two sub-fields

export FAKE_TMUX_A17_WATCH="$LOGD/repoHF-1.md"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="hfsess:@21" CLAUDE_CODE_SESSION_ID="$HF_ID" \
    CLAUDE_PROFILE_NAME=team-05a "$HANDOFF_CMD" --lane repoHF-1 clear
is    "lane-handoff exits 0" "$rc" 0
# ITS OWN STDOUT, KEPT: `$out` is whatever the LAST `run` left, and there is a
# `swapped` read between this run and the assertions at the foot of this block.
hf1_out="$out"
hf1_log="$(cat "$LOGD/repoHF-1.md")"
has   "…writing the lane's PAUSED line" "$hf1_log" "PAUSED — lane repoHF-1, session $HF_ID@Eagle"
has   "…whose payload opens 'swap;', which is what \`swapped\` matches on" "$hf1_log" "lane:repoHF-1 → swap;"
has   "…carrying Amendment 11(c)'s window" "$hf1_log" "window hfsess:0 @21"
has   "…its dir" "$hf1_log" "dir $HF_DIR"
has   "…its profile" "$hf1_log" "profile team-05a"
has   "…and Amendment 17(b)'s two: the agent" "$hf1_log" "agent claude"
has   "…and the transcript" "$hf1_log" "transcript $HF_ID"
has   "…with the why as the line's free text" "$hf1_log" " — clear"
has   "the restart line is printed, and it is one command" "$hf1_out" "READY — restart with: pclaude team-05a"
has   "…naming the agent the next start will use" "$hf1_out" "lane-start --agent claude resumes it"

run   "$E" swapped Eagle
has   "swapped lists the lane" "$out" "repoHF-1"
is    "…with the agent as its sixth field and the transcript as its seventh" \
      "$(printf '%s\n' "$out" | awk -F'\t' '$1 == "repoHF-1" { print $6 "/" $7 }')" "claude/$HF_ID"
is    "…and a record written before Amendment 17 carries both EMPTY, never a guess" \
      "$(printf '%s\n' "$out" | awk -F'\t' '$1 == "repoSW-1" { print $6 "/" $7 }')" "/"
run   "$E" lane-agent repoHF-1
is    "lane-agent reads the record's agent" "$out" "claude"
run   "$E" lane-transcript repoHF-1
is    "lane-transcript reads its transcript" "$out" "$HF_ID"
run   "$E" lane-agent repoSW-1
is    "…and an older record with neither is 8, the estate's 'no record' (Amendment 7(i))" "$rc" 8

# THE HANDOFF FILE — a fresh Rule 3 top block, the WRITERS section filled from
# the disk, and everything that was there kept below as history.
hf1_file="$(cat "$WIP/handoffs/repoHF/repoHF-1.md")"
is    "the handoff's line 1 is still the Rule 3 header lane-start splices under" \
      "$(head -n1 "$WIP/handoffs/repoHF/repoHF-1.md" | cut -c1-20)" "Lane: repoHF-1 (team"
is    "…with the blank line after it that puts the stamps at line 3" \
      "$(sed -n 2p "$WIP/handoffs/repoHF/repoHF-1.md")" ""
has   "…a fresh RESUME PROMPT block naming the agent and the transcript" "$hf1_file" "agent claude, transcript $HF_ID"
has   "…whose headline is what to EXPECT and never what to do (Addendum 1 (j))" "$hf1_file" "the count decides: this handoff cannot know"
has   "…a WRITERS section" "$hf1_file" "**WRITERS at"
has   "…naming the running writer's worktree" "$hf1_file" "$HF_DIR/.claude/worktrees/w1"
has   "…its branch" "$hf1_file" "branch \`feat/w1\`"
has   "…what it had committed" "$hf1_file" "the writer's last commit"
has   "…and what it is holding" "$hf1_file" "1 dirty"
has   "…the section for the brief where the caller passed none" "$hf1_file" "brief: (fill in"
# THE WRITERS OF AN IN-PROCESS CLEAR SURVIVE IT, AND THE BLOCK IS WHAT TELLS THE
# NEXT SESSION WHICH CASE IT IS IN (measured in this lane on 2026-09-14: a
# harness `/clear` mints a new transcript id in the SAME process, so every
# subagent lives through it and only its in-flight tool calls die). `ListAgents`
# comes first in BOTH kinds, because relaunching a writer that is still listed
# is two writers on one worktree.
has   "the top block's act (3) COUNTS the live writers first (Addendum 1 (i))" "$hf1_file" "COUNT THE LIVE WRITERS"
has   "…with clause (k) beside it, which is why the count comes first" "$hf1_file" "ONE WORKTREE, ONE WRITER"
has   "…and the reads that say where a writer that is NOT live stood" "$hf1_file" "git log @{u}.."
has   "…the WRITERS section opening with clause (i)'s own words" "$hf1_file" "FIRST count the live writers"
has   "…a live writer OWNING its worktree, messaged rather than relaunched" "$hf1_file" "A writer still live OWNS its worktree"
has   "…and the count beating the list where the two disagree" "$hf1_file" "THE COUNT WINS"
has   "…while a PLAIN handoff cannot know which kind followed it (Addendum 1 (h))" "$hf1_file" "kind unknown"
has   "the record carries the kind too, after the agent and the transcript" "$hf1_log" "; kind unknown"
has   "…and the free text names it after the why, in the addendum's own spelling" "$hf1_log" " — clear kind unknown"
has   "…and the file it was, below, as history" "$hf1_file" "Written before Amendment 17, by hand."
has   "the writers are polled on stdout too, with git's own words" "$hf1_out" "git status --short"
has   "…and the unpushed read beside it" "$hf1_out" "git log @{u}.."
is    "the handoff refresh is its own commit in the workspace repository" \
      "$(git -C "$WIP" log --format=%s -n1 -- handoffs/repoHF/repoHF-1.md)" "handoff(repoHF-1@Eagle): PAUSED, clear"
has   "…with the Rule 5 trailer" "$(git -C "$WIP" log --format=%b -n1 -- handoffs/repoHF/repoHF-1.md)" "Lane: repoHF-1"
has   "the row is flipped to PAUSED" "$(grep '^| `repoHF-1`' "$LANES")" "| PAUSED "

# The brief a caller DOES pass reaches the section.
printf '%s\t%s\n' "$HF_DIR/.claude/worktrees/w1" "take round 4 of #41" > "$SANDBOX/a17-writers.tsv"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="hfsess:@21" CLAUDE_CODE_SESSION_ID="$HF_ID" \
    CLAUDE_PROFILE_NAME=team-05a "$HANDOFF_CMD" --lane repoHF-3 --writers-file "$SANDBOX/a17-writers.tsv" --dir "$HF_DIR" clear
is    "a second handoff exits 0" "$rc" 0
has   "…and the WRITERS section carries the brief the caller passed" \
      "$(cat "$WIP/handoffs/repoHF/repoHF-3.md")" "brief: take round 4 of #41"

# THE SUB-FIELDS ARE VALIDATED BY THE WRITER, because this log is append-only.
run env LANES_LANE=repoHF-7 LANES_SESSION="$HF4_ID" "$E" log PAUSED lane:repoHF-7 '→' "swap; agent not a key" "x"
is    "an \`agent\` that is not a manifest key is refused by the writer" "$rc" 2
has   "…naming the rule rather than the caller" "$err" "manifest key"
hasnt "…and nothing was written" "$(cat "$LOGD/repoHF-7.md")" "not a key"
run env LANES_LANE=repoHF-7 LANES_SESSION="$HF4_ID" "$E" log PAUSED lane:repoHF-7 '→' "swap; transcript two words" "x"
is    "…and so is a \`transcript\` that is neither an id nor 'none'" "$rc" 2
run env PATH="$A17PATH" CLAUDE_CODE_SESSION_ID="$HF4_ID" "$HANDOFF_CMD" --lane repoHF-7 --agent 'not a key' x
is    "lane-handoff refuses the same value at the flag" "$rc" 2
has   "…naming the flag the caller used" "$err" "--agent takes a manifest key"

# THE TWO SUB-FIELDS ARE WRITTEN TOGETHER OR NOT AT ALL, AND AN EMPTY ONE IS NOT
# AN ABSENT ONE (Copilot rounds 1 and 2 on openRepoTools#47). A half record is
# read by `lane-start` as one field plus a DEFAULT for the other: Claude over a
# codex id, or codex over none. And a sub-field written blank parses exactly
# like one that was never there, so a malformed line would be indexed as a
# pre-amendment one for ever, in a log nothing rewrites.
run env LANES_LANE=repoHF-7 LANES_SESSION="$HF4_ID" "$E" log PAUSED lane:repoHF-7 '→' "swap; agent codex" "x"
is    "an \`agent\` with no \`transcript\` beside it is refused by the writer" "$rc" 2
has   "…naming the pair rather than the caller" "$err" "written TOGETHER or not at all"
run env LANES_LANE=repoHF-7 LANES_SESSION="$HF4_ID" "$E" log PAUSED lane:repoHF-7 '→' "swap; transcript none" "x"
is    "…and a \`transcript\` with no \`agent\` is refused the same way" "$rc" 2
run env LANES_LANE=repoHF-7 LANES_SESSION="$HF4_ID" "$E" log PAUSED lane:repoHF-7 '→' "swap; agent ; transcript none" "x"
is    "…and a sub-field that is THERE and EMPTY is neither valid nor 'absent'" "$rc" 2
has   "…saying no reader can tell it from a pre-amendment record" "$err" "THERE and EMPTY"
is    "…and nothing was written by any of the three" "$(grep -c '^PAUSED' "$LOGD/repoHF-7.md")" 0
# (the PAIR TOGETHER is what every `lane-handoff` above writes, and repoHF-1's
# record is the case that reads it back — this lane's log is left EMPTY of
# `PAUSED` lines on purpose: section 3 below is the `--late` rule, and its whole
# question is what a lane with no paused record does.)

# `--utc` IS THE LATE `PAUSED`'s SEAM AND HAS NO OTHER CALLER (Amendment 17,
# adoption act 7). This log is append-only and FILE ORDER is what every state
# read means by "last", so a STARTED or a RESUMED dated by hand changes what
# every reader reports about a lane that is running.
run env LANES_LANE=repoHF-7 LANES_SESSION="$HF4_ID" "$E" log RESUMED lane:repoHF-7 --utc "2026-09-13T01:02:03Z"
is    "--utc on a verb that is not PAUSED is refused" "$rc" 2
has   "…naming the one line that carries its own date" "$err" "dates the LATE PAUSED"
is    "…and nothing was written" "$(grep -c '^RESUMED' "$LOGD/repoHF-7.md")" 0

# ------------------------------------------ 2. /ctx — the record, then the pane

# WHICH `lane` THE COMMAND CAN SEE IS THE QUESTION IN THREE OF THE CASES BELOW
# (Amendment 18 Addendum 2 (i-8)), so each of them runs on a PATH THIS FILE
# BUILT rather than on whatever the workstation happens to carry:
# `openRepoTools#43` places `lane` in `~/.local/bin`, and a case that asked
# "what happens where there is no `lane`" against a workstation that has one
# would go green on the answer to a different question.
a17_path_without() {   # <word> — this section's PATH with every directory that holds <word> taken out
  a17p_want="$1"
  printf '%s' "$A17PATH" | tr ':' '\n' | while IFS= read -r a17p_d; do
    [ -n "$a17p_d" ] || continue
    if [ -x "$a17p_d/$a17p_want" ]; then continue; fi
    printf '%s:' "$a17p_d"
  done | sed 's/:$//'
}
a17_path_without_lane() { a17_path_without lane; }
A17PATH_NOLANE="$(a17_path_without_lane)"

: > "$FAKE_TMUX_A17_LOG"
export FAKE_TMUX_A17_WATCH="$LOGD/repoHF-5.md"
run env PATH="$A17PATH_NOLANE" FAKE_TMUX_WINDOW="hfsess:@21" CLAUDE_CODE_SESSION_ID="$HF_ID" \
    CLAUDE_PROFILE_NAME=team-05a "$HANDOFF_CMD" --lane repoHF-5 --restart clear
is    "lane-handoff --restart exits 0" "$rc" 0
a17_tmux="$(cat "$FAKE_TMUX_A17_LOG")"
has   "…respawning the lane's own pane" "$a17_tmux" "respawn-pane -k -t hfsess:@21.%21"
# WITH NO `lane` ON PATH — which is this sandbox, and every workstation until
# `openRepoTools#43` places that word — the line is the launcher's, which is
# the door Amendment 18 Addendum 2 (i-8) leaves open in the same sentence that
# names `lane <name>`: *"or through the launcher directly"*. The case below
# asks for the word itself, where it is there to be seen.
has   "…with no \`lane\` on PATH, through the launcher, with --lane BEFORE the profile" "$a17_tmux" "pclaude --lane repoHF-5 team-05a"
has   "…and the seam that makes the new session a FRESH one primed by the top block" "$a17_tmux" "LANE_START_FRESH=1"
hasnt "…never \`restart <lane>\`, which Addendum 2 takes off the person's PATH" "$a17_tmux" "restart repoHF-5"
is    "THE RECORD WAS WRITTEN BEFORE THE RESPAWN, which is what the fake could see" \
      "$(printf '%s\n' "$a17_tmux" | grep -o 'paused-lines=[0-9]*' | head -n1)" "paused-lines=1"
has   "…and the record is the lane's own PAUSED" "$(cat "$LOGD/repoHF-5.md")" "lane:repoHF-5 → swap;"

# AMENDMENT 18 ADDENDUM 2 (i-8) AND ITS ADOPTION LINE — *"opensoft/
# openRepoTools#36 (`/ctx`) respawns with `lane <name>`"*. Where the word is on
# PATH it is the word that is typed, with NO profile argument: `lane <name>`
# reads the record this act has just written for the lane's directory and
# profile, and asks nothing.
#
# THE FAKE CARRIES THE STRING EVERY BASH FILE THIS TOOLSET SHIPS CARRIES,
# because that is what `lane-handoff` reads it for: `lane` is an ordinary
# English word, and a pane respawned over somebody else's `lane` is a pane the
# person cannot get back.
mkdir -p "$SANDBOX/a17lane"
cat > "$SANDBOX/a17lane/lane" <<'FAKE'
#!/usr/bin/env bash
# lane — the word, as lane-collision-protocol Amendment 18 Addendum 1 names it
printf '%s\n' "$*" >> "${FAKE_LANE_LOG:-/dev/null}"
FAKE
# AND IT IS LARGER THAN THE BOUNDED READ (Copilot round 3 on openRepoTools#47).
# The word is recognised by `head -c 8192 < file | grep …`, and under
# `set -o pipefail` a `grep -q` that exits on the match leaves `head` writing
# into a closed pipe: SIGPIPE, 141, and the estate's OWN `lane` classified as
# somebody else's. The marker is in the first line; the padding below is what
# makes `head` still have something to write when `grep` has seen it.
{ printf '# padding, so this file is larger than the bounded read:\n'
  i=0
  while [ "$i" -lt 400 ]; do
    printf '# %s\n' "................................................................"
    i=$((i + 1))
  done
} >> "$SANDBOX/a17lane/lane"
chmod +x "$SANDBOX/a17lane/lane"
: > "$FAKE_TMUX_A17_LOG"
export FAKE_TMUX_A17_WATCH="$LOGD/repoHF-8.md"
run env PATH="$SANDBOX/a17lane:$A17PATH_NOLANE" FAKE_TMUX_WINDOW="hfsess:@21" CLAUDE_CODE_SESSION_ID="$HF_ID" \
    CLAUDE_PROFILE_NAME=team-05a "$HANDOFF_CMD" --lane repoHF-8 --restart clear
is    "with \`lane\` on PATH, lane-handoff --restart exits 0" "$rc" 0
a17_lane_tmux="$(cat "$FAKE_TMUX_A17_LOG")"
has   "…and the respawn line is \`lane <lane>\` — that word, resolved where it was found" \
      "$a17_lane_tmux" "a17lane/lane repoHF-8"
has   "…still with the FRESH seam, which rides in the environment and survives the hand-on to lane-start" \
      "$a17_lane_tmux" "LANE_START_FRESH=1"
hasnt "…and with no profile argument: \`lane <name>\` reads the record for it" "$a17_lane_tmux" "repoHF-8 team-05a"
hasnt "…never the launcher, where the word itself is there to be typed" "$a17_lane_tmux" "pclaude --lane repoHF-8"
hasnt "…and never \`restart <lane>\`" "$a17_lane_tmux" "restart repoHF-8"
is    "…the record still written BEFORE the respawn" \
      "$(printf '%s\n' "$a17_lane_tmux" | grep -o 'paused-lines=[0-9]*' | head -n1)" "paused-lines=1"

# A `lane` ON PATH THAT IS NOT THIS ESTATE'S WORD IS PASSED OVER FOR THE
# LAUNCHER, and said. The safe side of the two is the one that still starts the
# lane: a respawn is the one act no later refusal can undo.
mkdir -p "$SANDBOX/a17foreign"
cat > "$SANDBOX/a17foreign/lane" <<'FAKE'
#!/usr/bin/env bash
# somebody else's `lane`: a swimming-lane plotter, say. It names no protocol.
exit 0
FAKE
chmod +x "$SANDBOX/a17foreign/lane"
: > "$FAKE_TMUX_A17_LOG"
export FAKE_TMUX_A17_WATCH="$LOGD/repoHF-9.md"
run env PATH="$SANDBOX/a17foreign:$A17PATH_NOLANE" FAKE_TMUX_WINDOW="hfsess:@21" CLAUDE_CODE_SESSION_ID="$HF_ID" \
    CLAUDE_PROFILE_NAME=team-05a "$HANDOFF_CMD" --lane repoHF-9 --restart clear
is    "a \`lane\` that is not this estate's word still exits 0" "$rc" 0
a17_foreign_tmux="$(cat "$FAKE_TMUX_A17_LOG")"
has   "…respawning through the launcher instead" "$a17_foreign_tmux" "pclaude --lane repoHF-9 team-05a"
hasnt "…and never through the word it could not recognise" "$a17_foreign_tmux" "a17foreign/lane repoHF-9"
has   "…saying which \`lane\` it passed over" "$err" "is not this estate's word"

# A RECORD THAT CANNOT BE WRITTEN REFUSES BEFORE ANYTHING IS KILLED. repoHF-2's
# row carries only `session_…` footer ids, so no transcript uuid is knowable and
# `write_event` refuses the line (Amendment 11 clause (e)).
: > "$FAKE_TMUX_A17_LOG"
export FAKE_TMUX_A17_WATCH="$LOGD/repoHF-2.md"
# THE WINDOW IS ONE NO LIVE RECORD NAMES, and that is the point: repoHF-2's row
# carries only `session_…` footer ids, so with no session in the window either
# there is no transcript uuid anywhere and `write_event` refuses the line
# (Amendment 11 clause (e)). Asked from the window `live-a17.json` names, the
# window read would hand it a uuid and there would be no unwritable record to
# test with.
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="hfsess:@22" CLAUDE_PROFILE_NAME=team-05a \
    "$HANDOFF_CMD" --lane repoHF-2 --restart clear
is    "a /ctx whose record could not be written REFUSES" "$rc" 2
has   "…saying the pane is exactly as it was" "$err" "this pane is left exactly as it is"
is    "…and the pane was never respawned" "$(grep -c 'respawn-pane' "$FAKE_TMUX_A17_LOG")" 0
hasnt "…nor is there a PAUSED line for that lane" "$(cat "$LOGD/repoHF-2.md")" "PAUSED"

# THE RECORD IS THREE WRITES, AND A PANE IS NEVER RESPAWNED OVER A PARTIAL ONE
# (Copilot rounds 1 and 2 on openRepoTools#47). The object-log line is the
# first; the ROW is what every other lane and every launcher reads this lane's
# state from, and the HANDOFF's top block is literally the new session's first
# prompt. Each of the two below writes the PAUSED line and then fails at one of
# the others, and neither may kill the only process that could put it right.
hf_seed_handoff "$WIP/handoffs/repoHF/repoHF-11.md" repoHF-11
git -C "$WIP" add -- handoffs/repoHF/repoHF-11.md >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed repoHF-11's handoff"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
# A ROW WHOSE CELLS ARE NOT UNAMBIGUOUS, which since Amendment 13(a) is what a
# refused row write looks like. It used to be a state cell no anchor matched —
# `replace-in-row` was given a state word derived from the row itself and a
# lower-case `running` derived nothing — and that refusal is gone with the act:
# `set-row-state` REPLACES the cell whatever it says. What it will not do is
# write over a row carrying a seventh ` | `, because which text is the state
# cell is then not knowable from the row. SEEDED and not added, because the
# writer refuses to create this state (the line it would need carries a `|`).
add_seed_row "| \`repoHF-11\` | harness \`$HF_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoHF/repoHF-11.md | running · a | b |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a row whose state cell holds a literal ' | ', which no row write can take"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
: > "$FAKE_TMUX_A17_LOG"
export FAKE_TMUX_A17_WATCH="$LOGD/repoHF-11.md"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="hfsess:@21" CLAUDE_CODE_SESSION_ID="$HF_ID" \
    CLAUDE_PROFILE_NAME=team-05a "$HANDOFF_CMD" --lane repoHF-11 --restart clear
is    "a /ctx whose ROW could not be flipped REFUSES" "$rc" 2
has   "…saying the register would read RUNNING for a session that was just replaced" "$err" "the ROW WAS NOT FLIPPED"
has   "…and that the pane is exactly as it was" "$err" "this pane is left exactly as it is"
is    "…and the pane was never respawned" "$(grep -c 'respawn-pane' "$FAKE_TMUX_A17_LOG")" 0
has   "…while the record itself IS written, because a swap is never left unwritten" \
      "$(cat "$LOGD/repoHF-11.md")" "lane:repoHF-11 → swap;"

# A HANDOFF THE ROW NAMES AND NOTHING CAN FIND: the top block cannot be
# refreshed, so a respawn would hand the new session the block of the handoff
# this act has replaced — the writers of another act, the why of another act.
"$E" add-row "| \`repoHF-12\` | harness \`$HF_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoHF/repoHF-12-nowhere.md | ACTIVE |" >/dev/null 2>&1
: > "$FAKE_TMUX_A17_LOG"
export FAKE_TMUX_A17_WATCH="$LOGD/repoHF-12.md"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="hfsess:@21" CLAUDE_CODE_SESSION_ID="$HF_ID" \
    CLAUDE_PROFILE_NAME=team-05a "$HANDOFF_CMD" --lane repoHF-12 --restart clear
is    "a /ctx whose HANDOFF could not be refreshed REFUSES" "$rc" 2
has   "…saying the top block is what the new session is started with" "$err" "the HANDOFF WAS NOT REFRESHED"
is    "…and the pane was never respawned" "$(grep -c 'respawn-pane' "$FAKE_TMUX_A17_LOG")" 0
has   "…with the block printed, so the act it could not make is still recoverable" "$err" "## RESUME PROMPT — PAUSED"

# --exit types /exit into the lane's own pane (Amendment 18(d)).
: > "$FAKE_TMUX_A17_LOG"
export FAKE_TMUX_A17_WATCH="$LOGD/repoHF-6.md"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="hfsess:@21" CLAUDE_CODE_SESSION_ID="$HF_ID" \
    CLAUDE_PROFILE_NAME=team-05a "$HANDOFF_CMD" --lane repoHF-6 --exit "requested by $HF2_ID@Eagle/py-bench"
is    "lane-handoff --exit exits 0" "$rc" 0
has   "…typing /exit into the lane's own pane" "$(cat "$FAKE_TMUX_A17_LOG")" "send-keys -t hfsess:@21.%21 /exit Enter"
is    "…after the record, which is the same order /ctx takes" \
      "$(grep -o 'paused-lines=[0-9]*' "$FAKE_TMUX_A17_LOG" | head -n1)" "paused-lines=1"
has   "…and the why the requester gave is the record's free text" \
      "$(cat "$LOGD/repoHF-6.md")" "requested by $HF2_ID@Eagle/py-bench"
is    "…and the pane is not respawned as well: one act at a time" \
      "$(grep -c 'respawn-pane' "$FAKE_TMUX_A17_LOG")" 0
run env PATH="$A17PATH" "$HANDOFF_CMD" --lane repoHF-4 --restart --exit x
is    "--restart and --exit together are refused" "$rc" 2
has   "…naming the two ends they are" "$err" "two different ends for one act"

# ------------------------- 2b. --in-process: the writers live through a clear
#
# MEASURED IN THIS LANE ON 2026-09-14, and it is why the kind is recorded at
# all: a harness `/clear` mints a NEW TRANSCRIPT ID IN THE SAME PROCESS, so
# every subagent the lane has running SURVIVES it — only the tool calls they had
# in flight die. A top block that then said *relaunch every writer below* would
# put a SECOND writer on a worktree the first one still holds. The `--restart`
# above is the other kind and its block is right to say relaunch: that one
# replaces the process.
: > "$FAKE_TMUX_A17_LOG"
export FAKE_TMUX_A17_WATCH="$LOGD/repoHF-10.md"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="hfsess:@21" CLAUDE_CODE_SESSION_ID="$HF_ID" \
    CLAUDE_PROFILE_NAME=team-05a "$HANDOFF_CMD" --lane repoHF-10 --in-process clear
is    "lane-handoff --in-process exits 0" "$rc" 0
hf10_log="$(cat "$LOGD/repoHF-10.md")"
hf10_file="$(cat "$WIP/handoffs/repoHF/repoHF-10.md")"
has   "…and the record says which kind of clear this was" "$hf10_log" "; kind in-process"
has   "…the top block says to EXPECT every writer below live" "$hf10_file" "expect every writer below live"
hasnt "…and never tells the next session to relaunch them all" "$hf10_file" "relaunch every writer below from where it stands"
hasnt "…nor to relaunch NONE of them: a kind says what to expect, never what to do (Addendum 1 (j))" "$hf10_file" "relaunch NONE of them"
has   "…with clause (i)'s count, which is the same first line in every kind" "$hf10_file" "FIRST count the live writers"
has   "…and the one message a live writer is owed in place of a relaunch" "$hf10_file" "its in-flight call died"
has   "…and the free text carries the kind after the why (Addendum 1 (h))" "$hf10_log" " — clear in-process"
is    "…and the pane is untouched: --in-process respawns nothing" \
      "$(grep -c 'respawn-pane' "$FAKE_TMUX_A17_LOG")" 0
run env PATH="$A17PATH" "$HANDOFF_CMD" --lane repoHF-4 --in-process --restart x
is    "--in-process with --restart is refused" "$rc" 2
has   "…because each of those replaces the process the writers are children of" "$err" "THIS PROCESS KEEPS RUNNING"
run env PATH="$A17PATH" "$HANDOFF_CMD" --lane repoHF-4 --in-process --exit x
is    "…and so is --in-process with --exit" "$rc" 2
run env PATH="$A17PATH" "$HANDOFF_CMD" --lane repoHF-4 --in-process --late --at "2026-09-14T12:02:27Z"
is    "…and --in-process with --late, which is a contradiction in its own terms" "$rc" 2
has   "…because a late record is written for a session that has ALREADY ended" "$err" "ALREADY ENDED"

# ----------------------------------------------- 3. --late, and its one rule

# The lane's last lane-kind line is a STARTED at 09:00Z; the session died at
# 12:02:27Z with no swap. The late record is written from a SHELL, before the
# relaunch, dated by the moment the old session ended.
run env PATH="$A17PATH" CLAUDE_CODE_SESSION_ID="$HF_ID" CLAUDE_PROFILE_NAME=team-05a \
    "$HANDOFF_CMD" --lane repoHF-4 --late
is    "--late with no --at is refused" "$rc" 2
has   "…naming the flag and why a late line is dated by its own field" "$err" "a late record is dated by the moment the OLD SESSION ENDED"
run env PATH="$A17PATH" CLAUDE_CODE_SESSION_ID="$HF_ID" CLAUDE_PROFILE_NAME=team-05a \
    "$HANDOFF_CMD" --lane repoHF-4 --late --at "not-a-utc"
is    "…and so is an --at that is not a UTC instant" "$rc" 2

hf_seed_log repoHF-4 "2026-09-14T09:00:00Z"
run env PATH="$A17PATH" CLAUDE_CODE_SESSION_ID="$HF_ID" CLAUDE_PROFILE_NAME=team-05a \
    "$HANDOFF_CMD" --lane repoHF-4 --late --at "2026-09-14T12:02:27Z"
is    "--late writes the record a swap never left" "$rc" 0
hf4_log="$(cat "$LOGD/repoHF-4.md")"
has   "…as the lane's own PAUSED" "$hf4_log" "PAUSED — lane repoHF-4, session $HF_ID@Eagle, 2026-09-14T12:02:27Z"
has   "…dated by the moment the old session ended, not by this shell's clock" "$hf4_log" "; late 2026-09-14T12:02:27Z"
has   "…with the why the act is for" "$hf4_log" "usage limit hit before the swap"
has   "…and the handoff refreshed by the session that now holds the knowledge" \
      "$(cat "$WIP/handoffs/repoHF/repoHF-4.md")" "expect none of the writers below live"
has   "…the late record being the RESPAWN kind: the session it is written for has already ended" \
      "$hf4_log" "; kind respawn"
has   "…and it says the relaunch comes next" "$out" "Now start the lane"

run env PATH="$A17PATH" CLAUDE_CODE_SESSION_ID="$HF_ID" CLAUDE_PROFILE_NAME=team-05a \
    "$HANDOFF_CMD" --lane repoHF-4 --late --at "2026-09-14T12:05:00Z"
is    "…and a second late record on an already-paused lane is refused" "$rc" 2
has   "…saying the record is already there" "$err" "already a PAUSED"
is    "…and the log is unchanged" "$(grep -c '^PAUSED' "$LOGD/repoHF-4.md")" 1

# THE ORDER IS THE RULE. A lane whose relaunch is already recorded may not take
# a late PAUSED: file order is what every state read means by "last", the log is
# append-only, and a PAUSED after that RESUMED would make a RUNNING lane read as
# paused.
hf_seed_log repoHF-7 "2026-09-14T09:00:00Z" \
  "RESUMED — lane repoHF-7, session $HF4_ID@Eagle, 2026-09-14T13:00:00Z, lane:repoHF-7 → home opensoft/repoHF; estate repoHF"
run env PATH="$A17PATH" CLAUDE_CODE_SESSION_ID="$HF4_ID" CLAUDE_PROFILE_NAME=team-05a \
    "$HANDOFF_CMD" --lane repoHF-7 --late --at "2026-09-14T12:02:27Z"
is    "--late is refused once the relaunch is recorded" "$rc" 2
has   "…naming the line that is already last" "$err" "RESUMED at 2026-09-14T13:00:00Z"
has   "…and what the log would otherwise say about a lane that is running" "$err" "would make a lane that is RUNNING read as paused"
has   "…with the act that was owed, in order" "$err" "from a SHELL, and only then start the lane"
is    "…and nothing was written" "$(grep -c '^PAUSED' "$LOGD/repoHF-7.md")" 0

# ------------------------------------- 4. lane-start --agent: the launcher table

mkdir -p "$WIP/handoffs/repoAG"
AG_DIR="$HOME/projects/repoAG"
mkdir -p "$AG_DIR"
git init -q -b main "$AG_DIR"
git -C "$AG_DIR" remote add origin "https://github.com/opensoft/repoAG.git"
ag_seed_handoff() {   # <lane>
  { printf 'Lane: %s (team-05a, session %s) — single-use resume prompt: stamp RESUMED-by before acting (lane-collision-protocol rule 3)\n' "$1" "$HF_ID"
    printf '\n'
    printf '## RESUME PROMPT — PAUSED 2026-09-14T12:00:00Z (clear), agent codex, transcript %s — relaunch every writer below from where it stands\n\n' "$CODEX_ID"
    printf '**FIRST ACTS, in order.** (1) You are lane `%s`. THE TOP BLOCK OF %s.\n\n' "$1" "$1"
    printf -- '---\n\n'
    printf 'Everything below the rule is history and is NOT the first prompt.\n'
  } > "$WIP/handoffs/repoAG/$1.md"
}
ag_row() {   # <lane> <cell>
  "$E" add-row "| \`$1\` | $2 | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoAG/$1.md | ACTIVE |" >/dev/null 2>&1
}
ag_seed_log() {   # <lane> <payload tail>
  { printf '# lane %s — object log (lane-collision-protocol Amendment 7)\n' "$1"
    printf 'STARTED — lane %s, session %s@Eagle, 2026-09-14T09:00:00Z, lane:%s → home opensoft/repoAG; estate repoAG; dir %s\n' \
      "$1" "$HF_ID" "$1" "$AG_DIR"
    printf 'PAUSED — lane %s, session %s@Eagle, 2026-09-14T12:00:00Z, lane:%s → swap; dir %s; workstation Eagle; %s — clear\n' \
      "$1" "$HF_ID" "$1" "$AG_DIR" "$2"
  } > "$LOGD/$1.md"
  git -C "$WIP" add -- "lanes/log/$1.md"
  git -C "$WIP" commit -q -m "LOG($1@Eagle): seed a paused lane"
  git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
  git -C "$WIP" push -q origin main
  return 0
}
for ag_l in repoAG-1 repoAG-2 repoAG-3 repoAG-4; do ag_seed_handoff "$ag_l"; done
git -C "$WIP" add -- handoffs/repoAG >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the repoAG handoffs"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
ag_row repoAG-1 "harness \`$HF2_ID\`"
ag_row repoAG-2 "harness \`$HF2_ID\`"
ag_row repoAG-3 "harness \`$HF2_ID\`"
ag_row repoAG-4 "harness \`$HF2_ID\`"
ag_seed_log repoAG-1 "agent codex; transcript $CODEX_ID"
ag_seed_log repoAG-2 "agent codex; transcript $CODEX_ID"
ag_seed_log repoAG-3 "agent claude; transcript $HF2_ID"
ag_seed_log repoAG-4 "agent claude; transcript $HF2_ID"

: > "$FAKE_CODEX_LOG"
export FAKE_CODEX_WATCH="$WIP/handoffs/repoAG/repoAG-1.md"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="agsess:@41" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$AG_DIR" --agent codex repoAG-1
is    "lane-start --agent codex exits 0" "$rc" 0
ag_codex="$(cat "$FAKE_CODEX_LOG")"
has   "…launching codex with the handoff's TOP BLOCK as its first prompt" "$ag_codex" "THE TOP BLOCK OF repoAG-1."
hasnt "…and only the top block: what is below the rule is history, not a prompt" "$ag_codex" "Everything below the rule is history"
is    "…with the Rule 3 stamp already in the file when codex was launched" \
      "$(grep -o 'stamps-at-launch=[0-9]*' "$FAKE_CODEX_LOG" | head -n1)" "stamps-at-launch=1"
has   "…the stamp naming the agent and its own id" \
      "$(cat "$WIP/handoffs/repoAG/repoAG-1.md")" "RESUMED by codex $CODEX_ID (lane repoAG-1) at"
has   "…the row's session cell appended in the agent's own spelling" \
      "$(grep '^| `repoAG-1`' "$LANES")" "→ Codex \`$CODEX_ID\`"
has   "…and the row's stamp says who resumed it" "$(grep '^| `repoAG-1`' "$LANES")" "RESUMED by codex $CODEX_ID (lane repoAG-1)"

: > "$FAKE_CODEX_LOG"
export FAKE_CODEX_WATCH="$WIP/handoffs/repoAG/repoAG-2.md"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="agsess:@41" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$AG_DIR" repoAG-2
is    "with no --agent at all, the default is the agent of the last PAUSED" "$rc" 0
has   "…which is codex here, launched with the top block" "$(cat "$FAKE_CODEX_LOG")" "THE TOP BLOCK OF repoAG-2."

: > "$FAKE_CLAUDE_LOG"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="agsess:@41" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$AG_DIR" --agent claude repoAG-3
is    "--agent claude with no transcript here exits 0" "$rc" 0
ag_claude="$(cat "$FAKE_CLAUDE_LOG")"
has   "…taking a NEW session named for the lane" "$ag_claude" "--name repoAG-3 --session-id"
has   "…with the handoff's top block as its first prompt" "$ag_claude" "THE TOP BLOCK OF repoAG-3."
hasnt "…and never the title fallback, which filters a picker" "$ag_claude" "--resume repoAG-3"

run env PATH="$A17PATH" FAKE_TMUX_WINDOW="agsess:@41" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$AG_DIR" --agent gpt-5-cli repoAG-4 --no-launch
is    "an agent the table does not carry is a refusal" "$rc" 2
has   "…naming the ones it knows" "$err" "It knows: claude"
has   "…and codex beside it" "$err" "codex"
hasnt "…and nothing was launched" "$(cat "$FAKE_CODEX_LOG")" "repoAG-4"

# A LAUNCHER THE TABLE KNOWS AND THIS WORKSTATION DOES NOT HAVE IS REFUSED
# BEFORE ANY WRITE (Copilot round 3 on openRepoTools#47, `lane-start:2132`).
# The row, the object log and the Rule 3 stamp are all written before the
# `exec`, so a `codex` that is not installed recorded the lane as RESUMED and
# then exited 127 — a false transition in two append-only files. The code now
# refuses in 5a, which is before every one of those writes.
#
# THERE IS NO CASE HERE, AND THE REASON IS THE FIXTURE AND NOT THE RULE. Asking
# it needs a PATH with no `codex` on it, and the estate's workstations install
# that launcher GLOBALLY: on the one this was written on it is `/usr/bin/codex`,
# `/bin/codex` and `~/.npm-global/bin/codex`, so `a17_path_without codex` —
# which is how the three `lane` cases below build their PATHs — returns the
# EMPTY string and takes `bash`, `git`, `awk` and `sed` with it, and every run
# on it dies at the shebang with `/usr/bin/env: bash: No such file`. A case that
# can only be asked on a machine without a launcher every lane workstation has
# is a case that is green on CI and red at the desk, which is the failure mode
# the `a17_path_without_lane` comment below exists to prevent. The rule is held
# by the code and stated here; a fixture that can express "no codex" without
# expressing "no shell" would be the way to ask it.

# A RECORDED TRANSCRIPT BELONGS TO THE AGENT THAT RECORDED IT (Copilot round 2
# on openRepoTools#47). `lane-transcript` answers for the LANE — its last
# `PAUSED`, whichever agent wrote it — so a lane paused by `claude` and resumed
# with `--agent codex` would take the CLAUDE uuid and append it to the row's
# session cell spelled `Codex <uuid>`: an id no `codex` can resume, attributing
# this lane's history to a conversation that is not it, in a cell nothing
# rewrites. repoAG-4's record says `agent claude; transcript $HF2_ID`.
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="agsess:@41" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$AG_DIR" --agent codex repoAG-4 --no-launch
is    "--agent codex over a record that names claude exits 0" "$rc" 0
has   "…saying whose the recorded transcript is, and that this launch does not take it" \
      "$err" "names agent claude and this launch is codex"
hasnt "…and the session cell is NOT appended with a Claude uuid in Codex's spelling" \
      "$(grep '^| `repoAG-4`' "$LANES")" "Codex \`$HF2_ID\`"

# A LANE WITH NO ROW IS A `STARTED`, WHATEVER BRANCH LAUNCHED IT. `--agent` and
# the `/ctx` seam both set the verb to RESUMED because they resume a lane that
# PAUSED; a lane the register has never carried has paused nothing, and a
# RESUMED opening its object log is a line no reader can pair with a start.
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="agsess:@41" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$AG_DIR" --agent claude repoAG-9 --no-launch
is    "--agent claude on a lane with NO row exits 0" "$rc" 0
has   "…saying there is nothing to have resumed" "$err" "no row yet"
has   "…and the object log opens with a STARTED" "$(cat "$LOGD/repoAG-9.md")" "STARTED — lane repoAG-9"
hasnt "…never a RESUMED for a lane that has paused nothing" "$(cat "$LOGD/repoAG-9.md")" "RESUMED"

# `LANE_START_FRESH=1` — the seam /ctx respawns through: a NEW session of this
# lane's agent, primed by the top block, even though the transcript is here.
FRESH_DIR="$HOME/projects/repoFR"
mkdir -p "$FRESH_DIR"
git init -q -b main "$FRESH_DIR"
git -C "$FRESH_DIR" remote add origin "https://github.com/opensoft/repoFR.git"
fr_tdir="$HOME/.claude/projects/$(sanitize "$FRESH_DIR")"
mkdir -p "$fr_tdir"
printf '{"type":"user"}\n' > "$fr_tdir/$HF3_ID.jsonl"
mkdir -p "$WIP/handoffs/repoFR"
{ printf 'Lane: repoFR-1 (team-05a, session %s) — single-use resume prompt: stamp RESUMED-by before acting (lane-collision-protocol rule 3)\n' "$HF3_ID"
  printf '\n'
  printf '## RESUME PROMPT — the top block of repoFR-1\n'
} > "$WIP/handoffs/repoFR/repoFR-1.md"
git -C "$WIP" add -- handoffs/repoFR >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the repoFR handoff"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoFR-1\` | harness \`$HF3_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoFR/repoFR-1.md | ACTIVE |" >/dev/null 2>&1

: > "$FAKE_CLAUDE_LOG"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="frsess:@51" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$FRESH_DIR" repoFR-1 --no-launch
is    "without the seam, a lane whose transcript is here resumes it by id" "$rc" 0
has   "…exactly as Amendment 6 has always done" "$out" "--resume $HF3_ID"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="frsess:@51" CLAUDE_PROFILE_NAME=team-05a \
    LANE_START_FRESH=1 "$START" --dir "$FRESH_DIR" repoFR-1 --no-launch
is    "with LANE_START_FRESH=1 the same lane takes a NEW session" "$rc" 0
hasnt "…never a resume of the transcript the /ctx just paused" "$out" "--resume $HF3_ID"
has   "…named for the lane" "$out" "--name repoFR-1 --session-id"
has   "…and primed by the handoff's top block" "$out" "the top block of repoFR-1"

# ------------------------- 5. act 6: the transcript follows the lane

# A SHARED `projects/` NEEDS NO MOVE, and that is the measured fact this act
# shrank to (2026-09-14T12:35Z): on a launcher-configured workstation every
# profile's `projects/` resolves to ONE directory.
#
# ITS OWN LANE, because the case is about the row's LAST id having a transcript
# here: `repoFR-1`'s cell has since gained the uuid the `LANE_START_FRESH=1` run
# minted, and that one has no transcript at all — which is the OTHER branch.
mkdir -p "$HOME/.claude-profiles/profiles/opensoft/team/t3"
ln -sfn "$HOME/.claude/projects" "$HOME/.claude-profiles/profiles/opensoft/team/t3/projects"
SH_DIR="$HOME/projects/repoSH"
SH_ID="a17a0007-7777-4000-8000-a17a00077777"
mkdir -p "$SH_DIR"
git init -q -b main "$SH_DIR"
git -C "$SH_DIR" remote add origin "https://github.com/opensoft/repoSH.git"
sh_tdir="$HOME/.claude/projects/$(sanitize "$SH_DIR")"
mkdir -p "$sh_tdir"
printf '{"type":"user"}\n' > "$sh_tdir/$SH_ID.jsonl"
mkdir -p "$WIP/handoffs/repoSH"
printf 'Lane: repoSH-1 — resume prompt\n\nx\n' > "$WIP/handoffs/repoSH/repoSH-1.md"
git -C "$WIP" add -- handoffs/repoSH >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the repoSH handoff"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoSH-1\` | harness \`$SH_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoSH/repoSH-1.md | ACTIVE |" >/dev/null 2>&1
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="shsess:@81" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$SH_DIR" repoSH-1 --no-launch
is    "lane-start says WHERE it found the transcript" "$rc" 0
has   "…naming this profile's projects directory" "$err" "found in this profile's projects directory"
has   "…and saying that directory is SHARED, so a profile switch moves nothing" "$err" "which IS the directory profile(s) t3 read too"
has   "…and it resumes the lane by id, moving nothing" "$out" "--resume $SH_ID"

# A PROFILE WHOSE `projects/` IS REALLY ANOTHER DIRECTORY: the transcript is
# MOVED, a pointer is left, and the lane resumes by id.
MV_DIR="$HOME/projects/repoMV"
mkdir -p "$MV_DIR"
git init -q -b main "$MV_DIR"
git -C "$MV_DIR" remote add origin "https://github.com/opensoft/repoMV.git"
MV_ID="a17a0005-5555-4000-8000-a17a00055555"
t2_projects="$HOME/.claude-profiles/profiles/opensoft/team/t2/projects"
mv_slug="$(sanitize "$MV_DIR")"
mkdir -p "$t2_projects/$mv_slug"
printf '{"type":"user"}\n' > "$t2_projects/$mv_slug/$MV_ID.jsonl"
mkdir -p "$t2_projects/$mv_slug/$MV_ID"
printf 'a sidecar file\n' > "$t2_projects/$mv_slug/$MV_ID/sidecar.txt"
mkdir -p "$WIP/handoffs/repoMV"
printf 'Lane: repoMV-1 — resume prompt\n\nx\n' > "$WIP/handoffs/repoMV/repoMV-1.md"
git -C "$WIP" add -- handoffs/repoMV >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the repoMV handoff"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoMV-1\` | harness \`$MV_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoMV/repoMV-1.md | ACTIVE |" >/dev/null 2>&1

run env PATH="$A17PATH" FAKE_TMUX_WINDOW="mvsess:@61" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$MV_DIR" repoMV-1 --no-launch
is    "a transcript in ANOTHER profile's own projects directory is followed" "$rc" 0
has   "…and the move is said, with both directories" "$err" "moved into $HOME/.claude/projects/$mv_slug"
is    "…the transcript is HERE now" \
      "$( [ -f "$HOME/.claude/projects/$mv_slug/$MV_ID.jsonl" ] && echo yes || echo no )" yes
is    "…its sibling directory came with it" \
      "$( [ -f "$HOME/.claude/projects/$mv_slug/$MV_ID/sidecar.txt" ] && echo yes || echo no )" yes
is    "…it is a MOVE and not a copy, because two live transcripts of one uuid diverge" \
      "$( [ -f "$t2_projects/$mv_slug/$MV_ID.jsonl" ] && echo no || echo yes )" yes
is    "…with a pointer left where it was" \
      "$(ls "$t2_projects/$mv_slug" | grep -c "^$MV_ID.jsonl.moved-to-team-05a-")" 1
has   "…and the lane resumes it by id" "$out" "--resume $MV_ID"

# A UUID WHOSE HOLDER IS LIVE IN THE OTHER PROFILE IS A REFUSAL, NEVER A MOVE
# (Amendment 18(h): one live process per transcript).
LV_DIR="$HOME/projects/repoLV"
mkdir -p "$LV_DIR"
git init -q -b main "$LV_DIR"
git -C "$LV_DIR" remote add origin "https://github.com/opensoft/repoLV.git"
LV_ID="a17a0006-6666-4000-8000-a17a00066666"
lv_slug="$(sanitize "$LV_DIR")"
mkdir -p "$t2_projects/$lv_slug"
printf '{"type":"user"}\n' > "$t2_projects/$lv_slug/$LV_ID.jsonl"
mkdir -p "$HOME/.claude-profiles/profiles/opensoft/team/t2/sessions"
# NAMED FOR ANOTHER LANE, BY A PERSON — so `live_holder`'s fifth test skips it
# and this lane does not read as live at step 3. That is exactly the shape
# Amendment 18(h) is written about: a SECOND PROCESS on one transcript that the
# lane's own liveness read does not see, which is how three of them came to hold
# this lane's id on 2026-09-14.
write_record_ns "$HOME/.claude-profiles/profiles/opensoft/team/t2/sessions/live-lv.json" \
  "$LV_ID" "$LIVE_PID" "$live_start" "othersess:@99.%99" "somewhere-else-9" "user" "idle"
mkdir -p "$WIP/handoffs/repoLV"
printf 'Lane: repoLV-1 — resume prompt\n\nx\n' > "$WIP/handoffs/repoLV/repoLV-1.md"
git -C "$WIP" add -- handoffs/repoLV >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the repoLV handoff"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoLV-1\` | harness \`$LV_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoLV/repoLV-1.md | ACTIVE |" >/dev/null 2>&1

run env PATH="$A17PATH" FAKE_TMUX_WINDOW="lvsess:@71" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$LV_DIR" repoLV-1 --no-launch
is    "a transcript a LIVE process holds in another profile is refused" "$rc" 2
has   "…naming the pid" "$err" "pid $LIVE_PID"
has   "…and where that process is" "$err" "othersess:@99.%99"
has   "…and the rule it would have broken" "$err" "held by ONE live process"
has   "…with the retire act" "$err" "lane-end repoLV-1 --retire"
is    "…and the transcript was NOT moved" \
      "$( [ -f "$t2_projects/$lv_slug/$LV_ID.jsonl" ] && echo yes || echo no )" yes

# `--dry-run` MOVES NOTHING (Copilot round 1 on openRepoTools#47). This search
# runs long before the dry-run exit at the foot of the command, and a run whose
# last line is *nothing was renamed, written or launched* must not have moved a
# person's transcript out of another profile to get there.
DR_DIR="$HOME/projects/repoDR"
DR_ID="a17a0008-8888-4000-8000-a17a00088888"
mkdir -p "$DR_DIR"
git init -q -b main "$DR_DIR"
git -C "$DR_DIR" remote add origin "https://github.com/opensoft/repoDR.git"
dr_slug="$(sanitize "$DR_DIR")"
mkdir -p "$t2_projects/$dr_slug"
printf '{"type":"user"}\n' > "$t2_projects/$dr_slug/$DR_ID.jsonl"
mkdir -p "$WIP/handoffs/repoDR"
printf 'Lane: repoDR-1 — resume prompt\n\nx\n' > "$WIP/handoffs/repoDR/repoDR-1.md"
git -C "$WIP" add -- handoffs/repoDR >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the repoDR handoff"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoDR-1\` | harness \`$DR_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoDR/repoDR-1.md | ACTIVE |" >/dev/null 2>&1
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="drsess:@91" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$DR_DIR" repoDR-1 --dry-run
is    "a --dry-run that finds a transcript in another profile exits 0" "$rc" 0
has   "…printing the move it WOULD make, with both paths" "$err" "PLAN mv $t2_projects/$dr_slug/$DR_ID.jsonl"
has   "…and saying nothing was moved" "$err" "Nothing was moved"
is    "…the transcript is exactly where it was" \
      "$( [ -f "$t2_projects/$dr_slug/$DR_ID.jsonl" ] && echo yes || echo no )" yes
is    "…and this profile has no copy of it" \
      "$( [ -f "$HOME/.claude/projects/$dr_slug/$DR_ID.jsonl" ] && echo no || echo yes )" yes

# THE MOVE IS ONE TRANSACTION. The `.jsonl`, its sibling `<uuid>/` state
# directory and the pointer left behind are one act: a sibling orphaned in the
# other profile is state the resumed session silently loses, so a step that
# cannot complete PUTS BACK what the steps before it moved and refuses. A file
# already sitting where the sibling directory must go is how that is asked.
RB_DIR="$HOME/projects/repoRB"
RB_ID="a17a0009-9999-4000-8000-a17a00099999"
mkdir -p "$RB_DIR"
git init -q -b main "$RB_DIR"
git -C "$RB_DIR" remote add origin "https://github.com/opensoft/repoRB.git"
rb_slug="$(sanitize "$RB_DIR")"
mkdir -p "$t2_projects/$rb_slug/$RB_ID"
printf '{"type":"user"}\n' > "$t2_projects/$rb_slug/$RB_ID.jsonl"
printf 'a sidecar file\n' > "$t2_projects/$rb_slug/$RB_ID/sidecar.txt"
mkdir -p "$HOME/.claude/projects/$rb_slug"
printf 'not a directory\n' > "$HOME/.claude/projects/$rb_slug/$RB_ID"
mkdir -p "$WIP/handoffs/repoRB"
printf 'Lane: repoRB-1 — resume prompt\n\nx\n' > "$WIP/handoffs/repoRB/repoRB-1.md"
git -C "$WIP" add -- handoffs/repoRB >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the repoRB handoff"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoRB-1\` | harness \`$RB_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoRB/repoRB-1.md | ACTIVE |" >/dev/null 2>&1
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="rbsess:@92" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$RB_DIR" repoRB-1 --no-launch
is    "a move whose SIBLING cannot follow is refused, not half made" "$rc" 2
has   "…naming the sibling that could not follow" "$err" "sibling state directory"
has   "…and saying the move was put back" "$err" "the move was put back"
is    "…the transcript IS back where it was" \
      "$( [ -f "$t2_projects/$rb_slug/$RB_ID.jsonl" ] && echo yes || echo no )" yes
is    "…its sibling never left either" \
      "$( [ -f "$t2_projects/$rb_slug/$RB_ID/sidecar.txt" ] && echo yes || echo no )" yes
is    "…and this profile holds no half-moved transcript" \
      "$( [ -f "$HOME/.claude/projects/$rb_slug/$RB_ID.jsonl" ] && echo no || echo yes )" yes
is    "…and no pointer was left for a move that did not happen" \
      "$(ls "$t2_projects/$rb_slug" | grep -c "moved-to-")" 0

# AND AN OCCUPIED DESTINATION IS REFUSED BEFORE ANYTHING MOVES AT ALL (Copilot
# round 3 on openRepoTools#47). `mv <dir> <existing dir>` does NOT fail — it
# moves the source INSIDE it — so a `<uuid>/` already sitting here would take
# the other profile's sidecar as `<uuid>/<uuid>/`, mark the sibling moved, and
# resume with the transcript's state split from the transcript. Which of two
# `<uuid>` directories is this lane's is not a thing to guess at.
OC_DIR="$HOME/projects/repoOC"
OC_ID="a17a0010-1010-4000-8000-a17a00101010"
mkdir -p "$OC_DIR"
git init -q -b main "$OC_DIR"
git -C "$OC_DIR" remote add origin "https://github.com/opensoft/repoOC.git"
oc_slug="$(sanitize "$OC_DIR")"
mkdir -p "$t2_projects/$oc_slug/$OC_ID"
printf '{"type":"user"}\n' > "$t2_projects/$oc_slug/$OC_ID.jsonl"
printf 'the other profile.s sidecar\n' > "$t2_projects/$oc_slug/$OC_ID/sidecar.txt"
mkdir -p "$HOME/.claude/projects/$oc_slug/$OC_ID"
printf 'a sidecar that is ALREADY here\n' > "$HOME/.claude/projects/$oc_slug/$OC_ID/sidecar.txt"
mkdir -p "$WIP/handoffs/repoOC"
printf 'Lane: repoOC-1 — resume prompt\n\nx\n' > "$WIP/handoffs/repoOC/repoOC-1.md"
git -C "$WIP" add -- handoffs/repoOC >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the repoOC handoff"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
"$E" add-row "| \`repoOC-1\` | harness \`$OC_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoOC/repoOC-1.md | ACTIVE |" >/dev/null 2>&1
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="ocsess:@93" CLAUDE_PROFILE_NAME=team-05a \
    "$START" --dir "$OC_DIR" repoOC-1 --no-launch
is    "a destination that already holds that uuid is refused before anything moves" "$rc" 2
has   "…naming what already sits there" "$err" "ALREADY SITS where it would go"
is    "…the transcript never left the other profile" \
      "$( [ -f "$t2_projects/$oc_slug/$OC_ID.jsonl" ] && echo yes || echo no )" yes
is    "…and nothing was nested inside the directory that was already here" \
      "$( [ -e "$HOME/.claude/projects/$oc_slug/$OC_ID/$OC_ID" ] && echo no || echo yes )" yes
is    "…which still holds exactly what it held" \
      "$(cat "$HOME/.claude/projects/$oc_slug/$OC_ID/sidecar.txt")" "a sidecar that is ALREADY here"

# ------------------------------------------- 6. the three names are one act

hfsk="$(cat "$SRC_DIR/skills/handoff/SKILL.md")"
lssk="$(cat "$SRC_DIR/skills/lane-swap/SKILL.md")"
swcmd="$(cat "$SRC_DIR/commands/swap.md")"
hfcmd="$(cat "$SRC_DIR/commands/handoff.md")"
ctxcmd="$(cat "$SRC_DIR/commands/ctx.md")"
has   "the handoff skill is the act itself" "$hfsk" "# \`/handoff\` — hand this lane off"
has   "…and names the shell form as the same steps" "$hfsk" "\`lane-handoff\` is these same steps as one command"
has   "the lane-swap skill is an ALIAS of it" "$lssk" "Invoke the \`handoff\` skill now"
hasnt "…restating none of its steps" "$lssk" "## 4. Write the swap record"
has   "the /swap command names the same skill" "$swcmd" "Invoke the \`handoff\` skill now"
has   "the /handoff command names it too" "$hfcmd" "Invoke the \`handoff\` skill now"
has   "and /ctx is that skill with --restart" "$ctxcmd" "with \`--restart\`"
has   "…which is what the amendment calls it" "$ctxcmd" "/ctx\` is \`/handoff --restart\`"
has   "the skill carries Amendment 17(b)'s two sub-fields where the record is written" "$hfsk" "agent \$agent_name; transcript \$transcript_id"
has   "…and the WRITERS section in its top block" "$hfsk" "**WRITERS at <UTC>**"
has   "the skill's top block carries Addendum 1 (i)'s count, in the same words the command writes" \
      "$hfsk" "FIRST count the live writers"
has   "…a live writer owning its worktree, messaged rather than relaunched" \
      "$hfsk" "A writer still live OWNS its worktree"
has   "…and the count beating the list where the two disagree" "$hfsk" "THE COUNT WINS"
has   "…with clause (k) in the first acts" "$hfsk" "ONE WORKTREE, ONE WRITER"
has   "…and the THREE kinds, with what each tells the next session to EXPECT" \
      "$hfsk" "kind <in-process|respawn|unknown>"
has   "…the in-process one expecting every writer live" "$hfsk" "expect every writer below live"
has   "…and the unknown one, which a plain handoff cannot know (Addendum 1 (h))" \
      "$hfsk" "THIS HANDOFF CANNOT KNOW WHICH KIND FOLLOWED IT"
has   "the skill's own record writer carries the kind sub-field too" "$hfsk" 'payload="$payload; kind $kind"'
has   "…and the free text after the why, in the addendum's spelling" "$hfsk" "kind unknown"
has   "…and it asks window-session with the harness's own spelling of the window" \
      "$hfsk" "#{session_name}:#{window_id}"
has   "…and its row write SETS the whole cell, as the command does (Amendment 13(a))" \
      "$hfsk" 'set-row-state "$lane" "PAUSED · $hs_line"'
has   "…with the line cut where a cut cannot land inside a character" "$hfsk" 'hs_line="${hs_line% *} ..."'
hasnt "…and never the anchor the two writes it replaced had to guess at" "$hfsk" '"$state" "$state_new" "swap"'
has   "…and the measured fact that is the whole reason for the distinction" \
      "$hfsk" "mints a NEW TRANSCRIPT ID IN THE SAME PROCESS"
has   "and the respawn line Addendum 2 (i-8) names: \`lane <lane>\`" "$hfsk" 'LANE_START_FRESH=1 lane $lane'
has   "…with the launcher as the door the same clause leaves open" "$hfsk" "pclaude --lane \$lane"
has   "…chosen by whether that word is on PATH, which is the choice the command makes in code" \
      "$hfsk" 'if command -v lane >/dev/null 2>&1; then'
hasnt "…which is never \`restart <lane>\`" "$hfsk" 'respawn-pane -k -t "$pane" "restart'

echo "== Amendment 18 Addendum 1: the word \`lane\`, the numbered pick, the three branches =="
#
# AMENDMENT 18 ADDENDUM 1, RATIFIED 2026-09-14T14:05:54Z verbatim "ratify the
# addendum", out of Brett Heap's two messages that morning — *"i dont understand
# in another window i want to attach to that lane. what command do i use to do
# that?"* and *"this is too hard for users. we need simple way to list the lanes
# and then pick one to bind."* — and his answer to what the word should be,
# verbatim "lane (Recommended)".
#
# FIVE STATES IN ONE REGISTER, because the pick is a PARTITION and a partition
# is only proved by the rows it puts on each side:
#
#   repoPick-1  PAUSED, dir and profile recorded        AVAILABLE
#   repoPick-7  a binding THIS host proves dead         AVAILABLE
#   repoPick-2  LIVE, in the session this shell is in   LIVE HERE (select only)
#   repoPick-3  LIVE, in a DETACHED session             LIVE HERE (move + select)
#   repoPick-4  a binding on ANOTHER workstation        BOUND ELSEWHERE
#   repoPick-5  ENDED                                   HIDDEN (Amendment 19)
#
# THE NUMBERS ARE THE READ'S ORDER AND THE STAMPS DECIDE THEM: rows come back
# newest activity first, and the pick renders available, then live here, then
# bound elsewhere, numbering as it goes. So the six stamps above descend in the
# order the list is read in — 10:00, 09:50, 09:40, 09:30, 09:20 — and the
# answers below are 1 repoPick-1 · 2 repoPick-7 · 3 repoPick-2 · 4 repoPick-3 ·
# 5 repoPick-4. A case that hard-codes a number without pinning the stamp is a
# case that passes for the wrong reason.
#
# THE FAKE TMUX IS THIS SECTION'S OWN, in a directory of its own put FIRST on
# PATH for these cases only. The suite's shared fake answers the reads
# `lane-start`, `lane-end` and `window-lane` make; this one answers the four
# `lane` makes (`#S`, `#{session_name}`, `#{window_index}`, `#{session_attached}`)
# and LOGS the three acts — `move-window`, `select-window`, `switch-client` and
# the `attach` — so the attach can be watched without a tmux server. Its window
# table is `<@id><TAB><session><TAB><index><TAB><attached>`.
mkdir -p "$SANDBOX/lanebin"
cat > "$SANDBOX/lanebin/tmux" <<'FAKE'
#!/usr/bin/env bash
lt_by_id()   { printf '%s\n' "${LANE_TMUX_WINDOWS:-}" | awk -F'\t' -v t="$1" '$1 == t { print; exit }'; }
lt_by_sess() { printf '%s\n' "${LANE_TMUX_WINDOWS:-}" | awk -F'\t' -v s="$1" '$2 == s { print; exit }'; }
case "${1-}" in
  display-message)
    shift
    lt_t=""; lt_f=""
    while [ $# -gt 0 ]; do
      case "$1" in
        -p) shift ;;
        -t) lt_t="${2-}"; shift 2 ;;
        *)  lt_f="$1"; shift ;;
      esac
    done
    if [ -z "$lt_t" ]; then
      case "$lt_f" in
        '#S') printf '%s\n' "${LANE_TMUX_THIS:-}" ;;
        *)    printf '\n' ;;
      esac
      exit 0
    fi
    lt_l="$(lt_by_id "$lt_t")"
    [ -n "$lt_l" ] || lt_l="$(lt_by_sess "$lt_t")"
    [ -n "$lt_l" ] || exit 1
    case "$lt_f" in
      '#{session_name}')     printf '%s\n' "$(printf '%s' "$lt_l" | cut -f2)" ;;
      '#{window_index}')     printf '%s\n' "$(printf '%s' "$lt_l" | cut -f3)" ;;
      '#{session_attached}') printf '%s\n' "$(printf '%s' "$lt_l" | cut -f4)" ;;
      '#{window_id}')        printf '%s\n' "$(printf '%s' "$lt_l" | cut -f1)" ;;
      *)                     printf '\n' ;;
    esac ;;
  select-window)
    # THE ONE ACT THAT CAN FAIL AFTER THE FENCE HAS PASSED: the window resolved
    # a moment ago and is gone by the time it is selected. `$LANE_TMUX_SELECT_FAIL`
    # is that window, and nothing is logged — because nothing happened.
    [ -z "${LANE_TMUX_SELECT_FAIL:-}" ] || exit 1
    printf '%s\n' "$*" >> "${LANE_TMUX_LOG:-/dev/null}" ;;
  move-window)
    # THE MOVE CAN LOSE THE SAME RACE, and tmux refuses a `<session>:<@id>`
    # whose window has left that session between the check and the act —
    # measured on tmux 3.4, `can't find window: @2`, exit 1. Nothing is
    # logged, because nothing happened.
    [ -z "${LANE_TMUX_MOVE_FAIL:-}" ] || exit 1
    printf '%s\n' "$*" >> "${LANE_TMUX_LOG:-/dev/null}" ;;
  switch-client)
    [ -z "${LANE_TMUX_SWITCH_FAIL:-}" ] || exit 1
    printf '%s\n' "$*" >> "${LANE_TMUX_LOG:-/dev/null}" ;;
  attach|attach-session)
    printf '%s\n' "$*" >> "${LANE_TMUX_LOG:-/dev/null}" ;;
  *) : ;;
esac
FAKE
chmod +x "$SANDBOX/lanebin/tmux"
export LANE_TMUX_LOG="$SANDBOX/lane-tmux.log"
: > "$LANE_TMUX_LOG"
export LANE_TMUX_THIS="picksess"
export LANE_TMUX_WINDOWS="$(printf '@31\tpicksess\t3\t1\n@32\tdetsess\t7\t0\n@33\tothersess\t1\t1\n')"
LANEBIN_PATH="$SANDBOX/lanebin:$PATH"

# THE ONE ANSWER, READ FROM A REAL TERMINAL. `[ -t 0 ]` is the whole of what
# decides whether the question is asked, so a case that faked the test rather
# than the terminal would prove nothing about the branch a person meets. This
# runs the word under a pty, writes ONE line into it and collects everything the
# terminal saw — stdout and stderr together, which is what a terminal is.
LANE_PTY="$SANDBOX/pty-run.py"
cat > "$LANE_PTY" <<'PY'
import os, pty, select, sys

answer, argv = sys.argv[1], sys.argv[2:]
pid, fd = pty.fork()
if pid == 0:
    try:
        os.execvp(argv[0], argv)
    finally:
        os._exit(127)
os.write(fd, (answer + "\n").encode())
seen = b""
while True:
    try:
        ready, _, _ = select.select([fd], [], [], 60)
    except OSError:
        break
    if not ready:
        os.kill(pid, 9)
        break
    try:
        chunk = os.read(fd, 65536)
    except OSError:
        break
    if not chunk:
        break
    seen += chunk
_, status = os.waitpid(pid, 0)
sys.stdout.write(seen.decode("utf-8", "replace"))
sys.exit(os.WEXITSTATUS(status) if os.WIFEXITED(status) else 128 + os.WTERMSIG(status))
PY
HAVE_PTY=0
python3 -c 'import pty' >/dev/null 2>&1 && HAVE_PTY=1
NO_PTY_WHY="no python3 with pty on this host, so no terminal can be faked and the one question cannot be asked"
lane_pick() {   # <answer> <args to lane…>
  run env PATH="$LANEBIN_PATH" python3 "$LANE_PTY" "$@"
}

# ------------------------------------------------------------- the fixtures
PICK_DIR="$HOME/projects/repoPick"
mkdir -p "$PICK_DIR"
git init -q -b main "$PICK_DIR"
git -C "$PICK_DIR" remote add origin "https://github.com/opensoft/repoPick.git"
PICK1_ID="dddd0001-1111-4000-8000-dddd00011111"
PICK2_ID="dddd0002-2222-4000-8000-dddd00022222"
PICK3_ID="dddd0003-3333-4000-8000-dddd00033333"
PICK4_ID="dddd0004-4444-4000-8000-dddd00044444"
PICK5_ID="dddd0005-5555-4000-8000-dddd00055555"
PICK7_ID="dddd0007-7777-4000-8000-dddd00077777"
# The two LIVE ones are live because a real process is: the same `sleep` every
# liveness case in this file leans on, under two session ids of their own.
write_record "$sessions_dir/pick-here.json" "$PICK2_ID" "$LIVE_PID" "$live_start" "picksess:@31.%31" "repoPick-2" "busy"
write_record "$sessions_dir/pick-det.json"  "$PICK3_ID" "$LIVE_PID" "$live_start" "detsess:@32.%32"  "repoPick-3" "idle"
add_seed_row "| \`repoPick-1\` | harness \`$PICK1_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoPick/1.md | ACTIVE |"
add_seed_row "| \`repoPick-2\` | harness \`$PICK2_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoPick/2.md | ACTIVE |"
add_seed_row "| \`repoPick-3\` | harness \`$PICK3_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoPick/3.md | ACTIVE |"
add_seed_row "| \`repoPick-4\` | harness \`$PICK4_ID\` | Raven / test / brett | 2026-09-11T00:00Z | none | handoffs/repoPick/4.md | ACTIVE |"
add_seed_row "| \`repoPick-5\` | harness \`$PICK5_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoPick/5.md | ACTIVE |"
add_seed_row "| \`repoPick-7\` | harness \`$PICK7_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoPick/7.md | ACTIVE |"
{ printf '# lane repoPick-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoPick-1, session %s@Eagle, 2026-09-12T09:00:00Z, lane:repoPick-1 → home opensoft/repoPick; estate repoPick; dir %s; profile team-05a\n' "$PICK1_ID" "$PICK_DIR"
  printf 'PAUSED — lane repoPick-1, session %s@Eagle, 2026-09-12T10:00:00Z, lane:repoPick-1 → swap; dir %s; profile team-05a; workstation Eagle\n' "$PICK1_ID" "$PICK_DIR"
} > "$LOGD/repoPick-1.md"
{ printf '# lane repoPick-2 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoPick-2, session %s@Eagle, 2026-09-12T09:40:00Z, lane:repoPick-2 → home opensoft/repoPick; estate repoPick; dir %s; profile team-05a; window picksess:3 @31\n' "$PICK2_ID" "$PICK_DIR"
} > "$LOGD/repoPick-2.md"
{ printf '# lane repoPick-3 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoPick-3, session %s@Eagle, 2026-09-12T09:30:00Z, lane:repoPick-3 → home opensoft/repoPick; estate repoPick; dir %s; profile team-05a; window detsess:7 @32\n' "$PICK3_ID" "$PICK_DIR"
} > "$LOGD/repoPick-3.md"
# BOUND ELSEWHERE is a STARTED that never paused, on a workstation this host
# cannot see the session records of: `lanes_rows` cannot prove it dead and this
# machine has no way to say NOT LIVE about Raven.
{ printf '# lane repoPick-4 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'RESUMED — lane repoPick-4, session %s@Raven, 2026-09-12T09:20:00Z, lane:repoPick-4 → home opensoft/repoPick; estate repoPick; dir /elsewhere/repoPick; profile team-09z; window ravensess:2 @44\n' "$PICK4_ID"
} > "$LOGD/repoPick-4.md"
{ printf '# lane repoPick-5 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoPick-5, session %s@Eagle, 2026-09-12T09:40:00Z, lane:repoPick-5 → home opensoft/repoPick; estate repoPick; dir %s; profile team-05a\n' "$PICK5_ID" "$PICK_DIR"
  printf 'ENDED — lane repoPick-5, session %s@Eagle, 2026-09-12T11:40:00Z, lane:repoPick-5 — window closing; NOTHING IN FLIGHT\n' "$PICK5_ID"
} > "$LOGD/repoPick-5.md"
# A BINDING THIS HOST PROVES DEAD: a STARTED on THIS workstation with no live
# session record naming its id. That is the second half of "available", and the
# half a person is likeliest to meet — a lane whose window was closed without a
# swap.
{ printf '# lane repoPick-7 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoPick-7, session %s@Eagle, 2026-09-12T09:50:00Z, lane:repoPick-7 → home opensoft/repoPick; estate repoPick; dir %s; profile team-05a\n' "$PICK7_ID" "$PICK_DIR"
} > "$LOGD/repoPick-7.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the five states the pick partitions"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main

# THE TWO `next-free` WRAPPERS BOTH SURFACES NEED, made once here: `lane`'s
# pick and `lanes`'s footer read the same helper and answer for it the same
# way, so the cases that prove it read the same two fakes. `nfold` is the
# un-upgraded workstation (2, the contract's own silent code); `nfbroke` is a
# read that FAILED, which is never the same thing (Amendment 7(d)).
cat > "$SANDBOX/nfold" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  next-free) printf "lanes-edit: unknown subcommand 'next-free'\n" >&2; exit 2 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/nfold"
cat > "$SANDBOX/nfbroke" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  next-free) printf 'lanes-edit: simulated failure\n' >&2; exit 6 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/nfbroke"

# ------------------------------------- the partition, asked of the helper
#
# THE GROUPING IS A READ AND IS HELD AS ONE. `lane` renders it; `lanes-edit.sh
# lane-groups` decides it, over the rows both words already have, so the two
# surfaces cannot come to disagree about which lanes are free — the rule that
# put column 10 in the read (A11 Addendum 4 ruling 7).
run env LANES_NO_FETCH=1 "$E" lanes --prefix repoPick
is   "the rows of the seeded repository read" "$rc" 0
PICK_ROWS="$out"
pick_group_of() { printf '%s\n' "$PICK_GROUPS" | awk -F'\t' -v l="$1" '$2 == l { print $1; exit }'; }
PICK_GROUPS="$(printf '%s\n' "$PICK_ROWS" | "$E" lane-groups Eagle)"
is   "a PAUSED lane is AVAILABLE" "$(pick_group_of repoPick-1)" "available"
is   "a lane a live session here holds is LIVE" "$(pick_group_of repoPick-2)" "live"
is   "…and so is one in a detached session of this workstation" "$(pick_group_of repoPick-3)" "live"
is   "a binding on ANOTHER workstation is BOUND ELSEWHERE" "$(pick_group_of repoPick-4)" "elsewhere"
is   "a binding THIS host proves dead is AVAILABLE" "$(pick_group_of repoPick-7)" "available"
is   "an ENDED lane is in no group at all (Amendment 19)" "$(pick_group_of repoPick-5)" ""
# AND A `PAUSED` ROW OF ANOTHER WORKSTATION IS AVAILABLE HERE, which is the act
# this whole word exists for and is asserted so that no reordering of that awk
# can take it away quietly (Copilot round 10 on #45, `lanes-edit.sh:4870`, which
# asked for exactly this case for exactly that reason — and round 9 and round 10
# both read the same branch as a defect). `go_elsewhere`'s own refusal is the
# contract, in the words a person reads: *"the exit is a person on <workstation>
# parking it — `/lane-swap` in that session — after which it is PARKED and `lane
# <lane>` takes it here"*. Fed straight to the helper, because the seeded rows of
# this section are a partition of THIS workstation's and adding a sixth row to
# them would renumber every pick below.
is   "a PAUSED row of ANOTHER workstation is AVAILABLE, because parking IS the handoff" \
     "$(printf 'someRepo-9\tPAUSED\tRaven\n' | "$E" lane-groups Eagle | cut -f1)" "available"
is   "…while a BINDING of that same workstation is bound elsewhere, as it always was" \
     "$(printf 'someRepo-9\tIDLE\tRaven\n' | "$E" lane-groups Eagle | cut -f1)" "elsewhere"
run env LANES_NO_FETCH=1 "$E" lanes --lane repoFX20-2
is   "…and a RETIRED one is not either" "$(printf '%s\n' "$out" | "$E" lane-groups Eagle)" ""
# THE NEXT FREE POSITION IS THE SAME READ'S, over the same rows, so `lane`'s `f`
# and `lanes`'s footer cannot offer two different positions.
is   "next-free is the LOWEST position no lane of that repository holds" \
     "$(printf '%s\n' "$PICK_ROWS" | "$E" next-free repoPick)" "6"
run env LANES_NO_FETCH=1 "$E" next-free
is   "…and it refuses with the contract's 64 when no repository is named" "$rc" 64
# A POSITION A LANE HAS HELD IS RESERVED, `ENDED` AND `RETIRED` INCLUDED, and a
# NEIGHBOUR REPOSITORY'S LANES ARE NOT THIS ONE'S (Copilot round 7 on #45,
# `lanes-edit.sh:4839` and `:4853`). The first is why `repoPick-5`, which ended
# two fixtures ago, does not hand 5 back: a lane's identity is its name and its
# object log is append-only, so a second lane at that position would write its
# life into the first one's file. The second is a prefix test that read
# `repo-foo-1` as a lane of `repo` and took a position out of its neighbour.
is   "an ENDED lane's position is RESERVED and never handed out again" \
     "$(printf '%s\n' "$PICK_ROWS" | "$E" next-free repoPick)" "6"
is   "…and a neighbour repository's lanes take none of this one's positions" \
     "$(printf 'repoNb-foo-1\nrepoNb-foo-2\n' | "$E" next-free repoNb)" "1"
is   "…while its own, under the same names, are taken as they always were" \
     "$(printf 'repoNb-1\nrepoNb-foo-2\nrepoNb-3a\n' | "$E" next-free repoNb)" "2"

# ------------------------------------------------- the listing, and no question
#
# CLAUSE (i-3): with no terminal on stdin the word LISTS, SUGGESTS and ASKS
# NOTHING. An agent's stdin is not a terminal, and every agent on this estate
# reads this output rather than answering it — so this is the form the estate
# itself meets, and it is run first.
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$LANE" </dev/null
is    "a bare lane inside a checkout exits 0" "$rc" 0
has   "…heading its available lanes" "$out" "AVAILABLE"
has   "…with the parked one numbered" "$out" "1  repoPick-1"
has   "…naming its recorded profile and directory" "$out" "team-05a"
has   "…heading the lanes that are LIVE HERE" "$out" "LIVE HERE"
has   "…saying where the one in this session is, in clause (i-1)'s words" "$out" "window 3 of this session"
has   "…and that the other is in a detached session" "$out" "detached session detsess"
has   "…heading the lanes bound elsewhere" "$out" "BOUND ELSEWHERE"
has   "…naming the workstation that holds it" "$out" "Raven"
hasnt "…while a CLOSED lane is hidden from the pick entirely (Amendment 19)" "$out" "repoPick-5"
hasnt "…and no question was asked" "$out$err" "which?"
has   "…saying in terms why nothing was asked" "$out" "stdin is not a terminal"
has   "…and offering the acts filled in, which is what an agent reads" "$out" "lane-start repoPick 6"
# THE SAME ROWS AS A READ STILL SHOW THE CLOSED LANE, because `lanes` is the
# read and this is a pick.
run env LANES_NO_FETCH=1 "$LANES_CMD" --prefix repoPick </dev/null
has   "…while \`lanes\` still carries the closed lane, because that is the READ" "$out" "repoPick-5"
has   "…and its footer offers the same next free position the pick does" "$out" "next free position:  6"
has   "…and points at the word that binds one" "$out" "pick one:            lane"

# ------------------------------------------------------- one question, one answer
if [ "$HAVE_PTY" = 0 ]; then
  skip "the numbered pick asks one question on a terminal" "$NO_PTY_WHY"
else
  : > "$FAKE_PCLAUDE_LOG"
  lane_pick 1 env -C "$PICK_DIR" "$LANE"
  is    "answering with the number of an AVAILABLE lane exits 0" "$rc" 0
  has   "…having asked exactly one question" "$out" "which? [1-"
  has   "…which offers the new-lane answer with the position filled in" "$out" "f = a new lane at the next free position (repoPick-6)"
  has   "…and the launch goes through the LAUNCHER, in the lane's own directory and profile" \
        "$(cat "$FAKE_PCLAUDE_LOG")" "argv=--lane repoPick-1 team-05a"
  has   "…cd-ing there first (Evidence 3)" "$(cat "$FAKE_PCLAUDE_LOG")" "cwd=$PICK_DIR"
  # A LANE LIVE IN THIS SESSION IS SELECTED AND NEVER STARTED AGAIN (clause (h)).
  : > "$LANE_TMUX_LOG"; : > "$FAKE_PCLAUDE_LOG"
  lane_pick 3 env -C "$PICK_DIR" "$LANE"
  is    "answering with a lane LIVE in this very session exits 0" "$rc" 0
  has   "…selecting its window, the target SESSION-QUALIFIED so tmux picks nothing" \
        "$(cat "$LANE_TMUX_LOG")" "select-window -t picksess:@31"
  hasnt "…and moving nothing, because the window is already here" "$(cat "$LANE_TMUX_LOG")" "move-window"
  is    "…launching NOTHING: an attach is never a second process" "$(cat "$FAKE_PCLAUDE_LOG")" ""
  # AND ONE IN A DETACHED SESSION IS MOVED HERE AND SELECTED — the two acts
  # measured by hand on 2026-09-14.
  : > "$LANE_TMUX_LOG"; : > "$FAKE_PCLAUDE_LOG"
  lane_pick 4 env -C "$PICK_DIR" "$LANE"
  is    "answering with a lane live in a DETACHED session exits 0" "$rc" 0
  has   "…moving its window into this session by its @id, never by an index" \
        "$(cat "$LANE_TMUX_LOG")" "move-window -a -s detsess:@32"
  has   "…and selecting it in THIS session, which is where the move put it" \
        "$(cat "$LANE_TMUX_LOG")" "select-window -t picksess:@32"
  is    "…and launching nothing here either" "$(cat "$FAKE_PCLAUDE_LOG")" ""
  # BOUND ELSEWHERE IS A REFUSAL NAMING WHERE, until #38's act 4 exists.
  : > "$LANE_TMUX_LOG"; : > "$FAKE_PCLAUDE_LOG"
  lane_pick 5 env -C "$PICK_DIR" "$LANE"
  is    "answering with a lane bound ELSEWHERE refuses with 2" "$rc" 2
  has   "…naming the workstation it is bound on" "$out" "bound on Raven"
  has   "…and the act, which is clause (c)'s handoff and not a launch" "$out" "HANDOFF"
  has   "…saying the request itself does not exist yet" "$out" "act 4 and does not exist yet"
  is    "…launching nothing at all" "$(cat "$FAKE_PCLAUDE_LOG")" ""
  is    "…and touching no tmux either" "$(cat "$LANE_TMUX_LOG")" ""
  # `f` IS A NEW LANE AT THE NEXT FREE POSITION, which is `lane-start`'s act and
  # is printed here rather than run, so the register is left as this section
  # found it.
  : > "$FAKE_PCLAUDE_LOG"
  lane_pick f env -C "$PICK_DIR" "$LANE" --dry-run
  is    "answering \`f\` exits 0" "$rc" 0
  has   "…naming the lane it would open" "$out" "a new lane at repoPick-6"
  has   "…and the act, which is lane-start at that position" "$out" "lane-start repoPick 6"
  is    "…launching nothing under --dry-run" "$(cat "$FAKE_PCLAUDE_LOG")" ""
  # …AND `--dir` GOES WITH IT (Copilot round 1 on #45, `lane:710`). The flag is
  # in this word's own parser and `lane-start` takes the same one, so dropping
  # it here would open the new lane in a checkout nobody named — Evidence 3's
  # silent loss, at the one moment a lane is being created.
  : > "$FAKE_PCLAUDE_LOG"
  PICK_DIR_R="$(cd -- "$PICK_DIR" 2>/dev/null && pwd -P || printf '%s' "$PICK_DIR")"
  lane_pick f env -C "$PICK_DIR" "$LANE" --dry-run --dir "$PICK_DIR"
  is    "answering \`f\` with a --dir exits 0" "$rc" 0
  has   "…handing that directory to lane-start, resolved" "$out" "--dir $PICK_DIR_R"
  has   "…and still at the next free position" "$out" "repoPick 6"
  # …AND `f` READS THE POSITION'S OWN STATUS (Copilot round 3 on #45,
  # `lane:751`). `|| :` discarded it, so a read that FAILED after printing
  # digits handed those digits to the validation below and opened a lane at a
  # position this estate may well have taken.
  : > "$FAKE_CLAUDE_LOG"
  lane_pick f env -C "$PICK_DIR" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/nfbroke" "$LANE" --dry-run
  is    "answering \`f\` where the position read FAILED refuses with 1" "$rc" 1
  has   "…naming the code it got" "$out" "exited 6"
  has   "…saying it will not open a lane at a position it did not get" "$out" "did not get"
  is    "…and starting nothing" "$(cat "$FAKE_CLAUDE_LOG")" ""
  # `q` PICKS NONE, AND THAT IS NOT A FAILURE.
  : > "$LANE_TMUX_LOG"; : > "$FAKE_PCLAUDE_LOG"
  lane_pick q env -C "$PICK_DIR" "$LANE"
  is    "answering \`q\` exits 0" "$rc" 0
  has   "…saying nothing was picked" "$out" "nothing picked"
  is    "…and doing nothing" "$(cat "$FAKE_PCLAUDE_LOG")$(cat "$LANE_TMUX_LOG")" ""
  # AN ANSWER THAT IS NOT ONE OF THE CHOICES IS A REFUSAL AND NEVER A RE-ASK: one
  # answer is read, and a process that holds the terminal for a second is the
  # thing ratified decision 3 refused.
  : > "$FAKE_PCLAUDE_LOG"
  lane_pick 99 env -C "$PICK_DIR" "$LANE"
  is    "a number outside the list refuses with 2" "$rc" 2
  has   "…saying what the range was" "$out" "is not in 1-"
  has   "…and that nothing is waiting now" "$out" "nothing is waiting"
  is    "…launching nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""
  lane_pick zzz env -C "$PICK_DIR" "$LANE"
  is    "…and an answer that is not a number at all refuses the same way" "$rc" 2
  has   "…naming what was typed" "$out" "'zzz' is not one of the choices"
  # --switch IS THE OTHER ATTACH, for a person who wants the client moved rather
  # than the window.
  : > "$LANE_TMUX_LOG"
  lane_pick 4 env -C "$PICK_DIR" "$LANE" --switch
  is    "--switch exits 0 on a lane in another session" "$rc" 0
  has   "…switching the client to that session" "$(cat "$LANE_TMUX_LOG")" "switch-client -t detsess"
  has   "…naming the WINDOW in the switch itself, so no client can move it in between" \
        "$(cat "$LANE_TMUX_LOG")" "switch-client -t detsess:@32"
  hasnt "…and moving no window" "$(cat "$LANE_TMUX_LOG")" "move-window"
fi

# ------------------------------------------------- `lane <name>` on each branch
#
# The same three branches, reached by NAME rather than by number: one dispatch,
# so a lane picked and a lane named cannot take different paths.
: > "$LANE_TMUX_LOG"; : > "$FAKE_PCLAUDE_LOG"
run env PATH="$LANEBIN_PATH" "$LANE" repoPick-2 </dev/null
is    "lane <name> on a lane LIVE in this session exits 0" "$rc" 0
has   "…selecting its window and nothing else" "$(cat "$LANE_TMUX_LOG")" "select-window -t picksess:@31"
is    "…and launching nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""
: > "$LANE_TMUX_LOG"
run env PATH="$LANEBIN_PATH" "$LANE" repoPick-4 </dev/null
is    "lane <name> on a lane bound elsewhere refuses with 2" "$rc" 2
has   "…naming where it is bound" "$err" "bound on Raven"
is    "…and touching nothing" "$(cat "$LANE_TMUX_LOG")" ""
# AND THE CONTAINER NOTICE REACHES THIS BRANCH, WHICH IS THE ONE THAT NEEDS IT
# MOST. With no `$LANES_WORKSTATION` inside a container the workstation is the
# CONTAINER'S id, so NO row is this workstation's — and the partition then files
# a person's OWN lane under BOUND ELSEWHERE and refuses it by naming a machine
# they are sitting at. The listing has carried the sentence since it was
# written; `lane <name>` reaches this same refusal WITHOUT passing through the
# listing, so a notice printed only beneath the rows never reaches the person
# who typed the name. `repoPick-7` is a binding of THIS host, which is exactly
# the row the unset seam turns into somebody else's.
run env -u LANES_WORKSTATION LANES_IN_CONTAINER=1 PATH="$LANEBIN_PATH" "$LANE" repoPick-7 </dev/null
is    "a lane of THIS host refuses as bound elsewhere once the seam is unset" "$rc" 2
has   "…naming the workstation its row carries" "$err" "bound on Eagle"
has   "…and saying WHY this host is not that workstation" "$err" "LANES_WORKSTATION"
has   "…in the one sentence its own writers refuse with" "$err" "is the CONTAINER"
has   "…naming the launcher whose job the value is" "$err" "launcher"
hasnt "…and never the workstation: key R-A11-14 rejected by name" "$err" "workstation: "
# SAID ONCE PER RUN AND NEVER ONCE PER SURFACE: one run can reach both the
# listing and this branch, and a person who picked a number out of a listing
# that had already explained itself does not need the paragraph twice.
is    "…and the sentence is said once, not once for every surface that wants it" \
      "$(printf '%s' "$out$err" | tr -d '\r\n' | grep -o 'is the CONTAINER' | wc -l | tr -d ' ')" "1"
# AND IT IS SILENT WHERE THE SEAM ANSWERED, so the notice means what it says.
run env PATH="$LANEBIN_PATH" "$LANE" repoPick-4 </dev/null
hasnt "an ordinary elsewhere refusal carries no container notice at all" "$err" "LANES_WORKSTATION"

# AND A READ THIS COMMAND COULD NOT CAPTURE IS NOT A PROOF EITHER (Copilot round
# 3 on #45, `lane:322`). With no writable `$TMPDIR` the helper's notes go
# straight to the terminal and cannot be read back, so whether the liveness
# records answered is UNKNOWN from here — and unknown is not "the proof was
# made". Three states, not two.
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX TMPDIR="$SANDBOX/no-such-tmpdir" PATH="$LANEBIN_PATH" "$LANE" repoPick-7 </dev/null
is    "a binding refuses where this command could not read whether the proof was made" "$rc" 2
has   "…saying the notes could not be read back" "$err" "no temporary file could be made"
has   "…and that the answer is UNKNOWN rather than absent" "$err" "UNKNOWN from here"
is    "…launching nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""
# …AND A `PAUSED` LANE IS NO EXCEPTION TO IT (Copilot round 4, `lane:560`): its
# own last line is a LINE, and the proof is the read that did not happen.
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX TMPDIR="$SANDBOX/no-such-tmpdir" PATH="$LANEBIN_PATH" "$LANE" repoPick-1 </dev/null
is    "…and a PAUSED lane refuses on the unread state as well" "$rc" 2
has   "…in that state's own words" "$err" "no temporary file could be made"
is    "…launching nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""

# THE PICK SAYS WHY `f` IS NOT OFFERED (Copilot round 3 on #45, `lane:960`).
# `|| :` collapsed every status of the next-free read and the answer simply
# vanished from the question, which is a listing with an action missing and
# nothing on screen about it — the defect `lanes`'s footer had one file over.
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/nfold" "$LANE" </dev/null
is    "the pick still lists where the next-free read is MISSING" "$rc" 0
has   "…with the rows" "$out" "repoPick-1"
has   "…saying in terms that \`f\` is not offered" "$out" "is not offered"
has   "…and naming the act that brings it back" "$out" "openRepoTools --install"
hasnt "…never offering a position it did not get" "$out" "lane-start repoPick"
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/nfbroke" "$LANE" </dev/null
is    "…and where that read FAILED it still lists" "$rc" 0
has   "…saying so with the code it got" "$out" "exited 6"
hasnt "…and never calls a failed read an un-upgraded workstation" "$out" "predates lane-collision-protocol Amendment 18"
# A PROFILE CANNOT BE HANDED TO AN ATTACH, because an attach starts nothing.
run env PATH="$LANEBIN_PATH" "$LANE" repoPick-2 team-09z </dev/null
is    "lane <name> <profile> on a LIVE lane refuses rather than attaching under another name" "$rc" 2
has   "…saying an attach starts nothing" "$err" "an attach starts nothing"
has   "…and naming the act that does change a live lane's account" "$err" "/lane-swap"
# A CLOSED LANE IS NO ANSWER (8) AND NEVER A LAUNCH.
: > "$FAKE_PCLAUDE_LOG"
run env PATH="$LANEBIN_PATH" "$LANE" repoPick-5 </dev/null
is    "lane <name> on an ENDED lane exits 8" "$rc" 8
has   "…saying its last act was its last" "$err" "last act was its last"
is    "…and launching nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""

# THE WINDOW IS MATCHED BY ITS ID *AND* ITS SESSION NAME, which is the fence
# clause (b) states for `window-lane` and the reason it exists: tmux reissues
# `@` ids from `@0` when its server is replaced — measured on Eagle on
# 2026-09-13, 0 of 5 recorded windows resolving — so attaching on the id alone
# puts a person in whatever pane has since been given it.
: > "$LANE_TMUX_LOG"
run env PATH="$LANEBIN_PATH" LANE_TMUX_WINDOWS="$(printf '@31\tsomebody-elses-session\t0\t1\n')" "$LANE" repoPick-2 </dev/null
is    "a recorded window whose id now names ANOTHER session is a refusal" "$rc" 2
has   "…naming the session the id is in now and the one the record names" "$err" "is in session somebody-elses-session and the record says picksess"
has   "…and the act that is still safe to type" "$err" "tmux attach -t picksess"
is    "…having attached to nothing" "$(cat "$LANE_TMUX_LOG")" ""
: > "$LANE_TMUX_LOG"
run env PATH="$LANEBIN_PATH" LANE_TMUX_WINDOWS="" "$LANE" repoPick-2 </dev/null
is    "…and an id that names no window at all is the same refusal" "$rc" 2
has   "…saying so" "$err" "names no window on this tmux server at all"
is    "…and attaches to nothing" "$(cat "$LANE_TMUX_LOG")" ""

# OUTSIDE TMUX THE ATTACH IS `tmux attach -t <session>:<@id>`, with the lane's
# own window selected FIRST so the terminal lands on the lane rather than on
# whichever window that session left current — and the WINDOW named in the
# attach itself (Copilot round 6 on #45, `lane:708`), because a select and an
# attach are two acts and a window that closes between them would leave the
# second one on another lane. Measured on tmux 3.4: `attach -t <session>:<@id>`
# attaches AND makes that window current in one act, and refuses outright for a
# window that is not in that session.
: > "$LANE_TMUX_LOG"
run env -u TMUX PATH="$LANEBIN_PATH" "$LANE" repoPick-3 </dev/null
is    "lane <name> outside tmux exits 0 on a live lane" "$rc" 0
has   "…selecting the lane's own window first, in the session the record names" \
      "$(cat "$LANE_TMUX_LOG")" "select-window -t detsess:@32"
has   "…and then attaching to its session" "$(cat "$LANE_TMUX_LOG")" "attach -t detsess"
has   "…naming the WINDOW in that attach too, so no act between the two can land elsewhere" \
      "$(cat "$LANE_TMUX_LOG")" "attach -t detsess:@32"

# A SELECT THAT FAILED IS PART OF THE FENCE AND NOT A COURTESY (Copilot round 1
# on #45, `lane:610`). The id resolved at the check above and is gone by the
# time it is selected — a window closed in the half-second between — and going
# on would attach to whatever window that session left CURRENT, which is
# another lane. That is the one thing the id-AND-session fence exists to stop,
# so the swallowed failure is a refusal.
: > "$LANE_TMUX_LOG"
run env -u TMUX PATH="$LANEBIN_PATH" LANE_TMUX_SELECT_FAIL=1 "$LANE" repoPick-3 </dev/null
is    "a select-window that FAILED refuses instead of attaching to the current window" "$rc" 2
has   "…saying the window could not be selected" "$err" "could not be selected"
has   "…and why going on would be wrong" "$err" "another lane"
is    "…having attached to nothing at all" "$(cat "$LANE_TMUX_LOG")" ""
# THE SAME FENCE ON THE MOVE, where the window has already been brought here:
# the move is logged and the select still refuses rather than leaving the
# terminal on a window nobody asked for.
: > "$LANE_TMUX_LOG"
run env PATH="$LANEBIN_PATH" LANE_TMUX_SELECT_FAIL=1 "$LANE" repoPick-3 </dev/null
is    "…and so does the one after a move-window" "$rc" 2
has   "…saying what had already been done" "$err" "moved here out of detsess"
has   "…and naming the session the window is in NOW, not the one it came from" \
      "$err" "could not be selected in session picksess"
hasnt "…so it never sends a person back to a source that may have closed" "$err" "tmux attach -t detsess"
has   "…and the move itself is still in the log, because it happened" "$(cat "$LANE_TMUX_LOG")" "move-window"

# A BINDING IS AVAILABLE BECAUSE THIS HOST PROVED IT DEAD, AND AN UNREAD
# SESSION RECORD IS NOT THAT PROOF (Copilot round 1 on #45, `lane:777`).
# `lanes_rows` says on STDERR — and goes on answering — that this workstation's
# session records could not be read, in which case the STATE column is the
# LOG'S VERB ALONE and a lane that is LIVE shows as IDLE. Launching one is a
# second process on a running lane, which is the collision clause (h) is about.
cat > "$SANDBOX/livewarn" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  lanes) printf "lanes-edit: this workstation's session records could not be read, so the STATE column below is the LOG's verb alone\n" >&2 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/livewarn"
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX PATH="$LANEBIN_PATH" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/livewarn" "$LANE" repoPick-7 </dev/null
is    "a BINDING refuses where the liveness read did not answer" "$rc" 2
has   "…saying nothing proved that lane dead" "$err" "PROVED that lane dead"
has   "…and naming the read that says what is actually running" "$err" "live-holder"
is    "…launching nothing at all" "$(cat "$FAKE_PCLAUDE_LOG")" ""
# …AND SO DOES A `PAUSED` ROW, WHICH IS THE ONE MOST LIKELY TO BE RUNNING
# (Copilot round 4 on #45, `lane:560`). Round 1 passed `PAUSED` through on the
# reading that a lane parked by its own last line needs no proof — but the
# sentence this very refusal is reacting to says *"a lane that is live may show
# as IDLE OR PAUSED here"* (`lanes-edit.sh:4628`), because a live record beats
# the log's last verb and the verb is all that is left when the read fails
# (`lanes-edit.sh:4700`). `/lane-swap` writes the PAUSED line while its session
# is still on screen. The exception was a hole in the fence at its widest point.
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX PATH="$LANEBIN_PATH" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/livewarn" "$LANE" repoPick-1 </dev/null
is    "…and a PAUSED lane refuses too, on the same unread proof" "$rc" 2
has   "…saying a live lane shows as IDLE or PAUSED when the proof is missing" "$err" "IDLE or PAUSED"
has   "…naming /lane-swap, which writes that line while its session is still up" "$err" "/lane-swap"
is    "…launching nothing either" "$(cat "$FAKE_PCLAUDE_LOG")" ""

# ---------------------------------------------------------- `--all`, grouped
run env PATH="$LANEBIN_PATH" "$LANE" --all </dev/null
is    "lane --all exits 0" "$rc" 0
has   "…carrying this repository's lanes" "$out" "repoPick-1"
has   "…and another repository's, which is what --all asks for" "$out" "repoA11-1"
has   "…grouped by repository under each heading" "$out" "$(printf '\n  repoPick\n')"
hasnt "…and no next-free position, because no one repository is in scope" "$out" "lane-start repoPick"
run env PATH="$LANEBIN_PATH" "$LANE" --all repoPick-1 </dev/null
is    "--all and a lane name are two questions, and saying so is the 64" "$rc" 64

# ------------------------------------------------ clause (i-4): the alias
#
# *"Bare `lane-start` — no repository, no position — is an alias of `lane`, so
# clause (i) as ruled still holds and there is one implementation."* It renders
# nothing of its own: it `exec`s the word, because the launcher `exec`s IT.
: > "$FAKE_CLAUDE_LOG"
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$START" </dev/null
is    "a bare lane-start exits 0, where it used to refuse with 2" "$rc" 0
has   "…saying in one line that this is \`lane\`" "$err" "this is \`lane\`"
has   "…and printing that word's listing rather than one of its own" "$out" "AVAILABLE"
has   "…numbered, which is the pick" "$out" "1  repoPick-1"
is    "…and launching no session at all" "$(cat "$FAKE_CLAUDE_LOG")" ""

# AND THE OPTIONS IT WAS HANDED ARE NOT DROPPED ON THE FLOOR (Copilot round 1 on
# #45, `lane-start:661`). This command's parser has already taken them, and an
# `exec` carrying none of them turned `--no-launch` — a flag whose whole promise
# is that nothing starts — into an interactive pick that launches.
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$START" --no-launch </dev/null
is    "bare lane-start REFUSES a flag it would otherwise drop" "$rc" 2
has   "…naming the flag" "$err" "--no-launch"
has   "…and saying what the bare word is" "$err" "is \`lane\`"
has   "…with the form that does take it, filled in" "$err" "<repo> <n> --no-launch"
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$START" --estate x --yes </dev/null
is    "…and names every one of them, not the first" "$rc" 2
has   "…the one" "$err" "--yes"
has   "…and the other" "$err" "--estate"
# …AND THE VALUE GOES WITH THE FLAG THAT TOOK ONE (Copilot round 4 on #45,
# `lane-start:690`). `--estate x --yes` printed `--estate --yes`, whose
# `--estate` swallows the `--yes` and names an estate `--yes`: a suggested
# command that cannot be run is not a suggestion, it is a second refusal
# waiting.
has   "…with the VALUE the flag was given, so the line can actually be typed" "$err" "--estate x"
hasnt "…and never the flag with the next flag as its value" "$err" "--estate --yes"
# …AND QUOTED THE WAY THE SHELL WILL READ IT BACK (Copilot round 7 on #45,
# `lane-start:698`): a value with a space printed bare is two words when it is
# typed again, which is a suggested command that does something else.
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$START" --estate 'team blue' </dev/null
is    "…and a value with a space in it is still one value" "$rc" 2
# THE ASSERTION IS THE CONTRACT AND NOT ONE SPELLING OF IT. A shell has several
# correct quotings of `team blue` — `'team blue'` and `team\ blue` are both one
# word when they are read back — and `lane-start`'s own `quoted` has been each
# of them: `printf '%q '` until Amendment 17's #47, a POSIX single-quote loop
# since. What must hold is that the value is quoted AT ALL, in a form this shell
# reads as one word, and never bare.
est_q=""
case "$err" in
  *"--estate 'team blue'"*) est_q=quoted ;;
  *'--estate team\ blue'*) est_q=quoted ;;
esac
is    "…quoted the way the shell reads it back, in whichever spelling this file's quoter uses" "$est_q" "quoted"
hasnt "…never bare, which would be two words on the next line someone types" "$err" "--estate team blue"
is    "…and each of those two spellings IS one word when a shell reads it back" \
      "$( (eval "set -- 'team blue'"; printf '%s' "$#"); (eval 'set -- team\ blue'; printf '%s' "$#") )" "11"
if [ "$HAVE_PTY" = 0 ]; then
  skip "bare lane-start forwards the flags lane has" "$NO_PTY_WHY"
else
  # …WHILE THE TWO `lane` ALSO HAS ARE FORWARDED. `--dry-run` is proved by what
  # the AVAILABLE branch does with it: the act printed instead of performed.
  : > "$FAKE_PCLAUDE_LOG"
  lane_pick 1 env -C "$PICK_DIR" "$START" --dry-run
  is    "bare lane-start --dry-run exits 0" "$rc" 0
  has   "…having reached lane's own pick" "$out" "which? [1-"
  has   "…and carried the flag, so the act is printed and not performed" "$out" "--dry-run: nothing was launched"
  is    "…launching nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""
fi

# -------------------------------------- the footer when the helper is older
#
# A `lanes-edit.sh` WITH NO `next-free` IS NOT A NEXT FREE POSITION OF 1
# (Amendment 7(d)). `lanes` offered `lane-start <repo> 1` out of a read that
# never answered, which is a position this estate may well have taken.
run env LANES_NO_FETCH=1 REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/nfold" "$LANES_CMD" --prefix repoPick </dev/null
is    "lanes still lists where the next-free read is missing" "$rc" 0
has   "…with the rows" "$out" "repoPick-1"
hasnt "…and never offers a position it did not get" "$out" "next free position:"
has   "…saying which act brings it back" "$out" "openRepoTools --install"

# AND A READ THAT *FAILED* IS NOT AN UN-UPGRADED WORKSTATION (Copilot round 1 on
# #45, `lanes:432`). `|| :` made every status of that read the same status, and
# the footer then told a person to take the install for a read that had broken:
# the fail-closed family's own defect, one rung down.
run env LANES_NO_FETCH=1 REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/nfbroke" "$LANES_CMD" --prefix repoPick </dev/null
is    "lanes still lists where the next-free read FAILED" "$rc" 0
has   "…with the rows" "$out" "repoPick-1"
hasnt "…offering no position it did not get, here either" "$out" "next free position:"
has   "…naming the code the read actually gave" "$out" "exited"
hasnt "…and never calling a failed read an un-upgraded workstation" "$out" "predates lane-collision-protocol Amendment 18"

# ---- THE TWO ACTS THAT CAN FAIL *AFTER* THE FENCE HAS PASSED ---------------
#
# THE MOVE IS SPELLED WITH THE `@id` AND THE SOURCE IS FENCED WITH IT (Copilot
# round 4 on #45, `lane:715`). The index was read one command before it was
# used, and a window that closes in between gives its index to the next one.
# MEASURED, tmux 3.4 on a private socket, 2026-09-14: with `w3` at `src:2`,
# killing it and opening another window at that index and then `move-window -a
# -s src:2` moved the INTRUDER and exited 0 — the wrong window, in this
# session, silently — while `move-window -a -s src:@2` refused with `can't find
# window: @2` and exit 1. So the failure is tmux's own fence doing its work, and
# this word refuses on it rather than selecting into whatever came back.
: > "$LANE_TMUX_LOG"; : > "$FAKE_PCLAUDE_LOG"
run env PATH="$LANEBIN_PATH" LANE_TMUX_MOVE_FAIL=1 "$LANE" repoPick-3 </dev/null
is    "a move-window that FAILED is a refusal and never a select afterwards" "$rc" 2
has   "…naming the session the window could not be moved out of" "$err" "could not be moved out of session detsess"
has   "…saying nothing was moved and this terminal is where it was" "$err" "NOTHING was moved"
is    "…having touched nothing at all, the select included" "$(cat "$LANE_TMUX_LOG")" ""
is    "…and launching nothing either" "$(cat "$FAKE_PCLAUDE_LOG")" ""

# AND UNDER `--switch` THE SELECT COMES FIRST (Copilot round 3 on #45,
# `lane:687`). `switch-client` then `select-window` leaves a client that lost
# the race sitting in the target session's current window — another lane, and
# this terminal already in it. `select-window` names the session it acts on and
# needs no client there, so the lane's own window is made current BEFORE the
# client moves, and a select that fails costs nothing.
: > "$LANE_TMUX_LOG"
run env PATH="$LANEBIN_PATH" LANE_TMUX_SELECT_FAIL=1 "$LANE" --switch repoPick-3 </dev/null
is    "--switch with a select that FAILED refuses with 2" "$rc" 2
has   "…saying the window could not be selected" "$err" "could not be selected in session detsess"
hasnt "…and the client was never switched, because the select is the first act" \
      "$(cat "$LANE_TMUX_LOG")" "switch-client"
# …AND A SWITCH THAT FAILED AFTER A SELECT THAT WORKED IS ALSO A REFUSAL, in
# the words of the half that did happen: that session is on the lane now, and
# this client simply did not move.
: > "$LANE_TMUX_LOG"
run env PATH="$LANEBIN_PATH" LANE_TMUX_SWITCH_FAIL=1 "$LANE" --switch repoPick-3 </dev/null
is    "…and a switch-client that FAILED refuses with 2 as well" "$rc" 2
has   "…naming the act that failed, window and all" "$err" "switch-client -t detsess:@32\` then failed"
has   "…and the half that worked, which is the lane's own window selected there" \
      "$(cat "$LANE_TMUX_LOG")" "select-window -t detsess:@32"

# ---- A LANE WHOSE NAME IS NOT `<repo>-<n>` IS STARTED BY ONE ARGUMENT -------
#
# Copilot round 4 on #45, `lane:595`. The no-directory refusal built its remedy
# as `<repo> <position>`, and a `--verbatim` lane has neither: `nav-rail-audit`
# is a row like any other (`lane-start:601` takes it as ONE argument beside a
# `--dir`), and `lane-start --dir <path> nav-rail-audit <n>` would open
# `nav-rail-audit-<n>` — A DIFFERENT LANE. A refusal whose remedy records the
# directory of another lane is worse than one that says nothing.
VERB_ID="dddd0008-8888-4000-8000-dddd00088888"
add_seed_row "| \`nav-rail-audit\` | harness \`$VERB_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/browser/ui.md | ACTIVE |"
{ printf '# lane nav-rail-audit — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane nav-rail-audit, session %s@Eagle, 2026-09-12T08:00:00Z, lane:nav-rail-audit → home opensoft/browser; estate browser; profile team-05a\n' "$VERB_ID"
} > "$LOGD/nav-rail-audit.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a --verbatim lane with a profile and no recorded directory"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX PATH="$LANEBIN_PATH" "$LANE" nav-rail-audit </dev/null
is    "a --verbatim lane with no recorded directory refuses with 2" "$rc" 2
has   "…naming the ONE-ARGUMENT form that records it for THIS lane" \
      "$err" "lane-start --dir <the lane's checkout> nav-rail-audit"
hasnt "…and never a position appended to a name that has none" "$err" "nav-rail-audit <n>"
is    "…launching nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""

# ---- AND `env -C` IS NOT A GNU-ONLY OPTION THIS SUITE CANNOT USE -----------
#
# Round 4 read this section's `env -C <dir>` invocations as a macOS failure —
# *"`env -C` is a GNU `env` option, not available in macOS's /usr/bin/env … the
# macOS Bash 3.2 job will fail before exercising these lane cases"*. It does
# not. The macOS job has run these very cases GREEN — job 104128188482 on
# `fce18d5`: `ok a bare lane inside a checkout exits 0` and `ok answering with
# the number of an AVAILABLE lane exits 0`, both of them `env -C` forms, neither
# of which can exit 0 and carry a listing if `env` had refused the flag — and
# `main` has carried four more of them since Amendment 11. Asserted here as
# well, directly and on every platform, because a decline that is argued rather
# than measured is one the next round makes again.
is   "this platform's env takes the -C that every pick case in this section passes it" \
     "$(env -C "$LOGD" /bin/pwd -P 2>/dev/null)" "$(cd -- "$LOGD" && pwd -P)"
is   "…and exits 0 doing it, so a case that used it ran the command and not the usage" \
     "$(env -C "$LOGD" true >/dev/null 2>&1; echo $?)" 0

# ---- A READ THAT PRINTED DIGITS AND THEN FAILED IS STILL A READ THAT FAILED --
#
# Copilot round 5 on #45, `lane:1000` and `lanes:441`. Round 3 closed this in
# the `f` ANSWER (`go_new`, `lane:751`) and left it open in the two surfaces that
# OFFER `f`: both captured the status and then decided on the TEXT, and text
# from a failed read passes a shape test on its own output. `nfbroke` prints
# nothing, so neither surface had ever met the case. `nfpartial` prints a
# position and exits 6 — the position of a read that did not answer.
cat > "$SANDBOX/nfpartial" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  next-free) printf '3\n'; printf 'lanes-edit: died after printing\n' >&2; exit 6 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/nfpartial"
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/nfpartial" "$LANE" </dev/null
is    "the pick lists where next-free printed a position and THEN failed" "$rc" 0
has   "…with the rows" "$out" "repoPick-1"
has   "…saying \`f\` is not offered" "$out" "is not offered"
has   "…naming the code that read actually gave" "$out" "exited 6"
hasnt "…and never offering the position it printed before it died" "$out" "lane-start repoPick 3"
hasnt "…which is not in the question either" "$out$err" "f = a new lane"
run env LANES_NO_FETCH=1 REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/nfpartial" "$LANES_CMD" --prefix repoPick </dev/null
is    "…and the lanes footer answers the same way about the same read" "$rc" 0
hasnt "…offering no next free position out of it" "$out" "next free position:"
has   "…and naming the code instead" "$out" "exited 6"
hasnt "…never the digits that read printed before it failed" "$out" "lane-start repoPick 3"

# ---- THE ACTS A NO-TERMINAL RUN PRINTS CARRY THE `--dir` IT WAS GIVEN -------
#
# Copilot round 5 on #45, `lane:1030`. The `f` ANSWER has carried `--dir` since
# round 1 (`lane:710`); the line PRINTED for an agent to type dropped it, which
# opens the new lane in whatever checkout the reader happens to be standing in.
# One surface performed the act and the other printed it.
PICK_DIR_P="$(cd -- "$PICK_DIR" && pwd -P)"
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$LANE" --dir "$PICK_DIR" </dev/null
is    "a no-terminal listing with --dir exits 0" "$rc" 0
has   "…printing the new-lane act WITH that directory, resolved" "$out" "lane-start --dir $PICK_DIR_P repoPick"
has   "…and the named-lane act with it too, because the flag means the same there" "$out" "lane --dir $PICK_DIR_P <name>"

# ---- AND THE `AVAILABLE` HEADING SAYS WHAT AN UNREAD PROOF COSTS ------------
#
# Copilot round 5 on #45, `lanes-edit.sh:4829`. `lane-groups` groups a local row
# that is not LIVE as available — out of the STATE column, which is the log's
# verb alone when the session records could not be read. Every row under that
# heading is then unproven and `go_available` refuses each of them, so a listing
# that numbered them without a word would be asking a person to pick an answer
# this command has already decided to refuse.
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/livewarn" "$LANE" </dev/null
is    "the pick still lists where the liveness read did not answer" "$rc" 0
has   "…with the available rows on screen, because a person still needs to see them" "$out" "repoPick-1"
has   "…and says in terms that none of them can be launched from here" "$out" "NOTHING above can be launched"
has   "…naming the read that says what is actually running" "$out" "live-holder"
has   "…and that an attach is unaffected, because it starts nothing" "$out" "an attach starts"
# …AND IT IS SILENT WHERE THE PROOF *WAS* MADE, so the paragraph means what it says.
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$LANE" </dev/null
hasnt "…while an ordinary listing carries no such paragraph at all" "$out" "NOTHING above can be launched"

# ---- AND AN EMPTY LISTING'S `1` IS THE HELPER'S OWN ANSWER ------------------
#
# Round 6 read the `rc=8` branch of `lanes` — which prints `next free position:
# 1` without calling `next-free` — as a position that "can reuse a position the
# estate already owns" on a workstation whose helper predates the read. It
# cannot. `lane_next_free` (`lanes-edit.sh:4847`) reads ONLY THE ROWS ON STDIN
# and keeps those whose name begins `<repo>-`; the rows it would be handed are
# the ones that listing just found NONE of, and `lanes_rows`' own `--prefix`
# filter keeps every lane whose NAME carries the prefix (its third or-term), so
# an empty filtered listing IS "no lane named `<repo>-<n>` anywhere in this
# register". Routing it through the helper could only add a failure path in
# front of an answer that needs no read: a workstation without `next-free` would
# be refused the one position it can be certain of. Measured here rather than
# argued, both halves, on the same rows.
run env LANES_NO_FETCH=1 "$LANES_CMD" --prefix repoNoSuchAtAll </dev/null
is   "an empty listing exits 8, which is \`no lane of this repository\`" "$rc" 8
has  "…offering the position that follows from no lanes at all" "$out" "next free position:  1"
is   "…which is the helper's own answer over the rows that listing did not find" \
     "$(printf '' | "$E" next-free repoNoSuchAtAll)" "1"
is   "…and the helper says the same when it is handed the empty set explicitly" \
     "$(printf '\n' | "$E" next-free repoNoSuchAtAll)" "1"

# ---- AND EVERY PRINTED ACT IS A LINE THAT CAN BE TYPED BACK ----------------
#
# Copilot round 8 on #45: `lane:612`, `lane:1123`, `lane-start:706`. Three
# surfaces print a command for a person or an agent to run, and each dropped
# something the run it describes would need — a directory with a space in it,
# the `--switch` that makes the attach a switch rather than a move, and the
# `--dir` a bare `lane-start` was handed beside the flag it refused.
#
# THE `cd` IN THE NO-PROFILE REFUSAL, quoted where it is a path. `repoGap-1`
# records a directory with a space, which is a path a person may well have.
GAP_DIR="$HOME/projects/my gap repo"
mkdir -p "$GAP_DIR"
GAP_ID="dddd0010-1010-4000-8000-dddd00101010"
add_seed_row "| \`repoGap-1\` | harness \`$GAP_ID\` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoGap/1.md | ACTIVE |"
{ printf '# lane repoGap-1 — object log (lane-collision-protocol Amendment 7)\n'
  printf 'STARTED — lane repoGap-1, session %s@Eagle, 2026-09-12T08:30:00Z, lane:repoGap-1 → home opensoft/repoGap; estate repoGap; dir "%s"\n' "$GAP_ID" "$GAP_DIR"
} > "$LOGD/repoGap-1.md"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a lane whose recorded directory has a space in it"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX PATH="$LANEBIN_PATH" "$LANE" repoGap-1 </dev/null
is    "a lane with no recorded profile still refuses with 2" "$rc" 2
has   "…and the one line it hands over is QUOTED, so it can be pasted" \
      "$err" "cd $(printf '%q' "$GAP_DIR")"
hasnt "…never bare, which would be two arguments to cd" "$err" "cd $GAP_DIR "
is    "…launching nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""

# `--switch` IS A DIFFERENT ATTACH AND THE PRINTED ACT KEEPS IT.
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$LANE" --switch </dev/null
is    "a no-terminal listing with --switch exits 0" "$rc" 0
has   "…printing the named-lane act WITH the flag that makes it a switch" "$out" "lane --switch <name>"
hasnt "…and never the new-lane act with it, because lane-start has no such flag" "$out" "lane-start --switch"

# AND THE BARE `lane-start` REMEDY CARRIES WHAT IT KEPT, not only what it refused.
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$START" --dir "$PICK_DIR" --estate x </dev/null
is    "bare lane-start with one kept flag and one refused still refuses with 2" "$rc" 2
has   "…naming the refused one" "$err" "--estate x"
has   "…and carrying the kept one into the line it tells a person to type" "$err" "--dir"
has   "…with the checkout they actually named" "$err" "$PICK_DIR"

# ---- AND THE FENCE'S OWN REFUSALS OFFER THE WINDOW, NOT ONLY THE SESSION ----
#
# Copilot round 11 on #45, `lane:499` and `lane:804`. Both refusals ended with
# `tmux attach -t <session>` — the bare session, which lands on whatever that
# session has since made current. That is the outcome the id-AND-session fence
# exists to stop, offered inside the refusal that exists to stop it. The
# qualified form attaches AND selects in one act, or refuses; the bare session
# stays under it, said as what it is.
: > "$LANE_TMUX_LOG"
run env -u TMUX PATH="$LANEBIN_PATH" LANE_TMUX_SELECT_FAIL=1 "$LANE" repoPick-3 </dev/null
is    "a select that FAILED outside tmux still refuses with 2" "$rc" 2
has   "…offering the WINDOW first, which is either the lane or a refusal" "$err" "tmux attach -t detsess:@32"
has   "…and the bare session under it, said as whatever it now holds" "$err" "whatever it now holds"
: > "$LANE_TMUX_LOG"
run env PATH="$LANEBIN_PATH" LANE_TMUX_MOVE_FAIL=1 "$LANE" repoPick-3 </dev/null
is    "…and the move refusal answers the same way" "$rc" 2
has   "…with the window in the line it offers" "$err" "tmux attach -t detsess:@32"

# ---- A RESOLVER THAT *FAILED* IS NOT "THE TYPED SPELLING WILL DO" -----------
#
# Copilot round 11 on #45, `lane:956`. Two statuses are answers: `0`, the row's
# own spelling, and the unknown-subcommand `2` of a helper predating Amendment
# 15, which is the documented fall-through to the estate-wide read. Anything
# else is a read that did not answer, and a lane bound under a spelling nothing
# established is the defect Amendment 15 exists to prevent — taken here in the
# same words the row read, the grouping read and the position read already use.
cat > "$SANDBOX/canonbroke" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  canon-lane) printf 'lanes-edit: simulated failure\n' >&2; exit 5 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/canonbroke"
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX PATH="$LANEBIN_PATH" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/canonbroke" "$LANE" repoPick-1 </dev/null
is    "a canon-lane read that FAILED refuses with 1" "$rc" 1
has   "…naming the code it got" "$err" "exited 5"
has   "…saying a lane name is one name under any case" "$err" "Amendment 15"
has   "…and that nothing was launched or attached" "$err" "Nothing was launched"
is    "…launching nothing, which is the point" "$(cat "$FAKE_PCLAUDE_LOG")" ""
# …WHILE THE HELPER THAT PREDATES THE AMENDMENT IS STILL THE FALL-THROUGH IT
# WAS: `2` with no 15(d) words is an un-upgraded workstation, and the lane binds.
cat > "$SANDBOX/canonold" <<'WRAP'
#!/usr/bin/env bash
case "${1-}" in
  canon-lane) printf "lanes-edit: unknown subcommand 'canon-lane'\n" >&2; exit 2 ;;
esac
exec "$REAL_LANES_EDIT" "$@"
WRAP
chmod +x "$SANDBOX/canonold"
: > "$FAKE_PCLAUDE_LOG"
run env -u TMUX PATH="$LANEBIN_PATH" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/canonold" "$LANE" repoPick-1 </dev/null
is    "…and a helper with no canon-lane at all still binds the lane" "$rc" 0
has   "…through the launcher, as it always did" "$(cat "$FAKE_PCLAUDE_LOG")" "argv=--lane repoPick-1 team-05a"

# ---- THE LAST THREE OF THE SAME THREE FAMILIES ------------------------------
#
# Copilot round 12 on #45: `lane:873`, `lane:1215`, `lane:234`.
#
# `f`'s OWN READ TELLS THE TWO STATUSES APART, as the listing has since round 3:
# an un-upgraded workstation is named as one and sent to the install; a read
# that FAILED is named by its code. Both were "run it by hand" here.
if [ "$HAVE_PTY" = 0 ]; then
  skip "the f answer names an un-upgraded workstation as one" "$NO_PTY_WHY"
else
  : > "$FAKE_PCLAUDE_LOG"
  lane_pick f env -C "$PICK_DIR" REAL_LANES_EDIT="$E" LANES_EDIT="$SANDBOX/nfold" "$LANE" --dry-run
  is    "answering \`f\` where next-free is MISSING refuses with the contract's 2" "$rc" 2
  has   "…saying the workstation predates the addendum rather than that a read broke" "$out" "predates lane-collision-protocol Amendment 18"
  has   "…and naming the one act that fixes it" "$out" "openRepoTools --install"
  is    "…starting nothing" "$(cat "$FAKE_PCLAUDE_LOG")" ""
fi

# AN ANSWER TOO LONG TO BE A POSITION IS NOT ONE, and the length is compared
# BEFORE `$(( 10# ))` gets it: that conversion WRAPS at the shell's integer
# width, so `18446744073709551617` arrives at the range check as `1` and binds a
# lane nobody picked — the wrong-lane outcome every fence in this file stops.
if [ "$HAVE_PTY" = 0 ]; then
  skip "an answer that wraps the shell's integer width is refused" "$NO_PTY_WHY"
else
  : > "$FAKE_PCLAUDE_LOG"; : > "$LANE_TMUX_LOG"
  lane_pick 18446744073709551617 env -C "$PICK_DIR" "$LANE"
  is    "an answer wider than the shell's integers refuses with 2" "$rc" 2
  has   "…saying it is not in the range the question offered" "$out" "is not in 1-"
  is    "…and binding nothing, which is what wrapping would have done" \
        "$(cat "$FAKE_PCLAUDE_LOG")$(cat "$LANE_TMUX_LOG")" ""
fi

# AND AN ARGUMENT THAT WAS GIVEN AND IS EMPTY IS NOT "NO ARGUMENT": `lane ""`
# fell through every `[ -n "$name" ]` below it and became the LISTING — a
# malformed named invocation silently answering a different question.
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$LANE" "" </dev/null
is    "an empty lane name is the contract's 64 and never the listing" "$rc" 64
has   "…saying which argument was empty" "$err" "EMPTY argument"
hasnt "…and never rendering the listing instead" "$out" "AVAILABLE"
run env -C "$PICK_DIR" PATH="$LANEBIN_PATH" "$LANE" --all "" </dev/null
is    "…and the same beside --all" "$rc" 64

echo "== Amendment 13: the row is current state, the log is history =="

# THE CHECKOUT IS COMMITTED FIRST, for the reason the workstation-seam section
# below gives: the cases above leave handoff files uncommitted in the sandbox
# workspace on purpose, and `lanes-edit.sh` REFUSES an object-log write on a
# checkout it cannot rebase. These cases are about the row and the log, so the
# refusal is put out of the way rather than met.
git -C "$WIP" add -A >/dev/null 2>&1
git -C "$WIP" commit -q -m "commit the sandbox's pending handoffs before the Amendment 13 cases" >/dev/null 2>&1 || :
git -C "$WIP" pull -q --rebase origin main >/dev/null 2>&1 || :
git -C "$WIP" push -q origin main >/dev/null 2>&1 || :

A13_ID="aaaa0013-1313-4000-8000-aaaa00131313"
"$E" add-row "| \`repoA13-1\` | harness \`$A13_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoA13/x.md | LIVE · 2026-09-14T00:00:00Z · the row is born in the phrase |" >/dev/null 2>&1

# ---- (a) `set-row-state` REPLACES the cell, and stamps the UTC itself.
run env LANES_LANE=repoA13-1 "$E" set-row-state repoA13-1 "LANDING #29 · CI green; waiting on review"
is    "set-row-state writes the cell" "$rc" 0
a13_row="$(grep '^| `repoA13-1`' "$LANES")"
has   "…the STATE opens it" "$a13_row" "| LANDING #29 · "
has   "…UTC-stamped by the WRITER, never passed in" "$a13_row" "| LANDING #29 · $(date -u +%Y-)"
has   "…and the one line closes it" "$a13_row" " · CI green; waiting on review |"
hasnt "…and what the cell said before is REPLACED, not appended to" "$a13_row" "the row is born in the phrase"
is    "…so the cell is three parts and stays three parts" \
      "$(printf '%s' "$a13_row" | awk -F' \\| ' '{ c = $NF; sub(/ \|$/, "", c); n = split(c, p, / · /); print n }')" 3
is    "…and it is BOUNDED: 240 for the line, plus the state and the instant" \
      "$(printf '%s' "$a13_row" | awk -F' \\| ' '{ c = $NF; sub(/ \|$/, "", c); print (length(c) <= 280 ? "yes" : "no " length(c)) }')" "yes"

run "$E" set-row-state repoA13-1 "BUSY · doing things"
is    "an unknown STATE is refused" "$rc" 2
has   "…naming the seven there are" "$err" "LIVE, PAUSED, LANDING #<n>, LANDED, ENDED, RETIRED, HANDED OFF"
run "$E" set-row-state repoA13-1 "LANDING # · no number"
is    "a LANDING with no PR number is refused — Rule 6 reads this cell" "$rc" 2
a13_long="$(awk 'BEGIN { s = ""; while (length(s) < 241) s = s "x"; print s }')"
run "$E" set-row-state repoA13-1 "LIVE · $a13_long"
is    "a line over the cap is refused" "$rc" 2
has   "…naming the cap ratified decision O1 set" "$err" "the cap is 240"
has   "…and where the rest of it goes" "$err" "log NOTED"
run "$E" set-row-state repoA13-1 "LIVE · a | b"
is    "a line carrying a cell boundary is refused" "$rc" 2
run "$E" set-row-state repoA13-1 "LIVE · one · two"
is    "a line carrying the phrase's own separator is refused" "$rc" 2
run "$E" set-row-state repoA13-1 "LIVE"
is    "a phrase with no line at all is refused" "$rc" 2
is    "…and none of those five refusals touched the row" "$(grep '^| `repoA13-1`' "$LANES")" "$a13_row"

# A ROW WHOSE CELLS ARE NOT UNAMBIGUOUS IS REFUSED, NOT WRITTEN OVER. Seeded as
# it exists in the live register — a literal ` | ` inside a cell — because no
# writer here can create one: `set-row-state` refuses the very line that would.
add_seed_row "| \`repoA13-2\` | harness \`$A13_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoA13/y.md | LIVE · a | b inside the cell |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed a row whose state cell holds a literal ' | '" >/dev/null 2>&1
git -C "$WIP" pull -q --rebase origin main >/dev/null 2>&1 || :
git -C "$WIP" push -q origin main >/dev/null 2>&1
a13_amb="$(grep '^| `repoA13-2`' "$LANES")"
run "$E" set-row-state repoA13-2 "LIVE · this must not be written"
is    "a row with more than six ' | ' separators is refused" "$rc" 2
has   "…counting what it found against what a seven-column row has" "$err" "separators where a seven-column row carries 6"
has   "…saying which cell the other reading would have overwritten" "$err" "handoff path"
has   "…and naming the escape a Markdown table wants" "$err" '\|'
is    "…and the row is untouched" "$(grep '^| `repoA13-2`' "$LANES")" "$a13_amb"

# THE SHARED CUT THE THREE ROW WRITERS CARRY, as a unit. The address is
# `/^cut_to_line()/` and NOT `/^cut_to_line() {/`: an unescaped `{` in a BRE is
# undefined by POSIX, and BSD `sed` — the macOS job's — answers nothing at all
# for it, so all three of these cases came back EMPTY there while two of them
# passed vacuously against an empty string (measured on `4df80b6`'s
# `tests-macos`). The function's own line is unique without the brace. It is what keeps a
# `dir` or a launch flag holding a `|` from reaching `set-row-state`, whose
# contract refuses every pipe — a normal start would then rename the window and
# fail to stamp the row (Copilot round 1 on openRepoTools#82).
a13_cut="$(bash -c 'eval "$(sed -n "/^cut_to_line()/,/^}/p" "$1")"; cut_to_line "$2"' _ "$OPENREPOTOOLS_BIN_DIR/lane-start" "launching claude --flag a|b; dir /x · y")"
is    "the shared cut spells a cell boundary as the broken bar" "$a13_cut" "launching claude --flag a¦b; dir /x; y"
a13_long="$(awk 'BEGIN { s = ""; while (length(s) < 400) s = s "word "; print s }')"
a13_cut2="$(bash -c 'eval "$(sed -n "/^cut_to_line()/,/^}/p" "$1")"; cut_to_line "$2"' _ "$OPENREPOTOOLS_BIN_DIR/lane-start" "$a13_long")"
is    "…and cuts a long line at a word boundary, inside the cap" \
      "$( [ "${#a13_cut2}" -le 240 ] && echo yes || echo "no ${#a13_cut2}" )" "yes"
has   "…saying it was cut" "$a13_cut2" " ..."
a13_cut3="$(bash -c 'eval "$(sed -n "/^cut_to_line()/,/^}/p" "$1")"; cut_to_line "$2"' _ "$OPENREPOTOOLS_BIN_DIR/lane-start" "$(printf 'one\ntwo')")"
is    "…and a newline, because a row is ONE line of a table (Copilot round 2)" "$a13_cut3" "one; two"
hasnt "…never leaving half a character where the cut landed" "$a13_cut2" "wor ..."

# ---- (b) `append-row-status` is RETIRED, and the refusal names both acts.
run "$E" append-row-status repoA13-1 "anything at all"
is    "append-row-status refuses" "$rc" 2
has   "…naming the amendment that retired it" "$err" "Amendment 13(a)"
has   "…naming set-row-state for the STATE" "$err" "set-row-state repoA13-1"
has   "…naming log NOTED for the narrative" "$err" "log NOTED lane:repoA13-1"
has   "…naming log RULED for a ruling" "$err" "log RULED lane:repoA13-1"
has   "…and history for reading it back" "$err" "history repoA13-1"
has   "…and saying plainly that nothing was written" "$err" "Nothing was written"

# ---- (c) NOTED and RULED are written, and NEITHER IS A TRANSITION.
LANES_LANE=repoA13-1 LANES_SESSION="$A13_ID" "$E" log STARTED "lane:repoA13-1" "→" "home opensoft/repoA13" >/dev/null 2>&1
run env LANES_LANE=repoA13-1 LANES_SESSION="$A13_ID" "$E" log NOTED "lane:repoA13-1" "rebased on main; the flake is the fixture's clock"
is    "a NOTED is written" "$rc" 0
has   "…as a lane-kind line whose object is the lane itself" "$(cat "$LOGD/repoA13-1.md")" \
      "NOTED — lane repoA13-1, session $A13_ID@Eagle"
run env LANES_LANE=repoA13-1 LANES_SESSION="$A13_ID" "$E" log RULED "lane:repoA13-1" "→" "openrepotools#29" "Ratify as drafted (Recommended)"
is    "a RULED is written" "$rc" 0
has   "…with the object it bears on as its payload, CANONICALISED through repos.tsv" "$(cat "$LOGD/repoA13-1.md")" \
      "lane:repoA13-1 → opensoft/openRepoTools#29 — Ratify as drafted (Recommended)"

run env LANES_LANE=repoA13-1 LANES_SESSION="$A13_ID" "$E" log NOTED "opensoft/openRepoTools#29" "a note about an issue"
is    "a NOTED whose object is not the lane is refused" "$rc" 2
has   "…pointing at the payload where an object belongs" "$err" "log RULED lane:repoA13-1 → opensoft/openRepoTools#29"
run env LANES_LANE=repoA13-1 LANES_SESSION="$A13_ID" "$E" log NOTED "lane:repoA13-1" "→" "opensoft/openRepoTools#29" "x"
is    "a NOTED with a payload is refused" "$rc" 2
run env LANES_LANE=repoA13-1 LANES_SESSION="$A13_ID" "$E" log NOTED "lane:repoB-1" "a note about somebody else's lane"
is    "a NOTED whose object is ANOTHER lane is refused (Copilot round 5)" "$rc" 2
has   "…because a note is written into the log of the lane it names" "$err" "lane:repoA13-1, not lane:repoB-1"
is    "…and nothing was written to that lane's log" "$(cat "$LOGD/repoB-1.md" 2>/dev/null | grep -c 'somebody else' || :)" 0
run env LANES_LANE=repoA13-1 LANES_SESSION="$A13_ID" "$E" log RULED "lane:repoA13-1"
is    "a RULED with no words is refused" "$rc" 2
has   "…because the words ARE the ruling" "$err" "verbatim"
run env LANES_LANE=repoA13-1 LANES_SESSION="$A13_ID" "$E" log RULED "lane:repoA13-1" "←" "opensoft/openRepoTools#29" "x"
is    "a RULED pointed the other way is refused" "$rc" 2

run "$E" who --lane repoA13-1
has   "who --lane is unmoved by two narrative lines in the log" "$out" "none open"
run "$E" lanes
is    "…and the listing's state column is still the lane's last LANE verb" \
      "$(printf '%s\n' "$out" | grep '^repoA13-1' | head -n1 | cut -f2)" "IDLE"

LANES_LANE=repoA13-1 LANES_SESSION="$A13_ID" "$E" log PAUSED "lane:repoA13-1" "→" "swap; window a13sess:0; workstation Eagle; dir /x; profile team-a13" >/dev/null 2>&1
run "$E" swapped Eagle
has   "a swapped lane is listed" "$out" "repoA13-1"
LANES_LANE=repoA13-1 LANES_SESSION="$A13_ID" "$E" log NOTED "lane:repoA13-1" "a note taken after the swap, which is not a transition" >/dev/null 2>&1
run "$E" swapped Eagle
has   "…and a NOTED written AFTER the swap does not un-swap it (Amendment 13(b))" "$out" "repoA13-1"
run "$E" lane-last repoA13-1
has   "…nor does it become the lane's last lane-kind line" "$out" "PAUSED"

# THE PHRASE'S LINE IS PROSE, AND `lane-end` READS THE STATE (Copilot round 1
# on openRepoTools#82). The one path that still decides a merge hold from words
# — a lane with no object log — scanned the WHOLE cell, so an Amendment 13
# phrase whose line legitimately says "waiting for LANDING #7" was a false hold
# that refused to close the lane. A LEGACY DIARY CELL IS UNCHANGED.
"$E" add-row "| \`repoA13-3\` | harness \`$A13_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoA13/p.md | LIVE · 2026-09-14T00:00:00Z · waiting for LANDING #7 to go green |" >/dev/null 2>&1
run "$END" repoA13-3
is    "a phrase whose LINE mentions a landing is not a hold" "$rc" 0
has   "…and the lane is closed" "$(grep '^| `repoA13-3`' "$LANES")" "| ENDED · "
"$E" add-row "| \`repoA13-4\` | harness \`$A13_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoA13/q.md | LANDING #9 · 2026-09-14T00:00:00Z · CI green; waiting on review |" >/dev/null 2>&1
run "$END" repoA13-4
is    "…while a phrase whose STATE is LANDING still is one (Rule 6, unchanged)" "$rc" 2
has   "…named as what it read" "$err" "the last LANDING in its state cell"
"$E" add-row "| \`repoA13-5\` | harness \`$A13_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoA13/r.md | ACTIVE · 2026-09-12T10:00Z LANDING #7 into repoA13 main |" >/dev/null 2>&1
run "$END" repoA13-5
is    "…and a LEGACY diary cell is still scanned whole" "$rc" 2
# THE SECOND FIELD BEING AN INSTANT IS NOT ENOUGH (Copilot round 4 on
# openRepoTools#82). A legacy diary whose second entry is nothing but a
# timestamp has the phrase's SHAPE and none of its meaning: narrowing the scan
# to `ACTIVE` there would close a pre-cutover lane over an open landing, and
# narrowing is the fail-OPEN direction. The first field must be one of the
# amendment's own states too.
"$E" add-row "| \`repoA13-6\` | harness \`$A13_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoA13/s.md | ACTIVE · 2026-09-12T10:00:00Z · LANDING #7 into repoA13 main |" >/dev/null 2>&1
run "$END" repoA13-6
is    "a diary whose second entry is only an instant is not the phrase" "$rc" 2
has   "…so its landing still holds the lane" "$err" "the last LANDING in its state cell"
# AND EXACTLY THREE PARTS, WITH THE THIRD NOT EMPTY (Copilot round 5): a FOURTH
# ` · ` is a history after the phrase's first two fields, and narrowing to the
# state there would close a lane over the landing in that history.
"$E" add-row "| \`repoA13-7\` | harness \`$A13_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoA13/t.md | LIVE · 2026-09-14T00:00:00Z · a note · 2026-09-14T01:00:00Z LANDING #7 into repoA13 main |" >/dev/null 2>&1
run "$END" repoA13-7
is    "a cell with a FOURTH part is a diary, not the phrase" "$rc" 2
has   "…so the landing in its history still holds the lane" "$err" "the last LANDING in its state cell"

# ---- (d) `history` — the diary the cell used to be.
run "$E" history repoA13-1
is    "history exits 0 for a lane that has written a narrative" "$rc" 0
is    "…printing it in FILE order, oldest first" \
      "$(printf '%s\n' "$out" | head -n1 | awk '{ print $2 }')" "NOTED"
has   "…the ruling with the object it bears on" "$out" "RULED  opensoft/openRepoTools#29 — Ratify as drafted (Recommended)"
hasnt "…and never a lane-kind transition, which is not narrative" "$out" "STARTED"
hasnt "…and never the swap record either" "$out" "swap; window"
run "$E" history repoB-1
is    "a lane that has written no narrative is 8, not a failure" "$rc" 8
run "$E" history repoA13-1 --since yesterday
is    "a --since that is not an instant is a usage refusal (64)" "$rc" 64
run "$E" history
is    "…and so is history with no lane" "$rc" 64

# ---- (e) `migrate-state-cells` — clause (e)'s ONE act, on its own register.
#
# ITS OWN WORKSPACE, and that is not tidiness: this act rewrites EVERY row of
# the register it is pointed at and appends to every lane's log. Run against the
# suite's own sandbox register it would rewrite the fixtures of every case above
# and below it, and what it is being tested for — that it takes a whole register
# at once — is exactly what makes that unsafe. `LANES_WORKSPACE_ROOT` is the
# seam Amendment 9(a) left for pointing a helper at another sandbox.
MIG_ORIGIN="$SANDBOX/a13-origin.git"; MIG_WIP="$SANDBOX/a13wip"
git init -q --bare -b main "$MIG_ORIGIN"
git clone -q "$MIG_ORIGIN" "$MIG_WIP" 2>/dev/null
git -C "$MIG_WIP" config user.email "test@example.invalid"
git -C "$MIG_WIP" config user.name  "lane helper tests"
mkdir -p "$MIG_WIP/lanes/log"
MIG_ID1="aaaa0014-1414-4000-8000-aaaa00141414"
MIG_ID2="aaaa0015-1515-4000-8000-aaaa00151515"
{
  printf '# LANES.md — the migration sandbox\n\n'
  printf '| lane | session id | workstation / env / user | started (UTC) | objects owned | handoff path | state |\n'
  printf '|---|---|---|---|---|---|---|\n'
  # THREE ROWS, MIXED ENTRIES: one whose FIRST entry carries no UTC of its own
  # (it takes the row's `started`), one RULING, and a last entry whose leading
  # verb is one of clause (a)'s so the new cell is derived rather than MIGRATED.
  printf '| `repoMig-1` | harness `%s` → harness `%s` | Eagle / test / brett | 2026-09-11T00:00Z | none | handoffs/repoMig/x.md | ACTIVE · 2026-09-12T10:00:00Z opened the PR and it went green · 2026-09-12T11:00:00Z RULING: "land it as drafted" · 2026-09-12T12:00:00Z PAUSED for the night |\n' "$MIG_ID1" "$MIG_ID2"
  printf '| `repoMig-2` | harness `%s` | Eagle / test / brett | 2026-09-11 | none | handoffs/repoMig/y.md | LIVE |\n' "$MIG_ID1"
  printf '| `repoMig-3` | harness `%s` | Raven / test / brett | 2026-09-11 | none | handoffs/repoMig/z.md | ACTIVE · RATIFIED "as drafted" · 2026-09-13T08:00:00Z LANDED — PR #7 → abc1234 |\n' "$MIG_ID1"
  # A FOURTH, whose last entry's leading word is no state at all: its cell
  # becomes `MIGRATED`, which is clause (e)'s own word for "the state is in the
  # log now" and is not one of clause (a)'s seven.
  printf '| `repoMig-4` | harness `%s` | Eagle / test / brett | 2026-09-12 | none | handoffs/repoMig/w.md | ACTIVE · 2026-09-13T09:00:00Z rebased and re-ran the suite |\n' "$MIG_ID1"
  # A FIFTH, already in clause (a)'s shape: this act leaves it alone, and the
  # report counts it apart from the one-word cells, which are NOT in the shape
  # (Copilot round 1 on openRepoTools#82).
  printf '| `repoMig-5` | harness `%s` | Eagle / test / brett | 2026-09-12 | none | handoffs/repoMig/v.md | LIVE \302\267 2026-09-14T00:00:00Z \302\267 already the phrase |\n' "$MIG_ID1"
  # A SIXTH, whose last entry opens `LANDING #123abc`: the number ends where the
  # word ends, so that is NO landing and the cell becomes `MIGRATED` rather than
  # a merge hold Rule 6 would read (Copilot round 1 on openRepoTools#82).
  printf '| `repoMig-6` | harness `%s` | Eagle / test / brett | 2026-09-12 | none | handoffs/repoMig/u.md | ACTIVE \302\267 2026-09-13T10:00:00Z LANDING #123abc is not a number |\n' "$MIG_ID1"
} > "$MIG_WIP/lanes/LANES.md"
git -C "$MIG_WIP" add -A >/dev/null 2>&1
git -C "$MIG_WIP" commit -q -m "seed the migration sandbox"
git -C "$MIG_WIP" push -q -u origin main
MIG_HEAD0="$(git -C "$MIG_WIP" rev-parse HEAD)"

a13_tmp_before="$(ls -d "$TMPDIR"/tmp.* 2>/dev/null | grep -c . || :)"
run env LANES_WORKSPACE_ROOT="$MIG_WIP" "$E" migrate-state-cells
is    "the migration is a DRY RUN by default" "$rc" 0
has   "…saying so" "$out" "DRY RUN, nothing is written"
has   "…naming the archive it would write" "$out" "lanes/archive/LANES-pre-amendment-13-"
has   "…counting the rows it would take" "$out" "6 read · 4 to migrate · 1 already the phrase · 1 one word, no history · 0 skipped"
has   "…and saying what a one-word cell still owes, since it is NOT the phrase" "$out" "the next set-row-state on each writes it"
has   "…and the lines it would write" "$out" "log lines: 11 (9 NOTED, 2 RULED)"
has   "…with the phrase each cell becomes" "$out" "→ PAUSED · "
is    "…and it wrote NOTHING" "$(git -C "$MIG_WIP" status --porcelain | grep -c . || :)" 0
is    "…and left no staging directory behind either (Copilot round 1)" \
      "$(ls -d "$TMPDIR"/tmp.* 2>/dev/null | grep -c . || :)" "$a13_tmp_before"
is    "…not even a commit" "$(git -C "$MIG_WIP" rev-parse HEAD)" "$MIG_HEAD0"

# AN UNTRACKED TARGET LOG IS SOMEBODY'S UNCOMMITTED WORK (Copilot round 2 on
# openRepoTools#82): a TRACKED one that is dirty is already refused for the whole
# run by `refuse_dirty_checkout`, which reads staged and unstaged alike, but an
# untracked file is in neither list and this act would commit its first lines
# inside the migration's own commit, under the migration's message.
printf '# lane repoMig-4 — object log (seeded by a peer, uncommitted)\n' > "$MIG_WIP/lanes/log/repoMig-4.md"
run env LANES_WORKSPACE_ROOT="$MIG_WIP" "$E" migrate-state-cells
is    "…a row whose object log is untracked is SKIPPED, not committed for its author" "$rc" 0
has   "…naming the file and whose it is" "$out" "exists here but is NOT TRACKED"
has   "…and counting it among the skipped" "$out" "1 skipped"
git -C "$MIG_WIP" add -- lanes/log/repoMig-4.md >/dev/null 2>&1
git -C "$MIG_WIP" commit -q -m "the peer commits its own log, as the refusal asks"
git -C "$MIG_WIP" push -q origin main 2>/dev/null || :
# THE BASELINE MOVES WITH IT: the peer's commit is a commit, and the "one commit"
# this act makes is counted from where the act starts, not from the seed.
MIG_HEAD1="$(git -C "$MIG_WIP" rev-parse HEAD)"

run env LANES_WORKSPACE_ROOT="$MIG_WIP" "$E" migrate-state-cells --yes
is    "the act exits 0" "$rc" 0
is    "…and it is ONE commit (Rule 9), not one per row" \
      "$(git -C "$MIG_WIP" rev-list --count "$MIG_HEAD1"..HEAD)" 1
has   "…whose subject says what it did" "$(git -C "$MIG_WIP" log -1 --format=%s)" "Amendment 13(e)"
is    "…carrying the archive, all four logs and the register, and nothing else" \
      "$(git -C "$MIG_WIP" show --name-only --format= HEAD | grep -c .)" 6
is    "the pre-migration register is archived" \
      "$(ls "$MIG_WIP/lanes/archive" | grep -c '^LANES-pre-amendment-13-.*\.md$' || :)" 1
is    "…byte for byte as it was" \
      "$(git -C "$MIG_WIP" show "$MIG_HEAD0:lanes/LANES.md" | cmp -s - "$MIG_WIP/lanes/archive/$(ls "$MIG_WIP/lanes/archive" | head -n1)" && echo same || echo different)" "same"
mig_log1="$(cat "$MIG_WIP/lanes/log/repoMig-1.md")"
has   "an entry with no UTC of its own takes the row's started (clause (e))" "$mig_log1" \
      "NOTED — lane repoMig-1, session $MIG_ID2@Eagle, 2026-09-11T00:00Z, lane:repoMig-1 — ACTIVE"
has   "…an entry with one keeps it, and its text is verbatim" "$mig_log1" \
      "2026-09-12T10:00:00Z, lane:repoMig-1 — opened the PR and it went green"
has   "…an entry beginning RULING is a RULED, under its OWN leading UTC" "$mig_log1" \
      'RULED — lane repoMig-1, session '"$MIG_ID2"'@Eagle, 2026-09-12T11:00:00Z, lane:repoMig-1 — RULING: "land it as drafted"'
is    "…the session is the LAST uuid of the row's session cell" \
      "$(printf '%s\n' "$mig_log1" | grep -c "session $MIG_ID1@" || :)" 0
mig_log3="$(cat "$MIG_WIP/lanes/log/repoMig-3.md")"
has   "…and the workstation is the row's OWN column, not the one running the act" "$mig_log3" "@Raven,"
has   "…an entry beginning RATIFIED is a RULED too" "$mig_log3" 'RULED — lane repoMig-3'
has   "…and an entry with no timestamp of its own takes the row's started" "$mig_log3" \
      'RULED — lane repoMig-3, session '"$MIG_ID1"'@Raven, 2026-09-11T00:00Z, lane:repoMig-3 — RATIFIED "as drafted"'
has   "…and a text carrying its own \" — \" survives verbatim" "$mig_log3" "LANDED — PR #7 → abc1234"

mig_reg="$(cat "$MIG_WIP/lanes/LANES.md")"
has   "the cell is REPLACED by the state its last entry names" "$mig_reg" "| PAUSED · "
has   "…LANDED where the last entry says LANDED" "$mig_reg" "| LANDED · "
has   "…and by MIGRATED where the last entry's leading word is no state at all" "$mig_reg" "| MIGRATED · "
is    "…and \`LANDING #123abc\` derives no landing, because the number ends where the word does" \
      "$(grep '^| `repoMig-6`' "$MIG_WIP/lanes/LANES.md" | grep -c '| MIGRATED · ' || :)" 1
has   "…every migrated cell pointing at the log that now holds its history" "$mig_reg" "history in lanes/log/repoMig-1.md |"
hasnt "…with the diary gone from the row" "$mig_reg" "opened the PR and it went green"
has   "…and a cell that was already one phrase is untouched" "$mig_reg" "| LIVE |"

# THE MIGRATED LINE IS BOUNDED BY THE SAME CAP THE WRITER ENFORCES (Copilot
# round 5): this cell is built directly, not through `set-row-state`, and it
# carries a PATH whose length is the lane's name — which `check_lane_name`
# bounds in characters and not in length.
MIG_LONG="repoMig-$(awk 'BEGIN { s = ""; while (length(s) < 230) s = s "x"; print s }')"
printf '| `%s` | harness `%s` | Eagle / test / brett | 2026-09-12 | none | h | ACTIVE · 2026-09-13T10:00:00Z a long-named lane |\n' "$MIG_LONG" "$MIG_ID1" >> "$MIG_WIP/lanes/LANES.md"
git -C "$MIG_WIP" add -A >/dev/null 2>&1
git -C "$MIG_WIP" commit -q -m "seed a lane whose name alone is longer than the cap"
git -C "$MIG_WIP" push -q origin main 2>/dev/null || :
run env LANES_WORKSPACE_ROOT="$MIG_WIP" "$E" migrate-state-cells --yes
is    "a lane whose name alone overruns the cap still migrates" "$rc" 0
# TWO LINES, AND THE SPLIT IS NOT A STYLE CHOICE: `grep` and the awk program's
# `\|` on ONE line is what `test_no_shipped_bash_reaches_for_gnu_only_utilities_unaccompanied`
# reads as a BRE alternation handed to `grep`, which is a GNU extension BSD
# matches literally without saying so. The `\|` here is awk's own escape inside
# an ERE and never reaches `grep` — so the row is taken first, and the awk that
# splits it runs on its own line.
mig_long_row="$(grep "^| \`$MIG_LONG\`" "$MIG_WIP/lanes/LANES.md")"
mig_long_cell="$(printf '%s' "$mig_long_row" | awk -F' \\| ' '{ c = $NF; sub(/ \|$/, "", c); n = split(c, p, / · /); print (length(p[3]) <= 240 ? "yes" : "no " length(p[3])) }')"
is    "…with its line inside ratified decision O1's 240 characters" "$mig_long_cell" "yes"
has   "…and the line says it was cut" "$(grep "^| \`$MIG_LONG\`" "$MIG_WIP/lanes/LANES.md")" " ..."
MIG_HEAD2="$(git -C "$MIG_WIP" rev-parse HEAD)"

run env LANES_WORKSPACE_ROOT="$MIG_WIP" "$E" history repoMig-1 --since 2026-09-12T11:00:00Z
is    "history reads the migrated narrative" "$rc" 0
hasnt "…--since drops every entry older than the instant" "$out" "opened the PR"
has   "…and keeps the instant itself" "$out" "land it as drafted"
has   "…and what came after it" "$out" "PAUSED for the night"

run env LANES_WORKSPACE_ROOT="$MIG_WIP" "$E" migrate-state-cells --yes
is    "a SECOND run refuses: the migration is ONE act" "$rc" 2
has   "…saying the register is already in the shape" "$err" "already in Amendment 13(a)'s shape"
is    "…and changed nothing" "$(git -C "$MIG_WIP" rev-list --count "$MIG_HEAD2"..HEAD)" 0
run env LANES_WORKSPACE_ROOT="$MIG_WIP" "$E" migrate-state-cells --no-such-flag
is    "an unknown flag is a refusal, not a silent dry run" "$rc" 2

echo "== the workstation seam: unset, every writer reads the host =="

# THE OTHER HALF OF R-A9-13. Every case above this line runs with
# `LANES_WORKSTATION=Eagle` exported at the top of this file, which is what
# makes the 55 seed rows and the three writers agree on any machine. That pin
# would also hide the opposite defect — a writer that stopped reading the host
# at all, or that read it with a different command than its siblings, which is
# exactly what `lane-start` and `lane-end` did with their bare `hostname` until
# this round. So the seam is UNSET for these three cases and the DEFAULT is
# asserted directly, against `hostname -s` computed here: one spelling, shared
# by `lanes-edit.sh:438`, `lane-start` and `lane-end`.
WS_HOST="$(hostname -s)"
is   "this host has a short name to fall back to" \
     "$( [ -n "$WS_HOST" ] && echo yes || echo no )" "yes"

mkdir -p "$HOME/projects/repoWS"
git init -q -b main "$HOME/projects/repoWS"
git -C "$HOME/projects/repoWS" remote add origin "https://github.com/opensoft/repoWS.git"
# The cases above leave handoff files uncommitted in the sandbox workspace on
# purpose, and `lanes-edit.sh` REFUSES an object-log write on a checkout it
# cannot rebase — which is the behaviour those cases are about. This one is
# about the workstation name, so the checkout is committed first and the
# refusal is out of the way.
git -C "$WIP" add -A >/dev/null 2>&1
git -C "$WIP" commit -q -m "commit the sandbox's pending handoffs before the workstation-seam cases" >/dev/null 2>&1 || :

# `LANES_IN_CONTAINER=0` THROUGHOUT THIS SECTION, and the reason is the rule
# itself (`R-A11-14`): with the seam unset, the DEFAULT is `hostname -s` OUTSIDE
# a container and a REFUSAL INSIDE one — and the host this suite runs on is a
# container exactly when it is. The half this section is about is the default,
# so the probe is pinned; the refusal has its own cases in the Amendment 11
# section above, pinned the other way.
run env -u LANES_WORKSTATION LANES_IN_CONTAINER=0 "$START" repoWS 1 --no-launch
is   "lane-start with the seam unset exits 0" "$rc" 0
has  "…and its new row names the HOST in the workstation column" \
     "$(grep '^| `repoWS-1`' "$LANES")" "$WS_HOST / "

run env -u LANES_WORKSTATION LANES_IN_CONTAINER=0 env LANES_LANE=repoWS-1 "$E" claim "opensoft/repoWS#1" --no-github
is   "lanes-edit.sh claim with the seam unset exits 0" "$rc" 0
has  "…and stamps the same host on the CLAIMED line it writes" \
     "$(grep '^CLAIMED' "$LOGD/repoWS-1.md" | tail -n1)" "@$WS_HOST,"

run env -u LANES_WORKSTATION LANES_IN_CONTAINER=0 "$END" repoWS-1 --force
is   "lane-end with the seam unset exits 0" "$rc" 0
has  "…and its row status names the same host" \
     "$(grep '^| `repoWS-1`' "$LANES")" "lane-end on $WS_HOST:"

# ------------- 7. the resolver's 2 is a REFUSAL here too (Amendment 15(d))
#
# `2` IS TWO ANSWERS AND THE REFUSAL IS THE ONE THAT MATTERS. It is what a
# helper predating a subcommand spends on an unknown one — the rung this
# command's read fence falls through for — and it is ALSO `canon_lane`'s
# refusal of a register holding two rows that differ only by case, which every
# read through `check_lane_name` now carries. Falling through THAT is binding
# this window to whichever lane the next rung answers with, and then renaming
# the window, writing a PAUSED record and respawning a pane for it. So the
# refusal is asked for by its own WORDS, exactly as `lane-start`, `lane-end` and
# `restart` ask for it, and relayed — and it is asked BEFORE the rename, so a
# refusal leaves the window exactly as it found it.
#
# This pair is made LAST, after every other case in this section has run: two
# rows differing only by case are a register no read of that lane is unambiguous
# in, which is the point.
#
# SEEDED AS IT EXISTED, with `add_seed_row` and one commit — NOT with `add-row`,
# which is one of the writers Amendment 15 makes refuse this very shape. A
# fixture built through the writer would be a fixture with one row in it, and
# the case below would go green on a register that is not ambiguous at all.
add_seed_row "| \`repoHF-13\` | harness \`$HF_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoHF/repoHF-13.md | ACTIVE |"
add_seed_row "| \`repohf-13\` | harness \`$HF2_ID\` | Eagle / test / brett | 2026-09-14T00:00Z | none | handoffs/repoHF/repohf-13.md | ACTIVE |"
git -C "$WIP" add -A -- lanes >/dev/null 2>&1
git -C "$WIP" commit -q -m "seed the 15(d) pair lane-handoff is asked about"
git -C "$WIP" pull -q --rebase origin main 2>/dev/null || :
git -C "$WIP" push -q origin main
: > "$FAKE_TMUX_A17_LOG"
run env PATH="$A17PATH" FAKE_TMUX_WINDOW="hfsess:@21" CLAUDE_CODE_SESSION_ID="$HF_ID" \
    CLAUDE_PROFILE_NAME=team-05a "$HANDOFF_CMD" --lane repoHF-13 --restart clear
is    "lane-handoff refuses a register holding two rows that differ only by case" "$rc" 2
has   "…citing the merge that is a person's act" "$err" "Amendment 15(d)"
has   "…saying nothing was written and nothing renamed" "$err" "Nothing was written and nothing was renamed"
is    "…and no pane was respawned for a lane no read of it is unambiguous about" \
      "$(grep -c 'respawn-pane' "$FAKE_TMUX_A17_LOG")" 0
is    "…and no log was written for either spelling" \
      "$(ls "$LOGD" | grep -ci '^repohf-13\.md$' || :)" 0

# ------------------------------------------------------- nothing real touched
#
# The check is that the suite CREATED nothing here, which is not the same as
# this directory being empty: a real `lanes/log/` carries real lanes' logs, and
# asserting a count of zero would fail on the operator's own committed records
# rather than on anything the suite did. So it counts only names the SUITE
# could have written — the `repo[A-Z]…` fixtures every case uses — in the
# operator's real workspace, read at $REAL_WS before $HOME was redirected. (An
# earlier draft of this comment described a before/after list under a variable
# `SRC_LOG_BEFORE`; no such variable was ever written, and the fixture-name
# filter is what actually does the work.)
is   "the suite never created a log outside the sandbox" \
     "$(ls "$REAL_WS/lanes/log" 2>/dev/null | grep -c '^repo[A-Z]' || :)" 0
is   "the suite never wrote the real register" \
     "$(cat "$REAL_WS/lanes/LANES.md" 2>/dev/null | grep -c '^| `repo[A-Z]' || :)" 0
# BOTH OF THEM READ A PIPE, and the second one did not until A9 Addendum 4
# (R-A9-13, F3). `grep -c PATTERN FILE` on a file that is not there prints
# NOTHING and exits 2, so with no `~/.agents/workspace.yaml` on the host
# `$REAL_WS` is empty, the comparison was `""` against `0`, and this assertion
# FAILED on every CI runner and every new person's machine — the one host
# shape it was written to be harmless on. `grep -c` reading a PIPE always
# prints a number, so `cat 2>/dev/null | grep -c` degrades to `0` where the
# sibling above already did.
#
# NEVER VACUOUS, whatever this host has. The two above compare the operator's
# own workspace with itself and degrade to a true statement about nothing on a
# CI runner that has no workspace at all; this one asserts the positive — the
# logs the suite DID create are inside the sandbox, under the workspace the
# sandbox's own workspace.yaml names, and there is at least one of them.
is   "…and every log it did create is inside the sandbox workspace" \
     "$( [ "$(ls "$WIP/lanes/log" 2>/dev/null | grep -c .)" -gt 0 ] && echo yes || echo no )" "yes"

# THE FIXTURE EVERY LIVENESS CASE ABOVE DEPENDS ON, ASSERTED LAST (A9 Addendum
# 4, R-A9-11). A `sleep` that runs out of seconds before the suite runs out of
# cases does not announce itself: it turns "a live holder …" into "no live
# holder …" one case at a time, and 196 red lines say nothing about why. This
# one line does. Red here and nowhere else means the bound at `sleep 3000` is
# what needs raising; red here beside two hundred others means it is why.
is   "the liveness fixture was still running when the run ended" \
     "$(kill -0 "$LIVE_PID" 2>/dev/null && printf alive || printf gone)" alive

echo "----"
if [ "$pending_n" != 0 ]; then
  printf '%s PENDING — owed to a commit landing in another repository, not a failure:\n' "$pending_n"
  printf '%s' "$pending_list"
fi
printf '%s passed, %s failed, %s skipped, %s pending\n' "$pass" "$fail" "$skipped" "$pending_n"
[ "$fail" = 0 ] || exit 1
exit 0
