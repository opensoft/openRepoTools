# Implementation Verification Record

Status: **INCOMPLETE — LIVE UNVERIFIED**. A written implementation, reviewed
slice, or passing fake test is not full acceptance. `tasks.md` remains the
implementation task authority; this document identifies the evidence needed
to close the feature without reducing its scope.

## 2026-09-21 takeover — diagnostic checkpoint; 34 failures remain

Implementation continues under the user-authorized
[takeover record](../../openspec/changes/separate-swap-ctx-handoff/takeover-2026-09-21.md).
The inherited tree was archived before edits, including its untracked source
and modes. The serialized release gate is pending; previous overlay
counts below are historical and are not the result of this takeover. No new
task closure or production capability is claimed.

The frozen baseline was extracted to `openrepotools-sol-frozen.PIkooO/repo`
under the `py-bench` temporary root. Its source and mode manifests compare
equal to the preserved pre-edit manifests; their SHA-256 values are
`fcb71e030f136dc006fb027d77ccf659ae14acc507f7d0198c2de5699f6be7b0` and
`9f7ff3eaf42dca698ee155a3ee56c1b4271d58ef399c4ecb15927c7d065a933b`.
The original worktree may now change without changing this baseline input.
The first waiter on the original tree was stopped before pytest started;
the replacement uses the frozen tree and the canonical serialized wrapper.

The user subsequently explicitly authorized this branch's existing
`tests/run.sh --parallel-safe` mode for **diagnostic tests only** on September
21, after the shared queue continued waiting. Sol may replace only this
takeover's still-waiting invocation and run one isolated diagnostic at a time.
The final release gate remains serialized; isolated results do not close that
gate or establish native/live support.

The first isolated frozen baseline stopped during collection: **1 error,
724 deselected, no executed test results** (11.52 seconds).
`test_lane_managed_native_worker_boundaries.py` imported `_begin_native`
from the production SDK module instead of `test_lane_managed_sdk.py`, where
that fixture helper is defined. The import was corrected without changing the
SDK or excluding the module. Artifact:
`openrepotools-sol-baseline.9DZ1up/managed-baseline-isolated.xml`, SHA-256
`6f2402526c8f702edaa07405404b0d0a3c81564f7ab20d4fd0d3818bec989645`.
A new diagnostic must use the preserved baseline plus that exact import fix;
the in-progress controller must not be mixed into that baseline.

The corrected-import baseline completed using
`tests/run.sh --parallel-safe -k test_lane_managed`:
**1,369 passed, 96 failed, 724 deselected** in **478.04 seconds**.
Artifact: `openrepotools-sol-managed-overlay.SbrH0l/managed-overlay-isolated.xml`,
SHA-256 `f32256ecd70aaf6fac9122a90661088d3cfb7c4cb2fedacccbfc14522477c2e5`.
This is one frozen diagnostic snapshot, not an aggregate or release gate.

| Failing module suffix (`test_lane_managed_…`) | Failures |
| --- | ---: |
| `cli` | 5 |
| `cli_persistent_lifecycle` | 1 |
| `ctx_policy` | 2 |
| `native_ctx_integration` | 5 |
| `native_restoration` | 9 |
| `native_swap_fences` | 5 |
| `native_swap_integration` | 3 |
| `native_swap_integrity` | 23 |
| `native_swap_pump` | 2 |
| `native_worker_boundaries` | 12 |
| `source_history` | 18 |
| `target_adoption` | 11 |

The archive-focused frozen gate tested a real archive-preservation correction: optional
ledger defaults must remain internal to validation, not replace the original
snapshot while retaining its digest. Four new regression cases cover omitted
optional fields, repeated validation, read-only reload, and later persistence.
The isolated source-history, target-adoption, swap-integrity, and swap-integration
gate reported **71 passed, 8 failed, 2,114 deselected** in **181.04 seconds**.
All eight remaining cases correctly rejected negative-satisfaction evidence
with `uncertain-effect`; the test helper's old refusal-code whitelist excluded
that response. Only those eight cases now require that exact code. This
assertion correction needs a fresh rerun, not a retroactive passing count.
Artifact: `openrepotools-sol-archive-gate.PLysnZ/archive-gate-isolated.xml`.
XML SHA-256: `26047d7d090554c4dfd5e4068a6c15be20c7c59fb70cc6c6ad7df667cadef4af`.
The source/mode manifest digests are respectively
`806f62999e325cee755994fa2f63c02147e7df945626647fa5aaaa098ef62bdc` and
`c328d8514e7d552c089810f8e6e6ab0735da45b53bdd7020206af31cfc2baf16`.
Astra's bounded review confirmed that digest, canonical shape, semantic,
operation/generation, context, and source-identity checks still precede the
original-snapshot return.

The native child-observation correction accepts either relative ordering of
TaskStarted and SubagentStart, as the runner contract already permits. Both
events must independently follow the durable admission watermark and precede
or equal observation. Identity, terminal chronology, and controller admission
checks remain enforced. Astra's bounded security review found no blocking
finding. The combined diagnostic below passes the new positive and
stale/upper-bound negative regressions, but worker integration remains failing.

### Combined managed diagnostic after bounded corrections

Command: `tests/run.sh --parallel-safe -k test_lane_managed
--junitxml=<private-artifact>/combined-managed-isolated.xml` in `py-bench`.
The existing wrapper supplies an isolated pytest temporary root and disables
its cache provider. Result: **1,442 passed, 34 failed, 724 deselected**, no
collection errors or skips, in **392.56 seconds**. This is one frozen candidate,
not a sum of focused runs. The corrected-import baseline had 96 failures;
the candidate also includes 11 new regression cases.

Artifact: `openrepotools-sol-second-gate.nCBmg9/combined-managed-isolated.xml`.
XML SHA-256: `191ffb90b6a04eb6f15f926b46cd98afb9550c37fadfb60edf39de9e53e9034c`.
Source and mode manifest SHA-256 values:
`345ddffc42bc7021470d8711ebd97d0230178f1b723f58d1feeea41d5cae6ca6` and
`612eba19ebbe32e69d9ded72cc7a257a6eac4922294182fbdce43676504ba91f`.
Pre/post source and mode manifests compare equal. Later checkpoint-document
edits do not change the source or tests in that frozen candidate.

| Remaining module suffix (`test_lane_managed_…`) | Failures | Observed boundary, not a waiver |
| --- | ---: | --- |
| `cli_persistent_lifecycle` | 1 | Retry after paused recovery returns `busy`; earlier baseline timeout is no longer its failing assertion. |
| `native_ctx_integration` | 5 | Positive native ctx lifecycle remains unsupported. |
| `native_restoration` | 9 | Retention/restart/restoration acceptance remains open. |
| `native_swap_fences` | 5 | Takeover still fails to reach `fired`; fixing the nonexistent fixture daemon attribute did not settle the suite. |
| `native_swap_pump` | 2 | Public recovery/pump socket I/O failures remain. |
| `native_worker_boundaries` | 12 | Observation watermark and source-operation binding failures remain after the event-order correction. |

Source-history, target-adoption, swap-integrity, and swap-integration modules
pass in this combined candidate, including the exact negative-satisfaction
refusal checks. CLI identity-binding and mixed-native/legacy policy corrections
also pass. The selector retains every collected managed test. Legacy shell
assertion edits have only passed `bash -n` here, not T028. `git diff --check`
and strict OpenSpec validation pass. No serialized release gate, authenticated
probe, installed cutover, or task closure is claimed.

The exploratory native-ctx implementation was not included in either baseline.
Architecture review found no established ctx-specific pre-shutdown worker-clear
proof seam. Its draft was preserved privately and removed from the worktree;
native ctx still refuses. The five ctx integration failures and nine native
restoration suite failures remain open requirements, not expected-pass refusals.
See the takeover record for the precise missing contract and proposed next
design step. No task checkbox was changed.

Takeover inspection also recovered a newer **historical** T028 artifact:
`openrepotools-sol-legacy-t028-rerun3.mmK98L/t028.xml`, written on September 18,
reports **3,183 passed, 29 failed, 0 skipped/pending** inside the shell suite
(one failing pytest wrapper test), SHA-256
`368742ea5875875970904965dcf22894ebaf77d5c9b2764b5cee22be8f52e2db`.
It is a failure census for its old overlay, not the current source or a waiver.
Current T028 remains pending. Strict OpenSpec validation of
`separate-swap-ctx-handoff` passed on September 21; this validates artifact
structure, not runtime behavior or governance approval.

## Preserved 2026-09-18 checkpoint — consumer/history green, child and six-stage gates open

Sol's latest clean controller consumer/history checkpoint reported **65
passed, 0 failed/errors/skips, and 1,902 deselected** in **18.33 seconds**.
The JUnit artifact is
`/tmp/openrepotools-sol-controller-consumer-final.o0Htoz/controller.xml`,
SHA-256
`c61f5803f1b6d5eb05c12dcc789e816d5f60135fa28070b7a2fe69e78958e336`.
The frozen overlay's controller and recovery-test file hashes are respectively
`b4cc9d03e59949c6811f9065eae82c7b3a5356aa2d9c64200cba0afa7d02a8be` and
`cd5920e7b1dda10ec36bed86a59fe05b8330b547a397ad7637ee06556eb78f2c`; the
content and mode manifests were unchanged pre/post (`f0a913ead90bffbe2fde4a749831a2b0fe1d19689d46bdace2dc927677956f4e` and
`b9a619f11a6c2382809bf521ea2c894068a9923197be32f932a55864d94f68b5`). The
earlier **0 passed/65 failed** partial child checkpoint is invalid acceptance
evidence; this clean controller/history checkpoint does not validate the
current child-observation work-in-progress. The earlier **55 passed/10
failed** tuple-fixture checkpoint is likewise superseded; that fixture is now
fixed.

