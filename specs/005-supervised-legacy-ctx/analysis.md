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
record. T013 and T016 remain open until their actual validation
results are recorded; expert follow-up review T014 is complete; T017 remains subject to the user's existing merge hold.

The final nine-role expert panel verified strict schema preservation, private
intent temporary files, file-alias identity, complete pre-respawn launch checks,
rename fencing and cooperative observer cleanup. Focused regression fixtures
cover those findings and the observer fork/PID-publication signal boundary.
Shell parsing, error-level ShellCheck and strict OpenSpec validation pass. The
serialized local restart run is queued behind other workstation pytest jobs;
its outcome and current-head CI remain validation gates, not assumed passes.

Known boundary: managed enrollment and legacy runtime integration are feature
001's responsibility. This change refuses existing or unknown managed ownership
and provides no installation, automatic rollover or real-session canary.
