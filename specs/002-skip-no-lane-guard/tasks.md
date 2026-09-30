# Tasks

- [x] T001 Add the guard exemption and document its scope.
- [x] T002 Add regression cases for exact marker handling, unreadable identity and unaffected non-guard commands.
- [ ] T003 Run focused tests, syntax checks and governance validation; record results.

## Verification

- Nine isolated CLI smoke checks passed inside `py-bench`: exact marker opt-out, absent/empty/unsupported markers, malformed or empty hook input, and unaffected non-guard commands.
- Changed shell files pass `bash -n`; diff whitespace checks and strict OpenSpec validation pass.
- Before the infrastructure-probe cases were added, the canonical focused commands passed 9 and 161 tests respectively. Those results do not verify the expanded module.
- The expanded module has 13 cases. The canonical combined run is queued inside `py-bench` behind another workstation pytest process; record its actual result before completing T003.
