# SPDX-License-Identifier: Apache-2.0
"""Stand-ins for feature 007's SQL-register tests (L2-0d): the copies and the
stubs of `lanes-index`, and the `psql`s a test puts first on `PATH`.

Test modules import it from `tests/`, as three modules import
`package_layout.py`. What it holds:

- `flipped_copy(source, dest, value)`: `source`, a `lanes-index`, copied to
  `<dest>/lanes-index` with its one `RENDER_GIT_HALF = …` line rewritten to
  `value`, True or False. It takes the constant in either state, so test 14's
  refusing copy still builds once lane 3's T328 sets it True (T277). There is
  no environment override, which would be a production bypass of Q6(c)'s
  refusal (the test plan's open point 3; PC-5). `dest` is a directory, so a
  test copies `lanes-edit.sh` and what it reads beside the copy, where
  `lanes-index` and `lanes-edit.sh` each look for the other.
- `primary_stub(directory)`: a stub `lanes-index` for the bash tests, at
  `<directory>/lanes-index`, that answers `mode` with `primary` and logs every
  call. The contract's whole stub is T207's `contract_stub`.
- `REGISTER_FAKE_PSQL`: the register's fake `psql` (the test plan's section
  3.2), which extends `test_lanes_index.py`'s `FAKE_PSQL`.
- `PSQL_SHIM`: section 3.2's shim in front of the real `psql`, armed per test
  by a control file beside it.
- `contract_stub(directory, register=None)` and `stub_outcome(directory,
  argv_prefix, …)`: the contract's stub `lanes-index`, as CLI4.5 §6 states
  it, and the outcomes a test injects into it (T207). `contract_stub`'s
  docstring is its manual.
- `guard_session(home, directory, cwd, ...)`, `guard_strip_env(...)` and
  `GUARD_ENV_STRIP`: what a case gives `lanes-edit.sh guard` before it runs
  it, so that the guard gets past its session-record check to its register
  read (T203c): a live session record on this workstation, a stand-in `tmux`
  that answers the guard's window queries, the compact hook JSON, and the
  environment with the variables that would steer the guard elsewhere taken
  out. `guard_session`'s docstring is its manual.

THE FAKE-`psql` HOST RULE (lane 1's L1v4.5:525; #165 6741670709 item 9): the
fake and the shim are made for configurations whose `register_url=` names a
Unix socket or a loopback host (`localhost`, `127.0.0.0/8`, `::1`), or carries
`sslmode=verify-full` with an `sslrootcert=` naming a root file, never
`system`. Lane 1's T104 refuses any other at load (CLI4.5 §2.5), before any
`psql` runs.

THE ARGV LOG: each stub writes `<directory>/lanes-index.argv`, one line per
call, the call's arguments as one JSON array, so a test can assert that the
stub ran and what it was asked.

THE REGISTER'S FAKE `psql`. A test writes `REGISTER_FAKE_PSQL` to `<dir>/psql`,
makes it executable and puts `<dir>` first on `PATH`. Its environment:

- `FAKE_PSQL_LOG` (required) names its log: one JSON object per call, in call
  order, with `FAKE_PSQL`'s fields, `url`, `passfile`, `pgpassword` and
  `stdin`, and these besides:
  - `call`, the call's number in this log, from 1, counting only the calls
    that carry a request: a `psql --version` call is not counted (below);
  - `argv`, the whole argument list (P1475): what each path sends is the
    test's to assert, and the fake asserts no `VERBOSITY` for the calls the
    design leaves unnamed (the test plan's open point 29);
  - `connect_timeout`, `options` and `service`: `PGCONNECT_TIMEOUT`,
    `PGOPTIONS` (the path's `options=-c lock_timeout=… -c
    statement_timeout=…`) and `PGSERVICE`, each null where it is unset;
  - `pg`: every variable it received whose name begins `PG`, with its value,
    `PGPASSWORD`'s alone recorded as `*`, for T257's inherited-`PG*` cases
    (lane 3's R-PG-1, #165 6747611042).

  `url` is the connection rebuilt from the `PG*` variables, as lane 1's T103
  hands it on, `postgresql://<PGUSER>@<PGHOST>[:<PGPORT>]/<PGDATABASE>`, with
  no port where `PGPORT` is unset, and empty where none of the four is set.
- An argument that is `-d`, `--dbname` or one that holds a connection URL is
  refused: the call is logged with `refused`, and the fake exits 1. No
  register path puts a connection string in an argument list (Y:3491; CLI4.5
  §2.2 and §6).
- `psql --version`, a call whose whole argument list is `--version`, is a
  call of its own kind. Lane 1's T106 runs it once per process on a register
  path, before it sends anything, and refuses a `psql` older than 15 with 69,
  naming its version, with nothing sent (L1v4.10:152; lane 1, #165
  6752661856). The fake reads no stdin for it and answers `psql (PostgreSQL)
  16.4` (`PSQL_VERSION_LINE`) with exit 0, unless a `version` rule in
  `FAKE_PSQL_ANSWERS` answers it. Its log entry is
  `{"kind": "version", "url": …, "passfile": …, "pgpassword": …, "argv":
  ["--version"], "connect_timeout": …, "options": …, "service": …, "pg":
  {…}}`, with no `call` and no `stdin`. So the calls that carry a request are
  the entries with no `kind`, a case counting them leaves the probe out
  (`e.get("kind") != "version"`), and their `call` numbers are the ones a
  test without the probe sees.
- `FAKE_PSQL_ANSWERS` (optional) names a JSON file: a list of answers, each
  taught for the calls it names. The first that names a call answers it:
  - it names calls by `call` (that call alone), `from` (every call from that
    one on) and `match` (a text the call's stdin carries), all that it gives
    holding; an answer with none of the three names every call;
  - it answers with `sleep` (seconds, before anything else: a hang past the
    caller's timer), then `stdout` and `stderr`, then `signal` (a name, such
    as `KILL`, that the fake sends itself: a death by a signal) or `exit`
    (default 0);
  - a rule with `"kind": "version"` names the `psql --version` calls, every
    one, and only them: it takes no `call`, `from` or `match`, and answers
    as any rule does. Every other rule names only the calls that carry a
    request. So T257's `[snapshot-psql-14]` teaches `{"kind": "version",
    "stdout": "psql (PostgreSQL) 14.11\\n"}`, and a `--version` that hangs or
    fails is taught with `sleep` or `exit`.

  So the 69 refusal is `{"call": 1, "exit": 2}`; the retry's shape is
  `{"match": "commit_write", "exit": 3, "stderr": "ERROR:  40001: could not
  serialize access due to concurrent update\\n"}`; and a code taught for exit
  3 is taught as `ERROR:  <SQLSTATE>: <message>`, an LR005 or an LR007 with its
  `DETAIL:  <token>` line after it (section 3.2, "The line it is taught").
- A call no answer names is answered as `FAKE_PSQL` answers it, as an empty
  schema-1 store would, with `FAKE_PSQL_VERSION_FILE` read as it reads it.

THE SHIM. A test writes `PSQL_SHIM` to `<dir>/psql`, makes it executable,
puts `<dir>` first on `PATH`, ahead of the directory of the real `psql`, and
arms it by writing `<dir>/psql-shim.json`. It runs as `python3 -I`, standard
library only. With no control file it hands every call on unchanged. The
control file:

- `psql` (optional): the real `psql` to hand calls to; otherwise the first
  `psql` on `PATH` that is not the shim.
- `version` (optional): the line the shim answers `psql --version` with,
  `psql (PostgreSQL) 16.4` (`PSQL_VERSION_LINE`) where it is absent, such as
  `"psql (PostgreSQL) 14.11"` for T257's `[snapshot-psql-14]`. A call whose
  whole argument list is `--version` (lane 1's T106 probe, once per process
  on a register path: L1v4.10:152) is answered by the shim itself, that line
  and exit 0, and is never handed on: it reads no stdin, no arm applies to it,
  and it is not counted in `call`, `from` or the state.
- `arms`: a list, each arm a mode and the calls it applies to. An arm names
  calls by `call` (call k alone), `from` (every call from call k on) or
  `match` (a text the call's script carries, such as `find_write` for a
  lookup try or `commit_write` for a commit call). With `match`, `call` and
  `from` count only the calls that carry the text, so `{"match":
  "commit_write", "call": 2}` is the second commit call. An arm with none of
  the three applies to every call. One test may arm several modes, each on
  its own calls.

The modes, with the keys each takes:

- `window`, `ms`: sleep before handing the call on;
- `before` and `after`: a `pg_terminate_backend(pg_backend_pid())` statement
  before or after the script's last `COMMIT`, joined with psql's `\\;`, so the
  call stays one request. `after` exits 2 once the call has landed; with
  `fifo`, it first blocks on that FIFO;
- `timer`, `ms` or `fifo`: run the real `psql`, then sleep, or block on the
  FIFO in place of the sleep, then answer as `psql` answered;
- `fail-call` (by `call` or `from`) and `fail-match` (by `match`): exit 2,
  sending nothing;
- `edit-entry`, `field` and `value`: rewrite one field of the commit call's
  entry, the `'…'::jsonb` argument of `commit_write(`, before handing the
  call on. `field` may be a dotted path, such as `act.base`, and must exist.
  A part that meets a list is an index into it, a negative one counting from
  the list's end, so `register_lines.-1.workstation` is the last
  `register_lines` row's `workstation` (T203d); an index past either end is a
  field that is not there. Without `value` the field, or the list's element,
  is removed;
- `no-reconnect`, `as` (`before` or `after`): the first call the arm names
  is lost as that mode loses it, and every later call exits 2, sending
  nothing, as from a host that cannot reconnect;
- `hold`, `fifo`: block on the FIFO before handing the call on. A test's
  `open(fifo, "w")` returns once the call is held, and closing it lets the
  call go;
- `fork`, `fifo`, optional `exit`: start the call in a session of its own
  (`setsid`), where it blocks on the FIFO before it runs the real `psql`, and
  wait for it, so the caller's timer, which kills the shim, never reaches
  the call. With `"exit": true` the shim exits 2 once the fork is made.

Per call, the failures come first (a lost host, then `fail-call` and
`fail-match`), then `edit-entry`, `before` and `after` rewrite the script,
then `hold`, `window`, `fork`, the real `psql`, `after` and `timer`.

The shim writes, beside itself, `psql-shim.log`, one JSON object per call
when the call starts: `call`, `argv`, `stdin`, `sent` (the script as handed
on), `arms` (the modes applied), and the fake's `url`, `passfile`,
`pgpassword` and `pg`; `psql-shim.ends`, one line per call that ended, with
the codes; and its counters in `psql-shim.state`. A `psql --version` call's
entry in `psql-shim.log` is its own kind, `{"kind": "version", "argv":
["--version"], "url": …, "passfile": …, "pgpassword": …, "pg": {…}}`, with
no `call`, and it writes nothing to `psql-shim.ends` or the state, so the
calls that carry a request are the entries with no `kind`. A control file it
cannot read, an arm it does not know, or an arm that cannot apply to the call
it names (a `before` on a call with no `COMMIT`, an `edit-entry` field that is
not there) ends the call with exit 1 and `psql-shim: …` on stderr, recorded
in the log as `error`, sending nothing; on a `--version` call, so does a
control file it cannot read or a `version` that is not a string.

STANDARD LIBRARY ONLY, AND NOTHING FROM THE SUITE: no `conftest`, no pytest,
so the module loads the same way under pytest and under a task's
`python3 -I -c` verify, on Python 3.9 and up. Each script it writes is
standard library only too.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

#: THE CODE ROOT: the parent of this file's `tests/`, and the `lanes-index` in
#: it, which `flipped_copy` copies.
REPO = Path(__file__).resolve().parent.parent
LANES_INDEX = REPO / "lanes-index"

#: Q6(c)'S CONSTANT, AS `lanes-index` SPELLS IT (lane 1's T105): one line,
#: `RENDER_GIT_HALF = False` until lane 3's T328 sets it True.
RENDER_GIT_HALF_LINE = re.compile(rb"^RENDER_GIT_HALF = (True|False)$", re.M)

#: The name of each stub's argv log, beside the stub.
ARGV_LOG = "lanes-index.argv"

#: The shim's own files, beside it.
PSQL_SHIM_CONTROL = "psql-shim.json"
PSQL_SHIM_LOG = "psql-shim.log"
PSQL_SHIM_ENDS = "psql-shim.ends"

#: The shim's ten modes (the test plan's section 3.2).
PSQL_SHIM_MODES = ("window", "before", "after", "timer", "fail-call", "fail-match",
                   "edit-entry", "no-reconnect", "hold", "fork")

#: WHAT BOTH `psql`s ANSWER `psql --version` WITH, unless a test names another
#: (the fake's `version` rule, the shim's `version` key): a `psql` lane 1's
#: T106 accepts, 15 or later (L1v4.10:152). Each script holds this text too.
PSQL_VERSION_LINE = "psql (PostgreSQL) 16.4"


def flipped_copy(source, dest, value) -> Path:
    """Copy the `lanes-index` at `source` to `<dest>/lanes-index`, its
    `RENDER_GIT_HALF` line rewritten to `value`, and return the copy's path.

    The copy is the source's bytes but that one line, with the executable bit.
    `dest` is made if it is missing. A source with no such line, or with more
    than one, is refused, so a test never runs a copy it did not flip."""
    if not isinstance(value, bool):
        raise TypeError(f"flipped_copy: value must be True or False, not {value!r}")
    text = Path(source).read_bytes()
    found = RENDER_GIT_HALF_LINE.findall(text)
    if len(found) != 1:
        raise ValueError(f"flipped_copy: {source} holds {len(found)} `RENDER_GIT_HALF = ` "
                         f"lines, not one")
    directory = Path(dest)
    directory.mkdir(parents=True, exist_ok=True)
    copy = directory / "lanes-index"
    copy.write_bytes(RENDER_GIT_HALF_LINE.sub(b"RENDER_GIT_HALF = " + str(value).encode(), text))
    copy.chmod(0o755)
    return copy


#: THE STUB FOR THE BASH TESTS (R2's S8): a Python script a test runs by its
#: path. `mode` alone is answered, `primary`; anything else is not stubbed,
#: and ends 64 with that said, so a test sees what reached it.
_PRIMARY_STUB = r'''#!/usr/bin/env python3
# A STUB lanes-index (feature 007, L2-0d): it answers `mode` with `primary`
# and logs every call, one JSON array of arguments per line. Nothing else is
# stubbed here: the contract's whole stub is contract_stub (T207).
import json, sys

with open(ARGV_LOG_PATH, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\n")
if sys.argv[1:] == ["mode"]:
    sys.stdout.write("primary\n")
    sys.exit(0)
sys.stderr.write("lanes-index: this stub answers only `mode`: %s\n" % json.dumps(sys.argv[1:]))
sys.exit(64)
'''


def primary_stub(directory) -> Path:
    """Write `<directory>/lanes-index`, the stub that answers `mode` with
    `primary` and logs every call to `<directory>/lanes-index.argv`, and
    return its path. `directory` is made if it is missing."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stub = directory / "lanes-index"
    log = str((directory / ARGV_LOG).resolve())
    stub.write_text(_PRIMARY_STUB.replace("ARGV_LOG_PATH", repr(log)), encoding="utf-8")
    stub.chmod(0o755)
    return stub


