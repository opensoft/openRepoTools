# SPDX-License-Identifier: Apache-2.0
"""The `openrepotools` package (#228): what `pyproject.toml` declares, the
wheel's payload map against the installer's own list, a built wheel, and the
console script that runs the payload.

FOUR GROUPS, ONE PREFIX EACH (plan.md, "The test layout"), so that a task's
`verify:` selects exactly its own with `-k`:

- `test_metadata_*` holds contracts/wheel.md's `pyproject.toml` rules. The
  file is read with `tomllib`, or with `tomli` where `tomllib` is missing
  (Python 3.9 and 3.10, as in the `package` job, which installs `tomli` by
  hash), and these tests skip, naming `tomli`, where neither imports.
- `test_payload_map_*` holds the force-include map to the installer's
  `payload_names`, RUN FROM THE BASH FILE and never restated here, plus the
  openRepoShape pin, both ways round and naming every difference. The bash
  list stays the only list (design.md Decision 2, FR-007).
- `test_wheel_*` checks a BUILT wheel, and this suite builds none: a build
  fetches hatchling, and the suite reaches no network (research R8). They
  read the wheel from `OPENREPOTOOLS_TEST_WHEEL`, and skip, naming it, when
  it is unset; the `package` job sets it and fails on any skip. They run
  contracts/wheel.md's checks 2, 3, 5 and 6, and its member comparison,
  against this checkout's `HEAD`.
- `test_entry_*` runs pip's console script for `openrepotools.cli:main` in a
  real virtual environment (`venv --without-pip`: the standard library, and
  no network) that holds a `package_tree`. The entry module must replace its
  own process with the first `bash` on PATH, running the packaged
  `openRepoTools` with the person's arguments unchanged and with neither
  signal Python ignores at start-up still ignored, and must refuse, running
  nothing, where there is no `bash`, a `PATH` whose last entry is a file
  included (design.md Decision 3 as amended on 2026-10-18, FR-003, FR-004).

THE HELPERS ARE THE SUITE'S OWN. `command_env`, `placement_temporaries`,
`path_without`, `SLOW_TOOLS` and `NEEDS_JQ` come from
`tests/test_openrepotools_command.py`, `installer_function` from
`tests/test_install_by_rename.py`, and the layouts from
`tests/package_layout.py`.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import NamedTuple

import pytest

from conftest import REPO, WINDOWS_SKIP
from package_layout import PAYLOAD_PREFIX, console_script, package_tree
from test_install_by_rename import installer_function
from test_openrepotools_command import (NEEDS_JQ, SLOW_TOOLS, command_env,
                                        path_without, placement_temporaries)

try:
    import tomllib as TOML
except ImportError:   # Python 3.9 and 3.10
    try:
        import tomli as TOML
    except ImportError:
        TOML = None

COMMAND = REPO / "openRepoTools"
PYPROJECT = REPO / "pyproject.toml"
BUILD_LOCK = REPO / ".github" / "release-build-requirements.txt"

#: THE ONE PAYLOAD FILE THAT IS NOT ON THE INSTALLER'S LIST. `wip init` reads
#: the openRepoShape pin from beside the installer (`wip_shape_ref`), so the
#: wheel carries it as the force-include map's 24th entry, after the
#: installer's own 23.
PIN = "contracts/openreposhape-pin.yaml"

#: contracts/wheel.md's `pyproject.toml`, as the tests below hold it.
HATCHLING = "hatchling==1.27.0"
SCRIPTS = {"openRepoTools": "openrepotools.cli:main"}
STAMP = "src/openrepotools/_release.py"
PACKAGES = ["src/openrepotools"]

#: `[project]`'s keys: the ones the contract declares, and the four it allows
#: "as the model has them". Any other, such as `readme`, a static `version`,
#: `optional-dependencies`, `gui-scripts` or `entry-points`, changes what the
#: wheel holds or what its metadata says.
PROJECT_KEYS = ("name", "dynamic", "requires-python", "license",
                "license-files", "dependencies", "scripts")
PROJECT_KEYS_ALLOWED = ("description", "authors", "classifiers", "urls")

#: THE WHEEL'S MEMBERS beside the payload (contracts/wheel.md): the modules,
#: and the names in `openrepotools-<version>.dist-info/`.
MODULES = ("__init__.py", "cli.py", "_release.py")
DIST_INFO = ("METADATA", "WHEEL", "RECORD", "entry_points.txt",
             "licenses/LICENSE")

WHEEL_VARIABLE = "OPENREPOTOOLS_TEST_WHEEL"

#: contracts/cli-output.md's one refusal that does not go through `die`: the
#: entry module's own, so it has no blank line before it.
NO_BASH = ("REFUSED: openRepoTools needs bash, and there is no bash on this "
           "PATH. Nothing ran.")

NEEDS_BASH = pytest.mark.skipif(shutil.which("bash") is None,
                                reason="openRepoTools is a bash script")


def listed(problems: list) -> str:
    return "\n  " + "\n  ".join(problems)


# --- pyproject.toml ----------------------------------------------------------

@pytest.fixture(scope="module")
def pyproject() -> dict:
    """`pyproject.toml` as a TOML parser reads it, or a skip naming `tomli`."""
    if TOML is None:
        pytest.skip("pyproject.toml is read with tomllib (Python 3.11 and up) "
                    "or with tomli, and neither imports here: install tomli, "
                    "as the package job does (tomli==2.4.1, by hash)")
    with PYPROJECT.open("rb") as handle:
        return TOML.load(handle)


def project_table(pyproject: dict) -> dict:
    table = pyproject.get("project")
    assert isinstance(table, dict), "pyproject.toml has no [project] table"
    return table


def table_problems(where: str, table, keys) -> list:
    """What `table` lacks of `keys`, and what it holds beyond them."""
    if not isinstance(table, dict):
        return [f"[{where}] is missing, or is not a table"]
    return ([f"[{where}] has no `{key}`" for key in keys if key not in table]
            + [f"[{where}] has `{key}`, which contracts/wheel.md does not "
               "declare" for key in table if key not in keys])


def test_metadata_builds_with_hatchling_at_its_one_pin(pyproject):
    """`[build-system]` is hatchling at exactly 1.27.0, and nothing else.

    1.27.0 is the newest hatchling that still runs on Python 3.9, the oldest
    this package supports, and hatchling's `force-include` is what puts the
    payload in the wheel with no build hook (design.md Decision 2). A range
    would make the wheel's bytes depend on the day it was built.
    """
    assert pyproject.get("build-system") == {
        "requires": [HATCHLING], "build-backend": "hatchling.build"}, (
        f"[build-system] is {pyproject.get('build-system')!r}")


def test_metadata_the_build_lock_names_the_same_hatchling(pyproject):
    """`requires` IS THE BUILD LOCK'S HATCHLING (contracts/wheel.md).

    The release build installs its tools from the lock and builds with
    `--no-isolation`, so a lock naming another hatchling would build the
    release with a backend this file does not name. The lock is
    `tests/test_release_workflow.py`'s to hold in full; this holds the one
    line the two files share, from this file's side.
    """
    if not BUILD_LOCK.is_file():
        pytest.skip(f"{BUILD_LOCK.relative_to(REPO)} is not in this checkout, "
                    f"so there is no build lock to hold to {HATCHLING}")
    requires = pyproject.get("build-system", {}).get("requires", [])
    wanted = {r.split("==", 1)[1] for r in requires
              if isinstance(r, str) and r.startswith("hatchling==")}
    pins = re.findall(r"(?m)^hatchling==([^\s;\\]+)",
                      BUILD_LOCK.read_text(encoding="utf-8"))
    assert pins and wanted and set(pins) == wanted, (
        f"{BUILD_LOCK.relative_to(REPO)} pins hatchling at {pins or 'nothing'}, "
        f"and pyproject.toml requires {requires}")


def test_metadata_names_the_package_and_reads_its_version_from_the_stamp(
        pyproject):
    """`openrepotools`, with a DYNAMIC version read from the stamp alone.

    The tag is the one source of a version (FR-009): the release build writes
    it into `src/openrepotools/_release.py`, and `[tool.hatch.version]` reads
    it from there. A static `version` here would be a second number in a
    second file.
    """
    table = project_table(pyproject)
    assert table.get("name") == "openrepotools", table.get("name")
    assert table.get("dynamic") == ["version"], table.get("dynamic")
    assert "version" not in table, (
        f"[project] carries a static version, {table['version']!r}")
    version = pyproject.get("tool", {}).get("hatch", {}).get("version")
    assert version == {"path": STAMP}, f"[tool.hatch.version] is {version!r}"


def test_metadata_requires_python_3_9_or_later(pyproject):
    """3.9 is the `package` job's Python and the install check's oldest leg."""
    assert project_table(pyproject).get("requires-python") == ">=3.9", (
        project_table(pyproject).get("requires-python"))


def test_metadata_declares_no_dependencies(pyproject):
    """NONE (FR-001): the payload is bash, the entry module is the standard
    library, and what the payload runs it finds on PATH, as a checkout's
    does. A dependency would also be a fetch the offline install cannot
    make."""
    assert project_table(pyproject).get("dependencies") == [], (
        project_table(pyproject).get("dependencies"))


def test_metadata_declares_exactly_one_console_script(pyproject):
    """`openRepoTools`, the name a checkout's `--install` places, and no
    other (FR-001; a second console script is a non-goal)."""
    assert project_table(pyproject).get("scripts") == SCRIPTS, (
        project_table(pyproject).get("scripts"))


def test_metadata_declares_no_readme(pyproject):
    """README.md goes to the assembly root at the triad cutover, while this
    file goes to the code leg: a `readme` would name a file the release's
    own tree does not hold (FR-001)."""
    table = project_table(pyproject)
    assert "readme" not in table, f"[project] has readme = {table['readme']!r}"


def test_metadata_is_apache_2_0_with_the_license_file(pyproject):
    table = project_table(pyproject)
    assert table.get("license") == "Apache-2.0", table.get("license")
    assert table.get("license-files") == ["LICENSE"], table.get("license-files")


def test_metadata_project_declares_nothing_the_contract_does_not(pyproject):
    """`[project]` holds the contract's keys, and only the four it allows
    beside them: `description`, `authors`, `classifiers` and `urls`."""
    table = project_table(pyproject)
    problems = [f"[project] has no `{key}`" for key in PROJECT_KEYS
                if key not in table]
    problems += [f"[project] has `{key}`, which contracts/wheel.md neither "
                 "declares nor allows" for key in table
                 if key not in PROJECT_KEYS and key not in PROJECT_KEYS_ALLOWED]
    assert not problems, "pyproject.toml's [project] is not the contract's:" \
        + listed(problems)


def test_metadata_no_other_hatch_table_changes_what_the_wheel_holds(pyproject):
    """`[tool.hatch]` IS THE CONTRACT'S THREE DECLARATIONS AND NOTHING ELSE:
    the version's path, the wheel's `packages`, and the force-include map.

    Any other hatch key (a build hook, `include`, `exclude`, `only-include`,
    `sources`, `artifacts`, `reproducible`, another target) can change what
    the wheel holds or how its bytes come out, so a new one is a change to
    contracts/wheel.md first, and to this test with it.
    """
    hatch = pyproject.get("tool", {}).get("hatch")
    problems = table_problems("tool.hatch", hatch, ("version", "build"))
    if isinstance(hatch, dict):
        problems += table_problems("tool.hatch.version", hatch.get("version"),
                                   ("path",))
        build = hatch.get("build")
        problems += table_problems("tool.hatch.build", build, ("targets",))
        targets = build.get("targets") if isinstance(build, dict) else None
        problems += table_problems("tool.hatch.build.targets", targets,
                                   ("wheel",))
        wheel = targets.get("wheel") if isinstance(targets, dict) else None
        problems += table_problems("tool.hatch.build.targets.wheel", wheel,
                                   ("packages", "force-include"))
        if isinstance(wheel, dict) and "packages" in wheel \
                and wheel["packages"] != PACKAGES:
            problems.append(f"[tool.hatch.build.targets.wheel] packages is "
                            f"{wheel['packages']!r}, not {PACKAGES!r}")
    assert not problems, "pyproject.toml's hatch tables are not the contract's:" \
        + listed(problems)


# --- the force-include map against `payload_names` ---------------------------

#: Where the installer's argument loop begins. Every line above it defines a
#: list, a value or a function; the loop is where the command starts acting.
ARGUMENT_LOOP = re.compile(r"^while \[ \$# -gt 0 \]; do$", re.MULTILINE)


@pytest.fixture(scope="module")
def payload_list(tmp_path_factory) -> list:
    """`payload_names`, as the installer runs it.

    RUN FROM THE BASH FILE, NEVER RESTATED: the harness is every line of
    `openRepoTools` above its argument loop, which defines the lists and the
    functions, and then one call of `payload_names`. So whatever that
    function derives its list from, this reads the list it derives. The
    harness is a file, and not `bash -c`, because the installer is longer
    than Linux lets one argument be (128 KiB).
    """
    text = COMMAND.read_text(encoding="utf-8")
    loops = [match.start() for match in ARGUMENT_LOOP.finditer(text)]
    assert len(loops) == 1, (
        f"{COMMAND} has {len(loops)} argument loops at column 0, not one, so "
        "the harness cannot tell where its definitions end")
    where = tmp_path_factory.mktemp("payload-names")
    harness = where / "payload-names.sh"
    harness.write_text(text[:loops[0]] + "payload_names\n", encoding="utf-8")
    result = subprocess.run(["bash", str(harness)], capture_output=True,
                            text=True, check=False, stdin=subprocess.DEVNULL,
                            env=command_env(where), cwd=str(where))
    assert result.returncode == 0, (
        f"`payload_names`, run from {COMMAND}, exited {result.returncode}:\n"
        f"{result.stdout}{result.stderr}")
    names = result.stdout.splitlines()
    assert names, f"`payload_names`, run from {COMMAND}, printed nothing"
    return names


@pytest.fixture(scope="module")
def force_include(pyproject) -> dict:
    table = (pyproject.get("tool", {}).get("hatch", {}).get("build", {})
             .get("targets", {}).get("wheel", {}).get("force-include"))
    assert isinstance(table, dict) and table, (
        "pyproject.toml has no [tool.hatch.build.targets.wheel.force-include] "
        "table, or an empty one")
    return table


@NEEDS_BASH
def test_payload_map_keys_are_payload_names_and_the_pin_both_ways(
        force_include, payload_list):
    """ONE LIST (design.md Decision 2, FR-007). Every path the installer's
    `payload_names` prints, and the openRepoShape pin, is a key of the
    force-include map, and every key is one of them. Each difference is
    named, either way round: a payload file joins both lists in one commit.
    """
    expected = payload_list + [PIN]
    problems = [f"{name}: payload_names prints it, and the map has no key for it"
                for name in payload_list if name not in force_include]
    if PIN not in force_include:
        problems.append(f"{PIN}: the openRepoShape pin `wip init` reads, and "
                        "the map has no key for it")
    problems += [f"{key}: a key of the map, and neither in payload_names nor "
                 "the pin" for key in force_include if key not in expected]
    problems += [f"{name}: payload_names and the pin name it "
                 f"{expected.count(name)} times"
                 for name in sorted(set(expected)) if expected.count(name) > 1]
    assert not problems, (
        "pyproject.toml's force-include map is not the installer's "
        "payload_names plus the pin:" + listed(problems))


def test_payload_map_puts_each_path_at_openrepotools_payload(force_include):
    """Each entry is `"<P>" = "openrepotools/payload/<P>"`: the payload keeps
    its own relative paths inside the package, so the packaged
    `openRepoTools` finds its siblings, its skills and the pin beside itself
    exactly as a checkout's does."""
    wrong = [f'"{key}" = "{value}", not "{PAYLOAD_PREFIX}{key}"'
             for key, value in force_include.items()
             if value != PAYLOAD_PREFIX + key]
    assert not wrong, "force-include entries placed elsewhere:" + listed(wrong)


