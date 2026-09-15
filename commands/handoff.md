---
name: "Handoff"
description: "/handoff hands this lane off — the act /swap and /lane-swap also name, and the one /ctx runs before it restarts the pane"
category: Lane
tags: [lane, handoff, swap, ctx, lane-collision-protocol]
---

**Invoke the `handoff` skill now and follow every step of it, in order, to the end.**

That is the whole of this command, and the arguments typed after `/handoff` are its `why` and its flags:

- `/handoff [why]` — the swap, the reset, the profile switch. The why is free text: `clear`, `reset`,
  `switch`, `handoff to <who>`.
- `/handoff --restart` — the same act with the restart attached. `/ctx` is its short name and runs the same
  skill: the record first, then the lane's own pane respawned through the launcher with this handoff's top
  block as the new session's first prompt (Amendment 17(f)).
- `/handoff --exit requested by <uuid>@<host>/<container>` — the handoff another place requested: the record,
  then `/exit` typed into this lane's own pane, because a handoff to another place is a handoff and not a
  restart (Amendment 18(d)).

Lane-collision-protocol **Amendment 17(a)**, in force 2026-09-14T09:45:33Z: one act, three names, and
`lane-handoff` on `PATH` for the same steps from a shell. The steps are not restated here — the skill is the
single source of the act, and two copies of one procedure that must stay byte-equal is the rejected
alternative.
