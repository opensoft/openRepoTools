# PR #121 authority decision — 2026-10-04

Brett Heap selected: “Legacy compatibility; refuse managed lanes”.

The approved scope is supervised manual context restart for confirmed legacy
lanes. The YAML intent is legacy-only restart bookkeeping. It never supplies
managed lifecycle/readiness, managed generation/operation counters, or PR #97
lifecycle transitions. A managed or unknown ownership answer refuses before
canonical preservation writes or launch. PR #97 remains separate work owned
by openRepoTools-3.

This decision supersedes earlier shared-lifecycle/counter proposals in this
change. Those proposals are design history, not the current implementation
contract. The implementation handoff is exactly one Speckit feature:
`specs/005-supervised-legacy-ctx/`. Its spec, plan and tasks own completion and
validation. OpenSpec records governance, scope and this handoff.

This decision authorizes rework of PR #121, not release of the existing merge
hold, deployment, automatic rollover or a destructive real-session canary.
