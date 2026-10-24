# SPDX-License-Identifier: Apache-2.0
"""`.github/workflows/tests.yml`: its triggers, its four jobs and the `package` job (#228).

OFFLINE, LIKE THE REST OF THIS SUITE. What these tests hold is
contracts/workflows.md's "Held by `tests/test_tests_workflow.py`" list, with
the `package` job's steps 1 to 11 as that contract writes them. The workflow
is read with the PINNED STANDARD'S OWN `repo_shape.load_yaml` (research R9),
the fail-closed reader of the YAML subset this family writes, so a construct
outside that subset fails here first, and no YAML library joins the suite.
Without the submodule those tests SKIP, naming it, as the command tests do.
Two tests read the file as text instead, and need no submodule: the header
comment, because a comment is not data, and the digest rule, because a
digest is wrong wherever in the file it stands.

THREE OF THE `package` JOB'S STEPS ARE RUN, NOT ONLY READ. Each runs under
bash at the repository's root, as the runner runs it, with `$RUNNER_TEMP`,
`$HOME` and every `$GITHUB_*` file under the test's own directory, and with
pip pointed at no index, so nothing can be fetched:

- step 4, under a fake `pip` that records each call and installs nothing:
  the file it installs `tomli` from, by hash, must be the build lock's whole
  `tomli` entry, every hash of it;
- step 6, the wheel check, over four wheels made here with `zipfile` from
  HEAD's own blobs and modes, laid out as hatchling 1.27.0 lays one out, and
  put where step 5 leaves its two builds, `$RUNNER_TEMP/a/` and
  `$RUNNER_TEMP/b/`;
- step 11's report step, over JUnit reports written here.

WHAT THESE TESTS NEED OF THE `package` JOB, beyond the contract's own
words, written down here so that the task adding the job (T016) knows:

- each numbered step of the contract is its own YAML step, or several, in
  the contract's order, and step 11's report is a later YAML step than its
  pytest command;
- a step is found by what it does, its `run:`, `env:` and `with:`, never by
  its `name:`: step 4 names the build lock, 5 runs `pip wheel`, 6 opens a
  `python3 - … <<'PY'` heredoc, 7 names the pipx lock, 8 runs
  `pipx install`, 9 runs `openRepoTools --version`, 10 sets
  `OPENREPOTOOLS_REPO=offline.invalid/sentinel`, and 11 runs the contract's
  pytest command;
- step 6's YAML step holds that one heredoc, and its script, up to the
  heredoc's closing `PY`, checks the wheel in `$RUNNER_TEMP/a/` against
  `HEAD`, printing each problem, and exits 0 or 1;
- a step that is run reads what an earlier step left only through
  `$GITHUB_ENV`, `$GITHUB_PATH`, `$RUNNER_TEMP` or the job's `env:`, and the
  only expressions it holds are `${{ runner.temp }}`,
  `${{ github.workspace }}`, `${{ github.sha }}` and `${{ env.NAME }}`.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import NEEDS_UPSTREAM, REPO, UPSTREAM, WINDOWS_SKIP

WORKFLOW = REPO / ".github" / "workflows" / "tests.yml"
BUILD_LOCK = REPO / ".github" / "release-build-requirements.txt"
PINNED_READER = UPSTREAM / "scripts" / "repo_shape.py"

#: THE RELEASE GATE'S JOB IDS (FR-046), in the file's order. The gate
#: reads them by name, so a fifth job, a renamed one or a `name:` on one is
#: a gate that finds nothing.
JOB_IDS = ("guard-launch-mode", "tests", "tests-no-submodule", "package")

#: The two commits every job pins (contracts/workflows.md).
CHECKOUT = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
SETUP_PYTHON = "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065"

#: THE TRIGGERS. Only `push.branches` moves, from `[main]`.
PULL_REQUEST = {"types": ["opened", "synchronize", "reopened", "labeled"]}
PUSH = {"branches": ["main", "release/v*"]}
SCHEDULE = [{"cron": "17 4 * * *"}]

#: THE TWO TEST JOBS RUN THE PYTHON TESTS THREE WIDE (#77, step 2; Brett Heap's
#: ruling of 2026-10-23), and these are the pieces. EACH FLAG IS LOAD-BEARING:
#: `-n 3` is the width; `--dist loadfile` keeps a file's tests on one worker
#: and makes the shell suite's wrapper one unit; and `--no-loadscope-reorder`,
#: because pytest-xdist 3.8.0 otherwise sorts those units by size, biggest
#: first, and the wrapper's module is one of the smallest, so
#: `tests/conftest.py`'s hook that puts it first would be undone
#: (`tests/test_xdist_three_wide.py` runs both). THE PIN IS EXACT, and one
#: version: pytest-xdist 3.8.0 was released on 2025-07-01 and declares
#: `pytest>=7.0.0`, which 8.3.4 meets.
XDIST_PIN = "pytest-xdist==3.8.0"
XDIST_FLAGS = "-n 3 --dist loadfile --no-loadscope-reorder"
TEST_JOBS = ("tests", "tests-no-submodule")

#: THE THREE EXISTING JOBS AS TODAY'S FILE HOLDS THEM, written out here and
#: never read from history: CI checks out one commit at `fetch-depth: 1`.
#: Each is its runner, its checkout's options, its Python and its `run:`
#: commands in order. The pull request's diff review answers for the rest
#: of "byte for byte", of `guard-launch-mode`, which has not moved; `tests`
#: and `tests-no-submodule` carry #77's xdist pin and flags.
EXISTING_JOBS = {
    "guard-launch-mode": {
        "checkout": {"submodules": True, "fetch-depth": 1},
        "python": "3.x",
        "runs": [
            "python3 -m pip install --disable-pip-version-check "
            "--only-binary=:all: pytest==8.3.4",
            "bash tests/run.sh -k 'guard_launch_mode or repo_hygiene'",
        ],
    },
    "tests": {
        "checkout": {"submodules": True, "fetch-depth": 1},
        "python": "3.x",
        "runs": [
            "python3 -m pip install --disable-pip-version-check "
            f"pytest==8.3.4 {XDIST_PIN}",
            "{\n"
            '  echo "GIT_AUTHOR_NAME=openRepoTools CI"\n'
            '  echo "GIT_AUTHOR_EMAIL=ci@openrepotools.invalid"\n'
            '  echo "GIT_COMMITTER_NAME=openRepoTools CI"\n'
            '  echo "GIT_COMMITTER_EMAIL=ci@openrepotools.invalid"\n'
            '} >> "$GITHUB_ENV"\n',
            f"python3 -m pytest tests -q {XDIST_FLAGS}",
        ],
    },
    "tests-no-submodule": {
        "checkout": {"submodules": False, "fetch-depth": 1},
        "python": "3.x",
        "runs": [
            "python3 -m pip install --disable-pip-version-check "
            f"pytest==8.3.4 {XDIST_PIN}",
            "set -euo pipefail\n"
            "if [ -f upstream/openRepoShape/scripts/repo_shape.py ]; then\n"
            '  echo "the submodule IS checked out; this job proves nothing" >&2\n'
            "  exit 1\n"
            "fi\n",
            f"python3 -m pytest tests -q -rs {XDIST_FLAGS}",
        ],
    },
}

#: The identity the fixture commits carry, as the `tests` job sets it.
GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "openRepoTools CI",
    "GIT_AUTHOR_EMAIL": "ci@openrepotools.invalid",
    "GIT_COMMITTER_NAME": "openRepoTools CI",
    "GIT_COMMITTER_EMAIL": "ci@openrepotools.invalid",
}

#: contracts/cli-output.md's unstamped `--version`, which step 9 compares.
UNSTAMPED_VERSION = (
    "openRepoTools 0.0.0 (an unstamped package)",
    "  version   0.0.0, unstamped: a package built from a checkout, not a release",
    "  tag       none",
    "  commit    none",
    "  digest    none",
)

#: THE SKIP LINE AND THE COUNT LINE OF STEP 10, as the parts a bash script
#: carries whole however it quotes the rest: the line holds an apostrophe
#: and four backticks, and a script may escape either.
SKIP_LINE_PARTS = ("left to pipx at ", "(a link into pipx",
                   "openrepotools environment); update it with ",
                   "pipx upgrade openrepotools", ", then run ")
COUNT_LINE_PARTS = ("16 of 17 placed in ", ", and 1 left to pipx")

#: STEP 11's COMMAND, as contracts/workflows.md writes it.
PYTEST_COMMAND = ("python3 -m pytest tests/test_package.py "
                  "tests/test_package_stamp.py tests/test_install_pipx.py "
                  '-q -rs --junitxml="$RUNNER_TEMP/package-tests.xml"')

#: `$RUNNER_TEMP` in any spelling a step may give it.
RT = r"(?:\$\{?RUNNER_TEMP\}?|\$\{\{\s*runner\.temp\s*\}\})"

#: A heredoc's opening line, `python3 - … <<'PY'`: python3, a lone `-` for
#: its script, and nothing after the delimiter.
HEREDOC_OPENER = re.compile(
    r"^[ \t]*python3[ \t](?:[^\n]*[ \t])?-[ \t](?:[^\n]*[ \t])?<<'PY'[ \t]*$",
    re.M)

#: HOW EACH STEP OF THE `package` JOB IS FOUND, in the contract's order: the
#: first YAML step after the one before whose `run:`, `env:` or `with:`
#: matches. Steps 1 and 2 are the job's first two YAML steps, and step 3
#: is what lies between them and step 4.
ANCHORS = (
    (4, "the test tools", re.compile(r"release-build-requirements\.txt")),
    (5, "build twice, then compare", re.compile(r"\bpip[ \t]+wheel\b")),
    (6, "the wheel check", HEREDOC_OPENER),
    (7, "pipx from its hash lock",
     re.compile(r"release-pipx-requirements\.txt")),
    (8, "install the wheel with pipx", re.compile(r"\bpipx[ \t]+install\b")),
    (9, "the unstamped --version",
     re.compile(r"openRepoTools[\"']?[ \t]+--version\b")),
    (10, "an offline --install beside pipx's link",
     re.compile(r"\bOPENREPOTOOLS_REPO=[\"']?offline\.invalid/sentinel")),
    (11, "the package's tests, none skipped",
     re.compile(r"-m[ \t]+pytest[ \t]+tests/test_package\.py\b")),
)
REPORT = re.compile(r"package-tests\.xml")
ORDER = (4, 5, 6, 7, 8, 9, 10, 11, "report")

#: Where the package's files sit in the wheel, and the stamp in the commit.
PACKAGE = "openrepotools/"
PAYLOAD = PACKAGE + "payload/"
STAMP = "src/openrepotools/_release.py"
FORCE_INCLUDE = "[tool.hatch.build.targets.wheel.force-include]"

#: THE MODE HATCHLING 1.27.0 GIVES WHAT IT WRITES ITSELF, the `.dist-info/`
#: files: `set_zip_info_mode`'s default, 0644, with no file-type bits. A
#: file it copies in, a module or a payload file, keeps its type bits, with
#: its permissions normalised to 0644, or 0755 where the owner may execute
#: it (clarifications N4).
WRITTEN_MODE = 0o644

#: The `WHEEL` file hatchling 1.27.0 writes for a pure-Python wheel.
WHEEL_FILE = (b"Wheel-Version: 1.0\nGenerator: hatchling 1.27.0\n"
              b"Root-Is-Purelib: true\nTag: py3-none-any\n")

#: THE WHEEL CHECK'S FOUR WHEELS (contracts/workflows.md, step 6). Each case
#: is the exit the check must give and the name its output must add to the
#: output the wheel as built gives: the file that is wrong.
BYTE_TARGET = "skills/handoff/SKILL.md"
MODE_TARGET = "lanes-index"
WHEEL_CASES = {
    "as-built": (0, None),
    "no-license": (1, "LICENSE"),
    "payload-byte": (1, BYTE_TARGET),
    "payload-mode": (1, MODE_TARGET),
}

#: Every expression a run step may hold, and what the runner gives it.
EXPRESSION = re.compile(r"\$\{\{\s*([A-Za-z_][\w.-]*)\s*\}\}")

#: An index that never answers, for any pip the fake does not catch.
OFFLINE_INDEX = "https://offline.invalid/simple"

NEEDS_BASH = pytest.mark.skipif(shutil.which("bash") is None,
                                reason="the package job's steps are bash")


# --- reading the workflow -----------------------------------------------------

def pinned_reader():
    """The pinned openRepoShape's `scripts/repo_shape.py`, loaded from its
    own file under a name of this module's, so no other module's
    `repo_shape` can stand in for it."""
    spec = importlib.util.spec_from_file_location(
        "_tests_workflow_repo_shape", str(PINNED_READER))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def workflow() -> dict:
    """`tests.yml`, read by the pinned `load_yaml`. A refusal fails the test
    that asked, naming it: a construct outside the standard's subset is
    the workflow's to fix (research R9), not this suite's to read around."""
    reader = pinned_reader()
    try:
        loaded = reader.load_yaml(WORKFLOW)
    except reader.Refusal as refusal:
        pytest.fail(f"the pinned load_yaml refuses {WORKFLOW.name}: "
                    f"{refusal}. tests.yml must stay inside openRepoShape's "
                    f"YAML subset (research R9)", pytrace=False)
    assert isinstance(loaded, dict), f"{WORKFLOW.name} is not a mapping"
    return loaded


def jobs_of(workflow: dict) -> dict:
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict), f"{WORKFLOW.name} has no `jobs:` mapping"
    return jobs


def package_job(workflow: dict) -> dict:
    job = jobs_of(workflow).get("package")
    if not isinstance(job, dict):
        pytest.fail("tests.yml has no `package` job: contracts/workflows.md "
                    "adds it, with steps 1 to 11 (T016)", pytrace=False)
    steps = job.get("steps")
    if not isinstance(steps, list) or not all(isinstance(s, dict)
                                              for s in steps):
        pytest.fail("the package job has no list of steps", pytrace=False)
    return job


def as_text(value) -> str:
    """A YAML value as the runner hands it to a step."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def mapping_text(mapping) -> list:
    return ([f"{key}={as_text(value)}" for key, value in mapping.items()]
            if isinstance(mapping, dict) else [])


