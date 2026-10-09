# The triad split, lane-tooling side: what moves, what breaks, what to change

**Date:** 2026-10-07 (finished 2026-10-08 on base `c4864ac`) · **Lane:** openRepoTools-3 · **Branch:** `feat/triad-lane-tooling`,
made from `origin/main` at `c4864ac` · **Slice:** (d), the lane-tooling side of the
assembly/spec/code split of `opensoft/openRepoTools`.

**Plan read:** branch `004-migrate-to-triad` at `ff6f6a7` (the head of PR #187), read with
`git show` only: `specs/004-migrate-to-triad/{plan,tasks,spec,installer-design,research,data-model,quickstart,verification,adopter-rehearsal}.md`
and `openspec/changes/migrate-to-triad/{adoption-plan.yaml,design.md}`. Brett Heap confirmed
the leg names and their public visibility on 2026-10-07: `openRepoTools-spec` mounted at
`spec/` and `openRepoTools-code` mounted at `code/`.

Every `file:line` below is on main `c4864ac` unless it names another revision. Main moved
to `837928a` while this was finished (#187 landed the plan, its `specs/004-migrate-to-triad/` and
`openspec/changes/migrate-to-triad/` byte-identical to `ff6f6a7`; #188 the openRepoShape repin);
that changed only `specs/`, `openspec/`, `contracts/openreposhape-pin.yaml` and the
`upstream/openRepoShape` gitlink, so no line cited here from a tool or a test moved, and the
branch stays on `c4864ac`. A claim
marked **measured** was run on a throwaway fixture in this lane's scratch directory; one
marked **derived** follows from the code or from git's documented behaviour and was not run.
This document decides nothing. Plan tasks are T006 (root collisions and leg guidance), T007
(installer entry point), T009 (separate roots in fixtures and hygiene), T010 (CI and pin
checks) and T018 (feature selection, park/resume and bindings).

---

## 0. Summary

1. **None of the shipped lane tools reads `docs/`, `openspec/` or `specs/` at run time.** The
   adoption plan's cross-leg follow-ups for `lane-start`, `lanes-edit.sh`, `openRepoTools` and
   `claude-current` (adoption-plan.yaml:325-328 and :334) are comments, usage text, a URL, or
   the object-key grammar. Each tool finds its helpers **beside itself**: `$SCRIPT_DIR`,
   `$selfdir` or `__file__`. All of those helpers move to `code/` together, so that lookup
   works unchanged. The only code that really reads across legs is in the **tests**. Lane 1's
   PR #190 (`feat/test-roots-for-the-triad` at `c139e88`) gives the suite those roots, so this
   branch carries no test change of its own (§6).
2. **The installer is the most fragile surface.** The README one-liners and every
   already-installed copy's own `openRepoTools --install` fetch files by **repository-root
   path** from `opensoft/openRepoTools@main` (openRepoTools:70-71, :258-275, :1370-1394). Once
   the root split lands, those paths sit under the `code` gitlink. The result: the
   one-liners stop working, every installed copy's re-install **refuses** with nothing
   placed, and `wip init` **silently** seeds from openRepoShape `main` instead of the pinned
   commit (openRepoTools:2516). No patch made before cutover can avoid this without changing
   today's behaviour. The T007 entry point has to land **in the root-split PR itself** (§4.10).
3. **Lanes keep working only if their `dir` stays at the assembly root**, and three things
   change around them. First, `#n` expands against the assembly. Second, an OpenSpec claim
   keyed on `opensoft/openRepoTools` searches the wrong repository's pull requests. Third, a
   code-leg worktree can't be seen by the lane's sweep, the `lane-end` gate or the
   `lane-handoff` poll unless it was made with `lane-worktrees add --checkout <assembly>/code`.
   The daily report never counts a submodule leg as a canonical checkout. And one live lane
   outside this repository runs the **checkout copy** `~/projects/openRepoTools/lanes-edit.sh`,
   which disappears from that path at the split (§4.4, §4.5, §4.15).
4. **The code leg needs its own `.gitattributes` and `.gitignore`.** Git applies no
   superproject attribute to a path inside a submodule (**measured**, §4.13). The plan puts both
   files at the root only. Two hygiene caps are also full: `AGENTS.md` is at its cap
   (316/316) and `README.md` is at its cap (486/486). So T006's "add the AGENTS-shape line"
   and "merge shape/README.md" fail the hygiene suite unless those caps are raised with dated
   entries.

---

## 1. Scope and method

**In scope:** the lane tools (`lane-start`, `lane-end`, `lane-worktrees`, `lanes-edit.sh`,
`lanes-index`, `lane-handoff`, `lane-rename`, `lane`, `lanes`, `link-estates`, `repos.tsv`),
`openRepoTools --install` and `wip init`, the hooks it merges, the documents that name
checkout paths, the tests and CI that assume one root, and the register/handoff data in
`opensoft/brett-wip` that names `/workspace/projects/openRepoTools` (read, never written).

**Out of scope:** the estate verbs `park`, `resume` and `status`. They find estates by
`$PROJECTS_DIR` and run `make park`/`make resume`, and they already know three-leg roots
(AGENTS.md rule 4). `claude-current` and `claude-restart-check` appear only where the
installer places them.

**How:** I read every named file (the installer and `wip init` parts of `openRepoTools`,
`lane-start`, `link-estates`, `tests/conftest.py`, `tests/run.sh`, `.github/workflows/tests.yml`
and AGENTS.md in full; the large tools by their path-bearing sections). I grepped every shipped
file for self-location (`BASH_SOURCE`, `SCRIPT_DIR`, `selfdir`, `__file__`), cross-leg directory
names, hook and settings writes, and `project.yaml` readers. I measured git's behaviour around
submodules and worktrees on a fixture of three local bare repositories. I also read lane 1's
Gate B receipt in `brett-wip/migration/openRepoTools/adopter-fix-20261007-iM20tv/`, whose
standard table is 45 spec / 49 code / 6 root of 100 tracked paths at `c4864ac`. That matches
`git ls-files | wc -l` = 100 here.

---

## 2. What the plan documents say, checked

| Claim (where) | Checked on `c4864ac` |
| --- | --- |
| No change to lane-start, lane-worktrees, lane-end, link-estates or repos.tsv beyond placing them in code (adoption-plan.yaml:163-230, 259-268) | True of the placement. Not enough for the bindings: see §4.4, §4.5, §4.15. `lane-worktrees` and `lanes-index` are absent from the committed plan (it predates them) and present in lane 1's regenerated rehearsal plan as code. |
| lane-start and lanes-edit.sh name `docs/` (adoption-plan.yaml:326-327); lanes-edit.sh names `openspec/` (:334) | They are named, but never read: §3. |
| lane-handoff names `openspec/` and the follow-ups omit it | lane-handoff:2439 is a comment citing `openspec/changes/add-supervised-context-restart/design.md`. It is not a read. |
| lane-start reads estate `project.yaml` legs (lane-start:1271-1293); lanes-edit.sh too (lanes-edit.sh:5039-5121) | True. Both readers already handle an assembly like openRepoTools's: §4.2, §4.5. |
| repos.tsv:52 has only `openRepoTools` | True. There are no `-spec`/`-code` rows. |
| Paired layout `worktrees/<feature>/{spec,code}` (plan.md:207-208) has no code on main | True. No lane tool makes, polls or claims a tree there: §4.4. |
| installer-design.md: resolve, select, delegate; one immutable code identity checked against `contracts/code-pin.yaml`; `fetch_from_repo` :258, `collect_commands` :962, `collect_skills` :1370, `wip_shape_ref` :2502, `wip_fetch_template_file` :2519; REPO/REF :70-71 | Every line number holds. `code-pin` has 0 hits in tracked files. |
| installer-design.md:61-64 counts 15 names / 27 files / 29 artifacts | **Stale.** `INSTALLABLES` (openRepoTools:338) holds **17** names. With 3 skills and 3 command files at 2 paths each, that is **29 placed files + 2 hook entries = 31 artifacts**, which is the installer's own statement (openRepoTools:389-396). Placing by rename (#172, `3660224`) landed after the design. It changes the placement mechanics, not the sources. |

---

## 3. The adoption plan's cross-leg follow-ups, line by line

Lane 1's Gate B receipt (`logs/runB-cross-leg-grep.log`) lists file names only. Each hit
falls into one of these kinds: **comment**, **usage** (text a command prints), **URL**,
**key** (an object key, not a path), **fixture** (data a test builds), or **READ** (a file
opened at run time).

| Follow-up | Hit on `c4864ac` | Kind | Change needed |
| --- | --- | --- | --- |
| claude-current names `docs/` (:325) | claude-current:89 | comment | none |
| | claude-current:123 | usage (`--help` prints `docs/README-claude-current.md`) | Text only: the path is repository-relative, so after the split it means `spec/docs/…` from the root or `../spec/docs/…` from `code/`. Changing it changes `--help`'s bytes, so this is a **proposal** for the T014 docs batch, not a patch. |
| lane-start names `docs/` (:326) | lane-start:294, :617 | comment | none |
| lanes-edit.sh names `docs/` (:327) | lanes-edit.sh:10387 | comment | none |
| openRepoTools names `docs/` (:328) | openRepoTools:1218 (comment); :1342 (URL `code.claude.com/docs/en/hooks`) | comment, URL | none |
| tests/run.sh names `docs/` (:329) | tests/run.sh:36 | comment | none |
| test_install_skill_and_hook.py (:330) | :73, :1339 | URL | none |
| test_lane_helpers.sh names `docs/` (:331) | :3738, :6228 `cat "$SRC_DIR/docs/README-lanes.md"` | **READ** | #190: `LANE_MANUAL`, skipped when the run has no spec root |
| test_lane_start_claude_current.py (:332) | :15 | docstring | none |
| "… and 1 more" (:333) = test_repo_hygiene.py | :1183, :1214-1217, :1233, :2390, :2624 | **READ** | #190: `doc()` → `ROOTS.path_for` |
| lanes-edit.sh names `openspec/` (:334) | :280, :2770 (comments); :2814-2818, :2895-2897 (grammar `owner/repo:openspec/changes/<name>`); :12110 (comment) | key | No path change. The **repository half** of the key changes meaning: §4.5. |
| test_lane_helpers.sh names `openspec/` (:335) | :1280, :2086, :3781 (object keys of a fake `opensoft/repoE`); :13343 (comment) | fixture, comment | none |
| test_park_resume_commands.py names `specs/` (:336) | :350, a `feature_directory: worktrees/…/spec/specs/…` string in a three-leg record the test writes | fixture | none |
| (not listed) lane-handoff names `openspec/` | lane-handoff:2439 | comment | none |

---

## 4. Surface by surface

### 4.1 How every tool finds its helpers (all tools)

| Tool | Self-location (`c4864ac`) | Helpers found beside itself |
| --- | --- | --- |
| lane-start | :339-341 `SCRIPT_DIR` from `readlink -f` | lanes-edit.sh :600-604, claude-current :650, lanes :868, lane :917, lane-worktrees :4307 |
| lane-end | :259-261 | lanes-edit.sh :520, lane-worktrees :532 |
| lanes-edit.sh | :634-639 | lanes-index :2256, repos.tsv :2453, lane-start :9189 |
| lane-handoff | :119-120 | lanes-edit.sh :399, lane-start :685 |
| lane / lanes / lane-rename | lane:114-115 / lanes:102-103 / lane-rename:73-74 | lanes-edit.sh (lane:188, lanes:191, lane-rename:155), lane-start (lane:1166) |
| lanes-index | :325 `dirname(realpath(__file__))` | lanes-edit.sh |
| lane-worktrees | :441, :5278 | lanes-edit.sh, status |
| openRepoTools | :72 `SELF`; :971, :1372, :2504, :2521 `selfdir` | the 17 installables, `skills/`, `commands/`, `contracts/openreposhape-pin.yaml`, `upstream/openRepoShape/templates/…` |

**Under the triad:** every one of these helpers is code-leg content (adoption-plan.yaml:107-323),
so `code/<tool>` finds `code/<helper>` exactly as `<tool>` finds `<helper>` today. Installed
copies in `~/.local/bin` are unaffected. **No change; T006 confirms it.**

### 4.2 `lane-start`

| Line | What it does | Under the triad |
| --- | --- | --- |
| :608 | `PROJECTS_ROOT=${PROJECTS_ROOT:-$HOME/projects}` | unchanged |
| :1116-1357 | The lane's directory, by six rungs: `--dir`, the swap record, the lane log's `dir`, `$PROJECTS_ROOT/<repo>`, the estate `project.yaml` legs (:1291-1318), then a checkout named for the home and proved by its origin (:1319-1328) | Lanes openRepoTools-1, -2 and -3 record `dir /workspace/projects/openRepoTools` (§4.15), so rungs 2 and 3 answer. If the assembly stays at that path (an in-place adoption of the live checkout), **nothing changes**. A lane homed at `opensoft/openRepoTools-code` (none exists) would be resolved by rung 5: the reader at :1301-1309 matches `repository:` against the home and resolves `path: code` against the manifest's directory. The shell suite already covers rung 5 on a declared `legs:` manifest (tests/test_lane_helpers.sh:5691-5704). IRRS, IRSS and MedxEHR carry the same block on this workstation today. |
| :1118-1128 | "the harness keys a session to the directory it was started in" (Evidence 3) | **This is why a lane's `dir` should stay at the assembly root.** Re-homing a lane into `code/` changes the Claude project folder (`-workspace-projects-openRepoTools` → `-workspace-projects-openRepoTools-code`). That strands the lane's memory, and `--resume <uuid>` stops finding the transcript. **T018 proposal:** bindings keep `dir` = assembly root, and nothing is rebound. |
| :1180-1199 | The home is written from the directory's `origin` | At the assembly root the origin is still `opensoft/openRepoTools`, so the home is unchanged. |
| :4294-4340 | Starts the daily report (`lane-worktrees sweep --all --dry-run --report`) for `$PROJECTS_ROOT` | Inherits the report's blind spot: §4.4. |
| hooks | lane-start writes **no** hook and no `settings.json` (`grep` finds only comments at :142, :1783) | none |

**Patch:** none needed. **Proposal (T018):** the bindings decision above, plus a fixture test
that runs rung 5 against an openRepoTools-shaped manifest (§7).

### 4.3 `lane-end`

The close-out gate (:195-211, :1908-2045) runs `lane-worktrees sweep <lane> --branches
--include-scratch --include-caches --dry-run --porcelain`. It then reads every tree with
`git status --ignored` (:1927-1945) and every entry under `${dir%/*}/.lane-worktrees/<lane>`
(:2024-2045). Its roots and its trees are lane-worktrees'. **Under the triad it is as blind as
the sweep (§4.4).** A lane with unpushed work in a paired `worktrees/<feature>/code` tree, or
in any code-leg tree it never recorded, passes the gate. **Patch:** none. **Proposal:** the
lane-worktrees roots change in §4.4 closes this too.

### 4.4 `lane-worktrees`: sweep inventory, `add`, and the daily report

**Measured** on a fixture (assembly `A` with `code` and `spec` submodules, and a worktree
of the code leg at `A/worktrees/001-x/code`):

- `git -C A/code rev-parse --show-toplevel` → `A/code`, and `--show-superproject-working-tree` → `A`;
- `A/code/.git` is a **file**, `gitdir: ../.git/modules/code`;
- `git worktree add` inside the submodule succeeds (git 2.43);
- `git -C A worktree list` lists **only `A`**. The code leg's tree appears only under
  `git -C A/code worktree list`, whose main entry is spelled `A/.git/modules/code`;
- `git -C A status` shows `?? worktrees/`. The shape's assembly `.gitignore` template
  (`templates/assembly-root/.gitignore` at the pinned openRepoShape) does not ignore it.

| Line | What it reads | Under the triad |
| --- | --- | --- |
| :2165-2173 `_roots` | `<dir>/.claude/worktrees` and `${dir%/*}/.lane-worktrees/<lane>` | Unchanged for `dir` = assembly. The paired `A/worktrees/<feature>/{spec,code}` is **in neither root**. |
| :2175-2248 `_discover` | inventory sidecars + `git worktree list` of the lane's checkout and of every inventoried `checkout` | A code-leg tree is seen **only if** an inventory row names `checkout: <assembly>/code`. A tree made by `make resume`/Speckit in the paired layout is never seen. |
| :2122-2163 `_lane_claims` | trailer claims under `.claude/worktrees` only | Paired trees are never claimed. |
| :2709-2713, :2759-2763 | scratch and caches under `.lane-worktrees/<lane>` | unchanged |
| :5381-5557 `add` | `git worktree add` of `--checkout` or the lane's `dir`, at `${dir%/*}/.lane-worktrees/<lane>/<slice>`, then `set-lane-tree … --checkout <checkout>` | Without `--checkout`, it makes a worktree of the **assembly**, with empty, uninitialised `code/` and `spec/` (a worktree does not initialise submodules). **With `--checkout <assembly>/code` it works today:** `:5448-5451` accepts it because `--show-toplevel` is the submodule root (measured above). |
| :1091-1125 `estate_repos` | walks into a repository only through `worktrees`, `.worktrees`, `.claude`, or a child with `.git` | `A/worktrees/<feature>` has no `.git`, so `A/worktrees/<feature>/code` is never reached (derived). |
| :4884-4907, :4887 `Report.build` | `clones = [r … if os.path.isdir(r/.git)]` → canonical checkouts → branches, root-main, aging | A leg's `.git` is a file, so **a submodule leg is never canonical**. The code leg's branches, which are where all lane-tooling work happens after the split, never reach the daily report. This is already true today for every leg of IRRS, IRSS, MedxEHR and openDox on this workstation. |
| :4760-4770 `_under_container` | `worktrees`, `.worktrees`, `*-worktrees`, `.lane-worktrees/<lane>` | Recognises `A/worktrees`. Unaffected. |

**Patch:** none. Every fix changes what the sweep or the report says **today** about the
estate's existing triads, and the brief rules out behaviour changes. **Proposals (T018):**

1. **Guidance, no code:** under the triad a lane makes a code tree with
   `lane-worktrees add <lane> <slice> --checkout <assembly>/code`. That records the tree
   with the code leg as its checkout, so every reader above sees it.
2. `_roots` adds `<assembly>/worktrees` when `<dir>/project.yaml` names legs. Trees there are
   claimed only by the HEAD `Lane:` trailer rule `_lane_claims` already applies to
   `.claude/worktrees`, because that directory is per-feature, not per-lane. The same root
   goes into `lanes-edit.sh:12699-12705` (`lane_worktree_roots`) and
   `lane-handoff:1994-1996`, so the three readers cannot disagree.
3. `Report.build` treats a checkout whose `.git` is a file pointing into
   `<superproject>/.git/modules/<path>` as canonical when the superproject is canonical.
   This changes today's report for IRRS and the other existing triads, so it needs a ruling.

#### 2026-10-09: what this branch now implements of §4.4 (T018), and what moves for every shape

**On the coordinator's brief for slice (d2)** (worktree visibility for triad legs,
plan task T018), proposals 1–3 above are implemented as **shape-gated** changes,
one commit each with its tests (`tests/test_triad_lane_tooling.py`). The gate is
the standard's own rule: the lane's checkout (or the checkout a tool polls) is an
**assembly** when its own `project.yaml` declares a leg other than itself. One
reader answers it for every tool, `lanes-edit.sh project-legs <checkout>`, whose
seven deciding awk lines are `lane-start`'s rung-5 lines verbatim (a test holds
them equal). A checkout with no `project.yaml` is asked nothing, so on a single
repository every output, exit code, register line and inventory row is the one
`c45a452`'s tools produce: the test stores that "before" as a golden file
generated once from `c45a452`'s own tools (`tests/fixtures/t018/`), because CI
checks out at depth 1, and compares every touched command's output on a single
repository — one with a submodule that is no leg, and one with a `project.yaml`
naming no leg but itself — against it.

