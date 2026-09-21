# Governance review: swap, ctx, handoff, and shared lifecycle

**Status: PROPOSED—NOT APPROVED**

This document is a review packet for the unresolved governance items in the
`separate-swap-ctx-handoff` change. It proposes boundaries and records the
evidence that still needs an approving decision. It is not an amendment, an
implementation authorization, a merge record, or runtime-capability evidence.
The [approved native-subagent decision](native-subagent-decision.md) is used
as architecture evidence only: it does not approve this packet's protocol
supersession, cross-repository ownership, canary scope, or release.

## 1. Proposed Amendment 17 supersession mapping

The following is the proposed replacement for Amendment 17's one-act
interpretation. Until an approving governance citation is added, the existing
installed aliases and historical records remain governed by their current
rules; no installed cutover is claimed.

| Boundary | Proposed superseding clause | Compatibility and refusal rule |
| --- | --- | --- |
| `swap` | `swap` is an account-control transaction only: select the explicitly authorized same-family target, stop and account for the supported native graph, restore the exact coordinator conversation, and leave it held. It makes no prompt/model request, writes no summary/checkpoint/handoff, and does not perform `ctx`, `handoff`, worker restart, or `release`. | `ready-held` is not released. Missing or contradictory capability/effect evidence refuses before source effects and retains ownership/claims. |
| `ctx` | `ctx` requires a caller-supplied checkpoint and the current account, then creates a deliberate fresh coordinator context held before inference. `--workers hold` retains stopped old native records under the old lineage; `--workers restart` creates new-lineage native workers from the supplied checkpoint only after explicit release. | No exact cross-parent child rebind, implicit restart, generated checkpoint, or account change. Old parent/task links remain immutable. |
| `handoff` | `handoff` is a separate user-requested, record-only operation that records only a checkpoint/reference explicitly supplied by the caller. | It does not swap accounts, create a context, stop/restart workers, alter claims, dispatch, or release. Its record is not native lifecycle evidence. |
| `release` | `release` is a separate explicit, at-most-once inference boundary for the matching held operation/generation. | An identical accepted retry observes the prior result without another runtime call. Stale-generation, changed-content, unresolved, or overlapping release refuses without dispatch. |
| Legacy aliases and records | Preserve legacy aliases as historical compatibility surfaces, but a managed-owned or unknown lane must refuse legacy launch/handoff rather than fall through. Superseded independent-worker/schema-v1 records must be preserved and refused with an explicit migration/recovery reason. | No silent reinterpretation, deletion, child-session invention, or automatic migration. No installed alias replacement or cutover is asserted by this proposal. |

The proposed mapping keeps command distinction visible: `swap` changes the
account under a held exact coordinator, `ctx` deliberately creates context,
`handoff` records caller data, and `release` crosses the inference boundary.
None is an alias for another operation.

## 2. Shared lifecycle and PR #121 integration proposal

### Read-only PR identity and comparison

