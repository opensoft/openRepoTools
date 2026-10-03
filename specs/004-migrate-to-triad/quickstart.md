# Review this migration plan

Read [plan.md](plan.md), then the [resolved adoption mapping](../../openspec/changes/migrate-to-triad/adoption-plan.yaml)
and [work inventory](inventory.json). The mapping is for the recorded source
main only; implementation and live feature transfer have not been attempted.

From the original source checkout, the planning validation is:

```sh
python3 upstream/openRepoShape/adopt-project.py check \
  --source . \
  --plan ../openRepoTools-worktrees/004-migrate-to-triad/openspec/changes/migrate-to-triad/adoption-plan.yaml
```

From the migration worktree, validate governance artifacts:

```sh
openspec validate migrate-to-triad --strict
git diff --check
```

Route project CLIs through the declared bench. If source main changes,
regenerate the plan using `adopt-project.py plan`, retain reviewed resolutions
and follow-ups, then recheck. Do not change the baseline field to suppress a
stale-plan finding. Do not run real `execute` as a planning check.

Before execution, complete Gates A/B and review the actual frozen baseline,
visibility, mapping, follow-ups and preservation receipts. The standard requires
explicit approval before repository creation. All execution tasks are open in
[tasks.md](tasks.md); the migration does not require recreating feature 001's
specifications or claiming its unfinished runtime work is complete.