The SDK child-observation/no-send gate reported **229 passed, 3 failed, 0
skipped/errors** (232 selected) in **8.777 seconds**. Its JUnit artifact is
`/tmp/openrepotools-sol-sdk-daemon-child-gate.AHlWIb/child.xml`, SHA-256
`5c346eafd1972fc8afd1298c475631330cda718a2f7f451ef61b9cb9ef743c70`.
The failures are the pending-observation busy barrier, EOF ACK poisoning, and
the exact native no-send receipt; Astra's three fixes are approved and await
rerun. Source and mode manifests were unchanged pre/post
(`827d2861ec4a17f93c53f94bd3499ea0cbcb2b9d1433f43f188d7f6714825cec` and
`43850d7a8bfe39b8f7a1f3a09b2f6edef88e48daef06ef222b2c0afc01f1e121`).

The six-stage fixture-10 gate reported **26 passed, 7 failed, 0
skipped/errors** (33 selected) in **41.002 seconds**. Its JUnit artifact is
`/tmp/openrepotools-sol-sixstage-fixture10.Q07xNc/sixstage.xml`, SHA-256
`136f47ba96dd16437599c1f0324c92d83db008f279a108683f3eac141c78b215`.
The active diagnoses are native-key ordering and legacy collector behavior.
The new `native_swap_integrity` path was not included; any integrity result
here is historical rollover-integrity evidence only. Source and mode manifests
were unchanged pre/post (`7f19c65bfe6f1b8b36fcd7bb5f01d395c677688731dd6410d8922de7185f7a18`
and `b891521783feedb82b3358899a486c3b05e4711cde5f15c0736acb71c3a5eebb`).

These are active diagnostics, not acceptance: no task checkbox is added to the
existing **8/32** scoped closures, and authenticated account validation
remains **NOT RUN**.

## Latest scoped checkpoint — eight of 32 offline foundation closures

Astra approved only snapshot-scoped, offline foundation closure for T005,
T006, T007, and T008. Together with the previously scoped T022, T025, T026,
and T030 closures, this is **8 of 32 task closures**. It does not close T001,
T002, or T004, and it does not establish a held native swap, production
runtime support, authenticated account validation, or final acceptance.

The prior state/profile/adoption evidence remains the direct same-source
foundation evidence for T005/T007/T008: **170 passed**, JUnit SHA-256
`e3dc5dbd2addbd548257c099982958255bcc7612aab99321e682bec480291dee`, manifest
SHA-256
`4f3e5bf8e781c0423c2a24bb5644901e0d441f52576cfc839e31d7ebbbeaa283`.
This result is preserved as its own slice and is not summed with later runs.

The frozen broad snapshot in private artifact
`/tmp/openrepotools-sol-corrected-rollover.ebPR8y` reported **572 passed, 1
failed, and 1,308 deselected** in **103.33 seconds** (573 selected cases).
Its JUnit SHA-256 is
`06d51f954e0d7a3e49d3cd53c73697ac7e1ac6f255be4b881c8c19816b9e99a3`. The
source snapshot records head `1d477d2e61a3b9e0196bd802f4a885d51f6e62e1`,
the pinned shape submodule at
`39d5c986fcfac1a160474bfe91c5f1c37fccc72c`, unchanged before/after content
manifest SHA-256 `26ec6418e7ef4365a009077f50cae7a5321faf1bd8619a3a81515513f87fdecf`,
and unchanged before/after mode manifest SHA-256
`0eb8960f5604694ccfe809d846e6943fb9222f8bb84ef6c8918308091712c893`. Three
new unfinished files were excluded: `tests/test_lane_managed_swap_contract.py`,
`tests/test_lane_managed_native_swap_integration.py`, and
`tests/test_lane_managed_worker_boundaries.py`.

The sole failure is retained, not rewritten as a pass:
`tests/test_lane_managed_sdk_rollover.py::test_persistent_reader_rejects_stale_child_incarnation_after_parent_result`.
The stale-child ownership-conflict rejection was valid, but the observed
refusal set lacked the expected `ownership-conflict` code. This broad result
is therefore snapshot/diagnostic evidence only; it is not a full acceptance
aggregate.

The latest authoritative isolated pure-plus-packaging overlay is private
artifact `/tmp/openrepotools-sol-pure-packaging-corrected.slGDrk`. Its exact
selector was `test_lane_managed_swap_contract or
test_openrepotools_command or test_repo_hygiene or test_install_skill_and_hook`:
**391 passed, 0 failed/errors/skips, and 1,559 deselected** in **66.63
seconds**. Its JUnit SHA-256 is
`9a74cab37a7cc51aa73fac9eb07b909261ed807518b6ef64cf1bf3749a647e06`, with
unchanged before/after content-manifest SHA-256
`c432c5cfb21368318ab9415da8b5c653831bbee1decfe5c45b44ce2df909e1d0` and
unchanged before/after mode-manifest SHA-256
`a2c646e5ce949410395f828518486e7ef7544d03d8d8250c4b4f3d423bb37d04`.
The overlay contains only the frozen candidate plus the named helper/test and
three packaging corrections; `bash -n openRepoTools` passed. It excludes the
unfinished native-swap integration and worker-boundary tests and does not
validate the current new-runtime source. The earlier pure-packaging diagnostic
(**384 passed, 2 failed, 1,559 deselected, 75.48 seconds**, JUnit SHA-256
`4c02f2ebc033593204aef3be64a21a236efac83eb939e4bd80e8f39afc73f109`) remains
superseded/non-acceptance evidence; overlapping runs are not summed.

A separate frozen production-assertion overlay in private artifact
`/tmp/openrepotools-sol-sdk-assertion-overlay.IFm15w` selected
`test_lane_managed_sdk_rollover or test_lane_managed_cli or
test_lane_managed_native_interrupt_runtime or test_lane_managed_runtime` and
reported **193 passed, 0 failures/errors/skips, and 1,688 deselected** in
**14.48 seconds**. Its JUnit SHA-256 is
`68e52f2f764824529433ece47b2aaa6be120e4a5dc55ce20277a9b2c5a6f8da9`.
The overlay is `tests/test_lane_managed_sdk_rollover.py` on the same frozen
base snapshot; its before/after content-manifest SHA-256 is
`3ac2b5551fcecdf72add211ceb6e98eb9cd591a67728158eadfed46c6fb79465` and its
before/after mode-manifest SHA-256 is
`0eb8960f5604694ccfe809d846e6943fb9222f8bb84ef6c8918308091712c893`.
This supplies the missing stale-child ownership-conflict assertion alongside
CLI/runtime assertion coverage, but it is an overlay-only diagnostic and does
not convert the broad 572-pass/1-failure snapshot into a combined result or
validate the new native-swap source. Astra separately approved T006 as a
snapshot-scoped CLI/schema implementation closure from this old frozen
overlay; it does not validate the in-progress six-stage/native-swap source.
No other task checkbox is implied by this run.

### New parallel diagnostics (not acceptance)

The later Sol-reviewed SDK-plus-daemon release gate reported **375 passed,
0 failed/errors/skips, and 1,554 deselected** in **10.98 seconds**. Its
focused JUnit artifact is
`/tmp/openrepotools-sol-sdk-daemon-reviewed.FmuAhG/focused.xml`, with JUnit
SHA-256
`44a763b4241adb5a80feb5ba71a07220645489c67fa7eab7c0e87de2ded6e17e`.
This is a reviewed frozen-base overlay, not the current no-send
SDK/daemon/controller integration, and it is not combined with any other
selector. Sol's full content/mode manifest hashes were not included in this
handoff and are intentionally not inferred.

The superseded SDK-release diagnostic reported **201 selected cases**. Astra's
review found four safety holes in that diagnostic; the corrections are now
reviewed as GO for a rerun, but no corrected rerun result exists yet. Its
artifact path, JUnit digest, and content/mode manifest digests were not
included in the current evidence handoff and are intentionally not inferred.

The daemon slice reported **154 passed and 1 failed**. The failure was a
fixture-expectation mismatch; the fixture correction is now applied, but the
corrected rerun is still pending. No artifact or digest is asserted for this
intermediate result because Sol's current handoff did not provide one.

The older-source recovery slice reported **4 passed and 3 expected failures**.
Those expected failures exposed the native loose-proof gap. A controller
refusal for that gap has since been added, but this source slice did not test
the correction; the result remains historical diagnostic evidence only. Its
artifact and digest identifiers were not supplied and are not reconstructed
here.

T028 subsequently completed as a **failed** diagnostic: the outer run took
**1,439.52 seconds**, reported **1 failure and 1,873 deselected**, while the
inner result reported **2,713 passed, 492 failed, and 0 skipped/pending**.
The preserved artifact is `legacy-t028-mode.GW4QlR`; its full content/mode and
JUnit hashes were not included in Sol's handoff and are not inferred. Root
identified three candidate cascade bugs—`NF9`/`state8` misparsing, missing
`t19_mode`, and double-quoted `$#`—and the writer is verifying/fixing them;
the corrected rerun was pending at that checkpoint. This historical result
closes no task and is not an acceptance aggregate.

The authoritative T028 rerun remains **failed**. Its outer run took
**1,836.12 seconds**, with **1 failure and 1,873 deselected**; the inner run
reported **3,128 passed, 78 failed, and 0 skipped/pending**. The JUnit artifact
is `/tmp/openrepotools-sol-legacy-t028-rerun.38xE79/t028.xml`, SHA-256
`c150ff070b2871c285a5e5347a928f9c9a6ef54f29c17a9cfa78da18c6915be5`.
The source snapshot was unchanged; only the manifest prefixes supplied were
`bd86217c` (content) and `02b46f1b` (modes), so no full manifest digest is
inferred. The failures include 13 skill/ctx assertions followed by the T018
guard-roster and T019 lease/projection/remote-attach cascade; the complete
failure list is in `failing-assertions.txt` under the artifact directory. T028
remains open and this rerun closes no task or acceptance box.