def step_text(step: dict) -> str:
    """What a step does, for finding it: its `env:` and `with:` as
    `NAME=value` lines, then its `run:`. Never its `name:`, which says
    what a step is for and not what it does."""
    return "\n".join(mapping_text(step.get("env"))
                     + mapping_text(step.get("with"))
                     + [as_text(step.get("run"))])


def commands(script: str) -> list:
    """A script's command lines as the shell reads them: each continuation
    joined to the line it continues, comment lines dropped."""
    joined = re.sub(r"[ \t]*\\\n[ \t]*", " ", script)
    return [line.strip() for line in joined.splitlines()
            if line.strip() and not line.strip().startswith("#")]


def locate(job: dict) -> dict:
    """Each numbered step's first YAML step, and the report step's, by
    `ANCHORS`. Each is looked for only after the one before it, so the
    steps are in the contract's order, or the test that asked fails naming
    the first one that is not."""
    texts = [step_text(step) for step in job["steps"]]
    found: dict = {}
    start = 2
    for number, title, anchor in ANCHORS:
        hit = next((i for i in range(start, len(texts))
                    if anchor.search(texts[i])), None)
        if hit is None:
            after = (f"after step {number - 1} (YAML step {start - 1})"
                     if found else "after its checkout and setup-python")
            pytest.fail(f"the package job has no step {number}, {title}, "
                        f"{after}: no `run:`, `env:` or `with:` there "
                        f"matches {anchor.pattern!r} (contracts/workflows.md)",
                        pytrace=False)
        found[number], start = hit, hit + 1
    report = next((i for i in range(start, len(texts))
                   if REPORT.search(texts[i])), None)
    if report is None:
        pytest.fail("the package job has no step after its pytest command "
                    "that reads `$RUNNER_TEMP/package-tests.xml` (step 11)",
                    pytrace=False)
    found["report"] = report
    return found