**Outputs that change regardless of shape (for lane 1's ruling).** Two kinds of
text move on every checkout, single repository included, because they are usage
text and not behaviour; the coordinator directed both kept and listed here:

1. `lanes-edit.sh`'s refusal of an unknown subcommand (exit 2) now lists
   `project-legs` among the subcommands it answers to, and its usage header (what
   `lanes-edit.sh` with no argument prints) gains the `project-legs` line.
   `tests/test_repo_hygiene.py` requires the refusal to list every arm.
2. The `--help` text of the touched commands gains the triad guidance:
   `lane-worktrees --help` (a "A TRIAD" paragraph), `lane-end --help` (four lines
   in THE CLOSE-OUT GATE), and the commands later commits touch, each named in
   that commit's message.

No exit code, register line, inventory row, sweep row, gate verdict or report
line moves for a checkout with no `project.yaml`.

### 4.5 `lanes-edit.sh`

| Line | What it does | Under the triad |
| --- | --- | --- |
| :2754-2765 `alias_lookup`; :2776-2847 `canon_object` | resolves a key's repository through repos.tsv. A spelled `owner/repo` is **always accepted** (:2834) | `opensoft/openRepoTools-code#n` works with no repos.tsv row. The bare `openRepoTools-code#n` is refused until the row exists (§4.9). |
| :2791-2813 | `#n` expands against the lane's **home** | Home stays `opensoft/openRepoTools`, so `#n` always means the **assembly's** issue or PR. The code leg numbers its PRs from #1, so `#3` from an openRepoTools lane is the assembly's #3, never the code leg's. **T018 proposal:** code-leg and spec-leg objects are spelled in full. The lane-collision protocol text should say so. |
| :2814-2818, :2895-2897 | `owner/repo:openspec/changes/<name>` keys | Rule 1's sibling reads run `gh pr list --repo <object_repo> --search <slug>` (:10249-10272). A change keyed on `opensoft/openRepoTools` therefore searches the **assembly's** PRs, while spec PRs land in `openRepoTools-spec`. **T018 proposal:** at cutover, each open claim on `opensoft/openRepoTools:openspec/changes/<x>` is released and re-claimed as `opensoft/openRepoTools-spec:openspec/changes/<x>`, through `lanes-edit.sh release`/`claim`. The log is append-only and is never rewritten. |
| :5053-5105 `project_legs_file`, `same_project` | manifests at `$PROJECTS_ROOT/*/project.yaml` and `*/*/project.yaml` | `/workspace/projects/openRepoTools/project.yaml` is depth 1, so a claim on `opensoft/openRepoTools-code#n` from a lane homed at the assembly is "legs of one project.yaml — not a crossing" (:5120-5122). This works with no change. |
| :12555-12595 `tree_id_for`, `lane_tree_put` | sidecar per tree: absolute `path`, `checkout`, branch, head … | Formats are unchanged. Rows written before cutover stay **true**: they describe worktrees of the monorepo history, which is the assembly's own history (FR-001). |
| :12699-12705 `lane_worktree_roots` | `<dir>/.claude/worktrees`, `${dir%/*}/.lane-worktrees/<lane>` | Same gap as §4.4, proposal 2. |
| :16791-16829 `set-lane-tree` | takes an absolute path and an **unvalidated** `--checkout` | Records a code-leg tree today: `--checkout <assembly>/code`. |
| :14973-15030 `session-start`, `guard` | the two hook verbs; the guard compares window, session name and register row, never the cwd | unchanged (§4.11) |
| :594 `LANES_LANE_DIR` | leg detection from the lane's checkout | unchanged |

**Patch:** none. A behaviour change in object keys or roots needs a ruling. **Proposals:** as
in the table.

### 4.6 `lanes-index`

It reads the register through `lanes-edit.sh` beside itself (:325) and keeps its store and
config under XDG (`:160-166`). It has no repository-relative path. **No change.**

### 4.7 `lane-handoff`

Helpers beside itself (:119-120, :399, :685). The writers poll covers
`$dir/.claude/worktrees/*` and `$parent/.lane-worktrees/$lane/*` (:1892-1996), and has the
same gap as §4.4. The only `openspec/` reference is a comment (:2439). **No change; one
proposal (§4.4, item 2).**

### 4.8 `lane`, `lanes`, `lane-rename`

`lanes` with no arguments narrows to "the checkout around the cwd" by its
`git rev-parse --show-toplevel` and that checkout's `origin` (lanes:394-420, lane:440-460).
**Under the triad** a person standing in `code/` gets `--dir <assembly>/code --repo
opensoft/openRepoTools-code --prefix openRepoTools-code`. No lane matches, and it offers
`lane-start openRepoTools-code 1` (derived). From the assembly root it is unchanged.
`lane-rename` has no path of its own. **Proposal (T018):** when `--show-superproject-working-tree`
is non-empty and that superproject's `project.yaml` names the toplevel as a leg, narrow to the
superproject's directory and origin. This changes today's output inside IRRS/IRSS legs, so it
needs a ruling. Patch sketch:

```bash
here_root="$(git rev-parse --show-toplevel 2>/dev/null || :)"
super="$(git rev-parse --show-superproject-working-tree 2>/dev/null || :)"
if [ -n "$super" ] && [ -f "$super/project.yaml" ]; then here_root="$super"; fi
```

### 4.9 `link-estates` and `repos.tsv`

`link-estates` finds the workspace through `workspace.yaml` and never from its own location
(:89-295). It links `~/projects/<estate>/handoffs` → `<workspace>/handoffs/<estate>` for each
estate directory that exists (:399-409), and `~/projects/xFactory/lanes-edit.sh` →
`$OPENREPOTOOLS_BIN_DIR/lanes-edit.sh` (:421). **Under the triad:**
`/workspace/projects/openRepoTools/handoffs` is an untracked symlink in the live checkout today,
and it stays one at the assembly root. The hook link points at the installed copy. **No
change.**

`repos.tsv`:52 maps `openRepoTools` only. Its own rule (repos.tsv:16-23) is that a row is
added "when a new repo first appears in a LANDING line", resolved with `gh repo view`. Rows
for repositories that do not exist yet would break that rule. **Proposal (cutover, after Gate
C creates the legs):** two rows, `openRepoTools-code	opensoft/openRepoTools-code` and
`openRepoTools-spec	opensoft/openRepoTools-spec`, in the code leg's `repos.tsv`.

### 4.10 `openRepoTools --install`, `wip init` and the `installed.tsv` receipt

**Where each artifact comes from today.** `SELF` is this file (openRepoTools:72). When it is a
file, `selfdir` is its directory.

| Artifact | Local source (when `SELF` is a file) | Remote source | Code |
| --- | --- | --- | --- |
| The 17 `INSTALLABLES` (openRepoTools, park, resume, status, lane, lanes, lane-handoff, lane-rename, lanes-edit.sh, lane-start, lane-end, link-estates, repos.tsv, claude-current, claude-restart-check, lanes-index, lane-worktrees) | `$selfdir/<name>` | `fetch_from_repo <name>`: `gh api repos/$REPO/contents/<name>?ref=$REF`, else `raw.githubusercontent.com/$REPO/$REF/<name>` | :338, :962-990, :258-275 |
| 3 skills × 2 destinations | `$selfdir/skills/<n>/SKILL.md` | `fetch_from_repo skills/<n>/SKILL.md` | :1289-1290, :1370-1381 |
| 3 command files × 2 destinations | `$selfdir/commands/<n>.md` | `fetch_from_repo commands/<n>.md` | :1302-1303, :1387-1394 |
| `SessionStart` entry | constant `~/projects/xFactory/lanes-edit.sh session-start \|\| true` | none | :1320, :1324-1333 |
| `UserPromptSubmit` guard | constant `~/projects/xFactory/lanes-edit.sh guard` | none | :1352, :1355-1363 |
| `wip init` pin | `$selfdir/contracts/openreposhape-pin.yaml` | `fetch_from_repo contracts/openreposhape-pin.yaml`, **else the literal `main`** | :2502-2517 |
| `wip init` templates | `$selfdir/upstream/openRepoShape/templates/workspace-root/…` | `gh api`/raw from `opensoft/openRepoShape` at the pin | :2519-2544 |

**The receipt** (`installed.tsv`, rows written at openRepoTools:561-598) is
`<name> <destination> <sha256> <UTC>`. It records **no source**, so a code-leg source changes
none of its rows. Readers accept four **or more** fields (`receipt_rows_except` :641-645,
`receipt_verdict` :808-819). A fifth column for the code identity, which T008 asks to be
recorded ("record its actual code identity"), can be appended without breaking an older
reader.

**What happens in each context once the root split has landed** (derived; the GitHub
behaviour for paths under a gitlink is to be measured in T008):

| Context | Today | After the split, with no T007 |
| --- | --- | --- |
| a. `code/openRepoTools --install` in an assembly checkout | — | `selfdir` = `code/`, all 23 files local. **Works unchanged.** |
| b. `./openRepoTools --install` at the assembly root | the monorepo file | No file of that name until T007. |
| c. README one-liners (README.md:228, :236) | fetch root `openRepoTools`, which then fetches the rest by root path | The root path `openRepoTools` 404s until T007 exists. With a T007 entry point that only `exec`s the code installer, the code installer still fetches `park`, `skills/…` and the rest from `$REPO@$REF` = the **assembly**, where those paths are under `code` and 404. **The entry point must also hand the delegate one immutable code identity.** |
| d. Installed copy `~/.local/bin/openRepoTools --install` | `selfdir` = `~/.local/bin`, so it copies the **17 already-installed files over themselves** (:976-980; an installed copy never updated its commands) and fetches skills and commands from `opensoft/openRepoTools@main` | `collect_skills` gets a 404 and returns 1. `install_commands` dies at :1125 with "could not fetch one of the 3 skills…", **exit 2, nothing placed**. A safe refusal, but on every workstation. |
| e. Installed copy `openRepoTools wip init` | pin fetched from the monorepo | `contracts/openreposhape-pin.yaml` is not at the assembly root (the assembly has `contracts/{shape,spec,code}-pin.yaml`), so `wip_shape_ref` prints **`main`** (:2516). **Silent drift**: templates come from openRepoShape `main`, not from the pin. |
| f. `--version` | `openRepoTools (opensoft/openRepoTools @ main)` | unchanged text, now naming the assembly |

**Why no patch made now can save (d) and (e).** The population that would need the fix is
every copy already installed. Those copies get new code only from an install that succeeds,
and the only one that can succeed after cutover is (a) or the T007 one-liner. A
pre-cutover change that probes `contracts/code-pin.yaml` first would add a network request to
every remote install today. It would also have to tell a 404 from a transport failure
(installer-design.md:31-33), which `fetch_from_repo` cannot do: it returns a bare status
(:258-275). That is T007 proper.

**T007 proposal, as a sketch** (bash 3.2; root file `openRepoTools`; it delegates and adds no
install mechanics):

```bash
#!/usr/bin/env bash
# openRepoTools (assembly root): resolve ONE code identity, then run the code leg's installer.
set -euo pipefail
REPO="${OPENREPOTOOLS_REPO:-opensoft/openRepoTools}"; REF="${OPENREPOTOOLS_REF:-main}"
SELF="${BASH_SOURCE[0]:-$0}"
die() { printf '\nREFUSED: %s\n' "$1" >&2; exit 2; }
# 1. A local adopted checkout: the gitlink and contracts/code-pin.yaml must agree.
if [ -f "$SELF" ]; then
  here="$(cd -- "$(dirname -- "$SELF")" && pwd)"
  if [ -f "$here/project.yaml" ]; then
    link="$(git -C "$here" ls-tree HEAD code | awk '$2 == "commit" { print $3 }')"
    pin="$(sed -n 's/^commit:[[:space:]]*"\{0,1\}\([0-9a-f]\{40\}\)"\{0,1\}[[:space:]]*$/\1/p' "$here/contracts/code-pin.yaml")"
    [ -n "$link" ] && [ "$link" = "$pin" ] || die "code gitlink ($link) and contracts/code-pin.yaml ($pin) disagree"
    [ "$(git -C "$here/code" rev-parse HEAD 2>/dev/null)" = "$pin" ] || die "code/ is not checked out at the pin $pin: git submodule update --init code"
    exec "$here/code/openRepoTools" "$@"
  fi
fi
# 2. Remote: REF resolved ONCE; the pin read at that commit; the gitlink checked; the code
#    installer run with the public variables naming the code identity, so every payload it
#    fetches comes from that one commit (gh first, curl second, as fetch_from_repo does).
commit="$(gh api "repos/$REPO/commits/$REF" --jq .sha)" || die "…"
# … read contracts/code-pin.yaml at $commit (source_repository, commit), check the gitlink
#   `gh api repos/$REPO/contents/code?ref=$commit --jq .sha` equals it, fetch
#   openRepoTools from $code_repo at $code_commit into a temp file, then:
OPENREPOTOOLS_REPO="$code_repo" OPENREPOTOOLS_REF="$code_commit" exec bash "$tmp" "$@"
```

The **code installer** then needs installer-design.md's code-side resolution for context (d),
because an installed copy defaults `REPO` to the assembly again: before `collect_skills`, if
`$REPO@$REF` carries `contracts/code-pin.yaml`, payloads come from the pinned code repository
and commit. A pin that is present but malformed refuses. Only an authoritative 404 means a
legacy monorepo. **Landing order:** the entry point has to be in the root-split PR's tree. If
it lands later, the README one-liners are broken for everyone in between.

### 4.11 Hooks

Only `openRepoTools --install` writes hooks: two entries merged into
`$CLAUDE_USER_DIR/settings.json` (`plan_hook_merge` :1760-1880, `place_skill_and_hook` :1976).
Both commands name `~/projects/xFactory/lanes-edit.sh`, which `link-estates` points at the
**installed** `lanes-edit.sh` (link-estates:421). `lane-start` and every other tool write no
hook (grep: comments only). `lanes-edit.sh guard` (:15000-15030) compares window, session
name and register row, never the cwd or the repository layout. **No change.**

### 4.12 Documents that name checkout paths

| Where | What | Under the triad | Task |
| --- | --- | --- | --- |
| README.md:157 | `docs/README-lanes.md`, `docs/README-claude-current.md` | From the root README these are `spec/docs/…` | T006 / T014 docs batch |
| README.md:228, :236 | the one-liners for the root `openRepoTools` | stay byte-identical (`RAW_INSTALL_LINE`, test_repo_hygiene.py:105-107, is printed by openRepoShape's `--install`); they need T007 | T007 |
| README.md:417-449, :467-468 | pin-bump procedure with `upstream/openRepoShape`, `contracts/openreposhape-pin.yaml` | From the root these are `code/upstream/…`, `code/contracts/…`, or the procedure moves to the code leg's guidance | T006 |
| AGENTS.md:22, :44 | `docs/README-lanes.md`, `openspec/changes/skip-no-lane-guard/` | `spec/…` from the root | T006 |
| AGENTS.md:200-224, :233, :247-250, :285, :291-292 | `upstream/openRepoShape`, `contracts/openreposhape-pin.yaml`, `git submodule update --init upstream/openRepoShape`, `tests/run.sh`, `.github/workflows/tests.yml`, `tests/test_lane_helpers*.{sh,py}` | All are code-leg paths: from the root, `cd code` first | T006 |
| docs/README-lanes.md:573-594, :3979-3997 | `tests/run.sh` | code-leg path | T006 |
| docs/README-lanes.md:1793 | example `STARTED` line, `dir ~/projects…` | an example; true as long as the assembly stays at its path | none |
| docs/README-claude-current.md:172 | "looks for `claude-current` beside itself" | true in `code/` | none |
| ideation/brainstorm/supervised-context-restart-durable-intent.md:31 | `directory: /workspace/projects/openRepoTools` (an example intent record) | spec-leg prose; stays true if the assembly keeps that path | none |

**Hygiene caps that T006 will trip:** test_repo_hygiene.py:1735-1736 caps AGENTS.md at 316
lines, and it **is** 316. test_repo_hygiene.py:2232-2233 caps README.md at 486, and it **is**
486. The adoption follow-ups "add the line `Read AGENTS-shape.md first…` to the existing
AGENTS.md" (adoption-plan.yaml:339) and "merge shape/README.md into README.md" (:341) each
add lines. Each cap needs a dated entry in the same PR, following the convention the test's
docstring keeps.

### 4.13 Tests

Lane 1's **PR #190** (`feat/test-roots-for-the-triad` at `c139e88`, based on `c4864ac`,
T009/T010) is the suite's roots. It was read with `git diff c4864ac..c139e88 -- tests/` and
was not run here. This table says, for each assumption, what #190 does about it.

| Test | Assumption (`c4864ac`) | Under the triad | Change |
| --- | --- | --- | --- |
| tests/conftest.py:29 | `REPO = parents[1]`, one root | `REPO` is the code root, and stays so | #190: `ROOTS = resolve_roots(os.environ, SUITE_ROOT)`, `REPO = CODE_ROOT`, `ROOTS.path_for(rel)`. The roots come from `OPENREPOTOOLS_{CODE,ASSEMBLY,SPEC}_ROOT`, or are found through `discover_assembly` (`contracts/code-pin.yaml` + `project.yaml` + the gitlink). `OPENREPOTOOLS_COMPOSED=1` is the composed mode. |
| tests/conftest.py:48-58 | `UPSTREAM = REPO/upstream/openRepoShape` | code leg, unchanged (FR-004) | #190: `UPSTREAM = DEPENDENCY_ROOT`. Standalone it skips as today; composed it fails. |
| test_repo_hygiene.py: 23 reads of README.md, AGENTS.md, CLAUDE.md, docs/README-lanes.md (:849, :860, :887, :911, :918, :942, :954, :957, :988, :1010, :1012, :1038, :1048, :1183, :1217, :1221, :1233, :1246, :1735, :2232, :2390, :2624, :3074) | `REPO / …` | README, AGENTS and CLAUDE are assembly files; README-lanes is a spec file | #190: `doc()` and `code_first()` |
| test_repo_hygiene.py:234, :2453, :2650, :2691 | `git ls-files` at REPO | The code leg's own index only | #190: `tracked_files()` over `ROOTS.tracked_roots()`. The composed run also scans the assembly and the spec leg. |
| test_repo_hygiene.py:2681 | `REPO/.gitattributes` carries `* text=auto eol=lf` | **Fails in the code leg**, because the plan puts `.gitattributes` at the root only (adoption-plan.yaml:41-48). Git applies **no** superproject attribute inside a submodule: **measured**, `git -C A/code check-attr -a lane-start` prints nothing while `git -C A check-attr -a project.yaml` prints `text: auto`, `eol: lf`. The installer's `cmp -s` byte checks and test_openrepotools_command.py's byte comparisons depend on that rule. | #190 reads it from the code root **deliberately**, for the same reason. That makes the **T006** proposal mandatory: the code leg carries its own `.gitattributes` (`* text=auto eol=lf`) and `.gitignore` (`__pycache__/`, `*.py[cod]`, `.pytest_cache/`, as at the root today). Without the ignore file, a bare `python3 -m pytest` in `code/` leaves the submodule dirty in the assembly's status. |
| test_openrepotools_command.py:1398 | README.md | assembly | #190: `ROOTS.path_for("README.md")` |
| test_install_*.py, test_wip_init_command.py:42-43, test_upstream_pin.py:28, :102 | `openRepoTools`, `skills/`, `commands/`, `upstream/…`, `.gitmodules`, `contracts/…` at REPO | all code-leg paths | none needed; #190 also edits test_upstream_pin.py |
| tests/test_lane_helpers.sh:50, :3738, :6228 | `SRC_DIR` = repo root; manual read from `$SRC_DIR/docs/README-lanes.md` | The read comes back **empty**. 13 `has` assertions then fail (:3739-3744, :6229-6239, :6580), and 3 `hasnt` assertions pass with nothing to check (:3745, :6241, :6579) | #190: `LANE_MANUAL="${OPENREPOTOOLS_LANE_MANUAL-$SRC_DIR/docs/README-lanes.md}"`. The two quoting blocks are skipped, by name, when it is set and empty. **Not covered:** the third read, inside the `--retire` block (:6579-6580 on `c4864ac`, :6595-6596 in #190), still reads `$ln_doc` after #190's `if`/`else`. With no spec root `ln_doc` is never assigned, and the suite runs under `set -u` (:42), so the whole shell suite **aborts** there with `ln_doc: unbound variable`. **Measured** on the same construct: `bash -c 'set -uo pipefail; has() { :; }; has d "$ln_doc" x; echo after'` prints that error, exits 127 and never reaches `after`. This happens only in a standalone code leg; today's layout is unaffected. |
| tests/test_lane_helpers_suite.py:157-191 | runs the shell suite at REPO | needs the spec root handed to it | #190: `OPENREPOTOOLS_LANE_MANUAL` from `ROOTS.root_of("spec")` |
| tests/run.sh:75-80, :235-236 | cds to the repo root; venv named `openRepoTools` | code root; the venv name is a constant | #190: makes relative `OPENREPOTOOLS_*_ROOT` absolute before the `cd` |

**One gap in #190 that the lane tooling's layout raises** (read, not run):
`discover_assembly` stops at the first directory above the code checkout that carries the
assembly markers, and requires that directory to mount this checkout. A code worktree in
plan.md's paired layout, `<assembly>/worktrees/<feature>/code`, is therefore a leg with no
assembly. Its manual and front-door reads **skip** unless the roots are named, although the
paired spec worktree sits beside it at `../spec`.

### 4.14 CI (`.github/workflows/tests.yml`)

Every job checks out **this repository at its root** (`actions/checkout`, :55, :83, :129,
:184, :235, :291), with `submodules: true` (:57, :85, :186, :293) or `false` (:131, :237).
In the code leg the same file runs the code leg's own tests, with the nested
`upstream/openRepoShape` intact. With no spec or assembly context, #190's document reads
skip in a standalone run. Composed (`OPENREPOTOOLS_COMPOSED=1`), the run is refused before its
first test. #190 changes no workflow. The bash-3.2 list (:254-272) and `test_the_macos_job_parses_every_bash_file…`
(test_repo_hygiene.py:166-194) are code-relative and unaffected.

**T010 proposal, as a sketch:** each job that runs the full suite adds two read-only
checkouts and names them:

```yaml
      - uses: actions/checkout@<pinned sha>
        with: { path: code, submodules: true }
      - uses: actions/checkout@<pinned sha>
        with: { repository: opensoft/openRepoTools-spec, ref: <the matching spec commit>, path: spec }
      - uses: actions/checkout@<pinned sha>
        with: { repository: opensoft/openRepoTools, ref: main, path: assembly, submodules: false }
      - run: bash tests/run.sh -k 'guard_launch_mode or repo_hygiene'
        working-directory: code
        env:
          OPENREPOTOOLS_SPEC_ROOT: ${{ github.workspace }}/spec          # #190's names
          OPENREPOTOOLS_ASSEMBLY_ROOT: ${{ github.workspace }}/assembly
          OPENREPOTOOLS_COMPOSED: "1"
```

"Matching" is lane 1's decision: the spec commit the assembly's `contracts/spec-pin.yaml`
names at assembly `main`, or the paired feature branch of the same name. `tests-no-submodule`
(:127-149) keeps proving that a fork's first run skips rather than fails. The assembly's own
`validate.yml` from the shape checks manifest and pins.

**2026-10-09: the sketch above, as written, cannot pass #190's composed mode** (found by the
review of #190, read here at `dbc6837`). It checks out the PR's code at `code/` and the
assembly at its `main`, and names that assembly in `OPENREPOTOOLS_ASSEMBLY_ROOT` with
`OPENREPOTOOLS_COMPOSED=1`. #190's composed contract refuses any code root the assembly does
not pin: `Roots.absent()` (tests/conftest.py:283) runs `_leg_at_its_pin("code", …)` (:259),
which compares the code root's HEAD with the gitlink the assembly records at its code mount
and refuses a mismatch ("composed acceptance is for the pinned code leg and no other"), and
`pytest_configure` (:404-412) raises that refusal as a `pytest.UsageError`, **exit 4**, before
the first test. On a code PR the PR's commit is never the commit assembly `main` pins, so the
job would exit 4 on every code PR. Without `OPENREPOTOOLS_ASSEMBLY_ROOT`, `discover_assembly`
(tests/conftest.py:159-172) finds an assembly only above the code root that MOUNTS it at its
gitlink, which a sibling `code/` checkout is not. A composed job therefore has to do one of
three things:

1. check out an assembly whose code gitlink already points at the PR's own commit (a paired
   assembly branch that pins it);
