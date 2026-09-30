# Tasks

- [x] T001 Add the guard exemption and document its scope.
- [x] T002 Add regression cases for exact marker handling, unreadable identity and unaffected non-guard commands.
- [x] T003 Run focused tests, syntax checks and governance validation; record results.

## Verification

- The canonical focused CI command `bash tests/run.sh -k 'guard_launch_mode or repo_hygiene'` passed 165 checks, with 528 deselected, on implementation commit `64f4e93`. This includes all 13 expanded launch-mode cases and proves marked prompts do not invoke identity probes.
- The launcher/guard end-to-end smoke check passed: a profile-only launch exports the marker and permits its prompt, while an unmarked guard still refuses unreadable identity with status 2.
- Changed shell files pass `bash -n`; diff whitespace checks and strict OpenSpec validation pass.
- Windows checks and macOS Bash 3.2 syntax parsing passed. The focused CI runner honors the same wrapper and serialization rules as local runs.
