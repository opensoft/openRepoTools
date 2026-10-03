# Migration records

These records describe migration evidence; they confer no runtime ownership
and never replace lane claims, workspace pointers or the standard's pins.

| Record | Required facts |
| --- | --- |
| Adoption plan | Source repository/commit, standard revision evidence, names/visibility, reasoned path owners, follow-ups, coverage result and approval binding. Relative paths only in shared artifacts. |
| Work inventory | Observation time, branch/PR/head identity, detached status, readable/dirty indication and snapshot limits. Public `inventory.json` omits host paths and private work. |
| Private preservation receipt | Exact original worktree/binding, branch refs, staged/unstaged/untracked/ignored content digests, backup location and verified restore result. Stored host-locally or in existing private WIP storage. |
| Feature migration receipt | Original merge base/head and captured content; spec/code/root file mapping; resulting branches/commits/checksums; conflict/replay decisions, roles and approval. |
| Composed candidate evidence | Root/spec/code/standard commits, pin/digest consistency, installer payload revision, platform/CI/rehearsal/rollback results and outstanding findings. |
| Cutover approval | Actual candidate/baseline, visibility, leg names, preservation/rehearsal references, lane breakpoints and authorized actions. |

Generated `elected_by`/date metadata and `execution_authorized: false` in the
preliminary plan are informational. The adoption script does not enforce the
custom planning flag; the operator must not call real `execute` before the
reviewed approval gate. An inventory snapshot is never proof of backed-up work.
