## Purpose

Specify externally supervised Claude account swaps that preserve supported conversation graphs, dirty work, and exclusive execution with recoverable failure boundaries.

## ADDED Requirements

### Requirement: Managed launches pass through two supervisory authorities

For a lane enrolled in managed Claude operation, the lane-aware profile launcher SHALL ensure the persistent lanes service is ready and submit a launch request rather than directly starting an uncontrolled Claude runtime. The lanes service SHALL own registered-lane observation, operation ordering, and `swap`/`ctx` intent. It SHALL start or reconnect to the lane's execution-group supervisor, which SHALL durably admit and launch Claude, own source-process custody and admitted external jobs, and survive replacement of the Claude process. A failed or uncertain supervisor connection SHALL NOT fall back to direct Claude launch or create a second writer. Unmanaged Claude launches SHALL be identified as outside this contract.

#### Scenario: Managed `lclaude` launch

- **WHEN** `lclaude` resolves a lane and profile enrolled in managed operation
- **THEN** it ensures the lanes service is ready and submits the requested launch to that service
- **AND** the service starts or reconnects to one execution-group supervisor for the lane
- **AND** that supervisor launches Claude with the selected profile and durable ownership before model dispatch

#### Scenario: External command or edit under managed Claude

- **WHEN** a managed Claude session needs to run a shell command, external script, or workspace edit
- **THEN** it uses the execution-group supervisor's admitted job interface with durable job identity and resource reservations
- **AND** direct Bash/PowerShell and native file writes are unavailable in the supported managed launch configuration
- **AND** native read tools and native Claude subagents remain subject to their separate runtime inventory

#### Scenario: Supervisor is uncertain

- **WHEN** the lanes service cannot authenticate or reconcile the existing execution-group supervisor
- **THEN** it retains the lane's claim and refuses a new Claude launch or account transition
- **AND** neither the launcher nor recovery starts an unsupervised replacement

### Requirement: Automatic usage trigger submits a bounded swap request

The lane service SHALL watch registered lane bindings and source profiles. For each live, locally controllable managed Claude lane with automatic swap enabled and an explicitly configured authorized target profile, the system SHALL submit the same lane-service swap operation when a fresh source-profile five-hour usage sample is at least 95% used. It SHALL treat missing, unsupported, expired, or stale usage data as unknown and SHALL NOT infer a threshold crossing from a rounded tmux panel value. The trigger SHALL run outside model-directed `/handoff` or `/swap` instructions and SHALL NOT require another prompt on the source account. It SHALL deduplicate notifications for a lane and usage window and SHALL leave target selection and account validation to preflight.

#### Scenario: Registered lane can be observed on its bound host

- **WHEN** the service finds a registered lane with a current host/container/window binding and a reachable tmux server
- **THEN** it verifies the live binding and intended pane before using pane content for diagnostics
- **AND** it uses the profile's structured usage sample for the threshold decision

#### Scenario: The binding is elsewhere

- **WHEN** a registered lane is bound to another host or an inaccessible container
- **THEN** the local service does not treat its pane or process as observable or dead
- **AND** automatic swap requires a verified monitor/controller in that binding's environment or a verified relay

#### Scenario: Five percent remains and a target is configured

- **WHEN** a fresh source-profile status-line sample reports five-hour usage of at least 95% for a managed lane with automatic swap enabled
- **THEN** the external trigger submits a swap request to the persistent lane service, starting and readiness-checking that service if absent
- **AND** the service coordinates the old-profile quiescence and target-profile resume under the same requirements as a manual swap
- **AND** the trigger does not ask the old Claude model to run a handoff command

#### Scenario: A rate-limit failure arrives first

- **WHEN** Claude emits `StopFailure` with `error: rate_limit` before a qualifying usage sample is observed
- **THEN** the hook may submit the configured swap request to the service without waiting for another model turn
- **AND** repeated status-line or failure events do not start duplicate lane operations

#### Scenario: The trigger lacks trustworthy usage or a target

- **WHEN** the sample is absent, stale, unsupported, or from a different profile, or no authorized target is configured
- **THEN** no automatic account swap begins
- **AND** lane status reports the missing prerequisite without guessing a profile or treating unknown usage as safe

#### Scenario: Weekly limit reaches 95 percent

