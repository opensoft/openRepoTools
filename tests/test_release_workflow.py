# SPDX-License-Identifier: Apache-2.0
"""`.github/workflows/release.yml`, its two hash locks and its stamp writer
(opensoft/openRepoTools#228, User Story 5).

THE RELEASE IS HELD OFFLINE. The workflow builds the wheel, uploads it to
TestPyPI, checks the install on three legs and uploads it to PyPI, and
nothing here runs it. What can be held with no network is the file itself,
read with the PINNED standard's `repo_shape.load_yaml` (research R9), and the
scripts it carries. Most of the scripts whose outcome decides what is built,
uploaded or installed are RUN here, as GitHub runs a step, under fakes that
answer as the forge, the index, `curl`, the build and pipx do:

- in the build job, the version check and the repository guard, the ref,
  branch, clean-checkout, environments, gate and digest steps, the stamp
  writer, the build step's byte-for-byte compare, and the wheel check;
- in each upload job, the guard again, the dist step, the approval and tag
  re-checks, and both index checks;
- in the install check, the fetch from TestPyPI, the digest step, pipx's
  install and its one link, `--version`, and the 3.9 leg's compile.

SIX ARE STILL READ ONLY AS TEXT. Five are held by their commands: the
build's tool install from its hash lock and its two `git archive`
extractions, and the install check's install of pipx from its hash lock,
its offline `--install`, and the macOS rerun, which is held to the offline
`--install` line for line but for the lines it names. The sixth, the
build's record of the wheel, is held by its place and by its id, which the
build job's outputs read.
Every job's whole step list is pinned in order (`STEP_ORDER`).

contracts/workflows.md's `release.yml` list is the specification, one prefix
per part of it (plan.md, "The test layout"):

- `test_release_trigger_*`: a dispatch with `version` is the only trigger, no
  permission is granted at the top, one release runs at a time, and the input
  reaches every script through the environment alone;
- `test_release_lock_*`: both hash locks, one version per entry by sha256,
  hatchling at `pyproject.toml`'s pin, and pipx 1.11.1 below Python 3.10 and
  1.17.8 from 3.10;
- `test_release_build_*`: the build job's checkout, pins, steps and order;
  the ref step, run on a branch and on tags a forge and a `file://` origin
  hold, and the branch step, held to the rehearsal rule; the clean step run
  on a checkout moved or dirtied, the environments step under a forge, the
  gate on `tests.yml`'s four jobs and the digest step, each run under a
  forge, the digest step also in a copy of the checkout whose standard or
  pin names another definition; the build step run with a fake build;
  step 13's wheel check run on synthetic wheels made from HEAD's blobs; and
  the digest label, one literal in the installer, the pin and the standard;
- `test_release_stamp_writer_*`: the build's own stamp writer, run on a copy
  of the committed stamp and read back by `--version` from a `package_tree`;
- `test_release_guard_build_*` and `test_release_guard_upload_*` (FR-048):
  the repository guard, run under each row of contracts/workflows.md's table,
  and each upload job's own first step;
- `test_release_upload_*`: the four jobs' permissions and step lists, the
  two environments, the two conditions, and each upload job's checks around
  the pinned action, the dist step run over the files a case puts in
  `dist/`, the approval and tag re-checks run under a forge and the index
  checks under a fake index;
- `test_release_install_check_*`: the three legs and what each runs, its
  fetch, digest, pipx, `--version` and 3.9 steps run;
- `test_release_reads_*`: no step reads what the code leg will not hold;
- `test_release_header_*`: the RELEASING header's six sections, in order.

WRITTEN BEFORE THE WORKFLOW (tasks.md T018, ahead of T019 to T021). Until
`release.yml` exists, every test that reads it FAILS, naming the file and the
tasks that write it: never a skip, and never an error at collection, because
nothing is read from it until a test runs. The lock tests and the digest
label's test read nothing of it, and pass on their own.

HOW A STEP IS FOUND, which is this file's half of the contract with the
workflow (T019 to T021 write the other half):

- the repository guard is the step whose outputs the build job records as
  `to-testpypi` and `to-pypi` (contracts/workflows.md, step 14);
- the steps adapted from openRepoShape v1.1.0 are found by THE MODEL'S OWN
  NAMES, as prefixes (`BUILD_STEPS` below): step for step, as FR-028 has the
  workflow taken over;
- each upload job's guard is its first step ("Its first step runs the
  repository guard again, on its own");
- the install legs' own steps are found by their `if:`.

`STEP_ORDER`, which pins every job's whole step list in order, follows these
rules, and finds every other step by a prefix of its label: an action by the
action it uses, and this workflow's own steps, the install check's
`--version` among them, by their own names. So a step found by its role can
be renamed and still hold its place.

HOW A STEP IS RUN, as GitHub runs a `shell: bash` step: its `run:` text in a
file, `bash --noprofile --norc -eo pipefail <file>`, with the workflow's, the
job's and the step's literal `env:` values (one that holds an expression is
GitHub's to fill, and the case sets what it stands for), `GITHUB_OUTPUT` and
the other file commands under `tmp_path`, and NOTHING INHERITED that a runner,
a lane or a developer's shell set: every `GITHUB_*`, `RUNNER_*`, `LANES_*`
and `TMUX*` variable is removed first, and `gh` and `curl` are fakes that
write down that they were asked and refuse, unless a case puts a forge of its
own ahead of them. A heredoc is cut out as the model's `heredoc()` cuts one,
and run with this Python under `-I`: the stamp writer with the two copies as
its arguments, and the wheel check with the wheel as its one argument. Both
read the release's values from `VERSION`, `TAG`, `COMMIT`, `DIGEST` and
`REPOSITORY` (contracts/stamp.md), and the wheel check reads the run's own
commit and repository from `GITHUB_SHA` and `GITHUB_REPOSITORY` as well,
which carry the same values (the model's reads `GITHUB_SHA`).

WITHOUT THE SUBMODULE every test that reads YAML or the standard SKIPS, as the
command tests do (`NEEDS_UPSTREAM`), and a composed run fails instead. Nothing
here reads `specs/`, which goes to the spec leg at the cutover.
"""

from __future__ import annotations

import base64
import difflib
import functools
import hashlib
import http.server
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pytest

import package_layout as layout
from conftest import (GUIDANCE_DOCUMENTS, NEEDS_UPSTREAM, REPO, SPEC_TREES,
                      UPSTREAM, WINDOWS_SKIP)
from test_openrepotools_command import command_env

WORKFLOWS = REPO / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "release.yml"
TESTS_WORKFLOW = WORKFLOWS / "tests.yml"
BUILD_LOCK = REPO / ".github" / "release-build-requirements.txt"
PIPX_LOCK = REPO / ".github" / "release-pipx-requirements.txt"
PYPROJECT = REPO / "pyproject.toml"
PIN = REPO / "contracts" / "openreposhape-pin.yaml"
STAMP = layout.STAMP_SOURCE

#: THE MODEL: openRepoShape v1.1.0's own workflow, in the pinned submodule
#: (`190133d`). Its artifact actions' pins are this workflow's.
MODEL = UPSTREAM / ".github" / "workflows" / "release.yml"
STANDARD_SCRIPTS = UPSTREAM / "scripts"

NEEDS_BASH = pytest.mark.skipif(shutil.which("bash") is None,
                                reason="the workflow's steps are bash")

#: A step that runs longer than this is waiting on something it must not.
STEP_TIMEOUT = 120

# --- what contracts/workflows.md fixes -----------------------------------------

JOBS = ("build", "testpypi", "install", "pypi")
UPLOADS = {"testpypi": "testpypi", "pypi": "pypi"}

#: Each job's permissions, EXACTLY (contracts/workflows.md; data-model.md's
#: "A release run").
PERMISSIONS = {
    "build": {"contents": "read", "actions": "read"},
    "testpypi": {"id-token": "write", "actions": "read", "contents": "read"},
    "install": {"contents": "read"},
    "pypi": {"id-token": "write", "actions": "read", "contents": "read"},
}

#: The release gate's four job ids (FR-029, FR-046): `tests.yml` keeps them as
#: job ids with no `name:`, so a job's name in a run IS its id.
GATE = ("guard-launch-mode", "tests", "tests-no-submodule", "package")

#: The two repositories the guard knows, spelled as GitHub spells them in
#: `$GITHUB_REPOSITORY` (FR-048).
CODE_LEG = "opensoft/openRepoTools-code"
THIS_REPOSITORY = "opensoft/openRepoTools"

PUBLISH = "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33"
PUBLISH_TAG = "# v1.14.2"
TESTPYPI_LEGACY = "https://test.pypi.org/legacy/"
PIP_INDEX_URL = "https://pypi.org/simple/"

#: The digest's definition, one literal for the installer's `--version`
#: label, the pin's `digest_definition` and the standard's
#: `TREE_DIGEST_DEFINITION` (FR-029, design.md Decision 10).
DIGEST_LABEL = "sorted-ls-tree-r-v1"

#: The install check's condition, the model's own (`release.yml:855-858` at
#: v1.1.0): on a tag after TestPyPI succeeded, on a branch after the build
#: alone.
INSTALL_IF = ("${{ !cancelled() && needs.build.result == 'success' && "
              "(needs.testpypi.result == 'success' || "
              "(needs.testpypi.result == 'skipped' && "
              "!startsWith(github.ref, 'refs/tags/'))) }}")

#: The two ubuntu legs are pinned to 24.04, and macOS is not: `ubuntu-latest`
#: became Ubuntu 26.04 on 2026-10-21, where setup-python has no Python 3.9.
INSTALL_LEGS = [("ubuntu-24.04", "3.x"), ("macos-latest", "3.x"),
                ("ubuntu-24.04", "3.9")]

#: THE BUILD'S STEPS ADAPTED FROM THE MODEL, BY THE MODEL'S OWN NAMES, each
#: a prefix the step's `name:` begins with (contracts/workflows.md's build
#: steps 2 to 13; the model's are at `release.yml:206-665` at v1.1.0). Step 1,
#: the version and the repository guard, is found by the outputs it records.
REF_STEP = "the dispatched ref is the annotated tag v<version> at this commit"
ON_BRANCH_STEP = "the commit is on main or on the version's release branch"
CLEAN_STEP = "the checkout is this commit, and clean"
ENVIRONMENTS_STEP = "both environments ask a reviewer"
GATE_STEP = "the commit carries"
DIGEST_STEP = "the commit's tree digest is the forge's"
TOOLS_STEP = "install the release tools from their hash lock"
EXTRACT_STEP = "extract the commit twice"
STAMP_STEP = "write the stamp into both extractions"
BUILD_STEP = "build the wheel from each extraction"
WHEEL_CHECK_STEP = "the wheel holds the commit's own files"
RECORD_STEP = "record the wheel"
BUILD_STEPS = (REF_STEP, ON_BRANCH_STEP, CLEAN_STEP, ENVIRONMENTS_STEP,
               GATE_STEP, DIGEST_STEP, TOOLS_STEP, EXTRACT_STEP, STAMP_STEP,
               BUILD_STEP, WHEEL_CHECK_STEP, RECORD_STEP)

#: `owner/repository[/path]@<40 hex>`: an action pinned by a full commit, and
#: a `uses:` line as it is written, with its release tag as a comment (the
#: model's `COMMIT_PIN` and `USES_LINE`, `tests/test_release_workflow.py:62-66`
#: at v1.1.0).
COMMIT_PIN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}")
USES_LINE = re.compile(r"^\s*(?:- )?uses:\s*(\S+)(.*)$")

#: `${{ steps.<id>.outputs.<name> }}`, the one form a job output takes here.
STEP_OUTPUT = re.compile(r"\$\{\{\s*steps\.([A-Za-z_][A-Za-z0-9_-]*)"
                         r"\.outputs\.([A-Za-z_][A-Za-z0-9_-]*)\s*\}\}")

#: `--version` from a stamped package (contracts/cli-output.md), two spaces
#: meaning two.
STAMPED_VERSION = ("openRepoTools {VERSION} ({REPOSITORY} @ {COMMIT})\n"
                   "  version   {VERSION}\n"
                   "  tag       {TAG}\n"
                   "  commit    {COMMIT}\n"
                   "  digest    {DIGEST} (" + DIGEST_LABEL + ")\n")

#: hatchling 1.27.0's version pattern, `hatchling/version/core.py:6`, as
#: `tests/test_package_stamp.py` copies it with its citation.
HATCH_PATTERN = r'(?i)^(__version__|VERSION) *= *([\'"])v?(?P<version>.+?)\2'

FILE_COMMANDS = ("GITHUB_OUTPUT", "GITHUB_ENV", "GITHUB_STEP_SUMMARY",
                 "GITHUB_PATH")

#: WHAT A STEP RUN INHERITS FROM THIS PROCESS: nothing a runner, a lane
#: session, a forge login or a developer's shell set that a step could read.
FOREIGN_PREFIXES = ("LANES_", "TMUX", "GITHUB_", "RUNNER_", "ACTIONS_", "GH_",
                    "PIP_", "PIPX_", "OPENREPOTOOLS_", "CLAUDE_", "FORGE_")
FOREIGN_NAMES = frozenset({
    "VERSION", "TAG", "COMMIT", "DIGEST", "REPOSITORY", "WHEEL",
    "WHEEL_SHA256", "CI", "PYTHONPATH", "PYTHONHOME", "PYTHONUTF8",
    "PYTHONSTARTUP", "SOURCE_DATE_EPOCH", "ENVIRONMENT", "INDEX", "JSON_BASE",
    "TREE_A", "TREE_B"})


# --- reading the workflow ------------------------------------------------------

@functools.lru_cache(maxsize=1)
def standard():
    """The PINNED `scripts/repo_shape.py`, imported from the submodule and
    never copied (G2, R9). Every caller is a test marked `NEEDS_UPSTREAM`."""
    scripts = str(STANDARD_SCRIPTS)
    sys.path.insert(0, scripts)
    try:
        import repo_shape
    finally:
        sys.path.remove(scripts)
    return repo_shape


_READ: Dict[tuple, dict] = {}


def release() -> dict:
    """`release.yml` as the pinned `load_yaml` reads it, or THIS TEST'S
    FAILURE, naming the file and the tasks that write it. Called in the test's
    own body, so an absent file is a failure of the test that needed it, and
    never a setup error or a collection error."""
    if not (STANDARD_SCRIPTS / "repo_shape.py").is_file():
        pytest.skip("the pinned openRepoShape is not checked out; run "
                    "`git submodule update --init upstream/openRepoShape`")
    rel = os.path.relpath(WORKFLOW, REPO)
    if not WORKFLOW.is_file():
        pytest.fail(f"{rel} does not exist: contracts/workflows.md's release "
                    "workflow is written by tasks T019 (its shape and the "
                    "build job), T020 (testpypi, install and pypi) and T021 "
                    "(the RELEASING header), and this test holds what it must "
                    "say", pytrace=False)
    st = WORKFLOW.stat()
    key = (str(WORKFLOW), st.st_mtime_ns, st.st_size)
    if key not in _READ:
        try:
            _READ[key] = standard().load_yaml(WORKFLOW)
        except Exception as error:   # repo_shape.Refusal, and only it
            pytest.fail(f"the pinned load_yaml refuses {rel}: {error}",
                        pytrace=False)
    workflow = _READ[key]
    if not isinstance(workflow, dict) or not isinstance(
            workflow.get("jobs"), dict):
        pytest.fail(f"{rel} is not a workflow with `jobs:`", pytrace=False)
    return workflow


def job(workflow: dict, name: str) -> dict:
    jobs = workflow["jobs"]
    if not isinstance(jobs.get(name), dict):
        pytest.fail(f"release.yml has no `{name}` job; it has "
                    f"{sorted(jobs)}", pytrace=False)
    return jobs[name]


def steps_of(workflow: dict, name: str) -> list:
    found = job(workflow, name).get("steps")
    if not isinstance(found, list) or not found:
        pytest.fail(f"release.yml's `{name}` job has no steps", pytrace=False)
    return found


def label(step: dict) -> str:
    return (step.get("name") or str(step.get("uses", "")).split("@")[0]
            or "<an unnamed run step>")


def named(workflow: dict, name: str, prefix: str) -> dict:
    """The one step of job `name` whose name begins with `prefix`."""
    steps = steps_of(workflow, name)
    found = [s for s in steps if str(s.get("name", "")).startswith(prefix)]
    if len(found) != 1:
        pytest.fail(f"the `{name}` job has {len(found)} steps whose name "
                    f"begins {prefix!r}, not one (the model's own name). Its "
                    f"steps: {[label(s) for s in steps]}", pytrace=False)
    return found[0]


def where(workflow: dict, name: str, step: dict) -> int:
    return next(i for i, s in enumerate(steps_of(workflow, name)) if s is step)


def run_text(step: dict) -> str:
    value = step.get("run", "")
    return value if isinstance(value, str) else ""


def build_outputs(workflow: dict) -> dict:
    outputs = job(workflow, "build").get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        pytest.fail("the build job records no `outputs:`", pytrace=False)
    return outputs


def guard_step(workflow: dict) -> dict:
    """STEP 1, BY WHAT IT RECORDS: the build step whose `to-testpypi` and
    `to-pypi` the build job carries as outputs of its own (contracts/
    workflows.md, steps 1 and 14)."""
    outputs = build_outputs(workflow)
    ids = set()
    for name in ("to-testpypi", "to-pypi"):
        value = str(outputs.get(name, "")).strip()
        found = STEP_OUTPUT.fullmatch(value)
        if not found or found.group(2) != name:
            pytest.fail(f"the build job's output `{name}` is {value!r}, not "
                        f"`${{{{ steps.<the guard's id>.outputs.{name} }}}}`: "
                        "step 14 records step 1's to-testpypi and to-pypi",
                        pytrace=False)
        ids.add(found.group(1))
    if len(ids) != 1:
        pytest.fail(f"to-testpypi and to-pypi come from {sorted(ids)}, not "
                    "from one guard step", pytrace=False)
    (step_id,) = ids
    found = [s for s in steps_of(workflow, "build") if s.get("id") == step_id]
    if len(found) != 1 or not run_text(found[0]):
        pytest.fail(f"the build job has {len(found)} `run:` steps with id "
                    f"{step_id!r}, not one: the guard is a bash `run:` block "
                    "the suite runs", pytrace=False)
    return found[0]


def heredoc(script: str) -> str:
    """The Python a `run:` script hands to `python3 ... <<'PY'`: the model's
    own `heredoc()`, `tests/test_release_workflow.py:89-94` at v1.1.0."""
    lines = script.splitlines()
    [start] = [at for at, line in enumerate(lines)
               if line.rstrip().endswith("<<'PY'")]
    return "\n".join(lines[start + 1:lines.index("PY", start)]) + "\n"


def heredoc_line(script: str) -> str:
    """The command line that opens a step's heredoc."""
    [line] = [line for line in script.splitlines()
              if line.rstrip().endswith("<<'PY'")]
    return line


def commands(script: str) -> list:
    """A `run:` script's command lines as the shell reads them: each
    continuation joined to the line it continues, comment lines dropped (the
    model's `commands()`, `tests/test_release_workflow.py:97-102`)."""
    joined = re.sub(r"\s*\\\n\s*", " ", script)
    return [line.strip() for line in joined.splitlines()
            if line.strip() and not line.strip().startswith("#")]


def normal(expression) -> str:
    """An expression with its `${{ }}` taken off and its spaces collapsed."""
    text = " ".join(str(expression or "").split())
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    return text


def as_list(value) -> list:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def uses_lines(path: Path) -> Dict[str, str]:
    """Every `uses:` reference written in `path`, with the comment beside it."""
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = USES_LINE.match(line)
        if match:
            found[match.group(1)] = match.group(2).strip()
    return found


def every_step(workflow: dict):
    for name, body in workflow["jobs"].items():
        for step in (body.get("steps") or []):
            yield name, step


def transcript(done: subprocess.CompletedProcess) -> str:
    return (f"exit {done.returncode}\n--- stdout\n{done.stdout}"
            f"--- stderr\n{done.stderr}")


# --- running a step ------------------------------------------------------------

def clean_environ(home: Path) -> dict:
    """This process's environment with everything foreign taken out, and
    `home` as HOME."""
    env = {name: value for name, value in os.environ.items()
           if not name.startswith(FOREIGN_PREFIXES) and name not in FOREIGN_NAMES}
    home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(home)
    return env


def literal_env(scope) -> dict:
    """A `env:` mapping's values that hold no expression, as GitHub passes
    them: `true` and `false` as words."""
    out = {}
    for name, value in (scope or {}).items():
        if isinstance(value, bool):
            out[name] = "true" if value else "false"
        elif "${{" not in str(value):
            out[name] = str(value)
    return out


def refusing_network(directory: Path, log: Path) -> Path:
    """A `gh` and a `curl` that write down that they were asked, and fail."""
    directory.mkdir(parents=True, exist_ok=True)
    for tool in ("gh", "curl"):
        (directory / tool).write_text(
            "#!/bin/sh\n"
            f"printf '%s %s\\n' {tool} \"$*\" >> {shlex.quote(str(log))}\n"
            f"printf 'fake {tool}: nothing here may reach a network\\n' >&2\n"
            "exit 1\n", encoding="utf-8")
        (directory / tool).chmod(0o755)
    return directory


def python_tool(directory: Path, name: str, code: str) -> Path:
    """`name`, a Python program run by this interpreter, in `directory`."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(f"#!{sys.executable}\n" + code, encoding="utf-8")
    path.chmod(0o755)
    return directory


class Runner:
    """ONE JOB'S STEPS, RUN AS GITHUB RUNS THEM, under `work`.

    The steps share one set of file commands, so what one step records in
    `GITHUB_OUTPUT` the next sees, as on a runner. `values` are what GitHub
    would set for the case, and they win over every literal `env:` value.
    `forge` is a directory of fakes put ahead of the refusing `gh` and `curl`.
    """

    def __init__(self, work: Path, workflow: dict, job_name: str, values: dict,
                 forge: Optional[Path] = None) -> None:
        work.mkdir(parents=True, exist_ok=True)
        self.work = work
        self.values = dict(values)
        self.log = work / "network-was-asked.log"
        refusing = refusing_network(work / "refusing-network", self.log)
        env = clean_environ(work / "home")
        env["PATH"] = os.pathsep.join(
            [str(p) for p in (forge, refusing) if p is not None]
            + [env.get("PATH", os.defpath)])
        files = work / "runner-files"
        files.mkdir(exist_ok=True)
        for name in FILE_COMMANDS:
            path = files / name.lower()
            path.touch()
            env[name] = str(path)
        temp = work / "runner-temp"
        temp.mkdir(exist_ok=True)
        env["RUNNER_TEMP"] = str(temp)
        env.update(literal_env(workflow.get("env")))
        env.update(literal_env(workflow["jobs"].get(job_name, {}).get("env")))
        self.env = env
        self.output = Path(env["GITHUB_OUTPUT"])
        self.count = 0

    def run(self, step: dict, cwd: Optional[Path] = None
            ) -> subprocess.CompletedProcess:
        self.count += 1
        script = self.work / f"step-{self.count}.sh"
        script.write_text(run_text(step), encoding="utf-8")
        env = dict(self.env)
        env.update(literal_env(step.get("env")))
        env.update(self.values)
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", str(script)],
            capture_output=True, text=True, check=False,
            stdin=subprocess.DEVNULL, env=env,
            cwd=str(cwd or self.work), timeout=STEP_TIMEOUT)

    def recorded(self) -> List[Tuple[str, str]]:
        """`GITHUB_OUTPUT` as GitHub reads it: `name=value` lines, and
        `name<<DELIMITER` blocks."""
        lines = self.output.read_text(encoding="utf-8").split("\n")
        out: List[Tuple[str, str]] = []
        at = 0
        while at < len(lines):
            line = lines[at]
            at += 1
            if not line:
                continue
            eq, block = line.find("="), line.find("<<")
            if block != -1 and (eq == -1 or block < eq):
                name, delimiter, value = line[:block], line[block + 2:], []
                while at < len(lines) and lines[at] != delimiter:
                    value.append(lines[at])
                    at += 1
                at += 1
                out.append((name, "\n".join(value)))
            else:
                out.append((line[:eq], line[eq + 1:]) if eq != -1
                           else (line, ""))
        return out

    def decision(self) -> Dict[str, List[str]]:
        found: Dict[str, List[str]] = {}
        for name, value in self.recorded():
            if name in ("to-testpypi", "to-pypi"):
                found.setdefault(name, []).append(value)
        return found

    def asked(self) -> str:
        return (self.log.read_text(encoding="utf-8") if self.log.exists()
                else "")


def run_heredoc(step: dict, work: Path, arguments: list, values: dict,
                cwd: Path) -> subprocess.CompletedProcess:
    """A step's heredoc, cut out as the model cuts one and run by this Python,
    `-I`, with `arguments` and `values`."""
    code = heredoc(run_text(step))
    if "tomllib" in code and sys.version_info < (3, 11):
        pytest.skip("the step's script reads TOML with tomllib, which is "
                    "Python 3.11's and up, as the build job's Python is")
    work.mkdir(parents=True, exist_ok=True)
    script = work / "heredoc.py"
    script.write_text(code, encoding="utf-8")
    env = clean_environ(work / "home")
    env["PYTHONUTF8"] = "1"
    env.update(values)
    return subprocess.run([sys.executable, "-I", str(script),
                           *(str(a) for a in arguments)],
                          capture_output=True, text=True, check=False,
                          stdin=subprocess.DEVNULL, env=env, cwd=str(cwd),
                          timeout=STEP_TIMEOUT)


def ref_name(ref: str) -> str:
    for prefix in ("refs/heads/", "refs/tags/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref.split("/", 2)[-1] if ref.startswith("refs/") else ref


def release_values(release: dict) -> dict:
    """The five stamp values, under contracts/stamp.md's names and under the
    runner's, which carry the same ones."""
    values = dict(release)
    values["GITHUB_SHA"] = release["COMMIT"]
    values["GITHUB_REPOSITORY"] = release["REPOSITORY"]
    return values