2. build a throwaway assembly for the run that pins the PR's commit (the assembly at `main`,
   its `code` gitlink and `contracts/code-pin.yaml` moved to the PR's commit, the code leg
   checked out as its submodule), and run composed from that; or
3. run #190's **standalone** mode on code PRs (no `OPENREPOTOOLS_COMPOSED`), leaving composed
   acceptance to the assembly's own pin-bump PRs.

Which one is lane 1's decision under §7 item 7; the sketch above is item 2's starting point,
not a job that can run as it stands.

### 4.15 The register, logs, inventory and handoffs in `brett-wip` (read only)

`grep -rcE '/workspace/projects/openRepoTools|~/projects/openRepoTools|\$HOME/projects/openRepoTools'`
at brett-wip `c311a78`:

| File | Hits | What they are | Carry-over proposal |
| --- | ---: | --- | --- |
| lanes/LANES.md | 0 | Rows carry home `opensoft/openRepoTools` | none: the assembly keeps the name |
| lanes/log/openRepoTools-3.md / -1.md / -2.md | 32 / 11 / 11 | `dir /workspace/projects/openRepoTools` on STARTED/RESUMED/PAUSED lines (29 + 1, 11, 11 of them) | Append-only, never rewritten. They stay valid **if the assembly keeps this path**. If it moves, run one `lane-start --dir <new> openRepoTools <n>` per lane at its breakpoint; that writes the new `dir`. |
| `/workspace/projects/.lane-state/openRepoTools-{1,2,3}/trees/*.yaml` (beside, not in, brett-wip) | 18 / 8 / 14 sidecars | every row `checkout: /workspace/projects/openRepoTools`; 19 trees under `.claude/worktrees` | They stay true: they describe monorepo-history worktrees of the same repository. Translate each tree's delta through T016/T017 receipts, then retire it with `lane-worktrees sweep --yes`. The sweep's "landed" test compares against the assembly's default branch, where a monorepo branch's content never lands after the split, so expect **rescue to a bundle**, not "landed". |
| handoffs/openRepoTools/session-handoff-2026-09-13-lane-openRepoTools-3.md, migration-handoff-2026-10-06.md, …-2026-10-02-…-2.md, …-2026-09-16-…-1.md | 56, 42, 26, 24 | historical reads and paths | none: each live lane's next Rule 3 top block restates the current paths |
| handoffs/xFactory/session-handoff-2026-09-05-lane-opsXfactory-1.md | 11 | **"register writes via … `~/projects/openRepoTools/lanes-edit.sh`"**, the **checkout copy** | **Act before cutover:** this lane is live (PAUSED 2026-10-07T11:12:58Z, swap). That path disappears when the live checkout pulls the assembly main. Point its next handoff at the installed copy (`~/.local/bin/lanes-edit.sh` or `~/projects/xFactory/lanes-edit.sh`), and tell its owner. |
| handoffs/xFactory/attachments/opsXfactory-1/land-444.sh | 2 | `LANES_EDIT="${LANES_EDIT:-$HOME/projects/openRepoTools/lanes-edit.sh}"` (:329) | Same. A script that defaults to the checkout copy breaks at the split. |
| handoffs/xFactory/attachments/opsXfactory-1/briefs/DELTA-land-{444-r2,444-r4,444-r5-MERGE-WORKER,462}.md | 1 each | the same checkout-copy path in briefs | same |
| handoffs/xFactory/session-handoff-2026-09-0{2,5}…, -09-10b…, -09-12… (5 files); lanes/log/openxfactory-1.md (4), openXfactory-5.md (1), openXfactory-3.md (1) | 1-4 | mentions of the checkout and of its `lanes-edit.sh` | historical. Check whether any live lane still runs the checkout copy. |
| migration/openRepoTools/prep-20261007T100559Z/{worktrees.tsv, inventory-raw.json, status-openRepoTools.txt}; adopter-fix-20261007-iM20tv/{README.md, logs/lane-worktrees-add.log} | 9, 9, 1; 1, 1 | migration evidence | none: evidence of its time |

