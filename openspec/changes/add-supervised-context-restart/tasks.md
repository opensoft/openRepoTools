## 0. What this slice landed, and what it did not

The first implementation pass landed the transaction, the supervisor, the exact fresh launch and the retry surface — the path `opensoft/openRepoTools#94` measured breaking — and deliberately did **not** land the prerequisite lifecycle work, the machine-readable staged payload, the crash-point matrix or the protocol amendment. Ticked boxes below are implemented AND covered by cases in `tests/test_lane_helpers.sh`; unticked ones are open, and the three that were rewritten rather than ticked-as-written say so in their own line.

**Found in the review pass, and fixed here rather than left for a later one:**

- **A new operation inherited the last one's per-operation fields.** `set-restart-intent` keeps every field a transition does not name, which is what lets the supervisor write `starting` without blanking the digest. Five of the fields belong to ONE operation, though, and two of those are what the readiness predicate is built on: an inherited `new_transcript` is a uuid the new launch will never mint, so readiness could only run to its deadline; an inherited `old_transcript` is the wrong uuid to be *distinct from*, and being distinct from it is the check that catches `#94` itself. `old_transcript`, `new_transcript`, `attempt`, `reason` and `created` now fall back to nothing when the operation changes, and a caller that names one still wins.
- **`lane-start` nagged on every launch of every lane on a workstation whose `lanes-edit.sh` predates this change.** The estate's read fence is *"`0` an answer, `8` NO ANSWER and `2` a helper predating the read — both of those fall to the next rung"*; the restart-intent read treated `2` as a read that FAILED and printed a note. It is silent now, and only an unclassified code is said.
- **`--restart-status` told a reader that `lanes-edit.sh` has no `lane-state` when the lane merely has no snapshot.** The exits are told apart now (`8` the lane, `2` the helper, anything else a read that failed), which matters the day `#97` lands.

**Deferred, with the reason:**

- **§1 entirely** — it consumes `add-crash-consistent-lane-worktree-recovery`'s lane lock, generation and operation, which are on `feat/crash-consistent-lane-worktree-recovery` and not on `main`. The restart intent is a sibling sidecar under the *same* control root (design decision 14) so nothing here blocks on that merge and nothing re-implements it; §1's fail-closed work belongs in that change's own pass.
- **§3.1–3.3** — the staged semantic payload. `/ctx`'s skill step now calls `lane-handoff --restart` and carries no executable tmux recipe, which is decision 1's *one backend operation* and removes the second implementation of the destructive tail. The machine-readable payload file and its binding checks are a further step and are not in this pass.
- **§6.4–6.5, §8.4, §8.7–8.8** — explicit finalize-or-stop actions, generation-advancing recovery, the crash-point matrix and the manual canary.
- **§7.4** — the amendment that would authorise a supervised respawn and a durable restart intent. Design decisions 10 and 11 record where this implementation diverges from Amendment 18 Addendum 2 (i-8) as ratified; **this proposal is not treated as ratification of that divergence.**

## 1. Prerequisite Lifecycle Contract

- [ ] 1.1 Reconcile this change with the landed `add-crash-consistent-lane-worktree-recovery` state schema and document the exact lane lock, generation, operation, and exit-code interfaces consumed by supervised restart.
- [ ] 1.2 Add red-first tests proving ordinary handoff and `/ctx` refuse when lifecycle state cannot be read, locked, or compare-and-swapped.
- [ ] 1.3 Remove the fail-open path that continues a restart without lifecycle ownership and satisfy the refusal tests while preserving non-restarting late-handoff behavior where explicitly allowed.
- [ ] 1.4 Add red-first tests proving ordinary `/ctx` cannot supersede `SWAPPING`, and implement a separately named recovery/takeover operation that requires absence of a matching live owner.
- [ ] 1.5 Add stale-finalizer and concurrent-operation tests proving generation and operation fencing protect newer lane state.

## 2. Restart Intent Storage