@NEEDS_BASH
def test_payload_map_lists_payload_names_in_its_own_order_then_the_pin(
        force_include, payload_list):
    """The map is written in `payload_names`' own order, then the pin, as
    `pyproject.toml`'s comment says and `package_layout` reads it, so the two
    lists can be read against each other line by line."""
    assert list(force_include) == payload_list + [PIN], (
        "the force-include keys are not payload_names' order then the pin:\n"
        f"  map:      {list(force_include)}\n"
        f"  expected: {payload_list + [PIN]}")


# --- a built wheel -----------------------------------------------------------

@pytest.fixture(scope="module")
def built_wheel():
    """The wheel `OPENREPOTOOLS_TEST_WHEEL` names, open, or a skip naming it."""
    value = os.environ.get(WHEEL_VARIABLE, "")
    if not value:
        pytest.skip(f"{WHEEL_VARIABLE} is unset: these tests check a built "
                    "wheel, and the suite builds none (a build fetches "
                    "hatchling). Set it to a wheel built from this checkout's "
                    "HEAD, as the package job does")
    path = Path(value)
    if not path.is_file():
        pytest.fail(f"{WHEEL_VARIABLE}={value} names no file (read from "
                    f"{Path.cwd()})", pytrace=False)
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        pytest.fail(f"{WHEEL_VARIABLE}={value} is not a wheel: {error}",
                    pytrace=False)
    with archive:
        yield archive