- **WHEN** only the seven-day usage bucket reaches 95% under the initial five-hour policy
- **THEN** it does not trigger automatic account swap

#### Scenario: Multiple events for the same window

- **WHEN** several status-line updates, prompts, or a later rate-limit failure report the same source-profile usage window for one lane
- **THEN** at most one swap operation owns the lane transition
- **AND** a new five-hour window is eligible only after its reset identity is observed and the lane's current profile is re-evaluated

### Requirement: Preflight validates managed control and target compatibility

The controller SHALL verify a supported managed launch, exact session identities, target profile authentication and account identity, transcript-store compatibility, and compatible launch settings before planned shutdown. It SHALL use the supported profile launcher boundary without copying credentials or issuing a model probe. Unknown quota availability SHALL NOT be represented as guaranteed fresh quota.

#### Scenario: Target cannot access the conversations

- **WHEN** the target profile lacks compatible transcript storage or authorization
- **THEN** preflight refuses and the original session is left running

#### Scenario: Arbitrary CLI session lacks a control adapter

- **WHEN** the controller cannot prove control over the coordinator and its workers
- **THEN** it refuses the managed swap rather than assuming SDK attachment or process signaling is sufficient

#### Scenario: Swap was invoked inside the old Claude session

- **WHEN** `/swap` submits a request while the source account can still process a turn
- **THEN** it connects to the persistent lane service, or starts the service and verifies readiness if absent
- **AND** the service establishes independent lifetime and durable operation ownership before the old session stops
- **AND** the invoking tool call returns before planned shutdown

#### Scenario: Lane service cannot start

- **WHEN** a swap request finds no running lane service and its startup or readiness check fails
- **THEN** the old Claude session remains running and no participant is quiesced
- **AND** the caller receives the service failure

#### Scenario: Two callers request the same lane swap

- **WHEN** concurrent requests reach a running or starting lane service for the same lane
- **THEN** one operation owns the lane transition and the other caller receives that operation's identity or an explicit refusal
- **AND** neither a second lane service nor a second replacement writer is started

### Requirement: Complete participant inventory is sealed against new work

The controller SHALL inventory the coordinator and every relevant descendant, recording native identity, parent relationship, participant kind, completion state, workspace, and outstanding task/tool references. It SHALL fence task admission and account for racing spawns before sealing the roster.

#### Scenario: Worker spawns during quiescence

- **WHEN** a worker creation races with the admission fence
- **THEN** it is rejected or included in the controlled roster before shutdown proceeds
- **AND** it cannot become an untracked writer

### Requirement: Quiescence is acknowledged for every active participant

The controller SHALL interrupt and drain active supported participants and their tools using demonstrated runtime behavior. It SHALL confirm durable native state and absence of continuing old writers before replacement execution. Parent interruption, OS suspension, or process exit alone SHALL NOT count as proof of complete graph preservation.

#### Scenario: Child continues after parent interruption

- **WHEN** the parent is interrupted but a child or owned tool can still write
- **THEN** the lane is not declared quiescent
- **AND** replacement execution remains blocked

#### Scenario: Quiescence deadline expires

- **WHEN** a participant has not reached a verified safe state by the configured deadline
- **THEN** the controller reports that participant and the unresolved state
- **AND** it does not report successful swap or start competing writers

#### Scenario: Old background session remains attached to tmux

- **WHEN** the controller begins a swap from an attached source-profile background session
- **THEN** detaching or moving the tmux client does not count as stopping that session or changing its account
- **AND** target-profile execution stays blocked until the old coordinator, workers, and owned tools are quiescent and cannot continue

### Requirement: Native transcripts and mechanical intent support recovery

The controller SHALL persist a versioned durable operation record containing operation identity, source/target profile references, phase, participant graph, launch identity, persistence evidence, and unresolved effects. It SHALL retain native transcripts as conversation authority and SHALL NOT require a generated narrative or store authentication secrets in operation records or logs. Host-specific runtime paths SHALL remain in ignored host-local state.

#### Scenario: Controller stops after quiescence

- **WHEN** the controller crashes after participants are safely paused but before replacement startup
- **THEN** recovery can identify the same operation and exact conversations from durable records
- **AND** it does not require a model-written handoff to attempt recovery

### Requirement: Restart preserves the quiescent workspace