Outside brett-wip, nothing calls a tool by its checkout path. `~/.claude/settings.json` and
the shell rc files have no `projects/openRepoTools` (`grep` exited 1), and neither does
`~/.agents`. In `workBenches` there is one hit, a fixture string at
`devcontainer.test/test-claude-profile-lane-default.sh:282` and `:293`: text a fake prints,
naming a cwd. That is not a tool call.

---

## 5. What does not need to change, and why

- **How the tools find their helpers** (§4.1): every helper moves to `code/` with the tool.
- **`lane-start`'s directory rungs and `lanes-edit.sh`'s crossing test** (§4.2, §4.5): both
  already read `legs:` the way openRepoShape writes them, and the shell suite covers both
  (tests/test_lane_helpers.sh:1458-1469 for crossings, :5691-5704 for rung 5).
- **The workspace resolver, the register, logs and handoffs** (`link-estates:89-295`,
  byte-identical in four helpers): they are found through `workspace.yaml`, never from a
  checkout path.
- **`installed.tsv`**: it records destinations, not sources (§4.10).
- **Both hook entries**: they name the `~/projects/xFactory/lanes-edit.sh` link to the
  installed copy (§4.11).
- **`lanes-index`, `lane-rename`, `link-estates`**: no repository-relative path.
- **`set-lane-tree` and the inventory format**: absolute paths. An unvalidated `--checkout`
  already admits a code-leg tree.