The referenced work is [opensoft/openRepoTools PR #121](https://github.com/opensoft/openRepoTools/pull/121), an open, unmerged supervised
`/ctx` implementation by `brettheap`. The compared revision is
`main@957a26f048fd0920a2ea4d5de70fe8f3be81dbaf` to
`c4214265d9f6243c258d937881474ed12f65515c`. Read-only comparison found seven
overlapping file areas: `commands/ctx.md`, `docs/README-lanes.md`,
`lane-handoff`, `lane-start`, `lanes-edit.sh`, `skills/handoff`, and helper
tests. These facts do not mean that the PR is approved, merged, installed, or
compatible with the native-lineage contracts.

The PR itself records its mechanism as unratified and does not establish an
architecture agreement. This packet therefore treats its changed behavior as
read-only comparison input, not as a governing decision or landed dependency.

The PR's `restart-intent.yaml` and `fresh-from-handoff` supervisor artifacts
remain outside managed native `ctx` state and outside the explicit managed
`release` operation. They must not be adopted as native lifecycle records,
operation identities, release authorizations, or evidence of a shared
authority without a separately approved integration decision.

### Proposed shared authority contract

Any integration with recovery or supervised-context work must establish one
durable lifecycle authority for a lane generation:

1. One store lock and one owner/generation operation identity serialize
   enrollment, admission, swap, `ctx`, handoff, submit, recovery, release,
   shutdown, and unenrollment. A sibling operation ID cannot authorize the
   same runtime or claim.
2. The shared record retains exact coordinator/native identity, immutable
   native invocation history, dispatch/release intents, watermarks, and
   uncertainty. Recovery reconciles those records before any new runtime
   effect and never replays an uncertain send, release, external effect, or
   completed work.
3. Lineage-owned workspace claims remain exclusive. A claim transfer uses the
   existing exact claim compare-and-swap (claim-CAS) boundary; an adoption
   record binds source history, target claim, owner/daemon/operation identity,
   and trusted evidence before transfer. Missing evidence leaves ownership
   held or indeterminate.
4. Adoption is ownership bookkeeping, not native runtime readiness. It does
   not open, release, restart, or retarget a coordinator or child, and it
   cannot turn a PR artifact or caller assertion into lifecycle evidence.

External ownership and landing responsibility for the recovery and
supervised-context changes remain **unverified** in this packet. Do not invent
repository owners, lane names, merge status, dependency landings, or a shared
store authority from overlapping paths. The PR identity above is factual; its
integration approval and landing state are not.

## 3. Decision ledger

Each row has a proposed answer and an evidence pointer. The final column is
intentionally blank until the named authority records an approval decision.

| Decision | Proposed answer | Current evidence / boundary | Approval citation |
| --- | --- | --- | --- |
| Amendment 17 supersession | Adopt the mapping in §1: account-only held `swap`; caller-checkpoint fresh `ctx`; caller-reference-only `handoff`; separate `release`; explicit legacy refusal. | Native-subagent decision §§ Revised contract 2, 4, 7; this packet §1. Architecture evidence only. | **[blank — not approved]** |
| PR #121 relationship | Keep PR #121 as an open, unmerged supervised-`/ctx` input. Reconcile its overlapping command/protocol work before any cutover; do not absorb its supervisor artifacts into managed native state. | Read-only comparison in §2; PR link and exact base/head above. | **[blank — not approved]** |
| Lifecycle authority and lock | Select one owner/generation operation authority and one shared store lock for all lifecycle operations; refuse competing identities. | Existing managed-control/recovery contracts and proposed §2. | **[blank — not approved]** |
| Native history, claim-CAS, and adoption | Retain immutable native invocation history and lineage claims; require exact claim-CAS/adoption evidence; never replay uncertainty or treat adoption as runtime readiness. | Existing data-model and native-adoption contracts; proposed §2. | **[blank — not approved]** |
| External ownership | Do not name or assume an external recovery/context owner until an authoritative repository/owner/landing record is supplied. | No verified ownership evidence in this packet. | **[blank — not approved]** |
| Runtime capability disposition | Use the matrix in §4. A mode is supported only after pinned evidence closes its gates; unsupported or inconclusive results do not become acceptance. | Approved native decision's runtime-boundary notes; §4. | **[blank — not approved]** |
| Disposable authorization and canary | Name the source/target disposable profiles, lane, allowed effects, host/configuration boundary, authorization window, and rollback/cleanup before any authenticated probe. | Release-scope decision remains open; §5. | **[blank — not approved]** |
| Cross-repository dependencies | Name required approvals and landed revisions for openRepoTools, workBenches/launcher boundaries, and any recovery/context integration before release. | PR #121 remains open/unmerged; §5. | **[blank — not approved]** |

## 4. Pinned capability disposition matrix

The matrix distinguishes controller/test evidence from a production support
claim. A definitive `unsupported` result closes investigation of that exact
mode or participant combination; it is not a successful feature acceptance
result and does not authorize a fallback.

| Pinned mode or participant | Evidence currently available | Proposed disposition | What would be required to change the disposition |
| --- | --- | --- | --- |
| SDK `0.2.153` selecting bundled CLI `2.1.273`, print/stream-json path | Bundled selection and digest were observed; the path can restore `running_background_tasks` as `restoredOrphans` and enqueue an orphan-wake notification. | **INCONCLUSIVE / UNVERIFIED** until the exact selected mode passes Gate 0; **UNSUPPORTED** for zero-inference swap if it cannot hold startup. | No-auth orphan fixture on the exact binary/digest/mode; terminal child/tool stop; supported durable current-worker-state clear; target no-wake/no-model observation before release. |
| CLI `2.1.270` interactive takeover/adoption path | Local investigation observed an orphan auto-resume path before the first user query. | **UNSUPPORTED** for the held zero-model account-control claim in this mode. This closes the mode's current investigation, not feature acceptance. | A separately pinned mode with a supported hold boundary and complete current-run stop/effect evidence; do not generalize the old observation to another SDK selection. |
| CLI `2.1.270` print path or any separately installed binary not selected by the SDK | A print path without the interactive callback was observed, but no selected-SDK compatibility or no-wake proof follows from that observation. | **INCONCLUSIVE / UNVERIFIED**. | Record the actual SDK-selected executable/version/digest/arguments and run the exact startup/orphan and terminal-clear probes. |
| Fake/local runtime | Useful for controller serialization, refusal, queue, claim, and crash/recovery logic. | **SUPPORTED FOR MECHANICAL TESTING ONLY**; never native production capability. | A pinned runtime evidence package, not a stronger fake, is required for any live/native claim. |
| Runtime-owned native background Agent/Task | Native task/lifecycle behavior is not established by a background flag or parent tool return. | **INCONCLUSIVE / UNVERIFIED** until exact IDs, parent links, stop boundary, tool/effect accounting, and restart evidence are pinned. | Current-run native lifecycle and effect evidence for the exact selected runtime and participant kind. |
| Native teams | No separate team identity/stop/restart/effect contract is established by the approved decision. | **UNSUPPORTED / UNPROVEN** for this release. | A separately approved and tested team capability; Agent/Task evidence cannot close it. |
| Unmanaged detached shell/background process | No native lifecycle or ownership authority is available. | **UNSUPPORTED** as a managed native participant; retain separate effect/ownership uncertainty. | None within this feature; it requires a separate containment/effect contract. |

No row authorizes live authentication, account transition, model use, or an
installed cutover. A mode that remains inconclusive stays held/refused; a mode
marked unsupported is not silently replaced by another mode.

## 5. Remaining release decisions

### Named disposable authorization scope and canary

Before any authenticated or cross-account probe, approval must name all of the
following in one bounded authorization:

- disposable source and target profile identities, same transcript-storage
  family, and the exact pinned SDK/CLI/runtime mode;
- one disposable lane/coordinator transcript and an isolated workspace or
  worktree, with the allowed files, tools, external effects, and network
  boundary stated explicitly;
- the canary workstation/configuration and installation scope, including what
  existing sessions are out of scope;
- an authorization window, operator, abort condition, rollback/cleanup plan,
  and the rule that credentials, tokens, generated handoffs, and production
  data are neither copied nor persisted; and
- the evidence artifacts that must be recorded for zero-model account control,
  exact coordinator restore, native child disposition, claim ownership, and
  post-release work.

Until these names and limits are approved, static contracts and fake/local
results remain planning evidence only.

### Cross-repository approval and landed dependencies

Release also requires an explicit dependency ledger, with approval citations
and landed revisions for:

1. the openRepoTools managed-native lifecycle/dispatch implementation and its
   one-authority store/lock;
2. the workBenches launcher/profile boundary that selects and verifies the
   pinned runtime without copying credentials or silently changing command
   meaning;
3. the recovery/supervised-context integration, including the confirmed
   treatment of PR #121's overlapping command/protocol paths and exclusion of
   `restart-intent.yaml`/`fresh-from-handoff` from managed native state; and
4. any shape/pin or workflow dependency required to install those revisions
   together.

PR #121 is currently open and unmerged at the exact revision recorded in §2;
there is no merge, landing, approval, or installed-cutover claim here. The
release decision must name which revisions are approved, which dependency
lands first, and which canary evidence gates the next one. A merge alone is
not runtime acceptance.

## References

- [Change proposal](proposal.md)
- [Approved native-subagent decision](native-subagent-decision.md)
- [PR #121](https://github.com/opensoft/openRepoTools/pull/121) (open,
  unmerged read-only integration input)
- [Managed control contract](../../../specs/001-separate-swap-ctx-handoff/contracts/managed-control.md)
- [Recovery lifecycle contract](../../../specs/001-separate-swap-ctx-handoff/contracts/recovery-lifecycle.md)
- [Native adoption transaction](../../../specs/001-separate-swap-ctx-handoff/contracts/native-adoption-transaction.md)
