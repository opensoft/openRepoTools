# Feature Specification: Skip the guard for no-lane sessions

**Feature Branch**: `002-skip-no-lane-guard`
**Created**: 2026-09-30
**Status**: Approved for implementation by the user's request
**Input**: Implement the agreed per-session no-lane hook exemption.

## User Scenarios & Testing

### User Story 1 - Work without a lane (Priority: P1)

A profile session submits prompts even inside a projects directory with no tmux or readable lane workspace. Test the guard with the launch marker and missing lane infrastructure.

### User Story 2 - Keep lane enforcement (Priority: P1)

A lane session must still satisfy the existing identity checks. Test absent and unsupported marker values against the same missing-workspace fixture and expect status 2.

## Requirements

- **FR-001**: Exact `CLAUDE_NO_LANE=1` bypasses only the prompt guard, silently and before reading hook input.
- **FR-002**: Absent or unsupported values retain the existing checks.
- **FR-003**: Exempt prompts cause no lane record or tmux mutation.
- **FR-004**: Keep shared profile hooks installed.

## Success Criteria

- Exempt prompt fixtures return status 0 with empty stdout and stderr.
- Non-exempt fixtures refuse unreadable lane identity with status 2.
- Other lane commands still refuse missing workspace configuration.
