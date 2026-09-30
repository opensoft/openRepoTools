# Implementation Plan

Governance: `openspec/changes/skip-no-lane-guard/`.

Add an exact-value early exit to the guard dispatch arm using Bash 3.2 syntax. Update the scope documentation. Add subprocess regression coverage against isolated home/config directories and a tmux sentinel. Verify with `tests/run.sh -k guard_launch_mode`, Bash syntax checks and `openspec validate skip-no-lane-guard --strict`.

Dependency: workBenches feature `017-export-no-lane-mode` supplies and clears the process marker. Installed estate commands and vendored pins use their existing release paths.
