# SPDX-License-Identifier: Apache-2.0
"""The release stamp: which release of openRepoTools this package is (#228).

Only the release build writes this file. Its writer replaces each of the
five assignment lines below exactly once, with the version the tag names
(`v1.1.0` gives `1.1.0`), the tag, the tag's 40-hex commit, that commit's
sorted-ls-tree-r-v1 tree digest and the repository the release ran in. It
refuses a file in which it finds any of those lines twice or not at all. As
committed, the file is unstamped: 0.0.0 and four empty values, a package
built from a checkout and not a release, and `openRepoTools --version` says
so.

Bash is the one reader at run time. The packaged `openRepoTools` reads this
file by a fixed grammar (`stamp_read`), and never sources, imports or runs
it; no Python reads it at run time. Hatchling reads `VERSION` from it at
build time, by a pattern that takes the first line beginning, in any case,
with that field's name or with __version__, then an equals sign. So no line
of this docstring may begin that way, or the build and the command would
disagree. Keep the file LF only, with each assignment on one line.
"""
VERSION = "0.0.0"
TAG = ""
COMMIT = ""
DIGEST = ""
REPOSITORY = ""