def region(job: dict, found: dict, number, scope: str = "step") -> str:
    """The text a check reads: the job's `env:`, and then the YAML steps
    of step `number` (`step`), every step up to the end of it (`upto`), or
    the whole job (`job`)."""
    texts = [step_text(step) for step in job["steps"]]
    end = (found[ORDER[ORDER.index(number) + 1]] if number != "report"
           else len(texts))
    chosen = {"step": texts[found[number]:end], "upto": texts[:end],
              "job": texts}[scope]
    return "\n".join(mapping_text(job.get("env")) + chosen)


# --- running a step ---------------------------------------------------------------

def git_bytes(*args: str) -> bytes:
    proc = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True,
                          check=False)
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} in {REPO} failed: "
                             f"{proc.stderr.decode('utf-8', 'replace')}")
    return proc.stdout


class Runner:
    """The runner's part in a step, offline, under `root`.

    Bash runs the step's script at the repository's root, as `bash -e`, or
    as `bash --noprofile --norc -eo pipefail` under `shell: bash`, which is
    what GitHub runs. `$RUNNER_TEMP`, `$HOME` and the four `$GITHUB_*`
    files are directories and files under `root`, so a step under test
    never writes into the job that runs this suite; what a step appends to
    `$GITHUB_ENV` and `$GITHUB_PATH` reaches the steps after it, as on the
    runner. The job's `env:` and the step's own apply, and the expressions
    `EXPRESSION` names are filled in. pip is pointed at no index, so a pip
    nothing fakes can fetch nothing.
    """

    SCRUBBED = ("GITHUB_", "RUNNER_", "PIP_", "PIPX_", "OPENREPOTOOLS_",
                "SOURCE_DATE_EPOCH", "BASH_ENV", "PYTHONSTARTUP")

    def __init__(self, workflow: dict, job: dict, root: Path) -> None:
        self.root = root
        self.temp = root / "runner-temp"
        self.home = root / "home"
        self.scripts = root / "scripts"
        for directory in (self.temp, self.home, self.scripts):
            directory.mkdir(parents=True)
        self.files = {name: root / f"{name.lower()}.txt"
                      for name in ("GITHUB_ENV", "GITHUB_PATH",
                                   "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY")}
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(self.SCRUBBED)}
        env.update({
            "RUNNER_TEMP": str(self.temp), "HOME": str(self.home),
            "GITHUB_WORKSPACE": str(REPO), "GITHUB_SHA": Head.sha_of(),
            "CI": "true", "PIP_NO_INDEX": "1", "PIP_INDEX_URL": OFFLINE_INDEX,
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PYTHONDONTWRITEBYTECODE": "1"})
        for name, path in self.files.items():
            path.write_text("", encoding="utf-8")
            env[name] = str(path)
        self.env = env
        self.shell = ((job.get("defaults") or {}).get("run") or {}).get(
            "shell") or ((workflow.get("defaults") or {}).get("run")
                         or {}).get("shell")
        for key, value in (job.get("env") or {}).items():
            self.env[key] = self.evaluate(value)
        self.count = 0

    def evaluate(self, value) -> str:
        def one(match):
            name = match.group(1)
            if name == "runner.temp":
                return str(self.temp)
            if name == "github.workspace":
                return str(REPO)
            if name == "github.sha":
                return self.env["GITHUB_SHA"]
            if name.startswith("env."):
                return self.env.get(name[len("env."):], "")
            pytest.fail(f"a step holds the expression `${{{{ {name} }}}}`, "
                        f"which this test cannot give a value offline",
                        pytrace=False)
        return EXPRESSION.sub(one, as_text(value))

    def run(self, step: dict, script: str | None = None):
        """Run `step`'s `run:`, or `script` in its place, and return the
        finished process, its output as text."""
        self.count += 1
        env = dict(self.env)
        for key, value in (step.get("env") or {}).items():
            env[key] = self.evaluate(value)
        text = self.evaluate(step.get("run") if script is None else script)
        path = self.scripts / f"step-{self.count}.sh"
        path.write_text(text, encoding="utf-8")
        shell = step.get("shell") or self.shell
        if not shell:
            argv = ["bash", "-e", str(path)]
        elif shell == "bash":
            argv = ["bash", "--noprofile", "--norc", "-eo", "pipefail",
                    str(path)]
        else:
            pytest.fail(f"a step asks for `shell: {shell}`, and this test "
                        f"runs bash steps alone", pytrace=False)
        cwd = REPO / as_text(step.get("working-directory") or ".")
        proc = subprocess.run(argv, cwd=str(cwd), env=env,
                              capture_output=True, text=True, timeout=300,
                              check=False)
        self.absorb()
        return proc

    def absorb(self) -> None:
        """`$GITHUB_ENV`'s `NAME=value` and `NAME<<DELIMITER` entries, and
        `$GITHUB_PATH`'s directories, into the environment of the steps
        after; then both files are empty again, as each step finds them."""
        lines = self.files["GITHUB_ENV"].read_text(encoding="utf-8").split("\n")
        at = 0
        while at < len(lines):
            line = lines[at]
            at += 1
            if "<<" in line and ("=" not in line
                                 or line.index("<<") < line.index("=")):
                name, delimiter = line.split("<<", 1)
                value = []
                while at < len(lines) and lines[at] != delimiter:
                    value.append(lines[at])
                    at += 1
                at += 1
                self.env[name] = "\n".join(value)
            elif "=" in line:
                name, value = line.split("=", 1)
                self.env[name] = value
        for line in self.files["GITHUB_PATH"].read_text(
                encoding="utf-8").splitlines():
            if line.strip():
                self.env["PATH"] = line.strip() + os.pathsep + self.env["PATH"]
        for name in ("GITHUB_ENV", "GITHUB_PATH"):
            self.files[name].write_text("", encoding="utf-8")

    def lines(self, proc) -> list:
        """The process's output, stdout then stderr, one entry per line,
        with this runner's own directory written as `<root>`, so that two
        runners' outputs can be compared line for line."""
        text = proc.stdout + "\n" + proc.stderr
        for spelling in {str(self.root.resolve()), str(self.root)}:
            text = text.replace(spelling, "<root>")
        return [line.strip() for line in text.splitlines() if line.strip()]


def shown(proc) -> str:
    return (f"exit {proc.returncode}\n--- stdout ---\n{proc.stdout}"
            f"\n--- stderr ---\n{proc.stderr}")


# --- the lock ------------------------------------------------------------------

def lock_entries(text: str) -> dict:
    """`name==version ; marker` -> its sha256 digests, from a hash lock's
    text: continuation lines joined, comment lines dropped."""
    kept = "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("#"))
    entries = {}
    for entry in re.sub(r"\\\n", " ", kept).splitlines():
        if entry.strip():
            requirement = entry.split("--hash=")[0].strip()
            entries[requirement] = re.findall(r"--hash=sha256:(\S+)", entry)
    return entries


def build_lock_tomli() -> tuple:
    """The build lock's one `tomli` entry: its requirement line, as the
    lock writes it, and its digests."""
    entries = lock_entries(BUILD_LOCK.read_text(encoding="utf-8"))
    tomli = [name for name in entries if name.startswith("tomli==")]
    assert len(tomli) == 1, (f"{BUILD_LOCK.name} holds {len(tomli)} tomli "
                             f"entries, not one: {tomli}")
    assert entries[tomli[0]], f"{BUILD_LOCK.name}'s {tomli[0]} has no hash"
    return tomli[0], entries[tomli[0]]


#: A FAKE `pip`, and a `python3` that is one for `-m pip` alone. Each call
#: is one JSON line in `$FAKE_PIP_LOG`: its arguments, and the text of each
#: requirement file it names, read when it ran. Nothing is installed. Any
#: other `python3` call is the real interpreter's.
FAKE_PIP = r'''#!@PYTHON@
"""A fake pip for tests/test_tests_workflow.py: it records, and installs nothing."""
import json
import os
import sys

REAL = @REAL@


def record(args):
    files = {}
    at = 0
    while at < len(args):
        arg, name = args[at], None
        if arg in ("-r", "--requirement") and at + 1 < len(args):
            name = args[at + 1]
            at += 1
        elif arg.startswith("--requirement="):
            name = arg.split("=", 1)[1]
        elif arg.startswith("-r") and len(arg) > 2:
            name = arg[2:]
        if name is not None:
            path = os.path.abspath(name)
            try:
                with open(path, encoding="utf-8") as handle:
                    files[path] = handle.read()
            except OSError:
                files[path] = None
        at += 1
    with open(os.environ["FAKE_PIP_LOG"], "a", encoding="utf-8") as log:
        log.write(json.dumps({"args": args, "files": files}) + "\n")


args = sys.argv[1:]
if os.path.basename(sys.argv[0]).startswith("pip"):
    record(args)
    sys.exit(0)
at = 0
while at < len(args) and args[at].startswith("-") and args[at] not in ("-", "-m", "-c"):
    at += 1
if args[at:at + 2] == ["-m", "pip"]:
    record(args[at + 2:])
    sys.exit(0)
os.execv(REAL, [REAL] + args)
'''


def fake_pip(directory: Path) -> Path:
    directory.mkdir(parents=True)
    text = (FAKE_PIP.replace("@PYTHON@", sys.executable)
            .replace("@REAL@", repr(sys.executable)))
    for name in ("python3", "python", "pip", "pip3"):
        path = directory / name
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)
    return directory


def pip_command(args: list) -> str:
    return next((arg for arg in args if not arg.startswith("-")), "")


def only_binary_all(args: list) -> bool:
    return ("--only-binary=:all:" in args
            or any(a == "--only-binary" and b == ":all:"
                   for a, b in zip(args, args[1:])))


# --- HEAD's own files, and the wheels made of them ------------------------------

class Head:
    """HEAD's files, read from git and never from the working tree: the
    blobs and modes a wheel built at that commit is checked against."""

    @staticmethod
    def sha_of() -> str:
        return git_bytes("rev-parse", "HEAD").decode("ascii").strip()

    def __init__(self) -> None:
        self.sha = self.sha_of()
        self.epoch = int(git_bytes("log", "-1", "--format=%ct", "HEAD")
                         .decode("ascii").strip())
        self.modes = {}
        for entry in git_bytes("ls-tree", "-r", "-z", "--full-tree",
                               "HEAD").split(b"\0"):
            if entry:
                meta, path = entry.split(b"\t", 1)
                mode, kind, _ = meta.decode("ascii").split(" ")
                if kind == "blob":
                    self.modes[path.decode("utf-8")] = mode
        self._blobs: dict = {}
        pyproject = self.blob("pyproject.toml").decode("utf-8")
        self.payload = force_include_paths(pyproject)
        self.modules = tuple(sorted(
            path for path in self.modes
            if re.fullmatch(r"src/openrepotools/[^/]+\.py", path)))
        self.version = stamp_version(self.blob(STAMP).decode("utf-8"))
        self.project = toml_table(pyproject, "project")
        self.scripts = toml_table(pyproject, "project.scripts")
        self.dist_info = f"openrepotools-{self.version}.dist-info/"
        self.wheel_name = f"openrepotools-{self.version}-py3-none-any.whl"

    def blob(self, path: str) -> bytes:
        if path not in self.modes:
            raise AssertionError(f"HEAD has no file {path}")
        if path not in self._blobs:
            self._blobs[path] = git_bytes("cat-file", "blob", f"HEAD:{path}")
        return self._blobs[path]

    def zip_mode(self, path: str) -> int:
        """The mode hatchling 1.27.0 gives a file it copies in: a regular
        file at 0755 where git records `100755`, and at 0644 otherwise."""
        mode = self.modes[path]
        if mode not in ("100755", "100644"):
            raise AssertionError(f"{path} is {mode} at HEAD, neither 100755 "
                                 "nor 100644")
        return 0o100755 if mode == "100755" else 0o100644

    def metadata(self, license_file: bool = True) -> bytes:
        lines = ["Metadata-Version: 2.4", f"Name: {self.project['name']}",
                 f"Version: {self.version}",
                 f"License-Expression: {self.project['license']}"]
        if license_file:
            lines.append("License-File: LICENSE")
        lines.append(f"Requires-Python: {self.project['requires-python']}")
        return ("\n".join(lines) + "\n").encode("utf-8")

    def entry_points(self) -> bytes:
        return ("[console_scripts]\n" + "".join(
            f"{name} = {ref}\n" for name, ref in self.scripts.items())
        ).encode("utf-8")


def force_include_paths(pyproject: str) -> tuple:
    """`<P>` of each `"<P>" = "openrepotools/payload/<P>"` in the
    force-include table, in order: read by line, so that it reads the same
    on a Python with no `tomllib`, and held to `tomllib` where there is one."""
    lines = pyproject.split("\n")
    headers = [i for i, line in enumerate(lines)
               if line.strip() == FORCE_INCLUDE]
    assert len(headers) == 1, f"HEAD's pyproject.toml has {len(headers)} " \
                              f"{FORCE_INCLUDE} tables, not one"
    entry = re.compile(r'"([^"\\]+)" = "([^"\\]+)"')
    paths = []
    for line in lines[headers[0] + 1:]:
        line = line.strip()
        if line.startswith("["):
            break
        if not line or line.startswith("#"):
            continue
        match = entry.fullmatch(line)
        assert match and match.group(2) == PAYLOAD + match.group(1), (
            f"HEAD's force-include table holds a line this test does not "
            f"read: {line}")
        paths.append(match.group(1))
    try:
        import tomllib
    except ImportError:
        return tuple(paths)
    table = (tomllib.loads(pyproject)["tool"]["hatch"]["build"]["targets"]
             ["wheel"]["force-include"])
    assert list(table) == paths, "the force-include table reads one way by " \
                                 "line and another by tomllib"
    return tuple(paths)


def toml_table(pyproject: str, name: str) -> dict:
    """The `key = "value"` lines of one table, read by line."""
    values, inside = {}, False
    for line in pyproject.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            inside = stripped == f"[{name}]"
            continue
        match = re.fullmatch(r'"?([A-Za-z0-9_.-]+)"? = "([^"]*)"', stripped)
        if inside and match:
            values[match.group(1)] = match.group(2)
    return values


def stamp_version(text: str) -> str:
    versions = re.findall(r'(?m)^VERSION = "([^"]*)"$', text)
    assert len(versions) == 1, f"HEAD's {STAMP} holds {len(versions)} " \
                               "VERSION lines, not one"
    return versions[0]


@pytest.fixture(scope="module")
def head() -> Head:
    return Head()


def built_members(head: Head) -> dict:
    """The wheel `pip wheel` builds at HEAD, as hatchling 1.27.0 lays it
    out: each member's name -> (bytes, zip mode), RECORD aside."""
    members = {}
    for path in head.modules:
        members[PACKAGE + path.rsplit("/", 1)[1]] = (head.blob(path),
                                                     head.zip_mode(path))
    for rel in head.payload:
        members[PAYLOAD + rel] = (head.blob(rel), head.zip_mode(rel))
    info = head.dist_info
    members[info + "WHEEL"] = (WHEEL_FILE, WRITTEN_MODE)
    members[info + "entry_points.txt"] = (head.entry_points(), WRITTEN_MODE)
    members[info + "METADATA"] = (head.metadata(), WRITTEN_MODE)
    members[info + "licenses/LICENSE"] = (head.blob("LICENSE"), WRITTEN_MODE)
    return members


def case_members(head: Head, case: str) -> dict:
    """The wheel as built, with what `case` changes."""
    members = built_members(head)
    info = head.dist_info
    if case == "no-license":
        del members[info + "licenses/LICENSE"]
        members[info + "METADATA"] = (head.metadata(license_file=False),
                                      WRITTEN_MODE)
    elif case == "payload-byte":
        assert PAYLOAD + BYTE_TARGET in members, (
            f"{BYTE_TARGET} is no longer a payload file: pick another")
        data, mode = members[PAYLOAD + BYTE_TARGET]
        changed = bytearray(data)
        changed[len(changed) // 2] ^= 0x01
        members[PAYLOAD + BYTE_TARGET] = (bytes(changed), mode)
    elif case == "payload-mode":
        assert members.get(PAYLOAD + MODE_TARGET, (b"", 0))[1] == 0o100755, (
            f"{MODE_TARGET} is no longer an executable payload file: pick "
            "another")
        members[PAYLOAD + MODE_TARGET] = (members[PAYLOAD + MODE_TARGET][0],
                                          0o100644)
    else:
        assert case == "as-built", case
    return members


def write_wheel(path: Path, head: Head, members: dict) -> None:
    """`members`, and the RECORD of them, as one zip at the commit's time."""
    when = datetime.fromtimestamp(max(head.epoch, 315532800), timezone.utc)
    record = []
    for name, (data, _) in members.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest())
        record.append(f"{name},sha256={digest.rstrip(b'=').decode()},"
                      f"{len(data)}")
    record.append(f"{head.dist_info}RECORD,,")
    entries = dict(members)
    entries[head.dist_info + "RECORD"] = (
        ("\n".join(record) + "\n").encode("utf-8"), WRITTEN_MODE)
    with zipfile.ZipFile(path, "w") as wheel:
        for name, (data, mode) in entries.items():
            info = zipfile.ZipInfo(name, when.timetuple()[:6])
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            wheel.writestr(info, data)


def wheel_check_script(step: dict) -> tuple:
    """Step 6's script up to and including its heredoc's closing `PY`, and
    the heredoc's Python."""
    script = as_text(step.get("run"))
    lines = script.split("\n")
    openers = [i for i, line in enumerate(lines)
               if HEREDOC_OPENER.fullmatch(line)]
    assert len(openers) == 1, (f"step 6's YAML step opens {len(openers)} "
                               f"`python3 - <<'PY'` heredocs, not one")
    start = openers[0]
    assert "PY" in lines[start + 1:], "step 6's heredoc has no closing `PY`"
    end = lines.index("PY", start + 1)
    return ("\n".join(lines[:end + 1]) + "\n",
            "\n".join(lines[start + 1:end]) + "\n")


def run_wheel_check(workflow: dict, head: Head, root: Path, members: dict):
    """Step 6, over the wheel `members` make, placed where step 5 leaves its
    two builds: the finished process and its runner."""
    job = package_job(workflow)
    step = job["steps"][locate(job)[6]]
    script, _ = wheel_check_script(step)
    runner = Runner(workflow, job, root)
    first = runner.temp / "a" / head.wheel_name
    first.parent.mkdir()
    write_wheel(first, head, members)
    (runner.temp / "b").mkdir()
    shutil.copyfile(first, runner.temp / "b" / head.wheel_name)
    return runner.run(step, script=script), runner


# --- the triggers and the jobs ---------------------------------------------------

@NEEDS_UPSTREAM
def test_tests_yml_push_runs_on_main_and_every_release_branch(workflow):
    """FR-025: a push to `main` or to any `release/v*` branch runs the
    workflow, and nothing else about `push` is filtered."""
    assert workflow.get("on", {}).get("push") == PUSH, (
        f"`on.push` is {workflow.get('on', {}).get('push')!r}, not {PUSH!r}")


@NEEDS_UPSTREAM
def test_tests_yml_its_other_triggers_are_unchanged(workflow):
    """`pull_request` with `labeled` beside GitHub's three defaults, the
    nightly cron at 04:17 UTC and `workflow_dispatch`, and no trigger
    besides those and `push`."""
    on = workflow.get("on")
    assert isinstance(on, dict), "tests.yml has no `on:` mapping"
    assert sorted(on) == sorted(["pull_request", "push", "schedule",
                                 "workflow_dispatch"]), sorted(on)
    assert on["pull_request"] == PULL_REQUEST, on["pull_request"]
    assert on["schedule"] == SCHEDULE, on["schedule"]
    assert on["workflow_dispatch"] is None, on["workflow_dispatch"]


@NEEDS_UPSTREAM
def test_tests_yml_has_exactly_the_four_gate_jobs(workflow):
    """The release gate's ids (FR-046) and no fifth. None has a
    `name:`, so each check run is named by its id, and none has an `if:`,
    so every trigger runs all four."""
    jobs = jobs_of(workflow)
    assert sorted(jobs) == sorted(JOB_IDS), (
        f"the jobs are {list(jobs)}, not {list(JOB_IDS)}")
    for job_id in JOB_IDS:
        assert "name" not in jobs[job_id], f"`{job_id}` has a `name:`"
        assert "if" not in jobs[job_id], f"`{job_id}` has an `if:`"


@NEEDS_UPSTREAM
@pytest.mark.parametrize("job_id", sorted(EXISTING_JOBS))
def test_tests_yml_existing_job_keeps_todays_runner_checkout_python_and_runs(
        workflow, job_id):
    """The three jobs the contract leaves alone keep today's runner, checkout
    options, Python and `run:` commands, but for #77's xdist pin and flags on
    the test jobs, which are held by name below."""
    job = jobs_of(workflow).get(job_id)
    assert isinstance(job, dict), f"tests.yml has no `{job_id}` job"
    want = EXISTING_JOBS[job_id]
    steps = job.get("steps") or []
    assert job.get("runs-on") == "ubuntu-24.04", job.get("runs-on")
    assert len(steps) >= 2, f"`{job_id}` has {len(steps)} steps"
    assert steps[0].get("uses") == CHECKOUT, steps[0]
    assert steps[0].get("with") == want["checkout"], steps[0].get("with")
    assert steps[1].get("uses") == SETUP_PYTHON, steps[1]
    assert steps[1].get("with") == {"python-version": want["python"]}, \
        steps[1].get("with")
    runs = [step["run"] for step in steps if "run" in step]
    assert runs == want["runs"], f"`{job_id}`'s `run:` commands moved: {runs}"


@NEEDS_UPSTREAM
@pytest.mark.parametrize("job_id", TEST_JOBS)
def test_tests_yml_test_job_installs_one_pinned_xdist_and_runs_three_wide(
        workflow, job_id):
    """#77, step 2: the install names pytest-xdist at ONE exact version beside
    pytest's own pin, and the run carries `-n 3`, `--dist loadfile` and
    `--no-loadscope-reorder`. Each is held on its own, so that dropping any one
    says which: the width is gone, a file's tests are split across workers, the
    pin floats with the day, or xdist hands the shell suite out nearly last."""
    runs = [step["run"] for step in jobs_of(workflow)[job_id]["steps"]
            if "run" in step]
    installs = [run for run in runs if "pip install" in run]
    assert len(installs) == 1, f"`{job_id}` has {len(installs)} pip installs"
    words = shlex.split(installs[0])
    assert "pytest==8.3.4" in words, words
    assert [w for w in words if "xdist" in w] == [XDIST_PIN], (
        f"`{job_id}` installs {[w for w in words if 'xdist' in w]}, "
        f"not exactly {XDIST_PIN}")
    commands = [run for run in runs if "-m pytest" in run]
    assert len(commands) == 1, f"`{job_id}` has {len(commands)} pytest commands"
    argv = shlex.split(commands[0])
    assert "-n" in argv and argv[argv.index("-n") + 1:][:1] == ["3"], (
        f"`{job_id}` does not run `-n 3`: {commands[0]}")
    assert "--dist" in argv and argv[argv.index("--dist") + 1:][:1] == ["loadfile"], (
        f"`{job_id}` does not run `--dist loadfile`: {commands[0]}")
    assert "--no-loadscope-reorder" in argv, (
        f"`{job_id}` does not run `--no-loadscope-reorder`, so xdist sorts the "
        f"shell suite's module by size and hands it out nearly last: {commands[0]}")


@NEEDS_UPSTREAM
@pytest.mark.parametrize("job_id", ("guard-launch-mode", "package"))
def test_tests_yml_the_other_jobs_run_no_xdist(workflow, job_id):
    """The guard job runs `tests/run.sh -k`, which is serial and stays so, and
    the `package` job runs its three modules at the pin the lock gives it: no
    xdist in either."""
    job = jobs_of(workflow)[job_id]
    text = "\n".join(step_text(step) for step in job["steps"])
    assert "xdist" not in text, f"`{job_id}` mentions xdist"
    commands = [line for line in text.replace("\\\n", " ").splitlines()
                if "-m pytest" in line or "run.sh" in line]
    assert all("-n" not in line.split() and "--dist" not in line.split()
               for line in commands), f"`{job_id}` runs pytest three wide: {commands}"


def test_tests_yml_no_longer_says_pytest_is_the_only_thing_installed():
    """The comment above the install said so, and with pytest-xdist beside it
    that is no longer true."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "is the only thing installed here" not in text
    assert XDIST_PIN in text


def test_tests_yml_header_comment_names_both_push_branches_and_four_jobs():
    """FR-025: the comment above `on:` says that `push` covers `main` and
    every `release/v*` branch, and names the four jobs every trigger runs.
    It no longer says "(main only)" or "those same three jobs". Read as
    text, since a comment is not data, and with each job id in backticks,
    as the file writes every one."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    assert "on:" in lines, "tests.yml has no `on:` line"
    at = lines.index("on:")
    block = []
    while at > 0 and lines[at - 1].startswith("#"):
        at -= 1
        block.insert(0, lines[at])
    text = " ".join(line.lstrip("#").strip() for line in block)
    assert block, "tests.yml has no comment directly above `on:`"
    assert re.search(r"\bmain\b", text), f"the header names no `main`: {text}"
    assert "release/v*" in text, f"the header names no `release/v*`: {text}"
    missing = [job_id for job_id in JOB_IDS if f"`{job_id}`" not in text]
    assert not missing, f"the header names no {missing}: {text}"
    for stale in ("(main only)", "same three"):
        assert stale not in text, f"the header still says {stale!r}: {text}"


def test_tests_yml_holds_no_digest_of_its_own():
    """tests.yml holds no digest of tomli's. The build lock's entry is copied
    at run time, and the pipx lock carries the same entry (research R12): no
    `--hash=sha256:` and no 64-digit hex string anywhere in the file."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert not re.search(r"--hash[= ]sha256:", text), "tests.yml holds a --hash"
    digests = re.findall(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])",
                         text)
    assert not digests, f"tests.yml holds a digest of its own: {digests}"


# --- the package job, read ------------------------------------------------------

@NEEDS_UPSTREAM
def test_tests_yml_package_runs_on_ubuntu_python_3_9_with_the_submodule(
        workflow):
    """Steps 1 and 2: the pinned checkout, with `submodules: true` and
    `fetch-depth: 1`, then the pinned setup-python at `'3.9'`, the oldest
    Python the package supports, on ubuntu."""
    job = package_job(workflow)
    steps = job["steps"]
    assert job.get("runs-on") == "ubuntu-24.04", job.get("runs-on")
    assert len(steps) >= 2, f"the package job has {len(steps)} steps"
    assert steps[0].get("uses") == CHECKOUT, steps[0]
    assert steps[0].get("with") == {"submodules": True, "fetch-depth": 1}, \
        steps[0].get("with")
    assert steps[1].get("uses") == SETUP_PYTHON, steps[1]
    assert steps[1].get("with") == {"python-version": "3.9"}, (
        f"{steps[1].get('with')!r}: the version is the string '3.9', "
        "quoted, as a bare 3.9 is a number")


@NEEDS_UPSTREAM
def test_tests_yml_package_carries_steps_4_to_11_in_order(workflow):
    """Steps 4 to 11, each its own YAML step or steps, in the contract's
    order, with step 11's report read in a step after its pytest command."""
    found = locate(package_job(workflow))
    indices = [found[key] for key in ORDER]
    assert indices == sorted(set(indices)), found


def source_date_epoch_reaches_pip(text: str) -> bool:
    """`SOURCE_DATE_EPOCH` is exported, or set on each `pip wheel` command:
    an assignment alone never reaches the build."""
    if re.search(r"\bexport[ \t]+SOURCE_DATE_EPOCH\b", text):
        return True
    builds = [cmd for cmd in commands(text) if re.search(r"\bpip\s+wheel\b",
                                                         cmd)]
    return bool(builds) and all(cmd.startswith("SOURCE_DATE_EPOCH=")
                                for cmd in builds)


def runs_the_pytest_command(text: str) -> bool:
    """A command that is `PYTEST_COMMAND`, word for word as the shell splits
    it, after any `NAME=value` set on it."""
    want = shlex.split(PYTEST_COMMAND)
    for command in commands(text):
        try:
            words = shlex.split(command)
        except ValueError:
            continue
        while words and (words[0] == "env" or re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0])):
            words.pop(0)
        if words == want:
            return True
    return False


