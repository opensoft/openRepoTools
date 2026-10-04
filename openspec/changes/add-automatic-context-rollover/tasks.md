## 1. Prerequisite and Contract Decisions

- [ ] 1.1 Confirm the landed crash-consistent lane lifecycle exposes locked, generation-fenced operations for requesting, beginning, failing, and completing an automatic rollover.
- [ ] 1.2 Define the session snapshot schema and strict freshness rule, including transcript identity and malformed-input behavior.
- [ ] 1.3 Define the user-owned automatic-rollover configuration schema, default 65% threshold, explicit override, and one-launch disable precedence.
- [ ] 1.4 Verify the supported Claude Stop-hook continuation response and document the warning-only fallback for runtimes that cannot request another semantic handoff turn safely.

## 2. Signal and Policy Tests

- [ ] 2.1 Add red-first tests distinguishing context-window percentage from profile rate-limit percentages and covering values below, at, and above 65%.
- [ ] 2.2 Add red-first tests for missing, stale, malformed, and transcript-mismatched context snapshots.
- [ ] 2.3 Add red-first tests proving automatic rollover is opt-in, uses 65% when enabled without an override, honors an explicit threshold and one-launch disable, and cannot be enabled by repository-controlled content.
- [ ] 2.4 Implement the minimum snapshot and policy readers that satisfy the signal and configuration tests while remaining compatible with macOS bash 3.2.

## 3. Completed-Turn Controller

- [ ] 3.1 Add red-first tests proving the controller acts only on a completed main-session turn and ignores active/re-entered hooks and subagent-stop events.
- [ ] 3.2 Add red-first tests for canonical lane, transcript, pane, live-owner, generation, and `RUNNING` admission, including every ambiguous or conflicting refusal path.
- [ ] 3.3 Add red-first tests proving the atomic lane-generation request latch permits one request and rejects duplicate or stale-generation requests.
- [ ] 3.4 Implement the completed-turn controller and atomic request states without terminal keystroke injection or a continuously polling service.
- [ ] 3.5 Emit supported hook feedback that requests the semantic handoff with `--restart`, and emit warning-only output when continuation is unsupported or admission fails.

## 4. Semantic Handoff and Recovery Integration

- [ ] 4.1 Extend the handoff skill's machine-consumed invocation path to accept an automatic-rollover operation ID while preserving manual `/ctx` behavior.
- [ ] 4.2 Begin `SWAPPING` only after the handoff operation acquires the current lane generation and transition lock supplied by the prerequisite change.
- [ ] 4.3 Record `handoff-started`, `completed`, and `failed` request outcomes without allowing a stale request to finalize a newer lane generation.
- [ ] 4.4 Add failure-path tests proving snapshot, ownership, hook, semantic handoff, and transition failures leave the current pane alive and never retry in a Stop-hook loop.
- [ ] 4.5 Add an end-to-end fake-tmux scenario proving a successful automatic request produces the same durable handoff, `SWAPPED` state, fresh lane launch, and first-prompt handoff block as manual `/ctx`.

## 5. Installation and Operator Controls

- [ ] 5.1 Add an operator command or extend the existing usage-guard command to enable, disable, inspect, and set the automatic context threshold in user-owned configuration.
- [ ] 5.2 Install and remove the Stop-hook entry idempotently for bare Claude and shared-profile configurations without disturbing unrelated hooks.
- [ ] 5.3 Update command help and lane documentation to explain the 65% default, completed-turn timing, opt-in boundary, fallback warnings, and manual `/ctx` escape hatch.
- [ ] 5.4 Add installer tests proving every configured profile resolves the shared controller and that reinstall and rollback preserve unrelated settings.

## 6. Verification and Delivery

- [ ] 6.1 Run targeted hook, installation, lane-transition, and fake-tmux tests, including concurrent and stale-generation cases.
- [ ] 6.2 Run `tests/run.sh` through the repository's serialized test wrapper and resolve all regressions.
- [ ] 6.3 Verify scripts parse and behavior tests pass under macOS bash 3.2 constraints.
- [ ] 6.4 Perform a warning-only canary with real session snapshots before enabling automatic action, recording requested, refused, failed, and completed outcomes.
- [ ] 6.5 Enable one explicit test lane at 65%, verify a complete automatic rollover and manual disable path, then document rollback evidence.