- **`tests/run.sh`**: the lock, the run root and the venv name are not layout facts.
- **The dependency unit**: `upstream/openRepoShape`, `.gitmodules` and
  `contracts/openreposhape-pin.yaml` move together to code, so `test_upstream_pin.py`,
  `NEEDS_UPSTREAM` and `wip init`'s local template path stay true there.

---

## 6. What this branch carries

**One commit: this document** (T006 / T007 / T009 / T010 / T018). No shipped command changed.
Every behaviour change proposed in §4 changes what a command prints or does **today**, for
this repository or for the estate's existing triads. Each is written above as a proposal with
a sketch, for a ruling.

**Overlap with #190, and why this branch carries no test change.** An earlier draft of this
branch made the suite's roots shape-aware. Lane 1's PR #190 does the same work, more
completely, under other names. The draft was dropped before it was committed; its diff is
kept only in this lane's scratch directory.

| File | This branch's draft | #190 | Disposition |
| --- | --- | --- | --- |
| tests/conftest.py | `manifest_legs`, `checkout_roots`, `ASSEMBLY`, `SPEC`, `source()`; `$OPENREPOTOOLS_TEST_{ASSEMBLY,SPEC}_ROOT`; a missing root **fails** | `ROOTS`, `resolve_roots`, `ROOTS.path_for`; `$OPENREPOTOOLS_{CODE,ASSEMBLY,SPEC}_ROOT` and `_COMPOSED`; standalone **skips**, composed **refuses** | dropped; #190's definitions stand |
| tests/test_checkout_roots.py (new) | 9 cases on throwaway layouts, the paired layout among them | tests/test_test_roots.py (new, 573 lines) | dropped; the paired layout is a gap in #190 (§4.13) |
| tests/test_repo_hygiene.py | 23 reads through `source()` | `doc()`, `code_first()`, `tracked_files()` | dropped |
| tests/test_openrepotools_command.py | 1 read through `source()` | `ROOTS.path_for("README.md")` | dropped |
| tests/test_lane_helpers.sh, test_lane_helpers_suite.py | `SPEC_DIR` from `$OPENREPOTOOLS_TEST_SPEC_ROOT` (written, never committed) | `LANE_MANUAL` from `$OPENREPOTOOLS_LANE_MANUAL`, with skips | dropped; one read #190 leaves open (§4.13) |

