# SPDX-License-Identifier: Apache-2.0
"""openrepotools: openRepoTools as a package, installed with pipx (#228).

The wheel carries the installer's whole payload byte for byte under
`payload/`, together with the openRepoShape pin, so that
`openRepoTools --install` run from the package reaches no network. Its one
console script, `openRepoTools`, runs `cli.main`, which replaces its own
process with the first `bash` on PATH, running the packaged installer with
the person's arguments unchanged. `_release.py` is the stamp that names the
release; bash reads it, and no Python does.

This file holds this docstring and nothing else, so that loading the
package, as every console script and every build does, runs no code.
"""
