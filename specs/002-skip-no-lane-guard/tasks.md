# Tasks

- [x] T001 Add the guard exemption and document its scope.
- [x] T002 Add regression cases for exact marker handling, unreadable identity and unaffected non-guard commands.
- [x] T003 Run focused tests, syntax checks and governance validation; record results.

## Verification

- Nine isolated CLI smoke checks passed inside `py-bench`: exact marker opt-out, absent/empty/unsupported markers, malformed or empty hook input, and unaffected non-guard commands.
- Changed shell files pass `bash -n`; diff whitespace checks and strict OpenSpec validation pass.
- `tests/run.sh -k guard_launch_mode`: 9 passed; `tests/run.sh -k 'guard_launch_mode or repo_hygiene'`: 161 passed, inside `py-bench` using the canonical serialized wrapper.
