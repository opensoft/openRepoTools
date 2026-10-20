# SPDX-License-Identifier: Apache-2.0
"""Fake installed layouts of the `openrepotools` package, for the suite (#228).

The pipx, stamp and entry-module tests need the package as pip and pipx lay
it out on disk, without pip, without pipx and without a wheel: building a
wheel fetches hatchling, and this suite reaches no network. These builders
make that layout out of this checkout's own files, in a directory the test
owns:

- `package_tree(prefix, python, stamp)` builds
  `<prefix>/lib/<python>/site-packages/openrepotools/` and returns its
  `payload/` directory;
- `pipx_venv(pipx_home, release, python, stamp)` builds
  `<pipx_home>/venvs/openrepotools/` around a `package_tree`, as pipx 1.11.1,
  1.17.8 and 1.18.3 lay one out, and returns the venv;
- `console_script(path, python, form)` writes pip's console script for
  `openrepotools.cli:main`, in either of the two forms pip writes;
- `stamp_text(**fields)` gives the committed stamp's text with the given
  values.

STANDARD LIBRARY ONLY, AND NOTHING FROM THE SUITE: no `conftest`, no pytest.
So the module loads the same way under pytest, under a task's
`python3 -I -c` verify command and in a workflow step, on Python 3.9 (the
`package` job's) and up. It finds the repository from its own path, as the
parent of the `tests/` it sits in: the code root, which holds `src/`,
`pyproject.toml` and every payload file in every layout this suite runs in.

PATHS, NEVER A SHELL: every path here is a `pathlib.Path` and no builder runs
a command, so a directory with a space in it, as macOS's default pipx home
`~/Library/Application Support/pipx` has, is built like any other.
"""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path

#: THE CODE ROOT: the parent of this file's `tests/`.
REPO = Path(__file__).resolve().parent.parent

#: Where the package's modules live in the checkout, and the stamp among them.
PACKAGE_SOURCE = REPO / "src" / "openrepotools"
STAMP_SOURCE = PACKAGE_SOURCE / "_release.py"

#: THE WHEEL'S DECLARED PAYLOAD: `pyproject.toml`'s force-include table, each
#: entry `"<P>" = "openrepotools/payload/<P>"`. A built wheel holds exactly
#: these files, so a fake layout copies exactly these, in the table's order.
PYPROJECT = REPO / "pyproject.toml"
FORCE_INCLUDE = "[tool.hatch.build.targets.wheel.force-include]"
PAYLOAD_PREFIX = "openrepotools/payload/"

#: The one console script, as `[project.scripts]` declares it.
ENTRY_POINT = "openrepotools.cli:main"

#: THE PIPX RELEASES THE FIXTURES MIRROR, each with the interpreter its row of
#: contracts/pipx-link.md's matrix uses. 1.11.1 and 1.17.8 are what the
#: model's install check locks for Python below 3.10 and from 3.10 on, and
#: 1.18.3 was the newest on PyPI on 2026-10-17. Each of them puts a package's
#: venv at `<home>/venvs/<package>`, so the layout is the same in all three;
#: the release is recorded in the placeholder metadata, so that a fixture
#: says which row it is.
PIPX_RELEASES = {"1.11.1": "python3.9", "1.17.8": "python3.12",
                 "1.18.3": "python3.13"}

#: THE STAMP'S FIVE FIELDS, with the values the committed file holds
#: (contracts/stamp.md). Each committed line is `NAME = "VALUE"`.
STAMP_FIELDS = ("VERSION", "TAG", "COMMIT", "DIGEST", "REPOSITORY")
UNSTAMPED = {"VERSION": "0.0.0", "TAG": "", "COMMIT": "", "DIGEST": "",
             "REPOSITORY": ""}

