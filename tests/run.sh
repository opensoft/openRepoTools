#!/usr/bin/env bash
#
# tests/run.sh — THE way to run this repository's suite.
#
#   tests/run.sh                 the whole suite
#   tests/run.sh -k lane_helpers  …and anything else pytest takes
#
# WHY A WRAPPER AND NOT A LINE IN A DOCUMENT (opensoft/openRepoTools#51,
# measured 2026-09-14T20:4xZ on Eagle). This suite is minutes of bash and
# hundreds of `git` processes, and several lanes build in sibling worktrees of
# ONE checkout on one workstation. Four `python3 -m pytest tests -q` runs were
# live at once that evening, every one of them past a guard that had been
# copied into four briefs:
#
#     while pgrep -af 'python3 -m pytest' | grep -v pgrep >/dev/null; do sleep 20; done
#
# It never waited. Under the harness `grep` is a shell FUNCTION, and its status
# with stdout on `/dev/null` is 1 even where it matched — the same pipeline
# captured into a variable returned 0 and six lines. The collision is not a
# shared path (the suite redirects `$HOME` and `$TMPDIR`); it is TIME: a suite
# that takes 18 minutes alone takes far longer four-wide and trips every
# wrapper's timeout around it.
#
# So the guard is written ONCE, here, where no brief can retype it wrong:
#
#   * THE PATTERN IS ANCHORED AND SPLIT. `^python3 -m pyt` + `est` cannot match
#     this script's own command line, and the anchor keeps it to real runs.
#   * `pgrep`'s STATUS IS NEVER READ. The count is what decides, and it is
#     counted with `awk` rather than with `pgrep -c`, which is not in every
#     `pgrep` this repository runs under.
#   * THE POLL IS NOT THE LOCK. A poll alone lets every waiter start the
#     instant the run it was watching ends, which is the same collision one
#     step later. The lock is what makes the second one wait, and every lane on
#     one workstation must name the SAME file or there is no lock at all:
#     `${TMPDIR:-/tmp}/openrepotools-pytest.lock`, which is what `AGENTS.md`
#     and `docs/README-lanes.md` both spell, and what a hygiene test pins in
#     this file and in `AGENTS.md` together.
#   * THE POLL RUNS AGAIN INSIDE THE LOCK, because a run started by hand —
#     by somebody who did not use this wrapper — holds no lock to wait on.
#
# `flock` IS LINUX-ONLY. macOS ships none, so the fallback is `mkdir`, whose
# atomicity POSIX guarantees; the holder's pid is left inside it so a lock a
# killed run left behind is taken over rather than waited on for ever.
#
# NOTHING NEW LANDS BESIDE THE CODE (opensoft/openRepoTools#162, causes 3 and
# 4). A suite run used to leave `tests/__pycache__`, `.pytest_cache` and a
# killed run's sandboxes behind in whichever worktree ran it, and a lane's
# leftovers were 968 of 1,000 removals in the estate's cleanup. So:
#
#   * BYTECODE goes to `${XDG_CACHE_HOME:-$HOME/.cache}/openRepoTools/pycache`
#     (`PYTHONPYCACHEPREFIX`), never into a checkout;
#   * pytest's cache is off (`-p no:cacheprovider`);
#   * EVERY TEMPORARY DIRECTORY of the run - pytest's `--basetemp` and the
#     `TMPDIR` the suite's own `mktemp`s use - is under ONE run root,
#     `${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/tmp/<UTC>-<pid>/`,
#     which an EXIT trap removes however the run ends. A SIGKILL is the one
#     end no trap sees; the pid in the root's name is what lets
#     `lane-worktrees sweep --include-sandboxes` tell its owner is gone.
#   * the suite runs from the repository's own virtual environment where one
#     is there and has pytest (`${XDG_CACHE_HOME:-$HOME/.cache}/openRepoTools/
#     venvs/openRepoTools`, which `openRepoTools --install` names), put FIRST
#     on PATH so the command line still reads `python3 -m pytest` - the shape
#     every other lane's poll counts.
#
# THE LOCK IS COMPUTED BEFORE `TMPDIR` IS MOVED: it is the workstation's, and
# a run that locked a file under its own run root would lock nothing.
#
# bash 3.2 (Apple's stock `/bin/bash`) parses this file in CI, like every other
# bash file here: no `${x,,}`, no `mapfile`, no `declare -A`, no `local -n`.