def has(pattern: str):
    compiled = re.compile(pattern)
    return lambda text: compiled.search(text) is not None


def has_all(*parts: str):
    return lambda text: all(part in text for part in parts)


#: WHAT EACH STEP MUST SAY, from the contract's own words: per step, what
#: is checked, where (`step`: its own YAML steps; `upto`: every step up to
#: its end; `job`: the whole job; each with the job's `env:`), and how.
STEP_CHECKS = {
    4: (
        ("names tomli", "step", has(r"\btomli\b")),
        ("installs by hash, --require-hashes", "step", has(r"--require-hashes")),
        ("wheels only, --only-binary=:all:", "step",
         has(r"--only-binary[= ]:all:")),
        ("from a file under $RUNNER_TEMP", "step", has(RT)),
        ("then installs pytest==8.3.4", "step", has(r"pytest==8\.3\.4")),
    ),
    5: (
        ('SOURCE_DATE_EPOCH="$(git log -1 --format=%ct HEAD)"', "step",
         has(re.escape('SOURCE_DATE_EPOCH="$(git log -1 --format=%ct HEAD)"'))),
        ("which reaches both builds, exported or set on each", "step",
         source_date_epoch_reaches_pip),
        ("pip wheel --no-deps", "step", has(r"--no-deps")),
        ('into "$RUNNER_TEMP/a"', "step", has(RT + r"[\"']?/a\b")),
        ('and into "$RUNNER_TEMP/b"', "step", has(RT + r"[\"']?/b\b")),
        ("the two compared with cmp", "step", has(r"\bcmp\b")),
    ),
    7: (
        ("pipx by hash, --require-hashes", "step", has(r"--require-hashes")),
        ("wheels only, --only-binary=:all:", "step",
         has(r"--only-binary[= ]:all:")),
        ("PIPX_HOME under $RUNNER_TEMP", "job",
         has(r"\bPIPX_HOME=[\"']?" + RT)),
        ("PIPX_BIN_DIR under $RUNNER_TEMP", "job",
         has(r"\bPIPX_BIN_DIR=[\"']?" + RT)),
    ),
    8: (
        ("the link openRepoTools in PIPX_BIN_DIR", "step",
         has_all("PIPX_BIN_DIR", "openRepoTools")),
    ),
    9: tuple((f"the line `{line.strip()}`", "step", has_all(line.strip()))
             for line in UNSTAMPED_VERSION),
    10: (
        ('OPENREPOTOOLS_BIN_DIR="$PIPX_BIN_DIR"', "step",
         has(r"\bOPENREPOTOOLS_BIN_DIR=[\"']?(?:\$\{?PIPX_BIN_DIR\}?"
             r"|\$\{\{\s*env\.PIPX_BIN_DIR\s*\}\})")),
        ("runs --install", "step", has(r"--install\b")),
        ("with HOME a fresh directory", "step",
         has(r"(?<![A-Za-z0-9_])HOME=")),
        ("a PATH first holding a gh and a curl that exit 1", "step",
         lambda text: all(re.search(p, text) for p in (
             r"\bgh\b", r"\bcurl\b", r"exit 1(?![0-9])", r"\bPATH="))),
        ("the skip line, exactly", "step", has_all(*SKIP_LINE_PARTS)),
        ("the count line, exactly", "step", has_all(*COUNT_LINE_PARTS)),
        ("28 receipt rows", "step", has(r"\b28\b")),
    ),
    11: (
        (f"runs `{PYTEST_COMMAND}`", "step", runs_the_pytest_command),
        ("with OPENREPOTOOLS_TEST_WHEEL the built wheel", "upto",
         has(r"\bOPENREPOTOOLS_TEST_WHEEL\b")),
    ),
}


