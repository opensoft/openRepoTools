# Consumer-side reads for T006/T007/T008: what outside openRepoTools depends on its layout or its installer

Read at 2026-10-07T10:04:44Z–11:07:10Z by lane openRepoTools-2's writer, under #186, from ff6f6a7. An API-side error cut the run, and it resumed at 11:03:49Z, when every head was checked again.

HEADs read:

- workBenches `7fd01e30816b2f96e20e913208bd07b8682274af`. Dirty: yes, one modified submodule pointer, `sysBenches/cloudBench`. Every read used committed objects at that sha.
- brett-wip `ab88a10347fb605588643e7ea2e528217dab9a67`. It had 215 untracked entries, which were not read. HEAD moved to `466c3a8` by 11:03:49Z and to `349caef` by 11:07:10Z. The line numbers below were checked again at `ab88a10`.
- openRepoShape 7f84ca4 (`7f84ca42ca86a8902928345109d2bf6bad87bd91`).
- openRepoTools main c4864ac (`c4864ac5e59db49d01f638a80ed38daf1d788182`).

The plan files are read at `ff6f6a7c7b7921ca1e0b0234e898900f98532366` from lane 2's worktree. Brett Heap's 004 worktree was not entered.

2026-10-07, relayed by the coordinator and not read here: Brett Heap opened PR #187 (planning branch `004-migrate-to-triad` at ff6f6a7 → main; lane 1 lands it). He also confirmed the leg names `openRepoTools-spec` / `openRepoTools-code`, both public, as recorded on #186.

This document records facts only. "Covered" means installer-design.md at ff6f6a7 names the case; `l.N` cites that file. "(inferred)" marks a statement that was worked out rather than read.

## Split as read from adoption-plan.yaml at ff6f6a7

- **root (6 files):** `.gitattributes` (l.41), `.gitignore` (l.57), `AGENTS.md` (l.75), `CLAUDE.md` (l.83), `LICENSE` (l.91), `README.md` (l.99).
- **spec (18 files):** `docs/` (l.145), `openspec/` (l.241), `specs/` (l.288).
- **code (40 files):**
  - `.github/`
  - `.gitmodules`, `upstream/`
  - the whole `contracts/` directory (l.136–144). Its `rule:` is `spec-governance`, but its `resolution:` puts it in code, because at the baseline it holds only `openreposhape-pin.yaml`.
  - `commands/`, `skills/`, `repos.tsv`, `tests/`
  - the executables: `claude-current`, `claude-restart-check`, `lane`, `lane-end`, `lane-handoff`, `lane-rename`, `lane-start`, `lanes`, `lanes-edit.sh`, `link-estates`, `openRepoTools`, `park`, `resume`, `status`
- **Baseline:** `daed209` with 64 files (l.13–14). Main c4864ac tracks 100. Three of its top-level paths are under no mapped entry: `lane-worktrees`, `lanes-index` (both are in `INSTALLABLES` at `openRepoTools:338`) and `ideation/` (12 files). plan.md:58 puts "feature 001's retained `ideation/`" in spec.
- **Planned additions at the root** (not in the mapping):
  - the assembly `openRepoTools` entry point (installer-design.md:9–14; plan.md:64–67)
  - generated manifest, Makefile, validators and assembly pins (plan.md:57)
  - the shape's `validate.yml` (adoption-plan.yaml:53)

## Exact commands

