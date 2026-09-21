# Compatibility Requirements Quality Checklist

**Purpose**: Formal release-gate review of runtime, profile, legacy, and platform compatibility requirements
**Created**: 2026-09-16
**Feature**: [spec.md](../spec.md)

- [x] CHK001 Are supported participants limited to independent top-level sessions and prohibited native graph kinds named? [Scope, Spec §FR-001–FR-002]
- [x] CHK002 Is exact-loader success defined without requiring initialization fields Claude does not emit? [Clarity, Research §official Python SDK]
- [x] CHK003 Are missing transcript, empty reserved session, loader-error-before-init, and no-fallback cases covered? [Edge Cases, Spec §Edge Cases]
- [x] CHK004 Is Bash 3.2 compatibility required for every new shell surface? [Platform, Spec §FR-017]
- [x] CHK005 Are managed-owner guards and unmanaged legacy compatibility both specified, including helper absence versus managed marker presence? [Migration, Plan §Design Phases]
- [x] CHK006 Are cross-machine, Codex runtime, and workBenches mutation explicitly outside this delivery? [Scope, Spec §Assumptions]

## Native Architecture Override — 2026-09-16

The checked items above preserve the checklist's earlier review history. Their
independent-worker assumptions are historical and superseded by the approved
native-subagent decision; they are not current acceptance criteria. The items
below are the active native-architecture compatibility release gate.

### Coordinator, child, and runtime compatibility

- [ ] CHK007 Does the specification explicitly supersede the earlier independent-top-level participant boundary, so native coordinator/child compatibility is judged against the approved architecture? [History, Spec §Authority and history, Plan §Re-planning status]
- [ ] CHK008 Are each supported native participant kind and pinned runtime version named with discovery, stop, exact-continuation, or restart evidence, while teams and other unproven kinds remain explicitly unsupported or refused? [Completeness, Spec §FR-003, SC-001]
- [ ] CHK009 Are exact coordinator restoration requirements explicit for the existing transcript identity, UUID, target account and storage family, permission mode, model/configuration fingerprint, workspace, runtime fingerprint, and successful exact loader initialization? [Clarity, Spec §FR-010, Data model §CoordinatorRecord]
- [ ] CHK010 Does the contract distinguish the coordinator's sole top-level session/process identity from native child fields (`agent_id`, `task_id`, native `type`, launch `tool_use_id`, parent links, and event references), without inventing child UUIDs, SDK controls, or process groups? [Consistency, Spec §FR-002, Data model §NativeChildRecord]
- [ ] CHK011 Are sparse `SubagentStart`/`SubagentStop` events required to join against current run, task, parent invocation, and event watermark, with ambiguous joins, reused IDs, and stale completion markers remaining unknown rather than compatible evidence? [Clarity, Spec §FR-007, Research §Decision: ledger native identity and lifetime separately]
- [ ] CHK012 Does the Gate 0 requirement identify the actual SDK-selected CLI/transport path, SDK release, executable/configuration digest, runtime version, and launch mode instead of treating a generic promptless adapter as portable evidence? [Release Gate, Spec §FR-009, Plan §Implementation sequence]
- [ ] CHK013 Are the separately installed CLI and SDK-bundled CLI cases kept distinct, including the observed `2.1.270` versus bundled `2.1.273` paths and their separate executable/configuration evidence? [Compatibility, Research §Evidence and unresolved questions]
- [ ] CHK014 Does startup compatibility require terminal source child stop, an observed durable current-worker-state clear, and target `restored_orphans=0`, wake-event absence, and zero model requests before release, while `connect(prompt=None)` and print/stream-json mode alone are explicitly insufficient? [Safety, Spec §FR-009, Data model §OperationRecord]
- [ ] CHK015 Is public native-graph support refused when orphan auto-resume or initialization inference cannot be held safely, rather than inferred from a fake parent or a single installed CLI trace? [Edge Case, Spec §FR-009, Research §Decision: exact restore has a pinned capability gate]
- [ ] CHK016 Are runtime-owned background Agent tasks with captured task/lifecycle IDs treated as tracked native participants, while detached shells, `nohup`/`setsid` descendants, and unknown effects remain held, unsupported, or refused? [Coverage, Spec §FR-006, Research §Decision: background Agents are tracked; detached work is unsafe]
- [ ] CHK017 Are the four final worker dispositions and the held-only `resume-pending` interim state defined as a compatibility contract, without silently converting unavailable native continuation into a different worker architecture? [Clarity, Spec §FR-011, Data model §NativeChildRecord]
- [ ] CHK018 Do profile compatibility requirements require an explicitly named, authorized, same-family target with verified account identity and preserved participant model, effort, tools, permissions, workspace, and custom-agent settings? [Completeness, Spec §FR-029, Data model §Profile reference]
- [ ] CHK019 Are legacy lane/lane-start/lane-handoff guards and the managed projection required to remain fail-closed around native ownership conflicts, while native children are not incorrectly required to have distinct top-level names or sessions? [Consistency, Spec §FR-030, Plan §Durable state and compatibility]
- [ ] CHK020 Is the external `lane-swap <lane> --profile <profile>` surface required to preserve literal lane data such as `swap` and Bash 3.2 syntax while refusing unsupported participant or ownership states? [Platform, Spec §FR-032, repo AGENTS.md §Driving `park`, `resume`, and `status`]
- [ ] CHK021 Does public compatibility status identify the tested runtime/participant combinations, four worker dispositions, tracked-versus-detached background effects, and every unverified capability rather than presenting native support as generic? [Acceptance, Spec §FR-035, SC-011]
- [ ] CHK022 Are the supported execution platforms and optional live-runtime boundary explicit—Linux, macOS, and WSL2 for the shipped shell surfaces, with no unverified native Windows twin or implicit live-account portability claim? [Scope, Plan §Technical context, Spec §Assumptions]
