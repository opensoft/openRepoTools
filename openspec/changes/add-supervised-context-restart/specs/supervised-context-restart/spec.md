## ADDED Requirements

### Requirement: Semantic preparation precedes mechanical restart
The system SHALL obtain a current semantic handoff payload from the lane coordinator before beginning a normal `/ctx` restart, and SHALL execute lifecycle, record, tmux, launch, and retry mechanics through one deterministic backend.

#### Scenario: Current coordinator prepares a context restart
- **WHEN** the user invokes `/ctx` in a live lane coordinator
- **THEN** the coordinator captures current reasoning and writer outcomes in a staged handoff payload before invoking the mechanical backend
- **AND** the coordinator does not directly execute a tmux respawn recipe

#### Scenario: Semantic preparation cannot complete
- **WHEN** required semantic handoff or writer-accounting information cannot be produced
- **THEN** the system refuses the restart without killing the current pane process

### Requirement: Transition ownership is fail-closed
The mechanical backend MUST acquire the current lane generation and exclusive transition operation before changing canonical handoff or process state, and any failed or ambiguous acquisition MUST leave the current process alive.

#### Scenario: Current running owner acquires transition
- **WHEN** the requesting transcript and pane exclusively own a lane in `RUNNING`
- **THEN** the backend atomically moves that generation to `SWAPPING` and records a unique operation ID

#### Scenario: Generation changes during acquisition
- **WHEN** the lane generation changes between validation and compare-and-swap
- **THEN** the backend refuses without writing pause completion or replacing the pane

#### Scenario: Lane is already swapping
- **WHEN** ordinary `/ctx` finds the lane in `SWAPPING`
- **THEN** it refuses and directs the operator to reconciliation
- **AND** it does not automatically supersede the existing operation

### Requirement: Context restart intent is durable and operation-scoped
Before replacing the old process, the system SHALL atomically persist a restart intent containing the exact lane, generation, operation, old transcript, agent, profile, directory, pane binding, handoff path and digest, and `fresh-from-handoff` launch mode. The intent SHALL be the authority for the launch mode, and no environment variable SHALL be relied on to carry it (`opensoft/openRepoTools#94`: the installed profile launcher re-creates its child through `tmux new-session`, which hands that child the tmux server's environment and not the caller's, so an environment-only seam is lost at a boundary this system does not own). The intent SHALL live beneath the lane control root defined by `opensoft/openRepoTools#91`.

#### Scenario: Preservation transaction completes
- **WHEN** all mandatory handoff, protocol, row, worktree-snapshot, and lifecycle writes succeed
- **THEN** the system records a `pending` restart intent for the same generation and operation before attempting pane replacement
- **AND** it reads that intent back and confirms it names this operation before asking tmux for anything

#### Scenario: A restart is already in flight for this lane
- **WHEN** an ordinary `/ctx` finds a restart intent in `pending` or `starting`
- **THEN** it refuses before replacing the pane and leaves the existing operation untouched

#### Scenario: Intent cannot be persisted
- **WHEN** the restart intent cannot be atomically written or read back consistently
- **THEN** the system leaves the lane in an incomplete pre-restart state and does not intentionally kill the current process

#### Scenario: Handoff changes after intent creation
- **WHEN** the current handoff digest differs from the digest in a pending or failed intent
- **THEN** launch and retry refuse as stale rather than consuming changed instructions

### Requirement: Swapped state remains non-running until readiness
The lane SHALL remain `SWAPPED` while restart intent is `pending`, `starting`, or `failed`, and SHALL transition to `RUNNING` only through generation- and operation-fenced readiness finalization.

#### Scenario: Tmux accepts supervisor command
- **WHEN** tmux accepts replacement of the old pane process with the supervisor
- **THEN** the system records only that process replacement was accepted
- **AND** it does not mark the lane `RUNNING`

#### Scenario: Launcher is about to execute Claude
- **WHEN** launch preparation and pre-exec validation succeed
- **THEN** the lifecycle remains `SWAPPED` and the intent remains `starting` until readiness evidence succeeds

### Requirement: Pane supervisor survives replacement launch failures
Tmux SHALL replace the old coordinator with a pane-resident supervisor that launches the profile launcher as its child and remains present until the child becomes ready or its failure is reported. No path this supervisor opens SHALL exit the pane silently, including its own refusals before any launch (lane-collision-protocol Amendment 11: *No path the launcher opened exits the pane*). The supervisor SHALL never terminate the child (Amendment 8(f): ending somebody's process is not a boundary script's act).

#### Scenario: Profile launcher exits nonzero
- **WHEN** profile resolution or the launcher exits nonzero before readiness
- **THEN** the supervisor remains in the pane, marks the intent `failed`, and displays the exact failed stage and retry command

#### Scenario: Claude exits immediately
- **WHEN** the launcher succeeds but the Claude child exits before readiness
- **THEN** the supervisor remains visible and the lane remains non-running with a retryable failed intent

#### Scenario: Replacement becomes interactive
- **WHEN** the child is running normally
- **THEN** it owns the pane terminal in the foreground while the supervisor remains its waiting parent

### Requirement: Internal restart bypasses human lane dispatch
The supervisor MUST launch the exact pending operation without invoking the human-facing `lane` command or performing picker, attach, select, current-directory, title, or default-profile resolution. The supervisor MUST NOT be a separate installed command reachable on a user's `PATH` (lane-collision-protocol Amendment 18 Addendum 2 (i-8): *no word is kept on `PATH` for it alone*), and MUST be started by absolute path so that the respawned pane's `PATH` cannot decide what runs.