- [x] 2.1 Define the versioned restart-intent schema, field validation, bounded diagnostics, and `pending`, `starting`, `failed`, and `ready` transitions.
- [x] 2.2 Add red-first tests for atomic intent creation, readback, compare-and-swap, attempt increments, malformed or unknown schemas, and missing control roots.
- [x] 2.3 Implement restart-intent create, read, transition, and status operations under the existing per-lane lock using Bash 3.2-compatible code and atomic replacement.
- [x] 2.4 Add tests proving restart intents contain no credentials and reject absolute/relative handoff or directory values that conflict with the canonical lane record.
- [x] 2.5 Add handoff-digest tests proving a changed or missing handoff blocks launch and retry.

## 3. Semantic-to-Mechanical Boundary

- [ ] 3.1 Define and test the operation-scoped staged semantic payload containing coordinator narrative, writer inventory, writer outcomes, and intended handoff top block.
- [ ] 3.2 Refactor the handoff skill so `/ctx` produces the staged payload and invokes one backend operation instead of containing an executable tmux respawn recipe.
- [ ] 3.3 Add backend validation that binds staged payload, current transcript, canonical lane, pane, directory, generation, and operation before canonical writes begin.
- [x] 3.4 Refactor `lane-handoff --restart` to perform the ordered `RUNNING -> SWAPPING`, preservation writes, restart-intent creation, `SWAPPED`, supervisor preflight, and tmux handoff transaction.
- [x] 3.5 Add failure-injection tests at every pre-kill stage proving the current pane process remains alive and no stage reports a completed restart.

## 4. Pane Restart Supervisor

- [x] 4.1 Add a Bash 3.2-compatible pane supervisor that accepts only canonical lane and operation identifiers and resolves all launch facts from restart intent. **Rewritten from `lane-restart-supervisor`:** it is `lane-handoff --supervise --lane <lane> --operation <id>`, a mode of an already-installed command, because Amendment 18 Addendum 2 (i-8) keeps *no word on `PATH` for `/ctx` alone* (design decision 10). It is still a separate process, still what tmux starts, and still resolved by absolute path.
- [x] 4.2 Add red-first tests proving the supervisor refuses stale generations, mismatched panes, non-pending operations, conflicting runtime values, and ambiguous live holders.
- [x] 4.3 Implement the `pending -> starting` claim and launch the installed profile launcher as a foreground child without invoking the human-facing `lane` dispatcher.
- [x] 4.4 Preserve the supervisor as the pane root and add tests proving profile failure, launcher failure, and immediate child exit leave a visible process, `SWAPPED` lifecycle, failed intent, and retry instructions.
- [x] 4.5 Define and test normal signal propagation and post-readiness child exit behavior so intentional Claude exit does not trigger an automatic relaunch loop.
- [x] 4.6 ~~Install the supervisor by absolute path alongside existing lane commands~~ — **nothing to install** (decision 10). The supervisor is a mode of `lane-handoff`, which `openRepoTools --install` already places; the installed-file count is unchanged at twelve. It is *invoked* by absolute path, computed from the command's own location, which is asserted by the respawn case.

## 5. Exact Fresh Launch and Readiness

