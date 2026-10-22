# SPDX-License-Identifier: Apache-2.0
"""`.github/workflows/lint.yml`: the job that runs actionlint and shellcheck (#277).

OFFLINE, LIKE THE REST OF THIS SUITE. Before the file existed no CI job ran
either tool, so lane openRepoTools-2's three mutants of `release.yml` (I4, I13
and N3, which actionlint's own shellcheck rule flags) were shown nowhere. What
these tests hold is the file's contract, and they run its steps instead of only
reading them, under fakes, so nothing is fetched and neither tool is needed:

- the workflow is a file of its own: `tests.yml` is the release gate's file,
  with exactly four jobs, and rehearsal D rewrites it for the code leg;
- both tools are pinned by version and by sha256, and the install step unpacks
  an archive only after `sha256sum --strict -c` has accepted it (run, over
  fake archives: a genuine one, a tampered one of each tool, and a tool that
  says another version);
- the actionlint step has no exclusion and no config file, runs with the
  pinned shellcheck by path, and fails when actionlint reports its shellcheck
  rule disabled (run, under a fake actionlint); the header says to re-check
  that message on every actionlint bump;
- the shellcheck step finds the shell scripts by shebang and holds the
  baseline the file's header documents: twelve named scripts at
  `--severity=warning` less ten codes, every other script at every severity,
  and `tests/test_lane_helpers.sh` not run (run, in a throwaway git
  repository, under a fake shellcheck). It does not die on an empty tracked
  file or on one with no final newline, and it fails closed, naming the file,
  on a first line that is a shebang naming bash or sh in a form it does not
  select;
- the job has a `timeout-minutes` of 20, and the header names the runner its
  16 GB figure assumes and the memory print that diagnoses it;
- the header's table of excluded codes is the step's `excluded` list, its
  totals agree with each other, and the named scripts are tracked bash files.

The workflow is read with the PINNED STANDARD'S OWN `repo_shape.load_yaml`, as
`tests/test_tests_workflow.py` reads `tests.yml`, so a construct outside that
subset fails here first. Without the submodule those tests SKIP, naming it. The
tests that read the file as text, or the repository's own tracked files, need
no submodule.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from conftest import NEEDS_UPSTREAM, REPO, UPSTREAM, WINDOWS_SKIP

WORKFLOW = REPO / ".github" / "workflows" / "lint.yml"
PINNED_READER = UPSTREAM / "scripts" / "repo_shape.py"

#: The commit every job in this repository pins `actions/checkout` at.
CHECKOUT = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"

#: THE TWO TOOLS, as the install step pins them. A bump moves this table, the
#: workflow and the header together, so it is written out here and never read
#: back from the workflow: a pin that moved without this file is a failure.
ACTIONLINT = {
    "version": "1.7.12",
    "sha256": "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
    "archive": "actionlint_1.7.12_linux_amd64.tar.gz",
    "url": "https://github.com/rhysd/actionlint/releases/download/v1.7.12/"
           "actionlint_1.7.12_linux_amd64.tar.gz",
}
SHELLCHECK = {
    "version": "0.11.0",
    "sha256": "8c3be12b05d5c177a04c29e3c78ce89ac86f1595681cab149b65b97c4e227198",
    "archive": "shellcheck-v0.11.0.linux.x86_64.tar.xz",
    "url": "https://github.com/koalaman/shellcheck/releases/download/v0.11.0/"
           "shellcheck-v0.11.0.linux.x86_64.tar.xz",
}
INSTALL_ENV = {
    "ACTIONLINT_VERSION": ACTIONLINT["version"],
    "ACTIONLINT_SHA256": ACTIONLINT["sha256"],
    "SHELLCHECK_VERSION": SHELLCHECK["version"],
    "SHELLCHECK_SHA256": SHELLCHECK["sha256"],
}

#: THE BASELINE, measured on main `33ce26d` with the two pinned tools: the
#: ten codes the twelve baselined scripts fire at warning level, and the
#: twelve scripts (the same ten codes and twelve scripts as on `a42946e`, its
#: first measure). `park`, `resume` and `status` have no finding at all, so
#: they and every script added later are held to every severity.
EXCLUDED_CODES = ("SC1007", "SC2034", "SC2069", "SC2088", "SC2128", "SC2141",
                  "SC2154", "SC2178", "SC2209", "SC2318")
BASELINED = ("claude-current", "claude-restart-check", "lane", "lane-end",
             "lane-handoff", "lane-rename", "lane-start", "lanes",
             "lanes-edit.sh", "link-estates", "openRepoTools", "tests/run.sh")
CLEAN_SCRIPTS = ("park", "resume", "status")
#: The lane helpers' own suite: 1.1 MB of bash that nothing ships, and
#: shellcheck needs 16.2 GB for it (measured on `a42946e`; the file is the
#: same on `33ce26d`), more than a 16 GB runner has.
NOT_RUN = "tests/test_lane_helpers.sh"

NEEDS_BASH = pytest.mark.skipif(shutil.which("bash") is None,
                                reason="the lint job's steps are bash")
NEEDS_TOOLS = pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("git", "sha256sum", "tar", "xz")),
    reason="the lint job's steps need git, sha256sum, tar and xz")

#: Everything foreign a runner would not hand a step.
FOREIGN_PREFIXES = ("GITHUB_", "RUNNER_", "LANES_", "TMUX", "WORKBENCHES_",
                    "ACTIONLINT_", "SHELLCHECK_")


# --- reading the workflow -------------------------------------------------------

def pinned_reader():
    """The pinned openRepoShape's `scripts/repo_shape.py`, loaded from its
    own file under a name of this module's, so no other module's
    `repo_shape` can stand in for it."""
    spec = importlib.util.spec_from_file_location(
        "_lint_workflow_repo_shape", str(PINNED_READER))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def workflow() -> dict:
    """`lint.yml`, read by the pinned `load_yaml`. A refusal fails the test
    that asked, naming it: a construct outside the standard's subset is the
    workflow's to fix, not this suite's to read around."""
    if not WORKFLOW.is_file():
        pytest.fail(f"{WORKFLOW} does not exist: #277 adds the job that runs "
                    "actionlint and shellcheck, in a workflow file of its own",
                    pytrace=False)
    reader = pinned_reader()
    try:
        loaded = reader.load_yaml(WORKFLOW)
    except reader.Refusal as refusal:
        pytest.fail(f"the pinned load_yaml refuses {WORKFLOW.name}: {refusal}. "
                    "lint.yml must stay inside openRepoShape's YAML subset",
                    pytrace=False)
    assert isinstance(loaded, dict), f"{WORKFLOW.name} is not a mapping"
    return loaded


def lint_job(workflow: dict) -> dict:
    job = (workflow.get("jobs") or {}).get("lint")
    assert isinstance(job, dict), "lint.yml has no `lint` job"
    assert isinstance(job.get("steps"), list), "the lint job has no steps"
    return job


def step_running(workflow: dict, needle: str) -> dict:
    """The one step whose `run:` holds `needle`: a step is found by what it
    does and never by its `name:`."""
    hits = [step for step in lint_job(workflow)["steps"]
            if needle in str(step.get("run", ""))]
    assert len(hits) == 1, f"{len(hits)} steps run {needle!r}, not one"
    return hits[0]


def install_step(workflow: dict) -> dict:
    return step_running(workflow, "sha256sum --strict -c")


def actionlint_step(workflow: dict) -> dict:
    return step_running(workflow, "actionlint -verbose")


def shellcheck_step(workflow: dict) -> dict:
    return step_running(workflow, "git ls-files -z")


def header_of(text: str) -> str:
    """The comment block above `on:`, as one line of words."""
    lines = text.split("\non:\n", 1)[0].splitlines()
    return " ".join(line.lstrip("#").strip() for line in lines
                    if line.startswith("#"))


def tracked(path: str) -> bool:
    done = subprocess.run(["git", "ls-files", "--error-unmatch", "--", path],
                          cwd=str(REPO), capture_output=True, check=False)
    return done.returncode == 0


# --- running a step -------------------------------------------------------------

class Runner:
    """What the runner gives a step, under `root`: a `RUNNER_TEMP`, a
    `GITHUB_PATH` file, a HOME, and a PATH that starts with the directories
    the test names. Bash runs the script as `bash -e`, which is what a `run:`
    with no `shell:` gets on Linux."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.temp = root / "runner-temp"
        self.home = root / "home"
        self.bin = self.temp / "lint-tools" / "bin"
        for directory in (self.temp, self.home, self.bin):
            directory.mkdir(parents=True)
        self.github_path = root / "github_path.txt"
        self.github_path.write_text("", encoding="utf-8")

    def environ(self, step: dict, front: tuple, extra: dict | None) -> dict:
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(FOREIGN_PREFIXES)
               and key not in ("BASH_ENV", "ENV")}
        env.update({"HOME": str(self.home), "RUNNER_TEMP": str(self.temp),
                    "GITHUB_PATH": str(self.github_path), "CI": "true",
                    "GIT_CONFIG_GLOBAL": os.devnull, "LC_ALL": "C",
                    "PATH": os.pathsep.join(
                        [str(directory) for directory in front]
                        + [env.get("PATH", "")])})
        for key, value in (step.get("env") or {}).items():
            env[key] = str(value)
        env.update(extra or {})
        return env

    def run(self, step: dict, cwd: Path, front: tuple = (),
            extra: dict | None = None):
        script = self.root / "step.sh"
        script.write_text(str(step["run"]), encoding="utf-8")
        return subprocess.run(["bash", "-e", str(script)], cwd=str(cwd),
                              env=self.environ(step, front, extra),
                              capture_output=True, text=True, timeout=120,
                              check=False)


