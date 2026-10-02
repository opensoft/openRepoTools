## Context

`/ctx` is a semantic context rollover: the current Claude coordinator captures its reasoning, polls writers, refreshes the lane handoff, records the lane as paused, and starts a new Claude transcript whose first prompt is the handoff's top block. The shipped tail calls `tmux respawn-pane -k` with `lane <name>` or `pclaude` and exits successfully when tmux accepts that command. Tmux acceptance says nothing about whether the child selected an attach-only path, resolved a profile, executed Claude, remained alive, or consumed the intended handoff.

A measured run completed the preservation side and killed the old process but produced no replacement session. The valid handoff made manual recovery possible, but the pane and launch error disappeared. Three related facts make this more than a missing error check:

- the fresh-session requirement currently exists only as `LANE_START_FRESH=1` in the attempted command;
- `lane-start` records the lane `LIVE` before its final `exec`;
- `lane` is a human dispatcher whose valid outcomes include selecting or attaching to an existing session without launching anything.

This change depends on the generation and operation fencing introduced by `add-crash-consistent-lane-worktree-recovery`. It supplies the reliable execution primitive required before `add-automatic-context-rollover` may act at 65% context. Bash 3.2, Linux, macOS, WSL2, existing lane records, the read-only SessionStart hook contract, and non-destructive worktree behavior remain constraints.

## Goals / Non-Goals

**Goals:**

- Preserve the one-command `/ctx` experience on success.
- Refuse before killing the old process when semantic preparation, lifecycle ownership, or any mandatory preservation write fails.
- Persist the exact fresh launch as operation-scoped data before process replacement.
- Keep a process in the pane that can display and retry every post-handoff launch failure.
- Launch through a narrow operation consumer rather than the human-facing `lane` dispatcher.
- Mark a lane `RUNNING` only after positive replacement identity and liveness evidence.
- Make restart retries idempotent and reject stale operations and competing owners.
- Make the end-to-end behavior testable without a real GitHub repository or real Claude account.

**Non-Goals:**

- Replacing Claude's semantic handoff with a shell-generated summary.
- Interrupting an active turn or implementing the 65% threshold controller.
- Adding a continuously running machine-wide daemon.
- Rebuilding or modifying Git worktrees outside the existing estate and recovery contracts.
- Making profile part of stable lane identity.
- Changing the generic SessionStart hook into a blocking or networked writer.

## Decisions

### 1. Split semantic preparation from the mechanical restart transaction

The handoff skill SHALL produce the human narrative, writer replies, and a machine-readable staged payload. It SHALL then call one backend operation. The backend SHALL own identity validation, generation acquisition, lifecycle transitions, canonical handoff replacement, protocol records, restart intent, tmux replacement, and result classification.

The staged payload is not yet the canonical handoff and cannot authorize a restart. This allows the model to finish semantic work before the backend acquires the lane lock while preventing a model-authored shell recipe from becoming a second implementation of the destructive tail.

Alternative considered: retain executable tmux recipes in the skill. That preserves flexibility but caused the current implementation to have overlapping orchestration paths and makes exact failure behavior dependent on how the model follows prose.

### 2. Treat lifecycle ownership as a hard precondition

The backend SHALL compare-and-swap the current lane from `RUNNING` to `SWAPPING` under the prerequisite change's lane lock. Failure to read state, acquire the lock, match the expected generation, or establish the current owner SHALL refuse the restart while the old process remains alive.

An ordinary `/ctx` SHALL NOT supersede an existing `SWAPPING` operation. Takeover requires a separately named recovery action that first proves there is no matching live holder, retains the interrupted operation in history, and advances generation under lock.

Alternative considered: allow the semantic handoff and pause records to continue when lifecycle state cannot be written. That retains a best-effort handoff but permits competing operations to kill each other's coordinators, defeating generation fencing.

### 3. Preserve the existing swap states and add an operation-scoped restart intent

The lane lifecycle remains:

```text
RUNNING -> SWAPPING -> SWAPPED -> RUNNING
```

The launch interval is represented by a restart-intent sidecar beneath the lane control root rather than a new top-level `STARTING` state. The intent has states `pending`, `starting`, `failed`, and `ready`. While it is `pending`, `starting`, or `failed`, the lane remains `SWAPPED`; only positive readiness moves the lane to `RUNNING`.

