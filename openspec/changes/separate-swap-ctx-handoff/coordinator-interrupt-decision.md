# Coordinator-wide interrupt and durable drain

## Authority and scope

CLAIMED — lane swap-runtime-gate, session
`01a0b3be-3f3b-7272-bd2c-e11fda90fbb6`, 2026-09-18T10:19:57Z, for the
governed coordinator-wide interrupt/drain design and Speckit reconciliation.

Brett authorized this next step with “do the next step” after the Stage 1
report named a governed coordinator-wide interrupt-and-drain design. This
continues the same change and linked feature; no competing change claim,
remote feature branch or open feature pull request was found. Existing feature
work is preserved. Astra leads architecture, Sol High orchestration, and Luna
Max contract writing in Codex.

This decision is specified against the
[Stage 1 evidence](stage1-runtime-boundary.md). It grants no production runtime
capability and does not close Gate 0. Executable work remains solely in
[Speckit tasks](../../../specs/001-separate-swap-ctx-handoff/tasks.md).

## Evidence and selected design

For SDK `0.2.153` and its selected CLI `2.1.273`, a settled parent with one
native background Agent and a tracked Bash tool produced a new Messages
request after task-specific `stop_task`. The same fixture using documented
coordinator `interrupt` produced none, while separately observing native task
termination, tool termination and process exit. Exact parent resume stayed
request-free while held; explicit release preserved UUID and native history.
These are scripted API/gateway observations, not account-mode acceptance or a
proof that interrupt is a persistent inference fence.

In particular, Stage 1 started its cancellation measurement after fixture
setup and parent settlement. It did not validate the broader interval from
account-control entry before preflight/fencing specified below.

Select coordinator-wide interrupt as the candidate for a new distinct durable
transaction. Its detailed contract is
[coordinator interrupt](../../../specs/001-separate-swap-ctx-handoff/contracts/coordinator-interrupt.md).
The existing [native stop](../../../specs/001-separate-swap-ctx-handoff/contracts/native-stop.md)
transaction remains task-specific. Neither its authorization nor the
prototype's participant interrupt loop authorizes this broader operation.

## Required boundaries

1. Validate mode-specific source-control and target-startup capabilities before
   disruptive effects. Actual account/configuration, selected executable and
   transport are part of the capability identity. Unknown remains unsupported.
2. Fence coordinator input, native admissions, tools and mail, then reconcile
   in-flight admissions and seal the complete observed native roster. Bind
   actual child/parent/launch identities, definitions, claims and source runner
   incarnation. Do not infer completeness from an empty map or a receipt.
3. Persist a distinct coordinator interrupt intent and its possible-send marker
   before authorizing one SDK call on the existing connection. Dedupe against
   the source run and fence as well as request content; changing request IDs
   must not authorize another interrupt of the same unresolved source. The
   unresolved-source index also prevents changed operation, fence or roster
   identifiers from bypassing exclusion of that source incarnation.
   Revalidate the full authorization at the runner send boundary. The raw
   interrupt path and legacy participant loop cannot bypass it or race a
   second cancellation inside the unresolved account-control operation.
4. Keep event and persistence readers live while control awaits. Drain parent
   results, per-child current-run terminal events, tool ends and effect
   outcomes independently. An acknowledgement is neither native termination
   nor graph quiescence. A racing natural completion stays completed.
5. Advance only with authoritative current-run evidence for every roster
   member and tracked tool/effect. Then observe any required supported runtime
   state clearing, shut down the parent and prove old-writer exclusion before
   exact target resume. Interrupt may initiate child stopping; parent shutdown
   still follows child/tool quiescence.
6. Track new request attempts across the whole account-control interval. A
   positive count, an unobservable interval or a breach of the sealed roster
   blocks success and retains claims. Blocking external queries, tool
   permissions or a request already received by a gateway is insufficient.
7. Recover by reading durable intent and live evidence. Lost replies, crashes,
   timeouts, generation changes or event gaps never authorize automatic resend,
   claim release, target startup or model-assisted repair. Unknown effects
   remain unresolved even after all processes have exited.

## Scope retained

The caller's zero-new-model-request requirement is unchanged. There is still
one native coordinator lineage, exact parent restoration is mandatory, and
native children receive no independent SDK session or invented lifecycle API.
Completion evidence cannot be relabeled as stopped or copied across child
incarnations. Cancelled children use the existing held disposition and
post-release continuation/restart rules, with no automatic exact-resume claim.

This design does not expose a public interrupt command, select credentials,
enable swap, relax orphan/state-clear acceptance, or reinterpret older durable
records. A capability must cover the requested busy/settled mode, participant
kinds and complete roster; the one-child experiment is not a multiple-child
or foreground-parent guarantee.