REGISTER_FAKE_PSQL = r'''#!/usr/bin/env python3
# The REGISTER's FAKE psql (feature 007, L2-0d; the test plan's section 3.2).
# It extends test_lanes_index.py's FAKE_PSQL: it records what FAKE_PSQL
# records, the URL (rebuilt from the PG* variables), PGPASSFILE, whether
# PGPASSWORD is set, and stdin, and also the call's number, the whole argv,
# PGCONNECT_TIMEOUT, PGOPTIONS, PGSERVICE and every PG* variable it received.
# A test may teach it an answer per call (FAKE_PSQL_ANSWERS); otherwise it
# answers as FAKE_PSQL does. No database exists. It asserts no VERBOSITY.
# `psql --version` (lane 1's T106 probe) is a call of its own kind: answered
# DEFAULT_VERSION, or by a {"kind": "version"} rule, logged with
# "kind": "version" and never counted in `call`.
import fcntl, json, os, signal, sys, time

DEFAULT_VERSION = "psql (PostgreSQL) 16.4"
log = os.environ["FAKE_PSQL_LOG"]
answers = os.environ.get("FAKE_PSQL_ANSWERS", "")
vfile = os.environ.get("FAKE_PSQL_VERSION_FILE", "")
version = open(vfile).read().strip() if vfile else "1"
args = sys.argv[1:]
asks_version = args == ["--version"]
stdin = "" if asks_version else sys.stdin.read()
env = os.environ
url = ""
if any(env.get(k) for k in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER")):
    url = "postgresql://%s@%s%s/%s" % (env.get("PGUSER", ""), env.get("PGHOST", ""),
                                      ":" + env["PGPORT"] if env.get("PGPORT") else "",
                                      env.get("PGDATABASE", ""))
record = {"url": url, "passfile": env.get("PGPASSFILE", ""), "pgpassword": "PGPASSWORD" in env,
          "stdin": stdin, "argv": args, "connect_timeout": env.get("PGCONNECT_TIMEOUT"),
          "options": env.get("PGOPTIONS"), "service": env.get("PGSERVICE"),
          "pg": {k: ("*" if k == "PGPASSWORD" else v) for k, v in sorted(env.items())
                 if k.startswith("PG")}}
# NO CONNECTION STRING IN THE ARGUMENTS (Y:3491; CLI4.5 section 2.2 and 6).
refused = [a for a in args if a == "--dbname" or a.startswith("--dbname=") or
           (a.startswith("-d") and not a.startswith("--")) or
           "postgresql://" in a or "postgres://" in a]
if refused:
    record["refused"] = "a connection string or -d in the arguments: %s" % json.dumps(refused)
if asks_version:
    record = dict({"kind": "version"}, **{k: v for k, v in record.items() if k != "stdin"})
with open(log, "a+", encoding="utf-8") as handle:
    fcntl.flock(handle, fcntl.LOCK_EX)
    handle.seek(0)
    # `call` counts the calls that carry a request: never a --version entry.
    call = sum(1 for line in handle if not line.startswith('{"kind": "version"')) + 1
    if not asks_version:
        record = dict({"call": call}, **record)
    handle.write(json.dumps(record) + "\n")
if refused:
    sys.stderr.write("psql: error: the fake refuses %s\n" % record["refused"])
    sys.exit(1)


def taught():
    # A {"kind": "version"} rule names every --version call and only them;
    # every other rule names only the calls that carry a request.
    if not answers:
        return None
    with open(answers, encoding="utf-8") as handle:
        rules = json.load(handle)
    for rule in rules:
        if (rule.get("kind") == "version") != asks_version:
            continue
        if asks_version:
            return rule
        if "call" in rule and rule["call"] != call:
            continue
        if "from" in rule and call < rule["from"]:
            continue
        if "match" in rule and rule["match"] not in stdin:
            continue
        return rule
    return None


rule = taught()
if rule is not None:
    if rule.get("sleep"):
        time.sleep(float(rule["sleep"]))
    sys.stdout.write(rule.get("stdout", ""))
    sys.stderr.write(rule.get("stderr", ""))
    sys.stdout.flush()
    sys.stderr.flush()
    if rule.get("signal"):
        os.kill(os.getpid(), getattr(signal, "SIG" + rule["signal"]))
        time.sleep(5)
    sys.exit(int(rule.get("exit", 0)))
if asks_version:
    sys.stdout.write(DEFAULT_VERSION + "\n")
    sys.exit(0)
if vfile and "CREATE TABLE IF NOT EXISTS" in stdin:
    with open(vfile, "w") as handle:
        handle.write("1\n")


def echo(text):
    # `\echo` AS psql's OWN LEXER READS IT (opensoft/openRepoTools#166 item 4;
    # psqlscanslash.l's `xslashquote`), as test_lanes_index.py's FAKE_PSQL
    # reads it: words split on blanks, a quoted run taken whole, and inside
    # the quotes `''`, `\n \t \b \r \f`, octal `\ooo` and hex `\xhh` decoded.
    words, word, quoted, i = [], "", False, 0
    while i < len(text):
        ch = text[i]
        if not quoted and ch in " \t":
            if word:
                words.append(word)
                word = ""
            i += 1
        elif ch == "'" and quoted and text[i + 1:i + 2] == "'":
            word, i = word + "'", i + 2
        elif ch == "'":
            quoted, i = not quoted, i + 1
        elif quoted and ch == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            octal = len(text[i + 1:i + 4]) - len(text[i + 1:i + 4].lstrip("01234567"))
            hexes = len(text[i + 2:i + 4]) - len(text[i + 2:i + 4].lstrip("0123456789abcdefABCDEF"))
            if nxt in "ntbrf":
                word, i = word + {"n": "\n", "t": "\t", "b": "\b", "r": "\r", "f": "\f"}[nxt], i + 2
            elif octal:
                word, i = word + chr(int(text[i + 1:i + 1 + octal], 8)), i + 1 + octal
            elif nxt == "x" and hexes:
                word, i = word + chr(int(text[i + 2:i + 2 + hexes], 16)), i + 2 + hexes
            else:
                word, i = word + nxt, i + 2
        else:
            word, i = word + ch, i + 1
    if word:
        words.append(word)
    return " ".join(words)


for line in stdin.splitlines():
    if line.startswith("COPY (SELECT version"):
        if version:
            print(version)
    elif line.startswith("\\echo"):
        print(echo(line[len("\\echo"):]))
sys.exit(0)
'''