The intent includes schema version, lane, generation, operation ID, old transcript, agent, profile, canonical directory, handoff path and digest, launch mode `fresh-from-handoff`, pane binding, timestamps, attempt count, and bounded failure diagnostics. It contains no credentials. All writes use atomic replacement under the lane lock. Callers use `lanes-edit.sh` operations rather than parsing or rewriting the YAML themselves.

This makes the fresh-session requirement durable and retryable without expanding the top-level state machine needed by other lane operations.

### 4. Make `SWAPPED` and restart intent one pre-kill commit point

The guarded backend performs these acts in order:

1. validate the current lane/transcript/pane/directory identity;
2. acquire `RUNNING -> SWAPPING`, minting generation and operation ID;
3. verify the staged semantic payload and snapshot the current writer/worktree evidence;
4. refresh the canonical handoff and complete all mandatory protocol and lifecycle writes;
5. atomically create `pending` restart intent for the same generation and operation;
6. finalize the lifecycle to `SWAPPED` only when both preservation and intent are readable and consistent;
7. preflight the absolute supervisor executable and tmux target;
8. ask tmux to replace the pane with the supervisor for that exact operation.

Any failure through step 7 refuses without intentionally killing the old process. A tmux refusal leaves the lane `SWAPPED` with pending intent and the old process still present; the command reports the explicit terminal recovery command. Once tmux accepts step 8, the supervisor—not the old Claude—owns recovery.

Alternative considered: create restart intent after respawn. The originating process may already be dead, recreating the unrecorded launch gap this change exists to remove.

### 5. Use a restart-only pane supervisor owned by openRepoTools

The first implementation adds an openRepoTools command such as `lane-restart-supervisor`. Tmux starts it by absolute installed path with only lane and operation identifiers. The supervisor validates the pending intent and changes it to `starting` with compare-and-swap semantics before launching anything.

The supervisor invokes the installed profile launcher as a child, supplying the recorded lane, profile, directory, and fresh-from-handoff operation. It never invokes `lane`, never runs a picker, and never rediscovers launch choices from current directory, window title, or rotating defaults. `pclaude` may still perform account configuration and execute Claude inside the child process; because the supervisor is the parent, child exit does not close the pane.

The supervisor remains for the child's lifetime. Before readiness, child failure changes the intent to `failed` and leaves a diagnostic prompt in the pane. After readiness, a later normal child exit is reported and the supervisor exits according to the ordinary lane-end contract; it does not automatically relaunch an intentionally exited session.

Alternative considered: modify workBenches so every `pclaude` invocation has a permanent supervisor. That may be valuable later but broadens this fix across repositories. A restart-only wrapper can be delivered and tested entirely by openRepoTools while treating `pclaude` as a child dependency.

### 6. Launch by exact operation, not by human lane dispatch

The supervisor passes a new explicit operation input through the launcher to `lane-start`, for example `LANE_RESTART_OPERATION=<id>` during the compatibility phase and ultimately an explicit launcher option where workBenches can expose one. `lane-start` reads all launch facts from the fenced restart intent and rejects command-line or environment values that conflict.

`LANE_START_FRESH=1` may remain temporarily as an internal compatibility detail, but it is no longer the authority for deciding fresh launch. The intent's `mode: fresh-from-handoff` is authoritative. Normal `lane <name>` behavior remains unchanged for people.

### 7. Confirm readiness without changing the generic SessionStart contract

`lane-start` SHALL stop writing `LIVE`/`RUNNING` before `exec` for supervised operations. It may write launch-prepared identity and the intended new transcript while the lifecycle remains `SWAPPED`.

The supervisor waits up to 60 seconds for a local readiness predicate that combines:

- the launched child remains alive;
- the expected new transcript has been created by the selected profile;
- the canonical lane, agent, directory, pane, and transcript binding match the restart intent;
- no competing live holder exists.

The predicate is implemented as a read-only helper over process, transcript, register, and local sidecar evidence. It does not require the generic SessionStart hook to write or touch the network. Once the predicate succeeds, a separate supervisor-owned, generation-fenced writer atomically moves `SWAPPED` to `RUNNING`, marks the intent `ready`, and appends the normal resumed evidence.

