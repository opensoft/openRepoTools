## Context

The current `/swap` path invokes semantic handoff work before account rotation. The user wants the coordinator and all unfinished workers stopped quickly, then resumed with the same conversations under another authorized account. Claude is the first delivery target. Documentation and proposal approval precede implementation.

Native resume is conversation restoration, not process-memory checkpointing. Claude documents resumable ordinary subagent histories, but not automatic restoration of in-process teammates. Cancellation and user-stop semantics also differ from ordinary completion. See the [evidence record](../../../ideation/brainstorm/lane-session-operations-evidence-and-delivery.md). These differences are feasibility gates, not details an implementation may silently work around by generating handoffs.

Existing proposals own crash-consistent recovery and supervised context restart; [PR #121](https://github.com/opensoft/openRepoTools/pull/121) is an active implementation of the latter. This change owns operation separation and Claude account-preserving restart, not a competing recovery engine.

## Goals / Non-Goals

**Goals:** externally initiate account swap without a new model request; preserve exact conversation identities and dirty work; cover the complete supported participant graph; maintain exclusive writers; provide bounded stop attempts, observable recovery, and verified account selection. Separate account rotation from context rollover and knowledge transfer.

**Non-goals:** zero usage for work already in flight or subsequently continued; live credential patching; arbitrary process-memory freeze; open-ended profile rotation without a configured target; bypassing account access controls; cross-machine migration; Codex implementation in the first release; guaranteeing every Claude worker kind is resumable.

## Decisions

### 1. Three operations, one coordinated lifecycle

| Operation | Conversation contract | Account contract | Semantic handoff |
| --- | --- | --- | --- |
| `swap` | Resume the existing coordinator and supported unfinished workers by exact identity | Explicitly selected authorized target | Not generated or required |
| `ctx` | Fresh coordinator context; worker policy belongs to the context-restart contract | Keep the account unless separately requested | Semantic checkpoint required |
| `handoff` | Transfer work and understanding; no implicit restart | No implicit change | This is the operation's purpose |

Proposed external command: `lane swap <lane> --profile <profile>`. A terminal binding can invoke the same command. When the old account still has quota, `/swap` submits this request to the lane service; the invocation consumes its own Claude turn and must return before the service stops the old session. If the lane service is not running, the command starts it, verifies that it is ready, and only then submits the request. A slash frontend qualifies as token-free only if its input is intercepted before model dispatch. The external command remains the path when the old account cannot answer another turn.

An opt-in automatic trigger submits the same request when a fresh source-profile sample shows at least 95% used in Claude's five-hour window. The target profile must be selected in advance by explicit local configuration; automatic selection cannot guess from installed profiles. The trigger never changes credentials inside an existing process. Its only authority is to enqueue a request for the lane service, which still runs preflight and all quiescence/restore checks. A `StopFailure` with `error: rate_limit` can enqueue the same request after the quota is exhausted, without requiring the old model to respond.

Claude documents no hook event at a configurable usage percentage. Its status-line input does include `rate_limits.five_hour.used_percentage` and `resets_at` for eligible subscriber accounts after an API response. The installed workBenches status-line script already publishes this as a profile-keyed snapshot and its profile setup configures a ten-second `refreshInterval`; its `UserPromptSubmit` guard reads fresh snapshots and, at 95%, prints a model-directed `/handoff`/`/lane-swap` instruction. That existing guard is prompt-dependent and does not perform an external swap. The service can observe the profile-keyed snapshot directly, or receive an idempotent event from the publisher, without waiting for a user prompt or spending a model turn on the old account. Reading the tmux prompt panel is a useful display/identity check but not the threshold authority: the panel is rounded to an integer, may be truncated or hidden by UI state, has no reliable freshness marker, and renders the same account-wide value in each session. In particular, a displayed `95%` can represent less than 95% in the raw value. Status-line updates may go quiet while the coordinator waits for background work unless its timer is active, and hook/status-line behavior for detached managed sessions needs Gate 0 verification. A stale or absent sample is unknown, not a zero-usage or threshold-crossing reading. See [Claude status-line data](https://code.claude.com/docs/en/statusline) and [hook events](https://code.claude.com/docs/en/hooks).

The first automatic policy is five-hour only, matching workBenches' existing 95% breakpoint; weekly usage remains advisory pending a separate policy decision. Deduplicate by lane, source profile, usage-window reset, and operation ID so repeated status-line refreshes or a later `StopFailure` do not launch another replacement. If the configured target has no compatible authorization or known eligibility, preflight refuses before stopping the source. The service records why no swap occurred and exposes it in lane status. The controller must tolerate a sample that appears during a still-running model turn: it may request admission fencing, but it cannot claim a durable pause until that turn and its workers have reached verified boundaries.

Reuse the agreed per-lane lock, operation identity, lifecycle status, and restart-intent machinery. The shared contract must distinguish `resume-existing` from `fresh-from-checkpoint`; a handoff record is not evidence of a completed swap. Resolve ownership and schema compatibility with the existing recovery/context changes before implementation. Do not add a second independent authority for whether a lane is running.

### 2. Managed launch, execution-group custody, and a persistent lanes service are prerequisites

One lanes service outside the old Claude process owns the operation lock, coordinator/worker inventory, and launcher configuration. It stays running across account swaps and context rollovers and must survive stopping the old session, including when `/swap` caused it to start. Its startup must be independent of the old Claude process group and old tool call. A service already running receives the request directly; simultaneous callers must not create two services or two operations for one lane. Startup failure leaves the old session running and reports the failure before any quiescence. The service reuses the existing lane lifecycle owner rather than creating a parallel one. It must not assume an SDK client can attach to and control an arbitrary already-running CLI process.

The proposed managed hierarchy has two supervisory authorities: the lanes service coordinates registered lanes, usage triggers, per-lane operation locks, `swap`/`ctx` intent, recovery and tmux binding; an execution-group supervisor, started or reconnected to by the lanes service for each managed lane, owns the actual Claude launch, source-process custody, admitted external jobs, output/results and source-exclusion evidence. It outlives Claude A so admitted jobs can continue while Claude B starts. A per-source subreaper wrapper and the job-service thread are implementation components under that execution-group authority, not additional lane transaction owners. If the execution-group supervisor is uncertain or unavailable, the lanes service retains the operation and refuses to start a competing Claude process.

The current installed `lclaude` only delegates to `pclaude --with-lane`; it does not start either managed supervisor. The proposed managed launch path is `lclaude` resolving the lane/profile, ensuring the lanes service is ready, and submitting a launch request. The lanes service then starts or reconnects to that lane's execution-group supervisor; the supervisor durably admits and launches Claude with workBenches' profile isolation. The same route must be used for later restart/recovery so no direct `lclaude` fallback bypasses ownership after enrollment. Bare `claude` and profile-only `pclaude` remain unmanaged unless deliberately enrolled; they cannot be advertised as supporting supervised swap or ctx.

For every Claude session claimed as managed, external shell commands, long-running scripts and workspace edits must go through the execution-group supervisor's admitted job interface, with durable identity and resource reservations. The active Speckit CLI contract enforces this by omitting Bash/PowerShell and Edit/Write from Claude's tool roster and providing a reviewed MCP job endpoint. Native read tools and native Agent/SendMessage activity remain inside Claude's runtime and are inventoried separately. This is a managed-session rule, not a claim that every ordinary Claude process on the machine already uses the supervisor.

The service watches registered lane bindings, not just the lane that last invoked `/swap`. The lane register/log provides lane, profile, transcript, workstation/host, container, and tmux window reference where recorded; the service verifies that the binding is still current and live before acting. A window ID alone is insufficient because tmux can reuse it after a server restart, and a window may have multiple panes; the service resolves and verifies the intended pane in the bound tmux server. It can inspect that pane's rendered Claude status panel when the host/container and tmux socket are reachable. A lane bound on another host or an inaccessible container requires a monitor/controller in that binding's environment or a verified relay; the local service cannot infer liveness or scrape a remote pane from registry metadata alone. Account usage is profile-scoped, so one fresh reading can make every eligible, locally controllable lane on that profile a candidate, each still guarded by its own operation lock and configured target.

The existing `/ctx` implementation has a pane-resident restart supervisor for one operation. Under the proposed hierarchy, the lanes service owns `ctx` preparation-to-restart coordination through the same operation lock as `swap`, while the execution-group supervisor proves source exit and launches the fresh coordinator after the semantic checkpoint is durable. `ctx` still uses a new conversation on the same profile; `swap` resumes the old conversation on a target profile. Preserve the pane supervisor's operation IDs, generation fences, readiness rules and recovery behavior during migration, then retire its independent restart authority only after parity is tested. It must not race the lanes service to relaunch the same lane.

The active Speckit implementation selected a managed foreground CLI in a shared container, with a per-session subreaper wrapper and independently admitted jobs, rather than treating Claude's `--bg` host as the execution-group supervisor. This choice still keeps the shared container and unrelated sessions running during swap. Tmux binds the user-facing pane; detaching it cannot change the source process's account. The execution-group supervisor selects the profile only for a new Claude process and verifies source exclusion before that process begins model work. The feature branch's `specs/001-separate-swap-ctx-handoff/contracts/claude-cli-supervised-jobs.md` defines its experimental runtime boundary; its unfinished gates are not release evidence.

Preflight requires a supported launch mode and runtime version, resolvable exact native IDs, a complete participant inventory, and an accessible target profile in a compatible transcript-storage family. Unmanaged sessions or unsupported worker kinds refuse before planned shutdown. They can use the existing explicit handoff/context workflows, but swap does not invoke those as a fallback. The current `pclaude` entry point passes `--no-lane` on a bare profile launch, so the existing `/swap` skill's printed bare `pclaude <profile>` command does not establish lane restoration; the new controller must bind the lane and target profile explicitly.

### 3. Gate 0 proves Claude's preservation boundary

Before committing to the adapter transport, demonstrate external discovery, interruption, durable persistence, and exact-ID restoration for a coordinator and ordinary unfinished writer workers. Include a worker active in a tool and a spawn racing with quiescence. Prove restoration of parent-child routing and pending work without model-written summaries or restart prompts that trigger model work. Prove that a lanes service started by `/swap` becomes ready, survives the old session's shutdown, and handles a second request without starting a duplicate service; that its execution-group supervisor and admitted jobs survive that shutdown; that old Claude processes stay on the source account until stopped; and that resumed processes use the target account. The earlier `--bg --resume <id>` candidate could copy a conversation under a new ID; whichever transport is selected, a copied coordinator is not an exact-resume success.

Classify worker kinds separately: ordinary resumable subagents, one-shot helpers, in-process teammates, and independently launched sessions. An unfinished kind without demonstrated preservation is unsupported. In-process teams must not be claimed as supported merely because the parent transcript resumes. A coordinator-only demonstration is a prototype, not completion of the user's multi-worker requirement.

If native Claude control cannot satisfy this gate, stop and propose a revised managed-worker architecture or reduced scope for approval. Independently managed worker sessions may be an alternative, but changing the user's collaboration model is not an automatic fallback.

### 4. Controlled interruption and exact resume, not OS freeze

The logical sequence is:

1. Connect to the lane service, or start it and verify readiness if absent. Submit one swap request with an operation ID, then preflight target authentication, capabilities, storage visibility, and immutable launch configuration without disturbing the source-profile background session. If `/swap` submitted the request, return from its tool call before planned shutdown.
2. Acquire the lane operation lock, persist intent, fence task admission, and seal the roster. A racing spawn is either rejected or included before the roster is sealed.
3. Ask every active supported participant to stop promptly at a durable boundary; interrupt and drain runtime events where needed. Parent interruption alone is not proof of child or tool quiescence. Any native updates to the old conversation and worker transcripts must finish before replacement starts.
4. Confirm durable conversation state and reconcile outstanding tools. Persist the paused record, stop the source-profile background processes, and confirm they cannot continue writing or making old-account requests.
5. Start Claude under the selected target profile and direct it to resume the old coordinator and supported worker conversation IDs exactly, using a verified native resume command. Do not launch a second autonomous writer or accept a copied conversation ID. No semantic handoff or new-context prompt is required.
6. Verify account, conversation identities, worker routing, workspace, settings, and exclusive ownership. Commit readiness, attach the tmux pane to the target-profile background session, and release work once.

This is a logical pause, not a claim that operating-system memory or network requests are frozen. `SIGSTOP` alone cannot drain requests or reload credentials. Arbitrary termination risks losing unpersisted events. Signals may be adapter mechanisms only where their supported persistence and tool behavior have been verified.

No machine-generated continuation prompt is allowed to hide model calls in the stop/restore path. If the runtime automatically starts inference while loading a session and cannot hold it, it fails the zero-new-model-request control-path gate.

### 5. A mechanical record replaces swap's narrative requirement

Extend the shared durable intent contract with the minimum machine facts needed for deterministic recovery:

- Schema version, operation ID, lane identity, operation mode, phase, and timestamps.
- Source and target profile references plus non-secret expected account identity.
- Coordinator native session ID and participant roster: native IDs, parent relationships, worker kind, prior completion state, and pending task/tool references.
- Repository/worktree identity and portable relative location, launch-settings fingerprint, transcript store identity, and persistence acknowledgments supported by the runtime.
- Admission-fence state, ownership epoch, readiness evidence, and unresolved side effects.

Do not copy tokens, cookies, credentials, conversation bodies, or generated prose into this record. Native transcripts remain authoritative for conversation content. Host-local process handles and absolute resolved paths belong only in ignored local runtime state, not committed artifacts. Storage durability and phase transitions reuse the agreed lifecycle owner, including atomic writes and crash recovery.

Conceptual phases are `preflight`, `quiescing`, `paused`, `starting`, and `ready`, with failure or indeterminate outcomes. Map them to the existing lifecycle schema during integration rather than creating incompatible parallel status vocabularies.

### 6. Account and readiness checks are mechanical

workBenches retains profile/authentication/storage-family ownership. openRepoTools selects a profile through its supported launcher boundary, never copies authentication files or edits live credentials. Preflight validates target identity and known eligibility without a paid model probe; quota knowledge may be stale, so the controller must not promise unlimited or definitely fresh quota.

Preserve repository/worktree, model selection, permission posture, tools, and relevant launch configuration. An incompatible target account or model is a refusal, not permission escalation or a silent model downgrade. Shared transcript visibility does not by itself prove cross-account resume succeeds; Gate 0 must test that boundary with authorized profiles.

Readiness means the correct account has loaded the intended coordinator and every supported unfinished worker, completed workers remain completed, relationships and pending messages are accounted for, and old processes/tools cannot write concurrently. A process launch or successful parent resume alone is insufficient. Do not read credentials into logs while checking identity.

### 7. Failures remain explicit and recoverable

Configure bounded quiescence and startup deadlines. Measure latency by phase and participant kind before setting release performance thresholds; do not invent a shutdown-time guarantee now. Unsupported preflight leaves the original session running. A quiescence failure keeps the supervisor in control and reports which participants or effects remain uncertain; it does not start replacements beside them.

After the old runtime stops, startup failure leaves the lane paused with its native transcripts and durable operation ID intact. Retry resumes the same operation, reconciles any already-started replacements, and does not replay completed work or release twice. A controller crash at any transition must be recoverable from recorded intent plus runtime observation; stale process IDs are not proof of ownership.

An interrupted external command may already have changed remote state. Record uncertainty, prevent automatic replay, and require reconciliation before affected work continues. A local pause does not undo a deployment, push, or other remote side effect.

Swap does not commit, push, stash, reset, clean, or reconstruct worktrees. Already-running tools may change files until they are quiescent; once quiescent, restart itself preserves that filesystem state.

## Risks / Trade-offs

- **Claude may not expose a sufficient external control surface.** Background sessions can be attached from a terminal, but that alone does not prove external worker quiescence, exact cross-profile resume, or native team recovery. Gate 0 is a delivery blocker.
- **Strict all-worker preservation narrows initial compatibility.** Explicit refusal is preferable to calling a parent-only restart a completed swap. Supported configurations must still include meaningful multi-worker work.
- **Very fast stop conflicts with safe side-effect handling.** Bound the attempt and report uncertainty; never claim instantaneous cancellation of remote work.
- **Shared stores do not imply account-independent authorization.** Verify profile compatibility and actual resume identity; do not migrate credentials.
- **Parallel lifecycle changes can diverge.** Agree one owner and schema with recovery and PR #121 before coding. Its pane supervisor is per restart, so adding a persistent lane service requires an explicit integration decision; tests must cover mixed operation attempts and legacy records.

## Migration Plan

1. Review this proposal, the Claude-first compatibility gate, and the explicit protocol amendment replacing Amendment 17's alias interpretation.
2. Agree shared lifecycle integration and launcher ownership with the existing changes. Preserve their scopes and existing records.
3. Hand off to exactly one Speckit implementation feature. Its first acceptance gate is the Claude control/persistence proof, not a production claim. This checkout has no `.specify/` bootstrap; resolve that prerequisite through the normal bootstrap workflow when implementation is authorized.
4. Introduce the external swap command and versioned capability reporting. Keep `lane-handoff` a handoff surface. Migrate `/swap` and any `/lane-swap` alias deliberately; an old prompt-based alias must explain its legacy behavior or refuse, never silently advertise zero-token swap.
5. Publish supported Claude modes and tested versions only after interruption, account-switch, graph-restore, crash, and side-effect scenarios pass. Preserve compatibility with historical handoff/restart records without reinterpreting them as native swap intents.

## Open Questions

- Which Claude transport satisfies Gate 0 for ordinary unfinished subagents, including cancellation and pending messages? This is a blocking feasibility question with explicit pass/fail evidence, not permission to ship an approximation.
- How will the persistent lane service consume the recovery and supervised-context operation records while their existing pane supervisor remains responsible for `/ctx`? Settle the single lifecycle authority before executable planning; no second restart engine is authorized here.
- What measured quiescence/startup budgets should become supported defaults? Choose from the feasibility measurements and tool-risk classes.
