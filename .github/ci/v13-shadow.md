# v1.3 qualification and disabled shadow

This observer is not an efficiency activation. Ordinary full CI remains the
fallback except for the separately qualified exact delivery scope. The
parameterless full-CI qualification caller still runs
every original job when these control files change. No delivery router, verifier,
queue or required check consumes the observer's output. Existing claude-current
behavior is unchanged. The observer itself adds no queue or permission to omit
work. A [separate manual v1.3 queue](delivery-v13.md#manual-heavy-held-queue)
does not consume observer output or itself turn the independent delivery flag on.
Its preliminary entry filters and operator-consent boundary are separate from
the trusted heavy qualification required before that queue can merge.

The canonical proposal, design, requirements and implementation checklist live
in the spec leg at `openspec/changes/qualify-v13-taskset-ci/`. This projection is
not a replacement for feature007's task ledger or owner-approved task cuts.

## Observation contract

`v13-shadow-profiles.json` explicitly sets `efficiency_enabled: false`. Its
P05/P06 projection is bound to reviewed spec revision
`a3366afcc059b4686c990f4715c36dac9b1db05b` and the exact owner-reviewed cuts
described in the delivery runbook. This registry update does not enable the
observer or make its observations a grant. Exact named regular added/modified tests and
the exact cut's empty added markers can be observed. Mixed/control files,
deletions, renames, executable/symlink changes, missing/extra/nonempty markers,
marker-only edits and arbitrary dependent stacks cannot. The exact known-P01
exception below observes only pinned child cuts after P01 lands. Unsupported
or stale contexts fall back conservatively.

An independent source PR body (or source push commit message) can request an
observation with exactly one of each line, for example:

```text
CI-Shadow: sql-register-v13
CI-Task-Set: P05
```

These lines request **no skips, queue admission or qualification**. CRLF and
trailing horizontal whitespace are tolerated; duplicates/other scope names are
not. Labels and the actor do not grant authority. Closed/dequeued events,
candidate, main and reserved-branch pushes never receive a proposed cut.

## Exact known-P01 source topology

The disabled projections additionally bind the observed real cuts:

| Cut | Source PR | Immutable head | Source branch |
| --- | --- | --- | --- |
| P05 | #92 | `2a02cd9eba113329870ed7eba6efd470375b8739` | `007-p05-readers-table-and-default-arms` |
| P06 | #94 | `bcc8858bf587fbe86b00264b41caca1b39ccfc72` | `007-p06-refusing-flipped-wip-init-marker` |

Both first commits are P01 children; each has one exact reviewed linear fix.
Their owners' real branches, bases and metadata are not rewritten by this observer.
An explicitly reviewed `source.commits` binding pins one to three
linear commits as described in the delivery runbook; every exact parent and
cumulative cut is checked. Missing lineage keeps the original single-child
rule. A new owner commit is never followed automatically.
Current owner coordination is issue165 comments6898422904 and6898740891. These
bindings record provenance, not review acceptance or approved task-set authority.

After the existing exact P01 merged-contract check succeeds, the observer can
inspect a bound source PR still based on P01's exact head branch/SHA, or one
its owner has retargeted to current main without changing the source head.
The body must request the matching shadow cut and declare exactly one resolved
`Depends-On: #88`. A main-retargeted PR may omit that resolved dependency line.
Other, repeated, pending or ambiguous dependencies cannot gain an observation.

The source cut is checked against its exact P01 parent, not by pretending its
head contains newer unrelated main changes. Every named cut file and marker
must still be unchanged on main since that parent. An intervening cut-path
change is full fallback even if Git might merge it. No source merge, rebase,
flatten, synthetic candidate/ref, queue write or tested-tree receipt is produced.

For a push of that exact bound branch/head, the live source PR supplies the
explicit shadow intent; its original commit message need not be amended.
Repository/ref/SHA, current open nondraft PR, prerequisite and main snapshots
are bound and reread. Other source pushes retain the original current-main
ancestry and commit-intent requirements. Source iterations invalidate a binding
until a reviewed policy update; mutable heads are never followed automatically.

Realistic local Git fixtures cover independent main advancement, normal P01
landing, original and owner-retargeted bases, unchanged source heads, stale
reads and path collisions. Their temporary source merges verify preservation
of unrelated main content only; they are not PG or live-batch acceptance.

The token-bearing observer checks out only main with no persisted credentials,
reads main-owned policy, uses bounded read-only APIs/Git, and rereads mutable
identities. Missing main policy produces a fixed full fallback; it never runs
PR-owned code as a fallback. The separate PR contract job has no API token.
Its output is a log/summary only, never a gating job output or receipt.

## P01 coordination and prerequisite

P01 is independently owned code PR88. Lanes1/2 confirmed its CI change is only
`OPENREPOTOOLS_REQUIRE_PG: "1"` and a matching environment-only baseline
amendment; all job hashes and the 13 expanded integration jobs remain unchanged.
Coordination is recorded on assembly issue165, starting at comment6888083282,
including lane2's comment6888099830 and lane1's response.

The immutable context anchor is source head
`7f1141be15ac9c0d20c25c802ba9533c2fec811c`, with workflow blob
`e46aca51d4a7a59991c319ee809d46dc61a53d93` and baseline blob
`1fd9698a4e5be71b92fa4d9abc7ee6b39f60fcb0`. This does not pin a deployed
provider or authorize delivery. Pending, changed, inaccessible or missing
prerequisite evidence cannot produce a cut observation. Source/control drift
requires a reviewed projection update, not following a mutable PR head.

The optional explicit foundation epoch retains P01 ancestry, frozen controls and
markers, and exact four-file regular modes/blobs with no later drift. Absence
retains the original strict freeze. It never auto-discovers an epoch from main;
matching blobs alone are not a real-engine receipt. Canonical epoch/enablement
requirements live in `openspec/changes/enable-reviewed-v13-test-cuts/` in the spec leg.

`merged-contract-observed` means only that the exact same-repo/main PR source
and merge are ancestors of main, the control blobs match and required-engine
baseline/foundation markers are present. It is **not proof of successful
PostgreSQL execution, case parity, live batching or release acceptance**.
This PR does not edit P01's workflow, baseline, fixtures, conftest, gate or markers.

## Qualification evidence and later gates

This implementation must pass Git/mock-API and workflow contracts, strict spec
validation, the existing full-CI coverage-parity tests, ordinary full CI and its
parameterless reusable full call. Before P01 lands, green source/reuse runs
qualify only this additive implementation, not the real-engine007 foundation.

After P01 lands, future activation work must separately record:

1. Exact reviewed code/spec/provider revisions and ordinary/reuse run IDs.
2. Complete case identities and outcomes, grouped by normal and no-submodule
   shards, with no missing or duplicate cases and equal applicable coverage.
3. Approved skip reasons only. Missing PostgreSQL cannot count as an eligible
   engine skip; required-engine CI must fail instead. Feature007's existing
   temporary landing gate and release acceptance are unchanged.
4. Current owner-approved task cuts, dependent-stack treatment, immutable
   heavy/candidate/landing proof and separate scoped activation approval.

No live canary, settings/ruleset changes, app access, paid upgrades, release
changes, assembly pin adoption, tool update or running-lane changes are part of
this shadow implementation. Preserve lanes1–5 and all worktrees.