PSQL_SHIM = r'''#!/usr/bin/env -S python3 -I
# THE PSQL SHIM (feature 007, L2-0d; the test plan's section 3.2): one
# `python3 -I` script, standard library only, in front of the REAL psql, armed
# per test by psql-shim.json beside it. Its modes: window, before, after,
# timer, fail-call, fail-match, edit-entry, no-reconnect, hold and fork.
# `psql --version` (lane 1's T106 probe) it answers itself, DEFAULT_VERSION or
# the control file's `version`, logged with "kind": "version" and never counted.
# tests/sql_register_helpers.py's docstring is its manual.
import fcntl, json, os, re, signal, subprocess, sys, time

DEFAULT_VERSION = "psql (PostgreSQL) 16.4"
HERE = os.path.dirname(os.path.abspath(__file__))
CONTROL = os.path.join(HERE, "psql-shim.json")
LOG = os.path.join(HERE, "psql-shim.log")
ENDS = os.path.join(HERE, "psql-shim.ends")
STATE = os.path.join(HERE, "psql-shim.state")
LOCK = os.path.join(HERE, "psql-shim.lock")
MODES = ("window", "before", "after", "timer", "fail-call", "fail-match", "edit-entry",
         "no-reconnect", "hold", "fork")
KEYS = {"mode", "call", "from", "match", "ms", "fifo", "exit", "field", "value", "as"}
NEEDS = {"window": ("ms",), "hold": ("fifo",), "fork": ("fifo",), "edit-entry": ("field",),
         "no-reconnect": ("as",), "fail-match": ("match",)}
TERMINATE = "SELECT pg_terminate_backend(pg_backend_pid())"
COMMIT = re.compile(r"\bCOMMIT\b[ \t]*;?", re.I)
ENTRY = re.compile(r"'((?:[^']|'')*)'::jsonb")


class ShimError(Exception):
    pass


def arm_key(arm):
    return json.dumps(arm, sort_keys=True)


def check(arms):
    if not isinstance(arms, list):
        raise ShimError("`arms` is not a list")
    for arm in arms:
        if not isinstance(arm, dict) or arm.get("mode") not in MODES:
            raise ShimError("an arm with no mode of %s: %s" % (", ".join(MODES), json.dumps(arm)))
        unknown = sorted(set(arm) - KEYS)
        if unknown:
            raise ShimError("an arm with keys it does not know, %s: %s"
                            % (", ".join(unknown), json.dumps(arm)))
        for key in NEEDS.get(arm["mode"], ()):
            if key not in arm:
                raise ShimError("a `%s` arm needs `%s`: %s" % (arm["mode"], key, json.dumps(arm)))
        if arm["mode"] == "timer" and "ms" not in arm and "fifo" not in arm:
            raise ShimError("a `timer` arm needs `ms` or `fifo`: %s" % json.dumps(arm))
        if arm["mode"] == "no-reconnect" and arm["as"] not in ("before", "after"):
            raise ShimError("a `no-reconnect` arm's `as` is `before` or `after`: %s"
                            % json.dumps(arm))


def names(arm, call, script, state):
    # Whether `arm` names this call. With `match`, `call` and `from` count the
    # calls that carry the text (the count is kept in the state, per arm).
    number = call
    if "match" in arm:
        if arm["match"] not in script:
            return False
        seen = state.setdefault("seen", {})
        number = seen[arm_key(arm)] = seen.get(arm_key(arm), 0) + 1
    if "call" in arm and number != arm["call"]:
        return False
    if "from" in arm and number < arm["from"]:
        return False
    return True


def terminate(script, where):
    found = list(COMMIT.finditer(script))
    if not found:
        raise ShimError("`%s`: the call's script has no COMMIT" % where)
    m = found[-1]
    if where == "before":
        return script[:m.start()] + TERMINATE + " \\; " + script[m.start():]
    statement = script[m.start():m.end()].rstrip(" \t;")
    return script[:m.start()] + statement + " \\; " + TERMINATE + ";" + script[m.end():]


def step(node, key):
    # One part of `field`: in a list, a whole number is an index, a negative
    # one counting from the list's end (`register_lines.-1.workstation`, T203d);
    # every other part is the key as written, so a dict's path reads as before.
    if isinstance(node, list) and re.fullmatch(r"-?[0-9]+", key):
        return int(key)
    return key


def edit_entry(script, arm):
    at = script.find("commit_write(")
    if at < 0:
        raise ShimError("`edit-entry`: the call carries no commit_write(")
    m = ENTRY.search(script, at)
    if not m:
        raise ShimError("`edit-entry`: no '...'::jsonb entry after commit_write(")
    try:
        entry = json.loads(m.group(1).replace("''", "'"))
        path = arm["field"].split(".")
        node = entry
        for key in path[:-1]:
            node = node[step(node, key)]
        last = step(node, path[-1])
        if isinstance(last, int):
            if not -len(node) <= last < len(node):
                raise IndexError("list index %d out of range for %d items" % (last, len(node)))
        elif last not in node:
            raise KeyError(last)
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise ShimError("`edit-entry`: the entry has no field %s (%s)" % (arm["field"], exc))
    if "value" in arm:
        node[last] = arm["value"]
    else:
        del node[last]
    text = json.dumps(entry, ensure_ascii=False, separators=(",", ":")).replace("'", "''")
    return script[:m.start()] + "'" + text + "'::jsonb" + script[m.end():]


def real_psql(control):
    if control.get("psql"):
        return control["psql"]
    me = os.path.realpath(__file__)
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory or ".", "psql")
        if os.path.realpath(candidate) == me:
            continue
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise ShimError("no real psql on PATH behind the shim, and the control file names none")


def block(fifo):
    with open(fifo, "rb") as handle:
        handle.read()


def append(path, record):
    with open(path, "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(json.dumps(record) + "\n")


def connection():
    env = os.environ
    url = ""
    if any(env.get(k) for k in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER")):
        url = "postgresql://%s@%s%s/%s" % (env.get("PGUSER", ""), env.get("PGHOST", ""),
                                          ":" + env["PGPORT"] if env.get("PGPORT") else "",
                                          env.get("PGDATABASE", ""))
    return {"url": url, "passfile": env.get("PGPASSFILE", ""), "pgpassword": "PGPASSWORD" in env,
            "pg": {k: ("*" if k == "PGPASSWORD" else v) for k, v in sorted(env.items())
                   if k.startswith("PG")}}


def relay(out, err):
    sys.stdout.buffer.write(out)
    sys.stderr.buffer.write(err)
    sys.stdout.flush()
    sys.stderr.flush()


def text(data):
    return data.decode("utf-8", "surrogateescape")


def version(args):
    # `psql --version`, as lane 1's T106 asks it once per process (L1v4.10:152):
    # answered here, never handed on; no arm applies to it, it reads no stdin,
    # and it is not counted in the state or written to the ends.
    record = {"kind": "version", "argv": args}
    record.update(connection())
    error, line = "", DEFAULT_VERSION
    try:
        try:
            with open(CONTROL, encoding="utf-8") as handle:
                control = json.load(handle)
        except FileNotFoundError:
            control = {}
        except ValueError as exc:
            raise ShimError("the control file is not JSON: %s" % exc)
        if not isinstance(control, dict):
            raise ShimError("the control file is not a JSON object")
        line = control.get("version", DEFAULT_VERSION)
        if not isinstance(line, str):
            raise ShimError("`version` is not a string: %s" % json.dumps(line))
    except ShimError as exc:
        error = str(exc)
        record["error"] = error
    append(LOG, record)
    if error:
        sys.stderr.write("psql-shim: %s\n" % error)
        return 1
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
    return 0


def main():
    args = sys.argv[1:]
    if args == ["--version"]:
        return version(args)
    raw = sys.stdin.buffer.read()
    script = text(raw)
    record = {"argv": args, "stdin": script}
    record.update(connection())
    error = ""
    chosen, lost = [], False
    with open(LOCK, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(STATE, encoding="utf-8") as handle:
                state = json.load(handle)
        except FileNotFoundError:
            state = {}
        call = state["calls"] = state.get("calls", 0) + 1
        record = dict({"call": call}, **record)
        try:
            try:
                with open(CONTROL, encoding="utf-8") as handle:
                    control = json.load(handle)
            except FileNotFoundError:
                control = {}
            except ValueError as exc:
                raise ShimError("the control file is not JSON: %s" % exc)
            arms = control.get("arms", [])
            check(arms)
            chosen = [arm for arm in arms if names(arm, call, script, state)]
            if state.get("lost") and call > state["lost"]:
                lost = True
            for arm in chosen:
                if arm["mode"] == "no-reconnect" and not state.get("lost"):
                    state["lost"] = call
        except ShimError as exc:
            error = str(exc)
        with open(STATE + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        os.replace(STATE + ".tmp", STATE)
        modes = [arm["mode"] for arm in chosen]
        failing = [arm for arm in chosen if arm["mode"] in ("fail-call", "fail-match")]
        sent = script
        if not error and not lost and not failing:
            try:
                for arm in chosen:
                    if arm["mode"] == "edit-entry":
                        sent = edit_entry(sent, arm)
                for arm in chosen:
                    if arm["mode"] in ("before", "after"):
                        sent = terminate(sent, arm["mode"])
                    elif arm["mode"] == "no-reconnect" and state.get("lost") == call:
                        sent = terminate(sent, arm["as"])
                psql = real_psql(control)
            except ShimError as exc:
                error = str(exc)
        record.update({"sent": sent, "arms": modes})
        if error:
            record["error"] = error
        if lost:
            record["lost"] = True
        append(LOG, record)
    if error:
        sys.stderr.write("psql-shim: %s\n" % error)
        append(ENDS, {"call": call, "exit": 1, "error": error})
        return 1
    if lost or failing:
        why = "no-reconnect" if lost else failing[0]["mode"]
        sys.stderr.write("psql: error: connection to server failed: psql-shim %s (call %d)\n"
                         % (why, call))
        append(ENDS, {"call": call, "exit": 2, "failed": why})
        return 2
    for arm in chosen:
        if arm["mode"] == "hold":
            block(arm["fifo"])
    for arm in chosen:
        if arm["mode"] == "window":
            time.sleep(float(arm["ms"]) / 1000)
    after = [arm for arm in chosen if arm["mode"] == "after" or
             (arm["mode"] == "no-reconnect" and arm["as"] == "after" and state.get("lost") == call)]
    forks = [arm for arm in chosen if arm["mode"] == "fork"]
    data = sent.encode("utf-8", "surrogateescape")
    if forks:
        code, out, err = fork(forks[0], psql, args, data, call)
        if code is None:
            append(ENDS, {"call": call, "exit": 2, "forked": True})
            return 2
    else:
        proc = subprocess.run([psql] + args, input=data, capture_output=True)
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    for arm in after:
        if arm.get("fifo"):
            block(arm["fifo"])
    for arm in chosen:
        if arm["mode"] == "timer":
            if arm.get("fifo"):
                block(arm["fifo"])
            else:
                time.sleep(float(arm["ms"]) / 1000)
    relay(out, err)
    exit_code = 2 if after else code
    append(ENDS, {"call": call, "exit": exit_code, "psql": code})
    return exit_code


def fork(arm, psql, args, data, call):
    # The call in a session of its own, blocked on the FIFO before the real
    # psql runs; its answer goes to a file, never to the shim's pipes, which
    # the caller may have stopped reading.
    result = os.path.join(HERE, "psql-shim.fork-%d.json" % call)
    pid = os.fork()
    if pid == 0:
        code = 70
        try:
            os.setsid()
            null = os.open(os.devnull, os.O_RDWR)
            for fd in (0, 1, 2):
                os.dup2(null, fd)
            os.closerange(3, 1024)
            block(arm["fifo"])
            proc = subprocess.run([psql] + args, input=data, capture_output=True)
            code = proc.returncode
            with open(result + ".tmp", "w", encoding="utf-8") as handle:
                json.dump({"exit": code, "stdout": text(proc.stdout),
                           "stderr": text(proc.stderr)}, handle)
            os.replace(result + ".tmp", result)
            append(ENDS, {"call": call, "exit": code, "fork": os.getpid()})
        finally:
            os._exit(code)
    if arm.get("exit"):
        return None, b"", b""
    os.waitpid(pid, 0)
    with open(result, encoding="utf-8") as handle:
        answer = json.load(handle)
    return (answer["exit"], answer["stdout"].encode("utf-8", "surrogateescape"),
            answer["stderr"].encode("utf-8", "surrogateescape"))


def finish(code):
    # A psql that died by a signal: the shim dies by the same one, so the
    # caller reads a death by a signal, as it would from psql itself.
    if code < 0:
        try:
            signal.signal(-code, signal.SIG_DFL)
        except (OSError, ValueError):
            pass
        os.kill(os.getpid(), -code)
        time.sleep(5)
    sys.exit(code)


finish(main())
'''