The six-stage native-swap diagnostic reported **3 passed and 10 failed**.
It is diagnostic only; no artifact or digest was supplied with the current
handoff, so none is inferred. It is not final acceptance and does not establish
runtime capability or close any task.

The post-close two-second timeout diagnosis remains a timing/fixture finding,
not acceptance: the actual ready-held observation arrived at **2.5702 seconds**
while the production operation deadline remains **120 seconds** unchanged.
Astra approved a **10-second fixture timeout** plus a dedicated **2-second
negative pending gate**; that gate is still pending and no production timeout
was changed. The post-close diagnostic artifact is
`/tmp/openrepotools-sol-sixstage-postclose-diag.cPChpM/postclose.xml`, JUnit
SHA-256 `2a19df2d21f098fcc551652bc1c700178bf47e332799aaf1b55858d30df0a8c0`;
its one selected ready-held test timed out, so this remains a diagnostic.

Sol's latest isolated SDK no-send slice reported **201 passed, 1 failed, 0
skipped/errors** (202 selected) in **6.967 seconds**. The JUnit artifact is
`/tmp/openrepotools-sol-sdk-nosend-gate.TaFJ5U/sdk.xml`, SHA-256
`863426bbb48fcdd9c79ff47f38a4c55084784be717504526edba7ece569d7ebc`.
The one failure is `test_status_produces_exact_native_reservation_no_send_receipt`;
the missing receipt remains an implementation diagnostic. This overlay is not
combined with other runs and closes no task or acceptance box.

Runtime capability remains unsupported/unverified, and the authenticated
account path remains **NOT RUN**; neither is changed by these diagnostics.

T018 remains unchecked: T015–T019 require a successful held native swap, and
the new source/tests for that path are still pending. No new runtime rerun or
approval closure is claimed here.

## Current parallel checkpoint — correction in progress, not final acceptance

This checkpoint preserves the current parallel evidence while packaging and
implementation corrections continue. Test results alone close no task or
approval box; the separately reviewed T022 scope is called out below.

The state/profile/adoption slice reported **170 passed**. Its JUnit SHA-256 is
`e3dc5dbd2addbd548257c099982958255bcc7612aab99321e682bec480291dee` and its
manifest SHA-256 is
`4f3e5bf8e781c0423c2a24bb5644901e0d441f52576cfc839e31d7ebbbeaa283`.

The initial controller slice reported **116 passed and 15 failed**. The
failures include schema cascades and durable architecture gaps under
correction. Its JUnit SHA-256 is
`a4bed33d4433c69c264247aa5d5399c6a6efd9c32971f390ab403f5c3341f954` and its
manifest SHA-256 is
`4ea459b314685add7847bdb5840e47f6596afe3b2b587bf445c5f1bf1620f5c0`.

The corrected probe/SDK/help slice reported **410 passed and 3 failed**. Its
JUnit SHA-256 is
`b3f781d0d0dd3cd052597f746304e0f972619b80ea9d48acb92abc045029ef42` and its
manifest SHA-256 is
`4cbcdf25afa07bcdc97fbb0d43678463bdb9c00bd8a9def5e950fd75aa528130`.
Three packaging fixes were underway at that checkpoint.

A later **297 passed, 22 failed** packaging snapshot is invalidated for
acceptance: 20 failures came from a snapshot with corrupted `555/444` modes,
while two genuine wording/index test fixes were completed and their rerun was
still pending. The aggregate must not be treated as acceptance. The original
full baseline never ran. The retired queued T028 snapshot was mode-corrupt and
produced no JUnit; Sol is rebuilding mode-preserving snapshot plus hash/mode
verification.

The corrected probe removed unverified aliases and recorded unsupported or
unavailable worker/orphan/load/wake facts honestly; no runtime rerun is claimed.
Remaining planned work covers rollback/history, the SDK reader, public native
lifecycle, child routing, status, and `ctx`. These are plans only and do not
close new tasks or approval boxes. The replacement for the invalidated
packaging snapshot was initially pending; the authoritative result is recorded
below.

The subsequent authoritative mode-preserving packaging and handoff gate
reported **319 passed, 1,550 deselected, 0 failures, and 0 skips** in 76.19
seconds. Its JUnit SHA-256 is
`2c76ac58c1a3c8e20aa022a97ca161729136c54aaaf69e5520c80de5231b2bcf`.
Strict OpenSpec validation and tracked/untracked whitespace checks reported
clean across 1,580 untracked files; the selector included frozen
handoff integration. Matching pre/post content-manifest SHA-256 is
`d5e56bfbc61c0f2482327c391177919089e536e9ef4f259e1d54810fd600b1fd`, and
matching pre/post mode-manifest SHA-256 is
`073de820aa02c53adeb623d1d4cd80c92b5bd6de7ce4a84c68ea7eec46dd4fde`.
This establishes the snapshot integrity gate but is not native/runtime
acceptance. With root/Astra's scoped review, this is the
**third of 32 task closures** (T022 alongside the already closed T025/T026),
while all other task and approval states remain unchanged. The T022 checkbox
records only the bounded offline FR024/SC007 scope; native/runtime acceptance
remains open.

## Resumed regression batch — final frozen evidence

The historical reserved-transition slice passed **5 tests**, with 1,758
deselected; its interim JUnit SHA-256 is
`8b81f4eecef15c31d3da819c9853224ad7430b141d3b406c049a2a641d24f220`.

The final six-module frozen focus selected the exact controller, daemon, target
adoption, adoption transaction, reserved transition, and runner projection
categories: **314 passed, 0 failed, 1,449 deselected, 0 errors/skips**. Its
JUnit SHA-256 is
`06ec7511054f258af8d0afa988f75c8dfd4bf17b59c826a36eee394a646e5e4d`.

The executed broader managed selector covered the historic 18 families plus
those four modules, but this was only partial historical coverage: it omitted
the focused modules interrupt-drain, interrupt-status-wire, lineage-transfer,
source-history, and adoption-assessment. It completed with **938 passed, 0
failed, 825 deselected, 0 errors/skips** in **112.70 s**. This is not the full
prior 951-case historical census plus new modules. The four new-module counts
were target adoption **16**, adoption transaction **11**, reserved transition
**5**, and runner projection **45**; the old 20 failures are reconciled in
this snapshot. Its JUnit SHA-256 is
`8f47923a6ed4935c818da1912f8cfb9f4810d554d7afe946f61da8f7cb7e84c3`.

Strict `openspec validate ... --strict` passed, and tracked/untracked
whitespace validation passed with 158 untracked files and zero findings.
These tests are offline, fake-runtime, no-auth evidence only. The busy-parent
runtime result remains inconclusive; production native swap/restore and
authenticated account validation remain unproven. No Speckit/OpenSpec task or
acceptance box changed.

## Native adoption, legacy-managed migration, and busy-parent evidence — correction in progress

The first frozen probe-unit snapshot used the canonical isolated selector
`test_lane_managed_probe or test_lane_managed_loopback_probe`. It completed
with **73 passed, 6 failed, and 1,628 deselected**. All six exact failures were
busy-parent barrier cases: the continuation matcher selected the Bash tool ID
instead of the exact parent Agent tool ID, so no barrier was entered. Review
also found that response completion could be attributed by an unrelated later
SSE write. Both bounded probe/test corrections were made before re-freeze; no
runtime result from this red snapshot was treated as evidence. Its private
temporary artifact is `openrepotools-probe-unit.Led3tZ/`, its JUnit SHA-256 is
`1554b7fce4a530c9f9e1bb3c0dfac100789aa9b019a1a7764d30735cbf06b3c2`,
and its eight selected dependency hashes were identical pre/post.

The corrected selector then passed **80 tests**, with no failures, errors or
skips and 1,629 deselected. Its eight-file pre/post manifest was identical.
Private temporary artifact `openrepotools-probe-unit-rerun.czlgLB/` has JUnit
SHA-256
`0370573721966caa9a69e76c0a153196ffd1a3e772049d92ade8e53fca38b046`
and manifest SHA-256
`679f53026fe25164d3a5c50fb76ff14dab14daf0128a9e3eac7dbd647103f493`.

That green unit gate authorized one bounded busy-parent run under the separate
explicit approval. The exact observation and limits are recorded in
[live-validation.md](live-validation.md). In brief, the run positively
observed an exact pending parent Agent request plus immediate pre-entry child
and Bash liveness, an empty sticky request epoch through target hold, coherent
interrupt/terminal/process facts and cleanup. It did not prove blocked-response
cancellation, exact held parent load, completed-source continuity, worker-state
clear, orphan clear or a positive orphan path. The report remains
`inconclusive` with `support_claim=false`. Private temporary artifact
`openrepotools-busy-parent.MfKev7/report.json` has SHA-256
`bd463d8fc4f0daa189b1cc11341e1f5309358dd2395e795a4c8c78cb2ed696b0`;
the eight-item manifest, SDK/CLI pin and image identity were unchanged pre/post.

The next frozen managed focus selected the complete controller and daemon
modules plus `test_lane_managed_target_adoption` and
`test_lane_managed_adoption_transaction`. It completed with **241 passed, 22
failed, and 1,449 deselected**. The 21 selected dependency/contract files were
identical pre/post. Private temporary artifact
`openrepotools-adoption-focused.XHms9d/` has JUnit SHA-256
`d6d934a4bcccb670a17796a502f75b8d05bd9d6809c63ff6ef629bfc69dae6e8`
and manifest SHA-256
`57c8f0ddc6aea314e4289aa2a067c29ea8f63d042cb9d923da5fc6b98ee7b80d`.

