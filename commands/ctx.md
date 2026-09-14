---
name: "Ctx"
description: "/ctx clears this lane's context in one word: the handoff is written, then this lane's own pane is respawned with a new session whose first prompt is that handoff's top block"
category: Lane
tags: [lane, ctx, handoff, swap, lane-collision-protocol]
---

**Invoke the `handoff` skill now with `--restart`, and follow every step of it, in order, to the end.**

`/ctx` is `/handoff --restart` and nothing else. Lane-collision-protocol **Amendment 17 clause (f)**, folded
in on Brett Heap's word of 2026-09-14, verbatim: *"the /ctx should also run the first prompt and restart all.
so the user only does /ctx and it is all automatic from there"* — and ratified the same day as revision 2.

What that means in order, and the order is the rule:

1. the identity triple is fixed, the handoff file is refreshed with a fresh Rule 3 top block that **lists
   every writer this lane has running** (its worktree, its branch, its brief, what it had committed), the
   writers are polled, and `PAUSED` is written with Amendment 11(c)'s sub-fields, Amendment 17(b)'s `agent`
   and `transcript`, and `clear` as its why;
2. **then** the lane's own pane is respawned through the launcher — `tmux respawn-pane -k`, so the act
   survives the death of the session that started it — with a NEW session of the same agent whose FIRST
   PROMPT is that top block, run without anyone typing it;
3. that session stamps `RESUMED by …` first, as Rule 3 requires, then **COUNTS the live writers** —
   `ListAgents`, the agent's equivalent elsewhere — because the block's `WRITERS` section is a list to COUNT
   and not a list to relaunch (Amendment 17 Addendum 1 (i), in force 2026-09-14T20:59:31Z). A writer still
   live OWNS its worktree and is told, not relaunched; only a writer that is NOT live is relaunched, from
   where it stood.

**`/ctx` says which it did** (Addendum 1 (j)). This one respawns the pane, so the process every writer was a
child of is gone, the record says `kind respawn`, and the count then finds none — which is what makes
relaunching each one right. A clear that happens IN PLACE keeps that process and its writers with it: that
one is `--in-process`, `kind in-process`, and its block says to EXPECT every writer below live. Either way
the kind says what to expect and never what to do.

**A `/ctx` whose record could not be written REFUSES before it kills anything.** A pane is never respawned
over an unrecorded lane — and the record is three writes, not one: if the `PAUSED` line did not land, or the
row was not flipped, or the handoff's top block (which is the new session's first prompt) could not be
refreshed, this pane stays exactly as it is and the reason is printed.

No picker, no title fallback, no second command: the one word is the whole act.
