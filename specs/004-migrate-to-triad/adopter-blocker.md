# Pinned adopter refuses an existing submodule split

**Upstream:** opensoft/openRepoShape, pinned revision
`39d5c986fcfac1a160474bfe91c5f1c37fccc72c`.
**Consumer:** openRepoTools main
`daed20957f2dd2f22cca24053bb5bc8636ff6b3f`.
**Measured:** October 4, 2026; disposable local remotes only.

The reviewed mapping moves the existing `.gitmodules` together with
`upstream/openRepoShape` and its dependency contract into code. Plan `check`
passes. Both filtered legs are created, then assembly mounting returns 2:

```text
REFUSED a git or gh command failed. THE EXACT COMMAND WAS:
    git -c protocol.file.allow=always submodule add -q <local-spec-worktree> spec
    (in <local-assembly-worktree>)
    exit 128
--- output ---
fatal: please make sure that the .gitmodules file is in the working tree
--- end output ---
```

`adopt-project.py`'s `_mount_the_legs` (line 1201 at this pin) removes moved
paths with `git rm`, then immediately invokes `git submodule add`. `.gitmodules`
is among the moved files; its tracked deletion is still staged when the new
submodule registration is attempted. The root index contains only the six
original front-door files at refusal. The generated assembly registrations
have not been created. Git's missing-file guard is the observed failure; no
assumption about nested dependency correctness substitutes for this evidence.

## Reproduction for upstream review

Use a fresh isolated clone of the consumer at the recorded commit, a copy of
the resolved [adoption plan](../../openspec/changes/migrate-to-triad/adoption-plan.yaml),
git-filter-repo 2.47.0, and empty disposable local directories:

```sh
python3 <pinned-shape>/adopt-project.py check \
  --source <isolated-source> --plan <copied-plan>
python3 <pinned-shape>/adopt-project.py execute \
  --source <isolated-source> --plan <copied-plan> \
  --local-remote-dir <fresh-local-remotes> \
  --work-dir <fresh-local-work-dir> --yes
```

The yes here covers the reviewed local test only. Never use the live consumer
as `--source` for this reproduction: local mode still pushes an adoption
branch to its source clone if execution reaches that step.

Expected behavior: preserve the original registration in code, create fresh
assembly registrations for spec/code, complete source accounting, and retain
the dependency gitlink/contract identity. The source repository must remain
unchanged if execution refuses.

The upstream regression should cover a populated existing submodule, its
registration explicitly assigned to code, the generated assembly registrations,
recursive clone/bootstrap, exact mode/object accounting, and failure recovery.
Also cover partial registration ownership and no-existing-module inputs so a
fix cannot silently erase retained registrations or create duplicate owners.

No upstream issue or PR was published. No patch was applied to the pinned
checkout or failing candidate. Resolve through the owning repository's normal
review, then bump to a commit on its main and recompute the dependency digest.
Repeat the consumer rehearsal with fresh remotes. Gate B remains blocked by
this refusal even though extraction content was independently verified.

Private execution log SHA256:
`ca2a11775ca3b6d179fc038436a28090f65b05feb2a1611d4578b315733b5168`.