Plan files (lane 2's worktree, same commit as the planning branch):

```sh
date -u +%Y-%m-%dT%H:%M:%SZ
git -C /workspace/projects/.lane-worktrees/openRepoTools-2/triad-reads rev-parse HEAD
git -C /workspace/projects/.lane-worktrees/openRepoTools-2/triad-reads status --short
cat -n /workspace/projects/.lane-worktrees/openRepoTools-2/triad-reads/openspec/changes/migrate-to-triad/adoption-plan.yaml
cat -n /workspace/projects/.lane-worktrees/openRepoTools-2/triad-reads/specs/004-migrate-to-triad/installer-design.md
cat -n /workspace/projects/.lane-worktrees/openRepoTools-2/triad-reads/specs/004-migrate-to-triad/tasks.md
cat -n /workspace/projects/.lane-worktrees/openRepoTools-2/triad-reads/specs/004-migrate-to-triad/plan.md
cat -n /workspace/projects/.lane-worktrees/openRepoTools-2/triad-reads/specs/004-migrate-to-triad/spec.md
```

openRepoTools main (read-only; no fetch):

```sh
git -C /workspace/projects/openRepoTools rev-parse main c4864ac
git -C /workspace/projects/openRepoTools ls-tree --name-only c4864ac
git -C /workspace/projects/openRepoTools ls-tree -r --name-only c4864ac | wc -l                                   # 100
git -C /workspace/projects/openRepoTools ls-tree -r --name-only daed20957f2dd2f22cca24053bb5bc8636ff6b3f | wc -l   # 64
git -C /workspace/projects/openRepoTools diff --name-status daed20957f2dd2f22cca24053bb5bc8636ff6b3f c4864ac
git -C /workspace/projects/openRepoTools ls-tree c4864ac upstream/openRepoShape
git -C /workspace/projects/openRepoTools show c4864ac:.gitmodules
git -C /workspace/projects/openRepoTools ls-tree -r --name-only c4864ac contracts
git -C /workspace/projects/openRepoTools show c4864ac:openRepoTools > <scratchpad>/openRepoTools.c4864ac
grep -n 'raw.githubusercontent\|gh api\|OPENREPOTOOLS_REPO\|OPENREPOTOOLS_REF\|^REPO=\|^REF=\|INSTALLABLES\|repos.tsv\|SCRIPT_DIR\|script_dir\|BASH_SOURCE\|\$0' <scratchpad>/openRepoTools.c4864ac
grep -n 'selfdir\|skills/\|commands/\|contracts/\|upstream/\|docs/\|^[a-z_]*() *{' <scratchpad>/openRepoTools.c4864ac
sed -n '1,135p;136,440p;955,1002p;1210,1222p;1285,1368p;1365,1400p;2490,2545p' <scratchpad>/openRepoTools.c4864ac
git -C /workspace/projects/openRepoTools grep -n 'raw.githubusercontent\|gh api repos/opensoft/openRepoTools\|bash -s -- --install\|OPENREPOTOOLS_REF\|OPENREPOTOOLS_REPO' c4864ac -- README.md AGENTS.md docs
git -C /workspace/projects/openRepoTools show c4864ac:repos.tsv
git -C /workspace/projects/openRepoTools show c4864ac:lanes-edit.sh | grep -n 'repos.tsv'
git -C /workspace/projects/openRepoTools show c4864ac:lanes-edit.sh | grep -n '\.lane-state'
git -C /workspace/projects/openRepoTools show c4864ac:lane-worktrees | grep -n 'inventor'
git -C /workspace/projects/openRepoTools show c4864ac:lane-worktrees | sed -n '2120,2128p;2164,2175p;2708,2716p;4808,4822p'
git -C /workspace/projects/openRepoTools show c4864ac:link-estates | grep -n 'handoffs\|PROJECTS\|projects/\|estate'
git -C /workspace/projects/openRepoTools show c4864ac:.gitignore
for c in 2fb854f 5eb3d5f 500687c c4864ac; do git -C /workspace/projects/openRepoTools show $c:openRepoTools | sha256sum; done
git -C /workspace/projects/openRepoTools show c4864ac:lane-worktrees | sha256sum
git -C /workspace/projects/openRepoTools show c4864ac:lanes-edit.sh | sha256sum
ls -la /workspace/projects/openRepoTools
git -C /workspace/projects/openRepoTools status --porcelain=v1 --ignored
cat /workspace/projects/openRepoTools/.git/info/exclude
stat -c '%y' /workspace/projects/openRepoTools/.git/index   # 2026-10-07 04:28:20Z, before this read: the status call wrote no index
```

workBenches (read-only; committed objects at HEAD `7fd01e3`):

```sh
git -C /workspace/projects/workBenches rev-parse HEAD
git -C /workspace/projects/workBenches status --porcelain=v1                     # " M sysBenches/cloudBench"
git -C /workspace/projects/workBenches worktree list
git -C /workspace/projects/workBenches show HEAD:.gitmodules
git -C /workspace/projects/workBenches submodule status
git -C /workspace/projects/workBenches grep -n -i 'openRepoTools' HEAD -- .       # 939 lines; per-file counts via cut | sort | uniq -c
git -C /workspace/projects/workBenches grep -n -e '/workspace/projects/openRepoTools' -e 'openRepoTools-worktrees' -e '\.lane-worktrees' -e 'raw.githubusercontent.com/opensoft/openRepoTools' -e 'repos/opensoft/openRepoTools' -e 'github.com/opensoft/openRepoTools' -e 'opensoft/openRepoTools/' -e 'projects/openRepoTools' HEAD -- .
git -C /workspace/projects/workBenches show HEAD:devBenches/base-image/upstream-pin.yaml
git -C /workspace/projects/workBenches show HEAD:devBenches/base-image/Dockerfile | sed -n '136,285p'
git -C /workspace/projects/workBenches show HEAD:devBenches/base-image/update-upstream.py | sed -n '68,90p;886,960p'
git -C /workspace/projects/workBenches show HEAD:devBenches/base-image/files/estate/estate-commands-start
git -C /workspace/projects/workBenches show HEAD:devBenches/base-image/files/estate/workbench-entrypoint | grep -n 'estate-commands-start\|openrepotools\|exec'
git -C /workspace/projects/workBenches ls-tree -r --name-only HEAD devBenches/base-image/files/openrepotools
git -C /workspace/projects/workBenches show HEAD:scripts/setup-estate-commands.sh | grep -n -i 'openRepoTools\|vendor\|files/\|OPENREPOTOOLS\|INSTALLABLES\|skills/\|commands/\|755\|link-estates'
git -C /workspace/projects/workBenches show HEAD:scripts/setup-estate-commands.sh | sed -n '158,200p;276,330p;370,405p'
git -C /workspace/projects/workBenches show HEAD:setup.sh | sed -n '176,200p'
git -C /workspace/projects/workBenches show HEAD:README.md | sed -n '188p;190p'
stat -c '%y' /workspace/projects/workBenches/.git/index    # 2026-10-06 13:08:26Z, before this read
```

openRepoShape at 7f84ca4 (bare clone in lane 2's scratchpad, `ors-verify/ors.git`):

```sh
git -C <ors.git> log -1 --format='%H %cI %s' 7f84ca42ca86a8902928345109d2bf6bad87bd91
git -C <ors.git> grep -n -i 'openRepoTools' 7f84ca42ca86a8902928345109d2bf6bad87bd91 -- .        # 79 lines
git -C <ors.git> show "7f84ca42ca86a8902928345109d2bf6bad87bd91:openRepoShape" | grep -n 'raw.githubusercontent.com/opensoft/openRepoTools\|park and resume are installed by\|^[a-z_]*() *{'
git -C <ors.git> show "7f84ca42ca86a8902928345109d2bf6bad87bd91:openRepoShape" | sed -n '14,22p;76,86p;158,164p;268,290p'
git -C <ors.git> show "7f84ca42ca86a8902928345109d2bf6bad87bd91:README.md" | sed -n '400,410p;1355,1359p'
git -C <ors.git> show "7f84ca42ca86a8902928345109d2bf6bad87bd91:docs/cli.md" | sed -n '143,148p'
git -C <ors.git> show "7f84ca42ca86a8902928345109d2bf6bad87bd91:templates/workspace-root/AGENTS.md" | sed -n '28,34p;68,78p;88,95p'
git -C <ors.git> show "7f84ca42ca86a8902928345109d2bf6bad87bd91:scripts/shape_advisory.py" | sed -n '504,512p'
git -C <ors.git> show "7f84ca42ca86a8902928345109d2bf6bad87bd91:.github/workflows/tests.yml" | sed -n '268,282p'
git -C <ors.git> ls-tree -r --name-only 7f84ca42ca86a8902928345109d2bf6bad87bd91 | grep -i 'pin\|gitmodules'
git -C <ors.git> grep -n -i 'openRepoTools' 7f84ca42ca86a8902928345109d2bf6bad87bd91 -- contracts .gitmodules   # 0 lines
```

brett-wip (read-only; reads pinned at `ab88a10`):

```sh
git -C /workspace/projects/brett-wip rev-parse HEAD
git -C /workspace/projects/brett-wip status --porcelain=v1 | wc -l             # 215, all untracked
git -C /workspace/projects/brett-wip ls-tree --name-only HEAD
git -C /workspace/projects/brett-wip ls-tree HEAD lanes/
git -C /workspace/projects/brett-wip ls-tree -r --name-only HEAD | grep -i 'workspace.yaml'   # none
git -C /workspace/projects/brett-wip grep -n -e '/workspace/projects/openRepoTools' -e 'openRepoTools-worktrees' -e '\.lane-worktrees/openRepoTools' -e '~/projects/openRepoTools' -e 'projects/openRepoTools' ab88a10347fb605588643e7ea2e528217dab9a67 -- .   # 341 lines
git -C /workspace/projects/brett-wip show "ab88a10347fb605588643e7ea2e528217dab9a67:lanes/LANES.md" > <scratchpad>/LANES.md
grep -n '^| lane\|^| `openRepoTools' <scratchpad>/LANES.md
git -C /workspace/projects/brett-wip show "ab88a10347fb605588643e7ea2e528217dab9a67:lanes/log/openRepoTools-1.md"   # likewise -2, -3; sampled lines
git -C /workspace/projects/brett-wip show "ab88a10347fb605588643e7ea2e528217dab9a67:lanes/repos.tsv" | sha256sum
git -C /workspace/projects/brett-wip grep -n -e '\.local/bin/\(openRepoTools\|park\|resume\|status\|lane\|lanes\|lane-handoff\|lane-rename\|lanes-edit\.sh\|lane-start\|lane-end\|link-estates\|repos\.tsv\|claude-current\|claude-restart-check\|lanes-index\|lane-worktrees\)\b' -e 'share/openRepoTools' -e 'raw.githubusercontent.com/opensoft/openRepoTools' -e 'docs/README-lanes' -e 'openRepoTools-\(code\|spec\)' ab88a10347fb605588643e7ea2e528217dab9a67 -- .
git -C /workspace/projects/brett-wip grep -n -i -e 'openRepoTools' -e '\.local/bin' HEAD -- README.md AGENTS.md CLAUDE.md scripts/link-estates
ls -la /workspace/projects/xFactory/lanes-edit.sh /workspace/projects/xFactory/LANES.md
find /workspace/projects/.lane-state/openRepoTools-{1,2,3} -type f
grep -rn '^checkout:' /workspace/projects/.lane-state/openRepoTools-{1,2,3}
grep -rn '^path: /workspace/projects/openRepoTools/' /workspace/projects/.lane-state/openRepoTools-{1,2,3} | wc -l
```

`~/.agents` and the home directory:

```sh
ls -la /home/brett/.agents /home/brett/.agents/protocols /home/brett/.agents/templates
cat -n /home/brett/.agents/workspace.yaml
grep -rn -i -c 'openRepoTools' /home/brett/.agents/AGENTS.md /home/brett/.agents/protocols/*
grep -rn -e 'projects/openRepoTools' -e 'openRepoTools-worktrees' -e 'lane-worktrees/openRepoTools' -e 'raw.githubusercontent.com/opensoft/openRepoTools' -e 'repos/opensoft/openRepoTools' -e 'openRepoTools/installed.tsv' -e 'share/openRepoTools' -e 'openRepoTools/docs' -e 'docs/README-lanes' -e 'openRepoTools --install' -e 'openRepoTools/[A-Za-z]' /home/brett/.agents/{AGENTS.md,protocols,workspace.yaml,templates}   # 59 lines
grep -rln -i 'openRepoTools' /home/brett/.agents/skills /home/brett/.agents/templates /home/brett/.agents/.skill-lock.json   # none
cat /home/brett/.agents/protocols/project-agent-bootstrap.md
cat /home/brett/.agents/protocols/openspec-speckit-workflow.md
awk -F'\t' '{print NR, $1, $2, substr($3,1,12), $4}' /home/brett/.local/share/openRepoTools/installed.tsv   # 29 rows
sha256sum /home/brett/.local/bin/openRepoTools
grep -n 'lanes-edit\|lane-start\|xFactory\|openRepoTools\|\.local/bin' /home/brett/.claude/settings.json
grep -n -i 'openRepoTools' /home/brett/.claude/CLAUDE.md                          # none
grep -n -i 'projects/openRepoTools\|lane-worktrees\|raw.githubusercontent\|opensoft/openRepoTools\|docs/README-lanes' /home/brett/.claude/skills/{handoff,restart,lane-swap}/SKILL.md /home/brett/.claude/commands/*.md
sed -n '318,336p' /home/brett/.claude/skills/handoff/SKILL.md
```

## workBenches (`7fd01e3`)

| file:line | what it assumes today | what the split changes | installer-design.md coverage |
|---|---|---|---|
| `devBenches/base-image/upstream-pin.yaml:56-125` (and `:30-32`) | Source `openrepotools` = `opensoft/openRepoTools` at `b1015f4`. Its 21 `path:` rows (15 commands, `skills/<n>/SKILL.md` ×3, `commands/<n>.md` ×3) sit at the repository root. `path` is "the path in the source repository and the path under `vendor_dir`". | After the split those paths are root files of `openRepoTools-code`. In the assembly they sit behind the `code` gitlink, so a re-vendor against `opensoft/openRepoTools` at a post-split commit would not find them (inferred). The pin is still at `b1015f4` with 15 names; main has 17. | not covered |
| `devBenches/base-image/update-upstream.py:917-938, 941-956, 890-914` | `fetch_file` calls `gh api repos/<source>/contents/<path>?ref=<commit>`, falling back to `raw.githubusercontent.com/<source>/<commit>/<path>`. `fetch_tree_modes` reads `git/trees/<commit>?recursive=1`. `assert_on_default_branch` compares the commit with the source's default branch. All three expect blobs at those paths in that one repository. | Same as the row above. In the assembly tree, `code` is a gitlink, so neither the contents API nor tree modes reach the files (inferred). | not covered |
| `devBenches/base-image/Dockerfile:216-238` (comment `:148-156`) | `COPY files/openrepotools/<15 names>` to `/usr/local/bin`, then `chmod 0755`. The comment says openRepoTools pins openRepoShape "as a submodule in that repository". | The flat vendored layout is unchanged if it is vendored from the code leg, which keeps the same file names at its root (inferred from the mapping). The submodule and its pin move to `openRepoTools-code`. | not covered |
| `devBenches/base-image/Dockerfile:262-269` (`:240-249`) | Copies the whole vendored tree to `/usr/local/share/openrepotools`, then checks `openRepoTools`, `link-estates`, `skills/handoff/SKILL.md` and `commands/handoff.md` there. `--install` runs from that directory and copies every artifact "from its own directory". | That vendored `openRepoTools` must stay the code implementation, with siblings beside it. If the vendored file were an assembly entry point instead, it would have to delegate (inferred). | partial: l.9-14 ("Installed `openRepoTools` remains the code implementation"), l.40-48 ("legacy sibling behavior"). A vendored tree that is not a checkout is not named. |
| `devBenches/base-image/files/estate/estate-commands-start:134, 157-186` | Requires `$ESTATE_VENDOR_DIR/openRepoTools` to be executable. It `sed`-reads the one-line `INSTALLABLES=(`, `SKILLS=(` and `COMMANDS=(` arrays out of that file, derives `skills/<n>/SKILL.md` and `commands/<n>.md`, and installs nothing if any file is missing. | The file it parses has to keep those three one-line arrays. An entry point without them stops this step at `:177` ("could not read openRepoTools' own INSTALLABLES/SKILLS/COMMANDS lists") (inferred). | not covered |
| `estate-commands-start:239-240`; `scripts/setup-estate-commands.sh:378-381` | Runs `--install` with `OPENREPOTOOLS_REPO` and `OPENREPOTOOLS_REF` set to the sentinel `pinned-by-workBenches-no-fetch`, so that only sibling copies succeed. | The design resolves remote installs through `contracts/code-pin.yaml` at REPO/REF and refuses on transport or parse errors. A sentinel REPO with siblings and no pin is the legacy-sibling path. Today `wip_shape_ref` falls back to `main` when the pin fetch fails (`openRepoTools:2516`). | partial: l.30-33, l.47-48, l.83. The sentinel case is not named. |
| `scripts/setup-estate-commands.sh:162, 173, 266-268, 285, 312-321, 402, 434` | `TOOLS_SHIM` is the vendored file. `TOOLS_FILES` (15) is checked against the shim's `INSTALLABLES`, `SKILLS` and `COMMANDS` (`check_shim_list`). Every one of the 21 files must have a pin row. After `--install`, each placed file must `cmp` equal to its vendored copy at mode 755. | Depends on the vendored tree mirroring the source root and on the shim's arrays, the same as the two rows above. `check_shim_list` would now see 17 `INSTALLABLES` against 15 (a fact on main, not caused by the split). | not covered |
| `setup.sh:179-186, 208-209` | The host one-liner path: runs `scripts/setup-estate-commands.sh`, then `scripts/setup-workspace-repo.sh` (`openRepoTools wip init`). | Command names and help must hold. The route goes through the vendored tree (rows above). | partial: names and help, l.75. The vendored route is not named. |
| `scripts/setup-workspace-repo.sh:253-265, 271, 361` | Finds `$OPENREPOTOOLS_BIN_DIR/openRepoTools`, otherwise `PATH`. Asks `openRepoTools --help` whether `wip` is documented. Prints `update-upstream.py … --source openrepotools --at <commit> --yes`. | The installed name, the `--help` text and `wip init` must hold. The `--source openrepotools` advice points at the pin source in the first row. | covered: l.75, l.87 |
| `base-image/files/claude-profile:54-55, 557, 1649-1653`; `scripts/setup-claude-profiles.sh:213-224` | Matches the guard hook string byte for byte with openRepoTools's `GUARD_COMMAND` (cited as `openRepoTools:460-461`). Parses `openRepoTools --help`. Its install act is the string `openRepoTools --install`. Says `--install` owns the skill and command destinations. | Only installed names, help text, hook strings and destinations are read. The `openRepoTools:<line>` cites point into a file that moves to `code/`. | covered: l.59, l.75, l.86 |
| `README.md:80, 93, 155-156, 172, 188, 190` | "the lane tooling is installed from `opensoft/openRepoTools`" (`:188`); "places fifteen files" (`:190`). | The implementation moves to `openRepoTools-code`. The assembly keeps the slug and the one-liner (installer-design l.9-11). | not covered |
| `devBenches/base-image/files/openreposhape/openRepoShape:83, 280` (openRepoShape pin `71cf5de`) | A vendored copy of openRepoShape's raw-URL pointer `…/opensoft/openRepoTools/main/openRepoTools` (see the openRepoShape table). | The URL resolves only if the assembly root carries an `openRepoTools` file (inferred). | covered: l.9-11, l.75 |
| `devBenches/base-image/files/openrepotools/lane-handoff:813, 913`; `…/lanes-edit.sh:11412, 11939`; `…/skills/handoff/SKILL.md:292` | Vendored openRepoTools code (`b1015f4`) derives `<parent of lane dir>/.lane-worktrees/<lane>`. | The same as the code's own assumption (installer table, lane-worktrees row). It holds while lanes keep `dir /workspace/projects/openRepoTools` (inferred). | not covered |
| `devcontainer.test/test-setup-estate-commands.sh` (80 lines), `test-claude-profile-amendment-11.sh` (61), `test-setup-workspace-repo.sh` (52), and 8 more files under `devcontainer.test/` (57, including `README.md:70`); `test-claude-profile-lane-default.sh:282, 293`; `.github/workflows/speckit-git-bash.yml:19, 53` | The suites run or fake the vendored shim and its layout. `:282` and `:293` print `cwd /workspace/projects/openRepoTools`. The CI path filters are `devBenches/base-image/files/openrepotools/**`. | They follow whatever the vendored tree becomes. | not covered |
| `docs/claude-multi-account-profiles.md` (20 lines; `:314` cites `:1559`, `:1568`, `:1579` of openRepoTools `63a74af`), `openspec/**` and `specs/**` (52 lines), `base-image/files/claude-statusline-command.sh:477`, `scripts/wave-container-shell.sh:55`, `files/speckit-worktree/…/resume.sh:451, 465`, `devBenches/devcontainer.test/test-speckit-git-feature.sh:3425, 3487` | Prose that names `opensoft/openRepoTools`, its issues, or file:line inside it. | The slug stays as the assembly. The files named move to `code/`. | not covered |

## openRepoShape (`7f84ca4`)

openRepoShape pins nothing of openRepoTools.

| file:line | what it assumes today | what the split changes | installer-design.md coverage |
|---|---|---|---|
| `openRepoShape:279-280` (inside `install_commands`, which starts at `:250`): **the `--install` pointer line** | Prints `curl -fsSL https://raw.githubusercontent.com/opensoft/openRepoTools/main/openRepoTools`, piped to `bash -s -- --install`. That file must be the installer at the root of `opensoft/openRepoTools` on `main`. | The `openRepoTools` file moves to the code leg. The URL keeps resolving only through the planned assembly root entry point, which must delegate (inferred). | covered: l.9-14, l.75 (T007) |
| `openRepoShape:81-83` (`--help`) | The same line. | Same as the row above. | covered: l.9-11, l.75 |
| `README.md:404-408`, `docs/cli.md:145-147`, `docs/handbook.html:1542` (and `README.md:1357`, `docs/handbook.html:1646`) | The same line, byte for byte. | Same as the row above. | covered: l.9-11, l.75 |
| `tests/test_repo_hygiene.py:1202-1224`; `tests/test_openreposhape_command.py:55-57, 154, 272, 278` | `OPENREPOTOOLS_INSTALL` is pinned byte for byte in `openRepoShape`, `README.md` and `docs/handbook.html`. `:278` asserts that `--install` makes no request naming openRepoTools. | The tests hold only while the URL string is unchanged. | partial: l.10-11 keeps the one-liners. These tests are not named. |
| `templates/workspace-root/AGENTS.md:32, 71-76, 91-95`; `README.md:16, 18, 31, 58`; `handoffs/README.md:24`; `lanes/LANES.md:19, 40`; `lanes/log/README.md:4, 6`; `.gitattributes:8` | The template text that `openRepoTools wip init` copies into a WIP repository. It says the lane tooling (`lanes-edit.sh`, `lane-start`, `lane-end`, `test_lane_helpers.sh`, `link-estates`) and "README-lanes" live in `opensoft/openRepoTools`. | `docs/README-lanes.md` moves to `openRepoTools-spec`. The tools and `tests/` move to `openRepoTools-code`. | not covered: l.57 and l.87 cover only which template is selected, not its text |
| `scripts/shape_advisory.py:509` | `workspace.yaml` is "the shape `opensoft/openRepoTools`' `resume` reads". | `resume` moves to `code/`. The shape of `workspace.yaml` is unchanged (inferred). | not covered |
| `openRepoShape:19-25, 162`; `README.md:246, 1239`; `docs/handbook.html:495, 773, 782, 1538, 1739`; `AGENTS.md:429`; `.github/workflows/tests.yml:274`; the remaining test prose (for example `tests/test_openreposhape_command.py:17, 44`; `tests/test_repo_hygiene.py:70, 1190, 1230-1246`) | Provenance prose: `park` and `resume` are "opensoft/openRepoTools'". `AGENTS.md:429` says to read openRepoTools's `AGENTS.md` (which stays at the root). | The slug stays as the assembly. The named files move to `code/`. | not covered |
| `contracts/**` and `.gitmodules` | No line names openRepoTools (`git grep` returns 0). The pins found in the tree are template pins only. | Nothing; openRepoShape still pins nothing of openRepoTools. | n/a |

## brett-wip (`ab88a10`) and the host-local register state

| file:line | what it assumes today | what the split changes | installer-design.md coverage |
|---|---|---|---|
| `lanes/log/openRepoTools-1.md:2`, `openRepoTools-2.md:2`, `openRepoTools-3.md:59` … (52 lines: 11 + 11 + 30) | STARTED, RESUMED and PAUSED records carry `home opensoft/openRepoTools; estate openRepoTools; dir /workspace/projects/openRepoTools`. That is the directory a lane is relaunched in. | In-place adoption keeps the slug as the assembly. The checkout keeps holding only 6 root files plus `spec/` and `code/` (inferred). The executables a lane runs from the checkout root move to `code/`. | not covered (rebinding is plan.md:223-224, T018) |
| `lanes/log/openRepoTools-1.md:19`, `openRepoTools-3.md:291`, `:405`; `openXfactory-3.md:60`, `openXfactory-5.md:390`, `openxfactory-1.md:169` (+ `:253, 324, 411`) — 10 lines | Notes that name `.lane-worktrees/openRepoTools-1` and `-3`, `openRepoTools-cleanup-archives/…`, or `/workspace/projects/openRepoTools` as a working directory. | These are records of past acts. The paths stay valid while the assembly sits at the same path (inferred). | not covered |
| `lanes/LANES.md:1109` (`openRepoTools-3`), `:1303` (`openRepoTools-1`), `:2581` (`openRepoTools-2`) | The rows carry a handoff path `handoffs/openRepoTools/…` and no directory column (header `:76`). Only `:1109` names a checkout: `--dir /home/brett/projects/openRepoTools`. `/home/brett/projects` → `/workspace/projects`. | The handoff paths are in brett-wip and unaffected. The estate name `openRepoTools` stays. | not covered |
| `lanes/LANES.md:36` (and `:1305`); 12 `docs/README-lanes` lines in 9 files (first: `handoffs/openRepoTools/brief-lane-openRepoTools-1-2026-09-16.md:9`, `session-handoff-2026-09-16-lane-openRepoTools-1.md:33`, `lanes/log/openRepoTools-1.md:22`) | "the manual lives at `docs/README-lanes.md` in `opensoft/openRepoTools`". | `docs/` moves to `openRepoTools-spec`. | not covered |
| `lanes/repos.tsv:52` | The per-WIP alias override, read by `lanes-edit.sh` as `LANES_REPOS_TSV` (`lanes-edit.sh:2448`). It is byte-identical to the shipped table (sha256 `e4f9160a07ea…`). The only openRepoTools row is `openRepoTools` → `opensoft/openRepoTools`. | There are no `openRepoTools-spec` or `openRepoTools-code` rows, while the IRRS legs have them (`:29-30`, `:34-35`). The table header says an alias not in the table is refused, with a hint to spell owner/repo (shipped `repos.tsv:8`). | not covered |
| handoffs naming the checkout root `/workspace/projects/openRepoTools`: 145 lines (first: `handoffs/openRepoTools/migration-handoff-2026-10-06.md:15, 16, 32`) | Reads, cwd records and commands run in the monorepo checkout. | After cutover, the checkout at that path is the assembly. Code and docs are under `code/` and `spec/` (inferred). | not covered |
| `.lane-worktrees/openRepoTools-1` (50 lines), `-2` (3), `-3` (59) (first: `migration-handoff-2026-10-06.md:202`; `session-handoff-2026-10-02-lane-openRepoTools-2.md:19`; `session-handoff-2026-09-13-lane-openRepoTools-3.md:6`) | Lane worktrees are siblings of the lane directory, as monorepo worktrees. | Worktrees made after cutover would be worktrees of leg repositories. The triad protocol puts Speckit features under `<root>/worktrees/<NNN>/{spec,code}` (inferred from the protocol table below). | not covered |
| `openRepoTools-worktrees`: 16 lines (first: `migration-handoff-2026-10-06.md:204-206`) | The single-repository Speckit worktree root, `../<repo>-worktrees`. | It becomes `<assembly root>/worktrees/<NNN>/{spec,code}` (`openspec-speckit-workflow.md:114`). | not covered (plan.md:207-208, T006, T016-T018) |
| `~/projects/openRepoTools/lanes-edit.sh` (and `$HOME/…`): 20 lines (first: `handoffs/xFactory/attachments/opsXfactory-1/briefs/DELTA-land-444-r2.md:9`, `…-r4.md:4`, `…-r5-MERGE-WORKER.md:5`; also `session-handoff-2026-09-13-lane-openRepoTools-3.md:296`) | Runs the helper from the checkout root. | `lanes-edit.sh` moves to `code/` (path `~/projects/openRepoTools/code/lanes-edit.sh`, inferred). | not covered |
| installed-tool paths `~/.local/bin/<command>`: 82 lines in 30 files (first: `README.md:85`, `README.md:86`, `scripts/link-estates:16`); `~/.local/share/openRepoTools/installed.tsv`: 7 lines in 3 files (first: `migration-handoff-2026-10-06.md:17, 57, 114`) | Installed destinations. `README.md:85-86` and `scripts/link-estates:16-17` are the pre-Amendment-9 legacy map from `~/.local/bin/lane-start` and `lane-end` to `brett-wip/lanes/*`. They name no openRepoTools checkout path, and neither do the legacy copies `lanes/{lane-start,lane-end,lanes-edit.sh,test_lane_helpers.sh,README-lanes.md}`. | Destinations are expected to stay the same. | covered: l.75, l.86 |
| host-local `/workspace/projects/.lane-state/openRepoTools-{1,2,3}/trees/*.yaml` (not in git), e.g. `…/openRepoTools-2/trees/c95160057-…-triad-reads.yaml:5` | 37 tree records carry `checkout: /workspace/projects/openRepoTools`. 19 of them have a `path:` under `/workspace/projects/openRepoTools/.claude/worktrees/`, and 18 under `.lane-worktrees/openRepoTools-N`, including lane 1's workBenches worktrees (`…wb-image-rebuild-key.yaml:5`). | After cutover, new worktrees are of leg repositories. The checkout is the assembly root (inferred). | not covered |
| `/workspace/projects/openRepoTools/handoffs` → `/workspace/projects/brett-wip/handoffs/openRepoTools` (symlink placed by `link-estates:399-408`) | The checkout root holds an untracked symlink. It is ignored by `.git/info/exclude` (`/handoffs`), not by the tracked `.gitignore` (3 lines). | The assembly root keeps the path (in place, inferred). Its `.gitignore` gets the shape merge (adoption-plan.yaml:338). | not covered |

## `~/.agents` and the home directory

| file:line | what it assumes today | what the split changes | installer-design.md coverage |
|---|---|---|---|
| `~/.agents/AGENTS.md:273-278` | The lane helpers "are commands `openRepoTools --install` places from `opensoft/openRepoTools` — with the alias table `repos.tsv` beside them". | The source of the bytes becomes the code leg, through the root entry point. The names stay. | partial: l.9-14, l.75 |
| `~/.agents/AGENTS.md:327, 347-348, 367, 391-392, 419, 430, 443-444, 462, 488, 498` | "The code lands in `opensoft/openRepoTools`" for each amendment. | Code PRs land in `openRepoTools-code`, followed by an assembly pin bump (`openspec-speckit-workflow.md`, "Landing a feature"; inferred for this repository). | not covered |
| `protocols/lane-collision-protocol-amendment-9.md:735, 943`; `-11.md:1511`; `-12.md:315`; `-14.md:185`; `-17.md:175`; `-18.md:222` | Name `docs/README-lanes.md` as the tooling's manual. | `docs/` moves to `openRepoTools-spec`. | not covered |
| `protocols/lane-collision-protocol.md:659-666`; about 45 lines in amendments 8, 9, 11, 12, 16, 17 and 18 (first: `-8.md:194`, `-9.md:150`, `-11.md:1290`) | Name `openRepoTools --install` as the act that places the lane commands, skills and hooks. | Only the command name and act are read. | covered: l.75 |
| `protocols/lane-collision-protocol-amendment-9.md:673, 1000` | `:673`: `--install` runs from the copies vendored at workBenches' `upstream-pin.yaml`. `:1000`: `gh api repos/opensoft/openRepoTools/contents/<f>` returned 404 for files not yet in the repository. | The contents-API paths at the assembly root change. | partial: l.54 covers the fetch. The protocol text is not covered. |
| `protocols/openspec-speckit-workflow.md:114, 279-309`; `protocols/project-agent-bootstrap.md:96-131` | Single-repository `worktree_root: ../<repo>-worktrees`. Three-leg layout: `worktree_root: worktrees`, with `<root>/worktrees/<NNN>/{spec,code}`. | openRepoTools's feature worktrees move from `/workspace/projects/openRepoTools-worktrees/` to under the assembly root. | not covered (plan.md:207-208, T006) |
| `protocols/project-agent-bootstrap.md:138-178, 221-226`; `openspec-speckit-workflow.md:57-66` | `setup-openspeckit` detects a triad from `project.yaml`. It writes `.specify/`, managed blocks, opsx commands and skill links at the root, and OpenSpec scaffolding in the spec leg. The first line of `AGENTS.md` is an invariant. The shared checkout's `.specify/`, `.claude/`, `.agents/` and `.codex/` are local and ignored (`.git/info/exclude`). | The bootstrap must be re-run in the assembly root after the legs exist. | not covered (T006; adoption-plan.yaml:346) |
| `~/.agents/workspace.yaml:4-5` | `repository: opensoft/brett-wip`, `path: ~/projects/brett-wip`. No openRepoTools path. It is read by `openRepoTools:2211` and by `park`/`resume`. | Nothing in the file. | n/a |
| `~/.agents/AGENTS.md:384`; `lane-collision-protocol.md:681`; `-14.md:93` | `${XDG_CONFIG_HOME:-$HOME/.config}/openRepoTools/lanes-index.conf`, a per-workstation configuration path. | Nothing layout-dependent (inferred). | n/a |
| `~/.local/share/openRepoTools/installed.tsv` rows 1-29 (all stamped `2026-10-07T04:26:26Z`) | Rows 1-17 are `~/.local/bin/<INSTALLABLES>`. Rows 18-23 are the skills at `~/.claude-profiles/shared/skills/` and `~/.claude/skills/`. Rows 24-29 are the command files at both command dirs. The digests of `openRepoTools`, `lanes-edit.sh` and `lane-worktrees` equal the blobs at c4864ac. These rows consume the install, not the layout. | Names, destinations and receipt semantics are expected to stay the same. | covered: l.59, l.85-86 |
| `~/.claude/settings.json:25, 37` | Hook commands `~/projects/xFactory/lanes-edit.sh guard` and `… session-start \|\| true`. That path is a symlink to `/home/brett/.local/bin/lanes-edit.sh`. These consume the install. | Nothing, if destinations hold. | covered: l.59, l.86 |
| installed `~/.claude/skills/handoff/SKILL.md:329` (receipt rows 18-19; the `~/.claude-profiles/shared` copy has the same digest and was not opened) | The writer-poll loop sweeps `"$dir"/.claude/worktrees/*` and `"$(dirname "$dir")"/.lane-worktrees/"$lane"/*`. | Triad feature worktrees under `<root>/worktrees/<NNN>/{spec,code}` are outside both globs (inferred). | not covered |
| `~/.claude/CLAUDE.md`; `~/.agents/skills/**`, `templates/**`; `openspec-speckit-workflow.md` and `project-agent-bootstrap.md` by name | None of them name openRepoTools. | — | n/a |

## The installer's own assumptions (openRepoTools main `c4864ac`)

| file:line | what it assumes today | what the split changes | installer-design.md coverage |
|---|---|---|---|
| `openRepoTools:6-11`; `README.md:228, 236-237` | The raw-URL one-liner `…/opensoft/openRepoTools/main/openRepoTools` and `gh api repos/opensoft/openRepoTools/contents/openRepoTools`, both piped to `bash -s -- --install`. | The file moves to code. The assembly root needs the entry point. | covered: l.9-14, l.75 |
| `openRepoTools:70-72, 219-220`; `README.md:336-337` | `REPO="${OPENREPOTOOLS_REPO:-opensoft/openRepoTools}"`, `REF="${OPENREPOTOOLS_REF:-main}"`, `SELF="${BASH_SOURCE[0]:-$0}"`. | The default REPO now names the assembly. Payloads live in `openRepoTools-code`. | covered: l.16-21, l.79 |
| `openRepoTools:258-275` (`fetch_from_repo`) | Fetches `repos/$REPO/contents/$path?ref=$REF`, falling back to `raw.githubusercontent.com/$REPO/$REF/$path`. The path is relative to REPO's root. | Code paths are not at the assembly's root. | covered: l.54 |
| `openRepoTools:282-285, 338, 962-990` (`INSTALLABLES`, `collect_commands`) | "EVERY ONE OF THEM IS RESOLVED BY BARE NAME AT THE REPOSITORY ROOT". It copies `$selfdir/<name>` and fetches `<name>` otherwise. | The names sit at the code root, not the assembly root. | covered: l.40-48, l.55 |
| `openRepoTools:1290, 1303, 1370-1398` (`collect_skills`) | `skills/<n>/SKILL.md` and `commands/<n>.md` beside `$SELF`, fetched otherwise. Run from `~/.local/bin`, the 12 skill and command files are fetched from REPO/REF (inferred: they are not in the bin directory). | A fetch from the assembly misses them. | covered: l.16-18, l.55, l.78 |
| `openRepoTools:2502-2517` (`wip_shape_ref`) | Reads `$selfdir/contracts/openreposhape-pin.yaml`, else fetches `contracts/openreposhape-pin.yaml` from REPO/REF, else falls back to `main` (`:2516`). | `contracts/` moves to code. A fetch from the assembly would silently fall back to `main` (inferred from `:2516`). | covered: l.56 |
| `openRepoTools:2519-2523, 2187, 2192` (`wip_fetch_template_file`) | `$selfdir/upstream/openRepoShape/templates/workspace-root/<rel>`, else `opensoft/openRepoShape` at the pinned ref. | `upstream/` moves to code. | covered: l.57, l.87 |
| `openRepoTools:1218-1222` (`venv_note` comment) | Names the "convention `docs/README-lanes.md` states". | `docs/` moves to spec. | not covered (adoption-plan.yaml:328 follow-up) |
| `openRepoTools:28-56, 393-396` against installer-design.md:61-64 | Main: 17 `INSTALLABLES`; "31 artifacts, 29 of them files, 29 rows". The design: "15 names … 27 placed files plus two hook entries, 29 artifacts". | The design's numbers are those of `daed209`. | partial: l.64-65 ("Derive counts from the lists") |
| c4864ac tree against adoption-plan.yaml (baseline `daed209`) | `lane-worktrees`, `lanes-index` and `ideation/` (12 files) are tracked on main. | They are under no mapped path in the plan of record. | not covered (regeneration: T003, T012) |
| `repos.tsv:52` (`:8`, `:29-30`) | The only openRepoTools alias is `openRepoTools` → `opensoft/openRepoTools`. Unknown aliases are refused. | There are no leg aliases. | not covered |
| `openRepoTools:1320, 1352, 2211` | Hook commands name `~/projects/xFactory/lanes-edit.sh`. `workspace.yaml` is read from `${AGENT_PROTOCOL_ROOT:-$HOME/.agents}`. Neither depends on the layout. | Nothing (inferred). | covered: l.59, l.86 |
| `lane-worktrees:2164-2172, 2712`; `lanes-edit.sh:12146-12214` | Lane roots are `<dir>/.claude/worktrees` and `<parent of dir>/.lane-worktrees/<lane>`. The inventory is `<parent of dir>/.lane-state/<lane>`. | There is no `<dir>/worktrees` root for triad Speckit features (inferred from `_roots`). | not covered |
| `openRepoTools:291-292, 298-300, 322` | The comments name external consumers: workBenches' `setup-estate-commands.sh` 755 verification, `setup-claude-profiles.sh`, and `claude-profile` calling `claude-current`. | These are the workBenches rows above. | not covered |
| `.gitmodules:1-3`; `upstream/openRepoShape` gitlink `39d5c986`; `contracts/openreposhape-pin.yaml` | The dependency unit read by `wip_shape_ref` and `wip_fetch_template_file`. | All three move to code together (plan.md:60, FR-004). | covered: l.56-57 |

## Not covered by installer-design.md

**workBenches (9):**

1. `upstream-pin.yaml` source rows
2. `update-upstream.py` fetch and tree-mode reads
3. Dockerfile `/usr/local/bin` COPY and submodule comment
4. `estate-commands-start` array parse
5. `setup-estate-commands.sh` shim and pin checks
6. `README.md` "installed from `opensoft/openRepoTools`"
7. vendored lane code's `.lane-worktrees` derivation
8. devcontainer tests and CI path filters
9. prose and spec references

**openRepoShape (3):**

1. `templates/workspace-root` text naming README-lanes and the tooling's home
2. `shape_advisory.py:509`
3. provenance prose

**brett-wip and register state (11):**

1. lane log `dir` records
2. other path-bearing log lines
3. LANES.md rows
4. README-lanes location lines
5. `repos.tsv` override without leg aliases
6. handoffs naming the checkout root
7. `.lane-worktrees` lines
8. `openRepoTools-worktrees` lines
9. `~/projects/openRepoTools/lanes-edit.sh` lines
10. host-local `.lane-state` tree records
11. the `handoffs` symlink in the checkout root

**`~/.agents` and the home directory (5):**

1. "code lands in `opensoft/openRepoTools`"
2. `docs/README-lanes.md` in the protocols
3. the Speckit worktree root
4. the `setup-openspeckit` re-run
5. the installed handoff skill's writer-poll globs

**Installer, own assumptions (5):**

1. `venv_note`'s `docs/` reference
2. the paths unmapped against the baseline (`lane-worktrees`, `lanes-index`, `ideation/`)
3. `repos.tsv` leg aliases
4. lane-worktrees and `.lane-state` roots
5. comments naming external consumers

Total: 33 rows not covered. A further 7 are partial: workBenches 3, openRepoShape 1, `~/.agents` 2, installer 1.

## Could not read

- **Brett Heap's worktree `/workspace/projects/openRepoTools-worktrees/004-migrate-to-triad`:** not entered, under the hard rule. The plan files were read from lane 2's worktree at the same commit, ff6f6a7.
- **workBenches submodules** (`sysBenches/cloudBench`, which is modified, and `devBenches/*Bench`, `sysBenches/365Bench`): `git grep` at HEAD does not recurse into them. Not read.
- **Other writers' trees:** workBenches feature worktrees (`speckit-worktrees/012`–`017`) and lane 1's `wb-*` worktrees. Not read.
- **brett-wip:** the 215 untracked entries (`handoffs/xFactory/attachments/lane-opendox/…`) were not read. Commits after `ab88a10` (`466c3a8`, `349caef`) were not read.
- **GitHub, live:** no network read was made. Every statement that a URL or contents path would 404 after the split is marked inferred. PR #187 and the #186 record were not read here.
- **Raven** and any other workstation: not reachable from this bench.
- **`~/.claude-profiles/shared/skills/*` and `shared/commands/*`:** not opened. The receipt shows the same digests as the `~/.claude` copies that were read.
- **`git status` without `--no-optional-locks`** ran in `/workspace/projects/openRepoTools`, `/workspace/projects/workBenches` and `/workspace/projects/brett-wip`. The first two `.git/index` mtimes (`2026-10-07 04:28:20Z`, `2026-10-06 13:08:26Z`) predate this read. brett-wip's (`11:05:49Z`) postdates other writers' commits, and this read ran only `show`, `grep` and `rev-parse` there after 10:06Z.