---

## 7. Decisions for lane 1 (the migration owner)

1. **Bindings (T018):** keep every lane's `dir` at the assembly root and its home at
   `opensoft/openRepoTools`, and spell leg objects in full. The alternative is lanes homed on a
   leg, which changes the Claude project folder, and with it memory and `--resume`.
2. **Open OpenSpec claims (T018):** re-key `opensoft/openRepoTools:openspec/changes/<x>` to
   `opensoft/openRepoTools-spec:…` at cutover, by release and claim.
3. **Worktree visibility (T018):** adopt §4.4 proposal 1 (guidance) now. Rule on proposals 2
   and 3, which change the sweep and the daily report for existing triads too.
4. **Checkout-copy callers:** opsXfactory-1's handoff and its `land-444.sh` call
   `~/projects/openRepoTools/lanes-edit.sh`. Re-point them before the live checkout pulls the
   split.
5. **T007 landing order:** the root entry point goes in the root-split PR, and the code
   installer's pin resolution covers already-installed re-installs (context d) and
   `wip_shape_ref`'s silent `main` (context e).
6. **T006 contents:** the code leg's own `.gitattributes` and `.gitignore`; dated cap entries
   for AGENTS.md (316) and README.md (486); the root guidance's `code/` prefixes (§4.12).