#: THE RENDER SET'S PATHS (CLI4.5 §3.2): `lanes/LANES.md`, `lanes/aliases.tsv`,
#: each `lanes/log/<lane>.md` and `lanes/archive/*`. `lanes/repos.tsv` and
#: `lanes/log/README.md` come from the checkout, never from the register.
RENDER_SET_PATH = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|log/(?!README\.md$)[^/]+\.md"
                             r"|archive/[^/]+)$")

#: The contract stub's own files, beside it.
STUB_OUTCOMES = "lanes-index.outcomes"
STUB_RENDER_LOG = "lanes-index.render"


#: THE CONTRACT'S STUB `lanes-index` (T207; CLI4.5 §6, "What the fakes must
#: do", CLI4.5:881-903). Its manual is `contract_stub`'s docstring.
_CONTRACT_STUB = r'''#!/usr/bin/env python3
# THE CONTRACT'S STUB lanes-index (feature 007, L2-0d, T207), as CLI4.5
# section 6 states it: sections 3.1 to 3.5 exactly, section 3.6's four forms of
# `register read`, and section 3.7's argv record. Its register is the files
# under lanes-index.register/<seq>/ beside it, its journal and head are in
# lanes-index.state, and a test injects an outcome with stub_outcome. It logs
# every call to lanes-index.argv, one JSON array of arguments per line.
# tests/sql_register_helpers.py's contract_stub is its manual.
import datetime, fcntl, hashlib, importlib.machinery, importlib.util, json, os, re, shutil
import subprocess, sys, time, uuid

HERE = STUB_DIRECTORY
LANES_INDEX_SOURCE = LANES_INDEX_PATH
ARGV_LOG = os.path.join(HERE, "lanes-index.argv")
STATE = os.path.join(HERE, "lanes-index.state")
OUTCOMES = os.path.join(HERE, "lanes-index.outcomes")
RENDERS = os.path.join(HERE, "lanes-index.render")
REGISTER = os.path.join(HERE, "lanes-index.register")
LOCK = os.path.join(HERE, "lanes-index.lock")
SETS = os.path.join(HERE, "lanes-index.sets")

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
NUMBER = re.compile(r"^[0-9]+$")
# check_lane_name's class: letters, digits, `.`, `_` and `-`, not opening
# with `.` or `-`.
LANE_CLASS = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*$")
RENDER_SET = re.compile(r"^lanes/(LANES\.md|aliases\.tsv|log/(?!README\.md$)[^/]+\.md"
                        r"|archive/[^/]+)$")
ZEROS = "0" * 40
# Section 2.4 and 2.5 at their defaults: c = 2, N_a = 1, no service (w_s 0),
# and the commit's timer C = N_a.c + 6 s; schema_version.version is 1.
C, N_A, W_S_MS, SCHEMA = 2, 1, 0, 1
C_TIMER = N_A * C + 6
SECRET = re.compile(r"TOKEN|SECRET|PASSWORD|PASSWD|KEY", re.I)


class Exit(Exception):
    def __init__(self, code, out="", err=""):
        Exception.__init__(self, code)
        self.code, self.out, self.err = code, out, err


def usage(what):
    raise Exit(64, "", "lanes-index: usage: %s\n" % what)


def refuse(code, sqlstate, message, token=None):
    # Section 2.6: psql's ERROR line, then its DETAIL token, verbatim.
    raise Exit(code, "", "ERROR:  %s: %s\n" % (sqlstate, message)
               + ("DETAIL:  %s\n" % token if token else ""))


def options(args, values=(), equals=(), flags=(), positional=0):
    got, rest, i = {}, [], 0
    while i < len(args):
        arg = args[i]
        name, eq, value = arg.partition("=")
        if eq and name in equals:
            if name in got:
                usage("%s given twice" % name)
            got[name] = value
            i += 1
        elif arg in equals:
            usage("%s takes its value in the = form, %s=<key> (L1-D1)" % (arg, arg))
        elif arg in values:
            if arg in got:
                usage("%s given twice" % arg)
            if i + 1 >= len(args):
                usage("%s needs a value" % arg)
            got[arg] = args[i + 1]
            i += 2
        elif arg in flags:
            if arg in got:
                usage("%s given twice" % arg)
            got[arg] = True
            i += 1
        elif arg.startswith("-"):
            usage("%s is not an option of this command" % arg)
        else:
            rest.append(arg)
            i += 1
    if len(rest) != positional:
        usage("%d operand(s), not %d" % (positional, len(rest)))
    return got, rest


class Locked(object):
    def __enter__(self):
        self.handle = open(LOCK, "a")
        fcntl.flock(self.handle, fcntl.LOCK_EX)
        with open(STATE, encoding="utf-8") as handle:
            self.state = json.load(handle)
        return self.state

    def __exit__(self, *exc):
        with open(STATE + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(self.state, handle)
        os.replace(STATE + ".tmp", STATE)
        self.handle.close()
        return False


def put(path, data):
    # Each family file by temp file and rename, as section 3.6 has it.
    with open(path + ".tmp.%d" % os.getpid(), "wb") as handle:
        handle.write(data)
    os.replace(path + ".tmp.%d" % os.getpid(), path)


def images(seq):
    root = os.path.join(REGISTER, str(seq))
    found = {}
    for top, _dirs, files in os.walk(root):
        for name in files:
            full = os.path.join(top, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if RENDER_SET.match(rel):
                with open(full, "rb") as handle:
                    found[rel] = handle.read()
    return found


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows(state, seq):
    for entry in state["journal"].values():
        if entry["seq"] == seq:
            return entry["files"]
    return []


def identity(entry, lane, verb, digest):
    return (entry["lane"], entry["verb"], entry["args_sha256"]) == (lane, verb, digest)


def git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-C", cwd, "-c", "user.name=lanes-index stub",
                           "-c", "user.email=stub@lanes-index.invalid", "-c", "commit.gpgsign=false"]
                          + list(args), capture_output=True, env=env, check=True)


def build_tree(tree, checkout, seq, state):
    # Section 3.2's --tree: the render set at `seq`, from this stub's register;
    # lanes/repos.tsv and lanes/log/README.md from --checkout's origin/main
    # (under --at, repos.tsv as that seq's commit recorded it); one commit,
    # and refs/remotes/origin/main pointing at it.
    if os.path.exists(tree) and (not os.path.isdir(tree) or os.listdir(tree)):
        usage("--tree %s must not exist or must be empty" % tree)
    os.makedirs(tree, exist_ok=True)
    files = images(seq)
    for name in ("lanes/repos.tsv", "lanes/log/README.md"):
        recorded = os.path.join(REGISTER, "%d.repos.tsv" % seq)
        if name == "lanes/repos.tsv" and seq != state["n"] and os.path.exists(recorded):
            with open(recorded, "rb") as handle:
                files[name] = handle.read()
            continue
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        shown = subprocess.run(["git", "-C", checkout, "show", "origin/main:" + name],
                               capture_output=True, env=env)
        if shown.returncode == 0:
            files[name] = shown.stdout
    for rel, data in files.items():
        full = os.path.join(tree, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data)
    git(tree, "init", "-q")
    git(tree, "add", "-A")
    git(tree, "commit", "-q", "--allow-empty", "-m", "register at seq %d" % seq)
    git(tree, "update-ref", "refs/remotes/origin/main", "HEAD")
    if "lanes/repos.tsv" not in files:
        return ZEROS
    return git(tree, "rev-parse", "HEAD:lanes/repos.tsv").stdout.decode().strip()


def snapshot(args):
    o, _ = options(args, values=("--write-id", "--generation", "--lane", "--verb", "--args-sha256",
                                 "--tree", "--checkout", "--at"))
    wid, gen, at = o.get("--write-id"), o.get("--generation"), o.get("--at")
    rest = [o.get(k) for k in ("--lane", "--verb", "--args-sha256")]
    if ("--tree" in o) != ("--checkout" in o):
        usage("--tree and --checkout go together")
    if at is not None and not NUMBER.match(at):
        usage("--at takes a seq")
    if wid is None and gen is None and rest == [None, None, None]:
        kind = "act-begin"
    elif wid == "new" and gen is None and None not in rest:
        kind = "new"
    elif wid is not None and wid != "new" and gen is None:
        usage("--write-id <uuid> without --generation")
    elif wid is not None and wid != "new" and None not in rest:
        kind = "known"
    elif wid is None and gen is not None and rest == [None, None, None] and at is not None:
        kind = "generation"
    else:
        usage("the identity is all five flags, --write-id new with --lane, --verb and "
              "--args-sha256, or none")
    if at is not None and kind not in ("known", "generation"):
        usage("--at without --generation")
    if kind == "known" and not UUID.match(wid):
        usage("--write-id is a lowercase UUID")
    if gen is not None and not UUID.match(gen):
        usage("--generation is a lowercase UUID")
    if rest[2] is not None and not HEX64.match(rest[2]):
        usage("--args-sha256 is 64 lowercase hex")
    return lambda: snapshot_run(o, kind, wid, gen, at, rest)


def snapshot_run(o, kind, wid, gen, at, rest):
    with Locked() as state:
        if gen is not None and gen != state["generation"]:
            refuse(2, "LR007", "the write's generation is not the register's", "generation")
        seq = state["n"]
        lines = ["format=1", "generation=%s" % state["generation"]]
        if at is not None:
            seq = int(at)
            if seq > state["n"] or seq < state["first"]:
                raise Exit(69, "", "lanes-index: register snapshot: seq %d is not in this "
                                   "generation's journal\n" % seq)
        elif kind == "known" and wid in state["journal"]:
            entry = state["journal"][wid]
            if not identity(entry, *rest):
                refuse(2, "LR007", "the write id belongs to another write", "another-write")
            lines += ["write_id=%s" % wid, "found=%d" % entry["seq"]]
            lines += ["file=%s" % row for row in entry["files"]]
            clock = int(time.time())
            lines += ["switch=primary", "marker=present", "n=%d" % state["n"], "clock=%d" % clock,
                      "not_after=%d" % (clock + C_TIMER + 2), "schema=%d" % SCHEMA,
                      "c=%d" % C, "n_a=%d" % N_A]
            return Exit(0, "".join(line + "\n" for line in lines))
        if kind == "new":
            wid = str(uuid.uuid4())
        if wid is not None:
            lines.append("write_id=%s" % wid)
        clock = int(time.time())
        lines += ["switch=primary", "marker=present", "n=%d" % state["n"], "clock=%d" % clock,
                  "not_after=%d" % (clock + C_TIMER + 2), "schema=%d" % SCHEMA]
        if "--tree" in o:
            lines.append("repos_blob=%s" % build_tree(o["--tree"], o["--checkout"], seq, state))
        lines += ["c=%d" % C, "n_a=%d" % N_A]
    return Exit(0, "".join(line + "\n" for line in lines))


def attempt(directory, o):
    # Section 3.3's check of the attempt directory: 2, nothing sent.
    def bad(what):
        raise Exit(2, "", "lanes-index: attempt directory: %s; nothing was sent\n" % what)

    for name in ("snapshot", "changes.tsv", "msg", "author", "files", "not_after"):
        if not os.path.isfile(os.path.join(directory, name)):
            bad("%s is missing" % name)
    if not os.path.isdir(os.path.join(directory, "tree")):
        bad("tree/ is missing")
    with open(os.path.join(directory, "snapshot"), encoding="utf-8") as handle:
        snap = dict(line.partition("=")[::2] for line in handle.read().splitlines() if "=" in line)
    if snap.get("generation") != o["--generation"] or snap.get("write_id") != o["--write-id"]:
        bad("the flags differ from snapshot")
    changes = {}
    with open(os.path.join(directory, "changes.tsv"), encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            parts = line.split("\t")
            if (len(parts) != 4 or parts[0] not in ("A", "M", "D") or not HEX40.match(parts[2])
                    or not HEX40.match(parts[3])):
                bad("changes.tsv has a line that is not <status> TAB <path> TAB <blob> TAB <blob>")
            if not RENDER_SET.match(parts[1]):
                bad("%s is outside the render set" % parts[1])
            changes[parts[1]] = parts[0]
    root = os.path.join(directory, "images")
    staged = set()
    for top, _dirs, files in os.walk(root):
        for name in files:
            staged.add(os.path.relpath(os.path.join(top, name), root).replace(os.sep, "/"))
    for path in sorted(staged):
        if changes.get(path) not in ("A", "M"):
            bad("images/%s has no A or M line" % path)
    recomputed = []
    for path, status in sorted(changes.items()):
        if status == "D":
            recomputed.append("%s\t0\t-" % path)
            continue
        if path not in staged:
            bad("images/%s is missing" % path)
        with open(os.path.join(root, path), "rb") as handle:
            recomputed.append("%s\t1\t%s" % (path, sha(handle.read())))
    with open(os.path.join(directory, "files"), encoding="utf-8") as handle:
        listed = handle.read().splitlines()
    if sorted(row.split("\t")[0] for row in listed) != sorted(changes):
        bad("files and changes.tsv name different paths")
    if listed != recomputed:
        bad("files differs from the rows its images give")
    with open(os.path.join(directory, "not_after"), encoding="utf-8") as handle:
        not_after = handle.read().strip()
    if not NUMBER.match(not_after):
        bad("not_after is not epoch seconds")
    return snap, changes, recomputed, int(not_after)


def commit(args):
    o, rest = options(args, values=("--write-id", "--generation", "--lane", "--verb",
                                    "--args-sha256", "--workstation"), positional=1)
    for key in ("--write-id", "--generation", "--lane", "--verb", "--args-sha256", "--workstation"):
        if key not in o:
            usage("register commit needs %s" % key)
    if not UUID.match(o["--write-id"]) or not UUID.match(o["--generation"]):
        usage("--write-id and --generation are lowercase UUIDs")
    if not HEX64.match(o["--args-sha256"]):
        usage("--args-sha256 is 64 lowercase hex")
    return lambda: commit_run(o, rest[0])


def commit_run(o, directory):
    snap, changes, files, not_after = attempt(directory, o)
    ident = (o["--lane"], o["--verb"], o["--args-sha256"])
    with Locked() as state:
        if o["--generation"] != state["generation"]:
            refuse(2, "LR007", "the write's generation is not the register's", "generation")
        entry = state["journal"].get(o["--write-id"])
        if entry is not None:
            if not identity(entry, *ident):
                refuse(2, "LR007", "the write id belongs to another write", "another-write")
            return Exit(0, "already %d\n" % entry["seq"]
                        + "".join("file=%s\n" % row for row in entry["files"]))
        if snap.get("n") != str(state["n"]):
            refuse(75, "LR001", "the head moved since the snapshot")
        if int(time.time()) > not_after:
            refuse(75, "LR008", "the attempt reached its not_after")
        seq = state["n"] + 1
        shutil.copytree(os.path.join(REGISTER, str(state["n"])), os.path.join(REGISTER, str(seq)))
        for path, status in changes.items():
            target = os.path.join(REGISTER, str(seq), path)
            if status == "D":
                if os.path.exists(target):
                    os.remove(target)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(os.path.join(directory, "images", path), target)
        repos = os.path.join(directory, "tree", "lanes", "repos.tsv")
        if os.path.isfile(repos):
            shutil.copyfile(repos, os.path.join(REGISTER, "%d.repos.tsv" % seq))
        state["journal"][o["--write-id"]] = {
            "seq": seq, "lane": ident[0], "verb": ident[1], "args_sha256": ident[2],
            "workstation": o["--workstation"], "generation": state["generation"], "files": files}
        state["n"] = seq
    return Exit(0, "committed %d\n" % seq)


def journal(args):
    o, _ = options(args, values=("--write-id", "--not-after", "--generation", "--lane", "--verb",
                                 "--args-sha256", "--clock", "--clock-age"))
    for key in ("--write-id", "--not-after", "--generation", "--lane", "--verb", "--args-sha256"):
        if key not in o:
            usage("journal --write-id needs %s" % key)
    if ("--clock" in o) != ("--clock-age" in o):
        usage("--clock and --clock-age go together")
    if not UUID.match(o["--write-id"]) or not UUID.match(o["--generation"]):
        usage("--write-id and --generation are lowercase UUIDs")
    if not HEX64.match(o["--args-sha256"]):
        usage("--args-sha256 is 64 lowercase hex")
    for key in ("--not-after", "--clock", "--clock-age"):
        if key in o and not NUMBER.match(o[key]):
            usage("%s takes whole seconds" % key)
    return lambda: journal_run(o)


def journal_run(o):
    with Locked() as state:
        if o["--generation"] != state["generation"]:
            refuse(2, "LR007", "the write's generation is not the register's", "generation")
        entry = state["journal"].get(o["--write-id"])
        if entry is None:
            return Exit(0, "absent\n")
        if not identity(entry, o["--lane"], o["--verb"], o["--args-sha256"]):
            refuse(2, "LR007", "the write id belongs to another write", "another-write")
        return Exit(0, "found %d\n" % entry["seq"]
                    + "".join("file=%s\n" % row for row in entry["files"]))


def epoch(utc, module):
    # `<utc_ts>`: the stamp in epoch seconds, `-` where there is none or it
    # cannot be a time, by the checkout's register_utc_epoch where it has one.
    if not utc:
        return "-"
    reader = getattr(module, "register_utc_epoch", None)
    if reader is not None:
        value = reader(utc)
        return "-" if value is None else str(value)
    form = "%Y-%m-%dT%H:%M:%SZ" if utc.count(":") == 2 else "%Y-%m-%dT%H:%MZ"
    try:
        stamp = datetime.datetime.strptime(utc, form)
    except ValueError:
        return "-"
    return str(int(stamp.replace(tzinfo=datetime.timezone.utc).timestamp()))


def five_fields(module):
    # The checkout's own classify_register_line where it has one (lane 1's
    # T122); before it, the five fields as CLI4.10:636 defines them, from the
    # checkout's own REGISTER_KIND_RE, REGISTER_SLOTS where it has them, and
    # parse_register_line's repository, UTC and lane: never a second copy of
    # the classifier (CLI4.5:633).
    one = getattr(module, "classify_register_line", None)
    if one is not None:
        return one
    slots = getattr(module, "REGISTER_SLOTS", {})

    def fields_of(line):
        m = module.REGISTER_KIND_RE.match(line)
        if not m:
            return ("-", "-", "-", "-", "-")
        kind = m.group(1)
        fields = module.parse_register_line(line) or {}
        return (kind, (slots.get(kind) or (None, None))[0] or "-", fields.get("repo") or "-",
                epoch(fields.get("utc"), module), fields.get("lane") or "-")
    return fields_of


def classify(args):
    # Section 3.5 as contract draft 4.10 states it (CLI4.10:629-638; lane 1,
    # #165 6752238370): one LF-ended line per LF-cut input line, `<kind>` TAB
    # `<slot_role>` TAB `<repo_key>` TAB `<utc_ts>` TAB `<lane>`, each `-`
    # where absent. Any argument is 64, before stdin is read.
    options(args)

    def run():
        loader = importlib.machinery.SourceFileLoader("lanes_index_classifier", LANES_INDEX_SOURCE)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        one = five_fields(module)
        decode = getattr(module, "_decode", None) or (
            lambda raw: raw.decode("utf-8", "surrogateescape"))
        lines = sys.stdin.buffer.read().split(b"\n")
        if lines[-1] == b"":
            lines.pop()
        return Exit(0, "".join("\t".join(one(decode(raw))) + "\n" for raw in lines))
    return run


def suffix(key):
    # Section 3.6's file name for a log key: the key, or `%<hex>` outside the
    # class (O18).
    return key if LANE_CLASS.match(key) else "%" + key.encode("utf-8").hex()


def resolve(key, files):
    want = ("lanes/log/%s.md" % key).lower()
    hits = sorted(path for path in files if path.lower() == want)
    return hits


def row(text):
    # A `.head` row's present flag and digest: `1` and its sha256, or `0` and
    # `-` where the path is absent at `n` (CLI4.10:699 and :703).
    return ("0", "-") if text is None else ("1", sha(text))


def logs_at(files):
    return sorted(path for path in files if path.startswith("lanes/log/"))


def write_members(cache, members, files, head_rows, absent):
    # Each member at `n`, and its `.head` rows: one per path it names, present
    # or not (CLI4.10:699, :703). `logs` is `--all`'s set of logs, one row per
    # log it holds at `n`, its text cached or not (CLI4.11:703, S-a).
    for member in members:
        if member == "register":
            text = files.get("lanes/LANES.md")
            put(cache + ".register", (text or b"").rstrip(b"\n") + b"\n")
            head_rows["lanes/LANES.md"] = row(text)
        elif member == "paths":
            # Never `lanes/STORE` (CLI4.11:680): the stub's register holds the
            # render set alone.
            put(cache + ".paths", "".join(path + "\n" for path in sorted(files)).encode())
        elif member == "archive":
            names = sorted(path for path in files if path.startswith("lanes/archive/"))
            put(cache + ".archive", b"".join(files[path] for path in names))
            for path in names:
                head_rows[path] = row(files[path])
        elif member == "aliases":
            text = files.get("lanes/aliases.tsv")
            put(cache + ".aliases", text if text else b"# no lane aliases\n")
            head_rows["lanes/aliases.tsv"] = row(text)
        elif member == "logs":
            for path in logs_at(files):
                head_rows[path] = row(files[path])
        else:
            key = member[len("log:"):]
            hits = resolve(key, files)
            if len(hits) > 1:
                continue
            text = files[hits[0]] if hits else b""
            put(cache + ".log." + suffix(key), text)
            put(cache + ".logpath." + suffix(key), (hits[0] + "\n").encode() if hits else b"")
            if not LANE_CLASS.match(key):
                continue
            if hits:
                head_rows[hits[0]] = row(text)
            elif key not in absent:
                absent.append(key)


def write_head(cache, state, n, head_rows, absent, logs_set):
    lines = ["format=1", "n=%d" % n, "generation=%s" % state["generation"], "c=%d" % C,
             "n_a=%d" % N_A, "w_s_ms=%d" % W_S_MS]
    lines += ["file=%s\t%s\t%s" % ((path,) + head_rows[path]) for path in sorted(head_rows)]
    lines += ["absent=%s" % key for key in absent]
    data = "".join(line + "\n" for line in lines).encode()
    put(cache + ".head", data)
    # Whether this family holds `--all`'s set of logs: the stub's own record,
    # beside the stub, never in the family, and true only for this `.head`.
    try:
        with open(SETS, encoding="utf-8") as handle:
            sets = json.load(handle)
    except FileNotFoundError:
        sets = {}
    sets[os.path.abspath(cache)] = {"head": sha(data), "logs": bool(logs_set)}
    with open(SETS + ".tmp", "w", encoding="utf-8") as handle:
        json.dump(sets, handle)
    os.replace(SETS + ".tmp", SETS)


def holds_logs(cache):
    try:
        with open(SETS, encoding="utf-8") as handle:
            record = json.load(handle).get(os.path.abspath(cache))
        with open(cache + ".head", "rb") as handle:
            current = sha(handle.read())
    except (OSError, ValueError):
        return False
    return bool(record and record["head"] == current and record["logs"])


def read_head(cache):
    try:
        with open(cache + ".head", encoding="utf-8") as handle:
            text = handle.read().splitlines()
    except OSError:
        return None
    head = {"rows": {}, "absent": []}
    for line in text:
        key, _eq, value = line.partition("=")
        if key == "file":
            path, present, digest = value.split("\t")
            head["rows"][path] = (present, digest)
        elif key == "absent":
            head["absent"].append(value)
        else:
            head[key] = value
    return head


def members_of(o, files):
    if "--all" in o:
        return ["register", "paths", "archive", "aliases", "logs"] + [
            "log:" + name for name in all_logs(files)]
    members = o["--files"].split(",")
    for member in members:
        if member in ("register", "paths", "archive", "aliases"):
            continue
        if member.startswith("log:") and LANE_CLASS.match(member[len("log:"):]):
            continue
        usage("--files takes register, paths, archive, aliases and log:<key> for a key in "
              "check_lane_name's class, not %s" % member)
    return members


def all_logs(files):
    # `--all`'s logs: each `lanes/log/<File>.md` whose `<File>` is in the class.
    names = [path[len("lanes/log/"):-len(".md")] for path in logs_at(files)]
    return [name for name in names if LANE_CLASS.match(name)]


def cached_members(cache):
    directory, base = os.path.split(cache)
    found = []
    for name in ("register", "paths", "archive", "aliases"):
        if os.path.exists(cache + "." + name):
            found.append(name)
    for name in sorted(os.listdir(directory or ".")):
        if name.startswith(base + ".log.") and LANE_CLASS.match(name[len(base + ".log."):]):
            found.append("log:" + name[len(base + ".log."):])
    return found


def read(args):
    o, _ = options(args, values=("--for", "--cache", "--files", "--pid", "--repo", "--at",
                                 "--since"),
                   equals=("--lane", "--log-key"), flags=("--prefetch", "--all"))
    has = set(o)
    if o.get("--for") not in (None, "guard"):
        usage("--for takes guard")
    if "--cache" not in o:
        usage("register read needs --cache <file>")
    for key in ("--pid", "--at", "--since"):
        if key in o and not NUMBER.match(o[key]):
            usage("%s takes a whole number" % key)
    if has <= {"--prefetch", "--cache", "--files", "--all"} and "--prefetch" in has:
        if ("--files" in has) == ("--all" in has):
            usage("form 1 takes --files <set> or --all")
        form = 1
    elif has <= {"--for", "--prefetch", "--cache", "--pid", "--repo", "--lane"} and \
            {"--for", "--prefetch", "--pid", "--repo"} <= has:
        form = 2
    elif has <= {"--since", "--cache", "--files", "--log-key"} and "--since" in has and \
            ("--files" in has or "--log-key" in has):
        form = 3
    elif has == {"--for", "--at", "--pid", "--cache", "--lane"}:
        form = 4
    else:
        usage("not one of register read's four forms (section 3.6)")
    if form in (2, 4) and o.get("--lane") == "":
        usage("an empty --lane= key")
    if o.get("--log-key") == "":
        usage("an empty --log-key= key")
    if "--files" in o:
        members_of(o, {})
    return lambda: read_run(o, form)


def two_logs(key):
    raise Exit(69, "mode primary\n", "lanes-index: register read: two logs differ from %s "
               "only by case\n" % key)


def read_run(o, form):
    cache = o["--cache"]
    with Locked() as state:
        n = state["n"]
        if form == 4:
            head = read_head(cache)
            at = int(o["--at"])
            if head is None or head.get("generation") != state["generation"]:
                raise Exit(69, "mode primary\n", "lanes-index: register read: the cache's .head "
                           "is missing or names another generation\n")
            if at > n or at < state["first"]:
                raise Exit(69, "mode primary\n", "lanes-index: register read: seq %d is not in "
                           "this generation's journal\n" % at)
            files = images(at)
            key = o["--lane"]
            if len(resolve(key, files)) > 1:
                two_logs(key)
            write_members(cache, ["log:" + key], files, {}, [])
            return Exit(0, "mode primary\n")
        files = images(n)
        if form in (1, 2):
            if form == 1:
                members = members_of(o, files)
            else:
                members = ["register", "aliases"]
                if o.get("--lane") and LANE_CLASS.match(o["--lane"]):
                    members.append("log:" + o["--lane"])
            head_rows, absent = {}, []
            write_members(cache, members, files, head_rows, absent)
            write_head(cache, state, n, head_rows, absent, "logs" in members)
            return Exit(0, "mode primary\n")
        return form_3(o, cache, state, n, files)


def form_3(o, cache, state, n, files):
    # Form 3 as draft 4.10 and 4.11 state it (CLI4.10:730-733; CLI4.11:673):
    # the CACHED paths changed in (n, n'] by their digests at n'; 69 only for
    # a key the call asked for; a cached member that now matches two logs is
    # dropped from the family.
    asked = members_of(o, files) if "--files" in o else []
    if "--log-key" in o:
        asked.append("log:" + o["--log-key"])
    asked_keys = [m[len("log:"):] for m in asked if m.startswith("log:")]
    for key in asked_keys:
        if len(resolve(key, files)) > 1:
            two_logs(key)
    since = int(o["--since"])
    head = read_head(cache)
    logs_set = holds_logs(cache)
    cached = cached_members(cache)
    whole = (head is None or head.get("n") != str(since)
             or head.get("generation") != state["generation"]
             or not state["first"] <= since <= n)
    changed = set()
    if not whole:
        before = images(since)
        moved = set(before) ^ set(files)
        for path, kept in head["rows"].items():
            if row(files.get(path)) != kept:
                changed.add(path)
        if "paths" in cached:
            changed |= moved
        if "archive" in cached:
            changed |= {path for path in moved if path.startswith("lanes/archive/")}
        if logs_set:
            changed |= {path for path in moved if path.startswith("lanes/log/")}
        for key in head["absent"]:
            changed.update(resolve(key, files))
    dropped = []
    for member in cached:
        key = member[len("log:"):]
        if member.startswith("log:") and key not in asked_keys and len(resolve(key, files)) > 1:
            try:
                with open(cache + ".logpath." + key, encoding="utf-8") as handle:
                    dropped.append((key, handle.read().strip()))
            except OSError:
                dropped.append((key, ""))
            for name in (".log.", ".logpath."):
                if os.path.exists(cache + name + key):
                    os.remove(cache + name + key)
    gone = {key for key, _path in dropped}
    refetch = whole or bool(changed)
    if refetch:
        family = [m for m in cached if not (m.startswith("log:") and m[len("log:"):] in gone)]
        if logs_set:
            family += ["logs"] + ["log:" + name for name in all_logs(files)]
        head_rows, absent = {}, []
        write_members(cache, family + asked, files, head_rows, absent)
    else:
        head_rows = {path: kept for path, kept in head["rows"].items()
                     if path not in {old for _key, old in dropped}}
        absent = [key for key in head["absent"] if key not in gone]
        write_members(cache, asked, files, head_rows, absent)
    write_head(cache, state, n, head_rows, absent, logs_set)
    out = ["mode primary", "n=%d" % n] + ["changed=%s" % path for path in sorted(changed)]
    out.append("refetched=%d" % (1 if refetch else 0))
    return Exit(0, "".join(line + "\n" for line in out))


def render(args):
    # Section 3.7: the record of the fork's argv and environment, and the
    # flipped build's answer, which the detached caller never reads.
    options(args, values=("--checkout",))
    return lambda: render_run(args)


def render_run(args):
    env = {k: ("*" if SECRET.search(k) else v) for k, v in sorted(os.environ.items())}
    with open(RENDERS, "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(json.dumps({"argv": ["render"] + args, "env": env}) + "\n")
    return Exit(69, "", "lanes-index: render: git half not installed\n")


def route(argv):
    # The handler of a call this stub answers, its argv checked now (64), or
    # None for a form it does not answer unless a test injects one.
    words = argv[:2]
    if argv[:1] == ["mode"]:
        if argv[1:]:
            usage("mode takes no argument")
        return lambda: Exit(0, "primary\n")
    if words == ["register", "snapshot"]:
        if any(a in ("--files", "--all", "--out") for a in argv[2:]):
            return None
        return snapshot(argv[2:])
    if words == ["register", "commit"]:
        return commit(argv[2:])
    if argv[:1] == ["journal"] and "--write-id" in argv[1:]:
        return journal(argv[1:])
    if words == ["register", "classify"]:
        return classify(argv[2:])
    if words == ["register", "read"]:
        return read(argv[2:])
    if argv[:2] == ["render", "--checkout"]:
        return render(argv[1:])
    return None


def injected(argv):
    try:
        with open(OUTCOMES, encoding="utf-8") as handle:
            outcomes = json.load(handle)
    except FileNotFoundError:
        return None
    for outcome in reversed(outcomes):
        if argv[:len(outcome["argv"])] == outcome["argv"]:
            return outcome
    return None


def main(argv):
    with open(ARGV_LOG, "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(json.dumps(argv) + "\n")
    try:
        handler = route(argv)
        outcome = injected(argv)
        if outcome is not None:
            if outcome.get("committed") and handler is not None:
                try:
                    handler()
                except Exit:
                    pass
            if outcome.get("hang"):
                time.sleep(float(outcome["hang"]))
            raise Exit(int(outcome.get("exit") or 0), outcome.get("stdout") or "",
                       outcome.get("stderr") or "")
        if handler is None:
            usage("the contract stub does not answer %s; inject an outcome" % json.dumps(argv))
        raise handler()
    except Exit as end:
        sys.stdout.write(end.out)
        sys.stderr.write(end.err)
        return end.code


sys.exit(main(sys.argv[1:]))
'''