set -uo pipefail

prog="${0##*/}"

# THE REPOSITORY ROOT, so the suite runs the same from anywhere. `cd -P` is
# the portable physical path: `readlink -f` is not in the stock macOS userland.
cd -P -- "$(dirname -- "$0")/.." 2>/dev/null || {
  printf '%s: cannot find the repository root from %s\n' "$prog" "$0" >&2
  exit 1
}

# `--basetemp` IS THIS WRAPPER'S (#170 G8): every temporary directory of a run
# is under the run root its EXIT trap removes, and pytest takes the LAST
# `--basetemp` it is given - a caller's, forwarded after the wrapper's, won,
# and its files landed where nothing removes them. Refused, before any lock.
for rs_arg in ${1+"$@"}; do
  case "$rs_arg" in
    --basetemp|--basetemp=*)
      printf '%s: --basetemp is the wrapper'"'"'s own (the run root, which it removes); run without it\n' \
        "$prog" >&2
      exit 64 ;;
  esac
done

LOCK="${TMPDIR:-/tmp}/openrepotools-pytest.lock"

# SPLIT SO IT CANNOT MATCH ITSELF, anchored so it counts only real runs.
pat='^python3 -m pyt'"est"

pytest_live() {   # how many real `python3 -m pytest` processes are running
  command -v pgrep >/dev/null 2>&1 || { printf '0\n'; return 0; }
  pgrep -f "$pat" 2>/dev/null | awk 'END { print NR + 0 }'
}

wait_for_pytest() {   # <where> — block while any other suite is running
  wfp_said=0
  while [ "$(pytest_live)" -gt 0 ]; do
    if [ "$wfp_said" = 0 ]; then
      printf '%s: another `python3 -m pytest` is live on this workstation (%s) — waiting\n' \
        "$prog" "$1" >&2
      wfp_said=1
    fi
    sleep 20
  done
  return 0
}

