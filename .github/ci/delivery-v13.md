# Reviewed initial v1.3 test-only delivery

This source sets `delivery-v13-policy.json` to **true** for the exact registered
P05/P06 pair only. Check the actual default-branch policy after the separately
reviewed code PR merges; a private branch, spec merge or enabled flag alone is
not omission/admission authority or a live acceptance receipt. Existing
claude-current behavior is unchanged. All other v1.3 work retains full CI.
The shadow observer still cannot grant skips, qualification, admission or merge
authority, and its own `efficiency_enabled` remains false.

## Trusted proof boundary

The delivery-specific validator reads the immutable P05/P06 registry data,
never shadow observations. Under the approved staged rollout it requires all of:

- P01 #88 at its exact projected head, actually merged into main, with the
  frozen required-PostgreSQL workflow/baseline and empty P01 markers. The original
  13 integration jobs are not replaced. An optional explicit `foundation` binds
  an independently qualified actual-main ancestor descended from P01 and all
  four regular-file helper blobs. Helpers/modes must remain unchanged from that
  exact epoch; controls/markers remain frozen from original P01. Missing epochs
  retain the original P01-only freeze. No moving-main discovery, rehash or later
  helper drift is implicitly approved.
- The exact projected source PR/head/branch and complete regular-file/empty-marker
  cut. The default is one P01 child. An optional trusted `source.commits` list
  pins one to three unique full SHAs ending at `source.head`; every commit must
  have exactly the previous registered parent, starting at P01, and every
  cumulative prefix must obey the same cut. No unpinned fix, merge, reordered
  history or temporary off-scope revision qualifies. No arbitrary v1.3 PR qualifies.
- An open, ready, same-repository source targeting current main, with its
  dependency independently resolved by the owner. The preparer does not edit,
  rebase, retarget or merge lane-owned PRs.
- Unique matching `CI-Shadow: sql-register-v13`,
  `CI-Delivery: sql-register-v13` and `CI-Task-Set: P05` (or `P06`) body lines.
  These are intent, never review or permission.
- Existing authenticated exact-head fast-run/base-history evidence; complete
  clean hosted Codex or explicit local-review receipt and resolved threads for
  candidate qualification. Owner review waivers are not counterfeit Codex proof.

An immutable P01 child need not contain later main policy commits. The verifier
reconstructs its clean merge against current main, preserving unrelated main
content, and validates each actual candidate prefix's cut. It never flattens a
genuine unlanded dependency. Mixed domains, changed heads, wrong markers, modes,
paths, prerequisite drift or uncertain evidence refuse; full CI is the fallback.

The candidate proof retains the existing bound of two independent members and
adds `scope: sql-register-v13` only for v1.3. Legacy proof schemas remain exact.
Unknown/mixed/tampered scope refuses. Existing authenticated first-attempt
admission/qualified artifacts, complete heavy-job inventory, final live source
recheck and separate historical landing reader remain required. Historical proof
reconstructs each actual merge record/prefix tree; closed PRs never become open
admission. Policy/foundation changes after qualification retain full main CI.

## Publication versus activation

Source publication, including the enabled flag, is not a live acceptance receipt
or a queue command. The full-CI parity caller watches the validator, policy,
runbook and tests; its jobs and the parameterless complete suite are unchanged.
No release workflow is touched. The four existing queues are unchanged.

The registry points to merged spec revision
`a3366afcc059b4686c990f4715c36dac9b1db05b` and qualified immutable epoch
`f0070e009bc6f183904549b69c710ef3982ca6e6`. Main full run43735780675 and
same-tree run43734991157 passed15/15; matching real-engine smoke43733481662
verified session clone/query and SIGINT stop/restart/query. Later helper changes
require renewed matching qualification, not automatic advancement of this epoch.

| Profile | Source | Task set and tasks | Maximum files including markers |
| --- | --- | --- | --- |
| P05 | #92, `2a02cd9eba113329870ed7eba6efd470375b8739` | S007-07: T217, T235, T259 | 4 |
| P06 | #94, `bcc8858bf587fbe86b00264b41caca1b39ccfc72` | S007-09: T212, T256, T225, T242 | 6 |