@pytest.fixture(scope="module")
def head_tree() -> dict:
    """Every path at this checkout's HEAD, as `(mode, type, object)`: the
    commit a built wheel is held to."""
    result = subprocess.run(["git", "ls-tree", "-r", "-z", "HEAD"],
                            cwd=str(REPO), capture_output=True, check=False)
    assert result.returncode == 0, (
        f"`git ls-tree -r HEAD` failed in {REPO}:\n"
        + result.stderr.decode("utf-8", "replace"))
    tree = {}
    for record in result.stdout.split(b"\0"):
        if record:
            meta, _, path = record.partition(b"\t")
            mode, kind, sha = meta.decode("ascii").split(" ")
            tree[path.decode("utf-8")] = (mode, kind, sha)
    return tree


def blob(sha: str) -> bytes:
    result = subprocess.run(["git", "cat-file", "blob", sha], cwd=str(REPO),
                            capture_output=True, check=False)
    assert result.returncode == 0, f"`git cat-file blob {sha}` failed in {REPO}"
    return result.stdout


def dist_info_dirs(archive: zipfile.ZipFile) -> list:
    return sorted({name.split("/", 1)[0] for name in archive.namelist()
                   if name.split("/", 1)[0].endswith(".dist-info")})


def test_wheel_payload_is_the_commits_blobs_byte_for_byte_and_mode_for_mode(
        built_wheel, head_tree):
    """contracts/wheel.md's CHECK 2 (FR-006).

    Each `openrepotools/payload/<P>` is `git show HEAD:<P>` byte for byte,
    and its mode is the one hatchling 1.27.0's reproducible build gives the
    commit's: 0755 for `100755` and 0644 for `100644` (clarifications N4). A
    `.gitattributes` filter that changed a byte is caught here, before
    anything ships.
    """
    members = [info for info in built_wheel.infolist()
               if info.filename.startswith(PAYLOAD_PREFIX)
               and not info.filename.endswith("/")]
    problems = [] if members else [f"the wheel holds nothing under "
                                   f"{PAYLOAD_PREFIX}"]
    for info in members:
        rel = info.filename[len(PAYLOAD_PREFIX):]
        mode, kind, sha = head_tree.get(rel, ("", "", ""))
        if kind != "blob" or mode not in ("100644", "100755"):
            problems.append(f"{info.filename}: HEAD holds no regular file {rel}"
                            + (f" (it holds a {kind} at {mode})" if kind else ""))
            continue
        if built_wheel.read(info) != blob(sha):
            problems.append(f"{info.filename}: its bytes are not HEAD's blob "
                            f"{sha[:12]} of {rel}")
        want = 0o755 if mode == "100755" else 0o644
        got = stat.S_IMODE(info.external_attr >> 16)
        if got != want:
            problems.append(f"{info.filename}: mode {got:04o}, and HEAD's "
                            f"{mode} gives {want:04o}")
    assert not problems, "the wheel's payload is not HEAD's:" + listed(problems)