@NEEDS_UPSTREAM
@pytest.mark.parametrize("number", sorted(STEP_CHECKS),
                         ids=[f"step-{n}" for n in sorted(STEP_CHECKS)])
def test_tests_yml_package_step_says_what_the_contract_says(workflow, number):
    """What contracts/workflows.md writes for each of steps 4 to 11, read
    from the step itself. Steps 4, 6 and 11's report are also run, below."""
    job = package_job(workflow)
    found = locate(job)
    missing = [what for what, scope, check in STEP_CHECKS[number]
               if not check(region(job, found, number, scope))]
    assert not missing, (f"step {number} of the package job does not say: "
                         f"{missing}\n--- the step ---\n"
                         f"{region(job, found, number)}")


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
def test_tests_yml_package_sets_the_git_identity_by_environment(
        workflow, tmp_path):
    """Step 3: the identity the `tests` job gives the fixture commits, by
    the environment, here the job's `env:` or what the steps before step 4
    append to `$GITHUB_ENV`, which are run to see it. Never by
    `git config --global` anywhere in the job."""
    job = package_job(workflow)
    found = locate(job)
    runner = Runner(workflow, job, tmp_path)
    for step in job["steps"][2:found[4]]:
        if "run" in step:
            proc = runner.run(step)
            assert proc.returncode == 0, shown(proc)
    got = {name: runner.env.get(name) for name in GIT_IDENTITY}
    assert got == GIT_IDENTITY, f"before step 4 the identity is {got}"
    texts = [step_text(step) for step in job["steps"]]
    assert not [t for t in texts if re.search(r"\bgit\s+config\b[^\n]*--global",
                                              t)], "the job runs git config --global"