#### Scenario: Existing holder evidence is stale during restart
- **WHEN** stale records could cause `lane <name>` to choose an attach-only path
- **THEN** the supervisor ignores that dispatcher path and invokes the narrow operation launch using recorded intent

#### Scenario: Runtime arguments conflict with intent
- **WHEN** command-line or environment directory, profile, agent, pane, or lane values conflict with the restart intent
- **THEN** the operation launch refuses without substituting the conflicting value

### Requirement: Replacement readiness is positively verified
The system SHALL confirm child liveness, new transcript creation, canonical lane, agent, directory, pane and transcript binding, and absence of a competing live holder before finalizing `RUNNING`.

#### Scenario: All readiness evidence agrees
- **WHEN** the expected child is alive and every identity and binding check matches the restart intent
- **THEN** the system atomically marks the intent `ready`, transitions the same operation to `RUNNING`, and appends resumed evidence

#### Scenario: Child exits during readiness wait
- **WHEN** the child exits before all readiness evidence agrees
- **THEN** readiness fails, the lifecycle remains `SWAPPED`, and no successful resumed state is recorded

#### Scenario: Readiness deadline expires with a live child
- **WHEN** 60 seconds elapse while the child remains alive but readiness evidence is incomplete
- **THEN** the supervisor reports an indeterminate launch, leaves the child and lane state untouched, and offers explicit inspection and finalize-or-stop actions

#### Scenario: Generic SessionStart hook executes
- **WHEN** the replacement triggers the generic SessionStart hook
- **THEN** that hook remains read-only, network-free, and non-blocking
- **AND** supervisor-owned finalization supplies the state write

### Requirement: Fresh handoff is the replacement's first prompt
The operation launch SHALL create a new transcript and supply the exact current handoff top block as its initial user prompt. This is the requirement `opensoft/openRepoTools#94` measured being violated, and it SHALL hold with no fresh-session environment variable present at all.

#### Scenario: Pending context restart launches
- **WHEN** the supervisor consumes a valid `fresh-from-handoff` intent
- **THEN** it creates a transcript distinct from the old transcript and passes the digest-matched handoff top block as the first prompt

#### Scenario: Old transcript remains resumable
- **WHEN** a context restart intent names an old transcript that still exists
- **THEN** the operation launch does not use the normal transcript-resume path

#### Scenario: Every resume source is available and the environment carries nothing
- **WHEN** a pending `fresh-from-handoff` intent exists, the register row's last session id has a transcript in this directory, the lane's last `PAUSED` record names a second transcript that also exists, and no fresh-session environment variable is set
- **THEN** the launch is a new session named for the lane, primed by the handoff's top block
- **AND** it passes no transcript-resume argument for either existing transcript

#### Scenario: A confirmed restart authorises no further fresh launch
- **WHEN** a restart intent has reached `ready`
- **THEN** a later ordinary launch of that lane resolves its own resume source and does not treat the intent as authorising a fresh session

### Requirement: Failed restart is idempotently retryable
A failed restart SHALL be retryable under the same generation, operation, handoff digest, and launch facts when no matching child or competing holder is live.

#### Scenario: Operator retries a failed launch
- **WHEN** the intent is `failed`, its generation and handoff still match, and no live holder exists
- **THEN** the supervisor atomically increments the attempt count, returns the same intent to `starting`, and retries the exact launch

#### Scenario: Stale operation attempts retry
- **WHEN** a retry names an operation or generation that is no longer current
- **THEN** the system refuses without launching a child or modifying newer state

#### Scenario: Possible live child makes retry ambiguous
- **WHEN** process or binding evidence cannot exclude a live child from the previous attempt
- **THEN** retry refuses and directs the operator to reconciliation

### Requirement: Interrupted operations require explicit recovery
The system MUST separate ordinary context restart from generation-advancing recovery of abandoned `SWAPPING` or inconsistent restart operations.

#### Scenario: Recovery finds no live owner
- **WHEN** an explicit recovery action verifies that the recorded owner and launch child are absent
- **THEN** it may advance generation while retaining the interrupted operation in history

#### Scenario: Recovery finds a matching live owner
- **WHEN** reconciliation finds a live process matching the current operation
- **THEN** takeover refuses and reports that owner without killing it

### Requirement: Restart outcomes are observable and testable
The system SHALL expose operation state and diagnostics sufficient to distinguish preservation failure, tmux refusal, launcher failure, immediate child exit, indeterminate readiness, and confirmed running state.

#### Scenario: Operator inspects a failed restart
- **WHEN** the operator requests restart status after a failure
- **THEN** the output names the lane, generation, operation, attempt, lifecycle state, intent state, handoff, and bounded failure reason

#### Scenario: End-to-end success test runs
- **WHEN** the isolated test harness executes a supervised context restart with a fake child that emits valid transcript and binding evidence
- **THEN** it observes `RUNNING`, a ready intent, a distinct transcript, and the exact handoff top block as first prompt

#### Scenario: End-to-end failure test runs
- **WHEN** the isolated test harness executes a child that exits or never produces readiness evidence
- **THEN** it proves the supervisor remains, the lane is not `RUNNING`, and the same operation has a visible recovery path

### Requirement: Automatic rollover waits for supervised completion
Any automatic context controller SHALL treat a rollover as successful only after the supervised restart reaches readiness-confirmed `RUNNING`.

#### Scenario: Automatic request reaches swapped state only
- **WHEN** an automatic rollover completes its handoff but the replacement is pending, failed, or indeterminate
- **THEN** the controller reports the rollover incomplete and does not clear its operation latch as successful

#### Scenario: Automatic replacement is confirmed
- **WHEN** the supervisor finalizes the intended replacement as `RUNNING`
- **THEN** the automatic controller may mark its request completed