Nineteen of the renamed prior 20 baseline nodes still failed; the prior
`test_start_validates_every_spec_before_first_open` node passed. Three
additional nodes failed: public socket explicit-release dispatch, real native
mixed-roster refusal, and the new real controller/state adoption fixture. The
bounded failure census is 14 controller tests, seven daemon tests and one
target-adoption test. Dominant observed causes are fixture/expectation
alignment around exact claim owner scope, transcript source profile, explicit
dispatch, the trusted state-store recovery seam, add-worker error precedence,
and enforced claimless read-only controls. The state adoption-transaction
module was green. The original 951-case selector plus the two adoption modules
has **not run** on this snapshot; it remains held until the three assigned test
owners correct and explicitly re-freeze their files. Production controller,
state, daemon, probe code, probe tests and governed contracts remain frozen.
All owned test and runtime processes had exited before the three assigned
test-only files were thawed for correction.
No failure is waived, and no task or acceptance checkbox is closed.

## Native source-history and adoption assessment — focused green, census red

This frozen offline batch adds bounded native source archival and a read-only
adoption assessment. It does not perform adoption, transfer a controller,
enable native swap/ctx, or establish live support. All runs used the canonical
serialized `tests/run.sh` wrapper and a 45-file production, test, probe,
contract, design, and shared-infrastructure manifest.

The first focused run selected 90 cases and completed with **74 passed, 15
failed, 1 error, and 1,585 deselected**. The 15 source-history failures were
test-fixture alignment failures: `_fenced_authority` had an actual six-value
return while its callers still unpacked five values, including one caller that
consequently supplied an interrupt frame as the archive operation ID. The
setup error was exactly
`tests.test_lane_managed_adoption_assessment::test_pending_recovery_refuses_without_mutating_assessment_inputs`:
the test requested the absent `runtime_socket_path` fixture. Writers corrected
only those tests; production sources did not change. The private temporary
artifact basename is `openrepotools-history-focused.tI3s1i/`, the JUnit
SHA-256 is
`8d8f332d71ec1afa080bb91e207b63f8e4a70c2d4c55132aa05aae109a6443ce`,
and its matching pre/post manifest SHA-256 is
`9428537e710b370e792ff01c129ac29bd6ea24f60543e0bdb3b34aec956219b1`.

The second focused run selected the same 90 cases and completed with **89
passed, 1 failed, and 1,585 deselected**. The exact remaining node was
`tests.test_lane_managed_source_history::test_archive_revalidates_owner_daemon_and_generation_before_persisting`.
Its daemon case mutated the task-stop authority seam although archival is
contractually governed by coordinator-interrupt authority. The test was
aligned to the actual seam and parameterized into three independently named
owner, daemon, and generation cases, with no production edit. The private
temporary artifact basename is
`openrepotools-history-focused-rerun.Ie0NDW/`, the JUnit SHA-256 is
`2e35119181537cc82b94c3b6e9fbd005dffd81cacc8864d11981850dd1cbb2dc`,
and its matching pre/post manifest SHA-256 is
`0826ca49119f25a73bf9a2b194b9670179f360f395a4db7ea4c94210c2d3f57a`.

The final focused run selected **92 cases and passed all 92**, with no
failures, errors, or skips and 1,585 deselected. Its private temporary artifact
basename is `openrepotools-history-focused-final.v1RcmL/`, the JUnit SHA-256
is `3f881bc878e82183fb0bd3a004f21e41f2f7c2d6084b56e4c292e5c5a38b2768`,
and its matching pre/post 45-file manifest SHA-256 is
`9391f9069dfd6f6a89641f1bca4f9f4f9fa272090d80145682dde03d4ec5a479`.

The combined prior census plus source-history and adoption assessment then
completed with **930 passed, 21 failed, 0 errors/skips, and 726 deselected** in
123.30 seconds. Exact JUnit `(classname, name)` comparison preserved every one
of the prior 20 failures and removed none, but added this failure:
`tests.test_lane_managed_lineage_transfer::test_pending_owner_recovery_holds_transfer_before_claim_journal_or_index`.
It refused while constructing the fixture because its generated Unix socket
path exceeded the production 104-byte bound. This is a new unresolved census
failure, not a waived baseline failure. The private temporary artifact
basename is `openrepotools-history-combined-final.ty95kK/`, the JUnit SHA-256
is `26fbee0c78a9641b8e6a3710e75ecfd53d8aaf6647093d05913b382d13e083b8`,
and its matching pre/post 45-file manifest SHA-256 is
`9391f9069dfd6f6a89641f1bca4f9f4f9fa272090d80145682dde03d4ec5a479`.

Strict OpenSpec validation passed for change
`separate-swap-ctx-handoff`. The focused green result and strict validation do
not override the 21-failure combined result. No acceptance checkbox or task is
closed.

A subsequent test-only correction replaced that lineage-transfer test's long
constructed socket path with the existing short, private
`runtime_socket_path` fixture; production source and the 104-byte bound were
unchanged. The requested four-module 112-case focus and combined 951-case
rerun did **not run**: the canonical serialized wrapper remained queued behind
an unrelated workstation pytest throughout the bounded additional wait and
was stopped before its own `python3 -m pytest` began. No JUnit was created.
Private temporary artifact basename
`openrepotools-history-focus4.kJ1lmO/` contains only an abandoned pre-run
manifest and path list, which are not test evidence. Therefore the actual
evidence remains the 92-case focused green result and the 951-case combined
result with 21 failures above; the independently confirmed JUnit difference
still has the socket-fixture node as its sole addition and resolves none of
the 20 baseline nodes.

The user subsequently authorized the repository's existing isolated
`tests/run.sh --parallel-safe` mode for this batch only. On the frozen snapshot,
the four-module focus selected **112 cases and passed all 112**, with no
failures, errors, or skips and 1,565 deselected, in 11.03 seconds. This
validates the test-only short/private socket-fixture correction together with
source history, adoption assessment, loopback, and lineage transfer. Its
private temporary artifact basename is
`openrepotools-history-focus4-isolated.e4BL1b/`; the JUnit SHA-256 is
`be85275b128c632517f8b01736ac172b37b9513368f3f40269727e2da48be80d`,
and its matching pre/post 45-file manifest SHA-256 is
`2d000da7f0cebd551b719d0a6cc849023f42eb1c43f9168094357b573bc8f3f0`.

The isolated combined rerun then selected the same **951 cases** as the prior
red census and completed with **931 passed, 20 failed, 0 errors/skips, and 726
deselected** in 124.75 seconds. Exact JUnit `(classname, name)` comparison
found equality with the preserved 20-node baseline: no baseline node was added
or removed. Compared with the immediately preceding 21-failure census, the
sole socket-fixture addition was resolved. Its private temporary artifact basename is
`openrepotools-history-combined-isolated-final.D7oNEm/`; the JUnit SHA-256 is
`5ef9d364d71ad038d20945127a25985599be2815f49ba74e4b6191a3e0e89cc3`,
and its matching pre/post 45-file manifest SHA-256 is
`2d000da7f0cebd551b719d0a6cc849023f42eb1c43f9168094357b573bc8f3f0`.
The 20 baseline failures remain open and unwaived. These offline results make
no live/runtime capability claim and close no acceptance checkbox or task.

## Observational drain and lineage-transfer — validated bounded offline batch

This frozen offline batch contains the controller's read-only coordinator
interrupt drain/status projection, the state layer's bounded internal exact-CAS
workspace-claim replacement, three new focused test modules, and clarifications
to the coordinator-interrupt and managed-control contracts. The claim transfer
is an internal prerequisite only: it has no public ctx route, schema change, or
controller adoption. The drain projection is observational and grants no
runtime capability, target authorization, restore, release, or public success.

The ordinary serialized wrapper could not start while unrelated workstation
pytest processes remained live. Its waiting wrapper was terminated before an
openRepoTools pytest process began; private temporary artifact basename
`openrepotools-new3-final.UfvLAG/source-test-contract-pre.sha256` is therefore
an abandoned pre-run manifest, not evidence. The user then explicitly
authorized the repository's existing isolated `tests/run.sh --parallel-safe`
mode for this batch. That authorization and its private ambient paths do not
establish general parallel-execution safety or change the normal serialized
repository rule.

The isolated new-three selector passed **54 tests, 0 failures/errors/skips**,
with 1,570 deselected, in 12.79 seconds: **29** interrupt-drain, **5** public
status-wire, and **20** lineage-transfer cases. Its nine selected production,
test, contract, and shared-infrastructure files had identical pre/post
manifests, each with SHA-256
`7bed3227f1fcb8d50d676d7dbca15faea0bd6fe427bbc06c4d2463ec06ef8a8c`.
The JUnit report has SHA-256
`89e09fc18a2424dcf2310a8553759ccbc4016ca91533fde44e08f46e71e3cf4a`;
its private temporary artifact basename is
`openrepotools-new3-isolated.kiLGlH/new3.xml`.

The isolated combined selector then added those three modules to the previous
844-case census and completed with **878 passed, 20 failed, 0 errors/skips,
726 deselected** in 149.51 seconds. All 41 prior and new selected source, test,
probe, contract, and shared-infrastructure files had identical pre/post
manifests, each with SHA-256
`6d5fc318e2a0d4c4b627a645fe4514ed7a5d97f29ae8af70a6191c253a25647f`.
The combined JUnit report has SHA-256
`defd44be0efe912041b29cd166ed6527c0252b41e6e7fee70da56c1da48a5af9`;
its private temporary artifact basename is
`openrepotools-combined-isolated.pPWTX5/combined.xml`.

Direct JUnit comparison found the combined run's 20 failed node IDs exactly
equal to the prior baseline set: no baseline failure resolved and no new node
failed. The three new modules contributed **54 passing cases and 0 failures**
inside the combined report, so the unchanged prior 844-case portion remains
**824 passed and 20 failed**; these non-overlapping subset counts are not added
again to the combined total. The exact 15 controller and five daemon baseline
node IDs remain listed in the next census section and none is waived.

Read-only static checks also passed: strict OpenSpec validation reported change
`separate-swap-ctx-handoff` valid; Python syntax compilation passed for the two
changed production modules and three new test modules; and whitespace checks
passed for those files and both changed contracts. These offline checks and
tests are not live/runtime acceptance. No task or acceptance checkbox is
closed, and no live/runtime support claim is made.