# --- the package job, run ----------------------------------------------------------

@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
def test_tests_yml_package_tomli_is_the_build_locks_own_entry_with_every_hash(
        workflow, tmp_path):
    """Step 4, run under a fake pip: its first install is by hash, wheels
    only, from a file under `$RUNNER_TEMP` holding the build lock's whole
    `tomli` entry, its requirement line and every one of its digests, and
    nothing else; pytest==8.3.4 is installed after it. With no digest in
    tests.yml itself, the entry can only have come from the lock."""
    job = package_job(workflow)
    found = locate(job)
    requirement, digests = build_lock_tomli()
    runner = Runner(workflow, job, tmp_path / "run")
    log = tmp_path / "pip-calls.jsonl"
    runner.env["PATH"] = (str(fake_pip(tmp_path / "fakes")) + os.pathsep
                          + runner.env["PATH"])
    runner.env["FAKE_PIP_LOG"] = str(log)
    procs = [runner.run(step) for step in job["steps"][found[4]:found[5]]]
    said = "\n".join(shown(proc) for proc in procs)
    calls = ([json.loads(line) for line in log.read_text(
        encoding="utf-8").splitlines()] if log.is_file() else [])
    installs = [call for call in calls if pip_command(call["args"]) == "install"]
    assert installs, f"step 4 ran no pip install:\n{said}"
    first = installs[0]
    assert "--require-hashes" in first["args"], (
        f"step 4's first pip install is not by hash: {first['args']}\n{said}")
    assert only_binary_all(first["args"]), (
        f"step 4's first pip install is not wheels only: {first['args']}")
    assert len(first["files"]) == 1, (
        f"step 4's first install names {len(first['files'])} requirement "
        f"files, not one: {first['args']}")
    [(path, text)] = first["files"].items()
    assert text is not None, f"step 4 named {path}, which it never wrote"
    assert Path(path).resolve().is_relative_to(runner.temp.resolve()), (
        f"{path} is not under $RUNNER_TEMP")
    entries = lock_entries(text)
    assert list(entries) == [requirement], (
        f"step 4 installs {list(entries)}, not the lock's {requirement!r}:\n"
        f"{text}")
    assert sorted(entries[requirement]) == sorted(digests), (
        f"step 4's tomli carries {len(entries[requirement])} digests, and the "
        f"lock's entry {len(digests)}: every hash, and only those")
    later = [call for call in installs[1:]
             if "pytest==8.3.4" in call["args"]
             or any("pytest==8.3.4" in (body or "")
                    for body in call["files"].values())]
    assert later, f"step 4 installs no pytest==8.3.4 after tomli:\n{said}"