def test_wheel_modules_are_the_commits_own(built_wheel, head_tree):
    """contracts/wheel.md's CHECK 3: each `openrepotools/<name>.py` other
    than the stamp is `src/openrepotools/<name>.py` at HEAD, byte for byte.
    The stamp is check 4's: the `package` job's wheel holds the committed one
    and a release's holds its own, and each workflow holds that itself."""
    problems = []
    for info in built_wheel.infolist():
        match = re.fullmatch(r"openrepotools/([^/]+\.py)", info.filename)
        if not match or match.group(1) == "_release.py":
            continue
        source = f"src/openrepotools/{match.group(1)}"
        mode, kind, sha = head_tree.get(source, ("", "", ""))
        if kind != "blob":
            problems.append(f"{info.filename}: HEAD holds no {source}")
        elif built_wheel.read(info) != blob(sha):
            problems.append(f"{info.filename}: its bytes are not HEAD's {source}")
    assert not problems, "the wheel's modules are not HEAD's:" + listed(problems)


def test_wheel_dist_info_is_the_five_names_with_the_commits_license(
        built_wheel, head_tree):
    """contracts/wheel.md's CHECK 5 (FR-002).

    One `openrepotools-<version>.dist-info/`, holding exactly `METADATA`,
    `WHEEL`, `RECORD`, `entry_points.txt` and `licenses/LICENSE`, and that
    `LICENSE` is HEAD's. THIS check, not hatchling, makes a missing `LICENSE`
    fatal: hatchling 1.27.0's `license-files` glob raises nothing for a
    pattern that matches no file.
    """
    dirs = dist_info_dirs(built_wheel)
    assert len(dirs) == 1 and re.fullmatch(r"openrepotools-[^/-]+\.dist-info",
                                           dirs[0]), (
        f"the wheel's .dist-info directories are {dirs}, not one "
        "openrepotools-<version>.dist-info")
    prefix = dirs[0] + "/"
    held = [name[len(prefix):] for name in built_wheel.namelist()
            if name.startswith(prefix)]
    problems = [f"{prefix}{name}: missing" for name in DIST_INFO
                if name not in held]
    problems += [f"{prefix}{name}: not one of the five names" for name in held
                 if name not in DIST_INFO]
    mode, kind, sha = head_tree.get("LICENSE", ("", "", ""))
    if kind != "blob":
        problems.append("HEAD holds no LICENSE, and a wheel of it must not ship")
    elif "licenses/LICENSE" in held \
            and built_wheel.read(prefix + "licenses/LICENSE") != blob(sha):
        problems.append(f"{prefix}licenses/LICENSE: its bytes are not HEAD's "
                        "LICENSE")
    assert not problems, "the wheel's .dist-info is not FR-002's:" \
        + listed(problems)


@NEEDS_BASH
def test_wheel_holds_its_member_list_and_nothing_else(built_wheel,
                                                      payload_list):
    """contracts/wheel.md's CHECK 6, AND ITS LIST HELD THE OTHER WAY TOO.

    The members are the modules, the 24 payload files and the `.dist-info`
    names, and "the wheel holds nothing else": a member outside
    the list is named, and so is one the list has and the wheel lacks, which
    checks 2, 3 and 5 alone would pass over. A wheel without `cli.py` has no
    console script to run. A name the archive holds twice is named too.
    """
    names = built_wheel.namelist()
    dirs = dist_info_dirs(built_wheel)
    expected = ([f"openrepotools/{module}" for module in MODULES]
                + [PAYLOAD_PREFIX + rel for rel in payload_list + [PIN]]
                + [f"{d}/{name}" for d in dirs[:1] for name in DIST_INFO])
    problems = [] if len(dirs) == 1 else [f"the wheel has {len(dirs)} "
                                          f".dist-info directories: {dirs}"]
    problems += [f"{name}: in the wheel {names.count(name)} times"
                 for name in sorted(set(names)) if names.count(name) > 1]
    problems += [f"{name}: in the wheel, and not on its member list"
                 for name in sorted(set(names)) if name not in expected]
    problems += [f"{name}: on the member list, and not in the wheel"
                 for name in expected if name not in names]
    assert not problems, "the wheel's members are not contracts/wheel.md's:" \
        + listed(problems)


