## ADDED Requirements

### Requirement: Recoverable name drift offers explicit choices

When the guard can read a current lane row, the current transcript, the tmux
window, and the live session name, and the lane name differs from the session
name, it MUST warn and offer exactly these choices: `1` explicitly allow the
current lane/session mismatch, `2` adjust the lane binding to the session name,
or `3` adjust the session name to the lane name.

#### Scenario: Mismatch is offered instead of silently blocking

- **WHEN** the current window is lane `repo-1`, its latest transcript belongs to
  that row, and the live session is named `repo-2`
- **THEN** the guard prints the three numbered choices and records a pending
  answer without changing the window, session, or register

#### Scenario: Invalid answer remains safe

- **WHEN** the pending mismatch offer receives an answer other than `1`, `2`,
  or `3`
- **THEN** the answer prompt is refused, the offer remains pending, and no
  rename or register write occurs

### Requirement: Explicit allow is scoped and warning-only

When the operator selects `1`, the guard MUST consume that answer prompt and
retain an explicit allowance for the current lane/session pair. While that pair
remains unchanged, later prompts MUST pass with a warning and MUST NOT require
another repair choice. If either name changes, the allowance MUST no longer
apply.

#### Scenario: Allow permits the current work

- **WHEN** the operator answers `1` to a pending mismatch offer
- **THEN** the guard consumes the answer, records the allowance, and reports
  that later prompts will pass with a warning for the current lane/session pair

#### Scenario: Allow is invalidated by a changed name

- **WHEN** an explicitly allowed session or lane name changes
- **THEN** the guard presents the three choices again rather than silently
  carrying the old allowance forward

### Requirement: Lane-to-session repair moves the lane binding

When the operator selects `2`, the guard MUST adjust the active lane binding to
the session's lane name using the existing lane-start/register mechanics. It
MUST rename the tmux window before running the binding operation, preserve the
current transcript UUID in the destination row, mark the source lane as moved,
and consume the answer prompt.

#### Scenario: Existing destination lane is selected

- **WHEN** the operator answers `2` and the session name identifies an existing
  lane
- **THEN** the window and register bind to that destination lane, the current
  UUID is recorded there, the old lane records the move, and the answer prompt
  is consumed

#### Scenario: Destination cannot be derived safely

- **WHEN** the session name cannot provide the directory or lane arguments
  required by `lane-start`
- **THEN** choice `2` refuses without writing or renaming and prints the
  operator-supplied command needed to complete the move

### Requirement: Session-to-lane repair renames the session

When the operator selects `3`, the guard MUST type `/rename <lane>` into the
verified active Claude pane, consume the answer prompt, and report whether the
rename was typed successfully. It MUST NOT silently change the register.

#### Scenario: Pane accepts the rename

- **WHEN** the operator answers `3` and the active pane accepts tmux input
- **THEN** `/rename <lane>` is typed, the mismatch repair prompt is consumed,
  and the next prompt can be evaluated with the session name aligned

#### Scenario: Pane cannot accept the rename

- **WHEN** the operator answers `3` but the active pane cannot be verified or
  does not accept tmux input
- **THEN** no register write occurs, the guard reports the manual
  `/rename <lane>` command, and the mismatch offer remains available

### Requirement: Unsafe identity states remain blocked

The guard MUST continue to refuse with its blocking exit status when the
workspace, tmux window, live session record, register row, or transcript
identity cannot be verified, or when the transcript is superseded or duplicated.

#### Scenario: Register or session cannot be read

- **WHEN** the guard cannot establish the current lane/session/register triple
- **THEN** it refuses the prompt and does not offer a permissive choice

### Requirement: Lane launch recovers an exact same-agent transcript

When the lane row's last UUID has no transcript, but the lane's last PAUSED
record names the same agent and an existing transcript UUID, `lane-start` MUST
resume that exact transcript rather than pass the lane name to Claude's
title-filtered resume picker. It MUST restore the selected UUID to the end of
the session cell using the existing anchored writer before recording RESUMED.

#### Scenario: Harness UUID does not name a transcript

- **WHEN** a Claude lane's row ends in UUID `new`, no `new.jsonl` exists, and
  the same lane's last PAUSED record names existing transcript UUID `old`
- **THEN** the launch command contains `--resume old`, never `--resume <lane>`,
  and the row's session cell ends in `old` for the next launch

#### Scenario: Current-window evidence remains authoritative

- **WHEN** the current window contains a live session being bound to the lane
- **THEN** `lane-start` does not replace that live session with a transcript
  from an older PAUSED record
