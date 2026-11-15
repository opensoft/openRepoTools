# Scoped claude-current CI delivery

Status: **owner-approved activation phase; live acceptance requires dated evidence**.
This revision selects the enabled policy. Omission still requires complete
effective protection and authenticated proof; the flag alone grants nothing.
The dated service/qualification record is
[CI-ACTIVATION-11](../../features/009-manual-two-pr-queue/openspec/activation.md).
Assembly/session adoption and release acceptance remain separate and excluded.

## What is prepared

`delivery-policy.json` selects `enabled: true`; explicit false remains rollback.
`tests.yml` retains its ordinary
events and parameterless reusable entry. Its original thirteen expanded jobs
retain their commands, environment, matrices, checkout modes and accounting.
Two read-only controls add an honest `openrepotools-delivery` check. The old
reviewed baseline is not regenerated: tests remove only the exact reviewed
needs/if projection before comparing every original job hash. The new controls
are separately frozen and mutation-tested.

The router executes only a main checkout with persisted Git credentials disabled.
Both control jobs independently acquire the validated immutable PR test-merge
object if their main-only fetch lacks it. They validate the PR ref and ordered
main/source parents without checking out or executing PR-owned policy. Retrieval
uses the fixed public repository/SHA with no credentials, ref/tag/FETCH_HEAD
updates; failure retains full work or fails an already-selected omission gate.
Missing policy bootstraps full CI. Disabled/unreadable policy and any incomplete
or uncertain proof select full. A router failure cannot silently skip full jobs.
The final gate requires all four actual full results, or independently rechecks
the same omitted-work proof. It never posts success under an unrun test's name.

Even an enabled flag cannot omit work until complete effective branch rules
require `openrepotools-delivery` from GitHub Actions (integration15368) and none
of `guard-launch-mode`, `tests`, `tests-no-submodule`, `package` remains required.
The ruleset GET and public branch metadata GET cover layered rulesets and classic
protection, including contexts and checks arrays. Missing, malformed or changing
classic evidence retains full. Existing Contents:read is sufficient for branch
metadata; neither endpoint needs administrative access or settings writes.
The router never writes rulesets, branch protection, permissions or bypasses.
The separately approved operator migration is recorded in CI-ACTIVATION-11.

## Initial supported scope

Only modified regular files `claude-current` (100755) and
`tests/test_claude_current.py` (100644), with unchanged modes. One or two
independent main-based same-repository members; no dependent-stack flattening.
Both exact body lines are required for future efficiency:

```text
CI-Shadow: claude-current
CI-Delivery: claude-current
```

