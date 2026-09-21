---
name: "Ctx"
description: "Experimental planned native ctx hold/restart with incomplete integration; historical /ctx alias for unmanaged lanes"
category: Lane
tags: [lane, ctx, handoff, swap, managed]
---

## Managed lanes (opt in explicitly)

Native/live support is experimental and `UNVERIFIED`. The approved `ctx`
contract creates a fresh coordinator context under the current account from
an explicit caller-supplied checkpoint. The mapping-free `hold` and `restart`
forms are now complete at the public CLI/daemon wire boundary, but that wire
acceptance is not native lifecycle support. Missing controller or runtime
capability must fail closed rather than route through legacy handoff or the
superseded mapping path:

```text
lane-managed ctx <lane> --checkpoint <checkpoint> --workers hold
lane-managed ctx <lane> --checkpoint <checkpoint> --workers restart
```

Integration gap: the public parser and daemon route accept only the explicit,
mapping-free checkpoint plus `hold`/`restart` policy. They do not accept a
worker mapping or a body override that changes the selected policy. The
controller currently refuses `restart` for independent participants until
native restart admission and lineage transfer are implemented and correlated;
wire acceptance does not claim that lifecycle support. CLI, daemon,
controller, and runtime must implement the approved native contract together.

Under the approved contract in
`specs/001-separate-swap-ctx-handoff/contracts/managed-control.md`, the worker
policy is mandatory:

- `hold` stops and retains old native task records, parent links, claims, and
  unresolved effects. It does not promise live children survive parent
  shutdown. Releasing the fresh coordinator does not release those workers.
- `restart` creates a fresh coordinator UUID and execution lineage from the
  supplied checkpoint, keeping the durable lane owner and its generation.
  New native tasks may be requested only after explicit release. This is not
  exact cross-parent continuation; old task parent identities never change.

Before creating the fresh held coordinator, prove old-writer exclusion and
safe current-run child/tool stop boundaries. Preserve definitions, model,
effort, tools, permissions, dirty/untracked work, and lineage claims. An atomic
claim transfer must leave no ownership gap. Missing or contradictory evidence
keeps the lane held or indeterminate.

Explicit release syntax already exists in the control client:

```sh
lane-managed release <lane> --operation-id <operation-id> --generation <generation>
```

Release is a separate inference boundary, never implicit in ctx. Under the
restart policy, safely stopped unfinished work stays `restart-pending` until
release and correlated new native task events prove `restarted`. A send
acknowledgement is insufficient; uncertainty is `unresolved`, and completed
work stays completed. Preserve task/attempt correlation without claiming old
conversation or identity preservation or replaying uncertain effects.

Ctx does not switch accounts or generate a checkpoint. Worker restart writes
no handoff; `commands/handoff.md` is a separate checkpoint-only request with
no lifecycle effect. `shutdown` retains the managed owner, control service, and
claims; `unenroll` is explicit and requires proven quiescence. Native background
children and teams need capability evidence for their actual runtime; detached
or unknown effects cannot be treated as stopped from parent exit alone.
Fake tests do not verify native/live support, and legacy behavior is never a
fallback for a managed-owned lane.

## Unmanaged legacy compatibility

For a lane without durable managed ownership, `/ctx` retains its historical
meaning as `/handoff --restart` and invokes the legacy `handoff` skill. This
alias remains operational and executable for unmanaged lanes and existing
records. Legacy `lane`, `lane-start`, and handoff surfaces refuse a
managed-owned lane rather than launching a second owner.
