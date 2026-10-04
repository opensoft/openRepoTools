# Implementation plan

Single-repository feature on the existing PR #121 worktree and branch.
OpenSpec governance: `add-supervised-context-restart`.

Merge current main without replacing entire conflicted files. Keep its
Amendments 18/19/16 behavior, linear lookup optimizations and Claude resolver.

Use the existing locked `set-restart-intent` writer for legacy reservation and
attempt CAS. Add a preparing state before canonical preservation writes.
The pending state is the durable pre-kill commit point. A supervisor claims
one attempt, exports its identity through the in-pane launcher, and observes
that attempt's prepared UUID. Managed checks are affirmative reads, never
writers of enrollment or JSON state.

Prepare the expected post-stamp digest durably before publishing a resume
stamp. Both the prior and proven post-stamp digests are valid during that
bounded publication transaction; unrelated bytes remain invalid. Keep the
prompt tied to the validated canonical handoff and capture it before exec.

The supervisor never marks a live or unknown child retryable after a signal.
Readiness enumerates process witnesses rather than counting the preferred
holder projection. No lifecycle snapshot or managed generation is advanced.

Validation covers competing reservations, read/write faults, stale attempts,
late UUID publication, duplicate holders, stamp publication interruption,
agent/profile/path/pane conflicts, completed-intent ordinary resume and
supervisor termination before session registration. Use sandboxed local bare
repositories and fake launchers; no real sessions or GitHub test repositories.

Preparation reservations use `preservation-only`, which is not a launch mode.
Fenced cleanup may mark that preparation failed without authorizing a child from
previous preservation facts. An operator can inspect and reconcile an abandoned
preparing reservation, then request a new `/ctx`.

Each starting attempt consumes `new_transcript: none` exactly once. Later writes
expect the reserved UUID as well as operation, generation and attempt. Stamp
publication resolves a final-component symlink and atomically replaces its target
from a same-directory temporary file. The helper holds the same writer mutex
through ownership and prior-digest checks and replacement. All shipped handoff
publishers use this path; manual edits must follow the staging/publication skill
contract. Existing records with missing, duplicate or invalid fields refuse
transitions rather than being silently repaired.

Ordinary first launches use the resolved checkout as a control-root hint only
after all established root rungs fail. Explicit configuration, recorded
directories and PROJECTS_ROOT retain precedence. Each claimed attempt repeats the
all-holder absence check before starting, including interactive retries.

Require a known current pane before the supervisor claim. Forward the complete
launcher host/OS/container binding through respawn. Control-root reads inspect
existing directory ancestors so an unusable root cannot answer absence. Child
readiness rejects zombie process state and keeps unknown process state unready.

Final review hardening validates the complete pending launch before pane respawn,
uses filesystem identity for equivalent handoff aliases, and refuses control
characters rather than normalizing launch paths. The shared schema parser rejects
unknown and malformed content on reads, existing-record transitions and generated
record publication. Intent writes use private same-directory temporary files.
Rename takes the existing mutex and refuses unfinished/failed restart records.
Observers stop through a private marker and are reaped before marker removal,
without signaling a numeric PID that may already have been recycled.
