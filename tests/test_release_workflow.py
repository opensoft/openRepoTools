# SPDX-License-Identifier: Apache-2.0
"""`.github/workflows/release.yml`, its two hash locks and its stamp writer
(opensoft/openRepoTools#228, User Story 5).

THE RELEASE IS HELD OFFLINE. The workflow builds the wheel, uploads it to
TestPyPI, checks the install on three legs and uploads it to PyPI, and
nothing here runs it. What can be held with no network is the file itself,
read with the PINNED standard's `repo_shape.load_yaml` (research R9), and the
scripts it carries: every one whose outcome decides what is built or
uploaded is RUN here, as GitHub runs a step, under a fake `gh` that answers as
the forge does. contracts/workflows.md's `release.yml` list is the
specification, one prefix per part of it (plan.md, "The test layout"):

- `test_release_trigger_*`: a dispatch with `version` is the only trigger, no
  permission is granted at the top, one release runs at a time, and the input
  reaches every script through the environment alone;
- `test_release_lock_*`: both hash locks, one version per entry by sha256,
  hatchling at `pyproject.toml`'s pin, and pipx 1.11.1 below Python 3.10 and
  1.17.8 from 3.10;
- `test_release_build_*`: the build job's checkout, pins, steps and order;
  the ref step and the branch step held to the rehearsal rule; the gate on
  `tests.yml`'s four jobs and the digest step, each run under a forge, the
  digest step also in a copy of the checkout whose standard or pin names
  another definition; step 13's wheel check run on synthetic wheels made from
  HEAD's blobs; and the digest label, one literal in the installer, the pin
  and the standard;
- `test_release_stamp_writer_*`: the build's own stamp writer, run on a copy
  of the committed stamp and read back by `--version` from a `package_tree`;
- `test_release_guard_build_*` and `test_release_guard_upload_*` (FR-048):
  the repository guard, run under each row of contracts/workflows.md's table,
  and each upload job's own first step;
- `test_release_upload_*`: the four jobs' permissions, the two environments,
  the two conditions, and each upload job's checks around the pinned action;
- `test_release_install_check_*`: the three legs and what each runs;
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
`REPOSITORY` (contracts/stamp.md) and, as the model's do, from `GITHUB_SHA`
and `GITHUB_REPOSITORY`, which carry the same values.

WITHOUT THE SUBMODULE every test that reads YAML or the standard SKIPS, as the
command tests do (`NEEDS_UPSTREAM`), and a composed run fails instead. Nothing
here reads `specs/`, which goes to the spec leg at the cutover.
"""

from __future__ import annotations

import base64
import difflib
import functools
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
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
INSTALL_LEGS = [("ubuntu-latest", "3.x"), ("macos-latest", "3.x"),
                ("ubuntu-latest", "3.9")]

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
#: runs`, honouring `head_sha` and `event` where the query names them) and a
#: run's jobs (`actions/runs/<id>/jobs`). `--jq '.<key>[]'` answers one object
#: per line, as gh does; no `--jq` answers the page.
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
    for name in ("head_sha", "event"):
        if name in params:
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
    workflow = release()
    data = tmp_path / "forge.json"
    data.write_text(json.dumps({"runs": runs, "jobs": {str(k): v for k, v
                                                       in jobs.items()}}),
                    encoding="utf-8")
    forge = python_tool(tmp_path / "forge", "gh", RUNS_FORGE)
    values = {"GITHUB_REPOSITORY": CODE_LEG, "GITHUB_SHA": GATE_SHA,
              "VERSION": "1.1.0", "FORGE_DATA": str(data),
              "FORGE_LOG": str(tmp_path / "forge.log"),
              "FORGE_REPOSITORY": CODE_LEG}
    runner = Runner(tmp_path / "work", workflow, "build", values, forge)
    done = runner.run(named(workflow, "build", GATE_STEP))
    assert (done.returncode == 0) == passes, transcript(done)
    if names:
        assert names in done.stdout + done.stderr, (
            f"the refusal does not name {names}:\n{transcript(done)}")


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
    def change(members: dict, info: str) -> None:
        assert member not in members, f"the case is wrong: {member} is HEAD's"
        members[member] = (data, 0o644)
    return change


def a_line_more_in_the_stamp(members: dict, info: str) -> None:
    """The stamp with a comment line after its last: its five assignments are
    still the release's, and its bytes are not the committed file stamped."""
    data, mode = members["openrepotools/_release.py"]
    members["openrepotools/_release.py"] = (
        data + b"# a line the committed stamp does not have\n", mode)


