## Purpose

Allow Claude sessions launched without a lane to submit prompts while lane sessions retain their normal identity checks.

## ADDED Requirements

### Requirement: Respect the session launch mode

The prompt guard SHALL silently return status 0 when `CLAUDE_NO_LANE=1`, including when lane identity cannot be read. It SHALL keep existing enforcement for all other values and SHALL NOT alter profile hook settings or lane records for the exempt prompt.

#### Scenario: Profile session inside the projects root

- **WHEN** a prompt arrives from a process launched with `CLAUDE_NO_LANE=1` inside the projects root
- **THEN** it is allowed without consulting tmux or requiring a lane row

#### Scenario: Unsupported marker value

- **WHEN** the marker is absent, empty, `0`, or `true` and no lane workspace can be read
- **THEN** the guard returns status 2 through its existing refusal path

### Requirement: Limit the exemption to the prompt guard

Other lane commands SHALL retain their existing validation even when `CLAUDE_NO_LANE=1` is present.

#### Scenario: Registry read with no workspace

- **WHEN** a registry read runs with `CLAUDE_NO_LANE=1` and no workspace configuration
- **THEN** it still refuses the missing workspace
