# Approved direction: opt-in stop-then-resume v1

## Authority and scope

On 2026-09-22 Brett requested implementation of the recommendation to ship an
opt-in **stop, switch, then resume** mode. This revises his earlier decision to
retain the complete loaded-and-held contract and leave activation blocked.
It authorizes implementation, not an authenticated canary with unspecified
accounts, production activation, or a claim that the selected runtime passes.

This decision remains within `separate-swap-ctx-handoff` and its sole Speckit
feature `001-separate-swap-ctx-handoff`. Astra remains architecture lead,
Sol High orchestration/verification lead, and Luna Max implementation writer.
Executable tasks belong only to the existing Speckit `tasks.md`.

## Two distinct contracts

The existing strict native-swap contract and its six-stage evidence remain
unchanged for existing records. Missing mode markers MUST NOT reinterpret old
records as the new mode. No recovery path migrates an existing operation,
discards historical evidence, or silently falls back between contracts.

The new, explicitly selected `stop-then-resume-v1` contract defers **all target
runtime creation and exact session loading until explicit release**. Its
pre-release outcome is `ready-to-resume`, never `ready-held`, `restored`, or
`exact-resumed`. A prepared exact-resume specification is not a loaded session.
Existing requirements for target held loading, target no-wake receipts, and
pre-release worker-state clearing remain requirements of strict mode only.
They are not substituted with fabricated success values in v1.

All other safety requirements continue to apply, especially source exclusion,
writer ownership, transcript and file preservation, and uncertain-effect
reconciliation. Neither `ctx` nor `handoff` acquires new semantics here.
Strict graceful child/tool drain-before-parent-shutdown ordering does not
apply to v1: mechanical containment may stop unfinished work first, but complete
source exclusion and effect reconciliation must precede readiness. Termination
is never recorded as successful task completion.

## Required sequence

1. Resolve the explicitly named authorized target profile read-only. Bind the
   exact parent UUID, source invocation, complete native child ledger, immutable
   definitions, transcript access, settings, workspace, owner and generation.
   Unsupported source containment refuses before planned source shutdown.
2. Fence new admissions and dispatch. Mechanically stop the source without a
   generated handoff, source model prompt, or waiting for exhausted writers to
   finish their tasks. Prove exclusion of the entire owned source runtime,
   including any supervisor capable of restarting it, and reconcile tracked
   shell/tool/external effects. Parent PID death alone is insufficient.
3. Preserve the exact parent/child histories and dirty/untracked files in
   place, retain claims and immutable source evidence, and persist an exact
   target resume intent. Do not rewrite internal Claude transcripts/orphan
   state. Unknown descendants, histories, ownership or effects refuse or
   remain indeterminate. Only then report `ready-to-resume`, with no target
   process created and no target inference possible.
4. A matching explicit release durably authorizes target startup and inference
   before any target process is created. Release is an at-most-once boundary
   bound to this operation, generation, target profile and exact parent UUID.
   Startup may wake native children **after** that authorization; v1 does not
   promise a loaded-but-held target. Do not pre-send additional child restart
   instructions while automatic restoration is unresolved.
5. Resume only the exact parent using the supported loader. Validate actual
   account/session/runtime evidence and reconcile child events. Missing or
   wrong parent identity never falls back to a fresh conversation. An uncertain
   startup/release outcome retains claims and intent and is not retried as a
   second startup. Recovery observes; it does not automatically release.

Pre-release control initiates no model work. A supported source boundary must
still demonstrate its request behavior; moving target startup does not prove
that interrupting a busy source cannot trigger another request. Requests
already in flight and post-release target work must be reported separately.

Completed work remains completed. Child history available does not mean child
execution restored: `resume-pending`, `restart-pending`, `exact-resumed`,
`restarted`, and `unresolved` retain their evidence-based meanings. Unknown
external effects block replay. No child is promoted into an unrelated
top-level foreground session. Claims protect a stopped lane until safe release
or explicit, evidence-backed unenrollment.

## Evidence and activation

First run the smallest disposable no-auth, network-isolated scripted-runtime
experiment against the pinned SDK-selected CLI. It must include an unfinished
native child, saved local work, an outstanding tracked shell, complete source
containment, no target before release, and exact parent loading after release.
Quota exhaustion is simulated; the experiment is not actual-account proof.
Record unsupported facts rather than inferring them from process exit.

Fake tests establish ordering, schema, refusal, and crash/retry behavior only.
The new mode remains unavailable for production until its source and target
capabilities are measured, regression/platform/integration gates pass, and a
separately scoped authenticated canary succeeds. No automatic profile rotation,
credential migration, broad process termination, or unspecified remote effects
are authorized. Strict mode's upstream runtime requirements remain useful and
blocked independently; they are not a prerequisite to proving v1's different
target boundary.