#: THE LONGEST SHEBANG LINE pip writes as a plain `#!<python>`, counting the
#: `#!` and the newline: distlib's limit on Linux
#: (`pip/_vendor/distlib/scripts.py`, `_build_shebang`, in pip 26.2.1). pip
#: allows 512 on macOS; a fixture uses Linux's limit on every platform, so
#: that it is the same file wherever the suite runs, and `form=` forces
#: either form where a test needs that one.
SHEBANG_LIMIT = 127

#: PIP'S CONSOLE-SCRIPT TEMPLATE: `PipScriptMaker.script_template`
#: (`pip/_internal/operations/install/wheel.py:417-426` in pip 26.2.1),
#: filled in as distlib's `_get_script_text` fills it. The import is at
#: column 0, in both forms.
SCRIPT_TEMPLATE = ("import sys\n"
                   "from %(module)s import %(import_name)s\n"
                   "if __name__ == '__main__':\n"
                   "    sys.argv[0] = sys.argv[0].removesuffix('.exe')\n"
                   "    sys.exit(%(func)s())\n")


class LayoutError(RuntimeError):
    """The checkout does not hold what a fake layout is built from."""


def payload_paths() -> tuple[str, ...]:
    """The payload paths `<P>`, in the force-include table's order.

    READ BY LINE, because Python 3.9 has no `tomllib` and the suite takes
    nothing outside the standard library. The table's header is found as its
    own line, and every line up to the next header is a comment, a blank, or
    `"<P>" = "openrepotools/payload/<P>"` with `<P>` a relative path. Any
    other line refuses, naming itself, rather than build a layout from a map
    this reading did not understand. Where `tomllib` exists, it reads the
    same table, and the two readings must agree.

    Read at each call, not at import: a broken map then fails the builder
    that needs it, and leaves `tests/test_package.py`'s own map test free to
    name every difference.
    """
    text = PYPROJECT.read_bytes().decode("utf-8")
    lines = text.split("\n")
    headers = [i for i, line in enumerate(lines)
               if line.strip() == FORCE_INCLUDE]
    if len(headers) != 1:
        raise LayoutError(f"{PYPROJECT} has {len(headers)} {FORCE_INCLUDE} "
                          "headers, not one")
    entry = re.compile(r'"([^"\\]+)" = "([^"\\]+)"')
    paths: list[str] = []
    for number in range(headers[0] + 1, len(lines)):
        line = lines[number].strip()
        if line.startswith("["):
            break
        if not line or line.startswith("#"):
            continue
        match = entry.fullmatch(line)
        rel = match.group(1) if match else ""
        if (not match or match.group(2) != PAYLOAD_PREFIX + rel
                or {"", ".", ".."} & set(rel.split("/")) or rel in paths):
            raise LayoutError(
                f"{PYPROJECT}:{number + 1}: not a new "
                f'`"<P>" = "{PAYLOAD_PREFIX}<P>"` entry: {line}')
        paths.append(rel)
    if not paths:
        raise LayoutError(f"{PYPROJECT}'s {FORCE_INCLUDE} table is empty")
    try:
        import tomllib
    except ImportError:   # Python 3.9 and 3.10: the reading above is the one
        return tuple(paths)
    table = (tomllib.loads(text).get("tool", {}).get("hatch", {})
             .get("build", {}).get("targets", {}).get("wheel", {})
             .get("force-include", {}))
    if list(table.items()) != [(p, PAYLOAD_PREFIX + p) for p in paths]:
        raise LayoutError(f"{PYPROJECT}'s {FORCE_INCLUDE} table reads one way "
                          "by line and another by tomllib")
    return tuple(paths)


def _segment(value: str, what: str) -> str:
    """`value`, refused unless it is one path segment."""
    if (not isinstance(value, str) or value in ("", ".", "..")
            or "/" in value or "\0" in value):
        raise ValueError(f"{what} must be one path segment, not {value!r}")
    return value