# THE RUN ROOT AND ITS CLEANUP. `cleanup` is the EXIT trap: it stops whatever
# is left of the suite's PROCESS GROUP, then removes the run root and, on the
# `mkdir` path, the lock it holds. The INT and TERM handlers stop the suite and
# EXIT, so the EXIT trap runs - a handler that only cleaned up and returned
# would release the lock while the suite carried on.
#
# THE GROUP, NOT THE PID: pytest is waiting on a shell suite, a `git`, a
# fixture's `sleep` when the signal comes, and a TERM to pytest alone leaves
# them running with their temp root deleted under them and the lock released
# around them. The suite is started in a process group of its own (below), and
# the whole group is stopped and waited for, KILLed after ten seconds.
RUN_ROOT=""
LOCKDIR_HELD=""
SUITE_PID=""
SUITE_PGID=""
TTY_PGID=""
TTY_BEFORE=""
# A member still RUNNING, read from `ps` and never from `kill -0`: a zombie
# answers `kill -0` until whoever adopted it reaps it, which may be never.
group_alive() {
  ps -A -o pgid= -o stat= 2>/dev/null |
    awk -v g="$SUITE_PGID" '$1 == g && $2 !~ /^Z/ { n++ } END { exit n ? 0 : 1 }'
}
# THE DEADLINE COMES BEFORE THE REAP (#170 item 3): an unbounded `wait` on the
# leader ran first, so a leader that traps or ignores TERM held this wrapper -
# and the workstation's lock - for ever, and the KILL below was never reached.
# The group is polled (zombies are not members that run), KILLed at the
# deadline, and only then is the leader reaped.
stop_group() {
  [ -n "$SUITE_PGID" ] || { stop_strays; return 0; }
  kill -TERM -- "-$SUITE_PGID" 2>/dev/null || return 0
  sg_n=0
  while group_alive && [ "$sg_n" -lt 50 ]; do
    sleep 0.2
    sg_n=$((sg_n + 1))
  done
  kill -KILL -- "-$SUITE_PGID" 2>/dev/null || :
  if [ -n "$SUITE_PID" ]; then wait "$SUITE_PID" 2>/dev/null || :; fi
  return 0
}
# THE TERMINAL'S RUN KEEPS ITS GROUP ID TOO (#170 G14). Run in the foreground,
# the suite is in THIS wrapper's process group, which no `kill -- -<pgid>` can
# stop without stopping the wrapper and the caller's pipeline (`| tee`) with
# it. So the group's members are read before the suite starts, and what is in
# the group afterwards that was not - and is not the wrapper's own sibling, a
# process its caller started beside it - is what the suite left running: it
# is stopped, KILLed after ten seconds, before the run root goes and the lock
# is released.
group_members() {   # <pgid> - the pids of its running members, one per line
  ps -A -o pid= -o pgid= -o stat= 2>/dev/null |
    awk -v g="$1" '$2 == g && $3 !~ /^Z/ { print $1 }'
}
#
# THE SCAN NEVER COUNTS ITSELF (#179, Copilot round 2): run in a command
# substitution, its subshell, `ps` and `awk` were members of the group that
# were not there before, so every scan found "strays", every terminal run
# waited out the whole ten seconds, and the pids it killed were the scan's own,
# already gone. It is run in THIS shell, writing to a file under the run root:
# `ps` and `awk` are then this shell's own children (ppid `$$`), and those are
# passed over - a stray never is one, since the suite, this shell's child, has
# returned, and what it left was reparented away. bash 3.2 has no `$BASHPID`
# to name a subshell by.
strays() {   # <file> - the members of TTY_PGID the suite left running, one per line
  : > "$1"
  ps -A -o pid= -o pgid= -o ppid= -o stat= > "$1.ps" 2>/dev/null || return 0
  awk -v g="$TTY_PGID" -v me="$$" -v parent="$PPID" -v before=" $TTY_BEFORE " '
    $2 == g && $1 != me && $3 != me && $3 != parent && $4 !~ /^Z/ &&
      index(before, " " $1 " ") == 0 { print $1 }' "$1.ps" > "$1"
}
read_strays() {   # <file> - its pids into SS_PIDS, with no fork
  SS_PIDS=""
  while read -r rs_pid; do
    [ -n "$rs_pid" ] && SS_PIDS="$SS_PIDS $rs_pid"
  done < "$1"
}
stop_strays() {
  [ -n "$TTY_PGID" ] && [ -n "$RUN_ROOT" ] && [ -d "$RUN_ROOT" ] || return 0
  ss_file="$RUN_ROOT/.strays"
  strays "$ss_file"; read_strays "$ss_file"
  [ -n "$SS_PIDS" ] || return 0
  # shellcheck disable=SC2086
  kill -TERM $SS_PIDS 2>/dev/null || :
  ss_n=0
  while :; do
    strays "$ss_file"; read_strays "$ss_file"
    [ -n "$SS_PIDS" ] && [ "$ss_n" -lt 50 ] || break
    sleep 0.2
    ss_n=$((ss_n + 1))
  done
  # shellcheck disable=SC2086
  [ -z "$SS_PIDS" ] || kill -KILL $SS_PIDS 2>/dev/null || :
  return 0
}
cleanup() {
  stop_group
  [ -n "$RUN_ROOT" ] && rm -rf -- "$RUN_ROOT"
  [ -n "$LOCKDIR_HELD" ] && rm -rf -- "$LOCKDIR_HELD"
  return 0
}
on_signal() {   # <exit code>
  stop_group
  exit "$1"
}

