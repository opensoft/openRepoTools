## Why

Profile-only Claude launches currently encounter the lane name guard even though the operator chose to work without a lane. The guard must honor that launch mode for the lifetime of the process.

## What Changes

- Skip the prompt guard when the launcher supplies `CLAUDE_NO_LANE=1`.
- Keep the hook installed and enforce existing checks for every other value.
- Document the process environment contract with workBenches.
- Run the expanded guard and repository hygiene checks in a focused CI job using the canonical serialized wrapper.

## Capabilities

### New Capabilities

- `profile-only-lane-guard`: per-session exemption for a launch without a lane.

### Modified Capabilities

## Impact

`lanes-edit.sh guard`, lane documentation and regression coverage. workBenches supplies the marker. Implementation handoff: `specs/002-skip-no-lane-guard/`.