7. **T010 context:** which spec and assembly commits a code CI run pairs with, and whether the
   code leg's CI carries the two extra checkouts or the assembly's CI runs the composed suite.
   **2026-10-09:** the §4.14 sketch exits 4 under #190's composed mode as it stands (#190 at
   `dbc6837`: `_leg_at_its_pin`, tests/conftest.py:259, refuses a code root the assembly does
   not pin, raised by `pytest_configure`, :404-412; `discover_assembly`, :159-172, finds only
   an assembly that mounts the code root). The composed job must check out an assembly whose
   code gitlink points at the PR's own commit, or a throwaway assembly built for the run that
   pins it, or use #190's standalone mode (§4.14, 2026-10-09 note).
8. **Measure in T008:** what `gh api …/contents/<path>` and `raw.githubusercontent.com` answer
   for a path under a gitlink. §4.10 derives a 404 and does not claim it.
9. **Standalone skip, or standalone fail (#190):** there are two readings of FR-008. #190
   skips a document read in a standalone code leg and refuses only in composed mode. That
   is sound only if the composed job is **required** on every code PR (T010); otherwise a
   code-only CI is green with the manual never read. This branch's dropped draft failed in
   both modes, which keeps a code-only CI red until T010 gives it context. Choose one, and
   write it into T010.
10. **Paired worktrees in #190:** decide whether `discover_assembly` should also accept
    `<assembly>/worktrees/<feature>/code`, with the spec root at `../spec` (§4.13), and
    move the third manual read (#190's test_lane_helpers.sh:6595-6596) inside its `if`, or
    a standalone code-leg run aborts on `ln_doc: unbound variable` (§4.13, measured).
