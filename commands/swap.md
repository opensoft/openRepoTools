---
name: "Swap"
description: "/swap is the alias of /handoff: hand this lane off for a usage reset or profile switch"
category: Lane
tags: [lane, swap, handoff, ctx, lane-collision-protocol]
---

**Invoke the `handoff` skill now and follow every step of it, in order, to the end.**

That is the whole of this command. `/swap` is an alias (lane-collision-protocol Amendment 11 clause (g), SPEC
§9, and Amendment 17(a), which renamed the act it points at): the canonical name is `handoff`, the skill is
the single source of the act, and nothing here adds to, removes from, or reorders its steps. Two copies of
one procedure that must stay byte-equal is the rejected alternative, so the steps are not restated here —
read them there.

`/handoff`, `/swap`, `/lane-swap` and the shell command `lane-handoff` are four doors to one act and write
the same record. A context clear is that act with the restart attached: `/ctx`.
