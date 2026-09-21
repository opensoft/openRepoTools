## 1. Proposal review and governance

This is a governance and implementation-handoff checklist, not an executable
implementation task list. The shared OpenSpec/Speckit protocol assigns
executable tasks to exactly one later Speckit feature. Artifact completeness is
not proposal approval or evidence that Claude's compatibility gate has passed.

- [ ] 1.1 Approve the distinct swap, ctx, handoff, and native worker-restart
  contracts; verify that native children remain in the coordinator execution
  lineage, exact same-agent continuation is preferred where verified, and a
  post-release model-assisted new-native restart has no written handoff.
- [ ] 1.2 Approve the protocol amendment and legacy-alias migration replacing
  Amendment 17's one-act interpretation; verify a cited governance decision
  covers command meanings, explicit release, worker statuses, and historical
  record compatibility. Review the [proposed governance review](governance-review.md),
  which is explicitly **PROPOSED — NOT APPROVED** until that citation exists.
- [ ] 1.3 Agree integration ownership with the recovery and supervised-context
  changes, including PR #121; verify one lifecycle authority, shared operation
  locking, lineage-owned claims, optional isolated-worktree claims, and
  compatible intent modes. Use the [proposed governance review](governance-review.md)
  for the read-only PR comparison and unresolved ownership/landing decisions;
  it is **PROPOSED — NOT APPROVED**.

## 2. Speckit handoff and feasibility decision

Speckit feature: [001-separate-swap-ctx-handoff](../../../specs/001-separate-swap-ctx-handoff/spec.md).
Implementation branch: `001-separate-swap-ctx-handoff`, in its sibling feature
worktree. Brett subsequently authorized the architecture change and
implementation ("implement our new version" and "yes, make the arch change").
The approved revision retains Claude's native subagents in the coordinator's
session-lineage. It prefers verified exact same-agent continuation and permits
a model-assisted **new native child** restart only after target readiness and
explicit `release`, without generating a semantic or written handoff.

Native child identity comes from the runtime's agent/task IDs, parent linkage,
containing process tree, and hook/tool lifecycle evidence. No independent
child-runner UUID, process group, open/shutdown/release operation, or account
session is an implementation target. Runtime-owned background children and
teams are not automatically supported; their tested native boundaries must be
published. The old independent-worker prototype schema must be explicitly
refused or version-migrated, never silently reinterpreted or deleted.

The linked feature's [tasks](../../../specs/001-separate-swap-ctx-handoff/tasks.md)
are the sole executable checklist. Its
[verification record](../../../specs/001-separate-swap-ctx-handoff/verification.md)
tracks incomplete acceptance, and its
[live gate](../../../specs/001-separate-swap-ctx-handoff/live-validation.md)
remains incomplete; bounded scripted observations do not assert production or
cross-account success.

The 2026-09-18 [coordinator interrupt decision](coordinator-interrupt-decision.md)
records the next design step authorized after Stage 1: a separate durable
whole-roster interrupt and independent drain contract. The linked Speckit
artifacts reconcile its implementation tasks. The bounded scripted runtime
results do not close the governance or full runtime acceptance items below.

- [x] 2.1 Record the approved implementation handoff to the single linked
  Speckit feature and its feature worktree; executable tasks remain owned
  there.
- [ ] 2.2 Review that feature's Gate 0 evidence for external stop/load control,
  exact coordinator resume, native agent/task discovery, explicit parent/child
  admission fencing, startup orphan auto-resume checks, tracked background
  stop boundaries, and active-tool ownership. Verify the exact SDK-selected
  CLI executable, SDK/CLI versions, launch mode/arguments, and full binary
  digest are pinned. In the observed SDK `0.2.153` bundled-first case, this
  means CLI `2.1.273` (digest prefix `6c752e2c`); an earlier CLI `2.1.270`
  trace is not evidence for that pairing. Verify a no-auth orphan fixture,
  `PostToolUse(Agent)` is not treated as child quiescence, reused IDs/stale
  notifications are correlated to the current task/parent invocation and
  event watermark, and every unfinished worker receives an honest pending or
  terminal status: `resume-pending`, `restart-pending`, `exact-resumed`,
  `restarted`, or `unresolved`.
- [ ] 2.3 Verify the source runtime terminal-stops every tracked native child
  and durably clears its current-state record before source-parent exit, then
  verify target startup's no-wake/no-model behavior. Specifically cover the
  bundled CLI `2.1.273` print-path `restoredOrphans` default wake and
  `enqueuePendingNotification`; print or stream-json mode alone is not proof
  of a held graph. Refuse the configuration when either proof is missing.
- [ ] 2.4 Confirm the context contract distinguishes `hold` (stopped old
  native workers retained, without promising survival across parent shutdown)
  from `restart` (new-lineage workers from an explicitly supplied checkpoint
  only after release), and preserves each worker's model, effort, tools,
  permissions, and custom-agent definition.
- [ ] 2.5 Resolve the blocking design questions before production
  implementation planning; verify the recorded transport, lifecycle
  integration, lineage/worktree claim, and measured deadline decisions, or an
  explicitly approved design revision if native preservation is insufficient.

## 3. Release evidence and closure

- [ ] 3.1 Review the linked feature's acceptance evidence against both
  capability specs; verify coverage of zero-new-model-request control,
  explicit release-gated new-native restart, parent/child inference control,
  startup orphan terminal-stop/current-state-clear and target no-wake behavior,
  dirty-work preservation, account identity, native
  worker `resume-pending`/`restart-pending`/`exact-resumed`/`restarted`/
  `unresolved` statuses, duplicate-writer prevention, uncertain effects,
  completed-worker preservation, deadlines, and crash/retry recovery.
- [ ] 3.2 Confirm published supported configurations and migration guidance
  match measured behavior; verify unsupported modes refuse explicitly, native
  teams/background forms are not implied, and swap/restart do not silently
  fall back to semantic handoff, fresh context, invented child sessions, or
  replay of completed/uncertain work.
- [ ] 3.3 Archive only after the linked implementation and applicable
  cross-repository dependencies land, or after explicit abandonment; verify the
  closure record names the approved native-lineage decision and landed
  changes.
