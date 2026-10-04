# Planning evidence and decisions

October 3 inspection and October 4 refresh used the pinned standard's `AGENTS.md`, adoption
implementation, generated CLI reference and placement policy; root installer,
CI and fixture code; local branch/worktree state; read-only GitHub PR metadata.
No external writes, repositories, installation or migration occurred.

| Finding | Decision / execution consequence |
| --- | --- |
| October 4 main still matches GitHub at `82ecebe` (79 commits), 58 tracked paths and one standard gitlink | Regenerate/check the current main mapping; #61 and #146 remain included without replay. |
| Classifier treats shipped Markdown skills/commands as specification | Override to code with written reasons; these are installation payloads. |
| Original contract is the implementation's upstream dependency lock | Keep code pin/gitlink/.gitmodules together; generated assembly pins are separate. |
| `.specify` and agent directories are ignored local scaffolding | Preserve local config separately and regenerate root workflow after adoption. |
| Six current worktrees/local branches; main and all feature checkouts clean before refresh edits; open PRs #134/#121/#97 | Keep retired `002`/`003`, lclaude, detached, claim-takeover and #146 checkouts out of replay. Clean status alone does not complete preservation Gate A. |
| Feature 001 advanced to clean `3c26041`, committing broker/task-recovery work and restoring rollover/workspace packets | Preserve its complete branch delta and restored governance/ideation; remove the stale requirement to capture the previous dirty files as uncommitted work. |
| Feature 001 now selects required local Omnigent for `lclaude → oclaude → profile launch`, with implementation/qualification pending | Carry launcher contract, FR-047/T063–T065, LS custody/input fences and separate factory-broker gates; keep wrapper ownership in workBenches and transport ownership in Omnigent. |
| Non-draft #134 advanced to `11037f0` and has a clean sibling worktree | Carry code installer/resolver/preflight/timeout/test changes and spec manual if unmerged; regenerate baseline if it lands before freeze. |
| Two remaining preservation refs have no local worktrees | Review their history as recovery evidence; do not treat them as active writers or require recreation. |
| Estate status refuses this manifest-free single repository | Relay no-estate refusal; use local Git and read-only GitHub observations now, then estate status after adoption. |
| Installer fetches bare paths from `openRepoTools` and local sibling payloads | Preserve public root entry point and bind every payload to one code pin. |
| Tests conflate repo, spec and dependency paths | Introduce explicit checkout context and composed CI, preserving nested-pin tests. |
| `git-filter-repo` absent in inspected bench | Execution prerequisite; no software installation was performed for planning. |
| Standard plan `check` covers names/paths, not execution correctness | Local bare-remote rehearsal must cover existing submodule and blob accounting. |

Existing-submodule behavior, exact installation resolver implementation and
live feature replay are pending measured execution tasks, not assumed successes.
The final creation approval also confirms proposed public visibility.
