# Planning evidence and decisions

October 3, 2026 inspection used the pinned standard's `AGENTS.md`, adoption
implementation, generated CLI reference and placement policy; root installer,
CI and fixture code; local branch/worktree state; read-only GitHub PR metadata.
No external writes, repositories, installation or migration occurred.

| Finding | Decision / execution consequence |
| --- | --- |
| Source main advanced to `82ecebe` (79 commits), still 58 tracked paths and one standard gitlink | Regenerate the mapping from the source; #61 and #146 are included without replay. |
| Classifier treats shipped Markdown skills/commands as specification | Override to code with written reasons; these are installation payloads. |
| Original contract is the implementation's upstream dependency lock | Keep code pin/gitlink/.gitmodules together; generated assembly pins are separate. |
| `.specify` and agent directories are ignored local scaffolding | Preserve local config separately and regenerate root workflow after adoption. |
| Cleanup initially left five worktrees; reopening planning made six, then merged #146's checkout was removed; now five worktrees and open PRs #134/#121/#97 | Reduce the active replay queue; do not recreate retired `002`/`003`, lclaude, detached, claim-takeover or #146 checkouts. |
| Feature 001 at `c0b571c` still has dirty/untracked broker/task-recovery work | Preserve its current complete delta/content, not the previous snapshot. |
| Draft #134 and preservation refs have no local worktrees | Review retained branch history without treating it as an active writer or requiring recreation. |
| Estate status refuses this manifest-free single repository | Relay no-estate refusal; use local Git and read-only GitHub observations now, then estate status after adoption. |
| Installer fetches bare paths from `openRepoTools` and local sibling payloads | Preserve public root entry point and bind every payload to one code pin. |
| Tests conflate repo, spec and dependency paths | Introduce explicit checkout context and composed CI, preserving nested-pin tests. |
| `git-filter-repo` absent in inspected bench | Execution prerequisite; no software installation was performed for planning. |
| Standard plan `check` covers names/paths, not execution correctness | Local bare-remote rehearsal must cover existing submodule and blob accounting. |

Existing-submodule behavior, exact installation resolver implementation and
live feature replay are pending measured execution tasks, not assumed successes.
The final creation approval also confirms proposed public visibility.