make_run_root() {
  run_base="${XDG_STATE_HOME:-$HOME/.local/state}/openRepoTools/tmp"
  RUN_ROOT="$run_base/$(date -u +%Y%m%dT%H%M%SZ)-$$"
  mkdir -p -- "$RUN_ROOT/tmp" "$RUN_ROOT/basetemp" || {
    printf '%s: cannot create the run root %s\n' "$prog" "$RUN_ROOT" >&2
    exit 1
  }
  chmod 700 "$RUN_ROOT" 2>/dev/null || :
  # THE RUN'S MARK: `lane-worktrees sweep --include-sandboxes` removes a
  # temporary directory only on proof a suite made it (#170 item 1), and this
  # pid is that proof for a run root a SIGKILL left behind.
  printf '%s\n' "$$" > "$RUN_ROOT/.openrepotools-run" 2>/dev/null || :
  export TMPDIR="$RUN_ROOT/tmp"
  export PYTHONPYCACHEPREFIX="${XDG_CACHE_HOME:-$HOME/.cache}/openRepoTools/pycache"
  venv="${XDG_CACHE_HOME:-$HOME/.cache}/openRepoTools/venvs/openRepoTools"
  if [ -x "$venv/bin/python3" ] && "$venv/bin/python3" -c 'import pytest' >/dev/null 2>&1; then
    PATH="$venv/bin:$PATH"; export PATH
    printf '%s: the suite runs from the repository venv %s\n' "$prog" "$venv" >&2
  fi
}

# `${1+"$@"}` AND NEVER A BARE `"$@"`: under `set -u`, BASH 3.2 — Apple's stock
# shell, and the one this file's `mkdir` lock exists for — treats `"$@"` with no
# positional parameters as an unbound variable and exits. `"${*:-}"` is the same
# rule for the line that echoes them.
#
# THE SUITE RUNS IN THE BACKGROUND AND IS WAITED FOR, because bash runs a trap
# only once its FOREGROUND child returns: a TERM sent to this wrapper while
# pytest ran in the foreground waited out the whole suite. `wait` is
# interrupted by a trapped signal; the handler then stops the suite itself.
# `<&0` keeps the suite's stdin this shell's: a background command's default
# stdin, with job control off, is /dev/null.
#
# `set -m` FOR THE ONE LINE THAT STARTS IT puts the suite in a process group of
# its own, whose id is its pid, so `stop_group` reaches every process it
# started (one that made a session or group of its own is beyond any wrapper).
# Monitor mode is off again before the `wait`, so no job notice is printed.
#
# A TERMINAL ON STDIN RUNS THE SUITE IN THE FOREGROUND instead, in this
# wrapper's own process group - the terminal's foreground group. A background
# group reading the terminal (`--pdb`, `breakpoint()`, `input()`) is stopped by
# SIGTTIN, and this wrapper would wait on it for ever holding the
# workstation's lock. In the foreground a Ctrl-C reaches every process of the
# suite from the terminal itself; the cost is that a TERM sent to this wrapper
# from elsewhere is acted on once the suite returns.
run_suite() {
  printf '%s: python3 -m pytest tests -q -p no:cacheprovider %s\n' "$prog" "${*:-}" >&2
  if [ -t 0 ]; then
    TTY_PGID="$(ps -o pgid= -p "$$" 2>/dev/null | tr -d ' ')"
    TTY_BEFORE="$(group_members "$TTY_PGID" | tr '\n' ' ')"
    python3 -m pytest tests -q -p no:cacheprovider --basetemp="$RUN_ROOT/basetemp" ${1+"$@"}
    rs_rc=$?
    stop_strays
    return "$rs_rc"
  fi
  set -m
  python3 -m pytest tests -q -p no:cacheprovider --basetemp="$RUN_ROOT/basetemp" ${1+"$@"} <&0 &
  SUITE_PID=$!
  SUITE_PGID=$SUITE_PID
  set +m
  wait "$SUITE_PID"
  rs_rc=$?
  SUITE_PID=""
  return "$rs_rc"
}

wait_for_pytest "before the lock"

