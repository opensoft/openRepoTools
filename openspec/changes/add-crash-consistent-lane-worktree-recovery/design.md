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

## Decisions taken in implementation (opensoft/openRepoTools#91)

The eight decisions above were written before the openRepoTools lane tooling was
read against them. Each of the following records where the implementation
DEVIATES from one of them, and why; none of them is a silent departure, and
every one names the ratified rule or the AGENTS.md ruling it answers to.

### 9. `RUNNING` is written by the confirming act, not by the SessionStart hook

Decision 5 gives `RUNNING` to "the SessionStart path". In this estate that path
is `lanes-edit.sh session-start`, whose three properties are ratified and
load-bearing: **it never writes, it never touches the network, and it always
exits 0** (lane-collision-protocol Amendment 8, `R-A8-1`) — which is what makes
it safe to put in front of every session on the workstation. A hook that writes
is a hook that can break the session it was meant to orient, and a hook that
fetches puts two network round-trips in front of every session start.

The act that actually proves canonical lane, transcript, agent, directory and
exclusive binding is `lane-start` (with or without `--no-launch`), and the proof
it leaves is its `STARTED`/`RESUMED` line. So `RUNNING` follows THAT line, in
`write_event` — the register's single writer, which already validates the
session field and Amendment 17(b)'s sub-fields there for the same reason: from
any caller, over one implementation. `ENDED`/`RETIRED` become `CLOSED` by the
same rule. The hook still only reports, and the capability specification is
worded as *the confirming act* rather than *SessionStart* for this reason.

### 10. The lifecycle snapshot is local, and it is written where `R-A11-14` stops the register

Decision 3 pairs a snapshot with the append-only history. The snapshot is NOT
in the register: `lanes/LANES.md` is one file shared by every lane on every
workstation and every write of it is a commit, a `pull --rebase` and a push
(Amendment 5), while a transition is taken three times per handoff and must work
with no network at all. Nor is it inside a git worktree, for decision 2's own
reason.

It follows that Amendment 11's `R-A11-14` — no record is FILED UNDER A
WORKSTATION where none is configured, because such a record is unfindable by
every restart of every workstation — does not reach it. The snapshot is filed
under nothing, never committed and never leaves the machine that wrote it, so a
container with no `$LANES_WORKSTATION` still keeps a lifecycle it can recover
itself from. The two writers are therefore deliberately absent from
`lanes-edit.sh`'s dispatcher workstation guard, and the register and object-log
writes stop there exactly as they did.

### 11. The control root is derived from the lane's own checkout, not from a shape-governed worktree root

Decision 2 places the control root under "the shape-resolved worktree root". In
openRepoTools a lane keeps its writers in two places — `<checkout>/.claude/
worktrees/<name>` and `<projects>/.lane-worktrees/<lane>/<name>` — and NEITHER
is under `$SPECKIT_GIT_WORKTREE_ROOT`, which is where openRepoShape puts
governed FEATURE worktrees and where `AGENTS.md` forbids this tooling to
hand-roll anything at all.

So the control root is resolved in three rungs, none of them the caller's
current directory: `$LANES_LANE_STATE_ROOT/<lane>`; else `<parent of the lane's
recorded `dir`>/.lane-state/<lane>`, the same parent the lane's own
`.lane-worktrees/<lane>` root sits in, where `dir` is Amendment 11(c)'s recorded
field; else `$PROJECTS_ROOT/.lane-state/<lane>`. No answer is the honest answer
`8` — a lane that has not started under Amendment 11(c) has no directory to
derive one from, and Amendment 7(i)'s cutover rule is that nothing is
backfilled. This keeps decision 2's actual rule — *the sidecar is an index over
shape-governed paths, which are never moved* — and spells it for this
repository.

**And it is only half of the brainstorm's "derivable lane root".** That document
asks for a root resolved *"without relying on a historical absolute path"*, and
rung 2 is exactly such a path: Amendment 11(c)'s recorded `dir`. It is a
RECORDED fact rather than a guess or the caller's current directory, which is
what makes it safe to act on — but resolving the root from `home owner/repo`
and the estate, with no recorded path at all, is the coordinator-base work of
tasks 1.2 and 5.3 and is not in this implementation.