@NEEDS_BASH
def test_wheel_payload_members_are_payload_names_and_the_pin_both_ways(
        built_wheel, payload_list):
    """THE MEMBER COMPARISON (FR-007): the wheel's payload members against
    the installer's `payload_names` plus the pin, both ways round, each
    difference named. An `export-ignore` on a payload path, or a map entry
    that hatchling dropped, fails here."""
    expected = payload_list + [PIN]
    held = [name[len(PAYLOAD_PREFIX):] for name in built_wheel.namelist()
            if name.startswith(PAYLOAD_PREFIX)]
    problems = [f"{rel}: payload_names or the pin names it, and the wheel has "
                f"no {PAYLOAD_PREFIX}{rel}" for rel in expected if rel not in held]
    problems += [f"{PAYLOAD_PREFIX}{rel}: in the wheel, and neither in "
                 "payload_names nor the pin" for rel in held if rel not in expected]
    assert not problems, ("the wheel's payload is not payload_names plus the "
                          "pin:" + listed(problems))


# --- the console script ------------------------------------------------------

class Installed(NamedTuple):
    """A `package_tree` in a real virtual environment, and pip's console
    script for it."""
    prefix: Path
    python: Path
    payload: Path
    script: Path


@pytest.fixture(scope="module")
def installed(tmp_path_factory) -> Installed:
    """THE PACKAGE AS pip INSTALLS IT, WITHOUT pip AND WITHOUT A WHEEL.

    `python -m venv --without-pip` makes a real environment from the standard
    library alone, so its own `bin/python` imports from its own
    `site-packages`. `package_tree` builds the package there from this
    checkout, and `console_script` writes pip's script for the entry point at
    `bin/openRepoTools`, naming that `python`, in the form pip itself would
    choose for the path. Nothing is fetched.

    The fixture proves that the environment imports the package before any
    test runs. So a test that fails on `openrepotools.cli` fails on the
    entry module, never on the layout.
    """
    prefix = tmp_path_factory.mktemp("entry") / "prefix"
    made = subprocess.run([sys.executable, "-m", "venv", "--without-pip",
                           str(prefix)], capture_output=True, text=True,
                          check=False)
    assert made.returncode == 0, (
        f"the fixture could not make a virtual environment at {prefix}:\n"
        f"{made.stdout}{made.stderr}")
    python = prefix / "bin" / "python"
    asked = subprocess.run(
        [str(python), "-I", "-c",
         "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        capture_output=True, text=True, check=False)
    assert asked.returncode == 0, f"{python} would not run:\n{asked.stderr}"
    purelib = Path(asked.stdout.strip())
    try:
        parts = purelib.resolve().relative_to(prefix.resolve()).parts
    except ValueError:
        parts = ()
    assert (len(parts) == 3 and parts[0] == "lib"
            and parts[2] == "site-packages"), (
        f"the environment's site-packages is {purelib}, not "
        f"{prefix}/lib/<python>/site-packages, the layout package_tree builds")
    payload = package_tree(prefix, parts[1])
    imported = subprocess.run(
        [str(python), "-I", "-c",
         "import openrepotools; print(openrepotools.__file__)"],
        capture_output=True, text=True, check=False)
    assert (imported.returncode == 0
            and Path(imported.stdout.strip()).resolve()
            == (payload.parent / "__init__.py").resolve()), (
        f"{python} does not import the package_tree at {payload.parent}:\n"
        f"{imported.stdout}{imported.stderr}")
    script = console_script(prefix / "bin" / "openRepoTools", str(python))
    return Installed(prefix, python, payload, script)


def said(result) -> str:
    return (f"exit {result.returncode}\n--- stdout\n{result.stdout}"
            f"--- stderr\n{result.stderr}")


def run_entry(script: Path, *args: str, home: Path, env: dict | None = None,
              cwd: Path | None = None) -> subprocess.CompletedProcess:
    """The console script, run as a person runs it: by its path, so the
    kernel reads its first line. Stdin is a pipe, never a terminal."""
    return subprocess.run([str(script), *args], capture_output=True,
                          text=True, check=False, input="",
                          env=command_env(home, env),
                          cwd=None if cwd is None else str(cwd))


def recording_bash(directory: Path, record: Path) -> Path:
    """A `bash` that writes down what it was given and runs nothing.

    It writes its own pid, then each argument in brackets on a line of its
    own, and exits 0. First on PATH, it is the `bash` the entry module's
    `execvp` finds; the pid says whether that `bash` runs in the console
    script's own process. No argument a test passes holds a newline.
    """
    directory.mkdir(parents=True, exist_ok=True)
    shim = directory / "bash"
    shim.write_text("#!/bin/sh\n"
                    "{\n"
                    "\tprintf '%s\\n' \"$$\"\n"
                    "\tfor arg in \"$@\"; do printf '[%s]\\n' \"$arg\"; done\n"
                    "} > " + shlex.quote(str(record)) + "\n"
                    "exit 0\n", encoding="utf-8")
    shim.chmod(0o755)
    return shim


def read_record(record: Path) -> tuple:
    """`(pid, [argument, ...])`, as `recording_bash` wrote them."""
    lines = record.read_text(encoding="utf-8").split("\n")
    assert len(lines) >= 2 and lines[-1] == "", f"a torn record: {lines!r}"
    arguments = []
    for line in lines[1:-1]:
        assert line.startswith("[") and line.endswith("]"), (
            f"a record line that is not one argument: {line!r}")
        arguments.append(line[1:-1])
    return int(lines[0]), arguments


#: Arguments a shell would split, glob or expand, and an empty one: each must
#: reach `bash` exactly as given.
EXEC_ARGUMENTS = ("wip", "init", "two words", "*", "$HOME", "", "--version")


@NEEDS_BASH
@WINDOWS_SKIP
def test_entry_execs_the_first_bash_on_path_with_the_payload_and_the_arguments(
        installed, tmp_path):
    """DESIGN.MD DECISION 3, WORD FOR WORD (FR-003).

    The console script runs `os.execvp("bash", ["bash", <payload>/openRepoTools,
    *sys.argv[1:]])`: the FIRST `bash` on PATH, in the console script's OWN
    PROCESS, given the packaged `openRepoTools` by its absolute path and then
    the person's arguments unchanged, and nothing beyond them. The pid is
    what tells an exec from a child: a child's signals and exit status would
    come back through Python, and its `EXIT` trap would run in a process the
    person's terminal does not own.
    """
    record = tmp_path / "bash-was-given"
    shim = recording_bash(tmp_path / "first-on-path", record)
    home = tmp_path / "home"
    home.mkdir()
    run = subprocess.Popen(
        [str(installed.script), *EXEC_ARGUMENTS], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=command_env(home, {
            "PATH": f"{shim.parent}{os.pathsep}{os.environ['PATH']}"}),
        cwd=str(tmp_path))
    out, err = run.communicate(timeout=60)
    assert run.returncode == 0 and record.is_file(), (
        "the console script never ran the first bash on PATH:\n"
        f"exit {run.returncode}\n--- stdout\n{out}--- stderr\n{err}")
    pid, given = read_record(record)
    assert pid == run.pid, (
        f"bash ran as pid {pid}, and the console script was pid {run.pid}: "
        "the entry module ran bash as a child instead of replacing itself")
    assert given[:1] and os.path.isabs(given[0]) and (
        Path(given[0]).resolve() == (installed.payload / "openRepoTools").resolve()), (
        f"bash was given {given[:1]} as its script, not the packaged "
        f"{installed.payload / 'openRepoTools'}")
    assert given[1:] == list(EXEC_ARGUMENTS), (
        f"the arguments reached bash as {given[1:]!r}, not as given: "
        f"{list(EXEC_ARGUMENTS)!r}")


#: `(arguments, what the payload's refusal says)`: the top-level parser's
#: refusal, `--install`'s refusal of a second argument, `wip`'s two, and one
#: whose argument the refusal repeats back, spaces, glob and `$` included.
REFUSED_ARGUMENTS = [
    (("Atlas",), "installs the estate commands and creates the workspace they read"),
    (("--install", "Atlas"), "creates the workspace they read"),
    (("wip", "destroy"), "`wip destroy` is not a thing this command does"),
    (("wip", "init", "--org"), "--org needs a value"),
    (("wip", "init", "two words * $HOME"), "It got 'two words * $HOME'."),
]


@pytest.mark.parametrize("form", ["shebang", "trampoline"])
@pytest.mark.parametrize(
    "arguments, says", REFUSED_ARGUMENTS,
    ids=["unknown", "install-and-more", "wip-verb", "wip-option-value",
         "argument-repeated"])
@NEEDS_BASH
@WINDOWS_SKIP
def test_entry_a_refused_argument_is_the_payloads_own_refusal(
        installed, tmp_path, form, arguments, says):
    """US1 SCENARIO 6: WHEN THE PAYLOAD REFUSES, THE CONSOLE SCRIPT ADDS
    NOTHING. Its exit status, its stdout and its stderr are exactly what
    `bash <payload>/openRepoTools` gives for the same arguments, in both
    forms pip writes a console script in (a `#!` line, and the `/bin/sh`
    trampoline for a long or spaced interpreter path). Nothing is placed.
    """
    script = console_script(tmp_path / "bin" / "openRepoTools",
                            str(installed.python), form=form)
    home = tmp_path / "home"
    home.mkdir()
    direct = subprocess.run(
        ["bash", str(installed.payload / "openRepoTools"), *arguments],
        capture_output=True, text=True, check=False, input="",
        env=command_env(home), cwd=str(tmp_path))
    assert direct.returncode == 2 and says in direct.stderr, (
        "the case is wrong: the payload itself does not refuse it that way:\n"
        + said(direct))
    through = run_entry(script, *arguments, home=home, cwd=tmp_path)
    assert (through.returncode, through.stdout, through.stderr) == (
        direct.returncode, direct.stdout, direct.stderr), (
        "the console script's answer is not the payload's own.\n"
        f"=== the console script\n{said(through)}\n"
        f"=== bash <payload>/openRepoTools\n{said(direct)}")
    assert list(home.iterdir()) == [], "a refused run placed something"


def kill_group(run: subprocess.Popen) -> None:
    """SIGKILL to the session a run was started in, if any of it is left."""
    if run.poll() is None:
        try:
            os.killpg(run.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


@pytest.mark.parametrize("slow", sorted(SLOW_TOOLS))
@NEEDS_BASH
@WINDOWS_SKIP
@NEEDS_JQ
def test_entry_a_sigterm_mid_placement_leaves_no_placement_temporary(
        installed, tmp_path, slow):
    """US1 SCENARIO 7, THROUGH THE CONSOLE SCRIPT (FR-003).

    A package-mode `--install` started by the console script is holding a
    placement temporary, made slow by a `cp` or a `mktemp` first on PATH, as
    `tests/test_openrepotools_command.py`'s own case makes it. A SIGTERM
    goes to the pid the person started, and only to it. Because the entry
    module replaced itself with bash, that pid IS the payload's bash: its
    `EXIT` trap removes the temporary, and the run dies of the signal with
    the install unfinished. Run as a child instead, Python would die, and
    the payload's bash would go on placing files nobody asked it to.
    """
    real = shutil.which(slow)
    if real is None:
        pytest.skip(f"no real `{slow}` on PATH for the slow one to defer to")
    shim = tmp_path / f"slow-{slow}"
    shim.mkdir()
    (shim / slow).write_text(
        "#!/bin/sh\n" + SLOW_TOOLS[slow].format(real=real), encoding="utf-8")
    (shim / slow).chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()

    def default_signals() -> None:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    run = subprocess.Popen(
        [str(installed.script), "--install"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=command_env(home, {
            "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}),
        cwd=str(tmp_path), start_new_session=True, preexec_fn=default_signals)
    try:
        deadline = time.monotonic() + 60
        while (time.monotonic() < deadline and run.poll() is None
               and not placement_temporaries(home)):
            time.sleep(0.05)
        if not placement_temporaries(home):
            kill_group(run)
            out, err = run.communicate(timeout=60)
            pytest.fail("no placement ever made a temporary for the signal to "
                        f"land beside:\nexit {run.returncode}\n--- stdout\n"
                        f"{out}--- stderr\n{err}", pytrace=False)
        run.send_signal(signal.SIGTERM)
        try:
            out, err = run.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            pytest.fail("the install outlived its SIGTERM by a minute: the "
                        "signal did not reach the payload's bash, so the entry "
                        "module runs bash as a child instead of replacing "
                        "itself", pytrace=False)
    finally:
        if run.poll() is None:
            kill_group(run)
            run.communicate()
    assert run.returncode in (-signal.SIGTERM, 128 + signal.SIGTERM), (
        f"the run did not die of SIGTERM: exit {run.returncode}\n{out}{err}")
    assert placement_temporaries(home) == [], (
        "a placement temporary outlived the signal")
    assert "placed in" not in out, (
        "the install went on after the signal, so the pid that took it was "
        f"not the payload's bash:\n{out}")


#: THE SIGNALS PYTHON IGNORES AT START-UP, which the entry module must set
#: back to `SIG_DFL` before its exec (design.md Decision 3 as amended on
#: 2026-10-18, FR-003). By name, so a platform without one checks the other.
PYTHON_IGNORES = tuple((name, getattr(signal, name))
                       for name in ("SIGPIPE", "SIGXFSZ")
                       if hasattr(signal, name))


def signal_reading_bash(directory: Path, record: Path, real: str) -> Path:
    """A `bash` that writes down the signals it started with ignored, and
    runs nothing else.

    It IS a bash: its `#!` line names the real one, so the process the
    console script's exec becomes is a bash, as the payload's is. It writes
    its own pid; then, where `/proc/$$/status` can be read (Linux), that
    file's `SigIgn:` line, read by the shell itself with no child between, so
    the mask is the one this process started with; then the status a
    `yes | head -n 1` pipeline ends in under `pipefail`. That is 141,
    128 + SIGPIPE, when SIGPIPE kills `yes`, and 1, with a "Broken pipe" line
    on stderr, when `yes` inherited it ignored.
    """
    directory.mkdir(parents=True, exist_ok=True)
    shim = directory / "bash"
    shim.write_text("#!" + real + "\n"
                    "{\n"
                    "\tprintf 'pid %s\\n' \"$$\"\n"
                    "\tif [ -r \"/proc/$$/status\" ]; then\n"
                    "\t\twhile IFS= read -r line; do\n"
                    "\t\t\tcase $line in\n"
                    "\t\t\t\tSigIgn:*) printf '%s\\n' \"$line\" ;;\n"
                    "\t\t\tesac\n"
                    "\t\tdone < \"/proc/$$/status\"\n"
                    "\tfi\n"
                    "\tset -o pipefail\n"
                    "\tyes | head -n 1 > /dev/null\n"
                    "\tprintf 'pipeline %s\\n' \"$?\"\n"
                    "} > " + shlex.quote(str(record)) + "\n"
                    "exit 0\n", encoding="utf-8")
    shim.chmod(0o755)
    return shim


@NEEDS_BASH
@WINDOWS_SKIP
def test_entry_the_bash_it_execs_has_neither_sigpipe_nor_sigxfsz_ignored(
        installed, tmp_path):
    """FR-003: SIGNALS PASS THROUGH AS IF THE PERSON HAD RUN THE PAYLOAD WITH
    BASH DIRECTLY, so the bash the console script becomes starts with
    neither signal Python ignores at start-up still ignored.

    An exec keeps an ignored disposition, and a non-interactive bash cannot
    reset one it was started with, so a SIGPIPE Python left ignored would
    turn every `yes | head` inside the payload into a "Broken pipe" and a
    status of 1. This reads the state AFTER THE EXEC, in the bash process
    itself (`signal_reading_bash`, first on PATH), so it proves what bash
    inherited and not what Python set. The pid proves that the process read
    is the one the console script became. On Linux the `SigIgn` mask must
    hold neither signal; on every platform the pipeline must end in 141.

    The console script's Python is started with `restore_signals=True`, so
    it starts with both at `SIG_DFL`: whatever bash finds ignored, the
    console script's own Python left it so.
    """
    real = shutil.which("bash")
    record = tmp_path / "bash-started-with"
    shim = signal_reading_bash(tmp_path / "first-on-path", record,
                               str(Path(real).resolve()))
    home = tmp_path / "home"
    home.mkdir()
    run = subprocess.Popen(
        [str(installed.script), "--version"], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=command_env(home, {
            "PATH": f"{shim.parent}{os.pathsep}{os.environ['PATH']}"}),
        cwd=str(tmp_path), restore_signals=True)
    out, err = run.communicate(timeout=60)
    assert run.returncode == 0 and record.is_file(), (
        "the console script never ran the first bash on PATH:\n"
        f"exit {run.returncode}\n--- stdout\n{out}--- stderr\n{err}")
    lines = record.read_text(encoding="utf-8").splitlines()
    pids = [line[len("pid "):] for line in lines if line.startswith("pid ")]
    masks = [line[len("SigIgn:"):].strip() for line in lines
             if line.startswith("SigIgn:")]
    statuses = [line[len("pipeline "):] for line in lines
                if line.startswith("pipeline ")]
    assert pids == [str(run.pid)], (
        f"bash recorded pid {pids}, and the console script was pid {run.pid}: "
        "what was read is not the process the console script became")
    problems = []
    if sys.platform.startswith("linux"):
        if len(masks) != 1 or not re.fullmatch(r"[0-9a-fA-F]+", masks[0]):
            problems.append(f"bash read no one SigIgn mask from "
                            f"/proc/<pid>/status: {masks!r}")
        else:
            mask = int(masks[0], 16)
            for name, number in PYTHON_IGNORES:
                if (mask >> (number - 1)) & 1:
                    problems.append(f"{name} is ignored in the bash the "
                                    f"console script became (SigIgn "
                                    f"{masks[0]}, bit {number - 1})")
    wanted = str(128 + signal.SIGPIPE)
    if statuses != [wanted]:
        problems.append(f"`yes | head -n 1` under pipefail ended in "
                        f"{statuses}, not [{wanted!r}], the status SIGPIPE "
                        "kills `yes` with")
    assert not problems, (
        "the bash the console script became started with a signal Python "
        "ignores still ignored:" + listed(problems)
        + "\n--- the record\n" + "\n".join(lines) + f"\n--- stderr\n{err}")


@WINDOWS_SKIP
def test_entry_with_no_bash_on_path_refuses_exactly_and_runs_nothing(
        installed, tmp_path):
    """FR-004: NO `bash` ON PATH IS A REFUSAL, AND NOTHING ELSE HAPPENS.

    PATH is every executable the real one carries but `bash`. The console
    script's interpreter is named by its absolute path, so it starts, and
    the entry module finds no `bash`. It prints contracts/cli-output.md's
    line exactly, on stderr, and exits 2, the status `die` refuses with. It
    falls back on no other shell and no fixed path: the `--install` asked
    for places nothing and prints nothing, because nothing ran.
    """
    path = path_without(tmp_path, "bash")
    home = tmp_path / "home"
    home.mkdir()
    result = run_entry(installed.script, "--install", home=home,
                       env={"PATH": path}, cwd=tmp_path)
    assert (result.returncode, result.stdout, result.stderr) == (
        2, "", NO_BASH + "\n"), (
        f"not the exact no-bash refusal:\n{said(result)}")
    assert list(home.iterdir()) == [], (
        "something ran, and placed files, with no bash on PATH")


@WINDOWS_SKIP
def test_entry_with_no_bash_and_path_ending_in_a_file_refuses_exactly(
        installed, tmp_path):
    """FR-004, WHERE `PATH`'S LAST ENTRY IS A FILE: the same refusal.

    `os.execvp` raises the error of the last entry it tried, so with no
    `bash` anywhere and a regular file as `PATH`'s last entry it raises
    `NotADirectoryError`, not `FileNotFoundError`. The case is checked
    first, in the console script's own interpreter, so this cannot pass by
    reaching the other arm. Then the console script must print
    contracts/cli-output.md's line exactly, on stderr, and exit 2, as with
    no `bash` on any `PATH`: not a traceback and exit 1. The `--install`
    asked for places nothing and prints nothing, because nothing ran.
    """
    last = tmp_path / "a-file-not-a-directory"
    last.write_text("PATH's last entry, and not a directory\n",
                    encoding="utf-8")
    path = f"{path_without(tmp_path, 'bash')}{os.pathsep}{last}"
    probe = subprocess.run(
        [str(installed.python), "-I", "-c",
         "import os\n"
         "try:\n"
         "    os.execvp('bash', ['bash', '-c', 'exit 97'])\n"
         "except OSError as error:\n"
         "    print(type(error).__name__)\n"],
        capture_output=True, text=True, check=False,
        stdin=subprocess.DEVNULL, env={"PATH": path})
    assert (probe.returncode, probe.stdout) == (0, "NotADirectoryError\n"), (
        "the case is wrong: on this PATH execvp does not raise "
        f"NotADirectoryError:\n{said(probe)}")
    home = tmp_path / "home"
    home.mkdir()
    result = run_entry(installed.script, "--install", home=home,
                       env={"PATH": path}, cwd=tmp_path)
    assert (result.returncode, result.stdout, result.stderr) == (
        2, "", NO_BASH + "\n"), (
        f"not the exact no-bash refusal:\n{said(result)}")
    assert list(home.iterdir()) == [], (
        "something ran, and placed files, with no bash on PATH")


#: What `wip_shape_ref` reaches only when there is no pin beside the
#: installer: the fetch path. Each stands in as a refusal naming itself, so a
#: run that went past the packaged pin says so instead of fetching.
FETCH_PATH = ("workdir", "payload_probe", "payload_resolve_remote",
              "fetch_from_repo")


def pin_commit(pin: Path) -> str:
    """The pin's `commit:`, read as YAML spells it here: 40 lower-case hex
    digits, quoted or not."""
    found = re.findall(r'(?m)^commit:[ \t]*"?([0-9a-f]{40})"?[ \t]*$',
                       pin.read_text(encoding="utf-8"))
    assert len(found) == 1, f"{pin} has {len(found)} `commit:` lines, not one"
    return found[0]


@NEEDS_BASH
@WINDOWS_SKIP
def test_entry_wip_shape_ref_reads_the_pin_packaged_beside_the_payload(
        installed, tmp_path):
    """US1 SCENARIO 9 (FR-008): `wip init` FROM THE PACKAGE READS THE
    RELEASE'S OWN openRepoShape PIN, and never the network's.

    The path the console script hands bash is read back, with
    `recording_bash`, from a working directory far from any checkout. Then
    the installer's own `wip_shape_ref`, cut out with `installer_function`,
    runs with `$SELF` set to that path, as the packaged `openRepoTools` sets
    it from `BASH_SOURCE`. It prints the commit of the pin packaged beside
    the payload, the force-include map's 24th entry, and reaches nothing on
    the fetch path to get it.
    """
    record = tmp_path / "bash-was-given"
    shim = recording_bash(tmp_path / "first-on-path", record)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    started = run_entry(installed.script, "wip", "init", home=home, env={
        "PATH": f"{shim.parent}{os.pathsep}{os.environ['PATH']}"},
        cwd=elsewhere)
    assert started.returncode == 0 and record.is_file(), (
        "the console script never ran the first bash on PATH:\n"
        + said(started))
    _, given = read_record(record)
    assert given, "bash was given no script"
    stubs = "".join(
        f"{name}() {{ printf 'wip_shape_ref passed the pin beside %s and "
        f"reached {name}\\n' \"$SELF\" >&2; exit 97; }}\n"
        for name in FETCH_PATH)
    harness = tmp_path / "wip-shape-ref.sh"
    harness.write_text("set -euo pipefail\n"
                       'SELF="$1"\n'
                       "die() { printf '\\nREFUSED: %s\\n' \"$1\" >&2; exit 2; }\n"
                       + stubs + installer_function("wip_shape_ref")
                       + "wip_shape_ref\n", encoding="utf-8")
    result = subprocess.run(["bash", str(harness), given[0]],
                            capture_output=True, text=True, check=False,
                            stdin=subprocess.DEVNULL, env=command_env(home),
                            cwd=str(elsewhere))
    packaged = installed.payload / PIN
    assert packaged.read_bytes() == (REPO / PIN).read_bytes(), (
        "the package does not carry this checkout's pin")
    expected = pin_commit(packaged)
    assert (result.returncode, result.stdout, result.stderr) == (
        0, expected + "\n", ""), (
        f"wip_shape_ref, run from {given[0]}, did not read the packaged "
        f"pin's commit {expected}:\n{said(result)}")