def contract_stub(directory, register=None) -> Path:
    """Write `<directory>/lanes-index`, the contract's stub `lanes-index`
    (T207; CLI4.5 §6, CLI4.5:881-903), and return its path: a Python script
    with a `#!/usr/bin/env python3` line and the executable bit, which a test
    runs by its path (R2's S8). `directory` is made if it is missing.

    THE COPY RULE (CLI4.5 §6, CLI4.5:885; O11): a test copies `lanes-edit.sh`,
    `repos.tsv` and `lane-start` beside the stub, where `lanes_index_bin` looks
    first, `$SCRIPT_DIR/lanes-index`.

    ITS REGISTER: the render set's files at each seq, under
    `<directory>/lanes-index.register/<seq>/`; its head, its generation and its
    journal in `<directory>/lanes-index.state`. Called again on one
    directory, it starts a new register and moves the old one aside. The head starts at seq 1, the
    generation's first, holding `register`, a mapping of render-set paths
    (`lanes/LANES.md`, `lanes/aliases.tsv`, `lanes/log/<lane>.md`,
    `lanes/archive/<name>`) to their text, empty by default. The generation
    is a new UUID. Each `register commit` that commits makes the next seq.

    WHAT IT ANSWERS, by CLI4.5's sections; every other end is a test's to
    inject with `stub_outcome`:

    - §3.1 `mode`: `primary`, 0; with any argument, 64.
    - §3.2 `register snapshot`: the argv's forms, each other form 64 (an id
      without `--generation`, `--at` without it, `--tree` without
      `--checkout`); check 1, the generation, 2 with `ERROR:  LR007: …` and
      `DETAIL:  generation`; check 2, the id found with its lane, verb and
      `args_sha256`, 0 with `found=` and its `file=` rows; check 2′, the id
      another write's, 2 with `DETAIL:  another-write`; then the `key=value`
      lines in §3.2's order, the id minted for `--write-id new`, `not_after=`
      the clock plus `C` plus 2 s. `--tree <dir> --checkout <c>` builds the
      scratch tree from the stub's register at `n` (or at `--at <k>`), with
      `lanes/repos.tsv` and `lanes/log/README.md` from `<c>`'s `origin/main`,
      one commit and `refs/remotes/origin/main` on it, and prints
      `repos_blob=`. Under `--at` only the generation is checked, and a seq
      outside the generation's journal is 69. `--files`, `--all` and `--out`
      (§3.6's image form) are not answered.
    - §3.3 `register commit`: the argv, each flag required (64); the attempt
      directory's check, 2 with `lanes-index: attempt directory: <what>;
      nothing was sent` (a listed file missing, an image with no `A` or `M`
      line, `files` and `changes.tsv` naming different paths, `files`
      differing from the images' rows, the flags differing from `snapshot`, a
      path outside the render set); then LR007 `generation` and
      `another-write` (2), LR006 (0, `already <seq>` and its `file=` rows),
      LR001 where `snapshot`'s `n=` is not the head (75), LR008 past
      `not_after` (75), and otherwise `committed <seq>`, 0.
    - §3.4 `journal --write-id …`: the argv (64); LR007 `generation` and
      `another-write` (2); `found <seq>` with its `file=` rows, or `absent`,
      0. It answers at once: the wait and the window are the real
      `journal`'s, and LR011 and the lookup's 3s are injected.
    - §3.5 `register classify`, as contract draft 4.10 states it
      (CLI4.10:629-638; lane 1, #165 6752238370), not CLI4.5:636's four
      fields: one LF-ended line per LF-cut input line, five TAB-separated
      fields, `<kind>`, `<slot_role>`, `<repo_key>`, `<utc_ts>` (epoch
      seconds) and `<lane>`, each `-` where absent; any argument 64, before
      stdin is read. The fields are the checkout's own: its
      `classify_register_line` (lane 1's T122) where `LANES_INDEX` has one,
      and before it CLI4.10:636's fields from its `REGISTER_KIND_RE`,
      `REGISTER_SLOTS` (T118) where it has them, and `parse_register_line`,
      so the stub holds no second classifier (CLI4.5:633). A test teaches
      other fields with `stub_outcome`.
    - §3.6's four forms of `register read`, as contract draft 4.10 and
      draft 4.11 state them (lane 1, #165 6752925109), each form's argv (an
      empty `--lane=` 64 in forms 2 and 4; `--lane` and `--log-key` only in
      the `=` form): the first stdout line `mode primary`; the cache family
      written by temp file and rename beside `--cache <file>`, `.head` last;
      a key outside `check_lane_name`'s class as `.log.%<hex>`, never cached;
      two logs that differ only by case written by no form; form 4's `.head`
      checks (69 where it is missing, names another generation, or `--at` is
      outside the journal), its one log at `--at`, and no `.head`.
      `.outage`, `.direct` and the guard's "too late" are injected.
      - `.head`'s rows (CLI4.10:699, :703; CLI4.11:703, S-a): a `file=` row
        for every path a member names at `n`, present or not, `1` and its
        digest or `0` and `-`; a set member (`archive`, and `--all`'s logs)
        one row per file it holds at `n`, its text cached or not, a log
        outside the class or one of a case pair included; a `log:<key>` that
        resolves to no log an `absent=` row instead.
      - `.paths` never holds `lanes/STORE` (CLI4.11:680): the register holds
        the render set alone.
      - Form 3 (CLI4.10:730-733): the cached paths changed in `(n, n′]` by
        their digests at `n′` (a row whose digest differs or is absent, a
        path created or removed against a cached `.paths` or under a cached
        set member, an `absent=` key that now resolves), printed as `n=<n′>`,
        one `changed=<path>` per path, sorted, and `refetched=0` or `1`;
        where any is found, or `.head` is missing or names another `n` or
        generation, the whole family rewritten at `n′`, `.head` last;
        otherwise the members `--files` names, with their rows added. It
        exits 69 only for a key it was asked for, by `--files` or
        `--log-key=`; a cached member that now matches two logs is dropped
        from the family, its `.log.<key>` and `.logpath.<key>` removed
        (CLI4.11:673, N-g). Whether a family holds `--all`'s set of logs is
        the stub's own record, `lanes-index.sets` beside the stub, true only
        for the `.head` it wrote with it.
    - §3.7 `render --checkout <c>`: one JSON line per call in
      `<directory>/lanes-index.render`, its argv and its environment (the
      value of a variable whose name holds TOKEN, SECRET, PASSWORD, PASSWD or
      KEY recorded as `*`), and "git half not installed" on stderr, 69.
    - Anything else: 64, unless a test injects an outcome for it.

    Every call is logged to `<directory>/lanes-index.argv`, one JSON array of
    its arguments per line (lane 4's M9)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    old = directory / "lanes-index.register"
    if old.exists():
        old.rename(directory / f"lanes-index.register.old-{time.time_ns()}")
    seed = directory / "lanes-index.register" / "1"
    seed.mkdir(parents=True, exist_ok=True)
    for path, text in (register or {}).items():
        if not RENDER_SET_PATH.match(path):
            raise ValueError(f"contract_stub: {path} is not a render-set path")
        target = seed / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
    state = {"generation": str(uuid.uuid4()), "n": 1, "first": 1, "journal": {}}
    (directory / "lanes-index.state").write_text(json.dumps(state), encoding="utf-8")
    stub = directory / "lanes-index"
    here = str(directory.resolve())
    text = _CONTRACT_STUB.replace("STUB_DIRECTORY", repr(here), 1)
    text = text.replace("LANES_INDEX_PATH", repr(str(LANES_INDEX)), 1)
    stub.write_text(text, encoding="utf-8")
    stub.chmod(0o755)
    return stub


def stub_outcome(directory, argv_prefix, exit=None, stdout=None, stderr=None, committed=False,
                 hang=None) -> None:
    """Inject an outcome into the contract stub in `directory`: every later
    call whose arguments begin with `argv_prefix` (a string of words, such as
    `"register commit"`, or a list) ends with `exit` (0 where only output is
    given), printing `stdout` and `stderr`. The last injected outcome whose
    prefix matches answers, after the call's argv has been checked (64 still
    comes first).

    - `committed=True`: the call first does what it would, its own answer
      dropped, as "committed, then exit 3", agreement test 12's pair.
    - `hang=<seconds>`: it sleeps first, a hang past the caller's timer.
    - Each LR code is its `exit` with `stderr` in §2.6's shape, such as
      `"ERROR:  LR005: <message>\\nDETAIL:  main-held\\n"` with 2.
    - On `journal --write-id`, a crash (`exit=1`, a traceback on stderr) and an
      unknown code (any other) are the caller's to read as 3 (CO-2).

    Called with no outcome (no `exit`, `stdout`, `stderr` or `hang`), it
    removes the outcomes injected for that prefix."""
    words = argv_prefix.split() if isinstance(argv_prefix, str) else list(argv_prefix)
    path = Path(directory) / STUB_OUTCOMES
    outcomes = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if exit is None and stdout is None and stderr is None and hang is None:
        outcomes = [o for o in outcomes if o["argv"] != words]
    else:
        outcomes.append({"argv": words, "exit": exit, "stdout": stdout, "stderr": stderr,
                         "committed": bool(committed), "hang": hang})
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(outcomes), encoding="utf-8")
    os.replace(tmp, path)


# ------------------------------------------------ the guard's session (T203c)
#
# WHY: lane 5's T507 prefetch reads the register AFTER the guard's own
# checks, and each of them refuses with 2 (lane 5, #165 6755266457; F10's
# items 27 and 28). In `guard_run` at `a2073eae` (`lanes-edit.sh:10922`), in
# order: the subagent and `cwd` reads of the hook's JSON (`jstr`, which reads
# only the compact `"key":"value"`); the scope test against
# `${PROJECTS_ROOT:-$HOME/projects}` (`:10939`), which returns 0 outside it;
# the workspace check (`LANES_REPO`, `LANES_DIR`, `LANES_FILE`, `:10948`); the
# tmux checks (`here_context`'s `display-message -p
# '#{session_name}:#{window_id}'` and `'#{pane_pid}'`, `:10954`, then `'#W'`,
# `:10964`); and this workstation's session records, `transcript_holders
# "$G_ID"` (`:10986`), which needs a live record whose `sessionId` is the
# hook's `session_id` and whose window is this one, or it refuses "no live
# session record in THIS window" (`:11010`). Only then comes the register's
# text (`register_text`, `:11049`), the guard's first register read. Lane 5's
# `refs/l5/T502` changes the offer site, not these checks.

#: THE VARIABLES THAT WOULD STEER THE GUARD AWAY FROM A CASE'S OWN ESTATE, by
#: the prefixes of their names: the lane's own (`LANES_`, among them
#: `LANES_REPO` and `LANES_INDEX_CONFIG`), the harness's (`CLAUDE_`, among
#: them `CLAUDE_CODE_SESSION_ID` and `CLAUDE_NO_LANE`), tmux's, libpq's and
#: the fake's; `PROJECTS_ROOT`, which moves the scope test's root off
#: `$HOME/projects` so the guard returns 0 before any read (T220c's note,
#: F10's item 28); and `AGENT_PROTOCOL_ROOT`, which moves `workspace.yaml` off
#: `$HOME/.agents` (`lanes-edit.sh:785`).
GUARD_ENV_STRIP = ("LANES_", "CLAUDE_", "TMUX", "PG", "FAKE_PSQL", "PROJECTS_ROOT",
                   "AGENT_PROTOCOL_ROOT")

#: The stand-in's window, in the form the suite's session records carry
#: (`testsess:@1.%1`, `tests/test_supervised_restart_regressions.py`), and
#: `TMUX_PANE` as T215's and T220's benches set it; the window's name is the
#: lane's, `repoA-2` there.
GUARD_WINDOW = "repoA-2"
GUARD_TMUX_SESSION = "testsess"
GUARD_WINDOW_ID = "@1"
GUARD_PANE = "%1"
#: The stand-in's call log, beside it.
GUARD_TMUX_LOG = "tmux.log"

#: THE STAND-IN `tmux`, in the form of T215's and T220's `FAKE_TMUX` (a
#: `#!/bin/sh` that answers `display-message` as the lane's window and exits
#: 0 to the rest), with each query the guard makes answered as a real tmux
#: answers it, and every call logged. The `@…@` words are filled in, each
#: quoted for the shell, by `guard_session`.
_GUARD_TMUX = r'''#!/bin/sh
# A STAND-IN tmux (feature 007, T203c): it logs every call, each argument
# ended by US (0x1f), one call per line, and answers display-message as the
# lane's window does. A target that is not that window gets tmux's own
# "can't find window" and 1. Every other command is answered with nothing
# and 0.
{ for a in "$@"; do printf '%s\037' "$a"; done; printf '\n'; } >> @LOG@
[ "${1-}" = display-message ] || exit 0
target=""; prev=""; fmt=""
for a in "$@"; do
  [ "$prev" = -t ] && target="$a"
  prev="$a"; fmt="$a"
done
case "$target" in
  ''|@ID@|@SESSION@:@ID@|@PANE@|@SESSION@:@ID@.@PANE@) ;;
  *) printf "can't find window: %s\n" "$target" >&2; exit 1 ;;
esac
case "$fmt" in
  '#{session_name}:#{window_id}') printf '%s\n' @SESSION@:@ID@ ;;
  '#{session_name}') printf '%s\n' @SESSION@ ;;
  '#{window_id}') printf '%s\n' @ID@ ;;
  '#{pane_id}') printf '%s\n' @PANE@ ;;
  '#{pane_pid}') printf '%s\n' @PID@ ;;
  *) printf '%s\n' @WINDOW@ ;;
esac
exit 0
'''

#: THE SESSION'S LIVE PROCESS: it reads its stdin to the end, so it lives
#: until `GuardSession.close` closes that pipe, or the test's process dies.
_GUARD_HOLDER = "import sys; sys.stdin.buffer.read()"


def _sh(value) -> str:
    """`value` quoted for the shell, as one word."""
    return "'" + str(value).replace("'", "'\\''") + "'"


def _proc_start(pid) -> str:
    """The start token the guard compares, field 22 of `/proc/<pid>/stat`,
    cut after the last `) ` as `pid_alive` cuts it (`lanes-edit.sh:5154`).
    Empty where there is no `/proc`, where `pid_alive` asks `kill -0` alone."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return stat.rsplit(") ", 1)[1].split()[19]