Intent is not review or merge authority. Source routing requires live identity,
test-merge parents and exact-head successful fast-workflow/run/job/base-history
evidence. Complete candidate admission requires either the genuine clean managed
Codex receipt or the explicit [local-review receipt](#exact-head-local-review-receipts)
below, plus complete resolved threads. Quota replies, generic local summaries and
labels are not receipts. Local acceptance is never represented as a bot review.

Authenticated current run.path distinguishes ordinary tests.yml from reuse.
Reusable calls force full even though GitHub retains the caller's original event.
Release branches, nightly and manual runs force full. No release workflow changes.

Repeated canonical events on one unchanged head can leave several named fast
checks. A complete bounded configured-workflow catalogue identifies the unique
newest run by its per-workflow run_number; check array order and any older green
are not authority. All named check identities/suites must match that catalogue,
and exactly one current selected check must retain the complete run/job/source/
base-history proof. Recheck newest selection before proof. Missing current jobs,
unknown/truncated/ambiguous history and newest failures retain full; only existing
complete authenticated pending evidence may wait. No retry mechanism is added.

## Candidate, held queue and historical landing

The queue-push caller writes immutable admission and qualified JSON artifacts
from trusted verification into runner.temp, using the existing pinned upload
action. Records contain validated IDs, hashes and opt-in flags, not raw PR/review
bodies or secrets.
The CLI accepts no output path: it exclusively creates the fixed proof.json in
the canonical Actions runner.temp, refusing existing files and symlinks.
Readers bind numeric artifact ID/name/archive SHA256/run/head/repository/current
first attempt and reread provenance. Archives are size-limited,
one exact JSON member only, never extracted. All Git/API operations are bounded.
If a queue branch was deleted, the validated immutable public candidate commit
may be fetched by SHA from the fixed public repository, without credentials,
ref/tag/FETCH_HEAD updates or checkout. Unavailable objects retain full work.

A candidate-PR duplicate is omitted only for a genuine current caller plus its
admission record and independently revalidated live sources/Git chain. Actor,
branch prefix or draft status alone never exempts work. Without verified admission
no omission is allowed. Only authenticated pending fast receipts or an authentic live caller
awaiting admission may wait, for at most thirty ten-second intervals plus bounded
reads, within the existing fifteen-minute control-job budget. The observed fast
run43289185180 took3m19s, so a one-minute cap was insufficient. Absent opt-in,
unsupported scope, reusable/full-only callers, failed/malformed/unknown evidence
return full immediately. Waiting never qualifies a pending result: admission
remains success-only, and limit exhaustion retains full.

An authenticated pending fast observation returns only that existing bounded
wait after all initial identity/source/base-history/job/state checks. Completion
during those reads cannot qualify a mixed-state proof. A fresh poll revalidates
everything, including strict raw run/check rereads once all evidence succeeds.
Completed-proof drift still refuses; admission's default success-only behavior
and all wait limits remain unchanged. Pending work never grants omission.
The same no-proof wait applies to a genuine live candidate caller with no
admission artifact yet, even if it starts/completes during that observation.
Default readers and unauthenticated callers refuse; a fresh observation must
verify the actual artifact, whose complete proof and strict rereads are unchanged.

The parameterless candidate entry performs complete full CI and final live
verification before publishing qualified evidence. A unique **top-level**
`openrepotools-batch-heavy` waits for the whole call and rechecks live delivery
intent/reviews/identity. The new writer-requested manual queue
`openrepotools-claude-current` requires app-qualified fast + delivery on sources
and heavy on the combined candidate. It keeps protection injection at `queue`,
serial execution, max2 members, 60-second fill, 90-minute budget and zero retries/
splits. Older queues remain unchanged. No rule automatically enqueues anything.

Main-push reuse has a **separate historical reader**, not open admission with
invented push flags or now-closed PRs relabeled as open. It requires one unique
first-attempt successful authentic caller, the exact nineteen expanded jobs
(the original thirteen plus controls and verification/qualification), matching
immutable caller/callee SHAs, qualified record and unchanged policy/commands.
Every tested source head, ordered actual merge parent/prefix tree and GitHub
closed/merged record after completion must match. It searches only twenty recent
caller runs, with complete bounded per-head uniqueness checks; older/unknown
evidence falls back to full. Lookalike/manual merges, reruns, failures, skipped
jobs, changed policy or stale refs also fall back. New nested names are a
conservative contract to confirm in a later authorized canary, not live evidence.

## Owner-approved migration and qualification

1. Source preparation and local-review PRs have landed. Preserve current main's
   newer Sonar work and qualify the exact enablement head with full/reuse CI.
2. Brett approved the changed source merge floor below on 2026-11-13. Confirm the effective
   checks, queue config/service readiness and a qualified hosted or local review
   receipt path. Hosted Codex quota is not a prerequisite for the local path.
3. The approved migration installed app-bound `openrepotools-delivery` and removed
   the four legacy required contexts on 2026-11-13, with the live flag false.
   Target/effective readbacks preserved every unrelated rule and added no bypass.
4. Enable only via a separately reviewed config PR. Require failure/recovery and
   a user-authorized two-member live efficiency canary: fast-only source/candidate
   PR CI, one complete heavy caller, no duplicate full main run, exact prefix and
   final landed trees. Reject or roll back on uncertainty; do not claim success
   from source tests, labels or queue membership alone.
5. Reconcile governance and later assembly pins/composed CI/session adoption
   under their own approvals. Preserve running lanes and active plans.

Configuration publication, local fixtures, service recognition and completed
live qualification are distinct. Consult the dated evidence; do not infer a
successful canary or wider rollout merely from this enabled source revision.

**Changed source floor:** after activation, delivery success can mean fast
verification, not heavy integration. The named Mergify queue holds heavy; GitHub's
new required check by itself would not prevent a collaborator from directly
merging a fast-only source. Both Claude and Codex MUST use the named manual queue
for an authorized opted-in source, never direct merge. Queue-only usage is an
operator policy unless separately approved service controls enforce it. This PR
does not pretend otherwise or silently request a bypass/new ruleset control.

Rollback: an ordinary reviewed `enabled: false` change resumes every original
full job. Restoring legacy required contexts is a separate owner-approved setting
change. Neither rollback nor this phase changes release eligibility, apps,
installed tools, live sessions or lane ownership.

## Scoped manual operation

For an authorized current-head reviewed source, include both exact opt-in lines
above, preserve independent main-based topology and verify actual fast/delivery
success. Accept hosted review or the explicit local receipt below; a generic
summary or passing CI is not acceptance. Then a repository writer requests:

```bash
gh pr comment PR_NUMBER --repo opensoft/openRepoTools-code \
  --body '@mergifyio queue openrepotools-claude-current'
```

For the authorized two-member canary, request both independently ready members
close together, verify actual two-member order and leave heads/bases unchanged.
Do not direct-merge fast-only sources or edit a live queue branch. Record the
single complete heavy run, source/candidate/main CI and tested/landed prefix and
final trees. A singleton, reset, duplicate/full fallback or uncertain result is
not efficiency acceptance. Other files, dependencies and old full-only queues
retain their original full checks; this is not an arbitrary-lane fast path.

## Source-event description updates

Routing refusals emit fixed-vocabulary diagnostic codes to stderr, with the
verification stage. A source snapshot mismatch reports only mismatched field
names, never their values. Exception text, PR bodies and raw API payloads are
not logged. Diagnostics do not change the full-fallback result, retry policy,
proof schema, skip decision or merge authority. They distinguish early metadata
refusals from incomplete fast evidence and reread races before a fresh attempt.

Unrelated description prose may differ between the triggering source event and
the live PR, for example when a summary is appended before CI starts. Both
descriptions must independently contain the unique supported shadow/delivery
opt-ins and neither may declare a dependency. Every other snapshot field except
the bounded generated hint below, and all Git/fast provenance checks, remain exact. Later live rereads still compare
the complete body strictly; this does not ignore changes during verification,
trust an editing actor, grant queue authority or widen eligible files/actions.

At the initial source or genuine candidate PR comparison only, generated
`merge_commit_sha` hints may be missing/null or equal the trusted workflow
`GITHUB_SHA`. A different full-SHA hint qualifies only when an authenticated
immutable Git-commit read proves its returned identity, exact two ordered parents
and tree equal the actual tested merge. At most two distinct object lookups are
needed for the initial pair of hints, with no new permission, ref write or retry.
Both hints must qualify; unavailable, unknown, malformed or semantically different
objects retain full even when both snapshots agree. These hints never identify the tested
commit: the actual commit and ordered current-main/head parents are still
independently verified. At only the initial candidate comparison, descriptions
may differ when both are strings or null. Candidate prose grants no member,
review or admission authority; those proofs remain independently mandatory.
Invalid description types retain full. Subsequent live rereads compare the original
PR strictly, including the full body and generated hint; no race is normalized.

The R5 source pair qualified fast-only and formed a genuine two-member batch,
but its draft candidate selected full fallback. Edit history shows a description
edit before that decision, not the exact first failing historical predicate.
The bounded initial-description repair preserves every other identity and all
real proof checks. Candidate snapshot diagnostics report field names only;
known metadata/type/reread refusals use fixed codes, never body or hint values.
The failed specimen stays failed and stopped. A new reviewed/full-CI-qualified
repair and genuinely fresh source events are required for another canary.

R6 subsequently proved fast-only sources and real two-member admission, but
candidate77 logged candidate-reread at its final PR/branch/caller consistency
check. A Mergify description edit occurred in the same second; the exact first
differing raw field is unknown. That specimen was cancelled/dequeued before
landing and remains failed efficiency evidence, not a completed heavy result.

Only after complete candidate authentication, real admission and independent
live sources qualify may a still-valid changed final PR/caller view return the
existing no-proof bounded wait. Each observation repeats all verification.
Accepted proof still requires raw equality; no description, hint or caller data
is normalized into acceptance. Changed branch heads, invalid/moved identities,
malformed body/hints, failed/foreign/rerun callers and invalid source/artifact
proof retain immediate full refusal. Generic API failures do not become retries.

The route keeps its existing thirty ten-second waits and full exhaustion result.
Candidate omitted-work gate verification can use that same per-invocation bound,
but must match the original route mode/proof digest; exhaustion or a different
proof refuses. Source gate behavior is unchanged. Fixed pending diagnostics name
only pull_request/caller categories, not values. No nested budget, workflow,
permission, schema or flag changes. Qualification and genuinely fresh R7 events
remain required; never rerun or requeue failed R6 into clean acceptance.

## Exact-head local review receipts

This is an **alternative review contract**, not activation or merge
authority. Run `pre-pr-review`, `pr-review` or `branch-or-pr-review` locally in
Codex against the exact current PR head and base; resolve findings and re-review
before acceptance. Preserve the report's findings, resolution and validation.
An existing repository writer then explicitly accepts that report by publishing
a **new top-level PR comment** containing only this marker and JSON fence:

````text
<!-- openrepotools-local-review:v1 -->
```json
{
  "schema_version": 1,
  "repository": "opensoft/openRepoTools-code",
  "pull_request": 123,
  "head_sha": "REPLACE_WITH_CURRENT_40_CHARACTER_HEAD_SHA",
  "base_sha": "REPLACE_WITH_REVIEWED_40_CHARACTER_BASE_SHA",
  "reviewer": "codex-local",
  "skill": "pre-pr-review",
  "status": "accepted",
  "unresolved_findings": 0,
  "findings": "Describe the actual findings, or state that none remain.",
  "resolution": "Describe fixes and the exact-head re-review, or why no fixes were needed.",
  "validation": "Record actual commands/results and distinguish local from hosted CI."
}
```
````

The example is not a receipt: replace all identities and report text with real
evidence. A receipt for these configuration PRs cannot qualify a later source
head. Do not post one automatically from passing CI, a PR body, a profile launch
or the mere completion of a review agent. Publication is an explicit acceptance
act by a writer with authority for the task, not permission to merge or enqueue.

GitHub must identify the publishing author as a User; the live collaborator
permission GET must return that same login/numeric ID and `write` or `admin`
(`maintain` maps to `write`). No author allowlist, new app grant or workflow write
permission is introduced. Unknown/unavailable permission evidence refuses.
This is authenticated operator attestation, **not** cryptographic proof of local
model execution or independent human approval. All existing GitHub protections
remain applicable, including any independently required reviewer approval.

The whole body is bounded to 16 KiB; its exact JSON keys/types/schema and skill
must match the contract. Reports must be nonempty and at most 4,000 characters
each. The PR URL, server comment ID, repository, PR number, current head and base
must match. Both REST timestamps must agree and complete GraphQL comment metadata
must show `lastEditedAt: null` (including same-second edits). All comment IDs and
bodies must agree across REST and GraphQL before local selection or hosted
fallback. Same-count replacements and ordinary comments edited into new local
decisions refuse too. Never edit a receipt: publish a replacement.
The newest authorized local comment by creation time,
then numeric ID, controls acceptance; stale/malformed/dirty or revoked latest
local evidence refuses even if an older local/hosted approval is clean.

To revoke, publish a new receipt with `status: revoked`, the relevant identities
and an honest report explaining the problem. Stop queue operations; a new valid
local acceptance after re-review is needed to supersede it. Head/base changes
always require a fresh review and receipt. Bot/non-writer lookalikes confer no
authority; no authorized local receipt leaves the existing hosted path intact.

Fewer than 100 total comments, at most ten local-marker comments, complete
resolved review threads and complete unedited comment metadata are required.
Saturation, ambiguity, API failure or receipt/access drift on the final recheck
refuses; never truncate history, clear comments or weaken checks to qualify.
Normal full-CI delivery remains the fallback. Report text is hashed for snapshot
comparison, never executed, fetched or copied into candidate proof artifacts.
Admission, final heavy verification and the separate historical landing reader
retain their existing roles; review acceptance does not replace heavy CI.

## Primary references

- [Effective branch rules and permissions](https://docs.github.com/en/rest/repos/rules)
- [Caller context in reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows#calling-a-reusable-workflow)
- [Attempt-specific job inventory](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run-attempt)
- [Artifact API](https://docs.github.com/en/rest/actions/artifacts)
- [Mergify queue rules](https://docs.mergify.com/merge-queue/rules/)
- [Two-step qualification](https://docs.mergify.com/merge-queue/two-step/)

Reference proof patterns: OpenBenches5df4fa0, project-stack-ci.py. Its scopes,
review trust and effective GitHub rules are not copied as authority here.
