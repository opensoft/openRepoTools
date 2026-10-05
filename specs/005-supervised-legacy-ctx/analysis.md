# Consistency analysis

The approved legacy authority decision maps to FR-001 and T005. OpenSpec records
governance; this directory owns implementation tasks. Earlier shared-lifecycle
assumptions are explicitly superseded rather than retained as execution tasks.

The implementation has one restart backend. The `/ctx` command and handoff skill
delegate to it before canonical preservation writes. The managed ownership reader
is read-only; legacy operation counters never import PR #97 lifecycle counters.

Preparation (T006), attempt ownership (T007), launch facts (T008), stamp recovery
(T009), asynchronous readiness (T010) and interruption handling (T011) each have
entrypoint fault cases in `tests/test_supervised_restart_regressions.py`. The
existing shell suite retains integration coverage and CI is the full suite of
record. T013 and T016 passed on the pre-reconciliation head; T018 records the
fresh integration checks. Expert follow-up review T014 is complete; T017 remains
subject to the user's existing merge hold.

The final nine-role expert panel verified strict schema preservation, private
intent temporary files, file-alias identity, complete pre-respawn launch checks,
rename fencing and cooperative observer cleanup. Focused regression fixtures
cover those findings and the observer fork/PID-publication signal boundary.
Shell parsing, error-level ShellCheck and strict OpenSpec validation pass. The
pre-reconciliation serialized restart run and per-push CI passed. Fresh
reconciliation validation remains a separate gate, not an assumed pass.

Known boundary: managed enrollment and legacy runtime integration are feature
001's responsibility. This change refuses existing or unknown managed ownership
and provides no installation, automatic rollover or real-session canary.

## Reconciliation with landed PR #97

Main b1015f4 supplies the diagnostic lifecycle, worktree inventory and published
managed projection. Restart helpers use their own namespace so the diagnostic
functions cannot replace strict restart parsing or private publication. Restart
readiness and counters remain owned only by restart-intent.yaml. The restart
entrypoints and private writers refuse the published or locally contradictory
managed projection. Rename retains completed history under the old name while
moving only diagnostic files to the new name; unfinished recovery still refuses.

The previous head 69838c5 passed 111 focused cases, 3,537 shell assertions and
all per-push CI jobs (985 full-suite cases). T018 records fresh integration
validation; the existing hold and T017 remain in effect. Deferred issues #158
and #159 retain their scope. The nine-role integration review identified the
helper collision and completed-history rename boundary, which are addressed
with focused regression coverage in this reconciliation.

Reconciliation checks passed 26 focused cases (980 deselected), shell parsing,
error-level ShellCheck, Python compilation and strict OpenSpec validation for
both changes. The five incoming generic helper bodies match main exactly,
and no duplicate shell function names remain. The integration panel has no
remaining verified blockers; case-only rename is already refused before any
mutation and has explicit regression coverage. The broader serialized local
suite and fresh-head CI results are recorded in the PR review record when they
complete, rather than treated as passed before the reconciliation is pushed.
