## ADDED Requirements

### Requirement: Session-scoped context signal
The system SHALL determine rollover eligibility from a fresh numeric context-window percentage associated with the current Claude transcript. It MUST NOT substitute profile-level rate-limit usage, terminal scraping, or an estimate from conversation text.

#### Scenario: Fresh context snapshot is available
- **WHEN** the current transcript's fresh snapshot reports context usage at or above the configured threshold
- **THEN** the system treats the context threshold condition as satisfied

#### Scenario: Snapshot is unusable
- **WHEN** the context snapshot is absent, stale, malformed, or associated with another transcript
- **THEN** the system performs no automatic rollover and leaves the current session running

### Requirement: Opt-in user-owned policy
The system SHALL keep automatic context rollover disabled until the operator enables it in user-owned configuration. An enabled policy without an explicit threshold SHALL use 65%, and the system SHALL support an explicit threshold override and a one-launch disable. Repository-controlled files MUST NOT enable automatic pane replacement.

#### Scenario: Enabled with no threshold override
- **WHEN** the operator enables automatic rollover without specifying a percentage
- **THEN** the effective context threshold is 65%

#### Scenario: Repository requests automatic action
- **WHEN** only repository-controlled content requests automatic rollover
- **THEN** the system does not enable automatic pane replacement

#### Scenario: One-launch disable is present
- **WHEN** persistent policy enables rollover and the current launch explicitly disables it
- **THEN** the current session performs no automatic rollover

### Requirement: Completed-turn trigger
The system SHALL evaluate and request automatic rollover only at a completed main-session turn boundary. It MUST NOT interrupt model generation, an active tool call, file editing, subagent execution, or user input by means of a continuously acting timer or terminal keystroke injection.

#### Scenario: Threshold is crossed during active work
- **WHEN** context usage crosses the threshold while Claude is generating or running a tool
- **THEN** the system waits until the main session reaches a completed-turn boundary before evaluating rollover

#### Scenario: Subagent finishes
- **WHEN** a subagent stop event occurs above the threshold
- **THEN** the system does not request rollover of the lane coordinator

### Requirement: Verified lane admission
The system SHALL request automatic rollover only for a main Claude coordinator whose canonical lane, transcript, tmux pane, live ownership, lane generation, and `RUNNING` state agree. Ambiguity or an existing swap, resume, or rollover operation MUST leave the session untouched.

#### Scenario: Coordinator owns a running lane
- **WHEN** the threshold is reached and all coordinator, lane, pane, generation, and ownership evidence agrees
- **THEN** the system admits one automatic rollover request

#### Scenario: Lane identity is ambiguous
- **WHEN** the threshold is reached but lane identity or ownership evidence conflicts or cannot be read
- **THEN** the system refuses automatic rollover, reports the discrepancy, and keeps the current session alive

### Requirement: One-shot fenced request
The system SHALL persist an atomic rollover request before asking Claude to continue with handoff work. The request SHALL be keyed by canonical lane, lane generation, transcript, threshold, and operation ID, and one session generation MUST NOT issue the same threshold request more than once.

#### Scenario: Stop hook is entered repeatedly
- **WHEN** the completed-turn hook runs again for a session generation that already has a rollover request
- **THEN** the system does not create another request or inject another rollover instruction

#### Scenario: Lane generation changed
- **WHEN** a pending request names an older lane generation
- **THEN** the system does not allow that request to begin or finalize a transition in the newer generation

### Requirement: Semantic handoff parity with manual ctx
An admitted automatic rollover SHALL invoke the same semantic handoff-and-restart capability as manual `/ctx`. It SHALL capture current reasoning, account for active writers, refresh the handoff, perform the guarded lane transition, and use the resulting handoff as the fresh session's first prompt before considering the rollover complete.

#### Scenario: Automatic rollover succeeds
- **WHEN** Claude completes the semantic handoff and all guarded transition writes succeed
- **THEN** the pane is respawned into a fresh session through the lane launcher and that session receives the handoff top block as its first prompt

#### Scenario: External controller can only call the shell tail
- **WHEN** an external controller has not obtained a semantic handoff for the current operation
- **THEN** it MUST NOT treat a direct `lane-handoff --restart` invocation as a complete automatic `/ctx`

### Requirement: Fail-safe preservation
The system SHALL keep the current pane and session alive when any mandatory signal, policy, handoff, ownership, lock, or transition step fails. It SHALL record or display a precise failure and MUST NOT retry automatically in a loop.

#### Scenario: Handoff write fails
- **WHEN** the semantic handoff or any mandatory lane-state write fails
- **THEN** no pane respawn occurs, the automatic request is marked failed, and the operator is directed to recover or run manual `/ctx`

#### Scenario: Hook continuation is unsupported
- **WHEN** the installed Claude runtime cannot safely continue the stopped turn with a rollover instruction
- **THEN** the system emits a warning and leaves manual `/ctx` as the required action

### Requirement: Prerequisite crash-consistent lifecycle
The system MUST NOT enable automatic pane replacement until the crash-consistent lane transition controller provides exclusive ownership, generation fencing, and durable `RUNNING -> SWAPPING -> SWAPPED` transitions.

#### Scenario: Prerequisite is unavailable
- **WHEN** automatic policy is enabled but the guarded lane transition capability is absent or incompatible
- **THEN** the system reports that automatic rollover is unavailable and leaves manual warning behavior active