def version_env(home: Path) -> dict:
    env = command_env(home)
    for name in [n for n in env if n.startswith(
            ("LANES_", "TMUX", "OPENREPOTOOLS_PACKAGE_", "PIPX_", "GITHUB_",
             "RUNNER_"))]:
        del env[name]
    return env


def run_version(payload: Path, home: Path) -> subprocess.CompletedProcess:
    """`bash <payload>/openRepoTools --version`, as the entry module runs it."""
    home.mkdir(parents=True, exist_ok=True)
    return subprocess.run(["bash", str(payload / "openRepoTools"), "--version"],
                          capture_output=True, text=True, check=False,
                          stdin=subprocess.DEVNULL, env=version_env(home),
                          cwd=str(home), timeout=STEP_TIMEOUT)


#: A `gh` THAT ANSWERS THE FORGE'S REST READS from `FORGE_DATA`, a JSON map of
#: path (its query left off) to the object the API returns, writes down every
#: call in `FORGE_LOG`, and answers any other path as a 404. It evaluates the
#: three `--jq` forms the release's steps use, and refuses any other, so a step
#: that starts asking something new fails here rather than reading nothing.
API_FORGE = r'''
import json, os, re, sys
args = sys.argv[1:]
with open(os.environ["FORGE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
paths = [a for a in args[1:] if a.lstrip("/").startswith("repos/")]
if args[:1] != ["api"] or len(paths) != 1:
    sys.stderr.write("gh: Not Found (HTTP 404)\n")
    sys.exit(1)
path = paths[0].lstrip("/").partition("?")[0]
with open(os.environ["FORGE_DATA"], encoding="utf-8") as handle:
    answers = json.load(handle)
if path not in answers:
    sys.stderr.write("gh: Not Found (HTTP 404)\n")
    sys.exit(1)
answer = answers[path]
jq = None
for flag in ("--jq", "-q"):
    if flag in args:
        jq = args[args.index(flag) + 1].strip()
if jq is None:
    print(json.dumps(answer))
    sys.exit(0)
kind = re.fullmatch(r'select\(\.object\.type == "([a-z]+)"\) \| \.object\.sha', jq)
if kind:
    if answer.get("object", {}).get("type") == kind.group(1):
        print(answer["object"]["sha"])
elif jq == "[.tag, .object.type, .object.sha] | @tsv":
    print("\t".join([answer["tag"], answer["object"]["type"], answer["object"]["sha"]]))
else:
    sys.stderr.write(f"fake forge: it answers no --jq {jq!r}\n")
    sys.exit(1)
'''


def api_forge(tmp_path: Path, answers: dict) -> Tuple[Path, dict]:
    """`API_FORGE` in `tmp_path/forge`, answering `answers`, and the values
    a run gives it."""
    data = tmp_path / "forge.json"
    data.write_text(json.dumps(answers), encoding="utf-8")
    forge = python_tool(tmp_path / "forge", "gh", API_FORGE)
    return forge, {"FORGE_DATA": str(data), "FORGE_LOG": str(tmp_path / "forge.log")}


def forge_asked(tmp_path: Path) -> List[list]:
    log = tmp_path / "forge.log"
    return ([json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            if log.exists() else [])


def annotated_tag(repository: str, tag: str, object_: str, commit: str,
                  **lie) -> dict:
    """The forge's two answers for the annotated tag `tag`, its ref and its
    tag object, `object_` naming `commit`; `lie` changes the tag object's
    `name`, the `type` it names or the commit it `names`, or makes it
    `lightweight`."""
    if lie.get("lightweight"):
        return {f"repos/{repository}/git/ref/tags/{tag}": {
            "ref": f"refs/tags/{tag}", "object": {"type": "commit", "sha": commit}}}
    return {f"repos/{repository}/git/ref/tags/{tag}": {
                "ref": f"refs/tags/{tag}", "object": {"type": "tag", "sha": object_}},
            f"repos/{repository}/git/tags/{object_}": {
                "tag": lie.get("name", tag), "sha": object_,
                "object": {"type": lie.get("type", "commit"),
                           "sha": lie.get("names", commit)}}}


#: The identity and the clock of the git fixtures' commits and tags.
FIXTURE_GIT = {"GIT_AUTHOR_NAME": "release fixture",
               "GIT_AUTHOR_EMAIL": "fixture@openrepotools.invalid",
               "GIT_COMMITTER_NAME": "release fixture",
               "GIT_COMMITTER_EMAIL": "fixture@openrepotools.invalid",
               "GIT_AUTHOR_DATE": "2026-10-19T00:00:00Z",
               "GIT_COMMITTER_DATE": "2026-10-19T00:00:00Z",
               "GIT_CONFIG_NOSYSTEM": "1"}


def fixture_git(home: Path, cwd: Path, *args: str, data: Optional[str] = None) -> str:
    env = clean_environ(home)
    env.update(FIXTURE_GIT)
    done = subprocess.run(["git", *args], cwd=str(cwd), env=env, input=data,
                          capture_output=True, text=True, check=False,
                          timeout=STEP_TIMEOUT)
    assert done.returncode == 0, transcript(done)
    return done.stdout.strip()


def tagged_origin(where: Path, tags: Tuple[str, ...]) -> Tuple[Path, str, Dict[str, str]]:
    """A bare repository on this filesystem holding one commit and an
    annotated tag at it for each of `tags`, and an empty repository whose
    `origin` is it, by a `file://` URL: what the ref step fetches from.
    Returns that repository, the commit, and each tag's object."""
    home, origin, checkout = where / "home", where / "origin.git", where / "checkout"
    for directory in (origin, checkout):
        directory.mkdir(parents=True)
    fixture_git(home, origin, "init", "--quiet", "--bare")
    tree = fixture_git(home, origin, "mktree", data="")
    commit = fixture_git(home, origin, "commit-tree", tree, "-m", "the release commit")
    objects = {}
    for tag in tags:
        fixture_git(home, origin, "tag", "-a", tag, "-m", f"openRepoTools {tag}", commit)
        objects[tag] = fixture_git(home, origin, "rev-parse", f"refs/tags/{tag}")
    fixture_git(home, checkout, "init", "--quiet")
    fixture_git(home, checkout, "remote", "add", "origin", origin.as_uri())
    return checkout, commit, objects


def a_checkout(where: Path) -> Tuple[Path, str]:
    """A repository on this filesystem with one commit, a tracked file and a
    `.gitignore` that ignores `*.log`: a checkout as a build step finds it.
    Returns it and its commit."""
    home, checkout = where / "home", where / "checkout"
    checkout.mkdir(parents=True)
    fixture_git(home, checkout, "init", "--quiet")
    (checkout / "tracked.txt").write_text("the commit's own\n", encoding="utf-8")
    (checkout / ".gitignore").write_text("*.log\n", encoding="utf-8")
    fixture_git(home, checkout, "add", "tracked.txt", ".gitignore")
    fixture_git(home, checkout, "commit", "--quiet", "-m", "the release commit")
    return checkout, fixture_git(home, checkout, "rev-parse", "HEAD")


# --- HEAD, as git holds it -------------------------------------------------------

@functools.lru_cache(maxsize=1)
def head() -> Tuple[str, Dict[str, Tuple[str, str, str]]]:
    """HEAD's commit, and every path in its tree as `(mode, type, object)`."""
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO),
                         capture_output=True, text=True,
                         check=True).stdout.strip()
    raw = subprocess.run(["git", "ls-tree", "-r", "-z", sha], cwd=str(REPO),
                         capture_output=True, check=True).stdout
    tree = {}
    for record in raw.split(b"\0"):
        if record:
            meta, _, path = record.partition(b"\t")
            mode, kind, oid = meta.decode("ascii").split(" ")
            tree[path.decode("utf-8")] = (mode, kind, oid)
    return sha, tree


@functools.lru_cache(maxsize=None)
def blob(oid: str) -> bytes:
    return subprocess.run(["git", "cat-file", "blob", oid], cwd=str(REPO),
                          capture_output=True, check=True).stdout


def head_blob(path: str) -> bytes:
    mode, kind, oid = head()[1][path]
    assert kind == "blob", f"HEAD's {path} is a {kind}, not a file"
    return blob(oid)


def stamped(text: str, release: dict) -> str:
    """`text`, the committed stamp, with each of its five assignment lines
    replaced by the release's, as the writer replaces them."""
    lines = text.split("\n")
    for name in layout.STAMP_FIELDS:
        committed = f'{name} = "{layout.UNSTAMPED[name]}"'
        at = [i for i, line in enumerate(lines) if line == committed]
        assert len(at) == 1, f"the committed stamp holds {committed!r} {len(at)} times"
        lines[at[0]] = f'{name} = "{release[name]}"'
    return "\n".join(lines)


# --- trigger -------------------------------------------------------------------

@NEEDS_UPSTREAM
def test_release_trigger_a_dispatch_with_a_version_is_the_only_trigger():
    """NOTHING RUNS ON A PUSH, A TAG OR A PULL REQUEST (FR-028): an upload is
    an act Brett Heap approves, so a dispatch with a required `version`
    string is the workflow's one trigger."""
    workflow = release()
    on = workflow.get("on")
    assert isinstance(on, dict) and list(on) == ["workflow_dispatch"], (
        f"release.yml's triggers are {on!r}, not a dispatch alone")
    inputs = (on["workflow_dispatch"] or {}).get("inputs") or {}
    assert list(inputs) == ["version"], f"the dispatch's inputs are {list(inputs)}"
    version = inputs["version"]
    assert version.get("required") is True, version
    assert version.get("type") == "string", version
    assert version.get("description"), "the version input has no description"


@NEEDS_UPSTREAM
def test_release_trigger_grants_nothing_at_the_top_and_runs_one_release_at_a_time():
    """contracts/workflows.md's shape: `permissions: {}`, so each job grants
    its own; the `release` concurrency group, never cancelling a release
    halfway; `bash` by default; and `VERSION` and `PYTHONUTF8` in `env`."""
    workflow = release()
    assert workflow.get("permissions") == {}, (
        f"release.yml grants {workflow.get('permissions')!r} at the top")
    assert workflow.get("concurrency") == {"group": "release",
                                           "cancel-in-progress": False}, (
        workflow.get("concurrency"))
    assert workflow.get("defaults") == {"run": {"shell": "bash"}}, (
        workflow.get("defaults"))
    assert workflow.get("env") == {"VERSION": "${{ inputs.version }}",
                                   "PYTHONUTF8": "1"}, workflow.get("env")


@NEEDS_UPSTREAM
def test_release_trigger_the_input_reaches_every_script_through_the_environment():
    """NO EXPRESSION IS PASTED INTO A SCRIPT (contracts/workflows.md's shape):
    the input is `$VERSION`, which no script can be made to run, and no
    `run:` block holds a `${{`."""
    workflow = release()
    pasted = [f"{name}: {label(step)}" for name, step in every_step(workflow)
              if "${{" in run_text(step)]
    assert not pasted, f"steps with an expression in their script: {pasted}"


# --- the hash locks ------------------------------------------------------------

def lock_entries(path: Path) -> Dict[str, List[str]]:
    """`name==version ; marker` -> its sha256 digests, from a hash lock;
    continuation lines joined, comment lines dropped (the model's
    `lock_entries()`, `tests/test_release_workflow.py:105-115`). A requirement
    the lock writes twice is named here, not folded into one entry."""
    text = "\n".join(line for line in path.read_text(encoding="utf-8")
                     .splitlines() if not line.lstrip().startswith("#"))
    entries: Dict[str, List[str]] = {}
    for entry in re.sub(r"\\\n", " ", text).splitlines():
        if entry.strip():
            requirement = entry.split("--hash=")[0].strip()
            assert requirement not in entries, (
                f"{path.name} writes {requirement!r} twice")
            entries[requirement] = re.findall(r"--hash=sha256:(\S+)", entry)
    return entries


@pytest.mark.parametrize("lock", [BUILD_LOCK, PIPX_LOCK], ids=["build", "pipx"])
def test_release_lock_every_entry_is_one_version_named_by_its_sha256(lock):
    """A LOCK IS ONE VERSION PER ENTRY, BY DIGEST: every requirement pinned
    `==` one version, with a marker or none, and every `--hash` a sha256 of
    64 hex digits, so `--require-hashes` installs exactly the files named."""
    entries = lock_entries(lock)
    assert entries, f"{lock.name} names nothing"
    for requirement, digests in entries.items():
        assert re.fullmatch(r"[a-z0-9-]+==[0-9][0-9A-Za-z.]*( ; .+)?",
                            requirement), requirement
        assert digests, f"{requirement} carries no sha256"
        for digest in digests:
            assert re.fullmatch(r"[0-9a-f]{64}", digest), (requirement, digest)
    algorithms = set(re.findall(r"--hash=([A-Za-z0-9]+):",
                                lock.read_text(encoding="utf-8")))
    assert algorithms == {"sha256"}, f"{lock.name} names digests by {algorithms}"


def build_system_requires() -> list:
    """`[build-system] requires`, by TOML where a parser imports, and by its
    line otherwise (Python 3.9 has no `tomllib`)."""
    text = PYPROJECT.read_text(encoding="utf-8")
    try:
        import tomllib as toml
    except ImportError:
        try:
            import tomli as toml
        except ImportError:
            toml = None
    if toml is not None:
        return toml.loads(text)["build-system"]["requires"]
    section = text.split("[build-system]", 1)[1].split("\n[", 1)[0]
    [line] = [line for line in section.splitlines()
              if line.strip().startswith("requires")]
    return re.findall(r'"([^"]+)"', line)


def test_release_lock_the_build_lock_s_hatchling_is_pyproject_s_pin():
    """`hatchling==1.27.0` TWICE, AND THE SAME (FR-030, research R11): with
    `--no-isolation`, `build` refuses a backend that does not satisfy
    `[build-system] requires`, so the lock's one hatchling entry is
    `pyproject.toml`'s pin, and the lock carries hatchling's own requirements
    and the `build` frontend beside it."""
    [backend] = build_system_requires()
    entries = lock_entries(BUILD_LOCK)
    hatchling = [r.split(" ;")[0] for r in entries if r.startswith("hatchling==")]
    assert hatchling == [backend], (
        f"the build lock pins {hatchling}, and pyproject.toml requires {backend}")
    names = {r.split("==")[0] for r in entries}
    for name in ("build", "packaging", "pathspec", "pluggy", "trove-classifiers",
                 "tomli"):
        assert name in names, f"the build lock does not carry {name}"


def marker_holds(marker: str, python: Tuple[int, ...]) -> bool:
    """A lock marker made of `python_full_version` comparisons joined by
    `and`, evaluated for `python`. Any other marker is not one this test
    reads, and fails it."""
    operators = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
                 ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
                 "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
    verdict = True
    for clause in marker.split(" and "):
        found = re.fullmatch(r"\s*python_full_version (<=|>=|==|!=|<|>) "
                             r"'([0-9.]+)'\s*", clause)
        assert found, f"a pipx entry's marker holds {clause!r}"
        bound = tuple(int(part) for part in found.group(2).split("."))
        bound = bound + (0,) * (3 - len(bound))
        verdict = verdict and operators[found.group(1)](python, bound)
    return verdict


def test_release_lock_pipx_is_1_11_1_below_python_3_10_and_1_17_8_from_3_10():
    """THE INSTALL CHECK'S pipx (research R11): 1.11.1, the newest that
    installs on 3.9, below 3.10, and 1.17.8 from 3.10. Each Python a leg can
    run is given exactly one pipx entry, read from the markers as pip reads
    them."""
    pipx = {}
    for requirement in lock_entries(PIPX_LOCK):
        name_version, _, marker = requirement.partition(" ; ")
        if name_version.startswith("pipx=="):
            pipx[name_version.split("==")[1]] = marker
    assert set(pipx) == {"1.11.1", "1.17.8"}, f"the pipx lock pins pipx {sorted(pipx)}"
    for python in ((3, 9, 0), (3, 9, 25), (3, 10, 0), (3, 10, 2), (3, 11, 9),
                   (3, 12, 3), (3, 13, 1), (3, 14, 0)):
        given = [v for v, marker in pipx.items() if marker_holds(marker, python)]
        wanted = ["1.11.1"] if python < (3, 10) else ["1.17.8"]
        assert given == wanted, (
            f"on Python {'.'.join(map(str, python))} the lock gives pipx "
            f"{given}, not {wanted}")


def test_release_lock_the_fixtures_mirror_the_pipx_the_lock_installs():
    """THE LOCK'S pipx RELEASES ARE THE FIXTURES' (the lock's own header):
    `tests/package_layout.py` lays venvs out as each pipx the install check
    runs, so a resolution that moves pipx must move the fixtures too."""
    locked = {r.split(" ;")[0].split("==")[1] for r in lock_entries(PIPX_LOCK)
              if r.startswith("pipx==")}
    assert locked <= set(layout.PIPX_RELEASES), (
        f"the lock installs pipx {sorted(locked)}, and the fixtures mirror "
        f"{sorted(layout.PIPX_RELEASES)}")


# --- the build job: what it is --------------------------------------------------

@NEEDS_UPSTREAM
def test_release_build_checks_out_the_commit_with_its_submodule_its_history_and_no_credentials():
    """THE BUILD'S CHECKOUT (contracts/workflows.md): `submodules: true`,
    because the digest code exists here only in the submodule; full history,
    for the main and release-branch check; and `persist-credentials: false`,
    so no code the build runs can read the token from git's config."""
    workflow = release()
    steps = steps_of(workflow, "build")
    checkouts = [s for s in steps
                 if str(s.get("uses", "")).startswith("actions/checkout@")]
    assert len(checkouts) == 1 and steps[0] is checkouts[0], (
        f"the build's first step is not its one checkout: {[label(s) for s in steps]}")
    options = checkouts[0].get("with") or {}
    assert options.get("submodules") is True, options
    assert str(options.get("fetch-depth")) == "0", options
    assert options.get("persist-credentials") is False, options


@NEEDS_UPSTREAM
def test_release_build_every_action_is_pinned_by_a_full_commit_with_its_release_tag():
    """EVERY `uses:` IS A FULL COMMIT, its release tag beside it as a comment,
    and each is one contracts/workflows.md names: checkout and setup-python at
    `tests.yml`'s own commits and comments, the artifact actions at the
    model's, and the publish action at v1.14.2's. The parsed references and
    the written lines are the same list, so no `uses:` hides from either."""
    workflow = release()
    parsed = [str(step["uses"]) for _, step in every_step(workflow)
              if "uses" in step]
    assert parsed, "release.yml uses no action at all"
    written = uses_lines(WORKFLOW)
    lines = [m for m in (USES_LINE.match(line) for line in
                         WORKFLOW.read_text(encoding="utf-8").splitlines()) if m]
    assert sorted(m.group(1) for m in lines) == sorted(parsed)
    tests_pins, model_pins = uses_lines(TESTS_WORKFLOW), uses_lines(MODEL)
    problems = []
    for ref in sorted(set(parsed)):
        action, comment = ref.split("@")[0], written.get(ref, "")
        if not COMMIT_PIN.fullmatch(ref):
            problems.append(f"{ref}: not pinned by 40 hex digits")
        if not re.fullmatch(r"# v\S+", comment):
            problems.append(f"{ref}: its release tag is not written beside it")
        if action in ("actions/checkout", "actions/setup-python"):
            known = tests_pins
        elif action in ("actions/upload-artifact", "actions/download-artifact"):
            known = model_pins
        elif action == "pypa/gh-action-pypi-publish":
            known = {PUBLISH: PUBLISH_TAG}
        else:
            problems.append(f"{ref}: an action contracts/workflows.md does not name")
            continue
        if known.get(ref) != comment:
            problems.append(f"{ref} {comment}: not the pin "
                            f"{[k + ' ' + v for k, v in known.items() if k.startswith(action + '@')]}")
    assert not problems, "release.yml's actions:\n  " + "\n  ".join(problems)


@NEEDS_UPSTREAM
def test_release_build_its_steps_are_the_model_s_in_the_model_s_order():
    """THE MODEL'S STEPS, IN ITS ORDER (contracts/workflows.md, steps 1 to
    14): the guard first; the ref and the branch-membership checks together;
    the clean checkout before anything from it runs; the environments and the
    gate; the digest; the tools; two extractions, stamped and built; the
    wheel check right after the build and right before the record; and the
    wheel kept as an artifact after it."""
    workflow = release()
    found = [guard_step(workflow)] + [named(workflow, "build", prefix)
                                      for prefix in BUILD_STEPS]
    at = [where(workflow, "build", step) for step in found]
    names = [label(step) for step in found]
    assert at == sorted(at) and len(set(at)) == len(at), (
        "the build's steps are not in contracts/workflows.md's order:\n  "
        + "\n  ".join(f"{i}: {n}" for i, n in sorted(zip(at, names))))
    position = dict(zip((None,) + BUILD_STEPS, at))
    assert position[ON_BRANCH_STEP] == position[REF_STEP] + 1
    assert position[WHEEL_CHECK_STEP] == position[BUILD_STEP] + 1
    assert position[RECORD_STEP] == position[WHEEL_CHECK_STEP] + 1
    later = steps_of(workflow, "build")[position[RECORD_STEP] + 1:]
    assert [s for s in later
            if str(s.get("uses", "")).startswith("actions/upload-artifact@")], (
        "the wheel is not kept as an artifact after it is recorded")


@NEEDS_UPSTREAM
def test_release_build_no_step_is_conditional_and_none_carries_on_past_a_failure():
    """EACH STEP IS A REFUSAL ON FAILURE (contracts/workflows.md): the build
    runs on every dispatch, so neither it nor any of its steps carries an
    `if:` that could skip a check, and nothing continues past a failed step."""
    workflow = release()
    build = job(workflow, "build")
    assert "if" not in build, f"the build job runs only if {build['if']!r}"
    assert "continue-on-error" not in build
    for step in steps_of(workflow, "build"):
        assert "if" not in step, f"{label(step)} runs only if {step['if']!r}"
        assert "continue-on-error" not in step, label(step)


PIP_INSTALL = re.compile(r"\bpip3? install\b")


def pip_installs(workflow: dict, name: str) -> List[str]:
    return [command for step in steps_of(workflow, name)
            for command in commands(run_text(step)) if PIP_INSTALL.search(command)]


def hashed_from(command: str, lock: Path) -> List[str]:
    """What is wrong with `command` as an install from `lock` by hash."""
    problems = []
    if "--require-hashes" not in command:
        problems.append("no --require-hashes")
    if not re.search(r"--only-binary(?:\s+|=):all:", command):
        problems.append("not wheels only (--only-binary :all:)")
    named_locks = [m.group(2) for m in re.finditer(
        r"(?:^|\s)(?:-r|--requirement)(?:\s+|=)(\"?)([^\s\"]+)\1", command)]
    want = lock.relative_to(REPO).as_posix()
    if len(named_locks) != 1 or not named_locks[0].endswith(want):
        problems.append(f"reads {named_locks}, not {want} alone")
    return problems


@NEEDS_UPSTREAM
def test_release_build_installs_its_tools_from_the_build_lock_by_hash():
    """EVERY `pip install` THE BUILD RUNS (FR-030, FR-035), read as the shell
    reads it, is `--require-hashes`, wheels only, from
    `.github/release-build-requirements.txt` and nothing else."""
    workflow = release()
    installs = pip_installs(workflow, "build")
    assert installs, "the build installs nothing from its lock"
    problems = {command: hashed_from(command, BUILD_LOCK) for command in installs}
    assert not any(problems.values()), problems


@NEEDS_UPSTREAM
def test_release_build_builds_twice_from_two_git_archive_extractions_and_compares():
    """FR-030: `git archive` of the commit into two directories, a wheel only
    from each with `python -m build --wheel --no-isolation` at
    `SOURCE_DATE_EPOCH` the commit's own time, and the two compared with
    `cmp` before anything else reads them."""
    workflow = release()
    extract = run_text(named(workflow, "build", EXTRACT_STEP))
    assert "git archive" in extract and "GITHUB_SHA" in extract, extract
    build = run_text(named(workflow, "build", BUILD_STEP))
    assert "SOURCE_DATE_EPOCH" in build and "%ct" in build, build
    assert "-m build --wheel --no-isolation" in " ".join(commands(build)), build
    assert "--sdist" not in build
    assert re.search(r"(?<![\w-])cmp\s", build), "the two wheels are not compared"


