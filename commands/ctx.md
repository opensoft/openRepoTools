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
2. **then** a **RESTART INTENT** is written under the lane's own control root — the lane, a generation, an
   operation id, the transcript being paused, the agent, the profile, the checkout, the pane, the handoff's
   path and its **digest**, and the launch mode `fresh-from-handoff` — and read back;
3. **then** the lane's own pane is respawned — `tmux respawn-pane -k`, so the act survives the death of the
   session that started it — with the **pane supervisor** (`lane-handoff --supervise`, by absolute path). The
   supervisor claims that intent, runs the launch as its **child**, and stays in the pane whatever happens;
4. the launch is a NEW session of the same agent whose FIRST PROMPT is the top block written in step 1, run
   without anyone typing it;
5. that session stamps `RESUMED by …` first, as Rule 3 requires, then **COUNTS the live writers** —
   `ListAgents`, the agent's equivalent elsewhere — because the block's `WRITERS` section is a list to COUNT
   and not a list to relaunch (Amendment 17 Addendum 1 (i), in force 2026-09-14T20:59:31Z). A writer still
   live OWNS its worktree and is told, not relaunched; only a writer that is NOT live is relaunched, from
   where it stood;
6. only when the replacement is **positively confirmed** — a live child, exactly one holder of this lane, its
   transcript the new one and not the paused one, in the pane the intent names — is the restart marked
   `ready`. Until then it is not.

**Steps 2, 3 and 6 are new, and they are `opensoft/openRepoTools#94`.** On 2026-09-15 this command wrote its
record, respawned the pane with `LANE_START_FRESH=1 … lane <lane>`, and what came up was
`claude --name <lane> --resume <the uuid it had just paused>` — the same conversation, not a fresh one, with
no supervisor to notice. The seam was an **environment variable**, and the launcher re-creates its child
through `tmux new-session`, which hands that child the tmux **server's** environment and not the caller's.
An environment cannot cross that boundary; a **file** can, so the intent on disk is now the authority and
`LANE_START_FRESH` is a compatibility detail. And what tmux starts is a supervisor rather than the launch
itself, because a launch that ends takes the pane with it — Amendment 11's own invariant is *"No path the
launcher opened exits the pane"*, and this one did.

**`/ctx` says which it did** (Addendum 1 (j)). This one respawns the pane, so the process every writer was a
child of is gone, the record says `kind respawn`, and the count then finds none — which is what makes
relaunching each one right. A clear that happens IN PLACE keeps that process and its writers with it: that
one is `--in-process`, `kind in-process`, and its block says to EXPECT every writer below live. Either way
the kind says what to expect and never what to do.

**A `/ctx` whose record could not be written REFUSES before it kills anything.** A pane is never respawned
over an unrecorded lane — and the record is now FOUR writes, not three: if the `PAUSED` line did not land, or
the row was not flipped, or the handoff's top block (which is the new session's first prompt) could not be
refreshed, **or the restart intent could not be written and read back**, this pane stays exactly as it is and
the reason is printed. A pane respawned with no intent is a pane whose supervisor has nothing to launch from,
which is the same unrecorded restart one step along.

**A restart already in flight is not superseded.** A second `/ctx` on a lane whose intent is `pending` or
`starting` refuses — before the kill — and names `lane-handoff --restart-status --lane <lane>`.

**When the launch fails, the pane is still yours.** The supervisor marks the intent `failed`, prints the
stage that failed and offers one line to retry the same operation. Nothing of the lane is lost: the handoff
it wrote is intact and its top block is still the first prompt the next session gets.

No picker, no title fallback, no second command: the one word is the whole act.
