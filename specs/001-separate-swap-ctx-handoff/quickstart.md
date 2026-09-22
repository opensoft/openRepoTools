# Native-Lineage Experimental Quickstart

This is the existing **strict-mode** fake-runtime flow. The approved
[stop-then-resume-v1 experiment](contracts/stop-then-resume.md) instead creates
no target until explicit release. It is not yet a public `lane-swap` option;
its bounded observations belong in [live-validation.md](live-validation.md).

Status: **experimental and unverified**. This page describes the fake-runtime
acceptance flow; it is not live Claude evidence, account authorization, or a
claim that native child restoration works for an untested runtime.

1. Initialize the pinned command-test fixture and run the repository's
   canonical serialized suite:

   ```sh
   git submodule update --init upstream/openRepoShape
   tests/run.sh
   ```

   Do not interpret a missing submodule or an omitted/failed managed fixture as
   acceptance. Do not report a live capability from these fake results. The
   wrapper is the supported test entry point; this quickstart does not add
   command flags or invoke authentication, a profile switch, a model, quota,
   or a network service.

2. The fake fixture represents one explicitly enrolled coordinator execution
   lineage, with:

   - one exact coordinator session UUID, account/profile identity, permission
     and launch fingerprint, workspace identity, and owned process facts;
   - native Agent/Task child entries discovered from actual runtime events,
     including at least one unfinished child and one completed child;
   - a runtime-tracked background child only when its native lifecycle/tool
     events are present, plus a detached-effect case that remains unresolved;
   - a read-only coordinator with a writable child to prove the claim belongs
     to the lineage; and an optional isolated child worktree with its own
     globally checked claim.

3. Observe the lifecycle in order. `start` and `fence` hold coordinator and
   child admission. Before release, no child status is inferred from parent
   startup, `Agent` tool return, a reused agent ID, a stale marker, or an
   absent event. The fake Gate0 must record the exact SDK-selected CLI path,
   version, full digest, stream-json mode, and no-auth orphan result. Exercise
   the selected CLI's `running_background_tasks` -> `restoredOrphans` ->
   default-enabled wake -> `enqueuePendingNotification` path; stream-json or
   `print` alone is not proof. Terminal-stop current children, prove durable
   worker-state clear, and require target no-orphan/no-wake/no-model evidence.
   An interactive path that may auto-resume an orphan without a supported hold
   is refused.

4. A successful fake `swap` restores the exact coordinator under the selected
   profile and leaves it `ready-held`. Completed children remain completed.
   Unfinished children are `resume-pending` while held when exact continuation
   is eligible, or `restart-pending`/`unresolved` when it is not. Swap sends no
   model request and writes no checkpoint, generated summary, or handoff;
   `exact-resumed` is reported only after release and correlated continuation
   events.

5. Invoke `release` explicitly. It releases the coordinator once. If a child
   is `restart-pending`, at most one mechanically composed ID/status restart
   instruction may be sent through the coordinator after release. An
   `accepted-send` acknowledgement is not a restart: correlate the exact/new
   native task events and current watermark. A `resume-pending` child becomes
   `exact-resumed` only after its correlated post-release continuation event. A
   crash, partial restart, or uncertain send never replays the instruction or
   completed work.

6. Keep the other intents separate. `ctx hold` retains stopped native workers
   and their old parent/task records. `ctx restart` uses a caller-supplied
   checkpoint to create a new coordinator lineage; only after its release may
   new native child tasks be requested, never by cross-parent exact rebind.
   `handoff` is user-only and records only a caller-supplied checkpoint. It is
   not part of swap and does not pause, restart, release, or change claims.

7. Run `shutdown`, `recover`, `status`, and `unenroll` checks only against
   fake temporary state. Shutdown retains owner and claims until current-run
   child/tool/process/effect evidence proves quiescence. Unenroll is the only
   operation that clears them. A schema-version mismatch with the old
   independent-worker prototype must refuse until an explicit migration; do
   not hand-edit or silently reinterpret its state.

Any live experiment belongs to the separately authorized
[live-validation gate](live-validation.md). It must publish the exact tested
runtime and participant kinds and remain **UNVERIFIED** until reviewed. This
quickstart itself performs no live action and creates no written swap handoff.