Each source has its exact two-commit history pinned in the registry. P05/P06
owner READY reviews are records6898716602/6898717748, accepted together in
issue165 record6898740891. Their full runs43726550505/43729068826 passed15/15.
Lane2 consent6898422904 applies only to these exact heads with the required
reviews/full CI and lapses on a head change. These receipts do not waive the
fresh source-event, actual enabled-policy, queue and live-acceptance gates.

## Manual heavy-held queue

`openrepotools-sql-register-v13` is manual-only, writer-requested, serial and
limited to at most two members, with no failure splitting or automatic retries.
It uses queue protection injection, not `none` or `merge`. Entry filters require
main-targeted same-repository ready sources, supported P05/P06 v1.3 headers,
test-module/marker paths and app-qualified fast/delivery success. These coarse
filters are NOT exact-head profile acceptance. The trusted source/candidate
verifier still independently checks the registered head, lineage, full cut,
prerequisite, review, fast evidence, live rereads and complete heavy artifacts.
The queue cannot merge without app-qualified `openrepotools-batch-heavy` success.
While the actual delivery flag is false, v1.3 candidate proof refuses.
The false flag blocks qualification and merge through this heavy-held queue,
not a repository writer's ability to request preliminary manual queue entry.
Such a request remains unauthorized before enabled-policy and owner-consent
gates pass. The queue is not claimed
to be mechanically inert; no automatic entry or independent admission-consent
status is introduced or inferred from its coarse filters.

This source alone authorizes no queue command. The operator must verify fresh
owner consent for the exact two
heads, use only this named queue for fast-only sources and keep both members
stable through qualification. The service's batch size/wait alone does not
guarantee an exact two-member selection; live proof must show the actual members
and one accepted heavy run. A fast/delivery check is never direct-merge authority.

Before admission, verify actual required-engine qualification, current exact
owner heads/reviews/consent, actual enabled main and its registry, effective
app-qualified protection and Mergify readiness. Coordinate an idle merge/admission
window without resetting an active owner candidate or imposing a repository freeze.
Owner full-CI product batches are not the efficiency canary. If a batch changes
the frozen foundation, efficiency falls back to full until a separate reviewed
revision and matching real-engine qualification; never silently follow main.

Lane1 alone adds the three matching intent lines to each owner PR and triggers
a fresh canonical source event without rewriting the head. A body edit alone
does not trigger the opened/synchronize/reopened CI workflows. Do not edit bodies
while any candidate is active. Recheck the current main/base-history snapshot
and verify actual fast-only CI on both exact sources, not old full/fast statuses.

Reopening can regenerate GitHub's test-merge commit ID without changing its
ordered parents or tree. The trusted router may reconcile only that initial
generated hint using authenticated immutable commit-object equivalence; it does
not ignore a stale base, changed source or later live reread. Unknown/malformed
objects retain full. A full-fallback preparation event is not fast-only evidence
and must not be reported as an accepted efficiency canary.

The same unchanged head may also have historical fast-workflow checks. Only the
unique newest canonical run from the complete bounded configured-workflow
catalogue can supply fast proof, with its own matching check/run/job and source/
base-history evidence. Historical successes cannot cover a failed, pending,
missing, ambiguous or unrecognized newest receipt. A missing current job remains
immediate full fallback; no extra waiting or queue authority is introduced.

Only after all gates above pass under the approved owner-consented canary, a
repository writer may request the named queue on both independent members:

```sh
gh pr comment 92 --repo opensoft/openRepoTools-code \
  --body '@mergifyio queue openrepotools-sql-register-v13'
gh pr comment 94 --repo opensoft/openRepoTools-code \
  --body '@mergifyio queue openrepotools-sql-register-v13'
```

Neither this example nor an old consent is reusable admission authority. Verify
the actual candidate contains exactly both registered heads in its recorded
order; a singleton, retry or partial landing is not a clean two-member result.

Live acceptance must show fast-only source and candidate PR CI, exactly one
complete heavy caller per accepted batch, no duplicate full main run, and matching
tested/landed prefix and final trees. Local fixture enablement is not that test.
Rollback is a normal reviewed false policy. Assembly pins, composed acceptance,
SAFE-gated shared-checkout adoption, tools, sessions and releases remain separate.
Passing this first pair is initial test-only acceptance, not blanket v1.3
adoption. Wider task-set profiles require the next reviewed stage and its proof.
