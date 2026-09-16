## Context

`/ctx` is a semantic context rollover: the current Claude coordinator captures its reasoning, polls writers, refreshes the lane handoff, records the lane as paused, and starts a new Claude transcript whose first prompt is the handoff's top block. The shipped tail calls `tmux respawn-pane -k` with `lane <name>` or `pclaude` and exits successfully when tmux accepts that command. Tmux acceptance says nothing about whether the child selected an attach-only path, resolved a profile, executed Claude, remained alive, or consumed the intended handoff.

A measured run completed the preservation side and killed the old process but produced no replacement session. The valid handoff made manual recovery possible, but the pane and launch error disappeared. Three related facts make this more than a missing error check:

- the fresh-session requirement currently exists only as `LANE_START_FRESH=1` in the attempted command;
- `lane-start` records the lane `LIVE` before its final `exec`;
- `lane` is a human dispatcher whose valid outcomes include selecting or attaching to an existing session without launching anything.

**Measured before implementation (`opensoft/openRepoTools#94`, Eagle 2026-09-15T20:59Z).** The first of those three is not merely weak, it is *broken across the launcher boundary*. `claude-profile` re-creates its child through tmux, and its own `act1_compose_child_command` says why that matters: *"`tmux new-session` hands the command the SERVER's environment, not this client's, so a variable the operator exported in their own shell reaches the child only if it is written into the command string"*. It threads six values in explicitly; `LANE_START_FRESH` is not among them, so the respawn's fresh-session requirement was dropped at a boundary this repository does not own, and the pane came up resuming the transcript the `/ctx` had just paused. `lane-start`'s own `(( ! fresh ))` gates were correct and were simply never reached with `fresh` set. This is why decision 3's intent file is the *authority* and not a convenience, and why decision 6's environment seam is documented as a compatibility detail from the start rather than as a mechanism.

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

### 10. The supervisor is a MODE of `lane-handoff`, not a new word on `PATH`

Decision 5 proposes "an openRepoTools command such as `lane-restart-supervisor`", installed by absolute path (tasks 4.1 and 4.6). **That contradicts Amendment 18 Addendum 2 (i-8) as ratified**, which removed `restart` from the installed set on exactly this ground: *"no word is kept on `PATH` for it alone — 'if we need it for ctx, keep it for that' is met by `lane`, which does the same thing under the one name"*, over Brett Heap's own ruling *"i do not see any reason to expose this to the user"*. A thirteenth installed word whose only caller is `/ctx` is the thing that clause refuses.

The supervisor is therefore `lane-handoff --supervise --lane <lane> --operation <id>` — a mode of the command that already owns the `/ctx` transaction and is already installed. Everything the decision actually requires is kept: it is still a separate process from the launch it supervises, it is still what tmux starts, and it is still resolved **by absolute path** into the respawn line, because a respawned pane's `PATH` is whatever the person's shell profile makes of it. What is dropped is the new installed word, the twelve-file installer count it would have moved, and task 4.6's installer work, which becomes nothing to install. A person still has exactly one word, `lane`.

`--restart-status <lane>` is the read-only surface of task 6.1 on the same command, for the same reason.

### 11. (i-8)'s two doors are kept one level down, and `lane <name>` is not one of them for `/ctx`

Clause (i-8) names two doors for the respawn: *"relaunches the lane's own pane with `lane <name>` … or through the launcher directly"*. This change respawns into the supervisor and the supervisor takes **the second door** — `pclaude --lane <lane> <profile>`, the launcher directly — falling to `lane-start` itself where the workstation has no launcher or the lane's record names no profile.

The first door is not used for `/ctx` any more, and the reason is measured rather than argued. `lane <name>` is the human dispatcher: its valid outcomes include attaching to a live session and refusing, and the spec's requirement *Internal restart bypasses human lane dispatch* is incompatible with it. It was also the door through which #94 happened, because the fresh-session requirement it was asked to carry was an environment variable it could not protect.

**This is a deviation from in-force protocol text and it is not treated as ratified by this proposal.** Task 7.4 owes an amendment (an addendum to Amendment 18 Addendum 2, or to Amendment 17(f)) that authorises a supervised respawn and a durable restart intent. Until that is ratified the implementation is what it is and the divergence is named here, in the pull request, and in `lane-handoff`'s own comment at the respawn.

### 12. `RUNNING` before `exec` is scoped to #91's lifecycle, never to Amendment 8(d)'s `RESUMED`

Decision 7 says `lane-start` "SHALL stop writing `LIVE`/`RUNNING` before `exec` for supervised operations". Read widely that would repeal **Amendment 8(d)**, which makes `lane-start` the writer of the row stamp, the object log's `RESUMED`/`STARTED` line and the handoff's Rule 3 stamp, *before* the launch and deliberately — *"on a restart the session makes no register write at all"*. Those three are the append-only record of an act that did happen (a launch was prepared and made), every other lane reads them, and removing them would break `swapped`, the launcher's own resolution and Rule 3's stamp in one move.