#: THE SYNTHETIC WHEELS THAT ARE NOT THE COMMIT'S: contracts/workflows.md's
#: four, then one for each other check the step makes (contracts/wheel.md's
#: checks 2 to 5, and the run's values). Each is `(what its refusal must
#: name, the change to the wheel as built, the mode HEAD gives the file
#: changed, the run's values where they are not the release's)`.
NOT_THE_COMMITS = {
    "no-licenses-LICENSE": ("LICENSE", no_license, None, None),
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
    committed file stamped though its five values are the release's, and the
    wheel as built checked in a run of another repository. Each fails, and
    among the lines it prints beyond the wheel as built's is one naming what
    is wrong."""
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
    assert [line for line in new if names in line], (
        f"no line of the refusal names {names}:\n{transcript(bad)}")


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


#: The bytes the build recorded, and other bytes under the same name.
RECORDED_WHEEL = b"PK\x03\x04 the wheel the build job verified\n"
OTHER_WHEEL = b"PK\x03\x04 another file under the wheel's name\n"

#: `(the files in the job's wheel directory, whether the step passes)`.
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


@NEEDS_UPSTREAM
@pytest.mark.parametrize("which", WHEEL_DIGEST_CASES)
def test_release_install_check_the_digest_step_passes_the_recorded_wheel_alone(
        tmp_path, which):
    """THE STEP, RUN (contracts/workflows.md's install step 1): its heredoc,
    over the job's wheel directory, passes the one file named `$WHEEL` whose
    sha256 is `$WHEEL_SHA256`, and refuses other bytes under that name,
    another file beside it, another name, and nothing at all, so the install
    check never runs a file the build did not verify."""
    files, passes = WHEEL_DIGEST_CASES[which]
    wheel = "openrepotools-1.1.0rc1-py3-none-any.whl"
    temp = tmp_path / "runner-temp"
    (temp / "wheel").mkdir(parents=True)
    for name, data in files.items():
        (temp / "wheel" / name.replace("<wheel>", wheel)).write_bytes(data)
    values = {"RUNNER_TEMP": str(temp), "WHEEL": wheel,
              "WHEEL_SHA256": hashlib.sha256(RECORDED_WHEEL).hexdigest()}
    step = named(release(), "install", WHEEL_DIGEST_STEP)
    done = run_heredoc(step, tmp_path / "run", [], values, cwd=tmp_path)
    assert (done.returncode == 0) == passes, transcript(done)
    if not passes:
        out = done.stdout + done.stderr
        assert "::error::" in out and "Traceback" not in out, transcript(done)


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


@NEEDS_UPSTREAM
def test_release_install_check_the_offline_install_is_the_package_job_s_but_for_the_fingerprint():
    """THE TWO COPIES CANNOT DRIFT (FR-016, FR-032): the install check's
    offline `--install` is `tests.yml`'s `package` job's, line for line, with
    the same keys beside its script, and differs from it only in
    `FINGERPRINT_LINES`, each named there. So a count line, a skip line or a
    receipt count changed in one copy alone fails here, before a release
    tests what `tests.yml` never did and burns the version on TestPyPI."""
    ours = offline_install_step(install_steps(release()),
                                "release.yml's install job")
    package = (standard().load_yaml(TESTS_WORKFLOW).get("jobs") or {}).get("package")
    if not isinstance(package, dict) or not isinstance(package.get("steps"), list):
        pytest.fail("tests.yml has no `package` job with steps", pytrace=False)
    theirs = offline_install_step(package["steps"], "tests.yml's package job")
    keys = {k: v for k, v in ours.items() if k not in ("name", "run")}
    assert keys == {k: v for k, v in theirs.items() if k not in ("name", "run")}, (
        f"the two steps differ beside their scripts: {ours} against {theirs}")
    mine, its = run_text(ours).split("\n"), run_text(theirs).split("\n")
    matcher = difflib.SequenceMatcher(a=its, b=mine, autojunk=False)
    found = [(its[i1:i2], mine[j1:j2])
             for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]
    allowed = [(list(a), list(b)) for a, b in FINGERPRINT_LINES]
    assert found == allowed, (
        "the release's offline --install is not tests.yml's but for the "
        "fingerprint lines:\n" + "\n".join(difflib.unified_diff(
            its, mine, "tests.yml", "release.yml", lineterm="", n=0)))


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
    "opensoft/openRepoTools", "pypi.org publisher", "testpypi", "pypi")


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
    """The procedure's commands verbatim, the branch and tag policy's terms,
    the rehearsal branch, both repositories and both environments, and the
    missing pypi.org publisher, the second line of defence."""
    assert phrase in header(), f"the RELEASING header never says {phrase!r}"
