## Purpose

Define separate account-swap, context-rollover, and work-handoff contracts so callers can select the intended operation without hidden model work or lifecycle changes.

## ADDED Requirements

### Requirement: Swap preserves conversations while selecting an account

The system SHALL define `swap` as using an explicitly requested or previously configured authorized target account profile and resuming the existing coordinator and all supported unfinished worker conversations by their native identities. Swap SHALL NOT require or generate a semantic handoff, fresh conversation, commit, or push.

#### Scenario: Account-only transition

- **WHEN** a supported lane swaps to a compatible target profile
- **THEN** the coordinator and unfinished workers retain their native conversation identities under the target account
- **AND** the controller does not generate a handoff or perform repository housekeeping

#### Scenario: Automatic trigger selects the target

- **WHEN** the five-hour usage trigger requests a swap for a managed lane
- **THEN** the controller uses only that lane's previously configured authorized target profile
- **AND** it refuses if no target was configured

### Requirement: Context rollover and handoff remain distinct

The system SHALL define `ctx` as a fresh coordinator context from a semantic checkpoint, with worker treatment governed by its context-restart contract. The system SHALL define `handoff` as transferring work and understanding without an implicit account change or restart. Neither operation SHALL implicitly perform swap.

#### Scenario: Fresh context is requested

- **WHEN** the user requests only `ctx`
- **THEN** a semantic checkpoint and fresh coordinator context are used
- **AND** the account is unchanged

#### Scenario: Knowledge transfer is requested

- **WHEN** the user requests only `handoff`
- **THEN** the system produces or updates transfer information
- **AND** it does not automatically change accounts or restart the session

#### Scenario: Managed context rollover

- **WHEN** a managed lane requests `ctx` after its semantic checkpoint is durable
- **THEN** the persistent lanes service owns the same per-lane operation lock used by swap
- **AND** its execution-group supervisor verifies the old runtime boundary and launches the fresh coordinator on the unchanged profile
- **AND** the pane-resident restart supervisor cannot independently launch a competing coordinator

### Requirement: External swap control does not dispatch model work

The system SHALL provide a swap control surface outside the model conversation. Preflight, interruption, persistence, restart, and readiness verification SHALL NOT initiate model requests or ask agents to write summaries. A slash frontend SHALL qualify for this guarantee only when intercepted before model dispatch. Usage from already-running work and deliberately released continuation SHALL be distinguished from controller work.

#### Scenario: Current inference quota is exhausted

- **WHEN** the user invokes external swap while the current account cannot make another model request
- **THEN** the controller can attempt the supported stop-and-resume sequence without requesting model assistance

#### Scenario: Slash input would reach the model

- **WHEN** the installed frontend cannot intercept `/swap` before model dispatch
- **THEN** it is not advertised as the token-free swap path
- **AND** documentation identifies the external command

#### Scenario: Old account can still invoke the slash command

- **WHEN** `/swap` reaches Claude as a prompt while the source account still has quota
- **THEN** Claude may submit the request to the same persistent lane service used by the terminal command, starting that service if absent
- **AND** the controller performs the stop, target-profile launch, and native resume outside the old Claude process
- **AND** the slash invocation's model usage is reported separately from controller work

### Requirement: Claude-first capability boundaries are explicit

The initial implementation SHALL target Claude and publish tested runtime versions, launch modes, and participant kinds. It SHALL refuse unsupported preservation configurations before planned termination and SHALL NOT silently substitute handoff, fresh context, or a coordinator-only restart. Codex support SHALL remain a separate future delivery.

#### Scenario: Unsupported live teammate

- **WHEN** a lane contains an unfinished participant whose complete native restoration has not been demonstrated
- **THEN** swap refuses before planned shutdown and identifies that participant kind
- **AND** no handoff or fresh-context fallback is started automatically

### Requirement: Lifecycle and alias migration are coordinated

All three operations SHALL coordinate through one per-lane operation authority and shared compatible lifecycle records. The changed alias semantics SHALL require an explicit protocol migration. Historical records SHALL remain readable and SHALL NOT be relabeled as successful native swaps.

#### Scenario: Swap races with context restart

- **WHEN** a context restart already owns the lane transition
- **THEN** a swap cannot independently shut down or relaunch the same participants
- **AND** the controller reports the active operation

#### Scenario: Legacy handoff record is read

- **WHEN** the controller encounters a historical handoff or context-restart record
- **THEN** it interprets it using its original contract
- **AND** does not infer exact-session swap readiness from that record
