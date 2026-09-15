## 1. Guard state and interaction

- [x] 1.1 Extend the pending name-drift offer state to distinguish the three numbered choices and an explicit allow for the current lane/session pair.
- [x] 1.2 Replace recoverable lane/session mismatch hard-lock behavior with the numbered warning offer while retaining fail-closed handling for unsafe identity states.
- [x] 1.3 Implement choice `1` as a scoped warning-only allowance that is invalidated when either compared name changes.
- [x] 1.4 Implement choice `2` using the existing window-first `lane-start --no-launch` move path and current UUID/register anchoring.
- [x] 1.5 Implement choice `3` by typing `/rename <lane>` into the verified pane, with manual fallback when typing fails.

## 2. Verification and documentation

- [x] 2.1 Add shell coverage for the three choices, invalid answers, scoped allow, lane-to-session moves, and session-to-lane `/rename` typing.
- [x] 2.2 Add regression coverage proving unreadable, superseded, duplicate, and ambiguous identity states still block.
- [ ] 2.3 Run the canonical `tests/run.sh` focused tests and update user-facing lane documentation for the new prompt behavior.

## 3. Exact lane relaunch

- [x] 3.1 Diagnose the immediate `pclaude --lane openRepoTools-3 max001` exit against the installed helper, register row, PAUSED record, and transcript files.
- [x] 3.2 Make `lane-start` recover the same agent's exact PAUSED transcript when the row-last UUID has no transcript, preserving live-window and duplicate-holder fences.
- [x] 3.3 Restore the recovered UUID to the end of the session cell through the anchored writer before recording RESUMED.
- [x] 3.4 Add regression coverage for exact-ID recovery and exclusion of the title picker.
- [x] 3.5 Install the verified helper and confirm the real lane's dry-run launch argv.
