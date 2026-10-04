# Supervised legacy context restart

The approved 2026-10-04 authority decision supersedes the earlier shared-lifecycle
requirements. OpenSpec owns this decision; `specs/005-supervised-legacy-ctx/`
owns implementation and validation tasks.

## ADDED Requirements

### Requirement: Managed ownership refuses legacy restart
The manual supervised `/ctx` compatibility path SHALL establish canonical lane
identity and affirmative absence of managed ownership before preservation writes,
every child claim and every prepared launch. It SHALL refuse unreadable ownership
and SHALL NOT mutate feature 001's JSON ledger or PR #97's lifecycle snapshot.

#### Scenario: Managed lane invokes ctx
- **WHEN** managed ownership exists or cannot be verified
- **THEN** the legacy path refuses before canonical preservation or respawn

### Requirement: Reservation precedes preservation
The backend SHALL atomically reserve `preparing` before changing the handoff,
register, log or window. It SHALL complete the same reservation as `pending`
only after preservation succeeds, and SHALL refuse another active operation.
Catchable failure SHALL fence cleanup to that exact reservation. An abandoned
reservation SHALL have an explicit inspection and reconciliation path.

#### Scenario: Two context restarts overlap
- **WHEN** a second ctx finds an active reservation
- **THEN** it refuses without altering the first operation's preservation files

### Requirement: Each attempt owns one child transcript
Claims, child writes, failure and readiness SHALL compare operation, legacy
generation and attempt. The first child SHALL reserve an unclaimed transcript
exactly once; repeated consumers and stale attempts SHALL refuse before mutation
or exec. Launch facts SHALL bind agent, profile, directory, pane and row handoff.

#### Scenario: An old child races a retry
- **WHEN** its attempt token is no longer current
- **THEN** its reservation and launch refuse

### Requirement: Owned stamp publication remains recoverable
The exact prior and verified stamped handoff checksums SHALL be recorded before
atomically publishing the stamp to the resolved target, preserving symlinks.
Retries SHALL accept either complete owned version and reject unrelated edits.
The replacement's first prompt SHALL be that same validated handoff's top block.

#### Scenario: Stamp publication is interrupted
- **WHEN** interruption occurs on either side of atomic replacement
- **THEN** the complete old or complete stamped version remains acceptable

### Requirement: Readiness is positive and asynchronous
An observer SHALL reread the current attempt's prepared transcript and confirm
child liveness, the canonical lane, exactly one live holder, a distinct fresh
transcript and matching pane. Only the legacy intent becomes `ready`.

#### Scenario: Transcript is prepared after observation starts
- **WHEN** lane-start records the intended UUID
- **THEN** the observer reads that current UUID and validates its live evidence

### Requirement: Recovery cannot duplicate a live child
Cancellation before claim SHALL preserve the unclaimed intent. A live or unknown
child or unknown holder absence SHALL retain `starting` with an indeterminate
reason, blocking retry. Only a proven ended launch with no live holder SHALL
become `failed`. Retry SHALL preserve operation and increment attempt. Ordinary
lane resume SHALL refuse a failed supervised restart; historical ready intents
SHALL NOT override ordinary resume. No automatic rollover or real session canary
is authorized by this change.

#### Scenario: Supervisor ends while its child lives
- **WHEN** TERM or HUP reaches the claimed supervisor
- **THEN** the child is left alive and retry remains blocked
