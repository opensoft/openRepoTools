# Implementation Plan

Governance: `openspec/changes/skip-no-lane-guard/`.

Add an exact-value early exit before script initialization using Bash 3.2 syntax, preserving global option parsing and status-2 argument validation. Update the scope documentation and repository contract. Add subprocess regression coverage against isolated home/config directories and sentinels for tmux, git, hostname, readlink and workspace parsing. Verify with `tests/run.sh -k guard_launch_mode`, Bash syntax checks and `openspec validate skip-no-lane-guard --strict`.

Dependency: workBenches feature `017-export-no-lane-mode` supplies and clears the process marker. Installed estate commands and vendored pins use their existing release paths.
