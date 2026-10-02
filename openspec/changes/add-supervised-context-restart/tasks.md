## 1. Prerequisite Lifecycle Contract

- [ ] 1.1 Reconcile this change with the landed `add-crash-consistent-lane-worktree-recovery` state schema and document the exact lane lock, generation, operation, and exit-code interfaces consumed by supervised restart.
- [ ] 1.2 Add red-first tests proving ordinary handoff and `/ctx` refuse when lifecycle state cannot be read, locked, or compare-and-swapped.
- [ ] 1.3 Remove the fail-open path that continues a restart without lifecycle ownership and satisfy the refusal tests while preserving non-restarting late-handoff behavior where explicitly allowed.
- [ ] 1.4 Add red-first tests proving ordinary `/ctx` cannot supersede `SWAPPING`, and implement a separately named recovery/takeover operation that requires absence of a matching live owner.
- [ ] 1.5 Add stale-finalizer and concurrent-operation tests proving generation and operation fencing protect newer lane state.

## 2. Restart Intent Storage

- [ ] 2.1 Define the versioned restart-intent schema, field validation, bounded diagnostics, and `pending`, `starting`, `failed`, and `ready` transitions.
- [ ] 2.2 Add red-first tests for atomic intent creation, readback, compare-and-swap, attempt increments, malformed or unknown schemas, and missing control roots.
- [ ] 2.3 Implement restart-intent create, read, transition, and status operations under the existing per-lane lock using Bash 3.2-compatible code and atomic replacement.
- [ ] 2.4 Add tests proving restart intents contain no credentials and reject absolute/relative handoff or directory values that conflict with the canonical lane record.
- [ ] 2.5 Add handoff-digest tests proving a changed or missing handoff blocks launch and retry.

## 3. Semantic-to-Mechanical Boundary

- [ ] 3.1 Define and test the operation-scoped staged semantic payload containing coordinator narrative, writer inventory, writer outcomes, and intended handoff top block.
- [ ] 3.2 Refactor the handoff skill so `/ctx` produces the staged payload and invokes one backend operation instead of containing an executable tmux respawn recipe.
- [ ] 3.3 Add backend validation that binds staged payload, current transcript, canonical lane, pane, directory, generation, and operation before canonical writes begin.
- [ ] 3.4 Refactor `lane-handoff --restart` to perform the ordered `RUNNING -> SWAPPING`, preservation writes, restart-intent creation, `SWAPPED`, supervisor preflight, and tmux handoff transaction.
- [ ] 3.5 Add failure-injection tests at every pre-kill stage proving the current pane process remains alive and no stage reports a completed restart.

## 4. Pane Restart Supervisor

- [ ] 4.1 Add a Bash 3.2-compatible `lane-restart-supervisor` command that accepts only canonical lane and operation identifiers and resolves all launch facts from restart intent.
- [ ] 4.2 Add red-first tests proving the supervisor refuses stale generations, mismatched panes, non-pending operations, conflicting runtime values, and ambiguous live holders.
- [ ] 4.3 Implement the `pending -> starting` claim and launch the installed profile launcher as a foreground child without invoking the human-facing `lane` dispatcher.
- [ ] 4.4 Preserve the supervisor as the pane root and add tests proving profile failure, launcher failure, and immediate child exit leave a visible process, `SWAPPED` lifecycle, failed intent, and retry instructions.
- [ ] 4.5 Define and test normal signal propagation and post-readiness child exit behavior so intentional Claude exit does not trigger an automatic relaunch loop.
- [ ] 4.6 Install the supervisor by absolute path alongside existing lane commands and add installer/reinstaller tests for Linux, macOS, and WSL2 path behavior.

## 5. Exact Fresh Launch and Readiness