@NEEDS_UPSTREAM
def test_release_build_records_the_wheel_its_sha256_the_digest_and_the_guard_s_answers():
    """STEP 14: the build's outputs are the wheel's name, its sha256, the
    digest and step 1's `to-testpypi` and `to-pypi`, each read from a step of
    the build that exists. The record step and the digest step each feed
    one."""
    workflow = release()
    outputs = build_outputs(workflow)
    ids = {s.get("id") for s in steps_of(workflow, "build") if s.get("id")}
    sources = {}
    for name, value in outputs.items():
        found = STEP_OUTPUT.fullmatch(str(value).strip())
        assert found and found.group(1) in ids, (
            f"the build's output {name} is {value!r}, no build step's output")
        sources[name] = found.group(1)
    assert {"to-testpypi", "to-pypi"} <= set(outputs) and len(outputs) >= 5, (
        f"the build records {sorted(outputs)}")
    for prefix in (RECORD_STEP, DIGEST_STEP):
        step = named(workflow, "build", prefix)
        assert step.get("id") in sources.values(), (
            f"no output of the build job comes from {label(step)!r}")


@NEEDS_UPSTREAM
def test_release_build_the_checkout_and_both_environments_are_read_before_the_build():
    """STEPS 4 AND 5: the checkout is `$GITHUB_SHA` and clean before anything
    from it runs, and each environment names a required reviewer and admits
    the one deployment rule, the tags `v*`, as the model reads them."""
    workflow = release()
    clean = run_text(named(workflow, "build", CLEAN_STEP))
    assert "GITHUB_SHA" in clean and "status --porcelain" in clean, clean
    environments = run_text(named(workflow, "build", ENVIRONMENTS_STEP))
    for word in ("testpypi", "pypi", "required_reviewers", "custom_branch_policies",
                 "deployment-branch-policies", "v*"):
        assert word in environments, f"the environments step never reads {word}"