### 12. No sixth lane verb is added to the append-only log

Decision 3's alternative (derive everything from events) was rejected there for
the reasons it gives. The converse also holds and is stronger here: Amendment
7's lane-kind verbs are `STARTED`, `PAUSED`, `RESUMED`, `ENDED` and `RETIRED`,
and a sixth would change what `swapped_candidates`, `lane_row_facts`,
`lane_payload_field`, `lane-last`, `who` and `lane-end` each mean by *a lane's
last lane-kind line* — in a file nothing rewrites, on every workstation until
adoption reaches it. `SWAPPING` is therefore a snapshot state and never a log
line, and every existing reader is untouched.

### 13. `SWAPPED` needs three landed writes, and the swap still completes without them

Decision 4 says the operation "is not reported ready to swap until `SWAPPED`
lands". Amendment 11 Addendum 4 ruling 11 (`R-A11-11`) says a swap is never left
unwritten, and `lane-handoff` implements it: the restart line is printed even
where the row flip or the handoff refresh was refused, because a person whose
session is about to die needs the command either way.

Both are kept by separating them. The lifecycle commits `SWAPPED` only when all
three of the lane's `PAUSED` record, the row's state cell and the handoff file
have landed — the same three `--restart` and `--exit` already gate on — and
otherwise the state STAYS `SWAPPING` and the output names the unfinished step.
The READY line still prints, and now names the state it is printing under. A
lane called `SWAPPED` on two of the three is a lane whose recovery would skip
the third.

### 14. Reconciliation reports; `resume` remains the only rebuild, and it is NAMED, not invoked

Decision 7 says the system "names or invokes the estate `resume` path". It
names it. `AGENTS.md` rule 1 is that **`park` CREATES NOTHING and `resume`
RESETS NOTHING**, and `resume <Name>` runs that estate's own `make resume`
across every member of it — which is not a thing a read may do as a side effect
of a report. `lane-reconcile` runs `git status`, `git log @{u}..`,
`git rev-parse` and `git worktree list --porcelain` and nothing else; it never
deletes, resets, force-adds or prunes, and a stale worktree registration is
reported with the `git worktree prune` that clears it rather than pruned.

**Nor does the report take the lane lock.** The brainstorm has resume *"acquire
the lane lock"* before it reconciles; the lock here is the register's own mutex,
and taking it for a READ would serialize every launch on the workstation behind
every register write for the length of a `git worktree list` in each of a
lane's checkouts. The lock is taken where it decides something — around the
read of the fence and the replacement of the snapshot together, in
`set-lane-state`, so two transitions cannot both read the state before either
writes it. A report that raced a transition would print a state one moment
stale, which is what the `VERDICT` line is for.

### 15. An unreadable holder is `indeterminate`, and never a crash

The crash kinds are the lifecycle word crossed with the live-holder read, and
that read has three answers, not two: `0` a holder, `8` none, and anything else
**the records could not be read** — which is never "no holder" (`R22`, and
Amendment 7(d): a read that failed is never an answer). A holder that could not
be established therefore yields the verdict `indeterminate` and no crash is
pronounced on a read nobody got. `RESUMING` remains unpersisted, as decision 5
proposes.

## Decisions taken in the review round (Copilot round 5 on opensoft/openRepoTools#97)

### 16. EVERY lifecycle write is serialized and fenced, the follow-up included

The first implementation fenced `set-lane-state` and left the follow-up at the
foot of `write_event` unfenced *deliberately* — a confirmed `STARTED`/`RESUMED`
is a new owner arriving, and advancing the generation over the `SWAPPING` it
supersedes is exactly what the fence is for. What that argument missed is that
the two cases are the same act read at different moments. `write_event` appends
the line, commits it and pushes it before the snapshot is moved, and a lane can
be recovered by somebody else inside that window: a `RUNNING` written out of an
event that landed minutes ago would then overwrite a `SWAPPING` that began
since, which is precisely the overwrite the generation exists to refuse.

