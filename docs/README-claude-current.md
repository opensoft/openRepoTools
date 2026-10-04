# `claude-current` and `claude-restart-check`

Two commands `openRepoTools --install` places in `~/.local/bin` beside
`lane-start`, since opensoft/workBenches#119:

- **`claude-current`** answers which Claude Code a launch should start: the
  version npm publishes, updated first when every installed copy is behind,
  checked with `--version`, and named by an absolute path. `lane-start` calls
  it, and so does workBenches' `claude-profile`.
- **`claude-restart-check`** prints one green `RESTART NEEDED` line when a
  running session's Claude Code has been replaced on disk. workBenches' shared
  status line prints that line.

Brett Heap ruled on #119 on 2026-09-29. The home ruling, verbatim *"this work
is really for openRepoTools repo"*, puts both commands here. Point 2, verbatim
*"for 2, we can run update on every start, this ensures we have the latest
models"*, is why every launch runs the check. The workBenches side is the
ratified OpenSpec change `launch-current-claude` (opensoft/workBenches#120).

## Why

A lane started on an old Claude Code, and nothing noticed. Two npm installs
competed on `PATH`: the image's root-owned copy, frozen when the image was
built, and the user's own `~/.npm-global` copy. Which one a lane got depended
on the shell that launched it. A session loads the served model catalog when it
starts, so a session that ran 2.1.283 for twenty hours did not list a model
that a fresh `claude` on the same account listed. The same session kept running
the binary npm had replaced under it, and nothing told it to restart.

## `claude-current`

```sh
claude-current                 # the absolute path, one line on stdout
claude-current --porcelain     # path=, version=, published=, status=
claude-current --offline       # no npm read and no update: newest installed
```

It never resolves `claude` through `PATH`. It reads these candidates by
absolute path, in this order, and runs each one's `--version`:

1. the newest native version in `~/.local/share/claude/versions`, by its
   x.y.z name (workBenches #109's ordering);
2. `<user npm prefix>/bin/claude`. The prefix is `$CLAUDE_CURRENT_NPM_PREFIX`,
   else `$NPM_CONFIG_PREFIX`, else `$npm_config_prefix`, else the `prefix=`
   line of `~/.npmrc`, else `~/.npm-global`. A relative prefix is taken under
   `$HOME`, so the path npm installs into is the path read back;
3. `~/.local/bin/claude`;
4. the image's copies, `/usr/local/bin/claude` and `/usr/bin/claude`
   (`$CLAUDE_CURRENT_SYSTEM_CANDIDATES`, colon-separated; set it empty for
   none).

A path that resolves to a file already read is read once, under its first
spelling, which is the user-writable one.

It then asks npm, bounded by `$CLAUDE_CURRENT_TIMEOUT` seconds:
`npm view @anthropic-ai/claude-code version --prefer-online`.

| What it finds | What it answers | `status` |
|---|---|---|
| a candidate at npm's version | the first such candidate | `verified` |
| none equal, one newer than npm | the newest newer one | `ahead` |
| npm could not be read | the newest candidate, and says `UNVERIFIED` | `unverified` |
| every candidate behind npm, or none installed | it updates, then reads again (below) | |
| still behind after the update | exit 2, a refusal naming the fix | |
| still behind, `CLAUDE_ALLOW_STALE=1` | the newest candidate, and says `STALE` | `stale` |

An equal candidate beats a newer one. `ahead` is a launch, not a refusal.
"Newer" is SemVer's order, in both commands alike: numeric on x.y.z, a
release above its own pre-releases, and pre-release identifiers compared
one by one, numbers as numbers (`beta.9` before `beta.10`) and words in byte
order. Build metadata after a `+` is ignored.

**The update runs under a lock** at
`${XDG_CACHE_HOME:-~/.cache}/openrepotools/claude-current.lock.l`, the same one
for every launch whatever its `PATH` holds (`flock` is never used, so two
launches can never hold two different locks): a symlink whose text names its
owner, `pid=<pid>@<place>`. One `ln -s` makes that lock and names its owner,
so no lock is ever left without one. `<place>` is the host's name and, on
Linux, the pid namespace's inode, because containers that share a home share
the lock and a pid from another namespace says nothing about its owner. A lock
made at another place is waited on and never taken over, and the refusal names
its owner and place. A lock made here whose owner has died is taken over, by
one launch only: the one that holds a second directory, the reaper, while it
reads the owner again.
After it takes the lock it reads the candidates again, because another launch
may have updated while it waited. A lock it cannot take within
`CLAUDE_CURRENT_LOCK_WAIT` seconds is a refusal, unless that other launch's
update has already produced npm's version. A native install gets
`claude update`. When that does not reach npm's version, or there is no
native install, it runs
`npm install -g --prefix <user prefix> @anthropic-ai/claude-code@<published>`.
If `--version` still differs after that, it runs the package's own
`install.cjs` with `node`. npm 12's install-script policy skips that hook, so
until it runs the launcher npm links can be a stub. The shared image runs the
same hook by hand. Everything an update prints goes to stderr.

**Output.** stdout carries the path, or with `--porcelain` exactly four lines:

```text
path=<absolute path>
version=<x.y.z>
published=<x.y.z, or empty when npm could not be read>
status=<verified|ahead|unverified|stale>
```

stderr carries one line saying what was chosen, for example
`claude-current: claude 2.1.284 (verified against npm 2.1.284) at <path>`.
A refusal prints nothing on stdout.

**Exit.** 0 resolved; 1 no runnable Claude Code at all; 2 refused, because
every candidate is still behind npm after the update; 64 usage, including a
`CLAUDE_CURRENT_*` bound that is not a whole number of seconds. 64 is kept
apart from 1 because a launcher reports 1 as "no Claude Code".

| Variable | Default | What it is |
|---|---|---|
| `CLAUDE_ALLOW_STALE` | unset | `1` answers with a stale copy instead of refusing, and says `STALE` |
| `CLAUDE_CURRENT_NPM` | `npm` | the npm to run |
| `CLAUDE_CURRENT_NODE` | `node` | the node that runs `install.cjs` |
| `CLAUDE_CURRENT_TIMEOUT` | `10` | seconds for `npm view` |
| `CLAUDE_CURRENT_VERSION_TIMEOUT` | `10` | seconds for each `--version` |
| `CLAUDE_CURRENT_UPDATE_TIMEOUT` | `300` | seconds for each update command |
| `CLAUDE_CURRENT_LOCK_WAIT` | `330` | seconds to wait for another launch's update |
| `CLAUDE_CURRENT_CACHE_DIR` | `${XDG_CACHE_HOME:-~/.cache}/openrepotools` | where the lock lives; relative overrides or `XDG_CACHE_HOME` paths are taken under `$HOME` |
| `CLAUDE_CURRENT_NPM_PREFIX` | see candidate 2 | the user npm prefix, the one place an update writes |
| `CLAUDE_CURRENT_NATIVE_DIR` | `~/.local/share/claude/versions` | the native versions directory |
| `CLAUDE_CURRENT_SYSTEM_CANDIDATES` | `/usr/local/bin/claude:/usr/bin/claude` | the image's copies |

The timeouts use `timeout`, else Homebrew's `gtimeout`, else a watchdog of its
own, because a stock macOS ships neither. The watchdog ends the command's whole
process tree, as `timeout` ends its process group, so a child npm started
cannot hold the answer open past the bound. On every branch a command that
ignores TERM is sent KILL five seconds later.

## The hand-off

A launcher that starts the path `claude-current` answered exports three
variables to what it launches next:

- `CLAUDE_BIN=<path>`
- `CLAUDE_RESOLVED_BIN=<the same path>`
- `CLAUDE_VERIFIED_VERSION=<version>`

`CLAUDE_VERIFIED_VERSION` never reaches a running session. `lane-start` and
`claude-profile` both remove it before they start one. `CLAUDE_BIN` and
`CLAUDE_RESOLVED_BIN` may reach it, and that is what lets a later launch tell
an inherited answer from an operator's pin:

| The environment a launch finds | What it is | What the launch does |
|---|---|---|
| no `CLAUDE_BIN` | nothing chosen yet | resolves through `claude-current` |
| `CLAUDE_BIN` = `CLAUDE_RESOLVED_BIN`, no `CLAUDE_VERIFIED_VERSION` | an earlier launch's answer, inherited from a session's environment | resolves again |
| `CLAUDE_BIN` = `CLAUDE_RESOLVED_BIN` and `CLAUDE_VERIFIED_VERSION` | a launcher's answer, handed on | trusts it, and records the version |
| any other `CLAUDE_BIN` | an operator's pin | launches it as it is, with no check |

## `lane-start`

`lane-start` applies that table after confirmation and any handoff approval.
Resolution precedes a binding release, window rename or transcript move (and
also runs in the bare launch described below):

A binding held elsewhere must be approved for handoff before any resolver
call. Before releasing it, an implicit-agent handoff preflights a possible
Claude launch because the holder's new `PAUSED` record may name Claude. After
handoff, the agent is read afresh from that record. An explicit other agent
skips the Claude preflight. A declined handoff performs no update.
After resolution, the binding is read again immediately before the window
rename. A lane taken or changed during the update wait is refused; an unchanged
existing binding can continue.

- It looks for `claude-current` beside itself, then in
  `$OPENREPOTOOLS_BIN_DIR` (default `~/.local/bin`), and never on `PATH`. A
  sandbox that copies `lane-start` without it, as the lane suite does, launches
  the `claude` its own `PATH` names, and no test reaches a real npm.
- It runs `claude-current --porcelain` with stdin from `/dev/null`. The
  resolver's stderr goes straight to the operator.
- Exit 0: the launch command's first word becomes the absolute path.
  `CLAUDE_BIN` and `CLAUDE_RESOLVED_BIN` are exported with that path, and one
  line says `launching claude <version> (<status>) at <path>`.
- Exit 2 ends `lane-start` with 2, and any other failure with 1. Either way
  no binding handoff is requested, the window is not renamed, no transcript is
  moved, and the row, object log and handoff's Rule 3 stamp are not written.
- With no `claude-current` installed, one note says so, and `CLAUDE_BIN`
  (`claude` from `PATH` when unset) is launched unchecked, as before.
- `--dry-run` prints a `PLAN` line naming the call and runs nothing, because
  the resolver may update. `--no-launch` resolves nothing: it is the first act
  inside a running session and launches nothing.
- An explicit other agent skips it. With a free binding, only the selected
  `claude` agent asks. `--agent codex` launches `codex` as before.

The lane's `STARTED` or `RESUMED` log line records the version as one more
sub-field, `claude <version>`, when a version is in hand: read by
`claude-current` in this run, or handed on as `CLAUDE_VERIFIED_VERSION`. For
example:

```text
STARTED — lane repoZ-1, session <uuid>@Eagle, <UTC>, lane:repoZ-1 → home opensoft/repoZ; estate repoZ; dir <dir>; window testsess:0 @1; claude 2.1.284
```

A pinned launch records no version, and neither does a line written by the
deferred `--no-launch` act. A value that is not x.y.z is left off with a note,
because the log is append-only.

A `--confirm` answered No launches Claude bare, without a lane and writing
nothing, and that launch resolves the same way, refusal included. It is the
one launch that happens before step 4.

## `claude-restart-check`

```sh
claude-restart-check [--running <version>] [--pid <pid>]
```

It walks at most three processes, from `--pid` (default: its own parent) up
through their parents, to the first one whose `/proc/<pid>/exe` is a Claude
Code binary: a native version file (`…/claude/versions/<x.y.z>`), or the npm
package's `…/node_modules/@anthropic-ai/<dir>/bin/claude.exe`. The status line
runs its command under `/bin/sh -c`, and dash does not `exec` it, so claude is
the status line script's grandparent. That was measured on a live bench on
2026-09-29.

It warns when either of these holds:

- **The binary was replaced**: that exe link ends in ` (deleted)`. npm renames
  the old package directory before deleting it, so the running exe's path
  names a directory that no longer exists, and it cannot give the running
  version.
- **The installed version is newer than the running one.** The installed
  version is the highest of three, each read from disk: the running install's
  own (the highest x.y.z name beside a native version file, or the `version`
  in the npm package's `package.json` at its canonical path), the native
  versions directory (`$CLAUDE_CURRENT_NATIVE_DIR`, default
  `~/.local/share/claude/versions`), and the package in the user npm prefix,
  found the way `claude-current` finds it. So a session on the npm copy is
  told about a newer native install. The
  running version is `--running` (the status line JSON's `version`), else the
  native file's own name.

The warning is exactly one line, green unless `NO_COLOR` is set. A replaced
binary asks for a restart:

```text
RESTART NEEDED: running 2.1.283, installed 2.1.284; /ctx at your next breakpoint
```

When only another installed version is newer, the notice leaves the selection
to the next launch's registry check:

```text
NEWER COPY INSTALLED: running 2.1.284, installed 2.1.285; /ctx checks npm before selecting a version
```

`claude-current` prefers a candidate equal to npm's published version over an
ahead candidate. This disk-only check cannot predict that choice, so a newer
installed copy alone is not labelled `RESTART NEEDED`.

It never acts. There is no kill and no automatic `/ctx`, because a working
session is never interrupted. It reads `/proc`, one directory listing and a
few small files, reaches no network and runs no binary, so the render is not
slowed by a `claude --version`. It always exits 0, on a host with no `/proc` such as macOS too,
where it prints nothing: a status line must never break on this. 64 is kept
for an argument it does not know. `CLAUDE_RESTART_CHECK_PROC` (default
`/proc`) is the test seam.

The status line that calls it is workBenches'
`base-image/files/claude-statusline-command.sh`, which
`scripts/setup-claude-profiles.sh` installs as the profiles' shared
`statusline-command.sh`.

## Portability

Both commands parse and run under bash 3.2, which is what macOS ships. Neither
uses `mapfile`, associative arrays, `readlink -f` or GNU-only flags.
`tests/test_claude_current.py`, `tests/test_claude_restart_check.py` and
`tests/test_lane_start_claude_current.py` are their suites, and every one of
them runs against fakes. None reaches npm or runs a real Claude Code.
