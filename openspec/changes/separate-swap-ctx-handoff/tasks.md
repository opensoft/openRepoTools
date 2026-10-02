## 1. Proposal review and governance

This is a governance and implementation-handoff checklist, not an executable implementation task list. The shared OpenSpec/Speckit protocol assigns executable tasks to exactly one later Speckit feature. Artifact completeness is not proposal approval or evidence that Claude's compatibility gate has passed.

- [ ] 1.1 Approve the distinct swap, ctx, and handoff contracts and Claude-first scope; verify the recorded decision explicitly preserves full supported worker conversations without generated handoffs.
- [ ] 1.2 Approve the protocol amendment and legacy-alias migration replacing Amendment 17's one-act interpretation; verify a cited governance decision covers command meanings and historical-record compatibility.
- [ ] 1.3 Agree integration ownership with the recovery and supervised-context changes, including PR #121; verify a recorded decision identifies one lifecycle authority, shared operation locking, compatible intent modes, and how the persistent lane service coordinates with the existing pane-resident `/ctx` supervisor.
- [ ] 1.4 Agree the opt-in five-hour auto-swap policy and workBenches integration; verify target-profile configuration, fresh usage provenance, weekly non-trigger, window-based deduplication, and removal of the legacy model-directed 95% `/handoff` instruction for managed lanes.
- [ ] 1.5 Reconcile the two-authority launch hierarchy with the active Speckit feature: `lclaude` delegates managed launches to the lanes service, the lanes service starts/reconnects the lane's execution-group supervisor, and managed external shell/edit work uses admitted jobs. Verify that `ctx` moves under the same service lock before the pane supervisor loses restart authority, and that no direct-launch fallback or third independent transaction owner remains.

## 2. Speckit handoff and feasibility decision

Speckit feature: not created. Implementation branch/worktree: not created. No implementation is authorized by this documentation-only turn. Do not start production adapter work on an assumed Claude control surface.

- [ ] 2.1 After approval, record the link to exactly one Speckit feature and its implementation worktree, resolving the missing bootstrap prerequisite through the normal workflow; verify that feature references this proposal, design, both capability specs, and owns all executable tasks.
- [ ] 2.2 Review that feature's Gate 0 evidence for a lane service that is reused when running or started and readiness-checked when absent, survives old-session shutdown, and owns one operation per lane; for source-profile background workers becoming quiescent, target-profile background launch and tmux attachment, exact-ID restoration without a copied session, unfinished ordinary workers, routing, and active tools; verify supported Claude versions and participant kinds and reject coordinator-only success as completion.
- [ ] 2.3 Resolve the blocking design questions before production implementation planning; verify the recorded transport, lifecycle integration, and measured deadline decisions, or an explicitly approved design revision if native preservation is insufficient.
- [ ] 2.4 Verify the service watches registered lanes by current host/container/window binding, resolves the intended pane, and consumes an unrounded, fresh profile usage sample; test multiple lanes on one profile, detached/background sessions, rounded pane output, inaccessible bindings, absent/stale samples, an unconfigured target, repeated events, and a rate-limit `StopFailure` before treating the trigger as supported.

## 3. Release evidence and closure

- [ ] 3.1 Review the linked feature's acceptance evidence against both capability specs; verify coverage of zero-new-model-request control, dirty-work preservation, account identity, worker restoration, duplicate-writer prevention, uncertain effects, deadlines, and crash/retry recovery.
- [ ] 3.2 Confirm published supported configurations and migration guidance match measured behavior; verify unsupported modes refuse explicitly and do not silently fall back to handoff, fresh context, or parent-only resume.
- [ ] 3.3 Archive only after the linked implementation and applicable cross-repository dependencies land, or after explicit abandonment; verify the closure record names the decision and landed changes.