So the decision is scoped: what must not be written before readiness is **#91's lifecycle snapshot** — the `RUNNING` word in `lane-state.yaml`, which is the thing that means *this lane has a confirmed holder*. On a workstation where #91 has landed, `lane_state_follow` moves the snapshot to `RUNNING` on any `STARTED`/`RESUMED` line, and reconciling that with this change is work #91's own branch must take when the two merge; this change's supervisor writes `SWAPPED → RUNNING` itself, fenced, only after readiness, and its finalizer's `--expect SWAPPED` is what refuses a snapshot something else already moved.

**Honest residual, stated rather than hidden:** on `main` today there is no lifecycle snapshot at all, so between `lane-start`'s pre-`exec` `RESUMED` and the supervisor's readiness confirmation the register row reads as running while the restart intent still reads `starting`. The spec's *Swapped state remains non-running until readiness* is therefore met **in the restart intent, which this change owns**, and only met in the lane's lifecycle once #91 lands. Nothing in this change marks a lane ready on anything but positive evidence, which is the property the requirement exists for.

### 13. The lifecycle is fail-closed on the KILL and fail-open on the RECORD

Decision 2 and task 1.3 ask for fail-closed lifecycle ownership: refuse when state cannot be read, locked or compare-and-swapped. #91's landed integration is explicitly the opposite — *"THE LIFECYCLE NEVER REFUSES THE SWAP"* — and it supersedes an interrupted `SWAPPING` rather than refusing it, citing that a swap is never left unwritten (Amendment 8(a) step 4; the rule is `R-A11-5`, which this repository's own comments mis-cite as `R-A11-11`).

Both are right about different acts, and the reconciliation is the line Amendment 17(f) already draws:

- **The record is never refused.** The handoff, the `PAUSED` line and the row's state cell are written on every path, with any gap named in the handoff. #91's fail-open lifecycle stands.
- **The kill is always refused** when the record is incomplete: *"a `/ctx` whose record could not be written REFUSES before it kills anything (a pane is never respawned over an unrecorded lane)"*. This change adds the restart intent to that record — a pane respawned with no intent has a supervisor with nothing to launch from, which is the same unrecorded restart one step along — so the intent is the fourth gate beside the `PAUSED` line, the row and the handoff, and it is checked, written, and **read back**, before tmux is asked for anything.

A second `/ctx` over an operation that is still `pending` or `starting` is refused by the intent's own compare-and-swap (`--expect 'none|ready|failed'`), which is the spec's *ordinary `/ctx` does not supersede an existing operation* expressed as one argument, and it refuses **before** the kill rather than after it.

### 14. The restart intent lands without waiting for #91, under #91's control root

Task 1.1 assumes the prerequisite has landed. It has not: `add-crash-consistent-lane-worktree-recovery` is in flight on its own branch with its own writer. Blocking a measured, reproducible defect on another change's merge is the worse trade, so the restart intent is implemented now as a **sibling sidecar** — `restart-intent.yaml` beside `lane-state.yaml` — under a `lane_control_root` written byte-identical to #91's three rungs (`$LANES_LANE_STATE_ROOT`, the lane checkout's parent `.lane-state/<lane>`, `$PROJECTS_ROOT/.lane-state/<lane>`), with the same flat `key: value` grammar, the same atomic replace, the same `lane_op_id` shape and the same exit-code contract (0/1/2/**7 fence lost**/8/64).

The merge of the two branches is therefore a textual conflict whose resolution is *keep either copy of the four shared helpers*, and no second scheme is created. The generation the intent carries is read from #91's `lane-state` where the workstation has it and is `0` where it does not, which is what a workstation before that change can honestly say.

### 15. Readiness is proved from evidence `main` actually has

Decision 7's predicate names "the expected new transcript has been created by the selected profile". On `main` the readable, positive form of that is the workstation's own live-session records, read through `lanes-edit.sh live-holder <lane>`, which is the same read every other collision check in this estate makes. The predicate is therefore: the child is alive; exactly one live holder answers for the lane (a second is Amendment 18(h)'s collision, and a restart that confirmed itself with two processes answering would be the tooling making the very thing the protocol refuses); that holder's transcript is the one `lane-start` recorded it was about to make, or at minimum is **not** the transcript the `/ctx` paused; and it is in the pane the intent names.

Decision 7 also has the supervisor "display inspection and finalize-or-stop instructions" on an indeterminate. It **writes** them instead, into the intent's bounded `reason`, because the child is an interactive terminal program that owns the pane's screen and a line printed over a running Claude is a line nobody reads. `lane-handoff --restart-status --lane <lane>` from any other window is where it is read, and the supervisor prints the same thing in the pane the moment the child exits.

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