@NEEDS_UPSTREAM
def test_tests_yml_package_wheel_check_parses_as_python_3_9(workflow):
    """Step 6's heredoc runs on the job's Python, 3.9: it must parse there."""
    job = package_job(workflow)
    _, body = wheel_check_script(job["steps"][locate(job)[6]])
    ast.parse(body, filename="step 6's heredoc", feature_version=(3, 9))


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
def test_tests_yml_package_wheel_check_passes_the_wheel_as_built(
        workflow, head, tmp_path):
    """Step 6 over the wheel `pip wheel` builds at HEAD, made here from
    HEAD's blobs and modes: it passes, exit 0."""
    proc, _ = run_wheel_check(workflow, head, tmp_path, built_members(head))
    assert proc.returncode == 0, shown(proc)


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@pytest.mark.parametrize("case", [c for c in WHEEL_CASES if c != "as-built"])
def test_tests_yml_package_wheel_check_refuses_a_wheel_that_is_not_the_commits(
        workflow, head, tmp_path, case):
    """Step 6 over the wheel as built with one thing wrong: no
    `licenses/LICENSE`, a payload file with one byte changed, or a payload
    file that lost its execute bit. It exits 1, and what it prints beyond
    what the wheel as built gives names the file that is wrong."""
    built, built_runner = run_wheel_check(workflow, head, tmp_path / "built",
                                          built_members(head))
    assert built.returncode == 0, ("the wheel as built does not pass, so "
                                   "this case proves nothing:\n" + shown(built))
    proc, runner = run_wheel_check(workflow, head, tmp_path / "case",
                                   case_members(head, case))
    code, name = WHEEL_CASES[case]
    assert proc.returncode == code, shown(proc)
    before = set(built_runner.lines(built))
    new = [line for line in runner.lines(proc) if line not in before]
    assert any(name in line for line in new), (
        f"the check refused, and named no {name}:\n" + shown(proc))


