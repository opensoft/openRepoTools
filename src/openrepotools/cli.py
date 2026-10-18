# SPDX-License-Identifier: Apache-2.0
"""The `openRepoTools` console script: bash runs the packaged installer (#228).

pip's console script for `openrepotools.cli:main` calls `main()`, and
`main()` does one thing (design.md Decision 3). It replaces this process with
the first `bash` on PATH, running `payload/openRepoTools` from beside this
file with the person's arguments unchanged:
`os.execvp("bash", ["bash", <payload>/openRepoTools, *sys.argv[1:]])`.

AN EXEC, NOT A CHILD. The pid the person started becomes the payload's bash,
so a signal reaches bash itself, the `EXIT` trap that removes a placement's
temporary runs in that process, and bash's exit status is the command's.
Run as a subprocess, a signal would come back as a negative return code, and
the trap would run in a process the person's terminal does not own.

THE SIGNALS PYTHON IGNORES ARE PUT BACK FIRST (Decision 3 as amended by the
lead on 2026-10-18, FR-003). Python starts with SIGPIPE and SIGXFSZ ignored,
an exec keeps an ignored disposition, and a non-interactive bash cannot reset
a signal that was ignored on entry. Measured: bash's `SigIgn` was `0x4` run
directly and `0x1001004` through the exec, and `yes | head -1` ended in 141
directly but in 1 and a "Broken pipe" line through it. So `main()` sets both
to `SIG_DFL` just before the exec, as `subprocess`'s `restore_signals` does
for a child, and a platform that lacks one has nothing to put back for it.
Where the exec fails, each goes back to what it was, and only then is the
refusal printed, so the refusal runs exactly as it did before this change.

IT READS NOTHING AND PASSES NOTHING ELSE. Bash finds package mode from its
own path and reads the stamp, `_release.py`, by its own fixed grammar; no
Python reads it at run time, so Python and bash can never disagree about a
release. Hatchling reads its `VERSION` at build time, and the stamp's
docstring guard keeps that reading and bash's the same (design.md
Decision 5). This module sets no variable and adds no option for bash: the
arguments are the only thing it hands on.

ONE NAMED LIMIT, THE C LOCALE. Under a C or POSIX locale, Python's locale
coercion (PEP 538) sets `LC_CTYPE=C.UTF-8` before `main()` runs, so bash sees
it. `main()` does not undo it, because it cannot tell coercion from a
person's own `LC_CTYPE`; `PYTHONCOERCECLOCALE=0` avoids it (FR-003).

With no `bash` on PATH, it prints contracts/cli-output.md's refusal to stderr
and returns 2, the status bash's own `die` refuses with, and nothing runs. A
PATH whose last entry is a file is the same case: `execvp` then raises
`NotADirectoryError` where it would raise `FileNotFoundError`, and the
refusal is the same (FR-004).

The standard library only, and of it only `os`, `signal` and `sys`: the
package declares no dependencies, and `tests/test_repo_hygiene.py` holds
every module's imports to that allowlist (FR-005).
"""

import os
import signal
import sys

#: contracts/cli-output.md's one refusal that does not go through `die`, so
#: no blank line comes before it.
NO_BASH = ("REFUSED: openRepoTools needs bash, and there is no bash on this "
           "PATH. Nothing ran.")

#: The signals Python's start-up sets to `SIG_IGN`, by name: each is set back
#: to `SIG_DFL` before the exec, where this platform has it.
IGNORED_BY_PYTHON = ("SIGPIPE", "SIGXFSZ")


def main() -> int:
    """Become `bash <payload>/openRepoTools <arguments>`, or refuse with 2.

    It returns only when there is no `bash` on PATH; otherwise the exec
    replaces this process, and bash's exit status is the command's.
    """
    payload = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "payload")
    argv = ["bash", os.path.join(payload, "openRepoTools"), *sys.argv[1:]]
    found = []
    for name in IGNORED_BY_PYTHON:
        number = getattr(signal, name, None)
        if number is not None:
            found.append((number, signal.signal(number, signal.SIG_DFL)))
    try:
        os.execvp("bash", argv)
    except (FileNotFoundError, NotADirectoryError):
        for number, before in found:
            if before is not None:
                signal.signal(number, before)
        print(NO_BASH, file=sys.stderr)
        return 2
