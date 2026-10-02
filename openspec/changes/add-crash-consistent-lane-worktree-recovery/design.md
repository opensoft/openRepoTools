## Context

Lane identity is stable across Claude profile rotation, but the process running a lane has one checkout directory while its writers may occupy several linked Git worktrees. Current records can resume a transcript and, for newer lanes, recover the coordinator directory. They do not provide a complete machine-readable worktree inventory or a crash-consistent distinction between token exhaustion before `/swap`, interruption during `/swap`, and a completed handoff.

The existing systems retain separate authority:

- the lane event log is append-only history and binding evidence;
- the handoff is the human/agent resume narrative and current writer inventory;
- Git and the filesystem are truth about surviving worktrees and unpublished work;
- estate `park`, `status`, and `resume` own durable cross-workstation reconstruction;
- openRepoShape/Speckit owns governed feature-worktree placement.

The design must run in Bash 3.2 environments, avoid unguarded shared-register rewrites, preserve legacy lanes, and never delete, reset, or overwrite an unknown worktree.

## Goals / Non-Goals

**Goals:**

- Make every worktree owned by a lane discoverable after its coordinator dies.
- Distinguish `RUNNING`, `SWAPPING`, and `SWAPPED` across every token-exhaustion window.
- Make swap completion and resume ownership atomic, exclusive, and generation-fenced.
- Recalculate worktree and publication state before launching replacement writers.
- Keep profile rotation independent from lane and worktree identity.
- Reuse the estate reconstruction mechanism for work that was durably parked.

**Non-Goals:**

- Reconstructing uncommitted file contents after their directory is lost.
- Automatically deleting unknown paths or stale worktree registrations.
- Replacing the lane event log, handoff, or estate parked record.
- Moving existing shape-governed feature worktrees merely to satisfy a lane-first visual layout.
- Treating an absolute path or profile as stable lane identity.

## Decisions

### 1. Separate stable identity, coordinator checkout, and writer trees

The stable lane record carries canonical lane name, `home owner/repo`, and estate. The workstation resolves those values to a canonical primary checkout. The coordinator SHALL launch from that base after migration to this capability; mutable feature work SHALL occur in writer worktrees.

This makes the coordinator location derivable and prevents a profile rotation from silently selecting a feature checkout. Existing lanes that were deliberately launched from a worktree require explicit migration rather than automatic rebinding.

Alternative considered: preserve arbitrary coordinator directories indefinitely. This retains flexibility but makes a feature path part of lane identity and prevents deterministic recovery when that worktree is removed.

### 2. Use a lane control root with sidecars outside Git worktrees

The shape-resolved worktree root gains a lane namespace conceptually equivalent to:

```text
<worktree-root>/.lanes/<canonical-lane>/
├── lane-state.yaml
└── trees/
    └── <tree-id>.yaml
```

Each tree sidecar records repository identity, role, path relative to the resolved worktree root, branch or detached state, HEAD, upstream, writer agent/session, lifecycle state, and the last observed dirty and unpushed counts.

The sidecar is an index: a governed Speckit worktree remains at its shape-prescribed feature-first path. A lane-specific scratch tree may use a lane-derived physical path only where that does not violate the owning repository's worktree contract.

Sidecars do not live inside worktrees because orchestration metadata must not dirty a checkout or disappear with it.

### 3. Pair an atomic current-state snapshot with append-only events

`lane-state.yaml` is atomically replaced under the same lane lock used to authorize transitions. Every successful transition also appends an event to the existing lane history. The snapshot makes current-state reads cheap; the event log preserves provenance and explains how the snapshot arose.

The state document carries `generation`, `operation_id`, owner transcript/session, agent, profile, binding, and update time. Finalization uses compare-and-swap semantics over state, generation, and operation ID.

Alternative considered: derive everything from append-only events. That preserves one source but makes exclusive multi-step transitions and stale-finalizer rejection substantially harder for every reader.

### 4. Make `/swap` a two-phase transition

`/swap` performs these ordered acts:

1. lock the lane and compare-and-swap `RUNNING` to `SWAPPING`, minting an operation ID and next generation;
2. enumerate and snapshot every expected and discovered writer tree;
3. poll live writers and require their existing commit/push or explicit unresolved-work outcome;
4. refresh and commit the handoff, including the reconciled writer inventory;
5. write the protocol's `PAUSED`/swap records;
6. compare-and-swap the same operation from `SWAPPING` to `SWAPPED`.