def junit_report(tests: int, skipped: int = 0, failures: int = 0,
                 errors: int = 0) -> str:
    """A report as pytest 8.3.4's `--junitxml` writes one."""
    cases = []
    for number in range(tests):
        inner = ""
        if number < skipped:
            inner = '<skipped type="pytest.skip" message="a reason">a reason</skipped>'
        elif number < skipped + failures:
            inner = '<failure message="assert False">assert False</failure>'
        elif number < skipped + failures + errors:
            inner = '<error message="failed on setup">failed on setup</error>'
        cases.append(f'<testcase classname="tests.test_package" '
                     f'name="test_{number}" time="0.001">{inner}</testcase>')
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<testsuites name="pytest tests"><testsuite name="pytest" '
            f'errors="{errors}" failures="{failures}" skipped="{skipped}" '
            f'tests="{tests}" time="0.010" '
            'timestamp="2026-10-18T00:00:00.000000+00:00" hostname="runner">'
            + "".join(cases) + "</testsuite></testsuites>\n")


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@pytest.mark.parametrize("report, passes", [
    ({"tests": 3}, True),
    ({"tests": 0}, False),
    ({"tests": 3, "skipped": 1}, False),
    ({"tests": 3, "failures": 1}, False),
    ({"tests": 3, "errors": 1}, False),
], ids=["three-ran", "none-ran", "one-skipped", "one-failed", "one-error"])
def test_tests_yml_package_report_step_fails_on_any_skip_or_none_run(
        workflow, tmp_path, report, passes):
    """Step 11's report step, over a JUnit report at
    `$RUNNER_TEMP/package-tests.xml`: it passes only with at least one test
    and no skip, failure or error (design.md Decision 9's enforcer)."""
    job = package_job(workflow)
    step = job["steps"][locate(job)["report"]]
    runner = Runner(workflow, job, tmp_path)
    (runner.temp / "package-tests.xml").write_text(junit_report(**report),
                                                   encoding="utf-8")
    proc = runner.run(step)
    assert (proc.returncode == 0) is passes, shown(proc)


def test_tests_yml_synthetic_wheels_are_wheel_md_s_members(head):
    """The wheels above are the one contracts/wheel.md lists: HEAD's
    modules, the 24 payload files and the five `.dist-info` names, each
    case differing from the wheel as built in its one member alone."""
    built = built_members(head)
    info = head.dist_info
    assert len(head.payload) == 24, head.payload
    assert {PACKAGE + "__init__.py", PACKAGE + "_release.py"} <= set(built)
    assert sorted(name[len(info):] for name in built if name.startswith(info)) \
        == sorted(["METADATA", "WHEEL", "entry_points.txt",
                   "licenses/LICENSE"]), "RECORD is added when written"
    changed = {"no-license": {info + "licenses/LICENSE", info + "METADATA"},
               "payload-byte": {PAYLOAD + BYTE_TARGET},
               "payload-mode": {PAYLOAD + MODE_TARGET}}
    for case, names in changed.items():
        members = case_members(head, case)
        differ = {name for name in set(built) | set(members)
                  if built.get(name) != members.get(name)}
        assert differ == names, (case, differ)
