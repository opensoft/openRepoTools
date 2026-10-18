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

IT READS NOTHING AND PASSES NOTHING ELSE. Bash finds package mode from its
own path and reads the stamp, `_release.py`, by its own fixed grammar; no
Python reads it, so Python and bash can never disagree about a release. This
module sets no variable and adds no option for bash: the arguments are the
only thing it hands on.

With no `bash` on PATH, it prints contracts/cli-output.md's refusal to stderr
and returns 2, the status bash's own `die` refuses with, and nothing runs.

The standard library only, and of it only `os` and `sys`: the package
declares no dependencies, and `tests/test_repo_hygiene.py` holds every
module's imports to that allowlist (FR-005).
"""

import os
import sys

#: contracts/cli-output.md's one refusal that does not go through `die`, so
#: no blank line comes before it.
NO_BASH = ("REFUSED: openRepoTools needs bash, and there is no bash on this "
           "PATH. Nothing ran.")


def main() -> int:
    """Become `bash <payload>/openRepoTools <arguments>`, or refuse with 2.

    It returns only when there is no `bash` on PATH; otherwise the exec
    replaces this process, and bash's exit status is the command's.
    """
    payload = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "payload")
    try:
        os.execvp("bash", ["bash", os.path.join(payload, "openRepoTools"),
                           *sys.argv[1:]])
    except FileNotFoundError:
        print(NO_BASH, file=sys.stderr)
        return 2
