## Context

The `UserPromptSubmit` guard currently treats a window lane and a live Claude
session name that disagree as a hard identity failure. It already has a
pending-answer mechanism for a user-created rename, but that mechanism only
offers moving to the session's lane or renaming back, and it cannot explicitly
accept a deliberate mismatch.

## Goals / Non-Goals

**Goals:**

- Make recoverable lane/session name drift an explicit, one-prompt decision.
- Keep the decision scoped to the current lane/session pair and preserve the
  existing fail-closed behavior for unreadable or ambiguous state.
- Support three choices: allow this lane, move the lane binding to the session
  name, or rename the session to the lane name.
- Ensure the session-to-lane choice types `/rename <lane>` into the verified
  active Claude pane.
- Keep `pclaude --lane` on the exact-ID path when a restart records a harness
  UUID while continuing the Claude transcript named by the last PAUSED record.

**Non-Goals:**

- Changing the installed hook command or Claude hook configuration.
- Making unreadable registers, missing session records, duplicate transcripts,
  or superseded sessions permissive.
- Changing lane-start's session naming contract.

## Decisions

1. **Use the existing pending offer file, extended with a mode and choice.**
   This keeps the answer on the next prompt, prevents an unprompted write, and
   avoids introducing another state store. An allowed mismatch is recorded for
   the current session/lane pair so later prompts warn but do not repeatedly
   block; changing either name invalidates that allowance.

2. **Present numbered choices rather than interpreting free-form yes/no.**
   The guard prints `1` allow, `2` adjust lane to session, and `3` adjust
   session to lane. Only the exact numbered answer is acted on; invalid input
   leaves the offer pending and blocks that answer prompt.

3. **Reuse the established move and pane-typing mechanics.**
   Choice 2 renames the tmux window first, runs `lane-start --no-launch`, binds
   the current UUID to the destination row, and marks the source row moved.
   Choice 3 types `/rename <lane>` into the verified pane. The answer prompt
   is consumed in both repair cases so the repair lands before work resumes.

4. **Keep safety failures blocking.**
   The guard continues to return exit 2 when it cannot read the workspace,
   tmux, session record, or register, and for duplicate/superseded transcripts.
   Only a readable, current lane/session name mismatch reaches the three-choice
   offer.

5. **Use the same-agent PAUSED transcript only when the row-last transcript is
   absent.** The row remains the first source. If its last UUID has no
   transcript, the last PAUSED record names agent `claude`, and that record's
   transcript exists, `lane-start` resumes that exact UUID and appends it to
   the end of the session cell before the RESUMED status. A live session in
   the current window still wins, and an agent mismatch never borrows another
   agent's transcript.

## Risks / Trade-offs

- [Risk] Allowing a mismatch can make cross-session addressing less obvious.
  → The choice is explicit, scoped to the current pair, and emits a warning on
  every later prompt while the mismatch remains.
- [Risk] A pane may stop accepting `/rename` keys.
  → Reuse the existing verified-pane result handling and print the manual
  `/rename` command while keeping the offer/repair state visible.
- [Risk] Moving a lane can race with a register update.
  → Continue using `lane-start` and the existing published-row anchors; do not
  add a direct register rewrite.
- [Risk] An old handoff could point at a superseded transcript.
  → Consult it only after the row-last transcript is absent, require the same
  recorded agent, retain duplicate-holder checks, and restore the selected ID
  through the existing anchored session-cell writer.
