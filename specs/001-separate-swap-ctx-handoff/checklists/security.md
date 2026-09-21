# Security Requirements Quality Checklist

**Purpose**: Formal release-gate review of trust, credentials, permissions, and local control requirements
**Created**: 2026-09-16
**Feature**: [spec.md](../spec.md)

- [x] CHK001 Are credential-copying, auth probing, secret logging, and inherited provider override behaviors explicitly prohibited? [Spec §FR-010]
- [x] CHK002 Are expected account, family, profile ambiguity, and unsupported setup-token outcomes defined? [Coverage, Spec §FR-009–FR-010]
- [x] CHK003 Is actual permission-mode preservation distinguished from launcher-injected bypass behavior? [Clarity, Plan §Technical Context]
- [x] CHK004 Are filesystem ownership, modes, symlink rejection, traversal, atomic writes, and fsync requirements stated? [Completeness, Spec §FR-015]
- [x] CHK005 Are socket ownership, request size, stale generation, malformed frame, and timeout requirements bounded? [Completeness, Spec §FR-016]
- [x] CHK006 Is fake evidence prevented from asserting production/live capability? [Integrity, Spec §FR-018–FR-019]

## Native Architecture Override — 2026-09-16

The checked items above preserve the checklist's earlier review history. Their
independent-worker security assumptions are historical and superseded by the
approved native-subagent decision; they are not current acceptance criteria.
The items below are the active native-architecture security release gate.

### State, identity, and profile trust

- [ ] CHK007 Does the durable-state contract explicitly prohibit credentials, tokens, transcript/conversation bodies, generated prose, summaries, semantic handoffs, and checkpoints while retaining only native IDs, statuses, references, digests, and evidence? [Confidentiality, Spec §FR-028, Data model §CoordinatorRecord]
- [ ] CHK008 Are managed records required to live outside product worktrees in the owner-only same-store area with atomic writes, fsync/journal integrity, and workspace/common-directory identity checks? [Completeness, Spec §FR-028, Research §Decision: durable state is versioned and fail-closed]
- [ ] CHK009 Are unsafe filesystem modes, ownership, symlinks, traversal, and workspace mismatch defined as explicit fail-closed outcomes rather than recoverable guesses? [Edge Case, Spec §FR-028, Plan §Durable state and compatibility]
- [ ] CHK010 Does profile resolution require an explicitly named, authorized, same-transcript-family target and verified account identity while remaining read-only? [Clarity, Spec §FR-029, Data model §Profile reference]
- [ ] CHK011 Are unsupported setup-token/auth combinations, inherited provider overrides, credential copying, account discovery, and launch-configuration mutation explicitly refused? [Security Boundary, Spec §FR-029/FR-034, Existing CHK001]
- [ ] CHK012 Does the permission contract validate each native child's actual immutable tools, permission mode, model, effort, workspace, and custom-agent definition, without broadening a read-only parent or trusting an unknown identity? [Least Privilege, Spec §FR-017/FR-029, Research §Decision: lineage claims and native policy are distinct]

### Startup, inference, and effect safety

- [ ] CHK013 Does Gate 0 require evidence from the actual selected SDK and CLI/transport path—including release, executable/configuration digest, runtime version, launch mode, and a no-auth orphan fixture—rather than relying on a promptless fake? [Release Gate, Spec §FR-009, Plan §Implementation sequence]
- [ ] CHK014 Are source terminal child stop and observed durable current-worker-state clear required before old-parent exit, and target `restored_orphans=0`, no wake, and zero model request required before release? [Integrity, Data model §OperationRecord, Research §Decision: exact restore has a pinned capability gate]
- [ ] CHK015 Is it explicit that print/stream-json mode, `connect(prompt=None)`, a launch acknowledgement, cancellation acknowledgement, parent exit, or OS suspension alone cannot prove no startup inference, child quiescence, or safe account transition? [Clarity, Spec §FR-007/FR-009, User Story 2 §Acceptance Scenarios]
- [ ] CHK016 Does inability to hold orphan auto-resume or initialization inference result in public unsupported/refused status, with no fabricated classifier callback/state or silent fallback? [Fail Closed, Spec §FR-009, Plan §Control phases and swap]
- [ ] CHK017 Are unmanaged detached descendants, unknown writers, uncertain remote effects, and missing end evidence required to retain claims and block release, replay, resend, or competing writers? [Effect Safety, Spec §FR-008/FR-016, Research §Decision: background Agents are tracked; detached work is unsafe]
- [ ] CHK018 Does the contract separate tracked native background Agents with captured lifecycle identity from detached shell/background effects, so the former require tested evidence and the latter remain held or refused? [Participant Boundary, Spec §FR-006, Data model §TeamObservation]

### Schema, transport, and authorization boundaries

- [ ] CHK019 Are missing, unknown, or superseded independent-worker schemas refused with an explicit reason and preserved for operator recovery, with no destructive or inferential migration? [Compatibility, Spec §FR-031, Data model §Control and safety invariants]
- [ ] CHK020 Do durable request IDs, content digests, generation checks, malformed/oversized framing rules, and overlap rules prevent changed-content retries or stale requests from dispatching twice? [Replay Safety, Spec §FR-026/FR-027, Plan §Durable state and compatibility]
- [ ] CHK021 Are local transport requirements sufficiently bounded for socket ownership, frame size, connect/operation deadlines, and refusal reporting without weakening the native release fence? [Completeness, Plan §Technical context, Existing CHK005]
- [ ] CHK022 Is explicit operator authorization required for live account actions, profile transitions, and runtime probes in disposable scope, with unattended authentication, credential migration, network setup, and quota claims excluded? [Authorization, Spec §FR-034, Spec §Assumptions]
- [ ] CHK023 Are teams and every other unverified participant kind refused or labeled unsupported by default, rather than admitted under a generic child or fake-evidence security claim? [Scope, Spec §FR-003, SC-001/SC-004]
- [ ] CHK024 Does the swap/restart contract prevent generated handoff, summary, checkpoint, commit, push, stash, reset, and worktree-reconstruction artifacts from becoming an unintended secret or authority channel? [Data Minimization, Spec §FR-015/FR-024/FR-028]
- [ ] CHK025 Do public status and help surfaces label unverified live capabilities, account-control zero-model scope, post-release restart usage, and unsupported participant kinds so operators cannot mistake test evidence for authorization? [Operator Safety, Spec §FR-035, SC-011]