## Coordinated ctx and terminal-evidence census, 2026-09-18

The frozen ctx-policy, ctx wire/CLI, SDK terminal-evidence, native lifecycle,
and existing broad managed families were validated through the canonical
serialized wrapper. No source or test file changed during either final run.

Two earlier focused attempts were correction snapshots, not release totals.
The first selected 421 cases and completed with **418 passed, 3 failed** and
1,148 deselected; its JUnit SHA-256 is
`6c8db2cba35fe0627e559f7e67789b618908cab556a0303b3bdb014b22da3be0`.
After the first corrections and one added real-IPC case, the second selected
422 cases and completed with **421 passed, 1 failed** and 1,148 deselected; its
JUnit SHA-256 is
`27193b498685059ccd798c6a3022da44fe8ba27c39dff4709763ce7227650a5a`.
Private temporary artifact basenames are respectively
`openrepotools-focused.cCuoYO/focused.xml` and
`openrepotools-focused-rerun.bKBIt0/focused.xml`. These attempts overlap each
other and the final combined run, so their pass counts are not summed.

The terminal-evidence gate passed **7 tests, 0 failures/errors/skips**, with
1,563 deselected. Its five-file pre/post manifest has SHA-256
`ba21c7278036abd37ede2828eeacdf36800ada30ba0f24d0ba184896e832e676`;
the JUnit report has SHA-256
`c938a43a71e10de23328cbab60777f6e68ed58ab9ea48204805f2e4c9bc108b7`.
The private temporary artifact basename is
`openrepotools-terminal-evidence.EEEHWg/terminal-evidence.xml`. The reused-ID cases preserve
the current bounded behavior: a mixed historical/current admission roster is
unsupported until source-history archival exists, and stale terminal events
cannot close the current incarnation. The stale event is ignored as a
terminal fact while ownership conflict and uncertainty remain recorded; this
is correlation safety, not successful roster reconciliation.

The subsequent combined selector included the complete focused matrix plus
the full controller, daemon, state, profiles, probe, and loopback families. It
completed with **824 passed, 20 failed, 0 errors/skips, 726 deselected** in
120.42 seconds. The exact selector was:

```text
test_lane_managed_controller or test_lane_managed_daemon or
test_lane_managed_state or test_lane_managed_profiles or
test_lane_managed_probe or test_lane_managed_loopback_probe or
test_lane_managed_ctx_policy or test_lane_managed_ctx_wire or
test_lane_managed_terminal_evidence or test_lane_managed_sdk or
test_lane_managed_native_start_integration or
test_lane_managed_native_admission or test_lane_managed_native_stop or
test_lane_managed_native_interrupt_runtime or
test_lane_managed_stop_integration or
test_lane_managed_coordinator_interrupt or
test_lane_managed_interrupt_integration or test_lane_managed_cli
```

All 36 selected production, test, shared-infrastructure, and probe files had
identical pre/post manifests, each with SHA-256
`8036a3ac3c3c5298b7454485a3564e05ae25636c87f004ea52d4b9e1476db4d4`.
The combined JUnit report has SHA-256
`6f0deddbedf540741820804c65114e744704986bbbae4cc1c5e88b67886d5735`;
its private temporary artifact basename is
`openrepotools-combined-census.0TtZFX/combined.xml`.

Parsing that final JUnit with the exact earlier focused expression selected
**422 cases, all 422 passing**. This establishes the corrected focused subset
inside the combined snapshot without adding its overlapping count to the
combined total. The matching pre/post manifest establishes that no selected
source or test changed during the combined run.

No failure is waived. The exact remaining census is **15 controller** and
**5 daemon** failures:

- Controller: partial-unenroll claim-index recovery; reserved-UUID resume;
  release/dispatch; released unsent mail across lifecycle; add-worker held
  retry; lifecycle mail/transport preservation; start fixed-roster preflight;
  all-spec validation before open; failed and cancelled start recovery; start
  request deduplication; uncertain-start reload; accepted-open recovery;
  unenroll/re-enroll generation rollover; and changed-participant retry.
- Daemon: released idle-peer/later-mail dispatch; uncertain-send no-replay;
  post-candidate hold/fence revalidation; releasing the store lock across a
  runtime await; and the public socket held/release/single-ack lifecycle.

Exact failed node IDs from the combined JUnit are:

```text
tests/test_lane_managed_controller.py::test_partial_unenroll_claim_index_crash_stays_indeterminate_after_reload
tests/test_lane_managed_controller.py::test_reserved_uuid_written_by_trusted_verifier_uses_resume_on_next_swap
tests/test_lane_managed_controller.py::test_release_requires_matching_ready_generation_and_dispatches_once
tests/test_lane_managed_controller.py::test_released_unsent_mail_survives_add_worker_and_swap_then_dispatches_once
tests/test_lane_managed_controller.py::test_add_worker_held_retry_is_stable_across_release_reload_and_content_change
tests/test_lane_managed_controller.py::test_lifecycle_carries_only_unsent_mail_and_preserves_transport_effects
tests/test_lane_managed_controller.py::test_start_prevalidates_fixed_roster_and_records_ready_held_without_dispatch
tests/test_lane_managed_controller.py::test_start_validates_every_spec_before_first_open
tests/test_lane_managed_controller.py::test_start_failure_or_cancel_is_indeterminate_and_never_auto_replayed[failure]
tests/test_lane_managed_controller.py::test_start_failure_or_cancel_is_indeterminate_and_never_auto_replayed[cancel]
tests/test_lane_managed_controller.py::test_start_request_dedup_has_no_second_open_and_changed_specs_refuse
tests/test_lane_managed_controller.py::test_start_reload_reconciles_uncertain_mode_and_opens_only_pending_participant
tests/test_lane_managed_controller.py::test_start_recovery_reconciles_accepted_uncertain_open_and_only_continues_pending
tests/test_lane_managed_controller.py::test_unenroll_state_reenroll_rolls_controller_to_higher_generation_for_start
tests/test_lane_managed_controller.py::test_start_retry_same_request_refuses_every_changed_participant_semantic
tests/test_lane_managed_daemon.py::test_real_controller_dispatch_services_idle_peer_and_later_mail_after_release
tests/test_lane_managed_daemon.py::test_real_controller_uncertain_dispatch_is_not_replayed_automatically
tests/test_lane_managed_daemon.py::test_real_controller_held_worker_and_new_fence_are_revalidated_before_intent
tests/test_lane_managed_daemon.py::test_real_controller_dispatch_releases_store_lock_before_runtime_await
tests/test_lane_managed_daemon.py::test_public_cli_socket_uses_real_controller_for_held_release_and_one_ack
```

Several tests still exercise the superseded independent-runner topology, but
their recovery, deduplication, fencing, claim, lock, and at-most-once
guarantees remain requirements. They must be moved to the native coordinator
path rather than deleted or treated as expected failures.

Two architecture dependencies remain explicit. Historical coordinator
interrupt frames currently validate against the one current native context,
while native-context registration refuses a changed runner or invocation.
Native swap therefore needs source-context archival and recovery before
adopting a replacement runner under the same lineage UUID. Separately, ctx
requires a new lineage plus atomic lineage-claim transfer, while the current
state surface offers only separate claim and release operations. The current
guard and terminal-precedence implementation, plus planned observational drain,
do not close
T010, T014, or T021; aggregate drain, safe restore, release/recovery, the
selected-runtime gate, and live account behavior remain incomplete. No task
or acceptance checkbox is closed by this census.

## Live startup and interrupt integration, 2026-09-18

The authorized follow-up covers normal native coordinator startup, binding
the first durable mailbox invocation, hook/event roster tracking, local work
fencing, and the documented SDK interrupt through the existing one-time
durable authorization. Implementation and validation are in progress.

Acceptance requires a fresh real state store to create the native workspace
claim after capability preflight, prepare trusted identity before runtime
open, and bind the actual mailbox ID before the first query. The runtime
tests must exercise actual SDK-shaped hooks/task events and the production
control loop with a fake SDK client, including the interrupt call itself.
Manually registering a native context or submitting a fabricated roster alone
does not establish this integration.

The available hooks cannot observe every internal model request. Request
counts remain unknown, and a local query/tool fence grants no zero-request
runtime capability. Aggregate drain, process exclusion, target restoration,
recovery/release completion, and successful public swap remain later work.

The pre-change private snapshot is `stage12-integration/` beside the existing
Gate 0 artifacts. The previous broad JUnit survived and supplied the exact
16 outstanding controller/daemon failure node IDs after excluding the
subsequently corrected loopback fixture. This census is preserved in
`historical-broad-failures.json` with SHA-256
`45301a0510172cf388f924b9c8b579d225a3088c2043a4c6e0a639e016979ffd`.
Final focused and regression evidence must be recorded below before claiming
these two integration steps complete.

## Internal coordinator interrupt implementation, 2026-09-18

The next authorized slice adds controller intent/evidence persistence,
authenticated daemon callbacks, and independent SDK persistence IPC. Its
`coordinator_interrupts` ledger is separate from `native_stops`. The first
authorization durably records that a send may have occurred; exact retries
and reloads cannot authorize another send, and changing request/fence/roster
identifiers does not remove source exclusion. IPC also consumes each positive
authorization once to prevent a delayed reply from authorizing a retry.

The controller checks the active operation, durable native fence, complete
admission coverage, source identity, claim authority, and typed roster/evidence
correlations. Eight independent evidence kinds preserve worker/tool/effect,
parent, request-observation, and process facts without computing quiescence,
readiness, successful restoration, or a runtime capability. Missing new record
fields and native-stop records under the interrupt kind refuse on reload.