#: STEP 4, RUN: `(what is done to the checkout, whether HEAD is the run's
#: commit, whether the step passes)`.
CLEAN_CASES = {
    "this-commit-and-clean": (None, True, True),
    "another-commit-checked-out": (None, False, False),
    "a-tracked-file-changed": (("tracked.txt", "changed\n"), True, False),
    "a-file-added": (("added.txt", "new\n"), True, False),
    "an-ignored-file-added": (("build.log", "ignored\n"), True, False),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", CLEAN_CASES)
def test_release_build_the_clean_step_refuses_a_moved_or_dirty_checkout(tmp_path, which):
    """STEP 4, RUN, in a repository on this filesystem (FR-029: "the checkout
    is that commit, and it is clean"): it passes the run's commit with
    nothing changed, and refuses another commit, a tracked file changed, a
    file added, and an ignored file added."""
    change, at_the_run_s_commit, passes = CLEAN_CASES[which]
    checkout, commit = a_checkout(tmp_path / "git")
    if change is not None:
        (checkout / change[0]).write_text(change[1], encoding="utf-8")
    values = {"GITHUB_SHA": commit if at_the_run_s_commit else "e" * 40}
    workflow = release()
    runner = Runner(tmp_path / "work", workflow, "build", values)
    done = runner.run(named(workflow, "build", CLEAN_STEP), cwd=checkout)
    assert (done.returncode == 0) == passes, transcript(done)
    if not passes:
        assert "::error::" in done.stdout, transcript(done)
        if change is not None:
            assert change[0] in done.stdout, transcript(done)


def an_environment(reviewers: Tuple[str, ...] = ("brettheap",),
                   custom: bool = True) -> dict:
    """An environment as `GET repos/<r>/environments/<name>` returns it."""
    rules = ([{"type": "required_reviewers",
               "reviewers": [{"type": "User", "reviewer": {"login": login}}
                             for login in reviewers]}] if reviewers else [])
    return {"protection_rules": rules + [{"type": "branch_policy"}],
            "deployment_branch_policy": {"protected_branches": not custom,
                                         "custom_branch_policies": custom}}


def environment_answers(repository: str, changes: dict) -> dict:
    """Both environments as Brett Heap sets them up, a required reviewer and
    the one deployment rule `('tag', 'v*')` each, with `changes` by
    environment: `reviewers`, `custom`, `rules`, or `missing`."""
    answers = {}
    for name in ("testpypi", "pypi"):
        change = changes.get(name, {})
        if change.get("missing"):
            continue
        rules = change.get("rules", [("tag", "v*")])
        answers[f"repos/{repository}/environments/{name}"] = an_environment(
            change.get("reviewers", ("brettheap",)), change.get("custom", True))
        answers[f"repos/{repository}/environments/{name}/deployment-branch-policies"] = {
            "total_count": len(rules),
            "branch_policies": [{"type": kind, "name": pattern} for kind, pattern in rules]}
    return answers


#: STEP 5, RUN: `(the changes to both environments, the environment a
#: refusal names, or None where the step passes)`.
ENVIRONMENT_CASES = {
    "both-as-set-up": ({}, None),
    "testpypi-not-created-yet": ({"testpypi": {"missing": True}}, "testpypi"),
    "pypi-names-no-reviewer": ({"pypi": {"reviewers": ()}}, "pypi"),
    "a-branch-rule-beside-the-tags": (
        {"testpypi": {"rules": [("tag", "v*"), ("branch", "main")]}}, "testpypi"),
    "a-branch-rule-alone": ({"pypi": {"rules": [("branch", "v*")]}}, "pypi"),
    "another-tag-pattern": ({"pypi": {"rules": [("tag", "v1.*")]}}, "pypi"),
    "protected-branches-not-custom-rules": ({"testpypi": {"custom": False}}, "testpypi"),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", ENVIRONMENT_CASES)
def test_release_build_the_environments_step_refuses_an_environment_without_its_rules(
        tmp_path, which):
    """STEP 5, RUN under a forge (FR-029): both environments as set up pass;
    an environment not created yet, one with no required reviewer, one
    whose deployment limit holds a branch rule or another pattern, and one
    limited to protected branches are each refused, naming it."""
    changes, refused = ENVIRONMENT_CASES[which]
    forge, values = api_forge(tmp_path, environment_answers(CODE_LEG, changes))
    values["GITHUB_REPOSITORY"] = CODE_LEG
    workflow = release()
    runner = Runner(tmp_path / "work", workflow, "build", values, forge)
    done = runner.run(named(workflow, "build", ENVIRONMENTS_STEP))
    assert (done.returncode == 0) == (refused is None), transcript(done)
    if refused is not None:
        assert [line for line in done.stdout.splitlines() if line.startswith(
            f"::error::the {refused} environment")], transcript(done)


#: The build step's two builds, faked: `$RUNNER_TEMP/tools/bin/python -m build
#: ... --outdir <dir> .` writes each name in its tree's `build-names` into
#: `<dir>`, with its tree's `build-output` bytes, and writes down where it ran
#: and with which SOURCE_DATE_EPOCH.
FAKE_BUILD = r'''
import os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_BUILD_LOG"], "a", encoding="utf-8") as log:
    log.write("\t".join([os.getcwd(), os.environ.get("SOURCE_DATE_EPOCH", "<unset>"),
                         " ".join(args)]) + "\n")
out = args[args.index("--outdir") + 1]
os.makedirs(out, exist_ok=True)
with open("build-output", "rb") as handle:
    data = handle.read()
with open("build-names", encoding="utf-8") as handle:
    names = handle.read().split()
for name in names:
    with open(os.path.join(out, name), "wb") as handle:
        handle.write(data)
'''

BUILT = "openrepotools-1.1.0-py3-none-any.whl"

#: THE BUILD STEP, RUN: `(the first build's bytes and names, the second's,
#: whether the step passes)`.
BUILD_CASES = {
    "two-builds-one-file": ((b"the wheel", [BUILT]), (b"the wheel", [BUILT]), True),
    "two-builds-two-files": ((b"the wheel", [BUILT]), (b"another wheel", [BUILT]), False),
    "a-build-of-another-name": (
        (b"the wheel", [BUILT]), (b"the wheel", ["openrepotools-1.1.0-py3-none-any.zip"]),
        False),
    "a-build-of-two-files": (
        (b"the wheel", [BUILT]), (b"the wheel", [BUILT, "openrepotools-1.1.0.tar.gz"]),
        False),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("sha256sum") is None or shutil.which("cmp") is None,
                    reason="the build step runs GNU's sha256sum and cmp")
@pytest.mark.parametrize("which", BUILD_CASES)
def test_release_build_the_build_step_compares_the_two_builds_byte_for_byte(tmp_path, which):
    """THE BUILD STEP, RUN, with the backend faked (FR-030): it builds once in
    each extraction, at the commit's own time, and passes two builds that
    are one file; two builds of different bytes (its `cmp`), a build of
    another name, and a build that leaves two files are each refused."""
    first, second, passes = BUILD_CASES[which]
    checkout, commit = a_checkout(tmp_path / "git")
    trees = [tmp_path / "a" / "openRepoTools", tmp_path / "b" / "elsewhere" / "v1.1.0-src"]
    for tree, (data, names) in zip(trees, (first, second)):
        tree.mkdir(parents=True)
        (tree / "build-output").write_bytes(data)
        (tree / "build-names").write_text("\n".join(names) + "\n", encoding="utf-8")
    log = tmp_path / "build.log"
    values = {"VERSION": "1.1.0", "GITHUB_SHA": commit, "TREE_A": str(trees[0]),
              "TREE_B": str(trees[1]), "FAKE_BUILD_LOG": str(log)}
    workflow = release()
    runner = Runner(tmp_path / "work", workflow, "build", values)
    python_tool(Path(runner.env["RUNNER_TEMP"]) / "tools" / "bin", "python", FAKE_BUILD)
    done = runner.run(named(workflow, "build", BUILD_STEP), cwd=checkout)
    assert (done.returncode == 0) == passes, transcript(done)
    when = fixture_git(tmp_path / "git" / "home", checkout, "log", "-1", "--format=%ct", commit)
    builds = [line.split("\t") for line in log.read_text(encoding="utf-8").splitlines()]
    temp = runner.env["RUNNER_TEMP"]
    assert builds[0] == [str(trees[0]), when,
                         f"-m build --wheel --no-isolation --outdir {temp}/dist-a ."], builds
    if passes or which == "two-builds-two-files":
        assert [b[:2] for b in builds] == [[str(trees[0]), when], [str(trees[1]), when]], builds
    if not passes:
        assert "::error::" in done.stdout, transcript(done)


# --- the ref step and the branch step: the rehearsal rule ------------------------

REHEARSAL_BRANCHES = ["refs/heads/l3-rehearsal-v1.1.0", "refs/heads/main",
                      "refs/heads/release/v1.1", "refs/heads/feature/a-b"]


def ref_values(ref: str, version: str) -> dict:
    return {"GITHUB_REF": ref, "GITHUB_REF_NAME": ref_name(ref),
            "GITHUB_SHA": "c" * 40, "GITHUB_REPOSITORY": CODE_LEG,
            "VERSION": version}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("ref", REHEARSAL_BRANCHES)
def test_release_build_the_ref_step_passes_a_branch_as_the_rehearsal(tmp_path, ref):
    """STEP 2 ON A BRANCH (FR-029, the model's `release.yml:206-241`): a
    branch dispatch is the rehearsal, so the tag checks stand down and the
    step passes without asking the forge for a tag that does not exist."""
    workflow = release()
    runner = Runner(tmp_path, workflow, "build", ref_values(ref, "1.1.0rc1"))
    done = runner.run(named(workflow, "build", REF_STEP))
    assert done.returncode == 0, transcript(done)
    assert runner.asked() == "", f"a rehearsal asked:\n{runner.asked()}"


OTHER_REFS = {
    "a-pull-request": ("refs/pull/7/merge", "1.1.0"),
    "a-remote-branch": ("refs/remotes/origin/main", "1.1.0"),
    "a-note": ("refs/notes/commits", "1.1.0"),
    "no-ref-at-all": ("", "1.1.0"),
    "another-version-s-tag": ("refs/tags/v1.0.0", "1.1.0"),
    "a-tag-without-its-v": ("refs/tags/1.1.0", "1.1.0"),
    "an-rc-tag-for-the-final": ("refs/tags/v1.1.0rc1", "1.1.0"),
    "the-tag-the-forge-does-not-hold": ("refs/tags/v1.1.0", "1.1.0"),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", OTHER_REFS)
def test_release_build_the_ref_step_refuses_any_other_ref(tmp_path, which):
    """STEP 2 ON EVERYTHING ELSE (FR-029): a ref that is neither a branch nor
    the tag `v$VERSION` is refused, and so is that tag where the forge holds
    no annotated tag of that name (its `gh` refuses every question here)."""
    ref, version = OTHER_REFS[which]
    workflow = release()
    runner = Runner(tmp_path, workflow, "build", ref_values(ref, version))
    done = runner.run(named(workflow, "build", REF_STEP))
    assert done.returncode != 0, transcript(done)


@NEEDS_UPSTREAM
def test_release_build_the_ref_step_reads_the_tag_from_the_forge_and_from_git():
    """ON A TAG, BOTH READINGS (contracts/workflows.md, step 2): the annotated
    tag object `v$VERSION` as the forge's API answers for it and as git's own
    `refs/tags/` holds it, each held to `$GITHUB_SHA`."""
    script = run_text(named(release(), "build", REF_STEP))
    assert re.search(r"/git/(?:refs?/tags/|tags/)", script), (
        "the ref step reads no tag from the forge")
    assert [line for line in commands(script)
            if re.search(r"\bgit\s", line) and "refs/tags/" in line], (
        "the ref step reads no tag from git")
    assert "$GITHUB_SHA" in script


#: STEP 2 ON A TAG, where the forge and `origin` both hold the annotated tag
#: `v1.1.0` at the run's commit (and `v1.1.0-again`, another tag object at
#: it): `(the dispatched ref, the version, what the forge says otherwise,
#: whether the step passes)`. So what refuses is the step's own comparison:
#: the ref against `refs/tags/v$VERSION`, the forge's tag object against the
#: tag and the commit, and git's copy against the forge's.
REF_TAG_CASES = {
    "the-version-s-own-tag": ("refs/tags/v1.1.0", "1.1.0", {}, True),
    "another-version-s-tag": ("refs/tags/v1.0.0", "1.1.0", {}, False),
    "the-tag-without-its-v": ("refs/tags/1.1.0", "1.1.0", {}, False),
    "the-rc-tag-for-the-final": ("refs/tags/v1.1.0rc1", "1.1.0", {}, False),
    "the-forge-s-tag-names-another-commit": (
        "refs/tags/v1.1.0", "1.1.0", {"names": "d" * 40}, False),
    "the-forge-s-tag-object-has-another-name": (
        "refs/tags/v1.1.0", "1.1.0", {"name": "v1.1.1"}, False),
    "the-forge-s-tag-names-a-tag": ("refs/tags/v1.1.0", "1.1.0", {"type": "tag"}, False),
    "a-lightweight-tag-on-the-forge": (
        "refs/tags/v1.1.0", "1.1.0", {"lightweight": True}, False),
    "the-forge-s-tag-object-is-not-git-s": (
        "refs/tags/v1.1.0", "1.1.0", {"object": "v1.1.0-again"}, False),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", REF_TAG_CASES)
def test_release_build_the_ref_step_holds_the_ref_the_forge_and_git_to_v_version_at_this_commit(
        tmp_path, which):
    """STEP 2 ON A TAG, RUN (FR-029), with `origin` a bare repository on
    this filesystem: on `refs/tags/v1.1.0`, the annotated tag the forge and
    git both hold at the run's commit, it passes, fetching that tag. A ref
    that is another version's tag, the tag without its `v` or an rc's tag is
    refused before the forge is asked. A forge whose tag object names
    another commit, has another name, names a tag, or is a lightweight tag,
    and a git copy that is not the forge's object, are each refused."""
    ref, version, lie, passes = REF_TAG_CASES[which]
    checkout, commit, objects = tagged_origin(tmp_path / "git", ("v1.1.0", "v1.1.0-again"))
    lie = dict(lie)
    object_ = objects[lie.pop("object", "v1.1.0")]
    forge, values = api_forge(tmp_path, annotated_tag(CODE_LEG, "v1.1.0", object_,
                                                      commit, **lie))
    values.update(GITHUB_REF=ref, GITHUB_REF_NAME=ref_name(ref), GITHUB_SHA=commit,
                  GITHUB_REPOSITORY=CODE_LEG, VERSION=version)
    workflow = release()
    runner = Runner(tmp_path / "work", workflow, "build", values, forge)
    done = runner.run(named(workflow, "build", REF_STEP), cwd=checkout)
    assert (done.returncode == 0) == passes, transcript(done)
    if passes:
        assert done.stdout.strip().endswith(
            f"v1.1.0: annotated, tag object {objects['v1.1.0']}, at {commit}"), transcript(done)
        assert fixture_git(tmp_path / "git" / "home", checkout, "rev-parse",
                           "refs/tags/v1.1.0") == objects["v1.1.0"]
    else:
        assert "::error::" in done.stdout, transcript(done)
    if ref != f"refs/tags/v{version}":
        assert forge_asked(tmp_path) == [], (
            f"the step asked the forge about a ref it must refuse: {forge_asked(tmp_path)}")


#: A `gh` that answers `compare` as the forge does (`FORGE_COMPARE`, a JSON map
#: of branch to status as `compare/<commit>...<branch>` reads, flipped where a
#: script asks the other way round), writes down each branch it was asked
#: about, and answers anything else, or a branch with no status, as a 404.
COMPARE_FORGE = r'''
import json, os, sys
args = sys.argv[1:]
paths = [a for a in args[1:] if "/compare/" in a]
if args[:1] != ["api"] or len(paths) != 1:
    sys.stderr.write("gh: Not Found (HTTP 404)\n")
    sys.exit(1)
base, _, head = paths[0].split("/compare/", 1)[1].partition("...")
sha = os.environ["FORGE_COMMIT"]
flip = base != sha
branch = (base if flip else head)
for prefix in ("refs/heads/", "heads/"):
    if branch.startswith(prefix):
        branch = branch[len(prefix):]
with open(os.environ["FORGE_LOG"], "a", encoding="utf-8") as log:
    log.write(branch + "\n")
status = json.loads(os.environ["FORGE_COMPARE"]).get(branch)
if status is None:
    sys.stderr.write("gh: Not Found (HTTP 404)\n")
    sys.exit(1)
if flip:
    status = {"ahead": "behind", "behind": "ahead"}.get(status, status)
jq = None
for flag in ("--jq", "-q"):
    if flag in args:
        jq = args[args.index(flag) + 1]
if jq is None:
    print(json.dumps({"status": status}))
elif jq.strip() == ".status":
    print(status)
else:
    sys.stderr.write("fake forge: compare answers --jq .status alone\n")
    sys.exit(1)
'''

#: `(ref, version, the forge's compare by branch, passes, branches it may ask)`.
ON_BRANCH_CASES = {
    "on-main-identical": ("refs/tags/v1.1.0", "1.1.0", {"main": "identical"},
                          True),
    "on-main-ahead": ("refs/tags/v1.1.0", "1.1.0", {"main": "ahead"}, True),
    "a-patch-on-its-release-branch": (
        "refs/tags/v1.0.1", "1.0.1",
        {"main": "diverged", "release/v1.0": "identical"}, True),
    "an-rc-on-its-release-branch": (
        "refs/tags/v1.1.0rc1", "1.1.0rc1",
        {"main": "diverged", "release/v1.1": "ahead"}, True),
    "on-neither-with-no-release-branch": (
        "refs/tags/v1.1.0", "1.1.0", {"main": "diverged"}, False),
    "behind-main-and-diverged-from-the-release-branch": (
        "refs/tags/v1.1.0", "1.1.0",
        {"main": "behind", "release/v1.1": "diverged"}, False),
    "on-another-line-s-release-branch": (
        "refs/tags/v1.1.0", "1.1.0",
        {"main": "diverged", "release/v1.0": "identical"}, False),
    "a-pull-request-ref-the-forge-knows-nothing-of": (
        "refs/pull/7/merge", "1.1.0", {}, False),
    "a-branch-rehearsal": ("refs/heads/l3-rehearsal-v1.1.0", "1.1.0rc1", {},
                           True),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", ON_BRANCH_CASES)
def test_release_build_the_branch_step_answers_from_the_forge_s_compare(tmp_path,
                                                                     which):
    """STEP 3 (FR-029, the model's `release.yml:243-276`): on a tag, the
    forge's compare must call `main` or `release/v<X.Y>` identical to the
    commit or ahead of it, `X.Y` the version's own (`1.1` for `1.1.0rc1`),
    and it asks about no other branch. On a branch the rehearsal has no
    release branch to be on: the step says so, passes, and asks nothing."""
    ref, version, statuses, passes = ON_BRANCH_CASES[which]
    workflow = release()
    forge = python_tool(tmp_path / "forge", "gh", COMPARE_FORGE)
    log = tmp_path / "compare.log"
    values = ref_values(ref, version)
    values.update(FORGE_COMPARE=json.dumps(statuses), FORGE_LOG=str(log),
                  FORGE_COMMIT=values["GITHUB_SHA"])
    runner = Runner(tmp_path / "work", workflow, "build", values, forge)
    done = runner.run(named(workflow, "build", ON_BRANCH_STEP))
    asked = set(log.read_text(encoding="utf-8").split()) if log.exists() else set()
    assert (done.returncode == 0) == passes, transcript(done)
    line = "release/v" + ".".join(version.split(".")[:2])
    if ref.startswith("refs/heads/"):
        assert asked == set(), f"a rehearsal asked the forge about {asked}"
        assert done.stdout.strip(), "the rehearsal does not say why it passes"
    elif ref.startswith("refs/tags/"):
        assert asked <= {"main", line}, (
            f"the step asked about {sorted(asked)}; the version's branches "
            f"are main and {line}")
        if not passes:
            assert asked == {"main", line}, f"refused after asking {sorted(asked)}"


# --- the gate: tests.yml's four jobs on this commit ------------------------------

#: A `gh` that answers the gate's reads as the forge does, from `FORGE_DATA`:
#: a commit's `tests.yml` runs (`actions/runs`, or `actions/workflows/<file>/
#: runs`, honouring `head_sha` and `event` where the query names them, as the
#: API does, unless `FORGE_IGNORES` names one) and a run's jobs
#: (`actions/runs/<id>/jobs`). `--jq '.<key>[]'` answers one object per line,
#: as gh does; no `--jq` answers the page.
RUNS_FORGE = r'''
import json, os, re, sys, urllib.parse
args = sys.argv[1:]
with open(os.environ["FORGE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
paths = [a for a in args[1:] if a.lstrip("/").startswith("repos/")]
if args[:1] != ["api"] or len(paths) != 1:
    sys.stderr.write("gh: Not Found (HTTP 404)\n")
    sys.exit(1)
path, _, query = paths[0].lstrip("/").partition("?")
params = dict(urllib.parse.parse_qsl(query))
with open(os.environ["FORGE_DATA"], encoding="utf-8") as handle:
    data = json.load(handle)
repo = re.escape(os.environ["FORGE_REPOSITORY"])
jobs = re.fullmatch(rf"repos/{repo}/actions/runs/([0-9]+)/jobs", path)
runs = re.fullmatch(rf"repos/{repo}/actions/(?:workflows/([^/]+)/)?runs", path)
if jobs:
    key, rows = "jobs", data["jobs"].get(jobs.group(1), [])
elif runs:
    key, rows = "workflow_runs", data["runs"]
    if runs.group(1):
        rows = [r for r in rows if r["path"].rsplit("/", 1)[-1] == runs.group(1)]
    ignored = os.environ.get("FORGE_IGNORES", "").split(",")
    for name in ("head_sha", "event"):
        if name in params and name not in ignored:
            rows = [r for r in rows if r[name] == params[name]]
else:
    sys.stderr.write("gh: Not Found (HTTP 404)\n")
    sys.exit(1)
jq = None
for flag in ("--jq", "-q"):
    if flag in args:
        jq = args[args.index(flag) + 1]
if jq is None:
    print(json.dumps({"total_count": len(rows), key: rows}))
elif jq.strip() == f".{key}[]":
    for row in rows:
        print(json.dumps(row))
else:
    sys.stderr.write(f"fake forge: this route answers --jq .{key}[] alone\n")
    sys.exit(1)
'''

#: The commit every gate case is about, and a run of `tests.yml` on it.
GATE_SHA = "c" * 40


def a_run(number: int, event: str = "push", head_sha: str = GATE_SHA,
          path: str = ".github/workflows/tests.yml") -> dict:
    return {"id": number, "event": event, "head_sha": head_sha, "path": path,
            "name": "tests", "html_url": f"https://github.invalid/run/{number}"}


def a_job(name: str, when: str = "2026-10-18T17:00:00Z",
          conclusion: Optional[str] = "success",
          status: str = "completed") -> dict:
    return {"name": name, "status": status,
            "conclusion": conclusion if status == "completed" else None,
            "started_at": "2026-10-18T16:30:00Z",
            "completed_at": when if status == "completed" else None,
            "html_url": f"https://github.invalid/job/{name}/{when}"}


def the_four(when: str = "2026-10-18T17:00:00Z", leave_out: str = "",
             **changes) -> list:
    """The four gate jobs of one run, `changes` naming a job's own fields."""
    return [a_job(name, when, **changes.get(name.replace("-", "_"), {}))
            for name in GATE if name != leave_out]


GATE_CASES = {
    "a-push-run-passed": ([a_run(1)], {1: the_four()}, True, ""),
    "a-dispatch-run-passed": ([a_run(1, "workflow_dispatch")], {1: the_four()},
                              True, ""),
    "a-pull-request-run-alone": ([a_run(1, "pull_request")], {1: the_four()},
                                 False, ""),
    "a-run-of-another-commit": ([a_run(1, head_sha="d" * 40)], {1: the_four()},
                                False, ""),
    "a-run-of-another-workflow": (
        [a_run(1, path=".github/workflows/release.yml")], {1: the_four()},
        False, ""),
    **{f"no-{name}-job": ([a_run(1)], {1: the_four(leave_out=name)}, False,
                          name) for name in GATE},
    "package-still-in-progress": (
        [a_run(1)], {1: the_four(package={"status": "in_progress"})}, False,
        "package"),
    "package-skipped": (
        [a_run(1)], {1: the_four(package={"conclusion": "skipped"})}, False,
        "package"),
    "package-older-success-newer-failure": (
        [a_run(1), a_run(2, "workflow_dispatch")],
        {1: the_four("2026-10-18T17:00:00Z"),
         2: the_four("2026-10-18T18:00:00Z", package={"conclusion": "failure"})},
        False, "package"),
    "package-older-failure-newer-success": (
        [a_run(1), a_run(2, "workflow_dispatch")],
        {1: the_four("2026-10-18T17:00:00Z", package={"conclusion": "failure"}),
         2: the_four("2026-10-18T18:00:00Z")},
        True, ""),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", GATE_CASES)
def test_release_build_the_gate_decides_from_the_runs_jobs(tmp_path, which):
    """STEP 6 (FR-029, FR-046) under a forge: each of `guard-launch-mode`,
    `tests`, `tests-no-submodule` and `package` ran in a push or dispatch run
    of `tests.yml` on the commit, none is still running, and the newest of
    each to finish succeeded. A pull request's run, another commit's and
    another workflow's do not count, and a job missing, skipped, running or
    newest-failed refuses, naming that job."""
    runs, jobs, passes, names = GATE_CASES[which]
    done = run_gate(tmp_path, runs, jobs)
    assert (done.returncode == 0) == passes, transcript(done)
    if names:
        assert names in done.stdout + done.stderr, (
            f"the refusal does not name {names}:\n{transcript(done)}")


def run_gate(tmp_path: Path, runs: list, jobs: dict,
             ignores: str = "") -> subprocess.CompletedProcess:
    """Step 6 under `RUNS_FORGE`, holding `runs` and their `jobs`, and
    ignoring the query parameters `ignores` names."""
    workflow = release()
    data = tmp_path / "forge.json"
    data.write_text(json.dumps({"runs": runs, "jobs": {str(k): v for k, v
                                                       in jobs.items()}}),
                    encoding="utf-8")
    forge = python_tool(tmp_path / "forge", "gh", RUNS_FORGE)
    values = {"GITHUB_REPOSITORY": CODE_LEG, "GITHUB_SHA": GATE_SHA,
              "VERSION": "1.1.0", "FORGE_DATA": str(data),
              "FORGE_LOG": str(tmp_path / "forge.log"),
              "FORGE_REPOSITORY": CODE_LEG, "FORGE_IGNORES": ignores}
    runner = Runner(tmp_path / "work", workflow, "build", values, forge)
    return runner.run(named(workflow, "build", GATE_STEP))


#: STEP 6 UNDER A FORGE THAT RETURNS EVERY COMMIT'S RUNS, whatever the query
#: asks: `(the runs and their jobs, whether the step passes)`. So the step's
#: own `head_sha` filter is what keeps another commit's runs out.
GATE_UNFILTERED_CASES = {
    "another-commit-s-green-run-alone": (
        [a_run(1, head_sha="d" * 40)], {1: the_four()}, False),
    "this-commit-s-green-run-and-another-s-red-one": (
        [a_run(1), a_run(2, head_sha="d" * 40)],
        {1: the_four("2026-10-18T17:00:00Z"),
         2: the_four("2026-10-18T18:00:00Z", package={"conclusion": "failure"})}, True),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", GATE_UNFILTERED_CASES)
def test_release_build_the_gate_counts_this_commit_s_runs_whatever_the_forge_returns(
        tmp_path, which):
    """STEP 6 KEEPS TO THE COMMIT ITSELF (FR-029): under a forge that answers
    `head_sha=` with every commit's runs, another commit's green run does
    not pass this one, and another commit's newer red run does not refuse
    it."""
    runs, jobs, passes = GATE_UNFILTERED_CASES[which]
    done = run_gate(tmp_path, runs, jobs, ignores="head_sha")
    assert (done.returncode == 0) == passes, transcript(done)


@NEEDS_UPSTREAM
def test_release_build_the_gate_reads_tests_yml_s_own_runs_and_never_check_runs():
    """THE GATE'S SOURCE (the model's RV599, MUST 1): the jobs of `tests.yml`'s
    push and dispatch runs, never the commit's check runs, which anything
    holding an Actions token can create."""
    script = run_text(named(release(), "build", GATE_STEP))
    assert ".github/workflows/tests.yml" in script, "the gate names no workflow"
    for word in ("push", "workflow_dispatch", "/jobs", *GATE):
        assert word in script, f"the gate never reads {word!r}"
    assert "check-runs" not in script and "check_suite" not in script


# --- the digest and its label ---------------------------------------------------

@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
def test_release_build_the_digest_label_is_one_literal_in_the_installer_the_pin_and_the_standard(
        tmp_path):
    """ONE LITERAL, THREE PLACES (FR-029, design.md Decision 10): the label
    `--version` prints beside a stamped digest, the pin's `digest_definition`
    and the pinned standard's `TREE_DIGEST_DEFINITION` are all
    `sorted-ls-tree-r-v1`. The label is read from what `--version` prints in a
    `package_tree`, not from the script's text."""
    release_ = {"VERSION": "1.1.0", "TAG": "v1.1.0", "COMMIT": "a" * 40,
                "DIGEST": "b" * 64, "REPOSITORY": CODE_LEG}
    payload = layout.package_tree(tmp_path / "prefix",
                                  stamp=layout.stamp_text(**release_))
    done = run_version(payload, tmp_path / "home")
    lines = done.stdout.splitlines()
    assert done.returncode == 0 and len(lines) == 5, transcript(done)
    found = re.fullmatch(r"  digest    [0-9a-f]{64} \((.+)\)", lines[4])
    assert found, f"--version's digest line is {lines[4]!r}"
    pin = standard().load_yaml(PIN).get("digest_definition")
    assert (found.group(1), pin, standard().TREE_DIGEST_DEFINITION) == (
        DIGEST_LABEL, DIGEST_LABEL, DIGEST_LABEL)


@NEEDS_UPSTREAM
def test_release_build_the_digest_step_compares_the_definition_with_the_literal_and_the_pin():
    """STEP 7 (FR-029, FR-030): `tree_digest` on the checkout against
    `tree_digest_from_gh` on the forge, both from the PINNED submodule's
    `scripts/repo_shape.py`, and its `TREE_DIGEST_DEFINITION` held to the
    literal and to the pin's `digest_definition`. No copy of the digest code
    is added anywhere outside the submodule."""
    script = run_text(named(release(), "build", DIGEST_STEP))
    for word in ("tree_digest(", "tree_digest_from_gh(", "TREE_DIGEST_DEFINITION",
                 DIGEST_LABEL, "digest_definition", "openreposhape-pin.yaml",
                 "upstream", "openRepoShape", "scripts"):
        assert word in script, f"the digest step never names {word!r}"
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=str(REPO),
                             capture_output=True, check=True).stdout.split(b"\0")
    copies = [p.decode() for p in tracked if p.endswith(b"repo_shape.py")]
    assert copies == [], f"a copy of the standard's digest code: {copies}"


#: A `gh` that answers one question, the forge's recursive tree listing of
#: `FORGE_COMMIT` in `FORGE_REPOSITORY`, with `FORGE_DATA`; anything else is a 404.
TREE_FORGE = r'''
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FORGE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
want = ("repos/" + os.environ["FORGE_REPOSITORY"] + "/git/trees/"
        + os.environ["FORGE_COMMIT"] + "?recursive=1")
if args[:1] != ["api"] or want not in [a.lstrip("/") for a in args[1:]]:
    sys.stderr.write("gh: Not Found (HTTP 404)\n")
    sys.exit(1)
with open(os.environ["FORGE_DATA"], encoding="utf-8") as handle:
    sys.stdout.write(handle.read())
'''


def run_digest_step(tmp_path: Path, lie: bool, here: Path = REPO
                    ) -> Tuple[subprocess.CompletedProcess, Runner, str]:
    """The digest step, run in this checkout (or in `here`, laid out as it
    is), under a forge whose tree listing is HEAD's own, or HEAD's with one
    object changed."""
    workflow = release()
    sha, tree = head()
    rows = [{"path": p, "mode": m, "type": k, "sha": o}
            for p, (m, k, o) in sorted(tree.items())]
    if lie:
        rows[0] = dict(rows[0], sha="0" * 40)
    data = tmp_path / "tree.json"
    data.write_text(json.dumps({"sha": sha, "tree": rows, "truncated": False}),
                    encoding="utf-8")
    forge = python_tool(tmp_path / "forge", "gh", TREE_FORGE)
    values = {"GITHUB_SHA": sha, "GITHUB_REPOSITORY": CODE_LEG,
              "GITHUB_WORKSPACE": str(here), "VERSION": "1.1.0",
              "FORGE_DATA": str(data), "FORGE_LOG": str(tmp_path / "forge.log"),
              "FORGE_REPOSITORY": CODE_LEG, "FORGE_COMMIT": sha}
    if here != REPO:
        values["GIT_DIR"] = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir"], cwd=str(REPO),
            capture_output=True, text=True, check=True).stdout.strip()
    runner = Runner(tmp_path / "work", workflow, "build", values, forge)
    cache = STANDARD_SCRIPTS / "__pycache__"
    existed = cache.exists()
    try:
        done = runner.run(named(workflow, "build", DIGEST_STEP), cwd=here)
    finally:
        if not existed and cache.is_dir():
            shutil.rmtree(cache)
    return done, runner, standard().tree_digest(REPO, sha)


#: A definition no standard here digests by.
OTHER_LABEL = "sorted-ls-tree-r-v0"


def digest_checkout(tmp_path: Path, standard_label: str, pin_label: str) -> Path:
    """A place laid out as this checkout is for the digest step: a copy of
    the pinned standard's scripts and of the pin, each where the checkout
    has it, saying the definition it is given. git reads this checkout's own
    objects there, through `GIT_DIR`."""
    here = tmp_path / "checkout"
    scripts = here / STANDARD_SCRIPTS.relative_to(REPO)
    shutil.copytree(str(STANDARD_SCRIPTS), str(scripts),
                    ignore=shutil.ignore_patterns("__pycache__"))
    pin = here / PIN.relative_to(REPO)
    pin.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(PIN), str(pin))
    for path, line, said in ((scripts / "repo_shape.py",
                              'TREE_DIGEST_DEFINITION = "{}"\n', standard_label),
                             (pin, "digest_definition: {}\n", pin_label)):
        text = path.read_text(encoding="utf-8")
        assert text.count(line.format(DIGEST_LABEL)) == 1, (
            f"{path.name} does not say {line.format(DIGEST_LABEL)!r} once")
        path.write_text(text.replace(line.format(DIGEST_LABEL), line.format(said)),
                        encoding="utf-8")
    return here


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which, standard_label, pin_label", [
    ("as committed", DIGEST_LABEL, DIGEST_LABEL),
    ("the pin names another", DIGEST_LABEL, OTHER_LABEL),
    ("the standard names another", OTHER_LABEL, DIGEST_LABEL),
    ("both name another, alike", OTHER_LABEL, OTHER_LABEL),
])
def test_release_build_the_digest_step_holds_the_definition_to_the_literal_and_the_pin(
        tmp_path, which, standard_label, pin_label):
    """STEP 7, RUN, IN A COPY (FR-029): the digest step, run where a copy of
    the pinned standard and of the pin sit as they do in this checkout, and
    git reads this checkout's objects. As committed it passes and records
    HEAD's digest. Where the pin, the standard, or both alike name a
    definition other than the literal `--version` prints, the step refuses
    and records no digest: it compares `TREE_DIGEST_DEFINITION` with the
    literal and with the pin, and does not only name them."""
    here = digest_checkout(tmp_path, standard_label, pin_label)
    done, runner, digest = run_digest_step(tmp_path, lie=False, here=here)
    if which == "as committed":
        assert done.returncode == 0, transcript(done)
        assert [v for _, v in runner.recorded() if v == digest], (
            f"the step records {runner.recorded()}, not {digest}")
    else:
        assert done.returncode != 0, f"{which}, and the step passed:\n{transcript(done)}"
        assert not [v for _, v in runner.recorded() if v == digest], (
            f"{which}, and the step records the digest anyway")


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
def test_release_build_the_digest_step_records_the_commit_s_digest_where_the_forge_agrees(
        tmp_path):
    """STEP 7, RUN: in this checkout, under a forge whose listing is HEAD's
    own, the step passes and records HEAD's `sorted-ls-tree-r-v1` digest as
    the pinned standard computes it."""
    done, runner, digest = run_digest_step(tmp_path, lie=False)
    assert done.returncode == 0, transcript(done)
    assert [v for _, v in runner.recorded() if v == digest], (
        f"the step records {runner.recorded()}, not {digest}")


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
def test_release_build_the_digest_step_refuses_a_forge_that_disagrees(tmp_path):
    """STEP 7, RUN: a forge whose listing names one object differently is a
    release that would not be the forge's commit, and the step refuses."""
    done, runner, digest = run_digest_step(tmp_path, lie=True)
    assert done.returncode != 0, transcript(done)
    assert not [v for _, v in runner.recorded() if v == digest]


# --- step 13: the wheel check, on synthetic wheels ---------------------------------

WHEEL_TIME = (2026, 10, 18, 0, 0, 0)
ENTRY_POINTS = "[console_scripts]\nopenRepoTools = openrepotools.cli:main\n"


def wheel_release(version: str) -> dict:
    return {"VERSION": version, "TAG": f"v{version}", "COMMIT": head()[0],
            "DIGEST": "d" * 64, "REPOSITORY": CODE_LEG}


def wheel_members(release_: dict) -> Tuple[Dict[str, Tuple[bytes, int]], str]:
    """THE WHEEL THE RELEASE BUILD WRITES FOR HEAD, laid out as hatchling
    1.27.0 lays it out, from git's own blobs: the package's modules, the
    stamp with the release's five values, the 24 payload files at the modes
    hatchling gives HEAD's (0755 or 0644), and the five `.dist-info` names.
    Returns `{member: (bytes, mode)}` and the `.dist-info/` prefix."""
    sha, tree = head()
    members: Dict[str, Tuple[bytes, int]] = {}
    for path in sorted(tree):
        found = re.fullmatch(r"src/openrepotools/([^/]+\.py)", path)
        if found:
            data = head_blob(path)
            if found.group(1) == "_release.py":
                data = stamped(data.decode("utf-8"), release_).encode("utf-8")
            members[f"openrepotools/{found.group(1)}"] = (data, 0o644)
    for rel in layout.payload_paths():
        mode = tree[rel][0]
        members[layout.PAYLOAD_PREFIX + rel] = (
            head_blob(rel), 0o755 if mode == "100755" else 0o644)
    info = f"openrepotools-{release_['VERSION']}.dist-info/"
    members[info + "METADATA"] = ((
        "Metadata-Version: 2.4\nName: openrepotools\n"
        f"Version: {release_['VERSION']}\nLicense-Expression: Apache-2.0\n"
        "License-File: LICENSE\nRequires-Python: >=3.9\n").encode(), 0o644)
    members[info + "WHEEL"] = (b"Wheel-Version: 1.0\nGenerator: hatchling "
                               b"1.27.0\nRoot-Is-Purelib: true\nTag: "
                               b"py3-none-any\n", 0o644)
    members[info + "entry_points.txt"] = (ENTRY_POINTS.encode(), 0o644)
    members[info + "licenses/LICENSE"] = (head_blob("LICENSE"), 0o644)
    return members, info


def write_wheel(path: Path, members: Dict[str, Tuple[bytes, int]],
                info: str) -> Path:
    """`members` as a wheel, with the `RECORD` hatchling would write for
    them, at `path`."""
    rows = []
    for name, (data, _) in members.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest())
        rows.append(f"{name},sha256={digest.decode().rstrip('=')},{len(data)}")
    rows.append(f"{info}RECORD,,")
    every = dict(members)
    every[info + "RECORD"] = (("\n".join(rows) + "\n").encode(), 0o644)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as wheel:
        for name, (data, mode) in every.items():
            entry = zipfile.ZipInfo(name, date_time=WHEEL_TIME)
            entry.external_attr = (stat.S_IFREG | mode) << 16
            entry.create_system = 3
            entry.compress_type = zipfile.ZIP_DEFLATED
            wheel.writestr(entry, data)
    return path


def no_license(members: dict, info: str) -> None:
    """A tree with no `LICENSE`: no `licenses/LICENSE`, and no
    `License-File` line, as hatchling builds one."""
    del members[info + "licenses/LICENSE"]
    data, mode = members[info + "METADATA"]
    members[info + "METADATA"] = (data.replace(b"License-File: LICENSE\n", b""),
                                  mode)


def a_changed_member(member: str) -> Callable[[dict, str], None]:
    """`member`, where `{info}` is the `.dist-info/` prefix, with its middle
    byte changed."""
    def change(members: dict, info: str) -> None:
        name = member.format(info=info)
        data, mode = members[name]
        middle = len(data) // 2
        members[name] = (
            data[:middle] + bytes([data[middle] ^ 0x20]) + data[middle + 1:], mode)
    return change


def a_changed_byte(rel: str) -> Callable[[dict, str], None]:
    return a_changed_member(layout.PAYLOAD_PREFIX + rel)


def a_changed_mode(rel: str, mode: int) -> Callable[[dict, str], None]:
    def change(members: dict, info: str) -> None:
        data, _ = members[layout.PAYLOAD_PREFIX + rel]
        members[layout.PAYLOAD_PREFIX + rel] = (data, mode)
    return change


def a_missing_member(member: str) -> Callable[[dict, str], None]:
    def change(members: dict, info: str) -> None:
        del members[member]
    return change


def an_extra_member(member: str, data: bytes) -> Callable[[dict, str], None]:
    """`member`, where `{info}` is the `.dist-info/` prefix, added."""
    def change(members: dict, info: str) -> None:
        name = member.format(info=info)
        assert name not in members, f"the case is wrong: {name} is HEAD's"
        members[name] = (data, 0o644)
    return change


def a_dist_info_file_with(name: str, more: bytes) -> Callable[[dict, str], None]:
    """The `.dist-info/` file `name` with `more` after its last line."""
    def change(members: dict, info: str) -> None:
        data, mode = members[info + name]
        members[info + name] = (data + more, mode)
    return change


def a_line_more_in_the_stamp(members: dict, info: str) -> None:
    """The stamp with a comment line after its last: its five assignments are
    still the release's, and its bytes are not the committed file stamped."""
    data, mode = members["openrepotools/_release.py"]
    members["openrepotools/_release.py"] = (
        data + b"# a line the committed stamp does not have\n", mode)


#: THE SYNTHETIC WHEELS THAT ARE NOT THE COMMIT'S: contracts/workflows.md's
#: four, then one for each other check the step makes (contracts/wheel.md's
#: checks 2 to 5, the metadata, the entry points, and the run's values).
#: Each is `(what its refusal's ::error:: line must name, the change to the
#: wheel as built, the mode HEAD gives the file changed, the run's values
#: where they are not the release's)`.
NOT_THE_COMMITS = {
    "no-licenses-LICENSE": ("licenses/LICENSE, so the commit's LICENSE is not in it",
                            no_license, None, None),
    "a-payload-byte-changed": ("lanes-edit.sh", a_changed_byte("lanes-edit.sh"),
                               None, None),
    "a-payload-mode-0755-made-0644": (
        "link-estates", a_changed_mode("link-estates", 0o644), "100755", None),
    "a-payload-mode-0644-made-0755": (
        "repos.tsv", a_changed_mode("repos.tsv", 0o755), "100644", None),
    "a-licenses-LICENSE-of-other-bytes": (
        "licenses/LICENSE", a_changed_member("{info}licenses/LICENSE"), None,
        None),
    "a-module-byte-changed": ("openrepotools/cli.py",
                              a_changed_member("openrepotools/cli.py"), None,
                              None),
    "a-payload-file-missing": (
        "openrepotools/payload/lanes-index",
        a_missing_member(layout.PAYLOAD_PREFIX + "lanes-index"), None, None),
    "a-member-nothing-puts-there": (
        "extra.pth", an_extra_member("extra.pth", b"import os\n"), None, None),
    "the-stamp-with-a-line-more": ("_release.py", a_line_more_in_the_stamp,
                                   None, None),
    "a-run-of-another-repository": (
        f"'REPOSITORY': '{THIS_REPOSITORY}'", None, None,
        {"GITHUB_REPOSITORY": THIS_REPOSITORY}),
    "metadata-naming-a-dependency": (
        "'Requires-Dist': ['requests']",
        a_dist_info_file_with("METADATA", b"Requires-Dist: requests\n"), None, None),
    "a-second-console-script": (
        "'lane': 'openrepotools.cli:main'",
        a_dist_info_file_with("entry_points.txt", b"lane = openrepotools.cli:main\n"),
        None, None),
    "a-sixth-dist-info-file": (
        "INSTALLER", an_extra_member("{info}INSTALLER", b"pip\n"), None, None),
}


def run_wheel_check(workflow: dict, work: Path, release_: dict,
                    change: Optional[Callable[[dict, str], None]],
                    run: Optional[dict] = None) -> subprocess.CompletedProcess:
    """The wheel check's heredoc on the wheel as built for `release_`, with
    `change` made to it, under the run's values: the release's, or `run`'s
    where it names any."""
    members, info = wheel_members(release_)
    if change is not None:
        change(members, info)
    wheel = write_wheel(work / "dist" / f"openrepotools-{release_['VERSION']}"
                        "-py3-none-any.whl", members, info)
    values = release_values(release_)
    values.update(run or {})
    return run_heredoc(named(workflow, "build", WHEEL_CHECK_STEP), work, [wheel],
                       values, cwd=REPO)


@NEEDS_UPSTREAM
@pytest.mark.parametrize("version", ["1.1.0", "1.1.0rc1"])
def test_release_build_the_wheel_check_passes_the_wheel_as_built(tmp_path,
                                                                 version):
    """STEP 13 ON THE WHEEL AS BUILT (contracts/wheel.md, checks 2 to 6): every
    payload file is HEAD's blob in bytes and mode, each module is HEAD's, the
    stamp is HEAD's with its five lines the release's, and the `.dist-info`
    is the five names with HEAD's `LICENSE`. A final and a pre-release pass
    alike (design.md Decision 10)."""
    done = run_wheel_check(release(), tmp_path / "as-built",
                           wheel_release(version), None)
    assert done.returncode == 0, transcript(done)


@NEEDS_UPSTREAM
@pytest.mark.parametrize("which", NOT_THE_COMMITS)
def test_release_build_the_wheel_check_refuses_a_wheel_that_is_not_the_commit_s(
        tmp_path, which):
    """STEP 13 ON EACH WHEEL THAT IS NOT THE COMMIT'S (FR-002, FR-006): no
    `licenses/LICENSE`, a payload file with a byte changed, and a payload file
    with its mode changed either way; then a `licenses/LICENSE` that is not
    the commit's, a module with a byte changed, a payload file missing, a
    member nothing puts in the wheel, a stamp whose bytes are not the
    committed file stamped though its five values are the release's, the
    wheel as built checked in a run of another repository, metadata that
    names a dependency, a second console script, and a sixth `.dist-info/`
    file. Each fails, and among the lines it prints beyond the wheel as
    built's is an `::error::` line naming what is wrong. Only that line is
    the refusal: the step's own `print`s show some of the same values (the
    metadata, for one) whether or not it refuses them."""
    names, change, head_mode, run = NOT_THE_COMMITS[which]
    if head_mode is not None:
        assert head()[1][names][0] == head_mode, (
            f"the case is wrong: HEAD's {names} is not {head_mode}")
    workflow = release()
    release_ = wheel_release("1.1.0")
    good = run_wheel_check(workflow, tmp_path / "w" / "a", release_, None)
    bad = run_wheel_check(workflow, tmp_path / "w" / "b", release_, change, run)
    assert good.returncode == 0, transcript(good)
    assert bad.returncode != 0, transcript(bad)
    assert "Traceback (most recent call last)" not in bad.stdout + bad.stderr, (
        f"the check crashed rather than name the problem:\n{transcript(bad)}")

    def lines(done: subprocess.CompletedProcess, side: str) -> List[str]:
        text = (done.stdout + done.stderr).replace(str(tmp_path / "w" / side),
                                                   "<work>")
        return text.splitlines()

    known = set(lines(good, "a"))
    new = [line for line in lines(bad, "b") if line not in known]
    assert [line for line in new if line.startswith("::error::") and names in line], (
        f"no ::error:: line of the refusal names {names}:\n{transcript(bad)}")


# --- the stamp writer --------------------------------------------------------------

RELEASES = {
    "the-code-leg-s-v1.1.0": {
        "VERSION": "1.1.0", "TAG": "v1.1.0",
        "COMMIT": "0123456789abcdef0123456789abcdef01234567",
        "DIGEST": "89abcdef01234567" * 4, "REPOSITORY": CODE_LEG},
    "an-rc-rehearsal-here": {
        "VERSION": "1.1.0rc1", "TAG": "v1.1.0rc1", "COMMIT": "fedcba98" * 5,
        "DIGEST": "0f1e2d3c4b5a6978" * 4, "REPOSITORY": THIS_REPOSITORY},
    "a-patch-with-long-numbers": {
        "VERSION": "2.10.30", "TAG": "v2.10.30", "COMMIT": "a1" * 20,
        "DIGEST": "b2" * 32, "REPOSITORY": "someone/openRepoTools-code"},
}

#: Values no release carries (contracts/stamp.md, the writer's checks): each
#: changes the first release under every name that carries it.
NO_RELEASE_CARRIES = {
    **{f"version-{v or 'empty'}": {"VERSION": v, "TAG": f"v{v}"}
       for v in ("0.0.0", "1.1", "01.1.0", "1.1.0-rc1", "1.1.0rc01", "1.1.0rc",
                 "1.1.0.0", "")},
    "commit-in-upper-case": {"COMMIT": "A" * 40},
    "commit-of-39-digits": {"COMMIT": "a" * 39},
    "commit-empty": {"COMMIT": ""},
    "digest-of-63-digits": {"DIGEST": "b" * 63},
    "digest-empty": {"DIGEST": ""},
    "repository-without-an-owner": {"REPOSITORY": "openRepoTools"},
    "repository-a-b-c": {"REPOSITORY": "a/b/c"},
    "repository-with-a-quote": {"REPOSITORY": 'opensoft/open"RepoTools'},
    "repository-empty": {"REPOSITORY": ""},
    "a-tag-of-another-version": {"TAG": "v1.1.1"},
}


def write_stamp(workflow: dict, work: Path, release_: dict,
                texts: Optional[List[bytes]] = None
                ) -> Tuple[subprocess.CompletedProcess, List[Path]]:
    """The stamp step's own heredoc, run as the workflow runs it over the two
    extractions' `src/openrepotools/_release.py`: copies of the committed
    stamp, or `texts`."""
    copies = [work / side / "src" / "openrepotools" / "_release.py"
              for side in ("a", "b")]
    for copy, text in zip(copies, texts or [STAMP.read_bytes()] * 2):
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(text)
    done = run_heredoc(named(workflow, "build", STAMP_STEP), work / "run",
                       copies, release_values(release_), cwd=work)
    return done, copies


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", RELEASES)
def test_release_stamp_writer_writes_a_stamp_version_reads_back(tmp_path, which):
    """THE WRITER AND THE READER AGREE (FR-013, contracts/stamp.md). The
    build's own writer, run on two copies of the committed stamp, writes the
    same file into both: every line the committed file's but its five
    assignments, each now the release's value, and the last newline kept.
    Hatchling's pattern reads its `VERSION`, and `--version` from a
    `package_tree` carrying it prints the stamped five lines exactly. A final
    and a pre-release alike (design.md Decision 10)."""
    release_ = RELEASES[which]
    done, copies = write_stamp(release(), tmp_path, release_)
    assert done.returncode == 0, transcript(done)
    first, second = (copy.read_bytes() for copy in copies)
    assert first == second, "the two extractions carry different stamps"
    committed = STAMP.read_text(encoding="utf-8").split("\n")
    lines = first.decode("utf-8").split("\n")
    assert len(lines) == len(committed) and lines[-1] == "", (
        "the stamp is not the committed file line for line")
    changed = sorted(new for old, new in zip(committed, lines) if old != new)
    assert changed == sorted(f'{name} = "{value}"'
                             for name, value in release_.items()), changed
    found = re.search(HATCH_PATTERN, first.decode("utf-8"), re.MULTILINE)
    assert found and found.group("version") == release_["VERSION"]
    payload = layout.package_tree(tmp_path / "prefix", stamp=first)
    shown = run_version(payload, tmp_path / "home")
    assert (shown.returncode, shown.stdout, shown.stderr) == (
        0, STAMPED_VERSION.format(**release_), ""), transcript(shown)


@NEEDS_UPSTREAM
@pytest.mark.parametrize("which", NO_RELEASE_CARRIES)
def test_release_stamp_writer_refuses_a_value_no_release_carries(tmp_path, which):
    """A VALUE NO RELEASE CARRIES IS REFUSED, AND NOTHING IS WRITTEN: the
    unstamped `0.0.0`, a version that is neither `X.Y.Z` nor `X.Y.ZrcN`, and a
    commit, a digest or a repository of the wrong shape or none."""
    release_ = dict(RELEASES["the-code-leg-s-v1.1.0"])
    release_.update(NO_RELEASE_CARRIES[which])
    done, copies = write_stamp(release(), tmp_path, release_)
    assert done.returncode != 0, transcript(done)
    for copy in copies:
        assert copy.read_bytes() == STAMP.read_bytes(), f"{copy} was written"


@NEEDS_UPSTREAM
def test_release_stamp_writer_refuses_a_file_already_stamped(tmp_path):
    """IT STAMPS THE COMMITTED, UNSTAMPED FILE AND NOTHING ELSE: run again on
    its own output, it finds no `VERSION = "0.0.0"` to replace, refuses, and
    leaves the file as it was."""
    workflow = release()
    done, copies = write_stamp(workflow, tmp_path / "first",
                               RELEASES["the-code-leg-s-v1.1.0"])
    assert done.returncode == 0, transcript(done)
    stamped_text = copies[0].read_bytes()
    again, more = write_stamp(workflow, tmp_path / "again",
                              dict(RELEASES["the-code-leg-s-v1.1.0"],
                                   VERSION="1.1.1", TAG="v1.1.1"),
                              [stamped_text, stamped_text])
    assert again.returncode != 0, transcript(again)
    assert [copy.read_bytes() for copy in more] == [stamped_text] * 2


def a_stamp_the_writer_refuses(which: str) -> bytes:
    """The committed stamp made into one the writer must refuse: already
    stamped, with a `TAG = ""` written twice, or with no `DIGEST = ""`."""
    text = STAMP.read_text(encoding="utf-8")
    if which == "already-stamped":
        return stamped(text, RELEASES["the-code-leg-s-v1.1.0"]).encode("utf-8")
    lines = text.split("\n")
    if which == "a-line-twice":
        lines.insert(lines.index('TAG = ""'), 'TAG = ""')
    else:
        lines.remove('DIGEST = ""')
    return "\n".join(lines).encode("utf-8")


@NEEDS_UPSTREAM
@pytest.mark.parametrize("which", ["a-line-twice", "a-line-missing"])
def test_release_stamp_writer_refuses_a_file_that_is_not_the_committed_stamp(
        tmp_path, which):
    """EACH COMMITTED LINE EXACTLY ONCE (contracts/stamp.md, "A count other
    than one refuses"): a `TAG = ""` written twice, or a `DIGEST = ""` that
    is not there, is refused, and neither file is written."""
    text = a_stamp_the_writer_refuses(which)
    done, copies = write_stamp(release(), tmp_path,
                               RELEASES["the-code-leg-s-v1.1.0"], [text, text])
    assert done.returncode != 0, transcript(done)
    assert [copy.read_bytes() for copy in copies] == [text, text]


@NEEDS_UPSTREAM
@pytest.mark.parametrize("which", ["already-stamped", "a-line-twice",
                                   "a-line-missing"])
def test_release_stamp_writer_writes_neither_copy_until_both_are_checked(
        tmp_path, which):
    """BOTH ARE STAMPED AND CHECKED BEFORE EITHER IS WRITTEN (release.yml's
    step 10, after contracts/stamp.md's "Checks before writing"): the
    committed stamp as the first copy and one the writer refuses as the
    second, and the writer refuses with both copies as they were. A writer
    that wrote each copy as it checked it would leave the first extraction
    stamped and the second not."""
    texts = [STAMP.read_bytes(), a_stamp_the_writer_refuses(which)]
    done, copies = write_stamp(release(), tmp_path,
                               RELEASES["the-code-leg-s-v1.1.0"], texts)
    assert done.returncode != 0, transcript(done)
    assert [copy.read_bytes() for copy in copies] == texts, (
        "the writer refused the second copy and wrote the first anyway")


#: A FILESYSTEM THAT DOES NOT KEEP WHAT WAS WRITTEN: the heredoc at `argv[1]`
#: runs as `python3 -` runs it, with the rest of argv as its own, except that
#: a file read again after this run wrote it comes back one character short.
LOSSY_READ_BACK = r'''
import builtins, io, sys
code, sys.argv = sys.argv[1], ["-", *sys.argv[2:]]
real_open, written = builtins.open, set()


def lossy_open(path, mode="r", *args, **kwargs):
    if "w" in mode:
        written.add(str(path))
        return real_open(path, mode, *args, **kwargs)
    handle = real_open(path, mode, *args, **kwargs)
    if str(path) not in written:
        return handle
    with handle:
        return io.StringIO(handle.read()[:-1])


builtins.open = lossy_open
with real_open(code, encoding="utf-8") as handle:
    source = handle.read()
exec(compile(source, "<stdin>", "exec"), {"__name__": "__main__"})
'''


@NEEDS_UPSTREAM
def test_release_stamp_writer_reads_each_copy_back_and_refuses_one_that_is_not_what_it_wrote(
        tmp_path):
    """AFTER WRITING, EACH COPY IS READ AGAIN (contracts/stamp.md, "After
    writing"): on a filesystem that comes back one character short of what
    was written, the writer refuses, naming the copy, rather than build from
    a stamp it cannot vouch for."""
    copies = [tmp_path / side / "src" / "openrepotools" / "_release.py" for side in "ab"]
    for copy in copies:
        copy.parent.mkdir(parents=True)
        copy.write_bytes(STAMP.read_bytes())
    work = tmp_path / "run"
    work.mkdir()
    (work / "heredoc.py").write_text(
        heredoc(run_text(named(release(), "build", STAMP_STEP))), encoding="utf-8")
    (work / "lossy.py").write_text(LOSSY_READ_BACK, encoding="utf-8")
    env = clean_environ(work / "home")
    env["PYTHONUTF8"] = "1"
    env.update(release_values(RELEASES["the-code-leg-s-v1.1.0"]))
    done = subprocess.run([sys.executable, "-I", str(work / "lossy.py"),
                           str(work / "heredoc.py"), *map(str, copies)],
                          capture_output=True, text=True, check=False,
                          stdin=subprocess.DEVNULL, env=env, cwd=str(work),
                          timeout=STEP_TIMEOUT)
    assert done.returncode != 0, transcript(done)
    assert f"::error::{copies[0]} reads back as" in done.stderr, transcript(done)


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", RELEASES)
def test_release_stamp_writer_step_as_github_runs_it_stamps_the_run_s_repository(
        tmp_path, which):
    """STEP 10, THE WHOLE STEP, RUN AS GITHUB RUNS IT (contracts/stamp.md,
    "Input"): its bash sets `TAG`, `COMMIT` and `REPOSITORY` from `$VERSION`,
    `$GITHUB_SHA` and `$GITHUB_REPOSITORY`, and its heredoc writes them, so
    both extractions' stamps name the run's own repository, in this
    repository, in the code leg and in a fork alike, and nothing the script
    sets after its `export` replaces it."""
    release_ = RELEASES[which]
    workflow = release()
    trees = [tmp_path / "a" / "openRepoTools",
             tmp_path / "b" / "elsewhere" / f"v{release_['VERSION']}-src"]
    copies = [tree / "src" / "openrepotools" / "_release.py" for tree in trees]
    for copy in copies:
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(STAMP.read_bytes())
    values = {"VERSION": release_["VERSION"], "GITHUB_SHA": release_["COMMIT"],
              "GITHUB_REPOSITORY": release_["REPOSITORY"],
              "DIGEST": release_["DIGEST"], "TREE_A": str(trees[0]),
              "TREE_B": str(trees[1])}
    runner = Runner(tmp_path / "work", workflow, "build", values)
    done = runner.run(named(workflow, "build", STAMP_STEP))
    assert done.returncode == 0, transcript(done)
    want = stamped(STAMP.read_text(encoding="utf-8"), release_).encode("utf-8")
    for copy in copies:
        assert copy.read_bytes() == want, (
            f"{copy} is not the committed stamp with {release_}:\n"
            f"{copy.read_text(encoding='utf-8')}")


#: THE DISPATCHED REF, AS GITHUB SETS `GITHUB_REF` AND `GITHUB_REF_NAME`: a
#: rehearsal on the version's release branch, and the version's own tag.
STAMP_REFS = {
    "a-branch": ("refs/heads/release/v1.1", "release/v1.1"),
    "the-version-s-tag": ("refs/tags/v1.1.0", "v1.1.0"),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", STAMP_REFS)
def test_release_stamp_writer_step_stamps_v_version_on_a_branch_and_on_the_tag(
        tmp_path, which):
    """THE WHOLE STEP, RUN WITH THE REF GITHUB SETS (contracts/stamp.md: a
    stamped `TAG` is `v$VERSION`): on a branch and on the version's tag
    alike, both extractions' stamps are the committed file with `TAG`
    `v1.1.0`, which comes from `$VERSION` and never from the ref's name."""
    ref, name = STAMP_REFS[which]
    release_ = RELEASES["the-code-leg-s-v1.1.0"]
    workflow = release()
    trees = [tmp_path / "a" / "openRepoTools", tmp_path / "b" / "elsewhere" / "v1.1.0-src"]
    copies = [tree / "src" / "openrepotools" / "_release.py" for tree in trees]
    for copy in copies:
        copy.parent.mkdir(parents=True)
        copy.write_bytes(STAMP.read_bytes())
    values = {"VERSION": release_["VERSION"], "GITHUB_SHA": release_["COMMIT"],
              "GITHUB_REPOSITORY": release_["REPOSITORY"],
              "DIGEST": release_["DIGEST"], "GITHUB_REF": ref,
              "GITHUB_REF_NAME": name, "TREE_A": str(trees[0]),
              "TREE_B": str(trees[1])}
    runner = Runner(tmp_path / "work", workflow, "build", values)
    done = runner.run(named(workflow, "build", STAMP_STEP))
    assert done.returncode == 0, transcript(done)
    want = stamped(STAMP.read_text(encoding="utf-8"), release_).encode("utf-8")
    for copy in copies:
        assert copy.read_bytes() == want, (
            f"on {ref}, {copy} is not the committed stamp with TAG "
            f"{release_['TAG']}:\n{copy.read_text(encoding='utf-8')}")


@NEEDS_UPSTREAM
def test_release_stamp_writer_step_stamps_both_extractions_with_the_run_s_repository():
    """STEP 10 (contracts/stamp.md, "Input"): the heredoc is handed the two
    extractions' `src/openrepotools/_release.py`, and `REPOSITORY` is the
    run's `$GITHUB_REPOSITORY`, taken from the environment and never pasted
    in by an expression."""
    step = named(release(), "build", STAMP_STEP)
    script = run_text(step)
    assert heredoc_line(script).count("src/openrepotools/_release.py") == 2, (
        heredoc_line(script))
    env = step.get("env") or {}
    assert ('REPOSITORY="$GITHUB_REPOSITORY"' in script
            or normal(env.get("REPOSITORY")) == "github.repository"), (
        "the stamp's REPOSITORY is not the run's GITHUB_REPOSITORY")


# --- the repository guard (FR-048) --------------------------------------------------

FINALS = ("1.1.0", "1.0.1", "2.10.30")
PRE_RELEASES = ("1.1.0rc1", "1.2.0rc0", "1.1.0rc12")

#: "Any other" repository, spelled every way GitHub never spells one of the
#: two: the guard compares exactly, so each fails closed.
OTHER_REPOSITORIES = {
    "lower-case": "opensoft/openrepotools",
    "lower-case-code-leg": "opensoft/openrepotools-code",
    "a-capital-owner": "Opensoft/openRepoTools-code",
    "a-capital-suffix": "opensoft/openRepoTools-Code",
    "a-fork-of-the-code-leg": "someone/openRepoTools-code",
    "a-fork-of-this-one": "someone/openRepoTools",
    "a-longer-name": "opensoft/openRepoTools-code-fork",
    "the-spec-leg": "opensoft/openRepoTools-spec",
    "the-model": "opensoft/openRepoShape",
    "dot-git": "opensoft/openRepoTools-code.git",
    "a-leading-space": " opensoft/openRepoTools-code",
    "a-trailing-space": "opensoft/openRepoTools-code ",
    "none": "",
}


def tag_of(version: str) -> str:
    return f"refs/tags/v{version}"


#: contracts/workflows.md's table, row by row: `(repository, ref, version,
#: (to-testpypi, to-pypi))`, and `None` where the build refuses. The last row
#: is a ref that is neither a tag nor a branch, which the guard refuses too.
GUARD_ROWS = (
    [pytest.param(CODE_LEG, tag_of(v), v, ("true", "true"),
                  id=f"code-leg-a-tag-final-{v}") for v in FINALS]
    + [pytest.param(CODE_LEG, tag_of(v), v, ("true", "false"),
                    id=f"code-leg-a-tag-rc-{v}") for v in PRE_RELEASES]
    + [pytest.param(THIS_REPOSITORY, tag_of(v), v, ("true", "false"),
                    id=f"this-repository-a-tag-rc-{v}") for v in PRE_RELEASES]
    + [pytest.param(THIS_REPOSITORY, tag_of(v), v, None,
                    id=f"this-repository-a-tag-final-{v}") for v in FINALS]
    + [pytest.param(repository, tag_of(v), v, None,
                    id=f"other-{name}-a-tag-{v}")
       for name, repository in OTHER_REPOSITORIES.items()
       for v in ("1.1.0", "1.1.0rc1")]
    + [pytest.param(repository, "refs/heads/l3-rehearsal-v1.1.0", v,
                    ("false", "false"), id=f"{name}-a-branch-{v}")
       for name, repository in (("code-leg", CODE_LEG),
                                ("this-repository", THIS_REPOSITORY),
                                ("a-fork", "someone/openRepoTools-code"),
                                ("lower-case", "opensoft/openrepotools"),
                                ("none", ""))
       for v in ("1.1.0rc1", "1.2.0")]
    + [pytest.param(CODE_LEG, ref, "1.1.0rc1", ("false", "false"),
                    id=f"code-leg-{ref_name(ref).replace('/', '-')}")
       for ref in ("refs/heads/main", "refs/heads/release/v1.1",
                   "refs/heads/feature/a-b")]
    + [pytest.param(CODE_LEG, "refs/pull/1/merge", "1.1.0", None,
                    id="code-leg-a-pull-request-ref")]
)


def guard_values(repository: str, ref: str, version: str) -> dict:
    """What contracts/workflows.md runs the guard with, and nothing else:
    `GITHUB_REPOSITORY`, `GITHUB_REF` and `VERSION` (and `GITHUB_OUTPUT`,
    which every run has)."""
    return {"GITHUB_REPOSITORY": repository, "GITHUB_REF": ref,
            "VERSION": version}


def assert_decided(done: subprocess.CompletedProcess, runner: Runner,
                   decision: Optional[Tuple[str, str]]) -> None:
    if decision is None:
        assert done.returncode != 0, f"the guard passed:\n{transcript(done)}"
        assert runner.decision() == {}, (
            f"a refused run recorded {runner.decision()}")
    else:
        assert done.returncode == 0, f"the guard refused:\n{transcript(done)}"
        assert runner.decision() == {"to-testpypi": [decision[0]],
                                     "to-pypi": [decision[1]]}, (
            f"recorded {runner.recorded()}")


@NEEDS_UPSTREAM
def test_release_guard_build_is_step_one_and_the_build_job_records_its_answer():
    """STEPS 1 AND 14: the guard is a `run:` block of the build, before the ref
    step and so before anything asks the forge, with no `if:`, and the build
    job's `to-testpypi` and `to-pypi` are that one step's outputs."""
    workflow = release()
    guard = guard_step(workflow)
    assert where(workflow, "build", guard) < where(
        workflow, "build", named(workflow, "build", REF_STEP))
    assert "if" not in guard


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("repository, ref, version, decision", GUARD_ROWS)
def test_release_guard_build_decides_by_the_table(tmp_path, repository, ref,
                                                  version, decision):
    """FR-048, ROW BY ROW: the code leg sends a final to both indexes and a
    pre-release to TestPyPI; this repository a pre-release to TestPyPI and a
    final nowhere, refused; any other repository is refused on a tag; a
    branch is the rehearsal everywhere, passing with nothing to upload; and a
    ref that is neither, a pull request's, is refused. The guard decides from
    those three variables alone and asks no forge."""
    workflow = release()
    runner = Runner(tmp_path, workflow, "build",
                    guard_values(repository, ref, version))
    done = runner.run(guard_step(workflow))
    assert_decided(done, runner, decision)
    assert runner.asked() == "", f"the guard asked:\n{runner.asked()}"


#: Versions no release carries, on a tag and on a branch alike: "the version
#: must still parse" (contracts/workflows.md, step 2). `<marker>` is a file
#: the version would make if any script ran it.
BAD_VERSIONS = {
    "empty": "", "two-numbers": "1.1", "four-numbers": "1.1.0.0",
    "a-leading-zero": "01.1.0", "a-leading-zero-minor": "1.01.0",
    "a-leading-zero-patch": "1.1.00", "a-v": "v1.1.0",
    "a-dash-rc": "1.1.0-rc1", "rc-without-a-number": "1.1.0rc",
    "rc-with-a-leading-zero": "1.1.0rc01", "upper-case-rc": "1.1.0RC1",
    "an-alpha": "1.1.0a1", "a-dev-release": "1.1.0rc1.dev0",
    "a-local-label": "1.1.0+local", "a-trailing-space": "1.1.0 ",
    "a-second-line": "1.1.0\n1.2.0", "the-unstamped-0.0.0": "0.0.0",
    "a-command-substitution": "1.1.0$(touch <marker>)",
    "a-backtick-command": "1.1.0`touch <marker>`",
}
GOOD_VERSIONS = ("1.1.0rc1", "1.1.0rc0", "0.1.0", "1.0.1", "10.20.30", "1.2.0",
                 "2.0.0rc3")


def run_through_the_guard(workflow: dict, runner: Runner
                          ) -> subprocess.CompletedProcess:
    """Every `run:` step of the build from the first through the guard, in
    order, stopping at the first that fails: the version check, wherever in
    step 1 it is, and the guard."""
    steps = steps_of(workflow, "build")
    done = None
    for step in steps[:where(workflow, "build", guard_step(workflow)) + 1]:
        if run_text(step):
            done = runner.run(step)
            if done.returncode != 0:
                break
    assert done is not None
    return done


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("ref_kind", ["a-tag", "a-branch"])
@pytest.mark.parametrize("which", BAD_VERSIONS)
def test_release_guard_build_refuses_a_version_no_release_carries(tmp_path, which,
                                                                  ref_kind):
    """STEP 1'S VERSION (FR-029): `X.Y.Z` with no leading zero and not
    `0.0.0`, or `X.Y.ZrcN`, and nothing else, on a tag and on a branch. Each
    other input is refused before anything is recorded, and none is run."""
    marker = tmp_path / "the-version-ran"
    version = BAD_VERSIONS[which].replace("<marker>", str(marker))
    ref = (tag_of(version) if ref_kind == "a-tag"
           else "refs/heads/l3-rehearsal-v1.1.0")
    workflow = release()
    runner = Runner(tmp_path / "work", workflow, "build",
                    guard_values(CODE_LEG, ref, version))
    done = run_through_the_guard(workflow, runner)
    assert done.returncode != 0, transcript(done)
    assert runner.decision() == {}, runner.recorded()
    assert not marker.exists(), "a step ran the version input"


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("version", GOOD_VERSIONS)
def test_release_guard_build_passes_every_version_a_release_carries_on_a_branch(
        tmp_path, version):
    """THE OTHER HALF: each version a release can carry passes step 1 on a
    branch of the code leg, recording the rehearsal's two `false`s."""
    workflow = release()
    runner = Runner(tmp_path, workflow, "build",
                    guard_values(CODE_LEG, "refs/heads/l3-rehearsal-v1.1.0",
                                 version))
    done = run_through_the_guard(workflow, runner)
    assert_decided(done, runner, ("false", "false"))


#: Each upload job's own guard (FR-048): `(repository, version, passes)`.
UPLOAD_GUARD_CASES = {
    "testpypi": (
        [(CODE_LEG, v, True) for v in FINALS + PRE_RELEASES]
        + [(THIS_REPOSITORY, v, True) for v in PRE_RELEASES]
        + [(THIS_REPOSITORY, v, False) for v in FINALS + ("1.1.0-rc1",)]
        + [(r, v, False) for r in OTHER_REPOSITORIES.values()
           for v in ("1.1.0", "1.1.0rc1")]),
    "pypi": (
        [(CODE_LEG, v, True) for v in FINALS]
        + [(CODE_LEG, v, False) for v in PRE_RELEASES + (
            "1.1", "1.1.0-rc1", "1.1.0.0", "v1.1.0", "1.1.0rc1.dev0", "")]
        + [(THIS_REPOSITORY, v, False) for v in FINALS + PRE_RELEASES]
        + [(r, v, False) for r in OTHER_REPOSITORIES.values()
           for v in ("1.1.0", "1.1.0rc1")]),
}


def upload_guard_params(name: str) -> list:
    return [pytest.param(repository, version, passes,
                         id=f"{repository or 'none'}-{version or 'empty'}-"
                            f"{'passes' if passes else 'refused'}")
            for repository, version, passes in UPLOAD_GUARD_CASES[name]]


def run_upload_guard(tmp_path: Path, name: str, repository: str,
                     version: str, ref: Optional[str] = None
                     ) -> subprocess.CompletedProcess:
    """Job `name`'s first step, its guard, on `ref`: the version's own tag
    `refs/tags/v<version>` unless the case names another."""
    workflow = release()
    first = steps_of(workflow, name)[0]
    assert run_text(first) and "uses" not in first, (
        f"the {name} job's first step is {label(first)!r}, not its guard")
    runner = Runner(tmp_path, workflow, name,
                    guard_values(repository,
                                 tag_of(version) if ref is None else ref,
                                 version))
    return runner.run(first)


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("repository, version, passes",
                         upload_guard_params("testpypi"))
def test_release_guard_upload_testpypi_s_first_step(tmp_path, repository,
                                                     version, passes):
    """`testpypi`'s FIRST STEP, ON ITS OWN (FR-048): it passes any version in
    the code leg and a pre-release in this repository, and refuses a final
    here and every version in any other repository."""
    done = run_upload_guard(tmp_path, "testpypi", repository, version)
    assert (done.returncode == 0) == passes, transcript(done)


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("repository, version, passes",
                         upload_guard_params("pypi"))
def test_release_guard_upload_pypi_s_first_step(tmp_path, repository, version,
                                                passes):
    """`pypi`'s FIRST STEP (FR-031, FR-048): it refuses everything but a final
    `X.Y.Z` in `opensoft/openRepoTools-code`, so in this repository it
    refuses outright, in case its condition is ever loosened."""
    done = run_upload_guard(tmp_path, "pypi", repository, version)
    assert (done.returncode == 0) == passes, transcript(done)


#: What each upload job's guard passes on the version's own tag:
#: `(job, repository, version)`.
UPLOAD_GUARD_PASSES = [("testpypi", CODE_LEG, "1.1.0"),
                       ("testpypi", CODE_LEG, "1.1.0rc1"),
                       ("testpypi", THIS_REPOSITORY, "1.1.0rc1"),
                       ("pypi", CODE_LEG, "1.1.0")]

#: Every ref but `refs/tags/v<version>`, `<version>` the case's own: an
#: upload is made from that tag alone.
NOT_THE_VERSION_S_TAG = {
    "a-branch": "refs/heads/main",
    "the-rehearsal-branch": "refs/heads/l3-rehearsal-v1.1.0",
    "a-branch-named-as-the-tag": "refs/heads/v<version>",
    "another-version-s-tag": "refs/tags/v1.0.1",
    "the-tag-without-its-v": "refs/tags/<version>",
    "a-pull-request": "refs/pull/7/merge",
    "no-ref-at-all": "",
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", NOT_THE_VERSION_S_TAG)
@pytest.mark.parametrize("name, repository, version", [
    pytest.param(*case, id=f"{case[0]}-{case[1]}-{case[2]}")
    for case in UPLOAD_GUARD_PASSES])
def test_release_guard_upload_refuses_every_ref_but_the_version_s_own_tag(
        tmp_path, name, repository, version, which):
    """EACH UPLOAD JOB'S GUARD READS THE REF (FR-048: "each from its own tag
    v<version>"), in case the job's `if:` is ever loosened. A repository and
    a version the guard passes on `refs/tags/v<version>` are refused on a
    branch, on a branch named as the tag, on another version's tag, on the
    tag without its `v`, on a pull request's ref and on no ref at all."""
    ref = NOT_THE_VERSION_S_TAG[which].replace("<version>", version)
    own = run_upload_guard(tmp_path / "own", name, repository, version)
    assert own.returncode == 0, transcript(own)
    done = run_upload_guard(tmp_path / "other", name, repository, version, ref)
    assert done.returncode != 0, f"{name}'s guard passed on {ref!r}:\n{transcript(done)}"


# --- the jobs, their grants and their conditions ---------------------------------------

@NEEDS_UPSTREAM
def test_release_upload_the_jobs_are_build_testpypi_install_and_pypi():
    assert sorted(release()["jobs"]) == sorted(JOBS)


@NEEDS_UPSTREAM
def test_release_upload_each_job_grants_exactly_its_own_permissions():
    """ONLY THE TWO UPLOAD JOBS MINT AN IDENTITY TOKEN (FR-031): `testpypi` and
    `pypi` hold exactly `id-token: write`, `actions: read` and `contents:
    read`; `build` exactly `contents: read` and `actions: read`; `install`
    exactly `contents: read`."""
    workflow = release()
    granted = {name: job(workflow, name).get("permissions") for name in JOBS}
    assert granted == PERMISSIONS, granted


@NEEDS_UPSTREAM
def test_release_upload_each_upload_runs_in_its_own_environment_and_no_other_job_does():
    workflow = release()
    for name in JOBS:
        environment = job(workflow, name).get("environment")
        if name in UPLOADS:
            environment_name = (environment.get("name")
                                if isinstance(environment, dict) else environment)
            assert environment_name == UPLOADS[name], (name, environment)
        else:
            assert environment is None, (name, environment)


#: The parts a condition may hold beside the two contracts/workflows.md names.
STATUS_ATOMS = ("success()", "!cancelled()")
ATOM_REF = re.compile(r"startsWith\(github\.ref, '([^']*)'\)")
ATOM_OUTPUT = re.compile(r"needs\.build\.outputs(?:\.([A-Za-z0-9_-]+)|"
                         r"\['([A-Za-z0-9_-]+)'\]) == '([^']*)'")
ATOM_RESULT = re.compile(r"needs\.([A-Za-z0-9_-]+)\.result == 'success'")


def conjuncts(expression, name: str) -> List[str]:
    """`expression`'s `&&` parts, each with its outer parentheses off. A
    condition with an `||` can run where one of its parts says no, so it is
    not read."""
    text = normal(expression)
    if not text:
        pytest.fail(f"the {name} job has no `if:`", pytrace=False)
    if "||" in text:
        pytest.fail(f"the {name} job's `if:` holds `||`: {text}", pytrace=False)
    parts = []
    for part in text.split("&&"):
        part = part.strip()
        while (part.startswith("(") and part.endswith(")")
               and part[1:-1].count("(") == part[1:-1].count(")")):
            part = part[1:-1].strip()
        parts.append(part)
    return parts


def runs_when(workflow: dict, name: str, ref: str, outputs: dict) -> bool:
    """Whether job `name` runs on `ref` with the build's `outputs`, every job
    it needs having succeeded."""
    verdict = True
    for atom in conjuncts(job(workflow, name).get("if"), name):
        by_ref, by_output = ATOM_REF.fullmatch(atom), ATOM_OUTPUT.fullmatch(atom)
        if by_ref:
            verdict = verdict and ref.startswith(by_ref.group(1))
        elif by_output:
            key = by_output.group(1) or by_output.group(2)
            verdict = verdict and outputs.get(key, "") == by_output.group(3)
        elif not (ATOM_RESULT.fullmatch(atom) or atom in STATUS_ATOMS):
            pytest.fail(f"the {name} job's `if:` holds {atom!r}, which can run "
                        "it without the build's success or the guard's record",
                        pytrace=False)
    return verdict


#: `(ref, the build's record, testpypi runs, pypi runs)`.
UPLOAD_SCENARIOS = {
    "a-final-from-the-code-leg": ("refs/tags/v1.1.0",
                                  {"to-testpypi": "true", "to-pypi": "true"},
                                  True, True),
    "an-rc-rehearsal": ("refs/tags/v1.1.0rc1",
                        {"to-testpypi": "true", "to-pypi": "false"}, True, False),
    "a-branch-rehearsal": ("refs/heads/l3-rehearsal-v1.1.0",
                           {"to-testpypi": "false", "to-pypi": "false"},
                           False, False),
    "a-branch-whatever-the-record-says": ("refs/heads/l3-rehearsal-v1.1.0",
                                          {"to-testpypi": "true",
                                           "to-pypi": "true"}, False, False),
    "a-tag-the-record-sends-nowhere": ("refs/tags/v1.1.0",
                                       {"to-testpypi": "false",
                                        "to-pypi": "false"}, False, False),
    "a-tag-with-no-record": ("refs/tags/v1.1.0", {}, False, False),
    "a-tag-that-is-no-v-tag": ("refs/tags/1.1.0",
                               {"to-testpypi": "true", "to-pypi": "true"},
                               False, False),
}


@NEEDS_UPSTREAM
@pytest.mark.parametrize("which", UPLOAD_SCENARIOS)
def test_release_upload_testpypi_reads_to_testpypi_and_pypi_reads_to_pypi(which):
    """THE TWO CONDITIONS (FR-031, FR-048): each upload job runs only on a
    `refs/tags/v*` tag, after the jobs it needs succeeded, and only where the
    build's record says so: `testpypi` on `to-testpypi`, `pypi` on `to-pypi`.
    So in an rc rehearsal `pypi` is skipped and never asks for its approval,
    and a branch uploads nothing whatever the record says."""
    ref, outputs, testpypi, pypi = UPLOAD_SCENARIOS[which]
    workflow = release()
    assert runs_when(workflow, "testpypi", ref, outputs) is testpypi
    assert runs_when(workflow, "pypi", ref, outputs) is pypi


@NEEDS_UPSTREAM
def test_release_upload_pypi_waits_for_testpypi_and_every_install_leg():
    """The order is TestPyPI, the install check, then PyPI (FR-031)."""
    workflow = release()
    assert set(as_list(job(workflow, "testpypi").get("needs"))) == {"build"}
    assert set(as_list(job(workflow, "pypi").get("needs"))) == {
        "build", "testpypi", "install"}


#: EACH UPLOAD JOB'S CHECK OF THE ARTIFACT AGAINST THE BUILD'S RECORD, the
#: model's own step: found by its name, and holding the one command that
#: compares the file's sha256 with the recorded one. No bare "sha256" will
#: do, because the index steps read `["sha256"]` from the JSON too.
DIST_STEP = "dist holds the wheel the build job verified, and nothing else"
DIST_SHA256 = 'echo "$WHEEL_SHA256  dist/$WHEEL" | sha256sum --strict -c -'


def before_publish_checks() -> list:
    """What each upload job reads before the upload, by what its script
    asks: the artifact, its sha256 (the dist step, by its name and its
    command), the environment's rules and this run's approval again, the tag
    again, and the index's JSON for the version."""
    return [
        ("the build's artifact",
         lambda s: str(s.get("uses", "")).startswith("actions/download-artifact@")),
        ("the wheel's sha256 against the build's",
         lambda s: (str(s.get("name", "")) == DIST_STEP
                    and DIST_SHA256 in commands(run_text(s)))),
        ("the environment's rules, again",
         lambda s: "deployment-branch-policies" in run_text(s)),
        ("this run's approval", lambda s: "approvals" in run_text(s)),
        ("the tag, again", lambda s: re.search(r"git/refs?/tags/", run_text(s))),
        ("the index's JSON for the version", lambda s: "/json" in run_text(s)),
    ]


@NEEDS_UPSTREAM
@pytest.mark.parametrize("name", sorted(UPLOADS))
def test_release_upload_each_upload_job_checks_publishes_and_checks_again(name):
    """EACH UPLOAD JOB, IN ITS ORDER (contracts/workflows.md): its guard
    first; then the artifact and its sha256, the environment's rules, this
    run's approval and the tag read again, and an index that lists no file of
    the version; then the one upload with the pinned action, TestPyPI's to
    its legacy URL and PyPI's to the default index; then the index read again
    for exactly the recorded wheel. No step is conditional, none carries on
    past a failure, and nothing is installed by pip."""
    workflow = release()
    steps = steps_of(workflow, name)
    publishes = [i for i, s in enumerate(steps)
                 if str(s.get("uses", "")).startswith("pypa/gh-action-pypi-publish@")]
    assert len(publishes) == 1, f"{name} uploads {len(publishes)} times"
    at = publishes[0]
    publish = steps[at]
    assert publish["uses"] == PUBLISH, publish["uses"]
    options = publish.get("with") or {}
    if name == "testpypi":
        assert options.get("repository-url") == TESTPYPI_LEGACY, options
    else:
        assert "repository-url" not in options, options
    before = steps[1:at]
    for what, asks in before_publish_checks():
        assert [s for s in before if asks(s)], (
            f"{name} uploads without reading {what} first: "
            f"{[label(s) for s in steps]}")
    assert [s for s in steps[at + 1:] if "/json" in run_text(s)], (
        f"{name} does not read the index again after the upload")
    for step in steps:
        assert "if" not in step and "continue-on-error" not in step, label(step)
    assert "continue-on-error" not in job(workflow, name)
    assert pip_installs(workflow, name) == []


@NEEDS_UPSTREAM
def test_release_upload_both_jobs_run_the_same_checks_after_their_guards():
    """"THE SAME DOWNLOAD, SHA256 CHECK, RE-READS AND EMPTY-INDEX CHECK"
    (contracts/workflows.md): after each job's own guard, the two jobs' steps
    are one list, script for script, and the index each reads comes from its
    own settings. Nothing in `pypi` names TestPyPI."""
    workflow = release()
    mine, theirs = steps_of(workflow, "testpypi")[1:], steps_of(workflow, "pypi")[1:]
    assert [label(s) for s in mine] == [label(s) for s in theirs]
    for a, b in zip(mine, theirs):
        assert a.get("run") == b.get("run"), label(a)
    assert "test.pypi.org" not in json.dumps(job(workflow, "pypi"))


# --- the dist step, run ---------------------------------------------------------------

#: The bytes the build recorded, and other bytes under the same name.
RECORDED_WHEEL = b"PK\x03\x04 the wheel the build job verified\n"
OTHER_WHEEL = b"PK\x03\x04 another file under the wheel's name\n"

#: WHERE A JOB TAKES THE BUILD'S WHEEL, each upload job's `dist/` and the
#: install check's wheel directory: `(the files there, whether the step that
#: checks them passes)`.
WHEEL_DIGEST_CASES = {
    "the-recorded-wheel": ({"<wheel>": RECORDED_WHEEL}, True),
    "other-bytes-under-its-name": ({"<wheel>": OTHER_WHEEL}, False),
    "the-recorded-wheel-and-another-file": (
        {"<wheel>": RECORDED_WHEEL, "openrepotools-1.0.0-py3-none-any.whl":
         RECORDED_WHEEL}, False),
    "another-name-at-the-recorded-digest": (
        {"openrepotools-1.0.0-py3-none-any.whl": RECORDED_WHEEL}, False),
    "nothing": ({}, False),
}


def a_wheel_directory(directory: Path, files: dict, wheel: str) -> None:
    """`directory`, holding `files`, `<wheel>` standing for `wheel`."""
    directory.mkdir(parents=True)
    for name, data in files.items():
        (directory / name.replace("<wheel>", wheel)).write_bytes(data)


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.skipif(shutil.which("sha256sum") is None,
                    reason="the dist step runs GNU's sha256sum")
@pytest.mark.parametrize("which", WHEEL_DIGEST_CASES)
@pytest.mark.parametrize("name", sorted(UPLOADS))
def test_release_upload_the_dist_step_passes_the_verified_wheel_alone(tmp_path, name, which):
    """THE WHOLE DIST STEP, RUN in each upload job (FR-031: the bytes the
    build verified, and nothing else): `dist/` holding the one file named
    `$WHEEL`, whose sha256 is `$WHEEL_SHA256`, passes; other bytes under
    that name, another file beside it, another name, and an empty `dist/`
    are each refused."""
    files, passes = WHEEL_DIGEST_CASES[which]
    wheel = "openrepotools-1.1.0-py3-none-any.whl"
    workspace = tmp_path / "workspace"
    a_wheel_directory(workspace / "dist", files, wheel)
    values = {"WHEEL": wheel, "WHEEL_SHA256": hashlib.sha256(RECORDED_WHEEL).hexdigest()}
    workflow = release()
    runner = Runner(tmp_path / "work", workflow, name, values)
    done = runner.run(named(workflow, name, DIST_STEP), cwd=workspace)
    assert (done.returncode == 0) == passes, transcript(done)
    if passes:
        assert done.stdout.strip() == f"dist/{wheel}: OK", transcript(done)


# --- the re-checks at use time, run against a forge ------------------------------------

#: The upload jobs' two re-checks, by their names.
APPROVAL_STEP = "this environment still asks a reviewer and admits only the tags v*"
TAG_AGAIN_STEP = "the tag v<version> still names this commit"
RUN_ID = "4242"


def approvals(*given: Tuple[str, str]) -> list:
    """`GET repos/<r>/actions/runs/<id>/approvals`: one review per
    `(environment, state)`, by brettheap."""
    return [{"state": state, "comment": "", "user": {"login": "brettheap"},
             "environments": [{"name": environment}]} for environment, state in given]


#: THE APPROVAL RE-CHECK, RUN: `(the changes to the job's own environment,
#: this run's approvals, with "<own>" and "<other>" for the two
#: environments, or None where they cannot be read; whether the step
#: passes)`.
APPROVAL_CASES = {
    "approved-by-its-reviewer": ({}, [("<own>", "approved")], True),
    "no-approval": ({}, [], False),
    "approved-for-the-other-environment-alone": ({}, [("<other>", "approved")], False),
    "rejected": ({}, [("<own>", "rejected")], False),
    "the-approvals-cannot-be-read": ({}, None, False),
    "no-reviewer-now": ({"reviewers": ()}, [("<own>", "approved")], False),
    "a-branch-rule-now": ({"rules": [("tag", "v*"), ("branch", "main")]},
                          [("<own>", "approved")], False),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", APPROVAL_CASES)
@pytest.mark.parametrize("name", sorted(UPLOADS))
def test_release_upload_the_approval_recheck_refuses_a_run_its_environment_did_not_approve(
        tmp_path, name, which):
    """AT USE TIME, RUN under a forge, in each upload job: its environment
    still names a reviewer and admits the tags `v*` alone, and this run's
    deployment to it was approved, so it passes; no approval, an approval
    of the other environment alone, a rejection, approvals that cannot be
    read, and an environment that lost its reviewer or gained a branch rule
    while the run waited are each refused."""
    changes, given, passes = APPROVAL_CASES[which]
    own, other = UPLOADS[name], ("pypi" if name == "testpypi" else "testpypi")
    answers = environment_answers(THIS_REPOSITORY, {own: changes})
    if given is not None:
        answers[f"repos/{THIS_REPOSITORY}/actions/runs/{RUN_ID}/approvals"] = approvals(
            *[(own if env == "<own>" else other, state) for env, state in given])
    forge, values = api_forge(tmp_path, answers)
    values.update(GITHUB_REPOSITORY=THIS_REPOSITORY, GITHUB_RUN_ID=RUN_ID)
    workflow = release()
    runner = Runner(tmp_path / "work", workflow, name, values, forge)
    done = runner.run(named(workflow, name, APPROVAL_STEP))
    assert (done.returncode == 0) == passes, transcript(done)
    if passes:
        assert done.stdout.strip() == (f"{own}: a reviewer, the tags v* alone, and "
                                       "approved by brettheap"), transcript(done)
    else:
        assert "::error::" in done.stderr, transcript(done)


#: THE TAG RE-CHECK, RUN: `(what the forge says of v1.1.0's tag object,
#: whether the step passes)`, the run's commit being `c` * 40.
TAG_AGAIN_CASES = {
    "it-still-names-this-commit": ({}, True),
    "it-was-moved-to-another-commit": ({"names": "d" * 40}, False),
    "it-was-deleted": (None, False),
    "it-is-a-lightweight-tag-now": ({"lightweight": True}, False),
    "its-object-names-a-tag": ({"type": "tag"}, False),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", TAG_AGAIN_CASES)
@pytest.mark.parametrize("name", sorted(UPLOADS))
def test_release_upload_the_tag_recheck_refuses_a_tag_moved_while_the_run_waited(
        tmp_path, name, which):
    """RIGHT BEFORE THE UPLOAD, RUN under a forge, in each upload job: the
    annotated tag `v$VERSION` still names the run's commit, so it passes; a
    tag moved to another commit, deleted, made lightweight, or whose object
    names a tag is refused, since an upload cannot be taken back."""
    lie, passes = TAG_AGAIN_CASES[which]
    commit = "c" * 40
    answers = ({} if lie is None
               else annotated_tag(CODE_LEG, "v1.1.0", "7a" * 20, commit, **lie))
    forge, values = api_forge(tmp_path, answers)
    values.update(GITHUB_REPOSITORY=CODE_LEG, GITHUB_SHA=commit, VERSION="1.1.0")
    workflow = release()
    runner = Runner(tmp_path / "work", workflow, name, values, forge)
    done = runner.run(named(workflow, name, TAG_AGAIN_STEP))
    assert (done.returncode == 0) == passes, transcript(done)
    if passes:
        assert done.stdout.strip() == f"v1.1.0 still names {commit}", transcript(done)
    else:
        assert "::error::" in done.stdout, transcript(done)


# --- the index checks, run against a fake index ----------------------------------------

#: The two index checks around each upload, by their names, and the JSON API
#: each upload job reads.
EMPTY_INDEX_STEP = "the index holds no file of this version but the verified wheel"
SERVED_STEP = "the index serves exactly the verified wheel"
JSON_BASES = {"testpypi": "https://test.pypi.org/pypi/openrepotools/",
              "pypi": "https://pypi.org/pypi/openrepotools/"}

#: The verified wheel, its digest, and what else an index can hold.
INDEX_VERSION = "1.1.0"
INDEX_WHEEL = f"openrepotools-{INDEX_VERSION}-py3-none-any.whl"
INDEX_SDIST = f"openrepotools-{INDEX_VERSION}.tar.gz"
VERIFIED = "5e" * 32
ANOTHER_DIGEST = "a7" * 32
SERVED = (200, [(INDEX_WHEEL, VERIFIED, False)])
NOT_YET = (404, [])
DROPPED = (None, [])

#: THE CLOCK, the one other thing faked: `time.sleep` writes down what it was
#: asked and returns at once, so 20 reads 15 seconds apart take no time. It is
#: a `sitecustomize` on the step's PYTHONPATH, so the step's script runs as
#: it is written.
CLOCK = '''import os, time


def sleep(seconds, _log=os.environ["FAKE_CLOCK_LOG"]):
    with open(_log, "a", encoding="utf-8") as log:
        log.write(f"{seconds}\\n")


time.sleep = sleep
'''


class FakeIndex:
    """AN INDEX'S JSON API ON 127.0.0.1: the `n`th read gets `answers[n]`,
    and every read after the last answer gets the last again. Each answer is
    `(status, files)`, a file `(filename, sha256, yanked)`; the status `None`
    closes the connection with no response at all, a connection error with
    no HTTP status. Every read's path is written down in `reads`."""

    def __init__(self, answers: list) -> None:
        self.answers, self.reads = list(answers), []
        index = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                status, files = index.answers[min(len(index.reads),
                                                  len(index.answers) - 1)]
                index.reads.append(self.path)
                if status is None:
                    self.close_connection = True
                    return
                body = json.dumps(
                    {"info": {"name": "openrepotools"},
                     "urls": [{"filename": name, "digests": {"sha256": digest},
                               "yanked": yanked}
                              for name, digest, yanked in files]}
                    if status == 200 else {"message": f"HTTP {status}"}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.base = (f"http://127.0.0.1:{self.server.server_address[1]}"
                     "/pypi/openrepotools/")
        # a short poll, so that `shutdown` returns at once
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01}, daemon=True)

    def __enter__(self) -> "FakeIndex":
        self.thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def run_index_step(tmp_path: Path, name: str, prefix: str, answers: list
                   ) -> Tuple[subprocess.CompletedProcess, List[str], List[str]]:
    """Job `name`'s step `prefix`, run under the Runner with the job's own
    `INDEX`, the build's record and `JSON_BASE` the fake index's. Returns the
    run, the paths read, and the sleeps asked for."""
    workflow = release()
    assert (job(workflow, name).get("env") or {}).get("JSON_BASE") == JSON_BASES[name], (
        f"the {name} job reads {job(workflow, name).get('env')}")
    clock = tmp_path / "clock"
    clock.mkdir()
    (clock / "sitecustomize.py").write_text(CLOCK, encoding="utf-8")
    log = tmp_path / "clock.log"
    with FakeIndex(answers) as index:
        values = {"VERSION": INDEX_VERSION, "WHEEL": INDEX_WHEEL,
                  "WHEEL_SHA256": VERIFIED, "JSON_BASE": index.base,
                  "no_proxy": "*", "NO_PROXY": "*", "PYTHONPATH": str(clock),
                  "PYTHONDONTWRITEBYTECODE": "1", "FAKE_CLOCK_LOG": str(log)}
        runner = Runner(tmp_path / "work", workflow, name, values)
        done = runner.run(named(workflow, name, prefix))
        reads = list(index.reads)
    sleeps = log.read_text(encoding="utf-8").split() if log.exists() else []
    return done, reads, sleeps


#: BEFORE THE UPLOAD (FR-031, the lead's ruling, design.md Open Questions
#: item 15): `(what the index answers, whether the step passes)`. A 404 is a
#: version with no file yet, and a version listed with no file holds no file
#: either; the verified wheel at its digest, not yanked, is a re-run after an
#: upload that went through. Every other file refuses, and so does an index
#: that answers with an error.
EMPTY_INDEX_CASES = {
    "no-file-of-the-version-yet": (NOT_YET, True),
    "the-verified-wheel-at-its-digest": (SERVED, True),
    "the-version-listed-with-no-file": ((200, []), True),
    "the-verified-wheel-yanked": ((200, [(INDEX_WHEEL, VERIFIED, True)]), False),
    "the-wheel-s-name-at-another-digest": (
        (200, [(INDEX_WHEEL, ANOTHER_DIGEST, False)]), False),
    "another-file-beside-the-verified-wheel": (
        (200, [(INDEX_WHEEL, VERIFIED, False),
               (INDEX_SDIST, ANOTHER_DIGEST, False)]), False),
    "another-file-alone": ((200, [(INDEX_SDIST, ANOTHER_DIGEST, False)]), False),
    "an-index-error": ((503, []), False),
    "a-refusal-other-than-404": ((403, []), False),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", EMPTY_INDEX_CASES)
@pytest.mark.parametrize("name", sorted(UPLOADS))
def test_release_upload_the_empty_index_check_passes_no_file_or_the_verified_wheel_alone(
        tmp_path, name, which):
    """THE EMPTY-INDEX CHECK, RUN against a fake index, in each upload job:
    it reads the version's JSON once, passes a 404, a version with no file
    and the verified wheel already there at its digest, not yanked, and
    refuses the wheel yanked, the wheel's name at another digest, any other
    file, and an index that answers with an error."""
    answer, passes = EMPTY_INDEX_CASES[which]
    done, reads, _ = run_index_step(tmp_path, name, EMPTY_INDEX_STEP, [answer])
    assert (done.returncode == 0) == passes, transcript(done)
    assert reads == [f"/pypi/openrepotools/{INDEX_VERSION}/json"], reads
    if not passes and answer[0] == 200:
        assert "::error::" in done.stdout + done.stderr, transcript(done)


#: AFTER THE UPLOAD: `(what the index answers, read by read, whether the step
#: passes, how many reads it makes)`. It reads until the index serves exactly
#: the verified wheel, through a 404, an empty listing, a server error or a
#: connection closed with no response, up to 20 reads, and refuses the wheel
#: yanked, any other file and a client error at once.
SERVED_CASES = {
    "served-at-the-first-read": ([SERVED], True, 1),
    "not-yet-then-served": ([NOT_YET, SERVED], True, 2),
    "an-empty-listing-then-served": ([(200, []), SERVED], True, 2),
    "a-server-error-then-served": ([(503, []), SERVED], True, 2),
    "a-connection-error-then-served": ([DROPPED, SERVED], True, 2),
    "served-at-the-twentieth-read": ([NOT_YET] * 19 + [SERVED], True, 20),
    "served-only-after-twenty-reads": ([NOT_YET] * 20 + [SERVED], False, 20),
    "another-file-beside-it-every-time": (
        [(200, [(INDEX_WHEEL, VERIFIED, False),
                (INDEX_SDIST, ANOTHER_DIGEST, False)])], False, 20),
    "another-digest-every-time": (
        [(200, [(INDEX_WHEEL, ANOTHER_DIGEST, False)])], False, 20),
    "served-yanked": ([(200, [(INDEX_WHEEL, VERIFIED, True)])], False, 1),
    "a-refusal-other-than-404": ([(403, [])], False, 1),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", SERVED_CASES)
@pytest.mark.parametrize("name", sorted(UPLOADS))
def test_release_upload_the_served_check_reads_until_the_verified_wheel_is_served(
        tmp_path, name, which):
    """THE SERVED-DIGEST CHECK, RUN against a fake index, in each upload job:
    it keeps reading, 15 seconds apart, up to 20 reads, through a read that
    fails with no HTTP status, until the index serves exactly the verified
    wheel, and passes then; it refuses an index that never does, the wheel
    yanked, and a client error."""
    answers, passes, count = SERVED_CASES[which]
    done, reads, sleeps = run_index_step(tmp_path, name, SERVED_STEP, answers)
    assert (done.returncode == 0) == passes, transcript(done)
    assert reads == [f"/pypi/openrepotools/{INDEX_VERSION}/json"] * count, (
        f"{len(reads)} reads, not {count}: {reads}")
    assert set(sleeps) <= {"15"}, sleeps
    if passes:
        assert len(sleeps) == count - 1, sleeps


# --- the install check ---------------------------------------------------------------

def install_steps(workflow: dict) -> list:
    return steps_of(workflow, "install")


def condition_kind(condition) -> Optional[str]:
    text = normal(condition)
    if re.fullmatch(r"startsWith\(github\.ref, 'refs/tags/v?'\)", text):
        return "a-tag"
    if re.fullmatch(r"!\s*startsWith\(github\.ref, 'refs/tags/v?'\)", text):
        return "a-branch"
    if re.fullmatch(r"runner\.os == 'macOS'|matrix\.os == 'macos-latest'", text):
        return "macos"
    if re.fullmatch(r"matrix\.python == '3\.9'", text):
        return "python-3.9"
    return None


@NEEDS_UPSTREAM
def test_release_install_check_runs_after_testpypi_on_a_tag_and_after_the_build_on_a_branch():
    """THE MODEL'S CONDITION (contracts/workflows.md): on a tag after
    `testpypi` succeeded, on a branch when it was skipped, never after a
    failure; and the job reads nothing but its checkout."""
    install = job(release(), "install")
    assert set(as_list(install.get("needs"))) == {"build", "testpypi"}
    assert normal(install.get("if")) == normal(INSTALL_IF), install.get("if")


@NEEDS_UPSTREAM
def test_release_install_check_runs_three_legs_and_no_windows_leg():
    """ubuntu and macOS on Python 3.x, and ubuntu on 3.9, the package's
    oldest (FR-032): the legs are the matrix's only rows, each runs on its
    own `os` with its own Python, and none is Windows."""
    install = job(release(), "install")
    matrix = (install.get("strategy") or {}).get("matrix") or {}
    assert list(matrix) == ["include"], matrix
    legs = matrix["include"]
    assert all(set(leg) == {"os", "python"} for leg in legs), legs
    assert sorted((leg["os"], str(leg["python"])) for leg in legs) == sorted(
        INSTALL_LEGS), legs
    assert normal(install.get("runs-on")) == "matrix.os", install.get("runs-on")
    setups = [s for s in install_steps(release())
              if str(s.get("uses", "")).startswith("actions/setup-python@")]
    assert len(setups) == 1 and normal(
        (setups[0].get("with") or {}).get("python-version")) == "matrix.python"
    for step in install_steps(release()):
        assert step.get("shell") not in ("pwsh", "powershell", "cmd"), label(step)


@NEEDS_UPSTREAM
def test_release_install_check_reads_pypi_alone_and_installs_pipx_from_its_lock():
    """`PIP_INDEX_URL` is PyPI's, as the model has it, no script names
    another index, and every `pip install` is pipx from
    `.github/release-pipx-requirements.txt`, by hash, wheels only (FR-035)."""
    workflow = release()
    install = job(workflow, "install")
    assert (install.get("env") or {}).get("PIP_INDEX_URL") == PIP_INDEX_URL
    for step in install_steps(workflow):
        assert "--index-url" not in run_text(step), label(step)
        assert "--extra-index-url" not in run_text(step), label(step)
    installs = pip_installs(workflow, "install")
    assert installs, "the install check installs no pipx from its lock"
    problems = {command: hashed_from(command, PIPX_LOCK) for command in installs}
    assert not any(problems.values()), problems


#: THE INSTALL CHECK'S OWN CHECK OF THE WHEEL IT TOOK, by its name: on a tag
#: and on a branch alike, the one file it holds must have the sha256 the build
#: job recorded before anything from it runs.
WHEEL_DIGEST_STEP = "the wheel is the one the build job verified"


@NEEDS_UPSTREAM
def test_release_install_check_takes_the_wheel_by_its_digest_on_a_tag_and_a_branch():
    """STEP 1: on a tag the wheel comes from TestPyPI, on a branch it is the
    build's artifact, and in both cases its sha256 is checked before
    anything from it runs: `WHEEL_DIGEST_STEP`, with no `if:`, comes after
    both and before pipx installs the wheel, and the test after this one
    runs it. Only the intended steps are conditional: those two, and the
    macOS and Python 3.9 legs' own; and the checkout keeps no credentials."""
    workflow = release()
    steps = install_steps(workflow)
    kinds = {}
    for at, step in enumerate(steps):
        if "if" in step:
            kind = condition_kind(step["if"])
            assert kind, f"{label(step)} runs only if {step['if']!r}"
            kinds.setdefault(kind, []).append(at)
        assert "continue-on-error" not in step, label(step)
    assert len(kinds.get("a-tag", [])) == 1 and len(kinds.get("a-branch", [])) == 1, kinds
    fetch, take = steps[kinds["a-tag"][0]], steps[kinds["a-branch"][0]]
    assert "test.pypi.org" in run_text(fetch), label(fetch)
    assert str(take.get("uses", "")).startswith("actions/download-artifact@")
    after = max(kinds["a-tag"][0], kinds["a-branch"][0])
    check = named(workflow, "install", WHEEL_DIGEST_STEP)
    at = where(workflow, "install", check)
    assert at > after and "if" not in check, (
        f"{label(check)!r} is step {at}, conditional or before the wheel is "
        f"taken (step {after})")
    installs = [i for i, s in enumerate(steps)
                if re.search(r"\bpipx install\b", run_text(s))]
    assert installs and at < min(installs), (
        f"pipx installs the wheel (steps {installs}) before {label(check)!r} "
        f"(step {at}) checks its sha256")
    for step in steps:
        if str(step.get("uses", "")).startswith("actions/checkout@"):
            assert (step.get("with") or {}).get("persist-credentials") is False


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", WHEEL_DIGEST_CASES)
def test_release_install_check_the_digest_step_passes_the_recorded_wheel_alone(
        tmp_path, which):
    """THE WHOLE STEP, RUN (contracts/workflows.md's install step 1), its
    bash line and its heredoc, with `python` this interpreter: over the job's
    wheel directory it passes the one file named `$WHEEL` whose sha256 is
    `$WHEEL_SHA256`, and refuses other bytes under that name, another file
    beside it, another name, and nothing at all, so the install check never
    runs a file the build did not verify."""
    files, passes = WHEEL_DIGEST_CASES[which]
    wheel = "openrepotools-1.1.0rc1-py3-none-any.whl"
    digest = hashlib.sha256(RECORDED_WHEEL).hexdigest()
    workflow = release()
    fakes = python_tool(tmp_path / "fakes", "python", AS_PYTHON)
    runner = Runner(tmp_path / "work", workflow, "install",
                    {"WHEEL": wheel, "WHEEL_SHA256": digest}, fakes)
    a_wheel_directory(Path(runner.env["RUNNER_TEMP"]) / "wheel", files, wheel)
    done = runner.run(named(workflow, "install", WHEEL_DIGEST_STEP))
    assert (done.returncode == 0) == passes, transcript(done)
    out = done.stdout + done.stderr
    assert "Traceback" not in out, transcript(done)
    if passes:
        assert done.stdout.strip() == f"{wheel}: sha256 {digest}, the recorded digest", (
            transcript(done))
    else:
        assert "::error::" in out, transcript(done)


#: The install check's two steps that fetch and install, by their names.
FETCH_STEP = "fetch the wheel from TestPyPI"
PIPX_STEP = "pipx installs the wheel into a fresh environment"

#: `python`, as setup-python puts it on PATH: this interpreter.
AS_PYTHON = "import os, sys\nos.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n"

#: A `curl` that writes down each call, refuses one that is not https-only,
#: and answers a JSON URL with `FAKE_INDEX_JSON` and any other with bytes
#: naming the URL.
FAKE_CURL = r'''
import os, shutil, sys
args = sys.argv[1:]
with open(os.environ["FAKE_CURL_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join(args) + "\n")
if "--proto" not in args or args[args.index("--proto") + 1] != "=https":
    sys.stderr.write("fake curl: a fetch that is not https-only\n")
    sys.exit(1)
out, url = args[args.index("-o") + 1], args[-1]
if url.endswith("/json"):
    shutil.copyfile(os.environ["FAKE_INDEX_JSON"], out)
else:
    with open(out, "wb") as handle:
        handle.write(b"the file at " + url.encode())
'''

FETCHED_WHEEL = "openrepotools-1.1.0rc1-py3-none-any.whl"
FILE_HOST = "https://test-files.pythonhosted.org/packages/5e/1f/" + FETCHED_WHEEL


def listed(filename: str, digest: str, url: str) -> dict:
    return {"filename": filename, "digests": {"sha256": digest}, "url": url}


#: THE FETCH, RUN: `(what TestPyPI's JSON lists for the version, whether the
#: step passes)`. It must take the one file of the wheel's name at the
#: recorded digest, from TestPyPI's own file host, over https.
FETCH_CASES = {
    "listed-once-on-its-file-host": ([listed(FETCHED_WHEEL, VERIFIED, FILE_HOST)], True),
    "listed-on-another-host": (
        [listed(FETCHED_WHEEL, VERIFIED, "https://files.example.invalid/" + FETCHED_WHEEL)],
        False),
    "listed-over-plain-http": (
        [listed(FETCHED_WHEEL, VERIFIED, FILE_HOST.replace("https:", "http:"))], False),
    "listed-twice-at-the-digest": ([listed(FETCHED_WHEEL, VERIFIED, FILE_HOST)] * 2, False),
    "listed-at-another-digest": (
        [listed(FETCHED_WHEEL, ANOTHER_DIGEST, FILE_HOST)], False),
    "another-file-at-the-digest": (
        [listed("openrepotools-1.1.0rc1.tar.gz", VERIFIED, FILE_HOST)], False),
    "nothing-listed": ([], False),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", FETCH_CASES)
def test_release_install_check_the_fetch_takes_the_recorded_wheel_from_testpypi_s_file_host(
        tmp_path, which):
    """THE FETCH ON A TAG, RUN with `curl` faked (contracts/workflows.md's
    install step 1): it reads TestPyPI's JSON for the version, then fetches
    the one file listed under the wheel's name at the recorded digest, from
    test-files.pythonhosted.org over https. Another host, plain http, the
    file listed twice, another digest, another file, and nothing listed are
    each refused before anything is fetched."""
    entries, passes = FETCH_CASES[which]
    index = tmp_path / "testpypi.json"
    index.write_text(json.dumps({"info": {"name": "openrepotools"}, "urls": entries}),
                     encoding="utf-8")
    fakes = python_tool(tmp_path / "fakes", "curl", FAKE_CURL)
    python_tool(fakes, "python", AS_PYTHON)
    log = tmp_path / "curl.log"
    values = {"VERSION": "1.1.0rc1", "WHEEL": FETCHED_WHEEL, "WHEEL_SHA256": VERIFIED,
              "FAKE_CURL_LOG": str(log), "FAKE_INDEX_JSON": str(index)}
    workflow = release()
    runner = Runner(tmp_path / "work", workflow, "install", values, fakes)
    done = runner.run(named(workflow, "install", FETCH_STEP))
    assert (done.returncode == 0) == passes, transcript(done)
    urls = [line.split()[-1] for line in log.read_text(encoding="utf-8").splitlines()]
    wheel = Path(runner.env["RUNNER_TEMP"]) / "wheel" / FETCHED_WHEEL
    if passes:
        assert urls == ["https://test.pypi.org/pypi/openrepotools/1.1.0rc1/json",
                        FILE_HOST], urls
        assert wheel.read_bytes() == b"the file at " + FILE_HOST.encode()
        assert done.stdout.strip() == f"fetched {FILE_HOST}", transcript(done)
    else:
        assert urls == ["https://test.pypi.org/pypi/openrepotools/1.1.0rc1/json"], (
            f"the step fetched after refusing: {urls}")
        assert not wheel.exists()


#: `python -m pipx install ...`, faked: it writes down its arguments and
#: places in `$PIPX_BIN_DIR` what `FAKE_PIPX_PLACES` names, each `link:<name>`
#: (a link into its venv) or `file:<name>`; anything else runs this Python.
FAKE_PIPX_PYTHON = r'''
import os, sys
args = sys.argv[1:]
if args[:3] != ["-m", "pipx", "install"]:
    os.execv(sys.executable, [sys.executable, *args])
with open(os.environ["FAKE_PIPX_LOG"], "a", encoding="utf-8") as log:
    log.write("\t".join(args) + "\n")
bin_dir = os.environ["PIPX_BIN_DIR"]
os.makedirs(bin_dir, exist_ok=True)
for place in os.environ["FAKE_PIPX_PLACES"].split():
    kind, _, name = place.partition(":")
    if kind == "link":
        os.symlink(os.environ["FAKE_PIPX_TARGET"], os.path.join(bin_dir, name))
    else:
        with open(os.path.join(bin_dir, name), "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n")
'''

#: THE PIPX INSTALL, RUN: `(what pipx places in its bin directory, whether
#: the step passes)`. One command, so one link.
PIPX_CASES = {
    "the-one-link": (["link:openRepoTools"], True),
    "a-file-not-a-link": (["file:openRepoTools"], False),
    "a-second-command": (["link:openRepoTools", "link:lane"], False),
    "nothing-placed": ([], False),
    "another-name": (["link:openrepotools"], False),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", PIPX_CASES)
def test_release_install_check_pipx_places_the_one_link_openrepotools_and_nothing_else(
        tmp_path, which):
    """THE PIPX INSTALL, RUN with pipx faked (contracts/workflows.md's
    install step 3): pipx installs the fetched wheel, wheels only, and the
    step passes only where its bin directory holds the link `openRepoTools`
    and nothing else. A regular file, a second command, nothing, and a link
    of another name are each refused."""
    places, passes = PIPX_CASES[which]
    target = tmp_path / "venv" / "bin" / "openRepoTools"
    target.parent.mkdir(parents=True)
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    fakes = python_tool(tmp_path / "fakes", "python", FAKE_PIPX_PYTHON)
    log, bin_dir = tmp_path / "pipx.log", tmp_path / "pipx-bin"
    values = {"WHEEL": FETCHED_WHEEL, "PIPX_BIN_DIR": str(bin_dir),
              "FAKE_PIPX_PLACES": " ".join(places), "FAKE_PIPX_LOG": str(log),
              "FAKE_PIPX_TARGET": str(target)}
    workflow = release()
    runner = Runner(tmp_path / "work", workflow, "install", values, fakes)
    done = runner.run(named(workflow, "install", PIPX_STEP))
    assert (done.returncode == 0) == passes, transcript(done)
    wheel = f"{runner.env['RUNNER_TEMP']}/wheel/{FETCHED_WHEEL}"
    assert log.read_text(encoding="utf-8").splitlines() == [
        "\t".join(["-m", "pipx", "install", "--pip-args=--only-binary=:all:", wheel])]
    if not passes:
        assert "::error::" in done.stdout, transcript(done)


@NEEDS_UPSTREAM
def test_release_install_check_installs_with_pipx_and_runs_version_and_the_offline_install():
    """STEPS 2 TO 5: pipx places the wheel's one command; `--version` names
    the run's repository and commit; and an offline `--install` into a fresh
    `HOME`, with the sentinel repository, checks the skip line and the count
    line of contracts/cli-output.md."""
    steps = install_steps(release())
    texts = [run_text(s) for s in steps]
    assert [t for t in texts if "pipx" in t and "install" in t
            and "PIPX_BIN_DIR" in t], "no step installs the wheel with pipx"
    assert [t for t in texts if "--version" in t and "GITHUB_SHA" in t
            and "GITHUB_REPOSITORY" in t], "no step checks --version"
    assert [t for t in texts if "--install" in t
            and "offline.invalid/sentinel" in t
            and "(a link into pipx's openrepotools environment)" in t
            and "and 1 left to pipx" in t], "no step checks the offline install"


#: THE OFFLINE `--install` IS `tests.yml`'s OWN (the comment above the
#: release's step): the install check's script and the `package` job's are
#: one script, line for line, but for the two places that fingerprint pipx's
#: link. `tests.yml` takes the fingerprint with GNU's `stat -c` and
#: `sha256sum`, and the release, whose macOS leg has neither, with the leg's
#: Python. Each difference allowed, in order: `(tests.yml's lines,
#: release.yml's lines)`.
FINGERPRINT_LINES = (
    (['before="$(stat -c %i "$link") $(readlink "$link") $(sha256sum < "$link")"'],
     ["fingerprint='import hashlib, os, sys; p = sys.argv[1]; "
      "print(os.lstat(p).st_ino, os.readlink(p), "
      "hashlib.sha256(open(p, \"rb\").read()).hexdigest())'",
      'before="$(python3 -I -c "$fingerprint" "$link")"']),
    (['if [ ! -L "$link" ] ||',
      '    [ "$(stat -c %i "$link") $(readlink "$link") $(sha256sum < "$link")"'
      ' != "$before" ]; then'],
     ['if [ ! -L "$link" ] || [ "$(python3 -I -c "$fingerprint" "$link")"'
      ' != "$before" ]; then']),
)

#: THE macOS RERUN IS THE SAME SCRIPT AGAIN (FR-032): the release's offline
#: `--install`, run a second time under Apple's `/bin/bash` 3.2, and different
#: only where it must be. Each difference allowed, in order: `(the offline
#: --install's lines, the macOS rerun's lines)`. Its own home and offline
#: directory; the bash it runs under, which must print a `BASH_VERSION` of
#: 3.2; `/bin` first on the `--install`'s PATH; its own output files; and
#: refusals that name that bash. The skip line, the count line, the receipt's
#: 28 rows and the link's fingerprint are the offline --install's own.
MACOS_RERUN_LINES = (
    (['home="$RUNNER_TEMP/install-home"',
      'offline="$RUNNER_TEMP/offline-bin"'],
     ['home="$RUNNER_TEMP/install-home-bin-bash"',
      'offline="$RUNNER_TEMP/offline-bin-bin-bash"']),
    ([],
     ['# shellcheck disable=SC2016',
      'version="$(env -i PATH="/bin:$offline:$PIPX_BIN_DIR:$PATH" bash -c '
      '\'printf "%s\\n" "$BASH_VERSION"\')"',
      'echo "BASH_VERSION $version, from the bash first on PATH=/bin:..."',
      'case "$version" in',
      '  3.2.*) ;;',
      '  *)',
      '    echo "::error::the bash first on a PATH that begins with /bin is '
      '$version, not Apple\'s 3.2"',
      '    exit 1',
      '    ;;',
      'esac']),
    (['env -i HOME="$home" PATH="$offline:$PIPX_BIN_DIR:$PATH" \\'],
     ['env -i HOME="$home" PATH="/bin:$offline:$PIPX_BIN_DIR:$PATH" \\']),
    (['    "$link" --install > "$RUNNER_TEMP/install.out" 2> '
      '"$RUNNER_TEMP/install.err" ||',
      '    status=$?',
      'cat "$RUNNER_TEMP/install.out"',
      'cat "$RUNNER_TEMP/install.err" >&2'],
     ['    "$PIPX_BIN_DIR/openRepoTools" --install > '
      '"$RUNNER_TEMP/install-bin-bash.out" \\',
      '    2> "$RUNNER_TEMP/install-bin-bash.err" || status=$?',
      'cat "$RUNNER_TEMP/install-bin-bash.out"',
      'cat "$RUNNER_TEMP/install-bin-bash.err" >&2']),
    (['  echo "::error::the offline --install exited $status"'],
     ['  echo "::error::the offline --install under /bin/bash $version exited '
      '$status"']),
    (['  seen="$(grep -cFx -e "$line" "$RUNNER_TEMP/install.out" || true)"'],
     ['  seen="$(grep -cFx -e "$line" "$RUNNER_TEMP/install-bin-bash.out" || '
      'true)"']),
    (['    echo "::error::--install printed this line $seen times, not once: '
      '$line"'],
     ['    echo "::error::--install under /bin/bash $version printed this line '
      '$seen times, not once: $line"']),
    (['  echo "::error::--install wrote no receipt at $receipt"'],
     ['  echo "::error::--install under /bin/bash $version wrote no receipt at '
      '$receipt"']),
    (['  echo "::error::the receipt has $lines lines and $rows rows, not 28: a '
      'full install\'s 29 less pipx\'s link"'],
     ['  echo "::error::under /bin/bash $version the receipt has $lines lines '
      'and $rows rows, not 28"']),
    (['  echo "::error::--install changed pipx\'s link at $link"'],
     ['  echo "::error::--install under /bin/bash $version changed pipx\'s link '
      'at $link"']),
)

#: The offline `--install` step, in either file: the one step of its job, with
#: no `if:`, that runs `--install` against the sentinel repository.
SENTINEL = re.compile(r"\bOPENREPOTOOLS_REPO=[\"']?offline\.invalid/sentinel")


def offline_install_step(steps: list, whose: str) -> dict:
    found = [s for s in steps if SENTINEL.search(run_text(s)) and "if" not in s]
    if len(found) != 1:
        pytest.fail(f"{whose} has {len(found)} unconditional steps that run "
                    "--install against offline.invalid/sentinel, not one: "
                    f"{[label(s) for s in found]}", pytrace=False)
    return found[0]


def assert_one_script_but(theirs: dict, ours: dict, allowed: tuple,
                          names: Tuple[str, str], beside: tuple) -> None:
    """`ours` is `theirs` with the same keys but `beside`, and its script is
    `theirs`'s, line for line, but for `allowed`'s pairs, in order."""
    keys = {k: v for k, v in ours.items() if k not in beside}
    assert keys == {k: v for k, v in theirs.items() if k not in beside}, (
        f"{names[1]}'s step and {names[0]}'s differ beside their scripts: "
        f"{ours} against {theirs}")
    mine, its = run_text(ours).split("\n"), run_text(theirs).split("\n")
    matcher = difflib.SequenceMatcher(a=its, b=mine, autojunk=False)
    found = [(its[i1:i2], mine[j1:j2])
             for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]
    assert found == [(list(a), list(b)) for a, b in allowed], (
        f"{names[1]} is not {names[0]} but for the lines this test names:\n"
        + "\n".join(difflib.unified_diff(its, mine, names[0], names[1],
                                         lineterm="", n=0)))


@NEEDS_UPSTREAM
def test_release_install_check_the_offline_installs_are_one_script_but_for_named_lines():
    """THE THREE COPIES CANNOT DRIFT (FR-016, FR-032). The install check's
    offline `--install` is `tests.yml`'s `package` job's, line for line, with
    the same keys beside its script, but for `FINGERPRINT_LINES`. Its macOS
    rerun under `/bin/bash` 3.2 is that offline `--install` again, with the
    same keys but its `if:`, but for `MACOS_RERUN_LINES`. Each difference is
    named there. So a count line, a skip line or a receipt count changed in
    one copy alone fails here, before a release tests what `tests.yml` never
    did and burns the version on TestPyPI, and so does a rerun that no
    longer requires 3.2."""
    steps = install_steps(release())
    ours = offline_install_step(steps, "release.yml's install job")
    package = (standard().load_yaml(TESTS_WORKFLOW).get("jobs") or {}).get("package")
    if not isinstance(package, dict) or not isinstance(package.get("steps"), list):
        pytest.fail("tests.yml has no `package` job with steps", pytrace=False)
    theirs = offline_install_step(package["steps"], "tests.yml's package job")
    assert_one_script_but(theirs, ours, FINGERPRINT_LINES,
                          ("tests.yml", "release.yml"), ("name", "run"))
    reruns = [s for s in steps if condition_kind(s.get("if")) == "macos"
              and SENTINEL.search(run_text(s))]
    assert len(reruns) == 1, [label(s) for s in reruns]
    assert_one_script_but(ours, reruns[0], MACOS_RERUN_LINES,
                          ("the offline --install", "the macOS rerun"),
                          ("name", "run", "if"))


#: `/bin` put first on `PATH`: for one command (`PATH="/bin:..." command`),
#: or, as a command of its own, for every command after it.
BIN_FIRST = re.compile(r"""(?<!\w)PATH=["']?/bin:""")
BIN_FIRST_FROM_HERE = re.compile(r"""(?:export\s+)?PATH=["']?/bin:[^\s;&|]*["']?""")


def under_bin_first(script: str, pattern: str) -> bool:
    """Whether a command of `script` that matches `pattern` runs with `/bin`
    first on its `PATH`."""
    lines = commands(script)
    return any(re.search(pattern, line) and (
        BIN_FIRST.search(line)
        or any(BIN_FIRST_FROM_HERE.fullmatch(before) for before in lines[:at]))
        for at, line in enumerate(lines))


@NEEDS_UPSTREAM
def test_release_install_check_the_macos_leg_reruns_under_bin_bash_3_2():
    """FR-032, SC-008: on macOS only, the offline `--install` again with
    `PATH="/bin:$PATH"`, so Apple's `/bin/bash` 3.2 runs it, printing a
    `BASH_VERSION` that must begin with 3.2. The `--install` command itself
    has `/bin` first on its `PATH`, and so does the bash that prints
    `BASH_VERSION`, unless that bash is `/bin/bash` by name."""
    steps = [s for s in install_steps(release())
             if condition_kind(s.get("if")) == "macos"]

    def reruns(text: str) -> bool:
        prints = (under_bin_first(text, r"\bBASH_VERSION\b")
                  or any("BASH_VERSION" in line and "/bin/bash" in line
                         for line in commands(text)))
        return (under_bin_first(text, r"\bopenRepoTools\b.*\s--install\b")
                and prints and "3.2" in text)

    assert [s for s in steps if reruns(run_text(s))], [label(s) for s in steps]


@NEEDS_UPSTREAM
def test_release_install_check_the_3_9_leg_compiles_the_two_python_commands():
    """FR-032: on Python 3.9 only, the installed package's own
    `payload/lanes-index` and `payload/lane-worktrees` are compiled: the
    shipped bytes are what must compile on 3.9."""
    steps = [s for s in install_steps(release())
             if condition_kind(s.get("if")) == "python-3.9"]
    assert [s for s in steps if "compile(" in run_text(s)
            and "lanes-index" in run_text(s) and "lane-worktrees" in run_text(s)
            and "payload" in run_text(s)], [label(s) for s in steps]


#: The install check's `--version` step, by its name.
VERSION_STEP = "openRepoTools --version names this release, line for line"

#: The release the run is (contracts/stamp.md's names), and each stamp the
#: installed package may carry instead, with whether the step passes it.
VERSION_RUN = dict(RELEASES["an-rc-rehearsal-here"])
VERSION_CASES = {
    "this-release": ({}, True),
    "another-digest": ({"DIGEST": "1" * 64}, False),
    "another-commit": ({"COMMIT": "a" * 40}, False),
    "another-repository": ({"REPOSITORY": CODE_LEG}, False),
    "another-version": ({"VERSION": "1.1.0rc2", "TAG": "v1.1.0rc2"}, False),
    "unstamped": (None, False),
}


@NEEDS_UPSTREAM
@NEEDS_BASH
@WINDOWS_SKIP
@pytest.mark.parametrize("which", VERSION_CASES)
def test_release_install_check_the_version_step_passes_this_release_s_five_lines_alone(
        tmp_path, which):
    """THE `--version` STEP, RUN (contracts/workflows.md's install step 4):
    `$PIPX_BIN_DIR/openRepoTools` is the installed package's own entry,
    which execs bash on its payload as pipx's console script does, and its
    `--version` must be this run's five lines, the digest's among them. A
    package stamped with another digest, commit, repository or version, or
    unstamped, is refused."""
    changes, passes = VERSION_CASES[which]
    stamp = (layout.stamp_text() if changes is None
             else layout.stamp_text(**dict(VERSION_RUN, **changes)))
    payload = layout.package_tree(tmp_path / "venv", stamp=stamp)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    entry = bin_dir / "openRepoTools"
    entry.write_text("#!/bin/sh\nexec bash "
                     f"{shlex.quote(str(payload / 'openRepoTools'))} \"$@\"\n",
                     encoding="utf-8")
    entry.chmod(0o755)
    workflow = release()
    values = {"VERSION": VERSION_RUN["VERSION"],
              "GITHUB_REPOSITORY": VERSION_RUN["REPOSITORY"],
              "GITHUB_SHA": VERSION_RUN["COMMIT"],
              "DIGEST": VERSION_RUN["DIGEST"], "PIPX_BIN_DIR": str(bin_dir)}
    runner = Runner(tmp_path / "work", workflow, "install", values)
    done = runner.run(named(workflow, "install", VERSION_STEP))
    assert (done.returncode == 0) == passes, transcript(done)
    if passes:
        assert done.stdout == STAMPED_VERSION.format(**VERSION_RUN), transcript(done)
    else:
        assert "::error::" in done.stdout, transcript(done)


#: A heredoc run by this Python as if it were another release of Python:
#: `sys.version_info` and `sys.version` say `<version>`, `sys.argv` is
#: `["-"]`, as under `python3 -`, and nothing else is changed. The 3.9 leg's
#: step refuses any Python but 3.9, and the suite runs on a current one.
AS_ANOTHER_PYTHON = r'''
import sys
code, version = sys.argv[1], sys.argv[2]
sys.version = f"{version} (the suite's {sys.version.split()[0]}, read as {version})"
sys.version_info = tuple(int(part) for part in version.split(".")) + ("final", 0)
sys.argv = ["-"]
with open(code, encoding="utf-8") as handle:
    source = handle.read()
exec(compile(source, "<stdin>", "exec"), {"__name__": "__main__"})
'''


def with_two_pythons(home: Path) -> None:
    layout.pipx_venv(home, "1.11.1")
    layout.package_tree(home / "venvs" / "openrepotools", "python3.10")


def with_lanes_index_broken(home: Path) -> None:
    layout.pipx_venv(home, "1.11.1")
    payload = home / "venvs/openrepotools/lib/python3.9/site-packages/openrepotools/payload"
    (payload / "lanes-index").write_bytes(b"def broken(:\n")


def with_lane_worktrees_missing(home: Path) -> None:
    layout.pipx_venv(home, "1.11.1")
    payload = home / "venvs/openrepotools/lib/python3.9/site-packages/openrepotools/payload"
    (payload / "lane-worktrees").unlink()


#: `(the Python the step is run as, the pipx home it reads, whether it
#: passes, what its refusal names)`.
COMPILE_CASES = {
    "the-payload-as-built": ("3.9.25", lambda home: layout.pipx_venv(home, "1.11.1"),
                             True, None),
    "lanes-index-does-not-compile": ("3.9.25", with_lanes_index_broken, False,
                                     "lanes-index"),
    "lane-worktrees-missing": ("3.9.25", with_lane_worktrees_missing, False,
                               "lane-worktrees"),
    "no-payload-directory": ("3.9.25", lambda home: home.mkdir(parents=True),
                             False, "not one payload directory"),
    "two-payload-directories": ("3.9.25", with_two_pythons, False,
                                "not one payload directory"),
    "not-python-3.9": ("3.12.3", lambda home: layout.pipx_venv(home, "1.11.1"),
                       False, "not 3.9"),
}


@NEEDS_UPSTREAM
@pytest.mark.parametrize("which", COMPILE_CASES)
def test_release_install_check_the_3_9_step_refuses_a_payload_command_that_does_not_compile(
        tmp_path, which):
    """THE 3.9 LEG'S STEP, RUN (FR-032), on a pipx home laid out as pipx
    1.11.1 leaves it: it passes the payload as built, and refuses, naming
    why, a `lanes-index` that does not compile, a `lane-worktrees` that is
    missing, no payload directory or two, and any Python but 3.9. The step
    is run by this Python, reading as the Python the case names."""
    version, lay_out, passes, names = COMPILE_CASES[which]
    steps = [s for s in install_steps(release())
             if condition_kind(s.get("if")) == "python-3.9"]
    assert len(steps) == 1, [label(s) for s in steps]
    home = tmp_path / "pipx-home"
    lay_out(home)
    work = tmp_path / "run"
    work.mkdir()
    (work / "heredoc.py").write_text(heredoc(run_text(steps[0])), encoding="utf-8")
    (work / "as-another-python.py").write_text(AS_ANOTHER_PYTHON, encoding="utf-8")
    env = clean_environ(work / "home")
    env.update(PYTHONUTF8="1", PIPX_HOME=str(home))
    done = subprocess.run([sys.executable, "-I", str(work / "as-another-python.py"),
                           str(work / "heredoc.py"), version],
                          capture_output=True, text=True, check=False,
                          stdin=subprocess.DEVNULL, env=env, cwd=str(work),
                          timeout=STEP_TIMEOUT)
    assert (done.returncode == 0) == passes, transcript(done)
    out = done.stdout + done.stderr
    assert "Traceback" not in out, transcript(done)
    if names:
        assert [line for line in out.splitlines()
                if line.startswith("::error::") and names in line], transcript(done)


# --- every job's steps, in order -----------------------------------------------------

#: THE STEPS `STEP_ORDER` FINDS BY THEIR ROLE, as HOW A STEP IS FOUND (the
#: header) has them found, never by their names: the build's guard by the
#: outputs it records (`guard_step`), each upload job's guard as its first
#: step, and the macOS and 3.9 legs' own steps by their `if:`
#: (`condition_kind`). Each is written as the failure message prints it.
BUILD_GUARD = "<the repository guard: the step whose outputs the build job records>"
UPLOAD_GUARD = "<the repository guard again: the job's first step>"
MACOS_LEG = "<the macOS leg's own step: its if: is the macOS condition>"
PYTHON_3_9_LEG = "<the Python 3.9 leg's own step: its if: is the 3.9 condition>"

#: EACH JOB'S WHOLE STEP LIST, IN ORDER, each step by its role where the list
#: names one, and every other step by a prefix of its label (its name, or the
#: action it uses): so a step inserted anywhere, named or not, fails here, as
#: does one moved or dropped, and a step found by its role can be renamed. An
#: inserted step could undo a check before it (a step after the stamp writer
#: that rewrote the stamp, say) while every check still passes on its own.
STEP_ORDER = {
    "build": ["actions/checkout", "actions/setup-python", BUILD_GUARD, *BUILD_STEPS,
              "actions/upload-artifact"],
    "testpypi": [UPLOAD_GUARD, "actions/download-artifact",
                 DIST_STEP, APPROVAL_STEP, TAG_AGAIN_STEP, EMPTY_INDEX_STEP,
                 "pypa/gh-action-pypi-publish", SERVED_STEP],
    "install": ["actions/checkout", "actions/setup-python", FETCH_STEP,
                "take the build's own wheel", WHEEL_DIGEST_STEP,
                "pipx from its hash lock", PIPX_STEP, VERSION_STEP,
                "an offline --install beside pipx's link", MACOS_LEG,
                PYTHON_3_9_LEG],
    "pypi": [UPLOAD_GUARD, "actions/download-artifact",
             DIST_STEP, APPROVAL_STEP, TAG_AGAIN_STEP, EMPTY_INDEX_STEP,
             "pypa/gh-action-pypi-publish", SERVED_STEP],
}


def in_its_place(workflow: dict, at: int, step: dict, wanted: str) -> bool:
    """Whether `step`, at index `at` of its job, is the one `STEP_ORDER`
    puts there: the step of the role `wanted` names, or one whose label
    begins with `wanted`."""
    if wanted == BUILD_GUARD:
        return step is guard_step(workflow)
    if wanted == UPLOAD_GUARD:
        return at == 0
    if wanted == MACOS_LEG:
        return condition_kind(step.get("if")) == "macos"
    if wanted == PYTHON_3_9_LEG:
        return condition_kind(step.get("if")) == "python-3.9"
    return label(step).startswith(wanted)


@NEEDS_UPSTREAM
@pytest.mark.parametrize("name", JOBS)
def test_release_upload_each_job_runs_exactly_its_steps_in_order(name):
    """EVERY STEP OF EVERY JOB, IN ORDER, AND NO OTHER (contracts/workflows.md):
    the job's steps are `STEP_ORDER`'s, one for one, each found as the rest
    of this file finds it."""
    workflow = release()
    steps = steps_of(workflow, name)
    wanted = STEP_ORDER[name]
    assert len(steps) == len(wanted) and all(
        in_its_place(workflow, at, step, entry)
        for at, (step, entry) in enumerate(zip(steps, wanted))), (
        f"the {name} job's steps are:\n  " + "\n  ".join(label(s) for s in steps)
        + "\nand `STEP_ORDER` holds:\n  " + "\n  ".join(wanted))


# --- what the workflow reads ----------------------------------------------------------

#: What the code leg will not hold (FR-046): the spec trees and the front-door
#: documents, by `tests/conftest.py`'s own placement table; and the release
#: notes, which no release step reads (FR-034, design.md Decision 11).
OUTSIDE_THE_CODE_LEG = re.compile(
    r"(?<![\w.-])(?:" + "|".join(map(re.escape, SPEC_TREES)) + r")/"
    r"|(?<![\w.-])(?:" + "|".join(map(re.escape, GUIDANCE_DOCUMENTS))
    + r")(?![\w.-])|release-notes")


def step_texts(step: dict) -> List[str]:
    texts = commands(run_text(step))
    for scope in ("with", "env"):
        texts += [str(value) for value in (step.get(scope) or {}).values()]
    if step.get("working-directory"):
        texts.append(str(step["working-directory"]))
    return texts


@NEEDS_UPSTREAM
def test_release_reads_nothing_the_code_leg_will_not_hold():
    """FR-046: no step names `docs/`, `openspec/`, `specs/`, `ideation/`,
    `README.md`, `AGENTS.md` or `CLAUDE.md`, nor the release notes, in a
    command, an input or a setting: after the cutover the workflow runs in the
    code leg, which holds none of them."""
    workflow = release()
    found = [f"{name}: {label(step)}: {text[:120]}"
             for name, step in every_step(workflow) for text in step_texts(step)
             if OUTSIDE_THE_CODE_LEG.search(text)]
    found += [f"{name}: env: {value}" for name, body in workflow["jobs"].items()
              for value in (body.get("env") or {}).values()
              if OUTSIDE_THE_CODE_LEG.search(str(value))]
    assert not found, "steps that read outside the code leg:\n  " + "\n  ".join(found)


# --- the header ------------------------------------------------------------------------

def header() -> str:
    """The comment block above `on:`, its lines joined into one text, with
    each line's `#` and a shell continuation's `\\` taken off."""
    release()
    lines = []
    for line in WORKFLOW.read_text(encoding="utf-8").splitlines():
        if re.match(r"^on\s*:", line):
            break
        text = line.strip()
        if text.startswith("#"):
            text = text[1:].strip()
            if text.endswith("\\"):
                text = text[:-1].rstrip()
            lines.append(text)
    else:
        pytest.fail("release.yml has no `on:` line", pytrace=False)
    return " ".join(" ".join(lines).split())


#: contracts/workflows.md's six sections, each by one phrase it must carry,
#: in this order: what the workflow is and its model; the procedure, with the
#: tag message's form (FR-036); #850's policy; the two rehearsals, with the
#: first one's dispatch; where releases come from, by the guard (FR-048); and
#: what the workflow never reads (FR-046).
HEADER_SECTIONS = ("190133d", "Tagged on Brett Heap's word", "#850",
                   "gh workflow run release.yml --ref <branch> -f version=1.1.0rc1",
                   "FR-048", "FR-046")

#: What else the header must say, wherever it says it.
HEADER_CARRIES = (
    "RELEASING", "openRepoShape v1.1.0", "Decision 10", "openRepoTools-3",
    "Brett Heap", "Lane: <lane>",
    "gh release create v<version> --repo <repository> --verify-tag "
    "--notes-file <spec>/docs/release-notes/v<version>.md",
    "release/vX.Y", "annotated", "cherry-pick -x", "HOLD", "LANDED",
    "l3-rehearsal-v1.1.0", "tests.yml", "opensoft/openRepoTools-code",
    "opensoft/openRepoTools", "pypi.org publisher", "testpypi", "pypi",
    # the procedure's approvals, and the branch cut at the tag's commit: a
    # push of the tag itself is rejected ("trying to write non-commit object")
    "4. APPROVE `testpypi`, Brett Heap's act. The install check then runs on "
    "its three legs; approve `pypi` once it has passed.",
    "git push origin 'vX.Y.0^{commit}:refs/heads/release/vX.Y'",
    # the ref step's fetch needs the code leg public
    "opensoft/openRepoTools-code STAYS PUBLIC: the ref step fetches the tag "
    "from it with no credentials, as the model does, and the migration "
    "creates it public.",
    # Brett Heap's acts as the header words them: each environment's
    # settings, how little of them the build reads, and what the ruleset on
    # the tags `v*` allows. spec.md, contracts/workflows.md and the proposal
    # state the same settings, so a header sentence that changes here is one
    # that changes there
    "The build refuses every dispatch until both environments exist with a "
    "required reviewer and the deployment limit, and no job reads more of "
    "these acts than that.",
    "each with brettheap as the required reviewer, self-review allowed, "
    "administrators not bypassing, and a deployment limit of exactly one tag "
    "rule, `v*`.",
    "Only that a required reviewer is named (any, not brettheap in "
    "particular) and the limit are checked here (FR-029).",
    "only the admin role creates, moves or deletes one")


@NEEDS_UPSTREAM
def test_release_header_carries_the_six_releasing_sections_in_order():
    """THE RELEASING HEADER (FR-034, contracts/workflows.md "The header"): six
    sections, in order, each found after the one before it."""
    text = header()
    at = 0
    for phrase in HEADER_SECTIONS:
        found = text.find(phrase, at)
        assert found != -1, (
            f"the header carries no {phrase!r} after its earlier sections")
        at = found + len(phrase)


@NEEDS_UPSTREAM
@pytest.mark.parametrize("phrase", HEADER_CARRIES)
def test_release_header_says_what_releasing_needs(phrase):
    """The procedure's commands verbatim, its approval step, the branch and
    tag policy's terms, the rehearsal branch, both repositories and both
    environments, the missing pypi.org publisher, the second line of
    defence, and Brett Heap's acts as the header words them: each
    environment's settings, how little of them the build reads, and what the
    tag ruleset allows."""
    assert phrase in header(), f"the RELEASING header never says {phrase!r}"


#: A row of the guard's table as release.yml writes it, in the header and
#: above step 1: who, on which ref, which version, and what is uploaded.
TABLE_ROW = re.compile(
    r"(opensoft/openRepoTools-code|opensoft/openRepoTools|any other repository"
    r"|any repository)\s+(a tag|a branch)\s+(X\.Y\.ZrcN|X\.Y\.Z|any)\s+(\S.*)")
TABLE_OUTCOMES = {"TestPyPI, then PyPI": ("true", "true"),
                  "TestPyPI alone": ("true", "false"), "refused": None,
                  "nothing: the rehearsal": ("false", "false")}


def guard_tables() -> List[Tuple[int, Dict[Tuple[str, str, str], Optional[Tuple[str, str]]]]]:
    """Each run of comment lines in release.yml that are rows of the guard's
    table: its first line's number, and `{(who, ref, version): (to-testpypi,
    to-pypi)}`, `None` where the row says refused."""
    tables: list = []
    rows: Optional[dict] = None
    for number, line in enumerate(WORKFLOW.read_text(encoding="utf-8").splitlines(), 1):
        text = line.strip()
        found = TABLE_ROW.fullmatch(text[1:].strip()) if text.startswith("#") else None
        if not found:
            rows = None
            continue
        if rows is None:
            rows = {}
            tables.append((number, rows))
        key, outcome = found.group(1, 2, 3), found.group(4)
        assert key not in rows, f"line {number} writes the row {key} again"
        assert outcome in TABLE_OUTCOMES, f"line {number}: {outcome!r}"
        rows[key] = TABLE_OUTCOMES[outcome]
    return tables


def table_key(repository: str, ref: str, version: str) -> Optional[Tuple[str, str, str]]:
    """The table row a guard case falls under, or None for a ref that is
    neither a tag nor a branch, which the table does not list."""
    if ref.startswith("refs/heads/"):
        return ("any repository", "a branch", "any")
    if not ref.startswith("refs/tags/"):
        return None
    if repository in (CODE_LEG, THIS_REPOSITORY):
        return (repository, "a tag", "X.Y.ZrcN" if "rc" in version else "X.Y.Z")
    return ("any other repository", "a tag", "any")


@NEEDS_UPSTREAM
def test_release_header_s_guard_table_is_the_guard_s_own_decisions():
    """THE TABLE IS THE GUARD (FR-048): release.yml writes the guard's table
    twice, in the header's WHERE RELEASES COME FROM and above step 1, and each
    row says what `GUARD_ROWS`, which the guard is run under, decides for
    every case that falls under it. Every row has a case, and every case on
    a tag or a branch has its row."""
    release()
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(n for n, line in enumerate(lines, 1) if re.match(r"^on\s*:", line))
    tables = guard_tables()
    assert [number < start for number, _ in tables] == [True, False], (
        f"the guard's table is written at lines {[n for n, _ in tables]}, not "
        f"once in the header (before line {start}) and once above step 1")
    for number, rows in tables:
        reached = set()
        for case in GUARD_ROWS:
            repository, ref, version, decision = case.values
            key = table_key(repository, ref, version)
            if key is None:
                continue
            assert key in rows, f"the table at line {number} has no row {key}"
            assert rows[key] == decision, (
                f"the table at line {number} says {key} gives {rows[key]}, and "
                f"the guard decides {decision} for {case.id}")
            reached.add(key)
        assert reached == set(rows), (
            f"rows at line {number} no guard case reaches: {set(rows) - reached}")
