---
name: "Handoff"
description: "Experimental managed checkpoint record only; retain the historical handoff workflow for unmanaged lanes"
category: Lane
tags: [lane, handoff, swap, ctx, managed]
---

## Managed lanes (opt in explicitly)

Native/live support remains experimental and `UNVERIFIED`. The control client
accepts the following syntax; it does not certify the native lifecycle
integration. The current managed runtime path is incomplete, so unsupported or
inconclusive managed operations must refuse before source interruption rather
than fall back to the legacy procedure. Managed handoff is a
checkpoint-recording operation only:

```sh
lane-managed handoff <lane> --checkpoint <checkpoint>
```

Pass the current `--generation <generation>` for the managed owner.
The checkpoint reference must be supplied by the caller. The supervisor records
it and returns; it does not pause or interrupt participants, restart a process,
change the account/profile, acquire or release a writer claim, dispatch a
message, or invoke `release`. A managed handoff is not evidence that swap or
ctx completed. Invalid checkpoint input or a stale generation refuses without
changing lifecycle state; recording a reference does not validate its contents.

Swap and worker restart never invoke handoff or generate a written handoff,
summary, or checkpoint. A supported implementation has one coordinator and
native children, with exact parent restore during swap. Safely stopped
unfinished children remain `resume-pending` or `restart-pending` until explicit
release; `exact-resumed` and `restarted` require correlated post-release native
events. A checkpoint record proves none of those lifecycle facts.

For an explicit user message, the client syntax is
`lane-managed submit <lane> --recipient-id <coordinator-id> --payload <reference>`.
The native contract addresses the coordinator and queues input while held or
fenced; there is no independent child mailbox. Native dispatch integration
remains unverified. Ctx's distinct hold/restart policies remain planned as
described in `commands/ctx.md`. `shutdown` retains the managed owner, control
service/endpoint, and claims; only explicit `unenroll`, after authoritative
quiescence and effect resolution, removes them. Handoff changes none of these.

## Unmanaged legacy compatibility

Without durable managed ownership, `/handoff [why]`, `/swap`, and
`/lane-swap` retain their historical aliases and invoke the legacy handoff
skill. `/ctx` retains its historical restart form. These aliases remain for
existing unmanaged records and do not silently become managed operations.
Legacy `lane`, `lane-start`, and handoff surfaces refuse a managed-owned lane
rather than falling back to a second owner.