So the follow-up reads the snapshot under the same mutex `set-lane-state`
takes, and compares it with the PRE-IMAGE `write_event` took before its own
line existed — state, generation and operation in one string. Equal means this
write is the newest act on the lane and it proceeds; unequal means another act
got there first and NOTHING is written, with the lane named so a person can read
it. The mutex is taken **without dying for it**: the event line is already on
disk, so a lock nobody could take within 20 seconds costs the snapshot and says
so, never the event (`R-A11-11`).

### 17. A sidecar this helper cannot read is one it must not replace

`lane_state_read` fails closed for a schema version it does not know, and both
writers beside it read the raw fields and renamed their own file over the top —
so an older helper meeting a newer tooling's snapshot destroyed a record it
could not even read, and nothing later can undo that. The fail-closed contract
therefore binds the WRITERS too: `set-lane-state`, `set-lane-tree` and the
`write_event` follow-up each ask the schema first and refuse (exit 1) rather
than replace. The refusal is 1 and not 7 — 7 says a race was lost and invites
the caller to re-read and try again, and no re-read makes an unknown schema
readable. The inventory READER gained the same rule: `lane-trees` reports an
unknown sidecar by its id, path and schema and reads not one other field of it,
and `lane-reconcile` classifies it `unknown-schema` rather than recomputing git
against fields it is guessing at.

**And the inventory's own fence is compared rather than merely recorded.** Every
tree sidecar carried the generation and operation it was written under from the
first commit of this change, and nothing read them: a handoff that stalled while
a recovery advanced the lane filed its superseded poll straight over the current
one. `set-lane-tree` now compares both with the lane's snapshot under the mutex
and refuses with **7**; and where an observation is legitimately older than the
lane's current generation, `lane-reconcile` says so on the tree's own line.

### 18. One implementation of the observation, and an incomplete one is never completed

`lane-handoff` computed its own branch, head, upstream, dirty and unpushed for
every writer it polled and handed all five to `set-lane-tree` — a second
implementation of `lane_tree_now` with its own error handling, so the WRITERS
section a person reads and the sidecar a recovery reads could disagree about
what git said. The observation is now one function behind one read verb,
`lanes-edit.sh lane-tree-now <path>`, and the handoff records what it answers.

That one function no longer converts a git read which FAILED into a value.
Every read after the first `rev-parse --git-dir` used to end in
`|| printf 'unknown'`, `|| printf 'none'` or a count that fell back to `0`, so a
partially unreadable repository produced a record that looked CLEAN AND
PUBLISHED — and a later reconciliation comparing against it would call a tree
holding work `missing` rather than `possible-loss`. A failed read is now an
incomplete observation that prints nothing, which `set-lane-tree` refuses to
file and `lane-reconcile` reports as `unreadable`. Two states are answers rather
than failures and are spelled: `unborn` for a branch with no commit yet, and —
for a branch whose upstream is configured while its remote-tracking ref is not
in this checkout, the ordinary state after a merged branch is deleted — the
configured upstream with `unknown` unpushed, never the `0` that reads as
*everything here is published*.

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

- ~~Which existing lane lock becomes the single transition lock?~~ **Settled by
  the implementation**: `lanes-edit.sh`'s own mutex, taken around the read of
  the fence and the replacement of the snapshot together, so two transitions
  cannot both read the state before either writes it. How it is shared across a
  host/container boundary remains open — the snapshot is local to a machine by
  decision 10, so today it is not shared at all.
- ~~Does recovery complete an interrupted operation ID or always supersede it?~~
  **Settled**: it supersedes. A handoff that finds the lane still `SWAPPING`
  takes it over with a NEW generation and names the operation that never
  finished; that new generation is precisely what refuses the old finalizer if
  it ever wakes. Nothing of the interrupted operation is undone.
- Which tree-level discrepancies block the entire coordinator versus only that writer's relaunch?
- What subset of sidecar data is replicated through the workspace repository for another workstation?
- How should lane-specific scratch worktrees be named without colliding with Speckit feature identifiers?