def _place(data: bytes, target: Path, mode: int) -> Path:
    """Write `data` at `target` with `mode`, replacing what is there.

    A file or link already at `target` is removed first, so a builder run
    twice over one tree (an upgrade, say) never writes through a link a test
    left there, and never trips over a mode a test set.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.is_file():
        target.unlink()
    target.write_bytes(data)
    os.chmod(target, mode)
    return target


def package_tree(prefix: os.PathLike | str, python: str = "python3.12",
                 stamp: str | bytes | None = None) -> Path:
    """`<prefix>/lib/<python>/site-packages/openrepotools/`, as pip installs
    the wheel there. Returns its `payload/` directory.

    - Every `src/openrepotools/*.py` the checkout holds is copied at 0644:
      `__init__.py` and `_release.py`, and `cli.py` once it exists.
    - `stamp`, when given, is written as `_release.py` in place of the
      committed one, byte for byte (`stamp_text` makes one).
    - `payload/` holds every file the force-include table names, byte for
      byte from the checkout, at 0755 where the checkout's copy is
      owner-executable and 0644 otherwise, as hatchling's wheel gives them.

    Nothing is read from anywhere but the checkout, so the tree is the one a
    wheel built from it would install.
    """
    package = (Path(prefix) / "lib" / _segment(python, "python")
               / "site-packages" / "openrepotools")
    modules = sorted(p for p in PACKAGE_SOURCE.glob("*.py") if p.is_file())
    if STAMP_SOURCE not in modules:
        raise LayoutError(f"{STAMP_SOURCE} is missing: the package has no "
                          "stamp to copy")
    for module in modules:
        _place(module.read_bytes(), package / module.name, 0o644)
    if stamp is not None:
        data = stamp.encode("utf-8") if isinstance(stamp, str) else bytes(stamp)
        _place(data, package / "_release.py", 0o644)
    payload = package / "payload"
    for rel in payload_paths():
        source = REPO / rel
        if not source.is_file():
            raise LayoutError(f"{PYPROJECT} names {rel}, and {source} is not "
                              "a file")
        mode = 0o755 if source.stat().st_mode & stat.S_IXUSR else 0o644
        _place(source.read_bytes(), payload / rel, mode)
    return payload


def pipx_venv(pipx_home: os.PathLike | str, release: str,
              python: str | None = None,
              stamp: str | bytes | None = None) -> Path:
    """`<pipx_home>/venvs/openrepotools/`, as pipx `release` leaves it once
    `pipx install openrepotools` is done. Returns the venv.

    - `lib/<python>/site-packages/openrepotools/` is a `package_tree`, with
      `stamp` passed on. `python` defaults to `release`'s interpreter in
      `PIPX_RELEASES`.
    - `bin/openRepoTools` is pip's console script, naming the venv's own
      `bin/python` as pip does inside a pipx venv. So under a home whose path
      holds a space it is pip's `/bin/sh` trampoline, as on macOS's default
      pipx home, and a plain `#!` line otherwise.
    - `pipx_metadata.json` and `pyvenv.cfg` hold placeholder content, because
      pipx's link is recognised by their existence alone: nothing parses
      either, and no fixture holds an interpreter.

    The link in `<dir>` is the test's to make, absolute or relative, because
    that is what contracts/pipx-link.md's matrix varies. `PIPX_HOME` is never
    read here.
    """
    if release not in PIPX_RELEASES:
        raise ValueError(f"pipx {release!r} is not one of the releases the "
                         f"fixtures mirror: {', '.join(PIPX_RELEASES)}")
    python = PIPX_RELEASES[release] if python is None else python
    venv = Path(pipx_home).absolute() / "venvs" / "openrepotools"
    package_tree(venv, python, stamp)
    console_script(venv / "bin" / "openRepoTools", str(venv / "bin" / "python"))
    metadata = {
        "placeholder": ("a fake pipx venv for openRepoTools' suite: "
                        "--install reads only that this file exists"),
        "pipx_release_mirrored": release,
        "package": "openrepotools",
    }
    _place((json.dumps(metadata, indent=4, sort_keys=True) + "\n")
           .encode("utf-8"), venv / "pipx_metadata.json", 0o644)
    version = re.sub(r"^[^0-9]*", "", python)
    _place((f"home = {venv / 'bin'}\n"
            "include-system-site-packages = false\n"
            f"version = {version}\n").encode("utf-8"),
           venv / "pyvenv.cfg", 0o644)
    return venv


def console_script(path: os.PathLike | str, python: str,
                   form: str | None = None) -> Path:
    """Pip's console script for `openrepotools.cli:main` at `path`, at 0755
    as pip leaves it, naming `python` as its interpreter. Returns the path.

    The interpreter is quoted when it holds a space and is not quoted
    already, as distlib's `enquote_executable` does. Then, as distlib's
    `_build_shebang` does:

    - `form="shebang"`: `#!<python>` as the first line;
    - `form="trampoline"`: pip's three-line `/bin/sh` trampoline,
      `#!/bin/sh`, `'''exec' <python> "$0" "$@"` and `' '''`;
    - `form=None`, pip's own choice: the trampoline when the interpreter
      holds a space or the `#!` line would pass `SHEBANG_LIMIT`, and the
      plain shebang otherwise.

    The template follows, with `from openrepotools.cli import main` at
    column 0. A `python` that is not a Python, such as `/bin/bash`, makes the
    same shape around another interpreter, which is a fixture the recognition
    rule must not take for pip's.
    """
    if not isinstance(python, str) or not python or "\n" in python \
            or "\r" in python:
        raise ValueError(f"the interpreter must be one non-empty line, not "
                         f"{python!r}")
    executable = python
    if " " in executable and not executable.startswith('"'):
        executable = f'"{executable}"'
    if form is None:
        simple = (" " not in executable
                  and len(executable.encode("utf-8")) + 3 <= SHEBANG_LIMIT)
        form = "shebang" if simple else "trampoline"
    if form == "shebang":
        shebang = f"#!{executable}\n"
    elif form == "trampoline":
        shebang = f"#!/bin/sh\n'''exec' {executable} \"$0\" \"$@\"\n' '''\n"
    else:
        raise ValueError(f"form must be 'shebang', 'trampoline' or None, "
                         f"not {form!r}")
    module, func = ENTRY_POINT.split(":")
    body = SCRIPT_TEMPLATE % {"module": module,
                              "import_name": func.split(".")[0], "func": func}
    return _place((shebang + body).encode("utf-8"), Path(path), 0o755)


def stamp_text(**fields: str) -> str:
    """The committed stamp's text, with each given field's value in place of
    the committed one. With no fields, it is the committed file, unstamped.

    The fields are the five of `STAMP_FIELDS`, by those names. Each committed
    line, `VERSION = "0.0.0"`, `TAG = ""` and the rest, must be in the file
    exactly once, as the release build's writer requires; it is replaced
    whole, and every other byte is kept, the SPDX line and the docstring
    among them. A value is written as given and never checked, so that a
    test can build any broken stamp the reader must refuse: a partial one,
    a malformed field or a carriage return.
    """
    unknown = sorted(set(fields) - set(STAMP_FIELDS))
    if unknown:
        raise TypeError(f"stamp_text() takes {', '.join(STAMP_FIELDS)}, "
                        f"not {', '.join(unknown)}")
    for name, value in fields.items():
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a str, not {type(value).__name__}")
    lines = STAMP_SOURCE.read_bytes().decode("utf-8").split("\n")
    for name in STAMP_FIELDS:
        committed = f'{name} = "{UNSTAMPED[name]}"'
        where = [i for i, line in enumerate(lines) if line == committed]
        if len(where) != 1:
            raise LayoutError(f"{STAMP_SOURCE} holds `{committed}` "
                              f"{len(where)} times, not once: it is not the "
                              "unstamped stamp this builds on")
        if name in fields:
            lines[where[0]] = f'{name} = "{fields[name]}"'
    return "\n".join(lines)