- [x] 5.1 Add an explicit restart-operation input. **Rewritten by measurement (#94):** the pclaude-to-lane-start *environment* seam cannot carry it at all — `tmux new-session` hands the child the server's environment — so the authority is the restart intent on disk, `lane-start --operation <id>` is the explicit argument on the direct path, and `LANE_RESTART_OPERATION`/`LANE_START_FRESH` are exported by the supervisor as compatibility values that are never relied on.
- [x] 5.2 Refactor supervised `lane-start` preparation so it creates a distinct transcript and exact handoff first prompt. **Scoped (decision 12):** what must not be written before readiness is #91's lifecycle snapshot, never Amendment 8(d)'s `RESUMED` row stamp, object-log line and Rule 3 handoff stamp, which are the append-only record of a launch that was made and which every other reader depends on. `lane-start` writes the prepared transcript id back into the intent, fenced on the operation, so the supervisor has something to confirm against.
- [x] 5.3 Add conflict tests proving lane, profile, agent, directory, pane, transcript, and launch-mode arguments cannot override the restart intent.
- [x] 5.4 Implement a read-only readiness predicate over child liveness, transcript creation, canonical binding, directory, pane, and competing-holder evidence.
- [x] 5.5 Add a supervisor-owned fenced finalizer that marks the intent ready, moves `SWAPPED` to `RUNNING`, and appends resumed evidence only after the readiness predicate succeeds.
- [x] 5.6 Add tests for child exit before readiness, all-evidence success, conflicting holder, and a 60-second indeterminate timeout that preserves a live child without marking the lane running.
- [x] 5.7 Verify the generic SessionStart hook remains read-only, network-free, always non-blocking. **Verified by construction:** nothing in this slice writes from the hook or reads the network in it; readiness is a supervisor-owned predicate over process, register and sidecar evidence (`R-A8-1` untouched). Making the hook *report* the pending supervised state is not in this slice.

## 6. Retry, Inspection, and Recovery

- [x] 6.1 Add an operator status surface that reports lane generation, operation, attempt, lifecycle state, intent state, handoff, child evidence, and bounded failure reason.
- [x] 6.2 Implement idempotent retry from `failed` using the same operation, generation, handoff digest, directory, profile, and fresh launch mode.
- [x] 6.3 Add tests proving retry refuses stale state, changed handoff, mismatched pane, or any possible live child and never launches a competing process.
- [ ] 6.4 Implement explicit inspection and finalize-or-stop actions for an indeterminate but still-live child, each fenced on the original operation.
- [ ] 6.5 Add explicit cancellation and generation-advancing recovery behavior without deleting handoffs, lifecycle history, worktrees, or unpublished Git state.

## 7. Command and Protocol Integration

- [x] 7.1 Update `commands/ctx.md` and the handoff skill to describe the supervised transaction, visible failure behavior, and exact boundary between semantic and mechanical work.
- [x] 7.2 Remove direct `/ctx` respawn through `lane <name>` and retain normal human `lane` attach/select/launch behavior unchanged.
- [x] 7.3 Update lane documentation and command help with restart status, retry, indeterminate, cancel, and explicit recovery instructions.
- [ ] 7.4 Update the lane collision protocol proposal/amendment material required to authorize durable restart intent and supervised readiness, without silently treating this OpenSpec proposal as ratification.
- [ ] 7.5 Amend `add-automatic-context-rollover` artifacts so its success condition is readiness-confirmed `RUNNING` and its implementation depends on this change.

## 8. End-to-End Verification and Delivery

- [x] 8.1 Replace the fake-tmux string-only `/ctx` gate with an isolated end-to-end harness that runs the real supervisor and fake launcher children.
- [ ] 8.2 Prove successful rollover creates a distinct transcript, delivers the digest-matched handoff top block as the first prompt, reaches ready intent and `RUNNING`, and leaves no duplicate holder.
- [ ] 8.3 Prove tmux refusal, unknown profile, launcher nonzero exit, immediate child death, missing transcript, binding mismatch, readiness timeout, stale generation, and duplicate retry each produce their specified recoverable state.
- [ ] 8.4 Add crash-point tests between every `SWAPPING`, preservation, intent, `SWAPPED`, supervisor claim, child launch, and readiness-finalization write and verify deterministic reconciliation.
- [x] 8.5 Run targeted lane helper and installer tests, then run the complete serialized `tests/run.sh` suite and resolve all regressions.
- [x] 8.6 Verify all changed shell scripts parse and behavior tests pass under macOS Bash 3.2 constraints.
- [ ] 8.7 Canary one manual `/ctx` success and one deliberate launcher failure, recording evidence that success resumes from the handoff and failure leaves the supervisor and retry path visible.
- [ ] 8.8 Keep automatic rollover disabled until the manual canary and readiness-confirmed end-to-end gate pass; document rollback to non-restarting `/handoff` rather than unsafe direct self-respawn.