## Handoff and acceptance

The linked Speckit plan/data model/tasks own implementation sequencing and
test work. Preserve their existing task IDs and incomplete acceptance marks.
The first implementation slice is the internal durable transaction and real
store/IPC tests with a fake runtime; a public success path still depends on
the full pinned-runtime gate. Required cases include fence/admission races,
natural completion, nested/multiple children, loss of acknowledgement, daemon
takeover, wrong identities/generations, event gaps, process/effect uncertainty,
new model attempts, and unsupported busy/account modes.

The pending final Stage 1 focused suite remains a separate validation gap until
the canonical test runner can execute it. No source capability is granted by
the documentation or by fake-runtime integration tests.

The design review reconciled source-incarnation exclusion across changed
request/fence/roster identifiers, immutable seal versus advancing evidence,
pre-seal natural completion, positively idle parent turns, and refusal of
missing new record fields even under the native schema. Parent shutdown
follows drain; process exclusion follows shutdown. These are requirements for
the next implementation slice, not claims about the existing prototype.

## Review and validation

Astra completed architecture review with no remaining design blockers. Sol's
final strict OpenSpec validation passed. All 63 checked relative Markdown
targets exist; the executable list retains exactly T001–T032 with unique IDs,
valid task references and unchanged completion states. The reviewed document
snapshot remained unchanged during validation, and `git diff --check` passed.
The selected contract SHA-256 is
`44d905368a8585968d7a474f1fe68e47b205a48d05161a93e471bc5c05bb0703`.

This design step is complete. The pending Stage 1 combined probe tests still
could not start because the canonical guard found unrelated live pytest
processes; no waiter was left behind. This step changed documentation only,
with no production implementation, runtime experiment, commit or deployment.

## Internal transaction implementation follow-up

CLAIMED — lane swap-runtime-gate, session
`01a0b3be-3f3b-7272-bd2c-e11fda90fbb6`, 2026-09-18T11:28:23Z, for the
internal durable coordinator-interrupt transaction and store/IPC tests.
Brett authorized this slice with “do next step” after the completed design
named that implementation. A fresh sibling/remote/PR search found no competing
feature claim or branch. Existing feature work remains preserved.

The slice covers distinct intent/evidence records, controller validation and
recovery, trusted daemon callbacks and authenticated persistence request/ack
readers. It does not add a live roster producer, SDK interrupt dispatcher,
public interrupt route, successful public swap or runtime capability. Those
remain separate downstream work in the existing Speckit task list.

The bounded implementation is complete: durable distinct controller records,
trusted daemon callbacks, independent SDK persistence IPC, and real-store/IPC
tests are present. Astra's final architecture review found no remaining source
blockers. The focused canonical matrix passed **166 tests**; the previously
pending Stage 1 probe modules passed **64 tests** after a test-only fixture
correction. Sixteen existing controller/daemon lifecycle failures remain
unresolved in the broader regression check. See the linked
[verification record](../../../specs/001-separate-swap-ctx-handoff/verification.md#internal-coordinator-interrupt-implementation-2026-09-18)
for exact selectors, limitations, immutable source manifests, and JUnit hashes.

The concrete contract now distinguishes the roster identity/inventory digest
from the full intent digest and transactional admission/claim validation.
It also records the conservative paused-operation/nonempty-roster boundary of
this slice. Its current SHA-256 is
`ebc0aa1018e2149ed598207d09bf27e4d18ab7731fb5ac5118b6c86ef698d221`.
The next implementation work is live roster/fence production and SDK interrupt
dispatch, followed by aggregate drain/recovery orchestration under the existing
tasks. No public success path, capability, commit, or deployment is enabled.

## Live startup and interrupt integration follow-up

CLAIMED — lane swap-runtime-gate, session
`01a0b3be-3f3b-7272-bd2c-e11fda90fbb6`, 2026-09-18T12:12:42Z.
Brett explicitly authorized “do steps 1 and 2”: connect native coordinator
startup/context registration, actual child/tool roster tracking and fencing,
then consume durable authorization for a documented SDK coordinator interrupt
and persist real observations. Fresh remote-branch and open-PR searches found
no competing feature branch or PR. The previous source snapshot is preserved
in private preimages before edits.

This work implements the existing Speckit native lifecycle and interrupt tasks.
It does not grant the zero-request runtime capability or enable successful
public swap. Aggregate drain, source-process exclusion, target restoration,
release/recovery completion, and authenticated account validation remain the
subsequent steps. Local query/admission/tool fences must not be represented as
proof that runtime-internal inference or wake paths are fenced.