def guard_strip_env(environ=None, strip=()) -> dict:
    """A copy of `environ` (`os.environ` where it is None) without each
    variable whose name begins with a prefix in `GUARD_ENV_STRIP`, or in
    `strip`, a module's own (T215's `T215_`, for one)."""
    prefixes = tuple(GUARD_ENV_STRIP) + tuple(strip)
    source = os.environ if environ is None else environ
    return {k: v for k, v in source.items() if not k.startswith(prefixes)}


class GuardSession:
    """A live session for a guard case, made by `guard_session`, whose
    docstring is its manual."""

    def __init__(self, home, directory, cwd, window, session_id, name, name_source,
                 status, proc_start):
        self.home, self.directory, self.cwd = Path(home), Path(directory), Path(cwd)
        self.window, self.session_id = window, session_id
        self.target = f"{GUARD_TMUX_SESSION}:{GUARD_WINDOW_ID}.{GUARD_PANE}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.holder = subprocess.Popen([sys.executable, "-I", "-c", _GUARD_HOLDER],
                                       stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
        self.pid = self.holder.pid
        self.proc_start = _proc_start(self.pid) if proc_start is None else str(proc_start)
        self.tmux_env = f"{self.directory / 'tmux-server'},{self.pid},0"
        self.tmux_log = self.directory / GUARD_TMUX_LOG
        self.tmux = self.directory / "tmux"
        words = {"@LOG@": _sh(self.tmux_log), "@SESSION@": _sh(GUARD_TMUX_SESSION),
                 "@ID@": _sh(GUARD_WINDOW_ID), "@PANE@": _sh(GUARD_PANE),
                 "@PID@": _sh(self.pid), "@WINDOW@": _sh(window)}
        text = _GUARD_TMUX
        for word, value in words.items():
            text = text.replace(word, value)
        self.tmux.write_text(text, encoding="utf-8")
        self.tmux.chmod(0o755)
        sessions = self.home / ".claude" / "sessions"
        sessions.mkdir(parents=True, exist_ok=True)
        self.record = sessions / f"{self.pid}.json"
        self.record.write_text(json.dumps(
            {"pid": self.pid, "sessionId": session_id, "cwd": str(self.cwd),
             "procStart": self.proc_start, "tmux": self.target, "name": name,
             "nameSource": name_source, "status": status, "kind": "interactive"},
            separators=(",", ":")) + "\n", encoding="utf-8")
        self.record.chmod(0o600)

    def env(self, base, **extra) -> dict:
        """`base`, a case's environment for the guard (see `guard_strip_env`),
        with this session's window, `TMUX` and `TMUX_PANE`, and the stand-in's
        directory first on `PATH` where it is not already. An `extra` value
        of None removes that variable, as `TMUX=None` takes the session out
        of any window; any other sets it."""
        env = dict(base)
        env.update(TMUX=self.tmux_env, TMUX_PANE=GUARD_PANE)
        path = env.get("PATH", os.defpath)
        if path.split(os.pathsep)[0] != str(self.directory):
            env["PATH"] = os.pathsep.join([str(self.directory), path])
        for key, value in extra.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return env

    def hook_input(self, prompt="hello", cwd=None) -> str:
        """The hook's JSON for this session, compact as the harness sends it,
        since the guard's `jstr` reads `"<key>":"<value>"` with no blank after
        the colon: `hook_event_name`, `session_id`, `cwd` (this session's,
        unless given) and `prompt`, in T215's and T220's order."""
        return json.dumps({"hook_event_name": "UserPromptSubmit",
                           "session_id": self.session_id,
                           "cwd": str(self.cwd if cwd is None else cwd), "prompt": prompt},
                          separators=(",", ":"))

    def tmux_calls(self) -> list:
        """Every call the stand-in `tmux` took, in order, each its list of
        arguments."""
        if not self.tmux_log.exists():
            return []
        return [line.split("\x1f")[:-1]
                for line in self.tmux_log.read_text(encoding="utf-8",
                                                     errors="replace").splitlines()]

    def close(self) -> None:
        """End the session's process. Its record stays, naming a dead pid, so
        the guard reads it as not live; the files stay for the test's
        `tmp_path`. Safe to call twice."""
        holder = self.holder
        if holder.stdin is not None and not holder.stdin.closed:
            try:
                holder.stdin.close()
            except OSError:
                pass
        if holder.poll() is None:
            try:
                holder.wait(timeout=10)
            except subprocess.TimeoutExpired:
                holder.kill()
                holder.wait(timeout=10)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def guard_session(home, directory, cwd, *, window=GUARD_WINDOW, session_id=None, name=None,
                  name_source="user", status="busy", proc_start=None) -> GuardSession:
    """Give a guard case a live session, so that `lanes-edit.sh guard` gets
    past its session-record check to its register read, and return it as a
    `GuardSession`.

    - `home`: the `HOME` the guard runs with. The record is written under it.
    - `directory`: a directory the case puts first on `PATH` (its `bin`); the
      stand-in `tmux` and its log are written there, replacing any `tmux`
      the case wrote before.
    - `cwd`: the lane's checkout, the hook's `cwd`. It must be under
      `<home>/projects`, or the guard's scope test returns 0 before any read
      (T215b, T220c), and a `ValueError` says so.
    - `window`: the window's name, the lane's (`GUARD_WINDOW`, `repoA-2`).
    - `session_id`: the hook's `session_id` and the record's `sessionId`, in
      lower case as the harness writes it (another is a `ValueError`); a new
      uuid4 where None, so a case that writes a register row naming the
      session passes its own.
    - `name` and `name_source`: the record's `name` (the window's where None)
      and `nameSource` (`user`, as `/rename` or `--name` gives it).
    - `status`: the record's `status` (`busy`; `ended`, `exited`, `dead` or
      `stopped` makes it not live).
    - `proc_start`: the record's `procStart`; the live process's own start
      token where None. Any other value forges a recycled pid, so the record
      is not live.

    WHAT IT WRITES:

    - THE LIVE PROCESS: a child of the test (`GuardSession.pid`, `.holder`)
      in a session of its own, a Python that reads its stdin to the end, so
      it lives until `close()` or the test's process ends.
    - THE RECORD, `<home>/.claude/sessions/<pid>.json`, mode 0600, one line
      of compact JSON in the suite's record form: `pid`, `sessionId`, `cwd`,
      `procStart`, `tmux` (`testsess:@1.%1`), `name`, `nameSource`, `status`
      and `kind` (`interactive`). The guard's `transcript_holders` finds it
      by `"sessionId":"<id>"`, reads it live by `pid_alive` (`kill -0`, then
      field 22 of `/proc/<pid>/stat` equal to `procStart`), and here because
      its `tmux` target names the window the stand-in answers for.
    - THE STAND-IN, `<directory>/tmux`, logging each call to
      `<directory>/tmux.log` (`tmux_calls()` reads it). `display-message
      -p` answers `'#{session_name}:#{window_id}'` with `testsess:@1`,
      `'#{session_name}'` with `testsess`, `'#{window_id}'` with `@1`,
      `'#{pane_id}'` with `%1`, `'#{pane_pid}'` with the live pid, and any
      other format (`'#W'` among them) with `window`, as T215's and T220's
      `FAKE_TMUX` answers every one. A `-t` naming another window gets
      "can't find window" and 1. Every other command: nothing, and 0.

    WHAT IT RETURNS: the `GuardSession`, with `session_id`, `window`, `pid`,
    `proc_start`, `record`, `tmux`, `tmux_log`, `target`, `home`,
    `directory` and `cwd`, and:

    - `env(base, **extra)`: `base` with `TMUX` (`<directory>/tmux-server,
      <pid>,0`), `TMUX_PANE` (`%1`) and `directory` first on `PATH`. Make
      `base` with `guard_strip_env(os.environ, strip=(<the module's own
      prefixes>,))`, then set `HOME` to `home` and the case's own variables
      (`LANES_REPO`, `LANES_INDEX_CONFIG`, `LANES_LANE`, ...);
    - `hook_input(prompt="hello", cwd=None)`: the compact hook JSON, for the
      guard's stdin;
    - `tmux_calls()`: the stand-in's calls.

    TEARDOWN: `close()` (or a `with` block, or
    `request.addfinalizer(session.close)`) ends the live process; the record
    then names a dead pid, which the guard reads as no live session, and its
    files stay in the case's `tmp_path`. Without a `close()`, the process
    still ends when the test's process does, at the end of its stdin."""
    home, cwd = os.path.abspath(home), os.path.abspath(cwd)
    projects = os.path.join(home, "projects")
    if not (cwd + os.sep).startswith(projects + os.sep):
        raise ValueError(f"guard_session: the checkout {cwd} is not under {projects}, so the "
                         f"guard's scope test would return 0 before any read")
    session_id = str(uuid.uuid4()) if session_id is None else str(session_id)
    if session_id != session_id.lower():
        raise ValueError(f"guard_session: the session id {session_id} is not in lower case; "
                         f"the guard lower-cases the hook's and greps the records for it")
    return GuardSession(home, directory, cwd, window, session_id,
                        window if name is None else name, name_source, status, proc_start)