- [ ] 5.1 Add an explicit restart-operation input through the pclaude-to-lane-start seam, using a compatibility environment value only where the external launcher cannot yet expose an option.
- [ ] 5.2 Refactor supervised `lane-start` preparation so it creates a distinct transcript and exact handoff first prompt without writing `LIVE` or `RUNNING` before `exec`.
- [ ] 5.3 Add conflict tests proving lane, profile, agent, directory, pane, transcript, and launch-mode arguments cannot override the restart intent.
- [ ] 5.4 Implement a read-only readiness predicate over child liveness, transcript creation, canonical binding, directory, pane, and competing-holder evidence.
- [ ] 5.5 Add a supervisor-owned fenced finalizer that marks the intent ready, moves `SWAPPED` to `RUNNING`, and appends resumed evidence only after the readiness predicate succeeds.
- [ ] 5.6 Add tests for child exit before readiness, all-evidence success, conflicting holder, and a 60-second indeterminate timeout that preserves a live child without marking the lane running.
- [ ] 5.7 Verify the generic SessionStart hook remains read-only, network-free, always non-blocking, and able to report the pending supervised state without finalizing it.

## 6. Retry, Inspection, and Recovery

- [ ] 6.1 Add an operator status surface that reports lane generation, operation, attempt, lifecycle state, intent state, handoff, child evidence, and bounded failure reason.
- [ ] 6.2 Implement idempotent retry from `failed` using the same operation, generation, handoff digest, directory, profile, and fresh launch mode.
- [ ] 6.3 Add tests proving retry refuses stale state, changed handoff, mismatched pane, or any possible live child and never launches a competing process.
- [ ] 6.4 Implement explicit inspection and finalize-or-stop actions for an indeterminate but still-live child, each fenced on the original operation.
- [ ] 6.5 Add explicit cancellation and generation-advancing recovery behavior without deleting handoffs, lifecycle history, worktrees, or unpublished Git state.

## 7. Command and Protocol Integration

- [ ] 7.1 Update `commands/ctx.md` and the handoff skill to describe the supervised transaction, visible failure behavior, and exact boundary between semantic and mechanical work.
- [ ] 7.2 Remove direct `/ctx` respawn through `lane <name>` and retain normal human `lane` attach/select/launch behavior unchanged.
- [ ] 7.3 Update lane documentation and command help with restart status, retry, indeterminate, cancel, and explicit recovery instructions.
- [ ] 7.4 Update the lane collision protocol proposal/amendment material required to authorize durable restart intent and supervised readiness, without silently treating this OpenSpec proposal as ratification.
- [ ] 7.5 Amend `add-automatic-context-rollover` artifacts so its success condition is readiness-confirmed `RUNNING` and its implementation depends on this change.

## 8. End-to-End Verification and Delivery

- [ ] 8.1 Replace the fake-tmux string-only `/ctx` gate with an isolated end-to-end harness that runs the real supervisor and fake launcher children.
- [ ] 8.2 Prove successful rollover creates a distinct transcript, delivers the digest-matched handoff top block as the first prompt, reaches ready intent and `RUNNING`, and leaves no duplicate holder.
- [ ] 8.3 Prove tmux refusal, unknown profile, launcher nonzero exit, immediate child death, missing transcript, binding mismatch, readiness timeout, stale generation, and duplicate retry each produce their specified recoverable state.
- [ ] 8.4 Add crash-point tests between every `SWAPPING`, preservation, intent, `SWAPPED`, supervisor claim, child launch, and readiness-finalization write and verify deterministic reconciliation.
- [ ] 8.5 Run targeted lane helper and installer tests, then run the complete serialized `tests/run.sh` suite and resolve all regressions.
- [ ] 8.6 Verify all changed shell scripts parse and behavior tests pass under macOS Bash 3.2 constraints.
- [ ] 8.7 Canary one manual `/ctx` success and one deliberate launcher failure, recording evidence that success resumes from the handoff and failure leaves the supervisor and retry path visible.
- [ ] 8.8 Keep automatic rollover disabled until the manual canary and readiness-confirmed end-to-end gate pass; document rollback to non-restarting `/handoff` rather than unsafe direct self-respawn.
