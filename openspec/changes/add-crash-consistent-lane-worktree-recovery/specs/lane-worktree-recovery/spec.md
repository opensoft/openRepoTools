## ADDED Requirements

Capability `lane-worktree-recovery`, tracked in [opensoft/openRepoTools#91](https://github.com/opensoft/openRepoTools/issues/91). Where a requirement below is narrower than the brainstorm that proposed it, the reason is a numbered decision in `design.md`.

### Requirement: Canonical lane worktree inventory
The system SHALL maintain a structured inventory for every worktree owned by a lane, rooted or indexed beneath the worktree root derived from the lane's stable repository and estate identity. The inventory SHALL remain discoverable without parsing handoff prose or trusting the caller's current directory.

#### Scenario: Lane owns several worktrees
- **WHEN** one lane coordinates writers in multiple registered worktrees
- **THEN** the lane inventory identifies every tree by stable tree ID, repository, path, branch or detached state, HEAD, upstream, and writer identity

#### Scenario: Shape governs the physical path
- **WHEN** a Speckit or openRepoShape contract prescribes a feature-first worktree path
- **THEN** the lane inventory references that path without moving it into a conflicting lane-first layout

### Requirement: Coordinator base checkout
The system SHALL resolve the lane coordinator's checkout from canonical lane, home repository, estate, and workstation shape. After migration, the coordinator SHALL launch from the canonical base checkout while mutable feature work occurs in inventoried writer worktrees.

#### Scenario: Profile rotation
- **WHEN** an operator resumes a migrated lane under a different valid profile
- **THEN** the system uses the same canonical coordinator checkout and worktree inventory

#### Scenario: Legacy coordinator directory is ambiguous
- **WHEN** a legacy lane has no verified base-checkout record
- **THEN** the system requires an explicit directory or migration act and does not infer one from the current directory or handoff prose

### Requirement: Sidecar metadata remains outside worktrees
The system SHALL store lane and tree lifecycle metadata outside Git worktree directories.

#### Scenario: State update does not dirty work
- **WHEN** the system updates lane or tree state
- **THEN** no tracked or untracked orchestration file is added inside the associated Git worktree

### Requirement: Running ownership is confirmed
The system SHALL write `RUNNING` only from the act that confirms the canonical lane, transcript or session, agent, coordinator directory, and exclusive binding, and SHALL NOT write it from a read-only session-start report. See design decision 9: in this repository the confirming act is the lane start that records the binding, and the SessionStart hook never writes.

#### Scenario: Launcher dies before the binding is recorded
- **WHEN** a resume command begins but no replacement binding is confirmed and recorded
- **THEN** the system does not record the lane as `RUNNING`

#### Scenario: A read-only session-start report runs
- **WHEN** the session-start hook reports on a lane
- **THEN** it writes no lifecycle state, makes no network call, and exits successfully

#### Scenario: Confirmed replacement starts
- **WHEN** the confirming act proves the replacement owns the expected lane and binding
- **THEN** the system atomically records `RUNNING` with that owner and a newly advanced generation

### Requirement: Swap uses a two-phase lifecycle
The system SHALL transition a running lane to `SWAPPING` before `/swap` performs preservation work and SHALL transition it to `SWAPPED` only after every mandatory inventory, writer, handoff, and pause-record step succeeds.

#### Scenario: Token exhaustion before swap
- **WHEN** the running process disappears before invoking `/swap`
- **THEN** persisted state remains `RUNNING` and resume classifies the lane as an ungraceful stop

#### Scenario: Token exhaustion during swap
- **WHEN** the process disappears after `SWAPPING` is recorded but before all mandatory swap steps complete
- **THEN** persisted state remains `SWAPPING` and resume classifies the lane as an interrupted swap

#### Scenario: Graceful swap completes
- **WHEN** every mandatory swap step succeeds
- **THEN** the same operation atomically records `SWAPPED` before printing that the lane is ready to resume

### Requirement: Transitions are generation-fenced
Every ownership transition SHALL carry a monotonically advancing generation and unique operation ID, and a transition finalizer SHALL succeed only when its expected state, generation, and operation ID still match. Every write that follows a recorded act SHALL be serialized under the one transition lock and refused when the lane has moved past the state that write observed.

#### Scenario: A lifecycle write is overtaken while it lands
- **WHEN** the lane's state, generation, or operation changes between the moment a lifecycle-moving event is recorded and the moment its current-state snapshot is updated
- **THEN** the snapshot is left exactly as the later act wrote it, the recorded event still stands, and the overtaken write reports what it found

#### Scenario: An observation is filed under a superseded operation
- **WHEN** an inventory write names a generation or operation the lane has already moved past
- **THEN** the system refuses the write, changes no recorded observation, and directs the caller to re-read the lane

#### Scenario: Delayed swap finalizer
- **WHEN** an old `/swap` process attempts to record `SWAPPED` after another recovery or resume has advanced the generation
- **THEN** the system refuses the stale finalizer without changing current state

#### Scenario: Competing swap begins
- **WHEN** a second `/swap` attempts to start while the matching generation is already `SWAPPING`
- **THEN** the system refuses the competing operation or reports the existing operation without minting another owner

### Requirement: Resume reconciles records with live evidence
Before launching replacement writers, the system SHALL compare lane and tree sidecars with the latest handoff, verified live holders, Git worktree registrations, filesystem paths, branches, commits, dirty files, and unpushed commits.

#### Scenario: Existing writer remains live
- **WHEN** reconciliation finds a verified live writer for an inventoried worktree
- **THEN** the system does not launch a second writer into that worktree

#### Scenario: Running state has no holder
- **WHEN** persisted state is `RUNNING` and no verified owner remains live
- **THEN** the system reports an ungraceful stop and inspects every inventoried and discovered worktree before permitting recovery

#### Scenario: Liveness cannot be established
- **WHEN** the holder records cannot be read at all
- **THEN** the system reports that liveness is not established and pronounces neither crash kind, because a read that failed is not an answer

#### Scenario: Swapping state has no holder
- **WHEN** persisted state is `SWAPPING` and no verified owner remains live
- **THEN** the system reports the interrupted operation ID and preserves all trees for recovery

#### Scenario: Stored Git observations are stale
- **WHEN** current branch, HEAD, dirty state, or unpushed commits differ from the sidecar
- **THEN** the system reports current Git evidence and does not treat the stored observation as truth

#### Scenario: Unknown tree is discovered
- **WHEN** Git or the filesystem contains a worktree beneath the lane root that is absent from the inventory
- **THEN** the system reports it as unmanaged and does not delete, overwrite, or automatically assign it

#### Scenario: A tree cannot be read
- **WHEN** Git answers in a tree's path and one of the reads an observation is made of fails
- **THEN** the system reports the tree as unreadable, records no observation of it, and assumes neither clean nor dirty state for it

### Requirement: Missing worktrees are rebuilt only from durable records
The lane system SHALL delegate worktree reconstruction to the existing estate resume mechanism and SHALL not hand-roll worktree creation, WIP commits, resets, or force operations.

#### Scenario: Parked worktree is missing
- **WHEN** an inventoried worktree is absent and its last observation recorded no dirty or unpushed work
- **THEN** the system reports it as missing and NAMES the estate `resume` path as the only rebuild, without running it (design decision 14)

#### Scenario: A stale worktree registration is discovered
- **WHEN** a repository registers a worktree whose directory is gone
- **THEN** the system reports the stale registration and names the `git worktree prune` that clears it, and prunes nothing itself

#### Scenario: Potentially uncommitted worktree is missing
- **WHEN** a missing worktree's last evidence indicates dirty or unpublished work without a durable parked commit
- **THEN** the system reports possible loss and refuses to claim that the worktree can be reconstructed

### Requirement: Closed and swapped states remain distinguishable
The system SHALL distinguish a lane or tree that completed a temporary swap from one whose work is permanently closed.

#### Scenario: Swapped lane resumes
- **WHEN** a `SWAPPED` lane passes reconciliation and SessionStart confirms its replacement
- **THEN** the lane returns to `RUNNING` without changing the identity of its worktrees

#### Scenario: Closed tree is unexpectedly dirty
- **WHEN** a tree marked `CLOSED` contains dirty files or unpushed commits
- **THEN** the system reports a closure inconsistency and refuses automatic cleanup

### Requirement: Legacy migration is explicit and non-destructive
The system SHALL create structured state for a legacy lane only from an explicitly named start, swap, or migration using verified repository and Git evidence.

#### Scenario: Legacy lane is migrated during swap
- **WHEN** a legacy lane successfully completes `/swap` from a verified coordinator checkout
- **THEN** the system creates its structured lane and tree inventory without rewriting historical handoff or lane events

#### Scenario: Migration encounters an unknown path
- **WHEN** legacy evidence names a path that cannot be verified against the expected repository
- **THEN** the system refuses to adopt the path and leaves existing files unchanged

#### Scenario: A sidecar records a schema this tooling does not write
- **WHEN** a lane snapshot or a tree sidecar records a schema version this tooling does not write
- **THEN** every reader reports it as unknown without interpreting any other field of it, and every writer refuses to replace it rather than overwriting a record it cannot read