Swap SHALL NOT commit, push, stash, reset, clean, or reconstruct the user's worktrees. It SHALL preserve the filesystem state reached after in-flight writers become quiescent and SHALL distinguish in-flight tool changes from restart-induced changes.

#### Scenario: Dirty and untracked files are present

- **WHEN** a supported lane is quiescent with uncommitted and untracked work
- **THEN** restart leaves that work in place in the same workspace
- **AND** no clean-tree or pushed-commit prerequisite is imposed

### Requirement: Exact graph restoration does not regenerate context

The controller SHALL restore the exact coordinator and supported unfinished worker conversation identities under the selected account, preserving parent-child routing and accounting for pending messages and tasks. Completed workers SHALL remain completed. Loading and verification SHALL be held from new inference until readiness is committed; an adapter unable to do so SHALL fail the compatibility gate.

#### Scenario: Coordinator and two unfinished workers resume

- **WHEN** all three participants have supported durable native state
- **THEN** they load their original conversation identities and relationships under the target account
- **AND** a previously completed fourth worker is not restarted
- **AND** no model-generated reconstruction or continuation prompt is used during restoration

#### Scenario: Parent resume loses worker routing

- **WHEN** the coordinator loads but a required child identity or pending-message relationship cannot be restored
- **THEN** the controller reports incomplete restoration and keeps work held

#### Scenario: Native resume creates a copy

- **WHEN** Claude starts a new background process under the target profile but reports a copied conversation ID
- **THEN** the controller does not treat it as an exact resume or release the lane
- **AND** it records the attempted process for ownership reconciliation

### Requirement: Readiness verifies account and exclusive ownership

The controller SHALL verify the selected account, exact participant identities, workspace, compatible model and permission settings, and exclusive writer ownership before declaring success. It SHALL release work once per operation, only after the durable ready transition. A process starting successfully SHALL NOT alone establish readiness.

#### Scenario: Launcher selects the previous account

- **WHEN** a replacement process loads the correct session with the wrong account identity
- **THEN** readiness fails and autonomous work remains held

#### Scenario: Old worker remains capable of writing

- **WHEN** old participant ownership cannot be excluded
- **THEN** replacement execution is not released
- **AND** the controller reports an unresolved ownership condition

### Requirement: Uncertain external effects are not replayed

The controller SHALL distinguish cancellation acknowledgment from proof that an external effect did not occur. Unknown outcomes SHALL be recorded and SHALL block replay of the affected action until reconciled.

#### Scenario: External operation completes while its response is lost

- **WHEN** interruption leaves a deployment or other external mutation with an unknown result
- **THEN** resume does not automatically reissue that action
- **AND** the uncertainty is visible for reconciliation

### Requirement: Startup failure and retry are bounded and idempotent

The controller SHALL use configured startup deadlines and retain durable paused or indeterminate state on failure. A retry SHALL reuse the operation identity, reconcile surviving processes and ownership, and neither replay completed work nor duplicate release. Recovery SHALL distinguish preflight refusal, partial quiescence, paused startup failure, and already-ready execution.

#### Scenario: Target startup fails after the old runtime exits

- **WHEN** the selected profile cannot restore a required session before the startup deadline
- **THEN** the lane remains visibly paused or indeterminate with recoverable native state
- **AND** retry does not require a handoff or silently restart the old account

#### Scenario: Crash follows replacement launch

- **WHEN** recovery finds a replacement already launched for the recorded operation
- **THEN** it reconciles that instance before creating another
- **AND** no participant is released twice

### Requirement: Claude compatibility evidence includes unfinished workers

Release acceptance SHALL include external zero-new-model-request stop/load control, cross-profile exact-ID restoration, unfinished ordinary writer workers, racing spawns, active tools, readiness, and crash recovery on each supported runtime/launch configuration. Coordinator-only success SHALL NOT satisfy multi-worker swap acceptance. Unsupported native team restoration SHALL remain explicitly excluded unless separately demonstrated.

#### Scenario: Only parent resume is proven

- **WHEN** feasibility evidence demonstrates coordinator resume but not unfinished-worker preservation
- **THEN** the result is classified as a prototype and the full swap release remains blocked
- **AND** a different worker architecture or reduced scope requires an explicit design decision