def shown(done) -> str:
    return (f"exit {done.returncode}\n--- stdout ---\n{done.stdout}"
            f"\n--- stderr ---\n{done.stderr}")


def write_executable(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


# --- the workflow's shape ---------------------------------------------------------

@NEEDS_UPSTREAM
def test_lint_yml_is_a_workflow_of_its_own_with_the_one_job_lint(workflow):
    """The job is NOT in `tests.yml`: that file is the release gate's, with
    exactly four jobs, and rehearsal D rewrites it for the code leg. So the
    job is `lint` in `lint.yml`, on ubuntu-24.04 as every ubuntu job here is
    since #296 (`ubuntu-latest` became Ubuntu 26.04 on 2026-10-21), with no
    `if:`, so that every trigger runs it, and no `continue-on-error:`, which
    would make a lint that cannot fail."""
    assert workflow.get("name") == "lint", workflow.get("name")
    assert sorted(workflow.get("jobs") or {}) == ["lint"], sorted(workflow["jobs"])
    job = lint_job(workflow)
    assert job.get("runs-on") == "ubuntu-24.04", job.get("runs-on")
    for key in ("if", "needs", "strategy", "continue-on-error"):
        assert key not in job, f"the lint job has `{key}:`"
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "continue-on-error" not in text, "lint.yml names `continue-on-error`"
    assert [step for step in job["steps"] if "if" in step] == [], \
        "a lint step has an `if:`"


@NEEDS_UPSTREAM
def test_lint_yml_job_ends_a_hung_step_after_twenty_minutes(workflow):
    """`timeout-minutes: 20` on the job, so that a download that hangs or a
    shellcheck that does not return ends the run, where GitHub's own default
    would hold the runner for 360 minutes. The shellcheck step took about
    three minutes on the review's machine, `lanes-edit.sh` alone about two,
    so 20 leaves room for a slower runner and a retried download. The number
    is written here so that moving it is a decision and not a drift."""
    timeout = lint_job(workflow).get("timeout-minutes")
    assert timeout == 20, timeout


@NEEDS_UPSTREAM
def test_lint_yml_runs_on_pull_requests_main_release_branches_and_dispatch(workflow):
    """`pull_request` with GitHub's own types, `push` to `main` and every
    `release/v*` branch as `tests.yml` has it, and `workflow_dispatch`. No
    schedule: the tools are pinned, so a night changes nothing. No
    `pull_request_target`, which would run this file with a token the pull
    request's author does not hold."""
    assert workflow.get("on") == {
        "pull_request": None,
        "push": {"branches": ["main", "release/v*"]},
        "workflow_dispatch": None}, workflow.get("on")


@NEEDS_UPSTREAM
def test_lint_yml_reads_the_repository_and_nothing_else(workflow):
    """`contents: read` and no more, at the job and nowhere widened above it;
    the one action is the pinned checkout, by commit, at the options that
    keep the token out of the checkout's git config and fetch no submodule."""
    job = lint_job(workflow)
    assert job.get("permissions") == {"contents": "read"}, job.get("permissions")
    assert workflow.get("permissions") in (None, {}), workflow.get("permissions")
    uses = [step["uses"] for step in job["steps"] if "uses" in step]
    assert uses == [CHECKOUT], uses
    checkout = next(step for step in job["steps"] if "uses" in step)
    assert checkout.get("with") == {"submodules": False, "fetch-depth": 1,
                                    "persist-credentials": False}, checkout
    text = WORKFLOW.read_text(encoding="utf-8")
    assert not re.search(r"\b(id-token|packages|pull-requests|actions|checks)\s*:\s*write", text)
    assert re.search(r"^\s*- uses: " + re.escape(CHECKOUT) + r"  # v4$", text, re.M), \
        "the checkout's tag is not written beside its commit, as every job writes it"


@NEEDS_UPSTREAM
def test_lint_yml_steps_install_then_actionlint_then_shellcheck(workflow):
    steps = lint_job(workflow)["steps"]
    where = [steps.index(install_step(workflow)),
             steps.index(actionlint_step(workflow)),
             steps.index(shellcheck_step(workflow))]
    assert where == sorted(where) and where[0] >= 1, where
    assert len(steps) == 4, f"the lint job has {len(steps)} steps, not four"


# --- the pins ---------------------------------------------------------------------

@NEEDS_UPSTREAM
def test_lint_yml_pins_each_tool_by_version_and_sha256(workflow):
    """Each tool is a release archive at one exact version, with the sha256
    this table holds, from its own project's release page and nowhere else. A
    pin that moves moves this table with it, and the digests are each 64 hex
    digits, written by hand from the archive and never from a tag."""
    step = install_step(workflow)
    assert {key: str(value) for key, value in step["env"].items()} == INSTALL_ENV
    for key in ("ACTIONLINT_SHA256", "SHELLCHECK_SHA256"):
        assert re.fullmatch(r"[0-9a-f]{64}", INSTALL_ENV[key]), key
    script = step["run"]
    assert ('"https://github.com/rhysd/actionlint/releases/download/'
            'v${ACTIONLINT_VERSION}/$actionlint_archive"') in script
    assert ('"https://github.com/koalaman/shellcheck/releases/download/'
            'v${SHELLCHECK_VERSION}/$shellcheck_archive"') in script
    assert 'actionlint_archive="actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz"' in script
    assert 'shellcheck_archive="shellcheck-v${SHELLCHECK_VERSION}.linux.x86_64.tar.xz"' in script
    assert script.count("--proto '=https'") == 2 and script.count("--tlsv1.2") == 2
    assert not re.search(r"\b(apt-get|apt|pip|pip3|pipx|npm|brew|snap|cargo)\b"
                         r"|go install|docker pull", script), \
        "a tool is installed from somewhere other than its pinned release archive"


# --- the install step, run -------------------------------------------------------

ACTIONLINT_SCRIPT = (
    "#!/bin/sh\n"
    'case "$1" in -version) printf \'%s\\n\' "{version}" '
    '"installed by downloading from release page" ;; esac\n')
SHELLCHECK_SCRIPT = (
    "#!/bin/sh\n"
    'case "$1" in --version) printf \'%s\\n\' '
    '"ShellCheck - shell script analysis tool" "version: {version}" ;; esac\n')

#: A `curl` that serves the fixture archive named by the URL's last segment,
#: and writes down each URL it was asked for. Nothing reaches a network.
FAKE_CURL = r"""#!/bin/sh
out=
url=
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    --proto|--retry|--retry-delay) shift 2 ;;
    -*) shift ;;
    *) url="$1"; shift ;;
  esac
done
printf '%s\n' "$url" >> "$FAKE_CURL_LOG"
name="${url##*/}"
if [ ! -f "$FAKE_SERVE/$name" ]; then
  echo "fake curl: no fixture for $url" >&2
  exit 22
fi
cp "$FAKE_SERVE/$name" "$out"
"""


def add_file(archive: tarfile.TarFile, name: str, text: str,
             mode: int = 0o755) -> None:
    data = text.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size, info.mode, info.mtime = len(data), mode, 0
    archive.addfile(info, io.BytesIO(data))


def build_archives(serve: Path, actionlint_says: str = ACTIONLINT["version"],
                   shellcheck_says: str = SHELLCHECK["version"],
                   tamper: str | None = None) -> dict:
    """Fake archives under the names the pins give them, holding fake tools
    that say the versions asked for. `tamper` names a tool whose archive gets
    one member more, which makes its sha256 another one. Returns each
    archive's sha256, as the install step would be given it."""
    pytest.importorskip("lzma")
    serve.mkdir(parents=True, exist_ok=True)
    # THE GZIP HEADER CARRIES A TIME, so a second build of the same archive is
    # another file unless the time is fixed: the digests below must be the
    # same on every build of the same members.
    packed = io.BytesIO()
    with gzip.GzipFile(fileobj=packed, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            add_file(archive, "actionlint",
                     ACTIONLINT_SCRIPT.format(version=actionlint_says))
            add_file(archive, "README.md", "a readme\n", mode=0o644)
            if tamper == "actionlint":
                add_file(archive, "evil", "tampered\n")
    (serve / ACTIONLINT["archive"]).write_bytes(packed.getvalue())
    top = f"shellcheck-v{SHELLCHECK['version']}"
    with tarfile.open(serve / SHELLCHECK["archive"], "w:xz") as archive:
        add_file(archive, f"{top}/shellcheck",
                 SHELLCHECK_SCRIPT.format(version=shellcheck_says))
        add_file(archive, f"{top}/README.txt", "a readme\n", mode=0o644)
        if tamper == "shellcheck":
            add_file(archive, f"{top}/evil", "tampered\n")
    return {name: hashlib.sha256((serve / tool["archive"]).read_bytes()).hexdigest()
            for name, tool in (("actionlint", ACTIONLINT), ("shellcheck", SHELLCHECK))}


def run_install(workflow: dict, root: Path, served: dict | None = None,
                pinned_are_served: bool = True):
    """The install step over fixture archives, with `served` as what
    `build_archives` is asked for. The step is given as its pins either the
    digests of what is served, which is an archive that is what the pin says,
    or the digests of a genuine build that is not what is served, which is an
    archive that is not."""
    runner = Runner(root)
    serve = root / "serve"
    digests = build_archives(serve, **(served or {}))
    if not pinned_are_served:
        digests = build_archives(root / "genuine")
    write_executable(root / "fakes" / "curl", FAKE_CURL)
    done = runner.run(
        install_step(workflow), cwd=root, front=(root / "fakes",),
        extra={"FAKE_SERVE": str(serve), "FAKE_CURL_LOG": str(root / "curl.log"),
               "ACTIONLINT_SHA256": digests["actionlint"],
               "SHELLCHECK_SHA256": digests["shellcheck"]})
    log = root / "curl.log"
    asked = log.read_text(encoding="utf-8").split() if log.is_file() else []
    return done, runner, asked


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@NEEDS_TOOLS
def test_lint_yml_install_step_fetches_each_pinned_archive_and_puts_both_tools_on_path(
        workflow, tmp_path):
    """The step over archives that are what the pins say: it asks for exactly
    the two pinned URLs, in that order, unpacks both tools into one directory
    under `$RUNNER_TEMP`, and puts that directory on the steps' PATH."""
    done, runner, asked = run_install(workflow, tmp_path)
    assert done.returncode == 0, shown(done)
    assert asked == [ACTIONLINT["url"], SHELLCHECK["url"]], asked
    for tool in ("actionlint", "shellcheck"):
        binary = runner.bin / tool
        assert binary.is_file() and os.access(binary, os.X_OK), f"{binary} is not placed"
    assert runner.github_path.read_text(encoding="utf-8").split() == [str(runner.bin)]


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@NEEDS_TOOLS
@pytest.mark.parametrize("tampered", ["actionlint", "shellcheck"])
def test_lint_yml_install_step_unpacks_nothing_whose_sha256_is_not_the_pin(
        workflow, tmp_path, tampered):
    """An archive that is not the pinned one is refused BEFORE it is unpacked:
    the step fails on the digest, the tool is not in the bin directory, and
    where the first archive failed the second is never asked for. The step is
    given the digests of the genuine fixtures, and the archive served for
    `tampered` has one member more."""
    done, runner, asked = run_install(workflow, tmp_path,
                                      served={"tamper": tampered},
                                      pinned_are_served=False)
    assert done.returncode != 0, shown(done)
    assert "FAILED" in done.stdout, shown(done)
    assert not (runner.bin / tampered).exists(), f"{tampered} was unpacked unchecked"
    if tampered == "actionlint":
        assert asked == [ACTIONLINT["url"]], asked
        assert not (runner.bin / "shellcheck").exists()
    else:
        assert asked == [ACTIONLINT["url"], SHELLCHECK["url"]], asked


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@NEEDS_TOOLS
@pytest.mark.parametrize("which", ["actionlint", "shellcheck"])
def test_lint_yml_install_step_refuses_a_tool_that_says_another_version(
        workflow, tmp_path, which):
    """A digest that matches and a binary that says another version is still
    refused, and the message names the pin: the unpacked tool is the one the
    version names."""
    served = ({"actionlint_says": "1.7.99"} if which == "actionlint"
              else {"shellcheck_says": "0.9.0"})
    pin = (ACTIONLINT if which == "actionlint" else SHELLCHECK)["version"]
    done, _, _ = run_install(workflow, tmp_path, served=served)
    assert done.returncode != 0, shown(done)
    assert f"::error::the unpacked {which} says" in done.stdout, shown(done)
    assert f"the pin is {pin}" in done.stdout, shown(done)


# --- the actionlint step ---------------------------------------------------------

#: A fake actionlint that writes down its arguments and acts out a mode.
FAKE_ACTIONLINT = r"""#!/bin/sh
printf '%s\n' "$*" >> "$FAKE_ACTIONLINT_LOG"
case "$FAKE_ACTIONLINT_MODE" in
  clean) echo 'verbose: Found 0 errors in 3 files' >&2 ;;
  findings)
    echo '.github/workflows/release.yml:460:9: shellcheck reported issue in this script: SC2317:info:2:1: Command appears to be unreachable [shellcheck]'
    exit 1 ;;
  disabled)
    echo 'verbose: Rule "shellcheck" was disabled: exec: "shellcheck": executable file not found in $PATH' >&2 ;;
esac
"""


@NEEDS_UPSTREAM
def test_lint_yml_actionlint_step_has_no_exclusion_and_no_config(workflow):
    """The workflows carry no baseline: main is clean, so the step has no
    `-ignore`, no config file and no file list, `.github/` holds no actionlint
    config that would add one, and the repository root holds no
    `.shellcheckrc`, which would change the baseline the header documents."""
    script = actionlint_step(workflow)["run"]
    assert 'actionlint -verbose -shellcheck="$shellcheck_bin" >' in script, script
    for flag in ("-ignore", "-config-file", "-init-config", "-pyflakes"):
        assert flag not in script, f"the actionlint step passes {flag}"
    for name in ("actionlint.yaml", "actionlint.yml"):
        assert not (REPO / ".github" / name).exists(), \
            f".github/{name} would add exclusions the file's header says are none"
    assert not (REPO / ".shellcheckrc").exists(), \
        "a .shellcheckrc would change the baseline the workflow documents"


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@pytest.mark.parametrize("mode, code, said", [
    ("clean", 0, None),
    ("findings", 1, "SC2317"),
    ("disabled", 1, "::error::actionlint ran without its shellcheck rule"),
])
def test_lint_yml_actionlint_step_fails_on_a_finding_and_on_a_disabled_shellcheck_rule(
        workflow, tmp_path, mode, code, said):
    """The step over a fake actionlint: its own exit status is the step's, and
    an actionlint that reports its shellcheck rule disabled, which it does
    silently when it cannot start the binary, fails the step although it
    exited 0. It is always given the pinned shellcheck by path and nothing
    else."""
    runner = Runner(tmp_path)
    write_executable(runner.bin / "shellcheck", "#!/bin/sh\nexit 0\n")
    write_executable(runner.bin / "actionlint", FAKE_ACTIONLINT)
    done = runner.run(actionlint_step(workflow), cwd=tmp_path, front=(runner.bin,),
                      extra={"FAKE_ACTIONLINT_MODE": mode,
                             "FAKE_ACTIONLINT_LOG": str(tmp_path / "args.log")})
    assert done.returncode == code, shown(done)
    if said:
        assert said in done.stdout, shown(done)
    args = (tmp_path / "args.log").read_text(encoding="utf-8").splitlines()
    assert args == [f"-verbose -shellcheck={runner.bin / 'shellcheck'}"], args


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
def test_lint_yml_actionlint_step_refuses_a_shellcheck_that_is_not_the_pinned_one(
        workflow, tmp_path):
    """The runner image carries a shellcheck of its own, and a PATH that finds
    it first would run the workflows through whatever version the image has
    that week. The step fails before it runs actionlint at all."""
    runner = Runner(tmp_path)
    write_executable(runner.bin / "shellcheck", "#!/bin/sh\nexit 0\n")
    write_executable(runner.bin / "actionlint", FAKE_ACTIONLINT)
    write_executable(tmp_path / "image" / "shellcheck", "#!/bin/sh\nexit 0\n")
    done = runner.run(actionlint_step(workflow), cwd=tmp_path,
                      front=(tmp_path / "image", runner.bin),
                      extra={"FAKE_ACTIONLINT_MODE": "clean",
                             "FAKE_ACTIONLINT_LOG": str(tmp_path / "args.log")})
    assert done.returncode == 1, shown(done)
    assert "not the pinned one" in done.stdout, shown(done)
    assert not (tmp_path / "args.log").exists(), "actionlint ran anyway"


#: The line the actionlint step greps for. It is actionlint's own wording: the
#: real 1.7.12 prints it, with a status of 0, for a shellcheck that is missing
#: and for one that is not executable.
DISABLED_MESSAGE = 'Rule "shellcheck" was disabled'


def test_lint_yml_header_says_to_re_check_actionlints_disabled_message_on_every_bump():
    """The actionlint step knows that its shellcheck rule was switched off only
    by grepping actionlint's own wording, and the tests give it a hand-written
    copy of that line (`FAKE_ACTIONLINT`). An actionlint that rewords it would
    leave the guard dead with every test green, so the one thing standing
    between is the header's instruction to re-check the message on every bump.
    This holds the instruction, quoting the line the step greps for."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert f"grep -q '{DISABLED_MESSAGE}'" in text, \
        "the actionlint step greps for another message"
    words = header_of(text)
    assert re.search(r"[Oo]n every actionlint bump\b.*\bre-check\b.*"
                     + re.escape(DISABLED_MESSAGE), words), \
        f"the header does not say to re-check {DISABLED_MESSAGE!r} on every actionlint bump"


# --- the shellcheck step ---------------------------------------------------------

#: A fake shellcheck that writes down each call, and fails for the files named
#: in `$FAKE_SC_FAIL`.
FAKE_SHELLCHECK = r"""#!/bin/sh
printf '%s\n' "$*" >> "$FAKE_SC_LOG"
for last; do :; done
case " $FAKE_SC_FAIL " in *" $last "*) exit 1 ;; esac
exit 0
"""

#: What the throwaway repository tracks: name -> first line, which is written
#: as that line, a newline and a `:` line, or, where the value is bytes, the
#: file's exact content.
FIXTURE_FILES = {
    "park": "#!/usr/bin/env bash",            # clean: every severity
    "resume": "#!/bin/bash",
    "status": "#!/usr/bin/env sh",
    "plain.sh": "#!/bin/sh",
    "new-script": "#!/usr/bin/env bash",      # added later: every severity
    "odd name.sh": "#!/usr/bin/env bash",
    "lane": "#!/usr/bin/env bash",            # baselined
    "lanes-edit.sh": "#!/usr/bin/env bash",
    "tests/run.sh": "#!/usr/bin/env bash",
    "tests/test_lane_helpers.sh": "#!/usr/bin/env bash",   # not run
    "lane-worktrees": "#!/usr/bin/env python3",
    "zsh-thing": "#!/usr/bin/env zsh",
    "README.md": "# a document",
    "no-shebang": "echo not a script",
    # THE READ GUARD'S FILES (`IFS= read -r first < "$path" || true`). `read`
    # returns 1 when it reaches the end of the input, with nothing read from
    # an empty file and with its one line read from a file that has no final
    # newline, and without the guard either would end the step under `set -e`.
    "empty-file": b"",                                    # no first line: not selected
    "words-no-newline": b"just words, no final newline",  # not a shebang: not selected
    "script-no-newline": b"#!/usr/bin/env bash",          # a one-line script: selected
}
BASELINED_FLAGS = ["--severity=warning", "--exclude=" + ",".join(EXCLUDED_CODES)]
#: What the step hands shellcheck in that repository, file -> flags: the
#: baselined scripts at the baseline, every other selected file at none.
FIXTURE_SELECTED = {
    "park": [], "resume": [], "status": [], "plain.sh": [],
    "new-script": [], "odd name.sh": [], "script-no-newline": [],
    "lane": BASELINED_FLAGS, "lanes-edit.sh": BASELINED_FLAGS,
    "tests/run.sh": BASELINED_FLAGS}


def fixture_repo(root: Path, files: dict | None = None) -> Path:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True,
                   env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull})
    for name, content in (FIXTURE_FILES if files is None else files).items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content + "\n:\n", encoding="utf-8")
    if files is None:
        os.symlink("park", repo / "link-to-park")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True,
                   env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull})
    (repo / "untracked-script").write_text("#!/usr/bin/env bash\n:\n", encoding="utf-8")
    return repo


def run_shellcheck_step(workflow: dict, root: Path, files: dict | None = None,
                        fail: str = ""):
    repo = fixture_repo(root, files)
    runner = Runner(root)
    write_executable(root / "fakes" / "shellcheck", FAKE_SHELLCHECK)
    done = runner.run(shellcheck_step(workflow), cwd=repo, front=(root / "fakes",),
                      extra={"FAKE_SC_LOG": str(root / "calls.log"),
                             "FAKE_SC_FAIL": fail})
    log = root / "calls.log"
    calls = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
    return done, calls


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@NEEDS_TOOLS
def test_lint_yml_shellcheck_step_finds_the_scripts_by_shebang_and_holds_the_baseline(
        workflow, tmp_path):
    """The step in a throwaway repository under a fake shellcheck. Selected: a
    tracked regular file whose first line is a bash or sh shebang, one call
    each, a one-line script with no final newline included. Not selected:
    Python, zsh, a document, a file with no shebang, an EMPTY file, a file of
    words with no final newline, a symlink, an untracked file, and the lane
    helpers' suite. The step does not die on the empty file or on the two with
    no final newline: `read` returns 1 for each, which the guard on it
    swallows. The twelve named scripts are given `--severity=warning` and the
    ten excluded codes, and every other script, a new one included, is given
    nothing."""
    done, calls = run_shellcheck_step(workflow, tmp_path)
    assert done.returncode == 0, shown(done)
    want = sorted(" ".join(flags + [name]) for name, flags in FIXTURE_SELECTED.items())
    assert sorted(calls) == want, "\n".join(calls)


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@NEEDS_TOOLS
def test_lint_yml_shellcheck_step_checks_every_script_then_fails_naming_each_that_failed(
        workflow, tmp_path):
    """A script with findings does not stop the others from being checked:
    every selected file is run, and the step then fails, naming the files
    that failed."""
    done, calls = run_shellcheck_step(workflow, tmp_path, fail="lane park")
    assert done.returncode == 1, shown(done)
    assert len(calls) == len(FIXTURE_SELECTED), calls
    assert "::error::shellcheck reported findings in: " in done.stdout, shown(done)
    named = done.stdout.split("::error::shellcheck reported findings in: ")[1].split()
    assert sorted(named) == ["lane", "park"], named


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@NEEDS_TOOLS
def test_lint_yml_shellcheck_step_fails_where_it_finds_no_script_at_all(
        workflow, tmp_path):
    """A selection that finds nothing is a lint that checks nothing, so it is
    a failure and not a pass."""
    done, calls = run_shellcheck_step(workflow, tmp_path,
                                      files={"README.md": "# a document"})
    assert done.returncode == 1, shown(done)
    assert calls == [], calls
    assert "::error::no tracked file starts with a bash or sh shebang" in done.stdout, \
        shown(done)


#: First lines that name bash or sh in a form the step does not select (it
#: takes `#!/usr/bin/env bash`, `#!/bin/bash`, `#!/usr/bin/env sh` and
#: `#!/bin/sh`). A script written one of these ways would drop out of lint
#: without a word, so the step refuses it.
UNSELECTED_SHELL_SHEBANGS = [
    pytest.param("#!/usr/bin/bash", id="usr-bin-bash"),
    pytest.param("#! /bin/bash", id="a-space-after-the-bang"),
    pytest.param("#!/usr/bin/env -S bash", id="env-dash-S-bash"),
    pytest.param("#!/usr/local/bin/bash -e", id="usr-local-bin-bash-with-a-flag"),
    pytest.param("#!/usr/bin/sh", id="usr-bin-sh"),
    pytest.param("#! /bin/sh", id="sh-with-a-space-after-the-bang"),
    pytest.param("#!/usr/bin/env -S sh -e", id="env-dash-S-sh-with-a-flag"),
]


def error_lines(done) -> list:
    return [line for line in done.stdout.splitlines() if line.startswith("::error::")]


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@NEEDS_TOOLS
@pytest.mark.parametrize("shebang", UNSELECTED_SHELL_SHEBANGS)
def test_lint_yml_shellcheck_step_fails_closed_on_a_shell_shebang_it_does_not_select(
        workflow, tmp_path, shebang):
    """A tracked file whose first line is a shebang naming bash or sh in a form
    the step does not select would be left out of lint in silence. So the step
    names it in one error line and exits 1, before shellcheck has been asked
    for anything. Python, zsh and a document in the same repository are not
    named: only a shebang that names bash or sh is refused."""
    files = {"park": "#!/usr/bin/env bash", "odd-script": shebang,
             "tool.py": "#!/usr/bin/env python3", "zsh-thing": "#!/usr/bin/env zsh",
             "README.md": "# a document"}
    done, calls = run_shellcheck_step(workflow, tmp_path, files=files)
    assert done.returncode == 1, shown(done)
    assert calls == [], calls
    errors = error_lines(done)
    assert len(errors) == 1 and errors[0].startswith("::error::odd-script: "), shown(done)


@NEEDS_UPSTREAM
@WINDOWS_SKIP
@NEEDS_BASH
@NEEDS_TOOLS
def test_lint_yml_shellcheck_step_names_every_file_whose_shell_shebang_it_does_not_select(
        workflow, tmp_path):
    """Each such file is named, in a subdirectory and with a space in its name
    too, and not only the first one the scan meets."""
    files = {"park": "#!/usr/bin/env bash", "a-bash": "#!/usr/bin/bash",
             "b sh.sh": "#! /bin/sh", "dir/c-env-s": "#!/usr/bin/env -S bash -e"}
    done, calls = run_shellcheck_step(workflow, tmp_path, files=files)
    assert done.returncode == 1, shown(done)
    assert calls == [], calls
    named = sorted(line.split(": ", 1)[0] for line in error_lines(done))
    assert named == ["::error::a-bash", "::error::b sh.sh", "::error::dir/c-env-s"], \
        shown(done)


@NEEDS_UPSTREAM
def test_lint_yml_shellcheck_step_names_the_baseline_this_file_pins(workflow):
    """The step's lists are the ones this file holds, so a change to the
    baseline, a code or a script, is a change here as well: ten codes, twelve
    named scripts, the one suite not run, the floor `--severity=warning`, and
    never `--severity=error`, which would leave the baseline as nothing."""
    script = shellcheck_step(workflow)["run"]
    excluded = re.search(r"^\s*excluded='([^']*)'$", script, re.M).group(1)
    assert excluded.split(",") == list(EXCLUDED_CODES), excluded
    baselined = re.search(r"^\s*baselined='([^']*)'$", script, re.M).group(1)
    assert baselined.split() == list(BASELINED), baselined
    assert re.search(r"^\s*not_run='([^']*)'$", script, re.M).group(1) == NOT_RUN
    assert "--severity=warning" in script
    assert "--severity=error" not in script and "-S error" not in script
    assert not set(CLEAN_SCRIPTS) & set(BASELINED), \
        "a clean script is in the baselined list"


def test_lint_yml_baselined_scripts_are_tracked_bash_files_and_the_clean_ones_stay_out():
    """Each name the workflow lists, as baselined or as not run, is a tracked
    file that starts with a bash shebang, so a script that was renamed or
    deleted leaves a stale entry that fails here and not one in a list nobody
    reads. The three scripts that have no finding are tracked bash files too,
    and are in neither list: they stay held to every severity."""
    assert WORKFLOW.is_file(), f"{WORKFLOW} does not exist"
    script = WORKFLOW.read_text(encoding="utf-8")
    baselined = re.search(r"^\s*baselined='([^']*)'$", script, re.M)
    not_run = re.search(r"^\s*not_run='([^']*)'$", script, re.M)
    assert baselined and not_run, "lint.yml names no `baselined` or `not_run` list"
    named = baselined.group(1).split() + [not_run.group(1)]
    for name in named + list(CLEAN_SCRIPTS):
        assert tracked(name), f"{name} is not a tracked file"
        first = (REPO / name).read_text(encoding="utf-8").split("\n", 1)[0]
        assert first.startswith(("#!/usr/bin/env bash", "#!/bin/bash")), \
            f"{name} starts {first!r}"
    assert not set(CLEAN_SCRIPTS) & set(named), \
        "a script with no finding is in a list that loosens its check"


def test_lint_yml_header_documents_each_excluded_code_with_its_count():
    """THE BASELINE IS DOCUMENTED IN THE WORKFLOW FILE, a code at a time:
    each row of the header's table is `SCnnnn`, its count on main and its
    reason, and the rows are the step's ten codes and no others. The counts
    add up to the header's 190 warnings, and every baselined script is
    named in the header."""
    text = WORKFLOW.read_text(encoding="utf-8")
    rows = re.findall(r"(?m)^#   (SC\d{4}) +(\d+) ", text.split("\non:\n", 1)[0])
    assert sorted(code for code, _ in rows) == sorted(EXCLUDED_CODES), rows
    assert all(int(count) > 0 for _, count in rows), rows
    words = header_of(text)
    said = re.search(r"(\d+) warnings and (\d+) notes", words)
    assert said, "the header gives no count of warnings and notes"
    assert sum(int(count) for _, count in rows) == int(said.group(1)), (rows, said.groups())
    for name in BASELINED + (NOT_RUN,):
        assert f"`{name}`" in words, f"the header does not name {name}"
    for tool in (ACTIONLINT, SHELLCHECK):
        assert tool["version"] in words, f"the header does not say {tool['version']}"


def test_lint_yml_header_names_its_tree_and_its_totals_agree():
    """THE HEADER'S FIGURES ARE FROM ONE NAMED TREE: the baseline says which
    main it was measured on, and a figure from another tree names that tree
    where it stands. Its totals agree with each other, so that a re-measure
    that moves one moves them all: the findings are the warnings and the
    notes, every `N of the M findings` names that same M, and the notes and
    warnings the header says it leaves out are the ones it counts."""
    words = header_of(WORKFLOW.read_text(encoding="utf-8"))
    tree = re.search(r"MEASURED ON main `([0-9a-f]{7,40})`", words)
    assert tree, "the header does not name the main its baseline was measured on"
    held = re.search(r"hold (\d+) findings between them, (\d+) warnings and (\d+) notes",
                     words)
    assert held, "the header gives no total of findings"
    total, warnings, notes = (int(number) for number in held.groups())
    assert total == warnings + notes, held.groups()
    for of_the in re.findall(r"(\d+) of the (\d+) findings", words):
        assert int(of_the[1]) == total, (of_the, total)
    assert f"the {notes} notes and the {warnings} warnings of those ten codes" in words, \
        "the header's left-out notes and warnings are not the ones it counts"


def test_lint_yml_header_names_the_runner_its_16_gb_assumes_and_the_memory_print():
    """`lanes-edit.sh` peaks at about 10.9 GB, which fits the 16 GB of GitHub's
    standard Linux runner for a PUBLIC repository and not the 7 GB of a private
    one's. The header says so, and names the `MemTotal` and `MemAvailable`
    print as the aid for diagnosing a kill, which is only an aid while the step
    still prints them before it runs anything."""
    text = WORKFLOW.read_text(encoding="utf-8")
    words = header_of(text)
    assert "STANDARD LINUX RUNNER FOR A PUBLIC REPOSITORY" in words
    assert "private repository has 7 GB" in words
    assert "`MemTotal` and `MemAvailable`" in words
    assert "grep -E '^(MemTotal|MemAvailable)' /proc/meminfo || true" in text, \
        "the shellcheck step does not print the runner's memory"
    assert text.index("/proc/meminfo") < text.index("git ls-files -z"), \
        "the memory is printed after the selection has begun"
