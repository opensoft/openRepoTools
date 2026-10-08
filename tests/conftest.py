# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures, and the one thing this suite needs that it does not ship.

NO NETWORK AND NO GITHUB. Every test here runs `park`, `resume` or
`openRepoTools` against BARE REPOSITORIES IN A TEMPORARY DIRECTORY, a fake
`$HOME`, and — where a fetch is under test — a fake `gh` first on `$PATH` with
a `curl` that refuses. Nothing in this suite may create a real repository; if a
test ever needs a real `gh`, it is the wrong test.

THE STANDARD IS MOUNTED, NOT COPIED. `tests/test_park_resume_commands.py`
builds estates out of eight of openRepoShape's own files, and it reads them out
of the `upstream/openRepoShape` submodule this repository pins in
`contracts/openreposhape-pin.yaml`. A clone made WITHOUT `--recurse-submodules`
therefore has no template bytes to copy — so those tests SKIP, naming the one
command that fixes it. They never fail: a fork's first `pytest` going red on a
missing submodule is a fork nobody finishes.

FOUR ROOTS, NAMED RATHER THAN ASSUMED (opensoft/openRepoTools#186, T009 of
`specs/004-migrate-to-triad/tasks.md`). Today this repository is one tree and
every path the suite reads hangs off it. Adopted into the triad it is three:
the ASSEMBLY root (`README.md`, `AGENTS.md`, `CLAUDE.md`, the pins), the SPEC
leg (`docs/`, `openspec/`, `specs/`) and the CODE leg (every command, `tests/`,
`.gitmodules`, `contracts/openreposhape-pin.yaml`), with the DEPENDENCY,
`upstream/openRepoShape`, nested in the code leg. `ROOTS` below is the one
place that says which tree is which for this run, and `ROOTS.path_for(<rel>)`
is how a test reads a file from the root that owns it. Two modes:

  * STANDALONE (the default, and the only mode today's layout has): a root
    this checkout does not carry is SKIPPED, naming it — the same courtesy the
    missing submodule gets, and on today's layout nothing new skips, because
    the one tree is all four roots at once.
  * COMPOSED (`OPENREPOTOOLS_COMPOSED=1`, the assembly's exact-pin job): the
    run is a claim about the whole arrangement, so a missing assembly, spec or
    dependency root — or a code or spec leg that is not at the commit the
    assembly pins — REFUSES the session before a test runs, and a test that
    reaches an absent root FAILS. Nothing skips its way into composed
    acceptance (FR-008).
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

import pytest

#: THE TREE THIS SUITE WAS LOADED FROM, which is the code root unless
#: `OPENREPOTOOLS_CODE_ROOT` names another one.
SUITE_ROOT = Path(__file__).resolve().parents[1]

#: The four variables a caller names the roots and the mode with. `tests/run.sh`
#: passes them through, made absolute against the directory it was run from.
ENV_CODE_ROOT = "OPENREPOTOOLS_CODE_ROOT"
ENV_ASSEMBLY_ROOT = "OPENREPOTOOLS_ASSEMBLY_ROOT"
ENV_SPEC_ROOT = "OPENREPOTOOLS_SPEC_ROOT"
ENV_COMPOSED = "OPENREPOTOOLS_COMPOSED"

#: WHERE EACH FILE LIVES, by the adoption mapping's placement table
#: (`specs/004-migrate-to-triad/plan.md`, "Target placement"): the front-door
#: documents are the assembly's and the spec trees are the spec leg's.
#: Everything else is the code leg's — and that includes `.gitattributes`,
#: DELIBERATELY: the placement table puts it at the assembly, but git reads a
#: submodule's attributes from the submodule's own tree, so the line-ending
#: rule protects the bash files only where the bash files are. Reading it from
#: the assembly would pass while the code leg's checkout went unprotected.
GUIDANCE_DOCUMENTS = ("README.md", "AGENTS.md", "CLAUDE.md")
SPEC_TREES = ("docs", "openspec", "specs", "ideation")

#: TODAY'S SINGLE REPOSITORY CARRIES THE CANONICAL SPEC TREES BESIDE THE CODE,
#: and a code leg never does (FR-006 puts every full proposal and every
#: canonical spec in the spec leg). So a code root holding either IS the
#: single-repository layout, whose one tree is assembly, spec and code at once
#: — decided by the trees and never by the documents, so a deleted README there
#: is a failure and not a skip.
SINGLE_REPOSITORY_MARKERS = ("openspec", "specs")

#: What makes a directory the root it is claimed to be. A variable that names
#: a tree without these is refused, in either mode: it names the wrong tree.
CODE_MARKERS = ("openRepoTools", "contracts/openreposhape-pin.yaml")
ASSEMBLY_MARKERS = ("contracts/code-pin.yaml", "project.yaml")

#: The dependency, nested in the code leg, and the files the suite's skips
#: probe for: `scripts/repo_shape.py` is `NEEDS_UPSTREAM`'s below and
#: `templates/workspace-root/README.md` is `test_wip_init_command.py`'s. A
#: composed run needs both, because either one missing is a skip.
DEPENDENCY_PATH = "upstream/openRepoShape"
DEPENDENCY_PROBE = "scripts/repo_shape.py"
DEPENDENCY_PROBES = (DEPENDENCY_PROBE, "templates/workspace-root/README.md")


def _absolute(value: str) -> Path:
    path = Path(os.path.expanduser(value))
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def _git_out(cwd: Path, *args: str) -> Optional[str]:
    """`git <args>` in `cwd`, its stdout stripped, or None if it failed."""
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                              text=True, check=False)
    except OSError:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _gitlink(repository: Path, rel: str) -> Optional[str]:
    """The commit `repository`'s HEAD records at `rel`, if it is a gitlink."""
    row = _git_out(repository, "ls-tree", "HEAD", "--", rel)
    if not row:
        return None
    meta = row.split("\t", 1)[0].split(" ")
    if len(meta) != 3 or meta[0] != "160000" or meta[1] != "commit":
        return None
    return meta[2]


def _scalar(path: Path, key: str) -> Optional[str]:
    """`<key>: <value>` at column 0 of a flat pin or manifest file, with its
    comment and quotes stripped. The pins are a fixed grammar written by one
    tool, so a reader of one key is all this needs (no YAML dependency)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for raw in text.splitlines():
        if raw.startswith(key + ":"):
            value = raw[len(key) + 1:].split("#", 1)[0].strip()
            return value.strip('"').strip("'") or None
    return None


def _carries(root: Path, names) -> bool:
    return all((root / name).exists() for name in names)


def _carries_a_spec_tree(root: Path) -> bool:
    return root.is_dir() and any((root / name).is_dir() for name in SPEC_TREES)


def _mount(assembly: Path, role: str) -> str:
    """Where the assembly mounts a leg: its pin's `submodule_path:`."""
    return _scalar(assembly / "contracts" / f"{role}-pin.yaml",
                   "submodule_path") or role


def discover_assembly(code: Path) -> Optional[Path]:
    """The nearest directory above `code` that carries the assembly's pins and
    manifest AND records `code` as the gitlink its code pin names — or None,
    which is today's layout and a standalone code clone alike."""
    for candidate in code.resolve().parents:
        if not _carries(candidate, ASSEMBLY_MARKERS):
            continue
        mount = _mount(candidate, "code")
        top = _git_out(candidate, "rev-parse", "--show-toplevel")
        if (top and _same(Path(top), candidate) and _same(candidate / mount, code)
                and _gitlink(candidate, mount)):
            return candidate
        return None
    return None


class Roots:
    """The code, assembly, spec and dependency roots of one run, and its mode."""

    def __init__(self, code: Path, assembly: Optional[Path],
                 spec: Optional[Path], composed: bool,
                 how: Dict[str, str], problems: List[str]) -> None:
        self.code = code
        self.assembly = assembly
        self.spec = spec
        self.dependency = code / DEPENDENCY_PATH
        self.composed = composed
        self.how = how
        self.problems = problems
        #: `single` — today's one tree; `leg` — a code leg, standalone or
        #: mounted. Decided by the code root alone; the assembly and spec
        #: roots are found, or named, independently of it.
        self.layout = ("single" if any((code / name).is_dir()
                                       for name in SINGLE_REPOSITORY_MARKERS)
                       else "leg")

    # --- which root a file is read from ------------------------------------

    def owner_of(self, rel: str) -> str:
        rel = rel.replace("\\", "/")
        if rel in GUIDANCE_DOCUMENTS:
            return "assembly"
        if "/" in rel and rel.split("/", 1)[0] in SPEC_TREES:
            return "spec"
        return "code"

    def root_of(self, role: str) -> Optional[Path]:
        """The tree that answers for `role` in this run. On today's layout the
        code root answers for all three; in a leg, only what is there."""
        if role == "code":
            return self.code
        found = self.assembly if role == "assembly" else self.spec
        if found is not None:
            return found
        return self.code if self.layout == "single" else None

    def path_for(self, rel: str) -> Path:
        """`rel` in the root that owns it. Where that root is absent this SKIPS
        the calling test — or, composed, FAILS it — naming the root."""
        role = self.owner_of(rel)
        root = self.root_of(role)
        if root is None:
            self.need(role, rel)
        return root / rel

    def why_absent(self, role: str) -> str:
        if role == "assembly":
            return (f"no {ENV_ASSEMBLY_ROOT}, and no directory above {self.code} "
                    f"carries {' and '.join(ASSEMBLY_MARKERS)} mounting it")
        if self.assembly is not None:
            return (f"the assembly's spec leg {self.assembly / _mount(self.assembly, 'spec')} "
                    f"is not checked out, and {ENV_SPEC_ROOT} is unset")
        return f"no {ENV_SPEC_ROOT}, and no assembly root to find a spec leg in"

    def need(self, role: str, rel: str):
        """The outcome of a test that reached a root this run does not have."""
        why = self.why_absent(role)
        if self.composed:
            pytest.fail(f"{ENV_COMPOSED}=1 and {rel} is the {role} root's, which "
                        f"is absent: {why}", pytrace=False)
        pytest.skip(f"{rel} is the {role} root's, and this standalone code "
                    f"checkout has none ({why}); the composed run "
                    f"({ENV_COMPOSED}=1 from the assembly root) reads it")

    def tracked_roots(self) -> List[Tuple[str, Path]]:
        """Every distinct repository this run can read, code first."""
        out: List[Tuple[str, Path]] = []
        for role in ("code", "assembly", "spec"):
            root = self.root_of(role)
            if root is not None and not any(_same(root, seen) for _, seen in out):
                out.append((role, root))
        return out

    # --- the dependency ------------------------------------------------------

    def dependency_initialized(self, probes=DEPENDENCY_PROBES) -> bool:
        return all((self.dependency / probe).is_file() for probe in probes)

    # --- the composed contract -----------------------------------------------

    def _leg_at_its_pin(self, role: str, root: Path) -> List[str]:
        assert self.assembly is not None
        mount = _mount(self.assembly, role)
        recorded = _gitlink(self.assembly, mount)
        if recorded is None:
            return [f"the assembly root {self.assembly} records no gitlink at "
                    f"{mount!r}, which contracts/{role}-pin.yaml names"]
        head = _git_out(root, "rev-parse", "HEAD")
        if head != recorded:
            return [f"the {role} root {root} is at {head or 'no commit'}, and the "
                    f"assembly root records {recorded} at {mount!r}: composed "
                    f"acceptance is for the pinned {role} leg and no other"]
        dirty = _git_out(root, "status", "--porcelain", "--untracked-files=no")
        if dirty:
            return [f"the {role} root {root} has changes to tracked files "
                    f"({dirty.splitlines()[0].strip()} …): composed acceptance is "
                    f"for the committed bytes the pin names"]
        return []

    def absent(self) -> List[str]:
        """What a composed run is missing, one line per context."""
        lines: List[str] = []
        if self.assembly is None:
            lines.append(f"the ASSEMBLY root is absent: {self.why_absent('assembly')}")
        else:
            lines += self._leg_at_its_pin("code", self.code)
        if self.spec is None:
            lines.append(f"the SPEC root is absent: {self.why_absent('spec')}")
        elif self.assembly is not None:
            lines += self._leg_at_its_pin("spec", self.spec)
        if not self.dependency_initialized():
            missing = [p for p in DEPENDENCY_PROBES
                       if not (self.dependency / p).is_file()]
            lines.append(f"the DEPENDENCY {self.dependency} is not initialized "
                         f"(no {', '.join(missing)}): run `git submodule update "
                         f"--init --recursive` from the assembly root")
        return lines

    def refusal(self) -> Optional[str]:
        """Why this run must not start: a variable naming the wrong tree (either
        mode), or a composed run missing a context. None when it may run."""
        lines = list(self.problems)
        if self.composed:
            lines += self.absent()
        if not lines:
            return None
        head = ("openRepoTools test roots: " if not self.composed else
                f"openRepoTools composed run ({ENV_COMPOSED}=1) refused — it "
                f"never skips its way to acceptance: ")
        return head + "; ".join(lines)

    def describe(self) -> List[str]:
        """The roots, one line each, for the report header."""
        lines = [f"openRepoTools test roots: "
                 f"{'COMPOSED' if self.composed else 'standalone'}, "
                 f"{self.layout} layout"]
        for role in ("code", "assembly", "spec"):
            root = self.root_of(role)
            if root is None:
                lines.append(f"  {role}: absent")
                continue
            how = self.how.get(role) or (
                "default" if role == "code" else "the code root: today's single tree")
            lines.append(f"  {role}: {root} ({how})")
        state = "initialized" if self.dependency_initialized() else "NOT initialized"
        lines.append(f"  dependency: {self.dependency} ({state})")
        return lines


def resolve_roots(environ: Mapping[str, str], suite_root: Path) -> Roots:
    """The roots `environ` names, else the ones the layout around `suite_root`
    has. Pure apart from reading the disk and git, so the suite can ask it about
    a fixture layout as well as about itself."""
    problems: List[str] = []
    how: Dict[str, str] = {}

    composed_value = environ.get(ENV_COMPOSED, "")
    if composed_value not in ("", "0", "1"):
        problems.append(f"{ENV_COMPOSED}={composed_value!r} is neither 1 "
                        f"(composed) nor 0 or unset (standalone)")
    composed = composed_value == "1"

    code = suite_root.resolve()
    named = environ.get(ENV_CODE_ROOT, "")
    if named:
        candidate = _absolute(named)
        if candidate.is_dir() and _carries(candidate, CODE_MARKERS):
            code, how["code"] = candidate, ENV_CODE_ROOT
        else:
            problems.append(f"{ENV_CODE_ROOT}={named} is not a code root: it "
                            f"carries no {' and '.join(CODE_MARKERS)}")

    assembly: Optional[Path] = None
    named = environ.get(ENV_ASSEMBLY_ROOT, "")
    if named:
        candidate = _absolute(named)
        if candidate.is_dir() and _carries(candidate, ASSEMBLY_MARKERS):
            assembly, how["assembly"] = candidate, ENV_ASSEMBLY_ROOT
        else:
            problems.append(f"{ENV_ASSEMBLY_ROOT}={named} is not an assembly "
                            f"root: it carries no {' and '.join(ASSEMBLY_MARKERS)}")
    else:
        assembly = discover_assembly(code)
        if assembly is not None:
            how["assembly"] = "found above the code root, which it mounts"

    spec: Optional[Path] = None
    named = environ.get(ENV_SPEC_ROOT, "")
    if named:
        candidate = _absolute(named)
        if _carries_a_spec_tree(candidate):
            spec, how["spec"] = candidate, ENV_SPEC_ROOT
        else:
            problems.append(f"{ENV_SPEC_ROOT}={named} is not a spec root: it "
                            f"carries none of {', '.join(SPEC_TREES)}")
    elif assembly is not None:
        candidate = assembly / _mount(assembly, "spec")
        if _carries_a_spec_tree(candidate):
            spec, how["spec"] = candidate, "the assembly's spec leg"

    return Roots(code, assembly, spec, composed, how, problems)


#: THIS RUN'S ROOTS. Module-level names below are its fields, so the modules
#: that import `REPO` and `UPSTREAM` read the code root and its dependency
#: whatever the layout.
ROOTS = resolve_roots(os.environ, SUITE_ROOT)
CODE_ROOT = ROOTS.code
ASSEMBLY_ROOT = ROOTS.assembly
SPEC_ROOT = ROOTS.spec
DEPENDENCY_ROOT = ROOTS.dependency
COMPOSED = ROOTS.composed

#: `REPO` is the CODE root: every module that reads a command, a test or a pin
#: through it keeps reading the code leg's copy, which is what it always meant.
#: A document the assembly or the spec leg owns is read through
#: `ROOTS.path_for(<rel>)` instead.
REPO = CODE_ROOT


def pytest_configure(config):
    """REFUSE BEFORE THE FIRST TEST, naming every missing or misnamed root.

    A `UsageError` is pytest's own refusal (exit 4, `ERROR: <why>`), which is
    what a composed run that cannot be the claim it makes should be: not a
    session of skips that exits 0."""
    refusal = ROOTS.refusal()
    if refusal:
        raise pytest.UsageError(refusal)


def pytest_report_header(config):
    return ROOTS.describe()

#: AMENDMENT 14 — NO TEST NUDGES AN INSTALLED INDEXER BY ACCIDENT. Every
#: `lanes-edit.sh` write that pushes starts a detached `lanes-index sync`
#: wherever one is on PATH, and several suites here run with the workstation's
#: own PATH behind their fakes: the day a person installs `lanes-index`, those
#: writes would start one each. Off for the whole run; `tests/test_lanes_index.py`
#: builds every environment it runs from scratch and decides for itself.
os.environ["LANES_INDEX"] = "off"

#: opensoft/openRepoTools#162 — and no `lane-start` a test runs starts the
#: estate's daily report: it is detached, it reads the whole estate, and the
#: state directory it stamps may be the workstation's own.
os.environ["LANE_WORKTREES_REPORT"] = "off"

#: The pinned openRepoShape checkout: the DEPENDENCY root, nested in the code
#: root. Every path this suite reads out of the standard hangs off this one
#: name, so a bump of the pin moves one line in
#: `contracts/openreposhape-pin.yaml` and the gitlink beside it, and nothing
#: here.
UPSTREAM = DEPENDENCY_ROOT

#: THE TESTS THAT NEED THE STANDARD'S REAL BYTES. `scripts/repo_shape.py` is
#: the probe rather than the directory itself, because `git clone` without
#: `--recurse-submodules` leaves an EMPTY `upstream/openRepoShape/` behind —
#: the directory exists and holds nothing, so `is_dir()` would answer yes and
#: the tests would fail on a missing file instead of skipping.
#:
#: STANDALONE, THAT SKIP IS EXACTLY TODAY'S — the same condition and the same
#: reason, which is what the `tests-no-submodule` job asserts. COMPOSED, the
#: mark is the `required_dependency` fixture instead, which FAILS: a composed
#: session without the dependency is refused before it starts, and this is the
#: same rule held at the test, where a `--noconftest` run cannot route round it
#: (the fixture is then not found, which is an error and not a skip either).
_DEPENDENCY_SKIP_REASON = ("the pinned openRepoShape is not checked out; "
                           "run `git submodule update --init upstream/openRepoShape`")
if COMPOSED:
    NEEDS_UPSTREAM = pytest.mark.usefixtures("required_dependency")
else:
    NEEDS_UPSTREAM = pytest.mark.skipif(
        not (UPSTREAM / DEPENDENCY_PROBE).is_file(),
        reason=_DEPENDENCY_SKIP_REASON)


@pytest.fixture
def required_dependency():
    """`NEEDS_UPSTREAM` in a composed run: the dependency is there, or the test
    fails naming it."""
    if not (UPSTREAM / DEPENDENCY_PROBE).is_file():
        pytest.fail(f"{ENV_COMPOSED}=1 and the dependency {UPSTREAM} is not "
                    f"initialized; {_DEPENDENCY_SKIP_REASON}", pytrace=False)

#: THE TESTS THAT CANNOT RUN ON WINDOWS. Two shapes of test wear this: one that
#: runs `bash`, and one that puts a `#!`-shebang script named `gh` on PATH and
#: expects the operating system to execute it. Windows has neither — `bash.exe`
#: IS on the GitHub runner, so a `shutil.which("bash")` guard does not fire,
#: but `park`, `resume` and `openRepoTools` are bash scripts that run `make` in
#: a root which execs a shebang script, and a shebang means nothing to
#: CreateProcess. Skipping is honest because there is no Windows twin to run
#: instead: these three files are bash, and on Windows the way in is WSL2,
#: exactly as it is for openRepoShape's own `setup.sh`. What the Windows job
#: still proves is the checkout and the hygiene tests, which need no shell.
#: A shared `skipif` object rather than a named marker because there is no
#: pytest.ini to register one in, and an unregistered marker is a warning.
WINDOWS_SKIP = pytest.mark.skipif(
    os.name == "nt",
    reason="needs a POSIX shell and shebang execution; on Windows the way in "
           "is WSL2, as it is for openRepoShape's setup.sh")


def rmtree(path: Path) -> None:
    """`shutil.rmtree` that also works over a git object store on Windows.

    Git writes loose objects and packs READ-ONLY, and Windows refuses to
    unlink a read-only file — so a plain `rmtree` over a checkout raises
    PermissionError there and succeeds everywhere else. The handler clears the
    read-only bit and retries the one call that failed. `onerror` rather than
    `onexc`: the newer spelling is 3.12+, and this standard runs on 3.9.
    """
    def clear_readonly(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onerror=clear_readonly)


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=False)
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} in {cwd} failed:\n"
                             f"{proc.stderr}{proc.stdout}")
    return proc