if command -v flock >/dev/null 2>&1; then
  # THE FD FORM, so the lock is held for the life of this process and released
  # by its exit — including a kill, which no `rm` in a trap would survive.
  exec 9> "$LOCK" || { printf '%s: cannot open the lock file %s\n' "$prog" "$LOCK" >&2; exit 1; }
  flock 9 || { printf '%s: could not take the lock %s\n' "$prog" "$LOCK" >&2; exit 1; }
  trap cleanup EXIT
  trap 'on_signal 130' INT
  trap 'on_signal 143' TERM
  wait_for_pytest "inside the lock"
  make_run_root
  run_suite ${1+"$@"}
  exit $?
fi

# NO `flock` HERE — macOS. `mkdir` is the atomic operation POSIX gives a shell.
#
# THREE THINGS A `mkdir` LOCK HAS TO GET RIGHT, and the first shape of this loop
# got none of them (Copilot round 3 on openRepoTools#47):
#
#   * A LOCK WITH NO PID IN IT IS STALE, NOT ETERNAL. The pid is written the
#     instant after `mkdir` returns, and a run killed in that instant leaves a
#     directory nothing can validate — which the first shape waited on for ever,
#     blocking the estate's one test entry point.
#   * A TAKEOVER IS A CLAIM, NOT A DELETE. Two waiters that both see a dead
#     holder both `rm -rf` the name; if one has already re-made it, the other
#     deletes the NEW holder's lock and both suites run. The claim is a
#     `mv` — one rename, one winner — and the loser simply loops.
#   * AND THE CLAIM IS RE-READ AFTER THE RENAME, because the only way a live
#     holder can be behind that name is if it appeared between the read and the
#     rename. It is put straight back where that is what happened.
#
# A stale state must also HOLD for three polls (a minute) before it is claimed:
# a holder that is merely slow to write its pid is not a holder to evict.
LOCKDIR="$LOCK.d"
stale_polls=0
while ! mkdir "$LOCKDIR" 2>/dev/null; do
  holder="$(cat "$LOCKDIR/pid" 2>/dev/null || printf '')"
  stale=0
  case "$holder" in
    ''|*[!0-9]*) stale=1 ;;                       # no pid yet, or an unreadable one
    *) kill -0 "$holder" 2>/dev/null || stale=1 ;;
  esac
  if [ "$stale" = 1 ]; then
    stale_polls=$((stale_polls + 1))
    if [ "$stale_polls" -ge 3 ]; then
      claim="$LOCK.claimed.$$"
      if mv -- "$LOCKDIR" "$claim" 2>/dev/null; then
        # ONE RENAME, ONE WINNER — and then the re-read, because a live holder
        # behind that name means it appeared in the instant between the two.
        back="$(cat "$claim/pid" 2>/dev/null || printf '')"
        case "$back" in
          ''|*[!0-9]*) : ;;
          *) if kill -0 "$back" 2>/dev/null; then
               mv -- "$claim" "$LOCKDIR" 2>/dev/null || :
               printf '%s: %s is held by pid %s after all — waiting\n' "$prog" "$LOCKDIR" "$back" >&2
               stale_polls=0
               sleep 20
               continue
             fi ;;
        esac
        printf '%s: the lock %s was left by %s, which is gone — taken over\n' \
          "$prog" "$LOCKDIR" "${holder:-a run that died before writing its pid}" >&2
        rm -rf -- "$claim"
        continue
      fi
    fi
  else
    stale_polls=0
  fi
  printf '%s: waiting for the suite holding %s\n' "$prog" "$LOCKDIR" >&2
  sleep 20
done
printf '%s\n' "$$" > "$LOCKDIR/pid" 2>/dev/null || :
# THE SIGNAL HANDLERS EXIT, and that is the whole point of writing them out
# separately: a handler that only cleans up and RETURNS releases the lock while
# this suite carries on running, which is the collision the lock exists for.
LOCKDIR_HELD="$LOCKDIR"
trap cleanup EXIT
trap 'on_signal 130' INT
trap 'on_signal 143' TERM
wait_for_pytest "inside the lock"
make_run_root
run_suite ${1+"$@"}
exit $?