Any refusal, token exhaustion, or process death before step 6 leaves `SWAPPING`. The operation is not reported ready to swap until `SWAPPED` lands.

An old finalizer whose generation or operation ID no longer matches is refused. This prevents a delayed `/swap` from overwriting a recovered or newly running generation.

### 5. Let confirmed SessionStart own `RUNNING`

Resume does not mark a lane running when the launcher is invoked. State remains `SWAPPED` while the process starts. The SessionStart path changes `SWAPPED` to `RUNNING` only after it confirms canonical lane, transcript/session, agent, directory, and exclusive binding.

The first implementation does not persist `RESUMING`; an idempotent retry remains possible while state is `SWAPPED`. A future `RESUMING` state may be added if concurrent launch reservation cannot be expressed by the binding lock alone.

### 6. Reconcile intent with evidence before resume

Resume compares:

- lane and tree sidecars;
- the latest handoff inventory;
- live holder/session evidence;
- `git worktree list --porcelain` for every owning repository;
- actual paths beneath the resolved worktree root;
- current branch or detached HEAD, commit, upstream, dirty state, and unpushed commits.

Stored Git values are prior observations, not truth. Unknown or inconsistent paths are reported and preserved. A matching live holder blocks a duplicate; an absent holder under `RUNNING` or `SWAPPING` creates a recovery-required result.

### 7. Rebuild only through durable estate records

A missing tree may be reconstructed only when the estate parked record and its normal `resume` command authorize it. Lane tooling does not hand-roll `git worktree add`, WIP commits, soft resets, or force operations. A missing tree that may have held uncommitted work is a possible-loss refusal.

### 8. Treat profile as launch metadata only

Profile remains selectable on every launch. It is stored for diagnostics and default relaunch behavior but does not participate in lane identity, worktree paths, or generation ownership. A profile change resumes the same lane and validated worktree inventory.

## Risks / Trade-offs

- **[Risk] Lane-first discovery conflicts with feature-first Speckit paths** → Use a sidecar index over shape-governed paths; do not move governed trees.
- **[Risk] Snapshot and append-only history diverge** → Write under one lane lock, verify the event append, and surface disagreement as recovery-required.
- **[Risk] A stale PID appears live in another namespace** → Use the existing binding/session provenance contract, not PID alone.
- **[Risk] `RUNNING` remains after a process dies normally without `/swap`** → Treat `RUNNING` plus no verified holder as ungraceful and inspect all trees.
- **[Risk] A swap records `SWAPPING` and then permanently stalls** → Permit an explicit recovery/takeover operation that advances the generation while retaining the interrupted operation in history.
- **[Risk] Sidecars claim work is clean when Git changed later** → Recalculate all Git observations on resume and before `SWAPPED`.
- **[Risk] Coordinator-base enforcement disrupts legacy lanes** → Introduce explicit migration and warning stages before enforcing the invariant.
- **[Risk] Concurrent tooling versions interpret new state differently** → Version the sidecar schema and retain conservative fail-closed behavior for unknown versions or states.

## Migration Plan

1. Add read-only discovery and reporting for the new control root and state schema.
2. On an explicitly named lane start or successful `/swap`, create sidecars from verified repository identity, current binding, Git registrations, and the handoff; never scrape arbitrary prose silently.
3. Continue accepting legacy lanes with no sidecar through the existing explicit `--dir` path, while reporting that crash recovery is incomplete.
4. Add `SWAPPING` and `SWAPPED` writes behind compatibility detection so older installed readers fail closed rather than misclassify them.
5. Enable resume reconciliation before coordinator-base enforcement.
6. After existing lanes have been migrated, require the coordinator base and structured writer registration for newly created trees.

Rollback disables new writes but preserves sidecars and append-only events for diagnosis. It must not rewrite or remove lane history, worktrees, or handoffs.

## Open Questions

- Which existing lane lock becomes the single transition lock, and how is it shared across host/container boundaries?
- Does recovery complete an interrupted operation ID or always supersede it with a new generation?
- Which tree-level discrepancies block the entire coordinator versus only that writer's relaunch?
- What subset of sidecar data is replicated through the workspace repository for another workstation?
- How should lane-specific scratch worktrees be named without colliding with Speckit feature identifiers?