If the child exits first, readiness is `failed`. If the 60-second deadline expires while the child remains alive, the result is `indeterminate`: the supervisor does not kill the child, does not retry automatically, and does not mark `RUNNING`; it displays inspection and explicit finalize-or-stop instructions.

Alternative considered: regard successful `exec` or a short grace period as readiness. Neither proves transcript creation, correct binding, or survival. A write from the generic SessionStart hook was also rejected because its read-only, always-zero contract is load-bearing.

### 8. Retry the same operation and make recovery explicit

When intent is `failed` and no matching child or competing holder is live, the supervisor offers a retry that compare-and-swaps the same intent back to `starting` and increments its attempt count. The retry uses the same handoff digest, generation, operation, directory, and launch mode.

Stale generation, changed handoff digest, mismatched pane, or live-holder ambiguity refuses retry. Replacing or superseding the operation requires the explicit lifecycle recovery command, not an automatic fallback. No path resets, deletes, stashes, or reconstructs a worktree.

### 9. Test the process boundary, not only the generated tmux string

Tests SHALL run the real supervisor against fake launch children and isolated tmux-compatible harnesses. They SHALL assert process survival, state transitions, transcript/binding readiness, exact first-prompt handoff content, retries, and stale-operation refusal. Existing string-construction tests remain useful but are insufficient as the end-to-end gate.

## Risks / Trade-offs

- **[Risk] The supervisor and interactive child contend for the terminal** → Launch the child in the foreground with the supervisor blocked in `wait`; print only before launch and after child exit or timeout handling through a separate observation path.
- **[Risk] Transcript creation is delayed on a slow machine** → Use a 60-second readiness deadline, preserve an alive child on timeout, and classify the result as indeterminate rather than failed or running.
- **[Risk] pclaude does not yet expose an operation option** → Thread an operation environment variable through its existing environment-preservation seam first, then add an explicit option in coordinated workBenches work without making the environment value authoritative by itself.
- **[Risk] Local sidecar and shared lane records disagree** → Fence all finalization on generation and operation, report disagreement, and retain the intent and handoff for recovery.
- **[Risk] Strict refusal leaves an interrupted `SWAPPING` lane requiring attention** → Provide a read-only reconciliation report and separately named takeover action; never let ordinary `/ctx` silently seize it.
- **[Risk] The handoff changes after intent creation** → Store and verify its digest on every launch and retry.
- **[Risk] Automatic rollover mistakes tmux acceptance for completion** → Expose completion only from the readiness-gated `RUNNING` transition and make the automatic controller consume that outcome.

## Migration Plan

1. Land the prerequisite lifecycle operations with fail-closed compare-and-swap behavior; do not merge the current fail-open handoff integration.
2. Add restart-intent read/write/CAS operations and read-only status reporting without changing current `/ctx`.
3. Add the supervisor, exact-operation launch path, and fake-child tests behind an opt-in environment gate.
4. Refactor supervised `lane-start` so pre-exec work cannot write `RUNNING`; add readiness and finalization tests.
5. Switch manual `/ctx` to stage semantic input and invoke the guarded supervised backend. Retain a documented `/handoff` plus manual terminal launch as rollback.
6. Install the supervisor alongside the other openRepoTools commands and verify absolute-path resolution on Linux, macOS, and WSL2.
7. Run a manual canary that proves both successful continuation and visible child-launch failure before enabling the behavior globally.
8. Update `add-automatic-context-rollover` to require supervised readiness completion, then canary automatic rollover separately.

Rollback disables supervised respawn and returns `/ctx` to warning plus non-restarting `/handoff`; it does not restore the unsafe direct self-respawn. Pending intents and lifecycle history remain for diagnosis and can be closed only through explicit recovery.

## Open Questions

- Should successful readiness archive old restart intents immediately or retain a bounded per-lane history outside the append-only event log?
- What explicit operator command names best distinguish retry, finalize an indeterminate-but-valid child, cancel, and generation-advancing recovery?
- When workBenches adds a first-class operation option, should the compatibility environment seam be removed immediately or after one release overlap?
