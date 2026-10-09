# Gate B rehearsal, run C, at the post-landing source — October 8, 2026

**Task:** T003–T005 rehearsal evidence under [#186](https://github.com/opensoft/openRepoTools/issues/186).
No task is checked complete by it.
**Tool:** openRepoShape `7f84ca42ca86a8902928345109d2bf6bad87bd91` on its `main`
(`compare main...7f84ca4`: `identical` at measurement).
**Source:** main `837928a1029ac53b050a9bdcbc0ef4055b10719b`, read with `git ls-remote`
at 2026-10-08T20:54:21Z just before cloning. It is `c4864ac` plus #187, the
planning documents squashed as `44983ce`, and #188, the repin to `7f84ca4`
squashed as `837928a`.
**Private receipt ID:** `adopter-fix-20261008-1HztL0`.

**Run C supersedes nothing.** Runs A (`c4864ac`) and B (the repin candidate
`e43b243`) stand as recorded in
[adopter-rehearsal-2026-10-07.md](adopter-rehearsal-2026-10-07.md). That file
is on branch `004-migrate-to-triad-rehearsal` and reaches main with the
combined evidence PR. Run C is the same rehearsal, with the same tool and the
same resolutions, at the source that now exists after both landings. It is
also the durable rehearsed arrangement that T006–T010 take as input. It is
kept host-local outside every repository so it survives a bench restart.
Clone paths, local remote URLs, exact command lines and complete logs stay in
the private receipt.

**Dated 2026-10-09, after #192 landed (#193 items 8 and 13):**

- **Where the records are.** #192 brought this file and run C's plan to
  main. The 2026-10-07 record has been on main since #189 (`63810dd`), not
  on a branch as the paragraph above says.
- **What run C superseded.** No record: runs A and B stand as recorded. Its
  plan did replace run B's as the
  [mapping](../../openspec/changes/migrate-to-triad/adoption-plan.yaml), in
  merge `1a26463`. On main that link opens run C's plan from both records.
  So "On this branch" in the mapping section below holds for main, and the
  2026-10-07 record's "On this branch, the mapping is the regenerated run B
  plan" held only on its own branch. Run B's plan stays in history at
  `63810dd` (blob `f1067e3`). Neither plan is the cutover plan.
- **Runs A and B are gone from the bench.** The bench restart of
  2026-10-08, at about 09:45Z, cleared `/tmp` (#186 comment 6068861167).
  Both runs were built in a session scratch directory there, as the
  2026-10-07 receipt's README records, so their disposable repositories are
  gone and that receipt's logs are their only record. That is why run C is
  kept host-local.
- **An observation left out.** The run C comment on #186 (6068938765)
  noted that `openspec validate migrate-to-triad --strict` with `openspec`
  1.2.0 fails on pristine `837928a` too (`ADDED "Installation retains the
  public interface and one revision" must contain SHALL or MUST`), so run C
  does not cause it. The bench's `openspec` is now 1.13.1. On 2026-10-09
  the same command exited 0 on `837928a` and on `71b05cb`, #192's head,
  whose tree its squash `1abee1d` carries unchanged.

## Setup

- **filter-repo:** `git-filter-repo` 2.47.0 from a private venv.
  `python3 -m venv` refused with
  `The virtual environment was not created successfully because ensurepip is
  not available.` So the venv was created with `--without-pip`. The wheel
  came from `pip download` with SHA256
  `2cd04929b9024e83e65db571cbe36aec65ead0cb5f9ec5abe42158654af5ad83`, matching
  the recorded value. That exact file was installed into the venv with
  `--no-index`. The venv's `git-filter-repo` came first on `PATH`, and
  `git filter-repo --version` printed `a40bce548d2c`.
  - *Corrected 2026-10-09 (#193 item 12):* this bullet first gave the cause
    as "the rebuilt bench has no `ensurepip`", and the bench contradicts it.
    Its dpkg log has `python3-venv` and `python3.12-venv` installed on
    2026-09-23 at 00:18:06Z, before the 2026-10-08 boot.
    `/usr/bin/python3 -m ensurepip --version` prints `pip 24.0`, and
    `/usr/bin/python3 -m venv` succeeds (lane 2, #186 comments 6072333212
    and 6072724043; measured again on 2026-10-09). The refusal itself is
    real: the receipt's setup log records it. Its cause is not established.
    The `python3` the writer ran was the first on its `PATH`: the venv's
    `pyvenv.cfg`, in run C's host-local arrangement, records a user-local
    `python3` based on `/usr/bin/python3.12`. That entry is no longer on
    the bench, so the refusal cannot be retried as it ran.
- **Tool and source:** a fresh clone of openRepoShape at `7f84ca4`, unedited
  and clean afterwards, ignored files included. A fresh `--single-branch`
  clone of main, with one worktree and no linked worktrees. Its nested
  `upstream/openRepoShape` was not initialized.
- **Transport:** limited to local files (`GIT_ALLOW_PROTOCOL=file`). `gh` and
  `curl` shims refused and logged; no call was logged. The recursive clone
  reached code's nested openRepoShape through a local mirror of the tool clone.

## Mapping (T003)

Since the run B source, the tree gained 20 files and no new top-level path:

- 13 under `specs/004-migrate-to-triad/`;
- 6 under `openspec/changes/migrate-to-triad/`, including the October 4
  `adoption-plan.yaml` itself;
- `openspec/config.yaml`.

The pin change is the one run B already carried; its contract blob is
identical. `plan` left the same 18 questions. All 22 resolutions of the run B
plan were reapplied verbatim: the October 4 mapping's 19, plus
`lane-worktrees` and `lanes-index` to code and `ideation/` to spec. Every
other entry kept the tool's leg, unchanged from run B. The 20 new files are
spec through the existing `openspec/` and `specs/` entries.

The tool's follow-ups, re-derived over the resolved entries, are identical to
run B's. The ten reasoned follow-ups are unchanged except the source file
count, now 120. `check` printed `plan ok` for the executed plan and again
for the published copy. On this branch the
[mapping](../../openspec/changes/migrate-to-triad/adoption-plan.yaml) is that
published copy. It differs from the executed plan only by its header,
`local_path: .`, and the two closing status fields
(`execution_authorized: false`).

*Added 2026-10-09 (#193 item 10):* `check` validates against the source
clone's local `main`, not its `HEAD`. In openRepoShape `7f84ca4`'s
`adopt-project.py`, `_default_branch` (:288) takes the branch name from
`origin/HEAD`, and `git rev-parse` of that name (:256-257) is the commit
compared with the plan's source commit (:1026-1032). This plan therefore
passes `check` only in a clone whose local `main` is `837928a`. Against any
newer `main` it exits 1 with `FINDING plan-stale: the plan was written
against 837928a1029a but main is now at …`, whatever `HEAD` is checked out.
That includes main once this plan is on it: a plan cannot name the commit
that carries it. Measured on 2026-10-09 with this plan and a fresh clone,
local `main` at `63810dd` gave that finding and exit 1, also with `HEAD`
detached at `837928a`. Local `main` moved to `837928a` gave `plan ok` and
exit 0, also with `HEAD` detached at `63810dd`.

## Run C — main `837928a`

`execute --local-remote-dir … --work-dir … --yes` exited **0** and printed
`adoption verified: every source path is in exactly one place`.

| Source accounting (the standard's table) | Original entries |
| --- | ---: |
| Spec | 65 |
| Code | 49 |
| Assembly root | 6 |
| Dropped | 0 |
| Total | 120 |

The standard reported 18 added assembly paths, the same set as runs A and B.
An independent comparison matched path, mode, object type and object ID for
all 120 entries of `ls-tree -r 837928a`: 65 spec, 49 code and 6 root. It
found zero missing, duplicate or misplaced owners and no leg extras. The
gitlink `upstream/openRepoShape` at `7f84ca4` has exactly one owner, code.

| Disposable repository | Commit | Kept commits |
| --- | --- | ---: |
| Spec | `593250d600ca291f610671d993c2a6fc36cd690e` | 35 |
| Code | `73b04d637634f897ad24e22ee4c12bed287172d6` | 88 |
| Assembly split | `69b89245029d0339afd3317df7c9b1b3bbaf7fc1` | — |

Spec gained one kept commit, the planning squash. Code's tree digest
`b4940a13bd8ecbe2d1c6ed49368d1545d1a5f1f7a92623c7fe11ac1cb3617604` has the
same prefix run B recorded. Only the code commit identities differ, because
the repin landed as a different commit. The split commit's only parent is
`837928a`.

The recursive clone, `scripts/bootstrap.py` (`bootstrap ok`) and the
naming, manifest and pins validators all passed, and every tree was clean
afterwards. Code's nested openRepoShape was checked out at `7f84ca4`, matching
code's `contracts/openreposhape-pin.yaml`. The pinned checkout's own
`scripts/repo_shape.py` recomputed
`3be52767e727d924dd05f9e78b18eb70f1682fe48614fab519f85331eeff5fa8`, which
matches the contract.

The source clone was unchanged except for the one documented local-mode ref,
`refs/heads/adopt/three-repo-shape` at the split commit. That ref and the
two leg remotes are left in place, read-only, as the input to T006–T010.

## Private log SHA256s

- Execute: `f766bc707c88272598b6947ae850d9d42922763f0820940a0202ebcbc1835a46`.
- Bootstrap: `ea2be5dc7455c869a48c7bd36d73024c53ef6f233916cbf8e67ba897b3b732f7`.
- Independent comparison: `d3acbcd6274267eeadd36892bdbe2a08a9b08269d3215b373f84d630b91da007`.

The receipt holds every log with its SHA256. None was over 2 MB, so none was
trimmed.

## Remaining gates

**Gate B is not complete.** T006–T011 remain:

- root collisions and leg guidance;
- the installer entry point;
- composed tests and CI;
- the restore and rollback rehearsal.

Gate A preservation must be refreshed at a coordinated breakpoint. Before
Gate C, regenerate the plan from the frozen source that is actually chosen.
Brett Heap's explicit Gate C approval must name the revisions, the leg
repositories, their visibility and the final plan.

This evidence authorizes no real conversion, repository creation, merge,
default-branch move or lane rebinding.
