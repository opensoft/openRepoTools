# Tasks: governance and Speckit handoff

This checklist tracks approval, the single Speckit feature link, the acts
outside the repository, landing, and archival readiness. It holds no
implementation steps. The only executable task list will be
`specs/006-release-pypi/tasks.md` (see "Speckit Handoff"). Tick an item here
only when the step it names has actually happened, and with its evidence.

## 1. Proposal, review and planning artifacts

- [x] 1.1 Record the proposal with Brett Heap's decisions (#228's body) and
  his answers of 2026-10-17T21:51:50Z (#228 comment 6241784787); verify
  proposal.md cites both and the alignment review's fixes are in it
  (commit `698cf30`).
- [x] 1.2 Apply the council's verdicts: VALID 1–9 in proposal.md, NOTED
  N1–N5 and dismissed D1–D3 in clarifications.md, and the lead's correction
  to VALID 4 after #186 comment 6242560541; verify commits `56669c1` and
  `ea306de` are on `origin/006-release-pypi`.
- [x] 1.3 Record the two delta specs and design.md; verify
  `openspec validate release-tags-pypi --strict` reports the change valid
  and `openspec status --change release-tags-pypi` shows proposal, specs,
  design and tasks done.
- [x] 1.4 Record Brett Heap's word on the workBenches position, (a), (b) or
  (c); verify the proposal's "workBenches condition" bullet states his
  choice and is the only bullet that changed. Resolved 2026-10-18: Brett
  Heap chose (c) ("go with (c)"), and lane openRepoTools-3 filed
  opensoft/workBenches#165. The proposal's position (c) bullet states
  that, in the commit that ticks this item, and no other proposal bullet
  changed in it.

## 2. The single Speckit feature

- [x] 2.1 Create the one Speckit feature for this change with
  `/speckit.specify`; verify `specs/006-release-pypi/spec.md` exists on
  branch `006-release-pypi`, and that no other Speckit feature names
  `release-tags-pypi` or #228. Done 2026-10-17 at `eb12177`: `grep -rl` for
  either name under `specs/` finds only `specs/006-release-pypi/`.
- [ ] 2.2 Plan and task the feature with `/speckit.plan` and
  `/speckit.tasks`; verify `specs/006-release-pypi/tasks.md` exists, that
  every task carries a tier, a `files:` list and a `verify:` command, and
  that together they cover every requirement of both delta specs and every
  decision in design.md.
- [x] 2.3 Fill in the handoff below with the feature's final path; verify
  "Speckit Handoff" names exactly one feature, branch and task path, and is
  no longer marked pending. Done 2026-10-17 at `760281b`; the task path
  exists since `01ff6d6`.

## 3. Landing in opensoft/openRepoTools

- [ ] 3.1 Land feature 006's PRs by squash once each is independently
  reviewed and green on Linux CI (decision 4); verify each LANDED line
  names its squash commit on `main`.
- [ ] 3.2 Confirm the order lane openRepoTools-1 depends on: #228's PRs
  land before lane 1's single rehearsal and regenerated adoption plan (#186
  comment 6242560541, D1); verify the rehearsal's baseline commit contains
  #228's last squash commit.

## 4. Rehearsals, on Brett Heap's word

- [ ] 4.1 Brett Heap creates the `testpypi` and `pypi` environments in
  `opensoft/openRepoTools` (required reviewer brettheap, deployment limit the
  tag pattern `v*`) and the test.pypi.org pending publisher; verify the
  release build's environment gate passes on a branch dispatch.
- [ ] 4.2 Run the branch rehearsal; verify every build check and the install
  check pass, and no upload job runs.
- [ ] 4.3 On his word for the tag `v1.1.0rc1`, and his approval of the
  `testpypi` deployment, run the TestPyPI rehearsal; verify TestPyPI serves
  exactly the recorded digest, the install check passes, and the `pypi` job
  is skipped.

## 5. The cutover's dependencies (#186, lane openRepoTools-1)

- [ ] 5.1 Lane openRepoTools-1's adoption plan at openRepoShape v1.1.0
  carries this change's entries; verify `pyproject.toml` and `src/` go to
  code, `.github/` to code, and `docs/release-notes/` to spec, and that the
  plan states the cutover invariants: the four job ids, no release step
  reading across legs, and no `readme` in `pyproject.toml`.
- [ ] 5.2 After `execute`, `code-0001` is the code leg's first commit;
  verify that `LICENSE` on `openRepoTools-code`'s `main` is blob `261eeb9`
  before the first `package` run there, and record the check (lane
  openRepoTools-3).

## 6. v1.1.0, after `execute`, on Brett Heap's word

- [ ] 6.1 Brett Heap's code-side acts: in `opensoft/openRepoTools-code`,
  the two environments and the `v*` tag ruleset; the test.pypi.org
  publisher pointed at `openRepoTools-code`; the pypi.org pending publisher
  for it, the only one on pypi.org; verify all four exist before any v1.1.0
  dispatch.
- [ ] 6.2 Tag v1.1.0 on `openRepoTools-code`'s `main` once that commit's
  `tests.yml` runs have all finished and the newest is green; dispatch the
  release and take Brett Heap's approvals; verify PyPI serves exactly the
  recorded digest.
- [ ] 6.3 Create the GitHub Release from `docs/release-notes/v1.1.0.md`
  after PyPI serves 1.1.0, then cut `release/v1.1` at `v1.1.0`; verify both
  exist and the Release's body is the notes file's text.
- [ ] 6.4 Open the assembly's README PR with the pipx route's text once PyPI
  serves 1.1.0 and the workBenches condition holds (lane openRepoTools-3);
  verify the README's text matches the proposal's.

## 7. Verification and archive readiness

- [ ] 7.1 Accept the Speckit feature's evidence; verify every task in
  `specs/006-release-pypi/tasks.md` is checked, with its verify command's
  result recorded.
- [ ] 7.2 Archive only once v1.1.0 is published and the README PR has
  landed or been recorded as waiting on the workBenches condition; verify
  `openspec validate release-tags-pypi --strict` still passes before
  `/opsx:archive`.

## Speckit Handoff

- **Feature:** `006-release-pypi`
- **Branch:** `006-release-pypi`
- **Tasks:** `specs/006-release-pypi/tasks.md`
- **Specified:** 2026-10-17, by `/speckit.specify`
  (`specs/006-release-pypi/spec.md`)