The [contract](contracts/coordinator-interrupt.md#internal-persistence-slice)
records the bounded scope. Live roster production, SDK interrupt dispatch,
aggregate drain decisions, public routing, and Gate 0 remain open. T005–T014
and T027 are broader than this slice and remain unchecked. The Stage 1 probe
regression check remains separate from runtime capability acceptance.

Astra's final architecture review found no remaining source blockers. The
canonical focused run passed **166 tests, 0 failures/errors/skips** after a
test-only fixture correction. The first run had 161 passes and five instances
of the same `LineageRecord`/mapping fixture error before the tested behavior;
production source did not change between runs. Root inspected the final JUnit
counts, and pre/post source manifests match.

The focused selector covered `test_lane_managed_coordinator_interrupt`,
`test_lane_managed_interrupt_integration`, `test_lane_managed_sdk_interrupt`,
`test_lane_managed_native_stop`, `test_lane_managed_stop_integration`,
`test_lane_managed_sdk_stop`, `test_lane_managed_sdk_stop_ledger`,
`test_lane_managed_sdk_admission_ipc`, and
`test_lane_managed_daemon_admission_integration`, using serialized
`tests/run.sh -k '<names joined with or>' --junitxml=<private-artifact>`.

Private evidence is in `interrupt-implementation/` beside the existing Gate 0
artifacts. `focused-rerun-20260918.xml` has SHA-256
`6881be40b48e2541775538f5b4658235c8aaf9516e77175b771ea0fa1e8a7435`;
`focused-rerun-pre.sha256` has SHA-256
`00e1396751fc4010252cf6d645b6ce5059baae8430339acdf509f37d7f362df1`.
That manifest records all selected source/test hashes. Production hashes are:

| File | SHA-256 |
| --- | --- |
| `lane_managed_controller.py` | `f4bdee1820b55d7829253c78b9d175eda2dc1ec54ffaf06c4b1db6905e0274ed` |
| `lane_managed_sdk.py` | `8ce7289491ed9ff2ba6f3a3198c767ac47ee3ff02cb2239399c3663db943c230` |
| `lane_managed_daemon.py` | `7710682a73855a4ff1718c0a02a5401bdcb567c4863450fc6d617c231b2046de` |

The broader canonical selector (`test_lane_managed_controller or
test_lane_managed_daemon or test_lane_managed_state or
test_lane_managed_probe or test_lane_managed_loopback_probe`) completed with
**379 passed, 17 failed, 0 errors/skips**. Sixteen failures split into the
same 11 controller and five daemon lifecycle areas recorded in the earlier
735-pass census below. Those existing test files are unchanged, and this
slice does not modify the failing lifecycle implementations. The older JUnit
file was unavailable after the bench restart, so an exact prior failure-name
comparison was not possible. No failures are waived or marked expected.
`broad-20260918.xml` has SHA-256
`e763f6a9fceb2c1cf3f98e7a94e282b2a36ee8aa27d4e099488efa3023f9e0a7`;
the broad pre/post source manifests match. State (96), daemon schema (54),
and daemon admission integration (35) all passed.

The seventeenth failure was in the previously unrun final Stage 1 loopback
test: `runpy.run_path` returns a dictionary, but the fixture patched it as an
object. The corrected test patches the helper's actual globals mapping.
Both probe modules then passed **64 tests, 0 failures/errors/skips** through
the canonical runner. This closes the pending final Stage 1 unit-test gap;
neither probe implementation nor runtime experiment was changed or rerun.
The corrected loopback test SHA-256 is
`404e467d86d4e2f60398c8b1555723d3c201e09dddfe8e61209b8c70727058c0`.
`probes-rerun-20260918.xml` has SHA-256
`0d279ce4d627c3d48d27e0d636b78ea292e8391ca288d635bb60da6f19f30042`;
its matching pre/post four-file manifest has SHA-256
`dc3daed36bc572d163d49d58e25db7f8cf989f81e46d4746273afb2f6de97514`.

These selectors overlap; their pass counts are not a combined release total.
The internal persistence slice is implemented and tested, while the broader
feature remains incomplete. No full-suite/legacy run, live account test,
runtime capability grant, commit, installation, or deployment occurred.

## Coordinator interrupt design, 2026-09-18

Brett authorized the next governed design step after Stage 1. The
[decision](../../openspec/changes/separate-swap-ctx-handoff/coordinator-interrupt-decision.md)
and [contract](contracts/coordinator-interrupt.md) define distinct whole-roster
authorization, source-run deduplication, independent drain/effect evidence,
continuous request observation and uncertainty-preserving recovery. OpenSpec
deltas and the linked Speckit plan, model and existing task IDs are reconciled.
This is a design deliverable, not a production implementation or a completed
runtime gate. The existing per-task native-stop transaction remains separate.

Astra's design review found no remaining blockers. Strict OpenSpec validation
passed; Sol checked 63 relative Markdown links with none missing and all 32
unique task IDs/references with completion states preserved. The documents
remained unchanged during that validation and `git diff --check` passed.
The pending Stage 1 combined probe suite remains unrun because unrelated live
pytest processes still occupy the canonical guard; no test waiter remains.
No production code, source tests, runtime experiment or deployment was added
in this documentation step.

## Stage 1 runtime investigation, 2026-09-18

The bounded investigation is recorded in
[Stage 1 runtime boundary](../../openspec/changes/separate-swap-ctx-handoff/stage1-runtime-boundary.md).
SDK `0.2.153` and its bundled CLI `2.1.273` were recovered in an isolated
environment and the selected executable digest matched the earlier reference.
The fresh no-auth baseline reproduced successful initialization and a
successful nonexistent-task stop acknowledgement with no terminal event.

A new missing-parent negative control uses the SDK-generated exact resume
argument and sends initialization only. The real CLI rejected the missing
parent before successful initialization, exited naturally with status 1, and
wrote no transcript. Its error frame echoed the requested UUID; that echo is
not loaded-session evidence. There is no demonstrated false-readiness bug from
this control. The focused probe tests passed **25**, with 1,427 deselected;
reports, hashes and interpretation are in the investigation record.

The additional scripted loopback gateway run created a real native background
Agent and Bash process. Stopping the actual task yielded a receipt, stopped
notification, tool-terminal evidence and process exit before parent teardown.
The target initialized with the exact source resume argument and held for
eight seconds with zero endpoint requests. A later explicit release confirmed
the same native session UUID and original source/Agent history. Exact internal
load timing remains unknown. A repeat with the original parent turn settled
still made one request during source stopping: that task-specific candidate
fails the zero-request account-control requirement. The unfinished-worker
control first refused target launch when its scoped process cleanup was
incomplete; the corrected control excluded the observed fixture processes and
resumed the exact parent with zero held requests and preserved native history
after release.

The final documented-interrupt control stopped the actual native task and
tool, observed sleeper exit before teardown, and made **zero source-control
requests**. Exact parent resume then held for eight seconds with **zero target
requests**; release preserved UUID/history. Astra accepts this as a bounded
candidate for coordinator-wide interruption in scripted API/gateway mode. It
is not interchangeable with the existing task-specific authorization.
Whole-roster durable authorization/drain, actual account modes, multiple-child
and busy paths, full identity/effect accounting and internal orphan/wake
evidence remain open. T003, T004 and T030 remain open. No production runtime
capability has been granted. See the investigation for exact report hashes,
source snapshots and the architecture decision.

Final probe syntax and whitespace checks passed. The final combined focused
suite was **NOT RUN** because the canonical wrapper waited behind unrelated
live pytest processes; our waiters were cancelled before pytest started and
none remains. Earlier **25-pass** missing-parent and **28-pass** loopback
snapshots are recorded separately; the latter does not validate the final
probe changes. Final runtime reports and frozen hashes are preserved in the
investigation record and private manifest. No production files were changed
by Stage 1, and no commit, installation or deployment was performed.

## Native stop follow-up, 2026-09-17

T026 documentation alignment is complete after reviewing all six command,
skill and manual files. They distinguish the approved native workflow from
incomplete parser/lifecycle/runtime support; installed copies no longer rely
on relative links to uninstalled, unpublished feature records. This is a
documentation task closure only.

The actual selected-runtime missing-task stop probe returned success without
any matching terminal notification. See the
[negative-control observation](live-validation.md#2026-09-17-missing-task-stop-control).
Its 17 isolation/observation tests passed through the canonical wrapper in
3.12 seconds; artifact: `py-bench:/tmp/lane-probe-stop-control-20260917.xml`.
This does not close Gate 0.

Astra approved the separate
[internal native stop transaction](contracts/native-stop.md): persist intent
before a single send authorization, retain acknowledgement and terminal facts
separately, and never resend automatically after uncertainty. The controller,
daemon callbacks, SDK IPC and runner control path now implement this internal
mechanism. It has no public stop route and is not integrated as a completed
native swap workflow.

Astra's final static review closed the post-authorization error race,
overstated terminal provenance, multiple-child stop exclusion, task-progress
invalidation, dropped stop reply, ignored persistence refusal, duplicate retry
reader failure, and refusal-task bound bypass. A later provenance fix keeps
the actual terminal notification separate from subsequent hook observations.
This is code review evidence, not a runtime capability grant.

The review also found and fixed a real ctx preflight defect: a writable
coordinator now requires persisted claim identity and an available atomic
transfer method before any fencing or runtime action. The regression requires
no new runtime calls, runner opens or request reservation on that refusal.

Intermediate persistence/transport validation:

- Native-stop controller, daemon schema and real-store tests: **72 passed**,
  7.69 seconds; `py-bench:/tmp/lane-stop-durable-20260917.xml`.
- Expanded real-store tests including the actual SDK IPC readers, daemon and
  controller: **14 passed**, 9.45 seconds;
  `py-bench:/tmp/lane-stop-bridge-20260917.xml`. The transport is a pair of
  queues; this does not construct a live SDK client. Cases cover both evidence
  orders while the control lock is held, a lost acknowledgement followed by
  reload without reauthorization, preserved claims, same-generation daemon
  takeover, and malformed durable stop records.

These groups overlap. SDK stop dispatch and review fixes were still changing
at this checkpoint; these numbers establish only the named intermediate
slices and must not be presented as frozen-candidate or live acceptance.

### Frozen follow-up result

The final `tests/run.sh --parallel-safe -k 'test_lane_managed'` run in
`py-bench` completed with **735 passed, 16 failed, 693 deselected**, no skips,
in **111.97 seconds**. This supersedes the prior 617-pass/72-failure census
for the current working tree. Results:
`py-bench:/tmp/lane-native-stop-final-20260917.xml`; source/test/fixture
manifest: `py-bench:/tmp/lane-native-stop-final-20260917.sha256`.
All **36** manifest files were rehashed after the run: **zero changes**.

All stop-specific modules passed: controller persistence **7**, SDK controls
**11**, SDK lifecycle ledger **11**, and real-store/IPC integration **20**
(**49 total**, included in the 735 passes). Control tests use an explicit
fake SDK and inject ledger decisions; ledger tests use admitted synthetic
lifecycle events; integration tests use actual IPC readers, daemon callbacks,
controller transactions and private temporary stores. These complementary
tests do not establish a live runtime lifecycle or a completed public swap.

Also entirely green: SDK baseline **53**, admission IPC **60**, native
admission **37**, daemon admission integration **35**, daemon schema **54**,
Gate 0 fixtures **10**, runtime capability checks **23**, no-auth probe tests
**17**, state **96**, profiles **37**, and CLI **133**. The new ctx preflight
regression passes with no runtime effects. Static review and `git diff
--check` passed.

| Remaining module | Passed | Failed | Work still represented by failures |
| --- | ---: | ---: | --- |
| Controller | 101 | 11 | Unenroll recovery, canonical holder/profile handling, release/ctx and worker mailbox lifecycle, start validation/recovery and request semantics. |
| Daemon | 30 | 5 | Released-work dispatch, uncertain-send recovery, post-await fencing, lock release across runtime awaits, and the public socket lifecycle. |

No failures are waived or marked expected. Several tests still describe the
superseded independent-worker topology; their underlying guarantees must move
to the native coordinator lifecycle. Passing repaired prototype fixtures does
not close those native implementation tasks. The full serialized suite,
legacy Bash suite, platform CI and authenticated canary were not run for this
snapshot. T025 and T026 remain the only fully closed tasks. No commit, merge,
installation or deployment was performed in this follow-up.

The next implementation package is the coordinator-only public native start
path, with durable context registered before release or child admission, then
native swap/release/recovery. The release-critical runtime dependency remains
supported terminal-state clearing and held restoration with independently
observed model activity. Gate 0 remains inconclusive; production retains its
pre-effect refusal and no capability grant is created by these tests.

## Required evidence

Every row below remains open until the exact tested revision and results are
recorded. Temporary fake-runtime tests run only through `tests/run.sh` inside
the project execution environment. One designated executor owns the queue.
Public-path tests must exercise the real CLI, daemon, controller and temporary
state implementation where the row concerns their integration; a fake handler
that implements the expected behavior itself does not establish that behavior.

| Requirements | Evidence required for acceptance |
| --- | --- |
| FR-001, FR-002; SC-001 | Public enrollment of exactly one coordinator and runtime-observed native Agent/task children; actual parent/task/tool joins and immutable definitions, with no invented child UUID, account, PGID, mailbox, or independent runner. |
| FR-003, FR-009; SC-004 | Gate 0 on the actual SDK-selected CLI, full executable digest, mode and participant kinds; positive orphan-wake control and supported terminal-stop/state-clear candidate; no pre-release target wake or model request. Fake initialization cannot close this gate. |
| FR-004, FR-020, FR-026 | Concurrent public lifecycle/admission requests serialize against current durable owner, lineage and runner; admission persists before allow and is included in a racing seal or refused. Exact retries, changed content, stale replies and malformed frames are tested after reload. |
| FR-005, FR-010, FR-015; SC-002 | One coordinator, two unfinished native children, one completed child and one tracked background Agent: exact parent restore held under the selected account, zero account-control model requests, and no written handoff, generated checkpoint or repository mutation. |
| FR-006, FR-007, FR-018 | Current-run native lifecycle/task/tool correlation, reused IDs, nested parents, stale stop events and child lifetime after Agent-tool return; children stop before parent exclusion. Acknowledged cancellation, parent exit and OS suspension cannot prove quiescence. |
| FR-008, FR-016, FR-027; SC-005 | Unknown effects and detached descendants keep claims and release fenced; completed children stay completed; crash before/after send and partial restart never replay a possibly delivered instruction or completed work. |
| FR-011, FR-012, FR-013, FR-014; SC-003 | Honest held `resume-pending`/`restart-pending` dispositions; `exact-resumed`/`restarted` only from correlated post-release native events; missing transcript fallback, changed definitions, accepted-send without start, cancellation and partial starts remain explicit. |
| FR-017, FR-019; SC-006 | Real shared-index lineage claims, including a read-only coordinator with a writable child, isolated child worktrees and cross-lane equal/alias/ancestor overlap; actual child policy enforcement and dirty/untracked preservation. |
| FR-021, FR-025; SC-008 | Matching operation/owner-generation/runner release once; queued child work routes through the coordinator/native interface, never a child SDK connection. Held, stale, unresolved and uncertain-send cases dispatch no duplicate work. |
| FR-022, FR-023, FR-024; SC-007 | Explicit `ctx hold`/`ctx restart` retain the current account and owner generation, create a new coordinator lineage, and never exact-rebind old children. Caller checkpoint dispatch waits for release; checkpoint-only handoff changes no lifecycle, account, claim or release state. |
| FR-028 | Real common-dir storage, atomic bounded writes, lock/path/owner/mode/symlink refusals and crash reload; snapshots/journals contain no credentials, conversation bodies, generated summaries or checkpoint contents. |
| FR-029 | Read-only same-family profile/account/store verification; settings and actual custom-agent definitions preserved; setup-token and permission/model mismatches refuse; no credential copying, provider override leakage or workBenches mutation. |
| FR-030, FR-031; SC-009 | Managed/legacy enrollment race, exact coordinator lane/name/UUID guard and supported registry projection; native children share the parent identity. Old schemas remain byte-identical on refusal. Shutdown retains owner/service/claims; only proven explicit unenroll clears them. |
| FR-032; SC-010 | Bash 3.2 parsing, literal `swap` lane regression, installer all-or-none inventory and full canonical suite; managed/legacy front doors refuse incompatible ownership without fallback. |
| FR-033, FR-034 | Deterministic tests use temporary state and fake runtimes with no real accounts/network. Live probes require explicitly authorized disposable scope and the separate [live gate](live-validation.md). |
| FR-035; SC-011 | Public help/status distinguish operations, pending and observed worker outcomes, tracked background tasks and unmanaged effects, tested runtime scope and all remaining UNVERIFIED capabilities. |

## Current executor evidence

The new explicit concurrent executor is implemented in `tests/run.sh` as
`tests/run.sh --parallel-safe`. Two such invocations were run concurrently on
2026-09-17: the managed CLI selector passed **129 tests**, and the wrapper
hygiene selector passed **1 test**. Each invocation used its own short-path
temporary home, runtime/config/cache/state roots, protocol/projects roots, and
pytest `--basetemp`; pytest cache and bytecode writes were disabled.

These runs exercise the isolated executor configuration only; they do not prove
absence of all shared state or acceptable load for overlapping heavy suites.
Broader implementation and native acceptance remain incomplete. See the current
execution results below rather than treating historical prototype test totals
as native acceptance.

## Deployment-plan execution, 2026-09-17

The named Codex roles were dispatched: Astra for architecture review, Sol High
for orchestration and assertion audit, and Luna Max for disjoint state, SDK
and controller implementation slices. The controller slice initially repairs
durable request bookkeeping; it does not certify the historical independent
worker lifecycle as the native architecture.

The exact selected CLI initialization baseline now ran in a verified isolated
container and was cleaned up. Its result is **inconclusive**, not Gate 0 success:
positive orphan and terminal-cleared controls remain unexercised, with model
dispatch unknown. Details and the executable digest are in
[live-validation.md](live-validation.md#2026-09-17-isolated-initialization-observation).

Focused checks through the canonical wrapper in the Python bench:

- Profile resolver: **37 passed**, no failures/skips, in 3.73 seconds.
- State/ownership slice: **96 passed**, no failures/errors/skips, in 21.25
  seconds. This closes the state-owned portion of T005–T008; the cross-layer
  tasks remain open.
- Daemon response retention: **1 passed**, in 2.45 seconds. The regression now
  submits 40 requests, proves all were handled, and checks exactly the final
  32 responses remain in order. The prior five-request assertion did not
  exercise the retention limit.
- Probe isolation: **13 passed**, in 4.15 seconds. The reusable no-auth
  initialization probe also ran against the selected binary and removed its
  sandbox; its observation remains inconclusive.
- Focused packaging/CI inventory: **3 passed**, in 4.97 seconds: repeat install,
  missing-file refusal and macOS shell parse inventory. Linux/macOS CI now
  invokes the canonical wrapper; `lane-swap` is included in the macOS syntax
  step. This local inventory test is not an executed macOS CI result.
- T025 packaging and wrapper acceptance after the help changes: **25 passed**,
  no failures/skips, in 8.28 seconds. Both direct and installed `--help`/`-h`
  return locally without invoking `lane-managed`; literal `swap` stays a lane
  value. Missing fetches for either managed command or any of the five managed
  Python modules leave existing artifacts intact. T025 is complete; these
  results do not close the full-suite or live deployment gates.

These are offline results. The full regression, native public workflow and
authenticated canary are still required. No installation or deployment has
occurred in this execution.

### Prior managed-feature census (before the follow-up)

The prior managed selector through `tests/run.sh --parallel-safe`
in `py-bench` completed with **617 passed, 72 failed, 693 deselected in 104.17
seconds**. JUnit: `py-bench:/tmp/lane-managed-final-20260917.xml`; source/test
manifest: `py-bench:/tmp/lane-final-source-20260917.sha256`. This superseded the
intermediate 612-pass census at that snapshot. Follow-up changes above require
new validation; this historical result does not describe their final state.

Entire green modules in that run include runtime capability checks (**23**),
probe isolation (**13**), state (**96**), profiles (**37**) and CLI (**133**).
The new controller preflight/reload refusals, daemon projection cleanup/retry,
and bounded response-history regressions also pass. These counts overlap the
focused results above and must not be added into a separate release total.

| Module | Remaining failures |
| --- | ---: |
| Controller | 22 |
| Daemon | 8 |
| Daemon schema | 33 |
| Gate 0 fixtures | 2 |
| SDK | 5 |
| SDK admission IPC | 2 |

The failures include both prototype contract/fixture mismatches and unfinished
native lifecycle, ctx/release and SDK admission integration. They are not all
obsolete tests, and none is waived. Production capability validation must stay
enabled while fake-runtime fixtures are migrated. The full serialized suite,
legacy Bash helper suite, platform CI and authenticated native acceptance have
not been run for that candidate. Only T025 was complete at that checkpoint;
T026 has since been completed as recorded above. The feature is not
release-ready.

### Refusal behavior and remaining enablement work

Runtime identity reporting and capability assessment now distinguish missing
evidence from observed incompatibility. The production runner has no trusted
capability grant and refuses before constructing the SDK client; caller
fingerprints or launch-frame evidence cannot supply one. Contradictory nested
identities and noncanonical observation fields refuse. An evidence record for
a different runtime is inconclusive, rather than proof that this runtime is
incompatible.

Controller preflight now runs before initial claim reservation and before swap
fencing/interruption. Stored pre-effect refusals are terminal control outcomes
(`phase: complete`, `outcome: capability-refused`), not successful swaps.
Exact retries retain that refusal without reassessment; a new request is
required. An initial refusal leaves no participants/claims and permits explicit
unenrollment. A swap refusal preserves the previous released control operation.
Reloaded paused/starting swaps without capability coverage also refuse before
runtime calls; uncertain later-stage operations remain failed and fenced.

The ctx request journal now reserves its digest and operation kind before
mutation. Its recovery test requires the exact uncertainty refusal, durable
indeterminate state, and fresh recovery evidence rather than stale status.
Daemon unenrollment clears the shared managed projection before local owner
removal, preserves discovery/ownership on projection refusal, and restores the
projection when subsequent local cleanup fails so an explicit retry can finish.

Astra reviewed this as a refusal-only increment. **Before any production
capability grant is enabled**, the implementation still needs effective
configuration/settings/hook binding, binding the assessed executable to the
actual SDK launch, and explicit tested native participant/stop-mechanism scope.
Gate 0 also still needs the actual positive-orphan and supported terminal-stop/
state-clear observations. A synthetically complete unit-test evidence record
is not a production grant. Successful native lifecycle integration remains
unfinished; no full native acceptance task is closed by these refusal tests.

Installer all-or-none coverage and the full canonical suite are additional
release gates. Focused results cannot substitute for that suite. The live gate
requires explicitly authorized disposable profiles/sessions and must not stop
or repoint existing sessions, including Claude team05f.

## Verified unit slices

### Current takeover work (2026-09-17; not behaviorally verified)

Separate writers implemented SDK admission IPC/custom-definition delivery,
daemon callback binding, and native command documentation while the coordinator
implemented durable pre-allow context/admission checks and sealing-race tests.
An independent static review identified missing-ledger, owner-identity,
historical-release, and definition-projection issues for correction. These
edits have no new behavioral test result and close no implementation task.
All four findings now have fixes and regression cases: native fields must be
paired on reload, explicit owner identities must agree, release generation must
be current, and SDK/controller share body-free definition facts with a strict
full-definition digest. Corrupt non-redacted facts refuse reload. The integrated
controller/daemon/SDK and all three new test files pass `py_compile` inside
`py-bench`; tracked-file `git diff --check` also passes. Neither check executes
the tests or proves runtime behavior.

New focused test files are `tests/test_lane_managed_native_admission.py`,
`tests/test_lane_managed_daemon_admission_integration.py`, and
`tests/test_lane_managed_sdk_admission_ipc.py`. Registration is an internal
trusted-authority seam, not yet normal native-start/dispatch integration.
Invocation rollover, nested-parent authority, native lifecycle replacement,
ctx/release/recovery integration, and live gates remain incomplete.

The preserved immutable SDK snapshot wrapper PID `557786` still waits behind
other pytest processes. Its old snapshot cannot validate these new edits.
Do not bypass `tests/run.sh` or treat syntax compilation as acceptance. The
ordinary wrapper remains serialized; independent read-only validation may use
the explicit `tests/run.sh --parallel-safe` mode, which isolates ambient roots
and disables shared pytest caches. New source still requires a frozen
integrated test revision before acceptance.

The requirement IDs above follow the approved native revision. Results below
predate portions of that revision and apply only to their named source hashes;
independent-worker tests are historical evidence, not native acceptance.

- Profile/transcript gate, run `80572`: **37 passed, 0 failures/errors/skips**.
  Root inspected the JUnit result and verified the current profile source hash
  matches the saved manifest:
  `07bf2fd05cc1c79103946eb0b8786bbf11b8e2a441c16fc4c91c3ad6ce1f779f`.
  Evidence: `py-bench:/tmp/openrepotools-profile-final.zsNAzw/`.
  This is isolated unit evidence, not public end-to-end or live OAuth swap
  acceptance; later source changes require rerunning the applicable gate.
- Durable state gate, run `29491`: **73 passed, 0 failures/errors/skips**.
  Root inspected JUnit and verified the current state source hash matches the
  saved manifest:
  `863ef1eb0fc9c70f30a9aa2440d8f70397c04d32d9a98ca99541394136ad7e81`.
  Evidence: `py-bench:/tmp/openrepotools-state-final.MuS2zQ/`.
  This covers the state/ownership unit slice, not complete daemon or legacy
  command integration.
  **Superseded for current-source acceptance:** subsequent generation,
  supervisor-recovery, unenrollment and claim-transfer changes are not covered
  by this result. Rerun the state gate on their frozen revision; the 73-pass
  result remains evidence only for the hash recorded above.
- SDK adapter gate, run `67728`: **48 passed, 0 failures/errors/skips**.
  Root inspected JUnit and verified the current SDK source hash matches the
  saved manifest:
  `ececc01a617481ecd850dd6e586f23ba2f78f0adc1e058d119d30594bf3b9b4f`.
  Evidence: `py-bench:/tmp/openrepotools-sdk-rerun.AYAjdk/`.
  This is unit/fake protocol evidence only. Authenticated exact resume and
  cross-account validation remain unverified.

## Historical canonical results

These are executor-reported observations from intermediate revisions, not
proof that the current moving source passes. Older runs lack a recorded source
hash set; newer artifact locations are listed below. Rerun on a recorded
coherent snapshot before closure.

| Run handle | Scope | Observed result |
| --- | --- | --- |
| 78605 | SDK selector | 40 passed, 7 failed, 972 deselected; behavioral failures assigned for correction. |
| 34826 | Daemon acceptance selector | Collection failed on payload-resolver import-name mismatch; no behavioral acceptance result. |
| 8634 | Daemon acceptance selector | 11 passed, 14 failed, 1021 deselected; fixture/interface and production failures assigned for correction. |
| 22850 | SDK selector | 46 passed, 2 failed, 1013 deselected in 5.64 seconds; initialization handling and read-only fixture/cleanup corrections required. |
| 86138 | Profile selector | 35 passed, 2 failed, 1024 deselected in 1.37 seconds; legitimate shared-projects symlink discovery and a repeated-directory fixture require correction. JUnit and source manifest: `py-bench:/tmp/openrepotools-profile.bFasIc/`. |
| 15286 | State selector | 52 passed, 20 failed, 989 deselected in 19.44 seconds; short-socket/PGID fixture alignment and pending-child identity investigation remain. JUnit and source manifest: `py-bench:/tmp/openrepotools-state.1HpwK1/`. |
| 51062 | Profile rerun | 36 passed, 1 failed, 1030 deselected in 2.58 seconds; shared-store deduplication still loses a valid source-profile config mapping. Artifacts: `py-bench:/tmp/openrepotools-profile-rerun.oDK8k4/`. |
| 85123 | State rerun | 71 passed, 2 failed, 994 deselected in 13.62 seconds; remaining managed-owner/noncanonical-path fixture corrections assigned, production state unchanged. Artifacts: `py-bench:/tmp/openrepotools-state-rerun.LXs6GI/`. |
| 17844 | Installer selector | 62 passed, 1 failed, 1016 deselected in 35.71 seconds; an installable changed between the test's first and second install. Not a coherent-snapshot acceptance result; rerun after installable sources freeze. Artifacts: `py-bench:/tmp/openrepotools-installer.RLUxCn/`. |
| 78066 | Controller selector | 5 passed, 72 failed, 1002 deselected in 37.78 seconds; executor identified missing canonical name/lane fields in central fixtures as the dominant rejection. Fixture correction and a new behavioral run are required, not production validation relaxation. Artifacts: `py-bench:/tmp/openrepotools-controller.R6IH7M/`. |
| 79514 | CLI rerun | Root inspected terminal JUnit: 98 passed, 31 failed, 0 errors/skips, 129 tests; 19.907 seconds in the suite record. Failures include parser/transport, ownership fixtures, startup ordering/discovery and roster validation; correction and rerun required. Artifacts: `py-bench:/tmp/openrepotools-cli-rerun.3bqbhc/`. |

Do not combine pass counts from different revisions into a release total.
Record subsequent terminal results with selectors, revision/dirty-file hashes,
and any skipped coverage. A queued or silent live handle is neither a pass
nor a reason to restart the same run.
