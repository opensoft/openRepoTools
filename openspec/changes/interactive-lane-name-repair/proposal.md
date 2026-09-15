## Why

The prompt guard currently blocks a lane when the Claude session name and the
lane/register name drift, even when the operator can identify and repair the
drift safely. A single accidental rename can therefore strand an otherwise
valid working session; the guard needs an explicit, auditable repair choice.

## What Changes

- Replace the hard block for a recoverable lane/session name mismatch with a
  one-prompt repair offer.
- Offer exactly three explicit choices: allow this lane, change the lane
  binding to the session name, or rename the session to the lane name.
- Make the session-to-lane choice perform `/rename <lane>` in the active
  Claude pane before allowing work to continue.
- Preserve blocking for ambiguous, unreadable, superseded, or otherwise
  unsafe lane identity states.
- When a lane row ends in a harness UUID that has no transcript, recover the
  exact Claude transcript from the same agent's last PAUSED record instead of
  launching Claude's title-filtered resume picker.

## Capabilities

### New Capabilities

- `interactive-lane-name-repair`: explicit repair choices for recoverable
  lane/session name drift.

### Modified Capabilities


## Impact

The `lanes-edit.sh guard` `UserPromptSubmit` hook, its pending-answer state,
the lane/register update helpers, `lane-start`'s exact transcript selection,
the active-pane rename path, and the shell tests for lane helper behavior. The
installed hook command and existing safe failure behavior remain unchanged.
