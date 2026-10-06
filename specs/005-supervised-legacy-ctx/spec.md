# Supervised legacy context restart

Decision: Brett Heap, 2026-10-04: “Legacy compatibility; refuse managed lanes”.
This feature completes PR #121 on its existing branch. PR #97 remains owned
by openRepoTools-3; neither its branch nor its worktree is an input to this work.

## Scope

Provide a supervised manual `/ctx` restart for confirmed legacy Claude lanes. The
managed JSON ledger remains the sole lifecycle, readiness, operation and
generation authority for enrolled managed lanes. Legacy entrypoints refuse
managed or unknown ownership before preservation writes or launch.

The restart YAML stores only legacy restart bookkeeping. Its generations,
operations and attempts are independent of managed counters and of PR #97's
diagnostic lifecycle snapshots. Readiness never writes another lifecycle store.

## Requirements

- FR-001: Resolve canonical lane aliases before probing managed ownership.
  Use the installed managed ownership reader when available; unknown answers
  refuse. With managed storage but no compatible reader, refuse conservatively.
- FR-002: Reserve a legacy operation atomically before changing the handoff,
  pause log or register. A preparing/pending/starting operation cannot be
  superseded by ordinary `/ctx`. A refused competing restart changes no
  canonical preservation record and never respawns a pane.
  Reservation, completion, cleanup and later reads retain the sole existing
  intent among recorded-checkout and projects-root candidates, unless an
  explicit state-root override is supplied. Distinct competing records or
  unreadable candidate ownership refuse. Root selection and CAS share the
  writer mutex; recording a nested checkout cannot strand the reservation.
- FR-003: Validate complete intent schema, state, generation, operation,
  attempt and launch facts. Existing unreadable/malformed records cannot be
  interpreted as absent or rewritten to a supported schema. Schema 1 rejects
  unknown keys, duplicate keys, malformed lines and control delimiters; exact
  launch identities are preserved byte for byte and stored through private
  same-directory temporary files.
- FR-004: Fence each attempt's claim, transcript preparation, readiness,
  timeout, signal and failure writes by operation, generation and attempt.
  A delayed child of an earlier attempt cannot consume a newer attempt.
- FR-005: Bind the launch's canonical handoff, agent, profile, directory and
  pane to the recorded operation. An ordinary launcher cannot consume an
  active restart without its supervisor token. Before respawn, require an
  existing absolute checkout and verify every pending launch fact and checksum.
  Equivalent handoff symlink spellings refer to the same file. Lane rename
  refuses unfinished and failed restart ownership under the shared mutex.
- FR-006: Preserve the handoff bytes used for the prompt across owned resume
  stamps. Prepare durable evidence before publishing a stamp; an interruption
  at either publication boundary remains diagnosable and retryable. Unrelated
  handoff changes refuse launch/retry.
- FR-007: Observe the UUID prepared by the current attempt after launch, and
  require one live process with the intended transcript and binding. Preserve
  the existing preferred `live-holder` interface; enumerate all holders for
  readiness and refuse ambiguity. Claude-native interactive session record
  provenance supplies agent evidence within this Claude-only contract.
- FR-008: If a signal leaves a child alive or child absence unproven, preserve
  an indeterminate active operation. Do not advertise or permit a competing
  retry. A known-ended child permits retry of the same operation. Observer
  cleanup uses a private cancellation marker and waits for its owned child;
  it never signals a saved PID that may have been recycled.
- FR-009: Failure/status output describes the persisted state. A failed
  fresh launch requires its supervised operation; ordinary resume cannot bypass
  it. A failed preparation (`preservation-only`, attempt 0, no new transcript)
  authorizes no supervised launch. With no explicit/inherited restart tokens or fresh-session selectors
  and every holder confirmed absent, ordinary resume is permitted. Recheck the
  same operation/generation and qualifying fields before binding changes and
  before launch, retaining the failed intent unchanged. `preparing` still refuses.
  A completed intent remains history and permits ordinary resume.
- FR-010: Preserve main's binding, holder, performance and Claude resolver
  behavior. Use Bash 3.2-compatible implementation and the repository test
  wrapper in the dev container. CI remains the suite of record.

## Delivery gates

Focused fault tests and per-push CI must pass. The existing user hold remains
until explicitly released. Apply the macOS landing gate immediately before
an authorized merge. Do not install, deploy, restart a real lane or run a live
manual canary as an incidental test.
