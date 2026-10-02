## Context

See proposal.md. workBenches selects profile and lane modes per launch; profile settings can be used concurrently by both modes.

## Goals / Non-Goals

Honor the process's no-lane marker without editing shared profile settings. Other lane checks and commands retain their existing behavior.

## Decisions

The `guard` handler exits silently with status 0 for the exact environment value `CLAUDE_NO_LANE=1`, before reading hook input or validating lane identity. All other values use the existing enforcement path. Changing profile settings would affect concurrent lane sessions, so the exemption belongs to the child process environment.

## Risks / Trade-offs

An inherited marker could exempt a later lane launch. workBenches clears it for explicit lane requests and lane handoff; only explicit `--no-lane` wins over those requests. Existing Claude processes keep their launch environment and must be relaunched to change mode.

## Migration Plan

Install the marker-aware guard with the normal openRepoTools installation path and install the matching workBenches launcher. Revert both changes to roll back. Do not edit the pinned workBenches vendor copy directly.
